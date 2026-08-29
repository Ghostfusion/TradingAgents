# Deep Study: NautilusTrader → TradingAgents Enhancements

**Status:** design → implemented (all 3 phases: backtest harness, consistent risk sizing + pre-trade checks, statistics + config validation; web `run_backtest` wired) - see CHANGELOG [Unreleased] ### Added. Companion to the QuantLib/Lean + OpenBB deep-study implementations.
**Source study:** shallow clone of
[`nautechsystems/nautilus_trader`](https://github.com/nautechsystems/nautilus_trader)
read in this session (Rust `crates/` + Python `python/nautilus_trader`), mapped
onto the fork's deterministic `strategies/*`, the `dataflows/` vendor layer, the
paper/`pre_market` ledger, and `scripts/*` evaluation entry points.

Companion research-to-design docs: `docs/design_openbb_enhancements.md`
(typed envelopes, data surfaces) and `docs/design_quantlib_lean_enhancements.md`
(measurement/operational rigor). NautilusTrader's unique lesson is **execution
and evaluation rigor**: a real event-driven backtest engine with realistic fills
(slippage, fees, latency, order lifecycles), a formal pre-trade risk layer
(throttling, notional caps, fixed-risk position sizing), per-fill portfolio PnL
accounting with benchmark-relative statistics, and typed config validation.

This repo is **analysis-only** — it never routes live orders. So everything
here is adopted as a deterministic *advisory / evaluation* layer (backtest a
decision or ruleset, size risk consistently, report net-of-fee benchmark stats),
never as order emission. Nothing here is committed yet.

---

## 0. What NautilusTrader is (and is not)

- **Not** an LLM system. NautilusTrader is a Rust-core (pyo3) *event-driven
  algorithmic trading platform*: a live trading + backtesting engine over a
  message-bus/clock/cache kernel, with per-instrument order-matching venues,
  order lifecycles, a risk-limiting pipeline, portfolio PnL accounting, and a
  portfolio analyzer. Strategies are code (`Strategy` objects with
  `on_start`/`on_data`/`on_order_*` + managed indicators).
- Its transferable lessons for this fork are **execution-modeling and
  evaluation rigor**, not its actor/event architecture:
  1. **Backtest fills that know slippage + fees + latency + order state**,
     instead of filling at an assumed close.
  2. **A formal pre-trade risk layer** (rate throttles, notional caps) and an
     explicit **fixed-risk position sizer** that sizes by risk budget and
     tranche count - not an ad-hoc formula.
  3. **Per-fill realized/unrealized PnL + commission accounting** feeding a
     **benchmark-relative statistics** surface, not just a single max-drawdown.
  4. **Typed config with validation** that collects errors instead of silently
     coercing a bad value.

---

## 1. Execution-modeling lessons → a lightweight backtest harness

Verified against source:
`crates/backtest/src/{engine,config,exchange}.rs`, `crates/execution/src/{
matching_core.rs, matching_engine/mod.rs, models/{fill,fee}.rs, order_manager,
reconciliation}`, `crates/model/src/{enums.rs, position.rs}`,
`python/nautilus_trader/backtest/__init__.pyi`.

### B1. Bar-based matching engine (L1 fills from OHLCV) ⭐ quick win
- **Source:** `OrderMatchingEngine.process_bar` + `matching_core.rs` (price-time
  priority limit/stop books) + `SimulatedVenueConfig.bar_execution` (backtest
  pyi:295; engine.rs `process_bar`).
- **Gap:** TradingAgents has **no** replay/matching engine. `scripts/
  evaluate_config_gate.py` (G5 walk-forward + PBO) and `strategy_quality_report.py`
  evaluate *return series only*; there is no fill simulation, so a report's
  entry/stop/target/scale-in plan is never "executed" against history.
- **What:** a pure `strategies/backtest_engine.py` that replays daily OHLCV and
  fills limit/stop/market orders with price-time priority, producing fill
  events. `bar_execution`, `queue_position`, `use_market_order_acks` knobs.
- **Signature:**
  ```python
  # tradingagents/strategies/backtest_engine.py
  class OrderStatus: SUBMITTED, ACCEPTED, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED
  class Order: order_id, symbol, side, order_type, qty, price, trigger, status, filled_qty, avg_fill
  class OrderBook:  # limit/stop books, price-time priority
      submit(order) -> None  # stop triggers on high/low cross; limit rests/fills
  class MatchingEngine:
      replay(candles: list[dict], orders: list[Order]) -> list[Fill]  # close/bar_execution fill
  ```
- **Tests:** `tests/test_backtest_engine.py` - crucial: stop triggers on
  high/low, price-time priority, partial fills, cancel/reject transitions.

### B2. Fill, slippage + fee models (cost realism) ⭐ quick win
- **Source:** `execution/src/models/fill.rs` `DefaultFillModel`
  (prob_fill_on_limit, prob_slippage, is_slipped()); `fee.rs` `FixedFeeModel`,
  `MakerTakerFeeModel` (per-instrument `maker_fee`/`taker_fee` selected by
  `LiquiditySide::Maker/Taker`).
- **Gap:** TradingAgents has `liquidity_risk.volume_share_slippage` /
  `market_impact_slippage` (a single static cost fn) but no per-fill
  slippage/fee applied within a fill simulation; `evaluate_cost_bps` is a
  single global constant.
- **What:** a `FeeModel` (fixed-bps or maker/taker) + `FillModel` (optional
  probability of slippage adverse-tick on a fill) applied by the matching
  engine - so net-of-fee PnL is exact per fill, matching the repo's
  "analysis is a cost center" note (design_institutional §C1).
- **Signature:**
  ```python
  # tradingagents/strategies/backtest_models.py
  def fixed_fee(notional: float, fee_bps: float) -> float
  def maker_taker_fee(notional: float, maker_bps: float, taker_bps: float, liquidity: str) -> float
  def slip_price(price: float, tick: float, fill_model: str = "none") -> float  # +1 adverse tick
  ```
- **Wiring:** `scripts/backtest_strategy.py --report-dir ... --fees bps
  --slippage ticks` replays one report's plan (entry/stop/target/tranches from
  `5_portfolio/decision.md` + `full_states_log` JSON) over the vendor OHLCV and
  emits a `trades.csv` with gross/net PnL + MAE/MFE. Opt-in, advisory, never
  changes the graph.

