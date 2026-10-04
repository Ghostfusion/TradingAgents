# Regimes, Change Points & Bubbles

`book 07/19` · slug `regime-changepoint` · 663 papers in the corpus · 39 rated high-relevance by the sweep

## 0. Scope

This category is the literature of *the market's state as a latent variable*: Markov-switching and hidden-Markov regime models (and their failure modes — label instability, filtered vs smoothed state estimates, non-identifiable transition dynamics), change-point detection (CUSUM, Bayesian online, segmentation + clustering), and bubble/crash detection (LPPL/JLS critical points, log-periodicity, catastrophe and multifractal crash indices, Hurst/roughness). It matters to this repo because the entire analyst/risk stack is meant to be regime-aware: `regime.py`, `regime_state.py`, `regime_score.py` and `regime_performance.py` gate entries and scale position size, `regime_performance.regime_conditioned_performance` conditions backtest readouts, and the governing rule ("compute, don't narrate") makes the *distinction between a filtered (tradeable) and a smoothed (look-ahead) state estimate* a correctness boundary, not a style choice. The category also supplies the strongest negative results: naive regime switching often fails out-of-sample for reasons the models cannot fix.

## 1. Corpus composition

Header counts (authoritative, from the evidence pack): **663** annotated rows — **39 high**, **409 medium**, **215 low**. The booklist carries full bibliographic metadata for the **top 60**.

Decade distribution of the **top-60 booklist** (the hand-selected core) and of the **39 high-relevance rows**:

| decade | booklist (60) | high rows (39) |
| --- | --- | --- |
| 2000–2009 | 10 | 3 |
| 2010–2019 | 14 | 11 |
| 2020–2029 | 36 | 25 |

Primary category of the top-60 booklist (one category per paper):

| primary category | papers |
| --- | --- |
| q-fin.ST (statistical finance) | 35 |
| cond-mat.stat-mech | 5 |
| q-fin.RM | 4 |
| q-fin.PM | 3 |
| q-fin.TR | 3 |
| cs.LG | 3 |
| stat.ME, q-fin.GN, econ.GN, econ.EM, q-fin.CP, physics.soc-ph, cond-mat.dis-nn | 1 each |

The category is dominated by **q-fin.ST** and by the last seven years: 25 of the 39 high-relevance rows and 36 of the 60 booklist papers are 2020s. The recent mass is regime-switching applied to volatility forecasting and to portfolio allocation (HMM + RL, regime-gated mixtures-of-experts, text-augmented shift detection), while the durable core — Hamilton filtering vs Baum-Welch, statistical jump models, Bayesian online change-point detection, and the Sornette LPPLS crash model — sits in 2004–2019. A large fraction of the medium/background rows attach the category only because they *use* a regime label or a structural-break test as a sub-step; the high-relevance set is where the state model itself is the contribution.

## 2. Deep reads

### arXiv 2402.05272v3 — Downside Risk Reduction Using Regime-Switching Signals: A Statistical Jump Model Approach (2024)

- **Question**: does a more *persistent* regime identifier produce a better downside-risk strategy than a Gaussian HMM?
- **Data**: daily total-return series of S&P 500, DAX, Nikkei 225, 1970–2023; 3-month T-bill risk-free; out-of-sample test 1990–2023 with 10 bps one-way cost and a one-day trading delay.
- **Method**: a 0/1 strategy (100% risky in a favourable state, 100% cash otherwise); a 2-state Gaussian HMM (3000-day rolling window, Viterbi decode + rolling-mean smoothing), versus a statistical jump model that clusters EWM downside-deviation and Sortino features with an explicit jump penalty λ, selected by time-series CV that maximises the strategy's validation Sharpe.
- **Headline finding**: the HMM's online state path flips 8.5×/year (still ~2×/year with a 20-day median filter), while the jump model at λ≈50 reduces this to <1×/year; the JM-guided strategy lowers volatility and MDD and lifts Sharpe (S&P 500: 0.68 vs 0.54 HMM vs 0.48 buy-and-hold), raising CAGR 1–3.9%.
- **Limitation**: the identification task is *descriptive*, not predictive — the strategy only profits if an identified regime persists; there is ~half a month of latency detecting the onset and end of the COVID crash, and the 0/1 switch is acknowledged as too drastic for many mandates.

### arXiv 0904.1500v1 — Regime Switching Volatility Calibration by the Baum-Welch Method (2009)

- **Question**: is the Hamilton filter the right way to calibrate a regime-switching volatility model?
- **Data/method**: two-state lognormal regime-switching model on S&P 500; the Hamilton filter's maximum-likelihood recursion versus the Baum-Welch (forward-backward EM) algorithm, worked out for multivariate Gaussian mixtures.
- **Headline finding**: Baum-Welch is a *complete* estimation method — it recovers the full parameter set {A,B,π} by MLE with its own optimisation step, whereas the Hamilton filter needs the invariant-distribution assumption to start its recurrence; BW is validated in and out of sample on the S&P 500.
- **Limitation**: the paper is about calibration mechanics, not economic performance; the non-convex likelihood still requires multiple starts, and the comparison relies on the Hamilton filter's starting assumption rather than a like-for-like objective.

### arXiv 2605.14976v3 — Multi-regime Markov-switching models with time-varying transition probabilities (2026)

