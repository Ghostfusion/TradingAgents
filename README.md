<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>
<br>
<div align="center">
  <a href="https://github.com/TauricResearch" target="_blank"><img alt="TradingAgents #1 Repository of the Day" src="https://trendshift.io/api/badge/repositories/16192" width="250" height="55"/></a>
</div>
<br>
<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-10-05] **The trade-plan card now measures three rows it used to leave `unavailable`.** `technical_entry_price` comes from the same close-series support the card's own §103 support row is built from (so the two agree by construction); `execution_price` and `liquidity_adjusted_entry_price` come from the repo's own Corwin-Schultz/Abdi-Ranaldo spread over the verified OHLCV bundle (a fraction, so no foreign price scale can leak in); `fair_value_price` and `fair_value_target` come from the DCF, guarded by the same >5x data-quality check `get_dcf_valuation` applies and memoised so the pre-graph card and every tool call share one statement read. The DCF is deliberately **not** also wired as §100's valuation anchor/ceiling — it returns 0.10x of price for VST, which would collapse the card's headline entry price. Web impact none.
- [2026-10-05] **The report's entry/exit block stops printing design-document section numbers.** `3_trading/trader.md`, `5_portfolio/decision.md` and `complete_report.md` rendered every member reason with its citation — `- execution_price: unavailable - §74-§78: …`, `§58: …`, and `§103`/`§101` in the heading and predicate label. They now read `- execution_price: unavailable - the price this run could realistically pay`, `held past its holding horizon`. The strip lives in `render_entry_exit_block`; the member strings are data that `research_decision.json` publishes, so they keep their citations untouched. Web impact none.
- [2026-10-05] **A second decider: Perplexity's `pplx-decider-v1-27b`, run after the TypeSafe verdict.** New gate `enable_pplx_decider` (off by default), writing `pplx_verdict.json` beside `jev_verdict.json` — same `/api/alpha/decisions` endpoint, same battery and position neutralisation, only the model differs. (The route its model page advertises, `/api/v1/decisions`, is a 404 — probed.) Model overridable via `TRADINGAGENTS_PPLX_DECIDER_MODEL`. Web impact none.
- [2026-10-05] **The TypeSafe judge is configurable from `.env`.** `TRADINGAGENTS_JEV_MODEL` / `TRADINGAGENTS_JEV_ENDPOINT` / `TRADINGAGENTS_JEV_TIMEOUT` now drive `tradingagents/jev.py`'s defaults, previously hardcoded literals — so the verdict model or host changes without a code edit. Unset/blank keys keep the old values; an unparseable timeout refuses at import. Web impact none.
- [2026-10-04] **The books backlog closes — the last nine §3 items.** Conservative choices throughout: `purged_cpcv_splits` defaults to a one-bar embargo (C2); `regime_stability_check` + its gate report (C3); C7 keeps the IID conformal band as the byte-identical gate-off default (its under-coverage stated in-module, the block interval the option); `var_coverage_test(simulate=True)` finite-sample p (C9); `extreme_quantile_var` echoes its threshold (C10); `copula_scenarios` reports `model_risk` (C11); declared impact shapes + preferred square-root (C13); one `PARTICIPATION_CAP = 0.10` (C14); `kyle_lambda(direction="lagged")` (C15). Web impact none.
- [2026-10-04] **The books backlog continues — Batch C: seven additive §3 methodology items, a refutation, and a crash fixed on sight.** All opt-in, defaults unchanged: `deflated_sharpe(n_effective=…)` (C4), `rv_forecast(log_rv=True)` (C5), `memory_parameter(on_volatility=True)` (C6), `var_cvar_horizon(tail_index=…)` (C8), `kelly_weights` on the Ledoit-Wolf covariance (C12), `correlation_matrix`'s excess-kurtosis read (C17), `ols_factors(hac=True)` (C18). **C16 refuted** — the OHLC forward-fill is already counted and logged. `memory_parameter` no longer crashes on a constant series (refusal instead). Web impact none.
- [2026-10-04] **The books backlog continues — Batch B: CSCV PBO, forecast scoring producers, the MZ regression, the pool combination arm, and Ledoit-Wolf in the allocator.** Six survey-owned E-items, all additive and outside the frozen forecasting contract (§11.0): `evaluate.cscv_pbo` (a probability over the candidate × period matrix, `S=8`, reported by the gate as `pbo_probability` and used for the verdict); `calibration.mz_regression`; the `forecast_scores` module (`rmse`/`mae`/`qlike`/`crps` behind `SCORING_RULES`); `forecast_registry.equal_weight_combination`; and Ledoit-Wolf shrinkage as the allocator's default covariance. E13 (Yang-Zhang in the vol tool) was **refuted** — already built. Web impact none.
- [2026-10-04] **The paper-reading backlog resumes — Batch A: a cost-floor precondition, a regime sign test, a per-event-class sentiment half-life, and a Marchenko-Pastur i.i.d.-premise check.** The owner authorised the whole remaining `Strategies/books/` backlog; each item was re-verified against the live tree first. `scripts/evaluate_config_gate.py` now refuses a gross-edge significance verdict when the series' mean return is under a supplied round-trip cost (E5); `regime_conditioned_performance` carries a distribution-free per-regime sign test (E10); `sentiment.aggregate_weighted_sentiment` resolves each article's declared per-event half-life (E11); and `market_breadth.mp_iid_premise` reports whether the panel satisfies the MP band's i.i.d. premise (E12). All additive; web impact none.
- [2026-10-04] **The pipeline itself can now be falsified against synthetic nulls — H3's offline harness — and the familywise inflation of a search is measured.** `strategies/falsification.py` falsifies a *thesis*; nothing falsified a *pipeline*. H3 (paper `2604.15531`) runs a workflow's walk-forward winner over five reference classes (white noise, two-state regime-switching volatility, a bid-ask-bounce price bar, a single mean-zero factor plus noise, GARCH(1,1)) at `N = 1000` replays each, and calls a reported winner above the environment's empirical `(1-alpha)` quantile a **false positive** — it found signal in data built to hold none. `tradingagents/strategies/null_harness.py` owns the generators and the band; `evaluate.z_statistic` / `inflation_diagnostics` (beside `walk_forward_splits`) own the HAC z, `Delta_Z = Z*_IS − Z*_WF` and `K_eff`; `scripts/null_harness.py` is the offline caller. The paper's headline — **5.3% familywise false positive at K=1, 92.3% at K=50** — travels in the output. Measured at seed 0: the honest pipeline rejects at ≈ alpha (3.5–7.0%), a seven-candidate search at 22.5–41.0%. The failing-first proof puts one white-noise sample through both, honest inside / leak outside. 12 new tests; web impact none.
- [2026-10-04] **The D3 gap register is empty: all 38 verified wiring gaps land, and the gate that found them passes clean.** `Strategies/books/FINDINGS.md` §7's register held 37 reads with no wired equivalent (the 38th, `max_pain`, landed earlier the same day); every one is now a real call reaching its consumer's output, and `GAP_CALCULATORS` is emptied. The four `domain_bundles` composites became tools bound to the market / fundamentals / news analysts and the risk debators; 21 calculators joined the `analysis_tools` tool that should have carried them — the regime drill-down gained the stress composite / relative-vol / up-down-beta reads, the factor profile the learn/infer normalisation (and the PIT label beside its fitted moments), the signal-quality read the IC-decay and prediction-autocorrelation lines, the mean-reversion read entropy and the long-memory profile, the sentiment depth emitter SENT-8/9/10, the technical score its state and disagreement rows, and the risk score its triadic-stress row. The monitor / ledger / reflection chains had stopped at a config key: falsification breaches now record **and** alert, the prediction ledger carries the quant-only baseline beside the LLM rating, and a recorded analyst reflection reaches the pre-graph context. And the debate's R2' divergence rule is now applied through its producer instead of only stamping an alpha. Gate: `tests/test_calc_agent_wiring.py` → **117 passed**.
- [2026-10-04] **The paper reading's backlog starts landing: a two-observation covariance, a silent forward-fill, the missing MinTRL, unlabelled lead/lag rows, and the paired significance tests H4's own card named.** Each was verified against the live tree before being taken — and one was **refuted**: `FINDINGS.md` §3 said the volatility publisher "labels it `har_rv.ols.v1` without disclosing the target", but the registry row's `TargetRef.definition` names the squared close-to-close regressand with `unit="variance"` and the publisher passes it into every record, so that half is recorded in §5 rather than implemented. **`portfolio_optimizer._covariance_matrix` accepted as few as two observations**, and because a centred sample covariance over `n` rows has rank at most `n - 1`, the two callers that never invert (`risk_parity_weights`, `risk_contribution`) reported confident allocations from rank-deficient input; the floor is now the repo's own declared covariance floor, **imported** from `covariance_models` so it cannot drift. **`_clean_dataframe` forward-filled OHLC gaps silently**, so a downstream volatility read could not tell a carried-forward bar from a measured one; it now counts and logs what it invents. **`min_track_record_length`** adds Bailey & Lopez de Prado's MinTRL, verified against the paper's three published examples (daily 2.73 y, weekly 2.83, monthly 3.24). **Lead/lag rows carry a `relation` label** and the tool calls out a strongest cell that is not a lead. **`excess_accuracy` gains paired McNemar + Diebold-Mariano** on the same per-row miss object, with the fold p-values corrected by one extracted Benjamini-Yekutieli producer that H6's family also reads.
- [2026-10-04] **All five defects the paper reading surfaced are fixed — and the biggest one was 20× larger than the reading thought.** `Strategies/books/FINDINGS.md` registered D1-D5 as owner decisions; the owner took the class-level route and authorised the rest. **D3:** `tests/test_calc_agent_wiring.py` counted an `__all__` entry as a *use* and matched substrings — so `max_pain` passed on the retired `max_pain_dist_atr`, and `tail_risk` passed on 55 docstring hits with no call site anywhere. Corrected, the gate surfaces **115 of the 1,399 public calculators in scope (8.2%)**, not six. They are now declared **by class** — `ADVISORY_CALCULATORS` (`reference` / `dead`) for the deliberate ones, `GAP_CALCULATORS` for the verified wiring gaps with the consumer that should own each — and a guard refuses a stale or misspelled declaration, so the gate means what it says again. `derivatives_gamma.max_pain` is the first gap wired, into `get_gamma_profile`. **D1:** `evaluate.deflated_sharpe_ratio` applies the Bailey–López de Prado Eq. (2) in **per-observation** units (the paper's own scale) by composing `probabilistic_sharpe` with the selection threshold; the legacy difference keeps its bit-for-bit promise and now states the unit caveat. **D2:** the G5 gate reads N and V back from the trial ledger whenever `enable_trial_ledger` is on. **D4:** `SURVIVOR_ONLY` finally reaches a findings record — `coverage_window.universe_label()` + the `score_panel` record's `universe_label`. **D5:** `regime.sticky_markov` (the benchmark the registry declared and nothing implemented) now exists, is bound through `forecast_registry.BENCHMARK_IMPLEMENTATIONS`, and a bound ref that does not resolve fails a build — landed as a numbered design revision.
- [2026-10-04] **The 4,372-paper `E:\fin paper` corpus is read, categorised and registered as `Strategies/books/` — and the reading found two documentation defects.** Three passes: all 4,372 papers classified into 19 multi-label categories from title+abstract; an **abstract-level sweep of every one of the 4,372**, one annotated row per paper (takeaway, candidate repo surface, relevance grade), so nothing is unaccounted for; then 19 book documents, each reviewer reading its category's best papers in full text and verifying every repo symbol it names before claiming a `shipped`/`partial`/`absent` status. The library is `README.md` (taxonomy, method, limits), `01-…19-*.md` (one per category — start with **01 LLM & Agentic Trading Systems**, **02 Backtest Methodology & Overfitting**, **03 Data Quality**), `CORPUS_INDEX.md` (all 4,372 papers), `evidence/<slug>.md` (the sweep rows per category, verbatim) and **`FINDINGS.md`** (the consolidated defect register: 2 fixed, 5 needing an owner decision, a methodology backlog and 15 enhancement items, each row marked `[verified]` or `[reported]`). **`docs/design_fin_paper_survey_26.md` + `docs/paper_survey_26/` already surveyed the 309 `26xx` papers of this same corpus and remain the authority for them** — this library adds the 1997–2025 tail, a complete index, and per-paper sweep rows; the overlap is named explicitly in the books `README.md` §6. Fixed on sight, both docstring-only: `strategies/rnd_recovery.py:1` cited a placeholder id `(V3, 2512.xxxx)` — now the real `(V3, 2607.27188)` — and `strategies/market_session.py:336` documented an order-imbalance ratio its own code contradicts.
- [2026-10-03] **The forecast record can now be published — and it refuses to be faked — which unblocks FL-5.** FL-5 was deferred because no producer emitted the mandatory `Provenance`; **FL-9** is that producer. `tradingagents/strategies/forecast_publisher.py` reads its identity out of the registry row (so a record and the registry cannot drift) and fills all fourteen provenance fields from real sources — `data_snapshot_id` from `prompt_metrics.snapshot_identity`, `adjusted_prices` from `market_router.price_caliber_for` asked about the loader's actual source, `parameter_hash` over the regressor set and the fitted coefficients, `code_revision` from `execution_contract.git_sha()`. An absent or unstatable identity **refuses** (`PublishRefusal`) instead of defaulting: `price_caliber="unknown"` has no honest boolean, so nothing is published. `prediction_ledger.record_forecast`/`evaluate_forecast` are append-only with the evaluation in a **separate tagged row**, so the record row is byte-identical after an evaluation lands (verified by sha, live). The caller is `scripts/forecast_ledger.py` — offline, because ground rule 8 forbids the decision path and the in-run path cannot state a price caliber at all.
- [2026-10-03] **The forecast contract, its registry, its cited refusals, its dependency-admission gate, its benchmark declaration and V1's bind land — FL-1 + FL-2 + FL-3 + FL-4 + FL-6 + FL-7 of the frozen forecasting design.** Two declaration-only modules (`tradingagents/strategies/forecast_contract.py`, `.../forecast_registry.py`), a test-only admission gate, twenty-four tests, and one policy bind. The contract turns §7.2's rules into constructor errors rather than review comments: a refusal can never carry `0.0` (`value is None` iff `status != "ok"`), `interval` is all-or-nothing and carries no `realized_coverage`, `horizon_steps >= 1` so a state read cannot occupy the forecast namespace, `producer_id` (stable owner) is distinct from `implementation_ref` (current location), and provenance is mandatory with `padded`/`data_snapshot_id`/`calendar_id` defaulted by nothing. `ForecastRecord` has **no** evaluation field, and `ForecastEvaluation` needs a terminal only the prediction ledger holds, so the invariant — *a forecast cannot change because a later evaluation changed* — is structural. The registry declares **one authoritative producer per `(target, scope, frequency, horizon)`**: `rv_forecast` for `realized_volatility · single_asset · 1d · 1` (unit `variance`) and `market_breadth.forward_stress_probability` for `regime_stress_probability · index · 1d · 21`, every `implementation_ref` resolved through `importlib` in the suite so a renamed producer fails a build. Two of the plan's seed rows were dropped and the regime anchor corrected — those producers *measure the present*, and a state read is not a forecast. `absolute_return` and `return_rank` ship **`declined`** rather than omitted: cited policy statements (`RETURN_LEVEL_NOT_ADMITTED` after Hjalmarsson 2006 and Goyal/Welch/Zafirov; `RETURN_RANK_NOT_ADMITTED` after 2607.27461's 0.007 against the volatility rank's 0.108) that name no producer and are never scored — an absent key would be an invitation. `tests/test_forecast_dependency_admission.py` then makes admission evidence-based and **measures** that today's net dependency change is zero: `pyproject.toml` installs no forecasting extra, an unlisted one is flagged, a `CONDITIONAL` row must name the FD-1 clauses and benchmark that would admit it, and every row declares a licence tier (`default`/`osi_review`/`custom_review`, or `unverified` when the licence was not read from source — the *policy* question is the owner's open call). And a forecast gets no credit for producing a number: `BENCHMARK_BY_FAMILY` maps every target family to the benchmark it must beat (HAR-RV + naive trailing for volatility, **three** baselines for `absolute_return`, persistence + rank-neutral for the ranks, sticky Markov for the regimes, `conformal.iid_interval` as the interval floor), `benchmark_ref` is mandatory on every non-`declined` row, and the two ceilings — `2602.07841`'s out-of-sample R² and `H4`'s base rate — bind every directional family. **No dependency and no gate is added.** V1's own card in `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md` now names its admission path (FL-7) and decides none of it: offline-refit artefacts only, the pool's members are FD-1 §3.2 *candidates*, and `GARCH(1,1)-t`/`FIGARCH(1,1)-t` still have no supplier. FL-5 is deferred to the first producer that can publish a record: no producer emits one today (the chain head is V1's blocked pool), and `Provenance` is mandatory, so wiring the ledger anywhere now would be a stub over an unpopulated state key.
- [2026-10-03] **The research↔execution contract's authoritative side is settled — and settling it exposed a 100× sizing defect in the executor.** `tests/test_execution_contract.py::test_the_vendored_copy_matches_the_executors_published_schema` had been failing: this repo's `contracts/research_decision.v1.schema.json` carried an owner edit (`minimum: 0, maximum: 100` plus a description on `recommended_allocation_pct`) while `../TradingExecution/contracts/` still held the unconstrained form. The owner designated **this repo's copy authoritative**, so the executor's was synced and the guard is green again (26 passed, was 1 failed). The settlement surfaced a real defect on the executor's side: `signald/schema.py::build_signal_contract` converted `recommended_allocation_pct` from percent to fraction **only when `pct > 1.0`**, so every allocation in **(0, 1] percent** was read as a fraction — `0.5` (0.5%) became `0.5` (50%), deriving a $50,000 notional on a $100,000 book — and the per-order cap answers an over-cap notional by *shrinking to the cap*, so a 0.5% instruction could size as a cap-sized order. Fixed there with a failing-first test (`0.5% → 0.005`, `$500`); that repo's suite is 1139 passed. The unit had been undecided because the two fields legitimately differ: `recommended_allocation_pct` is **percent** (0..100 — the contract's declared domain; `agents/schemas.py` declares `ge=0, le=100`, and the owner's in-flight `reporting.py` change publishes the measured size into it, ×100 and clamped 0..1 → 0..100, while **at HEAD the field was still always `None`**) while `position.size_pct_book` is a **fraction** (`0.0242`) — and only the first is documented in the schema, a gap reported rather than annotated since that file is the owner's contract. Also recorded: the owner ratified that `absolute_return` and `return_rank` **ship as `declined` rows** in the forecast design (`docs/design_forecasting_libraries.md` §11.1). No tool, gate, config key or JSON key name changed.
- [2026-10-03] **The forecasting-layer evaluation: the model families were already here, so what gets adopted is a declaration rather than a dependency.** An external proposal recommended a time-series forecasting stack (`StatsForecast + MLForecast + arch + statsmodels + hmmlearn + ruptures`) plus a horizon-keyed `ForecastContext`. Evaluated against the tree: GARCH/ARCH, HAR + semiparametric long memory, HMM regime, change-point, conformal intervals, RND recovery, eigenspace rotation and the jump-robust proxies are **already shipped, gated and tested**, so a library there would be a second producer of a number this repo already computes (invariant 8). The one open item is V1's forecast pool, and its block is the **vendor state vector** (`VXV` + a HY-spread series), not a library — so `statsforecast`/`mlforecast` are recorded `CONDITIONAL` (offline refit only) and the rest declined. Verified from each project's source, four of the proposal's framing assumptions are wrong: `statsforecast` is a compiled C++ extension whose hard dependency is `statsmodels` (not numba); `arch` is **NCSA**; `mlforecast` needs `scikit-learn` + `optuna` (LightGBM/XGBoost are extras); and `StatsForecast`'s `GARCH` is implemented in-house, emitting `{"mean","sigma2"}`. What is adopted is a **`ForecastRecord` declaration** — a refusal can never carry `0.0`, production metadata is kept separate from post-hoc evaluation, one producer per key — with `return_forecast` shipped `declined` and a dependency-admission test. No dependency, no gate, no code. Two doc-truth defects fixed in the same pass: the `docs/paper_survey_26/` "verified" tables had drifted (8 of 10 rows, and 8 rows) and `design_vol_surface_and_vrp.md` §3 still called V2–V6 gaps after they had shipped. See `docs/design_forecasting_libraries.md`, `docs/implementation_plan_forecasting_libraries.md` and `CHANGELOG.md`. **Revised to v1.1 after review:** v1.0 had turned "no authoritative return forecast is admitted" into "returns are not forecastable" (only the first is defensible — the rule is now an *authorization gate* naming the benchmark that would admit one), required `realized_coverage` in the forecast interval where it cannot exist (production metadata is now split from a post-hoc `evaluation` block filled by the prediction ledger), and admitted `horizon=0` state reads into the forecast namespace (a state read is not a forecast). The return family is split into `absolute_return`/`relative_return`/`return_rank`/`residual_return`; admission is now evidence-based rather than capability-based (**FD-1**, five clauses, plus a mandatory per-family benchmark); the contract gained `target`, `frequency`, `forecast_origin`, richer provenance and machine-readable `reason_code`s; and the rejection reasons are categorized. Foundation models are `REJECT_THIS_PASS` rather than a class verdict — verified: TimesFM's source and ≤2.5 weights are Apache-2.0 but its **3.0 weights are non-commercial** ("commercial or production use of downloaded / self-hosted weights is not permitted"), while `chronos-forecasting` is Apache-2.0. **Revised to v1.2 after a second review:** the contract is now **three objects** — `CandidateForecast` (a pool member, never authoritative), `ForecastRecord` (production-time **immutable**, with *no* evaluation field) and `ForecastEvaluation` (post-hoc, appended by the ledger) — because v1.1 claimed immutability while mutating the record, and that split is what makes *"a forecast cannot change because a later evaluation changed"* true. Candidate outputs are formally separated from the one authoritative producer, which is what makes V1's pool legal under invariant 8; `forecast_origin` is corrected to "when all information available to the forecast is frozen"; `interval` is optional and all-or-nothing; and the StatsForecast/V1 model claim was verified **down** — `statsforecast` ships `GARCH`/`ARCH` with **no Student-t and no FIGARCH**, in-house `garch11_fit` is **Gaussian**, and `arch` lists FIGARCH only under *Contributing*, so V1's `GARCH(1,1)-t` / `FIGARCH(1,1)-t` members have **no supplier anywhere**. One review claim was **refuted from source** (`statsforecast` builds with `scikit-build-core`, not setuptools) and is recorded rather than complied with. **The design is declared FROZEN at v1.2**, with an explicit governance boundary (`§11.0`): the frozen surface is the contract, FD-1, capability-vs-quantity ownership, one authoritative producer per key, forecast ≠ score ≠ signal ≠ decision, the post-hoc evaluation boundary and the library verdict categories; the four remaining owner items (licence-tier default, `declined` vs `not_admitted`, V1's unsupplied `-t`/FIGARCH members, V1's vendor unblock) are **downstream implementation/owner decisions** that FL-1…FL-7 do not depend on, and **any decision that would change FD-1, the contract's semantics or authoritative ownership requires a numbered design revision** rather than an edit inside an implementation item.
- [2026-09-30] **The trade plan card now carries §103's ENTRY *and* EXIT blocks whole — the Trader and the PM finally read an exit price.** `trade_plan.build_trade_plan` has called `entry_exit_price` since Phase 6, but it passed **no exit argument** and then **discarded the assembled `exit` block**, so `exits.exit_decision` (which has no other caller in the repo) never ran for a plan. That card is the single string the Trader, the PM, the three risk debators, the RM and the bull/bear researchers read, so every one of them was arguing an exit without one. The card now feeds the assembler the two §101 inputs it can measure — the trailing level from the trail read (`trail_ema`'s EMA20, or the chandelier) and the plan's final tier (T2, else T1) as the target — and renders the §103 EXIT block: the predicate, every evaluated condition, `coverage N/7`, the levels with their sources, the §101 precedence, and the four exits that are **not** decidable at plan time named as *absent, NOT "no exit"*. The entry side now lists each §100 term's value behind the `min`, not just the binding name. Live: `coverage 3/7`, `trailing_stop 104.98 (EMA20)`, `target 108.94 (T2)`.
- [2026-09-29] **The annual-series reader now reads the shape the statements actually carry — the SBC-adjusted FCF stops being refused.** `ratios._series_entry` demanded the `{"values", "years"}` mapping that `annual_series`/`sec_annual_series` *return*, while `fetch_ticker` stores a series as a **bare list of floats**, so every SEC/vendor series attached to a canonical `fin` was silently rejected. Found on INCY: the run's own EDGAR table carried 17 annual `Share-based compensation` values ($249,346,000 in FY2025) while `get_quality_factors` printed *"no us-gaap:ShareBasedCompensation value for this filer"*. After the fix (measured live): `sbc=249,346,000`, `sbc_adjusted_fcf=1,105,282,000` (18.41% below reported FCF), `sbc_to_revenue=4.85%`. The same reader feeds `compute_ratios`' growth/deterioration series legs, which now light up as built. No tool, flag, gate or JSON shape changed.
- [2026-09-28] **The interactive CLI's report tree now carries the same post-run artefacts as a batch
  tree** — `cli/main.py::save_report_to_disk` writes its tree with `write_report_tree` directly, so it
  never went through `batch.analyze` and ran neither post-save hook. It was the one producer whose trees
  lacked `jev_verdict.json`, against the owner's instruction that the verdict is written each time a
  report has finished generating. Measured, not inferred: `reports/TROW_20260928_124933` and
  `reports/PBR_20260925_142907` are 9-entry trees against 10 for every batch tree, and both record the
  same `commit` as the batch trees written the same day — so the difference was the entry point, not the
  code. The shared dispatcher is now public (`batch.py::post_save_annotations`, renamed from
  `_post_save_annotations` because it has a caller in another module), the CLI's writer calls it after
  writing, and a caller with no trade date skips the pre-market check rather than writing
  `pre_market_review_None.md`. A recorded backlog row — "`pipeline.py` never writes a jev verdict" — was
  **stale**: `pipeline.py` calls `batch.analyze`, which has run the hook since 2026-09-21, and no
  `pipeline_<stamp>.md` exists anywhere, so it has not produced a recent tree at all. Still open:
  `trading_graph.py::save_reports`, the writer for ad-hoc `propagate()` + `save_reports()` calls,
  annotates nothing. Live proof (a copy of the TROW tree went 9 -> 10 entries) and web impact in
  `CHANGELOG.md`.
