# Statistical & Econometric Methodology

`book 17/19` · slug `stat-methodology` · 1037 papers in the corpus · 133 rated high-relevance by the sweep

## 0. Scope

This category is the estimation layer under every other category: how to estimate a
memory parameter, a Hurst exponent, a GARCH variance, a time-varying hedge ratio, a
conditional quantile, a VaR, a covariance spectrum, and how to attach honest
uncertainty to each. It matters to this repo because TradingAgents' governing rule is
*compute, don't narrate* - and a computed number is only as good as the estimator and
the inference behind it. The recurring failure mode the corpus documents is not a wrong
point estimate but a missing standard error: IID-honest tests reported on serially
dependent, heteroskedastic, thick-tailed financial data.

## 1. Corpus composition

The sweep annotated **1037** papers for this category (**133** high, 661 medium,
243 low). Decade counts below use the 133 high-relevance rows (the only rows in the
evidence pack carrying a year per row); the primary-category counts use the 60-paper
booklist, which is the ranked top of the category and therefore skewed toward the
sweep's own interests.

| Decade | High-relevance rows | Share |
| --- | --- | --- |
| 2000s | 19 | 14% |
| 2010s | 44 | 33% |
| 2020s | 70 | 53% |
| **Total** | **133** | **100%** |

| arXiv primary category | Booklist (top 60) |
| --- | --- |
| q-fin.ST | 24 |
| math.ST | 12 |
| stat.ME | 8 |
| econ.EM | 4 |
| q-fin.CP | 3 |
| cs.LG | 3 |
| stat.ML | 2 |
| q-fin.RM | 2 |
| q-fin.TR | 1 |
| cs.AI | 1 |

The category is dominated by two traditions: the econometrics of financial time series
(q-fin.ST, econ.EM) and mathematical statistics for stochastic processes (math.ST,
stat.ME) - together ~80% of the booklist. Almost half the high-relevance rows are from
2020 or later, and the 2023 cohort (28 rows) is the single densest year, driven by the
rough-volatility and high-frequency-estimation literature. Very little of the category
is directly tradeable; its value to this repo is the estimator-and-inference discipline
it supplies, not signals.

## 2. Deep reads

### 2605.24285v1 - Memory, Roughness, and Information Persistence in Financial Markets
- **Question.** Do rolling long-memory and rough-volatility measures carry incremental
  forecasting information beyond HAR/HAR-X, and do they behave coherently across regimes?
- **Data.** Panel of 115 S&P 500 constituents, November 2001-April 2026; daily squared
  returns, Parkinson range, realized variance.
- **Method.** Semiparametric GPH log-periodogram and local-Whittle `d`; rolling Hurst
  `H` for local roughness; persistence-augmented HAR / HAR-X regressions, shrinkage and
  tree ensembles.
- **Finding.** Volatility proxies show substantial long memory: cross-sectional mean
  `d_GPH = 0.226`, `d_local-Whittle = 0.440`, significant across nearly the whole panel.
  Rolling persistence rises in the GFC and COVID episodes and co-moves positively with
  VIX. Persistence features give moderate but significant forecast gains, strongest at
  longer horizons and in stress; economically structured feature design beats tree ML.
- **Limitation.** The paper explicitly refuses structural identification: near-integrated
  GARCH, structural breaks and microstructure noise can all *mimic* fractional
  dependence, so `d` is a reduced-form summary, not evidence of a fractional law.

### 1608.01895v3 - Semiparametric estimation and inference on the fractal index
- **Question.** Under what assumptions is the standard fractal-index (roughness)
  estimator valid, and what happens when observations carry measurement noise?
- **Data.** Simulation plus two empirical sets: turbulent velocity flows and a financial
  price series.
- **Method.** Variogram-based OLS estimator of the fractal index `alpha` for Gaussian and
  (via volatility modulation) conditionally Gaussian processes; a noise-robust estimator
  and a formal test for the presence of noise.
- **Finding.** Measurement noise biases the fractal index **downwards**, making a series
  look *more rough* than the underlying process. The paper proposes a practical bandwidth
  choice that differs from common practice and proves the conditionally-Gaussian extension.
- **Limitation.** The robust estimator and noise test are asymptotic; the paper is a
  theory-and-recommendations chapter, not an empirical rougher-than-Brownian proof.

### 2006.02077v4 - AdaVol: An Adaptive Recursive Volatility Prediction Method
- **Question.** Can GARCH-family QML be estimated recursively and stably in streaming,
  large-scale settings where batch optimizers are prohibitively expensive?
- **Data.** Simulated GARCH and a real stock-index series.
- **Method.** Stochastic-approximation recursive QML combined with Variance Targeting
  Estimation (VTE); O(d) per recursion, one pass over the data.
