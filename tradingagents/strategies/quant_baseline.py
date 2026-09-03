"""Quant-only baseline (W1-5): a deterministic, LLM-free signal stack.

The single most important experiment in the remediation plan: does adding the
LLM actually improve decisions? This builds a pure factor composite (momentum,
value, quality, volatility, trend) as a flat signal + a rating, both of which
can be backtested SIDE BY SIDE with the LLM-produced ratings from the
prediction ledger — quant-only vs quant+LLM vs LLM-only.

All deterministic, all from closes + a few static inputs; missing data ->
None, never a guess. ``baseline_rating`` maps the composite to the same
5-tier scale the PM uses (Sell..Buy) so the two are directly comparable.
"""

from __future__ import annotations


def momentum(close: list[float | None], horizon: int = 60) -> float | None:
    """12-week (60d) price momentum; None when unmeasurable."""
    vals = [c for c in (close or []) if c is not None]
    if len(vals) < horizon + 1:
        return None
    base, cur = vals[-horizon - 1], vals[-1]
    if not base:
        return None
    return cur / base - 1.0


def trend_strength(close: list[float | None], window: int = 20) -> float | None:
    """Fraction of the last ``window`` closes above their own MA(window):
    a simple trend filter in [0, 1]; None when unmeasurable."""
    vals = [c for c in (close or []) if c is not None]
    if len(vals) < window * 2:
        return None
    ma = sum(vals[-window:]) / window
    above = sum(1 for c in vals[-window:] if c > ma)
    return above / window


def volatility(close: list[float | None], window: int = 20) -> float | None:
    """Annualized daily-vol estimate (None when too few points)."""
    vals = [c for c in (close or []) if c is not None]
    if len(vals) < window + 1:
        return None
    rets = [vals[i] / vals[i - 1] - 1.0 for i in range(-window, 0) if vals[i - 1]]
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * (252 ** 0.5)


def value_score(pe: float | None, pb: float | None) -> float | None:
    """Cheapness composite in [0, 1]: 1 = cheap on both, 0 = rich.
    Uses only the inputs given; None when neither is present."""
    parts = []
    for ratio in (pe, pb):
        if ratio and ratio > 0:
            # cheapness: 1.0 at 10x, ~0.5 at 20x, -> 0 at 100x (clamped)
            parts.append(max(0.0, min(1.0, 1.0 - (ratio - 10.0) / 90.0)))
    return sum(parts) / len(parts) if parts else None


def quality_score(roe: float | None, margin: float | None) -> float | None:
    """Quality composite in [0, 1]: 1 = strong ROE + margin (normalized by
    plausible top bounds 30% ROE, 25% margin); None when no input."""
    parts = []
    if roe is not None:
        parts.append(max(0.0, min(1.0, roe / 30.0)))
    if margin is not None:
        parts.append(max(0.0, min(1.0, margin / 25.0)))
    return sum(parts) / len(parts) if parts else None


def quant_signal(close: list[float | None],
                 pe: float | None = None, pb: float | None = None,
                 roe: float | None = None, margin: float | None = None,
                 momentum_w: float = 0.3, value_w: float = 0.25,
                 quality_w: float = 0.25, trend_w: float = 0.20) -> dict:
    """Composite quant signal (W1-5): a single z-ish score in roughly [-1, 1]
    plus the per-factor sub-scores. Missing factors drop and weights are
    renormalized over the present set (honest)."""
    comp: dict[str, float] = {}
    m = momentum(close)
    if m is not None:
        comp["momentum"] = max(-1.0, min(1.0, m * 8.0))   # 12.5% move => 1.0
    v = volatility(close)
    if v is not None:
        # low-vol is favored: 1 at 10% annualized, 0 at 40%+
        comp["volatility"] = max(0.0, min(1.0, 1.0 - (v - 0.10) / 0.30))
    t = trend_strength(close)
    if t is not None:
        comp["trend"] = t * 2.0 - 1.0                      # 0..1 -> -1..1
    val = value_score(pe, pb)
    if val is not None:
        comp["value"] = val * 2.0 - 1.0
    q = quality_score(roe, margin)
    if q is not None:
        comp["quality"] = q * 2.0 - 1.0

    if not comp:
        return {"score": None, "components": {}, "weight_used": 0.0}
    w = {"momentum": momentum_w, "value": value_w, "quality": quality_w,
         "trend": trend_w, "volatility": momentum_w * 0.5}
    present = {k: comp[k] for k in comp}
    total_w = sum(w[k] for k in present)
    score = sum(comp[k] * w[k] for k in present) / total_w if total_w else None
    return {"score": round(score, 4) if score is not None else None,
            "components": {k: round(v, 4) for k, v in present.items()},
            "weight_used": round(total_w, 3)}


_RATING_BANDS = [(0.25, "Buy"), (0.05, "Overweight"), (-0.05, "Hold"),
                 (-0.25, "Underweight"), (-1.0, "Sell")]


def baseline_rating(score: float | None) -> str | None:
    """Map the quant composite to the PM's 5-tier scale (quant-only baseline
    rating). None when score is None."""
    if score is None:
        return None
    for thr, label in _RATING_BANDS:
        if score >= thr:
            return label
    return "Sell"


__all__ = ["momentum", "trend_strength", "volatility", "value_score",
           "quality_score", "quant_signal", "baseline_rating", "_RATING_BANDS"]
