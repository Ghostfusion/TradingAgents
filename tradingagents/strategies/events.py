"""Phase 4 - earnings event logic (PEAD harness).

Quantify the surprise (actual vs consensus), classify the post-earnings drift
regime and size a catalyst-risk overlay:

  surprise       = (eps_actual - eps_estimate) / |eps_estimate|
  drift_bias     = sign of surprise * sign of score drift -> hold vs fade
  risk_mult      = market-impled move vs a baseline (IV crush awareness)

Wire-up: the news analyst + seconds tools already fetch the earnings
calendar and catalyst data; this module converts them into sizing inputs.
"""

from __future__ import annotations


def surprise_score(actual: float | None, estimate: float | None) -> float | None:
    """Standardized earnings surprise; None when unquantifiable."""
    if actual is None or estimate is None:
        return None
    if estimate == 0:
        return None
    return (actual - estimate) / abs(estimate)


def drift_side(surprise, momentum: float | None = None) -> str:
    """PEAD side: 'beat' | 'miss' | 'flat'."""
    if surprise is None or abs(surprise) < 1e-9:
        return "flat"
    if surprise > 0:
        if momentum is not None and momentum < -0.1:
            return "beat"  # fundamental beat overrides short-term price weakness
        return "beat"
    return "miss"


def position_mult_by_side(side: str, catalyst: float = 1.0, cap: float = 1.5) -> float:
    """Position scale factor by event side (0 stays flat for 'flat')."""
    if side == "flat":
        return 0.0
    mult = 1.0 if side == "beat" else 0.5
    event_scale = catalyst if catalyst > 1 else 1.0
    return min(mult * event_scale, cap)


def expected_drift_after(day0: float, day_n: float) -> float:
    """Post-event drift return observed over the holding window."""
    if day0 <= 0:
        return 0.0
    return day_n / day0 - 1.0


def catalyst_risk_penalty(expected_move: float | None, baseline_move: float = 0.015) -> float:
    """Risk multiplier (<=1) from announcement-implied move vs baseline."""
    if expected_move is None or expected_move <= 0:
        return 0.5  # unknown expiry: halve the event position
    if baseline_move <= 0:
        return 1.0
    ratio = expected_move / baseline_move
    return max(0.0, min(1.0, 1.0 / (1.0 + ratio * 3.0)))


def gap_up_qualifies(
    day0_return: float | None,
    volume_ratio: float | None,
    vol_min: float = 2.5,
    gap_min: float | None = None,
) -> bool:
    """PEAD entry gate (Phase 4): a post-earnings gap up on exceptional
    volume (>=2.5x the average by default).

    ``volume_ratio`` is print-day volume / trailing average; ``gap_min`` is an
    optional minimum gap size (fraction) that must also hold. Unknown inputs
    never qualify (a gap we cannot verify is not a confirmed tailwind).
    """
    if day0_return is None or day0_return <= 0:
        return False
    if gap_min is not None and day0_return < gap_min:
        return False
    return bool(volume_ratio is not None and volume_ratio >= vol_min)


def consolidation_and_break(highs: list, closes: list, hold_days: int = 4) -> dict:
    """Post-earnings opening-range consolidation + breakout trigger.

    Measures the ``hold_days`` bars *after* the gap day (the caller passes the
    trailing bars only - the series must not include the print day itself),
    then flags a close above that range's high: the framework enters on a
    break above the consolidation high rather than chasing the gap.
    """
    if not highs or not closes or len(highs) < 2 or len(closes) < 2:
        return {"range_high": None, "range_low": None, "breakout": None}
    n = min(hold_days, len(highs) - 1) or 1
    seg_h = [float(v) for v in highs[-n:]]
    seg_l = [float(v) for v in closes[-n:]]  # low proxy: closes of the range
    rng_high = max(seg_h)
    rng_low = min(seg_l)
    tight_aggregate = False
    if n >= 3:
        first = max(highs[-n : -n // 2]) - min(closes[-n : -n // 2])
        last = max(highs[-n // 2 :]) - min(closes[-n // 2 :])
        tight_aggregate = bool(first and last < first)
    return {
        "range_high": round(rng_high, 4),
        "range_low": round(rng_low, 4),
        "tightening": tight_aggregate,
        "breakout": bool(closes[-1] > rng_high),
        "days": n,
    }


def post_earnings_play(
    day0_return: float | None,
    volume_ratio: float | None,
    post_highs: list,
    post_closes: list,
    hold_days: int = 4,
    vol_min: float = 2.5,
    gap_min: float | None = None,
) -> dict:
    """Full PEAD entry read: gap gate -> consolidation -> break trigger.

    Verdicts: ``setup`` (gap qualified and price broke the consolidation
    high), ``consolidating`` (gap qualified, waiting for the break),
    ``no-gap`` (gap did not qualify) or ``no-data``.
    """
    if day0_return is None or volume_ratio is None or not post_highs:
        return {"verdict": "no-data"}
    gap_ok = gap_up_qualifies(day0_return, volume_ratio, vol_min=vol_min, gap_min=gap_min)
    cons = consolidation_and_break(post_highs, post_closes, hold_days=hold_days)
    if not gap_ok:
        return {"verdict": "no-gap", "gap": False, **cons}
    if cons.get("breakout"):
        return {"verdict": "setup", "gap": True, **cons}
    return {"verdict": "consolidating", "gap": True, **cons}


__all__ = [
    "surprise_score",
    "drift_side",
    "position_mult_by_side",
    "expected_drift_after",
    "catalyst_risk_penalty",
    "gap_up_qualifies",
    "consolidation_and_break",
    "post_earnings_play",
]
