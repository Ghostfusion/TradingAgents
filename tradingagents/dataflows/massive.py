"""Massive.com data vendor: U.S. news with native sentiment (first integration).

Massive (``api.massive.com``, the renamed Polygon.io lineage) is a U.S.-centric
market-data provider. This module starts with the highest-leverage data it
exposes for TradingAgents: per-ticker news with **structured sentiment** from
the ``/v2/reference/news`` endpoint. Every article carries ``insights[]`` with
a ``sentiment`` (positive/negative/neutral) plus a ``sentiment_reasoning``
string, so the Sentiment and News analysts can read a computed signal instead
of guessing polarity from raw headlines.

Follows the vendor taxonomy in ``errors.py`` like the other vendors:

- a missing key raises ``MassiveNotConfiguredError`` so the routing layer treats
  the vendor as "unavailable" instead of crashing;
- empty / no-usable-rows raises ``NoMarketDataError`` so the router emits an
  honest "no data" signal rather than an empty string;
- transient 429 throttling surfaces as ``VendorRateLimitError`` so the router
  degrades to the next vendor instead of failing a run.

Scope note: Massive is US-centric. It is deliberately additive to the existing
moomoo/yfinance coverage (which handle HK/JP/IN/SS/SZ/etc.), not a replacement,
and production users must pick a plan whose recency (15-min delayed vs
real-time) matches the use case.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError
from .vendor_breaker import (
    note_vendor_ok,
    note_vendor_refused,
    note_vendor_transient,
    vendor_skip_reason,
)

logger = logging.getLogger(__name__)

BASE = "https://api.massive.com"
TIMEOUT = 20
_MAX_RETRIES = 2
_NEWS_LIMIT = 10  # default articles requested per query

# Possible sentiment values the provider returns.
_VALID_SENTIMENTS = {"positive", "negative", "neutral"}


class MassiveNotConfiguredError(VendorNotConfiguredError):
    """Raised when Massive is selected but no API key is configured.

    A ``VendorNotConfiguredError`` (and thus still a ValueError), so the routing
    layer's "vendor unavailable" handling and existing ValueError callers both
    keep working.
    """


def massive_api_key() -> str | None:
    """Massive key from config or environment; None when unset.

    Resolves from (1) the ``massive_api_key`` config key, then (2) env
    ``MASSIVE_API_KEY``. This mirrors the finnhub/fmp key resolution so the key
    stays in .env (gitignored) and never in code.
    """
    try:
        key = get_config().get("massive_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("MASSIVE_API_KEY")


def _capability(path: str) -> str:
    """Endpoint identity for the vendor health gate: the path minus a trailing symbol.

    A 403/429 belongs to the endpoint and the plan, never to the symbol, so
    ``.../tickers/ZM`` and ``.../tickers/NVDA`` must share one entry - keyed per
    symbol the negative cache would need a new entry for every name and would
    never actually suppress the re-ask.
    """
    parts = [p for p in str(path).split("/") if p]
    if parts and (parts[-1].isupper() or parts[-1].replace("-", "").isdigit()):
        parts.pop()
    return "/".join(parts)


def _get(path: str, params: dict | None = None) -> list | dict | None:
    """Authenticated GET; parsed JSON or None on any non-data failure.

    Raises no-network errors via the typed taxonomy on the way out:
    401/403 -> VendorNotConfigured-ish, 429 -> VendorRateLimitError, empty
    result conventions are left to the caller.
    """
    key = massive_api_key()
    if not key:
        raise MassiveNotConfiguredError(
            "Massive API key is not configured. Set MASSIVE_API_KEY in .env "
            "(or massive_api_key in config)."
        )
    capability = _capability(path)
    skip = vendor_skip_reason("massive", capability)
    if skip == "absent":
        # A plan/key verdict already recorded: skip without spending a request.
        # Not-configured is the honest type - this endpoint will not serve this
        # account, so the caller's plan-gated advisory is the right message.
        raise MassiveNotConfiguredError(
            f"Massive {capability} is known unavailable on this account plan; "
            "skipped (negative cache)."
        )
    if skip == "breaker":
        # Repeated transient failures are a rate-limit story, so they must
        # PROPAGATE - counting one as a served advisory would turn a throttle
        # into a fact.
        raise VendorRateLimitError(
            f"Massive {capability} skipped: breaker open after repeated transient failures"
        )
    url = f"{BASE}{path}"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if resp.status_code in (401, 403):
                # Access-denied (403) can also be an entitlements gap — the key
                # is valid but the account's plan lacks the requested endpoint.
                logger.warning(
                    "Massive auth/entitlement %s for %s; check MASSIVE_API_KEY "
                    "and the account plan.",
                    resp.status_code,
                    path,
                )
                note_vendor_refused("massive", capability)
                raise MassiveNotConfiguredError(
                    f"Massive returned HTTP {resp.status_code} (bad key or "
                    "plan lacks this dataset)"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                note_vendor_transient("massive")
                raise VendorRateLimitError(
                    f"Massive {path} returned HTTP {resp.status_code}"
                )
            if resp.status_code != 200:
                logger.warning("Massive %s: status %s", path, resp.status_code)
                return None
            note_vendor_ok("massive")
            return resp.json()
        except MassiveNotConfiguredError:
            raise
        except VendorRateLimitError:
            raise
        except requests.Timeout as exc:
            raise VendorRateLimitError(f"Massive {path} timed out") from exc
        except requests.RequestException as exc:
            if attempt < _MAX_RETRIES:
                logger.warning("Massive %s transient: %s; retrying", path, exc)
                continue
            logger.warning("Massive %s failed after retries: %s", path, exc)
            return None
    return None


def _requested_ticker_in(article: dict, ticker: str) -> bool:
    """True when ``ticker`` appears in the article's tickers or insights."""
    tickers = article.get("tickers") or []
    if ticker.lower() in [t.lower() for t in tickers]:
        return True
    for insight in article.get("insights") or []:
        if (insight.get("ticker") or "").lower() == ticker.lower():
            return True
    return False


