# Implementation Plan - Volatility, the Option Surface, and What the Engine Should Refuse

Status: **IN PROGRESS** - wave 0+1 build started: V6, V2 and V4 landed, and V6's jump leg now fires in-run (2026-09-23). The rest of this plan is not started.
2026 paper-survey adoption work, one of the six themes derived from the parent survey.
**Parent design:** [`design_vol_surface_and_vrp.md`](design_vol_surface_and_vrp.md)
**Parent survey:** [`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md)
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency surface, the cross-theme phase map, the dependency graph and the landing protocol live there.
**Items:** V6 (P1), V2 (P1), V4 (P1), V3 (P3), V5 (P3), V1 (P4, blocked), V7+V8 (declined, recorded).
**Gates added:** 5 - `enable_jump_robust_proxies`, `enable_long_memory`, `enable_event_iv_lift`, `enable_rnd_recovery`, `enable_eigen_rotation`. No existing gate is extended by this theme.

## 0. Scope

This plan covers the eight volatility-and-options items V1-V8: three P1 in-run reads (V6,
V2, V4), two P3 in-run producers (V3, V5), one P4 offline-ish architecture blocked on a
vendor decision (V1), and two declined-and-recorded papers (V7, V8).

Every item is additive and default-off, and every item degrades to `unavailable` rather
than to zero when its inputs are missing; none changes an existing computation. The
inherited rules that bind this theme specifically: **ground rule 3** - no item adds a
member to `COMPOSITE_ENGINES`, which stays `(fundamental, technical, regime, risk)`; V1-V6
feed `volatility_models`' existing consumers and `risk_score` instead. **Ground rule 2** -
V6 must not become a second authority beside `parkinson_vol` / `yang_zhang_vol`, V5 must
not sit beside the correlation reads whose rotation it measures, and V4 shares
`strategies/options_surface.py` with K3's risk-neutral skew proxy. **Ground rule 4** -
coverage travels with the number, so V2's aggregates and V5's panel reads report their
window or refuse. **Ground rule 7** - each new public function in `strategies/` ships with
its first caller in the same commit. **Ground rule 8** - V1's refit is an offline artefact
and is never called from `prepare_initial_state`, `finalize_run`, or any agent tool.

Rule-4 impact: none at the time of writing - option and volatility reads are internal to
the analysts and the risk engine.

## 1. Item cards

### V6 - Jump-robust proxies on daily bars

**Target.** `strategies/volatility_models.py`, beside `semivariance:55`, `parkinson_vol:142`, `garman_klass_vol:172`, `yang_zhang_vol:275`: new public `bipower_proxy(ohlc)` and `quarticity_proxy(ohlc)` plus the jump share they imply. First caller: `book_risk`'s tail read, which measures tail risk today "without asking whether the tail came in one print".
**Phase / run mode.** P1 / in-run.
**Behaviour.** Daily-bar analogues of bipower variation and realized quarticity - a squared-return-based jump-robust estimator and a quarticity proxy - so a jump is distinguishable from a diffusion without tick data. Every output is named a **proxy**, never a realized measure.
**Gate.** `enable_jump_robust_proxies`, default off.
**Failing-first test.** `tests/test_volatility_models.py::test_jump_proxy_separates_one_print_from_diffusion`. Mutation: drop the lag-1 cross-product term so the proxy collapses to a squared return. The test asserts a one-print path carries a strictly higher jump share than a smooth path of the same total variance, and fails by name under that mutation.
**Acceptance.** A one-print path and a smooth path with equal total variance get different jump shares; a window below the estimator floor returns `unavailable`, never `0.0`; with the gate off, `semivariance`, `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `yang_zhang_vol_series`, `ewma_vol` and `garch11_fit` are unchanged bit-for-bit.
**Depends on.** nothing (per-symbol; H10's `coverage_window` is used only to report the window).
**Doc caveat.** Without intraday data this is a proxy battery, not 2602.19732's estimator set - that paper's value is the tick-level archive, and only the daily-range subset is reproducible here.

### V2 - A memory parameter, not just a Hurst exponent

**Target.** New `strategies/long_memory.py`: `memory_parameter(returns) -> {gph_d, whittle_d, se}` and a HAR-family `rv_forecast(...)` whose extra regressors are the cross-sectional and sector persistence aggregates. The roughness leg stays where it is: `mean_reversion.hurst_exponent` (`:112`).
**Phase / run mode.** P1 / in-run.
**Behaviour.** A rolling semiparametric memory parameter per stock by GPH log-periodogram regression and local Whittle (`log I(lambda_j) = c - 2d*log(lambda_j) + e`) on 750-day windows, feeding layered HAR / HAR-X / shrinkage / pooled-Lasso regressions (`RV_{t+1} = b0 + b_d*RV_t + b_w*RV_w + b_m*RV_m (+ X_t)`). `d` is reported **beside** the forecast, never instead of it.
**Gate.** `enable_long_memory`, default off.
**Failing-first test.** `tests/test_long_memory.py::test_memory_parameter_is_backward_and_reported_beside_forecast`. Mutation: compute `d` on the full sample, so a future stressed name enters the aggregate. The test asserts the estimate is strictly backward and that the forecast record always carries `d` beside it, and fails by name under that mutation.
**Acceptance.** On a synthetic series with a known memory parameter, GPH and local Whittle bracket the truth within their `se`; a window containing any observation at or after the as-of date returns `unavailable`; the forecast return shape always carries `d` (a forecast from `d = 0` and one from `d = 0.44` are different objects).
**Depends on.** nothing (P1). The cross-sectional and sector aggregates are `unavailable` until a panel read exists; H10's `coverage_window` reports the panel window.
**Doc caveat.** The gains are "moderate" by the paper's own account and largest in stress - a crisis-channel improvement, not a general one - and its evidence (`d = 0.226` GPH, `0.440` local Whittle) is a cross-section this engine does not hold at that depth, so this is a re-measurement on this engine's panel before any threshold is trusted.

### V4 - The event shape, not the surface forecast

**Target.** `strategies/options_surface.py` (`:25` `iv_skew`, `:126`, `:152`), consuming `catalyst.fed_imminence:142`: new `pre_event_iv_lift(chain, event_date)`.
**Phase / run mode.** P1 / in-run.
**Behaviour.** Describes the ATM term-structure shape in **event time** - days to event, not calendar days - around a scheduled catalyst: the part of 2608.10693 that is robust (ATM implied volatility rises about two days before FOMC, up to +50% at 0DTE on announcement day). It is not a surface forecaster.
**Gate.** `enable_event_iv_lift`, default off.
**Failing-first test.** `tests/test_options_surface.py::test_pre_event_lift_is_indexed_in_event_time`. Mutation: index the shape by calendar days instead of days to event. The test asserts the same chain read against two different event dates yields different event-time shapes, and fails by name under that mutation.
**Acceptance.** With a scheduled event in the calendar the shape is indexed by days to event and carries the event date; with no event in the window it returns `unavailable`; no value is produced for a date after the as-of date (there is no forecasting leg).
**Depends on.** nothing (P1): the chain is already fetched and `catalyst.fed_imminence:142` already exists.
**Doc caveat.** The forecasting half is statistically insignificant by the authors' own tests; adopting it would be adopting a negative result as a positive one.

### V3 - Recover a density only when it is identifiable, and say when it is not

**Target.** New `strategies/rnd_recovery.py`, consuming `strategies/options_math.py:244` (`variance_swap_strike`) and `:399` (`model_free_implied_variance`): `rnd_recovery(chain) -> {density | None, method, conditioning, status}`.
**Phase / run mode.** P3 / in-run.
**Behaviour.** Fits a two-component lognormal mixture (or SVI-equivalent) per expiry under mass and forward constraints, returns decision functionals (1% quantile, risk-neutral variance, tail probability), and returns `status = unavailable` when the covered strikes cannot span the density or the conditioning spectrum is too poor. The unidentifiability flag is derived from the conditioning spectrum of the covered strikes.
**Gate.** `enable_rnd_recovery`, default off.
**Failing-first test.** `tests/test_rnd_recovery.py::test_sparse_chain_returns_unavailable_not_a_density`. Mutation: drop the conditioning-spectrum flag and always return a fitted density. The test asserts a chain whose strikes cannot span the density returns `status = unavailable` with `density is None` and the conditioning number reported, and fails by name under that mutation.
**Acceptance.** On a chain with a full strike span the returned density integrates to one and matches the forward constraint within tolerance; on a sparse chain the result is `unavailable`. The learned operator is **not** built - a decline recorded inside this card, because per-expiry classical fits beat the adapted learned operator on 524 held-out NIFTY calls.
**Depends on.** `options_math` (exists); P3 requires P0 + P1.
**Doc caveat.** No universal winner exists, per-expiry quantile errors stay large, and the paper's synthetic tail-functionals advantage for learned operators did not transfer to real quotes - do not build the learned version.

### V5 - Eigenspace rotation as a state variable

**Target.** New `strategies/eigen_rotation.py`, beside `strategies/covariance_models.py` (`:63` `ledoit_wolf_shrink`, `:106` `ewma_covariance`): `eigen_rotation(prev_corr, curr_corr) -> {rec, angles, mp_edge_check}`.
**Phase / run mode.** P3 / in-run (the weekly-pass question is raised in section 5).
**Behaviour.** Removes the market mode from a rolling 12-month correlation matrix, takes the subdominant eigenvectors, and measures rotation as the mean squared sine of the three principal angles between consecutive windows' subdominant eigenspaces - with a **mandatory** check that the subdominant block is outside the Marchenko-Pastur edge, because inside that edge the eigenvectors are noise and the rotation is meaningless. Inside the edge the output is `unavailable`.
**Gate.** `enable_eigen_rotation`, default off.
**Failing-first test.** `tests/test_eigen_rotation.py::test_rotation_refuses_inside_the_mp_edge`. Mutation: remove the MP-edge check. The test asserts a cross-section whose subdominant block lies inside the edge returns `unavailable`, never a rotation number, and fails by name under that mutation.
**Acceptance.** Outside the edge the rotation equals the mean squared sine of the three principal angles and is invariant to eigenvector sign; inside the edge the output is `unavailable`; both windows end at the as-of date.
**Depends on.** `covariance_models` (exists); P3 requires P0 + P1; H10's `coverage_window` for the panel. Shares the Marchenko-Pastur bound `(1-sqrt(n/w))^2` with X3's `mp_below_count`.
**Doc caveat.** The paper's panel is survivor-tilted by its own coverage filter; this is attribution/state measurement with no timing alpha and no crash protection, and its implied-correlation leg needs Cboe indices the engine does not have.

### V1 - Volatility forecast pool and regime-similarity routing

**Target.** New module beside `strategies/volatility_models.py` (whose `garch11_fit:425` and range estimators are the econometric members): `vol_forecast_pool(returns, state) -> {forecast, members[], weights, regime}`, over the members HAR-RV, GARCH(1,1)-t, FIGARCH(1,1)-t, GRU and XGBoost.
**Phase / run mode.** P4 / offline-ish, **BLOCKED on the vendor decision** (section 5). Ground rule 8: the refit is an offline artefact.
**Behaviour.** Scores each member online with the risk-sensitive loss `L = QLIKE(y, yhat) + lambda*max(y - yhat, 0)^2 / y^2` against the best active member (`R_m = L_m - min_j L_j`), weights the last 252 dates by recency and regime similarity (`w ~ exp(-gamma_time*(t-s)) * exp(-||z_t - z_s||^2 / gamma_reg^2)`), routes by a shrunk quantile threshold into pre-specified calm/stress pools, blends through a second gate against the rolling-best forecast, and applies a conditional HAR floor. The underprediction penalty stays a **separate** reported loss beside QLIKE.
**Gate.** none (needs the full state vector - `log VIX`, `log(VIX/VXV)`, 20-day realized vol, vol-of-vol, term spread, HY spread - and `VXV` plus a HY-spread series are not in the engine's fetch surface).
**Failing-first test.** `tests/test_vol_forecast_pool.py::test_pool_state_excludes_day_t_realization`. Mutation: let day-`t` realized variance enter the state vector. The test asserts every score uses forecasts and realizations up to `t` only, and fails by name under that mutation.
**Acceptance.** Weights sum to one; the routing state is a function of the state vector alone, with models refit every 21 days on a 504-day window; QLIKE and the underprediction penalty are reported as two losses; the Diebold-Mariano comparison is emitted against **both** baselines with its asset count. With `VXV` and the HY spread absent, `regime` is reported `partial` and the routing gain is `unmeasured`.
**Depends on.** the vendor decision (section 5); the ML-forecaster dependency decision (scikit-learn or the engine's existing regressions).
**Doc caveat.** The loss is a risk-management objective, not a trading return - gains concentrate in high-vol regimes, and the paper's Diebold-Mariano is significant against the VIX-switch baseline on 5 of 6 assets but against the rolling-best baseline on only 3.

### V7, V8 - Declined, recorded

**Target.** none. No module, no gate, no config key, no test.
**Phase / run mode.** - / recorded only.
**Behaviour.** V7 (2607.08500): a volatility-scaled piecewise-polynomial SDF estimated from options by Hansen-Jagannathan-distance GMM, predicting the equity premium at `R2_OS` up to +12.05% at 120d - it needs a long dense OptionMetrics-scale panel with joint implied rate and dividend extraction, which is out of this engine's reach. V8 (2608.24786): VRP harvesting by learning-to-rank, out-of-time Sharpe 4.31-5.76 - one index, one hold-out year, resting on intraday mark series, margin and fee assumptions a daily engine cannot reproduce. The record exists so neither is silently re-proposed; the theme's third refusal (2608.10693's surface forecaster) is declined inside V4's card.
**Gate.** none (declined - there is nothing to switch on).
**Failing-first test.** none (a decline has no code to mutate).
**Acceptance.** no code, gate or config key is added for either paper; the decline stays recorded in the design doc.
**Depends on.** nothing.
**Doc caveat.** The Sharpe should be treated as a red flag rather than a target, and it is a useful illustration of why 2604.15531 and 2608.27734 exist.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| V6 | jump-robust daily-bar proxies | `strategies/volatility_models.py` | P1 | in-run | `enable_jump_robust_proxies` |
| V2 | memory parameter + HAR-family forecast | `strategies/long_memory.py` (new) | P1 | in-run | `enable_long_memory` |
| V4 | event-conditional surface shape | `strategies/options_surface.py` | P1 | in-run | `enable_event_iv_lift` |
| V3 | RND recovery + identifiability flag | `strategies/rnd_recovery.py` (new) | P3 | in-run | `enable_rnd_recovery` |
| V5 | subdominant eigenspace rotation + MP check | `strategies/eigen_rotation.py` (new) | P3 | in-run | `enable_eigen_rotation` |
| V1 | volatility forecast pool + routing | new, beside `strategies/volatility_models.py` | P4 | offline-ish (blocked) | none (needs the full state vector) |
| V7, V8 | declined, recorded | - | - | recorded only | none (declined) |

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_jump_robust_proxies` | V6 | `strategies/volatility_models.py` | off |
| `enable_long_memory` | V2 | `strategies/long_memory.py` | off |
| `enable_event_iv_lift` | V4 | `strategies/options_surface.py` | off |
| `enable_rnd_recovery` | V3 | `strategies/rnd_recovery.py` | off |
| `enable_eigen_rotation` | V5 | `strategies/eigen_rotation.py` | off |

Five new gates; none extends an existing gate. The six registration points per gate
(`DEFAULT_CONFIG`, an `_ENV_OVERRIDES` row, a `docs/gate_registry.md` row with an
enforcement site, a `tests/test_gate_env_toggles.py` `REGISTRY` entry, `.env.example`, and
a `docs/api_reference.md` section 1.1 row) are listed in [`README.md`](README.md). V1 and
V7/V8 add no gate.

## 4. Dependencies

This theme's slice of the dependency graph:

```text
P0-1 H10 coverage_window ......... -> V2's cross-sectional aggregates, V5 and V1 (panel windows)
P0-6 H6  three verdicts .......... -> every V-item's findings must be able to be INCONCLUSIVE
P1 V2   memory_parameter ......... <- K2 (Hurst is computed today; a memory parameter is the complement)
P1 V6   jump-robust proxies ...... -> book_risk's tail read (first caller, same commit)
P1 V4   pre_event_iv_lift ........ <- catalyst.fed_imminence:142 (exists); shares options_surface.py with K3
P3 V3   rnd_recovery ............. <- options_math:244 variance_swap_strike, :399 model_free_implied_variance
P3 V5   eigen_rotation ........... <- covariance_models; MP bound (1-sqrt(n/w))^2 shared with X3's mp_below_count
P4 V1   vol_forecast_pool ........ <- the vendor decision (VXV, HY spread) + the ML-forecaster decision
```

Other-theme items named: H10, H6, K2, K3, X3. V7 and V8 have no dependency because they
have no producer. Two constraints are hard: **V1 cannot land before the vendor decision**,
and **V5 may not produce a number where the MP-edge check fails** - its honest common
answer on this book's size is `unavailable`.

## 5. Decisions requested (owner)

1. **This theme's own line.** Whether **V6 + V2** land as a first pass, and whether **`VXV` and a HY-spread series** are worth adding to the vendor surface to enable V1's full state vector. Until they are, the pool routes on a smaller state and the routing gain is unmeasured.
2. **The ML-forecaster dependency for V1.** Its three ML members (plus the shrinkage and pooled-Lasso regressors) need either scikit-learn as a declared dependency or the engine's existing regressions; X5 is affected either way.
3. **V5's run mode.** The panel reads (R3, R5, X4, V5) are recommended as a weekly offline pass rather than a per-run producer; this plan keeps V5 in-run as assigned and asks whether that should change.
4. **A home for this theme's findings.** V2's memory-parameter re-measurement and V6's proxy battery produce findings that need a ledger; `docs/scores/MEASUREMENT_FINDINGS.md` is the candidate.

## 6. Honest limits

1. **Everything here is a forecast of variance, not a return.** Structure is forecastable and return level is not; a better volatility forecast improves risk sizing and conditioning, and this theme claims nothing more.
2. **V1's headline gain is unmeasured on this engine.** Its -24% high-regime loss and -22% underprediction loss are the paper's, on a state vector the engine only partly fetches; the refit cadence was not measured here.
3. **V5's honest output is usually `unavailable`.** The MP-edge check fails on a cross-section this small; that is a correct answer, not a defect, and it must be reported rather than softened.
4. **V2 and V6 are re-measurements, not adoptions.** V2's `d` comes from a cross-section the engine does not hold at that depth, and V6 is a proxy battery by construction; neither threshold may be trusted before it is re-measured on this engine's panel.
5. **No item here enters `COMPOSITE_ENGINES`.** V1-V6 feed `volatility_models`' existing consumers and `risk_score`; none enters the composite by adjacency.
6. **None of it was backtested against this engine**, and two of the theme's three headline results (V8's Sharpe, 2608.10693's forecaster) are declined rather than built - that decline is the design working.
