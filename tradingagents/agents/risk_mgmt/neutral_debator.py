from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)

        trader_decision = state["trader_investment_plan"]
        computed_context = state.get("computed_decision_context") or ""

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

{instrument_context}
Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the conservative analyst: {current_conservative_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting.

**Computed decision context (deterministic, advisory - ground your risk argument in these numbers, never invent your own):**
{computed_context}

**Risk tools (call before asserting any risk figure):** get_risk_gate (PASS/WARN/REJECT + full limits incl. daily-loss / HWM / liquidity / capital-at-risk), get_tail_risk / get_book_tail_risk / get_tail_decomposition (VaR/CVaR + correlated stress + component tail), get_horizon_var (multi-day), get_downside_read, get_credit_spread_read (credit band + 1y default prob), get_volatility_estimators / get_garch_volatility / get_vol_cones (vol level), get_mean_reversion_quality, get_tranche_plan, get_position_sizing / get_fixed_risk_size (the risk-budget size), get_liquidity_risk (ILLIQ / float turnover / IWF), get_exit_check / get_trailing_exit (exit arithm), get_premarket_review (gap / re-anchor), get_regime_gate_read (knife guard), get_ledger_risk_state (daily-loss / HWM / win-rate), get_exit_overrides (liquidate / shrink), get_pre_trade_read (notional / rate gates), get_trade_plan. If a tool returns 'unavailable', say it is unavailable - never invent the number.
""" + get_language_instruction() + get_output_budget("debater")

        from tradingagents.agents.utils.risk_tool_loop import (
            RISK_DEBATOR_TOOLS,
            run_tool_loop,
        )
        from tradingagents.agents.utils.structured import retry_llm_if_truncated

        content, _transcript = run_tool_loop(llm, prompt, RISK_DEBATOR_TOOLS)
        content = retry_llm_if_truncated(llm, prompt, content)
        argument = f"Neutral Analyst: {content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
