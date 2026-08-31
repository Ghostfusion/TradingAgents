from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)

        trader_decision = state["trader_investment_plan"]
        computed_context = state.get("computed_decision_context") or ""

        prompt = f"""As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative. Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

{instrument_context}
Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here are the last arguments from the conservative analyst: {current_conservative_response} Here are the last arguments from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, not just presenting data. Challenge each counterpoint to underscore why a high-risk approach is optimal. Output conversationally as if you are speaking without any special formatting.

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
        argument = f"Aggressive Analyst: {content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
