# Volatility & Realized Variance

`book 10/19` · slug `volatility` · 1079 papers in the corpus · 144 rated high-relevance by the sweep

## 0. Scope

This category covers the measurement and forecasting of financial variance: OHLC range
estimators (Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang), high-frequency realized
variance and its noise/jump-robust corrections (bipower, two-scale, subsampled, kernel),
HAR and its extensions, fractional long-memory (ARFIMA/FIGARCH) and rough-volatility
models, the multivariate covariance/DCC family, volatility-of-volatility, and the loss
functions and tests used to compare forecasts. It matters more to this repo than any other
category: the engine already ships four OHLC estimators, a GARCH(1,1) fit, a bipower/quarticity
jump proxy, a HAR-family forecast, and two long-memory estimators, and it owns a frozen
forecasting-layer design (`docs/design_forecasting_libraries.md`) whose declared target is
realized volatility. Almost every paper here bears directly on those modules.

## 1. Corpus composition

The sweep tagged **1079** papers for this category (144 high, 741 medium, 194 low).
The 60-paper booklist — the top-60 by relevance score — is what I sampled and read. Its
composition:

| decade | booklist papers |
| --- | --- |
| 2020–2026 | 45 |
| 2010–2019 | 13 |
| 2000–2009 | 2 |

| primary arXiv category | booklist papers |
| --- | --- |
| q-fin.ST (statistical finance) | 44 |
| math.ST | 3 |
| econ.EM | 2 |
| stat.AP | 2 |
| q-fin.{TR,PR,RM,CP,MF}, econ.GN, stat.ME, cs.LG, physics.soc-ph | 1 each |

Counts used: `total_in_book = 1079`, high = 144 (evidence pack header); decade/category
counts from `booklists/volatility.json` (60 rows). The category is dominated by
`q-fin.ST` applied econometrics: GARCH-family and HAR-family forecasting on equity and
crypto series, with a heavy 2020s tail of ML/NN volatility forecasters. The genuinely
methodological core — roughness estimators, realized-measure theory, forecast-evaluation
losses — is a small minority and is where the deep reads concentrate.

## 2. Deep reads

### arXiv 1410.3394v1 — "Volatility is rough" (Gatheral, Jaisson, Rosenbaum, 2014)
- **Question**: is the log-volatility process smoother or rougher than Brownian motion, and
  what does that imply for forecasting?
- **Data/market**: DAX and Bund futures (1248 days, 2010–2014, integrated-variance proxies
  from a model with uncertainty zones) and S&P 500 / NASDAQ daily realized variance from the
  Oxford-Man Realized Library (3540 days, 2000–2014).
- **Method**: regress the empirical q-th moment of log-volatility increments on the lag,
  `m(q,Δ) ∝ Δ^{qH}`, then regress the per-q slopes ζ_q on q to read off H.
- **Finding**: H lies between **0.08 and 0.2** for every asset, i.e. log-volatility behaves
  like fractional Brownian motion with H ≈ 0.1; the Rough Fractional Stochastic Volatility
  model matches the data and its volatility forecasts **outperform conventional AR and HAR**.
- **Limitation**: the paper itself states only that it "cannot find evidence against" RFSV;
  H ≈ 0.1 is offered as a consistent model, not a statistical estimate. Classical persistence
  tests applied to RFSV-simulated data still conclude "long memory", so the long-memory
  stylized fact is not resolved.

### arXiv 2203.13820v3 — "Rough volatility: fact or artefact?" (Cont & Das, 2022/2023)
- **Question**: is measured roughness of realized volatility a property of spot volatility,
  or of the estimator?
- **Data/market**: synthetic fBm/fractional-process paths and simulated stochastic-volatility
  models, then AAPL and S&P 500 high-frequency data.
- **Method**: a model-free roughness index from **normalized p-th variation** along a sequence
  of partitions (a pathwise H estimate needing no model).
- **Finding**: **realized volatility always exhibits H significantly below 0.5 even when the
  spot volatility is Brownian**; the apparent roughness originates in the estimation error of
  the volatility proxy, not the latent process.
- **Limitation**: the method measures roughness only, not dependence; it cannot itself supply a
  volatility model, and it does not settle whether *spot* volatility is rough — only that the
  realized proxy cannot establish it.

### arXiv 1905.04852v2 — "Is Volatility Rough?" (Fukasawa, Takabatake, Westphal, 2019)
- **Question**: can H be estimated consistently when the volatility is latent?
- **Data/market**: simulations plus SPX 5-minute realized volatility (Oxford-Man, 2000–2018).
- **Method**: a quasi-likelihood/Whittle estimator of (H,η) under a continuous-time fractional
  SV model, using the error distribution of realized variance and a Whittle approximation to
  the log-vol autocovariance; consistency proven under high-frequency asymptotics.