- **Question**: can K-regime Markov-switching models with time-varying transition probabilities (TVTP) be identified and estimated when regimes have their own means and variances?
- **Data/method**: Monte Carlo across K=2 and K=3, three transition specifications (lagged-observation, exogenous covariate, GAS score-driven), plus US Treasury zero-coupon yield changes 1961–2024 at four maturities; open-source `multiregimeTVTP` R package.
- **Headline finding**: regime means, variances and transition probabilities are reliably recovered, and the filtered regime probabilities are accurate under correct specification (MSE < 0.008); but the GAS score coefficient is *statistically non-identifiable* — a ridge in the joint (σ², A) likelihood — and on real Treasury data 99 of 100 starts failed to converge with the score coefficient collapsing to zero, so the GAS model fell back to constant probabilities.
- **Limitation**: coverage of TVTP transition probabilities is systematically below nominal 95% (worst at K=3); the one-step-ahead conditional mean is insensitive to the transition specification because the regime means dominate it, so a good forecast is not evidence the dynamics are right.

### arXiv 2606.23492v1 — Continuous Hidden Markov Models for Equity Returns: Heavy-Tail Emission Families and Regime-Conditional Value-at-Risk (2026)

- **Question**: can a low-state continuous HMM reproduce the three Cont stylized facts *and* support a regime-conditional risk forecast?
- **Data/method**: SPY, a sector-balanced 30-ticker panel, a CRSP cross-decade transfer, and a six-asset copula extension; Gaussian / Student-t / Laplace / generalised-error emissions under one shared forward-backward recursion with quantile initialisation; explicit-duration HSMM benchmarks.
- **Headline finding**: the slow decay of absolute-return autocorrelation is a sum of finitely many geometric modes bounded by the rank of the centred transition matrix, and that rank bound is *not active* at a few states — marginal flexibility, not more decay modes, closes the fit gap; a heavy-tailed emission reproduces the stylized facts with no tuning hyperparameter, and a regime-conditional VaR from the filtered posterior passes a joint conditional-coverage test at α=0.05 (Engle-Manganelli DQ p=0.156 at K=3).
- **Limitation**: daily US equities in stable periods only; periodic refitting is recommended when regimes drift, and the static-fit OoS pass rate collapses on a calm slice (2004–2006 OoS KS pass 3–5%) even though the in-sample fit is decade-robust.

### arXiv 2605.27848v1 — Regime-Based Portfolio Allocation Using Hidden Markov Models and Reinforcement Learning (2026)

- **Question**: does an HMM regime signal plus a reinforcement-learning allocator beat rule-based rotation?
- **Data/method**: daily SPY/TLT/GLD 2004–2025; a BIC-selected 3-state Gaussian HMM (low-vol / transitional / high-vol) with filtered (Hamilton forward) probabilities and RTS smoothing for inspection; a tabular policy-iteration RL agent whose state is the HMM regime; 70/30 chronological split with a one-day execution lag.
- **Headline finding**: state-conditional means are economically interpretable (SPY dominates calm, gold defends in stress), and the RL policy attains Sharpe 0.83 in the OOS window versus 0.65 for buy-and-hold SPY, with the three-state HMM preferred by AIC/BIC over two states.
- **Limitation**: transaction costs are set to zero (explicitly acknowledged), Gaussian emissions under-represent jumps, the tabular MDP limits flexibility, and "smoothed probabilities partly address" but do not remove regime-boundary uncertainty.

### arXiv 2601.10732v1 — Regime-Dependent Predictive Structure Between Equity Factors: Evidence from Granger Causality (2026)

- **Question**: does the lead-lag structure between equity factors change across regimes?
- **Data/method**: 35 years of Fama-French factors (1990–2024); a Student-t HMM for regime labels; regime-conditional Granger causality with Bonferroni correction and event-based out-of-sample validation across six stress episodes.
- **Headline finding**: Value (HML) Granger-causes Size (SMB) only in crisis regimes (p<1.9e-5, 9-day lag, holding in 5 of 6 stress events); the Student-t HMM detects the 2011 EU-debt crisis at 69.4% of event days where a Gaussian model assigns 0.0%.
- **Limitation**: the same paper's own trading strategy *loses* money (−6.1% annual vs +1.9% buy-and-hold, Sharpe −0.75) — statistical predictability with a ~2% R² increment is not economic predictability; regime labels use full-sample information, so the split is not clean; the 2022 rate-hike episode reverses the direction.

### arXiv 2606.02657v1 — Regime-Arrival Uncertainty in Generalization Bounds under Distribution Shift (2026)

- **Question**: why does a model trained in one regime mix fail when deployed in another?
- **Data/method**: a two-state calm/crisis Markov model with an exact risk decomposition; 25 years of daily prices for ten global equity indices, regimes inferred by a two-state Gaussian HMM on [log return, 20-day realized vol]; rolling-origin (8y train / 2y test) with five estimator families.
- **Headline finding**: the deployment gap factorises exactly as (p₀₁ − π)·(R₁ − R₀); a domain classifier separates calm from crisis almost perfectly (0.93), yet an ex-post penalty using the *realized* future crisis fraction tracks the realized gap at Spearman ρ=0.729 [0.635, 0.801], while the training-only estimate (p₀₁ from the train window) fails completely (ρ≈0.084, CI contains 0).
- **Limitation**: a diagnostic, not a forecast — the escape condition π=p₀₁ is mathematically identified but empirically unreachable from historical windows; two regimes only; regime labels are HMM-inferred, not observed.

### arXiv 2004.09963v3 — Structural clustering of volatility regimes for dynamic trading strategies (2020)

