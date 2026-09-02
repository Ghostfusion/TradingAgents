# Implementation Plan — Qlib Integration (companion to `docs/design_qlib_integration.md`)

**Status:** plan only — no code changed.
**Date:** 2026-09-02.
**Source:** `docs/design_qlib_integration.md` (revised, direct `microsoft/qlib` study).
**Scope:** turn design §3 modules + §5 phases into concrete, reviewable tasks. Every task names exact files, functions, seams (verified against this repo), tests, config keys, and the design §8 acceptance item it evidences. Nothing here is a mandate: each phase ships as its own commit after its own approval, per the working agreement.

## 1. Ground rules (verified repo facts)

- All repo Python lives under the `tradingagents/` package; root scripts are `batch.py`, `pipeline.py`, `main.py`, `cli/main.py`, `scripts/*.py` (dev tools). Tests are root-level `tests/test_*.py`, each with `pytest.mark.timeout` (hermetic convention).
- `py -3.12` only (bare `python` = wrong venv). Windows shell: no heredocs — `write`/`edit` only. Console scripts author `main()` + `if __name__ == "__main__": raise SystemExit(main())` (see `scripts/evaluate_config_gate.py`).
- Commit style: Conventional Commits; **explicit `git add <paths>` only** — never `git add -A` (sweeps `Direction.md`, `_probe*.ps1`, `session.md`). `changelog.md` ≠ `CHANGELOG.md` (capitalize).
- Config: `tradingagents/default_config.py` `DEFAULT_CONFIG` dict + root `.env.example` mirror for every new key. Web mirror: `trading_web/backend/...` `run_value_tools` allowlist (design §4 table lists the web surface per module).
- Docs-true rule: `docs/api_reference.md` §5/§6, `docs/developer/04-strategies.md`, `docs/AGENT_ONBOARDING.md`, `README.md` (News + feature bullet), `CHANGELOG.md` updated in the same commit as the code.
- Every new tool: `tradingagents/agents/utils/agent_utils.py` `__all__` re-export → analyst prompt binding → graph ToolNode (`tradingagents/graph/trading_graph.py`, market node) → web allowlist → docs.
- No-fabrication: `float | None`, explicit `"unavailable"`, min-observation guards (repo contract; see `backtest_models.py` style).

## 2. Verified seams the plan touches

| Seam | Verified anchor |
| --- | --- |
| `_RUN_OHLCV_CACHE` | `tradingagents/agents/utils/analysis_tools.py:37` — `dict[(ticker, days)]`, `_ohlcv()` fetcher keyed `(ticker, days)`; the expression cache layers on this dict shape (keys: open/high/low/close/volume lists) |
| Tool re-exports | `tradingagents/agents/utils/agent_utils.py:168` `__all__`; separate tool modules `alpaca_tools.py`, `momentum_tools.py` exist (pattern for a new `factor_tools.py`) |
| IC machinery to generalize | `tradingagents/strategies/sentiment_research.py`: `rolling_information_coefficient` (per-date Pearson+Rank IC), `ic_term_structure` (mean rank IC + half-life), `quintile_long_short`, `_forward_returns`, `_bucket` — signal_analysis reuses patterns, not the sentiment coupling |
| Return/gate math | `tradingagents/strategies/evaluate.py` — `walk_forward_splits`, `sharpe`, `pbo_flag`, `deflated_sharpe` (consumed by `scripts/evaluate_config_gate.py` `gate_verdict(returns, train_len=60, test_len=20, trials=20)`); `cagr`, `sharpe` used in `scripts/backtest_strategy.py` (`ev.` alias) |
| Cost/fill models | `tradingagents/strategies/backtest_models.py` — `fixed_fee`, `maker_taker_fee`, `slip_price`, `make_cost_fn`, `limit_fill_probability`, `__all__`; `scripts/backtest_strategy.py` `backtest(...)` fills at close, `--fee-bps`, `--slippage-ticks`, honesty note already in module docstring |
| Look-ahead guard | `tradingagents/dataflows/date_window.py` — `to_utc`, `in_window` (half-open `[start, end+1d)`); `pit_registry` reuses these |
| Run-file front-end | `pipeline.py` args (verified): `tickers`, `-f/--file`, `-u/--universe`, `--market`, `-n --movers-count`, `--movers-direction`, `--top`, `--limit`, `-d --date`, `--min-mcap`, `--price-min`, `--pe-max`, `--workers`, `--analysts`, `--depth`, `--vendor` — runfile maps 1:1 to these; NOTE design §4 says `pipeline.py --alloc` — that flag does not exist yet; Phase 1 adds it |
| Gate eval | `scripts/evaluate_config_gate.py` `gate_verdict()` — reuse as-is for every Phase-4 candidate (walk-forward + PBO + deflated Sharpe) |
| Cache dirs | `DEFAULT_CONFIG["results_dir"]` (env `TRADINGAGENTS_RESULTS_DIR`), `DEFAULT_CONFIG["data_cache_dir"]` (env `TRADINGAGENTS_CACHE_DIR`, default `~/.tradingagents/cache` — outside the repo → experiments ledger is gitignored by location; no `.gitignore` edit needed) |