- **Finding**: the Gatheral log-log regression **gives H ≈ 0.1 almost regardless of the true H**
  used to simulate the data (regression coefficient 0.1258 on SPX), because the realized-variance
  estimation error manufactures the scaling; the quasi-likelihood estimate nevertheless
  concludes the empirical volatility **is** rough.
- **Limitation**: consistency is asymptotic and model-based; the estimator assumes a fractional
  specification, so it cannot itself falsify the roughness class.

### arXiv 2312.01426v2 — "Rough volatility: evidence from range volatility estimators" (Mouti, 2023)
- **Question**: does the rough-volatility finding survive when H is estimated from range
  (OHLC) proxies rather than high-frequency realized volatility?
- **Data/market**: a broad cross-section including non-standard assets; daily OHLC, Garman-Klass
  proxy.
- **Method**: replicate the Gatheral scaling regressions on log range-based volatility.
- **Finding**: H from range proxies is **below 0.1**, often near 0 — even rougher than the
  realized-volatility estimates — and RFSV forecasts **beat AR, HAR and GARCH in most
  scenarios**; the author reads this as evidence that rough volatility is intrinsic and not a
  microstructure-noise artifact.
- **Limitation**: it is a scaling-regression study, exposed to exactly the critique in
  Fukasawa et al. and Cont & Das; the "not an artifact" claim rests on the range estimator
  being noise-robust, which is asserted rather than stress-tested per asset.

### arXiv 2605.24285v1 — "Memory, Roughness, and Information Persistence in Financial Markets" (Deep, Appiah, Rachev, 2026)
- **Question**: do long-memory and roughness measures carry forecasting information beyond
  standard HAR/HAR-X predictors?
- **Data/market**: 115 S&P 500 constituents, 6136 trading days (Nov 2001–Apr 2026), plus a
  5-minute subsample; Bloomberg daily OHLC.
- **Method**: rolling GPH and local-Whittle memory estimates and rolling Hurst exponents;
  layered forecast design (HAR, HAR-X, persistence-augmented regressions, shrinkage, trees)
  with QLIKE loss, Diebold-Mariano with Harvey-Little-Neumann correction, Newey-West HAC, and
  panel-aware cross-sectional aggregation.
- **Finding**: cross-sectional mean **GPH d = 0.226** but **local-Whittle d = 0.440** (the two
  estimators disagree by a factor of two); persistence rises sharply in the GFC and COVID and
  co-moves with the VIX; persistence features add significant forecast gains, concentrated at
  **longer horizons and in stress regimes**, and **cross-sectional/sectoral aggregates and
  interactions — not own-stock persistence — drive the gains**; linear persistence-augmented
  models beat the tree-based ones.
- **Limitation**: no structural identification; the authors state the memory parameter is a
  reduced-form summary that may reflect breaks or regime shifts rather than true fractional
  integration.

### arXiv 2406.08041v1 — "HARd to Beat: The Overlooked Impact of Rolling Windows in the Era of Machine Learning" (Audrino & Chassot, 2024)
- **Question**: can ML beat HAR once HAR's fitting scheme is tuned?
- **Data/market**: 1445 CRSP/NYSE stocks, TAQ high-frequency 2015–2023, test Jan 2022–Nov 2023;
  5-minute log realized variance, plus VIX.
- **Method**: sweep HAR training window and re-estimation stride; compare OLS/WLS pooled and
  per-stock HAR against lasso, random forest, GBT and feed-forward NN, scored by MSE, QLIKE
  and realized utility.
- **Finding**: the optimal scheme is a **rolling window of roughly 630 days re-estimated daily**;
  even then a poorly re-estimated HAR looks bad, and once HAR is properly fitted ML **fails to
  beat it** on every metric (WLS-HAR lowest MSE and QLIKE; FFNN far behind); HAR is orders of
  magnitude cheaper.
- **Limitation**: information set deliberately restricted to RV+VIX, so it is silent on whether
  ML wins with richer features; jump/microstructure handling is left to the RV estimator.

### arXiv 2603.02898v1 — "Range-Based Volatility Estimators for Monitoring Market Stress" (Andrée, World Bank, 2026)
- **Question**: do OHLC range estimators transfer to thinly traded local commodity markets?
- **Data/market**: World Bank Real-Time Prices monthly food prices across conflict-affected,
  climate-exposed and remote markets.
