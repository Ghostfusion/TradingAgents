# Risk Calculations → Virtual Agents: Audit + Implementation Plan

**Status:** audit done against the current working tree (2026-08-31); plan
only — no code changed.
**Goal:** feed as many deterministic risk calculations as possible to the
agents that make the risk decision (the 3 risk debators, the Trader, the
Portfolio Manager), plus any other virtual agent that argues about risk
numbers today without them. All wiring follows the repo contract:
compute-as-tools, no-fabrication, advisory-first (gates already stay in the
risk governor overlay).

---

## 0. TL;DR

- The repo already has **~140 deterministic risk/risk-adjacent calculations**
  across `tradingagents/strategies/*` (VaR/CVaR family, governor, liquidity,
  sizing, exits, credit, vol models, options, fixed income, stats, eval,
  catalyst/event risk, consensus/calibration, pre-trade gates).
- Of those, **~36 are wrapped as analyst `@tool`s**. The remaining risk calcs
  are either (a) only consumed by the deterministic overlays / scripts, or
  (b) wrapped but **not reachable by any LLM**.
- The risk decision layer (`aggressive/conservative/neutral` debators,
  Trader, Portfolio Manager) has **no tool loop at all**. They receive a
  ~5-line prose `computed_decision_context` (regime gate, plan card, 1 CVaR
  line, drift hint, pre-open reads). The bulk of the risk math stays in the
  Market analyst's tool loop — 55 tools bound to the LLM, of which 18 are
  registered in the Market `ToolNode` but **not in the LLM's bound list**
  (unreachable), and 2 more tools are bound to **no node at all**.
- Plan: 7 phases — (1) repair the 18-tool binding gap; (2) wrap the untooled
  risk calculators as new `@tool`s; (3) enrich the shared decision context
  into a full computed "risk factsheet" (no topology change); (4) give the 3
  risk debators their own risk-`ToolNode` tool loop; (5) give the Trader a
  sizing/exits `ToolNode`; (6) cross-bind risk tools to news / fundamentals /
  researchers / PM; (7) web mirror + docs + tests, per the working agreement.

---

## 1. Audit scope & method

- **Risk surface inventory:** every public function in `tradingagents/strategies/`
  whose output is a risk number / risk verdict / risk-gating input (vol, tail,
  liquidity, sizing, stops, credit, options, fixed income, evaluation,
  pre-trade limits, catalyst/event de-risk, calibration/consensus).
- **Tool status:** `@tool` definitions in `agents/utils/*.py` (grep `^def get_`),
  per-node binding in `graph/trading_graph.py::_create_tool_nodes`, and per-
  analyst LLM binding (`llm.bind_tools(tools)` in each `agents/analysts/*.py`).
- **Reachability check:** diff ToolNode registration vs the analyst `tools`
  list, and diff every `@tool` vs every ToolNode (orphan scan), executed with
  a read-only `py -3.12 -c` script (no code changed).

---

## 2. Risk calculation inventory (by module)

Legend — **T+B** tooled and bound to an LLM; **T-U** tooled but unreachable
(registered in a ToolNode yet absent from the analyst's bound list, or bound
to no node); **C** consumed only by the deterministic overlay / context
injection (computed for the agents but not a callable tool); **-**
untooled (no `@tool` anywhere).

### 2.1 Tail / portfolio risk — `book_risk.py` (11 calcs)

| Function | Status | Agent today |
| --- | --- | --- |
| `simple_var` | T+B (`get_tail_risk`) | market |
| `cvar` | T+B (`get_tail_risk`) + C (PM `risk_context`, governor) | market, PM line |
| `portfolio_cvar` | T+B (`get_book_tail_risk`) + C (governor) | market, PM line |
| `portfolio_returns` | C (tool helper) | — |
| `stress_loss` | T+B (`get_tail_risk`) | market |
| `book_correlated_stress` | T+B (`get_book_tail_risk`) + C (PM line) | market, PM line |
| `drawdown_gate` | T+B (`get_book_tail_risk`) | market |
| `incremental_var` | T+B (`get_tail_decomposition`) | market |
| `component_var` | T+B (`get_tail_decomposition`) | market |
| `return_autocorrelation` | C (inside `get_horizon_var`) | market |
| `var_cvar_horizon` | T+B (`get_horizon_var`) | market |