## 3. Dependencies (build order)

```
Phase 1 pure modules (independent, parallelizable):
  factor_expressions ─ signal_analysis ─ market_tradability ─ portfolio_strategy
   │            └                        └               └
   ├─ tools: get_factor_profile / PM alloc tools (analysis_tools + __all__ + ToolNode + prompts)
   └
Phase 2: runfile + ledger (needs phases-1 modules for stage-window/learn-infer keys) ─ experiments.py
   └
Phase 3: pit_registry (independent of 1-2; can be pulled earlier — needed for learn/infer persistence + label) 
   └
Phase 4: factor_model_train (needs factor_expressions features + pit labels + gate) ─ factor_proposal_loop (needs signal_analysis + gate + LLM client)
   └─ tuner (optional; needs model)
Phase 5: fast-path alignment + tuner cadence (cross-refs design_market_refresh_fastpath.md)
```

## 4. Phase 1 — pure calculators (design §3.1, 3.2, 3.3, 3.8)

### 4.1 `tradingagents/strategies/factor_expressions.py` (new)
- Operators (pure `np.ndarray → np.ndarray | None` under min-obs): `ref(s,k)`, `delta(s,k)`, `mean(s,k)`, `std(s,k)`, `zscore(s,k)` (rolling), `rsi(s,k=14)`, `bias(s,k)`, `mom(s,k)`, `rank(xs)` (cross-sectional per date over a panel dict, reusing `_bucket`-style rank), `corr(x,y,k)`, `avg_vol(volume,k)`, `high_low_range(high,low,close,k)`.
- `alpha158_subset(ohlcv: dict) -> dict[str, list[float]]` — ~20-feature Alpha158 subset (momentum/reversal/volatility/value) computed off the `_ohlcv()` dict shape; advisory.
- `fit_zscore(train) -> (mean, std)` + `apply_zscore(values, mean, std)`, `fit_winsorize(train) -> (lo, hi)` + `apply_winsorize` — **learn/infer split**: fit on train segment only (runfile `stages.fit`), apply to valid/test/live. Moments stored per snapshot by `pit_registry` (Phase 3); until then a JSON sidecar under `data_cache_dir/experiments/` (config key the moments table).
- Expression cache: `_EXPR_CACHE: dict[(expr_str, symbol, bars, date), list]` layered on `_RUN_OHLCV_CACHE`, cap + evict-oldest (e.g. 512 entries), invalidation = as-of window change (date/bars/symbol) — honors `pit_registry` as-of (`_ohlcv` already refreshes by date).
- **Tool** `get_factor_profile(ticker, days=320)` → in `analysis_tools.py` near `_ohlcv` (or new `factor_tools.py`), re-export, bind market analyst prompt + market ToolNode; returns JSON dict `{as_of, factors, unavailable}` — no fabrication.
- Config: `enable_factor_profile` (default False) → `default_config.py` + `.env.example`.
- Tests `tests/test_factor_expressions.py`: operator math on synthetic series; min-obs → None; `alpha158_subset` shape; profile shape + unavailable path; **learn/infer hermetic: malicious test-window value does not change fitted mean/std (design §8-7)**; cache hit/miss + invalidation on date change.
- Acceptance: design §8-1, §8-7.
- Docs: api_reference §5, developer/04, AGENT_ONBOARDING feature list, README, CHANGELOG.

