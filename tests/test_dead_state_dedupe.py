"""Regression tests for the remaining defect-audit items (dead state + dedupe).

Covered here:

* (1a/1b) No agent node writes a state channel the ``AgentState`` TypedDict does
  not declare (LangGraph's write mapper silently drops undeclared keys), and the
  two dead channels — ``security_type`` (fundamentals) and ``sender`` (trader) —
  are gone.
* (2) One shared EMA implementation: ``technical_factors.ema`` is the same
  object the ``extended_indicators`` and ``value_dip`` modules use, so a fourth
  copy cannot creep in silently, and the results agree.
* (3) The DSA per-field integrity retry is reached from the real Research
  Manager agent path: a parsed plan with an empty mandatory field is rebuilt
  before render.
* (4) The sentiment analyst (which binds no tools) has no ``tools_social``
  ToolNode and its router never returns one, while the tool-less subgraph still
  completes a run.
* (5) ``get_sec_filings``' documented ``Args`` match its real signature (both
  derived programmatically, so a phantom arg cannot come back).
"""

from __future__ import annotations

import inspect
import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.schemas import (
    PortfolioRating,
    ResearchPlan,
    TraderAction,
    TraderProposal,
)
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.evidence_gather import TOOL_EVIDENCE_KEY
from tradingagents.graph import setup as graph_setup
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.conditional_logic import ConditionalLogic

# ---------------------------------------------------------------------------
# (1a/1b) dead state channels
# ---------------------------------------------------------------------------


class _FakeToolChain:
    def __init__(self, text):
        self._text = text

    def __call__(self, messages):
        return AIMessage(content=self._text, tool_calls=[])


class _FakeAnalystLLM:
    """bind_tools -> a chain that writes a short final report (no tool calls)."""

    def bind_tools(self, tools):
        return _FakeToolChain("final report")


def _fundamentals_state():
    return {
        "company_of_interest": "MSFT",
        "asset_type": "stock",
        "trade_date": "2026-09-09",
        "instrument_context": "MSFT (Microsoft Corporation)",
        "messages": [HumanMessage(content="Analyze MSFT")],
        TOOL_EVIDENCE_KEY: {},
    }


class _FakeStructuredLLM:
    """with_structured_output -> self; invoke returns the seeded schema object."""

    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):  # noqa: ARG002 - prompt unused by the fake
        return self._result


def test_removed_state_channels_are_not_declared():
    declared = set(AgentState.__annotations__)
    assert "security_type" not in declared
    assert "sender" not in declared


@pytest.mark.unit
def test_fundamentals_node_returns_only_declared_channels():
    from tradingagents.agents.analysts.fundamentals_analyst import (
        create_fundamentals_analyst,
    )

    node = create_fundamentals_analyst(_FakeAnalystLLM(), config={})
    out = node(_fundamentals_state())
    assert set(out) <= set(AgentState.__annotations__)
    assert set(out) == {"messages", "fundamentals_report", "tool_evidence"}
    assert "security_type" not in out


@pytest.mark.unit
def test_trader_node_returns_only_declared_channels(monkeypatch):
    # The advisory verification pass is irrelevant here; force it to degrade so
    # the assertion is about the node's own return contract.
    def _boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("verification disabled in test")

    monkeypatch.setattr(
        "tradingagents.agents.utils.risk_tool_loop.run_tool_loop", _boom
    )
    node = create_trader(
        _FakeStructuredLLM(TraderProposal(action=TraderAction.BUY, reasoning="r"))
    )
    state = {
        "company_of_interest": "MSFT",
        "instrument_context": "MSFT (Microsoft Corporation)",
        "investment_plan": "Buy MSFT.",
    }
    out = node(state)
    assert set(out) <= set(AgentState.__annotations__)
    assert set(out) == {"messages", "trader_investment_plan"}
    assert "sender" not in out


# ---------------------------------------------------------------------------
# (2) one shared EMA
# ---------------------------------------------------------------------------


def test_ema_is_one_shared_object_across_strategy_modules():
    from tradingagents.strategies import (
        extended_indicators as ei,
        technical_factors as tf,
        value_dip as vd,
    )

    assert ei.ema is tf.ema is vd.ema

    series = [100.0 + i for i in range(30)]
    expected = tf.ema(series, 10)
    # Behaviour contract: SMA-seeded, None for the first n-1 bars.
    assert expected[:9] == [None] * 9
    assert expected[9] == pytest.approx(sum(series[:10]) / 10)
    assert ei.ema(series, 10) == expected
    assert vd.ema(series, 10) == expected


