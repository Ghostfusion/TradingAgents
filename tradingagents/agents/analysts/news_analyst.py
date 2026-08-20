from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_catalyst_scale,
    get_earnings_calendar,
    get_earnings_catalyst,
    get_earnings_event_read,
    get_economic_calendar,
    get_fed_watch,
    get_global_news,
    get_instrument_context_from_state,
    get_language_instruction,
    get_macro_indicators,
    get_market_breadth,
    get_massive_news,
    get_news,
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
            get_global_news,
            get_macro_indicators,
            get_prediction_markets,
            get_earnings_calendar,
            get_sec_filings,
            get_economic_calendar,
            get_fed_watch,
            get_market_breadth,
            get_earnings_catalyst,
            get_catalyst_scale,
            get_earnings_event_read,
        ]

        system_message = (
            f"You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for {asset_label}-specific news by ticker symbol, get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news, get_macro_indicators(indicator, curr_date, look_back_days) to ground macro commentary in actual data from FRED (e.g. 'cpi', 'core_pce', 'unemployment', 'fed_funds_rate', '10y_treasury', 'yield_curve'), get_prediction_markets(topic, limit) for live market-implied probabilities of forward-looking events (e.g. 'Fed rate cut', 'recession 2026', geopolitical or sector events), get_earnings_calendar(ticker, curr_date) for the upcoming earnings date and last reported EPS surprise (a major single-day catalyst), and get_sec_filings(ticker) for recent SEC filings (8-K material events, 10-K/Q reports, S-1/S-3 capital raises, SC 13D/G stake disclosures) as hard event-risk signals beyond headlines. get_massive_news(ticker, start_date, end_date) also returns news but with per-article structured sentiment (positive/negative/neutral) and sentiment reasoning from Massive.com — use it alongside get_news when you need a computed sentiment label rather than raw headlines. "
            + "You also have scheduled-catalyst and regime tools: economic calendar, fed watch, market breadth, and earnings-catalyst - size the catalyst risk of an incoming print. "
            + "You also have two computed-analysis tools - ground your event claims in them, do not recompute from raw numbers: "
            + "get_catalyst_scale(ticker, curr_date) - one 0..1 risk scale + verdict folded from the next earnings print (with implied move), high-importance macro events and the next FOMC. Use scale/reasons when judging event-window risk; scale=1 means no imminent catalyst. "
            + "get_earnings_event_read(ticker, curr_date) - the last reported EPS surprise % + side (beat/miss) and the post-earnings drift setup (print-day move, volume vs 2.5x average, consolidation break). Use it before any beat/miss, drift or gap-up claim; it is the computed number. "
            + " Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_language_instruction()
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
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
