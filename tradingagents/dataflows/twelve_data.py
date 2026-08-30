"""Twelve Data data vendor (free "Basic" tier) — additive market data source.

Free tier: 800 API credits/day, 8 credits/minute; real-time US equities, forex
and crypto quotes, plus historical time-series OHLCV (1 credit per symbol-request),
endpoints: ``/time_series`` (1day interval), ``/quote`` (realtime snapshot),
``/price`` (latest price).

Wired as an additive tail on the ``core_stock_apis`` chain and as a fallback for
the market snapshot / crypto-prices tools. Key-gated:
``TWELVEDATA_API_KEY`` in ``.env``. Raises the typed errors the router
understands so a 401/403/429/empty degrades to the next vendor — never a
fabricated value.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.twelvedata.com"
TIMEOUT = 20
_MAX_RETRIES = 2


def twelve_data_api_key() -> str | None:
    """Twelve Data key from config or environment; None when unset."""
    import os

    try:
        from .config import get_config

        cfg = get_config()
        val = cfg.get("twelve_data_api_key")
        if val:
            return str(val)
    except Exception:  # noqa: BLE001 - config is best-effort
        pass
    return os.environ.get("TWELVEDATA_API_KEY")


def _twelve_get(path: str, params: dict | None = None) -> dict | list | None:
    """Authenticated GET ``BASE/{path}`` with apikey; parsed JSON or None.

    Twelve Data reports errors BOTH as non-200 statuses AND as HTTP 200 with a
    ``{"status": "error", "message": ...}`` body, so both are mapped onto the
    typed error taxonomy.
    """
    key = twelve_data_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "Twelve Data API key is not set. Add TWELVEDATA_API_KEY to .env."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["apikey"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"Twelve Data network error: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("twelve_data", path, detail="non-JSON response") from None

        # Twelve Data signals auth/plan problems with a non-200 status.
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"Twelve Data auth/forbidden (check TWELVEDATA_API_KEY): {resp.status_code}"
            )
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"Twelve Data rate limit (429) on {path}")

        # HTTP 200 with an error body: {"status": "error", "message": "..."}.
        if isinstance(data, dict) and str(data.get("status", "")).lower() == "error":
            msg = str(data.get("message") or data.get("code") or "unspecified error")
            lower = msg.lower()
            if any(tok in lower for tok in ("rate limit", "quota", "exceed", "credits")):
                raise VendorRateLimitError(f"Twelve Data rate limit: {msg}")
            if "apikey" in lower.lower() or "valid api key" in lower or "authentication" in lower.lower():
                raise VendorNotConfiguredError(f"Twelve Data auth: {msg}")
            raise NoMarketDataError("twelve_data", path, detail=msg)

        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"Twelve Data {path}: status {resp.status_code}")
        return data
    return None


def _fmt(v) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def get_stock_data_twelve_data(symbol: str, start_date: str, end_date: str) -> str:
    """Daily OHLCV via Twelve Data's ``/time_series`` (1day), as CSV.

    Matches the yfinance/moomoo/eodhd CSV shape
    (``Date,Open,High,Low,Close,Volume``) with the same header + metadata
    prefix, so the screener's ``_fetch_ohlcv`` parser and the analyst tool
    loops consume it unchanged.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _twelve_get(
        "time_series",
        {
            "symbol": symbol,
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": "5000",
            "order": "asc",
        },
    )
    if not isinstance(data, dict):
        raise NoMarketDataError(symbol, "time_series", detail="no response")
    values = data.get("values") if isinstance(data.get("values"), list) else []
    if not values:
        raise NoMarketDataError(
            symbol, "time_series", detail=f"no rows between {start_date} and {end_date}"
        )
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in values:
        date = str(r.get("datetime") or "")[:10]
        o = _fmt(r.get("open"))
        h = _fmt(r.get("high"))
        lo = _fmt(r.get("low"))
        c = _fmt(r.get("close"))
        v = r.get("volume")
        v = f"{float(v):.0f}" if v is not None else "0"
        lines.append(f"{date},{o},{h},{lo},{c},{v}")
    header = (
        f"# Stock data for {symbol} (Twelve Data) from {start_date} to {end_date}\n"
        f"# Total records: {len(values)}\n"
        f"# Data retrieved via Twelve Data on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + "\n".join(lines)


def get_market_snapshot_twelve_data(ticker: str) -> str:
    """Realtime quote for one ticker via ``/quote`` — a verification-grade price read.

    Twelve Data Basic serves real-time US equities. Renders close/open/high/low,
    change and percent-change, plus the 52-week range when present.
    """
    data = _twelve_get("quote", {"symbol": ticker})
    if not isinstance(data, dict) or not data.get("symbol"):
        raise NoMarketDataError(ticker, "quote", detail="no quote data")
    fields = {
        "ticker": data.get("symbol"),
        "name": data.get("name"),
        "close": data.get("close"),
        "open": data.get("open"),
        "high": data.get("high"),
        "low": data.get("low"),
        "change": data.get("change"),
        "percent_change": data.get("percent_change"),
        "datetime": data.get("datetime"),
        "52-week high": data.get("fifty_two_week_high"),
        "52-week low": data.get("fifty_two_week_low"),
    }
    lines = [f"## Market Snapshot — {ticker} (Twelve Data)", ""]
    for label, value in fields.items():
        if value is not None and str(value) != "":
            lines.append(f"- {label}: {value}")
    if data.get("meta") and isinstance(data.get("meta"), dict):
        s = data["meta"].get("symbol") or data["meta"].get("symbol")
        if s:
            lines.append(f"- symbol: {s}")
    return "\n".join(lines)


def _crypto_code(symbol: str) -> str:
    """Yahoo-style crypto symbol (``BTC-USD``) -> Twelve Data code (``BTC/USD``)."""
    base = (symbol or "").split("-")[0].split("/")[0].upper()
    return f"{base}/USD"


def get_crypto_prices_twelve_data(ticker: str, start_date: str, end_date: str) -> str:
    """Crypto OHLCV via Twelve Data ``/time_series``, as CSV (``BTC-USD`` in).

    Mirrors the tiingo crypto tool shape so the caller can drop it in as a
    fallback unchanged.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    code = _crypto_code(ticker)
    data = _twelve_get(
        "time_series",
        {
            "symbol": code,
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": "5000",
            "order": "asc",
        },
    )
    if not isinstance(data, dict):
        raise NoMarketDataError(ticker, "time_series", detail="no response")
    values = data.get("values") if isinstance(data.get("values"), list) else []
    if not values:
        raise NoMarketDataError(
            ticker, "time_series", detail=f"no crypto rows between {start_date} and {end_date}"
        )
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in values:
        date = str(r.get("datetime") or "")[:10]
        o = _fmt(r.get("open"))
        h = _fmt(r.get("high"))
        lo = _fmt(r.get("low"))
        c = _fmt(r.get("close"))
        v = r.get("volume")
        v = f"{float(v):.4f}" if v is not None else "0"
        lines.append(f"{date},{o},{h},{lo},{c},{v}")
    header = (
        f"# Crypto data for {symbol_for_header(ticker)} (Twelve Data) from "
        f"{start_date} to {end_date}\n"
        f"# Total records: {len(values)}\n\n"
    )
    return header + "\n".join(lines)


def symbol_for_header(ticker: str) -> str:
    return ticker


__all__ = [
    "get_stock_data_twelve_data",
    "get_market_snapshot_twelve_data",
    "get_crypto_prices_twelve_data",
    "twelve_data_api_key",
]
