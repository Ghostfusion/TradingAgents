"""R0 - RiskGovernor: deterministic pre-trade risk gate.

Real firms enforce limits with code, not prose. This module checks a decision
(its contract + book context) against a limits registry and returns a verdict:

  PASS   - within limits; nothing for the LLM to argue about
  WARN   - a limit is being approached/breached softly; quantify it
  REJECT - hard limit; execution must not proceed without escalation

Pure and unit-testable; the graph calls it after the position contract.
"""

from __future__ import annotations

LIMITS_KEYS = (
    "max_position_pct",  # per-trade size cap
    "max_book_position_pct",  # total book cap
    "risk_daily_cvar_budget_pct",  # daily tail-loss budget (% of book)
    "risk_max_drawdown_pct",  # realized drawdown stop for new risk
    "sector_cap_limit",  # single-sector cap
)


def default_limits(cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    return {
        "max_position_pct": float(cfg.get("max_position_pct", 0.30)),
        "max_book_position_pct": float(cfg.get("risk_max_position_pct", 0.45)),
        "risk_daily_cvar_budget_pct": float(cfg.get("risk_daily_cvar_budget_pct", 0.03)),
        "risk_max_drawdown_pct": float(cfg.get("risk_max_drawdown_pct", 0.10)),
        "safety_cap_pct": float(cfg.get("sector_cap_limit", 0.35)),
    }


def govern(
    size_pct: float | None,
    cfg: dict | None = None,
    *,
    book_total_pct: float | None = None,
    cvar_pct: float | None = None,
    drawdown_pct: float | None = None,
    sector_pct: float | None = None,
    sector_cap: float | None = None,
    halted: bool = False,
) -> dict:
    """Evaluate decision size against limits; PASS/WARN/REJECT + reasons.

    size_pct: the computed position fraction (0..1). Use None for limits that
    have no data - unknown limits never fail the gate.
    """
    limits = default_limits(cfg)
    reasons = []
    touches = []

    if halted:
        return {"verdict": "REJECT", "reasons": ["risk halt active"], "numbers": "halt=on"}

    if size_pct is None:
        return {"verdict": "PASS", "reasons": [], "numbers": "size unknown"}

    max_pos = limits["max_position_pct"]
    if size_pct > max_pos:
        reasons.append(f"size {size_pct:.1%} > cap {max_pos:.1%}")
    elif size_pct >= 0.9 * max_pos:
        touches.append(f"size {size_pct:.1%} near cap {max_pos:.1%}")

    if book_total_pct is not None:
        max_book = limits["max_book_position_pct"]
        if book_total_pct + size_pct > max_book:
            reasons.append(f"book {book_total_pct + size_pct:.1%} > {max_book:.1%}")

    if cvar_pct is not None:
        budget = limits["risk_daily_cvar_budget_pct"]
        if cvar_pct > budget:
            reasons.append(f"cvar {cvar_pct:.2%} > budget {budget:.2%}")
        elif cvar_pct >= 0.7 * budget:
            touches.append(f"cvar {cvar_pct:.2%} near budget {budget:.2%}")

    if drawdown_pct is not None:
        lim = limits["risk_max_drawdown_pct"]
        if drawdown_pct > lim:
            reasons.append(f"drawdown {drawdown_pct:.1%} > limit {lim:.1%}")

    if sector_pct is not None:
        lim = limits["safety_cap_pct"]
        if sector_pct + (size_pct if sector_pct > 0 else 0.0) > lim:
            reasons.append(f"sector {sector_pct:.1%} near cap {lim:.1%}")

    if reasons:
        return {"verdict": "REJECT", "reasons": reasons, "touches": touches}
    if touches:
        return {"verdict": "WARN", "reasons": [], "touches": touches}
    return {"verdict": "PASS", "reasons": [], "touches": []}


def build_risk_snapshot(
    verdict: dict,
    size_pct: float | None,
    stop_pct: float | None = None,
    cvar_pct: float | None = None,
    drawdown_pct: float | None = None,
) -> str:
    """Compact numbers-only snapshot for the risk debate (kills prose)."""
    parts = [f"verdict={verdict.get('verdict', '?')}"]
    if size_pct is not None:
        parts.append(f"size={size_pct:.1%}")
    if stop_pct is not None:
        parts.append(f"stop={stop_pct:.1%}")
    if cvar_pct is not None:
        parts.append(f"cvar={cvar_pct:.2%}")
    if drawdown_pct is not None:
        parts.append(f"dd={drawdown_pct:.1%}")
    if verdict.get("reasons"):
        parts.append("reasons=" + " | ".join(verdict["reasons"]))
    return "risk snapshot: " + "; ".join(parts)


__all__ = ["LIMITS_KEYS", "default_limits", "govern", "build_risk_snapshot"]
