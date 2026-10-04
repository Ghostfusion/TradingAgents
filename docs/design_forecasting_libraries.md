# Design: The Forecasting Layer — Ownership, Admission Rule, and the ForecastContract

**Status:** DESIGN — **FROZEN 2026-10-03 at v1.2.** The contract, the ownership invariant (**FD-1**), the
admission rule, the production/evaluation boundary and the library verdict categories are settled; an
implementation item may not reopen them (see §11.0 for the boundary). **No library is admitted and no
producer is built by this document.** The companion plan carries eight items: six `WORK` (FL-1…FL-6),
one `DOC` (FL-7) and one `DECISION` (FL-8).
**Version:** 1.2 (revises v1.1 and v1.0, 2026-10-03)
**Date:** 2026-10-03
**Scope:** Whether this engine should adopt a third-party time-series forecasting stack, what a forecast
*is* in this repository, and the contract a forecast number must satisfy to be admissible evidence.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Owners (docs this one must not double-own):** `docs/paper_survey_26/design_vol_surface_and_vrp.md`
(volatility, surface), `design_regime_estimation_hardening.md` (regime),
`design_cross_section_and_allocation.md` (cross-section, ranks), `design_risk_tail_and_coverage.md`
(tails, drawdown, VaR), `design_research_honesty_gates.md` (H1–H11).
**Plan:** [`implementation_plan_forecasting_libraries.md`](implementation_plan_forecasting_libraries.md) (v1.2, PLAN).
**Rule-4 impact:** none. No tool, gate, config key, report key or screener column changes.

**Revision notes.** *v1.2* answers a second review round: the mutable-evaluation contradiction is resolved
by splitting **`ForecastRecord` (production, immutable)** from **`ForecastEvaluation` (post-hoc,
immutable)**, which was the sharpest remaining issue; **candidate model outputs are formally separated
from the one authoritative producer**, which is what makes V1's forecast pool legal under invariant 8;
`forecast_origin` is given its correct meaning; the **StatsForecast/`arch` model-family claim is
corrected down** (neither supplies `GARCH(1,1)-t` or `FIGARCH(1,1)-t`); and `producer_id` is separated
from `implementation_ref`. §12.2 dispositions every point, including **one review claim that is refuted
by primary source** (`statsforecast`'s build backend — see §4.1n). *v1.1* answered the first review:
the return-forecast claim became an authorization gate rather than a market claim, production and
post-hoc interval metadata were separated, and `horizon = 0` state reads were removed.

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
| **Model families** — GARCH/ARCH, HAR + long memory, HMM regime, change-point, conformal intervals, covariance, RND recovery, eigenspace rotation | **Already owned, and five of six already shipped.** A library here would be a **second authoritative producer** of a quantity this repo already owns — forbidden by invariant 8 and FD-1 clause 5. |
| **The `ForecastContext` shape** | **Worth adopting — as a declaration, not a producer.** §7 is the artifact this document exists to specify. |
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

### The architecture, end to end

```
   candidate models            ┌ HAR · GARCH · FIGARCH · XGBoost · GRU · … ┐
   (NOT authoritative)         └────────────── candidate outputs ──────────┘
                                              │
                                              ▼
                            ┌─────  Forecast Pool / Selector  ─────┐
                            │  model selection · weighting ·      │
                            │  regime routing                     │
                            └──────────────┬──────────────────────┘
                                           │
                                ONE AUTHORITATIVE OUTPUT
                                           ▼
                          ┌────────  ForecastRecord  ────────┐
                          │ target · scope · frequency ·     │
                          │ horizon_steps · origin · value · │
                          │ interval · provenance · status   │
                          └──────────────┬───────────────────┘
                                         ▼
                            strategies/prediction_ledger.py
                                         ▼
                          ┌──────  ForecastEvaluation  ──────┐
                          │ realized outcome · score ·       │
                          │ benchmark_delta · coverage       │
                          └──────────────┬───────────────────┘
                                         ▼
                        H1 · H4 · H5 · H10 · H11  (honesty gates)
                                         ▼
                                 ADMISSIBLE EVIDENCE
```

And separately, never collapsed:

```
Forecast  ≠  Score  ≠  Signal  ≠  Decision
```

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

## 3. The Forecasting Dependency Admission Invariant (FD-1)

> **FD-1. A forecasting dependency may be admitted only when all five hold:**
>
> 1. a **declared producer** requires a **capability that no existing authoritative producer supplies**;
> 2. that producer has a **named consumer** (a tool, an engine, a report row, or a sizing input);
> 3. its **target is fully defined** — name, measurement definition and definition version, unit,
>    scope, frequency and horizon steps (§7.1, §7.3);
> 4. it **passes the applicable research-honesty gates** (H1 trial ledger, H4 accuracy ceiling, H5
>    verdict, H10 coverage, H11 intervals);
> 5. it does **not create a second authoritative producer for an already-owned semantic quantity.**
>
> **A capability gap is necessary but not sufficient.** A missing package never justifies itself:
> admission additionally requires a *benchmarked out-of-sample incremental value* against the target
> family's declared benchmark (§8.2). The sequence is:
>
> ```
> capability gap → research hypothesis → benchmark → incremental value
>                                              → producer specification → admission
> ```

### 3.1 Capability ownership vs quantity ownership

Clauses 1 and 5 are deliberately **different questions**, and the distinction is load-bearing:

| | Question | Consequence |
|---|---|---|
| **Capability ownership** (cl. 1) | Does *any* existing authoritative producer supply this capability? | If not, a library **may** provide the implementation. |
| **Quantity ownership** (cl. 5) | Does an existing authoritative producer already publish this semantic quantity? | If yes, a second producer is forbidden **regardless of implementation**. |

Worked cases:

- `arch` fails **clause 5**: `volatility_models.garch11_fit:438` already publishes the conditional
  variance. A different GARCH implementation is still a second producer of the same quantity.
- A learned cross-sectional forecast fails **clause 1** (no existing producer) but passes **clause 5**
  (nobody owns that quantity) — so this is a capability gap a library may fill.
- `statsforecast` passes clauses 1–2 **conditionally** for a specific capability and is blocked on
  clauses 3–4 until a benchmark exists.

### 3.2 Candidate outputs are not authoritative forecasts

This is the clause that makes V1's forecast pool legal under invariant 8.

> **Candidate model outputs are evaluation artifacts, not authoritative forecast quantities.** A group of
> models may each produce a value for the same semantic target; these are **candidates**. Only the
> **pool/selector** publishes the authoritative `ForecastRecord`, and it publishes exactly one. The
> uniqueness rule in §7.2 rule 2 therefore binds the **pool**, never its members.

Without this, a literal reading of "one producer per key" would make V1's pool (HAR-RV, GARCH, GRU,
XGBoost … all emitting `realized_volatility @ 1d`) look like a violation. It is not, because exactly one
of them is authoritative — the selector.