- **Question**: can the number of volatility regimes be *learned* instead of assumed?
- **Data/method**: 200 synthetic series (Gaussian and Laplace segment mixtures) plus SPY 2008–2020 and panels of indices, large caps, ETFs and FX pairs; Mood-test change-point detection partitions the series into locally stationary segments, a distance matrix between segment distributions is clustered spectrally (eigengap and a gradient-descent k-selection).
- **Headline finding**: the eigengap method recovers the true segmentation at mean Fowlkes-Mallows 0.93 (Gaussian) / 0.94 (Laplace); on SPY it learns five volatility clusters and the resulting online risk-avoidance strategy validates out of sample; the parametric Bartlett test over-segments far more than the non-parametric Mood test on Laplace segments.
- **Limitation**: segmentation mismatches (4/100 Gaussian, 11/100 Laplace) occur when a segment is sandwiched between two more-similar neighbours; a detected change point need not be a regime change (one SPY break had no volatility shift); the regime count depends on the analysis window length.

### arXiv 1905.09647v2 — Real-time Prediction of Bitcoin Bubble Crashes (2019)

- **Question**: can the LPPLS confidence indicator warn of crypto crashes in real time?
- **Data/method**: daily Bitcoin/USD ~2017–2019, then 1-hour and 30-minute bars; the log-periodic power law singularity model of Johansen-Ledoit-Sornette, calibrated over rolling windows, with the confidence indicator defined as the fraction of qualified LPPLS fits.
- **Headline finding**: on daily data the LPPLS confidence indicator *fails* to warn of short-lived bubbles, especially positive ones; an adaptive multilevel detection on 1-hour/30-minute bars detects the bubbles and forecasts the crashes, with short-window indicators informative at day-to-week scale and long-window indicators stable at week-to-month scale.
- **Limitation**: the method is scale-dependent and needs sub-daily data for short episodes; LPPLS diagnoses only endogenous bubbles, so a crash it misses is likely exogenous rather than evidence of no risk.

### arXiv 2101.03625v1 — The 'COVID' Crash of the 2020 U.S. Stock Market (2021)

- **Question**: was the February–March 2020 crash caused by an external shock or by an endogenous bubble?
- **Data/method**: daily Wilshire 5000, S&P 500, S&P MidCap 400, Russell 2000, Jan 2019–Dec 2020; the LPPLS model with the confidence indicator, plus a post-mortem on the distribution of the estimated critical time.
- **Headline finding**: all four indices showed the LPPLS bubble signature before the crash (all lost >⅓ in five weeks; mid- and small-caps lost more than large-caps); the inferred bubble inception dates to as early as September 2018, and the critical-time density is positively skewed — the paper argues the crash was endogenous, not caused by COVID.
- **Limitation**: LPPLS is parametric and can only flag endogenous bubbles; the COVID narrative is rejected by model fit rather than by an identified mechanism, and the bubble-start estimate varies materially across market-cap sectors.

### arXiv 2308.00087v1 — Efficient multi-change-point analysis to decode economic crisis information from the S&P 500 mean market correlation (2023)

- **Question**: can change points in the S&P 500 mean market correlation date macroeconomic crises, retrospectively and online?
- **Data/method**: ~20 years of daily S&P 500 mean market correlation (dot-com, GFC, euro crisis); a Bayesian multi-trend change-point analysis with an efficient open-source Python implementation; run both in retrospect and online-adaptive over pre-crisis segments.
- **Headline finding**: change-point distributions agree well with major crisis events and support reading the mean market correlation as an informative macro measure; the online sensitivity horizon is roughly 80–100 trading days after a crisis onset, and the results point to the U.S. housing bubble as the GFC trigger.
- **Limitation**: the online detection is *pre-crisis-segment* adaptive and has a ~80–100 day horizon, so it is not an early warning on a trading clock; the metric is one correlation summary and the change-point inference is model-based.

### arXiv 1707.07162v1 — Lagrange regularisation approach to compare nested data sets and determine objectively financial bubbles' inceptions (2017)

