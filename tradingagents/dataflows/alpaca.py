"""Alpaca market-data vendor functions (analysis-only).

Only data/calendar primitives — orders, positions, account, P&L, paper
trading are intentionally never implemented in this project.
"""

from __future__ import annotations

from tradingagents.dataflows.alpaca_common import alpaca_get


def get_bars(symbol: str, timeframe: str = "1Day", limit: int = 200,
           adjustment: str = "raw") -> "list | None":
    data = alpaca_get(f"stocks/{symbol}/bars",
                      {"timeframe": timeframe, "limit": limit,
                       "adjustment": adjustment})
    return data.get("bars") if isinstance(data, dict) else None


def get_bars_batch(symbols: list, timeframe: str = "1Day",
                 limit: int = 10) -> "dict | None":
    if not symbols:
        return {}
    data = alpaca_get("stocks/bars",
                  {"symbols": ",".join(symbols),
                   "timeframe": timeframe, "limit": limit})
    return data.get("bars") if isinstance(data, dict) else None


def get_latest_snapshot(symbols: list) -> "dict | None":
    if not symbols:
        return {}
    data = alpaca_get("stocks/snapshots",
                          {"symbols": ",".join(symbols)})
    if isinstance(data, dict):
        out = {}
        for sym, info in data.items():
            daily = (info or {}).get("dailyBar") or {}
            out[sym] = {"date": daily.get("t"), "open": daily.get("o"),
                        "high": daily.get("h"), "low": daily.get("l"),
                        "close": daily.get("c"), "volume": daily.get("v")}
        return out
    return None


def get_calendar(start: "str | None" = None,
                 end: "str | None" = None) -> "dict | None":
    params = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    data = alpaca_get("calendar", params,
               base="https://paper-api.alpaca.markets/v2")
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else None


def get_clock() -> "dict | None":
    return alpaca_get("clock", base="https://paper-api.alpaca.markets/v2")


__all__ = ["get_bars", "get_bars_batch", "get_latest_snapshot",
           "latest_snapshot", "get_calendar", "get_clock"]