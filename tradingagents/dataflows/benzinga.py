"""Benzinga vendor: ticker news, calendars, and the SEC/congress alt-data surface.

Benzinga returns ticker-scoped **financial** news with a headline, a link, the
author, the date and the tagged tickers. It is the rare free feed that is both
ticker-filtered and financial-first, so it slots in BEFORE the generic keyword
feeds in the ``news_data`` chain.

Three transport facts were measured against the live key on 2026-09-20 and each
one broke something, so each is handled explicitly:

1. **The response encoding is negotiated by header, not by parameter.**
   Benzinga's default is XML; ``Accept: application/json`` is the only switch,
   and the ``format=json`` query parameter is silently ignored. Without the
   header every call fails as ``non-JSON response``.
2. **The version segment is per-route, not global.** News is ``/api/v2``, the
   calendars are ``/api/v2.1``, the alt-data surface is ``/api/v1``. A ``BASE``
   that hardcoded ``/api/v2`` made the other two unreachable.
3. **The envelope is not consistent.** ``/v2/news`` is a bare list; every
   calendar is a dict keyed by its own family (``{"ratings": [...]}``); the
   alt-data surface is ``{"data": [...]}``; ``/v2.1/fundamentals`` is
   ``{"result": [...]}``; ``/v1/logos`` is ``{"logos": [...]}``. Collapsing any
   dict to ``None`` reports a 200 that carries rows as "no data".

Not every parameter does something. Verified live:

    /v2/news-removed   pageSize YES, page YES, every date parameter IGNORED
    /v2.1/calendar/*   parameters[tickers] YES, parameters[date_from/to] YES
    /v2/bars           interval REQUIRED (without it the body is a stub)
    /v2.1/fundamentals symbols= (NOT tickers=)

Key: ``BENZINGA_API_KEY`` in ``.env``. Raises the typed errors the router
understands so a 401/403/429/empty degrades to the next vendor - never a
fabricated value.

Measured on the live key 2026-09-20: the ``/v2/news`` payload carries ``title``,
``url``, ``created``, ``author``, ``stocks``, ``channels``, ``importance_rank``
and ``image``, while **``teaser`` and ``body`` come back as empty strings** - so
the render is headline + link, and it says so rather than implying a teaser.
"""

from __future__ import annotations

import contextlib
import html
import logging
import os
import time
from datetime import datetime, timedelta

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

#: Benzinga's API **root**. The version segment belongs to the caller's path:
#: news is ``v2/news``, the calendars are ``v2.1/calendar/...``, the alt-data
#: surface is ``v1/...``. This module used to hardcode ``/api/v2`` here, so
#: ``v2.1/calendar/ratings`` was requested as ``/api/v2/v2.1/calendar/ratings``
#: and every calendar came back as the gateway's own
#: ``no Route matched with those values`` 404 - the vendor could only ever
#: reach the ``/v2`` routes.
BASE = "https://api.benzinga.com/api"
TIMEOUT = 20
_MAX_RETRIES = 2
_ARTICLE_LIMIT = 10
_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 8.0

#: Benzinga's default response encoding is **XML**. Measured live 2026-09-20
#: against ``api.benzinga.com``:
#:
#:     no header                 -> 200  Content-Type: application/xml
#:     Accept: application/json  -> 200  Content-Type: application/json
#:     format=json               -> 200  Content-Type: application/xml  (IGNORED)
#:
#: ``format=json`` is a query parameter the vendor **silently ignores** - the
#: same "a parameter that does nothing is worse than a named gap" trap as
#: EODHD's ignored ``year``. The header is the only switch, so it is sent on
#: every request: without it ``resp.json()`` raises on an XML body, which the
#: status classifier below types as ``NoMarketDataError("non-JSON response")``
#: and the whole vendor degrades on every call.
_HEADERS = {"Accept": "application/json"}


def _backoff_seconds(attempt: int) -> float:
    """Bounded exponential backoff for retry ``attempt`` (0-based)."""
    return min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)


def _error_detail(resp) -> str:
    """Human detail for a failed response; the body is used as text only."""
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        msg = data.get("error") or data.get("message")
        if msg:
            return str(msg)[:200]
    text = str(getattr(resp, "text", "") or "").strip().replace("\n", " ")
    return text[:200] if text else f"HTTP {resp.status_code}"


def _unescape(value) -> str:
    """Decode HTML entities a vendor ships in its own text.

    Benzinga escapes ampersands in headlines, so the raw field reads
    ``Technology Hardware, Storage &amp; Peripherals``. The render is markdown
    read by a human and by the analyst, so the entity is decoded rather than
    passed through as literal text.
    """
    return html.unescape(str(value or "")).replace("\n", " ").strip()


def _envelope_error(data) -> str | None:
    """The vendor's own error text when a 200 body reports a failure.

    Two shapes: ``{"error": "..."}`` on the news routes, and
    ``{"ok": "true", "errors": [...]}`` on ``/v3/fundamentals``. The second one
    matters because ``errors`` is itself a list, so an unwrapper that simply
    takes the first list-valued member would hand the caller the error strings
    as if they were rows.
    """
    if not isinstance(data, dict):
        return None
    if data.get("error"):
        return str(data["error"])
    if "ok" in data and data.get("errors"):
        errors = data["errors"]
        if isinstance(errors, list):
            return "; ".join(str(e) for e in errors)
        return str(errors)
    return None