- **Method**: construct Parkinson, Garman-Klass, Rogers-Satchell and Yang-Zhang series and
  score them against independently documented disruption timelines.
- **Finding**: elevated range volatility aligns with documented disruptions and **detects
  symmetric or rapidly reversing stress that RSI misses**; the four estimators are treated as
  complementary composites rather than one winner.
- **Limitation**: monthly, non-financial, low-frequency data; no forecast evaluation, so it
  evidences *measurement* value, not forecast skill.

### arXiv 2309.17219v1 — "Covariance Matrix Filtering and Portfolio Optimisation: The Average Oracle vs Non-Linear Shrinkage and all the variants of DCC-NLS" (Bongiorno & Challet, 2023)
- **Question**: does the complex DCC + non-linear-shrinkage state of the art beat a simple
  covariance filter out of sample?
- **Data/market**: random samples of 100 from the top-500 US stocks by cap, 2000–2021, 10,000
  simulations, 5 bps costs.
- **Method**: compare sample covariance, Ledoit-Wolf NLS/QIS (short and long windows), their
  DCC variants, factor-augmented DCC, and the Average Oracle; score Sharpe, realized volatility,
  turnover, gross leverage and concentration.
- **Finding**: some DCC+NLS variants achieve marginally lower realized volatility, but the
  Average Oracle delivers **14–37% higher Sharpe**, with **10–19× lower turnover**, ~45% less
  gross leverage and roughly twice the diversification; DCC's rapid, concentrated, unstable
  weights are the mechanism.
- **Limitation**: single market (US equities) and long-only-ish long-short construction; the
  Average Oracle eigenvalues are calibrated on an outdated 1900–2000 dataset.

### arXiv 2006.03458v1 — "Doubly Multiplicative Error Models with Long- and Short-run Components" (Amendola, Candila, Cipollini, Gallo, 2020)
- **Question**: does splitting realized volatility into a slow long-run level and a fast
  short-run component beat HAR and GARCH-type models?
- **Data/market**: realized volatility of S&P 500, NASDAQ, FTSE 100 and Hang Seng.
- **Method**: Component MEM (both components daily) and MEM-MIDAS (low-frequency long-run
  component via mixed-data sampling); ML and GMM estimators.
- **Finding**: **both DMEM variants outperform HAR and the relevant GARCH-type models on every
  index**; models without a long-run component are dominated within both the RV and the
  conditional-variance classes; realized measures outperform return-based GARCH even when the
  latter carry a long-run component.
- **Limitation**: four indices, no panel/cross-sectional dimension; MIDAS requires a
  macro/low-frequency driver, which limits applicability to a purely price-driven engine.

### arXiv 1204.1452v4 — "Modeling and forecasting exchange rate volatility in time-frequency domain" (Baruník, Krehlík, Vácha, 2012)
- **Question**: does decomposing realized volatility into investment-horizon bands, and
  separating jumps from the continuous part, improve volatility forecasts?
- **Data/market**: FX futures (intraday) covering the financial crisis.
- **Method**: Realized GARCH driven by multiple time-frequency (wavelet) decomposed realized
  measures, with a **jump wavelet two-scale realized volatility** estimator separating jump
  variation from integrated variation; MLE and GAS estimation.
- **Finding**: **disentangling jump variation from integrated variation matters** for forecast
  performance; most predictive information comes from the highest-frequency spectral band
  (very short investment horizons); the proposed models beat conventional ones at one-day and
  multi-period horizons.
- **Limitation**: FX futures only; wavelet-band choice is a tuning artifact the paper does not
  fully robustify.

### arXiv 2602.19732v1 — "VOLatility Archive for Realized Estimates (VOLARE)" (Cipollini, Cruciani, Gallo, Insana, Otranto, Spagnolo, 2026)
- **Question**: can a single open infrastructure standardize high-frequency realized measures
  across asset classes for reproducible comparison?
- **Data/market**: tick data for US equities, FX pairs and futures from Kibot.
- **Method**: compute a uniform suite — realized variance, bipower variation, positive/negative
  realized semivariance, realized quarticity, kernels — at multiple sampling frequencies, with
  interactive HAR and MEM estimation.
- **Finding**: a standardized, cross-asset realized-measure archive with **consistent
  methodology** lets cross-asset model rankings reflect forecasting skill rather than
  measurement inconsistency; this is the dataset the foundation-model comparison below uses.
- **Limitation**: it is an archive/infrastructure paper; it prescribes no estimator and carries
  no forecast result of its own.

