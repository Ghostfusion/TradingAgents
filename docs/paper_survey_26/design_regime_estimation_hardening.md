# Design: Regime Estimation Hardening

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The engine's regime channel - `regime_score`, the market-state axes, and the detectors
underneath them. This doc takes the 3 high- and 21 medium-relevance regime papers from the 2026
`q-fin` corpus survey and specifies what each would change. Its organising finding is that the
corpus's regime papers are mostly about **evidence discipline**, not about better detectors: two of
the three most load-bearing results are negative.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Plan:** [`implementation_plan_regime_estimation_hardening.md`](implementation_plan_regime_estimation_hardening.md) - the item-level implementation plan for the items this doc owns (v1.0, PLAN); the set index is [`README.md`](README.md).
**Rule-4 impact:** none. Regime reads are internal; no report schema changes.

---

## 1. Executive summary

### What the corpus says about regime detection

Three results, in order of how much they should change behaviour here.

**1. Regime labels are usually coincident, and their separability is measured offline.** 2608.10788
builds a network-topology stress index that beats the Absorption Ratio out of sample
(`F1@p90 0.447` vs `0.134`, `p < 0.0005`) - and states plainly that it is a **coincident index, not
a forecast**. 2605.17117 finds a learned geometric observable that separates crisis windows with
`d = 0.83` in-sample, then reports it collapsing to **`d = 0.26` on a frozen holdout**, while the
observable with worse offline rank (`d = 0.61`) carries the strongest walk-forward evidence. The
paper's own summary is that "offline separability does not guarantee out-of-sample stability". Both
papers also agree on the metric that matters: 2605.17117's headline is a **false-alarm rate**, ~1.2/yr
against a supervised Random Forest's 3.6/yr.

**2. A single early-warning variable is not invariant, and that is the finding.** 2607.27070 sweeps
39 detrending/window configurations across seven liquidation cascades and finds **no variable that
fires in all of them**: price carries the critical-slowing-down signature in 5 of 7 events and is
silent in exactly the two sudden-news shocks. Its only invariant - taker-order-flow variance
compression, Fisher-combined `p ~ 5e-6` over 300 placebos - is high-frequency order flow this engine
does not hold. The transferable instrument is not the indicator; it is the **placebo-null and
configuration-sweep requirement** that stopped a plausible-looking finding from being published as
universal.

**3. You cannot estimate regime-arrival risk from training data.** 2606.02657 decomposes the
future-minus-training risk gap exactly as `(p01 - pi)(R1 - R0)`, and then reports the split that
matters: the **ex-post** penalty tracks realized train-to-deployment gaps (`Spearman rho = 0.729`,
95% CI `[0.635, 0.801]`) while the **training-only** estimator does not (`rho ~ 0.084`, CI includes
zero). Regime geometry is detectable in hindsight; regime *arrival* is not. Any read that claims to
warn about an approaching shift should be labelled coincident unless it clears a walk-forward test.

### The concrete gaps, independently

Two papers land on machinery the engine already has, and specify a small, well-defined extension:

- **BOCPD with a duration law.** `strategies/regime.py:764` implements Adams-MacKay BOCPD with a
  **constant hazard**. 2609.07989 replaces that with a run-length-dependent hazard compiled from an
  explicit duration law inside a hidden semi-Markov model, and reports the log-normal duration law
  dominating geometric and Pareto consistently across assets, months and criteria. This is the
  single smallest high-value change in this doc: same recursion, different hazard.
- **Heavy-tailed HMM emissions.** `strategies/regime.py:367` fits a walk-forward **2-state Gaussian**
  HMM. 2606.23492 shows that with `K = 3` and Student-t emissions the model reproduces all three
  Cont stylised facts (out-of-sample kurtosis 4.46 against an observed 5.29, out-of-sample KS 82.1%)
  and **passes the Christoffersen joint conditional-coverage VaR test** on held-out data - and that
  marginal flexibility explains more of the fit gap than added states, since the ACF rank bound
  (`K-1` modes) does not bind at `K >= 3`.