def _unwrap_records(data) -> list | None:
    """The row list from a Benzinga 200 body, whatever envelope it uses.

    Benzinga is not consistent: ``/v2/news`` answers with a bare list, every
    calendar answers with a dict keyed by its own family
    (``{"ratings": [...]}``, ``{"guidance": [...]}``), the alt-data surface
    answers ``{"data": [...]}``, ``/v2.1/fundamentals`` answers
    ``{"result": [...]}`` and ``/v1/logos`` answers ``{"logos": [...]}``.

    Returning ``None`` for every dict - which this did - meant each of those
    routes reported "no data" on a 200 that carried rows; only the bare-list
    news route ever worked. The rows are the sole list-valued member of the
    envelope, taken in insertion order.
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return None
    for value in data.values():
        if isinstance(value, list):
            return value
    return None


def benzinga_api_key() -> str | None:
    """Benzinga key from config or environment; None when unset."""
    try:
        from .config import get_config

        cfg = get_config()
        val = cfg.get("benzinga_api_key")
        if val:
            return str(val)
    except Exception:  # noqa: BLE001 - config is best-effort
        pass
    return os.environ.get("BENZINGA_API_KEY")


def _benzinga_get(path: str, params: dict | None = None) -> list | None:
    """Authenticated GET ``{BASE}/{path}`` with token; parsed rows or None.

    ``path`` is the **versioned** route (``v2/news``, ``v2.1/calendar/ratings``,
    ``v1/logos``); the version segment is not supplied by ``BASE``.

    The HTTP status is classified *before* the body is parsed: parsing first
    turned an HTML 429/5xx page (proxy/Cloudflare) into a permanent
    ``NoMarketDataError``, i.e. a rate limit typed as "no data". Only
    transient statuses (429/5xx) and network errors are retried, with bounded
    exponential backoff.
    """
    key = benzinga_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "Benzinga key is not set. Add BENZINGA_API_KEY to .env."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["token"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT, headers=_HEADERS)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(f"Benzinga network error: {exc}") from exc

        status = resp.status_code
        if status in (401, 403):
            raise VendorNotConfiguredError(
                f"Benzinga auth/forbidden (check BENZINGA_API_KEY): {status}"
            )
        if status == 429 or status >= 500:
            if attempt < _MAX_RETRIES:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(
                f"Benzinga {path}: status {status} - {_error_detail(resp)}"
            )
        if status != 200:
            # Non-retryable client error (400/404/...): permanent no-data.
            raise NoMarketDataError(
                "benzinga", path, detail=f"HTTP {status}: {_error_detail(resp)}"
            )
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("benzinga", path, detail="non-JSON response") from None
        detail = _envelope_error(data)
        if detail:
            raise NoMarketDataError("benzinga", path, detail=detail)
        return _unwrap_records(data)
    return None


# --------------------------------------------------------------------------- #
# render helpers
# --------------------------------------------------------------------------- #

def _require_dates(start_date: str, end_date: str) -> None:
    """Validate the ISO dates a calendar window is expressed in."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")


def _calendar_params(ticker: str, start_date: str, end_date: str) -> dict:
    """The bracketed parameter shape every ``/v2.1/calendar`` route uses."""
    return {
        "parameters[tickers]": ticker,
        "parameters[date_from]": start_date,
        "parameters[date_to]": end_date,
    }


def _scaled(value) -> str:
    """A money magnitude rendered compactly, or ``-`` when the field is blank.

    Benzinga ships guidance and offering magnitudes as strings of raw units
    (``"114332669224.000"``). Rendering the raw integer is unreadable in a
    report; rendering a scaled form is a presentation choice, so it is applied
    here rather than in the strategy layer. Blank stays blank - an absent
    guidance figure is a named gap, never a zero.
    """
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        num = float(text)
    except (TypeError, ValueError):
        return text[:40]
    sign = "-" if num < 0 else ""
    mag = abs(num)
    if mag >= 1e9:
        return f"{sign}{mag / 1e9:.2f}B"
    if mag >= 1e6:
        return f"{sign}{mag / 1e6:.2f}M"
    if mag >= 1e3:
        return f"{sign}{mag / 1e3:.2f}K"
    return f"{sign}{mag:.4f}".rstrip("0").rstrip(".")


def _plain(value) -> str:
    """A scalar rendered as text, ``-`` when blank."""
    text = _unescape(value)
    return text or "-"


def _num(value, width: int = 8) -> str:
    """A float-ish field rendered as text, ``-`` when blank."""
    text = str(value or "").strip()
    if not text:
        return "-"
    return text[:width]


def _price(value) -> str:
    """A price/target normalised to two decimals, ``-`` when blank.

    Benzinga is inconsistent about trailing zeros within one row
    (``pt_prior="365.00"`` beside ``pt_current="380.0000"``), so an unchanged
    target would otherwise render as a visible ``365.00 -> 380.0000``. The
    value is parsed and re-formatted; a field that does not parse is passed
    through rather than silently dropped.
    """
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        return f"{float(text):.2f}"
    except (TypeError, ValueError):
        return text[:20]


