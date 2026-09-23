# Paper-Survey Adoption - Implementation Plan

Status: **PLAN - not started.** Implements the six design docs derived from
[`docs/design_fin_paper_survey_26.md`](design_fin_paper_survey_26.md) (v1.0 SURVEY, 309
papers read, 31 high / 111 medium / 124 low / 43 none). Each phase names target files and
symbols, the exact behaviour, the config gate, the tests that must be **proven failing
first**, and the acceptance criteria.

Nothing here changes an existing computation: every item is additive, default-off, and
degrades to `unavailable` when its inputs are missing, per
[`implementation_plan_quant_formula_additions.md`](implementation_plan_quant_formula_additions.md)
section 0.

**Parents.** `docs/design_fin_paper_survey_26.md` is the index. Six themed design docs own
the item detail, and this plan does not restate it:

| Theme | Design doc | Items |
|---|---|---|
| Honest evaluation | `docs/design_research_honesty_gates.md` | H1-H11 |
| Regime and state | `docs/design_regime_estimation_hardening.md` | R1-R9 |
| Risk and tails | `docs/design_risk_tail_and_coverage.md` | K1-K6 |
| Volatility and options | `docs/design_vol_surface_and_vrp.md` | V1-V8 |
| Cross-section and allocation | `docs/design_cross_section_and_allocation.md` | X1-X8 |
| Text, news, disclosure | `docs/design_news_and_filing_signals.md` | N1-N7 |

**Rule-4 impact: none at the time of writing.** Nothing in this plan adds a tool, a CLI
flag, a gate the app reads, or a JSON shape change. Any phase that later does must state
its web impact in its own CHANGELOG entry (CHANGELOG preamble; registry
`trading_web/docs/web_TOPICS.md`).

**Anchor check.** Every `file.py:LINE` reference this plan reuses from the six docs was
re-verified against the tree before this file was written: **44 of 44 anchors held**
(`deflated_sharpe:103`, `bocpd:764`, `hmm_filtered_regime:367`, `_IGARCH_AB:40`,
`garch11_fit:425`, `rolling_band:143`, `rank_ic:64`, `amihud_illiquidity:71`,
`kyle_lambda:262`, `lm_tone:121`, `_bucket_day:397`, `residualize_returns:201`,
`news_novelty:215`, `granger_causality:273`, `iv_skew:25`, `fed_imminence:142`,
`resolve_peer_universe:174`, `gap_type:220`, and 26 more). Line numbers move; re-grep
before acting on any of them.

---

## 0. Ground rules (inherited, non-negotiable)

1. **Measurement before adoption.** Phase P0 is the instrument, not a signal. The survey's
   own thesis is that this corpus hands the engine "an audit standard, a set of
   coverage-aware estimators, and a repeated reminder that the volatility-and-structure
   channels are forecastable while the return channel mostly is not". A phase that adds a
   score before P0 lands is adopting an untested claim.