# ---------------------------------------------------------------------------
# (3) per-field integrity retry reached from the Research Manager node
# ---------------------------------------------------------------------------


def test_research_manager_rebuilds_result_with_empty_mandatory_field():
    plan_bad = ResearchPlan(
        recommendation=PortfolioRating.BUY,
        rationale="",
        strategic_actions="Build over two weeks.",
    )
    plan_good = ResearchPlan(
        recommendation=PortfolioRating.BUY,
        rationale="Bull case carried the debate.",
        strategic_actions="Build over two weeks.",
    )
    prompts: list = []

    class _RepairingLLM:
        def __init__(self):
            self._calls = 0

        def with_structured_output(self, schema):  # noqa: ARG002
            return self

        def invoke(self, prompt):
            prompts.append(prompt)
            self._calls += 1
            return plan_bad if self._calls == 1 else plan_good

    node = create_research_manager(_RepairingLLM())
    state = {
        "company_of_interest": "NVDA",
        "investment_debate_state": {
            "history": "Bull and bear argued.",
            "bull_history": "Bull...",
            "bear_history": "Bear...",
            "current_response": "",
            "judge_decision": "",
            "count": 1,
        },
    }
    out = node(state)

    assert "Bull case carried the debate." in out["investment_plan"]
    # One structured call + exactly one TARGETED repair on the same model.
    assert len(prompts) == 2
    assert "missing required field" in prompts[1]


# ---------------------------------------------------------------------------
# (4) sentiment analyst has no ToolNode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_social_spec_has_no_tool_node_and_router_never_returns_one():
    spec = build_analyst_execution_plan(("social",)).specs[0]
    assert spec.tool_node is None

    logic = ConditionalLogic()
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "get_news", "args": {}, "id": "1", "type": "tool_call"}],
    )
    assert (
        logic.should_continue_social({"messages": [tool_call_msg]})
        == "Msg Clear Sentiment"
    )


@pytest.mark.unit
def test_sentiment_run_has_no_tools_social_node_and_completes():
    spec = build_analyst_execution_plan(("social",)).specs[0]

    def sentiment_node(state):  # noqa: ARG001 - fake analyst
        return {
            "messages": [AIMessage(content="sentiment report", id="final")],
            "sentiment_report": "sentiment report",
        }

    sub = graph_setup._build_analyst_subgraph(
        spec, lambda: sentiment_node, None, ConditionalLogic()
    )
    graph = sub.get_graph()
    assert "tools_social" not in set(graph.nodes)
    out = sub.invoke({"messages": [HumanMessage(content="AAPL")]})
    assert out["sentiment_report"] == "sentiment report"

    # The sequential graph keeps the analyst -> clear edge and registers no
    # tool node for it either.
    from unittest.mock import MagicMock

    setup = graph_setup.GraphSetup(
        MagicMock(), MagicMock(), {}, ConditionalLogic(), analyst_concurrency=1
    )
    compiled = setup.setup_graph(("social",)).compile().get_graph()
    assert "tools_social" not in set(compiled.nodes)
    assert ("Sentiment Analyst", "Msg Clear Sentiment") in {
        (e.source, e.target) for e in compiled.edges
    }


# ---------------------------------------------------------------------------
# (5) get_sec_filings docstring args match the signature
# ---------------------------------------------------------------------------


def test_get_sec_filings_documented_args_match_signature():
    from tradingagents.agents.utils.market_position_tools import get_sec_filings

    func = getattr(get_sec_filings, "func", get_sec_filings)
    signature = inspect.signature(func)
    params = [p.name for p in signature.parameters.values()]

    doc = inspect.getdoc(func) or ""
    assert "Args:" in doc, "get_sec_filings must document its args"
    args_block = doc.split("Args:", 1)[1].split("Returns:", 1)[0]
    documented = [
        m.group(1)
        for line in args_block.splitlines()
        if (m := re.match(r"^\s*([A-Za-z_]\w*)\s*\(", line))
    ]

    assert documented == params


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
