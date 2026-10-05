# FINDINGS — what the 4,372-paper corpus says we should change

This is the consolidated, triaged output of the reading in this folder. Every
book's §5 lists the defects *it* found; this file is the register across all
nineteen, sorted by what can actually be done about each one.

**Provenance of each claim is marked.** `[verified]` = the parent re-read the
cited code and confirmed it this pass. `[reported]` = a book reviewer's claim,
grounded in their own read but not independently re-checked. Do not act on a
`[reported]` row without opening the file.

---

## 1. Fixed in this pass (2)

Both are documentation-only: no computed number changes.

| # | Defect | Fix |
| --- | --- | --- |
| F1 | `tradingagents/strategies/rnd_recovery.py:1` cited its source as `(V3, 2512.xxxx)` — a placeholder id is not a citable source. `[verified]` The real paper is **arXiv 2607.27188v1**, *"Inverse Learning of Latent Risk-Neutral Densities from Irregular Option Quotes"*, whose two-component lognormal mixture, NIFTY held-out quotes and declined learned operator match this module exactly. | Header now cites `(V3, 2607.27188)`. |
| F2 | `tradingagents/strategies/market_session.py:336` documented `ratio = inst_net / (\|inst_net\| + \|retail_net\|)` while line 349 computes `(inst + retail) / (\|inst\| + \|retail\|)`. `[verified]` The **code is right** and self-consistent — its own inline comment already says "signed net / total flow: +1 = all institutional buying, 0 = perfectly balanced", and a caller using the documented formula would mis-scale the ratio by up to 2×. The stale formula appears nowhere else, including no agent-facing tool description (`market_analyst.py:90` quotes only the verdict bands). | Docstring formula corrected to match the code. |

## 2. Confirmed defects — the decision, and what landed (5)

Each was verified, and each changed behaviour or policy if fixed — which is why
they were decisions and not §1 patches. The owner took the class-level route for
D3 and authorised the rest, so all five are now fixed or explicitly recorded.

| # | Defect | Disposition |
| --- | --- | --- |
| D1 | `deflated_sharpe` mixes scales | **Fixed** — `evaluate.deflated_sharpe_ratio` applies the paper's Eq. (2) in per-observation units and returns a probability; the scale-coupled legacy difference is kept (its docstring promised bit-for-bit) and now states the unit caveat it always had |
| D2 | the G5 gate deflates from a hard-coded trial count | **Fixed** — `gate_verdict` reads `trial_ledger.trial_stats` (N and V) whenever `enable_trial_ledger` is on, and reports which it used |
| D3 | the wiring gate under-detects unwired calculators | **Fixed** — the detector counts AST uses plus string constants, excluding docstrings and the `__all__` assignment. **115** orphans surfaced, not six (see the correction in the entry below); each is declared by class in `tests/test_calc_agent_wiring.py`, and the verified wiring gaps are registered as `GAP_CALCULATORS` with the consumer that should own them |
| D4 | `SURVIVOR_ONLY` is defined but never written | **Fixed** — `coverage_window.universe_label` plus the `score_panel` build record's `universe_label` |
| D5 | `regime.sticky_markov` cannot be evaluated | **Fixed** — `regime.sticky_markov` implemented, bound through `forecast_registry.BENCHMARK_IMPLEMENTATIONS` and resolved by the registry test; numbered design revision §12.3 |

