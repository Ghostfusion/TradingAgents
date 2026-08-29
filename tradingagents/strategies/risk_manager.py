"""Two-pass risk management that EMITS position-exit overrides (Lean L1).

Lean's ``RiskManagement.ManageRisk(targets) -> IEnumerable<IPortfolioTarget>``
is a second pass that can *override* construction targets with weight-0
(liquidate) or scaled-down targets when a position breaches a risk rule. This
fork's ``risk_governor`` is a *gate* on new risk (PASS/WARN/REJECT); it never
actively shrinks an existing position.

This module provides the missing second pass as a pure function over a
per-symbol state map (entry/peak/current). Advisory by default: callers decide
whether to consume the override targets. No position is ever touched by this
module itself.

``state_by_name`` must be persisted alongside the paper ledger with:
    {'entry': price, 'peak': highest value seen since entry,
     'current': latest price/value}
"""

from __future__ import annotations


def manage_risk(targets: dict, state_by_name: dict,
                max_drawdown_pct: float = 0.05) -> dict | str:
    """Return override targets that liquidate names down ``max_drawdown_pct``
    from their peak (Lean MaximumDrawdownPercentPortfolio / PerSecurity).

    ``targets`` is the current desired weight per symbol (from construction).
    ``state_by_name`` carries ``{'entry', 'peak', 'current'}`` per symbol.

    Returns ``{'overrides': {sym: 0.0 for breached}, 'notes': [...]}`` (each
    breach liquidates that name's target), or the string ``'unavailable'``
    when no state map / peak data exists for a name (callers should skip it,
    never guess).
    """
    if not state_by_name:
        return "unavailable"
    overrides: dict = {}
    notes: list[str] = []
    limit = abs(float(max_drawdown_pct))
    for sym in targets:
        st = state_by_name.get(sym) or {}
        peak = st.get("peak")
        current = st.get("current")
        if peak is None or current is None or float(peak) <= 0:
            notes.append(f"{sym}: no peak/current; skip")
            continue
        dd = float(current) / float(peak) - 1.0
        if dd < -limit:
            overrides[sym] = 0.0
            notes.append(f"{sym}: drawdown {dd:.1%} < -{limit:.1%} -> liquidate")
    return {"overrides": overrides, "notes": notes}


def trailing_stop_targets(targets: dict, state_by_name: dict,
                          trail_pct: float = 0.05) -> dict | str:
    """Lean TrailingStopRiskManagementModel as a pure override pass.

    Liquidate a name whose ``current`` has pulled back ``trail_pct`` below its
    peak. Longer-run positions are force-exit on margin give-back even when
    they are still profitable on entry. Same contract as :func:`manage_risk`.
    """
    if not state_by_name:
        return "unavailable"
    overrides: dict = {}
    notes: list[str] = []
    pct = abs(float(trail_pct))
    for sym in targets:
        st = state_by_name.get(sym) or {}
        peak = st.get("peak")
        current = st.get("current")
        if peak is None or current is None or float(peak) <= 0:
            notes.append(f"{sym}: no peak/current; skip")
            continue
        if float(current) / float(peak) - 1.0 < -pct:
            overrides[sym] = 0.0
            notes.append(f"{sym}: trailing stop struck -> liquidate")
    return {"overrides": overrides, "notes": notes}


__all__ = ["manage_risk", "trailing_stop_targets"]
