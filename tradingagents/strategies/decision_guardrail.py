"""Deterministic post-PM decision guardrail (DSA research §3.1, pillars 1-3).

Port of `daily_stock_analysis`'s post-LLM deterministic guardrail layer
(`analyzer.py` stabilize_decision_with_structure + risk-cap + canonical
score<->action contract), adapted to this fork's 5-tier `PortfolioRating`
scale and its advisory-only contract.

Invariant (property-tested): the guardrail can ONLY keep a rating or move it
toward Hold (neutral) — it never increases the magnitude of conviction away
from neutral, never flips a rating's sign across zero except to exactly zero,
and never fabricates an override. Every applied override records a `reason`.
The risk governor (hard gate) is untouched; this module is advisory input to
the rendered decision card only.

Rating strength mapping (v1): Buy=2, Overweight=1, Hold=0, Underweight=-1,
Sell=-2. Canonical 0-100 score bands that must agree with the rating.
"""

from __future__ import annotations

RATING_ORDER = ("Sell", "Underweight", "Hold", "Overweight", "Buy")
_STRENGTH = {r: i - 2 for i, r in enumerate(RATING_ORDER)}  # Sell=-2 .. Buy=2

# Canonical 0-100 score <-> rating scale (decision-scale v1). The table is
# embedded here AND in the PM prompt so both sides of the contract see the
# same bands (DSA decision_scale.py pattern).
SCORE_BANDS = ((80, "Buy"), (60, "Overweight"), (40, "Hold"), (20, "Underweight"), (0, "Sell"))


def score_for_rating(rating: str) -> int | None:
    """Lower bound of the canonical score band for a rating; None on unknown."""
    r = str(rating).strip()
    for lo, name in SCORE_BANDS:
        if r.lower() == name.lower():
            return lo
    return None


def score_band_for(score: float | None) -> str | None:
    """Rating implied by a 0-100 score; None for non-finite / out-of-range."""
    if score is None:
        return None
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if not (0 <= s <= 100):
        return None
    for lo, name in SCORE_BANDS:
        if s >= lo:
            return name
    return None


def validate_score_action_agreement(rating: str, score: float | None,
                                    scale_version: str = "v1") -> dict | None:
    """Versioned score<->rating consistency check (advisory, never a fix).

    Returns ``{ok, rating, implied, score}``; ``ok`` is False on a documented
    mismatch (score implies a different rating than the model picked) or when
    ``scale_version`` is unknown. Returns None only for unparseable input.
    """
    if scale_version != "v1":
        return None
    implied = score_band_for(score)
    if implied is None:
        return None
    r = str(rating).strip()
    return {
        "ok": r.lower() == implied.lower(),
        "rating": r,
        "implied": implied,
        "score": score,
    }


def _clamp_toward_hold(strength: int) -> int:
    return 0 if strength > 0 else strength  # positive -> Hold; non-positive keep


def _soften_one_tier(strength: int) -> int:
    """Move one tier toward Hold (never across zero except to zero)."""
    if strength == 0:
        return 0
    return strength - 1 if strength > 0 else strength + 1


def stabilize_decision(
    rating: str,
    risk_rows: list | None = None,
    technical_read: dict | None = None,
    flow_read: dict | None = None,
    overrides: list | None = None,
) -> dict:
    """Deterministic downgrade-only stabilizer over one PM rating.

    Returns ``{"rating": <maybe-changed>, "overrides": [{reason, from, to}]}``
    (``overrides`` is appended to the caller's list when provided). Rules:
      1. risk-cap: any risk row with severity >= "high" caps the rating at
         Hold (never forces a sell by risk alone).
      2. near resistance (price within 2% below a resistance level) WITHOUT
         confirmed inflow -> cap at Hold (buy w/o confirmation near the top).
      3. near support (price within 2% above a support level) WITHOUT confirmed
         outflow on a bearish call -> soften one tier toward Hold (de-risk a
         short into do-nothing; never flips to bullish).
    Unknown ratings / absent context are left unchanged (no fabrication).
    """
    raw = str(rating).strip()
    strength = _STRENGTH.get(raw)
    if strength is None:
        return {"rating": raw, "overrides": list(overrides or [])}
    cur = strength
    applied: list[dict] = []
    out_rating = raw

    def _apply(reason: str, new_strength: int) -> None:
        nonlocal cur, out_rating
        if new_strength == cur:
            return
        cur = new_strength
        out_rating = RATING_ORDER[cur + 2]
        applied.append({"reason": reason, "from": raw, "to": out_rating})

    # Rule 1: risk cap at Hold.
    risk_rows = risk_rows or []
    high_risk = any(
        isinstance(r, dict) and str(r.get("severity", "")).lower() == "high"
        for r in risk_rows
    )
    if high_risk and cur > 0:
        _apply("risk-cap: high-severity risk caps recommendation at Hold", _clamp_toward_hold(cur))

    # Rule 2: near resistance without confirmed inflow.
    if cur > 0 and technical_read and flow_read is not None:
        try:
            price = float(technical_read.get("price"))
            resist = float(technical_read.get("resistance"))
            near_resistance = resist > 0 and price >= resist * 0.98
        except (TypeError, ValueError):
            near_resistance = False
        inflow = bool(flow_read.get("inflow_confirmed")) if isinstance(flow_read, dict) else False
        if near_resistance and not inflow:
            _apply("near-resistance without confirmed inflow caps at Hold", _clamp_toward_hold(cur))

    # Rule 3: bearish call near support without confirmed outflow -> soften.
    if cur < 0 and technical_read and flow_read is not None:
        try:
            price = float(technical_read.get("price"))
            support = float(technical_read.get("support"))
            near_support = support > 0 and price <= support * 1.02
        except (TypeError, ValueError):
            near_support = False
        outflow = bool(flow_read.get("outflow_confirmed")) if isinstance(flow_read, dict) else False
        if near_support and not outflow:
            _apply("near-support without confirmed outflow softens a bearish call", _soften_one_tier(cur))

    merged = list(overrides or []) + applied
    return {"rating": out_rating, "overrides": merged}


def cap_pm_confidence(confidence: float | None, data_quality: str | None,
                      cap: float = 0.7) -> tuple[float | None, str | None]:
    """Cap PM confidence on degraded data quality (DSA confidence gate).

    Returns ``(capped_confidence, reason)``; when ``data_quality`` is
    ``stale``/``partial``/``fallback``/``unknown`` the confidence is capped at
    ``cap`` (or kept if already lower), with a reason; ``fresh``/None passes
    through unchanged (reason None). Never raises.
    """
    if data_quality in (None, "fresh"):
        return confidence, None
    if confidence is None:
        return confidence, None
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return confidence, None
    if c <= cap:
        return confidence, None
    return cap, f"confidence capped at {cap:.2f}: data quality is {data_quality}"


__all__ = [
    "RATING_ORDER",
    "SCORE_BANDS",
    "score_for_rating",
    "score_band_for",
    "validate_score_action_agreement",
    "stabilize_decision",
    "cap_pm_confidence",
]
