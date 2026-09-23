# Design: Honest Evaluation Gates for the Engine's Own Claims

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The engine produces claims: a rating, a score, a report, a signal. This doc specifies the
gates that decide whether a claim is *earned*. It is the design output of the 2026 `q-fin` corpus
survey (`docs/design_fin_paper_survey_26.md`), which found honest evaluation to be the largest and
most transferable theme in the corpus - 12 high- and 30 medium-relevance papers - and the theme
this engine is least equipped for, because the engine's own output is the thing being judged.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Rule-4 impact:** none. Nothing here touches the engine's externally visible surface; the app
reads reports and scores, and no schema changes.

---

## 1. Executive summary

### The argument the corpus makes

Four papers, independently, make the same structural argument: **statistical correction is applied
after the leak has already entered, so it cannot remove it.**

The sharpest demonstration is 2608.27734's planted oracle. It builds a strategy-discovery agent
whose actions are restricted to registry-validated tools, then deliberately adds a leaky oracle
into that registry. The oracle posts **Sharpe 34.7 in the design window and 51.5 in evaluation**
and scores a **Deflated Sharpe of 1.00 while surviving the probability-of-backtest-overfitting
test completely.** No deflation catches it, because the leak is not selection - it is contamination,
and every one of its evaluations is contaminated. The authors' conclusion is that the fix is
**expressibility, not discipline**: look-ahead must be *inexpressible* in the action surface, and
"prompting an LLM to avoid look-ahead is a weak guardrail".

The same paper supplies the second instrument: a **trial ledger**. Every evaluation the agent
performs is recorded, and every reported Sharpe is deflated by that count. On a 453-stock
point-in-time universe it certifies passive benchmarks and rejects every LLM-discovered strategy
(best: design Sharpe 1.69, DSR 0.86 against a 0.95 bar, evaluation Sharpe 0.18).

2609.00731 adds that the *discovery process* is itself a research object that can get lucky, and
that scoring its static output cannot distinguish a well-calibrated gate from a leaked one from a
favourable window.

### Why this engine is exposed

The engine's report tree is a claim. It contains ratings, per-engine scores, a composite, and prose
that cites numbers. Three specifics make the exposure concrete:

1. **The composite is a search.** `TradeScore = 0.40F + 0.25T + 0.15R + 0.20K` over four engines,
   each of which is itself a weighted sum of components. Every weight in that tree was chosen by
   someone at some point. `evaluate.deflated_sharpe` (`tradingagents/strategies/evaluate.py:103`)
   takes a caller-supplied `n_trials` and approximates the expected maximum Sharpe as
   `sqrt(2*ln(n_trials))`, subtracting it from the observed Sharpe. Nothing in the repo records the
   trials, and the function never sees the trials' Sharpe dispersion at all.
2. **Advisory reads are quoted as evidence.** `rule_eval.forward_returns`
   (`tradingagents/strategies/rule_eval.py:32`) measures forward returns from `closes[i]` - the
   signal bar's own close. That is the correct measurement for *"does this indicator carry
   information"* and the wrong one for *"what would this have earned"*, because an entry at the
   close that produced the signal is not executable. The corpus reports repeatedly that the first
   quantity does not convert into the second.
3. **The engine cannot see its own refusals.** `prediction_ledger` and `invalidation_ledger` record
   decisions that were **taken**. Nothing records the candidates the engine's gates **refused**, so
   the precision of the engine's own guards is unmeasurable today.

### The one-sentence thesis

> Every number the engine publishes should be traceable to the search that produced it, the
> coverage that licenses it, and the trials that inflate it - and where a claim cannot carry those
> three, it should be reported as unresolved rather than as evidence.

---

## 2. What this repo already has (verified)

Taken first. Each row was checked in the tree, not recalled.

