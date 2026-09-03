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


def create_research_manager(llm, fallback_llm=None):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

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

        # Structured-debate judge evidence (direction.md item 6): the L2 judge
        # verdict + L1 deterministic triage feed the Research Manager alongside
        # the bull/bear prose. Advisory — absent when the structured path did
        # not run or produced no judge output.
        from tradingagents.agents.researchers.structured_debate import (
            SECTION_ROLES,
            render_consumer_debate_matrix,
            render_judge_evidence,
        )

        judge_block = render_judge_evidence(state.get("debate_state") or {})
        # P3: replace the raw bull/bear prose with the tabulated Debate
        # Matrix (direction.md). Reporting still writes the full transcripts.
        ds = state.get("debate_state") or {}
        matrix_block = "\n\n**Debate Matrix (deterministic):**\n" + (
            render_consumer_debate_matrix(ds, SECTION_ROLES["research"])
            if ds.get("round_records")
            else "  (no structured debate rounds)"
        )

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader., your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

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

**Debate Matrix:**
{matrix_block}

{independent_block}
{judge_block}

**Computed decision context (deterministic, advisory - ground the plan's numbers in these, never invent your own):**
{computed_context}

{NO_EXTERNAL_TOOLS}""" + get_language_instruction() + get_output_budget("research")

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
            fallback_llm=fallback_llm,
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
