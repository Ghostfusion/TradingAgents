"""`EventScore` - occurrence and imminence, not exposure (WP-8).

Implements `docs/scores/EventScore.md` §5 (three layers: the imminence scalars,
the window flags and the hard block, the structured state) and
`docs/scores/IMPLEMENTATION_PLAN.md` §5.7. The engine's question is *"is a
high-impact event happening right now?"* - **occurrence and imminence** - as
distinct from `NewsScore` (information flow) and from `RiskScore`'s event leg
(the exposure an event creates; `EventScore.md` §0.2 splits the same producers by
question: this engine reads the day-counts and the window flags, `RiskScore` keeps
the implied move, the risk penalty and the size multiplier).

Five rules this module exists to hold:

1. **One imminence function, seven readers.** ``imminence(days_until, horizon)`` is
   ``clamp(1 - days_until / horizon, 0, 1)`` - monotone (a day further out never
   scores higher), bounded to ``[0, 1]``, and ``None`` for an absent day-count. It
   is the *same* function for the earnings, macro, Fed and OPEX producers
   (`catalyst.next_earnings.days_until`, `catalyst.macro_imminence.min_days`,
   `catalyst.fed_imminence.days_until`, `derivatives_gamma.opex_status.days_to_next`)
   and for the three families whose calendar does not exist yet.
2. **`NA` is not `0`** (master rule 1). A family with no calendar data carries
   ``None`` and a reason; it lowers the coverage, never the score. A family whose
   calendar is *missing* is not "a negative event" and is not "no event exists".
3. **The hard block is not this engine's.** The earnings blackout is set by
   `catalyst.build_catalyst_snapshot` (only on earnings, `catalyst.py:280-288`) and
   this module **passes it through verbatim, never computes one, never thresholds
   it, never vetoes with it**. No window constant of its own exists here.
4. **No weight vector is invented** (master rule 6). The owner gives this engine
   none (`EventScore.md` §0.1: every producer is a multiplier, a day-count or a
   boolean, so there is nothing to weight yet), so the combination runs
   equal-weight and **prints that fact**; the combination is unvalidated, so its
   status is ``RESEARCH_ONLY``.
5. **Nothing here sizes anything, gates anything, or reaches `SCORE_BANDS`.** The
   module never imports the sizing path, `risk_governor`, `GATE_PRECEDENCE` or
   `decision_guardrail`; its bands are its own and are event-intensity labels.
   The scale runs the **opposite way from the other engines** - 100 means an event
   is on top of us, not that the name is favourable - and the basis says so in
   words so the number cannot be read as a rating.

Out of scope by decision: `EventScore.md` §7 Q1/Q7 (the structured state is the
deliverable, not a validated 0-100 rating), §7 Q2 (macro/Fed/OPEX still never
hard-block), and §8 (intraday event-risk sizing vs latency - OPEN, needs a feed
decision and a latency contract; nothing intraday is implemented here).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .catalyst import parse_date
from .score_engine import align, band_label, combine, coverage_floor

# --- Horizons ---------------------------------------------------------------
#
# ``imminence`` needs one horizon per family. Each is the window the producer's
# own consumer already uses, never a fresh invention: the earnings lookahead is
# ``catalyst.next_earnings(lookahead_days=60)``, the macro window is
# ``catalyst_macro_window_days`` (3), the Fed window is
# ``catalyst_fed_window_days`` (10, what the snapshot passes), and OPEX is its
# own week (``opex_status.in_opex_week``). The three company-calendar families
# carry declared policy horizons: ``product_clinical`` has a producer as of
# 2026-09-18 (pdufa.bio) but its 90 days are still declared rather than measured,
# and ``court`` / ``investor_day`` have no source at all (see ABSENT_REASONS).

HORIZONS: dict[str, float] = {
    "earnings": 60.0,  # catalyst.next_earnings:90 lookahead_days=60
    "macro": 3.0,  # catalyst_macro_window_days default 3
    "fed": 10.0,  # catalyst_fed_window_days default 10
    "opex": 7.0,  # the OPEX week (opex_status:127 in_opex_week)
    # Declared policy: a regulatory decision is announced months ahead, and the
    # window is not measured from a producer's own consumer.
    "product_clinical": 90.0,
    "court": 90.0,
    "investor_day": 60.0,
}

# --- The family ledger ------------------------------------------------------
#
# Seven families, four of which have a producer (EventScore.md §1). Scope per
# §7 Q4: earnings and the three company calendars are NAME events, the macro
# complex and OPEX are MARKET events, and a market event never hard-blocks.

FAMILY_ORDER: tuple[str, ...] = (
    "earnings",
    "macro",
    "fed",
    "opex",
    "product_clinical",
    "court",
    "investor_day",
)

FAMILY_SCOPE: dict[str, str] = {
    "earnings": "NAME",
    "macro": "MARKET",
    "fed": "MARKET",
    "opex": "MARKET",
    "product_clinical": "NAME",
    "court": "NAME",
    "investor_day": "NAME",
}

SCORABLE = "SCORABLE"
ABSENT = "ABSENT"

FAMILY_AVAILABILITY: dict[str, str] = {
    "earnings": SCORABLE,
    "macro": SCORABLE,
    "fed": SCORABLE,
    "opex": SCORABLE,
    # SCORABLE as of 2026-09-18: pdufa.bio answers this family's two interfaces.
    # It is not always MEASURED - the source is optional and gated - which is
    # exactly what NA_REASONS below is for. Leaving it ABSENT would now be a
    # false claim: a producer exists.
    "product_clinical": SCORABLE,
    "court": ABSENT,
    "investor_day": ABSENT,
}

# The ABSENT reasons carry their evidence, and they are the *live* vendor
# findings, not the 2026-09-17 assumption. The P0-9 probe (2026-09-17) read
# moomoo's economic calendar over 14 days and got 50 rows, every one a MACRO
# release - zero FDA / clinical / trial / court / litigation / investor-day rows -
# which is what made the sourcing decision necessary. Two families are still
# unanswerable after it, and both say why with the source named.
ABSENT_REASONS: dict[str, str] = {
    "court": (
        "ABSENT after the 2026-09-18 sourcing decision: the chosen source cannot "
        "answer. CourtListener is a filing archive, not a forward calendar - its "
        "docket endpoints require a token and the anonymous search endpoint exposes "
        "only dateArgued / dateFiled / dateTerminated, all backward-looking (probed "
        "live: zero future-dated rows across three result sets of 144,748 / 4,563 / "
        "61,937,018 matches). The interface (forward_calendar) is bound and answers "
        "MISSING rather than not_applicable: 'this source cannot carry a forward "
        "date' is not the claim 'no court event is scheduled'."
    ),
    "investor_day": (
        "ABSENT by owner decision (2026-09-18): DROPPED, because no free source "
        "exists. Wall Street Horizon via Interactive Brokers is the only priced "
        "option ($49/mo retail) and was declined; EODHD's Corporate Events Calendar "
        "($19.99/mo) does not carry investor days at all - its own page scopes it to "
        "earnings, IPOs, splits, dividends and news. The nearest producers in the "
        "tree are get_corporate_actions (dividends / splits) and get_ipos "
        "(moomoo_extra_tools.py:178), neither a company-event calendar "
        "(EventScore.md section 4)."
    ),
}

# Why a *scorable* family can still be NA in one run - printed with the family so
# an absent value never reads as a measured zero.
NA_REASONS: dict[str, str] = {
    "earnings": (
        "NA: no print inside next_earnings' 60d lookahead (calendar absent or empty, "
        "or nothing scheduled inside the horizon)"
    ),
    "macro": (
        "NA: no HIGH-importance event inside the producer's own window "
        "(economic calendar absent or empty)"
    ),
    "fed": "NA: no FOMC meeting inside the producer's own window (fed_watch absent or empty)",
    "opex": "NA: opex_status returned no forward expiry (never 0 days)",
    "product_clinical": (
        "NA: no FDA / clinical event with an ANNOUNCED day inside the horizon. The "
        "source is optional and gated (enable_event_calendars), and pdufa.bio nulls "
        "`date` for every row whose precision is not 'day' - 336 of its 456 live "
        "rows - so a tracked catalyst with only a month estimate is NOT a forward "
        "event here, and is counted by the coverage line instead"
    ),
    "court": (
        "NA: the court family is ABSENT (see ABSENT_REASONS) - no source can carry a "
        "forward litigation date"
    ),
    "investor_day": (
        "NA: the investor-day family is ABSENT by decision (see ABSENT_REASONS) - no "
        "free source exists"
    ),
}

# --- The component table ----------------------------------------------------
#
# One imminence slot per family (the layer-1 scalar) plus the producer's own
# window flags, printed as evidence and never scored (layer 2). Every key is
# family-prefixed, so the set cannot collide with `RiskScore`'s event leg, whose
# keys are the EXPOSURE measures (EventScore.md §0.2).

IMMINENCE = "imminence"
FLAG = "flag"


class Component(NamedTuple):
    """One component: its family, whether it scores, its producer."""

    name: str
    family: str
    kind: str
    producer: str
    note: str = ""


def _c(name, family, kind, producer, note=""):
    return Component(name, family, kind, producer, note)


COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        _c(
            "earnings_imminence",
            "earnings",
            IMMINENCE,
            "catalyst.next_earnings:90 (days_until)",
        ),
        _c(
            "earnings_in_window",
            "earnings",
            FLAG,
            "catalyst.build_catalyst_snapshot:265 (the producer's own verdict)",
        ),
        _c(
            "macro_imminence",
            "macro",
            IMMINENCE,
            "catalyst.macro_imminence:123 (min_days)",
        ),
        _c(
            "macro_count_high",
            "macro",
            FLAG,
            "catalyst.macro_imminence:123 (count_high)",
        ),
        _c(
            "catalyst_unassessed",
            "macro",
            FLAG,
            "catalyst.build_catalyst_snapshot:344 (verdict catalyst-unassessed)",
            "the producer's honest-degradation flag: no forward macro feed was available, "
            "so the window was never assessed - not a confirmed clean one",
        ),
        _c(
            "fed_imminence",
            "fed",
            IMMINENCE,
            "catalyst.fed_imminence:142 (days_until)",
        ),
        _c(
            "fed_modal_prob",
            "fed",
            FLAG,
            "catalyst.fed_imminence:142 (modal_prob, percent)",
        ),
        _c(
            "opex_imminence",
            "opex",
            IMMINENCE,
            "derivatives_gamma.opex_status:127 (days_to_next)",
        ),
        _c(
            "opex_in_week",
            "opex",
            FLAG,
            "derivatives_gamma.opex_status:127 (in_opex_week)",
        ),
        _c(
            "opex_post_unwind",
            "opex",
            FLAG,
            "derivatives_gamma.opex_status:127 (post_opex_unwind)",
        ),
        _c(
            "product_clinical_imminence",
            "product_clinical",
            IMMINENCE,
            "forward_calendar('product' | 'clinical') <- event_calendars.fda_calendar_rows "
            "(pdufa.bio /api/v1/events, keyless)",
            "announced-day rows only (date_precision == 'day'): pdufa.bio nulls `date` "
            "for every month/quarter/year estimate, and a day-count built on a month "
            "midpoint would be an invented number",
        ),
        _c(
            "court_imminence",
            "court",
            IMMINENCE,
            "forward_calendar('court') <- event_calendars.court_calendar_rows (returns None)",
            "NO SOURCE: CourtListener is a filing archive - its only date fields are "
            "backward-looking (event_calendars.COURT_REASON)",
        ),
        _c(
            "investor_day_imminence",
            "investor_day",
            IMMINENCE,
            "forward_calendar('investor_day') <- no adapter (dropped by decision)",
            "DROPPED 2026-09-18: no free source exists "
            "(event_calendars.INVESTOR_DAY_REASON)",
        ),
    )
}

FAMILY_COMPONENTS: dict[str, tuple[str, ...]] = {
    fam: tuple(c.name for c in COMPONENTS.values() if c.family == fam) for fam in FAMILY_ORDER
}

#: The imminence slots (what scores) and the flags (what is printed).
IMMINENCE_COMPONENTS: tuple[str, ...] = tuple(
    c.name for c in COMPONENTS.values() if c.kind == IMMINENCE
)
FLAG_COMPONENTS: tuple[str, ...] = tuple(
    c.name for c in COMPONENTS.values() if c.kind == FLAG
)

#: The reserved passthrough key: a `build_catalyst_snapshot` output's own
#: ``hard_block`` travels here so the state can print it. It is NOT a scored
#: component and this module never constructs, thresholds or vetoes with it.
HARD_BLOCK_KEY = "hard_block"

# --- Output vocabulary ------------------------------------------------------

STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"

# This engine's own advisory labels, on the event-intensity axis (not a rating
# axis, and never `decision_guardrail.SCORE_BANDS`).
EVENT_BANDS: tuple = (
    (80.0, "event-window"),
    (60.0, "imminent"),
    (40.0, "approaching"),
    (20.0, "quiet"),
    (0.0, "clear"),
)

#: A count floor, capped at the family set's own size (the WP-2 FGS lesson). Two
#: of the seven families is the least that says anything; a family smaller than
#: the floor is withheld with the reason, never scored on what it lacks.
EVENT_MIN_COVERAGE = 2

CALENDAR_STATUSES: tuple[str, ...] = ("available", "missing", "not_applicable")

CALENDAR_INTERFACES: tuple[str, ...] = ("product", "clinical", "court", "investor_day")

#: The four interfaces of EventScore.md §7 Q5 map onto the three ABSENT families:
#: product launches and clinical/FDA decisions are one family's two calendars.
INTERFACE_FAMILY: dict[str, str] = {
    "product": "product_clinical",
    "clinical": "product_clinical",
    "court": "court",
    "investor_day": "investor_day",
}


def imminence(days_until, horizon) -> float | None:
    """``clamp(1 - days_until / horizon, 0, 1)`` - the engine's one occurrence scalar.

    Monotone (a day further out never scores higher), bounded to ``[0, 1]``:
    0 days -> 1.0, ``horizon`` days or more -> 0.0, and a negative day-count (an
    event that already passed) clamps to 1.0 rather than leaving the range.

    ``None`` in -> ``None`` out, and an unusable input (no day-count, a boolean,
    a non-finite number, a horizon that is not positive) is ``None`` too:
    **never 0**, which would claim the event is measured and far away.
    """
    if days_until is None or isinstance(days_until, bool):
        return None
    try:
        days = float(days_until)
        h = float(horizon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(days) and math.isfinite(h)) or h <= 0.0:
        return None
    return max(0.0, min(1.0, 1.0 - days / h))


def forward_calendar(family: str, rows: list | None = None, *,
                     trade_date: str | None = None, reason: str | None = None) -> dict:
    """The forward-company-calendar interface (EventScore.md §7 Q5).

    One interface per calendar - ``product``, ``clinical``, ``court``,
    ``investor_day`` - answering ``available`` | ``missing`` | ``not_applicable``,
    and **never a number when it has no data**: a missing calendar is not "no
    event exists" and certainly not "a negative event".

    - ``rows is None`` -> ``missing``: the question was not answered. ``reason``
      overrides the family's static ABSENT_REASONS text so a bound adapter can
      carry its OWN finding (CourtListener's "this source cannot carry a forward
      date" is not the same claim as "no adapter was ever written").
    - the adapter answered and carries a forward event -> ``available`` with the
      next ``{date, days_until}``.
    - the adapter answered and carries none -> ``not_applicable``.

    The three answers are never collapsed. ``dataflows.event_calendars`` binds
    ``product``/``clinical`` to pdufa.bio and leaves ``court`` at ``None``, and
    ``event_components`` consumes the ``available`` answer.
    """
    if family not in CALENDAR_INTERFACES:
        raise KeyError(
            f"unknown calendar interface {family!r}; known: {list(CALENDAR_INTERFACES)}"
        )
    fam = INTERFACE_FAMILY[family]
    if rows is None:
        # A family with no producer carries its ABSENT evidence; one that HAS a
        # producer but was not asked (the calendar gate is off, or the source did
        # not answer) carries the NA reason instead. Reaching for ABSENT_REASONS
        # alone would raise for a scorable family - which is a real state now
        # that pdufa.bio answers product/clinical.
        return {
            "family": family,
            "scope": FAMILY_SCOPE[fam],
            "status": "missing",
            "next": None,
            "events": 0,
            "reason": reason or ABSENT_REASONS.get(fam) or NA_REASONS.get(fam),
        }
    td = parse_date(trade_date) if trade_date else None
    best: dict | None = None
    events = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        d = parse_date(row.get("date") or row.get("timestamp"))
        if d is None:
            continue
        days = (d - td).days if td is not None else None
        if days is not None and days < 0:
            continue
        events += 1
        if best is None or (days is not None and days < best.get("days_until", 10**6)):
            best = {"date": d.strftime("%Y-%m-%d"), "days_until": days}
    if best is None:
        return {
            "family": family,
            "scope": FAMILY_SCOPE[fam],
            "status": "not_applicable",
            "next": None,
            "events": 0,
            "reason": (
                f"the {family} calendar answered and carries no forward event for this "
                "name: not_applicable, which is not 'a negative event'"
            ),
        }
    return {
        "family": family,
        "scope": FAMILY_SCOPE[fam],
        "status": "available",
        "next": best,
        "events": events,
        "reason": None,
    }


def calendar_answers(rows_by_interface: dict, *, trade_date: str | None = None,
                     reasons: dict | None = None) -> dict:
    """``forward_calendar`` answers per interface, from an adapter's rows.

    One place turns "what the source returned" into the three-status answer, so
    the leaf and the run card cannot drift: a caller that re-implemented this
    could collapse ``None`` (the question was not answered) into ``[]`` (it was
    answered and holds nothing), and that single mistake turns a source that
    cannot carry a forward date into a false claim that no event is scheduled.

    ``reasons`` overrides the static ABSENT_REASONS text per interface, which is
    how a bound adapter carries its own live finding.
    """
    out: dict = {}
    for interface in CALENDAR_INTERFACES:
        if interface not in (rows_by_interface or {}):
            continue
        out[interface] = forward_calendar(
            interface,
            rows_by_interface.get(interface),
            trade_date=trade_date,
            reason=(reasons or {}).get(interface),
        )
    return out


def event_components(
    snapshot: dict | None,
    *,
    opex: dict | None = None,
    calendars: dict | None = None,
) -> dict:
    """The occurrence half of a `catalyst.build_catalyst_snapshot` output.

    Pure assembly: every value is read from a producer that already ran - the
    snapshot's ``earnings`` / ``macro`` / ``fed`` blocks, a
    `derivatives_gamma.opex_status` result, and (once an adapter exists) a
    `forward_calendar` answer per company-event interface. No fetch, no formula,
    no vendor call.

    A block the producer could not measure is **left out** rather than sent as 0,
    so it leaves the family's denominator. The snapshot's ``hard_block`` is copied
    verbatim under :data:`HARD_BLOCK_KEY` when the snapshot carries the key: this
    function never creates one, and no macro / Fed / OPEX input can.
    """
    snap = dict(snapshot or {})
    out: dict = {}

    earnings = snap.get("earnings") or {}
    if earnings.get("days_until") is not None:
        out["earnings_imminence"] = earnings["days_until"]
    verdict = snap.get("verdict")
    if verdict is not None:
        out["earnings_in_window"] = verdict in ("earnings-window", "earnings-hard-block")
        out["catalyst_unassessed"] = verdict == "catalyst-unassessed"

    macro = snap.get("macro") or {}
    if macro.get("min_days") is not None:
        out["macro_imminence"] = macro["min_days"]
    if "count_high" in macro:
        out["macro_count_high"] = macro["count_high"]

    fed = snap.get("fed") or {}
    if fed.get("days_until") is not None:
        out["fed_imminence"] = fed["days_until"]
    if fed.get("modal_prob") is not None:
        out["fed_modal_prob"] = fed["modal_prob"]

    if opex and opex.get("next_opex") is not None:
        if opex.get("days_to_next") is not None:
            out["opex_imminence"] = opex["days_to_next"]
        if opex.get("in_opex_week") is not None:
            out["opex_in_week"] = opex["in_opex_week"]
        if opex.get("post_opex_unwind") is not None:
            out["opex_post_unwind"] = opex["post_opex_unwind"]

    # The company-event calendars: an `available` answer fills the family's
    # imminence slot; `missing` / `not_applicable` leave it NA, never 0. Two
    # interfaces share the product/clinical family and the nearer event wins.
    for interface, answer in (calendars or {}).items():
        fam = INTERFACE_FAMILY.get(interface)
        if fam is None or not isinstance(answer, dict) or answer.get("status") != "available":
            continue
        days = (answer.get("next") or {}).get("days_until")
        if days is None or isinstance(days, bool):
            continue
        key = f"{fam}_imminence"
        if key not in out or float(days) < float(out[key]):
            out[key] = days

    if HARD_BLOCK_KEY in snap:
        out[HARD_BLOCK_KEY] = snap[HARD_BLOCK_KEY]
    return out


def _family_floor(min_coverage=None) -> int:
    """The resolved count floor, capped at the family set's own size."""
    floor = coverage_floor(
        EVENT_MIN_COVERAGE if min_coverage is None else min_coverage, len(FAMILY_ORDER)
    )
    return min(floor, len(FAMILY_ORDER))


def _family_state(family: str, values: dict) -> dict:
    """One family's imminence, its score, its flags and its reason."""
    names = FAMILY_COMPONENTS[family]
    imminence_names = [n for n in names if COMPONENTS[n].kind == IMMINENCE]
    measured = {
        n: values[n]
        for n in imminence_names
        if n in values and values[n] is not None and not isinstance(values[n], bool)
    }
    # The NEAREST event is the family's occurrence (min day-count -> max
    # imminence); a farther second calendar must not dilute a nearer one.
    raw = min(measured.values(), key=lambda v: float(v)) if measured else None
    imm = imminence(raw, HORIZONS[family]) if measured else None
    aligned = align(imm, direction="higher_better", lo=0.0, hi=1.0) if imm is not None else None
    availability = FAMILY_AVAILABILITY[family]
    if imm is not None:
        reason = None
    elif availability == ABSENT:
        reason = ABSENT_REASONS[family]
    else:
        reason = NA_REASONS[family]
    return {
        "family": family,
        "scope": FAMILY_SCOPE[family],
        "availability": availability,
        "imminence": imm,
        "score": aligned,
        "horizon_days": HORIZONS[family],
        "components": {name: values.get(name) for name in names},
        "producer": COMPONENTS[imminence_names[0]].producer if imminence_names else None,
        "reason": reason,
    }


def event_state(components: dict, *, weights: dict | None = None) -> dict:
    """The structured event state, with its families, its coverage and its basis.

    ``components`` is the flat ``{component: raw value}`` dict over the keys
    declared in :data:`COMPONENTS` - the day-counts, the window flags and, under
    :data:`HARD_BLOCK_KEY`, the snapshot's own hard block. Anything absent is
    ``NA`` and is reported with its reason, never scored as 0 and never as a
    neutral.

    ``weights`` overrides the family weights; ``None`` runs **equal weights over
    the seven families and prints that no vector is published**
    (`EventScore.md` §0.1). The score is the weight renormalised over the
    families that produced an imminence, so an absent family lowers ``coverage``
    instead of the score, and below the floor the score is **withheld with its
    reason**.

    The scale runs the **opposite way from the other engines**: 100 = an event is
    on top of us. The basis states that in words, and the status is
    ``RESEARCH_ONLY`` because no weight vector here has been measured.

    Returns ``{"score", "band", "coverage", "families", "components", "imminence",
    "hard_block", "weights", "status", "withheld", "basis", ...}``.
    """
    values = dict(components or {})
    hard_block = values.pop(HARD_BLOCK_KEY, None)

    families = {fam: _family_state(fam, values) for fam in FAMILY_ORDER}
    scored = {fam: families[fam]["score"] for fam in FAMILY_ORDER}

    if weights is None:
        w: dict | None = None
        weight_basis = (
            "no weight vector is published for this engine (EventScore.md section 0.1) - "
            "equal weights, 1.0 per family, printed rather than invented"
        )
    else:
        w = {fam: float(weights.get(fam, 0.0) or 0.0) for fam in FAMILY_ORDER}
        weight_basis = "weights: " + ", ".join(f"{k}={v:g}" for k, v in sorted(w.items()))

    floor = _family_floor()
    combined = combine(scored, weights=w, min_coverage=floor, bands=EVENT_BANDS)

    present = [fam for fam in FAMILY_ORDER if families[fam]["imminence"] is not None]
    unmeasured = [fam for fam in FAMILY_ORDER if fam not in present]
    basis = (
        f"EventScore: {len(present)} of {len(FAMILY_ORDER)} families carried a measurable "
        f"imminence ({', '.join(present) if present else 'none'}) -> "
        f"{weight_basis}; "
        f"imminence = clamp(1 - days_until / horizon, 0, 1) over horizons "
        f"{dict(sorted(HORIZONS.items()))}; "
        f"SCALE IS INVERTED RELATIVE TO THE OTHER ENGINES - 100 means an event is on top "
        f"of us, not that the name is favourable; "
        f"flags are printed as evidence and never scored; "
        f"the hard block is passed through verbatim from the snapshot and is never "
        f"computed, thresholded or vetoed here; "
        f"families without data: {', '.join(unmeasured) if unmeasured else 'none'}; "
        f"family coverage {len(present)}/{len(FAMILY_ORDER)}; "
        f"advisory only - never a gate, never a size"
    )
    return {
        "score": combined.get("score"),
        "band": band_label(combined.get("score"), EVENT_BANDS),
        "coverage": combined.get("coverage"),
        "floor": combined.get("floor"),
        "families": families,
        "families_present": present,
        "families_unmeasured": unmeasured,
        "components": {
            name: {
                "raw": values.get(name),
                "family": COMPONENTS[name].family,
                "kind": COMPONENTS[name].kind,
                "producer": COMPONENTS[name].producer,
                "scored": COMPONENTS[name].kind == IMMINENCE,
                "note": COMPONENTS[name].note,
            }
            for name in COMPONENTS
        },
        "imminence": {fam: families[fam]["imminence"] for fam in FAMILY_ORDER},
        "hard_block": hard_block,
        "weights": w,
        "status": STATUS_RESEARCH_ONLY,
        "withheld": combined.get("withheld"),
        "basis": basis,
    }


__all__ = [
    "HORIZONS",
    "FAMILY_ORDER",
    "FAMILY_SCOPE",
    "FAMILY_AVAILABILITY",
    "FAMILY_COMPONENTS",
    "ABSENT_REASONS",
    "NA_REASONS",
    "COMPONENTS",
    "Component",
    "IMMINENCE_COMPONENTS",
    "FLAG_COMPONENTS",
    "HARD_BLOCK_KEY",
    "EVENT_BANDS",
    "EVENT_MIN_COVERAGE",
    "STATUS_RESEARCH_ONLY",
    "SCORABLE",
    "ABSENT",
    "CALENDAR_STATUSES",
    "CALENDAR_INTERFACES",
    "INTERFACE_FAMILY",
    "imminence",
    "forward_calendar",
    "calendar_answers",
    "event_components",
    "event_state",
]