- **Finding.** The QML criterion is **not convex** (it behaves like a concave function of
  the log term), so batch optimizers are start-value sensitive; VTE alleviates the
  convergence difficulties that arise when the true parameter sits near the boundary of
  the parameter space, and the recursive estimator trades stability against adaptability.
- **Limitation.** Asymptotic guarantees require the contraction/Lipschitz-moment
  conditions; the paper gives no finite-sample interval procedure.

### 2607.06690v1 - tsbootstrap: Distribution-Free UQ and Conformal Prediction for Time Series
- **Question.** Which dependence-aware bootstrap and conformal method actually preserves
  nominal coverage on serially dependent streams?
- **Data.** 800,000 simulated percentile intervals: five DGPs (white noise, AR(1) phi=0.9,
  MA(2), AR(1)+ARCH(1), ARFIMA(0,0.4,0)), 5,000 datasets each, B=999, alpha=0.10.
- **Method.** Block (moving/circular/stationary), residual, sieve and wild resampling plus
  adaptive conformal calibrators (EnbPI, ACI, NexCP, AgACI); automatic block length by the
  Politis-White spectral-density rule with the Patton correction.
- **Finding.** The IID bootstrap **undercovers sharply** under dependence: at 90% nominal
  the AR(1) coverage collapses to **27.8%** (IID), rising to 69.7% (moving block), 70.2%
  (stationary block) and **83.1% (sieve)**, nearest nominal under short-memory linear
  dependence; AR+ARCH recovers to **89.1%** under the sieve. Under ARFIMA long memory
  **no method reaches acceptable coverage** (IID 8.2%, best block 28.9%): the library
  exposes the method choice rather than imposing a default.
- **Limitation.** The coverage study is on the mean functional and one fixed statistic
  path; the compiled speedup applies only to the fixed-statistic reducer.

### 0706.1836v1 - Long Memory in Nonlinear Processes
- **Question.** How do nonlinear long-memory models explain why *squared/absolute* returns
  show long memory while *returns* do not?
- **Data.** Survey chapter with theory and cited empirics.
- **Method.** LMSV/LMSD (long-memory stochastic volatility/duration), shot-noise and
  point-process long-memory models; semiparametric Hurst/`d` estimation.
- **Finding.** Returns are typically uncorrelated while their squares or absolute values
  exhibit long memory; the memory parameter is `d = H - 1/2`, and the chapter catalogs
  models that generate this asymmetry without a fractional linear process in the raw
  series. This is the theoretical basis for running memory estimation on `|r|` or `r^2`,
  not on `r`.
- **Limitation.** A review, not a new estimator; most of the models are parametric and
  identified only with long samples.

### 1605.00868v2 - The Local Fractional Bootstrap
- **Question.** Finite-sample inference on path roughness (fractal index) is poor when
  based on the asymptotic CLT; can a bootstrap repair it?
- **Data.** Simulation plus high-frequency asset prices and atmospheric turbulence.
- **Method.** The local fractional bootstrap simulates an auxiliary fractional Brownian
  motion that mimics the fine high-frequency differences of a Brownian semistationary
  process under the null, then builds the roughness test from a ratio of realized power
  variations.
- **Finding.** The bootstrap-based test delivers **considerable finite-sample improvement
  over the CLT-based test**, which matters most precisely when the investigation is
  roughness of a real time series at moderate sample sizes.
- **Limitation.** Validity is proven for the BSS class; the driftless-kernel and
  volatility-modulation assumptions must hold for the auxiliary fBm to be the right null.

### 2607.28294v1 - Bootstrap Inference in Autoregressive Duration Models
- **Question.** For ACD models observed over a fixed calendar span - so the *number* of
  durations is random - which bootstrap scheme remains valid when durations have infinite
  mean?
- **Data.** Monte Carlo plus an empirical application to cryptocurrency ETFs.
- **Method.** Fixed-count vs random-count recursive bootstrap schemes; limit theory for
  heavy-tailed/integrated ACD linked to renewal theory with random sample sizes.
- **Finding.** When the duration tail index `kappa < 1` the estimator has a mixed-normal
  limit and classical bootstrap consistency fails, but the fixed-count bootstrap still
  reproduces the conditional Gaussian component, so percentile intervals stay first-order
  valid and bootstrap t-statistics are asymptotically standard normal. It stays robust to
  non-exponential innovation misspecification.
- **Limitation.** The fixed-count bootstrap's implied time span need not equal the
  original `T`; the theory is specific to the ACD/MEM family.