### B3. Order lifecycle + position/PnL state machine
- **Source:** `OrderStatus` enum (15 states, `is_open/is_closed/is_active`);
  `Position.apply_fill` -> realized/unrealized PnL, per-currency commission;
  `OrderManager.submit/modify/cancel` + `execution/reconciliation` (pure
  `reconcile_order_report`/`reconcile_fill_report`).
- **Gap:** the `pre_market_ledger` records order-level decisions, not fills;
  there is no order-state machine or per-fill PnL.
- **What:** fold B1's `Order`/`Position` into a small state machine used by the
  backtest harness **and** by the paper ledger's "if executed" path. Brings the
  exact, citeable net PnL numbers the reports/ledgers ask for today as prose.
- **Note:** full L2/L3 book matching, live reconciliation against a broker, and
  the event/message-bus/clock kernel are **out of scope** (this repo is
  batch-analysis; see Non-goals).

---

## 2. Risk-layer lessons → consistent sizing + pre-trade checks

Verified against source: `crates/risk/src/engine/{mod,config}.rs`,
`crates/risk/src/sizing.rs`, `crates/portfolio/src/{portfolio,manager}.rs`,
`python/nautilus_trader/risk/__init__.pyi` (`FixedRiskSizer.calculate`).

### R1. Fixed-risk position sizer (commission-aware, tranche-aware) ⭐ quick win
- **Source:** `calculate_fixed_risk_position_size(entry, stop_loss, equity,
  risk, commission_rate, exchange_rate, hard_limit, unit_batch_size, units)`:
  `risk_points = |entry - stop|`; `position_size = risk_money / risk_points /
  price_increment / multiplier`, capped at `hard_limit`, split across `units`
  (tranches) down to `unit_batch_size`. Nautilus's `units` is exactly the
  tranche count.
- **Gap:** TradingAgents sizes via `size.py` (quarter-Kelly + risk/stop) and
  `value_dip.tranche_plan`/`tranche_risk_read` - the math exists but is
  scattered and ignores commission. The risk governor and the tranche fold
  should share ONE fixed-risk primitive so the governor's budget matches the
  sizer's output (a real correction today: `contract.py` min(Kelly, risk/stop)
  is not commission-aware).