### 2.2 Risk governor — `risk_governor.py` (3)

| Function | Status | Agent today |
| --- | --- | --- |
| `default_limits` | C (overlay `govern`) | — |
| `govern` (PASS/WARN/REJECT) | T+B (`get_risk_gate`, **partial surface**) + C (overlay, authoritative) | market; post-graph |
| `build_risk_snapshot` | T+B (`get_risk_gate`) | market |

### 2.3 Liquidity / ownership — `liquidity_risk.py` (9)

| Function | Status | Agent today |
| --- | --- | --- |
| `free_float_factor` (IWF) | T+B (`get_ownership_concentration`) | fundamentals |
| `float_turnover` | T+B (`get_liquidity_risk`) | market |
| `amihud_illiquidity` | T+B (`get_liquidity_risk`) + C (governor gate) | market |
| `days_to_absorb` | T+B (`get_liquidation_days`) | market |
| `ownership_hhi` | T+B (`get_ownership_concentration`) | fundamentals |
| `liquidity_verdict` | T+B (`get_liquidity_risk`) + C (governor `enable_liquidity_gate`) | market, PM line |
| `volume_share_slippage` | **-** (backtest/paper costs only) | — |
| `market_impact_slippage` | **-** (backtest/paper costs only) | — |
| `roll_spread` | T+B (`get_liquidity_risk` renders it) | market |

### 2.4 Sizing (risk-first) — `size.py` (7) + `risk_sizing.py` (4)

| Function | Status | Agent today |
| --- | --- | --- |
| `kelly_fraction` / `position_size_kelly` | T+B (`get_position_sizing`) + C (contract) | market |
| `volatility_target_scale` | C (overlay) | — |
| `atr` / `stop_loss_atr` | C (contract, `get_swing_set` renders) | market |
| `cvar_budget` | C (contract) | — |
| `position_size_with_risk` | T+B (`get_position_sizing`) | market |
| `risk_points` | **-** | — |
| `riskable_money` (commission-aware) | **-** | — |
| `risk_money` (fixed-risk units) | **-** | — |
| `risk_quantity` (tranche split) | **-** | — |

### 2.5 Contract / exits / risk manager — `contract.py` (1), `exits.py` (9), `risk_manager.py` (2)

| Function | Status | Agent today |
| --- | --- | --- |
| `build_position_contract` | C (overlay; `get_risk_gate`/`get_position_sizing` feed it) | post-graph |
| `stop_to_breakeven` / `_r` / `target_level` | T+B (`get_exit_check`, `get_exit_plan`) | market |
| `net_of_cost` | C (eval) | — |
| `rebalance_due` | C (scripts) | — |
| `exit_check` | T+B (`get_exit_check`) | market |
| `breakeven_after_confirmation` | T+B (`get_exit_plan`) | market |
| `trailing_stop_exit` | T+B (`get_trailing_exit`) | market |
| `max_giveback_exit` | T+B (`get_trailing_exit`) | market |
| `manage_risk` (two-pass exit overrides) | **-** (paper-execution path only) | — |
| `trailing_stop_targets` | **-** (paper-execution path only) | — |

### 2.6 Credit / default — `credit_spread.py` (5)

| Function | Status | Agent today |
| --- | --- | --- |
| `credit_stress_level` (band + de-risk scale) | T+B (`get_credit_spread_read`) | **market only** (news analyst makes macro risk claims without it) |
| `hazard_from_spread` | T+B (rendered inside `get_credit_spread_read`) | market |
| `default_probability` | T+B (rendered inside `get_credit_spread_read`) | market |

### 2.7 Volatility models — `volatility_models.py` (4) + `options_math.py` (4) + `regime.py` (≈4)

| Function | Status | Agent today |
| --- | --- | --- |
| `parkinson_vol` / `garman_klass_vol` / `ewma_vol` | T+B (`get_volatility_estimators`) | market |
| `garch11_fit` | T+B (`get_garch_volatility`) | market |
| `black76` / `implied_vol_and_greeks` / `black_vol_surface` | T-B (used by `get_variance_premium`) + cboe `get_options_surface` | market (options surface), none (variance premium) |
| `variance_swap_strike` | T-U (`get_variance_premium` bound to **no node**) | — |
| `realized_vol` / `vol_percentile` / `regime_label` / `regime_gate_read` | T+B (`get_regime_read`/`get_regime_components`) + C (decision-context line) | market, debators (1 context line) |

