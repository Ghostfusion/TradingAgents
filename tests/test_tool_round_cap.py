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
    # Sentiment binds no tools and has no tool node: its router always goes to
    # the clear node, even if the pool somehow carries a tool call.
    assert logic.should_continue_social(state) == "Msg Clear Sentiment"


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


def test_finalize_messages_empty_turn_retries_on_backup_chain():
    """A cap-forced terminal turn that returns empty content must be re-asked
    ONCE on the backup chain (which carries the tool evidence), not silently
    passed through as \"\" (the QCOM fundamentals / NXPI market 2026-09-07
    pathology: the reasoning model burned its output budget)."""
    from unittest import mock

    from tradingagents.agents.utils.structured import (
        finalize_messages,
    )

    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="")
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="Final market report from backup.")

    out = finalize_messages(chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(), backup_chain=backup)
    assert out == "Final market report from backup."
    assert chain.invoke.call_count == 1
    assert backup.invoke.call_count == 1
    # The retry message history carries the tool evidence regardless of chain.
    retry_msgs = backup.invoke.call_args[0][0]
    assert isinstance(retry_msgs[-1], HumanMessage)
    assert "was empty" in retry_msgs[-1].content
    assert len(retry_msgs) > len(_msgs(MAX_TOOL_ROUNDS - 1, tail="tools"))


def test_finalize_messages_empty_turn_no_backup_retries_same_chain():
    """Without a backup chain, they empty cap turn is re-asked once on the
    same chain, then an explicit unavailable notice is emitted if still empty."""
    from unittest import mock

    from tradingagents.agents.utils.structured import (
        _EMPTY_CAP_PROMPT,
        finalize_messages,
    )

    chain = mock.MagicMock()
    chain.invoke.side_effect = [
        mock.MagicMock(content=""),
        mock.MagicMock(content="recovered report."),
    ]

    out = finalize_messages(chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai())
    assert out == "recovered report."
    assert chain.invoke.call_count ==  2
    # the retry appended the completion directive (never an empty-passthrough).
    retry_msgs = chain.invoke.call_args_list[1][0][0]
    assert isinstance(retry_msgs[-1], HumanMessage)
    assert "was empty" in retry_msgs[-1].content
    assert "empty" in _EMPTY_CAP_PROMPT


def test_finalize_messages_empty_turn_emits_unavailable_when_still_empty():
    """If the backup (or same chain) also returns empty, they function emits
    an explicit \"**Report unavailable**\" notice - never a silent \"\" that would
    land as a bare report-unavailable placeholder in the report tree."""
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="")
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="")

    out = finalize_messages(chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(), backup_chain=backup)
    assert out.startswith("**Report unavailable**")
    assert "**Report unavailable**" in out
    # backup first, then the primary - the terminal turn plus two repairs.
    assert chain.invoke.call_count == 2
    assert backup.invoke.call_count == 1

    # Without a backup the same chain gets the retry and still degrades cleanly.

    chain2 = mock.MagicMock()
    chain2.invoke.side_effect = [
        mock.MagicMock(content=""),
        mock.MagicMock(content=""),
    ]
    out2 = finalize_messages(chain2, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai())
    assert out2.startswith("**Report unavailable**")
    assert chain2.invoke.call_count == 2


def test_finalize_messages_strips_unfulfilled_tool_calls_before_backup_retry():
    """An earlier multi-call turn left half-executed must not reach the backup
    chain: a strict backend (OpenAI/Azure via OpenRouter) 400s a history with
    an unfulfilled tool call (\"No tool output found for function call <id>\",
    TSM 2026-09-07). finalize_messages must strip the orphan, keep the
    fulfilled call, and still return the backup's report."""
    from unittest import mock

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from tradingagents.agents.utils.structured import finalize_messages

    msgs = [
        HumanMessage(content="TSM"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_stock_data", "args": {"ticker": "TSM"}, "id": "c-multi-1", "type": "tool_call"},
                {"name": "get_fundamentals", "args": {"ticker": "TSM"}, "id": "c-multi-2", "type": "tool_call"},
            ],
        ),
        ToolMessage(content="CLOSE 428.91", tool_call_id="c-multi-1", name="get_stock_data"),
        _tool_ai(),  # cap-forced dangling last turn
    ]
    result = _tool_ai()
    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="")
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="Final market report from backup.")

    out = finalize_messages(chain, msgs, result, backup_chain=backup)

    assert out == "Final market report from backup."
    assert chain.invoke.call_count == 1
    assert backup.invoke.call_count == 1
    # The backup saw a clean history: the multi-call turn keeps only the
    # fulfilled call; the orphaned c-multi-2 was stripped.
    sent = backup.invoke.call_args[0][0]
    ai_turns = [m for m in sent if getattr(m, "tool_calls", None)]
    assert len(ai_turns) == 1, "cap tail stripped + orphan merged into one cleaned turn"
    kept_ids = [tc["id"] for tc in ai_turns[0].tool_calls]
    assert kept_ids == ["c-multi-1"]
    assert "c-multi-2" not in kept_ids
    assert isinstance(sent[-1], HumanMessage)


