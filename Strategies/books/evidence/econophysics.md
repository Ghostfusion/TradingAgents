# Evidence pack — Econophysics, Scaling & Agent-Based Models (`econophysics`)

Annotated sweep rows for this category: **985** (high 60 · med 573 · low 352).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (60)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2025 | [2507.23414v1](https://arxiv.org/abs/2507.23414v1) | Multifractal detrended fluctuation analysis and refined composite multiscale sample entropy measure complexity of Bitcoin, GBP/USD, gold and gas returns; Bitcoin shows highest complexity, attributed to stronger nonlinear correlations. | `strategies/complexity.py` |
| 2025 | [2504.01974v1](https://arxiv.org/abs/2504.01974v1) | Applies a binary Complexity-Entropy Plane to daily up/down moves of top cryptocurrencies, defining an inefficiency score; only Shiba Inu is significantly inefficient while most crypto trades near-efficiently, suggesting consensus architecture matters to efficiency. | `strategies/complexity.py` |
| 2025 | [2512.15720v1](https://arxiv.org/abs/2512.15720v1) | Computes order-flow entropy from a 15-state second-resolution Markov matrix on 38.5M SPY trades: low entropy raises 5-minute absolute returns 2.89x while directional accuracy stays chance-level (45%). | `strategies/orderflow.py` |
| 2025 | [2509.19663v3](https://arxiv.org/abs/2509.19663v3) | R/S, DFA, multifractal and ARFIMA-FIGARCH tests find long memory in conditional volatility (not mean returns) across equities, commodities and energy; deep generative models struggle to reproduce it. | `strategies/long_memory.py` |
| 2025 | [2507.22712v2](https://arxiv.org/abs/2507.22712v2) | Applies structural order-lifetime and modification filters to BankNifty limit-order-book imbalance; filtering parent orders of executed trades strengthens OBI-return directional association, while aggregate-flow filtration changes little, per correlation, regime and Hawkes diagnostics. | `strategies/orderflow.py` |
| 2025 | [2507.15437v3](https://arxiv.org/abs/2507.15437v3) | Forecasts linear fractional stable motion increments using codifference-based conditional expectation or semimetric projection; simulation and real volatility data show it outperforms fBm and HAR, revealing a selective-memory regime in rough volatility. | `strategies/long_memory.py` |
| 2023 | [2312.05655v1](https://arxiv.org/abs/2312.05655v1) | Novel scaling framework adjusts risk estimators to long horizons and extreme percentiles, giving robust, conservative capital-reserve estimates. | `strategies/book_risk.py` |
| 2023 | [2305.12632v2](https://arxiv.org/abs/2305.12632v2) | Temporal correlation deforms the Marchenko-Pastur eigenvalue law: longer tail and higher peak, power-decay correlation causing a phase transition. | `strategies/covariance_models.py` |
| 2023 | [2306.13378v3](https://arxiv.org/abs/2306.13378v3) | Generalized Lillo-Mike-Farmer order-splitting model with heterogeneous traders, exactly solved; order-sign autocorrelation power-law exponent is robust to intensity heterogeneity. | `strategies/orderflow.py` |
| 2023 | [2311.04727v2](https://arxiv.org/abs/2311.04727v2) | LSTM trained across a pool of assets beats traditional volatility models; a rough-volatility plus Zumbach model with five non-asset-dependent parameters matches it (crypto-winter). | `strategies/volatility_models.py` |
| 2023 | [2306.13371v1](https://arxiv.org/abs/2306.13371v1) | Links entropy-based market information and the Hurst exponent, deriving expressions under fractional Brownian motion and introducing a multi-scale informativeness method. | `strategies/complexity.py` |
| 2023 | [2312.16190v1](https://arxiv.org/abs/2312.16190v1) | Hawkes-model prediction from limit-order-book data with a continuous output error model forecasts cryptocurrency return signs, beating benchmarks. | `strategies/orderflow.py` |
| 2023 | [2312.16185v1](https://arxiv.org/abs/2312.16185v1) | Uses transfer entropy and convergent cross-mapping with Fourier surrogates to separate linear and nonlinear causality; German and US indices show significant nonlinear causality. | `strategies/statistical.py` |
| 2023 | [2305.08241v1](https://arxiv.org/abs/2305.08241v1) | NYSE one-minute prices fit shot-noise with Hurst 0.465 (slightly mean-reverting), arbitrageable over hours; cross-correlations predictable over years. | `strategies/mean_reversion.py` |
| 2023 | [2308.01486v1](https://arxiv.org/abs/2308.01486v1) | Path Shadowing Monte-Carlo averages future quantities over generated paths matching observed history; a maximum-entropy scattering-spectra model yields state-of-the-art realized-volatility forecasts. | `strategies/volatility_models.py` |
| 2023 | [2312.16637v3](https://arxiv.org/abs/2312.16637v3) | Shannon entropy and KL-based predictability test for ultra-high-frequency data; randomness rises with transaction-time aggregation and predictable days have high volume. | `strategies/complexity.py` |
| 2023 | [2304.11883v1](https://arxiv.org/abs/2304.11883v1) | Recurrent neural network estimates Hawkes model parameters on high-frequency data far faster than MLE with comparable accuracy, enabling real-time volatility. | `strategies/orderflow.py` |
| 2023 | [2312.01426v2](https://arxiv.org/abs/2312.01426v2) | Range-based volatility proxies confirm rough volatility (Hurst below 0.5, even below 0.1) across non-standard assets, refuting a microstructure-noise explanation. | `strategies/volatility_models.py` |
| 2023 | [2312.14903v2](https://arxiv.org/abs/2312.14903v2) | Scalable agent-based market simulation with heterogeneous agents and a continuous double-auction engine reproduces stylized facts without fitting historical data. | `strategies/backtest_engine.py` |
| 2022 | [2209.07092v2](https://arxiv.org/abs/2209.07092v2) | Most-probable-maximum-risk (MPMR) tail measure needs no confidence level; for Pareto sizes it scales as n^eta, giving a robust tail-index estimator xi=1/eta. | strategies/tail_risk.py |
| 2022 | [2203.13820v3](https://arxiv.org/abs/2203.13820v3) | Introduces a non-parametric normalized p-th variation roughness estimator; realized volatility always appears rough (H<0.5) even when spot volatility is Brownian, implicating microstructure noise. | `strategies/volatility_models.py` |
| 2021 | [2110.00771v2](https://arxiv.org/abs/2110.00771v2) | Models the limit order book with state-dependent Hawkes processes to measure one sell metaorder's price impact on NASDAQ data; sell child-order clustering matters more than order sizes. | `strategies/orderflow.py` |
| 2020 | [2011.12291v2](https://arxiv.org/abs/2011.12291v2) | Two-tailed peak-over-threshold Hawkes model finds asymmetric self/cross-excitation in S&P500 extreme gains and losses. | `strategies/tail_risk.py` |
| 2020 | [2009.10764v1](https://arxiv.org/abs/2009.10764v1) | CoVaR estimated with GJR-GARCH volatility clustering, heavy tails, negative skew and copula dependence; quantifies systemic risk. | `strategies/book_risk.py` |
| 2020 | [2012.10875v1](https://arxiv.org/abs/2012.10875v1) | Hawkes modelling of implied-volatility-surface dynamics; kernel coefficients govern skew/convexity, with no-arbitrage parameter conditions. | `strategies/options_surface.py` |
| 2020 | [2001.08442v1](https://arxiv.org/abs/2001.08442v1) | Marked point-process intensity-ratio model for limit order books; outperforms pure Hawkes methods predicting sign and aggressiveness of market orders on Euronext Paris stocks. | strategies/orderflow.py |
| 2020 | [2005.09036v2](https://arxiv.org/abs/2005.09036v2) | Proposes non-extensive (Tsallis-based) Value-at-Risk estimation to correct VaR underestimation in crises, where heavy-tailed non-Gaussian extreme returns inflate probability density. | strategies/book_risk.py |
| 2020 | [2002.04164v3](https://arxiv.org/abs/2002.04164v3) | RNSGHE robustly estimates multiscaling exponents via generalized Hurst exponent plus t/F tests; Monte-Carlo Multiscaling VaR mimics annual VaR for most stocks. | strategies/long_memory.py |
| 2020 | [2004.05894v1](https://arxiv.org/abs/2004.05894v1) | Extreme-value theory on the hidden tail beyond in-sample max: visible mean badly understates true moments for tail index near 1; hidden 0th moment ~ Exponential(mean 1/n). | strategies/tail_risk.py |
| 2019 | [1909.08308v1](https://arxiv.org/abs/1909.08308v1) | Models limit-order arrival and cancellation rates near best bid/ask in Borsa Istanbul; tests Geometric, Beta-Binomial, Discrete Weibull, Exponential and Power-law fits on 15 levels. | strategies/orderflow.py |
| 2019 | [1901.02419v5](https://arxiv.org/abs/1901.02419v5) | Models conditionally log-Laplace stochastic volatility with analytic conditional structure to give dynamic Pareto-tailed extreme event probabilities in heavy-tailed, nonlinearly dependent series. | `strategies/tail_risk.py` |
| 2019 | [1906.05420v1](https://arxiv.org/abs/1906.05420v1) | Builds a general nonlinear order-book model from individual agent behaviours (Markovian and Hawkes), proving ergodicity/diffusivity and giving closed-form spread, liquidity, volatility and a market-maker ranking methodology. | `strategies/orderflow.py` |
| 2019 | [1907.09452v1](https://arxiv.org/abs/1907.09452v1) | Extracts 270+ hand-crafted technical/quantitative features for short-term mid-price movement; wrapper selection (entropy, LMS, LDA) plus an adaptive logistic-regression feature reaches best performance with few features on Nasdaq Nordic LOB data. | strategies/technical_factors.py |
| 2019 | [1908.05089v1](https://arxiv.org/abs/1908.05089v1) | Studies the symmetric Hawkes price-tick model with MLE for ultra-high-frequency volatility estimation on S&P 500 stocks; proposes a diffusion analogy with analytical variance/skewness matching the Hawkes model. | strategies/volatility_models.py |
| 2019 | [1908.00257v2](https://arxiv.org/abs/1908.00257v2) | Defines cluster entropy S(tau,n) between price and moving average, integrated into a Market Dynamic Index; high-frequency index data shows systematic horizon dependence matching pricing-kernel horizon dependence and fBm series. | strategies/complexity.py |
| 2018 | [1812.07369v1](https://arxiv.org/abs/1812.07369v1) | Studies bid-ask spread evolution through the trading day for NASDAQ stocks; rescaled spreads collapse to a slow power-law decline after a volatile open, with large-tick stocks closing to one tick. | `strategies/market_session.py` |
| 2018 | [1802.08502v5](https://arxiv.org/abs/1802.08502v5) | Metaorder database shows power-law temporary market impact for aggressive and passive limit orders; long-term impact stabilizes near two-thirds of maximum and fair pricing holds. | `strategies/execution_schedule.py` |
| 2018 | [1809.08060v3](https://arxiv.org/abs/1809.08060v3) | State-dependent Hawkes processes couple self/cross-exciting order flow to a state process; applied to LOB data, excitation and order-flow endogeneity are strongly state-dependent and higher in disequilibrium. | `strategies/orderflow.py` |
| 2016 | [1607.05831v3](https://arxiv.org/abs/1607.05831v3) | Doubly stochastic self-exciting Hawkes process with time-varying exponential kernel; non-naive bias-corrected estimator with CLT for high-frequency asymptotics. | `strategies/orderflow.py` |
| 2015 | [1501.01155v1](https://arxiv.org/abs/1501.01155v1) | Entropy as a risk measure explains the equity premium better than CAPM beta; efficient portfolios lie on a return-entropy hyperbola (150 securities, 27 years). | `strategies/portfolio_optimizer.py` |
| 2014 | [1403.5227v3](https://arxiv.org/abs/1403.5227v3) | Model-independent branching-ratio approximation for Hawkes processes needs only mean and variance of event counts; a cheap market-endogeneity proxy. | strategies/orderflow.py |
| 2014 | [1412.7096v1](https://arxiv.org/abs/1412.7096v1) | Non-parametric Hawkes kernel estimation adapted to slowly decreasing kernels recovers power-law kernels over six decades; 8-D model of level-1 order-book events. | `strategies/orderflow.py` |
| 2014 | [1410.3394v1](https://arxiv.org/abs/1410.3394v1) | Log-volatility behaves as fractional Brownian motion with Hurst exponent ~0.1 (rough FSV model), improving volatility forecasts from HF data. | strategies/volatility_models.py |
| 2013 | [1302.1405v2](https://arxiv.org/abs/1302.1405v2) | Hawkes self-exciting fit to E-Mini S&P mid-price changes gives a two-regime power-law kernel (exponents -1.15 and -1.45) that integrates to unity 1998-2011, implying markets stay near criticality. | `strategies/orderflow.py` |
| 2012 | [1205.0505v1](https://arxiv.org/abs/1205.0505v1) | Profit landscape of a two-parameter (p,q) fluctuation strategy is fractal, so optimization is hypersensitive and out-of-sample tuning loses to buy-and-hold. | `strategies/config_robustness.py` |
| 2012 | [1210.6321v4](https://arxiv.org/abs/1210.6321v4) | Topic modeling plus regularized regressions on 24M news records and 206 S&P stocks shows news flow explains abnormally large trading volumes, removing apparent "excess trading". | `strategies/news_relevance.py` |
| 2012 | [1204.3136v3](https://arxiv.org/abs/1204.3136v3) | A thermodynamic multifractal partition-function index (normalized energy variation) identifies 1929, 1987 and 2008 crashes in real time and shows forecasting capability. | `strategies/regime.py` |
| 2012 | [1201.3572v2](https://arxiv.org/abs/1201.3572v2) | Hawkes self-excited calibration of E-mini S&P 500 futures 1998-2010 measures endogeneity: the exogenous share of price changes fell from 70% in 1998 to under 30% since 2007. | `strategies/orderflow.py` |
| 2011 | [1102.4819v2](https://arxiv.org/abs/1102.4819v2) | Generalizes ARCH into a two-regime process with threshold-triggered memory of past high-volatility values; yields fat-tailed densities and instantaneous-variance Hurst exponent above 0.8. | strategies/volatility_models.py |
| 2011 | [1103.5649v1](https://arxiv.org/abs/1103.5649v1) | Builds unconditional and conditional VaR for twelve European index futures using Extreme Value Theory with GARCH-filtered returns and a multi-period scaling law; normality biases in unconditional estimates extend to the conditional setting. | strategies/book_risk.py |
| 2010 | [1003.0168v1](https://arxiv.org/abs/1003.0168v1) | Ultra-high-frequency Shenzhen order flow around extreme price changes: price reverses with permanent impact; volatility, order volumes, spread and imbalance peak then decay power-law, with buy/sell market-order timing asymmetries. | strategies/orderflow.py |
| 2009 | [0903.0993v1](https://arxiv.org/abs/0903.0993v1) | NYSE 2215 stocks: overnight and daytime returns share total-return properties, volatility tails are power-law with long memory while returns are uncorrelated, and daytime drives the total return. | `strategies/market_session.py` |
| 2009 | [0906.5249v1](https://arxiv.org/abs/0906.5249v1) | Applies random-matrix theory to financial covariance matrices; smallest eigenvalues/spacings match Tracy-Widom and Wigner surmise robustly under reshuffling, supporting RMT cleaning for portfolio selection. | strategies/covariance_models.py |
| 2008 | [0804.3818v2](https://arxiv.org/abs/0804.3818v2) | Develops a quantitative theory of market impact for hidden orders reproducing the concave impact and universal return properties, assuming order flow translates into an uncorrelated price stream. | `strategies/execution_schedule.py` |
| 2006 | [physics/0601174v2](https://arxiv.org/abs/physics/0601174v2) | DFA finds no long-term memory in returns but strong long memory in volatility; AR(1) filtering leaves it unchanged, GARCH(1,1) filtering diminishes it, attributing long memory to volatility clustering. | `strategies/long_memory.py` |
| 2005 | [physics/0506101v1](https://arxiv.org/abs/physics/0506101v1) | Heston stochastic-volatility model with at least two volatility mean-reversion timescales fits IBOVESPA fluctuations from >20 minutes to 160 days; sub-20-minute returns are autocorrelated with power-law tails. | `strategies/volatility_models.py` |
| 2004 | [math/0412344v1](https://arxiv.org/abs/math/0412344v1) | Local Hurst exponent applied to high-frequency AUD/USD shows intraday dependence and volatility vary across the 24-hour day, aligning with market openings/closings; variation attributed to liquidity and dealer price discovery. | `strategies/long_memory.py` |
| 2003 | [cond-mat/0312643v1](https://arxiv.org/abs/cond-mat/0312643v1) | RMT on Tokyo TSE correlations: randomness repels deterministic and random eigenvalues, refining detection of correlated stock groups. | strategies/covariance_models.py |
| 2003 | [cond-mat/0311053v2](https://arxiv.org/abs/cond-mat/0311053v2) | LSE order signs are long-memory (ACF ~ tau^-0.6, Hurst ~0.7) yet anti-correlated transaction size and liquidity whiten returns; some institutions show long memory. | strategies/orderflow.py |
| 1999 | [cond-mat/9911168v1](https://arxiv.org/abs/cond-mat/9911168v1) | DAX 30 rolling correlation matrix: drawdowns coincide with separation of one strong collective eigenstate and reduced noise-state variance; drawups spread eigenstates. | strategies/eigen_rotation.py |

## Medium relevance (100) (showing the 100 most recent of 573)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2606.27932v1](https://arxiv.org/abs/2606.27932v1) | A Grünwald-Letnikov fractional-derivative KS framework removes the long-memory singularity to estimate Hurst exponents consistently; applied to realized volatility and equity indices it detects rough volatility and persistent, anti-persistent or efficient market states. | strategies/long_memory.py |
| 2026 | [2606.15755v1](https://arxiv.org/abs/2606.15755v1) | Multiplex Network Hawkes model with covariate-dependent excitation layers infers contagion from 99 firms' CDS (2004-2022); contagion is sparse, concentrated in outward flows from few institutions, with industry similarity the most supported channel. | strategies/triadic_stress.py |
| 2026 | [2601.23172v2](https://arxiv.org/abs/2601.23172v2) | Hawkes core/reaction-flow model with a scaling limit: signed flow Hurst H0, volume rough H0-1/2, volatility rough 2H0-3/2, power-law impact exponent 2-2H0; estimated H0 approx 3/4 matches the square-root law. | `strategies/orderflow.py` |
| 2026 | [2608.26128v1](https://arxiv.org/abs/2608.26128v1) | Econophysics thesis clusters spectral quantities of 430-stock S&P 500 correlation matrices into Market States; COVID-19 emerges atypical, needing C^2/C^3 reconstructions, with participation spreading during crises. | strategies/covariance_models.py |
| 2026 | [2601.12990v1](https://arxiv.org/abs/2601.12990v1) | SFAG GAN converts stylized facts (asymmetry, tails) into differentiable constraints jointly optimized with adversarial loss; on Shanghai Composite, baseline GANs collapse in backtests while SFAG supports robust momentum strategies. | `strategies/backtest_engine.py` |
| 2026 | [2607.26188v1](https://arxiv.org/abs/2607.26188v1) | Bitcoin cycle indicators degraded from precise to early to silent across four halvings because oscillator extremes compress; only the fixed halving clock, with tops ~525-546 days post-halving, stays stable. | strategies/catalyst.py |
| 2026 | [2606.23492v1](https://arxiv.org/abs/2606.23492v1) | Continuous hidden Markov model with heavy-tailed emissions (Gaussian, Student-t, Laplace, generalized error) separates regime autocorrelation from marginal shape; on U.S. equities heavy-tailed marginals close most of the fit gap, recovering volatility clustering and reducing kurtosis. | strategies/regime_state.py |
| 2026 | [2604.26811v2](https://arxiv.org/abs/2604.26811v2) | Network-based transfer entropy compares news vs social-media sentiment spillover across tech firms; news information flow intensified post-COVID; identifies information-hub companies. | strategies/sentiment_research.py |
| 2026 | [2606.24019v1](https://arxiv.org/abs/2606.24019v1) | Reconstructs metaorders from anonymous Nasdaq ITCH data (178 days) and confirms the square-root law of market impact for AAPL: exponent 1/2, prefactor c_raw=0.69, beating linear/log forms; impact collapses under sign shuffling and time scrambling. | strategies/execution_schedule.py |
| 2026 | [2603.12040v1](https://arxiv.org/abs/2603.12040v1) | Information-theoretic study of major indices during Trump's 2025 first 100 days; standard deviation and sliding-window entropy decouple, so entropy reflects diversity of outcomes rather than amplitude. | `strategies/complexity.py` |
| 2026 | [2608.22864v1](https://arxiv.org/abs/2608.22864v1) | Reformulates the Bayesian filter for Markov-Switching-Multifractal volatility using likelihood permutation symmetry, cutting complexity from O(D^k) to O(k^D) and improving ground-truth recovery. | strategies/volatility_models.py |
| 2026 | [2601.10517v2](https://arxiv.org/abs/2601.10517v2) | Extends Log S-fBM to a multivariate volatility model (mLog S-fBM) with co-Hurst and co-intermittency matrices; S&P 500 estimates show multifractal behavior and off-diagonal co-Hurst near H≈0.12. | `strategies/volatility_models.py` |
| 2026 | [2605.17117v2](https://arxiv.org/abs/2605.17117v2) | Four geometric observables (Berry phase rate, spectral entropy, state purity, Hamiltonian sensitivity) detect regime shifts across 17 crises; Berry phase d=0.72 with ~67% fewer false alarms than a Random Forest. | strategies/regime_state.py |
| 2026 | [2603.20271v1](https://arxiv.org/abs/2603.20271v1) | Builds transfer-entropy networks from foreign, institutional and individual investor flows across Korean equities (2020-2025); networks are sparse and heterogeneous, assessed via interaction information, conditional TE, Kelly bounds and Fama-MacBeth. | `strategies/orderflow.py` |
| 2026 | [2601.04959v1](https://arxiv.org/abs/2601.04959v1) | Discrete-time Markov chains on NASDAQ100 tick data categorize limit-order price changes into nine states; price inertia peaks at open/close with a market-capitalization gradient, and Jensen-Shannon divergence flags the close as most distinct. | `strategies/execution_schedule.py` |
| 2026 | [2607.06908v1](https://arxiv.org/abs/2607.06908v1) | Iterative global-factor algorithm combines Marcenko-Pastur edge recalibration with participation-ratio delocalization, recovering factor counts near the BBP transition where eigenvalue-only criteria fail; S&P 500 median count 7. | strategies/covariance_models.py |
| 2026 | [2601.17773v1](https://arxiv.org/abs/2601.17773v1) | MarketGAN embeds an asset-pricing factor structure in a TCN-based GAN generating joint return vectors; matches heavy tails, volatility clustering and cross-sectional tail co-movement, and its covariance estimates outperform factor bootstrap. | `strategies/covariance_models.py` |
| 2026 | [2601.11305v1](https://arxiv.org/abs/2601.11305v1) | Two-stage test (WLS multiscaling vs fractional Brownian motion; shuffled surrogates and distance-based permutation) shows rough Bergomi's multiscaling arises from fat-tailed returns, not volatility-path memory. | `strategies/volatility_models.py` |
| 2026 | [2607.27099v1](https://arxiv.org/abs/2607.27099v1) | Models rainfall clustering with critical Hawkes processes and heavy-tailed power-law kernels; aggregated rainfall converges to a rough fractional process with Hurst exponent 0.01-0.1, linking to market-microstructure and volatility models. | strategies/long_memory.py |
| 2026 | [2607.10297v1](https://arxiv.org/abs/2607.10297v1) | Spectral denoising splits correlation matrices into 10-16 structured eigenmodes plus noise; denoised NIFTY/S&P networks show stronger core-periphery structure and periphery portfolios beat unfiltered benchmarks risk-adjusted. | strategies/covariance_models.py |
| 2026 | [2601.08571v1](https://arxiv.org/abs/2601.08571v1) | Hilbert-Huang regime identification plus variable-length Markov modeling on global equity indices finds developed markets normalize after stress while developing markets retain residual tail dependence and downside persistence. | `strategies/regime.py` |
| 2026 | [2609.12227v1](https://arxiv.org/abs/2609.12227v1) | Compares dummy-variable regression, SSA and robust low-rank SSA seasonal commodity-futures models on 15 futures 2016-2024 with costs; the equal-weight benchmark has the strongest profile and no MEB Sharpe test rejects. | strategies/statistical.py |
| 2026 | [2604.19107v1](https://arxiv.org/abs/2604.19107v1) | Random-Matrix-Theory complexity gap (normalized largest eigenvalue minus average pairwise correlation) shows a three-phase G5 pattern across shocks: rich structure before, near-zero synchronization during, and recovery after. | `strategies/covariance_models.py` |
| 2026 | [2602.00073v1](https://arxiv.org/abs/2602.00073v1) | Test-time adaptation updates only normalization affine parameters on a frozen backbone under regime shift; batch-norm statistics update is a robust default for SPY/QQQ/EUR-USD, aggressive norm adaptation can hurt. | `strategies/regime.py` |
| 2026 | [2602.00548v2](https://arxiv.org/abs/2602.00548v2) | Multifractal detrended fluctuation analysis (Hurst h(2), multifractal strength) of six assets shows COVID-19 strongly shifted efficiency and Trump tariffs moderately; VIX anti-persistent h(2)<0.5, consistent with rough volatility. | `strategies/complexity.py` |
| 2026 | [2606.25986v1](https://arxiv.org/abs/2606.25986v1) | Finds an inference-compute power-law frontier in limit order book prediction on FI-2010 (R²=0.941 extrapolation), motivating FastBiNLOB, a dense axis-separable LOB mixer beating published macro-F1 targets at notably lower latency. | strategies/orderflow.py |
| 2026 | [2609.09405v1](https://arxiv.org/abs/2609.09405v1) | Provides statistical analysis of the Log S-fBM stochastic-volatility model, deriving scaling properties, tail-sensitive deviation inequalities, and a hypothesis test distinguishing rough (H near 0.1) from multifractal (H near 0) dynamics. | strategies/volatility_models.py |
| 2026 | [2601.11602v2](https://arxiv.org/abs/2601.11602v2) | Regularized deconvolution plus Hawkes analysis of Korean investor flows: foreign and institutional flows drive permanent price discovery, individual surges are panic-driven, institutional impact deteriorates in small caps when herding. | `strategies/orderflow.py` |
| 2026 | [2608.10852v2](https://arxiv.org/abs/2608.10852v2) | Compares one-minute crypto and E-mini S&P data via complexity-entropy plane and directed visibility graphs; conventional stylized facts overlap but crypto shows weaker ordinal organization and high-degree separation. | strategies/complexity.py |
| 2025 | [2507.09347v1](https://arxiv.org/abs/2507.09347v1) | Clusters nine equities by volatility via GMM, then Granger causality, PCMCI and transfer entropy find lead-lag links; DTW/KNN sets trade lag, backtest returning 15.38% versus 10.39% buy-and-hold. | `strategies/statistical.py` |
| 2025 | [2505.02678v4](https://arxiv.org/abs/2505.02678v4) | Introduces a nested factor model where the dominant log-volatility mode is rough (H~0.11) and idiosyncratic residuals multifractal (H~0), reproducing the stylized fact that index Hurst exponents exceed individual stocks; validated on S&P 500. | `strategies/long_memory.py` |
| 2025 | [2512.03123v1](https://arxiv.org/abs/2512.03123v1) | Imports stochastic thermodynamics to price impact: proves a Financial Second Law where convex impact makes any round-trip strategy's expected profit non-positive, plus a fluctuation theorem bounding profitable-cycle probability. | `strategies/execution_price.py` |
| 2025 | [2501.15596v1](https://arxiv.org/abs/2501.15596v1) | Four-factor commodity model (spot, stochastic volatility, convenience yield, stochastic rates) estimated with a Kalman filter on joint futures term structure and bond yields outperforms established approaches on crude oil. | `strategies/statistical_kalman.py` |
| 2025 | [2507.17431v1](https://arxiv.org/abs/2507.17431v1) | Subordinates Brownian motion under CIR/CKLS stochastic arrivals to build VGSA and generalized jump models; proves strong consistency and asymptotic normality for VG and CGMY, with Monte Carlo confirmation of approximate Gaussian behavior under heavy tails. | `strategies/volatility_models.py` |
| 2025 | [2512.08000v1](https://arxiv.org/abs/2512.08000v1) | Fits self-exciting and inhibitory Hawkes processes to Chinese market and sector index returns, finding long-term dependencies where high-activity sectors sustain trends and low-activity periods show strong sector rotation. | `strategies/triadic_stress.py` |
| 2025 | [2502.15787v1](https://arxiv.org/abs/2502.15787v1) | Event study of the Indian 2024 budget using AAR/CAAR around the announcement versus 2023/2022/2020 NIFTY50; fractal interpolation and dimension analysis frame announcement-induced fluctuations. | `strategies/events.py` |
| 2025 | [2508.16566v1](https://arxiv.org/abs/2508.16566v1) | Bivariate quadratic Hawkes process yields an asymmetric super-rough-Heston scaling limit preserving time-reversal asymmetry (Zumbach effect), with stochastic covariation between drivers in the near-unstable regime. | `strategies/orderflow.py` |
| 2025 | [2505.14655v1](https://arxiv.org/abs/2505.14655v1) | Studies 39 corporate-Bitcoin-holding firms, finding average BTC beta 0.62 (12 firms above 1) and, via transfer entropy, BTC as dominant information driver, implying hedging ratios must adapt dynamically to shifting information flows. | `strategies/covariance_models.py` |
| 2025 | [2508.07192v2](https://arxiv.org/abs/2508.07192v2) | Uses Wigner-type random matrices from correlated financial series; derives a deformed semicircle law, fourth moment growing with correlation strength and a moment phase transition under power-law decay. | `strategies/eigen_rotation.py` |
| 2025 | [2512.06473v1](https://arxiv.org/abs/2512.06473v1) | Builds multifractal detrended cross-correlation matrices ρ_r for 140 cryptocurrencies (2021-2024); detrending, heavy tails and fluctuation order jointly shift spectra beyond the random-matrix limit, isolating a market factor and sectoral modes. | `strategies/covariance_models.py` |
| 2025 | [2507.05749v2](https://arxiv.org/abs/2507.05749v2) | Develops a diagnostic for selecting a stable reference contract in multi-contract quoting, contrasting Hawkes order-flow forecasts with a composite limit-order-book liquidity factor; NIFTY futures tick data show event-history and LOB signals are complementary. | `strategies/orderflow.py` |
| 2025 | [2508.11649v1](https://arxiv.org/abs/2508.11649v1) | Argues volatility is insufficient under fractional dynamics; proposes pointwise Hurst-Holder regularity as a complementary risk metric capturing local deviations from martingale behavior. | `strategies/long_memory.py` |
| 2025 | [2502.04027v1](https://arxiv.org/abs/2502.04027v1) | Extends hidden-Markov-modulated Hawkes point process to piecewise-constant excitation kernels with EM inference; detects anomalous trade bursts in high-frequency crypto data better than a Markov-modulated Poisson benchmark. | `strategies/orderflow.py` |
| 2025 | [2504.15908v1](https://arxiv.org/abs/2504.15908v1) | Builds multi-scale Hawkes order-flow features including limit-order posting distance, trains an interpretable probabilistic network for mid-price moves, and finds 31% of large orders could spoof; posting distance is critical. | `strategies/orderflow.py` |
| 2025 | [2511.07834v1](https://arxiv.org/abs/2511.07834v1) | Derives horizon-correct VaR, Expected Shortfall, Sharpe, Kelly and drawdown formulas under Levy-stable return scaling, each carrying a closed-form Gaussian-bias term from the tail-index gap. | `strategies/book_risk.py` |
| 2025 | [2507.09554v1](https://arxiv.org/abs/2507.09554v1) | Transfer entropy plus Kramers-Moyal expansion maps directional coupling among Nasdaq, WTI, gold and the dollar; average TE rises 35% and 28% during COVID and Ukraine crises, exposing nonlinear regime shifts. | `strategies/triadic_stress.py` |
| 2025 | [2503.08697v1](https://arxiv.org/abs/2503.08697v1) | Matrix H-theory models multivariate returns as a compound of large-scale and hierarchical slow-background distributions in Wishart/inverse-Wishart universality classes, described by matrix-argument Meijer G-functions; fits S&P500 daily returns for portfolio strategies. | `strategies/covariance_models.py` |
| 2025 | [2504.15985v2](https://arxiv.org/abs/2504.15985v2) | Models realized volatility with multivariate fractional Brownian motion (component-wise Hurst exponents), proves consistent parameter estimation, and shows time-reversible mfBm out-of-sample forecasts outperform HAR and its variants. | `strategies/long_memory.py` |
| 2025 | [2509.00697v1](https://arxiv.org/abs/2509.00697v1) | 34-year Nifty 50 study mapping P/E to horizon-wise return distributions; finds 74% one-year gain probability, modal CAGR above 13%, ten-year trapping periods and low-dimensional chaos. | `strategies/complexity.py` |
| 2025 | [2510.13785v1](https://arxiv.org/abs/2510.13785v1) | Multifractal cross-correlation analysis attributes cryptocurrency multifractality to long-range correlations plus heavy-tailed returns, aiding volatility forecasting and regime-shift detection. | `strategies/complexity.py` |
| 2025 | [2511.03314v1](https://arxiv.org/abs/2511.03314v1) | Finds Bitcoin realized-volatility Hurst exponent decreases with sampling period, fitting a finite-sample ansatz; extrapolated small-scale values below 0.5 indicate rough volatility, with multifractality weaker than price returns. | `strategies/long_memory.py` |
| 2025 | [2504.09276v2](https://arxiv.org/abs/2504.09276v2) | Extends convergence results for a scale-invariant Hurst-parameter estimator to nonlinear transforms of fractional Brownian motion, proving consistency and almost-sure rates for rough stochastic volatility models estimated from integrated variance. | `strategies/long_memory.py` |
| 2025 | [2502.09079v1](https://arxiv.org/abs/2502.09079v1) | Complexity-entropy plane and spectral analysis show crypto series resemble Brownian noise; across horizons simple naive models consistently beat machine/deep forecasters, underscoring low predictability. | `strategies/complexity.py` |
| 2025 | [2504.20488v1](https://arxiv.org/abs/2504.20488v1) | Models returns as conditionally independent given randomly varying volatility, deriving a scaling form linking return tails to the volatility distribution; explains S&P 500, Apple, Paramount and Bitcoin stretched-exponential behaviour. | `strategies/volatility_models.py` |
| 2025 | [2510.24467v1](https://arxiv.org/abs/2510.24467v1) | Derives a closed-form expected-profit function linking trading frequency, execution cost and path roughness, proving a unique optimal frequency tied to price-path fractal dimension and fBm Hurst scaling. | `strategies/execution_schedule.py` |
| 2025 | [2506.03153v1](https://arxiv.org/abs/2506.03153v1) | Proposes Cubic, modelling adaptive fusion of constituent stocks plus binary-encoding classification with confidence regularization for index prediction; beats baselines on forecasting accuracy and downstream trading profitability across markets. | `strategies/market_breadth.py` |
| 2024 | [2411.05951v1](https://arxiv.org/abs/2411.05951v1) | Multifractal Detrended Fluctuation Analysis of Uniswap tick data (2023-24) finds emerging multifractality in decentralised crypto; spectra are left-asymmetric, stronger for transaction volumes than returns, with cross-correlations at large events. | `strategies/complexity.py` |
| 2024 | [2411.02804v1](https://arxiv.org/abs/2411.02804v1) | Constructs a revised VIX by fitting a double-subordinated Normal Inverse Gaussian Levy process to S&P 500 option prices to better identify heavy-tailed uncertainty shocks. | `strategies/options_surface.py` |
| 2024 | [2410.07224v1](https://arxiv.org/abs/2410.07224v1) | Bayesian ensemble and market-efficiency measures detect structural breakpoints in ten European electricity and gas markets triggered by the 2022 Russo-Ukrainian war and USD/RUB. | `strategies/regime_state.py` |
| 2024 | [2403.06253v2](https://arxiv.org/abs/2403.06253v2) | Entropy-corrected geometric Brownian motion relaxes log-normality and improves fits for non-log-normal distributions from dice experiments to real data. | `strategies/complexity.py` |
| 2024 | [2402.06642v1](https://arxiv.org/abs/2402.06642v1) | Establishes equivalence between GARCH-family models and neural-network counterparts, then uses it to build a hybrid volatility forecaster. | `strategies/volatility_models.py` |
| 2024 | [2412.03668v1](https://arxiv.org/abs/2412.03668v1) | Develops hidden Markov graphical models with state-dependent generalized hyperbolic distributions and penalized EM; recovers regime-specific sparse correlation graphs, applied to indexes, crypto and commodity futures 2017-2023. | `strategies/regime_state.py` |
| 2024 | [2405.05634v1](https://arxiv.org/abs/2405.05634v1) | First-order time-homogeneous Markov chain on high-frequency order sequences of six sectors during the 2018 US-China trade war; transition matrices reveal trader participation shifts on high-volatility days. | `strategies/orderflow.py` |
| 2024 | [2409.10543v1](https://arxiv.org/abs/2409.10543v1) | Kullback-Leibler cluster entropy on realized volatility across five indices is maximal at short scales while Shannon entropy peaks at long scales, giving complementary volatility/risk-diversity reads. | `strategies/complexity.py` |
| 2024 | [2409.10859v3](https://arxiv.org/abs/2409.10859v3) | Uses CRSP US equity data to document macroscopic market properties and stylized facts in stochastic portfolio theory terms, and systematically backtests the diversity-weighted portfolio. | `strategies/portfolio_strategy.py` |
| 2024 | [2409.07159v3](https://arxiv.org/abs/2409.07159v3) | Fractional Stochastic Regularity Model with random Hurst exponent driven by fractional Ornstein-Uhlenbeck; Shannon entropy quantifies serial information when H_t != 1/2. | `strategies/volatility_models.py` |
| 2024 | [2401.05430v1](https://arxiv.org/abs/2401.05430v1) | Multi-relational graph diffusion neural network with parallel retention builds dynamic stock graphs via entropy/signal-energy edges for trend classification. | `strategies/statistical.py` |
| 2024 | [2412.14353v4](https://arxiv.org/abs/2412.14353v4) | Models joint log-volatility as a multivariate fractional Ornstein-Uhlenbeck process with a GMM estimator; Oxford-Man realized-vol series are strongly correlated, show cross-covariance asymmetry and spillovers. | `strategies/long_memory.py` |
| 2024 | [2402.04740v1](https://arxiv.org/abs/2402.04740v1) | Non-parametric conditional-intensity estimation for multi-dimensional marked Hawkes processes via shallow-neural and neural-network Hawkes formulations. | `strategies/orderflow.py` |
| 2024 | [2401.13890v2](https://arxiv.org/abs/2401.13890v2) | Extends Hawkes to self/mutually exciting point process with flexible residuals and discrete Markovian intensity; improves high-frequency financial intensity estimation and filtered historical simulation. | `strategies/orderflow.py` |
| 2024 | [2401.10722v1](https://arxiv.org/abs/2401.10722v1) | Analyzes stylized facts of German bond futures (Schatz, Bobl, Bund, Buxl) from tick order books and introduces realism metrics to benchmark market simulators. | `strategies/backtest_models.py` |
| 2024 | [2402.11930v2](https://arxiv.org/abs/2402.11930v2) | High-frequency Bitcoin 2019-2022 shows anomalous diffusion, q-Gaussian heavy tails and power-law autocorrelation of absolute returns, split by a volatility regime shift. | `strategies/complexity.py` |
| 2024 | [2405.09929v1](https://arxiv.org/abs/2405.09929v1) | Kappa-generalised distribution (power-law tails) fits historic daily returns of FTSE 100 and top-100 Nasdaq stocks well in Monte-Carlo goodness-of-fit tests. | `strategies/tail_risk.py` |
| 2024 | [2411.06080v1](https://arxiv.org/abs/2411.06080v1) | Proposes the entropy-based lexical ratio, treating each asset as a keyword document, to measure portfolio diversification; on S&P 500 portfolios it matches conventional metrics while improving risk-adjusted returns. | `strategies/text_factors.py` |
| 2023 | [2302.08208v1](https://arxiv.org/abs/2302.08208v1) | Review linking econophysics information-filtering networks and financial-economics factor models for modeling asset dependence and multivariate volatility. | strategies/covariance_models.py |
| 2023 | [2303.03073v1](https://arxiv.org/abs/2303.03073v1) | NNNH neural-network nonparametric nonlinear Hawkes process captures mutually exciting and inhibitive patterns; SGD with an unbiased gradient estimator. | strategies/orderflow.py |
| 2023 | [2306.16162v1](https://arxiv.org/abs/2306.16162v1) | MFDFA of Indian FX rates (1999-2018) finds multifractality; source is mainly fat tails for USD but differs across currencies. | `strategies/complexity.py` |
| 2023 | [2301.13505v2](https://arxiv.org/abs/2301.13505v2) | Tokyo Stock Exchange nine-year microdata validates the Lillo-Mike-Farmer model: order-sign memory exponent gamma approximately equals metaorder-length exponent alpha minus one. | strategies/orderflow.py |
| 2023 | [2309.00390v1](https://arxiv.org/abs/2309.00390v1) | Fractal-geometry analysis of nine cryptocurrencies vs traditional assets; Bitcoin shows high price persistence, lowering efficiency but raising predictability. | `strategies/complexity.py` |
| 2023 | [2303.00495v1](https://arxiv.org/abs/2303.00495v1) | BTC/ETH lost independence from traditional markets after March 2020, coupling to US tech stocks in 2022; cryptocurrencies are not a safe haven. | strategies/covariance_models.py |
| 2023 | [2302.08829v2](https://arxiv.org/abs/2302.08829v2) | Heavy tails make the best in-sample performance and the best in-sample Sharpe ratio never coincide, questioning Sharpe as the gold-standard metric. | strategies/evaluate.py |
| 2023 | [2302.02769v1](https://arxiv.org/abs/2302.02769v1) | Compares heavy-tailed non-Gaussian return models by Monte Carlo: consistent scaling of large price changes and material impact on option pricing vs Black-Scholes. | strategies/options_math.py |
| 2023 | [2302.11822v1](https://arxiv.org/abs/2302.11822v1) | Multi-kernel Hawkes model of high-frequency mid-price identifies ultra-high, very-high and high-frequency kernels; conditional Hessian checks optimizer convergence. | strategies/orderflow.py |
| 2023 | [2303.09330v1](https://arxiv.org/abs/2303.09330v1) | CSIE-based betas benchmark portfolio volatility against indices and the whole market; finds symbol sets beating indices at equal or lower risk. | strategies/risk_score.py |
| 2023 | [2308.04181v1](https://arxiv.org/abs/2308.04181v1) | Approximate and Sample Entropy quantify randomness of Indian forex returns 2006-2021, tracking the GFC and COVID upheavals. | `strategies/complexity.py` |
| 2023 | [2311.07738v2](https://arxiv.org/abs/2311.07738v2) | Tests whether Cont's 11 stylized facts still hold in modern stock markets; not every return series expresses all facts after regulatory/technological change. | `strategies/statistical.py` |
| 2023 | [2307.08666v1](https://arxiv.org/abs/2307.08666v1) | Uses Shannon entropy on reconstructed dynamics of Lima stock exchange price series to quantify market complexity. | `strategies/complexity.py` |
| 2023 | [2304.08440v1](https://arxiv.org/abs/2304.08440v1) | Structural detrended multifractal fluctuation analysis with change-point regimes; single-factor self-explainable model of cryptocurrency market efficiency. | `strategies/complexity.py` |
| 2023 | [2306.10496v1](https://arxiv.org/abs/2306.10496v1) | Multifractal DFA tests global grain spot indices and confirms intrinsic multifractality, with extensive statistical tests for maize and barley. | `strategies/complexity.py` |
| 2023 | [2310.18903v3](https://arxiv.org/abs/2310.18903v3) | Visibility-graph analysis of WTI, Brent and Shanghai crude oil futures finds power-law degree distributions, clustering and small-world structure around recent crises. | `strategies/complexity.py` |
| 2023 | [2305.05751v1](https://arxiv.org/abs/2305.05751v1) | Crypto stylized facts: return distributions, volatility clustering and multifractal correlations match mature markets for top-cap coins; smaller coins deficient. | `strategies/volatility_models.py` |
| 2023 | [2304.06877v1](https://arxiv.org/abs/2304.06877v1) | Shows topological data analysis yields early-warning bubble signals whenever the log-periodic power law singularity model fits; demonstrated on Bitcoin bubbles. | `strategies/regime.py` |
| 2022 | [2202.01043v2](https://arxiv.org/abs/2202.01043v2) | Presents the two-tailed peaks-over-threshold Hawkes (2T-POT) model for conditional left/right tail quantile forecasts; across six indices it beats GARCH-EVT for VaR/ES at 5% coverage and below, supporting an asymmetric leverage effect. | `strategies/tail_risk.py` |
| 2022 | [2202.12067v1](https://arxiv.org/abs/2202.12067v1) | Models S&P 500 daily prices as 2D Levy flights, finding a 2/3 gyration-radius scaling law and eigenvalue power-law tails in Wishart spectra matching alpha=3/2 flight simulations. | `strategies/covariance_models.py` |
| 2022 | [2208.02659v3](https://arxiv.org/abs/2208.02659v3) | CARMA(p,q)-Hawkes process allows non-monotone intensity autocorrelation; derives stationarity/positivity, likelihood, simulation and AC-based estimation. | strategies/orderflow.py |
| 2022 | [2208.11976v1](https://arxiv.org/abs/2208.11976v1) | Shannon entropy of symbolised returns gives an exact/asymptotic distribution under EMH, forming a statistical market-efficiency test on indices, stocks and crypto. | strategies/complexity.py |
| 2022 | [2207.05939v2](https://arxiv.org/abs/2207.05939v2) | Variance formula for marked/unmarked Hawkes models gives Hawkes volatility on 0.1s mid-prices; intraday predictive power rises over time, useful for real-time risk management. | strategies/orderflow.py |
| 2022 | [2204.02682v1](https://arxiv.org/abs/2204.02682v1) | Analytic link between intrinsic (event) time and physical time with a new overshoot scaling law; physical-time series decomposes into liquidity and volatility components visible only in intrinsic time. | strategies/orderflow.py |
| 2022 | [2203.12587v2](https://arxiv.org/abs/2203.12587v2) | Applies the log-periodic power law model to four major NFT projects, finding as of December 2021 that NFTs are in a small bubble, Decentraland medium, and ENS/ArtBlocks small negative bubbles. | `strategies/regime.py` |
| 2022 | [2202.03198v1](https://arxiv.org/abs/2202.03198v1) | Analyzes S&P500 triplet interactions through balance theory, finding an ordered network structure forms during crises (2008, 2020) while stocks act independently otherwise; a critical temperature measures crisis strength. | `strategies/triadic_stress.py` |

## Low relevance / background (352)

| year | id | title |
| --- | --- | --- |
| 2026 | [2607.16281v1](https://arxiv.org/abs/2607.16281v1) | A Novel Hybrid Quantum Reservoir Computing (nHQRC) for Phase Transition Detection in Non-Equilibrium Dynamical Systems |
| 2026 | [2607.21826v1](https://arxiv.org/abs/2607.21826v1) | Are cryptocurrencies real financial bubbles? Evidence from quantitative analyses |
| 2026 | [2601.12175v2](https://arxiv.org/abs/2601.12175v2) | Distributional Fitting and Tail Analysis of Lead-Time Compositions: Nights vs. Revenue on Airbnb |
| 2026 | [2605.23962v1](https://arxiv.org/abs/2605.23962v1) | From Index to Equity: Pre-Training Transformers for Stock Return Prediction |
| 2026 | [2608.09378v1](https://arxiv.org/abs/2608.09378v1) | Scaling laws of Stablecoin Transactions: Evidence from USDT and USDC on the Ethereum blockchain |
| 2026 | [2604.22976v1](https://arxiv.org/abs/2604.22976v1) | Statistical Mechanics of Household Income and Wealth: Derivation from Firm Dynamics via Maximum Entropy and Mixture Aggregation |
| 2026 | [2605.10447v1](https://arxiv.org/abs/2605.10447v1) | Statistical Model Checking of the Keynes+Schumpeter Model: A Transient Sensitivity Analysis of a Macroeconomic ABM |
| 2026 | [2607.15119v1](https://arxiv.org/abs/2607.15119v1) | Thermodynamic theory of voting and EU elections |
| 2026 | [2602.01122v1](https://arxiv.org/abs/2602.01122v1) | Was Benoit Mandelbrot a hedgehog or a fox? |
| 2025 | [2512.16411v2](https://arxiv.org/abs/2512.16411v2) | Asymptotic and finite-sample distributions of one- and two-sample empirical relative entropy |
| 2025 | [2505.23928v2](https://arxiv.org/abs/2505.23928v2) | Critical Dynamics of Random Surfaces and Multifractal Scaling |
| 2025 | [2511.17479v1](https://arxiv.org/abs/2511.17479v1) | Emergence of Randomness in Temporally Aggregated Financial Tick Sequences |
| 2025 | [2504.18960v1](https://arxiv.org/abs/2504.18960v1) | Impact of the COVID-19 pandemic on the financial market efficiency of price returns, absolute returns, and volatility increment: Evidence from stock and cryptocurrency markets |
| 2025 | [2512.07860v1](https://arxiv.org/abs/2512.07860v1) | Integrating LSTM Networks with Neural Levy Processes for Financial Forecasting |
| 2025 | [2504.08611v1](https://arxiv.org/abs/2504.08611v1) | International Financial Markets Through 150 Years: Evaluating Stylized Facts |
| 2025 | [2501.11648v1](https://arxiv.org/abs/2501.11648v1) | Mean-Field Limits for Nearly Unstable Hawkes Processes |
| 2025 | [2512.17225v2](https://arxiv.org/abs/2512.17225v2) | Modeling financial time series with $φ^{4}$ quantum field theory |
| 2025 | [2504.19050v1](https://arxiv.org/abs/2504.19050v1) | Phase Transitions in Financial Markets Using the Ising Model: A Statistical Mechanics Perspective |
| 2025 | [2504.20058v2](https://arxiv.org/abs/2504.20058v2) | Predictive AI with External Knowledge Infusion: Datasets and Benchmarks for Stock Markets |
| 2025 | [2507.22035v1](https://arxiv.org/abs/2507.22035v1) | Quantum generative modeling for financial time series with temporal correlations |
| 2025 | [2505.10373v5](https://arxiv.org/abs/2505.10373v5) | Reproducing the first and second moments of empirical degree distributions |
| 2025 | [2512.17936v1](https://arxiv.org/abs/2512.17936v1) | Risk-Aware Financial Forecasting Enhanced by Machine Learning and Intuitionistic Fuzzy Multi-Criteria Decision-Making |
| 2025 | [2512.17925v1](https://arxiv.org/abs/2512.17925v1) | Stylized Facts and Their Microscopic Origins: Clustering, Persistence, and Stability in a 2D Ising Framework |
| 2025 | [2507.08394v1](https://arxiv.org/abs/2507.08394v1) | Temperature Measurement in Agent Systems |
| 2025 | [2511.14408v1](https://arxiv.org/abs/2511.14408v1) | The Hidden Constant of Market Rhythms: How $1-1/e$ Defines Scaling in Intrinsic Time |
| 2025 | [2512.12054v1](https://arxiv.org/abs/2512.12054v1) | Universal Dynamics of Financial Bubbles in Isolated Markets: Evidence from the Iranian Stock Market |
| 2025 | [2508.04671v1](https://arxiv.org/abs/2508.04671v1) | Universal Patterns in the Blockchain: Analysis of EOAs and Smart Contracts in ERC20 Token Networks |
| 2024 | [2401.09233v1](https://arxiv.org/abs/2401.09233v1) | A closer look at the chemical potential of an ideal agent system |
| 2024 | [2406.19406v2](https://arxiv.org/abs/2406.19406v2) | Dissecting Multifractal detrended cross-correlation analysis |
| 2024 | [2410.02798v1](https://arxiv.org/abs/2410.02798v1) | Joint multifractality in the cross-correlations between grains \& oilseeds indices and external uncertainties |
| 2024 | [2403.08362v2](https://arxiv.org/abs/2403.08362v2) | Mean-Field Microcanonical Gradient Descent |
| 2024 | [2408.16010v1](https://arxiv.org/abs/2408.16010v1) | Model-based and empirical analyses of stochastic fluctuations in economy and finance |
| 2024 | [2406.01335v2](https://arxiv.org/abs/2406.01335v2) | Statistics-Informed Parameterized Quantum Circuit via Maximum Entropy Principle for Data Science and Finance |
| 2024 | [2408.07653v3](https://arxiv.org/abs/2408.07653v3) | Stylized facts in Web3 |
| 2024 | [2406.07354v1](https://arxiv.org/abs/2406.07354v1) | The Theory of Intrinsic Time: A Primer |
| 2023 | [2311.10719v1](https://arxiv.org/abs/2311.10719v1) | Analysis of frequent trading effects of various machine learning models |
| 2023 | [2303.16155v1](https://arxiv.org/abs/2303.16155v1) | Entropy of financial time series due to the shock of war |
| 2023 | [2303.07393v4](https://arxiv.org/abs/2303.07393v4) | Many learning agents interacting with an agent-based market model |
| 2023 | [2303.15164v1](https://arxiv.org/abs/2303.15164v1) | On the Connection between Temperature and Volatility in Ideal Agent Systems |
| 2023 | [2307.09767v1](https://arxiv.org/abs/2307.09767v1) | Sig-Splines: universal approximation and convex calibration of time series generative models |
| 2023 | [2310.00753v1](https://arxiv.org/abs/2310.00753v1) | Study of Stylized Facts in Stock Market Data |
| 2022 | [2205.06338v1](https://arxiv.org/abs/2205.06338v1) | A Multivariate Hawkes Process Model for Stablecoin-Cryptocurrency Depegging Event Dynamics |
| 2022 | [2206.07831v2](https://arxiv.org/abs/2206.07831v2) | Analysis of inter-transaction time fluctuations in the cryptocurrency market |
| 2022 | [2207.10476v2](https://arxiv.org/abs/2207.10476v2) | Efficiency of the Moscow Stock Exchange before 2022 |
| 2022 | [2210.13667v2](https://arxiv.org/abs/2210.13667v2) | Experimental observations of fractal landscape dynamics in a dense emulsion |
| 2022 | [2211.00728v2](https://arxiv.org/abs/2211.00728v2) | Genuine multifractality in time series is due to temporal correlations |
| 2022 | [2301.10178v1](https://arxiv.org/abs/2301.10178v1) | Methods in Econophysics: Estimating the Probability Density and Volatility |
| 2022 | [2208.01445v1](https://arxiv.org/abs/2208.01445v1) | Multifractal cross-correlations of bitcoin and ether trading characteristics in the post-COVID-19 time |
| 2022 | [2210.09619v1](https://arxiv.org/abs/2210.09619v1) | Sector-wise analysis of Indian stock market: Long and short-term risk and stability analysis |
| 2022 | [2207.00493v1](https://arxiv.org/abs/2207.00493v1) | Simulating financial time series using attention |
| 2022 | [2205.04256v6](https://arxiv.org/abs/2205.04256v6) | SoK: Blockchain Decentralization |
| 2022 | [2208.08169v1](https://arxiv.org/abs/2208.08169v1) | Time is limited on the road to asymptopia |
| 2021 | [2106.06164v1](https://arxiv.org/abs/2106.06164v1) | A new look at calendar anomalies: Multifractality and day of the week effect |
| 2021 | [2112.06290v1](https://arxiv.org/abs/2112.06290v1) | A q-spin Potts model of markets: Gain-loss asymmetry in stock indices as an emergent phenomenon |
| 2021 | [2102.04532v1](https://arxiv.org/abs/2102.04532v1) | Asymmetric Tsallis distributions for modelling financial market dynamics |
| 2021 | [2112.03513v1](https://arxiv.org/abs/2112.03513v1) | Change of persistence in European electricity spot prices |
| 2021 | [2105.14193v1](https://arxiv.org/abs/2105.14193v1) | Characterization of the probability and information entropy of a process with an exponentially increasing sample space and its application to the Broad Money Supply |
| 2021 | [2112.03031v1](https://arxiv.org/abs/2112.03031v1) | Complexity and Persistence of Price Time Series of the European Electricity Spot Market |
| 2021 | [2108.11755v1](https://arxiv.org/abs/2108.11755v1) | Market Crash Prediction Model for Markets in A Rational Bubble |
| 2021 | [2103.09107v1](https://arxiv.org/abs/2103.09107v1) | Randentropy: a software to measure inequality in random systems |
| 2021 | [2103.00788v1](https://arxiv.org/abs/2103.00788v1) | Statistical mechanics and Bayesian Inference addressed to the Osborne Paradox |
| 2021 | [2106.07354v1](https://arxiv.org/abs/2106.07354v1) | The relationship between the US broad money supply and US GDP for the time period 2001 to 2019 with that of the corresponding time series for US national property and stock market indices, using an information entropy methodology |
| 2021 | [2109.01214v1](https://arxiv.org/abs/2109.01214v1) | What drives bitcoin? An approach from continuous local transfer entropy and deep learning classification models |
| 2020 | [2003.12655v1](https://arxiv.org/abs/2003.12655v1) | Coupled criticality analysis of inflation and unemployment |
| 2020 | [2007.04829v1](https://arxiv.org/abs/2007.04829v1) | Gintropy: Gini index based generalization of Entropy |
| 2020 | [2006.15214v1](https://arxiv.org/abs/2006.15214v1) | Improving MF-DFA model with applications in precious metals market |
| 2020 | [2004.07612v1](https://arxiv.org/abs/2004.07612v1) | Information transfer between stock market sectors: A comparison between the USA and China |
| 2020 | [2012.08517v1](https://arxiv.org/abs/2012.08517v1) | Model of cunning agents |
| 2020 | [2006.09154v1](https://arxiv.org/abs/2006.09154v1) | Multifractal temporally weighted detrended partial cross-correlation analysis to quantify intrinsic power-law cross-correlation of two non-stationary time series affected by common external factors |
| 2020 | [2010.15403v2](https://arxiv.org/abs/2010.15403v2) | Multiscale characteristics of the emerging global cryptocurrency market |
| 2020 | [2007.12880v1](https://arxiv.org/abs/2007.12880v1) | Visibility graph analysis of economy policy uncertainty indices |
| 2019 | [1910.13286v1](https://arxiv.org/abs/1910.13286v1) | A Self-Exciting Modelling Framework for Forward Prices in Power Markets |
| 2019 | [1905.04370v1](https://arxiv.org/abs/1905.04370v1) | A Three-state Opinion Formation Model for Financial Markets |
| 2019 | [1912.03556v1](https://arxiv.org/abs/1912.03556v1) | A percolation model for the emergence of the Bitcoin Lightning Network |
| 2019 | [1906.03305v1](https://arxiv.org/abs/1906.03305v1) | Clustering Degree-Corrected Stochastic Block Model with Outliers |
| 2019 | [1902.02040v1](https://arxiv.org/abs/1902.02040v1) | Development of an agent-based speculation game for higher reproducibility of financial stylized facts |
| 2019 | [1910.09153v1](https://arxiv.org/abs/1910.09153v1) | Entropic Dynamic Time Warping Kernels for Co-evolving Financial Time Series Analysis |
| 2019 | [1902.10877v1](https://arxiv.org/abs/1902.10877v1) | Financial series prediction using Attention LSTM |
| 2019 | [1901.07721v1](https://arxiv.org/abs/1901.07721v1) | Nonextensive triplets in stock market indices |
| 2019 | [1910.13803v1](https://arxiv.org/abs/1910.13803v1) | Rank-size law, financial inequality indices and gain concentrations by cyclist teams. The case of a multiple stage bicycle race, like Tour de France |
| 2019 | [1904.04951v3](https://arxiv.org/abs/1904.04951v3) | Robust Mathematical Formulation and Probabilistic Description of Agent-Based Computational Economic Market Models |
| 2019 | [1903.05322v1](https://arxiv.org/abs/1903.05322v1) | Stylized facts of the Indian Stock Market |
| 2018 | [1809.06728v1](https://arxiv.org/abs/1809.06728v1) | Dynamical variety of shapes in financial multifractality |
| 2018 | [1808.08585v1](https://arxiv.org/abs/1808.08585v1) | Evolutionary dynamics of cryptocurrency transaction networks: An empirical study |
| 2018 | [1808.04231v1](https://arxiv.org/abs/1808.04231v1) | GARCH(1,1) model of the financial market with the Minkowski metric |
| 2018 | [1807.09346v1](https://arxiv.org/abs/1807.09346v1) | Investigating the configurations in cross-shareholding: a joint copula-entropy approach |
| 2018 | [1803.02019v2](https://arxiv.org/abs/1803.02019v2) | Modelling stock correlations with expected returns from investors |
| 2018 | [1805.04750v1](https://arxiv.org/abs/1805.04750v1) | Multifractal analysis of financial markets |
| 2018 | [1809.00820v1](https://arxiv.org/abs/1809.00820v1) | Multiplicative random cascades with additional stochastic process in financial markets |
| 2018 | [1806.03758v1](https://arxiv.org/abs/1806.03758v1) | On critical dynamics and thermodynamic efficiency of urban transformations |
| 2018 | [1806.01616v1](https://arxiv.org/abs/1806.01616v1) | Power-law cross-correlations: Issues, solutions and future challenges |
| 2018 | [1805.11909v1](https://arxiv.org/abs/1805.11909v1) | Quantitative approach to multifractality induced by correlations and broad distribution of data |
| 2018 | [1809.02674v4](https://arxiv.org/abs/1809.02674v4) | The new face of multifractality: Multi-branchedness and the phase transitions in time series of mean inter-event times |
| 2017 | [1710.08860v1](https://arxiv.org/abs/1710.08860v1) | A Topological Approach to Scaling in Financial Data |
| 2017 | [1706.03246v2](https://arxiv.org/abs/1706.03246v2) | Aftershocks following crash of currency exchange rate: The case of RUB/USD in 2014 |
| 2017 | [1704.05818v1](https://arxiv.org/abs/1704.05818v1) | Anomalous Scaling of Stochastic Processes and the Moses Effect |
| 2017 | [1704.04442v1](https://arxiv.org/abs/1704.04442v1) | Crude oil market and geopolitical events: an analysis based on information-theory-based quantifiers |
| 2017 | [1702.06191v1](https://arxiv.org/abs/1702.06191v1) | Evidence for criticality in financial data |
| 2017 | [1706.00467v1](https://arxiv.org/abs/1706.00467v1) | Fluctuation analysis of electric power loads in Europe: Correlation multifractality vs. Distribution function multifractality |
| 2017 | [1710.07331v2](https://arxiv.org/abs/1710.07331v2) | Information measure for financial time series: quantifying short-term market heterogeneity |
| 2017 | [1707.03746v3](https://arxiv.org/abs/1707.03746v3) | Modeling the price of Bitcoin with geometric fractional Brownian motion: a Monte Carlo approach |
| 2017 | [1703.06840v1](https://arxiv.org/abs/1703.06840v1) | New approaches in agent-based modeling of complex financial systems |
| 2017 | [1702.06055v2](https://arxiv.org/abs/1702.06055v2) | Performance of information criteria used for model selection of Hawkes process models of financial data |
| 2017 | [1708.04532v1](https://arxiv.org/abs/1708.04532v1) | Some stylized facts of the Bitcoin market |
| 2017 | [1707.07618v3](https://arxiv.org/abs/1707.07618v3) | Statistical properties and multifractality of Bitcoin |
| 2017 | [1712.02003v2](https://arxiv.org/abs/1712.02003v2) | Universal fluctuations in growth dynamics of economic systems |
| 2017 | [1711.10552v1](https://arxiv.org/abs/1711.10552v1) | Using nonlinear stochastic and deterministic (chaotic tools) to test the EMH of two Electricity Markets the case of Italy and Greece |
| 2017 | [1702.00144v1](https://arxiv.org/abs/1702.00144v1) | Zipf's law for share price and company fundamentals |
| 2016 | [1601.07900v2](https://arxiv.org/abs/1601.07900v2) | Critical value of the total debt in view of the debts durations |
| 2016 | [1606.06111v2](https://arxiv.org/abs/1606.06111v2) | Deviations from universality in the fluctuation behavior of a heterogeneous complex system reveal intrinsic properties of components: The case of the international currency market |
| 2016 | [1604.03996v2](https://arxiv.org/abs/1604.03996v2) | Evidence of Self-Organization in Time Series of Capital Markets |
| 2016 | [1608.07752v3](https://arxiv.org/abs/1608.07752v3) | Financial Market Dynamics: Superdiffusive or not? |
| 2016 | [1608.06781v2](https://arxiv.org/abs/1608.06781v2) | Fractal approach towards power-law coherency to measure cross-correlations between time series |
| 2016 | [1601.03688v1](https://arxiv.org/abs/1601.03688v1) | Inter-occurrence times and universal laws in finance, earthquakes and genomes |
| 2016 | [1611.00897v1](https://arxiv.org/abs/1611.00897v1) | Joint multifractal analysis based on wavelet leaders |
| 2016 | [1610.09812v1](https://arxiv.org/abs/1610.09812v1) | Long-range Correlation and Market Segmentation in Bond Market |
| 2016 | [1601.07707v1](https://arxiv.org/abs/1601.07707v1) | Micro-foundation using percolation theory of the finite-time singular behavior of the crash hazard rate in a class of rational expectation bubbles |
| 2016 | [1610.08416v2](https://arxiv.org/abs/1610.08416v2) | Minimum spanning tree filtering of correlations for varying time scales and size of fluctuations |
| 2016 | [1603.08383v1](https://arxiv.org/abs/1603.08383v1) | Modelling income, wealth, and expenditure data by use of Econophysics |
| 2016 | [1610.09519v2](https://arxiv.org/abs/1610.09519v2) | Multifractal cross wavelet analysis |
| 2016 | [1608.01895v3](https://arxiv.org/abs/1608.01895v3) | Semiparametric inference on the fractal index of Gaussian and conditionally Gaussian time series data |
| 2016 | [1612.08705v1](https://arxiv.org/abs/1612.08705v1) | Speculation and Power Law |
| 2016 | [1612.05229v1](https://arxiv.org/abs/1612.05229v1) | Stylized Facts and Simulating Long Range Financial Data |
| 2016 | [1610.07028v1](https://arxiv.org/abs/1610.07028v1) | Techniques for multifractal spectrum estimation in financial time series |
| 2016 | [1612.09344v1](https://arxiv.org/abs/1612.09344v1) | The Random Walk behind Volatility Clustering |
| 2016 | [1606.01218v1](https://arxiv.org/abs/1606.01218v1) | World Financial 2014-2016 Market Bubbles: Oil Negative - US Dollar Positive |
| 2015 | [1502.05603v2](https://arxiv.org/abs/1502.05603v2) | Assessment of 48 Stock markets using adaptive multifractal approach |
| 2015 | [1503.05550v1](https://arxiv.org/abs/1503.05550v1) | Club Convergence of House Prices: Evidence from China's Ten Key Cities |
| 2015 | [1510.03040v1](https://arxiv.org/abs/1510.03040v1) | Coupled uncertainty provided by a multifractal random walker |
| 2015 | [1510.04910v2](https://arxiv.org/abs/1510.04910v2) | Detrended cross-correlations between returns, volatility, trading activity, and volume traded for the stock market companies |
| 2015 | [1511.08830v1](https://arxiv.org/abs/1511.08830v1) | Disentangling bipartite and core-periphery structure in financial networks |
| 2015 | [1509.01839v1](https://arxiv.org/abs/1509.01839v1) | Efficiency and credit ratings: a permutation-information-theory analysis |
| 2015 | [1510.08615v1](https://arxiv.org/abs/1510.08615v1) | Gold, currencies and market efficiency |
| 2015 | [1507.04298v2](https://arxiv.org/abs/1507.04298v2) | Modelling Financial Markets by Self-Organized Criticality |
| 2015 | [1507.06219v1](https://arxiv.org/abs/1507.06219v1) | Multi-scaling of wholesale electricity prices |
| 2015 | [1510.04690v1](https://arxiv.org/abs/1510.04690v1) | On Capturing the Spreading Dynamics over Trading Prices in the Market |
| 2015 | [1502.00225v1](https://arxiv.org/abs/1502.00225v1) | Power-law correlations in finance-related Google searches, and their cross-correlations with volatility and traded volume: Evidence from the Dow Jones Industrial components |
| 2015 | [1505.08117v1](https://arxiv.org/abs/1505.08117v1) | Predictability of price movements in deregulated electricity markets |
| 2015 | [1505.06053v2](https://arxiv.org/abs/1505.06053v2) | Record statistics for random walk bridges |
| 2015 | [1509.01212v1](https://arxiv.org/abs/1509.01212v1) | Stochastic Frontier I & D of fractal dimensions for technological innovation |
| 2015 | [1501.02447v3](https://arxiv.org/abs/1501.02447v3) | Stochastic simulation framework for the Limit Order Book using liquidity motivated agents |
| 2015 | [1508.07428v2](https://arxiv.org/abs/1508.07428v2) | Time-dependent scaling patterns in high frequency financial data |
| 2015 | [1509.06315v1](https://arxiv.org/abs/1509.06315v1) | Universality of market superstatistics |
| 2014 | [1407.5258v1](https://arxiv.org/abs/1407.5258v1) | Agent-based model with asymmetric trading and herding for complex financial systems |
| 2014 | [1404.6637v2](https://arxiv.org/abs/1404.6637v2) | Braided and Knotted Stocks in the Stock Market: Anticipating the flash crashes |
| 2014 | [1412.2124v1](https://arxiv.org/abs/1412.2124v1) | Competition of Commodities for the Status of Money in an Agent-based Model |
| 2014 | [1401.2860v1](https://arxiv.org/abs/1401.2860v1) | Complex temporal structure of activity in on-line electronic auctions |
| 2014 | [1403.1574v2](https://arxiv.org/abs/1403.1574v2) | Consentaneous agent-based and stochastic model of the financial markets |
| 2014 | [1412.3126v1](https://arxiv.org/abs/1412.3126v1) | Financial Time Series: Stylized Facts for the Mexican Stock Exchange Index Compared to Developed Markets |
| 2014 | [1409.8024v5](https://arxiv.org/abs/1409.8024v5) | Herding interactions as an opportunity to prevent extreme events in financial markets |
| 2014 | [1401.7496v1](https://arxiv.org/abs/1401.7496v1) | Microeconomic Structure determines Macroeconomic Dynamics. Aoki defeats the Representative Agent |
| 2014 | [1401.5452v1](https://arxiv.org/abs/1401.5452v1) | Modeling the stylized facts of wholesale system marginal price (SMP) and the impacts of regulatory reforms on the Greek Electricity Market |
| 2014 | [1401.3316v2](https://arxiv.org/abs/1401.3316v2) | Multifractal Diffusion Entropy Analysis: Optimal Bin Width of Probability Histograms |
| 2014 | [1401.2548v1](https://arxiv.org/abs/1401.2548v1) | Mutual Information Rate-Based Networks in Financial Markets |
| 2014 | [1411.1924v1](https://arxiv.org/abs/1411.1924v1) | On the Complexity and Behaviour of Cryptocurrencies Compared to Other Markets |
| 2014 | [1406.7526v1](https://arxiv.org/abs/1406.7526v1) | Predictability of Volatility Homogenised Financial Time Series |
| 2014 | [1411.2215v1](https://arxiv.org/abs/1411.2215v1) | Simple Stochastic Order-Book Model of Swarm Behavior in Continuous Double Auction |
| 2014 | [1412.1293v1](https://arxiv.org/abs/1412.1293v1) | Skewness and kurtosis analysis for non-Gaussian distributions |
| 2014 | [1411.3399v1](https://arxiv.org/abs/1411.3399v1) | Trend and Fractality Assessment of Mexico's Stock Exchange |
| 2014 | [1411.1689v1](https://arxiv.org/abs/1411.1689v1) | Universality of Tsallis q-exponential of interoccurrence times within the microscopic model of cunning agents |
| 2014 | [1405.5939v1](https://arxiv.org/abs/1405.5939v1) | Wealth share analysis with "fundamentalist/chartist" heterogeneous agents |
| 2013 | [1308.2732v1](https://arxiv.org/abs/1308.2732v1) | A relative information approach to financial time series analysis using binary $N$-grams dictionaries |
| 2013 | [1304.0212v1](https://arxiv.org/abs/1304.0212v1) | Do wealth distributions follow power laws? Evidence from "rich lists" |
| 2013 | [1312.3247v1](https://arxiv.org/abs/1312.3247v1) | Emergent quantum mechanics of finances |
| 2013 | [1309.0218v1](https://arxiv.org/abs/1309.0218v1) | Exponential and power laws in public procurement markets |
| 2013 | [1305.5958v1](https://arxiv.org/abs/1305.5958v1) | Fluctuation analysis of the three agent groups herding model |
| 2013 | [1308.1749v1](https://arxiv.org/abs/1308.1749v1) | Fractality of profit landscapes and validation of time series models for stock prices |
| 2013 | [1312.6443v2](https://arxiv.org/abs/1312.6443v2) | Global inequality in energy consumption from 1980 to 2010 |
| 2013 | [1309.2416v1](https://arxiv.org/abs/1309.2416v1) | Modeling of Stock Returns and Trading Volume |
| 2013 | [1305.0436v1](https://arxiv.org/abs/1305.0436v1) | Multivariate high-frequency financial data via semi-Markov processes |
| 2013 | [1311.5753v3](https://arxiv.org/abs/1311.5753v3) | Nucleation, condensation and lambda-transition on a real-life stock market |
| 2013 | [1312.3894v1](https://arxiv.org/abs/1312.3894v1) | Semi-Markov Models in High Frequency Finance: A Review |
| 2013 | [1309.2130v4](https://arxiv.org/abs/1309.2130v4) | The Interrupted Power Law and The Size of Shadow Banking |
| 2012 | [1204.6483v1](https://arxiv.org/abs/1204.6483v1) | Applications of statistical mechanics to economics: Entropic origin of the probability distributions of money, income, and energy consumption |
| 2012 | [1201.4841v2](https://arxiv.org/abs/1201.4841v2) | Econophysics of a religious cult: the Antoinists in Belgium [1920-2000] |
| 2012 | [1209.4175v1](https://arxiv.org/abs/1209.4175v1) | Hierarchical structure of stock price fluctuations in financial markets |
| 2012 | [1211.3599v1](https://arxiv.org/abs/1211.3599v1) | Network analysis of correlation strength between the most developed countries |
| 2012 | [1206.7000v1](https://arxiv.org/abs/1206.7000v1) | On the role of backauditing for tax evasion in an agent-based Econophysics model |
| 2011 | [1101.1847v1](https://arxiv.org/abs/1101.1847v1) | Critical Overview of Agent-Based Models for Economics |
| 2011 | [1107.3456v2](https://arxiv.org/abs/1107.3456v2) | Exploring complex networks via topological embedding on surfaces |
| 2011 | [1103.1501v1](https://arxiv.org/abs/1103.1501v1) | Exponential wealth distribution: a new approach from functional iteration theory |
| 2011 | [1112.0233v1](https://arxiv.org/abs/1112.0233v1) | Income Tax Evasion Dynamics: Evidence from an Agent-based Econophysics Model |
| 2011 | [1102.1624v2](https://arxiv.org/abs/1102.1624v2) | On the criticality of inferred models |
| 2011 | [1102.2620v1](https://arxiv.org/abs/1102.2620v1) | Predicting economic market crises using measures of collective panic |
| 2010 | [1009.4843v2](https://arxiv.org/abs/1009.4843v2) | A quantum model for the stock market |
| 2010 | [1003.1802v1](https://arxiv.org/abs/1003.1802v1) | A simple model of mortality trends aiming at universality: Lee Carter + Cohort |
| 2010 | [1006.4382v1](https://arxiv.org/abs/1006.4382v1) | Fairness Is an Emergent Self-Organized Property of the Free Market for Labor |
| 2010 | [1009.4835v2](https://arxiv.org/abs/1009.4835v2) | Financial LPPL Bubbles with Mean-Reverting Noise in the Frequency Domain |
| 2010 | [1009.2743v1](https://arxiv.org/abs/1009.2743v1) | Mesoscopic modelling of financial markets |
| 2010 | [1001.2639v1](https://arxiv.org/abs/1001.2639v1) | Point Processes Modeling of Time Series Exhibiting Power-Law Statistics |
| 2010 | [1007.1631v1](https://arxiv.org/abs/1007.1631v1) | Price dynamics in financial markets: a kinetic approach |
| 2010 | [1007.5074v1](https://arxiv.org/abs/1007.5074v1) | Statistical mechanics approach to the probability distribution of money |
| 2010 | [1008.2179v1](https://arxiv.org/abs/1008.2179v1) | Statistical mechanics of money, debt, and energy consumption |
| 2010 | [1002.0917v1](https://arxiv.org/abs/1002.0917v1) | Statistical properties of agent-based models in markets with continuous double auction mechanism |
| 2010 | [1011.2385v1](https://arxiv.org/abs/1011.2385v1) | The foreign exchange market: return distributions, multifractality, anomalous multifractality and Epps effect |
| 2010 | [1006.2057v1](https://arxiv.org/abs/1006.2057v1) | The individual income distribution in Argentina in the period 2000-2009. A unique source of non stationary data |
| 2010 | [1011.5187v1](https://arxiv.org/abs/1011.5187v1) | Transition from Exponential to Power Law Distributions in a Chaotic Market |
| 2010 | [1004.1210v2](https://arxiv.org/abs/1004.1210v2) | Universal Fluctuations of AEX index |
| 2010 | [1004.1138v2](https://arxiv.org/abs/1004.1138v2) | Universal Fluctuations of the FTSE100 |
| 2010 | [1004.1136v2](https://arxiv.org/abs/1004.1136v2) | Universality in DAX index returns fluctuations |
| 2009 | [0902.0075v2](https://arxiv.org/abs/0902.0075v2) | A k-generalized statistical mechanics approach to income analysis |
| 2009 | [0910.2447v1](https://arxiv.org/abs/0910.2447v1) | Activity Dependent Branching Ratios in Stocks, Solar X-ray Flux, and the Bak-Tang-Wiesenfeld Sandpile Model |
| 2009 | [0909.1007v2](https://arxiv.org/abs/0909.1007v2) | Bubble Diagnosis and Prediction of the 2005-2007 and 2008-2009 Chinese stock market bubbles |
| 2009 | [0905.1518v2](https://arxiv.org/abs/0905.1518v2) | Colloquium: Statistical mechanics of money, wealth, and income |
| 2009 | [0909.1974v2](https://arxiv.org/abs/0909.1974v2) | Econophysics: Empirical facts and agent-based models |
| 2009 | [0903.2099v1](https://arxiv.org/abs/0903.2099v1) | Financial Atoms and Molecules |
| 2009 | [0901.0401v1](https://arxiv.org/abs/0901.0401v1) | From Physics to Economics: An Econometric Example Using Maximum Relative Entropy |
| 2009 | [0903.4216v2](https://arxiv.org/abs/0903.4216v2) | Statistical thermodynamics of economic systems |
| 2009 | [0905.4450v1](https://arxiv.org/abs/0905.4450v1) | Stock Market and Motion of a Variable Mass Spring |
| 2009 | [0910.2524v1](https://arxiv.org/abs/0910.2524v1) | Universal and nonuniversal allometric scaling behaviors in the visibility graphs of world stock market indices |
| 2009 | [0912.4898v4](https://arxiv.org/abs/0912.4898v4) | Universal patterns of inequality |
| 2008 | [0801.1475v2](https://arxiv.org/abs/0801.1475v2) | A Multifractal Analysis of Asian Foreign Exchange Markets |
| 2008 | [0803.3733v1](https://arxiv.org/abs/0803.3733v1) | Comment on ``Tests of scaling and universality of the distributions of trade size and share volume: Evidence from three distinct markets" by Plerou and Stanley, Phys. Rev. E 76, 046109 (2007) |
| 2008 | [0804.4081v1](https://arxiv.org/abs/0804.4081v1) | Comparison of detrending methods for fluctuation analysis |
| 2008 | [0801.3494v1](https://arxiv.org/abs/0801.3494v1) | Direct evidence for inversion formula in multifractal financial volatility measure |
| 2008 | [0803.0436v1](https://arxiv.org/abs/0803.0436v1) | Double Power Law Decay of the Persistence in Financial Markets |
| 2008 | [0812.2664v1](https://arxiv.org/abs/0812.2664v1) | Evidence for the Gompertz Curve in the Income Distribution of Brazil 1978-2005 |
| 2008 | [0806.2989v2](https://arxiv.org/abs/0806.2989v2) | How to grow a bubble: A model of myopic adapting agents |
| 2008 | [0802.1747v1](https://arxiv.org/abs/0802.1747v1) | Information flow between stock indices |
| 2008 | [0809.1040v2](https://arxiv.org/abs/0809.1040v2) | Patterns in high-frequency FX data: Discovery of 12 empirical scaling laws |
| 2008 | [0805.2792v1](https://arxiv.org/abs/0805.2792v1) | Productivity Dispersion: Facts, Theory, and Implications |
| 2008 | [0807.0563v1](https://arxiv.org/abs/0807.0563v1) | The exponentially truncated q-distribution: A generalized distribution for real complex systems |
| 2008 | [0804.4191v3](https://arxiv.org/abs/0804.4191v3) | Theory of market fluctuations |
| 2008 | [0810.2508v2](https://arxiv.org/abs/0810.2508v2) | Universality in the stock exchange |
| 2008 | [0807.3800v3](https://arxiv.org/abs/0807.3800v3) | What drives mutual fund asset concentration? |
| 2007 | [physics/0701171v2](https://arxiv.org/abs/physics/0701171v2) | A case study of speculative financial bubbles in the South African stock market 2003-2006 |
| 2007 | [0710.4010v2](https://arxiv.org/abs/0710.4010v2) | A stochastic theory for temporal fluctuations in self-organized critical systems |
| 2007 | [0711.3106v3](https://arxiv.org/abs/0711.3106v3) | A threshold model of financial markets |
| 2007 | [0709.2083v1](https://arxiv.org/abs/0709.2083v1) | Economic dynamics with financial fragility and mean-field interaction: a model |
| 2007 | [0709.3662v4](https://arxiv.org/abs/0709.3662v4) | Econophysics, Statistical Mechanics Approach to |
| 2007 | [0706.3122v2](https://arxiv.org/abs/0706.3122v2) | Effects of payoff functions and preference distributions in an adaptive population |
| 2007 | [0708.0063v1](https://arxiv.org/abs/0708.0063v1) | Information flow between composite stock index and individual stocks |
| 2007 | [0706.2140v1](https://arxiv.org/abs/0706.2140v1) | Multifractality in stock indexes: Fact or fiction? |
| 2007 | [0705.2551v1](https://arxiv.org/abs/0705.2551v1) | Network Topology of an Experimental Futures Exchange |
| 2007 | [physics/0701302v1](https://arxiv.org/abs/physics/0701302v1) | Power Law in Firms Bankruptcy |
| 2007 | [0709.1281v1](https://arxiv.org/abs/0709.1281v1) | Relative and Discrete Utility Maximising Entropy |
| 2007 | [0705.4329v1](https://arxiv.org/abs/0705.4329v1) | Scale-free avalanches in the multifractal random walk |
| 2007 | [physics/0701156v2](https://arxiv.org/abs/physics/0701156v2) | Structurally dynamic spin market networks |
| 2007 | [0712.3992v1](https://arxiv.org/abs/0712.3992v1) | Two Fractal Overlap Time Series: Earthquakes and Market Crashes |
| 2007 | [0709.0591v1](https://arxiv.org/abs/0709.0591v1) | Utility function estimation: the entropy approach |
| 2007 | [physics/0702185v1](https://arxiv.org/abs/physics/0702185v1) | Yet on statistical properties of traded volume: correlation and mutual information at different value magnitudes |
| 2006 | [math-ph/0607066v1](https://arxiv.org/abs/math-ph/0607066v1) | Analysis of Stochstic Evolution |
| 2006 | [physics/0608004v1](https://arxiv.org/abs/physics/0608004v1) | Critical dynamics and global persistence exponent on Taiwan financial market |
| 2006 | [nlin/0601074v2](https://arxiv.org/abs/nlin/0601074v2) | Difference in nature of correlation between NASDAQ and BSE indices |
| 2006 | [physics/0609006v1](https://arxiv.org/abs/physics/0609006v1) | Dynamics of the Warsaw Stock Exchange index as analysed by the nonhomogeneous fractional relaxation equation |
| 2006 | [physics/0606012v1](https://arxiv.org/abs/physics/0606012v1) | Econophysics of Stock and Foreign Currency Exchange Markets |
| 2006 | [physics/0607246v1](https://arxiv.org/abs/physics/0607246v1) | Econophysics of interest rates and the role of monetary policy |
| 2006 | [physics/0603040v2](https://arxiv.org/abs/physics/0603040v2) | Evaluation of Tranche in Securitization and Long-range Ising Model |
| 2006 | [physics/0607273v2](https://arxiv.org/abs/physics/0607273v2) | Frequency analysis of tick quotes on the foreign exchange market and agent-based modeling: A spectral distance approach |
| 2006 | [physics/0608016v2](https://arxiv.org/abs/physics/0608016v2) | Market Efficiency in Foreign Exchange Markets |
| 2006 | [physics/0605147v2](https://arxiv.org/abs/physics/0605147v2) | Multifractal Model of Asset Returns versus real stock market dynamics |
| 2006 | [physics/0608009v1](https://arxiv.org/abs/physics/0608009v1) | Multifractal Properties of the Ukraine Stock Market |
| 2006 | [physics/0607167v1](https://arxiv.org/abs/physics/0607167v1) | Non-extensive Behavior of a Stock Market Index at Microscopic Time Scales |
| 2006 | [physics/0606005v1](https://arxiv.org/abs/physics/0606005v1) | On the gap between an empirical distribution and an exponential distribution of waiting times for price changes in a financial market |
| 2006 | [physics/0611159v3](https://arxiv.org/abs/physics/0611159v3) | Phase transition in the globalization of trade |
| 2006 | [physics/0603173v1](https://arxiv.org/abs/physics/0603173v1) | Power Laws and Gaussians for Stock Market Fluctuations |
| 2006 | [physics/0609210v2](https://arxiv.org/abs/physics/0609210v2) | Scale invariant multiplier and multifractality of absolute returns in stock markets |
| 2006 | [physics/0601171v2](https://arxiv.org/abs/physics/0601171v2) | Scale-free avalanche dynamics in the stock market |
| 2006 | [cond-mat/0605623v2](https://arxiv.org/abs/cond-mat/0605623v2) | Statistical mechanics of combinatorial auctions |
| 2006 | [physics/0607202v2](https://arxiv.org/abs/physics/0607202v2) | Stock price fluctuations and the mimetic behaviors of traders |
| 2006 | [physics/0609088v3](https://arxiv.org/abs/physics/0609088v3) | The Why of the Applicability of Statistical Physics to Economics |
| 2006 | [math/0610219v1](https://arxiv.org/abs/math/0610219v1) | The minimal entropy martingale measure for general Barndorff-Nielsen/Shephard models |
| 2006 | [physics/0612068v2](https://arxiv.org/abs/physics/0612068v2) | Topological Properties of the Minimal Spanning Tree in Korean and American Stock Markets |
| 2005 | [physics/0505047v1](https://arxiv.org/abs/physics/0505047v1) | Analyzing money distributions in `ideal gas' models of markets |
| 2005 | [physics/0506103v1](https://arxiv.org/abs/physics/0506103v1) | Boltzmann-Gibbs Distribution of Fortune and Broken Time-Reversible Symmetry in Econodynamics |
| 2005 | [cond-mat/0501261v1](https://arxiv.org/abs/cond-mat/0501261v1) | Five Years of Continuous-time Random Walks in Econophysics |
| 2005 | [nlin/0507037v1](https://arxiv.org/abs/nlin/0507037v1) | Forecasting non-stationary financial time series through genetic algorithm |
| 2005 | [physics/0505079v1](https://arxiv.org/abs/physics/0505079v1) | Fundamental Factors versus Herding in the 2000-2005 US Stock Market and Prediction |
| 2005 | [cond-mat/0503607v2](https://arxiv.org/abs/cond-mat/0503607v2) | Importance of Positive Feedbacks and Over-confidence in a Self-Fulfilling Ising Model of Financial Markets |
| 2005 | [physics/0505115v1](https://arxiv.org/abs/physics/0505115v1) | Money Exchange Model and a general Outlook |
| 2005 | [cond-mat/0502151v1](https://arxiv.org/abs/cond-mat/0502151v1) | On the connection between financial processes with stochastic volatility and nonextensive statistical mechanics |
| 2005 | [physics/0503024v1](https://arxiv.org/abs/physics/0503024v1) | Power-law distributions in economics: a nonextensive statistical approach |
| 2005 | [physics/0510058v3](https://arxiv.org/abs/physics/0510058v3) | Scaling theory of temporal correlations and size dependent fluctuations in the traded value of stocks |
| 2005 | [cond-mat/0501513v4](https://arxiv.org/abs/cond-mat/0501513v4) | Self-Similar Log-Periodic Structures in Western Stock Markets from 2000 |
| 2005 | [cond-mat/0503156v1](https://arxiv.org/abs/cond-mat/0503156v1) | Simulations of financial markets in a Potts-like model |
| 2005 | [physics/0503163v1](https://arxiv.org/abs/physics/0503163v1) | Stock Mechanics: a classical approach |
| 2005 | [physics/0506098v1](https://arxiv.org/abs/physics/0506098v1) | Stock mechanics: predicting recession in S&P500, DJIA, and NASDAQ |
| 2005 | [physics/0510047v1](https://arxiv.org/abs/physics/0510047v1) | Time series of stock price and of two fractal overlap: Anticipating market crashes? |
| 2004 | [cond-mat/0408143v1](https://arxiv.org/abs/cond-mat/0408143v1) | A Guided Walk Down Wall Street: an Introduction to Econophysics |
| 2004 | [cond-mat/0401181v2](https://arxiv.org/abs/cond-mat/0401181v2) | Bridging the ARCH model for finance and nonextensive entropy |
| 2004 | [nlin/0412038v2](https://arxiv.org/abs/nlin/0412038v2) | Multifractal Behavior of the Korean Stock-market Index KOSPI |
| 2004 | [cond-mat/0405173v1](https://arxiv.org/abs/cond-mat/0405173v1) | Multifractal Measures for the Yen-Dollar Exchange Rate |
| 2004 | [cond-mat/0403624v1](https://arxiv.org/abs/cond-mat/0403624v1) | On anomalous distributions in intra-day financial time series and Non-extensive Statistical Mechanics |
| 2004 | [cond-mat/0409179v2](https://arxiv.org/abs/cond-mat/0409179v2) | On distribution of number of trades in different time windows in the stock market |
| 2004 | [cond-mat/0401210v1](https://arxiv.org/abs/cond-mat/0401210v1) | Origin of Crashes in 3 US stock markets: Shocks and Bubbles |
| 2004 | [cond-mat/0408625v1](https://arxiv.org/abs/cond-mat/0408625v1) | Phase Transition of Dynamical Herd Behaviors in Financial Markets |
| 2004 | [cond-mat/0412014v1](https://arxiv.org/abs/cond-mat/0412014v1) | Power Law Distributions for Stock Prices in Financial Markets |
| 2004 | [cond-mat/0407418v1](https://arxiv.org/abs/cond-mat/0407418v1) | Scaling Properites of Price Changes for Korean Stock Indices |
| 2004 | [cond-mat/0405257v2](https://arxiv.org/abs/cond-mat/0405257v2) | Self-Organized Criticality and Stock Market Dynamics: an Empirical Study |
| 2004 | [cond-mat/0410289v1](https://arxiv.org/abs/cond-mat/0410289v1) | Statistical analysis of the price index of Tehran Stock Exchange |
| 2004 | [cond-mat/0403465v1](https://arxiv.org/abs/cond-mat/0403465v1) | Stylized Statistical Facts of Indonesian Financial Data: Empirical Study of Several Stock Indexes in Indonesia |
| 2004 | [cond-mat/0406310v1](https://arxiv.org/abs/cond-mat/0406310v1) | Volatility of Linear and Nonlinear Time Series |
| 2004 | [cond-mat/0405390v1](https://arxiv.org/abs/cond-mat/0405390v1) | Zipf's Law Distributions for Korean Stock Prices |
| 2003 | [cond-mat/0312404v2](https://arxiv.org/abs/cond-mat/0312404v2) | A mechanism leading bubbles to crashes: the case of Japan's land markets |
| 2003 | [cond-mat/0312489v1](https://arxiv.org/abs/cond-mat/0312489v1) | Activity autocorrelation in financial markets. A comparative study between several models |
| 2003 | [cond-mat/0312413v2](https://arxiv.org/abs/cond-mat/0312413v2) | Asymptotic behavior of the Daily Increment Distribution of the IPC, the Mexican Stock Market Index |
| 2003 | [cond-mat/0303271v1](https://arxiv.org/abs/cond-mat/0303271v1) | Bose-Einstein Condensation in Financial Systems |
| 2003 | [cond-mat/0312658v1](https://arxiv.org/abs/cond-mat/0312658v1) | Causal Slaving of the U.S. Treasury Bond Yield Antibubble by the Stock Market Antibubble of August 2000 |
| 2003 | [cond-mat/0312357v1](https://arxiv.org/abs/cond-mat/0312357v1) | Effects of Randomness on Power Law Tails in Multiplicatively Interacting Stochastic Processes |
| 2003 | [physics/0301007v1](https://arxiv.org/abs/physics/0301007v1) | Finite-Time Singularity Signature of Hyperinflation |
| 2003 | [cond-mat/0303568v1](https://arxiv.org/abs/cond-mat/0303568v1) | Fitting the Power-law Distribution to the Mexican Stock Market index data |
| 2003 | [cond-mat/0304143v2](https://arxiv.org/abs/cond-mat/0304143v2) | Herd Behavior of Returns in the Futures Exchange Market |
| 2003 | [cond-mat/0309404v1](https://arxiv.org/abs/cond-mat/0309404v1) | Langevin processes, agent models and socio-economic systems |
| 2003 | [cond-mat/0305270v1](https://arxiv.org/abs/cond-mat/0305270v1) | Multifractal Features in the Foreign Exchange and Stock Markets |
| 2003 | [cond-mat/0308012v1](https://arxiv.org/abs/cond-mat/0308012v1) | Multifractal Properties of Price Fluctuations of Stocks and Commodities |
| 2003 | [cond-mat/0301307v1](https://arxiv.org/abs/cond-mat/0301307v1) | Nonextensive statistical mechanics and economics |
| 2003 | [cond-mat/0312406v2](https://arxiv.org/abs/cond-mat/0312406v2) | Power law for ensembles of stock prices |
| 2003 | [cond-mat/0312560v2](https://arxiv.org/abs/cond-mat/0312560v2) | Power law for the calm-time interval of price changes |
| 2003 | [cond-mat/0306605v1](https://arxiv.org/abs/cond-mat/0306605v1) | Risk aversion in financial decisions: A nonextensive approach |
| 2003 | [cond-mat/0308013v1](https://arxiv.org/abs/cond-mat/0308013v1) | Scale-Dependent Price Fluctuations for the Indian Stock Market |
| 2003 | [cond-mat/0302468v2](https://arxiv.org/abs/cond-mat/0302468v2) | Scaling Law for the Distribution of Fluctuations of Share Volume |
| 2003 | [cond-mat/0302470v2](https://arxiv.org/abs/cond-mat/0302470v2) | Scaling behavior in land markets |
| 2003 | [cond-mat/0311372v2](https://arxiv.org/abs/cond-mat/0311372v2) | Stochastic Cellular Automata Model for Stock Market Dynamics |
| 2003 | [cond-mat/0312568v1](https://arxiv.org/abs/cond-mat/0312568v1) | Superstatistics in Econophysics |
| 2003 | [cond-mat/0310092v2](https://arxiv.org/abs/cond-mat/0310092v2) | Testing the Stability of the 2000-2003 US Stock Market "Antibubble" |
| 2003 | [cond-mat/0305004v1](https://arxiv.org/abs/cond-mat/0305004v1) | The US 2000-2003 Market Descent: Clarifications |
| 2003 | [cond-mat/0301068v1](https://arxiv.org/abs/cond-mat/0301068v1) | The average shape of a fluctuation: universality in excursions of stochastic processes |
| 2003 | [cond-mat/0304469v1](https://arxiv.org/abs/cond-mat/0304469v1) | Using Recurrent Neural Networks To Forecasting of Forex |
| 2003 | [cond-mat/0302434v1](https://arxiv.org/abs/cond-mat/0302434v1) | Using the Scaling Analysis to Characterize Financial Markets |
| 2002 | [physics/0205053v2](https://arxiv.org/abs/physics/0205053v2) | A Quantum Approach to Stock Price Fluctuations |
| 2002 | [cond-mat/0205320v1](https://arxiv.org/abs/cond-mat/0205320v1) | Cont-Bouchaud percolation model including Tobin tax |
| 2002 | [cond-mat/0206047v1](https://arxiv.org/abs/cond-mat/0206047v1) | Endogeneous Versus Exogeneous Shocks in Systems with Memory |
| 2002 | [cond-mat/0212010v2](https://arxiv.org/abs/cond-mat/0212010v2) | Evidence of a Worldwide Stock Market Log-Periodic Anti-Bubble Since Mid-2000 |
| 2002 | [cond-mat/0205482v1](https://arxiv.org/abs/cond-mat/0205482v1) | Financial multifractality and its subtleties: an example of DAX |
| 2002 | [cond-mat/0201219v1](https://arxiv.org/abs/cond-mat/0201219v1) | Firms Growth Dynamics, Competition and Power Law Scaling |
| 2002 | [cond-mat/0208464v1](https://arxiv.org/abs/cond-mat/0208464v1) | Long-Time Fluctuations in a Dynamical Model of Stock Market Indices |
| 2002 | [cond-mat/0205083v1](https://arxiv.org/abs/cond-mat/0205083v1) | Market simulation with hierarchical information flux |
| 2002 | [cond-mat/0202028v1](https://arxiv.org/abs/cond-mat/0202028v1) | Non-Lévy Distribution of Commodity Price Fluctuations |
| 2002 | [cond-mat/0204295v1](https://arxiv.org/abs/cond-mat/0204295v1) | Predicting critical crashes? A new restriction for the free variables |
| 2001 | [cond-mat/0104260v1](https://arxiv.org/abs/cond-mat/0104260v1) | Correlations Between Reconstructed EUR Exchange Rates vs. CHF, DKK, GBP, JPY and USD |
| 2001 | [cond-mat/0103033v1](https://arxiv.org/abs/cond-mat/0103033v1) | False EUR exchange rates vs. DKK, CHF, JPY and USD. What is a strong currency? |
| 2001 | [cond-mat/0108017v1](https://arxiv.org/abs/cond-mat/0108017v1) | Financial Market Dynamics |
| 2001 | [cond-mat/0109410v1](https://arxiv.org/abs/cond-mat/0109410v1) | Imitation and contrarian behavior: hyperbolic bubbles, crashes and chaos |
| 2001 | [cond-mat/0104318v1](https://arxiv.org/abs/cond-mat/0104318v1) | Market price simulator based on analog electrical circuit |
| 2001 | [nlin/0107057v3](https://arxiv.org/abs/nlin/0107057v3) | On multifractality and fractional derivatives |
| 2001 | [cond-mat/0102423v2](https://arxiv.org/abs/cond-mat/0102423v2) | Power Laws of Wealth, Market Order Volumes and Market Returns |
| 2001 | [cond-mat/0111257v2](https://arxiv.org/abs/cond-mat/0111257v2) | Power law relaxation in a complex system: Omori law after a financial market crash |
| 2001 | [cond-mat/0108452v1](https://arxiv.org/abs/cond-mat/0108452v1) | Scaling in the Bombay Stock Exchange Index |
| 2001 | [cond-mat/0106520v1](https://arxiv.org/abs/cond-mat/0106520v1) | Significance of log-periodic precursors to financial crashes |
| 2001 | [cond-mat/0110201v1](https://arxiv.org/abs/cond-mat/0110201v1) | Stability of money: Phase transitions in an Ising economy |
| 2001 | [cond-mat/0110273v1](https://arxiv.org/abs/cond-mat/0110273v1) | Stochastic Multiplicative Processes for Financial Markets |
| 2000 | [cond-mat/0003357v1](https://arxiv.org/abs/cond-mat/0003357v1) | A dynamical model describing stock market price distributions |
| 2000 | [cond-mat/0101001v2](https://arxiv.org/abs/cond-mat/0101001v2) | A simple model of price formation |
| 2000 | [cond-mat/0011088v1](https://arxiv.org/abs/cond-mat/0011088v1) | Fokker-Planck equation of distributions of financial returns and power laws |
| 2000 | [cond-mat/0010222v1](https://arxiv.org/abs/cond-mat/0010222v1) | Power Laws are Boltzmann Laws in Disguise |
| 2000 | [cond-mat/0008026v1](https://arxiv.org/abs/cond-mat/0008026v1) | Power, Levy, Exponential and Gaussian Regimes in Autocatalytic Financial Systems |
| 2000 | [cond-mat/0004001v1](https://arxiv.org/abs/cond-mat/0004001v1) | Stock Market Speculation: Spontaneous Symmetry Breaking of Economic Valuation |
| 1999 | [cond-mat/9901268v1](https://arxiv.org/abs/cond-mat/9901268v1) | Financial ``Anti-Bubbles'': Log-Periodicity in Gold and Nikkei collapses |
| 1999 | [cond-mat/9909439v1](https://arxiv.org/abs/cond-mat/9909439v1) | Market Fluctuations: multiplicative and percolation models, size effects and predictions |
| 1999 | [cond-mat/9910141v1](https://arxiv.org/abs/cond-mat/9910141v1) | On Rational Bubbles and Fat Tails |
| 1999 | [cond-mat/9905169v1](https://arxiv.org/abs/cond-mat/9905169v1) | Scaling transformation and probability distributions for financial time series |
| 1997 | [cond-mat/9705087v1](https://arxiv.org/abs/cond-mat/9705087v1) | Scaling in stock market data: stable laws and beyond |

