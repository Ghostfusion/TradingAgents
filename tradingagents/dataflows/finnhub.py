"""Finnhub data vendor: news, analyst ratings, and earnings calendar.

Finnhub offers a broad free tier (60 req/min, paid plans for higher volume) and
is already used for company + global news. This module also exposes the two
most decision-relevant fundamental/event datasets Finnhub provides beyond news:

  1. ``get_analyst_ratings``  — recommendation trends + price targets
     (a consensus benchmark the fundamental analyst should argue against).
  2. ``get_earnings_calendar`` — upcoming earnings dates (the dominant
     single-day price catalyst), plus the last reported EPS surprise.

Both follow the vendor taxonomy in ``errors.py``: a missing key raises
``FinnhubNotConfiguredError`` so the routing layer treats the vendor as
"unavailable" instead of crashing, and empty results raise ``NoMarketDataError``
so the router emits an honest "no data" signal rather than an empty string.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import finnhub

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError

logger = logging.getLogger(__name__)


class FinnhubNotConfiguredError(VendorNotConfiguredError):
    """Raised when Finnhub is selected but no API key is configured.

    A VendorNotConfiguredError (and thus still a ValueError), so the routing
    layer's "vendor unavailable" handling and existing ValueError callers both
    keep working.
    """


def _client() -> finnhub.Client:
    """Build a Finnhub client, raising a typed error when the key is missing."""
    config = get_config()
    api_key = config.get("finnhub_api_key")
    if not api_key:
        raise FinnhubNotConfiguredError(
            "Finnhub API key is not configured. Set TRADINGAGENTS_FINNHUB_API_KEY "
            "in .env (or finnhub_api_key in config)."
        )
    return finnhub.Client(api_key=api_key)


def _date_window(end_date: str, look_back_days: int) -> tuple[str, str]:
    """Return (start_date, end_date) as yyyy-mm-dd strings."""
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = (end - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    return start, end_date


def get_news_finnhub(ticker, start_date, end_date):
    finnhub_client = _client()

    news = finnhub_client.company_news(ticker, _from=start_date, to=end_date)

    if not news:
        return f"No news found for {ticker} from {start_date} to {end_date}"

    news_str = ""
    for article in news:
        headline = article.get("headline", "No Title")
        summary = article.get("summary", "")
        url = article.get("url", "")

        news_str += f"### {headline}\n"
        if summary:
            news_str += f"{summary}\n"
        if url:
            news_str += f"Link: {url}\n"
        news_str += "\n"

    return f"## {ticker} News from {start_date} to {end_date}:\n\n{news_str}"


def get_global_news_finnhub(curr_date, look_back_days=None, limit=None):
    finnhub_client = _client()

    news = finnhub_client.general_news("general", min_id=0)

    if not news:
        return "No global news found"

    news_str = ""
    for article in news:
        headline = article.get("headline", "No Title")
        summary = article.get("summary", "")
        url = article.get("url", "")

        news_str += f"### {headline}\n"
        if summary:
            news_str += f"{summary}\n"
        if url:
            news_str += f"Link: {url}\n"
        news_str += "\n"

    return f"## Global Market News:\n\n{news_str}"


def get_analyst_ratings_finnhub(ticker: str) -> str:
    """Fetch Finnhub analyst recommendation trends + price targets for a ticker.

    Raises ``NoMarketDataError`` when Finnhub returns no rating data so the
    routing layer can surface an honest "no data" signal instead of an empty
    body (and fall through to another configured vendor for the same tool).
    """
    finnhub_client = _client()

    # recommendation_trends returns [{'buy': N, 'sell': N, 'hold': N,
    # 'strongBuy': N, 'strongSell': N, 'period': 'yyyy-mm-dd'}, ...]
    trends = finnhub_client.recommendation_trends(ticker) or []
    # price_target returns {'symbol', 'lastUpdated', 'targetMean', 'targetHigh',
    # 'targetLow', 'targetMedian', 'numberOfAnalysts', ...}
    target = finnhub_client.price_target(ticker) or {}

    if not trends and not target.get("targetMean"):
        raise NoMarketDataError(
            ticker,
            detail="no analyst rating or price-target data returned",
        )

    lines = [f"## {ticker.upper()} Analyst Ratings (Finnhub)\n"]

    if target.get("numberOfAnalysts") or target.get("targetMean"):
        lines.append("### Price Target Consensus")
        lines.append(f"- Analysts covering: {target.get('numberOfAnalysts', 'n/a')}")
        lines.append(f"- Mean target: {target.get('targetMean', 'n/a')}")
        lines.append(f"- Median target: {target.get('targetMedian', 'n/a')}")
        lines.append(f"- High target: {target.get('targetHigh', 'n/a')}")
        lines.append(f"- Low target: {target.get('targetLow', 'n/a')}")
        if target.get("lastUpdated"):
            lines.append(f"- Last updated: {target.get('lastUpdated')}")
        lines.append("")

    if trends:
        lines.append("### Recommendation Trend (most recent first)")
        lines.append("| Period | Strong Buy | Buy | Hold | Sell | Strong Sell |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in trends[:6]:
            lines.append(
                f"| {row.get('period', 'n/a')} "
                f"| {row.get('strongBuy', 0)} "
                f"| {row.get('buy', 0)} "
                f"| {row.get('hold', 0)} "
                f"| {row.get('sell', 0)} "
                f"| {row.get('strongSell', 0)} |"
            )

    return "\n".join(lines)


def get_earnings_calendar_finnhub(
    ticker: str,
    curr_date: str,
    look_back_days: int | None = None,
) -> str:
    """Fetch upcoming earnings dates + last reported EPS surprise for a ticker.

    ``earnings_calendar`` returns the next earnings date (and, for some
    symbols, the previous quarter's estimate/actual/surprise). Raises
    ``NoMarketDataError`` when no upcoming earnings entry is returned.
    """
    if look_back_days is None:
        look_back_days = 30

    start_date, end_date = _date_window(curr_date, look_back_days)
    finnhub_client = _client()

    earnings = finnhub_client.earnings_calendar(
        _from=start_date, to=end_date, symbol=ticker, international=False
    )

    if not earnings or not isinstance(earnings, dict):
        raise NoMarketDataError(
            ticker,
            detail="no earnings calendar data returned",
        )

    data = earnings.get("earningsCalendar") or []
    if not data:
        raise NoMarketDataError(
            ticker,
            detail="no upcoming earnings in the requested window",
        )

    lines = [f"## {ticker.upper()} Earnings Calendar (Finnhub)"]
    for row in data[:5]:
        lines.append(
            f"- Earnings date: {row.get('date', 'n/a')}"
            f" | EPS estimate: {row.get('epsEstimate', 'n/a')}"
            f" | EPS actual: {row.get('epsActual', 'n/a')}"
            f" | Surprise: {row.get('surprisePercent', 'n/a')}"
            f" | Revenue estimate: {row.get('revenueEstimate', 'n/a')}"
        )
    return "\n".join(lines)


def get_basic_financials_finnhub(symbol: str, curr_date: str | None = None) -> str:
    """Finnhub basic financials metrics (free tier) -> canonical line items.

    A single call to ``company_basic_financials`` provides the fundamental
    metrics the framework's Phase-1 screens need (EPS / revenue / ROE growth
    and levels, margins, payout, current ratio, 52w high). Returns a compact
    ``Key: value`` block the screener's text parser can canonicalize into
    eps_yoy / revenue_yoy / roe / market_cap; raises ``NoMarketDataError``
    when Finnhub reports nothing.
    """
    finnhub_client = _client()
    data = finnhub_client.company_basic_financials(symbol, "all") or {}
    metric = data.get("metric") or {}
    if not metric:
        raise NoMarketDataError(symbol, detail="no basic financial metrics returned")
    out = [
        f"Basic Financials — {symbol.upper()} (Finnhub)",
        "Sector: " + (data.get("sector") or ""),
    ]
    for k, v in metric.items():
        # keep the numbers textual for the canonical parser (it reads 'a: 1.2')
        # Finnhub reports market cap in millions - scale to raw USD so the
        # screener's market-cap floor ($) compares correctly.
        if k == "marketCapitalization" and isinstance(v, (int, float)):
            v = float(v) * 1_000_000.0
        if isinstance(v, (int, float)):
            out.append(f"{k}: {v}")
    return "\n".join(out)


def get_company_peers_finnhub(ticker: str) -> str:
    """Finnhub peers (free tier) -> comma-separated comparable tickers."""
    finnhub_client = _client()
    peers = finnhub_client.company_peers(ticker) or []
    if not peers:
        raise NoMarketDataError(ticker, "no peer data returned")
    return "Peers: " + ", ".join(str(p) for p in peers[:24])


def get_insider_activity_finnhub(ticker: str, months: int = 12) -> str:
    """Finnhub insider sentiment (free tier) -> deterministic numeric read.

    ``stock/insider-sentiment`` requires explicit from/to dates; we use the
    last ``months``. Returns the summed net insider change, the recent-vs-prior
    trend, and the latest month's mspr (the proprietary score) so the analyst
    gets a handful of numbers, not a row dump.
    """
    finnhub_client = _client()

    def _window():
        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=int(months) * 30)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    _from, to = _window()
    data = finnhub_client.stock_insider_sentiment(ticker, _from=_from, to=to) or {}
    rows = data.get("data") or []
    if not rows:
        raise NoMarketDataError(ticker, detail="no insider sentiment in window")
    net = sum(float(r.get("change") or 0.0) for r in rows)
    n = len(rows)
    last = rows[0]
    half = max(1, n // 2)
    recent = sum(float(r.get("change") or 0.0) for r in rows[:half])
    prior = sum(float(r.get("change") or 0.0) for r in rows[half:]) if len(rows) > half else 0.0
    trend = "accelerating" if recent > prior else ("decelerating" if prior > 0 else "flat")
    lines = [
        f"## Insider Sentiment — {ticker.upper()} (Finnhub)",
        f"- Window: last {months} months, {n} periods",
        f"- Net change (sum, shares): {net:,.0f}",
        f"- Recent {half} vs prior {len(rows) - half}: {recent:,.0f} vs {prior:,.0f}",
        f"- Trend: {trend}",
        f"- Last month: {last.get('month')}/{last.get('year')} "
        f"change={last.get('change'):,} mspr={last.get('mspr'):.1f}",
        "",
        "Interpretation: net insider buying (positive) usually precedes "
        "outperformance; net selling is a caution flag, not a sell signal. "
        "Weigh alongside institutional holdings and capital flow.",
    ]
    return "\n".join(lines)


def get_profile_finnhub(ticker: str) -> dict | None:
    """Finnhub company profile2 (free tier) key-gated sector/identity lookup.

    Returns the raw profile dict (sector, industry, marketCap, float, ipo,
    country...) or None when the key is missing / Finnhub errors. This is the
    authoritative second-tier sector source behind FMP in the screener's
    ``--sector-rank`` fallback chain; wrapped in try/except by callers so it
    never raises into a scan.
    """
    try:
        data = _client().company_profile2(symbol=ticker) or {}
        if isinstance(data, dict) and data.get("ticker"):
            # Finnhub returns the GICS sector under ``finnhubIndustry``.
            if "finnhubIndustry" in data and "sector" not in data:
                data["sector"] = data["finnhubIndustry"]
            return data
        return None
    except Exception:  # noqa: BLE001 - optional enrichment never raises
        return None
