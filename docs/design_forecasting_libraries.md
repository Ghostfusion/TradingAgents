# Design: The Forecasting Layer — Ownership, Admission Rule, and the ForecastContract

**Status:** DESIGN — the *admission invariant and the contract* are proposed; **no library is admitted and
no producer is built by this document**. Seven items are `WORK` in the companion plan.
**Version:** 1.1 (revises v1.0, 2026-10-03)
**Date:** 2026-10-03
**Scope:** Whether this engine should adopt a third-party time-series forecasting stack, what a forecast
*is* in this repository, and the contract a forecast number must satisfy to be admissible evidence.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Owners (docs this one must not double-own):** `docs/paper_survey_26/design_vol_surface_and_vrp.md`
(volatility, surface), `design_regime_estimation_hardening.md` (regime),
`design_cross_section_and_allocation.md` (cross-section, ranks), `design_risk_tail_and_coverage.md`
(tails, drawdown, VaR), `design_research_honesty_gates.md` (H1–H11, the evaluation gates).
**Plan:** [`implementation_plan_forecasting_libraries.md`](implementation_plan_forecasting_libraries.md) (v1.1, PLAN).
**Rule-4 impact:** none. No tool, gate, config key, report key or screener column changes.

**Revision note (v1.1).** Rewritten in response to an external review. The substantive corrections:
*v1.0 turned "no authoritative return forecast is admitted" into "returns are not forecastable"* — those
are different claims and only the first is defensible (§5.1); *v1.0 required `realized_coverage` in the
forecast interval*, which cannot exist at forecast time — production and evaluation metadata are now
separated (§7.1); *v1.0 admitted `horizon = 0` state reads into the forecast namespace*, which is
namespace leakage (§7.2 rule 6); and *v1.0's admission rule was capability-based*, which lets a missing
package justify itself (§3). §12 records the disposition of every review point.

---

## 1. Executive summary

This document evaluates a proposal to add a forecasting stack (`StatsForecast + MLForecast + arch +
statsmodels + hmmlearn + ruptures`, plus a horizon-keyed `ForecastContext`) to this repository.

**The headline finding is not "we don't need forecasting libraries."** It is:

> **This engine already owns the forecasting *methods*. What it does not have is a general-purpose
> learned forecast-*pool* producer — and even that is already designed (V1), blocked on a vendor data
> dependency rather than on a library.**

| Half of the proposal | Verdict |
|---|---|
| **Model families** — GARCH/ARCH, HAR + long memory, HMM regime, change-point, conformal intervals, covariance, RND recovery, eigenspace rotation | **Already owned, and five of six already shipped.** A library here would be a **second producer** of a number this repo already computes — forbidden by invariant 8. |
| **The `ForecastContext` shape** | **Worth adopting — as a declaration, not a producer.** The contract in §7 is the artifact this document exists to specify. |
| **The dependencies** | **Not admitted.** `statsforecast`/`mlforecast` are `CONDITIONAL`; the rest are rejected with categorized reasons (§9). **Net dependency change: zero.** |

### The core principle

> **A forecasting library is not a forecasting capability, and a forecast is not an authoritative
> research fact.** A dependency is admitted only to support a *declared producer* with a defined target,
> definition and consumer; a forecast becomes *admissible evidence* only after it satisfies this
> repository's ownership, provenance, out-of-sample evaluation and research-honesty requirements.

### The boundary this document is bound by

`docs/design_fin_paper_survey_26.md` §3, already recorded in-house:

> **forecasts exist, but in volatility** — structure, rank, volatility and covariance are estimable and
> stable; **the level of the return is the part that resists.**

---

## 2. What a forecast is here — and is not

The single most likely future defect this design must prevent:

```
Forecast = +2.3%  →  ForecastScore = 73  →  BUY
```

That recreates exactly the problem the score architecture exists to avoid. The layers are distinct:

| Layer | Question it answers | Owner |
|---|---|---|
| **Forecast** | *What does a model estimate will happen?* | a declared producer (§7), recorded in the prediction ledger |
| **Score** | *How does the engine rate the current evidence?* | `docs/scores/README.md`, the engines |
| **Signal** | *What actionable research implication follows?* | `strategies/signal_action.py` |
| **Decision** | *What does the research process conclude?* | the LLM adjudication layer + `decision_packet` |

**Forecasting is not scoring.** A forecast never becomes a score by adjacency, and no forecast enters
`COMPOSITE_ENGINES` (which stays `(fundamental, technical, regime, risk)`).

The repository already states the correct boundary for the one place a forecast is consumed as an input:
`strategies/portfolio.py:452` `kelly_weights` — *"the excess returns must be declared by the caller (**a
forecast source**)"*. A forecast is a **declared input**, never an internal authority.

---

## 3. The Forecasting Dependency Admission Invariant

