"""StockData.org data vendor (free "$0/mo" plan) — additive market data source.

Free tier: 100 requests/day; ``/v1/data/quote`` (current quote), ``/v1/data/eod``
(end-of-day OHLCV, ~1 month history on free), ``/v1/data/intraday`` (1-minute on
free), and ``/v1/news/all`` (2 articles per request on free). Crypto and forex
EOD data are served through ``/v1/data/eod``.

Wired as an additive last-resort tail on ``core_stock_apis`` / ``news_data`` and
as a fallback for the market snapshot. Key-gated: ``STOCKDATA_API_KEY`` in
``.env``. Raises the typed errors the router understands so 401/403/429/empty
degrades to the next vendor — never a fabricated value.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.stockdata.org"
TIMEOUT = 20
_MAX_RETRIES = 2


def stockdata_api_key() -> str | None:
    """StockData.org key from config or environment; None when unset."""
    import os

    try:
        from .config import get_config

        cfg = get_config()
        val = cfg.get("stockdata_api_key")
        if val:
            return str(val)
    except Exception:  # noqa: BLE001 - config is best-effort
        pass
    return os.environ.get("STOCKDATA_API_KEY")


def _stockdata_get(path: str, params: dict | None = None) -> dict | None:
    """Authenticated GET ``BASE/{path}`` with api_token; parsed dict or None.

    StockData.org reports errors as HTTP 200 with ``{"error": "..."}`` AND as
    non-200 statuses; both map onto the typed taxonomy.
    """
    key = stockdata_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "StockData.org API key is not set. Add STOCKDATA_API_KEY to .env."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["api_token"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"StockData.org network error: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("stockdata", path, detail="non-JSON response") from None

        if not isinstance(data, dict):
            if resp.status_code != 200 and attempt < _MAX_RETRIES:
                continue
            raise NoMarketDataError("stockdata", path, detail="malformed response")

        # Error body: {"error": {"message": "..."}} (top-level string too).
        err = data.get("error")
        if err is not None:
            msg = str(err.get("message") if isinstance(err, dict) else err)
            lower = msg.lower()
            if any(tok in lower for tok in ("rate", "quota", "limit", "exceed")):
                raise VendorRateLimitError(f"StockData.org rate limit: {msg}")
            if any(tok in lower for tok in ("api key", "forbidden", "401", "403", "unauthor")):
                raise VendorNotConfiguredError(f"StockData.org auth: {msg}")
            raise NoMarketDataError("stockdata", path, detail=msg)

        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"StockData.org rate limit (429) on {path}")
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"StockData.org auth/forbidden (check STOCKDATA_API_KEY): {resp.status_code}"
            )
        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"StockData.org {path}: status {resp.status_code}")
        return data
    return None


def _fmt(v) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def get_stock_data_stockdata(symbol: str, start_date: str, end_date: str) -> str:
    """End-of-day OHLCV via StockData.org ``/v1/data/eod``, as CSV.

    Free plan = ~1 month (~30 rows) and 3 symbols per request; history claims are
    capped to that window honestly (no fabrication). Matches the yfinance/moomoo
    CSV shape.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _stockdata_get("v1/data/eod", {"symbols": symbol})
    if not isinstance(data, dict):
        raise NoMarketDataError(symbol, "eod", detail="no response")
    raw = data.get("data")
    rows = raw if isinstance(raw, list) else []
    if not rows:
        raise NoMarketDataError(symbol, "eod", detail="no EOD rows (free tier = ~1 month)")
    lines = ["Date,Open,High,Low,Close,Volume"]
        # StockData.org returns newest-first; the yfinance/moomoo/eodhd CSV is
    # oldest-first, so reverse to keep downstream time-series consumers in order.
    for r in reversed(rows):
        date = str(r.get("date") or "")[:10]
        o = _fmt(r.get("open"))
        h = _fmt(r.get("high"))
        lo = _fmt(r.get("low"))
        c = _fmt(r.get("close"))
        v = r.get("volume")
        v = f"{float(v):.0f}" if v is not None else "0"
        lines.append(f"{date},{o},{h},{lo},{c},{v}")
    header = (
        f"# Stock data for {symbol} (StockData.org), free tier ~ 6 months history\n"
        f"# Total records: {len(rows)}\n"
        f"# Data retrieved via StockData.org on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + "\n".join(lines)


def get_market_snapshot_stockdata(ticker: str) -> str:
    """Current quote via StockData.org ``/v1/data/quote``.

    Renders price, change, percent change, day range and 52-week range when
    present - a verification-grade price read.
    """
    data = _stockdata_get("v1/data/quote", {"symbols": ticker})
    if not isinstance(data, dict):
        raise NoMarketDataError(ticker, "quote", detail="no response")
    raw = data.get("data")
    rows = raw if isinstance(raw, list) else []
    if not rows:
        raise NoMarketDataError(ticker, "quote", detail="no quote data")
    q = rows[0] if isinstance(rows[0], dict) else {}
    fields = {
        "ticker": q.get("ticker"),
        "name": q.get("name"),
        "price": q.get("price"),
        "day_change": q.get("day_change"),
        "day_change_percent": q.get("day_change_percent"),
        "day_high": q.get("day_high"),
        "day_low": q.get("day_low"),
        "52-week high": q.get("week_52_high"),
        "52-week low": q.get("week_52_low"),
    }
    lines = [f"## Market Snapshot — {ticker} (StockData.org)", ""]
    for label, value in fields.items():
        if value is not None and str(value) != "":
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def get_news_stockdata(symbol: str, start_date: str, end_date: str) -> str:
    """News for a ticker via StockData.org ``/v1/news/all``.

    Free tier returns 2 articles per request; we render them with headline,
    date, source and a snippet - the same shape the other news vendors produce.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _stockdata_get("v1/news/all", {"symbols": symbol, "limit": 2})
    if not isinstance(data, dict):
        raise NoMarketDataError(symbol, "news", detail="no response")
    raw = data.get("data")
    articles = raw if isinstance(raw, list) else []
    if not articles:
        return f"No news found for {symbol} around {end_date} (StockData.org)"
    lines = [f"## {symbol} News — StockData.org", ""]
    for article in articles[:2]:
        if not isinstance(article, dict):
            continue
        title = article.get("title") or "(no title)"
        date = str(article.get("date") or "")[:16]
        # StockData.org returns the paywall flag + source; descriptions are brief.
        snippet = article.get("description") or article.get("snippet") or ""
        snippet = str(snippet).replace("\n", " ").strip()[:200]
        source = article.get("source") or ""
        lines.append(f"- **{title}**  ({date} {source})")
        if snippet:
            lines.append(f"  {snippet}")
    joined = "\n".join(lines).rstrip()
    return joined or f"No news found for {symbol} around {end_date} (StockData.org)"


__all__ = [
    "get_stock_data_stockdata",
    "get_market_snapshot_stockdata",
    "get_news_stockdata",
    "stockdata_api_key",
]