def _range(lo, hi, mid, unit: str = "") -> str:
    """``min-max (mid ...)`` with each part independently allowed to be blank."""
    lo_s, hi_s, mid_s = _scaled(lo), _scaled(hi), _scaled(mid)
    if lo_s == "-" and hi_s == "-" and mid_s == "-":
        return "-"
    span = f"{lo_s} to {hi_s}" if (lo_s != "-" or hi_s != "-") else "-"
    if mid_s != "-":
        span = f"{span} (mid {mid_s})" if span != "-" else f"mid {mid_s}"
    return f"{span}{unit}"


def _truncate(text, limit: int = 300) -> str:
    """Bound a free-text field so one row cannot dominate the render."""
    body = _unescape(text)
    if len(body) <= limit:
        return body
    return body[: limit - 1].rstrip() + "\u2026"


def _header(title: str, ticker: str, start_date: str, end_date: str) -> list[str]:
    """The two-line preamble every windowed reader shares."""
    return [f"## {ticker} {title} \u2014 Benzinga", f"_window {start_date} .. {end_date}_", ""]


def _no_rows(ticker: str, what: str, start_date: str, end_date: str) -> NoMarketDataError:
    """A typed empty-window error so the router degrades to the next vendor."""
    return NoMarketDataError(
        ticker, what, detail=f"no records between {start_date} and {end_date}"
    )


# --------------------------------------------------------------------------- #
# news (the chain member)
# --------------------------------------------------------------------------- #

def get_news_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """Ticker-scoped financial news via ``/v2/news``.

    Renders headline, timestamp, source and the link. ``teaser``/``body`` are
    empty strings on this tier, so the render does not imply one.
    """
    _require_dates(start_date, end_date)
    items = _benzinga_get(
        "v2/news",
        {
            "tickers": ticker,
            "dateFrom": start_date,
            "dateTo": end_date,
            "pageSize": _ARTICLE_LIMIT,
        },
    )
    if not items:
        raise _no_rows(ticker, "news", start_date, end_date)
    lines = [f"## {ticker} News \u2014 Benzinga", ""]
    shown = 0
    for item in items:
        if shown >= _ARTICLE_LIMIT:
            break
        shown += 1
        if not isinstance(item, dict):
            continue
        # Titles arrive HTML-escaped ("Technology Hardware, Storage &amp;
        # Peripherals"). The render is markdown read by a human and by the
        # analyst, so the entity must be decoded or the reader sees `&amp;`.
        title = _unescape(item.get("title"))[:120] or "(no title)"
        date = str(item.get("created") or item.get("updated") or "")[:16]
        source = str(item.get("author") or item.get("source") or "").strip()
        # Headline + link on this tier; `teaser`/`body` come back as empty
        # strings, so the render emits nothing rather than a blank line.
        teaser = _unescape(item.get("teaser") or item.get("body"))
        link = str(item.get("url") or item.get("link") or "")
        lines.append(f"- **{title}**  ({date} {source})")
        if teaser:
            lines.append(f"  {teaser[:200]}")
        if link and link != "None":
            lines.append(f"  url: {link}")
    return "\n".join(lines)


