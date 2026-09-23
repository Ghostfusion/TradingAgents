# Design: Risk, Tail Measurement, and the Coverage That Licenses Them

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The risk channel - `risk_score`, the book-risk primitives, tail measurement, drawdown
expectations, covariance under short panels, and position sizing. Takes the 5 high- and 11
medium-relevance risk papers plus the covariance items from the 2026 `q-fin` corpus survey.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Plan:** [`docs/implementation_plan_paper_survey_26.md`](implementation_plan_paper_survey_26.md) - the phased, gated adoption plan for these items (v1.0, PLAN).
**Rule-4 impact:** none. Risk reads are internal.

---

## 1. Executive summary

### What the corpus says about risk measurement

The theme's single most useful paper makes the engine's own house rule into a mechanism.
**2604.08765** ships a next-day 5% VaR *together with* an input-quality score and a prediction-
uncertainty score, where both act on the number: they **widen the estimate or mark it unavailable**.
Its breach rate falls from 5.80% to 4.35% overall and from 6.56% to 4.89% in stress, and it holds up
under simulated input corruption (15% row faults). This engine already has the doctrine - *coverage
travels with the number; missing data is `unavailable`, never zero* - and already has every
ingredient (`book_risk.simple_var` / `cvar` / `portfolio_cvar`, `data_quality.aggregate_quality`,
`conformal.quantile_band`). What it does not have is the join.

Three further findings, each of which changes a number rather than adding a signal:

**1. A drawdown has four separate expectations, and Gaussian tables conflate them.** 2608.00127
extends the Rej-Seager-Bouchaud framework to **maximum drawdown, maximum loss, time under water and
longest recovery time**, and shows the four move *differently* when skewness, fat tails, volatility
clustering and Sharpe-estimation uncertainty vary - "so a single Gaussian table mis-warns". Its
cleanest result is a correction to a habit: under long memory the apparent amplification of drawdown
risk is, for maximum-drawdown depth, **almost entirely self-similar dispersion scaling `T^(H-1/2)`
rather than path geometry** - a failure of square-root-of-time calibration, not intrinsic danger.

**2. Canonical option-implied predictors decay.** 2608.26115 builds a 12.36M firm-day panel and
finds the Xing smirk coefficient decaying from **-0.023 (t = -5.5) in 2015-19 to -0.006 (t = -1.5) in
2023-26**, then flipping to **+0.016 (t = +2.1)** at a 63-day horizon, while the IV spread and
risk-neutral skewness stay significant at `|t| > 4` in every cell. The lesson is not "use the smirk";
it is that a published option-implied predictor is a *regime-conditional* quantity and must not be
hard-wired with a sign.

**3. Covariance from returns fails exactly where it is needed.** 2607.24410 learns a forward
covariance for the equity cross-section from point-in-time **characteristics** alone, which also
covers names with too little return history to estimate covariance from returns. 2608.30446 attacks
the same problem from the data-structure side: a positive-definite estimate for **ragged
pairwise-complete** panels, trained end-to-end to minimize realized global-minimum-variance risk,
over up to 1,500 US equities and 26 expanding windows. Ragged pairwise panels are precisely the
*coverage* problem of §4 of the survey, in covariance clothing.

### The one-sentence thesis

> A risk number without its input quality, its uncertainty, and the coverage that produced it is not
> a conservative estimate - it is an unlabelled one.

---

## 2. What this repo already has (verified)