### 2.8 Mean reversion / statistics / rotation — `mean_reversion.py` (3), `statistical.py` (9), `rotation.py` (3)

| Function | Status | Agent today |
| --- | --- | --- |
| `ar1_half_life` / `ou_half_life` / `mean_reversion_verdict` | T+B (`get_mean_reversion_quality`) | market |
| `normality` / `unit_root` | T-U (in node, not bound) | — |
| `omega` | T-U (in node, not bound) | — |
| `correlation_matrix` | T-U (`get_book_correlation`, in node, not bound) | — |
| `cointegration_pair` | **-** | — |
| `granger_causality` | **-** | — |
| `capm_decomposition` | T-U (`get_capm_risk`, in node, not bound) | — |
| `ols_factors` / `variance_inflation_factor` | **-** | — |
| `relative_rotation` | T-U (in node, not bound) | — |
| `clenow_momentum` | T-U (in node, not bound) | — |
| `vol_cones` | **-** | — |

### 2.9 Evaluation / quality — `evaluate.py` (≈29), `journal.py` (2), `alpha_eval.py` (2)

| Function | Status | Agent today |
| --- | --- | --- |
| `sharpe` / `sortino` / `max_drawdown` / `cagr` / `volatility` | T+B (`get_strategy_quality`) | market |
| `deflated_sharpe` / `pbo_flag` / `walk_forward_splits` | C (G5 gate scripts) | — |
| `downside_deviation` / `downside_measures` | T+B (`get_downside_read`) | market |
| `tracking_error` / `information_ratio` / `beta` / `alpha` / `treynor` / `rolling_beta` | C (memory alpha; `get_strategy_quality` partial) | — |
| `probabilistic_sharpe` | T+B (`get_strategy_quality`) | market |
| `underwater_drawdowns` / `calmar_ratio` / `ulcer_index` / `capture_ratio` / `tail_ratio` / `expectancy_stats` | T+B (`get_strategy_quality`) | market |
| `implementation_shortfall` | C (strategy-quality execution block) | — |
| `trade_excursions` (MAE/MFE) | **-** | — |
| `alpha_score` / `insight_accuracy` (magnitude-scored alpha) | **-** | — |

### 2.10 Pre-trade / paper-execution gates — `risk_checks.py` (3), `backtest_models.py` (5)

| Function | Status | Agent today |
| --- | --- | --- |
| `RateLimiter` / `pre_trade_check` / `notional` | **-** (backtest/paper path) | — |
| `fixed_fee` / `maker_taker_fee` / `slip_price` / `make_cost_fn` / `limit_fill_probability` | **-** (`scripts/backtest_strategy.py`) | — |

### 2.11 Catalyst / event risk — `catalyst.py` (≈6), `events.py` (8), `pre_market.py` (≈6)

| Function | Status | Agent today |
| --- | --- | --- |
| `build_catalyst_snapshot` / `fold_catalyst_into_overlay` / `apply_catalyst_scale` | T+B (`get_catalyst_scale`) + C (overlay) | news, post-graph |
| `last_earnings_surprise` / `next_earnings` / `implied_move_from_history` | T+B (`get_earnings_event_read`, `get_expected_move`) | news, market |
| `surprise_score` / `drift_side` / `position_mult_by_side` | T+B (`get_beat_miss_sizing`, `get_earnings_event_read`) | news |
| `expected_drift_after` / `catalyst_risk_penalty` / `gap_up_qualifies` / `consolidation_and_break` / `post_earnings_play` | C (inside `get_earnings_event_read`) | news |
| `premarket_gap` / `catalyst_window_read` / `reanchor_plan` / `review_decision` | T+B (`get_premarket_review`) | market |
| `ledger_track_record` (paper-book win rate) | **-** (script only) | — |

### 2.12 Value-Dip / tranche / portfolio — `value_dip.py` (risk rows), `portfolio.py` (8), `portfolio_optimizer.py` (5), `consensus.py` (3), `calibration.py` (4), `factors.py`, `fixed_income.py` (6)