| Instrument | Where, verified |
|---|---|
| Deflated / probabilistic Sharpe, PBO-ish flag, RC, SPA, purged CPCV splits | `strategies/evaluate.py:103` `deflated_sharpe`, `:181` `purged_cpcv_splits`, `:235` `pbo_flag`, `:311` `reality_check`, `:351` `spa`, `:545` `probabilistic_sharpe` |
| Walk-forward splits, cost-aware metrics | `strategies/evaluate.py` |
| Robust choice over a config grid (not argmax) | `strategies/config_robustness.py:66` `config_robustness` |
| Immutable prediction rows scored against later outcomes | `strategies/prediction_ledger.py` |
| Thesis invalidation ledger | `strategies/invalidation_ledger.py` |
| Numeric falsifiers bound to a thesis | `strategies/falsification.py` |
| Confidence calibration table | `strategies/calibration.py:22` `calibration_table` |
| Direction + magnitude + horizon scoring | `strategies/alpha_eval.py:20` `alpha_score`, `insight_accuracy` |
| Rank IC / IC-IR over any score series | `strategies/signal_analysis.py:64` `rank_ic`, `icir` |
| Per-period IC over the decision ledger | `strategies/alpha_health.py:200` `per_period_ic` |
| Deflated IC + RC/SPA over an expression zoo | `strategies/alpha_zoo.py:243` `bench_zoo` |
| Bounded expression DSL with an AST purity gate | `strategies/factor_expressions.py`, `strategies/alpha_zoo.py` |
| Nine-field factor identity record | `strategies/factor_schema.py` |
| Conformal (CQR) bands with stated coverage | `strategies/conformal.py:143` `rolling_band` |
| Decision-level input quality, cross-vendor disagreement, PIT invariant | `strategies/data_quality.py` |
| Regime-conditioned performance attribution | `strategies/regime_performance.py:24` `regime_conditioned_performance` |
| An LLM-free baseline stack | `strategies/quant_baseline.py` |
| Per-indicator minimum-history guard | `dataflows/market_data_validator.py:34` `_INDICATOR_MIN_BARS` |
| IGARCH breakdown guard at exactly the threshold the corpus reports | `strategies/volatility_models.py:40` `_IGARCH_AB = 0.999` |
| Tamper-evident append-only audit ledger | `strategies/hash_chain_audit.py` |
| A measured conditional prior, as precedent | `strategies/market_session.py:220` `gap_type` (empirical fill rate per gap class) |

The last two rows matter more than they look. `_IGARCH_AB = 0.999` is *the exact value* 2603.20237
reports as the GARCH-breakdown threshold on padded panels, and `gap_type` is already the shape a
measured conditional prior takes here. The engine is not starting from zero on either idea.

---

## 3. The gaps, as builders

Each item: the finding, the paper, what to compute, what it needs, its point-in-time status, its
cost, the owner, and the paper's own caveat carried forward.

### H1 - The trial ledger, and deflation that can see it

**Finding.** `evaluate.deflated_sharpe` (`:103`) implements the selection penalty as
`observed - sqrt(2*ln(n_trials))` and takes `n_trials` as a caller-supplied integer. Two things are
missing: the count is an assertion rather than a measurement, and the trials' **Sharpe dispersion
`V` never enters**. The correct selection threshold under the standard construction is

```text
SR*_0 = sqrt(V) * [ (1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e)) ]     g = Euler-Mascheroni
DSR   = Phi( (SR_hat - SR*_0) * sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) )
```

so a search whose trials were tightly clustered is penalised differently from one whose trials were
wildly dispersed, and the current implementation cannot tell them apart.

**Paper.** 2608.27734 - one evaluation entry point, a ledger row per distinct evaluation, `N` from
the ledger, `V` from the ledger's Sharpe distribution; CSCV PBO over the design-window return
matrix; an evaporation curve of best-of-first-k Sharpe against its k-trial threshold.

**What to compute.** `trial_ledger.record(candidate_id, window, returns_sha, sharpe, as_of)` and a
`deflated_sharpe(..., n_trials, sharpe_dispersion)` overload. Every deflated number the score panel
or coverage scorecard publishes carries its `N` beside it.

**Inputs.** Per-candidate design-window return series. All derivable from bars already fetched.

**PIT.** Honest by construction: the design window precedes the evaluation window, and the
evaluation window is never visible to the search.

**Cost.** Deflation is microseconds. The ledger's real footprint is storing `N` candidate return
series; CSCV is `C(S, S/2)` recombinations, so use `S = 8` not `S = 16` (16 is 12,870).

