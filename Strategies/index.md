# Strategies — Index & Code Map

This is the navigation index for the `Strategies/` folder. It maps each
**plan / spec markdown** to the **`tradingagents/strategies/*.py` modules** that
implement it, the **config flags** that gate it, and the **consumer** (screener
mode, analyst tool, or overlay). Read `docs/developer/04-strategies.md` (the
module inventory) alongside this.

---

## The strategy plans at a glance

| # | Plan file | What it specifies | Implemented by | Config gate |
| --- | --- | --- | --- | --- |
| 1 | `Math.md` | Value-screening playbook (Magic Formula, Quantitative Value, value traps) | `dataflows/quantitative_scores.py`, `scripts/value_screener.py` | `--scan value` |
| 2 | `value_strategy.md` | Master-watchlist -> screened candidates -> analyst pipeline | `scripts/value_screener.py`, `strategies/factors.py` | `--rank composite`, `--alloc` |
| 3 | `value_style_gap_plan.md` | V1-V5 value-style enhancements (normalized earnings, composite rank, alloc) | `strategies/normalized.py`, `strategies/factors.py`, `strategies/portfolio.py` | `--enable-float`, `--alloc` |
| 4 | `framework.md` | Techno-fundamental swing trading (technical + fundamental + catalysts) | `strategies/swing.py`, `strategies/factors.py`, `strategies/catalyst.py` | `--scan swing` |
| 5 | `scan.md` | Screener scan modes (trend-pullback, breakout, momentum, swing, vcp) | `scripts/value_screener.py` (+ `strategies/{momentum,swing,size}.py`) | `--scan <mode>` |
| 6 | `momentum_day_trading.md` | Momentum day-trading (analysis-only signals: pillars, pullback, RVOL) | `strategies/momentum.py` | `--scan momentum` |
| 7 | `risk_management_plan.md` | Deterministic risk governor (PASS/WARN/REJECT, CVaR limits) | `strategies/risk_governor.py`, `strategies/book_risk.py` | `enable_risk_governor` |
| 8 | `decision_hardening_spec.md` | G1-G5 decision hardening (contract, calibration, consensus, PBO gate) | `strategies/{contract,calibration,consensus,evaluate}.py` | `enable_position_contract` / `enable_calibration` / `enable_agreement` / `enable_threshold_gate` |
| 9 | `enhancement_plan.md` | 8-phase research plan (regime, PEAD/catalyst, sentiment, reflection) | `strategies/{regime,catalyst,events,sentiment,reflection,evaluate}.py` | per-phase enable flags |
| 10 | `alpaca_data_analysis.md` | Alpaca market-data integration (analysis-only, no execution) | `dataflows/alpaca*.py`, `agents/utils/alpaca_tools.py` | `enable_alpaca` |
| 11 | `Discounted_Cash_Flow.md` | DCF valuation methodology (pragmatic FCF-DCF built from it) | `strategies/dcf.py`, `get_dcf_valuation` tool (fundamentals) | provider-sourced; growth/ERP overrides |
| 12 | `Value_Dip_swing.md` + `Value_Dip_swing_Continue.md` | Value Dip + Swing hybrid (margin of safety, valuation Z, FCF yield, RSI/%b oversold entry, tranche scale-in, blended expectancy) | `strategies/value_dip.py` + six value-dip analyst tools + the `tranche_risk_read` fold | `--scan value-dip`, `enable_value_dip` + `enable_tranche_risk` |
| 12b | (value-dip + swing combo research) | Additional dip/swing calculations studied against the project: Chandelier exit, KST, Money Flow Index, Stochastic %K, ADX, Fib retracement, pivot points, value+momentum composite | `strategies/technical_factors.py` + `swing.chandelier_exit`/`fib_levels` + `value_dip.fib_retrace_entry`/`_stochastic_oversold` + `factors.value_momentum_score` + `get_swing_exits`/`get_dip_technical` tools + screener MFI/StocK/KST/Chandel columns + `build_position_contract` trail_stop/implied_move | always-on (pure/optional) |
| 12c | (value-dip + swing combo research, round 2) | Exhaustive web research gaps: Graham Number, NCAV/net-net, Earnings Power Value (EPV), StochRSI, RSI2, Williams %R, Keltner, Donchian, OBV divergence, Parabolic SAR, Elder thermometer | `strategies/fundamental_floors.py` + `technical_factors` (stoch_rsi/rsi2/williams_r/keltner/donchian/obv/psar/elder) + `value_dip_setup` rows + `get_value_floors` (fundamentals) + `get_mean_reversion_tech` (market) tools + screener Graham/NCAV/EPV/StochRSI/RSI2/W%R/Kelt/Donch/OBV/PSAR/Elder columns | always-on (pure/optional) |
| 13 | `risk2.md` | Liquidity & ownership risk (IWF, float turnover, Amihud ILLIQ, days-to-absorb, HHI) | `strategies/liquidity_risk.py` + `get_liquidity_risk` (market) + `get_ownership_concentration` (fundamentals) + governor gate + screener columns | `enable_liquidity_gate` (off by default) |
| 14 | `capital_income.md` | Preferred-income index methodology (liquidity screen, indicated yield top-50, MV/equal + 3% cap) | `strategies/capital_income.py` + standalone `scripts/capital_income_screener.py` (no graph wiring) | standalone CLI |
| 15 | (screener sector table) | Full 11-SPDR sector ranking table (1m/3m returns, rank, top-3 flags) appended to the report when the ranking is computed | `scripts/value_screener.py::_sector_table_markdown` + `strategies/sector_rank.py` | `--sector-rank` / `--enrich-sector` |
| 16 | (conditional action report) | Check report verdicts against the risk basket: basket names on newest Underweight/Sell (reduce), non-basket on newest Overweight/Buy (add); extract the report's condition and check it against live OHLCV (MET/NOT_MET/UNKNOWN) | `scripts/action_report.py` + `agents/schemas.ActionConditionVerdict` + `agents/overrides/action_condition_judge.py` | `--basket` / `--llm` (optional judge) |
| 17 | (value-dip + swing + pre/post-market research) | 6 new technical factors (Aroon, Fisher, Chaikin, Elder-Ray, Supertrend, volume profile) + market-session module (opening range/ORB, gap type, order imbalance, premarket liquidity, post-close confirmation) + 5 market-analyst tools + screener Aroon/Fisher/Supertrend/POC columns | `strategies/technical_factors.py` + `strategies/market_session.py` + `analysis_tools.get_opening_range`/`get_gap_type`/`get_order_imbalance`/`get_premarket_liquidity`/`get_post_close_confirmation` + `value_screener` columns | always-on (pure/optional) |
| 18 | (industry-practice suggestions) | Correlation-aware allocation, book-level correlated stress, liquidity-aware costs, paper-ledger track record, limit-order directive, claim-vs-computed audit, strategy-quality report | `strategies/portfolio.py` (correlation_penalty) + `book_risk.book_correlated_stress` + `exits`/`evaluate` (illiq) + `pre_market.ledger_track_record` + `pre_market_review.py` (limit-order) + `reporting.audit_decision_numbers` + `scripts/strategy_quality_report.py` | `enable_decision_audit` (opt-in) |
| 19 | `News_Sentiment.md` + `News_Sentiment_Implementation_Plan.md` | News-sentiment factor: EODHD `/sentiments` daily series (-1..1 + 7d SMA + innovation), AV/GDELT fallbacks; lead/lag, multi-horizon Newey-West regression, sector/size neutralization, rolling IC + half-life, quintile long/short; opt-in overlay fold | `strategies/sentiment.py`, `strategies/sentiment_research.py`, `dataflows/{eodhd,alpha_vantage_news,gdelt}`, `scripts/sentiment_factor_eval.py`, screener `--sentiment` (Sent7/SentZ), `overlays.fold_sentiment_into_overlay` | `enable_sentiment_factor` (off) + `sentiment_factor_*` config |
| 20 | `quants.md` + `quant2.md` + `Quant_Formulas_Implementation_Plan.md` + `formulas/` (6-pillar + master catalog) | Quant formula map implemented: volatility estimators (Parkinson/GK/YZ/EWMA/GARCH + overlay switch), Ledoit-Wolf shrunk + EWMA covariance, book concentration (active share / effective holdings / HHI / entropy), tail decomposition (incremental/component VaR) + EVT/GPD extreme-quantile VaR/ES, mean-reversion quality (AR(1)/OU half-life), Roll spread + Kyle lambda, multi-asset fractional Kelly alloc, preferred YTM/duration/DV01, credit hazard, variance-swap strike, implementation shortfall | `strategies/{volatility_models,covariance_models,mean_reversion,fixed_income,book_risk,portfolio,liquidity_risk,credit_spread,options_math,evaluate}.py` + `scan/capital_income --fi` | `volatility_estimator` (default close) + `covariance_shrinkage_enable`/`enable_kelly_alloc` (default off) |
| 21 | `cookbook.md` | Quant-strategy cookbook (5 recipes + common framework): MOP time-series momentum, cross-sectional mean reversion, cointegration pairs, multifactor factor portfolios, options volatility — all implemented | `strategies/{momentum,cross_section,statistical,factors,evaluate,options_math,book_risk,portfolio_optimizer,credit_spread,rate_utils,market_session}.py` + tools `get_ts_momentum_weights`/`get_pair_trade_signal`/`get_event_pnl_response`/`get_book_depth_read`/`get_merton_distance` | advisory (bound to market analyst + risk debators) |
| 22 | `docs/design_hummingbot_integration.md` | Hummingbot V2 teacher study (Strategy/Controller/Executor, per-executor CloseType accounting, budget-collateral lock, live-book fill-latency, unified executor ledger, async notifier) — adopted as advisory exit-accounting / collateral-lock / fill-latency / ledger-spec / notifier phases | design only (no code) | phase-gated, default-off |
| 23 | `docs/design_ai_hedge_fund_integration.md` | ai-hedge-fund v2 teacher study (mandate-as-data fund/strategy/model YAML, event-study market-model CAR + significance, abstention-vs-neutral conviction blending, per-clamp risk audit events, prompt provenance vault) — adopted as advisory mandate/event-study/abstention/clamp/vault phases | design only (no code) | phase-gated, default-off |
| 24 | `docs/design_fincept_terminal_integration.md` | FinceptTerminal v4 (C++20/Qt6 + embedded Python) teacher study — typed topic-registry refresh policy (TTL/min-interval/coalesce/freshness), tool-result size budget with park-and-page, dual tool-loop budget + visible exhaustion + progress narration, SQLite per-step checkpoints + resume, org-as-data governance metadata (seniority/risk_tolerance/rigor criteria), single-source-of-truth capability cross-check gate — adopted as advisory topic-policy/result-store/budget-visibility/resume/governance/gate phases | design only (no code) | phase-gated, default-off |
| 25 | `docs/design_yfinance_integration.md` | yfinance v1.7.0 (ranaroussi; one of the fork's no-key vendors) teacher study — typed absence taxonomy (reason-carrying errors, lazy capability), exchange-tz + currency KV cache with validation/invalidation for OHLCV reads, 100x currency-unit repair (detected + flagged), batch error grouping + debug-serialize rule, deliberate 1.x pin — adopted as advisory absent-reason/tz-cache/unit-repair/batch-diagnostics/pin phases | **P1 adopted** (`VendorAbsence` + contextvar side channel + `VendorResult.absence` + OHLCV/run_card/web `absence` field; tests `test_vendor_absence`), **P5 adopted** (`yfinance~=1.4` pin + `dataflows/README.md` vendor notes); P2/P3/P4 design-only | P1: always-on (read-only fields, defaults null); P5: dependency pin |
| 26 | `docs/design_anthropic_financial_services_integration.md` | anthropics/financial-services teacher study (skills as single source, vendored into agent bundles with a `check.py` byte-identity drift gate; one-source/two-wrapper agent prompts; `output_schema` + harness-side validation; data-vs-directions guardrails) — adopted as advisory skill-drift-gate / guardrail-text / output-shape / trigger-phrase / bundle-assessment phases | design only (no code) | phase-gated, default-off |
| 27 | `docs/design_myhhub_stock_integration.md` | myhhub/stock (InStock; Chinese A-share rule-based quant platform) teacher study — trading-calendar singleton (is_trade_date / prev / next with None fallbacks) feeding the `effective_date` override hook, session-aware scheduling hint (after-close jobs skip mid-session), uniform strategy-predicate + min-obs guard convention, env-first credential priority — adopted as advisory calendar-cache / session-hint / obs-guard / credential-priority phases; live robot + MySQL persistence + GUI are non-goals | design only (no code) | phase-gated, default-off |

---

## 1. `Math.md` — value-screening source playbook

**What it is:** curated reading for systematically generating a master watchlist
of value stocks (Magic Formula / Quantitative Value / Acquirer's Multiple).

**Implemented by**:
- `tradingagents/dataflows/quantitative_scores.py` — the quantitative score
  helpers (EY, EV/EBIT, Piotroski, Beneish, Normalized).
- `scripts/value_screener.py` — the `--scan value` classic screens.

**Related**: `Strategies/value_strategy.md`, `Strategies/value_style_gap_plan.md`.

---

## 2. `value_strategy.md` — master watchlist -> analyst pipeline

**Status**: plan + reference implementation.

**What it specifies**: turn the screening playbook into an executable strategy
layered on the vendor pipeline (`route_to_vendor`) so a generated watchlist
feeds straight into the analyst teams. **Status:** plan + reference implementation.

**Implemented by**: `scripts/value_screener.py` (screens + `--rank`), plus
`strategies/factors.py` (composite rank), `strategies/portfolio.py` (alloc).

---

## 3. `value_style_gap_plan.md` — value-style enhancement plan

**Gap map** (V1..V5):
- **V1** Normalized earnings + trap verdict -> `strategies/normalized.py`;
- **V2** composite (value + momentum) ranking -> `strategies/factors.py`;
- **V3** book/portfolio caps -> `strategies/portfolio.py`;
- **V4** ATR exits / rebalance -> `strategies/exits.py`;
- **V5** computed numbers into debate -> `strategies/debate_context.py`.

---

## 4. `framework.md` — techno-fundamental swing framework

**Specifies** multi-day/multi-week swing execution: liquidity threshold, technical
structure, momentum screen, fundamental quality filters, event catalysts.

**Implemented by**: `strategies/swing.py` (2R/3R targets, 1-ATR stop, trail),
`strategies/factors.py` (quality), `strategies/catalyst.py` (event de-risk).
Consumed via `--scan swing` in the screener and `get_swing_set` analyst tool.

**Related**: `Strategies/scan.md`, `Strategies/value_strategy.md`.

---

## 5. `scan.md` — screener scan modes

**Specifies** `scripts/value_screener.py --scan <mode>`:
`value`, `trend-pullback`, `breakout`, `momentum`, `swing`, `vcp`, `all`.

**Gate rule**: every gate is computed, never narrated; a missing data point makes
a gate "unknown" (ignored, not failed). Runs on top of liquidity / price / mcap /
PE / ATR filters.

**Implemented by**: `scripts/value_screener.py` mode functions + the strategies
in `docs/developer/04-strategies.md` §4.1 (swing, momentum, relative_strength).

---

## 6. `momentum_day_trading.md` — momentum / day-trading signals

**Analysis-only adaptation** of the momentum playbook: no order/execution
endpoints. Turns the playbook into detectable screening & risk signals via
`strategies/momentum.py` (pillars, first-pullback, RVOL, session flags) and
`strategies/contract.py` + `strategies/book_risk.py` for sizing/risk.
Consumed via `--scan momentum` and `get_momentum_scan`.

---

## 7. `risk_management_plan.md` — deterministic risk governor

**Specifies**: replace chatty 3-LLM risk debate with a **deterministic
pre-trade control** (limits, stress, escalation, audit); the LLM only argues at
breaches with numbers.

**Implemented by**: `strategies/risk_governor.py` (`govern` -> PASS/WARN/REJECT,
`build_risk_snapshot`) + `strategies/book_risk.py` (CVaR). Wired in
`graph/trading_graph.py::_apply_strategy_overlays` when `enable_risk_governor`.
Audit rows -> `risk_audit.jsonl`.

---

## 8. `decision_hardening_spec.md` — "compute, don't narrate"

**Status**: spec; the modules below are the implementation targets.

- **G1** deterministic position & stop -> `strategies/contract.py`.
- **G2** calibration (bucket win-rate -> P) -> `strategies/calibration.py`.
- **G3** computed agreement / consensus -> `strategies/consensus.py` + `agents/utils/rating.py`.
- **G5** walk-forward / PBO gate -> `strategies/evaluate.py` consumed by
  `scripts/evaluate_config_gate.py`.

Relevant config: `enable_position_contract`, `enable_calibration`,
`enable_agreement`, `enable_threshold_gate`.

---

## 9. `enhancement_plan.md` — 8-phase research plan

Phase-by-phase plan for 8 trading threads with arXiv/coverage references. All
phases config-gated and off by default:
- Phase 0..2 regime / sizing -> `strategies/regime.py`, `strategies/size.py`
- Phase 4 PEAD / catalyst -> `strategies/events.py`, `strategies/catalyst.py`
- Phase 5 reflection -> `strategies/reflection.py`
- Phase 6 media sentiment -> `strategies/sentiment.py`
- Phase G5 PBO gate -> `strategies/evaluate.py`

---

## 10. `alpaca_data_analysis.md` — Alpaca market-data integration (analysis-only)

**Scope constraint**: no trading/execution/orders/positions/portfolio P&L.
Only market-data/calendar/asset enrichment.

**Implemented by**: `dataflows/alpaca*.py` (incl. `alpaca_common.py`,
`alpaca.py`), `agents/utils/alpaca_tools.py` (the `get_market_snapshot_alpaca`
tool, `get_bars`), gated by `enable_alpaca`. See the `alpaca_data_analysis.md`
for the endpoint allowlist.

---

## Cross-map: where strategies meet the graph & reports

| Strategy area | Consumer (graph tool / overlay / screener) |
| --- | --- |
| Value screens | `scripts/value_screener.py`, `get_analyst_verdict` (fundamentals analyst) |
| Value Dip + Swing | `get_bollinger_pct_b`, `get_tranche_plan`, `get_trade_expectancy` (market); `get_fcf_yield`, `get_valuation_z_score`, `get_value_dip_setup` (fundamentals) + `--scan value-dip`; tranche risk fold in `graph/trading_graph._apply_strategy_overlays` |
| Swing/RS/VCP | `get_swing_set`, `get_relative_strength`, `get_volatility_contraction` (market analyst) + `--scan` |
| Catalyst/events | `get_catalyst_scale`, `get_earnings_event_read` (news analyst) + `_apply_strategy_overlays` |
| Momentum | `get_momentum_scan`, `--scan momentum` |
| Risk governor | `graph/trading_graph.py::_apply_strategy_overlays` (PASS/WARN/REJECT) |
| Contract/sizing | `get_position_sizing`, `_apply_strategy_overlays` |

---

## Strategy config flags quick lookup

- **Value screens**: `--scan`, `--rank`, `--enable-float`, `--alloc`
- **Value Dip + Swing tranche risk**: `enable_tranche_risk`, `tranche_*` (weights/stop_mult/risk_pct/account)
- **Swing/framework**: `--scan swing`, `--min-atr-pct`, `--min-avg-vol`
- **Momentum/day**: `--scan momentum`
- **Risk governor**: `enable_risk_governor`, `risk_*`
- **Position contract**: `enable_position_contract`, `position_sizing`,
  `target_vol`, `risk_per_trade`, `atr_mult`, `kelly_fraction`
- **Calibration**: `enable_calibration`, `calibration_min_n`
- **Threshold/PBO**: `enable_threshold_gate`, `evaluate_cost_bps`

See [`docs/developer/04-strategies.md`](../docs/developer/04-strategies.md) for
the module reference, and `docs/AGENT_ONBOARDING.md` for the work prescriptions.