| Function | Status | Agent today |
| --- | --- | --- |
| `tranche_plan` / `tranche_risk_read` | T+B (`get_tranche_plan`) + C (governor `peak_deployed_pct`/`capital_at_risk_pct`) | market, post-graph |
| `expectancy` / `breakeven_win_rate` | T+B (`get_trade_expectancy`) | market |
| `allocation_block` / `adjust_for_caps` / `correlation_penalty` | T+B (`get_allocation`, `get_portfolio_weights`) | fundamentals |
| `risk_parity_weights` / `min_variance_weights` / `confidence_weights` / `risk_contribution` | T-U (`get_risk_parity_alloc`, in node, not bound) | — |
| `agreement_score` / `consensus_from_score` | T+B (`get_consensus`) + C (PM line) | fundamentals, PM |
| `fit_buckets` / `calibrated_confidence` | C (injected calibration table into PM context) | PM (context only) |
| `preferred_ytm` / `macaulay_duration` / `modified_duration` / `dv01` / `bond_convexity` | **-** (`capital_income` screener only) | — |

### 2.13 Mode / session risk — `momentum.py` (risk rows), `market_session.py` (5), `trade_plan.py` (1)

| Function | Status | Agent today |
| --- | --- | --- |
| `session_flags` / `psych_level` / `past_optimal_window` | T+B (`get_session_discipline`, `get_momentum_detail`) | market |
| `opening_range` / `gap_type` / `order_imbalance` / `premarket_liquidity` / `post_close_confirmation` | T+B (5 separate tools) | market |
| `build_trade_plan` | C (injected plan card into decision context) | debators/trader/PM (context only) |

**Counts:** ≈140 risk/risk-adjacent calculations total; ≈36 tooled; of the
tooled — 18 are unreachable by the Market LLM (section 3), 2 are bound to no
node (`get_variance_premium`, `get_news_sentiment`); ≈15 risk calculators
have no `@tool` at all (commission sizer, pre-trade gates, two-pass exit
overrides, MAE/MFE, magnitude-alpha, fixed-income, cointegration/Granger/VIF,
vol-cones, paper-ledger track record).

---

## 3. Current wiring per agent (what each virtual agent can compute today)

| Agent | Tools bound to LLM | Computed context injected | Risk-calc gap |
| --- | --- | --- | --- |
| **Market analyst** | 55 (node holds 73) | none | 18 node tools unreachable (below) |
| **News analyst** | 18 | none | credit-stress / unit-root / macro risk-off read missing |
| **Fundamentals analyst** | 31 (node 32) | none | fixed-income risk (preferreds), magnitude-alpha missing |
| **Sentiment (social)** | 0 (pre-fetched blocks) | none | n/a (data, not risk) |
| **Bull / Bear researchers** | 0 | **no computed context** (only analyst reports) | risk factsheet absent |
| **Trader** | 0 | `computed_decision_context` | sizing/exits not callable |
| **Aggressive / Conservative / Neutral** | 0 | `computed_decision_context` | **the risk team has no risk tools** |
| **Research Manager** | 0 | none (plan from debate) | consensus/allocation absent |
| **Portfolio Manager** | 0 | consensus + CVaR + liquidity lines + computed context | book-level tools absent |

**Market ToolNode ∩ analyst-bound diff (18 tools the LLM cannot call,**
`tradingagents/agents/analysts/market_analyst.py::tools` vs
`graph/trading_graph.py::_create_tool_nodes["market"]`):

```
get_book_correlation   get_capm_risk        get_clenow_momentum
get_downside_read      get_exit_plan        get_horizon_var
get_market_movers      get_normality        get_options_surface
get_payoff_asymmetry   get_relative_rotation get_risk_parity_alloc
get_scaleout_plan      get_sentiment_computed  get_sofr_curve
get_trailing_exit      get_treasury_curve   get_unit_root
```

**The decision context** (`graph/trading_graph.py::_compiled_decision_context`,
the ONLY deterministic numbers the Trader/PM/3 risk debators see) currently
emits ~5 lines: regime-gate verdict, `build_trade_plan` card, one CVaR line
(single/book/stress from `risk_context`), an alpha-decay hint, and pre-open
RVOL/gap/depth lines when `enable_preopen_*` is on. No volatility estimates,
no liquidity verdict (PM gets it separately), no credit stress, no tranche
capital-at-risk, no governor limits, no fixed-risk size, no expected move.

