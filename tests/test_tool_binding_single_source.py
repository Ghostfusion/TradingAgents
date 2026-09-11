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
