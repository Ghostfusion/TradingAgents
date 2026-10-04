# Return, Price & Time-Series Forecasting

`book 16/19` · slug `forecasting` · 1567 papers in the corpus · 168 rated high-relevance by the sweep

## 0. Scope

This category covers the prediction of returns, prices, volatility and other financial
time series: point forecasters (ARIMA/HAR/factor/DL), probabilistic and density
forecasters and their scoring rules (CRPS, QLIKE, log score), forecast combination and
reconciliation, conformal and other calibrated interval methods, nowcasting, and the
evaluation methodology that decides whether any of these beat a benchmark. It matters to
this repo more than any other category because the repo already contains a first-class
forecast *contract* — `ForecastRecord` / `ForecastEvaluation` / a registry of
authoritative producers and declared benchmarks — so the corpus's real contribution is
not "here is a model to add" but "here is what makes a forecast claim honest". The
dominant empirical message across the serious recent work is deflationary: simple,
correctly-fitted econometric baselines are hard to beat, most stated edges are
base-rate or calibration artefacts, and marginal coverage is not a density.

## 1. Corpus composition

Numbers derived from the corpus classification: 1567 papers list `forecasting` in
their book membership, of which 146 carry it as their **primary** book (the rest are
cross-listed from volatility, correlation, ml-methods, etc.). The sweep's own evidence
pack reports 1567 annotated rows (168 high · 830 medium · 569 low).

| Decade | Papers (book membership) |
| --- | --- |
| 1990s | 7 |
| 2000s | 139 |
| 2010s | 432 |
| 2020s | 989 |

| Primary arXiv category | Papers |
| --- | --- |
| q-fin.ST (Statistical Finance) | 965 |
| cs.LG | 103 |
| q-fin.TR | 49 |
| cond-mat.stat-mech | 46 |
| q-fin.RM | 45 |
| stat.AP | 42 |
| physics.soc-ph | 37 |
| q-fin.CP | 32 |

The category is dominated by `q-fin.ST` (62% of members) and, within that, by two
weak genres: single-asset ARIMA/LSTM price-level "prediction" papers that never
benchmark against a random walk, and electricity-price papers (a large but
repo-irrelevant sub-population whose methods — quantile postprocessing, CRPS
combination, IDR — nonetheless transfer directly to probabilistic *financial*
forecasting). The methodologically serious 2024-2026 tail is small but strong: it is
about R² ceilings, base-rate honesty, foundation models vs HAR, conformal validity, and
proper scoring. That tail is what §2 reads.

## 2. Deep reads

### arXiv 2602.07841v3 — A Nontrivial Upper Bound on the Out-of-Sample R² in Return Forecasting
- **Question**: is there a bound below 1 on achievable out-of-sample R² that is a
  function of directional accuracy alone?
- **Method**: a constructed "coin-flip oracle" that uses the true conditional expected
  absolute return and a Bernoulli sign with constant hit probability `p`; its plim
  R²_OOS is derived analytically as `kappa * (2p - 1)^2`, with
  `kappa = (E[sqrt(eps)])^2 / E[eps] - 1` and `eps = r^2 / sigma_hat^2`.
- **Data**: 14 weekly Yahoo Finance series, ten conventional predictive models, split
  ratios 80:20 to 60:40; top 2% absolute log-returns trimmed to reduce noise.
- **Finding**: practical models' (2DA-1)², R²_OOS/kappa points sit below or on the
  quadratic bound in essentially every scenario; the bound is a cheap, model-agnostic
  falsifier that exposes "metric disconnect" between sign skill and MSE skill.
- **Limitation**: it is an inequality from a constructed oracle, not a power bound;
  `kappa` assumes sign/magnitude independence; an unflagged point is *not* evidence of
  skill.

### arXiv 2406.08041v1 — HARd to Beat: The Overlooked Impact of Rolling Windows in the Era of Machine Learning
- **Question**: can ML beat HAR for realized-volatility forecasting once the HAR fitting
  scheme is not deliberately handicapped?
- **Data**: 1,445 CRSP/TAQ US stocks, Jan 2015-Oct 2023, 5-minute realized variance, log
  RV, HAR and HAR-VIX; OLS/WLS, per-stock and pooled.
- **Method**: a grid over training-window length and re-estimation stride, then a
  comparison against 20+ ML models under QLIKE, MSE and realized-utility losses.
- **Finding**: with a daily re-estimation (stride 1) and a training window of roughly
  630-1,000 days (2.5-4 years), HAR is competitive with or beats tuned ML; performance
  collapses when the model is not re-estimated daily (stride 2 or 5 already hurts).
  Many "ML beats HAR" results in the literature coincide with suboptimal HAR schemes.
- **Limitation**: restricted information set (own RV + VIX); no jump or microstructure-noise
  treatment.

### arXiv 2607.05291v1 — Forecasting Realized Volatility with Time Series Foundation Models
- **Question**: do zero-shot time-series foundation models (TSFMs) beat econometric
  benchmarks for realized volatility?
- **Data**: VOLARE dataset, 50 assets (40 US equities, 5 FX pairs, 5 futures), horizons
  h = 1, 5, 22.