### 0907.5276v1 - Bayesian Inference on QGARCH Using the Adaptive Construction Scheme
- **Question.** Can MCMC reliably estimate the four-parameter asymmetric QGARCH model,
  given that ML is start-value sensitive?
- **Data.** Artificial QGARCH series.
- **Method.** Metropolis-Hastings with a proposal density built adaptively from the
  posterior samples themselves (no ML pre-fit of the proposal).
- **Finding.** The adaptive construction scheme samples QGARCH parameters effectively -
  serial correlations between draws are very small even with the extra asymmetry
  parameter - and is an efficient alternative to ML for the asymmetric GARCH family.
- **Limitation.** Purely synthetic; no empirical index application, no predictive
  comparison against QMLE.

### 2203.08224v4 - Predicting Value at Risk for Cryptocurrencies With Generalized Random Forests
- **Question.** Do nonparametric quantile methods beat parametric GARCH/CAViaR for VaR on
  highly volatile assets?
- **Data.** Daily log-returns of 105 major cryptocurrencies, 07/2010-04/2024.
- **Method.** Generalized Random Forests (Athey-Tibshirani-Wager) adapted to quantile
  prediction, with covariates for volatility, liquidity and supply; rolling-window
  out-of-sample VaR backtests against GARCH, GJR-GARCH, quantile regression and CAViaR.
- **Finding.** GRF has **superior VaR-forecasting performance**, and the advantage is
  *especially pronounced in unstable times* and for the most volatile asset classes; for
  stablecoins GJR-GARCH and quantile regression can compete. Long-horizon standard
  deviations that matter in calm times cease to be relevant predictors in unstable times.
- **Limitation.** Crypto-specific; the wins are on coverage/quantile-score metrics, not
  on a trading P&L.

### 2011.00552v3 - Mixed-frequency quantile regressions to forecast VaR and Expected Shortfall
- **Question.** Can a quantile regression directly estimate VaR and ES while blending
  low-frequency and high-frequency predictors?
- **Data.** WTI crude-oil and RBOB gasoline futures, January 2010-July 2022 (covers
  COVID and the Ukraine shock).
- **Method.** MF-QR(-X): the quantile regression constant is a function of low-frequency
  variables (e.g. the geopolitical-risk index) and the daily component uses realized
  measures; weak-stationarity conditions derived, extensive Monte Carlo, VaR/ES
  backtests against parametric and nonparametric rivals.
- **Finding.** The mixed-frequency quantile model **outperforms competing specifications**
  on standard VaR and ES backtesting procedures, without a distributional assumption on
  the innovations, and jointly forecasts VaR and ES via the asymmetric Laplace density.
- **Limitation.** Two energy futures only; the low-frequency component must be chosen
  ex ante and is not selected data-adaptively.

### 2404.16449v1 - Analysis of Market Efficiency Using a Kalman Filter
- **Question.** Can a two-stage Kalman filter extract a trendline that predicts price
  reversals, and does it differ across market types?
- **Data.** Major developed and emerging stock-market indices (Korea, Vietnam, Malaysia,
  UK, Europe, Japan, Hong Kong).
- **Method.** Two-stage Kalman filter assuming the data contains a consistent trendline
  (the true value) observed with noise; the deviation of price from the filtered
  trendline becomes a price-reversal indicator, backtested as a portfolio.
- **Finding.** The Kalman-filter-based price-reversal indicator yields **significant
  portfolio returns in emerging markets** and positive returns in developed markets,
  consistent with weaker efficiency in emerging markets.
- **Limitation.** A short conference-style paper; parameter/state-noise choices are not
  systematically optimized and the reversal indicator is evaluated only as a raw signal.

### 2309.02205v1 - On statistical arbitrage under a conditional factor model of equity returns
- **Question.** Can a state-space conditional factor model define fair value for
  multivariate equity statistical arbitrage?
- **Data.** US equities, 29-year history, with realistic transaction costs.
- **Method.** Asset returns are noisy observations of a linear combination of factor
  values and latent time-varying factor risk premia; the Kalman filter (linear) and
  Unscented Kalman filter (nonlinear) recover filtered risk premia online; large
  deviations of observation from filtered return are mean-reversion candidates.
- **Finding.** The conditional factor state-space model is **useful for mid-frequency
  statistical arbitrage**, competitive against benchmarks and published methods, and
  time-varying risk premia capture non-stationarity by construction - though performance
  degrades in the most recent years.
- **Limitation.** The nonlinear state-space model's gains are model-dependent; the
  degradation over time suggests the factor structure itself drifts.

### 2602.07046v5 - Do Crypto Markets Differentiate Infrastructure from Regulatory Shocks?
- **Question.** Does an event-study's significance survive once event inclusion and
  dependence are treated honestly?