**Owner.** `strategies/evaluate.py`, beside `alpha_zoo.bench_zoo` which already calls
`deflated_sharpe` with a caller-supplied count.

**Caveat.** The DSR construction is standard Bailey-Lopez de Prado; the paper's contribution is the
*architecture* (one entry point + a ledger), not a new statistic.

### H2 - Make look-ahead inexpressible, not merely discouraged

**Finding.** The repo has a bounded expression DSL and an AST purity gate, which is a real
head start. But *pure* is not *causal*: a side-effect-free expression can still reference a field
that was not observable at the decision date, or shift a series forward.

**Paper.** 2608.27734's central claim: a leaky oracle survives DSR=1.00 and PBO completely, so the
leak must be removed from the action surface rather than corrected afterwards.

**What to compute.** Extend the nine-field `factor_schema` record with an explicit availability
declaration, and have the AST gate reject (a) any forward shift and (b) any field whose declared
availability is later than the decision date. Bind it to the two producers that already know the
answer: `data_quality.fundamentals_pit_ok` and `dataflows/pit_registry.read_as_of`.

**Inputs.** A per-field availability table - publication lag for macro and vendor fields, filing
date for fundamentals.

**PIT.** This *is* the PIT mechanism.

**Cost.** Static analysis at expression-registration time; zero per run.

**Owner.** `strategies/factor_expressions.py` (the gate), `strategies/factor_schema.py` (the record).

**Caveat.** The paper's oracle is a deliberately extreme contamination, not a model of realistic
leakage; a registry that is wrong about a field's availability reintroduces the leak with more
confidence.

### H3 - Falsify a workflow against synthetic nulls

**Finding.** `strategies/falsification.py` falsifies a *thesis* - numeric invalidation levels bound
to a claim. Nothing falsifies a *pipeline*: run the whole thing on data with no signal in it and see
whether it still reports some.

**Paper.** 2604.15531 runs the entire pipeline (preprocessing, feature construction, tuning,
selection, portfolio mapping) under five reference classes - white noise, two-state regime-switching
volatility, a bid-ask-bounce place bar, a single mean-zero factor plus noise, and GARCH(1,1) - with
`N = 1000` replications each, and falsifies if the walk-forward winner exceeds that environment's
empirical `(1-alpha)` quantile. Its inflation diagnostics are the reusable part:

```text
Z_IS,k = Rbar_IS,k / sqrt(VHAC(Rbar_IS,k));   Z*_IS = max_k |Z_IS,k|
Delta_Z = Z*_IS - Z*_WF                       (mean |Z*_IS| 2.79 at K=100 vs 0.80 walk-forward)
K_eff   = (sum lambda_i)^2 / sum lambda_i^2   from the candidate correlation matrix
```

Its headline warning is the one to internalise: **familywise false-positive probability is 5.3% at
`K = 1` and 92.3% at `K = 50`.** A search of fifty candidates will find something.

**What to compute.** A null-environment harness (Stage 1, offline, never in-run) plus Stage 2's
`Delta_Z` and `K_eff` from the retained candidate matrix.

**Inputs.** Stage 1 needs only the calibrated generators. Stage 2 needs every candidate's statistic
series, which the H1 ledger is what makes possible.

**Cost.** Stage 1 is `5 x 1000` full pipeline replays - prohibitive in-run, and fine offline. Stage
2 is `O(K^2)` once.

**Owner.** New module; diagnostics sit beside `evaluate.walk_forward_splits`.

**Caveat.** The authors are explicit that this is a **necessary-condition screen, not a
certification**, and that a pipeline can be tuned to pass it.

### H4 - Accuracy honesty: a ceiling and a base rate

**Finding.** The engine scores directional hits (`calibration_table`, `alpha_eval.alpha_score`) with
no reference to what those hits are worth, and no always-up baseline.

**Papers.** 2602.07841 derives a hard ceiling linking the two quantities:

```text
plim R^2_OOS <= kappa * (2*DA - 1)^2
kappa = (E[sqrt(eps)])^2 / E[eps] - 1         eps_t = r_t^2 / sigma_hat_t^2
```