- **Method**: nine zero-shot TSFMs across eight architectures vs eight econometric
  specifications (HAR family, Log-HAR, ARFIMA, ARMA, MEM), with Diebold-Mariano and
  Model Confidence Set tests, Mincer-Zarnowitz recalibration, Giacomini-Rossi
  fluctuation tests.
- **Finding**: pooled QLIKE favours TSFMs but is driven by a few outlier assets; under
  equal-weight loss ratios only Tiny Time Mixers (<1M params) beats Log-HAR at every
  horizon, by 1.3-1.8%. An equal-weight average of TTM and Log-HAR matches the best
  single model and enters the MCS for 98-100% of assets. Mincer-Zarnowitz shows most
  short-horizon edge is shared *calibration*, not information — only the monthly
  horizon retains a genuine informational gain. Architecture choice matters more than
  foundation-vs-econometric.
- **Limitation**: zero-shot only; single point forecast; no return-series transfer
  (returns remain near-unpredictable).

### arXiv 2607.06690v1 — tsbootstrap: Distribution-Free Uncertainty Quantification and Conformal Prediction for Time Series
- **Question**: does the ordinary (IID) bootstrap/conformal machinery keep its coverage
  promise on dependent series?
- **Method**: one typed API for block, residual, sieve and wild resampling plus adaptive
  conformal calibrators (EnbPI, ACI, NexCP, AgACI); controlled coverage study; streaming
  reduce that avoids materializing the O(Bn) replicate tensor.
- **Finding**: the IID bootstrap **undercovers sharply** under dependence; the sieve is
  nearest to nominal under short-memory linear dependence; dependence-aware methods
  reduce but do not fully remove the deficit.
- **Limitation**: software/benchmark note (JMLR), no new finance-specific estimator; the
  coverage study is on controlled processes, not market returns.

### arXiv 2608.07479v2 — Marginally Useful: An Information-Gap Identity in Split Conformal Prediction
- **Question**: what exactly is lost when conformal prediction is read as a predictive
  *distribution*?
- **Method**: an identity for the conformal predictive system (CPS): the expected
  log-score regret of a single-shape (residual-pooled) forecaster relative to the oracle
  equals `I(R; X) = E_X KL(r(.|X) || r_bar)`, the mutual information between the residual
  and the input.
- **Finding**: marginal coverage and log score are orthogonal axes. Residual pooling
  achieves coverage while leaving the density — and therefore the log score — exactly
  where the base model put it; the permanent regret is `I(R; X)` and no `X`-blind
  recalibration can reduce it. A constant-width band over-covers easy inputs and
  under-covers hard (high-variance) inputs even at exact nominal marginal coverage.
- **Limitation**: asymptotic/large-calibration limit; a note, not an estimator; gives
  the size of the gap, not a method for closing it.

### arXiv 2606.03184v1 — FinStressTS: A Parametric Synthetic Benchmark for Time-Series Forecasting in Finance
- **Question**: can model failure be attributed to a specific mechanism rather than to
  opaque real-data entanglement?
- **Method**: 30 diagnostic environments over six mechanism families (volatility
  clustering, multi-scale persistence, heavy-tailed shocks, regime switching,
  self-exciting jumps, zero-inflation); 15 models (AR/HAR/VAR, PatchTST/iTransformer/
  TimeXer/DLinear, and DeepAR/TSFlow); point NMAE and probabilistic CRPS; learning
  curves.
- **Finding**: model performance is governed by architectural inductive bias, not
  capacity — simple autoregressive and linear models consistently beat Transformers in
  volatility-, tail- and jump-driven settings; parametric probabilistic models (DeepAR)
  are better calibrated than flexible flows under stress; neural models need multiples
  more data than classical baselines and often fail to improve with more samples.
- **Limitation**: synthetic mechanisms, so it diagnoses failure modes rather than
  certifying real-data accuracy; no leaderboard claim for any market.

### arXiv 2607.12248v2 — When Directional Accuracy Lies: A Base-Rate-Honest Benchmark for LoRA-Adapted TimesFM
- **Question**: is apparent high directional accuracy from a fine-tuned TSFM real skill?
- **Method**: frozen-data, expanding walk-forward folds, held-out-ticker stratified
  split, honest baselines (zero-shot TimesFM, always-up, random walk, persistence, AR(1)),
  paired McNemar and Diebold-Mariano tests under Benjamini-Hochberg FDR control; run
  identically on NASDAQ-100 and S&P 500.
- **Finding**: an apparent ~80% directional accuracy in a 2014+ bull window is a ~0.70
  always-up base rate, and the fine-tuned model scores *below* it. On the honest
  benchmark, pooled LoRA shows no directional skill at any horizon on either universe;
  the only significant benefit of fine-tuning is a reduction in point-forecast error,
  which still does not beat naive baselines. Per-sector specialisation is *worse* than
  one pooled adapter (DM p<0.001 at h=128).
- **Limitation**: two equity universes, one TSFM family; negative result, not a general
  no-skill theorem.

### arXiv 2404.02270v2 — Postprocessing of point predictions for probabilistic forecasting: The benefits of using isotonic distributional regression
- **Question**: which postprocessing method best turns point forecasts into calibrated
  predictive distributions?
