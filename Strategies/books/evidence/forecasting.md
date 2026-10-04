# Evidence pack — Return, Price & Time-Series Forecasting (`forecasting`)

Annotated sweep rows for this category: **1567** (high 168 · med 830 · low 569).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (168)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2608.14014v1](https://arxiv.org/abs/2608.14014v1) | Tests rumor-buying/news-selling on 4.57M articles; the news move concentrates before and at publication (2.8x by publication close versus twenty days later), and markets underreact to numbers but overreact to stories. | strategies/events.py |
| 2026 | [2602.00082v1](https://arxiv.org/abs/2602.00082v1) | LLM multi-agent framework (announcement, event, momentum, market analysts plus prediction and decision agents) for Chinese public REITs; both DeepSeek-R1 and fine-tuned Qwen3-8B beat buy-and-hold on return, Sharpe and drawdown. | `tradingagents/graph/trading_graph.py` |
| 2026 | [2608.23808v2](https://arxiv.org/abs/2608.23808v2) | MinervaScore grades post-selection robustness from Deflated Sharpe, PBO, SPA, Minimum Track Record Length and regime stability; on 359,062 records it separates real signal from lucky backtests at AUROC 0.989. | strategies/evaluate.py |
| 2026 | [2607.01377v1](https://arxiv.org/abs/2607.01377v1) | Estimates Kyle's price-impact coefficient λ from daily CRSP order flow (2020-2025); signed order flow predicts contemporaneous and one-month-ahead returns, and an adverse-selection mechanism resolves the liquidity-premium puzzle without risk-based compensation. | strategies/liquidity_risk.py |
| 2026 | [2608.07479v2](https://arxiv.org/abs/2608.07479v2) | Shows conformal residual pooling carries a permanent logarithmic-score regret alongside valid coverage; gives the exact information-gap size as an oracle adversary's betting growth rate. | strategies/conformal.py |
| 2026 | [2605.24285v1](https://arxiv.org/abs/2605.24285v1) | Combines long-memory estimation, rough-volatility diagnostics and persistence regressions on 115 S&P500 names; GPH d=0.226, local-Whittle d=0.440; persistence rises in crises and with VIX. | strategies/long_memory.py |
| 2026 | [2605.20142v1](https://arxiv.org/abs/2605.20142v1) | Mixture of mirrored Weibull distributions models stock returns and VaR; outperforms Gaussian-mixture and t-mixture models in VaR estimation on three S&P500 stocks. | strategies/book_risk.py |
| 2026 | [2603.17463v2](https://arxiv.org/abs/2603.17463v2) | Forecast reconciliation combining univariate and multivariate portfolio-variance forecasts beats a standard multivariate GARCH approach, especially under misspecification, though noisy covariance proxies limit model discrimination. | `strategies/covariance_models.py` |
| 2026 | [2601.07687v4](https://arxiv.org/abs/2601.07687v4) | Physics-informed neural estimator cleans cross-covariance matrices by learning a nonlinear map of empirical singular values; matches analytic shrinkage and stays stable as universe size grows on U.S. equities. | `strategies/covariance_models.py` |
| 2026 | [2606.04217v2](https://arxiv.org/abs/2606.04217v2) | Polymarket-v1 archive (1.2B trades, ground-truth aggressor direction) shows the tick rule and bulk volume classification are near-random (49.8%/50.5%), inferred VPIN diverges and OFI is directionally biased, degrading transaction-cost analysis. | strategies/orderflow.py |
| 2026 | [2604.08765v3](https://arxiv.org/abs/2604.08765v3) | Reliability-aware ETF tail-risk service combines data-quality checks, lower-tail prediction, uncertainty scoring and risk-aware adjustment in rolling walk-forward; improves stressed-period monitoring and stays reliable under simulated input degradation. | `strategies/tail_risk.py` |
| 2026 | [2604.17327v1](https://arxiv.org/abs/2604.17327v1) | Live portfolio validation of multi-agent MarketSenseAI on the S&P500 (19 months): the strong-buy equal-weight portfolio earns +2.18%/month versus a +1.15% passive benchmark; agent-structure analysis reveals the edge source. | `strategies/alpha_eval.py` |
| 2026 | [2604.15531v1](https://arxiv.org/abs/2604.15531v1) | Falsification audit tests complete ML predictive workflows against zero-predictability and microstructure-placebo reference classes; workflows producing significant walk-forward evidence there are falsified, and a magnitude gap quantifies selection-induced inflation. | `strategies/falsification.py` |
| 2026 | [2603.20237v2](https://arxiv.org/abs/2603.20237v2) | Formalizes temporal coverage bias in calendar-aligned panels and proposes coverage-aware structuring via instrument observation windows and an availability matrix; Dhaka Stock Exchange results show substantial distortion from naive alignment. | `strategies/coverage_window.py` |
| 2026 | [2607.24410v1](https://arxiv.org/abs/2607.24410v1) | Characteristic-Driven Dynamic Factor Model builds covariance from observable firm fundamentals, jointly learning interpretable factor exposures and a forward covariance estimator, matching return-based forecasts and onboarding unseen assets zero-shot. | strategies/covariance_models.py |
| 2026 | [2608.10788v1](https://arxiv.org/abs/2608.10788v1) | Applies the Triadic Stress Index to correlation networks across five markets; it beats the Absorption Ratio by 0.273 out-of-sample F1, emits the cleanest alarms, and gives parameter-free per-node attribution. | strategies/triadic_stress.py |
| 2026 | [2608.27734v1](https://arxiv.org/abs/2608.27734v1) | LLM strategy-discovery system with registry-validated look-ahead-free tools and trial-count deflation; honest evaluation certifies passive benchmarks and rejects every LLM-discovered strategy across 453 stocks and 39 ETFs. | strategies/trial_ledger.py |
| 2026 | [2607.06690v1](https://arxiv.org/abs/2607.06690v1) | tsbootstrap packages block/residual/sieve/wild resampling and adaptive conformal calibrators (EnbPI, ACI, NexCP, AgACI) in one typed API; the IID bootstrap undercovers under dependence, with sieve nearest nominal. | strategies/conformal.py |
| 2025 | [2508.18592v1](https://arxiv.org/abs/2508.18592v1) | Combines three ML models for CSI 300 stock selection under static and IC-based dynamic weighting; IC-mean weighting beats metric-based weighting and single models. | `strategies/signal_analysis.py` |
| 2025 | [2507.23414v1](https://arxiv.org/abs/2507.23414v1) | Multifractal detrended fluctuation analysis and refined composite multiscale sample entropy measure complexity of Bitcoin, GBP/USD, gold and gas returns; Bitcoin shows highest complexity, attributed to stronger nonlinear correlations. | `strategies/complexity.py` |
| 2025 | [2508.07408v1](https://arxiv.org/abs/2508.07408v1) | LLM labels event categories on high-sentiment company tweets, aligned to 1-7 day forward returns; certain events yield negative alpha, Sharpe to -0.38, IC above 0.05. | `strategies/sentiment_research.py` |
| 2025 | [2507.18417v1](https://arxiv.org/abs/2507.18417v1) | FinDPO fine-tunes an LLM via Direct Preference Optimization for financial sentiment, beating SFT models by 11%; a logit-to-score conversion feeds portfolio strategies yielding 67% annual returns and Sharpe 2.0 after 5bps costs. | `strategies/sentiment_research.py` |
| 2025 | [2509.04541v2](https://arxiv.org/abs/2509.04541v2) | Introduces finance-grounded loss functions from Sharpe, PnL and max drawdown plus turnover regularization for deep trading models; they beat MSE on algorithmic-trading metrics. | `strategies/evaluate.py` |
| 2025 | [2511.08571v1](https://arxiv.org/abs/2511.08571v1) | Walk-forward gold-futures trend/momentum strategy with volatility targeting, impact-adjusted fractional Kelly sizing and ATR exits; delivers Sharpe 2.88 and 0.52 percent max drawdown net of costs. | `strategies/momentum.py` |
| 2025 | [2512.15720v1](https://arxiv.org/abs/2512.15720v1) | Computes order-flow entropy from a 15-state second-resolution Markov matrix on 38.5M SPY trades: low entropy raises 5-minute absolute returns 2.89x while directional accuracy stays chance-level (45%). | `strategies/orderflow.py` |
| 2025 | [2507.15079v1](https://arxiv.org/abs/2507.15079v1) | Isotonic Quantile Regression Averaging (iQRA) adds stochastic order constraints to ensemble point forecasts, producing probabilistic electricity-price forecasts that beat conformal and state-of-the-art postprocessing on reliability, sharpness and cost, without hyperparameter tuning. | `strategies/conformal.py` |
| 2025 | [2509.19663v3](https://arxiv.org/abs/2509.19663v3) | R/S, DFA, multifractal and ARFIMA-FIGARCH tests find long memory in conditional volatility (not mean returns) across equities, commodities and energy; deep generative models struggle to reproduce it. | `strategies/long_memory.py` |
| 2025 | [2507.15437v3](https://arxiv.org/abs/2507.15437v3) | Forecasts linear fractional stable motion increments using codifference-based conditional expectation or semimetric projection; simulation and real volatility data show it outperforms fBm and HAR, revealing a selective-memory regime in rough volatility. | `strategies/long_memory.py` |
| 2025 | [2508.15922v1](https://arxiv.org/abs/2508.15922v1) | Probabilistic crypto volatility forecasting: feeds HAR/GARCH/ARFIMA and ML point forecasts into quantile estimation via residual simulation (QRS); QRS on log realized vol of linear models wins. | `strategies/conformal.py` |
| 2025 | [2506.06329v1](https://arxiv.org/abs/2506.06329v1) | Builds News-Count and Capitalization-Adjusted Hype Indices measuring media attention for S&P 100 stocks/sectors; the indices classify hype groups and relate to returns, volatility and VIX at various lags, aiding volatility analysis and short-term signaling. | `strategies/news_relevance.py` |
| 2025 | [2506.07711v6](https://arxiv.org/abs/2506.07711v6) | Introduces a framework for signed, size- and duration-varying metaorders with square-root impact and time decay, plus q-dependent exponents; predicts non-monotonic power laws in parameter a matching data, supporting order-driven excess volatility. | `strategies/orderflow.py` |
| 2025 | [2508.01880v3](https://arxiv.org/abs/2508.01880v3) | Time-varying factor-augmented volatility framework extracts dynamic cross-sectional factors from realized volatilities and feeds statistical and AI models; improves 1-day and 7-day forecasts for tech equities and crypto, and a pairs-trading strategy earns superior risk-adjusted returns. | `strategies/volatility_models.py` |
| 2025 | [2502.20978v2](https://arxiv.org/abs/2502.20978v2) | Semi-parametric quantile historical simulation forecasts multi-step VaR and ES by scaling returns with an estimated quantile series then resampling; extends to Realized GARCH/CAViaR, evaluated in simulation and 1%/2.5% one- and ten-day forecasts. | `strategies/tail_risk.py` |
| 2024 | [2412.00896v1](https://arxiv.org/abs/2412.00896v1) | Introduces warm-start genetic programming with careful initialization and structural constraints to mine alpha factors; on 2020-2024 Chinese equities yields better out-of-sample prediction and higher portfolio returns than benchmark. | `strategies/alpha_zoo.py` |
| 2024 | [2404.16449v1](https://arxiv.org/abs/2404.16449v1) | Kalman-filter two-stage trendline extraction yields a price-reversal indicator generating strong portfolio returns in emerging and developed markets. | `strategies/statistical_kalman.py` |
| 2024 | [2401.10370v1](https://arxiv.org/abs/2401.10370v1) | Comparative review of deep generative models (CGAN, CWGAN, diffusion, signature) for financial time-series generation, applied to Historical-Simulation VaR. | `strategies/book_risk.py` |
| 2024 | [2401.06724v2](https://arxiv.org/abs/2401.06724v2) | Latent/revealed order book model of equity closing auctions reproduces liquidity buildup and reduced price impact as event rate accelerates; measured on Euronext Paris. | `strategies/orderflow.py` |
| 2024 | [2406.08041v1](https://arxiv.org/abs/2406.08041v1) | Across 1,455 stocks, HAR with a refined rolling-window fitting scheme beats tuned ML models on QLIKE/MSE/realized utility at far lower computational cost and with interpretability. | `strategies/long_memory.py` |
| 2024 | [2411.08382v1](https://arxiv.org/abs/2411.08382v1) | Hybrid VAR plus feedforward neural network predicts order-flow imbalance, feeding VAR residuals to the FNN and estimating buy/sell intensity; beats standalone FNN and VAR on Binance and synthetic data. | `strategies/orderflow.py` |
| 2024 | [2401.03393v2](https://arxiv.org/abs/2401.03393v2) | Compares Markov-Switching GARCH with Stochastic ARV models for Bitcoin conditional variance; SARV forecasts better and two-stage estimation is recommended. | `strategies/volatility_models.py` |
| 2024 | [2401.06249v4](https://arxiv.org/abs/2401.06249v4) | SpotV2Net graph attention network forecasts intraday spot volatility, using nonparametric Fourier vol-of-vol and co-vol-of-vol estimates as edge features; gains on Dow components. | `strategies/volatility_models.py` |
| 2024 | [2404.00012v1](https://arxiv.org/abs/2404.00012v1) | Risk-on/risk-off strategy combining a volatility/credit-spread stress indicator with GPT-4 sentiment of Bloomberg summaries; higher Sharpe and lower max drawdown across major equity markets. | `strategies/credit_spread.py` |
| 2024 | [2401.03443v1](https://arxiv.org/abs/2401.03443v1) | Structured factor copulas model joint and conditional bank distress from CDS; systematic contagion via latent global plus region-specific factors prevails. | `strategies/tail_risk.py` |
| 2023 | [2308.14235v6](https://arxiv.org/abs/2308.14235v6) | Statistical-physics model of Level 3 order book defines kinetic energy, momentum and 'active depth'; outperforms benchmarks and ML for volatility and expected returns. | `strategies/orderflow.py` |
| 2023 | [2304.07619v6](https://arxiv.org/abs/2304.07619v6) | GPT-4 predicts news-headline market reactions with ~90% portfolio-day hit rates; scores forecast subsequent drift, especially small caps and negative news. | `strategies/events.py` |
| 2023 | [2310.14536v1](https://arxiv.org/abs/2310.14536v1) | Co-trains a normalizing-flow RV transformation with the prediction model under a maximum-likelihood objective for skewed, fat-tailed realized volatility. | `strategies/volatility_models.py` |
| 2023 | [2306.12446v2](https://arxiv.org/abs/2306.12446v2) | Compares deep forecasters (MLP, RNN, TCN, Temporal Fusion Transformer) with GARCH for multivariate volatility; TFT wins in most of five assets. | `strategies/volatility_models.py` |
| 2023 | [2310.16849v1](https://arxiv.org/abs/2310.16849v1) | Random-matrix-theory analysis of global agricultural futures correlation: largest eigenvalue is a market mode, deviating eigenvalues identify groups. | `strategies/covariance_models.py` |
| 2023 | [2311.14759v2](https://arxiv.org/abs/2311.14759v2) | Uses BART MNLI zero-shot classification of Twitter/Reddit sentiment for Bitcoin and Ethereum forecasting, beating dictionary-based sentiment methods. | `strategies/sentiment_research.py` |
| 2023 | [2306.00093v2](https://arxiv.org/abs/2306.00093v2) | Discrete q-exponential distribution fits limit-order cancellation times; order-flow modeled with power-law long memory. | `strategies/orderflow.py` |
| 2023 | [2309.08800v1](https://arxiv.org/abs/2309.08800v1) | Cluster-driven dynamic-time-warping method robustly detects lead-lag relationships in lagged multi-factor models, linked to multireference alignment. | `strategies/statistical.py` |
| 2023 | [2310.04027v2](https://arxiv.org/abs/2310.04027v2) | Retrieval-augmented LLM framework improves financial sentiment analysis, addressing zero-shot weaknesses and sparse news context. | `strategies/sentiment_research.py` |
| 2023 | [2306.02136v3](https://arxiv.org/abs/2306.02136v3) | FinBERT sentiment plus LSTM predicts stock trends and beats BERT, standalone LSTM and ARIMA; sentiment significantly improves accuracy. | `strategies/sentiment_research.py` |
| 2023 | [2303.16151v1](https://arxiv.org/abs/2303.16151v1) | Factor decomposition plus sectoral residual restrictions and VHAR-LASSO forecast large S&P 500 realized covariance matrices, improving minimum-variance portfolios. | strategies/covariance_models.py |
| 2023 | [2311.04727v2](https://arxiv.org/abs/2311.04727v2) | LSTM trained across a pool of assets beats traditional volatility models; a rough-volatility plus Zumbach model with five non-asset-dependent parameters matches it (crypto-winter). | `strategies/volatility_models.py` |
| 2023 | [2306.12964v1](https://arxiv.org/abs/2306.12964v1) | RL framework mines synergistic formulaic alpha sets jointly, optimizing combined performance rather than independently generated alphas. | `strategies/alpha_zoo.py` |
| 2023 | [2308.01419v1](https://arxiv.org/abs/2308.01419v1) | Customized graph neural networks forecast multivariate realized volatility with spillovers; nonlinear spillovers help up to one week, multi-hop alone does not. | `strategies/volatility_models.py` |
| 2023 | [2312.16190v1](https://arxiv.org/abs/2312.16190v1) | Hawkes-model prediction from limit-order-book data with a continuous output error model forecasts cryptocurrency return signs, beating benchmarks. | `strategies/orderflow.py` |
| 2023 | [2311.10685v3](https://arxiv.org/abs/2311.10685v3) | Empirical Bayes mines 136,000 long-short strategies, matching top-journal out-of-sample performance without look-ahead bias; common multiple-testing methods fail to find performers. | `strategies/trial_ledger.py` |
| 2023 | [2310.09903v5](https://arxiv.org/abs/2310.09903v5) | Tests 123 technical indicators and 10 regression models on 13 years of Apple data; a 3-day window is best and linear/ridge regression win. | `strategies/extended_indicators.py` |
| 2023 | [2308.05564v4](https://arxiv.org/abs/2308.05564v4) | Large skew-t copula models capture asymmetric extreme tail dependence in intraday equity returns; Bayesian variational inference makes high-dimensional estimation fast. | `strategies/covariance_models.py` |
| 2023 | [2306.15807v4](https://arxiv.org/abs/2306.15807v4) | Introduces liquidity premium measures and liquidity-adjusted ARMA-GARCH/EGARCH models that outperform traditional models at extreme liquidity. | `strategies/liquidity_risk.py` |
| 2023 | [2306.05568v2](https://arxiv.org/abs/2306.05568v2) | MACE, a multivariate alternating conditional expectations algorithm (Random Forest + constrained ridge), builds maximally predictable portfolios and scales to large ones. | `strategies/portfolio_optimizer.py` |
| 2023 | [2307.12744v1](https://arxiv.org/abs/2307.12744v1) | Generalized Langevin equation models S&P500 mean market correlation with a memory kernel spanning three trading weeks, improving correlation forecasting and portfolio risk. | `strategies/covariance_models.py` |
| 2023 | [2308.08135v1](https://arxiv.org/abs/2308.08135v1) | Framework extracts stock factors from high-frequency order-flow and tick-level order-book data to support high-frequency investment. | `strategies/orderflow.py` |
| 2023 | [2305.20067v1](https://arxiv.org/abs/2305.20067v1) | Time-varying conditional-quantile VaR modeling; asymmetric MAD ranks forecasts; violation-frequency band stabilizes quantiles on Fama-French 25 portfolios. | `strategies/book_risk.py` |
| 2023 | [2305.08241v1](https://arxiv.org/abs/2305.08241v1) | NYSE one-minute prices fit shot-noise with Hurst 0.465 (slightly mean-reverting), arbitrageable over hours; cross-correlations predictable over years. | `strategies/mean_reversion.py` |
| 2023 | [2310.09622v1](https://arxiv.org/abs/2310.09622v1) | Bivariate jump-diffusion model of Bitcoin price driven by Google-search sentiment; closed-form price and neural-network option valuation. | `strategies/options_math.py` |
| 2023 | [2305.10911v1](https://arxiv.org/abs/2305.10911v1) | Outlier detection by projecting multivariate data onto directions maximizing the convex Cumulant Generating Function; extends PCA and flags financial crises early. | `strategies/data_quality.py` |
| 2023 | [2309.02205v1](https://arxiv.org/abs/2309.02205v1) | State-space conditional factor model filters time-varying risk premia online; large deviations from filtered returns initiate mean-reversion statistical-arbitrage trades. | `strategies/statistical_kalman.py` |
| 2023 | [2304.09947v2](https://arxiv.org/abs/2304.09947v2) | Gradient-free online ensemble reweights 16 models by out-of-sample R-squared; applied to sector rotation, finding sector returns more predictable than stock returns. | `strategies/rotation.py` |
| 2023 | [2308.01486v1](https://arxiv.org/abs/2308.01486v1) | Path Shadowing Monte-Carlo averages future quantities over generated paths matching observed history; a maximum-entropy scattering-spectra model yields state-of-the-art realized-volatility forecasts. | `strategies/volatility_models.py` |
| 2023 | [2312.16637v3](https://arxiv.org/abs/2312.16637v3) | Shannon entropy and KL-based predictability test for ultra-high-frequency data; randomness rises with transaction-time aggregation and predictable days have high volume. | `strategies/complexity.py` |
| 2023 | [2307.00459v1](https://arxiv.org/abs/2307.00459v1) | PCA on S&P 500 covariance with an HMM on principal components forecasts factor then stock returns; tuned strategy beats buy-and-hold. | `strategies/factors.py` |
| 2023 | [2309.06393v1](https://arxiv.org/abs/2309.06393v1) | Real-time VaR for crypto derivative portfolios in kdb+/q using EWMA, GARCH and HAR with delta-gamma-theta and Cornish-Fisher expansions. | `strategies/book_risk.py` |
| 2023 | [2308.08550v1](https://arxiv.org/abs/2308.08550v1) | Extended LSTMs with per-dimension flexible timescales predict asset volatility better than rough volatility by ~20% and halve training epochs. | `strategies/volatility_models.py` |
| 2023 | [2312.01426v2](https://arxiv.org/abs/2312.01426v2) | Range-based volatility proxies confirm rough volatility (Hurst below 0.5, even below 0.1) across non-standard assets, refuting a microstructure-noise explanation. | `strategies/volatility_models.py` |
| 2023 | [2304.09937v1](https://arxiv.org/abs/2304.09937v1) | ML stock predictions degrade during recessions; recession history and risk-free rate do not help, and good-recession performance reflects low volatility, not ML merit. | `strategies/regime_performance.py` |
| 2023 | [2309.16196v1](https://arxiv.org/abs/2309.16196v1) | Transformer using mixed-frequency data (macro indicators plus Baidu search indices as subjective factors) predicts stock volatility. | `strategies/volatility_models.py` |
| 2023 | [2306.14222v2](https://arxiv.org/abs/2306.14222v2) | Standardized evaluation of three LLMs extracting Chinese news sentiment factors into quantitative trading strategies. | `strategies/sentiment_research.py` |
| 2023 | [2306.12434v1](https://arxiv.org/abs/2306.12434v1) | Internal bar strength (IBS) as a mean-reversion indicator for country ETFs; backtest over 10 years suggests profitable short-term signals. | `strategies/mean_reversion.py` |
| 2022 | [2203.12460v1](https://arxiv.org/abs/2203.12460v1) | Studies a decade of ~100k earnings-call transcripts from 6,300 firms; a semantic GNN reliably predicts price moves across five sectors, semantics beat sales/EPS, while pre-earnings analyst ratings correlate weakly. | `strategies/text_factors.py` |
| 2022 | [2212.14670v1](https://arxiv.org/abs/2212.14670v1) | Hierarchical RL Macro-Meta-Micro Trader (with LSTM volume forecast) optimizes VWAP execution and saves 1.16 bp average cost over the best baseline on Shanghai stocks. | strategies/execution_schedule.py |
| 2022 | [2203.12457v1](https://arxiv.org/abs/2203.12457v1) | Engineers technical, order-flow and order-book features fed to a Tabnet network predicting short-term silver futures direction on the Shanghai Futures Exchange, reaching 0.601 accuracy. | `strategies/orderflow.py` |
| 2022 | [2201.09319v1](https://arxiv.org/abs/2201.09319v1) | Shows normalized option-volume imbalance between positive and negative views predicts excess overnight equity returns; decomposing five participant classes, Market-Maker volumes and high-IV put contracts carry the strongest signal. | `strategies/orderflow.py` |
| 2022 | [2203.08224v4](https://arxiv.org/abs/2203.08224v4) | Adapts Generalized Random Forests to quantile prediction for cryptocurrency VaR over 105 coins; GRF beats quantile regression, GARCH and CAViaR, especially in unstable and highly volatile periods. | `strategies/book_risk.py` |
| 2022 | [2203.12456v1](https://arxiv.org/abs/2203.12456v1) | Blending and augmented BARCH models counter SVR-GARCH's backward-eavesdropping over/underestimation; empirically improve volatility forecasting peak/trough behaviour on SH300 and S&P500. | `strategies/volatility_models.py` |
| 2022 | [2209.10334v2](https://arxiv.org/abs/2209.10334v2) | Classifying trades by co-occurrence into five types yields conditional order imbalance (COI); COIs predict returns and trading strategies earn high Sharpe on 457 stocks. | strategies/orderflow.py |
| 2022 | [2202.08962v2](https://arxiv.org/abs/2202.08962v2) | Pools cross-stock intraday data with a market-volatility proxy to forecast realized volatility; neural networks beat linear and tree models, generalize to unseen stocks, and exploit time-of-day effects. | `strategies/long_memory.py` |
| 2021 | [2106.07177v2](https://arxiv.org/abs/2106.07177v2) | Predicts the implied volatility surface with a two-step framework: extract features (PCA, VAE, or surface sampling), forecast with LSTM, then reconstruct via arbitrage-constrained DNN; sampling/VAE outperform classical methods on S&P500 data. | `strategies/options_surface.py` |
| 2021 | [2101.10942v2](https://arxiv.org/abs/2101.10942v2) | Shows prediction-error-based evaluation of neural stock predictors is statistically flawed; the absolute-value constraint distorts reported performance. | `strategies/evaluate.py` |
| 2021 | [2104.10673v4](https://arxiv.org/abs/2104.10673v4) | Multi-objective elicitability makes CoVaR/CoES/MES forecast backtesting feasible; Diebold-Mariano tests and a traffic-light approach on DAX/S&P500. | `strategies/tail_risk.py` |
| 2021 | [2107.07206v2](https://arxiv.org/abs/2107.07206v2) | Compares logistic regression and feedforward neural networks for credit scoring; temporal repeated-measure features boost accuracy, and a new Stein-unbiased-risk-estimate (SURE) calibration stacked with Platt improves predicted-probability calibration. | `strategies/calibration.py` |
| 2021 | [2112.13213v4](https://arxiv.org/abs/2112.13213v4) | Integrates top-level order flow imbalances into a single OFI explaining equity price impact better than best-level OFI; multi-asset cross-impact adds no contemporaneous power, but lagged cross-asset OFI predicts short-horizon returns. | `strategies/orderflow.py` |
| 2021 | [2103.09106v1](https://arxiv.org/abs/2103.09106v1) | Feature learning on 5 technical and 23 fundamental indicators shows analyst rating matters; 83.62% directional accuracy and 85% buy precision on S&P500. | `strategies/analyst_revisions.py` |
| 2021 | [2103.05921v1](https://arxiv.org/abs/2103.05921v1) | Knockoff procedure controls false-discovery rate in financial factor selection; applied to fund replication and explanatory/prediction networks. | `strategies/factors.py` |
| 2021 | [2109.10946v1](https://arxiv.org/abs/2109.10946v1) | Studies Copula-GARCH VaR/ES forecast model risk, isolating marginals versus copula; risk is economically large, crisis-heavy and almost entirely copula-driven, and model confidence sets reduce it. | `strategies/volatility_models.py` |
| 2021 | [2107.07678v1](https://arxiv.org/abs/2107.07678v1) | Extends a two-state Kalman filter to multiple hidden states for predicting daily trading volume; cross-validation selects the best state count by minimizing volume MSE, validated across comparison experiments. | `strategies/statistical_kalman.py` |
| 2021 | [2102.07372v2](https://arxiv.org/abs/2102.07372v2) | REST relational event-driven graph neural model forecasts stock trends using news events and inter-stock relations. | `strategies/news_score.py` |
| 2021 | [2103.09987v1](https://arxiv.org/abs/2103.09987v1) | Statistical Arbitrage Risk Premium: elastic-net projects each stock's returns onto peers to build replicate portfolios hedging factor residual risk. | `strategies/peer_universe.py` |
| 2021 | [2103.16388v1](https://arxiv.org/abs/2103.16388v1) | FinALBERT (ALBERT) trained on 10 years of labelled Stocktwits data for financial text classification and stock price-change prediction. | `strategies/sentiment_research.py` |
| 2021 | [2103.01670v1](https://arxiv.org/abs/2103.01670v1) | LOB recreation model predicts the limit order book from TAQ history using an ODE recurrent neural network. | `strategies/orderflow.py` |
| 2020 | [2012.05906v1](https://arxiv.org/abs/2012.05906v1) | Sentiment from financial news and tweets correlates with next-day FTSE100 volatility and returns. | `strategies/sentiment_research.py` |
| 2020 | [2004.12400v1](https://arxiv.org/abs/2004.12400v1) | Dynamic Conditional Weights model of realized optimal portfolio weights; adds break-even transaction cost measure; best min-variance allocations on Dow Jones 30 across risk aversion/costs. | strategies/portfolio_optimizer.py |
| 2020 | [2006.02077v4](https://arxiv.org/abs/2006.02077v4) | Presents AdaVol, an adaptive recursive streaming estimation routine for GARCH models using stochastic approximation and variance targeting, extending batch QML to large-scale settings. | strategies/volatility_models.py |
| 2020 | [2004.06565v2](https://arxiv.org/abs/2004.06565v2) | Bayesian consensus estimator correcting miscalibration and heteroscedastic noise; unbiased, asymptotically efficient; hierarchical variant beats existing consensus models on ILI and earnings forecasts. | strategies/consensus.py |
| 2020 | [2009.03094v1](https://arxiv.org/abs/2009.03094v1) | XGBoost on fundamental and technical features across many stocks captures post-earnings-announcement drift dynamics beyond simple regressions. | `strategies/catalyst.py` |
| 2020 | [2009.06910v1](https://arxiv.org/abs/2009.06910v1) | SVR-GARCH-KDE hybrid nonparametrically forecasts Value-at-Risk, overcoming parametric bias from skew and leptokurtosis. | `strategies/book_risk.py` |
| 2020 | [2010.01241v1](https://arxiv.org/abs/2010.01241v1) | Temporal CNNs predict Bitcoin spot movement from limit-order-book data at 71% walk-forward accuracy on a 2-second horizon. | `strategies/orderflow.py` |
| 2020 | [2006.03458v1](https://arxiv.org/abs/2006.03458v1) | Proposes Doubly Multiplicative Error Models (Component-MEM and MEM-MIDAS) combining long/short-run components; both beat HAR and GARCH-type models on S&P 500, NASDAQ, FTSE 100, Hang Seng realized volatility. | strategies/volatility_models.py |
| 2020 | [2004.11953v2](https://arxiv.org/abs/2004.11953v2) | Operator-algebra limit-order-book model of order arrivals/cancellations forecasts intraday returns: 80% in-sample R^2, ~15% past-only, >75% directional accuracy under 10 min, RMSPE 10x lower. | strategies/orderflow.py |
| 2020 | [2001.08442v1](https://arxiv.org/abs/2001.08442v1) | Marked point-process intensity-ratio model for limit order books; outperforms pure Hawkes methods predicting sign and aggressiveness of market orders on Euronext Paris stocks. | strategies/orderflow.py |
| 2020 | [2011.00552v3](https://arxiv.org/abs/2011.00552v3) | Mixed-frequency quantile regression directly forecasts VaR and Expected Shortfall blending low- and high-frequency predictors. | `strategies/book_risk.py` |
| 2020 | [2002.04164v3](https://arxiv.org/abs/2002.04164v3) | RNSGHE robustly estimates multiscaling exponents via generalized Hurst exponent plus t/F tests; Monte-Carlo Multiscaling VaR mimics annual VaR for most stocks. | strategies/long_memory.py |
| 2020 | [2004.11674v1](https://arxiv.org/abs/2004.11674v1) | Non-Gaussian GARCH on Bitcoin, Ethereum, Litecoin: skewed GED gives best specification/forecast for BTC and LTC, skewed distribution best for ETH; relax normality for accuracy. | strategies/volatility_models.py |
| 2020 | [2006.00158v1](https://arxiv.org/abs/2006.00158v1) | Applies HAR models with positive/negative realized semivariance, asymmetric jumps and leverage effects to Japanese futures/spot markets; leverage clearly matters, RSV helps, asymmetric jumps do not. | strategies/long_memory.py |
| 2020 | [2004.00550v2](https://arxiv.org/abs/2004.00550v2) | Combines GARCH-family models with Mixture of Distribution Hypothesis using tweet and transaction volume; simplest GARCH(1,1) responds best to external signal out-of-sample. | strategies/volatility_models.py |
| 2020 | [2004.05894v1](https://arxiv.org/abs/2004.05894v1) | Extreme-value theory on the hidden tail beyond in-sample max: visible mean badly understates true moments for tail index near 1; hidden 0th moment ~ Exponential(mean 1/n). | strategies/tail_risk.py |
| 2019 | [1904.08153v3](https://arxiv.org/abs/1904.08153v3) | Heterogeneous simultaneous graphical dynamic linear model embedding HAR-RV gives a GPU-scalable multivariate volatility estimator with interpretable decompositions, validated up to one month ahead on stocks, FX and ETF futures. | `strategies/long_memory.py` |
| 2019 | [1905.04603v15](https://arxiv.org/abs/1905.04603v15) | Generalizes Shiller CAPE by treating log wealth-minus-earnings as an AR(1) with 4.6% trend; the new valuation measure disproves the EMH and is applied to retirement withdrawal planning. | `strategies/cape.py` |
| 2019 | [1910.01491v1](https://arxiv.org/abs/1910.01491v1) | RIC-NN: nonlinear multi-factor deep net with rank-IC stopping criterion and transfer learning across regions; beats off-the-shelf ML and major equity funds over 14 years on MSCI stocks. | strategies/signal_analysis.py |
| 2019 | [1906.09024v2](https://arxiv.org/abs/1906.09024v2) | Builds a BERT-based financial sentiment index for three Hong Kong stocks using Weibo text and combines it with option-implied and market-implied sentiment; LSTM then predicts individual stock returns nonlinearly. | `strategies/sentiment_research.py` |
| 2019 | [1912.10709v2](https://arxiv.org/abs/1912.10709v2) | Recasts the cross-sectional Information Coefficient as high-dimensional directional statistics, deriving closed-form IC covariance and variance and optimising IC mean/variance; tested on Chinese stocks. | strategies/signal_analysis.py |
| 2019 | [1901.02419v5](https://arxiv.org/abs/1901.02419v5) | Models conditionally log-Laplace stochastic volatility with analytic conditional structure to give dynamic Pareto-tailed extreme event probabilities in heavy-tailed, nonlinearly dependent series. | `strategies/tail_risk.py` |
| 2019 | [1907.02666v1](https://arxiv.org/abs/1907.02666v1) | GARCH-Ito-OI and GARCH-Ito-IV models integrate low-frequency, 5-minute high-frequency and option-implied volatility; quasi-MLE asymptotics established and both models forecast better than popular alternatives. | `strategies/volatility_models.py` |
| 2019 | [1910.13115v2](https://arxiv.org/abs/1910.13115v2) | Weekly idiosyncratic momentum (IMOM) in Chinese A-shares 1997-2017: contrarian and IMOM effects; IVOL- and max-drawdown-based portfolios perform best; profits tied to upside sentiment. | strategies/momentum.py |
| 2019 | [1909.11009v1](https://arxiv.org/abs/1909.11009v1) | Rolling out-of-sample forecasts of commodity implied-volatility surfaces (2006-2016); explicitly modelling the term structure with Nelson-Siegel factors is most accurate for energy and precious metals. | strategies/options_surface.py |
| 2019 | [1907.09452v1](https://arxiv.org/abs/1907.09452v1) | Extracts 270+ hand-crafted technical/quantitative features for short-term mid-price movement; wrapper selection (entropy, LMS, LDA) plus an adaptive logistic-regression feature reaches best performance with few features on Nasdaq Nordic LOB data. | strategies/technical_factors.py |
| 2019 | [1909.03792v2](https://arxiv.org/abs/1909.03792v2) | Hybrid lexicon+learning Persian sentiment: comment volume predicts closing price; volume and sentiment together predict daily return on Tehran stocks. | strategies/sentiment_research.py |
| 2018 | [1807.02422v2](https://arxiv.org/abs/1807.02422v2) | Semi-parametric realized joint VaR/ES quantile regression with a measurement equation linking realized variance/range to latent ES; adaptive Bayesian MCMC beats parametric and non-parametric rivals on 7 indices and 7 assets. | `strategies/book_risk.py` |
| 2018 | [1812.07295v1](https://arxiv.org/abs/1812.07295v1) | Proposes long-memory models whose fractional parameter d varies over time through a score-driven stochastic recurrence; validated by Monte Carlo and two real series. | `strategies/long_memory.py` |
| 2018 | [1812.02527v1](https://arxiv.org/abs/1812.02527v1) | Uses State Switching Markov Autoregressive models to identify Wyckoff-style accumulation/distribution/advance/decline regimes, then tailors trend, range, retracement and breakout strategies per regime. | `strategies/regime_state.py` |
| 2016 | [1605.06482v4](https://arxiv.org/abs/1605.06482v4) | Nonlinear leverage-effect functions within Bayesian stochastic volatility improve density forecasts for 89% of 615 S&P500 and Nikkei 225 stocks versus linear. | `strategies/volatility_models.py` |
| 2015 | [1509.08079v1](https://arxiv.org/abs/1509.08079v1) | Overnight volatility is significantly positively correlated with next-day intraday volatility but much less with the preceding day's, a robust time asymmetry. | `strategies/volatility_models.py` |
| 2015 | [1509.05954v1](https://arxiv.org/abs/1509.05954v1) | Shows stationarity alone is insufficient for cointegration trading; proposes algorithmic search for maximally mean-reverting portfolios that are sparse and/or sufficiently volatile. | `strategies/mean_reversion.py` |
| 2015 | [1510.06946v2](https://arxiv.org/abs/1510.06946v2) | Introduces quantile coherency in the frequency domain to capture general nonlinear dependence; empirical application sharpens tail-risk measurement of stock returns. | `strategies/tail_risk.py` |
| 2014 | [1407.5528v1](https://arxiv.org/abs/1407.5528v1) | Gives an arbitrage-free prediction of future co-terminal option prices across many strikes, respecting no-arbitrage restrictions in a multivariate time series model. | strategies/options_surface.py |
| 2014 | [1408.2794v1](https://arxiv.org/abs/1408.2794v1) | Adds 11 IBES sector-specific factors to market factors and estimates the resulting sector-based factor model by expectation maximization. | strategies/factors.py |
| 2014 | [1410.3394v1](https://arxiv.org/abs/1410.3394v1) | Log-volatility behaves as fractional Brownian motion with Hurst exponent ~0.1 (rough FSV model), improving volatility forecasts from HF data. | strategies/volatility_models.py |
| 2013 | [1303.4351v4](https://arxiv.org/abs/1303.4351v4) | Compares common technical trading strategies against a completely random strategy on FTSE-UK, FTSE-MIB, DAX and S&P 500 over 15-20 years of data. | `strategies/quant_baseline.py` |
| 2013 | [1312.0557v7](https://arxiv.org/abs/1312.0557v7) | Derives the asymptotic distribution of the Markowitz portfolio for general and multivariate-normal returns, enabling robust inference and covariance-mis-estimation error estimates. | strategies/portfolio_optimizer.py |
| 2013 | [1303.1690v3](https://arxiv.org/abs/1303.1690v3) | Shows law-invariant spectral risk measures such as expected shortfall are not elicitable unless they reduce to minus the expected value; the elicitable coherent law-invariant measures are expectiles. | `strategies/book_risk.py` |
| 2013 | [1304.2942v3](https://arxiv.org/abs/1304.2942v3) | Optimal execution under displaced diffusion compared across VaR, expected shortfall and squared-asset-expectation criteria; differences matter at high risk aversion and low impact. | `strategies/execution_schedule.py` |
| 2012 | [1212.4890v2](https://arxiv.org/abs/1212.4890v2) | Derives Bollinger Bands from rolling regression, proves a return-duration relationship in BB pairs trading, and builds a random-walk-plus-noise "Fixed Forecast Maximum Duration" variant tested on SAP/Nikkei. | `strategies/extended_indicators.py` |
| 2012 | [1204.3136v3](https://arxiv.org/abs/1204.3136v3) | A thermodynamic multifractal partition-function index (normalized energy variation) identifies 1929, 1987 and 2008 crashes in real time and shows forecasting capability. | `strategies/regime.py` |
| 2012 | [1204.1452v4](https://arxiv.org/abs/1204.1452v4) | Realized GARCH with multi-time-frequency realized volatility and jump wavelet two-scale estimator beats conventional models in FX futures; most forecast information comes from the highest frequencies. | `strategies/volatility_models.py` |
| 2012 | [1112.1051v1](https://arxiv.org/abs/1112.1051v1) | Compares Twitter, news, Google search and survey sentiment across DJIA, volume, VIX and gold: weekly Google search volumes and Twitter sentiment predict daily returns, while traditional surveys lag and become insignificant. | `strategies/sentiment_research.py` |
| 2012 | [1201.3572v2](https://arxiv.org/abs/1201.3572v2) | Hawkes self-excited calibration of E-mini S&P 500 futures 1998-2010 measures endogeneity: the exogenous share of price changes fell from 70% in 1998 to under 30% since 2007. | `strategies/orderflow.py` |
| 2012 | [1202.1854v2](https://arxiv.org/abs/1202.1854v2) | Wavelet (MODWT, two-scale) realized-variance estimator splits variance into investment horizons and jumps, is noise-robust, and forecasts best in simulations and forex futures. | `strategies/volatility_models.py` |
| 2012 | [1208.4831v2](https://arxiv.org/abs/1208.4831v2) | Wavelet band least-squares finds fractional cointegration between implied and realized volatility; corridor implied volatility (not MFIV) is the unbiased long-run RV forecast on S&P 500/DAX. | `strategies/options_surface.py` |
| 2012 | [1206.2153v2](https://arxiv.org/abs/1206.2153v2) | QARCH calibration on US returns finds significant off-diagonal feedback one order of magnitude weaker than diagonal, power-law kernel decay, and observed time-reversal violations smaller than predicted. | `strategies/volatility_models.py` |
| 2011 | [1112.4534v1](https://arxiv.org/abs/1112.4534v1) | Method-of-moments volatility estimator from daily OHLC range of arithmetic Brownian motion, treating the open jump as a virtual after-hours session; used for Black-Scholes mispricing trades. | `strategies/volatility_models.py` |
| 2011 | [1102.5457v4](https://arxiv.org/abs/1102.5457v4) | Metaorder market-impact theory via a fair-pricing condition predicts impact rises as roughly the square root of size, with permanent impact relaxing to about two-thirds of peak. | strategies/execution_schedule.py |
| 2011 | [1102.2240v1](https://arxiv.org/abs/1102.2240v1) | Modified time-lag random matrix theory on 48 world indices finds long-range power-law cross-correlations in absolute returns that decay slowly; a PCA global factor model explains much of it. | strategies/covariance_models.py |
| 2011 | [1103.5649v1](https://arxiv.org/abs/1103.5649v1) | Builds unconditional and conditional VaR for twelve European index futures using Extreme Value Theory with GARCH-filtered returns and a multi-period scaling law; normality biases in unconditional estimates extend to the conditional setting. | strategies/book_risk.py |
| 2011 | [1110.4784v3](https://arxiv.org/abs/1110.4784v3) | Web search query volumes for NASDAQ-100 stocks correlate with and anticipate trading-volume peaks by one day or more, emerging from uncoordinated collective user activity. | `strategies/sentiment.py` |
| 2009 | [0904.4131v2](https://arxiv.org/abs/0904.4131v2) | Applies Alfonsi-Fruth-Schied optimal execution in an agent-based order book, finds calibration failure, and generalizes the model with size-dependent recovery speed, proving optimal strategies. | `strategies/execution_schedule.py` |
| 2009 | [0906.5249v1](https://arxiv.org/abs/0906.5249v1) | Applies random-matrix theory to financial covariance matrices; smallest eigenvalues/spacings match Tracy-Widom and Wigner surmise robustly under reshuffling, supporting RMT cleaning for portfolio selection. | strategies/covariance_models.py |
| 2008 | [0808.1710v3](https://arxiv.org/abs/0808.1710v3) | Extends a Gaussian linear state-space model of mean-reverting spreads for statistical arbitrage with time-varying parameters and real-time estimation of hidden states. | `strategies/mean_reversion.py` |
| 2005 | [physics/0507006v1](https://arxiv.org/abs/physics/0507006v1) | Clustering algorithms filter correlation-matrix uncertainty in portfolio optimization, improving the predicted-to-realized risk ratio across wide ranges of N and T (bootstrap analysis). | `strategies/portfolio_optimizer.py` |
| 2005 | [physics/0512090v1](https://arxiv.org/abs/physics/0512090v1) | Free random matrix theory generalizes the Marchenko-Pastur law to rectangular correlation matrices, giving a null singular-value interval to detect true input-output correlations in large-dimension forecasting. | `strategies/covariance_models.py` |
| 2004 | [cond-mat/0401360v1](https://arxiv.org/abs/cond-mat/0401360v1) | Volatility autocorrelation fits a superposition of exponentials, giving an analytic best linear volatility forecast that includes leverage and clustering; parameters fit to DJIA 30. | strategies/volatility_models.py |
| 2004 | [cond-mat/0410079v1](https://arxiv.org/abs/cond-mat/0410079v1) | Earnings forecasts 1987-2004 are over-optimistic and herding; a year-ahead skill ~ "no change" forecast; herding stronger in US; clear sector effects. | strategies/analyst_revisions.py |
| 2003 | [cond-mat/0312643v1](https://arxiv.org/abs/cond-mat/0312643v1) | RMT on Tokyo TSE correlations: randomness repels deterministic and random eigenvalues, refining detection of correlated stock groups. | strategies/covariance_models.py |
| 2003 | [cond-mat/0311053v2](https://arxiv.org/abs/cond-mat/0311053v2) | LSE order signs are long-memory (ACF ~ tau^-0.6, Hurst ~0.7) yet anti-correlated transaction size and liquidity whiten returns; some institutions show long memory. | strategies/orderflow.py |
| 2001 | [cond-mat/0108023v1](https://arxiv.org/abs/cond-mat/0108023v1) | Random-matrix analysis of US stock correlation matrices: most eigenvalues inside RMT bounds, deviating stable eigenvectors map to the market mode plus business sectors. | strategies/covariance_models.py |
| 1999 | [cond-mat/9903203v1](https://arxiv.org/abs/cond-mat/9903203v1) | Nonlinear fractional covariance matrix maps non-Gaussian returns to Gaussians; minimizing variance can raise large risks, and tail description matters more than correlations. | strategies/covariance_models.py |
| 1999 | [cond-mat/9902283v1](https://arxiv.org/abs/cond-mat/9902283v1) | RMT on 1000 US stocks: most eigenvalues follow GOE statistics with few large deviations; eigenvectors at spectrum edges have large inverse participation ratios (localization-like). | strategies/covariance_models.py |

## Medium relevance (100) (showing the 100 most recent of 830)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2602.07841v3](https://arxiv.org/abs/2602.07841v3) | Derives a nontrivial upper bound on out-of-sample R^2 in return forecasting via a coin-flip oracle; the bound is a quadratic function of directional accuracy, and empirical models are fundamentally bounded by it. | `strategies/signal_analysis.py` |
| 2026 | [2605.05211v1](https://arxiv.org/abs/2605.05211v1) | Hedge-fund review of LLMs for stock forecasting: news sentiment, report/transcript analysis, price tokenization, multi-agent systems; stresses data leakage, illiquidity premia and predictability limits. | strategies/debate_claim.py |
| 2026 | [2607.03858v1](https://arxiv.org/abs/2607.03858v1) | Multivariate spectral variance-ratio generalisation decomposes long-horizon equity memory into return and volatility channels; a parsimonious five-factor model fits five panels and dates a late-1980s US volatility-memory regime transition. | strategies/long_memory.py |
| 2026 | [2606.04153v1](https://arxiv.org/abs/2606.04153v1) | Decomposes returns into sign and magnitude, modeling sign conditional on contemporaneous magnitude; captures nonlinear predictability and delivers substantial out-of-sample statistical and economic gains on monthly U.S. excess returns versus linear regression. | strategies/volatility_models.py |
| 2026 | [2608.00761v1](https://arxiv.org/abs/2608.00761v1) | Uses ChatGPT and DeepSeek to score currency fundamentals from economic data releases; a long-strong/short-weak currency strategy earns Sharpe above 0.7, with the Taylor rule explaining the predictability. | strategies/cross_section.py |
| 2026 | [2603.24215v3](https://arxiv.org/abs/2603.24215v3) | Adapts Altman's bankruptcy model to compositional-data log-ratios combined with machine learning; compositional log-ratios mitigate outliers and asymmetry and change bankruptcy-prediction results versus standard ratios. | `strategies/ratios.py` |
| 2026 | [2603.19136v2](https://arxiv.org/abs/2603.19136v2) | Autoencoder reconstruction-error gating routes data to dual node transformers specialized for stable versus event-driven regimes, with reinforcement-learning control and no manual regime labels. | `strategies/regime_state.py` |
| 2026 | [2605.23978v1](https://arxiv.org/abs/2605.23978v1) | Algometrics shows deployment risk is unidentifiable from passive history, crowding can invert model rankings, and randomized/instrumented actions identify short-horizon linear feedback. | strategies/evaluate.py |
| 2026 | [2608.26128v1](https://arxiv.org/abs/2608.26128v1) | Econophysics thesis clusters spectral quantities of 430-stock S&P 500 correlation matrices into Market States; COVID-19 emerges atypical, needing C^2/C^3 reconstructions, with participation spreading during crises. | strategies/covariance_models.py |
| 2026 | [2607.27461v1](https://arxiv.org/abs/2607.27461v1) | Three-matrix Observable Matrix Dynamics portfolio replaces Markowitz expected returns and covariance with correlation distances and Markov ranking chains; volatility rank is forecastable, achieving Sharpe 1.06-1.44 net of costs. | strategies/portfolio_optimizer.py |
| 2026 | [2605.12099v1](https://arxiv.org/abs/2605.12099v1) | Bayesian dynamic gamma process for realized volatility combined with dynamic linear models for prices captures leverage/feedback; improves S&P sector ETF price forecasts vs standard models. | strategies/volatility_models.py |
| 2026 | [2603.11408v2](https://arxiv.org/abs/2603.11408v2) | Builds five LLM sentiment dimensions (relevance, polarity, intensity, uncertainty, forwardness) from energy news, aggregated weekly to classify weekly WTI crude oil futures returns. | `strategies/news_score.py` |
| 2026 | [2602.17851v1](https://arxiv.org/abs/2602.17851v1) | Uses a causal forest with FinancialBERT sentiment scores and SHAP to estimate causal effects of report sentiment on bank profitability in Nepal; finds significant effects conditioned by loan-portfolio composition and balance-sheet leverage. | `strategies/sentiment_research.py` |
| 2026 | [2605.16324v1](https://arxiv.org/abs/2605.16324v1) | Bi-level chaotic-fusion graph network predicts intervals for stock returns via separate center/width functions and volatility-aware gating, improving interval calibration and sharpness across regimes. | strategies/conformal.py |
| 2026 | [2603.22886v1](https://arxiv.org/abs/2603.22886v1) | iVDFM learns identifiable latent factors from multivariate time series by conditioning iVAE-style on the innovation process; linear diagonal dynamics allow scalable companion-matrix and Krylov computation with competitive probabilistic forecasting. | `strategies/statistical.py` |
| 2026 | [2606.23492v1](https://arxiv.org/abs/2606.23492v1) | Continuous hidden Markov model with heavy-tailed emissions (Gaussian, Student-t, Laplace, generalized error) separates regime autocorrelation from marginal shape; on U.S. equities heavy-tailed marginals close most of the fit gap, recovering volatility clustering and reducing kurtosis. | strategies/regime_state.py |
| 2026 | [2602.07659v1](https://arxiv.org/abs/2602.07659v1) | Continuous Program Search: learns a block-factorized latent embedding of a trading-strategy DSL and geometry-compiled mutation operators, improving behavior locality; finds strong strategies with order-of-magnitude fewer evaluations and highest median OOS Sharpe. | `strategies/alpha_zoo.py` |
| 2026 | [2608.05755v2](https://arxiv.org/abs/2608.05755v2) | Extends LSTM with macro covariates and learnable sector embeddings for S&P 500 long-short forecasts; the sector-embedding model outperforms plain LSTM, Random Forest and buy-and-hold on risk and return. | strategies/universe_factors.py |
| 2026 | [2604.19476v2](https://arxiv.org/abs/2604.19476v2) | Two-stage network builds a sparse 10-K embedding candidate graph then uses an LLM to filter edges by economic relation, aggregating pair mean-reversion signals; LLM filtering improves an S&P500 2011-2019 backtest over raw similarity. | `strategies/mean_reversion.py` |
| 2026 | [2606.08586v1](https://arxiv.org/abs/2606.08586v1) | Builds stock-level topological anomaly scores via Takens delay embedding, BallMapper graphs and decoder-conditional VAEs, testing predictive content for intraday return curves; penalised function-on-function regression confirms a regime-dependent temporal fingerprint across all assets. | strategies/cross_section.py |
| 2026 | [2606.27670v1](https://arxiv.org/abs/2606.27670v1) | CryptoGAT recasts cryptocurrency price prediction as a cross-asset graph attention problem rather than temporal modeling, outperforming LSTM/GRU/Transformer baselines and arguing that extreme volatility defeats time-series models. | strategies/covariance_models.py |
| 2026 | [2605.27977v1](https://arxiv.org/abs/2605.27977v1) | Forecasts US aggregate bond index with MLPs on lagged vectors and CNNs on Gramian Angular Fields after fractional differencing; MLPs merely match the naive persistence benchmark. | strategies/factor_expressions.py |
| 2026 | [2601.14062v1](https://arxiv.org/abs/2601.14062v1) | One-step-ahead classification of healthcare index direction from OHLC plus novel mutual-ratio nowcasting features; accuracy >0.8, MCC >0.6 on US/India indices, SHAP shows nowcast features dominate. | `strategies/extended_indicators.py` |
| 2026 | [2608.14323v1](https://arxiv.org/abs/2608.14323v1) | Maps characteristic dependence via a Maximally Filtered Clique Forest onto a Homological Neural Network for annual excess-return forecasts; it matches a three-layer benchmark, ranks better, and uses ~80x fewer parameters. | strategies/universe_factors.py |
| 2026 | [2608.14859v1](https://arxiv.org/abs/2608.14859v1) | Builds an earnings-call human-capital disruption measure; a one-standard-deviation rise associates with 0.55pp higher idiosyncratic volatility and predicts ~0.50% higher idiosyncratic volatility over 42 trading days. | strategies/text_factors.py |
| 2026 | [2604.01431v1](https://arxiv.org/abs/2604.01431v1) | Daily Kalshi prediction-market probability changes forecast crypto realized volatility: Fed repricing predicts Bitcoin (t=3.63), recession-risk signal gives out-of-sample MSFE 0.979 (Clark-West p=0.020), CPI repricing predicts altcoins. | `strategies/volatility_models.py` |
| 2026 | [2607.00475v1](https://arxiv.org/abs/2607.00475v1) | End-to-end AI policies map market states to weights for 16 liquid CME futures via a differentiable Sharpe loss; learned policies beat equal-weight, risk-parity and time-series momentum, though non-uniformly. | strategies/portfolio_optimizer.py |
| 2026 | [2603.12040v1](https://arxiv.org/abs/2603.12040v1) | Information-theoretic study of major indices during Trump's 2025 first 100 days; standard deviation and sliding-window entropy decouple, so entropy reflects diversity of outcomes rather than amplitude. | `strategies/complexity.py` |
| 2026 | [2607.08500v2](https://arxiv.org/abs/2607.08500v2) | Recovers a volatility-scaled stochastic discount factor from S&P 500 options; the SDF is stable and non-monotonic, becoming W-shaped with maturity, and its equity premium predicts better out-of-sample than Martin bounds. | strategies/rnd_recovery.py |
| 2026 | [2602.00776v1](https://arxiv.org/abs/2602.00776v1) | Unified CatBoost pipeline (direction-aware GMADL, time-series CV) on 1-second Binance Futures order books shows stable SHAP feature rankings across BTC/LTC/ETC/ENJ/ROSE; maker/taker backtests validate adverse-selection microstructure theory. | `strategies/orderflow.py` |
| 2026 | [2606.03184v1](https://arxiv.org/abs/2606.03184v1) | Introduces FinStressTS, a synthetic benchmark of 30 diagnostic environments spanning six mechanism families; benchmarks 15 forecasters, finding autoregressive and linear models often beat Transformers on volatility-, tail- and jump-driven tasks. | strategies/evaluate.py |
| 2026 | [2602.07020v1](https://arxiv.org/abs/2602.07020v1) | Shows categorical attributes (issuer sector, domicile) dominate bond spread-curve predictability; proposes representation-learning embeddings for bond similarity that beat one-hot baselines, evaluated via sparse-issuer augmentation for risk modeling and curve construction. | `strategies/fixed_income.py` |
| 2026 | [2607.05291v1](https://arxiv.org/abs/2607.05291v1) | Compares nine zero-shot time-series foundation models with eight econometric specs for realized-volatility forecasting across 50 assets; only Tiny Time Mixers beats Log-HAR at every horizon, and narrowly. | strategies/long_memory.py |
| 2026 | [2604.00346v2](https://arxiv.org/abs/2604.00346v2) | Forecasts limit-order-book durations with a self-exciting flexible residual point process that preserves heavy-tailed interarrival times; proves Harris ergodicity and reports strong predictive performance on high-frequency data. | `strategies/orderflow.py` |
| 2026 | [2603.19286v1](https://arxiv.org/abs/2603.19286v1) | Integrates a pre-trained LLM with daily financial news for multi-stock prediction, using stock-name embeddings and self-, cross- and position-aware self-attentive pooling to filter news by relevance. | `strategies/news_relevance.py` |
| 2026 | [2602.00196v1](https://arxiv.org/abs/2602.00196v1) | Uses LLMs (RAG, programmatic prompting) to synthesize economically motivated equity features from analyst/options/price-volume data; competitive with baselines, 14-91% Sharpe gains, weakly correlated with traditional features. | `strategies/factors.py` |
| 2026 | [2605.11645v1](https://arxiv.org/abs/2605.11645v1) | GeomHerd tracks Ollivier-Ricci curvature on LLM-agent interaction graphs to quantify herding forward-looking, bypassing price-correlation lag; mean-field bridge links it to the CSAD statistic. | strategies/consensus.py |
| 2026 | [2604.09821v2](https://arxiv.org/abs/2604.09821v2) | Two-stage panel forecaster (global pooled AR(1) plus block-specific local residual models) lifts out-of-sample R2 from 0.630 to 0.677 on a 93-actor quarterly panel, confirmed on held-out 2015-2024 windows. | `strategies/cross_section.py` |
| 2026 | [2608.26127v1](https://arxiv.org/abs/2608.26127v1) | Proposes FA-GSTN, reframing realized-volatility forecasting as modeling a spatio-temporal graph over the implied-volatility surface; it sets state of the art (R^2 up to 0.473) and is data-efficient and stress-robust. | strategies/options_surface.py |
| 2026 | [2606.08232v3](https://arxiv.org/abs/2606.08232v3) | 15-day paper-traded Solana memecoin deployment (190 trades, +117.7%): worst entry hours not significant (p=0.56), removing the top three trades makes returns unprofitable, and rejected tokens often hit 50% drawdown. | strategies/refusal_ledger.py |
| 2026 | [2602.00086v3](https://arxiv.org/abs/2602.00086v3) | Evaluates DeBERTa/RoBERTa/FinBERT news-sentiment models for stock movement prediction; DeBERTa reaches 75% accuracy, a three-model ensemble about 80%, and sentiment features slightly help LSTM/PatchTST/tPatchGNN classifiers. | `strategies/sentiment_research.py` |
| 2026 | [2602.06198v1](https://arxiv.org/abs/2602.06198v1) | Gradient-boosting classifier on SEC Form 4 insider purchases in microcaps (17,237 trades, 2018-2024) reaches AUC 0.70; distance from 52-week high dominates (36%); post-run-up disclosures yield 6.3% mean CAR. | `strategies/signal_analysis.py` |
| 2026 | [2602.07048v2](https://arxiv.org/abs/2602.07048v2) | Hybrid causal screener: Granger causality finds lead-lag pairs in Kalshi prediction markets, LLM semantic filter re-ranks them by plausible transmission; win rate 51.4%->54.5%, average loss $649->$347. | `strategies/statistical.py` |
| 2026 | [2603.19944v2](https://arxiv.org/abs/2603.19944v2) | Tests ChatGPT, Gemini, DeepSeek and Perplexity across three prompting strategies on stock picks; LLMs show reasoning failures and hallucinations but can beat the market under human supervision and filing grounding. | `strategies/debate_claim.py` |
| 2026 | [2606.22719v1](https://arxiv.org/abs/2606.22719v1) | Leakage-controlled evaluation of a retrieval-augmented LLM ranking seven U.S. equity style factors from decision-time macro nowcasts; median monthly rank IC +0.154, but a kNN macro-analog baseline recovers comparable median IC. | strategies/data_quality.py |
| 2026 | [2603.20965v2](https://arxiv.org/abs/2603.20965v2) | A logistic meta-classifier aggregates three zero-shot LLM disclosure classifiers (label, confidence, rationale) into a next-day stock return-direction signal, with contamination-controlled evaluation. | `strategies/text_factors.py` |
| 2026 | [2607.25189v1](https://arxiv.org/abs/2607.25189v1) | Long-memory GARCH with level-and-slope updates in a two-dimensional Markov state; establishes positive Harris recurrence and delivers competitive out-of-sample volatility forecasts while capturing low-frequency persistence. | strategies/long_memory.py |
| 2026 | [2608.09641v1](https://arxiv.org/abs/2608.09641v1) | Shows the smallest eigenvalues of financial correlation matrices carry market-synchronization information, complementing large-eigenvalue PCA/RMT, and validates it in descriptive and predictive experiments. | strategies/covariance_models.py |
| 2026 | [2606.00624v1](https://arxiv.org/abs/2606.00624v1) | HANET hierarchically nests daily asset-return signals inside monthly macro windows with cross-attention; attention over macro contexts adapts to scarce regimes across 55 liquid futures. | strategies/regime_score.py |
| 2026 | [2604.03499v3](https://arxiv.org/abs/2604.03499v3) | Marking-aware sequential VaR recalibration targets normalized option-book loss with only forecast-time information, recalibrating upper-tail VaR from past residuals; fixes book, marking and loss-scale choices standard pipelines leave outside the target. | `strategies/book_risk.py` |
| 2026 | [2608.03616v1](https://arxiv.org/abs/2608.03616v1) | Measures the branching ratio of the October 2025 crypto-perpetual liquidation cascade in-flight; it ran deeply subcritical at lambda ~0.1-0.2, with 88% of forced selling inside thirty minutes and 63% absorbed off-book. | strategies/tail_risk.py |
| 2026 | [2603.21672v3](https://arxiv.org/abs/2603.21672v3) | Bayesian framework where investors underestimate structural breaks in factor risk premia; a predictive-likelihood-ratio mislearning intensity relates to persistent pricing distortions rather than immediate collapse. | `strategies/factors.py` |
| 2026 | [2606.06190v1](https://arxiv.org/abs/2606.06190v1) | Triple-timeframe Markov-switching GARCH (daily/4-hour/hourly) with Filardo time-varying transition probabilities combines three AR(1)-MS-GARCH models into a 27-state tensor, achieving superior out-of-sample EUR/USD volatility forecasting versus conventional GARCH. | strategies/volatility_models.py |
| 2026 | [2605.21504v1](https://arxiv.org/abs/2605.21504v1) | Chronos-2 time-series foundation model: multivariate inputs beat univariate across Magnificent-7 and Treasury-rate panels (2000-2025 rolling), but mixing equity and rate series degrades accuracy. | scripts/forecast_ledger.py |
| 2026 | [2603.20456v1](https://arxiv.org/abs/2603.20456v1) | Neural HMM with adaptive granularity attention: a dilated-CNN tick encoder plus wavelet-LSTM, gated by local volatility and transaction intensity, for high-frequency order-flow modeling across scales. | `strategies/orderflow.py` |
| 2026 | [2603.28257v2](https://arxiv.org/abs/2603.28257v2) | KAN-PCA autoencoder replaces PCA's linear projections with B-spline KAN encodings; on 20 S&P500 returns (2015-2024) reconstructs R2=66.57% vs PCA's 62.99% with 3 factors, matching PCA out-of-sample. | `strategies/covariance_models.py` |
| 2026 | [2609.08106v1](https://arxiv.org/abs/2609.08106v1) | Decomposes MASTER's inter-stock attention: learned attention is near-uniform yet its low-rank deviation carries cross-sectional value; Nystrom attention with 32 landmarks matches full O(N^2) attention, while graph alternatives degrade performance. | strategies/cross_section.py |
| 2026 | [2607.19005v2](https://arxiv.org/abs/2607.19005v2) | Observable Matrix Dynamics tracks S&P 500 correlation distance matrices and Markov ranking chains; effective dimension collapses in 2008/2020, and correlation geometry forecasts the endogenous 2008 crisis but not 2020. | strategies/regime_state.py |
| 2026 | [2609.04420v1](https://arxiv.org/abs/2609.04420v1) | Derives exact finite-population variance and optimal stratified allocation for weighted rare-event risk estimation; the imbalance ratio cancels from the allocation, making equal allocation the default with realised ratio gamma=min(2*pi/f,1). | strategies/evaluate.py |
| 2026 | [2603.29763v1](https://arxiv.org/abs/2603.29763v1) | Derives a CEV price process for constant-product AMM tokens from diffusive pool flow, with closed-form European options and liquidity-adjusted Greeks; CEV leverage skew makes Black-Scholes underprice 20%-OTM puts ~6% IV at every pool depth. | `strategies/options_math.py` |
| 2026 | [2608.26115v1](https://arxiv.org/abs/2608.26115v1) | Re-estimates option-implied crash predictability on 12.36M firm-days (2015-2026); the smirk-return relation fades while IV spread and risk-neutral skewness persist, with boosted trees best in the AI/mega-cap regime. | strategies/options_surface.py |
| 2026 | [2606.06823v1](https://arxiv.org/abs/2606.06823v1) | PandaAI, a closed-loop neuro-symbolic LLM agent with market-regime modeling and constrained alpha generation, reports on CSI 300 18.2% higher Rank IC and 25.7% lower maximum drawdown than state-of-the-art time-series models. | strategies/alpha_zoo.py |
| 2026 | [2603.28198v1](https://arxiv.org/abs/2603.28198v1) | PCGS fixes the generalized-share recursion while adaptively varying post-loss controls; PCGS-TF uses a causal Transformer update controller and attains pathwise weighted regret guarantees for strictly online switching-oracle tracking. | `strategies/score_engine.py` |
| 2026 | [2605.25894v1](https://arxiv.org/abs/2605.25894v1) | Multi-modal LSTM/Transformer on 15 fundamentals, 3 technicals and FinBERT news sentiment predicts earnings-day direction; Transformer achieves higher macro F1 and sentiment adds consistent value. | strategies/events.py |
| 2026 | [2602.00133v1](https://arxiv.org/abs/2602.00133v1) | PredictionMarketBench gives SWE-bench-style event-driven replay of Kalshi order books with maker/taker fees and a tool-based agent interface; naive agents underperform on costs while fee-aware strategies stay competitive. | `strategies/backtest_engine.py` |
| 2026 | [2607.19453v1](https://arxiv.org/abs/2607.19453v1) | Audits candle-based Binance ML timing models: after extensive predecessor search an unchanged ten-pair selector lost 6.72% over 19 cycles at 31bps cost, and every evaluated policy remains NO_TRADE. | strategies/evaluate.py |
| 2026 | [2609.20550v1](https://arxiv.org/abs/2609.20550v1) | Decomposes principal-component estimation error in high-dimensional factor models into out-of-subspace (estimable) and in-subspace terms with almost sure limits; in a three-factor US equity simulation out-of-subspace error dominates. | strategies/covariance_models.py |
| 2026 | [2604.19580v1](https://arxiv.org/abs/2604.19580v1) | Shows quantile-based battery trading strategies (QBTS) do not incentivize honest probabilistic forecasts and ignore intertemporal price dependence; reframes battery optimization as a stochastic program evaluating the economic value of forecast accuracy. | `strategies/evaluate.py` |
| 2026 | [2608.02828v2](https://arxiv.org/abs/2608.02828v2) | Proposes observation-driven filters driven by the derivative of any proper scoring rule, not just the log score; separates rule, scaling and autoregressive roles and applies it to variance-forecast loss and VaR/PIT calibration. | strategies/volatility_models.py |
| 2026 | [2607.27099v1](https://arxiv.org/abs/2607.27099v1) | Models rainfall clustering with critical Hawkes processes and heavy-tailed power-law kernels; aggregated rainfall converges to a rough fractional process with Hurst exponent 0.01-0.1, linking to market-microstructure and volatility models. | strategies/long_memory.py |
| 2026 | [2601.08571v1](https://arxiv.org/abs/2601.08571v1) | Hilbert-Huang regime identification plus variable-length Markov modeling on global equity indices finds developed markets normalize after stress while developing markets retain residual tail dependence and downside persistence. | `strategies/regime.py` |
| 2026 | [2606.02657v1](https://arxiv.org/abs/2606.02657v1) | Generalization bounds for Markov-switching distribution shift decompose regime-composition mismatch from regime sensitivity; the ex-post realized gap detects crisis geometry but not temporal arrival. | strategies/coverage_window.py |
| 2026 | [2601.10732v1](https://arxiv.org/abs/2601.10732v1) | Student-t HMM identifies crisis regimes where Value (HML) Granger-causes Size (SMB) at a 9-day lag (p<1e-4, 5/6 stress events); no trading profit, framed for risk management. | `strategies/regime.py` |
| 2026 | [2608.12251v1](https://arxiv.org/abs/2608.12251v1) | Proposes RG-ResMoE, a regime-gated residual mixture-of-experts for cross-sectional volatility forecasting; routing regime state to experts beats appending it as input, improving accuracy, stability and VaR calibration. | strategies/volatility_models.py |
| 2026 | [2604.10402v4](https://arxiv.org/abs/2604.10402v4) | Risk-sensitive specialist routing with online evaluation and state-dependent gating combines regime-specific ETF volatility forecasters; versus a rolling-best baseline it cuts high-volatility loss ~24% and underprediction loss ~22%. | `strategies/regime_performance.py` |
| 2026 | [2604.07159v1](https://arxiv.org/abs/2604.07159v1) | SBBTS extends the Schrodinger-Bass formulation to multi-step series, jointly calibrating drift and stochastic volatility via a conditional-transport decomposition; Heston experiments reproduce marginals and temporal dynamics. | `strategies/volatility_models.py` |
| 2026 | [2605.17724v1](https://arxiv.org/abs/2605.17724v1) | Compares LSTM and gradient boosting on MNQ 5-min intraday prediction 2021-2025; no config beats the 51.8% base rate (best 50.89%, permutation p=0.135/0.515). | strategies/falsification.py |
| 2026 | [2603.05917v3](https://arxiv.org/abs/2603.05917v3) | Proposes a node-transformer over a stock graph whose edges encode sector affiliation and price correlation, fused with BERT sentiment for cross-sectional stock price forecasting; no numeric result reported. | `strategies/sentiment.py` |
| 2026 | [2604.19107v1](https://arxiv.org/abs/2604.19107v1) | Random-Matrix-Theory complexity gap (normalized largest eigenvalue minus average pairwise correlation) shows a three-phase G5 pattern across shocks: rich structure before, near-zero synchronization during, and recovery after. | `strategies/covariance_models.py` |
| 2026 | [2606.12446v2](https://arxiv.org/abs/2606.12446v2) | Shows persistent latent default-probability dynamics plus temporal coarse-graining generate effective default correlation, explaining long-horizon overdispersion and autocorrelation; coarse-graining monthly posterior paths improves predictive density and regularizes variance attribution. | strategies/credit_spread.py |
| 2026 | [2601.07588v1](https://arxiv.org/abs/2601.07588v1) | Meta-learning stacking framework aligns financial-statement reference dates with evaluation dates to remove publication-delay bias in Italian SME credit scoring, improving temporal consistency and predictive stability over standard ensembles. | `strategies/data_quality.py` |
| 2026 | [2602.00073v1](https://arxiv.org/abs/2602.00073v1) | Test-time adaptation updates only normalization affine parameters on a frozen backbone under regime shift; batch-norm statistics update is a robust default for SPY/QQQ/EUR-USD, aggressive norm adaptation can hurt. | `strategies/regime.py` |
| 2026 | [2606.25986v1](https://arxiv.org/abs/2606.25986v1) | Finds an inference-compute power-law frontier in limit order book prediction on FI-2010 (R²=0.941 extrapolation), motivating FastBiNLOB, a dense axis-separable LOB mixer beating published macro-F1 targets at notably lower latency. | strategies/orderflow.py |
| 2026 | [2601.21447v1](https://arxiv.org/abs/2601.21447v1) | Extends GARCH CCC/STCC/DCC models with Trade Policy Uncertainty and a presidential dummy for US stock-bond correlations 2015-2025; time-varying specs win, DCC+TPU gives best fit and forecasts. | `strategies/covariance_models.py` |
| 2026 | [2606.20145v1](https://arxiv.org/abs/2606.20145v1) | Finds volatility and correlations increase in strong up- or down-trends, quantified by quadratic polynomials of today's trend strength; refines mean-reversion models, improves market-risk prediction and supports a critical lattice-gas view. | strategies/volatility_models.py |
| 2026 | [2605.13407v1](https://arxiv.org/abs/2605.13407v1) | PRISM-VQ dynamic factor model combines expert priors, vector-quantized discrete latent factors and a structure-conditioned mixture-of-experts; improves cross-sectional ranking on CSI300/S&P500. | strategies/cross_section.py |
| 2026 | [2609.12793v1](https://arxiv.org/abs/2609.12793v1) | Proposes VertiFuseX, a hybrid LSTM with penultimate-layer vertical fusion of multi-scale temporal features; it achieves 30-54% MAPE reductions versus LSTM baselines across 10 global equity indices (2010-2024). | scripts/forecast_ledger.py |
| 2026 | [2609.14733v1](https://arxiv.org/abs/2609.14733v1) | Proposes WaVeFuse, wavelet-denoised OHLCV plus channel-wise CWT, CNN-BiLSTM and Transformer branches fused by vertical attention; it reaches R2 0.81-0.96 and 70.5-78.3% directional accuracy on four indices. | scripts/forecast_ledger.py |
| 2026 | [2607.12248v2](https://arxiv.org/abs/2607.12248v2) | Base-rate-honest frozen-data benchmark for LoRA-adapted TimesFM: apparent 80% directional accuracy is a ~0.70 always-up base rate, and pooled LoRA shows no directional skill on NASDAQ-100 or S&P 500. | strategies/evaluate.py |
| 2026 | [2602.11020v2](https://arxiv.org/abs/2602.11020v2) | Compares early vs late multi-view fusion (OHLCV chart, indicator matrix) for next-day direction under time-block splits with embargo; fusion is regime-dependent, late fusion more reliable once labels stabilize, joint FGSM/PGD attacks remain hard. | `strategies/evaluate.py` |
| 2026 | [2608.10693v1](https://arxiv.org/abs/2608.10693v1) | Uses a 2D convolutional LSTM with FOMC-date features to forecast the implied-volatility surface; pre-announcement IV rises strongest for short-dated OTM options in high-volatility regimes, with a limited but real ML edge. | strategies/options_surface.py |
| 2026 | [2601.08896v1](https://arxiv.org/abs/2601.08896v1) | XGBoost forecasts one-step-ahead NEPSE index log-returns using 30 lagged returns, rolling volatility, and 14-period RSI, with Optuna tuning and walk-forward expanding/rolling validation avoiding lookahead bias. | `strategies/backtest_engine.py` |
| 2025 | [2507.09347v1](https://arxiv.org/abs/2507.09347v1) | Clusters nine equities by volatility via GMM, then Granger causality, PCMCI and transfer entropy find lead-lag links; DTW/KNN sets trade lag, backtest returning 15.38% versus 10.39% buy-and-hold. | `strategies/statistical.py` |
| 2025 | [2508.20101v1](https://arxiv.org/abs/2508.20101v1) | Heterogeneous spatiotemporal GARCH adds spatially correlated innovations and varying parameters over a balance-sheet-derived proxy space; predicts firm volatility with contagion effects. | `strategies/covariance_models.py` |
| 2025 | [2504.06028v1](https://arxiv.org/abs/2504.06028v1) | Models uncovered-interest-parity deviations as a mean-reverting risk premium via an Ornstein-Uhlenbeck process inside the exchange-rate SDE; closed-form forecast distributions are coverage-backtested on USD/KRW, strong short/long term but weak at 3 months. | `strategies/mean_reversion.py` |
| 2025 | [2510.16636v1](https://arxiv.org/abs/2510.16636v1) | Three-step framework: right-tailed unit-root test identifies S&P 500 bubbles, NLP extracts news-sentiment features, and ensemble learning predicts bubble occurrence with macro indicators. | `strategies/regime.py` |
| 2025 | [2508.02686v1](https://arxiv.org/abs/2508.02686v1) | Mixture-of-Experts combines an RNN for high-volatility stocks with linear regression for stable ones via a volatility-aware gate; across 30 US stocks it cuts MSE up to 33% and 28% versus standalone models. | `strategies/regime_score.py` |
| 2025 | [2509.10542v1](https://arxiv.org/abs/2509.10542v1) | Adaptive Temporal Fusion Transformer segments crypto subseries at relative maxima past a threshold, using dynamic subseries lengths and pattern categories to improve short-term forecasting over vanilla TFT. | `strategies/volatility_models.py` |
| 2025 | [2503.24241v1](https://arxiv.org/abs/2503.24241v1) | Analyzes decades of S&P500 accumulated returns' gain/loss distributions, fitting power-law tail CDFs with confidence intervals and U-tests; mean rises near-linearly with accumulation days, skew stays negative and roughly constant, variance scales linearly, contradicting symmetric-return theory. | `strategies/tail_risk.py` |
| 2025 | [2505.24650v1](https://arxiv.org/abs/2505.24650v1) | First finance application of mechanistic interpretability to LLMs, reverse-engineering activations and circuits to observe and modify behavior; demonstrates use cases in trading strategies, sentiment, bias and hallucination detection for regulatory transparency. | `strategies/debate_claim.py` |

## Low relevance / background (569)

| year | id | title |
| --- | --- | --- |
| 2026 | [2602.21869v3](https://arxiv.org/abs/2602.21869v3) | A Bayesian approach to out-of-sample network reconstruction |
| 2026 | [2603.16886v1](https://arxiv.org/abs/2603.16886v1) | A Controlled Comparison of Deep Learning Architectures for Multi-Horizon Financial Forecasting: Evidence from 918 Experiments |
| 2026 | [2608.20727v1](https://arxiv.org/abs/2608.20727v1) | A Multiscale Ball Test for Conditional Mean Independence |
| 2026 | [2607.16281v1](https://arxiv.org/abs/2607.16281v1) | A Novel Hybrid Quantum Reservoir Computing (nHQRC) for Phase Transition Detection in Non-Equilibrium Dynamical Systems |
| 2026 | [2608.26106v1](https://arxiv.org/abs/2608.26106v1) | A Statistical-Finance Benchmark for Same-Day Directional Stock Prediction: Walk-Forward Evidence from SPY |
| 2026 | [2608.12424v2](https://arxiv.org/abs/2608.12424v2) | AI-Driven Multiscenario Interest Rate Forecasting: A Proof of Concept for Banking Asset Management |
| 2026 | [2603.18107v1](https://arxiv.org/abs/2603.18107v1) | ARTEMIS: A Neuro Symbolic Framework for Economically Constrained Market Dynamics |
| 2026 | [2601.22200v1](https://arxiv.org/abs/2601.22200v1) | Adaptive Benign Overfitting (ABO): Overparameterized RLS for Online Learning in Non-stationary Time-series |
| 2026 | [2603.18021v2](https://arxiv.org/abs/2603.18021v2) | Anomaly prediction in XRP price with topological features |
| 2026 | [2604.22801v2](https://arxiv.org/abs/2604.22801v2) | Beyond Sequential Prediction: Learning Financial Market Dynamics in Volatile and Non-Stationary Environments through Sentiment-Conditioned Generative Modelling |
| 2026 | [2602.00037v2](https://arxiv.org/abs/2602.00037v2) | Bitcoin Price Prediction using Machine Learning and Combinatorial Fusion Analysis |
| 2026 | [2608.12259v1](https://arxiv.org/abs/2608.12259v1) | Calibration Bets on the Past: Post-Training Quantization for Financial Time-Series Forecasting |
| 2026 | [2603.00422v3](https://arxiv.org/abs/2603.00422v3) | Coupled Supply and Demand Forecasting in Platform Accommodation Markets |
| 2026 | [2601.16821v3](https://arxiv.org/abs/2601.16821v3) | Directional-Shift Dirichlet ARMA Models for Compositional Time Series with Structural Break Intervention |
| 2026 | [2608.11505v1](https://arxiv.org/abs/2608.11505v1) | Does a Structural Model Add Anything to the Closing Price? Calibrated forecasting, incremental information, and match leverage in the Italian Serie A |
| 2026 | [2604.09650v1](https://arxiv.org/abs/2604.09650v1) | Dynamic Forecasting and Temporal Feature Evolution of Stock Repurchases in Listed Companies Using Attention-Based Deep Temporal Networks |
| 2026 | [2607.28847v1](https://arxiv.org/abs/2607.28847v1) | Effort-Centric Fairness in Lending Decisions |
| 2026 | [2607.25459v1](https://arxiv.org/abs/2607.25459v1) | Emergent Latent-State Computation under Stochastic Volatility |
| 2026 | [2604.22995v1](https://arxiv.org/abs/2604.22995v1) | Equations of Motion for an Economy: Capital Deepening, Technology, and Firm Survival |
| 2026 | [2602.00049v1](https://arxiv.org/abs/2602.00049v1) | Exploring the Interpretability of Forecasting Models for Energy Balancing Market |
| 2026 | [2608.26174v1](https://arxiv.org/abs/2608.26174v1) | Forecasting Economically Significant Bitcoin Moves: A Multi-Scale TCN with Profit-Optimized Thresholds |
| 2026 | [2602.18358v4](https://arxiv.org/abs/2602.18358v4) | Forecasting the Evolving Composition of Inbound Tourism Demand: A Bayesian Compositional Time Series Approach Using Platform Booking Data |
| 2026 | [2609.06267v1](https://arxiv.org/abs/2609.06267v1) | From Discrete Trailing Returns to a Continuous Graphical Profile: Return-to-Present Curves |
| 2026 | [2605.23962v1](https://arxiv.org/abs/2605.23962v1) | From Index to Equity: Pre-Training Transformers for Stock Return Prediction |
| 2026 | [2608.26122v1](https://arxiv.org/abs/2608.26122v1) | From electricity prices to profits: multidimensional probabilistic forecasting for BESS trading |
| 2026 | [2606.05138v1](https://arxiv.org/abs/2606.05138v1) | Generating Financial Time Series by Matching Random Convolutional Features |
| 2026 | [2606.30037v1](https://arxiv.org/abs/2606.30037v1) | Heads, Not Backbones: Output Heads Dominate Architectures on Fat-Tailed Returns |
| 2026 | [2608.08825v1](https://arxiv.org/abs/2608.08825v1) | Hybrid Neural-Classical Correction for Frozen Time Series Foundation Models: A Comprehensive Ablation Study on High-Frequency Stock Prediction |
| 2026 | [2601.11601v1](https://arxiv.org/abs/2601.11601v1) | Latent Variable Phillips Curve |
| 2026 | [2605.15767v1](https://arxiv.org/abs/2605.15767v1) | Market Makers and Risk Aversion: A Hamiltonian Approach to the Excess Volatility Puzzle |
| 2026 | [2609.08060v1](https://arxiv.org/abs/2609.08060v1) | Pre-game paired-comparison modeling of professional League of Legends map outcomes |
| 2026 | [2602.14860v1](https://arxiv.org/abs/2602.14860v1) | Predicting the success of new crypto-tokens: the Pump.fun case |
| 2026 | [2601.19321v1](https://arxiv.org/abs/2601.19321v1) | Predictive Accuracy versus Interpretability in Energy Markets: A Copula-Enhanced TVP-SVAR Analysis |
| 2026 | [2606.00061v1](https://arxiv.org/abs/2606.00061v1) | Reflexivity as Prompt: Does Awareness of Self-Reinforcing Market Dynamics Improve LLMs as Financial Market Forecasters? |
| 2026 | [2606.15701v1](https://arxiv.org/abs/2606.15701v1) | Robust Transformer-Based One-Step Stock Index Forecasting via Shifted Data Augmentation |
| 2026 | [2602.18572v1](https://arxiv.org/abs/2602.18572v1) | Sub-City Real Estate Price Index Forecasting at Weekly Horizons Using Satellite Radar and News Sentiment |
| 2026 | [2604.14619v1](https://arxiv.org/abs/2604.14619v1) | The Acoustic Camouflage Phenomenon: Re-evaluating Speech Features for Financial Risk Prediction |
| 2026 | [2604.16835v1](https://arxiv.org/abs/2604.16835v1) | The CTLNet for Shanghai Composite Index Prediction |
| 2026 | [2601.02677v1](https://arxiv.org/abs/2601.02677v1) | Uni-FinLLM: A Unified Multimodal Large Language Model with Modular Task Heads for Micro-Level Stock Prediction and Macro-Level Systemic Risk Assessment |
| 2026 | [2607.24065v1](https://arxiv.org/abs/2607.24065v1) | Variational Quantum Conditional Boltzmann Machines for Time-Series Forecasting: Architectures, Symmetric Hyperparameter Evaluation, and a Nonlinear Benchmark |
| 2025 | [2511.08658v1](https://arxiv.org/abs/2511.08658v1) | "It Looks All the Same to Me": Cross-index Training for Long-term Financial Series Prediction |
| 2025 | [2507.18643v1](https://arxiv.org/abs/2507.18643v1) | A Regression-Based Share Market Prediction Model for Bangladesh |
| 2025 | [2506.09851v2](https://arxiv.org/abs/2506.09851v2) | Advancing Exchange Rate Forecasting: Leveraging Machine Learning and AI for Enhanced Accuracy in Global Financial Markets |
| 2025 | [2504.13189v1](https://arxiv.org/abs/2504.13189v1) | BASIR: Budget-Assisted Sectoral Impact Ranking -- A Dataset for Sector Identification and Performance Prediction Using Language Models |
| 2025 | [2502.15726v1](https://arxiv.org/abs/2502.15726v1) | Bankruptcy analysis using images and convolutional neural networks (CNN) |
| 2025 | [2508.02685v1](https://arxiv.org/abs/2508.02685v1) | Benchmarking Classical and Quantum Models for DeFi Yield Prediction on Curve Finance |
| 2025 | [2506.08113v2](https://arxiv.org/abs/2506.08113v2) | Benchmarking Pre-Trained Time Series Models for Electricity Price Forecasting |
| 2025 | [2505.06190v1](https://arxiv.org/abs/2505.06190v1) | Beyond the Mean: Limit Theory and Tests for Infinite-Mean Autoregressive Conditional Durations |
| 2025 | [2510.15900v1](https://arxiv.org/abs/2510.15900v1) | Bitcoin Price Forecasting Based on Hybrid Variational Mode Decomposition and Long Short Term Memory Network |
| 2025 | [2501.09760v1](https://arxiv.org/abs/2501.09760v1) | Boosting the Accuracy of Stock Market Prediction via Multi-Layer Hybrid MTL Structure |
| 2025 | [2509.02388v1](https://arxiv.org/abs/2509.02388v1) | Bridging Human Cognition and AI: A Framework for Explainable Decision-Making Systems |
| 2025 | [2510.26035v1](https://arxiv.org/abs/2510.26035v1) | Budget Forecasting and Integrated Strategic Planning for Leaders |
| 2025 | [2510.18903v4](https://arxiv.org/abs/2510.18903v4) | Centered-Innovation MA for Bayesian Dirichlet ARMA: Theoretical Equivalence and an Application to Bank-Asset Shares |
| 2025 | [2506.08762v2](https://arxiv.org/abs/2506.08762v2) | EDINET-Bench: Evaluating LLMs on Complex Financial Tasks using Japanese Financial Statements |
| 2025 | [2511.17479v1](https://arxiv.org/abs/2511.17479v1) | Emergence of Randomness in Temporally Aggregated Financial Tick Sequences |
| 2025 | [2511.08588v1](https://arxiv.org/abs/2511.08588v1) | Explainable Federated Learning for U.S. State-Level Financial Distress Modeling |
| 2025 | [2505.01044v3](https://arxiv.org/abs/2505.01044v3) | Exploring different subtypes of recurrent event Cox-regression models in modelling lifetime default risk: A tutorial |
| 2025 | [2507.14160v1](https://arxiv.org/abs/2507.14160v1) | FinSurvival: A Suite of Large Scale Survival Modeling Tasks from Finance |
| 2025 | [2507.01979v1](https://arxiv.org/abs/2507.01979v1) | Forecasting Labor Markets with LSTNet: A Multi-Scale Deep Learning Approach |
| 2025 | [2507.01964v1](https://arxiv.org/abs/2507.01964v1) | Forecasting Nigerian Equity Stock Returns Using Long Short-Term Memory Technique |
| 2025 | [2501.13136v1](https://arxiv.org/abs/2501.13136v1) | Forecasting of Bitcoin Prices Using Hashrate Features: Wavelet and Deep Stacking Approach |
| 2025 | [2506.21246v1](https://arxiv.org/abs/2506.21246v1) | From On-chain to Macro: Assessing the Importance of Data Source Diversity in Cryptocurrency Market Forecasting |
| 2025 | [2503.15403v1](https://arxiv.org/abs/2503.15403v1) | HQNN-FSP: A Hybrid Classical-Quantum Neural Network for Regression-Based Financial Stock Market Prediction |
| 2025 | [2505.12806v1](https://arxiv.org/abs/2505.12806v1) | Hierarchical Representations for Evolving Acyclic Vector Autoregressions (HEAVe) |
| 2025 | [2512.15738v1](https://arxiv.org/abs/2512.15738v1) | Hybrid Quantum-Classical Ensemble Learning for S\&P 500 Directional Prediction |
| 2025 | [2508.20105v2](https://arxiv.org/abs/2508.20105v2) | Identification of phase correlations in Financial Stock Market Turbulence |
| 2025 | [2502.04097v3](https://arxiv.org/abs/2502.04097v3) | Impermanent loss and Loss-vs-Rebalancing II |
| 2025 | [2512.07860v1](https://arxiv.org/abs/2512.07860v1) | Integrating LSTM Networks with Neural Levy Processes for Financial Forecasting |
| 2025 | [2507.01973v2](https://arxiv.org/abs/2507.01973v2) | Integration of Wavelet Transform Convolution and Channel Attention with LSTM for Stock Price Prediction based Portfolio Allocation |
| 2025 | [2501.10535v3](https://arxiv.org/abs/2501.10535v3) | Lead Times in Flux: Analyzing Airbnb Booking Dynamics During Global Upheavals (2018-2022) |
| 2025 | [2510.13790v1](https://arxiv.org/abs/2510.13790v1) | Market-Based Variance of Market Portfolio and of Entire Market |
| 2025 | [2510.04556v2](https://arxiv.org/abs/2510.04556v2) | Model Monitoring: A General Framework with an Application to Non-life Insurance Pricing |
| 2025 | [2512.17225v2](https://arxiv.org/abs/2512.17225v2) | Modeling financial time series with $φ^{4}$ quantum field theory |
| 2025 | [2502.15853v1](https://arxiv.org/abs/2502.15853v1) | Multi-Agent Stock Prediction Systems: Machine Learning Models, Simulations, and Real-Time Trading Strategies |
| 2025 | [2504.19623v2](https://arxiv.org/abs/2504.19623v2) | Multi-Horizon Echo State Network Prediction of Intraday Stock Returns |
| 2025 | [2511.08622v2](https://arxiv.org/abs/2511.08622v2) | Multi-period Learning for Financial Time Series Forecasting |
| 2025 | [2505.01543v1](https://arxiv.org/abs/2505.01543v1) | Multiscale Causal Analysis of Market Efficiency via News Uncertainty Networks and the Financial Chaos Index |
| 2025 | [2504.18982v1](https://arxiv.org/abs/2504.18982v1) | On Bitcoin Price Prediction |
| 2025 | [2601.05274v1](https://arxiv.org/abs/2601.05274v1) | On the use of case estimate and transactional payment data in neural networks for individual loss reserving |
| 2025 | [2504.20058v2](https://arxiv.org/abs/2504.20058v2) | Predictive AI with External Knowledge Infusion: Datasets and Benchmarks for Stock Markets |
| 2025 | [2505.13933v2](https://arxiv.org/abs/2505.13933v2) | Quantum Reservoir Computing for Realized Volatility Forecasting |
| 2025 | [2511.18125v1](https://arxiv.org/abs/2511.18125v1) | Random processes for long-term market simulations |
| 2025 | [2512.17936v1](https://arxiv.org/abs/2512.17936v1) | Risk-Aware Financial Forecasting Enhanced by Machine Learning and Intuitionistic Fuzzy Multi-Criteria Decision-Making |
| 2025 | [2509.24151v1](https://arxiv.org/abs/2509.24151v1) | STRAPSim: A Portfolio Similarity Metric for ETF Alignment and Portfolio Trades |
| 2025 | [2507.21298v2](https://arxiv.org/abs/2507.21298v2) | Slomads Rising: Stay Length Shifts in Digital Nomad Travel, United States 2019-2024 |
| 2025 | [2508.11372v2](https://arxiv.org/abs/2508.11372v2) | Stealing Accuracy: Predicting Day-ahead Electricity Prices with Temporal Hierarchy Forecasting (THieF) |
| 2025 | [2502.15813v1](https://arxiv.org/abs/2502.15813v1) | Stock Price Prediction Using a Hybrid LSTM-GNN Model: Integrating Time-Series and Graph-Based Analysis |
| 2025 | [2511.05523v1](https://arxiv.org/abs/2511.05523v1) | The Evolution of Probabilistic Price Forecasting Techniques: A Review of the Day-Ahead, Intra-Day, and Balancing Markets |
| 2025 | [2511.05030v3](https://arxiv.org/abs/2511.05030v3) | The Shape of Markets: Machine learning modeling and Prediction Using 2-Manifold Geometries |
| 2025 | [2505.09620v1](https://arxiv.org/abs/2505.09620v1) | The impact of economic policies on housing prices. Approximations and predictions in the UK, the US, France, and Switzerland from the 1980s to today |
| 2025 | [2506.17244v1](https://arxiv.org/abs/2506.17244v1) | Transformers Beyond Order: A Chaos-Markov-Gaussian Framework for Short-Term Sentiment Forecasting of Any Financial OHLC timeseries Data |
| 2025 | [2601.00011v1](https://arxiv.org/abs/2601.00011v1) | Ultimate Forward Rate Prediction and its Application to Bond Yield Forecasting: A Machine Learning Perspective |
| 2025 | [2504.01964v2](https://arxiv.org/abs/2504.01964v2) | What Can 240,000 New Credit Transactions Tell Us About the Impact of NGEU Funds? |
| 2025 | [2512.17945v2](https://arxiv.org/abs/2512.17945v2) | What's the Price of Monotonicity? A Multi-Dataset Benchmark of Monotone-Constrained Gradient Boosting for Credit PD |
| 2024 | [2404.07298v3](https://arxiv.org/abs/2404.07298v3) | A Deep Learning Method for Predicting Mergers and Acquisitions: Temporal Dynamic Industry Networks |
| 2024 | [2410.12807v1](https://arxiv.org/abs/2410.12807v1) | A Hierarchical conv-LSTM and LLM Integrated Model for Holistic Stock Forecasting |
| 2024 | [2405.13076v1](https://arxiv.org/abs/2405.13076v1) | A K-means Algorithm for Financial Market Risk Forecasting |
| 2024 | [2410.02846v3](https://arxiv.org/abs/2410.02846v3) | A Spatio-Temporal Machine Learning Model for Mortgage Credit Risk: Default Probabilities and Loan Portfolios |
| 2024 | [2410.19291v2](https://arxiv.org/abs/2410.19291v2) | A Stock Price Prediction Approach Based on Time Series Decomposition and Multi-Scale CNN using OHLCT Images |
| 2024 | [2402.06689v1](https://arxiv.org/abs/2402.06689v1) | A Study on Stock Forecasting Using Deep Learning and Statistical Models |
| 2024 | [2407.18324v1](https://arxiv.org/abs/2407.18324v1) | AMA-LSTM: Pioneering Robust and Fair Financial Audio Analysis for Stock Volatility Prediction |
| 2024 | [2403.00273v1](https://arxiv.org/abs/2403.00273v1) | ARED: Argentina Real Estate Dataset |
| 2024 | [2410.21291v3](https://arxiv.org/abs/2410.21291v3) | Achilles, Neural Network to Predict the Gold Vs US Dollar Integration with Trading Bot for Automatic Trading |
| 2024 | [2404.07969v1](https://arxiv.org/abs/2404.07969v1) | An End-to-End Structure with Novel Position Mechanism and Improved EMD for Stock Forecasting |
| 2024 | [2401.05441v2](https://arxiv.org/abs/2401.05441v2) | An adaptive network-based approach for advanced forecasting of cryptocurrency values |
| 2024 | [2403.00770v1](https://arxiv.org/abs/2403.00770v1) | Blockchain Metrics and Indicators in Cryptocurrency Trading |
| 2024 | [2411.06076v1](https://arxiv.org/abs/2411.06076v1) | BreakGPT: Leveraging Large Language Models for Predicting Asset Price Surges |
| 2024 | [2402.14708v2](https://arxiv.org/abs/2402.14708v2) | CaT-GNN: Enhancing Credit Card Fraud Detection via Causal Temporal Graph Neural Networks |
| 2024 | [2411.13599v2](https://arxiv.org/abs/2411.13599v2) | Can ChatGPT Overcome Behavioral Biases in the Financial Sector? Classify-and-Rethink: Multi-Step Zero-Shot Reasoning in the Gold Investment |
| 2024 | [2408.06679v1](https://arxiv.org/abs/2408.06679v1) | Case-based Explainability for Random Forest: Prototypes, Critics, Counter-factuals and Semi-factuals |
| 2024 | [2403.14695v2](https://arxiv.org/abs/2403.14695v2) | Chain-structured neural architecture search for financial time series forecasting |
| 2024 | [2403.00777v1](https://arxiv.org/abs/2403.00777v1) | Combating Financial Crimes with Unsupervised Learning Techniques: Clustering and Dimensionality Reduction for Anti-Money Laundering |
| 2024 | [2409.03762v1](https://arxiv.org/abs/2409.03762v1) | Combining supervised and unsupervised learning methods to predict financial market movements |
| 2024 | [2411.05790v1](https://arxiv.org/abs/2411.05790v1) | Comparative Analysis of LSTM, GRU, and Transformer Models for Stock Price Prediction |
| 2024 | [2405.08089v1](https://arxiv.org/abs/2405.08089v1) | Comparative Study of Bitcoin Price Prediction |
| 2024 | [2409.08297v1](https://arxiv.org/abs/2409.08297v1) | Comparative Study of Long Short-Term Memory (LSTM) and Quantum Long Short-Term Memory (QLSTM): Prediction of Stock Market Movement |
| 2024 | [2401.09778v1](https://arxiv.org/abs/2401.09778v1) | Cross-Domain Behavioral Credit Modeling: transferability from private to central data |
| 2024 | [2410.05297v1](https://arxiv.org/abs/2410.05297v1) | Cyber Risk Taxonomies: Statistical Analysis of Cybersecurity Risk Classifications |
| 2024 | [2412.18202v6](https://arxiv.org/abs/2412.18202v6) | Developing Cryptocurrency Trading Strategy Based on Autoencoder-CNN-GANs Algorithms |
| 2024 | [2411.05801v1](https://arxiv.org/abs/2411.05801v1) | Do LLM Personas Dream of Bull Markets? Comparing Human and AI Investment Strategies Through the Lens of the Five-Factor Model |
| 2024 | [2405.17070v2](https://arxiv.org/abs/2405.17070v2) | Efficient mid-term forecasting of hourly electricity load using generalized additive models |
| 2024 | [2404.00015v3](https://arxiv.org/abs/2404.00015v3) | Empowering Credit Scoring Systems with Quantum-Enhanced Machine Learning |
| 2024 | [2410.07216v1](https://arxiv.org/abs/2410.07216v1) | Evaluating Financial Relational Graphs: Interpretation Before Prediction |
| 2024 | [2405.11686v1](https://arxiv.org/abs/2405.11686v1) | Exploiting Distributional Value Functions for Financial Market Valuation, Enhanced Feature Creation and Improvement of Trading Algorithms |
| 2024 | [2401.10931v1](https://arxiv.org/abs/2401.10931v1) | Forecasting Cryptocurrency Staking Rewards |
| 2024 | [2411.15228v1](https://arxiv.org/abs/2411.15228v1) | Forecasting the Price of Rice in Banda Aceh after Covid-19 |
| 2024 | [2403.06779v1](https://arxiv.org/abs/2403.06779v1) | From Factor Models to Deep Learning: Machine Learning in Reshaping Empirical Asset Pricing |
| 2024 | [2412.10540v1](https://arxiv.org/abs/2412.10540v1) | Higher Order Transformers: Enhancing Stock Movement Prediction On Multimodal Time-Series Data |
| 2024 | [2407.13698v1](https://arxiv.org/abs/2407.13698v1) | International Trade Flow Prediction with Bilateral Trade Provisions |
| 2024 | [2404.16169v3](https://arxiv.org/abs/2404.16169v3) | Interpretable Machine Learning Models for Predicting the Next Targets of Activist Funds |
| 2024 | [2409.08282v3](https://arxiv.org/abs/2409.08282v3) | LSR-IGRU: Stock Trend Prediction Based on Long Short-Term Relationships and Improved GRU |
| 2024 | [2408.10255v2](https://arxiv.org/abs/2408.10255v2) | Large Investment Model |
| 2024 | [2409.06728v1](https://arxiv.org/abs/2409.06728v1) | Leveraging RNNs and LSTMs for Synchronization Analysis in the Indian Stock Market: A Threshold-Based Classification Approach |
| 2024 | [2412.14529v1](https://arxiv.org/abs/2412.14529v1) | Leveraging Time Series Categorization and Temporal Fusion Transformers to Improve Cryptocurrency Price Forecasting |
| 2024 | [2408.04644v2](https://arxiv.org/abs/2408.04644v2) | Lower Bounds of Uncertainty of Observations of Macroeconomic Variables and Upper Limits on the Accuracy of Their Forecasts |
| 2024 | [2410.20679v3](https://arxiv.org/abs/2410.20679v3) | MCI-GRU: Stock Prediction Model Based on Multi-Head Cross-Attention and Improved GRU |
| 2024 | [2402.06633v1](https://arxiv.org/abs/2402.06633v1) | MDGNN: Multi-Relational Dynamic Graph Neural Network for Comprehensive and Dynamic Stock Investment Prediction |
| 2024 | [2404.07179v1](https://arxiv.org/abs/2404.07179v1) | Machine learning-based similarity measure to forecast M&A from patent data |
| 2024 | [2402.18959v1](https://arxiv.org/abs/2402.18959v1) | MambaStock: Selective state space model for stock prediction |
| 2024 | [2408.16010v1](https://arxiv.org/abs/2408.16010v1) | Model-based and empirical analyses of stochastic fluctuations in economy and finance |
| 2024 | [2403.13192v1](https://arxiv.org/abs/2403.13192v1) | Modeling stock price dynamics on the Ghana Stock Exchange: A Geometric Brownian Motion approach |
| 2024 | [2411.12013v2](https://arxiv.org/abs/2411.12013v2) | Neural and Time-Series Approaches for Pricing Weather Derivatives: Performance and Regime Adaptation Using Satellite Data |
| 2024 | [2412.16333v1](https://arxiv.org/abs/2412.16333v1) | Optimizing Fintech Marketing: A Comparative Study of Logistic Regression and XGBoost |
| 2024 | [2410.01843v1](https://arxiv.org/abs/2410.01843v1) | Optimizing Time Series Forecasting: A Comparative Study of Adam and Nesterov Accelerated Gradient on LSTM and GRU networks Using Stock Market data |
| 2024 | [2406.19399v1](https://arxiv.org/abs/2406.19399v1) | Predicting Customer Goals in Financial Institution Services: A Data-Driven LSTM Approach |
| 2024 | [2409.04471v2](https://arxiv.org/abs/2409.04471v2) | Predicting Foreign Exchange EUR/USD direction using machine learning |
| 2024 | [2403.03410v1](https://arxiv.org/abs/2403.03410v1) | Prediction Of Cryptocurrency Prices Using LSTM, SVM And Polynomial Regression |
| 2024 | [2403.00774v2](https://arxiv.org/abs/2403.00774v2) | Regional inflation analysis using social network data |
| 2024 | [2404.03968v1](https://arxiv.org/abs/2404.03968v1) | Regularization for electricity price forecasting |
| 2024 | [2405.11431v2](https://arxiv.org/abs/2405.11431v2) | Review of deep learning models for crypto price prediction: implementation and evaluation |
| 2024 | [2410.07143v1](https://arxiv.org/abs/2410.07143v1) | SARF: Enhancing Stock Market Prediction with Sentiment-Augmented Random Forest |
| 2024 | [2410.07220v1](https://arxiv.org/abs/2410.07220v1) | Stock Price Prediction and Traditional Models: An Approach to Achieve Short-, Medium- and Long-Term Goals |
| 2024 | [2406.19414v1](https://arxiv.org/abs/2406.19414v1) | Stock Volume Forecasting with Advanced Information by Conditional Variational Auto-Encoder |
| 2024 | [2409.08281v1](https://arxiv.org/abs/2409.08281v1) | StockTime: A Time Series Specialized Large Language Model Architecture for Stock Price Prediction |
| 2024 | [2407.18519v1](https://arxiv.org/abs/2407.18519v1) | TCGPN: Temporal-Correlation Graph Pre-trained Network for Stock Forecasting |
| 2024 | [2406.19403v1](https://arxiv.org/abs/2406.19403v1) | Temporal distribution of clusters of investors and their application in prediction with expert advice |
| 2024 | [2411.13562v1](https://arxiv.org/abs/2411.13562v1) | The Role of AI in Financial Forecasting: ChatGPT's Potential and Challenges |
| 2024 | [2406.07354v1](https://arxiv.org/abs/2406.07354v1) | The Theory of Intrinsic Time: A Primer |
| 2024 | [2403.02523v1](https://arxiv.org/abs/2403.02523v1) | Transformer for Times Series: an Application to the S&P500 |
| 2024 | [2402.06638v1](https://arxiv.org/abs/2402.06638v1) | Transformers with Attentive Federated Aggregation for Time Series Stock Forecasting |
| 2024 | [2405.20715v1](https://arxiv.org/abs/2405.20715v1) | Transforming Japan Real Estate |
| 2024 | [2411.05829v1](https://arxiv.org/abs/2411.05829v1) | Utilizing RNN for Real-time Cryptocurrency Price Prediction and Trading Strategy Optimization |
| 2024 | [2410.01831v1](https://arxiv.org/abs/2410.01831v1) | Value of Information in the Mean-Square Case and its Application to the Analysis of Financial Time-Series Forecast |
| 2023 | [2302.07796v1](https://arxiv.org/abs/2302.07796v1) | A Comparative Predicting Stock Prices using Heston and Geometric Brownian Motion Models |
| 2023 | [2311.06280v1](https://arxiv.org/abs/2311.06280v1) | A Data-driven Deep Learning Approach for Bitcoin Price Forecasting |
| 2023 | [2308.08554v1](https://arxiv.org/abs/2308.08554v1) | AI-Assisted Investigation of On-Chain Parameters: Risky Cryptocurrencies and Price Factors |
| 2023 | [2304.09761v1](https://arxiv.org/abs/2304.09761v1) | An innovative Deep Learning Based Approach for Accurate Agricultural Crop Price Prediction |
| 2023 | [2311.10719v1](https://arxiv.org/abs/2311.10719v1) | Analysis of frequent trading effects of various machine learning models |
| 2023 | [2303.04581v1](https://arxiv.org/abs/2303.04581v1) | Application of supervised learning models in the Chinese futures market |
| 2023 | [2303.01923v3](https://arxiv.org/abs/2303.01923v3) | Bayesian CART models for insurance claims frequency |
| 2023 | [2304.09939v1](https://arxiv.org/abs/2304.09939v1) | Bitcoin: A life in crises |
| 2023 | [2303.16148v2](https://arxiv.org/abs/2303.16148v2) | Causal Modelling of Cryptocurrency Price Movements Using Discretisation-Aware Bayesian Networks |
| 2023 | [2303.17266v1](https://arxiv.org/abs/2303.17266v1) | Coskewness under dependence uncertainty |
| 2023 | [2303.09397v1](https://arxiv.org/abs/2303.09397v1) | Cryptocurrency Price Prediction using Twitter Sentiment Analysis |
| 2023 | [2302.08911v1](https://arxiv.org/abs/2302.08911v1) | DSE Stock Price Prediction using Hidden Markov Model |
| 2023 | [2305.04811v2](https://arxiv.org/abs/2305.04811v2) | Deep learning models for price forecasting of financial time series: A review of recent advancements: 2020-2022 |
| 2023 | [2303.03080v4](https://arxiv.org/abs/2303.03080v4) | Defining and comparing SICR-events for classifying impaired loans under IFRS 9 |
| 2023 | [2310.16845v1](https://arxiv.org/abs/2310.16845v1) | Dual-Class Stocks: Can They Serve as Effective Predictors? |
| 2023 | [2311.07597v2](https://arxiv.org/abs/2311.07597v2) | Enhancing Actuarial Non-Life Pricing Models via Transformers |
| 2023 | [2303.16149v1](https://arxiv.org/abs/2303.16149v1) | Explaining Exchange Rate Forecasts with Macroeconomic Fundamentals Using Interpretive Machine Learning |
| 2023 | [2302.13850v1](https://arxiv.org/abs/2302.13850v1) | Exploring the Advantages of Transformers for High-Frequency Trading |
| 2023 | [2303.16117v2](https://arxiv.org/abs/2303.16117v2) | Feature Engineering Methods on Multivariate Time-Series Data for Financial Data Science Competitions |
| 2023 | [2302.12118v1](https://arxiv.org/abs/2302.12118v1) | Financial Distress Prediction For Small And Medium Enterprises Using Machine Learning Techniques |
| 2023 | [2302.08897v1](https://arxiv.org/abs/2302.08897v1) | Forecasting the Turkish Lira Exchange Rates through Univariate Techniques: Can the Simple Models Outperform the Sophisticated Ones? |
| 2023 | [2306.12965v2](https://arxiv.org/abs/2306.12965v2) | Improved Financial Forecasting via Quantum Machine Learning |
| 2023 | [2303.09407v1](https://arxiv.org/abs/2303.09407v1) | Improving CNN-base Stock Trading By Considering Data Heterogeneity and Burst |
| 2023 | [2301.10166v1](https://arxiv.org/abs/2301.10166v1) | Leveraging Vision-Language Models for Granular Market Change Prediction |
| 2023 | [2308.04947v1](https://arxiv.org/abs/2308.04947v1) | Methods for Acquiring and Incorporating Knowledge into Stock Price Prediction: A Survey |
| 2023 | [2304.03038v1](https://arxiv.org/abs/2304.03038v1) | Modelling customer lifetime-value in the retail banking industry |
| 2023 | [2305.14378v1](https://arxiv.org/abs/2305.14378v1) | Predicting Stock Market Time-Series Data using CNN-LSTM Neural Network Model |
| 2023 | [2303.10481v1](https://arxiv.org/abs/2303.10481v1) | Predictive Optimized Model on Money Markets Instruments With Capital Market and Bank Rates Ratio |
| 2023 | [2308.11939v1](https://arxiv.org/abs/2308.11939v1) | Retail Demand Forecasting: A Comparative Study for Multivariate Time Series |
| 2023 | [2301.10153v1](https://arxiv.org/abs/2301.10153v1) | Sequential Graph Attention Learning for Predicting Dynamic Stock Trends (Student Abstract) |
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
| 2023 | [2310.05971v2](https://arxiv.org/abs/2310.05971v2) | Theoretical Economics as Successive Approximations of Statistical Moments |
| 2023 | [2301.13255v1](https://arxiv.org/abs/2301.13255v1) | Wavelet Analysis for Time Series Financial Signals via Element Analysis |
| 2022 | [2203.06848v1](https://arxiv.org/abs/2203.06848v1) | A Comparative Study on Forecasting of Retail Sales |
| 2022 | [2209.10720v1](https://arxiv.org/abs/2209.10720v1) | A Real Data-Driven Analytical Model to Predict Information Technology Sector Index Price of S&P 500 |
| 2022 | [2201.12286v1](https://arxiv.org/abs/2201.12286v1) | A Stock Trading System for a Medium Volatile Asset using Multi Layer Perceptron |
| 2022 | [2205.01094v3](https://arxiv.org/abs/2205.01094v3) | A Word is Worth A Thousand Dollars: Adversarial Attack on Tweets Fools Stock Predictions |
| 2022 | [2207.02799v1](https://arxiv.org/abs/2207.02799v1) | A multi-task network approach for calculating discrimination-free insurance prices |
| 2022 | [2209.09548v1](https://arxiv.org/abs/2209.09548v1) | An Attention Free Long Short-Term Memory for Time Series Forecasting |
| 2022 | [2208.14385v2](https://arxiv.org/abs/2208.14385v2) | Application of Convolutional Neural Networks with Quasi-Reversibility Method Results for Option Forecasting |
| 2022 | [2204.02623v2](https://arxiv.org/abs/2204.02623v2) | Attention-based CNN-LSTM and XGBoost hybrid model for stock prediction |
| 2022 | [2207.11577v1](https://arxiv.org/abs/2207.11577v1) | Augmented Bilinear Network for Incremental Multi-Stock Time-Series Classification |
| 2022 | [2201.02729v1](https://arxiv.org/abs/2201.02729v1) | Bitcoin Price Predictive Modeling Using Expert Correction |
| 2022 | [2204.12928v1](https://arxiv.org/abs/2204.12928v1) | Causal Analysis of Generic Time Series Data Applied for Market Prediction |
| 2022 | [2207.03221v1](https://arxiv.org/abs/2207.03221v1) | Clustering of Excursion Sets in Financial Market |
| 2022 | [2206.03278v1](https://arxiv.org/abs/2206.03278v1) | Cointegration and ARDL specification between the Dubai crude oil and the US natural gas market |
| 2022 | [2205.06677v1](https://arxiv.org/abs/2205.06677v1) | Collective behavior of stock prices in the time of crisis as a response to the external stimulus |
| 2022 | [2205.00974v1](https://arxiv.org/abs/2205.00974v1) | Cross Cryptocurrency Relationship Mining for Bitcoin Price Prediction |
| 2022 | [2206.13860v2](https://arxiv.org/abs/2206.13860v2) | Detection and Forecasting of Extreme event in Stock Price Triggered by Fundamental, Technical, and External Factors |
| 2022 | [2204.00883v1](https://arxiv.org/abs/2204.00883v1) | Electricity Price Forecasting: The Dawn of Machine Learning |
| 2022 | [2210.00876v1](https://arxiv.org/abs/2210.00876v1) | Embedding-based neural network for investment return prediction |
| 2022 | [2209.12664v1](https://arxiv.org/abs/2209.12664v1) | Feature-Rich Long-term Bitcoin Trading Assistant |
| 2022 | [2204.11735v1](https://arxiv.org/abs/2204.11735v1) | Forecasting Electricity Prices |
| 2022 | [2204.12914v3](https://arxiv.org/abs/2204.12914v3) | Forecasting foreign exchange rates with regression networks tuned by Bayesian optimization |
| 2022 | [2207.04794v1](https://arxiv.org/abs/2207.04794v1) | LASSO Principal Component Averaging -- a fully automated approach for point forecast pooling |
| 2022 | [2205.04736v1](https://arxiv.org/abs/2205.04736v1) | Large Scale Probabilistic Simulation of Renewables Production |
| 2022 | [2201.08218v1](https://arxiv.org/abs/2201.08218v1) | Long Short-Term Memory Neural Network for Financial Time Series |
| 2022 | [2203.01738v1](https://arxiv.org/abs/2203.01738v1) | Machine learning model to project the impact of Ukraine crisis |
| 2022 | [2203.08635v1](https://arxiv.org/abs/2203.08635v1) | Measurability of functionals and of ideal point forecasts |
| 2022 | [2208.14311v4](https://arxiv.org/abs/2208.14311v4) | Modeling Volatility and Dependence of European Carbon and Energy Prices |
| 2022 | [2210.00870v1](https://arxiv.org/abs/2210.00870v1) | Multiclass Sentiment Prediction for Stock Trading |
| 2022 | [2212.05916v1](https://arxiv.org/abs/2212.05916v1) | NETpred: Network-based modeling and prediction of multiple connected market indices |
| 2022 | [2204.12932v1](https://arxiv.org/abs/2204.12932v1) | NFT Appraisal Prediction: Utilizing Search Trends, Public Market Data, Linear Regression and Recurrent Neural Networks |
| 2022 | [2209.02407v1](https://arxiv.org/abs/2209.02407v1) | Predict stock prices with ARIMA and LSTM |
| 2022 | [2209.09649v3](https://arxiv.org/abs/2209.09649v3) | Predicting Mutual Funds' Performance using Deep Learning and Ensemble Techniques |
| 2022 | [2210.14605v2](https://arxiv.org/abs/2210.14605v2) | Predicting the State of Synchronization of Financial Time Series using Cross Recurrence Plots |
| 2022 | [2204.06109v1](https://arxiv.org/abs/2204.06109v1) | Prediction of motor insurance claims occurrence as an imbalanced machine learning problem |
| 2022 | [2204.09568v1](https://arxiv.org/abs/2204.09568v1) | Predictive Accuracy of a Hybrid Generalized Long Memory Model for Short Term Electricity Price Forecasting |
| 2022 | [2205.11439v1](https://arxiv.org/abs/2205.11439v1) | Probabilistic forecasting of German electricity imbalance prices |
| 2022 | [2209.01378v3](https://arxiv.org/abs/2209.01378v3) | RNN(p) for Power Consumption Forecasting |
| 2022 | [2205.06675v1](https://arxiv.org/abs/2205.06675v1) | Research on the correlation between text emotion mining and stock market based on deep learning |
| 2022 | [2206.06026v1](https://arxiv.org/abs/2206.06026v1) | Robust Knockoffs for Controlling False Discoveries With an Application to Bond Recovery Rates |
| 2022 | [2204.12929v2](https://arxiv.org/abs/2204.12929v2) | Sequence-Based Target Coin Prediction for Cryptocurrency Pump-and-Dump |
| 2022 | [2201.12291v1](https://arxiv.org/abs/2201.12291v1) | Simulating Using Deep Learning The World Trade Forecasting of Export-Import Exchange Rate Convergence Factor During COVID-19 |
| 2022 | [2211.13002v1](https://arxiv.org/abs/2211.13002v1) | Simulation-based Forecasting for Intraday Power Markets: Modelling Fundamental Drivers for Location, Shape and Scale of the Price Distribution |
| 2022 | [2205.04256v6](https://arxiv.org/abs/2205.04256v6) | SoK: Blockchain Decentralization |
| 2022 | [2208.13564v1](https://arxiv.org/abs/2208.13564v1) | Stock Market Prediction using Natural Language Processing -- A Survey |
| 2022 | [2201.04965v2](https://arxiv.org/abs/2201.04965v2) | Stock Movement Prediction Based on Bi-typed Hybrid-relational Market Knowledge Graph via Dual Attention Networks |
| 2022 | [2204.05783v1](https://arxiv.org/abs/2204.05783v1) | Stock Price Prediction using Sentiment Analysis and Deep Learning for Indian Markets |
| 2022 | [2208.08496v1](https://arxiv.org/abs/2208.08496v1) | Stock Prices as Janardan Galton Watson Process |
| 2022 | [2207.06605v2](https://arxiv.org/abs/2207.06605v2) | StockBot: Using LSTMs to Predict Stock Prices |
| 2022 | [2208.07254v1](https://arxiv.org/abs/2208.07254v1) | The Efficient Market Hypothesis for Bitcoin in the context of neural networks |
| 2022 | [2201.00350v5](https://arxiv.org/abs/2201.00350v5) | The Interpretability of LSTM Models for Predicting Oil Company Stocks: Impact of Correlated Features |
| 2022 | [2203.13001v1](https://arxiv.org/abs/2203.13001v1) | The application of techniques derived from artificial intelligence to the prediction of the solvency of bank customers: case of the application of the cart type decision tree (dt) |
| 2022 | [2212.05369v1](https://arxiv.org/abs/2212.05369v1) | Time Series Analysis in American Stock Market Recovering in Post COVID-19 Pandemic Period |
| 2022 | [2207.11486v1](https://arxiv.org/abs/2207.11486v1) | Time Series Prediction under Distribution Shift using Differentiable Forgetting |
| 2022 | [2208.08300v1](https://arxiv.org/abs/2208.08300v1) | Transformer-Based Deep Learning Model for Stock Price Prediction: A Case Study on Bangladesh Stock Market |
| 2022 | [2212.01267v1](https://arxiv.org/abs/2212.01267v1) | Understanding Cryptocoins Trends Correlations |
| 2022 | [2207.06273v1](https://arxiv.org/abs/2207.06273v1) | Understanding Unfairness in Fraud Detection through Model and Data Bias Interactions |
| 2022 | [2205.06673v1](https://arxiv.org/abs/2205.06673v1) | Univariate and Multivariate LSTM Model for Short-Term Stock Market Prediction |
| 2022 | [2207.04882v2](https://arxiv.org/abs/2207.04882v2) | Variations on two-parameter families of forecasting functions: seasonal/nonseasonal Models, comparison to the exponential smoothing and ARIMA models, and applications to stock market data |
| 2021 | [2104.05204v2](https://arxiv.org/abs/2104.05204v2) | A Fast Evidential Approach for Stock Forecasting |
| 2021 | [2111.08060v1](https://arxiv.org/abs/2111.08060v1) | A Multi-criteria Approach to Evolve Sparse Neural Architectures for Stock Market Forecasting |
| 2021 | [2103.09750v1](https://arxiv.org/abs/2103.09750v1) | A Survey of Forex and Stock Price Prediction Using Deep Learning |
| 2021 | [2104.07469v1](https://arxiv.org/abs/2104.07469v1) | A comparative study of Different Machine Learning Regressors For Stock Market Prediction |
| 2021 | [2103.15096v1](https://arxiv.org/abs/2103.15096v1) | Accurate Stock Price Forecasting Using Robust and Optimized Deep Learning Models |
| 2021 | [2110.12000v3](https://arxiv.org/abs/2110.12000v3) | Bank transactions embeddings help to uncover current macroeconomics |
| 2021 | [2112.15315v1](https://arxiv.org/abs/2112.15315v1) | Bayesian Testing Of Granger Causality In Functional Time Series |
| 2021 | [2107.03299v1](https://arxiv.org/abs/2107.03299v1) | Big Data Information and Nowcasting: Consumption and Investment from Bank Transactions in Turkey |
| 2021 | [2109.00983v1](https://arxiv.org/abs/2109.00983v1) | Bilinear Input Normalization for Neural Networks in Financial Forecasting |
| 2021 | [2104.04041v1](https://arxiv.org/abs/2104.04041v1) | CLVSA: A Convolutional LSTM Based Variational Sequence-to-Sequence Model with Attention for Predicting Trends of Financial Markets |
| 2021 | [2101.02287v2](https://arxiv.org/abs/2101.02287v2) | COVID19-HPSMP: COVID-19 Adopted Hybrid and Parallel Deep Information Fusion Framework for Stock Price Movement Prediction |
| 2021 | [2102.05448v1](https://arxiv.org/abs/2102.05448v1) | Combination of window-sliding and prediction range method based on LSTM model for predicting cryptocurrency |
| 2021 | [2103.00366v2](https://arxiv.org/abs/2103.00366v2) | Confronting Machine Learning With Financial Research |
| 2021 | [2112.10139v1](https://arxiv.org/abs/2112.10139v1) | Denoised Labels for Financial Time-Series Data via Self-Supervised Learning |
| 2021 | [2106.09664v1](https://arxiv.org/abs/2106.09664v1) | Design and Analysis of Robust Deep Learning Models for Stock Price Prediction |
| 2021 | [2112.15036v2](https://arxiv.org/abs/2112.15036v2) | Dimensionality reduction for prediction: Application to Bitcoin and Ethereum |
| 2021 | [2110.12003v1](https://arxiv.org/abs/2110.12003v1) | Embracing advanced AI/ML to help investors achieve success: Vanguard Reinforcement Learning for Financial Goal Planning |
| 2021 | [2105.10871v1](https://arxiv.org/abs/2105.10871v1) | Financial Time Series Analysis and Forecasting with HHT Feature Generation and Machine Learning |
| 2021 | [2101.03087v2](https://arxiv.org/abs/2101.03087v2) | Forecasting Commodity Prices Using Long Short-Term Memory Neural Networks |
| 2021 | [2112.15431v1](https://arxiv.org/abs/2112.15431v1) | Forecasting pandemic tax revenues in a small, open economy |
| 2021 | [2103.14080v1](https://arxiv.org/abs/2103.14080v1) | Forecasting with Deep Learning: S&P 500 index |
| 2021 | [2112.03946v1](https://arxiv.org/abs/2112.03946v1) | Generative Adversarial Network (GAN) and Enhanced Root Mean Square Error (ERMSE): Deep Learning for Stock Price Movement Prediction |
| 2021 | [2103.11706v1](https://arxiv.org/abs/2103.11706v1) | Interpreting Deep Learning Models with Marginal Attribution by Conditioning on Quantiles |
| 2021 | [2107.05592v1](https://arxiv.org/abs/2107.05592v1) | Investor Behavior Modeling by Analyzing Financial Advisor Notes: A Machine Learning Perspective |
| 2021 | [2107.11059v1](https://arxiv.org/abs/2107.11059v1) | LocalGLMnet: interpretable deep learning for tabular data |
| 2021 | [2106.00647v4](https://arxiv.org/abs/2106.00647v4) | Mapping the NFT revolution: market trends, trade networks and visual features |
| 2021 | [2108.11755v1](https://arxiv.org/abs/2108.11755v1) | Market Crash Prediction Model for Markets in A Rational Bubble |
| 2021 | [2107.03926v1](https://arxiv.org/abs/2107.03926v1) | Measuring Financial Time Series Similarity With a View to Identifying Profitable Stock Market Opportunities |
| 2021 | [2107.01017v1](https://arxiv.org/abs/2107.01017v1) | MegazordNet: combining statistical and machine learning standpoints for time series forecasting |
| 2021 | [2104.13947v1](https://arxiv.org/abs/2104.13947v1) | Modelling Net Loan Loss with Bayesian and Frequentist Regression Analysis |
| 2021 | [2106.12961v1](https://arxiv.org/abs/2106.12961v1) | Next-Day Bitcoin Price Forecast Based on Artificial intelligence Methods |
| 2021 | [2101.02296v1](https://arxiv.org/abs/2101.02296v1) | Predicting CEO Compensation in Non-Controlled Public Corporations with the Canonical Regression Quantile Method |
| 2021 | [2110.02206v1](https://arxiv.org/abs/2110.02206v1) | Predicting Credit Risk for Unsecured Lending: A Machine Learning Approach |
| 2021 | [2111.15355v1](https://arxiv.org/abs/2111.15355v1) | Prediction of Fund Net Value Based on ARIMA-LSTM Hybrid Model |
| 2021 | [2108.10065v1](https://arxiv.org/abs/2108.10065v1) | Previsão dos preços de abertura, mínima e máxima de índices de mercados financeiros usando a associação de redes neurais LSTM |
| 2021 | [2111.08390v1](https://arxiv.org/abs/2111.08390v1) | Price Stability of Cryptocurrencies as a Medium of Exchange |
| 2021 | [2106.02522v5](https://arxiv.org/abs/2106.02522v5) | Price graphs: Utilizing the structural information of financial time series for stock prediction |
| 2021 | [2106.07361v1](https://arxiv.org/abs/2106.07361v1) | Probabilistic Forecasting of Imbalance Prices in the Belgian Context |
| 2021 | [2104.06259v1](https://arxiv.org/abs/2104.06259v1) | Profitability Analysis in Stock Investment Using an LSTM-Based Deep Learning Model |
| 2021 | [2106.12985v2](https://arxiv.org/abs/2106.12985v2) | Stock Market Analysis with Text Data: A Review |
| 2021 | [2103.14081v1](https://arxiv.org/abs/2103.14081v1) | Stock price forecast with deep learning |
| 2021 | [2104.03053v1](https://arxiv.org/abs/2104.03053v1) | The value of big data for analyzing growth dynamics of technology based new ventures |
| 2021 | [2105.10866v1](https://arxiv.org/abs/2105.10866v1) | Towards Artificial Intelligence Enabled Financial Crime Detection |
| 2021 | [2112.02365v2](https://arxiv.org/abs/2112.02365v2) | TransBoost: A Boosting-Tree Kernel Transfer Learning Algorithm for Improving Financial Inclusion |
| 2021 | [2107.01273v2](https://arxiv.org/abs/2107.01273v2) | Visual Time Series Forecasting: An Image-driven Approach |
| 2021 | [2102.04861v1](https://arxiv.org/abs/2102.04861v1) | Wavelet Denoised-ResNet CNN and LightGBM Method to Predict Forex Rate of Change |
| 2021 | [2109.01214v1](https://arxiv.org/abs/2109.01214v1) | What drives bitcoin? An approach from continuous local transfer entropy and deep learning classification models |
| 2020 | [2008.09667v1](https://arxiv.org/abs/2008.09667v1) | A Blockchain Transaction Graph based Machine Learning Method for Bitcoin Price Prediction |
| 2020 | [2004.11697v2](https://arxiv.org/abs/2004.11697v2) | A Time Series Analysis-Based Stock Price Prediction Using Machine Learning and Deep Learning Models |
| 2020 | [2009.12129v1](https://arxiv.org/abs/2009.12129v1) | A first econometric analysis of the CRIX family |
| 2020 | [2001.03333v1](https://arxiv.org/abs/2001.03333v1) | A new approach for trading based on Long Short Term Memory technique |
| 2020 | [2002.09565v4](https://arxiv.org/abs/2002.09565v4) | Adversarial Attacks on Machine Learning Systems for High-Frequency Trading |
| 2020 | [2003.01859v1](https://arxiv.org/abs/2003.01859v1) | Applications of deep learning in stock market prediction: recent progress |
| 2020 | [2007.13566v2](https://arxiv.org/abs/2007.13566v2) | Are low frequency macroeconomic variables important for high frequency electricity prices? |
| 2020 | [2005.13005v2](https://arxiv.org/abs/2005.13005v2) | Daily Middle-Term Probabilistic Forecasting of Power Consumption in North-East England |
| 2020 | [2004.01498v1](https://arxiv.org/abs/2004.01498v1) | Deep Probabilistic Modelling of Price Movements for High-Frequency Trading |
| 2020 | [2004.01497v1](https://arxiv.org/abs/2004.01497v1) | Deep learning for Stock Market Prediction |
| 2020 | [2010.15111v1](https://arxiv.org/abs/2010.15111v1) | Evaluating data augmentation for financial time series classification |
| 2020 | [2004.01502v1](https://arxiv.org/abs/2004.01502v1) | Financial Market Trend Forecasting and Performance Analysis Using LSTM |
| 2020 | [2001.01127v1](https://arxiv.org/abs/2001.01127v1) | Forecasting Bitcoin closing price series using linear regression and neural networks models |
| 2020 | [2002.10247v1](https://arxiv.org/abs/2002.10247v1) | Forecasting Foreign Exchange Rate: A Multivariate Comparative Analysis between Traditional Econometric, Contemporary Machine Learning & Deep Learning Techniques |
| 2020 | [2001.08979v1](https://arxiv.org/abs/2001.08979v1) | Forecasting NIFTY 50 benchmark Index using Seasonal ARIMA time series models |
| 2020 | [2009.13595v1](https://arxiv.org/abs/2009.13595v1) | Forecasting Short-term load using Econometrics time series model with T-student Distribution |
| 2020 | [2008.08004v2](https://arxiv.org/abs/2008.08004v2) | Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark |
| 2020 | [2002.05789v1](https://arxiv.org/abs/2002.05789v1) | Gaussian process imputation of multiple financial series |
| 2020 | [2004.11485v1](https://arxiv.org/abs/2004.11485v1) | High-dimensional macroeconomic forecasting using message passing algorithms |
| 2020 | [2010.08400v1](https://arxiv.org/abs/2010.08400v1) | Hybrid Modelling Approaches for Forecasting Energy Spot Prices in EPEC market |
| 2020 | [2007.02673v1](https://arxiv.org/abs/2007.02673v1) | Impact of COVID-19 on Forecasting Stock Prices: An Integration of Stationary Wavelet Transform and Bidirectional Long Short-Term Memory |
| 2020 | [2011.01961v1](https://arxiv.org/abs/2011.01961v1) | Insights into Fairness through Trust: Multi-scale Trust Quantification for Financial Deep Learning |
| 2020 | [2005.03969v5](https://arxiv.org/abs/2005.03969v5) | Methods for forecasting the effect of exogenous risk on stock markets |
| 2020 | [2012.08517v1](https://arxiv.org/abs/2012.08517v1) | Model of cunning agents |
| 2020 | [2007.06848v1](https://arxiv.org/abs/2007.06848v1) | Modeling Financial Time Series using LSTM with Trainable Initial Hidden States |
| 2020 | [2005.04955v3](https://arxiv.org/abs/2005.04955v3) | Multi-Graph Convolutional Network for Relationship-Driven Stock Movement Prediction |
| 2020 | [2008.01670v1](https://arxiv.org/abs/2008.01670v1) | Multi-stream RNN for Merchant Transaction Prediction |
| 2020 | [2004.00201v1](https://arxiv.org/abs/2004.00201v1) | NetDP: An Industrial-Scale Distributed Network Representation Framework for Default Prediction in Ant Credit Pay |
| 2020 | [2008.08006v1](https://arxiv.org/abs/2008.08006v1) | Neural networks in day-ahead electricity price forecasting: Single vs. multiple outputs |
| 2020 | [2011.09109v1](https://arxiv.org/abs/2011.09109v1) | On Simultaneous Long-Short Stock Trading Controllers with Cross-Coupling |
| 2020 | [2002.02011v1](https://arxiv.org/abs/2002.02011v1) | Predicting Bank Loan Default with Extreme Gradient Boosting |
| 2020 | [2011.09137v2](https://arxiv.org/abs/2011.09137v2) | Principal Component Analysis and Factor Analysis for Feature Selection in Credit Rating |
| 2020 | [2005.13417v1](https://arxiv.org/abs/2005.13417v1) | Probabilistic multivariate electricity price forecasting using implicit generative ensemble post-processing |
| 2020 | [2004.01489v1](https://arxiv.org/abs/2004.01489v1) | Regression Approach for Modeling COVID-19 Spread and its Impact On Stock Market |
| 2020 | [2011.08011v2](https://arxiv.org/abs/2011.08011v2) | Robust Analysis of Stock Price Time Series Using CNN and LSTM-Based Deep Learning Models |
| 2020 | [2008.11788v1](https://arxiv.org/abs/2008.11788v1) | Share Price Prediction of Aerospace Relevant Companies with Recurrent Neural Networks based on PCA |
| 2020 | [2001.09769v1](https://arxiv.org/abs/2001.09769v1) | Stock Price Prediction Using Convolutional Neural Networks on a Multivariate Timeseries |
| 2020 | [2009.10819v1](https://arxiv.org/abs/2009.10819v1) | Stock Price Prediction Using Machine Learning and LSTM-Based Deep Learning Models |
| 2020 | [2008.11806v2](https://arxiv.org/abs/2008.11806v2) | The Time Function of Stock Price |
| 2020 | [2010.05601v1](https://arxiv.org/abs/2010.05601v1) | The loss optimisation of loan recovery decision times using forecast cash flows |
| 2020 | [2002.06878v1](https://arxiv.org/abs/2002.06878v1) | Trimming the Sail: A Second-order Learning Paradigm for Stock Prediction |
| 2020 | [2008.07836v2](https://arxiv.org/abs/2008.07836v2) | Unveiling the directional network behind the financial statements data using volatility constraint correlation |
| 2020 | [2008.07907v2](https://arxiv.org/abs/2008.07907v2) | Volatility Depends on Market Trades and Macro Theory |
| 2019 | [1910.13969v1](https://arxiv.org/abs/1910.13969v1) | A Classifiers Voting Model for Exit Prediction of Privately Held Companies |
| 2019 | [1901.09143v1](https://arxiv.org/abs/1901.09143v1) | A Study on Neural Network Architecture Applied to the Prediction of Brazilian Stock Returns |
| 2019 | [1909.12063v1](https://arxiv.org/abs/1909.12063v1) | Artificial Intelligence BlockCloud (AIBC) Technical Whitepaper |
| 2019 | [1904.05315v1](https://arxiv.org/abs/1904.05315v1) | Bitcoin Price Prediction: An ARIMA Approach |
| 2019 | [1905.07581v1](https://arxiv.org/abs/1905.07581v1) | Convolutional Feature Extraction and Neural Arithmetic Logic Units for Stock Prediction |
| 2019 | [1908.08036v2](https://arxiv.org/abs/1908.08036v2) | Deep Reinforcement Learning for Foreign Exchange Trading |
| 2019 | [1901.09729v4](https://arxiv.org/abs/1901.09729v4) | Estimation and simulation of the transaction arrival process in intraday electricity markets |
| 2019 | [1912.11216v6](https://arxiv.org/abs/1912.11216v6) | Evolutionary Dynamics of Investors Expectations and Market Price Movement |
| 2019 | [1902.10877v1](https://arxiv.org/abs/1902.10877v1) | Financial series prediction using Attention LSTM |
| 2019 | [1904.11145v1](https://arxiv.org/abs/1904.11145v1) | Forecasting in Big Data Environments: an Adaptable and Automated Shrinkage Estimation of Neural Networks (AAShNet) |
| 2019 | [1904.00749v1](https://arxiv.org/abs/1904.00749v1) | Forecasting the Volatilities of Philippine Stock Exchange Composite Index Using the Generalized Autoregressive Conditional Heteroskedasticity Modeling |
| 2019 | [1902.10948v1](https://arxiv.org/abs/1902.10948v1) | Global Stock Market Prediction Based on Stock Chart Images Using Deep Q-Network |
| 2019 | [1909.09563v1](https://arxiv.org/abs/1909.09563v1) | Gradient Boost with Convolution Neural Network for Stock Forecast |
| 2019 | [1908.07999v3](https://arxiv.org/abs/1908.07999v3) | HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction |
| 2019 | [1902.03125v2](https://arxiv.org/abs/1902.03125v2) | High-performance stock index trading: making effective use of a deep LSTM neural network |
| 2019 | [1904.09214v1](https://arxiv.org/abs/1904.09214v1) | Inefficiency of the Brazilian Stock Market: the IBOVESPA Future Contracts |
| 2019 | [1907.11984v1](https://arxiv.org/abs/1907.11984v1) | Investigating the effect of competitiveness power in estimating the average weighted price in electricity market |
| 2019 | [1906.06248v3](https://arxiv.org/abs/1906.06248v3) | Machine Learning on EPEX Order Books: Insights and Forecasts |
| 2019 | [1906.10121v3](https://arxiv.org/abs/1906.10121v3) | Metaheuristics optimized feedforward neural networks for efficient stock price prediction |
| 2019 | [1905.08444v1](https://arxiv.org/abs/1905.08444v1) | Predicting and Forecasting the Price of Constituents and Index of Cryptocurrency Using Machine Learning |
| 2019 | [1912.04015v2](https://arxiv.org/abs/1912.04015v2) | Sanction or Financial Crisis? An Artificial Neural Network-Based Approach to model the impact of oil price volatility on Stock and industry indices |
| 2019 | [1911.02449v2](https://arxiv.org/abs/1911.02449v2) | Scaling in Income Inequalities and its Dynamical Origin |
| 2019 | [1907.07514v1](https://arxiv.org/abs/1907.07514v1) | Self Organizing Supply Chains for Micro-Prediction: Present and Future uses of the ROAR Protocol |
| 2019 | [1908.11212v1](https://arxiv.org/abs/1908.11212v1) | Stock Price Forecasting and Hypothesis Testing Using Neural Networks |
| 2019 | [1903.05322v1](https://arxiv.org/abs/1903.05322v1) | Stylized facts of the Indian Stock Market |
| 2019 | [1903.12258v1](https://arxiv.org/abs/1903.12258v1) | Using Deep Learning Neural Networks and Candlestick Chart Representation to Predict Stock Market |
| 2019 | [1902.08938v1](https://arxiv.org/abs/1902.08938v1) | Working Paper: Improved Stock Price Forecasting Algorithm based on Feature-weighed Support Vector Regression by using Grey Correlation Degree |
| 2018 | [1803.04591v1](https://arxiv.org/abs/1803.04591v1) | A Generalization of the Robust Positive Expectation Theorem for Stock Trading via Feedback Control |
| 2018 | [1804.00825v1](https://arxiv.org/abs/1804.00825v1) | A Probabilistic Analysis of Autocallable Optimization Securities |
| 2018 | [1801.00681v1](https://arxiv.org/abs/1801.00681v1) | A novel improved fuzzy support vector machine based stock price trend forecast model |
| 2018 | [1802.05326v1](https://arxiv.org/abs/1802.05326v1) | Analysis of Financial Credit Risk Using Machine Learning |
| 2018 | [1805.06649v1](https://arxiv.org/abs/1805.06649v1) | Day-ahead electricity price forecasting with high-dimensional structures: Univariate vs. multivariate modeling frameworks |
| 2018 | [1805.12111v4](https://arxiv.org/abs/1805.12111v4) | Dynamic Advisor-Based Ensemble (dynABE): Case study in stock trend prediction of critical metal companies |
| 2018 | [1812.09081v2](https://arxiv.org/abs/1812.09081v2) | Econometric modelling and forecasting of intraday electricity prices |
| 2018 | [1812.11226v2](https://arxiv.org/abs/1812.11226v2) | Fast Training Algorithms for Deep Convolutional Fuzzy Systems with Application to Stock Index Prediction |
| 2018 | [1803.06386v1](https://arxiv.org/abs/1803.06386v1) | Forecasting Economics and Financial Time Series: ARIMA vs. LSTM |
| 2018 | [1807.00939v3](https://arxiv.org/abs/1807.00939v3) | Mining Illegal Insider Trading of Stocks: A Proactive Approach |
| 2018 | [1805.11317v1](https://arxiv.org/abs/1805.11317v1) | Neural networks for stock price prediction |
| 2018 | [1807.07328v1](https://arxiv.org/abs/1807.07328v1) | Quantifying Volatility Reduction in German Day-ahead Spot Market in the Period 2006 through 2016 |
| 2018 | [1804.00820v1](https://arxiv.org/abs/1804.00820v1) | Return Optimization Securities and Other Remarkable Structured Investment Products: Indicators of Future Outcomes for U.S. Treasuries? |
| 2018 | [1801.10583v1](https://arxiv.org/abs/1801.10583v1) | Short- to Mid-term Day-Ahead Electricity Price Forecasting Using Futures |
| 2018 | [1801.07960v1](https://arxiv.org/abs/1801.07960v1) | Stock returns forecast: an examination by means of Artificial Neural Networks |
| 2018 | [1811.08604v1](https://arxiv.org/abs/1811.08604v1) | The value of forecasts: Quantifying the economic gains of accurate quarter-hourly electricity price forecasts |
| 2018 | [1812.02433v1](https://arxiv.org/abs/1812.02433v1) | Using published bid/ask curves to error dress spot electricity price forecasts |
| 2017 | [1709.10277v1](https://arxiv.org/abs/1709.10277v1) | A Structural Model for Fluctuations in Financial Markets |
| 2017 | [1705.01144v1](https://arxiv.org/abs/1705.01144v1) | A Time Series Analysis-Based Forecasting Framework for the Indian Healthcare Sector |
| 2017 | [1801.00185v1](https://arxiv.org/abs/1801.00185v1) | A dynamic network model with persistent links and node-specific latent variables, with an application to the interbank market |
| 2017 | [1706.07821v1](https://arxiv.org/abs/1706.07821v1) | An Investigation of the Structural Characteristics of the Indian IT Sector and the Capital Goods Sector: An Application of the R Programming in Time Series Decomposition and Forecasting |
| 2017 | [1707.00757v1](https://arxiv.org/abs/1707.00757v1) | Checking account activity and credit default risk of enterprises: An application of statistical learning methods |
| 2017 | [1703.08282v1](https://arxiv.org/abs/1703.08282v1) | Cohort effects in mortality modelling: a Bayesian state-space approach |
| 2017 | [1704.00985v6](https://arxiv.org/abs/1704.00985v6) | Discretion versus Policy Rules in Futures Markets: A Case of the Osaka-Dojima Rice Exchange, 1914-1939 |
| 2017 | [1706.00948v5](https://arxiv.org/abs/1706.00948v5) | Financial Series Prediction: Comparison Between Precision of Time Series Models and Machine Learning Methods |
| 2017 | [1711.04174v1](https://arxiv.org/abs/1711.04174v1) | Financial Time Series Prediction Using Deep Learning |
| 2017 | [1708.07061v3](https://arxiv.org/abs/1708.07061v3) | Forecasting day-ahead electricity prices in Europe: the importance of considering market integration |
| 2017 | [1706.07466v1](https://arxiv.org/abs/1706.07466v1) | Identification of Credit Risk Based on Cluster Analysis of Account Behaviours |
| 2017 | [1705.01142v1](https://arxiv.org/abs/1705.01142v1) | Machine Learning for Better Models for Predicting Bond Prices |
| 2017 | [1707.03746v3](https://arxiv.org/abs/1707.03746v3) | Modeling the price of Bitcoin with geometric fractional Brownian motion: a Monte Carlo approach |
| 2017 | [1801.05752v2](https://arxiv.org/abs/1801.05752v2) | Part 1: Training Sets & ASG Transforms |
| 2017 | [1702.06055v2](https://arxiv.org/abs/1702.06055v2) | Performance of information criteria used for model selection of Hawkes process models of financial data |
| 2017 | [1703.10806v2](https://arxiv.org/abs/1703.10806v2) | Probabilistic Mid- and Long-Term Electricity Price Forecasting |
| 2017 | [1704.05499v1](https://arxiv.org/abs/1704.05499v1) | Quantifying instabilities in Financial Markets |
| 2017 | [1708.02625v1](https://arxiv.org/abs/1708.02625v1) | Risk Constrained Trading Strategies for Stochastic Generation with a Single-Price Balancing Market |
| 2017 | [1710.05513v1](https://arxiv.org/abs/1710.05513v1) | Robust Maximum Likelihood Estimation of Sparse Vector Error Correction Model |
| 2017 | [1707.07618v3](https://arxiv.org/abs/1707.07618v3) | Statistical properties and multifractality of Bitcoin |
| 2016 | [1607.05660v1](https://arxiv.org/abs/1607.05660v1) | A Comparison of Nineteen Various Electricity Consumption Forecasting Approaches and Practicing to Five Different Households in Turkey |
| 2016 | [1610.08415v1](https://arxiv.org/abs/1610.08415v1) | A Comparison of Various Electricity Tariff Price Forecasting Techniques in Turkey and Identifying the Impact of Time Series Periods |
| 2016 | [1601.05012v6](https://arxiv.org/abs/1601.05012v6) | A Simple Measure of Economic Complexity |
| 2016 | [1605.09484v1](https://arxiv.org/abs/1605.09484v1) | A unified approach to mortality modelling using state-space framework: characterisation, identification, estimation and forecasting |
| 2016 | [1604.08677v1](https://arxiv.org/abs/1604.08677v1) | An Explicit Formula for Likelihood Function for Gaussian Vector Autoregressive Moving-Average Model Conditioned on Initial Observables with Application to Model Calibration |
| 2016 | [1611.02556v1](https://arxiv.org/abs/1611.02556v1) | Application of the Generalized Linear Models in Actuarial Framework |
| 2016 | [1607.02093v1](https://arxiv.org/abs/1607.02093v1) | Artificial Neural Network and Time Series Modeling Based Approach to Forecasting the Exchange Rate in a Multivariate Framework |
| 2016 | [1602.07599v4](https://arxiv.org/abs/1602.07599v4) | Backtesting Lambda Value at Risk |
| 2016 | [1601.02407v1](https://arxiv.org/abs/1601.02407v1) | Decomposition of Time Series Data of Stock Markets and its Implications for Prediction: An Application for the Indian Auto Sector |
| 2016 | [1611.04941v4](https://arxiv.org/abs/1611.04941v4) | Empirical analysis of daily cash flow time series and its implications for forecasting |
| 2016 | [1612.02666v1](https://arxiv.org/abs/1612.02666v1) | Evaluating the Performance of ANN Prediction System at Shanghai Stock Market in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2016 | [1605.04945v1](https://arxiv.org/abs/1605.04945v1) | Extended nonlinear feedback model for describing episodes of high inflation |
| 2016 | [1610.02863v1](https://arxiv.org/abs/1610.02863v1) | Feasible Invertibility Conditions for Maximum Likelihood Estimation for Observation-Driven Models |
| 2016 | [1608.01103v1](https://arxiv.org/abs/1608.01103v1) | Fluctuation of USA Gold Price - Revisited with Chaos-based Complex Network Method |
| 2016 | [1605.08025v1](https://arxiv.org/abs/1605.08025v1) | Foreign exchange risk premia: from traditional to state-space analyses |
| 2016 | [1609.02354v1](https://arxiv.org/abs/1609.02354v1) | Generalized Autoregressive Score Models in R: The GAS Package |
| 2016 | [1612.09189v1](https://arxiv.org/abs/1612.09189v1) | Global economic dynamics of the forthcoming years. A forecast |
| 2016 | [1610.00259v1](https://arxiv.org/abs/1610.00259v1) | Hysteresis and Duration Dependence of Financial Crises in the US: Evidence from 1871-2016 |
| 2016 | [1607.05608v1](https://arxiv.org/abs/1607.05608v1) | Identification of market trends with string and D2-brane maps |
| 2016 | [1603.01397v1](https://arxiv.org/abs/1603.01397v1) | Latent class analyisis for reliable measure of inflation expectation in the indian public |
| 2016 | [1610.09812v1](https://arxiv.org/abs/1610.09812v1) | Long-range Correlation and Market Segmentation in Bond Market |
| 2016 | [1601.07707v1](https://arxiv.org/abs/1601.07707v1) | Micro-foundation using percolation theory of the finite-time singular behavior of the crash hazard rate in a class of rational expectation bubbles |
| 2016 | [1602.01960v1](https://arxiv.org/abs/1602.01960v1) | Multiple Wavelet Coherency Analysis and Forecasting of Metal Prices |
| 2016 | [1601.04341v1](https://arxiv.org/abs/1601.04341v1) | Negative oil price bubble is likely to burst in March - May 2016. A forecast on the basis of the law of log-periodical dynamics |
| 2016 | [1609.05394v1](https://arxiv.org/abs/1609.05394v1) | Predicting Future Shanghai Stock Market Price using ANN in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2016 | [1612.04370v1](https://arxiv.org/abs/1612.04370v1) | S&P500 Forecasting and Trading using Convolution Analysis of Major Asset Classes |
| 2016 | [1612.09344v1](https://arxiv.org/abs/1612.09344v1) | The Random Walk behind Volatility Clustering |
| 2016 | [1610.07287v1](https://arxiv.org/abs/1610.07287v1) | The asset price bubbles in emerging financial markets: a new statistical approach |
| 2016 | [1606.06003v1](https://arxiv.org/abs/1606.06003v1) | Using String Invariants for Prediction Searching for Optimal Parameters |
| 2016 | [1611.06010v1](https://arxiv.org/abs/1611.06010v1) | Value-at-Risk Prediction in R with the GAS Package |
| 2016 | [1606.01218v1](https://arxiv.org/abs/1606.01218v1) | World Financial 2014-2016 Market Bubbles: Oil Negative - US Dollar Positive |
| 2015 | [1509.01215v1](https://arxiv.org/abs/1509.01215v1) | Assessing Consistency of Consumer Confidence Data using Dynamic Latent Class Analysis |
| 2015 | [1506.01984v1](https://arxiv.org/abs/1506.01984v1) | Autoregressive approaches to import--export time series II: a concrete case study |
| 2015 | [1506.02940v1](https://arxiv.org/abs/1506.02940v1) | Autoregressive approaches to import-export time series I: basic techniques |
| 2015 | [1508.04754v2](https://arxiv.org/abs/1508.04754v2) | Currency target zone modeling: An interplay between physics and economics |
| 2015 | [1508.07534v1](https://arxiv.org/abs/1508.07534v1) | Forecasting Exchange Rates Using Time Series Analysis: The sample of the currency of Kazakhstan |
| 2015 | [1501.00818v2](https://arxiv.org/abs/1501.00818v2) | Forecasting day ahead electricity spot prices: The impact of the EXAA to other European electricity markets |
| 2015 | [1507.06219v1](https://arxiv.org/abs/1507.06219v1) | Multi-scaling of wholesale electricity prices |
| 2015 | [1505.08117v1](https://arxiv.org/abs/1505.08117v1) | Predictability of price movements in deregulated electricity markets |
| 2015 | [1501.04682v3](https://arxiv.org/abs/1501.04682v3) | Toward robust early-warning models: A horse race, ensembles and model uncertainty |
| 2015 | [1511.00483v1](https://arxiv.org/abs/1511.00483v1) | With string model to time series forecasting |
| 2014 | [1502.06434v1](https://arxiv.org/abs/1502.06434v1) | ANN Model to Predict Stock Prices at Stock Exchange Markets |
| 2014 | [1403.8018v2](https://arxiv.org/abs/1403.8018v2) | Are credit ratings time-homogeneous and Markov? |
| 2014 | [1406.6862v1](https://arxiv.org/abs/1406.6862v1) | Coping with area price risk in electricity markets: Forecasting Contracts for Difference in the Nordic power market |
| 2014 | [1404.3219v1](https://arxiv.org/abs/1404.3219v1) | Estimating nonlinear regression errors without doing regression |
| 2014 | [1401.7496v1](https://arxiv.org/abs/1401.7496v1) | Microeconomic Structure determines Macroeconomic Dynamics. Aoki defeats the Representative Agent |
| 2014 | [1406.7526v1](https://arxiv.org/abs/1406.7526v1) | Predictability of Volatility Homogenised Financial Time Series |
| 2014 | [1404.7642v1](https://arxiv.org/abs/1404.7642v1) | Predictive regressions for macroeconomic data |
| 2014 | [1409.4894v1](https://arxiv.org/abs/1409.4894v1) | The Credibility Theory applied to backtesting Counterparty Credit Risk |
| 2014 | [1411.3399v1](https://arxiv.org/abs/1411.3399v1) | Trend and Fractality Assessment of Mexico's Stock Exchange |
| 2014 | [1411.1689v1](https://arxiv.org/abs/1411.1689v1) | Universality of Tsallis q-exponential of interoccurrence times within the microscopic model of cunning agents |
| 2013 | [1305.2655v1](https://arxiv.org/abs/1305.2655v1) | An Exactly Solvable Discrete Stochastic Process with Correlated Properties |
| 2013 | [1308.1749v1](https://arxiv.org/abs/1308.1749v1) | Fractality of profit landscapes and validation of time series models for stock prices |
| 2013 | [1307.8308v1](https://arxiv.org/abs/1307.8308v1) | Is it possible to predict long-term success with k-NN? Case Study of four market indices (FTSE100, DAX, HANGSENG, NASDAQ) |
| 2013 | [1301.2076v1](https://arxiv.org/abs/1301.2076v1) | Modeling of income distribution in the European Union with the Fokker-Planck equation |
| 2013 | [1307.2048v1](https://arxiv.org/abs/1307.2048v1) | Modeling record-breaking stock prices |
| 2013 | [1306.3110v1](https://arxiv.org/abs/1306.3110v1) | Some applications of first-passage ideas to finance |
| 2013 | [1309.7119v3](https://arxiv.org/abs/1309.7119v3) | Stock price direction prediction by directly using prices data: an empirical study on the KOSPI and HSI |
| 2012 | [1204.6483v1](https://arxiv.org/abs/1204.6483v1) | Applications of statistical mechanics to economics: Entropic origin of the probability distributions of money, income, and energy consumption |
| 2012 | [1201.1604v1](https://arxiv.org/abs/1201.1604v1) | Deriving consensus rankings via multicriteria decision making methodology |
| 2012 | [1207.4069v1](https://arxiv.org/abs/1207.4069v1) | Global Inflation Dynamics: regularities & forecasts |
| 2012 | [1206.6972v2](https://arxiv.org/abs/1206.6972v2) | Record statistics and persistence for a random walk with a drift |
| 2012 | [1203.1313v2](https://arxiv.org/abs/1203.1313v2) | UPDATE February 2012 - The Food Crises: Predictive validation of a quantitative model of food prices including speculators and ethanol conversion |
| 2012 | [1209.6376v1](https://arxiv.org/abs/1209.6376v1) | UPDATE July 2012 / The Food Crises: The US Drought |
| 2011 | [1110.5429v1](https://arxiv.org/abs/1110.5429v1) | Causal modeling and inference for electricity markets |
| 2011 | [1104.4716v1](https://arxiv.org/abs/1104.4716v1) | From the currency rate quotations onto strings and brane world scenarios |
| 2011 | [1110.2603v1](https://arxiv.org/abs/1110.2603v1) | Multi-agent based analysis of financial data |
| 2011 | [1102.2620v1](https://arxiv.org/abs/1102.2620v1) | Predicting economic market crises using measures of collective panic |
| 2011 | [1103.5659v1](https://arxiv.org/abs/1103.5659v1) | U.S. Core Inflation: A Wavelet Analysis |
| 2010 | [1003.1802v1](https://arxiv.org/abs/1003.1802v1) | A simple model of mortality trends aiming at universality: Lee Carter + Cohort |
| 2010 | [1009.4142v1](https://arxiv.org/abs/1009.4142v1) | About the Justification of Experience Rating: Bonus Malus System and a new Poisson Mixture Model |
| 2010 | [1001.3176v1](https://arxiv.org/abs/1001.3176v1) | Analyzing the prices of the most expensive sheet iron all over the world: Modeling, prediction and regime change |
| 2010 | [1005.0051v1](https://arxiv.org/abs/1005.0051v1) | Crude oil and motor fuel: Fair price revisited |
| 2010 | [1007.5413v1](https://arxiv.org/abs/1007.5413v1) | Optimization of Financial Instrument Parcels in Stochastic Wavelet Model |
| 2010 | [1006.2010v1](https://arxiv.org/abs/1006.2010v1) | Prediction accuracy and sloppiness of log-periodic functions |
| 2010 | [1004.0213v1](https://arxiv.org/abs/1004.0213v1) | S&P 500 returns revisited |
| 2010 | [1002.0917v1](https://arxiv.org/abs/1002.0917v1) | Statistical properties of agent-based models in markets with continuous double auction mechanism |
| 2010 | [1101.0184v1](https://arxiv.org/abs/1101.0184v1) | Testing the Capital Asset Pricing Model (CAPM) on the Uganda Stock Exchange |
| 2010 | [1005.5675v2](https://arxiv.org/abs/1005.5675v2) | The Financial Bubble Experiment: Advanced Diagnostics and Forecasts of Bubble Terminations Volume II-Master Document |
| 2010 | [1011.2882v2](https://arxiv.org/abs/1011.2882v2) | The Financial Bubble Experiment: Advanced Diagnostics and Forecasts of Bubble Terminations, Volume III |
| 2010 | [1011.5187v1](https://arxiv.org/abs/1011.5187v1) | Transition from Exponential to Power Law Distributions in a Chaotic Market |
| 2010 | [1005.1760v2](https://arxiv.org/abs/1005.1760v2) | Two stock options at the races: Black-Scholes forecasts |
| 2010 | [1001.1916v1](https://arxiv.org/abs/1001.1916v1) | Utilisation des méthodes de Lee-Carter et Log-Poisson pour l'ajustement de tables de mortalité dans le cas de petits échantillons |
| 2009 | [0902.1576v3](https://arxiv.org/abs/0902.1576v3) | A Paradigm Shift from Production Function to Production Copula: Statistical Description of Production Activity of Firms |
| 2009 | [0903.0282v1](https://arxiv.org/abs/0903.0282v1) | A dynamic nonlinear model for saturation in industrial growth |
| 2009 | [0901.1945v1](https://arxiv.org/abs/0901.1945v1) | A mathematical proof of the existence of trends in financial time series |
| 2009 | [0909.1007v2](https://arxiv.org/abs/0909.1007v2) | Bubble Diagnosis and Prediction of the 2005-2007 and 2008-2009 Chinese stock market bubbles |
| 2009 | [0903.0203v1](https://arxiv.org/abs/0903.0203v1) | Mechanical Model of Personal Income Distribution |
| 2009 | [0907.1827v1](https://arxiv.org/abs/0907.1827v1) | The Chinese Equity Bubble: Ready to Burst |
| 2009 | [0911.0454v4](https://arxiv.org/abs/0911.0454v4) | The Financial Bubble Experiment: advanced diagnostics and forecasts of bubble terminations |
| 2009 | [0904.1404v2](https://arxiv.org/abs/0904.1404v2) | The Size Variance Relationship of Business Firm Growth Rates |
| 2009 | [0903.5064v1](https://arxiv.org/abs/0903.5064v1) | Unemployment and inflation in Western Europe: solution by the boundary element method |
| 2009 | [0909.0418v3](https://arxiv.org/abs/0909.0418v3) | World stock market: more sizeable trend reversal likely in February/March 2010 |
| 2008 | [0808.3360v1](https://arxiv.org/abs/0808.3360v1) | Criticality Characteristics of Current Oil Price Dynamics |
| 2008 | [0802.4043v2](https://arxiv.org/abs/0802.4043v2) | Current log-periodic view on future world market development |
| 2008 | [0808.3269v1](https://arxiv.org/abs/0808.3269v1) | Dynamic scaling approach to study time series fluctuations |
| 2008 | [0811.0376v1](https://arxiv.org/abs/0811.0376v1) | Exact prediction of S&P 500 returns |
| 2008 | [0806.2989v2](https://arxiv.org/abs/0806.2989v2) | How to grow a bubble: A model of myopic adapting agents |
| 2008 | [0806.2397v1](https://arxiv.org/abs/0806.2397v1) | Measuring Value in Healthcare |
| 2008 | [0808.0372v1](https://arxiv.org/abs/0808.0372v1) | The distribution of first-passage times and durations in FOREX and future markets |
| 2008 | [0804.4191v3](https://arxiv.org/abs/0804.4191v3) | Theory of market fluctuations |
| 2008 | [0805.3213v1](https://arxiv.org/abs/0805.3213v1) | Using self-similarity and renormalization group to analyze time series |
| 2008 | [0807.3800v3](https://arxiv.org/abs/0807.3800v3) | What drives mutual fund asset concentration? |
| 2007 | [physics/0701171v2](https://arxiv.org/abs/physics/0701171v2) | A case study of speculative financial bubbles in the South African stock market 2003-2006 |
| 2007 | [0704.0589v1](https://arxiv.org/abs/0704.0589v1) | Analysis of the real estate market in Las Vegas: Bubble, seasonal patterns, and prediction of the CSW indexes |
| 2007 | [math/0702814v1](https://arxiv.org/abs/math/0702814v1) | Combining domain knowledge and statistical models in time series analysis |
| 2007 | [0704.1738v1](https://arxiv.org/abs/0704.1738v1) | Financial time-series analysis: A brief overview |
| 2006 | [physics/0611281v2](https://arxiv.org/abs/physics/0611281v2) | Forecasting extreme events in collective dynamics: an analytic signal approach to detecting discrete scale invariance |
| 2006 | [math/0605421v1](https://arxiv.org/abs/math/0605421v1) | Imbalance attractors for a strategic model of market microstructure |
| 2006 | [physics/0605179v1](https://arxiv.org/abs/physics/0605179v1) | Microeconomic co-evolution model for financial technical analysis signals |
| 2006 | [physics/0606040v3](https://arxiv.org/abs/physics/0606040v3) | Queueing theoretical analysis of foreign currency exchange rates |
| 2006 | [physics/0602055v1](https://arxiv.org/abs/physics/0602055v1) | Stock mechanics: theory of conservation of total energy and predictions of coming short-term fluctuations of Dow Jones Industrials Average (DJIA) |
| 2006 | [math/0611186v1](https://arxiv.org/abs/math/0611186v1) | The distribution of a linear predictor after model selection: Unconditional finite-sample distributions and asymptotic approximations |
| 2006 | [physics/0610047v3](https://arxiv.org/abs/physics/0610047v3) | Volatility and dividend risk in perpetual American options |
| 2005 | [math/0512181v1](https://arxiv.org/abs/math/0512181v1) | Accompanying document to "Point Estimation with Exponentially Tilted Empirical Likelihood" |
| 2005 | [nlin/0507037v1](https://arxiv.org/abs/nlin/0507037v1) | Forecasting non-stationary financial time series through genetic algorithm |
| 2005 | [physics/0505079v1](https://arxiv.org/abs/physics/0505079v1) | Fundamental Factors versus Herding in the 2000-2005 US Stock Market and Prediction |
| 2005 | [cond-mat/0503607v2](https://arxiv.org/abs/cond-mat/0503607v2) | Importance of Positive Feedbacks and Over-confidence in a Self-Fulfilling Ising Model of Financial Markets |
| 2005 | [physics/0503006v1](https://arxiv.org/abs/physics/0503006v1) | Prediction oriented variant of financial log-periodicity and speculating about the stock market development until 2010 |
| 2005 | [physics/0503163v1](https://arxiv.org/abs/physics/0503163v1) | Stock Mechanics: a classical approach |
| 2005 | [physics/0506098v1](https://arxiv.org/abs/physics/0506098v1) | Stock mechanics: predicting recession in S&P500, DJIA, and NASDAQ |
| 2005 | [physics/0504100v1](https://arxiv.org/abs/physics/0504100v1) | Time and foreign exchange markets |
| 2004 | [cond-mat/0406225v2](https://arxiv.org/abs/cond-mat/0406225v2) | Properties of low variability periods in financial time series |
| 2004 | [cond-mat/0406704v1](https://arxiv.org/abs/cond-mat/0406704v1) | Stock markets are not what we think they are: the key roles of cross-ownership and corporate treasury stock |
| 2003 | [cond-mat/0307323v3](https://arxiv.org/abs/cond-mat/0307323v3) | Another type of log-periodic oscillations on Polish stock market? |
| 2003 | [cond-mat/0312149v1](https://arxiv.org/abs/cond-mat/0312149v1) | Antibubble and Prediction of China's stock market and Real-Estate |
| 2003 | [cond-mat/0301543v1](https://arxiv.org/abs/cond-mat/0301543v1) | Critical Market Crashes |
| 2003 | [cond-mat/0311089v1](https://arxiv.org/abs/cond-mat/0311089v1) | Fearless versus Fearful Speculative Financial Bubbles |
| 2003 | [physics/0301007v1](https://arxiv.org/abs/physics/0301007v1) | Finite-Time Singularity Signature of Hyperinflation |
| 2003 | [cond-mat/0304601v3](https://arxiv.org/abs/cond-mat/0304601v3) | Predictability of large future changes in major financial indices |
| 2003 | [cond-mat/0310092v2](https://arxiv.org/abs/cond-mat/0310092v2) | Testing the Stability of the 2000-2003 US Stock Market "Antibubble" |
| 2003 | [cond-mat/0305004v1](https://arxiv.org/abs/cond-mat/0305004v1) | The US 2000-2003 Market Descent: Clarifications |
| 2003 | [cond-mat/0304469v1](https://arxiv.org/abs/cond-mat/0304469v1) | Using Recurrent Neural Networks To Forecasting of Forex |
| 2002 | [cond-mat/0209591v2](https://arxiv.org/abs/cond-mat/0209591v2) | Log-periodic self-similarity: an emerging financial law? |
| 2002 | [cond-mat/0204295v1](https://arxiv.org/abs/cond-mat/0204295v1) | Predicting critical crashes? A new restriction for the free variables |
| 2002 | [cond-mat/0209065v1](https://arxiv.org/abs/cond-mat/0209065v1) | The US 2000-2002 Market Descent: How Much Longer and Deeper? |
| 2001 | [physics/0112045v1](https://arxiv.org/abs/physics/0112045v1) | Dynamics of market indices, Markov chains, and random walking problem |
| 2001 | [cond-mat/0110124v2](https://arxiv.org/abs/cond-mat/0110124v2) | Nucleation of Market Shocks in Sornette-Ide model |
| 2001 | [cond-mat/0102423v2](https://arxiv.org/abs/cond-mat/0102423v2) | Power Laws of Wealth, Market Order Volumes and Market Returns |
| 2001 | [cond-mat/0106520v1](https://arxiv.org/abs/cond-mat/0106520v1) | Significance of log-periodic precursors to financial crashes |
| 2000 | [cond-mat/0004179v1](https://arxiv.org/abs/cond-mat/0004179v1) | A Stochastic Cascade Model for FX Dynamics |
| 2000 | [cond-mat/0009401v1](https://arxiv.org/abs/cond-mat/0009401v1) | Empirical properties of the variety of a financial portfolio and the single-index model |
| 2000 | [cond-mat/0011088v1](https://arxiv.org/abs/cond-mat/0011088v1) | Fokker-Planck equation of distributions of financial returns and power laws |
| 2000 | [cond-mat/0001120v1](https://arxiv.org/abs/cond-mat/0001120v1) | Fractional calculus and continuous-time finance |
| 2000 | [cond-mat/0001324v1](https://arxiv.org/abs/cond-mat/0001324v1) | Increments of Uncorrelated Time Series Can Be Predicted With a Universal 75% Probability of Success |
| 2000 | [cond-mat/0004001v1](https://arxiv.org/abs/cond-mat/0004001v1) | Stock Market Speculation: Spontaneous Symmetry Breaking of Economic Valuation |
| 2000 | [cond-mat/0006065v1](https://arxiv.org/abs/cond-mat/0006065v1) | Variety and Volatility in Financial Markets |
| 1999 | [cond-mat/9901268v1](https://arxiv.org/abs/cond-mat/9901268v1) | Financial ``Anti-Bubbles'': Log-Periodicity in Gold and Nikkei collapses |
| 1999 | [cond-mat/9909439v1](https://arxiv.org/abs/cond-mat/9909439v1) | Market Fluctuations: multiplicative and percolation models, size effects and predictions |
| 1999 | [cond-mat/9910141v1](https://arxiv.org/abs/cond-mat/9910141v1) | On Rational Bubbles and Fat Tails |
| 1998 | [cond-mat/9804111v1](https://arxiv.org/abs/cond-mat/9804111v1) | Are Financial Crashes Predictable? |
| 1998 | [cond-mat/9803059v1](https://arxiv.org/abs/cond-mat/9803059v1) | Fixed Points in Self-Similar Analysis of Time Series |

