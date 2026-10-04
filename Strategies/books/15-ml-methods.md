# Machine Learning & Deep Learning Methods

`book 15/19` · slug `ml-methods` · 800 papers in the corpus · 62 rated high-relevance by the sweep

## 0. Scope

This category is the methodological substrate of the corpus: the papers that train, validate,
calibrate or refute statistical learners on financial data — deep nets, gradient-boosted trees,
Gaussian processes, RL agents, and the validation machinery (walk-forward, purged CV, deflated
Sharpe, conformal prediction, probabilistic calibration) that decides whether any of it is real.
It matters to this repo less for the model classes themselves — TradingAgents deliberately computes
with deterministic, mostly linear calculators rather than training nets — and more for the *evaluation
discipline*: what makes a backtest a methodological artifact, how to make a probability an honest
probability, and where a sophisticated learner hides behind a mis-specified baseline. This book
therefore centres on the sweep's strongest and most skeptical papers rather than on the many
LSTM-price-prediction papers that dominate the category by count.

## 1. Corpus composition

The evidence pack for this category carries **800 annotated rows**: **62 high-relevance**, 392
medium, 346 low/background. The composition table below is derived from the 60-paper booklist
(`booklists/ml-methods.json`), which is the sweep's top-ranked slice and is representative of the
high-relevance tail.

Primary arXiv category of the 60 booklist papers:

| primary category | n |
| --- | --- |
| q-fin.ST (statistical finance) | 44 |
| cs.LG | 9 |
| q-fin.TR (trading & microstructure) | 2 |
| q-fin.RM | 1 |
| q-fin.GN | 1 |
| econ.EM | 1 |
| stat.ML | 1 |
| cs.CL | 1 |
| **total** | **60** |

Year of the 60 booklist papers:

| year | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n | 2 | 3 | 11 | 6 | 6 | 8 | 10 | 9 | 5 |

This category is dominated by one genre: a recurrent or convolutional net fed OHLCV/technical
indicators to forecast a price or direction, evaluated by prediction error on a single train/test
split — 2020 alone contributes 11 of the 60. That genre is largely irrelevant to a compute-don't-
narrate repo. The high-relevance *minority* is a different literature: evaluation methodology
(multiplicity, walk-forward, purged CV), probabilistic output (conformal, quantile, calibration),
and the negative results showing when deep learning fails to beat a naive baseline. This book
reads that minority.

## 2. Deep reads

### arXiv 2604.15531v1 — Spurious Predictability in Financial Machine Learning (2026)

- **Question**: can a *complete* predictive workflow (feature construction, tuning, selection, portfolio
  mapping) be tested for validity rather than just for backtest Sharpe?
- **Data / setting**: Monte Carlo induced-null environments (white noise, regime-switching vol, a
  Roll-style bid–ask-bounce placebo, a zero-alpha factor null, GARCH(1,1) clustering) plus empirical
  return and volatility-forecasting case studies; 1,000 replications per scenario run through the
  QuantAudit reference implementation.
- **Method**: a two-stage falsification audit. Stage 1 replays the fixed workflow on induced-null
  reference classes that preserve the pipeline's mechanics but remove conditional-mean
  predictability; a workflow that produces statistically significant walk-forward winners there is
  *falsified*. Stage 2 measures selection-induced inflation on real data via the absolute magnitude
  gap ΔZ = Z*_IS − Z*_WF and a stabilised Backtest Inflation Factor.
- **Headline finding**: under a global martingale-difference null the optimised in-sample winner grows
  as Θ(√log K_eff) where K_eff is the *effective* multiplicity (the spectral participation ratio
  (tr Σ)²/‖Σ‖²_F of the search correlation matrix), while strictly disjoint walk-forward evidence
  stays stochastically bounded. At nominal K = 1000 the median in-sample/walk-forward inflation
  ratio was 5.12; nominal K badly overstates K_eff when candidate strategies are correlated.
- **Limitation**: passing the audit is a necessary, not sufficient, condition — it does not certify
  economic truth, and a publicly known null environment invites "meta-overfitting," which the authors
  mitigate only with a blind-parameter protocol they do not fully deploy.

### arXiv 2602.00080v1 — The GT-Score: A Robust Objective Function for Reducing Overfitting (2026)

- **Question**: can anti-overfitting structure be embedded directly in the optimisation objective,
  rather than corrected after the fact?
- **Data / market**: daily OHLCV for the top 50 S&P 500 names, 2010–2024; three technical strategies
  (RSI, MACD, Bollinger) under random search with 25 evaluations per trial.
- **Method**: GT-Score = μ·ln(z)·r²/σ_d, a multiplicative composite of performance, a significance
  gate ln(z) (z = standardised excess mean vs buy-and-hold), an R² consistency term and downside
  deviation; walk-forward with 4-year train / 2-year validation / 1-year step and a 30-day embargo,
  plus a 9000-trial Monte Carlo across 15 seeds.
