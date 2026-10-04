# Data Quality, Robustness & Missing Data

`book 03/19` · slug `data-quality` · 135 papers in the corpus · 11 rated high-relevance by the sweep

## 0. Scope

This category covers how financial observations are wrong, missing, or noisy before any model touches them: multivariate outlier detection, imputation of missing observations and the bias it injects, measurement error in observed returns and curves (attenuation, spurious serial correlation, biased covariance spectra), denoising of price/volatility series, generated data for backtest stress-testing, and the reliability of the vendors and collectors that produce the data. It is directly load-bearing for this repo because the governing rule is *compute, don't narrate*: a computed read is only as good as the frame it reads, and every analyst claim inherits the quality of the vendor row, the calendar alignment, and the fill policy behind it. The repo already ships a decision-level quality tier (`data_quality.py`), cross-vendor reconciliation (`metric_reconcile.py`), a coverage-window honesty gate (`coverage_window.py`), and a reliability-aware tail read (`tail_risk.py`), so the useful literature here is the part that constrains or corrects those reads rather than the part that motivates them.

## 1. Corpus composition

The sweep annotated 135 rows for this slug: 11 high, 77 medium, 47 low. By publication decade (counted from the 135 dated rows in `evidence/data-quality.md`):

| decade | papers |
| --- | --- |
| 1990s | 1 |
| 2000s | 13 |
| 2010s | 34 |
| 2020s | 87 |
| **total** | **135** |

The category is dominated by the 2020s and, within it, by three clusters: deep generative / autoencoder methods for imputation and synthetic series (16 of the 60 booklist papers), random-matrix and random-matrix-adjacent covariance cleaning, and econophysics-style outlier/denoising analyses that predate the ML wave (the 2004-2011 JSE, wavelet, and surrogate-data papers). Classical measurement-error work is the thinnest strand: only a handful of papers (1408.6279v1, 2408.07405v1, 2411.05998v1, 1809.07203v2) treat the observation as a noisy draw rather than as the ground truth, which is precisely the strand this repo's reader/refusal architecture should be measured against. The 60 booklist papers skew newer than the full category because the relevance scorer up-weighted ML-era titles.

## 2. Deep reads

The 18 papers below were read in the rendered PDF (abstract + introduction + method + results/conclusion where present). Where only part of a paper was available to me, the limitation bullet says so.

### arXiv 2305.10911v1 — Non-parametric cumulants approach for outlier detection of multivariate financial data (2023)

- **Question.** How to flag distorted observations in multivariate financial data without a distributional assumption, when a few outliers can dominate portfolio-optimisation inputs.
- **Data / market.** Simulated standard-normal, correlated-normal, skew-normal and Student-t panels, plus a real Dow Jones / crisis-period application.
- **Method.** Project the (centred, not standardised) data onto the direction that maximises the Cumulant Generating Function; the paper proves CGF is convex and recasts the search as concave minimisation, solved with a multistart projected-gradient heuristic. Outlierness is `|z − median(Z)| / MAD(Z)` above a threshold, iterated until the projected kurtosis stops increasing. For small radius `r` the optimal direction collapses to the first PCA component; higher cumulants only enter at large `r`, which also makes the CGF estimate noisier, so `r` is set where the relative CGF variance hits 10%.
- **Headline finding.** On asymmetric and heavy-tailed panels MaxCGF wins (skew-normal AUC 0.914 vs Domino 0.890; Student-t ν=10 AUC 0.913 at 8 min vs 19 min) and it is the cheapest of the projection methods (≈1-10 min vs 15-22 min). It is *not* uniformly best: on the symmetric-normal panel Peña-Prieto (kurtosis-projection) beats it on AUC (0.985 vs 0.881).
- **Limitation.** A non-convex multistart heuristic with no global-optimum guarantee; the radius `r` is a tuning knob; on Gaussian data the classical kurtosis projection is both better and simpler.

### arXiv 1110.4648v1 — Anti-Robust and Tonsured Statistics (2011)

- **Question.** Instead of trimming outliers away, can one strip the *inliers* to characterise what the market does during large moves?
- **Data / market.** S&P 500 vs 1-year Treasury changes 1871-2004; BAC vs GE weekly returns 1986-2010; GBP and JPY 10-year yield changes.
- **Method.** "Tonsuring": rank observations by an L2 or rank-distance metric, discard the smallest distances, and recompute Pearson, Spearman and Somers correlations on the surviving tail. Every real-data curve is compared against Gaussian surrogates carrying the same full-sample correlation, because tonsuring *itself* raises correlation slightly even under multivariate normality.
- **Headline finding.** Pearson correlation is not distribution-free: with 61% driving Gaussian correlation, the measured Pearson correlation of two Tukey g-and-h processes moves with skewness while rank correlation is unchanged. On real data the tonsured curves lie *below* the Gaussian artefacts, i.e. extremes do not attach as tightly as a Gaussian of the same average correlation implies — except in specific stressed pairs, where tonsured correlation rises faster than the surrogate.
- **Limitation.** Explicitly exploratory: there is no parametric form for tonsured correlation and no analogue of the GPD for extrapolation, so the curve is meaningless once fewer than one or two dozen points remain.

### arXiv 2408.07405v1 — Modeling of Measurement Error in Financial Returns Data (2024)

