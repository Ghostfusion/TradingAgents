"""Decision-level data quality + cross-vendor disagreement + PIT invariant
(W3-1, W3-2, W3-4).

- ``aggregate_quality`` — weights per-input quality scores (0-100) into an
  overall decision score + a confidence tier (full/normal/reduced/none) that
  mirrors the remediation plan's table (91-100 full, 80-90 normal, 65-79
  reduced, <65 no strong recommendation). Always honest: an unmeasured input
  is excluded from the weight (never counted as 0).
- ``disagreement_flag`` — given several measured values of the SAME metric
  across vendors (e.g. EPS), report the cross-vendor spread % and flag when
  it exceeds a threshold: DATA CONFLICT rather than silently picking a vendor.
- ``fundamentals_pit_ok`` — W3-4: a fundamental read is only usable in a
  decision whose effective date is >= the fundamental's period/as-of date;
  otherwise fail-closed (refuse the leak of a future restated/dated value).

All pure + deterministic; advisory only (reports a score/flag, never gates a
hard rule by itself).
"""

from __future__ import annotations

# Per-input quality weight (sums to 100 over the standard set). Missing
# inputs are excluded and the remaining weights renormalized.
_INPUT_WEIGHT = {
    "price": 22.0,
    "volume": 15.0,
    "fundamentals": 22.0,
    "news": 14.0,
    "options": 12.0,
    "macro": 15.0,
}

_QUALITY_TIERS = [
    (91.0, "full"),
    (80.0, "normal"),
    (65.0, "reduced"),
]


def aggregate_quality(input_scores: dict) -> dict:
    """Weighted overall data-quality score (0-100) + confidence tier.

    ``input_scores``: {input_name: 0-100} (e.g. price=95, fundamentals=70).
    Unmeasured inputs are dropped and weights renormalized over the present
    set (honest: absence is not a 0).
    Returns {score, tier, inputs, weight_used}.
    """
    weights = dict(_INPUT_WEIGHT)
    drop = [k for k in weights if k not in (input_scores or {})]
    for k in drop:
        weights.pop(k, None)
    present = [k for k in (input_scores or {}) if k in _INPUT_WEIGHT]
    if not present or not weights:
        return {"score": None, "tier": "unknown", "inputs": {}, "weight_used": 0.0}
    total_w = sum(weights.values())
    score = sum(
        float(input_scores[k]) * weights[k] / total_w for k in present
    ) if total_w > 0 else None
    tier = "unknown"
    for thr, label in _QUALITY_TIERS:
        if score is not None and score >= thr:
            tier = label
            break
    if score is not None and score < 65.0:
        tier = "none"
    return {
        "score": round(score, 1) if score is not None else None,
        "tier": tier,
        "inputs": {k: float(input_scores[k]) for k in present},
        "weight_used": total_w,
    }


def disagreement_flag(values: list, threshold_pct: float = 5.0) -> dict:
    """Cross-vendor spread on one metric (W3-2).

    ``values``: measured values of the same metric across vendors. Returns
    {consistent, spread_pct, min, max, count}. A spread beyond ``threshold_pct``
    (relative to the mean) flags DATA CONFLICT instead of silently trusting
    one vendor. Nones / <2 values -> no claim (consistent, spread None).
    """
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return {"consistent": True, "spread_pct": None,
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None, "count": len(vals)}
    mean = sum(vals) / len(vals)
    spread = (max(vals) - min(vals)) / mean * 100.0 if mean else 0.0
    return {
        "consistent": spread <= threshold_pct,
        "spread_pct": round(spread, 2),
        "min": min(vals), "max": max(vals), "count": len(vals),
    }


def fundamentals_pit_ok(period_date: str | None, effective_date: str | None) -> bool:
    """W3-4: is a fundamental read with as-of/period ``period_date`` usable at
    ``effective_date``? True only when period <= effective (not future).
    Any unparseable/missing side -> False (fail-closed: don't leak a future
    value into an earlier decision)."""
    if not period_date or not effective_date:
        return False
    try:
        return str(period_date) <= str(effective_date)
    except Exception:  # noqa: BLE001 - malformed -> fail closed
        return False


__all__ = ["aggregate_quality", "disagreement_flag", "fundamentals_pit_ok",
           "_INPUT_WEIGHT", "_QUALITY_TIERS"]