`arch` still fails: it is not a candidate in a pool, it is a **competing authority** for a quantity the
engine already publishes.

---

## 4. Verified library facts

Read from each project's current `pyproject.toml` / `LICENSE` / model source on 2026-10-03.

| Library | Licence (verified) | Core runtime deps (verified) | Build |
|---|---|---|---|
| `statsforecast` 2.1.1 | **Apache-2.0** | `coreforecast`, `numpy`, `pandas<3.0.0`, `scipy`, **`statsmodels>=0.14.5`**, `fugue`, `utilsforecast`, `threadpoolctl`, `cloudpickle`, `tqdm` | **compiled** |
| `mlforecast` 1.1.0 | **Apache-2.0** | `coreforecast`, **`scikit-learn`**, **`optuna`**, `narwhals`, `fsspec`, `pandas<3.0` | pure-python |
| `arch` | **NCSA** (OSI-approved, permissive) | `numpy`, `pandas`, `scipy`, `statsmodels`, `packaging` | **compiled** |
| `qlib` | **MIT** | (platform) | pure-python |
| `finrl` | **MIT** | (platform) | pure-python |
| `chronos-forecasting` | **Apache-2.0** (README + `LICENSE`) | torch | weights from HF |
| `timesfm` | source **Apache-2.0**; weights **≤ 2.5 Apache-2.0**; **3.0 weights non-commercial** | torch / MLX | weights from HF |
| `hmmlearn`, `ruptures`, `statsmodels`, `darts`, `neuralforecast`, `pymc` | **not verified in this pass** | — | mixed |

### 4.1 Corrections to the evaluated proposal's dependency model

Four of its framing assumptions do not match the verified versions:

- **`statsforecast` takes `statsmodels` as a hard dependency and does not declare `numba`.** The
  proposal's mental model of the Nixtla stack is inaccurate for the verified versions.
- **`arch` is NCSA** — OSI-approved and permissive, but a distinct licence with its own attribution
  clause, not the MIT/BSD/Apache class the proposal groups it with.
- **`mlforecast`'s core dependency is `scikit-learn` + `optuna`.** `LightGBM`/`XGBoost` appear only under
  the `dask`/`ray`/`spark` extras, so the "→ LightGBM/XGBoost" path needs an extra, not just the package.
- **Licensing must be version- and checkpoint-specific, never class-level.** TimesFM's README states
  plainly that *"TimesFM 3.0 pretrained weights are distributed under the separate
  `timesfm-non-commercial-license-v1.0` license … Commercial or production use of downloaded / self-hosted
  weights is **not permitted**"*, while its source and its ≤2.5 weights are Apache-2.0 and commercial 3.0
  use is permitted only through Google Cloud services.

<a id="4-1n"></a>
### 4.1n One review claim refuted by primary source

A review round asserted that `statsforecast`'s current upstream `pyproject.toml` "shows setuptools as the
build backend" and asked that the build-system detail be softened. **That is not what upstream declares.**
Fetched from `main` on 2026-10-03:

```toml
[build-system]
requires = ["scikit-build-core>=1.0.3", "pybind11>=3"]
build-backend = "scikit_build_core.build"
```

So this document states it exactly as verified — **compiled, `scikit-build-core` + `pybind11`** — and keeps
the detail, because a native-extension build is a real admission consideration on Windows. The point is
recorded rather than silently complied with; if a different ref or a fork is the review's source, the
disagreement is about *which ref was read*.

### 4.2 Verified capabilities — and a model-family correction

**`StatsForecast` ships `GARCH` and `ARCH`** (`python/statsforecast/models.py`, their own documented
group), implemented **in-house** — `fit()` calls `garch_model(y, p, q)`, `predict()` calls
`garch_forecast(...)`. It does **not** delegate to `arch`, which is why `arch` is absent from its
dependency list. `predict()` returns **`{"mean", "sigma2"}`**, intervals are `quantile × sqrt(sigma2)`
(Gaussian) unless `prediction_intervals=ConformalIntervals(...)` is passed.

**What it does *not* ship, verified by reading the module:**

| Claimed by the evaluated proposal (V1's member list) | `statsforecast` | `arch` | In-house |
|---|---|---|---|
| `GARCH` / `ARCH` | ✅ `class GARCH`, `class ARCH` | ✅ | ✅ `garch11_fit:438` |
| `GARCH(1,1)-t` (Student-t innovations) | ❌ **no t option** — grep for `student` in `models.py` returns **0** matches | ✅ Student's T **and** GED distributions | ❌ `garch11_fit` is **Gaussian** MLE (no t/skew/GED anywhere in `volatility_models.py`) |
| `FIGARCH(1,1)-t` | ❌ **no FIGARCH class** | ❌ FIGARCH appears in `arch`'s README only under **Contributing** — *"Implement new volatility process, e.g., FIGARCH"* — i.e. an open request, not shipped | ❌ |

**Consequence — recorded, not resolved here.** V1's card (`design_vol_surface_and_vrp.md` §V1, which owns
the member list) names `HAR-RV, GARCH(1,1)-t, FIGARCH(1,1)-t, GRU, XGBoost`. On the verified evidence,
**the two `-t`/FIGARCH members have no confirmed supplier in any candidate library or in-house producer.**
That is a genuine capability gap under FD-1 clause 1 — and it is *not* a reason to admit `arch` wholesale,
since `arch` fails clause 5 for plain GARCH. It is a reason for V1's owner to either drop those members or
scope them explicitly; this document does not decide it (§10).