- **Question**: how do you choose the calibration window (the bubble's start) without an exogenous judgement?
- **Data/method**: synthetic bubbles with a known transition plus S&P 500, Brazil IBovespa and China SSEC; a Lagrange regularisation of the normalised sum of squared residuals, χ²_λ(Φ), penalising the model's own overfitting tendency, compared with RSS and RSS/(N−p).
- **Headline finding**: χ²_λ(Φ) endogenously selects the optimal fitting-window start w* and recovers the inception of the bubbles ending in 1987 Black Monday and the 2008 sub-prime crisis, and of Chinese bubbles, with no additional information — a problem the paper describes as previously unsolved.
- **Limitation**: demonstrated on one linear-regression-with-change-point toy problem and on bubble fits; the choice of model class still conditions the window, and the method dates an inception rather than predicting a termination.

### arXiv 1804.06261v4 — Dissection of Bitcoin's Multiscale Bubble History from January 2012 to February 2018 (2018)

- **Question**: can a bubble history be built automatically rather than hand-dated?
- **Data/method**: Bitcoin/USD 2012–2018; automatic drawup/drawdown peak detection with the Lagrange Regularisation Method for regime inception, then LPPLS confidence indicators over multiple scales and k-means clustering of the predicted critical times.
- **Headline finding**: the pipeline identifies 3 major and 10 smaller peaks; clusters of predicted critical times are read as plausible scenarios for the subsequent price path across three long and four short bubbles.
- **Limitation**: the analysis is retrospective with fictitious "present" times; the LPPLS scenario clusters give a most-probable termination window rather than a point forecast, and sensitivity to the clustering scale is not fully resolved.

### arXiv 1302.7036v2 — Realizing stock market crashes: stochastic cusp catastrophe model of returns under time-varying volatility (2013)

- **Question**: can catastrophe theory's bifurcations be applied to stock returns once volatility is normalised out?
- **Data/method**: nearly 27 years of U.S. stock market data; a two-step estimator — realized volatility from high-frequency data, then a stochastic cusp catastrophe fitted on volatility-normalised returns — plus a rolling-estimation variant and simulations on the role of noise.
- **Headline finding**: the first half of the sample shows marks of bifurcations, while in the second half the catastrophe model is *unable to confirm* that behaviour — the paper presents this as an important shift in how catastrophe theory may legitimately be applied.
- **Limitation**: the disappearance of bifurcations in the later period is a negative result with no resolved cause; the method relies on high-frequency realized volatility and on the cusp's specific geometry.

### arXiv 1204.3136v3 — Identifying financial crises in real time (2012)

- **Question**: can a thermodynamic multifractal index flag crises early using only past data?
- **Data/method**: daily Dow Jones, DAX, FTSE100, CAC, S&P 500, Nasdaq; a partition-function formulation from a multifractal measure gives an analogous free energy and specific heat, and the area variation rate (AVR) of the specific-heat curve is the index; only past data is used at each point.
- **Headline finding**: AVR flags Black Thursday 1929, Black Monday 1987 and the 2008 sub-prime crisis with clear, robust signatures and has forecasting capability; the 2011 episode reads as a *different kind* of event, below the earlier curves.
- **Limitation**: the parameters (window N, increment T, shift l) are chosen per data type rather than derived; the method distinguishes systemic from external fluctuations but does not explain causes, and the "always below 10⁻³" baseline is asserted without proof.

### arXiv cond-mat/0401210v1 — Origin of Crashes in 3 US stock markets: Shocks and Bubbles (2004)

- **Question**: are large crashes a single phenomenon or two?
- **Data/method**: DJIA, S&P 500 and NASDAQ over the past century; crashes defined objectively as top-rank filtered drawdowns (filter scaled by historical volatility), then classified against shocks and LPPLS bubbles.
- **Headline finding**: all crashes link to either an external shock or an LPPLS bubble with an empirically well-defined complex exponent, and with one exception every previously identified LPPLS bubble is followed by a top-rank drawdown — a near one-to-one correspondence.
- **Limitation**: the classification is a retrospective census; the "one-to-one correspondence" rests on the LPPLS bubble list, and the mechanism (efficient markets on two time scales) is an interpretation rather than a tested model.

### arXiv 2608.12251v1 — Regime-Gated Residual Mixture-of-Experts for Cross-Sectional Volatility Forecasting (2026)

- **Question**: does it matter *where* regime information enters a volatility model?
- **Data/method**: 1,027 U.S. equities 2018–2025 (plus a 1,552-stock Japanese replication); rolling walk-forward, 30 non-overlapping quarterly test windows, ~1.9M out-of-sample forecasts; a capacity-matched comparison where only the integration pathway (input append vs gate) and the routing hardness vary.
- **Headline finding**: appending regime variables to the forecasting input degrades accuracy and destabilises training, while restricting them to a *soft* routing gate improves both accuracy and Value-at-Risk calibration; hard routing consistently underperforms soft routing, and the gains concentrate in elevated-volatility periods.
- **Limitation**: the study is a design comparison on one backbone family and two panels; the regime variables are two volatility indicators, so "regime" here is volatility state, not a full macro regime.

### arXiv 2604.10402v4 — Risk-Sensitive Specialist Routing for Volatility Forecasting (2026)

- **Question**: can online model *routing* adapt to regime changes better than a single winner?
- **Data/method**: a daily six-ETF panel, next-day realized variance proxied by Garman-Klass; a rolling walk-forward with an online scoring rule that penalises relative underprediction (QLIKE + an underprediction term) and weights recent history by regime similarity; calm and stress specialist pools combined by a logistic stress score.
- **Headline finding**: the strongest forecaster is regime-dependent rather than stable; relative to a rolling-best baseline the framework cuts high-volatility forecast loss by ~24% and underprediction loss by ~22%.
- **Limitation**: the specialist pools and the stress-score coefficients are pre-specified and not learned; the design is a six-ETF panel, so the routing thresholds' generality is untested.

### arXiv 1812.02527v1 — Evaluating the Building Blocks of a Dynamically Adaptive Systematic Trading Strategy (2018)

- **Question**: can Wucykoff-style states be identified and used to select a trading style per regime?
- **Data/method**: State-Switching Markov Autoregressive models identify accumulation/distribution/advance/decline regimes; trend-following, range, retracement and breakout strategies are built and assigned per regime, then tied into a dynamic allocation.
- **Headline finding**: regimes are economically meaningful and different strategies are appropriate in different states, supporting a regime-conditional strategy switch rather than one universal alpha.
- **Limitation**: an MSc thesis rather than a peer-reviewed test; the regime-to-strategy mapping is judgemental and the backtests do not control for multiple testing across the strategy/regime grid.

### arXiv 2606.31251v1 — Regime-Conditional Distributional Comparison of Trading Strategies: A GAMLSS/ZAGA Framework (2026)

- **Question**: can strategy comparison report *how* relative performance varies with regime instead of a single full-horizon number?
- **Data/method**: a walk-forward backtest of 146 out-of-sample folds on the S&P 500 (2002–2025); the Adjusted Information Ratio of a polynomial-SVM strategy and buy-and-hold per fold, modelled jointly by a GAMLSS with a Zero-Adjusted Gamma response conditioned on realized volatility and cumulative momentum, with bootstrap tests at six representative regimes.
- **Headline finding**: the dominance relationship between the strategy and buy-and-hold is *conditional on market regime* — a distributional, regime-conditional comparison can reverse the full-horizon verdict.
- **Limitation**: one strategy pair on one index; the regime covariates are just realized volatility and momentum, and the framework is a comparison instrument rather than a trading rule.

## 3. Learnings applicable to this repo

### L1. Un-penalised HMM state paths flip far too often to trade; persistence must be imposed explicitly.

- **Source**: `arXiv 2402.05272v3` (2024) — Downside Risk Reduction Using Regime-Switching Signals: A Statistical Jump Model Approach
- **Finding**: an online two-state Gaussian HMM flips its inferred state 8.5×/year, still ~2×/year after a 20-day median filter, whereas a statistical jump model with a jump penalty λ≈50 flips <1×/year and lifts Sharpe / cuts MDD across S&P 500, DAX and Nikkei 1990–2023 with a one-day delay and 10 bps costs.
- **Repo surface**: `tradingagents/strategies/regime.py::hmm_filtered_regime` (returns per-bar `states` = argmax of the filtered posterior, with no dwell constraint) and `tradingagents/strategies/regime.py::hmm_transition_read` (reports `persistence` / `expected_duration`).
- **Status**: `partial` — verified by reading `regime.py`: `hmm_filtered_regime` emits raw `argmax` states and there is no jump-penalty or minimum-dwell latch anywhere in the module (a grep for `jump_penalty`/`min_dwell`/`median filter` in `regime.py` returns nothing); persistence is only *reported*, never *imposed*.
- **Concrete step**: add an optional, default-off persistence smoother to `hmm_filtered_regime` — a small Viterbi jump penalty over the filtered emission log-densities (or a minimum-dwell latch) — and expose the resulting expected duration in `last`; keep the gate-off output byte-identical.

### L2. Report regime-composition mismatch between train and deployment; it is the dominant OOS failure mode and is not the model's fault.

- **Source**: `arXiv 2606.02657v1` (2026) — Regime-Arrival Uncertainty in Generalization Bounds under Distribution Shift
- **Finding**: the deployment gap factorises exactly as (p₀₁ − π)·(R₁ − R₀); on 25 years and ten global indices an ex-post penalty using the realized future crisis fraction tracks the realized gap at ρ=0.729 [0.635, 0.801], while the training-only estimate fails (ρ≈0.084, CI contains 0) even though regimes are separated at 0.93.
- **Repo surface**: `tradingagents/strategies/regime_performance.py::regime_conditioned_performance`; `tradingagents/strategies/coverage_window.py`; `tradingagents/strategies/evaluate.py::walk_forward_splits`.
- **Status**: `absent` — `regime_conditioned_performance` tabulates per-regime hit/return from scored ledger rows but computes no train-vs-test regime-fraction difference, and `coverage_window.py` labels coverage/survivors rather than regime mixture.
- **Concrete step**: add `regime_mixture_gap(train_rows, test_rows, regime_field="regime")` to `regime_performance.py` returning each split's regime fractions and their absolute difference, printed beside the per-regime table and labelled `diagnostic` (never a forecast — the paper's own training-only estimator fails).

