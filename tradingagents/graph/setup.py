# TradingAgents/graph/setup.py

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import (
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_fundamentals_analyst,
    create_market_analyst,
    create_msg_delete,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_sentiment_analyst,
    create_trader,
)
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.independent_vote import (
    create_independent_stance_node,
)

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic

# Every target a shared conditional router can return. Each edge driven by the
# router maps all of them, so a fall-through return (e.g. under prompt/i18n/
# refactor drift in the speaker labels) can never hit a missing path_map entry
# and crash LangGraph mid-run (#1088).
DEBATE_PATH_MAP = {
    "Bull Researcher": "Bull Researcher",
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
}
RISK_ANALYSIS_PATH_MAP = {
    "Aggressive Analyst": "Aggressive Analyst",
    "Conservative Analyst": "Conservative Analyst",
    "Neutral Analyst": "Neutral Analyst",
    "Portfolio Manager": "Portfolio Manager",
}


def _build_analyst_subgraph(spec, analyst_factory, tool_node, conditional_logic):
    """Compile one analyst's isolated tool-calling chain as its own subgraph.

    Used only by the opt-in parallel mode: each analyst runs in a thread with
    a *copy* of the messages so tool loops never read another analyst's
    in-flight output (the shared ``messages[-1]`` routers would otherwise
    mis-route across analysts). The subgraph mirrors the sequential edges:
    analyst → (tools loop | done) — the clear step is a no-op here because
    each thread starts from the same base messages.
    """
    sub = StateGraph(AgentState)
    sub.add_node(spec.agent_node, analyst_factory())
    sub.add_node(spec.tool_node, tool_node)
    sub.add_edge(START, spec.agent_node)
    router = getattr(conditional_logic, f"should_continue_{spec.key}")
    sub.add_conditional_edges(
        spec.agent_node,
        router,
        {f"tools_{spec.key}": spec.tool_node, spec.clear_node: END},
    )
    sub.add_edge(spec.tool_node, spec.agent_node)
    return sub.compile()