2. **One producer per derived quantity.** No item may become a second authority beside an
   existing one. Three items are explicitly constrained by their own docs and are the
   ones most likely to violate this: **K4** (must not sit beside `ledoit_wolf_shrink`),
   **X5** (must *replace* `resolve_peer_universe`'s label resolver, not add to it), and
   **H10** (a *reader* of the loaded frame, not a second data-quality authority).
3. **Nothing enters the composite by adjacency.** `COMPOSITE_ENGINES` stays
   `(fundamental, technical, regime, risk)`. No item in the six docs proposes a member
   change; several propose inputs to an existing member's components. That distinction is
   the difference between a signal and a state read, and the phases below keep it.
4. **Coverage travels with the number.** Missing data is `unavailable`, never zero. Every
   item that can be computed over a padded or thin window must report the window (H10 is
   the mechanism) or refuse.
5. **Gates must be able to fail.** Each new test is proven failing under a targeted
   mutation of the code it guards. Tests assert observable behaviour, never wiring or
   source text.
6. **Six registration points per gate**: `DEFAULT_CONFIG`, an `_ENV_OVERRIDES` row, a
   `docs/gate_registry.md` row with an enforcement site, a `tests/test_gate_env_toggles.py`
   `REGISTRY` entry, `.env.example`, and a `docs/api_reference.md` section 1.1 row
   (regenerate with `scripts/gen_api_reference_table.py --write`). Registering a gate also
   moves the coverage sentence in `docs/gate_registry.md` ("41 of the 89").
7. **A new public function in `strategies/` or `dataflows/` ships with its first caller in
   the same commit**, or `tests/test_calc_agent_wiring.py::test_public_calc_reachable_or_whitelisted`
   fails. Underscore-prefixed names are exempt; tests do not count.
8. **Offline artefacts are not in-run producers.** Items marked OFFLINE below may not be
   called from `prepare_initial_state`, `finalize_run`, or any agent tool.

---

## 1. What this plan is, and what it is not

**It is** a sequenced, gated path from the survey to production, with the cost and the
prerequisites of each item stated as measured facts rather than as estimates from the
papers.

**It is not** a claim that any of these items will improve returns. The single most
load-bearing finding in the corpus is a negative one: of six candidate retail signal
families audited under a three-gate protocol, **four were REFUTED and two INCONCLUSIVE -
**none SUPPORTED** (2607.20093). The corpus's contribution here is discipline and
coverage-aware estimation, and each of the six themed docs reaches that conclusion
independently, from a different starting surface.

**Three of the six docs' own headline results are null or self-refuting**, and the plan
carries them as constraints rather than as builds:

- **R8** - regime *arrival* is not estimable from training data (`rho = 0.084`, CI
  contains zero). Consequence: no output may read "approaching shift risk" unless a
  walk-forward-tested detector backs it or it is labelled coincident.
- **R9** - appending regime variables to a feature vector *degrades* both accuracy and
  stability (IC 0.5469 gated vs 0.5378 appended). Consequence: regime conditions *how much
  to trust* another read; it is not concatenated onto one. This is a standing constraint on
  every later phase.
- **V7, V8** - a Sharpe of 4.31-5.76 from one index-year, and a surface forecast that is
  rarely significant, are declined. Declining them is the design working, not an omission.

---

## 2. The dependency surface, measured (2026-09-23)

Cost estimates in the six docs assume a numerical stack. Measured against the interpreter
that actually runs this engine (`py -3.12`, Python 3.12.10):

| Package | Installed | Declared in manifest | Directly imported by the engine |
|---|---|---|---|
| numpy | 2.2.6 | **was not** - fixed this session | yes (5 modules) |
| scipy | 1.15.3 | **was not** - fixed this session | yes (2 modules) |
| pandas | 3.0.5 | yes | yes |
| networkx | 3.5 | no | no |
| numba | 0.61.2 | no | no |
| matplotlib | 3.10.3 | no | no |
| torch | 2.7.1+cpu | no | no |
| **sklearn** | **absent** | no | no |
| statsmodels, arch, hmmlearn, ruptures | absent | no | no |

### 2.1 One defect, already fixed (this commit)

`tradingagents/strategies/statistical.py:18` does `from scipy import stats` and
`:19` `from scipy.special import betainc`; `sentiment_research.py:27` does the same. That
module is reached at runtime from **12 sites in `agents/utils/analysis_tools.py`** and from
`strategies/lottery.py:74` - i.e. from the analyst tool surface, not from dead code.

**Neither numpy nor scipy was declared.** A clean `pip install` of the declared manifest
resolves **no scipy at all**: every scipy edge from a declared dependency is
extras-gated - `pandas -> scipy>=1.14.1; extra == "computation"`,
`yfinance -> scipy>=1.6.3; extra == "repair"` - and the only packages that require scipy
unconditionally in this environment (`PyMatting`, `albumentations`, `colour-science`,
`rembg`, `scikit-image`) are image/vision packages the engine does not depend on. numpy
does arrive transitively (`pandas`, `stockstats`), but it is still imported directly and
undeclared.

Fixed in this commit: `numpy>=1.26.0` and `scipy>=1.11.2` added to `pyproject.toml`
`[project].dependencies` and to `requirements.txt` (which mirrors it). The floors are
conservative on purpose - the API surface in use is `np.array`/`np.linalg`/`np.asarray`
and `scipy.stats`/`scipy.special.betainc`/`scipy.optimize`, all long-stable, and no
numpy-2-only API is used.

**This is why the plan's Phase 0 needs no new dependency**: the honesty instruments are
numpy + scipy work.

### 2.2 sklearn is absent, and three items need it (or a hand-rolled equivalent)

| Item | Needs | Consequence |
|---|---|---|
| **X2** double-selection LASSO over components | an L1 solver | scipy has no LASSO. Either add sklearn, or implement LARS/coordinate descent in-house (the selection half is ~80 lines and the doc only needs a survivor list). |
| **X5** valuation-anchored peer weights | a gradient-boosted tree | leaf co-occurrence needs a fitted tree. `sklearn.ensemble.GradientBoostingRegressor` is the small option. |
| **K4** covariance from characteristics | a trained encoder | the doc already defers this pending a training pipeline. Unchanged. |
| **V1** vol forecast pool | three ML forecasters | the doc's own architecture; scikit-learn or the engine's existing regressions. |

**Decision requested** (see section 8): add `scikit-learn` as a declared dependency, or
scope X2 to a hand-rolled L1 selection.

### 2.3 torch is installed but undeclared - and it changes two items' cost

The news doc's honest-limits section 4 says N1 and N6 "would need torch or a hosted
encoder, which changes the engine's dependency profile - a decision the owner should make
explicitly". **torch 2.7.1+cpu is already installed** in this interpreter (pulled in by
`google-genai`/`transformers`-side packages, none of which the engine declares), and the
engine imports it nowhere. So:

- **N1's story clustering and N6's relevance comparison can run locally on torch** without
  a hosted endpoint - but only if torch is *declared*, which makes the dependency profile
  change explicit rather than accidental. It is currently an undeclared heavyweight that
  happens to be present.
- The doc's fallback (1-2 batched LLM tag calls per symbol-day, embeddings from an existing
  provider) remains available and is the lower-commitment option.

**Decision requested** (section 8).

### 2.4 tsbootstrap exists and matches the H11 claim

2607.06690's library is real and public: block, residual, sieve and wild bootstrap plus
adaptive conformal calibrators (EnbPI, ACI, NexCP, AgACI) behind one typed API. H11 does
**not** require it - a moving-block bootstrap for a claim statistic is ~30 lines over
numpy, and the block length already has a stated rule (lag-1 autocorrelation plus ADF).
Adopting the library buys the conformal calibrators, which are the part H11 wants for the
paired band. **Decision requested**: in-house block bootstrap (no new dependency) versus
the library.

### 2.5 Nothing else in the corpus needs a new package

GPH log-periodogram and local Whittle (V2), Marchenko-Pastur bounds (X3, V5), projector
distance and absorption ratio (R3), `Tr(A^3)` (R7), NNLS (H9), Kupiec/Christoffersen
coverage tests (R2), an fBm drawdown table (K2), and the realized-measure proxies (V6) are
all numpy/scipy work at this engine's scale.

---

## 3. Phase map

Sizes: S = under a day, M = one to three days, L = a week or more. OFFLINE items may not
be called in-run (ground rule 8).

