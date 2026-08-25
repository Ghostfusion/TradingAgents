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
    capital_at_risk_pct: float | None = None,
    risk_cap_pct: float | None = None,
    liquidity_verdict: str | None = None,
    liquidity_dangers: list[str] | None = None,
) -> dict:
    """Evaluate decision size against limits; PASS/WARN/REJECT + reasons.

    size_pct: the computed position fraction (0..1). Use None for limits that
    have no data - unknown limits never fail the gate.

    ``capital_at_risk_pct`` / ``risk_cap_pct`` (both keyword-only, optional)
    add a tranche-scaling control: the worst-case capital exposed at the hard
    stop must stay within the configured risk budget. When ``size_pct`` is the
    peak-deployed-at-scale-in fraction (from a tranche plan), the per-trade cap
    bounds the fully-scaled position, not the first entry. Both default None ->
    the check is skipped, keeping existing callers/tests unchanged.

    ``liquidity_verdict`` / ``liquidity_dangers`` (keyword-only, optional) add
    the risk2.md liquidity/ownership gate: an ILLIQUID verdict REJECTs, a
    CAUTION verdict WARNs. Only active when the caller passes a verdict (the
    graph enables it via ``enable_liquidity_gate``); default None -> skipped,
    preserving current behavior.
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

    if capital_at_risk_pct is not None and risk_cap_pct is not None:
        if capital_at_risk_pct > float(risk_cap_pct):
            reasons.append(f"capital-at-risk {capital_at_risk_pct:.2%} > cap {risk_cap_pct:.2%}")
        elif capital_at_risk_pct >= 0.9 * float(risk_cap_pct):
            touches.append(f"capital-at-risk {capital_at_risk_pct:.2%} near cap {risk_cap_pct:.2%}")

    if drawdown_pct is not None:
        lim = limits["risk_max_drawdown_pct"]
        if drawdown_pct > lim:
            reasons.append(f"drawdown {drawdown_pct:.1%} > limit {lim:.1%}")

    if sector_pct is not None:
        lim = limits["safety_cap_pct"]
        if sector_pct + (size_pct if sector_pct > 0 else 0.0) > lim:
            reasons.append(f"sector {sector_pct:.1%} near cap {lim:.1%}")

    # risk2.md liquidity/ownership gate (opt-in via the caller passing a
    # verdict; the graph enables it with enable_liquidity_gate). ILLIQUID
    # REJECTs, CAUTION WARNs - unknown inputs never fail the gate.
    if liquidity_verdict is not None:
        lv = str(liquidity_verdict).lower()
        if lv == "illiquid":
            reasons.append("liquidity: ILLIQUID")
            if liquidity_dangers:
                reasons.append("liquidity: " + "; ".join(liquidity_dangers))
        elif lv == "caution":
            touches.append("liquidity: CAUTION")
            if liquidity_dangers:
                touches.append("liquidity: " + "; ".join(liquidity_dangers))

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
    capital_at_risk_pct: float | None = None,
) -> str:
    """Compact numbers-only snapshot for the risk debate (kills prose)."""
    parts = [f"verdict={verdict.get('verdict', '?')}"]
    if size_pct is not None:
        parts.append(f"size={size_pct:.1%}")
    if stop_pct is not None:
        parts.append(f"stop={stop_pct:.1%}")
    if cvar_pct is not None:
        parts.append(f"cvar={cvar_pct:.2%}")
    if capital_at_risk_pct is not None:
        parts.append(f"cap_at_risk={capital_at_risk_pct:.2%}")
    if drawdown_pct is not None:
        parts.append(f"dd={drawdown_pct:.1%}")
    if verdict.get("reasons"):
        parts.append("reasons=" + " | ".join(verdict["reasons"]))
    return "risk snapshot: " + "; ".join(parts)


__all__ = ["LIMITS_KEYS", "default_limits", "govern", "build_risk_snapshot"]
