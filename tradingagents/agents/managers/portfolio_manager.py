"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]

        # Computed risk-debate consensus (deterministic; the PM must cite it, not
        # reinvent alignment from prose). Parse the three analysts' last stances
        # and compute the agreement score + high/low label.
        try:
            from tradingagents.agents.utils.rating import parse_rating
            from tradingagents.strategies.consensus import (
                agreement_score,
                consensus_from_score,
            )
            stances = []
            for key in ("aggressive_history", "conservative_history", "neutral_history"):
                for chunk in (risk_debate_state.get(key) or [])[-3:]:
                    if isinstance(chunk, str):
                        stances.append(parse_rating(chunk))
            score = agreement_score(stances)
            consensus_line = (
                f"**Computed risk-consensus** (deterministic): agreement={score:.2f} "
                f"label={consensus_from_score(score)} (n={len(stances)}) - set your "
                f"PortfolioDecision.consensus to this level, not a guess.\n\n"
                if score is not None
                else "\n"
            )
        except Exception:  # noqa: BLE001 - degrade to no line
            consensus_line = "\n"

        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
{lessons_line}
**Risk Analysts Debate History:**
{history}

{consensus_line}---

Be decisive and ground every conclusion in specific evidence from the analysts.

**Risk-adjusted sizing and conviction (required):**
- Set `position_size` explicitly from the risk debate — scale it down (or to `0% — no new position`) when the analysts flag high volatility, thin liquidity, or elevated downside risk; scale up only when the debate converged on a well-evidenced view. This is the final size that supersedes the trader's proposal.
- Set `stop_loss` from the risk debate's volatility/liquidity assessment (e.g. below a key support level or one ATR from entry) when the decision is to enter or hold a position.
- Set `confidence` (0–1) from how strongly the evidence converged and how robust the data was. Set `consensus` to `low` when the aggressive/conservative/neutral analysts materially disagreed (a dissent flag), and `high` when they broadly aligned.
- Prefer a clear `Hold`/`Underweight`/`Sell` (with `position_size` `0%` or a reduction) over an ambiguous call when the debate is split — a decision to do nothing is a decision.

{NO_EXTERNAL_TOOLS}{get_language_instruction()}"""

        final_trade_decision = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
        }

    return portfolio_manager_node