---

## 4. Findings (the gaps this plan closes)

1. **F1 — 18 registered risk tools are unreachable** by the Market LLM
   (bound in the ToolNode, absent from `bind_tools`). These are exactly the
   quant-risk tools (horizon-VaR, downside, trailing exit, risk-parity,
   normality/unit-root, CAPM, rotation, Clenow, omega, correlation, scale-out,
   sentiment-computed, curve surfaces, movers). Zero LLM can cite them today.
2. **F2 — orphan tools bound to no node:** `get_variance_premium`
   (analysis_tools, in `agent_utils.__all__`, absent from every ToolNode) and
   `get_news_sentiment` (news_data_tools chain tool).
3. **F3 — the risk decision layer has no tool loop.** 3 risk debators +
   Trader + PM argue risk from prose reports + a ~5-line context string;
   the Market analyst is the sole risk-number funnel (55 tools in one prompt).
4. **F4 — untooled risk calculators:** `risk_sizing.py` (commission-aware
   fixed-risk sizer: `risk_points`, `riskable_money`, `risk_money`,
   `risk_quantity`), `risk_checks.py` (`pre_trade_check`, `RateLimiter`,
   `notional`), `risk_manager.py` (`manage_risk`, `trailing_stop_targets`),
   `fixed_income.py` (preferred YTM/duration/DV01/convexity),
   `journal.trade_excursions` (MAE/MFE/profit-factor),
   `alpha_eval.alpha_score`/`insight_accuracy` (magnitude-scored alpha),
   `statistical.cointegration_pair`/`granger_causality`/`ols_factors`/
   `variance_inflation_factor`, `rotation.vol_cones`,
   `pre_market.ledger_track_record`, `hmm_regime` (hmmlearn-gated).
5. **F5 — `get_risk_gate` exposes only part of `govern()`.** The governor
   accepts `daily_loss_pct`, `hwm_drawdown_pct`, `liquidity_verdict`,
   `capital_at_risk_pct`, `risk_cap_pct`, `sector_pct` — the tool only passes
   `cvar_pct` + `drawdown_pct`. The LLM's risk-gate calls therefore give
   PASS/WARN/REJECT on an incomplete limit set.
6. **F6 — risk tools bound to the wrong/only agent:** credit stress +
   unit-root belong in the News/Macro loop; fixed-income belongs in
   Fundamentals; book-level allocation/risk-parity belongs with the PM /
   risk debators, not only the Market analyst; the Bull/Bear researchers get
   no computed context at all.

---

## 5. Implementation plan (phased, smallest-first)

### Phase 1 — Make existing tools reachable (quick win, no new calculators)

- Add the 18 unreachable tools (F1) to
  `tradingagents/agents/analysts/market_analyst.py` `tools` list + prompt
  lines (one-line "use before X claim" each, matching existing style); keep
  the ToolNode unchanged (it already imports them).
- Bind the 2 orphans (F2): `get_variance_premium` to the market node + list
  (event-vol claim); `get_news_sentiment` to the news node behind
  `get_news_sentiment_series` (or drop the alias if redundant — decide by
  usage; prefer keeping the chain tool exposed).
- **Acceptance:** a hermetic `test_analysis_tools.py`-style guard asserts
  every ToolNode-registered tool for an analyst is present in that analyst's
  `bind_tools` list and vice-versa (the audit script becomes a test:
  `test_toolnode_bound_tools_are_reachable`); market analyst bound count
  55 → 73.

### Phase 2 — Wrap the untooled risk calculators as new `@tool`s

All wrap existing pure strategies functions; signatures follow tool style
(`float | None`, explicit `unavailable`), bound per the table.