> **On equivalence.** `StatsForecast.GARCH` and `garch11_fit` both produce GARCH-family conditional
> variance. That overlap establishes an **ownership conflict** under FD-1 clause 5; it is **not** a claim
> of numerical equivalence, and it does not need to be. Two GARCH implementations differ in likelihood,
> distributional assumption, initialization, parameter constraints, optimizer, scaling, horizon handling
> and missing-data policy.

**The evaluated proposal's architectural advice is consistent with this repository's invariant 8** — it
declines "one giant `ForecastScore`" and keeps the score engines independent, which is
`docs/scores/README.md` §2.1 restated.

---

## 5. What is forecastable: the evidence, by target family

### 5.1 The absolute return level — **not admitted**, and that is not the same as "unforecastable"

> **No authoritative absolute return-level forecast is admitted by this design unless a declared producer
> demonstrates out-of-sample incremental value against this repository's prescribed benchmark and passes
> the research-honesty gates.**

That is a **statement about this engine's authorization**, not about markets. Three claims kept apart:

| Claim | Status |
|---|---|
| "A univariate price-history model fitted to one name produces an authoritative expected return" | **Rejected.** This is what the evidence bears on. |
| "Stock returns are not forecastable" (universal) | **Not claimed, and not supported by the cited evidence.** |
| "No absolute return-level forecast is currently authorized in this engine" | **The operative rule.** |

**Hjalmarsson (2006), Fed IFDP 855.** *"Using Monte Carlo simulations, I show that typical out-of-sample
forecast exercises for stock returns are unlikely to produce any evidence of predictability, even when
there is in fact predictability and the correct model is estimated."* His T=600-monthly, c=−20 runs put
the conditional forecast ahead of the constant-return benchmark **on average** only above a true
β ≈ 0.015, with a Diebold-Mariano rejection rate of 5.8% at that β. The instruction that follows — *"you
are often better off setting it equal to zero, rather than using a noisy estimate of it"* — is an argument
about **estimation noise against a small coefficient**, not about the absence of structure.

**Goyal, Welch & Zafirov (2021 SFI WP 21-85; RFS 2024, 37(11) 3490).** 17 original predictors plus 29
variables from 26 post-2008 papers, samples ending 2021: *"Much of the extant literature seems obsolete,
with a majority of variables no longer having empirical support even in-sample. A small number still
perform reasonably well."* Note the last clause: **a small number still work.**

So the rule is a **gate, not a verdict**.

### 5.2 The four return-adjacent targets are different objects

| Target | Meaning | Status |
|---|---|---|
| `absolute_return` | a name's expected absolute return over a horizon | **not admitted** — the weak construction above |
| `relative_return` | return in excess of a benchmark/peer set | distinct question; the cross-section channel |
| `return_rank` | the name's ordinal position in the cross-section | **not admitted on the available evidence; local evaluation may reopen it** (§8.2) |
| `residual_return` | return after market/factor residualization | distinct; `cross_section.residualize_returns:223` already produces the *input* |

The repository's own measurement (`design_cross_section_and_allocation.md` §1, paper 2607.27461): the
**volatility-rank** transition matrix is forecastable with multi-step memory (out-of-sample monthly
log-likelihood gain **0.108**) while the **return-rank** matrix is not (**0.007**); return-rank mean
absolute error sits at 2.5 deciles and covariates do not move it, while the volatility rank's falls from
2.05 to 1.78.

> **Wording note.** v1.1 called `return_rank` "explicitly near-unforecastable", which overstated a
> single-paper result. The status is now phrased as an *admission* decision, consistent with §13.6.

### 5.3 Volatility — forecastable, with HAR-RV as the benchmark to beat

**Corsi (2009), *J. Financial Econometrics* 7(2):174–196.** HAR-RV:

```
RV_{t+1} = c + b_d * RV_t + b_w * RV_w + b_m * RV_m
```

Its abstract records the finding this engine's design already assumes — *"direct time series modeling of
realized volatility strongly outperforms, in terms of out-of-sample forecasting, the popular GARCH and
stochastic volatility models"* — with S&P 500 coefficients b_d=0.372, b_w=0.343, b_m=0.224.

**Leushuis & Petkov (2026), *Financial Innovation* 12:14** (open access). A review of 32 realized-volatility
models from 41 papers, 2000–H1 2024. It reports stronger performance for some deep architectures and
enumerates six empirical properties any model must address. **That evidence is a literature aggregate, not
a measurement on this engine's data, and therefore does not justify adoption without an engine-specific
evaluation** (§8.2).

> The leakage/complexity concern this literature raises is **treated as a risk to be discharged by
> H1/H4/H5/H11** — measured, block-bootstrapped, deflated, base-rate-checked — **not as evidence against
> neural forecasting itself.** The same applies to foundation models: excellent benchmark performance is
> not an admissible producer.

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
   └── learned forecast pool ─ genuine capability gap  → V1 (designed, BLOCKED)
       …plus the `GARCH(1,1)-t` / `FIGARCH(1,1)-t` members, which have NO supplier (§4.2)