with `sigma_hat` from an **out-of-sample** GARCH(1,1). A model whose `((2DA-1)^2, R^2_OOS/kappa)`
point sits above the 45-degree line is not evidence of skill - many points in the paper show a
positive `(2DA-1)^2` with a *negative* `R^2_OOS`. 2607.12248 supplies the companion: report **excess
accuracy** (model minus always-up on identical windows) with walk-forward folds, a held-out-ticker
split, block-bootstrap intervals, and paired McNemar / Diebold-Mariano tests under FDR control.

**What to compute.** `ceiling_ratio(returns, forecasts)` -> `(kappa_hat, (2DA-1)^2, R^2_OOS/kappa)`,
flagged when above the line; and `excess_accuracy(pred, realized, baseline="always_up")`.

**Inputs.** Realized returns and their out-of-sample forecasts; a GARCH(1,1) fit for the vol series.
`volatility_models.garch11_fit` (`:425`) exists but is wired to no evaluation path today.

**PIT.** Both use out-of-sample rows only; `sigma_hat` must be estimated on prior data.

**Cost.** `O(T)` plus one MLE fit - sub-second at these lengths.

**Owner.** `strategies/alpha_eval.py` and `strategies/calibration.py`, with the GARCH leg from
`strategies/volatility_models.py`.

**Caveat.** 2602.07841 is an **inequality derived from a constructed oracle, not a test**: it can
flag an impossible point but cannot reject a forecast, and `kappa` assumes sign/magnitude
independence. Read it as a falsifier of claims, never as a validator.

### H5 - A five-gate verdict, positive controls, and the informational-versus-executable line

**Finding.** `rule_eval.forward_returns` (`:32`) measures forward returns from `closes[i]`, the
signal bar's own close, and `evaluate_rule` reports the resulting stats. That is a legitimate
*information* statistic. It is not a net-of-cost policy result, and the corpus says the two differ
systematically.

**Papers.** 2605.04004 requires a signal to pass five gates **simultaneously** - out-of-sample
`T >= 2.0`, `>= 30` trades per fold, positive net of an instrument-specific friction floor, the same
sign across all test years, and `p_perm < 0.001` - and, critically, requires **positive controls**:
signals known to carry edge that must still pass, so a harness that has gone blind is detected.
2607.19453 reports the separation directly: ROC AUC 0.874/0.896 with average precision only
0.134/0.116, and a policy that lost 44.30% over seven cycles against buy-and-hold's -41.20%.

**What to compute.** Report the **triple** side by side - ranking skill, average precision at the
label prevalence, and realized net policy return - and require the entry convention to be named. Add
a `fill_on_next_bar` variant of the rule evaluation; the correct convention already exists in
`strategies/backtest_engine.py`'s `MatchingEngine` and is simply not what `rule_eval` uses.

**Inputs.** Per-trade net returns, fold and year labels, a per-candidate permutation harness, a
friction constant per instrument class.

**PIT.** Signal at close, entry next open, parameters fit only on training folds. 2605.04004
excludes the training year from its year-stability gate to avoid circularity - worth copying.

**Cost.** Cheap once bars exist; the permutation test is the only material cost.

**Owner.** `strategies/rule_eval.py`, with the five-gate conjunction beside `strategies/evaluate.py`.

**Caveat.** 2605.04004 is a pure negative result on one futures instrument over one regime window,
and its positive controls carry disclosed selection exposure. The *protocol* transfers; its friction
floor (`2.0` points on MNQ) and trade minima do not.

### H6 - Three verdicts, materiality, and family-level FDR

**Finding.** The engine's verifier emits FLAG verdicts. A non-significant result is not evidence of
no effect, and the corpus supplies the vocabulary that keeps the two apart.

**Paper.** 2607.20093 composes three pre-declared gates and classifies **REFUTED / SUPPORTED /
INCONCLUSIVE** using an exposure-time-matched benchmark and equivalence logic:

```text
REFUTED      iff U_S < delta_S  or  U_R < delta_R  or survival fails
SUPPORTED    iff L_S > delta_S  and L_R > delta_R  and survives
INCONCLUSIVE iff the interval straddles the threshold   (underpowered, NOT null)
```

with `delta_S = 0.20` and `delta_R = 0.01` declared in advance, two-stage hierarchical
Benjamini-Yekutieli control, and an exposure-matched comparator (the same binary position replayed
against buy-and-hold-when-in, cash-when-flat, cost-free). Of six candidate rules, four are REFUTED
and two INCONCLUSIVE - **none SUPPORTED**.

