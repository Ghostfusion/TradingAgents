from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.toolsets import fundamentals_tools
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)

_ETF_SYSTEM_TAIL = (
    " SECURITY-TYPE: ETF/FUND. This is an index or exchange-traded fund "
    "wrapper, NOT an operating company. Company statement tools "
    "(get_balance_sheet / get_cashflow / get_income_statement / get_ratios / "
    "get_dcf_valuation / get_fcf_yield / get_analyst_verdict / "
    "get_earnings_quality / get_value_floors / ...) are EXPECTED to be "
    "unavailable for a fund — do not treat their absence as a 'no valuation' "
    "conclusion. Instead: call get_etf_valuation(ticker) for the weighted "
    "constituent valuation (harmonic P/E, forward P/E, earnings/FCF yield, "
    "valuation percentile vs own history, vs SPY/XLK) and use those numbers "
    "before any 'cheap / expensive / no anchor' claim; get_etf_decline_driver "
    "(classifies the decline cause as MARKET/SECTOR/ETF_SPECIFIC/"
    "CONSTITUENT_DRIVEN instead of the company 'clean' read); "
    "get_etf_relative_strength (both legs shown, fixes the "
    "priceRelativeToS&P500 ambiguity); get_etf_risk (beta/downside-capture/"
    "vol%/ATR%/maxDD); get_etf_mechanics (NAV premium/discount; distributions "
    "are ETF distributions, not corporate dividends). A BUY requires an "
    "ETF-level valuation case — never 'no DCF -> no BUY'. Congressional "
    "trades on a fund are noise (weight ~0)."
)