### 4.2 `tradingagents/strategies/signal_analysis.py` (new)
- `rank_ic(signal, forward_returns) -> float | None`, `icir(ic_series) -> float | None` (mean/std·√n), `quantile_long_short(signal, prices, rebalance, holding) -> dict` (quintile monotonicity + L-S spread; generalize `sentiment_research.quintile_long_short`, drop sentiment coupling), `ic_decay_half_life(ic_by_horizon)` (reuse `ic_term_structure` half-life fit), `long_short_return(r_long, r_short) -> (r_long − r_short)/2, r_avg`, `long_short_precision(predicted, realized, quantiles)`, `pred_autocorr(signal, lag=1) -> float | None` (is the forecast sticky — the signal-side twin of return autocorrelation).
- Wire into `scripts/strategy_quality_report.py`: add a "signal IC/IR/decay/L-S" section + the **excess-return with/without-cost table** (annualized return, IR, max drawdown) using `evaluate.cagr/sharpe` + the `backtest_models.make_cost_fn` cost path — the with/without split is the Qlib report convention.
- PM advisory line when a score series is present (portfolio_manager prompt/tool result string).
- Always-on pure calc — no config key.
- Tests `tests/test_signal_analysis.py`: planted predictive → positive rank IC + monotonic quantiles; reversed → negative; short history → `unavailable`/None; L-S decomposition arithmetic; sticky series → high pred_autocorr (design §8-2).
- Acceptance: §8-2.

### 4.3 `tradingagents/strategies/portfolio_strategy.py` (new)
- `topk_drop_weights(scores, held, topk, n_drop) -> dict[str, float]` — holds top-k by score, drops worst-held (`n_drop`), turnover = 2·drop/topk.
- `enhanced_index_weights(scores, benchmark_weights, w0, turnover_cap, b_dev=0.02, f_dev=None, force_hold=frozen-set|None, force_sell=None) -> dict[str, float] | None` — convex program: `max d·r − λ(vᵀΣv + var_u·d²)` s.t. `w ≥ 0`, `Σw = 1`, `‖w − w0‖₁ ≤ turnover_cap`, benchmark- and factor-deviation bounds, masks, epsilon cleanup, **two-stage fallback** (drop turnover cap → return `w0`), `None` under degenerate input. cvxpy **optional**: `try: import cvxpy` else scipy projection fallback (simplex projection + greedy turnover cap) — no hard dependency (design §6).
- Tools → `analysis_tools.py` (PM toolset): `get_topk_drop_plan(scores_by_name, topk, n_drop)`, `get_enhanced_index_tilt(scores, benchmark_weights, w0=None, turnover_cap=0.2)`; re-export; bind PM; consumed by `pipeline.py --alloc` (new CLI flag → alloc plan printed into `action_report`/PM context; flag gated by `enable_topk_drop`/`enable_enhanced_index` (False)). `portfolio_contract` (FinRL doc §6.3) is a later wrapper — no-op here.
- Tests `tests/test_portfolio_strategy.py`: top-k hold + worst-held drop + turnover formula (design §8-3); convex: caps tracking error AND turnover, honours masks, fallback to `w0` on infeasible without exception (design §8-9).
- Acceptance: §8-3, §8-9.

### 4.4 `tradingagents/strategies/market_tradability.py` (new)
- Same family as `backtest_models.py` (`__all__`, pure, no-fabrication): `limit_gate(change, threshold) -> "up" | "down" | None` (limit-up blocks buy, limit-down blocks sell), `volume_gate(order_qty, day_volume, cap=0.2) -> int` (truncates), `suspended(close) -> bool` (NaN close = suspended, Qlib `$close` convention), `deal_price_selector(bar, price_spec) -> float | None` (`close` | `open` | `vwap`, or a `(buy, sell)` pair of specs).
- Wire into `scripts/backtest_strategy.py`: in `backtest(...)` fill loop — refuse fills on suspended/limit days, cap qty by participation, pick deal price per spec; report prints `deal_price=<spec> limit_threshold=<x> participation=<cap>` so the fill model is stated (design §8-8 honesty).
- Config + CLI: `backtest_limit_threshold` (0.0 = off), `backtest_volume_participation` (0.2), `backtest_deal_price` ("close") in `default_config.py`/`.env.example`; `--deal-price`, `--limit-threshold`, `--participation` flags override.
- Tests `tests/test_market_tradability.py`: limit-up blocks a buy, allows a sell; suspended day → no fill; cap truncates qty; vwap selected (design §8-8).
- Acceptance: §8-8.