- **Data**: day-ahead German and Spanish electricity prices, two 4.5-year test periods
  spanning COVID and the Ukraine war; LEAR and naive point forecasters as inputs.
- **Method**: Quantile Regression Averaging (QRA), Conformal Prediction (CP), and
  Isotonic Distributional Regression (IDR), plus their ensemble; Shapley-value
  attribution.
- **Finding**: IDR shows the most varied behaviour and contributes most to the ensemble
  of the three distributions; the combination beats state-of-the-art Distributional Deep
  Neural Networks. The gain is in the tail/quantile shape, which residual-pooling
  conformal cannot see.
- **Limitation**: electricity prices, a strongly seasonal and far more predictable
  series than equity returns; results may not transfer wholesale.

### arXiv 2508.15922v1 — Probabilistic Forecasting of Cryptocurrency Volatility: From Point to Quantile Forecasts
- **Question**: can point forecasts of crypto realized variance be converted into
  calibrated quantile forecasts?
- **Data**: Bitcoin (BTC/USD), Kraken 5-minute data, 2017-2021.
- **Method**: twelve base point models (HAR, GARCH, ARFIMA, LASSO, SVR, MLP, RF, LSTM);
  Quantile Estimation through Residual Simulation (QRS) and probabilistic stacking with
  quantile-linear-regression / quantile-regression-forest meta-models; scored by CRPS,
  relative frequency and Winkler score.
- **Finding**: QRS applied to *linear* base models on **log-transformed** realized
  volatility consistently beats more sophisticated alternatives; probabilistic stacking
  is robust.
- **Limitation**: one asset/period; the win is for the log-RV transform plus a linear
  base, which is a data point about scale, not a new model class.

### arXiv 2303.01855v2 — An adaptive volatility method for probabilistic forecasting and its application to the M6 competition
- **Question**: can an EMH-respecting, adaptive-volatility forecaster compete in a live
  probabilistic competition?
- **Method**: AdaVol (recursive streaming GARCH estimation by stochastic approximation
  with variance targeting) for conditional volatility, converted to return-density
  forecasts, with the competition metric optimized online by stochastic gradient.
- **Finding**: a deliberately simple, adaptive-volatility model placed 7th overall and
  5th in the forecasting task of the M6 competition — beating most of the field without
  any return-mean model, by forecasting only the scale of an approximately efficient
  market.
- **Limitation**: ranking in one competition; no long-run out-of-sample study and no
  economic-value backtest.

### arXiv 2304.09947v2 — Online Ensemble Learning for Sector Rotation: A Gradient-Free Framework
- **Question**: how should a heterogeneous model pool be combined under nonstationarity?
- **Method**: multiplicative-weights (gradient-free) online ensemble that reweights 16
  models (OLS/PCR/LASSO + RF/GBRT/NN hierarchy) by recent **out-of-sample R²**, with a
  regret bound expressed directly in R²; applied to sector-level features aggregated
  from firm characteristics.
- **Finding**: sector-level returns are more predictable and more stable than individual
  stock returns; the online ensemble beats individual models, equal weighting and
  offline ensembles in both accuracy and economic value, and is robust through the
  COVID stress.
- **Limitation**: sector aggregation is a lower-noise target than the single-name
  forecasts the repo mostly produces; regret bound is with respect to the best model
  in hindsight, not to the truth.

### arXiv 2603.17463v2 — Multivariate GARCH and portfolio variance prediction: a forecast reconciliation perspective
- **Question**: does reconciling univariate and multivariate portfolio-variance forecasts
  improve risk forecasts?
- **Method**: simulation with known true covariance and noisy proxies, comparing a
  multivariate GARCH against reconciled combinations of univariate and multivariate
  forecasts; empirical GARCH application.
- **Finding**: reconciliation improves on a standard multivariate approach, especially
  when the multivariate model is misspecified; with noisy covariance proxies, correctly-
  and incorrectly-specified models become hard to tell apart, but reconciliation still
  helps (less). Noise in the covariance proxy drives both the size of the gain and the
  identifiability of the best model.
- **Limitation**: portfolio **variance** only (weights assumed known); the gains are
  smallest exactly when the proxy is noisy — the realistic case.

### arXiv 2601.14062v1 — Demystifying the trend of the healthcare index: is historical price a key driver?
- **Question**: can same-day OHLC data predict the next day's opening direction?
- **Data**: US and Indian healthcare indices, five years including COVID.
- **Method**: supervised classification over original prices, volatility indicators and
  novel **nowcasting features built from mutual OHLC ratios**; Shapley explainability.
- **Finding**: accuracy >0.8 and MCC >0.6; the mutual-ratio nowcasting features dominate
  feature importance, ahead of the raw prices.
- **Limitation**: two sector indices, 1-step-ahead open direction; an open-to-open task
  that the repo's close-to-close forecasts do not share, and no cost/tradability test.

### arXiv 2606.22719v1 — Leakage-Aware Benchmarking of LLM Forecasting: Real-Time Nowcasts as the Decision-Time Input
- **Question**: how much of an LLM forecaster's rank IC survives a strict decision-time
  information constraint?
- **Method**: retrieval-augmented 7B LLM ranks seven US equity style factors monthly
  (2023-04 to 2026-03) from lag-shifted FRED variables, macro-event summaries and the
  Cleveland Fed's **archived daily CPI nowcast** for the unreleased current month.