| Instrument | Where, verified |
|---|---|
| VaR, CVaR, portfolio CVaR | `strategies/book_risk.py:9` `simple_var`, `:18` `cvar`, `:59` `portfolio_cvar` |
| Drawdown governor | `strategies/book_risk.py:210` `drawdown_gate` |
| Maximum drawdown (realized, from an equity curve) | `strategies/evaluate.py:119` `max_drawdown` |
| Decision-level input quality + cross-vendor disagreement + PIT invariant | `strategies/data_quality.py:40` `aggregate_quality` |
| Conformal quantile bands and rolling bands | `strategies/conformal.py:103` `quantile_band`, `:143` `rolling_band` |
| IV skew, surface shape, term-structure slope | `strategies/options_surface.py:25` `iv_skew`, `:126` `surface_shape`, `:152` `term_structure_slope` |
| Per-strike dealer gamma | `strategies/derivatives_gamma.py:52` `gex_per_strike` |
| Covariance estimators incl. Ledoit-Wolf | `strategies/covariance_models.py:63` `ledoit_wolf_shrink` |
| HRP, optimizer, liquidity risk, hierarchical risk parity | `strategies/hierarchical_risk_parity.py`, `portfolio_optimizer.py`, `liquidity_risk.py` |
| Kelly sizing | `strategies/size.py:14` `kelly_fraction`, `:24` `position_size_kelly`, `portfolio.py:452` `kelly_weights` |
| Regime-conditional VaR inputs | `strategies/regime.py:367` `hmm_filtered_regime` (see the regime doc) |

Note what is *absent* from this list: no function joins a quality score to a VaR, no drawdown
expectation exists (only realized `max_drawdown`), and no covariance estimator consumes
characteristics.

## 3. The gaps, as builders

### K1 - Attach quality and uncertainty to the tail number

**Finding.** `book_risk.simple_var` / `cvar` / `portfolio_cvar` return a number and nothing else.
`data_quality.aggregate_quality` computes a quality verdict but is not consumed by any risk read.
`conformal.quantile_band` produces an interval but is not applied to VaR. So the engine's headline
tail figure carries no indication of whether its inputs were fit to produce it.

**Paper.** 2604.08765 composes four stages:
`Q_t = 0.30*q_miss + 0.35*q_ohlc + 0.15*q_jump + 0.10*q_vol + 0.10*q_stale`, mapped to
green/yellow/red; a pooled 5% quantile gradient-boosted ensemble with five bootstrap members plus a
63-day historical fallback; an **uncertainty** score from ensemble dispersion, a PCA-Mahalanobis
out-of-distribution distance and a recent breach-drift term; and a conservative blend where quality
and uncertainty only ever move the number **outward, or withhold it**.

**What to compute.** `tail_risk(returns, quality) -> {var, cvar, q_score, uncertainty, band, status}`
where `status` is `ok | widened | unavailable`. The rule is one-directional: quality and uncertainty
may widen the band or refuse the estimate, never narrow it.

**Inputs.** Per-symbol daily OHLCV; the missing-field fraction, OHLC-consistency and stale-price
flags already exist in `data_quality`; ensemble dispersion requires ≥2 members.

**PIT.** Rolling window ending at `t`; the quality flags are properties of the loaded frame.

**Cost.** Cheap: the ensemble is five bootstrap fits per symbol per run, seconds.

**Owner.** New module composing `book_risk` + `data_quality` + `conformal`; consumed by `risk_score`.

**Caveat.** The paper's gain is partly a **conservative downward shift** - its VaR still fails the
Kupiec test - and its thresholds are fixed ex ante on six ETFs. Report it as a reliability layer, not
as a calibrated VaR, and keep the coverage test beside it (see R2 in the regime doc).

### K2 - Four drawdown expectations, and the right time-scaling

**Finding.** The engine measures realized drawdown (`evaluate.max_drawdown`, `book_risk.drawdown_gate`)
and cannot say how deep or how long a drawdown of a given Sharpe *should* run - which is the actual
keep-or-kill question.

**Paper.** 2608.00127 reframes the Rej-Seager-Bouchaud closed forms as a Monte-Carlo table over
**four** measures - maximum drawdown, maximum loss, final negative time, longest recovery time - then
varies skewness, fat tails, volatility clustering and Sharpe-estimation uncertainty at fixed true
Sharpe and volatility, and finds the four move independently. Under fractional Brownian motion the
maximum-drawdown amplification is dispersion scaling:

```text
MDD scales as T^(H - 1/2),   not T^(1/2)
```

so a persistence-heavy book's drawdown is not "more dangerous" - it is mis-scaled by the
square-root-of-time convention.

