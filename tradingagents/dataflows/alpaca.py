"""Alpaca market-data vendor functions (analysis-only).

Only data/calendar primitives — orders, positions, account, P&L, paper
trading are intentionally never implemented in this project.
"""

from __future__ import annotations

from tradingagents.dataflows.alpaca_common import alpaca_get


def get_bars(
    symbol: str, timeframe: str = "1Day", limit: int = 200, adjustment: str = "raw"
) -> list | None:
    data = alpaca_get(
        f"stocks/{symbol}/bars", {"timeframe": timeframe, "limit": limit, "adjustment": adjustment}
    )
    return data.get("bars") if isinstance(data, dict) else None


def get_bars_batch(symbols: list, timeframe: str = "1Day", limit: int = 10) -> dict | None:
    if not symbols:
        return {}
    data = alpaca_get(
        "stocks/bars", {"symbols": ",".join(symbols), "timeframe": timeframe, "limit": limit}
    )
    return data.get("bars") if isinstance(data, dict) else None


def get_latest_snapshot(symbols: list) -> dict | None:
    if not symbols:
        return {}
    data = alpaca_get("stocks/snapshots", {"symbols": ",".join(symbols)})
    if isinstance(data, dict):
        out = {}
        for sym, info in data.items():
            daily = (info or {}).get("dailyBar") or {}
            out[sym] = {
                "date": daily.get("t"),
                "open": daily.get("o"),
                "high": daily.get("h"),
                "low": daily.get("l"),
                "close": daily.get("c"),
                "volume": daily.get("v"),
            }
        return out
    return None


def get_intraday(symbols: list) -> dict | None:
    """Latest 1m bar + L1 trade/quote per symbol (snapshots endpoint).

    Returns {sym: {price, vwap, volume, ts}}; None when the call fails.
    """
    if not symbols:
        return {}
    data = alpaca_get("stocks/snapshots", {"symbols": ",".join(symbols)})
    if not isinstance(data, dict):
        return None
    out = {}
    for sym, info in data.items():
        if not isinstance(info, dict):
            continue
        trade = info.get("latestTrade") or {}
        quote = info.get("latestQuote") or {}
        minute = info.get("latestBar") or {}
        daily = info.get("dailyBar") or {}
        price = trade.get("px") or quote.get("bp") or quote.get("ap") or daily.get("c")
        vwap = (minute.get("vw") if minute else None) or daily.get("vw")
        volume = (
            minute.get("v")
            if minute is not None and minute.get("v") is not None
            else daily.get("v")
        )
        out[sym] = {
            "price": price,
            "vwap": vwap,
            "volume": volume,
            "ts": trade.get("t") or minute.get("t"),
        }
    return out


def intraday_context(ticker: str) -> str:
    """One-line Alpaca intraday context for a ticker (used in instrument ctx)."""
    try:
        info = (get_intraday([ticker]) or {}).get(ticker) or {}
        price = info.get("price")
        if price is None:
            return ""
        parts = [f"alpaca intraday: price={price}"]
        if info.get("vwap") is not None:
            parts.append(f"vwap={info['vwap']}")
        if info.get("volume") is not None:
            parts.append(f"vol={info['volume']}")
        return " | ".join(parts)
    except Exception:
        return ""


def get_calendar(start: str | None = None, end: str | None = None) -> dict | None:
    params = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    data = alpaca_get("calendar", params, base="https://paper-api.alpaca.markets/v2")
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else None


def get_clock() -> dict | None:
    return alpaca_get("clock", base="https://paper-api.alpaca.markets/v2")


__all__ = [
    "get_bars",
    "get_bars_batch",
    "get_latest_snapshot",
    "get_intraday",
    "get_calendar",
    "get_clock",
]
