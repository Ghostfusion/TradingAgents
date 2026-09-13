from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.toolsets import news_tools
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)


def create_news_analyst(llm, backup_llm=None, config=None):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        asset_type = state.get("asset_type", "stock")
        asset_label = "company" if asset_type == "stock" else "asset"
        instrument_context = get_instrument_context_from_state(state)

        tools = news_tools()

        # Forced-tool evidence (map-reduce): gather deterministically once
        # when analyst_forced_tools is set; skipped on tool-loop re-entries.
        from tradingagents.agents.utils.evidence_gather import gather_for_analyst_node

        evidence_block, tool_evidence = gather_for_analyst_node(
            state, "news", tools, config
        )

        system_message = (
            f"You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for {asset_label}-specific news by ticker symbol, get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news, get_macro_indicators(indicator, curr_date, look_back_days) to ground macro commentary in actual data from FRED (e.g. 'cpi', 'core_pce', 'unemployment', 'fed_funds_rate', '10y_treasury', 'yield_curve'), get_prediction_markets(topic, limit) for live market-implied probabilities of forward-looking events (e.g. 'Fed rate cut', 'recession 2026', geopolitical or sector events), get_earnings_calendar(ticker, curr_date) for the upcoming earnings date and last reported EPS surprise (a major single-day catalyst), and get_sec_filings(ticker) for recent SEC filings (8-K material events, 10-K/Q reports, S-1/S-3 capital raises, SC 13D/G stake disclosures) as hard event-risk signals beyond headlines; `get_share_buyback_authorization(ticker, curr_date)` reports trailing-4Q repurchase spend and the ordinary-share-count trend so the insider-selling narrative is balanced against actual corporate buybacks; it explicitly marks the remaining AUTHORIZATION as a company-disclosure item (8-K/release) absent from the vendor feed - so report it unavailable unless an announcement is quoted verbatim — when SEC EDGAR is unavailable it automatically falls back to Massive's Form-4 insider-activity data and the result says so, so you can tell the difference. get_massive_news(ticker, start_date, end_date) also returns news but with per-article structured sentiment (positive/negative/neutral) and sentiment reasoning from Massive.com — use it alongside get_news when you need a computed sentiment label rather than raw headlines. Cite get_news / get_massive_news for the article evidence, get_global_news for the macro tape, get_earnings_calendar for the next print date, get_prediction_markets for event odds and get_sec_filings for the primary document before any claim that depends on them. "
            + "You also have scheduled-catalyst and regime tools: economic calendar, fed watch, market breadth, and earnings-catalyst - size the catalyst risk of an incoming print. "
            + "You also have several computed-analysis tools - ground your event claims in them, do not recompute from raw numbers: "
            + "get_catalyst_scale(ticker, curr_date) - one 0..1 risk scale + verdict folded from the next earnings print (with implied move), high-importance macro events and the next FOMC. Use scale/reasons when judging event-window risk; scale=1 means no imminent catalyst. "
            + "get_news_sentiment_series(ticker) - the daily news-sentiment series (score -1..1, 7d SMA, latest innovation, article count) from the EODHD/Alpha-Vantage/GDELT chain. Use it before any 'news sentiment is shifting / at extremes' claim. "
            + "get_earnings_event_read(ticker, curr_date) - the last reported EPS surprise % + side (beat/miss) and the post-earnings drift setup (print-day move, volume vs 2.5x average, consolidation break). Use it before any beat/miss, drift or gap-up claim; it is the computed number. "
            + "get_beat_miss_sizing(side, catalyst) - the deterministic position multiplier implied by a beat/miss side (with the catalyst scale). Use its multiplier when the market will size an event-window position, not a guess. Cite its multiplier before any 'size up / down into the print' claim. "
            + "You also have macro-risk-off tools: get_credit_spread_read(current_date) returns the FRED ICE BofA HY/CCC/BB OAS credit-cycle band (low/moderate/high/severe) + 0..1 de-risk scale + implied 1y default probability - cite it (or its explicit 'unavailable') before any 'credit stress / risk-off / debt market' claim; get_news_sentiment(ticker, start_date, end_date) returns the daily news-sentiment series from the news_sentiment chain. "
            + "You also have a cross-asset macro tool: get_macro_regime_read(rate_change_bps?, yield_curve_slope_bps?, credit_spread_bps?, dollar_index_chg_pct?, vol_percentile?) folds the same fed / curve / credit / DXY / vol markers you already cite into ONE label (Risk-On / Liquidity-Contraction / Stagflation) - cite it before any 'the tape is risk-on / we are in a liquidity crunch / this is stagflation' claim; unmeasured inputs leave the label unavailable, never invented."
            + "get_taylor_read(policy_rate, inflation, output_gap?) - the Taylor-rule implied policy rate + actual-vs-rule deviation (tight/easy/neutral stance); cite it before any 'the Fed is restrictive / accommodative / rates are off the rule' claim. get_economic_calendar / get_fed_watch give the scheduled-events and rate-probability context. "
            + " You also have liquidity / FX / commodity depth: `get_tga_balance()` returns the daily Treasury General Account operating-cash balance (a falling TGA = reserve injection into the banking system, rising = drain) - cite it before any 'system liquidity / bank reserves / Treasury issuance' claim; `get_fx_snapshot()` returns the DXY + major FX pairs with 1d/5d changes (delayed, advisory) - cite it before any 'USD strength / currency move' claim; and `get_macro_indicators` has extra aliases beyond the default set: 'tga' (WDTGAL), 'reverse_repo' (RRPONTSYD), 'repo' (RPONTSYD), 'fed_balance_sheet' (WALCL), 'effr', 'sofr', 'wti', 'gold', 'natgas', 'copper', 'ecb_rate' (ECBDFR), 'boj_rate' - use them before any 'commodity price / global policy-rate / money-market rate' claim. "
            + "You also have get_news_relevance_read(title, ticker, source_url, snippet) - the deterministic 0-100 relevance score + admission verdict for any news item; use it to rank the highest-signal articles instead of judging by headline alone. Cite its relevance score before any 'this headline matters most' claim. "
            + " Flow and event tools: `get_earnings_catalyst(ticker, current_date)` returns the moomoo earnings-catalyst event (print time + implied move) - pair it with `get_catalyst_scale` when sizing an incoming print; `get_insider_transactions(ticker, start_date, end_date)` returns the windowed insider-transaction flow - cite it before any 'insider buying/selling this week' claim; `get_gdelt_sentiment(ticker)` returns the GDELT aggregate news-sentiment view for the ticker - use it as a cross-check on `get_news_sentiment_series`; `get_market_breadth(ticker)` returns the market-breadth/participation read - cite it before any 'broad or narrow participation' claim; `get_ipos()` returns the upcoming IPO calendar - use it before any 'new-listing / IPO-flow' claim. "
            + " Text-factor tool: `get_disclosure_tone(ticker, current_date)` returns deterministic Loughran-McDonald tone counts, a readability score, and - when a second document for the same firm is available - the filing-vs-news tone and complexity GAPS. Cite it before any 'management sounded confident / the language turned cautious / the filing is opaque' claim; quote the counts and the dictionary version, and treat a zero-hit read as NO SIGNAL, not as neutral. The complexity gap is the more persistent of the two channels. "
            + " Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " HARD CITATION RULE for figures: copy every number you cite VERBATIM"
            " from a tool output (the §Tool Evidence block above or from a tool"
            " you call in this session) - exact digits, never retyped or"
            " reformatted. When you must state a derived percentage or level,"
            " compute it from verbatim-copied inputs. If two tools disagree on"
            " the same quantity (e.g. two ATRs, two 200-day averages, two"
            " moves), quote BOTH with their tool names and flag the conflict -"
            " never splice, substitute, or reconcile silently."
            "  NO SELF-CORRECTION ARTIFACTS: never leave a value in the"
            "  report with an inline (corrected: / correction -) caveat."
            "  If you catch a retype mid-edit, rewrite cleanly - a final"
            "  artifact must never contain a wrong value plus a correction"
            "  marker (HPE 2026-09-10 news.md leaked both 9.87 corrected:"
            "  4.8 and 172.346 correction - 154.3360)."
            "  FOMC DIRECTION: a Fed modal target range is only a hold if"
            "  the CURRENT effective-rate band equals it. Derive the band"
            "  from the effective rate (floor to 25bp) and label the modal"
            "  outcome HIKE/HOLD/CUT - never call a 25bp modal move a"
            "  hold without that check (IREN 2026-09-10: effective 3.63 ->"
            "  band 3.50-3.75, so modal 3.75-4.00% is a HIKE, not a hold;"
            "  the hold-priced framing was wrong)."
            "  Pass current_rate to get_catalyst_scale so it prints the"
            "  modal range + direction; quote that direction verbatim."
            "  CATALYST LABEL: get_catalyst_scale modal_prob is the"
            "  probability of the modal outcome at the event - state the"
            "  outcome and date (e.g. FOMC Sep 15-16: ~73% modal probability"
            "  of a hawkish hold/hike per the event contract), never a bare"
            "  modal 73.4% label (HPE 2026-09-10 left it unstated)."
            "  10Y FRED ID: fetch the 10-year Treasury as DGS10 (or vendor"
            "  10y field), never DGS1 (1-year); label the as-of date with"
            "  the value (a transient 9.87 print in HPE was the wrong"
            "  series id, not a market move)."
            "  MACRO MUSTS: Treasury yields (10Y DGS10), RRP, and EFFR"
            " MUST come from get_macro_indicators(...,'10y_treasury'/'fed_funds_rate'/"
            "'reverse_repo' or a raw FRED id); market-implied probabilities (Fed"
            " cut, recession odds) MUST come from get_prediction_markets; TGA"
            " MUST come from get_tga_balance. A macro number whose tool output is"
            " absent (NO_DATA or never called) is NOT citable - say 'unavailable'"
            " instead of quoting a recalled value (the 10Y-9.78%/4.85% and RRP 0.626B"
            " AMZN 2026-09-09 flags were uncited macro). Never paste a recalled"
            " macro figure into the report."
            " Index-inclusion events (S&P 100/500 additions) are dated by the"
            " index announcement; quote the index date exactly and NEVER assert"
            " a buying/rebalance-window end as fact - call it a potential"
            " index-demand catalyst whose magnitude/timing cannot be assumed"
            " (SNDK 2026-09-10 called the passive-buying window running to"
            " ~Sep 21, which is not part of the announcement)."
            "  EARNINGS DATE: a next-print date from get_earnings_calendar is"
            "  vendor-estimated unless the issuer confirmed it - say vendor-"
            "  estimated next earnings date when quoting it, never imply the"
            "  company announced the date (MSFT 2026-09-10: 2026-10-28 quote"
            "  read as officially confirmed; Microsoft IR had not published it)."
            " SEC filings: 8-K entries surface the SEC generic classification"
            " (material event / M&A / guidance) - not the document content. Do"
            " NOT escalate an 8-K to an unknown material event to flag before"
            " trading because content is not surfaced; say routine disclosure"
            " with the filing type and date, e.g. FY2027 segment/investor-"
            " metric restructuring (MSFT 2026-09-02 8-K) - not an unidentified"
            " corporate shock."
            " One EPS-estimate value per earnings date: the calendar returns"
            " exactly one estimate per print - never quote two different est"
            " figures for the same date (MSFT 2026-09-10: 4.72 headline/table"
            " vs 4.16 forward-calendar for 2026-10-28)."
            " Insider rows: repeated sells by one officer/director should be"
            " calibrated to 10b5-1 reality - scheduled sales under a plan are"
            " not discretionary bearish conviction (SNDK 2026-09-10 CTO sold"
            " under a 10b5-1 plan adopted 2026-06-04); call it persistent"
            " selling, not the strongest negative tell."
            " Macro/credit levels: one timestamp per series - never quote the"
            " same OAS/yield at two values in one report (SNDK 2026-09-10"
            " HY OAS 2.71 body vs 2.59 table is a cache replication slip)."

            + " DAY COUNTS: quote the tool's own countdown (`in Nd` from"
            " get_earnings_calendar, `fomc Nd out` / `earnings <date> in Nd` from"
            " get_catalyst_scale) - never compute days-to-catalyst yourself. The"
            " wrong base date shifts it silently: NVDA 2026-09-12 news.md called"
            " the next print '83 days away', which is the gap from the PRIOR print"
            " (2026-08-26 -> 2026-11-17); from the analysis date the count was 66."
            + " Summary-table figures must MATCH their body figures exactly"
            " (same digits, same units/scales - never drop, substitute or"
            " abbreviate a figure into a stale one. e.g. a Q2 AI-orders row"
            " that the body states as $61B must show $61B in the table, not"
            " the prior-quarter's $2B). DELL 2026-09-10 news.md lost the"
            " $61B AI-orders figure in its summary row."
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
                    "{system_message}\n{evidence_block}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(evidence_block=evidence_block)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        # Tool-less twins of the two chains above: the cap-forced terminal turn
        # runs on these, because a relay that ignores tool_choice="none" can
        # answer the forced turn with another tool call, whose content is empty
        # (measured 2026-09-11 through OpenRouter: finish_reason "tool_calls",
        # 467 output tokens -> the "empty terminal turn" notice was a model
        # still asking for tools, not a token burn).
        plain_chain = None
        try:
            plain_chain = prompt | llm
        except Exception:  # noqa: BLE001 - non-runnable llm: fall back to the bound chain
            plain_chain = None
        backup_plain_chain = None
        if backup_llm is not None and backup_llm is not llm:
            try:
                backup_plain_chain = prompt | backup_llm
            except Exception:  # noqa: BLE001 - degrade to the bound backup chain
                backup_plain_chain = None

        # Backup model (TRADINGAGENTS_BACKUP_LLM): same prompt + tool surface,
        # different model, used for truncation-continuation retries only.
        backup_chain = None
        if backup_llm is not None and backup_llm is not llm:
            try:
                backup_chain = prompt | backup_llm.bind_tools(tools)
            except Exception:  # noqa: BLE001 - degrade to same-model continuation
                backup_chain = None

        # Tool-round cap turn: the router sent us back because the last
        # message still carries tool_calls after MAX_TOOL_ROUNDS. Do not
        # re-invoke the model for more tools - strip the dangling tool_calls
        # and run one terminal prose turn so the report is never empty and
        # the loop always terminates (no pathological self-loop).
        from langchain_core.messages import AIMessage as _CapAIMessage

        from tradingagents.agents.utils.structured import finalize_messages

        _cap_msg = state["messages"][-1]
        if getattr(_cap_msg, "tool_calls", None):
            _report = finalize_messages(chain, state["messages"], _cap_msg, backup_chain=backup_chain, agent_name="News Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)
            return {
                "messages": [_CapAIMessage(content=_report, id="news-cap-report")],
                "news_report": _report,
                "tool_evidence": tool_evidence,
            }

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content
            from tradingagents.agents.utils.structured import (
                retry_chain_if_stub,
                retry_chain_if_truncated,
            )

            report = retry_chain_if_truncated(chain, state["messages"], report, backup_chain=backup_chain)
            # A model can answer a tool loop with a bare status turn instead of
            # the report (no tool_calls -> the router takes it as final). Ask it
            # once to deliver the report from the gathered evidence.
            report = retry_chain_if_stub(chain, state["messages"], report, "News Analyst", backup_chain=backup_chain)
        else:
            # Tool-round cap hit: the router forced this turn; the model must
            # write the final report now (dangling tool_calls stripped, one
            # terminal LLM call) so the report is never left empty.
            from tradingagents.agents.utils.structured import finalize_messages

            report = finalize_messages(chain, state["messages"], result, backup_chain=backup_chain, agent_name="News Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)

        return {
            "messages": [result],
            "news_report": report,
            "tool_evidence": tool_evidence,
        }

    return news_analyst_node