- **Headline finding**: GT-Score raised the walk-forward generalisation ratio (validation/training
  return) from ~0.185 to 0.365, a 98% improvement, at the cost of slightly lower raw test return
  (43.6% vs 46–50%); paired Monte-Carlo differences were detectable at p < 0.01 but with small
  effect sizes.
- **Limitation**: z is treated as a heuristic gate not a hypothesis test (fat tails and
  autocorrelation break the Gaussian sampling assumption), and the author is explicit that the
  reported p-values are descriptive, not selection-adjusted.

### arXiv 2507.15079v1 — Isotonic Quantile Regression Averaging (iQRA) for Uncertainty Quantification (2025)

- **Question**: how do you turn an ensemble of point forecasts into well-calibrated predictive
  quantiles without hyperparameter tuning?
- **Data / market**: German day-ahead electricity prices, 2015–2024, with a 5-year out-of-sample
  test spanning COVID and the Russian invasion; 25 independently trained NARX nets as the point
  ensemble.
- **Method**: impose stochastic-order constraints (non-negative quantile-regression coefficients) on
  Quantile Regression Averaging; this is enforced by deleting the negative-coefficient variables from
  the linear program, so it is hyperparameter-free and reduces problem complexity. Benchmarked
  against conformal prediction, historical simulation, isotonic distributional regression, plain QRA
  and Lasso QRA.
- **Headline finding**: iQRA beat every benchmark on reliability and sharpness (ACE, CRPS, pinball),
  and in particular beat coverage-based conformal prediction on reliability across confidence levels
  — while needing no regularisation search.
- **Limitation**: isotonicity with respect to the covariate is an assumption justified because the
  covariates are the target's own point estimates; it is not a general solution, and conformal
  prediction's basic form additionally forces a symmetry assumption to convert intervals to quantiles.

### arXiv 2209.05559v6 — Deep Reinforcement Learning for Cryptocurrency Trading: A Practical Approach to Address Backtest Overfitting (2023)

- **Question**: how do you reject a DRL trading agent that only looks good because it was selected?
- **Data / market**: 10 high-volume crypto pairs, 5-minute bars; training 02/02/2022–04/30/2022,
  test 05/01/2022–06/27/2022 — a test window in which the crypto market crashed twice.
- **Method**: cast backtest-overfitting detection as a hypothesis test. Train with *combinatorial
  cross-validation* (split the training data into N=5 groups, take k=2 as validation at a time,
  J=10 splits) so performance is averaged across many market situations; stack per-trial validation
  return vectors into a matrix M, draw row-splits, and estimate the probability of overfitting as
  P(logit < 0), where the logit is the log-odds that the best in-sample strategy ranks below median
  out-of-sample.
- **Headline finding**: agents with a lower estimated overfitting probability earned higher returns
  during the two crashes than more-overfitted agents, an equal-weight portfolio, and the S&P DBM index.
- **Limitation**: a single 10-crypto, 6-week test; the overfitting probability targets hyperparameter
  selection and leakage, not the structural question of whether DRL is the right tool at all.

### arXiv 2101.10942v2 — Absolute Value Constraint: The Reason for Invalid Performance Evaluation Results of Neural Network Models for Stock Price Prediction (2021)

- **Question**: is prediction error (MSE/MAE/RMSE/R²) a valid evaluation criterion for a stock-price
  forecaster?
- **Data / market**: 40 stocks, 20 from Shanghai/Shenzhen and 20 from NASDAQ/S&P 500, 2011–2017.
- **Method**: train six shallow/deep nets (MLP, RNN, LSTM, GRU, BiRNN, BiLSTM) under an orthogonal
  L16(4⁵) experiment design and compare four prediction-error measures against realised return.
- **Headline finding**: a prediction error computed from an absolute value cannot represent the
  signed, directional quantity that actually matters for trading; the same error magnitude can
  correspond to opposite directions. High-accuracy (low-error) models repeatedly failed to be
  directionally useful, so PE is not suitable as the evaluation of a stock-price predictor.
- **Limitation**: the paper is a critique with a demonstration, not a replacement metric; it does not
  propose the new evaluation procedure it calls for, and it does not control for a baseline hit rate.

### arXiv 2509.04541v2 — Finance-Grounded Optimization for Algorithmic Trading (2026)

- **Question**: does aligning the training loss with the *trading* objective beat minimising MSE?
- **Data / market**: 61 Binance crypto assets, daily/hourly/15-minute data, 2022–2025, with
  market-neutral portfolio construction.