### arXiv 2607.05291v1 — "Forecasting Realized Volatility with Time Series Foundation Models" (Brini, 2026)
- **Question**: do zero-shot pretrained time-series foundation models beat econometric
  volatility benchmarks?
- **Data/market**: VOLARE, 50 assets (40 equities, 5 FX, 5 futures), horizons 1/5/22 days.
- **Method**: nine foundation models (eight architectures) against eight econometric specs
  (Log-HAR, HAR, ARFIMA, ARMA, MEM, jump- and quarticity-augmented HAR), with Diebold-Mariano,
  Model Confidence Set, Mincer-Zarnowitz recalibration and Giacomini-Rossi fluctuation tests.
- **Finding**: pooled QLIKE favors foundations but is outlier-driven; under per-asset average
  loss ratios only **Tiny Time Mixers (<1M parameters) beats Log-HAR at every horizon, by
  ~1.3–1.8%**, and an MZ recalibration shows the daily-horizon edge is largely a scaling
  artifact — a genuine informational gain remains only at the monthly horizon. An
  **equal-weight TTM + Log-HAR average enters the MCS for 98–100% of assets**, and Log-HAR
  and the HAR/ARFIMA/MEM family are never displaced.
- **Limitation**: zero-shot only; VOLARE's equity panel is survivor-balanced; monthly-horizon
  gains are thin.

### arXiv 2305.04137v2 — "Volatility of Volatility and Leverage Effect from Options" (Chong & Todorov, 2023)
- **Question**: can vol-of-vol and the leverage effect be estimated model-free from options?
- **Data/market**: high-frequency short-dated options.
- **Method**: integrate available options into the conditional characteristic function of the
  price increment to recover spot volatility; form the vol-of-vol estimator from the **sample
  variance of spot-volatility increments plus a first-order autocovariance correction** for
  option observation error; leverage as the covariance of price and volatility increments.
- **Finding**: the estimators are consistent and the autocovariance term **removes the bias
  from option observation error**; vol-of-vol emerges as a risk factor only weakly correlated
  with volatility itself.
- **Limitation**: the convergence rate depends on whether latent-volatility diffusion or
  option-observation error dominates, and the method needs dense short-dated option chains —
  unavailable to a daily-equity engine.

### arXiv 2604.01431v1 — "Do Prediction Markets Forecast Cryptocurrency Volatility? Evidence from Kalshi Macro Contracts" (Mohanty & Krishnamachari, 2026)
- **Question**: do daily probability changes in macro event markets forecast crypto realized
  volatility?
- **Data/market**: Kalshi contracts (Fed, CPI, GDP, recession) and six crypto assets,
  Jan 2023–Mar 2026.
- **Method**: HAR-augmented regressions of realized volatility on orthogonalized prediction-market
  repricing; Clark-West MSFE tests, Benjamini-Hochberg correction.
- **Finding**: Fed-rate repricing predicts Bitcoin in-sample (**t = 3.63**); the recession-risk
  signal is the most stable out of sample (**MSFE ratio 0.979, Clark-West p = 0.020**); CPI
  repricing predicts altcoins; the signals survive orthogonalization against Fed-funds futures,
  Treasury yields and the Deribit IV index.
- **Limitation**: short sample, few assets, and the monetary-policy channel is regime-dependent
  on the 2024–2025 rate-cutting cycle.

### arXiv 2508.15922v1 — "Probabilistic Forecasting Cryptocurrencies Volatility: From Point to Quantile Forecasts" (Dudek, Orzeszko, Fiszeder, 2025)
- **Question**: how should point volatility forecasts be turned into conditional quantiles?
- **Data/market**: cryptocurrency realized variance.
- **Method**: feed point forecasts from HAR, GARCH, ARFIMA and ML (LASSO, SVR, MLP, RF, LSTM)
  into quantile estimation by **residual simulation (QRS)**; compare against direct quantile ML.
- **Finding**: QRS applied to the **log realized volatility of the linear models wins** — the
  best probabilistic forecast is a simple point model with a well-calibrated residual
  distribution, not a direct quantile learner.
- **Limitation**: crypto-only, extreme-volatility regime; QRS inherits the point model's bias.

### arXiv 2407.10659v1 — "A nonparametric test for rough volatility" (Chong & Todorov, 2024)
- **Question**: can one *test* rough vs semimartingale volatility rather than assume a
  fractional model?