| Phase | Leads with | Lands in | Gate | Size | Run mode | Depends on |
|---|---|---|---|---|---|---|
| **P0** | H10, H1, H7, H11, H4, H6 | `strategies/coverage_window.py` (new), `evaluate.py`, `rule_eval.py`, `conformal.py`, `alpha_eval.py`, `calibration.py`, `agents/utils/report_verifier.py` | `enable_coverage_window`, `enable_trial_ledger`, `enable_refusal_ledger`, `enable_bootstrap_intervals`, `enable_accuracy_ceiling`, `enable_materiality_verdict` | S-S | in-run | - |
| **P1** | X3, X6, V6, V2, R1, K2, K3, X8, V4, R7, R3 | `market_breadth.py`, `signal_analysis.py`, `volatility_models.py`, `long_memory.py` (new), `regime.py`, `book_risk.py`, `options_surface.py`, `technical_factors.py`, `catalyst.py` | `enable_mp_lower_spectrum`, `enable_long_memory`, `enable_drawdown_envelope`, `enable_rn_skew_proxy`, `enable_trend_spectral`, `enable_event_iv_lift`, `enable_triadic_stress`, `enable_spectral_null_band`; R1 extends `enable_bocpd` | S | in-run | P0's H10 for the panel items |
| **P2** | K1, R2, N3, K5, H2 | `book_risk.py`, `regime.py`, `strategies/aggregators.py` (new), `size.py`, `factor_expressions.py`, `factor_schema.py` | `enable_tail_risk_layer`, `enable_hmm_heavy_tails`, `enable_learned_aggregator`, `enable_boundary_sizing`, `enable_factor_availability_gate` | M | in-run | P0 (H11 intervals for the coverage test), P1 |
| **P3** | H5, H8, H9, N1, N2, N5, N7, R4, R5, X2, X5, X7, V3, V5, N4, N6 | `rule_eval.py`, `data_quality.py`, `dataflows/`, `peer_universe.py`, `text_factors.py`, `news_relevance.py`, `regime.py`, `market_breadth.py`, new modules | `enable_rule_policy_gates`, `enable_vintage_guard`, `enable_report_attribution`, `enable_news_event_tags`, `enable_filing_sentiment`, `enable_prompt_condition_harness`, `enable_leadlag_plausibility`, `enable_regime_shift_proposer`, `enable_forward_stress_probability`, `enable_peer_edge_classifier`, `enable_rnd_recovery`, `enable_eigen_rotation`, `enable_multidim_sentiment`, `enable_embedding_relevance` | M-L | mixed | P0 + P1 |
| **P4** | H3, X1, X4, R6, V1, K4 | offline harnesses and scripts | none (scripts, not gates) | L | **OFFLINE** | H1's ledger; for R6, the onset panel |

Landing rule: **one item per commit**, each with its own CHANGELOG entry and its own
failing-first proof. A phase is complete when every item in it is either landed or
explicitly deferred in writing.

---

## 4. Phase detail

### P0 - the measurement instruments

P0 leads because the survey's largest transferable theme is honest evaluation, because
these six items are the cheapest in the whole plan, and because they decide whether the
later items deserve to land at all. Each is independently landable.

#### P0-1 - Coverage window and survivor labelling (H10)

**Target.** `strategies/coverage_window.py` (new):
`coverage_window(series) -> {"first_valid", "last_valid", "n_bars", "padded_days", "alignment"}`.
Reader, not producer: it reads the already-loaded frame. `strategies/data_quality.py`
consumes it; `scripts/coverage_scorecard.py` reports it per symbol.

**Behaviour.** `padded_days` counts positions before the first valid observation in a
calendar-aligned panel. A panel statistic computed over a padded window is reported
`unavailable`, not computed - this is the rule the corpus's temporal-coverage-bias result
motivates. Separately, any backtest over a current-constituent universe is labelled
`survivor_only` in the findings record.

**Gate.** `enable_coverage_window`, default off.

**Failing-first test.** Remove the `padded_days > 0` refusal branch and a test with a
deliberately padded frame must fail by name.

**Acceptance.** On a frame with 40 leading NaNs, `padded_days == 40` and the dependent
statistic is `unavailable`; on a dense frame the statistic is unchanged to the byte
(the section 9.3 guarantee `tests/test_cli_propagate_parity.py` already pins elsewhere).

**Note.** The repo is already half-instrumented for this: `market_data_validator._INDICATOR_MIN_BARS`
(`:34`) guards each indicator and `volatility_models._IGARCH_AB = 0.999` (`:40`) is
*exactly* the GARCH-breakdown threshold the paper reports. H10 adds the window, not the
threshold.

#### P0-2 - Trial ledger and dispersion-aware deflation (H1)

**Target.** `strategies/trial_ledger.py` (new): `record(candidate_id, window, returns_sha, sharpe, as_of)`.
`strategies/evaluate.py:103`: extend `deflated_sharpe` with an optional
`sharpe_dispersion` argument and the standard selection threshold

```text
SR*_0 = sqrt(V) * [ (1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e)) ]   g = Euler-Mascheroni
```

**Behaviour.** `N` comes from the ledger, `V` from the ledger's Sharpe distribution, never
from a caller's assertion. Every deflated number the score panel or coverage scorecard
publishes carries its `N` beside it. `alpha_zoo.bench_zoo` (which today supplies a
caller-supplied count) switches to the ledger.

**Cost.** Deflation is microseconds. The ledger's footprint is `N` candidate return
series. CSCV uses `S = 8`, not `S = 16` (12,870 recombinations).

**Failing-first test.** Two candidate sets with the same `N` but different Sharpe
dispersion must produce different deflated values; a mutation that ignores
`sharpe_dispersion` must fail the test by name.

**Acceptance.** With dispersion supplied, the deflated Sharpe matches the closed form; with
it absent, today's behaviour is preserved bit-for-bit and the result carries
`dispersion: "assumed"`.

#### P0-3 - Refusal ledger and save-to-miss ratio (H7)

**Target.** `strategies/refusal_ledger.py` (new), beside `strategies/prediction_ledger.py`
(whose `score_outcome` shape is the template). One row per refused candidate: symbol,
as-of, gate, reason, input snapshot hash. A forward sampler classifies each refusal against
subsequent price paths into the paper's five tiers.