v1.0 buried this in §1 as a conclusion. It is the primary principle, so it is stated as an invariant in
the same spirit as `MASTER_DESIGN.md` §2 and `docs/scores/README.md` §2.1.

> **FD-1. A forecasting dependency may be admitted only when all five hold:**
>
> 1. a **declared forecast producer** requires a capability not available from any existing
>    authoritative producer;
> 2. that producer has a **named consumer** (a tool, an engine, a report row, or a sizing input);
> 3. the **target is fully defined** — target name, measurement definition, unit, frequency and horizon
>    (§7.1, §7.3);
> 4. the producer **passes the applicable research-honesty gates** (`design_research_honesty_gates.md`:
>    H1 trial ledger, H4 accuracy ceiling, H5 verdict, H10 coverage, H11 intervals);
> 5. **no existing authoritative producer owns the same quantity.**
>
> **Capability gap is necessary but not sufficient.** A missing package never justifies itself: admission
> additionally requires a *benchmarked out-of-sample incremental value* against the target family's
> declared benchmark (§8.2). The sequence is:
>
> ```
> capability gap → research hypothesis → benchmark → incremental value
>                                              → producer specification → admission
> ```

`arch` fails clause 5. `darts` fails clauses 1–2. `statsforecast` passes 1–2 **conditionally** and is
blocked on 4 until a benchmark exists.

---

## 4. Verified library facts

Read from each project's current `pyproject.toml` / `LICENSE` / model source on 2026-10-03.

| Library | Licence (verified) | Core runtime deps (verified) | Build |
|---|---|---|---|
| `statsforecast` 2.1.1 | **Apache-2.0** | `coreforecast`, `numpy`, `pandas<3.0.0`, `scipy`, **`statsmodels>=0.14.5`**, `fugue`, `utilsforecast`, `threadpoolctl`, `cloudpickle`, `tqdm` | **compiled** (`scikit-build-core` + `pybind11`) |
| `mlforecast` 1.1.0 | **Apache-2.0** | `coreforecast`, **`scikit-learn`**, **`optuna`**, `narwhals`, `fsspec`, `pandas<3.0` | pure-python |
| `arch` | **NCSA** — not MIT/BSD/Apache | `numpy`, `pandas`, `scipy`, `statsmodels`, `packaging` | **compiled** (`meson-python` + Cython) |
| `qlib` | **MIT** | (platform) | pure-python |
| `finrl` | **MIT** | (platform) | pure-python |
| `chronos-forecasting` | **Apache-2.0** (README + `LICENSE`) | torch | model weights from HF |
| `timesfm` | source **Apache-2.0**; weights **≤ 2.5 Apache-2.0**; **3.0 weights non-commercial** | torch / MLX | model weights from HF |
| `hmmlearn`, `ruptures`, `statsmodels`, `darts`, `neuralforecast`, `pymc` | **not verified in this pass** | — | mixed |

### 4.1 Corrections to the evaluated proposal's dependency model

Four of its framing assumptions do not match the verified versions. Stated factually, since the point is
the dependency surface, not the argument:

- **`statsforecast` takes `statsmodels` as a hard dependency and does not declare `numba`.** The
  proposal's mental model of the Nixtla stack is inaccurate for the verified versions.
- **`arch` is NCSA**, a distinct licence with its own attribution clause — not the MIT/BSD/Apache class
  the proposal groups it with.
- **`mlforecast`'s core dependency is `scikit-learn` + `optuna`.** `LightGBM`/`XGBoost` appear only under
  the `dask`/`ray`/`spark` extras, so the "→ LightGBM/XGBoost" path needs an extra, not just the package.
- **Licensing must be version- and checkpoint-specific, never class-level.** The clearest case is
  TimesFM, whose README states plainly: *"TimesFM 3.0 pretrained weights are distributed under the
  separate `timesfm-non-commercial-license-v1.0` license and are restricted to non-commercial,
  non-production use. Commercial or production use of downloaded / self-hosted weights is **not
  permitted**"* — while its source and its ≤2.5 weights are Apache-2.0, and commercial 3.0 use is
  permitted only through Google Cloud services. A blanket "foundation models are free" rule and a blanket
  "foundation models are non-free" rule are both wrong.

### 4.2 Verified capabilities relevant to this design

**`StatsForecast` ships `GARCH` and `ARCH` models** (`python/statsforecast/models.py`, their own
documented group), and both are **implemented in-house** — `fit()` calls `garch_model(y, p, q)`,
`predict()` calls `garch_forecast(...)`. It does **not** delegate to `arch`, which is why `arch` is absent
from its dependency list.

`predict()` returns **`{"mean", "sigma2"}`** — the conditional-variance forecast, which is the quantity
this engine's risk path consumes. Intervals are `quantile × sqrt(sigma2)` (Gaussian) unless
`prediction_intervals=ConformalIntervals(...)` is passed.