def get_news_removed_benzinga(limit: int = 100, page: int = 1) -> str:
    """Retracted news IDs via ``/v2/news-removed``.

    The only feed in this repo that can **invalidate** evidence already
    collected: an id here names an article Benzinga has withdrawn.

    **The date parameters do nothing.** Measured live 2026-09-20: ``{}``,
    ``parameters[date_from]``/``parameters[date_to]``, ``dateFrom``/``dateTo``
    and a one-day window all return the identical first row. ``pageSize`` and
    ``page`` DO work (verified: ``pageSize=5`` returns 5, ``page=2`` returns a
    different set). So this reader takes a limit and a page - not a date window
    - and never claims to filter by one. The endpoint is not ticker-scoped.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if page <= 0:
        raise ValueError("page must be positive")
    items = _benzinga_get("v2/news-removed", {"pageSize": limit, "page": page})
    if not items:
        raise NoMarketDataError("benzinga", "news-removed", detail="no retractions returned")
    lines = [
        "## Retracted Benzinga Articles",
        f"_most recent {limit} retraction ids, page {page} "
        "(the endpoint accepts no date window)_",
        "",
    ]
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- id {_plain(item.get('id'))}  retracted {_plain(item.get('updated'))}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# calendars (new capabilities)
# --------------------------------------------------------------------------- #

def get_guidance_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """Corporate guidance revisions via ``/v2.1/calendar/guidance``.

    The forward-looking companion to the reported statements: management's own
    revenue/EPS range for a named future period, plus the prior range when the
    vendor carries one. This is the only forward *growth* producer in the data
    layer, which is why it exists - ``rev_cagr5`` in the fundamental engine is
    a trailing measure and comes back ``NA`` when the statement history is
    short.
    """
    _require_dates(start_date, end_date)
    items = _benzinga_get(
        "v2.1/calendar/guidance", _calendar_params(ticker, start_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "guidance", start_date, end_date)
    lines = _header("Guidance Revisions", ticker, start_date, end_date)
    for item in items:
        if not isinstance(item, dict):
            continue
        date = _plain(item.get("date"))
        period = _plain(item.get("period"))
        year = _plain(item.get("period_year"))
        flags = []
        if str(item.get("is_primary") or "").upper() == "Y":
            flags.append("primary")
        if str(item.get("prelim") or "").upper() == "Y":
            flags.append("preliminary")
        importance = item.get("importance")
        if importance not in (None, ""):
            flags.append(f"importance {importance}")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"- **{date}** {period} {year}{suffix}")
        currency = _plain(item.get("currency"))
        rev = _range(
            item.get("revenue_guidance_min"),
            item.get("revenue_guidance_max"),
            item.get("revenue_guidance_est"),
        )
        rev_prior = _range(
            item.get("revenue_guidance_prior_min"), item.get("revenue_guidance_prior_max"), None
        )
        eps = _range(
            item.get("eps_guidance_min"), item.get("eps_guidance_max"), item.get("eps_guidance_est")
        )
        eps_prior = _range(
            item.get("eps_guidance_prior_min"), item.get("eps_guidance_prior_max"), None
        )
        if rev != "-":
            line = f"  revenue {_plain(item.get('revenue_type'))} {currency}: {rev}"
            if rev_prior != "-":
                line += f"  (prior {rev_prior})"
            lines.append(line)
        if eps != "-":
            line = f"  eps {_plain(item.get('eps_type'))}: {eps}"
            if eps_prior != "-":
                line += f"  (prior {eps_prior})"
            lines.append(line)
        note = _truncate(item.get("notes"), 240)
        if note:
            lines.append(f"  note: {note}")
    return "\n".join(lines)


def get_fda_calendar_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """FDA and clinical milestones via ``/v2.1/calendar/fda``.

    Regulatory events: approvals, rejections, trial results and the drug and
    indication they concern. Sparse for a non-biopharma issuer (zero rows is a
    correct answer for, say, AAPL), which is why an empty window raises the
    typed no-data error rather than rendering a bare header.
    """
    _require_dates(start_date, end_date)
    items = _benzinga_get(
        "v2.1/calendar/fda", _calendar_params(ticker, start_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "fda", start_date, end_date)
    lines = _header("FDA / Clinical Milestones", ticker, start_date, end_date)
    for item in items:
        if not isinstance(item, dict):
            continue
        drug = item.get("drug")
        if not isinstance(drug, dict):
            drug = {}
        name = _plain(drug.get("name"))
        indications = drug.get("indication_symptom")
        if isinstance(indications, list) and indications:
            name += f" (indication: {', '.join(str(i) for i in indications[:3])})"
        if drug.get("generic") is True:
            name += " [generic]"
        lines.append(
            f"- **{_plain(item.get('date'))}** {_plain(item.get('event_type'))} \u2014 {name}"
        )
        companies = item.get("companies")
        if isinstance(companies, list) and companies:
            named = []
            for company in companies[:4]:
                if not isinstance(company, dict):
                    continue
                symbols = [
                    str(s.get("symbol"))
                    for s in (company.get("securities") or [])
                    if isinstance(s, dict) and s.get("symbol")
                ]
                label = str(company.get("name") or "").strip()
                named.append(f"{label} ({', '.join(symbols)})" if symbols else label)
            if named:
                lines.append(f"  companies: {'; '.join(named)}")
        target = _plain(item.get("target_date"))
        if target != "-":
            lines.append(f"  target date: {target}")
        status = _plain(item.get("status"))
        if status != "-":
            lines.append(f"  status: {status}")
        brief = _truncate(item.get("outcome_brief") or item.get("outcome"), 300)
        if brief:
            lines.append(f"  {brief}")
    return "\n".join(lines)


def get_offerings_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """Secondary offerings via ``/v2.1/calendar/offerings``.

    A dilution signal: shares issued, the price, the gross size and whether the
    paper came off a shelf. Sparse by nature - the whole US market produced five
    rows in the first nine months of 2026 - so an empty window is normal.
    """
    _require_dates(start_date, end_date)
    items = _benzinga_get(
        "v2.1/calendar/offerings", _calendar_params(ticker, start_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "offerings", start_date, end_date)
    lines = _header("Secondary Offerings", ticker, start_date, end_date)
    for item in items:
        if not isinstance(item, dict):
            continue
        size = _scaled(item.get("dollar_shares"))
        lines.append(
            f"- **{_plain(item.get('date'))}** {_plain(item.get('ticker'))} "
            f"({_plain(item.get('name'))})"
        )
        detail = []
        shares = item.get("number_shares")
        if isinstance(shares, (int, float)) and shares:
            detail.append(f"{int(shares):,} shares")
        price = _price(item.get("price"))
        if price != "-":
            detail.append(f"price {price}")
        if size != "-":
            currency = _plain(item.get("currency"))
            detail.append(f"gross {size} {currency}" if currency != "-" else f"gross {size}")
        # A shelf registration legitimately carries no size yet; the flag is
        # the whole signal in that case, so it is always rendered.
        detail.append("shelf" if item.get("shelf") is True else "no shelf")
        offering_type = _plain(item.get("offering_type"))
        if offering_type != "-":
            detail.append(offering_type)
        lines.append("  " + ", ".join(detail))
        note = _truncate(item.get("notes"), 240)
        if note:
            lines.append(f"  note: {note}")
    return "\n".join(lines)


def get_analyst_actions_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """Individual analyst actions via ``/v2.1/calendar/ratings``.

    One row per action, with the firm, the analyst, what changed (rating and/or
    price target) and the size of the target move. This is the *event* view,
    complementary to ``get_analyst_ratings``' consensus snapshot: it shows the
    revision direction and who made it.
    """
    _require_dates(start_date, end_date)
    items = _benzinga_get(
        "v2.1/calendar/ratings", _calendar_params(ticker, start_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "ratings", start_date, end_date)
    lines = _header("Analyst Actions", ticker, start_date, end_date)
    for item in items:
        if not isinstance(item, dict):
            continue
        date = _plain(item.get("date"))
        clock = str(item.get("time") or "").strip()
        stamp = f"{date} {clock}".strip()
        firm = _plain(item.get("analyst"))
        who = str(item.get("analyst_name") or "").strip()
        if who:
            firm += f" ({who})"
        action = _plain(item.get("action_company"))
        rating_now = _plain(item.get("rating_current"))
        rating_before = _plain(item.get("rating_prior"))
        rating_bit = f"{action} {rating_now}"
        if rating_before != "-" and rating_before != rating_now:
            rating_bit += f" (was {rating_before})"
        lines.append(f"- **{stamp}** {firm}: {rating_bit}")
        pt_now = str(item.get("pt_current") or "").strip()
        pt_before = str(item.get("pt_prior") or "").strip()
        if pt_now or pt_before:
            pt_action = _plain(item.get("action_pt"))
            pct = str(item.get("pt_pct_change") or "").strip()
            bit = f"  pt {pt_action} {_price(pt_before)} \u2192 {_price(pt_now)}"
            if pct:
                bit += f" ({pct}%)"
            lines.append(bit)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# backups for existing multi-vendor routes
# --------------------------------------------------------------------------- #
#
# Each of these renders the SAME contract as the primary vendor for its method,
# so the router can fall through to Benzinga without the caller seeing a
# different shape.
#
# Two of them are worth a note. Measured live 2026-09-20, ``/v1/gov/usa/
# congress/trades`` and ``/v1/sec/insider_transactions/transactions`` **ignore
# every ticker parameter**: ``tickers``, ``symbols``, ``parameters[tickers]``
# and ``company_symbol`` each returned the identical market-wide stream. They
# are firehoses, so the reader fetches a bounded number of pages and filters
# LOCALLY, and the render names that basis rather than implying the vendor
# filtered for it.


def _trailing_window(days: int) -> tuple[str, str]:
    """An ISO window ending today, for readers whose tool passes no dates."""
    end = datetime.now()
    start = end - timedelta(days=int(days))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _insider_symbol(row: dict) -> str:
    """The issuing company's symbol on a Form 4 transaction row."""
    filing = row.get("filing")
    if isinstance(filing, dict):
        return str(filing.get("company_symbol") or "")
    return ""


