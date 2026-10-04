# Evidence pack — Correlation, Networks & Dependence (`correlation-networks`)

Annotated sweep rows for this category: **1053** (high 96 · med 609 · low 348).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (96)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2608.30446v1](https://arxiv.org/abs/2608.30446v1) | Adapts a rotation-invariant neural covariance estimator to indefinite pairwise-complete correlation matrices via mask-aware moments and a GRU; reduces annualized five-day volatility ~20% and raises Sharpe ~40% on 1,500 US equities (2000-2025). | strategies/covariance_models.py |
| 2026 | [2605.06818v1](https://arxiv.org/abs/2605.06818v1) | Bayesian low-rank factor model with dynamic shrinkage prior and multivariate factor stochastic volatility estimates time-varying correlation matrices; proves posterior contraction; total-correlation scalar summary. | strategies/covariance_models.py |
| 2026 | [2603.17463v2](https://arxiv.org/abs/2603.17463v2) | Forecast reconciliation combining univariate and multivariate portfolio-variance forecasts beats a standard multivariate GARCH approach, especially under misspecification, though noisy covariance proxies limit model discrimination. | `strategies/covariance_models.py` |
| 2026 | [2607.03082v1](https://arxiv.org/abs/2607.03082v1) | Evaluates buy-and-hold, mean-variance, CVaR and tangency portfolios on 30 actively managed ETFs (2020-2025): tangency rivals buy-and-hold, CVaR controls downside, but tail exposure persists after aggregation. | strategies/portfolio_optimizer.py |
| 2026 | [2603.20237v2](https://arxiv.org/abs/2603.20237v2) | Formalizes temporal coverage bias in calendar-aligned panels and proposes coverage-aware structuring via instrument observation windows and an availability matrix; Dhaka Stock Exchange results show substantial distortion from naive alignment. | `strategies/coverage_window.py` |
| 2026 | [2608.20020v1](https://arxiv.org/abs/2608.20020v1) | Measures co-movement reconfiguration as mean squared sine of principal angles between S&P 500 subdominant eigenspaces; it is priced in the variance risk premium (t=5.40), with only the persistent component compensated. | strategies/eigen_rotation.py |
| 2026 | [2608.10788v1](https://arxiv.org/abs/2608.10788v1) | Applies the Triadic Stress Index to correlation networks across five markets; it beats the Absorption Ratio by 0.273 out-of-sample F1, emits the cleanest alarms, and gives parameter-free per-node attribution. | strategies/triadic_stress.py |
| 2025 | [2509.19663v3](https://arxiv.org/abs/2509.19663v3) | R/S, DFA, multifractal and ARFIMA-FIGARCH tests find long memory in conditional volatility (not mean returns) across equities, commodities and energy; deep generative models struggle to reproduce it. | `strategies/long_memory.py` |
| 2025 | [2512.02037v1](https://arxiv.org/abs/2512.02037v1) | Adapts Avellaneda–Lee pairs trading to Polish equities, replicating assets via PCA, ETFs and LSTM factors; 2017-2019 PCA earns ~20% cumulative, Sharpe 2.63; only ETF approach survives 2020. | `strategies/mean_reversion.py` |
| 2025 | [2508.01880v3](https://arxiv.org/abs/2508.01880v3) | Time-varying factor-augmented volatility framework extracts dynamic cross-sectional factors from realized volatilities and feeds statistical and AI models; improves 1-day and 7-day forecasts for tech equities and crypto, and a pairs-trading strategy earns superior risk-adjusted returns. | `strategies/volatility_models.py` |
| 2025 | [2503.02680v1](https://arxiv.org/abs/2503.02680v1) | Trains one signature-enhanced transformer (GFT-Sig) globally across 80 crypto pairs for VWAP execution; the globally-fitted model beats asset-specific models on absolute and quadratic VWAP loss and generalizes to out-of-sample assets. | `strategies/execution_schedule.py` |
| 2024 | [2401.10370v1](https://arxiv.org/abs/2401.10370v1) | Comparative review of deep generative models (CGAN, CWGAN, diffusion, signature) for financial time-series generation, applied to Historical-Simulation VaR. | `strategies/book_risk.py` |
| 2024 | [2411.08382v1](https://arxiv.org/abs/2411.08382v1) | Hybrid VAR plus feedforward neural network predicts order-flow imbalance, feeding VAR residuals to the FNN and estimating buy/sell intensity; beats standalone FNN and VAR on Binance and synthetic data. | `strategies/orderflow.py` |
| 2024 | [2401.06249v4](https://arxiv.org/abs/2401.06249v4) | SpotV2Net graph attention network forecasts intraday spot volatility, using nonparametric Fourier vol-of-vol and co-vol-of-vol estimates as edge features; gains on Dow components. | `strategies/volatility_models.py` |
| 2024 | [2401.03443v1](https://arxiv.org/abs/2401.03443v1) | Structured factor copulas model joint and conditional bank distress from CDS; systematic contagion via latent global plus region-specific factors prevails. | `strategies/tail_risk.py` |
| 2023 | [2310.14536v1](https://arxiv.org/abs/2310.14536v1) | Co-trains a normalizing-flow RV transformation with the prediction model under a maximum-likelihood objective for skewed, fat-tailed realized volatility. | `strategies/volatility_models.py` |
| 2023 | [2306.12446v2](https://arxiv.org/abs/2306.12446v2) | Compares deep forecasters (MLP, RNN, TCN, Temporal Fusion Transformer) with GARCH for multivariate volatility; TFT wins in most of five assets. | `strategies/volatility_models.py` |
| 2023 | [2305.06961v2](https://arxiv.org/abs/2305.06961v2) | Copula-based pairs trading on cointegrated cryptocurrency pairs using linear/non-linear cointegration; outperforms buy-and-hold on profitability and risk-adjusted returns. | `strategies/mean_reversion.py` |
| 2023 | [2312.02081v1](https://arxiv.org/abs/2312.02081v1) | Copula-based deviation measure for cointegrated asset pairs offers more stable and informative dependence assessment than correlation coefficients. | `strategies/mean_reversion.py` |
| 2023 | [2310.16849v1](https://arxiv.org/abs/2310.16849v1) | Random-matrix-theory analysis of global agricultural futures correlation: largest eigenvalue is a market mode, deviating eigenvalues identify groups. | `strategies/covariance_models.py` |
| 2023 | [2306.05479v1](https://arxiv.org/abs/2306.05479v1) | Convolutional-Transformer survival model maps time-varying limit-order-book features to fill-time distributions, beating survival baselines on proper scoring rules. | `strategies/backtest_models.py` |
| 2023 | [2305.12632v2](https://arxiv.org/abs/2305.12632v2) | Temporal correlation deforms the Marchenko-Pastur eigenvalue law: longer tail and higher peak, power-decay correlation causing a phase transition. | `strategies/covariance_models.py` |
| 2023 | [2310.18658v1](https://arxiv.org/abs/2310.18658v1) | Two-step nonparametric CoVaR estimation using order statistics for unobservable multivariate quantiles, measuring node risk in financial networks. | `strategies/book_risk.py` |
| 2023 | [2306.02136v3](https://arxiv.org/abs/2306.02136v3) | FinBERT sentiment plus LSTM predicts stock trends and beats BERT, standalone LSTM and ARIMA; sentiment significantly improves accuracy. | `strategies/sentiment_research.py` |
| 2023 | [2311.06256v1](https://arxiv.org/abs/2311.06256v1) | SV-PF-RNN hybrid of neural network and particle filter estimates true stochastic volatility from noisy data, improving on a basic particle filter. | `strategies/volatility_models.py` |
| 2023 | [2308.01419v1](https://arxiv.org/abs/2308.01419v1) | Customized graph neural networks forecast multivariate realized volatility with spillovers; nonlinear spillovers help up to one week, multi-hop alone does not. | `strategies/volatility_models.py` |
| 2023 | [2308.05564v4](https://arxiv.org/abs/2308.05564v4) | Large skew-t copula models capture asymmetric extreme tail dependence in intraday equity returns; Bayesian variational inference makes high-dimensional estimation fast. | `strategies/covariance_models.py` |
| 2023 | [2310.09622v1](https://arxiv.org/abs/2310.09622v1) | Bivariate jump-diffusion model of Bitcoin price driven by Google-search sentiment; closed-form price and neural-network option valuation. | `strategies/options_math.py` |
| 2023 | [2304.09947v2](https://arxiv.org/abs/2304.09947v2) | Gradient-free online ensemble reweights 16 models by out-of-sample R-squared; applied to sector rotation, finding sector returns more predictable than stock returns. | `strategies/rotation.py` |
| 2023 | [2304.14098v2](https://arxiv.org/abs/2304.14098v2) | Optimal covariance cleaning for heavy tails; Frobenius-norm minimization equals information-loss minimization for Gaussian but deviates for Student-t in finite samples. | `strategies/covariance_models.py` |
| 2023 | [2306.05667v1](https://arxiv.org/abs/2306.05667v1) | Combines Random-Matrix-Theory covariance cleaning with Nested Clustered Optimization (spectral clustering + MST) to curb Markowitz instability on Mexican equities. | `strategies/hierarchical_risk_parity.py` |
| 2023 | [2308.08550v1](https://arxiv.org/abs/2308.08550v1) | Extended LSTMs with per-dimension flexible timescales predict asset volatility better than rough volatility by ~20% and halve training epochs. | `strategies/volatility_models.py` |
| 2023 | [2304.11883v1](https://arxiv.org/abs/2304.11883v1) | Recurrent neural network estimates Hawkes model parameters on high-frequency data far faster than MLE with comparable accuracy, enabling real-time volatility. | `strategies/orderflow.py` |
| 2023 | [2307.09137v1](https://arxiv.org/abs/2307.09137v1) | Two-stage DCC-EGARCH with VaR and Cornish-Fisher CFVaR measures crypto/stock spillovers during COVID; finds significant short- and long-term effects and volatility surges after positive news. | `strategies/book_risk.py` |
| 2023 | [2310.16850v1](https://arxiv.org/abs/2310.16850v1) | Copula-CoVaR with ARMA-GARCH-skewed-t finds agricultural futures-spot tail dependence and extreme risk spillovers intensified by the Russia-Ukraine conflict. | `strategies/tail_risk.py` |
| 2022 | [2203.13740v1](https://arxiv.org/abs/2203.13740v1) | Derives generalized precision matrices valid beyond Gaussianity using the local dependence function, focusing on multivariate t-Student; minimum-variance portfolios using them show significantly lower out-of-sample variance. | `strategies/covariance_models.py` |
| 2022 | [2203.12460v1](https://arxiv.org/abs/2203.12460v1) | Studies a decade of ~100k earnings-call transcripts from 6,300 firms; a semantic GNN reliably predicts price moves across five sectors, semantics beat sales/EPS, while pre-earnings analyst ratings correlate weakly. | `strategies/text_factors.py` |
| 2022 | [2203.03179v4](https://arxiv.org/abs/2203.03179v4) | Deep neural networks identify robust statistical-arbitrage strategies under model ambiguity without cointegration pairs; empirically profitable in up to 50 dimensions, during crises and when pairs break. | `strategies/mean_reversion.py` |
| 2022 | [2207.10539v1](https://arxiv.org/abs/2207.10539v1) | LSTM value-at-risk estimator matches GARCH on simulated data but beats all estimators on real data by exception rate and mean quantile score. | strategies/book_risk.py |
| 2022 | [2212.14670v1](https://arxiv.org/abs/2212.14670v1) | Hierarchical RL Macro-Meta-Micro Trader (with LSTM volume forecast) optimizes VWAP execution and saves 1.16 bp average cost over the best baseline on Shanghai stocks. | strategies/execution_schedule.py |
| 2022 | [2202.11285v1](https://arxiv.org/abs/2202.11285v1) | Neural GARCH makes GARCH/BEKK coefficients time-varying via a recurrent network trained with stochastic gradient variational Bayes; the Student-t variant consistently outperforms across univariate and multivariate series. | `strategies/volatility_models.py` |
| 2022 | [2203.12457v1](https://arxiv.org/abs/2203.12457v1) | Engineers technical, order-flow and order-book features fed to a Tabnet network predicting short-term silver futures direction on the Shanghai Futures Exchange, reaching 0.601 accuracy. | `strategies/orderflow.py` |
| 2022 | [2202.08962v2](https://arxiv.org/abs/2202.08962v2) | Pools cross-stock intraday data with a market-volatility proxy to forecast realized volatility; neural networks beat linear and tree models, generalize to unseen stocks, and exploit time-of-day effects. | `strategies/long_memory.py` |
| 2021 | [2106.07177v2](https://arxiv.org/abs/2106.07177v2) | Predicts the implied volatility surface with a two-step framework: extract features (PCA, VAE, or surface sampling), forecast with LSTM, then reconstruct via arbitrage-constrained DNN; sampling/VAE outperform classical methods on S&P500 data. | `strategies/options_surface.py` |
| 2021 | [2101.10942v2](https://arxiv.org/abs/2101.10942v2) | Shows prediction-error-based evaluation of neural stock predictors is statistically flawed; the absolute-value constraint distorts reported performance. | `strategies/evaluate.py` |
| 2021 | [2111.13109v3](https://arxiv.org/abs/2111.13109v3) | Proposes covariance-matrix cleaning using eigenvalues independent of inputs that encode long-term averaging, targeting nonstationary systems; outperforms stationary-optimal filters on real and synthetic data for portfolio variance minimization. | `strategies/covariance_models.py` |
| 2021 | [2107.07206v2](https://arxiv.org/abs/2107.07206v2) | Compares logistic regression and feedforward neural networks for credit scoring; temporal repeated-measure features boost accuracy, and a new Stein-unbiased-risk-estimate (SURE) calibration stacked with Platt improves predicted-probability calibration. | `strategies/calibration.py` |
| 2021 | [2103.05921v1](https://arxiv.org/abs/2103.05921v1) | Knockoff procedure controls false-discovery rate in financial factor selection; applied to fund replication and explanatory/prediction networks. | `strategies/factors.py` |
| 2021 | [2109.10946v1](https://arxiv.org/abs/2109.10946v1) | Studies Copula-GARCH VaR/ES forecast model risk, isolating marginals versus copula; risk is economically large, crisis-heavy and almost entirely copula-driven, and model confidence sets reduce it. | `strategies/volatility_models.py` |
| 2021 | [2112.07521v2](https://arxiv.org/abs/2112.07521v2) | Shows non-linear shrinkage of the return covariance matrix is not optimal for portfolio optimization under nonstationary dependence, derives the correct optimal target, and quantifies on historical data how much NLS can be improved. | `strategies/portfolio_optimizer.py` |
| 2021 | [2102.07372v2](https://arxiv.org/abs/2102.07372v2) | REST relational event-driven graph neural model forecasts stock trends using news events and inter-stock relations. | `strategies/news_score.py` |
| 2021 | [2103.10989v1](https://arxiv.org/abs/2103.10989v1) | Mixed Bernstein (generalized Archimedean) copula derives aggregate-risk density and closed-form TVaR and TVaR-based capital allocations. | `strategies/book_risk.py` |
| 2021 | [2103.01670v1](https://arxiv.org/abs/2103.01670v1) | LOB recreation model predicts the limit order book from TAQ history using an ODE recurrent neural network. | `strategies/orderflow.py` |
| 2020 | [2012.02395v1](https://arxiv.org/abs/2012.02395v1) | New parametrization of correlation/covariance matrices by an unrestricted vector guaranteeing positive definiteness, with reconstruction algorithm. | `strategies/covariance_models.py` |
| 2020 | [2009.10764v1](https://arxiv.org/abs/2009.10764v1) | CoVaR estimated with GJR-GARCH volatility clustering, heavy tails, negative skew and copula dependence; quantifies systemic risk. | `strategies/book_risk.py` |
| 2019 | [1910.01491v1](https://arxiv.org/abs/1910.01491v1) | RIC-NN: nonlinear multi-factor deep net with rank-IC stopping criterion and transfer learning across regions; beats off-the-shelf ML and major equity funds over 14 years on MSCI stocks. | strategies/signal_analysis.py |
| 2019 | [1904.00745v6](https://arxiv.org/abs/1904.00745v6) | Deep neural asset-pricing model uses the no-arbitrage condition as criterion and adversarial test-asset construction; outperforms benchmarks out-of-sample on Sharpe ratio, explained variation and pricing errors. | `strategies/factors.py` |
| 2019 | [1909.04497v2](https://arxiv.org/abs/1909.04497v2) | Equity2Vec graph component captures evolving cross-sectional interactions and fuses technical, news and cross-sectional signals end-to-end, outperforming SOTA approaches and monetizing signals. | strategies/cross_section.py |
| 2018 | [1811.11618v2](https://arxiv.org/abs/1811.11618v2) | Revisits Kalman filtering via probabilistic graphical models, links it to HMMs, adds extended-Kalman inference algorithms and CMA-ES estimation, and shows superior trend-following detection. | `strategies/statistical_kalman.py` |
| 2016 | [1610.08104v1](https://arxiv.org/abs/1610.08104v1) | RMT review covering Marchenko-Pastur, free probability and rotationally invariant estimators for cleaning large correlation matrices, with financial applications. | `strategies/covariance_models.py` |
| 2015 | [1511.07945v1](https://arxiv.org/abs/1511.07945v1) | Neighbor-Net correlation clustering with circular ordering on 126 Shanghai A shares reduces diversified-portfolio risk versus random or industry grouping during market increases. | `strategies/hierarchical_risk_parity.py` |
| 2015 | [1507.01729v4](https://arxiv.org/abs/1507.01729v4) | Spectral variance-decomposition framework measures short/medium/long-frequency volatility connectedness; high-frequency connectedness marks calm rapid information processing. | `strategies/tail_risk.py` |
| 2015 | [1510.06946v2](https://arxiv.org/abs/1510.06946v2) | Introduces quantile coherency in the frequency domain to capture general nonlinear dependence; empirical application sharpens tail-risk measurement of stock returns. | `strategies/tail_risk.py` |
| 2014 | [1406.0437v2](https://arxiv.org/abs/1406.0437v2) | High-dimensional global minimum variance portfolio via random-matrix shrinkage, optimal in out-of-sample variance under weak return assumptions. | strategies/portfolio_optimizer.py |
| 2013 | [1308.2608v2](https://arxiv.org/abs/1308.2608v2) | Optimal linear shrinkage covariance estimator in high dimensions with distribution-free asymptotic shrinkage intensities minimizing Frobenius loss. | strategies/covariance_models.py |
| 2013 | [1308.0931v3](https://arxiv.org/abs/1308.0931v3) | Optimal linear shrinkage estimator for the high-dimensional precision matrix, distribution-free and almost surely minimizing Frobenius loss. | strategies/covariance_models.py |
| 2013 | [1302.6305v1](https://arxiv.org/abs/1302.6305v1) | RMT on global indices and Korean local indices before/during/after 2008 finds a market mode in the top eigenvector and sign flips in the second across crisis phases, with quick recovery. | `strategies/eigen_rotation.py` |
| 2012 | [1203.6228v2](https://arxiv.org/abs/1203.6228v2) | General eigenvector-dynamics theory recasts subspace stability via overlap singular values and a fidelity distance, with explicit Gaussian-orthogonal spectra and covariance-matrix risk-control application. | `strategies/eigen_rotation.py` |
| 2012 | [1210.6321v4](https://arxiv.org/abs/1210.6321v4) | Topic modeling plus regularized regressions on 24M news records and 206 S&P stocks shows news flow explains abnormally large trading volumes, removing apparent "excess trading". | `strategies/news_relevance.py` |
| 2012 | [1210.2043v1](https://arxiv.org/abs/1210.2043v1) | Nonparametric Bernstein copulas as pair-copulas in vine models remove parametric family selection and beat AIC-calibrated parametric vines on simulated and financial data. | `strategies/covariance_models.py` |
| 2011 | [1111.1113v2](https://arxiv.org/abs/1111.1113v2) | Rigorous copula-based hierarchical risk aggregation yields exact diversification benefits for Gaussian (and LogNormal) trees, showing thin trees diversify better than fat trees. | `strategies/hierarchical_risk_parity.py` |
| 2011 | [1106.3921v2](https://arxiv.org/abs/1106.3921v2) | Screen-cluster-estimate (SCE) approach: hard-threshold estimation of large spatial covariance matrices for m-dependent β-mixing panels, then variable clustering into semiparametric models; applied to CPI panels. | `strategies/covariance_models.py` |
| 2011 | [1108.4258v1](https://arxiv.org/abs/1108.4258v1) | Framework for stability of the subspace spanned by P eigenvectors under perturbation, using overlap-matrix singular values to define a "fidelity" distance; applied to correlation-matrix risk control. | `strategies/eigen_rotation.py` |
| 2011 | [1102.2240v1](https://arxiv.org/abs/1102.2240v1) | Modified time-lag random matrix theory on 48 world indices finds long-range power-law cross-correlations in absolute returns that decay slowly; a PCA global factor model explains much of it. | strategies/covariance_models.py |
| 2011 | [1110.4784v3](https://arxiv.org/abs/1110.4784v3) | Web search query volumes for NASDAQ-100 stocks correlate with and anticipate trading-volume peaks by one day or more, emerging from uncoordinated collective user activity. | `strategies/sentiment.py` |
| 2009 | [0909.1383v3](https://arxiv.org/abs/0909.1383v3) | Finds residual noise bands in stock-return correlation matrices form non-mixing subbands; builds generalized random-matrix market models with heavy tails and exposes a stationary risk-estimation bias in conventional eigenvalue cleaning. | strategies/covariance_models.py |
| 2009 | [0902.3836v1](https://arxiv.org/abs/0902.3836v1) | Markowitz-diversified portfolio weights in Korean and Japanese markets: stronger market-property influence lowers diversification, and RMT correlation control improves portfolio management. | `strategies/portfolio_optimizer.py` |
| 2009 | [0903.1525v1](https://arxiv.org/abs/0903.1525v1) | Studies large empirical covariance/correlation matrices (size 54-330): spectra are static except the top few eigenvalues, which carry the distinct dynamics. | `strategies/covariance_models.py` |
| 2009 | [0906.5249v1](https://arxiv.org/abs/0906.5249v1) | Applies random-matrix theory to financial covariance matrices; smallest eigenvalues/spacings match Tracy-Widom and Wigner surmise robustly under reshuffling, supporting RMT cleaning for portfolio selection. | strategies/covariance_models.py |
| 2008 | [0809.4615v1](https://arxiv.org/abs/0809.4615v1) | Reviews correlation-matrix filtering via hierarchical trees, correlation networks and hierarchically nested factor models for portfolio optimization. | `strategies/hierarchical_risk_parity.py` |
| 2007 | [0710.0576v1](https://arxiv.org/abs/0710.0576v1) | Compares Random-Matrix-Theory and shrinkage filtering of large correlation matrices via Kullback-Leibler distance, measuring recovery of the underlying correlation matrix. | `strategies/covariance_models.py` |
| 2006 | [physics/0601166v3](https://arxiv.org/abs/physics/0601166v3) | SVD with the Kaiser-Guttman stopping rule estimates the effective dimensionality (number of independent bets) of a return correlation matrix; South African market breadth is far lower than anticipated. | `strategies/portfolio_optimizer.py` |
| 2005 | [physics/0507006v1](https://arxiv.org/abs/physics/0507006v1) | Clustering algorithms filter correlation-matrix uncertainty in portfolio optimization, improving the predicted-to-realized risk ratio across wide ranges of N and T (bootstrap analysis). | `strategies/portfolio_optimizer.py` |
| 2005 | [physics/0507111v1](https://arxiv.org/abs/physics/0507111v1) | RMT correlation-cleaning for portfolio optimization: generalizes Marchenko-Pastur to exponential-moving-average empirical correlation matrices and models the market eigenvalue as an Ornstein-Uhlenbeck process on the unit sphere. | `strategies/covariance_models.py` |
| 2005 | [physics/0509235v1](https://arxiv.org/abs/physics/0509235v1) | Applies random-matrix filtering to noisy empirical covariance matrices in a controlled simulation, showing filtered matrices improve portfolio optimization over naive use. | `strategies/covariance_models.py` |
| 2004 | [cond-mat/0402573v1](https://arxiv.org/abs/cond-mat/0402573v1) | Exponentially-weighted RMT-filtered covariance estimator (with analytic spectrum) beats EWMA and uniform RMT filtering in portfolio optimization. | strategies/covariance_models.py |
| 2004 | [cond-mat/0401300v1](https://arxiv.org/abs/cond-mat/0401300v1) | Correlation-based equity networks extract economic information from noisy matrices and can falsify market models by topological comparison. | strategies/covariance_models.py |
| 2004 | [cond-mat/0403177v1](https://arxiv.org/abs/cond-mat/0403177v1) | RMT-based algorithm removes noise from correlation estimators; applied to S&P500 to test adequacy for portfolio management. | strategies/covariance_models.py |
| 2003 | [cond-mat/0305475v1](https://arxiv.org/abs/cond-mat/0305475v1) | Simulation-based framework isolates noise sources in financial correlation matrices and benchmarks covariance estimators for portfolio and risk management. | strategies/covariance_models.py |
| 2003 | [cond-mat/0312643v1](https://arxiv.org/abs/cond-mat/0312643v1) | RMT on Tokyo TSE correlations: randomness repels deterministic and random eigenvalues, refining detection of correlated stock groups. | strategies/covariance_models.py |
| 2003 | [cond-mat/0312496v2](https://arxiv.org/abs/cond-mat/0312496v2) | RMT exact relations between true covariance spectrum and its estimator show correlations are measurable even in the "random" part of the spectrum; portfolio implications noted. | strategies/covariance_models.py |
| 2001 | [cond-mat/0108023v1](https://arxiv.org/abs/cond-mat/0108023v1) | Random-matrix analysis of US stock correlation matrices: most eigenvalues inside RMT bounds, deviating stable eigenvectors map to the market mode plus business sectors. | strategies/covariance_models.py |
| 2001 | [cond-mat/0111503v1](https://arxiv.org/abs/cond-mat/0111503v1) | Noisy empirical covariance matrices have little effect on linearly-constrained min-variance but cause severe degeneracy under non-linear (margin/capital) constraints. | strategies/covariance_models.py |
| 1999 | [cond-mat/9911168v1](https://arxiv.org/abs/cond-mat/9911168v1) | DAX 30 rolling correlation matrix: drawdowns coincide with separation of one strong collective eigenstate and reduced noise-state variance; drawups spread eigenstates. | strategies/eigen_rotation.py |
| 1999 | [cond-mat/9902283v1](https://arxiv.org/abs/cond-mat/9902283v1) | RMT on 1000 US stocks: most eigenvalues follow GOE statistics with few large deviations; eigenvectors at spectrum edges have large inverse participation ratios (localization-like). | strategies/covariance_models.py |
| 1998 | [cond-mat/9802256v1](https://arxiv.org/abs/cond-mat/9802256v1) | Minimal-spanning-tree / subdominant-ultrametric hierarchical structure of stock correlations yields a meaningful economic taxonomy and common factors. | strategies/covariance_models.py |

## Medium relevance (100) (showing the 100 most recent of 609)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2606.15755v1](https://arxiv.org/abs/2606.15755v1) | Multiplex Network Hawkes model with covariate-dependent excitation layers infers contagion from 99 firms' CDS (2004-2022); contagion is sparse, concentrated in outward flows from few institutions, with industry similarity the most supported channel. | strategies/triadic_stress.py |
| 2026 | [2606.04153v1](https://arxiv.org/abs/2606.04153v1) | Decomposes returns into sign and magnitude, modeling sign conditional on contemporaneous magnitude; captures nonlinear predictability and delivers substantial out-of-sample statistical and economic gains on monthly U.S. excess returns versus linear regression. | strategies/volatility_models.py |
| 2026 | [2603.19136v2](https://arxiv.org/abs/2603.19136v2) | Autoencoder reconstruction-error gating routes data to dual node transformers specialized for stable versus event-driven regimes, with reinforcement-learning control and no manual regime labels. | `strategies/regime_state.py` |
| 2026 | [2608.26128v1](https://arxiv.org/abs/2608.26128v1) | Econophysics thesis clusters spectral quantities of 430-stock S&P 500 correlation matrices into Market States; COVID-19 emerges atypical, needing C^2/C^3 reconstructions, with participation spreading during crises. | strategies/covariance_models.py |
| 2026 | [2608.06618v1](https://arxiv.org/abs/2608.06618v1) | MINGLE jointly learns latent factors and an exposure-similarity graph via ADMM for portfolio diversification; the exposure graph aligns with sectors and its portfolios beat correlation-based counterparts across volatility regimes and costs. | strategies/portfolio_optimizer.py |
| 2026 | [2604.23087v1](https://arxiv.org/abs/2604.23087v1) | Gaussian-copula framework learns deal-level dependence from joint success frequencies; holding marginals fixed, correlation preserves mean but fattens right tails/kurtosis in VC portfolios. | strategies/covariance_models.py |
| 2026 | [2605.16324v1](https://arxiv.org/abs/2605.16324v1) | Bi-level chaotic-fusion graph network predicts intervals for stock returns via separate center/width functions and volatility-aware gating, improving interval calibration and sharpness across regimes. | strategies/conformal.py |
| 2026 | [2605.29541v1](https://arxiv.org/abs/2605.29541v1) | Copula-based Markov chain with Weibull marginals (Clayton/Joe copulas) for offline change-point estimation under nonlinear serial dependence; MLE via Newton-Raphson with bootstrap intervals. | strategies/statistical.py |
| 2026 | [2606.23492v1](https://arxiv.org/abs/2606.23492v1) | Continuous hidden Markov model with heavy-tailed emissions (Gaussian, Student-t, Laplace, generalized error) separates regime autocorrelation from marginal shape; on U.S. equities heavy-tailed marginals close most of the fit gap, recovering volatility clustering and reducing kurtosis. | strategies/regime_state.py |
| 2026 | [2601.00395v1](https://arxiv.org/abs/2601.00395v1) | Builds conditional p-threshold mutual-information minimum-spanning-tree networks for QUAD large caps around the COVID crash; networks integrate during the crash and post-crash shows higher relative frequency of large volatility events. | `strategies/triadic_stress.py` |
| 2026 | [2606.16840v1](https://arxiv.org/abs/2606.16840v1) | Dynamic Hüsler-Reiss graphical models on the 13 largest cryptocurrencies show a near-complete stable lower-tail dependence graph versus a thinning upper tail; intra-crypto diversification fails on the downside and standard models understate crash probability eight-fold. | strategies/tail_risk.py |
| 2026 | [2608.05755v2](https://arxiv.org/abs/2608.05755v2) | Extends LSTM with macro covariates and learnable sector embeddings for S&P 500 long-short forecasts; the sector-embedding model outperforms plain LSTM, Random Forest and buy-and-hold on risk and return. | strategies/universe_factors.py |
| 2026 | [2604.19476v2](https://arxiv.org/abs/2604.19476v2) | Two-stage network builds a sparse 10-K embedding candidate graph then uses an LLM to filter edges by economic relation, aggregating pair mean-reversion signals; LLM filtering improves an S&P500 2011-2019 backtest over raw similarity. | `strategies/mean_reversion.py` |
| 2026 | [2606.08586v1](https://arxiv.org/abs/2606.08586v1) | Builds stock-level topological anomaly scores via Takens delay embedding, BallMapper graphs and decoder-conditional VAEs, testing predictive content for intraday return curves; penalised function-on-function regression confirms a regime-dependent temporal fingerprint across all assets. | strategies/cross_section.py |
| 2026 | [2606.27670v1](https://arxiv.org/abs/2606.27670v1) | CryptoGAT recasts cryptocurrency price prediction as a cross-asset graph attention problem rather than temporal modeling, outperforming LSTM/GRU/Transformer baselines and arguing that extreme volatility defeats time-series models. | strategies/covariance_models.py |
| 2026 | [2608.29025v1](https://arxiv.org/abs/2608.29025v1) | Compares classical and deep hedging on real Deribit BTC options; Whalley-Wilmott cuts costs by $1.79 per episode, and none of the three deep hedging models beats any classical benchmark on any metric. | strategies/options_math.py |
| 2026 | [2605.27977v1](https://arxiv.org/abs/2605.27977v1) | Forecasts US aggregate bond index with MLPs on lagged vectors and CNNs on Gramian Angular Fields after fractional differencing; MLPs merely match the naive persistence benchmark. | strategies/factor_expressions.py |
| 2026 | [2608.14323v1](https://arxiv.org/abs/2608.14323v1) | Maps characteristic dependence via a Maximally Filtered Clique Forest onto a Homological Neural Network for annual excess-return forecasts; it matches a three-layer benchmark, ranks better, and uses ~80x fewer parameters. | strategies/universe_factors.py |
| 2026 | [2602.07046v5](https://arxiv.org/abs/2602.07046v5) | GJR-GARCH-X event study of 50 crypto shocks across six assets; curated high-salience events give 3.49x variance multiplier but dependence-robust inference removes significance (copula p~0.39); asymmetry directional, selection-conditional, unresolved. | `strategies/volatility_models.py` |
| 2026 | [2604.26811v2](https://arxiv.org/abs/2604.26811v2) | Network-based transfer entropy compares news vs social-media sentiment spillover across tech firms; news information flow intensified post-COVID; identifies information-hub companies. | strategies/sentiment_research.py |
| 2026 | [2607.06373v1](https://arxiv.org/abs/2607.06373v1) | Derives perturbation/null laws for eigenspace projector movement and scalar spectral functionals of shrinkage covariance estimators, enabling calibrated tests of whether absorption-ratio and leading-share moves are structural. | strategies/covariance_models.py |
| 2026 | [2603.05260v2](https://arxiv.org/abs/2603.05260v2) | Proposes a finite-sample multivariate extreme-value framework rotating high-frequency returns into the correlation-matrix eigenbasis, then peaks-over-threshold estimation; separates market, sectoral and idiosyncratic tail behavior under nonstationarity. | `strategies/eigen_rotation.py` |
| 2026 | [2601.11201v1](https://arxiv.org/abs/2601.11201v1) | Separates slow and fast components in financial series via generalized eigenvalue problems under variance and tail stationarity; demonstrated on FX, equity ETFs and treasury yields for drift, mean reversion and tail risk. | `strategies/volatility_models.py` |
| 2026 | [2601.10517v2](https://arxiv.org/abs/2601.10517v2) | Extends Log S-fBM to a multivariate volatility model (mLog S-fBM) with co-Hurst and co-intermittency matrices; S&P 500 estimates show multifractal behavior and off-diagonal co-Hurst near H≈0.12. | `strategies/volatility_models.py` |
| 2026 | [2605.11645v1](https://arxiv.org/abs/2605.11645v1) | GeomHerd tracks Ollivier-Ricci curvature on LLM-agent interaction graphs to quantify herding forward-looking, bypassing price-correlation lag; mean-field bridge links it to the CSAD statistic. | strategies/consensus.py |
| 2026 | [2608.26127v1](https://arxiv.org/abs/2608.26127v1) | Proposes FA-GSTN, reframing realized-volatility forecasting as modeling a spatio-temporal graph over the implied-volatility surface; it sets state of the art (R^2 up to 0.473) and is data-efficient and stress-robust. | strategies/options_surface.py |
| 2026 | [2603.10202v2](https://arxiv.org/abs/2603.10202v2) | Hybrid HMM discretizes excess growth rates into Laplace quantile states, augments regime switching with Poisson jump-duration for tail dwell times, and is fitted by transition counting, scaling to 424 assets. | `strategies/regime.py` |
| 2026 | [2606.03457v1](https://arxiv.org/abs/2606.03457v1) | Hybrid news sentiment engine: a CPU-only three-way ensemble of FinBERT-style lexicon scoring, adaptive TF-IDF headline clustering tracking realized price reactions, and auto-calibrating weights; adapts to market regimes without retraining or GPU compute. | strategies/sentiment_research.py |
| 2026 | [2606.07450v1](https://arxiv.org/abs/2606.07450v1) | Tests Pearson versus mutual-information dependency estimators with MST/PMFG filtering and four community decoders across 2,328 Indonesian rolling windows; Pearson-MST-Infomap best recovers sectors, while MI-PMFG exposes local and heterogeneous structures. | strategies/peer_universe.py |
| 2026 | [2603.20271v1](https://arxiv.org/abs/2603.20271v1) | Builds transfer-entropy networks from foreign, institutional and individual investor flows across Korean equities (2020-2025); networks are sparse and heterogeneous, assessed via interaction information, conditional TE, Kelly bounds and Fama-MacBeth. | `strategies/orderflow.py` |
| 2026 | [2607.06908v1](https://arxiv.org/abs/2607.06908v1) | Iterative global-factor algorithm combines Marcenko-Pastur edge recalibration with participation-ratio delocalization, recovering factor counts near the BBP transition where eigenvalue-only criteria fail; S&P 500 median count 7. | strategies/covariance_models.py |
| 2026 | [2608.09641v1](https://arxiv.org/abs/2608.09641v1) | Shows the smallest eigenvalues of financial correlation matrices carry market-synchronization information, complementing large-eigenvalue PCA/RMT, and validates it in descriptive and predictive experiments. | strategies/covariance_models.py |
| 2026 | [2606.00624v1](https://arxiv.org/abs/2606.00624v1) | HANET hierarchically nests daily asset-return signals inside monthly macro windows with cross-attention; attention over macro contexts adapts to scarce regimes across 55 liquid futures. | strategies/regime_score.py |
| 2026 | [2601.17773v1](https://arxiv.org/abs/2601.17773v1) | MarketGAN embeds an asset-pricing factor structure in a TCN-based GAN generating joint return vectors; matches heavy tails, volatility clustering and cross-sectional tail co-movement, and its covariance estimates outperform factor bootstrap. | `strategies/covariance_models.py` |
| 2026 | [2602.08182v1](https://arxiv.org/abs/2602.08182v1) | NANSDE-Net introduces neural-network-kernel ARMA noise, an Ito-compatible alternative to fractional Brownian motion, for Neural SDEs; matches or beats fractional SDE-Net reproducing long- and short-memory while staying tractable. | `strategies/long_memory.py` |
| 2026 | [2603.20456v1](https://arxiv.org/abs/2603.20456v1) | Neural HMM with adaptive granularity attention: a dilated-CNN tick encoder plus wavelet-LSTM, gated by local volatility and transaction intensity, for high-frequency order-flow modeling across scales. | `strategies/orderflow.py` |
| 2026 | [2603.28257v2](https://arxiv.org/abs/2603.28257v2) | KAN-PCA autoencoder replaces PCA's linear projections with B-spline KAN encodings; on 20 S&P500 returns (2015-2024) reconstructs R2=66.57% vs PCA's 62.99% with 3 factors, matching PCA out-of-sample. | `strategies/covariance_models.py` |
| 2026 | [2609.08106v1](https://arxiv.org/abs/2609.08106v1) | Decomposes MASTER's inter-stock attention: learned attention is near-uniform yet its low-rank deviation carries cross-sectional value; Nystrom attention with 32 landmarks matches full O(N^2) attention, while graph alternatives degrade performance. | strategies/cross_section.py |
| 2026 | [2605.25894v1](https://arxiv.org/abs/2605.25894v1) | Multi-modal LSTM/Transformer on 15 fundamentals, 3 technicals and FinBERT news sentiment predicts earnings-day direction; Transformer achieves higher macro F1 and sentiment adds consistent value. | strategies/events.py |
| 2026 | [2609.20550v1](https://arxiv.org/abs/2609.20550v1) | Decomposes principal-component estimation error in high-dimensional factor models into out-of-subspace (estimable) and in-subspace terms with almost sure limits; in a three-factor US equity simulation out-of-subspace error dominates. | strategies/covariance_models.py |
| 2026 | [2604.19580v1](https://arxiv.org/abs/2604.19580v1) | Shows quantile-based battery trading strategies (QBTS) do not incentivize honest probabilistic forecasts and ignore intertemporal price dependence; reframes battery optimization as a stochastic program evaluating the economic value of forecast accuracy. | `strategies/evaluate.py` |
| 2026 | [2606.31475v2](https://arxiv.org/abs/2606.31475v2) | Extends rogue-wave theory to financial volatility: a Kerr-nonlinearity Schrodinger model in a moving window shows Anderson localisation before VIX peaks whose minimum-eigenvalue gradient spikes at onset, detecting 7 of 8 major peaks. | strategies/tail_risk.py |
| 2026 | [2607.10297v1](https://arxiv.org/abs/2607.10297v1) | Spectral denoising splits correlation matrices into 10-16 structured eigenmodes plus noise; denoised NIFTY/S&P networks show stronger core-periphery structure and periphery portfolios beat unfiltered benchmarks risk-adjusted. | strategies/covariance_models.py |
| 2026 | [2608.12251v1](https://arxiv.org/abs/2608.12251v1) | Proposes RG-ResMoE, a regime-gated residual mixture-of-experts for cross-sectional volatility forecasting; routing regime state to experts beats appending it as input, improving accuracy, stability and VaR calibration. | strategies/volatility_models.py |
| 2026 | [2606.09274v1](https://arxiv.org/abs/2606.09274v1) | Reverse stress testing reconstructs a coherent multivariate stress scenario from a single exogenous shock by maximizing conditional density, solved under parametric, empirical-likelihood semiparametric and nonparametric inverse-distance resampling assumptions; validated on market data. | strategies/book_risk.py |
| 2026 | [2603.05917v3](https://arxiv.org/abs/2603.05917v3) | Proposes a node-transformer over a stock graph whose edges encode sector affiliation and price correlation, fused with BERT sentiment for cross-sectional stock price forecasting; no numeric result reported. | `strategies/sentiment.py` |
| 2026 | [2604.19107v1](https://arxiv.org/abs/2604.19107v1) | Random-Matrix-Theory complexity gap (normalized largest eigenvalue minus average pairwise correlation) shows a three-phase G5 pattern across shocks: rich structure before, near-zero synchronization during, and recovery after. | `strategies/covariance_models.py` |
| 2025 | [2508.20101v1](https://arxiv.org/abs/2508.20101v1) | Heterogeneous spatiotemporal GARCH adds spatially correlated innovations and varying parameters over a balance-sheet-derived proxy space; predicts firm volatility with contagion effects. | `strategies/covariance_models.py` |
| 2025 | [2508.02686v1](https://arxiv.org/abs/2508.02686v1) | Mixture-of-Experts combines an RNN for high-volatility stocks with linear regression for stable ones via a volatility-aware gate; across 30 US stocks it cuts MSE up to 33% and 28% versus standalone models. | `strategies/regime_score.py` |
| 2025 | [2502.08242v2](https://arxiv.org/abs/2502.08242v2) | Network communicability on correlation-derived Indian market graphs; 70%/80% of stock pairs shift significantly in GFC/COVID; communicability features beat shortest-path measures at classifying stable versus volatile periods. | `strategies/triadic_stress.py` |
| 2025 | [2504.16635v2](https://arxiv.org/abs/2504.16635v2) | Combines GARCH volatility models with a Double Deep Q-Network direction forecast for Value-at-Risk; on daily Eurostoxx 50 it improves VaR accuracy, cuts breaches and capital requirements under crisis volatility. | `strategies/book_risk.py` |
| 2025 | [2506.04656v1](https://arxiv.org/abs/2506.04656v1) | Applies bootstrap testing to absolute log returns of U.S. S&P 500 and Chinese A-shares; finds more isolated dependent clusters in the U.S. versus a more interconnected China, with strong cross-market materials and consumer links. | `strategies/tail_risk.py` |
| 2025 | [2502.15458v2](https://arxiv.org/abs/2502.15458v2) | Extends Diebold-Yilmaz variance-decomposition connectedness to clustered nodes, orthogonal shocks across clusters and correlated within, ordering relevant across but not within; applied to sixteen country equity markets. | `strategies/covariance_models.py` |
| 2025 | [2505.19243v1](https://arxiv.org/abs/2505.19243v1) | Compares log returns against fractional and tempered-fractional differencing as LSTM inputs across four indices; fractional differentiation improves forecast error metrics and risk-adjusted trading returns, supporting memory-preserving transforms. | `strategies/long_memory.py` |
| 2025 | [2510.16008v1](https://arxiv.org/abs/2510.16008v1) | Introduces convolutional attention over recurrent and 2D-convolutional-recurrent layers with a novel multivariate padding method, forecasting Betfair pre-live market-depth price movements for automated trading. | `strategies/orderflow.py` |
| 2025 | [2505.06950v1](https://arxiv.org/abs/2505.06950v1) | Performs multivariate VaR and CVaR analysis using several copula families fitted with DCC-GARCH models on historical financial series, comparing goodness-of-fit to assess each copula approach's validity and effectiveness. | `strategies/book_risk.py` |
| 2025 | [2505.14655v1](https://arxiv.org/abs/2505.14655v1) | Studies 39 corporate-Bitcoin-holding firms, finding average BTC beta 0.62 (12 firms above 1) and, via transfer entropy, BTC as dominant information driver, implying hedging ratios must adapt dynamically to shifting information flows. | `strategies/covariance_models.py` |
| 2025 | [2512.21798v2](https://arxiv.org/abs/2512.21798v2) | Generates synthetic S&P 500 return series with TimeGAN and VAEs; TimeGAN better captures temporal dynamics, supporting privacy-preserving, reproducible portfolio and risk simulation. | - |
| 2025 | [2504.20088v1](https://arxiv.org/abs/2504.20088v1) | Trains a deep residual network with a hybrid market/analytic loss to price European Petrobras options, cutting mean absolute error 64.3% versus Black-Scholes in the 3-19 BRL range and staying accurate at long expiries. | `strategies/options_math.py` |
| 2025 | [2507.20039v1](https://arxiv.org/abs/2507.20039v1) | Builds dependency networks from VAR forecast-error variance decomposition and Minimum Spanning Tree, selecting central stocks; ARIMA/NNAR forecasts plus VaR allocation yield 63.74% versus 18% buy-and-hold over one year. | `strategies/portfolio_optimizer.py` |
| 2025 | [2512.06473v1](https://arxiv.org/abs/2512.06473v1) | Builds multifractal detrended cross-correlation matrices ρ_r for 140 cryptocurrencies (2021-2024); detrending, heavy tails and fluctuation order jointly shift spectra beyond the random-matrix limit, isolating a market factor and sectoral modes. | `strategies/covariance_models.py` |
| 2025 | [2504.06566v5](https://arxiv.org/abs/2504.06566v5) | Diffusion factor model embeds latent factor structure into generative diffusion by decomposing the score function with time-varying orthogonal projections; nonasymptotic bounds depend on factor dimension, enabling high-dimensional return simulation and mean-variance/factor portfolios. | `strategies/factors.py` |
| 2025 | [2507.14325v1](https://arxiv.org/abs/2507.14325v1) | Matrix-H theory extends the Marchenko-Pastur eigenvalue distribution of correlation matrices to multiscale hierarchical structure, capturing more variance and providing noise reduction that improves inference of true asset correlations. | `strategies/covariance_models.py` |
| 2025 | [2508.15825v2](https://arxiv.org/abs/2508.15825v2) | Compares TikTok video versus Twitter text sentiment for crypto via LLMs; TikTok sentiment drives speculative short-term moves, Twitter aligns with long-term dynamics, cross-platform signals lift forecasting up to 20%. | `strategies/sentiment.py` |
| 2025 | [2512.12334v1](https://arxiv.org/abs/2512.12334v1) | Extends dynamic Bayesian networks to 10-day 97.5% expected shortfall and stressed ES on S&P 500; backtests show all models fail accurate ES/SES, with EGARCH(1,1) best for ES and GARCH(1,1) for SES. | `strategies/book_risk.py` |
| 2025 | [2502.05218v1](https://arxiv.org/abs/2502.05218v1) | FactorGCL, a hypergraph factor model with cascading residual architecture and temporal residual contrastive learning, mines hidden factors beyond prior ones and beats state-of-the-art stock-return prediction. | `strategies/factors.py` |
| 2025 | [2509.18820v2](https://arxiv.org/abs/2509.18820v2) | q-dependent detrended cross-correlation and q-minimum-spanning-trees track amplitude-dependent correlation structure of 140 Binance crypto pairs; networks shift at the April 2022 Terra/Luna crash. | `strategies/triadic_stress.py` |
| 2025 | [2512.02352v3](https://arxiv.org/abs/2512.02352v3) | Introduces forwarded visibility horizon L+ in horizontal visibility graphs as a rank-invariant path-roughness estimator; tail exponent θ predicts θ(H)=1−H and separates rough Bergomi from Heston/GARCH on VIX. | `strategies/volatility_models.py` |
| 2025 | [2509.24144v2](https://arxiv.org/abs/2509.24144v2) | End-to-end LSTM plus graph attention plus news sentiment directly learns daily portfolio weights for nine US stocks, avoiding the forecast-then-mean-variance two-step and its instability. | `strategies/portfolio_optimizer.py` |
| 2025 | [2502.11310v2](https://arxiv.org/abs/2502.11310v2) | Generalized factor neural network with PCA/Soft PCA layers embedded at any stage, alternating factor modeling and nonlinear transforms; effective on hierarchical compositional data, forecasting equity ETF indices and macro nowcasting. | `strategies/factors.py` |
| 2025 | [2509.13923v1](https://arxiv.org/abs/2509.13923v1) | Derives the expected Frobenius error of holdout cross-validation for large covariance estimation under rotationally invariant multiplicative noise, using Weingarten calculus and Ledoit-Peche oracle eigenvalues. | `strategies/covariance_models.py` |
| 2025 | [2504.15908v1](https://arxiv.org/abs/2504.15908v1) | Builds multi-scale Hawkes order-flow features including limit-order posting distance, trains an interpretable probabilistic network for mid-price moves, and finds 31% of large orders could spoof; posting distance is critical. | `strategies/orderflow.py` |
| 2025 | [2507.09554v1](https://arxiv.org/abs/2507.09554v1) | Transfer entropy plus Kramers-Moyal expansion maps directional coupling among Nasdaq, WTI, gold and the dollar; average TE rises 35% and 28% during COVID and Ukraine crises, exposing nonlinear regime shifts. | `strategies/triadic_stress.py` |
| 2025 | [2508.20108v2](https://arxiv.org/abs/2508.20108v2) | ReVol: return-volatility normalization plus sample-characteristic reintegration and GBM/NN blend to counter distribution shift; improves backbones by over 0.03 IC and 0.7 SR on average. | `strategies/volatility_models.py` |
| 2025 | [2505.22836v1](https://arxiv.org/abs/2505.22836v1) | Trains a deep-hedging neural network with as few as 256 trajectories; under geometric Brownian motion with transaction costs it significantly outperforms Black-Scholes and the Leland model, enabling practical real-time implementation. | `strategies/options_math.py` |
| 2025 | [2504.18958v1](https://arxiv.org/abs/2504.18958v1) | Builds a tensor/eigenvalue Financial Chaos Index, fits a three-regime Modified Lognormal Power-Law switching model (1990-2023), and uses Equity Market Volatility sentiment with elastic net to forecast VIX across regimes. | `strategies/regime.py` |
| 2025 | [2503.08696v1](https://arxiv.org/abs/2503.08696v1) | Multimodal Russian-market forecaster combines candlestick time series with news text via RuBERT/Qwen embeddings and an LSTM over 176 Moscow Exchange stocks; adding the textual modality cut MAPE by 55%. | `strategies/news_relevance.py` |
| 2025 | [2507.02018v1](https://arxiv.org/abs/2507.02018v1) | Proposes NGAT, a node-level graph attention network for long-term stock prediction over corporate relationship graphs; demonstrates existing graph-comparison methods are flawed and NGAT performs consistently across two datasets. | `strategies/peer_universe.py` |
| 2025 | [2504.02518v4](https://arxiv.org/abs/2504.02518v4) | Introduces online multivariate distributional regression with coordinate descent and LASSO regularization for 24-hour probabilistic electricity price forecasting; on German day-ahead data it gives well-calibrated joint prediction intervals and a regularized dependence-structure path via open-source ondil. | `strategies/statistical.py` |
| 2025 | [2506.17549v1](https://arxiv.org/abs/2506.17549v1) | Develops Bayesian Generalised Pareto Regression linking tail scale to covariates for Indian Nifty 50 crashes; Cauchy prior wins on RMSE/AIC/BIC and S&P 500 and gold volatility significantly drive extreme-loss forecasts. | `strategies/tail_risk.py` |
| 2025 | [2507.15876v1](https://arxiv.org/abs/2507.15876v1) | Bayesian graphical model dynamically decomposes CTA returns into short-term trend, long-term trend and market-beta factors, showing how the blend of horizons shapes risk-adjusted performance. | `strategies/momentum.py` |
| 2025 | [2502.18177v1](https://arxiv.org/abs/2502.18177v1) | Dynamic neural VWAP framework adds recurrent networks and continuous feedback adjustment to a prior static direct-optimization model; gains 10-15% execution performance in liquid crypto markets. | `strategies/execution_schedule.py` |
| 2025 | [2506.19856v1](https://arxiv.org/abs/2506.19856v1) | Introduces Characteristic Vector Linkages as firm-linkage proxies; Euclidean similarity and Quantum Cognition Machine Learning both yield profitable momentum-spillover strategies, with QCML similarity outperforming Euclidean. | `strategies/peer_universe.py` |
| 2025 | [2501.16772v2](https://arxiv.org/abs/2501.16772v2) | Across equities, rates, FX and commodities, markets trend on hours-to-years scales and revert shorter/longer; weak trends persist in trending regimes but revert before statistical significance, consistent with herding. | `strategies/mean_reversion.py` |
| 2025 | [2504.09380v2](https://arxiv.org/abs/2504.09380v2) | Embeds the GARCH(1,1) update into GRU/LSTM gating (GARCH-GRU/LSTM); out-of-sample it beats classical GARCH, pipeline hybrids and Transformers on US equity indices, with GARCH-GRU fastest and well-calibrated 99% VaR. | `strategies/volatility_models.py` |
| 2024 | [2410.16526v1](https://arxiv.org/abs/2410.16526v1) | Dynamic spatiotemporal network ARCH adds spatial, temporal and spatiotemporal spillovers plus volatility-specific latent factors, estimated by Bayesian MCMC. | `strategies/volatility_models.py` |
| 2024 | [2408.05659v1](https://arxiv.org/abs/2408.05659v1) | Builds return/realized-vol/volume correlation networks across E-mini S&P 500 and VIX futures expiries, feeding a multi-channel GCN-LSTM forecaster. | `strategies/volatility_models.py` |
| 2024 | [2411.15002v1](https://arxiv.org/abs/2411.15002v1) | Couples LSTM Deep Hedging with Kronecker-Factored Approximate Curvature second-order optimization; on simulated Heston paths cuts transaction costs 78.3%, P&L variance 34.4%, Sharpe 0.0401 vs -0.0025. | `strategies/options_math.py` |
| 2024 | [2405.12993v1](https://arxiv.org/abs/2405.12993v1) | Portfolios built from the core-periphery profile of Pearson-correlation stock networks consistently outperform centrality-based strategies in Sharpe ratio and returns. | `strategies/portfolio_optimizer.py` |
| 2024 | [2404.00028v2](https://arxiv.org/abs/2404.00028v2) | Separately builds weighted temporal anti-correlation and positive-correlation networks among Shanghai/Shenzhen stocks; fundamental topological measures differ between the two. | `strategies/covariance_models.py` |
| 2024 | [2404.01338v1](https://arxiv.org/abs/2404.01338v1) | LDA topic modelling plus temporality detection finds relevant financial events, forecasts and predictions in unstructured news streams. | `strategies/news_relevance.py` |
| 2024 | [2408.12839v1](https://arxiv.org/abs/2408.12839v1) | Helmholtz-Hodge-Kodaira decomposition splits Granger-causality market networks into gradient/rotational parts, revealing precious-metals and pharma as Covid-crisis causal drivers. | `strategies/covariance_models.py` |
| 2024 | [2405.05642v1](https://arxiv.org/abs/2405.05642v1) | Partial-correlation complex networks around three crypto crashes (2017-20): degree density and clustering coefficient spike during crashes and are smallest pre-crash. | `strategies/breadth_depth.py` |
| 2024 | [2409.15103v1](https://arxiv.org/abs/2409.15103v1) | Random matrix theory characterises the high-dimensional mean-variance efficient frontier when p/n -> c; two of three quantities are biased/overestimated by sample counterparts. | `strategies/portfolio_optimizer.py` |
| 2024 | [2411.03922v1](https://arxiv.org/abs/2411.03922v1) | FEVD, volume-normalized FEVD and Granger-causality frequency/days on high-frequency data identify leading co-movement Chinese bank stocks, whose influence ties to wealth management, interbank activity, equity multiplier and NPLs. | `strategies/statistical.py` |
| 2024 | [2404.15495v2](https://arxiv.org/abs/2404.15495v2) | Detrended correlation analysis of NFT collections shows weaker correlation strength than other markets and eigenvalue spectra closer to noise. | `strategies/covariance_models.py` |
| 2024 | [2411.13555v3](https://arxiv.org/abs/2411.13555v3) | Empirically compares MLP, CNN, LSTM and Transformer for long-short S&P500/NASDAQ portfolios from past returns, RSI, volume and volatility; deep-learning predictions improve return, Sharpe ratio and drawdown over two-year tests. | `strategies/portfolio_strategy.py` |
| 2024 | [2404.07224v1](https://arxiv.org/abs/2404.07224v1) | Stacked classification system detects 'opportunity' predictions in financial tweets with high precision to distinguish them from other financial emotions. | `strategies/sentiment.py` |
| 2024 | [2403.00772v1](https://arxiv.org/abs/2403.00772v1) | Combines BERT sentiment with LSTM stock prediction and tests whether Weibo users' financial background affects forecast accuracy. | `strategies/sentiment_research.py` |
| 2024 | [2410.16858v1](https://arxiv.org/abs/2410.16858v1) | Temporal Graph Attention network on dynamic global-market graphs using correlation and volatility-spillover indices improves volatility forecasting over GARCH. | `strategies/volatility_models.py` |

## Low relevance / background (348)

| year | id | title |
| --- | --- | --- |
| 2026 | [2602.21869v3](https://arxiv.org/abs/2602.21869v3) | A Bayesian approach to out-of-sample network reconstruction |
| 2026 | [2604.22801v2](https://arxiv.org/abs/2604.22801v2) | Beyond Sequential Prediction: Learning Financial Market Dynamics in Volatile and Non-Stationary Environments through Sentiment-Conditioned Generative Modelling |
| 2026 | [2603.21797v1](https://arxiv.org/abs/2603.21797v1) | Connecting Distributed Ledgers: Surveying Novel Interoperability Solutions in On-chain Finance |
| 2026 | [2604.09650v1](https://arxiv.org/abs/2604.09650v1) | Dynamic Forecasting and Temporal Feature Evolution of Stock Repurchases in Listed Companies Using Attention-Based Deep Temporal Networks |
| 2026 | [2603.24190v2](https://arxiv.org/abs/2603.24190v2) | Dynamical thermalization and turbulence in social stratification models |
| 2026 | [2604.02549v1](https://arxiv.org/abs/2604.02549v1) | Financial Anomaly Detection for the Canadian Market |
| 2026 | [2609.17415v1](https://arxiv.org/abs/2609.17415v1) | Financial Contagion Networks as Annealing-Ready Ising Systems Cascades, Bailout Optimization, and Susceptibility |
| 2026 | [2608.26174v1](https://arxiv.org/abs/2608.26174v1) | Forecasting Economically Significant Bitcoin Moves: A Multi-Scale TCN with Profit-Optimized Thresholds |
| 2026 | [2602.10960v1](https://arxiv.org/abs/2602.10960v1) | Integrating granular data into a multilayer network: an interbank model of the euro area for systemic risk assessment |
| 2026 | [2604.07567v2](https://arxiv.org/abs/2604.07567v2) | Marginal Persistence and Dynamic Copula Dependence in Sovereign Rating Migration Counts: A Discrete Interval-Likelihood MAGMAR Analysis |
| 2026 | [2601.19321v1](https://arxiv.org/abs/2601.19321v1) | Predictive Accuracy versus Interpretability in Energy Markets: A Copula-Enhanced TVP-SVAR Analysis |
| 2026 | [2604.19796v1](https://arxiv.org/abs/2604.19796v1) | Systemic Risk and Default Cascades in Global Equity Markets: A Network and Tail-Risk Approach Based on the Gai Kapadia Framework |
| 2026 | [2604.16835v1](https://arxiv.org/abs/2604.16835v1) | The CTLNet for Shanghai Composite Index Prediction |
| 2026 | [2606.23337v1](https://arxiv.org/abs/2606.23337v1) | When Staking Rewards Compound: Measuring the Impact of Ethereum's Pectra Upgrade |
| 2025 | [2511.08658v1](https://arxiv.org/abs/2511.08658v1) | "It Looks All the Same to Me": Cross-index Training for Long-term Financial Series Prediction |
| 2025 | [2502.17044v1](https://arxiv.org/abs/2502.17044v1) | A data-driven econo-financial stress-testing framework to estimate the effect of supply chain networks on financial systemic risk |
| 2025 | [2506.09851v2](https://arxiv.org/abs/2506.09851v2) | Advancing Exchange Rate Forecasting: Leveraging Machine Learning and AI for Enhanced Accuracy in Global Financial Markets |
| 2025 | [2510.15993v1](https://arxiv.org/abs/2510.15993v1) | Aligning Language Models with Investor and Market Behavior for Financial Recommendations |
| 2025 | [2502.15726v1](https://arxiv.org/abs/2502.15726v1) | Bankruptcy analysis using images and convolutional neural networks (CNN) |
| 2025 | [2508.02685v1](https://arxiv.org/abs/2508.02685v1) | Benchmarking Classical and Quantum Models for DeFi Yield Prediction on Curve Finance |
| 2025 | [2510.15900v1](https://arxiv.org/abs/2510.15900v1) | Bitcoin Price Forecasting Based on Hybrid Variational Mode Decomposition and Long Short Term Memory Network |
| 2025 | [2501.09760v1](https://arxiv.org/abs/2501.09760v1) | Boosting the Accuracy of Stock Market Prediction via Multi-Layer Hybrid MTL Structure |
| 2025 | [2504.15268v17](https://arxiv.org/abs/2504.15268v17) | Causal Discovery via Simultaneous DAG Recovery Using the Angles Space of Directional Dependence Measures |
| 2025 | [2502.19305v2](https://arxiv.org/abs/2502.19305v2) | Corporate Fraud Detection in Rich-yet-Noisy Financial Graph |
| 2025 | [2507.01980v1](https://arxiv.org/abs/2507.01980v1) | Detecting Fraud in Financial Networks: A Semi-Supervised GNN Approach with Granger-Causal Explanations |
| 2025 | [2507.01979v1](https://arxiv.org/abs/2507.01979v1) | Forecasting Labor Markets with LSTNet: A Multi-Scale Deep Learning Approach |
| 2025 | [2507.01964v1](https://arxiv.org/abs/2507.01964v1) | Forecasting Nigerian Equity Stock Returns Using Long Short-Term Memory Technique |
| 2025 | [2501.13136v1](https://arxiv.org/abs/2501.13136v1) | Forecasting of Bitcoin Prices Using Hashrate Features: Wavelet and Deep Stacking Approach |
| 2025 | [2511.05463v1](https://arxiv.org/abs/2511.05463v1) | From sectorial coarse graining to extreme coarse graining of S&P 500 correlation matrices |
| 2025 | [2503.15403v1](https://arxiv.org/abs/2503.15403v1) | HQNN-FSP: A Hybrid Classical-Quantum Neural Network for Regression-Based Financial Stock Market Prediction |
| 2025 | [2505.12806v1](https://arxiv.org/abs/2505.12806v1) | Hierarchical Representations for Evolving Acyclic Vector Autoregressions (HEAVe) |
| 2025 | [2508.20105v2](https://arxiv.org/abs/2508.20105v2) | Identification of phase correlations in Financial Stock Market Turbulence |
| 2025 | [2511.04784v1](https://arxiv.org/abs/2511.04784v1) | Insights into Tail-Based and Order Statistics |
| 2025 | [2512.07860v1](https://arxiv.org/abs/2512.07860v1) | Integrating LSTM Networks with Neural Levy Processes for Financial Forecasting |
| 2025 | [2510.15942v2](https://arxiv.org/abs/2510.15942v2) | Intrinsic Geometry of the Stock Market from Graph Ricci Flow |
| 2025 | [2502.15853v1](https://arxiv.org/abs/2502.15853v1) | Multi-Agent Stock Prediction Systems: Machine Learning Models, Simulations, and Real-Time Trading Strategies |
| 2025 | [2504.19623v2](https://arxiv.org/abs/2504.19623v2) | Multi-Horizon Echo State Network Prediction of Intraday Stock Returns |
| 2025 | [2505.01543v1](https://arxiv.org/abs/2505.01543v1) | Multiscale Causal Analysis of Market Efficiency via News Uncertainty Networks and the Financial Chaos Index |
| 2025 | [2502.15611v2](https://arxiv.org/abs/2502.15611v2) | Network topology of the Euro Area interbank market |
| 2025 | [2601.05274v1](https://arxiv.org/abs/2601.05274v1) | On the use of case estimate and transactional payment data in neural networks for individual loss reserving |
| 2025 | [2504.20058v2](https://arxiv.org/abs/2504.20058v2) | Predictive AI with External Knowledge Infusion: Datasets and Benchmarks for Stock Markets |
| 2025 | [2507.22035v1](https://arxiv.org/abs/2507.22035v1) | Quantum generative modeling for financial time series with temporal correlations |
| 2025 | [2512.17929v2](https://arxiv.org/abs/2512.17929v2) | Reinforcement Learning for Monetary Policy Under Macroeconomic Uncertainty: Analyzing Tabular and Function Approximation Methods |
| 2025 | [2507.08835v1](https://arxiv.org/abs/2507.08835v1) | Representation learning with a transformer by contrastive learning for money laundering detection |
| 2025 | [2505.10373v5](https://arxiv.org/abs/2505.10373v5) | Reproducing the first and second moments of empirical degree distributions |
| 2025 | [2512.17936v1](https://arxiv.org/abs/2512.17936v1) | Risk-Aware Financial Forecasting Enhanced by Machine Learning and Intuitionistic Fuzzy Multi-Criteria Decision-Making |
| 2025 | [2508.11372v2](https://arxiv.org/abs/2508.11372v2) | Stealing Accuracy: Predicting Day-ahead Electricity Prices with Temporal Hierarchy Forecasting (THieF) |
| 2025 | [2502.15813v1](https://arxiv.org/abs/2502.15813v1) | Stock Price Prediction Using a Hybrid LSTM-GNN Model: Integrating Time-Series and Graph-Based Analysis |
| 2025 | [2512.17925v1](https://arxiv.org/abs/2512.17925v1) | Stylized Facts and Their Microscopic Origins: Clustering, Persistence, and Stability in a 2D Ising Framework |
| 2025 | [2512.07886v1](https://arxiv.org/abs/2512.07886v1) | The Endogenous Constraint: Hysteresis, Stagflation, and the Structural Inhibition of Monetary Velocity in the Bitcoin Network (2016-2025) |
| 2025 | [2509.06468v1](https://arxiv.org/abs/2509.06468v1) | The use of financial and sustainability ratios to map a sector. An approach using compositional data |
| 2025 | [2508.04671v1](https://arxiv.org/abs/2508.04671v1) | Universal Patterns in the Blockchain: Analysis of EOAs and Smart Contracts in ERC20 Token Networks |
| 2025 | [2506.17720v3](https://arxiv.org/abs/2506.17720v3) | Wealth Thermalization Hypothesis and Social Networks |
| 2025 | [2502.00201v2](https://arxiv.org/abs/2502.00201v2) | Year-over-Year Developments in Financial Fraud Detection via Deep Learning: A Systematic Literature Review |
| 2024 | [2404.07298v3](https://arxiv.org/abs/2404.07298v3) | A Deep Learning Method for Predicting Mergers and Acquisitions: Temporal Dynamic Industry Networks |
| 2024 | [2411.13603v1](https://arxiv.org/abs/2411.13603v1) | A Full-History Network Dataset for BTC Asset Decentralization Profiling |
| 2024 | [2410.12807v1](https://arxiv.org/abs/2410.12807v1) | A Hierarchical conv-LSTM and LLM Integrated Model for Holistic Stock Forecasting |
| 2024 | [2410.19291v2](https://arxiv.org/abs/2410.19291v2) | A Stock Price Prediction Approach Based on Time Series Decomposition and Multi-Scale CNN using OHLCT Images |
| 2024 | [2402.06689v1](https://arxiv.org/abs/2402.06689v1) | A Study on Stock Forecasting Using Deep Learning and Statistical Models |
| 2024 | [2410.21291v3](https://arxiv.org/abs/2410.21291v3) | Achilles, Neural Network to Predict the Gold Vs US Dollar Integration with Trading Bot for Automatic Trading |
| 2024 | [2407.06529v1](https://arxiv.org/abs/2407.06529v1) | Advanced Financial Fraud Detection Using GNN-CL Model |
| 2024 | [2401.05441v2](https://arxiv.org/abs/2401.05441v2) | An adaptive network-based approach for advanced forecasting of cryptocurrency values |
| 2024 | [2405.00051v1](https://arxiv.org/abs/2405.00051v1) | Arbitrage impact on the relationship between XRP price and correlation tensor spectra of transaction networks |
| 2024 | [2403.00770v1](https://arxiv.org/abs/2403.00770v1) | Blockchain Metrics and Indicators in Cryptocurrency Trading |
| 2024 | [2402.14708v2](https://arxiv.org/abs/2402.14708v2) | CaT-GNN: Enhancing Credit Card Fraud Detection via Causal Temporal Graph Neural Networks |
| 2024 | [2403.14695v2](https://arxiv.org/abs/2403.14695v2) | Chain-structured neural architecture search for financial time series forecasting |
| 2024 | [2405.08089v1](https://arxiv.org/abs/2405.08089v1) | Comparative Study of Bitcoin Price Prediction |
| 2024 | [2402.08071v2](https://arxiv.org/abs/2402.08071v2) | Contagion on Financial Networks: An Introduction |
| 2024 | [2409.05547v3](https://arxiv.org/abs/2409.05547v3) | Critical Dynamics of Random Surfaces: Time Evolution of Area and Genus |
| 2024 | [2403.00775v1](https://arxiv.org/abs/2403.00775v1) | Detecting Anomalous Events in Object-centric Business Processes via Graph Neural Networks |
| 2024 | [2412.18202v6](https://arxiv.org/abs/2412.18202v6) | Developing Cryptocurrency Trading Strategy Based on Autoencoder-CNN-GANs Algorithms |
| 2024 | [2410.07216v1](https://arxiv.org/abs/2410.07216v1) | Evaluating Financial Relational Graphs: Interpretation Before Prediction |
| 2024 | [2411.05815v2](https://arxiv.org/abs/2411.05815v2) | Graph Neural Networks for Financial Fraud Detection: A Review |
| 2024 | [2404.00034v1](https://arxiv.org/abs/2404.00034v1) | Investigating Similarities Across Decentralized Financial (DeFi) Services |
| 2024 | [2409.08282v3](https://arxiv.org/abs/2409.08282v3) | LSR-IGRU: Stock Trend Prediction Based on Long Short-Term Relationships and Improved GRU |
| 2024 | [2409.06728v1](https://arxiv.org/abs/2409.06728v1) | Leveraging RNNs and LSTMs for Synchronization Analysis in the Indian Stock Market: A Threshold-Based Classification Approach |
| 2024 | [2410.20679v3](https://arxiv.org/abs/2410.20679v3) | MCI-GRU: Stock Prediction Model Based on Multi-Head Cross-Attention and Improved GRU |
| 2024 | [2402.06633v1](https://arxiv.org/abs/2402.06633v1) | MDGNN: Multi-Relational Dynamic Graph Neural Network for Comprehensive and Dynamic Stock Investment Prediction |
| 2024 | [2404.07179v1](https://arxiv.org/abs/2404.07179v1) | Machine learning-based similarity measure to forecast M&A from patent data |
| 2024 | [2402.18959v1](https://arxiv.org/abs/2402.18959v1) | MambaStock: Selective state space model for stock prediction |
| 2024 | [2411.12013v2](https://arxiv.org/abs/2411.12013v2) | Neural and Time-Series Approaches for Pricing Weather Derivatives: Performance and Regime Adaptation Using Satellite Data |
| 2024 | [2410.01843v1](https://arxiv.org/abs/2410.01843v1) | Optimizing Time Series Forecasting: A Comparative Study of Adam and Nesterov Accelerated Gradient on LSTM and GRU networks Using Stock Market data |
| 2024 | [2406.19399v1](https://arxiv.org/abs/2406.19399v1) | Predicting Customer Goals in Financial Institution Services: A Data-Driven LSTM Approach |
| 2024 | [2403.00774v2](https://arxiv.org/abs/2403.00774v2) | Regional inflation analysis using social network data |
| 2024 | [2405.11431v2](https://arxiv.org/abs/2405.11431v2) | Review of deep learning models for crypto price prediction: implementation and evaluation |
| 2024 | [2411.11848v1](https://arxiv.org/abs/2411.11848v1) | Robust Graph Neural Networks for Stability Analysis in Dynamic Networks |
| 2024 | [2410.07220v1](https://arxiv.org/abs/2410.07220v1) | Stock Price Prediction and Traditional Models: An Approach to Achieve Short-, Medium- and Long-Term Goals |
| 2024 | [2407.18519v1](https://arxiv.org/abs/2407.18519v1) | TCGPN: Temporal-Correlation Graph Pre-trained Network for Stock Forecasting |
| 2024 | [2404.00060v1](https://arxiv.org/abs/2404.00060v1) | Temporal Graph Networks for Graph Anomaly Detection in Financial Networks |
| 2024 | [2406.19403v1](https://arxiv.org/abs/2406.19403v1) | Temporal distribution of clusters of investors and their application in prediction with expert advice |
| 2024 | [2411.05829v1](https://arxiv.org/abs/2411.05829v1) | Utilizing RNN for Real-time Cryptocurrency Price Prediction and Trading Strategy Optimization |
| 2024 | [2403.14483v1](https://arxiv.org/abs/2403.14483v1) | Utilizing the LightGBM Algorithm for Operator User Credit Assessment Research |
| 2023 | [2311.06280v1](https://arxiv.org/abs/2311.06280v1) | A Data-driven Deep Learning Approach for Bitcoin Price Forecasting |
| 2023 | [2304.09761v1](https://arxiv.org/abs/2304.09761v1) | An innovative Deep Learning Based Approach for Accurate Agricultural Crop Price Prediction |
| 2023 | [2311.10719v1](https://arxiv.org/abs/2311.10719v1) | Analysis of frequent trading effects of various machine learning models |
| 2023 | [2307.16427v1](https://arxiv.org/abs/2307.16427v1) | Causal Inference for Banking Finance and Insurance A Survey |
| 2023 | [2303.16148v2](https://arxiv.org/abs/2303.16148v2) | Causal Modelling of Cryptocurrency Price Movements Using Discretisation-Aware Bayesian Networks |
| 2023 | [2305.17285v1](https://arxiv.org/abs/2305.17285v1) | Critical density for network reconstruction |
| 2023 | [2303.09397v1](https://arxiv.org/abs/2303.09397v1) | Cryptocurrency Price Prediction using Twitter Sentiment Analysis |
| 2023 | [2301.02027v3](https://arxiv.org/abs/2301.02027v3) | Cryptocurrency co-investment network: token returns reflect investment patterns |
| 2023 | [2302.08911v1](https://arxiv.org/abs/2302.08911v1) | DSE Stock Price Prediction using Hidden Markov Model |
| 2023 | [2305.04811v2](https://arxiv.org/abs/2305.04811v2) | Deep learning models for price forecasting of financial time series: A review of recent advancements: 2020-2022 |
| 2023 | [2311.07597v2](https://arxiv.org/abs/2311.07597v2) | Enhancing Actuarial Non-Life Pricing Models via Transformers |
| 2023 | [2305.04865v1](https://arxiv.org/abs/2305.04865v1) | Estimating the impact of supply chain network contagion on financial stability |
| 2023 | [2307.14409v2](https://arxiv.org/abs/2307.14409v2) | Exploring the Bitcoin Mesoscale |
| 2023 | [2306.12965v2](https://arxiv.org/abs/2306.12965v2) | Improved Financial Forecasting via Quantum Machine Learning |
| 2023 | [2301.10166v1](https://arxiv.org/abs/2301.10166v1) | Leveraging Vision-Language Models for Granular Market Change Prediction |
| 2023 | [2308.04947v1](https://arxiv.org/abs/2308.04947v1) | Methods for Acquiring and Incorporating Knowledge into Stock Price Prediction: A Survey |
| 2023 | [2305.14378v1](https://arxiv.org/abs/2305.14378v1) | Predicting Stock Market Time-Series Data using CNN-LSTM Neural Network Model |
| 2023 | [2303.10481v1](https://arxiv.org/abs/2303.10481v1) | Predictive Optimized Model on Money Markets Instruments With Capital Market and Bank Rates Ratio |
| 2023 | [2301.10153v1](https://arxiv.org/abs/2301.10153v1) | Sequential Graph Attention Learning for Predicting Dynamic Stock Trends (Student Abstract) |
| 2023 | [2307.09767v1](https://arxiv.org/abs/2307.09767v1) | Sig-Splines: universal approximation and convex calibration of time series generative models |
| 2023 | [2307.11846v2](https://arxiv.org/abs/2307.11846v2) | Social and individual learning in the Minority Game |
| 2023 | [2308.13061v1](https://arxiv.org/abs/2308.13061v1) | Spatial and Spatiotemporal Volatility Models: A Review |
| 2023 | [2302.14164v1](https://arxiv.org/abs/2302.14164v1) | Stock Broad-Index Trend Patterns Learning via Domain Knowledge Informed Generative Network |
| 2023 | [2310.16855v1](https://arxiv.org/abs/2310.16855v1) | Stock Market Directional Bias Prediction Using ML Algorithms |
| 2023 | [2306.12969v1](https://arxiv.org/abs/2306.12969v1) | Stock Price Prediction using Dynamic Neural Networks |
| 2023 | [2303.09323v1](https://arxiv.org/abs/2303.09323v1) | Stock Trend Prediction: A Semantic Segmentation Approach |
| 2023 | [2305.14382v1](https://arxiv.org/abs/2305.14382v1) | Stock and market index prediction using Informer network |
| 2023 | [2301.05693v1](https://arxiv.org/abs/2301.05693v1) | Stock market forecasting using DRAGAN and feature matching |
| 2023 | [2304.02094v1](https://arxiv.org/abs/2304.02094v1) | TM-vector: A Novel Forecasting Approach for Market stock movement with a Rich Representation of Twitter and Market data |
| 2023 | [2305.08740v1](https://arxiv.org/abs/2305.08740v1) | Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction |
| 2023 | [2307.08650v2](https://arxiv.org/abs/2307.08650v2) | Thailand Asset Value Estimation Using Aerial or Satellite Imagery |
| 2023 | [2304.00510v1](https://arxiv.org/abs/2304.00510v1) | The Tech Decoupling |
| 2023 | [2312.09654v2](https://arxiv.org/abs/2312.09654v2) | The cost of artificial latency in the PBS context |
| 2023 | [2309.13662v1](https://arxiv.org/abs/2309.13662v1) | Topology-Agnostic Detection of Temporal Money Laundering Flows in Billion-Scale Transactions |
| 2022 | [2201.12286v1](https://arxiv.org/abs/2201.12286v1) | A Stock Trading System for a Medium Volatile Asset using Multi Layer Perceptron |
| 2022 | [2207.02799v1](https://arxiv.org/abs/2207.02799v1) | A multi-task network approach for calculating discrimination-free insurance prices |
| 2022 | [2207.13914v3](https://arxiv.org/abs/2207.13914v3) | Anatomy of a Stablecoin's failure: the Terra-Luna case |
| 2022 | [2208.14385v2](https://arxiv.org/abs/2208.14385v2) | Application of Convolutional Neural Networks with Quasi-Reversibility Method Results for Option Forecasting |
| 2022 | [2204.02623v2](https://arxiv.org/abs/2204.02623v2) | Attention-based CNN-LSTM and XGBoost hybrid model for stock prediction |
| 2022 | [2207.11577v1](https://arxiv.org/abs/2207.11577v1) | Augmented Bilinear Network for Incremental Multi-Stock Time-Series Classification |
| 2022 | [2201.07737v1](https://arxiv.org/abs/2201.07737v1) | COVID-19 impact on the international trade |
| 2022 | [2203.15009v2](https://arxiv.org/abs/2203.15009v2) | DAMNETS: A Deep Autoregressive Model for Generating Markovian Network Time Series |
| 2022 | [2206.03386v3](https://arxiv.org/abs/2206.03386v3) | Dependency structures in cryptocurrency market from high to low frequency |
| 2022 | [2207.10476v2](https://arxiv.org/abs/2207.10476v2) | Efficiency of the Moscow Stock Exchange before 2022 |
| 2022 | [2204.00883v1](https://arxiv.org/abs/2204.00883v1) | Electricity Price Forecasting: The Dawn of Machine Learning |
| 2022 | [2210.00876v1](https://arxiv.org/abs/2210.00876v1) | Embedding-based neural network for investment return prediction |
| 2022 | [2204.12914v3](https://arxiv.org/abs/2204.12914v3) | Forecasting foreign exchange rates with regression networks tuned by Bayesian optimization |
| 2022 | [2203.15470v1](https://arxiv.org/abs/2203.15470v1) | Graph similarity learning for change-point detection in dynamic networks |
| 2022 | [2211.00948v2](https://arxiv.org/abs/2211.00948v2) | Inflexible Multi-Asset Hedging of incomplete market |
| 2022 | [2203.10465v4](https://arxiv.org/abs/2203.10465v4) | Inspection-L: Self-Supervised GNN Node Embeddings for Money Laundering Detection in Bitcoin |
| 2022 | [2206.08401v5](https://arxiv.org/abs/2206.08401v5) | Is Decentralized Finance Actually Decentralized? An Interdisciplinary Framework Integrating Network Theory, Agent-Based Simulation, and Longitudinal Evidence from Aave, GHO Issuance, and Cross-Chain Expansion |
| 2022 | [2201.08218v1](https://arxiv.org/abs/2201.08218v1) | Long Short-Term Memory Neural Network for Financial Time Series |
| 2022 | [2207.01151v3](https://arxiv.org/abs/2207.01151v3) | Modeling Randomly Walking Volatility with Chained Gamma Distributions |
| 2022 | [2208.14311v4](https://arxiv.org/abs/2208.14311v4) | Modeling Volatility and Dependence of European Carbon and Energy Prices |
| 2022 | [2210.16679v1](https://arxiv.org/abs/2210.16679v1) | Monitoring the Dynamic Networks of Stock Returns |
| 2022 | [2212.05916v1](https://arxiv.org/abs/2212.05916v1) | NETpred: Network-based modeling and prediction of multiple connected market indices |
| 2022 | [2204.12932v1](https://arxiv.org/abs/2204.12932v1) | NFT Appraisal Prediction: Utilizing Search Trends, Public Market Data, Linear Regression and Recurrent Neural Networks |
| 2022 | [2201.07214v1](https://arxiv.org/abs/2201.07214v1) | Opinion Dynamics in Financial Markets via Random Networks |
| 2022 | [2207.07315v1](https://arxiv.org/abs/2207.07315v1) | Pattern Analysis of Money Flow in the Bitcoin Blockchain |
| 2022 | [2204.06109v1](https://arxiv.org/abs/2204.06109v1) | Prediction of motor insurance claims occurrence as an imbalanced machine learning problem |
| 2022 | [2204.09568v1](https://arxiv.org/abs/2204.09568v1) | Predictive Accuracy of a Hybrid Generalized Long Memory Model for Short Term Electricity Price Forecasting |
| 2022 | [2205.11439v1](https://arxiv.org/abs/2205.11439v1) | Probabilistic forecasting of German electricity imbalance prices |
| 2022 | [2209.09157v1](https://arxiv.org/abs/2209.09157v1) | RESHAPE: Explaining Accounting Anomalies in Financial Statement Audits by enhancing SHapley Additive exPlanations |
| 2022 | [2206.00568v1](https://arxiv.org/abs/2206.00568v1) | RMT-Net: Reject-aware Multi-Task Network for Modeling Missing-not-at-random Data in Financial Credit Scoring |
| 2022 | [2209.01378v3](https://arxiv.org/abs/2209.01378v3) | RNN(p) for Power Consumption Forecasting |
| 2022 | [2208.03456v1](https://arxiv.org/abs/2208.03456v1) | Recurrence measures and transitions in stock market dynamics |
| 2022 | [2204.12929v2](https://arxiv.org/abs/2204.12929v2) | Sequence-Based Target Coin Prediction for Cryptocurrency Pump-and-Dump |
| 2022 | [2207.00493v1](https://arxiv.org/abs/2207.00493v1) | Simulating financial time series using attention |
| 2022 | [2205.04256v6](https://arxiv.org/abs/2205.04256v6) | SoK: Blockchain Decentralization |
| 2022 | [2208.13564v1](https://arxiv.org/abs/2208.13564v1) | Stock Market Prediction using Natural Language Processing -- A Survey |
| 2022 | [2201.04965v2](https://arxiv.org/abs/2201.04965v2) | Stock Movement Prediction Based on Bi-typed Hybrid-relational Market Knowledge Graph via Dual Attention Networks |
| 2022 | [2208.07254v1](https://arxiv.org/abs/2208.07254v1) | The Efficient Market Hypothesis for Bitcoin in the context of neural networks |
| 2022 | [2201.00350v5](https://arxiv.org/abs/2201.00350v5) | The Interpretability of LSTM Models for Predicting Oil Company Stocks: Impact of Correlated Features |
| 2022 | [2203.13001v1](https://arxiv.org/abs/2203.13001v1) | The application of techniques derived from artificial intelligence to the prediction of the solvency of bank customers: case of the application of the cart type decision tree (dt) |
| 2022 | [2212.05369v1](https://arxiv.org/abs/2212.05369v1) | Time Series Analysis in American Stock Market Recovering in Post COVID-19 Pandemic Period |
| 2022 | [2210.16863v2](https://arxiv.org/abs/2210.16863v2) | Time-aware Metapath Feature Augmentation for Ponzi Detection in Ethereum |
| 2021 | [2111.08060v1](https://arxiv.org/abs/2111.08060v1) | A Multi-criteria Approach to Evolve Sparse Neural Architectures for Stock Market Forecasting |
| 2021 | [2111.15367v2](https://arxiv.org/abs/2111.15367v2) | A Review on Graph Neural Network Methods in Financial Applications |
| 2021 | [2103.09750v1](https://arxiv.org/abs/2103.09750v1) | A Survey of Forex and Stock Price Prediction Using Deep Learning |
| 2021 | [2111.15354v1](https://arxiv.org/abs/2111.15354v1) | An Improved Reinforcement Learning Model Based on Sentiment Analysis |
| 2021 | [2110.12000v3](https://arxiv.org/abs/2110.12000v3) | Bank transactions embeddings help to uncover current macroeconomics |
| 2021 | [2109.00983v1](https://arxiv.org/abs/2109.00983v1) | Bilinear Input Normalization for Neural Networks in Financial Forecasting |
| 2021 | [2104.04041v1](https://arxiv.org/abs/2104.04041v1) | CLVSA: A Convolutional LSTM Based Variational Sequence-to-Sequence Model with Attention for Predicting Trends of Financial Markets |
| 2021 | [2101.02287v2](https://arxiv.org/abs/2101.02287v2) | COVID19-HPSMP: COVID-19 Adopted Hybrid and Parallel Deep Information Fusion Framework for Stock Price Movement Prediction |
| 2021 | [2105.10871v1](https://arxiv.org/abs/2105.10871v1) | Financial Time Series Analysis and Forecasting with HHT Feature Generation and Machine Learning |
| 2021 | [2101.03087v2](https://arxiv.org/abs/2101.03087v2) | Forecasting Commodity Prices Using Long Short-Term Memory Neural Networks |
| 2021 | [2103.14080v1](https://arxiv.org/abs/2103.14080v1) | Forecasting with Deep Learning: S&P 500 index |
| 2021 | [2112.03946v1](https://arxiv.org/abs/2112.03946v1) | Generative Adversarial Network (GAN) and Enhanced Root Mean Square Error (ERMSE): Deep Learning for Stock Price Movement Prediction |
| 2021 | [2107.11059v1](https://arxiv.org/abs/2107.11059v1) | LocalGLMnet: interpretable deep learning for tabular data |
| 2021 | [2106.00647v4](https://arxiv.org/abs/2106.00647v4) | Mapping the NFT revolution: market trends, trade networks and visual features |
| 2021 | [2108.10065v1](https://arxiv.org/abs/2108.10065v1) | Previsão dos preços de abertura, mínima e máxima de índices de mercados financeiros usando a associação de redes neurais LSTM |
| 2021 | [2106.02522v5](https://arxiv.org/abs/2106.02522v5) | Price graphs: Utilizing the structural information of financial time series for stock prediction |
| 2021 | [2104.06259v1](https://arxiv.org/abs/2104.06259v1) | Profitability Analysis in Stock Investment Using an LSTM-Based Deep Learning Model |
| 2021 | [2104.07260v1](https://arxiv.org/abs/2104.07260v1) | Quantifying firm-level economic systemic risk from nation-wide supply networks |
| 2021 | [2103.09107v1](https://arxiv.org/abs/2103.09107v1) | Randentropy: a software to measure inequality in random systems |
| 2021 | [2103.14081v1](https://arxiv.org/abs/2103.14081v1) | Stock price forecast with deep learning |
| 2020 | [2008.09667v1](https://arxiv.org/abs/2008.09667v1) | A Blockchain Transaction Graph based Machine Learning Method for Bitcoin Price Prediction |
| 2020 | [2004.11697v2](https://arxiv.org/abs/2004.11697v2) | A Time Series Analysis-Based Stock Price Prediction Using Machine Learning and Deep Learning Models |
| 2020 | [2003.01859v1](https://arxiv.org/abs/2003.01859v1) | Applications of deep learning in stock market prediction: recent progress |
| 2020 | [2007.15475v1](https://arxiv.org/abs/2007.15475v1) | Connecting actuarial judgment to probabilistic learning techniques with graph theory |
| 2020 | [2002.06405v1](https://arxiv.org/abs/2002.06405v1) | Deep Learning for Asset Bubbles Detection |
| 2020 | [2004.01498v1](https://arxiv.org/abs/2004.01498v1) | Deep Probabilistic Modelling of Price Movements for High-Frequency Trading |
| 2020 | [2004.01497v1](https://arxiv.org/abs/2004.01497v1) | Deep learning for Stock Market Prediction |
| 2020 | [2007.00017v2](https://arxiv.org/abs/2007.00017v2) | Dynamic Portfolio Optimization with Real Datasets Using Quantum Processors and Quantum-Inspired Tensor Networks |
| 2020 | [2010.15111v1](https://arxiv.org/abs/2010.15111v1) | Evaluating data augmentation for financial time series classification |
| 2020 | [2004.05325v1](https://arxiv.org/abs/2004.05325v1) | Evolving efficiency and robustness of global oil trade networks |
| 2020 | [2004.01502v1](https://arxiv.org/abs/2004.01502v1) | Financial Market Trend Forecasting and Performance Analysis Using LSTM |
| 2020 | [2001.01127v1](https://arxiv.org/abs/2001.01127v1) | Forecasting Bitcoin closing price series using linear regression and neural networks models |
| 2020 | [2002.10247v1](https://arxiv.org/abs/2002.10247v1) | Forecasting Foreign Exchange Rate: A Multivariate Comparative Analysis between Traditional Econometric, Contemporary Machine Learning & Deep Learning Techniques |
| 2020 | [2004.07290v2](https://arxiv.org/abs/2004.07290v2) | From code to market: Network of developers and correlated returns of cryptocurrencies |
| 2020 | [2010.08400v1](https://arxiv.org/abs/2010.08400v1) | Hybrid Modelling Approaches for Forecasting Energy Spot Prices in EPEC market |
| 2020 | [2007.02673v1](https://arxiv.org/abs/2007.02673v1) | Impact of COVID-19 on Forecasting Stock Prices: An Integration of Stationary Wavelet Transform and Bidirectional Long Short-Term Memory |
| 2020 | [2011.01961v1](https://arxiv.org/abs/2011.01961v1) | Insights into Fairness through Trust: Multi-scale Trust Quantification for Financial Deep Learning |
| 2020 | [2007.03980v4](https://arxiv.org/abs/2007.03980v4) | Interdependencies of female board member appointments |
| 2020 | [2007.06848v1](https://arxiv.org/abs/2007.06848v1) | Modeling Financial Time Series using LSTM with Trainable Initial Hidden States |
| 2020 | [2007.14630v2](https://arxiv.org/abs/2007.14630v2) | Money flow network among firms' accounts in a regional bank of Japan |
| 2020 | [2005.04955v3](https://arxiv.org/abs/2005.04955v3) | Multi-Graph Convolutional Network for Relationship-Driven Stock Movement Prediction |
| 2020 | [2010.15403v2](https://arxiv.org/abs/2010.15403v2) | Multiscale characteristics of the emerging global cryptocurrency market |
| 2020 | [2004.00201v1](https://arxiv.org/abs/2004.00201v1) | NetDP: An Industrial-Scale Distributed Network Representation Framework for Default Prediction in Ant Credit Pay |
| 2020 | [2008.08006v1](https://arxiv.org/abs/2008.08006v1) | Neural networks in day-ahead electricity price forecasting: Single vs. multiple outputs |
| 2020 | [2011.08011v2](https://arxiv.org/abs/2011.08011v2) | Robust Analysis of Stock Price Time Series Using CNN and LSTM-Based Deep Learning Models |
| 2020 | [2008.11788v1](https://arxiv.org/abs/2008.11788v1) | Share Price Prediction of Aerospace Relevant Companies with Recurrent Neural Networks based on PCA |
| 2020 | [2009.06221v2](https://arxiv.org/abs/2009.06221v2) | Spearman's footrule and Gini's gamma: Local bounds for bivariate copulas and the exact region with respect to Blomqvist's beta |
| 2020 | [2001.09769v1](https://arxiv.org/abs/2001.09769v1) | Stock Price Prediction Using Convolutional Neural Networks on a Multivariate Timeseries |
| 2020 | [2009.10819v1](https://arxiv.org/abs/2009.10819v1) | Stock Price Prediction Using Machine Learning and LSTM-Based Deep Learning Models |
| 2020 | [2004.06676v1](https://arxiv.org/abs/2004.06676v1) | The interdependency structure in the Mexican stock exchange: A network approach |
| 2020 | [2008.07836v2](https://arxiv.org/abs/2008.07836v2) | Unveiling the directional network behind the financial statements data using volatility constraint correlation |
| 2020 | [2002.02271v1](https://arxiv.org/abs/2002.02271v1) | Using generative adversarial networks to synthesize artificial financial datasets |
| 2020 | [2007.12880v1](https://arxiv.org/abs/2007.12880v1) | Visibility graph analysis of economy policy uncertainty indices |
| 2019 | [1901.09143v1](https://arxiv.org/abs/1901.09143v1) | A Study on Neural Network Architecture Applied to the Prediction of Brazilian Stock Returns |
| 2019 | [1905.04370v1](https://arxiv.org/abs/1905.04370v1) | A Three-state Opinion Formation Model for Financial Markets |
| 2019 | [1912.03556v1](https://arxiv.org/abs/1912.03556v1) | A percolation model for the emergence of the Bitcoin Lightning Network |
| 2019 | [1912.04009v2](https://arxiv.org/abs/1912.04009v2) | An empirical study of neural networks for trend detection in time series |
| 2019 | [1906.03305v1](https://arxiv.org/abs/1906.03305v1) | Clustering Degree-Corrected Stochastic Block Model with Outliers |
| 2019 | [1907.01119v1](https://arxiv.org/abs/1907.01119v1) | Comparative analysis of layered structures in empirical investor networks and cellphone communication networks |
| 2019 | [1905.07581v1](https://arxiv.org/abs/1905.07581v1) | Convolutional Feature Extraction and Neural Arithmetic Logic Units for Stock Prediction |
| 2019 | [1903.01655v1](https://arxiv.org/abs/1903.01655v1) | Cross-shareholding networks and stock price synchronicity: Evidence from China |
| 2019 | [1910.12281v1](https://arxiv.org/abs/1910.12281v1) | Deep convolutional autoencoder for cryptocurrency market analysis |
| 2019 | [1912.10105v1](https://arxiv.org/abs/1912.10105v1) | Dissecting Ethereum Blockchain Analytics: What We Learn from Topology and Geometry of Ethereum Graph |
| 2019 | [1910.09153v1](https://arxiv.org/abs/1910.09153v1) | Entropic Dynamic Time Warping Kernels for Co-evolving Financial Time Series Analysis |
| 2019 | [1902.10877v1](https://arxiv.org/abs/1902.10877v1) | Financial series prediction using Attention LSTM |
| 2019 | [1904.11145v1](https://arxiv.org/abs/1904.11145v1) | Forecasting in Big Data Environments: an Adaptable and Automated Shrinkage Estimation of Neural Networks (AAShNet) |
| 2019 | [1910.11216v2](https://arxiv.org/abs/1910.11216v2) | Fragmentation of Distributed Exchanges |
| 2019 | [1902.10948v1](https://arxiv.org/abs/1902.10948v1) | Global Stock Market Prediction Based on Stock Chart Images Using Deep Q-Network |
| 2019 | [1909.09563v1](https://arxiv.org/abs/1909.09563v1) | Gradient Boost with Convolution Neural Network for Stock Forecast |
| 2019 | [1908.07999v3](https://arxiv.org/abs/1908.07999v3) | HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction |
| 2019 | [1902.03125v2](https://arxiv.org/abs/1902.03125v2) | High-performance stock index trading: making effective use of a deep LSTM neural network |
| 2019 | [1904.09214v1](https://arxiv.org/abs/1904.09214v1) | Inefficiency of the Brazilian Stock Market: the IBOVESPA Future Contracts |
| 2019 | [1906.06248v3](https://arxiv.org/abs/1906.06248v3) | Machine Learning on EPEX Order Books: Insights and Forecasts |
| 2019 | [1906.10121v3](https://arxiv.org/abs/1906.10121v3) | Metaheuristics optimized feedforward neural networks for efficient stock price prediction |
| 2019 | [1904.05317v1](https://arxiv.org/abs/1904.05317v1) | On the Co-movement of Crude, Gold Prices and Stock Index in Indian Market |
| 2019 | [1910.08627v2](https://arxiv.org/abs/1910.08627v2) | On the quantum behavior and clustering properties of correlated financial portfolios |
| 2019 | [1911.03467v1](https://arxiv.org/abs/1911.03467v1) | Relation between Blomqvist's beta and other measures of concordance of copulas |
| 2019 | [1909.06648v2](https://arxiv.org/abs/1909.06648v2) | Relation between non-exchangeability and measures of concordance of copulas |
| 2019 | [1912.04015v2](https://arxiv.org/abs/1912.04015v2) | Sanction or Financial Crisis? An Artificial Neural Network-Based Approach to model the impact of oil price volatility on Stock and industry indices |
| 2019 | [1908.11212v1](https://arxiv.org/abs/1908.11212v1) | Stock Price Forecasting and Hypothesis Testing Using Neural Networks |
| 2019 | [1906.03232v2](https://arxiv.org/abs/1906.03232v2) | Style Transfer with Time Series: Generating Synthetic Financial Data |
| 2019 | [1909.08964v1](https://arxiv.org/abs/1909.08964v1) | To Detect Irregular Trade Behaviors In Stock Market By Using Graph Based Ranking Methods |
| 2019 | [1909.12946v2](https://arxiv.org/abs/1909.12946v2) | Towards Federated Graph Learning for Collaborative Financial Crimes Detection |
| 2019 | [1903.12258v1](https://arxiv.org/abs/1903.12258v1) | Using Deep Learning Neural Networks and Candlestick Chart Representation to Predict Stock Market |
| 2018 | [1802.05326v1](https://arxiv.org/abs/1802.05326v1) | Analysis of Financial Credit Risk Using Machine Learning |
| 2018 | [1805.12111v4](https://arxiv.org/abs/1805.12111v4) | Dynamic Advisor-Based Ensemble (dynABE): Case study in stock trend prediction of critical metal companies |
| 2018 | [1808.08585v1](https://arxiv.org/abs/1808.08585v1) | Evolutionary dynamics of cryptocurrency transaction networks: An empirical study |
| 2018 | [1804.02350v2](https://arxiv.org/abs/1804.02350v2) | From Bitcoin to Bitcoin Cash: a network analysis |
| 2018 | [1807.09346v1](https://arxiv.org/abs/1807.09346v1) | Investigating the configurations in cross-shareholding: a joint copula-entropy approach |
| 2018 | [1805.11317v1](https://arxiv.org/abs/1805.11317v1) | Neural networks for stock price prediction |
| 2018 | [1801.07960v1](https://arxiv.org/abs/1801.07960v1) | Stock returns forecast: an examination by means of Artificial Neural Networks |
| 2018 | [1801.02205v1](https://arxiv.org/abs/1801.02205v1) | The Network of U.S. Mutual Fund Investments: Diversification, Similarity and Fragility throughout the Global Financial Crisis |
| 2017 | [1801.00185v1](https://arxiv.org/abs/1801.00185v1) | A dynamic network model with persistent links and node-specific latent variables, with an application to the interbank market |
| 2017 | [1711.04174v1](https://arxiv.org/abs/1711.04174v1) | Financial Time Series Prediction Using Deep Learning |
| 2017 | [1708.07061v3](https://arxiv.org/abs/1708.07061v3) | Forecasting day-ahead electricity prices in Europe: the importance of considering market integration |
| 2017 | [1706.09240v3](https://arxiv.org/abs/1706.09240v3) | Local fluctuations of the signed traded volumes and the dependencies of demands: a copula analysis |
| 2017 | [1704.05499v1](https://arxiv.org/abs/1704.05499v1) | Quantifying instabilities in Financial Markets |
| 2017 | [1703.10832v2](https://arxiv.org/abs/1703.10832v2) | Social dynamics of financial networks |
| 2016 | [1610.00795v2](https://arxiv.org/abs/1610.00795v2) | A dynamic approach merging network theory and credit risk techniques to assess systemic risk in financial networks |
| 2016 | [1602.03271v1](https://arxiv.org/abs/1602.03271v1) | A study of co-movements between oil price, stock index and exchange rate under a cross-bicorrelation perspective: the case of Mexico |
| 2016 | [1607.02093v1](https://arxiv.org/abs/1607.02093v1) | Artificial Neural Network and Time Series Modeling Based Approach to Forecasting the Exchange Rate in a Multivariate Framework |
| 2016 | [1608.03058v1](https://arxiv.org/abs/1608.03058v1) | Dynamic portfolio strategy using clustering approach |
| 2016 | [1612.02666v1](https://arxiv.org/abs/1612.02666v1) | Evaluating the Performance of ANN Prediction System at Shanghai Stock Market in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2016 | [1608.01103v1](https://arxiv.org/abs/1608.01103v1) | Fluctuation of USA Gold Price - Revisited with Chaos-based Complex Network Method |
| 2016 | [1608.07694v1](https://arxiv.org/abs/1608.07694v1) | Foreign Exchange Market Performance: Evidence from Bivariate Time Series Approach |
| 2016 | [1610.09812v1](https://arxiv.org/abs/1610.09812v1) | Long-range Correlation and Market Segmentation in Bond Market |
| 2016 | [1601.07707v1](https://arxiv.org/abs/1601.07707v1) | Micro-foundation using percolation theory of the finite-time singular behavior of the crash hazard rate in a class of rational expectation bubbles |
| 2016 | [1602.01960v1](https://arxiv.org/abs/1602.01960v1) | Multiple Wavelet Coherency Analysis and Forecasting of Metal Prices |
| 2016 | [1609.00926v3](https://arxiv.org/abs/1609.00926v3) | Multivariate Mixed Tempered Stable Distribution |
| 2016 | [1609.05394v1](https://arxiv.org/abs/1609.05394v1) | Predicting Future Shanghai Stock Market Price using ANN in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2016 | [1606.02871v1](https://arxiv.org/abs/1606.02871v1) | The study of Thai stock market across the 2008 financial crisis |
| 2016 | [1601.00263v1](https://arxiv.org/abs/1601.00263v1) | Time and Frequency Structure of Causal Correlation Network in China Bond Market |
| 2016 | [1610.04334v1](https://arxiv.org/abs/1610.04334v1) | Time-Varying Comovement of Foreign Exchange Markets |
| 2015 | [1507.05687v1](https://arxiv.org/abs/1507.05687v1) | A General Framework for Complex Network Applications |
| 2015 | [1503.06926v1](https://arxiv.org/abs/1503.06926v1) | A study of co-movements between USA and Latin American stock markets: a cross-bicorrelations perspective |
| 2015 | [1502.05603v2](https://arxiv.org/abs/1502.05603v2) | Assessment of 48 Stock markets using adaptive multifractal approach |
| 2015 | [1507.01901v1](https://arxiv.org/abs/1507.01901v1) | Banking Networks and Leverage Dependence: Evidence from Selected Emerging Countries |
| 2015 | [1507.03278v1](https://arxiv.org/abs/1507.03278v1) | Contagion effects in the world network of economic activities |
| 2015 | [1511.08830v1](https://arxiv.org/abs/1511.08830v1) | Disentangling bipartite and core-periphery structure in financial networks |
| 2015 | [1501.03371v1](https://arxiv.org/abs/1501.03371v1) | Google matrix analysis of the multiproduct world trade network |
| 2015 | [1504.06773v1](https://arxiv.org/abs/1504.06773v1) | Google matrix of the world network of economic activities |
| 2015 | [1503.00823v1](https://arxiv.org/abs/1503.00823v1) | Influence network in Chinese stock market |
| 2015 | [1510.04690v1](https://arxiv.org/abs/1510.04690v1) | On Capturing the Spreading Dynamics over Trading Prices in the Market |
| 2015 | [1501.04682v3](https://arxiv.org/abs/1501.04682v3) | Toward robust early-warning models: A horse race, ensembles and model uncertainty |
| 2014 | [1502.06434v1](https://arxiv.org/abs/1502.06434v1) | ANN Model to Predict Stock Prices at Stock Exchange Markets |
| 2014 | [1409.6193v3](https://arxiv.org/abs/1409.6193v3) | Estimating topological properties of weighted networks from limited information |
| 2014 | [1406.7064v1](https://arxiv.org/abs/1406.7064v1) | Hierarchical Structure of the Foreign Trade: The Case of the United State |
| 2014 | [1401.2548v1](https://arxiv.org/abs/1401.2548v1) | Mutual Information Rate-Based Networks in Financial Markets |
| 2014 | [1403.3638v1](https://arxiv.org/abs/1403.3638v1) | Networked relationships in the e-MID Interbank market: A trading model with memory |
| 2014 | [1411.7613v2](https://arxiv.org/abs/1411.7613v2) | Systemic risk analysis in reconstructed economic and financial networks |
| 2014 | [1411.1689v1](https://arxiv.org/abs/1411.1689v1) | Universality of Tsallis q-exponential of interoccurrence times within the microscopic model of cunning agents |
| 2013 | [1310.2446v3](https://arxiv.org/abs/1310.2446v3) | A statistical physics perspective on criticality in financial markets |
| 2013 | [1309.4050v2](https://arxiv.org/abs/1309.4050v2) | Analytical solution for a class of network dynamics with mechanical and financial applications |
| 2013 | [1310.1634v2](https://arxiv.org/abs/1310.1634v2) | Cascades in real interbank markets |
| 2013 | [1311.5101v1](https://arxiv.org/abs/1311.5101v1) | Copulas and time series with long-ranged dependences |
| 2013 | [1311.2273v1](https://arxiv.org/abs/1311.2273v1) | Measures of uncertainty in market network analysis |
| 2013 | [1309.5073v1](https://arxiv.org/abs/1309.5073v1) | Non-linear dependences in finance |
| 2013 | [1311.5753v3](https://arxiv.org/abs/1311.5753v3) | Nucleation, condensation and lambda-transition on a real-life stock market |
| 2013 | [1307.4821v1](https://arxiv.org/abs/1307.4821v1) | Power-law exponent of the Bouchaud-Mézard model on regular random network |
| 2013 | [1308.0925v1](https://arxiv.org/abs/1308.0925v1) | Unveiling correlations between financial variables and topological metrics of trading networks: Evidence from a stock and its warrant |
| 2013 | [1310.6819v1](https://arxiv.org/abs/1310.6819v1) | Valuing FtD Contract under Copula Approach via Monte-Carlo Stimulation |
| 2012 | [1209.2467v1](https://arxiv.org/abs/1209.2467v1) | Bouchaud-Mézard model on a random network |
| 2012 | [1208.2696v1](https://arxiv.org/abs/1208.2696v1) | Distribution Of Wealth In A Network Model Of The Economy |
| 2012 | [1211.3599v1](https://arxiv.org/abs/1211.3599v1) | Network analysis of correlation strength between the most developed countries |
| 2012 | [1207.5269v1](https://arxiv.org/abs/1207.5269v1) | Structural distortions in the Euro interbank market: The role of 'key players' during the recent market turmoil |
| 2012 | [1209.2781v2](https://arxiv.org/abs/1209.2781v2) | Wealth distribution on complex networks |
| 2011 | [1107.3456v2](https://arxiv.org/abs/1107.3456v2) | Exploring complex networks via topological embedding on surfaces |
| 2011 | [1112.5711v1](https://arxiv.org/abs/1112.5711v1) | The topology of cross-border exposures: beyond the minimal spanning tree approach |
| 2010 | [1004.4402v2](https://arxiv.org/abs/1004.4402v2) | Characteristics of Real Futures Trading Networks |
| 2010 | [1011.4336v2](https://arxiv.org/abs/1011.4336v2) | Impact of the topology of global macroeconomic network on the spreading of economic crises |
| 2010 | [1002.0917v1](https://arxiv.org/abs/1002.0917v1) | Statistical properties of agent-based models in markets with continuous double auction mechanism |
| 2009 | [0902.1576v3](https://arxiv.org/abs/0902.1576v3) | A Paradigm Shift from Production Function to Production Copula: Statistical Description of Production Activity of Firms |
| 2009 | [0901.2384v2](https://arxiv.org/abs/0901.2384v2) | An Analysis of the Japanese Credit Network |
| 2009 | [0905.4272v1](https://arxiv.org/abs/0905.4272v1) | Complementarity between private and public investment in R&D: A Dynamic Panel Data analysis |
| 2009 | [0909.1974v2](https://arxiv.org/abs/0909.1974v2) | Econophysics: Empirical facts and agent-based models |
| 2009 | [0911.3045v1](https://arxiv.org/abs/0911.3045v1) | Sign and amplitude representation of the forex networks |
| 2009 | [0901.2377v3](https://arxiv.org/abs/0901.2377v3) | Structure and temporal change of the credit network between banks and large firms in Japan |
| 2009 | [0910.2524v1](https://arxiv.org/abs/0910.2524v1) | Universal and nonuniversal allometric scaling behaviors in the visibility graphs of world stock market indices |
| 2009 | [0901.2381v1](https://arxiv.org/abs/0901.2381v1) | Visualizing a large-scale structure of production network by N-body simulation |
| 2008 | [0801.3047v1](https://arxiv.org/abs/0801.3047v1) | Econometrics as Sorcery |
| 2008 | [0806.2989v2](https://arxiv.org/abs/0806.2989v2) | How to grow a bubble: A model of myopic adapting agents |
| 2008 | [0804.2441v2](https://arxiv.org/abs/0804.2441v2) | Topological identification in networks of dynamical systems |
| 2007 | [0705.0503v1](https://arxiv.org/abs/0705.0503v1) | Change point estimation for the telegraph process observed at discrete times |
| 2007 | [physics/0703128v2](https://arxiv.org/abs/physics/0703128v2) | Fluctuation scaling versus gap scaling |
| 2007 | [0705.2551v1](https://arxiv.org/abs/0705.2551v1) | Network Topology of an Experimental Futures Exchange |
| 2007 | [physics/0701156v2](https://arxiv.org/abs/physics/0701156v2) | Structurally dynamic spin market networks |
| 2006 | [physics/0611147v1](https://arxiv.org/abs/physics/0611147v1) | Networks of companies and branches in Poland |
| 2006 | [physics/0612068v2](https://arxiv.org/abs/physics/0612068v2) | Topological Properties of the Minimal Spanning Tree in Korean and American Stock Markets |
| 2005 | [physics/0506103v1](https://arxiv.org/abs/physics/0506103v1) | Boltzmann-Gibbs Distribution of Fortune and Broken Time-Reversible Symmetry in Econodynamics |
| 2005 | [physics/0509090v2](https://arxiv.org/abs/physics/0509090v2) | Effects of the globalization in the Korean financial markets |
| 2003 | [cond-mat/0304469v1](https://arxiv.org/abs/cond-mat/0304469v1) | Using Recurrent Neural Networks To Forecasting of Forex |
| 2002 | [cond-mat/0205482v1](https://arxiv.org/abs/cond-mat/0205482v1) | Financial multifractality and its subtleties: an example of DAX |
| 2002 | [cond-mat/0203256v2](https://arxiv.org/abs/cond-mat/0203256v2) | Time dependent cross correlations between different stock returns: A directed network of influence |
| 2001 | [cond-mat/0108068v1](https://arxiv.org/abs/cond-mat/0108068v1) | Decomposing the stock market intraday dynamics |
| 2001 | [cond-mat/0112271v1](https://arxiv.org/abs/cond-mat/0112271v1) | Identifying Complexity by Means of Matrices |
| 2001 | [nlin/0107057v3](https://arxiv.org/abs/nlin/0107057v3) | On multifractality and fractional derivatives |
| 2001 | [cond-mat/0110201v1](https://arxiv.org/abs/cond-mat/0110201v1) | Stability of money: Phase transitions in an Ising economy |
| 2000 | [cond-mat/0009287v2](https://arxiv.org/abs/cond-mat/0009287v2) | Money and Goldstone modes |
| 1999 | [cond-mat/9903144v1](https://arxiv.org/abs/cond-mat/9903144v1) | Markovian approximation in foreign exchange markets |
| 1997 | [cond-mat/9705087v1](https://arxiv.org/abs/cond-mat/9705087v1) | Scaling in stock market data: stable laws and beyond |

