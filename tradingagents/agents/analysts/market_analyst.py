from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.toolsets import market_tools
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)

# These two live in their own tool modules (not re-exported by agent_utils),
# matching how graph/trading_graph.py imports them for the market ToolNode.


def create_market_analyst(llm, backup_llm=None, config=None):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = market_tools()

        # Forced-tool evidence (map-reduce): gather deterministically once
        # when analyst_forced_tools is set; skipped on tool-loop re-entries.
        from tradingagents.agents.utils.evidence_gather import gather_for_analyst_node

        evidence_block, tool_evidence = gather_for_analyst_node(
            state, "market", tools, config
        )

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
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis. Terminology is strict: RSI >70 = OVERBOUGHT, RSI <30 = OVERSOLD — never write '>70 oversold' or '<30 overbought' (2026-09-09 IGV market.md mixed the two).

Volatility Indicators:
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

Volume-Based Indicators:
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names.

Before writing the final report, call get_verified_market_snapshot for this ticker and the current date, and treat it as the source of truth for any exact OHLCV, price-level, or indicator-value claim. If another tool's output conflicts with the verified snapshot, flag the discrepancy rather than inventing a reconciled number. When you see ANY live/intraday print (Alpaca snapshot, delayed quote, momentum feed) that differs from the verified bar's close by more than ~2% OR falls outside the verified bar's day low/high, you MUST call get_live_price_sanity(live_price, day_low, day_high) and report its verdict verbatim in the note - never reconcile a live print on your own. Do not claim historical validation, support/resistance bounces, or exact percentage moves unless they are directly supported by tool output with concrete dates and prices. Cite it before any exact price-level claim.

You also have Massive.com verification tools (plan-gated): get_market_snapshot(ticker) returns a consolidated latest trade/bar/VWAP/change block you can cross-check against the verified snapshot when available; get_top_movers('gainers'|'losers') lists the day's biggest movers for market-context / relative-breadth framing. If either returns 'unavailable', proceed without it. Cite it before any 'the day's leaders / laggards' claim.

You also have two forward-looking positioning tools: call get_options_chain(ticker, current_date) for implied volatility, open interest, and the put/call ratio (leading positioning/expectation signals), and get_short_interest(ticker) for short % of float, days-to-cover, and ownership split (squeeze and conviction signals). For intraday shorting conviction, call get_short_volume(ticker, start_date, end_date) for the daily short-sale volume ratio (% of total volume sold short) — elevated readings indicate heavy shorting pressure. Weigh these as positioning gauges, not directional price calls. For a keyless official variant and the off-exchange read: get_short_sale_volume(ticker, days?) returns the FINRA Reg SHO daily short-sale volume (% short-sale of volume; FINRA public tier serves historical dates, as-of stated — get_short_volume above stays the current source when the MASSIVE key is set), and get_dark_pool_flow(ticker, weeks?) returns the FINRA ATS weekly off-exchange share/trade/notional flow (public tier historical, as-of stated; a free FINRA API key upgrades to the current window) - cite it before any 'dark-pool / off-exchange flow' claim.
You also have a liquidity tool: call get_liquidity_risk(ticker, current_date) for the computed Amihud ILLIQ (price impact per dollar traded), float turnover (ADV / float), the free-float factor (IWF) and a LIQUID / CAUTION / ILLIQUID verdict (Strategies/risk2.md). Cite it (or its explicit 'unavailable') before any 'liquid enough to trade / thin book / slippage risk / index-eligible' claim. For a name whose quoted spread is unavailable, call get_spread_estimate(ticker, current_date) for the Corwin-Schultz / Abdi-Ranaldo high-low spread FLOOR; cite it before any 'trading cost / round-trip slippage / spread' claim, and say it is a floor, not a quoted spread.

You also have a money-flow tool: call get_capital_flow(ticker) for weekly net capital inflow/outflow split by order size (super/big/mid/small) and the latest session's capital distribution. Sustained large/super-order outflows suggest institutional distribution; sustained inflows suggest accumulation. Weigh this as a positioning gauge alongside the options and short-interest signals.

