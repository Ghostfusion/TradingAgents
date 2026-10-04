# Evidence pack — Machine Learning & Deep Learning Methods (`ml-methods`)

Annotated sweep rows for this category: **800** (high 62 · med 392 · low 346).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (62)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2602.00082v1](https://arxiv.org/abs/2602.00082v1) | LLM multi-agent framework (announcement, event, momentum, market analysts plus prediction and decision agents) for Chinese public REITs; both DeepSeek-R1 and fine-tuned Qwen3-8B beat buy-and-hold on return, Sharpe and drawdown. | `tradingagents/graph/trading_graph.py` |
| 2026 | [2607.27188v1](https://arxiv.org/abs/2607.27188v1) | Compares latent risk-neutral density recovery from option quotes: a two-component lognormal mixture wins on price/L1/Wasserstein error, while DeepONet improves tail quantiles and NIFTY test-time adaptation cuts RMSE 28.3%. | strategies/rnd_recovery.py |
| 2026 | [2606.31251v1](https://arxiv.org/abs/2606.31251v1) | Walk-forward S&P 500 backtest models Adjusted Information Ratio sequences for an SVM strategy versus buy-and-hold via GAMLSS with a Zero-Adjusted Gamma response conditioned on volatility and momentum; dominance is regime-conditional. | strategies/regime_performance.py |
| 2026 | [2604.15531v1](https://arxiv.org/abs/2604.15531v1) | Falsification audit tests complete ML predictive workflows against zero-predictability and microstructure-placebo reference classes; workflows producing significant walk-forward evidence there are falsified, and a magnitude gap quantifies selection-induced inflation. | `strategies/falsification.py` |
| 2026 | [2602.00080v1](https://arxiv.org/abs/2602.00080v1) | GT-Score composite objective (performance, significance, consistency, downside risk) reduces overfitting; walk-forward on 50 S&P 500 names 2010-2024 improves generalization ratio 98% vs baselines (p<0.01). | `strategies/evaluate.py` |
| 2025 | [2508.18592v1](https://arxiv.org/abs/2508.18592v1) | Combines three ML models for CSI 300 stock selection under static and IC-based dynamic weighting; IC-mean weighting beats metric-based weighting and single models. | `strategies/signal_analysis.py` |
| 2025 | [2509.04541v2](https://arxiv.org/abs/2509.04541v2) | Introduces finance-grounded loss functions from Sharpe, PnL and max drawdown plus turnover regularization for deep trading models; they beat MSE on algorithmic-trading metrics. | `strategies/evaluate.py` |
| 2025 | [2507.15079v1](https://arxiv.org/abs/2507.15079v1) | Isotonic Quantile Regression Averaging (iQRA) adds stochastic order constraints to ensemble point forecasts, producing probabilistic electricity-price forecasts that beat conformal and state-of-the-art postprocessing on reliability, sharpness and cost, without hyperparameter tuning. | `strategies/conformal.py` |
| 2025 | [2508.15922v1](https://arxiv.org/abs/2508.15922v1) | Probabilistic crypto volatility forecasting: feeds HAR/GARCH/ARFIMA and ML point forecasts into quantile estimation via residual simulation (QRS); QRS on log realized vol of linear models wins. | `strategies/conformal.py` |
| 2025 | [2512.02037v1](https://arxiv.org/abs/2512.02037v1) | Adapts Avellaneda–Lee pairs trading to Polish equities, replicating assets via PCA, ETFs and LSTM factors; 2017-2019 PCA earns ~20% cumulative, Sharpe 2.63; only ETF approach survives 2020. | `strategies/mean_reversion.py` |
| 2025 | [2503.02680v1](https://arxiv.org/abs/2503.02680v1) | Trains one signature-enhanced transformer (GFT-Sig) globally across 80 crypto pairs for VWAP execution; the globally-fitted model beats asset-specific models on absolute and quadratic VWAP loss and generalizes to out-of-sample assets. | `strategies/execution_schedule.py` |
| 2024 | [2401.10370v1](https://arxiv.org/abs/2401.10370v1) | Comparative review of deep generative models (CGAN, CWGAN, diffusion, signature) for financial time-series generation, applied to Historical-Simulation VaR. | `strategies/book_risk.py` |
| 2024 | [2406.08041v1](https://arxiv.org/abs/2406.08041v1) | Across 1,455 stocks, HAR with a refined rolling-window fitting scheme beats tuned ML models on QLIKE/MSE/realized utility at far lower computational cost and with interpretability. | `strategies/long_memory.py` |
| 2024 | [2411.08382v1](https://arxiv.org/abs/2411.08382v1) | Hybrid VAR plus feedforward neural network predicts order-flow imbalance, feeding VAR residuals to the FNN and estimating buy/sell intensity; beats standalone FNN and VAR on Binance and synthetic data. | `strategies/orderflow.py` |
| 2023 | [2308.14235v6](https://arxiv.org/abs/2308.14235v6) | Statistical-physics model of Level 3 order book defines kinetic energy, momentum and 'active depth'; outperforms benchmarks and ML for volatility and expected returns. | `strategies/orderflow.py` |
| 2023 | [2309.02994v1](https://arxiv.org/abs/2309.02994v1) | Offline estimation of a nonparametric price-impact propagator; greedy strategies based on it are suboptimal due to spurious correlation between signal and estimator. | `strategies/execution_schedule.py` |
| 2023 | [2310.14536v1](https://arxiv.org/abs/2310.14536v1) | Co-trains a normalizing-flow RV transformation with the prediction model under a maximum-likelihood objective for skewed, fat-tailed realized volatility. | `strategies/volatility_models.py` |
| 2023 | [2308.08031v1](https://arxiv.org/abs/2308.08031v1) | Large language models learn company embeddings from SEC business descriptions, giving continuous similarity that beats discrete GICS for portfolio construction and attribution. | `strategies/peer_universe.py` |
| 2023 | [2306.12446v2](https://arxiv.org/abs/2306.12446v2) | Compares deep forecasters (MLP, RNN, TCN, Temporal Fusion Transformer) with GARCH for multivariate volatility; TFT wins in most of five assets. | `strategies/volatility_models.py` |
| 2023 | [2306.05479v1](https://arxiv.org/abs/2306.05479v1) | Convolutional-Transformer survival model maps time-varying limit-order-book features to fill-time distributions, beating survival baselines on proper scoring rules. | `strategies/backtest_models.py` |
| 2023 | [2311.14759v2](https://arxiv.org/abs/2311.14759v2) | Uses BART MNLI zero-shot classification of Twitter/Reddit sentiment for Bitcoin and Ethereum forecasting, beating dictionary-based sentiment methods. | `strategies/sentiment_research.py` |
| 2023 | [2306.02136v3](https://arxiv.org/abs/2306.02136v3) | FinBERT sentiment plus LSTM predicts stock trends and beats BERT, standalone LSTM and ARIMA; sentiment significantly improves accuracy. | `strategies/sentiment_research.py` |
| 2023 | [2311.04727v2](https://arxiv.org/abs/2311.04727v2) | LSTM trained across a pool of assets beats traditional volatility models; a rough-volatility plus Zumbach model with five non-asset-dependent parameters matches it (crypto-winter). | `strategies/volatility_models.py` |
| 2023 | [2311.06256v1](https://arxiv.org/abs/2311.06256v1) | SV-PF-RNN hybrid of neural network and particle filter estimates true stochastic volatility from noisy data, improving on a basic particle filter. | `strategies/volatility_models.py` |
| 2023 | [2306.12964v1](https://arxiv.org/abs/2306.12964v1) | RL framework mines synergistic formulaic alpha sets jointly, optimizing combined performance rather than independently generated alphas. | `strategies/alpha_zoo.py` |
| 2023 | [2311.14735v1](https://arxiv.org/abs/2311.14735v1) | Conditional importance-weighted autoencoders and conditional normalizing flows model the joint 500-dimensional distribution of S&P 500 equity returns. | `strategies/covariance_models.py` |
| 2023 | [2308.01419v1](https://arxiv.org/abs/2308.01419v1) | Customized graph neural networks forecast multivariate realized volatility with spillovers; nonlinear spillovers help up to one week, multi-hop alone does not. | `strategies/volatility_models.py` |
| 2023 | [2310.09903v5](https://arxiv.org/abs/2310.09903v5) | Tests 123 technical indicators and 10 regression models on 13 years of Apple data; a 3-day window is best and linear/ridge regression win. | `strategies/extended_indicators.py` |
| 2023 | [2306.05568v2](https://arxiv.org/abs/2306.05568v2) | MACE, a multivariate alternating conditional expectations algorithm (Random Forest + constrained ridge), builds maximally predictable portfolios and scales to large ones. | `strategies/portfolio_optimizer.py` |
| 2023 | [2310.09622v1](https://arxiv.org/abs/2310.09622v1) | Bivariate jump-diffusion model of Bitcoin price driven by Google-search sentiment; closed-form price and neural-network option valuation. | `strategies/options_math.py` |
| 2023 | [2304.09947v2](https://arxiv.org/abs/2304.09947v2) | Gradient-free online ensemble reweights 16 models by out-of-sample R-squared; applied to sector rotation, finding sector returns more predictable than stock returns. | `strategies/rotation.py` |
| 2023 | [2401.05337v1](https://arxiv.org/abs/2401.05337v1) | Unsupervised linear-signal framework maximizes Sharpe ratio of PnL from exogenous variables with regularization; applied to a U.S. Treasury bond ETF. | `strategies/signal_analysis.py` |
| 2023 | [2306.05667v1](https://arxiv.org/abs/2306.05667v1) | Combines Random-Matrix-Theory covariance cleaning with Nested Clustered Optimization (spectral clustering + MST) to curb Markowitz instability on Mexican equities. | `strategies/hierarchical_risk_parity.py` |
| 2023 | [2308.08550v1](https://arxiv.org/abs/2308.08550v1) | Extended LSTMs with per-dimension flexible timescales predict asset volatility better than rough volatility by ~20% and halve training epochs. | `strategies/volatility_models.py` |
| 2023 | [2304.11883v1](https://arxiv.org/abs/2304.11883v1) | Recurrent neural network estimates Hawkes model parameters on high-frequency data far faster than MLE with comparable accuracy, enabling real-time volatility. | `strategies/orderflow.py` |
| 2023 | [2312.14903v2](https://arxiv.org/abs/2312.14903v2) | Scalable agent-based market simulation with heterogeneous agents and a continuous double-auction engine reproduces stylized facts without fitting historical data. | `strategies/backtest_engine.py` |
| 2023 | [2304.09937v1](https://arxiv.org/abs/2304.09937v1) | ML stock predictions degrade during recessions; recession history and risk-free rate do not help, and good-recession performance reflects low volatility, not ML merit. | `strategies/regime_performance.py` |
| 2023 | [2309.16196v1](https://arxiv.org/abs/2309.16196v1) | Transformer using mixed-frequency data (macro indicators plus Baidu search indices as subjective factors) predicts stock volatility. | `strategies/volatility_models.py` |
| 2022 | [2203.12460v1](https://arxiv.org/abs/2203.12460v1) | Studies a decade of ~100k earnings-call transcripts from 6,300 firms; a semantic GNN reliably predicts price moves across five sectors, semantics beat sales/EPS, while pre-earnings analyst ratings correlate weakly. | `strategies/text_factors.py` |
| 2022 | [2209.05559v6](https://arxiv.org/abs/2209.05559v6) | Hypothesis-test approach to backtest overfitting in deep-RL crypto trading; less-overfitted agents earn higher returns than benchmark during a double market crash. | strategies/evaluate.py |
| 2022 | [2203.03179v4](https://arxiv.org/abs/2203.03179v4) | Deep neural networks identify robust statistical-arbitrage strategies under model ambiguity without cointegration pairs; empirically profitable in up to 50 dimensions, during crises and when pairs break. | `strategies/mean_reversion.py` |
| 2022 | [2207.10539v1](https://arxiv.org/abs/2207.10539v1) | LSTM value-at-risk estimator matches GARCH on simulated data but beats all estimators on real data by exception rate and mean quantile score. | strategies/book_risk.py |
| 2022 | [2212.14670v1](https://arxiv.org/abs/2212.14670v1) | Hierarchical RL Macro-Meta-Micro Trader (with LSTM volume forecast) optimizes VWAP execution and saves 1.16 bp average cost over the best baseline on Shanghai stocks. | strategies/execution_schedule.py |
| 2022 | [2202.11285v1](https://arxiv.org/abs/2202.11285v1) | Neural GARCH makes GARCH/BEKK coefficients time-varying via a recurrent network trained with stochastic gradient variational Bayes; the Student-t variant consistently outperforms across univariate and multivariate series. | `strategies/volatility_models.py` |
| 2022 | [2203.12457v1](https://arxiv.org/abs/2203.12457v1) | Engineers technical, order-flow and order-book features fed to a Tabnet network predicting short-term silver futures direction on the Shanghai Futures Exchange, reaching 0.601 accuracy. | `strategies/orderflow.py` |
| 2022 | [2203.08224v4](https://arxiv.org/abs/2203.08224v4) | Adapts Generalized Random Forests to quantile prediction for cryptocurrency VaR over 105 coins; GRF beats quantile regression, GARCH and CAViaR, especially in unstable and highly volatile periods. | `strategies/book_risk.py` |
| 2022 | [2202.08962v2](https://arxiv.org/abs/2202.08962v2) | Pools cross-stock intraday data with a market-volatility proxy to forecast realized volatility; neural networks beat linear and tree models, generalize to unseen stocks, and exploit time-of-day effects. | `strategies/long_memory.py` |
| 2021 | [2106.07177v2](https://arxiv.org/abs/2106.07177v2) | Predicts the implied volatility surface with a two-step framework: extract features (PCA, VAE, or surface sampling), forecast with LSTM, then reconstruct via arbitrage-constrained DNN; sampling/VAE outperform classical methods on S&P500 data. | `strategies/options_surface.py` |
| 2021 | [2101.10942v2](https://arxiv.org/abs/2101.10942v2) | Shows prediction-error-based evaluation of neural stock predictors is statistically flawed; the absolute-value constraint distorts reported performance. | `strategies/evaluate.py` |
| 2021 | [2107.07206v2](https://arxiv.org/abs/2107.07206v2) | Compares logistic regression and feedforward neural networks for credit scoring; temporal repeated-measure features boost accuracy, and a new Stein-unbiased-risk-estimate (SURE) calibration stacked with Platt improves predicted-probability calibration. | `strategies/calibration.py` |
| 2021 | [2103.09106v1](https://arxiv.org/abs/2103.09106v1) | Feature learning on 5 technical and 23 fundamental indicators shows analyst rating matters; 83.62% directional accuracy and 85% buy precision on S&P500. | `strategies/analyst_revisions.py` |
| 2021 | [2103.09987v1](https://arxiv.org/abs/2103.09987v1) | Statistical Arbitrage Risk Premium: elastic-net projects each stock's returns onto peers to build replicate portfolios hedging factor residual risk. | `strategies/peer_universe.py` |
| 2021 | [2103.16388v1](https://arxiv.org/abs/2103.16388v1) | FinALBERT (ALBERT) trained on 10 years of labelled Stocktwits data for financial text classification and stock price-change prediction. | `strategies/sentiment_research.py` |
| 2021 | [2103.01670v1](https://arxiv.org/abs/2103.01670v1) | LOB recreation model predicts the limit order book from TAQ history using an ODE recurrent neural network. | `strategies/orderflow.py` |
| 2020 | [2009.03094v1](https://arxiv.org/abs/2009.03094v1) | XGBoost on fundamental and technical features across many stocks captures post-earnings-announcement drift dynamics beyond simple regressions. | `strategies/catalyst.py` |
| 2020 | [2009.06910v1](https://arxiv.org/abs/2009.06910v1) | SVR-GARCH-KDE hybrid nonparametrically forecasts Value-at-Risk, overcoming parametric bias from skew and leptokurtosis. | `strategies/book_risk.py` |
| 2020 | [2010.01241v1](https://arxiv.org/abs/2010.01241v1) | Temporal CNNs predict Bitcoin spot movement from limit-order-book data at 71% walk-forward accuracy on a 2-second horizon. | `strategies/orderflow.py` |
| 2019 | [1910.01491v1](https://arxiv.org/abs/1910.01491v1) | RIC-NN: nonlinear multi-factor deep net with rank-IC stopping criterion and transfer learning across regions; beats off-the-shelf ML and major equity funds over 14 years on MSCI stocks. | strategies/signal_analysis.py |
| 2019 | [1906.09024v2](https://arxiv.org/abs/1906.09024v2) | Builds a BERT-based financial sentiment index for three Hong Kong stocks using Weibo text and combines it with option-implied and market-implied sentiment; LSTM then predicts individual stock returns nonlinearly. | `strategies/sentiment_research.py` |
| 2019 | [1904.00745v6](https://arxiv.org/abs/1904.00745v6) | Deep neural asset-pricing model uses the no-arbitrage condition as criterion and adversarial test-asset construction; outperforms benchmarks out-of-sample on Sharpe ratio, explained variation and pricing errors. | `strategies/factors.py` |
| 2019 | [1909.04497v2](https://arxiv.org/abs/1909.04497v2) | Equity2Vec graph component captures evolving cross-sectional interactions and fuses technical, news and cross-sectional signals end-to-end, outperforming SOTA approaches and monetizing signals. | strategies/cross_section.py |
| 2019 | [1907.09452v1](https://arxiv.org/abs/1907.09452v1) | Extracts 270+ hand-crafted technical/quantitative features for short-term mid-price movement; wrapper selection (entropy, LMS, LDA) plus an adaptive logistic-regression feature reaches best performance with few features on Nasdaq Nordic LOB data. | strategies/technical_factors.py |

## Medium relevance (100) (showing the 100 most recent of 392)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2601.16274v2](https://arxiv.org/abs/2601.16274v2) | MPTE applies Transformer attention to mixed-frequency nonlinear factor models, extending PCA to attention operators with consistency results; competitive on 13 FRED macro targets, recovers variable and lag importance. | `strategies/factors.py` |
| 2026 | [2603.24215v3](https://arxiv.org/abs/2603.24215v3) | Adapts Altman's bankruptcy model to compositional-data log-ratios combined with machine learning; compositional log-ratios mitigate outliers and asymmetry and change bankruptcy-prediction results versus standard ratios. | `strategies/ratios.py` |
| 2026 | [2603.19136v2](https://arxiv.org/abs/2603.19136v2) | Autoencoder reconstruction-error gating routes data to dual node transformers specialized for stable versus event-driven regimes, with reinforcement-learning control and no manual regime labels. | `strategies/regime_state.py` |
| 2026 | [2602.07066v1](https://arxiv.org/abs/2602.07066v1) | Builds a Market Stress Probability Index forecasting one-month-ahead US equity stress from cross-sectional fragility signals via L1-regularized logistic regression in an expanding window; beats a lagged-return/realized-vol benchmark out-of-sample. | `strategies/regime_score.py` |
| 2026 | [2601.12990v1](https://arxiv.org/abs/2601.12990v1) | SFAG GAN converts stylized facts (asymmetry, tails) into differentiable constraints jointly optimized with adversarial loss; on Shanghai Composite, baseline GANs collapse in backtests while SFAG supports robust momentum strategies. | `strategies/backtest_engine.py` |
| 2026 | [2602.17851v1](https://arxiv.org/abs/2602.17851v1) | Uses a causal forest with FinancialBERT sentiment scores and SHAP to estimate causal effects of report sentiment on bank profitability in Nepal; finds significant effects conditioned by loan-portfolio composition and balance-sheet leverage. | `strategies/sentiment_research.py` |
| 2026 | [2605.16324v1](https://arxiv.org/abs/2605.16324v1) | Bi-level chaotic-fusion graph network predicts intervals for stock returns via separate center/width functions and volatility-aware gating, improving interval calibration and sharpness across regimes. | strategies/conformal.py |
| 2026 | [2608.05755v2](https://arxiv.org/abs/2608.05755v2) | Extends LSTM with macro covariates and learnable sector embeddings for S&P 500 long-short forecasts; the sector-embedding model outperforms plain LSTM, Random Forest and buy-and-hold on risk and return. | strategies/universe_factors.py |
| 2026 | [2606.08586v1](https://arxiv.org/abs/2606.08586v1) | Builds stock-level topological anomaly scores via Takens delay embedding, BallMapper graphs and decoder-conditional VAEs, testing predictive content for intraday return curves; penalised function-on-function regression confirms a regime-dependent temporal fingerprint across all assets. | strategies/cross_section.py |
| 2026 | [2606.27670v1](https://arxiv.org/abs/2606.27670v1) | CryptoGAT recasts cryptocurrency price prediction as a cross-asset graph attention problem rather than temporal modeling, outperforming LSTM/GRU/Transformer baselines and arguing that extreme volatility defeats time-series models. | strategies/covariance_models.py |
| 2026 | [2608.29025v1](https://arxiv.org/abs/2608.29025v1) | Compares classical and deep hedging on real Deribit BTC options; Whalley-Wilmott cuts costs by $1.79 per episode, and none of the three deep hedging models beats any classical benchmark on any metric. | strategies/options_math.py |
| 2026 | [2605.27977v1](https://arxiv.org/abs/2605.27977v1) | Forecasts US aggregate bond index with MLPs on lagged vectors and CNNs on Gramian Angular Fields after fractional differencing; MLPs merely match the naive persistence benchmark. | strategies/factor_expressions.py |
| 2026 | [2608.14323v1](https://arxiv.org/abs/2608.14323v1) | Maps characteristic dependence via a Maximally Filtered Clique Forest onto a Homological Neural Network for annual excess-return forecasts; it matches a three-layer benchmark, ranks better, and uses ~80x fewer parameters. | strategies/universe_factors.py |
| 2026 | [2606.04574v2](https://arxiv.org/abs/2606.04574v2) | Deep RL execution overlay for crypto pair trading: hierarchical Filter-then-Rank selection plus Fixed-Risk Adaptive-Mean execution with PPO+LSTM; beat the heuristic baseline out-of-sample, significant at 10% after a block bootstrap. | strategies/mean_reversion.py |
| 2026 | [2607.00475v1](https://arxiv.org/abs/2607.00475v1) | End-to-end AI policies map market states to weights for 16 liquid CME futures via a differentiable Sharpe loss; learned policies beat equal-weight, risk-parity and time-series momentum, though non-uniformly. | strategies/portfolio_optimizer.py |
| 2026 | [2606.08791v1](https://arxiv.org/abs/2606.08791v1) | Proves a dynamic policy's cumulative regret equals the sum of per-period covariances between the cost vector and decisions, extending a single-period identity; yields a consistent O(T·nd) model-free audit tool with bias corrections. | strategies/evaluate.py |
| 2026 | [2607.28127v1](https://arxiv.org/abs/2607.28127v1) | FinSMART applies market-aligned reinforcement learning to financial sentiment using realized market outcomes and a discrete asymmetric trading reward, improving cumulative trading returns 220% over the strongest baseline. | strategies/sentiment_research.py |
| 2026 | [2606.03184v1](https://arxiv.org/abs/2606.03184v1) | Introduces FinStressTS, a synthetic benchmark of 30 diagnostic environments spanning six mechanism families; benchmarks 15 forecasters, finding autoregressive and linear models often beat Transformers on volatility-, tail- and jump-driven tasks. | strategies/evaluate.py |
| 2026 | [2602.07020v1](https://arxiv.org/abs/2602.07020v1) | Shows categorical attributes (issuer sector, domicile) dominate bond spread-curve predictability; proposes representation-learning embeddings for bond similarity that beat one-hot baselines, evaluated via sparse-issuer augmentation for risk modeling and curve construction. | `strategies/fixed_income.py` |
| 2026 | [2603.19286v1](https://arxiv.org/abs/2603.19286v1) | Integrates a pre-trained LLM with daily financial news for multi-stock prediction, using stock-name embeddings and self-, cross- and position-aware self-attentive pooling to filter news by relevance. | `strategies/news_relevance.py` |
| 2026 | [2605.17117v2](https://arxiv.org/abs/2605.17117v2) | Four geometric observables (Berry phase rate, spectral entropy, state purity, Hamiltonian sensitivity) detect regime shifts across 17 crises; Berry phase d=0.72 with ~67% fewer false alarms than a Random Forest. | strategies/regime_state.py |
| 2026 | [2608.26127v1](https://arxiv.org/abs/2608.26127v1) | Proposes FA-GSTN, reframing realized-volatility forecasting as modeling a spatio-temporal graph over the implied-volatility surface; it sets state of the art (R^2 up to 0.473) and is data-efficient and stress-robust. | strategies/options_surface.py |
| 2026 | [2606.03457v1](https://arxiv.org/abs/2606.03457v1) | Hybrid news sentiment engine: a CPU-only three-way ensemble of FinBERT-style lexicon scoring, adaptive TF-IDF headline clustering tracking realized price reactions, and auto-calibrating weights; adapts to market regimes without retraining or GPU compute. | strategies/sentiment_research.py |
| 2026 | [2602.00086v3](https://arxiv.org/abs/2602.00086v3) | Evaluates DeBERTa/RoBERTa/FinBERT news-sentiment models for stock movement prediction; DeBERTa reaches 75% accuracy, a three-model ensemble about 80%, and sentiment features slightly help LSTM/PatchTST/tPatchGNN classifiers. | `strategies/sentiment_research.py` |
| 2026 | [2602.06198v1](https://arxiv.org/abs/2602.06198v1) | Gradient-boosting classifier on SEC Form 4 insider purchases in microcaps (17,237 trades, 2018-2024) reaches AUC 0.70; distance from 52-week high dominates (36%); post-run-up disclosures yield 6.3% mean CAR. | `strategies/signal_analysis.py` |
| 2026 | [2606.00624v1](https://arxiv.org/abs/2606.00624v1) | HANET hierarchically nests daily asset-return signals inside monthly macro windows with cross-attention; attention over macro contexts adapts to scarce regimes across 55 liquid futures. | strategies/regime_score.py |
| 2026 | [2601.17773v1](https://arxiv.org/abs/2601.17773v1) | MarketGAN embeds an asset-pricing factor structure in a TCN-based GAN generating joint return vectors; matches heavy tails, volatility clustering and cross-sectional tail co-movement, and its covariance estimates outperform factor bootstrap. | `strategies/covariance_models.py` |
| 2026 | [2602.08182v1](https://arxiv.org/abs/2602.08182v1) | NANSDE-Net introduces neural-network-kernel ARMA noise, an Ito-compatible alternative to fractional Brownian motion, for Neural SDEs; matches or beats fractional SDE-Net reproducing long- and short-memory while staying tractable. | `strategies/long_memory.py` |
| 2026 | [2603.20456v1](https://arxiv.org/abs/2603.20456v1) | Neural HMM with adaptive granularity attention: a dilated-CNN tick encoder plus wavelet-LSTM, gated by local volatility and transaction intensity, for high-frequency order-flow modeling across scales. | `strategies/orderflow.py` |
| 2026 | [2603.28257v2](https://arxiv.org/abs/2603.28257v2) | KAN-PCA autoencoder replaces PCA's linear projections with B-spline KAN encodings; on 20 S&P500 returns (2015-2024) reconstructs R2=66.57% vs PCA's 62.99% with 3 factors, matching PCA out-of-sample. | `strategies/covariance_models.py` |
| 2026 | [2609.08106v1](https://arxiv.org/abs/2609.08106v1) | Decomposes MASTER's inter-stock attention: learned attention is near-uniform yet its low-rank deviation carries cross-sectional value; Nystrom attention with 32 landmarks matches full O(N^2) attention, while graph alternatives degrade performance. | strategies/cross_section.py |
| 2026 | [2608.26115v1](https://arxiv.org/abs/2608.26115v1) | Re-estimates option-implied crash predictability on 12.36M firm-days (2015-2026); the smirk-return relation fades while IV spread and risk-neutral skewness persist, with boosted trees best in the AI/mega-cap regime. | strategies/options_surface.py |
| 2026 | [2606.06823v1](https://arxiv.org/abs/2606.06823v1) | PandaAI, a closed-loop neuro-symbolic LLM agent with market-regime modeling and constrained alpha generation, reports on CSI 300 18.2% higher Rank IC and 25.7% lower maximum drawdown than state-of-the-art time-series models. | strategies/alpha_zoo.py |
| 2026 | [2603.28198v1](https://arxiv.org/abs/2603.28198v1) | PCGS fixes the generalized-share recursion while adaptively varying post-loss controls; PCGS-TF uses a causal Transformer update controller and attains pathwise weighted regret guarantees for strictly online switching-oracle tracking. | `strategies/score_engine.py` |
| 2026 | [2605.25894v1](https://arxiv.org/abs/2605.25894v1) | Multi-modal LSTM/Transformer on 15 fundamentals, 3 technicals and FinBERT news sentiment predicts earnings-day direction; Transformer achieves higher macro F1 and sentiment adds consistent value. | strategies/events.py |
| 2026 | [2609.20550v1](https://arxiv.org/abs/2609.20550v1) | Decomposes principal-component estimation error in high-dimensional factor models into out-of-subspace (estimable) and in-subspace terms with almost sure limits; in a three-factor US equity simulation out-of-subspace error dominates. | strategies/covariance_models.py |
| 2026 | [2605.27848v1](https://arxiv.org/abs/2605.27848v1) | Three-state Gaussian HMM (BIC-selected) plus reinforcement learning allocates across SPY/TLT/GLD 2004-2025; HMM-based allocations beat a passive SPY benchmark with a one-day execution lag. | strategies/regime.py |
| 2026 | [2608.12251v1](https://arxiv.org/abs/2608.12251v1) | Proposes RG-ResMoE, a regime-gated residual mixture-of-experts for cross-sectional volatility forecasting; routing regime state to experts beats appending it as input, improving accuracy, stability and VaR calibration. | strategies/volatility_models.py |
| 2026 | [2604.07159v1](https://arxiv.org/abs/2604.07159v1) | SBBTS extends the Schrodinger-Bass formulation to multi-step series, jointly calibrating drift and stochastic volatility via a conditional-transport decomposition; Heston experiments reproduce marginals and temporal dynamics. | `strategies/volatility_models.py` |
| 2026 | [2605.17724v1](https://arxiv.org/abs/2605.17724v1) | Compares LSTM and gradient boosting on MNQ 5-min intraday prediction 2021-2025; no config beats the 51.8% base rate (best 50.89%, permutation p=0.135/0.515). | strategies/falsification.py |
| 2026 | [2603.05917v3](https://arxiv.org/abs/2603.05917v3) | Proposes a node-transformer over a stock graph whose edges encode sector affiliation and price correlation, fused with BERT sentiment for cross-sectional stock price forecasting; no numeric result reported. | `strategies/sentiment.py` |
| 2026 | [2605.13407v1](https://arxiv.org/abs/2605.13407v1) | PRISM-VQ dynamic factor model combines expert priors, vector-quantized discrete latent factors and a structure-conditioned mixture-of-experts; improves cross-sectional ranking on CSI300/S&P500. | strategies/cross_section.py |
| 2026 | [2609.12793v1](https://arxiv.org/abs/2609.12793v1) | Proposes VertiFuseX, a hybrid LSTM with penultimate-layer vertical fusion of multi-scale temporal features; it achieves 30-54% MAPE reductions versus LSTM baselines across 10 global equity indices (2010-2024). | scripts/forecast_ledger.py |
| 2026 | [2609.14733v1](https://arxiv.org/abs/2609.14733v1) | Proposes WaVeFuse, wavelet-denoised OHLCV plus channel-wise CWT, CNN-BiLSTM and Transformer branches fused by vertical attention; it reaches R2 0.81-0.96 and 70.5-78.3% directional accuracy on four indices. | scripts/forecast_ledger.py |
| 2026 | [2608.10693v1](https://arxiv.org/abs/2608.10693v1) | Uses a 2D convolutional LSTM with FOMC-date features to forecast the implied-volatility surface; pre-announcement IV rises strongest for short-dated OTM options in high-volatility regimes, with a limited but real ML edge. | strategies/options_surface.py |
| 2026 | [2601.08896v1](https://arxiv.org/abs/2601.08896v1) | XGBoost forecasts one-step-ahead NEPSE index log-returns using 30 lagged returns, rolling volatility, and 14-period RSI, with Optuna tuning and walk-forward expanding/rolling validation avoiding lookahead bias. | `strategies/backtest_engine.py` |
| 2025 | [2510.12725v1](https://arxiv.org/abs/2510.12725v1) | Non-parametric bootstrap robust portfolio optimization builds data-driven confidence intervals without distributional assumptions, mitigating estimation error and parameter instability in expected returns and covariances. | `strategies/portfolio_optimizer.py` |
| 2025 | [2507.09347v1](https://arxiv.org/abs/2507.09347v1) | Clusters nine equities by volatility via GMM, then Granger causality, PCMCI and transfer entropy find lead-lag links; DTW/KNN sets trade lag, backtest returning 15.38% versus 10.39% buy-and-hold. | `strategies/statistical.py` |
| 2025 | [2510.16636v1](https://arxiv.org/abs/2510.16636v1) | Three-step framework: right-tailed unit-root test identifies S&P 500 bubbles, NLP extracts news-sentiment features, and ensemble learning predicts bubble occurrence with macro indicators. | `strategies/regime.py` |
| 2025 | [2508.02686v1](https://arxiv.org/abs/2508.02686v1) | Mixture-of-Experts combines an RNN for high-volatility stocks with linear regression for stable ones via a volatility-aware gate; across 30 US stocks it cuts MSE up to 33% and 28% versus standalone models. | `strategies/regime_score.py` |
| 2025 | [2509.10542v1](https://arxiv.org/abs/2509.10542v1) | Adaptive Temporal Fusion Transformer segments crypto subseries at relative maxima past a threshold, using dynamic subseries lengths and pattern categories to improve short-term forecasting over vanilla TFT. | `strategies/volatility_models.py` |
| 2025 | [2502.08242v2](https://arxiv.org/abs/2502.08242v2) | Network communicability on correlation-derived Indian market graphs; 70%/80% of stock pairs shift significantly in GFC/COVID; communicability features beat shortest-path measures at classifying stable versus volatile periods. | `strategies/triadic_stress.py` |
| 2025 | [2511.06224v1](https://arxiv.org/abs/2511.06224v1) | Benchmarks ARIMA, SARIMA, GARCH and EGARCH on 2010-2020 daily Bitcoin prices; ARIMA gives the strongest short-run log-price forecasts while EGARCH best fits volatility asymmetry. | `strategies/volatility_models.py` |
| 2025 | [2504.16635v2](https://arxiv.org/abs/2504.16635v2) | Combines GARCH volatility models with a Double Deep Q-Network direction forecast for Value-at-Risk; on daily Eurostoxx 50 it improves VaR accuracy, cuts breaches and capital requirements under crisis volatility. | `strategies/book_risk.py` |
| 2025 | [2505.19243v1](https://arxiv.org/abs/2505.19243v1) | Compares log returns against fractional and tempered-fractional differencing as LSTM inputs across four indices; fractional differentiation improves forecast error metrics and risk-adjusted trading returns, supporting memory-preserving transforms. | `strategies/long_memory.py` |
| 2025 | [2510.16008v1](https://arxiv.org/abs/2510.16008v1) | Introduces convolutional attention over recurrent and 2D-convolutional-recurrent layers with a novel multivariate padding method, forecasting Betfair pre-live market-depth price movements for automated trading. | `strategies/orderflow.py` |
| 2025 | [2508.02738v1](https://arxiv.org/abs/2508.02738v1) | CreditARF integrates financial metrics with FinBERT features from annual reports for corporate credit rating, releasing the CCRD dataset; experiments show 8-12% accuracy improvement over financial-only models. | `strategies/text_factors.py` |
| 2025 | [2512.21798v2](https://arxiv.org/abs/2512.21798v2) | Generates synthetic S&P 500 return series with TimeGAN and VAEs; TimeGAN better captures temporal dynamics, supporting privacy-preserving, reproducible portfolio and risk simulation. | - |
| 2025 | [2504.13521v2](https://arxiv.org/abs/2504.13521v2) | Represents sequential limit-order-book snapshots as image channels with learned embeddings and applies deep learning to HFT; reports state-of-the-art performance in high-frequency trading and portfolio optimization. | `strategies/orderflow.py` |
| 2025 | [2502.13722v2](https://arxiv.org/abs/2502.13722v2) | Deep-learning VWAP execution framework directly optimizes the execution objective via custom loss, bypassing volume-curve prediction; consistently lowers VWAP slippage versus conventional and linear approaches in crypto markets. | `strategies/execution_schedule.py` |
| 2025 | [2504.20088v1](https://arxiv.org/abs/2504.20088v1) | Trains a deep residual network with a hybrid market/analytic loss to price European Petrobras options, cutting mean absolute error 64.3% versus Black-Scholes in the 3-19 BRL range and staying accurate at long expiries. | `strategies/options_math.py` |
| 2025 | [2507.01971v1](https://arxiv.org/abs/2507.01971v1) | Proposes DeepSupp, a multi-head attention autoencoder over dynamic correlation matrices, extracting S&P 500 support levels via DBSCAN; it beats six baselines on six financial metrics including support accuracy and regime sensitivity. | `strategies/extended_indicators.py` |
| 2025 | [2507.20039v1](https://arxiv.org/abs/2507.20039v1) | Builds dependency networks from VAR forecast-error variance decomposition and Minimum Spanning Tree, selecting central stocks; ARIMA/NNAR forecasts plus VaR allocation yield 63.74% versus 18% buy-and-hold over one year. | `strategies/portfolio_optimizer.py` |
| 2025 | [2504.06566v5](https://arxiv.org/abs/2504.06566v5) | Diffusion factor model embeds latent factor structure into generative diffusion by decomposing the score function with time-varying orthogonal projections; nonasymptotic bounds depend on factor dimension, enabling high-dimensional return simulation and mean-variance/factor portfolios. | `strategies/factors.py` |
| 2025 | [2509.16137v1](https://arxiv.org/abs/2509.16137v1) | Adds Bloomberg intra-bar open/high/low/close timestamps to OHLC features; timing features consistently improve VWAP prediction across ML architectures on log-likelihood, MSE, R2 and direction. | `tradingagents/dataflows/stockstats_utils.py` |
| 2025 | [2508.02702v1](https://arxiv.org/abs/2508.02702v1) | Proposes a data-manipulation framework simulating time-varying data availability, domain shifts and label scarcity to realistically evaluate transfer-learning methods on financial fraud streams, illustrated on proprietary card-payment and public Bank Account Fraud datasets. | `strategies/coverage_window.py` |
| 2025 | [2506.06345v1](https://arxiv.org/abs/2506.06345v1) | Combines transformer time-series models (DLinear, LTSNet, Vanilla/Time Series Transformer) with technical indicators and SHAP/LIME explanations to predict BIST100 bank prices (2015-2025), demonstrating strong accuracy and interpretable feature attributions. | `strategies/report_attribution.py` |
| 2025 | [2501.16659v1](https://arxiv.org/abs/2501.16659v1) | Solves Exploratory Mean-Variance with Regime Switching via RL, proving a Policy Improvement Theorem; Orthogonality Condition learning beats temporal-difference learning and outperforms on real market data. | `strategies/portfolio_optimizer.py` |
| 2025 | [2502.05218v1](https://arxiv.org/abs/2502.05218v1) | FactorGCL, a hypergraph factor model with cascading residual architecture and temporal residual contrastive learning, mines hidden factors beyond prior ones and beats state-of-the-art stock-return prediction. | `strategies/factors.py` |
| 2025 | [2505.08180v1](https://arxiv.org/abs/2505.08180v1) | Trains ML models on high-frequency predictors to forecast intraday volume; finds intraday volume highly predictable via commonality and that accurate forecasts materially improve VWAP execution strategies. | `strategies/execution_schedule.py` |
| 2025 | [2503.21422v1](https://arxiv.org/abs/2503.21422v1) | Surveys AI in quantitative investment via the alpha-strategy pipeline: human-crafted features and statistical models, then deep learning across data and execution, then LLMs as autonomous agents generating alphas in self-iterative workflows. | `strategies/alpha_zoo.py` |
| 2025 | [2509.24144v2](https://arxiv.org/abs/2509.24144v2) | End-to-end LSTM plus graph attention plus news sentiment directly learns daily portfolio weights for nine US stocks, avoiding the forecast-then-mean-variance two-step and its instability. | `strategies/portfolio_optimizer.py` |
| 2025 | [2502.11310v2](https://arxiv.org/abs/2502.11310v2) | Generalized factor neural network with PCA/Soft PCA layers embedded at any stage, alternating factor modeling and nonlinear transforms; effective on hierarchical compositional data, forecasting equity ETF indices and macro nowcasting. | `strategies/factors.py` |
| 2025 | [2506.03780v3](https://arxiv.org/abs/2506.03780v3) | Proves random-Fourier-feature in-sample standardization replaces shift-invariant kernels with training-set-dependent ones, and derives information-theoretic lower bounds; with 12,000 features and 12 monthly observations, escaping the bound needs 25-30 years. | `strategies/coverage_window.py` |
| 2025 | [2510.03236v1](https://arxiv.org/abs/2510.03236v1) | Regime-switching methods (soft Markov switching, distributional spectral clustering) forecast S&P 500 realized volatility from 5-minute returns, 2014-2025, with historical and sentiment features. | `strategies/volatility_models.py` |
| 2025 | [2512.17923v2](https://arxiv.org/abs/2512.17923v2) | Obfuscation testing: LLMs given only raw S&P 500 gamma-exposure values detect dealer hedging patterns (gamma, pinning, 0DTE) at 71.5%, staying 91.2% accurate without regime labels or temporal context. | `strategies/derivatives_gamma.py` |
| 2025 | [2503.03612v4](https://arxiv.org/abs/2503.03612v4) | Surveys financial sentiment's definition and measurement, tracing lexicon and market-based methods to BERT-style models (RoBERTa, FinBERT) for classification and GPT-style models (GPT-4, OPT, LLaMA) for generation and real-time interpretation. | `strategies/sentiment_research.py` |
| 2025 | [2504.15908v1](https://arxiv.org/abs/2504.15908v1) | Builds multi-scale Hawkes order-flow features including limit-order posting distance, trains an interpretable probabilistic network for mid-price moves, and finds 31% of large orders could spoof; posting distance is critical. | `strategies/orderflow.py` |
| 2025 | [2508.20108v2](https://arxiv.org/abs/2508.20108v2) | ReVol: return-volatility normalization plus sample-characteristic reintegration and GBM/NN blend to counter distribution shift; improves backbones by over 0.03 IC and 0.7 SR on average. | `strategies/volatility_models.py` |
| 2025 | [2505.22836v1](https://arxiv.org/abs/2505.22836v1) | Trains a deep-hedging neural network with as few as 256 trajectories; under geometric Brownian motion with transaction costs it significantly outperforms Black-Scholes and the Leland model, enabling practical real-time implementation. | `strategies/options_math.py` |
| 2025 | [2502.05186v1](https://arxiv.org/abs/2502.05186v1) | Multimodal LSTM fusing financial metrics, tweets and news; ChatGPT-4o/FinBERT sentiment lifts forecast accuracy up to 5%, with tweet and news sentiment individually and jointly predictive. | `strategies/sentiment_research.py` |
| 2025 | [2503.08696v1](https://arxiv.org/abs/2503.08696v1) | Multimodal Russian-market forecaster combines candlestick time series with news text via RuBERT/Qwen embeddings and an LSTM over 176 Moscow Exchange stocks; adding the textual modality cut MAPE by 55%. | `strategies/news_relevance.py` |
| 2025 | [2507.02018v1](https://arxiv.org/abs/2507.02018v1) | Proposes NGAT, a node-level graph attention network for long-term stock prediction over corporate relationship graphs; demonstrates existing graph-comparison methods are flawed and NGAT performs consistently across two datasets. | `strategies/peer_universe.py` |
| 2025 | [2507.01970v1](https://arxiv.org/abs/2507.01970v1) | Uses OpenAI headline embeddings of WSJ news with PCA to predict SPY daily moves, adding DXY and Treasury yields; headline embeddings improve price prediction by at least 40% over models without them. | `strategies/sentiment_research.py` |
| 2025 | [2506.23619v2](https://arxiv.org/abs/2506.23619v2) | Shows posterior drift degrades out-of-sample forecasting of overparametrized models; applied to equity-premium market timing, results are highly sensitive to sub-periods and bandwidth, with large bandwidths consistent but risk-adjusted unattractive. | `strategies/config_robustness.py` |
| 2025 | [2512.04099v1](https://arxiv.org/abs/2512.04099v1) | Applies Partial-Multivariate Transformer (PMformer) to BTCUSDT/ETHUSDT returns against eleven baselines; partial features balance signal and noise, but lower prediction error does not consistently translate to higher simulated returns. | `strategies/evaluate.py` |
| 2025 | [2509.05922v1](https://arxiv.org/abs/2509.05922v1) | Uses DML average-partial-effect causal ML plus real-time capitulation nowcasting; identifies options-implied risk-appetite volatility and market liquidity as key causal drivers of market troughs. | `strategies/options_surface.py` |
| 2025 | [2506.07928v1](https://arxiv.org/abs/2506.07928v1) | Tests whether high-dimensional ML beats benchmarks for daily firm-level realized-variance forecasting; small forecast-error gains yield economically significant portfolio improvements, arguing models be trained for portfolio objectives. | `strategies/long_memory.py` |
| 2025 | [2509.11844v1](https://arxiv.org/abs/2509.11844v1) | ProteuS generates semi-synthetic financial time series with pre-defined structural breaks, supplying ground truth to benchmark concept-drift and regime-adaptation algorithms. | `strategies/regime.py` |
| 2025 | [2502.09079v1](https://arxiv.org/abs/2502.09079v1) | Complexity-entropy plane and spectral analysis show crypto series resemble Brownian noise; across horizons simple naive models consistently beat machine/deep forecasters, underscoring low predictability. | `strategies/complexity.py` |
| 2025 | [2511.07434v1](https://arxiv.org/abs/2511.07434v1) | Presents RL-Exec, a PPO liquidation agent trained on BTC-USD LOB replays with transient impact, fees and latency, outperforming TWAP and a book-liquidity VWAP baseline under a strict train/test split. | `strategies/execution_schedule.py` |
| 2025 | [2502.18177v1](https://arxiv.org/abs/2502.18177v1) | Dynamic neural VWAP framework adds recurrent networks and continuous feedback adjustment to a prior static direct-optimization model; gains 10-15% execution performance in liquid crypto markets. | `strategies/execution_schedule.py` |
| 2025 | [2502.05210v3](https://arxiv.org/abs/2502.05210v3) | Tests Fama-French three/four/five-factor models on Manuf, Hitec and Other US sectors; five-factor fits best; LSTM captures additional industry-specific factors for return regression and prediction. | `strategies/factors.py` |
| 2025 | [2507.06345v2](https://arxiv.org/abs/2507.06345v2) | Formulates trade execution as dynamic market-and-limit order placement modelled by multivariate logistic-normal distributions, trained with reinforcement learning; it outperforms benchmark strategies in simulated limit-order-book environments with noise, tactical and strategic traders. | `strategies/execution_schedule.py` |
| 2025 | [2510.16503v1](https://arxiv.org/abs/2510.16503v1) | Fine-tunes BERT on Russia-Ukraine war financial news (2024) and combines sentiment scores with a Student-t GARCH to relate sentiment to heavy-tailed market volatility. | `strategies/sentiment_research.py` |
| 2025 | [2506.19856v1](https://arxiv.org/abs/2506.19856v1) | Introduces Characteristic Vector Linkages as firm-linkage proxies; Euclidean similarity and Quantum Cognition Machine Learning both yield profitable momentum-spillover strategies, with QCML similarity outperforming Euclidean. | `strategies/peer_universe.py` |
| 2025 | [2502.01495v1](https://arxiv.org/abs/2502.01495v1) | Applies quantum cognition machine learning to supervised distance-metric learning for corporate bonds; outperforms classical tree-based similarity models in high-yield markets, matching or better in investment-grade. | `strategies/peer_universe.py` |
| 2025 | [2502.15757v3](https://arxiv.org/abs/2502.15757v3) | TLOB transformer uses dual spatial/temporal attention on limit-order-book data with a horizon-bias-free labeling scheme; beats state-of-the-art across datasets/horizons, though predictability falls over time and spreads erode profits. | `strategies/orderflow.py` |
| 2025 | [2504.09380v2](https://arxiv.org/abs/2504.09380v2) | Embeds the GARCH(1,1) update into GRU/LSTM gating (GARCH-GRU/LSTM); out-of-sample it beats classical GARCH, pipeline hybrids and Transformers on US equity indices, with GARCH-GRU fastest and well-calibrated 99% VaR. | `strategies/volatility_models.py` |
| 2025 | [2511.08608v1](https://arxiv.org/abs/2511.08608v1) | Rolling walk-forward test on NIFTY equities finds 'thinking' LLMs (gpt-5) do not reliably beat a direct LLM or ridge/random-forest learners on cross-sectional 1-IC, MSE and costed backtests. | `strategies/signal_analysis.py` |

## Low relevance / background (346)

| year | id | title |
| --- | --- | --- |
| 2026 | [2606.21515v1](https://arxiv.org/abs/2606.21515v1) | A Censored Transformed Model for Proportional Outcomes with Boundary Mass and an Application to Loss Given Default Modeling |
| 2026 | [2603.16886v1](https://arxiv.org/abs/2603.16886v1) | A Controlled Comparison of Deep Learning Architectures for Multi-Horizon Financial Forecasting: Evidence from 918 Experiments |
| 2026 | [2608.26106v1](https://arxiv.org/abs/2608.26106v1) | A Statistical-Finance Benchmark for Same-Day Directional Stock Prediction: Walk-Forward Evidence from SPY |
| 2026 | [2603.18107v1](https://arxiv.org/abs/2603.18107v1) | ARTEMIS: A Neuro Symbolic Framework for Economically Constrained Market Dynamics |
| 2026 | [2604.04662v1](https://arxiv.org/abs/2604.04662v1) | Anticipatory Reinforcement Learning: From Generative Path-Laws to Distributional Value Functions |
| 2026 | [2604.22801v2](https://arxiv.org/abs/2604.22801v2) | Beyond Sequential Prediction: Learning Financial Market Dynamics in Volatile and Non-Stationary Environments through Sentiment-Conditioned Generative Modelling |
| 2026 | [2602.00037v2](https://arxiv.org/abs/2602.00037v2) | Bitcoin Price Prediction using Machine Learning and Combinatorial Fusion Analysis |
| 2026 | [2604.09650v1](https://arxiv.org/abs/2604.09650v1) | Dynamic Forecasting and Temporal Feature Evolution of Stock Repurchases in Listed Companies Using Attention-Based Deep Temporal Networks |
| 2026 | [2607.25459v1](https://arxiv.org/abs/2607.25459v1) | Emergent Latent-State Computation under Stochastic Volatility |
| 2026 | [2602.00049v1](https://arxiv.org/abs/2602.00049v1) | Exploring the Interpretability of Forecasting Models for Energy Balancing Market |
| 2026 | [2604.02549v1](https://arxiv.org/abs/2604.02549v1) | Financial Anomaly Detection for the Canadian Market |
| 2026 | [2608.26174v1](https://arxiv.org/abs/2608.26174v1) | Forecasting Economically Significant Bitcoin Moves: A Multi-Scale TCN with Profit-Optimized Thresholds |
| 2026 | [2605.23962v1](https://arxiv.org/abs/2605.23962v1) | From Index to Equity: Pre-Training Transformers for Stock Return Prediction |
| 2026 | [2606.05138v1](https://arxiv.org/abs/2606.05138v1) | Generating Financial Time Series by Matching Random Convolutional Features |
| 2026 | [2606.30037v1](https://arxiv.org/abs/2606.30037v1) | Heads, Not Backbones: Output Heads Dominate Architectures on Fat-Tailed Returns |
| 2026 | [2608.08825v1](https://arxiv.org/abs/2608.08825v1) | Hybrid Neural-Classical Correction for Frozen Time Series Foundation Models: A Comprehensive Ablation Study on High-Frequency Stock Prediction |
| 2026 | [2606.25007v1](https://arxiv.org/abs/2606.25007v1) | Multi-Stream Temporal Fusion for Financial Fraud Detection |
| 2026 | [2601.19321v1](https://arxiv.org/abs/2601.19321v1) | Predictive Accuracy versus Interpretability in Energy Markets: A Copula-Enhanced TVP-SVAR Analysis |
| 2026 | [2606.15701v1](https://arxiv.org/abs/2606.15701v1) | Robust Transformer-Based One-Step Stock Index Forecasting via Shifted Data Augmentation |
| 2026 | [2604.16835v1](https://arxiv.org/abs/2604.16835v1) | The CTLNet for Shanghai Composite Index Prediction |
| 2026 | [2601.02677v1](https://arxiv.org/abs/2601.02677v1) | Uni-FinLLM: A Unified Multimodal Large Language Model with Modular Task Heads for Micro-Level Stock Prediction and Macro-Level Systemic Risk Assessment |
| 2026 | [2608.05373v1](https://arxiv.org/abs/2608.05373v1) | Velocity- and Regime-Aware Detection of Intraday Options Market Manipulation, with Explainable Attribution |
| 2025 | [2511.08658v1](https://arxiv.org/abs/2511.08658v1) | "It Looks All the Same to Me": Cross-index Training for Long-term Financial Series Prediction |
| 2025 | [2507.18643v1](https://arxiv.org/abs/2507.18643v1) | A Regression-Based Share Market Prediction Model for Bangladesh |
| 2025 | [2510.16066v4](https://arxiv.org/abs/2510.16066v4) | AI-BAAM: AI-Driven Bank Statement Analytics as Alternative Data for Malaysian MSME Credit Scoring |
| 2025 | [2506.09851v2](https://arxiv.org/abs/2506.09851v2) | Advancing Exchange Rate Forecasting: Leveraging Machine Learning and AI for Enhanced Accuracy in Global Financial Markets |
| 2025 | [2510.15993v1](https://arxiv.org/abs/2510.15993v1) | Aligning Language Models with Investor and Market Behavior for Financial Recommendations |
| 2025 | [2502.15726v1](https://arxiv.org/abs/2502.15726v1) | Bankruptcy analysis using images and convolutional neural networks (CNN) |
| 2025 | [2508.02685v1](https://arxiv.org/abs/2508.02685v1) | Benchmarking Classical and Quantum Models for DeFi Yield Prediction on Curve Finance |
| 2025 | [2506.08113v2](https://arxiv.org/abs/2506.08113v2) | Benchmarking Pre-Trained Time Series Models for Electricity Price Forecasting |
| 2025 | [2510.15900v1](https://arxiv.org/abs/2510.15900v1) | Bitcoin Price Forecasting Based on Hybrid Variational Mode Decomposition and Long Short Term Memory Network |
| 2025 | [2501.09760v1](https://arxiv.org/abs/2501.09760v1) | Boosting the Accuracy of Stock Market Prediction via Multi-Layer Hybrid MTL Structure |
| 2025 | [2511.13384v4](https://arxiv.org/abs/2511.13384v4) | CBDC Stress Test in a Dual-Currency Setting |
| 2025 | [2504.12771v1](https://arxiv.org/abs/2504.12771v1) | Classification-Based Analysis of Price Pattern Differences Between Cryptocurrencies and Stocks |
| 2025 | [2512.12783v3](https://arxiv.org/abs/2512.12783v3) | Credit Risk Estimation with Non-Financial Features: Evidence from a Synthetic Istanbul Dataset |
| 2025 | [2507.01980v1](https://arxiv.org/abs/2507.01980v1) | Detecting Fraud in Financial Networks: A Semi-Supervised GNN Approach with Granger-Causal Explanations |
| 2025 | [2511.08588v1](https://arxiv.org/abs/2511.08588v1) | Explainable Federated Learning for U.S. State-Level Financial Distress Modeling |
| 2025 | [2504.20250v1](https://arxiv.org/abs/2504.20250v1) | Financial Data Analysis with Robust Federated Logistic Regression |
| 2025 | [2502.15822v1](https://arxiv.org/abs/2502.15822v1) | Financial fraud detection system based on improved random forest and gradient boosting machine (GBM) |
| 2025 | [2507.01979v1](https://arxiv.org/abs/2507.01979v1) | Forecasting Labor Markets with LSTNet: A Multi-Scale Deep Learning Approach |
| 2025 | [2507.01964v1](https://arxiv.org/abs/2507.01964v1) | Forecasting Nigerian Equity Stock Returns Using Long Short-Term Memory Technique |
| 2025 | [2501.13136v1](https://arxiv.org/abs/2501.13136v1) | Forecasting of Bitcoin Prices Using Hashrate Features: Wavelet and Deep Stacking Approach |
| 2025 | [2503.15403v1](https://arxiv.org/abs/2503.15403v1) | HQNN-FSP: A Hybrid Classical-Quantum Neural Network for Regression-Based Financial Stock Market Prediction |
| 2025 | [2512.15738v1](https://arxiv.org/abs/2512.15738v1) | Hybrid Quantum-Classical Ensemble Learning for S\&P 500 Directional Prediction |
| 2025 | [2512.07860v1](https://arxiv.org/abs/2512.07860v1) | Integrating LSTM Networks with Neural Levy Processes for Financial Forecasting |
| 2025 | [2507.01973v2](https://arxiv.org/abs/2507.01973v2) | Integration of Wavelet Transform Convolution and Channel Attention with LSTM for Stock Price Prediction based Portfolio Allocation |
| 2025 | [2510.04556v2](https://arxiv.org/abs/2510.04556v2) | Model Monitoring: A General Framework with an Application to Non-life Insurance Pricing |
| 2025 | [2512.17225v2](https://arxiv.org/abs/2512.17225v2) | Modeling financial time series with $φ^{4}$ quantum field theory |
| 2025 | [2506.15723v3](https://arxiv.org/abs/2506.15723v3) | Modern approaches to building interpretable models of the property market using machine learning on the base of mass cadastral valuation |
| 2025 | [2502.15853v1](https://arxiv.org/abs/2502.15853v1) | Multi-Agent Stock Prediction Systems: Machine Learning Models, Simulations, and Real-Time Trading Strategies |
| 2025 | [2504.19623v2](https://arxiv.org/abs/2504.19623v2) | Multi-Horizon Echo State Network Prediction of Intraday Stock Returns |
| 2025 | [2504.18982v1](https://arxiv.org/abs/2504.18982v1) | On Bitcoin Price Prediction |
| 2025 | [2601.05274v1](https://arxiv.org/abs/2601.05274v1) | On the use of case estimate and transactional payment data in neural networks for individual loss reserving |
| 2025 | [2505.13933v2](https://arxiv.org/abs/2505.13933v2) | Quantum Reservoir Computing for Realized Volatility Forecasting |
| 2025 | [2510.15903v1](https://arxiv.org/abs/2510.15903v1) | Quantum and Classical Machine Learning in Decentralized Finance: Comparative Evidence from Multi-Asset Backtesting of Automated Market Makers |
| 2025 | [2507.22035v1](https://arxiv.org/abs/2507.22035v1) | Quantum generative modeling for financial time series with temporal correlations |
| 2025 | [2512.17929v2](https://arxiv.org/abs/2512.17929v2) | Reinforcement Learning for Monetary Policy Under Macroeconomic Uncertainty: Analyzing Tabular and Function Approximation Methods |
| 2025 | [2507.08835v1](https://arxiv.org/abs/2507.08835v1) | Representation learning with a transformer by contrastive learning for money laundering detection |
| 2025 | [2512.17936v1](https://arxiv.org/abs/2512.17936v1) | Risk-Aware Financial Forecasting Enhanced by Machine Learning and Intuitionistic Fuzzy Multi-Criteria Decision-Making |
| 2025 | [2508.11372v2](https://arxiv.org/abs/2508.11372v2) | Stealing Accuracy: Predicting Day-ahead Electricity Prices with Temporal Hierarchy Forecasting (THieF) |
| 2025 | [2502.15813v1](https://arxiv.org/abs/2502.15813v1) | Stock Price Prediction Using a Hybrid LSTM-GNN Model: Integrating Time-Series and Graph-Based Analysis |
| 2025 | [2511.05030v3](https://arxiv.org/abs/2511.05030v3) | The Shape of Markets: Machine learning modeling and Prediction Using 2-Manifold Geometries |
| 2025 | [2505.09620v1](https://arxiv.org/abs/2505.09620v1) | The impact of economic policies on housing prices. Approximations and predictions in the UK, the US, France, and Switzerland from the 1980s to today |
| 2025 | [2506.17244v1](https://arxiv.org/abs/2506.17244v1) | Transformers Beyond Order: A Chaos-Markov-Gaussian Framework for Short-Term Sentiment Forecasting of Any Financial OHLC timeseries Data |
| 2025 | [2601.00011v1](https://arxiv.org/abs/2601.00011v1) | Ultimate Forward Rate Prediction and its Application to Bond Yield Forecasting: A Machine Learning Perspective |
| 2025 | [2512.17945v2](https://arxiv.org/abs/2512.17945v2) | What's the Price of Monotonicity? A Multi-Dataset Benchmark of Monotone-Constrained Gradient Boosting for Credit PD |
| 2025 | [2502.00201v2](https://arxiv.org/abs/2502.00201v2) | Year-over-Year Developments in Financial Fraud Detection via Deep Learning: A Systematic Literature Review |
| 2024 | [2405.03624v1](https://arxiv.org/abs/2405.03624v1) | $ε$-Policy Gradient for Online Pricing |
| 2024 | [2404.07298v3](https://arxiv.org/abs/2404.07298v3) | A Deep Learning Method for Predicting Mergers and Acquisitions: Temporal Dynamic Industry Networks |
| 2024 | [2410.12807v1](https://arxiv.org/abs/2410.12807v1) | A Hierarchical conv-LSTM and LLM Integrated Model for Holistic Stock Forecasting |
| 2024 | [2405.13076v1](https://arxiv.org/abs/2405.13076v1) | A K-means Algorithm for Financial Market Risk Forecasting |
| 2024 | [2411.13564v1](https://arxiv.org/abs/2411.13564v1) | A Random Forest approach to detect and identify Unlawful Insider Trading |
| 2024 | [2410.02846v3](https://arxiv.org/abs/2410.02846v3) | A Spatio-Temporal Machine Learning Model for Mortgage Credit Risk: Default Probabilities and Loan Portfolios |
| 2024 | [2410.19291v2](https://arxiv.org/abs/2410.19291v2) | A Stock Price Prediction Approach Based on Time Series Decomposition and Multi-Scale CNN using OHLCT Images |
| 2024 | [2402.06689v1](https://arxiv.org/abs/2402.06689v1) | A Study on Stock Forecasting Using Deep Learning and Statistical Models |
| 2024 | [2407.18324v1](https://arxiv.org/abs/2407.18324v1) | AMA-LSTM: Pioneering Robust and Fair Financial Audio Analysis for Stock Volatility Prediction |
| 2024 | [2410.21291v3](https://arxiv.org/abs/2410.21291v3) | Achilles, Neural Network to Predict the Gold Vs US Dollar Integration with Trading Bot for Automatic Trading |
| 2024 | [2407.06529v1](https://arxiv.org/abs/2407.06529v1) | Advanced Financial Fraud Detection Using GNN-CL Model |
| 2024 | [2404.07969v1](https://arxiv.org/abs/2404.07969v1) | An End-to-End Structure with Novel Position Mechanism and Improved EMD for Stock Forecasting |
| 2024 | [2401.05441v2](https://arxiv.org/abs/2401.05441v2) | An adaptive network-based approach for advanced forecasting of cryptocurrency values |
| 2024 | [2404.04282v1](https://arxiv.org/abs/2404.04282v1) | Analyzing Economic Convergence Across the Americas: A Survival Analysis Approach to GDP per Capita Trajectories |
| 2024 | [2403.00770v1](https://arxiv.org/abs/2403.00770v1) | Blockchain Metrics and Indicators in Cryptocurrency Trading |
| 2024 | [2411.06076v1](https://arxiv.org/abs/2411.06076v1) | BreakGPT: Leveraging Large Language Models for Predicting Asset Price Surges |
| 2024 | [2402.14708v2](https://arxiv.org/abs/2402.14708v2) | CaT-GNN: Enhancing Credit Card Fraud Detection via Causal Temporal Graph Neural Networks |
| 2024 | [2408.06679v1](https://arxiv.org/abs/2408.06679v1) | Case-based Explainability for Random Forest: Prototypes, Critics, Counter-factuals and Semi-factuals |
| 2024 | [2403.14695v2](https://arxiv.org/abs/2403.14695v2) | Chain-structured neural architecture search for financial time series forecasting |
| 2024 | [2412.10860v2](https://arxiv.org/abs/2412.10860v2) | Classification of Financial Data Using Quantum Support Vector Machine |
| 2024 | [2409.03762v1](https://arxiv.org/abs/2409.03762v1) | Combining supervised and unsupervised learning methods to predict financial market movements |
| 2024 | [2411.05790v1](https://arxiv.org/abs/2411.05790v1) | Comparative Analysis of LSTM, GRU, and Transformer Models for Stock Price Prediction |
| 2024 | [2405.08089v1](https://arxiv.org/abs/2405.08089v1) | Comparative Study of Bitcoin Price Prediction |
| 2024 | [2409.08297v1](https://arxiv.org/abs/2409.08297v1) | Comparative Study of Long Short-Term Memory (LSTM) and Quantum Long Short-Term Memory (QLSTM): Prediction of Stock Market Movement |
| 2024 | [2401.09778v1](https://arxiv.org/abs/2401.09778v1) | Cross-Domain Behavioral Credit Modeling: transferability from private to central data |
| 2024 | [2403.00775v1](https://arxiv.org/abs/2403.00775v1) | Detecting Anomalous Events in Object-centric Business Processes via Graph Neural Networks |
| 2024 | [2412.18202v6](https://arxiv.org/abs/2412.18202v6) | Developing Cryptocurrency Trading Strategy Based on Autoencoder-CNN-GANs Algorithms |
| 2024 | [2403.00707v2](https://arxiv.org/abs/2403.00707v2) | Dimensionality reduction techniques to support insider trading detection |
| 2024 | [2404.00015v3](https://arxiv.org/abs/2404.00015v3) | Empowering Credit Scoring Systems with Quantum-Enhanced Machine Learning |
| 2024 | [2411.05013v1](https://arxiv.org/abs/2411.05013v1) | Enhancing literature review with LLM and NLP methods. Algorithmic trading case |
| 2024 | [2410.07216v1](https://arxiv.org/abs/2410.07216v1) | Evaluating Financial Relational Graphs: Interpretation Before Prediction |
| 2024 | [2405.11686v1](https://arxiv.org/abs/2405.11686v1) | Exploiting Distributional Value Functions for Financial Market Valuation, Enhanced Feature Creation and Improvement of Trading Algorithms |
| 2024 | [2412.16083v2](https://arxiv.org/abs/2412.16083v2) | Federated Diffusion Modeling with Differential Privacy for Tabular Data Synthesis |
| 2024 | [2403.06779v1](https://arxiv.org/abs/2403.06779v1) | From Factor Models to Deep Learning: Machine Learning in Reshaping Empirical Asset Pricing |
| 2024 | [2411.05815v2](https://arxiv.org/abs/2411.05815v2) | Graph Neural Networks for Financial Fraud Detection: A Review |
| 2024 | [2412.10540v1](https://arxiv.org/abs/2412.10540v1) | Higher Order Transformers: Enhancing Stock Movement Prediction On Multimodal Time-Series Data |
| 2024 | [2407.13698v1](https://arxiv.org/abs/2407.13698v1) | International Trade Flow Prediction with Bilateral Trade Provisions |
| 2024 | [2404.16169v3](https://arxiv.org/abs/2404.16169v3) | Interpretable Machine Learning Models for Predicting the Next Targets of Activist Funds |
| 2024 | [2404.00034v1](https://arxiv.org/abs/2404.00034v1) | Investigating Similarities Across Decentralized Financial (DeFi) Services |
| 2024 | [2409.08282v3](https://arxiv.org/abs/2409.08282v3) | LSR-IGRU: Stock Trend Prediction Based on Long Short-Term Relationships and Improved GRU |
| 2024 | [2409.06728v1](https://arxiv.org/abs/2409.06728v1) | Leveraging RNNs and LSTMs for Synchronization Analysis in the Indian Stock Market: A Threshold-Based Classification Approach |
| 2024 | [2412.14529v1](https://arxiv.org/abs/2412.14529v1) | Leveraging Time Series Categorization and Temporal Fusion Transformers to Improve Cryptocurrency Price Forecasting |
| 2024 | [2410.20679v3](https://arxiv.org/abs/2410.20679v3) | MCI-GRU: Stock Prediction Model Based on Multi-Head Cross-Attention and Improved GRU |
| 2024 | [2402.06633v1](https://arxiv.org/abs/2402.06633v1) | MDGNN: Multi-Relational Dynamic Graph Neural Network for Comprehensive and Dynamic Stock Investment Prediction |
| 2024 | [2404.07179v1](https://arxiv.org/abs/2404.07179v1) | Machine learning-based similarity measure to forecast M&A from patent data |
| 2024 | [2402.18959v1](https://arxiv.org/abs/2402.18959v1) | MambaStock: Selective state space model for stock prediction |
| 2024 | [2411.12013v2](https://arxiv.org/abs/2411.12013v2) | Neural and Time-Series Approaches for Pricing Weather Derivatives: Performance and Regime Adaptation Using Satellite Data |
| 2024 | [2412.16333v1](https://arxiv.org/abs/2412.16333v1) | Optimizing Fintech Marketing: A Comparative Study of Logistic Regression and XGBoost |
| 2024 | [2410.01843v1](https://arxiv.org/abs/2410.01843v1) | Optimizing Time Series Forecasting: A Comparative Study of Adam and Nesterov Accelerated Gradient on LSTM and GRU networks Using Stock Market data |
| 2024 | [2406.19399v1](https://arxiv.org/abs/2406.19399v1) | Predicting Customer Goals in Financial Institution Services: A Data-Driven LSTM Approach |
| 2024 | [2409.04471v2](https://arxiv.org/abs/2409.04471v2) | Predicting Foreign Exchange EUR/USD direction using machine learning |
| 2024 | [2403.03410v1](https://arxiv.org/abs/2403.03410v1) | Prediction Of Cryptocurrency Prices Using LSTM, SVM And Polynomial Regression |
| 2024 | [2403.00774v2](https://arxiv.org/abs/2403.00774v2) | Regional inflation analysis using social network data |
| 2024 | [2405.11431v2](https://arxiv.org/abs/2405.11431v2) | Review of deep learning models for crypto price prediction: implementation and evaluation |
| 2024 | [2411.11848v1](https://arxiv.org/abs/2411.11848v1) | Robust Graph Neural Networks for Stability Analysis in Dynamic Networks |
| 2024 | [2410.07143v1](https://arxiv.org/abs/2410.07143v1) | SARF: Enhancing Stock Market Prediction with Sentiment-Augmented Random Forest |
| 2024 | [2406.01335v2](https://arxiv.org/abs/2406.01335v2) | Statistics-Informed Parameterized Quantum Circuit via Maximum Entropy Principle for Data Science and Finance |
| 2024 | [2410.07220v1](https://arxiv.org/abs/2410.07220v1) | Stock Price Prediction and Traditional Models: An Approach to Achieve Short-, Medium- and Long-Term Goals |
| 2024 | [2407.18519v1](https://arxiv.org/abs/2407.18519v1) | TCGPN: Temporal-Correlation Graph Pre-trained Network for Stock Forecasting |
| 2024 | [2404.00060v1](https://arxiv.org/abs/2404.00060v1) | Temporal Graph Networks for Graph Anomaly Detection in Financial Networks |
| 2024 | [2411.13562v1](https://arxiv.org/abs/2411.13562v1) | The Role of AI in Financial Forecasting: ChatGPT's Potential and Challenges |
| 2024 | [2407.14573v7](https://arxiv.org/abs/2407.14573v7) | Trading Devil Final: Backdoor attack via Stock market and Bayesian Optimization |
| 2024 | [2406.10719v5](https://arxiv.org/abs/2406.10719v5) | Trading Devil: Robust backdoor attack via Stochastic investment models and Bayesian approach |
| 2024 | [2403.02523v1](https://arxiv.org/abs/2403.02523v1) | Transformer for Times Series: an Application to the S&P500 |
| 2024 | [2402.06638v1](https://arxiv.org/abs/2402.06638v1) | Transformers with Attentive Federated Aggregation for Time Series Stock Forecasting |
| 2024 | [2405.20715v1](https://arxiv.org/abs/2405.20715v1) | Transforming Japan Real Estate |
| 2024 | [2411.05829v1](https://arxiv.org/abs/2411.05829v1) | Utilizing RNN for Real-time Cryptocurrency Price Prediction and Trading Strategy Optimization |
| 2024 | [2403.14483v1](https://arxiv.org/abs/2403.14483v1) | Utilizing the LightGBM Algorithm for Operator User Credit Assessment Research |
| 2024 | [2410.01831v1](https://arxiv.org/abs/2410.01831v1) | Value of Information in the Mean-Square Case and its Application to the Analysis of Financial Time-Series Forecast |
| 2023 | [2311.06280v1](https://arxiv.org/abs/2311.06280v1) | A Data-driven Deep Learning Approach for Bitcoin Price Forecasting |
| 2023 | [2304.09761v1](https://arxiv.org/abs/2304.09761v1) | An innovative Deep Learning Based Approach for Accurate Agricultural Crop Price Prediction |
| 2023 | [2311.10719v1](https://arxiv.org/abs/2311.10719v1) | Analysis of frequent trading effects of various machine learning models |
| 2023 | [2303.09397v1](https://arxiv.org/abs/2303.09397v1) | Cryptocurrency Price Prediction using Twitter Sentiment Analysis |
| 2023 | [2302.08911v1](https://arxiv.org/abs/2302.08911v1) | DSE Stock Price Prediction using Hidden Markov Model |
| 2023 | [2305.04811v2](https://arxiv.org/abs/2305.04811v2) | Deep learning models for price forecasting of financial time series: A review of recent advancements: 2020-2022 |
| 2023 | [2310.16845v1](https://arxiv.org/abs/2310.16845v1) | Dual-Class Stocks: Can They Serve as Effective Predictors? |
| 2023 | [2311.07597v2](https://arxiv.org/abs/2311.07597v2) | Enhancing Actuarial Non-Life Pricing Models via Transformers |
| 2023 | [2303.16149v1](https://arxiv.org/abs/2303.16149v1) | Explaining Exchange Rate Forecasts with Macroeconomic Fundamentals Using Interpretive Machine Learning |
| 2023 | [2302.13850v1](https://arxiv.org/abs/2302.13850v1) | Exploring the Advantages of Transformers for High-Frequency Trading |
| 2023 | [2302.12118v1](https://arxiv.org/abs/2302.12118v1) | Financial Distress Prediction For Small And Medium Enterprises Using Machine Learning Techniques |
| 2023 | [2306.12965v2](https://arxiv.org/abs/2306.12965v2) | Improved Financial Forecasting via Quantum Machine Learning |
| 2023 | [2303.09407v1](https://arxiv.org/abs/2303.09407v1) | Improving CNN-base Stock Trading By Considering Data Heterogeneity and Burst |
| 2023 | [2308.16391v2](https://arxiv.org/abs/2308.16391v2) | Improving the Accuracy of Transaction-Based Ponzi Detection on Ethereum |
| 2023 | [2308.06935v1](https://arxiv.org/abs/2308.06935v1) | Insurance pricing on price comparison websites via reinforcement learning |
| 2023 | [2301.10166v1](https://arxiv.org/abs/2301.10166v1) | Leveraging Vision-Language Models for Granular Market Change Prediction |
| 2023 | [2303.07393v4](https://arxiv.org/abs/2303.07393v4) | Many learning agents interacting with an agent-based market model |
| 2023 | [2308.02491v1](https://arxiv.org/abs/2308.02491v1) | Mapping Global Value Chains at the Product Level |
| 2023 | [2304.03038v1](https://arxiv.org/abs/2304.03038v1) | Modelling customer lifetime-value in the retail banking industry |
| 2023 | [2305.14378v1](https://arxiv.org/abs/2305.14378v1) | Predicting Stock Market Time-Series Data using CNN-LSTM Neural Network Model |
| 2023 | [2308.11939v1](https://arxiv.org/abs/2308.11939v1) | Retail Demand Forecasting: A Comparative Study for Multivariate Time Series |
| 2023 | [2301.10153v1](https://arxiv.org/abs/2301.10153v1) | Sequential Graph Attention Learning for Predicting Dynamic Stock Trends (Student Abstract) |
| 2023 | [2307.09767v1](https://arxiv.org/abs/2307.09767v1) | Sig-Splines: universal approximation and convex calibration of time series generative models |
| 2023 | [2302.14164v1](https://arxiv.org/abs/2302.14164v1) | Stock Broad-Index Trend Patterns Learning via Domain Knowledge Informed Generative Network |
| 2023 | [2310.16855v1](https://arxiv.org/abs/2310.16855v1) | Stock Market Directional Bias Prediction Using ML Algorithms |
| 2023 | [2306.12969v1](https://arxiv.org/abs/2306.12969v1) | Stock Price Prediction using Dynamic Neural Networks |
| 2023 | [2303.09323v1](https://arxiv.org/abs/2303.09323v1) | Stock Trend Prediction: A Semantic Segmentation Approach |
| 2023 | [2305.14382v1](https://arxiv.org/abs/2305.14382v1) | Stock and market index prediction using Informer network |
| 2023 | [2301.05693v1](https://arxiv.org/abs/2301.05693v1) | Stock market forecasting using DRAGAN and feature matching |
| 2023 | [2304.02094v1](https://arxiv.org/abs/2304.02094v1) | TM-vector: A Novel Forecasting Approach for Market stock movement with a Rich Representation of Twitter and Market data |
| 2023 | [2305.08740v1](https://arxiv.org/abs/2305.08740v1) | Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction |
| 2023 | [2307.08650v2](https://arxiv.org/abs/2307.08650v2) | Thailand Asset Value Estimation Using Aerial or Satellite Imagery |
| 2023 | [2311.06292v1](https://arxiv.org/abs/2311.06292v1) | Towards a data-driven debt collection strategy based on an advanced machine learning framework |
| 2022 | [2203.06848v1](https://arxiv.org/abs/2203.06848v1) | A Comparative Study on Forecasting of Retail Sales |
| 2022 | [2209.00858v1](https://arxiv.org/abs/2209.00858v1) | A Discussion of Discrimination and Fairness in Insurance Pricing |
| 2022 | [2201.12286v1](https://arxiv.org/abs/2201.12286v1) | A Stock Trading System for a Medium Volatile Asset using Multi Layer Perceptron |
| 2022 | [2205.01094v3](https://arxiv.org/abs/2205.01094v3) | A Word is Worth A Thousand Dollars: Adversarial Attack on Tweets Fools Stock Predictions |
| 2022 | [2212.05912v1](https://arxiv.org/abs/2212.05912v1) | A machine learning approach to support decision in insider trading detection |
| 2022 | [2207.02799v1](https://arxiv.org/abs/2207.02799v1) | A multi-task network approach for calculating discrimination-free insurance prices |
| 2022 | [2209.09548v1](https://arxiv.org/abs/2209.09548v1) | An Attention Free Long Short-Term Memory for Time Series Forecasting |
| 2022 | [2208.14385v2](https://arxiv.org/abs/2208.14385v2) | Application of Convolutional Neural Networks with Quasi-Reversibility Method Results for Option Forecasting |
| 2022 | [2204.02623v2](https://arxiv.org/abs/2204.02623v2) | Attention-based CNN-LSTM and XGBoost hybrid model for stock prediction |
| 2022 | [2207.11577v1](https://arxiv.org/abs/2207.11577v1) | Augmented Bilinear Network for Incremental Multi-Stock Time-Series Classification |
| 2022 | [2206.13860v2](https://arxiv.org/abs/2206.13860v2) | Detection and Forecasting of Extreme event in Stock Price Triggered by Fundamental, Technical, and External Factors |
| 2022 | [2201.07220v1](https://arxiv.org/abs/2201.07220v1) | Do not rug on me: Zero-dimensional Scam Detection |
| 2022 | [2204.00883v1](https://arxiv.org/abs/2204.00883v1) | Electricity Price Forecasting: The Dawn of Machine Learning |
| 2022 | [2210.00876v1](https://arxiv.org/abs/2210.00876v1) | Embedding-based neural network for investment return prediction |
| 2022 | [2209.12664v1](https://arxiv.org/abs/2209.12664v1) | Feature-Rich Long-term Bitcoin Trading Assistant |
| 2022 | [2204.11735v1](https://arxiv.org/abs/2204.11735v1) | Forecasting Electricity Prices |
| 2022 | [2204.12914v3](https://arxiv.org/abs/2204.12914v3) | Forecasting foreign exchange rates with regression networks tuned by Bayesian optimization |
| 2022 | [2203.15470v1](https://arxiv.org/abs/2203.15470v1) | Graph similarity learning for change-point detection in dynamic networks |
| 2022 | [2211.00948v2](https://arxiv.org/abs/2211.00948v2) | Inflexible Multi-Asset Hedging of incomplete market |
| 2022 | [2203.10465v4](https://arxiv.org/abs/2203.10465v4) | Inspection-L: Self-Supervised GNN Node Embeddings for Money Laundering Detection in Bitcoin |
| 2022 | [2201.08218v1](https://arxiv.org/abs/2201.08218v1) | Long Short-Term Memory Neural Network for Financial Time Series |
| 2022 | [2203.01738v1](https://arxiv.org/abs/2203.01738v1) | Machine learning model to project the impact of Ukraine crisis |
| 2022 | [2204.12932v1](https://arxiv.org/abs/2204.12932v1) | NFT Appraisal Prediction: Utilizing Search Trends, Public Market Data, Linear Regression and Recurrent Neural Networks |
| 2022 | [2209.02407v1](https://arxiv.org/abs/2209.02407v1) | Predict stock prices with ARIMA and LSTM |
| 2022 | [2209.09649v3](https://arxiv.org/abs/2209.09649v3) | Predicting Mutual Funds' Performance using Deep Learning and Ensemble Techniques |
| 2022 | [2210.14605v2](https://arxiv.org/abs/2210.14605v2) | Predicting the State of Synchronization of Financial Time Series using Cross Recurrence Plots |
| 2022 | [2204.06109v1](https://arxiv.org/abs/2204.06109v1) | Prediction of motor insurance claims occurrence as an imbalanced machine learning problem |
| 2022 | [2204.09568v1](https://arxiv.org/abs/2204.09568v1) | Predictive Accuracy of a Hybrid Generalized Long Memory Model for Short Term Electricity Price Forecasting |
| 2022 | [2205.11439v1](https://arxiv.org/abs/2205.11439v1) | Probabilistic forecasting of German electricity imbalance prices |
| 2022 | [2209.09157v1](https://arxiv.org/abs/2209.09157v1) | RESHAPE: Explaining Accounting Anomalies in Financial Statement Audits by enhancing SHapley Additive exPlanations |
| 2022 | [2206.00568v1](https://arxiv.org/abs/2206.00568v1) | RMT-Net: Reject-aware Multi-Task Network for Modeling Missing-not-at-random Data in Financial Credit Scoring |
| 2022 | [2209.01378v3](https://arxiv.org/abs/2209.01378v3) | RNN(p) for Power Consumption Forecasting |
| 2022 | [2205.06675v1](https://arxiv.org/abs/2205.06675v1) | Research on the correlation between text emotion mining and stock market based on deep learning |
| 2022 | [2206.06026v1](https://arxiv.org/abs/2206.06026v1) | Robust Knockoffs for Controlling False Discoveries With an Application to Bond Recovery Rates |
| 2022 | [2204.12929v2](https://arxiv.org/abs/2204.12929v2) | Sequence-Based Target Coin Prediction for Cryptocurrency Pump-and-Dump |
| 2022 | [2201.12291v1](https://arxiv.org/abs/2201.12291v1) | Simulating Using Deep Learning The World Trade Forecasting of Export-Import Exchange Rate Convergence Factor During COVID-19 |
| 2022 | [2207.00493v1](https://arxiv.org/abs/2207.00493v1) | Simulating financial time series using attention |
| 2022 | [2208.13564v1](https://arxiv.org/abs/2208.13564v1) | Stock Market Prediction using Natural Language Processing -- A Survey |
| 2022 | [2204.05783v1](https://arxiv.org/abs/2204.05783v1) | Stock Price Prediction using Sentiment Analysis and Deep Learning for Indian Markets |
| 2022 | [2207.06605v2](https://arxiv.org/abs/2207.06605v2) | StockBot: Using LSTMs to Predict Stock Prices |
| 2022 | [2207.04368v2](https://arxiv.org/abs/2207.04368v2) | Supervised similarity learning for corporate bonds using Random Forest proximities |
| 2022 | [2208.07254v1](https://arxiv.org/abs/2208.07254v1) | The Efficient Market Hypothesis for Bitcoin in the context of neural networks |
| 2022 | [2201.00350v5](https://arxiv.org/abs/2201.00350v5) | The Interpretability of LSTM Models for Predicting Oil Company Stocks: Impact of Correlated Features |
| 2022 | [2204.03760v1](https://arxiv.org/abs/2204.03760v1) | The market drives ETFs or ETFs the market: causality without Granger |
| 2022 | [2212.05369v1](https://arxiv.org/abs/2212.05369v1) | Time Series Analysis in American Stock Market Recovering in Post COVID-19 Pandemic Period |
| 2022 | [2208.08300v1](https://arxiv.org/abs/2208.08300v1) | Transformer-Based Deep Learning Model for Stock Price Prediction: A Case Study on Bangladesh Stock Market |
| 2022 | [2207.06273v1](https://arxiv.org/abs/2207.06273v1) | Understanding Unfairness in Fraud Detection through Model and Data Bias Interactions |
| 2022 | [2205.06673v1](https://arxiv.org/abs/2205.06673v1) | Univariate and Multivariate LSTM Model for Short-Term Stock Market Prediction |
| 2021 | [2111.08060v1](https://arxiv.org/abs/2111.08060v1) | A Multi-criteria Approach to Evolve Sparse Neural Architectures for Stock Market Forecasting |
| 2021 | [2111.15367v2](https://arxiv.org/abs/2111.15367v2) | A Review on Graph Neural Network Methods in Financial Applications |
| 2021 | [2103.09750v1](https://arxiv.org/abs/2103.09750v1) | A Survey of Forex and Stock Price Prediction Using Deep Learning |
| 2021 | [2104.07469v1](https://arxiv.org/abs/2104.07469v1) | A comparative study of Different Machine Learning Regressors For Stock Market Prediction |
| 2021 | [2103.15096v1](https://arxiv.org/abs/2103.15096v1) | Accurate Stock Price Forecasting Using Robust and Optimized Deep Learning Models |
| 2021 | [2106.08361v1](https://arxiv.org/abs/2106.08361v1) | Adversarial Attacks on Deep Models for Financial Transaction Records |
| 2021 | [2111.15354v1](https://arxiv.org/abs/2111.15354v1) | An Improved Reinforcement Learning Model Based on Sentiment Analysis |
| 2021 | [2110.12000v3](https://arxiv.org/abs/2110.12000v3) | Bank transactions embeddings help to uncover current macroeconomics |
| 2021 | [2109.00983v1](https://arxiv.org/abs/2109.00983v1) | Bilinear Input Normalization for Neural Networks in Financial Forecasting |
| 2021 | [2104.04041v1](https://arxiv.org/abs/2104.04041v1) | CLVSA: A Convolutional LSTM Based Variational Sequence-to-Sequence Model with Attention for Predicting Trends of Financial Markets |
| 2021 | [2101.02287v2](https://arxiv.org/abs/2101.02287v2) | COVID19-HPSMP: COVID-19 Adopted Hybrid and Parallel Deep Information Fusion Framework for Stock Price Movement Prediction |
| 2021 | [2102.05448v1](https://arxiv.org/abs/2102.05448v1) | Combination of window-sliding and prediction range method based on LSTM model for predicting cryptocurrency |
| 2021 | [2103.00366v2](https://arxiv.org/abs/2103.00366v2) | Confronting Machine Learning With Financial Research |
| 2021 | [2112.10139v1](https://arxiv.org/abs/2112.10139v1) | Denoised Labels for Financial Time-Series Data via Self-Supervised Learning |
| 2021 | [2106.09664v1](https://arxiv.org/abs/2106.09664v1) | Design and Analysis of Robust Deep Learning Models for Stock Price Prediction |
| 2021 | [2112.03874v2](https://arxiv.org/abs/2112.03874v2) | Efficient Calibration of Multi-Agent Simulation Models from Output Series with Bayesian Optimization |
| 2021 | [2110.12003v1](https://arxiv.org/abs/2110.12003v1) | Embracing advanced AI/ML to help investors achieve success: Vanguard Reinforcement Learning for Financial Goal Planning |
| 2021 | [2105.10871v1](https://arxiv.org/abs/2105.10871v1) | Financial Time Series Analysis and Forecasting with HHT Feature Generation and Machine Learning |
| 2021 | [2101.03087v2](https://arxiv.org/abs/2101.03087v2) | Forecasting Commodity Prices Using Long Short-Term Memory Neural Networks |
| 2021 | [2103.14080v1](https://arxiv.org/abs/2103.14080v1) | Forecasting with Deep Learning: S&P 500 index |
| 2021 | [2112.03946v1](https://arxiv.org/abs/2112.03946v1) | Generative Adversarial Network (GAN) and Enhanced Root Mean Square Error (ERMSE): Deep Learning for Stock Price Movement Prediction |
| 2021 | [2111.15356v1](https://arxiv.org/abs/2111.15356v1) | Improved Method of Stock Trading under Reinforcement Learning Based on DRQN and Sentiment Indicators ARBR |
| 2021 | [2103.11706v1](https://arxiv.org/abs/2103.11706v1) | Interpreting Deep Learning Models with Marginal Attribution by Conditioning on Quantiles |
| 2021 | [2107.05592v1](https://arxiv.org/abs/2107.05592v1) | Investor Behavior Modeling by Analyzing Financial Advisor Notes: A Machine Learning Perspective |
| 2021 | [2111.06631v1](https://arxiv.org/abs/2111.06631v1) | Joint Models for Cause-of-Death Mortality in Multiple Populations |
| 2021 | [2107.11059v1](https://arxiv.org/abs/2107.11059v1) | LocalGLMnet: interpretable deep learning for tabular data |
| 2021 | [2110.11999v1](https://arxiv.org/abs/2110.11999v1) | Machine Learning in Finance-Emerging Trends and Challenges |
| 2021 | [2106.00647v4](https://arxiv.org/abs/2106.00647v4) | Mapping the NFT revolution: market trends, trade networks and visual features |
| 2021 | [2107.03926v1](https://arxiv.org/abs/2107.03926v1) | Measuring Financial Time Series Similarity With a View to Identifying Profitable Stock Market Opportunities |
| 2021 | [2107.01017v1](https://arxiv.org/abs/2107.01017v1) | MegazordNet: combining statistical and machine learning standpoints for time series forecasting |
| 2021 | [2106.12961v1](https://arxiv.org/abs/2106.12961v1) | Next-Day Bitcoin Price Forecast Based on Artificial intelligence Methods |
| 2021 | [2110.02206v1](https://arxiv.org/abs/2110.02206v1) | Predicting Credit Risk for Unsecured Lending: A Machine Learning Approach |
| 2021 | [2111.15355v1](https://arxiv.org/abs/2111.15355v1) | Prediction of Fund Net Value Based on ARIMA-LSTM Hybrid Model |
| 2021 | [2108.10065v1](https://arxiv.org/abs/2108.10065v1) | Previsão dos preços de abertura, mínima e máxima de índices de mercados financeiros usando a associação de redes neurais LSTM |
| 2021 | [2106.02522v5](https://arxiv.org/abs/2106.02522v5) | Price graphs: Utilizing the structural information of financial time series for stock prediction |
| 2021 | [2104.06259v1](https://arxiv.org/abs/2104.06259v1) | Profitability Analysis in Stock Investment Using an LSTM-Based Deep Learning Model |
| 2021 | [2103.14081v1](https://arxiv.org/abs/2103.14081v1) | Stock price forecast with deep learning |
| 2021 | [2112.02365v2](https://arxiv.org/abs/2112.02365v2) | TransBoost: A Boosting-Tree Kernel Transfer Learning Algorithm for Improving Financial Inclusion |
| 2021 | [2107.01273v2](https://arxiv.org/abs/2107.01273v2) | Visual Time Series Forecasting: An Image-driven Approach |
| 2021 | [2102.04861v1](https://arxiv.org/abs/2102.04861v1) | Wavelet Denoised-ResNet CNN and LightGBM Method to Predict Forex Rate of Change |
| 2021 | [2109.01214v1](https://arxiv.org/abs/2109.01214v1) | What drives bitcoin? An approach from continuous local transfer entropy and deep learning classification models |
| 2020 | [2008.09667v1](https://arxiv.org/abs/2008.09667v1) | A Blockchain Transaction Graph based Machine Learning Method for Bitcoin Price Prediction |
| 2020 | [2004.11697v2](https://arxiv.org/abs/2004.11697v2) | A Time Series Analysis-Based Stock Price Prediction Using Machine Learning and Deep Learning Models |
| 2020 | [2001.03333v1](https://arxiv.org/abs/2001.03333v1) | A new approach for trading based on Long Short Term Memory technique |
| 2020 | [2002.09565v4](https://arxiv.org/abs/2002.09565v4) | Adversarial Attacks on Machine Learning Systems for High-Frequency Trading |
| 2020 | [2006.03686v1](https://arxiv.org/abs/2006.03686v1) | Adversarial Robustness of Deep Convolutional Candlestick Learner |
| 2020 | [2003.01859v1](https://arxiv.org/abs/2003.01859v1) | Applications of deep learning in stock market prediction: recent progress |
| 2020 | [2004.01509v1](https://arxiv.org/abs/2004.01509v1) | Comprehensive Review of Deep Reinforcement Learning Methods and Applications in Economics |
| 2020 | [2005.13005v2](https://arxiv.org/abs/2005.13005v2) | Daily Middle-Term Probabilistic Forecasting of Power Consumption in North-East England |
| 2020 | [2002.06405v1](https://arxiv.org/abs/2002.06405v1) | Deep Learning for Asset Bubbles Detection |
| 2020 | [2002.05786v1](https://arxiv.org/abs/2002.05786v1) | Deep Learning for Financial Applications : A Survey |
| 2020 | [2004.01498v1](https://arxiv.org/abs/2004.01498v1) | Deep Probabilistic Modelling of Price Movements for High-Frequency Trading |
| 2020 | [2004.01497v1](https://arxiv.org/abs/2004.01497v1) | Deep learning for Stock Market Prediction |
| 2020 | [2010.15111v1](https://arxiv.org/abs/2010.15111v1) | Evaluating data augmentation for financial time series classification |
| 2020 | [2004.01502v1](https://arxiv.org/abs/2004.01502v1) | Financial Market Trend Forecasting and Performance Analysis Using LSTM |
| 2020 | [2001.01127v1](https://arxiv.org/abs/2001.01127v1) | Forecasting Bitcoin closing price series using linear regression and neural networks models |
| 2020 | [2002.10247v1](https://arxiv.org/abs/2002.10247v1) | Forecasting Foreign Exchange Rate: A Multivariate Comparative Analysis between Traditional Econometric, Contemporary Machine Learning & Deep Learning Techniques |
| 2020 | [2008.08004v2](https://arxiv.org/abs/2008.08004v2) | Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark |
| 2020 | [2010.08400v1](https://arxiv.org/abs/2010.08400v1) | Hybrid Modelling Approaches for Forecasting Energy Spot Prices in EPEC market |
| 2020 | [2011.01961v1](https://arxiv.org/abs/2011.01961v1) | Insights into Fairness through Trust: Multi-scale Trust Quantification for Financial Deep Learning |
| 2020 | [2009.05636v1](https://arxiv.org/abs/2009.05636v1) | Machine Learning for Temporal Data in Finance: Challenges and Opportunities |
| 2020 | [2007.06848v1](https://arxiv.org/abs/2007.06848v1) | Modeling Financial Time Series using LSTM with Trainable Initial Hidden States |
| 2020 | [2005.04955v3](https://arxiv.org/abs/2005.04955v3) | Multi-Graph Convolutional Network for Relationship-Driven Stock Movement Prediction |
| 2020 | [2008.08006v1](https://arxiv.org/abs/2008.08006v1) | Neural networks in day-ahead electricity price forecasting: Single vs. multiple outputs |
| 2020 | [2011.10300v2](https://arxiv.org/abs/2011.10300v2) | Policy Gradient Methods for the Noisy Linear Quadratic Regulator over a Finite Horizon |
| 2020 | [2002.02011v1](https://arxiv.org/abs/2002.02011v1) | Predicting Bank Loan Default with Extreme Gradient Boosting |
| 2020 | [2011.09137v2](https://arxiv.org/abs/2011.09137v2) | Principal Component Analysis and Factor Analysis for Feature Selection in Credit Rating |
| 2020 | [2006.14510v3](https://arxiv.org/abs/2006.14510v3) | Quantum Computing for Finance: State of the Art and Future Prospects |
| 2020 | [2011.08011v2](https://arxiv.org/abs/2011.08011v2) | Robust Analysis of Stock Price Time Series Using CNN and LSTM-Based Deep Learning Models |
| 2020 | [2008.11788v1](https://arxiv.org/abs/2008.11788v1) | Share Price Prediction of Aerospace Relevant Companies with Recurrent Neural Networks based on PCA |
| 2020 | [2001.09769v1](https://arxiv.org/abs/2001.09769v1) | Stock Price Prediction Using Convolutional Neural Networks on a Multivariate Timeseries |
| 2020 | [2009.10819v1](https://arxiv.org/abs/2009.10819v1) | Stock Price Prediction Using Machine Learning and LSTM-Based Deep Learning Models |
| 2020 | [2002.06878v1](https://arxiv.org/abs/2002.06878v1) | Trimming the Sail: A Second-order Learning Paradigm for Stock Prediction |
| 2020 | [2002.02271v1](https://arxiv.org/abs/2002.02271v1) | Using generative adversarial networks to synthesize artificial financial datasets |
| 2020 | [2003.09723v1](https://arxiv.org/abs/2003.09723v1) | Where do we stand in cryptocurrencies economic research? A survey based on hybrid analysis |
| 2019 | [1910.13969v1](https://arxiv.org/abs/1910.13969v1) | A Classifiers Voting Model for Exit Prediction of Privately Held Companies |
| 2019 | [1901.09143v1](https://arxiv.org/abs/1901.09143v1) | A Study on Neural Network Architecture Applied to the Prediction of Brazilian Stock Returns |
| 2019 | [1912.04009v2](https://arxiv.org/abs/1912.04009v2) | An empirical study of neural networks for trend detection in time series |
| 2019 | [1907.03370v1](https://arxiv.org/abs/1907.03370v1) | Artificial Intelligence Alter Egos: Who benefits from Robo-investing? |
| 2019 | [1909.12063v1](https://arxiv.org/abs/1909.12063v1) | Artificial Intelligence BlockCloud (AIBC) Technical Whitepaper |
| 2019 | [1905.07581v1](https://arxiv.org/abs/1905.07581v1) | Convolutional Feature Extraction and Neural Arithmetic Logic Units for Stock Prediction |
| 2019 | [1908.08036v2](https://arxiv.org/abs/1908.08036v2) | Deep Reinforcement Learning for Foreign Exchange Trading |
| 2019 | [1910.12281v1](https://arxiv.org/abs/1910.12281v1) | Deep convolutional autoencoder for cryptocurrency market analysis |
| 2019 | [1907.05697v2](https://arxiv.org/abs/1907.05697v2) | Dreaming machine learning: Lipschitz extensions for reinforcement learning on financial markets |
| 2019 | [2001.00918v1](https://arxiv.org/abs/2001.00918v1) | Fairness in Multi-agent Reinforcement Learning for Stock Trading |
| 2019 | [1902.10877v1](https://arxiv.org/abs/1902.10877v1) | Financial series prediction using Attention LSTM |
| 2019 | [1904.11145v1](https://arxiv.org/abs/1904.11145v1) | Forecasting in Big Data Environments: an Adaptable and Automated Shrinkage Estimation of Neural Networks (AAShNet) |
| 2019 | [1902.10948v1](https://arxiv.org/abs/1902.10948v1) | Global Stock Market Prediction Based on Stock Chart Images Using Deep Q-Network |
| 2019 | [1909.09563v1](https://arxiv.org/abs/1909.09563v1) | Gradient Boost with Convolution Neural Network for Stock Forecast |
| 2019 | [1902.03125v2](https://arxiv.org/abs/1902.03125v2) | High-performance stock index trading: making effective use of a deep LSTM neural network |
| 2019 | [1904.09214v1](https://arxiv.org/abs/1904.09214v1) | Inefficiency of the Brazilian Stock Market: the IBOVESPA Future Contracts |
| 2019 | [1906.06248v3](https://arxiv.org/abs/1906.06248v3) | Machine Learning on EPEX Order Books: Insights and Forecasts |
| 2019 | [1910.10099v1](https://arxiv.org/abs/1910.10099v1) | Mesoscale impact of trader psychology on stock markets: a multi-agent AI approach |
| 2019 | [1906.10121v3](https://arxiv.org/abs/1906.10121v3) | Metaheuristics optimized feedforward neural networks for efficient stock price prediction |
| 2019 | [1905.08444v1](https://arxiv.org/abs/1905.08444v1) | Predicting and Forecasting the Price of Constituents and Index of Cryptocurrency Using Machine Learning |
| 2019 | [1912.04015v2](https://arxiv.org/abs/1912.04015v2) | Sanction or Financial Crisis? An Artificial Neural Network-Based Approach to model the impact of oil price volatility on Stock and industry indices |
| 2019 | [1908.11212v1](https://arxiv.org/abs/1908.11212v1) | Stock Price Forecasting and Hypothesis Testing Using Neural Networks |
| 2019 | [1906.03232v2](https://arxiv.org/abs/1906.03232v2) | Style Transfer with Time Series: Generating Synthetic Financial Data |
| 2019 | [1909.03808v1](https://arxiv.org/abs/1909.03808v1) | Systemic Risk Clustering of China Internet Financial Based on t-SNE Machine Learning Algorithm |
| 2019 | [1909.08964v1](https://arxiv.org/abs/1909.08964v1) | To Detect Irregular Trade Behaviors In Stock Market By Using Graph Based Ranking Methods |
| 2019 | [1909.12946v2](https://arxiv.org/abs/1909.12946v2) | Towards Federated Graph Learning for Collaborative Financial Crimes Detection |
| 2019 | [1903.12258v1](https://arxiv.org/abs/1903.12258v1) | Using Deep Learning Neural Networks and Candlestick Chart Representation to Predict Stock Market |
| 2019 | [1909.10801v1](https://arxiv.org/abs/1909.10801v1) | WATTNet: Learning to Trade FX via Hierarchical Spatio-Temporal Representation of Highly Multivariate Time Series |
| 2019 | [1902.08938v1](https://arxiv.org/abs/1902.08938v1) | Working Paper: Improved Stock Price Forecasting Algorithm based on Feature-weighed Support Vector Regression by using Grey Correlation Degree |
| 2018 | [1801.00681v1](https://arxiv.org/abs/1801.00681v1) | A novel improved fuzzy support vector machine based stock price trend forecast model |
| 2018 | [1802.05326v1](https://arxiv.org/abs/1802.05326v1) | Analysis of Financial Credit Risk Using Machine Learning |
| 2018 | [1805.12111v4](https://arxiv.org/abs/1805.12111v4) | Dynamic Advisor-Based Ensemble (dynABE): Case study in stock trend prediction of critical metal companies |
| 2018 | [1812.11226v2](https://arxiv.org/abs/1812.11226v2) | Fast Training Algorithms for Deep Convolutional Fuzzy Systems with Application to Stock Index Prediction |
| 2018 | [1803.06386v1](https://arxiv.org/abs/1803.06386v1) | Forecasting Economics and Financial Time Series: ARIMA vs. LSTM |
| 2018 | [1805.11317v1](https://arxiv.org/abs/1805.11317v1) | Neural networks for stock price prediction |
| 2018 | [1801.07960v1](https://arxiv.org/abs/1801.07960v1) | Stock returns forecast: an examination by means of Artificial Neural Networks |
| 2017 | [1705.06899v1](https://arxiv.org/abs/1705.06899v1) | CDS Rate Construction Methods by Machine Learning Techniques |
| 2017 | [1707.00757v1](https://arxiv.org/abs/1707.00757v1) | Checking account activity and credit default risk of enterprises: An application of statistical learning methods |
| 2017 | [1706.00948v5](https://arxiv.org/abs/1706.00948v5) | Financial Series Prediction: Comparison Between Precision of Time Series Models and Machine Learning Methods |
| 2017 | [1711.04174v1](https://arxiv.org/abs/1711.04174v1) | Financial Time Series Prediction Using Deep Learning |
| 2017 | [1708.07061v3](https://arxiv.org/abs/1708.07061v3) | Forecasting day-ahead electricity prices in Europe: the importance of considering market integration |
| 2017 | [1705.03396v1](https://arxiv.org/abs/1705.03396v1) | Machine Learning Techniques for Mortality Modeling |
| 2017 | [1705.01142v1](https://arxiv.org/abs/1705.01142v1) | Machine Learning for Better Models for Predicting Bond Prices |
| 2017 | [1707.08504v1](https://arxiv.org/abs/1707.08504v1) | Mutation Clusters from Cancer Exome |
| 2017 | [1709.03943v1](https://arxiv.org/abs/1709.03943v1) | Support Spinor Machine |
| 2016 | [1607.02093v1](https://arxiv.org/abs/1607.02093v1) | Artificial Neural Network and Time Series Modeling Based Approach to Forecasting the Exchange Rate in a Multivariate Framework |
| 2016 | [1607.02470v2](https://arxiv.org/abs/1607.02470v2) | Deep Learning for Mortgage Risk |
| 2016 | [1612.02666v1](https://arxiv.org/abs/1612.02666v1) | Evaluating the Performance of ANN Prediction System at Shanghai Stock Market in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2016 | [1609.05394v1](https://arxiv.org/abs/1609.05394v1) | Predicting Future Shanghai Stock Market Price using ANN in the Period 21-Sep-2016 to 11-Oct-2016 |
| 2015 | [1501.04682v3](https://arxiv.org/abs/1501.04682v3) | Toward robust early-warning models: A horse race, ensembles and model uncertainty |
| 2014 | [1502.06434v1](https://arxiv.org/abs/1502.06434v1) | ANN Model to Predict Stock Prices at Stock Exchange Markets |
| 2013 | [1310.2446v3](https://arxiv.org/abs/1310.2446v3) | A statistical physics perspective on criticality in financial markets |
| 2007 | [physics/0701156v2](https://arxiv.org/abs/physics/0701156v2) | Structurally dynamic spin market networks |
| 2003 | [cond-mat/0304469v1](https://arxiv.org/abs/cond-mat/0304469v1) | Using Recurrent Neural Networks To Forecasting of Forex |