- **Finding**: median monthly rank IC +0.154 across three non-overlapping 12-month
  windows, but the mean IC is statistically underpowered (bootstrap CI includes zero),
  and a **kNN macro-analog baseline recovers comparable median IC** — real-time
  inflation information plus macro similarity explains most of the signal.
- **Limitation**: short sample; leakage is controlled by design but the point estimate
  is not significant; style-factor ranking, not stock returns.

### arXiv 2605.21504v1 — Multivariate Financial Forecasting using the Chronos Time Series Foundation Models
- **Question**: do multivariate (MV) inputs improve a TSFM's financial forecasts over
  univariate (UV)?
- **Data**: Magnificent-7 equities, US Treasury rates, and a combined panel, rolling
  monthly evaluation 2000-2025.
- **Method**: Chronos-2 with varied input windows and horizons, RMSE/MAPE.
- **Finding**: MV inputs consistently beat UV, with strong gains for interest rates and
  meaningful gains for equities; series-level comparisons improve in every case. But
  **mixing equities and rates degrades accuracy** — adding noisy cross-domain context
  hurts.
- **Limitation**: point RMSE/MAPE only (no proper-score or interval evaluation);
  variable-window rolling protocol with no formal significance testing.

### arXiv 2603.16886v1 — A Controlled Comparison of Deep Learning Architectures for Multi-Horizon Financial Forecasting: Evidence from 918 Experiments
- **Question**: which deep architecture actually forecasts best when the comparison is
  not confounded?
- **Method**: nine architectures (Autoformer, DLinear, iTransformer, LSTM, ModernTCN,
  N-HiTS, PatchTST, TimesNet, TimeXer) × three asset classes (crypto, FX, equity indices)
  × two horizons; fixed-seed Bayesian hyperparameter search, configuration freezing,
  multi-seed final training, and pairwise statistical correction.
- **Finding**: ModernTCN best mean rank (1.333) with 75% first-place rate; PatchTST
  second; architecture explains 99.90% of raw RMSE variance vs 0.01% for seed noise, so
  three seeds suffice. **Directional accuracy is indistinguishable from 50% across all
  54 model-category-horizon combinations** at hourly resolution — MSE-trained
  architectures lack directional skill.
- **Limitation**: hourly horizons on price levels; MSE loss is shown to be the wrong
  objective, so the negative directional result is partly about the loss, not the data.

### arXiv 2608.26106v1 — A Statistical-Finance Benchmark for Same-Day Directional Stock Prediction: Walk-Forward Evidence from SPY
- **Question**: is there detectable same-day directional information in open-at-time
  features for SPY?
- **Data**: SPY, 1993-02 to 2024-03, 7,837 trading days; expanding-window walk-forward;
  auxiliary screen of 541 US equities.
- **Method**: XGBoost vs Random Forest, LightGBM, Logistic Regression and naive baselines;
  Diebold-Mariano and McNemar tests; SHAP.
- **Finding**: on the last 800 days, logistic regression reaches 71.09% close-direction
  accuracy, RF 61.20%, XGBoost 58.45% (95% bootstrap CI [54.94%, 62.08]). Accuracy is
  threshold-conditioned: 58.4% overall rises to 72.7% when the predicted move exceeds
  1%, but the usable sample falls from 799 to 154. SPY ranks 4th of 541 for the close
  target, so results should not be generalised.
- **Limitation**: one ETF, "same-day" target (open-to-close), a residual-overlap design;
  the authors explicitly bound the economic claim.

### arXiv 2307.07689v1 — Supervised Dynamic PCA: Linear Dynamic Forecasting with Many Predictors
- **Question**: should many predictors be scaled by their relevance to the target before
  PCA?
- **Method**: supervised PCA that first re-weights each predictor and its lags by
  dynamic forecasting significance, then applies PCA to the re-scaled panel, with LASSO
  factor selection; consistency and prediction-superiority theory; simulations and a US
  macro forecasting application.
- **Finding**: target-aware scaling beats the conventional diffusion-index PCA, which
  never learns the predictor-target relationship before compressing; LASSO factor
  selection improves on using all factors.
- **Limitation**: macro (low-frequency, smooth) panel; no equity cross-section result,
  where the signal-to-noise is far lower and factor relevance is less stable.

### arXiv 2308.15443v1 — Combining predictive distributions of electricity prices: Does minimizing the CRPS lead to optimal decisions?
- **Question**: does a CRPS-optimal weighted combination of predictive distributions also
  maximize economic value?
- **Data**: hourly German EPEX day-ahead prices.
- **Method**: CRPS learning (adaptive, pointwise/diurnal weighting) vs equal-weight
  aggregation, evaluated on accuracy and on day-ahead bidding profit.
- **Finding**: more ensemble diversity improves accuracy, but the higher computational
  cost of CRPS learning is **not** offset by higher profit despite significantly more
  accurate predictions. Accuracy and decision value come apart.
- **Limitation**: one market; scoring and decision objective are related but not
  coincident, which is the paper's point rather than a limitation.

