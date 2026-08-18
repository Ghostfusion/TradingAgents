"""G3 - measured disagreement / consensus (computed, not narrated)."""

from __future__ import annotations

_RATING_ORDER = {"Buy": 1.0, "Overweight": 0.5, "Hold": 0.0,
                 "Underweight": -0.5, "Sell": -1.0}


def rating_to_number(rating) -> "float | None":
    """Map a 5-tier rating to a numeric stance; None for unknowns."""
    text = str(rating).strip().title() if rating is not None else ""
    return _RATING_ORDER.get(text)


def agreement_score(ratings: list) -> "float | None":
    """1 - normalized range of stances in [0,1]; None when < 2 valid inputs."""
    vals = [rating_to_number(r) for r in ratings]
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    lo, hi = min(vals), max(vals)
    spread = hi - lo  # 0..2
    return max(0.0, min(1.0, 1.0 - spread / 2.0))


def consensus_from_score(score: "float | None", high_at: float = 0.7) -> str:
    """Computed consensus: 'high' when score >= high_at, else 'low'."""
    if score is None:
        return "unknown"
    return "high" if score >= high_at else "low"


__all__ = [
    "rating_to_number", "agreement_score", "consensus_from_score",
]