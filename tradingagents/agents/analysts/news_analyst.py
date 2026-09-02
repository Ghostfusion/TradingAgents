from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_beat_miss_sizing,
    get_catalyst_scale,
    get_credit_spread_read,
    get_earnings_calendar,
    get_earnings_catalyst,
    get_earnings_event_read,
    get_economic_calendar,
    get_fed_watch,
    get_gdelt_sentiment,
    get_global_news,
    get_insider_transactions,
    get_instrument_context_from_state,
    get_ipos,
    get_language_instruction,
    get_macro_indicators,
    get_market_breadth,
    get_massive_news,
    get_news,
    get_news_sentiment,
    get_news_sentiment_series,
    get_output_budget,
    get_prediction_markets,
    get_sec_filings,
)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        asset_type = state.get("asset_type", "stock")
        asset_label = "company" if asset_type == "stock" else "asset"
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_news,
            get_massive_news,
            get_gdelt_sentiment,
            get_news_sentiment_series,
            get_global_news,
            get_macro_indicators,
            get_prediction_markets,
            get_earnings_calendar,
            get_sec_filings,
            get_ipos,
            get_insider_transactions,
            get_economic_calendar,
            get_fed_watch,
            get_market_breadth,
            get_earnings_catalyst,
            get_catalyst_scale,
            get_earnings_event_read,
            get_beat_miss_sizing,
            get_news_sentiment,
            get_credit_spread_read,
        ]

        system_message = (
            f"You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for {asset_label}-specific news by ticker symbol, get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news, get_macro_indicators(indicator, curr_date, look_back_days) to ground macro commentary in actual data from FRED (e.g. 'cpi', 'core_pce', 'unemployment', 'fed_funds_rate', '10y_treasury', 'yield_curve'), get_prediction_markets(topic, limit) for live market-implied probabilities of forward-looking events (e.g. 'Fed rate cut', 'recession 2026', geopolitical or sector events), get_earnings_calendar(ticker, curr_date) for the upcoming earnings date and last reported EPS surprise (a major single-day catalyst), and get_sec_filings(ticker) for recent SEC filings (8-K material events, 10-K/Q reports, S-1/S-3 capital raises, SC 13D/G stake disclosures) as hard event-risk signals beyond headlines — when SEC EDGAR is unavailable it automatically falls back to Massive's Form-4 insider-activity data and the result says so, so you can tell the difference. get_massive_news(ticker, start_date, end_date) also returns news but with per-article structured sentiment (positive/negative/neutral) and sentiment reasoning from Massive.com — use it alongside get_news when you need a computed sentiment label rather than raw headlines. "
            + "You also have scheduled-catalyst and regime tools: economic calendar, fed watch, market breadth, and earnings-catalyst - size the catalyst risk of an incoming print. "
            + "You also have three computed-analysis tools - ground your event claims in them, do not recompute from raw numbers: "
            + "get_catalyst_scale(ticker, curr_date) - one 0..1 risk scale + verdict folded from the next earnings print (with implied move), high-importance macro events and the next FOMC. Use scale/reasons when judging event-window risk; scale=1 means no imminent catalyst. "
            + "get_news_sentiment_series(ticker) - the daily news-sentiment series (score -1..1, 7d SMA, latest innovation, article count) from the EODHD/Alpha-Vantage/GDELT chain. Use it before any 'news sentiment is shifting / at extremes' claim. "
            + "get_earnings_event_read(ticker, curr_date) - the last reported EPS surprise % + side (beat/miss) and the post-earnings drift setup (print-day move, volume vs 2.5x average, consolidation break). Use it before any beat/miss, drift or gap-up claim; it is the computed number. "
            + "get_beat_miss_sizing(side, catalyst) - the deterministic position multiplier implied by a beat/miss side (with the catalyst scale). Use its multiplier when the market will size an event-window position, not a guess. "
            + "You also have macro-risk-off tools: get_credit_spread_read(current_date) returns the FRED ICE BofA HY/CCC/BB OAS credit-cycle band (low/moderate/high/severe) + 0..1 de-risk scale + implied 1y default probability - cite it (or its explicit 'unavailable') before any 'credit stress / risk-off / debt market' claim; get_news_sentiment(ticker, start_date, end_date) returns the daily news-sentiment series from the news_sentiment chain. "
            + " Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_language_instruction() + get_output_budget("analyst")
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        # Tool-round cap turn: the router sent us back because the last
        # message still carries tool_calls after MAX_TOOL_ROUNDS. Do not
        # re-invoke the model for more tools - strip the dangling tool_calls
        # and run one terminal prose turn so the report is never empty and
        # the loop always terminates (no pathological self-loop).
        from langchain_core.messages import AIMessage as _CapAIMessage

        from tradingagents.agents.utils.structured import finalize_messages

        _cap_msg = state["messages"][-1]
        if getattr(_cap_msg, "tool_calls", None):
            _report = finalize_messages(chain, state["messages"], _cap_msg)
            return {
                "messages": [_CapAIMessage(content=_report, id="news-cap-report")],
                "news_report": _report,
            }

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content
            from tradingagents.agents.utils.structured import (
                retry_chain_if_stub,
                retry_chain_if_truncated,
            )

            report = retry_chain_if_truncated(chain, state["messages"], report)
            # A model can answer a tool loop with a bare status turn instead of
            # the report (no tool_calls -> the router takes it as final). Ask it
            # once to deliver the report from the gathered evidence.
            report = retry_chain_if_stub(chain, state["messages"], report, "News Analyst")
        else:
            # Tool-round cap hit: the router forced this turn; the model must
            # write the final report now (dangling tool_calls stripped, one
            # terminal LLM call) so the report is never left empty.
            from tradingagents.agents.utils.structured import finalize_messages

            report = finalize_messages(chain, state["messages"], result)

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
