"""Phase 3/5 - swing-trade building blocks.

Implements the deterministic parts of the techno-fundamental swing framework
(Strategies/framework.md):

  * trend architecture - price above a rising 50/200 SMA with the 20-day EMA
    stacked above the 50-day SMA
  * RSI band discipline - RSI operating 45-70; pullbacks reset to 40-50 but
    must not break below 40
  * pullback setup - orderly pullback into the rising 20-day EMA on declining
    volume (entry zone, not an order)
  * structure stop - 1 ATR below the most recent swing low
  * targets - 2R / 3R two-tier profit targets (T1/T2) with a 50% T1
    scale-out to break-even and a 20-day-EMA trailing rule for the balance

Pure and offline-testable; no network, no state. The screener and any overlay
feed daily OHLCV and read flags back.
"""

from __future__ import annotations


def _sma(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(series[-n:]) / n


def _ema_last(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    k = 2.0 / (n + 1)
    ema = sum(series[:n]) / n
    for v in series[n:]:
        ema = float(v) * k + ema * (1 - k)
    return ema


def rsi(closes: list, n: int = 14) -> float | None:
    """Wilder-style RSI(14) over the daily closes (vanilla smoothing)."""
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if gains + losses == 0:
        return 50.0
    rs = gains / losses if losses > 0 else float("inf")
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def trend_architecture(closes: list) -> dict:
    """Stack + slope checks; each flag is True/False or None when unknown."""
    if not closes:
        return {
            "stacked": None,
            "above_sma50": None,
            "above_sma200": None,
            "sma50_rising": None,
            "sma200_rising": None,
            "ema20_above_sma50": None,
            "context": "no data",
        }
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    ema20 = _ema_last(closes, 20)
    last = float(closes[-1])
    sma50_5 = _sma(closes[:-5], 50) if len(closes) > 50 else None
    sma200_15 = _sma(closes[:-15], 200) if len(closes) > 200 else None

    above_50 = bool(last > sma50) if sma50 is not None else None
    above_200 = bool(last > sma200) if sma200 is not None else None
    rising_50 = bool(sma50 > sma50_5) if sma50_5 is not None else None
    rising_200 = bool(sma200 > sma200_15) if sma200_15 is not None else None
    ema_above = bool(ema20 > sma50) if (ema20 is not None and sma50 is not None) else None
    if sma200 is None or sma50 is None or ema20 is None:
        stacked = None
    else:
        stacked = bool(
            ema_above is True and sma50 > sma200 and rising_50 is True and rising_200 is True
        )
    parts = []
    if stacked is not None:
        parts.append("stacked" if stacked else "stack-broken")
    if above_50 is not None:
        parts.append("above50" if above_50 else "below50")
    ctx = "trend: " + ", ".join(parts) if parts else "trend: n/a"
    return {
        "stacked": stacked,
        "above_sma50": above_50,
        "above_sma200": above_200,
        "sma50_rising": rising_50,
        "sma200_rising": rising_200,
        "ema20_above_sma50": ema_above,
        "context": ctx,
    }


def rsi_band(
    rsi_value: float | None, strong: tuple = (45.0, 70.0), reset: tuple = (40.0, 50.0)
) -> dict:
    """RSI operating-band read for swing longs.

    ``in_band`` (45-70, the framework's operating range), ``pullback`` (40-50,
    the healthy reset zone) and ``broken`` (below 40 - setup invalidated).
    """
    if rsi_value is None:
        return {"value": None, "strong": None, "pullback": None, "broken": None, "label": "unknown"}
    v = float(rsi_value)
    strong_lo, strong_hi = strong
    reset_lo, reset_hi = reset
    in_band = bool(strong_lo <= v <= strong_hi)
    pull = bool(reset_lo <= v < strong_lo)  # 40-<45: below band but not broken
    reset_zone = bool(reset_lo <= v <= reset_hi)
    broken = bool(v < reset_lo)
    hot = bool(v > strong_hi)
    if broken:
        label = "broken"
    elif hot:
        label = "hot"
    elif in_band:
        label = "strong"
    else:
        label = "reset"
    return {
        "value": v,
        "in_band": in_band,
        "strong": in_band,
        "pullback": pull,
        "reset_zone": reset_zone,
        "broken": broken,
        "hot": hot,
        "label": label,
    }


def pullback_setup(closes: list, lows: list, volumes: list, window: int = 6) -> dict:
    """Orderly pullback into the 20-day EMA on declining volume.

    Requires the price to have traded down to (but held) the EMA while recent
    volume fades vs the prior stretch - accumulation, not distribution.
    """
    ema20 = _ema_last(closes, 20)
    sma50 = _sma(closes[:-window], 50) if len(closes) > 50 + window else None
    if ema20 is None or not lows or not volumes:
        return {"candidate": False, "near_ema": None, "volume_fade": None}
    close = float(closes[-1])
    low = float(lows[-1])
    near_ema = bool(low <= ema20 and close >= ema20)
    recent = volumes[-window:]
    prior = volumes[-2 * window : -window]
    vf = None
    if recent and len(prior) >= window:
        vf = sum(recent) / window <= sum(prior) / window
    up = bool(sma50 is not None and ema20 > sma50)
    candidate = bool(near_ema and (vf is not False) and (up is not False))
    return {
        "near_ema": near_ema,
        "volume_fade": vf,
        "uptrend_base": up,
        "ema20": round(ema20, 4),
        "candidate": candidate,
    }


def swing_low_stop(
    lows: list,
    atr_value: float | None,
    atr_mult: float = 1.0,
    lookback: int = 10,
    close: float | None = None,
) -> dict:
    """Structure stop: 1 ATR below the most recent swing low.

    ``risk_pct`` is the stop distance from ``close`` (the framework's position
    sizing input: shares = capital x risk% / (entry - stop)).
    """
    if not lows or len(lows) < lookback or not atr_value or atr_value <= 0:
        return {"swing_low": None, "stop": None, "risk_pct": None}
    swing_low = min(float(v) for v in lows[-lookback:])
    stop = swing_low - float(atr_mult) * float(atr_value)
    risk_pct = None
    if close is not None and close > stop > 0 and close > 0:
        risk_pct = (close - stop) / close
    return {
        "swing_low": round(swing_low, 4),
        "stop": round(stop, 4),
        "atr": round(float(atr_value), 4),
        "atr_mult": atr_mult,
        "risk_pct": round(risk_pct, 4) if risk_pct is not None else None,
    }


def targets_rr(entry: float, stop: float, r1: float = 2.0, r2: float = 3.0) -> dict:
    """Two-tier targets from a risk multiple (T1 = 2R, T2 = 3R by default)."""
    risk = float(entry) - float(stop)
    if risk <= 0:
        return {"valid": False, "t1": None, "t2": None}
    return {
        "valid": True,
        "entry": round(float(entry), 4),
        "stop": round(float(stop), 4),
        "risk": round(risk, 4),
        "t1": round(float(entry) + float(r1) * risk, 4),
        "t2": round(float(entry) + float(r2) * risk, 4),
        "r1": float(r1),
        "r2": float(r2),
    }


def scaleout_plan(entry: float, stop: float, t1_fraction: float = 0.5) -> dict:
    """Scale-out policy: sell ``t1_fraction`` at T1, move to break-even, trail
    the rest on the 20-day EMA (the framework's Phase-5 profit management)."""
    t = targets_rr(entry, stop)
    if not t.get("valid"):
        return {"valid": False}
    return {
        "valid": True,
        "t1": t["t1"],
        "t2": t["t2"],
        "t1_fraction": t1_fraction,
        "t2_fraction": round(1.0 - t1_fraction, 4),
        "breakeven_after_t1": True,
        "trail": "20-day EMA",
    }


def trail_ema(closes: list, n: int = 20) -> dict:
    """Trailing rule flag: a daily close below the rising 20-day EMA exits."""
    ema = _ema_last(closes, n)
    if ema is None:
        return {"ema": None, "below": None, "exit": None}
    below = float(closes[-1]) < ema
    return {"ema": round(ema, 4), "below": below, "exit": below}


def swing_report(
    closes: list,
    highs: list,
    lows: list,
    volumes: list,
    atr_value: float | None = None,
    benchmark_closes: list | None = None,
) -> dict | None:
    """One deterministic swing read for a symbol.

    Combines trend architecture, RSI band, pullback setup, structure stop,
    targets and (when ``benchmark_closes`` is given) relative strength. Returns
    None with fewer than ~200 closes (the 200-day SMA is structural).
    """
    if not closes or len(closes) < 200:
        return None
    arch = trend_architecture(closes)
    rsi_val = rsi(closes)
    band = rsi_band(rsi_val)
    pull = pullback_setup(closes, lows, volumes)
    rs = None
    if benchmark_closes:
        try:
            from .relative_strength import relative_strength_report

            rs = relative_strength_report(closes, benchmark_closes)
        except Exception:  # noqa: BLE001 - RS is an enhancement, never fatal
            rs = None

    stop_block = None
    targets_block = None
    if atr_value and lows and len(lows) >= 10:
        stop_block = swing_low_stop(lows, atr_value, close=float(closes[-1]))
        if stop_block and stop_block.get("stop"):
            targets_block = targets_rr(float(closes[-1]), stop_block["stop"])
    elif atr_value is None and lows and len(lows) >= 10:
        # No ATR supplied: still report swing low + targets from a proxy stop
        # (stop = swing low; targets measured against it).
        swing_low = min(float(v) for v in lows[-10:])
        stop_block = {
            "swing_low": round(swing_low, 4),
            "stop": round(swing_low, 4),
            "atr": None,
            "risk_pct": None,
        }
        targets_block = targets_rr(float(closes[-1]), swing_low)

    rs_ok = rs is None or rs.get("verdict") in ("leading", "uptrend")
    band_ok = band.get("label") in ("strong", "reset")
    candidate = bool(
        arch.get("stacked") is True and band_ok and pull.get("candidate") is True and rs_ok
    )
    ctx_parts = [arch.get("context", "")]
    if rs:
        ctx_parts.append(
            "rs: " + rs.get("verdict", "?") if rs.get("verdict") != "unknown" else "rs: n/a"
        )
    ctx_parts.append("rsi=" + band.get("label", "?"))
    return {
        "architecture": arch,
        "rsi": band,
        "pullback": pull,
        "relative_strength": rs,
        "stop": stop_block,
        "targets": targets_block,
        "scaleout": scaleout_plan(float(closes[-1]), stop_block["stop"])
        if stop_block and stop_block.get("stop")
        else None,
        "trail": trail_ema(closes),
        "candidate": candidate,
        "context": "; ".join(p for p in ctx_parts if p),
    }


__all__ = [
    "rsi",
    "trend_architecture",
    "rsi_band",
    "pullback_setup",
    "swing_low_stop",
    "targets_rr",
    "scaleout_plan",
    "trail_ema",
    "swing_report",
]