**Behaviour.** The engine currently records decisions **taken**; this records candidates
**refused**, so a guardrail's precision becomes measurable. Tie-break rule from the paper:
**missed beats saved**.

**Acceptance.** The gate sources are the engine's own refusals (risk governor, knife
guard, tradability, news admission, value-dip floors). The per-gate save-to-miss ratio is
reported **with its event count**; the paper's own headline tier was refuted by its matched
lifecycle test, so the ratio is reported as a taxonomy plus discipline, never as a
constant. A mutation that drops the "missed beats saved" tie-break fails by name.

#### P0-4 - Intervals that respect autocorrelation (H11)

**Target.** `strategies/conformal.py:143` (`rolling_band`) gains the information-gap axis
beside its coverage; a block-bootstrap interval is added for every claim statistic the
score panel (`scripts/score_panel.py`) and coverage scorecard
(`scripts/coverage_scorecard.py`) publish. Block length chosen from lag-1 autocorrelation
plus an ADF check.

**Behaviour.** A pooled band can be wide and still uninformative; the second axis is the
log-score of the pooled band against a conditional-scale alternative on the same
calibration window. Reported per band; `unavailable` below the `min_n` floor.

**Acceptance.** On a synthetic AR(1) series the IID interval under-covers and the block
interval does not; the information-gap value is reported for a wide-but-uninformative band
and differs from a narrow informative one.

**Decision.** In-house moving-block bootstrap versus the public `tsbootstrap` library
(section 2.4).

#### P0-5 - R-squared ceiling and excess accuracy (H4)

**Target.** `strategies/alpha_eval.py` and `strategies/calibration.py`:
`ceiling_ratio(returns, forecasts) -> (kappa_hat, (2DA-1)^2, R2_OOS/kappa)` and
`excess_accuracy(pred, realized, baseline="always_up")`. The GARCH leg comes from
`strategies/volatility_models.py:425` (`garch11_fit`), which exists and is wired to no
evaluation path today.

**Behaviour.** `sigma_hat` is an **out-of-sample** GARCH(1,1) fit. A `((2DA-1)^2,
R2_OOS/kappa)` point above the 45-degree line is flagged. `excess_accuracy` is reported with
walk-forward folds and block-bootstrap intervals from P0-4.

**Read it as a falsifier, never a validator**: the ceiling is an inequality derived from a
constructed oracle and cannot reject a forecast.

**Acceptance.** A constructed forecast with positive `(2DA-1)^2` and negative OOS `R^2`
is flagged; a mutation that drops the out-of-sample requirement on `sigma_hat` fails by
name.

#### P0-6 - Three-way verdict and family FDR (H6)

**Target.** `strategies/evaluate.py`: `materiality_verdict(stat, ci_low, ci_high, delta)`
plus a family-level FDR over a batch of candidate signals, and an exposure-time-matched
benchmark arm in `benchmark_table` (which today compares on a common window without
matching time in market). `agents/utils/report_verifier.py`: the verdict vocabulary becomes
SUPPORTED / REFUTED / **INCONCLUSIVE**.

```text
REFUTED      iff U_S < delta_S  or  U_R < delta_R  or survival fails
SUPPORTED    iff L_S > delta_S  and L_R > delta_R  and survives
INCONCLUSIVE iff the interval straddles the threshold   (underpowered, NOT null)
```

**Behaviour.** Thresholds are pre-declared in config, not chosen after the fact. A
non-significant result is recorded as unresolved rather than as evidence of no edge - which
is the vocabulary change that makes every later phase's findings honest.

**Acceptance.** An interval straddling `delta` yields INCONCLUSIVE, not REFUTED; a mutation
that collapses INCONCLUSIVE into REFUTED fails by name.

---

### P1 - zero-new-data state reads

Every item here computes from data the run already fetches. No new vendor, no new
dependency, all default-off, none in `COMPOSITE_ENGINES`.