### arXiv 2102.00968v3 — CRPS Learning
- **Question**: can predictive distributions be combined with weights that vary both
  over time *and within the distribution* (tail vs centre)?
- **Method**: pointwise combination across quantiles optimizing the CRPS, with
  spline/B-spline batch and online estimators and a fully adaptive Bernstein online
  aggregation (BOA) scheme with optimal convergence.
- **Finding**: distribution-adaptive weighting (some models better in the centre, others
  in the tails) materially improves probabilistic forecasts over single-weight
  combinations; the online BOA variant has proven optimal convergence.
- **Limitation**: the method optimizes a statistical score; by 2308.15443, a better CRPS
  need not mean better decisions.

### arXiv 2608.02828v2 — Proper-Score Observation-Driven Filters
- **Question**: must a score-driven volatility filter use the log-score (likelihood)?
- **Method**: recursions driven by the negative parameter derivative of *any*
  differentiable proper scoring rule under a declared working family and predictable
  scaling; local mean reversion via risk curvature; OU approximation of tracking error;
  consistency and asymptotic normality.
- **Finding**: the rule, the scaling and the autoregressive component are three separate
  design choices; rule choice changes robustness, adaptation, variance-forecast loss,
  VaR calibration and PIT diagnostics, and the log score's information identity that
  equates curvature and innovation variance does *not* hold for other rules.
- **Limitation**: theory plus simulation/single international-equity illustration;
  no large-scale realised-volatility horse race.

### arXiv 2303.01651v1 — Optimal probabilistic forecasts for risk management
- **Question**: should predictive distributions be calibrated with a score matched to
  the risk decision?
- **Method**: produces forecast distributions optimized for VaR/ES-relevant scoring
  rules under (potentially misspecified) models; applied to VaR/ES prediction and to VIX
  futures hedging.
- **Finding**: calibrating the predictive distribution with a score that rewards accurate
  extreme-return prediction improves VaR and ES forecasts, and tail-focused distributions
  give better VIX-futures hedging outcomes.
- **Limitation**: the score must be chosen pre-decision and is itself a model choice;
  results are for VaR/ES and VIX, not general return density.

## 3. Learnings applicable to this repo

### L1. The out-of-sample R² ceiling is a falsifier, not a validator — use it as a hard field on every directional claim
- **Source**: `arXiv 2602.07841` (2026) — A Nontrivial Upper Bound on the Out-of-Sample R² in Return Forecasting
- **Finding**: plim R²_OOS ≤ `kappa * (2DA − 1)²`; a forecast whose (2DA−1)², R²_OOS/kappa
  point lies above the quadratic is arithmetically impossible. Over 14 weekly series and
  ten models, practical forecasts never exceed the bound; complexity buys little R².
- **Repo surface**: `tradingagents/strategies/alpha_eval.py::ceiling_ratio` (the H4
  implementation) and `tradingagents/strategies/forecast_registry.py::DIRECTIONAL_CEILINGS`.
- **Status**: shipped — `ceiling_ratio` implements `kappa_hat` and the point/flag; the
  registry binds `out_of_sample_r2: "2602.07841"` to the four directional targets; the
  gate `enable_accuracy_ceiling` is read in `alpha_eval._ceiling_gate`.
- **Concrete step**: turn `enable_accuracy_ceiling` on in the default config and make
  `prediction_ledger.evaluate_forecast` refuse to score a directional forecast until the
  ceiling point is attached, so no R² claim can be published ceiling-free.

### L2. Directional accuracy must always be quoted as excess over the always-up base rate
- **Source**: `arXiv 2607.12248` (2026) — When Directional Accuracy Lies
- **Finding**: an apparent ~80% directional accuracy over a 2014+ bull window is a ~0.70
  always-up base rate; the fine-tuned model then scores **below** base rate. Under honest
  walk-forward with McNemar/DM + FDR, pooled LoRA has zero directional skill on NASDAQ-100
  and S&P 500.
- **Repo surface**: `tradingagents/strategies/calibration.py::excess_accuracy` (H4).
- **Status**: shipped — `excess_accuracy(pred, realized, baseline="always_up")` computes
  per-fold model hit rate minus the always-up rate with the H11 interval; its gate is the
  same `enable_accuracy_ceiling` switch.
- **Concrete step**: call `excess_accuracy` from `scorecard` so every per-agent hit rate
  is printed with its excess and interval, and drop the bare `hit_rate` from the run card.

