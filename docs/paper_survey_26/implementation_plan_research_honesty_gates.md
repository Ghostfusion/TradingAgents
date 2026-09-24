# Implementation Plan - Honest Evaluation Gates

Status: **IN PROGRESS** - wave 0+1 build started: H10, H1 and H11 (both halves) landed (2026-09-23). The rest of this plan is not started.
2026 `q-fin` corpus survey - the gates that decide whether a claim the engine publishes is
*earned*. Parent survey: [`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md).
**Parent design:** [`design_research_honesty_gates.md`](design_research_honesty_gates.md)
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency surface, the cross-theme phase map, the dependency graph and the landing protocol live there.
**Items:** H10 (P0), H1 (P0), H7 (P0), H11 (P0), H4 (P0), H6 (P0), H2 (P2), H5 (P3), H8 (P3), H9 (P3), H3 (P4, OFFLINE)
**Gates added:** 10 (`enable_coverage_window`, `enable_trial_ledger`, `enable_refusal_ledger`, `enable_bootstrap_intervals`, `enable_accuracy_ceiling`, `enable_materiality_verdict`, `enable_factor_availability_gate`, `enable_rule_policy_gates`, `enable_vintage_guard`, `enable_report_attribution`), no extensions to existing gates. H3 adds none.

## 0. Scope

This plan covers the eleven gates that judge the engine's own output: the coverage that licenses a
number (H10), the search that inflated it (H1), the refusals it never recorded (H7), the interval
width its autocorrelation earns (H11), the accuracy ceiling it cannot exceed (H4), the vocabulary
that keeps "not proven" apart from "disproven" (H6), plus the four downstream instruments (H2, H5,
H8, H9) and the offline falsification harness (H3). Every item is additive and default-off, and
degrades to `unavailable` when its inputs are missing. The inherited rules binding this theme
specifically are 1 (P0 is the instrument, and here it is the engine's own claim that is judged), 2
(H10 and H4's GARCH leg are readers, not second producers), 3 (nothing here enters
`COMPOSITE_ENGINES`), 4 (coverage travels with the number, and H10 is the mechanism), 5 (every gate
can fail), 6 (six registration points per gate), 7 (a new public function in `strategies/` or
`dataflows/` ships with its first caller), and 8 (H3 is offline and may not be called in-run).

## 1. Item cards

### H10 - Coverage window and survivor labelling

**Target.** `strategies/coverage_window.py` (new): `coverage_window(series) -> {"first_valid", "last_valid", "n_bars", "padded_days", "alignment"}`; consumed by `strategies/data_quality.py`, reported per symbol by `scripts/coverage_scorecard.py`.  
**Phase / run mode.** P0 / in-run  
**Behaviour.** `padded_days` counts positions before the first valid observation in a calendar-aligned panel; a panel statistic computed over a padded window is reported `unavailable`, never computed, and any backtest over a current-constituent universe is labelled `survivor_only` in the findings record. It is a **reader of the already-loaded frame, not a producer - never a second data-quality authority**; H10 adds the window, not the threshold, so `market_data_validator._INDICATOR_MIN_BARS` (`:34`) and `volatility_models._IGARCH_AB = 0.999` (`:40`) stay exactly as they are.  
**Gate.** `enable_coverage_window`, default off.  
**Failing-first test.** New `tests/test_coverage_window.py::test_padded_panel_is_unavailable`: remove the `padded_days > 0` refusal branch and it must fail by name, asserting `padded_days == 40` on a frame with 40 leading NaNs and `unavailable` for the dependent statistic.  
**Acceptance.** `padded_days == 40` and the statistic `unavailable` on the padded frame; on a dense frame the statistic is unchanged to the byte (the guarantee `tests/test_cli_propagate_parity.py` already pins elsewhere).  
**Depends on.** nothing.  
**Doc caveat.** The 20%/26% magnitudes are Dhaka end-of-day under one ARIMA/GARCH setup; the zero-return dilution mechanism transfers, the figures do not, and this repo never applies the backward-fill case.

### H1 - Trial ledger and dispersion-aware deflation

**Target.** `strategies/trial_ledger.py` (new): `record(candidate_id, window, returns_sha, sharpe, as_of)`; `strategies/evaluate.py:103` (`deflated_sharpe`) gains an optional `sharpe_dispersion` argument and the standard selection threshold

```text
SR*_0 = sqrt(V) * [ (1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e)) ]   g = Euler-Mascheroni
```

**Phase / run mode.** P0 / in-run  
**Behaviour.** `N` and the trials' Sharpe dispersion `V` come from the ledger, **never from a caller's assertion**; the existing caller-supplied path, `alpha_zoo.bench_zoo`, switches to the ledger, and every deflated number the score panel or coverage scorecard publishes carries its `N` beside it. CSCV uses `S = 8`, not `S = 16` (16 is 12,870 recombinations).  
**Gate.** `enable_trial_ledger`, default off.  
**Failing-first test.** New `tests/test_trial_ledger.py::test_dispersion_changes_deflated_sharpe`: two candidate sets with the same `N` but different Sharpe dispersion must produce different deflated values, so a mutation that ignores `sharpe_dispersion` fails by name.  
**Acceptance.** With dispersion supplied, the deflated Sharpe matches the closed form; with it absent, today's behaviour is preserved bit-for-bit and the result carries `dispersion: "assumed"`.  
**Depends on.** nothing (H3 depends on this ledger).  
**Doc caveat.** The DSR construction is standard Bailey-Lopez de Prado; the paper's contribution is the architecture (one entry point plus a ledger), not a new statistic.

### H7 - Refusal ledger and save-to-miss ratio

**Target.** `strategies/refusal_ledger.py` (new), beside `strategies/prediction_ledger.py` (whose `score_outcome` shape is the template) and `strategies/alpha_health.py`: one row per refused candidate (symbol, as-of, gate, reason, input snapshot hash), plus a forward sampler that classifies each refusal against subsequent price paths into the paper's five tiers.  
**Phase / run mode.** P0 / in-run  
**Behaviour.** The engine records decisions **taken**; this records candidates **refused**, so a guardrail's precision becomes measurable. Tie-break rule from the paper: **missed beats saved**. Storage and IO bound; classification is a single deterministic pass.  
**Gate.** `enable_refusal_ledger`, default off.  
**Failing-first test.** New `tests/test_refusal_ledger.py::test_tie_break_missed_beats_saved`: a mutation that drops the "missed beats saved" tie-break must fail by name, asserting the tier assigned to a refusal that both saved capital and missed a subsequent run.  
**Acceptance.** Gate sources are the engine's own refusals (risk governor, knife guard, tradability, news admission, value-dip floors); the per-gate save-to-miss ratio is reported **with its event count**, as a taxonomy plus discipline, never as a constant.  
**Depends on.** nothing (N7's rejections and X2's dropped components log into this ledger).  
**Doc caveat.** The paper's generalisation is weak - 13 to 22 days, one chain, one deployment, one regime - and its headline tier was refuted by its own test; adopt the taxonomy and the discipline, not the ratio.

### H11 - Autocorrelation-aware intervals and information gap

**Target.** `strategies/conformal.py:143` (`rolling_band`) gains the information-gap axis beside its coverage; a block-bootstrap interval is added for every claim statistic `scripts/score_panel.py` and `scripts/coverage_scorecard.py` publish, with the block length chosen from lag-1 autocorrelation plus an ADF check.  
**Phase / run mode.** P0 / in-run  
**Behaviour.** A pooled band can be wide and still uninformative; the second axis is the log-score of the pooled band against a conditional-scale alternative on the same calibration window, reported per band and `unavailable` below the `min_n` floor. Seconds at panel size.  
**Gate.** `enable_bootstrap_intervals`, default off.  
**Failing-first test.** New `tests/test_bootstrap_intervals.py::test_block_interval_covers_ar1`: on a synthetic AR(1) series the IID interval under-covers, so a mutation substituting the IID interval for the block interval fails by name.  
**Acceptance.** On a synthetic AR(1) series the IID interval under-covers and the block interval does not; the information-gap value is reported for a wide-but-uninformative band and differs from a narrow informative one.  
**Depends on.** nothing (its intervals feed H4's `excess_accuracy`, H6's verdicts, K1's band and R2's coverage test).  
**Decision.** In-house moving-block bootstrap versus the public `tsbootstrap` library (section 5).  
**Doc caveat.** 2608.07479 reports the gap as an identity under a maintained link; treat it as a diagnostic, not a test.

### H4 - R-squared ceiling and excess accuracy

**Target.** `strategies/alpha_eval.py` and `strategies/calibration.py`: `ceiling_ratio(returns, forecasts) -> (kappa_hat, (2DA-1)^2, R2_OOS/kappa)` and `excess_accuracy(pred, realized, baseline="always_up")`; the GARCH leg is `strategies/volatility_models.py:425` (`garch11_fit`), which exists and is wired to no evaluation path today and is read here as a reader, not as a second authority in the risk channel.  
**Phase / run mode.** P0 / in-run  
**Behaviour.** `sigma_hat` is an **out-of-sample** GARCH(1,1) fit; a `((2DA-1)^2, R2_OOS/kappa)` point above the 45-degree line is flagged, and `excess_accuracy` is reported with walk-forward folds and block-bootstrap intervals from H11. Read the ceiling as a falsifier, never as a validator.  
**Gate.** `enable_accuracy_ceiling`, default off.  
**Failing-first test.** New `tests/test_accuracy_ceiling.py::test_above_line_point_is_flagged`: a constructed forecast with positive `(2DA-1)^2` and negative OOS `R^2` must be flagged, so a mutation that drops the out-of-sample requirement on `sigma_hat` fails by name.  
**Acceptance.** The impossible point above the 45-degree line is flagged, and dropping the out-of-sample requirement on `sigma_hat` turns the test red. `O(T)` plus one MLE fit - sub-second at these lengths.  
**Depends on.** H11 (block-bootstrap intervals for the excess-accuracy report).  
**Doc caveat.** 2602.07841 is an inequality derived from a constructed oracle, not a test - it can flag an impossible point but cannot reject a forecast, and `kappa` assumes sign/magnitude independence.

### H6 - Three-way verdict and family FDR

**Target.** `strategies/evaluate.py`: `materiality_verdict(stat, ci_low, ci_high, delta)` plus a family-level FDR over a batch of candidate signals (the familywise machinery `reality_check`/`spa` already supply) and an exposure-time-matched benchmark arm in `benchmark_table`, which today compares on a common window without matching time in market; `agents/utils/report_verifier.py` takes the verdict vocabulary SUPPORTED / REFUTED / INCONCLUSIVE.

```text
REFUTED      iff U_S < delta_S  or  U_R < delta_R  or survival fails
SUPPORTED    iff L_S > delta_S  and L_R > delta_R  and survives
INCONCLUSIVE iff the interval straddles the threshold   (underpowered, NOT null)
```

**Phase / run mode.** P0 / in-run  
**Behaviour.** `delta_S = 0.20` and `delta_R = 0.01` are **pre-declared in config**, not chosen after the fact, and a non-significant result is recorded as unresolved rather than as evidence of no edge - **INCONCLUSIVE must never collapse into REFUTED**. The comparator is exposure-matched: the same binary position replayed against buy-and-hold-when-in, cash-when-flat, cost-free.  
**Gate.** `enable_materiality_verdict`, default off.  
**Failing-first test.** New `tests/test_materiality_verdict.py::test_straddling_interval_is_inconclusive`: an interval straddling `delta` must yield INCONCLUSIVE, not REFUTED, so a mutation that collapses INCONCLUSIVE into REFUTED fails by name.  
**Acceptance.** The straddling interval is INCONCLUSIVE; the vocabulary reaches `agents/utils/report_verifier.py`, and every later phase's findings can be INCONCLUSIVE.  
**Depends on.** H11 (intervals for the verdict).  
**Doc caveat.** The thresholds are declared but admittedly non-canonical, and the unit of analysis is a catalogued rule, not a portfolio.

### H2 - Availability-typed factor DSL gate

**Target.** `strategies/factor_expressions.py` (the gate) and `strategies/factor_schema.py` (the record): the nine-field factor record gains an explicit **availability** declaration, and the AST gate rejects (a) any forward shift and (b) any field whose declared availability is later than the decision date, bound to `data_quality.fundamentals_pit_ok` and `dataflows/pit_registry.read_as_of`.  
**Phase / run mode.** P2 / in-run  
**Behaviour.** Look-ahead becomes **inexpressible rather than discouraged**: a side-effect-free expression that references a field unobservable at the decision date, or shifts a series forward, is rejected before it can run. This is the PIT mechanism for expressions; static analysis at registration time, zero per run.  
**Gate.** `enable_factor_availability_gate`, default off.  
**Failing-first test.** New `tests/test_factor_availability_gate.py::test_late_availability_field_rejected`: a mutation that removes the forward-shift rejection must fail by name; the test registers an expression whose declared availability is later than the decision date and asserts rejection at registration time.  
**Acceptance.** Registration-time rejection of a forward shift and of a late-availability field; the nine-field record carries the availability declaration; no per-run cost.  
**Depends on.** H8's per-field availability table (publication lag for macro and vendor fields, filing date for fundamentals).  
**Doc caveat.** The paper's oracle is a deliberately extreme contamination, not a model of realistic leakage; a registry that is wrong about a field's availability reintroduces the leak with more confidence.

### H5 - Five-gate verdict, positive controls, and the next-open variant

**Target.** `strategies/rule_eval.py`: a `fill_on_next_bar` variant of rule evaluation, using the convention `strategies/backtest_engine.py`'s `MatchingEngine` already applies and `rule_eval` does not, reporting the **triple** side by side - ranking skill, average precision at the label prevalence, and realized net policy return - with the entry convention **named**; the five-gate conjunction sits beside `strategies/evaluate.py`.  
**Phase / run mode.** P3 / in-run  
**Behaviour.** `rule_eval.forward_returns` (`:32`) measures from `closes[i]`, the signal bar's own close: a legitimate *information* statistic, not a net-of-cost policy result. The five gates are out-of-sample `T >= 2.0`, `>= 30` trades per fold, positive net of an instrument-specific friction floor, the same sign across all test years, and `p_perm < 0.001`, with the training year excluded from the year-stability gate to avoid circularity; **positive controls** - signals known to carry edge that must still pass - detect a harness that has gone blind.  
**Gate.** `enable_rule_policy_gates`, default off.  
**Failing-first test.** New `tests/test_rule_policy_gates.py::test_positive_control_detects_blind_harness`: a mutation that removes the positive controls must fail by name, because with them removed the harness reports a known-edge control signal as failing.  
**Acceptance.** A known-edge positive control still passes, the entry convention is named on every reported triple, and the five gates are conjunctive. Cheap once bars exist; the permutation test is the only material cost.  
**Depends on.** nothing item-level (P3 follows P0 and P1).  
**Doc caveat.** 2605.04004 is a pure negative result on one futures instrument over one regime window, and its positive controls carry disclosed selection exposure; the protocol transfers, its friction floor (`2.0` points on MNQ) and trade minima do not.

### H8 - Vintage/lag guard and the non-LLM comparator

**Target.** `strategies/data_quality.py` (the PIT invariant) and `dataflows/`: a publication-lag table for scheduled macro releases, an as-reported vintage store (or a documented lag substitution), an archived-nowcast substitution where one exists, and the **mandatory non-LLM comparator on the identical input set** before any LLM signal is credited. `dataflows/pit_registry.read_as_of` masks payloads by as-of date, but only for payloads stored under the right date - the vintage store is the missing half.  
**Phase / run mode.** P3 / in-run (one extra fetch per series per run; negligible in a 4-symbol run)  
**Behaviour.** A month-end read that takes the current vintage leaks future information silently, because the value is simply present - the BLS publishes CPI roughly ten days after the month-end decision date and revisions follow. The guard consults the lag table, reads the as-reported value, and withholds credit from any LLM signal until a non-LLM analog is re-scored on the identical input set, generalising `strategies/quant_baseline.py` from "the engine" to "a claimed signal".  
**Gate.** `enable_vintage_guard`, default off.  
**Failing-first test.** New `tests/test_vintage_guard.py::test_llm_signal_needs_non_llm_comparator`: a mutation that removes the comparator must fail by name; an LLM arm that beats the quant arm must not be credited when the comparator is dropped.  
**Acceptance.** A current-vintage read at a month-end decision date is refused and the comparator's result is part of the output, not optional. The reported median monthly rank IC is +0.154 with a bootstrap 95% CI of [-0.02, +0.28] that includes zero and a permutation p of 0.11, against a plain kNN baseline at +0.161.  
**Depends on.** nothing (its lag table is what H2 consumes).  
**Doc caveat.** The paper's own pipeline is statistically underpowered - a median over 36 monthly points with per-month IC standard deviation around 0.45 - and the authors say so; adopt the guard, not the headline.

### H9 - Report attribution and factor novelty

**Target.** A new module beside `strategies/score_disagreement.py` (which already compares quant and LLM risk reads): `attribution(reports, thesis) -> weights` by a **non-negative least squares** projection of the thesis vector onto the four report vectors, and a novelty screen for a newly admitted factor against the existing zoo plus a disclosed reference set. The per-claim granularity it sits above is `strategies/debate_claim.py`'s; the reference-set machinery is `strategies/peer_universe.py`'s.  
**Phase / run mode.** P3 / in-run  
**Behaviour.** The engine cannot say which analyst report drove a decision, and cannot say whether a "new" factor is a relabelling. `novelty = mean_f max_{z in Z} |corr(s_f, z)|` against a reference set `Z` held out from generation, and productivity, performance and novelty are required **jointly** - no one meaningful without the other two. One embedding pass per report plus a small NNLS solve; descriptive of a completed run, no look-ahead; the paper's rolling re-execution protocol is out of scope.  
**Gate.** `enable_report_attribution`, default off.  
**Failing-first test.** New `tests/test_report_attribution.py::test_relabelled_factor_flagged`: a mutation that removes the novelty screen must fail by name; a factor that is a relabelling of an existing zoo member must be flagged.  
**Acceptance.** Influence weights are non-negative and attribute the thesis across the report vectors; a relabelled factor is flagged rather than admitted as new.  
**Depends on.** nothing.  
**Doc caveat.** 2609.00731's own headline is a near-tie against a DSR-equivalent on synthetic ground truth, and it admits a residual backbone-leakage it cannot remove.

### H3 - Synthetic-null workflow falsification

**Target.** A new module, with its diagnostics beside `evaluate.walk_forward_splits`: Stage 1 is a null-environment harness running the whole pipeline (preprocessing, feature construction, tuning, selection, portfolio mapping) under five reference classes - white noise, two-state regime-switching volatility, a bid-ask-bounce place bar, a single mean-zero factor plus noise, and GARCH(1,1) - with `N = 1000` replications each, falsifying if the walk-forward winner exceeds that environment's empirical `(1-alpha)` quantile. Stage 2 computes the inflation diagnostics:

```text
Z_IS,k = Rbar_IS,k / sqrt(VHAC(Rbar_IS,k));   Z*_IS = max_k |Z_IS,k|
Delta_Z = Z*_IS - Z*_WF
K_eff   = (sum lambda_i)^2 / sum lambda_i^2   from the candidate correlation matrix
```

**Phase / run mode.** P4 / OFFLINE  
**Behaviour.** `strategies/falsification.py` falsifies a *thesis*; this falsifies a *pipeline* - run the whole thing on data with no signal in it and see whether it still reports some. `5 x 1000` pipeline replays are prohibitive in-run and fine offline; Stage 2 is `O(K^2)` once. Carry the paper's headline warning into the output: familywise false-positive probability is **5.3% at `K = 1` and 92.3% at `K = 50`**.  
**Gate.** none (offline harness/script; ground rule 8 forbids calling it from `prepare_initial_state`, `finalize_run`, or any agent tool).  
**Failing-first test.** The harness run is its own proof: on the white-noise reference class a deliberately planted leaky candidate must exceed the null band and a clean pipeline must stay inside it.  
**Acceptance.** The walk-forward winner is inside the environment's empirical `(1-alpha)` quantile for a clean pipeline and outside it for a planted leak; `Delta_Z` and `K_eff` are reported from the retained candidate matrix.  
**Depends on.** H1's ledger - a **hard ordering constraint**: H3 cannot land before H1 exists, because Stage 2 consumes the retained candidate matrix that H1's ledger is what makes possible.  
**Doc caveat.** The authors are explicit that this is a necessary-condition screen, not a certification, and that a pipeline can be tuned to pass it.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| H10 | coverage window + survivor labelling | `strategies/coverage_window.py` (new) | P0 | in-run | `enable_coverage_window` |
| H1 | trial ledger + dispersion-aware deflation | `strategies/trial_ledger.py` (new), `strategies/evaluate.py:103` | P0 | in-run | `enable_trial_ledger` |
| H7 | refusal ledger + save-to-miss ratio | `strategies/refusal_ledger.py` (new) | P0 | in-run | `enable_refusal_ledger` |
| H11 | autocorrelation-aware intervals + information gap | `strategies/conformal.py:143` | P0 | in-run | `enable_bootstrap_intervals` |
| H4 | R-squared ceiling + excess accuracy | `strategies/alpha_eval.py`, `strategies/calibration.py` | P0 | in-run | `enable_accuracy_ceiling` |
| H6 | three-way verdict + family FDR | `strategies/evaluate.py`, `agents/utils/report_verifier.py` | P0 | in-run | `enable_materiality_verdict` |
| H2 | availability-typed factor DSL gate | `strategies/factor_expressions.py`, `strategies/factor_schema.py` | P2 | in-run | `enable_factor_availability_gate` |
| H5 | five-gate verdict + positive controls + next-open variant | `strategies/rule_eval.py` | P3 | in-run | `enable_rule_policy_gates` |
| H8 | vintage/lag guard + non-LLM comparator | `strategies/data_quality.py`, `dataflows/` | P3 | in-run | `enable_vintage_guard` |
| H9 | report attribution + factor novelty | new module beside `strategies/score_disagreement.py` | P3 | in-run | `enable_report_attribution` |
| H3 | synthetic-null workflow falsification | new offline harness | P4 | OFFLINE | none (offline harness/script) |

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_coverage_window` | H10 | `strategies/coverage_window.py`, refusal at the dependent panel statistic | off |
| `enable_trial_ledger` | H1 | `strategies/evaluate.py:103` `deflated_sharpe` | off |
| `enable_refusal_ledger` | H7 | `strategies/refusal_ledger.py` | off |
| `enable_bootstrap_intervals` | H11 | `strategies/conformal.py:143` (`rolling_band`) | off |
| `enable_accuracy_ceiling` | H4 | `strategies/alpha_eval.py`, `strategies/calibration.py` | off |
| `enable_materiality_verdict` | H6 | `strategies/evaluate.py` `materiality_verdict`, `agents/utils/report_verifier.py` | off |
| `enable_factor_availability_gate` | H2 | `strategies/factor_expressions.py` AST gate | off |
| `enable_rule_policy_gates` | H5 | `strategies/rule_eval.py` | off |
| `enable_vintage_guard` | H8 | `strategies/data_quality.py` PIT invariant | off |
| `enable_report_attribution` | H9 | new module beside `strategies/score_disagreement.py` | off |

