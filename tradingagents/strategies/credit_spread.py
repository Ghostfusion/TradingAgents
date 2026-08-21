"""Credit-stress read from ICE BofA US high-yield option-adjusted spreads.

Deterministic, offline introspection of three FRED OAS series (the classic
forward-looking risk-off sentinel the regime/risk overlays care about):

  hy_oas    = ICE BofA US High Yield OAS              (BAMLH0A0HYM2)
  ccc_oas   = ICE BofA CCC & Lower US High Yield OAS (BAMLH0A3HYC)
  bb_oas    = ICE BofA BB US High Yield OAS        (BAMLH0A1HYBB)

The threshold bands mirror the standard credit-cycle read used by the macro
layer (see docs/api_reference.md + docs/massive_integration.md): widening HY
and CCC option-adjusted spreads past the warning levels signal credit stress
that historically precedes equities de-rating.

No network here - this module only classifies values the agent already holds.
"""

from __future__ import annotations

# OAS % thresholds (mind: FRED reports these series in %, not bps).
# Bands follow the credit-cycle table used by the macro layer: below the low
# bound = low; from low up to mid = moderate; mid..high = high; above = severe.
CCC_LOW = 8.0      # CCC OAS < 8%   -> low
CCC_MID = 11.0     # CCC OAS 10-12% -> moderate (mid ~11)
CCC_HIGH = 15.0    # CCC OAS > 15%  -> severe
HY_LOW = 3.0       # HY OAS < 3%    -> low
HY_MID = 4.5       # HY OAS 3.5-4.5% -> moderate
HY_HIGH = 5.5      # HY OAS > 5.5%  -> severe


def _band_of(value: float | None, low: float, mid: float, high: float) -> str | None:
    """Classify one OAS into low / moderate / high / severe."""
    if value is None:
        return None
    if value < low:
        return "low"
    if value < mid:
        return "moderate"
    if value <= high:
        return "high"
    return "severe"


def credit_stress_level(
    hy_oas: float | None,
    ccc_oas: float | None,
    bb_oas: float | None = None,
) -> dict:
    """Verdict dict for the credit regime from the HY/CCC/BB OAS values.

    Returns ``{"level", "scale", "reasons"}`` where ``level`` is the worst
    band observed across the available series (low -> moderate -> high ->
    severe) and ``scale`` (1.0 = no de-risk, 0.5 = full risk-off) is a
    deterministic multiplier an overlay consumer can apply. Missing series are
    skipped (never fabricated); if nothing is available the level is "unknown".
    """
    hy = _band_of(hy_oas, HY_LOW, HY_MID, HY_HIGH)
    ccc = _band_of(ccc_oas, CCC_LOW, CCC_MID, CCC_HIGH)
    bb = _band_of(bb_oas, HY_LOW, HY_MID, HY_HIGH)

    rank = {"low": 0, "moderate": 1, "high": 2, "severe": 3}
    active = [b for b in (hy, ccc, bb) if b is not None]
    if not active:
        return {"level": "unknown", "scale": 1.0, "reasons": []}

    level = max(active, key=lambda b: rank[b])
    scale = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.5}[rank[level]]

    reasons = []
    if hy is not None:
        reasons.append(f"hy_oas={hy_oas:.2f}% ({hy})")
    if ccc is not None:
        reasons.append(f"ccc_oas={ccc_oas:.2f}% ({ccc})")
    if bb is not None:
        reasons.append(f"bb_oas={bb_oas:.2f}% ({bb})")

    return {
        "level": level,
        "scale": scale,
        "reasons": reasons,
    }


__all__ = ["credit_stress_level", "CCC_LOW", "CCC_MID", "CCC_HIGH", "HY_LOW", "HY_MID", "HY_HIGH"]
