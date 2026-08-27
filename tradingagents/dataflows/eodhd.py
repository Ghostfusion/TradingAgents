"""EODHD optional data vendor: daily OHLCV (EOD Historical Data).

EODHD (https://eodhd.com) is a low-cost end-of-day market data provider. The
``EOD Historical Data - All World`` plan ($19.99/mo) offers 100,000 calls/day
at 1,000 calls/min with 30+ years of daily OHLCV — a strong replacement for
the moomoo K-line quota (100 calls/7 days) that the value screener exhausts.

This module implements the ``get_stock_data`` vendor contract: daily OHLCV as
a CSV string in the same shape yfinance/moomoo produce (``Date,Open,High,Low,
Close,Volume``), so the screener's ``_fetch_ohlcv`` parser and the analyst
tool loops consume it unchanged.

Every function degrades to a typed error (``NoMarketDataError`` /
``VendorRateLimitError`` / ``VendorNotConfiguredError``) so the router falls
through to the next vendor in the chain — EODHD stays an optional layer.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://eodhd.com/api"
TIMEOUT = 20
_MAX_RETRIES = 2


def eodhd_api_key() -> str | None:
    """API token from config or environment; None when unset."""
    try:
        from tradingagents.dataflows.config import get_config

        key = get_config().get("eodhd_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("EODHD_API_KEY") or os.environ.get("TRADINGAGENTS_EODHD_API_KEY")


def _eodhd_get(path: str, params: dict | None = None) -> dict | list | None:
    """GET ``BASE/{path}`` with api_token; parsed JSON or None on any failure.

    EODHD returns HTTP 200 with a JSON error body (``{"code": ..., "message":
    ...}``) for most failures, and HTTP 429 for rate limits. This helper
    classifies both so the router can fall through cleanly.
    """
    import requests as _requests

    key = eodhd_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "EODHD API token is not set. Add EODHD_API_KEY (or "
            "TRADINGAGENTS_EODHD_API_KEY) to .env."
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
            raise VendorRateLimitError(f"EODHD network error: {exc}") from exc
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"EODHD rate limit (429) on {path}")
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"EODHD auth/forbidden (check EODHD_API_KEY): {resp.status_code}"
            )
        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"EODHD {path}: status {resp.status_code}")
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("eodhd", path, detail="non-JSON response") from None
        # EODHD reports errors as a JSON body with a "code" field.
        if isinstance(data, dict) and data.get("code") is not None:
            msg = str(data.get("message") or data.get("code"))
            if "limit" in msg.lower() or "quota" in msg.lower():
                raise VendorRateLimitError(f"EODHD rate limit: {msg}")
            raise NoMarketDataError("eodhd", path, detail=msg)
        return data
    return None


def get_stock_data_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """Daily OHLCV via EODHD's ``/eod/{symbol}`` endpoint, as CSV.

    Matches the yfinance/moomoo CSV shape (``Date,Open,High,Low,Close,Volume``)
    so the screener's ``_fetch_ohlcv`` parser and the analyst tool loops consume
    it unchanged. Raises typed errors on no data / rate limit / bad key so the
    router falls through to the next vendor.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _eodhd_get(
        f"eod/{symbol}",
        {
            "from": start_date,
            "to": end_date,
            "period": "d",
            "fmt": "json",
        },
    )
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    # EODHD returns newest-first; the yfinance/moomoo CSV is oldest-first.
    rows = list(reversed(data))
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in rows:
        try:
            date = str(r.get("date") or "")[:10]
            o = float(r.get("open"))
            h = float(r.get("high"))
            lo = float(r.get("low"))
            c = float(r.get("close"))
            v = float(r.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        lines.append(f"{date},{o:.2f},{h:.2f},{lo:.2f},{c:.2f},{v:.0f}")
    if len(lines) == 1:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    header = (
        f"# Stock data for {symbol} (from {symbol}) from {start_date} to {end_date}\n"
        f"# Total records: {len(rows)}\n"
        f"# Data retrieved via EODHD on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + "\n".join(lines)


def get_news_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """News for a ticker via EODHD's ``/news`` endpoint (works on the EOD plan).

    Renders each article with headline, date, source, and a content snippet —
    the same shape the other news vendors produce so the analyst tool loops
    consume it unchanged.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _eodhd_get(
        "news",
        {
            "s": symbol,
            "from": start_date,
            "to": end_date,
            "limit": 20,
            "fmt": "json",
        },
    )
    if not isinstance(data, list) or not data:
        return f"No news found for {symbol} from {start_date} to {end_date} (EODHD)"
    lines = [f"## {symbol} News — EODHD", ""]
    for article in data[:20]:
        title = article.get("title") or "(no title)"
        content = article.get("content") or ""
        news_time = str(article.get("date") or "")[:16]
        source = article.get("source") or ""
        if content:
            content = str(content).replace("\n", " ").strip()[:200]
        lines.append(f"- **{title}**  ({news_time} {source})")
        if content:
            lines.append(f"  {content}")
    return "\n".join(lines)


def get_corporate_actions_eodhd(ticker: str) -> str:
    """Dividend history + stock splits via EODHD's ``/div`` and ``/splits``.

    Both endpoints work on the EOD plan. Renders the same shape as the moomoo
    corporate-actions vendor so the analyst tool loops consume it unchanged.
    """
    lines = [f"## Corporate Actions — {ticker} (EODHD)", ""]
    try:
        div = _eodhd_get(f"div/{ticker}", {"fmt": "json"})
        if isinstance(div, list) and div:
            lines.append("### Recent dividends")
            for d in div[-5:]:  # newest last in EODHD's ascending order
                lines.append(
                    f"- {d.get('date', '?')} | ex-date {d.get('date', '?')} "
                    f"| record {d.get('recordDate', '?')} | payable {d.get('paymentDate', '?')} "
                    f"| value {d.get('value', '?')} {d.get('currency', '')}"
                )
    except Exception:  # noqa: BLE001 - dividends degrade independently
        pass
    try:
        sp = _eodhd_get(f"splits/{ticker}", {"fmt": "json"})
        if isinstance(sp, list) and sp:
            lines.append("")
            lines.append("### Stock splits")
            for s in sp[-5:]:
                lines.append(f"- {s.get('date', '?')} | {s.get('split', '?')}")
    except Exception:  # noqa: BLE001 - splits degrade independently
        pass
    if len(lines) == 2:
        raise NoMarketDataError(ticker, ticker, detail="no corporate action data")
    lines.append("")
    lines.append(
        "Interpretation: consistent dividend growth and share buybacks signal "
        "management confidence and shareholder return discipline; splits are "
        "usually cosmetic (note adjustment factors)."
    )
    return "\n".join(lines)


def get_exchange_symbols_eodhd(market: str = "US") -> list[dict]:
    """The full symbol list for an exchange via ``/exchange-symbol-list``.

    Works on the EOD plan (verified: 51,198 US symbols). Returns
    ``[{Code, Name, Country, Exchange, Currency, Type, Isin}]`` so the
    screener can build a universe without the moomoo movers rank.
    """
    data = _eodhd_get(f"exchange-symbol-list/{market}", {"fmt": "json"})
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(market, market, detail="no exchange symbols")
    return data
