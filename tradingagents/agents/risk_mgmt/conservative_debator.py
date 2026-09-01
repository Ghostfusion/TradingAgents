from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
    opponent_argument_or_opening,
)


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = opponent_argument_or_opening(
            risk_debate_state.get("current_aggressive_response", ""), "aggressive analyst"
        )
        current_neutral_response = opponent_argument_or_opening(
            risk_debate_state.get("current_neutral_response", ""), "neutral analyst"
        )

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)

        trader_decision = state["trader_investment_plan"]
        computed_context = state.get("computed_decision_context") or ""

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

{instrument_context}
Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches. Output conversationally as if you are speaking without any special formatting.

**Computed decision context (deterministic, advisory - ground your risk argument in these numbers, never invent your own):**
{computed_context}

**Risk tools (call before asserting any risk figure):** get_risk_gate (PASS/WARN/REJECT + full limits incl. daily-loss / HWM / liquidity / capital-at-risk), get_tail_risk / get_book_tail_risk / get_tail_decomposition (VaR/CVaR + correlated stress + component tail), get_horizon_var (multi-day), get_downside_read, get_credit_spread_read (credit band + 1y default prob), get_volatility_estimators / get_garch_volatility / get_vol_cones (vol level), get_mean_reversion_quality, get_tranche_plan, get_position_sizing / get_fixed_risk_size (the risk-budget size), get_liquidity_risk (ILLIQ / float turnover / IWF), get_exit_check / get_trailing_exit (exit arithm), get_premarket_review (gap / re-anchor), get_regime_gate_read (knife guard), get_ledger_risk_state (daily-loss / HWM / win-rate), get_exit_overrides (liquidate / shrink), get_pre_trade_read (notional / rate gates), get_trade_plan. If a tool returns 'unavailable', say it is unavailable - never invent the number.
""" + get_language_instruction() + get_output_budget("debater")

        from tradingagents.agents.utils.risk_tool_loop import (
            RISK_DEBATOR_TOOLS,
            run_tool_loop,
        )
        from tradingagents.agents.utils.structured import retry_llm_if_truncated

        content, _transcript = run_tool_loop(llm, prompt, RISK_DEBATOR_TOOLS, max_rounds=2)  # bound runtime: 2 tool rounds per debate turn
        content = retry_llm_if_truncated(llm, prompt, content)
        argument = f"Conservative Analyst: {content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