- **Data.** 50 crypto events, six assets, January 2019-August 2025.
- **Method.** GJR-GARCH-X with a dependence-aware inference ladder: conditional fixed-path
  Student-t copula bootstrap, floored recursive sensitivity, event-level block bootstrap;
  event inclusion treated as an explicit design parameter.
- **Finding.** A curated high-salience screen gives a **3.49x** variance multiplier, but it
  is selection-conditional (0.5-1.6x on a broad pool) and **not significant** under the
  copula bootstrap (p ~= 0.39). A naive IID test treating the six per-asset coefficients as
  independent samples had produced "apparently decisive" significance that **does not
  survive dependence and heavy-tail corrections**; the six-contrast effective sample size
  is only **1.33-2.35**.
- **Limitation.** A single event-study sample; the paper's own verdict is "directional,
  selection-conditional, inference-scheme-sensitive, unresolved".

### 2506.04656v1 - Classification of Extremal Dependence in Financial Markets via Bootstrap Inference
- **Question.** How can clusters of extreme co-movement be identified without a
  parametric tail model?
- **Data.** Absolute log returns of S&P 500 and Chinese A-share stocks.
- **Method.** A bootstrap-based testing procedure for multivariate regular variation /
  asymptotic dependence, applied to large panels.
- **Finding.** The US economy shows **more isolated clustering** of dependent assets than
  China, which is **more interconnected** in extremal dependence; cross-market links are
  strong in materials, consumer staples and consumer discretionary. The bootstrap makes a
  large-scale empirical tail-network classification feasible.
- **Limitation.** The method classifies asymptotic dependence vs independence rather than
  a continuous tail-dependence coefficient.

### 2503.13950v1 - Asymptotic Properties of the GLS Estimator with Heteroskedastic and Autocorrelated Errors
- **Question.** Which Wald test keeps nominal size in multivariate regression under both
  heteroskedasticity and autocorrelation?
- **Data.** Simulation (multiple cross-sectional units over time).
- **Method.** Prais-Winston and Cochrane-Orcutt feasible GLS estimators and the Wald
  statistics built on them, versus the GRS test and the HAR/Newey-West Wald test.
- **Finding.** The proposed Wald statistics **remain robust to heteroskedasticity and
  autocorrelation**, while the original and modified GRS tests exhibit **severe Type I
  errors when errors are autocorrelated**, and the HAR Wald test over-rejects as the
  number of cross-sectional units grows.
- **Limitation.** Parametric GLS requires a model for the error covariance; the
  nonparametric alternative (HAR) has its own dimensionality curse.

### 1103.5665v1 - Evaluating the Precision of Estimators of Quantile-Based Risk Measures
- **Question.** How precise are VaR, ES and spectral-risk estimators at realistic sample
  sizes, and can the classical asymptotic-normality shortcut be trusted?
- **Data.** Simulation across loss distributions.
- **Method.** A Monte Carlo method for estimator precision; study of the sampling
  distribution of risk estimators and its dependence on the loss distribution.
- **Finding.** The common practice of relying on **asymptotic normality results is
  unreliable at the sample sizes commonly available**; estimator precision depends on the
  shape of the loss distribution, so a VaR/ES number should carry a measured uncertainty
  band rather than a Gaussian standard error.
- **Limitation.** Pre-2011 methodology; the Monte-Carlo precision method is
  computationally heavier than a closed-form SE.

### 2103.05921v1 - Financial Factors Selection With Knockoffs
- **Question.** Can factor selection control the false-discovery rate rather than just
  p-value each factor?
- **Data.** Fund-replication and explanatory/prediction networks.
- **Method.** The knockoff procedure - synthetic negative-control factors that mimic the
  correlation structure of the real ones - to select factors while controlling FDR.
- **Finding.** Knockoffs give **FDR-controlled factor selection** in financial factor
  models, applicable to fund replication and to explanatory/prediction networks where
  many candidate factors are correlated.
- **Limitation.** Knockoff construction quality governs validity; correlated,
  low-signal factors make the filter conservative.

### 1811.11618v2 - Kalman filter demystified
- **Question.** How does the Kalman filter relate to hidden Markov models, and can the
  connection improve inference and parameter estimation?
- **Data.** Financial-market illustrations (trend detection).
- **Method.** A probabilistic-graphical-model presentation of the Kalman filter, new
  inference algorithms for extended Kalman filters, and CMA-ES as an EM alternative for
  parameter estimation.
- **Finding.** Kalman filtering is an HMM in continuous state; the parameter-estimation
  step (traditionally EM) can be replaced by CMA-ES, and the filter connects directly to
  a trend-following technical system with superior trend-detection performance.