- **Signature:**
  ```python
  # tradingagents/strategies/risk_sizing.py
  def risk_points(entry: float, stop: float) -> float
  def riskable_money(equity: float, risk_frac: float, commission_rate: float = 0.0) -> float
  def risk_money(fixed_risk_size, ...)  # fixed-risk position size (entry, stop, equity,
                                        # risk_frac, commission_rate, hard_limit, units)
  ```
  Wire `tranche_risk_read` + `position_contract` + `risk_governor` through it
  (same numbers the report already claims). Config: `risk_per_trade` if needed.
- **Tests:** `tests/test_strategies_risk_sizing.py` - commission reduces size;
  stop-distance drives size; hard_limit caps; units split sum-to-1; edge
  `stop == entry` -> 0.

### R2. Pre-trade throttling + notional cap (paper-execution gate)
- **Source:** `RiskEngineConfig` (`bypass`, `max_order_submit`/`max_order_modify`
  `RateLimit`, `max_notional_per_order`); the pre-trade pipeline runs
  validation -> notional/quantity/margin -> trading-state -> throttling. (The
  master checkout here hardcodes this pipeline rather than the classic
  `set_max_*`/`add_risk_check` API still described in the docs; the *concept*
  is the transferable part.)
- **Gap:** `risk_governor.govern` is a single-shot PASS/WARN/REJECT on one
  proposal; there is no submission-rate or per-instrument notional bound when
  the pre-market/paper layer *would* act.
- **What:** a small `pre_trade_checks(submissions, max_rate, max_notional)` that
  the backtest harness / pre-market execution path calls before each fill,
  throttling (rolling window count) and capping notional per symbol. Advisory,
  opt-in (`enable_paper_execution`), never wired into the graph.
- **Signature:**
  ```python
  # tradingagents/strategies/risk_checks.py
  class RateLimiter: allow(now) -> bool;   # rolling window
  def pre_trade_check(order, symbol_notional, max_notional, limiter) -> bool
  ```

---

## 3. Evaluation / statistics + config-validation lessons

### E1. Benchmark-relative + tail-rounded statistics ⭐ quick win
- **Source:** `crates/analysis/src/statistics/*` (34 files: `ValueAtRisk`,
  `ExpectedShortfall`, `OmegaRatio`, `CalmarRatio`, `UlcerIndex`,
  `UpCaptureRatio`/`DownCaptureRatio`, `TailRatio`, `Expectancy`,
  `ProfitFactor`, `Alpha`, `Beta`, `TreynorRatio`, `InformationRatio`,
  `TrackingError`, `MaxDrawdown`, `SharpeRatio`, `SortinoRatio`, ...) and
  `analyzer.rs` (`calculate_statistics`, `set_portfolio_returns_from_snapshots`,
  `get_performance_stats_returns_vs_benchmark`, `record_trade`).
- **Gap vs our repo:** `evaluate.py` already gained many of these from the
  QuantLib pass (sharpe, sortino, rolling_beta, alpha, prob_sharpe, VaR/CVaR,
  omega, underwater). The genuinely-new, cheap ones TradingAgents lacks:
  **Calmar ratio, Ulcer index, up/down capture ratio, tail ratio, and
  expectancy-from-wins/losses**, plus a **benchmark-relative** surface
  (tracking error / information ratio vs the regional benchmark map, which the
  memory log already resolves for alpha).
- **Signature** (add to `strategies/evaluate.py`, all `float | None`,
  no-fabrication, `None` < `min_n`):
  ```python
  def calmar_ratio(returns, ppy=252) -> float|None      # CAGR / max_drawdown
  def ulcer_index(returns) -> float|None                # sqrt(mean(drawdown^2))
  def capture_ratio(returns, benchmark, up: bool) -> float|None
  def tail_ratio(returns) -> float|None                 # avg_win / avg_loss
  def expectancy_stats(wins: list, losses: list) -> dict|None  # {profit_factor, expectancy, win_rate}
  ```
- **Wiring:** `strategy_quality_report.py` + `orderflow_evaluate.py` surface the
  new rows; the PM's benchmark-relative context stays advisory. Tests:
  `tests/test_strategies_evaluate.py` (extend; hermetic).

### E2. Config validation that collects errors ⭐ quick win
- **Source:** `RiskEngineConfig.validate()` using a `ConfigErrorCollector`
  (checks every field, returns `ConfigError::Multiple` with all violations);
  builders that `build()` -> `validate()`.