### L3. Learn the number of volatility regimes by clustering change-point segments, rather than assuming a state count.

- **Source**: `arXiv 2004.09963v3` (2020) — Structural clustering of volatility regimes for dynamic trading strategies
- **Finding**: change-point segmentation (Mood test) plus a distance matrix between segment distributions plus spectral clustering (eigengap k-selection) recovers the true segmentation at mean Fowlkes-Mallows 0.93/0.94 on Gaussian/Laplace synthetics and learns five volatility clusters for SPY 2008–2020; the parametric Bartlett test badly over-segments non-normal segments.
- **Repo surface**: `tradingagents/strategies/regime.py::bocpd`, `::cusum`; `tradingagents/strategies/breadth_depth.py::_chow_test`.
- **Status**: `partial` — `bocpd` (with duration-law hazards) and `cusum` detect change points and `_chow_test` tests one break, but nothing clusters the resulting segments by distribution to *learn* the regime count.
- **Concrete step**: add `regime_segment_clusters(series)` that runs `bocpd`, builds a per-segment distribution-distance matrix (KS or Wasserstein over standardized returns), and reports the eigengap-selected cluster count beside the segments; return `unavailable` below a segment/observation floor and mark "a change point is not necessarily a regime change".

### L4. Bubble detection is scale-dependent; LPPLS on daily bars fails on short bubbles, so a detector must run multiple scales and say "not detectable".

- **Source**: `arXiv 1905.09647v2` (2019) — Real-time Prediction of Bitcoin Bubble Crashes
- **Finding**: the LPPLS confidence indicator on daily Bitcoin data fails to warn of short-lived positive bubbles, while an adaptive multilevel detection on 1-hour / 30-minute bars detects them and forecasts the crashes; short-window readings track day-to-week bubble status and long-window readings week-to-month.
- **Repo surface**: `(new module)` — verified by grep: no `lppls` / `log.periodic` symbol exists anywhere in `tradingagents/` or `scripts/`; the module does not exist.
- **Status**: `absent`.
- **Concrete step**: add `tradingagents/strategies/bubble.py::lppls_confidence(bars, scales, ...)` computing the Filimonov-Sornette 3-nonlinear-parameter fit and the LPPLS confidence indicator (fraction of qualified fits) per scale, gated off by default; return a record whose reading is `not detectable` (never `no bubble`) and carry the scale and window in the basis.

### L5. Date a bubble's inception (the calibration-window start) with a regularised fit window instead of an exogenous choice.

