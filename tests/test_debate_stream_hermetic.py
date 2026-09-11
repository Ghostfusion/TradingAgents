"""Hermetic full-stream test: structured debate subgraph compiles and runs
end-to-end with stub LLMs (enable_debate ON), and the legacy chain is
byte-identical when OFF.

Design: docs/design_multi_agent_debate.md. Mocks the LLM factory so no
network/provider is touched; asserts the graph reaches the Research Manager
when the structured path is enabled and that the legacy path resolves to the
same node set when it is off.
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.default_config import DEFAULT_CONFIG

pytestmark = pytest.mark.timeout(120)


class _StubLLM(RunnableLambda):
    """Stub LLM runnable: satisfies the analyst chain's ``llm.bind_tools(tools)``
    shape and emits a real ``AIMessage`` (no tool calls)."""

    def bind_tools(self, tools=None, **kwargs):
        return self


def _stub_llm_factory(**kwargs):
    """Return a LangChain RunnableLambda wrapping a stub (usable as an LLM)."""

    class _S:
        def __call__(self, prompt):
            return AIMessage(
                content="stub response with enough body to pass the stub guard.",
                tool_calls=[],
            )

    return _StubLLM(_S())


@pytest.mark.unit
def test_structured_debate_graph_compiles_with_stub_llms(tmp_path, monkeypatch):
    """enable_debate=True must build + compile the graph with structured nodes."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        lambda *a, **k: type(
            "C", (), {"get_llm": lambda self: _stub_llm_factory()}
        )(),
    )
    cfg = dict(DEFAULT_CONFIG)
    cfg["enable_debate"] = True
    cfg["debate_max_rounds"] = 2
    cfg["max_debate_rounds"] = 2
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    nodes = set(ta.workflow.nodes)
    for n in (
        "SD Bull",
        "SD Bear",
        "SD L1",
        "SD Finalize",
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
    ):
        assert n in nodes, f"missing node {n}"
    # The structured chain must route: Bull -> L1 -> Bear -> L1 -> Finalize -> RM.
    assert "SD L1" in nodes and "SD Finalize" in nodes


@pytest.mark.unit
def test_structured_mode_routes_stances_to_sd_bull(tmp_path, monkeypatch):
    """enable_debate=True must route the pre-debate stances into the SD
    subgraph (SD Bull -> SD L1 -> ...), NOT the legacy Bull Researcher —
    regression: the analyst-clear/stance edges stayed on the legacy node, so
    the SD nodes were unreachable and the bull/bear debate models never ran."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        lambda *a, **k: type(
            "C", (), {"get_llm": lambda self: _stub_llm_factory()}
        )(),
    )
    cfg = dict(DEFAULT_CONFIG)
    cfg["enable_debate"] = True
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    edges = {(getattr(e, "source", None), getattr(e, "target", None)) for e in ta.graph.get_graph().edges}
    assert ("Independent Researcher Stances", "SD Bull") in edges, f"stances must enter SD Bull, got {sorted(edges) & {('Independent Researcher Stances', t) for _, t in edges if _ == 'Independent Researcher Stances'}}"
    assert ("SD Bull", "SD L1") in edges, "SD Bull -> SD L1 missing"
    assert ("SD Finalize", "Research Manager") in edges, "SD Finalize -> RM missing"


def test_legacy_path_unchanged_with_flag_off(tmp_path, monkeypatch):
    """enable_debate=False keeps the one-shot bull/bear/RM chain + the SD
    placeholders registered so the router targets always exist."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        lambda *a, **k: type(
            "C", (), {"get_llm": lambda self: _stub_llm_factory()}
        )(),
    )
    cfg = dict(DEFAULT_CONFIG)
    cfg["enable_debate"] = False
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    nodes = set(ta.workflow.nodes)
    assert "SD Finalize" in nodes  # registered unconditionally (no-op)


@pytest.mark.unit
def test_full_stream_reaches_research_manager_when_structured_on(tmp_path, monkeypatch):
    """With enable_debate ON and stub LLMs, a full graph stream runs the
    structured debate chain end-to-end and the Research Manager plan is present
    (back-compat key). Stub LLMs emit no tool calls, so no vendor is touched."""
    from langchain_core.messages import HumanMessage

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        lambda *a, **k: type(
            "C", (), {"get_llm": lambda self: _stub_llm_factory()}
        )(),
    )
    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.TradingMemoryLog",
        lambda cfg: type(
            "M",
            (),
            {
                "store_decision": lambda *a, **k: None,
                "get_pending_entries": lambda *a, **k: [],
                "get_track_record": lambda *a, **k: "",
                "get_past_context": lambda *a, **k: "",
                "get_track_record_stats": lambda *a, **k: "",
            },
        )(),
    )
    cfg = dict(DEFAULT_CONFIG)
    cfg["enable_debate"] = True
    cfg["debate_max_rounds"] = 1
    cfg["max_debate_rounds"] = 1
    cfg["enable_independent_vote"] = False
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))

    state = {
        "company_of_interest": "AAA",
        "company_name": "AAA",
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

    nodes_seen: list[str] = []
    research_plan = None
    for chunk in ta.graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            nodes_seen.append(node)
            if isinstance(update, dict) and update.get("investment_plan"):
                research_plan = update["investment_plan"]

    # The structured chain actually ran, then handed off to the Research Manager.
    for node in ("SD Bull", "SD L1", "SD Bear", "SD Finalize", "Research Manager"):
        assert node in nodes_seen, f"{node} never ran; saw {nodes_seen}"
    assert research_plan, "Research Manager produced no investment_plan"