You also have an event-risk tool: call get_expected_move(ticker, current_date) for the option-market-implied 1-day move at the upcoming earnings print (e.g. ±9%). Weigh a large expected move when sizing volatility and when setting stop distances around the event — a ±10% event requires wider stops or smaller size than ±2%. Cite the implied move before any 'the print is priced in / size for the event' claim.

You also have computed-analysis tools - use these numbers as ground truth, do not re-derive them from raw prices:
- get_swing_set(ticker) - the deterministic multi-week setup: trend stack, RSI band, the 1-ATR structure stop below the swing low, 2R/3R targets, trail and VCP state. Use its stop/target/risk numbers whenever you propose entry, stop or reward:risk. Cite its stop and targets before any entry / stop / reward:risk claim.
- get_swing_exits(ticker) - the chandelier trailing stop (3x ATR below the 22-bar high) + 20-day EMA trail + 2R/3R targets. Use it before any 'trailing stop / exit level / let winners run' claim on a swing position.
- get_dip_technical(ticker) - the value-dip timing read: RSI(14), Bollinger %b, Stochastic %K oversold, Money Flow Index and KST momentum. Use it before any 'oversold / dip timing / mean reversion' claim - it separates a turnable value dip from a falling knife.
- get_mean_reversion_tech(ticker) - the faster/smoother mean-reversion + channel technicals: StochRSI, RSI2, Williams %R, Keltner, Donchian, OBV divergence, Parabolic SAR, Elder thermometer. Use it before any 'oversold / channel support / trailing exit / volume confirmation' claim.
- get_opening_range(ticker) - the opening-range breakout (ORB) read: first-15-min high/low + breakout + 2R stop/target. Use it before any 'opening range / ORB / first-15-min breakout' claim on a swing entry.
- get_gap_type(ticker) - the overnight gap classification (common / breakaway / runaway / exhaustion) + heuristic fill probability and days-to-fill. Use it before any 'gap will fill / breakaway gap / gap risk' claim.
- get_order_imbalance(ticker) - the order-imbalance verdict (buy-heavy / sell-heavy / balanced) from institutional vs retail net flow. Use it before any 'institutions are buying/selling / order imbalance' claim.
- get_premarket_liquidity(ticker) - the pre-market liquidity read (latest volume vs 30d avg; thin-book warning). Use it before any 'liquid enough to trade pre-market / thin book / wide spread' claim.
- get_post_close_confirmation(ticker) - the post-close confirmation (stopped-out / target-hit / holding) vs the prior report's stop/target. Use it before any 'the close confirmed / stopped out' claim on a held position.
- get_relative_strength(ticker) - the stock vs its benchmark (SPY) RS line verdict (leading/uptrend/lagging/diverging/unknown). Use it before any 'outperforming the market' claim.
- get_position_sizing(confidence, stop_dist_pct, ...) - the risk-budget + quarter-Kelly size for a proposed setup (feed it the swing-set stop distance). Report the computed size, not an invented one. Cite the computed size before any 'size this at X%' claim.
- get_risk_gate(size_pct, ...) - the house risk verdict (PASS/WARN/REJECT) for any proposed size. Flag it in your report when a size you considered would REJECT. Cite the verdict before any sizing / risk-budget claim.

You also have three environment-flow tools - ground regime and order-lifecycle claims in them:
- get_regime_read(ticker) - the deterministic regime label (vol percentile + trend), volatility-target position scale, 60d momentum and 52w distance. Use it before any 'the regime is risk-on/off' or 'trade the trend' claim.
- get_skill_read(ma_alignment, trend_score, requested, baseline_score) - the regime-from-opinion skill read (DSA advisory): it derives the regime from YOUR OWN computed technical opinion (bullish & >=70 -> trending_up, bearish & <=30 -> trending_down, 35..65 -> sideways) and selects the matching strategy-skills with their bounded +-20 score adjustments. Use it before any 'which playbook applies' claim or to fold advisory adjustments onto a score; everything is computed, nothing is guessed.
- get_volatility_contraction(ticker) - the VCP base state (15%->8%->3% contraction, volume fade, near-breakout). Use it when assessing whether a tight base precedes a breakout.
- get_orderflow_read(ticker) - the live institutional-vs-retail net, distribution score, divergence and alignment. Use it (instead of raw get_capital_flow) before any 'institutions are accumulating/distributing' claim - it is the computed summary.

