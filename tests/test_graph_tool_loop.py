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
    analyst node. The sentiment analyst binds no tools, so it has no tool node
    at all (only its analyst -> clear edge) and is skipped here.
    """
    from tradingagents.graph.analyst_execution import build_analyst_execution_plan
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import GraphSetup

    mock = MagicMock()
    tool_nodes = {k: MagicMock() for k in ("market", "news", "fundamentals")}
    gs = GraphSetup(mock, mock, tool_nodes, ConditionalLogic(1, 1), analyst_concurrency=1)
    wf = gs.setup_graph(("market", "social", "news", "fundamentals"))
    graph = wf.compile().get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    nodes = set(graph.nodes)

    plan = build_analyst_execution_plan(("market", "social", "news", "fundamentals"))
    for spec in plan.specs:
        if spec.tool_node is None:
            # Tool-less analyst (sentiment): no tool node is registered, and the
            # router cannot name one.
            assert "tools_social" not in nodes
            assert "tools_social" not in {t for _, t in edges}
            continue
        assert (spec.tool_node, spec.agent_node) in edges, (
            f"missing analyst tool-loop edge {spec.tool_node} -> {spec.agent_node}"
        )
    # The tool-less sentiment analyst still completes: analyst -> clear node.
    assert ("Sentiment Analyst", "Msg Clear Sentiment") in edges


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
def test_apply_overlays_noops_on_short_closes(monkeypatch, mock_llm_client):
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
    # No exception; the decision is untouched by the short-series degradation.
    assert out["final_trade_decision"] == "**Rating**: Hold"
    # The None overlay is normalized to an empty dict, so the downstream folds
    # run against it instead of raising on ``None.get`` (pre-fix they were
    # skipped by their except handlers and no overlay was attached at all).
    overlay = out["strategy_overlays"]
    assert isinstance(overlay, dict) and overlay
    assert out["position_contract"]  # the position-contract fold executed


@pytest.mark.unit
def test_try_fetch_closes_normalizes_newest_first_vendor_rows(monkeypatch):
    """A vendor that returns OHLCV rows NEWEST-first must not leak an OLDEST
    close as ``closes[-1]`` (the "latest close" every consumer reads: the
    trade-plan reference price, basket return mixes, regime reads).

    Regression: the TSM 2026-09-07 run built its trade-plan card off
    ``closes[-1] = 288.88`` — the OLDEST row EODHD returned, because
    ``_try_fetch_closes`` never re-sorted (the tool-level ``_ohlcv`` did, after
    the ABNB $128.56 incident) — so the analyst's "288.88 trade card" collided
    with the verified 428.91 bar.
    """
    import tradingagents.dataflows.interface as iface
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    # EODHD-style newest-first CSV (Date,Open,High,Low,Close,Volume).
    csv_blocks = "\r\n".join(
        [
            "Date,Open,High,Low,Close,Volume",
            "2026-09-04,421.88,429.82,419.42,428.91,12276300",
            "2026-09-03,413.29,417.29,407.82,417.01,7827800",
            "2026-09-02,413.2,416.5,411.27,415.5,6301000",
            "2026-09-01,405.0,410.0,400.0,402.5,5000000",
        ]
    )
    monkeypatch.setattr(
        iface, "route_to_vendor", lambda *a, **k: csv_blocks
    )
    ta = object.__new__(TradingAgentsGraph)  # skip heavy __init__; method is stateless
    closes = ta._try_fetch_closes("tsm", days=320)
    # Ascending order: oldest date first, so closes[-1] is the LATEST close.
    assert closes == [402.5, 415.5, 417.01, 428.91]
    assert closes[-1] == 428.91  # the verified bar - never 288.88/the oldest row
