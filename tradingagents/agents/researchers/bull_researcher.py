from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)


def create_bull_researcher(llm):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)
        computed_context = state.get("computed_decision_context") or ""
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bull Analyst advocating for investing in the {target_label}. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.

**Computed decision context (deterministic, advisory - ground every number you cite in these; never invent your own):**
{computed_context}
""" + get_language_instruction() + get_output_budget("debater")

        response = llm.invoke(prompt)

        from tradingagents.agents.utils.structured import retry_llm_if_truncated

        content = retry_llm_if_truncated(llm, prompt, response.content)
        if not (content or "").strip():
            # A degenerate empty response would render as a bare "Bull
            # Analyst:" marker and starve the debate. Retry once with a
            # completion directive; if still empty, emit an honest note so
            # the Research Manager still has a real (if thin) argument.
            try:
                retry = llm.invoke(
                    "Your previous response contained no argument. Produce a "
                    "brief bull case for this position now, citing only the "
                    "reports and computed context above. If you genuinely "
                    "cannot, state 'no argument available'."
                )
                content = retry.content if hasattr(retry, "content") else str(retry)
            except Exception:  # noqa: BLE001 - degrade to the note
                content = ""
        if not (content or "").strip():
            content = (
                "No argument produced this turn; rely on the analyst reports "
                "and the computed decision context."
            )
        argument = f"Bull Analyst: {content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