| New tool | Wraps | Bound to | Why it matters |
| --- | --- | --- | --- |
| `get_fixed_risk_size(equity, risk_frac, entry, stop, commission_rate, units)` | `risk_sizing.riskable_money`/`risk_money`/`risk_quantity` | market (and Trader node in Phase 5) | the one commission-aware, tranche-aware sizer; makes the governor's budget and the sizer agree from the LLM side |
| `get_exit_overrides(targets, state_by_name, max_drawdown_pct, trail_pct)` | `risk_manager.manage_risk` + `trailing_stop_targets` | risk debators / PM (advisory; needs persisted `state_by_name` from paper ledger; returns `unavailable` without it) | Lean-style second-pass liquidate/shrink override the LLMs can reference for held names |
| `get_pre_trade_read(symbol, notional, symbol_notional, max_notional, max_rate, window_secs)` | `risk_checks.pre_trade_check` + `RateLimiter` + `notional` | risk debators (advisory) | submission-rate + notional-cap bound for paper/backtest execution context |
| `get_trade_plan(ticker, price, ...)` | `trade_plan.build_trade_plan` (+ tranche/exits/be_rule inputs) | Trader node (Phase 5) + PM context | makes the plan card a callable first-class object instead of only a context string |
| `get_ledger_risk_state(ticker)` | `pre_market.ledger_track_record` + memory-log realized entries (`daily_loss_pct`, `hwm_drawdown_pct`, win-rate drift) | risk debators + PM | supplies the `daily_loss` + `hwm` inputs the governor's `get_risk_gate` currently cannot see (F5) |
| `get_fixed_income_risk(ticker, price?, par?, years?)` | `fixed_income.preferred_ytm`/`macaulay_duration`/`modified_duration`/`dv01`/`bond_convexity` | fundamentals | preferreds/income names: yield + duration + DV01 risk rows (labels perpetuals n/a, never a fake YTM) |
| `get_pair_risk(x, y, maxlag)` | `statistical.cointegration_pair` + `granger_causality` | market | pair mean-reversion + lead-lag, mark-to-market style |
| `get_vif_read(columns)` | `statistical.variance_inflation_factor` | market | collinearity check before the LLM stacks factor claims |
| `get_vol_cones(ticker)` | `rotation.vol_cones` | market | multi-horizon realized-vol percentile (5/10/21/63/126d) |
| `get_trade_excursions(trades)` | `journal.trade_excursions` | market (strategy-quality block) | MAE/MFE/profit-factor; exit-quality QA |
| `get_alpha_scoring(direction, predicted_magnitude, period_days, actual_return, confidence)` | `alpha_eval.alpha_score` + `insight_accuracy` | fundamentals | predicted-magnitude vs actual scoring (Insight/L7) |
| `get_regime_gate_read(ticker, catalyst_window)` | `regime.regime_gate_read` | market (mirrors the context line, callable) | knife-guard verdict the debators currently see only as a context string |

- Extend `get_risk_gate` (F5): accept + forward `daily_loss_pct`,
  `hwm_drawdown_pct`, `liquidity_verdict`, `capital_at_risk_pct`,
  `risk_cap_pct`, `sector_pct` to `govern()`, so the LLM risk-gate call
  reflects the full limits registry.
- **Acceptance:** hermetic tests per tool (synthetic inputs; commission
  reduces size; overrides liquidate on peak-drawdown breach; pre-trade cap
  blocks; cointegration/granger on planted pair; vol-cones known percentiles;
  MAE/MFE on a scripted trade path; alpha_score magnitude-error on a planted
  call). Existing `test_strategies_*` files extend; new tools land in
  `tests/test_analysis_tools.py`-style bind guards.

### Phase 3 — Enrich the shared decision context (no topology change)

`_compiled_decision_context` (trader/PM/debators) gains a computed **risk
factsheet** appended as labeled lines; everything already-computed elsewhere,
best-effort, "unavailable" on missing data:

1. **Limits registry:** `max_position_pct`, book cap, CVaR budget,
   drawdown limit, sector cap, `catalyst_hard_block_days` — the debators
   argue against explicit numbers, not vibes.
2. **Governor inputs:** `get_ledger_risk_state` output (daily loss, HWM
   drawdown, win-rate drift) + liquidity verdict lines.
3. **Volatility estimates:** latest close / Parkinson / Garman-Klass /
   EWMA / GARCH long-run vol (one line) + vol percentile from regime.
4. **Tail factsheet:** single-name VaR/CVaR (have), book CVaR/stress (have),
   plus top-1 component-VaR contributor from `get_tail_decomposition`.
5. **Credit + macro stress:** `credit_stress_level` band + scale, HY
   implied 1y default probability (when FRED key present).
6. **Event risk:** expected-move % at the next print + catalyst scale +
   `catalyst_hard_block_days` countdown.