- **Question.** How to model discretely observed fund log-returns (and their running maximum) when the recorded data are a noisy draw from a latent process.
- **Data / market.** Fund return series (hedge-fund data noted as bias-prone); simulated Lévy models.
- **Method.** A latent Lévy process for the true returns and the period maximum; the recorded data are conditionally independent measurements of the latent process. A stick-breaking representation approximates the joint return/maximum transition, with MCMC inference and a multilevel-Monte-Carlo extension that provably reduces the cost of a given mean-square error.
- **Headline finding.** The framing itself: reported fund returns and maxima should be treated as measurement-error observations, not as the process, and the posterior can be inferred without an analytic joint transition density.
- **Limitation.** Read here to abstract + model/contribution sections; numerical results were not reached. The model is heavy and fund-specific, not a drop-in for daily equity OHLCV.

### arXiv 2404.00013v1 — Missing Data Imputation With Granular Semantics and AI-driven Pipeline for Bankruptcy Prediction (2024)

- **Question.** How to impute missing entries in large, high-dimensional, imbalanced financial panels without repeatedly scanning the whole database per missing value.
- **Data / market.** Polish Bankruptcy dataset; five years of data.
- **Method.** "Granular semantics": build a small granule around each missing entry from a few highly correlated features and the most reliable nearest observations, then predict within the granule (intergranular prediction), followed by random-forest feature selection, SMOTE balancing, and six classifiers including a DNN.
- **Headline finding.** Contextual (feature-semantic) granules impute large-missing-rate panels effectively and the downstream bankruptcy pipeline is competitive across all five years.
- **Limitation.** Bankruptcy panel, not returns; read here to abstract + introduction, so the reported comparison detail was not independently inspected. Imputed values are point estimates with no uncertainty.

### arXiv 2002.05789v1 — Gaussian Process Imputation of Multiple Financial Series (2020)

- **Question.** Can a multi-output Gaussian process learn cross-channel co-movement well enough to impute and predict financial series that are jointly driven by a latent market state.
- **Data / market.** Gold, oil, NASDAQ, USD weekly 2017-2018; ten USD exchange rates daily 2017; missingness deliberately injected (30-60% random plus whole trailing ranges removed).
- **Method.** Multi-output Gaussian process with the multi-output spectral-mixture (MOSM) kernel; cross-channel covariance built in the spectral domain from magnitude, mean, covariance, delay and phase per mixture component. Parameter init from a Bayesian non-parametric spectral estimate; L-BFGS-B.
- **Headline finding.** MOSM imputes the removed stretches with almost all data inside the 95% band and recovers the significant co-movements (oil-NASDAQ strongly positive, oil-gold, gold-USD weakly negative). It is competitive with, not dominant over, the CSM kernel — CSM had lower nMAE on the GONU panel (1.88 vs 1.8) and MOSM was better on the FX panel (4.8e-3 vs 8e-3 nMAE).
- **Limitation.** Errors in the kernel's recovered cross-correlation matrix come from NLL-only fitting (three correlated channels need not induce the pairwise correlation), and one channel is only imputable if a strongly correlated channel exists.

### arXiv 1809.07203v2 — Parameter Estimation of Heavy-Tailed AR Model with Missing Data via Stochastic EM (2018)

- **Question.** Estimate a heavy-tailed (Student-t innovation) AR model from an incomplete series — the Gaussian-AR-with-missing case was covered, the heavy-tailed case was not.
- **Data / market.** Simulations across missing rates plus real Hang Seng index returns (260 daily observations, visibly heavy-tailed on the QQ plot).
- **Method.** ML estimation by stochastic approximation EM; the latent scale-mixture variables and the missing block are drawn by Gibbs/MCMC, with convergence to a stationary point of the observed likelihood proved.
- **Headline finding.** On Hang Seng the t-AR(1) gives a lower averaged prediction error than the Gaussian AR(1) on complete data (8.836e-6 vs 9.141e-6), and with 10 of 250 observations deleted the incomplete-data t-AR estimates stay close to the complete-data ones (φ₁ −9.459e-5 vs −9.580e-5; ν 2.671 vs 2.622). So jointly modelling heaviness and missingness beats assuming Gaussian innovations.
- **Limitation.** Univariate AR only; the missing block's conditional distribution relies on Gaussian conditional structure given the latent scales.

### arXiv physics/0612170v1 — Volatility Dynamics of Wavelet-Filtered Stock Prices (2006)

- **Question.** Does wavelet denoising of 5-minute returns change the measured volatility dynamics.
- **Data / market.** 5-minute returns of the Russian MICEX10 index and five liquid stocks, 2003-2005 (16384 = 2^14 intervals, 14 resolution levels).
- **Method.** Daubechies-2 DWT; universal thresholding at each level (`|w| > sqrt(2 log n)·σ_j`); the "signal" is the inverse transform of surviving coefficients. The noise definition is operational: choose the threshold's starting level so the noise component's lag-1 linear autocorrelation vanishes.
- **Headline finding.** Denoising materially changes the answer. The filtered series' normalised hypercumulant κ drops from 0.79-0.89 (raw) to 0.17-0.32 (filtered), i.e. the filtered series is *far* more non-Gaussian; volatility autocorrelation stays power-law but with different exponents; and filter-induced linear autocorrelation appears (ρ_F(1) up to −0.29 for SNGS/SBER) that the raw series did not have.
- **Limitation.** Data from 2003-2005 and one market; the definition of noise (zero lag-1 linear autocorrelation) is explicitly acknowledged as non-fundamental and says nothing about higher-order independence.

### arXiv 2408.05690v1 — Strong denoising of financial time-series (2024)