- **Gap:** `tradingagents/default_config.py::_coerce` coerces `TRADINGAGENTS_*`
  to the default's type but never range-checks; a bad value (negative window,
  fraction > 1, weights not summing ~0) silently mis-behaves later.
- **What:** a `validate_config(config)` in `default_config.py` run at startup
  (and at env-override application) that collects violations: fractions in
  [0,1] (`kelly_fraction`, `target_vol`, scales), `catalyst_*`>0,
  `tranche_weights` sum≈1.0, `risk_*` in (0,1), return a single summary string
  (logged, never raised - advisory). Tests: `tests/test_default_config.py`.
- **Signature:**
  ```python
  def validate_config(config: dict) -> list[str]   # human-readable violations
  ```

---

## 4. Recommended phases (highest ROI first, all deterministic/advisory)

### Phase 1 — Backtest harness (fills + costs) — a NEW capability
- B1 `strategies/backtest_engine.py` (order lifecycle + bar matching) + B2
  `backtest_models.py` (fee/slippage/fill) + B3 position PnL; plus
  `scripts/backtest_strategy.py` that replays a report's plan (entry/stop/
  targets/tranches from `full_states_log`/`decision.md`) over vendor OHLCV →
  `trades.csv` + net-of-fee PnL + MAE/MFE. This makes
  `evaluate_config_gate`/`strategy_quality_report` and the paper ledger
  "execute" plans instead of assuming fills. No graph change.
- Tests: `test_backtest_engine.py`, `test_backtest_models.py` (hermetic, timeout).

### Phase 2 — Consistent risk sizing + pre-trade checks
- R1 `strategies/risk_sizing.py` (fixed-risk, commission-aware, tranche-aware);
  rewire `tranche_risk_read` + `position_contract` + `risk_governor` to it.
- R2 `strategies/risk_checks.py` (RateLimiter + notional cap) used by the
  paper-execution path (`enable_paper_execution`, default OFF).
- Tests: `test_strategies_risk_sizing.py`, `test_strategies_risk_checks.py`.

### Phase 3 — Statistics + config validation
- E1 `evaluate.py` additions (Calmar, Ulcer, capture, tail_ratio, expectancy)
  + benchmark-relative surface in `strategy_quality_report.py`.
- E2 `validate_config()` range checks in `default_config.py`.
- Tests: extend `test_strategies_evaluate.py`, `test_default_config.py`.

---

## 5. Non-goals / risks

- **No live order routing / broker adapters / message-bus kernel.** The
  event/actor architecture is the wrong shape for a batch LLM pipeline; the
  kernel, live reconciliation, L2/L3 book matching, and adapter connectors are
  explicitly out of scope. We adopt only the deterministic evaluation/sizing
  pieces.
- **No alpha claims.** Every item is a fill-modelled PnL / risk number / stat
  / config guard, all advisory and never gating the LLM decision unless opt-in.
- **No-fabrication preserved.** All `float | None`, explicit "unavailable";
  a backtest with insufficient bars degrades, never invents a fill.
- **Backtest is a paper/eval tool, not a promise of live results.** Slippage/
  latency on daily bars is a coarse approximation of Nautilus's L2 matching;
  state that honestly (daily-bar model, no queue-position realism).
- **Scope control** - B1/B2/E1/E2 are quick wins that exercise existing seams
  (`style: no new vendors, no new schema`); the risk sizer rewire (R1) is the
  only behavior-touching item and stays config-compatible (same outputs, just
  commission-aware + centralized).

---

## 6. Quick-wins verdict

1. **Fixed-risk position sizer (R1)** - commission-aware, tranche-aware single
   primitive unifying `size.py` / `tranche_risk_read` / `position_contract` /
   `risk_governor`; a pure math function + config wiring, high consistency
   value, low effort. Highest ROI.
2. **Statistics (E1)** - Calmar / Ulcer / up-down-capture / tail-ratio /
   expectancy + benchmark-relative surface; pure formulas on existing return
   series, no data deps, fills the last risk-report gaps.
3. **Config validation (E2)** - `validate_config()` range checks catch
   mis-coerced `TRADINGAGENTS_*` before they silently skew a run; tiny.
4. **Backtest harness (B1/B2/B3)** - a *new* capability (replay a plan with
   fills/fees and net PnL) that upgrades `evaluate_config_gate` /
   `strategy_quality_report` and the paper ledger from "assume fills" to
   "executed with costs"; medium effort, unique value, strictly advisory.