- **Method**: a family of differentiable finance-grounded losses — SharpeLoss (variance-normalised,
  scale-invariant), ModSharpeLoss (+ a prediction-quality penalty), PnL, MaxDrawdown (soft-min and
  log variants), mean-variance, mean-CVaR, entropic risk — plus *band* turnover regularisation that
  penalises turnover only outside an admissible range [bb, tb] rather than monotonically.
- **Headline finding**: standard MSELoss-trained LSTMs posted *negative* Sharpe ratios and negative
  PnL (≈ −6%), while LogMDDLoss and modified-Sharpe objectives reached Sharpe ≈ 1.5–1.76 with far
  smaller drawdowns; turnover regularisation added further benefit, and the band variant avoided the
  near-static degeneration of linear turnover penalties.
- **Limitation**: the authors show SharpeLoss is scale-invariant (a degenerate high-leverage solution
  is not penalised), and their modified variant's raw penalty is sign-unstable, which is why they add
  norm-type penalties; results are one market over one window.

### arXiv 2304.09937v1 — Stock Price Predictability and the Business Cycle via Machine Learning (2023)

- **Question**: do ML models degrade in recessions, and can that be fixed by feeding them recession data?
- **Data / market**: S&P 500 index, Dec 1969 – May 2020, divided into seven NBER recession-aligned
  sub-periods; LSTM, BLSTM and GRU with L2 + dropout + early stopping.
- **Method**: for each sub-period, train "in-sample with recession" vs "in-sample without recession"
  (equal-sized), validate on a held-out slice, and evaluate on a test set that is equal parts
  recession and expansion, so recession and expansion performance are directly comparable.
- **Headline finding**: 15 of 21 models had higher MSE in recessions than expansions and 13 had lower
  R²; adding recession history improved only 22 of 42 models with no clear pattern, and adding the
  risk-free rate helped 25 of 42 — both mixed. The two recessions where models did *not* degrade were
  the low-volatility late-70s/early-80s periods, so good recession performance reflected policy-driven
  low volatility, not model merit.
- **Limitation**: the degradation is correlated with volatility but the paper does not isolate cause;
  the prescription is limited to "evaluate in both regimes," with no working remedy.

### arXiv 2107.07206v2 — Credit Scoring Using Neural Networks and SURE Posterior Probability Calibration (2025)

- **Question**: how should classifier probabilities be calibrated when the true probability is never
  observed, and does a deep net beat logistic regression?
- **Data / market**: the UCI Taiwanese credit-card dataset, 30,000 users, 22% default (imbalanced);
  static, dynamic (6-month payment history) and combined feature sets.
- **Method**: compares an F1-optimal logistic regression and a 3×60 feed-forward net under balanced
  cross-entropy, then introduces a Stein-Unbiased-Risk-Estimate (SURE) calibration that minimises an
  unbiased estimate of the MSE to the *unobserved* true probability, with sigmoid or Kumaraswamy
  calibration functions; stacked with Platt scaling.
- **Headline finding**: the net barely beat logistic regression; dynamic features lifted test F1 by
  ~0.10–0.15 over static ones; and stacking SURE with classical Platt improved calibration beyond
  either alone. The paper also shows reliability diagrams and ECE are bin-count-sensitive (10 vs 50
  bins on the same data look "almost perfect" vs "obviously not"), arguing for Brier score / BCE.
- **Limitation**: calibration assumes Gaussian noise on the predicted probabilities, and the σ²
  estimate invokes an (acknowledged) independence assumption between prediction and label.

### arXiv 2406.08041v1 — HARd to Beat: The Overlooked Impact of Rolling Windows in the Era of Machine Learning (2024)

- **Question**: does the HAR realized-volatility model actually lose to ML, once the HAR fitting
  scheme is specified correctly?
- **Data / market**: 1,445 CRSP/TAQ US stocks, 5-minute intraday, Jan 2015 – Oct 2023.
- **Method**: grid the HAR fitting scheme over training-window size × re-estimation frequency (stride),
  then compare against hyperparameter-tuned ML (lasso, RF, GBT, FFNN, LSTM) on an identical
  information set (log-RV + VIX), scored by QLIKE, MSE and realized utility.
- **Headline finding**: the HAR model's edge is almost entirely a fitting-scheme artifact —
  daily re-estimation and a 2.5–4-year rolling window are optimal, and with that scheme HAR beats or
  ties tuned ML at a fraction of the compute while remaining interpretable. Papers that found ML
  winning had used sub-optimal HAR fitting schemes (long strides, short windows).
- **Limitation**: restricted to a narrow information set (RV lags + VIX); the authors explicitly leave
  richer feature sets for future work and do not model jumps or microstructure noise separately.

### arXiv 2310.09903v5 — Integrating Feature Selection and Regression Methods with Technical Indicators (2023)

