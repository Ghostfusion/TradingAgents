"""Hard-gate precedence resolver (review: "hard-gate precedence").

The desk rule the external review demanded (market.md audit): risk controls
sit upstream of execution and compose in a fixed precedence order — the
EARLIEST blocker wins, regardless of how good a lower gate looks:

    KILL (halt/emergency) > PORTFOLIO (drawdown) > TRADE (size/cap) >
    liquidity (ILLIQUID) > regime veto > data quality

This module is the deterministic, pure resolver for that hierarchy. The
graph/tools already enforce the top pieces individually (`risk_governor.govern`
for size/cap, `get_book_tail_risk.drawdown_gate` for portfolio, `halted`
for kill); this ties them into one ordered verdict the analyst and the
guardrail can cite — so a report can never again present
``drawdown_gate=True`` side-by-side with ``risk_ok=True`` without an arbiter.

Pure: no IO, no LLM. Advisory when used in tool output; authoritative when
the graph reads its verdict.
"""

from __future__ import annotations

# Precedence order: earliest key wins a REJECT.
GATE_ORDER: tuple[str, ...] = (
    "kill_switch",   # emergency halt / flatten — highest severity
    "portfolio",     # realized book drawdown beyond limit
    "trade",         # per-trade size / capital-at-risk cap
    "liquidity",     # ILLIQUID / thin market
    "regime",        # regime veto (e.g. no-new-risk regime)
    "data_quality",  # stale/corrupted feed rejects the trade
)

GATE_LABELS: dict[str, str] = {
    "kill_switch": "kill (halt/emergency)",
    "portfolio": "portfolio (drawdown)",
    "trade": "trade (size/capital)",
    "liquidity": "liquidity",
    "regime": "regime veto",
    "data_quality": "data-quality",
}


def evaluate_hierarchy(
    *,
    halt: bool = False,
    drawdown_over: bool | None = None,
    trade_reject: bool | None = None,
    illiquid: bool | None = None,
    regime_veto: bool | None = None,
    data_veto: bool | None = None,
) -> dict:
    """Resolve the risk-gate precedence, earliest REJECT wins.

    Returns ``{"verdict": "PASS"|"REJECT", "blocker": gate_key|None,
    "reason": str}``. A ``None`` gate is "not active" (safe); a truthy gate
    blocks. Mapping: halt -> kill_switch; drawdown_over -> portfolio;
    trade_reject -> trade; illiquid -> liquidity; regime_veto -> regime;
    data_veto -> data_quality. When no gate blocks, PASS with blocker None.
    """
    trigger = {
        "kill_switch": bool(halt),
        "portfolio": bool(drawdown_over),
        "trade": bool(trade_reject),
        "liquidity": bool(illiquid),
        "regime": bool(regime_veto),
        "data_quality": bool(data_veto),
    }
    for gate in GATE_ORDER:
        if trigger[gate]:
            return {
                "verdict": "REJECT",
                "blocker": gate,
                "reason": (
                    f"blocked by {GATE_LABELS[gate]} gate "
                    f"(precedence {GATE_ORDER.index(gate) + 1}/{len(GATE_ORDER)})"
                ),
            }
    return {"verdict": "PASS", "blocker": None, "reason": ""}


def kill_switch_state(
    day_loss_pct: float | None,
    hard_day_limit_pct: float | None = None,
    hard_max_drawdown_pct: float | None = None,
    drawdown_pct: float | None = None,
) -> bool:
    """Kill-switch tier: True when the emergency thresholds are breached.

    ``day_loss_pct``: today's p&l as a fraction (negative = loss). A session
    loss at/under ``hard_day_limit_pct`` (e.g. -0.02) or a book drawdown
    at/over ``hard_max_drawdown_pct`` arms the kill switch. Returns False
    when thresholds are None (no tier configured) or inputs are missing.
    """
    return (
        (
            hard_day_limit_pct is not None
            and day_loss_pct is not None
            and day_loss_pct <= hard_day_limit_pct
        )
        or (
            hard_max_drawdown_pct is not None
            and drawdown_pct is not None
            and drawdown_pct >= hard_max_drawdown_pct
        )
    )


def render_hierarchy(verdict: dict) -> str:
    """Compact render for a tool/prompt block."""
    if not isinstance(verdict, dict):
        return ""
    line = f"risk-hierarchy: {verdict.get('verdict', '?')}"
    if verdict.get("blocker"):
        line += f" blocker={verdict['blocker']}"
    if verdict.get("reason"):
        line += f" reason={verdict['reason']}"
    return line


__all__ = [
    "GATE_ORDER",
    "GATE_LABELS",
    "evaluate_hierarchy",
    "kill_switch_state",
    "render_hierarchy",
]
