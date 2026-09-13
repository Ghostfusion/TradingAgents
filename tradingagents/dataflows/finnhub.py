"""Finnhub data vendor: news, analyst ratings, and earnings calendar.

Finnhub offers a broad free tier (60 req/min, paid plans for higher volume) and
is already used for company + global news. This module also exposes the two
most decision-relevant fundamental/event datasets Finnhub provides beyond news:

  1. ``get_analyst_ratings``  — recommendation trends + price targets
     (a consensus benchmark the fundamental analyst should argue against).
  2. ``get_earnings_calendar`` — upcoming earnings dates (the dominant
     single-day price catalyst) over a forward window from the as-of date,
     plus any reported EPS figures the vendor returns for it.

Both follow the vendor taxonomy in ``errors.py``: a missing key raises
``FinnhubNotConfiguredError`` so the routing layer treats the vendor as
"unavailable" instead of crashing, and empty results raise ``NoMarketDataError``
so the router emits an honest "no data" signal rather than an empty string.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import finnhub

from .config import get_config
from .date_window import in_window
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


def _article_published(article) -> datetime | None:
    """Finnhub article publish time: the ``datetime`` epoch (seconds) as UTC."""
    ts = article.get("datetime") if isinstance(article, dict) else None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


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
    """Global market news trimmed to ``[curr_date - look_back_days, curr_date]``.

    Finnhub's ``general_news`` feed is live-only, so a historical/backtest run
    must filter it or it sees today's headlines (look-ahead). ``look_back_days``
    and ``limit`` default to the configured ``global_news_lookback_days`` /
    ``global_news_article_limit``, the same defaults the yfinance and
    alpha_vantage siblings use.
    """
    config = get_config()
    if look_back_days is None:
        look_back_days = config["global_news_lookback_days"]
    if limit is None:
        limit = config["global_news_article_limit"]

    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=int(look_back_days))

    finnhub_client = _client()
    news = finnhub_client.general_news("general", min_id=0) or []

    kept = []
    for article in news:
        if len(kept) >= int(limit):
            break
        if not isinstance(article, dict):
            continue
        if in_window(_article_published(article), start_dt, end_dt):
            kept.append(article)

    if not kept:
        return f"No global news found between {start_dt:%Y-%m-%d} and {curr_date}"

    news_str = ""
    for article in kept:
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
    """Fetch upcoming earnings dates for a ticker (forward-looking window).

    ``earnings_calendar`` is queried over ``[curr_date, curr_date +
    look_back_days]``: the tool's purpose is the next scheduled catalyst, so a
    backward window could never return it. Any EPS estimate/actual/surprise
    the vendor reports for those dates is rendered too. Raises
    ``NoMarketDataError`` when no earnings entry is returned in the window.
    """
    if look_back_days is None:
        look_back_days = 30

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    end_date = (curr_dt + timedelta(days=int(look_back_days))).strftime("%Y-%m-%d")
    finnhub_client = _client()

    earnings = finnhub_client.earnings_calendar(
        _from=curr_date, to=end_date, symbol=ticker, international=False
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
        date_txt = str(row.get("date", "n/a"))
        days_txt = ""
        try:
            days_out = (datetime.strptime(date_txt, "%Y-%m-%d") - curr_dt).days
            if days_out >= 0:
                # The countdown a report quotes instead of computing it.
                days_txt = f" | Days out: {days_out}"
        except (TypeError, ValueError):
            pass
        lines.append(
            f"- Earnings date: {date_txt}"
            f" | EPS estimate: {row.get('epsEstimate', 'n/a')}"
            f" | EPS actual: {row.get('epsActual', 'n/a')}"
            f" | Surprise: {row.get('surprisePercent', 'n/a')}"
            f" | Revenue estimate: {row.get('revenueEstimate', 'n/a')}"
            f"{days_txt}"
        )
    return "\n".join(lines)


# Finnhub encodes each metric's reporting basis in its key suffix
# (``roaTTM``, ``netProfitMarginAnnual``, ``currentRatioQuarterly``). The
# mapping is data-driven and total: a key whose suffix isn't recognised is
# labelled basis-unknown rather than guessed at, so a vendor TTM value can no
# longer read like a period-agnostic one (D3: the unlabelled ``roaTTM``
# 81.41% sat next to a computed 58.06%).
_BASIS_BY_SUFFIX = (
    ("TTM", "TTM, Finnhub"),
    ("Annual", "annual, Finnhub"),
    ("Quarterly", "quarterly, Finnhub"),
)
_UNKNOWN_BASIS = "vendor, basis unknown"

# Relative divergence above which the vendor's own ROA inputs win over the
# emitted ``roaTTM`` row.
_ROA_REL_TOLERANCE = 0.20


def _metric_basis(key: str) -> str:
    """Basis + source label for a Finnhub metric key (``_BASIS_BY_SUFFIX``)."""
    for suffix, label in _BASIS_BY_SUFFIX:
        if key.endswith(suffix):
            return label
    return _UNKNOWN_BASIS


def _is_number(v) -> bool:
    """True for a real int/float metric value (``bool`` excluded)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _roa_reconcile_note(metric: dict) -> str:
    """Cross-check Finnhub's ``roaTTM`` against the payload's own inputs.

    ROA = TTM net margin x TTM asset turnover. Finnhub ships both inputs
    alongside ``roaTTM``, so when the vendor's own product disagrees with the
    emitted ROA by more than ``_ROA_REL_TOLERANCE`` relative, return an
    advisory ``# NOTE:`` correction naming both numbers and the implied value.
    Mirrors ``y_finance._net_debt_note``: returns "" when an input is absent
    or the figures agree, and never raises.
    """
    roa = metric.get("roaTTM")
    margin = metric.get("netProfitMarginTTM")
    if not _is_number(roa) or not _is_number(margin):
        return ""
    turnover = metric.get("assetTurnoverTTM")
    if not _is_number(turnover):
        turnover = metric.get("totalAssetTurnoverTTM")
    if not _is_number(turnover):
        # No turnover row: derive it from revenue / total assets when shipped.
        revenue = metric.get("revenueTTM")
        if not _is_number(revenue):
            revenue = metric.get("totalRevenueTTM")
        assets = metric.get("totalAssetsTTM")
        if not _is_number(assets):
            assets = metric.get("totalAssets")
        if not _is_number(revenue) or not _is_number(assets) or assets == 0:
            return ""
        turnover = revenue / assets
    implied = margin * turnover
    if roa == 0 or abs(implied - roa) <= _ROA_REL_TOLERANCE * abs(roa):
        return ""
    return (
        f"\n# NOTE: vendor 'ROA TTM' ({roa:.2f}) disagrees with its own TTM "
        f"inputs: TTM net margin ({margin:.2f}) x TTM asset turnover "
        f"({turnover:.4f}) implies {implied:.2f}. Quote the implied figure, "
        f"not the vendor ROA row."
    )