- **Source**: `arXiv 1707.07162v1` (2017) — Lagrange regularisation approach to compare nested data sets and determine objectively financial bubbles' inceptions
- **Finding**: a Lagrange-regularised normalised residual sum of squares, χ²_λ(Φ), penalising the model's own overfitting, endogenously selects the optimal fitting-window start w* and recovers the inceptions of the 1987 and 2008 bubbles plus Chinese bubbles, without additional information.
- **Repo surface**: `(new module)`; nearest existing surfaces are `tradingagents/strategies/regime.py::bocpd` (segment starts) and `tradingagents/strategies/long_memory.py::memory_parameter` (windowed fits).
- **Status**: `absent` — no window-selection/regularisation helper exists (verified by reading `long_memory.py` and `regime.py`: window lengths are fixed constants such as `MEMORY_WINDOW` / `min_train`, not selected).
- **Concrete step**: add `fit_window_inception(series, model_fn)` implementing χ²_λ(Φ) and use it to date the start of a BOCPD segment, returning the selected window and the unregularised RSS/(N−p) reference side by side.

### L6. A crash is either endogenous (bubble) or exogenous (shock); a detector must classify, not just alarm.

- **Source**: `arXiv cond-mat/0401210v1` (2004) — Origin of Crashes in 3 US stock markets: Shocks and Bubbles; `arXiv 2101.03625v1` (2021) — The 'COVID' Crash of the 2020 U.S. Stock Market
- **Finding**: all top-rank filtered drawdowns in DJIA/S&P 500/NASDAQ link to either an external shock or an LPPLS bubble, and with one exception every LPPLS bubble is followed by a top-rank drawdown; LPPLS only diagnoses endogenous bubbles, so a crash it misses is likely exogenous — the 2020 crash carried the signature (bubble inception as early as Sep 2018) and is argued to be endogenous rather than COVID-caused.
- **Repo surface**: `tradingagents/strategies/regime.py::regime_gate_read`; `tradingagents/strategies/market_breadth.py::forward_stress_probability`; `tradingagents/strategies/news_score.py` / `event_state.py`.
- **Status**: `absent` — the regime gate returns a tradability label and the forward-stress read returns a calibrated probability, but neither distinguishes an endogenous (drawn-out acceleration) crash from an exogenous (news shock) one.
- **Concrete step**: when a change-point or bubble read fires, cross-check the event/catalyst read and report the episode as `endogenous-candidate` vs `exogenous-candidate` with the evidence named; never return a single undifferentiated "crash detected".

### L7. Heavy-tailed HMM emissions catch moderate crises that a Gaussian HMM misses entirely — make them reachable by default.

- **Source**: `arXiv 2601.10732v1` (2026) — Regime-Dependent Predictive Structure Between Equity Factors; `arXiv 2606.23492v1` (2026) — Continuous HMM ... Heavy-Tail Emission Families and Regime-Conditional VaR
- **Finding**: a Student-t HMM assigns 69.4% of 2011 EU-debt-crisis days to the crisis regime where a Gaussian HMM assigns 0.0%; heavy-tailed marginals close most of the stylized-fact fit gap with no tuning hyperparameter, and a regime-conditional VaR from the filtered posterior passes joint conditional coverage at α=0.05 (DQ p=0.156 at K=3).
- **Repo surface**: `tradingagents/strategies/regime.py::EMISSION_FAMILIES`, `::hmm_filtered_regime(emission=...)`, `::_hmm_heavy_tails_enabled`, `::regime_conditional_var`; `tradingagents/strategies/book_risk.py` (coverage test of the regime VaR).
- **Status**: `partial` — read `regime.py`: the Student-t/Laplace/GED emissions and `regime_conditional_var` are implemented and wired to `book_risk`'s coverage test, but `hmm_filtered_regime`'s default is `emission="gaussian"`, `n_states=3`, and the heavy-tail path is behind `enable_hmm_heavy_tails` (default off), so the default regime read is Gaussian.
- **Concrete step**: report the Gaussian-vs-Student-t crisis-detection delta in the HMM read's `basis`, and run the evidence pack's regime read at `emission="student_t"` so the heavy-tail capability is measured rather than dormant.

### L8. Regime-conditional predictive structure can be statistically significant and economically worthless; expose it as risk monitoring, never as alpha.

