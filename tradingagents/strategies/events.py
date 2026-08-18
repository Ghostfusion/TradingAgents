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


def surprise_score(actual: "float | None", estimate: "float | None") -> "float | None":
    """Standardized earnings surprise; None when unquantifiable."""
    if actual is None or estimate is None:
        return None
    if estimate == 0:
        return None
    return (actual - estimate) / abs(estimate)


def drift_side(surprise, momentum: "float | None" = None) -> str:
    """PEAD side: 'beat' | 'miss' | 'flat'."""
    if surprise is None or abs(surprise) < 1e-9:
        return "flat"
    if surprise > 0:
        if momentum is not None and momentum < -0.1:
            return "beat"  # fundamental beat overrides short-term price weakness
        return "beat"
    return "miss"


def position_mult_by_side(side: str, catalyst: float = 1.0,
                          cap: float = 1.5) -> float:
    """Position scale factor by event side (0 stays flat for 'flat')."""
    if side == "flat":
        return 0.0
    mult = 1.0 if side == "beat" else 0.5
    event_scale = catalyst if catalyst > 1 else 1.0
    return min(mult * event_scale, cap)


def expected_drift_after(day0 : float, day_n: float) -> float:
    """Post-event drift return observed over the holding window."""
    if day0 <= 0:
        return 0.0
    return day_n / day0 - 1.0


def catalyst_risk_penalty(expected_move: "float | None",
                          baseline_move: float = 0.015) -> float:
    """Risk multiplier (<=1) from announcement-implied move vs baseline."""
    if expected_move is None or expected_move <= 0:
        return 0.5  # unknown expiry: halve the event position
    if baseline_move <= 0:
        return 1.0
    ratio = expected_move / baseline_move
    return max(0.0, min(1.0, 1.0 / (1.0 + ratio * 3.0)))


__all__ = [
    "surprise_score", "drift_side", "position_mult_by_side",
    "expected_drift_after", "catalyst_risk_penalty",
]