def _congress_symbol(row: dict) -> str:
    """The traded security's ticker on a congressional trade row."""
    security = row.get("security")
    if isinstance(security, dict):
        return str(security.get("ticker") or "")
    return ""


def _filtered_pages(path: str, symbol: str, pages: int, page_size: int, extract, want: int):
    """Rows whose extracted symbol matches, scanned over at most ``pages`` pages.

    Only for the two market-wide firehose endpoints, which ignore every ticker
    parameter. Scans forward from the newest page and stops as soon as ``want``
    matches are in hand, so the common case costs one request. A page shorter
    than ``page_size`` is the end of the stream.

    **The paging parameter is spelled differently per route family.** Measured
    live 2026-09-20: the ``/v1/*`` endpoints page on lowercase ``pagesize``
    (``pageSize`` there is ignored, and the page slices come back ragged -
    50/150/141 rows) while ``/v2/news-removed`` honours camelCase ``pageSize``.
    Using the wrong spelling does not error; it silently returns a different
    slice, which is how the first version of this reader scanned four "pages"
    and found nothing.
    """
    target = str(symbol or "").strip().upper()
    found: list = []
    for page in range(1, int(pages) + 1):
        batch = _benzinga_get(path, {"pagesize": int(page_size), "page": page}) or []
        if not batch:
            break
        for row in batch:
            if not isinstance(row, dict):
                continue
            if str(extract(row) or "").strip().upper() == target:
                found.append(row)
                if len(found) >= want:
                    return found
        if len(batch) < int(page_size):
            break
    return found