> **Note on ownership, not equivalence.** `StatsForecast.GARCH` and `strategies/volatility_models.py:438`
> `garch11_fit` both produce GARCH-family conditional-variance forecasts. That overlap is sufficient to
> establish an **ownership conflict** under FD-1 clause 5. This document does **not** claim the two are
> numerically equivalent, and it does not need to: two GARCH implementations differ in likelihood,
> distributional assumption, initialization, parameter constraints, optimizer, scaling, horizon handling
> and missing-data policy. Establishing equivalence would require its own measurement.

**The evaluated proposal's architectural advice is consistent with this repository's invariant 8** — it
declines "one giant `ForecastScore`" and keeps the score engines independent, which is
`docs/scores/README.md` §2.1 restated.

---

## 5. What is forecastable: the evidence, by target family

### 5.1 The absolute return level — **not admitted**, and that is not the same as "unforecastable"

v1.0 stated this badly. The correct claim is:

> **No authoritative absolute return-level forecast is admitted by this design unless a declared producer
> demonstrates out-of-sample incremental value against this repository's prescribed benchmark and passes
> the research-honesty gates.**

That is a **statement about this engine's authorization**, not about markets. The distinction matters
because it is falsifiable and it names what would change it. Three separate things have been conflated in
the past and are kept apart here:

| Claim | Status |
|---|---|
| "A univariate price-history model fitted to one name produces an authoritative expected return" | **Rejected.** This is what the evidence bears on. |
| "Stock returns are not forecastable" (universal) | **Not claimed, and not supported by the cited evidence.** |
| "No absolute return-level forecast is currently authorized in this engine" | **The operative rule.** |

The evidence supports *skepticism about the specific, weakest construction*:

**Hjalmarsson (2006), Fed IFDP 855.** *"Using Monte Carlo simulations, I show that typical out-of-sample
forecast exercises for stock returns are unlikely to produce any evidence of predictability, even when
there is in fact predictability and the correct model is estimated."* His T=600-monthly, c=−20 runs put
the conditional forecast ahead of the constant-return benchmark **on average** only above a true
β ≈ 0.015, with a Diebold-Mariano rejection rate of 5.8% at that β. The instruction that follows —
*"you are often better off setting it equal to zero, rather than using a noisy estimate of it"* — is an
argument about **estimation noise against a small coefficient**, not about the absence of structure.

**Goyal, Welch & Zafirov (2021 SFI WP 21-85; RFS 2024, 37(11) 3490).** 17 original predictors plus 29
variables from 26 post-2008 papers, samples ending 2021: *"Much of the extant literature seems obsolete,
with a majority of variables no longer having empirical support even in-sample. A small number still
perform reasonably well."* Note the last clause: **a small number still work.** A universal claim would
have to contradict it.

So the rule is a **gate, not a verdict**: it declines the construction that has repeatedly failed, and it
leaves the door open for a producer that clears §8.2's benchmark.

### 5.2 The four return-adjacent targets are different objects

This is the second place v1.0 was too coarse. A single `return_forecast` concept cannot express:

| Target | Meaning | Evidence |
|---|---|---|
| `absolute_return` | a name's expected absolute return over a horizon | the weak construction above — **not authorized** |
| `relative_return` | a name's return in excess of a benchmark/peer set | distinct question; the cross-section channel |
| `return_rank` | the name's ordinal position in the cross-section | **explicitly near-unforecastable** — see below |
| `residual_return` | the return after market/factor residualization | distinct again; `cross_section.residualize_returns:223` already produces the *input* |

The repository's own survey result (`design_cross_section_and_allocation.md` §1, paper 2607.27461) is
precise: the **volatility-rank** transition matrix is forecastable with multi-step memory (out-of-sample
monthly log-likelihood gain **0.108**) while the **return-rank** matrix is close to unforecastable
(**0.007**); return-rank mean absolute error sits at 2.5 deciles and covariates do not move it, while the
volatility rank's falls from 2.05 to 1.78 with covariates.

So `return_rank` carries a `declined` status with a cited reason — exactly like `absolute_return` — and
neither statement is allowed to stand in for the other.

### 5.3 Volatility — forecastable, with HAR-RV as the benchmark to beat

**Corsi (2009), *J. Financial Econometrics* 7(2):174–196.** HAR-RV:

```
RV_{t+1} = c + b_d * RV_t + b_w * RV_w + b_m * RV_m
```

Its abstract records the finding this engine's design already assumes — *"direct time series modeling of
realized volatility strongly outperforms, in terms of out-of-sample forecasting, the popular GARCH and
stochastic volatility models"* — with S&P 500 coefficients b_d=0.372, b_w=0.343, b_m=0.224. The model
reproduces long memory, fat tails and self-similarity **without being a long-memory process**, which is
why a three-term regression is the right benchmark rather than a null.