- **Limitation.** Didactic/overview; the performance claims are illustrative rather than
  a controlled backtest.

### 1602.02185v2 - Sparse Kalman Filtering Approaches to Covariance Estimation from High Frequency Data in the Presence of Jumps
- **Question.** Can covariance be estimated from high-frequency data when returns are
  asynchronous, noisy and jump-contaminated?
- **Data.** Simulated high-frequency data.
- **Method.** Extends the Kalman-EM covariance algorithm to jump models; Kalman
  Expectation Conditional Maximization with Laplace and spike-and-slab jump priors, and a
  Bayesian Gibbs sampler over the posterior covariance.
- **Finding.** Both sparse Kalman approaches give **improved covariance estimation relative
  to KEM** in the presence of jumps, detecting jumps rather than letting them corrupt the
  covariance.
- **Limitation.** Simulation-only; the jump priors are the modeling assumption and no
  index application is shown.

### 2607.06373v1 - Error Propagation in Spectral Functionals of Shrinkage Covariance Estimators
- **Question.** When a rolling covariance spectrum's absorption ratio or leading eigenspace
  moves, is that market structure or estimation noise?
- **Data.** Simulation under a known population covariance plus an equity-panel appendix.
- **Method.** A first-order null law for the projector movement `D = ||P_k - P_k'||_F`
  between overlapping windows; a distribution-free Davis-Kahan band; an estimator-aware
  parametric bootstrap; deterministic bounds for the scalar spectral functionals.
- **Finding.** Spectral functionals fluctuate under estimation noise and shrinkage changes
  the law of that noise, so **movement must be calibrated against a null band** before it
  is read as structural change; first-order immunity to elliptical kurtosis holds for
  scale-invariant functionals and only them, and shrinkage biases the absorption ratio in
  high dimensions (a trace-preserving spike-debiased estimator removes it).
- **Limitation.** The null is first-order and assumes overlapping windows; the population
  covariance is known only in the simulations.

## 3. Learnings applicable to this repo

### L1. Report both semiparametric memory estimators and the gap between them
- **Source**: `arXiv 2605.24285v1` (2026) - Memory, Roughness, and Information Persistence.
- **Finding**: GPH and local-Whittle estimates of the same `d` diverge systematically on the
  same panel (0.226 vs 0.440), and the paper warns that structural breaks and
  near-integrated GARCH mimic fractional dependence, so `d` is a reduced-form summary.
- **Repo surface**: `tradingagents/strategies/long_memory.py::memory_parameter`.
- **Status**: shipped - the function already returns `gph_d` and `whittle_d` side by side.
- **Concrete step**: add the estimator gap (`whittle_d - gph_d`) to the record's `basis`
  and flag when it exceeds the GPH asymptotic `se`, so a caller can see the
  spurious-long-memory caveat without reading the paper.

### L2. Measurement noise biases roughness/Hurst estimates downward
- **Source**: `arXiv 1608.01895v3` (2018) - Semiparametric inference on the fractal index.
- **Finding**: additive noise biases the fractal index downward (a series then looks
  *more* rough than the underlying process); a noise-robust estimator and a formal noise
  test are required to avoid spurious roughness.
- **Repo surface**: `tradingagents/strategies/mean_reversion.py::hurst_exponent`.
- **Status**: absent - the module uses rescaled-range analysis on the raw series with no
  noise correction, and `long_memory.py` has no noise test.
- **Concrete step**: document the bias direction in `hurst_exponent`'s docstring and add a
  noise test (e.g. compare a lag-1-differenced variogram against the fitted slope) that
  returns `None` or a `noise_flagged` flag when the sequence looks noise-contaminated.

### L3. Under dependence the IID bootstrap undercovers; block/sieve do not fully fix it
- **Source**: `arXiv 2607.06690v1` (2026) - tsbootstrap.
- **Finding**: at 90% nominal the IID bootstrap covers 27.8% on AR(1) phi=0.9 (sieve 83.1%,
  moving block 69.7%) and 8.2% on ARFIMA long memory, where *no* method reaches nominal.
- **Repo surface**: `tradingagents/strategies/conformal.py::block_bootstrap_interval`
  and `::block_length`.
- **Status**: shipped - the module already self-selects a block length from the series'
  own ACF and ADF check and states the realized-coverage caveat.
- **Concrete step**: add a sieve/residual option beside the moving-block path so the
  short-memory-linear case gets its nearest-nominal method, and keep reporting the
  realized coverage rather than the nominal level.

