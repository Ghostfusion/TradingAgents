"""Momentum market analyst tool (analysis-only).

Wraps the momentum first-pullback + 5-pillar signals so the Market Analyst
can inspect a ticker's momentum setup directly (no execution).
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def get_momentum_scan(ticker: str) -> str:
    """Momentum day-trading signal scan for a single ticker (analysis only).

    Uses daily bars (Alpaca when configured, else the vendor chain) to report
    the 5-pillar pre-filter and the first-pullback pattern with R/R.

    Args:
        ticker: single ticker symbol.

    Returns:
        Compact text: pillars, pullback flags, R/R; or an 'unavailable'
        message when data cannot be fetched.
    """
    data = None
    try:
        from tradingagents.dataflows import alpaca

        bars = alpaca.get_bars(ticker, timeframe="1Day", limit=120)
        if bars:
            data = {
                "closes": [float(b["c"]) for b in bars],
                "highs": [float(b["h"]) for b in bars],
                "lows": [float(b["l"]) for b in bars],
                "volumes": [float(b["v"]) for b in bars],
            }
    except Exception:
        data = None
    if not data or not data["closes"]:
        return "momentum scan unavailable (no daily bars)"
    return _momentum_text(ticker, data)


def _momentum_text(ticker: str, data: dict) -> str:
    from tradingagents.strategies.momentum import (
        first_pullback, pillars, rvol,
    )

    closes = data["closes"]
    vols = data["volumes"]
    rv = rvol(vols)
    pill = pillars(close=closes[-1], day_volume=vols[-1],
                   prev_close=closes[-2] if len(closes) >= 2 else None,
                   day_open=None, rv=rv)
    pull = first_pullback(closes, data["highs"], data["lows"], vols)
    lines = [
        f"momentum scan {ticker}:",
        f"  RVOL(50d)={rv and round(rv, 2)}",
        f"  pillars: rvol={pill['rvol']} high_vol={pill['high_volume']} "
        f"gap={pill['gap']} price_2_20={pill['price_band']} float_ok={pill['float']}",
        f"  first_pullback: surge={pull.get('surge')} retrace_ok={pull.get('retrace_ok')} "
        f"9ema={pull.get('holds_9ema')} vwap={pull.get('holds_vwap')} "
        f"new_high={pull.get('trigger')} rr={pull.get('rr')} stop={pull.get('stop')}",
        f"  setup={'PASS' if pull.get('candidate') else 'NO'}",
    ]
    sep = chr(10)
    return sep.join(lines)