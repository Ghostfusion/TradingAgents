"""Momentum market analyst tool (analysis-only).

Wraps the momentum first-pullback + 5-pillar signals so the Market Analyst
can inspect a ticker's momentum setup directly (no execution). Phase 1 wiring
fixes the two dead pillars (gap via daily open, low-float via FMP/yfinance);
the intraday block (Phase 4) adds a session-VWAP hold + psychological levels
from 1m bars when Alpaca is available.
"""

from __future__ import annotations

import os

from langchain_core.tools import tool


@tool
def get_momentum_scan(ticker: str) -> str:
    """Momentum day-trading signal scan for a single ticker (analysis only).

    Uses daily bars (Alpaca when configured, else the vendor chain) to report
    the 5-pillar pre-filter and the first-pullback pattern with R/R, plus an
    intraday confirmation block (1m session VWAP hold, psych levels) when
    intraday bars are reachable.

    Args:
        ticker: single ticker symbol.

    Returns:
        Compact text: pillars, pullback flags, R/R, intraday block; or an
        'unavailable' message when data cannot be fetched.
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
                "opens": [float(b["o"]) for b in bars],
            }
    except Exception:
        data = None
    if not data or not data["closes"]:
        return "momentum scan unavailable (no daily bars)"
    return _momentum_text(ticker, data)


def _momentum_text(ticker: str, data: dict) -> str:
    from tradingagents.strategies.momentum import (
        first_pullback,
        intraday_pullback,
        pillars,
        psych_level,
        rvol,
    )

    closes = data["closes"]
    vols = data["volumes"]
    opens = data.get("opens") or []
    rv = rvol(vols)
    day_open = opens[-1] if opens else None
    day_close = closes[-1]
    float_shares = None
    if os.environ.get("TRADINGAGENTS_MOMENTUM_OFFLINE") != "1":
        try:
            from tradingagents.dataflows.float_shares import fetch_float_shares

            float_shares = fetch_float_shares(ticker)
        except Exception:
            float_shares = None
    pill = pillars(close=day_close, day_volume=vols[-1],
                   prev_close=closes[-2] if len(closes) >= 2 else None,
                   day_open=day_open, rv=rv, float_shares=float_shares)
    pull = first_pullback(closes, data["highs"], data["lows"], vols,
                          opens=opens or None)
    lines = [
        f"momentum scan {ticker}:",
        f"  RVOL(50d)={rv and round(rv, 2)}",
        f"  pillars: rvol={pill['rvol']} high_vol={pill['high_volume']} "
        f"gap={pill['gap']} price_2_20={pill['price_band']} float_ok={pill['float']}",
        f"  first_pullback: surge={pull.get('surge')} retrace_ok={pull.get('retrace_ok')} "
        f"9ema={pull.get('holds_9ema')} vwap={pull.get('holds_vwap')} "
        f"volrule={pull.get('volume_ok')} tailok={pull.get('tail_ok')} "
        f"new_high={pull.get('trigger')} rr={pull.get('rr')} stop={pull.get('stop')}",
        f"  setup={'PASS' if pull.get('candidate') else 'NO'}",
    ]
    # Phase-4 intraday confirmation (best effort): 1m bars -> session VWAP
    # hold, first-pullback on the intraday frame, psychological levels.
    try:
        from tradingagents.dataflows import alpaca
        from tradingagents.dataflows.config import get_config

        if os.environ.get("TRADINGAGENTS_MOMENTUM_NO_INTRADAY") != "1" and (
            get_config().get("enable_alpaca")
        ):
            ibars = alpaca.get_bars(ticker, timeframe="1Min", limit=390)
            if ibars:
                iday = intraday_pullback(ibars)
                pl = psych_level(day_close)
                lines.append(
                    f"  intraday: bars={iday.get('bar_count')} "
                    f"session_vwap={iday.get('session_vwap')} "
                    f"holds_vwap={iday.get('holds_session_vwap')} "
                    f"intraday_setup={'PASS' if iday.get('candidate') else 'NO'}"
                )
                if pl.get("above") is not None:
                    lines.append(
                        f"  psych_levels: next={pl['above']} "
                        f"below={pl['below']} dist_pct={pl['dist_pct'] and round(pl['dist_pct'], 2)}"
                    )
    except Exception:
        pass
    sep = chr(10)
    return sep.join(lines)
