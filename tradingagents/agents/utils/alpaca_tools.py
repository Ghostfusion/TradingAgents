"""Alpaca analyst tool (analysis-only): live intraday snapshot for agents.

One batch call to the Alpaca snapshots endpoint; degrades to a clear
'unavailable' message when keys are missing or the call fails.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def get_market_snapshot_alpaca(tickers: str) -> str:
    """Live Alpaca 1-minute snapshot (last price, VWAP, volume) for tickers.

    Args:
        tickers: comma-separated ticker symbols (e.g. "AAPL,MSFT").

    Returns:
        Compact per-symbol lines with price, 1m VWAP and 1m volume, or a
        clear 'unavailable' message when Alpaca is not configured.
    """
    try:
        from tradingagents.dataflows.alpaca import get_intraday
    except Exception:
        return "alpaca intraday unavailable (client not installed)"
    symbols = [t.strip().upper() for t in (tickers or "").split(",") if t.strip()]
    if not symbols:
        return "no tickers provided"
    data = get_intraday(symbols)
    if not data:
        return "alpaca intraday unavailable (no keys or request failed)"
    lines = []
    for sym in symbols:
        info = data.get(sym) or {}
        price = info.get("price")
        vwap = info.get("vwap")
        volume = info.get("volume")
        if price is None:
            lines.append(f"{sym}: no intraday data")
            continue
        parts = [f"{sym}: price={price}"]
        if vwap is not None:
            parts.append(f"vwap={vwap}")
        if volume is not None:
            parts.append(f"vol={volume}")
        lines.append(" | ".join(parts))
    sep = chr(10)
    return sep.join(lines) if lines else "alpaca intraday unavailable"