def make_parallel_analyst_node(plan, subgraphs, concurrency: int):
    """Return a node that runs all selected analysts concurrently in threads.

    Each thread invokes its analyst's compiled subgraph on an isolated copy of
    the messages; results are merged back (per-analyst report keys, messages
    deduped by id). The debate chain downstream sees the same reports the
    sequential path produces — only the wall-clock is parallel.
    """

    def run_analysts_parallel(state):
        base = list(state.get("messages", []))
        base_ids = {getattr(m, "id", None) for m in base}

        def run_one(spec):
            final = subgraphs[spec.key].invoke(
                {**state, "messages": list(base)},
                config={"recursion_limit": 300},
            )
            return spec, final

        results = {}
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(run_one, spec) for spec in plan.specs]
            for fut in futures:
                spec, final = fut.result()
                results[spec.key] = final

        merged = list(base)
        seen = set(base_ids)
        for spec in plan.specs:
            for m in results[spec.key].get("messages", []):
                mid = getattr(m, "id", None)
                if mid is None or mid not in seen:
                    seen.add(mid)
                    merged.append(m)

        out = dict(state)
        out["messages"] = merged
        for spec in plan.specs:
            out[spec.report_key] = results[spec.key].get(spec.report_key, "")
        return out

    return run_analysts_parallel


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        analyst_concurrency: int = 1,
    ):
        """Initialize with required components.

        ``analyst_concurrency``: >1 runs the analyst teams concurrently
        (each in its own thread with isolated messages); 1 keeps the
        sequential chain. Opt-in — concurrent runs multiply LLM/data load.
        """
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.analyst_concurrency = int(analyst_concurrency or 1)

    def setup_graph(self, selected_analysts=("market", "social", "news", "fundamentals")):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        plan = build_analyst_execution_plan(selected_analysts)

        analyst_factories = {
            "market": lambda: create_market_analyst(self.quick_thinking_llm),
            "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
            "news": lambda: create_news_analyst(self.quick_thinking_llm),
            "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
        }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)
        # Option-A hybrid: ONE independent pre-debate stance per role, sampled
        # with no transcript / opponent responses; the debates below stay the
        # risk-surfacing layer. Nodes no-op when enable_independent_vote is off.
        independent_researcher_node = create_independent_stance_node(
            ("bull", "bear"), self.quick_thinking_llm
        )
        independent_risk_node = create_independent_stance_node(
            ("aggressive", "conservative", "neutral"), self.quick_thinking_llm
        )

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        if self.analyst_concurrency > 1:
            # Parallel: each analyst is an isolated subgraph run in its own
            # thread (see make_parallel_analyst_node); one "Run Analysts" node
            # fans out and joins them before the debate chain.
            subgraphs = {
                spec.key: _build_analyst_subgraph(
                    spec,
                    analyst_factories[spec.key],
                    self.tool_nodes[spec.key],
                    self.conditional_logic,
                )
                for spec in plan.specs
            }
            workflow.add_node(
                "Run Analysts",
                make_parallel_analyst_node(plan, subgraphs, self.analyst_concurrency),
            )
        else:
            for spec in plan.specs:
                workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
                workflow.add_node(spec.clear_node, create_msg_delete())
                workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Independent Researcher Stances", independent_researcher_node)
        workflow.add_node("Independent Risk Stances", independent_risk_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)
        if self.analyst_concurrency > 1:
            workflow.add_edge(START, "Run Analysts")
            workflow.add_edge("Run Analysts", "Bull Researcher")
            workflow.add_edge("Run Analysts", "Independent Researcher Stances")
            workflow.add_edge("Independent Researcher Stances", "Bull Researcher")
        else:
            # Start with the first analyst
            workflow.add_edge(START, plan.specs[0].agent_node)

            # Connect analysts in sequence
            for i, spec in enumerate(plan.specs):
                current_analyst = spec.agent_node
                current_tools = spec.tool_node
                current_clear = spec.clear_node

                # Add conditional edges for current analyst
                workflow.add_conditional_edges(
                    current_analyst,
                    getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                    [current_tools, current_clear],
                )
                # Analyst tool loop: ToolNode feeds back into the analyst node
                # (re-run with the tool results). Without this edge the
                # ToolNode has no outgoing target and LangGraph terminates the
                # graph right after the first tool round - the analyst report
                # stays empty and the debate chain never runs (regression
                # guard: tests/test_graph_tool_loop.py).
                workflow.add_edge(current_tools, current_analyst)
                # Connect to next analyst or to Bull Researcher if this is the last analyst
                if i < len(plan.specs) - 1:
                    workflow.add_edge(current_clear, plan.specs[i + 1].agent_node)
                else:
                    # Independent researcher stances sampled BEFORE the debate;
                    # then the fixed Bull/Bear debate chain runs as before.
                    workflow.add_edge(current_clear, "Independent Researcher Stances")
                    workflow.add_edge("Independent Researcher Stances", "Bull Researcher")

        # Both research-debate edges share the complete DEBATE_PATH_MAP (#1088).
        for debate_node in ("Bull Researcher", "Bear Researcher"):
            workflow.add_conditional_edges(
                debate_node,
                self.conditional_logic.should_continue_debate,
                DEBATE_PATH_MAP,
            )
        workflow.add_edge("Trader", "Independent Risk Stances")
        workflow.add_edge("Independent Risk Stances", "Aggressive Analyst")
        # All three risk edges share the complete RISK_ANALYSIS_PATH_MAP (#1088).
        for risk_node in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst"):
            workflow.add_conditional_edges(
                risk_node,
                self.conditional_logic.should_continue_risk_analysis,
                RISK_ANALYSIS_PATH_MAP,
            )

        workflow.add_edge("Portfolio Manager", END)

        return workflow
