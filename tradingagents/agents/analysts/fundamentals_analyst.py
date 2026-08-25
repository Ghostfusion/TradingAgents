from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_allocation,
    get_analyst_ratings,
    get_analyst_verdict,
    get_balance_sheet,
    get_balance_sheet_health,
    get_basic_financials,
    get_cashflow,
    get_company_peers,
    get_composite_rank,
    get_corporate_actions,
    get_dcf_valuation,
    get_decline_driver_check,
    get_dividends,
    get_earnings_quality,
    get_earnings_surprise,
    get_fcf_yield,
    get_form4_insider,
    get_fundamentals,
    get_income_statement,
    get_insider_activity,
    get_instrument_context_from_state,
    get_language_instruction,
    get_margin_of_safety,
    get_output_budget,
    get_ownership_concentration,
    get_portfolio_weights,
    get_ratios,
    get_revenue_breakdown,
    get_smart_money,
    get_valuation_z_score,
    get_value_dip_setup,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_analyst_ratings,
            get_smart_money,
            get_revenue_breakdown,
            get_corporate_actions,
            get_dividends,
            get_analyst_verdict,
            get_earnings_surprise,
            get_earnings_quality,
            get_portfolio_weights,
            get_basic_financials,
            get_insider_activity,
            get_company_peers,
            get_form4_insider,
            get_ratios,
            get_allocation,
            get_dcf_valuation,
            get_margin_of_safety,
            get_composite_rank,
            get_fcf_yield,
            get_valuation_z_score,
            get_value_dip_setup,
            get_balance_sheet_health,
            get_decline_driver_check,
            get_ownership_concentration,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_analyst_ratings` to benchmark against the sell-side rating and price-target consensus."
            + " You also have quality and smart-money signals: `get_revenue_breakdown(ticker)` for the latest period's segment revenue mix and concentration (a shrinking core segment or heavy single-segment concentration are quality flags); `get_corporate_actions(ticker)` for dividend history and stock splits (consistent dividends signal return discipline); `get_smart_money(ticker)` for ARK fund institutional activity (arbitrary buys/sells); `get_institution_holdings(ticker)` for the institutional share of the float and its period-over-period change (13F-style accumulation/distribution); and `get_earnings_surprise_history(ticker)` for EPS surprise vs estimate per print, the day-of price reaction, and the option-implied move (a succession of beats supports the growth case, negative surprises flag quality risk). Weigh these as supporting signals, not one signal."
            + " You also have computed-analysis tools - ground your 'quality', 'value', 'accounting risk' and 'beat/miss' claims in them: `get_analyst_verdict(ticker, current_date)` returns the deterministic value screens (EY, EV/EBIT, Piotroski F, Beneish M, Altman Z, Net-Net), the collapsed trap-risk verdict with evidence, ROE and EPS/Revenue YoY - quote these numbers rather than re-deriving them; `get_earnings_surprise(ticker, current_date)` returns the standardized last-reported EPS surprise % and its side (beat/miss). `get_dcf_valuation(ticker, current_date, growth=..., erp=...)` returns a provider-sourced discounted-cash-flow fair value (EV, terminal-value share, WACC) - cite it (or its explicit 'unavailable') before any 'undervalued/overvalued on intrinsics' claim; it complements the multiple-based EY/EV-EBIT screens. `get_earnings_quality(ticker, current_date)` returns the Sloan accruals ratio ((net income - operating cash flow) / total assets) folded into the forensic trap verdict with the accrual as extra evidence - cite it (or its explicit 'unavailable') before any 'strong earnings quality / accrual-driven earnings / manipulation risk' claim. "
            + " You also have three Finnhub-powered tools (free tier, key-gated): `get_basic_financials(ticker)` returns the metric block (EPS/revenue YoY growth, ROE/ROA, margins, payout, current ratio) - use it before any growth/quality metric claim; `get_insider_activity(ticker)` returns the net 12-month insider change + latest mspr (use before any net insider-buy/sell claim); `get_company_peers(ticker)` returns the comparable peer group for 'cheap vs peers / relative valuation' reasoning. "
            + " For a multi-name value book, `get_portfolio_weights(...)` computes cap-respecting value weights and `get_allocation(scores, sector_map, ...)` returns the final cap-respected allocation block with per-name weights and the min-names check - report the computed weights when proposing an allocation."
            + " For valuation-safety and cross-sectional standing: `get_margin_of_safety(ticker, intrinsic=...)` reports the (intrinsic - price) / intrinsic safety margin you must cite before any 'undervalued/overvalued' claim (pass ``intrinsic`` from get_dcf_valuation / your own fair-value estimate); `get_composite_rank(ticker)` ranks the ticker among its industry peers cross-sectionally by value+momentum factors (composite percentile 0-1) - cite its standing vs peers before any 'cheap relative to peers / leader in the group' claim."
            + " `get_ratios(ticker)` returns the computed valuation/profitability block (EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, Cash ratio, dividend yield, FCF, market cap) derived from this project's own statements - cite these numbers before any 'cheap / richly valued / quality' claim; missing inputs render n/a (never invented)."
            + " You also have value-dip computed tools (the Value Dip + Swing hybrid, `Strategies/Value_Dip_swing.md`): `get_fcf_yield(ticker, current_date)` returns the free cash flow yield (FCF / market cap; >= 6% is the framework's value-floor row) - cite it before any 'strong cash generation supports the value' claim; `get_valuation_z_score(ticker, current_date, multiple=...)` returns the historical valuation Z (current vs its own trailing P/E, EV/EBITDA or P/FCF; Z <= -1.5 = cheap vs history) - cite it before any 'trades below its historical norm' claim; `get_value_dip_setup(ticker, current_date)` returns the hybrid allocation matrix (value floor + technical entry + trade risk + exit target) as one computed candidate verdict - call it before proposing a value-dip (discounted entry with oversold timing) setup."
            + " You also have two Step-1 fundamental-dip gates: `get_balance_sheet_health(ticker, current_date)` returns the balance-sheet health (debt/equity < 1.0 OR current ratio > 1.5) - cite it before any 'low leverage / strong balance sheet' claim; `get_decline_driver_check(ticker, current_date)` returns the negative-force screen (clean / caution / structural) - if it says 'structural', the dip is company-specific (fraud/distress, deeply negative momentum, negative FCF/ROE, severe EPS decline) and the value-dip setup should be rejected, not bought."
            + " You also have an ownership tool: `get_ownership_concentration(ticker, current_date)` returns the free-float factor (IWF = float / total shares; < 0.5 = structural passive under-allocation) and, when a per-holder breakdown is available, the Herfindahl-Hirschman index (HHI; > 2500 = highly concentrated governance risk) per Strategies/risk2.md - cite it (or its explicit 'unavailable') before any 'widely held / concentrated ownership / index-eligible' claim."
            + get_language_instruction() + get_output_budget("analyst"),
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
