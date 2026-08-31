"""Per-analyst tool-round cap (conditional_logic) + finalize_messages tests.

Regression guards for the NVDA empty-market_report root cause: a market
analyst whose tool loop never terminates (model keeps calling tools, or a
slow/hung vendor call keeps the loop spinning) leaves ``market_report == ""``
which reporting.py silently dropped - no market.md at all. The fix:

1. ``ConditionalLogic.should_continue_{market,news,fundamentals}`` force the
   terminal report turn after ``MAX_TOOL_ROUNDS`` tool rounds (routing back to
   the analyst node instead of the tool node).
2. ``structured.finalize_messages`` runs that terminal turn (strips dangling
   tool_calls so the model must answer in prose, one final LLM call).
3. The analyst node wires the cap branch; ``reporting.write_report_tree``
   writes an explicit "report unavailable" block when a report is empty.

Hermetic: fake vendor tools + MagicMock LLMs, no network.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from tradingagents.graph.conditional_logic import MAX_TOOL_ROUNDS, ConditionalLogic

pytestmark = pytest.mark.timeout(180)


def _tool_ai(name: str = "fake") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {"symbol": "NVDA"}, "id": "tc-1"}],
    )


def _msgs(n_tool_rounds: int, tail="tools", tool_name: str = "fake") -> list:
    """Message pool: n AI tool rounds (each followed by a tool result) + tail."""
    msgs: list = [HumanMessage(content="NVDA")]
    for _ in range(n_tool_rounds):
        msgs.append(_tool_ai(tool_name))
        msgs.append(ToolMessage(content="DATA", tool_call_id="tc-1"))
    if tail == "tools":
        msgs.append(_tool_ai(tool_name))
    else:
        msgs.append(AIMessage(content="final report"))
    return msgs


def test_tool_rounds_counts_ai_tool_calls_only():
    msgs = [
        HumanMessage(content="x"),
        _tool_ai(),
        ToolMessage(content="d", tool_call_id="tc-1"),
        _tool_ai(),
        AIMessage(content="report"),
    ]
    assert ConditionalLogic.tool_rounds(msgs) == 2


def test_market_router_under_cap_routes_to_tools():
    logic = ConditionalLogic()
    assert logic.should_continue_market({"messages": _msgs(2)}) == "tools_market"


def test_market_router_at_cap_forces_terminal_report_turn():
    logic = ConditionalLogic()
    state = {"messages": _msgs(MAX_TOOL_ROUNDS - 1, tail="tools")}
    # MAX_TOOL_ROUNDS total tool-call AIs in the pool -> cap hit.
    assert len([m for m in state["messages"] if getattr(m, "tool_calls", None)]) == MAX_TOOL_ROUNDS
    assert logic.should_continue_market(state) == "Market Analyst"


def test_market_router_clear_when_final_prose():
    logic = ConditionalLogic()
    assert logic.should_continue_market({"messages": _msgs(3, tail="prose")}) == "Msg Clear Market"


def test_news_and_fundamentals_router_at_cap():
    logic = ConditionalLogic()
    state = {"messages": _msgs(MAX_TOOL_ROUNDS - 1, tail="tools")}
    assert logic.should_continue_news(state) == "News Analyst"
    assert logic.should_continue_fundamentals(state) == "Fundamentals Analyst"
    # Sentiment binds no tools; it has no loop to cap, so a tool call on its
    # pool still routes to the (nonexistent) tool node - unchanged behavior.
    assert logic.should_continue_social(state) == "tools_social"


def test_router_below_cap_news_fundamentals():
    logic = ConditionalLogic()
    state = {"messages": _msgs(1, tail="tools")}
    assert logic.should_continue_news(state) == "tools_news"
    assert logic.should_continue_fundamentals(state) == "tools_fundamentals"


# ---------------------------------------------------------------------------
# finalize_messages (structured.py)
# ---------------------------------------------------------------------------


def test_finalize_messages_strips_tool_calls_and_runs_terminal_turn():
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="Final market report.")
    msgs = _msgs(MAX_TOOL_ROUNDS - 1, tail="tools")
    result = _tool_ai()

    out = finalize_messages(chain, msgs, result)
    assert out == "Final market report."
    # The dangling tool_calls were stripped: the last message has none.
    inv = chain.invoke.call_args[0][0]
    assert not getattr(inv[-1], "tool_calls", None)


def test_finalize_messages_passthrough_when_no_tool_calls():
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    result = mock.MagicMock(content="Already a report.", tool_calls=[])
    assert finalize_messages(chain, [], result) == "Already a report."
    chain.invoke.assert_not_called()


def test_finalize_messages_degrades_on_chain_failure():
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    chain.invoke.side_effect = RuntimeError("provider down")
    result = mock.MagicMock(content="partial content", tool_calls=[{"name": "x"}])
    assert finalize_messages(chain, [], result) == "partial content"


def test_finalize_messages_merges_truncated_terminal_turn():
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    truncated = "A long market analysis " * 10 + "the trend is"
    msgs = _msgs(MAX_TOOL_ROUNDS - 1, tail="tools")

    # Terminal turn not truncated -> one call.
    chain1 = mock.MagicMock()
    chain1.invoke.return_value = mock.MagicMock(content=truncated + " up. Done.")
    out = finalize_messages(chain1, msgs, _tool_ai())
    assert "up. Done." in out
    assert chain1.invoke.call_count == 1

    # A terminal turn that is itself cut gets one continuation (2 calls total).
    chain2 = mock.MagicMock()
    chain2.invoke.side_effect = [
        mock.MagicMock(content=truncated),
        mock.MagicMock(content=" and the setup is confirmed. End."),
    ]
    out2 = finalize_messages(chain2, msgs, _tool_ai())
    assert "and the setup is confirmed. End." in out2
    assert chain2.invoke.call_count == 2


# ---------------------------------------------------------------------------
# Analyst node wiring: cap turn produces a non-empty report
# ---------------------------------------------------------------------------


def test_market_analyst_cap_turn_produces_report():
    """The market analyst node, on a cap turn (result has tool_calls), runs the
    final-report branch and returns a non-empty market_report."""
    from unittest import mock

    from tradingagents.agents.analysts.market_analyst import create_market_analyst

    llm = mock.MagicMock()
    bind = mock.MagicMock()
    llm.bind_tools.return_value = bind
    # RunnableSequence coerces a plain mock via __call__ (not .invoke): the
    # chain.invoke paths hit bind(...) directly.
    bind.side_effect = [
        # First chain.invoke = the cap turn (emits tool_calls)...
        mock.MagicMock(content="", tool_calls=[{"name": "get_stock_data", "args": {}, "id": "t1"}]),
        # Second = the terminal report turn (prose).
        mock.MagicMock(content="**Market report**: NVDA trend up, RSI 58."),
    ]
    node = create_market_analyst(llm)
    state = {
        "trade_date": "2026-08-29",
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "instrument_context": "",
        "messages": [HumanMessage(content="NVDA")],
    }
    out = node(state)
    assert out["market_report"] == "**Market report**: NVDA trend up, RSI 58."
    assert out["market_report"]  # never empty on a cap turn


@tool
def _fake_tool(symbol: str) -> str:
    """Fake vendor tool."""
    return f"DATA:{symbol}"


def test_compiled_graph_analyst_loop_terminates_after_cap():
    """End-to-end through a small compiled graph: an analyst that ALWAYS
    returns tool_calls still terminates (cap -> terminal report turn) instead
    of looping forever with an empty report."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import ToolNode

    from tradingagents.agents.utils.agent_states import AgentState

    logic = ConditionalLogic()

    def cap_aware(state):
        # Existing tool rounds in the pool decide: under the cap keep calling
        # tools; at the cap write the final report (no more tool_calls).
        n = logic.tool_rounds(state["messages"])
        if n >= MAX_TOOL_ROUNDS:
            return {"messages": [AIMessage(content="done report")], "market_report": "done report"}
        return {"messages": [_tool_ai("_fake_tool")], "market_report": ""}

    workflow = StateGraph(AgentState)
    workflow.add_node("Market Analyst", cap_aware)
    workflow.add_node("tools_market", ToolNode([_fake_tool]))
    workflow.add_node("Msg Clear Market", lambda s: {"messages": [AIMessage(content="cleared")]})
    workflow.add_edge(START, "Market Analyst")
    workflow.add_conditional_edges(
        "Market Analyst",
        logic.should_continue_market,
        ["Market Analyst", "tools_market", "Msg Clear Market"],
    )
    workflow.add_edge("tools_market", "Market Analyst")
    workflow.add_edge("Msg Clear Market", END)
    graph = workflow.compile()

    final = graph.invoke({"messages": [HumanMessage(content="NVDA")]})
    assert final["market_report"] == "done report"
    # Rounds 1..MAX-1 ran through the tool node (one ToolMessage each); the
    # MAX-th AI is the cap round the router routes back to the analyst node,
    # which then writes the final report (matching real flow, where
    # finalize_messages strips that dangling tool call).
    tool_msgs = [m for m in final["messages"] if getattr(m, "type", "") == "tool"]
    assert len(tool_msgs) == MAX_TOOL_ROUNDS - 1
    tool_ais = [m for m in final["messages"] if getattr(m, "tool_calls", None)]
    assert len(tool_ais) == MAX_TOOL_ROUNDS
    assert final["messages"][-1].content == "cleared"