- **Question**: which indicator/model combination predicts Apple's price best, and does feature
  selection help?
- **Data / market**: 13 years of Apple Inc. daily data, 123 technical indicators, 10 regression models.
- **Method**: wrapper feature selection (forward and backward) over the indicator set, evaluated by
  five error metrics across window lengths.
- **Headline finding**: a **3-day** window is best; **linear and ridge regression win overall**
  (MSE 0.00025), and feature selection helps enormously — MLP +56.47%, SVR +67.42%, linear +76.7%,
  ridge +72.82%. The most useful indicators were Squeeze Pro, Percentage Price Oscillator, Thermo,
  Decay, Archer OBV, Bollinger Bands, Squeeze and Ichimoku.
- **Limitation**: a single name (AAPL) and error-based evaluation, which the same corpus (2101.10942)
  shows is not a valid proxy for trading usefulness; the results are not out-of-sample across assets.

### arXiv 2508.15922v1 — Probabilistic Forecasting Cryptocurrencies Volatility: From Point to Quantile Forecasts (2025)

- **Question**: how should point forecasts of crypto volatility be converted into calibrated quantiles?
- **Data / market**: Bitcoin BTC/USD from Kraken, 2017–2021, daily realized variance from 5-minute
  returns (288/day); 2019–2020 train, 2021 test.
- **Method**: three probabilistic stacking methods fed by 12 base models (HAR, HAR-R, ARFIMA, GARCH,
  LASSO, ridge, SVR, MLP, FNM, RF, LSTM): Quantile Estimation through Residual Simulation (QRS),
  Quantile Linear Regression (QLR), Quantile Regression Forests (QRF), each on raw vs log-RV and with
  or without extended inputs.
- **Headline finding**: QRS applied to **log-transformed RV from linear base models** (HAR/ARFIMA/
  ridge/SVR) had the best CRPS with statistically significant Diebold–Mariano edges; GARCH, LASSO and
  LSTM were worst; QLR suffered quantile crossing in ~12% of cases and raw-RV QRS produced
  inadmissible negative low quantiles in ~3.5% of cases.
- **Limitation**: one asset (BTC); QRS assumes past residuals represent future uncertainty, inherits
  base-model bias, and does not model time-varying error distributions.

### arXiv 2411.15674v1 — Quantile Deep Learning Models for Multi-Step Ahead Time Series Prediction (2024)

- **Question**: can deep nets output a full conditional quantile fan for multi-step forecasts without
  losing point accuracy?
- **Data / market**: Bitcoin and Ethereum daily closes plus benchmark series.
- **Method**: replace the output-layer loss of RNN/LSTM/BD-LSTM/ED-LSTM/Conv-LSTM with the quantile
  (pinball) loss at q ∈ {0.05, 0.25, 0.50, 0.75, 0.95}, univariate and multivariate, grouped-percentile
  and vector-based output parameterisations, benchmarked against conventional MSE-trained equivalents.
- **Headline finding**: the quantile loss adds calibrated predictive quantiles at **no loss** of point
  accuracy versus MSE-trained models, and handles volatility and extremes better.
- **Limitation**: the point estimate is taken as the median quantile; the paper does not test on a
  trading objective, and quantile crossing is not structurally prevented in all parameterisations.

### arXiv 2602.17851v1 — Beyond the Numbers: Causal Effects of Financial Report Sentiment on Bank Profitability (2026)

- **Question**: is report sentiment *causally* linked to profitability, or only correlated?
- **Data / market**: 10 banks on the Nepal Stock Exchange, quarterly reports 2013–2024; FinancialBERT
  sentiment scores on the report narrative.
- **Method**: a **causal forest** (honest splitting, AIPW, propensity-score weighting) for individual
  treatment effects, with XGBoost for tabular prediction and **SHAP** used to decorrelate and re-rank
  feature importance, since raw Gini/gain importance "overfits to training data and yields biased
  assessments, especially with highly correlated features."
- **Headline finding**: significant, covariate-conditioned causal associations were found between
  balance-sheet / expense-management variables and profitability, with effects modulated by loan-
  portfolio composition and leverage; the paper's methodological claim is that correlated features
  defeat impurity-based importances and a causal framework is needed to separate cause from predictor.
- **Limitation**: ten firms in one market, a preprint working paper; the causal identification rests
  on unconfoundedness that is not testable here.

### arXiv 2605.16324v1 — Bi-Level Chaotic Fusion Graph Convolutional Network for Stock Market Prediction Interval (2026)

- **Question**: can deep nets produce prediction intervals that are both *calibrated and sharp* across
  regimes, unlike a single point forecast?