**What to compute.** A `materiality_verdict(stat, ci_low, ci_high, delta)` helper plus a
family-level FDR across a batch of candidate signals, and an exposure-time-matched benchmark arm in
`evaluate.benchmark_table` (which today compares on a common window without matching time in
market).

**Inputs.** Nothing new: existing intervals, plus pre-declared thresholds.

**PIT.** Honest as declared. Its own caveat: the stationary bootstrap resamples the same full sample,
so it is not a held-out test.

**Cost.** `O(days)` per family; the survival Monte Carlo dominates.

**Owner.** `strategies/evaluate.py` (`reality_check`/`spa` already supply familywise machinery) and
the verifier's verdict vocabulary in `agents/utils/report_verifier.py`.

**Caveat.** The thresholds are declared but admittedly non-canonical, and the unit of analysis is a
catalogued rule, not a portfolio.

### H7 - Log the refusals

**Finding, and the cleanest gap in this doc.** `prediction_ledger` and `invalidation_ledger` record
decisions **taken**. Nothing records candidates the engine **refused**. So a filter's precision -
capital saved versus profit forgone - is unmeasurable, and a report claiming a guardrail protected
the book cannot be contradicted by any computed artifact.

**Papers.** 2607.02830 classifies post-rejection forward outcomes into five tiers
(saved-windowed / missed-moon / saved-early-death / flat / unclassifiable) and reports a
**conservative save-to-miss ratio of 3.7:1** across 2,402 events - while showing the wider 14.8:1
reading rests on a tier its own matched lifecycle test **refutes** (48.9% reaching "gone" for
early-death-classified mints vs 57.6% for other rejected mints). 2605.12151 publishes the
underlying deposit so the classification rule itself becomes externally testable.

**What to compute.** A refusal ledger: one row per refused candidate (symbol, as-of, gate, reason,
input snapshot hash), plus a forward sampler that classifies each refusal against subsequent price
paths, plus the per-gate save-to-miss ratio. Tie-break rule from the paper: missed beats saved.

**Inputs.** The engine's own gate decisions (risk governor, knife guard, tradability, news
admission, the value-dip floors) and forward price paths - both already available.

**PIT.** All inputs are observed forward trajectories; the only hindsight risk is in the
classification rule, not the data.

**Cost.** Storage and IO bound; classification is a single deterministic pass.

**Owner.** New module, sitting beside `strategies/prediction_ledger.py` (whose
`score_outcome` shape is the right template) and `strategies/alpha_health.py`.

**Caveat.** The paper's own generalisation is weak - 13 to 22 days, one chain, one deployment, one
regime - and its headline tier was refuted by its own test. Adopt the *taxonomy and the discipline*,
not the ratio.

### H8 - A decision-time leakage guard on macro and news inputs

**Finding.** Macro series are read at their current vintage. The BLS publishes CPI roughly ten days
after the month-end decision date, and revisions follow. A month-end evaluation that reads the
current CPI value leaks future information - and this happens silently, because the value is simply
present.

**Paper.** 2606.22719 builds the honest version: lag-shifted FRED series plus the Cleveland Fed's
archived daily CPI nowcast read at `t`, then reports the result *symmetrically*. Median monthly rank
IC **+0.154 with a bootstrap 95% CI of [-0.02, +0.28] that includes zero** and a permutation p of
0.11 - and a plain kNN macro-analog baseline recovers a comparable median (+0.161). Its practical
lesson is that any LLM signal must be re-scored against a **non-LLM analog on the identical input
set** before the LLM is credited.

**What to compute.** A publication-lag table for scheduled macro releases, an as-reported vintage
store (or a documented lag substitution), an archived-nowcast substitution where one exists, and the
mandatory non-LLM comparator.

**Inputs.** FRED (with vintage awareness, ideally ALFRED), the archived nowcast, and the engine's
existing news corpus. `dataflows/pit_registry.read_as_of` already masks payloads by as-of date - but
only for payloads stored under the right date, so the vintage store is the missing half.

**PIT.** This *is* the PIT mechanism for macro.