The six registration points per gate are listed in [`README.md`](README.md).

## 4. Dependencies

```text
H10 coverage_window ....... gates every panel statistic in P1 and P4
H1  trial ledger .......... -> H3 (Stage 2 retains the candidate matrix)
H11 intervals ............. -> H4 excess_accuracy, H6 materiality, K1 band, R2 coverage test
H7  refusal ledger ........ -> N7 (rejections logged), X2 (dropped components logged)
H6  three verdicts ........ -> every later item's findings, which must be able to be INCONCLUSIVE
H8  vintage lag table ..... -> H2 (a per-field availability table)
H3  null harness .......... <- H1's ledger (hard ordering constraint)
```

Within this theme exactly one ordering constraint is hard: **H3 cannot land before H1's ledger
exists**. The rest of H1-H11 is independently landable, one item per commit, each behind its own
default-off gate, with the P3 items following P0 and P1.

## 5. Decisions requested (owner)

1. **The theme's own line:** which subset to build, and whether **H10 + H1 + H7** land together as a
   first pass. The design doc's recommended order is H10, H1, H7, H4, H6, H11, then H2, H5, H8, H9,
   H3 - H3 last because it is offline, expensive, and depends on H1's ledger existing.
2. **H11:** in-house moving-block bootstrap (no new dependency, and the block-length rule is already
   specified) versus the public `tsbootstrap` library, which buys the adaptive conformal calibrators
   (EnbPI, ACI, NexCP, AgACI) the paired band wants (section 2.4).
