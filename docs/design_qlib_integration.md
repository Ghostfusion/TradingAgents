# Design: Incorporating Qlib into TradingAgents

**Status:** design only — no code changed.
**Date:** 2026-09-02.
**Source study:** `https://github.com/Ghostfusion/qlib` (a vanilla mirror of
Microsoft's Qlib, `microsoft/qlib` line) — README + primary docs read this
session (`component/data.html`, `component/workflow.html`,
`component/strategy.html`, `component/online.html`, arXiv 2009.11189) plus a
web search on factor-ML/LLM integration governance.
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
- Tool `get_factor_profile(ticker)` (market): returns the latest row of a
  compact factor set — so the LLM can cite "price 2.3σ below its 20d mean with
  declining volatility" instead of re-deriving it.
- **Tests:** operator math on synthetic series; min-obs guards; profile shape.

### 3.2 `strategies/signal_analysis.py` — IC/quantile surface (Pillar 4)
- `rank_ic(signal, forward_returns)`, `icir(ic_series)`, `quantile_long_short`
  (reuse the sentiment-research quintile pattern but generic over any signal),
  `ic_decay_half_life` (reuse `curved` fit from `sentiment_research`).
- Wires into `strategy_quality_report.py` ("factor IC: 0.03, ICIR 1.2, decay
  8d") and a PM advisory line when a score series is present.
- **Tests:** planted predictive signal → positive rank IC; reverse → negative;
  none under short history.

### 3.3 `strategies/portfolio_strategy.py` — Topk-Drop + Enhanced Indexing (Pillar 3)
- `topk_drop_weights(scores, held, topk, n_drop)` — the Qlib Topk-Drop
  algorithm as a pure function (target weight change set, turnover = 2·drop/topk).
- `enhanced_index_weights(scores, benchmark_weights, tracking_error_cap)` —
  the tracking-error-controlled tilt (reuse `statistical.ols` / `evaluate`
  beta machinery).
- Tools: `get_topk_drop_plan(scores_by_name, topk, n_drop)`,
  `get_enhanced_index_tilt(scores, benchmark_weights)` → bound to the PM
  toolset (decision-agent advisory) + consumed by `pipeline.py --alloc`.
- **Tests:** topk-drop holds top-k by score and drops worst-held; turnover
  formula; enhanced tilt caps tracking error.

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

---

## 4. Where each piece lands (seams)

| Module | Seam | Config / flag | Web surface |
| --- | --- | --- | --- |
| `factor_expressions` | market analyst tool `get_factor_profile` | `enable_factor_profile` (False) | Value Tools |
| `signal_analysis` | `strategy_quality_report.py` + PM advisory | — (always-on pure calc) | Scripts screen row |
| `portfolio_strategy` | PM tools + `pipeline.py --alloc` + `action_report` | `enable_topk_drop` / `enable_enhanced_index` (False) | Pipeline alloc strategy |
| `runfile.py` + ledger | `batch.py`/`pipeline.py` flags front-end | `--runfile <yaml>` | Jobs screen preset |
| `pit_registry` | `pre_market_review`, fast path, backtests | `enable_pit_registry` (True) | Reports as-of labels |
| `factor_model_train` | advisory rank only | `enable_factor_model` (False) | none (research) |

Every new tool: hermetic tests with `pytest-timeout`, `agent_utils.__all__`
re-export, ToolNode + analyst prompt binding, `.env.example` mirror, docs.

---

## 5. Phased rollout

- **Phase 1 — pure calculators (highest ROI, no new data):** `factor_expressions`
  (subset + `get_factor_profile`), `signal_analysis` (rank IC/ICIR/quantile),
  `portfolio_strategy` (Topk-Drop + enhanced-index). Tests hermetic; docs true;
  web Value Tools mirror.
- **Phase 2 — runfile + experiment ledger:** `scripts/runfile.py` declarative
  runs + experiments JSONL; reproducibility/diff.
- **Phase 3 — PIT registry:** fundamentals/decision as-of store consumed by
  pre-market reviewer + fast path + backtests; as-of labels everywhere.
- **Phase 4 — advisory factor model (optional, gated):** `factor_model_train`
  + walk-forward/PBO gate before any score reaches the LLM; default OFF.
- **Phase 5 — fast-path alignment:** `docs/design_market_refresh_fastpath.md`
  T0/T1/T2 formalized with the runfile + pit_registry + signal_analysis (the
  Qlib online/routine analog), still advisory.

Each phase: pure functions + hermetic tests + `.env.example` + docs
(api_reference, developer/04-strategies, AGENT_ONBOARDING) + README/CHANGELOG +
trading_web mirror + commit/push, per the working agreement.

---

## 6. Non-goals / risks (honest)

- **No ML in the default path.** The fork's deterministic core stays the
  authority; the advisor factor model is Phase-4, gated, and never an executor
  (web-search-validated: ML factor = research filter, LLM = policy wrapper
  under hard risk rules).
- **No RL framework, no high-freq execution engine, no `.bin` storage rework.**
  The repo is single-name advisory analysis; Qlib's RL/HFT/order-execution
  pillars map to non-goals. The existing vendor cache + OHLCV cache stay.
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

## 7. Quick-wins verdict

1. **`factor_expressions` (+ `get_factor_profile`)** — pure, local, gives the
   LLM citable cross-sectional-style features with zero new vendors/quota.
2. **`signal_analysis`** — reuses the existing sentiment-research IC machinery
   generically; fills the IC/ICIR/quantile gap in `strategy_quality_report`.
3. **`portfolio_strategy` Topk-Drop/enhanced-index** — turns the composite-rank
   score into a turnover-managed allocation plan the PM can cite.
4. **Runfile + experiment ledger** — reproducibility/diff without touching the
   execution path.
5. **PIT registry** — correctness (as-of hygiene) that every later phase needs.
6. **Factor model** — last, gated, advisory-only (philosophy boundary).

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
7. Full suite hermetic (timers), ruff clean, docs/README/CHANGELOG true,
   trading_web mirrored, committed + pushed.