### D1. `deflated_sharpe` mixes an annualized Sharpe with a unit-scale threshold `[verified]`
`tradingagents/strategies/evaluate.py:161-186` computes `sharpe(returns, risk_free, periods_per_year)`
— an **annualized** CAGR-based Sharpe — and subtracts `_selection_threshold`,
which for the default path is `sqrt(2·ln N)`, the expected maximum of `N`
*standard-normal* (unit-variance, per-observation) Sharpe draws. Those are
different scales. The Bailey–López de Prado DSR applies the correction to the
**per-observation** SR with the T- and moment-dependent denominator
`sqrt(1 − γ₃·SR + ((γ₄−1)/4)·SR²)`; `evaluate.probabilistic_sharpe` exists at
line 950 but is not composed into `deflated_sharpe`.
**Why it needs you:** the docstring ships an explicit compatibility promise
("with the gate off the argument is ignored and the result is the pre-existing
approximation bit for bit"), and the number feeds `scripts/evaluate_config_gate.py`'s
verdict. Correcting it changes published gate outcomes.
**Options:** (a) compose `probabilistic_sharpe` into `deflated_sharpe` behind a
new flag, keeping the old path as the default; (b) fix the scale in place and
accept the verdict change; (c) document the approximation as deliberate.
**Taken: (a)** — a new, literature-correct statistic (`deflated_sharpe_ratio`)
landed beside the legacy difference rather than replacing it, because the legacy
number is what the G5 gate publishes and its docstring promised the pre-existing
result bit for bit. The legacy path also gained the unit caveat (c) would have
required, so nothing about it is silent either way.
Sources: `2608.23808v2`, `2608.27734v1` (books 02, 14, 15).

### D2. The G5 gate deflates from a hard-coded trial count `[verified]`
`scripts/evaluate_config_gate.py:47` calls `deflated_sharpe(returns, n_trials=trials)`
with a default and never reads `trial_ledger.trial_stats`, bypassing the
measured-dispersion path (`deflated_sharpe_report`) entirely. The literature's
central claim is that deflation must be indexed to the *recorded* search.
**Needs you because** the ledger path is deliberately behind `enable_trial_ledger`
(default off); making the gate read it is a policy change.

### D3. The wiring gate under-detects unwired calculators `[verified]`
`tests/test_calc_agent_wiring.py:141-147` treats a function as "an internal
helper of a reachable module" when `text.count(fn) > 1` in its **own** text.
A public function is therefore considered wired if it appears only as `def` plus
an `__all__` entry. Verified consequence: **six public calculators have no
non-test caller yet the gate passes (32 passed, 1 skipped)** —
`calibration.isotonic_calibrate`, `signal_analysis.ic_decay_half_life`,
`derivatives_gamma.max_pain`, `quant_baseline.quant_signal` / `baseline_rating`,
`monitor.notify` — and none is in `LEGACY_WHITELIST`.
**Why it needs you:** tightening `internal_use` to exclude `__all__` will fail
the build until those six are either wired or whitelisted with a reason. That is
a policy call about the repo's own "a calculator that never reaches a tool loop
is incomplete work" rule, not a bug fix I should make silently.
Note also the module-level case is inert (`_MODULE_CASES` is empty because
`_reference_blob()` includes the module under test).

**Correction (2026-10-04, measured).** "Six" was the subset the corpus happened
to name; the gate's real blind spot is **115 of the 1,399 public functions in
scope (8.2%)**, across ~60 modules — measured by re-implementing the gate and
diffing it against the corrected rule. Two detection holes compound: an `__all__`
entry satisfied `text.count(fn) > 1`, and `blob.count(fn)` matched substrings
(`max_pain` passed on the retired `max_pain_dist_atr`; `tail_risk` passed on 55
docstring and tool-name hits while having no call site anywhere). The module-level
note above is stale too: under the corrected rule `_MODULE_CASES` is live again
(`strategies/monitor.py`, `strategies/triadic_stress.py`).

### D4. The corpus sweep confirms `SURVIVOR_ONLY` is defined but never written `[verified]`
`coverage_window.py:45` defines it and `:140` exports it; nothing else in
`tradingagents/` or `scripts/` consumes it (grep: definition + test only). The
coverage *reader* is ahead of the literature; the *label* never reaches a
findings record. Against `2603.19380v1` (survivor-only Indian small-caps
overstate annual return 23.3% and Sharpe 9.1%), a published backtest can still
omit the survivor caveat. **Needs you** because it is a reporting-shape decision.

### D5. `forecast_registry` declares a benchmark that cannot be evaluated `[verified]`
`forecast_registry.py:195-196` and `:269` use `"regime.sticky_markov"` as the
benchmark ref for the `regime_probability` / `regime_stress_probability`
families. The string occurs nowhere else in the tree; no `sticky_markov` exists
in `regime.py` or anywhere else. The registry's second row is `status="ok"`, so
the declared authoritative producer has a benchmark name that resolves to
nothing. **Needs you** because the registry is inside the forecasting theme's
frozen surface (design §11.0) — amending it is a numbered design revision, not a
drive-by edit. Sources: `2402.05272v3` (book 07).

## 3. Methodology questions the corpus raises (act only with a decision)

These are `[reported]` unless marked. They are real, cited, and each would change
how a number is computed — grouped so they can be decided in batches.

**Evaluation / overfitting**
- `pbo_flag` is a "best in-sample pick fails OOS" boolean but the gate reports it
  as reason `"PBO"`; the literature's PBO is a CSCV probability over the
  candidate×fold matrix. `[verified]` (the function's own docstring says "Crude").
- Purge without embargo is the default on the panel path (`embargo=0` in the
  `score_panel` / `score_panel_eval` callers); López de Prado's CPCV needs both.
- No minimum-track-record-length check anywhere (a 6-month Sharpe-2.9 backtest
  can clear `deflated_sharpe`).
- No regime-stability gate on promoted strategies.
- Deflation counts raw trials, not effective (decorrelated) trials.

**Forecasting / volatility**
- `rv_forecast` fits HAR in RV **levels** with `returns**2` as the proxy, while
  the cited benchmarks define **log-RV** from 5-minute realized variance; the
  publisher labels it `har_rv.ols.v1` without disclosing the target. **The
  second half of this row is REFUTED** — the target is disclosed in the record's
  mandatory `target.definition` (`unit="variance"`, `definition_version`
  `realized_volatility.v2`); see §5. The level-vs-log-RV difference stands.
- `memory_profile` passes raw **returns** into `memory_parameter`, whose own
  docstring says the series is "the series the window is cut from" — but the
  literature locates long memory in **volatility**, so a near-zero `d` may be
  read as "no long memory" when volatility memory was never measured.
- `SCORING_RULES` admits `CRPS` and `QLIKE` but neither is implemented anywhere.
- **No significance test on forecast evaluations** — `benchmark_delta` is a
  signed loss difference with no Diebold–Mariano and no MZ regression.
- The default interval path is the IID conformal band (`_bootstrap_gate` off),
  which the module's own comment reports at 0.45 realized coverage at ρ=0.8.

**Risk**
- `var_cvar_horizon` scales by `sqrt(T)` with an autocorrelation-only validity
  flag; under heavy tails the correct scaling is `T^{1/α}`.
- `var_coverage_test` judges on asymptotic χ² with a 60-observation floor.
- `extreme_quantile_var` fixes `threshold_quantile=0.90` and publishes a
  method-of-moments warm start when the optimiser fails.
- Copula model risk is unpriced (four families, fixed `nu=5`, no selection).

**Portfolio / sizing**
- Shrinkage exists (`covariance_models.ledoit_wolf_shrink`) but is not in the
  allocation path; `portfolio_optimizer._covariance_matrix` inverts the raw
  sample covariance and returns a matrix from as few as **2** observations.
- `kelly_weights` computes `Σ⁻¹μ` on the raw sample covariance.

**Throughput / costs**
- Three incompatible impact shapes across one cost decision (square-root,
  quadratic, linear) — the literature rejects linear decisively.
- Participation policy is inconsistent (20% cap vs 15% default vs 10% POV).
- `liquidity_risk.kyle_lambda` builds its regressor as `sign(ΔP)·V`, so λ is
  mechanically positive and not identified from trade direction.

**Data**
- `stockstats_utils._clean_dataframe` forward-fills OHLC gaps with no flag, so
  downstream autocorrelation/volatility reads partly read synthetic bars.
- `statistical.correlation_matrix` defaults to Pearson on heavy-tailed returns.
- `granger_causality` / `ols_factors` report IID-homoskedastic p-values.

## 4. Enhancement backlog — the highest-value learnings

Not defects; the corpus's constructive proposals, in rough value order. Each is
developed with a source, a repo surface and a concrete step in the book named.

> **Overlap warning.** Several of these are already planned. The owner's
> `docs/design_fin_paper_survey_26.md` + `docs/paper_survey_26/` (six design docs
> and six implementation plans over the 309 `26xx` papers) already carry **E1**
> (CSCV PBO), **E6** (Diebold–Mariano), **E7** (QLIKE), **E9** (Ledoit-Wolf)
> and **E13** (Yang-Zhang) — verified by grep against those files. For those,
> this table is corroboration, not a new proposal; the plan of record is
> `docs/paper_survey_26/`, and E1/E6/E7/E9/E13 are mostly `26xx` papers that the
> survey already judged. **E2, E3, E4, E5, E8, E10, E11, E12, E14 and E15 were
> not found in that set** and stand on their own.

| # | Learning | Book | Repo surface |
| --- | --- | --- | --- |
| E1 | Add CSCV **Probability of Backtest Overfitting** as a probability, not a boolean | [02](02-backtest-evaluation.md) | `evaluate.py` |
| E2 | Add **Minimum Track Record Length** beside every reported Sharpe | [02](02-backtest-evaluation.md) | `evaluate.py` (new) |
| E3 | Publish **excess accuracy over the base rate** by default, so no raw hit rate reaches a report | [02](02-backtest-evaluation.md), [16](16-forecasting.md) | `calibration.py` (shipped, gate off) |
| E4 | **Null-environment workflow audit** — replay the whole pipeline on induced-null panels and falsify the *workflow* | [02](02-backtest-evaluation.md) | `falsification.py` (new) |
| E5 | **Cost-floor precondition** — refuse significance testing when the gross edge is under round-trip cost | [02](02-backtest-evaluation.md), [13](13-crypto.md) | `scripts/evaluate_config_gate.py` |
| E6 | **Diebold–Mariano + MZ** on every forecast evaluation | [10](10-volatility.md) | `prediction_ledger.py` |
| E7 | **CRPS / QLIKE** implementations to back the declared scoring rules | [16](16-forecasting.md) | `forecast_contract.py` / new |
| E8 | **Equal-weight combination arm** for the forecast registry (the candidate pool is `()`) | [16](16-forecasting.md) | `forecast_registry.CANDIDATE_MEMBERS` |
| E9 | **Ledoit-Wolf into the optimiser**, plus a minimum-observation guard on the allocators | [09](09-portfolio.md), [11](11-correlation-networks.md) | `portfolio_optimizer.py` |
| E10 | **Regime-conditional comparison with a sign test**, instead of one full-horizon number | [02](02-backtest-evaluation.md), [07](07-regime-changepoint.md) | `regime_performance.py` |
| E11 | **Per-event-class sentiment half-life** instead of one global 7 days | [04](04-sentiment-text.md) | `sentiment.py` |
| E12 | **RMT edge guard**: report an autocorrelation/tail check before trusting the MP band | [11](11-correlation-networks.md) | `market_breadth.py`, `eigen_rotation.py` |
| E13 | **Wire the analyst tool path to Yang-Zhang**, not the dominated Parkinson/Garman-Klass | [10](10-volatility.md) | `analysis_tools.py:11284` |
| E14 | **Morning/afternoon and lead-lag labelling**: label lag ≤ 0 correlations as contemporaneous/priced-in | [04](04-sentiment-text.md) | `analysis_tools.get_sentiment_lead_lag` |
| E15 | **Sticky-Markov persistence benchmark** for the regime rows (see D5) | [07](07-regime-changepoint.md) | `regime.py` (new) |

**Dispositions (2026-10-04).** Each row was re-checked against the live tree
before anything was taken, because a `Status` column written against *code* can
call an item `absent` when the `26xx` plans already own it.

- **Shipped:** **E2** (`evaluate.min_track_record_length`, verified against
  Bailey & López de Prado's own three published examples) and **E14** (the
  lead/lag `relation` label plus the non-lead call-out). **E3**'s remaining half
  is done: `calibration.excess_accuracy` is H4, shipped behind
  `enable_accuracy_ceiling`, and the paired tests H4's own card names now ship
  with it.
- **E15 landed as D5.**
- **E4 is H3 — LANDED 2026-10-04.** The overlap grep above missed it: `implementation_plan_research_
  honesty_gates.md`'s **H3 — synthetic-null workflow falsification** *is* "replay
  the whole pipeline on induced-null panels", five reference classes at N = 1000.
  It is now built: `tradingagents/strategies/null_harness.py` (Stage 1 - the
  generators, the null band, the honest-vs-leaky verdict) plus
  `evaluate.inflation_diagnostics` beside `walk_forward_splits` (Stage 2 -
  `Delta_Z`, `K_eff`), called offline by `scripts/null_harness.py`. No gate, per
  H3's card; the familywise warning (5.3% at K=1, 92.3% at K=50) travels in the
  output.
- **Owned by the survey, do not duplicate:** **E1** (CSCV PBO — H1's card), **E6**
  (Diebold–Mariano — named in H4's and V1's cards), **E7** (QLIKE — V1's loss),
  **E8** (`CANDIDATE_MEMBERS` is `design_vol_surface_and_vrp.md` §V1's pool), **E9**
  (the allocation path — survey ground rule 2 binds **K4** to *replace* rather
  than sit beside `ledoit_wolf_shrink`), **E13** (the design doc already lists
  Yang-Zhang as an existing producer; the tool at `analysis_tools.py:11298`
  still returns Parkinson/Garman-Klass, which is a wiring choice inside that
  theme).
- **Still open, no owner:** **E5** (cost-floor precondition on the G5 gate —
  `[verified]` absent: `scripts/evaluate_config_gate.py` names no cost, turnover,
  fee or slippage term, so its deflated-Sharpe significance is taken on a gross
  series), **E10** (the per-regime read exists —
  `regime_performance.regime_conditioned_performance` — but it reports a
  comparison, not a **sign test**; `[verified]` no sign test anywhere in that
  module), **E11** (per-event-class sentiment half-life — `sentiment.decayed_
  weight` still takes one global `half_life=7.0` and its one call site passes a
  single caller-supplied value, so no event class maps to its own decay), **E12**
  (the row's ask is an **autocorrelation/tail check on the MP band's i.i.d.
  premise**; both `market_breadth` and `eigen_rotation` *state* that premise in a
  docstring and neither tests it — `[verified]`. The **separate** bulk-refusal
  guard already exists and predates the row: `469a611` refuses a rotation taken
  inside the MP bulk, and `market_breadth.mp_below_count` is the one producer of
  the edge (X3, 2608.09641) — so do not re-file E12 as "no MP guard at all").

## 5. Claims that did not survive verification

- **"`max_pain`, `notify`, `isotonic_calibrate` etc. are dead code."** Not dead
  in the repo's sense — each is defined, exported and exercised by a test file
  (`test_calibration_regime.py`, `test_qlib_phase1.py`, `test_phase8_ops.py`).
  They are **unwired in production**, which is D3's real content. `[verified]`
- **"`regime.sticky_markov` is a dangling reference that must resolve to a
  symbol."** Benchmark refs are *labels* carried into
  `prediction_ledger.evaluate_forecast`, not callables — the ledger takes the
  benchmark *score* from the caller. So D5 is a naming/observability gap, not a
  broken import. `[verified]`
- **"`long_memory.memory_parameter` is called with the wrong argument."** It is
  passed `returns`, which is exactly what its own docstring specifies. The
  disagreement is between the docstring's contract and the literature's
  definition of variance memory — a design question, not a call-site bug.
  `[verified]`
- **"The publisher labels the HAR forecast `har_rv.ols.v1` without disclosing
  the target."** It **does** disclose it, and in the mandatory field: the
  registry's `realized_volatility` row carries a `TargetRef.definition` —
  *"next-session realized VARIANCE: HAR-RV fitted on RV = squared close-to-close
  log returns (RV_{t+1} = b0 + b_d RV_t + b_w RV_w + b_m RV_m)…"* — with
  `definition_version="realized_volatility.v2"` and `unit="variance"`, and
  `publish_realized_volatility_forecast` passes `target=row.target` into every
  record it publishes (`forecast_publisher.py:363`). `MODEL_VERSION` names the
  *model*, and the record carries the target beside it. The **level-vs-log-RV**
  half of §3's row stands (the literature's HAR-RV is log-RV from intraday
  realized variance) — that is a method difference, disclosed, and the V2
  territory of the `26xx` survey. Recorded rather than acted on. `[verified]`

## 6. How these were found, and how far to trust them

- Every claim originates in a book's §5, written by a reviewer who read the
  papers and opened the repo. The `[verified]` rows were re-checked by the parent
  against the live tree; a `[reported]` row has **not** been.
- None of this is a benchmark result. The corpus documents what the literature
  finds; it does not tell us what this repo's numbers actually are. Several
  fixes above would change computed outputs, which is precisely why they are
  decisions rather than patches.
- Two files were changed in this pass, both docstrings (`§1`). **No computational
  behaviour was altered**, and no test was weakened.

---

## 7. The D3 gap register — the 38 wiring gaps, ALL WIRED (2026-10-04)

The corrected wiring detector (see §2 D3) surfaced 115 unreferenced public
calculators. Triaging them left **38 verified wiring gaps**: a read with no wired
equivalent, and a consumer that should own it. They were declared in
`tests/test_calc_agent_wiring.py::GAP_CALCULATORS` — the authoritative register,
because the gate refuses a stale or misspelled declaration — and repeated below
so the work list was readable without opening a test file.

**All 38 are now wired** (2026-10-04): every key became a real call reaching its
consumer's rendered output or persisted artifact. `GAP_CALCULATORS` is therefore
**empty** — the dict stays as the mechanism, and the gate still refuses a key
that is no longer orphaned. The table below is the record of WHICH consumer took
each read.

| module:function | consumer that should own it |
| --- | --- |
| `alpha_eval:insight_accuracy` | `analysis_tools:get_alpha_scoring` |
| `complexity:approximate_entropy` | `analysis_tools:get_mean_reversion_quality` |
| `debate_score:divergence_check` | the debate read (design_multi_agent_debate §4.5) |
| `debate_score:reweight_to_baseline` | `structured_debate:create_debate_finalize` |
| `derivatives_gamma:max_pain` | **wired 2026-10-04** → `analysis_tools:get_gamma_profile` |
| `domain_bundles:get_fundamental_profile` | `fundamentals_analyst` |
| `domain_bundles:get_market_technicals` | `market_analyst` |
| `domain_bundles:get_portfolio_risk_envelope` | `aggressive_debator` |
| `domain_bundles:get_sentiment_flow_feed` | `news_analyst` |
| `factor_expressions:apply_winsorize` | `analysis_tools:get_factor_profile` |
| `factor_expressions:apply_zscore` | `analysis_tools:get_factor_profile` |
| `factor_expressions:fit_winsorize` | `analysis_tools:get_factor_profile` |
| `falsification:monitor_conditions` | `monitor:notify` |
| `falsification:record_breaches` | `falsification:monitor_conditions` |
| `mean_reversion:memory_profile` | `analysis_tools:get_mean_reversion_quality` |
| `monitor:notify` | `falsification:monitor_conditions` |
| `portfolio_optimizer:confidence_weights` | `analysis_tools:get_risk_parity_alloc` |
| `quant_baseline:baseline_rating` | `prediction_ledger:log_decision` |
| `quant_baseline:quant_signal` | `prediction_ledger:log_decision` |
| `reflection:build_reflection_context` | `trading_graph:prepare_initial_state` (enable_reflection) |
| `regime:market_stress_composite` | `analysis_tools:get_regime_components` |
| `regime:relative_vol_ratio` | `analysis_tools:get_regime_components` |
| `regime:upside_downside_beta` | `analysis_tools:get_regime_components` |
| `risk_sizing:risk_quantity` | `analysis_tools:get_fixed_risk_size` |
| `sector_screener:stock_screen` | `analysis_tools:get_sector_rotation_screen` |
| `sentiment:event_study` | *(none named from the tree)* |
| `sentiment:gini_coefficient` | *(none named from the tree)* |
| `sentiment:sentiment_dynamics` | `analysis_tools:_sentiment_depth_rows` |
| `signal_analysis:ic_decay_half_life` | `analysis_tools:get_signal_quality` |
| `signal_analysis:pred_autocorr` | `analysis_tools:get_signal_quality` |
| `technical_score:technical_disagreement` | `analysis_tools:get_technical_score` |
| `technical_score:technical_state` | `analysis_tools:get_technical_score` |
| `triadic_stress:triadic_stress` | `analysis_tools:_risk_components` |
| `dataflows/alpaca:get_calendar` | `scripts/value_screener.py` |
| `dataflows/pit_registry:markup_label` | *(none named from the tree)* |
| `dataflows/preopen:postfill_drift` | `scripts/strategy_quality_report.py:build_report` |
| `dataflows/stockdata:get_market_snapshot_stockdata` | `market_position_tools:get_market_snapshot` |
| `dataflows/yfinance_sector:fetch_eps_revisions` | `scripts/value_screener.py:_fetch_revision_guarded` |

**Landing notes (2026-10-04).** Where the tree named no consumer, the wiring
chose one and said why: `sentiment.event_study` and `sentiment.gini_coefficient`
both joined `analysis_tools._sentiment_depth_rows` — the module's own SENT-7/9/10/11
emitter, which already published SENT-9's attention set and SENT-10's asymmetry —
and `dataflows/pit_registry.markup_label` joined `analysis_tools.get_factor_profile`,
the one place that already writes a PIT snapshot and its fitted moments, so the
label is stored beside them rather than on a new path. `debate_score.divergence_check`
landed in `structured_debate`'s round completion (R2' of design §4.5), where the two
rated sides' allocation stances are finally compared, and the reweight it gates is
applied by `reweight_to_baseline` in the finalize node. The four `domain_bundles`
composites became tools bound to the analysts the register named
(`agents/utils/domain_bundle_tools.py`), each with its own trigger line.

**A reminder about the other 77.** They are declared `reference` / `dead` and are
*not* work: a recipe the vault documents as a formula, a debug or schema-self-check
helper, a duplicate of a wired symbol, or a read that needs an input no vendor
supplies. The table above is now the record of the wiring, not a remainder.