### The one-sentence thesis

> This engine does not need a better regime detector; it needs its regime claims to state whether
> they are coincident or predictive, to carry a false-alarm rate, and to prove they beat a placebo
> before they enter a score.

---

## 2. What this repo already has (verified)

| Instrument | Where, verified |
|---|---|
| Realized-vol percentile (21d vs a reference window) | `strategies/regime.py:51` `vol_percentile` |
| Choppiness | `strategies/regime.py:133` `choppiness` |
| Walk-forward 2-state **Gaussian** HMM with filtered posteriors | `strategies/regime.py:367` `hmm_filtered_regime` |
| HMM regime label | `strategies/regime.py:507` `hmm_regime` |
| Adams-MacKay BOCPD, **constant hazard**, NIG prior, `zero_run_prob` / `map_run_length` | `strategies/regime.py:764` `bocpd` |
| Four independent regime-state axes | `strategies/regime_state.py` |
| Regime-conditioned performance attribution | `strategies/regime_performance.py:24` `regime_conditioned_performance` |
| Entropy features | `strategies/complexity.py:19` `permutation_entropy` |
| GARCH family + realized-vol estimators | `strategies/volatility_models.py:425` `garch11_fit` |
| Correlation matrix | `strategies/statistical.py:203` `correlation_matrix` |
| Lag-1..max autocorrelation + Ljung-Box | `strategies/book_risk.py:353` `return_autocorrelation` |
| Variance ratio, Hurst | `strategies/mean_reversion.py:216` `variance_ratio`, `:112` `hurst_exponent` |
| Trend strength | `strategies/quant_baseline.py:28` `trend_strength` (note: not in `regime.py`) |
| Idiosyncratic vol, market realized vol | `strategies/lottery.py:51` `idiosyncratic_vol`, `strategies/regime.py` |
| Breadth (market-wide and sector) | `strategies/market_breadth.py`, `strategies/sector_breadth.py` |
| Walk-forward splits | `strategies/evaluate.py:181`-family |

So the engine has a Gaussian HMM, a constant-hazard BOCPD, an entropy family, concentration reads
and attribution. What it does **not** have is any of the four disciplines below.

## 3. The gaps, as builders

### R1 - BOCPD with a duration law instead of a constant hazard

**Finding.** `regime.py:764` implements the Adams-MacKay run-length recursion with a **constant
hazard**. A constant hazard encodes a geometric run-length prior, i.e. it asserts that a regime is
as likely to end on its first day as on its hundredth.

**Paper.** 2609.07989 derives the hazard from an explicit duration law inside a hidden semi-Markov
model - the `K = 1` reduction `P(r_t | x_1:t)` - and reports the **log-normal** law dominating
geometric and Pareto consistently across assets, months and criteria, matching "the absence of a
characteristic timescale in order flow". Assessment uses a covering metric (length-weighted Jaccard
of the segmentation), one-step MSE and cumulative loss, not just a label.

**What to compute.** A `hazard_mode` parameter on `bocpd`: `constant` (today's behaviour, the
default) or a duration-law-compiled hazard from `{lognormal, pareto, geometric}`, with the duration
parameters estimated from run lengths observed so far. Report the covering metric beside
`zero_run_prob` so a change in hazard can be judged.

**Inputs.** The same series `bocpd` already takes.

**PIT.** The duration law is estimated from run lengths up to `t`; expanding-window only.

**Cost.** Same recursion, `O(t)`; the duration compile is a `O(#runs)` pass.

**Owner.** `strategies/regime.py:764`.

**Caveat.** The paper's evidence is **high-frequency NASDAQ order flow**, and it provides no
daily-frequency validation - so this is a hypothesis for a daily series, not a demonstrated gain.
Its multivariate extension was *beaten* by independent univariate filters, which is a warning
against pooling.

### R2 - Heavy-tailed emissions, and a VaR that is coverage-tested

