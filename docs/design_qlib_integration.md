# Design: Incorporating Qlib into TradingAgents

**Status:** design only — no code changed.
**Date:** 2026-09-02 (initial mirror study), **revised 2026-09-02 (direct
repo deep-research)**.
**Source study:** first pass read a vanilla mirror (`Ghostfusion/qlib`). This
revision deep-researches **`https://github.com/microsoft/qlib` directly**
(source-verified this session): README + ecosystem (RD-Agent), the key
component docs read as `.rst` in the repo (`docs/component/{data,workflow,
highfreq,online,meta,rl/overall}.rst`, `docs/advanced/PIT.rst`,
`docs/hidden/tuner.rst`), and primary source files (`qlib/data/ops.py`,
`qlib/data/pit.py` (format via docs), `qlib/contrib/data/handler.py`
(DataHandlerLP / Alpha158 / Alpha360), `qlib/data/dataset/processor.py`
(learn/infer processors), `qlib/backtest/exchange.py` (cost/limit/
volume-threshold model), `qlib/contrib/strategy/optimizer/enhanced_indexing.py`
(cvxpy convex program), `qlib/contrib/eva/alpha.py` (IC/long-short surface),
`qlib/workflow/online/manager.py` (OnlineManager + DelayTrainer),
`qlib/workflow/expm.py` + `qlib/model/trainer.py` (MLflow experiment manager,
train/delay-train), `examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml`
(qrun init-by-config), `examples/rl_order_execution/README.md` (QlibRL OE,
simulator gap), README model-zoo/benchmark + offline/online data-server
sections). Paper: arXiv 2009.11189 (primary), **arXiv 2505.15155
(RD-Agent-Quant, NeurIPS 2025 — LLM-driven factor/model co-optimization)**.
Web (2026-09-02): Qlib recent features (RL 2022, RD-Agent 2024, v0.9.7
parquet+MLflow Aug 2025), Qlib-vs-FinRL synthesis.
**Object:** absorb the transferable lessons of Qlib into this fork without
violating its contracts: **compute-as-tools, no-fabrication, advisory-first,
deterministic hard gates, walk-forward/PBO before any gate ships.**

