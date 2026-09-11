"""Tool binding has one source of truth (S1).

Before this, each analyst bound a hand-written list while
``TradingAgentsGraph._create_tool_nodes`` maintained a *separate*
hand-written list per ToolNode. The two drifted: the fundamentals analyst
bound five ``get_etf_*`` tools that no ToolNode could execute, so on the ETF
path langgraph answered "is not a valid tool" for every call (P0-4), while
the market node carried 14 tools no analyst could bind.

Both sides now read ``tradingagents.agents.toolsets``, so these tests pin the
invariant rather than a list: an analyst's node executes exactly the tools the
analyst may bind - nothing missing (the ETF gap) and nothing extra (the
orphans).
"""

from __future__ import annotations

from tradingagents.agents.toolsets import (
    analyst_toolset,
    fundamentals_company_tools,
    fundamentals_etf_tools,
    market_tools,
    news_tools,
)
from tradingagents.graph.trading_graph import TradingAgentsGraph

# The ETF methodology tools that were bound but unrunnable (P0-4).
_ETF_TOOLS = {
    "get_etf_valuation",
    "get_etf_decline_driver",
    "get_etf_relative_strength",
    "get_etf_risk",
    "get_etf_mechanics",
}


def _nodes():
    # _create_tool_nodes takes no instance state, so it is called directly
    # (no graph build, no vendor access).
    return TradingAgentsGraph._create_tool_nodes(TradingAgentsGraph.__new__(TradingAgentsGraph))


def _names(tools):
    return {t.name for t in tools}


def test_toolnode_matches_analyst_toolset():
    """A ToolNode carries exactly the tools its analyst may bind."""
    nodes = _nodes()
    assert set(nodes) == {"market", "news", "fundamentals"}
    for key, node in nodes.items():
        expected = _names(analyst_toolset(key))
        actual = set(node.tools_by_name)
        assert actual == expected, (
            f"{key} ToolNode drifted from its analyst toolset: "
            f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )


def test_every_bound_tool_has_an_executor():
    """Every tool an analyst can bind (either fundamentals variant) executes."""
    nodes = _nodes()
    bound = {
        "market": market_tools(),
        "news": news_tools(),
        "fundamentals": fundamentals_company_tools() + fundamentals_etf_tools(),
    }
    # The sentiment analyst prefetches its data and binds no tools, so it has
    # no ToolNode and is absent from the node map on purpose.
    for key, tools in bound.items():
        missing = _names(tools) - set(nodes[key].tools_by_name)
        assert not missing, (
            f"{key} analyst binds {sorted(missing)}, which its ToolNode cannot "
            "execute - langgraph would reject the call as an unknown tool"
        )


def test_etf_tools_are_executable():
    """The five ETF methodology tools are runnable on the fundamentals node."""
    node = _nodes()["fundamentals"]
    missing = _ETF_TOOLS - set(node.tools_by_name)
    assert not missing, (
        f"ETF tools bound by the fundamentals analyst have no executor: {sorted(missing)}"
    )


def test_fundamentals_variants_stay_distinct():
    """The ETF swap keeps company statement tools out and the ETF tools in."""
    company = _names(fundamentals_company_tools())
    etf = _names(fundamentals_etf_tools())
    assert etf >= _ETF_TOOLS, f"ETF toolset is missing: {sorted(_ETF_TOOLS - etf)}"
    assert not (_ETF_TOOLS & company), "ETF valuation tools leaked into the company toolset"
    for statement_tool in ("get_balance_sheet", "get_cashflow", "get_income_statement"):
        assert statement_tool not in etf, (
            f"{statement_tool} is a company statement tool; a fund wrapper has none "
            "and its absence must not read as a verdict"
        )


# ---------------------------------------------------------------------------
# Callability is two conditions, and the gate above only proves one of them:
# a tool must be in the agent's `bind_tools` set (or the model cannot emit the
# call) AND dispatachable by its executor. The ETF bug was bind-without-
# executor; the 16 orphan ToolNode entries were executor-without-bind. These
# tests capture the real bind call so the invariant is behavioural, not a
# re-assertion of the same list.
# ---------------------------------------------------------------------------


def _bound_by_node(factory) -> set[str]:
    """The tool list the analyst really hands ``bind_tools``.

    The factories build their tool list inside the node, so the node is
    invoked with a stub LLM and a minimal state. Only the bind call is
    asserted: the node may fail later on the stubbed message, which is
    irrelevant here (and a failure *before* the bind shows up as an unbound
    LLM, which the assertion catches).
    """
    import contextlib
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    llm = MagicMock(name="llm")
    llm.bind_tools.return_value.invoke.return_value = AIMessage(content="ok")
    node = factory(llm, config={})
    state = {
        "trade_date": "2026-09-10",
        "company_of_interest": "AAPL",
        "instrument_context": "",
        "messages": [AIMessage(content="prior")],
    }
    with contextlib.suppress(Exception):  # the stub message is not a report
        node(state)
    assert llm.bind_tools.called, f"{factory.__name__}'s node never bound its tools"
    return {t.name for t in llm.bind_tools.call_args[0][0]}


def test_analyst_nodes_bind_the_toolset_the_node_executes():
    from tradingagents.agents.analysts.market_analyst import create_market_analyst
    from tradingagents.agents.analysts.news_analyst import create_news_analyst

    nodes = _nodes()
    cases = (
        ("market", create_market_analyst, market_tools()),
        ("news", create_news_analyst, news_tools()),
    )
    for key, factory, toolset in cases:
        bound = _bound_by_node(factory)
        assert bound == _names(toolset) == set(nodes[key].tools_by_name), (
            f"{key}: the analyst binds {len(bound)} tools, its toolset has "
            f"{len(toolset)}, its node executes {len(nodes[key].tools_by_name)}"
        )


def test_fundamentals_variants_are_both_executable():
    """The node carries the union, so either variant the node binds runs."""
    executor = set(_nodes()["fundamentals"].tools_by_name)
    for variant in (fundamentals_company_tools(), fundamentals_etf_tools()):
        missing = _names(variant) - executor
        assert not missing, f"fundamentals binds tools its node cannot execute: {sorted(missing)}"


def test_tool_loop_binds_exactly_what_it_executes():
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    from tradingagents.agents.utils.risk_tool_loop import run_tool_loop

    tools = market_tools()[:2]
    llm = MagicMock(name="llm")
    llm.bind_tools.return_value.invoke.return_value = AIMessage(content="ok")
    prose, transcript = run_tool_loop(llm, "prompt", tools, max_rounds=1)
    assert prose == "ok" and transcript == []
    assert llm.bind_tools.call_args[0][0] == tools, (
        "the loop must bind the same list it dispatches - a copy or a rebind "
        "would let the model call a tool the executor does not have"
    )


def test_risk_and_trader_loops_are_populated_and_unique():
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    for label, tools in (
        ("RISK_DEBATOR_TOOLS", risk_tool_loop.RISK_DEBATOR_TOOLS),
        ("TRADER_TOOLS", risk_tool_loop.TRADER_TOOLS),
    ):
        names = [getattr(t, "name", None) for t in tools]
        assert names and all(names), f"{label} is empty or holds a nameless entry"
        assert len(names) == len(set(names)), f"{label} binds a duplicate tool name"

