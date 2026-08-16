"""Parallel analyst execution (opt-in analyst_concurrency > 1).

Each analyst runs as an isolated subgraph in its own thread with a copy of the
messages, so tool loops never read another analyst's in-flight output. These
tests verify the parallel node produces all reports, executes tool loops, and
merges messages without cross-talk — using fake analyst nodes (no LLM).
"""

import unittest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from tradingagents.graph import setup as graph_setup
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator


@tool
def _fake_data_tool(symbol: str) -> str:
    """Fake vendor tool used to exercise the tool-loop inside a subgraph."""
    return f"DATA:{symbol}"


class ParallelAnalystNodeTests(unittest.TestCase):
    def _build(self, selected=("market", "news"), concurrency=2):
        plan = build_analyst_execution_plan(selected)
        seen = {}

        def make_analyst(key, report_key):
            def node(state):
                msgs = list(state["messages"])
                seen[key] = [getattr(m, "id", None) for m in msgs]
                if not any(getattr(m, "tool_calls", None) for m in msgs):
                    return {
                        "messages": [
                            AIMessage(
                                content="need data",
                                id=f"ai-{key}",
                                tool_calls=[
                                    {
                                        "name": "_fake_data_tool",
                                        "args": {"symbol": "AAPL"},
                                        "id": f"tc-{key}",
                                    }
                                ],
                            )
                        ],
                        report_key: "",
                    }
                return {
                    "messages": [AIMessage(content=f"{key} report", id=f"final-{key}")],
                    report_key: f"{key} report",
                }

            return node

        tool_nodes = {spec.key: ToolNode([_fake_data_tool]) for spec in plan.specs}
        subgraphs = {
            spec.key: graph_setup._build_analyst_subgraph(
                spec,
                lambda k=spec.key, rk=spec.report_key: make_analyst(k, rk),
                tool_nodes[spec.key],
                ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1),
            )
            for spec in plan.specs
        }
        node_fn = graph_setup.make_parallel_analyst_node(plan, subgraphs, concurrency)
        return plan, node_fn, seen

    def test_parallel_node_produces_all_reports_and_runs_tool_loops(self):
        plan, node_fn, seen = self._build()
        state = Propagator().create_initial_state("AAPL", "2026-08-16")
        out = node_fn(state)

        self.assertEqual(out["market_report"], "market report")
        self.assertEqual(out["news_report"], "news report")
        # Tool loops ran: each analyst saw its own AI(tool_call) + ToolMessage.
        for spec in plan.specs:
            self.assertEqual(len(seen[spec.key]), 3, f"{spec.key} saw {seen[spec.key]}")
            # Isolation: the other analyst's tool-call id must NOT appear here.
            for other in plan.specs:
                if other.key != spec.key:
                    self.assertNotIn(f"tc-{other.key}", seen[spec.key])
        # Merged messages contain both finals, deduped.
        merged_ids = {getattr(m, "id", None) for m in out["messages"]}
        for spec in plan.specs:
            self.assertIn(f"final-{spec.key}", merged_ids)

    def test_parallel_node_single_analyst(self):
        plan, node_fn, seen = self._build(selected=("market",))
        state = Propagator().create_initial_state("AAPL", "2026-08-16")
        out = node_fn(state)
        self.assertEqual(out["market_report"], "market report")
        self.assertEqual(len(out["messages"]), 5)  # base + ai + tool + toolmsg + final

    def test_sequential_graph_still_sequential(self):
        """analyst_concurrency=1 must keep the per-analyst node chain."""
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        cfg = DEFAULT_CONFIG.copy()
        ta = TradingAgentsGraph(selected_analysts=("market", "news"), debug=False, config=cfg)
        nodes = set(ta.graph.get_graph().nodes.keys())
        self.assertIn("Market Analyst", nodes)
        self.assertNotIn("Run Analysts", nodes)

    def test_parallel_graph_uses_run_analysts_node(self):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        cfg = DEFAULT_CONFIG.copy()
        cfg["analyst_concurrency"] = 2
        ta = TradingAgentsGraph(selected_analysts=("market", "news"), debug=False, config=cfg)
        nodes = set(ta.graph.get_graph().nodes.keys())
        self.assertIn("Run Analysts", nodes)
        self.assertNotIn("Market Analyst", nodes)


if __name__ == "__main__":
    unittest.main()
