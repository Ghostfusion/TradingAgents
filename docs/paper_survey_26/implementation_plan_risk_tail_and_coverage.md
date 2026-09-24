# Implementation Plan - Risk, Tails, and the Coverage That Licenses Them

Status: **IN PROGRESS** - wave 1 landed K3 (2026-09-23); the T1 batch adds K2 (report-only, so the governor keeps the square-root-of-time convention until the mandate answer) and K1 (2026-09-24). K4, K5 and K6 remain: K4 is deferred for want of a training stack, K5 awaits the sizing authorisation, K6 is recorded only.
for the drawdown expectations, the option-implied skew proxy, the quality-adjusted tail number, the
boundary size multiplier, the deferred characteristics covariance and the recorded marking-aware
VaR, all specified in the theme design below, one of the six themed design docs derived from
[`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md).

**Parent design:** [`design_risk_tail_and_coverage.md`](design_risk_tail_and_coverage.md)
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency surface, the cross-theme phase map, the dependency graph and the landing protocol live there.
**Items:** K2 (P1), K3 (P1), K1 (P2), K5 (P2), K4 (P4, offline and deferred), K6 (recorded only).
**Gates added:** 4 new (`enable_drawdown_envelope`, `enable_rn_skew_proxy`, `enable_tail_risk_layer`, `enable_boundary_sizing`). K4 and K6 add none.

## 0. Scope

This plan covers the engine's risk channel - `risk_score`, the book-risk primitives, tail
measurement, drawdown expectations, covariance under short panels and position sizing - through six
items in phase order: two P1 in-run reads (K2, K3), two P2 composite reads over producers that
already exist (K1, K5), one deferred P4 offline item (K4) and one recorded-not-built note (K6).
Every item is additive and default-off, and degrades to `unavailable` when its inputs are missing -
never to zero, and never to a substituted default.

The inherited rules that bind this theme specifically are: **rule 1**, because K1's band is built on
P0-4's intervals and its coverage test is R2's instrument, and a phase that adds a score before P0
lands is adopting an untested claim; **rule 2**, because K4 is the item that rule names - if adopted
it must *replace* the estimator on the ragged path rather than sit beside
`strategies/covariance_models.py:63` `ledoit_wolf_shrink`; **rule 3**, because no item here changes
`COMPOSITE_ENGINES` - K1 and K5 feed components `risk_score` already declares, and K3's crash
classifier is a proposal, not a component; **rule 4**, because K1's headline number must report the
window it was computed over (H10 is the mechanism) or refuse; **rule 6** for the four new gates;
**rule 7** for the new public functions (`drawdown_envelope`, the cross-strike skew proxy,
`tail_risk`, `boundary_factor`, `covariance_from_characteristics`); and **rule 8**, which is what
makes K4 an offline artefact that may never be called from `prepare_initial_state`, `finalize_run`,
or any agent tool.

## 1. Item cards

### K2 - Four drawdown expectations, and the right time-scaling

**Target.** `strategies/book_risk.py` (no new module): `drawdown_envelope(sharpe, horizon, skew, kurtosis, hurst) -> {mdd_median, mdd_p90, max_loss, time_under_water, longest_recovery}`, consumed by `backtest_evaluation` and by the drawdown governor `strategies/book_risk.py:210` `drawdown_gate`. The Hurst input comes from `mean_reversion.hurst_exponent:112`, which already computes one.
**Phase / run mode.** P1 / in-run.
**Behaviour.** A Monte-Carlo table (or a precomputed lookup plus interpolation) over four separate measures - maximum drawdown, maximum loss, time under water, longest recovery - so the engine can say how deep and how long a drawdown of a given Sharpe should run instead of only measuring the one that happened. The `T^(H-1/2)` dispersion rescaling is applied **only when a Hurst estimate exists**; without one the envelope uses the square-root-of-time convention and says so. The envelope carries the Sharpe's estimation uncertainty as a reported field.
**Gate.** `enable_drawdown_envelope`, default off.
**Failing-first test.** `tests/test_drawdown_envelope.py::test_hurst_rescales_mdd`. Mutation: pin the exponent to the constant `0.5` so `hurst` is ignored. It asserts that at `H > 0.5` the p90 maximum drawdown scales as `T^(H-1/2)` and not as `T^(1/2)`, and that with `hurst` absent the result uses `T^(1/2)` and carries `hurst: "assumed"`.
**Acceptance.** At fixed true Sharpe and volatility the four measures move independently as skewness and kurtosis vary - no single Gaussian table reproduces all four; the `H`-scaled p90 matches the closed-form ratio within the table's interpolation tolerance; and the Sharpe's estimation uncertainty is present in the output whenever a Sharpe is.
**Depends on.** nothing - independently landable. `mean_reversion.hurst_exponent:112` exists today, and V2's `memory_parameter` is the complement rather than a prerequisite.
**Doc caveat.** The framework assumes a stationary Sharpe, and the paper's own point is that Sharpe-*estimation* uncertainty changes the answer, so the envelope must carry that uncertainty with it.

### K3 - Option-implied reads are regime-conditional, not constants

**Target.** `strategies/options_surface.py`: a cross-strike risk-neutral skewness proxy beside the existing `iv_skew` (`:25`), `surface_shape` (`:126`) and `term_structure_slope` (`:152`); the regime conditioning lives with `risk_score`'s existing components.
**Phase / run mode.** P1 / in-run.
**Behaviour.** The proxy is computed from cross-strike OTM IVs, requires at least five strikes and returns `unavailable` below that; its record names itself a **cross-strike IV proxy**, not the true BKM moment. Any skew or spread read used in scoring is conditioned on the regime cell rather than applied as a constant. The paper's firm-level crash classifier is a proposal, not a component: it does not enter the composite by adjacency.
**Gate.** `enable_rn_skew_proxy`, default off.
**Failing-first test.** `tests/test_rn_skew_proxy.py::test_proxy_unavailable_below_five_strikes`. Mutation: lower the strike floor so a four-strike chain yields a number. It asserts `unavailable` at four strikes, a labelled proxy value at five, and that the returned record carries the cross-strike-IV label rather than a BKM claim.
**Acceptance.** Four strikes yields `unavailable`, never a number; five or more yields a value whose record carries the label and the regime cell it was conditioned on; no constant smirk coefficient is admissible anywhere in scoring.
**Depends on.** nothing for the proxy itself. The conditioning reads the regime cell the engine already produces (`strategies/regime.py:367` `hmm_filtered_regime`).
**Doc caveat.** Regime- and universe-specific, and its panel claims need the whole option tape, which is beyond this engine's vendors - what is taken is the finding that the coefficient is unstable.

### K1 - A tail number that carries its quality and its uncertainty

**Target.** New module composing `strategies/book_risk.py:9` `simple_var`, `:18` `cvar`, `:59` `portfolio_cvar` with `strategies/data_quality.py:40` `aggregate_quality` and `strategies/conformal.py:103` `quantile_band` / `:143` `rolling_band`: `tail_risk(returns, quality) -> {var, cvar, q_score, uncertainty, band, status}` with `status in {ok, widened, unavailable}`. Consumed by `risk_score`.
**Phase / run mode.** P2 / in-run.
**Behaviour.** One-directional by construction: input quality and estimation uncertainty may widen the band or refuse the estimate, **never narrow it**. The quality score is the paper's weighted composition over flags `data_quality` already computes; the uncertainty score comes from ensemble dispersion (two or more members required), an out-of-distribution distance and a recent breach-drift term.
**Gate.** `enable_tail_risk_layer`, default off.
**Failing-first test.** `tests/test_tail_risk_layer.py::test_quality_only_widens`. Mutation: remove the one-directional guard so a quality-driven adjustment can shrink the band. It asserts that on a fixed return series a monotonically worsening quality input yields a non-decreasing band width and moves `status` from `ok` through `widened` to `unavailable`, and that no input ever narrows it.
**Acceptance.** No input narrows the band; a red quality verdict yields `unavailable` rather than a number; the coverage test (Kupiec and Christoffersen joint conditional-coverage, the instrument R2 uses) lands in the same commit, and the breach rate is reported with the number.
**Depends on.** P0-4 (H11) intervals feed K1's band; P0-1 (H10) is the mechanism by which the tail number reports the window it was computed over; P2 R2's coverage test ships with the tail layer.
**Doc caveat.** The paper's gain is partly a conservative downward shift, its VaR still fails the Kupiec test, and its thresholds were fixed ex ante on six ETFs - report it as a reliability layer, not as a calibrated VaR, and keep the coverage test beside it.

### K5 - Size below Kelly when a costly boundary is near

**Target.** `strategies/size.py`: an optional `boundary_factor(distance_to_limit, horizon, residual)` multiplier on the existing `kelly_fraction` (`:14`) and `position_size_kelly` (`:24`) sizes (and `portfolio.py:452` `kelly_weights`), consumed by the risk governor.
**Phase / run mode.** P2 / in-run.
**Behaviour.** The optimal exposure `f*(d, T, rho)` as a function of log-distance-to-boundary `d`, horizon `T` and residual ratio `rho`, applied only when a hard limit is configured. Near the boundary `f*` is compressed below the no-boundary Kelly fraction; the multiplier **never increases size**.
**Gate.** `enable_boundary_sizing`, default off.
**Failing-first test.** `tests/test_boundary_sizing.py::test_factor_never_increases_size`. Mutation: drop the compression so `f*` can exceed the no-boundary Kelly fraction. It asserts the multiplier is `<= 1.0` for every `(d, T, rho)` and tends to `1.0` as `d` grows.
**Acceptance.** The multiplier is `<= 1.0` everywhere and monotone in proximity to the limit; with no hard limit configured the Kelly size is unchanged bit-for-bit and the output carries `boundary: "unconfigured"`.
**Depends on.** nothing. Its input is the risk-basket drawdown the governor already computes (`strategies/book_risk.py:210` `drawdown_gate`) and the mandate's limits.
**Doc caveat.** A pure model with no empirical calibration - `p`, `a`, `b`, `L`, `S` must come from elsewhere - so it is a shape, not a number, and applying it reduces live size in a way that must be argued.

### K4 - Covariance from characteristics on the short-history path

**Target.** `strategies/covariance_models.py`: `covariance_from_characteristics(char_panel) -> {exposures, covariance, coverage}`, used **only** for names whose own return history is too short and labelled as such in the output; consumed by `hierarchical_risk_parity` / `portfolio_optimizer`.
**Phase / run mode.** P4 / **OFFLINE, deferred**.
**Behaviour.** Point-in-time characteristics (size, valuation, leverage, sector) produce a forward covariance for the equity cross-section, covering the names the engine's coverage rule would otherwise have to leave `unavailable`. The constraint is binding: if adopted it must **replace** the existing estimator on the ragged path, not sit beside `strategies/covariance_models.py:63` `ledoit_wolf_shrink`.
**Gate.** none - the item is deferred pending a training stack, so no gate is registered.
**Failing-first test.** None lands while the item is deferred. The test that gates adoption is `tests/test_covariance_characteristics.py::test_ragged_path_has_one_producer`. Mutation: make the short-history path fall back to `ledoit_wolf_shrink` as well as the characteristics estimator. It asserts that exactly one covariance source answers on the ragged path and that the output carries the short-history label.
**Acceptance.** On a panel containing names under the return-history floor, every such name's covariance comes from the characteristics estimator with its coverage recorded, and no ragged-path name is served by two estimators.
**Depends on.** an offline encoder (a training stack this engine has no stack for). No in-run dependency: per ground rule 8 it may never be called from `prepare_initial_state`, `finalize_run`, or any agent tool.
**Doc caveat.** The principled ragged-panel estimator needs end-to-end neural training and risks becoming a second covariance producer beside `ledoit_wolf_shrink`, which the house rule forbids.

### K6 - Marking-aware VaR (recorded only)

**Target.** None.
**Phase / run mode.** None / recorded only.
**Behaviour.** What was found: a sequential-VaR recalibration for standardized option books that is aware of how the book is marked, so the VaR's validity is tied to the mark convention rather than to the book's notional - a VaR that is right under one mark is not right under another.
**Gate.** none - recorded, not built.
**Failing-first test.** None - nothing is built, so no test guards it.
**Acceptance.** Not applicable: the deliverable is this record. It becomes a build only if option positions ever enter the mandate, which is a mandate decision rather than a survey one.
**Depends on.** nothing.
**Doc caveat.** Its data requirement (the option tape) exceeds this engine's vendors, and it is relevant only if option positions ever enter the mandate.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| K2 | four drawdown expectations + `T^(H-1/2)` rescaling | `strategies/book_risk.py` | P1 | in-run | `enable_drawdown_envelope` |
| K3 | cross-strike risk-neutral skewness proxy + regime conditioning | `strategies/options_surface.py` | P1 | in-run | `enable_rn_skew_proxy` |
| K1 | quality- and uncertainty-adjusted tail number | new module composing `strategies/book_risk.py`, `strategies/data_quality.py`, `strategies/conformal.py` | P2 | in-run | `enable_tail_risk_layer` |
| K5 | absorbing-boundary size multiplier | `strategies/size.py` | P2 | in-run | `enable_boundary_sizing` |
| K4 | covariance from characteristics on the short-history path | `strategies/covariance_models.py` | P4 | offline, deferred | none (deferred) |
| K6 | marking-aware VaR | none | none | recorded only | none (recorded) |

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_drawdown_envelope` | K2 | `strategies/book_risk.py` `drawdown_envelope`, read by the drawdown governor and `backtest_evaluation` | off |
| `enable_rn_skew_proxy` | K3 | `strategies/options_surface.py` cross-strike proxy into `risk_score` | off |
| `enable_tail_risk_layer` | K1 | new tail module `tail_risk` into `risk_score` | off |
| `enable_boundary_sizing` | K5 | `strategies/size.py` `boundary_factor`, read by the risk governor | off |

K4 and K6 register no gate: K4 is deferred and K6 is recorded. The four new gates each need the six
registration points listed in [`README.md`](README.md).

## 4. Dependencies

```text
K2  -> nothing (independently landable); Hurst from mean_reversion.hurst_exponent:112
K2  <- V2 (memory_parameter is the complement; both read the same persistence)
K3  -> nothing; the conditioning reads the regime cell from regime.py:367 hmm_filtered_regime
K1  -> P0-4 (H11) intervals -> K1's band; P0-1 (H10) -> the window the tail number reports
K1  -> P2 R2 (the coverage test ships with the tail layer)
K5  -> nothing; input is the drawdown from book_risk.py:210 drawdown_gate and the mandate's limits
K4  -> an offline encoder (does not exist) -> then the ragged path, replacing ledoit_wolf_shrink
K6  -> nothing (recorded)
H6  -> every finding this theme publishes must be able to be INCONCLUSIVE
```

K2, K3, K1 and K5 are in-run and cheap (seconds or less) against the four-symbol run budget; K4 is
offline by construction and is the only member of this slice that ground rule 8 constrains. K1 and
K5 are P2 and may not land before P1's producers exist; K2 and K3 are independently landable.

## 5. Decisions requested (owner)

1. **Whether K1 + K2 land as a first pass, and whether the mandate permits the `T^(H-1/2)` rescaling to reach the drawdown governor.** This is the theme's own decision line. The plan sequences K2 in P1 and K1 in P2 because K1's band is built on P0-4's intervals; if the rescaling is not authorised, K2 lands as a report-only read and `drawdown_gate` keeps the square-root-of-time convention.
2. **Whether K5 is authorised to reduce live position sizes.** The multiplier only ever reduces size, so its cost is opportunity rather than risk - and the paper is a shape with no empirical calibration, which makes the reduction an argument, not a default.
3. **Whether a training stack is ever stood up for K4.** If it is, the characteristics estimator replaces the ragged-path estimator; if not, the ragged path stays unserved and its names stay `unavailable`, which is the honest current answer.
4. **Whether a scored skew or spread read may depend on the regime cell.** That is a behaviour change to an existing `risk_score` component rather than a new signal, so it is the owner's call, not the implementer's.

## 6. Honest limits

1. **K1's gain is partly conservatism.** The paper's VaR still fails the Kupiec test after the quality layer; widening a band is easy and being right is not, so the coverage test is the deliverable and the number is not.
2. **K2's four expectations rest on a stationary-Sharpe Monte Carlo.** Sharpe-estimation uncertainty is carried, not solved, and `T^(H-1/2)` is a rescaling of an existing number rather than a new risk measure - it corrects a scaling habit, it does not detect anything.
3. **K3 is a negative result about a predictor, not a new predictor.** Its practical value is that the engine should stop treating a skew coefficient as stable, and its panel claims need an option tape this engine's vendors do not supply.
4. **K5 is uncalibrated by its authors' own admission.** It is a shape whose parameters must come from elsewhere, and applying it reduces size in a way that must be argued.
5. **K4 is deferred, so the coverage problem it addresses stays open.** Until a training stack exists, a name with forty bars still contributes a noisy row or is `unavailable`; the deferred item is a plan to fix that, not a fix.
6. **K6 is recorded, not built, and nothing in this theme changes `COMPOSITE_ENGINES`.** The items feed components `risk_score` already declares; no item adds an engine, and no item is evidence of an edge.