**What to compute.** `drawdown_envelope(sharpe, horizon, skew, kurtosis, hurst) -> {mdd_median,
mdd_p90, max_loss, time_under_water, longest_recovery}`, with the `T^(H-1/2)` rescaling applied when
a Hurst estimate is available (`mean_reversion.hurst_exponent:112` already computes one).

**Inputs.** An estimated Sharpe and the return series' higher moments - the engine's decision ledger
already holds the former.

**PIT.** Estimated from the strategy's own realized P&L to date.

**Cost.** Monte Carlo is `O(paths * horizon)`; a precomputed lookup table plus interpolation is the
practical form.

**Owner.** `strategies/book_risk.py`, consumed by `backtest_evaluation` and the drawdown governor.

**Caveat.** The framework assumes a stationary Sharpe; the paper's own point is that
Sharpe-*estimation* uncertainty changes the answer, so the envelope must carry the Sharpe's
uncertainty with it.

### K3 - Option-implied reads are regime-conditional, not constants

**Finding.** `options_surface.iv_skew` (`:25`) and `surface_shape` (`:126`) compute a put-skew and
risk-reversal/butterfly. Whether either predicts anything is treated as a property of the read rather
than of the period.

**Paper.** 2608.26115 builds 12.36M firm-days over 10,026 underlyings and three macro regimes, and
finds the smirk's predictive coefficient decaying from -0.023 to -0.006 and then flipping sign
(+0.016, `t = +2.1`) at 63 days, while IV spread and a cross-strike risk-neutral skewness proxy stay
significant (`|t| > 4`) in every cell. It also ships a firm-level option-implied crash classifier
whose out-of-sample `R^2` improves from +0.07% to +1.29%.

**What to compute.** (a) A risk-neutral skewness proxy from cross-strike OTM IVs, requiring at least
five strikes and returning `unavailable` below that - note the paper is explicit that this is a
*cross-strike IV proxy*, not the true BKM moment. (b) Any use of a skew/spread read in scoring is
conditioned on the regime cell, not applied as a constant. (c) The crash classifier is a *proposal*,
not a component: per rule 17 it does not enter the composite by adjacency.

**Inputs.** The option chains the engine already fetches; the full option tape is the paper's data
requirement and is **beyond what this engine's vendors supply** - so the panel regression is out of
reach and only the per-symbol reads are in scope.

**PIT.** End-of-day option records at `t`; standard.

**Cost.** Per-symbol, cheap, on chains already fetched.

**Owner.** `strategies/options_surface.py` for (a); the regime conditioning lives with
`risk_score`'s existing components.

**Caveat.** Regime- and universe-specific, and it needs the whole option tape for its panel claims.
This engine can take the *finding that the coefficient is unstable*, which is the part that changes
behaviour.

### K4 - Covariance when return history is short

**Finding.** `covariance_models` estimates from returns. A name with forty bars contributes a noisy
row and a noisier correlation; the engine's coverage rule says such a name's covariance should be
`unavailable`, but there is nothing to put in its place.

**Papers.** 2607.24410 learns a forward covariance for the equity cross-section from point-in-time
**characteristics** - size, valuation, leverage, sector - producing interpretable factor exposures
and covering names with too little return history. 2608.30446 handles the complementary case, a
**ragged pairwise-complete** panel (each pair using its own overlap), where the naive correlation
matrix is indefinite, and maps it to a PSD matrix with a rotation-invariant neural estimator trained
end-to-end on realized GMV risk, over 26 expanding windows and up to 1,500 US equities.

**What to compute.** The characteristics path is the tractable one here:
`covariance_from_characteristics(char_panel) -> {exposures, covariance, coverage}`, used **only** for
names whose own return history is too short, and labelled as such in the output. The ragged-panel
estimator is noted as the principled version, deferred until a training pipeline exists.

**Inputs.** The characteristics panel the fundamentals engine already assembles.

**PIT.** Point-in-time characteristics; the encoder is fit offline.

**Cost.** Cheap at inference; the encoder is offline training this engine has no stack for.

**Owner.** `strategies/covariance_models.py`, consumed by `hierarchical_risk_parity` /
`portfolio_optimizer`.

