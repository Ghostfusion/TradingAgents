# Implementation Plan — FinRL Integration (companion to `docs/design_finrl_integration.md`)

**Status:** plan only — no code changed.
**Date:** 2026-09-02.
**Source:** `docs/design_finrl_integration.md` (the merged Qlib+FinRL roadmap; §13 says implementers follow THIS doc's rollout — the Qlib doc holds the shared design details).
**Scope:** concrete, reviewable tasks for the five FinRL net-new modules (§6.1–§6.6) plus the shared-phase extensions, mapped to exact files, verified seams, tests, config keys, and design §11 acceptance items. Phases 2–4 are **shared** with the Qlib roadmap — those foundations (§3.4 runfile, §3.5 pit_registry, §3.6 factor_model_train) are ALREADY IMPLEMENTED (commits `93ef6ad`, `38142a8`, `8cbac61`); this plan's tasks extend them, they are not net-new builds.

## 1. Ground rules (verified repo facts)

- Repo package `tradingagents/`; root `batch.py`, `pipeline.py`, `cli/main.py`; dev tools `scripts/*.py`. Tests `tests/test_*.py` with `pytest.mark.timeout` (hermetic).
- `py -3.12` only; no heredocs on Windows — `write`/`eval` for file edits (the edit tool has been intermittently injecting corrupt bytes; use byte-level `eval` repairs when that happens).
- Conventional Commits; **explicit `git add <paths>` only** — never `git add -A` (sweeps `Direction.md`, `_probe*.ps1`, `session.md`).
- Config: `tradingagents/default_config.py` `DEFAULT_CONFIG` + env map + `.env.example` mirror for every new key. Web mirror: `trading_web/backend/capabilities.py` `run_value_tools` allowlist + dispatch.
- Docs-true set (same commit): `docs/api_reference.md` §5/§6, `docs/developer/04-strategies.md`, `docs/AGENT_ONBOARDING.md`, `README.md`, `CHANGELOG.md`.
- Every new tool: `analysis_tools.py` `__all__` → `agent_utils.py` re-export → graph ToolNode (`tradingagents/graph/trading_graph.py`) → web allowlist → docs.
- No-fabrication: `float | None`, explicit `"unavailable"`, min-obs guards.

## 2. Verified seams (checked against the repo this session)

| Seam | Verified anchor | FinRL use |
| --- | --- | --- |
| Single-speed regime | `strategies/regime.py`: `realized_vol`, `vol_percentile`, `trend_strength`, `choppiness`, `regime_gate_read` | `market_stress.slow_regime` reuses price-trend/vol primitives; adds persistence + VIX robust-z + fast overlay |
| Exit suite | `strategies/exits.py`: `trailing_stop_exit`, `max_giveback_exit`, `exit_check` | `stop_policy` PositionState wraps these for absolute-priority + cooldown |
| Risk override | `strategies/risk_manager.py`: `manage_risk`, `trailing_stop_targets` | stop_policy renders cooldown rows alongside the existing override |
| Alloc zoo | `strategies/portfolio_optimizer.py`: `risk_parity_weights`, `min_variance_weights`; `strategies/portfolio.py` `allocation_block` + `value_ratio_weights` | `portfolio_contract`: equal-weight helper + MVO-adjacent min-var baseline; allocation_block consumes `allocation_strategy` |
| Qlib alloc math | `strategies/portfolio_strategy.py` `topk_drop_weights`/`enhanced_index_weights` | portfolio_contract's topk-drop/enhanced-index members (Qlib §3.3) |
| **Already-landed** | `strategies/portfolio_strategy.py`, `dataflows/pit_registry.py`, `scripts/runfile.py`, `scripts/factor_model_train.py`, `scripts/factor_proposal_loop.py`, `scripts/tuner.py` (commits 43c0ce6→8cbac61) | this plan EXTENDS, does not rebuild |
| Reviewer consumer tools | `analysis_tools.py:3855` `get_exit_overrides`, `:3978` `get_ledger_risk_state` | stop_policy adds cooldown rows to BOTH (persisted via memory log / `pre_market_ledger.jsonl`) |
| Stress context line | `trading_graph.py:1388` `_compiled_decision_context` | gains a one-line market-stress read (advisory) |
| VIX + SPX | `dataflows/fred.py:66` `"vix": "VIXCLS"`; `analysis_tools._benchmark_closes()` (SPY default) | slow_regime inputs — no new vends |
| `--alloc` seam | `scripts/value_screener.py:1282 --alloc` → `portfolio.allocation_block` (the design's earlier "pipeline.py --alloc" was corrected — pipeline has no alloc machinery) | portfolio_contract consumed here + `get_allocation_plan` (PM) |
| Report | `scripts/strategy_quality_report.py` (`build_report`) | benchmark_surface rows rendered here; `evaluate_config_gate.gate_verdict` gains baseline-relative report |
| Web | `trading_web/backend/capabilities.py` `run_value_tools` (has `ledger_risk_state`, `factor_profile`) | add `market_stress_read`; alloc strategy selector |

## 3. Dependency graph

```
Phase 1 (independent pure modules, parallelizable):
  market_stress ── stop_policy ── benchmark_surface ── portfolio_contract
   ├─ tool get_market_stress_read + context line + overlays fold
   ├─ stop_policy: extend get_exit_overrides / get_ledger_risk_state + plan card + action report
   ├─ benchmark_surface: strategy_quality_report + gate report
   └─ portfolio_contract: allocation_strategy in allocation_block + get_allocation_plan (PM)
Phase 2: runfile stage + environment_registry (extends landed runfile; uses pit_registry)
Phase 3: PIT registry — DONE (38142a8); only the FinRL datadate→tradedate acceptance corpus + consumer wiring remain
Phase 4: factor_model_train ensemble cadence (candidate zoo + OOS validation selection, gate authority)
Phase 5: fast-path alignment doc (T0/T1/T2 ↔ two-layer regime) — partially landed in the Qlib fast-path docs; add the stop-policy/turbulence cross-ref
```

## 4. Phase 1 — pure calculators (design §6.1–§6.4)

### 4.1 `tradingagents/strategies/market_stress.py` (new)
- `turbulence_index(returns_panel: dict[str, list]) -> pd.Series | None` — rolling-window Mahalanobis `(x_t − μ)ᵀ Σ⁻¹ (x_t − μ)` over the basket/benchmark panel; `numpy.linalg.pinv` robust inverse; **≥2 aligned names** (min-breadth) else None; per-date series with leading None (no fabrication). Panel source = the same basket the repo fetches for `book_risk.portfolio_cvar` (config `risk_basket_tickers`).
- `slow_regime(spx_close, vix_close, as_of, trend_ma_weeks=26, drawdown_weeks=13, dd_threshold=0.10, vix_z_threshold=3.0, persistence_weeks=2, state_history=None) -> dict` — RISK_ON/NEUTRAL/RISK_OFF from (SPX vs 26w MA, 13w drawdown, VIX robust-z); **persistence validation**: a state must survive `persistence_weeks` before flipping (caller passes prior states; module is stateless). Reuses `regime.trend_strength`/`realized_vol` primitives + FRED `vix` fetch.
- `fast_risk_off(daily_returns, shock_days=3, vol_shock_mult=3.0) -> {active, days_remaining, triggers}` — daily emergency overlay: (a) price shock = cumulative N-day move beyond N-day vol×mult, (b) vol shock = realized-vol jump; tightens immediately (no persistence) — the ESCALATE analog.
- `fold_market_stress_into_overlay(stress: dict) -> float` — advisory de-risk scale in [0,1] + verdict string; NEVER a hard REJECT beyond the existing governor.
- Config `enable_market_stress` (False) + `market_stress_*` keys: `market_stress_persistence_weeks` (2), `market_stress_dd_threshold` (0.10), `market_stress_vix_z_threshold` (3.0), `market_stress_shock_days` (3), `market_stress_vol_shock_mult` (3.0).
- **Tool** `get_market_stress_read(ticker)` — market ToolNode + 3 risk debators + a one-line `_compiled_decision_context` addition; re-export `agent_utils`; web `run_value_tools`.
- Tests `tests/test_market_stress.py`: planted covariance-shift episode → turbulence jumps; <2 aligned names → None; `slow_regime` refuses to flip before `persistence_weeks` (feed a state history); `fast_risk_off` triggers on a planted 3-day shock; fold scale bounded [0,1] (design §11-1).
- Acceptance: §11-1.

### 4.2 `tradingagents/strategies/stop_policy.py` (new)
- `PositionState` (per-symbol: entry, peak, entry_date, peak_date), `check_absolute_stop(state, price, stop_pct) -> {hit, price}`, `check_trailing_stop(state, price, trail_pct) -> {hit, price}` (delegates to `exits.trailing_stop_exit`), `check_position_stops(state, price, stop_pct, trail_pct) -> {verdict, reason, price}` — **absolute takes priority** over trailing.
- `activate_cooldown(symbol, trigger_date, cooldown_weeks)` / `cooldown_active(symbol, as_of, cooldown_weeks) -> bool` — pure date math; persistence via the existing memory log / `pre_market_ledger.jsonl` row with `kind:"cooldown"`.
- Wire: extend `analysis_tools.get_exit_overrides` (:3855) and `get_ledger_risk_state` (:3978) to append `cooldown until <date>` rows for stopped names; plan card + `action_report` render the row. Advisory only — the LLM sees state, never tightens it.
- Config: `stop_cooldown_weeks` (4) + `TRADINGAGENTS_STOP_COOLDOWN_WEEKS`; reuse `trailing_stop_pct` / `risk_manager_drawdown_pct`.
- Tests `tests/test_stop_policy.py`: absolute beats trailing (plant a state where both trigger); cooldown blocks re-entry for exactly `stop_cooldown_weeks`; `get_ledger_risk_state` renders cooldown rows against a seeded ledger (design §11-2).
- Acceptance: §11-2.

### 4.3 `tradingagents/strategies/portfolio_contract.py` (new)
- `PlanWeights` — typed result `(strategy: str, weights: dict[str, float], metadata: dict)`; **weights sum ≤ 1.0 with cash remainder documented**; no-fabrication (empty/degenerate input → None metadata note, weight dict always real).
- Uniform interface: `plan_from_strategy(strategy, scores=None, returns_by_name=None, benchmark_weights=None, w0=None, caps=None) -> PlanWeights` dispatching value-ratio (existing `portfolio.value_ratio_weights`) | risk-parity (`portfolio_optimizer.risk_parity_weights`) | min-variance (`min_variance_weights`) | **equal-weight** (new `equal_weight_weights(names)` — `1/n`, cash remainder) | **topk-drop / enhanced-index** (`portfolio_strategy` — the Qlib §3.3 math already landed).
- MVO note: a full mean-variance optimum needs expected-return estimates (noisy/advisory); the plan uses `min_variance_weights` as the MVO-adjacent baseline and documents that choice (design §6.4 speaks of "min-variance benchmarks" — honest scope).
- Wire: `portfolio.allocation_block` honors `allocation_strategy` (default `value-ratio` — **behavior unchanged**); new PM tool `get_allocation_plan(score_by_name, caps=None, strategy=None)` → single `PlanWeights` render; consumed by `scripts/value_screener.py --alloc` (existing flag) + `get_allocation` + `action_report`.
- Config: `allocation_strategy` enum + `TRADINGAGENTS_ALLOCATION_STRATEGY`.
- Tests `tests/test_portfolio_contract.py`: every strategy returns the SAME `PlanWeights` shape (sum ≤ 1.0, cash remainder documented); topk-drop/enhanced-index members pass through the Qlib math unchanged; `allocation_block` with `allocation_strategy=value-ratio` equals today's block (regression); turnover reported via `evaluate.turnover` (design §11-3).
- Acceptance: §11-3.

### 4.4 `tradingagents/strategies/benchmark_surface.py` (new)
- `benchmark_rows(buy_hold_close, equal_weight_rets, mvo_rets, strategy_rets) -> {cum, ann_ret, ann_vol, sharpe, maxdd, calmar}` per line (reuse `evaluate.cagr/volatility/sharpe/max_drawdown/calmar_ratio` + `equity_curve`).
- Wire: `strategy_quality_report.build_report` renders the strategy **vs** passive buy-hold / equal-weight / min-variance rows **always** (a raw single curve is never the deliverable); `evaluate_config_gate` output gains a baseline-relative note (PBO/DSR is already absolute — add "vs equal-weight" line).
- Baseline inputs: buy-hold = the benchmark/SPY close series (`_benchmark_closes`); equal-weight = `equal_weight_weights` returns over the same window; MVO-adjacent = `min_variance_weights` returns.
- Always-on pure calc (no config flag).
- Tests `tests/test_benchmark_surface.py`: rows render for planted series; calmar/maxdd math vs `evaluate`; degenerate (short) series → honest None per cell (design §11-4).
- Acceptance: §11-4.

### 4.5 Phase-1 integration task (one owner)
- Tools re-exported + ToolNodes (market node gains `get_market_stress_read`; PM node gains `get_allocation_plan`); `get_exit_overrides`/`get_ledger_risk_state` cooldown rows; `_compiled_decision_context` stress line; `allocation_strategy` config + `.env.example`; trading_web: `market_stress_read` in `run_value_tools` + alloc-strategy selector; docs set; ruff + full hermetic suite; commit `feat: finrl phase 1 pure calculators (market stress, stop policy, contract, benchmark surface)`.

## 5. Phase 2 — runfile stages + environment registry (design §6.5)

- **Extend** `scripts/runfile.py` (landed): YAML gains `stage` (train/test/trade date windows — FinRL 2: agent never sees test/trade data at train time) and `environment` (named context) sections, expanding 1:1 to existing flags — no new execution path. Stage windows feed the learn/infer split (pit_registry moments) so a staged run fits normalization on `stage.train` only.
- **New** `tradingagents/dataflows/environment_registry.py`: named market contexts (`US-megacap-tech`, `US-basket`, `HK-large-cap`, `crypto`) = `{universe, asset_type, exchange, benchmark_ticker, data_vendors preset, session_flags}`; registry read view (list/resolve by name); referenced by runfile `environment:` + web Jobs presets. Also documents the low-vs-high-frequency missing-data policy mapping to the look-ahead guard (FinRL 1: low-freq drop suspended rows; high-freq ffill close + volume 0 — a doc note, not a code gate).
- Tests `tests/test_runfile_stages.py`: runfile with stage+environment → identical argv to the same flags; environment resolution errors → clear message; stage windows present in the ledger params row (design §11-5).
- Acceptance: §11-5. Commit: `feat: finrl phase 2 runfile stages + environment registry`.

## 6. Phase 3 — PIT registry (SHARED, mostly landed)

- `dataflows/pit_registry.py` is DONE (commit `38142a8`): as-of masking (§8-5), moments persistence, `markup_label`. Remaining FinRL tasks:
  - Add the FinRL-X `ML_STOCK_SELECTION.md` worked example (datadate→tradedate mapping, uniform membership filter at train AND inference, y_return verification) as the acceptance-test corpus: `tests/test_pit_registry.py` gains a datadate→tradedate alignment case + a train/inference membership-uniformity case.
  - Consumer wiring: `pre_market_review` reads the prior decision via `read_as_of` (currently `full_states_log`); backtest hygiene as-of labels.
- Acceptance: §11-6. Commit: `test: finrl pit-registry datadate→tradedate corpus + pre_market consumer`.

## 7. Phase 4 — factor-model ensemble cadence (design §6.6, extends `scripts/factor_model_train.py`)

- **Candidate zoo**: extend the model builder to produce N variants (ridge alphas ×(optionally lightgbm depths when installed) over Alpha158 + FinRL-52 feature-names; FinRL's 52-factor list is a reference pool, Alpha158 subset is the actual computed pool — the doc says "cite FinRL's factor list").
- **OOS validation selection**: `tuner.search_grid` already ranks alpha candidates by walk-forward OOS Sharpe; selection = best **gated** candidate (gate authority = `evaluate_config_gate.gate_verdict`), **never in-sample argmax**; rolling re-train at rebalance windows (FinRL 9).
- **Baseline-relative report**: every candidate is reported vs equal-weight / value-ratio / momentum on the same IC + backtest surface (`benchmark_surface` + `signal_analysis` combine to provide the surface).
- Gate unchanged: score reaches the LLM only after walk-forward+PBO; `enable_factor_model=False` default.
- Tests `tests/test_ensemble_cadence.py`: planted predictive zoo → the best OOS-validated candidate selected, never the in-sample best when they differ; ungated candidates never advisory; baseline rows present (design §11-7).
- Acceptance: §11-7. Commit: `feat: finrl phase 4 factor-model ensemble cadence (candidate zoo, OOS selection)`.

## 8. Phase 5 — fast-path alignment (doc; cross-refs)

- Extend `docs/design_market_refresh_fastpath.md`: T0 gate = `market_stress.slow_regime` persistence check (HOLD/UPDATE/ESCALATE = regime persistence + `fast_risk_off` escalation); stop cooldown rows feed the T1 re-decision (a stopped name stays cool during intraday refresh); turbulence index = the T0 market-wide tail read. Still advisory; `fast_path_*` cadence keys.
- Commit: `docs: fast-path aligned with finrl two-layer regime + stop policy`.

## 9. Definition of done (per phase + final)

- Per phase: hermetic tests named above green (`py -3.12 -m pytest tests/test_<module>.py -q`), ruff clean, config mirrors (`default_config.py` + `.env.example`), tools bound + re-exported + web-mirrored, docs-true set updated in the same commit, explicit `git add` of touched paths, Conventional Commit, push.
- Final gate (design §11-8): full suite hermetic, ruff clean, docs/README/CHANGELOG true, trading_web mirrored, pushed; acceptance §11-1…§11-8 evidenced by the named tests.

## 10. Risks & sequencing notes

- **Turbulence noise** (design §9): Mahalanobis over short panels is unstable — min-breadth guard (≥2 aligned names), robust `pinv`, advisory-only fold; the module degrades to None, never a guess.
- **Persistence lag**: slow regime flips slowly by design; the fast overlay covers emergencies; both advisory. Tests must drive the state history explicitly (no hidden cross-call state — stateless module, caller passes history).
- **Cooldown cost**: a cooldown can miss a genuine re-entry — advisory rows only, configurable weeks, applied only when a plan references it (never silent).
- **MVO honesty**: no expected-return estimator — the "MVO" baseline is min-variance; document the substitution in the module docstring and the docs-true set (no fabrication).
- **Landed-vs-new**: phases 2–4 extend shipped code — do not re-implement the base (`runfile.py` argv expansion, `pit_registry` masking, `factor_model_train` gate) — only add the FinRL sections/selection. Reviews should diff against the landed commits (`93ef6ad`, `38142a8`, `8cbac61`).
- **Parallelization**: Phase-1 modules (4.1–4.4) are independent pure slices — fan out to subagents with one integration owner for tools/docs/web; Phases 2, 4 sequential; Phase 3 test-only; Phase 5 doc-only.
- **No RL runtime, no execution layer** (design §9): every module is a pure calculator or advisory row behind the existing overlays; nothing learns a policy in the default path.