```

The repository has most of the forecasting **methods** but no general-purpose **learned forecast-pool
producer** with online scoring and regime-similarity routing. That is V1's item — blocked on a **vendor
state vector** (`VXV` + a HY-spread series), not on a library.

---

## 6. What this repo already owns (verified)

### 6.1 The owners

| Theme | Producer(s), verified | State |
|---|---|---|
| GARCH / ARCH / range / semivariance | `strategies/volatility_models.py:68` `semivariance`, `:155` `parkinson_vol`, `:185` `garman_klass_vol`, `:288` `yang_zhang_vol`, `:332` `yang_zhang_vol_series`, `:397` `ewma_vol`, `:438` `garch11_fit` (Gaussian MLE, `:53` `_IGARCH_AB` guard) | built |
| Jump-robust realized measures | `volatility_models.py` `bipower_proxy` / `quarticity_proxy`, gate `enable_jump_robust_proxies` | built — V6 |
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

- **`arch`** → `garch11_fit` owns GARCH-family conditional variance. Fails FD-1 clause 5.
  `REJECT_DUPLICATE`. *Caveat recorded:* `arch`'s Student-t/GED distributions are the only candidate
  coverage for `GARCH(1,1)-t`, but that does not lift the clause-5 conflict for the GARCH quantity itself;
  the unresolved `-t`/FIGARCH gap belongs to V1's owner (§4.2).
- **`statsmodels`** → its regime/econometric surface is covered by `regime.py` + `covariance_models.py`,
  and it is a **hard dependency of `statsforecast`**, arriving transitively if that is ever admitted.
  `REJECT_DIRECT`.
- **`hmmlearn`** → `hmm_filtered_regime` exists **and feeds `book_risk`'s VaR**. A second regime label is
  the highest-risk duplicate in this table, because two disagreeing labels are indistinguishable from a
  regime change. `REJECT_DUPLICATE`.
- **`ruptures`** → `cusum` + `bocpd` + `spectral_change_read` cover the declared change-point surface.
  `REJECT_DUPLICATE`.
- **`StatsForecast`** → supplies **candidate classical forecasters** for V1's pool (GARCH/ARCH and other
  statistical baselines). It does **not** supply `GARCH(1,1)-t` or `FIGARCH(1,1)-t` (§4.2), and it must not
  be described as doing so. `CONDITIONAL`.
- **`MLForecast`** → **candidate tabular / lag-feature learned members** of the pool (sklearn-compatible
  regressors; XGBoost/LightGBM only with the optional extras admitted). **It is *not* a neural framework —
  a GRU member requires a separate producer implementation** on the PyTorch side. `CONDITIONAL`.

---

## 7. The ForecastContract

The contract is a **declaration**. It computes nothing, and it is deliberately not gated — a declaration
that must be switched on is one nobody uses. The producers it reads are each already individually gated
(`enable_long_memory`, `enable_jump_robust_proxies`, `enable_hmm_heavy_tails`, `enable_bootstrap_intervals`, …).

### 7.1 Three records, two of them immutable

**The v1.1 error this fixes:** v1.1 declared the prediction ledger to hold *"immutable prediction rows"*
and then placed a mutable `evaluation` block **inside** `ForecastRecord`. A record cannot be immutable and
mutated later. The three objects are now separate, and the invariant they buy is the one that matters:

> **A forecast cannot change because a later evaluation changed.** What the model knew at `t` is exactly
> reproducible, and the evaluation is a separate, append-only event keyed to it.

```
# 1. CandidateForecast — a pool MEMBER. Never authoritative, never published.
CandidateForecast
├── candidate_id       : str
├── target             : TargetRef        # same shape as below; the member must declare it
├── frequency          : str
├── horizon_steps      : int
├── forecast_origin    : timestamp
├── model_id           : str              # "har_rv" | "garch11" | "xgboost" | ...
├── model_version      : str
├── value              : float
└── interval           : Interval | None

# 2. ForecastRecord — PRODUCTION-TIME IMMUTABLE. One per authoritative (target, scope, frequency, horizon).
ForecastRecord
├── forecast_id        : str
├── producer_id        : str              # STABLE SEMANTIC OWNER: "forecast_pool.realized_volatility.v1"
├── implementation_ref : str              # repo path, resolves per §7.2 rule 8: "strategies/long_memory.py::rv_forecast"
├── gate               : str | None       # "enable_long_memory" | None
│
├── target                                # MANDATORY (§7.2 rule 7)
│   ├── name           : str              # "realized_volatility" | "return_rank" | ...
│   ├── definition     : str              # the measurement, spelled out
│   ├── definition_version : str          # "realized_volatility.v2" - a redefinition is a NEW target
│   ├── unit           : str              # "annualized_vol" | "probability" | "rank_decile" | ...
│   └── annualization  : int | None       # 252, or None
│
├── entity_scope       : str              # "single_asset" | "sector" | "portfolio" | "index" | "cross_section"
├── frequency          : str              # "1d" | "5m" | "1w"  - 5d@1d is not 5d@5m
├── horizon_steps      : int              # steps in `frequency` units; >= 1
├── forecast_origin    : timestamp        # when all information available to the forecast is FROZEN
│
├── value              : float | None     # None <=> status != "ok"  (NEVER 0.0 as a placeholder)
├── status             : str              # "ok" | "unavailable" | "declined"
├── reason_code        : str | None       # MACHINE-READABLE, closed vocabulary
├── reason_detail      : str | None       # human prose, optional
│
├── interval           : Interval | None  # OPTIONAL (§7.2 rule 5)
│   ├── low            : float
│   ├── high           : float
│   ├── nominal_coverage : float          # 0.90
│   ├── method         : str              # "CQR" | "block_bootstrap" | "gaussian_sigma"
│   └── calibration_ref : str             # the PROCEDURE/VERSION: "H11-CQR-v2" (not a window)
│
└── provenance
    ├── data_snapshot_id : str            # WHICH OBSERVATIONS: "EODHD_20261003_US_EQ_v17"
    ├── training_start   : timestamp
    ├── training_end     : timestamp
    ├── requested_window : int
    ├── effective_window : int
    ├── padded           : bool           # a padded window is BIASED, not merely low-confidence
    ├── missing_obs      : int
    ├── imputed_obs      : int
    ├── adjusted_prices  : bool           # adjusted vs unadjusted changes the economic meaning
    ├── feature_version  : str
    ├── model_version    : str
    ├── parameter_hash   : str
    ├── code_revision    : str            # git SHA of the implementation
    └── calendar_id      : str            # "XNYS" - 22 `1d` steps is not 22 calendar days

