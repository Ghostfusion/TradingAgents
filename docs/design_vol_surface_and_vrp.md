# Design: Volatility, the Option Surface, and What the Engine Should Refuse

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The volatility and option-derived channels. Takes the volatility/options items from the
2026 `q-fin` corpus survey - 18 medium-relevance papers plus the high-relevance items routed here -
and separates them into three classes: **forecastable** (volatility), **estimable but not
identifiable** (risk-neutral densities, surfaces), and **refused** (results this engine's data
cannot reproduce).
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Plan:** [`docs/implementation_plan_paper_survey_26.md`](implementation_plan_paper_survey_26.md) - the phased, gated adoption plan for these items (v1.0, PLAN).
**Rule-4 impact:** none. Option and volatility reads are internal to the analysts and the risk engine.

---

## 1. Executive summary

### The corpus's cleanest split

This is the one theme where the corpus's ranking of methods is unambiguous and consistent: **the
volatility channel is forecastable, the density channel is estimable, and neither the surface
forecast nor the option-strategy results survive contact with this engine's data.**

**Forecastable.** 2604.10402 pools five next-day realized-variance forecasters (HAR-RV, GARCH(1,1)-t,
FIGARCH(1,1)-t, GRU, XGBoost), scores each online with a **risk-sensitive loss** (QLIKE plus an
underprediction penalty), weights the last 252 dates by recency *and regime similarity*, and routes
between a calm and a stress pool. High-regime loss falls from 0.4834 to 0.3685 (**-24%**) and
underprediction loss from 0.0245 to 0.0192 (**-22%**), significant on Diebold-Mariano against the
VIX-switch baseline on 5 of 6 assets. The engine has each of those single models in some form and
**no pool, no online scoring, and no routing**.

**Estimable, but the corpus says stop there.** 2607.27188's headline is a warning: **accurate option
prices do not imply accurate density recovery.** A two-component lognormal mixture wins on aggregate
synthetic metrics; learned operators win only tail functionals; and on 524 held-out NIFTY calls,
**simple per-expiry classical fits beat the adapted DeepONet**. Its conclusion is that no universal
winner exists and the latent risk-neutral density **is not identifiable from prices alone**. The
deliverable is therefore an *unidentifiability flag* derived from the conditioning spectrum of the
covered strikes - not a density.

**Refused.** 2608.10693's ConvLSTM beats the random walk by ~8-9% RMSE on the IV surface at `h=1`
and the edge "is rarely statistically significant" (Diebold-Mariano frequently fails to reject);
its robust finding is the *event* pattern, not the forecast. 2608.24786 reports an out-of-time
Sharpe of **4.31-5.76** on SPXW put selling from a single index and a single hold-out year, resting
on 1-minute marks, margin and fee assumptions this engine cannot reproduce. Both are recorded and
declined.

### The one-sentence thesis

> The engine should forecast volatility, describe the surface, and refuse to price a density it
> cannot identify - and the corpus is unusually explicit about which of the three is which.

---

## 2. What this repo already has (verified)

| Instrument | Where, verified |
|---|---|
| Realized vol (close-to-close) | `strategies/regime.py:31` `realized_vol` |
| Semivariance | `strategies/volatility_models.py:55` `semivariance` |
| Parkinson, Garman-Klass, Yang-Zhang (+ series) | `strategies/volatility_models.py:142` `parkinson_vol`, `:172` `garman_klass_vol`, `:275` `yang_zhang_vol`, `:319` `yang_zhang_vol_series` |
| EWMA vol | `strategies/volatility_models.py:384` `ewma_vol` |
| GARCH(1,1) MLE, with an IGARCH breakdown guard | `strategies/volatility_models.py:425` `garch11_fit`, `:40` `_IGARCH_AB = 0.999` |
| Variance-swap strike, model-free implied variance | `strategies/options_math.py:244` `variance_swap_strike`, `:399` `model_free_implied_variance` |
| IV skew, surface shape, term-structure slope | `strategies/options_surface.py:25`, `:126`, `:152` |
| Dealer gamma per strike, OPEX, max pain | `strategies/derivatives_gamma.py:52` `gex_per_strike`, + OPEX/max-pain |
| EWMA covariance, Ledoit-Wolf shrinkage | `strategies/covariance_models.py:106` `ewma_covariance`, `:63` `ledoit_wolf_shrink` |
| FOMC imminence, economic calendar | `strategies/catalyst.py:142` `fed_imminence` |