def test_finalize_messages_deorphans_same_chain_when_no_backup():
    """Without a backup, the same-chain retry must also be de-orphaned
    (symmetry with the backup path): the recovered report still arrives."""
    from unittest import mock

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from tradingagents.agents.utils.structured import finalize_messages

    msgs = [
        HumanMessage(content="TSM"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_stock_data", "args": {"ticker": "TSM"}, "id": "o1", "type": "tool_call"},
                {"name": "get_sentiment", "args": {"ticker": "TSM"}, "id": "o2", "type": "tool_call"},
            ],
        ),
        ToolMessage(content="DATA", tool_call_id="o1", name="get_stock_data"),
        _tool_ai(),
    ]
    chain = mock.MagicMock()
    chain.invoke.side_effect = [
        mock.MagicMock(content=""),
        mock.MagicMock(content="recovered report."),
    ]
    out = finalize_messages(chain, msgs, _tool_ai())
    assert out == "recovered report."
    assert chain.invoke.call_count == 2
    second = chain.invoke.call_args_list[1][0][0]
    ai_turns = [m for m in second if getattr(m, "tool_calls", None)]
    assert len(ai_turns) == 1
    kept_ids = [tc["id"] for tc in ai_turns[0].tool_calls]
    assert kept_ids == ["o1"]


def test_finalize_messages_clean_history_passes_through_unchanged():
    """A history with no unfulfilled tool calls must reach the backup chain
    with the SAME tool_calls intact (de-orphan is a no-op on clean input)."""
    from unittest import mock

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from tradingagents.agents.utils.structured import finalize_messages

    msgs = [
        HumanMessage(content="TSM"),
        AIMessage(
            content="",
            tool_calls=[{"name": "get_stock_data", "args": {"ticker": "TSM"}, "id": "p1", "type": "tool_call"}],
        ),
        ToolMessage(content="DATA", tool_call_id="p1", name="get_stock_data"),
        _tool_ai(),
    ]
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="clean report.")
    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="")

    out = finalize_messages(chain, msgs, _tool_ai(), backup_chain=backup)
    assert out == "clean report."
    sent = backup.invoke.call_args[0][0]
    ai_turns = [m for m in sent if getattr(m, "tool_calls", None)]
    kept_ids = [tc["id"] for tc in ai_turns[0].tool_calls]
    assert kept_ids == ["p1"], "clean call passed through untouched"