- **Data/market**: simulated paths and SPY high-frequency data.
- **Method**: volatility is rough iff its increments are negatively autocorrelated at high
  frequencies; the test is the sample autocovariance of spot-volatility increments, with a
  feasible CLT under the semimartingale null; robust to jumps of arbitrary activity and to
  microstructure noise.
- **Finding**: fixed asymptotic size and asymptotic power one; **SPY data rejects the
  semimartingale null in favor of rough volatility**.
- **Limitation**: relies on spot-volatility estimation; it is a test of roughness only and does
  not deliver a forecasting model.

### arXiv 0912.1617v1 / arXiv 0908.1677v1 — "Homogeneous Volatility Bridge Estimators" / "Most Efficient Homogeneous Volatility Estimators" (Saichev, Sornette, Filimonov, Corsi)
- **Question**: which OHLC combination extracts the most information about variance?
- **Data/market**: Wiener-with-drift log-price processes; synthetic tick series.
- **Method**: derive the exact joint distribution of high-minus-open, low-minus-open and
  close-minus-open for a Wiener bridge, then construct the minimum-variance homogeneous
  estimator.
- **Finding**: the bridge construction (treating the intraday path as pinned at open and close)
  is **significantly more efficient than the Garman-Klass and Parkinson estimators**, because a
  Wiener's high/low sit near the interval edges while a bridge's sit away from them.
- **Limitation**: the optimality is exact only under the Wiener/drift assumptions; Garman-Klass
  assumes zero drift and Parkinson discards open/close information.

## 3. Learnings applicable to this repo

### L1. Roughness must be estimated on log realized volatility, not on returns
- **Source**: `arXiv 2203.13820` (2022) — Rough volatility: fact or artefact? (and `arXiv 1905.04852`, 2019)
- **Finding**: realized volatility exhibits H < 0.5 even when the spot volatility is Brownian
  (Cont & Das), and the standard log-log scaling regression returns H ≈ 0.1 regardless of the
  truth (Fukasawa et al.). Roughness is a property of the log-volatility path, and naive
  estimators of it are biased by proxy estimation error.
- **Repo surface**: `tradingagents/strategies/mean_reversion.py::hurst_exponent` — R/S analysis
  run on the *return* series; `memory_profile` presents it as `roughness_h`, the "roughness leg".
- **Status**: `partial` — the estimator exists but measures return mean-reversion, not
  log-volatility roughness; the label `roughness_h` overstates what it is.
- **Concrete step**: add a `realized_roughness_h` computed by `hurst_exponent` over a log
  range-volatility series (from `volatility_models.parkinson_vol` / `yang_zhang_vol_series`),
  and relabel the existing return-series value as a mean-reversion exponent.