3. **H8's data sourcing:** an as-reported vintage store needs ALFRED (or a documented lag
   substitution); `dataflows/pit_registry.read_as_of` masks payloads by as-of date but only for
   payloads stored under the right date, so the vintage store is the missing half.

## 6. Honest limits

1. **A gate is not evidence of an edge.** Adopting all eleven items makes the engine harder to fool
   and no more likely to be right; none of them produces a return.
2. **Nothing here has been tested against this engine's data.** H10's mechanism is the only one the
   repo is already half-instrumented for; the rest are proposals until the harness says otherwise.
3. **Three of the source papers report null or refuted results**, which is why they were selected:
   H5's study is a pure negative result on one instrument, H7's headline tier was refuted by its own
   matched lifecycle test, and H8's pipeline is underpowered by its authors' own admission. The
   caveat travels with every item above.
4. **Two items touch surfaces that already have a producer** (H4's GARCH leg into the risk channel;
   H10's window into data quality). Both are readers of existing producers, not second authorities;
   either one computing a quantity its neighbour already owns violates inherited ground rule 2.
5. **H3 and H5's permutations are too expensive for the ~40-minute four-symbol run** - H3 is offline
   by construction and ground rule 8 forbids calling it in-run, and H5's permutation harness is the
   only material in-run cost of its card.