def _edge_targets(graph, source: str) -> set:
    edges = getattr(graph, "edges", None)
    if edges is None:
        return set()
    return {e.target for e in edges if getattr(e, "source", None) == source}


def test_production_setup_registers_analyst_cap_self_loop():
    """Production GraphSetup must register the ANALYST node itself as a
    conditional-edge target for the tool-round-cap routers (the router returns
    'Market Analyst' / 'News Analyst' / 'Fundamentals Analyst' on the cap).
    Without it LangGraph raises ``KeyError 'Market Analyst'`` inside the
    analyst task on the cap turn (regression: SKHY interactive run)."""
    from unittest import mock

    from langchain_core.tools import tool as _tool
    from langgraph.prebuilt import ToolNode

    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import GraphSetup

    @_tool
    def _dummy(_: str) -> str:
        """Dummy tool for edge-map inspection (never invoked)."""
        return "x"

    llm = mock.MagicMock()
    tool_nodes = {
        "market": ToolNode([_dummy]),
        "news": ToolNode([_dummy]),
        "fundamentals": ToolNode([_dummy]),
    }
    setup = GraphSetup(llm, llm, tool_nodes, ConditionalLogic(), analyst_concurrency=1)
    workflow = setup.setup_graph(("market", "news", "fundamentals"))
    graph = workflow.compile().get_graph()
    for node in ("Market Analyst", "News Analyst", "Fundamentals Analyst"):
        assert node in _edge_targets(graph, node), f"{node} missing self-loop cap target"


def test_parallel_subgraph_registers_analyst_cap_self_loop():
    """Same guard for the parallel subgraphs (each analyst subgraph must route
    the cap back to its own analyst node without a KeyError)."""
    from unittest import mock

    from langchain_core.tools import tool as _tool
    from langgraph.prebuilt import ToolNode

    from tradingagents.graph.analyst_execution import build_analyst_execution_plan
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import _build_analyst_subgraph

    @_tool
    def _dummy(_: str) -> str:
        """Dummy tool for subgraph edge-map inspection (never invoked)."""
        return "x"

    llm = mock.MagicMock()
    plan = build_analyst_execution_plan(("market", "news", "fundamentals"))
    tool_node = ToolNode([_dummy])
    logic = ConditionalLogic()
    for spec in plan.specs:
        sub = _build_analyst_subgraph(spec, lambda: llm, tool_node, logic)
        edges = {e.source: e.target for e in sub.get_graph().edges}
        assert spec.agent_node in edges, f"{spec.agent_node} missing subgraph self-loop cap target"