def test_deorphan_logs_stripped_call_ids(caplog):
    """When _deorphan_tool_calls actually strips an unfulfilled call it must
    log the offending ids so the real orphan mechanism (id reuse / relay
    id-mangling / single-output-of-multi-call) is visible in production, not
    silently swallowed."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from tradingagents.agents.utils.structured import _deorphan_tool_calls

    msgs = [
        HumanMessage(content="TSM"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_stock_data", "args": {"ticker": "TSM"}, "id": "k1", "type": "tool_call"},
                {"name": "get_sentiment", "args": {"ticker": "TSM"}, "id": "k2", "type": "tool_call"},
            ],
        ),
        ToolMessage(content="DATA", tool_call_id="k1", name="get_stock_data"),
    ]
    with caplog.at_level("WARNING", logger="tradingagents.agents.utils.structured"):
        out = _deorphan_tool_calls(msgs)

    # The orphaned k2 was stripped; k1 kept.
    ai_turn = [m for m in out if getattr(m, "tool_calls", None)][0]
    assert [tc["id"] for tc in ai_turn.tool_calls] == ["k1"]
    # The diagnostic names the stripped call and the turn index.
    assert "de-orphaning 1 unfulfilled tool call(s) at message[1]" in caplog.text
    assert "'k2'" in caplog.text
    assert "no tool output" in caplog.text


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


def test_production_setup_research_risk_chain_edges_are_wired():
    """The graph must NOT silently end after the Research Manager. Full chain:
    Bull/Bear debate (conditional -> Research Manager) -> Research Manager ->
    Trader -> Independent Risk Stances -> Aggressive/Conservative/Neutral ->
    Portfolio Manager -> END. A missing edge truncates the saved report at
    '## II. Research Team Decision / Research Manager' with no 3_trading/
    4_risk/ 5_portfolio (regression: SKHY interactive reports 08-30/08-31)."""
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
    graph = setup.setup_graph(("market", "news", "fundamentals")).compile().get_graph()

    def targets(source):
        return {e.target for e in graph.edges if e.source == source}

    # Debate advances to the Research Manager judge.
    assert "Research Manager" in targets("Bull Researcher")
    assert "Research Manager" in targets("Bear Researcher")
    # Research Manager flows ONWARD to the Trader (this is the missing-edge
    # regression).
    assert targets("Research Manager") == {"Trader"}
    assert targets("Trader") == {"Independent Risk Stances"}
    assert targets("Independent Risk Stances") == {"Aggressive Analyst"}
    # Risk debate reaches the Portfolio Manager; PM ends the graph.
    for risk in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst"):
        assert "Portfolio Manager" in targets(risk), f"{risk} missing PM target"
    assert targets("Portfolio Manager") == {"__end__"}


@tool
def _ok_tool(symbol: str) -> str:
    """A well-behaved tool (paired with a sibling that raises)."""
    return f"DATA:{symbol}"


@tool
def _boom_tool(symbol: str) -> str:
    """A tool whose execution raises (simulates moomoo/Massive/fmp vendor churn)."""
    raise RuntimeError("vendor down")


def test_toolnode_handle_errors_keeps_sibling_call_when_one_raises():
    """B1 round containment: a single failing tool in a multi-call assistant
    round must NOT abort the round and drop its sibling's result.

    Regression (2026-09-07): langgraph's DEFAULT ToolNode error handling
    re-raises non-invocation exceptions during the multi-call executor.map, so
    one raising tool lost the ENTIRE round's ToolMessages (the sibling's data
    was dropped AND the failing id became an orphan -> strict backends 400 'no
    tool output found'). With handle_tool_errors=True every call gets a paired
    ToolMessage (the success as data, the failure as an error message), so the
    model still sees the sibling result and no id is left unpaired.
    """
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import ToolNode

    from tradingagents.agents.utils.agent_states import AgentState

    # Analysts build ToolNodes with handle_tool_errors=True (B1).
    tool_node = ToolNode([_ok_tool, _boom_tool], handle_tool_errors=True)

    def analyst(state):
        # Emit ONE multi-call turn (a good tool + a raising tool).
        calls = [
            {"name": "_ok_tool", "args": {"symbol": "TSM"}, "id": "good-1", "type": "tool_call"},
            {"name": "_boom_tool", "args": {"symbol": "TSM"}, "id": "boom-1", "type": "tool_call"},
        ]
        return {"messages": [AIMessage(content="", tool_calls=calls)]}

    def done(state):
        return {"market_report": "END"}

    workflow = StateGraph(AgentState)
    workflow.add_node("Analyst", analyst)
    workflow.add_node("tools_market", tool_node)
    workflow.add_node("Done", done)
    workflow.add_edge(START, "Analyst")
    workflow.add_edge("Analyst", "tools_market")
    workflow.add_edge("tools_market", "Done")
    workflow.add_edge("Done", END)
    graph = workflow.compile()

    final = graph.invoke({"messages": [HumanMessage(content="TSM")]})

    tool_msgs = [m for m in final["messages"] if isinstance(m, ToolMessage)]
    tool_ids = {m.tool_call_id for m in tool_msgs}
    # BOTH calls paired: the ok sibling produced data, the boom sibling an error.
    assert "good-1" in tool_ids, f"sibling result dropped: {tool_ids}"
    assert "boom-1" in tool_ids, f"failing call orphaned: {tool_ids}"
    by_id = {m.tool_call_id: m for m in tool_msgs}
    assert "DATA:TSM" in str(by_id["good-1"].content)
    assert "unavailable" in str(by_id["boom-1"].content).lower() or "error" in str(
        by_id["boom-1"].content
    ).lower()
    assert final["market_report"] == "END"  # round did NOT abort the graph


# Empty cap-forced terminal turn: repair with a raised output budget
# ------------------------------------------------------------------
# Live failure 2026-09-11 (GOOG, news): the cap-forced terminal turn returned
# no text at all and the news report was replaced by the unavailable notice.
# Cause class: reasoning tokens share max_tokens, so a reasoning model can
# spend the whole budget on hidden reasoning before writing a word - and the
# old repair re-asked the SAME question with the SAME cap on the SAME chain,
# reproducing the burn. Measured on the real config (deepseek-v4.1-flash,
# reasoning_effort=high, 44k-token evidence context): 16000 cap -> the turn
# stopped at exactly 16000 output tokens (finish_reason="length"); the same
# input at 32000 finished naturally. The repair now doubles the cap and tries
# the backup chain first, then the primary.


def test_terminal_turn_max_tokens_doubles_the_configured_cap(monkeypatch):
    from tradingagents.agents.utils.structured import _terminal_turn_max_tokens

    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens_quick": 16000},
    )
    assert _terminal_turn_max_tokens() == 32000
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens": 8000},
    )
    assert _terminal_turn_max_tokens() == 16000
    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: {})
    assert _terminal_turn_max_tokens() is None


def test_empty_terminal_turn_repair_raises_the_output_budget(monkeypatch):
    """The repair turn is granted the doubled cap, not the cap that just burned."""
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens_quick": 16000},
    )
    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content="")
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="Final news report from backup.")

    out = finalize_messages(
        chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(),
        backup_chain=backup, agent_name="News Analyst",
    )
    assert out == "Final news report from backup."
    assert backup.invoke.call_args[1] == {"max_tokens": 32000}


def test_empty_terminal_turn_repair_falls_back_to_the_primary(monkeypatch):
    """Backup empty -> the primary is asked too (raised cap), instead of the
    notice. The old code gave up after the single backup attempt."""
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens_quick": 16000},
    )
    chain = mock.MagicMock()
    chain.invoke.side_effect = [
        mock.MagicMock(content=""),                       # cap-forced terminal turn
        mock.MagicMock(content="News report from primary."),  # repair on primary
    ]
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="")

    out = finalize_messages(
        chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(),
        backup_chain=backup, agent_name="News Analyst",
    )
    assert out == "News report from primary."
    assert backup.invoke.call_count == 1
    assert chain.invoke.call_count == 2
    assert backup.invoke.call_args[1] == {"max_tokens": 32000}
    assert chain.invoke.call_args_list[1][1] == {"max_tokens": 32000}


def test_empty_terminal_turn_repair_survives_a_backup_exception(monkeypatch):
    """A backup chain that raises (e.g. its model rejects the tool-bearing
    history) must not lose the repair: the primary is still asked."""
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens_quick": 16000},
    )
    chain = mock.MagicMock()
    chain.invoke.side_effect = [
        mock.MagicMock(content=""),
        mock.MagicMock(content="News report from primary."),
    ]
    backup = mock.MagicMock()
    backup.invoke.side_effect = RuntimeError("400 tool history unsupported")

    out = finalize_messages(
        chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(),
        backup_chain=backup, agent_name="News Analyst",
    )
    assert out == "News report from primary."


def test_empty_terminal_turn_journals_the_forensics(monkeypatch, tmp_path):
    """The unavailable notice must leave a record: the empty turn raises
    nothing, so without this entry the notice is undiagnosable (the live
    2026-09-11 GOOG news failure could not be attributed to a model, a finish
    reason or a token split)."""
    import json
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    journal_dir = tmp_path / "journal"
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"llm_failure_journal_dir": str(journal_dir)},
    )
    empty_turn = AIMessage(
        content="",
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 44042,
            "output_tokens": 16000,
            "total_tokens": 60042,
            "output_token_details": {"reasoning": 15980},
        },
    )
    chain = mock.MagicMock()
    chain.invoke.return_value = empty_turn
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="")

    out = finalize_messages(
        chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(),
        backup_chain=backup, agent_name="News Analyst",
    )
    assert out.startswith("**Report unavailable**")
    files = list(journal_dir.glob("*.json"))
    assert len(files) == 1, f"expected one forensic entry, got {files}"
    entry = json.loads(files[0].read_text(encoding="utf-8"))
    assert entry["stage"] == "finalize_messages/News Analyst"
    assert entry["finish_reason"] == "length"
    assert entry["output_tokens"] == 16000
    assert entry["reasoning_tokens"] == 15980
    assert entry["repaired"] is False
    assert entry["raised_max_tokens"] == 2 * 16000 or entry["raised_max_tokens"] is None
    assert len(entry["repair_outcomes"]) == 2


def test_terminal_turn_reads_block_shaped_content(monkeypatch):
    """A relay that returns content as typed blocks must not be read as empty:
    the old extraction passed the list to ``.strip()``, which raised inside the
    retry path and degraded a real report to the notice."""
    from unittest import mock

    from tradingagents.agents.utils.structured import finalize_messages

    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config", lambda: {},
    )
    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(
        content=[
            {"type": "reasoning", "text": "hidden chain of thought"},
            {"type": "text", "text": "News report body. End."},
        ]
    )

    out = finalize_messages(
        chain, _msgs(MAX_TOOL_ROUNDS - 1, tail="tools"), _tool_ai(),
        agent_name="News Analyst",
    )
    assert out == "News report body. End."