**Leushuis & Petkov (2026), *Financial Innovation* 12:14** (open access). A review of 32 realized-volatility
models from 41 papers, 2000–H1 2024. It reports stronger performance for some deep architectures (a
CNN-LSTM hybrid leads on its aggregated metrics) and enumerates the six empirical properties any model must
address. **That evidence is a literature aggregate, not a measurement on this engine's data, and therefore
does not justify adoption without an engine-specific evaluation** (§8.2). The review also deliberately
excludes GARCH as a latent-volatility model, and a 2025 paper in the same journal's related list —
*"Examining Challenges in Implied Volatility Forecasting: A Critical Review of Data Leakage and Feature
Engineering combined with High-Complexity Models"* — is a standing warning about this model class.

### 5.4 The precise gap — not "no forecasting", but "no learned forecast pool"

```
evaluated proposal
   ├── GARCH ───────────── already owned  (volatility_models.garch11_fit:438)
   ├── HAR + long memory ── already owned  (strategies/long_memory.py, V2)
   ├── HMM / regime ─────── already owned  (regime.py:545, R2)
   ├── change-point ─────── already owned  (regime.py:1013, :1327)
   ├── conformal intervals ─ already owned  (conformal.py, H11)
   ├── covariance ──────── already owned  (covariance_models.py:85, :132)
   │
   └── ML forecast pool ─── genuine capability gap  → V1 (already designed, BLOCKED)
```

The repository has most of the forecasting **methods** but no general-purpose **learned forecast-pool
producer** with online scoring and regime-similarity routing. That is the accurate architectural
conclusion, and it is V1's item — blocked on a **vendor state vector** (`VXV` + a HY-spread series), not
on a library.

---

## 6. What this repo already owns (verified)

### 6.1 The owners

| Theme | Producer(s), verified | State |
|---|---|---|
| GARCH / ARCH / range / semivariance | `strategies/volatility_models.py:68` `semivariance`, `:155` `parkinson_vol`, `:185` `garman_klass_vol`, `:288` `yang_zhang_vol`, `:332` `yang_zhang_vol_series`, `:397` `ewma_vol`, `:438` `garch11_fit` (MLE, `:53` `_IGARCH_AB` breakdown guard) | built |
| Jump-robust realized measures | `volatility_models.py` `bipower_proxy` / `quarticity_proxy` behind `enable_jump_robust_proxies` | built — V6 |
| HAR + semiparametric memory | `strategies/long_memory.py:146` `memory_parameter` (GPH + local Whittle), `:236` `rv_forecast`, `:58` `long_memory_enabled`; consumed by `mean_reversion.py::memory_profile` | built — V2, `gate_registry.md:273` |
| HMM / Markov regime | `regime.py:545` `hmm_filtered_regime` (Baum-Welch `_hmm_em:355`, **causal filtered** posteriors), `:781` `regime_conditional_var`, `:743` `hmm_regime` delegating so there is ONE producer | built — R2 |
| Change-point / structure break | `regime.py:1013` `cusum`, `:1327` `bocpd`, `:1494` `spectral_change_read`; `complexity.py` | built |
| Kalman / state-space | `statistical_kalman.py:42` `kalman_spread` | built |
| Conformal / probabilistic intervals | `conformal.py` `quantile_band` (CQR), `rolling_band`, `iid_interval`, `block_bootstrap_interval`, `information_gap`, `adf_t`, `block_length` | built — H11 |
| Option-implied / risk-neutral | `options_surface.py:25` `iv_skew`, `:201` `surface_shape`, `:227` `term_structure_slope`, `:294` `pre_event_iv_lift`, `:489` `rn_skew_proxy`; `rnd_recovery.py` | built — V3, V4, K3 |
| Covariance / eigenstructure | `covariance_models.py:132` `ewma_covariance`, `:85` `ledoit_wolf_shrink`; `eigen_rotation.py` | built — V5 |
| Tails / drawdown / VaR-CVaR | `tail_risk.py`, `book_risk.py::drawdown_envelope`, `triadic_stress.py` | built — K1, K2 |
| Evaluation harness | `prediction_ledger.py`, `evaluate.py`, `trial_ledger.py`, `calibration.py:151`, `signal_analysis.py:64` `rank_ic` | built — H1, H5 |

### 6.2 The Tier-1 audit, stated precisely

All six Tier-1 proposals are either **redundant with an existing authoritative producer** or **belong to
an already-defined but currently blocked producer capability**:

- **`arch`** → `garch11_fit` is the GARCH producer. Fails FD-1 clause 5. `REJECT_DUPLICATE`.
- **`statsmodels`** → its regime/econometric surface is covered by `regime.py` + `covariance_models.py`.
  It is also a **hard dependency of `statsforecast`**, so it arrives transitively if that is ever
  admitted — no direct case. `REJECT_DIRECT`.