### L3. HAR is hard to beat if re-estimated daily over a 2.5–4-year window; the repo already fits that scheme but omits the VIX term
- **Source**: `arXiv 2406.08041` (2024) — HARd to Beat
- **Finding**: across 1,445 stocks, HAR with a daily re-estimation and a ~630-1,000-day
  training window matches or beats tuned ML on QLIKE/MSE/realized utility; stride >1
  degrades it sharply, and the "ML beats HAR" literature coincides with suboptimal HAR
  schemes.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast`
  (`MEMORY_WINDOW = 750`, OLS on RV_t, 5-day and 22-day means).
- **Status**: partial — the default 750-day window and per-call refit match the paper's
  optimum, but the VIX regressor (`HAR-VIX`) and a WLS estimator are absent, and RMSE is
  the only natural loss.
- **Concrete step**: allow an optional VIX column in `rv_forecast`'s `extra` regressor
  set and report the fit under both OLS and WLS, so the HAR-VIX comparison the paper
  finds decisive is reproducible.

### L4. Declare TSFM forecasters as candidates and combine them with HAR rather than picking a winner
- **Source**: `arXiv 2607.05291` (2026) — Forecasting Realized Volatility with Time Series Foundation Models
- **Finding**: over 50 assets and three horizons, only Tiny Time Mixers (1.3-1.8%) beats
  a well-specified Log-HAR zero-shot, and the equal-weight TTM+Log-HAR average matches
  the best single model while entering the Model Confidence Set for 98-100% of assets.
  Architecture choice matters more than foundation-vs-econometric.
- **Repo surface**: `tradingagents/strategies/forecast_registry.py::CANDIDATE_MEMBERS`
  (empty today) and `...::publish_realized_volatility_forecast`.
- **Status**: absent — `CANDIDATE_MEMBERS: tuple[RegistryRow, ...] = ()`; the pool and
  selector are explicitly deferred to the volatility design doc.
- **Concrete step**: add one TSFM and one HAR row as `CANDIDATE_MEMBERS` sharing the
  `realized_volatility` key and publish the pool's equal-weight combination through the
  existing `ForecastPublisher`, so the benchmark is HAR, not a single winner.

### L5. Conformal marginal coverage is not a density: report the information gap beside every band
- **Source**: `arXiv 2608.07479` (2026) — Marginally Useful
- **Finding**: expected log-score regret of a residual-pooled conformal forecaster
  relative to the oracle equals `I(R; X)` — the mutual information between residual and
  input. Coverage is exactly achieved while the density, and hence the log score, is
  untouched; a constant-width band over-covers low-variance inputs and under-covers
  high-variance ones.
- **Repo surface**: `tradingagents/strategies/conformal.py::information_gap` and
  `...::rolling_band`, `...::quantile_band`.
- **Status**: shipped — `information_gap` computes the pooled-vs-conditional scale gap in
  nats/observation with a `GAP_THRESHOLD = 0.02` "uninformative" cut; but it is only
  emitted on the `block_bootstrap_interval` path behind the H11 gate.
- **Concrete step**: fill `information_gap` into the `Interval` record for every published
  band regardless of gate and treat a gap above `GAP_THRESHOLD` as a refusal to call the
  band a distributional forecast.

### L6. The IID bootstrap undercovers under dependence; the block length must come from the series
- **Source**: `arXiv 2607.06690` (2026) — tsbootstrap
- **Finding**: the IID bootstrap undercovers sharply under dependence; block/residual/sieve/
  wild resampling reduces the deficit, with the sieve nearest to nominal under short-memory
  linear dependence.
- **Repo surface**: `tradingagents/strategies/conformal.py::iid_interval`,
  `...::block_bootstrap_interval`, `...::block_length`, `...::_bootstrap_gate`.
- **Status**: shipped but off by default — `_bootstrap_gate` returns
  `cfg.get("enable_bootstrap_intervals", False)`; the module docstring itself reports
  IID coverage falling from 0.85 (rho=0) to 0.45 (rho=0.8), and the registry's
  `INTERVAL_BENCHMARK = "interval.conformal_iid_floor"` is the weakest arm.
- **Concrete step**: make the block-bootstrap interval the default band and keep the IID
  interval only as the declared floor; add a sieve option for the linear-HAR case.

### L7. Isotonic distributional regression can turn the repo's point forecasts into distributions
- **Source**: `arXiv 2404.02270` (2024) — Postprocessing of point predictions … IDR
- **Finding**: IDR contributes the most to an ensemble of QRA, conformal prediction and
  IDR, and the combination beats state-of-the-art distributional DNNs across two 4.5-year
  electricity test periods. The gain is in quantile shape/tails, exactly what residual
  pooling misses.
- **Repo surface**: `tradingagents/strategies/calibration.py::isotonic_calibrate` and
  `tradingagents/strategies/conformal.py::quantile_band`.
- **Status**: partial — `isotonic_calibrate` exists and is exported, but a grep over
  `tradingagents/` shows **no caller**: isotonic regression is available for confidence
  buckets and is never used to build a predictive interval.
- **Concrete step**: add an IDR postprocessing path that maps a point forecast's
  calibration residuals to a monotone quantile function and ensemble it with the
  conformal band, mirroring the paper's QRA+CP+IDR combination.

### L8. CRPS/QLIKE are declared but never computed — a proper score must be implemented before it can be scored
- **Source**: `arXiv 2308.15443` (2023) — Combining predictive distributions of electricity prices; `arXiv 2102.00968` (2021) — CRPS Learning
- **Finding**: CRPS-optimal weighting is not decision-optimal (higher accuracy, no higher
  bidding profit), and distribution-adaptive (centre-vs-tail) CRPS weighting beats single
  weights. The score is a real, separable axis from economic value.
- **Repo surface**: `tradingagents/strategies/forecast_contract.py::SCORING_RULES`
  (`("CRPS", "QLIKE", "RMSE", "MAE")`) and `prediction_ledger.py::evaluate_forecast`.
- **Status**: partial — `SCORING_RULES` is validated at construction, but a grep shows
  CRPS appears only in that tuple and in a docstring; nothing in the tree computes CRPS
  or QLIKE, so `scoring_rule="CRPS"` currently cannot be backed by a number.
- **Concrete step**: implement `crps_from_quantiles` and `qlike` (the standard
  log-sigma²-based form) in `evaluate.py` and have `evaluate_forecast` compute the score
  from the `Interval`'s quantiles, refusing the row when no density exists.

### L9. Convert point forecasts to quantiles with residual simulation on the log scale over linear base models
- **Source**: `arXiv 2508.15922` (2025) — Probabilistic Forecasting Cryptocurrencies Volatility
- **Finding**: QRS applied to linear base models (HAR/GARCH/ARFIMA) on log-realized
  volatility beats ML meta-models; probabilistic stacking is robust. CRPS/relative
  frequency/Winkler are the evaluation axes.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast` (the base
  forecaster) + `tradingagents/strategies/conformal.py::quantile_band`.