| Item | Target | Behaviour in one line | Gate |
|---|---|---|---|
| **X3** | `market_breadth.py` / `sector_breadth.py` | `mp_below_count(corr, n, w)` counts eigenvalues below the Marchenko-Pastur lower bound `(1-sqrt(n/w))^2`; `unavailable` when `w <= n`. Runs on the 11 SPDR sector ETFs `sector_rank` already tracks. **Coincident and direction-blind** - report as state, never as signal. | `enable_mp_lower_spectrum` |
| **X6** | `signal_analysis.py` over `liquidity_risk.py` | A **study**, not an estimator: `rank_ic(kyle_lambda_month_t, fwd_return_t+1)` using `signal_analysis.rank_ic:64`, which already does this. No new estimator exists or is added. | none (OFFLINE script) |
| **V6** | `volatility_models.py` | Daily-bar analogues of bipower variation and realized quarticity, so a jump is distinguishable from a diffusion without tick data. Named as **proxies**, not realized measures. | `enable_jump_robust_proxies` |
| **V2** | `long_memory.py` (new) | `memory_parameter(returns) -> {gph_d, whittle_d, se}` by GPH log-periodogram regression and local Whittle on rolling 750-day windows, plus a HAR/HAR-X `rv_forecast`. `d` is reported **beside** the forecast, because a forecast from `d = 0` and one from `d = 0.44` are different objects. | `enable_long_memory` |
| **R1** | `regime.py:764` | A `hazard_mode` parameter on `bocpd`: `constant` (today's behaviour, the default) or a duration-law-compiled hazard from `{lognormal, pareto, geometric}` estimated from run lengths so far (expanding window). Report the covering metric beside `zero_run_prob`. High-frequency order flow evidence only - a hypothesis at daily frequency. | extends `enable_bocpd` |
| **R3** | `regime.py`, `covariance_models.py` | `eigen_projector_distance(prev_window, curr_window)` plus scalar spectral functionals, each **with** a calibrated first-order null band; the **flag**, not the raw functional, feeds `regime_score`. | `enable_spectral_null_band` |
| **R7** | new, consumer `risk_score` | `triadic_stress(returns_by_name) -> {tsi, epicentre[]}` with an explicit `coincident: true` marker; `unavailable` below eight names. | `enable_triadic_stress` |
| **K2** | `book_risk.py` | `drawdown_envelope(sharpe, horizon, skew, kurtosis, hurst)` returning median and p90 maximum drawdown, maximum loss, time under water, longest recovery, with the `T^(H-1/2)` dispersion rescaling when a Hurst estimate exists (`mean_reversion.hurst_exponent:112` already computes one). The envelope carries the Sharpe's **estimation uncertainty**. | `enable_drawdown_envelope` |
| **K3** | `options_surface.py` | A cross-strike risk-neutral skewness proxy requiring at least five strikes, `unavailable` below that. Note the paper is explicit this is a cross-strike IV proxy, not the true BKM moment. The actionable half is the *finding that the coefficient is unstable*: any skew/spread read used in scoring is conditioned on the regime cell, not applied as a constant. | `enable_rn_skew_proxy` |
| **X8** | `technical_factors.py`, consumed by swing | `spectral_excess_mass(returns) -> {mass, condition_met}` and `cost_optimal_span(cost_bps, vol) -> int`. Reported **beside** the swing factor, not inside its score: a condition on when trend-following deserves weight, not a direction. | `enable_trend_spectral` |
| **V4** | `options_surface.py`, consuming `catalyst.fed_imminence:142` | `pre_event_iv_lift(chain, event_date)` describing the ATM term-structure shape in **event time** (days to event, not calendar days). Not a surface forecaster - the forecasting half is statistically insignificant by the authors' own tests. | `enable_event_iv_lift` |

**P1 evidence rule.** R1, V2 and V6 are re-measurements on this engine's panel before any
threshold is trusted: R1's evidence is NASDAQ order flow, V2's is a cross-section the engine
does not hold at that depth, and V6 is a proxy battery by construction.

---

### P2 - composite reads over producers that already exist

| Item | Target | Behaviour in one line | Gate |
|---|---|---|---|
| **K1** | new, composing `book_risk` + `data_quality` + `conformal` | `tail_risk(returns, quality) -> {var, cvar, q_score, uncertainty, band, status}` with `status in {ok, widened, unavailable}`. **One-directional**: quality and uncertainty may widen the band or refuse the estimate, never narrow it. Ships with its coverage test, because the paper's VaR still fails Kupiec. | `enable_tail_risk_layer` |
| **R2** | `regime.py:367`, VaR consumer in `book_risk.py` | An `emission` parameter on the HMM (`gaussian` default, plus `student_t`, `laplace`, `ged`) and `regime_conditional_var(posteriors, emissions, q)` whose output is checked by **Kupiec and Christoffersen joint conditional-coverage** tests. The coverage test is the deliverable; a VaR without one is a number. | `enable_hmm_heavy_tails` |
| **N3** | new, consuming `consensus.py` + `prediction_ledger.py` | `learned_aggregator(agent_outputs, agreement_features) -> {label, confidence}` trained on the engine's own decision ledger. The feature vector must include **agreement structure**, not just votes. | `enable_learned_aggregator` |
| **K5** | `size.py` | An optional `boundary_factor(distance_to_limit, horizon, residual)` multiplier on the existing Kelly size, applied only when a hard limit is configured. **Never increases size.** Pure model, no empirical calibration - a shape, not a number. | `enable_boundary_sizing` |
| **H2** | `factor_expressions.py` (the gate), `factor_schema.py` (the record) | The nine-field factor record gains an explicit **availability** declaration; the AST gate rejects any forward shift and any field whose declared availability is later than the decision date. Bound to `data_quality.fundamentals_pit_ok` and `dataflows/pit_registry.read_as_of`. This is the expressibility fix: a leaky oracle survives DSR 1.00 and PBO completely, so the leak must be removed from the action surface rather than corrected afterwards. | `enable_factor_availability_gate` |

**P2 note.** N3 is the only item in the news theme with a *measured* effect in the theme
(balanced accuracy 0.561 to 0.612 against majority vote 0.573), and it is the smallest;
its caveat is that the target is next-day direction at a 53% base rate and the paper
concedes the prompt partition may drive part of the gain.

---

### P3 - new producers, mostly with an offline estimation step

One card per doc, items grouped because they share the same shape: a new module, an
offline estimator, an in-run reader.

**H5, H8, H9 (honesty).**
- `rule_eval.py`: add a `fill_on_next_bar` variant (signal at close, entry next open - the
  convention `backtest_engine.MatchingEngine` already uses elsewhere) and report the
  **triple** side by side: ranking skill, average precision at label prevalence, and
  realized net policy return. Require the entry convention to be **named**. Five gates
  simultaneously, plus **positive controls** so a harness that has gone blind is detected.
  `enable_rule_policy_gates`.
- `data_quality.py` + `dataflows/`: a publication-lag table for scheduled macro releases,
  an as-reported vintage store (or a documented lag substitution), an archived-nowcast
  substitution where one exists, and the **mandatory non-LLM comparator on the identical
  input set** before any LLM signal is credited. `enable_vintage_guard`.
- New module beside `score_disagreement.py`: `attribution(reports, thesis)` by NNLS over
  embeddings, and a novelty screen for a newly admitted factor against the existing zoo
  plus a reference set. `enable_report_attribution`.

**R4, R5 (regime).** `regime_shift_candidates(text_corpus)` (cheap proposer) plus
`validate_shift(date, panel)` (LR-VAR test, the authority); proposals that fail validation
are **recorded, not silently dropped**. `forward_stress_probability(panel)` with its
**calibration report as part of the output**, because an uncalibrated probability is a
score wearing a probability's name. `enable_regime_shift_proposer`,
`enable_forward_stress_probability`.

**X2, X5, X7 (cross-section).** The redundancy screen runs **offline on a schedule** and its
consumption is a decision: a component that never survives becomes a *documented* component
rather than a scored one. `valuation_anchored_peers` **replaces** the label-based resolver.
`peer_edge_classifier` classifies every candidate edge and **drops competitor edges** before
aggregation, with its rejections logged into P0-3's refusal ledger.
`enable_peer_edge_classifier`; X2 is a script; X5 is a replacement decision, not a gate.

**N1, N2, N4, N5, N6, N7 (text).**
- N1: `tag_article`, `cluster_stories` (title+summary embedding cosine, the paper's 0.80),
  and `tag_drift_prior(tag) -> {drift_h6_20, width_term, n_events, lo, hi}` estimated
  offline, carried in **as a prior with its interval and its event count, never as a gate**.
  The **background** drift is negative for every size bucket and must be subtracted, or the
  prior misattributes it to the tag. `enable_news_event_tags`.
- N2: `filing_sentiment(filing, scope)` with a **section parser the engine does not have**,
  `scope="item_1a"` as the firm-level default (the inverse of the naive choice), and
  `vol_score` as a distinct output. Both the dictionary baseline and the supervised score
  are reported side by side for one release cycle. `enable_filing_sentiment`.
- N4: five dimensions elicited per article on the **admitted subset only** (the admission
  filter is a prerequisite, not an optimisation), aggregated by relevance-weighted mean,
  with the **prompt version stored with every score**. `enable_multidim_sentiment`.
- N5: version the prompt as a first-class input, record the condition per run, and score
  per-condition accuracy on the ledger. Adopt the **harness**, not the framing.
  `enable_prompt_condition_harness`.
- N6: an embedding relevance score running **alongside** the lexical one, with disagreements
  logged - a comparison first, never a swap on this evidence. `enable_embedding_relevance`.
- N7: a semantic plausibility stage **in front of** `statistical.granger_causality:273`;
  the statistical test stays the authority and the LLM only removes pairs it cannot justify,
  with rejections logged. `enable_leadlag_plausibility`.

**V3, V5 (volatility).** `rnd_recovery(chain)` fits a two-component lognormal mixture per
expiry under mass and forward constraints and returns decision functionals, with an
**unidentifiability flag derived from the conditioning spectrum of the covered strikes** -
`unavailable` when the strikes cannot span the density. Per-expiry classical fits beat the
learned operator on real quotes, so the learned version is not built.
`eigen_rotation(prev_corr, curr_corr) -> {rec, angles, mp_edge_check}` with the MP-edge
check, because inside that edge the eigenvectors are noise and the rotation is meaningless.
`enable_rnd_recovery`, `enable_eigen_rotation`.

---

### P4 - offline and panel-scale

**H3 - synthetic-null workflow falsification (OFFLINE).** Run each scored strategy
end-to-end against five reference classes (white noise, regime-switching volatility, bid-ask
bounce, a zero-alpha factor, GARCH(1,1)) and require the walk-forward winner to stay inside
that environment's null band before any factor is credited. `5 x 1000` pipeline replays:
prohibitive in-run by construction, and fine offline. Stage 2's `Delta_Z` and `K_eff` come
from the retained candidate matrix that **P0-2's ledger is what makes possible**. Carry the
paper's headline warning into the output: familywise false-positive probability is 5.3% at
`K = 1` and **92.3% at `K = 50`**.

**X1, X4 - rank transition and horizon memory (OFFLINE).** Both need a full cross-section
every run against a ~40-minute four-symbol budget, and both are weekly-offline jobs. X1's
volatility chain is the default; the **return** chain is available only with the
`unforecastable` flag attached, because reporting it without the flag invites exactly the
misuse the paper documents.

**R6 - the early-warning admission gate (OFFLINE, BLOCKED).** The gate refuses to register
any early-warning indicator into `regime_score` unless it survives a 39-configuration
detrend/window sweep, beats a **matched placebo onset null**, and reports a false-alarm
rate. **It needs a labelled event-onset panel that does not exist.** Until one is built,
the gate's honest output for every candidate indicator is `unavailable`. Building that panel
is itself a deliverable, and it is a prerequisite, not a side task.

**V1 - the volatility forecast pool (OFFLINE-ish).** The largest single architecture in the
theme: a pool of forecasters scored online by a risk-sensitive loss, exponentially weighted
by recency **and regime similarity**, with a shrunk quantile threshold routing into
pre-specified calm/stress pools. It needs a state vector (`log VIX`, `log(VIX/VXV)`, 20-day
realized vol, vol-of-vol, term spread, HY spread) that the engine only partly fetches.
**Blocked on the vendor decision** in section 8; until then the pool routes on a smaller
state and the routing gain is unmeasured. Keep the underprediction penalty as a *separate*
reported loss beside QLIKE so the conservatism is visible.

**K4 - covariance from characteristics (OFFLINE, deferred).** The characteristics path is
tractable at inference but the encoder is offline training this engine has no stack for.
The doc's constraint is binding: if adopted it must **replace** the existing estimator on
the ragged path, not sit beside `ledoit_wolf_shrink`.

---

## 5. Item index

| ID | Deliverable | Owner | Phase | Run mode |
|---|---|---|---|---|
| H1 | trial ledger + dispersion-aware deflation | `evaluate.py` + new ledger | P0 | in-run |
| H2 | availability-typed factor DSL gate | `factor_expressions.py`, `factor_schema.py` | P2 | in-run |
| H3 | synthetic-null workflow falsification | new harness | P4 | offline |
| H4 | R-squared ceiling + excess accuracy | `alpha_eval.py`, `calibration.py` | P0 | in-run |
| H5 | five-gate verdict + positive controls + next-open variant | `rule_eval.py` | P3 | in-run |
| H6 | three-way materiality verdict + family FDR | `evaluate.py`, `report_verifier.py` | P0 | in-run |
| H7 | refusal ledger + save-to-miss ratio | new | P0 | in-run |
| H8 | vintage/lag guard + non-LLM comparator | `data_quality.py`, `dataflows/` | P3 | in-run |
| H9 | report attribution + factor novelty | new | P3 | in-run |
| H10 | coverage window + survivor labelling | `coverage_window.py` (new) | P0 | in-run |
| H11 | autocorrelation-aware intervals + information gap | `conformal.py` | P0 | in-run |
| R1 | duration-law hazard for BOCPD | `regime.py:764` | P1 | in-run |
| R2 | heavy-tail emissions + coverage-tested regime VaR | `regime.py:367` | P2 | in-run |
| R3 | calibrated null band for spectral movement | `regime.py`, `covariance_models.py` | P1 | in-run |
| R4 | text-proposed, statistically-validated shift dates | new | P3 | offline/weekly |
| R5 | calibrated forward stress probability | `market_breadth.py` | P3 | weekly |
| R6 | early-warning admission gate | new | P4 | offline (blocked) |
| R7 | coincident stress index + epicentre | new | P1 | in-run |
| R8 | labelling constraint (no producer) | - | - | constraint |
| R9 | soft-gate constraint, deferred | - | - | constraint |
| K1 | quality/uncertainty-adjusted tail number | new (composes 3) | P2 | in-run |
| K2 | four drawdown expectations + `T^(H-1/2)` | `book_risk.py` | P1 | in-run |
| K3 | risk-neutral skewness proxy + regime conditioning | `options_surface.py` | P1 | in-run |
| K4 | covariance from characteristics (short-history path) | `covariance_models.py` | P4 | offline |
| K5 | absorbing-boundary size multiplier | `size.py` | P2 | in-run |
| K6 | marking-aware VaR | - | - | recorded only |
| V1 | volatility forecast pool + routing | new | P4 | offline-ish (blocked) |
| V2 | memory parameter + HAR-family forecast | `long_memory.py` (new) | P1 | in-run |
| V3 | RND recovery with identifiability flag | `rnd_recovery.py` (new) | P3 | in-run |
| V4 | event-conditional surface shape | `options_surface.py` | P1 | in-run |
| V5 | subdominant eigenspace rotation + MP check | `eigen_rotation.py` (new) | P3 | in-run |
| V6 | jump-robust proxies on daily bars | `volatility_models.py` | P1 | in-run |
| V7, V8 | declined, recorded | - | - | - |
| X1 | volatility-rank transition chain | `rank_transition.py` (new) | P4 | offline |
| X2 | redundancy screen over components | `factor_expressions.py`, `alpha_zoo.py` | P3 | offline |
| X3 | Marchenko-Pastur lower-spectrum count | `market_breadth.py`, `sector_breadth.py` | P1 | in-run |
| X4 | eigenmode variance ratio by horizon | new | P4 | offline |
| X5 | valuation-anchored peer weights | `peer_universe.py` (**replaces**) | P3 | offline fit |
| X6 | forward-rank test of existing liquidity estimators | `signal_analysis.py` + `liquidity_risk.py` | P1 | offline |
| X7 | relation-classified peer edges | `peer_universe.py`, `theme_triggers.py` | P3 | offline |
| X8 | spectral excess mass + cost-optimal span | `technical_factors.py` | P1 | in-run |
| N1 | event tags, story clustering, per-tag drift prior | new | P3 | in-run + offline fit |
| N2 | Item 1A-scoped, volatility-supervised filing tone | `text_factors.py`, `dataflows/sec_edgar.py` | P3 | in-run + offline fit |
| N3 | learned aggregator over labels/confidences/agreement | new | P2 | in-run |
| N4 | five-dimension elicitation, relevance-weighted | new | P3 | in-run (admitted subset) |
| N5 | prompt-condition A/B harness | `agents/utils/prompt_metrics.py` | P3 | offline |
| N6 | embedding news relevance (compared, not swapped) | `news_relevance.py` | P3 | in-run |
| N7 | semantic plausibility screen on lead-lag | new | P3 | offline |

---

## 6. Cross-item dependencies

```text
P0-1 H10 coverage_window ......... gates every panel statistic in P1 and P4
P0-2 H1  trial ledger ............ -> H3 (Stage 2 retains the candidate matrix)
P0-4 H11 intervals ............... -> H4 excess_accuracy, H6 materiality, K1 band, R2 coverage test
P0-3 H7  refusal ledger .......... -> N7 (rejections logged), X2 (dropped components logged)
P0-6 H6  three verdicts ........... -> every later item's findings, which must be able to be INCONCLUSIVE
P1 V2   memory_parameter ......... <- K2 (Hurst is computed today; a memory parameter is the complement)
P1 X3   mp_below_count ........... + R3 eigen null band: both spectral, one per panel read
P1 R1   hazard_mode .............. independent; smallest change in the regime theme
P2 H2   availability gate ........ <- a per-field availability table (H8's publication-lag work)
P2 R2   coverage-tested VaR ...... -> K1 (the coverage test ships with the tail layer)
P4 R6   onset gate ............... <- the labelled onset panel, which does not exist yet
P4 K4   characteristics covariance <- an offline encoder; must replace, not sit beside
```

Two ordering constraints are hard: **H3 cannot land before H1's ledger exists**, and
**R6 cannot land before the onset panel exists**. Everything else is independently landable.

---

## 7. In-run versus offline (the 40-minute budget)

A four-symbol run takes ~40 minutes end to end (measured: the MCD interactive run at
`ff27ab4` took 2405 s). Against that budget:

**In-run, cheap (seconds or less).** H10, H1, H7, H11, H4, H6, X3, V2, V6, R1, R3, R7,
K2, K3, K5, V4, X8, H2, N3, K1, R2, V3, N6.

**In-run but material.** N1 (1-2 batched tag calls per symbol-day), N4 (one LLM call per
**admitted** article - the doc's most expensive per-run item, and the admission filter is a
prerequisite), V5 (only where the MP edge allows, which is usually `unavailable` at this
book's size).

**Offline by construction, never in-run.** H3 (5x1000 replays), X1, X4, X5's fit, X2, X6,
N5, N7, R4, R6, K4, V1's refit. Ground rule 8 forbids calling these from
`prepare_initial_state`, `finalize_run`, or any agent tool.

**Panel needs.** R3, R5, X1, X3, X4 and V5 read a cross-section, not a symbol. For R3, R5,
X4 and V5, the docs recommend a **weekly offline pass** rather than a per-run producer; R5's
calibration belongs with `strategies/calibration.py`, and X3 is cheap enough per panel
because it runs on 11 sector ETFs.

---

## 8. Open decisions (owner)

Each themed doc ends with one line; those six, plus five the grounding work surfaced:

**From the six docs.**

1. **Honesty (H):** which subset to build, and whether **H10 + H1 + H7** land together as a
   first pass. This plan assumes yes and puts them in P0.
2. **Regime (R):** whether **R1 + R2** land as a first pass, and whether to fund the
   labelled onset panel that **R6** depends on.
3. **Risk (K):** whether **K1 + K2** land as a first pass, and whether the mandate permits
   the **`T^(H-1/2)` rescaling** to reach the drawdown governor.
4. **Volatility (V):** whether **V6 + V2** land as a first pass, and whether **`VXV` and a
   HY-spread series** are worth adding to the vendor surface to enable V1's full state
   vector.
5. **Cross-section (X):** whether **X3 + X6 + X2** land first, and whether the panel-scale
   items (**X1, X4**) are scoped as a weekly offline job rather than per-run producers (this
   plan assumes offline).
6. **News (N):** whether **N3 + N1** land first, and whether the engine may add a
   hosted-embedding dependency for N1's tagging and N6's comparison.

**Surfaced by the grounding work.**

7. **scikit-learn:** add it as a declared dependency, or scope **X2** to a hand-rolled L1
   selection (~80 lines for the selection half)? X5 and V1 are affected either way. K4 is
   deferred regardless.
8. **torch:** it is installed but undeclared. Declare it (making N1/N6 local and explicit),
   or keep the hosted/LLM-call route the news doc already scoped?
9. **tsbootstrap:** adopt the library for H11's conformal calibrators, or keep the
   in-house moving-block bootstrap (no new dependency, and the block-length rule is already
   specified)?
10. **H8's data sourcing:** an as-reported vintage store needs ALFRED (or a documented lag
    substitution). `dataflows/pit_registry.read_as_of` masks payloads by as-of date but only
    for payloads stored under the right date - the vintage store is the missing half.
11. **`docs/scores/MEASUREMENT_FINDINGS.md`** is owner-authored and already records three
    fields as "not measured" that are now measured. Findings from these phases need a home;
    nominate the file (and its edit convention) or a new ledger, and say which.

**Standing constraint, restated:** R9 is not a build. Regime information conditions *how
much to trust* another read; it is never concatenated onto it.

---

## 9. Verification and landing protocol

Per item, in order:

1. **Failing-first proof.** Write the test, prove it **fails** under a targeted mutation of
   the code it guards, restore the source **byte-identical** (assert sha256 in a `finally`),
   and assert the expected test name appears in the failure output.
2. **Gate registration (six points)** if the item adds a gate - section 0 rule 6.
3. **Wiring in the same commit** if the item adds a public function to `strategies/` or
   `dataflows/` - section 0 rule 7.
4. **Full engine suite** (`py -3.12 -m pytest tests -q`, ~11-13 min) for any code change,
   run detached, with no source edits while it runs and no other suite concurrently. A
   docs-only commit does not need it.
5. **`py -3.12 -m ruff check .`** clean. Scratch scripts removed before the suite runs;
   the repo-root lint sees untracked `.py` files.
6. **Docs in the same commit**: `CHANGELOG.md` (newest entry directly under the first
   `### Changed`), `docs/AGENT_ONBOARDING.md` (newest entry above the current top dated
   entry), `docs/gate_registry.md` (the row **and** the coverage sentence), `.env.example`,
   `docs/api_reference.md` section 1.1 (via `scripts/gen_api_reference_table.py --write`),
   and any design doc whose status line changes.
7. **Web impact stated** in the CHANGELOG entry if the item touches a tool, flag or JSON
   shape the sibling app consumes. Contract tests:
   `py -3.12 -m pytest tests/test_engine_contract.py tests/test_doc_claims.py -q` from
   `trading_web/`.
8. **One item per commit**, explicit paths staged (never `git add -A`), with
   `git diff --cached --numstat` inspected before the commit. Doc edits must show `N 0`.

---

## 10. Honest limits

1. **None of this was backtested against this engine.** Every proposal in the six docs is
   untested here until P0's instruments say otherwise. This plan sequences the instruments
   first for exactly that reason.
2. **A gate is not evidence of an edge.** Adopting all six phases makes the engine harder
   to fool and no more likely to be right.
3. **The corpus's results are mostly single-window, single-market preprints.** Each item
   carries its paper's caveat into the design docs, and those caveats are the reason
   several items are declined (V7, V8, K6, the absence of H3's certification claim).
4. **Two of the three most load-bearing regime results are negative** (R8, R9), and the
   news theme's text results are the weakest in the survey by evidence quality. Adopting
   the vocabulary of a result is not adopting the result.
5. **The plan's own cost numbers are the papers' plus the measured dependency surface.**
   Where a cost was not measured (V1's refit cadence, N1's tagging latency at feed volume),
   the item says so rather than guessing.
6. **Nothing here enters `COMPOSITE_ENGINES`.** Six docs, 49 items, zero member changes -
   and that is a deliberate property of the corpus's findings, not an omission.