7. **Fixed-risk size:** max units/shares at the computed stop
   (`risk_sizing.risk_money` with config `risk_*` + tranche weights) —
   the exact number the governor's budget implies.
8. **Tranche capital-at-risk:** `tranche_risk_read` `peak_deployed_pct` /
   `capital_at_risk_pct` (currently post-graph only; precompute the read)
   so the debators argue the scale-in risk before the PM sizes.

Injection points stay the same 5 prompts (trader.py, 3 risk debators,
portfolio_manager.py). Additionally inject a compact **risk factsheet
subset** into the Bull/Bear researcher prompts (F6): the LLM debate can only
challenge the analysts' numbers if it has measured numbers to challenge —
bear researcher gets VaR/stress/credit/liquidity lines; bull gets none
removed, only facts added. No prompt for RM/PМ gets longer than the
`max_output_tokens_deep` cap implies; keep each line ≤ 1 sentence.

- **Acceptance:** hermetic unit test that `_compiled_decision_context` emits
  every expected labeled line on a synthetic state (mock closes + memory) and
  degrades to "unavailable" on missing inputs; a string-length guard test
  keeps the factsheet under a fixed budget (e.g. 1.2k chars).

### Phase 4 — Give the 3 risk debators a real risk `ToolNode` (topology)

The strongest "wire calculations into the risk analysts" step — mirrors the
analyst loop pattern already in `graph/setup.py` + `conditional_logic.py`:

- New node registry entries in `graph/trading_graph.py::_create_tool_nodes`:
  `"risk"` (shared by the 3 debators) bound to a curated risk toolset:
  `get_risk_gate` (full F5 surface), `get_tail_risk`, `get_book_tail_risk`,
  `get_tail_decomposition`, `get_horizon_var`, `get_credit_spread_read`,
  `get_liquidity_risk`, `get_volatility_estimators`, `get_garch_volatility`,
  `get_mean_reversion_quality`, `get_tranche_plan`, `get_position_sizing`,
  `get_exit_check`, `get_trailing_exit`, `get_expected_move`,
  `get_premarket_review`, `get_ledger_risk_state`, `get_fixed_risk_size`,
  `get_exit_overrides`, `get_pre_trade_read` (Phase 2 tools).
- `graph/setup.py`: each debator node becomes an analyst-style loop
  (`debator -> tool node -> debator | clear`), with the existing
  `should_continue_risk_analysis` router extended by a
  `MAX_TOOL_ROUNDS`-style cap (reuse `finalize_messages` for the terminal
  turn; the cap routers pattern from the 2026-08-31 analyst-cap fix).
