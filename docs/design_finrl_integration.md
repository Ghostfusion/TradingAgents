# Design: Incorporating FinRL into TradingAgents

**Status:** design only — no code changed.
**Date:** 2026-09-02.
**Source study:** `AI4Finance-Foundation/FinRL` (master; classic FinRL),
`FinRL-Trading`/`FinRL-X` (master; next-gen), FinRL-Meta docs, the canonical
papers, and web searches — full list in §1. The FinRL study is merged with the
existing `docs/design_qlib_integration.md` (Qlib) into ONE roadmap so an
implementer follows a single source of truth; §4 marks which modules each
teacher owns.
**Object:** absorb FinRL's transferable lessons into this fork without
violating its contracts: **compute-as-tools, no-fabrication, advisory-first,
deterministic hard gates, walk-forward/PBO before any gate ships, analysis-only
(no execution layer).**

Companion docs: `docs/design_qlib_integration.md` (the merged roadmap's Qlib
half), `docs/design_market_refresh_fastpath.md` (T0/T1/T2 — the same shape as
FinRL-X's two-layer regime), `docs/design_quantlib_lean_enhancements.md`,
`docs/api_reference.md` §5/§6, `docs/developer/` set.

---

## 0. What FinRL is (one paragraph)

FinRL is AI4Finance's **deep-reinforcement-learning trading framework** — the
first open-source library of its kind — organized as a three-layer stack
(**market environments → DRL agents → financial applications**) around a
**train-test-trade** pipeline: download/clean/feature-engineer data (DataOps),
train DRL agents (A2C/DDPG/PPO/SAC/TD3 via Stable-Baselines3 / ElegantRL /
RLlib), backtest with transaction costs + turbulence risk gating, and paper/
live trade. The ecosystem has three generations:

| Generation | Positioning | What it contributes |
| --- | --- | --- |
| **FinRL** (2020) | Classic end-to-end educational/research framework | three-layer architecture; gym market envs; reward shaping; turbulence gate; ensemble rolling re-train |
| **FinRL-Meta** (2022) | Market environments + benchmarks | DataOps auto pipeline; hundreds of gym envs; baseline strategies (passive/MVO/equal-weight/mean-variance); cloud competition |
| **FinRL-X / FinRL-Trading** (2026) | Next-gen production | **weight-centric contract** `w_t = R(T(A(S(𝒳≤t))))` (selection→allocation→timing→risk overlay); ML stock selection (per-sector-bucket models) + DRL timing; two-layer market regime (slow gate + fast risk-off overlay) with persistence + stop-loss/cooldown policy; `bt` backtest; Alpaca multi-account execution |

Its worldview: **learn a policy (or score) over a market environment, output a
portfolio decision, evaluate on risk-adjusted metrics vs baselines** — evaluated
end-to-end in a trading loop, not on win-rate.

The fork's worldview is complementary: **LLM agent deliberation over computed,
deterministic numbers**, single-name-focused, live-vendor-fed, committees +
deterministic overlays. The two share DNA already: `pipeline.py` (screen→rank→
top-N) is the "ML selection" step, `_apply_strategy_overlays` is the "timing +
risk overlay" step, `book_risk.portfolio_cvar` is the basket tail read,
`evaluate_config_gate.py` is walk-forward + PBO, `pre_market.py`
CONFIRM/REVISE/REJECT is a risk overlay, and the T0/T1/T2 fast-path design is a
two-layer cadence.

---

## 1. Source study (verified this session)

**Repos (read):**
- `AI4Finance-Foundation/FinRL` (master): `finrl/meta/env_stock_trading/
  env_stocktrading.py` (+currency +stoploss +np), `agents/stablebaselines3/
  models.py` (DRLAgent + DRLEnsembleAgent), `meta/data_processor.py`,
  `meta/preprocessor/preprocessors.py` (FeatureEngineer, turbulence),
    `applications/stock_trading/ensemble_stock_trading.py`, `config.py`,
  `train.py`/`trade.py` pattern, `plot.py` (pyfolio tear sheet), `meta/paper_trading/
  alpaca.py`
- `AI4Finance-Foundation/FinRL-Trading` (master): `src/strategies/
  base_strategy.py` (StrategyResult), `adaptive_rotation/{adaptive_rotation_engine,
  market_regime, risk_manager, group_strength, intra_group_ranking}.py`,
  `data/data_processor.py`, `trading/trade_executor.py`, `ML_STOCK_SELECTION.md`
  (y_return PIT discipline), `weight_allocation_guide.md`
- FinRL-Meta docs (`docs/source/finrl_meta/`: Data_layer.rst, Environment_layer.rst,
  Benchmark.rst, overview.rst, background.rst)

**Papers (abstract-verified):** FinRL (arXiv 2011.09607), FinRL-Meta
(arXiv 2211.03107). FinRL-X paper (arXiv 2603.21330) and FinRL-DeepSeek
(Feb 2025, Benhenda — LLM-infused risk-sensitive RL) are cited per README/web;
their claims are marked `[claimed, not source-verified]` where relevant.

**Web searches (5, dated):** FinRL architecture/ecosystem; FinRL papers;
FinRL-DeepSeek; DRL-trading critiques (backtest overfitting, look-ahead bias,
reproducibility); Qlib-vs-FinRL / LLM+RL hybrid lessons.

---

## 2. The two teachers, one project

| | **Qlib** (existing design) | **FinRL** (this design) |
| --- | --- | --- |
| Paradigm | research→production **factor/ML systematic quant** | **RL-driven trading** (learn, don't optimize) |
| Core interface | expression engine → `pred_score` series → IC/ICIR-evaluated | environment → **weight vector** → risk-adjusted backtest |
| Best-in-class | PIT data + factor libraries + workflow/recorder + Topk-Drop | risk-shaping reward, turbulence regime gate, rolling ensemble re-train + validation selection, two-layer regime + stop/cooldown, baselines |
| What stays out (both) | RL/HFT/execution | RL runtime = **non-goal** for the fork (deterministic core); execution = non-goal (analysis-only) |

Both independently validate the same fork-contract truths: **point-in-time
discipline**, **walk-forward validation**, **advisory-first** (ML/RL = research
filters, never executors), and **cost-realistic evaluation**. §4 turns that
convergence into one merged module list.

---

## 3. FinRL pillars → fork gaps → transferable lessons

| FinRL pillar | What it does | Fork gap today | Transferable lesson (adoptable) |
| --- | --- | --- | --- |
| **1. Market environments + DataOps** (FinRL-Meta) | automatic data pipeline → hundreds of reusable gym environments; per-frequency NaN policy (low-freq: drop rows reflecting suspension; high-freq: ffill close + volume 0) | vendor chains exist per-category; no named, parameterized market context registry; no explicit per-frequency missing-data convention | A **market-environment registry** — named contexts (`US-megacap-tech`, `HK-large-cap`, `crypto`, …) = {universe, asset_type, exchange, benchmark_ticker, data_vendors preset, session flags} that the runfile/web jobs reference; document the low-vs-high-frequency fill policy mapping to the existing look-ahead guard |
| **2. Train-test-trade separation** | the agent never sees backtest/trade data at train time (period split); uniform PIT membership filter at train AND inference | backtests pin `curr_date` per run; no declared train/test/trade **stage windows** in one run definition | runfile gains **stage windows** (`train`, `test`, `trade` date ranges) + the PIT registry (shared with Qlib §3.5) — one definition, no leakage between stages |
| **3. Turbulence risk gate** | Mahalanobis-style **market-stress scalar** from a rolling cross-section covariance; positions liquidated above a threshold | single-name CVaR + basket CVaR exist; no cross-sectional market-stress scalar with a hard risk-off semantic | `strategies/market_stress.py::turbulence_index(returns_panel)` over the basket/benchmark panel (robust pinv, min-breadth guard → None); advisory fold + context line (see §6.1) |
| **4. Two-layer market regime + persistence** (FinRL-X) | Slow regime (weekly: SPX vs 26w MA + 13w drawdown + VIX robust z) sets group caps / cash floor and **must persist N weeks to flip**; Fast risk-off overlay (daily shock) tightens instantly | `regime.py` is single-speed, no persistence validation, no fast overlay | `market_stress.slow_regime` + `fast_risk_off` with persistence (state must survive N periods to switch) — this IS the T0-gate + ESCALATE shape of the fast-path design; fold as advisory scale, never a gate (repo rule) |
| **5. Risk-shaped reward** (env_stocktrading_stoploss) | reward = total-asset change − cash penalty − stop-loss penalty − low-profit penalty + realized-win bonus; profit/loss-ratio constraint built in | PM contract is min(Kelly, risk/stop) × folds — return-constrained but no **explicit cash-floor / stop-adherence term** in the objective the agents optimize | Guidance + a computed line: a **risk-adjusted objective directive** in the plan card / PM prompt (drawdown-from-HWM + cash-floor + stop-adherence read from the ledger — never "maximize total return" naked); reuse `risk_hwm_soft/hard_pct` + `risk_daily_loss_budget_pct` |
| **6. Stop-loss + cooldown policy** (FinRL-X) | per-symbol `PositionState` (entry/peak tracking); absolute stop from entry + trailing stop from peak, **cooldown weeks after a stop** (no re-entry) | `exits.trailing_stop_exit` / `max_giveback_exit` + `risk_manager` exist advisory; **no cooldown registry, no persisted per-symbol stop state** | `strategies/stop_policy.py`: PositionState + absolute/trailing check + `activate_cooldown`; extend `get_ledger_risk_state` / `get_exit_overrides` with cooldown rows; exposed in the plan card + action report (see §6.2) |
| **7. Weight-centric contract** (FinRL-X) | `w_t = R(T(A(S(𝒳≤t))))` — every module (equal-weight, MVO, min-var, DRL allocator, KAMA timing, risk overlay) returns ONE weight vector; backtest and live consume the same contract | `portfolio.py` alloc returns dicts via `get_allocation`; `scripts/value_screener.py --alloc` (→ `portfolio.allocation_block`) consumes one shape; no universal, deployable **weight-vector result** across alloc strategies | `strategies/portfolio_contract.py`: a `PlanWeights(strategy, weights, metadata)`-typed result + uniform interface over the existing alloc modules (value-ratio, risk-parity, min-variance, correlation-penalized, topk-drop, enhanced-index) consumed by `scripts/value_screener.py --alloc` + `get_allocation` + `action_report` (see §6.3) |
| **8. Baseline-relative evaluation** (FinRL-Meta Benchmark) | every result vs passive buy-hold / equal-weight / mean-variance / min-variance baselines; metrics = cum return, annualized return/vol, Sharpe, MaxDD | `evaluate.py` + `strategy_quality_report` report strategy rows; baselines exist only as alpha-vs-benchmark in memory | `strategies/benchmark_surface.py`: always render strategy **vs** passive/equal-weight/MVO baseline rows in `strategy_quality_report` + `evaluate_config_gate` (see §6.4) — a raw single curve is never the deliverable |
| **9. Rolling ensemble re-train + OOS validation selection** (classic FinRL) | every rebalance window: train 5 algos on expanding data, pick the best by **validation Sharpe**, trade the forward window | the advisory factor-model design (Qlib §3.6) trains one model; no candidate-zoo + validation-selection policy | the Phase-4 factor model runs on a **FinRL ensemble cadence**: re-train at rebalance windows, evaluate a candidate zoo, select by OOS validation Sharpe (deflated/PBO-gated) — never in-sample argmax (see §6.6) |
| **10. Multi-timeframe data** | 1-min bars for intraday/paper-trading examples | `alpaca.get_intraday`/`get_bars` (1m) exist, screener-only | **Note only** — no execution need (matches Qlib pillar 9 non-goal); the intraday data already lands in `market_session` tools |
| **11. LLM+RL hybrid guidance** (web synthesis; FinRL-DeepSeek; QlibRL) | LLM extracts risk/text priors → RL policy + reward shaping; best practice = **hybridization** (LLM = reasoning/signal, RL = constrained allocation, deterministic rules last). Qlib ships its own RL toolkit (QlibRL, 2022, order-execution PPO/OPDS/TWAP) and warns that training/backtest simulators differ | n/a — the fork is already the "policy wrapper over computed numbers with hard deterministic gates" | **Validation, not adoption**: the fork's architecture is the recommended hybrid shape. Any future learned allocator = advisory input behind the existing overlays; never the executor. Do NOT add an RL runtime — QlibRL's simulator-gap warning (design_qlib §1a-21) reinforces why the fork's paper fills must state their model |

---

## 4. Delta vs the Qlib design (what changes in the merged roadmap)

| Qlib-design module (design_qlib_integration.md) | FinRL lesson | Merge outcome | Owner |
| --- | --- | --- | --- |
| `factor_expressions` + `get_factor_profile` | FinRL's indicators (MACD/RSI/ADX/CCI stockstats) + its **52-factor fundamental list** are a feature-pool reference | **Keep as-is**; cite FinRL's factor list as the Phase-4 model's feature pool (plus Alpha158 subset) | Qlib (+FinRL feature list as reference) |
| `signal_analysis` (rank IC/ICIR/quantile) | FinRL-Meta benchmarks use Sharpe/vol/MaxDD, not IC | **Keep as-is**; FinRL's metric set moves into `benchmark_surface` (§6.4) — two complementary surfaces | Qlib (IC) + FinRL (baseline-relative stats) |
| `portfolio_strategy` (Topk-Drop + enhanced-index) | FinRL-X weight-centric contract + equal-weight/MVO/min-var zoo | **Wrap in `portfolio_contract`** (§6.3): Topk-Drop keeps Qlib selection math; enhanced-index is the Qlib convex program (turnover cap, benchmark-deviation, force-hold/sell masks, fallback — design_qlib §3.3); equal-weight/MVO/min-var join as contract-conforming modules; all consumed by `scripts/value_screener.py --alloc` (via `portfolio.allocation_block`) | shared (contract = FinRL, math = Qlib) |
| `runfile` + experiment ledger | FinRL-X Pydantic settings + YAML strategy configs + walk-forward engine; FinRL-Meta DataOps | **Extend**: runfile gains `stage` (train/test/trade date windows) + `environment` (named market context from `environment_registry`); ledger unchanged | shared |
| `pit_registry` | FinRL-X `ML_STOCK_SELECTION.md` is a textbook PIT discipline (datadate→tradedate mapping, uniform SP500-membership filter at train AND inference, y_return verification) | **Reinforced** — the doc's worked example becomes the PIT-registry acceptance test corpus | shared |
| `factor_model_train` (LightGBM advisory) | FinRL ensemble: candidate zoo + OOS validation-Sharpe selection, rolling re-train | **Extend**: ensemble cadence + selection policy (§6.6) | shared |
| fast-path alignment (T0/T1/T2) | FinRL-X two-layer regime (slow + fast overlay + persistence) is the same shape | **Aligned formally** (§6.1) — the fast path's T0 gate = regime persistence check; ESCALATE = fast risk-off | shared |
| RL framework | FinRL is the RL teacher | **Non-goal unchanged**; note the LLM+RL hybrid synthesis in §9 | — |

Nothing from the Qlib design is dropped; FinRL **adds** five net-new modules:
`market_stress` (turbulence + two-layer regime + persistence), `stop_policy`
(cooldown), `portfolio_contract` (weight-vector contract), `benchmark_surface`,
and the ensemble cadence on the factor model. The Qlib design itself gained
four lessons after its direct-repo deep study (`docs/design_qlib_integration.md`
§1a/§3.7-§3.10): the **RD-Agent factor-proposal loop** (LLM proposes
candidates, deterministic math + PBO gate decides), the **learn/infer
normalization split**, the **market-tradability** backtest model, and
recorder-style ledger rows — ownership stays shared as in the table above
(RL/non-goal rows unchanged).

---

## 5. Design principles (bound by the repo contract)

1. **Advisory-first, always.** Every FinRL-sourced artifact is a deterministic
   calculator or an advisory signal injected into the decision agents — hard
   gates remain the existing overlay pipeline (regime → catalyst → contract →
   governor).
2. **Deterministic core.** All new calculators pure `float | None`,
   explicit `unavailable`, min-obs guards (no-fabrication).
3. **ML/RL is a research filter, not an executor.** Any candidate model must
   pass walk-forward + PBO/DSR + cost robustness before its score is even
   advisory to the LLM (existing `evaluate_config_gate` / `enable_threshold_gate`
   policy); selection uses OOS-validation metrics, never in-sample argmax.
4. **Point-in-time discipline.** Everything the LLM sees carries an as-of
   timestamp; the PIT registry (Qlib §3.5) is the single store; FinRL's
   datadate→tradedate pattern is its acceptance corpus.
5. **Everything is a tool.** New calculators become `@tool`s bound to analysts
   (working-agreement §0), re-exported in `agent_utils`, graph ToolNode +
   prompt, web-mirrored.
6. **Risk-adjusted objective (new, from FinRL).** The agents' objective is
   never naked return: the plan card/PM prompt carry drawdown-from-HWM +
   cash-floor + stop-adherence rows from the ledger (`risk_hwm_*`,
   `risk_daily_loss_budget_pct`), and the contract bounds size as today.
7. **Baseline-relative (new, from FinRL).** Evaluation reports strategy vs
   passive/equal-weight/MVO baselines — a raw single curve is not a result.
8. **No execution layer** (analysis-only), **no RL runtime** in the default
   path.

---

## 6. Proposed modules (pure, hermetic-tested)

### 6.1 `strategies/market_stress.py` — turbulence + two-layer regime (FinRL 3-4)
- `turbulence_index(returns_panel) -> pd.Series` — rolling-window Mahalanobis
  distance of the basket's return panel vs its history (`(x_t − μ)ᵀ Σ⁻¹ (x_t − μ)`;
  robust `pinv`, ≥2-name aligned breadth, else None) — FinRL `calculate_turbulence`
  with the basket the repo already fetches for `portfolio_cvar`.
- `slow_regime(spx_close, vix, as_of, trend_ma_weeks=26, drawdown_weeks=13,
  dd_threshold=0.10, vix_z_threshold=3.0, persistence_weeks=2) -> {state,
  signals, constraints, is_persistent}` — RISK_ON/NEUTRAL/RISK_OFF from
  (trend, drawdown, VIX robust z) with **persistence validation** (state must
  survive `persistence_weeks` before flipping) — the T0-gate analog.
- `fast_risk_off(daily_returns, shock_days=3, vol_shock_mult=3.0) -> {active,
  days_remaining, triggers}` — daily emergency overlay (price shock + vol
  shock) that tightens immediately — the ESCALATE analog.
- Advisory fold: `fold_market_stress_into_overlay` (advisory de-risk scale + verdict;
  NEVER a hard REJECT beyond the existing governor) — config `enable_market_stress`
  (default False), `market_stress_*` keys.
- Tool `get_market_stress_read(ticker)` (market analyst + 3 risk debators),
  re-export in `agent_utils`, market ToolNode + prompt; `_compiled_decision_
  context` gains a one-line stress read; report `Iva` surfaces it.

### 6.2 `strategies/stop_policy.py` — position state + cooldown (FinRL 6)
- `PositionState` (entry/peak/date tracking per symbol), `check_absolute_stop`,
  `check_trailing_stop`, `check_position_stops` (absolute takes priority),
  `activate_cooldown(symbol, trigger_date, cooldown_weeks)`, `cooldown_active`.
- Wire: `get_exit_overrides` / `get_ledger_risk_state` gain cooldown rows
  (persisted via the memory log + paper ledger); the plan card and
  `action_report` render "cooldown until <date>" for stopped names.
- Config: `stop_cooldown_weeks` (+ `TRADINGAGENTS_STOP_COOLDOWN_WEEKS`, default 4);
  reuse `trailing_stop_pct` / `risk_manager_drawdown_pct`.
- Advisory only; the LLM sees the state, never tightens it.

### 6.3 `strategies/portfolio_contract.py` — weight-vector contract (FinRL 7)
- `PlanWeights(strategy: str, weights: dict[str, float] | pd.DataFrame,
  metadata: dict)`-typed result (StrategyResult pattern, no-fabrication —
  weights sum ≤ 1.0 with cash remainder documented).
- Uniform interface over the alloc modules: value-ratio (existing),
  risk-parity/min-variance (existing), correlation-penalized (existing),
  **Topk-Drop + enhanced-index** (Qlib §3.3 math), **equal-weight + MVO/
  min-variance benchmarks** (FinRL — the same modules double as baselines).
- Consumed by `scripts/value_screener.py --alloc` (via
  `portfolio.allocation_block` — the screener flag; the earlier
  "`pipeline.py --alloc`" reference was a doc slip, `pipeline.py` has no
  alloc machinery), `get_allocation` (fundamentals), and `action_report`;
  a new PM tool `get_allocation_plan(score_by_name, caps)` — advisory.
- Config: `allocation_strategy` enum (value-ratio | risk-parity | min-variance |
  equal-weight | topk-drop | enhanced-index), default value-ratio — behavior
  unchanged.

### 6.4 `strategies/benchmark_surface.py` — baseline-relative stats (FinRL 8)
- `benchmark_rows(buy_hold_close, equal_weight_rets, mvo_rets, strategy_rets)
  -> {cum, ann_ret, ann_vol, sharpe, maxdd, calmar}` rows for each line.
  Mean-variance/min-variance weights from `portfolio_optimizer.min_variance_weights`
  (existing).
- Wire: `strategy_quality_report.py` always renders strategy **vs** baselines
  (a raw single curve is never the deliverable); `evaluate_config_gate`
  reports PBO/DSR baseline-relative.

### 6.5 runfile stages + market-environment registry (shared; extends Qlib §3.4)
- `scripts/runfile.py` YAML gains sections: `stage` (train/test/trade date
  windows — FinRL 2), `environment` (named context, below), `strategy` (scan/
  alloc/overlay flags), `agent` (analysts/depth/models). Expands 1:1 to
  existing flags — no new execution path.
- `dataflows/environment_registry.py`: named market contexts (e.g.
  `US-megacap-tech`, `US-basket`, `HK-large-cap`, `crypto`) = {universe |
  positions, asset_type, exchange, benchmark_ticker, data_vendors preset,
  session flags}; referenced by runfile + web Jobs presets (FinRL 1).

### 6.6 Advisory factor model — ensemble cadence (shared; extends Qlib §3.6)
- Extend `scripts/factor_model_train.py`: a **candidate zoo** (LightGBM
  variants over Alpha158 + FinRL-52 features), re-trained at rebalance windows;
  **selection by OOS validation Sharpe (deflated/PBO-gated)**, never
  in-sample argmax (FinRL 9). Every candidate is reported **vs simple
  baselines (equal-weight / value-ratio / momentum) on the same IC + backtest
  surface** — the Qlib model-zoo benchmark convention (design_qlib §1a-20),
  which `benchmark_surface` (§6.4) + `signal_analysis` (Qlib §3.2) combine to
  provide.
- Gate unchanged: score reaches the LLM only after walk-forward+PBO passes;
  `enable_factor_model=False` default. (FinRL-DeepSeek's LLM-infused risk
  shaping stays out: LLM signals already flow via the news/sentiment tools.)

---

## 7. Where each piece lands (seams)

| Module | Seam | Config / flag | Web surface |
| --- | --- | --- | --- |
| `market_stress` | market tool `get_market_stress_read` + risk-debator bind + context line + overlay fold | `enable_market_stress` (False) + `market_stress_*` | Value Tools + Pre-Market |
| `stop_policy` | `get_exit_overrides` / `get_ledger_risk_state` + plan card + action report | `stop_cooldown_weeks` (4) | Scripts screen row |
| `portfolio_contract` | `scripts/value_screener.py --alloc` (→ `portfolio.allocation_block`) + `get_allocation` + `get_allocation_plan` (PM) + `action_report` | `allocation_strategy` (value-ratio default) | Pipeline alloc strategy |
| `benchmark_surface` | `strategy_quality_report.py` + `evaluate_config_gate` | always-on pure calc | Scripts screen |
| runfile stages + env registry | `batch.py`/`pipeline.py` flags front-end | `--runfile <yaml>`; registry = named presets | Jobs screen preset |
| factor-model ensemble cadence | `factor_model_train.py` (advisory rank only) | `enable_factor_model` (False) | none (research) |

Every new tool: hermetic tests with `pytest-timeout`, `agent_utils.__all__`
re-export, ToolNode + analyst prompt binding, `.env.example` mirror, docs.

---

## 8. Phased rollout (merged Qlib + FinRL)

- **Phase 1 — pure calculators** (`market_stress` turbulence + two-layer
  regime + persistence; `stop_policy` cooldown; `benchmark_surface`; wrap
  `portfolio_contract`). Tests hermetic; docs true; web Value Tools mirror.
- **Phase 2 — runfile + env registry** (stage windows, `--runfile`,
  `environment_registry`).
- **Phase 3 — PIT registry** (shared; as-of masking; consumed by pre-market
  reviewer + fast path + backtests; FinRL's datadate→tradedate as acceptance).
- **Phase 4 — advisory factor model + ensemble cadence** (candidate zoo,
  OOS-validation selection, PBO gate; default OFF).
- **Phase 5 — fast-path alignment** (T0/T1/T2 formalized with the two-layer
  regime + stop policy + pit-registry; still advisory).

Each phase: pure functions + hermetic tests + `.env.example` + docs
(api_reference, developer/04, AGENT_ONBOARDING) + README/CHANGELOG +
trading_web mirror + commit/push (working agreement). No phase rewires the
graph topology or the overlay order.

---

## 9. Non-goals / risks (honest)

- **No RL runtime, no execution layer.** The fork is deterministic-first,
  analysis-only; DRL and broker integration are non-goals (Qlib §6 echoes
  this — Qlib itself shipped an RL toolkit in 2022, used for order execution,
  and the fork still declines it). The LLM+RL hybrid synthesis (web): LLM =
  reasoning/signal, constrained alloc = advisory, deterministic rules last —
  the fork already has that shape; any learned module plugs in behind the
  overlays. **Simulator-gap honesty (QlibRL lesson):** every paper/backtest
  fill states its model (deal price, slippage, limit/participation gates —
  the Qlib `Exchange` lessons, design_qlib §1a-13/§3.8) so training-vs-backtest
  and paper-vs-book differences are labeled, never silent.
- **DRL trading critiques apply to anything learned** (web): backtest
  overfitting, look-ahead bias (FinRL-X's own `ML_STOCK_SELECTION.md` documents
  how easily y_return leaks), seed/hyperparameter sensitivity, non-stationarity.
  Mitigation is the existing gate order: walk-forward, PBO/DSR, parameter
  stability, cost robustness, then promotion — and the PIT registry.
- **Turbulence estimation noise.** Mahalanobis over a short panel is unstable;
  min-breadth guard + robust pinv + advisory-only fold (never a hard gate).
- **Persistence lag.** A regime that must persist N weeks flips slowly — by
  design (avoids whipsaw), but the fast risk-off overlay covers the emergency
  case; both stay advisory.
- **Cooldown cost.** A stop-loss cooldown can miss a genuine re-entry; the
  cooldown is advisory rows (the LLM sees them), configurable weeks, and only
  applied if a plan references it — never silently.
- **Scope creep.** Each pillar maps to ONE module; nothing rewires the graph
  topology or the overlay order. FinRL's own legacy (coupled monolith,
  hand-rolled loops, `config.py` globals) is an anti-pattern — adopted
  selectively as pure functions only.

## 10. Quick-wins verdict

1. **`market_stress` turbulence + two-layer regime** — a deterministic
   market-wide tail scalar + persistence-gated regime the risk debators can
   cite; zero new vendors (basket panel already fetched).
2. **`stop_policy` cooldown** — fills the one gap in the exit suite (no
   re-entry gate) with pure state math + ledger rows.
3. **`benchmark_surface`** — baselines make every eval report honest; pure
   formulas on existing series.
4. **`portfolio_contract` weight-vector interface** over existing alloc
   modules (incl. the Qlib Topk-Drop/enhanced-index math) — the FinRL-X
   lesson with no new algorithm code.
5. **runfile stages + env registry** — reproducibility/diff without touching
   the execution path (FinRL-X's Pydantic/YAML front-end).
6. **Factor-model ensemble cadence** — last, gated, advisory-only (the
   deterministic-core boundary).

## 11. Acceptance (evidence checklist)

1. `turbulence_index` recovers a planted covariance-shift episode and reports
   None under <2 aligned names; `slow_regime` refuses to flip before
   `persistence_weeks`; `fast_risk_off` triggers on a planted 3-day shock.
2. `stop_policy`: absolute stop takes priority over trailing; cooldown blocks
   re-entry for `stop_cooldown_weeks`; `get_ledger_risk_state` renders the
   cooldown rows.
3. `portfolio_contract`: every alloc module returns the same `PlanWeights`
   shape (weights ≤ 1.0 with cash remainder documented); `--alloc` and
   `get_allocation_plan` consume it; turnover via `evaluate`.
4. `benchmark_surface`: strategy report renders vs buy-hold/equal-weight/MVO
   rows (cum/ann-return/vol/Sharpe/MaxDD/Calmar).
5. `--runfile` with stage+environment sections produces the identical invocation
   to the same flags; experiment ledger rows round-trip and are gitignored.
6. PIT registry masks post-as-of records (FinRL datadate→tradedate corpus);
   pre-market reviewer reads the prior decision point-in-time.
7. Any Phase-4 model passes walk-forward + PBO + cost gates before its score
   is advisory; selection is OOS-validation-based, never in-sample argmax;
   default OFF.
8. Full suite hermetic (timers), ruff clean, docs/README/CHANGELOG true,
   trading_web mirrored, committed + pushed.

## 12. References

- FinRL repo + README: https://github.com/AI4Finance-Foundation/FinRL (read;
  `finrl/meta/env_stock_trading/*`, `agents/stablebaselines3/models.py`,
  `meta/data_processor.py`, `meta/preprocessor/preprocessors.py`, `config.py`,
  `applications/stock_trading/ensemble_stock_trading.py`, `plot.py`,
  `meta/paper_trading/alpaca.py`)
- FinRL-Meta docs: `docs/source/finrl_meta/{Data_layer,Environment_layer,Benchmark,overview,background}.rst` (read)
- FinRL-X / FinRL-Trading repo + README + `ML_STOCK_SELECTION.md` +
  `src/strategies/{base_strategy,adaptive_rotation/*}`, `src/trading/trade_executor.py`,
  `src/data/data_processor.py` (read)
- FinRL paper: arXiv 2011.09607 (abstract-verified); FinRL-Meta: arXiv
  2211.03107 (abstract-verified); FinRL-X paper claimed at arXiv 2603.21330
  and FinRL-DeepSeek (Benhenda, Feb 2025) per README/web — `[claimed, not
  source-verified]`
- Web (2026-09-02): FinRL ecosystem/architecture; FinRL papers;
  FinRL-DeepSeek; DRL-trading critiques (backtest overfitting, look-ahead,
  reproducibility; walk-forward/purged-CV/deflated-Sharpe/PBO mitigations);
  Qlib-vs-FinRL / LLM+RL hybrid synthesis (weight-centric outputs, PIT
  discipline, LLM = signal not universal trader, hybrid > pure RL).

## 13. Merge note

This doc is the merged roadmap for **both** teachers: every module in
`docs/design_qlib_integration.md` is carried forward (owner column in §4);
FinRL adds the five modules in §6. Implementers follow THIS document's phased
rollout (§8) — the Qlib doc remains as the Qlib-specific design details that
§4 references.