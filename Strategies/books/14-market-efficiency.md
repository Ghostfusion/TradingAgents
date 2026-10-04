# Market Efficiency, Predictability & Information

`book 14/19` · slug `market-efficiency` · 387 papers in the corpus · 38 rated high-relevance by the sweep

## 0. Scope

This category covers the empirical question the whole repo rests on: *is anything predictable, at what horizon, and is the predictability statistically and economically real once search and cost are accounted for?* It spans weak-form tests (variance ratios, entropy, Hurst), the adaptive-market / time-varying-efficiency evidence, price-discovery and information-share work (order flow, Kyle's λ, options), limits to arbitrage, anomaly decay after publication, and the statistical-versus-economic-significance boundary. It matters to TradingAgents because the repo's governing rule is *compute, don't narrate*: an analyst may only assert predictability that some computed read supports, and this literature says most apparent predictability is a search artifact, a cost artifact, or a regime artifact. The category is dominated by two things the sweep over-collected — econophysics entropy/efficiency measures and yet-another "ML beats the market" forecasting paper — with a small but high-value core of selection-corrected, cost-aware evaluation papers.

## 1. Corpus composition

Header counts (authoritative): **387** papers, of which the sweep rated **38 high**, **226 medium**, **123 low**. The evidence pack itemises **261** of these as full rows (38 high + the 100 most-recent medium + 123 background); the booklist carries full bibliographic metadata for the **top 60**.

Decade distribution of the 261 dated evidence rows, and of the top-60 booklist:

| decade | evidence rows (261) | booklist (60) |
| --- | --- | --- |
| 1990s | 1 | 0 |
| 2000–2009 | 39 | 3 |
| 2010–2019 | 68 | 22 |
| 2020–2026 | 153 | 35 |

Dominated by **q-fin.ST-style statistical-finance papers from the last six years** (153/261 evidence rows, 35/60 booklist). The recent mass is the re-litigation of predictability under machine learning and LLMs (does an ML model beat the random walk, and does it survive the honest protocol?); the durable core — variance-ratio/AMH time-varying-efficiency tests, entropy-based weak-form tests, Knight/price-discovery microstructure, and the multiple-testing/selection correction — sits in 2000–2019. The 123 background rows attach the category mostly by *reporting* a forecasting number over a crypto or foreign-equity series, not by contributing a method; the 38 high-relevance rows are where the method and the correction live.

## 2. Deep reads

### arXiv 2604.15531v1 — Spurious Predictability in Financial Machine Learning (2026)

- **Question**: how do you separate a genuinely stable information→outcome relation from predictability manufactured by selection, leakage, or violated temporal ordering?
- **Method**: a *falsification audit* that runs an entire workflow (feature construction → tuning → selection → portfolio mapping) on induced-null environments — strict martingale-difference reference classes plus "microstructure placebos" that preserve zero expected excess return but embed transient artifacts. A workflow that produces significant strict walk-forward evidence on the strict null is statistically falsified; on the placebo, economically falsified. For survivors, a Backtest Inflation Factor (BIF) and a magnitude gap quantify selection-induced inflation.
- **Headline finding**: under a global martingale-difference null the optimized in-sample winner grows as **log K_eff**, where K_eff is the *effective* number of independent strategies after accounting for correlation — not the nominal specification count; walk-forward evaluation stays stochastically bounded under the same null. Random (non-temporal) cross-validation mechanically improves reported volatility-forecast performance under the null. Models can reproduce known systematic risk premia (significant gross returns, zero alpha after factor adjustment).
- **Limitation**: the audit is a pre-commitment *filter*, not a correction; it requires the researcher to construct plausible null environments, and the post-hoc tools it complements (Reality Check, SPA) assume the true trial count is known — which in modern adaptive search it rarely is.

### arXiv 2311.10685v3 — High-Throughput Asset Pricing (2023, rev. 2025)

- **Question**: should factor research mine *less* (restrict to theory) or mine *rigorously* (condition on the search)?
- **Data/method**: empirical-Bayes (EB) mining of **136,000** long-short strategies systematically constructed from accounting ratios, past returns, and ticker symbols; select the top 1% by EB-predicted Sharpe; no look-ahead. Compared against the 200 published strategies of Chen–Zimmermann.
- **Headline finding**: the EB top-1% portfolio earns **5.7%/yr out-of-sample 1983–2020** versus **5.9%/yr** for the average of the 200 published strategies — matching top-journal performance while being real-time constructible. Naive argmax-of-Sharpe mining often selects the same strategies an ideal Bayesian would (Prop. 1), but the naive *performance estimates* are distorted. Predictability is concentrated in equal-weighted accounting strategies, small stocks, and pre-2004. Popular finance multiple-testing methods (Harvey–Liu–Zhu's Benjamini–Yekutieli hurdle; Chordia–Goyal–Saretto's Romano–Wolf) **fail to identify most out-of-sample performers** — the BY Theorem 1.3 procedure is "very often unneeded, and yields too conservative of a procedure"; Storey's FDR and EB shrinkage do capture the majority.
- **Limitation**: theory-free EB with a 20-year rolling window misses the ~2004 structural break: post-2004 predictions are closer to zero and OOS returns even closer, so contemporary edge is thin and partly explained by the 20y window not adapting to the break.

### arXiv 2608.23808v2 — Equity Strategy Backtesting: Luck or Edge? The MinervaScore (2026)

- **Question**: can heterogeneous pass/fail verdicts be turned into one auditable post-selection robustness grade?
- **Method**: five gates — Deflated Sharpe Ratio (pass ≥ 0.95), Probability of Backtest Overfitting (≤ 0.50), Hansen's SPA (p ≤ 0.10), Minimum Track Record Length, and a hand-built regime-stability composite (≥ 0.60). Pass = logical AND; gate margins combined by a Lipták-style inverse-normal blend with a conservative offset.
- **Headline finding**: separates true signal from lucky backtests at **AUROC 0.989** on synthetic markets, but the margin over the GT-Score proxy is small and it stays close to the corrected **DSR-alone** baseline (the strongest single gate). 60–95% of production DSR values saturate at exactly zero, so the DSR *statistic* (logit-rescaled), not its pass/fail value, is carried forward. In a pre-registered test on unseen real-market data the score showed **no significant forward relationship** (Spearman ρ_s = 0.013, one-sided p = 0.40). The paper therefore presents it as a validation/reporting layer, not evidence of real-market predictability.
- **Limitation**: the regime-stability composite is called "the most heuristic component"; the standardization by cross-sectional dispersion makes the aggregate "descriptive rather than inferential"; no forward predictive claim is made.
- **Key mechanics for this repo**: MinTRL is per-bar and single-strategy, dependent only on Sharpe/skew/kurtosis/confidence, *not* on N; effective multiplicity should be estimated by decorrelating searched parameter vectors (eigenvalue approach), not the nominal configuration count.

### arXiv 2607.01377v1 — Liquidity Premium and Investment Horizons (2026)

- **Question**: does the Kyle (1985) price-impact coefficient λ, estimated from daily order flow, forecast the cross-section of returns?
- **Data/method**: CRSP daily/monthly, entire universe, 2020–2025; firm-month signed order flow, volume volatility, and two λ̂ estimators (a within-month price-impact regression and an Amihud-style ratio); panel and Fama–MacBeth regressions with size/B-M/momentum/Amihud controls.
- **Headline finding**: signed order flow **strongly predicts contemporaneous and one-month-ahead returns**; volume volatility predicts *lower* subsequent returns (elevated noise-trading variance narrows λ and degrades price discovery); Fama–MacBeth slopes survive Newey–West adjustment. Predictability is strongest at **short horizons** and high frequencies, consistent with price impact rising as information revelation approaches. The illiquidity premium is resolved as an adverse-selection equilibrium effect (low flow widens λ and depresses price; normalization restores it) rather than risk compensation (Constantinides's puzzle).
- **Limitation**: the return-prediction coefficient on λ̂ is **specification-sensitive** — its sign and magnitude move with specification choices, which the paper investigates as a robustness question rather than claiming robustness.

### arXiv 2304.09937v1 — Stock Price Predictability and the Business Cycle via Machine Learning (2023)

- **Question**: do ML models predict the S&P 500 differently in recessions, and does adding recession history or the risk-free rate help?
- **Data/method**: S&P 500 index; LSTM, bidirectional LSTM, GRU; all seven US recessions 1969–2020; each recession modelled as a separate forecasting problem.
- **Headline finding**: for the majority of models, forecasting errors are **larger in recessions** than expansions; adding recession observations to the training set improves only about half the models (22 of 42) with no clear pattern by architecture; including a recession-history predictor or the risk-free rate "does not necessarily improve" performance. Recessions where models do well (the late-1970s oil-crisis periods) exhibit **lower market volatility** — so the "good" performance reflects effective monetary-policy stabilization, not ML merit.
- **Limitation**: single index, seven recession events — a small effective sample; the authors recommend evaluating models in both recessions and expansions rather than claiming a general result.

### arXiv 2208.11976v1 — A statistical test of market efficiency based on information theory (2022)

- **Question**: can an entropy measure of return sequences be given a *significance test*, rather than only a gradual efficiency score?
- **Method**: symbolize returns to up/down indicators, decompose sequences into prefix + next suffix; define "market information" `I^{L+1}` as the excess of the ideal-EMH entropy over the true conditional entropy. Theorem 1: I = 0 under EMH, I > 0 otherwise. The estimator is asymptotically **gamma(2^L−1, 1/(ln 2 · n))** under the null (a KS test validates the approximation at n ≳ 100 for L = 1).
- **Headline finding** (2021 daily data, L = 1, n = 100): the EMH is **never** rejected for the Russell 2000 index; rejected for the **CAC 40** 60.8% of dates at 95% (31.0% at 99%, 4.4% at 99.9%); rejected for a single Russell constituent (Percient) 57.0% at 95%; rejected for **BTC/USD only 4.2%** of the time at 95%. Aggregating many stocks into an index makes the single-name inefficiencies disappear.
- **Limitation**: the two-state symbolization discards most of the return distribution; the null is less restrictive than full weak-form efficiency (rejecting it is stronger evidence, not weaker), and the authors flag multi-state extensions as future work.

### arXiv 2011.14809v1 — Collective dynamics of stock market efficiency (2020)

- **Question**: is efficiency constant, and can its *dynamics* be measured and clustered?
- **Data/method**: 43 major world stock indices, 20 years; time-varying efficiency = **permutation entropy** of log-returns inside sliding windows (≈1 = efficient, lower = departure from randomness); dynamical clustering over windows; a weighted co-clustering network with PageRank centrality and stochastic block models.
- **Headline finding**: markets cluster hierarchically by long-run efficiency profile, but **efficiency ranks are stable only 1–2 months** and clusterings only **≈4 months**. The co-clustering network is essentially fully connected (edge-weight Gini 0.18) and resolves into **two modules** (24 indices incl. USA/Asia-Pacific; 19 incl. 12 European). The authors read this as efficiency being a *collective* phenomenon — global synchronization can drive high efficiency, but the same entanglement spreads low-efficiency states systemically.
- **Limitation**: the network edges carry no direction of influence (co-movement, not causality); index-level aggregation may hide the single-name inefficiency the entropy test above finds; only 20 years and index data.

### arXiv 1202.0100v13 — The Evolution of Stock Market Efficiency in the US: A Non-Bayesian Time-Varying Model (2012, rev. 2015)

- **Question**: does US market efficiency evolve, and can its time path be estimated without a Bayesian prior?
- **Method**: a non-Bayesian **time-varying AR (TV-AR)** whose coefficients follow a random walk; the "degree of market efficiency" ζ_t is a function of the estimated TV-AR coefficients, with bootstrap confidence bands constructed under the null of zero autocorrelation.
- **Headline finding**: the US market has evolved, and its degree of efficiency shows **cyclical fluctuations with a 30–40 year periodicity**. It is efficient except for four spells in the sample: the long recession 1873–1879, the 1902–1904 recession, the New Deal era, and the 1957–1958 recession and its aftermath. The authors state this is partly consistent with behavioral finance / AMH.
- **Limitation**: univariate AR approximation of a complex non-stationary process; the "local stationarity" assumption is explicit, and the result is a single-market historical narrative rather than a tradable rule.

### arXiv 1207.1842v4 — A Test of the Adaptive Market Hypothesis using a Time-Varying AR Model in Japan (2012, rev. 2016)

- **Question**: do the first and second sections of the Tokyo Stock Exchange (TOPIX vs TSE2) differ in how their efficiency evolves?
- **Method**: same Ito et al. TV-AR framework; the time-varying degree of efficiency ζ_t is compared against a residual-bootstrap band under the zero-autocorrelation null (99% band rejection = 1% significance); monthly data October 1961 – December 2015.
- **Headline finding**: (1) the degree of efficiency **changes over time** in both markets; (2) TSE2's efficiency level is **lower than TOPIX's** in most periods; (3) **TOPIX has evolved toward efficiency, TSE2 has not** — consistent with AMH for the more qualified, higher-volume market.
- **Limitation**: two markets, one measure; the AMH is an interpretive frame, and the paper's own framing makes clear the measure is a local AR approximation.

### arXiv 1611.04090v1 — Time-varying return predictability in the Chinese stock market (2015/2016)

- **Question**: is Chinese-market return predictability stable, or does it move with market conditions?
- **Method**: wild-bootstrap automatic variance-ratio test plus the generalized spectral test, applied in a time-varying (rolling) fashion to Chinese index returns.
- **Headline finding**: return predictability **varies over time**, and significant predictability is observed **around market turmoils**; the authors read this as AMH-consistent and draw practical implications for timing.
- **Limitation**: a single emerging market and two tests; the "turmoil" windows are identified ex post.

### arXiv 2306.01740v4 — Not feeling the buzz: Correction study of mispricing and inefficiency in online sportsbooks (2024)

- **Question**: does the Wikipedia "buzz" mispricing strategy replicate, and does its profit survive data cleaning?
- **Method**: exact reproduction of Ramirez–Reade–Singleton on the same tennis-betting dataset, then cleaning, then a post-2020 extension.
- **Headline finding**: the mispricing claim **reproduces exactly**, but the published betting profits are driven by **a single bet** (the "Hercog" bet) that returned outlier profits from erroneously long odds; once that data-quality issue is fixed, most reported profit disappears and only one strategy ("competitive" matches) remains significant in the original out-of-sample period. In the post-2020 extension the competitive strategy generates **no further profit** and the model coefficients are **no longer reliable predictors** — consistent with the market having become more efficient.
- **Limitation**: one study, one market; the authors present it as a case study in the necessity of replication and data cleaning, not as a general law.

### arXiv 2502.15757v3 — TLOB: A Transformer with Dual Attention for Price Trend Prediction on Limit Order Books (2025)

- **Question**: does a complex attention model add real predictive power over a simple MLP on LOB data, and does the edge survive cost?
- **Data/method**: FI-2010 benchmark, Tesla and Intel LOB data, and a recent Bitcoin dataset; a dual spatial/temporal attention transformer with a horizon-bias-free labelling scheme; 4 horizons; a spread-based trend definition used as the cost proxy.
- **Headline finding**: a plain **MLP adapted to LOB already beats prior SoTA**, challenging complex architectures; TLOB exceeds SoTA by an average 3.7 F1 (FI-2010), 1.3/7.7 F1 (TSLA/INTC), 1.1 F1 (BTC). More importantly it measures **stock-price predictability declining over time by −6.68 F1** ("growing market efficiency") and finds that when trends are defined using the average spread (the primary transaction cost) **performance deteriorates** — classification accuracy does not translate into profitable trades.
- **Limitation**: LOB benchmarks and three assets; the authors explicitly argue the accuracy decline is EMH-consistent (signals compete themselves away) rather than an architecture failure.

### arXiv 2606.04153v1 — A new decomposition approach to modeling financial returns: conditioning sign on magnitude (2026)

- **Question**: does decomposing returns into sign and magnitude reveal nonlinear predictability that linear predictive regressions miss?
- **Method**: `R_t = sign(R_t)·|R_t|`; model the magnitude marginal (multiplicative-error/Weibull) and the **sign conditional on the contemporaneous magnitude** (probit), joined by a copula or by a conditional-sign-magnitude factorization (CSM); a toy example shows OLS has population MSE ≈ 0.595 even under full predictability when direction and scale are separate predictors.
- **Headline finding**: on **monthly US stock-market excess returns**, out-of-sample forecasting delivers "substantial statistical and economic gains relative to linear regression and complete subset regression," competitive with copula-based decompositions. Volatility (magnitude) dynamics produce **sign predictability even without mean predictability** (Christoffersen–Diebold), and predictors correlate more strongly with one component (e.g. the short rate with sign; credit spreads with magnitude) than with the raw return.
- **Limitation**: the CSM compares only against OLS/CSR,copula and a few nonlinear benchmarks; it is a forecasting model with no explicit multiplicity correction, so the OOS gains are stated for the specified predictor set.

### arXiv 2501.16772v2 — Trends and Reversion in Financial Markets on Time Scales from Minutes to Decades (2025)

- **Question**: at which horizons do price trends persist and at which do they revert?
- **Data/method**: 24 futures (14 years of tick data, 30 years of daily), 330 years of monthly asset prices, yearly data since medieval times; trend strength φ = a t-statistic-like weighted average of past excess log-returns; next-day return regressed on `a + b·φ + c·φ³` (≈2 million daily pairs across 24 assets × 10 horizons).
- **Headline finding**: markets are **trending on hours-to-years** and **reverting on shorter and longer scales**. In the trending regime, weak trends persist (herding) but trends **tend to revert before becoming statistically significant** — "by the time a trend is obvious in a chart, it is already over." The persistence coefficient b **peaks at T ≈ 3–12 months**; the reversion coefficient c is negative and roughly horizon-independent. Crucially, **b has vanished over the decades** (trend-following no longer works as it did in the 1990s), while c is stable.
- **Limitation**: the cubic is a reduced-form fit, not a structural model; the lattice-gas interpretation is speculative; futures-only for the short-horizon claims.

### arXiv 2608.26115v1 — Option-Implied Signals and Crash Risk (2026)

- **Question**: has the canonical option-implied predictability survived 2015–2026, and is it regime-conditional?
- **Data/method**: 12.36M US equity firm-day observations, 10,026 underlyings, 2015–2026, split into three regimes (low-vol post-crisis, high-vol transition, AI/mega-cap); panel regressions on six canonical signals plus a boosted-tree ML benchmark on the full IV surface.
- **Headline finding**: the **Xing et al. smirk–return relation has decayed monotonically** across regimes — next-month coefficient −0.023 (t = −5.5) in low-vol → −0.006 (t = −1.5, insignificant) in AI/mega-cap, and **reverses sign at three months** (+0.016, t = +2.1). The Cremers–Weinbaum IV spread and a Bakshi-style risk-neutral skewness **remain significant in every regime**. Boosted trees beat linear specifications on next-month prediction *only* in the AI/mega-cap regime (R²_OOS +1.29% vs +0.07%), and firm-level 5-day crash classification AUC is **highest in calm markets (0.706) and weakest in high-volatility regimes (0.561)**.
- **Limitation**: the dominant predictors differ across all three regimes (open-interest-weighted vega, contract count, OTM call IV), and none of the canonical hand-engineered signals appear in the top five anywhere — so the "canonical" signals are proxies whose usefulness is regime-bound.

### arXiv 2604.19476v2 — Cross-Stock Predictability via LLM-Augmented Semantic Networks (2026)

- **Question**: does textual embedding similarity make spurious cross-stock links, and does an LLM edge-filter restore the economic fidelity of a semantic network?
- **Method**: two stages — a sparse candidate graph from 10-K embeddings, then an LLM classifies each candidate edge into six economic relation categories (competitor/supply-chain/peer/…), with competitor edges removed and substitutes down-weighted; pair-level mean-reversion z-scores aggregated to stock-level signals by relation-aware and Gatev-distance weights.
- **Headline finding** (S&P 500, 2011–2019): LLM filtering raises the long-short Sharpe from **0.742 to 0.820** and cuts max drawdown from **−10.47% to −7.85%**; the semantic network substantially outperforms random graphs and SIC industry networks; Fama–French regressions confirm a statistically significant daily alpha not subsumed by conventional risk premia. Information diffuses gradually across economically linked firms, creating exploitable dislocations.
- **Limitation**: an LLM edge classifier is an added model with its own error; the backtest is one universe/period, and "economic relation" labelling is not ground-truthable.

## 3. Learnings applicable to this repo

### L1. Deflate by the *effective* number of independent trials, not the nominal count
- **Source**: `arXiv 2604.15531v1` (2026) — Spurious Predictability; `arXiv 2311.10685v3` (2023) — High-Throughput Asset Pricing.
- **Finding**: the optimized in-sample winner grows as `log K_eff`, and K_eff is the effective number of independent strategies after correlation (redundancy collapses K_eff toward 1). Using the nominal trial count over-deflates a tightly correlated search; the EB paper shows the search's own recorded dispersion, not a guessed N, is what predicts OOS performance.
- **Repo surface**: `tradingagents/strategies/evaluate.py::_selection_threshold` and `::deflated_sharpe_report`; `tradingagents/strategies/trial_ledger.py::trial_stats`.
- **Status**: `partial` — `deflated_sharpe_report` already accepts a *measured* Sharpe dispersion read from the trial ledger and tags provenance `measured` vs `assumed`, but the measured path is behind `enable_trial_ledger` (default off) and the fallback `sqrt(2·ln N)` assumes independence; no decorrelated K_eff estimator exists (verified by reading both modules).
- **Concrete step**: add an `n_effective` estimate from the correlation/eigenvalues of the ledger's candidate return series, and have `deflated_sharpe_report` consume it by default when the ledger is on, so a correlated search is not punished (or trusted) on its nominal K.

### L2. Use a less-conservative FDR (Storey/empirical Bayes) than Benjamini–Yekutieli for family screening
- **Source**: `arXiv 2311.10685v3` (2023) — High-Throughput Asset Pricing.
- **Finding**: the Harvey–Liu–Zhu Benjamini–Yekutieli hurdle rejects **nearly all 136,000 mined strategies** even though thousands have real out-of-sample returns; BY Theorem 1.3 is "very often unneeded, and yields too conservative of a procedure." Storey's FDR and EB shrinkage recover the majority of genuine performers. A family screen that only runs BY has a very high false-negative rate.
- **Repo surface**: `tradingagents/strategies/evaluate.py::family_materiality` (BY step-up over the stationary-bootstrap p-values; wired via `tradingagents/agents/utils/report_verifier.py::_family_materiality`).
- **Status**: `shipped` — the BY step-up is implemented and reaches the report verifier, and its demotion rule refuses to collapse a failure into `REFUTED`. The gap is power, not correctness.
- **Concrete step**: add a Storey (2002) / EB-shrinkage arm beside the BY arm in `family_materiality` and report both, so a family that BY rejects wholesale can still surface the performers the paper shows exist.

### L3. Gate horizon on a *measured* time-varying efficiency / AMH statistic
- **Source**: `arXiv 1202.0100v13` (2012/2015) — US TV-AR; `arXiv 1207.1842v4` (2012/2016) — Japan AMH; `arXiv 2011.14809v1` (2020) — Collective efficiency; `arXiv 1611.04090v1` (2015/2016) — Chinese predictability.
- **Finding**: efficiency is not a constant — the US degree oscillates with a 30–40 year cycle and is abnormal in four historical spells; TOPIX has evolved toward efficiency while TSE2 has not; efficiency ranks rotate within 1–2 months and clusterings within ≈4 months; Chinese predictability concentrates around market turmoils. A signal's expected edge therefore depends on the current efficiency state, not on an average.
- **Repo surface**: `tradingagents/strategies/regime_performance.py::regime_conditioned_performance` (and `::macro_regime`).
- **Status**: `partial` — per-regime tabulation of hit/return exists and is wired into `scripts/strategy_quality_report.py`, but there is no measured efficiency statistic (variance ratio, permutation entropy, TV-AR ζ) feeding a horizon gate.
- **Concrete step**: compute a rolling efficiency statistic (e.g. `complexity.permutation_entropy` or a variance-ratio over a sliding window) and store it as a regime axis, then require `regime_conditioned_performance` to report the strategy's edge per efficiency state so "this works" is never stated without the state.

### L4. Ground every claimed forecast horizon in an IC-decay half-life, not an intuition
- **Source**: `arXiv 2502.15757v3` (2025) — TLOB; `arXiv 2501.16772v2` (2025) — Trends and Reversion.
- **Finding**: predictability is strongly horizon-dependent: TLOB measures price-trend predictability declining by −6.68 F1 over time, and the trends paper finds the persistence coefficient peaks at T ≈ 3–12 months while trends revert on short and long scales. A signal traded past its measured half-life is trading noise.
- **Repo surface**: `tradingagents/strategies/signal_analysis.py::ic_decay_half_life` (and `::rank_ic`).
- **Status**: `partial` — `ic_decay_half_life` exists in the module's `__all__` but is referenced only by its unit test; `analysis_tools` wires only `rank_ic`/`icir` (verified by grep).
- **Concrete step**: call `ic_decay_half_life` from the signal-analysis tool and publish it beside the IC, so a reported horizon is bounded by the measured decay (and `alpha_eval`'s horizon scoring can refuse a horizon beyond the half-life).

### L5. Require the cost-adjusted arm beside every gross signal read
- **Source**: `arXiv 2502.15757v3` (2025) — TLOB; `arXiv 2306.01740v4` (2024) — buzz correction.
- **Finding**: redefining trends using the average spread — the primary transaction cost — materially degrades performance, so classification accuracy is not profit; and a replication that looked profitable collapsed once a single outlier data point was removed. Statistical significance and economic significance are different tests.
- **Repo surface**: `tradingagents/strategies/signal_analysis.py::with_without_cost_table`; `tradingagents/strategies/evaluate.py::net_returns`.
- **Status**: `shipped` — both exist and `with_without_cost_table` is wired into `scripts/strategy_quality_report.py`, `factor_proposal_loop.py` and others.
- **Concrete step**: make the with/without-cost table a **required** companion on the analyst signal tool (not only the scripts) so no `rank_ic`/`quantile_long_short` number reaches a report without its cost-adjusted twin.

### L6. Attribute results to their most influential observations before trusting them
- **Source**: `arXiv 2306.01740v4` (2024) — buzz correction; `arXiv 2608.26115v1` (2026) — option-implied decay.
- **Finding**: the buzz study's published profit was driven by **one bet**; removing it removed most of the result. A backtest or journal that reports only aggregate win/loss can be silently carrying a single-outlier result.
- **Repo surface**: `tradingagents/strategies/journal.py::trade_excursions` (MAE/MFE/profit-factor; wired via `analysis_tools.get_trade_excursions`).
- **Status**: `partial` — excursion/attribution stats exist and are wired, but there is no leave-one-out or single-trade-contribution estimate.
- **Concrete step**: add a `max_single_trade_contribution` / leave-one-out-Sharpe field to `trade_excursions` and flag any result whose top observation carries a disproportionate share of PnL.

### L7. Treat canonical option-implied signals as regime-bound and track their decay
- **Source**: `arXiv 2608.26115v1` (2026) — Option-Implied Signals and Crash Risk.
- **Finding**: the smirk–return relation has decayed to insignificance and **reversed sign** across regimes while IV spread and risk-neutral skewness persist; ML beats linear *only* in the AI/mega-cap regime; crash classification is weak exactly when systematic shocks dominate. "Canonical" is not "durable."
- **Repo surface**: `tradingagents/strategies/options_surface.py::iv_skew` / the `RN_SKEW_LABEL` cross-strike IV proxy.
- **Status**: `partial` — `iv_skew` and the labelled RN-skew proxy exist and are wired into `analysis_tools`, but nothing conditions them on regime or records their time-varying predictive content.
- **Concrete step**: attach the current regime (`regime_performance.macro_regime` / `regime_score`) to the options-surface read and treat skew signals as regime-conditional rather than standing features.

### L8. Use signed order flow (not raw volume) for the short-horizon liquidity-premium read
- **Source**: `arXiv 2607.01377v1` (2026) — Liquidity Premium and Investment Horizons.
- **Finding**: signed order flow predicts contemporaneous and **one-month-ahead** returns and dominates unsigned volume; volume volatility predicts *lower* subsequent returns; the effect is strongest at short horizons. λ itself is specification-sensitive.
- **Repo surface**: `tradingagents/strategies/liquidity_risk.py::kyle_lambda` (and `::amihud_illiquidity`), both wired into `analysis_tools` and `risk_score`.
- **Status**: `shipped` — Kyle λ and Amihud illiquidity are computed and consumed; the repo's λ is estimated from daily bars.
- **Concrete step**: add a signed-flow proxy (`sign(close-open or close-to-close) × volume`) and a cross-sectional forward-return test against it, so the order-flow signal the paper shows dominates volume becomes an available input rather than only volume/λ.

### L9. Model sign conditional on magnitude (nonlinear return predictability)
- **Source**: `arXiv 2606.04153v1` (2026) — Conditioning sign on magnitude.
- **Finding**: volatility dynamics produce sign predictability even without mean predictability, and linear regressions miss the sign×magnitude interaction entirely (the toy example's population OLS MSE ≈ 0.595 under approximate full predictability). Conditioning the sign on the contemporaneous magnitude yields substantial OOS gains on monthly US excess returns.
- **Repo surface**: `tradingagents/strategies/volatility_models.py` and `tradingagents/strategies/signal_analysis.py` — no sign-on-magnitude estimator exists.
- **Status**: `absent` — no conditional-sign-on-magnitude symbol is present (verified by grep for sign/magnitude conditioning).
- **Concrete step**: add a `sign_on_magnitude` read (probit of sign on realized magnitude + predictors) to the market-analyst signal set, reported alongside the magnitude/volatility forecast.

### L10. Do not credit forecasting skill where a low-volatility regime explains it
- **Source**: `arXiv 2304.09937v1` (2023) — Business Cycle via ML.
- **Finding**: ML forecasting errors are larger in most recessions; adding recession history or the risk-free rate does not reliably help; and the recessions where models look good are the ones with **lower volatility** (policy-stabilized), so the apparent skill is a volatility artifact. Evaluate in recessions *and* expansions.
- **Repo surface**: `tradingagents/strategies/regime_performance.py::regime_conditioned_performance` / `::macro_regime`.
- **Status**: `partial` — regime tabulation and a cross-asset macro-regime label exist, but nothing decomposes excess ML accuracy into a volatility component before crediting skill.
- **Concrete step**: in the scorecard, report accuracy/IC net of the contemporaneous volatility regime; refuse to publish a "skill" claim whose gain disappears once the low-vol state is controlled.

### L11. Falsify the workflow against induced nulls, not just the thesis
- **Source**: `arXiv 2604.15531v1` (2026) — Spurious Predictability.
- **Finding**: a whole pipeline (features → tuning → selection → portfolio mapping) must be run on zero-predictability reference classes and microstructure placebos; any workflow producing significant walk-forward evidence there is falsified. Random CV inflates volatility forecasts under nulls, and models may reproduce risk premia (gross significance, zero alpha).
- **Repo surface**: `tradingagents/strategies/falsification.py` — but this module falsifies *theses* (numeric invalidation conditions), a different sense.
- **Status**: `absent` for the workflow-null audit — `falsification.py` has no placebo/reference-class machinery (verified by reading the module: it defines `FalsificationCondition`, `check_breached`, `monitor_conditions`, `evaluate_debate_claims`).
- **Concrete step**: add a `null_audit` that replays the evaluation path on a shuffled/zero-predictability panel and returns a `falsified` flag, gated off by default; run it whenever a candidate backtest is promoted.

### L12. Make thesis invalidation a monitored, pushed event
- **Source**: `arXiv 2011.14809v1` (2020) — Collective efficiency (ranks rotate in 1–2 months); `arXiv 1202.0100v13` (2012/2015) — US efficiency cycles.
- **Finding**: efficiency states and rank orderings rotate on monthly timescales, so a thesis-checked-once thesis is stale within a quarter. Invalidation must be re-evaluated on subsequent closes and pushed to the operator, not appended to a log nobody reads.
- **Repo surface**: `tradingagents/strategies/falsification.py::monitor_conditions` and `tradingagents/strategies/monitor.py::notify`.
- **Status**: `partial` — both exist, and `evaluate_debate_claims` (the debate-time grounding path) is wired into `analysis_tools`, but `monitor_conditions` has no production caller (only tests) and `monitor.notify` has **no production caller at all** (grep across `tradingagents/` and `scripts/` returns only the definition and tests).
- **Concrete step**: add a nightly re-check that calls `monitor_conditions` with the latest metrics snapshot and, on any breach, calls `monitor.notify("invalidation", detail, config)` — so the AMH-driven requirement that invalidation be caught within its 1–2 month rotation window is met.

## 4. Where this repo is already ahead of the literature

- **A full selection-correction toolkit is shipped and wired.** `evaluate.py` carries the deflated Sharpe with provenance tagging, a PBO flag, White's Reality Check, Hansen's SPA over a stationary bootstrap, and purged CPCV splits; `alpha_zoo` and `score_panel` consume them. Most high-relevance papers in this category *cite* these instruments; TradingAgents implements them.
- **A three-way materiality verdict that refuses to read power as refutation.** `evaluate.materiality_verdict` returns `SUPPORTED`/`REFUTED`/`INCONCLUSIVE`, and `family_materiality` explicitly demotes a family-corrected failure to `INCONCLUSIVE` rather than `REFUTED` — exactly the discipline the replication/decay papers have to construct by hand.
- **Cost-aware evaluation is first-class.** `evaluate.net_returns` and `signal_analysis.with_without_cost_table` exist and are wired into the strategy-quality and factor-proposal scripts; the TLOB paper's central point (classification ≠ profit once spread is the trend threshold) is already an available computation here.
- **Entropy / complexity measurement already exists.** `complexity.permutation_entropy` implements the exact statistic the collective-efficiency paper (2011.14809v1) builds its whole result on, and it is wired into `analysis_tools`.
- **A trial ledger records the search.** `trial_ledger.py` persists one immutable row per evaluated candidate with a return-series hash, and `trial_stats` reads N and dispersion back — the architecture the honest-evaluation literature asks for, present before the book.
- **Liquidity microstructure is measured, not narrated.** `liquidity_risk.py` ships Kyle's λ, Amihud illiquidity, Roll/Corwin–Schultz/Abdi–Ranaldo spreads and a composite verdict; `options_surface.py` ships put-skew and a labelled cross-strike RN-skew proxy.
- **Research honesty gates exist.** `alpha_eval.ceiling_ratio` (an out-of-sample R² ceiling with an observation floor) and `factor_dispersion.factor_score_dispersion` (cross-metric agreement with a *declared* MaximumPossibleStd) implement exactly the "state the bound and the scale" discipline the anomaly literature demands.

## 5. Defects or risks the literature exposes

1. **The monitoring notifier is dead code in production.** `tradingagents/strategies/monitor.py:22` defines `notify` as the push path for "breaker trips, stale-data thresholds, and invalidation breaches," but a repo-wide grep finds it imported only by `tests/test_phase8_ops.py` — no production call site. Against 2011.14809v1 (efficiency ranks rotate in 1–2 months) and 1202.0100v13 (30–40 year efficiency cycles with four abnormal spells), a system that only appends to a JSONL cannot push an invalidation inside its rotation window.
2. **The thesis auto-monitor never runs on subsequent closes.** `tradingagents/strategies/falsification.py:58` (`monitor_conditions`) documents re-evaluation of invalidation conditions on later closes, but only `evaluate_debate_claims` (debate-time grounding) is wired, in `tradingagents/agents/utils/analysis_tools.py:13481`; `monitor_conditions` appears only in `tests/test_data_quality_falsification.py`. A thesis that silently breaches its invalidation level is therefore never caught by the module built to catch it (papers 2011.14809v1, 1611.04090v1).
3. **`family_materiality` runs only the over-conservative BY FDR.** `tradingagents/strategies/evaluate.py:704` implements the Benjamini–Yekutieli step-up (`p_(i) ≤ (i/K)·α/H_K`). `arXiv 2311.10685v3` shows the BY-based HLY hurdle rejects nearly all of 136,000 mined strategies while thousands have genuine out-of-sample returns; the repo's family screen shares that low power. (Mitigating: a failed family correction is demoted to `INCONCLUSIVE`, so the error is under-detection, not false refutation.)
4. **Default deflation assumes independent trials.** `tradingagents/strategies/evaluate.py:142` (`_selection_threshold`) falls back to `sqrt(2·ln N)` — the expected maximum of N *independent* standard normals — whenever the gate is off or dispersion is absent. `arXiv 2604.15531v1` shows the relevant multiplicity is `K_eff ≤ K`, so for the correlated parameter searches this repo actually runs, the default over-deflates (and the measured path is behind `enable_trial_ledger`, default off).
5. **No minimum track-record-length gate.** `arXiv 2608.23808v2` makes MinTRL one of five required gates. A grep for `min_track|mintrl|track_record_length` over `tradingagents/` and `scripts/` finds nothing; `alpha_eval.CEILING_MIN_N = 40` is an *observation floor* for the accuracy ceiling, not a length-versus-Sharpe sufficiency test. A short, high-Sharpe backtest can clear `deflated_sharpe` here without any length check.
6. **No regime-stability gate on promoted strategies.** `arXiv 2608.23808v2`'s fifth gate asks whether evidence is concentrated in one regime. `tradingagents/strategies/regime_performance.py::regime_conditioned_performance` *tabulates* per-regime performance but nothing gates on it; combined with `arXiv 2304.09937v1` (skill is often a low-volatility artifact) and 2011.14809v1 (regimes rotate monthly), a strategy can be promoted on an edge that exists in one state only.
7. **IC-decay half-life is computed but unused.** `tradingagents/strategies/signal_analysis.py:169` (`ic_decay_half_life`) is reachable only from its test. Against `arXiv 2502.15757v3` (predictability declines by −6.68 F1 over time) and `arXiv 2501.16772v2` (persistence peaks at 3–12 months), a horizon claim made through `analysis_tools` (which wires only `rank_ic`/`icir`) is ungrounded by the repo's own decay instrument.

## 6. Limits of this review

- I read the **full text of 16 papers** (abstract, introduction, and the method/results sections that matter, within pages 1–~200 of each PDF). The remaining high-relevance rows and all medium/background rows were used only as the abstract-level map in the evidence pack; none of them is listed in §2.
- Corpus composition uses the **261 dated evidence rows** the pack itemises (38 high + the 100 most-recent medium + 123 background) and the top-60 booklist metadata; the other 126 medium rows are not itemised, so the decade table under-counts the mid-2000s–2010s middle of the category.
- Every repo status is what the cited symbol does in the module I read, cross-checked with `grep` for call sites. I ran no tests, linters or gates, and I did not execute any script — a "wired" status means an importer exists, not that the path executes cleanly.
- Several sections of the PDFs (heavy math derivations, the MinervaScore calibration appendices, the CSM likelihood appendix) were skimmed rather than verified line by line; quantitative findings are taken from the abstract/introduction and the results text where the number appeared.
- The `options_surface` and `volatility_models` surfaces were checked for the symbols named in L7/L9 but not read in full, so the "no sign-on-magnitude estimator" status is a grep-based absence over those files, not an exhaustive class-level proof.