You also have decision-grounding tools:
- get_regime_components(ticker) - drill into why the regime label says what it does: vol_pct, trend strength, choppiness, label. Use before any regime claim, alongside get_regime_read.
- get_exit_check(entry, close, atr, ...) - the deterministic stop-to-breakeven, ATR target, and holding action (stop/target/hold) for a held long. Use its numbers, not a guessed stop, when proposing an exit or a stop/target level. Cite it before any stop / target / hold-level claim.
- get_momentum_detail(ticker) - exact momentum microstructure (pillars, rvol, vwap, ema9, first-pullback) for a day-trade pre-filter. Use before any momentum/pullback claim.
- get_sector_rotation_screen(enable_breadth?, top_n?) - the sector rotation SCREEN: regime cap + multi-factor SPDR rank (momentum/RS/trend/risk) + RRG quadrant + pullback-divergence leader flags + dispersion trend, and (with breadth on) constituent breadth / EW-CW leadership / Setup A-B states. Use it before any 'sector is rotating / leadership shifting / early rotation' claim - a sector-first screen, advisory, never a gate.
- get_sector_rank(ticker) - the 11-SPDR sector momentum ranking (1m + 3m) and where this ticker's sector stands (top3/tracking/unknown). Use it before any 'sector is leading / rotating' or 'trade with the sector tailwind' claim.
- get_dupont_read(net_margin, asset_turnover, equity_multiplier, tax_burden?, interest_burden?) - the DuPont ROE decomposition (why ROE is high: margin vs turnover vs leverage; leverage-led is lower quality).
- get_scenario_dcf(fcf, wacc, shares?, cash?, debt?, g_base?, g_bear?, g_bull?) - a bear/base/bull DCF value range; use before any 'intrinsic value is X' claim.
- get_earnings_quality_verdict(net_income, ocf, total_assets, fcf?, capex?, eps_growth?, fcf_growth?) - the earnings-quality verdict (cash conversion, accruals, FCF vs EPS divergence).
- get_hrp_alloc(ticker, returns_by_name) - Hierarchical Risk Parity book weights (robust under noisy covariance, no matrix inversion; more conservative returns). Use before any 'HRP / hierarchical risk / robust book allocation' claim.
- get_momentum_12_1(ticker) - the canonical 12-1 momentum (skips the last month's short-term reversal). Use before any '11-month momentum / 12-1 factor' claim.
- get_taylor_read(current_date) - the Taylor-rule implied policy rate (classic 1993 r* = 2%) and the actual-vs-rule deviation. Use before any 'Fed is tight/loose / policy rate should be X / rate-cut or hike odds' claim; the deviation sign tells whether policy sits restrictively (positive) or accommodatively (negative) vs the rule.
- get_options_iv_read(ticker) - ATM-IV expected move, put:call OI concentration, put-skew and the volatility risk premium from the machine option chain. Use before any 'options price a X% move / puts are rich / vol is cheap' claim; renders n/a without a chain.
- get_factor_profile(ticker) - the computed Alpha158-style 16-factor profile (momentum/reversal/vol/value composite, gated by enable_factor_profile). Use before any 'factor-based edge / quant-factor reading' claim; returns explicit unavailable when the config gate is off.
- get_cycle_tilt(current_date) - the business-cycle phase (early/mid/late/recession) from PMI + yield curve + credit spreads and the advisory sector tilt. Use it before any 'cyclicals should lead / defensives favored / regime rotation' claim.
- get_option_breakeven(long_strike, long_premium, short_strike?, spot?, short_ttm_days?, delta?, days_to_earnings?, days_to_ex_div?) - the option-position breakeven + PMCC discipline read. Use it before any 'breakeven / the sold call sits above cost / option-rent' claim.
- get_gamma_profile(ticker) - the dealer-gamma regime (short = momentum/cascade, long = mean-reversion) + call/put walls from the options chain. Use it before any 'options flow / structural wall / pinning' claim — advisory market-structure context, never a price law.
- get_opex_read(current_date) / get_derivatives_flow(ticker, current_date) - option-expiry calendar context (OPEX week, post-OPEX unwind) and the combined gamma + OPEX + IV read. Use before any 'pinned into expiry / OPEX-driven / expiration-effect' claim.
- get_vol_surface_shape(ticker) - 25-delta risk reversal (skew direction: negative = puts rich), 25-delta butterfly (smile curvature), and term-structure slope (long vs short-dated ATM IV). Use before any 'the vol curve is steep / skew is rich / wings are expensive' claim.
- get_parity_screen(ticker, cost_bps=...) - put-call parity / conversion-reversal only screen across the chain. Use before any 'options are mispriced / an arbitrage exists' claim; a flag is a screen, not a trade. (1m + 3m) and where this ticker's sector stands (top3/tracking/unknown). Use it before any 'sector is leading / rotating' or 'trade with the sector tailwind' claim.
- get_cycle_tilt(current_date) - the business-cycle phase (early/mid/late/recession) from PMI + yield curve + credit spreads and the advisory sector tilt. Use it before any 'cyclicals should lead / defensives favored / regime rotation' claim.
- get_strategy_quality(ticker, returns=...) - net CAGR, annualized vol, Sharpe and max drawdown over the price-derived (or provided) return series. Use before any 'this is a high-quality / risk-adjusted strategy' claim.
- get_signal_quality(signal, forward_returns, quantile=0.8) - the deterministic validation read for any forecast you reuse: Spearman rank IC, ICIR, Qlib long-short precision (top-quantile sign hit rate) and a combinatorial-CPCV path count. Ground any 'this signal/score predicts well' or 'this edge survives out-of-sample' claim in it (or its explicit n/a).
- get_bsm_option_quote(spot, strike, t_years, vol, option_type, r=0.0, q=0.0) - direct Black-Scholes-Merton price + Greeks (incl. charm with the dividend term) for an equity option when the chain does not quote your exact strike/expiry. Advisory model quote, never a market price - label it as such in any answer. Use before any 'the option is cheap / rich' or 'this strike prices in ~X' claim.
- get_risk_overlay(portfolio_value, floor?, expected_vol?, target_vol?, multiplier?) - the CPPI floor-protected risky exposure (m * max(P - floor, 0)) + vol-targeting scale (target/expected, capped 3x) for a book - use before any 'run the book at X% risk / lever the cushion' claim; advisory overlay, risk gates stay authoritative.
- get_execution_schedule(notional, intervals, volatility?, temp_impact?, risk_aversion?, method=...) - the Almgren-Chriss optimal execution trajectory (or TWAP/VWAP/POV benchmarks) for a size: E[IS] + var(IS) + per-interval trades. Use before any 'how do we scale into/out of this' claim - advisory scheduling, never an order.
- get_lottery_factors(ticker) - the lottery-tilt screen (MAX = biggest single-day return in the month; IVOL = idiosyncratic vol). High MAX/IVOL = over-priced right-tail, EXPECTED to underperform (Bali 2011; cross-market confirmed) - use before any 'high-octane / the big up-days justify the risk' claim; a quality penalty, not a momentum endorsement.
- get_tail_risk(ticker, alpha=...) - the historical VaR / CVaR tail-loss budget and a -10% uniform stress loss. Use it before any position-sizing/tail-risk claim in a risk-off regime.
- get_session_discipline(ticker, peak_pnl=..., current_pnl=...) - the deterministic intraday walk-away read: 50% giveback from session peak, max-daily-loss breach, past the 10:00 ET optimal window, and the nearest psych levels around the current price. Use it before any 'sell into strength / take the day off / giveback' claim when trading intraday momentum.
- get_credit_spread_read(current_date) - the FRED ICE BofA HY/CCC/BB option-adjusted spreads and the deterministic credit-cycle band (low/moderate/high/severe) + de-risk scale. Use it before any 'credit stress / risk-off / debt markets / HYG-vs-TLT' claim; the CCC spread is the leading risk-off sentinel (degrades to 'unavailable' when FRED_API_KEY is unset).
- get_technical_factors(ticker) - the extended technicals in one call: ADX (trend strength), classic pivots (P/R1/S1/R2/S2), Aroon (trend age), Fisher Transform (reversal), Chaikin Oscillator (accumulation), Elder-Ray (bull/bear power), Supertrend (ATR trailing direction) and the volume profile (POC + value area). Use it before any 'trend strength / pivot support-resistance / Aroon age / Fisher turn / Chaikin accumulation / Elder-Ray pressure / Supertrend direction / POC-value-area' claim.
- get_extended_indicators(ticker) - the extended trend/momentum/volume group: Ichimoku cloud (trend + support/resistance), CCI (overbought/oversold), ROC, momentum oscillator, TRIX, Force Index, accumulation/distribution (A-D), VPT (volume price trend), Chaikin Money Flow (buying/selling pressure) and anchored VWAP (cost basis). Use it before any 'Ichimoku cloud / CCI / ROC / TRIX / A-D / VPT / CMF / VWAP cost-basis' claim.
- get_candlestick_patterns(ticker) - a scan of the most recent candles for common patterns: doji (indecision), hammer / shooting star (reversal), bullish/bearish engulfing and morning/evening star. Use it before any 'doji / hammer / engulfing / morning star / shooting star' price-structure claim.
- get_book_tail_risk(ticker, weights=...) - the book-level tail: portfolio CVaR from a weighted return mix, the correlated -10% stress loss (a macro event moves every position at once), and the drawdown gate (True = new risk blocked). Use it before any 'book tail / correlated stress / drawdown gate' claim; complements get_tail_risk (single-name).
- get_composed_risk_gate(ticker, size_pct?, capital_at_risk_pct?, risk_cap_pct?, liquidity_verdict?, weights=...) - the ONE-call composed risk verdict that applies the precedence rule PORTFOLIO gate > TRADE gate: it feeds the book's realized drawdown into the risk governor automatically, so a blocked portfolio drawdown gate REJECTs the position even when trade-level risk_ok looks fine. Use it before ANY 'can we open this risk / risk_ok / drawdown_gate vs size' claim - never reconcile drawdown_gate and risk_ok by hand.
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
- get_exit_plan(entry, atr, current, peak=..., stop=..., giveback_pct=...) - the structure/R breakeven trigger + margin-giveback stop in one exit-management read. Use when managing an open position. Cite it before any 'move the stop / take the exit' claim.
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
- get_book_depth_read(bid, ask, bid_size, ask_size) - microprice + order-book imbalance (size-weighted fair value + signed depth asymmetry). Use for any thin-book / quote-depth / short-horizon price-pressure claim. Use before any 'the book is thin / a size this large will move the price' claim.
- get_ts_momentum_weights(closes_by_name) - MOP-style vol-scaled time-series momentum portfolio weights (sign of trailing log return / EWMA vol, target-vol normalized, gross-capped). Use before any 'this asset is trending, size more' claim.
- get_pair_trade_signal(x, y) - pairs-trading spread z-score signal (entry |z|>=2, exit <=0.5, stop >=3) with cointegration + half-life. Use before any 'these two mean-revert, trade the spread' claim.
- get_pair_risk(ticker_x, ticker_y) - Engle-Granger cointegration plus per-lag Granger causality between two names (the tool fetches both close series itself). Use before any 'these two lead/lag each other / the spread is mean-reverting' claim - get_pair_trade_signal gives the trade signal, this gives the lead-lag evidence behind it.
- get_vif_read(ticker, factors=[...]) - variance-inflation across named factors (rsi, mom, bias, zscore, std, vol, range), which the tool builds from the run OHLCV. Use before presenting two like measures (e.g. RSI and StochRSI) as independent evidence: VIF > 5 means they carry the same information and must not be stacked as separate confirmations.

Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + " You also have technical/vol/flow tools you must cite before the matching claim: `get_indicators(ticker)` gives the indicator block (SMA/RSI/MACD/bands) - cite it before any moving-average/oscillator claim; `get_garch_volatility(ticker)` and `get_volatility_estimators(ticker)` give the GARCH conditional-vol and the historical/GARCH/EWMA/range vol estimates - cite before any 'vol is spiking / vol regime' claim; `get_shift_detection(ticker, current_date)` gives the CUSUM/EWMA regime-shift read - cite before any 'regime changed / structural break' claim; `get_mean_reversion_quality(ticker)` gives the mean-reversion quality (variance-ratio test) - cite before any 'mean-reverting / trending' claim; `get_options_surface(ticker)` gives the implied-vol surface shape (25-delta RR/BF) + term-structure slope - cite before any 'options pricing / skew / term-structure' claim; `get_merton_distance(equity, debt, equity_vol, r?, t?)` gives the Merton distance-to-default (equity-value based) - cite before any 'default risk / distress' claim in the technical report; `get_earnings_quality_verdict(net_income, ocf, total_assets, ...)` gives the raw-number earnings-quality verdict - cite it before any 'earnings quality / accounting risk' claim in the technical report; `get_tail_decomposition(returns_by_name, ...)` gives the tail-risk decomposition (modified VaR/CVaR per name) - cite before any 'tail risk concentrated in X' claim; `get_universe_membership(ticker, ...)` reports universe eligibility - cite it when the name's membership drives sizing; `get_regime_state(ticker, current_date)` (Kalman trend regime) and `get_position_risk_multiplier(ticker, position_pct)` (size x vol x corr) - cite before any 'trend regime' or 'this size is risky' claim. `get_return_decomposition(ticker, current_date)` splits the name's return into its overnight and intraday legs - cite it before any 'the dip is being sold intraday / the move is overnight news / gap risk' claim (it says which leg, never why). "
            + " Data-source tools: `get_stock_data(ticker, start_date, end_date)` returns the OHLCV series - cite it as the price basis for any technical computation; `get_crypto_prices(symbols, ...)` returns crypto spot prices - use it before any crypto-relative 'price / momentum' claim; `get_market_snapshot_alpaca(...)` returns the Alpaca market snapshot (when the Alpaca key is set) - use it as a live cross-check on `get_market_snapshot`; `get_cost_models(direction, size_usd, adv_usd, hist_vol, ...)` returns the fill cost/slippage/impact models (square-root + capacity) - cite before any 'how costly is this size to fill' claim; `get_momentum_scan(...)` returns the universe momentum scan - use its leading names before any 'strongest momentum names' claim; and `get_debate_claims_verdict(claims)` adjudicates the debate's factual claims (supported/refuted/uncertain with evidence) - run it on the pricing claims before you finalize. "
            + " HARD CITATION RULE for figures: copy every figure VERBATIM from"
            " the tool output you cite (the §Tool Evidence block above, or a"
            " tool you call: verified snapshot, get_swing_set, get_stock_data,"
            " ...) - exact digits and units, never retyped or reformatted."
            " When you must state a derived percentage or level (e.g. price"
            " vs a moving average), compute it from verbatim-copied inputs,"
            " and never re-derive a value the tools already computed for you."
            " If two tools disagree on the same quantity, quote BOTH with"
            " their tool names and flag the conflict; never splice or silently"
            " reconcile them (a stop level belongs to one tool with its own"
            " ATR basis - do not mix two tools' ATRs in one claim)."
            + " Label breakout/reference levels by their actual quote type:the"
            " verified snapshot's Close and get_market_snapshot's Prev close are"
            " CLOSES - never label a prior-session close as a 'high' (the"
            " 'high' column owns 'high'; a 52-week-high leaf owns that label)."
            " NEVER call a forming/intraday session bar a CLOSE - the verified"
            " snapshot annotates a FORMING bar (in-progress session); then write"
            " intraday levels and avoid closed/EOD/daily-close wording"
            " (MU 2026-09-10 market.md called 982.95 the close at 1:37pm)."
            " ALSO do not call a forming-bar intraday move a CONFIRMED gap-down"
            " / confirmed fill / confirmed close - provisional until the"
            " session closes (SNDK 2026-09-10 called the gap-down into"
            " 1698.41 confirmed on a forming bar)."

            " Write trigger/reference numbers at their REAL scale - a 1,010+"
            " trigger is never a 400-area / 500-area level (MU 2026-09-10"
            " summarized a 1,010 trigger as 400-area confirmation)."
            " Label a trailing stop by its OWN basis; do not reuse another"
            "indicator's name: a 20-day-true-range trail is not a 20-EMA;"
            " quote each exit value under the tool that produced it (SNDK"
            " 2026-09-10 market.md renamed its 20-day-true trail 1586.04"
            " as 20-EMA 1586.04 in the summary table)."
            "  PRICE/TIMESTAMP GATE: when a quoted price differs >1% from the"
            "  verified snapshot or prior close, flag DATA-INTEGRITY and never"
            "  finalize a SELL/exit-stopped call on the unverified figure; state"
            "  which timestamp every price carries (WDC 2026-09-10: 462.03 forming"
            "  bar vs 09-09 close 482.28 was a 4.2% difference flagged only in notes)."
            "  SELL vs REDUCE: exits / trailing stops triggered is a REDUCE for"
            "  existing longs; an unconditional SELL needs an explicit short thesis"
            "  - keep the two distinct (WDC 2026-09-10 reported SELL while evidence"
            "  said REDUCE-existing / NO-new-long)."
            "  MACD is one canonical record: quote ONE value triple per timestamp"
            "  everywhere - body and summary table must match (WDC 2026-09-10 body"
            "  -9.32/+8.37 vs summary -0.32/+0.25 contradicted)."
            "  BOLLINGER: one canonical band set per report - quote the"
            "  middle/lower/upper + %b from ONE indicator print; a second"
            "  band pair (different upper/lower) needs an explicit source"
            "  label, and %b must be computed from the quoted bands only"
            "  (TSM 2026-09-10: body 438.16/405.14 vs table wide 438.59/404.71"
            "  with %b 0.7394 that matches only the body pair)."
            "  GAP VS SESSION: a gap is prior-close to open; the session"
            "  change is close to prior close - never call a session"
            "  decline a gap and vice versa (HPE 2026-09-10: open gap"
            "  -1.9% (57.80/58.90) and close -5.8% (55.46/58.90) were"
            "  both labeled -5.4% gap/red day). State both numbers"
            "  separately with their own labels."
            "  RATIO CONVENTIONS: when quoting a call/put or put/call"
            "  ratio together with an activity multiplier, state the"
            "  convention and source for each (HPE 2026-09-10 wrote"
            "  Call/Put vol = 2.41 then call activity 4.2x put - two"
            "  different ratio universes unlabeled). Both must invert"
            "  consistently or be labeled separately."
            "  CALL WALL: quote one call-wall level per report and"
            "  reconcile with the gamma section (HPE 2026-09-10:"
            "  gamma section said call wall 53.0, the table wrote"
            "  walls 58/53 - pick one or label the expiry)."
            "  ATR UNITS: ATR is a magnitude - never write a signed"
            "  percentage like (-5.8% of price); use (5.8% of price)"
            "  (HPE 2026-09-10 ATR(14) 3.24 (-5.8% of price) slip)."
            "  INTRADAY CLAIMS vs OHLC: a claim that price printed"
            "  back under a level intraday must be consistent with the"
            "  day low/high vs that level (HPE 2026-09-10 said price"
            "  printed back under the 10-EMA 54.66 intraday, but the"
            "  day low 55.21 never crossed it - restate or check the"
            "  level)."
            "  CANONICAL LEVELS: one value per labeled level (200-DMA"
            "  distance, GARCH cond, chandelier stop) - body and summary"
            "  table must agree; a second value needs an explicit"
            "  methodology label (HPE 2026-09-10: 200-SMA +64.7% vs"
            "  +184.7% in the table, GARCH cond 58.90/65.90, chandelier"
            "  54.11 vs 58.2/58.11)."
            "  STOP BASIS: the structure/chandelier stop is computed from"
            "  that tool's ATR snapshot - it may differ from the headline"
            "  ATR(14) indicator. When quoting both, label which ATR each"
            "  stop uses (IREN 2026-09-10: structure stop 31.6567 is 1x"
            "  ATR 3.1533 below swing low 34.81, while the headline ATR"
            "  reads 3.38 - 31.43 would be 1x3.38; the two ATRs differ)."
            "  CHANDELIER BASIS: chandelier = highest-high over the lookback"
            "  - multiplier x ATR, never (price - multiplier x ATR) - state"
            "  the anchor high when the number is non-obvious (IREN: 39.83"
            "  is 3xATR below a ~49.97 bar high, not 3xATR below close"
            "  43.64 = 33.50)."
            "  EXPECTED-MOVE EVENT REFERENCE: the expected 1-sigma"
            "  earnings move describes the NEXT unprinted earnings date"
            "  from the calendar - if the last quarter already printed,"
            "  say so and never call the move pending (HPE 2026-09-10:"
            "  Q3 earnings already reported 09-02; +/-10.9% is the"
            "  option-implied move sized for the next print, not a"
            "  pending near-term event)."
            "  sector tool exactly once - body and summary table must"
            "  agree (TSM 2026-09-10: body XLK rank #4 vs table rank5;"
            "  both tools said 4)."
            "  EXPECTED-MOVE BAND: quote the vendor dollar band when the"
            "  expected-move % is stated; if no band exists, write dollar"
            "  band unavailable - NEVER write +/-$0.00 (impossible for a"
            "  positive move at a nonzero price; MSFT 2026-09-10 wrote 6.6%"
            "  as +/-$0.00 while the leaf gave [458, 523])."
            " DELL 2026-09-10 market.md mislabeled the 09-09 close 535.25"
            " as '09-09 high' while the snapshot's Prev close is the close."
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
        # different model. Used for the truncation-continuation retry so a
        # model that keeps cutting at the output cap is not re-paid for the
        # repair. None-safe: no backup configured -> the retry stays on the
        # same chain (legacy behavior).
        backup_chain = None
        if backup_llm is not None and backup_llm is not llm:
            try:
                backup_chain = prompt | backup_llm.bind_tools(tools)
            except Exception:  # noqa: BLE001 - degrade to same-model continuation
                backup_chain = None

        # Tool-round cap turn: the router sent us back because the
        # message still carries tool_calls after MAX_TOOL_ROUNDS. Do not
        # re-invoke the model for more tools - strip the dangling tool_calls
        # and run one terminal prose turn so the report is never empty and
        # the loop always terminates (no pathological self-loop).
        from langchain_core.messages import AIMessage as _CapAIMessage

        from tradingagents.agents.utils.structured import finalize_messages

        _cap_msg = state["messages"][-1]
        if getattr(_cap_msg, "tool_calls", None):
            _report = finalize_messages(chain, state["messages"], _cap_msg, backup_chain=backup_chain, agent_name="Market Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)
            return {
                "messages": [_CapAIMessage(content=_report, id="market-cap-report")],
                "market_report": _report,
                "tool_evidence": tool_evidence,
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

            report = retry_chain_if_truncated(chain, state["messages"], report, backup_chain=backup_chain)
            # A model can answer a tool loop with a bare status turn instead of
            # the report (no tool_calls -> the router takes it as final). Ask it
            # once to deliver the report from the gathered evidence.
            report = retry_chain_if_stub(chain, state["messages"], report, "Market Analyst", backup_chain=backup_chain)
        else:
            # Tool-round cap hit: the router forced this turn; the model must
            # write the final report now (dangling tool_calls stripped, one
            # terminal LLM call) so the report is never left empty.
            from tradingagents.agents.utils.structured import finalize_messages

            report = finalize_messages(chain, state["messages"], result, backup_chain=backup_chain, agent_name="Market Analyst",
                          plain_chain=plain_chain, backup_plain_chain=backup_plain_chain)

        return {
            "messages": [result],
            "market_report": report,
            "tool_evidence": tool_evidence,
        }

    return market_analyst_node