### L4. Conformal bands under dependence need an adaptive alpha, not a static one
- **Source**: `arXiv 2607.06690v1` (2026) - tsbootstrap (conformal layer).
- **Finding**: static split conformal assumes exchangeable calibration data and undercovers
  on autoregressive streams; adaptive calibrators (ACI, NexCP, AgACI) target drifting and
  volatility-clustered regimes.
- **Repo surface**: `tradingagents/strategies/conformal.py::rolling_band`.
- **Status**: partial - `rolling_band` recalibrates on a trailing window but uses a fixed
  nominal `alpha` and no adaptive step.
- **Concrete step**: add an optional ACI-style update of the effective miscoverage level
  from the realized hit sequence, reported beside the static band.

### L5. GARCH QML is non-convex; variance targeting stabilizes the fit
- **Source**: `arXiv 2006.02077v4` (2020) - AdaVol.
- **Finding**: the Gaussian QL criterion is not convex and batch optimizers are start-value
  sensitive; variance targeting alleviates convergence problems near the parameter-space
  boundary.
- **Repo surface**: `tradingagents/strategies/volatility_models.py::garch11_fit`.
- **Status**: partial - the fit uses a Nelder-Mead warm start (`omega0=0.05*var`,
  `alpha0=0.10`, `beta0=0.85`) with no variance targeting.
- **Concrete step**: parameterize the fit by `(alpha, beta)` with `omega` pinned to
  `var * (1 - alpha - beta)` (variance targeting), removing one free dimension and the
  common start-value failures.

### L6. A near-integrated GARCH fit is not a long-run-volatility measurement
- **Source**: `arXiv 2605.24285v1` (2026) - Memory, Roughness, and Information Persistence.
- **Finding**: near-integrated GARCH models and FIGARCH are difficult to distinguish in
  finite samples when persistence approaches unity, so an IGARCH fit carries no finite
  unconditional variance.
- **Repo surface**: `tradingagents/strategies/volatility_models.py::garch11_fit`
  (`_IGARCH_AB = 0.999` guard).
- **Status**: shipped - `long_run_vol` is already `None` when `alpha + beta >= _IGARCH_AB`
  and the boundary artifact is documented by a real NVDA example.
- **Concrete step**: none required; keep the guard and cite it in the analyst tool text so
  the refusal is read as a persistence finding, not a missing number.

### L7. Inferential significance on per-asset coefficients is not robust to dependence
- **Source**: `arXiv 2602.07046v5` (2026) - GJR-GARCH-X dependence-robust event study.
- **Finding**: a naive IID test on six per-asset coefficients produced "apparently
  decisive" significance that vanished under a copula/block bootstrap; effective sample
  size was only 1.33-2.35.
- **Repo surface**: `tradingagents/strategies/statistical.py::granger_causality` (F-test at
  line 273) and `::ols_factors` (t/p at line 353).
- **Status**: absent - both report classical homoskedastic p-values with no dependence
  correction.
