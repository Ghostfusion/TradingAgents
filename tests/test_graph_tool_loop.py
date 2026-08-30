"""Graph regressions: the analyst tool-loop edge + short-closes overlay guard.

Two bugs fixed together:

1. The sequential analyst loop lost its ``ToolNode -> analyst`` edge, so the
   ToolNode became a dead end and the graph TERMINATED right after the market
   analyst's first tool round — empty reports, no debate chain, a stub-only
   report folder (reproduced live: SKHY 2026-08-30). These tests pin the edge
   structurally AND functionally (a streamed run must complete a tool round
   and continue into the debate chain).

2. `build_strategy_overlays` returns None for < 60 bars (thinly-traded ADR /
   new listing); three downstream folds called `.get` on it and logged
   "'NoneType' object has no attribute 'get'". The overlay pipeline must
   no-op cleanly for a short series.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.dataflows.config import set_config


class _FakeChat(GenericFakeChatModel):
    """GenericFakeChatModel is a pydantic model - the analyst chain's
    `prompt | llm.bind_tools(...)` would otherwise raise NotImplementedError.
    A no-op bind_tools is functionally identical for the test."""

    def bind_tools(self, tools=None, **kwargs):
        return self


def _analytic_llm():
    """Scripted model: analyst with one tool round, then a report,
    then the two researchers' debate turns."""
    # A debate can run several alternating turns; script enough responses so
    # the fake LLM never exhausts mid-graph (test breaks at the first debate
    # chunk anyway).
    from itertools import cycle

    debate_turns = cycle(
        [
            "Bull Researcher: Rating: Buy, strong setup.",
            "Bear Researcher: Rating: Sell, overvalued.",
        ]
    )
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_data",
                    "args": {
                        "ticker": "AAA",
                        "start_date": "2026-07-01",
                        "end_date": "2026-08-30",
                    },
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="final market report"),
    ]
    messages.extend(AIMessage(content=next(debate_turns)) for _ in range(28))
    return _FakeChat(messages=iter(messages))


def _fake_tool_node(state: dict) -> dict:
    """Stand-in ToolNode: answers the analyst's tool call with a ToolMessage."""
    return {"messages": [ToolMessage(content="ok 200.0", tool_call_id="1")]}


def _minimal_state() -> dict:
    return {
        "company_of_interest": "AAA",
        "asset_type": "stock",
        "instrument_context": "AAA (Test Corp)",
        "trade_date": "2026-08-30",
        "messages": [HumanMessage(content="AAA")],
        "market_report": "",
        "sentiment_report": "",
        "news_report": "",
        "fundamentals_report": "",
        "past_context": "",
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }


@pytest.mark.unit
def test_every_analyst_tool_node_loops_back_to_analyst():
    """Structural guard for the sequential analyst tool loop.

    Regression: the `ToolNode -> analyst` edge was dropped, turning the ToolNode
    into a Graph-trim dead end. Every analyst's tool node must feed back into its
    analyst node.
    """
    from tradingagents.graph.analyst_execution import build_analyst_execution_plan
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import GraphSetup

    mock = MagicMock()
    tool_nodes = {k: MagicMock() for k in ("market", "social", "news", "fundamentals")}
    gs = GraphSetup(mock, mock, tool_nodes, ConditionalLogic(1, 1), analyst_concurrency=1)
    wf = gs.setup_graph(("market", "social", "news", "fundamentals"))
    edges = {(e.source, e.target) for e in wf.compile().get_graph().edges}

    plan = build_analyst_execution_plan(("market", "social", "news", "fundamentals"))
    for spec in plan.specs:
        assert (spec.tool_node, spec.agent_node) in edges, (
            f"missing analyst tool-loop edge {spec.tool_node} -> {spec.agent_node}"
        )


@pytest.mark.unit
def test_stream_completes_tool_round_and_reaches_debate():
    """Functional guard: a real streamed run must survive a tool round and keep
    going into the debate chain.

    Without the ToolNode->analyst edge the graph STOPS -- no market report, no
    debate; this test would fail on 'market report missing' and 'debate never
    reached'.
    """
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import GraphSetup

    llm = _analytic_llm()
    set_config({"analyst_concurrency": 1, "enable_independent_vote": False})
    tool_nodes = {"market": _fake_tool_node}
    gs = GraphSetup(llm, llm, tool_nodes, ConditionalLogic(8, 8), analyst_concurrency=1)
    graph = gs.setup_graph(("market",)).compile()

    # The seeded debate state (all-empty) is truthy from the first chunk; only
    # treat the debate as reached once an actual argument was made (count > 0).
    seen_reports = []
    seen_debate = False
    for chunk in graph.stream(
        AgentState(_minimal_state()), stream_mode="values"
    ):
        if "market_report" in chunk and chunk["market_report"]:
            seen_reports.append(chunk["market_report"])
        debate = chunk.get("investment_debate_state") or {}
        if debate.get("count", 0) > 0:
            seen_debate = True
            break  # debate reached; enough evidence
    assert "final market report" in seen_reports
    assert seen_debate


@pytest.mark.unit
def test_apply_overlays_noops_on_short_closes(monkeypatch, caplog, mock_llm_client):
    """Short (< 60 bar) OHLCV must degrade the overlay pipeline cleanly.

    Regression: a None overlay from `build_strategy_overlays` crashed the order-flow /
    position-contract / governor folds with "'NoneType' object has no attribute 'get'".
    """
    import tradingagents.default_config as dc
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = dc.DEFAULT_CONFIG.copy()
    cfg.update(
        {
            "enable_strategy_overlays": True,
            "enable_orderflow": True,
            "enable_position_contract": True,
            "enable_risk_governor": True,
            "enable_events": True,
            "enable_computed_context": False,
            "enable_agreement": False,
            "enable_tranche_risk": False,
            "risk_audit_enabled": False,
        }
    )
    ta = TradingAgentsGraph(debug=False, config=cfg)
    ta._try_fetch_closes = lambda ticker: [100.0] * 37  # short series
    monkeypatch.setattr(
        "tradingagents.strategies.orderflow.fetch_flow", lambda ticker: None
    )
    monkeypatch.setattr(
        "tradingagents.strategies.catalyst.fetch_catalyst_data",
        lambda ticker, date: None,
    )
    ta._basket_cvar = lambda ticker: None
    ta._basket_stress = lambda ticker: None

    final_state = {
        "company_of_interest": "SKHY",
        "company_name": "SKHY",
        "asset_type": "stock",
        "trade_date": "2026-08-30",
        "messages": [],
        "market_report": "m",
        "sentiment_report": "s",
        "news_report": "n",
        "fundamentals_report": "f",
        "final_trade_decision": "**Rating**: Hold",
    }
    out = ta._apply_strategy_overlays(final_state, "SKHY")
    assert out is not None  # no exception; overlay-attached state returned
    assert out["final_trade_decision"] == "**Rating**: Hold"
    assert "strategy overlays skipped for SKHY: 37 close bars (< 60 required)" in caplog.text
    assert "position contract skipped" not in caplog.text
    assert "risk governor skipped" not in caplog.text