Companion docs: `docs/design_market_refresh_fastpath.md` (the fast-path that
this design's online/routine pillar formalizes), `docs/design_quantlib_lean_enhancements.md`,
`docs/api_reference.md` §5/§6, `docs/developer/` set.

---

## 0. What Qlib is (one paragraph)

Qlib is Microsoft's **AI-oriented quantitative investment platform**: a full
research→production pipeline for **cross-sectional, factor/ML-driven
systematic quant** — a PIT (point-in-time) data layer with an expression
engine and Alpha158/Alpha360 factor libraries, a declarative workflow engine
(`qrun` YAML → init-by-config → train/predict/evaluate/backtest → recorder
experiment tracking), a model zoo (LightGBM, Transformer, TabNet, RL…), a
portfolio-strategy layer (Topk-Drop, Enhanced-Indexing…), a backtest engine
with cost/exchange modeling and IC/risk analysis, and **online serving /
model-rolling** (`OnlineManager.routine()` retrains and refreshes predictions
as new data arrives). Its worldview: **fit a statistical model to a large
universe's engineered features, let it rank/score, then manage a portfolio off
those scores** — evaluated by win-rate-free metrics like IC/ICIR and
walk-forward robustness.

**Since the mirror read, Qlib has evolved (verified in the source):** PIT
database (2022), **QlibRL** reinforcement-learning framework for order
execution (2022, PPO/OPDS/TWAP), **meta/market-dynamics** modeling (DDG-DA,
2022), **RD-Agent** LLM-driven Auto Quant Factory on top of Qlib (2024,
arXiv 2505.15155, NeurIPS 2025), and v0.9.7 (Aug 2025) adding **Parquet
support + MLflow integration**. §1a folds the new lessons into this design.

The fork's worldview is different and complementary: **LLM agent deliberation
over computed, deterministic numbers**, single-name-focused, live-vendor-fed,
decision-reviewed by committees + deterministic overlays. The two share DNA
already: `pipeline.py` (screen→rank→top-N) is a miniature cross-sectional
workflow, `evaluate_config_gate.py` is walk-forward+PBO, `memory.py` resolves
alpha vs regional benchmark, `_RUN_OHLCV_CACHE` is a panel cache, and
`docs/design_market_refresh_fastpath.md` is a model-rolling concept.

---

## 1. Qlib pillars → fork gaps → transferable lessons

| Qlib pillar | What it does | Fork gap today | Transferable lesson (adoptable) |
| --- | --- | --- | --- |
| **1. Data layer + expression engine** | `.bin` panel store; PIT integrity; `Ref/Mean/Std/Delta/…` operators; Alpha158/Alpha360 factor libraries | Vendor cache is TTL strings; OHLCV cache is in-run only; no factor-expression DSL; no PIT fundamentals snapshots | A **pure factor-expression layer** over the OHLCV/panel cache (operators as numpy calculators) + a **point-in-time registry** for fundamentals/decisions (the repo already has the look-ahead guard in `dataflows/date_window.py`; make it a first-class as-of snapshot store) |
| **2. Workflow + recorder** | `qrun` YAML declarative config → init-by-config; experiment/artifact recording (mlflow-style) | Runs are flag-driven (`batch.py/pipeline.py` flags); results tracked in `batch_summary_*.jsonl` + report trees + `risk_audit.jsonl` | A **declarative run YAML** (universe/analysts/depth/models/tools) expanded to the existing flags, plus an **experiment ledger** (config hash, metrics, artifacts) so every run is reproducible and diffable |
| **3. Strategy zoo** | `TopkDropoutStrategy`, `EnhancedIndexingStrategy`, `WeightStrategyBase` | `portfolio.py` has cap-respecting value weights + correlation penalty; no turnover-managed daily portfolio strategy | **Adopt Topk-Drop + enhanced-indexing as pure portfolio strategies** over a `pred_score` series (from composite rank or an advisory factor score) — feed `pipeline.py --alloc` and the PM's allocation tool; reuse `evaluate.backtest` turnover math |
| **4. Backtest / evaluation** | `backtest_daily`, `risk_analysis` (annualized return, IR, max DD), `SigAnaRecord` (IC/ICIR), cost/limit-threshold exchange | `evaluate_config_gate` (walk-forward+PBO), `backtest_strategy.py`, `strategy_quality_report.py` exist; **signal-level IC/ICIR/quantile analysis missing** (only `sentiment_research` has IC machinery) | **Signal analysis module** (rank IC, ICIR, quantile monotonicity, IC decay) generalized from `sentiment_research` to any factor/score series; wire into `strategy_quality_report` + the PM advisory context |
| **5. Model zoo** | LightGBM/Transformer/TabNet/… supervised factor models + RL | Fork is explicitly deterministic-first (`quants.md` non-goal: "no ML runtime") | **Advisory, gated, optional**: a supervised factor model (LightGBM) trained on Alpha158-style features → `pred_score` fed to the LLM as one more computed input — **only after walk-forward + PBO evidence** (repo `enable_threshold_gate` policy). Not a gate; never the executor (web search §6) |
| **6. RL framework** | Continuous decision/portfolio optimization via RL | No execution layer; decisions are advisory | **Non-goal** (see §5) — note only: the repo's reweight-to-baseline / consensus machinery is its analog for "policy under constraints" |
| **7. Online serving / model rolling** | `OnlineManager.routine()`: retrain + refresh predictions daily; DelayTrainer parallel batch | `pre_market_review` (CONFIRM/REVISE/REJECT) + `docs/design_market_refresh_fastpath.md` (T0/T1/T2) | **Formalize the fast path as an OnlineManager analog**: snapshot stamp, `routine()` = refresh decision from deltas, delay-train = nightly full-run cadence; HOLD/UPDATE/ESCALATE = decision policy |
| **8. Nested decision framework** | Multi-level strategies/executors at different granularities (high-freq vs daily) | `pre_market_review` (overnight) + report decisions (close) are two levels | **Alignment note**: the market-refresh fast path IS a second granularity level (intraday refresh over daily full-stack) — keep them as explicit layers, not a rewrite |
| **9. High-frequency data** | 1-min bars, order-book examples | `alpaca.get_intraday`/`get_bars` (1m) exist, screener-only | **Note only** — no execution need; the intraday data already lands in `market_session` tools |
| **10. Task management** | Serial/parallel trainers, collectors, task queue | `batch.py` ThreadPool + `effective_workers` cap; pipeline universe | **Already-aligned** (concurrency exists); adopt the "task = one configurable unit" idea into the run YAML (pillar 2) |

### 1a. New pillars verified in the direct repo study (2026-09-02)

| Qlib feature | What it does (source-verified) | Fork gap today | Transferable lesson (adoptable) |
| --- | --- | --- | --- |
| **11. RD-Agent / Auto Quant Factory** (arXiv 2505.15155, NeurIPS 2025) | An LLM multi-agent loop (Research agent proposes, Development agent implements) **iteratively proposes new factor expressions and model variants**, implemented in Qlib's DSL, evaluated on a PIT-validated dataset (IC/ICIR + backtest), and the results feed the next proposal; `rdagent fin_factor|fin_model|fin_quant` runs sit on Qlib. Reported: ~2× ARR vs benchmark factor libraries with >70% fewer factors | Factors are fixed calculators; no mechanism for the LLM to *propose* candidate factors that a deterministic layer then judges | A **factor-proposal loop pattern** — a light `scripts/factor_proposal_loop.py` (reuses the repo's LLM client; NO RD-Agent dependency) that has the LLM draft candidate expressions over `factor_expressions` operators, evaluates them deterministically (rank IC/ICIR/decay + walk-forward/PBO via §3.2 + §3.5), and only **gated** survivors become advisory tools. "LLM proposes, math decides" — a direct extension of compute-as-tools |
| **12. Learn/infer processor split** (`DataHandlerLP`, `qlib/data/dataset/processor.py`) | Cross-sectional normalization (`CSZScoreNorm`, `ZScoreNorm`, `Fillna`, `DropnaLabel`) is FIT on the **train segment only** (`fit_start_time..fit_end_time`) and the fitted stats applied to valid/test/live — the mechanical no-look-ahead rule | The fork standardizes ad-hoc per run (screener percentiles, `--rank`); no declared train-window for normalization moments | Every cross-sectional transform in the factor pipeline declares **fit-on-train / apply-everywhere**: store the fitted moments (mean/std) per snapshot in `pit_registry` so a later run reuses the same statistics (`fit_start_time`/`fit_end_time` in the runfile stage windows, §3.4) |
| **13. Exchange tradability model** (`qlib/backtest/exchange.py`) | Configurable `deal_price` ($close/$open/$vwap, or a buy/sell pair); `limit_threshold` (float on \|$change\| → limit-up/down untradable, or expression tuple); `volume_threshold` (participation-capped order size, cum vs current); `open_cost`/`close_cost`/`min_cost`/`impact_cost` (slippage); `trade_unit` (100 CN); `$close` NaN = suspended | `backtest_models.py` (Nautilus port) has fixed/maker-taker fees + adverse-tick slippage but **no limit-up/down tradability, no participation caps, no configurable deal price, no suspended-day gate** | Extend the backtest cost layer with a pure **tradability module** (`market_tradability`, §3.8): limit_threshold from the OHLCV `$change`, volume_threshold participation, suspended-day detection (NaN close), deal-price selection — makes `scripts/backtest_strategy.py` fills honest at level of Qlib's `Exchange` |
| **14. Convex-optimization portfolio construction** (`contrib/strategy/optimizer/enhanced_indexing.py`) | `EnhancedIndexingOptimizer` is a cvxpy program: `max d·r − λ(vᵀΣv + var_u·d²)` s.t. `w ≥ 0`, `Σw = 1`, `‖w − w0‖₁ ≤ δ` (turnover cap), benchmark-deviation bounds `wb ± b_dev`, factor-deviation bounds, force-hold / force-sell masks, epsilon cleanup, **graceful fallback** (drop turnover cap, then return w0) | `portfolio.py` uses heuristic caps + correlation penalty; the design's `enhanced_index_weights` sketch is a heuristic tilt | Upgrade §3.3's enhanced-index to the **constraint-program formulation** (turnover cap, benchmark-deviation, masks, fallback); cvxpy optional (scipy fallback projector) — pure function, advisory only, wired into `portfolio_contract` (FinRL doc §6.3) |
| **15. Signal-quality surface** (`contrib/eva/alpha.py`, `contrib/report/analysis_position/*`) | Per-date IC + Rank-IC series; **long-short return decomposition** `(r_long − r_short)/2, r_avg`; quantile long/short **precision**; **prediction autocorrelation** (`pred_autocorr` — is the forecast itself sticky?); excess-return with/without cost report (annualized return, **information_ratio**, max drawdown) | `sentiment_research` has IC machinery; no generic long-short decomposition, no pred-autocorrelation, no with/without-cost breakdown | Fold into §3.2 `signal_analysis`: `long_short_return`, `long_short_precision`, `pred_autocorr`; `strategy_quality_report` gains the **with/without-cost excess-return table** (IR + maxDD) |
| **16. DelayTrainer parallel training** (`workflow/online/manager.py`, `model/trainer.py`) | OnlineManager `routine()` retrains + refreshes predictions each period; **Trainer vs DelayTrainer**: delay-train records the tasks first, then **trains ALL tasks at the end** (parallel); `Simulation + DelayTrainer` backtests the whole history and trains every window's models afterwards; `history` records which models were online per day; `prepare_signals` ensembles them (`AverageEnsemble`) | The fast-path design (T0/T1/T2) has the cadence but no "batch the training, run it at the end" mechanism | Fast-path alignment: **T1 refresh = reuse the day's online models to update predictions; the nightly T2 full run IS the delayed training batch** — the Qlib DelayTrainer pattern applied to the repo's scheduled cadence (see also FinRL doc §3.9 / fast-path doc) |
| **17. Experiment manager / recorder** (`workflow/expm.py`, `workflow/recorder.py`, mlflow-backed) | `ExpManager` (mlflow URI), `R.log_params(flatten_dict(task_config))`, Recorder status lifecycle (started/done), saves the **model artifact + dataset CONFIG (never the raw data)**, `search_records` returns metrics/params/tags columns; file-locked for parallel writers | The planned ledger is JSONL rows; no artifact/dataset-config separation, no status lifecycle | Sharpen the §3.4 ledger: store `{config_hash, params, metrics, artifact: model/dataset-config, status}`, keep raw data OUT of the ledger (referenced by path), add a `search_records`-style read; reuse `risk_audit.jsonl` conventions |
| **18. Rolling retrain + meta/market-dynamics (DDG-DA)** | Rolling-retrain baseline + a **meta-controller** that learns patterns across a series of forecasting tasks and guides the next task (`docs/component/meta.rst`); adapts to non-stationarity | Fork's drift/decay monitor (design_institutional D2) + calibration + memory log are single-series, not task-series | **Alignment note** — DDG-DA's "learn across tasks, guide the next" is the fork's memory-log/calibration/drift-monitor stack; no new module needed, but the factor-model ensemble cadence (FinRL §6.6) is the natural place to adopt the rolling-retrain discipline |
| **19. Hyperparameter tuner** (`contrib/tuner/*`, hyperopt) | Tuner pipeline searches model + trainer + strategy + **data-label** spaces over rolling windows, optimizes a chosen report factor (`model_score`/`model_pearsonr`/backtest IR), saves local + global best params | `evaluate_config_gate` gates thresholds but does no search | **Optional** search front-end whose *candidates must pass the existing walk-forward+PBO gate* — search may find, the gate decides (never promote on search alone); keeps G5 threshold-governance authority |
| **20. Expression/dataset cache + model-zoo benchmark convention** | Expression cache (computed factor results keyed by expression string) + dataset cache: the data-server benchmark shows **7.4 s vs 184.4 s (HDF5)** for a 14-feature × 800-stock × 2007-2020 build; every zoo model reports on Alpha158/Alpha360 against a central results table (IC/ICIR + backtest IR) | `_RUN_OHLCV_CACHE` caches raw OHLCV, not computed factors; no shared benchmark table for candidates | Layer an **expression-string-keyed cache** on §3.1 (including PIT-safe invalidation via `pit_registry`); every advisory-model candidate is reported **vs simple baselines (equal-weight / value-ratio / momentum) on the same IC + backtest surface** — the convention `benchmark_surface` (FinRL §6.4) + `signal_analysis` combine to give |
| **21. Simulator-gap honesty** (`examples/rl_order_execution/README.md`) | QlibRL warns: training uses a **simplified simulator**, backtest a realistic one → results differ; to reproduce training numbers, run the backtest with the same simulator | `backtest_strategy.py` fills at close/limit with a stated model, but the gap between "assumed fills" and "the paper book" is not always labeled | **Note only**: `backtest_strategy.py` and `pre_market_ledger` rows must state their fill model (deal price, slippage, partial-fill) so a reader never mistakes the simulation for the execution — same honesty contract as RD-Agent findings |