- [2026-09-27] **ValuationScore row 55 gets its producer, and the Dream-RSI replay simulator is declined
  on the record** — two items that needed a producer or a written decision rather than a wiring pass. The
  **SBC-adjusted free-cash-flow read** (`us-gaap:ShareBasedCompensation` -> the canonical `sbc` key) now
  exists as `strategies/ratios.sbc_adjusted_fcf`: `reported_fcf = OCF - |capex|` beside
  `economic_fcf = reported_fcf - SBC`, plus `SBC/revenue` (the quality-pillar ratio the round-3 composite
  study names). The read renders in the fundamentals analyst's quality-factors leaf, which fetches the SEC
  XBRL series; the plain ratio block reads the *vendor* statements, which carry no SBC row at all (live
  MSFT 2026-09-27: D&A and the working-capital legs are itemised, the SBC add-back is not), so the four
  keys stay engine-only there instead of printing four permanent `n/a` lines. It is a **single named XBRL
  concept, and a filer without it refuses with a
  reason** - never a zero adjustment: measured live 2026-09-27, 55 of 60 large US filers carry
  `us-gaap:ShareBasedCompensation` (MSFT FY2026 12.405B, SBC/revenue 3.74%; CVX files none and refuses),
  and the nearest alternative, `us-gaap:AllocatedShareBasedCompensationExpense`, is a *different quantity*
  (SIMO FY2025 26,283,000 vs 203,305,000), so it is deliberately not substituted. Not all filers are
  fully covered at the reference year: NVDA carries the SBC row but no current capex tag, so it prints
  SBC and SBC/revenue and refuses the FCF adjustment with the reason. **Dream-RSI**: `docs/design_dream_rsi_replay_simulator.md`
  §8 records the decision - the replay simulator is **declined**, because a recorded tree here is a chain
  (one trajectory per analyst), the rounds are not recorded (and the `tool_evidence.json` leaves carry a
  *duration*, not a round, so the study's own Phase D aimed at the wrong artifact), the tool-call journal
  has no reader anywhere in the repo or the web app, and offline policy evaluation has no counterfactual
  support from one trajectory per decision. It names the three preconditions (sibling branches on record,
  a round index in the report tree, a measured cost term) that would have to exist first. Details, tests,
  mutation proofs and web impact in `CHANGELOG.md`.
- [2026-09-26] **The six engine findings from the score trace are fixed - and two of the six were a claim
  problem, not a code problem** — a read-only trace of how RegimeScore, EventScore and RiskScore reach a report
  turned up six things worth fixing. The one that mattered most: the quant scorecard's `event` row read
  `EVENT_NO_SNAPSHOT` on **every** run (the snapshot is built before the graph, and the row never received the
  forward-calendar answers), so one `run_card.json` carried a measured `event_state` block beside a scorecard
  block that said the engine was never measured. `quant_scorecard` now takes `calendars=` and honors
  `enable_event_calendars`, and the new `with_event_entry` fills the row from the run's own catalyst overlay -
  returning a copy, so the debate's pre-graph snapshot keeps the reason it was read with and the composite
  cannot move (`event` is not a composite input). R3's `spectral_change` leg, declared under
  `enable_spectral_null_band` and fed by nothing, now reads its two rolling windows off the run's shared S&P 500
  panel; `events.expected_drift_after`, exported, unit-tested and called by nothing, now prints the post-event
  drift over the play's own window in the news analyst's earnings read. The remaining findings were claims: the
  VIX term-structure leg has been live since P0-5 (Cboe's own VIX9D/VIX3M index history) while `regime_score.py`
  called its data source absent, and `toolsets.py`'s docstrings promised that gated engine tools are bound to
  analysts when their gate is on - **no engine leaf is bound to any toolset at any gate setting**; the numbers
  arrive as supplied scorecard text, and tests assert the absence. One real defect fell out of the last of those:
  `DEFAULT_CONFIG` is the shipped dict *with* the ambient `.env` applied **in place**, so on a machine whose
  `.env` enables the engines the two tests asserting "ships off" failed - `SHIPPED_DEFAULTS` now separates what
  ships from what the machine runs. Details, tests and web impact in `CHANGELOG.md`.
- [2026-09-24] **The survey's T1 batch landed - nine items, all default-off, and the risk lane now refuses what
  it cannot identify** — the T1 tier of `docs/paper_survey_26/README.md` section 2.1, in six pushes. **The
  refusals are the point.** A risk-neutral density is recovered only when the covered strikes can identify one:
  the read takes the SVD of the mixture's price-sensitivity matrix and refuses with `density: None` *plus* the
  rank and condition number, measured at **4031.5** on a four-strike chain where the unflagged fit would
  happily return a 1% quantile of 50.50. A subdominant eigenspace rotation is refused inside the
  Marchenko-Pastur bulk, where the eigenvectors are noise — and the bound is **imported** from
  `market_breadth.mp_below_count`, never re-derived. A forward shift, or a field whose declared availability
  is later than the decision date, is now **inexpressible** in the factor DSL rather than discouraged, and an
  undeclared field fails closed. **The instruments arrived with the reads:** a shared Kupiec/Christoffersen
  coverage test (`book_risk.var_coverage_test`) judges the regime VaR that K1's tail layer also consumes, and
  that tail number can only ever **widen** — quality and uncertainty move the band outward or refuse it, never
  inward. **The reporting reads:** a drawdown envelope applying the `T^(H-1/2)` depth rescaling only when a
  Hurst estimate exists, landed **report-only** so the governor keeps square-root-of-time until the mandate
  answer; and a cross-sectional forward stress probability whose calibration is part of the output (the number
  *is* its band's realized hit rate) and which says in its own `caveat` that it is fitted, not walk-forward
  tested. Two smaller deliverables: an offline redundancy screen with the L1 selection hand-rolled in numpy
  (scikit-learn is absent and adding it is still a decision), and a prompt-condition harness that makes a
  prompt edit attributable **without changing a single prompt string**. Gates, tests and per-item caveats are
  in `CHANGELOG.md`. Gate surface: 103 keys / 55 registry rows → **111 keys / 63 rows**.
- [2026-09-23] **The paper-survey adoption set landed its first wave - fourteen default-off instruments
  and state reads, and one measured defect it deliberately did not fix** — Waves 0 and 1 of
  `docs/paper_survey_26/`, one item per push, every one additive and off by default, so a gate-off run is
  byte-identical to the run before it existed and nothing entered `COMPOSITE_ENGINES`. The honesty
  instruments came first because they decide whether anything later deserves to land: a **coverage window**
  that refuses a panel statistic computed over a padded one, a **trial ledger** that reads the trial count
  and the Sharpe dispersion back from its own rows so a deflated Sharpe is deflated by a *measured* search
  rather than a caller's assertion, a **refusal ledger** that records the candidates the guardrails *stop*
  (a ratio without its denominator is not a measurement) with *missed beats saved* as an explicit
  tie-break, **autocorrelation-aware intervals** whose block length comes from the series' own ACF decay and
  is checked against an ADF test, and an **information gap** that tells a wide-but-uninformative band from a
  tight one. Then the state reads over data the engine already fetches: a duration-law hazard on the
  changepoint read, daily-bar jump proxies that say whether a tail came in one print, a GPH/Whittle memory
  parameter beside the HAR forecast, a labelled cross-strike skew proxy, a Marchenko-Pastur count of how
  many independent bets are left, a trend read beside the swing factor, a pre-event IV shape indexed in
  event time, a null-band spectral change read, and a triadic stress index that names the epicentre and is
  labelled `coincident`. Two honesty results travel with the wave: the block interval recovers most of what
  an IID interval loses under persistence but **does not** restore nominal coverage at panel scale (0.75
  against 0.45 measured at `rho = 0.8`), so the module says so instead of rounding up; and a **confirmed
  divergence from Ledoit-Wolf (2004)** in `ledoit_wolf_shrink` - the intensity omits the `1/t` factor and
  saturates at 1.0 on a narrow panel (measured 1.0000 against the paper's 0.6366) - is recorded with its
  proof and **not fixed**, because the code matches its own docstring and its own pinned test and changing
  it moves numbers you read. Gates, tests and caveats are in `CHANGELOG.md`; the per-theme plans live in
  `docs/paper_survey_26/`.
- [2026-09-15] **The post-PM decision guardrail is on, and the executor's only input contract is actually
  written** — `strategies/decision_guardrail.py` (still default-off in code) is enabled in the shipped `.env`: a
  Buy/Overweight is capped at Hold when a structured risk-debate row is HIGH/CRITICAL, confidence is capped on
  non-fresh data, and a flipped judge caps it further; downgrade-only by construction, no provider calls.
  Measured across all 21 trees before enabling, the cap would have changed **0 ratings** — the same HIGH rows
  already make the deterministic gate block new risk. Same session: `research_decision.json` is live in
  production (schema 1.1.0, validates against the executor's published contract), and
  `write_research_decision`'s silently-swallowed `AttributeError` (`_model_pool` is a dict, not a leaf list)
  meant that contract had never been emitted at all. See CHANGELOG.
- [2026-09-15] **Bull/bear transcripts separate their rounds, and five verifier false positives closed** —
  verifying the newest tree (IEI, a first run for that symbol) flagged `market` and `sentiment`; adjudicating all
  13 claims against `tool_evidence.json` found **one real report defect** (a `get_capital_flow` count of "7 of the
  last 8 weeks" where the tool's own weekly table shows 6 of 8) and **two analyst-recall defects** (a hedge-fund
  "basis-trade unwind" mechanism no leaf carries — the headline snippet stops mid-sentence — and a "~4-5 year
  duration" figure the same tree's fundamentals section had correctly refused for lack of a leaf). The rest were
  the verifier misreading its own text: `_PRIMARY_PRICE` matched the "at" inside an ordinary word (the market
  section's own caveat "Treat 114.33 as unverified" became the report's spot price, which then re-derived the
  swing-set row's 2R/3R off the day low plus ATR and flagged two verbatim `get_swing_set` targets), `t1`/`t2`
  bound to the first tool named on a line and to nothing at all on a tool-less summary row (two frameworks framed
  each other), a percent two clauses away counted as a 200-SMA distance, a dated series ("10 EMA 116.1043 ->
  115.0450") read as two competing values, and a line naming the **FOMC meeting** was held to `get_fed_watch`
  though that analyst's own news leaf carried it. Separately, `2_research/bull.md`/`bear.md` never gained the risk
  section's `### Round N` separators — the writer passed `role="Bull"` while the debate state labels every turn
  `"Bull Analyst:"`, so a two-round transcript rendered as one wall; both sections now render identically.
  Post-fix re-run: all four sections PASS, 0 non-GROUNDED claims. See CHANGELOG.
- [2026-09-14] **The report verifier stopped flagging its own extraction artifacts** - adjudicating a 4-symbol batch (727 claims: 639 GROUNDED, 78
  INTERNAL_CONFLICT, 6 UNSUPPORTED, 4 MISQUOTED, 0 CONTRADICTED) showed the CONFLICT rows were mostly the scan misreading figures: comma-grouped
  `$28,243,000,000` read as `28`, a label eating its value's leading digit (`bear 171.38` -> `71.38`), prose sliced into the reported value
  (`rice (919.97`), `stoch` matching `stochrsi`, a VIF row's score read as the RSI level, `>= 1.3` read as a second RVOL, `12m` read as 12 million,
  three labelled quarters read as one metric, and a `[\d.]+` capture swallowing a period (which silently disabled the DuPont identity check). The
  R-multiple check also crossed one tool's entry with another's stop, and the band check demanded conformal coverage from the option-implied
  expected-move band. Capture and binding are fixed (table/slash pair binding, per-tool scoping for T1/T2, conformal-only bands, line-local
  R-multiple pairs, hardened floats): conflict rows over all 45 archived trees 409 -> 186, metric errors 0, and **0** R-multiple/band claims on the
  four new trees (12 before). See [`CHANGELOG.md`](CHANGELOG.md); the advisory contract is unchanged - reports are never rewritten.
- [2026-09-14] **The sentiment analyst can no longer cite a macro level it cannot show.** The news stem gets a deterministic 10-year FRED leaf
  (`get_macro_indicators`, S11b under `enable_evidence_symmetry`); the sentiment stem binds no tools, so SKHY 2026-09-14 stated "US 10-year above 5%"
  with no leaf at all and the verifier flagged it. Under the same gate the sentiment node now fetches that leaf once, journals it under
  `tool_evidence.sentiment`, puts it in the prompt, and forbids recalled macro figures (a headline that disagrees must be reported as disagreeing).
- [2026-09-13] **S11c's mirrored evidence budget is reachable** - the paired-role discretionary mirror was
  implemented but read an undeclared, env-unreachable key, so it could never activate. `evidence_symmetry_pairs`
  (JSON `{roles, budget}` specs, `TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS`) now drives it: a surplus discretionary call
  is dropped from the evidence and journaled with its args, a forced leaf is never suppressed, and with no pair
  declared a gate-on run stays byte-identical. See CHANGELOG.
- [2026-09-13] **A launcher's `TRADINGAGENTS_*` exports were silently replaced by `.env`** - the package reloaded
  the whole `.env` with `override=True` (to force the three output-token caps) and restored only those three keys, so
  every other key the file declares overwrote the caller's environment at import: an exported gate, provider or
  temperature was ignored, and a rule-10 gate flip could not be scoped to a single run. The cap force-set is now
  scoped to the cap keys, so `TRADINGAGENTS_ENABLE_X=true py -3.12 batch.py ...` works. See CHANGELOG.
- [2026-09-13] **A drafting monologue can no longer ship as a manager plan** - the Research Manager's
  free-text fallback returned the model's own self-correction monologue ("why does my decimal become asterisks") and
  it landed verbatim at the top of `2_research/manager.md`, where the Trader and Portfolio Manager read it as the
  investment plan. A new guard detects that text, keeps the monologue's own final draft when it has one (no extra
  call), otherwise re-asks once on the backup model, and never ships the monologue. See CHANGELOG.
- [2026-09-13] **Round-3 scoring & sentiment formulas land (S1-S11, all gates default-off)** — ten additive
  deterministic reads: the Altman Z'/Z''/Z''-EM variants with the distress zones they label, the Piotroski
  F-Score's paper basis/bands/recorded deviations, Mohanram's G-Score + Montier's C-Score (industry medians from
  the resolved peer universe), a weighted/unweighted news aggregation, the crowd bull/bear ratio + dispersion, an
  MSCI-style coverage-guarded revision ratio (`get_analyst_revision_index`), a 0-100 composite quality score, score
  IC/decile/coverage/stability rows, an exponentially weighted rolling sentiment window, and paired-role evidence
  symmetry (`symmetry_report` + a mirrored discretionary budget + a gated plan call that falls back to the legacy
  loop). New screener columns G/C/Qual/RevIdx (`--growth-scores`, `--quality-score`, `--revision-index`). Every
  gate defaults off, every output prints its basis, and an unavailable input is printed as unavailable rather than
  scored 0. The reduced BW-style index (S9) stays unscheduled. See CHANGELOG.
- [2026-09-14] **OpenRouter prompt caching actually hits, and large-prompt
  request shaping** — the analyst system message (which carries the
  forced-evidence block) was rebuilt on every tool round from state that had
  since grown, so the prompt prefix moved at token 0 and an implicit prefix
  cache (OpenRouter/DeepSeek) was dead for the whole tool loop. It is now
  frozen at the first render (`_rendered_block`), and the OpenRouter client
  gained opt-in `TRADINGAGENTS_OPENROUTER_STREAMING`,
  `TRADINGAGENTS_OPENROUTER_SESSION_ID=auto` (sticky routing — never
  `provider.order`, which disables it) and the `provider` sort/latency/
  throughput/require_parameters/allow_fallbacks keys. The footer shows
  `(cache N)` and the failure journal records typed provider errors
  (`error_type=timeout` for the 504 class). Measured live on one prompt:
  `cache_read` 0 → 5888 of 6043 input tokens on the second turn. See CHANGELOG.
- [2026-09-13] **Forced-tool short-circuit actually wired** — `make_short_circuit_tool_node` guarded on
  `callable(node)`, but a LangGraph `ToolNode` is a Runnable and not callable, so every production node was returned
  unwrapped: gathered tools could re-hit the vendor, no tool call was journaled, and model-pool results
  (`get_macro_indicators`, `get_prediction_markets`) never became evidence leaves — which made the verifier flag the
  QQQI news report's five real 10Y/RRP/Polymarket lines as unsupported. Runnables now get a `RunnableLambda` that
  forwards the graph config and still answers `tools_by_name` (the tool-binding contract the wiring tests assert);
  an unwrappable node is logged instead of silently skipped. Also fixed `get_catalyst_scale` printing the modal
  probability as `8650%`. See CHANGELOG.
- [2026-09-13] **Options horizons** — every yfinance-chain tool parsed an expiry as a 6-digit contract stamp
  while yfinance returns ISO dates, so all of them silently priced a 68-day chain at 30 days: the model-free
  implied variance was doubled (0.1034 vs 0.0458), the gamma call wall read 55.0 instead of 56.0, and an expected
  move was labelled 30d while scaling a 68-day ATM IV. One `expiry_days` helper now reads both spellings, and every
  options leaf names its expiry + horizon (plus the variance-vs-vol, ATM-vs-mean-IV and OI-expiry conventions). See
  CHANGELOG.
- [2026-09-13] **Phantom conflicts + understated fund yields** — gather-time metric reconciliation now
  reads each value from the line that *names* it, so a fund with no market-cap leaf no longer produces
  `market_cap: VALUES CONFLICT range=10 .. 2026` (it says `NO VALUE IN EVIDENCE` instead), and the same fix
  removed the phantom `market_snapshot` conflicts on stock runs. The dividend-yield sanity check now also parses
  fund **distribution lists** (cadence inferred from the dated prints) and flags an understated quote — the QQQI
  2026-09-13 run quoted `9.00%` against its own record paying 14.02% — and `get_fundamentals` cross-checks the
  vendor yield field against the trailing-12m payment record. See CHANGELOG.
- [2026-09-07] **Debate reproducibility toolkit** — judge ensemble
  (`TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE`, now 5), structured-fallback reliability
  flags, field-level consensus in the RM/PM matrix, a deterministic **PM
  confidence gate** (judge flip / low agreement / free-text fallback caps the
  PM's confidence and injects a "judge reliability" prompt line), and
  `scripts/repro_check.py` (run N times, report verdict agreement). Applied
  config: ensemble=5, temp=0.1, judge→gpt-5.6-luna. A 2×3 TSM probe showed both
  old and new config yield 2/3 self-agreement (Underweight/Underweight/Overweight
  → Hold/Overweight/Hold) — the flips are reduced but not eliminated; the PM
  gate now makes a flip DEGRADE confidence instead of silently swinging the
  verdict. See CHANGELOG.
- [2026-09-07] **Reasoning-budget bound for OpenRouter models** — new
  `TRADINGAGENTS_OPENROUTER_REASONING_EFFORT` (`.env`, `low|medium|high`, off
  by default): a reasoning model (deepseek-v4-flash) that burns its WHOLE
  max_tokens on hidden reasoning now gets its hidden-reasoning effort capped
  below the output budget, so the cap-forced final report turn / structured
  debate JSON always has output room instead of returning empty / failing
  JSON-parse (the 2026-09-07 empty-report + free-text-revert defect). Sent
  only for the OpenRouter provider. See CHANGELOG.
- [2026-09-07] **Tool-not-found 400 fixed on report retries** — the analyst
  cap-forced retry (and truncation/stub chain continuations) now strip
  unfulfilled tool calls from the history before re-invoking, so a strict
  OpenAI/Azure backend no longer 400s ("No tool output found for function
  call") and the backup-model recovery of empty reports actually lands.
  See CHANGELOG.
 — `_try_fetch_closes` now
  re-sorts vendor OHLCV to ascending order, so `closes[-1]` is the LATEST
  close, never an OLDEST stale row. The TSM 2026-09-07 trade-plan card had
  pinned reference price 288.88 (oldest EODHD row) against the verified
  428.91 bar; the trade-plan card now reads 428.91. See CHANGELOG.
 — 
  when the `MAX_TOOL_ROUNDS` terminal turn returns empty content (a reasoning
  model burned its output budget on hidden reasoning), the analyst is now
  re-asked once on the backup chain (or same chain) with a completion
  directive, and only if still empty emits an explicit `**Report unavailable**`
  notice — never a silent "" that landed as a bare report-unavailable
  placeholder (QCOM fundamentals + NXPI market 2026-09-07). See CHANGELOG.
 — new `TRADINGAGENTS_BACKUP_LLM` (`.env`, `provider:model`): when ANY LLM response is cut at the output cap, the continuation retry runs on the configured backup model instead of re-paying the one that kept truncating. Threaded through every analyst/reporter/manager/debater truncation path INCLUDING the structured debate turns + L2 judge (a cut structured call falls back and repairs on the backup); empty = same-model continuations (legacy). See CHANGELOG.
- [2026-09-08] **IT subsector universe + dual-benchmark RS** - `sector_rank.INDUSTRY_ETFS` extended with the IT subsector set (SOXX/IGV/CIBR/SKYY/AIQ/BOTZ/DTCR/NXTG/IYW/FINX/XSD, parent XLK; VGT = benchmark, excluded from the ranked pool) and `get_sector_rank` now emits dual-benchmark RS on the XLK industry pool: per-row `rs2` (percentile vs VGT) answers "strongest IT subsector" while the rank stays SPY-relative — "which beats the market" in the same pass. All advisory, P2-industry-gated. See CHANGELOG.
- [2026-09-06] **Sector-rotation curated-breadth crash fix** — `get_sector_rotation_screen`'s curated-industry branch referenced `_top_note` (UnboundLocalError, the nxpi 2026-09-06 batch death) and the shared breadth block referenced imports scoped only to the eodhd branch; both fixed + regression-tested. See CHANGELOG.
- [2026-09-06] **Agent wiring: all audited calcs agent-usable via tools + prompts** — closed the 5 audit calcs with no agent surface: `bsm_equity_surface` → `get_bsm_option_quote`, `long_short_precision`/`purged_cpcv_splits` → `get_signal_quality`, `cap_and_redistribute` → `get_constituent_cap_weights`; each bound + prompt-guided (Alpaca paper surfaces excluded). See CHANGELOG.
- [2026-09-06] **Quant-formula audit pass 2** — 13 remaining divergences from the web-verified audit corrected: modified VaR (excess kurtosis), capital-income exact ceiling cap, downside deviation /N, Black-76 rho `-T·V`, BSM charm sign + dividend term, Zmijewski CA/CL, Alpha158 returns sign, canonical CHOP choppiness, Qlib precision, combinatorial CPCV, Wilder-RMA RSI/stochRSI, Taylor r*=2% (1993), GEX sign convention. All pinned by regression tests. See CHANGELOG.
- [2026-09-06] **Sector rotation screen + EODHD breadth** — constituent breadth/EW-CW/setups now run off the EODHD full-US universe (major-exchange filtered, budget-capped, per-sector n shown). See CHANGELOG.
- [2026-09-06] **Sector rotation screen** — sector-first screener tool (regime/RS/quadrant/pullback-divergence/dispersion + breadth/EW-CW/setups), LLM-facing, after-cost-validated context-only. See CHANGELOG.
- [2026-09-06] **Industry depth** — SEC EDGAR full-text search (keyless; customer-concentration footnotes, peer 10-Ks) + USPTO PatentsView patent activity (free key); wired to the fundamentals analyst. See CHANGELOG.
- [2026-09-06] **Order-flow depth** — FINRA ATS dark-pool flow + Reg SHO short-sale volume (official, keyless, as-of-gated); wired to the market analyst. See CHANGELOG.
- [2026-09-06] **Macro depth** — TGA liquidity (Treasury Fiscal Data), FX snapshot (DXY + majors), FRED liquidity/commodity/global-rate aliases; wired to the news analyst. See CHANGELOG.
- [2026-09-06] **Fundamentals depth** — earnings-call transcripts (FMP free), congressional stock trades (House/Senate watchers), SEC EDGAR XBRL financial history; all wired to the fundamentals analyst. See CHANGELOG.
- [2026-09-05] **Quant-formula Phase 6** - lottery-tilt (MAX/IVOL), Almgren-Chriss execution schedule + TWAP/VWAP/POV, CPPI + vol-target overlay — all advisory, wired to the market analyst. See CHANGELOG.
- [2026-09-05] **Quant-formula implementation (P1-P5)** - speed/zomma Greeks + vol-surface shape + parity screen; Cornish-Fisher VaR, Kappa/LPM, Burke/Martin/Pain, ruin + optimal f; variance ratio + CUSUM/EWMA + entropy features; Ohlson/Zmijewski + Dechow-Dichev; Taylor rule. All advisory, wired to the market/news analysts with prompts. See the research doc.
- [2026-09-05] **Vendor outage hardening** - a total vendor-chain failure on the flow-critical categories (prices, indicators, statements, news) now degrades to a `DATA_UNAVAILABLE` sentinel instead of aborting the run; per-vendor failures stay logged.
- [2026-09-05] **Earnings quality wired to the consensus verdict** - `get_earnings_quality(ticker, date)` is now a provider-fed read: it fetches net income / operating cash flow / total assets / capex and returns the consensus concern level (cash conversion, accrual ratio, FCF=OCF-|capex|, negative-FCF red flag) plus the forensic trap. Capex handling is sign-robust; the old ad-hoc 6%/2% accrual band is superseded.
- [2026-09-05] **Quant-engine v2 (audited)** - DuPont driver is now log-attribution (margin/leverage/mixed-led labels), scenario DCF respects g_base=0 and reports the market-price band + margin of safety, earnings-quality renders a concern level (None on no inputs); trio wired into the fundamentals analyst. DuPont ROE decomposition (`get_dupont_read`), scenario DCF (`get_scenario_dcf`), and an earnings-quality verdict (`get_earnings_quality_verdict`) — all advisory, from the 69-section quant spec (`docs/design_quant_engine_v2.md`). See CHANGELOG.
- [2026-09-05] **Quant-engine additions** - HRP portfolio construction (`get_hrp_alloc`), 12-1 momentum (`get_momentum_12_1`), an Omega row in `get_strategy_quality`, and industry-neutral factor z — all advisory, from the end-to-end quant spec + web evidence (`docs/design_quant_engine_additions.md`). 210 suite green. See CHANGELOG.
- [2026-09-05] **Option breakeven / PMCC read** - from the AVGO PMCC sample
  review: `get_option_breakeven` (new `strategies/options_breakeven.py`,
  market analyst) — breakeven = strike + premium, the short-call floor above
  breakeven, long-leg intrinsic/extrinsic split, delta bands, 30-45d theta
  window, earnings + ex-div assignment risk. Advisory, None-safe (n/a, never
  fabricated), no execution. 151 suite green. See CHANGELOG.
- [2026-09-16] **Webull OpenAPI provider study** - a direct-source study of
  Webull's Market Data API (HTTP + MQTT streaming) mapped onto `data_vendors`: the
  one provider whose income/cashflow/balance rows arrive natively basis-tagged
  (`fiscal_year`/`fiscal_period`/`end_date`/`publish_date`), i.e. the upstream half
  of the 2026-09-14 basis-drift finding; 300 req/min, 20 symbols per bars call, and a
  Python SDK, against three constraints that decide it (US-only symbols, a paid
  Nasdaq non-display entitlement for real-time with a one-device rule, and a
  production token that expires after 15 idle days). Phased P0-P3 with the sandbox
  go/no-go test spelled out (`docs/design_webull_data_provider.md`). Design only -
  no code, no chain change, the no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-05] **Sector-rotation research actions 1+3+2** - RRG quadrant
  (`rs_level x rs_momentum` → Leading/Weakening/Improving/Lagging, the
  separate-signal discipline firms use) + rotation cadence note in
  `get_sector_rank` (gated `enable_sector_multifactor`), and a
  business-cycle → sector-tilt read (`get_cycle_tilt`, new
  `strategies/cycle_tilt.py`, FRED PMI/curve/spreads, market analyst,
  None-safe). All advisory/default-off. 212 suite green. See CHANGELOG.
- [2026-09-05] **Sector-rotation P1-P3 implemented** - `sector_rank.py` gains
  the multi-factor machinery: tie-aware percentile ranking over momentum /
  RS-vs-SPY / trend / risk (P1), parent-gated industry layer (P2), constituent
  breadth + EW/CW leadership (P3) — all advisory and default-off
  (`enable_sector_multifactor` / `enable_sector_industry` /
  `enable_sector_breadth`), so the legacy sector read is unchanged until
  opted in. 24 new module tests, gated render tests, 210 suite green. See
  CHANGELOG.
- [2026-09-05] **Sector-rotation reference** - distilled from two deleted
  LLM-generated specs into `strategies/formulas/sector_rotation.md`:
  staged Market→Sector→Industry→Stock pipeline (regime = gate, score ≠
  signal), reconciled 8-factor sector score, two-level universe, and the
  two genuinely new factors (constituent breadth, EW-vs-CW leadership
  ratio) — mapped onto the existing `sector_rank.py` as P1-P3 advisory
  phases. See CHANGELOG.
- [2026-09-05] **LLM request-timeout fix** - every client request (incl.
  streaming) is now bounded by a 300 s default (`request_timeout` /
  `default_request_timeout` — the SDKs' real fields; the legacy `timeout`
  passthrough was a latent TypeError and no default was ever set). A
  stalled provider (e.g. DeepSeek at US-night peak) now raises + degrades
  instead of hanging the CLI job in an apparent "re-trying truncated
  output" loop. See CHANGELOG.
- [2026-09-04] **myhhub/stock teacher study** - a direct-source study of the
  InStock A-share rule-based quant platform (uniform strategy predicates,
  trading-calendar singleton, declarative web table registry, daily job
  pipeline) mapped onto the fork as 4 advisory, phase-gated, default-off
  adoptions — flagship: a managed trading-calendar cache feeding the
  existing `effective_date` override hook, serving the yfinance study's
  "exchange closed vs no data" gap
  (`docs/design_myhhub_stock_integration.md`). Design only — no code, the
  no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-04] **anthropics/financial-services teacher study** - a
  direct-source study of the Anthropic financial-services monorepo
  (skills-as-single-source vendored into agent bundles with a byte-identity
  drift gate, one-source/two-wrapper prompts, harness-side output_schema
  validation, data-vs-directions guardrails) mapped onto the fork as 5
  advisory, phase-gated, default-off adoptions — flagship: a skill-sync
  drift gate extending the permanent calc→agent wiring discipline
  (`docs/design_anthropic_financial_services_integration.md`). Design only —
  no code, the no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-04] **yfinance study P1 + P5 implemented** - typed absence
  reasons now travel through the read envelope (`VendorAbsence` +
  `VendorResult.absence` + OHLCV/web `absence` field and the run card's `data_absence`; string
  callers untouched) and yfinance is deliberately pinned `~=1.4` with
  vendor-quirk notes (`tradingagents/dataflows/README.md`). P2/P3/P4 of the
  study stay design-only. 181 tests green. See CHANGELOG.
- [2026-09-04] **yfinance teacher study** - a direct-source study of
  ranaroussi/yfinance v1.7.0 (one of the fork's no-key vendors) mapped onto
  the fork's vendor layer as 5 advisory, phase-gated, default-off adoptions
  (typed absence reasons, exchange-tz + currency cache for OHLCV reads, 100x
  currency-unit repair, batch error grouping + debug-serialize, deliberate
  1.x pin — `docs/design_yfinance_integration.md`); validation table shows
  the fork already adopted the retry/typed-error/stale-guard/
  statement-currency halves of the discipline. Design only — no code, the
  no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-04] **FinceptTerminal teacher study** - a direct-source study of
  Fincept-Corporation/FinceptTerminal v4 (typed topic-registry refresh
  policy, tool-result park-and-page budgets, dual tool-loop budget + visible
  exhaustion, SQLite per-step checkpoints + resume, org-as-data governance
  metadata, single-source-of-truth capability gate) mapped onto the fork +
  trading_web as 6 advisory, phase-gated, default-off adoptions
  (`docs/design_fincept_terminal_integration.md`); validation table shows
  the fork is already ahead on LLM providers, Qlib study and backtest
  semantics. Design only — no code, the no-execution/advisory mandates
  stand. See CHANGELOG.
- [2026-09-04] **ai-hedge-fund teacher study** - a direct-source study of
  virattt/ai-hedge-fund v2 (mandate-as-data fund YAML, event-study
  market-model CAR significance, abstention-vs-neutral conviction blending,
  per-clamp risk audit, prompt provenance vault) mapped onto the fork's
  seams as 5 advisory, phase-gated, default-off adoptions
  (`docs/design_ai_hedge_fund_integration.md`); the validation table also
  shows the fork is already ahead on CPCV/PBO/evaluate metrics. Design
  only — no code, the no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-04] **Hummingbot teacher study** - a direct-source study of
  Hummingbot's V2 framework (Strategy/Controller/Executor, per-executor
  CloseType accounting, pre-trade budget-collateral lock, live-book
  fill-latency, unified executor ledger, async notifier) mapped onto the
  fork's seams as 5 advisory, phase-gated, default-off adoptions
  (`docs/design_hummingbot_integration.md`). Design only — no code, the
  no-execution/advisory mandates stand. See CHANGELOG.
- [2026-09-04] **Calc→agent wiring gates** - the wiring contract is now a
  permanent test: every public calc must be externally referenced (or a
  helper of a reachable module) and every `@tool` must be bound to a
  ToolNode / risk loop / analyst. **Corrected 2026-09-11:** that first gate
  counted "bound" as *appearing in a ToolNode list*, so the eight tools it
  reported as wired (`get_pair_risk`, `get_trade_excursions`, `get_vif_read`,
  `get_no_trade_guard_band`, `get_prediction_ledger_score`,
  `get_trade_outcome_metrics`, `get_stress_grid_read`,
  `get_macro_regime_read`) were never callable — a model can only call a tool
  in its `bind_tools` set — and `docs/api_reference.md` documented 16
  bindings that did not exist. The gate now reads the toolset objects,
  requires the `bind_tools` set and the executor list to agree in both
  directions, and fails on a stale declaration or an unreal documented
  surface.
- [2026-09-04] **Formula-catalog quant adds (six-pillar + master-catalog)** -
  Ledoit-Wolf shrunk covariance + EWMA covariance + Yang-Zhang vol (completes
  the estimator set: close/Parkinson/GK/YZ/EWMA/GARCH), a book-concentration
  suite (active share / effective holdings / HHI / entropy), EVT/GPD
  extreme-tail VaR/ES (extrapolates beyond the observed worst day), Kyle
  lambda (daily-bar impact slope) and multi-asset fractional Kelly allocation
  — all advisory, default-off config, bound as market/fundamentals analyst
  tools (+ trading_web Value Tools). See CHANGELOG.
- [2026-09-04] **Value-dip `--knife-z` velocity gate + batch `--probe` tracing** -
  the value screener's value-dip scan can now enforce the falling-knife
  velocity-z guard (``--knife-z -2.5`` blocks candidates whose 3-day price
  velocity z drops below -2.5 — the unresolved-cascade case the composite knife
  guard warns about; knife rows were always displayed, the flag just decides
  whether they gate). Wired across the tickers/eodhd-us/eodhd-losers/moomoo
  universes; web Screener form mirrors it. ``batch.py --probe`` writes a
  per-stage trace JSONL (graph_start / graph_done / graph_failed) so a hung or
  failed symbol shows exactly which stage broke. See CHANGELOG.
- [2026-09-04] **fix: risk governor drawdown stop** - the R0/R2 realized-
  drawdown stop could never fire (the config limit was fed into its own
  comparison). Now resolved from the measured basket drawdown
  (`book_risk.portfolio_drawdown`), so a real >limit book drawdown blocks new
  risk - LULU's BLOCKED analyst read now matches the final Risk Gate.
- [2026-09-04] **Alpha-health ledger + monitor** - ``scripts/alpha_health.py``
  collects emitted decisions into ``reports/alpha_ledger.jsonl`` and joins
  realized 1/5/20/60d forward returns to report score distribution, rank IC /
  ICIR, the horizon alpha-decay curve and win rates - answering "did the
  scorer stop finding opportunities, or did the market get efficient?"
  (`TRADINGAGENTS_ALPHA_LEDGER_ENABLE`).
- [2026-09-04] **Agent-visible quant tools** - regime state, Kalman pair
  spread, execution multiplier, Black-Litterman allocation and the no-trade
  guard band are now @tools bound to the Market/Fundamentals analysts (+
  ToolNodes), and the graph feeds real hard guards (risk REJECT / stale data /
  illiquid) into position sizing under `enable_hard_guards`.
- [2026-09-04] **Kalman dynamic spread + Black-Litterman** - a pure Kalman
  filter tracks a pair's hedge ratio online (adapts to drift; static rolling
  beta doesn't) for pairs/stat-arb signals; Black-Litterman view blending
  (P/Ω/Q) already ships in the optimiser. Both web-formula-verified, tested.
- [2026-09-04] **Execution multiplier (soft/hard)** - one tunable
  `execution_multiplier` over an explicit two-tier policy: soft guards
  (regime/vol/knife/flow) scale size down, hard guards
  (halt/liquidity/portfolio-risk/data-quality/broker-safety) block outright.
  Halve-not-block, with a real stop only when warranted.
- [2026-09-04] **Regime Vol Cap (F_vol)** - the ATR-ratio ladder
  (1.2→100% / 1.5→75% / 2.0→50% / 3.0→25% / >3→block) scales position size
  continuously instead of binary on/off, composing with F_regime and F_knife;
  the vol leg leaves F_regime when the ladder is enabled (no double half).
  Advisory (`vol_cap_enable`, default off).
- [2026-09-04] **Multi-axis regime state** - four crisp dimensions
  (Trend/Volatility/Relative-vs-benchmark/Drawdown) instead of one label,
  aggregated with a graduated `F_regime` position-size factor composed with
  the knife guard (`sized ×= F_regime × F_knife`). Advisory
  (`regime_state_enable`, default off).
- [2026-09-04] **Composite knife-guard score** - a weighted falling-knife
  score K (return/volume/ATR/drawdown/order-flow z legs) with a graduated
  position-size multiplier (1.0 → 0.5 → 0.25 → block) instead of a binary
  buy/don't-buy, plus a transaction-cost no-trade guard band for the
  execution layer. Advisory (`knife_composite_enable`, default off);
  displayed in every value-dip setup.
- [2026-09-04] **Screener column pruning** - the value watchlist hides any
  column with no data in every row (`n/a`/`no`/empty), keeping only columns
  that carry real values (Rank/Ticker always shown); the legend follows the
  table. Sparse runs report compact results instead of 60+ mostly-empty
  columns.
- [2026-09-03] **Execution-layer contract emitter** - every report tree now
  writes `research_decision.json` (deterministic, hash-pinned; PM rating, G1
  position contract stop/target/size, data_quality, risk_gate; nulls for the
  unproducible — fail closed). It is the ONLY input contract of the new
  TradingExecution signal daemon (Phase A; signals only, no orders).
- [2026-09-02] **Nightly-review driver `--mode recent`** - `scripts/nightly_review.py`
  can now review each symbol's MOST RECENT report folder instead of only the
  newest `batch_summary_*.jsonl`, so interactive CLI / `propagate()` runs that
  never wrote a batch summary (e.g. INTU / TSLA / DELL) get pre-open re-checks
  too. Newest-per-symbol is keyed on the folder-name timestamp (fixed-width,
  lexicographic); folders without a prior decision are skipped with a note.
  Default `--mode batch` behavior is unchanged. trading_web `run_nightly`
  forwards `--mode` and the Nightly form gains a "Review source" selector.
  The scheduler wrapper now runs `--mode recent --max-symbols 25`, and the
  driver hard-exits after a completed run (no moomoo shutdown hang).
  See CHANGELOG.
- [2026-09-02] **Positions -> risk-basket utility + PM holdings read (Option A/B)** - 
  `scripts/positions_to_basket.py` combines broker position CSVs (Fidelity-style,
  under gitignored `positions/`) into the real `TRADINGAGENTS_RISK_BASKET_TICKERS` /
  `_WEIGHTS` **with cash in the denominator** - the <1.0 weight remainder IS the
  cash sleeve (`book_risk.portfolio_cvar`'s documented "weights + cash" semantic).
  Dry-run by default (per-account cross-check, total/cash, per-symbol weights);
  `--apply` backs up `.env` and rewrites only the two basket lines; `--write-book-json`
  persists the dollar book (gitignored) - the Option-C artifact. New `holdings_tickers` /
  `holdings_weights` config (+ env) feed an advisory **"Computed book"** block into the
  computed decision context (Option A default: the basket IS the book; Option B: a
  separate holdings map overrides it), so the PM now states "you hold no TSLA -> size 0"
  instead of the conditional "if you hold it, trim". The `profolio/` gitignore typo is
  fixed to also cover `positions/`. See CHANGELOG.
- [2026-09-01] **Parent-repo ports: look-ahead safety + debate opening** (#1/#2) -
  `dataflows/date_window.py` now centralizes the half-open UTC content window;
  StockTwits and Reddit trim to the run's as-of window so a historical/backtest
  run can never leak post-date chatter (yfinance news already had the rule).
  The five legacy debators (bull/bear + 3 risk) interpolate an explicit
  "opponent has not spoken yet — open the debate with your own case" marker on
  round 1 instead of fabricating the other side's position. See CHANGELOG.
- [2026-09-01] **Cookbook quant-strategy gap implementation** - the five
  `Strategies/cookbook.md` recipes (time-series momentum, cross-sectional mean
  reversion, cointegration pairs, multifactor portfolios, options vol) are now
  code: MOP-style `ts_momentum_weights` (sign x inverse-EWMA-vol, target-vol
  capped), a cross-sectional toolkit (`cross_section.py`: winsorize /
  centered-rank / quantile-split / market-residualize / dollar+beta+sector-
  neutral book / no-trade band), pairs `spread_zscore` / `pair_signal` /
  `pair_quantities` / `ecm_loading`, z-composite alpha + multi-horizon
  momentum, portfolio stats (turnover / turnover-cost / exposure /
  rolling-Sharpe / regime-split), Black-76 rho/vanna/vomma/charm + vanilla-BSM
  surface + delta-gamma-vega-theta scenario P&L + Cboe/VIX-style model-free
  implied variance (fixing the always-degrading `get_variance_premium`), CDaR,
  max-diversification weights, Merton distance-to-default, forward rate, and a
  microprice/OBI depth read. All bound to the market analyst + risk debators as
  advisory tools. See CHANGELOG.
- [2026-09-01] **Structured-debate robustness + json_mode route fix** - the
  opt-in debate pipeline is now fully working end-to-end on live runs (QCOM,
  DELL). Root cause of the always-empty judge: OpenRouter's `json_object`
  route requires the literal token "json" in the prompt, which the judge
  lacked - every call 400ed and fell back to ragged output. Fixed: "single
  JSON object" prompt cue + flattened `scores: [{dimension, score}]` rubric
  + tolerant coercion + a deterministic prose-score fallback. Claim-key
  resolution upgraded (normalize -> alias -> confidence-gated fuzzy) so
  humanized labels (`Free cash flow yield`, `Altman Z-score`) verify as
  `valid` instead of `(unused)`. New `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL`
  key lets the neutral risk debater use its own model. See CHANGELOG.
- [2026-08-31] **Risk-section structured debate parity (direction.md)** -
  the structured multi-agent debate now covers BOTH sections: the risk
  debate (aggressive/conservative/neutral) runs the same machinery as the
  research debate — `RiskDebaterTurnPayload` grounded turns, L1 claim
  verification + severity triage, and the SAME blind order-rotated judge
  (3 candidates) before the Portfolio Manager. Model keys are shared:
  `TRADINGAGENTS_DEBATE_BULL_MODEL` → bull + aggressive,
  `_BEAR_MODEL` → bear + conservative, `_JUDGE_MODEL` → both judges;
  neutral stays on the quick tier. ONE depth knob
  (`TRADINGAGENTS_RESEARCH_DEPTH` or the CLI selection) now drives BOTH
  round counts to the same level (research + risk), and the research router
  no longer hard-stops after one round — it cycles to the next round within
  the cap. Research Manager + Portfolio Manager prompts now include the L2
  judge verdict evidence block. `4_risk/structured_risk_debate.md` mirrors
  the research evidence block. All remains opt-in via `enable_debate`;
  off-mode legacy chain bit-identical. See CHANGELOG.
- [2026-08-31] **Structured multi-agent debate implemented (opt-in)** -
  the research debate design (`docs/design_multi_agent_debate.md`) is now
  code: with `enable_debate` (+ `TRADINGAGENTS_ENABLE_DEBATE=true`) the
  bull/bear debate runs as a structured subgraph — `DebaterTurnPayload`
  turns via a dual-mode schema adapter (structured-output API with a
  markdown-fence + Pydantic repair fallback), pure L1 claim verification +
  severity triage (HARD_BREACH → baseline fallback, RETRYABLE → one scoped
  regen, SOFT_WARNING → penalty + annotated L2), an entrenchment index +
  divergence-floor artificial-consensus flag with α-reweight to the
  empirical base rate, and a blind order-rotated dimensioned L2 judge
  (`L2JudgeDimensionedRubric`); per-role heterogeneous models
  (`debate_bull_model` / `_bear_model` / `_judge_model`, capability-matrix
  checked at startup) and a matched-compute A/B harness
  (`scripts/debate_ab_harness.py`, Brier + max-unforecasted drawdown).
  Judge scores + claim ledger render into the 2_research section
  (`structured_debate.md`). All `debate_*` config defaults OFF — the
  legacy one-shot chain is bit-identical when unused. See CHANGELOG.
- [2026-08-31] **Multi-agent debate architecture (design, research-only)** -
  `docs/design_multi_agent_debate.md` upgrades the bull/bear research debate
  onto a production two-layer judiciary: deterministic L1 gates (claim
  verifier, risk governor, divergence check) always precede an L2 blind,
  dimensioned, ensembled LLM judge; heterogeneous per-role models; an FSM
  orchestrator with the canonical wire schemas from
  `Strategies/Multi_Agents_Debate.md` (DebaterTurnPayload /
  L1DeterministicResult / L2JudgeDimensionedRubric); R1 fast-abort +
  single-role regen, R2 artificial-consensus reweight, R3 dual-mode schema
  adapter + config-time capability matrix, R4 matched-compute A/B (Brier +
  max unforecasted drawdown), R5 state machine. Research only — no code
  changed; the proposed `debate_*` config defaults OFF. See CHANGELOG.
- [2026-08-31] **CLI deep-run runtime/depth defect fixed** - 'deep' research
  depth mapped to 5 bull + 5 bear debate turns, which multiplied runtime
  (SKHY 08-31 >1h vs 30-40m) and let later debate turns degenerate into
  rambling/empty arguments that left a 0-byte `2_research/manager.md`. Depth
  now scales the RISK rounds only; the bull/bear researchers each run once.
  Also: empty-argument retry + honest-note guards in both researchers, an
  explicit "plan unavailable" block when the Research Manager produces no
  plan, and a 2-tool-round cap on the risk-debator / Trader in-node tool
  loops. See CHANGELOG.
- [2026-08-31] **Risk calculations wired into the decision agents** (7-phase
  audit, `docs/design_risk_calculations_agent_wiring.md`): the 18 quant-risk
  tools that existed in the market ToolNode but were unreachable by the LLM
  are now bound (horizon-VaR, downside, trailing exit, risk-parity, normality,
  unit-root, CAPM, rotation, Clenow, omega, correlation, scale-out, sentiment-
  computed, curve surfaces, movers, variance premium); 12 new `@tool`s wrap
  previously-untooled calculators (`get_fixed_risk_size`, `get_exit_overrides`,
  `get_pre_trade_read`, `get_ledger_risk_state`, `get_trade_plan`,
  `get_fixed_income_risk`, `get_pair_risk`, `get_vif_read`, `get_vol_cones`,
  `get_trade_excursions`, `get_alpha_scoring`, `get_regime_gate_read`);
  `get_risk_gate` now checks the full governor surface (daily-loss budget,
  high-water-mark tiers, sector cap, tranche capital-at-risk, liquidity
  verdict); the 3 risk debators run an in-node 23-tool risk loop and the
  Trader a 12-tool verification pass (`agents/utils/risk_tool_loop.py`, capped
  at MAX_TOOL_ROUNDS, plain-invocation fallback when the provider cannot bind
  tools); the computed decision context carries a risk factsheet (limits
  registry, vol estimates, tranche peak-deployed + capital-at-risk, fixed-risk
  size); news analyst gains credit-stress + news-sentiment, fundamentals gains
  fixed-income + alpha-scoring, Research Manager + bull/bear researchers get
  the computed context. Also moved 5 strategy keys that had been misplaced in
  `data_vendors` back to top-level config (sentiment-factor overlay +
  `volatility_estimator` were silently unreachable as defaults). Web
  value-tools += 5 new ticker tools. Tests: `tests/test_risk_agent_wiring.py`
  (22 hermetic). See CHANGELOG.
- [2026-08-31] **Report truncated after Research Manager (missing Trader /
  risk / PM)** - interactive runs (e.g. SKHY 08-30/08-31) saved only the
  analysts + bull/bear/research-manager because the graph **ended after the
  Research Manager judge** — `graph/setup.py` had lost the
  `Research Manager -> Trader` edge (and the Bull/Bear debate conditionals in
  the same block), so LangGraph had no path onward and the Trader / risk /
  Portfolio-Manager sections never rendered. Restored the full chain
  (Research Manager -> Trader -> risk debate -> Portfolio Manager -> END);
  hermetic full-stream verification + a regression test guard it. See
  CHANGELOG.
- [2026-08-31] **Tool-round cap `KeyError '<Analyst>'` fix** - a run whose
  market/news/fundamentals analyst hit the 8-tool-round cap crashed with
  `KeyError: 'Market Analyst'` (LangGraph "During task ..." note) because the
  cap routers return the analyst node name but the graph only registered
  `tools`/`clear` as conditional-edge targets. The analyst node is now a
  registered self-loop target in both sequential and parallel modes, and the
  analyst nodes short-circuit the cap turn (strip dangling tool_calls, one
  terminal prose turn) so the loop always terminates and reports are never
  empty. Regression tests added. See CHANGELOG.
- [2026-09-03] **Live-print reconciliation** - Alpaca `get_intraday` symbol-mismatch guard + `get_live_price_sanity` tool (flags live prints below the verified day low / above the high as likely-stale, never reconciled).
- [2026-09-03] **Cluster/exit gates** - `allocation_block` hard `max_pairwise_corr` cluster gate + `trailing_stop_exit` ATR-adaptive trailing (`trailing_stop_atr_mult`); both advisory/default-off, notes sync'd.
- [2026-09-03] **Mean-reversion hardenings** - `regime_gate_read` market-stress leg (`market_stress_index`=^SPX, `market_stress_vol_cap`=0.85), `liquidity_verdict` 20d dollar-volume floor (`min_dollar_volume`) + Roll-spread cap (`max_spread_bps`), `catalyst_hard_block_days` default 5 (forward earnings blackout). All advisory/default-off except the blackout. Tests in test_strategies_{liquidity,regime}.
- [2026-09-03] **`--universe moomoo-screen` - whole-market value-dip scanner
  via moomoo Stock Screening V2** - the value screener can now seed from the
  moomoo screener API (local OpenD): a server-side AND of value anchors
  (PE_TTM, market cap, ROE) and dip timing (5-day change, RSI 14) over the
  whole US market, plus the 52-week-high distance factor. Rows carry the
  API's own price/PE/ROE/RSI/52w values, so the watchlist reflects the dip
  without a per-symbol fetch. Filter defaults come from config
  (TRADINGAGENTS_MOOMOO_SCREEN_*) and are overridable per flag
  (--max-chg5d/--max-rsi/--max-debt-assets, plus the shared --pe-max/--min-mcap/
--min-roe) + server-side price/PB band (--price-min, --pb-min/--pb-max),
  configurable pullback window (--dip-days, default 5; the reference recipe
  uses 20), and a client-side NYSE/Nasdaq exchange gate (--exchanges,
  default NYSE,NASDAQ, applied to every universe - moomoo screen V2 has no
  functional US exchange filter, so candidates are checked via
  get_stock_basicinfo / EODHD list). Needs OpenD logged in + `moomoo-api`; no other key.
- [2026-08-31] **`--universe eodhd-losers` + `--value-dip-loose`** - the value
  screener can now seed the scan from the EODHD bulk US real-time feed (one
  call, ~18k rows, OpenD-independent): the biggest intraday decliners by
  change% are screened first (equity-filtered against the exchange-symbol
  common-stock list, so warrants/ETFs don't dominate the seed), harvesting
  value-dip/momentum candidates from today's actual dips instead of an
  alphabetical `eodhd-us` slice. `--value-dip-loose` relaxes the value-dip
  entry to `RSI<=35 OR %b<=0.10` and appends a ranked near-miss table naming
  the gate each near candidate missed. `-n` sets the decliner count; `--price-min`
  gates on the feed's live close; mcap/PE/ATR gates still run per-symbol.
  Docs: `Strategies/scan.md` "Universe sources" + "The value-dip".
- [2026-08-30] **Two-stage screener gating** - every OHLCV-capable scan mode
  (`trend-pullback`/`breakout`/`momentum`/`swing`/`vcp`/`value-dip`) now runs a
  **cheap OHLCV-only gate (Stage A)** on the single cached price series before
  any fundamentals fetch — non-candidates are dropped without querying a data
  provider. Only survivors get memoized fundamentals (Stage B) and then
  provider enrichment (Stage C: float/sector/revisions/institutions).
  `value`/`all` fall straight through. This makes a large `eodhd-us` slice or a
  movers universe tractable (non-candidates cost ~1 vendor call instead of
  ~6-7). Docs: `Strategies/scan.md` "Two-stage gating".
- [2026-08-30] **News/sentiment providers (A-C)** - GDELT (keyless native
  news-tone + daily sentiment, `get_gdelt_sentiment` tool, opt-in chain),
  NewsAPI.org (free 100 req/day global macro headlines, `NEWSAPI_API_KEY`),
  and Benzinga (free ticker-scoped financial news, `BENZINGA_API_KEY`).
  Registered vendors; NewsAPI in the default chain, GDELT/Benzinga opt-in. See
  CHANGELOG.
- [2026-08-30] **News-sentiment factor** (`News_Sentiment.md`) - EODHD
  `/sentiments` daily series (-1..1 + 7d SMA + latest innovation; AV
  `NEWS_SENTIMENT` + GDELT fallbacks) via a new `news_sentiment` chain;
  analytics `strategies/sentiment_research.py` (lead/lag, multi-horizon
  Newey-West regression, rolling IC + half-life, quintile long/short);
  tools `get_news_sentiment_series` / `get_sentiment_lead_lag` on the market
  + news analysts; `scripts/sentiment_factor_eval.py` + screener
  `--sentiment` (Sent7/SentZ); opt-in `enable_sentiment_factor` overlay fold;
  trading_web Value Tools. See CHANGELOG.
- [2026-08-30] **Quant-formula calculations** (`Strategies/quants.md` +
  `quant2.md`) - volatility estimators (Parkinson / Garman-Klass / EWMA /
  GARCH(1,1) + `volatility_estimator` overlay switch), book tail
  decomposition (incremental/component VaR), mean-reversion quality
  (AR(1)/OU half-life with a t-test gate), Roll effective-spread, preferred
  fixed-income YTM/duration/DV01 (capital_income `--fi`), credit
  hazard/default-probability, variance-swap strike, and implementation
  shortfall (strategy_quality `avg_is_bp`). New market tools + trading_web
  Value Tools 33->36. See CHANGELOG.

- [2026-08-30] **Extended technical indicators** - the standard
  trend/momentum/volume/structure set the project lacked now computes locally
  (`strategies/extended_indicators.py`): Ichimoku cloud, CCI, ROC, momentum
  oscillator, TRIX, Force Index, A/D line, VPT, Chaikin Money Flow, anchored
  VWAP, golden/death cross + a candlestick pattern scanner (doji/hammer/
  engulfing/stars). Two new market-analyst tools `get_extended_indicators` +
  `get_candlestick_patterns` (no new vendor, no quota). See CHANGELOG.

- [2026-08-30] **Twelve Data + StockData.org vendors** - two new free-tier
  market-data providers: Twelve Data (free "Basic": 800 credits/day, realtime
  US stocks/forex/crypto quotes + historical OHLCV) and StockData.org (free
  "$0/mo": 100 requests/day, quote/EOD/intraday/news). Both keyed via
  `TWELVEDATA_API_KEY` / `STOCKDATA_API_KEY` in `.env` and wired as tails of
  `core_stock_apis` + `news_data`, plus market-snapshot / crypto-prices
  fallbacks. All key-gated; the existing chains stay first. See CHANGELOG.

- [2026-08-30] **Independent pre-debate stances (Option-A hybrid)** - the 3
  risk debators + bull/bear researchers each emit ONE independent stance
  (rating / confidence / strength / reason) BEFORE the debate runs, sampled
  with **no transcript and no opponents' responses** — so agreement/consensus
  (`enable_agreement`, G3), the G1 position-contract multiply, the PM's
  dissent flag and the Research Manager's read all come from uncontaminated,
  conformity-free opinions while the debate stays the risk-surfacing layer.
  Opt-in `enable_independent_vote` (`TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE`);
  every fallback is the legacy parse-from-history path when off. See CHANGELOG.

- [2026-08-29] **Risk gate placement + compact verdict** - the computed risk
  gate is no longer repeated at the top of every analyst report (it appears
  once, in `4_risk/` + `5_portfolio/decision.md`), the compact `verdict.md` no
  longer duplicates the PM decision, and report re-renders are idempotent
  (no doubled `### Round N` headings). See CHANGELOG.

- [2026-08-29] **Readable reports + verbose risk files** - the interactive
  CLI now always writes the full risk-debate transcripts
  (`4_risk/aggressive.md` / `conservative.md` / `neutral.md`) instead of a
  single `verdict.md`, and debate/trader/research reports are automatically
  paragraph-spaced with `### Round N` headings (analyst-style readability) via
  `reporting._readable_section`. Re-render old folders with
  `scripts/rebuild_complete_report.py`. See CHANGELOG.

- [2026-08-29] **Canonical output root** - all `reports/`, `screener/` and
  `action_reports/` outputs now resolve against the TradingAgents repo,
  regardless of where the CLI or web server is launched from (previously the
  web app, started from `TradingNew` or `trading_web`, could drop `reports/`
  into those parent folders). Wired through a shared
  `resolve_output_path()` helper across batch/pipeline/screener/action-report/
  nightly-review/pre-market-review/rebuild. Stale stray `reports/` dirs were
  consolidated into `TradingAgents/reports/`. See CHANGELOG.

- [2026-08-29] **Provider-endpoint + calc-wiring pass** - audited every data
  provider's docs for exposable endpoints and every strategy calculator for
  agent wiring. New keyless yfinance fallbacks for `analyst_ratings`
  (recommendation summary + price-target consensus), `earnings_calendar`
  (earnings dates + EPS surprise) and `institution_data` (institutional +
  major holders), registered in the vendor chains — those signals no longer
  need a moomoo gateway or paid key. New market tools `get_scaleout_plan`
  (tiered profit-taking), `get_payoff_asymmetry` (Omega ratio) and
  `get_book_correlation` (book concentration); `get_strategy_quality` now also
  reports Calmar / Ulcer / tail-ratio / expectancy. See CHANGELOG.

- [2026-08-29] **Full-set audit fixes (correctness + agent wiring)** - a
  read-everything audit fixed 14 defects so the numbers the LLM agents cite are
  correct and reachable: `exit_check` target now anchored at entry (was close,
  so "target" could never fire); parametric horizon CVaR sign/tail-probability
  fix; `first_pullback` R:R no longer permanently dead; yfinance statement CSV
  parsed newest-first (was returning the OLDEST year as "latest") and its
  `# comment` header no longer mis-routes to the text parser; `tracking_error`
  now demeaned; `ev_ebitda` no longer collapses to P/EBITDA; FCF/dividend-yield
  sign-safe on GAAP-negative capex/divs; Alpha-Vantage error strings no longer
  cached as data; screener/movers invalid args return `DATA_UNAVAILABLE`
  sentinels; routed EODHD symbol list is a string. Wiring: new `get_exit_plan`
  tool (breakeven-after-confirmation + margin-giveback), and `get_consensus` +
  `get_sentiment_computed` (previously unbound) are now callable from the
  analyst ToolNodes; batch `--vendor` presets keep all 27 data categories. See
  CHANGELOG.

- [2026-08-28] **QuantLib + Lean enhancements (deep-study implementation)** -
  evaluation breadth beyond Sharpe (Sortino / PSR / rolling-beta / underwater
  drawdowns), horizon VaR/CVaR, options IV + Greeks (Black-76), risk-parity /
  min-variance / confidence-weighted allocation from a real covariance matrix,
  a two-pass risk manager (advisory, off), MAE/MFE excursion journaling, and
  volume-share / market-impact slippage - all as deterministic pure modules
  under `tradingagents/strategies/` plus 4 new market analyst tools, with every
  gate default OFF / advisory-only. See
  docs/design_quantlib_lean_enhancements.md and CHANGELOG.

- [2026-08-28] **Pre-open + execution-quality advisory rows** - probed your
  actual data tiers and built what's available on free: pre-market RVOL vs
  30-day pre-open average, gap vs the live pre-open price, and a live IEX
  quote-depth thin-book proxy (all Alpaca free IEX) fed into the pre-market
  review as advisory context; plus a post-fill drift (alpha-profile) block in
  the strategy-quality report. True opening-imbalance (NOII) and short-locate
  are plan-gated / out of scope - documented.

- [2026-08-28] **Institutional workflow for value-dip + swing (Phases A-E)** -
  mapped institutional best practice (regime switching, catalyst-first value,
  daily-loss/HWM risk gates, trade plan card, arrival-benchmark execution
  ledger, sleeve attribution, alpha-decay monitor) onto the stack. All new
  signals are ADVISORY - computed from real data and injected into the 5
  decision agents (Trader, PM, 3 risk debators) via a compiled decision
  context, so the LLMs reason over hard numbers; nothing blocks unless you
  opt into the strict flags. See docs/design_institutional_value_dip_workflow.md
  and CHANGELOG.

- [2026-08-28] **Value Dip + Swing enhancements (web-researched)** - compared
  the setup/exit math against established swing-trading practice and closed
  the gaps: VCP now enforces a **halving progression** (`contraction_tol=0.65`,
  default) with a final-tightness gate + a `pivot` breakout field; the
  **chandelier exit** uses real daily highs (was a closes proxy); the value-dip
  setup adds a `trend` row (opt-in `require_trend` gate), a `plan_stop_ok`
  harmonization field, a `strict_vdu` mode, configurable ATR/%-drawdown
  tranche ladders, and an R-based breakeven (`exits.stop_to_breakeven_r`).
  See CHANGELOG.

- [2026-08-28] **Dedupe repeated debate tables in reports** - deep runs
  rendered 4-6 near-identical summary tables per debate agent (one per round)
  - e.g. the latest NVDA report carried 28 tables in `complete_report.md`.
  Fix: debaters now append their summary table only in the FINAL round
  (`get_output_budget("debater")`), and `reporting._collapse_repeated_tables`
  keeps only the last table per header as a render-time guarantee (existing
  reports fixed via `rebuild_complete_report.py`). NVDA sample: complete
  report 28 -> 14 tables.

- [2026-08-28] **Interactive CLI now applies the strategy overlays** - the
  CLI streamed the graph but skipped `_apply_strategy_overlays`, so a CLI
  report omitted the Risk Gate block / position contract / computed risk
  context that the batch/API path renders (two same-day NVDA reports diverged
  structurally: batch showed a Risk Gate PASS, CLI showed none and a
  different decision). The CLI now seeds `risk_context` pre-PM and applies
  the overlays before saving - same hooks as `propagate()`, so CLI and batch
  reports carry the same computed risk surface.

- [2026-08-28] **Audit-driven correctness fixes (data integrity + wiring)** - a
  repo-wide audit fixed ~26 defects with hermetic tests (1490 passed, 2
  skipped, ruff clean). Highlights: Piotroski ROA point no longer awarded to
  negative-ROA firms; the vendor router records rate-limit errors so an
  all-throttled optional chain degrades instead of crashing; Alpha Vantage HTTP
  429/5xx/timeout map to a retryable error (was a hard crash of the price
  path); DCF projects the LATEST FCF (was the historical max); OBV bullish
  divergence slice fixed; yfinance statement/insider functions re-raise instead
  of caching prose as truth; `TRANCHE_WEIGHTS` env coerces to floats (was
  silently disabling the tranche fold); and six analyst tools the prompts
  instructed (get_expected_move, get_institution_holdings,
  get_earnings_surprise_history, get_momentum_scan, get_market_snapshot_alpaca,
  get_insider_transactions) are now actually bound. Edge fixes: percent-field
  unit drift, moomoo rate-limit classification + forex/futures fallback,
  non-circular pre-market ledger realized return, `--rank composite` wiring,
  pipeline worker cap, `--illiq` flag. The Portfolio Manager now receives the
  deterministic CVaR/liquidity context it was meant to argue from. Docs/config
  aligned (overlay defaults, missing env overrides, entry-point flags); web
  `--illiq` forwarded. See CHANGELOG for the full list.

- [2026-08-27] **EODHD real-time snapshot + top movers** - the Massive
  snapshot / top-movers endpoints are 403 on the free plan; EODHD's
  `/api/real-time` works on the EOD plan and now backs them:
  `get_market_snapshot_eodhd` (live OHLCV + prev close + change%) and
  `get_top_movers_eodhd` (bulk `?ex=US` ~18k stocks sorted by change_p). The
  `get_market_snapshot` / `get_top_movers` tools fall back to EODHD when
  Massive 403s.

- [2026-08-27] **Truncation-retry enforcement** - when an LLM response is cut
  at the output cap (ends mid-sentence), the agent re-invokes with a
  continuation prompt and merges, so reports are never truncated. Wired into
  every agent path: PM/RM/trader/sentiment free-text fallback, the 3 analyst
  tool-calling chains, and the bull/bear researchers + 3 risk debators. Up
  to 2 continuation attempts, only when a cut is detected; a failed
  continuation degrades to the original text.

- [2026-08-27] **Tool-wiring audit: 4 new market tools + OHLCV cache +
  computed sentiment on** - the audit found strategy functions that were
  implemented but never exposed to the analyst LLMs, and duplicate OHLCV
  fetches across tools. New market tools: `get_technical_factors` (ADX/pivots/
  Aroon/Fisher/Chaikin/Elder-Ray/Supertrend/volume-profile in one call),
  `get_book_tail_risk` (portfolio CVaR + correlated stress + drawdown gate),
  `get_liquidation_days` (block-absorption days), `get_premarket_review`
  (CONFIRM/REVISE/REJECT arbiter). A run-level OHLCV cache makes every tool
  share ONE vendor fetch per ticker per run (no duplicate data).
  `enable_sentiment` is now on (computed StockTwits score + surprise velocity
  injected into the sentiment report).

- [2026-08-27] **Market tool-node binding fix + higher output cap** - the
  market analyst's prompt listed `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` and the 5 market-session tools, but they were never
  registered in the market `ToolNode` (a wiring gap from the original
  value-dip+swing commits) — every run had the LLM call tools that error "not a
  valid tool". All 8 are now bound. `max_output_tokens` / `_quick` raised
  6000 → 8000 after 2026-08-27 WDC analyst reports truncated mid-sentence at
  the 6000 cap.

- [2026-08-27] **EODHD primary + eodhd-us default universe** - the
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance fallback); `news_data` and `corporate_actions` also lead
  with EODHD. New EODHD endpoints: news, splits/dividends, and the full US
  symbol list (~18k common stocks) — the screener's default `--universe
  eodhd-us` (no moomoo quota). The bulk US real-time feed (one call, ~18k
  rows) backs the screener's `--universe eodhd-losers` (biggest intraday
  decliners first — a loss-ordered value-dip/momentum harvest) and the
  `get_top_movers` tool fallback. moomoo movers (`top-losers`/`heat-proxy`)
  stay as the optional intraday source. Fundamentals/technicals/intraday/
  options are not on the EOD plan, so those chains keep moomoo/yfinance.

- [2026-08-27] **EODHD vendor (daily OHLCV)** - new `dataflows/eodhd.py`
  serves daily bars in the same CSV shape as yfinance/moomoo, wired into the
  `core_stock_apis` chain (`moomoo,eodhd,yfinance`) and as a `--vendor eodhd`
  preset. Key: `TRADINGAGENTS_EODHD_API_KEY`. Free tier 20 calls/day; EOD
  plan $19.99/mo = 100k calls/day @ 1000/min, 30+ years — replaces the moomoo
  K-line quota (100 calls/7 days) the value screener exhausts.

- [2026-08-27] **Value-screener web-timeout fixes** - (1) every moomoo SDK
  call now runs under a 5s wall-clock timeout (`TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`,
  default 5.0) instead of the SDK's own 20s per-call wait, so a degraded
  gateway can't stall a run; (2) the value-dip gating pass pre-filters on
  cheap OHLCV-only technicals (RSI/%b/stop) before the heavy fundamentals
  fetch, dropping ~7 vendor calls/symbol to 1 for non-candidates; (3) the
  web `run_screener` budget is 2400s and a timed-out capability kills its
  whole process tree so no orphaned process holds a moomoo connection.

- [2026-08-26] **Correlation-aware allocation** - the allocation plan
  (`portfolio.allocation_block`, the `get_allocation` analyst tool, and the
  screener's `--alloc`) now accepts return series and, when
  `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY=true`, down-weights names whose
  average pairwise correlation with the rest of the book exceeds
  `TRADINGAGENTS_CORRELATION_THRESHOLD` (default 0.6) by
  `TRADINGAGENTS_CORRELATION_PENALTY_FRAC` (default 0.3) before the
  per-name/per-sector caps - risk-parity style concentration control
  (industry-practice item 1). Names without a measurable return series are
  never penalized (no fabrication).

- [2026-08-24] **Per-role max output tokens + density directives** - new env keys
  `TRADINGAGENTS_MAX_OUTPUT_TOKENS(_QUICK/_DEEP)` cap the LLM output via
  `max_tokens` (quick=analysts/researchers/debaters/trader 6000, deep=RM/PM
  2500, based on measured report sizes + your `min(1,048,576, 1,310,720 - input)`
  formula).
  Every agent prompt now carries a `get_output_budget(...)` directive: dense,
  bounded, tool-call-first (never approximate a number you can fetch).

- [2026-08-24] **OpenRouter provider-ignore routing** - add a configurable
  slow-provider blocklist: set `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` in
  `.env` (comma-separated provider slugs). It is sent as `provider.ignore` in
  the OpenRouter request body via `extra_body`, so OpenRouter skips those
  endpoints (e.g. slow/unreliable ones) on every request. No restriction when
  unset.

- [2026-08-23] **Free computed ratios (no paid Massive plan)** - new
  `strategies/ratios.py` replicates the plan-gated Massive `get_ratios` block
  locally from the project's own canonical statements: EV, EV/EBIT, EV/EBITDA,
  EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash
  ratio, dividend yield, FCF, market cap. Exposed as `get_ratios` on the
  fundamentals analyst (computed, free). Adds the `inventory` canonical alias
  so Quick ratio computes. A latent double-`@tool` bug in analysis_tools.py
  (which broke import once the file grew) was also fixed.

- [2026-08-23] **SEC EDGAR -> Massive insider fallback** - `get_sec_filings` now
  falls back to Massive's Form-4 insider-activity data when official SEC EDGAR
  fails for any reason (HTTP 403 from SEC fair-access throttling, network
  failure, or a non-US ticker with no EDGAR record). The fallback result is
  clearly labelled as insider-activity-only so the agent never mistakes Form-4
  for the full 8-K/10-K set; if both sources fail it returns an explicit
  unavailable message (no fabrication).

- [2026-08-23] **Web UI (sibling project)** - `TradingNew/trading_web/` (outside this
  repo, per the layout rule): a React SPA + FastAPI interface covering every
  capability (batch/pipeline/screener/pre-market/nightly/decision-history/
  reports/raw-read-only) with login security (scrypt passwords, HMAC-signed
  sessions, CSRF, lockout, path-defense, CSP, audit log). See
  `TradingNew/trading_web/README.md`.

- [2026-08-22] **Pre-market review (overnight reviewer)** - closes the gap
  between a close-time decision and the next open: a deterministic arbiter
  (`strategies/pre_market.py` - gap / catalyst-window / re-anchored tranche /
  cap breach -> CONFIRM/REVISE/REJECT), a `PreMarketVerdict` schema + a
  deep-think prompt-variant reviewer (no new graph node), a standalone
  `scripts/pre_market_review.py` for the pre-open gap/anchor path, and an
  opt-in same-night `batch.py` step (`enable_pre_market_review`). Design in
  `docs/pre_market_review.md`.
- [2026-08-22] **Pre-market review follow-up (fixes + features)** - defect
  fixes: the standalone script now extracts the prior plan's entry/stop and
  re-anchors the tranche plan to the measured open (gap/through-stop/adverse-fill
  checks actually run), the batch hook passes `results_dir` so it finds the
  full state JSON, and `_fetch_deltas` prefers a real-time pre-market price
  (Alpaca when enabled else yfinance `fast_info.last_price`) + ATR(14).
  Features: `scripts/nightly_review.py` (drive reviews from the batch summary),
  a paper-book ledger (`pre_market_ledger.jsonl` with pending->realized
  resolution), guarded overnight-headline context for the reviewer, and
  `scripts/decision_history.py` (per-ticker decision series).

- [2026-08-22] **Blank-symbol yfinance hardening** - a whitespace/empty ticker
  (e.g. a malformed LLM tool call in `batch.py --symbols ...`) previously
  leaked yfinance's raw `TypeError: 'NoneType' object does not support item
  assignment` + HTTP-4xx ERROR noise; it now canonicalizes to `""` and raises
  the typed NoMarketDataError, so the router returns one clean
  `NO_DATA_AVAILABLE: blank/empty ticker symbol` sentinel the agents report
  honestly.

- [2026-08-22] **Value Dip gaps (Step-1 + Step-2)** - five more deterministic strategies close the original doc's gaps: `balance_sheet_health` (D/E < 1.0 OR current ratio > 1.5) + `profitability_quality` (FCF + ROE > 15%) as Step-1 gates; the Step-2 technical ladder (`macd_divergence` on Daily RSI/MACD, `volume_dry_up` / `trigger_candle` RVOL>=1.3 / `higher_low_structure` composed into `vdu_entry_setup`), `support_structure` (multi-month base / 200-SMA), and the `decline_driver_check` negative-force screen. Exposed as five new analyst `@tool`s (market: get_macd_divergence / get_vdu_entry_setup / get_support_structure; fundamentals: get_balance_sheet_health / get_decline_driver_check); `value_dip_setup` and the `--scan value-dip` screener now gate on the new rows when measured. Hermetic-tested, doc'd.

- [2026-08-22] **Tranche risk fold (risk governor)** - with `enable_tranche_risk` (+ `tranche_*` keys), the risk governor sizes/throttles against the worst-case 3-tranche scale-in measured from the close + config-frozen weights (never the LLM): the **peak-deployed-at-scale-in** fraction is the per-trade cap the governor bounds (scale-in ties up more capital near the lows), and the **capital-at-risk** budget (sum of per-tranche losses at the hard stop) is enforced via `govern()`'s new `capital_at_risk_pct`/`risk_cap_pct` check. `build_position_contract` gains a weighted `entry_price` hook so the G1 stop/risk matches the tranche execution; the Risk Gate report block shows `Tranche peak-deployed` / `Tranche capital-at-risk`. Hermetic-tested.

- [2026-08-22] **Value Dip + Swing hybrid** - new `strategies/value_dip.py` implements the math from `Strategies/Value_Dip_swing.md` + `Value_Dip_swing_Continue.md` (Bollinger %b, historical valuation Z, FCF yield, breakeven win rate / expectancy, 3-tranche scale-in plan with weighted avg entry + composite stop + capital-at-risk check + blended 1.8R/3.0R, and the hybrid allocation matrix). Six new analyst `@tool`s bound to the market/fundamentals tool loops (`get_bollinger_pct_b`, `get_tranche_plan`, `get_trade_expectancy`; `get_fcf_yield`, `get_valuation_z_score`, `get_value_dip_setup`) so the agents reason over computed numbers, plus a new `--scan value-dip` screener mode. Config `enable_value_dip`; hermetic-tested.

- [2026-08-21] **Per-test timers** - every test runs under a `pytest-timeout` deadline (180s per-test default, thread method, 30-min session cap) so a hung vendor/network call can never block the whole session indefinitely; the live-vendor modules (`value_screener`/`scan_strategies`/`growth_screens`/`structured_agents`) carry a 600s module-level override. See `docs/developer/10-tests-layout.md`.
- [2026-08-21] **True portfolio CVaR (risk governor)** - the governor's daily
  tail budget can now come from the *weighted basket's* historical CVaR
  (`book_risk.portfolio_cvar`) instead of the single analyzed name: set
  `risk_basket_tickers` (comma list) + optional `risk_basket_weights` (k=v pairs
  or JSON) in config/env. Falls back to single-name when unconfigured/unresolvable.
- [2026-08-21] **Risk Gate shows both CVaRs** - with a basket configured, each
  report's `Risk Gate (computed)` block now shows `Analyzed-name CVaR` (the
  analyzed ticker's own tail) next to `Portfolio (book) CVaR — this fed the
  gate`; the same numbers are computed-injected into the Portfolio Manager
  prompt (`**Computed daily-tail CVaR**`) so the PM reasons from them.
- [2026-08-21] **Session-discipline + earnings-quality tool audit** - two more deterministic strategies exposed as analyst `@tool`s: `get_session_discipline` (intraday walk-away rules: giveback / max-daily-loss / past 10:00 ET optimal + psych levels, market node; wraps `momentum.session_flags`) and `get_earnings_quality` (Sloan accruals ratio folded into the forensic trap verdict incl. the accrual evidence trigger; fundamentals node; surfaces `normalized.accruals_ratio` that `screen_ticker`'s trap call had dropped). Bound in `_create_tool_nodes` + prompt; 6 hermetic tests; also documented the previously-omitted `TRADINGAGENTS_ENABLE_MASSIVE_FLAT` / `TRADINGAGENTS_MASSIVE_FLAT_DIR` env keys and sync'd `.env.example`.
- [2026-08-20] **Strategies index** - added `Strategies/index.md`, a navigation map linking every strategy plan doc under `Strategies/` to its implementation modules, config gates, scan modes, and consumers. Wired into the README docs pointer.
- [2026-08-20] **DCF valuation tool** - `get_dcf_valuation` + `strategies/dcf.py`: a pragmatic free-cash-flow DCF the fundamentals analyst can cite (fair value, EV, terminal-value share, WACC from provider data: cashflow statements, 10y treasury, beta, shares/cash/debt). Built from `Strategies/Discounted_Cash_Flow.md`; growth/ERP are analyst overrides; degrades to 'unavailable' if no usable FCF.
- [2026-08-20] **Massive no-data failover fix** - the direct Massive tool wrappers now degrade to an explicit "unavailable" string (instead of raising `NoMarketDataError`) when the vendor lacks a symbol's data, so a batch run falls back to moomoo/yfinance and completes instead of failing the whole symbol. Regression-tested in `tests/test_massive_vendor.py` (8 cases).
- [2026-08-20] **Data providers doc** - `docs/developer/12-data-providers.md` catalogs all **13 data providers** (8 routed vendors: yfinance, FRED, Polymarket, Alpha Vantage, Finnhub, SEC EDGAR, Moomoo, Massive; + 5 direct sources: Alpaca, FMP, Reddit, StockTwits, float_shares), with per-category chains and API-key gates.
- [2026-08-20] **Agent decision-tools** - `docs/developer/11-agent-decision-tools.md` plans + implements six computed decision tools the analyst LLMs now cite: `get_exit_check` (stop/target/action), `get_allocation` (cap-respecting book), `get_regime_components` (vol/trend/chop), `get_consensus` (rating agreement, also injected into the PM), `get_momentum_detail` (pillars/rvol/vwap), `get_beat_miss_sizing` (event multiplier). All bound to market/fundamentals/news tool nodes + hermetic-tested.
- [2026-08-21] **Credit-stress read (FRED OAS)** - `get_credit_spread_read(date)` bound to the market analyst: the ICE BofA US high-yield OAS series (HY `BAMLH0A0HYM2`, CCC & lower `BAMLH0A3HYC`, BB `BAMLH0A1HYBB`) flattened by `strategies/credit_spread.py::credit_stress_level` into a deterministic credit-cycle band (low/high/severe) + a 0..1 de-risk scale (thresholds: HY <3% low / 3.5-4.5% moderate / >5.5% severe; CCC <8% low / 10-12% moderate / >15% severe). FRED aliases `hy_oas` / `ccc_oas` / `bb_oas` added to the macro vendor; the read degrades to explicit 'unavailable' when `FRED_API_KEY` is unset. 8 hermetic tests; docs/README/CHANGELOG kept true.
- [2026-08-21] **Second decision-tool batch** - five more deterministic strategies exposed as analyst `@tool`s so the LLMs cite computed numbers instead of guessing: `get_sector_rank` (11-SPDR 1m/3m momentum + the ticker's sector standing, market node), `get_strategy_quality` (net CAGR / vol / Sharpe / max drawdown over a return series, market), `get_margin_of_safety` ((intrinsic-price)/intrinsic band, fundamentals), `get_composite_rank` (value+momentum composite percentile vs industry peers, fundamentals), `get_tail_risk` (VaR/CVaR tail budget + -10% stress loss, market). Bound in `_create_tool_nodes` + each analyst's tools list/prompt; 12 hermetic tests; ruff-clean.
- [2026-08-20] **Developer docs set** - added `docs/developer/` with 11 focused guides (topology, graph topology + run, dataflow/vendors, strategies, agents/tools, entrypoints, persistence, dev guide, Massive integration, tests layout) covering the *whole* project for a joining developer.
- [2026-08-20] **Massive Flat-File screener (folder, OFF by default)** - the value-screener's `_fetch_ohlcv` reads a Massive day-aggregates folder (`TRADINGAGENTS_MASSIVE_FLAT_DIR` / `massive_flat_dir`, default `data/massive_flat`) ONLY when `TRADINGAGENTS_ENABLE_MASSIVE_FLAT=true` (default OFF), giving bulk-history ATR/ATR-pct/scan bases before the per-ticker vendor chain. Opt-in, >=15-row gate; hermetic-tested. Also validated a live end-to-end `batch.py` run to AAPL (Underweight) exercising the new Massive tools.
- [2026-08-20] **Massive NOI + Flat Files (item 8)** - `massive_noi.py` (WebSocket Net Order Imbalance streamer + `scripts/massive_noi_monitor.py` monitor app) and `massive_flat.py` (bulk Flat-File day-aggregates loader into per-ticker OHLCV for the screener/backtests). Both are **plan-gated standalone utilities** - not batch `@tool`s. NOI needs the Imbalances Expansion add-on; Flat Files need Starter+.
- [2026-08-20] **Massive corporate actions, peers & IPOs (row 5)** - `get_company_peers` gains a `massive` option (`related-companies`, finnhub-format-compatible); `get_corporate_actions`/`get_dividends` (dividends + splits) bind Massive to the fundamentals analyst; `get_ipos` (IPO reference) binds to the news analyst. All entitled on the current tier (probed 200).
- [2026-08-20] **Massive fundamentals/ratios + snapshots (plan-aware)** - `get_ratios` (precomputed EV/EBITDA, P/E, P/B, ROE/ROA, FCF), `get_market_snapshot` (consolidated day/quote), and `get_top_movers` wired to the market/fundamentals analysts + `pipeline.py --universe top-movers-massive`. These endpoints return 403 on the free Basic plan, so all degrade with an explicit "upgrade at massive.com/pricing" message and activate when the plan includes them.
- [2026-10-01] **Massive SEC filing TEXT (10-K sections / risk factors / 8-K items)** - three direct tools on the fundamentals analyst close the one real gap the endpoint audit found: `sec_edgar` owns XBRL facts, the filing LIST and EDGAR full-text search, but had no item-level section extraction. `get_filing_sections(ticker, section?)` returns the 10-K's own item text (the vendor publishes only `risk_factors` and `business`) as **bounded excerpts that state `[+N chars withheld]`** - a risk-factor section runs 53k-69k chars; `get_risk_factors(ticker, include_taxonomy?)` returns the issuer's disclosed risks grouped by vendor category with the supporting text (the taxonomy dictionary is opt-in: a second request on a ~5 req/min plan); `get_8k_filings(ticker)` returns recent 8-K current reports with their `items_text`. **Measured live**: all three honour the `ticker` filter (10/10, 50/50, 10/10 rows). `/stocks/filings/8-K/vX/disclosures` was REJECTED - an AAPL query returned another issuer's rows (no reliable ticker filter), the same defect that defers 13-F. An unknown `section` is named with the published set, never answered with a different section. No config gate: these degrade to an explicit "unavailable" like every direct Massive wrapper. See `docs/massive_integration.md` §3g + Appendix A.
- [2026-08-20] **Massive Form-4 insider activity** - `get_form4_insider(ticker, start, end)` bound to the fundamentals analyst reports net open-market insider buying (buys P minus sells S, excluding grant/exercise A/M) from SEC Form 4 via Massive. 13-F institutional holdings are deliberately NOT wired (the endpoint has no security filter - only filer_cik/filing_date - so a per-ticker aggregate would be misleading); moomoo `get_institution_holdings` remains the source.
- [2026-08-20] **Massive short-interest/short-volume** - `get_short_interest_massive` adds a `massive` `short_interest` vendor (FINRA 2-week settlement: shares short, days-to-cover, avg daily volume); a dedicated `get_short_volume(ticker, start, end)` tool surfaces the daily short-sale volume ratio to the market analyst. Both degrade cleanly via the error taxonomy.
- [2026-08-20] **Massive economy + catalyst OpenD decoupling** - `get_macro_indicators_massive` adds a `massive` `macro_data` vendor (treasury-yields / inflation / inflation-expectations / labor-market, FRED-compatible aliases like `10y_treasury`/`yield_curve`/`cpi`); a deterministic `macro_backdrop` (yield-curve inversion x0.70, elevated 10y breakeven x0.75) keeps the B1 catalyst overlay de-risking near macro stress even when the moomoo OpenD event calendar is down — `fetch_catalyst_data` now degrades per-section instead of nulling the overlay on moomoo failure.
- [2026-08-20] **Massive.com vendor (news sentiment)** - new `dataflows/massive.py` + `get_massive_news`: per-article **structured sentiment** (positive/negative/neutral + reasoning) from `/v2/reference/news`, ticker-filtered; bound to the news/social tool nodes + news analyst; `get_news` chain gains a `massive` vendor (opt-in). Key: `MASSIVE_API_KEY`. US-only additive vendor — see `docs/massive_integration.md`.
- [2026-08-20] **Moomoo period-order + prior-period fix** - the value screener
  used to keep the OLDEST statement period (moomoo lists newest-first) and
  never supplied prior-period values, so the **Beneish M column was always
  `n/a`** and every metric (EY, EV/EBIT, F, Z, EpsYoY...) was computed on
  stale fiscal-2022-era data. The canonical parser is now period-order aware,
  emits `{current, prior}` dicts, skips moomoo `-` sub-item/contra lines, and
  fixes a `d&a` alias that silently aliased depreciation to SG&A. **M now
  computes** (e.g. MT -2.29, WMT -2.72). NetNet staying `no` on large caps is
  expected (needs `CA - TL` negative-threshold), not a bug.
- [2026-08-19] **Finnhub free-tier integration** - live-probed your key and wired the endpoints that work: `get_basic_financials` (EPS/revenue YoY + ROE metrics feed the screener `--min-eps-yoy/--min-rev-yoy/--min-roe` gates and the Fundamentals analyst), `get_insider_activity` (computed 12m net insider change + mspr + trend), `get_company_peers`, and Finnhub as the second-tier `--sector-rank` sector source (FMP → Finnhub → yfinance). All key-gated/guarded, no-fabrication.
- [2026-08-19] **Computed-analysis tools - follow-up batch (6 more)** - `get_regime_read`, `get_volatility_contraction`, `get_orderflow_read` bound to the Market analyst; `get_analyst_verdict` (EY/EV/EBIT/F/M/Z/trap-risk/ROE/YoY), `get_earnings_surprise`, `get_portfolio_weights` bound to the Fundamentals analyst. Full set = 12 computed-signal tools for the analyst LLMs.
- [2026-08-19] **Computed-analysis tools for the analyst LLMs** - `get_swing_set`, `get_relative_strength`, `get_earnings_event_read`, `get_catalyst_scale`, `get_position_sizing`, `get_risk_gate` wrap the deterministic strategy calculators (`strategies/{swing,relative_strength,events,catalyst,size,risk_governor}`) as LangChain tools bound to the market + news analyst tool loops - the agents now reason over computed stops/targets/RS/surprise/catalyst-scale/sizing/risk-gate numbers instead of re-deriving (or inventing) them. All follow the no-fabrication contract (exact numbers or explicit 'unavailable').
- [2026-08-19] **Framework Phase-1 screens** - optional `--min-eps-yoy` / `--min-rev-yoy` (moomoo statement YoY columns; also fixed moomoo markdown `##`-header payloads never reaching the parser), `--min-roe`, `--max-mcap`, `--sector-rank` (SPDR top-3 by 1m/3m momentum), `--revision` (net analyst upgrades 60d), `--inst-accum` (two-quarter institutional %-of-float); new EpsYoY/RevYoY/ROE, Sec/Rank, RevUp, Inst columns; gates only apply to measured values, missing data renders n/a.
- [2026-08-19] **VCP scan (`--scan vcp`)** - `strategies/swing.py::vcp_setup` (the classic 15%->8%->3% volatility-contraction base: strict pivot troughs, last-3 pullback depths vs the base high must contract, deepest pullback within 30%, fading volume across troughs - absent volume never fails); new screener mode with `VCP`/`Brk` columns; `swing_report` carries the VCP block as an extra signal; mode docs in `Strategies/scan.md`. Suite 924 passed / 2 skipped.
- [2026-08-19] **Swing scan + relative strength + catalyst hard veto** - new `--scan swing` screener mode built on `strategies/swing.py` (20-EMA-over-rising-50/200-SMA trend stack, RSI 45-70 band, pullback-into-EMA on fading volume, 1-ATR swing-low stop, 2R/3R targets, T1 scale-out + 20-EMA trail) and `strategies/relative_strength.py` (RS line vs `benchmark_ticker`, 63-day uptrend + new-high position + negative-divergence); PEAD post-earnings entry helpers (`events.py`); optional `catalyst_hard_block_days` that makes the risk governor REJECT new risk inside the earnings window; `Strategies/scan.md` filled with all scan-mode docs. Source: `Strategies/framework.md`. Suite 888 passed / 2 skipped.
- [2026-08-19] **Repo hygiene pass** - full lint cleanup to a green `ruff check` across `tradingagents/`, `scripts/`, `tests/`, `cli/` and the entry scripts, plus defect fixes found by the lint pass: removed a stale `__all__` entry in the Alpaca vendor (`latest_snapshot` -> `get_latest_snapshot`), fixed an unimported `Mapping` annotation, `raise ... from None` for expected data-format errors, explicit `zip(strict=)` everywhere, import-order fix in `batch.py`, deleted the committed scratch file `test.py`; **documentation completed**: `.env.example` now mirrors all 53 supported `TRADINGAGENTS_*` overrides (Alpaca/Finnhub/FMP keys, moomoo tuning, all strategy/catalyst/risk toggles, persistence paths), `docs/api_reference.md` deduped + env table completed, dev-machine paths scrubbed from `docs/AGENT_ONBOARDING.md`. Suite 843 passed / 2 skipped; "pip check" clean (rich / cryptography satisfied).
- [2026-08-19] **Fork changelog (since last remote)** - B2 cross-sectional pipeline (`pipeline.py`: universe -> value-screen -> composite rank -> top-N -> concurrent moomoo batch, with `reports/pipeline_<ts>.md` summaries and per-symbol TOC reports); **A-series analyst tools** (moomoo, optional) `get_institution_holdings` (13F-style institutional % + period change), `get_earnings_surprise_history` (EPS surprise vs estimate per print with day reaction and NaN-safe rendering), `get_expected_move` (option-implied 1-sigma move at the next earnings + price band), wired to the market/fundamentals analysts; **catalyst overlay (B1) on by default** (`enable_events`) plus moomoo earnings-calendar fixes (7-day-inclusive cap, real column normalization, 4-tuple unpacking) verified live (AVGO 2026/Q3 implied move 9.4%, band [328.39, 396.57]); **docs**: `docs/api_reference.md` (config keys, graph flow, vendor contract, overlays) and `docs/howto_end_to_end.md` (screener -> pipeline -> reports). Suite 843 passed / 2 skipped, clean exit; no env/credentials committed.
</td></tr>
</table>
- [2026-07] **TradingAgents v0.3.1** released with correctness and stability fixes: Alpha Vantage look-ahead filtering, graph-router crash-safety, graph-shape-aware checkpoint resume, working crypto sentiment sources, a configurable LLM retry budget, Bedrock API-key auth, and Claude Sonnet 5 / Fable 5 support. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-06] **TradingAgents v0.3.0** released with a verified data-access contract, an expanded provider registry (NVIDIA, Kimi, Groq, Mistral, Bedrock, and any OpenAI-compatible endpoint), FRED and Polymarket data vendors, a current-generation model catalog, and a CI gate.
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, and Reddit chatter into a single sentiment read to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions, determining the timing and magnitude of trades.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.12
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For Azure OpenAI, copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For AWS Bedrock, install the extra with `pip install ".[bedrock]"`, set `llm_provider: "bedrock"`, configure AWS credentials (environment variables, `~/.aws/credentials`, or an IAM role) and `AWS_DEFAULT_REGION`, and use a Bedrock model ID, e.g. `us.anthropic.claude-opus-4-8-v1:0`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

For any other OpenAI-compatible server (vLLM, LM Studio, llama.cpp, or a custom relay), use `llm_provider: "openai_compatible"` and set the endpoint via `backend_url` (or `TRADINGAGENTS_LLM_BACKEND_URL`), e.g. `http://localhost:8000/v1` for vLLM or `http://localhost:1234/v1` for LM Studio. The model is whatever your server serves. No key is needed for local servers; set `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires one.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```

The TUI renders Nerd Font icons (status, team, header glyphs) when the terminal font supports them. Set `TRADINGAGENTS_NERDFONT=0` in `.env` to fall back to plain text/ASCII for terminals without a Nerd Font.

### Markets and tickers

TradingAgents works with any market Yahoo Finance covers, using the exchange-suffixed ticker. Company identity and the alpha benchmark resolve automatically per market.

- US: `AAPL`, `SPY`
- Hong Kong: `0700.HK` · Tokyo: `7203.T` · London: `AZN.L`
- India: `RELIANCE.NS`, `.BO` · Canada: `.TO` · Australia: `.AX`
- China A-shares: Shanghai `.SS`, Shenzhen `.SZ` (e.g. `600519.SS` for Kweichow Moutai)
- Crypto: `BTC-USD`, `ETH-USD`

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-5.5"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Reproducibility

TradingAgents is LLM-driven, so two runs of the same ticker and date can differ. This is expected for a research tool built on language models, not a defect. The variation comes from a few distinct sources, and it helps to separate them.

Language model sampling is non-deterministic. Even at a fixed temperature, providers do not guarantee byte-identical output across calls, and reasoning models (the default GPT-5.x family, and any thinking-mode model) vary the most because their internal reasoning is itself sampled.

Live data moves. News, StockTwits, and Reddit return different content as time passes, so a run today sees different inputs than a run last week even for the same historical trade date. Pin the analysis date to hold the price and indicator window fixed, but the social and news sources still reflect "now".

To reduce variation you can lower the sampling temperature. Set `temperature` in your config (or `TRADINGAGENTS_TEMPERATURE` in `.env`); lower values make models that honor it more repeatable. The current curated models are reasoning-first and largely ignore temperature, so for tighter reproducibility use a non-reasoning model, which you can set explicitly via the Custom model ID option.

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["temperature"] = 0.0
# Reasoning models ignore temperature. For tighter reproducibility, set a
# non-reasoning deep/quick model explicitly (e.g. via the Custom model ID option).
```

What does not vary anymore: the analyzed company identity is resolved deterministically from the ticker before any agent runs, and the market analyst grounds exact price and indicator claims in a verified data snapshot. Earlier reports of "different companies" or fabricated price levels across runs are addressed by these two mechanisms.

Backtest results are not guaranteed to match any published figure. Returns depend on the model, the temperature, the date range, data quality, and the sampling above. Treat the framework as a research scaffold for studying multi-agent analysis, not as a strategy with a fixed, replicable return.

> [!IMPORTANT]
> **⚠️ The sections below are additions made in this fork and are not part of the original upstream TradingAgents project.**
>
> ---
>
> **Docs**: [`docs/api_reference.md`](docs/api_reference.md) (config keys, graph, vendor contract, overlays), [`docs/howto_end_to_end.md`](docs/howto_end_to_end.md) (screener → pipeline → reports), the full developer map in [`docs/developer/`](docs/developer/00-index.md), and the strategy-plan index in [`Strategies/index.md`](Strategies/index.md).
>


<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Batch runner

A headless, concurrent runner ships alongside the interactive CLI. Run several symbols at once, auto-save reports in the same layout the CLI produces, and get a machine-readable summary — no interactive prompts.

```bash
python batch.py --symbols NVDA MSFT AAPL
python batch.py --symbols NVDA MSFT AAPL 0700.HK --date 2026-07-22 --workers 4
python batch.py --symbols NVDA --depth deep --analysts market news
```

Options: `--symbols` (required), `--date` (default today), `--workers` (default 3), `--depth` (`shallow`/`medium`/`deep`, default `deep`), `--analysts` (default all four teams), `--verify` (advisory LLM report-verification pass after each symbol — each analyst report is checked against its `tool_evidence.json` leaves and `verify_flags.json` is written into the report tree; never blocks delivery). Each symbol gets its own memory log (`~/.tradingagents/memory/<TICKER>.md`), reports land in `./reports/<TICKER>_<timestamp>/`, and a per-run summary is appended to `./reports/batch_summary_<timestamp>.jsonl`. Configuration (provider, models, API key) is inherited from `.env`. To run the verifier manually against an existing tree: `py -3.12 scripts/report_verify.py --report-dir reports/<TICKER>_<timestamp>`.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Extended data sources

Beyond the core price, fundamental, and news vendors, TradingAgents can pull additional free, decision-relevant signals (all optional — a vendor failure degrades gracefully instead of aborting a run):

- **Options market** (yfinance) — implied volatility, put/call open-interest and volume skew, surfaced to the market analyst.
- **SEC EDGAR filings** — 8-K (material events), 10-K/10-Q (reports), S-1/S-3 (capital raises), SC 13D/G (stake disclosures), surfaced to the news analyst.
- **Short interest / float** (yfinance) — days-to-cover, short % of float, ownership split, surfaced to the market analyst.
- **Analyst ratings & price targets** (Finnhub) — recommendation trends and consensus targets, surfaced to the fundamentals analyst.
- **Earnings calendar** (Finnhub) — upcoming earnings dates and EPS surprises, surfaced to the news analyst.
- **News with structured sentiment** (Massive.com) — per-article sentiment (positive/negative/neutral) + reasoning, surfaced to the news/social analysts via `get_massive_news`. Set `MASSIVE_API_KEY` (or `TRADINGAGENTS_MASSIVE_API_KEY`). US-centric additive vendor; see `docs/massive_integration.md`.
- **Macro economy + catalyst OpenD decoupling** (Massive.com) — `get_macro_indicators` gains a `massive` vendor (treasury yields / inflation / inflation-expectations / labor-market, FRED-compatible aliases); a deterministic `macro_backdrop` (yield-curve inversion / elevated breakevens) keeps the B1 catalyst overlay de-risking near macro stress even when the moomoo OpenD event calendar is unavailable.
- **Short interest / short volume** (Massive.com) — `get_short_interest` gains a `massive` vendor (FINRA 2-week settlement, days-to-cover / shares short); a dedicated `get_short_volume` tool surfaces the daily short-sale volume ratio to the market analyst.
- **SEC filing TEXT** (Massive.com) — `get_filing_sections(ticker, section?)` returns the 10-K's own item text (published sections: `risk_factors`, `business`) as bounded excerpts that state what they withheld, `get_risk_factors(ticker, include_taxonomy?)` returns the disclosed risks grouped by vendor category with supporting text, and `get_8k_filings(ticker)` returns recent 8-K current reports with their item text — all bound to the fundamentals analyst, and the one narrative-filing surface no other reader in this tree carries (`sec_edgar` has the XBRL facts, the filing list and full-text search, not the sections).
- **Form-4 insider activity** (Massive.com) — `get_form4_insider(ticker, start, end)` surfaces net open-market insider buying (P−S, excluding grant/exercise) to the fundamentals analyst.
- **Fundamentals ratios + market snapshots** (Massive.com, plan-gated) — `get_ratios` (precomputed EV/EBITDA, P/E, ROE...) to the fundamentals analyst; `get_market_snapshot` / `get_top_movers` to the market analyst; `pipeline.py --universe top-movers-massive`. These 403 on the free Basic plan and degrade with an explicit upgrade message — they activate when the account's plan includes them.
- **NOI + Flat Files** (Massive.com, plan-gated) — `massive_noi.py` (WebSocket NOI monitor app) and `massive_flat.py` (bulk OHLCV loader) are standalone utilities: the screener's `_fetch_ohlcv` reads a Massive day-aggregates folder when the `enable_massive_flat` toggle is on (bulk ATR/scan bases), a NOI monitor app consumes the WebSocket feed, and `scripts/validate_massive_flat.py` sanity-checks a dropped CSV. NOI needs the Imbalances Expansion add-on; Flat Files need Starter+.
- **Corporate actions, peers & IPOs** (Massive.com, entitled) — `get_company_peers` gains a `massive` option (`related-companies`); `get_corporate_actions`/`get_dividends` (dividends+splits) bind Massive to the fundamentals analyst; `get_ipos` (IPO reference) binds to the news analyst.

Each source is a vendor behind the same `route_to_vendor` interface and is toggled per-category in `default_config.py` (`options_data`, `sec_filings`, `short_interest`, `analyst_ratings`, `earnings_calendar`). Set `finnhub_api_key` (or `TRADINGAGENTS_FINNHUB_API_KEY`) for the two Finnhub sources.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Moomoo OpenAPI vendor

Moomoo OpenAPI (formerly Futu OpenAPI) is available as an additional vendor behind the same `route_to_vendor` interface. It serves quotes/candlesticks, technical indicators, F10 financials, news, options chains, short interest, analyst consensus, the earnings calendar, and insider trades through the **local OpenD gateway** (TCP, default `127.0.0.1:11111`).

- **No credentials in `.env`** — install OpenD, log in once with your (free) moomoo account and tick "remember password". The project only connects to the gateway.
- **Headless autostart** — set `TRADINGAGENTS_MOOMOO_AUTOSTART=true` (default in `.env`) and `TRADINGAGENTS_MOOMOO_ACCOUNT=<your moomoo ID>` (not a password); the vendor launches OpenD with `-login_by_remember=1` when it is not running. `TRADINGAGENTS_MOOMOO_OPEND_PATH` overrides executable discovery. Note: OpenD is a local desktop gateway — inside Docker, moomoo simply degrades to the fallback vendors unless OpenD is reachable from the container.
- **Analyst parallelism (opt-in)** — set `TRADINGAGENTS_ANALYST_CONCURRENCY=2` (or `analyst_concurrency` in config) to run the analyst teams concurrently, each in its own thread with isolated messages. Multiplies LLM/provider load and free-tier quota burn — start with 2, keep 1 (default) for rate-limited setups.
- **Graceful fallback** — when OpenD is down, logged out, or lacks quote permission for a market, the router emits `DATA_UNAVAILABLE`/`NO_DATA_AVAILABLE` and falls back to the next configured vendor (yfinance, finnhub, …). Free quote rights cover US equities (LV3 promo), HK LV1, and crypto; A-shares and LSE/India are not covered for global accounts.
- **Financial statements honor the tool contract** — `get_balance_sheet`, `get_cashflow`, and `get_income_statement` accept the same `freq` (`annual`/`quarterly`) and `curr_date` arguments as the yfinance and alpha_vantage vendors: `freq` selects the annual vs. quarterly report type on the moomoo SDK, and `curr_date` filters out statements published after the trading day (look-ahead guard). `get_fundamentals` accepts `curr_date` the same way.
- Covered by default in `data_vendors` chains (`moomoo,yfinance` for prices/indicators/fundamentals/options/short-interest, `moomoo,finnhub` for ratings/earnings, `fred,moomoo` for macro). Prediction markets use `polymarket,moomoo` — Polymarket first, with moomoo's event contracts (category → series → event → contract → snapshot, live YES probabilities) as the fallback. Event contracts are server-gated to moomoo SG/MY accounts; other regions fall back to Polymarket automatically.

**Decision-quality tiers** (all moomoo-only, optional, degrade to a `DATA_UNAVAILABLE` sentinel when OpenD is down or gated):
- **Tier 1 — new evidence classes:** `get_capital_flow` (weekly net inflow by order size + session distribution → Market Analyst), `get_smart_money` (ARK institutional activity → Fundamentals), `get_economic_calendar` (dated CPI/FOMC/payroll catalysts → News), `get_fed_watch` (market-implied rate probabilities → News).
- **Tier 2 — enrichment:** `get_market_breadth` (sector heat map + rise/fall distribution → News), `get_revenue_breakdown` (segment mix and concentration, one table per vendor dimension — shares are comparable only inside a dimension → Fundamentals), `get_corporate_actions` (dividends/splits → Fundamentals), `get_earnings_catalyst` (historical earnings implied move + IV crush → News, feeds catalyst-risk sizing).
- **Tier 3 — accuracy infra:** the memory-log realized-return path uses moomoo's trading-day calendar for exact holding-day counting (falls back to the old calendar heuristic when OpenD is unreachable or the market is unsupported).

The `batch.py` runner accepts a `--vendor moomoo|yfinance|default` flag to force a vendor-chain preset across all categories per run.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Value watchlist screener

`scripts/value_screener.py` builds a master watchlist *before* spending analyst LLM budget: it screens each symbol through the same `route_to_vendor` chain (`fundamental_data` defaults to `moomoo,yfinance`), translating vendor output (CSV/markdown/JSON/text) into canonical line items and computing the classic screens — **EV/EBIT (Acquirer's Multiple), Earnings Yield, Piotroski F-Score, Beneish M-Score, Altman Z-Score and net-net** (see [`strategies/value_strategy.md`](strategies/value_strategy.md) and `strategies/Math.md` for the playbook). Missing rows render `n/a`, never a fabricated number.

The daily-changing universe can come from moomoo's intraday **top-movers"/"heat-proxy" rank** (领跌/领涨榜) — the biggest decliners at call time — so the watchlist rotates with the market:

```
python scripts/value_screener.py -u heat-proxy -n 50 -d 2026-06-30
```

`heat-proxy` is US-only (stocks only - ETFs/ETNs/funds/indices are excluded), takes the
official hot master (gainers+losers, hottest first) and keeps the losers of the moment,
then gates to **price ≥ $15, 0 < P/E (TTM) ≤ 40, market cap ≥ $10B**
(`--price-min 15`, `--pe-max 40`, `--min-mcap 10000000000`) plus
**30-day avg volume ≥ 1M shares** (`--min-avg-vol`) and
**ATR(14) ≥ 2% of price** (`--min-atr-pct`)
and **market cap ≥ $100B** (`--min-mcap`, default; float cap NEVER exceeds total
cap, so the total-cap floor covers the “cap or float cap ≥ $100B” rule) before
the value screens run. It uses moomoo's official intraday **trade rank** (price
movement), which is **not** the in-app **Heat List** — and the Heat List is
**not** unavailable: `OpenQuoteContext.get_hot_list` (`Qot_GetHotList`, the
hot-discussion rank) returns each name's `search_heat`, `trade_heat` and
`news_heat` plus their equal-weighted `average_heat` (verified live 2026-09-18 —
US `all_count` 9,072, HK 3,030). The two measure different things — attention
vs. price — so `heat-proxy` is a misnomer kept for CLI compatibility, not a
stand-in for a missing endpoint. To use the literal app Heat List today, save
its top symbols to a file and pass `-f list.txt`. Output includes the day's change, name, and a
screen-per-column table; pick from the ranked rows. Each run also saves
the watchlist to `screener/watchlist_<finish_timestamp>.md` (e.g. `screener/watchlist_20260817_180415.md`,
same `%Y%m%d_%H%M%S` format as reports; configurable via `--out-dir`; the prefix is
this screen's own, so the Value score screen's `value_score_*.md` report in the same
folder is never deleted by a Screener run).
Requires OpenD running +
logged in (same as every moomoo feature), and fails loudly if unavailable.

The same loss-ordered idea works without moomoo/OpenD via the EODHD bulk
real-time feed — one call, no quota, no gateway:

```
python scripts/value_screener.py -u eodhd-losers -n 500 --scan value-dip -d 2026-08-31
```

`eodhd-losers` takes the biggest intraday decliners by change% from the ~18k-row
US feed (`-n` up to the whole feed; moomoo movers cap at 200), applies
`--price-min` on the feed's live close, and runs the same per-symbol
mcap/PE/ATR gates + two-stage scan afterwards. The feed rows carry price +
change only (no name/mcap/type), so the seed is **equity-filtered** against
the EODHD exchange-symbol common-stock list (one cached call) — warrants /
units / leveraged ETFs, which dominate the intraday losers, are dropped before
the scan (degrades to the unfiltered list if the reference call fails).
Adding `--value-dip-loose` relaxes the value-dip entry to `RSI<=35 OR %b<=0.10`
(was AND) and appends a ranked **near-miss table** naming the gate each near
candidate missed — the daily practical watchlist, honestly labelled.
`--knife-z -2.5` enforces the falling-knife velocity-z guard: candidates whose
3-day price velocity z drops below -2.5 are blocked (unresolved cascade), not
just flagged.

Numeric hygiene: statements reported in a non-USD currency (JPY etc., e.g.
many ADRs) are refused by the USD-only metrics (EV/EY/Acquirer/Z/net-net
render `n/a` instead of mixing currencies), and the day's % change is
normalized to a fraction regardless of the market session. `0` disables any gate.

### The broker-panel value screen (`scripts/value_score_screen.py`)

A second, narrower screen applies one broker app's filter panel verbatim — market
cap ≥ $10B, 0 < P/E (TTM) ≤ 33, P/B ≤ 9, P/S (TTM) ≤ 8, Price-to-Cash-Flow (TTM) ≤ 25 —
keeps only the names **down ≥ 2% on the day**, adds optional anchors (`--roe-min`,
`--chg5d-max`, `--rsi-max`, the NYSE/Nasdaq common-stock gate, and the
US-domicile gate `--exclude-foreign`), then ranks the
survivors by the engine's own `fundamental_score` composite and prints only the names
clearing `--fundamental-score-min` (default 50 — the flag was `--score-min` before
2026-09-28), then filters that list again on the engine's own `technical_score`
composite, keeping only the names at or above `--tech-score-min`
(default 50 — the `TECH_BANDS` `neutral` edge, so that cut is an engine boundary and not
a free research cut like `--fundamental-score-min`; `0` skips the pass and its per-name
OHLCV fetch):

```
py -3.12 scripts/value_score_screen.py --roe-min 15 --chg5d-max 3 --rsi-max 55 --limit 60
```

`--panel <date>` scores those names against the built SEC EDGAR XBRL panel for that
date (`data_cache_dir/panels/<date>.json`, one file per date, cached forever) instead
of the run's own cross-section, so the percentile is market-relative; the report prints
which denominator it used, and a candidate the panel does not carry is refused by name
rather than scored as 0. The composite is `RESEARCH_ONLY` — a tie-aware percentile with
no band table — and reaches no executor gate. The `tech` column is the engine's
`technical_score` over the name's own bars (the same components the run card and the
`get_technical_score` tool read), band-labelled by its own table; a name whose composite
cannot be measured is **withheld, never passed**, so it does not appear in the qualifying
table and its reason is printed instead. `--exclude-foreign` keeps only **US-domiciled
issuers**, which removes foreign companies *and* their US-listed ADRs in one pass: it reads
the ISSUER's country (Yahoo), not the listing venue, and an ADR's country is the issuer's
(KSPI → Kazakhstan, BABA → China), so the `--exchanges` gate alone never removes one — the
EODHD symbol list reports the *exchange's* country (`USA` for all 50,973 US rows), calls an
ADR `Common Stock`, and gives it a US-prefixed ISIN. A name whose country cannot be fetched
is dropped too (**fail-closed**, like the ratio gates) and counted separately, so a vendor
outage reads as a drop count rather than a clean empty list. OpenD supplies the server-side Screening
V2 stage; `--no-moomoo` falls back to the deepest decliners and labels the run a
partial scan. Runnable from the `trading_web` app as its **Value score** screen
(`/value-score`) - every flag above is a field, blank keeps this script's own
default and `0` disables that gate - and the app lists what it writes under
Reports → **Screen reports** (the `screener/` markdown is a file, not a run
folder, so it has its own list there). See
`docs/implementation_plan_value_screen_score.md`.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Decision quality

The Portfolio Manager's structured output now captures the full risk-adjusted decision, not just a rating:

- `confidence` (0–1) — conviction in the decision.
- `position_size` — an explicit, risk-capped size that supersedes the trader's proposal.
- `stop_loss` — a risk-derived stop level.
- `consensus` (`high`/`low`) — a dissent flag when the aggressive/conservative/neutral analysts materially disagree.

The decision log also feeds an aggregate track record back into the Portfolio Manager: on each same-ticker run it injects the historical directional win rate, mean realized return, and mean alpha, so future decisions weigh past accuracy.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Report format (consolidated hierarchy + Table of Contents)

Every run writes a per-section tree (`1_analysts/`, `2_research/`, `3_trading/`, `4_risk/`, `5_portfolio/` — raw per-agent markdown) plus a consolidated `complete_report.md`. The consolidated file auto-demotes each agent's own headings 3 levels so its outline sits strictly under its role label:

```
#  Trading Analysis Report: <ticker>    ← document
## I. Analyst Team Reports              ← team
### Market Analyst                      ← role
  #### <the analyst's own title>        ← agent content
    ##### <their sections>
    ###### <details>
```

The per-section files (`1_analysts/market.md`, `2_research/bull.md`, …) keep their own heading levels — only the consolidated view is demoted by three — but they are **not** byte-identical to the model's raw output: the debate/trader/risk sections go through the readable pass (paragraph spacing, and `### Round N` separators when a debate ran several rounds), and any section can carry a truncation marker. `complete_report.md` also opens with an auto-generated **Table of Contents** (GitHub-anchor links to every team and role).

To re-render the consolidated report for an existing folder (e.g. after a formatter change) without re-running the analysis — preserving the `Risk Gate (computed)` block when present:
```bash
py -3.12 scripts/rebuild_complete_report.py reports/SFTBY_20260819_115450
py -3.12 scripts/rebuild_complete_report.py      # all folders
```

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Operational hardening

- **Thread-safe configuration** — `set_config`/`get_config` are thread-local, so concurrent batch workers never leak per-symbol overrides into each other.
- **Vendor-result cache** — successful vendor fetches are cached on disk under a TTL (default 6 hours) to avoid re-burning free-tier API quotas; news is never cached, and failures are never cached.
- **Vendor-served logging** — the routing layer logs which vendor answered each call, making free-tier quota burn visible.
- **NaN-safe options chains** — yfinance option chains frequently carry missing/`NaN` open-interest, volume, and implied-volatility values; the options vendor skips non-finite values when summing (missing counts contribute 0) instead of crashing the call.
- **Reddit rate limiting** — Reddit fetches are paced process-wide to avoid 429s, with a `TRADINGAGENTS_DISABLE_REDDIT=1` kill-switch for heavy batch days.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Decision hardening (compute, don't narrate)

Spec: [`Strategies/decision_hardening_spec.md`](Strategies/decision_hardening_spec.md).
All config-gated, off by default:

- **G1 position & stop contract** - `tradingagents/strategies/contract.py`:
  size = min(Kelly, risk/stop) x vol x flow x agreement, 2x-ATR stop, with an
  audit reason string; graph attaches `position_contract` when
  `enable_position_contract` is on.
- **G2 confidence calibration** (`strategies/calibration.py`) - bucket
  realized win-rates from the ledger into `calibrated_confidence` and a
  calibration table for the PM (`enable_calibration`).
- **G3 measured consensus** (`strategies/consensus.py`) - `agreement_score`
  replaces the binary narrative flag; feeds G1. With `enable_independent_vote`
  the agreement comes from the INDEPENDENT pre-debate stances (no
  conformity/adversarial-persuasion bias) instead of the debate transcript.
- **G4 sentiment decay/velocity** (`strategies/sentiment.py`) - recency
  half-life weight, credibility factors, surprise z-score vs 30d baseline.
- **G5 threshold gate** (`scripts/evaluate_config_gate.py`) - walk-forward +
  PBO before tuning any new default (`enable_threshold_gate`).
- **B2 cross-sectional pipeline** (`pipeline.py`) - screens the universe
  (positional/file tickers or moomoo's top-losers/heat-proxy movers) through
  the value-screener engine, ranks by the EY+momentum+52w composite, picks
  top-N, and runs them through the batch runner (moomoo-first) — one command
  to `reports/pipeline_<ts>.md` + per-symbol report folders with TOCs.
- **A-series analyst tools (moomoo, optional)** - `get_institution_holdings`
  (13F-style institutional % + period change), `get_earnings_surprise_history`
  (EPS actual vs estimate per print + day reaction + implied move, with
  NaN-safe rendering), and `get_expected_move` (option-implied 1σ move at the
  next earnings + price band) — wired to the market and fundamentals analysts.
- **B1 scheduled-catalyst overlay** (`tradingagents/strategies/catalyst.py`) -
  deterministic catalyst sizing (the Phase-4 PEAD wiring). `enable_events` is
  **on by default**; the graph folds earnings (next print date + last surprise side +
  market-implied move / IV crush), HIGH-importance economic events (CPI, FOMC,
  payrolls, ...), and Fed-watch meetings into a `0..1` position scale and a
  verdict (`earnings-window` / `earnings-hard-block` / `macro-catalyst` /
  `fed-catalyst` / `no-imminent-catalyst`). The scale multiplies the overlay's
  `position_scale` and caps the G1 contract (`catalyst_scale`, included in its
  reason string); the guarded fetch returns None (neutral) when OpenD is
  unavailable, and the rule never scales **up** beyond the base - it is
  pre-event de-risking. With `catalyst_hard_block_days > 0`, an earnings print
  inside that window makes the risk governor **REJECT** new risk outright
  (the framework's "never initiate" rule).
  Tuning keys: `catalyst_window_days`, `catalyst_baseline_move`,
  `catalyst_macro_window_days`/`_scale`, `catalyst_fed_window_days`/`_scale`,
  `catalyst_miss_scale`, `catalyst_scale_floor`, `catalyst_hard_block_days` (0 = off).

Regression status: full suite passes (1153 passed / 2 skipped / 56 subtests).


</td></tr>
</table>

## Research



Researched trading methods implemented as pure, offline-testable modules under
`tradingagents/strategies/` (plan: [`Strategies/enhancement_plan.md`](Strategies/enhancement_plan.md)).
All are **config-gated and off by default** (`default_config.py`); enable per phase
only after validating in the evaluation harness:

- **P0 eval** `evaluate.py` - cost-adjusted metrics, deflated Sharpe (multi-trial
  penalty), walk-forward splits, backtest-overfit flag, drawdown/CAGR.
- **P1 regime** `regime.py` - realized-vol percentile, 200-SMA trend, choppiness,
  optional 2-3 state HMM label (hmmlearn); `enable_regime`.
- **P2 sizing** `size.py` - quarter-Kelly, smoothed volatility targeting, ATR
  stops, CVaR budget; `position_sizing` (`kelly|vol_target|flat`), `target_vol`.
- **P3 factors** `factors.py` - 12-1m momentum, 52-week-high distance, vol-adjusted
  momentum and a cross-sectional composite rank folding the value screens.
- **P4 events** `events.py` - earnings surprise, post-earnings-drift side, and
  catalyst-risk multipliers; **B1 wiring** in `catalyst.py` folds earnings /
  macro / Fed-watch into a position scale + verdict applied by the graph when
  `enable_events` is on (see Decision hardening).
- **P5 reflection** `reflection.py` - JSON-lines post-trade ledger, decayed
  analyst hit-rates, critique hints, ticker recall; `enable_reflection`.
- **Value-style hardening (V1-V5)** - `strategies/normalized.py` (5y
  median-margin normalized EBIT, historical percentiles, Sloan accruals,
  and a LOW/MED/HIGH trap verdict surfaced as the watchlist **Trap** column),
  `strategies/portfolio.py` (hard per-name/sector caps, residual cash),
  `strategies/exits.py` (stop-to-breakeven, ATR targets, rebalance cadence). The V5 computed-context
  snippets were removed (write-only state read by no agent; see CHANGELOG).
  V2 wires value+momentum composite ranking into the screener
  R0-R4: deterministic **RiskGovernor** gate (PASS/WARN/REJECT), stress/shock
  scenarios and CVaR book risk (`strategies/book_risk.py`), escalation via
  `risk_halt`, and a `risk_audit.jsonl` trail (`scripts/risk_report.py`).
  Plan: `Strategies/risk_management_plan.md`.
  (`--rank composite` / `enable_composite_rank`), alloc block via
  `--alloc` (+ Qlib Topk-Drop / enhanced-index behind `enable_topk_drop` /
  `enable_enhanced_index`), contract exits via `enable_exits`.
  Plan: `Strategies/value_style_gap_plan.md`.
- **DSA decision quality (advisory, default off)** - `strategies/decision_guardrail.py` (post-PM downgrade-only stabilizer, risk-cap at Hold, score<->rating consistency, confidence cap on stale data; `enable_decision_guardrail`). Research: `docs/design_daily_stock_analysis_research.md`.
- **Vibe-Trading transfer (advisory, default off)** - `dataflows/market_router.py` now carries price-caliber +
  volume-unit provenance (`price_caliber`/`volume_unit` on `VendorResult`; `caliber_consistency` warns on mixed
  adjusted/raw across vendors - the dividend-gap / board-lot class of bug), `backtest_engine` next-bar fill
  semantics + lookahead sentinel (`fill_on_next_bar`; signals fill at T+1 close), fills-vs-targets reporting
  (`position_target`/`position_filled`), persistent `invalidation_ledger` + `--invalidate` CLI (decision
  history + action-report auto-breach), `run_card.json` per report tree (config hash/commit/LLM/verdict),
  versioned cache keys + no-forming-bar staleness guard (`vendor_cache` v2, news cache v1), hash-chained
  tamper-evident `risk_audit` ledger (`--verify-chain`), and `strategies/alpha_zoo.py` (AST purity gate +
  bounded evaluator + `scripts/factor_bench.py` rank-IC bench). Design: `docs/design_shadow_account.md`.
- **Measurement (advisory, default off)** - `strategies/prediction_ledger.py` (W1-1: log every
  decision as a scorable prediction row; W1-3 MAE/MFE + stop/target hit scoring against realized closes),
  `strategies/llm_cost.py` (W1-8: provider rate-table cost estimate for quality-per-dollar); wired into the
  graph behind `enable_prediction_ledger`.
- **Validation guards (W2, advisory)** - `strategies/evaluate.py` gains `purged_cpcv_splits` /
  `cpcv_overfit_mask` / `oos_split` (combinatorial purged CV + out-of-sample bands); `bench_zoo` reports OOS
  rank-IC, walk-forward mean IC, CPCV overfit flag, and deflated IC; `factor_proposal_loop` requires a
  trailing-OOS IC for factor adoption.
- **Data integrity (W3, advisory)** - `strategies/data_quality.py` (W3-1 decision-level
  quality score + tier, W3-2 cross-vendor disagreement flag, W3-4 fundamentals-PIT invariant),
  `strategies/falsification.py` (W3-7 structured numeric thesis invalidation auto-monitored into the
  invalidation ledger).
- **Measurement (W1-2/4/6/7, advisory)** - `strategies/calibration.py` (confidence
  calibration bins + per-agent scorecard from the prediction ledger), `evaluate.benchmark_table`
  (strategy vs market + simple-strategy comparators; `strategy_quality_report --benchmark SPY`),
  prediction-ledger auto-invalidation on stop-hit outcomes.
- **Architecture (W4, advisory)** - `strategies/domain_bundles.py` (5 composite per-analyst
  domain tools over the 146 atomic ones + news-relevance profile), `strategies/typed_state.py` (immutable
  AnalystSummary/ResearchVerdict/TradeProposal/RiskVerdict/Decision artifacts + compact summarizer),
  `falsification.evaluate_debate_claims` (judge grounding: cites-only-computed metrics, auto-reject
  already-invalidated theses).
- **Regime + scenario (W1-10/W2-11/W4-6, advisory)** - `strategies/regime_performance.py`
  (per-regime outcome tabulation, computed stress grid, cross-asset macro regime Risk-On/Contraction/
  Stagflation), `scripts/agent_ablation.py` (W1-11 drop-one measurement harness).
- **Costs/capacity/actions (W2-6..10, advisory)** - `strategies/backtest_models.py` gains
  square-root market impact (from ADV+spread), one-way turnover, capacity-vs-ADV, short-borrow cost, and
  corporate-action price adjustment; `pit_registry.universe_membership` guards survivorship (W2-10).
- **Ops + polish (W1-5/W3-5/W3-6/W3-8/W4-5/W4-7/W4-8, advisory)** - `strategies/quant_baseline.py`
  (quant-only baseline for side-by-side LLM comparison), `strategies/options_surface.py` (IV rank/skew/OI/
  expected-move/VRP), `strategies/integrity_tools.py` (thesis-evidence matrix, prompt-injection detection,
  complexity report), `llm_clients/tier_router.py` (hybrid model tier), `strategies/monitor.py` (alert
  notifier), `scripts/factor_bench.py --benchmark` model-vs-model.
- **DSA robustness (advisory, default off)** - `dataflows/market_router.py` (market classifier + opt-in per-market
  vendor priority `market_source_priority` + gap-fill; default path bit-identical), `dataflows/vendor_breaker.py`
  (thread-safe 3-fail/300s circuit breaker + half-open probe + negative capability cache), `dataflows/effective_date.py`
  (effective-trading-date calendar: weekend/holiday -> previous session, pre-close -> prior Friday), `dataflows/schema.py`
  `VendorResult` honesty fields (`fallback_from`/`is_stale`/`data_quality`/`missing_fields`).
- **DSA polish (advisory, default off)** - `strategies/skills.py` + `strategies/skills/*.yaml` (declarative strategy-skill
  DSL: instructions/tools/market regimes/priority + bounded +-20 score adjustments, regime-from-opinion thresholds
  >=70/<=30/35-65, router precedence user->regime->priority; `enable_skill_overlays`/`skill_dir`),
  `strategies/news_relevance.py` (deterministic relevance scoring, official-source boost, spam admission, degrade
  triple - 'no news' never means 'search failed'; `enable_news_relevance`), `dataflows/news_cache.py` (owner-wait
  coalescing TTL cache, one fetch per key under concurrency).
- **DSA reporting (advisory, default off)** - `strategies/report_disclosure.py` (computed driver attribution sum-to-100,
  consensus support/oppose readout, `watch_conditions`/`next_check_time` fast-path rows, >=1 `invalidation_conditions`
  per decision with manual fallback, sources-used-vs-empty + models disclosure footers; `enable_report_attribution`),
  appended to `5_portfolio/decision.md` by `reporting.write_report_tree`.
- **Qlib Phase 1 (advisory, default off)** - `strategies/factor_expressions.py`
  (Alpha158-style 16-factor profile via `get_factor_profile`, expression-string
  cache, learn/infer train-only moments), `strategies/signal_analysis.py` (rank
  IC/ICIR, quantile long-short, IC-decay, pred-autocorrelation; the report's
  with/without-cost table), `strategies/portfolio_strategy.py` (Qlib Topk-Drop +
  convex enhanced-index behind `enable_topk_drop` / `enable_enhanced_index`,
  feeding the screener alloc block + PM tools `get_topk_drop_plan` /
  `get_enhanced_index_tilt`), `strategies/market_tradability.py` (limit-up/down,
  suspension, participation caps, deal-price: `backtest_limit_threshold` /
  `backtest_volume_participation` / `backtest_deal_price`, wired into
  `scripts/backtest_strategy.py`). Plan: `docs/design_qlib_integration.md`.
- **P7 order flow (L1-L4)** - `tradingagents/strategies/orderflow.py` turns moomoo
  capital-flow buckets (XL/L/M/S, in/out) into deterministic signals:
  `distribution_score`, divergence (distribution-into-strength / silent-accumulation),
  exhaustion, bucket alignment. Wired as: tool output enrichment (`**Flow Signal**`),
  sizing fold into the strategy overlay (`enable_orderflow`; flow-scaled even while
  `enable_orderflow` is off, the raw tool stays available), state/graph stamp, and
  `scripts/orderflow_evaluate.py` for ledger-based evaluation (win-rate, mean alpha). - sentiment velocity, mention spikes,
  N-seed consensus (majority/blend); `enable_sentiment`, `consensus_seeds`.

- **M1-M5 momentum day-trading** (Warrior Trading 5-step playbook, spec:
  `Strategies/momentum_day_trading.md`) - `tradingagents/strategies/momentum.py`
  + `tradingagents/strategies/journal.py`, analysis-only (no execution):
  - **M1 stock selection** (`pillars`) - RVOL vs 50-day avg volume, total
    volume, open-gap vs prior close, $2-$20 price band, float < 20M shares.
    Each pillar is True (pass) / False (measured fail) / None (no data) -
    missing data never fails a scan and the screener/tool gate on *known*
    failures only. The float pillar is fed by `dataflows/float_shares.py`
    (FMP company profile, guarded yfinance fallback).
  - **M2 entry pattern** (`first_pullback`) - initial surge, pullback that
    retraces <= 50%, holds the 9-EMA and VWAP, trigger = first new-high candle
    above the pullback high, R/R >= 2 with a hard stop at the pullback low;
    rulebook extras when opens are available: light-red/heavy-green volume
    (`volume_ok`) and no prominent topping tails (`tail_ok`).
  - **M3 execution** (`psych_level`) - next whole/half-dollar level for
    psychological support/resistance.
  - **M4 session gates** (`session_flags` + `past_optimal_window`) - 50%
    peak give-back, max daily loss, ~10:00 ET window cutoff, missing-setups
    flag, folded into a single `walk_away` verdict.
  - **M5 journal & analytics** (`strategies/journal.py`) - JSON-lines paper
    ledger (`record_momentum_trade`, `momentum_stats`, `format_summary`):
    win/loss rate, avg R, per-pillar pass rates, FOMO / session-flag counts.
  - **Intraday confirmation** (`intraday_pullback`) - same pattern on 1m/5m
    bars with a session-VWAP hold (bar `vw` preferred, else typical price).
  Wired: Market Analyst tool `get_momentum_scan` (daily pillars + pullback +
  intraday block), screener `--scan momentum` with `--enable-float`
  low-float enrichment and `--journal PATH` (records candidates, prints
  ledger stats at the end). Live-only enrichment toggles:
  `TRADINGAGENTS_MOMENTUM_OFFLINE=1` and `TRADINGAGENTS_MOMENTUM_NO_INTRADAY=1`.

- **Techno-fundamental swing (S1-S3, spec: `Strategies/framework.md`)** -
  `tradingagents/strategies/swing.py` + `tradingagents/strategies/relative_strength.py`,
  analysis-only, wired as the screener `--scan swing` mode:
  - **S1 trend architecture** - price above a *rising* SMA50/SMA200 with the
    20-day EMA stacked above the SMA50 (`trend_architecture`).
  - **S2 relative strength** - RS line vs `benchmark_ticker` (default SPY) in
    an established 63-day uptrend (`relative_strength_report`): `leading` /
    `uptrend` pass, `lagging` / `diverging` (price new-high without RS
    backing) fail, unknown benchmark never blocks.
  - **S3 pullback setup** (`pullback_setup`) - low trades into the 20-day EMA
    while the close holds it on declining volume (accumulation).
  - **S4 RSI discipline** (`rsi_band`) - RSI 45-70 operating band or 40-50
    reset zone; below 40 invalidates.
  - **S5 stops & targets** (`swing_low_stop`, `targets_rr`, `scaleout_plan`,
    `trail_ema`) - 1-ATR stop below the swing low, 2R/3R targets, 50% T1
    scale-out to break-even, 20-day-EMA trail.
  - **S6 PEAD entry** (`events.py`) - post-earnings 2.5x-volume gap ->
    opening-range consolidation -> break of consolidation high
    (`post_earnings_play`).
  Wired: `--scan swing` gates on the stack + RS + pullback and prints
  `ScanC`/`RS`/`Stp`/`T2` columns (mode docs: `Strategies/scan.md`).

- **Volatility Contraction Pattern (`vcp_setup`, framework Phase 3)** -
  successively shallower pullbacks off a base high on fading volume (e.g.
  15% -> 8% -> 3%): strict pivot troughs, last-3 depths must contract (10%
  noise tolerance), deepest pullback within 30% of the base, volume across
  troughs must not expand (absent volume never fails). Wired as the screener
  `--scan vcp` mode with `VCP`/`Brk` columns; `swing_report` carries the VCP
  block as an additional signal.

- **Graph wiring** (`enable_strategy_overlays`, `enable_reflection`): the graph
  attaches regime/sizing/momentum overlays to the final state and records
  realized outcomes to `strategy_ledger.jsonl` (**enabled by default**;
  disable via `enable_strategy_overlays: false` / `enable_reflection: false`;
  both are also settable through `.env` (see below).

Regression status: full suite passes (1153 passed / 2 skipped / 56 subtests);
smoke imports of graph/dataflow/agent/strategy modules green.

## Contributing

Contributions are welcome: bug fixes, documentation, and feature ideas; past contributions are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
