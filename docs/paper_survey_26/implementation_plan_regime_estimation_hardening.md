# Implementation Plan - Regime and State

Status: **IN PROGRESS** - wave 0+1 build started: R1 and R7 landed (2026-09-23), R1 still dormant in-run pending the tool selector. The rest of this plan is not started.
path for the detectors, panel reads and constraints specified in
[`design_regime_estimation_hardening.md`](design_regime_estimation_hardening.md), one of the six
themed design docs derived from [`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md).

**Parent design:** [`design_regime_estimation_hardening.md`](design_regime_estimation_hardening.md)
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency surface, the cross-theme phase map, the dependency graph and the landing protocol live there.
**Items:** R1 (P1), R2 (P2), R3 (P1), R7 (P1), R4 (P3), R5 (P3), R6 (P4, blocked), R8 (constraint), R9 (constraint).
**Gates added:** 5 new (`enable_hmm_heavy_tails`, `enable_spectral_null_band`, `enable_triadic_stress`, `enable_regime_shift_proposer`, `enable_forward_stress_probability`), plus one extension of the existing `enable_bocpd`.

## 0. Scope

This plan covers the engine's regime channel: `regime_score`, the market-state axes, and the
detectors underneath them (`strategies/regime.py`, `strategies/regime_state.py`,
`strategies/regime_performance.py`, `strategies/covariance_models.py`,
`strategies/market_breadth.py`, and two new modules). Every item is additive and default-off, and
degrades to `unavailable` when its inputs are missing - never to zero, and never to a substituted
default. R8 and R9 build nothing; they are standing constraints on the rest of this plan and on
every later phase.

The inherited rules that bind this theme specifically are: **rule 2**, because R2's coverage-tested
VaR must not become a second risk authority beside `strategies/book_risk.py` and R5 must not become
a second breadth authority beside `strategies/market_breadth.py`; **rule 3**, because no item here
changes `COMPOSITE_ENGINES` - R1, R2, R3 and R5 feed components `regime_score` already declares, and
R7 feeds `risk_score`; **rule 4**, because R3, R5, R6 and R7 all read a panel and must refuse on a
thin one; **rule 6** for the five new gates; **rule 7** for the new public functions
(`eigen_projector_distance`, `triadic_stress`, `regime_shift_candidates`, `validate_shift`,
`forward_stress_probability`, `early_warning_gate`); and **rule 8**, which is what makes R4 and R6
offline artefacts that may never be called from `prepare_initial_state`, `finalize_run`, or any
agent tool. P0 binds the theme twice over: H10's coverage window is a prerequisite for every panel
read here (R3, R5, R6, R7), and H11's intervals feed R2's coverage test.

## 1. Item cards

### R1 - BOCPD with a duration law instead of a constant hazard

**Target.** `strategies/regime.py:764` `bocpd`: a `hazard_mode` parameter (`constant` = today's behaviour, the default; or a duration-law-compiled hazard from `{lognormal, pareto, geometric}`), with the duration parameters estimated from run lengths observed so far, and the covering metric reported beside `zero_run_prob`.
**Phase / run mode.** P1 / in-run.
**Behaviour.** The run-length prior stops asserting that a regime is as likely to end on its first day as on its hundredth; the hazard is compiled from an explicit duration law and re-estimated on an expanding window. Same recursion, `O(t)`; the duration compile is an `O(#runs)` pass. A change in hazard can be judged because the covering metric (length-weighted Jaccard of the segmentation) travels with `zero_run_prob`.
**Gate.** extends `enable_bocpd` (no new gate).
**Failing-first test.** `tests/test_bocpd.py::test_hazard_mode_lognormal_is_run_length_dependent`. Mutation: delete the duration-law compile so `hazard_mode` falls through to the scalar `hazard` (today's constant branch). It asserts that on a series carrying a manufactured long regime the `lognormal` hazard is not constant across run lengths and the resulting `zero_run_prob` differs from the `constant` run on the same series, while the default path leaves every existing assertion in `tests/test_bocpd.py` green, including the `hazard` echo field and the stationary `map_run_length == 240` case.
**Acceptance.** `hazard_mode="constant"` reproduces today's `zero_run_prob` and `map_run_length` bit-for-bit; a duration-law mode reports the covering metric beside `zero_run_prob`; degenerate duration parameters take the same `None` path today's invalid-hazard input takes.
**Depends on.** nothing - independently landable, and the smallest change in the theme.
**Doc caveat.** The paper's evidence is high-frequency NASDAQ order flow with no daily-frequency validation, so daily frequency is a hypothesis here and not a demonstrated gain; its multivariate extension was beaten by independent univariate filters, which warns against pooling.

### R2 - Heavy-tailed emissions, and a VaR that is coverage-tested

**Target.** `strategies/regime.py:367` `hmm_filtered_regime`: an `emission` parameter (`gaussian` default, plus `student_t`, `laplace`, `ged`) with selectable `K`; and `regime_conditional_var(posteriors, emissions, q)`, whose VaR consumer sits in `strategies/book_risk.py`.
**Phase / run mode.** P2 / in-run.
**Behaviour.** One shared forward-backward kernel; only the per-state M-step swaps across emission families. The regime-conditional VaR is the running state posterior times each state's CDF, and its output is checked by Kupiec and **Christoffersen joint conditional-coverage** tests on held-out data rather than asserted. The coverage test is the deliverable; a VaR without one is a number.
**Gate.** `enable_hmm_heavy_tails`, default off.
**Failing-first test.** `tests/test_hmm_heavy_tails.py::test_the_coverage_test_rejects_the_gaussian_var`. Mutation: bypass the coverage test by returning a passing verdict unconditionally (equivalently, compute the VaR under the Gaussian CDF regardless of `emission`). It asserts that on a manufactured fat-tailed two-regime series the Gaussian-emission VaR fails the joint conditional-coverage test while the Student-t one does not, and that the reported verdict carries the coverage level and the held-out window it was computed on.
**Acceptance.** The VaR output carries its Kupiec and Christoffersen verdicts with the sample they were computed on; `unavailable` when the held-out window is too thin for the test; `emission="gaussian"` preserves today's `probs` and `last` bit-for-bit, so the existing pins in `tests/test_strategies_regime.py` stay green; a `K` other than 2 is reported with the selection criterion used.
**Depends on.** P0-4 (H11) intervals for the coverage test; the VaR output is consumed by **K1** (tail-risk layer), which ships the coverage test with its band.
**Doc caveat.** A static transition matrix drifts - the paper's out-of-sample 2025 ACF is under-estimated - and `K`-selection by held-out likelihood is an in-sample choice; the rank-non-binding result is a cross-ticker median, not universal.

### R3 - Declare a regime change only against a null band

**Target.** `strategies/regime.py` / `strategies/covariance_models.py`: `eigen_projector_distance(prev_window, curr_window)` plus the scalar spectral functionals (absorption ratio, leading-eigenvalue share), each reported with its calibrated first-order null band and a flag for whether the move exceeds it; the flag, not the raw functional, feeds `regime_score`.
**Phase / run mode.** P1 / in-run.
**Behaviour.** A spectrum estimated from a finite window moves on its own, so structural change is declared only when the move exceeds what estimation noise produces under shrinkage. One eigendecomposition per rolling window, `O(N^3)` naive - fine at `N` in the tens, and the engine already computes correlation matrices. This is a per-panel read, not per-symbol.
**Gate.** `enable_spectral_null_band`, default off.
**Failing-first test.** `tests/test_spectral_null_band.py::test_a_stable_covariance_is_not_flagged`. Mutation: make the flag unconditionally True. It asserts that successive windows drawn from one fixed covariance are not flagged, that a window with a block correlation injected at a known index is flagged, and that the band depends only on window length and shrinkage intensity - the same length and intensity carry the same band.
**Acceptance.** Band and flag are reported beside every functional; a non-rejection reads "not detectable", never "no change"; the raw functional never reaches `regime_score`.
**Depends on.** P0-1 (H10) coverage window for the panel read; sibling of **X3** - both are spectral panel reads, one eigenspace and one eigenvalue count.
**Doc caveat.** The paper's own framing is that non-rejections partly reflect wide null bands, so a wide band means "not detectable" and never "no change".

### R7 - A coincident stress read, labelled coincident

**Target.** New module: `triadic_stress(returns_by_name) -> {tsi, epicentre[]}` over the correlation network that `strategies/statistical.py:203` `correlation_matrix` already produces, with `TSI = (C*D/M)*Coex` and a per-node `diag(A^3)` epicentre attribution; consumer is the risk debate and `risk_score`.
**Phase / run mode.** P1 / in-run.
**Behaviour.** Names where in the cross-section a stress is centred instead of reporting only that concentration moved. `Tr(A^3)` is `O(N^3)` or `O(N^2 * edges)` - trivial at this engine's book size. The output carries an explicit `coincident: true` marker and is `unavailable` below roughly eight names.
**Gate.** `enable_triadic_stress`, default off.
**Failing-first test.** `tests/test_triadic_stress.py::test_epicentre_names_the_stressed_block`. Mutation: return an empty epicentre list, dropping the `diag(A^3)` attribution. It asserts that on a manufactured panel where a known subset of names carries the correlated block the epicentre names that subset, and that `triadic_stress` returns `unavailable` below eight names.
**Acceptance.** `coincident: true` is present on every returned read; a cross-section below eight names yields `unavailable`, never a saturated index; the epicentre is ordered.
**Depends on.** P0-1 (H10) coverage window; R8 governs its labelling.
**Doc caveat.** Coincident, not leading; only marginally exceeds the Absorption Ratio; needs a cross-section and saturates when it is small.

### R4 - A cheap proposer validated by a statistical test

**Target.** New module beside `strategies/theme_triggers.py` (whose escalation shape it copies) and `strategies/regime_performance.py`: `regime_shift_candidates(text_corpus)` (cheap LLM proposer, dates only) and `validate_shift(date, panel)` (likelihood-ratio VAR test, the authority).
**Phase / run mode.** P3 / offline + weekly.
**Behaviour.** The pattern the engine already uses for themes, applied to dates: propose cheaply, validate expensively, and let only survivors reach the score. The validated date set is what enters `regime_score`; proposals that fail validation are recorded, not silently dropped. Validation uses only data before the candidate date plus a fixed post-window.
**Gate.** `enable_regime_shift_proposer`, default off.
**Failing-first test.** `tests/test_regime_shift_proposer.py::test_a_candidate_that_fails_the_lr_test_does_not_enter_the_date_set`. Mutation: make `validate_shift` return True unconditionally. It asserts that on a panel with no break at the candidate date the date is absent from the validated set and present in the recorded rejections, and that the score's date set is the validated set.
**Acceptance.** Every proposal has a recorded verdict; the score never sees an unvalidated date; nothing in this item is reachable from a run path (ground rule 8).
**Depends on.** P0 and P1; a curated policy corpus the engine does not currently hold.
**Doc caveat.** Tuned to a monetary/Treasury setting with a hand-built anchor list, and the text channel needs a curated policy corpus the engine does not currently hold.

### R5 - A calibrated forward stress probability from the cross-section

**Target.** `strategies/market_breadth.py`: `forward_stress_probability(panel) -> {p_stress, horizon, calibration}`, monthly frequency, with the calibration report produced alongside `strategies/calibration.py`.
**Phase / run mode.** P3 / weekly.
**Behaviour.** Aggregates monthly cross-sectional fragility signals - return dispersion, downside extremes, higher moments - over the tracked universe into a one-month-ahead probability of entering a high-stress regime, with the calibration report as part of the output, because an uncalibrated probability is a score wearing a probability's name. Cheap once the panel exists; the cost is the panel, which breadth already pays.
**Gate.** `enable_forward_stress_probability`, default off.
**Failing-first test.** `tests/test_forward_stress_probability.py::test_the_probability_carries_its_calibration_report`. Mutation: drop the `calibration` key from the returned dict. It asserts that the output carries `p_stress`, `horizon` and a calibration report, and that a cross-section too thin to calibrate yields `unavailable`, never a number.
**Acceptance.** Calibration report present whenever `p_stress` is; `unavailable` on a thin cross-section; the horizon is stated in the output, not implied by the caller.
**Depends on.** P0-1 (H10) coverage window; R8 binds its wording; the panel the run already fetches.
**Doc caveat.** Cross-sectional fragility signals are correlated with each other and with the outcome being predicted, so the paper's calibration is the claim and it needs re-fitting on this engine's panel before any threshold is trusted.

### R6 - The gate every early-warning indicator must pass

**Target.** New module `early_warning_gate`, plus the labelled event-onset panel it cannot run without; the findings ledger records the verdicts.
**Phase / run mode.** P4 / **OFFLINE, BLOCKED**.
**Behaviour.** A discipline item, not a detector: the gate refuses to register any early-warning indicator into `regime_score` unless it (a) survives the 39-configuration detrend/window sweep, (b) beats a matched placebo onset null, and (c) reports a false-alarm rate. Availability is per-indicator and explicit. It is blocked by construction: the engine has crises in its report trees but **no labelled onset panel**, so until one is built the honest output for every candidate indicator is `unavailable`. **Building that panel is itself a deliverable and a prerequisite, not a side task.**
**Gate.** none - this item *is* a gate module, not a config gate, and it has no `DEFAULT_CONFIG` key to register.
**Failing-first test.** `tests/test_early_warning_gate.py::test_an_indicator_that_fails_the_placebo_null_is_refused`. Mutation: admit on the configuration sweep alone, skipping the matched placebo null. It asserts that with a synthetic panel an indicator that survives the sweep and fails the matched placebo null is refused, and that with no labelled onset panel every candidate is `unavailable` with its reason - the second assertion is the only deployable half today, and the first becomes runnable when the panel lands.
**Acceptance.** No early-warning indicator reaches `regime_score` without all three conditions, each recorded with its verdict; the sweep and null use onsets outside the evaluated event.
**Depends on.** the labelled event-onset panel (does not exist) - a hard prerequisite; P0-1 (H10) for the panel coverage.
**Doc caveat.** The paper's own `n = 7` and its placebos share regime; the protocol is the contribution.

### R8 - Do not promise regime-arrival risk (constraint)

**Constraint.** No output may read as forecasting an approaching shift - "approaching shift risk", "early warning", or any equivalent - unless a walk-forward-tested detector backs it, or the read is explicitly labelled coincident. This constrains `regime_score`'s wording and any report prose that cites a regime read. **No target, no gate, no test: it forbids wording rather than building.** It binds R4 (whose output is dates, not forecasts), R5 (whose probability must carry its calibration), R7 (whose marker is `coincident: true`), and every later phase.
**Measurement behind it.** 2606.02657 decomposes the future-minus-training risk gap exactly as `(p01 - pi)(R1 - R0)`: the **ex-post** penalty tracks realized train-to-deployment gaps (Spearman `rho = 0.729`, 95% CI `[0.635, 0.801]`), while the **training-only** estimator does not (`rho ~ 0.084`, CI includes zero). Regime geometry is detectable in hindsight; regime *arrival* is not.
**Doc caveat.** The model is a two-state Markov chain and the engine has no calm/crisis label axis today; the constraint is about honest labelling, not about adopting the estimator.

### R9 - Regime as a soft gate, not an input (constraint, deferred)

**Constraint.** Regime information conditions *how much to trust* another read; it is **never concatenated onto one**. No regime variable enters a feature vector, and no read may cite a regime cell as an additive term. Standing on every later phase. **No target, no gate, no test: no build is specified, and the item is recorded because it constrains future work.**
**Measurement behind it.** 2608.12251 routes regime variables through a gate on residual expert corrections instead of appending them, and reports appending them *degrades* both accuracy and stability (**IC 0.5469 gated vs 0.5378 appended**). 2605.11423 supplies the mirror-image warning: a three-condition day classifier identifies a real 4.4% of sessions with a `+25.6bp` next-day spread, and its **eight directional rules all failed** - a classifier that identifies interesting days is not thereby a signal.
**Doc caveat.** Deferred by design; recorded so that a later phase does not rediscover the degradation the paper measures.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| R1 | duration-law hazard on `bocpd` plus the covering metric | `strategies/regime.py:764` | P1 | in-run | extends `enable_bocpd` |
| R2 | `emission` families + coverage-tested regime VaR | `strategies/regime.py:367`, VaR consumer `strategies/book_risk.py` | P2 | in-run | `enable_hmm_heavy_tails` |
| R3 | projector distance + scalar functionals with a null band | `strategies/regime.py`, `strategies/covariance_models.py` | P1 | in-run | `enable_spectral_null_band` |
| R7 | triadic stress index + epicentre attribution | new module, consumer `risk_score` | P1 | in-run | `enable_triadic_stress` |
| R4 | shift-date proposer + LR-VAR validator | new module beside `strategies/theme_triggers.py` | P3 | offline + weekly | `enable_regime_shift_proposer` |
| R5 | calibrated forward stress probability | `strategies/market_breadth.py` | P3 | weekly | `enable_forward_stress_probability` |
| R6 | early-warning admission gate + labelled onset panel | new module | P4 | offline, blocked | none (gate module) |
| R8 | labelling constraint on regime-arrival wording | - | - | constraint | none (constraint) |
| R9 | soft-gate constraint, deferred | - | - | constraint | none (constraint) |

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_hmm_heavy_tails` | R2 | `strategies/regime.py:367` emission path; `strategies/book_risk.py` VaR consumer | off |
| `enable_spectral_null_band` | R3 | `strategies/regime.py`, `strategies/covariance_models.py` into `regime_score` | off |
| `enable_triadic_stress` | R7 | new module into `risk_score` | off |
| `enable_regime_shift_proposer` | R4 | the weekly/offline job entry and the in-run reader of the validated date set | off |
| `enable_forward_stress_probability` | R5 | `strategies/market_breadth.py` into `regime_score` | off |

`enable_bocpd` (R1) is **extended, not added**: `hazard_mode` joins the parameters the existing gate
already guards, so R1 registers no new gate and every existing `enable_bocpd` pin stays green.
The five new gates each need the six registration points listed in
[`README.md`](README.md), including the `docs/gate_registry.md` coverage sentence.

## 4. Dependencies

```text
R1  -> nothing (independently landable; the smallest change in the theme)
R2  -> P0-4 (H11) intervals -> the coverage test; R2's VaR -> K1 (the tail layer consumes it)
R3  -> P0-1 (H10) coverage window; sibling of X3, one eigenspace read beside one eigenvalue count
R7  -> P0-1 (H10) coverage window; labelled coincident per R8; consumer is risk_score
R4  -> P0 + P1; needs a curated policy corpus the engine does not hold
R5  -> P0-1 (H10) coverage window; calibration with strategies/calibration.py; wording bound by R8
R6  -> the labelled event-onset panel (does not exist) -> then the admission path into regime_score
R8  -> constrains R4, R5, R7 and every later phase (standing, no dependency of its own)
R9  -> constrains every later phase (standing, deferred, no producer)
```

`R6` and `R4` are the two offline members of this slice: per ground rule 8 neither may be called
from `prepare_initial_state`, `finalize_run`, or any agent tool. R1, R2, R3 and R7 are in-run and
cheap (seconds or less); R5 is weekly because its panel is the cost.

## 5. Decisions requested (owner)

1. **Whether R1 + R2 land as a first pass, and whether to fund the labelled onset panel that R6 depends on.** R1 is the smallest high-value change in the theme and R2 carries the coverage test; the panel is an unfunded prerequisite that blocks R6 entirely.
2. **Whether R3 and R5 are weekly offline passes or per-run producers.** Both read a panel on every run, which is a real cost against the four-symbol run budget; scoping them to a weekly pass means `regime_score` sees a dated panel read rather than a live one.
3. **Whether the engine acquires a curated policy corpus for R4.** Without one the proposer has nothing to propose and the LR-VAR validator is the only half that runs; the decision is the corpus, not the code.
4. **Whether R7's epicentre is wired into the risk debate and `risk_score` output or stays internal to the risk debate's reasoning.** The index is cheap; the question is whether naming names is an output the sibling app may consume.

## 6. Honest limits

1. **Two of this theme's three most load-bearing results are negative or self-limiting** (R8, R9), which is why they lead the design doc: a reader who takes only the detectors has taken the weaker half.
2. **R1 and R2 are validated on data this engine does not hold** - NASDAQ order flow and SPY daily returns respectively - so both are hypotheses here until re-measured on this engine's panel; R1's frequency transfer is the largest single open question in the plan.
3. **R6 cannot land at all** until the labelled onset panel is built, and until then the honest output for every candidate indicator is `unavailable` - including a candidate that looks convincing.
4. **R3, R5 and R7 read a panel, not a symbol**, and a four-symbol book is a thin cross-section; R7 refuses below eight names, and R3's bands are widest exactly where the book is smallest.
5. **R4's dates are only as good as the corpus behind them**, and the LR-VAR validator is the authority - so a thin corpus yields few validated dates, which is a refusal, not a silent acceptance.
6. **Nothing here changes `COMPOSITE_ENGINES`:** the items feed components `regime_score` already declares, and R7 feeds `risk_score`; no item adds an engine, and no item is evidence of an edge.