def get_basic_financials_finnhub(symbol: str, curr_date: str | None = None) -> str:
    """Finnhub basic financials metrics (free tier) -> canonical line items.

    A single call to ``company_basic_financials`` provides the fundamental
    metrics the framework's Phase-1 screens need (EPS / revenue / ROE growth
    and levels, margins, payout, current ratio, 52w high). Returns a compact
    ``Key: value`` block the screener's text parser can canonicalize into
    eps_yoy / revenue_yoy / roe / market_cap; raises ``NoMarketDataError``
    when Finnhub reports nothing. Each metric line carries its own basis and
    source (``roaTTM (TTM, Finnhub): ...``) so a vendor value is never
    mistaken for a computed, period-agnostic one.
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
        # keep the numbers textual for the canonical parser (it reads the
        # value after the last ':'; its row matcher matches the key substring,
        # so the added basis label does not break eps_yoy/revenue_yoy/roe/mcap)
        # Finnhub reports market cap in millions - scale to raw USD so the
        # screener's market-cap floor ($) compares correctly.
        if k == "marketCapitalization" and isinstance(v, (int, float)):
            v = float(v) * 1_000_000.0
        if isinstance(v, (int, float)):
            out.append(f"{k} ({_metric_basis(k)}): {v}")
    return "\n".join(out) + _roa_reconcile_note(metric)


# Finnhub returns malformed/foreign-listing peer ids for some US names
# (SNDK 2026-09-10: "3NDK", "3QP", "QPIQI", "INFQ" in the peer-review row).
# Map known aliases back to the canonical US ticker and drop duplicates.
_PEER_ALIASES = {
    "3NDK": "SNDK", "3WDC": "WDC", "3QP": "HPQ", "3HPE": "HPE",
    "3SMCI": "SMCI", "3IONQ": "IONQ", "3NTAP": "NTAP",
    "QPIQI": "GPIQI", "QINFQ": "INFQ",
}


def _normalize_peer(p) -> str:
    p = str(p).strip().upper()
    if not p:
        return ""
    if p in _PEER_ALIASES:
        return _PEER_ALIASES[p]
    # Numeric-prefix junk like "3NDK" (a non-US listing code) -> letters only
    # when that yields a clean ticker we already emit.
    if len(p) > 1 and p[0].isdigit() and p[1:].isalnum():
        core = p[1:]
        if core.isalpha():
            return core
    return p


def get_company_peers_finnhub(ticker: str) -> str:
    """Finnhub peers (comparable tickers) -> comma-separated canonical tickers."""
    finnhub_client = _client()
    peers = finnhub_client.company_peers(ticker) or []
    if not peers:
        raise NoMarketDataError(ticker, detail="no peer data returned")
    canon, seen = [], set()
    for p in peers[:24]:
        n = _normalize_peer(p)
        if not n or n == str(ticker).strip().upper() or n in seen:
            continue
        seen.add(n)
        canon.append(n)
    if not canon:
        canon = [str(p) for p in peers[:24]]
    return "Peers: " + ", ".join(canon)


_INSIDER_WINDOW_MONTHS = 12


def get_insider_activity_finnhub(symbol: str, curr_date: str | None = None) -> str:
    """Finnhub insider sentiment (free tier) -> deterministic numeric read.

    ``stock/insider-sentiment`` requires explicit from/to dates. ``curr_date``
    (yyyy-mm-dd) is the analysis as-of date and ends the window, so a
    historical/backtest run never sees insider activity published after it.
    ``curr_date=None`` falls back to the wall clock for live callers that have
    no as-of date - a backtest MUST pass ``curr_date``.

    Returns the summed net insider change, the recent-vs-prior trend, and the
    latest month's mspr (the proprietary score) so the analyst gets a handful
    of numbers, not a row dump.
    """
    finnhub_client = _client()

    end = datetime.strptime(curr_date, "%Y-%m-%d") if curr_date else datetime.now()
    start = end - timedelta(days=_INSIDER_WINDOW_MONTHS * 30)
    _from, to = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    data = finnhub_client.stock_insider_sentiment(symbol, _from=_from, to=to) or {}
    rows = data.get("data") or []
    if not rows:
        raise NoMarketDataError(symbol, detail="no insider sentiment in window")
    net = sum(float(r.get("change") or 0.0) for r in rows)
    n = len(rows)
    last = rows[0]
    half = max(1, n // 2)
    recent = sum(float(r.get("change") or 0.0) for r in rows[:half])
    prior = sum(float(r.get("change") or 0.0) for r in rows[half:]) if len(rows) > half else 0.0
    trend = "accelerating" if recent > prior else ("decelerating" if prior > 0 else "flat")
    lines = [
        f"## Insider Sentiment — {symbol.upper()} (Finnhub)",
        f"- Window: last {_INSIDER_WINDOW_MONTHS} months, {n} periods",
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