So the engine has a good **estimator battery** and no **combination, memory-parameter, or
surface-geometry** layer at all.

## 3. The gaps, as builders

### V1 - A volatility forecast pool with risk-sensitive routing

**Finding.** `volatility_models` exposes single estimators. Each is used as if it were the forecast.

**Paper.** 2604.10402's architecture: a pool of forecasters, each scored online by
`L = QLIKE(y, yhat) + lambda*max(y - yhat, 0)^2 / y^2` against the best active member,
`R_m = L_m - min_j L_j`, then exponentially weighted by recency **and regime similarity**
(`w ∝ exp(-gamma_time*(t-s)) * exp(-||z_t - z_s||^2 / gamma_reg^2)`) over a state vector of
`log VIX`, `log(VIX/VXV)`, 20-day realized vol, vol-of-vol, term spread and HY spread. A shrunk
quantile threshold routes into pre-specified calm/stress pools; branch outputs blend with a rolling-
best forecast through a second gate; a conditional HAR floor prevents underprediction.

**What to compute.** `vol_forecast_pool(returns, state) -> {forecast, members[], weights, regime}`,
with the underprediction penalty kept as a *separate* reported loss beside QLIKE so the conservatism
is visible rather than folded in.

**Inputs.** Per-symbol daily OHLCV plus the macro state (`VIX`, `VXV`, term spread, HY spread).
All daily vendor data; the engine already fetches several of these.

**PIT.** Scores use only forecasts and realizations up to `t`; models refit every 21 days on a
504-day window. Breaks if day-`t` realized variance enters the state vector, or the pool is chosen
after seeing test results - both worth an explicit test.

**Cost.** Three ML + two econometric forecasters per symbol, refit every 21 days; seconds to minutes
of CPU, no GPU.

**Owner.** `strategies/volatility_models.py` for the members; the pool and routing are a new module.

**Caveat.** The loss is a **risk-management objective, not a trading return** - gains concentrate in
high-vol regimes, and the paper's own Diebold-Mariano is significant against the *VIX-switch*
baseline on 5 of 6 assets but against the rolling-best baseline on only 3.

### V2 - A memory parameter, not just a Hurst exponent

**Finding.** `mean_reversion.hurst_exponent` (`:112`) estimates roughness. There is no
semiparametric long-memory parameter and no HAR/HAR-X regression, so the engine cannot express the
distinction the corpus keeps making between short and long memory.

**Paper.** 2605.24285 estimates a rolling memory parameter per stock by GPH log-periodogram
regression and local Whittle (`log I(lambda_j) = c - 2d*log(lambda_j) + e`), builds cross-sectional
and sector persistence aggregates, and feeds them into layered HAR / HAR-X / shrinkage / pooled-Lasso
regressions:

```text
RV_{t+1} = b0 + b_d*RV_t + b_w*RV_w + b_m*RV_m  (+ X_t)
```

Reported mean `d = 0.226` (GPH) and `0.440` (local Whittle), significant nearly panel-wide, with
stress-period MSE gains over HAR of **+11.8% / +17.9% / +8.8%** at `h = 1/5/22` under high VIX.

**What to compute.** `memory_parameter(returns) -> {gph_d, whittle_d, se}` and a HAR-family
`rv_forecast(...)` whose extra regressors are the persistence aggregates. Report `d` beside the
forecast, because a forecast from a series with `d = 0` and one with `d = 0.44` are different objects.

**Inputs.** Daily returns for a close-to-close realized-variance proxy. True high-frequency RV needs
intraday data the engine lacks; the doc requires the proxy be labelled as such.

**PIT.** Rolling 750-day windows, strictly backward. Breaks if a full-sample `d` or a cross-sectional
aggregate containing future stressed names is used.

**Cost.** Log-periodogram regression is `O(T log T)`; trivial.

**Owner.** New module (`strategies/long_memory.py`), with the roughness leg already in
`mean_reversion.py`.

**Caveat.** The gains are "moderate" by the paper's own account and largest in stress - so the
mechanism is a crisis-channel improvement, not a general one.

### V3 - Recover a density only when it is identifiable, and say when it is not

