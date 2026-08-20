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
                raise MassiveNotConfiguredError(
                    f"Massive returned HTTP {resp.status_code} (bad key or "
                    "plan lacks this dataset)"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise VendorRateLimitError(
                    f"Massive {path} returned HTTP {resp.status_code}"
                )
            if resp.status_code != 200:
                logger.warning("Massive %s: status %s", path, resp.status_code)
                return None
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


__all__ = [
    "get_news_massive",
    "get_macro_indicators_massive",
    "get_short_interest_massive",
    "get_short_volume_massive",
    "get_form4_insider_massive",
    "fetch_macro_backdrop",
    "is_yield_curve_inverted",
    "latest_breakeven",
    "massive_api_key",
    "MassiveNotConfiguredError",
]
