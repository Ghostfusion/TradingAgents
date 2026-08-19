"""Momentum day-trading signals (analysis-only; no execution).

Implements the 5-pillar momentum pre-filter + first-pullback pattern +
session risk flags from Strategies/momentum_day_trading.md. Pure, offline-
testable functions.
"""

from __future__ import annotations


def rvol(volumes: list, window: int = 50) -> "float | None":
    """Relative volume: today's volume vs the trailing window average."""
    if not volumes or len(volumes) < 2:
        return None
    hist = volumes[-window - 1 : -1]
    if not hist:
        return None
    base = sum(hist) / len(hist)
    if base <= 0:
        return None
    return volumes[-1] / base


def ema9(closes: list) -> "float | None":
    if not closes:
        return None
    k = 2.0 / 10.0
    n = min(9, len(closes))
    ema = sum(closes[:n]) / n
    for v in closes[n:]:
        ema = v * k + ema * (1 - k)
    return ema


def vwap(closes: list, volumes: list) -> "float | None":
    n = min(len(closes), len(volumes))
    if n == 0:
        return None
    value = volume = 0.0
    for i in range(n):
        volume += volumes[i]
        value += closes[i] * volumes[i]
    return value / volume if volume else None


def pillars(close=None, day_volume=None, prev_close=None, day_open=None,
            rv: "float | None" = None, price_lo: float = 2.0,
            price_hi: float = 20.0, float_shares: "float | None" = None) -> dict:
    """The five pillars of the momentum pre-filter (varargs -> clean call)."""
    res = {}
    res["rvol"] = bool(rv is not None and rv >= 2.0)
    res["high_volume"] = bool(day_volume is not None and day_volume >= 1_000_000)
    gap = None
    if prev_close and day_open is not None and prev_close > 0:
        gap = day_open / prev_close - 1.0
    res["gap"] = bool(gap is not None and gap >= 0.02)
    res["price_band"] = bool(close is not None and price_lo <= close <= price_hi)
    res["float"] = None if float_shares is None else bool(float_shares <= 20e6)
    return res


def first_pullback(closes: list, highs: list, lows: list, volumes: list,
                   window: int = 6) -> dict:
    """First-pullback pattern: surge, <=50% retrace, 9 EMA/VWAP hold, new-high."""
    if len(closes) < window + 4 or not highs or not lows or not volumes:
        return {"candidate": False}
    c = closes[-1]
    ema = ema9(closes)
    vw = vwap(closes, volumes)
    segment = closes[-window:]
    surge_ok = segment[0] and segment[-1] / segment[0] - 1.0 >= 0.03
    recent_high = max(highs[-window - 1 : -1]) if len(highs) > window else max(highs)
    near = lows[-window - 1 : -1]
    low_start = min(near) if near else 0.0
    pull_low = min(lows[-window:])
    retrace = (recent_high - pull_low) / max(recent_high - low_start, 1e-9)
    retrace_ok = retrace <= 0.5
    hold9 = ema is not None and c > ema
    hold_v = vw is not None and c > vw
    trigger = c > recent_high
    stop = pull_low
    risk = c - stop if c > stop else None
    reward = recent_high - stop if risk is not None else None
    rr = reward / risk if risk and risk > 0 else None
    candidate = bool(surge_ok and retrace_ok and hold9 and hold_v
                     and trigger and rr is not None and rr >= 2.0)
    return {"surge": surge_ok, "retrace_ok": retrace_ok,
            "holds_9ema": hold9, "holds_vwap": hold_v, "trigger": trigger,
            "stop": round(stop, 4), "rr": round(rr, 2) if rr is not None else None,
            "candidate": candidate}


def session_flags(peak_pnl: "float | None", current_pnl: "float | None",
                  max_daily_loss: float = 0.03) -> dict:
    """'Walk away for the day' rules as analysis flags."""
    give_back = None
    if peak_pnl and current_pnl is not None and peak_pnl > 0:
        give_back = (peak_pnl - current_pnl) / peak_pnl >= 0.5
    out = {"giveback_50": give_back}
    if current_pnl is None:
        out["max_daily_loss_hit"] = None
    else:
        out["max_daily_loss_hit"] = current_pnl <= -max_daily_loss
    return out


__all__ = ["rvol", "ema9", "vwap", "pillars", "first_pullback", "session_flags"]