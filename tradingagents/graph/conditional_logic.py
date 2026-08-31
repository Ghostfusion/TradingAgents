# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.researchers.structured_debate import (
    SECTION_CHANNEL,
    SECTION_ROLES,
)
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
        """Determine if debate should continue (legacy one-shot chain)."""
        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # rounds of back-and-forth between 2 agents
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_structured_debate(
        self, state: AgentState, section: str = "research"
    ) -> str:
        """Router for the SD L1 node (opt-in structured debate).

        Section-aware: ``section="research"`` routes {SD Bull, SD Bear,
        SD L1, SD Finalize}; ``section="risk"`` routes {SD Risk Aggressive,
        SD Risk Conservative, SD Risk Neutral, SD Risk L1, SD Risk Finalize}.

        Returns the next node:
        - terminated / baseline fallback  -> the section's Finalize node
        - PENDING_REGEN (bounded)         -> the same role's node
        - else the next role in the section's order (round continues); when
          the round is complete and the round cap (``max_debate_rounds``)
          is not reached, the first role starts the next round — the depth
          knob drives BOTH sections (direction.md).
        """
        channel = SECTION_CHANNEL[section]
        roles = SECTION_ROLES[section]

        def rn(role: str) -> str:
            return (
                f"SD Risk {role.title()}"
                if section == "risk"
                else f"SD {role.title()}"
            )

        end = "SD Risk Finalize" if section == "risk" else "SD Finalize"
        ds = state.get(channel) or {}
        if ds.get("terminated"):
            return end
        pending = ds.get("pending_regen_role")
        if pending and pending in roles:
            return rn(pending)
        last = ds.get("last_side") or roles[0]
        if last in roles:
            idx = roles.index(last)
            if idx < len(roles) - 1:
                return rn(roles[idx + 1])
            # Round complete. Continue to the next round until the cap
            # (depth knob) is reached; default 1 round keeps the legacy
            # one-shot behavior.
            rounds_done = len(ds.get("score_series") or [])
            max_rounds = int(self.max_debate_rounds or 1)
            if rounds_done < max_rounds:
                return rn(roles[0])
        return end

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
