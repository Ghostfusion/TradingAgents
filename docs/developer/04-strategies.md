# 4. Strategies — the deterministic calculators

`tradingagents/strategies/*.py` are **pure, offline, deterministic functions**
that back the analyst tool loops and the post-graph overlays. No LLM is
involved. This is the "compute, don't narrate" core.

> **Plan specs** live in [`Strategies/`](../../Strategies/) — see
> [`Strategies/index.md`](../../Strategies/index.md) to map each plan doc to
> its implementation modules, config flags, and consumers.

## 4.1 Value & screening calculators

- `swing.py` — `swing_report`, `vcp_setup`: trend stack, RSI band, 1-ATR stop,
  2R/3R targets, volatility contraction.
- `relative_strength.py` — `relative_strength_report`: leading/uptrend/lagging
  vs SPY.
- `momentum.py` — pillars, first-pullback, RVOL, session flags (intraday).
- `regime.py` — regime gate (vol percentile / trend label).
- `sector_rank.py` — `--sector-rank` logic (SPDR top-3 by momentum).
- `size.py` — Kelly / vol-target / position sizing (position_sizing).
- `portfolio.py` — `value_ratio_weights`, cap adjustments (watchlist alloc).
- `portfolio_strategy.py` — Qlib Topk-Drop (`topk_drop_weights`) + convex
  enhanced-index (`enhanced_index_weights`: long-only, Σw=1, turnover cap,
  benchmark/factor-deviation, masks, two-stage fallback; scipy SLSQP +
  pure-python fallback, cvxpy optional) - pure, advisory.
- `factor_expressions.py` — Alpha158-style operator set (`ref/delta/mean/std/
  zscore/rsi/bias/mom/corr/avg_vol/high_low_range`), cross-sectional rank,
  learn/infer fit-apply split (train-only moments), expression-string cache.
- `signal_analysis.py` — rank IC/ICIR, quantile long-short, IC-decay
  half-life, prediction autocorrelation, with/without-cost report table.
- `prediction_ledger.py` — decision prediction rows + outcome scoring (MAE/MFE, hit, level breaches); `llm_cost.py` — provider-rate cost estimates.
- `report_disclosure.py` — attribution/consensus/watch/invalidation/disclosure footers (DSA research §3.7).
- `skills.py` — declarative YAML strategy-skill overlays (bounded advisory adjustments), regime-from-opinion, router.
- `news_relevance.py` — news relevance scoring + official-source boost + spam admission + degrade triple.
- `market_router.py` / `vendor_breaker.py` / `effective_date.py` (dataflows) — market-classified vendor priority + breaker/half-open + effective-trading-date (DSA research §3.4/§3.6).
- `decision_guardrail.py` — post-PM downgrade-only stabilizer + versioned score<->rating validator + confidence cap on degraded data quality (advisory, DSA research §3.1).
- `market_tradability.py` — limit-up/down gates, suspension, volume
  participation caps, deal-price selector (Qlib exchange model, advisory).
- `normalized.py` — 5y median-margin EBIT + EV/EBIT + 5y PE percentile.
- `value_dip.py` — Value Dip + Swing hybrid (`Strategies/Value_Dip_swing*.md`):  Bollinger %b, historical valuation Z, FCF yield, breakeven win rate /
  expectancy, 3-tranche scale-in plan (P1/P2/P3, weighted avg entry, composite
  stop, capital-at-risk, blended R:R), the hybrid allocation matrix
  (`value_dip_setup`), the deterministic tranche-scaling risk fold
  (`tranche_risk_read`), and the six Step-1/Step-2 gap calculators:
  `balance_sheet_health` (D/E + current ratio), `profitability_quality`
  (FCF + ROE), `macd_divergence` / `volume_dry_up` / `trigger_candle` /
  `higher_low_structure` / `vdu_entry_setup` (the Step-2 ladder),
  `support_structure` (multi-month base / 200-SMA), and `decline_driver_check`
  (negative-force screen). Exposed as eleven value-dip analyst tools,
  `--scan value-dip`, and the folded risk gate.
- `factors.py` — composite rank (EY + momentum + 52w).
- `technical_factors.py` — KST, MFI, Stochastic, ADX, pivots, StochRSI, RSI2,
  W%R, Keltner, Donchian, OBV, PSAR, Elder thermometer + the research-added
  `aroon` (trend age), `fisher_transform` (normalized reversal),
  `chaikin_oscillator` (buying pressure), `elder_ray` (bull/bear power),
  `supertrend` (ATR trailing), `volume_profile` (POC + value area).
- `market_session.py` — pre/post-market session mechanics: `opening_range`
  (ORB breakout + 2R stop/target), `gap_type` (common/breakaway/runaway/
  exhaustion + fill stats), `order_imbalance` (buy/sell-heavy from flow
  nets), `premarket_liquidity` (thin-book warning), `post_close_confirmation`
  (stopped-out / target-hit / holding).
- `extended_indicators.py` — the standard trend/momentum/volume/structure
  group computed locally (no vendor): Ichimoku cloud, golden/death cross,
  CCI, ROC, momentum oscillator, TRIX, Force Index, A/D line, VPT, Chaikin
  Money Flow, anchored VWAP + `scan_candlesticks` (doji/hammer/shooting-star/
  engulfing/morning+evening star). Exposed as `get_extended_indicators` +
  `get_candlestick_patterns` on the market analyst.