def get_earnings_calendar_benzinga(
    ticker: str, curr_date: str, look_ahead_days: int | None = None
) -> str:
    """Upcoming earnings via ``/v2.1/calendar/earnings``.

    Backup for ``get_earnings_calendar``. The window is FORWARD
    (``[curr_date, curr_date + look_ahead_days]``) because the tool's purpose
    is the next scheduled catalyst; a backward window could never return it.
    Carries the estimate and the prior-year figure, the confirmed flag, and any
    surprise once the print has happened.
    """
    if look_ahead_days is None:
        look_ahead_days = 30
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    end_date = (curr_dt + timedelta(days=int(look_ahead_days))).strftime("%Y-%m-%d")
    items = _benzinga_get(
        "v2.1/calendar/earnings", _calendar_params(ticker, curr_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "earnings", curr_date, end_date)
    lines = [
        f"## {ticker.upper()} Earnings Calendar (Benzinga)",
        f"_forward window {curr_date} .. {end_date}_",
        "",
    ]
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        period = _plain(item.get("period"))
        year = _plain(item.get("period_year"))
        confirmed = "confirmed" if str(item.get("date_confirmed") or "") == "1" else "unconfirmed"
        lines.append(
            f"- **{_plain(item.get('date'))}** {period} {year} ({confirmed})"
            f"{' at ' + str(item.get('time')) if item.get('time') else ''}"
        )
        eps_est = _num(item.get("eps_est"))
        eps_prior = _num(item.get("eps_prior"))
        eps_actual = _num(item.get("eps"))
        eps_bit = f"  eps estimate {eps_est}"
        if eps_prior != "-":
            eps_bit += f" (prior {eps_prior})"
        if eps_actual != "-":
            surprise = _num(item.get("eps_surprise_percent"))
            eps_bit += f" actual {eps_actual}"
            if surprise != "-":
                eps_bit += f" surprise {surprise}%"
        lines.append(eps_bit)
        rev_est = _scaled(item.get("revenue_est"))
        rev_prior = _scaled(item.get("revenue_prior"))
        if rev_est != "-" or rev_prior != "-":
            rev_bit = f"  revenue estimate {rev_est}"
            if rev_prior != "-":
                rev_bit += f" (prior {rev_prior})"
            lines.append(rev_bit)
    return "\n".join(lines)


#: Rating vocabulary buckets, so a consensus can be counted from individual
#: actions. Matched case-insensitively as substrings; an unrecognised label is
#: counted in none of them and is never folded into one by guesswork.
_BUYISH = ("strong buy", "buy", "outperform", "overweight", "accumulate", "positive")
_HOLDISH = ("hold", "neutral", "market perform", "equal-weight", "equal weight", "sector perform")
_SELLISH = ("strong sell", "sell", "underperform", "underweight", "reduce", "negative")


def _rating_bucket(label: str) -> str:
    """``buy`` / ``hold`` / ``sell`` / ``other`` for a vendor rating label.

    ``buy`` is tested after the more specific ``strong buy`` only in the sense
    that the tuple is scanned in order; a label matching nothing is ``other``
    rather than being forced into a bucket.
    """
    text = str(label or "").strip().lower()
    if not text:
        return "other"
    if any(word in text for word in _BUYISH):
        return "buy"
    if any(word in text for word in _HOLDISH):
        return "hold"
    if any(word in text for word in _SELLISH):
        return "sell"
    return "other"


def get_analyst_ratings_benzinga(ticker: str, look_back_days: int = 90) -> str:
    """Sell-side ratings via ``/v2.1/calendar/ratings``.

    Backup for ``get_analyst_ratings``. The tool passes no dates, so the window
    is the trailing ``look_back_days``. The consensus block is **derived from
    the individual actions in that window** and says so: it counts each firm's
    current rating into a buy/hold/sell bucket and summarises the price targets
    the actions carry. It is a different construction from the primary vendors'
    published consensus, which is why it is labelled rather than presented as
    one.
    """
    start_date, end_date = _trailing_window(look_back_days)
    items = _benzinga_get(
        "v2.1/calendar/ratings", _calendar_params(ticker, start_date, end_date)
    )
    if not items:
        raise _no_rows(ticker, "ratings", start_date, end_date)

    buckets = {"buy": 0, "hold": 0, "sell": 0, "other": 0}
    targets: list[float] = []
    firms: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        buckets[_rating_bucket(item.get("rating_current"))] += 1
        firm = str(item.get("analyst") or "").strip()
        if firm:
            firms.add(firm)
        raw = str(item.get("pt_current") or "").strip()
        if raw:
            with contextlib.suppress(ValueError):
                targets.append(float(raw))

    lines = [
        f"## {ticker.upper()} Analyst Ratings (Benzinga)",
        f"_derived from {len(items)} individual actions, {start_date} .. {end_date}_",
        "",
        "### Rating Distribution (latest rating per action)",
        f"- Buy: {buckets['buy']}   Hold: {buckets['hold']}   "
        f"Sell: {buckets['sell']}   Unclassified: {buckets['other']}",
        f"- Distinct firms: {len(firms)}",
    ]
    if targets:
        targets.sort()
        mid = len(targets) // 2
        median = targets[mid] if len(targets) % 2 else (targets[mid - 1] + targets[mid]) / 2
        lines.append(
            f"- Price targets carried by these actions: "
            f"low {targets[0]:.2f}, median {median:.2f}, high {targets[-1]:.2f}"
        )
    lines.append("")
    lines.append("### Recent Actions")
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        stamp = f"{_plain(item.get('date'))} {str(item.get('time') or '').strip()}".strip()
        firm = _plain(item.get("analyst"))
        who = str(item.get("analyst_name") or "").strip()
        if who:
            firm += f" ({who})"
        bit = f"- {stamp} {firm}: {_plain(item.get('action_company'))} {_plain(item.get('rating_current'))}"
        pt_now = str(item.get("pt_current") or "").strip()
        if pt_now:
            bit += f" pt {_price(pt_now)}"
        lines.append(bit)
    return "\n".join(lines)


def get_insider_transactions_benzinga(ticker: str, limit: int = 10) -> str:
    """SEC Form 4 insider transactions via ``/v1/sec/insider_transactions/transactions``.

    Backup for ``get_insider_transactions``. The endpoint ignores every ticker
    parameter, so the rows are the **most recent filings filtered locally** for
    this symbol - the render names that basis. Carries the owner, their
    relationship, the acquired/disposed direction, shares, price, the
    post-transaction holding and the 10b5-1 flag.
    """
    rows = _filtered_pages(
        "v1/sec/insider_transactions/transactions",
        ticker,
        4,
        100,
        _insider_symbol,
        int(limit),
    )
    if not rows:
        raise NoMarketDataError(
            ticker,
            "insider transactions",
            detail="no Form 4 transactions for this symbol in the most recent filings",
        )
    lines = [
        f"## {ticker.upper()} Insider Transactions (Benzinga)",
        "_most recent Form 4 filings, filtered locally (the endpoint takes no ticker filter)_",
        "",
    ]
    for row in rows[: int(limit)]:
        owner = row.get("owner") if isinstance(row.get("owner"), dict) else {}
        name = str(owner.get("insider_name") or "?").strip()
        title = str(owner.get("insider_title") or "").strip()
        roles = [
            label
            for key, label in (
                ("is_officer", "officer"),
                ("is_director", "director"),
                ("is_ten_percent_owner", "10% owner"),
            )
            if owner.get(key) is True
        ]
        who = name
        if title:
            who += f" ({title})"
        elif roles:
            who += f" ({', '.join(roles)})"
        direction = "acquired" if str(row.get("acquired_or_disposed") or "") == "A" else "disposed"
        shares = str(row.get("shares") or "").strip()
        shares_s = f"{shares} shares" if shares else "shares n/a"
        price = _price(row.get("price_per_share"))
        date = str(row.get("date_transaction") or "")[:10] or "?"
        held = str(row.get("post_transaction_quantity") or "").strip()
        filing = row.get("filing") if isinstance(row.get("filing"), dict) else {}
        flags = []
        if filing.get("is_10b5") is True:
            flags.append("10b5-1 plan")
        if row.get("is_derivative") is True:
            flags.append("derivative")
        tail = f" [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"- {date}: {who} — {direction} {shares_s} @ {price} "
            f"(code {_plain(row.get('transaction_code'))}){tail}"
        )
        if held:
            lines.append(f"  holding after: {held}")
    return "\n".join(lines)