**Finding.** `hmm_filtered_regime` (`:367`) is Gaussian. Equity returns are not, and a Gaussian
emission understates exactly the tail states a regime model exists to find.

**Paper.** 2606.23492 keeps one shared forward-backward kernel and swaps only the per-state M-step
across four emission families (Gaussian, Student-t, Laplace, GED), then builds a
**regime-conditional VaR** from the running state posterior times each state's CDF - and backtests
it with Kupiec and **Christoffersen joint conditional-coverage** tests, which is the part that makes
it a measurement rather than a claim.

**What to compute.** An `emission` parameter on the HMM (`gaussian` default, plus `student_t`,
`laplace`, `ged`), `K` selectable (the paper selects `K* = 3` by held-out log-likelihood/BIC), and a
`regime_conditional_var(posteriors, emissions, q)` whose output is checked by a coverage test rather
than asserted. The coverage test is the deliverable; a VaR without one is a number.

**Inputs.** Daily excess growth rate per symbol - already available.

**PIT.** Walk-forward, expanding window, as `hmm_filtered_regime` already is.

**Cost.** Same EM; Student-t adds an ECM step. Seconds per symbol.

**Owner.** `strategies/regime.py:367`, with the VaR consumer in `strategies/book_risk.py`.

**Caveat.** A static transition matrix drifts - the paper's out-of-sample 2025 ACF is
under-estimated - and `K`-selection by held-out likelihood is an in-sample choice. The
rank-non-binding result is a cross-ticker median, not universal.

### R3 - Declare a regime change only against a null band

**Finding.** The engine reads cross-sectional concentration (correlation structure, breadth) and
treats movement as change. But a spectrum estimated from a finite window moves on its own: shrink an
estimator and its leading eigenspace wanders.

**Paper.** 2607.06373 derives a first-order null law for movement in a shrinkage covariance
estimator's leading eigenspace (projector distance) and for scalar spectral functionals (absorption
ratio, leading-eigenvalue share), so that structural change is declared only when the move exceeds
what estimation noise produces - using a debiased estimator under shrinkage.

**What to compute.** `eigen_projector_distance(prev_window, curr_window)` and the scalar functionals,
each reported **with** the calibrated null band and a flag for whether the move exceeds it. Feed the
flag, not the raw functional, to `regime_score`.

**Inputs.** Rolling return windows over the tracked cross-section. Needs the cross-section, so it is
a per-panel read, not per-symbol.

**PIT.** Both windows end at `t`; the null band depends only on window length and shrinkage
intensity.

**Cost.** One eigendecomposition per rolling window, `O(N^3)` naive for the leading subspace - fine
at `N` in the tens, and the engine already computes correlation matrices.

**Owner.** `strategies/regime.py` or `strategies/covariance_models.py`, consumed by
`regime_score`.

**Caveat.** The paper's own framing is that non-rejections partly reflect wide null bands; a wide
band means "not detectable", never "no change".

### R4 - A cheap proposer validated by a statistical test

**Finding.** The engine already has a cheap escalation pattern - `theme_triggers` widens candidate
themes at near-zero cost, and the expensive path only runs on the survivors. There is no equivalent
for *dates*.

**Paper.** 2605.30363 proposes central-bank/policy-text candidates with an LLM, then validates each
candidate date with a **likelihood-ratio VAR test** on a price/macro panel, and symmetrically
accepts data-detector candidates only after an LLM text check. Reported `F1 = 0.82`, `F2 = 0.86`
against a 26-event anchor list on US Treasuries 2010-2024.

**What to compute.** A `regime_shift_candidates(text_corpus)` proposer (cheap, LLM, dates only) and
a `validate_shift(date, panel)` LR-VAR test (the authority). The date set that enters the score is
the *validated* set; proposals that fail validation are recorded, not silently dropped.

**Inputs.** Policy/news text the engine already gathers, plus a returns/macro panel.

**PIT.** Text is dated at publication; validation uses only data before the candidate date plus a
fixed post-window.

