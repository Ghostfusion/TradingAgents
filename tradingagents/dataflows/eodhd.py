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