#: Congressional transaction type codes the vendor uses.
_CONGRESS_TYPES = {"P": "buy", "S": "sell", "S (partial)": "sell (partial)", "E": "exchange"}


def get_congress_trades_benzinga(ticker: str, limit: int = 8) -> str:
    """Congressional trades via ``/v1/gov/usa/congress/trades``.

    Backup for ``get_congress_trades``. The endpoint ignores every ticker
    parameter, so the rows are the **most recent filings filtered locally** for
    this symbol - the render names that basis. Richer than the keyless mirror
    on filer context: party, state, district and the committees the filer sits
    on, alongside the amount band and the disclosure PDF.
    """
    rows = _filtered_pages(
        "v1/gov/usa/congress/trades", ticker, 4, 100, _congress_symbol, int(limit)
    )
    if not rows:
        raise NoMarketDataError(
            ticker,
            "congress trades",
            detail="no congressional trades for this symbol in the most recent filings",
        )
    buys = sum(1 for r in rows if str(r.get("transaction_type") or "").upper().startswith("P"))
    sells = sum(1 for r in rows if str(r.get("transaction_type") or "").upper().startswith("S"))
    lines = [
        f"## {ticker.upper()} Congressional Trades (Benzinga)",
        "_most recent disclosures, filtered locally (the endpoint takes no ticker filter)_",
        "",
        f"- **Net over the sampled window**: {buys} buys / {sells} sells (net {buys - sells:+d})",
        "",
    ]
    for row in rows[: int(limit)]:
        info = row.get("filer_info") if isinstance(row.get("filer_info"), dict) else {}
        security = row.get("security") if isinstance(row.get("security"), dict) else {}
        chamber = str(row.get("chamber") or info.get("chamber") or "?").strip()
        member = str(info.get("display_name") or info.get("member_name") or "?").strip()
        party = str(info.get("party") or "").strip()
        state = str(info.get("state") or "").strip()
        district = str(info.get("district") or "").strip()
        where = " ".join(part for part in (party, state, district) if part)
        kind = _CONGRESS_TYPES.get(
            str(row.get("transaction_type") or "").strip(),
            _plain(row.get("transaction_type")),
        )
        lines.append(
            f"- {_plain(row.get('transaction_date'))}: {member} ({chamber}"
            f"{', ' + where if where else ''}) — {kind} "
            f"{_plain(security.get('name'))} ({_plain(security.get('ticker'))}), "
            f"amount {_plain(row.get('amount'))}"
        )
        url = str(row.get("disclosure_url") or "").strip()
        if url:
            lines.append(f"  disclosure: {url}")
    return "\n".join(lines)