def create_fundamentals_analyst(llm, backup_llm=None, config=None):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        # ETF routing (docs/design_etf_fundamental_valuation.md): when the
        # engine is enabled and the security is classified as a fund/ETF,
        # swap the company toolset for the ETF one and append the ETF
        # instructions. Default-off; a classification UNKNOWN keeps today's
        # company path.
        security_type = "UNKNOWN"
        if config and config.get("enable_etf_engine"):
            try:
                from tradingagents.agents.utils.agent_utils import resolve_instrument_identity
                from tradingagents.strategies.security_type import classify_security

                cls = classify_security(
                    str(state["company_of_interest"]).upper(),
                    identity=resolve_instrument_identity(str(state["company_of_interest"])),
                )
                security_type = cls.get("security_type") or "UNKNOWN"
            except Exception:  # noqa: BLE001 - degrade to company path
                security_type = "UNKNOWN"
        is_etf = security_type == "ETF"

        tools = fundamentals_tools(is_etf)

        # Forced-tool evidence (map-reduce): when analyst_forced_tools is set,
        # gather the fixed tool set once (skipped on tool-loop re-entries via
        # the state key) and reduce from the rendered block instead of the
        # LLM-selected subset. see docs/design_mapreduce_forced_tool_gathering.md.
        from tradingagents.agents.utils.evidence_gather import gather_for_analyst_node

        evidence_block, tool_evidence = gather_for_analyst_node(
            state, "fundamentals", tools, config
        )

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " FISCAL-PERIOD LABELS: quarter rows come from vendors with"
            " calendar-dated period ends; when a company fiscal year-end"
            " differs (e.g. SNDK/WDC end early July, MU ends May), label the"
            " latest rows by their FISCAL period (FY2026 Q4 ended 2026-07-03,"
            " row dated 2026-06-30) - never invent a calendar ordinal like"
            " Q2 2026 for the latest quarter (SNDK 2026-09-10 fundamentals"
            " mislabeled fiscal Q4 as Q2 2026)."
            "  SERIES COUNT LABEL: an N-quarter trend series must list N"
            "  entries (or N+1 including the base) and say which - a"
            "  four-quarter uptrend with five values is a labeling slip"
            "  (ADBE 2026-09-10 wrote a four-quarter uptrend as 5.873 ->"
            "  5.988 -> 6.194 -> 6.398 -> 6.618 = five quarters)."
            "  DATA AS-OF: the latest fiscal quarter in every financial"
            "  tool is the newest row the vendor has surfaced - state that"
            "  period explicitly in the snapshot (ADBE 2026-09-10: rows"
            "  stopped at 2026-05-31 even though the report date is"
            "  09-10, because Q3 was not yet in the feed). Never present"
            "  the latest-quoted quarter as universally current."
            "  REVENUE ROW: quote the income-statement Total Revenue row"
            "  verbatim for the latest quarter (HPE 2026-09-10 leaf:"
            "  $12,213M; the report wrote $12.45B in the body and $12.30B"
            "  in the table - neither matches the leaf row). One revenue"
            "  per quarter, body = summary = tool."
            "  PRICE-TARGET MEAN: the analyst-consensus mean-PT comes from"
            "  one ratings call - body and summary must quote the same"
            "  mean/high/low (HPE leaf: mean 69.38 high 88 low 54; the"
            "  table wrote 58.38 / 58.97, which match no leaf)."
            "  GAIN/LOSS ROWS: unusual items are SIGNED rows in the feeds"
            "  (cash-flow Gain/Loss from Continuing Ops; IS Total Unusual"
            "  Items) - quote one of them verbatim with its sign; never"
            "  synthesize an unsigned third value (HPE report wrote $344M"
            "  gain on sale of business; the leaves carry -$444M gain/loss"
            "  and +$373M unusual items)."
            " ADR/COMMON-SHARE BASIS: ADR statement EPS comes from the"
            " vendor share count (5.18B for TSM = the ADR float) - quote"
            " per-ADR TWD/USD values AND the local common-share value"
            " when the ratio differs (TSM 5 common:1 ADR; vendor diluted"
            " EPS 136.25 TWD per ADR = NT$27.25 per common share, US$4.31"
            " per ADR). State the basis on every EPS/normalized-eps"
            " figure; a bare TWD EPS with no share convention is a"
            " defect (TSM 2026-09-10 report quoted 136.25 as if common)."
            "  GAAP/NORMALIZED: distinguish GAAP EPS/income from normalized"
            " (non-GAAP, adjusted) values with explicit labels; when a total"
            " unusual-item/gain-on-sale flips quarterly sign, say so - report"
            " both GAAP and normalized, never only one (WDC 2026-09-10"
            " normalized Q4 -3.1B vs reported +3.07B argued the wrong way)."
            "  EARNINGS-SURPRISE BASIS: the vendor surprise % pairs the"
            " reported EPS (often GAAP) with a consensus estimate whose basis"
            " can differ (adjusted) - when the actual EPS is negative, label"
            " the surprise as basis-unreconciled and never extrapolate"
            " consecutive misses into a catalyst/risk signal without"
            " confirming the actual and estimate bases match (IREN 2026-09-10"
            " Q4: act -2.16 GAAP vs est -0.6058; the adjusted read was a beat)."
            "  NON-OPERATING GAIN SUBSTANCE: a vendor row NAME is not evidence"
            " of the transaction. A 'Gain on Sale of Security' row is often an"
            " UNREALIZED mark-to-market on equity stakes, not a completed sale"
            " (GOOG 2026-09-11 Q2: $98.839B vendor row; coverage describes an"
            " unrealized mark-to-market, the report's 'Gain On Sale Of"
            " Security' label implied a cash-realizing sale). State the amount,"
            " that the vendor flags it unusual/non-operating, and whether the"
            " feed establishes realized vs unrealized; when it does not, say"
            " the feed does not - never write 'proceeds'/'sold'/'cashed in'"
            " that no leaf evidences."
            "  NORMALIZED-EPS PROVENANCE: when the feed supplies its own"
            " Normalized Income (unusual items removed, often tax-effected at"
            " the reported effective rate), label that figure as the VENDOR's"
            " normalization and do not present it as the Street's adjusted"
            " basis: the two differ (GOOG 2026-09-11 Q2: vendor-normalized"
            " ~$2.62 vs the reported adjusted print ~$2.85 against a $2.8991"
            " consensus). Give the add-back and implied tax treatment when the"
            " leaves allow it, and mark any vendor-normalized-vs-consensus"
            " comparison as cross-basis."
            "  REFERENCE-PRICE BASIS: state the reference price with its as-of"
            " date and whether it is a settled close or a FORMING intraday bar"
            " on every price-derived line (margin of safety, DCF-vs-market,"
            " PT upside, SMA/EMA distance, value-floor gaps). A ratio computed"
            " on a forming bar is PROVISIONAL - never present it as a settled"
            " valuation gap, and say so when a distance is a fraction of a"
            " percent (it can flip sign at the close: GOOG 2026-09-11 price"
            " +0.4% above the 200-day SMA on the forming bar vs BELOW it on"
            " the prior settled close). When the evidence block carries a"
            " Reference-price line, use it as the basis; when no basis is"
            " stated, say the basis is unavailable rather than assuming a"
            " settled close."
            "  EV/EBIT SIGN SANITY: when operating income is negative the"
            " EV/EBIT (acquirers multiple) MUST be negative; a huge positive"
            " EV/EBIT next to a loss is an artifact (near-zero EBIT slice) -"
            " cite the negative side from get_ratios and flag/omit the absurd"
            " one (IREN 2026-09-10: 270,761 vs -18.29)."
            "  PARENT/SUB-ITEM SUMS: when a quote breaks a parent into"
            " sub-items, verify they sum to the parent; if they do not, quote"
            " both and state the mismatch rather than implying they reconcile"
            " (IREN FY26 special charges -779.76M vs Write Off 638.80 + Other"
            " 111.80 + Restructuring 4.25 - Gain on PPE 24.91 = 729.94 - a"
            " ~49.8M vendor gap)."
            "  EV/NET-DEBT BRIDGE: when quoting EV and net debt, show the"
            " bridge (EV - net debt = equity value) or state the debt/cash"
            " conventions (restricted cash, leases) - an implied EV net-debt"
            " that disagree s with the balance sheet is unexplained (IREN"
            " 2026-09-10: EV implied ~1.94B net debt vs LT debt 7.42B - cash"
            " 5.90B = ~1.52B, or net cash with restricted cash)."
            " CASH-FLOW UNIT DISCIPLINE: free-cash-flow totals share one unit"
            " scale across the report (M vs B slip: WDC 2026-09-10 cited both"
            " $4.1B and $3.10M TTM FCF; the real FY26 is $3.51B)."
            " MARGIN-OF-SAFETY BASIS: when quoting a margin-of-safety /"
            " premium number, state its denominator - (FV-P)/FV vs"
            " (FV-P)/P differ by orders (MSFT 2026-09-10: DCF 113.09 vs"
            " price 490.50 is -333.7% on the FV basis but -76.9% on price;"
            " quote which basis the tool returns and never relabel)."
            "  REPEAT key figures EXACTLY in the summary table - a summary"
            "  row that restates EPS/DCF/CR at a rounded or paired value is a"
            "  defect (MSFT 2026-09-10: body diluted EPS $4.81 from the leaf,"
            "  summary row $4.84 - matches neither basic $4.82 nor diluted)."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_analyst_ratings` to benchmark against the sell-side rating and price-target consensus.Cite them before any company-quality, statement or sell-side-consensus claim. "
            + " You also have quality and smart-money signals: `get_revenue_breakdown(ticker)` for the latest period's segment revenue mix and concentration (a shrinking core segment or heavy single-segment concentration are quality flags); `get_corporate_actions(ticker)` for dividend history and stock splits (consistent dividends signal return discipline); `get_smart_money(ticker)` for ARK fund institutional activity (arbitrary buys/sells); `get_institution_holdings(ticker)` for the institutional share of the float and its period-over-period change (13F-style accumulation/distribution); and `get_earnings_surprise_history(ticker)` for EPS surprise vs estimate per print, the day-of price reaction, and the option-implied move (a succession of beats supports the growth case, negative surprises flag quality risk). Weigh these as supporting signals, not one signal.Cite these before any quality / smart-money / capital-return claim. "
            + " You also have computed-analysis tools - ground your 'quality', 'value', 'accounting risk' and 'beat/miss' claims in them: `get_analyst_verdict(ticker, current_date)` returns the deterministic value screens (EY, EV/EBIT, Piotroski F, Beneish M, Altman Z, Net-Net), the collapsed trap-risk verdict with evidence, ROE and EPS/Revenue YoY - quote these numbers rather than re-deriving them; `get_earnings_surprise(ticker, current_date)` returns the standardized last-reported EPS surprise % and its side (beat/miss). `get_dcf_valuation(ticker, current_date, growth=..., erp=...)` returns a provider-sourced discounted-cash-flow fair value (EV, terminal-value share, WACC) - cite it (or its explicit 'unavailable') before any 'undervalued/overvalued on intrinsics' claim; it complements the multiple-based EY/EV-EBIT screens. `get_earnings_quality(ticker, current_date)` returns the Sloan accruals ratio ((net income - operating cash flow) / total assets) folded into the forensic trap verdict with the accrual as extra evidence - cite it (or its explicit 'unavailable') before any 'strong earnings quality / accrual-driven earnings / manipulation risk' claim. "
            + " For CYCLICAL reporters (memory/NAND/HDD/storage - MU/SNDK/WDC/TSM),"
            " call `get_normalized_cycle_dcf(ticker, current_date, wacc=...)`Cite it before any mid-cycle / normalized-earnings valuation claim. "
            " (median-of-annual-FCF perpetuity, per share) alongside the run-rate"
            " get_dcf_valuation - the run-rate DCF is distorted at a pricing peak"
            " or trough, and the median-of-cycle anchor is independent; cite BOTH"
            " when discussing a cyclical name's intrinsic value (the WDC"
            " review loop asked for a normalized-cycle layer)."
            + " You also have three Finnhub-powered tools (free tier, key-gated): `get_basic_financials(ticker)` returns the metric block (EPS/revenue YoY growth, ROE/ROA, margins, payout, current ratio) - use it before any growth/quality metric claim; `get_insider_activity(ticker)` returns the net 12-month insider change + latest mspr (use before any net insider-buy/sell claim); `get_company_peers(ticker)` returns the comparable peer group for 'cheap vs peers / relative valuation' reasoning. "
            + " For a multi-name value book, `get_portfolio_weights(...)` computes cap-respecting value weights and `get_allocation(scores, sector_map, ...)` returns the final cap-respected allocation block with per-name weights and the min-names check - report the computed weights when proposing an allocation. When the cap must be EXACT with excess redistributed to the uncapped names (index-style constituent capping), use `get_constituent_cap_weights(weights, cap=0.03, ceiling=0.035)` instead - it returns the exact-ceiling capped vector (or flags the degenerate fallback when the ceiling is not enforceable).Cite the computed weights before any multi-name allocation claim. "
            + " For valuation-safety and cross-sectional standing: `get_margin_of_safety(ticker, intrinsic=...)` reports the (intrinsic - price) / intrinsic safety margin you must cite before any 'undervalued/overvalued' claim (pass ``intrinsic`` from get_dcf_valuation / your own fair-value estimate); `get_composite_rank(ticker)` ranks the ticker among its industry peers cross-sectionally by value+momentum factors (composite percentile 0-1) - cite its standing vs peers before any 'cheap relative to peers / leader in the group' claim."
            + " `get_ratios(ticker)` returns the computed valuation/profitability block (EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, Cash ratio, dividend yield, FCF, market cap) derived from this project's own statements - cite these numbers before any 'cheap / richly valued / quality' claim; missing inputs render n/a (never invented)."
            + " You also have value-dip computed tools (the Value Dip + Swing hybrid, `Strategies/Value_Dip_swing.md`): `get_fcf_yield(ticker, current_date)` returns the free cash flow yield (FCF / market cap; >= 6% is the framework's value-floor row) - cite it before any 'strong cash generation supports the value' claim; `get_capex_quality(ticker, current_date)` returns the capital-allocation read (CapEx intensity z, funding cover OCF/CapEx, CapEx-vs-revenue elasticity, incremental-ROIC economic spread vs WACC, 5-regime label, 0-100 score, advisory penalty) - cite it before any 'negative FCF is bad / capex is value-destructive' claim, because a negative FCF can be PRODUCTIVE_INVESTMENT (reinvestment) rather than OVERINVESTMENT / DISTRESS; `get_valuation_z_score(ticker, current_date, multiple=...)` returns the historical valuation Z (current vs its own trailing P/E, EV/EBITDA or P/FCF; Z <= -1.5 = cheap vs history) - cite it before any 'trades below its historical norm' claim; `get_value_dip_setup(ticker, current_date)` returns the hybrid allocation matrix (value floor + technical entry + trade risk + exit target) as one computed candidate verdict - call it before proposing a value-dip (discounted entry with oversold timing) setup."
            + " You also have two Step-1 fundamental-dip gates: `get_balance_sheet_health(ticker, current_date)` returns the balance-sheet health (debt/equity < 1.0 OR current ratio > 1.5) - cite it before any 'low leverage / strong balance sheet' claim; `get_decline_driver_check(ticker, current_date)` returns the negative-force screen (clean / caution / structural) - if it says 'structural', the dip is company-specific (fraud/distress, deeply negative momentum, negative FCF/ROE, severe EPS decline) and the value-dip setup should be rejected, not bought."
            + " You also have a structural-value tool: `get_value_floors(ticker, current_date)` returns the Graham Number, NCAV (net-net) and Earnings Power Value (EPV) floors - cite it (or its explicit 'unavailable') before any 'cheap on assets / below book / earnings-power floor' claim; it is the asset/earnings-backed cheapness floor beyond DCF/MoS/FCF yield."
            + " You also have an ownership tool: `get_ownership_concentration(ticker, current_date)` returns the free-float factor (IWF = float / total shares; < 0.5 = structural passive under-allocation) and, when a per-holder breakdown is available, the Herfindahl-Hirschman index (HHI; > 2500 = highly concentrated governance risk) per Strategies/risk2.md - cite it (or its explicit 'unavailable') before any 'widely held / concentrated ownership / index-eligible' claim."
            + " You also have three free-tier depth tools: `get_financial_history(ticker, years=?)` returns the SEC EDGAR XBRL annual 10-K history (revenue/NI/OCF/capex/assets/liabilities/equity/cash; the only free source beyond ~4-5y; pre-XBRL years render n/a, stated per the report span) - cite it before any long-run trajectory claim; `get_congress_trades(ticker)` returns the House + Senate Stock Watcher open-market trades (net buys/sells + samples; free, keyless) - cite it before any Congress-insider flow claim, a negative net is a (secondary) caution flag, never a gate; `get_earnings_transcript(ticker)` returns the latest earnings-call transcript date/quarter + an excerpt when the FMP free tier serves it (quote only from the returned text; never invent management quotes) - cite it before any \"management said / guided\" claim. You also have industry-depth tools: `get_edgar_fulltext_search(query, forms=?, date_range=?)` searches SEC filing text (e.g. 'major customer' in 10-K) for the customer/supplier-concentration footnote, peer 10-K mentions, and thematic scans - use it before any 'concentrated customer / supplier dependency / moat' claim (verify in the actual filing); `get_patent_activity(ticker)` returns USPTO PatentsView annual granted patents + recent titles (name-based assignee match; free key) as an advisory innovation/moat gauge." + " You also have income/outcome tools: `get_fixed_income_risk(ticker, years=...)` returns the indicated yield and - only when a call/redemption horizon is inferable - YTM, Macaulay/modified duration, DV01 and convexity for bond-like preferreds (a perpetual renders YTM n/a, never a fake yield) - cite it before any 'yield / duration / income risk' claim on a preferred; `get_alpha_scoring(direction, predicted_magnitude, period_days, actual_return, confidence)` scores a past insight's direction + magnitude accuracy ('I said +12%, realized +2%') for the journal/reflection - use it to audit past calls, not to invent a track record."
            + " You also have quant-engine v2 reads (ground your 'quality / value / accounting risk' claims in them; all advisory): `get_dupont_read(net_margin, asset_turnover, equity_multiplier, tax_burden?, interest_burden?)` decomposes ROE into margin/turnover/leverage legs and tells you whether it is margin-led (quality) or leverage-led (lower quality); `get_scenario_dcf(fcf, wacc, shares?, cash?, debt?, g_base?, g_bear?, g_bull?, margin_shock_bear?, margin_shock_bull?, market_price?)` gives the bear/base/bull intrinsic range and, when you pass the market price, the band it sits in (below bear / bear-base / base-bull / above bull) plus the base-case margin of safety - cite it before any 'undervalued/overvalued on intrinsic value' framing; `get_earnings_quality(ticker, current_date)` is the provider-fed earnings-quality read - it fetches the statements itself and returns the consensus concern level (LOW/MEDIUM/HIGH = concern; HIGH means most concern, lowest quality) with the cash-conversion / accrual / FCF evidence plus the forensic Beneish/Altman/F-Score trap - cite it before any 'earnings quality' claim; `get_earnings_quality_verdict(net_income, ocf, total_assets, ...)` is the raw-number variant when you already hold the three figures." + " Regime / sizing context: `get_regime_state(ticker, current_date)` returns the Kalman-filtered trend regime (level/slope + spread) - cite it before any 'trend regime / structural break' claim and pair it with `get_kalman_spread` for the regime-spread read; `get_position_risk_multiplier(ticker, position_pct)` returns the position risk multiplier (size x vol x correlation) - use it before any 'this size is too risky / overweight' claim on a book; `get_allocation_black_litterman(returns, expected_excess_returns, ...)` returns the Black-Litterman posterior weights (the shrink-toward-prior tilt of get_allocation) - offer it as the prior-informed variant when proposing the allocation. Ownership extras: `get_dividends(ticker)` returns the dividend schedule and yield history (consistent payouts reinforce the corporate-actions return-discipline read) - cite it before any 'dividend/yield history' claim; `get_form4_insider(ticker, start_date, end_date)` returns SEC Form 4 open-market net insider $-flow over the window (purchases minus sales, option rows excluded) - cite it (or its explicit 'unavailable') before any 'insider accumulation/selling this window' claim, as the windowed complement to `get_insider_activity`'s 12-month net." + get_language_instruction() + get_output_budget("analyst")
        )

        if is_etf:
            # The multi-line literal builds a 1-tuple (trailing comma); join
            # it to a plain str before appending the ETF tail.
            system_message = ("".join(system_message) if isinstance(system_message, tuple)
                              else system_message) + _ETF_SYSTEM_TAIL

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
            _report = finalize_messages(chain, state["messages"], _cap_msg, backup_chain=backup_chain, agent_name="Fundamentals Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)
            return {
                "messages": [_CapAIMessage(content=_report, id="fundamentals-cap-report")],
                "fundamentals_report": _report,
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
            # the report (no tool_calls -> the router takes it as final,
            # e.g. the 217-byte fundamentals stub on NVDA 2026-09-02). Ask it
            # once to deliver the report from the gathered evidence.
            report = retry_chain_if_stub(chain, state["messages"], report, "Fundamentals Analyst", backup_chain=backup_chain)
        else:
            # Tool-round cap hit: the router forced this turn; the model must
            # write the final report now (dangling tool_calls stripped, one
            # terminal LLM call) so the report is never left empty.
            from tradingagents.agents.utils.structured import finalize_messages

            report = finalize_messages(chain, state["messages"], result, backup_chain=backup_chain, agent_name="Fundamentals Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)

        return {
            "messages": [result],
            "fundamentals_report": report,
            "tool_evidence": tool_evidence,
        }

    return fundamentals_analyst_node
