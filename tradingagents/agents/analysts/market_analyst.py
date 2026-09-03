from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_bollinger_pct_b,
    get_book_correlation,
    get_book_depth_read,
    get_book_tail_risk,
    get_candlestick_patterns,
    get_capital_flow,
    get_capm_risk,
    get_clenow_momentum,
    get_cost_models,
    get_credit_spread_read,
    get_crypto_prices,
    get_debate_claims_verdict,
    get_dip_technical,
    get_downside_read,
    get_event_pnl_response,
    get_exit_check,
    get_exit_plan,
    get_expected_move,
    get_extended_indicators,
    get_gap_type,
    get_garch_volatility,
    get_horizon_var,
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_liquidation_days,
    get_liquidity_risk,
    get_live_price_sanity,
    get_macd_divergence,
    get_market_movers,
    get_market_snapshot,
    get_mean_reversion_quality,
    get_mean_reversion_tech,
    get_merton_distance,
    get_momentum_detail,
    get_news_sentiment_series,
    get_normality,
    get_opening_range,
    get_options_chain,
    get_options_surface,
    get_order_imbalance,
    get_orderflow_read,
    get_output_budget,
    get_pair_trade_signal,
    get_payoff_asymmetry,
    get_position_sizing,
    get_post_close_confirmation,
    get_premarket_liquidity,
    get_premarket_review,
    get_regime_components,
    get_regime_read,
    get_relative_rotation,
    get_relative_strength,
    get_risk_gate,
    get_risk_parity_alloc,
    get_scaleout_plan,
    get_sector_rank,
    get_sentiment_computed,
    get_sentiment_lead_lag,
    get_session_discipline,
    get_short_interest,
    get_short_volume,
    get_skill_read,
    get_sofr_curve,
    get_stock_data,
    get_strategy_quality,
    get_support_structure,
    get_swing_exits,
    get_swing_set,
    get_tail_decomposition,
    get_tail_risk,
    get_technical_factors,
    get_top_movers,
    get_trade_expectancy,
    get_trailing_exit,
    get_tranche_plan,
    get_treasury_curve,
    get_ts_momentum_weights,
    get_unit_root,
    get_universe_membership,
    get_variance_premium,
    get_vdu_entry_setup,
    get_verified_market_snapshot,
    get_volatility_contraction,
    get_volatility_estimators,
)