**Cost.** One extra fetch per series per run; negligible inside a 4-symbol run.

**Owner.** `strategies/data_quality.py` (PIT invariant) and `dataflows/`; the comparator idea
generalises `strategies/quant_baseline.py` from "the engine" to "a claimed signal".

**Caveat.** The paper's own pipeline is statistically underpowered - a median over 36 monthly points
with per-month IC standard deviation around 0.45 - and the authors say so. Adopt the guard, not the
headline.

### H9 - Attribution and novelty

**Findings, two of them.** The engine cannot say which analyst report drove a decision, and cannot
say whether a "new" factor is a relabelling.

**Papers.** 2604.17327 embeds each analyst report and the PM's final thesis with the same text model
and solves a **non-negative least squares** projection of the thesis vector onto the four report
vectors to attribute per-run influence, then scores picks against same-date, same-count random
baskets. 2609.00731 requires **productivity, performance and novelty jointly** - no one meaningful
without the other two - where `novelty = mean_f max_{z in Z} |corr(s_f, z)|` against a disclosed
reference set `Z` held out from generation.

**What to compute.** `attribution(reports, thesis) -> weights` via NNLS over embeddings; and a
novelty screen on any newly admitted factor against the existing zoo plus a reference set.

**Inputs.** The report texts (already in the tree), an embedding model, and a reference factor set.
`strategies/debate_claim.py` already grounds individual claims, which is the per-claim granularity
this sits above.

**PIT.** Descriptive of a completed run; no look-ahead.

**Cost.** One embedding pass per report plus a small NNLS solve - negligible. The rolling
re-execution protocol in the same paper (hours of LLM calls) is out of scope here.

**Owner.** New module beside `strategies/score_disagreement.py` (which already compares quant and
LLM risk reads) and `strategies/peer_universe.py` (for the reference-set machinery).

**Caveat.** 2609.00731's own headline is a near-tie against a DSR-equivalent on synthetic ground
truth, and it admits a residual backbone-leakage it cannot remove.

### H10 - Coverage: record the window, and label the survivor

**Finding.** No module records when a symbol's series begins. A name listed forty bars ago silently
feeds truncated-window fallbacks and cross-sectional z-scores that mix 40-bar and 2,000-bar
histories, with nothing in the output naming the differing coverage.

**Papers.** 2603.20237 formalises *temporal coverage bias*: calendar-aligning instruments with
heterogeneous listing histories extends price history before valid trading began, and measures the
damage on 53 instruments - **return volatility suppressed by a mean 20.0%**, GARCH unconditional
variance distorted by **26.2%**, present in more than 90%, and backward extension breaking GARCH
estimation outright in **22 of 53** (`alpha + beta >= 0.999`). 2603.19380 measures the other
direction: survivor-only NIFTY Smallcap 250 backtests overstate returns by **4.94pp** and Sharpe by
**0.097**, because 82.5% of the stocks ever in the index had left it.

**What the repo already does - and it is unusually close.** `market_data_validator._INDICATOR_MIN_BARS`
(`:34`) flags every indicator whose bar count is below its window, and
`volatility_models._IGARCH_AB = 0.999` (`:40`) withholds the long-run variance when `alpha + beta`
reaches exactly the threshold the paper reports as breakdown. The missing half is the *window*.

**What to compute.** `coverage_window(series) -> {first_valid, last_valid, n_bars, padded_days,
alignment}` - read off the loaded frame, so it costs nothing - carried alongside any number computed
over it, and a rule that a panel statistic computed over a padded window is reported `unavailable`
rather than computed. Separately: label any backtest over a current-constituent universe
`survivor_only` in the findings ledger.

**Inputs.** The loaded price frame plus its listing boundary. No new vendor call.

**PIT.** Point-in-time honest: the first bar is a past fact.

**Cost.** `O(days)` per symbol, sub-millisecond.

**Owner.** New module (`strategies/coverage_window.py`), consumed by `strategies/data_quality.py` and
`scripts/coverage_scorecard.py`.

**Caveat.** The magnitudes are Dhaka end-of-day under one ARIMA/GARCH setup; the **zero-return
dilution mechanism** transfers, the 20%/26% figures do not, and this repo never applies the
backward-fill case.