# 3. ForecastEvaluation — POST-HOC IMMUTABLE, appended by the ledger. NEVER writable by a producer.
ForecastEvaluation
├── forecast_id        : str              # the key back to the ForecastRecord
├── realized_outcome   : float
├── evaluated_as_of    : timestamp
├── n_observations     : int
├── scoring_rule       : str              # "CRPS" | "QLIKE" | "RMSE" | "MAE"
├── score              : float
├── benchmark_ref      : str
├── benchmark_score    : float
├── benchmark_delta    : float
└── realized_coverage  : float | None     # only for a record that carried an interval
```

The reproducibility tuple is therefore `(data_snapshot_id, model_version, parameter_hash, code_revision,
feature_version)` — four of which v1.1 lacked, which is why two materially different forecasts could have
shared a `model_version`.

### 7.2 The rules

1. **`value is None` iff `status != "ok"`.** A forecast that cannot be made is `unavailable`; it is never
   `0.0` and never a shrunk-to-zero pseudo-number (`NA != 0`, `ScoreContextContract.md`, restated).
2. **One authoritative producer per `(target.name, entity_scope, frequency, horizon_steps)`** — asserted by
   a test. **Candidate member outputs are explicitly exempt** (§3.2): only the pool/selector is
   authoritative, and it publishes exactly one record per key.
3. **`declined` is a first-class status**, distinct from `unavailable`:
   - `ok` — a producer was authorized and produced a value.
   - `unavailable` — authorized, not currently producible. Codes: `INSUFFICIENT_HISTORY`,
     `MISSING_VENDOR_SERIES`, `MODEL_FIT_FAILURE`, `COVERAGE_FAILURE`, `GATE_OFF`.
   - `declined` — the engine **intentionally does not produce this by policy**. Codes:
     `RETURN_LEVEL_NOT_ADMITTED`, `RETURN_RANK_NOT_ADMITTED`, `TARGET_NOT_ADMITTED`.
   A `declined` row is a **cited, reversible policy statement**; an absent row is an invitation.
   *Review note:* a reviewer preferred `not_admitted` to avoid confusion with a trading decision. The
   **owner's ratified term is `declined`** (2026-10-03), so that is what ships; renaming is a one-constant
   change and is recorded in §11 as the owner's call, not taken unilaterally.
4. **`reason_code` is machine-readable** from a closed vocabulary, with optional `reason_detail` prose; a
   test asserts every non-`ok` row carries a code from the vocabulary.
5. **`interval` is optional, and all-or-nothing.** If present, `low`/`high`/`nominal_coverage`/`method`
   are mandatory; if absent, **no interval field may be populated**. A partially populated interval is a
   defect, not a low-confidence band. Production metadata only — `realized_coverage` lives in
   `ForecastEvaluation` (§7.1), never here.
6. **A state read is not a forecast.** `horizon_steps >= 1` is required. A regime/current-state read
   belongs in the score/state contracts — otherwise `ForecastRecord(key="regime.current", horizon=0)`
   appears and the forecast namespace becomes a generic analytics namespace, destroying the ledger's
   ability to reason.
7. **No forecast without a target definition.** `target.name`, `target.definition`,
   `target.definition_version`, `target.unit`, `entity_scope`, `frequency` and `horizon_steps` are
   mandatory. This matters because the repo carries at least nine distinct volatility concepts
   (`ewma_vol`, `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `garch11_fit`, realized vol,
   `semivariance`, `bipower_proxy`, `quarticity_proxy`) — **a forecast of one is not interchangeable with
   a forecast of another** — and because the same target name recurs across scopes.
8. **`producer_id` is the stable identity; `implementation_ref` is the current location.** Code paths move
   during refactoring; the semantic owner does not. Both are recorded, with `code_revision` pinning the
   exact implementation version. **`implementation_ref` is written as a repo path relative to the code
   package root** — `strategies/long_memory.py::rv_forecast` — and **resolves by a fixed transform**: strip
   the `.py`, map `/` → `.`, prefix `tradingagents.`, split on `::`, then
   `importlib.import_module("tradingagents.strategies.long_memory")` → `rv_forecast`. **The prefix is
   mandatory at resolution time**, because a *top-level* `strategies/` directory also exists and it is the
   **docs vault** (notes only — no `.py`, no `__init__.py`); the bare form alone is ambiguous and does not
   import. A **new** module is therefore named with its full path in this document's plan.
9. **Provenance is mandatory**, including `padded`, `data_snapshot_id` and `calendar_id`. The corpus's
   temporal-coverage-bias result is that a padded window *suppresses measured volatility in a known
   direction* — biased, not merely uncertain — and `adjusted_prices` changes the economic meaning of a
   return series while leaving the arithmetic reproducible.

### 7.3 The target vocabulary

Declared once, so `producer_id` stays a name rather than a semantic soup:

```
target.name ∈ { absolute_return, relative_return, return_rank, residual_return,
                volatility, variance, volatility_rank,
                regime_probability, regime_stress_probability }
entity_scope ∈ { single_asset, sector, portfolio, index, cross_section }
unit        ∈ { annualized_vol, variance, probability, rank_decile, pct, raw_return_bps }
```

Key/horizon are **separated**, not combined, and scope is part of the identity:

```
target.name="realized_volatility"  entity_scope="single_asset"  frequency="1d"  horizon_steps=1
target.name="volatility_rank"      entity_scope="cross_section" frequency="1d"  horizon_steps=22
target.name="regime_stress_probability" entity_scope="index"    frequency="1d"  horizon_steps=5
```

(`v1.0` wrote keys such as `rv.d1`, encoding the horizon inconsistently and carrying no scope.)

### 7.4 What the contract does not do