- **Data / market**: 43 NSE companies across eight sectors, 2016–2026.
- **Method**: a spatio-temporal graph net with a bi-level chaotic-fusion feature transform (logistic +
  tent maps), separate nonlinear heads for interval centre and width, volatility-aware gating for
  regime dependence, and a Lower-Upper Bound Estimation (LUBE) training objective.
- **Headline finding**: reached the lowest Winkler score (0.0778), tightest intervals (PIAW = 0.1407)
  and highest coverage (PICP = 96.6%), statistically significant vs LSTM/GRU/GCN/HGNN baselines by
  Diebold–Mariano.
- **Limitation**: interval quality is reported by Winkler/PICP on one market's in-sample-style split;
  the LUBE objective is a loss-based interval estimator with no distribution-free coverage guarantee,
  unlike conformal methods.

## 3. Learnings applicable to this repo

### L1. Penalise selection with *effective*, not nominal, multiplicity

- **Source**: `arXiv 2604.15531` (2026) — Spurious Predictability in Financial Machine Learning.
- **Finding**: under a global martingale-difference null the optimised in-sample statistic grows as
  Θ(√log K_eff), where K_eff = (tr Σ)²/‖Σ‖²_F is the spectral participation ratio of the candidate
  correlation matrix. Using the nominal trial count N overstates the deflation when candidates are
  correlated: at nominal K = 1000 the median in-sample/walk-forward inflation ratio was 5.12.
- **Repo surface**: `tradingagents/strategies/evaluate.py::_selection_threshold` and
  `tradingagents/strategies/trial_ledger.py::trial_stats`.
- **Status**: `partial` — `deflated_sharpe_report` deflates by N and reports provenance, and
  `trial_stats` returns `sharpe_dispersion` from the ledger, but `_selection_threshold` falls back to
  a bare `sqrt(2·log(n_trials))` tagged `"assumed"` when dispersion is missing, and no code computes
  a K_eff from the correlation of the trial-return streams.
- **Concrete step**: when `trial_stats` supplies ≥2 return series, build their correlation matrix and
  compute K_eff = (tr Σ)²/‖Σ‖²_F, then deflate by K_eff instead of `n_trials` (or report both with
  provenance `"effective"`).

### L2. Add an induced-null falsification gate ahead of any backtest claim

- **Source**: `arXiv 2604.15531` (2026) — Spurious Predictability in Financial Machine Learning.
- **Finding**: replaying a fixed workflow on (a) a martingale-difference reference class and (b) a
  bid–ask-bounce microstructure placebo falsifies pipelines that hallucinate signal or exploit
  non-investable artifacts; a correctly specified workflow produces bounded walk-forward winners on
  both. Volatility-forecasting results that used random K-fold instead of walk-forward were
  mechanically improved under the null.
- **Repo surface**: `(new module)` — the existing `tradingagents/strategies/falsification.py` implements
  *thesis* falsification (numeric invalidation conditions on a live decision), which is a different
  concept; there is no synthetic-null runner.
- **Status**: `absent`.
- **Concrete step**: add `strategies/null_audit.py` with generators for a zero-mean i.i.d. series, a
  GARCH(1,1) zero-mean series and an MA(1) bid–ask-bounce placebo, a runner that replays a candidate
  signal through the existing `evaluate.walk_forward_splits`, and a refusal when the walk-forward
  winner exceeds the Monte-Carlo null quantile.

### L3. Estimate a probability of backtest overfitting from combinatorial splits, not a boolean

- **Source**: `arXiv 2209.05559` (2023) — Deep RL for Cryptocurrency Trading: Address Backtest Overfitting.
- **Finding**: combinatorial cross-validation (N=5 groups, k=2 held out, J=10 splits) across many
  market situations, with the overfitting probability P(logit < 0) taken over row-splits of the
  trial-return matrix, low-overfit agents beat more-overfitted agents and the benchmark through two
  crashes; single-validation walk-forward "can easily result in overfitting."
- **Repo surface**: `tradingagents/strategies/evaluate.py::cpcv_overfit_mask` / `pbo_flag` /
  `purged_cpcv_splits`.
- **Status**: `partial` — purged CPCV folds and a *boolean* overfit flag exist, but the repo reduces
  the combinatorial result to `oopcs[best] < threshold` rather than a probability over many splits.
- **Concrete step**: over the combinatorial splits already yielded by `purged_cpcv_splits`, rank the
  best in-sample trial against its out-of-sample rank per split and return P(logit < 0) as a
  numeric overfit probability beside the existing mask.

### L4. Enforce disjoint in-sample/walk-forward blocks and an embargo

