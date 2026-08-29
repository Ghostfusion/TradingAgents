# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.utils.agent_states import AgentState

# Per-analyst tool-round cap: how many tool rounds (LLM turns that emitted
# tool_calls) an analyst may run before the graph forces a terminal
# final-report turn. Bounds the analyst tool loop so a model that never stops
# calling tools (or a run near the LangGraph recursion limit) cannot leave the
# analyst report empty ("", which reporting.py would silently drop). Normal
# analysts make well under this many calls; the recursion budget
# (``Propagator.max_recur_limit``, default 100) is shared by all loops.
MAX_TOOL_ROUNDS = 8


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    @staticmethod
    def tool_rounds(messages) -> int:
        """Number of tool rounds in the message pool (AI turns that emitted tool_calls).

        Each analyst loop is self-contained: sequential mode's clear node wipes
        messages between analysts, and the parallel subgraph starts each analyst
        from the shared base messages - so every AI-with-tool_calls message in
        the pool belongs to the analyst whose router is deciding. A HumanMessage
        / ToolMessage never carries tool_calls, so ``getattr`` is safe.
        """
        return sum(1 for m in messages if getattr(m, "tool_calls", None))

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            if self.tool_rounds(messages) >= MAX_TOOL_ROUNDS:
                # Cap hit: force the terminal report turn (the analyst node
                # strips the dangling tool_calls and writes its final report
                # from the evidence gathered) instead of running more tools.
                return "Market Analyst"
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if sentiment-analyst tool round should continue.

        Method name keeps the legacy ``social`` suffix to match the
        ``AnalystType.SOCIAL = "social"`` wire value (saved-config
        back-compat); the returned ``clear_node`` label uses the v0.2.5
        rename so it matches the node registered by the execution plan.
        The sentiment analyst binds no tools (data is in the prompt), so the
        tool-round cap never applies here.
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Sentiment"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            if self.tool_rounds(messages) >= MAX_TOOL_ROUNDS:
                # Cap hit: force the terminal report turn (see should_continue_market).
                return "News Analyst"
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            if self.tool_rounds(messages) >= MAX_TOOL_ROUNDS:
                # Cap hit: force the terminal report turn (see should_continue_market).
                return "Fundamentals Analyst"
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 3 rounds of back-and-forth between 2 agents
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 3 rounds of back-and-forth between 3 agents
            return "Portfolio Manager"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