**Caveat.** 2608.30446 needs end-to-end neural training and risks becoming a **second covariance
producer** beside `ledoit_wolf_shrink` - which the house rule forbids. If adopted, it must *replace*
the existing estimator on the ragged path, not sit beside it, and the doc says so explicitly.

### K5 - Size below Kelly when a costly boundary is near

**Finding.** `size.kelly_fraction` (`:14`) and `position_size_kelly` (`:24`) apply the growth-optimal
fraction as if the horizon were infinite and ruin were impossible. This engine's mandate has hard
limits and a drawdown governor, i.e. an absorbing boundary.

**Paper.** 2607.28230 solves a finite-horizon binary multiplicative process with an **absorbing
threshold and a residual payoff** by exact lattice propagation, obtaining the optimal exposure
`f*(d, T, rho)` as a function of log-distance-to-boundary `d`, horizon `T` and residual ratio `rho`.
Near the boundary, `f*` is **compressed below the no-boundary Kelly fraction** - and the paper shows
this maps to an elevated apparent CRRA coefficient with no preference heterogeneity, i.e. observed
"risk aversion" may be an artifact of the boundary.

**What to compute.** An optional `boundary_factor(distance_to_limit, horizon, residual)` multiplier
on the existing Kelly size, applied only when a hard limit is configured. It never increases size.

**Inputs.** The risk-basket drawdown (computed for the governor) and the mandate's limits.

**PIT.** Current distance to the limit.

**Cost.** A 2-D lookup over `(d, T)`; trivial.

**Owner.** `strategies/size.py`, consumed by the risk governor.

**Caveat.** **A pure model with no empirical calibration** - `p`, `a`, `b`, `L`, `S` must come from
elsewhere, and the paper is about sizing, not about detecting anything. It is a shape, not a number.

### K6 - Marking-aware VaR recalibration (noted)

**Paper.** 2604.03499 recalibrates sequential VaR for standardized option books in a way that is
**aware of how the book is marked** - so the VaR's validity is tied to the mark convention rather
than to the book's notional. Relevant to this engine only if option positions ever enter the mandate;
recorded here so the idea is not lost, and not proposed for build.

---

## 4. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| K1 | quality- and uncertainty-adjusted tail number | new, composing `book_risk` + `data_quality` + `conformal` | yes |
| K2 | four drawdown expectations + `T^(H-1/2)` rescaling | `strategies/book_risk.py` | no |
| K3 | risk-neutral skewness proxy; regime-conditional skew use | `strategies/options_surface.py` | no |
| K4 | covariance from characteristics on the short-history path | `strategies/covariance_models.py` | no |
| K5 | absorbing-boundary size multiplier | `strategies/size.py` | no |
| K6 | marking-aware VaR (noted only) | - | - |

## 5. Honest limits

1. **K1's gain is partly conservatism.** The paper's VaR still fails the Kupiec test after the
   quality layer; widening a band is easy and being right is not. Ship the coverage test with it.
2. **K4 must not create a second covariance producer.** This is the item most likely to violate the
   house rule by accident, and the doc constrains it to the path where no existing estimator can
   serve.
3. **K3 is a negative result about a predictor, not a new predictor.** Its practical value is that
   the engine should stop treating a skew coefficient as stable.
4. **K5 is uncalibrated by its authors' own admission**, and applying it would reduce position sizes
   in a way that must be argued, not assumed.
5. **The option-tape requirements of 2608.26115 and 2604.03499 exceed this engine's vendors.** Only
   the per-symbol reads are in scope; the panel claims are not.

## 6. Recommended build order

1. **K1** - the join the engine is already one import away from, and the doctrine it already holds.
2. **K2** - turns a realized number into an expectation, and corrects a scaling habit.
3. **K3** - small, and it stops misuse of an existing read.
4. **K5**, **K4** - in that order; both need an argument about sizing and producer uniqueness first.

**Decision requested:** whether K1 + K2 land as a first pass, and whether the mandate permits the
`T^(H-1/2)` rescaling to reach the drawdown governor.