def get_stock_data_benzinga(symbol: str, start_date: str, end_date: str) -> str:
    """Daily OHLCV via ``/v2/bars``.

    Backup for ``get_stock_data``. **``interval`` is required**: without it the
    vendor answers 200 with a stub row (``[{"symbol": ..., "interval": 3600}]``)
    and no candles, which reads as "no data" rather than "bad request". The
    window is honoured (verified: a 10-day window returns 6 sessions, a 20-day
    window returns 12). Candles carry a millisecond epoch ``time``.
    """
    _require_dates(start_date, end_date)
    rows = _benzinga_get(
        "v2/bars",
        {
            "symbols": symbol,
            "interval": "1D",
            "from": start_date,
            "to": end_date,
        },
    )
    candles: list = []
    for row in rows or []:
        if isinstance(row, dict) and isinstance(row.get("candles"), list):
            candles.extend(c for c in row["candles"] if isinstance(c, dict))
    if not candles:
        raise NoMarketDataError(
            symbol, "stock data", detail=f"no daily bars between {start_date} and {end_date}"
        )
    lines = [
        f"## {symbol} Daily OHLCV (Benzinga)",
        f"_window {start_date} .. {end_date}, {len(candles)} sessions_",
        "",
        "| Date | Open | High | Low | Close | Volume |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candle in candles:
        stamp = str(candle.get("time") or "").strip()
        try:
            day = datetime.utcfromtimestamp(int(stamp) / 1000).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            day = stamp[:10] or "?"
        lines.append(
            f"| {day} | {_num(candle.get('open'), 12)} | {_num(candle.get('high'), 12)} "
            f"| {_num(candle.get('low'), 12)} | {_num(candle.get('close'), 12)} "
            f"| {_num(candle.get('volume'), 14)} |"
        )
    return "\n".join(lines)


def get_corporate_actions_benzinga(ticker: str) -> str:
    """Dividends and splits via the ``/v2.1/calendar`` pair.

    Backup for ``get_corporate_actions``. The tool passes no dates, so the
    windows are trailing: two years of dividends (the ex-date, pay date and
    record date, the amount, the prior amount, the frequency and the yield) and
    three years of splits. A ticker with neither raises the typed no-data error
    rather than rendering two empty headings.
    """
    div_start, div_end = _trailing_window(730)
    split_start, split_end = _trailing_window(1095)
    dividends = _benzinga_get(
        "v2.1/calendar/dividends", _calendar_params(ticker, div_start, div_end)
    )
    splits = _benzinga_get(
        "v2.1/calendar/splits", _calendar_params(ticker, split_start, split_end)
    )
    if not dividends and not splits:
        raise NoMarketDataError(
            ticker,
            "corporate actions",
            detail=f"no dividends since {div_start} and no splits since {split_start}",
        )
    lines = [f"## {ticker.upper()} Corporate Actions (Benzinga)", ""]
    if dividends:
        lines.append(f"### Dividends ({div_start} .. {div_end})")
        for item in dividends:
            if not isinstance(item, dict):
                continue
            amount = _price(item.get("dividend"))
            prior = str(item.get("dividend_prior") or "").strip()
            bit = f"- {_plain(item.get('date'))}: {amount} {_plain(item.get('currency'))}"
            if prior:
                bit += f" (prior {_price(prior)})"
            frequency = item.get("frequency")
            if isinstance(frequency, (int, float)) and frequency:
                bit += f", {int(frequency)}x/yr"
            yield_pct = str(item.get("dividend_yield") or "").strip()
            if yield_pct:
                with contextlib.suppress(ValueError):
                    bit += f", yield {float(yield_pct) * 100:.2f}%"
            lines.append(bit)
            dates = []
            for label, key in (
                ("ex", "ex_dividend_date"),
                ("record", "record_date"),
                ("payable", "payable_date"),
            ):
                value = str(item.get(key) or "").strip()
                if value:
                    dates.append(f"{label} {value}")
            if dates:
                lines.append("  " + ", ".join(dates))
        lines.append("")
    if splits:
        lines.append(f"### Splits ({split_start} .. {split_end})")
        for item in splits:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {_plain(item.get('date'))}: {_plain(item.get('ratio'))} "
                f"({_plain(item.get('split_type'))})"
            )
    return "\n".join(lines)


__all__ = [
    "benzinga_api_key",
    "get_analyst_actions_benzinga",
    "get_analyst_ratings_benzinga",
    "get_congress_trades_benzinga",
    "get_corporate_actions_benzinga",
    "get_earnings_calendar_benzinga",
    "get_fda_calendar_benzinga",
    "get_guidance_benzinga",
    "get_insider_transactions_benzinga",
    "get_news_benzinga",
    "get_news_removed_benzinga",
    "get_offerings_benzinga",
    "get_stock_data_benzinga",
]