**Cost.** One LLM call per corpus window plus a VAR fit per candidate - this is an offline or
weekly process, not a per-run one.

**Owner.** New module beside `strategies/theme_triggers.py` (whose escalation shape it copies) and
`strategies/regime_performance.py`.

**Caveat.** Tuned to a monetary/Treasury setting with a hand-built anchor list, and the text channel
needs a curated policy corpus the engine does not currently hold.

### R5 - A forward stress probability from the cross-section

**Finding.** The engine's regime reads are mostly single-series (vol percentile, trend, choppiness)
plus breadth. It has no calibrated forward probability of a stressed *market* state.

**Paper.** 2602.07066 aggregates monthly cross-sectional fragility signals - return dispersion,
downside extremes, higher moments - over the tracked universe into a calibrated one-month-ahead
probability of entering a high-stress regime.

**What to compute.** `forward_stress_probability(panel) -> {p_stress, horizon, calibration}` - a
calibrated probability, with `unavailable` when the cross-section is too thin. The calibration
report is part of the output, because an uncalibrated probability is a score wearing a probability's
name.

**Inputs.** The panel the run already fetches (breadth already consumes one). Monthly frequency.

**PIT.** Cross-sectional aggregates at `t` predicting `t+1`.

**Cost.** Cheap once the panel exists; the cost is the panel, which breadth already pays.

**Owner.** `strategies/market_breadth.py` is the nearest existing home; the calibration belongs with
`strategies/calibration.py`.

**Caveat.** Cross-sectional fragility signals are correlated with each other and with the outcome
being predicted; the paper's calibration is the claim, and it needs re-fitting on this engine's
panel before any threshold is trusted.

### R6 - The gate every early-warning indicator must pass

**Finding.** This is a discipline item, not a detector, and it is the most transferable result in
the theme. A plausible, well-constructed early-warning signal was **stopped** by the authors' own
placebo test.

**Papers.** 2607.27070's protocol: for each state variable, build a causal detrended residual (a
trailing moving average), compute rolling variance and lag-1 autocorrelation over a shorter window,
test the pre-event trend with a **Kendall tau** ending at the event onset, and **sweep 39
detrend/window configurations** - then require significance against a **placebo null built from
comparable non-event onsets**. 2605.17117 supplies the other half: report a **false-alarm rate per
year**, and note that an offline separability ranking must be re-measured on a frozen holdout.

**What to compute.** A `early_warning_gate` that refuses to register any early-warning indicator
into `regime_score` unless it (a) survives the configuration sweep, (b) beats a matched placebo
onset null, and (c) reports a false-alarm rate. Availability is per-indicator and explicit.

**Inputs.** A labelled event panel. The engine has crises in its ~50 report trees but **no labelled
onset panel** - building one is the prerequisite, and the honest answer until then is
`unavailable`.

**PIT.** The sweep and null must use onsets outside the evaluated event.

**Cost.** Offline; hours, not per-run.

**Owner.** New module, and the findings ledger.

**Caveat.** 2607.27070's own `n = 7` and its placebos share regime; the *protocol* is the
contribution.

### R7 - A coincident stress read, labelled coincident

**Finding.** The engine has concentration and drawdown reads but nothing that tells the risk debate
*where* in the cross-section a stress is centred.

**Paper.** 2608.10788's Triadic Stress Index `TSI = (C*D/M)*Coex` over the correlation network -
`C` normalized `Tr(A^3)` (weighted clustering), `D` density, `M` the inverse spectral gap of the
graph Laplacian, `Coex` degree variance - plus a **per-node attribution `diag(A^3)`** that names the
epicentre. It marginally beats the Absorption Ratio and produces cleaner alarms (4.0% unexplained
vs 14.7%).

**What to compute.** `triadic_stress(returns_by_name) -> {tsi, epicentre[]}` with an explicit
`coincident: true` marker, and `unavailable` below roughly eight names (the paper notes it saturates
on small networks).

**Inputs.** A correlation network over the tracked cross-section - `statistical.correlation_matrix`
already produces the input.