- `agents/risk_mgmt/*.py`: bind the tool list + prompt directives
  ("call the risk tools before asserting a risk number; cite the computed
  verdict; never invent a VaR/CVaR"). `independent_vote.py` stances run
  before the loop (unchanged); the computed `agreement_score` then reflects
  tools-cited stances.
- Parallel-mode (`analyst_concurrency>1`) is unaffected (risk debate stays
  after analysts); guard tests assert the new edges registered in both
  serial and parallel setups (mirror
  `test_production_setup_registers_analyst_cap_self_loop`).
- **Acceptance:** hermetic graph-wiring tests (edges complete, cap
  self-loop registered, tool-call rejection guarded); a full-stream mock-LLM
  run exercises ≥ 1 risk tool call per debator and asserts the decision keys
  survive.

### Phase 5 — Trader `ToolNode` (sizing/exits math)

The Trader proposes `entry_price` / `stop_loss` / `position_sizing` with no
numbers today. Bind a small sizing/exits node:

- New `"trader"` ToolNode: `get_position_sizing`, `get_risk_gate` (full
  surface), `get_fixed_risk_size`, `get_exit_check`, `get_exit_plan`,
  `get_trailing_exit`, `get_scaleout_plan`, `get_tranche_plan`,
  `get_trade_expectancy`, `get_trade_plan`, `get_swing_set`,
  `get_swing_exits` (market data via existing helpers).
- `graph/setup.py`: Trader becomes an analyst-style loop with a tool-round
  cap (same pattern as Phase 4); the structured `TraderProposal`
  (`agents/schemas.py`) is unchanged — the LLM just cites computed levels.
- **Acceptance:** wiring guard + mock-LLM smoke: proposal contains a
  stop/size traceable to a computed tool value (hermetic).

### Phase 6 — Cross-bind to the other virtual agents (F6)

| Agent | Add (bind + prompt line) | Rationale |
| --- | --- | --- |
| **News analyst** | `get_credit_spread_read(current_date)` (+ optionally `get_unit_root` for macro series) | every macro risk-off / credit claim becomes computed |
| **Fundamentals analyst** | `get_fixed_income_risk`, `get_alpha_scoring` | preferreds risk rows + magnitude-vs-actual scoring |
| **Research Manager** | `get_consensus`, `get_allocation` (already bound to fundamentals — bind to RM node) | plan cites computed agreement + cap-respecting alloc |
| **Portfolio Manager** (optional, later) | a `"pm"` ToolNode: `get_book_tail_risk`, `get_tail_risk`, `get_tail_decomposition`, `get_risk_parity_alloc`, `get_allocation`, `get_consensus`, `get_exit_overrides`, `get_ledger_risk_state` | the final decision grounds size / stop / consensus in book-level math |
| **Sentiment (social)** | none (pre-fetched blocks; no tool loop by design) | — |

- **Acceptance:** per-analyst bind guards + prompt-token budget check
  (`get_output_budget` still applies; keep each addition to one line).

### Phase 7 — Web mirror + docs + tests + commit (working agreement)

- trading_web: new Phase-2 tools added to the Value-Tools whitelist
  (`backend/capabilities.py`), job allowlists (`backend/main.py`,
  `backend/config.py`), and the SPA options/help text (`frontend/src/App.jsx`);
  README sync table.
- Docs: `docs/api_reference.md` §6.1/§6.4 (new tools, expanded `get_risk_gate`
  signature), `docs/developer/04-strategies.md`, `docs/developer/02-graph-workflow.md`
  (new risk/trader loops), `docs/AGENT_ONBOARDING.md` changelog + working-tree
  entry, `CHANGELOG.md` [Unreleased].
- Every new test carries `pytestmark = pytest.mark.timeout(...)`; run
  `py -3.12 -m ruff check` (E/W/F/I/B/UP/C4/SIM, line 100), then
  `py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider`.
- Commit + push per the onboarding agreement (Conventional Commits).

---

## 6. Constraints & conventions (enforced in every phase)

- **Always `py -3.12`**; windows heredoc rule (write tool for content);
- **No-fabrication:** every new tool returns exact numbers or explicit
  "unavailable"; `float | None`; min-obs guards (e.g. `cointegration`/`vif`
  < n obs → None).
- **Advisory-first:** new tools never gate; hard gating stays in the
  governor overlay + strict value-dip flags. Tool use in prompts is
  directive-style ("cite before asserting X"), never mandatory-tool.
- **Token budget:** quick tier caps at 8000 (`max_output_tokens_quick`);
  tool prompts stay one-line; the risk factsheet (Phase 3) is budget-capped
  (~1.2k chars) and the Phase-4/5 tool lists stay ≤ ~20 tools (the Market
  node at 73 is the ceiling, not the target).
- **Tool-round caps:** new loops reuse the analyst cap pattern
  (`MAX_TOOL_ROUNDS`=8, `finalize_messages` terminal turn); LangGraph edges
  registered for both serial + parallel modes; fall-through can never raise.
- **No secrets** in commits; `.env` untouched.

## 7. Non-goals

- No new data sources / vendors (all Phase-2 calculators run on data the
  repo already fetches).
- No new LangGraph nodes for experimentation beyond the risk-debator and
  Trader loops (Phase 4/5) — the PM loop (Phase 6) stays optional and later.
- No execution layer: `risk_checks`/`risk_manager` tools are advisory reads
  for the LLMs, not order submission.
- No re-litigating the overlay order (regime → orderflow → catalyst →
  contract → governor) or the `enable_*` default flags.

## 8. Verification checklist (end state)

1. Market analyst LLM sees 73 tools and the 18-gap test passes.
2. Phase-2 tools bound, hermetic-tested, web-mirrored.
3. Risk factsheet present in the 5 decision prompts under budget; researchers
   get the subset.
4. Risk debators + Trader loops run tool calls end-to-end in both concurrency
   modes (mock LLM), edges guard-tested, reports render every section.
5. ruff clean, full suite green (with timers), docs/README/CHANGELOG true,
   committed and pushed.