- `dcf.py` — pragmatic FCF-DCF intrinsic valuation (WACC via CAPM, Gordon TV,
  EV->equity bridge) powering `get_dcf_valuation`.
- `journal.py` — `--journal` alloc/journal.
- `ratios.py` — computed valuation & profitability ratios (EV, EV/EBIT,
  EV/EBITDA, EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, liquidity,
  cash ratio, dividend yield, FCF, market cap) derived from the project's own
  canonical statements — a free, offline replication of the plan-gated Massive
  ratio block; exposed as `get_ratios` on the fundamentals analyst.
  Also adds the `inventory` canonical alias so Quick ratio computes.

## 4.2 Overlays

- `overlays.py` — `build_strategy_overlays(config, closes)`, `fold_flow*`,
  `apply_overlay_to_state`, `record_reflection_outcome`.
- `size.py` — ATR/vol targets / Kelly sizing (`atr`, `kelly_fraction`).
- `book_risk.py` — `cvar` (tail budget).
- `catalyst.py` — `build_catalyst_snapshot`, `fetch_catalyst_data`
  (earnings/macro/Fed scale 0..1), `fold_catalyst_into_overlay`,
  hard-block (REJECT inside window).
- `events.py` — `post_earnings_play`, `surprise_score`, `drift_side`.
- `risk_governor.py` — `govern()` -> PASS/WARN/REJECT; `build_risk_snapshot`.
- `contract.py` — `build_position_contract` (size + stop from min(Kelly,
  risk/stop)*vol*flow*agree*catalyst).
- `calibration.py` — `fit_buckets` (ledger win-rate -> calibrated P).
- `consensus.py` — `agreement_score` (debate stances -> agreement).
- `debate_context.py` — `build_computed_context` (numbers into debate).
- `exits.py` — stop/BE/targets.
- `reflection.py` — ledger, analyst hit-rates.
- `orderflow.py` — `fetch_flow`, `summarize`, divergence/alignment/exhaustion.
- `sentiment.py` — `compute_social_scores`, `computed_sentiment_line`,
  `aggregate_daily_sentiment` (feed -> daily mean scores, post-16:00 ET
  next-day bucket) + `daily_sentiment_sma` (calendar 7d SMA + innovation).
- `sentiment_research.py` — news-sentiment factor analytics (lead/lag,
  multi-horizon Newey-West HAC regression, sector-neutral z /
  size-residualization, rolling IC + IC-IR, IC term structure + half-life,
  weekly quintile long/short, `sentiment_factor_scale` overlay helper).
- `volatility_models.py` — Parkinson / Garman-Klass / EWMA / GARCH(1,1)
  volatility estimators (+ `volatility_estimator` overlay switch `close`
  default | ewma | garch).
- `mean_reversion.py` — demeaned AR(1)/OU half-life with an OLS t-test gate
  + `mean_reversion_verdict`.
- `fixed_income.py` — preferred YTM / duration / DV01 / convexity.
- `cross_section.py` — cookbook cross-sectional toolkit: `winsorize`,
  `cross_sectional_z`, `centered_rank` (2.RankPct-1), `quantile_split`,
  `residualize_returns` (market beta residual), `neutralize_book`
  (dollar + beta + sector-neutral via a row-space projection, gross
  renormalized), `no_trade_band`.
- `momentum.py` — MOP-style `ts_momentum_weights` (sign x inverse-EWMA-vol,
  target-vol normalized, gross-leverage capped).
- `options_math.py` — Black-76 with rho/vanna/vomma/charm + vanilla
  `bsm_equity_surface` + `greek_pnl_response` (delta-gamma-vega-theta P&L) +
  Cboe/VIX-style `model_free_implied_variance`.
- `book_risk.py` — `cdar` (Chekhlov drawdown-at-risk).
- `portfolio_optimizer.py` — `max_diversification_weights` (Choueifaty).
- `credit_spread.py` — `merton_distance_to_default` (equity-as-a-call).
- `rate_utils.py` — `forward_rate` between discount factors.
- `market_session.py` — `book_depth_read` (microprice + OBI).

## 4.3 Evaluation

- `evaluate.py` — walk-forward splits, Sharpe, deflated Sharpe, PBO flag
  (used by `scripts/evaluate_config_gate.py` G5).

## 4.4 How strategies feed the graph

- **Pre-graph**: the analyst tool loops call `get_*` tools that wrap a strategy
  function (e.g. `get_swing_set` -> `swing.swing_report`).
- **Post-graph**: `_apply_strategy_overlays` calls several of these in an
  order (see `02-graph-workflow.md` §2.6).

## 4.5 Config flags that gate them

`enable_regime` / `enable_factors` / `enable_sentiment` / `enable_threshold_gate`
default OFF; all `enable_*` overlays default ON except those four. Catalyst
keys: `catalyst_*`. Risk: `risk_*`. Sizing: `position_sizing`, `target_vol`,
`risk_per_trade`, `atr_mult`, `kelly_fraction`.

## 4.6 Adding a new strategy

1. Create `strategies/<name>.py` with pure functions.
2. Add a unit test `tests/test_strategies_<name>.py`.
3. Optionally expose it as an analyst tool via `analysis_tools.get_<x>` and
   bind it in the applicable analyst's tool node + prompt.
4. Optionally fold it into the overlay pipeline in `_apply_strategy_overlays`.
5. Add the config flag + `.env.example` override.
6. Update README/CHANGELOG/docs.

Continue to [`05-agents-tools.md`](05-agents-tools.md).