- **`hmmlearn`** → `hmm_filtered_regime` exists **and feeds `book_risk`'s VaR**. A second regime label is
  the highest-risk duplicate in this table, because two disagreeing labels are indistinguishable from a
  regime change. `REJECT_DUPLICATE`.
- **`ruptures`** → `cusum` + `bocpd` + `spectral_change_read` cover the declared change-point surface.
  `REJECT_DUPLICATE`.
- **`StatsForecast`** → its distinct artifact is V1's scored, regime-routed **pool**, which is designed and
  blocked on a vendor state vector. `CONDITIONAL`.
- **`MLForecast`** → the pool's learned members. This is *not* a wrapper around something already built;
  learned-member forecasting is genuinely the capability gap. `CONDITIONAL`.

---

## 7. The ForecastContract

The contract is a **declaration**. It computes nothing, and it is deliberately not gated — a declaration
that must be switched on is one nobody uses. The producers it reads are each already individually gated
(`enable_long_memory`, `enable_jump_robust_proxies`, `enable_hmm_heavy_tails`, `enable_bootstrap_intervals`, …).

### 7.1 The record

```
ForecastRecord
├── key                  : str            # semantic name; carries NO horizon (see §7.4)
├── producer             : str            # "strategies/long_memory.py::rv_forecast"  <- the authority
├── gate                 : str | None     # "enable_long_memory" | None
│
├── target                                # MANDATORY - "volatility" alone is not a target (§7.3)
│   ├── name             : str            # "realized_volatility" | "return_rank" | ...
│   ├── definition       : str            # the measurement, e.g. "sqrt(sum of squared daily returns)"
│   ├── unit             : str            # "annualized_vol" | "probability" | "rank_decile" | ...
│   └── annualization    : int | None     # 252, or None
│
├── frequency            : str            # "1d" | "5m" | "1w"   <- 5d@1d is not 5d@5m
├── horizon              : int            # steps in `frequency` units; >= 1 (rule 6)
├── forecast_origin      : timestamp      # the as-of date the forecast is made FOR
│
├── value                : float | None    # None <=> status != "ok"  (NEVER 0.0 as a placeholder)
├── status               : str            # "ok" | "unavailable" | "declined"
├── reason_code          : str | None     # MACHINE-READABLE (§7.2 rule 4)
├── reason_detail        : str | None     # human prose, optional
│
├── interval                              # PRODUCTION metadata: known when the forecast is made
│   ├── low              : float
│   ├── high             : float
│   ├── nominal_coverage : float          # 0.90
│   ├── method           : str            # "CQR" | "block_bootstrap" | "gaussian_sigma"
│   └── calibration_ref  : str | None     # the calibration window/source the band was calibrated on
│
├── provenance
│   ├── data_version     : str
│   ├── training_start   : timestamp
│   ├── training_end     : timestamp
│   ├── requested_window : int
│   ├── effective_window : int
│   ├── padded           : bool           # a padded window is BIASED, not merely low-confidence
│   ├── missing_obs      : int
│   ├── imputed_obs      : int
│   ├── adjusted_prices  : bool           # adjusted vs unadjusted changes the economic meaning
│   └── model_version    : str
│
└── evaluation                            # POST-HOC metadata: DECLARED, not populated at forecast time
    ├── evaluated        : bool           # False at creation; the ledger fills this later
    ├── realized_coverage: float | None
    ├── n_observations   : int | None
    ├── scoring_rule     : str | None     # "CRPS" | "QLIKE" | "RMSE" | "MAE"
    ├── benchmark_ref    : str | None     # which §8.2 benchmark it was scored against
    ├── benchmark_delta  : float | None
    └── evaluated_as_of  : timestamp
```

### 7.2 The rules

1. **`value is None` iff `status != "ok"`.** A forecast that cannot be made is `unavailable`; it is never
   `0.0` and never a shrunk-to-zero pseudo-number (`NA != 0`, `ScoreContextContract.md`, restated for
   forecasts).
2. **One producer per `(key, frequency, horizon)`.** Declared once, asserted by a test. Invariant 8, made
   checkable for forecasts.
3. **`declined` is a first-class status**, distinct from `unavailable`:
   - `ok` — a producer was authorized and produced a value.
   - `unavailable` — authorized, but not currently producible. Codes: `INSUFFICIENT_HISTORY`,
     `MISSING_VENDOR_SERIES`, `MODEL_FIT_FAILURE`, `COVERAGE_FAILURE`, `GATE_OFF`.
   - `declined` — the engine **intentionally does not produce this by policy**. Codes:
     `RETURN_LEVEL_NOT_ADMITTED`, `RETURN_RANK_NOT_ADMITTED`, `TARGET_NOT_ADMITTED`.
   A `declined` row is a **cited, reversible policy statement**; an absent row is an invitation.
4. **`reason_code` is machine-readable** and drawn from a closed vocabulary; `reason_detail` is optional
   prose. A test asserts every non-`ok` row carries a code from the vocabulary.
