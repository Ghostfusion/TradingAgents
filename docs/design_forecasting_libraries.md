# Design: The Forecasting Layer — Library Landscape, Admission Rule, and the ForecastContract

**Status:** DESIGN — the *admission rule and the contract* are proposed; **no library is admitted and no
producer is built by this document**. Three items are `WORK` in the companion plan.
**Version:** 1.0
**Date:** 2026-10-03
**Scope:** The question *"should this engine adopt a time-series forecasting library stack?"* — the
library landscape, the evidence on what is actually forecastable in equities, what this repo already
owns, and the one artifact worth adopting: a **declaration**, not a producer.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Owners (the docs this one must not double-own):**
`docs/paper_survey_26/design_vol_surface_and_vrp.md` (volatility + surface), the same folder's
`design_regime_estimation_hardening.md` (regime), `design_cross_section_and_allocation.md`
(cross-section + ranks), `design_risk_tail_and_coverage.md` (tails, drawdown, VaR),
`design_research_honesty_gates.md` (the evaluation gates).
**Plan:** [`implementation_plan_forecasting_libraries.md`](implementation_plan_forecasting_libraries.md) — the item-level plan (v1.0, PLAN).
**Rule-4 impact:** none. No tool, gate, config key, report key or screener column is added by this
document.

---

## 1. Executive summary

An external proposal recommended adopting a forecasting stack for this engine — a 40-library survey
whose "starting recommendation" is
**`StatsForecast + MLForecast + arch + statsmodels + hmmlearn + ruptures`**, plus a `ForecastContext`
object carrying `return_forecast`, `volatility_forecast`, `probability`, `prediction_interval` and
`regime_forecast` keyed by horizon.

Read against the code and the corpus already in this repo, the recommendation splits cleanly:

| Half of the recommendation | Verdict |
|---|---|
| **The model families** (GARCH/ARCH, HAR + long memory, HMM/Markov regime, conformal intervals, jump-robust realized measures) | **Already owned and largely already built in-house.** Five of the six themes the proposal names have a shipped, gated, tested producer. Adopting a library here would create a **second producer** of a number this repo already produces — invariant 8 forbids it. |
| **The `ForecastContext` shape** (horizons, intervals, probabilities, provenance) | **Worth adopting — as a *declaration*, not a producer.** This is the proposal's genuinely useful contribution and the reason this doc exists. |
| **As a dependency** (`StatsForecast`, `MLForecast`, `arch`, …) | **Not admitted.** See §7 — for the one open item (V1's forecast pool, currently blocked) the verdict is *conditional*, and even there the mechanism is the offline refit, not a live dependency. |

The one thing this document *builds* is a rule: **a forecasting dependency is admitted only when a
declared producer needs it, and never when it would restate a number the engine already computes.**

And the proposal's own architecture advice turns out to be the repo's existing architecture — it says
*"I wouldn't create one giant ForecastScore"* and *"your existing engines remain independent"*; that is
`docs/scores/README.md` §2.1 invariants 8–18 verbatim, reached from the outside.

### The corpus's own answer, already recorded here

`docs/design_fin_paper_survey_26.md` §3 states the finding this doc is bound by:

> **forecasts exist, but in volatility** — structure, rank, volatility and covariance are estimable and
> stable; **the level of the return is the part that resists.**

The proposal's `return_forecast` field is therefore the one member of its `ForecastContext` this engine
must **refuse to populate with a number**, and the corpus is unusually explicit about why (§4).

---

## 2. The recommendation under evaluation

Restated neutrally so the verdict can be checked against it. The proposal:

1. broadens an earlier list to 40 libraries across seven problem types (return, price, volume,
   volatility, regime, probabilistic, multivariate);
2. names six functional groups and a two-tier stack — Tier 1 *integrate* (`StatsForecast`,
   `MLForecast`, `arch`, `statsmodels`, `hmmlearn`, `ruptures`), Tier 2 *research* (`NeuralForecast`,
   `Darts`, `PyMC`, `GluonTS`, `PyTorch Forecasting`, `AutoGluon-TimeSeries`), Tier 3 *foundation
   models* (`Chronos`, `TimesFM`, `Moirai`, `Lag-Llama`, `MOMENT`), Tier 4 *probably unnecessary*
   (`Prophet`, `PyAF`, `Greykite`, `Kats`, `PyFlux`);
3. recommends against one giant `ForecastScore`, and for a `ForecastContext` that preserves the
   forecast information beside the score engines;
4. notes that `StatsForecast` "already has probabilistic forecasting and GARCH/ARCH support, so you may
   not actually need three separate dependencies";
5. ends with a **six-library** starting recommendation.

Claims (1), (4) and (5) are checkable and are checked in §3. Claim (3) is architectural and is checked
in §5 against the repo's invariant 8.

---

## 3. Verified library facts

Read from each project's current `pyproject.toml` / `LICENSE` / model source on 2026-10-03, not from
memory. **Four of the proposal's framing assumptions are wrong or incomplete**, and two of them matter
for this engine.

| Library | Licence (verified) | Core runtime deps (verified) | Build | Note |
|---|---|---|---|---|
| `statsforecast` 2.1.1 | **Apache-2.0** ✅ | `coreforecast`, `numpy`, `pandas<3.0.0`, `scipy`, **`statsmodels>=0.14.5`**, `fugue`, `utilsforecast`, `threadpoolctl`, `cloudpickle`, `tqdm` | **compiled** (`scikit-build-core` + `pybind11`) | **`statsmodels` is a hard dep of `statsforecast`.** **`numba` is not** — the proposal's mental model of the Nixtla stack is out of date. |
| `mlforecast` 1.1.0 | **Apache-2.0** ✅ | `coreforecast`, **`scikit-learn`**, `optuna`, `narwhals`, `fsspec`, `pandas<3.0` | pure-python | **`LightGBM`/`XGBoost` are NOT core deps** — they appear only under the `dask`/`ray`/`spark` extras. The proposal's "→ LightGBM/XGBoost" arrow needs an extra. |
| `arch` | **NCSA** — *not* MIT/BSD/Apache | `numpy`, `pandas`, `scipy`, `statsmodels`, `packaging` | **compiled** (`meson-python` + Cython) | The proposal groups `arch` with permissive-licensed peers; NCSA is OSI-approved and permissive but it is a **distinct licence with a distinct attribution clause** — a legal review item, not a footnote. |
| `qlib` | **MIT** ✅ | (platform) | pure-python | Already has a design + plan pair here — `docs/design_qlib_integration.md`, `docs/implementation_qlib_integration.md`. |
| `finrl` | **MIT** ✅ | (platform) | pure-python | Already has a design + plan pair here — `docs/design_finrl_integration.md`, `docs/implementation_plan_finrl.md`. |
| `hmmlearn`, `ruptures`, `statsmodels`, `darts`, `neuralforecast`, `pymc`, foundation models | **not verified in this pass** | — | mixed | Recorded as **unadmitted until verified**. The foundation-model row carries a second trap: *code* licence and *checkpoint* licence are separate instruments and can differ. `[INFERENCE]` |

### 3.1 Two facts the proposal gets right

**`StatsForecast` really does ship `GARCH` and `ARCH` models.** Verified in
`python/statsforecast/models.py` — `class GARCH` and `class ARCH(GARCH)`, documented as their own group
("Suited for modeling time series that exhibit non-constant volatility over time").

Two details the proposal does not mention, and both are the interesting part for this repo:

- The GARCH implementation is **in-house** — `fit()` calls `garch_model(y, p, q)` and
  `predict()` calls `garch_forecast(...)`. It does **not** delegate to `arch`, which is why `arch` is
  absent from its dependency list. The proposal implies the opposite grouping.
- `predict()` returns a dict of **`{"mean", "sigma2"}`** — i.e. it hands back the *conditional variance
  forecast*, which is precisely the quantity this engine's risk path consumes. Intervals are
  `quantile × sqrt(sigma2)` (a Gaussian assumption) unless `prediction_intervals=ConformalIntervals(...)`
  is passed, in which case they are conformal.

**The proposal's "cannot beat the unconditional mean" instinct is correct and is the corpus's central
result** — see §4.

### 3.2 The proposal's three-groups framing is the wrong axis here

It groups libraries by *problem type* (return/price/volume/volatility/regime/probabilistic). This engine
groups by **who owns the number**. The same library can be correct under the first axis and forbidden
under the second — which is exactly what happens to `statsforecast` and `arch` in §7.

---

## 4. What is actually forecastable: the evidence

Four primary sources, all read in this pass.

### 4.1 The return level is the part that resists

**Hjalmarsson (2006), Federal Reserve IFDP 855.** *"Using Monte Carlo simulations, I show that typical
out-of-sample forecast exercises for stock returns are unlikely to produce any evidence of
predictability, even when there is in fact predictability and the correct model is estimated."*

The mechanism is not a lack of structure — it is estimation noise against a small coefficient. His
T=600-monthly, c=−20 simulations find the conditional forecast only beats the constant-return
(β=0) benchmark **on average** once the true β exceeds ~0.015, while the Diebold-Mariano test's
rejection rate at β=0.015 is 5.8%. His conclusion is the design instruction:

> *"in order to produce good forecasts when the slope coefficient in a linear regression is small, you
> are often better off setting it equal to zero, rather than using a noisy estimate of it."*

**Goyal, Welch & Zafirov (2021 SFI WP 21-85; RFS 2024, 37(11) 3490).** The 2022 re-examination tested
the original 17 predictors plus 29 variables from 26 post-2008 papers, samples ending 2021:
*"Much of the extant literature seems obsolete, with a majority of variables no longer having empirical
support even in-sample. A small number still perform reasonably well."*

Read together: a `return_forecast` number produced by fitting a model to a single name's price history
is not a weak signal — **it is a statistically unsupported one**, and it would enter this engine as a
number indistinguishable from a measured one.

### 4.2 The volatility level is forecastable, and HAR is the baseline to beat

**Corsi (2009), *J. Financial Econometrics* 7(2):174–196.** The HAR-RV model:

```
RV_{t+1} = c + b_d * RV_t + b_w * RV_w + b_m * RV_m
```

His abstract records the finding this engine's design already assumes: *"direct time series modeling of
realized volatility strongly outperforms, in terms of out-of-sample forecasting, the popular GARCH and
stochastic volatility models"* — with S&P 500 coefficients b_d=0.372, b_w=0.343, b_m=0.224. The model
reproduces long memory, fat tails and self-similarity **without** being a long-memory process, which is
why a three-term regression is the correct benchmark rather than a null hypothesis.

**Leushuis & Petkov (2026), *Financial Innovation* 12:14** (open access, DOI 10.1186/s40854-025-00809-5).
A review of 32 realized-volatility models from 41 papers, 2000–H1 2024. Its findings: ARMA/HAR remain the
**linear baselines**, the best-performing architecture is a CNN-LSTM hybrid, and the paper enumerates the
six empirical properties any model must address — autocorrelation/clustering, asymmetry, leptokurtosis,
mean reversion, seasonality, co-movement. It **deliberately excludes GARCH** as a latent-volatility
model. The honest reading for this engine: the deep-learning increment over HAR is real but modest, and
the review's own sibling literature flags the risk — a 2025 paper in the same journal's related list is
titled *"Examining Challenges in Implied Volatility Forecasting: A Critical Review of Data Leakage and
Feature Engineering combined with High-Complexity Models."*

### 4.3 The engine's own survey reached the same conclusion first

`docs/design_fin_paper_survey_26.md` §3 (2026-09-23), on the 2026 corpus:

| Paper | Finding |
|---|---|
| 2607.27461 | a name's 10-decile **volatility-rank** transition matrix is forecastable with multi-step memory; its **return-rank** matrix is close to unforecastable. Out-of-sample monthly log-likelihood gain **0.108 vs 0.007**; rank MAE 2.05→1.78 with covariates for volatility, stuck at 2.5 for return. |
| 2602.07841 | a **nontrivial upper bound on the out-of-sample R²** in return forecasting — a *ceiling to check claims against*, not a model to fit. |

So the boundary is already drawn in this repo, by the same evidence class, and the new material here
does not move it.

### 4.4 What follows for a `ForecastContext`

1. **Volatility, covariance, rank and regime are forecastable** → these keys may carry numbers, from the
   producers that already own them.
2. **The return level is not** → `return_forecast` must be `unavailable` with a named reason, not a
   fitted number. A numeric return forecast here would be a **new authoritative producer** of a quantity
   the engine has already decided not to produce, and `Strategies/` + `CHANGELOG.md` record that
   decision as taken: the sector-rotation spec's *"expected return/risk"* construction is **"Rejected
   outright (`evaluate.py` + CPCV/PBO is the repo's method)"**.
3. **Any forecast that does carry a number must travel with its interval and its realized coverage** —
   the house rule ("coverage travels with the number") plus the corpus's H11 axis, both already built.

---

## 5. What this repo already owns — and why a library would be a second producer

### 5.1 The eight invariants

`docs/MASTER_DESIGN.md` §2, invariant 8: **one producer per number**. `docs/scores/README.md` §2.1
invariants 8–18 restate it as *"no derived quantity may have two independent authoritative producers."*

A "forecasting layer" is, by construction, a second place a number is computed. It is therefore either
(a) the *declared* producer for numbers nothing else produces, or (b) a duplicate. §5.2 shows it is
almost entirely (b).

### 5.2 The owners, verified in the tree

| Theme the proposal names | Who already owns it here | State |
|---|---|---|
| GARCH / ARCH / range / semivariance vol estimators | `strategies/volatility_models.py:68` `semivariance`, `:155` `parkinson_vol`, `:185` `garman_klass_vol`, `:288` `yang_zhang_vol`, `:332` `yang_zhang_vol_series`, `:397` `ewma_vol`, `:438` `garch11_fit` (MLE, with the `:53` `_IGARCH_AB` breakdown guard) | **built** |
| Jump-robust realized measures (bipower, quarticity, jump share) | `strategies/volatility_models.py` `bipower_proxy` / `quarticity_proxy`, behind `enable_jump_robust_proxies` | **built** — V6 |
| HAR-family realized-variance forecast + semiparametric memory parameter | `strategies/long_memory.py:146` `memory_parameter` (GPH + local Whittle), `:236` `rv_forecast`, `:58` `long_memory_enabled`; consumed by `strategies/mean_reversion.py::memory_profile` | **built** — V2, `gate_registry.md:273` "wired", `test_long_memory.py` |
| HMM / Markov regime | `strategies/regime.py:545` `hmm_filtered_regime` — a real Baum-Welch fit (`_hmm_em:355`) with **causal filtered** posteriors, plus `:781` `regime_conditional_var`; `hmm_regime:743` delegates so there is ONE HMM producer. Behind `enable_hmm_heavy_tails` | **built** — R2 |
| Change-point / structure break | `strategies/regime.py:1013` `cusum`, `:1327` `bocpd`, `:1494` `spectral_change_read` (behind `enable_spectral_null_band`); `strategies/complexity.py` | **built** |
| Kalman / state-space smoothing | `strategies/statistical_kalman.py:42` `kalman_spread` | **built** |
| Conformal / probabilistic intervals | `strategies/conformal.py` `quantile_band` (CQR), `rolling_band`, `iid_interval`, `block_bootstrap_interval`, `information_gap`, `adf_t`, `block_length`; `enable_bootstrap_intervals` | **built** — H11 |
| Option-implied / risk-neutral reads | `strategies/options_surface.py:25` `iv_skew`, `:201` `surface_shape`, `:227` `term_structure_slope`, `:294` `pre_event_iv_lift`, `:489` `rn_skew_proxy`; `strategies/rnd_recovery.py` behind `enable_rnd_recovery` | **built** — V3, V4, K3 |
| Covariance, eigenstructure, rotation | `strategies/covariance_models.py:132` `ewma_covariance`, `:85` `ledoit_wolf_shrink`; `strategies/eigen_rotation.py` behind `enable_eigen_rotation` | **built** — V5 |
| Tail / drawdown / VaR-CVaR | `strategies/tail_risk.py` (`enable_tail_risk_layer`), `strategies/book_risk.py::drawdown_envelope`, `strategies/triadic_stress.py` | **built** — K1, K2 |
| Rank/selection + evaluation harness | `strategies/signal_analysis.py:64` `rank_ic`, `strategies/prediction_ledger.py`, `strategies/evaluate.py`, `strategies/trial_ledger.py`, `strategies/calibration.py` | **built** |

### 5.3 The proposal's Tier 1, item by item

- **`arch`** → `garch11_fit` exists, is MLE, and carries an explicit IGARCH guard. `arch` would be a
  second GARCH producer. **Not admitted.**
- **`statsmodels`** → its Markov-switching and econometric surface is largely covered by
  `regime.py` + `covariance_models.py` + the in-house regressions. It is also a *hard dependency of
  `statsforecast`*, so it arrives transitively if `statsforecast` is ever admitted — no separate case for
  adding it directly.
- **`hmmlearn`** → `regime.py::hmm_filtered_regime` exists **and is wired into `book_risk`'s VaR**. A
  second HMM is a second regime label — the most dangerous kind of duplicate, because two regime labels
  that disagree are indistinguishable from a regime change. **Not admitted.**
- **`ruptures`** → `spectral_change_read` + `complexity.py` cover the declared change-point surface.
- **`StatsForecast`** → its genuinely distinct value here is the **forecast *pool* with online scoring
  and regime-similarity routing** — which is *already designed*, as **V1**
  (`design_vol_surface_and_vrp.md` §V1), and **blocked on a vendor state vector** (`VXV` + a HY-spread
  series), not on a library.
- **`MLForecast`** → the ML members of that same V1 pool. Same owner, same block.

**Six of six Tier-1 libraries are either already in-house or already owned by a blocked design item.**

### 5.4 The one place a library is plausibly correct

V1's pool names members `HAR-RV, GARCH(1,1)-t, FIGARCH(1,1)-t, GRU, XGBoost` — two econometric members
(this repo can do) and three learned ones (it cannot, today). **This is a genuine capability gap**, and
it is the *only* place in the proposal where a dependency buys something the engine does not have.

Its own plan already states the correct shape: *"P4 / offline-ish … the refit is an offline artefact"*
and ground rule 8 — *"never called from `prepare_initial_state`, `finalize_run`, or any agent tool."*
So even for the admitted case the artifact is an **offline refit producing a versioned artefact**, not a
live library call on the decision path. That is the mechanism §7's admission rule encodes.

---

## 6. The artifact worth adopting: a `ForecastContract`, not a producer

The proposal's `ForecastContext` is right in shape and wrong in one field. Adopted here as a
**declaration** — a schema every existing producer already satisfies or explicitly refuses — it buys
three things the repo does not have: a single place that says *which* forecast numbers exist, a
machine-checkable "no second producer" rule, and a refusal that is as visible as a number.

### 6.1 The shape

```
ForecastRecord                     # ONE producer per key, per horizon, declared once
├── key            : str           # e.g. "rv.d1", "vol_rank.d22", "regime.p_stress"
├── producer       : str           # "strategies/long_memory.py::rv_forecast"  <- the authority
├── gate           : str | None    # "enable_long_memory" | None (always-on)
├── horizon        : int           # trading days, or 0 for a state read (not a forecast)
├── unit           : str           # "annualized_vol" | "probability" | "rank_decile" | ...
├── value          : float | None  # None  <=>  status != "ok"   (NEVER 0.0 as a placeholder)
├── status         : str           # "ok" | "unavailable" | "declined"
├── unavailable    : str | None    # the NAMED reason when status != "ok"
└── interval       : dict | None   # {low, high, nominal, realized_coverage, block, basis}
```

### 6.2 The five rules

1. **`value is None` iff `status != "ok"`.** A forecast that cannot be made is `unavailable` with a
   reason; it is never `0.0`, and it is never a shrunk-to-zero pseudo-number (`NA != 0`, the existing
   `docs/scores/ScoreContextContract.md` §NA rule, restated for forecasts).
2. **One producer per `(key, horizon)`.** Declared in the registry, asserted by a test. This is
   invariant 8 made checkable for forecasts specifically.
3. **A `declined` key is a first-class status.** `return_forecast` ships **`status="declined"`** with the
   §4 reason attached — so the absence is discoverable, cited and deliberate rather than an empty field a
   future contributor helpfully fills in.
4. **An interval travels with the number, and so does its *realized* coverage.** `conformal.py`'s own
   module comment states the governing lesson — *"read the realized coverage, never the nominal level
   alone"* — and `information_gap` already measures whether a band is wide because it knows something.
5. **Provenance is mandatory.** `as_of`, the window, and whether the window was **padded** — the corpus's
   temporal-coverage-bias result (a padded window is biased in a known direction, not merely
   low-confidence) makes `padded: bool` a required field, not a nicety.

### 6.3 What the contract explicitly does NOT do

- It is **not** a new module that computes anything. It is a declaration plus a registry plus a test.
- It does **not** create a `ForecastScore` engine, and it does not add a member to
  `COMPOSITE_ENGINES` (which stays `(fundamental, technical, regime, risk)`).
- It does **not** put a return forecast on the decision path. `strategies/portfolio.py:452`
  `kelly_weights`' docstring already names the correct boundary — *"the excess returns must be declared
  by the caller (a forecast source)"* — i.e. **a forecast is a declared input, never an internal
  authority**. The contract makes that declaration explicit instead of implicit.

---

## 7. Per-library verdict

Admission has three outcomes. **`INTEGRATE`** = becomes a declared dependency this pass.
**`CONDITIONAL`** = admitted only when a named `WORK` item unblocks, via the offline-refit mechanism.
**`REJECT`** = recorded with a reason, so it is not silently re-proposed (the same convention
`design_vol_surface_and_vrp.md` uses for V7/V8).

| Library | Verdict | Reason |
|---|---|---|
| `statsforecast` | **CONDITIONAL** (offline only) | Its distinct artifact is V1's forecast pool, which is already designed and blocked on a **vendor state vector**, not a library. If V1 unblocks, `statsforecast` may supply the econometric members **as an offline refit** (ground rule 8). It brings `statsmodels` transitively. |
| `mlforecast` | **CONDITIONAL** (offline only) | The learned members of that same V1 pool. Note it requires `scikit-learn` **and `optuna`** as core deps. |
| `arch` | **REJECT** | `garch11_fit` already produces the conditional variance, with an IGARCH guard and a test. A second GARCH is a second producer. (`arch`'s NCSA licence would also be the first non-MIT/BSD/Apache dep here.) |
| `statsmodels` | **REJECT (direct)** | Arrives transitively with `statsforecast` if that is ever admitted; adding it directly duplicates `regime`/`covariance_models` surface. |
| `hmmlearn` | **REJECT** | `regime.hmm_filtered_regime` exists and is wired into `book_risk`'s VaR. A second regime label is the highest-risk duplicate in this table. |
| `ruptures` | **REJECT** | `spectral_change_read` + `complexity.py` cover the declared change-point surface. |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | **REJECT** | Research-labouratory tools with no declared consumer; each is a large, compiled-or-torch dependency. Reopen only with a hypothesis that names the producer. |
| `pymc`, `pyro`, `tensorflow-probability` | **REJECT** | The probabilistic-programming surface has no declared consumer; `conformal.py` already supplies calibrated intervals. |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | **REJECT (recorded, not adopted)** | Foundation models: code and **checkpoint** licences differ, inference needs weights and GPU, and the corpus's own directional-accuracy paper (2607.12248) is a warning about exactly this class. Recorded so the class is not re-proposed as "free accuracy". |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | **REJECT (Tier 4, agreed)** | The proposal already declines these; this doc agrees and records the agreement. |
| `qlib`, `finrl` | **ALREADY OWNED** | Both have existing design+plan pairs in `docs/`; nothing is added here. |

**Net dependency change this pass: none.** The admission rule is written so that a future change is a
reviewable declaration rather than a `pip install`.

---

## 8. Non-goals — what this document does not own

- **The volatility forecast pool (V1)** — owned by `design_vol_surface_and_vrp.md` §V1. This doc only
  states its library-admission path.
- **The memory parameter and HAR forecast (V2)** — owned by the same doc; **already built** as
  `strategies/long_memory.py`.
- **Regime estimation (R1–R9)**, **tails/drawdown (K1–K6)**, **cross-section ranks (X1–X8)**,
  **evaluation gates (H1–H11)** — each owned by its own `docs/paper_survey_26/` pair. This doc cites
  them and must not restate them.
- **The expected-return / scoring construction** — `COMPOSITE_ENGINES` and the score set are owned by
  `docs/scores/README.md`. Nothing here changes a score.
- **`_float_tokens` / report verification** — unrelated ownership.

---

## 9. Open owner decisions

1. **Is `return_forecast` shipped as `declined`, or omitted entirely?** This doc recommends
   **`declined` with a cited reason** (§6.2 rule 3) — a visible refusal is harder to silently reverse than
   an absent key. It is one field in a declaration and is the owner's call.
2. **Does the admission rule permit an NCSA-licensed dependency?** `arch` is REJECT on duplication
   grounds regardless, but the *policy* question is separate and will recur: this repo's current
   dependency set is MIT/BSD/Apache. Recommend: **permissive-OSI only, NCSA requires an explicit
   sentence** — so it is decided once, not per library.
3. **V1's vendor unblock** — `VXV` and a HY-spread series are not confirmed live vendor calls. That is
   V1's blocker and an owner/vendor decision, recorded in `design_vol_surface_and_vrp.md` §5, and it is
   the *only* thing standing between this doc's `CONDITIONAL` verdicts and a real dependency.

---

## 10. Honest limits

1. **Four library licences were not verified from source in this pass** (`hmmlearn`, `ruptures`,
   `statsmodels`, the foundation models). They are marked unadmitted rather than assumed permissive.
2. **`statsforecast`'s `GARCH` was read in source but not executed.** The claim that it emits
   `{"mean", "sigma2"}` is a read of `predict()`'s return dict, not an observed run. `[INFERENCE]` for
   the *behaviour*, fact for the *code*.
3. **The CNN-LSTM-over-HAR result in Leushuis & Petkov is a literature aggregate**, not a measurement on
   this engine's data; their related literature is explicit that the deep-learning increment is fragile
   under leakage.
4. **No item here is backtested** — this document authorises no build. Its claims are about *ownership*
   and *evidence*, both of which are checkable in the tree today.
5. **This doc's own verdict could be wrong on V1.** If V1 unblocks and its learned members cannot be
   expressed with the in-house regressions, `statsforecast`/`mlforecast` may be the cheapest correct
   answer — which is why they are `CONDITIONAL` and not `REJECT`, and why the admission rule exists
   rather than a ban.

---

## References

- Hjalmarsson, E. (2006). *Should We Expect Significant Out-of-Sample Results when Predicting Stock
  Returns?* Federal Reserve Board IFDP 855. <https://www.federalreserve.gov/pubs/ifdp/2006/855/ifdp855.pdf>
- Goyal, A., Welch, I., & Zafirov, A. (2021/2024). *A Comprehensive 2022 Look at the Empirical
  Performance of Equity Premium Prediction II.* SFI WP 21-85; *Review of Financial Studies* 37(11) 3490.
  <https://www.sfi.ch/en/publications/n-21-85-a-comprehensive-look-at-the-empirical-performance-of-equity-premium-prediction-ii>
- Corsi, F. (2009). *A Simple Approximate Long-Memory Model of Realized Volatility.*
  *J. Financial Econometrics* 7(2):174–196. <https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf>
- Leushuis, R. M., & Petkov, N. (2026). *Advances in forecasting realized volatility: a review of
  methodologies.* *Financial Innovation* 12:14. DOI 10.1186/s40854-025-00809-5.
- Nixtla. `statsforecast` / `mlforecast` `pyproject.toml` and `python/statsforecast/models.py` (main).
- Sheppard, K. `arch` `pyproject.toml` (main) — licence NCSA.
- Microsoft `qlib` LICENSE (MIT); AI4Finance `FinRL` LICENSE (MIT).
- Internal: `docs/design_fin_paper_survey_26.md` §3, §5; `docs/paper_survey_26/design_vol_surface_and_vrp.md`
  §2, §V1, §V2, §5; `docs/paper_survey_26/design_cross_section_and_allocation.md` §1;
  `docs/MASTER_DESIGN.md` §2 (invariant 8); `docs/scores/README.md` §2.1; `CHANGELOG.md`
  (the *"Rejected outright"* entry).