### 4.5 Phase-1 integration task (one owner)
- New tools in `agent_utils.__all__` + market/PM prompts + graph ToolNode; `pipeline.py --alloc` flag; `default_config.py` keys + `.env.example`; trading_web allowlist + scripts screen rows; docs set; `ruff check` + full hermetic suite; commit. Suggested commit: `feat: qlib phase 1 pure calculators (factor expressions, signal analysis, tradability, alloc)` — plus separate `feat: pipeline --alloc` if cleaner.

## 5. Phase 2 — runfile + experiment ledger (design §3.4 + §3.9)

- `scripts/runfile.py` (new): `--runfile <yaml>`, `--dry-run` (print expanded argv, no run), `--ledger <path>|off`. YAML keys `{universe:{file|tickers, top, limit, min_mcap, price_min, pe_max}, date, analysts, depth, vendor, workers, movers:{count, direction}, stages:{fit:{start,end}, valid:{start,end}, test:{start,end}}, factor_model:{enable}, tools:[...]}` → expands **1:1 to the verified `pipeline.py` args** (no new execution path; import pipeline's entrypoint in-process).
- Ledger append (JSONL, one row/line) under `DEFAULT_CONFIG["data_cache_dir"]/experiments/` (home cache → gitignored by location): `{run_id, config_hash, params, metrics:{ic, icir, mdd, sharpe, pbo}, status: "pending"|"done"|"failed", artifact:{model, dataset_config, report_dir}}` — **raw data by path only** (design §3.9). Parallel-writer safety: O_APPEND single-line write + retry-once on partial line (Windows-safe, no new dep).
- `scripts/experiments.py` (new): read view — `--filter-metrics "ic>0.03", "pbo=false"`, `--format table|json`, `--diff <run_a> <run_b>`.
- Tests `tests/test_runfile.py`: runfile→argv equivalence via `--dry-run` vs hand-written flags; config-hash stability across reruns with identical YAML; ledger round-trip; status lifecycle; experiments filter/diff (design §8-4, §8-11).
- Acceptance: §8-4, §8-11. Commit: `feat: qlib phase 2 runfile + recorder-style experiment ledger`.

## 6. Phase 3 — point-in-time registry (design §3.5)

- `tradingagents/dataflows/pit_registry.py` (new): append-only JSONL per `(symbol, as_of)` under `data_cache_dir/pit_registry/{symbol}.jsonl`; API `store_snapshot(symbol, as_of, payload)`, `read_snapshot(symbol, as_of)`, `read_as_of(symbol, as_of)` (**masks > as_of** — reuse `date_window.to_utc`/`in_window` semantics), `put_moments(symbol, as_of, {mean,std,...})`/`get_moments(symbol)` for the §4.1 learn/infer persistence.
- **Label convention:** `markup_label(close_series) -> float | None` = `Ref(close,-2)/Ref(close,-1) − 1` (next-execution-day return with one-day buffer) — registered `(symbol, as_of)` so backtests and the factor loop never align a signal with same-day return.
- Consumers: `scripts/pre_market_review.py` (prior decision via registry, not only `full_states_log`), backtest hygiene (as-of labels), fast path (design_market_refresh_fastpath).
- Tests `tests/test_pit_registry.py`: as-of masking (record dated after `as_of` invisible — design §8-5); moments round-trip + **malicious test-window value does not alter stored train-fitted stats (§8-7)**; label math on a synthetic close series.
- Acceptance: §8-5, §8-7. Commit: `feat: qlib phase 3 point-in-time registry + label convention`.

## 7. Phase 4 — gated advisory factor model + proposal loop (design §3.6, §3.7)

- `scripts/factor_model_train.py` (new): LightGBM (already a soft dep? verify `requirements.txt` — if absent, guard `enable_factor_model` import so default path needs nothing) over `alpha158_subset` features × memory-log realized outcomes, PIT-labeled via `pit_registry.markup_label`; **OOS walk-forward via `evaluate.walk_forward_splits` + `evaluate_config_gate.gate_verdict`** (unchanged authority); output `pred_score` per name; **score becomes advisory only after the gate passes** and `enable_factor_model=True`; default False.
- `scripts/factor_proposal_loop.py` (new): LLM drafts candidate expressions from the `factor_expressions` operator menu + a "current factors / recent IC" prompt (repo LLM client — `tradingagents/llm_clients`); deterministic eval per candidate = §4.2 metrics + `gate_verdict`; emits candidate sheet (computed columns only) under `data_cache_dir/experiments/`; **gated survivors** become config-gated extra `get_factor_profile` rows (`factor_proposal_*` keys, default OFF). No RD-Agent/Docker (design §6). Hermetic tests inject the proposal list directly — no LLM call in tests (design §8-10).
- Tests `tests/test_factor_model_train.py` + `tests/test_factor_proposal_loop.py`: gate blocks ungated scores; default-OFF reachability test (with `enable_factor_model=False` no model score in any tool result); planted predictive candidate → IC row + adopt flag; random noise → honest reject; sheet has computed columns only (design §8-6, §8-10).
- Commit: `feat: qlib phase 4 gated advisory factor model + factor-proposal loop` (+ optional separate commits).
- Optional `scripts/tuner.py` (design §3.10, `enable_tuner` False): search over model params; **every candidate still passes `gate_verdict`; search finds, gate decides** (G5 authority kept).

## 8. Phase 5 — fast-path alignment (design §5 Phase 5)

- Task (docs/alignment, no runtime code until fast-path design lands): write the T0/T1/T2 ↔ DelayTrainer alignment section in `docs/design_market_refresh_fastpath.md` — T2 nightly = the delayed batch of `factor_model_train` retrains (parallel via existing `batch.py` worker pool), T1 = reuse the day's online models to refresh predictions; cadence config `fast_path_*`; still advisory.
- Commit: `docs: fast-path alignment with qlib online/routine (delay-train pattern)`.

## 9. Definition of done (per phase + final)

- Per phase: hermetic tests named above green (`py -3.12 -m pytest tests/test_<module>.py -q`), `ruff check` clean, config mirrors (`default_config.py` + `.env.example`), tools bound + re-exported + web-mirrored, docs-true set updated in the same commit, **explicit `git add` of the touched paths**, Conventional Commit, push.
- Final gate (design §8-12): full suite hermetic (timers), ruff clean, docs/README/CHANGELOG true, trading_web mirrored, everything pushed. Acceptance checklist §8-1…§8-12 is the evidence ledger — each item cites the test that proves it.

## 10. Risks & sequencing notes

- **Cross-sectional thinness** (design §6): single-name runs cannot produce panel IC — `rank_ic`/quantiles need universe runs (`pipeline.py --universe`); below min-obs, return `unavailable`, never a guess. Universe-run fixtures in tests use synthetic panels.
- **cvxpy stays optional** — scipy fallback must be the default-path solver used by tests; cvxpy path covered by one smoke test only when installed.
- **learn/infer is a two-phase landing**: Phase 1 ships the fit/apply split + moments sidecar; Phase 3 moves persistence into `pit_registry` (design §5 ordering) — do not reimplement between phases, just re-point storage.
- **`pipeline.py --alloc` is a CLI addition** the design assumes (verified absent today) — keep it flag-gated and off by default; `action_report` rendering change is the only graph-adjacent edit.
- **Ledger writers on Windows**: O_APPEND single-line writes; retry-once on partial line; no `fcntl`/portalocker dep.
- **Parallelization**: Phase-1 modules (4.1–4.4) are independent pure slices — safe to fan out to task subagents with one integration owner for tests/ + docs + web mirror (shared-boundary task); Phases 2–5 are sequential.
- **No RD-Agent, no RL, no execution layer** (design §6) — the proposal loop and model are pattern/tool adoptions only.