### H11 - Intervals that respect autocorrelation

**Finding.** Panel statistics (hit rate, score-versus-outcome correlation) are quoted as points. A
daily series' autocorrelation makes an IID interval too narrow, and a band that is merely wide is
not the same as a good one.

**Papers.** 2607.06690 exposes block, residual, sieve and wild bootstrap plus adaptive conformal
calibrators (EnbPI, ACI, NexCP, AgACI) behind one spec-selected API, choosing the block length from
lag-1 autocorrelation and an ADF test. 2608.07479 adds the missing second axis: alongside realized
coverage, report the **information gap** - the log-score of the pooled band against a
conditional-scale alternative on the same calibration window - because a pooled band can be wide and
still uninformative.

**What to compute.** Block-bootstrap intervals for every claim statistic the score panel and
coverage scorecard publish; and, for the existing `conformal.rolling_band`, the information-gap
axis beside its coverage.

**Inputs.** Existing scored rows.

**PIT.** Not applicable - post-hoc measurement.

**Cost.** Seconds at panel size.

**Owner.** `strategies/conformal.py:143` (`rolling_band`), consumed by `scripts/score_panel.py` and
`scripts/coverage_scorecard.py`.

**Caveat.** 2608.07479 reports the gap as an identity under a maintained link; treat it as a
diagnostic, not a test.

---

## 4. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| H1 | trial ledger + dispersion-aware deflation | `strategies/evaluate.py` | yes (ledger) |
| H2 | availability-typed factor DSL gate | `strategies/factor_expressions.py`, `factor_schema.py` | no |
| H3 | synthetic-null workflow falsification | new | yes |
| H4 | R-squared ceiling + excess accuracy | `strategies/alpha_eval.py`, `calibration.py` | no |
| H5 | five-gate verdict + positive controls + next-open variant | `strategies/rule_eval.py` | no |
| H6 | three-way materiality verdict + family FDR | `strategies/evaluate.py`, `report_verifier.py` | no |
| H7 | refusal ledger + save-to-miss ratio | new | yes |
| H8 | publication-lag/vintage guard + non-LLM comparator | `strategies/data_quality.py`, `dataflows/` | partly |
| H9 | report attribution + factor novelty | new | yes |
| H10 | coverage window + survivor labelling | new (`coverage_window.py`) | yes |
| H11 | autocorrelation-aware intervals + information gap | `strategies/conformal.py` | no |

## 5. Honest limits

1. **A gate is not evidence of an edge.** Every item above measures claims; none of them produces a
   return. Adopting all eleven makes the engine harder to fool and no more likely to be right.
2. **The corpus's own results are mostly single-window, single-market, single-author preprints.**
   Each item carries its paper's caveat. Three of the papers explicitly report null or refuted
   results, which is why they were selected.
3. **H3 and H5's permutations are too expensive to run inside a 40-minute four-symbol run.** They
   are offline instruments by construction, and the doc says so where it matters.
4. **Nothing here has been tested against this engine's data.** H10's mechanism is the only one the
   repo is already half-instrumented for; the rest are proposals until the harness says otherwise.
5. **Two items would add producers to surfaces that already have one** (H4's GARCH leg into the
   risk channel; H10's window into data quality). Both are named as *readers* of existing producers
   rather than as second authorities, per the rule that no derived quantity may have two.

## 6. Recommended build order

Cheapest-and-highest-value first, each independently landable behind a config gate:

1. **H10** (`coverage_window`) - free to compute, closes a real silence, and the repo is already
   half-built for it.
2. **H1** (trial ledger + dispersion) - makes every existing deflated number honest.
3. **H7** (refusal ledger) - the only item that measures something the engine currently cannot see
   at all.
4. **H4** (ceiling + base rate) - cheap, and it constrains what a report may claim.
5. **H6** (three-way verdict) - a vocabulary change in the verifier, no new maths.
6. **H11** (intervals) - upgrades every published statistic at once.
7. **H2**, **H5**, **H8**, **H9**, **H3** - in that order; H3 last because it is offline and
   expensive and depends on H1's ledger existing.

**Decision requested:** which subset to build, and whether H10 + H1 + H7 land together as a first
pass.
