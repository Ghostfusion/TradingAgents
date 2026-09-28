"""§103: the complete Entry/Exit price object.

Assembles the phase primitives into the single object ``Strategies/entry_exit.md``
§103 recommends, sitting after the scores and before the decision layer. Every
member is a price the repo measured, or ``None`` with a reason - the assembly
never invents one.

``final_entry_price`` is §100's ``min(target, max)`` over the terms that are
present. **Execution is not a member of that ``min``.** §102 lists it there,
but an execution-adjusted price is a *cost* adjustment, not an independent
economic ceiling, and §100 itself applies the buffer before the min - putting
it inside the min double-counts it (the defect recorded in the plan). It is
reported, and the final is taken over the ceilings alone.

Pure and deterministic. Advisory throughout.
"""

from __future__ import annotations

from tradingagents.strategies.entry_ceiling import entry_ceiling
from tradingagents.strategies.entry_target import entry_target
from tradingagents.strategies.execution_price import execution_price
from tradingagents.strategies.exits import EXIT_PRECEDENCE, exit_decision
from tradingagents.strategies.risk_entry import risk_adjusted_entry

#: The §100 final's members, in declared order (also the tie-break order).
FINAL_ENTRY_TERMS = ("target_entry_price", "max_entry_price", "risk_adjusted_entry_price")


def entry_exit_price(
    *,
    price=None,
    # entry ceilings (§102 / §100's P_entry,max)
    valuation_ceiling=None,
    expected_return_ceiling=None,
    rr_ceiling=None,
    # entry target anchors (§100's P_entry,target)
    valuation_price=None,
    technical_price=None,
    tranche_price=None,
    # risk rule (§68) and its permission half (§87/§88)
    stop=None,
    max_stop_fraction=None,
    name_cvar=None,
    cvar_budget=None,
    # execution (§74-§78)
    execution_spread=None,
    execution_impact=None,
    execution_slippage=None,
    liquidity_status=None,
    # exit (§101)
    trailing_stop=None,
    target=None,
    thesis_break=None,
    risk_gate=None,
    time_exit_fired=None,
    expected_value=None,
) -> dict:
    """Assemble §103's ENTRY and EXIT blocks from the phase primitives."""
    ceiling = entry_ceiling(
        price=price,
        valuation_ceiling=valuation_ceiling,
        expected_return_ceiling=expected_return_ceiling,
        rr_ceiling=rr_ceiling,
    )
    target_entry = entry_target(
        valuation_price=valuation_price,
        technical_price=technical_price,
        tranche_price=tranche_price,
    )
    risk = risk_adjusted_entry(
        stop=stop,
        max_stop_fraction=max_stop_fraction,
        name_cvar=name_cvar,
        cvar_budget=cvar_budget,
    )
    execution = execution_price(
        price=price,
        spread=execution_spread,
        impact=execution_impact,
        slippage=execution_slippage,
        liquidity_status=liquidity_status,
    )

    entry_block: dict = {
        "max_entry_price": ceiling["value"],
        "ceiling_status": ceiling["status"],
        "ceiling_binding_source": ceiling["binding_source"],
        "ceiling_coverage": ceiling["coverage"],
        "target_entry_price": target_entry["value"],
        "target_status": target_entry["status"],
        "target_coverage": target_entry["coverage"],
        "risk_adjusted_entry_price": risk["value"],
        "cvar_status": risk["cvar_status"],
        "execution_price": execution["execution_price"],
        "liquidity_adjusted_entry_price": execution["liquidity_adjusted_entry_price"],
        "execution_coverage": execution["coverage"],
        "execution_buffer": execution["buffer"],
        "liquidity_status": liquidity_status,
    }

    candidates = [
        (term, entry_block[term])
        for term in FINAL_ENTRY_TERMS
        if entry_block[term] is not None
    ]
    if candidates:
        final = min(v for _, v in candidates)
        binding = next(term for term, v in candidates if v == final)
    else:
        final = None
        binding = None
    entry_block["final_entry_price"] = final
    entry_block["final_entry_binding"] = binding
    entry_block["final_entry_basis"] = dict(candidates)

    exit_block = exit_decision(
        close=price,
        stop=stop,
        trailing_stop=trailing_stop,
        target=target,
        thesis_break=thesis_break,
        risk_gate=risk_gate,
        time_exit_fired=time_exit_fired,
        expected_value=expected_value,
    )
    exit_block["precedence"] = list(EXIT_PRECEDENCE)

    return {"entry": entry_block, "exit": exit_block}


__all__ = ["FINAL_ENTRY_TERMS", "entry_exit_price"]