### L2. The HAR target and regressand should be log realized volatility
- **Source**: `arXiv 2406.08041` (2024) — HARd to Beat
- **Finding**: the logarithmic RV estimator "is well-known to outperform its standard
  counterpart"; the paper's HAR is defined on log-RV, and this is also the target in the
  foundation-model benchmark (`arXiv 2607.05291`, which fits "Log-HAR").
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast` — fits
  `RV_{t+1} = b0 + b_d RV_t + b_w RV_w + b_m RV_m` in RV levels, with the proxy
  `RV = returns ** 2`.
- **Status**: `partial` — a HAR fits, but on levels and with a squared-daily-return proxy.
- **Concrete step**: add a `log_rv` mode to `rv_forecast` that fits `log RV_{t+1}` on the
  trailing log-RV means, keeping the current level fit as a named alternative so the two are
  never conflated.

### L3. The HAR fitting scheme (rolling window and re-estimation stride) is first-order
- **Source**: `arXiv 2406.08041` (2024) — HARd to Beat
- **Finding**: across 1445 stocks the optimal scheme is a rolling window of roughly **630
  days, re-estimated daily**; larger windows lower error, and failing to re-estimate daily
  degrades HAR badly enough to make ML look superior.
- **Repo surface**: `tradingagents/strategies/long_memory.py::rv_forecast` and its default
  `window = MEMORY_WINDOW` (`MEMORY_WINDOW = 750`).
- **Status**: `partial` — one window constant is reused for the memory fit and the HAR fit,
  and the HAR re-estimation cadence is not declared.
- **Concrete step**: introduce a separate `HAR_WINDOW` (default ~630) and document that
  `rv_forecast` is meant to be re-run on the latest bar each day.

### L4. Forecast comparison needs Diebold-Mariano and Mincer-Zarnowitz, not a raw loss delta
- **Source**: `arXiv 2607.05291` (2026) — foundation models vs benchmarks; `arXiv 2605.24285` (2026)
- **Finding**: both papers refuse to rank models on loss alone: they apply Diebold-Mariano
  (HLN-corrected, HAC variance) and Model Confidence Sets, and Mincer-Zarnowitz regressions
  to separate a *calibration* edge from an *informational* edge — the TSFM daily-horizon
  "win" vanished under MZ recalibration.
- **Repo surface**: `tradingagents/strategies/prediction_ledger.py` (`benchmark_delta`,
  lines 291-293) and `forecast_contract.py::SCORING_RULES` (`("CRPS","QLIKE","RMSE","MAE")`).
- **Status**: `partial` — QLIKE is a declared scoring rule, but no significance test or MZ
  regression is implemented anywhere in the repo (the only `Diebold-Mariano` occurrence is a
  prose caveat in `options_surface.py:246`, and there is no Mincer-Zarnowitz code).
- **Concrete step**: add a `forecast_comparison` helper with an HLN-corrected Diebold-Mariano
  statistic and an MZ regression, and record both on `ForecastEvaluation`.

### L5. Volatility-of-volatility is a distinct risk factor estimable model-free
- **Source**: `arXiv 2305.04137` (2023) — Volatility of Volatility and Leverage Effect from Options
- **Finding**: vol-of-vol can be recovered from the sample variance plus first-order
  autocovariance of spot-volatility increments; the autocovariance term removes observation-error
  bias, and the resulting factor is only weakly correlated with volatility itself.
- **Repo surface**: `tradingagents/strategies/options_surface.py` (new function) and
  `tradingagents/strategies/tail_risk.py`.
- **Status**: `absent` — the repo measures implied-vol level, rank, skew and expected move,
  but no vol-of-vol.
- **Concrete step**: add a `vol_of_vol` read over an implied-volatility series using the
  variance-minus-autocovariance correction, gated like the other optional reads.

### L6. Prefer shrinkage to DCC; complex covariance filters buy turnover and leverage, not Sharpe
- **Source**: `arXiv 2309.17219` (2023) — The Average Oracle vs DCC-NLS
- **Finding**: DCC+NLS variants at best match a simple filter's realized volatility but lose
  14–37% of Sharpe through 10–19× turnover, ~45% higher gross leverage and half the
  diversification.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink` (line 85)
  and `ewma_covariance` (line 132).
- **Status**: `shipped` — the repo already uses Ledoit-Wolf shrinkage plus an EWMA covariance
  and has no DCC; the learning is a justification to keep it that way.
- **Concrete step**: when covariance-based weights are produced (`portfolio_optimizer.py`),
  report turnover, gross leverage and a concentration measure beside the weights, so a
  complex estimator cannot be adopted on volatility alone.

### L7. A long-run / short-run component split beats plain HAR
- **Source**: `arXiv 2006.03458` (2020) — Doubly Multiplicative Error Models
- **Finding**: Component MEM and MEM-MIDAS — a slow long-run level times a fast short-run
  component — outperform HAR and GARCH-type models on S&P 500, NASDAQ, FTSE 100 and Hang Seng;
  models without the long-run component are dominated.
- **Repo surface**: `tradingagents/strategies/long_memory.py` (new model).
- **Status**: `absent` — `rv_forecast` is a single-regime HAR.
- **Concrete step**: add a component-MEM RV forecast (or at minimum a long-run level term) as
  a candidate producer alongside the HAR, leaving HAR as the benchmark.

### L8. Separate jumps from the continuous variation; the high-frequency band carries the signal
- **Source**: `arXiv 1204.1452` (2012) — Realized GARCH in the time-frequency domain
- **Finding**: disentangling jump variation from integrated variation materially improves
  forecasts, and most predictive information sits in the highest-frequency band.
- **Repo surface**: `tradingagents/strategies/volatility_models.py::bipower_proxy` (line 616,
  jump share) and `long_memory.py::rv_forecast`.
- **Status**: `partial` — the jump *share* is computed (`bipower_proxy`) but never enters the
  RV forecast; there is no HAR-J.
- **Concrete step**: feed `bipower_proxy`'s jump-share as an extra regressor to produce a
  HAR-J variant of `rv_forecast`.

### L9. Garman-Klass and Parkinson are not the efficient OHLC estimators; Yang-Zhang is
- **Source**: `arXiv 0912.1617` (2009) and `arXiv 0908.1677` (2009) — Homogeneous volatility bridge estimators
- **Finding**: bridge estimators are significantly more efficient than Garman-Klass and
  Parkinson; Garman-Klass assumes zero drift and Parkinson discards open/close information,
  while Yang-Zhang is drift-independent and gap-aware.