- **Concrete step**: expose a block-bootstrap p-value (reuse
  `conformal.py::block_bootstrap_interval`'s block-length logic) beside the analytic p, or
  mark the analytic p as "IID-assumption" in the returned `basis`.

### L8. HAC-robust Wald inference for factor regressions
- **Source**: `arXiv 2503.13950v1` (2025) - GLS with heteroskedastic and autocorrelated errors.
- **Finding**: GRS-type tests show severe Type I errors under autocorrelated errors, and
  the nonparametric HAR Wald test over-rejects as cross-sectional dimension grows; a
  robust Wald keeps nominal size.
- **Repo surface**: `tradingagents/strategies/statistical.py::ols_factors`.
- **Status**: absent - `se` is computed as `sqrt(mse * (X'X)^-1)`, the classical
  homoskedastic OLS standard error.
- **Concrete step**: compute Newey-West HAC standard errors (a Bartlett kernel over the
  residual cross-products) and report both the classical and HAC p-values.

### L9. Thick-tailed predictors break OLS + robust standard errors
- **Source**: `arXiv 2008.06130v1` (2020) - An estimator for predictive regression.
- **Finding**: for thick-tailed predictors under heteroskedasticity, least squares with
  robust standard errors performs poorly, "sometimes dramatically"; an unbiased consistent
  estimator exists whenever the means are finite, with near-nominal size, and extends to
  quantile regression.
- **Repo surface**: `tradingagents/strategies/statistical.py::capm_decomposition`.
- **Status**: absent - the beta is a plain `scipy.stats.linregress` slope with the classic
  inference.
- **Concrete step**: add a median/quantile-regression beta beside the OLS beta for
  commodity and factor betas so a thick-tailed driver (crypto, commodities) does not
  silently distort the exposure.

### L10. Direct conditional-quantile VaR outperforms parametric GARCH in unstable periods
- **Source**: `arXiv 2203.08224v4` (2024) - GRF VaR; `arXiv 2011.00552v3` (2023) -
  mixed-frequency quantile VaR/ES.
- **Finding**: Generalized Random Forests beat GARCH/GJR-GARCH/CAViaR/quantile regression
  for VaR, most in unstable/high-volatility periods; a mixed-frequency quantile regression
  with a realized measure and a low-frequency driver beats parametric rivals on VaR and ES
  backtests without a distributional assumption.
- **Repo surface**: `tradingagents/strategies/book_risk.py::extreme_quantile_var`
  (line 562) and `::var_cvar_horizon` (line 386).
- **Status**: partial - the repo has historical/empirical quantile VaR but no conditional
  quantile regression driven by a realized-vol or VIX regressor.
- **Concrete step**: add a quantile-regression VaR with a lagged realized-volatility (and
  optional VIX) regressor, reported beside the historical `simple_var`, so the tail read
  adapts to the regime.

### L11. Calibrate spectral-functional movement against a null band
- **Source**: `arXiv 2607.06373v1` (2026) - Error Propagation in Spectral Functionals.
- **Finding**: a shrinkage covariance's absorption ratio and leading share move under
  estimation noise alone; movement must be judged against a first-order null band, and
  shrinkage biases the absorption ratio in high dimensions.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::spectral_null_band`
  (line 217), `::panel_spectrum`, `::eigen_projector_distance`, `::spectral_functionals`.
- **Status**: shipped - the R3 section implements the paper's first-order null band as a
  calibrated, data-independent function of window `T` and shrinkage `delta`.
- **Concrete step**: none; the shipped band already refuses ("not detectable", never
  "no change") and the bias caveat is documented in the module header.

### L12. Control false discovery when admitting factors
- **Source**: `arXiv 2103.05921v1` (2021) - Financial Factors Selection With Knockoffs.
- **Finding**: knockoffs select factors while controlling the false-discovery rate, which
  p-value-by-p-value testing does not, in correlated factor menus.
- **Repo surface**: `tradingagents/strategies/statistical.py::variance_inflation_factor`
  (and `ols_factors`' per-coefficient p-values).
- **Status**: absent - the repo reports VIF for collinearity and per-factor t/p, but no
  FDR-controlled selector.
- **Concrete step**: add a knockoff-style selector over the factor menu that returns an
  FDR-controlled selected set, or at minimum a Benjamini-Hochberg correction on the
  per-factor p-values.

### L13. VaR/ES precision is distribution-dependent; asymptotic normality is not safe
- **Source**: `arXiv 1103.5665v1` (2011) - Precision of Quantile-Based Risk Estimators.
- **Finding**: relying on asymptotic normality is unreliable at the sample sizes commonly
  available, and precision of VaR/ES/spectral estimators depends on the loss distribution;
  a Monte-Carlo precision band is proposed.
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_coverage_test` (line 1082).
- **Status**: partial - the coverage verdict uses the asymptotic Kupiec and Christoffersen
  chi-square statistics with no small-sample caveat.
- **Concrete step**: surface the sample size and add a bootstrap-based coverage interval
  (or a refusal floor already present) so a pass on 60 observations is not read as a pass
  on 600.

### L14. Kalman noise parameters should be estimated, not fixed constants
- **Source**: `arXiv 1811.11618v2` (2018) - Kalman filter demystified;
  `arXiv 2309.02205v1` (2023) - state-space conditional factor model.
- **Finding**: the filter's behavior is governed by `Q`/`R`; the literature estimates them
  (EM, CMA-ES) and uses the Unscented variant for nonlinear dynamics, rather than fixing
  them.
- **Repo surface**: `tradingagents/strategies/statistical_kalman.py::kalman_spread`
  (`DEFAULT_Q = 1e-4`, `DEFAULT_R = 1e-2`).
- **Status**: partial - the dynamic hedge ratio is computed, but `Q`/`R` are constants
  with no estimation and the signal threshold `|z| > 1.5` is hard-coded.
- **Concrete step**: add an optional likelihood-based fit of `Q`/`R` (or at least a
  variance-targeted `R` from the measurement residual), and report the fit's
  log-likelihood beside the spread.

## 4. Where this repo is already ahead of the literature

- **Autocorrelation-aware intervals with a measured information gap.** `conformal.py`
  (H11) ships a moving-block interval whose length is *earned from the series' own ACF
  and ADF check* and carries an information-gap diagnostic; it also records the measured
  coverage table (IID 0.45 vs block 0.75 at rho=0.8) and states plainly that the block
  interval does **not** restore nominal coverage at panel scale. tsbootstrap (2607.06690)
  reaches the same conclusion; this repo reached it and hardened it into a refusal.
- **The spectral null band (R3).** `covariance_models.py` implements 2607.06373's
  first-order law as a deliberately data-independent band with a "not detectable" verdict
  distinct from "no change", and refuses a zero band rather than flagging every move - a
  stricter reading than the paper itself demands.
- **The IGARCH boundary guard.** `volatility_models.py::garch11_fit` refuses `long_run_vol`
  on `alpha + beta >= 0.999` and documents the floating-point artifact (a 1,355,146%
  "long-run vol") that the boundary produces - the near-integrated-GARCH trap 2605.24285
  warns about, caught in production.
- **Dual memory estimators with a strict as-of refusal.** `long_memory.py::memory_parameter`
  returns GPH and local-Whittle together and refuses any window that reaches the as-of
  date, so a future stressed name cannot enter a backward estimate.

## 5. Defects or risks the literature exposes

- **`statistical.py::granger_causality` (line 273) and `::ols_factors` (line 353) report
  IID-homoskedastic p-values.** The F-test uses `rss_u/dfd` and the OLS t-test uses
  `mse * (X'X)^-1`, both valid only under no heteroskedasticity and no autocorrelation.
  `arXiv 2503.13950v1` shows GRS-type tests exhibit severe Type I errors under
  autocorrelated errors; `arXiv 2602.07046v5` shows an IID test on six per-asset
  coefficients produced "apparently decisive" significance with effective sample size
  1.33-2.35; `arXiv 2008.06130v1` shows least-squares inference on thick-tailed predictors
  under heteroskedasticity performs "poorly, sometimes dramatically so". Any analyst claim
  built on `granger_causality`'s `x_causes_y` or `ols_factors`' `p_value` inherits this.
- **`mean_reversion.py::hurst_exponent` (line 113) has no measurement-noise correction.**
  R/S analysis on a noise-contaminated series is biased downward. `arXiv 1608.01895v3`
  proves noise makes a series look more rough than it is; `arXiv 2605.24285v1` names
  microstructure noise as a source of spurious roughness. A noisy liquid name can be
  classified mean-reverting from an artifact.
- **`book_risk.py::var_coverage_test` (line 1082) judges on asymptotic chi-square.**
  The Kupiec POF and Christoffersen independence statistics are asymptotic in the number
  of breaches. `arXiv 1103.5665v1` shows asymptotic-normality-based precision is
  unreliable at the sample sizes commonly available and depends on the loss distribution.
  A `pass` verdict on a short held-out window overstates the evidence.
- **`long_memory.py::memory_parameter` (line 146) surfaces no spurious-long-memory test.**
  The GPH asymptotic `se = pi/sqrt(24m)` is reported for the whole record, but the
  local-Whittle estimate (whose `se = 1/(2 sqrt(m))` is smaller) can differ from GPH by
  more than that `se`, and neither estimator separates genuine fractional integration from
  regime shifts. `arXiv 2605.24285v1` explicitly cautions that the parameter "should be
  interpreted cautiously because it may reflect evolving market conditions".
- **`volatility_models.py::garch11_fit` (line 438) has no variance targeting.** `arXiv
  2006.02077v4` shows the QML criterion is non-convex and that batch fits are start-value
  sensitive; a Nelder-Mead warm start can converge to a local optimum or return `None` for
  a valid series, and the caller cannot see whether the failure was data or optimizer.

## 6. Limits of this review

- **Read vs skimmed.** I read abstract, introduction, method and results for 18 papers in
  the §2 set, plus 1103.5665 and 2103.05921 for the defects section. The other ~1019
  category papers were covered only through the sweep's one-line rows; the medium (661)
  and low (243) bands were not deep-read.
- **Sampling.** Papers were chosen to cover the five emphasis themes (long memory,
  GARCH estimation/inference, state-space/Kalman, quantile regression, bootstrap) rather
  than drawn at random from the 133 high-relevance rows; roughly half the high rows are
  about covariance cleaning, high-frequency realized measures and rough volatility, which
  I sampled rather than exhausted.
- **Numbers.** Corpus counts (1037 / 133 / 661 / 243) are the evidence pack's own. The
  decade table is over the 133 high-relevance rows only; the category table is over the
  60-paper booklist only. Neither is the full 1037-paper year/category distribution, which
  the evidence pack does not carry in full.
- **Not verified.** I did not run or inspect the repo's tests, and I did not read the
  tool-wiring layer (`agents/utils/*_tools.py`) to confirm which of these calculators reach
  an analyst loop; the surfaces above are the strategy modules only.
- **Paper reproducibility.** No paper's code was executed; findings are as the papers
  state them, including their own reported limitation sections.