**Finding.** `options_math` prices variance-swap inputs but the engine has no Breeden-Litzenberger
density, no mixture fit, and no way to say "this chain cannot support a density".

**Paper.** 2607.27188 compares direct parametric and regularized estimators against learned
operators, and its real-data result is the one to keep: **per-expiry classical fits beat the adapted
learned operator on 524 held-out NIFTY calls**, and the paper states plainly that the latent
risk-neutral density **is not identifiable from prices alone**. Its implementation detail that
matters here is an unidentifiability flag derived from the **conditioning spectrum of the covered
strikes**.

**What to compute.** `rnd_recovery(chain) -> {density | None, method, conditioning, status}` where a
two-component lognormal mixture (or SVI-equivalent) is fit per expiry under mass and forward
constraints, decision functionals (1% quantile, risk-neutral variance, tail probability) are
returned, and `status` is `unavailable` when the covered strikes cannot span the density or the
conditioning spectrum is too poor.

**Inputs.** Per-expiry chains with enough strikes. Single-name US chains are frequently too sparse -
which is exactly the case the flag exists for.

**PIT.** End-of-day chain at `t`.

**Cost.** Per-expiry fit, seconds.

**Owner.** New module (`strategies/rnd_recovery.py`), consuming `options_math`.

**Caveat.** No universal winner exists, per-expiry quantile errors stay large, and the paper's
synthetic tail-functionals advantage for learned operators did **not** transfer to real quotes. Do
not build the learned version.

### V4 - The event shape, not the surface forecast

**Finding.** The engine has `fed_imminence` (`catalyst.py:142`) and a term-structure slope read, but
no description of how the surface *behaves around* a scheduled event - which is the part of
2608.10693 that is robust.

**Paper.** ATM implied volatility rises about **two days before FOMC**, up to **+50% at 0DTE on
announcement day**. The ConvLSTM surface forecaster that the paper also builds beats the random walk
by ~8-9% RMSE at `h=1` and is **rarely statistically significant**.

**What to compute.** An event-conditional surface read: `pre_event_iv_lift(chain, event_date)` giving
the ATM term-structure shape in event time (days to event, not calendar days). **Not** a surface
forecaster.

**Inputs.** The chain the engine already fetches plus the calendar it already has. No intraday
surface snapshots required for the *descriptive* read; the forecasting version would need them and is
declined.

**PIT.** Chain at `t`, event date known in advance - a scheduled catalyst is the one thing safely
knowable ahead.

**Cost.** Per-symbol, cheap.

**Owner.** `strategies/options_surface.py`, consuming `catalyst.fed_imminence`.

**Caveat.** The forecasting half is statistically insignificant by the authors' own tests; adopting
it would be adopting a negative result as a positive one.

### V5 - Eigenspace rotation as a state variable

**Finding.** The engine reads correlation *levels* (`book_risk`, `statistical.correlation_matrix`,
`sector_breadth`). Nothing measures how fast the correlation structure's **shape** is rotating, which
is a different quantity from its level.

**Paper.** 2608.20020 removes the market mode from a 12-month correlation matrix, takes the
subdominant eigenvectors, and measures rotation as the mean squared sine of the three principal
angles between consecutive windows' subdominant eigenspaces. Reported coupling to the log variance
risk premium at `t = 5.40` for the three-month average, versus `t = 0.30` for the monthly innovation,
and **largely unspanned** by traded implied correlation (at most 6.7%).

**What to compute.** `eigen_rotation(prev_corr, curr_corr) -> {rec, angles, mp_edge_check}` - the
rotation plus a check that the subdominant block is outside the Marchenko-Pastur edge, because inside
that edge the eigenvectors are noise and the rotation is meaningless.

**Inputs.** A rolling S&P-500-scale panel; the engine's tracked cross-section is much smaller, so the
MP-edge check will frequently return `unavailable` - which is the honest answer.

**PIT.** Both windows end at `t`.

**Cost.** One eigendecomposition per window.

**Owner.** New module (`strategies/eigen_rotation.py`), beside `covariance_models`.

**Caveat.** The paper's panel is survivor-tilted by its own coverage filter; the result is
attribution/state measurement with **no timing alpha and no crash protection**, and its
implied-correlation leg needs Cboe indices the engine does not have.

### V6 - The realized-measure battery this engine can actually run