- **Source**: `arXiv 2604.15531` (2026) and `arXiv 2602.00080` (2026).
- **Finding**: selection must be measurable with respect to the in-sample σ-field only; leakage via
  normalisation over the full sample, survivorship, or overlapping labelling horizons lowers the noise
  floor and manufactures alpha. Random cross-validation breaks temporal order. The GT-Score
  walk-forward used a 4y/2y/1y split with a 30-day embargo and improved the generalisation ratio to 0.365.
- **Repo surface**: `tradingagents/strategies/evaluate.py::walk_forward_splits`,
  `purged_cpcv_splits(n, n_splits, embargo)`, `oos_split`.
- **Status**: `shipped` — embargo is a first-class parameter of `purged_cpcv_splits` and
  `walk_forward_splits` yields strictly ordered (train, test) slices; paper's risk is a caller-side
  concern, not a missing capability.
- **Concrete step**: none required beyond keeping the 30-day embargo default in any new caller; do not
  add a K-fold splitter for time-series inputs.

### L5. Score candidate configurations on a composite robustness objective, not raw return

- **Source**: `arXiv 2602.00080` (2026) — The GT-Score.
- **Finding**: a multiplicative objective combining performance, a significance gate ln(z), an R²
  consistency term and downside deviation raised the walk-forward generalisation ratio by 98%
  (0.185 → 0.365) at the cost of lower raw test return — i.e. the reliability gain is bought by
  refusing parameterisations whose in-sample strength will not survive.
- **Repo surface**: `tradingagents/strategies/config_robustness.py::config_robustness` and
  `tradingagents/strategies/evaluate.py::_rc_metric`.
- **Status**: `partial` — `config_robustness` already refuses the argmax in favour of an edge/plateau
  read, and `reality_check`/`spa` adjust for multiplicity, but the per-cell objective is a plain
  `score` (Sharpe or mean) with no significance/consistency/downside composite.
- **Concrete step**: when ranking grid cells, multiply the Sharpe term by a capped significance factor
  (e.g. `log(max(z,1))` clipped) and divide by downside deviation, so a lone high-return cell with no
  statistical edge cannot win the search.

### L6. Add a parametric (Platt) calibration arm and a Brier/ECE honesty metric