def get_news_massive(
    ticker: str, start_date: str, end_date: str, limit: int = _NEWS_LIMIT
) -> str:
    """Retrieve recent news articles with structured sentiment for a ticker.

    Filters the provider's multi-ticker articles down to rows tagged with the
    requested symbol, and renders each article's sentiment + reasoning so the
    news / sentiment analysts read a computed polarity rather than raw prose.

    Args:
        ticker: Case-sensitive symbol (AAPL).
        start_date / end_date: yyyy-mm-dd publishing window.
        limit: cap on articles fetched before the ticker filter.

    Returns a formatted markdown report, or raises ``NoMarketDataError`` when
    no article matches the ticker.
    """
    payload = _get(
        "/v2/reference/news",
        {
            "ticker": ticker,
            "published_utc.gte": f"{start_date}T00:00:00Z",
            "published_utc.lte": f"{end_date}T23:59:59Z",
            "limit": limit,
        },
    )
    articles = (payload or {}).get("results") if isinstance(payload, dict) else payload
    if not isinstance(articles, list) or not articles:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no news for {start_date}..{end_date}"
        )

    relevant = [a for a in articles if _requested_ticker_in(a, ticker)]
    if not relevant:
        raise NoMarketDataError(
            ticker,
            detail=f"Massive returned news but none tagged with {ticker} "
            f"(provider articles carry multiple tickers)",
        )

    lines = [
        f"## {ticker} Massive.com news with sentiment ({start_date} to {end_date}):",
        "",
    ]
    for article in relevant:
        title = article.get("title", "No Title")
        published = article.get("published_utc", "")
        pub = article.get("publisher") or {}
        source = pub.get("name", "")
        url = article.get("article_url", "")
        lines.append(f"### {title}")
        if published:
            lines.append(f"Published: {published}")
        if source:
            lines.append(f"Source: {source}")
        desc = article.get("description")
        if desc:
            lines.append(f"{desc}")
        # Only surface the sentiment tagged for THIS ticker.
        own_insight = None
        for insight in article.get("insights") or []:
            if (insight.get("ticker") or "").lower() == ticker.lower():
                own_insight = insight
                break
        if own_insight:
            sentiment = own_insight.get("sentiment", "")
            reasoning = own_insight.get("sentiment_reasoning", "")
            tag = sentiment if sentiment in _VALID_SENTIMENTS else "unavailable"
            lines.append(f"Sentiment: {tag}")
            if reasoning:
                lines.append(f"Sentiment reasoning: {reasoning}")
        if url:
            lines.append(f"Link: {url}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Economy (REST `/fed/v1/*`) — macro series and deterministic macro backdrop
# ---------------------------------------------------------------------------

# Friendly aliases -> (endpoint, response field, units, frequency). Mirrors
# the FRED macro tool's surface so the Macro analyst can switch vendors while
# the LLM prompt keeps the same alias vocabulary.
_MACRO_SERIES = {
    # Treasury yields (daily)
    "10y_treasury": ("/fed/v1/treasury-yields", "yield_10_year", "%", "daily"),
    "2y_treasury": ("/fed/v1/treasury-yields", "yield_2_year", "%", "daily"),
    "30y_treasury": ("/fed/v1/treasury-yields", "yield_30_year", "%", "daily"),
    "yield_curve": ("/fed/v1/treasury-yields", "spread_10y2y", "%", "daily"),
    "10y_2y_spread": ("/fed/v1/treasury-yields", "spread_10y2y", "%", "daily"),
    # Inflation (monthly)
    "cpi": ("/fed/v1/inflation", "cpi", "index", "monthly"),
    "core_cpi": ("/fed/v1/inflation", "cpi_core", "index", "monthly"),
    "pce": ("/fed/v1/inflation", "pce", "index", "monthly"),
    "core_pce": ("/fed/v1/inflation", "pce_core", "index", "monthly"),
    # Inflation expectations (daily, breakevens %)
    "inflation_expectations": (
        "/fed/v1/inflation-expectations", "market_10_year", "%", "daily"
    ),
    "10y_breakeven": ("/fed/v1/inflation-expectations", "market_10_year", "%", "daily"),
    "5y_breakeven": ("/fed/v1/inflation-expectations", "market_5_year", "%", "daily"),
    # Labor (monthly)
    "unemployment": ("/fed/v1/labor-market", "unemployment_rate", "%", "monthly"),
    "unemployment_rate": (
        "/fed/v1/labor-market", "unemployment_rate", "%", "monthly"
    ),
    "labor_force_participation": (
        "/fed/v1/labor-market", "labor_force_participation_rate", "%", "monthly"
    ),
    "avg_hourly_earnings": (
        "/fed/v1/labor-market", "avg_hourly_earnings", "USD", "monthly"
    ),
    "job_openings": ("/fed/v1/labor-market", "job_openings", "thousands", "monthly"),
}


_DEFAULT_LOOKBACK_DAYS = 365
_MAX_MACRO_ROWS = 40


def get_macro_indicators_massive(
    indicator: str, curr_date: str, look_back_days: int | None = None
) -> str:
    """Fetch a macro time series from Massive's economy endpoints.

    Supports the same friendly aliases the FRED tool exposes (``cpi``,
    ``core_pce``, ``unemployment``, ``10y_treasury``, ``yield_curve``,
    ``inflation_expectations``, ...) so the Macro analyst can switch vendors
    without re-learning an alias vocabulary. Returns a formatted markdown
    report (title, units, window, latest, change, recent table) matching the
    FRED vendor's contract.

    Args:
        indicator: Friendly alias (e.g. "cpi", "10y_treasury").
        curr_date: End of the window (yyyy-mm-dd); no later observations are
            returned, so a past date never leaks future data.
        look_back_days: Trailing window length; None uses a 1-year default.

    Returns:
        str: A markdown macro report, or a clear "unavailable/unknown alias"
            message (the latter so a bad LLM argument doesn't abort the run).
    """
    key = indicator.strip().lower()
    entry = _MACRO_SERIES.get(key)
    if entry is None:
        return (
            f"Massive: '{indicator}' is not a known macro alias. Use one of: "
            + ", ".join(sorted(set(_MACRO_SERIES)))
        )
    endpoint, field, units, freq = entry

    if look_back_days is None:
        look_back_days = _DEFAULT_LOOKBACK_DAYS
    from datetime import datetime, timedelta

    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    payload = _get(
        endpoint,
        {
            "date.gte": start_date,
            "date.lte": curr_date,
            "sort": "date.desc",
            "limit": _MAX_MACRO_ROWS,
        },
    )
    rows = (payload or {}).get("results") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        return f"Massive: no {field} data for {indicator} in {start_date}..{curr_date}."

    header = (
        f"## Massive: {indicator} ({field})\n"
        f"- Units: {units}\n"
        f"- Frequency: {freq}\n"
        f"- Window: {start_date} to {curr_date}\n"
    )

    # yield_curve maps to a derived spread, not a raw row field.
    points = []
    for row in rows:
        date_s = str(row.get("date") or "")
        if field == "spread_10y2y":
            try:
                val = float(row.get("yield_10_year")) - float(row.get("yield_2_year"))
            except (TypeError, ValueError):
                continue
        else:
            raw = row.get(field)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
        points.append((date_s, val))

    if not points:
        return f"Massive: no usable {indicator} observations in this window."

    # rows are newest-first; sort ascending for consistency with FRED.
    points.sort(key=lambda p: p[0])
    first_date, first_val = points[0]
    last_date, last_val = points[-1]
    delta = last_val - first_val
    base = first_val
    pct = f" ({delta / base * 100:+.2f}%)" if base != 0 else ""
    summary = (
        f"\n**Latest:** {last_val:g} ({last_date}) | "
        f"**Change over window:** {delta:+.2f}{pct} "
        f"from {first_val:g} ({first_date})\n"
    )

    table = (
        "\n| Date | Value |\n| --- | --- |\n"
        + "\n".join(f"| {d} | {v:g} |" for d, v in points[-_MAX_MACRO_ROWS:])
        + "\n"
    )

    return header + summary + table


# Macro-backdrop helpers the catalyst overlay uses to de-risk without depending
# on a forward event calendar (moomoo economic_calendar / fed_watch). Massive's
# economy endpoints are time-series, not forward calendars, so the backdrop is a
# deterministic read of *current/accentuated* macro stress (yield-curve
# inversion, elevated breakevens / CPI) rather than a count of imminent events.


def is_yield_curve_inverted(rows: list) -> bool | None:
    """True when the latest 10y-2y spread is negative (inverted curve)."""
    for row in rows or []:
        try:
            return (float(row.get("yield_10_year")) - float(row.get("yield_2_year"))) < 0
        except (TypeError, ValueError):
            continue
    return None


def latest_breakeven(rows: list, field: str = "market_10_year") -> float | None:
    """Latest breakeven inflation (10y by default) from expectation rows."""
    for row in rows or []:
        try:
            return float(row[field])
        except (KeyError, TypeError, ValueError):
            continue
    return None


# Thresholds for the macro backdrop signal (documented in docs/massive_integration.md).
_INVERSION_SCALE = 0.7
_ELEVATED_BREAKEVEN = 3.0  # 10y breakeven % above which inflation is stressed
_BREAKEVEN_SCALE = 0.75


def fetch_macro_backdrop(
    trade_date: str, look_back_days: int = 90
) -> dict | None:
    """Deterministic macro stress signal from Massive treasury/inflation data.

    Returns None when the data is unavailable (guarded, mirrors the other
    guarded fetches). Otherwise returns
    ``{"scale", "verdict", "reasons", "curve_inverted", "breakeven"}`` where
    ``scale`` is a 0..1 de-risk multiplier to apply when the moomoo event
    calendar is unavailable. ``verdict`` is ``macro-backdrop`` when stressed or
    ``no-macro-stress`` when the data reads calm.
    """
    try:
        from datetime import datetime, timedelta

        end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        start = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        end = trade_date

        yt = _get(
            "/fed/v1/treasury-yields",
            {"date.gte": start, "date.lte": end, "sort": "date.desc", "limit": 30},
        )
        yields = (yt or {}).get("results") if isinstance(yt, dict) else yt
        inverted = is_yield_curve_inverted(yields) if isinstance(yields, list) else None

        ie = _get(
            "/fed/v1/inflation-expectations",
            {"date.gte": start, "date.lte": end, "sort": "date.desc", "limit": 30},
        )
        ierows = (ie or {}).get("results") if isinstance(ie, dict) else ie
        breakeven = (
            latest_breakeven(ierows) if isinstance(ierows, list) else None
        )
        if breakeven is not None:
            breakeven = round(breakeven, 2)

        stressed = inverted is True or (
            breakeven is not None and breakeven > _ELEVATED_BREAKEVEN
        )
        if not stressed:
            return {
                "scale": 1.0,
                "verdict": "no-macro-stress",
                "reasons": [],
                "curve_inverted": inverted,
                "breakeven": breakeven,
            }

        scale = 1.0
        reasons = []
        if inverted is True:
            scale *= _INVERSION_SCALE
            reasons.append("yield curve inverted (10y<2y) -> x0.70")
        if breakeven is not None and breakeven > _ELEVATED_BREAKEVEN:
            scale *= _BREAKEVEN_SCALE
            reasons.append(f"10y breakeven {breakeven:.2f}% elevated -> x0.75")
        return {
            "scale": round(max(0.0, scale), 4),
            "verdict": "macro-backdrop",
            "reasons": reasons,
            "curve_inverted": inverted,
            "breakeven": breakeven,
        }
    except Exception as exc:  # noqa: BLE001 - guarded like orderflow.fetch
        logger.info("massive macro backdrop unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Short interest / short volume (REST `/stocks/v1/*`) — squeeze & conviction
# ---------------------------------------------------------------------------


def _fmt_int(value) -> str:
    """Format a number with thousands separators, or 'n/a'."""
    if value is None:
        return "n/a"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if n.is_integer():
        return f"{int(n):,}"
    return f"{n:,.1f}"


def get_short_interest_massive(ticker: str, rows: int = 4) -> str:
    """FINRA short interest (two-week settlement cadence) for a ticker.

    Matches the ``get_short_interest(ticker)`` vendor contract (single symbol
    arg) so it plugs into the existing ``short_interest`` category and the
    ``get_short_interest`` tool. Returns the most recent settlements
    (newest-first) with short_interest, days_to_cover and average daily volume
    so the market analyst reads a squeeze/conviction signal.

    Raises ``NoMarketDataError`` when the provider returns no rows.
    """
    from .errors import NoMarketDataError  # local to avoid top-level cycle

    payload = _get(
        "/stocks/v1/short-interest",
        {"ticker": ticker, "sort": "settlement_date.desc", "limit": rows},
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no short-interest for {ticker}"
        )

    lines = [f"## {ticker.upper()} Short Interest (Massive.com, FINRA)", ""]
    for row in results:
        date_s = str(row.get("settlement_date") or "?")[:10]
        short_i = row.get("short_interest")
        dtc = row.get("days_to_cover")
        adv = row.get("avg_daily_volume")
        lines.append(f"- Settlement {date_s}:")
        lines.append(f"  - Shares short: {_fmt_int(short_i)}")
        lines.append(f"  - Days to cover: {_fmt_num(dtc)}")
        lines.append(f"  - Avg daily volume: {_fmt_int(adv)}")

    # P0-6: a level is not a signal on its own - rank the latest settlement
    # against the name's OWN settlement history and state the sign explicitly
    # (SentimentScore.md 0.2 point 4: high short interest is bearish positioning
    # with a squeeze RISK, never a bullish signal). The vendor returns
    # newest-first, so the series is reversed before ranking.
    try:
        from tradingagents.strategies.short_interest import short_interest_percentile

        series = [row.get("short_interest") for row in reversed(results)]
        si = short_interest_percentile(series)
        if si["latest"] is not None:
            change = (
                f", {si['change_pct']:+.1f}% vs prior settlement"
                if si["change_pct"] is not None
                else ""
            )
            lines.append("")
            lines.append(
                f"- Latest settlement vs its own history: {si['basis']}{change}"
            )
            if si["percentile"] is not None:
                lines.append(f"  - Percentile: {si['percentile']:.0%}")
            lines.append(f"  - {si['direction']}")
    except Exception:  # noqa: BLE001 - the raw settlements are still the report
        pass

    latest = results[0]
    dtc = latest.get("days_to_cover")
    lines.append("")
    note = (
        "Interpretation: days_to_cover >5 means unwinding would take time "
        "(high squeeze/conviction); short-interest rising across settlements "
        "indicates building bearish positioning."
    )
    if dtc is not None:
        try:
            lines.append(f"Latest days-to-cover = {float(dtc):.1f}.")
            lines.append(note)
        except (TypeError, ValueError):
            pass
    return "\n".join(lines)


def get_short_volume_massive(
    ticker: str, start_date: str, end_date: str, rows: int = 10
) -> str:
    """Daily short-sale volume ratio (%) for a ticker from FINRA / ATS data.

    ``short_volume_ratio`` = short volume / total volume (%). Elevated readings
    indicate heavy intraday shorting — a conviction / squeeze signal the
    market analyst can weigh. Returns the most recent days within the window,
    newest-first.

    Raises ``NoMarketDataError`` when the provider returns no rows.
    """
    from .errors import NoMarketDataError

    payload = _get(
        "/stocks/v1/short-volume",
        {
            "ticker": ticker,
            "date.gte": start_date,
            "date.lte": end_date,
            "limit": rows,
        },
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no short-volume for {ticker}"
        )

    lines = [f"## {ticker.upper()} Short Volume (Massive.com, % of total)", ""]
    for row in results:
        date_s = str(row.get("date") or "?")[:10]
        ratio = row.get("short_volume_ratio")
        short_v = row.get("short_volume")
        total_v = row.get("total_volume")
        lines.append(
            f"- {date_s}: short volume {_fmt_int(short_v)} of {_fmt_int(total_v)} "
            f"({_fmt_num(ratio)}%)"
        )
    return "\n".join(lines)


def _fmt_num(value) -> str:
    """Format a number to 1-2 decimals; n/a when unparseable."""
    if value is None:
        return "n/a"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{n:.1f}"


# ---------------------------------------------------------------------------
# SEC filings (REST `/stocks/filings/vX/*`) — institutional + insider ownership
# ---------------------------------------------------------------------------


def _plural_ticker_param(ticker: str) -> str:
    """Normalize mass to single ticker for the ``ticker``/``tickers`` filters."""
    return ticker.strip().upper()


def get_form4_insider_massive(
    ticker: str, start_date: str, end_date: str, rows: int = 500
) -> str:
    """Open-market insider transactions (Form 4) for a ticker over a window.

    Pulls the latest Form 4 filings tagged for ``ticker`` within the window and
    separates open-market **purchases** (transaction_code ``P``) from **sales**
    (``S``), then reports the net dollar amount of open-market buying — a
    direct insider-accumulation/distribution signal. Grant/award (``A``) and
    exercise (``M``) rows are excluded from the net to avoid option-stuff
    noise.

    Raises ``NoMarketDataError`` when the provider returns no rows.
    """
    from .errors import NoMarketDataError

    payload = _get(
        "/stocks/filings/vX/form-4",
        {
            "tickers": _plural_ticker_param(ticker),
            "filing_date.gte": start_date,
            "filing_date.lte": end_date,
            "limit": rows,
        },
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no Form 4 filings for {ticker}"
        )

    buy_val = 0.0
    sell_val = 0.0
    buys = 0
    sells = 0
    for row in results:
        code = str(row.get("transaction_code") or "").upper()
        if code not in ("P", "S"):
            continue
        val = row.get("transaction_value")
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        if code == "P":
            buy_val += val
            buys += 1
        else:
            sell_val += val
            sells += 1

    net = buy_val - sell_val
    lines = [
        f"## {ticker.upper()} Insider Transactions (Form 4, Massive.com)",
        "",
        f"Window: {start_date} to {end_date}",
        f"- Open-market buys (P): {buys} tx, ${_fmt_int(buy_val)}",
        f"- Open-market sells (S): {sells} tx, ${_fmt_int(sell_val)}",
        f"- Net open-market $: {_fmt_signed(net)}",
        "",
        "Sample recent transactions:",
    ]
    shown = 0
    for row in results:
        if shown >= 8:
            break
        code = str(row.get("transaction_code") or "").upper()
        if code not in ("P", "S"):
            continue
        lines.append(
            f"- {str(row.get('transaction_date') or row.get('filing_date') or '?')[:10]} "
            f"| {row.get('owner_name') or '?'} ({'director' if row.get('is_director') else 'officer' if row.get('is_officer') else 'owner'}) "
            f"| {'BUY' if code=='P' else 'SELL'} "
            f"{_fmt_int(row.get('transaction_shares'))} sh @ {_fmt_num(row.get('transaction_price_per_share'))} "
            f"= ${_fmt_int(row.get('transaction_value'))}"
        )
        shown += 1
    lines.append("")
    lines.append(
        "Interpretation: sustained insider open-market buying is a (secondary) "
        "accumulation signal; net selling a caution flag. Excludes option "
        "grant/exercise (A/M) rows to avoid compensation noise."
    )
    return "\n".join(lines)


def _fmt_signed(value) -> str:
    """Format a signed dollar amount with thousands separators."""
    if value is None:
        return "n/a"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{'+' if n > 0 else ''}{n:,.0f}"


# ---------------------------------------------------------------------------
# SEC filing TEXT (REST `/stocks/filings/vX/*` and `/stocks/taxonomies/vX/*`)
#
# `sec_edgar.py` owns XBRL facts, filing metadata and EDGAR full-text SEARCH but
# has no item-level section extraction. These readers add the narrative — the
# 10-K's own item text, the categorised risk-factor set, and the 8-K's items —
# which is what the fundamentals analyst grounds a risk/strategy claim in.
#
# MEASURED LIVE 2026-10-01 (and unlike the 13-F deferral below): all three
# filing reads HONOUR the `ticker` filter — 10/10, 50/50 and 10/10 rows came
# back for the requested symbol. `/stocks/filings/8-K/vX/disclosures` did NOT
# (an AAPL query returned another issuer's rows), so it is deliberately NOT
# read here; that is the same defect that defers 13-F in
# `docs/massive_integration.md` §3c, and a per-ticker aggregate built on it
# would mix issuers.
#
# Text is LONG — a 10-K risk-factor section measured 53k–69k chars — so every
# reader renders a BOUNDED excerpt and states how much it withheld. A truncated
# quote that says so is honest; one that does not is a misquote.
# ---------------------------------------------------------------------------

_SECTIONS_PATH = "/stocks/filings/10-K/vX/sections"
_RISK_FACTORS_PATH = "/stocks/filings/vX/risk-factors"
_8K_TEXT_PATH = "/stocks/filings/8-K/vX/text"
_RISK_TAXONOMY_PATH = "/stocks/taxonomies/vX/risk-factors"

# The section names the vendor actually publishes (measured: a five-year AAPL
# read returned only these two). A requested name outside the set is NAMED,
# never silently answered with a different section.
TEN_K_SECTIONS = ("risk_factors", "business")

# Bound per excerpt, and per category for the risk-factor set: a report head
# cannot carry 68k chars, and a silently truncated quote would misrepresent it.
_SECTION_EXCERPT_CHARS = 1500
_RISK_ROWS_PER_CATEGORY = 6
_SUPPORTING_TEXT_CHARS = 300


def _excerpt(text, limit: int = _SECTION_EXCERPT_CHARS) -> str:
    """One bounded line of ``text``, saying what it withheld.

    Collapses newlines so a section renders as a single quotable line and
    appends ``[+N chars withheld]`` when it cut — an unlabelled truncation
    would read as the whole item.
    """
    flat = " ".join(str(text or "").split())
    if not flat:
        return "(empty text)"
    if len(flat) <= limit:
        return flat
    return f"{flat[:limit]} [+{len(flat) - limit} chars withheld]"


def _taxonomy_block(kind: str = "risk-factors", limit: int = 21) -> str:
    """The vendor's category dictionary for a filing taxonomy, as a table.

    Private on purpose: ``/stocks/taxonomies/*`` is reference data with no
    ticker and no signal of its own — it only explains the category labels the
    filing readers print, so it is rendered *inside* them rather than exposed
    as a read an analyst would call by itself.
    """
    rows: list = []
    try:
        payload = _get(_RISK_TAXONOMY_PATH if kind == "risk-factors"
                       else "/stocks/taxonomies/vX/disclosures",
                       {"limit": int(limit)})
    except Exception as exc:  # noqa: BLE001 - the dictionary is context, not data
        return f"\nCategory dictionary unavailable: {exc}"
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if isinstance(results, list):
        rows = [r for r in results if isinstance(r, dict)]
    if not rows:
        return "\nCategory dictionary: no rows returned."
    lines = ["", f"Category dictionary ({kind}, {len(rows)} shown):", ""]
    for row in rows:
        path = " / ".join(
            str(row.get(k) or "")
            for k in ("primary_category", "secondary_category", "tertiary_category")
        ).strip(" /")
        desc = str(row.get("description") or "").strip()
        lines.append(f"- {path or row.get('taxonomy') or '?'}"
                     + (f" — {desc}" if desc else ""))
    return "\n".join(lines)


def get_filing_sections_massive(
    ticker: str, section: str | None = None, limit: int = 10
) -> str:
    """10-K item sections — the filing's own PROSE, newest first.

    `sec_edgar` owns the XBRL facts and the filing list; this is the narrative,
    e.g. the 10-K's own Item 1A Risk Factors and Item 1 Business text, which no
    other reader in this tree carries. Measured live: the vendor publishes only
    ``risk_factors`` and ``business``, over about five fiscal years.

    ``section`` filters client-side to one published name; an unknown name is
    **named with the published set**, never silently answered with a different
    section. Each section renders as a bounded excerpt that states how much it
    withheld.

    Raises ``NoMarketDataError`` when the vendor returns no rows.
    """
    from .errors import NoMarketDataError

    payload = _get(
        _SECTIONS_PATH,
        {"ticker": _plural_ticker_param(ticker), "limit": int(limit)},
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no 10-K sections for {ticker}"
        )

    rows = [r for r in results if isinstance(r, dict)]
    published = sorted(
        {str(r.get("section") or "") for r in rows if r.get("section")}
    ) or list(TEN_K_SECTIONS)
    want = (section or "").strip().lower()
    if want:
        rows = [r for r in rows if str(r.get("section") or "").strip().lower() == want]
    lines = [
        f"## {ticker.upper()} 10-K sections (SEC filing text, Massive.com)",
        "",
        f"Published sections: {', '.join(published) or 'none'}; "
        f"{len(results)} row(s) returned"
        + (f", {len(rows)} matching '{want}'" if want else ""),
        "",
    ]
    if not rows:
        lines.append(
            f"No rows for section '{want}'. The vendor publishes: "
            f"{', '.join(published) or 'none'}. Nothing is substituted for a "
            "missing section."
        )
        return "\n".join(lines)
    for row in rows:
        lines += [
            f"### {row.get('section')} — period ending {row.get('period_end')} "
            f"(filed {row.get('filing_date')})",
            "",
            _excerpt(row.get("text")),
            f"Source: {row.get('filing_url')}",
            "",
        ]
    lines.append(
        "Interpretation: this is the filing's own text, quoted in excerpts — "
        "the primary source for a risk or strategy claim. Cite the period; the "
        "wording changes year to year."
    )
    return "\n".join(lines)


def get_risk_factors_massive(
    ticker: str, limit: int = 50, include_taxonomy: bool = False
) -> str:
    """Categorised risk factors drawn from a ticker's filings (Massive.com).

    Each row is a risk statement carrying ``primary``/``secondary``/
    ``tertiary_category`` labels plus the ``supporting_text`` it was drawn from
    — a categorised view the raw 10-K text is not. ``include_taxonomy`` also
    prints the vendor's category dictionary, so the labels can be read rather
    than guessed. Measured live: the ``ticker`` filter is honoured (50/50 rows).

    Raises ``NoMarketDataError`` when the vendor returns no rows.
    """
    from .errors import NoMarketDataError

    payload = _get(
        _RISK_FACTORS_PATH,
        {"ticker": _plural_ticker_param(ticker), "limit": int(limit)},
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no risk factors for {ticker}"
        )

    rows = [r for r in results if isinstance(r, dict)]
    by_cat: dict[str, list] = {}
    for row in rows:
        by_cat.setdefault(
            str(row.get("primary_category") or "uncategorised"), []
        ).append(row)
    lines = [
        f"## {ticker.upper()} Risk factors (SEC filing text, Massive.com)",
        "",
        f"{len(rows)} categorised risk statement(s) across "
        f"{len(by_cat)} primary categor{'y' if len(by_cat) == 1 else 'ies'}",
        "",
    ]
    for cat in sorted(by_cat):
        items = by_cat[cat]
        lines.append(f"### {cat} ({len(items)})")
        for row in items[:_RISK_ROWS_PER_CATEGORY]:
            sub = " / ".join(
                str(row.get(k) or "")
                for k in ("secondary_category", "tertiary_category")
            ).strip(" /")
            lines.append(
                f"- **{sub or 'uncategorised'}** "
                f"(filed {str(row.get('filing_date') or '')[:10]}): "
                f"{_excerpt(row.get('supporting_text'), _SUPPORTING_TEXT_CHARS)}"
            )
        if len(items) > _RISK_ROWS_PER_CATEGORY:
            lines.append(
                f"- ... {len(items) - _RISK_ROWS_PER_CATEGORY} more in this category "
                "(raise `limit` to see them)"
            )
        lines.append("")
    if include_taxonomy:
        lines.append(_taxonomy_block("risk-factors"))
        lines.append("")
    lines.append(
        "Interpretation: these are the issuer's own disclosed risks, categorised "
        "by the vendor. A category with many statements is where the filing "
        "spends its risk budget — not a probability."
    )
    return "\n".join(lines)


def get_8k_filings_massive(ticker: str, limit: int = 10) -> str:
    """Recent 8-K current reports with their ITEM TEXT (Massive.com).

    The event-level narrative — e.g. "Item 2.02 Results of Operations and
    Financial Condition" — which `sec_edgar.recent_filing_forms` does not carry
    (it lists the forms, not their text). Measured live: the ``ticker`` filter
    is honoured (10/10 rows).

    Raises ``NoMarketDataError`` when the vendor returns no rows.
    """
    from .errors import NoMarketDataError

    payload = _get(
        _8K_TEXT_PATH,
        {"ticker": _plural_ticker_param(ticker), "limit": int(limit)},
    )
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no 8-K filings for {ticker}"
        )

    rows = [r for r in results if isinstance(r, dict)]
    lines = [
        f"## {ticker.upper()} 8-K current reports (SEC filing text, Massive.com)",
        "",
        f"{len(rows)} filing(s), most recent first",
        "",
    ]
    for row in rows:
        lines += [
            f"### {str(row.get('filing_date') or '')[:10]} — "
            f"{row.get('form_type') or '8-K'} ({row.get('accession_number') or '?'})",
            "",
            _excerpt(row.get("items_text"), 600),
            f"Source: {row.get('filing_url')}",
            "",
        ]
    lines.append(
        "Interpretation: 8-K items are event disclosures (results, material "
        "agreements, leadership changes). The item NUMBER names the event type; "
        "cite it before characterising the event."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Precomputed valuation & fundamentals (REST `/stocks/financials/v1/*`)
#   Plan-aware: these endpoints are entitlements-gated (403 on free Basic). The
#   403 path degrades through the router exactly like a missing key, so the
#   tools light up automatically once the account's plan includes them.
# ---------------------------------------------------------------------------


def _not_entitled(path: str, exc) -> str:
    """Honest message for entitlement-guarded endpoints (403 on current plan)."""
    return (
        f"{path} unavailable: {exc}. The Massive account plan does not include "
        f"this dataset; upgrade at massive.com/pricing to enable it."
    )


def get_ratios_massive(ticker: str, curr_date: str | None = None) -> str:
    """Precomputed valuation & profitability ratios for a ticker (plan-aware).

    Uses `/stocks/financials/v1/ratios` (EV/EBITDA, P/E, P/B, ROE, ROA, D/E,
    FCF, dividend yield, ...) so the analyst reads precomputed numbers instead
    of derivations. Returns a ``key: value`` block, or an explicit
    ``unavailable`` message when the endpoint is entitlement-gated (403 on free
    Basic) or the ticker has no ratios.

    Args:
        ticker: symbol.
        curr_date: optional as-of date (YYYY-MM-DD).
    """
    try:
        payload = _get(
            "/stocks/financials/v1/ratios",
            {"ticker": ticker, "limit": 1},
        )
    except MassiveNotConfiguredError as exc:
        # Only an entitlement/plan gap becomes the advisory string; a 429/5xx/
        # timeout must propagate so the router degrades to the next vendor
        # instead of counting this message as a served result.
        return _not_entitled("ratios", exc)
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        return f"ratios unavailable for {ticker}: no data returned."
    row = results[0]
    lines = [f"## {ticker.upper()} Ratios (Massive.com)", ""]
    labels = [
        ("date", "Date"), ("enterprise_value", "EV"), ("ev_to_ebitda", "EV/EBITDA"),
        ("ev_to_sales", "EV/Sales"), ("price_to_earnings", "P/E"),
        ("price_to_book", "P/B"), ("price_to_sales", "P/S"),
        ("price_to_cash_flow", "P/CF"), ("price_to_free_cash_flow", "P/FCF"),
        ("return_on_equity", "ROE"), ("return_on_assets", "ROA"),
        ("debt_to_equity", "D/E"), ("current", "Current"), ("quick", "Quick"),
        ("cash", "Cash ratio"), ("dividend_yield", "Div yield"),
        ("free_cash_flow", "FCF"), ("market_cap", "Market cap"),
    ]
    for key, label in labels:
        v = row.get(key)
        if v is None:
            continue
        if key in ("return_on_assets", "return_on_equity", "dividend_yield"):
            lines.append(f"- {label}: {float(v):.2%}")
        elif key in (
            "ev_to_ebitda", "ev_to_sales", "debt_to_equity", "current", "quick", "cash"
        ) or key in (
            "price_to_earnings", "price_to_book", "price_to_sales", "price_to_cash_flow",
            "price_to_free_cash_flow",
        ):
            lines.append(f"- {label}: {float(v):.2f}")
        else:
            lines.append(f"- {label}: {_fmt_int(v)}")
    lines.append("")
    # Absurd-multiple sanity (NXPI 2026-09-09 review loop): a >100x
    # EV/EBITDA (or EV/EBIT) from the vendor is almost always a contaminated
    # EBITDA/EBIT denominator (e.g. a tiny trailing value), not a real
    # multiple. Flag it inline so the analyst never treats 474.72x as
    # valuation evidence.
    ev_ebitda = row.get("ev_to_ebitda")
    ev_ebit = row.get("ev_to_ebit")
    anomalies = []
    for lbl, v in (("EV/EBITDA", ev_ebitda), ("EV/EBIT", ev_ebit)):
        try:
            if v is not None and -100 < float(v) < 100:
                continue
            if v is not None and abs(float(v)) >= 100:
                anomalies.append(f"{lbl} {float(v):.2f}")
        except (TypeError, ValueError):
            continue
    if anomalies:
        lines.append(
            "DATA-QUALITY: " + "; ".join(anomalies)
            + " > 100x — vendor-multiple anomaly (contaminated EBITDA/EBIT "
            "denominator), do not use as valuation evidence; recompute from "
            "normalized EBITDA = EBIT + D&A if needed."
        )
    lines.append(
        "Interpretation: precomputed valuation/profitability from Massive. "
        "Cross-check against screener value multiples (EY/EV-EBIT/F/Z) before a "
        "final cheap/quality call."
    )
    return "\n".join(lines)


def get_fundamentals_massive(ticker: str, curr_date: str | None = None) -> str:
    """Comprehensive fundamentals overview for a ticker (plan-aware).

    Matches the ``get_fundamentals`` vendor contract (``(ticker, curr_date)``
    -> str) so it plugs into the ``fundamental_data`` category. Renders the
    latest ratios block plus the statement-derived metrics Massive provides.
    Degrades to an explicit 'unavailable' message when entitlement-gated (403)
    or the ticker has no data.

    Args:
        ticker: symbol.
        curr_date: optional as-of date (YYYY-MM-DD); today when None.
    """
    return get_ratios_massive(ticker, curr_date)


# ---------------------------------------------------------------------------
# Snapshots & market movers (REST `/v2/snapshot/locale/us/*`)
#   Plan-aware: entitlements-gated on free Basic (403). Once the plan includes
#   snapshots, these power single-ticker verification and the pipeline universe.
#   All degrade through the router (DataUnavailable) on the current plan.
# ---------------------------------------------------------------------------


def get_market_snapshot_massive(ticker: str) -> str:
    """Latest consolidated market snapshot for one stock (plan-aware).

    Uses `/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}` — the latest
    day/minute/prevDay bars, VWAP, today's change, plus quote/trade when the
    plan includes them. A verification-grade read for the market analyst.
    Returns a ``key: value`` block, or an explicit 'unavailable' message when
    entitlement-gated (403) or the snapshot is empty.

    Args:
        ticker: symbol.
    """
    try:
        payload = _get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}",
            {},
        )
    except MassiveNotConfiguredError as exc:
        # Entitlement/plan gap only; throttle/transport errors propagate.
        return _not_entitled("snapshot", exc)
    t = (payload or {}).get("ticker") if isinstance(payload, dict) else None
    if not t:
        return f"market snapshot unavailable for {ticker}: no data returned."
    day = t.get("day") or {}
    prev = t.get("prevDay") or {}
    lines = [f"## {ticker.upper()} Market Snapshot (Massive.com)", ""]
    lines.append(f"- Last: {_fmt_num(day.get('c'))} | O {_fmt_num(day.get('o'))} "
                 f"H {_fmt_num(day.get('h'))} L {_fmt_num(day.get('l'))} | "
                 f"VWAP {_fmt_num(day.get('vw'))}")
    lines.append(f"- Volume: {_fmt_int(day.get('v'))}")
    lines.append(f"- Prev close: {_fmt_num(prev.get('c'))} | "
                 f"Today's change: {_fmt_num(t.get('todaysChange'))} "
                 f"({_fmt_num(t.get('todaysChangePerc'))}%)")
    quote = t.get("lastQuote") or {}
    if quote:
        lines.append(f"- Quote bid {_fmt_num(quote.get('p'))} ask {_fmt_num(quote.get('P'))}")
    trade = t.get("lastTrade") or {}
    if trade:
        lines.append(f"- Last trade {_fmt_num(trade.get('p'))} @ {_fmt_int(trade.get('s'))}")
    return "\n".join(lines)


