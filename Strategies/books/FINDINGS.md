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

## 2. Confirmed defects that need an owner decision (5)

Each is verified, each is a real problem, and each changes behaviour or policy
if fixed — which is why they are here and not in §1.

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
  publisher labels it `har_rv.ols.v1` without disclosing the target.
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