**Finding.** `volatility_models` has the range estimators (Parkinson, Garman-Klass, Yang-Zhang) but
not bipower variation, realized quarticity, realized kernels, or realized covariance.

**Paper.** 2602.19732 (VOLARE) standardises exactly that estimator set on cleaned tick data, with
HAR/HAR-Q and MEM model classes. Its own caveat is the relevant one: **the value is the tick-level
archive**, and without intraday data only the daily-range subset is reproducible.

**What to compute.** Nothing new, with one exception worth noting: **bipower variation and realized
quarticity have daily-bar analogues** (squared-return-based jump-robust estimators and quarticity
proxies) that let the engine distinguish a jump from a diffusion without tick data. That distinction
is currently absent - `book_risk` measures tail risk without asking whether the tail came in one
print.

**Inputs.** Daily OHLCV.

**PIT.** Backward window.

**Cost.** Trivial.

**Owner.** `strategies/volatility_models.py`.

**Caveat.** Without intraday data this is a proxy battery, not the estimator set; the doc requires
the proxies be named as proxies rather than as realized measures.

### V7, V8 - Recorded and declined

- **2607.08500** (a volatility-scaled piecewise-polynomial SDF estimated from options by
  Hansen-Jagannathan-distance GMM, predicting the equity premium at `R²_OS` up to +12.05% at 120d)
  needs a long dense OptionMetrics-scale panel with joint implied rate and dividend extraction. It is
  an interesting *pricing* result and out of this engine's reach; recorded for completeness.
- **2608.24786** (VRP harvesting by learning-to-rank, out-of-time Sharpe 4.31-5.76) reports a Sharpe
  that should be treated as a red flag rather than a target: one index, one hold-out year, and results
  that rest on intraday mark series, margin and fee assumptions a daily engine cannot reproduce. It
  is declined, and it is also a useful illustration of why 2604.15531 and 2608.27734 exist.

---

## 4. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| V1 | volatility forecast pool + regime-aware routing | new, beside `volatility_models.py` | yes |
| V2 | long-memory parameter + HAR-family forecast | new (`long_memory.py`) | yes |
| V3 | RND recovery with an identifiability flag | new (`rnd_recovery.py`) | yes |
| V4 | event-conditional surface shape | `strategies/options_surface.py` | no |
| V5 | subdominant-eigenspace rotation with an MP-edge check | new (`eigen_rotation.py`) | yes |
| V6 | jump-robust proxies on daily bars | `strategies/volatility_models.py` | no |
| V7, V8 | declined, recorded | - | - |

## 5. Honest limits

1. **The two headline option results are the ones to decline.** A Sharpe of 4.31-5.76 from one
   index-year, and a surface forecast that is rarely significant, are exactly the artifacts the
   honesty doc's gates exist to catch. Declining them here is the design working.
2. **V1 and V2 both need a state vector the engine only partly fetches** - `VXV` and HY spreads are
   not confirmed as live vendor calls. Until they are, the pool routes on a smaller state and the
   routing gain is unmeasured.
3. **V5's honest output on this engine's book is usually `unavailable`.** The MP-edge check will fail
   on a small cross-section; that is a correct answer, not a defect, and it must be reported rather
   than softened.
4. **Everything here is a forecast of variance, not a return.** The corpus's repeated finding is that
   structure is forecastable and return level is not; a better volatility forecast improves risk
   sizing and conditioning, and the doc does not claim more.
5. **No item adds a member to `COMPOSITE_ENGINES`.** V1-V6 feed `volatility_models`' existing
   consumers and `risk_score`; none enters the composite by adjacency.

## 6. Recommended build order

1. **V6** - trivial, and it answers a question the engine currently cannot ask (jump or diffusion).
2. **V2** - a memory parameter is a prerequisite for interpreting any volatility forecast, and it
   pairs with the risk doc's `T^(H-1/2)` rescaling.
3. **V1** - the largest single gain in the theme, and the one with a genuine architecture.
4. **V3** - small, and it adds a refusal the engine lacks.
5. **V4**, **V5** - descriptive reads; V5 only where the MP edge allows it.

**Decision requested:** whether V6 + V2 land as a first pass, and whether `VXV` and a HY-spread
series are worth adding to the vendor surface to enable V1's full state vector.
