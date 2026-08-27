"""Market-session mechanics: pre-market / open / close reads (pure, offline).

Complements ``pre_market.py`` (the CONFIRM / REVISE / REJECT decision
arbiter) with the *session mechanics* the reviewer and the analyst LLMs can
ground claims in:

  opening_range          - first-N-minute high/low + ORB breakout read
  gap_type               - common / breakaway / runaway / exhaustion + fill stats
  order_imbalance        - buy-heavy / sell-heavy / balanced from flow nets
  premarket_liquidity    - thin-book warning from pre-market volume vs average
  post_close_confirmation- did the close confirm the plan (vs stop/target)?

Every function is pure and returns None on missing/invalid input (the
no-fabrication rule). No network, no state.
"""

from __future__ import annotations

__all__ = [
    "opening_range",
    "gap_type",
    "order_imbalance",
    "premarket_liquidity",
    "post_close_confirmation",
]


def opening_range(highs, lows, closes=None, n_minutes: int = 15) -> dict:
    """Opening range: the high/low of the first ``n_minutes`` of trading.

    Returns ``{or_high, or_low, mid, breakout, stop, target}`` where
    ``breakout`` is 'up' / 'down' / None (latest close vs the range),
    ``stop`` is below the range low (long) or above the range high (short),
    and ``target`` is a 2R multiple of the range width. ``closes`` is
    optional; without it the latest high is used as the breakout proxy.
    None when insufficient bars.
    """
    if not highs or not lows or len(highs) < 2 or len(lows) < 2:
        return {
            "or_high": None, "or_low": None, "mid": None,
            "breakout": None, "stop": None, "target": None,
        }
    try:
        seg_h = [float(x) for x in highs[:n_minutes]]
        seg_l = [float(x) for x in lows[:n_minutes]]
        or_high = max(seg_h)
        or_low = min(seg_l)
        mid = (or_high + or_low) / 2.0
        last = float(closes[-1]) if closes else (float(highs[-1]) if highs else None)
        if last is None:
            return {
                "or_high": round(or_high, 4), "or_low": round(or_low, 4),
                "mid": round(mid, 4), "breakout": None, "stop": None, "target": None,
            }
        width = or_high - or_low
        if width <= 0:
            return {
                "or_high": round(or_high, 4), "or_low": round(or_low, 4),
                "mid": round(mid, 4), "breakout": None, "stop": None, "target": None,
            }
        if last > or_high:
            breakout = "up"
            stop = or_low
        elif last < or_low:
            breakout = "down"
            stop = or_high
        else:
            breakout = None
            stop = or_low  # default long-side stop
        return {
            "or_high": round(or_high, 4),
            "or_low": round(or_low, 4),
            "mid": round(mid, 4),
            "breakout": breakout,
            "stop": round(stop, 4),
            "target": round(or_high + 2.0 * width, 4) if breakout == "up" else round(or_low - 2.0 * width, 4),
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return {
            "or_high": None, "or_low": None, "mid": None,
            "breakout": None, "stop": None, "target": None,
        }


def gap_type(closes, highs, lows, volumes, n: int = 20) -> dict:
    """Classify the most recent overnight gap + estimate fill behavior.

    Gap = today's open vs yesterday's close. Types (Investopedia):
      common     - small gap, normal volume, fills fast (high fill prob)
      breakaway  - gaps out of a range/pattern on elevated volume (low fill)
      runaway    - mid-trend continuation gap (low fill)
      exhaustion - gap after a sharp run, likely trend end (high fill)

    Returns ``{type, gap_pct, fill_probability, days_to_fill}`` where the
    fill stats are heuristic estimates from the gap size + volume (never
    fabricated — None when the inputs are insufficient).
    """
    if len(closes) < n + 2 or len(highs) < n + 2 or len(lows) < n + 2 or len(volumes) < n + 2:
        return {"type": None, "gap_pct": None, "fill_probability": None, "days_to_fill": None}
    try:
        prev_close = float(closes[-2])
        today_open = float(closes[-1])  # daily close proxy for the open
        if prev_close <= 0:
            return {"type": None, "gap_pct": None, "fill_probability": None, "days_to_fill": None}
        gap_pct = (today_open - prev_close) / prev_close
        avg_vol = sum(float(v) for v in volumes[-n:]) / n
        vol_ratio = float(volumes[-1]) / avg_vol if avg_vol > 0 else None
        # recent range width (volatility context)
        seg_h = [float(x) for x in highs[-n:]]
        seg_l = [float(x) for x in lows[-n:]]
        rng = max(seg_h) - min(seg_l)
        abs_gap = abs(gap_pct)
        if rng <= 0:
            return {"type": None, "gap_pct": round(gap_pct, 6), "fill_probability": None, "days_to_fill": None}
        # heuristic classification
        if vol_ratio is not None and vol_ratio >= 2.0 and abs_gap >= 0.02:
            gtype = "breakaway"
            fill_prob = 0.3
            days = 5
        elif abs_gap >= 0.05:
            gtype = "exhaustion"
            fill_prob = 0.6
            days = 3
        elif abs_gap >= 0.02:
            gtype = "runaway"
            fill_prob = 0.4
            days = 4
        else:
            gtype = "common"
            fill_prob = 0.8
            days = 2
        return {
            "type": gtype,
            "gap_pct": round(gap_pct, 6),
            "fill_probability": fill_prob,
            "days_to_fill": days,
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return {"type": None, "gap_pct": None, "fill_probability": None, "days_to_fill": None}


def order_imbalance(inst_net: float | None, retail_net: float | None) -> dict:
    """Order-imbalance verdict from institutional vs retail net flow.

    ``inst_net`` / ``retail_net`` are the net signed flows (e.g. from
    ``orderflow.institutional_net`` / ``retail_net``). Returns
    ``{verdict, ratio}`` where ratio = inst_net / (|inst_net| + |retail_net|)
    and verdict is buy-heavy / sell-heavy / balanced. None when both are
    missing.
    """
    if inst_net is None and retail_net is None:
        return {"verdict": None, "ratio": None}
    inst = float(inst_net) if inst_net is not None else 0.0
    retail = float(retail_net) if retail_net is not None else 0.0
    denom = abs(inst) + abs(retail)
    if denom <= 0:
        return {"verdict": "balanced", "ratio": 0.0}
    # signed net / total flow: +1 = all institutional buying, -1 = all
    # retail/selling, 0 = perfectly balanced.
    ratio = (inst + retail) / denom
    if ratio > 0.3:
        verdict = "buy-heavy"
    elif ratio < -0.3:
        verdict = "sell-heavy"
    else:
        verdict = "balanced"
    return {"verdict": verdict, "ratio": round(ratio, 4)}


def premarket_liquidity(volume: float | None, avg_volume: float | None) -> dict:
    """Pre-market liquidity read: current pre-market volume vs the daily
    average. A very low ratio = thin book (wide spreads, gap risk).

    Returns ``{ratio, verdict}`` where verdict is liquid / thin / illiquid.
    None when either input is missing.
    """
    if volume is None or avg_volume is None or avg_volume <= 0:
        return {"ratio": None, "verdict": None}
    ratio = float(volume) / float(avg_volume)
    if ratio >= 0.10:
        verdict = "liquid"
    elif ratio >= 0.03:
        verdict = "thin"
    else:
        verdict = "illiquid"
    return {"ratio": round(ratio, 4), "verdict": verdict}


def post_close_confirmation(close: float | None, stop: float | None, target: float | None) -> dict:
    """Post-close confirmation: did the close confirm the plan?

    Returns ``{verdict, action}``:
      - close beyond the stop  -> 'stopped-out' (REJECT the plan)
      - close at/above target  -> 'target-hit' (take profit)
      - close between stop/target -> 'holding' (plan intact)
    None when close is missing.
    """
    if close is None:
        return {"verdict": None, "action": None}
    c = float(close)
    if stop is not None and target is not None:
        lo, hi = min(float(stop), float(target)), max(float(stop), float(target))
        if c < lo:
            return {"verdict": "stopped-out", "action": "exit"}
        if c > hi:
            return {"verdict": "target-hit", "action": "take-profit"}
        return {"verdict": "holding", "action": "hold"}
    if stop is not None and c < float(stop):
        return {"verdict": "stopped-out", "action": "exit"}
    if target is not None and c > float(target):
        return {"verdict": "target-hit", "action": "take-profit"}
    return {"verdict": "holding", "action": "hold"}
