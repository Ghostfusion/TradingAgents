# Evidence pack — Regimes, Change Points & Bubbles (`regime-changepoint`)

Annotated sweep rows for this category: **663** (high 39 · med 409 · low 215).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (39)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2608.23808v2](https://arxiv.org/abs/2608.23808v2) | MinervaScore grades post-selection robustness from Deflated Sharpe, PBO, SPA, Minimum Track Record Length and regime stability; on 359,062 records it separates real signal from lucky backtests at AUROC 0.989. | strategies/evaluate.py |
| 2026 | [2605.24285v1](https://arxiv.org/abs/2605.24285v1) | Combines long-memory estimation, rough-volatility diagnostics and persistence regressions on 115 S&P500 names; GPH d=0.226, local-Whittle d=0.440; persistence rises in crises and with VIX. | strategies/long_memory.py |
| 2026 | [2601.07687v4](https://arxiv.org/abs/2601.07687v4) | Physics-informed neural estimator cleans cross-covariance matrices by learning a nonlinear map of empirical singular values; matches analytic shrinkage and stays stable as universe size grows on U.S. equities. | `strategies/covariance_models.py` |
| 2026 | [2602.07085v3](https://arxiv.org/abs/2602.07085v3) | QuantaAlpha: evolutionary LLM alpha-mining framework using trajectory-level mutation/crossover with semantic consistency; on CSI 300 achieves IC 0.0472, ARR 4.68%, MDD 11.8%, and transfers to CSI 500 and S&P 500. | `strategies/alpha_zoo.py` |
| 2026 | [2606.31251v1](https://arxiv.org/abs/2606.31251v1) | Walk-forward S&P 500 backtest models Adjusted Information Ratio sequences for an SVM strategy versus buy-and-hold via GAMLSS with a Zero-Adjusted Gamma response conditioned on volatility and momentum; dominance is regime-conditional. | strategies/regime_performance.py |
| 2026 | [2604.17327v1](https://arxiv.org/abs/2604.17327v1) | Live portfolio validation of multi-agent MarketSenseAI on the S&P500 (19 months): the strong-buy equal-weight portfolio earns +2.18%/month versus a +1.15% passive benchmark; agent-structure analysis reveals the edge source. | `strategies/alpha_eval.py` |
| 2026 | [2608.20020v1](https://arxiv.org/abs/2608.20020v1) | Measures co-movement reconfiguration as mean squared sine of principal angles between S&P 500 subdominant eigenspaces; it is priced in the variance risk premium (t=5.40), with only the persistent component compensated. | strategies/eigen_rotation.py |
| 2025 | [2511.08571v1](https://arxiv.org/abs/2511.08571v1) | Walk-forward gold-futures trend/momentum strategy with volatility targeting, impact-adjusted fractional Kelly sizing and ATR exits; delivers Sharpe 2.88 and 0.52 percent max drawdown net of costs. | `strategies/momentum.py` |
| 2025 | [2507.22712v2](https://arxiv.org/abs/2507.22712v2) | Applies structural order-lifetime and modification filters to BankNifty limit-order-book imbalance; filtering parent orders of executed trades strengthens OBI-return directional association, while aggregate-flow filtration changes little, per correlation, regime and Hawkes diagnostics. | `strategies/orderflow.py` |
| 2025 | [2507.15437v3](https://arxiv.org/abs/2507.15437v3) | Forecasts linear fractional stable motion increments using codifference-based conditional expectation or semimetric projection; simulation and real volatility data show it outperforms fBm and HAR, revealing a selective-memory regime in rough volatility. | `strategies/long_memory.py` |
| 2025 | [2512.02037v1](https://arxiv.org/abs/2512.02037v1) | Adapts Avellaneda–Lee pairs trading to Polish equities, replicating assets via PCA, ETFs and LSTM factors; 2017-2019 PCA earns ~20% cumulative, Sharpe 2.63; only ETF approach survives 2020. | `strategies/mean_reversion.py` |
| 2024 | [2402.05272v3](https://arxiv.org/abs/2402.05272v3) | Statistical jump model regime-switching with jump-penalty persistence and time-series CV directly optimising strategy performance reduces downside risk vs Markov-switching. | `strategies/regime.py` |
| 2024 | [2401.03393v2](https://arxiv.org/abs/2401.03393v2) | Compares Markov-Switching GARCH with Stochastic ARV models for Bitcoin conditional variance; SARV forecasts better and two-stage estimation is recommended. | `strategies/volatility_models.py` |
| 2024 | [2401.03443v1](https://arxiv.org/abs/2401.03443v1) | Structured factor copulas model joint and conditional bank distress from CDS; systematic contagion via latent global plus region-specific factors prevails. | `strategies/tail_risk.py` |
| 2023 | [2307.03693v1](https://arxiv.org/abs/2307.03693v1) | Classifies five decades of S&P500 realized-volatility extremes into Black Swans, Dragon Kings and negative Dragon Kings, aligning largest values with major crises. | `strategies/tail_risk.py` |
| 2023 | [2308.00087v1](https://arxiv.org/abs/2308.00087v1) | Efficient Bayesian multi-change-point Python implementation decodes crisis periods from S&P500 mean market correlation retrospectively and online pre-crisis. | `strategies/regime.py` |
| 2023 | [2311.10739v1](https://arxiv.org/abs/2311.10739v1) | Markov-switching VAR splits Bitcoin returns into low- and high-volatility regimes; rising monetary-policy uncertainty cuts BTC returns by -0.028 and -0.44. | `strategies/regime_state.py` |
| 2023 | [2309.00025v1](https://arxiv.org/abs/2309.00025v1) | Proposes consistent nonparametric dependence measures (nonlinear, local, transformation-invariant); high-frequency returns show tail asymmetry and lack of diversification at distress. | `strategies/covariance_models.py` |
| 2023 | [2304.09947v2](https://arxiv.org/abs/2304.09947v2) | Gradient-free online ensemble reweights 16 models by out-of-sample R-squared; applied to sector rotation, finding sector returns more predictable than stock returns. | `strategies/rotation.py` |
| 2023 | [2304.14098v2](https://arxiv.org/abs/2304.14098v2) | Optimal covariance cleaning for heavy tails; Frobenius-norm minimization equals information-loss minimization for Gaussian but deviates for Student-t in finite samples. | `strategies/covariance_models.py` |
| 2023 | [2307.00459v1](https://arxiv.org/abs/2307.00459v1) | PCA on S&P 500 covariance with an HMM on principal components forecasts factor then stock returns; tuned strategy beats buy-and-hold. | `strategies/factors.py` |
| 2023 | [2304.09937v1](https://arxiv.org/abs/2304.09937v1) | ML stock predictions degrade during recessions; recession history and risk-free rate do not help, and good-recession performance reflects low volatility, not ML merit. | `strategies/regime_performance.py` |
| 2022 | [2209.05559v6](https://arxiv.org/abs/2209.05559v6) | Hypothesis-test approach to backtest overfitting in deep-RL crypto trading; less-overfitted agents earn higher returns than benchmark during a double market crash. | strategies/evaluate.py |
| 2021 | [2104.03667v1](https://arxiv.org/abs/2104.03667v1) | Detects market regimes from monthly realized covariance matrices comparing a vector logistic smooth-transition autoregressive model against unsupervised learning, improving tail-risk hedging. | `strategies/regime_state.py` |
| 2020 | [2004.09963v3](https://arxiv.org/abs/2004.09963v3) | Change-point detection plus clustering of segment distributions learns discrete volatility regimes for indices, equities, ETFs, FX; feeds a validated online dynamic risk-avoidance strategy. | strategies/regime.py |
| 2018 | [1812.02527v1](https://arxiv.org/abs/1812.02527v1) | Uses State Switching Markov Autoregressive models to identify Wyckoff-style accumulation/distribution/advance/decline regimes, then tailors trend, range, retracement and breakout strategies per regime. | `strategies/regime_state.py` |
| 2018 | [1811.11618v2](https://arxiv.org/abs/1811.11618v2) | Revisits Kalman filtering via probabilistic graphical models, links it to HMMs, adds extended-Kalman inference algorithms and CMA-ES estimation, and shows superior trend-following detection. | `strategies/statistical_kalman.py` |
| 2013 | [1302.1405v2](https://arxiv.org/abs/1302.1405v2) | Hawkes self-exciting fit to E-Mini S&P mid-price changes gives a two-regime power-law kernel (exponents -1.15 and -1.45) that integrates to unity 1998-2011, implying markets stay near criticality. | `strategies/orderflow.py` |
| 2013 | [1212.6016v1](https://arxiv.org/abs/1212.6016v1) | Nonparametric structural-break detection for volatility models drift separately within each regime without Gaussian assumptions, improving fit on major stock indices. | `strategies/regime_state.py` |
| 2013 | [1302.7036v2](https://arxiv.org/abs/1302.7036v2) | Two-step stochastic cusp catastrophe on realized-volatility-normalized US returns (27 years) confirms bifurcations only in the first half of the sample. | `strategies/regime.py` |
| 2012 | [1204.3136v3](https://arxiv.org/abs/1204.3136v3) | A thermodynamic multifractal partition-function index (normalized energy variation) identifies 1929, 1987 and 2008 crashes in real time and shows forecasting capability. | `strategies/regime.py` |
| 2012 | [1204.1452v4](https://arxiv.org/abs/1204.1452v4) | Realized GARCH with multi-time-frequency realized volatility and jump wavelet two-scale estimator beats conventional models in FX futures; most forecast information comes from the highest frequencies. | `strategies/volatility_models.py` |
| 2012 | [1201.3572v2](https://arxiv.org/abs/1201.3572v2) | Hawkes self-excited calibration of E-mini S&P 500 futures 1998-2010 measures endogeneity: the exogenous share of price changes fell from 70% in 1998 to under 30% since 2007. | `strategies/orderflow.py` |
| 2012 | [1208.4831v2](https://arxiv.org/abs/1208.4831v2) | Wavelet band least-squares finds fractional cointegration between implied and realized volatility; corridor implied volatility (not MFIV) is the unbiased long-run RV forecast on S&P 500/DAX. | `strategies/options_surface.py` |
| 2011 | [1112.3095v3](https://arxiv.org/abs/1112.3095v3) | Documents a November 2007 bear raid on Citigroup via anomalous borrowed-share selling coinciding with a price drop, arguing the repealed uptick rule was needed for stability. | `strategies/short_interest.py` |
| 2011 | [1102.4819v2](https://arxiv.org/abs/1102.4819v2) | Generalizes ARCH into a two-regime process with threshold-triggered memory of past high-volatility values; yields fat-tailed densities and instantaneous-variance Hurst exponent above 0.8. | strategies/volatility_models.py |
| 2010 | [1009.2928v1](https://arxiv.org/abs/1009.2928v1) | Reviews evidence that volatility is predominantly endogenous from order-flow/liquidity fluctuations; identifies a bid-ask-spread–volatility feedback loop driving micro-liquidity crises and price jumps. | strategies/orderflow.py |
| 2009 | [0904.1500v1](https://arxiv.org/abs/0904.1500v1) | Calibrates regime-switching volatility models with the Baum-Welch algorithm instead of the Hamilton filter, showing advantages on S&P500 in- and out-of-sample. | `strategies/regime.py` |
| 2004 | [cond-mat/0410079v1](https://arxiv.org/abs/cond-mat/0410079v1) | Earnings forecasts 1987-2004 are over-optimistic and herding; a year-ahead skill ~ "no change" forecast; herding stronger in US; clear sector effects. | strategies/analyst_revisions.py |

## Medium relevance (100) (showing the 100 most recent of 409)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2606.27932v1](https://arxiv.org/abs/2606.27932v1) | A Grünwald-Letnikov fractional-derivative KS framework removes the long-memory singularity to estimate Hurst exponents consistently; applied to realized volatility and equity indices it detects rough volatility and persistent, anti-persistent or efficient market states. | strategies/long_memory.py |
| 2026 | [2606.15755v1](https://arxiv.org/abs/2606.15755v1) | Multiplex Network Hawkes model with covariate-dependent excitation layers infers contagion from 99 firms' CDS (2004-2022); contagion is sparse, concentrated in outward flows from few institutions, with industry similarity the most supported channel. | strategies/triadic_stress.py |
| 2026 | [2607.03858v1](https://arxiv.org/abs/2607.03858v1) | Multivariate spectral variance-ratio generalisation decomposes long-horizon equity memory into return and volatility channels; a parsimonious five-factor model fits five panels and dates a late-1980s US volatility-memory regime transition. | strategies/long_memory.py |
| 2026 | [2605.11423v3](https://arxiv.org/abs/2605.11423v3) | Volatility-Volume-Gap classifier flags MNQ days with elevated overnight gap, first-30min return and first-bar volume; activates 4.4% of sessions, 77.6% reverse from peak, but no directional config passes (best T=1.46). | strategies/pre_market.py |
| 2026 | [2603.19136v2](https://arxiv.org/abs/2603.19136v2) | Autoencoder reconstruction-error gating routes data to dual node transformers specialized for stable versus event-driven regimes, with reinforcement-learning control and no manual regime labels. | `strategies/regime_state.py` |
| 2026 | [2608.26128v1](https://arxiv.org/abs/2608.26128v1) | Econophysics thesis clusters spectral quantities of 430-stock S&P 500 correlation matrices into Market States; COVID-19 emerges atypical, needing C^2/C^3 reconstructions, with participation spreading during crises. | strategies/covariance_models.py |
| 2026 | [2608.06618v1](https://arxiv.org/abs/2608.06618v1) | MINGLE jointly learns latent factors and an exposure-similarity graph via ADMM for portfolio diversification; the exposure graph aligns with sectors and its portfolios beat correlation-based counterparts across volatility regimes and costs. | strategies/portfolio_optimizer.py |
| 2026 | [2605.16324v1](https://arxiv.org/abs/2605.16324v1) | Bi-level chaotic-fusion graph network predicts intervals for stock returns via separate center/width functions and volatility-aware gating, improving interval calibration and sharpness across regimes. | strategies/conformal.py |
| 2026 | [2607.28294v1](https://arxiv.org/abs/2607.28294v1) | Develops bootstrap inference for autoregressive conditional duration models over fixed calendar spans; consistency holds for tail index at least 1 and percentile intervals stay valid in infinite-mean regimes, applied to crypto ETF durations. | strategies/statistical.py |
| 2026 | [2605.29541v1](https://arxiv.org/abs/2605.29541v1) | Copula-based Markov chain with Weibull marginals (Clayton/Joe copulas) for offline change-point estimation under nonlinear serial dependence; MLE via Newton-Raphson with bootstrap intervals. | strategies/statistical.py |
| 2026 | [2606.23492v1](https://arxiv.org/abs/2606.23492v1) | Continuous hidden Markov model with heavy-tailed emissions (Gaussian, Student-t, Laplace, generalized error) separates regime autocorrelation from marginal shape; on U.S. equities heavy-tailed marginals close most of the fit gap, recovering volatility clustering and reducing kurtosis. | strategies/regime_state.py |
| 2026 | [2601.00395v1](https://arxiv.org/abs/2601.00395v1) | Builds conditional p-threshold mutual-information minimum-spanning-tree networks for QUAD large caps around the COVID crash; networks integrate during the crash and post-crash shows higher relative frequency of large volatility events. | `strategies/triadic_stress.py` |
| 2026 | [2606.16840v1](https://arxiv.org/abs/2606.16840v1) | Dynamic Hüsler-Reiss graphical models on the 13 largest cryptocurrencies show a near-complete stable lower-tail dependence graph versus a thinning upper tail; intra-crypto diversification fails on the downside and standard models understate crash probability eight-fold. | strategies/tail_risk.py |
| 2026 | [2606.08586v1](https://arxiv.org/abs/2606.08586v1) | Builds stock-level topological anomaly scores via Takens delay embedding, BallMapper graphs and decoder-conditional VAEs, testing predictive content for intraday return curves; penalised function-on-function regression confirms a regime-dependent temporal fingerprint across all assets. | strategies/cross_section.py |
| 2026 | [2608.29025v1](https://arxiv.org/abs/2608.29025v1) | Compares classical and deep hedging on real Deribit BTC options; Whalley-Wilmott cuts costs by $1.79 per episode, and none of the three deep hedging models beats any classical benchmark on any metric. | strategies/options_math.py |
| 2026 | [2602.07046v5](https://arxiv.org/abs/2602.07046v5) | GJR-GARCH-X event study of 50 crypto shocks across six assets; curated high-salience events give 3.49x variance multiplier but dependence-robust inference removes significance (copula p~0.39); asymmetry directional, selection-conditional, unresolved. | `strategies/volatility_models.py` |
| 2026 | [2604.01431v1](https://arxiv.org/abs/2604.01431v1) | Daily Kalshi prediction-market probability changes forecast crypto realized volatility: Fed repricing predicts Bitcoin (t=3.63), recession-risk signal gives out-of-sample MSFE 0.979 (Clark-West p=0.020), CPI repricing predicts altcoins. | `strategies/volatility_models.py` |
| 2026 | [2605.30363v2](https://arxiv.org/abs/2605.30363v2) | Text-enhanced regime-shift pipeline cross-validates LLM-proposed candidates from text with a likelihood-ratio VAR test on the panel; deployed on FOMC minutes plus a 14-variable Treasury panel 2010-2024. | strategies/regime.py |
| 2026 | [2605.12977v1](https://arxiv.org/abs/2605.12977v1) | MLE method enhances an existing factor risk model by refining factors and adding transient statistical factors; needs only returns plus two hyperparameters (number of factors, half-life). | strategies/covariance_models.py |
| 2026 | [2602.00776v1](https://arxiv.org/abs/2602.00776v1) | Unified CatBoost pipeline (direction-aware GMADL, time-series CV) on 1-second Binance Futures order books shows stable SHAP feature rankings across BTC/LTC/ETC/ENJ/ROSE; maker/taker backtests validate adverse-selection microstructure theory. | `strategies/orderflow.py` |
| 2026 | [2606.03184v1](https://arxiv.org/abs/2606.03184v1) | Introduces FinStressTS, a synthetic benchmark of 30 diagnostic environments spanning six mechanism families; benchmarks 15 forecasters, finding autoregressive and linear models often beat Transformers on volatility-, tail- and jump-driven tasks. | strategies/evaluate.py |
| 2026 | [2608.22864v1](https://arxiv.org/abs/2608.22864v1) | Reformulates the Bayesian filter for Markov-Switching-Multifractal volatility using likelihood permutation symmetry, cutting complexity from O(D^k) to O(k^D) and improving ground-truth recovery. | strategies/volatility_models.py |
| 2026 | [2601.10517v2](https://arxiv.org/abs/2601.10517v2) | Extends Log S-fBM to a multivariate volatility model (mLog S-fBM) with co-Hurst and co-intermittency matrices; S&P 500 estimates show multifractal behavior and off-diagonal co-Hurst near H≈0.12. | `strategies/volatility_models.py` |
| 2026 | [2605.11645v1](https://arxiv.org/abs/2605.11645v1) | GeomHerd tracks Ollivier-Ricci curvature on LLM-agent interaction graphs to quantify herding forward-looking, bypassing price-correlation lag; mean-field bridge links it to the CSAD statistic. | strategies/consensus.py |
| 2026 | [2605.17117v2](https://arxiv.org/abs/2605.17117v2) | Four geometric observables (Berry phase rate, spectral entropy, state purity, Hamiltonian sensitivity) detect regime shifts across 17 crises; Berry phase d=0.72 with ~67% fewer false alarms than a Random Forest. | strategies/regime_state.py |
| 2026 | [2604.09821v2](https://arxiv.org/abs/2604.09821v2) | Two-stage panel forecaster (global pooled AR(1) plus block-specific local residual models) lifts out-of-sample R2 from 0.630 to 0.677 on a 93-actor quarterly panel, confirmed on held-out 2015-2024 windows. | `strategies/cross_section.py` |
| 2026 | [2608.24786v1](https://arxiv.org/abs/2608.24786v1) | Applies LightGBM LambdaRank to the SPXW zero-day short-put cross-section with margin sizing and uncertainty abstention; out-of-time Sharpe 4.31-5.76 and PSR 0.964, beating passive benchmarks by at least 3.84. | strategies/cross_section.py |
| 2026 | [2603.10202v2](https://arxiv.org/abs/2603.10202v2) | Hybrid HMM discretizes excess growth rates into Laplace quantile states, augments regime switching with Poisson jump-duration for tail dwell times, and is fitted by transition counting, scaling to 424 assets. | `strategies/regime.py` |
| 2026 | [2606.03457v1](https://arxiv.org/abs/2606.03457v1) | Hybrid news sentiment engine: a CPU-only three-way ensemble of FinBERT-style lexicon scoring, adaptive TF-IDF headline clustering tracking realized price reactions, and auto-calibrating weights; adapts to market regimes without retraining or GPU compute. | strategies/sentiment_research.py |
| 2026 | [2606.07450v1](https://arxiv.org/abs/2606.07450v1) | Tests Pearson versus mutual-information dependency estimators with MST/PMFG filtering and four community decoders across 2,328 Indonesian rolling windows; Pearson-MST-Infomap best recovers sectors, while MI-PMFG exposes local and heterogeneous structures. | strategies/peer_universe.py |
| 2026 | [2607.03888v2](https://arxiv.org/abs/2607.03888v2) | Local Gaussian correlation degrades in joint tails via sample scarcity; derives the AMISE-optimal location-adaptive bandwidth and maps where adaptivity beats the global plug-in (moderate dependence, curved surfaces only). | strategies/tail_risk.py |
| 2026 | [2606.00624v1](https://arxiv.org/abs/2606.00624v1) | HANET hierarchically nests daily asset-return signals inside monthly macro windows with cross-attention; attention over macro contexts adapts to scarce regimes across 55 liquid futures. | strategies/regime_score.py |
| 2026 | [2608.03616v1](https://arxiv.org/abs/2608.03616v1) | Measures the branching ratio of the October 2025 crypto-perpetual liquidation cascade in-flight; it ran deeply subcritical at lambda ~0.1-0.2, with 88% of forced selling inside thirty minutes and 63% absorbed off-book. | strategies/tail_risk.py |
| 2026 | [2603.21672v3](https://arxiv.org/abs/2603.21672v3) | Bayesian framework where investors underestimate structural breaks in factor risk premia; a predictive-likelihood-ratio mislearning intensity relates to persistent pricing distortions rather than immediate collapse. | `strategies/factors.py` |
| 2026 | [2606.06190v1](https://arxiv.org/abs/2606.06190v1) | Triple-timeframe Markov-switching GARCH (daily/4-hour/hourly) with Filardo time-varying transition probabilities combines three AR(1)-MS-GARCH models into a 27-state tensor, achieving superior out-of-sample EUR/USD volatility forecasting versus conventional GARCH. | strategies/volatility_models.py |
| 2026 | [2605.14976v3](https://arxiv.org/abs/2605.14976v3) | Extends GAS Markov-switching to K regimes with time-varying transition probabilities and regime-specific means/variances; R package multiregimeTVTP; applied to US Treasury yields 1961-2024. | strategies/regime_state.py |
| 2026 | [2603.20456v1](https://arxiv.org/abs/2603.20456v1) | Neural HMM with adaptive granularity attention: a dilated-CNN tick encoder plus wavelet-LSTM, gated by local volatility and transaction intensity, for high-frequency order-flow modeling across scales. | `strategies/orderflow.py` |
| 2026 | [2607.19005v2](https://arxiv.org/abs/2607.19005v2) | Observable Matrix Dynamics tracks S&P 500 correlation distance matrices and Markov ranking chains; effective dimension collapses in 2008/2020, and correlation geometry forecasts the endogenous 2008 crisis but not 2020. | strategies/regime_state.py |
| 2026 | [2609.04420v1](https://arxiv.org/abs/2609.04420v1) | Derives exact finite-population variance and optimal stratified allocation for weighted rare-event risk estimation; the imbalance ratio cancels from the allocation, making equal allocation the default with realised ratio gamma=min(2*pi/f,1). | strategies/evaluate.py |
| 2026 | [2608.26115v1](https://arxiv.org/abs/2608.26115v1) | Re-estimates option-implied crash predictability on 12.36M firm-days (2015-2026); the smirk-return relation fades while IV spread and risk-neutral skewness persist, with boosted trees best in the AI/mega-cap regime. | strategies/options_surface.py |
| 2026 | [2601.01216v2](https://arxiv.org/abs/2601.01216v2) | Introduces order-constrained spectral causality via sensitivity of second-order dependence operators to order-preserving deformations; Granger, directed coherence, and Geweke causality are special cases, and simulations confirm power. | `strategies/statistical.py` |
| 2026 | [2606.06823v1](https://arxiv.org/abs/2606.06823v1) | PandaAI, a closed-loop neuro-symbolic LLM agent with market-regime modeling and constrained alpha generation, reports on CSI 300 18.2% higher Rank IC and 25.7% lower maximum drawdown than state-of-the-art time-series models. | strategies/alpha_zoo.py |
| 2026 | [2601.08571v1](https://arxiv.org/abs/2601.08571v1) | Hilbert-Huang regime identification plus variable-length Markov modeling on global equity indices finds developed markets normalize after stress while developing markets retain residual tail dependence and downside persistence. | `strategies/regime.py` |
| 2026 | [2606.02657v1](https://arxiv.org/abs/2606.02657v1) | Generalization bounds for Markov-switching distribution shift decompose regime-composition mismatch from regime sensitivity; the ex-post realized gap detects crisis geometry but not temporal arrival. | strategies/coverage_window.py |
| 2026 | [2605.27848v1](https://arxiv.org/abs/2605.27848v1) | Three-state Gaussian HMM (BIC-selected) plus reinforcement learning allocates across SPY/TLT/GLD 2004-2025; HMM-based allocations beat a passive SPY benchmark with a one-day execution lag. | strategies/regime.py |
| 2026 | [2601.10732v1](https://arxiv.org/abs/2601.10732v1) | Student-t HMM identifies crisis regimes where Value (HML) Granger-causes Size (SMB) at a 9-day lag (p<1e-4, 5/6 stress events); no trading profit, framed for risk management. | `strategies/regime.py` |
| 2026 | [2608.12251v1](https://arxiv.org/abs/2608.12251v1) | Proposes RG-ResMoE, a regime-gated residual mixture-of-experts for cross-sectional volatility forecasting; routing regime state to experts beats appending it as input, improving accuracy, stability and VaR calibration. | strategies/volatility_models.py |
| 2026 | [2609.07989v1](https://arxiv.org/abs/2609.07989v1) | Studies Bayesian Online Changepoint Detection and two literature extensions, applying them to signed order flow of NASDAQ-listed equities to identify structural breaks in real time. | strategies/orderflow.py |
| 2026 | [2606.09274v1](https://arxiv.org/abs/2606.09274v1) | Reverse stress testing reconstructs a coherent multivariate stress scenario from a single exogenous shock by maximizing conditional density, solved under parametric, empirical-likelihood semiparametric and nonparametric inverse-distance resampling assumptions; validated on market data. | strategies/book_risk.py |
| 2026 | [2604.10402v4](https://arxiv.org/abs/2604.10402v4) | Risk-sensitive specialist routing with online evaluation and state-dependent gating combines regime-specific ETF volatility forecasters; versus a rolling-best baseline it cuts high-volatility loss ~24% and underprediction loss ~22%. | `strategies/regime_performance.py` |
| 2026 | [2609.19013v2](https://arxiv.org/abs/2609.19013v2) | Measures routing frictions across Ethereum/Base AMM pools: measured access costs eliminate 80.45% of states with positive gross gains (34.85% gross lower bound vs 6.89% net upper), and realized multi-pool activation is just 1.203%. | strategies/market_tradability.py |
| 2026 | [2607.06220v1](https://arxiv.org/abs/2607.06220v1) | 45 years of US economic news sentiment show stable average tone but rising persistence and bimodality with longer pessimistic bursts, fitting an endogenous-memory model rather than daily short-memory reactions. | strategies/sentiment.py |
| 2026 | [2606.12446v2](https://arxiv.org/abs/2606.12446v2) | Shows persistent latent default-probability dynamics plus temporal coarse-graining generate effective default correlation, explaining long-horizon overdispersion and autocorrelation; coarse-graining monthly posterior paths improves predictive density and regularizes variance attribution. | strategies/credit_spread.py |
| 2026 | [2602.00073v1](https://arxiv.org/abs/2602.00073v1) | Test-time adaptation updates only normalization affine parameters on a frozen backbone under regime shift; batch-norm statistics update is a robust default for SPY/QQQ/EUR-USD, aggressive norm adaptation can hurt. | `strategies/regime.py` |
| 2026 | [2609.09405v1](https://arxiv.org/abs/2609.09405v1) | Provides statistical analysis of the Log S-fBM stochastic-volatility model, deriving scaling properties, tail-sensitive deviation inequalities, and a hypothesis test distinguishing rough (H near 0.1) from multifractal (H near 0) dynamics. | strategies/volatility_models.py |
| 2026 | [2601.21447v1](https://arxiv.org/abs/2601.21447v1) | Extends GARCH CCC/STCC/DCC models with Trade Policy Uncertainty and a presidential dummy for US stock-bond correlations 2015-2025; time-varying specs win, DCC+TPU gives best fit and forecasts. | `strategies/covariance_models.py` |
| 2026 | [2605.13407v1](https://arxiv.org/abs/2605.13407v1) | PRISM-VQ dynamic factor model combines expert priors, vector-quantized discrete latent factors and a structure-conditioned mixture-of-experts; improves cross-sectional ranking on CSI300/S&P500. | strategies/cross_section.py |
| 2026 | [2609.12793v1](https://arxiv.org/abs/2609.12793v1) | Proposes VertiFuseX, a hybrid LSTM with penultimate-layer vertical fusion of multi-scale temporal features; it achieves 30-54% MAPE reductions versus LSTM baselines across 10 global equity indices (2010-2024). | scripts/forecast_ledger.py |
| 2026 | [2609.14733v1](https://arxiv.org/abs/2609.14733v1) | Proposes WaVeFuse, wavelet-denoised OHLCV plus channel-wise CWT, CNN-BiLSTM and Transformer branches fused by vertical attention; it reaches R2 0.81-0.96 and 70.5-78.3% directional accuracy on four indices. | scripts/forecast_ledger.py |
| 2026 | [2602.11020v2](https://arxiv.org/abs/2602.11020v2) | Compares early vs late multi-view fusion (OHLCV chart, indicator matrix) for next-day direction under time-block splits with embargo; fusion is regime-dependent, late fusion more reliable once labels stabilize, joint FGSM/PGD attacks remain hard. | `strategies/evaluate.py` |
| 2026 | [2608.10693v1](https://arxiv.org/abs/2608.10693v1) | Uses a 2D convolutional LSTM with FOMC-date features to forecast the implied-volatility surface; pre-announcement IV rises strongest for short-dated OTM options in high-volatility regimes, with a limited but real ML edge. | strategies/options_surface.py |
| 2026 | [2607.27070v1](https://arxiv.org/abs/2607.27070v1) | Seven BTC liquidation cascades show no event-invariant early-warning variable: critical slowing down appears in price in five of seven but is absent in abrupt news shocks; taker order-flow variance compression is the only precursor. | strategies/regime_state.py |
| 2025 | [2508.20101v1](https://arxiv.org/abs/2508.20101v1) | Heterogeneous spatiotemporal GARCH adds spatially correlated innovations and varying parameters over a balance-sheet-derived proxy space; predicts firm volatility with contagion effects. | `strategies/covariance_models.py` |
| 2025 | [2504.06028v1](https://arxiv.org/abs/2504.06028v1) | Models uncovered-interest-parity deviations as a mean-reverting risk premium via an Ornstein-Uhlenbeck process inside the exchange-rate SDE; closed-form forecast distributions are coverage-backtested on USD/KRW, strong short/long term but weak at 3 months. | `strategies/mean_reversion.py` |
| 2025 | [2510.16636v1](https://arxiv.org/abs/2510.16636v1) | Three-step framework: right-tailed unit-root test identifies S&P 500 bubbles, NLP extracts news-sentiment features, and ensemble learning predicts bubble occurrence with macro indicators. | `strategies/regime.py` |
| 2025 | [2508.02686v1](https://arxiv.org/abs/2508.02686v1) | Mixture-of-Experts combines an RNN for high-volatility stocks with linear regression for stable ones via a volatility-aware gate; across 30 US stocks it cuts MSE up to 33% and 28% versus standalone models. | `strategies/regime_score.py` |
| 2025 | [2512.08000v1](https://arxiv.org/abs/2512.08000v1) | Fits self-exciting and inhibitory Hawkes processes to Chinese market and sector index returns, finding long-term dependencies where high-activity sectors sustain trends and low-activity periods show strong sector rotation. | `strategies/triadic_stress.py` |
| 2025 | [2502.08242v2](https://arxiv.org/abs/2502.08242v2) | Network communicability on correlation-derived Indian market graphs; 70%/80% of stock pairs shift significantly in GFC/COVID; communicability features beat shortest-path measures at classifying stable versus volatile periods. | `strategies/triadic_stress.py` |
| 2025 | [2508.16566v1](https://arxiv.org/abs/2508.16566v1) | Bivariate quadratic Hawkes process yields an asymmetric super-rough-Heston scaling limit preserving time-reversal asymmetry (Zumbach effect), with stochastic covariation between drivers in the near-unstable regime. | `strategies/orderflow.py` |
| 2025 | [2503.24241v1](https://arxiv.org/abs/2503.24241v1) | Analyzes decades of S&P500 accumulated returns' gain/loss distributions, fitting power-law tail CDFs with confidence intervals and U-tests; mean rises near-linearly with accumulation days, skew stays negative and roughly constant, variance scales linearly, contradicting symmetric-return theory. | `strategies/tail_risk.py` |
| 2025 | [2508.02758v1](https://arxiv.org/abs/2508.02758v1) | CTBench: first benchmark for cryptocurrency time-series generation, adding Market Utility and Statistical Arbitrage tasks; benchmarks eight models across four regimes, exposing fidelity-versus-profitability trade-offs. | `strategies/mean_reversion.py` |
| 2025 | [2502.14431v1](https://arxiv.org/abs/2502.14431v1) | Topological data analysis on multidimensional stock/commodity series; Wasserstein-distance spikes mark the COVID-19 crash and cross-market divergence; Granger tests show bidirectional crash-period causality, overall stock-to-commodity direction. | `strategies/regime.py` |
| 2025 | [2504.20116v1](https://arxiv.org/abs/2504.20116v1) | Shows leveraged-ETF compounding depends on return autocorrelation, volatility clustering and regime persistence, not just volatility drag; AR-GARCH and regime-switching models plus 20 years of SPDR data confirm trends help, mean reversion hurts. | `strategies/etf_risk.py` |
| 2025 | [2507.01989v1](https://arxiv.org/abs/2507.01989v1) | Models Iran, Turkey and Sri Lanka USD exchange-rate dynamics with Kramers-Moyal expansion and Fokker-Planck formalism; confirms Markovian log returns, finds stabilizing drift and nonlinear diffusion, and rolling estimation detects regime shifts tied to political events. | `strategies/regime_state.py` |
| 2025 | [2507.01971v1](https://arxiv.org/abs/2507.01971v1) | Proposes DeepSupp, a multi-head attention autoencoder over dynamic correlation matrices, extracting S&P 500 support levels via DBSCAN; it beats six baselines on six financial metrics including support accuracy and regime sensitivity. | `strategies/extended_indicators.py` |
| 2025 | [2508.07192v2](https://arxiv.org/abs/2508.07192v2) | Uses Wigner-type random matrices from correlated financial series; derives a deformed semicircle law, fourth moment growing with correlation strength and a moment phase transition under power-law decay. | `strategies/eigen_rotation.py` |
| 2025 | [2504.06566v5](https://arxiv.org/abs/2504.06566v5) | Diffusion factor model embeds latent factor structure into generative diffusion by decomposing the score function with time-varying orthogonal projections; nonasymptotic bounds depend on factor dimension, enabling high-dimensional return simulation and mean-variance/factor portfolios. | `strategies/factors.py` |
| 2025 | [2512.00893v1](https://arxiv.org/abs/2512.00893v1) | Structural-break analysis of the 2024 U.S. election shows human-driven ERC-20 stablecoin transfers shifted two days pre-election, exchange volumes on Election Day, and algorithmic activity in January 2025. | `strategies/regime.py` |
| 2025 | [2501.16659v1](https://arxiv.org/abs/2501.16659v1) | Solves Exploratory Mean-Variance with Regime Switching via RL, proving a Policy Improvement Theorem; Orthogonality Condition learning beats temporal-difference learning and outperforms on real market data. | `strategies/portfolio_optimizer.py` |
| 2025 | [2512.12334v1](https://arxiv.org/abs/2512.12334v1) | Extends dynamic Bayesian networks to 10-day 97.5% expected shortfall and stressed ES on S&P 500; backtests show all models fail accurate ES/SES, with EGARCH(1,1) best for ES and GARCH(1,1) for SES. | `strategies/book_risk.py` |
| 2025 | [2509.18820v2](https://arxiv.org/abs/2509.18820v2) | q-dependent detrended cross-correlation and q-minimum-spanning-trees track amplitude-dependent correlation structure of 140 Binance crypto pairs; networks shift at the April 2022 Terra/Luna crash. | `strategies/triadic_stress.py` |
| 2025 | [2502.04027v1](https://arxiv.org/abs/2502.04027v1) | Extends hidden-Markov-modulated Hawkes point process to piecewise-constant excitation kernels with EM inference; detects anomalous trade bursts in high-frequency crypto data better than a Markov-modulated Poisson benchmark. | `strategies/orderflow.py` |
| 2025 | [2510.03236v1](https://arxiv.org/abs/2510.03236v1) | Regime-switching methods (soft Markov switching, distributional spectral clustering) forecast S&P 500 realized volatility from 5-minute returns, 2014-2025, with historical and sentiment features. | `strategies/volatility_models.py` |
| 2025 | [2512.17923v2](https://arxiv.org/abs/2512.17923v2) | Obfuscation testing: LLMs given only raw S&P 500 gamma-exposure values detect dealer hedging patterns (gamma, pinning, 0DTE) at 71.5%, staying 91.2% accurate without regime labels or temporal context. | `strategies/derivatives_gamma.py` |
| 2025 | [2512.21823v2](https://arxiv.org/abs/2512.21823v2) | Applies Conditional Restricted Boltzmann Machines with autoregressive conditioning and persistent contrastive divergence to multi-asset data 2013-2025; the Gaussian variant preserves correlations and offers interpretable systemic-risk regime detection. | `strategies/regime_state.py` |
| 2025 | [2511.07834v1](https://arxiv.org/abs/2511.07834v1) | Derives horizon-correct VaR, Expected Shortfall, Sharpe, Kelly and drawdown formulas under Levy-stable return scaling, each carrying a closed-form Gaussian-bias term from the tail-index gap. | `strategies/book_risk.py` |
| 2025 | [2507.09554v1](https://arxiv.org/abs/2507.09554v1) | Transfer entropy plus Kramers-Moyal expansion maps directional coupling among Nasdaq, WTI, gold and the dollar; average TE rises 35% and 28% during COVID and Ukraine crises, exposing nonlinear regime shifts. | `strategies/triadic_stress.py` |
| 2025 | [2502.14897v2](https://arxiv.org/abs/2502.14897v2) | Market-derived labels assign tweets by ensuing price trends; fine-tuned domain model beats sentiment benchmarks by 11%, context-aware variant hits 89.6% on Bitcoin news, backtests Sharpe up to 5.07. | `strategies/sentiment_research.py` |
| 2025 | [2504.18958v1](https://arxiv.org/abs/2504.18958v1) | Builds a tensor/eigenvalue Financial Chaos Index, fits a three-regime Modified Lognormal Power-Law switching model (1990-2023), and uses Equity Market Volatility sentiment with elastic net to forecast VIX across regimes. | `strategies/regime.py` |
| 2025 | [2509.00697v1](https://arxiv.org/abs/2509.00697v1) | 34-year Nifty 50 study mapping P/E to horizon-wise return distributions; finds 74% one-year gain probability, modal CAGR above 13%, ten-year trapping periods and low-dimensional chaos. | `strategies/complexity.py` |
| 2025 | [2510.13785v1](https://arxiv.org/abs/2510.13785v1) | Multifractal cross-correlation analysis attributes cryptocurrency multifractality to long-range correlations plus heavy-tailed returns, aiding volatility forecasting and regime-shift detection. | `strategies/complexity.py` |
| 2025 | [2506.23619v2](https://arxiv.org/abs/2506.23619v2) | Shows posterior drift degrades out-of-sample forecasting of overparametrized models; applied to equity-premium market timing, results are highly sensitive to sub-periods and bandwidth, with large bandwidths consistent but risk-adjusted unattractive. | `strategies/config_robustness.py` |
| 2025 | [2506.17549v1](https://arxiv.org/abs/2506.17549v1) | Develops Bayesian Generalised Pareto Regression linking tail scale to covariates for Indian Nifty 50 crashes; Cauchy prior wins on RMSE/AIC/BIC and S&P 500 and gold volatility significantly drive extreme-loss forecasts. | `strategies/tail_risk.py` |
| 2025 | [2509.11844v1](https://arxiv.org/abs/2509.11844v1) | ProteuS generates semi-synthetic financial time series with pre-defined structural breaks, supplying ground truth to benchmark concept-drift and regime-adaptation algorithms. | `strategies/regime.py` |
| 2025 | [2512.20477v1](https://arxiv.org/abs/2512.20477v1) | State-switching model with yield-curve-slope market state gives the Aligned Economic Index in-sample R²=5.9% and out-of-sample 4.12% predictability, beating Welch-Goyal predictors, including through COVID turbulence. | `strategies/regime.py` |
| 2025 | [2512.20460v2](https://arxiv.org/abs/2512.20460v2) | Introduces a state-switching predictive regression defining market state in real time from the yield-curve slope; the Aligned Economic Index improves in-sample and out-of-sample equity-premium predictability. | `strategies/regime.py` |
| 2025 | [2501.16772v2](https://arxiv.org/abs/2501.16772v2) | Across equities, rates, FX and commodities, markets trend on hours-to-years scales and revert shorter/longer; weak trends persist in trending regimes but revert before statistical significance, consistent with herding. | `strategies/mean_reversion.py` |
| 2025 | [2511.08608v1](https://arxiv.org/abs/2511.08608v1) | Rolling walk-forward test on NIFTY equities finds 'thinking' LLMs (gpt-5) do not reliably beat a direct LLM or ridge/random-forest learners on cross-sectional 1-IC, MSE and costed backtests. | `strategies/signal_analysis.py` |
| 2024 | [2403.01360v1](https://arxiv.org/abs/2403.01360v1) | 'Digitwashing' gap between digital-transformation words and deeds in A-share firms significantly raises stock price crash risk, driven by economic-policy-uncertainty perception. | `strategies/text_factors.py` |
| 2024 | [2404.04962v1](https://arxiv.org/abs/2404.04962v1) | High-frequency panel (2020-2022) finds crypto price volatility rises with positive returns and is driven by daily leverage, signed volatility and jumps, unlike classical equity behaviour. | `strategies/volatility_models.py` |

## Low relevance / background (215)

| year | id | title |
| --- | --- | --- |
| 2026 | [2608.26158v1](https://arxiv.org/abs/2608.26158v1) | A Frequency-Controlled Comparison of Tick- and Minute-Based Information Bars for Cryptocurrency Markets |
| 2026 | [2607.16281v1](https://arxiv.org/abs/2607.16281v1) | A Novel Hybrid Quantum Reservoir Computing (nHQRC) for Phase Transition Detection in Non-Equilibrium Dynamical Systems |
| 2026 | [2608.26106v1](https://arxiv.org/abs/2608.26106v1) | A Statistical-Finance Benchmark for Same-Day Directional Stock Prediction: Walk-Forward Evidence from SPY |
| 2026 | [2603.18107v1](https://arxiv.org/abs/2603.18107v1) | ARTEMIS: A Neuro Symbolic Framework for Economically Constrained Market Dynamics |
| 2026 | [2601.22200v1](https://arxiv.org/abs/2601.22200v1) | Adaptive Benign Overfitting (ABO): Overparameterized RLS for Online Learning in Non-stationary Time-series |
| 2026 | [2604.04662v1](https://arxiv.org/abs/2604.04662v1) | Anticipatory Reinforcement Learning: From Generative Path-Laws to Distributional Value Functions |
| 2026 | [2607.21826v1](https://arxiv.org/abs/2607.21826v1) | Are cryptocurrencies real financial bubbles? Evidence from quantitative analyses |
| 2026 | [2603.00422v3](https://arxiv.org/abs/2603.00422v3) | Coupled Supply and Demand Forecasting in Platform Accommodation Markets |
| 2026 | [2607.09906v1](https://arxiv.org/abs/2607.09906v1) | Depth-Efficient Quantum Topological Data Analysis for Regime-Specific Detection of Financial Stress |
| 2026 | [2601.16821v3](https://arxiv.org/abs/2601.16821v3) | Directional-Shift Dirichlet ARMA Models for Compositional Time Series with Structural Break Intervention |
| 2026 | [2601.12175v2](https://arxiv.org/abs/2601.12175v2) | Distributional Fitting and Tail Analysis of Lead-Time Compositions: Nights vs. Revenue on Airbnb |
| 2026 | [2607.25459v1](https://arxiv.org/abs/2607.25459v1) | Emergent Latent-State Computation under Stochastic Volatility |
| 2026 | [2609.17415v1](https://arxiv.org/abs/2609.17415v1) | Financial Contagion Networks as Annealing-Ready Ising Systems Cascades, Bailout Optimization, and Susceptibility |
| 2026 | [2602.18358v4](https://arxiv.org/abs/2602.18358v4) | Forecasting the Evolving Composition of Inbound Tourism Demand: A Bayesian Compositional Time Series Approach Using Platform Booking Data |
| 2026 | [2604.05008v1](https://arxiv.org/abs/2604.05008v1) | Generative Path-Law Jump-Diffusion: Sequential MMD-Gradient Flows and Generalisation Bounds in Marcus-Signature RKHS |
| 2026 | [2606.30037v1](https://arxiv.org/abs/2606.30037v1) | Heads, Not Backbones: Output Heads Dominate Architectures on Fat-Tailed Returns |
| 2026 | [2602.10960v1](https://arxiv.org/abs/2602.10960v1) | Integrating granular data into a multilayer network: an interbank model of the euro area for systemic risk assessment |
| 2026 | [2601.19321v1](https://arxiv.org/abs/2601.19321v1) | Predictive Accuracy versus Interpretability in Energy Markets: A Copula-Enhanced TVP-SVAR Analysis |
| 2026 | [2602.15474v1](https://arxiv.org/abs/2602.15474v1) | Quantum Reservoir Computing for Statistical Classification in a Superconducting Quantum Circuit |
| 2026 | [2605.12151v2](https://arxiv.org/abs/2605.12151v2) | RED-2400: A Public Benchmark of Algorithmically-Rejected Trading Events with Outcome Labels |
| 2026 | [2606.00061v1](https://arxiv.org/abs/2606.00061v1) | Reflexivity as Prompt: Does Awareness of Self-Reinforcing Market Dynamics Improve LLMs as Financial Market Forecasters? |
| 2026 | [2608.09378v1](https://arxiv.org/abs/2608.09378v1) | Scaling laws of Stablecoin Transactions: Evidence from USDT and USDC on the Ethereum blockchain |
| 2026 | [2602.18572v1](https://arxiv.org/abs/2602.18572v1) | Sub-City Real Estate Price Index Forecasting at Weekly Horizons Using Satellite Radar and News Sentiment |
| 2026 | [2604.19796v1](https://arxiv.org/abs/2604.19796v1) | Systemic Risk and Default Cascades in Global Equity Markets: A Network and Tail-Risk Approach Based on the Gai Kapadia Framework |
| 2026 | [2605.12547v2](https://arxiv.org/abs/2605.12547v2) | The Payment Heterogeneity Index: An Integrated Unsupervised Framework for High-Volume Procurement Oversight and Decision Support |
| 2026 | [2607.24065v1](https://arxiv.org/abs/2607.24065v1) | Variational Quantum Conditional Boltzmann Machines for Time-Series Forecasting: Architectures, Symmetric Hyperparameter Evaluation, and a Nonlinear Benchmark |
| 2026 | [2608.05373v1](https://arxiv.org/abs/2608.05373v1) | Velocity- and Regime-Aware Detection of Intraday Options Market Manipulation, with Explainable Attribution |
| 2026 | [2605.21009v1](https://arxiv.org/abs/2605.21009v1) | Wartime Controls, Political Connections, and the Pricing of Zaibatsu Rents in Japan, 1930-1943 |
| 2025 | [2503.23992v1](https://arxiv.org/abs/2503.23992v1) | A cost of capital approach to determining the LGD discount rate |
| 2025 | [2502.17044v1](https://arxiv.org/abs/2502.17044v1) | A data-driven econo-financial stress-testing framework to estimate the effect of supply chain networks on financial systemic risk |
| 2025 | [2512.16411v2](https://arxiv.org/abs/2512.16411v2) | Asymptotic and finite-sample distributions of one- and two-sample empirical relative entropy |
| 2025 | [2510.18903v4](https://arxiv.org/abs/2510.18903v4) | Centered-Innovation MA for Bayesian Dirichlet ARMA: Theoretical Equivalence and an Application to Bank-Asset Shares |
| 2025 | [2512.15738v1](https://arxiv.org/abs/2512.15738v1) | Hybrid Quantum-Classical Ensemble Learning for S\&P 500 Directional Prediction |
| 2025 | [2502.04097v3](https://arxiv.org/abs/2502.04097v3) | Impermanent loss and Loss-vs-Rebalancing II |
| 2025 | [2501.11648v1](https://arxiv.org/abs/2501.11648v1) | Mean-Field Limits for Nearly Unstable Hawkes Processes |
| 2025 | [2512.17225v2](https://arxiv.org/abs/2512.17225v2) | Modeling financial time series with $φ^{4}$ quantum field theory |
| 2025 | [2512.07886v1](https://arxiv.org/abs/2512.07886v1) | The Endogenous Constraint: Hysteresis, Stagflation, and the Structural Inhibition of Monetary Velocity in the Bitcoin Network (2016-2025) |
| 2025 | [2511.14408v1](https://arxiv.org/abs/2511.14408v1) | The Hidden Constant of Market Rhythms: How $1-1/e$ Defines Scaling in Intrinsic Time |
| 2025 | [2506.17244v1](https://arxiv.org/abs/2506.17244v1) | Transformers Beyond Order: A Chaos-Markov-Gaussian Framework for Short-Term Sentiment Forecasting of Any Financial OHLC timeseries Data |
| 2025 | [2512.12054v1](https://arxiv.org/abs/2512.12054v1) | Universal Dynamics of Financial Bubbles in Isolated Markets: Evidence from the Iranian Stock Market |
| 2024 | [2405.00051v1](https://arxiv.org/abs/2405.00051v1) | Arbitrage impact on the relationship between XRP price and correlation tensor spectra of transaction networks |
| 2024 | [2402.08071v2](https://arxiv.org/abs/2402.08071v2) | Contagion on Financial Networks: An Introduction |
| 2024 | [2404.00015v3](https://arxiv.org/abs/2404.00015v3) | Empowering Credit Scoring Systems with Quantum-Enhanced Machine Learning |
| 2024 | [2411.12543v1](https://arxiv.org/abs/2411.12543v1) | Germany's Tax Revenue and its Total Administrative Cost |
| 2024 | [2411.12013v2](https://arxiv.org/abs/2411.12013v2) | Neural and Time-Series Approaches for Pricing Weather Derivatives: Performance and Regime Adaptation Using Satellite Data |
| 2024 | [2403.00774v2](https://arxiv.org/abs/2403.00774v2) | Regional inflation analysis using social network data |
| 2023 | [2302.08911v1](https://arxiv.org/abs/2302.08911v1) | DSE Stock Price Prediction using Hidden Markov Model |
| 2023 | [2305.04865v1](https://arxiv.org/abs/2305.04865v1) | Estimating the impact of supply chain network contagion on financial stability |
| 2023 | [2307.14409v2](https://arxiv.org/abs/2307.14409v2) | Exploring the Bitcoin Mesoscale |
| 2023 | [2302.08897v1](https://arxiv.org/abs/2302.08897v1) | Forecasting the Turkish Lira Exchange Rates through Univariate Techniques: Can the Simple Models Outperform the Sophisticated Ones? |
| 2022 | [2207.13914v3](https://arxiv.org/abs/2207.13914v3) | Anatomy of a Stablecoin's failure: the Terra-Luna case |
| 2022 | [2205.06677v1](https://arxiv.org/abs/2205.06677v1) | Collective behavior of stock prices in the time of crisis as a response to the external stimulus |
| 2022 | [2206.06320v1](https://arxiv.org/abs/2206.06320v1) | Cryptocurrency Bubble Detection: A New Stock Market Dataset, Financial Task & Hyperbolic Models |
| 2022 | [2206.13751v4](https://arxiv.org/abs/2206.13751v4) | Estimating the Currency Composition of Foreign Exchange Reserves |
| 2022 | [2212.05304v1](https://arxiv.org/abs/2212.05304v1) | Estimation and Application of the Convergence Bounds for Nonlinear Markov Chains |
| 2022 | [2210.13667v2](https://arxiv.org/abs/2210.13667v2) | Experimental observations of fractal landscape dynamics in a dense emulsion |
| 2022 | [2211.00728v2](https://arxiv.org/abs/2211.00728v2) | Genuine multifractality in time series is due to temporal correlations |
| 2022 | [2203.15470v1](https://arxiv.org/abs/2203.15470v1) | Graph similarity learning for change-point detection in dynamic networks |
| 2022 | [2201.09790v1](https://arxiv.org/abs/2201.09790v1) | Linear Laws of Markov Chains with an Application for Anomaly Detection in Bitcoin Prices |
| 2022 | [2201.07214v1](https://arxiv.org/abs/2201.07214v1) | Opinion Dynamics in Financial Markets via Random Networks |
| 2022 | [2208.03456v1](https://arxiv.org/abs/2208.03456v1) | Recurrence measures and transitions in stock market dynamics |
| 2022 | [2208.07251v3](https://arxiv.org/abs/2208.07251v3) | Signature-based validation of real-world economic scenarios |
| 2022 | [2211.13002v1](https://arxiv.org/abs/2211.13002v1) | Simulation-based Forecasting for Intraday Power Markets: Modelling Fundamental Drivers for Location, Shape and Scale of the Price Distribution |
| 2022 | [2212.05369v1](https://arxiv.org/abs/2212.05369v1) | Time Series Analysis in American Stock Market Recovering in Post COVID-19 Pandemic Period |
| 2021 | [2102.04532v1](https://arxiv.org/abs/2102.04532v1) | Asymmetric Tsallis distributions for modelling financial market dynamics |
| 2021 | [2108.11755v1](https://arxiv.org/abs/2108.11755v1) | Market Crash Prediction Model for Markets in A Rational Bubble |
| 2021 | [2108.01243v3](https://arxiv.org/abs/2108.01243v3) | Some results on maximum likelihood from incomplete data: finite sample properties and improved M-estimator for resampling |
| 2021 | [2106.07354v1](https://arxiv.org/abs/2106.07354v1) | The relationship between the US broad money supply and US GDP for the time period 2001 to 2019 with that of the corresponding time series for US national property and stock market indices, using an information entropy methodology |
| 2021 | [2109.01214v1](https://arxiv.org/abs/2109.01214v1) | What drives bitcoin? An approach from continuous local transfer entropy and deep learning classification models |
| 2020 | [2002.05697v1](https://arxiv.org/abs/2002.05697v1) | Analysis of intra-day fluctuations in the Mexican financial market index |
| 2020 | [2003.06184v2](https://arxiv.org/abs/2003.06184v2) | Coronavirus and oil price crash |
| 2020 | [2002.06405v1](https://arxiv.org/abs/2002.06405v1) | Deep Learning for Asset Bubbles Detection |
| 2020 | [2001.01127v1](https://arxiv.org/abs/2001.01127v1) | Forecasting Bitcoin closing price series using linear regression and neural networks models |
| 2020 | [2005.03969v5](https://arxiv.org/abs/2005.03969v5) | Methods for forecasting the effect of exogenous risk on stock markets |
| 2020 | [2012.14297v1](https://arxiv.org/abs/2012.14297v1) | Simple approaches on how to discover promising strategies for efficient enterprise performance, at time of crisis in the case of SMEs : Voronoi clustering and outlier effects perspective |
| 2019 | [1905.04370v1](https://arxiv.org/abs/1905.04370v1) | A Three-state Opinion Formation Model for Financial Markets |
| 2019 | [1907.03370v1](https://arxiv.org/abs/1907.03370v1) | Artificial Intelligence Alter Egos: Who benefits from Robo-investing? |
| 2019 | [1904.12526v1](https://arxiv.org/abs/1904.12526v1) | Empirical facts characterizing banking crises: an analysis via binary time series |
| 2019 | [1902.10500v1](https://arxiv.org/abs/1902.10500v1) | Q-Gaussian diffusion in stock markets |
| 2019 | [1912.04015v2](https://arxiv.org/abs/1912.04015v2) | Sanction or Financial Crisis? An Artificial Neural Network-Based Approach to model the impact of oil price volatility on Stock and industry indices |
| 2019 | [1909.10801v1](https://arxiv.org/abs/1909.10801v1) | WATTNet: Learning to Trade FX via Hierarchical Spatio-Temporal Representation of Highly Multivariate Time Series |
| 2018 | [1808.04231v1](https://arxiv.org/abs/1808.04231v1) | GARCH(1,1) model of the financial market with the Minkowski metric |
| 2018 | [1807.09346v1](https://arxiv.org/abs/1807.09346v1) | Investigating the configurations in cross-shareholding: a joint copula-entropy approach |
| 2018 | [1806.03758v1](https://arxiv.org/abs/1806.03758v1) | On critical dynamics and thermodynamic efficiency of urban transformations |
| 2018 | [1805.11909v1](https://arxiv.org/abs/1805.11909v1) | Quantitative approach to multifractality induced by correlations and broad distribution of data |
| 2018 | [1804.00820v1](https://arxiv.org/abs/1804.00820v1) | Return Optimization Securities and Other Remarkable Structured Investment Products: Indicators of Future Outcomes for U.S. Treasuries? |
| 2018 | [1801.02205v1](https://arxiv.org/abs/1801.02205v1) | The Network of U.S. Mutual Fund Investments: Diversification, Similarity and Fragility throughout the Global Financial Crisis |
| 2018 | [1812.02433v1](https://arxiv.org/abs/1812.02433v1) | Using published bid/ask curves to error dress spot electricity price forecasts |
| 2017 | [1706.03246v2](https://arxiv.org/abs/1706.03246v2) | Aftershocks following crash of currency exchange rate: The case of RUB/USD in 2014 |
| 2017 | [1704.04442v1](https://arxiv.org/abs/1704.04442v1) | Crude oil market and geopolitical events: an analysis based on information-theory-based quantifiers |
| 2017 | [1707.07977v1](https://arxiv.org/abs/1707.07977v1) | Ether: Bitcoin's competitor or ally? |
| 2017 | [1707.07162v1](https://arxiv.org/abs/1707.07162v1) | Lagrange regularisation approach to compare nested data sets and determine objectively financial bubbles' inceptions |
| 2017 | [1705.02344v2](https://arxiv.org/abs/1705.02344v2) | Noisy independent component analysis of auto-correlated components |
| 2017 | [1709.04059v1](https://arxiv.org/abs/1709.04059v1) | Random walks and market efficiency in Chinese and Indian equity markets |
| 2017 | [1703.10832v2](https://arxiv.org/abs/1703.10832v2) | Social dynamics of financial networks |
| 2017 | [1707.04838v2](https://arxiv.org/abs/1707.04838v2) | Transitions between superstatistical regimes: validity, breakdown and applications |
| 2016 | [1610.00795v2](https://arxiv.org/abs/1610.00795v2) | A dynamic approach merging network theory and credit risk techniques to assess systemic risk in financial networks |
| 2016 | [1606.06829v1](https://arxiv.org/abs/1606.06829v1) | Brexit or Bremain ? Evidence from bubble analysis |
| 2016 | [1608.07796v1](https://arxiv.org/abs/1608.07796v1) | Causality and Correlations between BSE and NYSE indexes: A Janus Faced Relationship |
| 2016 | [1604.03996v2](https://arxiv.org/abs/1604.03996v2) | Evidence of Self-Organization in Time Series of Capital Markets |
| 2016 | [1605.04945v1](https://arxiv.org/abs/1605.04945v1) | Extended nonlinear feedback model for describing episodes of high inflation |
| 2016 | [1601.01753v2](https://arxiv.org/abs/1601.01753v2) | Geography and distance effect on financial dynamics in the Chinese stock market |
| 2016 | [1612.09189v1](https://arxiv.org/abs/1612.09189v1) | Global economic dynamics of the forthcoming years. A forecast |
| 2016 | [1610.00259v1](https://arxiv.org/abs/1610.00259v1) | Hysteresis and Duration Dependence of Financial Crises in the US: Evidence from 1871-2016 |
| 2016 | [1601.07707v1](https://arxiv.org/abs/1601.07707v1) | Micro-foundation using percolation theory of the finite-time singular behavior of the crash hazard rate in a class of rational expectation bubbles |
| 2016 | [1601.04341v1](https://arxiv.org/abs/1601.04341v1) | Negative oil price bubble is likely to burst in March - May 2016. A forecast on the basis of the law of log-periodical dynamics |
| 2016 | [1610.07287v1](https://arxiv.org/abs/1610.07287v1) | The asset price bubbles in emerging financial markets: a new statistical approach |
| 2016 | [1606.02871v1](https://arxiv.org/abs/1606.02871v1) | The study of Thai stock market across the 2008 financial crisis |
| 2016 | [1606.01218v1](https://arxiv.org/abs/1606.01218v1) | World Financial 2014-2016 Market Bubbles: Oil Negative - US Dollar Positive |
| 2015 | [1503.06926v1](https://arxiv.org/abs/1503.06926v1) | A study of co-movements between USA and Latin American stock markets: a cross-bicorrelations perspective |
| 2015 | [1510.00876v1](https://arxiv.org/abs/1510.00876v1) | Analysis of the particle transfer between two systems under unification |
| 2015 | [1503.05550v1](https://arxiv.org/abs/1503.05550v1) | Club Convergence of House Prices: Evidence from China's Ten Key Cities |
| 2015 | [1507.03278v1](https://arxiv.org/abs/1507.03278v1) | Contagion effects in the world network of economic activities |
| 2015 | [1501.04123v1](https://arxiv.org/abs/1501.04123v1) | Data manipulation detection via permutation information theory quantifiers |
| 2015 | [1507.04298v2](https://arxiv.org/abs/1507.04298v2) | Modelling Financial Markets by Self-Organized Criticality |
| 2015 | [1507.07214v10](https://arxiv.org/abs/1507.07214v10) | One trade at a time -- unraveling the Equity Premium Puzzle |
| 2014 | [1404.6637v2](https://arxiv.org/abs/1404.6637v2) | Braided and Knotted Stocks in the Stock Market: Anticipating the flash crashes |
| 2014 | [1412.2124v1](https://arxiv.org/abs/1412.2124v1) | Competition of Commodities for the Status of Money in an Agent-based Model |
| 2014 | [1403.1574v2](https://arxiv.org/abs/1403.1574v2) | Consentaneous agent-based and stochastic model of the financial markets |
| 2014 | [1409.8024v5](https://arxiv.org/abs/1409.8024v5) | Herding interactions as an opportunity to prevent extreme events in financial markets |
| 2014 | [1412.1293v1](https://arxiv.org/abs/1412.1293v1) | Skewness and kurtosis analysis for non-Gaussian distributions |
| 2013 | [1310.2446v3](https://arxiv.org/abs/1310.2446v3) | A statistical physics perspective on criticality in financial markets |
| 2013 | [1305.2655v1](https://arxiv.org/abs/1305.2655v1) | An Exactly Solvable Discrete Stochastic Process with Correlated Properties |
| 2013 | [1310.1634v2](https://arxiv.org/abs/1310.1634v2) | Cascades in real interbank markets |
| 2013 | [1309.2130v4](https://arxiv.org/abs/1309.2130v4) | The Interrupted Power Law and The Size of Shadow Banking |
| 2012 | [1204.6483v1](https://arxiv.org/abs/1204.6483v1) | Applications of statistical mechanics to economics: Entropic origin of the probability distributions of money, income, and energy consumption |
| 2012 | [1201.4841v2](https://arxiv.org/abs/1201.4841v2) | Econophysics of a religious cult: the Antoinists in Belgium [1920-2000] |
| 2012 | [1203.1313v2](https://arxiv.org/abs/1203.1313v2) | UPDATE February 2012 - The Food Crises: Predictive validation of a quantitative model of food prices including speculators and ethanol conversion |
| 2012 | [1209.6376v1](https://arxiv.org/abs/1209.6376v1) | UPDATE July 2012 / The Food Crises: The US Drought |
| 2011 | [1103.5978v1](https://arxiv.org/abs/1103.5978v1) | Financial Risks and the Pension Protection Fund: Can it Survive Them? |
| 2011 | [1102.2620v1](https://arxiv.org/abs/1102.2620v1) | Predicting economic market crises using measures of collective panic |
| 2011 | [1112.5711v1](https://arxiv.org/abs/1112.5711v1) | The topology of cross-border exposures: beyond the minimal spanning tree approach |
| 2010 | [1002.0609v1](https://arxiv.org/abs/1002.0609v1) | A new space-time model for volatility clustering in the financial market |
| 2010 | [1001.3176v1](https://arxiv.org/abs/1001.3176v1) | Analyzing the prices of the most expensive sheet iron all over the world: Modeling, prediction and regime change |
| 2010 | [1009.4835v2](https://arxiv.org/abs/1009.4835v2) | Financial LPPL Bubbles with Mean-Reverting Noise in the Frequency Domain |
| 2010 | [1005.2044v2](https://arxiv.org/abs/1005.2044v2) | Note on log-periodic description of 2008 financial crash |
| 2010 | [1006.2010v1](https://arxiv.org/abs/1006.2010v1) | Prediction accuracy and sloppiness of log-periodic functions |
| 2010 | [1007.1631v1](https://arxiv.org/abs/1007.1631v1) | Price dynamics in financial markets: a kinetic approach |
| 2010 | [1010.6026v1](https://arxiv.org/abs/1010.6026v1) | Statistical properties of derivatives: a journey in term structures |
| 2010 | [1005.5675v2](https://arxiv.org/abs/1005.5675v2) | The Financial Bubble Experiment: Advanced Diagnostics and Forecasts of Bubble Terminations Volume II-Master Document |
| 2010 | [1011.2882v2](https://arxiv.org/abs/1011.2882v2) | The Financial Bubble Experiment: Advanced Diagnostics and Forecasts of Bubble Terminations, Volume III |
| 2010 | [1009.5800v2](https://arxiv.org/abs/1009.5800v2) | Will the US Economy Recover in 2010? A Minimal Spanning Tree Study |
| 2009 | [0902.0075v2](https://arxiv.org/abs/0902.0075v2) | A k-generalized statistical mechanics approach to income analysis |
| 2009 | [0910.2447v1](https://arxiv.org/abs/0910.2447v1) | Activity Dependent Branching Ratios in Stocks, Solar X-ray Flux, and the Bak-Tang-Wiesenfeld Sandpile Model |
| 2009 | [0909.1007v2](https://arxiv.org/abs/0909.1007v2) | Bubble Diagnosis and Prediction of the 2005-2007 and 2008-2009 Chinese stock market bubbles |
| 2009 | [0909.1974v2](https://arxiv.org/abs/0909.1974v2) | Econophysics: Empirical facts and agent-based models |
| 2009 | [0909.2885v1](https://arxiv.org/abs/0909.2885v1) | Financial bubbles analysis with a cross-sectional estimator |
| 2009 | [0907.1827v1](https://arxiv.org/abs/0907.1827v1) | The Chinese Equity Bubble: Ready to Burst |
| 2009 | [0911.0454v4](https://arxiv.org/abs/0911.0454v4) | The Financial Bubble Experiment: advanced diagnostics and forecasts of bubble terminations |
| 2009 | [0909.0418v3](https://arxiv.org/abs/0909.0418v3) | World stock market: more sizeable trend reversal likely in February/March 2010 |
| 2008 | [0808.3360v1](https://arxiv.org/abs/0808.3360v1) | Criticality Characteristics of Current Oil Price Dynamics |
| 2008 | [0806.2989v2](https://arxiv.org/abs/0806.2989v2) | How to grow a bubble: A model of myopic adapting agents |
| 2007 | [physics/0701171v2](https://arxiv.org/abs/physics/0701171v2) | A case study of speculative financial bubbles in the South African stock market 2003-2006 |
| 2007 | [0704.0589v1](https://arxiv.org/abs/0704.0589v1) | Analysis of the real estate market in Las Vegas: Bubble, seasonal patterns, and prediction of the CSW indexes |
| 2007 | [physics/0701156v2](https://arxiv.org/abs/physics/0701156v2) | Structurally dynamic spin market networks |
| 2007 | [0712.3992v1](https://arxiv.org/abs/0712.3992v1) | Two Fractal Overlap Time Series: Earthquakes and Market Crashes |
| 2006 | [physics/0606012v1](https://arxiv.org/abs/physics/0606012v1) | Econophysics of Stock and Foreign Currency Exchange Markets |
| 2006 | [physics/0611281v2](https://arxiv.org/abs/physics/0611281v2) | Forecasting extreme events in collective dynamics: an analytic signal approach to detecting discrete scale invariance |
| 2006 | [physics/0605179v1](https://arxiv.org/abs/physics/0605179v1) | Microeconomic co-evolution model for financial technical analysis signals |
| 2006 | [physics/0607167v1](https://arxiv.org/abs/physics/0607167v1) | Non-extensive Behavior of a Stock Market Index at Microscopic Time Scales |
| 2006 | [physics/0606005v1](https://arxiv.org/abs/physics/0606005v1) | On the gap between an empirical distribution and an exponential distribution of waiting times for price changes in a financial market |
| 2006 | [physics/0611159v3](https://arxiv.org/abs/physics/0611159v3) | Phase transition in the globalization of trade |
| 2006 | [cond-mat/0605623v2](https://arxiv.org/abs/cond-mat/0605623v2) | Statistical mechanics of combinatorial auctions |
| 2005 | [physics/0505079v1](https://arxiv.org/abs/physics/0505079v1) | Fundamental Factors versus Herding in the 2000-2005 US Stock Market and Prediction |
| 2005 | [cond-mat/0501513v4](https://arxiv.org/abs/cond-mat/0501513v4) | Self-Similar Log-Periodic Structures in Western Stock Markets from 2000 |
| 2005 | [physics/0506098v1](https://arxiv.org/abs/physics/0506098v1) | Stock mechanics: predicting recession in S&P500, DJIA, and NASDAQ |
| 2005 | [physics/0510047v1](https://arxiv.org/abs/physics/0510047v1) | Time series of stock price and of two fractal overlap: Anticipating market crashes? |
| 2004 | [cond-mat/0405172v1](https://arxiv.org/abs/cond-mat/0405172v1) | Herd Behaviors in Financial Markets |
| 2004 | [nlin/0412038v2](https://arxiv.org/abs/nlin/0412038v2) | Multifractal Behavior of the Korean Stock-market Index KOSPI |
| 2004 | [cond-mat/0401210v1](https://arxiv.org/abs/cond-mat/0401210v1) | Origin of Crashes in 3 US stock markets: Shocks and Bubbles |
| 2004 | [cond-mat/0408625v1](https://arxiv.org/abs/cond-mat/0408625v1) | Phase Transition of Dynamical Herd Behaviors in Financial Markets |
| 2003 | [cond-mat/0312404v2](https://arxiv.org/abs/cond-mat/0312404v2) | A mechanism leading bubbles to crashes: the case of Japan's land markets |
| 2003 | [cond-mat/0307323v3](https://arxiv.org/abs/cond-mat/0307323v3) | Another type of log-periodic oscillations on Polish stock market? |
| 2003 | [cond-mat/0312149v1](https://arxiv.org/abs/cond-mat/0312149v1) | Antibubble and Prediction of China's stock market and Real-Estate |
| 2003 | [cond-mat/0312658v1](https://arxiv.org/abs/cond-mat/0312658v1) | Causal Slaving of the U.S. Treasury Bond Yield Antibubble by the Stock Market Antibubble of August 2000 |
| 2003 | [cond-mat/0301543v1](https://arxiv.org/abs/cond-mat/0301543v1) | Critical Market Crashes |
| 2003 | [cond-mat/0311089v1](https://arxiv.org/abs/cond-mat/0311089v1) | Fearless versus Fearful Speculative Financial Bubbles |
| 2003 | [physics/0301007v1](https://arxiv.org/abs/physics/0301007v1) | Finite-Time Singularity Signature of Hyperinflation |
| 2003 | [cond-mat/0304143v2](https://arxiv.org/abs/cond-mat/0304143v2) | Herd Behavior of Returns in the Futures Exchange Market |
| 2003 | [cond-mat/0304451v1](https://arxiv.org/abs/cond-mat/0304451v1) | Herd Behaviors in the Stock and Foreign Exchange Markets |
| 2003 | [cond-mat/0304601v3](https://arxiv.org/abs/cond-mat/0304601v3) | Predictability of large future changes in major financial indices |
| 2003 | [cond-mat/0308013v1](https://arxiv.org/abs/cond-mat/0308013v1) | Scale-Dependent Price Fluctuations for the Indian Stock Market |
| 2003 | [cond-mat/0302507v3](https://arxiv.org/abs/cond-mat/0302507v3) | Significance of log-periodic signatures in cumulative noise |
| 2003 | [cond-mat/0310092v2](https://arxiv.org/abs/cond-mat/0310092v2) | Testing the Stability of the 2000-2003 US Stock Market "Antibubble" |
| 2003 | [cond-mat/0305004v1](https://arxiv.org/abs/cond-mat/0305004v1) | The US 2000-2003 Market Descent: Clarifications |
| 2002 | [cond-mat/0209685v1](https://arxiv.org/abs/cond-mat/0209685v1) | Dynamics of a financial market index after a crash |
| 2002 | [cond-mat/0206047v1](https://arxiv.org/abs/cond-mat/0206047v1) | Endogeneous Versus Exogeneous Shocks in Systems with Memory |
| 2002 | [cond-mat/0212010v2](https://arxiv.org/abs/cond-mat/0212010v2) | Evidence of a Worldwide Stock Market Log-Periodic Anti-Bubble Since Mid-2000 |
| 2002 | [cond-mat/0209591v2](https://arxiv.org/abs/cond-mat/0209591v2) | Log-periodic self-similarity: an emerging financial law? |
| 2002 | [cond-mat/0205531v1](https://arxiv.org/abs/cond-mat/0205531v1) | Non-Parametric Analyses of Log-Periodic Precursors to Financial Crashes |
| 2002 | [cond-mat/0204295v1](https://arxiv.org/abs/cond-mat/0204295v1) | Predicting critical crashes? A new restriction for the free variables |
| 2002 | [cond-mat/0208574v1](https://arxiv.org/abs/cond-mat/0208574v1) | Statistical properties of the Jakarta and Kuala Lumpur stock exchange indices before and after crash |
| 2002 | [cond-mat/0207227v1](https://arxiv.org/abs/cond-mat/0207227v1) | Stock Market Scale by Artificial Insymmetrised Patterns |
| 2002 | [cond-mat/0209065v1](https://arxiv.org/abs/cond-mat/0209065v1) | The US 2000-2002 Market Descent: How Much Longer and Deeper? |
| 2001 | [cond-mat/0109410v1](https://arxiv.org/abs/cond-mat/0109410v1) | Imitation and contrarian behavior: hyperbolic bubbles, crashes and chaos |
| 2001 | [cond-mat/0110124v2](https://arxiv.org/abs/cond-mat/0110124v2) | Nucleation of Market Shocks in Sornette-Ide model |
| 2001 | [cond-mat/0111257v2](https://arxiv.org/abs/cond-mat/0111257v2) | Power law relaxation in a complex system: Omori law after a financial market crash |
| 2001 | [cond-mat/0106520v1](https://arxiv.org/abs/cond-mat/0106520v1) | Significance of log-periodic precursors to financial crashes |
| 2001 | [cond-mat/0110273v1](https://arxiv.org/abs/cond-mat/0110273v1) | Stochastic Multiplicative Processes for Financial Markets |
| 2001 | [cond-mat/0104362v1](https://arxiv.org/abs/cond-mat/0104362v1) | Variety of Stock Returns in Normal and Extreme Market Days: The August 1998 Crisis |
| 2000 | [cond-mat/0009401v1](https://arxiv.org/abs/cond-mat/0009401v1) | Empirical properties of the variety of a financial portfolio and the single-index model |
| 2000 | [cond-mat/0010222v1](https://arxiv.org/abs/cond-mat/0010222v1) | Power Laws are Boltzmann Laws in Disguise |
| 2000 | [cond-mat/0008026v1](https://arxiv.org/abs/cond-mat/0008026v1) | Power, Levy, Exponential and Gaussian Regimes in Autocatalytic Financial Systems |
| 2000 | [cond-mat/0004001v1](https://arxiv.org/abs/cond-mat/0004001v1) | Stock Market Speculation: Spontaneous Symmetry Breaking of Economic Valuation |
| 2000 | [cond-mat/0002438v1](https://arxiv.org/abs/cond-mat/0002438v1) | Symmetry alteration of ensemble return distribution in crash and rally days of financial markets |
| 2000 | [cond-mat/0004263v4](https://arxiv.org/abs/cond-mat/0004263v4) | The Nasdaq crash of April 2000: Yet another example of log-periodicity in a speculative bubble ending in a crash |
| 2000 | [cond-mat/0006065v1](https://arxiv.org/abs/cond-mat/0006065v1) | Variety and Volatility in Financial Markets |
| 1999 | [cond-mat/9901035v1](https://arxiv.org/abs/cond-mat/9901035v1) | Critical Crashes |
| 1999 | [cond-mat/9903142v1](https://arxiv.org/abs/cond-mat/9903142v1) | Critical Crashes? |
| 1999 | [cond-mat/9901268v1](https://arxiv.org/abs/cond-mat/9901268v1) | Financial ``Anti-Bubbles'': Log-Periodicity in Gold and Nikkei collapses |
| 1999 | [cond-mat/9909439v1](https://arxiv.org/abs/cond-mat/9909439v1) | Market Fluctuations: multiplicative and percolation models, size effects and predictions |
| 1999 | [cond-mat/9910141v1](https://arxiv.org/abs/cond-mat/9910141v1) | On Rational Bubbles and Fat Tails |
| 1998 | [cond-mat/9804111v1](https://arxiv.org/abs/cond-mat/9804111v1) | Are Financial Crashes Predictable? |
| 1998 | [cond-mat/9810092v1](https://arxiv.org/abs/cond-mat/9810092v1) | Booms and Crashes in Self-Similar Markets |
| 1997 | [cond-mat/9710336v2](https://arxiv.org/abs/cond-mat/9710336v2) | Renormalization Group Analysis of October Market Crashes |