- **Source**: `arXiv 2601.10732v1` (2026) — Regime-Dependent Predictive Structure Between Equity Factors
- **Finding**: HML Granger-causes SMB only in crisis regimes (p<1.9e-5, 9-day lag, 5/6 stress events) but the directional strategy loses (−6.1% annual, Sharpe −0.75 vs +1.9% / +0.27 for buy-and-hold); the R² increment from adding HML lags is ~2%.
- **Repo surface**: `tradingagents/strategies/regime_performance.py` (per-regime tabulation); `tradingagents/strategies/statistical.py`.
- **Status**: `absent` — no regime-conditional lead-lag/Granger read exists.
- **Concrete step**: add `regime_conditional_lead_lag(a, b, regime_labels)` to `regime_performance.py` reporting the optimal lag and p-value per regime beside the R² increment, labelled `risk-monitoring` and explicitly not a signal (the paper's own evidence is the reason).

### L9. Regime information should gate or route — not be appended as a forecasting input; soft routing beats hard.

- **Source**: `arXiv 2608.12251v1` (2026) — Regime-Gated Residual Mixture-of-Experts; `arXiv 2604.10402v4` (2026) — Risk-Sensitive Specialist Routing for Volatility Forecasting
- **Finding**: appending the same regime variables to the forecasting input degrades accuracy and destabilises training, while restricting them to a soft routing gate improves accuracy and VaR calibration; hard routing underperforms soft; risk-sensitive routing (underprediction-penalised) cuts high-volatility loss ~24% and underprediction loss ~22% versus a rolling-best baseline, and the best forecaster is regime-dependent.
- **Repo surface**: `tradingagents/strategies/regime_state.py::regime_factor` (multiplicative gate on position size); `tradingagents/strategies/regime_score.py::regime_score`; `tradingagents/strategies/regime_performance.py::regime_conditioned_performance`.
- **Status**: `partial` — the repo already gates exposure by regime (consistent with the paper's principle), but it has no per-regime *routing* of candidate signals/models and no risk-sensitive (underprediction/downside) scoring of that routing.
- **Concrete step**: add a `best_signal_per_regime(candidates, regime_labels)` read to `regime_performance.py` that ranks candidates by a downside-penalised loss within each regime and returns an advisory routing table with the routing set reported.

### L10. Regime-switching volatility forecasts pay off mainly in the high-volatility state and need regime-aware features.

- **Source**: `arXiv 2510.03236v1` (2025) — Improving S&P 500 Volatility Forecasting through Regime-Switching Methods
- **Finding**: over 11 years of 5-minute SPX realized volatility, a coefficient-based soft-regime algorithm (Mood-test segmentation, Bayesian-GMM soft weights, XGBoost regime probabilities) beats the baseline in every period including COVID, with the gains concentrated where uncertainty is highest; soft clustering beats hard assignment.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast`; `tradingagents/strategies/volatility_models.py` (estimators/GARCH); `tradingagents/strategies/regime.py::realized_vol`.
- **Status**: `partial` — a HAR-family RV forecast and a full volatility estimator suite exist, but the RV forecast takes no regime weighting (read `long_memory.py`: `rv_forecast` has no regime input).
- **Concrete step**: give `rv_forecast` an optional `regime_posterior` argument that blends the forecast branches by the filtered posterior, and report the weights and the high-volatility leg's contribution in the record.

### L11. Crash/bifurcation signatures are period-specific; a detector must report historical detection rates, not assert a universal law.

- **Source**: `arXiv 1302.7036v2` (2013) — Realizing stock market crashes: stochastic cusp catastrophe; `arXiv 1204.3136v3` (2012) — Identifying financial crises in real time
- **Finding**: the stochastic cusp catastrophe on volatility-normalised US returns (27 years) confirms bifurcations only in the *first* half of the sample and cannot confirm them in the second; the thermodynamic multifractal area-variation-rate index flags 1929/1987/2008 but reads 2011 as a different kind of event — crash signatures do not hold uniformly across eras.
- **Repo surface**: `tradingagents/strategies/regime.py` (rule/threshold regime and crash reads); `tradingagents/strategies/mean_reversion.py::hurst_exponent`.
- **Status**: `absent`/`partial` — no cusp or multifractal crash detector exists; the repo's crash notion is threshold-based (`regime_state.DD_SEVERE`, vol-percentile bands).
- **Concrete step**: if a crash-model read is added, require it to also report its in-sample detection rate over the episodes it claims (via `regime_performance.regime_conditioned_performance`) and withhold a universal claim when the rate is not measured across periods.

### L12. Regime-state estimates carry uncertainty and identifiability limits that must travel with the number.

- **Source**: `arXiv 2605.14976v3` (2026) — Multi-regime Markov-switching models with time-varying transition probabilities
- **Finding**: regime means/variances and transition probabilities are well recovered, but the GAS score coefficient is statistically non-identifiable (a ridge in the joint (σ², A) likelihood); on real Treasury data 99/100 starts failed to converge with the coefficient collapsing to zero; TVTP transition-probability coverage is systematically below nominal 95%, worst at K=3; the one-step conditional mean is insensitive to transition misspecification.
- **Repo surface**: `tradingagents/strategies/regime.py::hmm_transition_read`, `::hmm_filtered_regime` (the `selection` block carries BIC beside a caller-supplied K); `tradingagents/strategies/regime_score.py::regime_state_metadata`.
- **Status**: `partial` — read `regime.py`: `hmm_transition_read` reports `persistence`/`expected_duration` as point estimates and `hmm_filtered_regime` reports BIC/loglik, but neither emits a transition-probability uncertainty band nor flags a near-ridge/collapsed fit.
- **Concrete step**: have `hmm_transition_read` return the transition rows with a dispersion field (profile/bootstrap) and mark a fit whose off-diagonal dynamic is collapsed or near a likelihood ridge as `unidentified` rather than reporting a point estimate.

## 4. Where this repo is already ahead of the literature

- **Filtered-not-smoothed HMM state estimates are a construction invariant.** `regime.py::_hmm_filter_step` documents that it runs the forward recursion only ("NOT `predict_proba`, which runs the backward pass too and so conditions on observations after `t`"), parameters are refit on strictly-past prefixes, and states are canonicalised by mean return at every refit (`_hmm_canonical`). The literature's central filtered-vs-smoothed warning (`0904.1500v1`, `2402.05272v3`) is already enforced in code.
- **Heavy-tailed emissions under one shared forward-backward kernel, with a regime-conditional VaR.** `regime.py::hmm_filtered_regime` supports `gaussian`/`student_t`/`laplace`/`ged` through `EMISSION_FAMILIES`, and `regime.py::regime_conditional_var` builds the mixture quantile from the filtered posterior and feeds `book_risk`'s coverage test — the exact construction `2606.23492v1` recommends.
- **Bayesian online change-point detection with explicit duration-law hazards.** `regime.py::bocpd` implements Adams-MacKay BOCPD with a conjugate NIG prior, an internal causal standardization, selectable `constant`/`lognormal`/`pareto`/`geometric` run-length hazards, and a length-weighted `covering` metric against the constant-hazard reference.
- **A calibrated null band before declaring a cross-sectional structural change.** `regime.py::spectral_change_read` + `covariance_models.py` (`spectral_null_band`, `panel_spectrum`, `eigen_projector_distance`) declare a regime change only when a spectral move exceeds a calibrated first-order null band, and a non-rejection reads "not detectable", never "no change" — matching `2607.06373`'s finding.
- **Classical change-point tooling is present.** `regime.py::cusum` (tabular CUSUM) and `::ewma_control` (EWMA chart), and `breadth_depth.py::_chow_test` (Chow break F-statistic), cover the offline/online change-detection core of `2004.09963v3` and `2308.00087v1`.
- **Calibrated probability reads travel with their caveat.** `market_breadth.py::forward_stress_probability` is in-sample calibrated, states its horizon, and is printed beside `regime_score` rather than scored — the honest-reporting shape the regime literature (e.g. `2308.00087v1`) demands of an online detector.

## 5. Defects or risks the literature exposes

1. **Dangling benchmark reference `regime.sticky_markov` — fixed 2026-10-04 (D5, design §12.3).** `tradingagents/strategies/forecast_registry.py:195` and `:196` declare `("regime.sticky_markov",)` as the benchmark tuple for the `regime_probability` / `regime_stress_probability` keys, and `:269` sets `benchmark_ref="regime.sticky_markov"`. A repo-wide grep for `sticky_markov` returned exactly those three lines; no `def sticky_markov` existed anywhere. The persistence/benchmarking literature (`arXiv 2402.05272v3`, which benchmarks HMM vs jump-model persistence) makes this a real gap: the FL-2 registry asserts an authoritative producer/benchmark per forecast key, and this benchmark could not be evaluated. **Now it can**: `strategies/regime.py::sticky_markov` implements the two-state persistence estimator (transition counts, `p_stay`, stationary law, and an explicit `unavailable` for an absorbing chain), `forecast_registry.BENCHMARK_IMPLEMENTATIONS` binds the ref to it, `tests/test_forecast_registry.py` resolves the binding against the live tree, and `scripts/forecast_ledger.py` refuses to score a bound ref that does not resolve.
2. **The default regime read is Gaussian, which the literature shows can miss moderate crises entirely.** `tradingagents/strategies/regime.py::hmm_filtered_regime` defaults to `emission="gaussian"` and `n_states=3`, and `_hmm_heavy_tails_enabled` gates the Student-t/Laplace/GED path off by default. `arXiv 2601.10732v1` measures a Gaussian HMM at 0.0% crisis-day classification of the 2011 EU-debt crisis versus 69.4% for a Student-t HMM; `arXiv 2606.23492v1` shows heavy-tailed marginals are what close the stylized-fact gap. A moderate-stress episode can therefore be invisible in the engine's default regime label.
3. **`bocpd`'s shift flag does not invalidate straddling-window statistics.** `tradingagents/strategies/regime.py:1353-1356` states that a `True` shift "invalidates window-based statistics for the NEXT read: Hurst, variance-ratio and half-life are estimated on a window that straddles the break", and explicitly notes "this function does not touch them" — no code enforces the recomputation. `arXiv 2004.09963v3` requires statistics to be read on locally stationary segments and `arXiv 2308.00087v1` treats a change point as a state reset. As written, `mean_reversion.hurst_exponent` / `variance_ratio` and `long_memory.memory_parameter` can be computed across a detected break and reported as a stable regime property.
4. **`cusum` calibrates its baseline from the first observations of the series, not a leading window.** `tradingagents/strategies/regime.py::cusum` (lines ~1031-1033) sets `base = vals[:cal]` and `mu0 = mean(base)` with `cal ≈ 30`; on a long series the control-chart mean is anchored to the series start, so a persistent level drift will push the cumulative sum past `h` and leave it signalled. The change-point literature (`arXiv 2004.09963v3`; `arXiv 2308.00087v1`) reads shifts against locally stationary segments / an online-adaptive baseline rather than a fixed early baseline.

## 6. Limits of this review

I read the abstract, introduction, method and the results/limitation sections of the 20 papers listed in §2 (a handful, e.g. `1302.7036v2`, `1204.3136v3`, `cond-mat/0401210v1`, were read at abstract/introduction level with the result tables from the body, and are marked by their bullet content). The remaining high-relevance rows (`2608.23808v2`, `2605.24285v1`, `2601.07687v4`, `2608.20020v1`, `2309.00025v1`, `2304.09947v2`, `2304.14098v2`, `2307.00459v1`, `2304.09937v1`, `2401.03393v2`, `2401.03443v1`, `2307.03693v1`, `2209.05559v6`, `2104.03667v1`, `1811.11618v2`, `1302.1405v2`, `1201.3572v2`, `1208.4831v2`, `1112.3095v3`, `1102.4819v2`, `1009.2928v1`, `2004.09963v3`'s neighbours, `0904.1500v1`'s companions) were only skimmed from the abstract-level evidence pack, and medium/background rows were not sampled beyond the pack. Repo-symbol claims were verified by reading the module source (`regime.py`, `regime_state.py`, `regime_score.py`, `regime_performance.py`, `market_breadth.py`, `breadth_depth.py`, `statistical_kalman.py`, `volatility_models.py`, `long_memory.py`, `mean_reversion.py`, `covariance_models.py`, `evaluate.py`, `tail_risk.py`) and by repo-wide greps for `lppls`/`log.periodic`, `hurst`, `hawkes`, `jump_model`, `Page-Hinkley`, `sticky_markov`. I did not run any test, linter, formatter or git command, and I did not verify runtime behaviour — a "shipped" or "partial" status means the symbol exists and its docstring/code shows the described capability, not that its output was executed. The category has 663 papers and this review covers the 39 high-relevance rows plus the top-60 booklist; the medium band (409 papers) is represented only through the evidence pack's summaries.