- **Repo surface**: `tradingagents/strategies/volatility_models.py::parkinson_vol` (line 155),
  `garman_klass_vol` (line 185), `yang_zhang_vol` (line 288); exposed in
  `tradingagents/agents/utils/analysis_tools.py` at lines 11284-11289 and 11545-11553.
- **Status**: `shipped` — all three exist, and `regime.hmm_regime` already uses
  `yang_zhang_vol_series` as its volatility leg (regime.py:613); the risk is the analyst
  tool path where Parkinson/Garman-Klass are offered as first-class reads.
- **Concrete step**: annotate `parkinson_vol`/`garman_klass_vol` with their drift assumption
  and prefer `yang_zhang_vol` in the analyst-facing volatility tool.

### L10. The two long-memory estimators disagree; report both and treat d as a stress state variable
- **Source**: `arXiv 2605.24285` (2026) — Memory, Roughness, and Information Persistence
- **Finding**: on the same 115-stock panel GPH gives d = 0.226 and local Whittle d = 0.440;
  persistence rises in crises, co-moves with the VIX, and its forecast value is concentrated
  at longer horizons and in stress — and comes from cross-sectional aggregates, not own-stock d.
- **Repo surface**: `tradingagents/strategies/long_memory.py::memory_parameter` (line 146)
  reports `gph_d`, `whittle_d` and an `se`; `mean_reversion.py::memory_profile` pairs it with
  the forecast.
- **Status**: `partial` — both estimators are already reported (this matches the paper), but
  the estimator *spread* is not surfaced as a signal and the HAR-X cross-sectional leg is
  unavailable.
- **Concrete step**: carry the GPH/Whittle spread in the `memory_parameter` record's basis and
  consume `d` (or its deviation from its own history) as a regime-input in `regime_score`.

### L11. A rough fractional SV forecast is a real competitor to HAR
- **Source**: `arXiv 1410.3394` (2014) — Volatility is rough; `arXiv 2312.01426` (2023) — range-based evidence
- **Finding**: RFSV volatility forecasts outperform conventional AR and HAR forecasts
  (Gatheral et al.), and the result replicates on range proxies across non-standard assets
  (Mouti).
- **Repo surface**: `tradingagents/strategies/long_memory.py` (new `rfsv_forecast`).
- **Status**: `absent` — the repo has the HAS-HAR forecast and the memory parameter, but no
  fractional forecast model.
- **Concrete step**: add a RFSV next-day log-RV forecast (the closed-form fOU predictor, no
  simulation needed) as a candidate in the forecast pool, benchmarked against `rv_forecast`.

### L12. GARCH innovations should be non-Gaussian; FIGARCH covers long memory
- **Source**: `arXiv 1909.04903` (2019) — Bitcoin GARCH with Student-t, GED, NIG;
  `docs/design_forecasting_libraries.md` §4.2 (records the in-house gap)
- **Finding**: fat-tailed, skewed innovations (t/GED/NIG) fit and forecast crypto/equity
  volatility materially better than Gaussian, and FIGARCH is the standard long-memory
  conditional-variance model.
- **Repo surface**: `tradingagents/strategies/volatility_models.py::garch11_fit` (Gaussian MLE).
- **Status**: `partial` — `garch11_fit` exists (and handles the IGARCH boundary), but the
  design doc states explicitly it has no Student-t/skew/GED option and that no FIGARCH supplier
  exists in-house or in the candidate libraries.
- **Concrete step**: add a Student-t innovation option to `garch11_fit`'s likelihood; if a
  FIGARCH is ever declared, treat it as a new capability gap under FD-1 rather than assuming
  a library supplies it.

## 4. Where this repo is already ahead of the literature

- **Covariance estimator choice.** The repo uses Ledoit-Wolf shrinkage and EWMA covariance and
  has no DCC; `arXiv 2309.17219` shows the DCC+NLS state of the art loses on Sharpe to a simple
  filter. The repo avoided the losing branch a priori.
- **Volatility leg in the regime model.** `regime.hmm_regime` (regime.py:613) drives its
  HMM feature with `yang_zhang_vol_series`, the drift-independent, gap-aware estimator — ahead
  of the Parkinson/Garman-Klass choices still common in the range-volatility literature
  (`arXiv 2603.02898`).
- **Two long-memory estimators side by side.** `long_memory.memory_parameter` reports GPH and
  local Whittle together with an asymptotic standard error, which is exactly the pair
  `arXiv 2605.24285` uses to expose their disagreement. Single-estimator practice is the norm.