# These two live in their own tool modules (not re-exported by agent_utils),
# matching how graph/trading_graph.py imports them for the market ToolNode.
from tradingagents.agents.utils.alpaca_tools import get_market_snapshot_alpaca
from tradingagents.agents.utils.momentum_tools import get_momentum_scan


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
            get_live_price_sanity,
            get_market_snapshot,
            get_crypto_prices,
            get_top_movers,
            get_options_chain,
            get_short_interest,
            get_short_volume,
            get_liquidity_risk,
            get_cost_models,
            get_debate_claims_verdict,
            get_universe_membership,
            get_capital_flow,
            get_swing_set,
            get_skill_read,
            get_swing_exits,
            get_dip_technical,
            get_mean_reversion_tech,
            get_opening_range,
            get_gap_type,
            get_order_imbalance,
            get_premarket_liquidity,
            get_post_close_confirmation,
            get_relative_strength,
            get_position_sizing,
            get_risk_gate,
            get_regime_read,
            get_regime_components,
            get_exit_check,
            get_momentum_detail,
            get_volatility_contraction,
            get_orderflow_read,
            get_sector_rank,
            get_session_discipline,
            get_news_sentiment_series,
            get_sentiment_lead_lag,
            get_strategy_quality,
            get_tail_risk,
            get_credit_spread_read,
            get_bollinger_pct_b,
            get_tranche_plan,
            get_trade_expectancy,
            get_macd_divergence,
            get_vdu_entry_setup,
            get_support_structure,
            get_technical_factors,
            get_extended_indicators,
            get_candlestick_patterns,
            get_volatility_estimators,
            get_garch_volatility,
            get_tail_decomposition,
            get_mean_reversion_quality,
            get_book_tail_risk,
            get_liquidation_days,
            get_premarket_review,
            get_expected_move,
            get_momentum_scan,
            get_market_snapshot_alpaca,
            get_book_correlation,
            get_capm_risk,
            get_clenow_momentum,
            get_downside_read,
            get_exit_plan,
            get_horizon_var,
            get_market_movers,
            get_normality,
            get_options_surface,
            get_payoff_asymmetry,
            get_relative_rotation,
            get_risk_parity_alloc,
            get_scaleout_plan,
            get_sentiment_computed,
            get_sofr_curve,
            get_trailing_exit,
            get_treasury_curve,
            get_unit_root,
            get_variance_premium,
            get_event_pnl_response,
            get_book_depth_read,
            get_ts_momentum_weights,
            get_pair_trade_signal,
            get_merton_distance,
        ]

        system_message = (
            """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

Moving Averages:
- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

MACD Related:
- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

Momentum Indicators:
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

Volatility Indicators:
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

Volume-Based Indicators:
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names.

Before writing the final report, call get_verified_market_snapshot for this ticker and the current date, and treat it as the source of truth for any exact OHLCV, price-level, or indicator-value claim. If another tool's output conflicts with the verified snapshot, flag the discrepancy rather than inventing a reconciled number. Do not claim historical validation, support/resistance bounces, or exact percentage moves unless they are directly supported by tool output with concrete dates and prices.

You also have Massive.com verification tools (plan-gated): get_market_snapshot(ticker) returns a consolidated latest trade/bar/VWAP/change block you can cross-check against the verified snapshot when available; get_top_movers('gainers'|'losers') lists the day's biggest movers for market-context / relative-breadth framing. If either returns 'unavailable', proceed without it.

You also have two forward-looking positioning tools: call get_options_chain(ticker, current_date) for implied volatility, open interest, and the put/call ratio (leading positioning/expectation signals), and get_short_interest(ticker) for short % of float, days-to-cover, and ownership split (squeeze and conviction signals). For intraday shorting conviction, call get_short_volume(ticker, start_date, end_date) for the daily short-sale volume ratio (% of total volume sold short) — elevated readings indicate heavy shorting pressure. Weigh these as positioning gauges, not directional price calls.
You also have a liquidity tool: call get_liquidity_risk(ticker, current_date) for the computed Amihud ILLIQ (price impact per dollar traded), float turnover (ADV / float), the free-float factor (IWF) and a LIQUID / CAUTION / ILLIQUID verdict (Strategies/risk2.md). Cite it (or its explicit 'unavailable') before any 'liquid enough to trade / thin book / slippage risk / index-eligible' claim.

You also have a money-flow tool: call get_capital_flow(ticker) for weekly net capital inflow/outflow split by order size (super/big/mid/small) and the latest session's capital distribution. Sustained large/super-order outflows suggest institutional distribution; sustained inflows suggest accumulation. Weigh this as a positioning gauge alongside the options and short-interest signals.

You also have an event-risk tool: call get_expected_move(ticker, current_date) for the option-market-implied 1-day move at the upcoming earnings print (e.g. ±9%). Weigh a large expected move when sizing volatility and when setting stop distances around the event — a ±10% event requires wider stops or smaller size than ±2%.

You also have computed-analysis tools - use these numbers as ground truth, do not re-derive them from raw prices:
- get_swing_set(ticker) - the deterministic multi-week setup: trend stack, RSI band, the 1-ATR structure stop below the swing low, 2R/3R targets, trail and VCP state. Use its stop/target/risk numbers whenever you propose entry, stop or reward:risk.
- get_swing_exits(ticker) - the chandelier trailing stop (3x ATR below the 22-bar high) + 20-day EMA trail + 2R/3R targets. Use it before any 'trailing stop / exit level / let winners run' claim on a swing position.
- get_dip_technical(ticker) - the value-dip timing read: RSI(14), Bollinger %b, Stochastic %K oversold, Money Flow Index and KST momentum. Use it before any 'oversold / dip timing / mean reversion' claim - it separates a turnable value dip from a falling knife.
- get_mean_reversion_tech(ticker) - the faster/smoother mean-reversion + channel technicals: StochRSI, RSI2, Williams %R, Keltner, Donchian, OBV divergence, Parabolic SAR, Elder thermometer. Use it before any 'oversold / channel support / trailing exit / volume confirmation' claim.
- get_opening_range(ticker) - the opening-range breakout (ORB) read: first-15-min high/low + breakout + 2R stop/target. Use it before any 'opening range / ORB / first-15-min breakout' claim on a swing entry.
- get_gap_type(ticker) - the overnight gap classification (common / breakaway / runaway / exhaustion) + heuristic fill probability and days-to-fill. Use it before any 'gap will fill / breakaway gap / gap risk' claim.
- get_order_imbalance(ticker) - the order-imbalance verdict (buy-heavy / sell-heavy / balanced) from institutional vs retail net flow. Use it before any 'institutions are buying/selling / order imbalance' claim.
- get_premarket_liquidity(ticker) - the pre-market liquidity read (latest volume vs 30d avg; thin-book warning). Use it before any 'liquid enough to trade pre-market / thin book / wide spread' claim.
- get_post_close_confirmation(ticker) - the post-close confirmation (stopped-out / target-hit / holding) vs the prior report's stop/target. Use it before any 'the close confirmed / stopped out' claim on a held position.
- get_relative_strength(ticker) - the stock vs its benchmark (SPY) RS line verdict (leading/uptrend/lagging/diverging/unknown). Use it before any 'outperforming the market' claim.
- get_position_sizing(confidence, stop_dist_pct, ...) - the risk-budget + quarter-Kelly size for a proposed setup (feed it the swing-set stop distance). Report the computed size, not an invented one.
- get_risk_gate(size_pct, ...) - the house risk verdict (PASS/WARN/REJECT) for any proposed size. Flag it in your report when a size you considered would REJECT.

You also have three environment-flow tools - ground regime and order-lifecycle claims in them:
- get_regime_read(ticker) - the deterministic regime label (vol percentile + trend), volatility-target position scale, 60d momentum and 52w distance. Use it before any 'the regime is risk-on/off' or 'trade the trend' claim.
- get_skill_read(ma_alignment, trend_score, requested, baseline_score) - the regime-from-opinion skill read (DSA advisory): it derives the regime from YOUR OWN computed technical opinion (bullish & >=70 -> trending_up, bearish & <=30 -> trending_down, 35..65 -> sideways) and selects the matching strategy-skills with their bounded +-20 score adjustments. Use it before any 'which playbook applies' claim or to fold advisory adjustments onto a score; everything is computed, nothing is guessed.
- get_volatility_contraction(ticker) - the VCP base state (15%->8%->3% contraction, volume fade, near-breakout). Use it when assessing whether a tight base precedes a breakout.
- get_orderflow_read(ticker) - the live institutional-vs-retail net, distribution score, divergence and alignment. Use it (instead of raw get_capital_flow) before any 'institutions are accumulating/distributing' claim - it is the computed summary.

You also have decision-grounding tools:
- get_regime_components(ticker) - drill into why the regime label says what it does: vol_pct, trend strength, choppiness, label. Use before any regime claim, alongside get_regime_read.
- get_exit_check(entry, close, atr, ...) - the deterministic stop-to-breakeven, ATR target, and holding action (stop/target/hold) for a held long. Use its numbers, not a guessed stop, when proposing an exit or a stop/target level.
- get_momentum_detail(ticker) - exact momentum microstructure (pillars, rvol, vwap, ema9, first-pullback) for a day-trade pre-filter. Use before any momentum/pullback claim.
- get_sector_rank(ticker) - the 11-SPDR sector momentum ranking (1m + 3m) and where this ticker's sector stands (top3/tracking/unknown). Use it before any 'sector is leading / rotating' or 'trade with the sector tailwind' claim.
- get_strategy_quality(ticker, returns=...) - net CAGR, annualized vol, Sharpe and max drawdown over the price-derived (or provided) return series. Use before any 'this is a high-quality / risk-adjusted strategy' claim.
- get_tail_risk(ticker, alpha=...) - the historical VaR / CVaR tail-loss budget and a -10% uniform stress loss. Use it before any position-sizing/tail-risk claim in a risk-off regime.
- get_session_discipline(ticker, peak_pnl=..., current_pnl=...) - the deterministic intraday walk-away read: 50% giveback from session peak, max-daily-loss breach, past the 10:00 ET optimal window, and the nearest psych levels around the current price. Use it before any 'sell into strength / take the day off / giveback' claim when trading intraday momentum.
- get_credit_spread_read(current_date) - the FRED ICE BofA HY/CCC/BB option-adjusted spreads and the deterministic credit-cycle band (low/moderate/high/severe) + de-risk scale. Use it before any 'credit stress / risk-off / debt markets / HYG-vs-TLT' claim; the CCC spread is the leading risk-off sentinel (degrades to 'unavailable' when FRED_API_KEY is unset).
- get_technical_factors(ticker) - the extended technicals in one call: ADX (trend strength), classic pivots (P/R1/S1/R2/S2), Aroon (trend age), Fisher Transform (reversal), Chaikin Oscillator (accumulation), Elder-Ray (bull/bear power), Supertrend (ATR trailing direction) and the volume profile (POC + value area). Use it before any 'trend strength / pivot support-resistance / Aroon age / Fisher turn / Chaikin accumulation / Elder-Ray pressure / Supertrend direction / POC-value-area' claim.
- get_extended_indicators(ticker) - the extended trend/momentum/volume group: Ichimoku cloud (trend + support/resistance), CCI (overbought/oversold), ROC, momentum oscillator, TRIX, Force Index, accumulation/distribution (A-D), VPT (volume price trend), Chaikin Money Flow (buying/selling pressure) and anchored VWAP (cost basis). Use it before any 'Ichimoku cloud / CCI / ROC / TRIX / A-D / VPT / CMF / VWAP cost-basis' claim.
- get_candlestick_patterns(ticker) - a scan of the most recent candles for common patterns: doji (indecision), hammer / shooting star (reversal), bullish/bearish engulfing and morning/evening star. Use it before any 'doji / hammer / engulfing / morning star / shooting star' price-structure claim.
- get_book_tail_risk(ticker, weights=...) - the book-level tail: portfolio CVaR from a weighted return mix, the correlated -10% stress loss (a macro event moves every position at once), and the drawdown gate (True = new risk blocked). Use it before any 'book tail / correlated stress / drawdown gate' claim; complements get_tail_risk (single-name).
- get_liquidation_days(ticker, shares_to_liquidate=...) - days for the market to absorb a block at a 15% participation cap. Use it before any 'can the market absorb this block / unwind risk / days to liquidate' claim.
|- get_premarket_review(ticker, prior_close=..., open_price=..., prior_stop=..., entry_price=...) - the deterministic pre-market CONFIRM / REVISE / REJECT arbiter from measured deltas (gap vs ATR, catalyst window, re-anchored tranche caps). Use it before any 'gap risk / re-anchor / pre-market review' claim on a held plan.
|
|You also have news-sentiment computed tools:
|- get_news_sentiment_series(ticker) - the daily news-sentiment series (score -1..1, 7d SMA, latest innovation, article count) from the EODHD / Alpha-Vantage / GDELT chain. Use its 7d SMA / latest innovation before any 'news sentiment is shifting / at extremes' claim.
|- get_sentiment_lead_lag(ticker, max_lags, innovations) - the cross-correlation of daily news sentiment vs forward returns (Pearson/Spearman, positive lag = sentiment leads price). Use the strongest-corr lag before any 'sentiment leads/lags this move' claim.

You also have value-dip computed tools (the Value Dip + Swing hybrid):
- get_bollinger_pct_b(ticker) - the deterministic Bollinger %b: price position inside the 20-day 2-sigma band. %b <= 0 = at/piercing the lower band; <= 0.10 is the mean-reversion entry zone. Use it before any 'oversold / at the lower Bollinger / mean-reversion entry' claim.
- get_tranche_plan(ticker, weights=..., risk_pct=..., account=...) - the 3-tranche scale-in plan (P1/P2/P3 at 1.0/2.0 ATR, weighted avg entry, composite stop P3-1.5ATR, capital-at-risk check, 1.8R/3.0R targets + blended R:R and breakeven win rate). Use its computed levels whenever you propose a scale-in entry for a value dip.
- get_trade_expectancy(p_win, avg_win, avg_loss, rr=...) - the per-trade expectancy E = p*W - (1-p)*L and breakeven win rate 1/(1+R:R). Use it before any 'this setup has positive expectancy / the win rate needed to break even' claim.
- get_macd_divergence(ticker) - the Daily RSI(14) / MACD-histogram momentum divergence read (bullish-divergence / higher-low / lower-low-confirmation). Use it before any 'bullish divergence / momentum turning / reversal support' claim.
- get_vdu_entry_setup(ticker) - the Step-2 entry ladder: volume dry-up near support -> divergence/higher-low -> trigger candle (close above prior high, RVOL >= 1.3x). Use its candidate before proposing an active swing entry out of an oversold dip.
- get_support_structure(ticker) - the major-support read (multi-month base low, 200-day SMA proximity, holding above base). Use it before any 'at major support / near the 200-day / multi-month base' claim.


You also have quant-risk / distribution / book tools - use these numbers as ground truth, do not re-derive them:
- get_horizon_var(ticker, horizon_days, alpha) - multi-day VaR/CVaR (sqrt-T scaling, gated on autocorrelation). Use before any 'over the next N days the risk is...' claim.
- get_downside_read(ticker, target=...) - semi-deviation / downside deviation / shortfall probability / avg shortfall vs a target. Use before any 'downside risk' claim.
- get_trailing_exit(ticker, entry, peak, current, trail_pct) - peak-trailing / give-back exit arithm (Lean L4). Use before any 'trail the stop / give back gains' claim.
- get_exit_plan(entry, atr, current, peak=..., stop=..., giveback_pct=...) - the structure/R breakeven trigger + margin-giveback stop in one exit-management read. Use when managing an open position.
- get_scaleout_plan(entry, stop, t1_fraction) - tiered partial-profit plan (sell T1 -> break-even -> trail). Use when proposing profit-taking.
- get_risk_parity_alloc(ticker, returns_by_name) - risk-parity / min-variance weights + per-name risk contributions over a book. Use before any 'risk-parity / risk-budget allocation' claim.
- get_payoff_asymmetry(ticker, returns=...) - the Omega ratio (gains/losses payoff asymmetry about a threshold).
- get_book_correlation(returns_by_name, method=...) - full pairwise correlation matrix over a book (avg + max pair). Use before any 'diversification / correlation' claim.
- get_capm_risk(ticker, benchmark=...) - CAPM decomposition: beta, systematic (R2) and idiosyncratic risk. Use before any 'beta / market risk / idiosyncratic' claim.
- get_normality(ticker) - Jarque-Bera / Shapiro-Wilk / KS normality tests on returns. Use before any 'fat tails / normal regime' claim.
- get_unit_root(ticker) - ADF/KPSS stationarity tests on the close series. Use before any 'mean-reverting vs trending price process' claim.
- get_relative_rotation(ticker, benchmark=...) - RRG quadrant (leading/weakening/lagging/improving) vs a benchmark. Use before any 'rotation / sector leadership' claim.
- get_clenow_momentum(ticker) - Clenow trend-quality momentum (log-slope x R2, penalizes noise). Use before any 'trend persistence' claim.
- get_sentiment_computed(ticker) - the computed StockTwits score + surprise velocity (z vs baseline). Use it (not raw counts) before any 'social sentiment is shifting' claim.
- get_sofr_curve(current_date) / get_treasury_curve(current_date) - risk-free term structures for any discounting / rate claim; DISABLED until the config flag is on.
- get_market_movers(kind) - the day's gainers/losers/active list for breadth framing.
- get_variance_premium(ticker) - the fair variance-swap strike vs current IV (the event-vol premium). Use before any 'vol is expensive/cheap into the event' claim.
- get_event_pnl_response(spot, delta, gamma, vega, theta, dS_pct, dSigma) - the delta-gamma-vega-theta P&L a catalyst move implies per option unit (cookbook recipe 5). Use with the surface greeks + expected move before claiming 'the move would be worth X'.
- get_book_depth_read(bid, ask, bid_size, ask_size) - microprice + order-book imbalance (size-weighted fair value + signed depth asymmetry). Use for any thin-book / quote-depth / short-horizon price-pressure claim.
- get_ts_momentum_weights(closes_by_name) - MOP-style vol-scaled time-series momentum portfolio weights (sign of trailing log return / EWMA vol, target-vol normalized, gross-capped). Use before any 'this asset is trending, size more' claim.
- get_pair_trade_signal(x, y) - pairs-trading spread z-score signal (entry |z|>=2, exit <=0.5, stop >=3) with cointegration + half-life. Use before any 'these two mean-revert, trade the spread' claim.

Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
            + get_output_budget("analyst")
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
                "messages": [_CapAIMessage(content=_report, id="market-cap-report")],
                "market_report": _report,
            }

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content
            # Enforce completeness: if the final content was cut at the output
            # cap, re-invoke the chain with a continuation so the report is not
            # truncated mid-sentence.
            from tradingagents.agents.utils.structured import (
                retry_chain_if_stub,
                retry_chain_if_truncated,
            )

            report = retry_chain_if_truncated(chain, state["messages"], report)
            # A model can answer a tool loop with a bare status turn instead of
            # the report (no tool_calls -> the router takes it as final). Ask it
            # once to deliver the report from the gathered evidence.
            report = retry_chain_if_stub(chain, state["messages"], report, "Market Analyst")
        else:
            # Tool-round cap hit: the router forced this turn; the model must
            # write the final report now (dangling tool_calls stripped, one
            # terminal LLM call) so the report is never left empty.
            from tradingagents.agents.utils.structured import finalize_messages

            report = finalize_messages(chain, state["messages"], result)

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