- **Question.** Can two autoencoders that must "agree" on a representation denoise financial series better than a single under-complete or L1/L2-regularised AE.
- **Data / market.** S&P 500 total return as target with macro context variables (10y and 2y yields, CAPE, NY Fed activity, M&A?, corporate margins, curve steepness, M2), weekly from the mid-1980s (~2000 samples).
- **Method.** Two heterogeneous convolutional AEs are combined with *different* context variables; each takes turns speaking (sampling codes) and listening (updating its encoder against the partner's translated codes via a learned per-sample dictionary). Mutual agreement replaces hand-tuned regularisation.
- **Headline finding.** Mutual regularisation visibly separates up/down regimes in the context-variable plane where separate training does not (Y10-CAPE space), and the resulting strategies avoid the 2020 and 2022 drawdowns. Denoising here is a *reference-library* construction: profiles are clustered from denoised in-sample data, and out-of-sample data is compared unprocessed because the future return `y_{t+h}` cannot be auto-encoded — an asymmetry needed to avoid look-ahead.
- **Limitation.** Very small sample (~2000 weekly rows), reconstruction of the target is not the point, and the P/L evidence is opportunistic rather than a pre-registered test.

### arXiv 2307.02154v1 — Noise reduction for functional time series (2023)

- **Question.** Separate the serially-dependent dynamical part of a curve time series from cross-sectionally correlated idiosyncratic noise.
- **Data / market.** Simulated VAR(1) factor-loading curve series (d = 2, 4, 6) and hourly KNMI temperature curves (4015 days, 24 points/day).
- **Method.** Dynamic FPCA: identify the dynamical subspace M and the noise subspace M_ε, then project the observed curves along the noise subspace; the projection is MISE-optimal (not merely orthogonal) when the noise has components parallel to the signal.
- **Headline finding.** One-step-ahead forecast error Δ_F improves over Karhunen-Loève and orthogonal denoising, and the gain is largest in relative terms when the noise level is high (λ = 0.4: 0.628 vs 0.767 KL and vs a 0.617 theoretical lower bound). Denoised curves also remove the bias that the noise covariance puts into the KL eigenfunctions.
- **Limitation.** Stationarity of the curve series is assumed (the temperature data is detrended and deseasonalised); d is assumed finite and known in the forecasting comparison; the empirical application is weather, not finance — the transfer is the *estimator*, not the result.

### arXiv 1906.10325v1 — Against the Norm: Modeling Daily Stock Returns with the Laplace Distribution (2019)

- **Question.** Is the normal distribution an adequate model for daily index returns.
- **Data / market.** Daily simple returns of S&P 500, Dow Jones Industrial Average, NASDAQ Composite from Yahoo Finance back to January 2012 (N = 5000 / 1879 / 1879).
- **Method.** Skew, kurtosis, Shapiro-Wilk W and p-value; then compare the empirical CDF against fitted normal and Laplace CDFs (Laplace centre = sample median, scale = mean absolute deviation from the median).
- **Headline finding.** Normality is decisively rejected (e.g. S&P 500 skew −0.343, excess kurtosis 3.247, W 0.9557, p ≈ 1.9e-23). The Laplace CDF captures both the tails and the body better than the normal across all three indices.
- **Limitation.** Single distributional family comparison; no conditional-volatility model; the sample starts in 2012.

### arXiv cond-mat/0404416v2 — Serial Correlation, Periodicity and Scaling of Eigenmodes in an Emerging Market (2007)

- **Question.** What are the serial-correlation, periodic and long-memory properties of correlation-matrix eigenmodes, and does interpolating missing days change them.
- **Data / market.** Johannesburg Stock Exchange daily data, January 1993 - December 2002, two covariance-matrix cases (341 and 319 stocks for 1998-2002); comparison with S&P 500 RMT studies.
- **Method.** Eigenmode time series from correlation eigenvectors; spectral analysis for calendar effects; Lo-MacKinlay variance-ratio tests for the random-walk null; R/S and DFA for long memory.
- **Headline finding.** The leading eigenmode carries strong calendar effects (peaks at quarterly, three-weekly and weekly frequencies) but eigenmodes inside the Wishart noise band show *negative* serial correlation. The key data-quality result: interpolating missing/illiquid days with zero-order hold introduces high-frequency noise and **spurious serial correlation**. Newer companion work (cond-mat/0402389v3, cond-mat/0404416v2) also notes ZOH raises RMT agreement while adding that spurious autocorrelation.
- **Limitation.** One emerging market and a ten-year window; Hurst/DFA estimates are heuristic and no single long-memory test is definitive.

### arXiv 2607.02823v4 — Auditing Collector-Generated Graduation Labels on Pump.fun (2026)

- **Question.** Does an off-chain collector's terminal label measure the platform-side event, and does a model fitted on one temporal slice generalise to the next.
- **Data / market.** 749,816 unique Solana memecoin mints recorded by a V3 collector, 12 May - 10 June 2026, split into a 15-day development cohort and a 14-day validation cohort.
- **Method.** (i) A source-code and reconstructed-state measurement audit of the collector (60-second top-50 polling, 24-hour wall-clock TIMEOUT); (ii) a pre-registered logistic association model with calendar-day cluster-robust covariance and day-block bootstrap, under a frozen stability-gate framework.
- **Headline finding.** Development discrimination is high (AUROC 0.8594) but collapses to chance on the temporal holdout (AUROC 0.4642; 500/500 bootstrap replicates below 0.5 with a 95% interval [0.4112, 0.5196] containing 0.5). Validation calibration is destroyed (slope 0.013, intercept +2.816); two of nine stability gates pass. The recorded TIMEOUT label is a joint function of the platform event *and* the collector's polling design, so it does not establish platform-side non-graduation.
- **Limitation.** Single platform and a bespoke collector; the paper reports a deliberately narrow negative result (v5 retracts the v1.3 claims).

### arXiv 2105.01380v1 — Why and how systematic strategies decay (2021)

- **Question.** Which ex-ante characteristics predict the out-of-sample Sharpe decay of a published anomaly.
- **Data / market.** 72 published characteristics-based US factors (CRSP-COMPUSTAT 1963-2014, embargoed four months after fiscal year end) plus CFM international pools.
- **Method.** Replicate each factor, measure the discount ratio SR_OOS / SR_IS after publication and in international/large-cap pools with a size adjustment (simple √N or a two-step regression on 1/√N). Build 11 predictors: four arbitrage proxies, six overfitting proxies, and publication date.
- **Headline finding.** Publication year alone explains 30% of the decay variance (decade-on-decade haircut roughly halves: ~5ppt per year). Two **outlier-sensitivity** measures add another ~15%: the range of in-sample Sharpe across 100 draws each dropping 10% of the pool, and a factor re-estimated while discarding the 0.1% most influential observations (Broderick et al.). The in-sample t-stat is only a weak predictor; arbitrage-capital proxies are marginal.
- **Limitation.** The measures are correlational predictors of decay, not causal; factors published after 2010 are excluded.

### arXiv 2601.12990v1 — Beyond Visual Realism: Toward Reliable Financial Time Series Generation (2026)

- **Question.** Why do GAN-generated financial series look realistic yet collapse under a trading backtest, and can structure-preserving objectives fix it.
- **Data / market.** Daily Shanghai Composite Index returns, 2004-2024 (~5000 observations), sequence length 2520.
- **Method.** SFAG = WGAN-GP plus four differentiable stylised-fact losses: GPD tail-index gap, squared-return ACF MSE for volatility clustering, return/future-vol correlation for the leverage effect, and the Frobenius gap between cross-scale (5/20/60/120-day) volatility correlation matrices. Losses annealed over the first 20% of training.
- **Headline finding.** Baselines reproduce marginal realism but a 60-day momentum backtest on their synthetic paths returns 2152-2467% annualised with ~1000% volatility and VaR near −80%; SFAG returns 27.8% / 9.37% vol / −0.91% VaR against a real-data benchmark of 33.1% / 15.2% / −1.10%. Tail-index gap falls from 0.0776 (WGAN-GP) to 0.0146; the leverage effect is *not* preserved by any model (gap 32-33).
- **Limitation.** One equity index; single 60-day momentum strategy; the leverage-effect gap is large for all models including SFAG; no transaction-cost sensitivity beyond 5 bps.

### arXiv 2209.11686v2 — Anomaly Detection on Financial Time Series by Principal Component Analysis and Neural Networks (2022)

- **Question.** Detect and localise anomalous observations in market-risk-factor series so that risk models are not mis-calibrated, without hand-setting a detection threshold.
- **Data / market.** Simulated contaminated factor panels plus real market-risk data; Black-Scholes/Normal downstream VaR experiment.
- **Method.** PCA as a feature extractor; a feedforward network produces an anomaly score, and the cut-off is itself a calibrated network parameter minimised through a customised loss (removing expert bias). A second step localises the anomalous observation within a flagged series.
- **Headline finding.** The PCA-NN detector is high and stable across synthetic and real data; when used as a cleaning pre-processing step, **VaR estimation errors are reduced**. Detection is 77% for the smallest shock-amplitude group and 96-98% for the largest; localisation is 86-100%.
- **Limitation.** Performance degrades for small-amplitude anomalies (the group a real vendor error would most plausibly fall into); the "basic imputation" used to correct detected anomalies is not the contribution and is only sketched.

### arXiv 2411.05998v1 — Filling in Missing FX Implied Volatilities with Uncertainties (2024)

- **Question.** Can VAE imputation of missing FX implied volatilities beat classical surface models, and can it report uncertainty.
- **Data / market.** FX option implied-volatility surfaces.
- **Method.** Modify the standard VAE imputation: heteroscedastic noise in the decoder, residual-network encoder/decoder instead of a plain MLP, and distributional imputation that returns p(x_missing | x_obs) rather than a point.
- **Headline finding.** With the architecture changes, imputation error in low-missingness regimes nearly halves and the need for β-VAEs disappears. Crucially, without residual networks VAEs do **not** beat classical baselines (Heston-with-jumps can significantly outperform prior VAE work); and point estimates alone were the gap the paper closes.
- **Limitation.** Read here to abstract + introduction; the paper states classical models remain strong competitors, so the practical takeaway is uncertainty reporting, not "use a VAE".

### arXiv 1408.6279v1 — A Noisy Principal Component Analysis for Forward Rate Curves (2014)

- **Question.** Is classical PCA valid for forward-rate curves when those curves are interpolated from yields and contaminated by market-microstructure noise.
- **Data / market.** Simulated Gaussian HJM and three-factor CIR term structures calibrated to US data (1985-2000); US and UK term-structure applications.
- **Method.** Model the observed curve as the true curve plus observational error, prove the forward and yield covariance operators have equal rank, and replace the static sample covariance with long-run covariance-matrix estimators (Andrews kernel-type, Kiefer-Vogelsang fixed-b, Müller robust-optimal) that absorb the dependence the interpolation/contamination induces.
- **Headline finding.** A remarkable difference in the number of principal components between forward rates and yields is *strong evidence of unobserved noise* — under no measurement error the ranks must coincide. Static-covariance PCA is biased by microstructure and interpolation noise; LRCM-based PCA recovers the true covariance structure and cuts pricing errors.
- **Limitation.** Term-structure-specific; the LRCM bandwidth/kernel choice is a further tuning layer; finite-sample LRCM estimators are known to behave poorly under strong dependence.

### arXiv 2604.08765v3 — Reliability-Aware ETF Tail-Risk Monitoring (2026)

- **Question.** How to make a daily lower-tail (VaR) monitor trustworthy when inputs degrade, regimes shift, or predictive performance drifts.
- **Data / market.** Daily panel of six ETFs (SPY, QQQ, IWM, EEM, GLD, TLT) plus VIX and zero-coupon yields; walk-forward 2023-01-03 to 2025-12-29.
- **Method.** Four stages: (1) service-time quality flags `Q_t` = weighted missingness, OHLC-inconsistency, return-jump, volume-jump and stale-close indicators; (2) bootstrap-quantile tail model with a 63-day residual recalibration; (3) uncertainty `U_t` = ensemble dispersion, PCA-Mahalanobis OOD score, and recent breach-rate drift; (4) a conservative safe VaR `min(historical 63-day quantile, q̂_t − A_t)` where the adjustment `A_t` grows with `s_t·U_t` and `Q_t`, with green/orange/red alerts.
- **Headline finding.** Integrating quality, uncertainty and conservative adjustment improves stressed-period breach control and stays reliable under simulated input degradation, whereas a forecast-only monitor can be statistically acceptable yet operationally unreliable.
- **Limitation.** Six ETFs and one market regime window; weights/thresholds are fixed ex ante rather than fitted, and missing macro data is imputed with trailing medians.

## 3. Learnings applicable to this repo

### L1. Add a distribution-free multivariate outlier scan for the panel

- **Source**: `arXiv 2305.10911v1` (2023) — Non-parametric cumulants approach for outlier detection.
- **Finding**: Projecting data onto the max-CGF direction and thresholding `|z − median| / MAD` detects multivariate outliers without a distributional assumption, is cheapest among projection methods, and is the best of the three on skewed/heavy-tailed panels (AUC 0.914 skew-normal, 0.913 Student-t ν=10 vs Domino's 0.890).
- **Repo surface**: `tradingagents/strategies/data_quality.py` (existing `aggregate_quality` / `disagreement_flag` score *inputs* by vendor, not observations by time); a scan would consume `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink` or `statistical.py::correlation_matrix` for the panel and `tradingagents/strategies/ratios.py::robust_z` for the univariate MAD scale.
- **Status**: absent — read `data_quality.py` in full; there is no per-observation anomaly function, only weighted input scores and a vendor spread.
- **Concrete step**: Add `data_quality.outlier_scan(returns_by_name, threshold=3.5)` that whitens the panel (reuse `statistical.correlation_matrix`), projects onto one or a few max-variance directions, and returns the flagged `(date, name, score)` rows plus the window they were computed on; report it in the evidence block and never let it gate by itself (matching the module's advisory contract).

### L2. Score the outlier-sensitivity of a candidate before trusting its Sharpe

- **Source**: `arXiv 2105.01380v1` (2021) — Why and how systematic strategies decay.
- **Finding**: Two sensitivity-to-observations measures (range of Sharpe across 100 draws removing 10% of the pool; re-estimation dropping the 0.1% most influential observations) add ~15% explanatory power for *out-of-sample* Sharpe decay beyond publication year (which alone explains 30%), while the in-sample t-stat is only a weak predictor.
- **Repo surface**: `tradingagents/strategies/evaluate.py::deflated_sharpe` (line 161) and `deflated_sharpe_report` adjust only for the *number of trials*; `evaluate.py::cpcv_overfit_mask` / `pbo_flag` (W2-2) catch in-sample winners that fail OOS but not single-observation leverage.
- **Status**: partial — verified `deflated_sharpe`/`pbo_flag` exist; no function drops a subset of names or influential observations and re-measures Sharpe.
- **Concrete step**: Add `evaluate.outlier_sensitivity(returns_by_name, n_draws=100, drop_frac=0.10)` returning the Sharpe range and a Broderick-style influence score, and surface it beside `deflated_sharpe_report` in the eval harness so a fragile factor is visible before it is promoted.

### L3. Correct covariance/PCA estimation for measurement error with a long-run covariance estimator

- **Source**: `arXiv 1408.6279v1` (2014) — A Noisy Principal Component Analysis for Forward Rate Curves.
- **Finding**: Under observational error and interpolation, the static sample covariance gives a biased spectral structure and a spurious factor count; ranks of forward and yield covariance operators must coincide absent noise, so a rank gap is direct evidence of contamination. A long-run covariance matrix (kernel-weighted with a fixed bandwidth) recovers the true structure and cuts pricing errors.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink` (line 85) and `panel_spectrum` (line 272); `statistical.py::correlation_matrix` (line 203).
- **Status**: absent — reads show Ledoit-Wolf shrinkage and a first-order spectral null band, but no estimator that sums lagged cross-covariances (the LRCM class).
- **Concrete step**: Add `covariance_models.long_run_covariance(returns_by_name, bandwidth="sample")` implementing the Bartlett/fixed-b estimator, run it beside `ledoit_wolf_shrink`, and refuse to declare a factor-count/spectrum change when the static and LRCM spectra disagree on the rank.

### L4. Make interpolated observations carry an uncertainty band, not a point

- **Source**: `arXiv 2411.05998v1` (2024) — Filling in Missing FX Implied Volatilities with Uncertainties; `arXiv 2002.05789v1` (2020) — Gaussian Process Imputation.
- **Finding**: VAE imputation only becomes competitive once it reports p(x_missing | x_obs) rather than a point estimate (and uses residual networks, which nearly halve error in low-missingness regimes); the GP imputer likewise reports a posterior mean *with a 95% band*, and its errors concentrate where no strongly-correlated channel exists.
- **Repo surface**: `tradingagents/strategies/rate_utils.py::interpolate` (returns point values, drops out-of-range points) and `tradingagents/strategies/options_surface.py::_interp_iv_at` (line 181, point value).
- **Status**: absent — both interpolation paths return scalars with no dispersion; verified by reading their docstrings.
- **Concrete step**: Have `options_surface._interp_iv_at` return the two bracketing observed IVs alongside the interpolated value (a local error proxy), and have `rate_utils.interpolate` optionally return per-point spacing-to-nearest-observation so a consumer can widen a band around interpolated inputs.

### L5. Record which observations are forward-filled, because ffill injects serial correlation

- **Source**: `arXiv cond-mat/0404416v2` (2007) — Serial Correlation, Periodicity and Scaling of Eigenmodes in an Emerging Market (with cond-mat/0402389v3).
- **Finding**: Interpolating missing/illiquid days with zero-order hold (and, in the companion RMT paper, plain zero-padding) introduces high-frequency noise and **spurious serial correlation**; eigenmodes then show autocorrelation the raw series did not have.
- **Repo surface**: `tradingagents/dataflows/stockstats_utils.py::_clean_dataframe` (line 64, `ffill()` at line 76) and `tradingagents/strategies/coverage_window.py::coverage_window` (reports `padded_days` but not fills).
- **Status**: partial — `_clean_dataframe` ffill-only is look-ahead-safe (the comment at lines 73-75 explicitly rejects bfill for future leakage), but neither it nor `coverage_window` records which positions were filled, so a downstream autocorrelation or volatility read cannot know it is partly reading synthetic bars.
- **Concrete step**: Return a fill mask from `_clean_dataframe` (or a `filled_days` count through `coverage_window`) and have `data_quality.panel_statistic` report it; a statistic taken over a heavily-filled window should say so beside the number, exactly as `padded_days` does.

### L6. Keep refusing missing-data windows in the heavy-tail estimators — and say why

- **Source**: `arXiv 1809.07203v2` (2018) — Parameter Estimation of Heavy-Tailed AR Model with Missing Data.
- **Finding**: A Student-t AR estimated from an incomplete series (via stochastic EM over the missing block) gives lower prediction error than a Gaussian AR on complete data (8.836e-6 vs 9.141e-6) and its estimates stay close to the complete-data ones at 4% missingness. Filling a heavy-tailed series with a Gaussian-implied value is the wrong estimator, not a neutral convenience.
- **Repo surface**: `tradingagents/strategies/long_memory.py::memory_parameter` (refuses a window that still contains a post-`as_of` or missing name rather than silently trimming) and `coverage_window.py::coverage_window`.
- **Status**: partial — the refusal policy is implemented and documented, but there is no missing-data-aware estimator, so incompleteness converts a measurable quantity into `unavailable` rather than a wider-interval estimate.
- **Concrete step**: When a memory/HAR window is refused for missingness, additionally report the largest contiguous complete sub-window and its estimate as a *sensitivity* beside the refusal — never replacing the refusal, just bounding what the missing rows could have hidden.

### L7. Report calibration slope/intercept on a temporal holdout, not just discrimination

- **Source**: `arXiv 2607.02823v4` (2026) — Auditing Collector-Generated Graduation Labels on Pump.fun.
- **Finding**: A model with development AUROC 0.8594 collapsed to 0.4642 on a subsequent 14-day holdout, with calibration slope 0.013 and intercept +2.816 — discrimination looked fine in-slice while the labels themselves were a joint function of the event and the collector's polling design, not the event alone.
- **Repo surface**: `tradingagents/strategies/calibration.py::calibration_table` / `isotonic_calibrate` / `excess_accuracy` and `tradingagents/strategies/evaluate.py::oos_split` (line 382) / `walk_forward_splits` (line 244).
- **Status**: partial — `calibration.py` bins confidence vs hit rate and fits isotonic maps; no Cox calibration slope/intercept is reported, and no scoring pipeline is forced to publish a temporal-holdout calibration beside its discrimination.
- **Concrete step**: Add `calibration.calibration_slope_intercept(pred, realized)` and have the eval harness print it per walk-forward fold next to the hit rate, so a regime where the model is merely confident-but-miscalibrated is distinguished from one where it is uninformative.

### L8. Generate stress paths that satisfy stylised facts before using them to judge a strategy

- **Source**: `arXiv 2601.12990v1` (2026) — Beyond Visual Realism: SFAG.
- **Finding**: GAN synthetic paths that look realistic produced backtests of 2152-2467% annualised return and ~1000% volatility, while adding differentiable GPD-tail, volatility-clustering, leverage and cross-scale-volatility constraints produced 27.8% / 9.37% vs a 33.1% / 15.2% real benchmark. Distributional realism is not backtest validity; the leverage effect was *not* preserved even by the best model.
- **Repo surface**: `tradingagents/strategies/backtest_engine.py` (order state machine + bar matching) and `tradingagents/strategies/evaluate.py::_stationary_indices` (the stationary bootstrap already used by `reality_check` / `spa`).
- **Status**: absent — verified there is no synthetic-path generator; the bootstrap resamples existing returns rather than imposing tail/clustering structure.
- **Concrete step**: Add `backtest_engine.synthetic_paths(returns, n_paths, seed)` that stationary-bootstraps blocks and then rescales to match the sample's GPD tail index and squared-return ACF at lags 1-20; use it only for stress evaluation, and report the leverage-effect gap so the generator does not over-claim.

### L9. Feed OHLC-consistency and staleness flags into the reliability-aware VaR quality score

- **Source**: `arXiv 2604.08765v3` (2026) — Reliability-Aware ETF Tail-Risk Monitoring.
- **Finding**: The quality score that drives conservative VaR adjustment is built from missingness fraction, an OHLC-internal-consistency flag, return/volume jump z-scores and a stale-close indicator; quality, uncertainty and a conservative adjustment together improve stressed-period breach control under degraded inputs.
- **Repo surface**: `tradingagents/strategies/tail_risk.py::tail_risk` (line 174) consumes a quality score from `data_quality.py::aggregate_quality`; `tradingagents/dataflows/market_data_validator.py::live_price_sanity` already classifies a live print against the verified bar (INSIDE/OUTSIDE/BELOW/ABOVE).
- **Status**: partial — `tail_risk` applies quality/uncertainty widening, and the validator computes bar-comparison bands, but the quality score is not fed the OHLC-consistency/staleness/jump terms the paper uses; `aggregate_quality` takes only caller-supplied per-input scores.
- **Concrete step**: Add a `data_quality.market_quality_flags(ohlcv)` producer computing missingness, OHLC-consistency (`low <= min(open,close) <= max(open,close) <= high`), jump z-scores and a repeated-close staleness flag, and document that its output is the intended input to `aggregate_quality` and hence to `tail_risk`.

### L10. Screen reported financials with a first-digit (Benford) test

- **Source**: `arXiv 1712.00131v1` (2017) — Benford's law as a screen for reported financial data (medium-relevance sweep row).
- **Finding**: The first-significant-digit distribution departs from Benford when data are misreported; a distribution-distance test on the digits flags which series to distrust, then the outliers are removed before use.
- **Repo surface**: `tradingagents/strategies/data_quality.py` and `tradingagents/strategies/ratios.py` (both consume vendor-reported line items).
- **Status**: absent — no digit/leading-digit test anywhere under `tradingagents/strategies/`.
- **Concrete step**: Add `data_quality.benford_screen(values, min_n=300)` returning the first-digit histogram, the Benford MAD/chi-square distance and a flag, and wire it into the fundamentals gathering path as an advisory data-conflict note beside `metric_reconcile`.

### L11. Treat financial statement ratios as compositional (log-ratio) before z-scoring

- **Source**: `arXiv 2305.16842v8` (2023) and `arXiv 2210.11138v2` (2022) — Compositional-data methodology for financial ratios (both high/medium sweep rows).
- **Finding**: Ratios of accounting line items are compositional: they are skewed, outlier-prone, and numerator/denominator dependent, and conclusions change when results are made invariant to that dependence; log-ratio transforms remove the skew and the artefactual outliers.
- **Repo surface**: `tradingagents/strategies/ratios.py` (the ratio block) and the winsorised-z pipeline in `factors.py::category_scores` / `factor_schema.py` (`normalization_method="winsorised-z"`).
- **Status**: absent — `ratios.py` computes raw ratios and winsorises only downstream via the cross-section layer; no log-ratio/CLR transform exists (verified by reading `ratios.py`).
- **Concrete step**: Add `ratios.log_ratio(a, b)` (and a CLR helper over a ratio group) and use it in the cross-section score path for the accounting-ratio factors, reporting the transformed value beside the raw one so the change is auditable.

### L12. If a denoiser is ever added, publish the filter and the autocorrelation it induces

- **Source**: `arXiv physics/0612170v1` (2006) — Volatility Dynamics of Wavelet-Filtered Stock Prices; `arXiv 2307.02154v1` (2023) — Noise reduction for functional time series.
- **Finding**: Wavelet filtering changes the measured regime drastically (hypercumulant κ from 0.79-0.89 raw to 0.17-0.32 filtered) and *introduces* linear autocorrelation the raw series lacked (ρ_F(1) down to −0.29); a well-posed denoiser (MISE-optimal FPCA) improves forecasts but the target (which subspace is signal) is an assumption that must be stated.
- **Repo surface**: `tradingagents/strategies/volatility_models.py` (`semivariance`, `bipower_proxy`, `quarticity_proxy`) and `tradingagents/strategies/complexity.py` (entropy features); `book_risk.py::var_cvar_horizon` (line 386) already gates √T scaling on lag-1 autocorrelation.
- **Status**: absent — no denoising step exists today, which is the safe default; the risk is that one is added later without its side-effects being measured.
- **Concrete step**: If a smoother is introduced, require it to emit a filter descriptor (type, window, threshold) into the record and to run `book_risk.return_autocorrelation` (line 355) before and after, so the `scaling_valid` gate can see the induced dependence.

## 4. Where this repo is already ahead of the literature

- **Cross-vendor conflict is computed, not narrated.** `data_quality.py::disagreement_flag` reports the spread on one metric across vendors and flags DATA CONFLICT, and `metric_reconcile.py::reconcile_metrics` / `extract_de_value` compare the same underlying metric across differently-labelled tool leaves. Most of the corpus treats a single data source as ground truth.
- **Point-in-time and coverage honesty are first-class.** `data_quality.fundamentals_pit_ok` fail-closes a fundamental dated after the effective date, `panel_statistic` refuses a statistic over a padded window, and `coverage_window.SURVIVOR_ONLY` names the survivor-bias label in the findings record. The surveyed literature rarely states either invariant explicitly.
- **Robust standardisation is single-sourced and fit on train only.** `ratios.robust_z` / `ratios.MAD_SCALE`, `cross_section.winsorize`, `cross_section.cross_sectional_z(robust=True)`, `analyst_revisions.winsor_z`, `breadth_depth._robust_z` / `_winsorize_series`, and `factor_expressions.fit_winsorize` / `apply_winsorize` (train-segment bounds only) implement the median/MAD + winsorised-z discipline with the no-look-ahead split baked in — a cleaner treatment than most outlier papers surveyed.
- **Look-ahead-safe cleaning is documented.** `stockstats_utils._clean_dataframe` forward-fills only and explains (lines 73-75) that bfill would pull a future row; `rate_utils.interpolate` drops points outside the observed range rather than extrapolating.
- **√T risk scaling is gated on measured autocorrelation.** `book_risk.var_cvar_horizon` refuses to trust √T when lag-1 autocorrelation exceeds 0.2 — the exact failure mode the imputation papers warn about.
- **Heavy tails are already modelled.** `regime.py::EMISSION_FAMILIES` offers `laplace`, `student_t` and `ged` HMM emissions behind a gate, and `book_risk.extreme_quantile_var` fits a GPD tail that extrapolates beyond the worst observed day — the Laplace/GPD recommendation of 1906.10325v1 and the EVT literature is already available.
- **Reliability-aware tail risk is implemented.** `tail_risk.py::tail_risk` (K1, explicitly cited to 2604.08765v3) attaches quality, uncertainty, coverage and a widened band to the VaR/CVaR number and withholds a red number.
- **Tamper-evident audit ledger.** `hash_chain_audit.py::append` / `verify` chains every row to the SHA-256 of the previous raw line; none of the surveyed data-quality papers proposes an integrity mechanism.
- **Multi-trial overfitting controls.** `evaluate.py::deflated_sharpe`, `cpcv_overfit_mask`, `pbo_flag`, `reality_check`, `spa`, `family_materiality` exceed the robustness apparatus of the individual factor-decay papers.

## 5. Defects or risks the literature exposes

1. **Forward-filled bars silently change autocorrelation and volatility reads.** `tradingagents/dataflows/stockstats_utils.py::_clean_dataframe` (fill at line 76) forward-fills OHLC gaps. `cond-mat/0404416v2` shows zero-order-hold interpolation introduces high-frequency noise and spurious serial correlation; any downstream read on an ffilled stretch (rolling vol, `book_risk.return_autocorrelation`, eigenmode/variance-ratio analyses) is reading partly synthetic bars with no flag saying so. The `var_cvar_horizon` autocorrelation gate partially protects the √T path, but the fill is invisible to the statistic itself.
2. **Default Pearson correlation is biased on skewed data.** `tradingagents/strategies/statistical.py::correlation_matrix` (line 203) defaults to `method="pearson"`. `1110.4648v1` (Figure 1) demonstrates that measured Pearson correlation moves with skewness while the true Gaussian-driven correlation is fixed, and `2005.03963v2` finds rank-based correlations more stable. Consumers (`covariance_models`, `peer_universe`) that take the default inherit the bias on heavy-tailed equity returns; the Spearman/Kendall options exist but are not the default.
3. **Static covariance is used without a measurement-error correction.** `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink` (line 85) / `panel_spectrum` (line 272) shrink a static sample covariance. `1408.6279v1` shows the static covariance is biased under observational error/interpolation and can corrupt the factor count; the repo has no long-run covariance estimator to cross-check against, so a spurious spectral change cannot be distinguished from a real one except through the first-order null band.
4. **In-sample Sharpe has no outlier-sensitivity gate.** `tradingagents/strategies/evaluate.py::sharpe` (line 94) is a plain non-robust moment estimator; `2105.01380v1` shows two observation-sensitivity measures predict roughly 15% of out-of-sample Sharpe decay beyond publication year. The repo deflates for the number of trials (`deflated_sharpe`) but never tests how much of a factor's Sharpe survives removing a small random subset of names or the most influential observations.
5. **Imputed/interpolated values are point estimates with no dispersion.** `options_surface._interp_iv_at` (line 181) and `rate_utils.interpolate` return scalars. `2411.05998v1` establishes that imputation without uncertainty p(x_missing|x_obs) is the gap that made prior VAE work uncompetitive; any consumer that treats an interpolated IV or rate as a measured observation understates its error.

## 6. Limits of this review

- **Read vs skimmed.** §2 reports 18 papers read in the rendered PDF; the remaining 117 rows of the evidence pack were consumed only at the abstract/takeaway level from `evidence/data-quality.md`. Within §2, 2408.07405v1 and 2404.00013v1 were read to abstract + method rather than to their numerical-results sections; 2411.05998v1 to abstract + introduction. Their bullets say so.
- **Sampling.** The 60-paper booklist is the relevance-scorer's top slice of 135 rows; I selected deep reads to cover the six emphasis themes (outliers, imputation, measurement error, denoising, synthetic data, vendor reliability) rather than to follow the score ordering, so a few very-high-scoring random-matrix/covariance-cleaning papers (2601.07687v4, 2111.13109v3, 2310.19992v1, 2311.14735v1) were not deep-read because their surface (`covariance_models.py`) is already covered by the measurement-error and spectral-null work.
- **Could not verify.** Papers behind `/`-style ids were read from the `_`-substituted filenames (`physics_0612170v1`, `cond-mat_0404416v2`); the cond-mat companion cond-mat/0402389v3 was cited from the evidence pack's row, not read in full. Repo statuses were verified by reading the named modules; no repository tests, linters, or git commands were run, and no code was modified.