- It is **not** a module that computes anything — declarations, a registry and tests.
- It does **not** add a member to `COMPOSITE_ENGINES`.
- It does **not** put a return forecast on the decision path (`kelly_weights`' declaration boundary, §2).
- It does **not** accept state reads (§7.2 rule 6).
- Candidate outputs are **not** `ForecastRecord`s and never reach the ledger as authoritative (§3.2).

---

## 8. From forecast to admissible evidence

### 8.1 The wiring

```
candidate models ──► pool/selector ──► ForecastRecord (immutable)
                                              │
                                              ▼
                            strategies/prediction_ledger.py
                                              │
                              realized outcome resolves
                                              ▼
                            ForecastEvaluation (immutable, appended)
                                              │
        point:  MAE / RMSE            ── vs benchmark
        dist:   CRPS / QLIKE          ── vs benchmark
        band:   realized coverage     ── vs nominal
                                              ▼
        H1 (trial ledger, deflation) · H4 (accuracy ceiling / base rate)
        H5 (five-gate verdict) · H10 (coverage) · H11 (autocorrelation-aware intervals)
                                              ▼
                                  admission / continued use
```

One-way, enforced by test: **the ledger scores the producer; the producer never scores itself.** A
producer has no write access to `ForecastEvaluation`.

### 8.2 Every forecast family needs a declared benchmark

A forecast does not get credit for producing a number.

| Target family | Benchmark |
|---|---|
| `volatility` / `variance` | **HAR-RV** (Corsi) and naive trailing realized vol; GARCH as a third reference |
| `absolute_return` | **zero-return** *and* **expanding historical mean** *and* **rolling historical mean** — three distinct hypotheses, not one line |
| `relative_return` / `residual_return` | the appropriate factor baseline (sector-neutral, beta-neutral as applicable) |
| `return_rank` / `volatility_rank` | **cross-sectional persistence** (today's rank) and a **rank-neutral / cross-sectional-mean** baseline |
| `regime_probability` | persistent-state (sticky) Markov baseline |
| any `interval` | naive empirical quantile band (`conformal.iid_interval` is the floor, and its own module comment says to read the *realized* coverage, never the nominal level) |

Plus the repo's existing discipline: `2602.07841`'s **nontrivial upper bound on the out-of-sample R²** (the
H-theme's ceiling for any return-forecast claim) and `H4`'s base-rate ceiling for every directional claim.

---

## 9. Per-library verdict

Reasons are categorized so a future contributor re-opens the *right* argument rather than the whole row.

| Candidate | Verdict | Reason |
|---|---|---|
| `statsforecast` | **CONDITIONAL** | **Candidate classical forecasters** for a declared pool (GARCH/ARCH + statistical baselines). Does **not** supply `GARCH(1,1)-t` or `FIGARCH(1,1)-t` (§4.2). Offline refit only (ground rule 8). Requires FD-1 cl. 3–4 + §8.2 benchmark. |
| `mlforecast` | **CONDITIONAL** | **Candidate tabular/lag-feature learned members** (sklearn-compatible). **Not** a neural framework — a GRU member needs a separate implementation. Brings `scikit-learn` + `optuna`. |
| `arch` | **REJECT_DUPLICATE** | `garch11_fit` owns GARCH-family conditional variance (FD-1 cl. 5). Its Student-t/GED surface is noted; that does not lift the conflict for the GARCH quantity (§6.2). |
| `statsmodels` | **REJECT_DIRECT** | Existing `regime`/`covariance_models` surface; transitive via `statsforecast` if admitted. |
| `hmmlearn` | **REJECT_DUPLICATE** | `hmm_filtered_regime` exists and feeds `book_risk`'s VaR. |
| `ruptures` | **REJECT_DUPLICATE** | `cusum` + `bocpd` + `spectral_change_read`. |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | **REJECT_NO_CONSUMER** | No declared producer; large compiled/torch dependency surface. |
| `pymc`, `pyro`, `tensorflow-probability` | **REJECT_NO_CONSUMER** | No declared probabilistic producer; `conformal.py` already supplies calibrated bands. |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | **REJECT_THIS_PASS** | No declared consumer **and no demonstrated incremental value**. Reopening requires a separate **code-licence / checkpoint-licence / hardware / reproducibility / leakage** evaluation — TimesFM 3.0's non-commercial weights (§4.1) are the worked example. |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | **REJECT_NO_RESEARCH_CASE** | No research case; agreed with the evaluated proposal's own Tier 4. |
| `qlib`, `finrl` | **ALREADY_COVERED** | Their *territory* is already evaluated/covered by existing design+plan pairs and in-house modules (`factor_expressions`, `signal_analysis`, `portfolio_strategy`, `market_tradability`). Neither is an installed or authoritative producer — so **not** `ALREADY_OWNED`, which means something stronger in this architecture. |

**Today's net dependency change: zero.**

### 9.1 Offline boundary — these are not runtime dependencies

Admission, when it ever happens, is **refit-environment** admission only:

```
refit / research environment            TradingAgents + signald runtime
   ├── statsforecast                       └── consumes a versioned forecast
   ├── mlforecast                              artefact (data_snapshot_id +
   ├── lightgbm / xgboost (extras)             model_version + parameter_hash +
   └── optuna                                  code_revision)
        └── emits a versioned artefact
```

A `CONDITIONAL` verdict must **never** be read as "add this to the main project's runtime dependencies".
Ground rule 8 already forbids calling a refit from `prepare_initial_state`, `finalize_run` or any agent
tool; this makes the deployment shape explicit.

---

## 10. Non-goals

- **V1's volatility forecast pool and its member list** — owned by `design_vol_surface_and_vrp.md` §V1. §4.2
  **records** that two of its named members have no supplier; it does not re-scope the item.
- **V2's memory parameter and HAR forecast** — owned by the same doc; **built** as `strategies/long_memory.py`.
- **Regime (R1–R9), tails/drawdown (K1–K6), cross-section (X1–X8), evaluation gates (H1–H11)** — each owned
  by its `docs/paper_survey_26/` pair. Cited here, never restated.
- **The score set and `COMPOSITE_ENGINES`** — owned by `docs/scores/README.md`.
- **`recommended_allocation_pct`'s unit and the `size_pct_book` documentation gap** — a cross-repo contract
  matter settled 2026-10-03 (§11.2).
- **Report verification** — unrelated ownership.

---

## 11. Owner decisions — the freeze boundary, then the register

### 11.0 The freeze boundary (declared 2026-10-03)

**Frozen at v1.2.** Changing any row below is a **design revision**, not an implementation-item edit:

| frozen surface | where |
|---|---|
| `CandidateForecast` / `ForecastRecord` / `ForecastEvaluation`, and the two-immutable split | §7.1 |
| FD-1's five clauses and the candidate-output exemption | §3, §3.2 |
| capability ownership (cl. 1) vs quantity ownership (cl. 5) | §3.1 |
| one **authoritative** producer per `(target.name, entity_scope, frequency, horizon_steps)` | §6, §7.3 |
| forecast ≠ score ≠ signal ≠ decision | §2 |
| the evidence/evaluation boundary — `ForecastEvaluation` is post-hoc and ledger-written | §7.1, §8.1 |
| the library verdict categories (`CONDITIONAL` / `REJECT_*` / `ALREADY_COVERED`) | §9 |

**Downstream of the freeze.** The four open items below (§11.3–§11.6: the licence-tier default, `declined`
vs `not_admitted`, V1's unsupplied `-t`/FIGARCH members, V1's vendor unblock) belong to the **implementation
and owner workflow**, not to this document. **FL-1…FL-7 execute without any of them being settled** — none is
a precondition for the contract, the registry, the refusal rows, the admission test, the ledger wiring or the
benchmark declaration.

**The governance rule.** A downstream decision that would change FD-1, the `ForecastContract`'s semantics, or
authoritative ownership **is a design change**: it must return here as a numbered revision, name what it
invalidates, and update §12. It may never ride in silently on an FL item's diff.

### Answered (owner, 2026-10-03)

1. **`absolute_return` and `return_rank` ship as `declined` rows** — with reason codes and citations
   (§7.2 rule 3). Not omitted: a cited refusal is harder to silently reverse than an absent field.
2. **This repo's `contracts/research_decision.v1.schema.json` is the authoritative side** of the
   research↔execution contract. `../TradingExecution/contracts/` was synced to it, and the settlement
   exposed a 100× unit defect on the executor's side (`recommended_allocation_pct` read as a fraction
   whenever it was ≤ 1.0), fixed there with a failing-first test.

### Open

3. **Is the dependency policy "MIT/BSD/Apache by default"?** §4's licence table makes the tiers concrete:
   **default** MIT/BSD/Apache; **other OSI-approved permissive licences (incl. NCSA) allowed only after
   explicit review**; **non-OSI, custom and model-checkpoint licences always require explicit review.**
   This replaces v1.1's self-contradictory phrasing, which called NCSA "not permissive" while also
   proposing "permissive OSI only" — NCSA *is* OSI-approved and permissive.
4. **`declined` vs `not_admitted`** — a reviewer prefers `not_admitted` (no collision with a trading
   decision). The owner's ratified term is `declined`; renaming is one constant. Owner's call.
5. **V1's `GARCH(1,1)-t` / `FIGARCH(1,1)-t` members** — §4.2 shows no supplier. V1's owner must either drop
   them or scope them to a producer that would have to be built. Recorded, not decided here.
6. **V1's vendor unblock** — `VXV` and a HY-spread series are not confirmed live vendor calls.

---

## 12. Review dispositions

### 12.1 v1.0 → v1.1 (29 points — all accepted; see the v1.1 revision note in `CHANGELOG.md`)

### 12.2 v1.1 → v1.2

| # | Review point | Disposition |
|---|---|---|
| 1 | Distinguish capability ownership from quantity ownership | **Accepted** — §3.1 |
| 2 | **`ForecastRecord` is not immutable** — evaluation mutates it | **Accepted (P0)** — §7.1 splits `ForecastRecord` (production, immutable) from `ForecastEvaluation` (post-hoc, appended by the ledger) |
| 3 | `forecast_origin` meaning is wrong | **Accepted** — §7.1: "when all information available to the forecast is frozen" |
| 4 | **Candidate models vs the one authoritative producer** | **Accepted (P0)** — §3.2 + §7.2 rule 2 exempts candidates; §7.1 adds `CandidateForecast` |
| 5 | `producer` should not be a code path | **Accepted** — `producer_id` (stable) + `implementation_ref` + `code_revision` |
| 6 | Provenance needs `data_snapshot_id`, `code_revision`, `parameter_hash`, `feature_version`, `calendar_id` | **Accepted** — §7.1 |
| 7 | `interval` should be optional + all-or-nothing | **Accepted** — §7.2 rule 5 |
| 8 | `calibration_ref` = procedure/version, not a window | **Accepted** — `"H11-CQR-v2"` |
| 9 | `declined` → `not_admitted` | **Not taken — owner's ratified term is `declined`.** Recorded in §7.2 rule 3 and §11.4 as the owner's call |
| 10 | Tighten `return_rank` language | **Accepted** — §5.2 |
| 11 | **StatsForecast is not the `GARCH(1,1)-t`/`FIGARCH(1,1)-t` source** | **Accepted, and extended** — §4.2 verifies it independently and finds the members have **no supplier anywhere**, incl. in-house (Gaussian-only) and `arch` (t yes, FIGARCH unimplemented) |
| 12 | Narrow MLForecast's role | **Accepted** — §6.2, §9 |
| 13 | "StatsForecast's build backend is setuptools" | **REFUTED by primary source** — §4.1n. Upstream `main` declares `build-backend = "scikit_build_core.build"` |
| 14 | Sharpen the return benchmarks | **Accepted** — §8.2 (zero vs expanding mean vs rolling mean; persistence + rank-neutral) |
| 15 | The pool needs a formal owner | **Accepted** — §1 diagram, §3.2, `producer_id = forecast_pool.<target>.v1` |
| 16 | `horizon` → `horizon_steps`; add `calendar_id` | **Accepted** — §7.1, §7.3 |
| 17 | Add `entity_scope`; widen the uniqueness key | **Accepted** — §7.1, §7.2 rule 2, §7.3 |
| 18 | Version the target definition | **Accepted** — `target.definition_version` |
| 19 | `data_version` → `data_snapshot_id` | **Accepted** — §7.1 |
| 20 | `qlib`/`finrl` → `ALREADY_COVERED` | **Accepted** — §9 |
| 21 | Keep §13 | **Retained** |
| 22 | Licence-policy wording is self-contradictory (NCSA *is* OSI permissive) | **Accepted** — §11.3, three explicit tiers |
| 23 | Make the offline dependency boundary explicit | **Accepted** — §9.1 |
| 24 | Make the leakage sentence operational | **Accepted** — §5.3 (a risk discharged by HH-1/H4/H5/H11) |
| 25 | Replace the architecture diagram | **Accepted** — §1 |
| 26 | Final contract shape | **Accepted with the P0 split** — §7.1 |
| 27 | Disposition table | **Accepted** — this table |

### 12.3 Post-freeze revision 1 — the regime benchmark is now producible (D5)

**Numbered revision, per §11.0.** The reading of the `E:\fin paper` corpus
(`Strategies/books/`) verified that §8.2's `regime.sticky_markov` benchmark ref
named a method **no producer implemented**: the string occurred only in
`forecast_registry.py` (`:195`, `:196`, `:269`) and no `sticky_markov` existed in
`regime.py` or anywhere else. The `regime_stress_probability` row was `status="ok"`
while its declared benchmark could never be scored.

**What changed.**

| surface | before | after |
|---|---|---|
| `strategies/regime.py` | no sticky-Markov estimator | `sticky_markov(states, *, threshold_quantile=None)` — two-state maximum-likelihood transition counts, `p_stay`, and the stationary law; an absorbing chain reports `unavailable` rather than `p_stay = 1` |
| `forecast_registry.BENCHMARK_IMPLEMENTATIONS` | (did not exist) | a ref → `(module, symbol)` map, resolved against the live tree by `tests/test_forecast_registry.py`, so a ref can no longer claim a producer that has been renamed away |
| `scripts/forecast_ledger.py` | took `--benchmark-score` on trust | refuses to score when a bound ref does not resolve, and reports `benchmark_ref` / `benchmark_implementation` |

**What this does NOT change.** FD-1's five clauses, the three-record contract and
its two-immutable split, capability-vs-quantity ownership, the one-authoritative-
producer rule, the evidence/evaluation boundary and the §9 verdict categories are
untouched (§11.0). The other eleven declared benchmark refs remain
**declaration-only labels** — their documented state (§5 of
`Strategies/books/FINDINGS.md`): the caller supplies the benchmark's score to
`prediction_ledger.evaluate_forecast`. `BENCHMARK_IMPLEMENTATIONS` names only the
refs whose *method* this repo implements.

**Why it is a revision and not an FL item.** A benchmark ref is a contract with
the caller: it says what a row must beat. A ref that resolves to nothing makes that
contract unverifiable — the same class of defect as the wiring gate's `__all__`
hole, a declaration that reads as enforcement. E15 in
`Strategies/books/FINDINGS.md` §4 is the enhancement this discharges.

---

## 13. Honest limits

1. **No library was evaluated for forecast quality on this engine's production universe.** Library
   capability is not evidence of financial usefulness — §4 establishes what a package *contains*, never
   that it *works here*.
2. **No item here is backtested** — this document authorises no build.
3. **Seven licences were verified from source** (`statsforecast`, `mlforecast`, `arch`, `qlib`, `finrl`,
   `chronos`, `timesfm`); **every other library in §9 is marked unadmitted rather than assumed
   permissive**, and several (`hmmlearn`, `ruptures`, `statsmodels`, `darts`, `neuralforecast`, `pymc`)
   were not verified because their verdicts do not turn on the licence.
4. **`statsforecast`'s `GARCH` was read in source but never executed.** That `predict()` returns
   `{"mean","sigma2"}` is a read of its return dict. `[INFERENCE]` for the behaviour, fact for the code.
5. **The `-t`/FIGARCH absence (§4.2) is a *negative* read** — "no such class in `models.py`", "no
   `student` match", "FIGARCH listed under Contributing". A negative read is strong here because the
   module is explicit about its model roster, but it is a read of one ref on one day.
6. **`return_rank`'s `declined` status rests on one paper's measurement** (2607.27461's 0.007 vs 0.108),
   which is the best available evidence here but is not this engine's own measurement. §8.2 names the
   benchmark that would settle it locally.
7. **This document's `CONDITIONAL` verdicts could be wrong.** If V1 unblocks and its learned members cannot
   be expressed with the in-house regressions, `statsforecast`/`mlforecast` may be the cheapest correct
   answer — which is why they are conditional and why FD-1 is an admission rule rather than a ban.
8. **FD-1 is a rule, not an enforcement.** The plan's FL-4 tests that a verdict was recorded; it cannot
   tell whether the verdict was right.

---

## References

- Hjalmarsson, E. (2006). Fed IFDP 855. <https://www.federalreserve.gov/pubs/ifdp/2006/855/ifdp855.pdf>
- Goyal, A., Welch, I., & Zafirov, A. (2021/2024). SFI WP 21-85; *Review of Financial Studies* 37(11) 3490.
- Corsi, F. (2009). *J. Financial Econometrics* 7(2):174–196.
- Leushuis, R. M., & Petkov, N. (2026). *Financial Innovation* 12:14. DOI 10.1186/s40854-025-00809-5.
- Nixtla `statsforecast` `pyproject.toml` (build backend: `scikit_build_core.build`) + `python/statsforecast/models.py` (`class GARCH`, `class ARCH`; no FIGARCH; no Student-t) — main, 2026-10-03.
- Nixtla `mlforecast` `pyproject.toml` (core: `scikit-learn` + `optuna`; LightGBM/XGBoost in extras).
- Sheppard, K. `arch` `README.md` — NCSA; ARCH/GARCH/TARCH/EGARCH/EWMA; Normal/Student-T/GED; **FIGARCH listed only under Contributing**.
- `google-research/timesfm` `LICENSE` + README licence notice; `amazon-science/chronos-forecasting` `LICENSE` + README.
- Microsoft `qlib` LICENSE (MIT); AI4Finance `FinRL` LICENSE (MIT).
- Internal: `design_fin_paper_survey_26.md` §3/§5; `paper_survey_26/design_vol_surface_and_vrp.md`
  §2/§V1/§V2/§5; `paper_survey_26/design_cross_section_and_allocation.md` §1; `MASTER_DESIGN.md` §2;
  `docs/scores/README.md` §2.1; `CHANGELOG.md` (*"Rejected outright"*).
