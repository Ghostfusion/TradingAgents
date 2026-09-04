"""Execution multiplier - two-tier risk policy (halve-not-block material).

Soft guards REDUCE exposure multiplicatively; hard guards BLOCK the order
regardless of any multiplier. ``combine()`` returns the final ``factor``
(product of softs, 0.0 when any hard flag is set) plus a reason list, so the
downstream contract/sizing or the execution OrderGuard treats the two classes
differently instead of folding a hard stop into a 0.1x multiplier.

Soft reasons are catalog-ordered for determinism; hard reasons are listed in
the order provided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SOFT_CATALOG = (
    "regime", "vol_cap", "knife", "drawdown", "liquidity", "momentum", "flow",
)

HARD_NAMES = {
    "halt",
    "insufficient_liquidity",
    "max_portfolio_risk",
    "data_quality_failure",
    "broker_safety",
}


@dataclass(frozen=True)
class RiskMultiplier:
    soft: dict[str, float] = field(default_factory=dict)
    hard: tuple[str, ...] = ()


def combine(multiplier: RiskMultiplier | None = None) -> dict[str, Any]:
    """Combine soft factors and evaluate hard guards into one multiplier.

    Returns ``{factor, blocked, soft_reasons, hard_reasons}``:
      * factor - product of soft values (default 1.0); 0.0 if any hard set
      * blocked - True iff any hard guard is live
      * soft_reasons - only entries with factor < 1.0, catalog order
      * hard_reasons - the live hard flags
    """
    if multiplier is None:
        return {"factor": 1.0, "blocked": False, "soft_reasons": [], "hard_reasons": []}
    soft = {k: float(v) for k, v in multiplier.soft.items() if v is not None}
    hard = tuple(multiplier.hard or ())
    bad_hard = [h for h in hard if h not in HARD_NAMES]
    # unknown hard flags fail SAFE (block) rather than silently passing
    hard = tuple(hard) + tuple(bad_hard)
    factor = 1.0
    for v in soft.values():
        factor *= max(0.0, min(1.0, v))
    blocked = bool(hard)
    if blocked:
        factor = 0.0
    soft_reasons = [k for k in SOFT_CATALOG if k in soft and soft[k] < 1.0]
    hard_reasons = list(hard)
    return {
        "factor": round(factor, 6),
        "blocked": blocked,
        "soft_reasons": soft_reasons,
        "hard_reasons": hard_reasons,
    }


__all__ = ["RiskMultiplier", "combine"]