- **Source**: `arXiv 2107.07206` (2025) — Credit Scoring with SURE Posterior Probability Calibration.
- **Finding**: stacking a SURE (Stein's unbiased risk estimate) calibration with classical **Platt
  scaling** improved predicted-probability calibration beyond either alone; reliability diagrams and
  ECE are bin-count-sensitive (the same data looks "almost perfect" at 10 bins and "obviously not" at
  50), so Brier score / BCE should be reported too. Deep nets barely beat logistic regression.
- **Repo surface**: `tradingagents/strategies/calibration.py::isotonic_calibrate`,
  `fit_buckets`, `calibrated_confidence`, `_calibration_error`.
- **Status**: `partial` — the module has isotonic regression and a fixed-bin bucket path, but no Platt
  (sigmoid) calibrator and no Brier/BCE score; `_calibration_error` is the ECE-style bin-gap that the
  paper shows is biased.
- **Concrete step**: add `platt_calibrate(entries)` (fit a two-parameter logistic regression on
  `{confidence, won}`) plus `brier_score(entries)`, and report the Brier score beside
  `calibration_table_text` so the bin-count sensitivity is visible.

### L7. Constrain probability/quantile bands by stochastic order before trusting coverage

- **Source**: `arXiv 2507.15079` (2025) — Isotonic Quantile Regression Averaging.
- **Finding**: imposing the stochastic-order (non-negative-coefficient) constraint on quantile
  regression is hyperparameter-free, reduces problem complexity, and beat conformal prediction on
  reliability across confidence levels; basic conformal prediction additionally requires a symmetry
  assumption to turn intervals into quantiles, and its width is constant in the point forecast.
- **Repo surface**: `tradingagents/strategies/conformal.py::quantile_band`, `rolling_band`,
  `calibrate`, `block_bootstrap_interval`.
- **Status**: `partial` — the module already states that block bootstrap does not restore nominal
  coverage under strong persistence (0.75 vs 0.90 at ρ=0.8) and tells callers to read realised
  coverage, which is exactly the right honesty posture; but `quantile_band` builds the band from an
  unconstrained point spread with no monotonicity constraint tying width/level to the point estimate.
- **Concrete step**: in `quantile_band`/`rolling_band`, derive the quantile levels as a monotone
  function of the point estimate (e.g. enforce non-decreasing bounds in the predicted value) so the
  band cannot cross; report the constraint in the `basis` string.

### L8. Never judge a forecaster by prediction error alone; quote the directional baseline

- **Source**: `arXiv 2101.10942` (2021) — Absolute Value Constraint.
- **Finding**: MSE/MAE/RMSE take an absolute value and therefore cannot represent the signed direction
  that trading depends on; the same error magnitude maps to opposite directions, so PE "is not
  suitable as an evaluation indicator." Across 40 stocks and six nets, low-error models were
  repeatedly not directionally useful.
- **Repo surface**: `tradingagents/strategies/calibration.py::excess_accuracy` and
  `tradingagents/strategies/alpha_eval.py::alpha_score`, `insight_accuracy`.
- **Status**: `partial` — `excess_accuracy` already reports a hit rate *minus the always-up baseline*
  per walk-forward fold, which is precisely the fix the paper implies; `alpha_score` still carries a
  magnitude error and `insight_accuracy` aggregates hits without the always-up reference.
- **Concrete step**: have `insight_accuracy` (and any scorecard over `prediction_ledger`) route
  through `excess_accuracy` so every published accuracy figure carries its directional baseline.

### L9. Re-estimate the HAR baseline daily over a long window before claiming ML wins

- **Source**: `arXiv 2406.08041` (2024) — HARd to Beat.
- **Finding**: over 1,445 US stocks the HAR realized-vol model's edge is a fitting-scheme artifact:
  daily re-estimation with a 2.5–4-year rolling window is optimal, and with that scheme HAR beats or
  ties hyperparameter-tuned lasso/RF/GBT/FFNN/LSTM at far lower cost. Studies that found ML winning
  had used sub-optimal HAR schemes.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast`, `MEMORY_WINDOW = 750`,
  `HAR_MIN_OBS = 64`.
- **Status**: `partial` — `rv_forecast` is a HAR-family regression over log-RV with a memory
  parameter, but its fitting scheme (window, stride) is not exposed and the module gates on
  `enable_long_memory` (default off).
- **Concrete step**: document and expose the HAR window/stride explicitly (default to a ~750-day
  rolling window re-estimated per call) and state that it is the benchmark any ML vol forecaster must
  beat, since the paper shows a mis-specified HAR is the only reason ML appears to win.

### L10. Report performance per regime, and do not read low-volatility periods as model merit

- **Source**: `arXiv 2304.09937` (2023) — Stock Price Predictability and the Business Cycle.
- **Finding**: 15/21 RNN models had higher MSE in recessions and 13 had lower R²; adding recession
  history helped only 22/42 models and the risk-free rate 25/42 (both mixed). The recessions where
  models did *not* degrade were the low-volatility late-70s/early-80s periods, so good recession
  performance reflected policy-stabilised volatility, not ML merit.
- **Repo surface**: `tradingagents/strategies/regime_performance.py::regime_conditioned_performance`
  and `tradingagents/strategies/evaluate.py::regime_split_performance`.
- **Status**: `shipped` — regime-conditioned hit/return tabulation exists and is exactly the right
  instrument; the risk is interpretive (attributing a low-vol regime's good read to signal quality),
  not a missing calculator.
- **Concrete step**: when surfacing a regime's hit rate, print the regime's realised volatility
  beside it so a low-vol "good" regime is not read as model merit.

### L11. Treat correlated features as a first-class obstacle to attribution

- **Source**: `arXiv 2602.17851` (2026) — Beyond the Numbers.
- **Finding**: impurity/gain feature importances "overfit to training data and yield biased
  assessments, especially with highly correlated features," making individual contributions
  indiscernible; the paper uses SHAP to decorrelate and re-rank, with a causal forest (AIPW, honest
  splitting) to move from prediction to heterogeneous treatment effects.
- **Repo surface**: `tradingagents/strategies/statistical.py::variance_inflation_factor` and
  `tradingagents/strategies/score_engine.py::combine` / `align`.
- **Status**: `partial` — the repo computes VIF and `score_engine` already refuses to attribute a
  composite to non-monotonic legs, but no consumer gates a factor-attribution claim on collinearity,
  and there is no decorrelation-aware importance (no SHAP anywhere in `tradingagents/`).
- **Concrete step**: in any factor-contribution read, compute the pairwise VIF among the contributing
  legs and withhold per-leg attribution (report "collinear, not separable") when VIF exceeds a
  threshold, rather than publishing an ordered importance list.

### L12. Where a probabilistic output is built, build it on log-scale linear base models

- **Source**: `arXiv 2508.15922` (2025), `arXiv 2411.15674` (2024) and `arXiv 2605.16324` (2026).
- **Finding**: QRS quantiles from **log-transformed RV** on linear base models (HAR/ARFIMA/ridge/SVR)
  had the best CRPS with significant Diebold–Mariano edges; GARCH, LASSO and LSTM were worst; QLR
  crossed quantiles in ~12% of cases and raw-RV QRS produced inadmissible negative low quantiles in
  ~3.5%. Deep quantile nets add calibrated quantiles at no point-accuracy loss, and a two-headed
  centre/width net with LUBE achieved PICP 96.6% / Winkler 0.0778 — but with no distribution-free
  coverage guarantee.
- **Repo surface**: `tradingagents/strategies/conformal.py::quantile_band`,
  `tradingagents/strategies/long_memory.py::rv_forecast`,
  `tradingagents/strategies/book_risk.py::var_coverage_test`.
- **Status**: `partial` — the repo builds conformal bands and tests VaR coverage (Kupiec +
  Christoffersen), but nothing derives volatility quantiles by residual simulation from the HAR
  forecast, and the log-scale requirement is not enforced anywhere.
- **Concrete step**: add a residual-simulation quantile builder over `rv_forecast`'s log-RV residuals
  (never raw RV) and validate it with the existing `var_coverage_test`, so a probabilistic vol band
  enters the tail stack from the winning configuration rather than from a deep net.

## 4. Where this repo is already ahead of the literature

- **Selection-aware evaluation is native, not bolted on.** `evaluate.py` carries `deflated_sharpe`,
  `probabilistic_sharpe`, `reality_check`, `spa`, `purged_cpcv_splits`, `pbo_flag` and
  `cpcv_overfit_mask`; `trial_ledger.py` records one immutable row per evaluated candidate and
  `trial_stats` reads N and Sharpe dispersion back. Most papers in this category report a single
  backtest Sharpe with no multiplicity correction at all.
- **Intervals are reported with their realised coverage and a refusal to overstate it.**
  `conformal.py` documents that block bootstrap fails to restore nominal coverage under strong
  persistence (0.75 vs 0.90 at ρ=0.8) and mandates reading realised coverage; `tail_risk.py` widens
  (never narrows) a band by quality and uncertainty. Papers here routinely report nominal PICP as if
  achieved.
- **A directional baseline is mandatory.** `calibration.excess_accuracy` subtracts the always-up
  baseline per walk-forward fold — the exact repair 2101.10942 calls for but does not implement.
- **Isotonic + regime-bucketed calibration already exists**, ahead of the one-shot Platt scaling most
  calibration papers use (`calibration.py::isotonic_calibrate`, `fit_buckets_by_regime`).
- **Survivor labelling** (`coverage_window.SURVIVOR_ONLY`, `padded_days`) names the current-constituent
  universe leak that the ML-backtest literature repeatedly re-discovers.

## 5. Defects or risks the literature exposes

- **Deflation can silently fall back to nominal multiplicity.** `evaluate.py::_selection_threshold`
  returns `sqrt(2·log(n_trials))` with provenance `"assumed"` when `sharpe_dispersion` is absent;
  2604.15531 shows the correct quantity is K_eff ≤ N under correlated search, so a caller that
  ignores the provenance can under-deflate a correlated grid by a large factor.
- **The calibration-error metric inherits a known bias.** `calibration.py::_calibration_error` is an
  ECE-style fixed-`_BINS` gap; 2107.07206 demonstrates that ECE is bin-count-sensitive and biased
  toward densely populated bins, so the repo's single calibration number can read "calibrated" on a
  coarse binning that a finer one would reject.
- **A non-significant or error-only accuracy figure can still be published.** `alpha_eval.py::alpha_score`
  records a magnitude error and `insight_accuracy` aggregates hit rates without a baseline; 2101.10942
  is the direct evidence that such numbers are not valid trading measures. The fix exists
  (`excess_accuracy`) but is not the only path to a published accuracy.
- **Regime reads can be misattributed.** `regime_performance.py::regime_conditioned_performance`
  tabulates per-regime outcomes without the regime's realised volatility; 2304.09937 shows a
  low-volatility regime produces a good-looking read that is a policy artifact, not signal.

## 6. Limits of this review

I read 14 papers in full text — abstract, introduction, method, results and conclusion — chosen from
the methodology/skepticism tail of the category rather than the LSTM-price-prediction majority, which
I sampled only through the evidence pack and booklist metadata. The 392 medium-relevance rows were
not re-read; several relevant 2026 preprints (e.g. 2606.31251 on GAMLSS-modelled Information Ratio,
2604.09650, 2601.16274) were left to abstract level. The corpus composition numbers in §1 are derived
from the 60-paper booklist alone and are not a census of all 800 rows — the medium/low slices are
summarised from the evidence pack's category counts, not independently recounted. Repo claims are
from reading the module docstrings and declaration surfaces named in each learning; I did not execute
any calculator, and I did not verify the wiring of these calculators into agent tools, so a
`shipped` status means the symbol and its documented behaviour exist, not that a caller consumes it.
SHAP is asserted absent from `tradingagents/` on the strength of a targeted search for `SHAP`/
`Shapley`/`isotonic`/`conformal`/`brier`; a dependency-free re-implementation under a different name
was not exhaustively ruled out.
