"""Forward company-event calendars - the vendor decision of 2026-09-18.

`EventScore.md` section 4 recorded three families as ABSENT **with evidence**:
FDA/clinical decisions, court decisions, and investor days had no forward
calendar anywhere in the tree, and the moomoo economic-calendar probe returned
50 rows that were every one a macro release. Section 7 Q5 declared the
``forward_calendar`` interface and left the data source as a vendor decision.

That decision is now made, and this module is it:

===================  =========================================  ==============
Family               Source                                     Cost
===================  =========================================  ==============
FDA / clinical       pdufa.bio ``/api/v1/events``                $0, keyless
Court                CourtListener - **cannot answer** (below)  $0
Investor day         **DROPPED** - no free source exists        n/a
===================  =========================================  ==============

**pdufa.bio** is free and keyless (1,000 requests/day anonymous) and is the only
one of the three with a real forward calendar. Its published semantics decide
this adapter's shape, and the important one is a 2026-09-09 breaking change:
``date`` is an **announced day or null**. When ``date_precision`` is ``month``,
``quarter`` or ``year`` the field is null and only ``date_month`` holds the
granularity, because the site used to publish a month midpoint as if a sponsor
had announced it. **Only ``date_precision == "day"`` rows are used here.** A
month midpoint turned into a day-count would be exactly the fabrication this
repository refuses, and it would land in a scored imminence.

That filter is expensive and worth stating: of the 456 live rows on 2026-09-18,
**120 carried an announced day** and 336 did not. The undated rows are not
discarded silently - :func:`calendar_coverage` counts them per family, so the
engine's coverage figure reflects the evidence that exists rather than the
subset that happens to be dated.

**CourtListener cannot answer the question this family asks.** It is a filing
archive, not a forward calendar: its docket and docket-entry endpoints require a
token, and the anonymously accessible ``/search/`` endpoint exposes exactly three
date fields - ``dateArgued``, ``dateFiled``, ``dateTerminated`` - all of which
are backward-looking. Probed live on 2026-09-18 across ``type=r`` result sets for
three queries (144,748 / 4,563 / 61,937,018 matches), **zero rows carried a
future date**. So :func:`court_calendar_rows` returns ``None``: the family stays
``missing`` rather than becoming ``not_applicable``, because "this source cannot
carry a forward date" is not the same claim as "no court event is scheduled", and
only the second one would be a false assertion.

**Investor day is dropped by decision, not by omission.** Wall Street Horizon via
Interactive Brokers ($49/mo) was the only priced source and the owner declined
it; EODHD's Corporate Events Calendar ($19.99/mo) does not carry investor days at
all - its own page scopes it to earnings, IPOs, splits, dividends and news. The
family therefore reports ``missing`` with that reason, and the design permits it:
the families are independent and coverage prints per family.

Attribution is required by pdufa.bio's free tier and is carried in
:data:`ATTRIBUTION`.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

#: pdufa.bio's free tier requires a visible link back. Kept here so every
#: rendered consumer can carry it rather than each inventing its own string.
ATTRIBUTION = "Catalyst data from pdufa.bio (https://www.pdufa.bio)"

PDUFA_BASE = "https://www.pdufa.bio/api/v1"
COURTLISTENER_SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"
_UA = "TradingAgentsResearch/1.0 (TradingAgents analysis; contact: vincent_liu@msn.com)"
_TIMEOUT = 25

#: The ``EventScore`` interfaces this module answers, and the two it does not.
#: ``product`` and ``clinical`` share one engine family (``INTERFACE_FAMILY`` in
#: ``strategies/event_state.py``), and the nearer of the two wins there.
CALENDAR_FAMILIES: tuple[str, ...] = ("product", "clinical", "court", "investor_day")

#: pdufa.bio event type -> the ``forward_calendar`` interface it answers. An FDA
#: decision is the product's route to market (``PDUFA``); a trial readout, an
#: advisory-committee meeting and a conference presentation are all clinical
#: readouts. Both land in the one ``product_clinical`` engine family.
PDUFA_INTERFACE: dict[str, str] = {
    "PDUFA": "product",
    "Readout": "clinical",
    "AdComm": "clinical",
    "Conference": "clinical",
}
#: An event that has already happened is not a forward catalyst. The statuses
#: below are the ones pdufa.bio uses for a decision still ahead of us; the
#: complement (Decided / Reported / Ended / Held) is excluded here as well as by
#: the day-count, because a "Decided" row is not a pending catalyst whatever its
#: date says.
PDUFA_FORWARD_STATUSES: frozenset[str] = frozenset(
    {"Upcoming", "Scheduled", "Guided", "Estimated", "Awaiting"}
)

#: Why the court family has no adapter answer. Carries the live finding and its
#: evidence, because a bare "no data" would read as an unbuilt seam.
COURT_REASON = (
    "CourtListener is a filing archive, not a forward calendar: its docket and "
    "docket-entry endpoints require a token, and the anonymously accessible "
    "/search/ endpoint exposes only dateArgued / dateFiled / dateTerminated, all "
    "backward-looking (probed live 2026-09-18: zero future-dated rows across "
    "three type=r result sets of 144,748 / 4,563 / 61,937,018 matches). The "
    "family stays MISSING rather than not_applicable: 'this source cannot carry "
    "a forward date' is not the claim 'no court event is scheduled'."
)

#: Why the investor-day family has no adapter answer. Dropped by owner decision
#: (2026-09-18) after the sourcing review - it is the only family with no free
#: source, and the one priced source was declined.
INVESTOR_DAY_REASON = (
    "DROPPED BY DECISION (owner, 2026-09-18): no free source exists. Wall Street "
    "Horizon via Interactive Brokers is the only priced option ($49/mo retail) "
    "and was declined; EODHD's Corporate Events Calendar ($19.99/mo) does not "
    "carry investor days at all - its own page scopes it to earnings, IPOs, "
    "splits, dividends and news. The family reports MISSING, never "
    "not_applicable, and the design permits it: the families are independent and "
    "coverage prints per family."
)


def _get_json(url: str, params: dict | None = None, *, timeout: int = _TIMEOUT):
    """GET a JSON document; raises on any transport or decode failure."""
    from urllib import parse as _urlparse

    if params:
        url = url + "?" + _urlparse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _day(rows, trade_date: str | None) -> list[dict]:
    """The rows carrying an ANNOUNCED day, as ``forward_calendar`` rows.

    Only ``date_precision == "day"`` survives: pdufa.bio nulls ``date`` for every
    other precision precisely so a month midpoint cannot be read as a day, and a
    day-count built on one would be invented. A row with no usable date is
    dropped here and counted by :func:`calendar_coverage`, never turned into a
    number.
    """
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("date_precision") or "") != "day":
            continue
        date = str(row.get("date") or "")[:10]
        if len(date) != 10:
            continue
        if str(row.get("status") or "") not in PDUFA_FORWARD_STATUSES:
            continue
        out.append({
            "date": date,
            "name": row.get("name"),
            "type": row.get("type"),
            "status": row.get("status"),
            "indication": row.get("indication"),
            "source": row.get("source"),
            "source_url": row.get("source_url"),
            "url": row.get("url"),
        })
    return out


def fda_calendar_rows(ticker: str, trade_date: str | None = None, *,
                      timeout: int = _TIMEOUT) -> list[dict] | None:
    """The forward FDA / clinical events for one name, from pdufa.bio.

    One request per name (``/api/v1/events?ticker=``), covering every event type
    the site tracks. Returns the **announced-day** rows only (see :func:`_day`),
    or ``None`` when the source could not be reached - which is deliberately
    distinct from ``[]``: an empty list means the calendar answered and holds no
    forward event (``not_applicable``), while ``None`` means the question was not
    answered (``missing``).

    Raises nothing: this is an optional depth on a run, and the caller records
    the reason rather than failing an analysis over a calendar.
    """
    code = str(ticker or "").strip().upper()
    if not code:
        return None
    try:
        payload = _get_json(
            f"{PDUFA_BASE}/events", {"ticker": code, "limit": 200}, timeout=timeout
        )
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.warning("pdufa.bio calendar fetch failed for %s: %s", code, exc)
        return None
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    return _day(rows, trade_date)


def court_calendar_rows(ticker: str, trade_date: str | None = None, **_) -> list[dict] | None:
    """The forward court events for one name - **no source can answer this**.

    Returns ``None`` always, which makes the family ``missing`` with
    :data:`COURT_REASON`. Returning ``[]`` would assert "this company has no
    scheduled court event", and nothing in the accessible data supports that
    claim; returning a row built from ``date_last_filing`` would assert a past
    filing is an upcoming event.
    """
    return None


def court_probe(ticker: str, *, timeout: int = _TIMEOUT) -> dict:
    """Re-run the live check behind :data:`COURT_REASON`, for verification.

    Queries the anonymously accessible search endpoint and reports how many of
    the returned dockets carry a date AFTER today. Kept as a callable (rather
    than only as prose) so the finding can be re-verified when the API changes
    instead of being trusted forever.
    """
    from datetime import date

    today = date.today().isoformat()
    try:
        payload = _get_json(COURTLISTENER_SEARCH,
                            {"q": ticker, "type": "r", "page_size": 20}, timeout=timeout)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}
    results = (payload or {}).get("results") or []
    fields = ("dateArgued", "dateFiled", "dateTerminated")
    future = [
        {f: r.get(f) for f in fields if r.get(f)}
        for r in results
        if any(str(r.get(f) or "") > today for f in fields)
    ]
    return {
        "reachable": True,
        "count": (payload or {}).get("count"),
        "rows": len(results),
        "date_fields": list(fields),
        "future_dated": future,
    }


def company_event_calendars(ticker: str, trade_date: str | None = None, *,
                            families: tuple[str, ...] | None = None,
                            timeout: int = _TIMEOUT) -> dict:
    """``{interface: rows | None}`` for the four declared calendar interfaces.

    ``rows is None`` means the question was not answered (``missing``); ``[]``
    means it was answered and holds nothing (``not_applicable``). The two are
    never collapsed - the distinction is the whole point of the interface, and
    collapsing it is how a missing calendar becomes "no event exists".
    """
    want = set(families or CALENDAR_FAMILIES)
    out: dict = dict.fromkeys(CALENDAR_FAMILIES)
    if "product" in want or "clinical" in want:
        rows = fda_calendar_rows(ticker, trade_date, timeout=timeout)
        if rows is not None:
            out["product"] = [r for r in rows if PDUFA_INTERFACE.get(str(r.get("type"))) == "product"]
            out["clinical"] = [r for r in rows if PDUFA_INTERFACE.get(str(r.get("type"))) == "clinical"]
    if "court" in want:
        out["court"] = court_calendar_rows(ticker, trade_date, timeout=timeout)
    if "investor_day" in want:
        out["investor_day"] = None
    return out


def calendar_coverage(ticker: str, trade_date: str | None = None, *,
                      timeout: int = _TIMEOUT) -> dict:
    """Per-family coverage: how many rows the source holds, how many are dated.

    The undated share is the honest denominator problem this source creates:
    pdufa.bio tracks 456 catalysts and only 120 carry an announced day, so a
    family that reports "0 events" without saying "of 3 rows, 3 undated" would
    read as an absence of catalysts rather than an absence of *dates*.
    """
    code = str(ticker or "").strip().upper()
    held = dated = 0
    total = None
    reachable = False
    if code:
        try:
            payload = _get_json(f"{PDUFA_BASE}/events",
                                {"ticker": code, "limit": 200}, timeout=timeout)
            rows = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(rows, list):
                reachable = True
                held = len(rows)
                dated = len(_day(rows, trade_date))
                total = (payload.get("meta") or {}).get("total")
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            logger.warning("pdufa.bio coverage fetch failed for %s: %s", code, exc)
    return {
        "source": "pdufa.bio",
        "reachable": reachable,
        "rows_held": held,
        "rows_with_announced_day": dated,
        "rows_undated": held - dated,
        "dataset_total": total,
        "families": {
            "product": "pdufa.bio /events (type=PDUFA)",
            "clinical": "pdufa.bio /events (type=Readout|AdComm|Conference)",
            "court": COURT_REASON,
            "investor_day": INVESTOR_DAY_REASON,
        },
        "attribution": ATTRIBUTION,
    }


__all__ = [
    "ATTRIBUTION",
    "CALENDAR_FAMILIES",
    "COURT_REASON",
    "INVESTOR_DAY_REASON",
    "PDUFA_FORWARD_STATUSES",
    "PDUFA_INTERFACE",
    "calendar_coverage",
    "company_event_calendars",
    "court_calendar_rows",
    "court_probe",
    "fda_calendar_rows",
]