- **Status**: partial — `rv_forecast` produces a point forecast and refuses (naming the
  reason) when the extra leg is missing, but produces no quantiles; the log-RV scale the
  paper shows matters is not guaranteed by the producer.
- **Concrete step**: have `rv_forecast` fit on `log(RV)` and emit residual-simulation
  quantiles, so the published `ForecastRecord`'s `Interval` is a density rather than a
  conformal width around a level.

### L10. Fit and update volatility filters against the score the decision actually uses
- **Source**: `arXiv 2608.02828` (2026) — Proper-Score Observation-Driven Filters
- **Finding**: a filter can be driven by the derivative of **any** proper scoring rule,
  not just the log score; rule, scaling and autoregression are three separable choices,
  and rule choice changes variance-forecast loss, VaR calibration and PIT diagnostics.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast` (OLS HAR) and
  `tradingagents/strategies/volatility_models.py`.
- **Status**: absent — the HAR leg is plain OLS (squared-error), and no proper-score-driven
  update exists in either module.
- **Concrete step**: add an optional QLIKE-driven recursive update of the HAR coefficients
  alongside the OLS fit and report both, so the fit is scored by the same loss the
  forecast is evaluated with.

### L11. Reconcile univariate and multivariate portfolio-variance forecasts
- **Source**: `arXiv 2603.17463` (2026) — Multivariate GARCH and portfolio variance prediction
- **Finding**: reconciliation of univariate and multivariate risk forecasts improves on a
  standard multivariate model, most when the multivariate model is misspecified; noisy
  covariance proxies shrink the gain and blur model identification but do not remove it.
- **Repo surface**: `tradingagents/strategies/covariance_models.py` (Ledoit-Wolf shrinkage,
  EWMA, spectral functionals) and `tradingagents/strategies/book_risk.py`.
- **Status**: absent — no reconciliation step exists between per-name variance forecasts
  and the book covariance.
- **Concrete step**: combine the HAR realized-variance forecasts with the multivariate
  covariance forecast and reconcile the book's variance to the aggregate of its
  constituents before it reaches `book_risk`.

### L12. Decision-time nowcasts belong in the feature set, and any analog baseline must be run
- **Source**: `arXiv 2601.14062` (2026) — Demystifying the trend of the healthcare index;
  `arXiv 2606.22719` (2026) — Leakage-Aware Benchmarking of LLM Forecasting
- **Finding**: mutual OHLC-ratio nowcast features dominate feature importance for next-day
  direction; and under a strict decision-time constraint a kNN macro-analog baseline
  recovers a comparable median IC to a retrieval-augmented LLM, so the real-time input and
  macro similarity — not the LLM — explain most of the signal.
- **Repo surface**: `tradingagents/strategies/extended_indicators.py` (no mutual-ratio
  feature today) and `tradingagents/strategies/data_quality.py` (PIT invariant).
- **Status**: partial — the PIT invariant exists in `data_quality.py`, but no
  nowcast-feature generator and no analog-baseline arm exist.
- **Concrete step**: add mutual-ratio nowcast features to `extended_indicators` and, for
  any nowcast-driven forecast, publish a kNN/analog baseline as a declared benchmark so
  the LLM path cannot claim credit the analog already earns.

### L13. Degrade a forecast claim to an interval only after it beats naive persistence
- **Source**: `arXiv 2607.12248` (2026) — When Directional Accuracy Lies; `arXiv 2606.03184` (2026) — FinStressTS
- **Finding**: neural forecasters routinely fail to beat random-walk/persistence, need
  multiples more data, and are governed by inductive bias rather than capacity; simple AR
  and linear models win in volatility-, tail- and jump-driven regimes.
- **Repo surface**: `tradingagents/strategies/evaluate.py::walk_forward_splits`,
  `...::benchmark_table`, and `tradingagents/strategies/falsification.py`.
- **Status**: partial — the walk-forward and benchmark machinery exists, but the registry's
  `realized_volatility` benchmark set (`volatility.har_rv`, `volatility.naive_trailing_realized`,
  `volatility.garch11`) is not enforced at publication time.
- **Concrete step**: in the publisher, require that the record's evaluation carry a
  same-window naive-trailing-realized score and mark the record "unscored" until it does.

## 4. Where this repo is already ahead of the literature

- **The R² ceiling is implemented, not just cited.** `alpha_eval.ceiling_ratio` computes
  `kappa_hat` and the (2DA−1)², R²/kappa point from `2602.07841`, and
  `forecast_registry.DIRECTIONAL_CEILINGS` binds the paper id to the directional targets —
  the abstract sweep found this paper only six months old and it is already a declared
  contract term here.
- **Base-rate honesty is a first-class instrument.** `calibration.excess_accuracy` and
  `alpha_eval.ceiling_ratio` are wired into `graph/trading_graph.py` (lines ~548-565), so
  the run card carries both the always-up excess and the R² ceiling — matching the
  strongest methodological finding in `2607.12248`, which post-dates most of the corpus.
- **Autocorrelation-aware intervals and the conformal information gap already exist.**
  `conformal.block_bootstrap_interval`, `block_length` and `information_gap` implement
  exactly the H11 axis the tsbootstrap paper (`2607.06690`) and the information-gap note
  (`2608.07479`) argue for; few production forecasters have either.
- **The HAR fitting scheme is already at the literature optimum.** `long_memory.rv_forecast`
  refits each call over a 750-day backward window, which is inside the 630-1,000-day,
  daily-stride optimum `2406.08041` identifies — the repo avoids the suboptimal-scheme
  trap that paper attributes to much of the "ML beats HAR" literature.
- **One authoritative producer per forecast key, with immutable records.** The
  `forecast_contract` / `forecast_registry` / `prediction_ledger` split is stricter than
  anything in the corpus: a forecast cannot be scored without naming its benchmark
  (`forecast_registry.RegistryRow.__post_init__`), and `ForecastEvaluation` is writable
  only by the ledger, which prevents the post-hoc score-editing the corpus repeatedly
  warns about.

## 5. Defects or risks the literature exposes

- **A declared scoring rule that cannot be produced.** `forecast_contract.SCORING_RULES`
  (line 129) admits `"CRPS"` and `"QLIKE"`, and `prediction_ledger.evaluate_forecast`
  accepts them, but no CRPS or QLIKE computation exists anywhere in the tree (grep: the
  token occurs only at `forecast_contract.py:129` and `prediction_ledger.py:292`). Any
  evaluation written with a distributional rule is therefore unverifiable. `arXiv
  2308.15443` / `arXiv 2102.00968`.
- **The default interval path undercovers under autocorrelation.** `conformal._bootstrap_gate`
  (`conformal.py:509-522`) returns `False` unless `enable_bootstrap_intervals` is set, so
  the default band is the IID interval the module's own comment reports at 0.45 realized
  coverage when rho=0.8 — and `forecast_registry.INTERVAL_BENCHMARK` (line 201) is
  literally `"interval.conformal_iid_floor"`. `arXiv 2607.06690` shows the IID bootstrap
  undercovers under dependence. The safe arm exists but is off.
- **`isotonic_calibrate` is dead code on the prediction path.** `calibration.py:143`
  defines it and `calibration.py:406` exports it, but no module imports it (grep over
  `tradingagents/`), so the best-performing postprocessing method in `arXiv 2404.02270`
  is available for confidence buckets yet absent from interval construction.
- **The realized-variance proxy is squared daily returns.** `long_memory.rv_forecast`
  (`long_memory.py:246-249`) uses `returns ** 2` as its RV when no `rv` series is supplied.
  HAR models in `2406.08041` and `2607.05291` are estimated on 5-minute realized variance;
  a squared-daily-return proxy is far noisier, which biases every QLIKE/log-score
  comparison the HAR leg participates in.
- **The registry's candidate pool is empty, so no combination arm exists.** `2607.05291`
  shows the equal-weight HAR+TSFM average dominating either component, and `2304.09947`
  shows online R²-weighting dominating equal weights — but `forecast_registry.CANDIDATE_MEMBERS`
  (line 325) is `()`, so the repo can only score one producer per key and has no
  combination or encompassing test at all.

## 6. Limits of this review

- **Read vs skimmed.** Full-text reads (§2) cover 22 papers chosen from the sweep's high-
  and medium-relevance rows; their abstracts, introductions, methods and (where they
  existed) results/conclusions were read on the rendered PDF. All other papers in the
  1,567-paper category were reached only through the abstract-level evidence pack and
  `booklists/forecasting.json`; claims about them are not made here.
- **Sampling.** The category is dominated by thin single-asset ARIMA/LSTM price-level
  papers and by electricity-price forecasting; I deliberately over-sampled the 2024-2026
  methodological tail (R² bounds, conformal validity, TSFM-vs-HAR, proper scoring) and
  under-sampled the crypto and energy literatures, which transfer only narrowly to an
  equity research engine.
- **Not verified.** I did not run any repo code, tests or backtests (per the review
  protocol), so every `shipped`/`partial`/`absent` status is a reading of the source, not
  an execution result. The CRPS-absence and `isotonic_calibrate`-uncalled findings are
  grep-level static observations; a dynamic import path I did not find could change them.
- **Category boundary.** 1,567 papers list `forecasting` in their book membership but only
  146 carry it as the primary book; cross-listed volatility, correlation and ml-methods
  papers are counted in the composition table as they appear in `index.json`.