---

## 2. Design principles (bound by the repo contract)

1. **Advisory-first, always.** Every Qlib-sourced artifact is a deterministic
   calculator or an advisory signal injected into the decision agents — the
   hard gates remain the existing overlay pipeline (regime → catalyst → contract
   → governor).
2. **Deterministic core.** The expression engine, strategy math, and signal
   analysis are pure functions (like every `strategies/*` module). No-fabrication:
   `float | None`, explicit `unavailable`, min-observation guards.
3. **ML is a research filter, not an executor.** The web-search-validated
   pattern: an ML factor model must pass walk-forward + PBO/DSR + cost
   robustness **before** its score is even advisory to the LLM — this is the
   repo's existing `evaluate_config_gate` / `enable_threshold_gate` policy,
   applied to any new model.
4. **Point-in-time discipline.** Everything the LLM sees carries an as-of
   timestamp; no look-ahead (extend `dataflows/date_window.py` semantics to any
   stored snapshot).
5. **Everything is a tool.** New calculators become `@tool`s bound to the
   analysts (working-agreement §0), re-exported in `agent_utils`, in the graph
   ToolNode + prompt, web-mirrored.

---

## 3. Proposed modules (pure, hermetic-tested)

### 3.1 `strategies/factor_expressions.py` — expression engine (Pillar 1)
- A small operator set over a price/panel series: `Ref(k)`, `Delta(k)`,
  `Mean(k)`, `Std(k)`, `ZScore(k)`, `Rsi`, `Bias`, `Mom(k)`, `Rank`, `Corr(x,y,k)`,
  `AvgVol`, `HighLowRange`… each a pure function (`np.ndarray → np.ndarray`,
  `None` under min-obs).
