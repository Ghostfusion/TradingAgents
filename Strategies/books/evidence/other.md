# Evidence pack — Other / Unclassified (`other`)

Annotated sweep rows for this category: **269** (high 5 · med 78 · low 186).

Source: the complete abstract-level sweep of all 4,372 corpus papers - one annotated row per paper, from title + abstract. The per-slice working files are not shipped; these packs are that sweep, fanned out per category. `repo surface` names a real module from `tradingagents/strategies/` where the sweep judged the paper relevant.

## High relevance (5)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2607.28230v2](https://arxiv.org/abs/2607.28230v2) | Finite-horizon multiplicative growth with an absorbing boundary yields optimal exposure compressed below the Kelly fraction near ruin; unconstrained CRRA benchmarks misread this geometry as elevated risk aversion. | strategies/size.py |
| 2020 | [2001.04237v1](https://arxiv.org/abs/2001.04237v1) | Explains relations between averages, moving averages and the exponential moving average, and defines the MACD trend indicator, discussing its mathematical properties. | strategies/extended_indicators.py |
| 2020 | [2010.01157v1](https://arxiv.org/abs/2010.01157v1) | Distance and cointegration pairs trading on US equities 1990-2020 fails to beat the market unless tuned but excels in bear markets. | `strategies/mean_reversion.py` |
| 2019 | [1906.05057v2](https://arxiv.org/abs/1906.05057v2) | Proposes a distance measure incorporating time-varying lead-lag relationships for pairs-trading pair selection; combined with SSD it consistently yields the best profits on Indian and American datasets. | `strategies/mean_reversion.py` |
| 2008 | [0802.0984v2](https://arxiv.org/abs/0802.0984v2) | Proposes the Moving Mini-Max technical indicator emphasising price maxima/minima with inherent smoothing for mechanical rules and chart-pattern analysis. | `strategies/extended_indicators.py` |

## Medium relevance (78)

| year | id | takeaway | repo surface |
| --- | --- | --- | --- |
| 2026 | [2603.13632v1](https://arxiv.org/abs/2603.13632v1) | Shows the Kelly rule fails to maximize average growth under time-changed semi-martingale returns unless log-returns are normal; Kelly bets too large, with error growing in stochastic-clock variance. | `strategies/risk_sizing.py` |
| 2025 | [2512.07887v1](https://arxiv.org/abs/2512.07887v1) | ARDL analysis (2008-2015) of BIST-100 and Turkish CDS finds bidirectional short/long-run effects: 1 TL CDS rise cuts BIST-100 ~22.5 TL short-run/~85.5 TL long-run, with interest, inflation, FX and political events significant. | `strategies/credit_spread.py` |
| 2025 | [2503.16470v2](https://arxiv.org/abs/2503.16470v2) | Models Japanese horse-race win odds as an Ornstein-Uhlenbeck process driven by herders (odds-chasing) and fundamentalists (true-probability) bettors; 3450 JRA races reveal a microscopic betting rule and mean-reverting odds convergence paralleling financial markets. | `strategies/mean_reversion.py` |
| 2024 | [2402.05364v2](https://arxiv.org/abs/2402.05364v2) | Coarse-grains Pearson correlation matrices by sector into Guhr matrices; market-state evolution and transition matrices match Pearson while reducing variables by orders of magnitude. | `strategies/covariance_models.py` |
| 2024 | [2403.18126v2](https://arxiv.org/abs/2403.18126v2) | Revisits Baaquie-Bouchaud stiff elastic-string field theory of forward interest rates; parsimonious model reproduces the whole forward-rate-curve correlation structure 1994-2023. | `strategies/fixed_income.py` |
| 2024 | [2405.12991v1](https://arxiv.org/abs/2405.12991v1) | Uses spectral and agglomerative clustering for systematic comparable-company analysis and cost-of-equity computation for public and private firms. | `strategies/peer_universe.py` |
| 2023 | [2309.12082v2](https://arxiv.org/abs/2309.12082v2) | Generalizes geometric Brownian motion to polynomial-drift SDEs; model selection favors q=2, and MCMC potentials show a stable-price well. | `strategies/statistical.py` |
| 2023 | [2301.02692v1](https://arxiv.org/abs/2301.02692v1) | Isotonic recalibration makes regression models auto-calibrated; under a low signal-to-noise ratio the recalibrated functions have low complexity and are explainable. | strategies/calibration.py |
| 2023 | [2301.05080v1](https://arxiv.org/abs/2301.05080v1) | Distance correlation coefficient (zero only if independent) detects nonlinear S&P500 pair associations invisible to Pearson; agglomerative clustering maps market states. | strategies/statistical.py |
| 2023 | [2311.00964v3](https://arxiv.org/abs/2311.00964v3) | SpectralRules finds bi-objective Pareto-optimal fraud-prevention rule sets (precision vs recall) to refine the two-stage rule-mining framework. | `strategies/rule_eval.py` |
| 2022 | [2201.01330v3](https://arxiv.org/abs/2201.01330v3) | Constructs credit spread curves by fitting parametrised survival curves rather than Z-spreads, derives risky-bond valuation avoiding high-price/yield artifacts, and shows how to compute carry, rolldown and relative value. | `strategies/credit_spread.py` |
| 2021 | [2108.10176v1](https://arxiv.org/abs/2108.10176v1) | Defines multivariate self- and cross-exciting jump point processes whose intensities are driven by stochastic jump magnitudes, gives stability conditions and fits S&P 500 and Nikkei data; a nonlinear variant fits best, with crisis-time jump clustering. | `strategies/tail_risk.py` |
| 2020 | [2010.15105v1](https://arxiv.org/abs/2010.15105v1) | Compares price-response-function definitions across correlated markets; finds long-lasting non-Markovian price impact and spread effects. | `strategies/orderflow.py` |
| 2020 | [2004.06586v3](https://arxiv.org/abs/2004.06586v3) | Extends Random Orthogonal Matrix simulation to match Kollo skewness: necessary/sufficient conditions, admissible-value construction, concatenation effect; simulation study. | strategies/covariance_models.py |
| 2020 | [2005.02482v1](https://arxiv.org/abs/2005.02482v1) | Uses Jensen-Shannon divergence between normalized log-return distributions to measure currency similarity, revealing hierarchical FOREX clusters distinct from conventional correlation-based methods. | strategies/hierarchical_risk_parity.py |
| 2019 | [1905.01541v1](https://arxiv.org/abs/1905.01541v1) | Localizes co-jumps in US and European Treasury yield curves via wavelet coefficients; US curves co-jump far more, and co-jump behavior is linked to 103 FOMC and 119 ECB announcements. | `strategies/rate_utils.py` |
| 2019 | [1907.09218v2](https://arxiv.org/abs/1907.09218v2) | Defines generalized statistical arbitrage via sigma-algebra information systems, generalizing Bondarenko; constructs embedded-binomial, follow-the-trend and partition strategies performing well on simulated and market data. | strategies/mean_reversion.py |
| 2019 | [1907.04422v1](https://arxiv.org/abs/1907.04422v1) | Two-way fixed-effects analysis of 250,000+ S&P 100 observations finds evidence of both under- and overreaction and a nonlinear return-trend relation: small positive trends raise returns, larger ones lower them. | `strategies/momentum.py` |
| 2019 | [1907.10306v1](https://arxiv.org/abs/1907.10306v1) | Proves tau-Kendall correlation equals sign-coincidence probability for elliptical distributions; distribution-free tests on China/US/UK/Germany stocks 2003-2014 accept elliptical returns for US/UK/Germany, reject for China. | strategies/statistical.py |
| 2018 | [1803.09432v1](https://arxiv.org/abs/1803.09432v1) | Thermal optimal path method finds a time-dependent lead-lag between onshore CNY and offshore CNH: USD appreciation runs offshore-to-onshore, RMB appreciation the reverse. | `strategies/orderflow.py` |
| 2017 | [1711.04717v2](https://arxiv.org/abs/1711.04717v2) | Evidence that markets trend at medium term and mean-revert over years, with prices within a factor 2 of value, fitting chartist/fundamentalist behavior. | `strategies/mean_reversion.py` |
| 2016 | [1603.01308v2](https://arxiv.org/abs/1603.01308v2) | Dynamic Adaptive Mixture Models sequentially adapt mixture components and composition from data, avoiding simulation, and approximate stochastic dynamic mixtures in financial econometrics. | `strategies/statistical.py` |
| 2016 | [1612.07802v2](https://arxiv.org/abs/1612.07802v2) | Symmetry-guided time definition enforces scale invariance and stationarity of return distributions while consistently quantifying overnight periods. | `strategies/market_session.py` |
| 2015 | [1503.02177v1](https://arxiv.org/abs/1503.02177v1) | Compounding local distributions with their parameter distribution models long-horizon non-stationary time series, illustrated on turbulence and FX data. | `strategies/volatility_models.py` |
| 2015 | [1502.07522v1](https://arxiv.org/abs/1502.07522v1) | Combines cluster analysis and stochastic process analysis to describe high-dimensional financial systems by few dominating variables and recover fixed points via optimization. | `strategies/regime_state.py` |
| 2015 | [1504.06235v1](https://arxiv.org/abs/1504.06235v1) | Stop-and-Reverse-MinMax process analyses lead-lag phase shifts between two series via directional statistics; finds strong FX/commodity/index links with nonzero phase shifts. | `strategies/statistical.py` |
| 2015 | [1503.00556v1](https://arxiv.org/abs/1503.00556v1) | Geometric data analysis plus stochastic modelling identifies the dominating variable of the market correlation structure and links its evolution to historical market events. | `strategies/regime_state.py` |
| 2015 | [1510.07280v1](https://arxiv.org/abs/1510.07280v1) | Models non-stationary volume-price distribution parameters with Kullback-Leibler model selection; an inverse Gamma fits tails and the tail parameter follows an Ornstein-Uhlenbeck process. | `strategies/volatility_models.py` |
| 2015 | [1510.03550v3](https://arxiv.org/abs/1510.03550v3) | Simple stock-selection model shows index outperformance is concentrated in a few stocks, making random active subsets likely to underperform, so indexing works. | `strategies/portfolio.py` |
| 2014 | [1401.1892v2](https://arxiv.org/abs/1401.1892v2) | Applies big-buyer/big-seller price model to 20 Hong Kong banking and real-estate stocks; proposes Follow-the-Big-Buyer and related strategies. | strategies/orderflow.py |
| 2014 | [1409.5321v1](https://arxiv.org/abs/1409.5321v1) | Empirical statistics of the automatically calibrated 1-2-3 trend indicator across EUR-USD, DAX futures, gold and crude oil time scales. | strategies/technical_factors.py |
| 2013 | [1302.3870v1](https://arxiv.org/abs/1302.3870v1) | Second-order stock market model gives each stock return/variance parameters depending on both rank and name, with estimation methods and stability properties for idiosyncratic analysis. | `strategies/cross_section.py` |
| 2013 | [1311.0657v1](https://arxiv.org/abs/1311.0657v1) | Detrending moving-average cross-correlation coefficient measures non-stationary series correlation, bounded in [-1,1] and matching true correlation in simulation. | strategies/statistical.py |
| 2013 | [1310.3984v1](https://arxiv.org/abs/1310.3984v1) | DCCA coefficient estimates correlation of non-stationary series accurately regardless of fractional differencing parameter and beats Pearson. | strategies/complexity.py |
| 2013 | [1309.0602v1](https://arxiv.org/abs/1309.0602v1) | Segmentation of univariate series via Fisher's exact test; change point detected at minimum p-value, applied to FX rates and shuffled controls. | strategies/regime_state.py |
| 2012 | [1205.0332v2](https://arxiv.org/abs/1205.0332v2) | Recursive Gaussian-mixture segmentation of Tokyo Stock Exchange prices 2000-2012: quintile volatility counts track macro conditions and spike after the March 2011 earthquake. | `strategies/regime_state.py` |
| 2012 | [1211.3060v1](https://arxiv.org/abs/1211.3060v1) | Monotonic "elemental trends" in DJIA, NASDAQ and IPC have duration distributions differing from the no-memory expectation per Anderson-Darling tests. | `strategies/momentum.py` |
| 2012 | [1211.2754v1](https://arxiv.org/abs/1211.2754v1) | Time-difference relevance plus PageRank finds the leader index among 21 Chinese coal stocks; large well-managed firms show return antecedence and higher scores. | `strategies/peer_universe.py` |
| 2012 | [1204.0426v1](https://arxiv.org/abs/1204.0426v1) | Weekly FX data 2007-2010 show fluctuation scaling between mean quote/trade counts and standard deviations except during market shocks; scaling index tracks average cross-correlation. | `strategies/covariance_models.py` |
| 2012 | [1208.2878v1](https://arxiv.org/abs/1208.2878v1) | Time-series clustering comparison of 1-month LIBOR and SIBOR 2005-2011 concludes SIBOR was not manipulated the way LIBOR was. | `strategies/data_quality.py` |
| 2012 | [1206.1272v3](https://arxiv.org/abs/1206.1272v3) | Spin-model mapping defines negative Kelvin temperature for stocks; NYSE negative-temperature peaks correlate with subsequent index moves and an autocorrelation decays as temperature rises. | `strategies/regime.py` |
| 2012 | [1205.0336v1](https://arxiv.org/abs/1205.0336v1) | Multivariate Gaussian-mixture segmentation with Jensen-Shannon divergence discriminator detects major international economic events in 30 FX pairs, 2001-2011. | `strategies/regime_state.py` |
| 2012 | [1206.5224v4](https://arxiv.org/abs/1206.5224v4) | Proposes a volume-weighted historical-price index for buy/sell price ranges and reports significantly improved performance of agents trading real data. | `strategies/technical_factors.py` |
| 2012 | [1209.6369v1](https://arxiv.org/abs/1209.6369v1) | Sovereign-default equilibrium model relates Greek debt/GDP to interest rates (default at 2× GDP) and projects default dates for Greece, Portugal, Ireland, Spain and Italy. | `strategies/credit_spread.py` |
| 2012 | [1201.3083v3](https://arxiv.org/abs/1201.3083v3) | Nonlinear stochastic model with multiplicativity exponent above one maps to a Bessel process; derives the burst-duration PDF and applies it to return bursts. | `strategies/complexity.py` |
| 2012 | [1209.0900v1](https://arxiv.org/abs/1209.0900v1) | Wavelet coherence on biofuels 2003-2011 finds ethanol-corn and biodiesel-diesel coupled at low frequencies, shifting to high frequencies during the food crisis. | `strategies/covariance_models.py` |
| 2011 | [1108.5596v1](https://arxiv.org/abs/1108.5596v1) | Applies factorial-moment intermittency analysis to prices: second-order moment shows non-Gaussian fluctuation sensitivity below a 4-hour resolution threshold. | `strategies/complexity.py` |
| 2011 | [1111.2038v1](https://arxiv.org/abs/1111.2038v1) | Mexican IPC daily log-returns 2000-2010 reject normality but not an α-stable Lévy law at 5%; estimated tail decay depends strongly on sample size. | `strategies/tail_risk.py` |
| 2011 | [1110.1006v1](https://arxiv.org/abs/1110.1006v1) | Large futures dataset shows high-frequency log-returns fit a t-distribution with ν≈3, robust across series and sampling frequencies below one hour. | `strategies/tail_risk.py` |
| 2011 | [1102.5431v1](https://arxiv.org/abs/1102.5431v1) | Derives an LM-type test for a change in mean under unknown-form heteroskedasticity; Monte Carlo shows good size/power, illustrated on the S&P 500 daily closing level. | strategies/statistical.py |
| 2010 | [1011.2674v1](https://arxiv.org/abs/1011.2674v1) | Uses detrended cross-correlation analysis on 59 years of S&P 500 to find power-law price-volume cross-correlations, estimating volume tail exponent ~3 and an approximate inverse cubic law across indices. | strategies/orderflow.py |
| 2010 | [1005.0378v1](https://arxiv.org/abs/1005.0378v1) | Dow Jones 1991-2008 pairwise Pearson correlations show stocks move more correlatedly when the index falls than when it rises, a significant asymmetry attributed to a constant-fear factor. | strategies/breadth_depth.py |
| 2010 | [1004.0685v3](https://arxiv.org/abs/1004.0685v3) | Fuzzy score discriminates good/bad Russian corporate bond issuers from accounting data; reports in-sample Gini AR about 73% and a simple mapping to implied external credit ratings. | strategies/credit_spread.py |
| 2010 | [1004.4522v1](https://arxiv.org/abs/1004.4522v1) | Tests random-matrix extraction of meaningful input-output correlations between large-dimensional variables; applies a toy model to Polish macroeconomic data as an alternative to classical cointegration. | strategies/covariance_models.py |
| 2009 | [0910.2909v3](https://arxiv.org/abs/0910.2909v3) | Models the statistical error from observation asynchrony in return correlations and shows it is a major cause of the Epps effect; quantifies and compensates it using only trading prices and trading times. | strategies/covariance_models.py |
| 2008 | [0804.1039v1](https://arxiv.org/abs/0804.1039v1) | Examines whether Feller conditions matter in discrete-time multivariate macro-finance term-structure models, using German data and affine yield approximations. | `strategies/rate_utils.py` |
| 2008 | [0806.2617v2](https://arxiv.org/abs/0806.2617v2) | Studies an ARCH-type heteroskedastic process with q-exponential variance memory; derives self-correlation, kurtosis, multiscaling, first-passage times and an asymmetric leverage-effect variant. | `strategies/volatility_models.py` |
| 2007 | [0709.3261v1](https://arxiv.org/abs/0709.3261v1) | Analyzes London Stock Exchange member trading sign sequences, finding persistent correlations structured into correlated and anti-correlated clusters of institutions. | `strategies/orderflow.py` |
| 2007 | [0709.0281v1](https://arxiv.org/abs/0709.0281v1) | Proposes detrended cross-correlation analysis (DXA) to measure power-law cross-correlations between two non-stationary time series. | `strategies/statistical.py` |
| 2007 | [physics/0701110v3](https://arxiv.org/abs/physics/0701110v3) | Investigates the Epps effect (decaying short-window return correlations), confirming trading asynchronicity matters but is alone insufficient to explain the whole effect even where lead-lag is negligible. | `strategies/covariance_models.py` |
| 2007 | [physics/0703208v2](https://arxiv.org/abs/physics/0703208v2) | Measures distributions of short-term high-frequency price-trend lengths, finds they contradict an uncorrelated stochastic process, and proposes a simple memory model giving qualitative agreement with real data. | `strategies/momentum.py` |
| 2006 | [physics/0601002v1](https://arxiv.org/abs/physics/0601002v1) | Inverse statistics across 2/3 of DJIA stocks show the gain/loss asymmetry is absent in individual stocks and their average, pointing to market-wide collective synchronized movement. | `strategies/alpha_eval.py` |
| 2006 | [physics/0612059v3](https://arxiv.org/abs/physics/0612059v3) | Proposes risk evaluation via a potential/objective-function transformation of the covariance matrix that rescales assets to similar distributions; tested on New York and Warsaw exchanges. | `strategies/covariance_models.py` |
| 2006 | [physics/0603139v1](https://arxiv.org/abs/physics/0603139v1) | Nikkei 225 absolute log-returns (1975-2002) are power-law in the inflationary period but exponential in the deflationary one; a two-group fundamentalist/noise-trader model reproduces both depending on relative trader counts. | `strategies/regime.py` |
| 2006 | [physics/0604137v2](https://arxiv.org/abs/physics/0604137v2) | Waiting-time up-down asymmetry appears in indices but not individual stocks; a market model where randomly fluctuating stocks occasionally synchronize short-term draw-downs, parameterized by a 'fear factor', reproduces it. | `strategies/breadth_depth.py` |
| 2005 | [physics/0502119v1](https://arxiv.org/abs/physics/0502119v1) | Develops a generalized mean-reverting stochastic model driven by multiplicative and additive Wiener processes; analyzes its Ito-Langevin long-time density, showing additive-multiplicative processes realistically describe empirical volatility distributions. | `strategies/volatility_models.py` |
| 2005 | [physics/0511129v1](https://arxiv.org/abs/physics/0511129v1) | A sliding-window Langevin fit of a time-dependent linear restoring force describes S&P 500 daily log-returns (1950-1999), linking the mean-reverting drift to return autocorrelation. | `strategies/mean_reversion.py` |
| 2005 | [physics/0511091v1](https://arxiv.org/abs/physics/0511091v1) | Inverse-statistics optimal investment horizon: the gain/loss asymmetry seen in the DJIA vanishes for 2/3 of individual DJIA stocks, implying it comes from market-wide cooperative synchronization. | `strategies/alpha_eval.py` |
| 2005 | [physics/0510112v2](https://arxiv.org/abs/physics/0510112v2) | A nonextensive generalized Kullback-Leibler measure of Dow 30 traded volume decays slowly with lag, implying nonlinearities; a proposed dynamical mechanism matches the empirical stationary PDF. | `strategies/statistical.py` |
| 2005 | [physics/0503014v1](https://arxiv.org/abs/physics/0503014v1) | Applies Minimum Spanning Trees to the global FX market, showing the tree captures global FX dynamics and identifies momentarily dominant and dependent currencies, giving machinery for which currencies are 'in play'. | `strategies/triadic_stress.py` |
| 2004 | [cond-mat/0409375v2](https://arxiv.org/abs/cond-mat/0409375v2) | Diffusion model with rate depending on deviation from a consensus price gives an analytic return distribution that matches computed histograms. | strategies/mean_reversion.py |
| 2004 | [cond-mat/0403662v1](https://arxiv.org/abs/cond-mat/0403662v1) | Intertrade times of 30 US stocks fit a Weibull and collapse to one universal curve; power-law correlated, suggesting they drive price formation. | strategies/orderflow.py |
| 2004 | [cond-mat/0403333v2](https://arxiv.org/abs/cond-mat/0403333v2) | Stochastic-geometry embedding of yearly S&P500 batches in low dimensions; crises reinforce correlation structure but can weaken sector clustering (1987 vs 2001). | strategies/triadic_stress.py |
| 2004 | [cond-mat/0403469v1](https://arxiv.org/abs/cond-mat/0403469v1) | Intertrade-time process is non-Markovian with long-range memory; intervals show power-like correlation (Moscow MICEX and Xetra data). | strategies/orderflow.py |
| 2003 | [cond-mat/0301268v1](https://arxiv.org/abs/cond-mat/0301268v1) | Estimates Fokker-Planck drift and diffusion (Kramers-Moyal) for NIKKEI, NASDAQ and FX; establishes Markov nature and notes a distinctive NASDAQ diffusion. | strategies/statistical.py |
| 2002 | [cond-mat/0211039v1](https://arxiv.org/abs/cond-mat/0211039v1) | Inverse statistics: the investment-horizon distribution (waiting time to reach a return level) peaks at an optimal horizon; gain-loss asymmetry strongest at short horizons. | strategies/alpha_eval.py |
| 2001 | [cond-mat/0104369v1](https://arxiv.org/abs/cond-mat/0104369v1) | Reviews empirical and theoretical evidence that financial time series are complex in temporal and ensemble properties, with extreme trading days behaving distinctly from normal ones. | strategies/complexity.py |
| 1999 | [cond-mat/9912051v1](https://arxiv.org/abs/cond-mat/9912051v1) | Price changes as fluctuating diffusion: the transaction count (collisions) is power-law long-range correlated and drives the absolute-return correlations; local variance drives the tails. | strategies/orderflow.py |

## Low relevance / background (186)

| year | id | title |
| --- | --- | --- |
| 2026 | [2604.11413v1](https://arxiv.org/abs/2604.11413v1) | A Herding-Based Model of Technological Transfer and Economic Convergence: Evidence from Central and Eastern Europe |
| 2026 | [2608.03088v1](https://arxiv.org/abs/2608.03088v1) | A New Approach to Goodness of Fit for Ergodic Markov Processes |
| 2026 | [2603.16720v2](https://arxiv.org/abs/2603.16720v2) | Discrimination-insensitive pricing |
| 2026 | [2606.04715v1](https://arxiv.org/abs/2606.04715v1) | How the interpolation of life tables affects the decomposition of life insurance surplus |
| 2026 | [2603.25338v2](https://arxiv.org/abs/2603.25338v2) | Optimal threshold resetting in collective diffusive search |
| 2026 | [2605.02248v1](https://arxiv.org/abs/2605.02248v1) | Statistics of a multi-factor function from its Fourier transform |
| 2026 | [2608.06048v1](https://arxiv.org/abs/2608.06048v1) | Thermodynamic statistics of given names in USA and France |
| 2025 | [2505.13019v2](https://arxiv.org/abs/2505.13019v2) | Characterizing asymmetric and bimodal long-term financial return distributions through quantum walks |
| 2025 | [2501.16793v1](https://arxiv.org/abs/2501.16793v1) | Considerations on the use of financial ratios in the study of family businesses |
| 2025 | [2504.05912v3](https://arxiv.org/abs/2504.05912v3) | Financial resilience of agricultural and food production companies in Spain: A compositional cluster analysis of the impact of the Ukraine-Russia war (2021-2023) |
| 2025 | [2501.03434v2](https://arxiv.org/abs/2501.03434v2) | How to verify that a given process is a Lévy-Driven Ornstein-Uhlenbeck Process |
| 2025 | [2502.14479v5](https://arxiv.org/abs/2502.14479v5) | Modelling the term-structure of default risk under IFRS 9 within a multistate regression framework |
| 2025 | [2509.09415v1](https://arxiv.org/abs/2509.09415v1) | Note on pre-taxation reported data by UK FTSE-listed companies. A search for Benford's laws compatibility |
| 2025 | [2504.07021v1](https://arxiv.org/abs/2504.07021v1) | Polyspectral Mean based Time Series Clustering of Indian Stock Market |
| 2025 | [2504.13501v4](https://arxiv.org/abs/2504.13501v4) | Target Search Optimization by Threshold Resetting |
| 2024 | [2403.19502v2](https://arxiv.org/abs/2403.19502v2) | On the potential of quantum walks for modeling financial return distributions |
| 2024 | [2410.02987v2](https://arxiv.org/abs/2410.02987v2) | Parrondo's effects with aperiodic protocols |
| 2024 | [2405.00046v1](https://arxiv.org/abs/2405.00046v1) | Synchronization in a market model with time delays |
| 2024 | [2402.04138v1](https://arxiv.org/abs/2402.04138v1) | TAC Method for Fitting Exponential Autoregressive Models and Others: Applications in Economy and Finance |
| 2024 | [2402.11066v1](https://arxiv.org/abs/2402.11066v1) | Towards Financially Inclusive Credit Products Through Financial Time Series Clustering |
| 2024 | [2409.11524v1](https://arxiv.org/abs/2409.11524v1) | Unlocking NACE Classification Embeddings with OpenAI for Enhanced Analysis and Processing |
| 2023 | [2311.10738v1](https://arxiv.org/abs/2311.10738v1) | Approximation of supply curves |
| 2023 | [2307.14049v1](https://arxiv.org/abs/2307.14049v1) | Capital Structure Theories and its Practice, A study with reference to select NSE listed public sectors banks, India |
| 2023 | [2303.06603v3](https://arxiv.org/abs/2303.06603v3) | Correlation between upstreamness and downstreamness in random global value chains |
| 2023 | [2302.13781v1](https://arxiv.org/abs/2302.13781v1) | Distribution in the Geometrically Growing System and Its Evolution |
| 2023 | [2311.14738v1](https://arxiv.org/abs/2311.14738v1) | The Impact Of Interest Rates On Firms Financial Decisions |
| 2023 | [2308.14215v1](https://arxiv.org/abs/2308.14215v1) | TimeTrail: Unveiling Financial Fraud Patterns through Temporal Correlation Analysis |
| 2023 | [2301.04455v1](https://arxiv.org/abs/2301.04455v1) | Utilizing Technical Data to Discover Similar Companies in Dhaka Stock Exchange |
| 2022 | [2211.16151v1](https://arxiv.org/abs/2211.16151v1) | Business-cycles and Cash-on-Market: Pre-money Startup Valuation in the Macroeconomic Environment |
| 2022 | [2204.10243v4](https://arxiv.org/abs/2204.10243v4) | Heterogeneous rarity patterns drive price dynamics in NFT collections |
| 2022 | [2212.05933v2](https://arxiv.org/abs/2212.05933v2) | Nostradamus: Weathering Worth |
| 2022 | [2212.12044v2](https://arxiv.org/abs/2212.12044v2) | Reduced-order autoregressive dynamics of a complex financial system: a PCA-based approach |
| 2022 | [2205.07563v2](https://arxiv.org/abs/2205.07563v2) | Resemblance of the power-law scaling behavior of a non-Markovian and nonlinear point processes |
| 2022 | [2207.04867v2](https://arxiv.org/abs/2207.04867v2) | The Lepto-Variance of Stock Returns |
| 2022 | [2212.07944v4](https://arxiv.org/abs/2212.07944v4) | Variable Clustering via Distributionally Robust Nodewise Regression |
| 2022 | [2204.04794v1](https://arxiv.org/abs/2204.04794v1) | Willingness to pay, surplus and Insurance policy under dual theory |
| 2021 | [2109.04324v1](https://arxiv.org/abs/2109.04324v1) | A Tale of Two (and More) Altruists |
| 2021 | [2110.03512v1](https://arxiv.org/abs/2110.03512v1) | Application of DEA in International Market Selection for the export of products from Spain |
| 2021 | [2112.15426v1](https://arxiv.org/abs/2112.15426v1) | Lunatic Stocks: Moon Phases as Irregular Sampling Features for Pattern Recognition in the Stock Markets |
| 2021 | [2112.02449v1](https://arxiv.org/abs/2112.02449v1) | Optimal Income Crossover for Two-Class Model Using Particle Swarm Optimization |
| 2021 | [2109.07212v3](https://arxiv.org/abs/2109.07212v3) | Optimising Rolling Stock Planning including Maintenance with Constraint Programming and Quantum Annealing |
| 2021 | [2104.00262v3](https://arxiv.org/abs/2104.00262v3) | Statistical significance revisited |
| 2020 | [2012.15078v1](https://arxiv.org/abs/2012.15078v1) | Development and similarity of insurance markets of European Union countries after the enlargement in 2004 |
| 2020 | [2001.09446v2](https://arxiv.org/abs/2001.09446v2) | Finance from the viewpoint of physics |
| 2020 | [2010.06306v1](https://arxiv.org/abs/2010.06306v1) | Local and Non-local Fractional Porous Media Equations |
| 2020 | [2003.10922v1](https://arxiv.org/abs/2003.10922v1) | Market structure dynamics during COVID-19 outbreak |
| 2020 | [2008.05527v1](https://arxiv.org/abs/2008.05527v1) | Transmission of market orders through communication line with relativistic delay |
| 2020 | [2003.11027v1](https://arxiv.org/abs/2003.11027v1) | Turn-of-the Year Affect in Gold Prices: Decomposition Analysis |
| 2019 | [1908.11204v1](https://arxiv.org/abs/1908.11204v1) | A multi-scale symmetry analysis of uninterrupted trends returns of daily financial indices |
| 2019 | [1908.10014v1](https://arxiv.org/abs/1908.10014v1) | Christmas Jump in LIBOR |
| 2019 | [1911.00715v1](https://arxiv.org/abs/1911.00715v1) | Do Chinese Internet Users Exist Heterogeneity in Search Behavior? |
| 2019 | [1906.04822v1](https://arxiv.org/abs/1906.04822v1) | Generalized Beta Prime Distribution: Stochastic Model of Economic Exchange and Properties of Inequality Indices |
| 2019 | [1903.01820v1](https://arxiv.org/abs/1903.01820v1) | Influence of petroleum and gas trade on EU economies from the reduced Google matrix analysis of UN COMTRADE data |
| 2019 | [1908.03407v1](https://arxiv.org/abs/1908.03407v1) | On the Compound Beta-Binomial Risk Model with Delayed Claims and Randomized Dividends |
| 2019 | [1911.11971v2](https://arxiv.org/abs/1911.11971v2) | With or without replacement? Sampling uncertainty in Shepp's urn scheme |
| 2018 | [1801.08256v1](https://arxiv.org/abs/1801.08256v1) | A Hilbert Space of Stationary Ergodic Processes |
| 2018 | [1806.01781v1](https://arxiv.org/abs/1806.01781v1) | Comparing Alternatives to Measure the Impact of DDoS Attack Announcements on Target Stock Prices |
| 2018 | [1806.10935v1](https://arxiv.org/abs/1806.10935v1) | Data on the annual aggregated income taxes of the Italian municipalities over the quinquennium 2007-2011 |
| 2018 | [1810.09366v1](https://arxiv.org/abs/1810.09366v1) | Description of Incomplete Financial Markets for the Discrete Time Evolution of Risk Assets |
| 2018 | [1808.05893v1](https://arxiv.org/abs/1808.05893v1) | Exploring how innovation strategies at time of crisis influence performance: a cluster analysis perspective |
| 2018 | [1809.08681v3](https://arxiv.org/abs/1809.08681v3) | Financial accumulation implies ever-increasing wealth inequality |
| 2018 | [1807.00573v1](https://arxiv.org/abs/1807.00573v1) | Strategic behaviour and indicative price diffusion in Paris Stock Exchange auctions |
| 2017 | [1703.00703v4](https://arxiv.org/abs/1703.00703v4) | *K-means and Cluster Models for Cancer Signatures |
| 2017 | [1710.11184v3](https://arxiv.org/abs/1710.11184v3) | Correlations and Clustering in Wholesale Electricity Markets |
| 2017 | [1709.02129v1](https://arxiv.org/abs/1709.02129v1) | Data science for assessing possible tax income manipulation: The case of Italy |
| 2017 | [1706.08361v1](https://arxiv.org/abs/1706.08361v1) | Decomposition of Time Series Data to Check Consistency between Fund Style and Actual Fund Composition of Mutual Funds |
| 2017 | [1703.03195v1](https://arxiv.org/abs/1703.03195v1) | Diffusive and arrested-like dynamics in currency exchange markets |
| 2017 | [1709.08023v1](https://arxiv.org/abs/1709.08023v1) | Ownership Cost Calculations for Distributed Energy Resources Using Uncertainty and Risk Analyses |
| 2017 | [1705.01145v1](https://arxiv.org/abs/1705.01145v1) | Stochastic modelling of non-stationary financial assets |
| 2017 | [1706.06007v1](https://arxiv.org/abs/1706.06007v1) | Symbolic dynamics techniques for complex systems: Application to share price dynamics |
| 2017 | [1712.00979v1](https://arxiv.org/abs/1712.00979v1) | The balance of growth and risk in population dynamics |
| 2017 | [1709.06279v2](https://arxiv.org/abs/1709.06279v2) | Universal Lévy's stable law of stock market and its characterization |
| 2016 | [1610.05697v1](https://arxiv.org/abs/1610.05697v1) | "Butterfly Effect" vs Chaos in Energy Futures Markets |
| 2016 | [1611.07432v2](https://arxiv.org/abs/1611.07432v2) | "Chaos" in energy and commodity markets: a controversial matter |
| 2016 | [1607.06158v3](https://arxiv.org/abs/1607.06158v3) | Dimension Reduction in Statistical Estimation of Partially Observed Multiscale Processes |
| 2016 | [1604.07782v1](https://arxiv.org/abs/1604.07782v1) | Is the public sector of your country a diffusion borrower? Empirical evidence from Brazil |
| 2016 | [1605.03559v1](https://arxiv.org/abs/1605.03559v1) | Survey on log-normally distributed market-technical trend data |
| 2015 | [1509.05475v1](https://arxiv.org/abs/1509.05475v1) | A proposal of a methodological framework with experimental guidelines to investigate clustering stability on financial time series |
| 2015 | [1505.05089v1](https://arxiv.org/abs/1505.05089v1) | CEI: a new indicator measuring City Commercial Credit Risk initiated in China |
| 2015 | [1503.08441v1](https://arxiv.org/abs/1503.08441v1) | East africa in the Malthusian trap? A statistical analysis of financial, economic, and demographic indicators |
| 2015 | [1504.03822v1](https://arxiv.org/abs/1504.03822v1) | Fisher information and quantum mechanical models for finance |
| 2015 | [1510.00237v1](https://arxiv.org/abs/1510.00237v1) | Seasonalities and cycles in time series: A fresh look with computer experiments |
| 2015 | [1507.07219v4](https://arxiv.org/abs/1507.07219v4) | Why Quantitative Structuring? |
| 2014 | [1406.5083v1](https://arxiv.org/abs/1406.5083v1) | A variation of the Dragulescu-Yakovenko income model |
| 2014 | [1406.4783v1](https://arxiv.org/abs/1406.4783v1) | Advisors and indicators based on the SSA models and non-linear generalizations |
| 2014 | [1406.0455v3](https://arxiv.org/abs/1406.0455v3) | Buyer to Seller Recommendation under Constraints |
| 2014 | [1403.3138v1](https://arxiv.org/abs/1403.3138v1) | Distribution of the asset price movement and market potential |
| 2014 | [1409.6257v1](https://arxiv.org/abs/1409.6257v1) | Optimal models of extreme volume-prices are time-dependent |
| 2014 | [1404.1730v2](https://arxiv.org/abs/1404.1730v2) | Stochastic Evolution of Stock Market Volume-Price Distributions |
| 2013 | [1308.3966v1](https://arxiv.org/abs/1308.3966v1) | Analyzing Herd Behavior in Global Stock Markets: An Intercontinental Comparison |
| 2013 | [1312.5807v1](https://arxiv.org/abs/1312.5807v1) | Block Sampling under Strong Dependence |
| 2013 | [1305.2263v1](https://arxiv.org/abs/1305.2263v1) | Direct Evidence for Synchronization in Japanese Business Cycle |
| 2013 | [1312.4803v2](https://arxiv.org/abs/1312.4803v2) | Multiscaling edge effects in an agent-based money emergence model |
| 2013 | [1301.2535v1](https://arxiv.org/abs/1301.2535v1) | Reinterpretation of Sieczka-Hołyst financial market model |
| 2013 | [1309.5703v1](https://arxiv.org/abs/1309.5703v1) | The Relationship Between Stock Market Parameters and Interbank Lending Market: an Empirical Evidence |
| 2013 | [1311.4068v1](https://arxiv.org/abs/1311.4068v1) | Uncertain growth and the value of the future |
| 2012 | [1206.0496v1](https://arxiv.org/abs/1206.0496v1) | A Compact Mathematical Model of the World System Economic and Demographic Growth, 1 CE - 1973 CE |
| 2012 | [1205.5820v1](https://arxiv.org/abs/1205.5820v1) | A Multi-Level Lorentzian Analysis of the Basic Structures of the Daily DJIA |
| 2012 | [1205.2470v1](https://arxiv.org/abs/1205.2470v1) | Equilibrium Distribution of Labor Productivity: A Theoretical Model |
| 2012 | [1209.4695v3](https://arxiv.org/abs/1209.4695v3) | On statistical indistinguishability of the complete and incomplete markets |
| 2012 | [1208.1188v1](https://arxiv.org/abs/1208.1188v1) | Relations between allometric scalings and fluctuations in complex systems: The case of Japanese firms |
| 2011 | [1103.5973v1](https://arxiv.org/abs/1103.5973v1) | A Utility Based Approach to Energy Hedging |
| 2011 | [1103.0647v1](https://arxiv.org/abs/1103.0647v1) | A class of CTRWs: Compound fractional Poisson processes |
| 2011 | [1102.3702v1](https://arxiv.org/abs/1102.3702v1) | A dynamic hybrid model based on wavelets and fuzzy regression for time series estimation |
| 2011 | [1103.2234v1](https://arxiv.org/abs/1103.2234v1) | Do firms share the same functional form of their growth rate distribution? A new statistical test |
| 2011 | [1103.1689v1](https://arxiv.org/abs/1103.1689v1) | Information Theoretic Limits on Learning Stochastic Differential Equations |
| 2011 | [1108.0386v1](https://arxiv.org/abs/1108.0386v1) | Multiplicative Asset Exchange with Arbitrary Return Distributions |
| 2011 | [1106.4710v1](https://arxiv.org/abs/1106.4710v1) | Proportionate vs disproportionate distribution of wealth of two individuals in a tempered Paretian ensemble |
| 2011 | [1109.4859v1](https://arxiv.org/abs/1109.4859v1) | The Food Crises: A quantitative model of food prices including speculators and ethanol conversion |
| 2010 | [1012.5932v1](https://arxiv.org/abs/1012.5932v1) | An statistical analysis of stratification and inequity in the income distribution |
| 2010 | [1010.2061v7](https://arxiv.org/abs/1010.2061v7) | Brownian markets |
| 2010 | [1010.0208v2](https://arxiv.org/abs/1010.0208v2) | Equilibrium distributions and relaxation times in gas-like economic models: an analytical derivation |
| 2010 | [1004.1804v2](https://arxiv.org/abs/1004.1804v2) | Interacting Many-Investor Models, Opinion Formation and Price Formation with Non-extensive Statistics |
| 2010 | [1003.5356v1](https://arxiv.org/abs/1003.5356v1) | Nonlinear Stochastic Model of Return matching to the data of New York and Vilnius Stock Exchanges |
| 2010 | [1010.0854v2](https://arxiv.org/abs/1010.0854v2) | On low-sampling-rate Kramers-Moyal coefficients |
| 2010 | [1007.3347v1](https://arxiv.org/abs/1007.3347v1) | On-line trading as a renewal process: Waiting time and inspection paradox |
| 2010 | [1001.4401v3](https://arxiv.org/abs/1001.4401v3) | The level crossing and inverse statistic analysis of German stock market index (DAX) and daily oil price time series |
| 2010 | [1011.1796v5](https://arxiv.org/abs/1011.1796v5) | Using The Censored Gamma Distribution for Modeling Fractional Response Variables with an Application to Loss Given Default |
| 2009 | [0912.5420v3](https://arxiv.org/abs/0912.5420v3) | Consumer Expenditure Distribution in India, 1983-2007: Evidence of a Long Pareto Tail |
| 2009 | [0905.3870v1](https://arxiv.org/abs/0905.3870v1) | On the short-term influence of oil price changes on stock markets in GCC countries: linear and nonlinear analyses |
| 2009 | [0906.1462v1](https://arxiv.org/abs/0906.1462v1) | Spiraling toward market completeness and financial instability |
| 2009 | [0905.3874v1](https://arxiv.org/abs/0905.3874v1) | Stock market integration in the Latin American markets: further evidence from nonlinear modeling |
| 2009 | [0901.2271v2](https://arxiv.org/abs/0901.2271v2) | Superstatistical fluctuations in time series: Applications to share-price dynamics and turbulence |
| 2009 | [0901.1500v1](https://arxiv.org/abs/0901.1500v1) | Superstatistics of Labour Productivity in Manufacturing and Nonmanufacturing Sectors |
| 2009 | [0903.4783v2](https://arxiv.org/abs/0903.4783v2) | Threshold levels in Economics |
| 2008 | [0811.3122v1](https://arxiv.org/abs/0811.3122v1) | A multiscale view on inverse statistics and gain/loss asymmetry in financial time series |
| 2008 | [0805.2713v1](https://arxiv.org/abs/0805.2713v1) | Coherence-based multivariate analysis of high frequency stock market values |
| 2008 | [0805.3071v1](https://arxiv.org/abs/0805.3071v1) | Convergence and cluster structures in EU area according to fluctuations in macroeconomic indices |
| 2008 | [0807.5001v1](https://arxiv.org/abs/0807.5001v1) | Decomposition of order statistics of semimartingales using local times |
| 2008 | [0801.0748v1](https://arxiv.org/abs/0801.0748v1) | Hausdorff clustering |
| 2008 | [0806.4876v3](https://arxiv.org/abs/0806.4876v3) | Inconsistency of the judgment matrix in the AHP method and the decision maker's knowledge |
| 2008 | [0809.3541v1](https://arxiv.org/abs/0809.3541v1) | Labour Productivity Superstatistics |
| 2008 | [0804.1837v1](https://arxiv.org/abs/0804.1837v1) | Mathematical analysis of long tail economy using stochastic ranking processes |
| 2008 | [0810.1059v1](https://arxiv.org/abs/0810.1059v1) | Measuring the "non-stopping timeness" of ends of previsible sets |
| 2008 | [0804.0902v1](https://arxiv.org/abs/0804.0902v1) | Time vs. Ensemble Averages for Nonstationary Time Series |
| 2007 | [0711.1836v2](https://arxiv.org/abs/0711.1836v2) | A Markov process associated with plot-size distribution in Czech Land Registry and its number-theoretic properties |
| 2007 | [cond-mat/0702607v1](https://arxiv.org/abs/cond-mat/0702607v1) | Geometrical Brownian Motion Driven by Color Noise |
| 2007 | [0705.2098v1](https://arxiv.org/abs/0705.2098v1) | Kolkata Restaurant Problem as a generalised El Farol Bar Problem |
| 2007 | [0801.0108v1](https://arxiv.org/abs/0801.0108v1) | Note on two phase phenomena in financial markets |
| 2007 | [0709.1092v2](https://arxiv.org/abs/0709.1092v2) | Persistence in a Random Bond Ising Model of Socio-Econo Dynamics |
| 2007 | [0710.1893v1](https://arxiv.org/abs/0710.1893v1) | Quasistatically varying log-normal distribution in the middle scale region of Japanese land prices |
| 2007 | [0707.0385v1](https://arxiv.org/abs/0707.0385v1) | Specialization of strategies and herding behavior of trading firms in a financial market |
| 2007 | [0705.1056v1](https://arxiv.org/abs/0705.1056v1) | The log-normal distribution from Non-Gibrat's law in the middle scale region of profits |
| 2007 | [0706.1460v1](https://arxiv.org/abs/0706.1460v1) | Uncertainty in the Fluctuations of the Price of Stocks |
| 2007 | [physics/0702003v1](https://arxiv.org/abs/physics/0702003v1) | Waiting time analysis of foreign currency exchange rates: Beyond the renewal-reward theorem |
| 2006 | [physics/0612091v1](https://arxiv.org/abs/physics/0612091v1) | A Probability Density Function for Google's stocks |
| 2006 | [physics/0605246v1](https://arxiv.org/abs/physics/0605246v1) | An Outlook on Correlations in Stock Prices |
| 2006 | [physics/0608214v1](https://arxiv.org/abs/physics/0608214v1) | Comparison of gain-loss asymmetry behavior for stocks and indexes |
| 2006 | [physics/0701008v1](https://arxiv.org/abs/physics/0701008v1) | Fluctuations in time intervals of financial data from the view point of the Gini index |
| 2006 | [physics/0601205v2](https://arxiv.org/abs/physics/0601205v2) | Level Crossing Analysis of the Stock Markets |
| 2006 | [physics/0603076v1](https://arxiv.org/abs/physics/0603076v1) | Living in an Irrational Society: Wealth Distribution with Correlations between Risk and Expected Profits |
| 2006 | [physics/0603013v1](https://arxiv.org/abs/physics/0603013v1) | Stock mechanics: unification with economy |
| 2006 | [physics/0603012v1](https://arxiv.org/abs/physics/0603012v1) | The Process of price formation and the skewness of asset returns |
| 2005 | [physics/0511119v3](https://arxiv.org/abs/physics/0511119v3) | Dynamics of the return distribution in the Korean financial market |
| 2005 | [physics/0504014v1](https://arxiv.org/abs/physics/0504014v1) | Hausdorff clustering of financial time series |
| 2005 | [nlin/0511048v1](https://arxiv.org/abs/nlin/0511048v1) | Persistence Probabilities of the German DAX and Shanghai Index |
| 2005 | [physics/0502084v1](https://arxiv.org/abs/physics/0502084v1) | Statistical Properties of Demand Fluctuation in the Financial Market |
| 2005 | [physics/0512127v1](https://arxiv.org/abs/physics/0512127v1) | Stock mechanics: a general theory and method of energy conservation with applications on DJIA |
| 2005 | [physics/0508023v1](https://arxiv.org/abs/physics/0508023v1) | Stock mechanics: energy conservation theory and the fundamental line of DJIA |
| 2005 | [physics/0504002v1](https://arxiv.org/abs/physics/0504002v1) | The Quantitative Relations between Stock Prices and Quantities of Tradable Stock Shares and Its Applications |
| 2005 | [physics/0504210v2](https://arxiv.org/abs/physics/0504210v2) | What can we see from Investment Simulation based on Generalized (m,2)-Zipf law? |
| 2004 | [cond-mat/0401443v1](https://arxiv.org/abs/cond-mat/0401443v1) | An interest rates cluster analysis |
| 2004 | [nlin/0402012v3](https://arxiv.org/abs/nlin/0402012v3) | Analysis of Data Clusters Obtained by Self-Organizing Methods |
| 2004 | [cond-mat/0402511v2](https://arxiv.org/abs/cond-mat/0402511v2) | Critical Ising Model and Financial Market |
| 2004 | [cond-mat/0412723v1](https://arxiv.org/abs/cond-mat/0412723v1) | Modelling financial markets by the multiplicative sequence of trades |
| 2004 | [cond-mat/0401445v1](https://arxiv.org/abs/cond-mat/0401445v1) | On pricing of interest rate derivatives |
| 2003 | [cond-mat/0307226v1](https://arxiv.org/abs/cond-mat/0307226v1) | Modelling and computer simulation of an insurance policy: A search for maximum profit |
| 2002 | [cond-mat/0203591v1](https://arxiv.org/abs/cond-mat/0203591v1) | Anticorrelations and subdiffusion in financial systems |
| 2002 | [cond-mat/0201514v1](https://arxiv.org/abs/cond-mat/0201514v1) | Modelling share volume traded in financial markets |
| 2002 | [cond-mat/0209446v1](https://arxiv.org/abs/cond-mat/0209446v1) | Statistical Bounds on Equity |
| 2001 | [cond-mat/0109026v1](https://arxiv.org/abs/cond-mat/0109026v1) | Asset-asset interactions and clustering in financial markets |
| 2001 | [cond-mat/0107256v1](https://arxiv.org/abs/cond-mat/0107256v1) | Ensemble properties of securities traded in the NASDAQ market |
| 2001 | [cond-mat/0101143v1](https://arxiv.org/abs/cond-mat/0101143v1) | Liquid markets and market liquids: collective and single-asset dynamics in financial markets |
| 2001 | [cond-mat/0102494v2](https://arxiv.org/abs/cond-mat/0102494v2) | Markov properties of high frequency exchange rate data |
| 2001 | [cond-mat/0110285v1](https://arxiv.org/abs/cond-mat/0110285v1) | Self-similar approach to market analysis |
| 2001 | [cond-mat/0102042v1](https://arxiv.org/abs/cond-mat/0102042v1) | To sell or not to sell? Behavior of shareholders during price collapses |
| 2000 | [cond-mat/0001293v1](https://arxiv.org/abs/cond-mat/0001293v1) | Domino effect for world market fluctuations |
| 2000 | [physics/0007075v1](https://arxiv.org/abs/physics/0007075v1) | Optimization of Trading Physics Models of Markets |
| 2000 | [cond-mat/0007385v1](https://arxiv.org/abs/cond-mat/0007385v1) | Scaling and Multi-scaling in Financial Markets |
| 2000 | [cond-mat/0010455v1](https://arxiv.org/abs/cond-mat/0010455v1) | Statistical physics of adaptive correlation of agents in a market |
| 2000 | [cond-mat/0001268v2](https://arxiv.org/abs/cond-mat/0001268v2) | Taxonomy of Stock Market Indices |
| 1999 | [cond-mat/9912006v1](https://arxiv.org/abs/cond-mat/9912006v1) | Dynamics of the Number of Trades of Financial Securities |
| 1999 | [cond-mat/9906381v2](https://arxiv.org/abs/cond-mat/9906381v2) | Scale-invariant Truncated Lévy Process |
| 1999 | [cond-mat/9909302v1](https://arxiv.org/abs/cond-mat/9909302v1) | Statistical Properties of Statistical Ensembles of Stock Returns |
| 1997 | [cond-mat/9709141v2](https://arxiv.org/abs/cond-mat/9709141v2) | From turbulence to financial time series |
| 1997 | [cond-mat/9710290v2](https://arxiv.org/abs/cond-mat/9710290v2) | Resummation Methods for Analyzing Time Series |