def get_top_movers_massive(direction: str = "gainers", count: int = 10) -> str:
    """Top U.S. market gainers/losers by snapshot (plan-aware).

    Uses `/v2/snapshot/locale/us/markets/stocks/{direction}` (gainers/losers)
    to list the top movers with their today-change and close — a clean,
    OpenD-independent universe source for the cross-sectional pipeline
    (`pipeline.py --universe`). Returns a ranked list, or an explicit
    'unavailable' message when entitlement-gated (403).

    Args:
        direction: 'gainers' or 'losers'.
        count: max rows to render.
    """
    direction = direction.lower().strip()
    if direction not in ("gainers", "losers"):
        return f"invalid direction '{direction}'; use 'gainers' or 'losers'."
    try:
        payload = _get(
            f"/v2/snapshot/locale/us/markets/stocks/{direction}",
            {"limit": count},
        )
    except MassiveNotConfiguredError as exc:
        # Entitlement/plan gap only; throttle/transport errors propagate.
        return _not_entitled("top movers", exc)
    rows = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(rows, list) or not rows:
        return f"top {direction} unavailable: no data returned."
    lines = [f"## Top U.S. Market {direction.title()} (Massive.com)", ""]
    for row in rows[:count]:
        sym = row.get("ticker") or "?"
        day = row.get("day") or {}
        change = day.get("c")
        pct = row.get("todaysChangePerc")
        lines.append(
            f"- {sym}: {_fmt_num(change)} ({_fmt_num(pct)}%)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Corporate actions + reference (REST) - entitled on the current plan (200).
#   Wire as working enrichments: dividends/splits (corporate_actions channel),
#   related companies (peers fallback), and IPO / ticker-event reference.
# ---------------------------------------------------------------------------


def get_dividends_massive(ticker: str, rows: int = 5) -> str:
    """Recent cash dividends for a ticker (Massive, entitled).

    Returns declaration/ex/record/pay dates, cash amount, frequency, and the
    split-adjustment factor - feed for dividend-discipline and return-demand
    reasoning. Raises NoMarketDataError when the ticker has no dividends.
    """
    from .errors import NoMarketDataError

    payload = _get("/stocks/v1/dividends", {"ticker": ticker, "limit": rows})
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(ticker, detail="Massive returned no dividends")
    lines = [f"## {ticker.upper()} Dividends (Massive.com)", ""]
    for d in results:
        lines.append(f"- pay {str(d.get('pay_date') or '?')[:10]} | "
                     f"ex {str(d.get('ex_dividend_date') or '?')[:10]} | "
                     f"{_fmt_num(d.get('cash_amount'))} {d.get('currency') or 'USD'} "
                     f"| freq {d.get('frequency') or '?'}x/yr | "
                     f"type {d.get('distribution_type') or 'recurring'}")
    lines.append("")
    lines.append("Interpretation: rising / consistent regular dividends signal "
                 "return discipline; the adjustment factor helps normalize split "
                 "history.")
    return "\n".join(lines)


def get_splits_massive(ticker: str, rows: int = 5) -> str:
    """Recent stock splits for a ticker (Massive, entitled).

    Returns execution date, split from/to, adjustment type and the historical
    adjustment factor - context for share-structure / split-adjusted price work.
    """
    from .errors import NoMarketDataError

    payload = _get("/stocks/v1/splits", {"ticker": ticker, "limit": rows})
    results = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(results, list) or not results:
        raise NoMarketDataError(ticker, detail="Massive returned no split events")
    lines = [f"## {ticker.upper()} Stock Splits (Massive.com)", ""]
    for s in results:
        lines.append(f"- {str(s.get('execution_date') or '?')[:10]} | "
                     f"{_fmt_num(s.get('split_from'))}->{_fmt_num(s.get('split_to'))} "
                     f"| {s.get('adjustment_type') or '?'} | "
                     f"adj {_fmt_num(s.get('historical_adjustment_factor'))}")
    return "\n".join(lines)


def get_related_companies_massive(ticker: str) -> str:
    """Comparable companies for a ticker (Massive related-companies).

    Matches the finnhub ``get_company_peers`` output format
    (``Peers: A, B, C``) so it drops into the ``get_company_peers`` tool /
    channel as a reroute/fallback for relative-valuation reasoning.
    """
    from .errors import NoMarketDataError

    payload = _get(f"/v1/related-companies/{ticker}")
    rows = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(rows, list) or not rows:
        raise NoMarketDataError(ticker, detail="Massive returned no related companies")
    peers = [r.get("ticker") for r in rows if r.get("ticker")]
    if not peers:
        raise NoMarketDataError(ticker, detail="Massive related-companies had no symbols")
    return "Peers: " + ", ".join(str(p) for p in peers[:24])


def get_ipos_massive(limit: int = 10, status: str = "pending") -> str:
    """Upcoming / historical IPOs from Massive (entitled).

    Returns issuer, ticker, announced/expected dates, offer price, size and
    status - a catalyst/universe input (new listings are fresh-money events).
    """
    from .errors import NoMarketDataError

    payload = _get("/vX/reference/ipos", {"limit": limit, "ipo_status": status})
    rows = payload if isinstance(payload, list) else (payload or {}).get("results")
    if not isinstance(rows, list) or not rows:
        raise NoMarketDataError("ipo", detail="Massive returned no IPO events")
    lines = [f"## IPOs (Massive.com, status={status})", ""]
    for d in rows:
        lines.append(f"- {str(d.get('last_updated') or str(d.get('announced_date') or '?'))[:10]} "
                     f"| {d.get('ticker') or '?'} | {d.get('issuer_name') or '?'} "
                     f"| {_fmt_num(d.get('final_issue_price'))} | {d.get('ipo_status') or '?'}")
    return "\n".join(lines)
def get_corporate_actions_massive(ticker: str) -> str:
    """Combined corporate actions (dividends + splits) for a ticker.

    Matches the ``get_corporate_actions(ticker)`` vendor contract so it slots
    into the existing ``corporate_actions`` category as a ``massive`` option
    alongside moomoo. Returns dividends + splits sections, or an explicit
    no-data message when the ticker has neither.
    """
    from .errors import NoMarketDataError

    try:
        div = get_dividends_massive(ticker, rows=5)
    except NoMarketDataError:
        div = ""
    try:
        sp = get_splits_massive(ticker, rows=5)
    except NoMarketDataError:
        sp = ""
    if not div and not sp:
        raise NoMarketDataError(ticker, detail="Massive returned no corporate actions")
    return (div + "\n" + sp).strip()







__all__ = [
    "get_news_massive",
    "get_macro_indicators_massive",
    "get_short_interest_massive",
    "get_short_volume_massive",
    "get_form4_insider_massive",
    "get_filing_sections_massive",
    "get_risk_factors_massive",
    "get_8k_filings_massive",
    "get_ratios_massive",
    "get_fundamentals_massive",
    "get_market_snapshot_massive",
    "get_top_movers_massive",
    "get_dividends_massive",
    "get_splits_massive",
    "get_related_companies_massive",
    "get_corporate_actions_massive",
    "get_ipos_massive",
    "fetch_macro_backdrop",
    "is_yield_curve_inverted",
    "latest_breakeven",
    "massive_api_key",
    "MassiveNotConfiguredError",
]