- `alpha158_subset(ohlcv) -> dict[feature, series]` — a curated subset of
  Alpha158-style features (momentum/reversal/volatility/value) computed off the
  run-level OHLCV cache; advisory.
- **Expression-level cache (pillar 20):** computed factor values cached keyed
  by the expression string + instrument + range (Qlib: 7.4 s vs 184.4 s HDF5
  for a 14-feature build), layered on `_RUN_OHLCV_CACHE`; invalidation honours
  the `pit_registry` as-of window.
- **Learn/infer processor split (pillar 12):** any cross-sectional transform
  (CS-Z-score / winsorize / fillna) declares `fit_*` windows in the runfile;
  the **moments are fit on the train segment only** and the fitted stats are
  stored per snapshot in `pit_registry`, then applied to valid/test/live —
  the mechanical no-look-ahead rule.
- Tool `get_factor_profile(ticker)` (market): returns the latest row of a
  compact factor set — so the LLM can cite "price 2.3σ below its 20d mean with
  declining volatility" instead of re-deriving it.
- **Tests:** operator math on synthetic series; min-obs guards; profile shape.

### 3.2 `strategies/signal_analysis.py` — IC/quantile surface (Pillar 4)
- `rank_ic(signal, forward_returns)`, `icir(ic_series)`, `quantile_long_short`
  (reuse the sentiment-research quintile pattern but generic over any signal),
  `ic_decay_half_life` (reuse `curved` fit from `sentiment_research`).
