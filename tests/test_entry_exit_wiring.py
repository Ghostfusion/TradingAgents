"""§103's entry/exit price block reaches the Trader, the PM and the report.

One assembly per run: ``build_trade_plan`` captures the structured §103
ENTRY/EXIT object it rendered the card from, the graph puts that dict on the
``entry_exit_block`` state channel, and the Trader's node and the PM's node each
append the same rendered block to their own output. So the entry price and the
exit price print where the decision is (``3_trading/trader.md``,
``5_portfolio/decision.md``, the consolidated report) instead of only inside the
report's computed-context dump (section IVa) - and the two surfaces cannot
disagree, because there is one block.

Hermetic: stub LLMs, no network, the advisory verification pass forced to
degrade.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    TraderAction,
    TraderProposal,
)
from tradingagents.agents.trader.trader import create_trader
from tradingagents.strategies.entry_exit_families import (
    ENTRY_MEMBERS,
    EXIT_MEMBERS,
    member as _member,
)

pytestmark = pytest.mark.timeout(120)

#: A realistic captured block: one measurable ceiling, no execution terms, an
#: exit predicate that evaluated two of its conditions.
_BLOCK = {
    "ticker": "TST",
    "reference_price": 100.0,
    "entry": {
        "final_entry_price": 98.5,
        "final_entry_binding": "max_entry_price",
        "final_entry_basis": {"max_entry_price": 99.0, "target_entry_price": 98.5},
        "max_entry_price": 99.0,
        "ceiling_status": "AT_CEILING",
        "ceiling_binding_source": "risk_reward",
        "ceiling_coverage": 1,
        "target_entry_price": 98.5,
        "target_status": "OK",
        "target_coverage": 1,
        "risk_adjusted_entry_price": None,
        "cvar_status": "NO_SOURCE",
        "execution_price": None,
        "execution_buffer": None,
        "execution_coverage": 0,
        "liquidity_status": None,
    },
    "exit": {
        "exit": False,
        "reason": "no exit condition fired",
        "exit_price": 100.0,
        "conditions": {"stop": False, "target": False},
        "coverage": 2,
        "precedence": ["risk_gate", "stop", "target"],
    },
    "levels": {
        "unified_stop": 95.0,
        "trailing_stop": None,
        "trailing_stop_source": None,
        "target": 110.0,
        "target_basis": "T2",
    },
}

_BLOCK_HEADING = "**Entry / Exit price (§103, computed - advisory):**"

# Every §103 name, so the renderer is exercised on the complete object. Two
# members that no run can produce stay absent-with-a-reason, so the test sees
# both shapes: a measured price, and a named absence (never a blank row).
_BLOCK["entry"]["members"] = {
    name: _member(98.5, "fixture: a measured entry family") for name in ENTRY_MEMBERS
}
_BLOCK["entry"]["members"]["final_entry_price"] = _member(
    98.5, "§100: min(target, max) over the terms present; binding max_entry_price"
)
_BLOCK["entry"]["members"]["momentum_entry_price"] = _member(
    None, "no calibrated momentum-score -> price map exists"
)
_BLOCK["exit"]["members"] = {
    name: _member(110.0, "fixture: a measured exit family") for name in EXIT_MEMBERS
}
_BLOCK["exit"]["members"]["stop_loss_price"] = _member(
    95.0, "the plan's unified stop (invalidation)"
)
_BLOCK["exit"]["members"]["event_exit"] = _member(
    None, "needs the forward calendar, which the card is built without"
)


class _StructuredLLM:
    """``with_structured_output`` -> self; ``invoke`` returns the seeded model."""

    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):  # noqa: ARG002 - the fake ignores the prompt
        return self._result


def _pm_state() -> dict:
    """Minimal PM state (mirrors what the risk debate writes)."""
    return {
        "company_of_interest": "TST",
        "risk_debate_state": {
            "history": "Risk debate history.",
            "aggressive_history": "a",
            "conservative_history": "c",
            "neutral_history": "n",
            "judge_decision": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 1,
        },
        "investment_plan": "Research plan.",
        "trader_investment_plan": "Trader plan.",
    }


def _trader_node(monkeypatch):
    """A Trader node whose advisory verification pass is forced to degrade."""

    def _boom(*args, **kwargs):  # noqa: ARG001 - signature unused
        raise RuntimeError("verification disabled in test")

    monkeypatch.setattr("tradingagents.agents.utils.risk_tool_loop.run_tool_loop", _boom)
    return create_trader(
        _StructuredLLM(TraderProposal(action=TraderAction.BUY, reasoning="r"))
    )


def test_the_trader_output_carries_the_103_price_block(monkeypatch):
    node = _trader_node(monkeypatch)
    out = node(
        {
            "company_of_interest": "TST",
            "instrument_context": "TST (Test Corp)",
            "investment_plan": "Buy TST.",
            "entry_exit_block": _BLOCK,
        }
    )
    plan = out["trader_investment_plan"]

    assert _BLOCK_HEADING in plan
    assert "- final_entry_price: 98.50 - §100: min(target, max) over the terms present" in plan
    assert "- stop_loss_price: 95.00 - the plan's unified stop (invalidation)" in plan
    assert "- momentum_entry_price: unavailable - no calibrated momentum-score" in plan
    assert "- event_exit: unavailable - needs the forward calendar" in plan
    assert "- §101 exit predicate:" in plan
    assert "no exit condition fired" in plan


def test_the_pm_decision_carries_the_same_block():
    node = create_portfolio_manager(
        _StructuredLLM(
            PortfolioDecision(
                rating=PortfolioRating.BUY,
                executive_summary="s",
                investment_thesis="t",
                entry_price=98.5,
                price_target=110.0,
                stop_loss=95.0,
            )
        )
    )
    state = _pm_state()
    state["entry_exit_block"] = _BLOCK
    decision = node(state)["final_trade_decision"]

    # The PM's own levels render first...
    assert "**Entry Price**: 98.5" in decision
    assert "**Price Target**: 110.0" in decision
    # ...then the computed block, from the same dict the Trader read.
    assert _BLOCK_HEADING in decision
    assert "- final_entry_price: 98.50" in decision
    # Rating stays the first line: parsers, the CLI and the memory log read it.
    assert decision.startswith("**Rating**: Buy")


def test_a_run_without_a_captured_block_appends_nothing():
    """An older run, or a gate-off run with no card, carries no block: the
    renderer returns "" rather than an empty heading."""
    node = create_portfolio_manager(
        _StructuredLLM(
            PortfolioDecision(
                rating=PortfolioRating.HOLD,
                executive_summary="s",
                investment_thesis="t",
            )
        )
    )
    decision = node(_pm_state())["final_trade_decision"]

    assert "§103" not in decision
    assert "Entry Price" not in decision
