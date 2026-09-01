"""Momentum day-trading signals (analysis-only; no execution).

Implements the 5-pillar momentum pre-filter + first-pullback pattern + session
risk flags + intraday confirmation from Strategies/momentum_day_trading.md
(Warrior Trading 5-step playbook). Pure, offline-testable functions; all
network access lives in the tool/screener layer, never here.

Phase-2 extensions (completed pattern rules):
  - light-red / heavy-green volume rule (``volume_ok``)
  - topping-tail exclusion (``tail_ok``)
Phase-3 extensions (session gates):
  - ``session_flags`` gains the ``past_optimal_window`` / ``no_quality_setups``
    walk-away rules and a single ``walk_away`` verdict
Phase-4 extensions (intraday confirmation):
  - ``intraday_pullback`` runs the same pattern on 1m/5m bars with a session
    VWAP hold; ``psych_level`` reports whole/half-dollar levels
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def rvol(volumes: list, window: int = 50) -> float | None:
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


def ema9(closes: list) -> float | None:
    if not closes:
        return None
    k = 2.0 / 10.0
    n = min(9, len(closes))
    ema = sum(closes[:n]) / n
    for v in closes[n:]:
        ema = v * k + ema * (1 - k)
    return ema


def vwap(closes: list, volumes: list) -> float | None:
    n = min(len(closes), len(volumes))
    if n == 0:
        return None
    value = volume = 0.0
    for i in range(n):
        volume += volumes[i]
        value += closes[i] * volumes[i]
    return value / volume if volume else None


def twap(closes: list) -> float | None:
    """Time-Weighted Average Price: simple arithmetic mean of prices over the
    window (no volume weighting). Complements ``vwap``; used for execution
    benchmarks where volume data is unavailable or the schedule is fixed.
    """
    vals = []
    for v in closes:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(f):
            continue
        vals.append(f)
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _log_returns(closes: list) -> list[float]:
    """Log returns of a close series (skips None / non-positive)."""
    out: list[float] = []
    prev: float | None = None
    for c in closes:
        try:
            f = float(c)
        except (TypeError, ValueError):
            prev = None
            continue
        if not math.isfinite(f) or f <= 0:
            prev = None
            continue
        if prev is not None:
            out.append(math.log(f / prev))
        prev = f
    return out


def ts_momentum_weights(
    closes_by_name: dict,
    horizon: int = 252,
    vol_window: int = 60,
    target_vol: float = 0.10,
    max_leverage: float = 2.0,
) -> dict | None:
    """Cookbook recipe 1 time-series momentum weights (MOP-style).

    Per name: ``w_i ~= sign(log(P_t/P_{t-h})) / sigma_i`` - the sign of the
    trailing-horizon log return scaled inverse to recent EWMA volatility
    (volatility targeting). Raw weights are normalized to the portfolio
    ``target_vol`` and hard-capped at ``max_leverage`` gross. Names without
    enough history / zero vol contribute nothing (honest partial book).

    Returns ``{name: weight, ...}`` with ``_meta`` = ``{target_vol,
    gross, n_names}`` or None when no name has a measurable signal.
    """
    from .volatility_models import ewma_vol

    out: dict = {}
    for name, closes in (closes_by_name or {}).items():
        logs = _log_returns(closes)
        if len(logs) <= horizon:
            continue
        mom = math.log(float(closes[-1]) / float(closes[-(horizon + 1)]))
        if not math.isfinite(mom):
            continue
        sig = ewma_vol(logs, lam=0.94, min_obs=20)
        if sig is None or sig <= 0:
            continue
        w = (1.0 if mom > 0 else (-1.0 if mom < 0 else 0.0)) / sig
        out[name] = w
    if not out:
        return None
    # Normalize ex-ante vol to the target: scale = target_vol / mean(sigma_i).
    sigmas = [1.0 / abs(w) for w in out.values() if w != 0.0]
    scale = 1.0
    if sigmas:
        scale = target_vol / (sum(sigmas) / len(sigmas))
    raw = {n: w * scale for n, w in out.items()}
    gross = sum(abs(v) for v in raw.values())
    if gross > max_leverage:
        k = max_leverage / gross
        raw = {n: v * k for n, v in raw.items()}
        gross = max_leverage
    raw["_meta"] = {
        "target_vol": round(float(target_vol), 4),
        "gross": round(float(gross), 4),
        "n_names": sum(1 for n in raw if n != "_meta"),
    }
    return raw


def pillars(close=None, day_volume=None, prev_close=None, day_open=None,
            rv: float | None = None, price_lo: float = 2.0,
            price_hi: float = 20.0, float_shares: float | None = None) -> dict:
    """The five pillars of the momentum pre-filter.

    Each pillar is True (pass), False (known fail) or None (unknown - the
    pillar is ignored until the data is available). ``gap`` and ``float`` are
    None when the source isn't wired so callers can tell "missing data" apart
    from "measured and failed".
    """
    res: dict = {}
    res["rvol"] = bool(rv is not None and rv >= 2.0) if rv is not None else None
    res["high_volume"] = (bool(day_volume is not None and day_volume >= 1_000_000)
                          if day_volume is not None else None)
    gap = None
    if prev_close and day_open is not None and prev_close > 0:
        gap = day_open / prev_close - 1.0
    res["gap"] = bool(gap >= 0.02) if gap is not None else None
    res["price_band"] = (bool(close is not None and price_lo <= close <= price_hi)
                         if close is not None else None)
    res["float"] = None if float_shares is None else bool(float_shares <= 20e6)
    return res


def _volume_color_ok(opens: list | None, closes: list, volumes: list,
                     window: int) -> bool | None:
    """Light volume on red candles, heavy on green (spec rule). None=no data."""
    if not opens or len(opens) != len(closes) or len(volumes) != len(closes):
        return None
    seg_o = opens[-window:]
    seg_c = closes[-window:]
    seg_v = volumes[-window:]
    red = [float(v) for o, c, v in zip(seg_o, seg_c, seg_v, strict=False) if c < o]
    green = [float(v) for o, c, v in zip(seg_o, seg_c, seg_v, strict=False) if c >= o]
    if len(red) < 2 or len(green) < 2:
        return None
    return sum(red) / len(red) < sum(green) / len(green)


def _top_tail_ok(opens: Sequence[float] | None, closes: list, highs: list,
                 window: int) -> bool | None:
    """No prominent topping tails in the segment (upper wick > 1.5x body)."""
    if not opens:
        return None
    ratios = []
    for o, c, h in zip(opens[-window:], closes[-window:], highs[-window:],
                       strict=False):
        if o is None or c is None or h is None:
            return None
        body = abs(float(c) - float(o))
        if body > 1e-9:
            upper = float(h) - max(float(o), float(c))
            ratios.append(upper / body)
    if not ratios:
        return None
    return max(ratios) < 1.5


def first_pullback(closes: list, highs: list, lows: list, volumes: list,
                   opens: list | None = None, window: int = 6) -> dict:
    """First-pullback pattern: surge, <=50% retrace, 9 EMA/VWAP hold, new-high.

    ``opens`` enables the two rulebook extras (``volume_ok``, ``tail_ok``);
    without them the extras stay None (unknown) and never fail a candidate.
    """
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
    # Reward is measured to a real target beyond the trigger (measured-move
    # extension): target = c + (recent_high - low_start). Anchoring reward to
    # the already-passed ``recent_high`` (as before) made rr = reward/risk < 1
    # whenever the trigger fired, so the 2R gate could never pass and the
    # first-pullback candidate was permanently dead.
    measured_move = (recent_high - low_start) if recent_high and low_start is not None else None
    target = (c + measured_move) if measured_move is not None else None
    reward = (target - c) if target is not None else None
    rr = reward / risk if (risk and risk > 0 and reward is not None) else None
    volume_ok = _volume_color_ok(opens, closes, volumes, window)
    tail_ok = _top_tail_ok(opens, closes, highs, window)
    candidate = bool(surge_ok and retrace_ok and hold9 and hold_v
                     and trigger and rr is not None and rr >= 2.0
                     and (volume_ok is not False) and (tail_ok is not False))
    return {"surge": surge_ok, "retrace_ok": retrace_ok,
            "holds_9ema": hold9, "holds_vwap": hold_v, "trigger": trigger,
            "volume_ok": volume_ok, "tail_ok": tail_ok,
            "stop": round(stop, 4),
            "target": round(target, 4) if target is not None else None,
            "rr": round(rr, 2) if rr is not None else None,
            "candidate": candidate}


def session_flags(peak_pnl: float | None, current_pnl: float | None,
                  max_daily_loss: float = 0.03,
                  past_optimal_window: bool | None = None,
                  no_quality_setups: bool | None = None) -> dict:
    """'Walk away for the day' rules as analysis flags (Phase 3).

    Returns every rule state plus a single ``walk_away`` total that is True
    when any walk-away rule fired (unknowns never force a walk-away).
    """
    give_back = None
    if peak_pnl and current_pnl is not None and peak_pnl > 0:
        give_back = (peak_pnl - current_pnl) / peak_pnl >= 0.5
    out: dict = {"giveback_50": give_back}
    if current_pnl is None:
        out["max_daily_loss_hit"] = None
    else:
        out["max_daily_loss_hit"] = current_pnl <= -max_daily_loss
    out["past_optimal_window"] = (None if past_optimal_window is None
                                  else bool(past_optimal_window))
    out["no_quality_setups"] = (None if no_quality_setups is None
                                else bool(no_quality_setups))
    fired = [v for v in (out["giveback_50"], out["max_daily_loss_hit"],
                         out["past_optimal_window"], out["no_quality_setups"])
             if v is True]
    out["walk_away"] = bool(fired)
    return out


def past_optimal_window(now=None, cutoff_hour: int = 10, cutoff_minute: int = 0,
                        tz_name: str = "America/New_York") -> bool | None:
    """True when ``now`` is at/after the cash window cutoff in market time.

    The playbook's optimal trading window ends around 10:00 ET; a None return
    means the clock is unavailable (callers then ignore the rule).
    """
    from datetime import datetime

    if now is None:
        now = datetime.now()
    try:
        from zoneinfo import ZoneInfo

        local = now.astimezone(ZoneInfo(tz_name))
        cutoff = local.replace(hour=cutoff_hour, minute=cutoff_minute,
                               second=0, microsecond=0)
        return local >= cutoff
    except Exception:
        return None


def psych_level(price: float) -> dict:
    """Whole/half-dollar levels around ``price`` (psychological S/R)."""
    step = 0.5
    if price is None or price <= 0:
        return {"above": None, "below": None, "dist_pct": None}
    above = math.ceil(price / step) * step
    below = math.floor(price / step) * step
    return {"above": above, "below": below,
            "dist_pct": (above - price) / price * 100.0}


def intraday_pullback(bars: list, window: int = 6) -> dict:
    """First-pullback on intraday bars (1m/5m) with a session VWAP hold.

    ``bars``: list of dicts with keys o/h/l/c/v (opional vw). Missing bars
    degrade cleanly to ``{"candidate": False}``.
    """
    if not bars or len(bars) < window + 4:
        return {"candidate": False, "bar_count": len(bars) if bars else 0}
    closes = [float(b["c"]) for b in bars]
    highs = [float(b["h"]) for b in bars]
    lows = [float(b["l"]) for b in bars]
    vols = [float(b["v"]) for b in bars]
    opens = [float(b["o"]) for b in bars]
    fp = first_pullback(closes, highs, lows, vols, opens=opens, window=window)
    fp["bar_count"] = len(bars)
    # Session VWAP - prefer the vendor's bar VWAP when present, else the
    # typical-price proxy (h+l+c)/3.
    vals = []
    for b in bars:
        v = b.get("vw")
        if v is None and isinstance(b.get("h"), (int, float)):
            v = (float(b["h"]) + float(b["l"]) + float(b["c"])) / 3.0
        if v is not None:
            vals.append(float(v))
    svwap = vwap(vals, vols) if vals else None
    hold = svwap is not None and closes[-1] > svwap
    fp["session_vwap"] = round(svwap, 4) if svwap is not None else None
    fp["holds_session_vwap"] = hold if svwap is not None else None
    if hold is False:
        fp["candidate"] = False
    return fp


__all__ = ["rvol", "ema9", "vwap", "pillars", "first_pullback", "session_flags",
           "past_optimal_window", "psych_level", "intraday_pullback", "twap",
           "ts_momentum_weights"]