- **Pillar 15 additions:** `long_short_return` (`(r_long − r_short)/2`, `r_avg`
  per date), `long_short_precision` (quantile long/short prec), `pred_autocorr`
  (is the forecast itself sticky — the signal-side twin of
  `return_autocorrelation`); `strategy_quality_report.py` gains the
  **excess-return with/without-cost** table (annualized return, information
  ratio, max drawdown), the standard Qlib backtest report.
- Wires into `strategy_quality_report.py` ("factor IC: 0.03, ICIR 1.2, decay
  8d") and a PM advisory line when a score series is present.
- **Tests:** planted predictive signal → positive rank IC; reverse → negative;
  none under short history.

### 3.3 `strategies/portfolio_strategy.py` — Topk-Drop + Enhanced Indexing (Pillar 3, 14)
- `topk_drop_weights(scores, held, topk, n_drop)` — the Qlib Topk-Drop
  algorithm as a pure function (target weight change set, turnover = 2·drop/topk).
- `enhanced_index_weights(scores, benchmark_weights, w0, turnover_cap, b_dev,
  f_dev, force_hold, force_sell)` — the **Qlib convex program (pillar 14)** as
  a pure function: `max d·r − λ(vᵀΣv + var_u·d²)` s.t. long-only, `Σw = 1`,
  `‖w − w0‖₁ ≤ turnover_cap`, benchmark-deviation bounds, factor-deviation
  bounds, force-hold/force-sell masks, epsilon cleanup, and the **two-stage
  fallback** (drop turnover cap → return `w0`) on solver failure. cvxpy
  optional (a scipy projection fallback keeps the core path dependency-free);
  `None`/`unavailable` under degenerate input (no-fabrication).
- Tools: `get_topk_drop_plan(scores_by_name, topk, n_drop)`,
  `get_enhanced_index_tilt(scores, benchmark_weights, w0?, turnover_cap?)` →
  bound to the PM toolset (decision-agent advisory) + consumed by
  `pipeline.py --alloc` and `portfolio_contract` (FinRL doc §6.3).
- **Tests:** topk-drop holds top-k by score and drops worst-held; turnover
  formula; enhanced-index caps tracking error AND total turnover, honours
  force-hold/force-sell masks, falls back to `w0` when the problem is
  infeasible (no exception).

### 3.4 `scripts/runfile.py` + experiment ledger (Pillar 2)
- A YAML "runfile" (declarative: universe/date/analysts/depth/vendor/model
  hooks/tools) expanded 1:1 to the existing `batch.py`/`pipeline.py` flags —
  **no new execution path**, just a declarative front-end.
- An experiment ledger appended per run:
  `{run_id, config_hash, symbol(s), metrics: {ic, icir, mdd, sharpe, pbo},
  artifacts: [report_dir, summary]}` — under `data_cache_dir/experiments/`
  (gitignored), reusing the `batch_summary_*.jsonl` row shape + `risk_audit.jsonl`.
- **Tests:** runfile→flags equivalence; config-hash stability; ledger append.

### 3.5 Point-in-time registry (Pillar 1b)
- `dataflows/pit_registry.py`: store fundamentals/decision snapshots keyed by
  `(symbol, as_of)` so any later re-analysis (or the fast path) reads the same
  point-in-time view the original run used — surfaces the as-of on every read.
  Backed by the existing disk cache dir; reuses `date_window.py` for the window.
- **Label convention (Alpha158/360):** the canonical markup label is the
  **next-execution-day return with a one-day buffer** — Qlib's
  `Ref($close,-2)/Ref($close,-1) - 1` (features at t, label = t+1→t+2 close
  return, i.e. the return realized AFTER the close the signal could trade at);
  same family as FinRL-X's tradedate discipline. The registry records the
  label + its as-of day so backtests and the factor loop never align a signal
  with a same-day return.
- Consumed by: pre-market reviewer (prior decision already from
  `full_states_log`), the fast path, and backtest hygiene.
- **Tests:** as-of masking (a record dated after `as_of` is never visible).

### 3.6 Optional advisory factor model (Pillar 5 — gated, Phase 4)
- `scripts/factor_model_train.py`: LightGBM over `factor_expressions` features
  on the memory-log realized outcomes; output = `pred_score` per name.
- **Gate (repo policy):** the score reaches the LLM only after the existing
  walk-forward+PBO gate (`evaluate_config_gate.py`) passes on OOS data; until
  then it is a research artifact only. Config `enable_factor_model=False`
  default; `.env` mirror.
- Not in the default chain; a philosophy footnote: the fork's deterministic
  core stays the authority; the model is an extra computed input, never a gate.

### 3.7 `scripts/factor_proposal_loop.py` — LLM-proposed candidates, math decides (Pillar 11)
- **Pattern (RD-Agent, not the dependency):** a small loop that (1) has the LLM
  (the repo's existing client) draft candidate factor expressions from a menu of
  `factor_expressions` operators + a short "current factor list / recent IC"
  prompt, (2) evaluates each candidate deterministically — rank IC/ICIR/decay
  (§3.2), PIT-safe via `pit_registry`/learn-infer stats (§3.1), then the
  walk-forward+PBO gate §3.6 applies, (3) emits a **candidate sheet** with the
  raw metrics and (4) only **gated** survivors become advisory tools
  (`get_factor_profile` gains new rows by config, default OFF).
- **Guards (repo contract):** the LLM only proposes; every number in the sheet
  is computed, never narrated; no candidate is added to a default tool chain
  without the gate; the loop costs no new dependency (no RD-Agent, no Docker).
- Config `enable_factor_proposal_loop` (False) + `factor_proposal_*` keys.
- **Tests:** hermetic — an injected "proposal" of a planted predictive factor
  gets a positive IC row and a gated "adopt" flag; a random-noise proposal
  gets an honest reject; the sheet renders only computed columns.

### 3.8 `strategies/market_tradability.py` — backtest tradability model (Pillar 13)
- Pure module extending `backtest_models.py`: `limit_gate(change, threshold)`
  (limit-up → untradable to buy, limit-down → untradable to sell),
  `volume_gate(order_qty, day_volume, participation_cap)` (cap at a % of
  volume), `suspended(close)` (NaN close = suspended, mirroring Qlib's
  `$close` convention), `deal_price_selector(bar, price_spec)` (`close` |
  `open` | `vwap`, or a buy/sell pair) — all `float | None` / bool,
  no-fabrication.
- Wire into `scripts/backtest_strategy.py`: fills are refused on suspended/
  limit days and capped by participation; the report states the deal-price +
  limit thresholds used (§7/non-goal 21 honesty).
- Config: `backtest_limit_threshold` (0.0 = off), `backtest_volume_participation`
  (0.2 default cap), `backtest_deal_price` ("close").
- **Tests:** limit-up blocks a buy and allows a sell; suspended day yields no
  fill; participation cap truncates qty; vwap deal price selected.

### 3.9 Ledger sharpening — recorder-style experiment rows (Pillar 17)
- Extend the §3.4 ledger row to: `{run_id, config_hash, params, metrics: {ic,
  icir, mdd, sharpe, pbo, ir_with_cost, ir_without_cost}, status, artifact:
  {model: path, dataset_config: path, report_dir}}.` Raw data stays OUT of the
  ledger (referenced by path); `status` lifecycle (pending/done/failed) with a
  file-lock for parallel writers (batch workers).
- A `scripts/experiments.py` read view (`search_records`-style filter on
  metrics/params) so candidates from §3.7 and §3.6 are diffable.

### 3.10 Optional tuner front-end + market-dynamics alignment (Pillars 18-19)
- **Tuner (optional):** a hyperopt-style search over §3.6's model params (and
  optionally §3.2's signal transforms) with rolling windows — **search only;
  every candidate still passes the existing walk-forward+PBO gate before
  promotion** (G5 authority kept). `enable_tuner` (False).
- **Market-dynamics alignment:** DDG-DA's "learn across tasks, guide the next"
  is an alignment note — the memory log, calibration table, and
  `strategy_quality_report` drift/decay monitor already implement the concept;
  the factor-model ensemble cadence (FinRL doc §6.6) is the rolling-retrain
  seating. No new module.

---

## 4. Where each piece lands (seams)

| Module | Seam | Config / flag | Web surface |
| --- | --- | --- | --- |
| `factor_expressions` | market analyst tool `get_factor_profile` | `enable_factor_profile` (False) | Value Tools |
| `signal_analysis` | `strategy_quality_report.py` + PM advisory | — (always-on pure calc) | Scripts screen row |
| `portfolio_strategy` | PM tools + `pipeline.py --alloc` + `action_report` | `enable_topk_drop` / `enable_enhanced_index` (False) | Pipeline alloc strategy |
| `runfile.py` + ledger | `batch.py`/`pipeline.py` flags front-end; §3.9 recorder rows + status | `--runfile <yaml>` | Jobs screen preset + experiments read view |
| `pit_registry` | `pre_market_review`, fast path, backtests; §3.1 fitted norm moments + label convention | `enable_pit_registry` (True) | Reports as-of labels |
| `factor_model_train` | advisory rank only | `enable_factor_model` (False) | none (research) |
| `factor_proposal_loop` | §3.7 candidate sheet → gated rows into `get_factor_profile` | `enable_factor_proposal_loop` (False) + `factor_proposal_*` | Value Tools (gated rows only) |
| `market_tradability` | `scripts/backtest_strategy.py` fills + `pre_market_ledger` | `backtest_limit_threshold` / `backtest_volume_participation` / `backtest_deal_price` | Scripts screen row |
| tuner (optional) | §3.10 search over §3.6 params | `enable_tuner` (False) | none (research) |

Every new tool: hermetic tests with `pytest-timeout`, `agent_utils.__all__`
re-export, ToolNode + analyst prompt binding, `.env.example` mirror, docs.

---

## 5. Phased rollout

- **Phase 1 — pure calculators (highest ROI, no new data):** `factor_expressions`
  (subset + `get_factor_profile` + expression cache + learn/infer split),
  `signal_analysis` (rank IC/ICIR/quantile + long-short + pred_autocorr +
  with/without-cost table), `portfolio_strategy` (Topk-Drop + the convex
  enhanced-index with masks/fallback), `market_tradability`. Tests hermetic;
  docs true; web Value Tools mirror.
- **Phase 2 — runfile + experiment ledger:** `scripts/runfile.py` declarative
  runs (with stage windows, §3.4) + recorder-style experiments rows (§3.9);
  reproducibility/diff.
- **Phase 3 — PIT registry:** fundamentals/decision as-of store consumed by
  pre-market reviewer + fast path + backtests; as-of labels everywhere;
  fitted normalization moments stored per snapshot (learn-infer split).
- **Phase 4 — advisory factor model + factor-proposal loop (optional, gated):**
  `factor_model_train` + `factor_proposal_loop` — every candidate passes the
  walk-forward/PBO gate before any score reaches the LLM; default OFF.
- **Phase 5 — fast-path alignment + tuner:** `docs/design_market_refresh_fastpath.md`
  T0/T1/T2 formalized with the runfile + pit_registry + signal_analysis + the
  DelayTrainer pattern (§1a-16); optional tuner (§3.10); still advisory.

Each phase: pure functions + hermetic tests + `.env.example` + docs
(api_reference, developer/04-strategies, AGENT_ONBOARDING) + README/CHANGELOG +
trading_web mirror + commit/push, per the working agreement.

---

## 6. Non-goals / risks (honest)

- **No ML in the default path.** The fork's deterministic core stays the
  authority; the advisor factor model is Phase-4, gated, and never an executor
  (web-search-validated: ML factor = research filter, LLM = policy wrapper
  under hard risk rules).
- **No RD-Agent dependency.** The §3.7 loop adopts RD-Agent's *pattern* (LLM
  proposes, deterministic math decides) using the repo's own LLM client — never
  the RD-Agent system (Linux + Docker + its own agent loop).
- **No RL framework, no high-freq execution engine, no `.bin` storage rework.**
  The repo is single-name advisory analysis; Qlib's RL/HFT/order-execution
  pillars map to non-goals (QlibRL's order-execution RL exists — 2022 — and is
  the simulator-gap cautionary tale, pillar 21). The existing vendor cache +
  OHLCV cache stay; cvxpy stays optional (scipy fallback).
- **Cross-sectional data is thin.** Alpha158-style features need panel history;
  the fork's universe runs are per-name. `get_factor_profile` is
  single-name-accurate but cross-sectional IC/decay needs the screener's
  universe runs — honest scope: signal analysis degrades to `unavailable`
  below min-observation breadth.
- **Overfitting risk.** Any new feature/model must pass the existing walk-forward
  + PBO gate before promotion (repo `enable_threshold_gate` policy) — the
  search-validated gate order: walk-forward, PBO/DSR, parameter stability,
  cost robustness, then promotion.
- **Scope creep.** Each pillar maps to ONE module; nothing here rewires the
  graph topology or the overlay order.
- **RD-Agent claims are not promises.** The reported 2× ARR / 70%-fewer-factors
  numbers are from the paper's own setting (CN market, its loop, its costs);
  the §3.7 loop's value is the propose→evaluate discipline, not those numbers.

## 7. Quick-wins verdict

1. **Learn/infer processor split** — the mechanical no-look-ahead rule for
   every future factor/score; pure stat-fitting, ~no new code.
2. **`factor_expressions` (+ `get_factor_profile` + expression cache)** — pure,
   local, gives the LLM citable cross-sectional-style features with zero new
   vendors/quota.
3. **`signal_analysis` (+ long-short / pred_autocorr / with-without-cost)** —
   reuses the existing sentiment-research IC machinery generically; fills the
   IC/ICIR/quantile gap in `strategy_quality_report`.
4. **`market_tradability`** — makes the existing backtest fills honest
   (limit/suspension/participation/deal-price) at near-zero cost.
5. **`portfolio_strategy` Topk-Drop + convex enhanced-index** — turns the
   composite-rank score into a turnover-managed, constraint-respecting
   allocation plan the PM can cite.
6. **Runfile + experiment ledger** — reproducibility/diff without touching the
   execution path.
7. **PIT registry** — correctness (as-of hygiene) that every later phase needs.
8. **Factor-proposal loop + factor model** — last, gated, advisory-only
   (philosophy boundary).

## 8. Acceptance (evidence checklist)

1. `get_factor_profile` returns a compact computed factor set on a live name;
   incorrect input → explicit unavailable, never a guess.
2. `rank_ic`/`icir` recover planted signals and report `unavailable` under
   short history; quantile monotonicity matches the directional tilt.
3. Topk-Drop holds top-k by score, drops worst-held, turnover = 2·drop/topk;
   enhanced-index caps tracking error.
4. `--runfile` produces the identical invocation to the same flags; experiment
   ledger rows round-trip and are gitignored.
5. PIT registry masks post-as-of records; pre-market reviewer reads the prior
   decision point-in-time.
6. Any Phase-4 model passes walk-forward + PBO + cost gates before its score is
   advisory; default OFF.
7. Cross-entity normalization moments fit on the train segment only: a malicious
   test-window value does not alter the fitted mean/std (hermetic test against
   the learn/infer split).
8. `market_tradability`: limit-up blocks a buy and allows a sell; suspended day
   yields no fill; participation cap truncates qty; backtest report states the
   deal-price/thresholds used.
9. Convex enhanced-index: caps tracking error AND total turnover; honours
   force-hold/force-sell masks; returns `w0` on an infeasible problem (no
   exception).
10. Factor-proposal loop: a planted predictive candidate gets a computed IC row
   and a gated "adopt" flag; random-noise candidates are honestly rejected;
   the candidate sheet contains only computed columns.
11. Ledger rows carry `{config_hash, params, metrics, status, artifact}`, raw
   data stored by reference only; `scripts/experiments.py` diff view works.
12. Full suite hermetic (timers), ruff clean, docs/README/CHANGELOG true,
   trading_web mirrored, committed + pushed.