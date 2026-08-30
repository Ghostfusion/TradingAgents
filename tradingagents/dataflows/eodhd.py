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
        # EODHD reports errors as a JSON body with a "code" field AND a
        # "message" field (e.g. {"code": 404, "message": "Not found"}). A
        # dict with only a "code" field (no "message") is a normal data
        # payload — e.g. /api/real-time/{ticker} returns {"code": "AAPL.US",
        # "close": ...} where "code" is the ticker symbol, not an error.
        if isinstance(data, dict) and data.get("code") is not None and data.get("message") is not None:
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


def _sentiment_points_eodhd(
    symbol: str, start_date: str, end_date: str
) -> list[dict] | None:
    """Daily aggregated sentiment series from EODHD ``/sentiments``.

    Returns ``[{"date", "score", "n"}]`` with ``score`` centered to [-1, 1]
    (EODHD ``normalized`` is 0..1), or None when the ticker has no rows.
    """
    data = _eodhd_get(
        "sentiments",
        {
            "s": symbol,
            "from": start_date,
            "to": end_date,
            "fmt": "json",
        },
    )
    if not isinstance(data, dict) or not data:
        raise NoMarketDataError(
            symbol, "sentiments",
            detail=f"no sentiment rows between {start_date} and {end_date}",
        )
    want = str(symbol).upper()
    key = want if want in data else None
    if key is None:
        for k in data:
            if str(k).upper().startswith(want) or want.startswith(str(k).upper().split(".")[0]):
                key = k
                break
    if key is None:
        raise NoMarketDataError(
            symbol, "sentiments", detail=f"no rows for {symbol} in response"
        )
    rows = data[key] or []
    out = []
    for r in rows:
        try:
            score = (float(r.get("normalized")) - 0.5) * 2.0
        except (TypeError, ValueError):
            continue
        if not -1.0 <= score <= 1.0:
            continue
        try:
            n = int(r.get("count") or 0)
        except (TypeError, ValueError):
            n = 0
        out.append({"date": str(r.get("date")), "score": score, "n": n})
    return sorted(out, key=lambda d: d["date"]) or None


def get_news_sentiment_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """Daily news-sentiment series for a ticker via EODHD ``/sentiments``.

    Renders the daily mean (centered to [-1,1]) + 7-day SMA + latest
    innovation + article count — the news-sentiment factor's computed series.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    points = _sentiment_points_eodhd(symbol, start_date, end_date)
    if not points:
        return f"News sentiment unavailable for {symbol} (EODHD)"
    from tradingagents.strategies.sentiment import daily_sentiment_sma

    series = daily_sentiment_sma(points, window=7) or [
        {"date": p["date"], "score": p["score"], "sma_7d": None, "innovation": None, "n": p["n"]}
        for p in points
    ]
    lines = [f"## {symbol} Daily News Sentiment — EODHD (scale -1..1)", ""]
    lines.append("| date | score | sma_7d | innovation | articles |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in series:
        sc = f"{r['score']:+.2f}" if r["score"] is not None else "n/a"
        sma = f"{r['sma_7d']:+.2f}" if r["sma_7d"] is not None else "n/a"
        inn = f"{r['innovation']:+.2f}" if r["innovation"] is not None else "n/a"
        lines.append(f"| {r['date']} | {sc} | {sma} | {inn} | {r['n']} |")
    latest = series[-1]
    tail = [
        "",
        f"- latest score {latest['score'] if latest['score'] is not None else 'n/a'}, "
        f"7d SMA {latest['sma_7d'] if latest['sma_7d'] is not None else 'n/a'}",
    ]
    if latest.get("innovation") is not None:
        tail.append(f"- latest sentiment innovation {latest['innovation']:+.2f}")
    return "\n".join(lines + tail)


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


def get_exchange_symbols_text_eodhd(market: str = "US") -> str:
    """String-rendered symbol list for the routed ``get_exchange_symbols``
    vendor path (the vendor contract requires a string; the raw list form is
    kept for the screener's direct import)."""
    data = get_exchange_symbols_eodhd(market)
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append(
            "{Code}\t{Name}\t{Country}\t{Exchange}\t{Currency}\t{Type}".format(**item)
        )
    if not rows:
        raise NoMarketDataError(market, market, detail="no exchange symbols")
    return "{Code}\tName\tCountry\tExchange\tCurrency\tType\n" + "\n".join(rows)


def get_market_snapshot_eodhd(ticker: str) -> str:
    """Latest live (15-20 min delayed) OHLCV + change for one ticker.

    Uses ``/api/real-time/{ticker}`` — works on the EOD plan (verified live:
    AAPL returns open/high/low/close/volume/previousClose/change/change_p).
    This is the EODHD replacement for the Massive snapshot (403 on the free
    plan): the market analyst's "latest verified bar" + gap read. Renders the
    same key:value block shape as the Massive snapshot so the tool output is
    interchangeable.
    """
    data = _eodhd_get(f"real-time/{ticker}", {"fmt": "json"})
    if not isinstance(data, dict) or not data.get("code"):
        raise NoMarketDataError(ticker, ticker, detail="no real-time data")
    lines = [f"## {ticker.upper()} Market Snapshot (EODHD)", ""]
    lines.append(
        f"- Last: {data.get('close')} | O {data.get('open')} "
        f"H {data.get('high')} L {data.get('low')} | Volume {data.get('volume')}"
    )
    lines.append(
        f"- Prev close: {data.get('previousClose')} | "
        f"Today's change: {data.get('change')} ({data.get('change_p')}%)"
    )
    return "\n".join(lines)


def get_top_movers_eodhd(direction: str = "gainers", count: int = 10) -> str:
    """Top U.S. market gainers/losers from the bulk real-time feed.

    Uses ``/api/real-time/{ticker}?ex=US`` — one call returns ~18k US stocks
    with live OHLCV + change_p (verified live on the EOD plan). Sorts by
    change_p (desc = gainers, asc = losers) and renders the top ``count``.
    This is the EODHD replacement for the Massive top-movers endpoint (403 on
    the free plan) — a clean, OpenD-independent universe source.
    """
    direction = str(direction).strip().lower()
    if direction not in ("gainers", "losers"):
        return f"invalid direction '{direction}'; use 'gainers' or 'losers'."
    data = _eodhd_get("real-time/US.US", {"ex": "US", "fmt": "json"})
    if not isinstance(data, list) or not data:
        raise NoMarketDataError("US", "US", detail="no real-time bulk data")
    rows = [r for r in data if r.get("change_p") is not None]
    rows.sort(key=lambda r: float(r["change_p"]), reverse=(direction == "gainers"))
    lines = [f"## Top U.S. Market {direction.title()} (EODHD)", ""]
    for row in rows[:count]:
        sym = (row.get("code") or "?").split(".")[0]
        lines.append(f"- {sym}: {row.get('close')} ({row.get('change_p')}%)")
    return "\n".join(lines)