5. **Production and evaluation metadata are separate.** `interval.realized_coverage` does **not** exist —
   the interval carries only what is knowable when the forecast is made. Realized coverage lives in
   `evaluation` and is populated by the prediction ledger after the outcome resolves. *This was a v1.0
   error.*
6. **A state read is not a forecast.** `horizon >= 1` is required. A regime/current-state read belongs in
   the score/state contracts, not here — otherwise `ForecastRecord(key="regime.current", horizon=0)`
   appears and the forecast namespace becomes a generic analytics namespace, destroying the ability to
   reason about the ledger.
7. **No forecast without a target definition.** `target.name`, `target.definition`, `target.unit`,
   `frequency` and `horizon` are mandatory. This matters because the repo carries at least nine distinct
   volatility concepts (`ewma_vol`, `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `garch11_fit`,
   realized vol, `semivariance`, `bipower_proxy`, `quarticity_proxy`) — **a forecast of one is not
   interchangeable with a forecast of another.**
8. **Provenance is mandatory**, including `padded`. The corpus's temporal-coverage-bias result is that a
   padded window *suppresses measured volatility in a known direction* — it is biased, not merely
   uncertain — and `adjusted_prices` changes the economic meaning of a return series while leaving the
   arithmetic reproducible.

### 7.3 The target vocabulary

Declared once, so `key` stays a name rather than a semantic soup:

```
absolute_return      relative_return      return_rank      residual_return
volatility           variance             volatility_rank
regime_probability   regime_stress_probability
```

`unit` is drawn from: `annualized_vol`, `variance`, `probability`, `rank_decile`, `pct`,
`raw_return_bps`.

Key/horizon are **separated**, not combined:

```
key = "realized_volatility"      frequency = "1d"   horizon = 1    unit = "annualized_vol"
key = "volatility_rank"          frequency = "1d"   horizon = 22   unit = "rank_decile"
key = "regime_stress_probability" frequency = "1d"  horizon = 5    unit = "probability"
```

(`v1.0` wrote keys such as `rv.d1`, which encoded the horizon inconsistently.)

### 7.4 What the contract does not do

- It is **not** a module that computes anything — a declaration, a registry and a test.
- It does **not** add a member to `COMPOSITE_ENGINES`.
- It does **not** put a return forecast on the decision path (`kelly_weights`' declaration boundary, §2).
- It does **not** accept state reads (§7.2 rule 6).

---

## 8. From forecast to admissible evidence

### 8.1 The wiring

v1.0 omitted this entirely; it is the largest architectural gap in that revision.

```
Forecast producer (declared, gated)
        │
        ▼
ForecastRecord (this contract)
        │
        ▼
strategies/prediction_ledger.py      ← immutable prediction rows, scored against realized outcomes
        │
        ▼
realized outcome
        │
        ▼
evaluation:  evaluate.py · trial_ledger.py · calibration.py · signal_analysis.rank_ic
        │
        ├── point:  MAE / RMSE            ── vs benchmark
        ├── dist:   CRPS / QLIKE          ── vs benchmark
        └── band:   realized coverage     ── vs nominal
        ▼
design_research_honesty_gates.md: H1 (trial ledger, deflation) · H4 (accuracy ceiling / base rate)
                                  H5 (five-gate verdict) · H11 (autocorrelation-aware intervals)
        ▼
admission / continued use
```

The direction is one-way: **the ledger scores the producer; the producer never scores itself.** A
forecast's `evaluation` block is filled by the ledger, not by the producer, so a producer cannot declare
its own realized coverage.

### 8.2 Every forecast family needs a declared benchmark

A forecast does not get credit for producing a number. Before admission, each family names its benchmark:

| Target family | Benchmark |
|---|---|
| `volatility` / `variance` | **HAR-RV** (Corsi) and naive trailing realized vol; GARCH as a third reference |
| `absolute_return` | historical mean; zero |
| `relative_return` / `residual_return` | the appropriate factor or rank baseline |
| `return_rank` / `volatility_rank` | persistence (today's rank); `centered_rank` of trailing return |
| `regime_probability` | persistent-state (sticky) Markov baseline |
| any `interval` | naive empirical quantile band (`conformal.iid_interval` is the floor) |

Plus the repo's existing discipline: `2602.07841`'s **nontrivial upper bound on the out-of-sample R²**
(surveyed in the H-theme) is a ceiling any return-forecast claim must stay under, and `H4`'s base-rate
ceiling applies to every directional claim.

---

## 9. Per-library verdict

Reasons are categorized so a future contributor can re-open the *right* argument rather than the whole
row.

| Candidate | Verdict | Reason |
|---|---|---|
| `statsforecast` | **CONDITIONAL** | Only for a declared producer whose capability is not already owned, and only as a versioned **offline refit** (ground rule 8). Requires FD-1 cl. 1–4 + §8.2 benchmark. |
| `mlforecast` | **CONDITIONAL** | Same; the likely source of V1's learned members. Brings `scikit-learn` + `optuna`. |
| `arch` | **REJECT_DUPLICATE** | `garch11_fit` is the existing GARCH producer (FD-1 cl. 5). |
| `statsmodels` | **REJECT_DIRECT** | Existing `regime`/`covariance_models` surface; transitive via `statsforecast` if admitted. |
| `hmmlearn` | **REJECT_DUPLICATE** | `hmm_filtered_regime` exists and feeds `book_risk`'s VaR. |
| `ruptures` | **REJECT_DUPLICATE** | `cusum` + `bocpd` + `spectral_change_read`. |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | **REJECT_NO_CONSUMER** | No declared producer; large compiled/torch dependency surface. |
| `pymc`, `pyro`, `tensorflow-probability` | **REJECT_NO_CONSUMER** | No declared probabilistic producer; `conformal.py` already supplies calibrated bands. |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | **REJECT_THIS_PASS** | No declared consumer **and no demonstrated incremental value**. Reopening requires a separate **code-licence / checkpoint-licence / hardware / reproducibility / leakage** evaluation — TimesFM 3.0's non-commercial weights (§4.1) are the worked example of why that review is not a formality. |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | **REJECT_NO_RESEARCH_CASE** | No research case; agreed with the evaluated proposal's own Tier 4. |
| `qlib`, `finrl` | **ALREADY_OWNED** | Existing design+plan pairs in `docs/`. |

**Today's net dependency change: zero.**

---

## 10. Non-goals

- **V1's volatility forecast pool** — owned by `design_vol_surface_and_vrp.md` §V1; this doc only names its
  admission path.
- **V2's memory parameter and HAR forecast** — owned by the same doc; **built** as `strategies/long_memory.py`.
- **Regime (R1–R9), tails/drawdown (K1–K6), cross-section (X1–X8), evaluation gates (H1–H11)** — each owned
  by its `docs/paper_survey_26/` pair. Cited here, never restated.
- **The score set and `COMPOSITE_ENGINES`** — owned by `docs/scores/README.md`.
- **Report verification** — unrelated ownership.

---

## 11. Open owner decisions

1. **Does `absolute_return` and `return_rank` ship as `declined` rows, or omitted?** §7.2 rule 3 recommends
   **`declined` with a reason code** — a cited refusal is harder to silently reverse than an absent field.
2. **Is the dependency policy permissive-OSI only?** `arch` is rejected on duplication grounds regardless,
   but the *policy* recurs: this repo's dependency set is currently MIT/BSD/Apache. Recommend: **permissive
   OSI only; NCSA and any checkpoint licence require an explicit sentence** — decided once, not per library.
3. **V1's vendor unblock** — `VXV` and a HY-spread series are not confirmed live vendor calls. That is V1's
   blocker and the only thing standing between §9's `CONDITIONAL` verdicts and a real dependency.

---

## 12. Review dispositions (v1.0 → v1.1)

Every point raised in review, with its disposition. Points are numbered by the review's own headings.

| # | Review point | Disposition |
|---|---|---|
| 1 | Elevate the admission sentence to a formal invariant, with 5 clauses | **Accepted** — §3, FD-1 |
| 2 | Headline finding is "methods owned, no learned forecast *pool*" | **Accepted** — §1, §5.4 |
| 3 | Don't say "returns are not forecastable"; say no authoritative return forecast is admitted | **Accepted** — §5.1, the most important correction |
| 4 | Separate `absolute_return` / `relative_return` / `return_rank` / `residual_return` | **Accepted** — §5.2, §7.3 |
| 5 | Add `target`, `frequency`, `forecast_origin`, `evaluation` to the record | **Accepted** — §7.1 |
| 6 | Split interval production from realized-coverage evaluation | **Accepted** — §7.1, §7.2 rule 5 (a genuine v1.0 error) |
| 7 | Enrich provenance (`padded` insufficient; add adjusted prices, versions, windows) | **Accepted** — §7.1 |
| 8 | Define `ok` / `unavailable` / `declined` semantics; add machine-readable reason codes | **Accepted** — §7.2 rules 3–4 |
| 9 | Remove `horizon = 0` state reads from ForecastContract | **Accepted** — §7.2 rule 6 |
| 10 | Tighten key/horizon identity; pick one convention | **Accepted** — §7.3 (separated, not combined) |
| 11 | Add a mandatory `target_definition` | **Accepted** — §7.2 rule 7 |
| 12 | Soften "the proposal's mental model is out of date" | **Accepted** — §4.1 |
| 13 | Don't claim StatsForecast's GARCH equals the repo's until numerically established | **Accepted** — §4.2, ownership only |
| 14 | Don't assert "the DL increment over HAR is real but modest" without a basis | **Accepted** — §5.3 |
| 15 | Foundation models: `REJECT_THIS_PASS` + explicit review list, not a class verdict | **Accepted — and strengthened**: verified TimesFM 3.0's non-commercial weights |
| 16 | `CONDITIONAL` needs two conditions (gap **and** in-house infeasibility) | **Accepted** — §3, §9 |
| 17 | Admission must be evidence-based, not capability-based | **Accepted** — §3 |
| 18 | Add "forecasting is not scoring" | **Accepted** — §2 |
| 19 | Connect the contract to the prediction ledger and evaluation gates | **Accepted** — §8.1 |
| 20 | Mandatory benchmark per forecast family | **Accepted** — §8.2 |
| 21 | Categorize rejection reasons | **Accepted** — §9 |
| 22 | "Six of six Tier-1" needs qualification | **Accepted** — §6.2 |
| 23 | Add "no library was evaluated for forecast quality on this universe" | **Accepted** — §13.1 |
| 24 | Make the doc less conversational / stand alone | **Accepted in part** — the doc's scope *is* an evaluation, so the object is named neutrally ("the evaluated proposal") in §1–§2 and §12, rather than removed. §1–§3 now read standalone. |
| 25 | Revised decision matrix | **Accepted** — §9 |
| 26 | Revised `ForecastRecord` | **Accepted with modifications** — §7.1 retains `NA != 0` (a refusal can never carry a zero), mandatory `padded`, and closed vocabularies for `status` / `reason_code` / `unit`, so the record stays machine-testable |
| 27 | "No forecast without a target definition" | **Accepted** — §7.2 rule 7 |
| 28 | Recommended final architecture | **Accepted** — §2 + §8.1 |
| 29 | Keep-list | **Retained** |

---

## 13. Honest limits

1. **No library was evaluated for forecast quality on this engine's production universe.** Library
   capability is therefore not evidence of financial usefulness — §4 establishes what a package
   *contains*, never that it *works here*.
2. **No item here is backtested** — this document authorises no build.
3. **Seven licences were verified from source** (`statsforecast`, `mlforecast`, `arch`, `qlib`, `finrl`,
   `chronos`, `timesfm`); **every other library in §9 is marked unadmitted rather than assumed
   permissive**, and several (including `hmmlearn`, `ruptures`, `statsmodels`, `darts`, `neuralforecast`,
   `pymc`) were not verified in this pass because their verdicts do not turn on the licence.
4. **`statsforecast`'s `GARCH` was read in source but never executed.** That `predict()` returns
   `{"mean","sigma2"}` is a read of its return dict. `[INFERENCE]` for the behaviour, fact for the code.
5. **Leushuis & Petkov's deep-learning result is a literature aggregate**, and their sibling literature is
   explicit that such increments are fragile under leakage — §5.3 states it as a reason not to adopt.
6. **`return_rank`'s `declined` status rests on one paper's measurement** (2607.27461's 0.007 vs 0.108),
   which is the best available evidence here but is not this engine's own measurement. §8.2 names the
   benchmark that would settle it locally.
7. **This document's `CONDITIONAL` verdicts could be wrong.** If V1 unblocks and its learned members cannot
   be expressed with the in-house regressions, `statsforecast`/`mlforecast` may be the cheapest correct
   answer — which is why they are conditional and why FD-1 is an admission rule rather than a ban.

---

## References

- Hjalmarsson, E. (2006). *Should We Expect Significant Out-of-Sample Results when Predicting Stock
  Returns?* Fed IFDP 855. <https://www.federalreserve.gov/pubs/ifdp/2006/855/ifdp855.pdf>
- Goyal, A., Welch, I., & Zafirov, A. (2021/2024). SFI WP 21-85; *Review of Financial Studies* 37(11) 3490.
- Corsi, F. (2009). *J. Financial Econometrics* 7(2):174–196.
- Leushuis, R. M., & Petkov, N. (2026). *Financial Innovation* 12:14. DOI 10.1186/s40854-025-00809-5.
- Nixtla `statsforecast` / `mlforecast` `pyproject.toml` + `python/statsforecast/models.py` (main).
- Sheppard, K. `arch` `pyproject.toml` (main) — NCSA.
- `google-research/timesfm` `LICENSE` (Apache-2.0) + README licence notice (3.0 weights non-commercial).
- `amazon-science/chronos-forecasting` `LICENSE` + README (Apache-2.0).
- Microsoft `qlib` LICENSE (MIT); AI4Finance `FinRL` LICENSE (MIT).
- Internal: `design_fin_paper_survey_26.md` §3/§5; `paper_survey_26/design_vol_surface_and_vrp.md`
  §2/§V1/§V2/§5; `paper_survey_26/design_cross_section_and_allocation.md` §1; `MASTER_DESIGN.md` §2
  (invariant 8); `docs/scores/README.md` §2.1; `CHANGELOG.md` (the *"Rejected outright"* entry).