**PIT.** Rolling window ending at `t`.

**Cost.** `Tr(A^3)` is `O(N^3)` or `O(N^2 * edges)`; trivial at this engine's book size.

**Owner.** New module; consumer is the risk debate and `risk_score`.

**Caveat.** Coincident, not leading; only marginally exceeds the Absorption Ratio; needs a
cross-section and saturates when it is small.

### R8 - Do not promise regime-arrival risk

**Finding, recorded as a limitation.** 2606.02657's decomposition is exact and its ex-post penalty
is real, but its training-only estimator has `rho = 0.084` with a CI containing zero. **Regime
arrival is not estimable from training data.**

**Consequence here.** Any output that reads "approaching shift risk" must either be based on a
walk-forward-tested detector or be labelled coincident. This doc treats it as a constraint on
`regime_score`'s wording and on any report prose that cites a regime read.

**Caveat.** The model is a two-state Markov chain, and the engine has no calm/crisis label axis
today; the constraint is about honest labelling, not about adopting the estimator.

### R9 - Regime as a soft gate, not an input (deferred)

**Finding.** 2608.12251 routes regime variables through a **gate** on residual expert corrections
rather than appending them to the feature vector - and reports that appending them *degrades* both
accuracy and stability (IC 0.5469 gated vs 0.5378 appended). 2605.11423 supplies the mirror-image
warning from the other direction: a three-condition day classifier that identifies a real 4.4% of
sessions with a `+25.6bp` next-day spread, and whose eight directional rules **all failed**.

**Action here.** No build. Recorded because it constrains future work: regime information should
condition *how much to trust* another read, not be concatenated onto it, and a classifier that
identifies interesting days is not thereby a signal.

---

## 4. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| R1 | duration-law hazard for BOCPD | `strategies/regime.py:764` | no |
| R2 | heavy-tail emissions + coverage-tested regime VaR | `strategies/regime.py:367` | no |
| R3 | calibrated null band for spectral movement | `strategies/regime.py`, `covariance_models.py` | no |
| R4 | text-proposed, statistically-validated shift dates | new, beside `theme_triggers.py` | yes |
| R5 | calibrated forward stress probability | `strategies/market_breadth.py` | no |
| R6 | the early-warning admission gate | new | yes |
| R7 | coincident stress index + epicentre attribution | new | yes |
| R8 | labelling constraint, no producer | - | - |
| R9 | architectural constraint, deferred | - | - |

## 5. Honest limits

1. **Two of the three most load-bearing results in this theme are negative or self-limiting.** That
   is why they are quoted first. The theme's contribution is discipline, and a reader who takes only
   the detectors has taken the weaker half.
2. **The two concrete extensions (R1, R2) are validated on data this engine does not hold** - NASDAQ
   order flow and SPY daily returns respectively. Both are hypotheses here until re-measured on this
   engine's panel.
3. **R6 needs a labelled event-onset panel that does not exist.** Until one is built, the gate's
   honest output for every candidate indicator is `unavailable`.
4. **R5 and R3 need a cross-section on every run**, which is a real cost against a ~40-minute
   four-symbol budget. Both are candidates for a weekly offline pass rather than a per-run producer.
5. **Nothing here changes the composite by adjacency.** R1, R2, R3 and R5 feed `regime_score`'s
   existing components; they do not add a new engine to `COMPOSITE_ENGINES`.

## 6. Recommended build order

1. **R1** - smallest change in the doc, same recursion, and it removes an assertion (constant hazard
   = geometric durations) the engine never made deliberately.
2. **R2** - the coverage-tested VaR is the deliverable; the emissions are the mechanism.
3. **R3** - cheap, and it stops the engine calling estimator noise a regime change.
4. **R6** - the admission gate, which needs the onset panel built first.
5. **R7**, **R5**, **R4** - in that order.

**Decision requested:** whether R1 + R2 land as a first pass, and whether to fund the labelled
onset panel that R6 depends on.
