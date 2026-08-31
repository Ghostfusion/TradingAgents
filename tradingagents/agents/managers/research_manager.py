"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.schemas import ResearchPlan, render_research_plan
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_research_manager(llm):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)
        history = state["investment_debate_state"].get("history", "")

        investment_debate_state = state["investment_debate_state"]
        computed_context = state.get("computed_decision_context") or ""
        # Option-A hybrid: the bull/bear researchers' INDEPENDENT pre-debate
        # reads (sampled before any cross-talk) — an uncontaminated view of
        # how strong each side's case really is, before the adversarial loop
        # converges them. Absent when the flag is off.
        independent_block = ""
        researcher_stances = state.get("researcher_independent_stances") or {}
        if researcher_stances:
            rows = []
            for role in ("bull", "bear"):
                s = researcher_stances.get(role) or {}
                rating = s.get("rating") or "unavailable"
                strength = s.get("strength")
                strength_txt = (
                    f" (strength {int(strength)}/100)"
                    if strength is not None
                    else ""
                )
                reason = (s.get("reason") or "").strip()
                rows.append(
                    f"- **{role.capitalize()}** (independent, pre-debate): "
                    f"{rating}{strength_txt}"
                    + (f" — {reason}" if reason else "")
                )
            independent_block = (
                "\n\n**Independent pre-debate researcher reads** (sampled before "
                "the debate; no cross-talk — use them to judge how robust the "
                "debate's conclusion is):\n" + "\n".join(rows)
            )

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position

Commit to a clear stance whenever the debate's strongest arguments warrant one; reserve Hold for situations where the evidence on both sides is genuinely balanced.

---

**Debate History:**
{history}
{independent_block}

**Computed decision context (deterministic, advisory - ground the plan's numbers in these, never invent your own):**
{computed_context}

{NO_EXTERNAL_TOOLS}""" + get_language_instruction() + get_output_budget("research")

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