- **Refusal discipline over fabricated numbers.** `rv_forecast`/`memory_parameter` return
  `status:"unavailable"` with a named reason below their floors rather than a number. This is
  the discipline Cont & Das (`arXiv 2203.13820`) and Fukasawa et al. (`arXiv 1905.04852`) argue
  for, since a roughness estimate from a noisy proxy is worse than none.
- **One authoritative RV producer with a declared benchmark.** `forecast_registry` pins
  `long_memory.realized_volatility.v1` with `benchmark_ref = "volatility.har_rv"` and QLIKE in
  the contract — the "compute, don't narrate" boundary the forecast-evaluation literature
  presupposes (`arXiv 2607.05291`).

## 5. Defects or risks the literature exposes

1. **The HAR is fit in RV levels with a squared-daily-return proxy, not log-RV.**
   `long_memory.py::rv_forecast` defines `RV = returns ** 2` and fits the level regression,
   while `arXiv 2406.08041` and `arXiv 2607.05291` both define the benchmark as **log-RV** and
   state the log estimator dominates the standard one. The repo's HAR is therefore a
   non-standard variant, and `forecast_publisher` labels it `har_rv.ols.v1` — the model
   version does not disclose that the target is levels, not logs.

2. **`mean_reversion.hurst_exponent` labels a return-series R/S exponent as roughness.**
   `memory_profile` returns it as `roughness_h`, but R/S on the *return* series measures return
   persistence/mean-reversion, not the H of log volatility. `arXiv 2203.13820` and
   `arXiv 1905.04852` show the roughness question is about the log-volatility path and that
   naive scaling estimators are biased. A consumer reading `roughness_h ≈ 0.5` would wrongly
   conclude the volatility is *not* rough.

3. **The analyst tool path surfaces the dominated OHLC estimators.**
   `analysis_tools.py:11284-11289` offers Parkinson and Garman-Klass as the volatility read.
   `arXiv 0912.1617`/`0908.1677` show both are strictly less efficient than the Yang-Zhang/bridge
   estimator the repo already owns (`yang_zhang_vol`, `volatility_models.py:288`). Garman-Klass
   additionally assumes zero drift.

4. **Forecast evaluations carry no significance test.**
   `prediction_ledger.py` (`benchmark_delta`, lines 291-293) reports a signed loss difference
   with no Diebold-Mariano statistic and no MZ regression. `arXiv 2607.05291` demonstrates a
   case where a raw loss advantage reverses under MZ recalibration; `arXiv 2605.24285` adds the
   panel-aware-inference warning that naive pooling inflates significance. A "beat the
   benchmark" flag without either test is exactly the overclaim those papers guard against.

5. **The HAR-X term that the source paper shows matters is permanently unavailable.**
   `long_memory.rv_forecast` reports its `extra` (cross-sectional/sector aggregate) leg as
   `unavailable` because no panel read exists. `arXiv 2605.24285` finds the forecasting gains
   come *primarily* from cross-sectional and sectoral persistence aggregates and
   persistence-by-stress interactions, not own-stock persistence — i.e. the deployed HAR omits
   the term the paper identifies as the source of the gain.

6. **One window constant serves two models with different optimal windows.**
   `rv_forecast` defaults its HAR window to `MEMORY_WINDOW = 750`, the window `arXiv 2605.24285`
   uses for the memory parameter. `arXiv 2406.08041` finds the optimal HAR window is roughly
   **630** days, and the two choices answer different estimation problems. Sharing the constant
   silently ties the HAR regressor set to a memory-estimation decision.

## 6. Limits of this review

Read in substantial part (abstract + introduction + method and/or results + conclusion as
available): 16 papers — 1410.3394, 2203.13820, 1905.04852, 2312.01426, 2605.24285, 2406.08041,
2603.02898, 2309.17219, 2006.03458, 1204.1452, 2602.19732, 2607.05291, 2305.04137, 2604.01431,
2508.15922, 2407.10659 (plus the two Saichev/Sornette bridge papers). Skimmed or abstract-only:
the remaining ~44 booklist papers and the medium/low evidence rows; thesis-length and
simulation-only physics/econophysics entries were not opened. The category was sampled by
relevance score (top 60) biased toward the priority themes; the 1079-paper population is far
larger and mostly `q-fin.ST`. I did not re-run any repo code, tests or linters; all repo
claims come from reading the cited modules. Estimator performance numbers quoted from a paper
are the paper's own, on the paper's own data, and are not claims about this engine.
