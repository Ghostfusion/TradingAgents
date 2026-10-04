# Backtest Methodology, Overfitting & Evaluation

`book 02/19` · slug `backtest-evaluation` · 430 papers in the corpus · 82 rated high-relevance by the sweep

## 0. Scope

This category is the statistics of *whether a historical result is real*: backtest overfitting and the probability of backtest overfitting (PBO), the deflated and probabilistic Sharpe ratios, minimum track-record length, multiple-testing and false-discovery control across a strategy search, purged/embargoed combinatorial cross-validation, data snooping, look-ahead and survivorship bias, the reality of out-of-sample R² in return forecasting, and transaction-cost discounting of backtest PnL. It matters more to this repo than any single alpha paper, because TradingAgents already ships the plumbing (`evaluate.py`, `trial_ledger.py`, `config_robustness.py`, `coverage_window.py`, `scripts/evaluate_config_gate.py`) and the governing rule is *compute, don't narrate* — so the repo's own eval layer has to survive exactly the audit this literature performs. The gap is in the *statistical* layer: several instruments are crude approximations labelled with the names of rigorous tests.

## 1. Corpus composition

Header counts (authoritative): **430** papers, of which the sweep rated **82 high**, **262 medium**, **86 low**. The evidence pack lists **268** of these as full rows (82 high + the 100 most-recent medium + 86 background); the booklist carries full bibliographic metadata for the **top 60**.

Decade/5-year distribution of the 268 dated evidence rows:

| years | papers |
| --- | --- |
| 2000–2004 | 1 |
| 2005–2009 | 2 |
| 2010–2014 | 9 |
| 2015–2019 | 27 |
| 2020–2024 | 93 |
| 2025–2026 | 136 |

Primary category of the top-60 booklist (a paper may only carry one):

| primary category | papers |
| --- | --- |
| q-fin.ST (statistical finance) | 33 |
| q-fin.RM | 5 |
| q-fin.PM | 4 |
| q-fin.TR | 3 |
| cs.LG | 3 |
| q-fin.CP / stat.ML | 2 each |
| cs.AI, cs.CL, cs.CE, cs.ET, econ.EM, physics.soc-ph, q-fin.GN, q-fin.MF | 1 each |

Dominated by **q-fin.ST** and by the last two years: the "Backtest Methodology" label is applied by the sweep to a very broad set of forecasting-and-selection papers, and roughly half the hand-selected top-60 (`5-yr` buckets 2015: 13, 2020: 22, 2025: 25) is 2025–2026. The recent mass is the LLM/agent strategy-discovery literature re-learning the pre-2020 statistical corrections (deflated Sharpe, PBO, purged CV, trial-count deflation); the durable methodological core — Rej–Seager–Bouchaud's PnL discounting, the Sharpe-information criterion, discrete false-discovery rates — sits in 2016–2019. A large fraction of the medium/background rows attach the category only because they *report* an out-of-sample number, not because they contribute a method; the high-relevance tier is where the actual instruments live.

## 2. Deep reads

### arXiv 2608.23808v2 — Equity Strategy Backtesting: Luck or Edge? The MinervaScore as a Statistical Robustness Grade (2026)

- **Question**: can the heterogeneous pass/fail verdicts of four validation statistics be turned into one auditable post-selection robustness grade?
- **Data**: 359,062 production backtest records; synthetic markets with known ground truth; one pre-registered sealed real-market window.
- **Method**: five gates — Deflated Sharpe Ratio (threshold 0.95), PBO via Combinatorially Symmetric Cross-Validation (threshold ≤ 0.50), Hansen's SPA (≤ 0.10), Minimum Track Record Length, and a hand-built regime-stability composite ρ (≥ 0.60). Pass = logical AND of all five; margins combined by a Lipták-style inverse-normal combination; display 0–100 capped so ≥ 80 appears only when all gates pass.
- **Findings**: separates true signal from lucky backtests at AUROC 0.989 (headline difficulty), but the margin over the GT-Score proxy (0.986) is small, and DSR-alone is the strongest *single* signal (0.988) with the smallest worst-case regret (0.009 vs 0.021). 60–95% of production DSR values saturate at exactly zero, so the DSR *statistic* (not the pass/fail value) is carried into the score by a logit. Pre-registered real-market test produced **no** forward relationship (Spearman ρ_s = 0.013, one-sided p = 0.40).
- **Limitation**: the authors explicitly refuse to claim demonstrated forward predictive power; the regime composite is "the most heuristic component"; score is a ranking layer, not a calibrated probability.
- **Key mechanics for this repo**: MinTRL = `1 + (1 − γ₃·SR + ((γ₄−1)/4)·SR²)·(Φ⁻¹(1−α)/SR)²` is *per-bar, single-strategy* and independent of N — not the same as Minimum Backtest Length, which does depend on N. CPCV with N groups, k test groups yields `C(N,k)·k/N` distinct paths (N=6, k=2 → 15 splits but only 5 paths); conflating splits with paths overstates effective sample size. The multiple-testing correction should use the *effective* number of independent trials, estimated by decorrelating searched parameter vectors (eigenvalue approach), not the nominal configuration count.

### arXiv 2602.00080v1 — The GT-Score: A Robust Objective Function for Reducing Overfitting in Data-Driven Trading Strategies (2026)

- **Question**: does baking anti-overfitting structure into the *search objective* (rather than correcting after) improve generalization?
- **Data**: 50 S&P 500 names, daily OHLCV 2010–2024, three strategies (RSI, MACD, Bollinger), 9 walk-forward splits and 9,000 Monte-Carlo trials over 15 seeds.
- **Method**: `GT = µ·ln(z)·r² / σ_d`, with z a t-style excess-return statistic and z ≤ 1 penalized smoothly; optimization by random search, 25 evaluations/trial, 4y train / 2y validation / 1y step / 30-day embargo.
- **Findings**: walk-forward generalization ratio (validation return / training return) improves **98%** vs baseline objectives; Monte-Carlo paired tests are significant (p < 0.01 vs Sortino and Simple) but with **small effect sizes**.
- **Limitation**: the paper concedes z is "a heuristic gating term … rather than an exact hypothesis test" — fat tails, heteroskedasticity and autocorrelation reduce effective sample size and can miscalibrate a Gaussian z; and the GT-Score carries **no multiple-testing correction** (it never observes how many strategies were tried). Imposes a minimum of 50 trades (`n_min=50`) because a smaller sample makes the z denominator unstable.

### arXiv 2608.27734v1 — What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery (2026)

- **Question**: what remains of LLM-discovered alpha once look-ahead is *inexpressible* and every reported number is deflated by the search's own recorded trial count?
- **Data**: 453-stock point-in-time US equity universe and a 39-ETF multi-asset universe, realistic commissions/spreads/square-root impact/borrow, design vs held-out windows of 4 and 9 years; two frontier models, up to 100 candidates, 5 repeated runs.
- **Method**: agent composes declarative plans only through registry-validated tools; a deterministic audit enforces event publication delays; every evaluation writes a trial-ledger row. DSR takes N and V from the ledger, PBO is CSCV over S=16 blocks, plus stationary-bootstrap CIs and paired tests vs buy-and-hold.
- **Findings**: (i) a deliberately leaky oracle with **Sharpe ratio 35 survives DSR and PBO completely** — deflation and leakage-control are complementary, not substitutes. (ii) Honest evaluation certifies passive premia and rejects *every* discovered strategy. (iii) An "evaporation curve" traces the best in-sample Sharpe rising with trials while the deflation threshold rises faster. (iv) The statistical-power arithmetic shows certifying moderate low-frequency edges needs decades of out-of-sample data or substantial breadth.
- **Limitation**: preprint; the negative result is confined to the (heavily arbitraged) universes tested.

### arXiv 2604.15531v1 — Spurious Predictability in Financial Machine Learning (2026)

- **Question**: how do you falsify a *whole workflow* (feature construction → tuning → selection → portfolio map) rather than a single model?
- **Method**: induce synthetic null reference classes that preserve financial stylistics but remove conditional-mean predictability (including "microstructure placebos"); run the entire workflow on them under strict walk-forward; a workflow producing significant evidence in the null is falsified. For survivors, a Backtest Inflation Factor (BIF) and gap diagnostics quantify selection-induced inflation.
- **Findings**: under a global martingale-difference null the optimized in-sample winner grows as **log K_eff**, where K_eff is the *effective* number of independent strategies after correlation — not the nominal count; walk-forward evaluation stays stochastically bounded under the same null. Random (non-temporal) CV mechanically improves reported volatility-forecast performance under nulls.
- **Relevance**: this treats "does my evaluation protocol itself leak or inflate?" as a testable hypothesis with a placebo.

### arXiv 2605.04004v3 — Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study (2026)

- **Data/method**: 14 signal families, 947 days of 5-minute Micro E-Mini Nasdaq (MNQ) bars, 2021–2025, expanding-window walk-forward; five simultaneous pass criteria (OOS net T ≥ 2.0, ≥ 30 trades/fold, positive net after round-trip friction, consistent direction across 2023/24/25, permutation p < 0.05).
- **Findings**: **none** of the 14 pass all five. 11 fail purely on the cost floor (max gross 0.07–1.50 points/trade vs a 2.0-point MNQ friction floor); three clear friction and fail T-stat or year-stability. Two positive-control signals from a companion program (different architecture) clear all five with margin (T = 3.11 and 4.30).
- **Limitation**: single instrument; the author notes the paper began as a search, so its epistemics differ from an ab-initio null study.

### arXiv 2603.19380v1 — Survivorship Bias in Emerging Market Small-Cap Indices: Evidence from India's NIFTY Smallcap 250 (2026)

- **Question**: how large is survivorship bias when a backtest uses only a current-constituent universe?
- **Data**: 1,437 stocks, 2016–2025, historical index composition reconstructed by market-cap ranking using bhavcopy data that includes delisted names.
- **Findings**: survivor-only backtests overstate annual return by **4.94 pp (23.3%)** (26.17% vs 21.23% true) and Sharpe by **0.097 (9.1%)**; turnover 82.5%, split across delisted (16.1%), graduated (33.1%) and demoted (33.2%) names — all three categories contribute.
- **Limitation**: one index/market; reconstruction accuracy ~85% on historical membership.

### arXiv 2209.05559v6 — Deep Reinforcement Learning for Cryptocurrency Trading: Practical Approach to Address Backtest Overfitting (2022)

- **Question**: can backtest overfitting be turned into a decision rule for *which trained agent to deploy*?
- **Method**: formulate overfitting detection as a hypothesis test; estimate each agent's probability of overfitting; reject agents above a preset threshold; test on 10 cryptocurrencies over 2022-05-01→2022-06-27 (a period containing two crashes).
- **Findings**: less-overfitted DRL agents earn higher returns than more-overfitted agents, an equal-weight strategy, and the S&P DBM index during the crash test.
- **Limitation**: very short (≈2-month) test window; the PBO estimate is used as a filter, not as a calibrated forward probability.

### arXiv 2311.10685v3 — High-Throughput Asset Pricing (2023/2025 rev.)

- **Question**: should you mine *less* (theory-restrict) or mine *rigorously* (condition on search)?
- **Data/method**: empirical-Bayes mining of **136,000** long-short strategies built from accounting ratios, past returns and ticker symbols; select top 1% by EB-predicted Sharpe; no look-ahead.
- **Findings**: the data-mined portfolio earns **5.7%/yr** out-of-sample 1983–2020 versus 5.9%/yr for the average of 200 published strategies — matching top-journal performance while being real-time constructible. Naive argmax-of-Sharpe selection often picks the *same* strategies an ideal Bayesian would (Prop. 1), but the naive *performance estimates* are distorted. Common multiple-testing methods used in finance **fail to identify most out-of-sample performers**.
- **Limitation**: predictability concentrates in accounting strategies, small stocks and pre-2004 — its contemporary edge is thinner.

### arXiv 1811.06766v2 — Technical Analysis and Discrete False Discovery Rate: Evidence from MSCI Indices (2018)

- **Data/method**: >21,000 technical trading rules on 12 categorical/country MSCI markets, 2004–2015, rolling forward structures; introduces DFRD^±, an adaptive, more-powerful discrete-p-value false-discovery-rate control.
- **Findings**: after data-snooping control, technical analysis retains short-term value in advanced, emerging and frontier markets; profitability is state-dependent (financial stress, economic environment, market development); cross-validation stresses frequent rebalancing and the variability of rule profitability.
- **Relevance**: a worked demonstration that a family of tens of thousands of rules can be screened with an FDR rather than a single best rule's t-stat.

### arXiv 1902.01802v1 — How should you discount your backtest PnL? (2019)

- **Question**: by what factor should in-sample PnL be haircut?
- **Model**: strategy PnL as drifted Brownian motion; the researcher only pitches strategies whose *estimated* SR clears a deployment threshold, and "improves" sub-threshold ones by tweaking building blocks — both the favourable-noise realization and the tweaking produce overfitting.
- **Finding**: a simple closed-form factor for discounting in-sample PnL; the calibration embedded in the paper: for true SR = 0.5 a PnL needs **43 years** of daily data to be 99.9% distinguishable from noise, so appraisal of low-Sharpe strategies is "fraught with risk"; residual (vs existing book) Sharpes of 0.3–0.5 are common in CTA.
- **Relevance**: a PnL *haircut* is a different instrument from a Sharpe deflation and is the missing one in this repo.

### arXiv 1602.06186v5 — Noise Fit, Estimation Error and a Sharpe Information Criterion (2016)

- **Question**: the in-sample Sharpe maximized over a k-dimensional parameter space is biased; can it be corrected and used for model selection?
- **Method**: derives an unbiased Sharpe estimator adjusting for **both** noise-fit and estimation-error bias, then uses the adjusted Sharpe as a model-selection criterion analogous to AIC.
- **Finding**: selecting the model with the highest *adjusted* Sharpe selects the model with the highest estimated out-of-sample Sharpe, in the same way AIC selection does for log-likelihood.
- **Relevance**: gives an explicit k-parameter-count penalty and a selection rule, exactly what `config_robustness` gestures at without a statistic.

### arXiv 2101.10942v2 — Absolute Value Constraint: The Reason for Invalid Performance Evaluation Results of Neural Network Models for Stock Price Prediction (2021)

- **Question**: is prediction-error (MSE/MAE-style) evaluation of stock predictors statistically valid?
- **Data/method**: 20 China A-share and 20 US (NASDAQ/NYSE) stock datasets over six years, six shallow/deep nets, four prediction-error measures.
- **Finding**: the absolute-value constraint means the same prediction error says nothing about *direction*; PE only partially reflects accuracy and **cannot** reflect directional change, so it is unfit as an evaluation criterion and can mislead deployment.
- **Relevance**: a crisp statement of why this repo's directional hit-rate/IC evaluation, not price-level error, is the right surface.

### arXiv 2602.07841v3 — A Nontrivial Upper Bound on the Out-of-Sample R² in Return Forecasting (2026)

- **Question**: how high can out-of-sample R² in return forecasting possibly be?
- **Method**: define a "coin-flip oracle" that, at the same directional accuracy, theory-outperforms practical models in MSE; its R²_OOS is a **quadratic function of directional accuracy** and therefore a tractable upper bound.
- **Finding**: empirical R²_OOS of common predictive models is bounded by this quadratic across multiple forecasting scenarios.
- **Relevance**: a closed-form ceiling tying the repo's directional-accuracy instruments (`alpha_eval.ceiling_ratio`, `calibration.excess_accuracy`) to a maximum attainable R².

### arXiv 2608.21888v1 — Short-horizon mean reversion in cryptocurrency markets: a matched cross-market measurement (2026)

- **Data/method**: one matched, strictly out-of-sample walk-forward protocol on 183 Binance pairs vs 187 US stocks/ETFs at 15-minute horizons, plus an exact permutation null, artifact battery and a frozen six-month holdout.
- **Findings**: directional reversal is significant in 90% of crypto pairs vs 2.7% of US names; the signal lives in *signs* not magnitudes (lag-1 autocorrelation near zero yet betting against the previous candle captures most of it); gross edge peaks near **1.3 bp** per trade against a **5 bp** cheapest round-trip cost — "large enough to detect, too small to clear" benchmark costs. Class-mean AUC gap +0.031 as designed, +0.011 under the most conservative accounting.
- **Limitation**: gains descriptive, not identified; mechanism evidence stated at exactly its strength.

### arXiv 2607.12248v2 — When Directional Accuracy Lies: A Base-Rate-Honest Benchmark for LoRA-Adapted TimesFM on Equity Forecasting (2026)

- **Question**: is a high directional-accuracy number skill or a base rate?
- **Method**: frozen-data benchmark, expanding walk-forward, stratified held-out-ticker split, honest baselines (zero-shot TimesFM, always-up, random-walk, persistence, AR(1)), paired McNemar/Diebold-Mariano tests under Benjamini-Hochberg FDR control; headline metric is **excess accuracy over the always-up base rate**.
- **Findings**: an apparent ~80% directional accuracy is a ~0.70 always-up base rate, and the fine-tuned model scores *below* it; pooled LoRA shows no directional skill at any horizon on either universe (excess accuracy centred on zero, negative at six months); per-sector specialization is significantly *worse* than pooled (DM p < 0.001 at h = 128).
- **Limitation**: negative result for one pretrained model family; the contribution is the protocol.

### arXiv 2609.04420v1 — Optimal Stratified Allocation for Rare-Event Onset Forecasting in Dependent Sequences (2026)

- **Question**: how should a small evaluation budget be allocated when positives are <1%?
- **Method**: exact finite-population variance of the class-weighted risk estimator under stratified sampling without replacement; Neyman-optimal allocation; Serfling bound transfers allocation to selection error; five purged forward evaluation blocks.
- **Findings**: the class-imbalance multiplier inflates the positive stratum's dispersion by exactly the imbalance ratio, so the optimal allocation ratio is free of that ratio and **equal allocation displaces proportional allocation** as the default; efficiency gain `1/{4π(1−π)}` when classes are equidispersed. Application: forward-onset detection on 350 US equities 2004–2011 (<1% positives); average precision 5.8/3.1/2.3× prevalence at h = 5/10/20; predicted design ordering reproduced exactly for h = 10.
- **Limitation**: no backtest and no profitability claim; dependence bound is asymptotic.

### arXiv 2606.31251v1 — Regime-Conditional Distributional Comparison of Trading Strategies: A GAMLSS/ZAGA Framework Applied to the S&P 500 (2026)

- **Question**: does collapsing a strategy comparison to one full-horizon metric discard regime information?
- **Method**: walk-forward backtest of 146 OOS folds on the S&P 500 (2002–2025); Adjusted Information Ratio (IR*) per fold for an SVM strategy (SVMP) and buy-and-hold; jointly model the IR* sequences with a GAMLSS / Zero-Adjusted-Gamma response conditioned on realized volatility and cumulative momentum; parametric-bootstrap tests at six representative regimes.
- **Finding**: the SVMP-vs-BH dominance relationship is **regime-conditional** — it flips by market state, which the single-number comparison hides.
- **Limitation**: one index and one strategy family; ZAGA is a modelling choice.

### arXiv 1602.07599v4 — Backtesting Lambda Value at Risk (2016)

- **Question**: how do you backtest a risk measure (λ-VaR) rather than a return series?
- **Method**: three nonparametric tests for λ-VaR — one unilateral (small samples), one bilateral asymptotic, one simulation-based for comparing λ-VaRs under different distributional assumptions.
- **Finding**: a backtesting exercise confirms λ-VaR's higher performance relative to plain VaR, especially when estimated with distributions that capture tail behaviour.
- **Relevance**: an example of *forecast backtesting* (exception counting) as distinct from *strategy backtesting*; the repo's VaR/tail surfaces lack an exception-counting backtest.

## 3. Learnings applicable to this repo

### L1. `pbo_flag` is not PBO — replace it with a CSCV estimate
- **Source**: `arXiv 2608.23808v2` (2026) — MinervaScore; corroborated by `arXiv 2608.27734v1` (2026) — honest evaluation.
- **Finding**: the Probability of Backtest Overfitting is estimated by Combinatorially Symmetric Cross-Validation: partition into S blocks, form all symmetric in/out combinations, and PBO = P(the in-sample-best candidate's out-of-sample logit rank ≤ 0) — a *probability*, computed from the full candidate×fold performance matrix. The repo's `pbo_flag` is a single boolean over one best index.
- **Repo surface**: `tradingagents/strategies/evaluate.py::pbo_flag`.
- **Status**: `partial` (a crude flag exists; the CSCV probability does not — verified by reading `evaluate.py` around the function and its `__all__`).
- **Concrete step**: add `cscv_pbo(candidates_by_fold, S=16)` returning the fraction of in-sample-winner-below-median cases, keep `pbo_flag` as a documented degraded path, and have `scripts/evaluate_config_gate.py` report the probability rather than a single-index flag.

### L2. Add Minimum Track Record Length as a per-strategy sufficiency gate
- **Source**: `arXiv 2608.23808v2` (2026) — MinervaScore.
- **Finding**: MinTRL = `1 + (1 − γ₃·SR + ((γ₄−1)/4)·SR²)·(Φ⁻¹(1−α)/SR)²` gives the minimum track length for an observed Sharpe to differ from zero at confidence 1−α; it is a function of one strategy's skew, kurtosis and Sharpe and is independent of N. It is distinct from Minimum Backtest Length, which depends on N.
- **Repo surface**: `(new module)` — no minimum-track-record-length symbol exists (`grep min_track|mintrl|track_record_length` over `tradingagents/` and `scripts/` returns nothing).
- **Status**: `absent`.
- **Concrete step**: add `min_trl(returns)` beside `probabilistic_sharpe` in `evaluate.py` and publish it next to every reported Sharpe so a short, high-Sharpe backtest can be flagged as under-length.

### L3. Deflation must be indexed to the *recorded* search, not a caller's integer
- **Source**: `arXiv 2608.27734v1` (2026) — honest evaluation; `arXiv 2608.23808v2` (2026) — MinervaScore.
- **Finding**: in a system that records its own search, DSR's N and dispersion V come from the trial ledger, and the "evaporation curve" (best in-sample Sharpe vs the rising deflation threshold) is the diagnostic. A hard-coded trial count silently decouples the reported number from the search that produced it.
- **Repo surface**: `tradingagents/strategies/trial_ledger.py::trial_stats` and `tradingagents/strategies/evaluate.py::deflated_sharpe_report`; consumer `scripts/evaluate_config_gate.py::gate_verdict`.
- **Status**: `partial` — `deflated_sharpe_report` already supports a measured dispersion read from the ledger (`trial_stats`), but `gate_verdict` calls `deflated_sharpe(returns, n_trials=trials)` with a default `trials=20` and never reads the ledger (verified).
- **Concrete step**: have `gate_verdict` read N and V from `trial_ledger.trial_stats` when the gate is on and fall back to the argument only when off, so the G5 gate's deflation is the search's own.

### L4. Leakage-safety and deflation are complementary — a leaky oracle survives DSR and PBO
- **Source**: `arXiv 2608.27734v1` (2026) — honest evaluation.
- **Finding**: a planted look-ahead oracle posting Sharpe 35 passes DSR and PBO completely. Statistical correction cannot detect a leak that is available to the model; leakage must be made *inexpressible* structurally (registry-validated feature surface) and reinforced by a search ledger.
- **Repo surface**: `tradingagents/strategies/trial_ledger.py` (search recording) and the PIT invariant in `tradingagents/strategies/data_quality.py`.
- **Status**: `partial` — the repo records candidate evaluations and enforces a PIT invariant on some inputs, but there is no single registry-gated action surface through which every evaluated candidate must pass (verified across `trial_ledger.py`, `data_quality.py`).
- **Concrete step**: route every evaluated candidate through one `trial_ledger.record` entry point (as `alpha_zoo` partially does) so the ledger cannot be bypassed, and add a leakage-safe feature allow-list checked at evaluation time.

### L5. Effective multiplicity, not nominal trial count
- **Source**: `arXiv 2608.23808v2` (2026) — MinervaScore; `arXiv 2604.15531v1` (2026) — Spurious Predictability.
- **Finding**: the in-sample winner grows as log K_eff, and K_eff is the effective number of *independent* strategies after decorrelation (eigenvalue-based); correlated configurations must not be counted as independent searches. Using the nominal count over-deflates, using the raw row count over-trusts.
- **Repo surface**: `tradingagents/strategies/trial_ledger.py::trial_stats`.
- **Status**: `partial` — `trial_stats` returns N as the row count and V as the Sharpe variance; no decorrelation/effective-N estimator exists (verified).
- **Concrete step**: add an optional `n_effective` estimate derived from the correlation of the ledger's candidate return series, and allow `deflated_sharpe_report` to consume it.

### L6. Report excess accuracy over the base rate, never raw directional hit rate
- **Source**: `arXiv 2607.12248v2` (2026) — base-rate-honest benchmark; `arXiv 2101.10942v2` (2021) — absolute-value constraint.
- **Finding**: an apparent ~80% directional accuracy was a ~0.70 always-up base rate; the headline metric must be excess accuracy over the same-rows always-up baseline, tested per walk-forward fold. Prediction-error metrics cannot substitute because the absolute-value constraint hides direction.
- **Repo surface**: `tradingagents/strategies/calibration.py::excess_accuracy` (and `tradingagents/strategies/alpha_eval.py::insight_accuracy`).
- **Status**: `shipped` (gate `enable_accuracy_ceiling`, default off — verified in `calibration.py`).
- **Concrete step**: publish `excess_accuracy` beside every hit-rate/scorecard row by default so no raw accuracy reaches a report without its base rate.

### L7. Discount in-sample PnL with an explicit haircut factor, not only a Sharpe deflation
- **Source**: `arXiv 1902.01802v1` (2019) — How should you discount your backtest PnL?
- **Finding**: in-sample PnL overfitting has two sources (favourable-noise realization, and researcher "improvement" of sub-threshold strategies); both yield a closed-form factor by which in-sample PnL should be discounted. For true SR = 0.5, 43 years of daily data are needed for 99.9% confidence — a PnL-level haircut, not a Sharpe subtraction.
- **Repo surface**: `tradingagents/strategies/evaluate.py::deflated_sharpe`.
- **Status**: `partial` — the repo deflates a Sharpe, never a PnL/return series (verified; `simple_long_pnl` in `backtest_engine.py` has no discount path).
- **Concrete step**: add `discount_in_sample_pnl(returns, sr_threshold)` implementing the paper's factor and publish the discounted return beside `total_return`.

### L8. The gross edge must clear a stated cost floor before any inference
- **Source**: `arXiv 2608.21888v1` (2026) — matched cross-market; `arXiv 2605.04004v3` (2026) — MNQ falsification.
- **Finding**: the crypto reversal edge (~1.3 bp/trade) is detectable but below the 5 bp round-trip cost; 11 of 14 MNQ families fail purely because gross return (0.07–1.50 pts) is under the 2.0-point friction floor. A signal test that ignores the cost floor is testing nothing.
- **Repo surface**: `tradingagents/strategies/backtest_models.py::square_root_impact` / `make_cost_fn` and `tradingagents/strategies/evaluate.py::net_returns`.
- **Status**: `shipped` — cost functions and net-return subtraction exist (`backtest_models.py`, `evaluate.py`); the missing piece is a *standard* "must clear the floor" precondition in the gate.
- **Concrete step**: add a cost-floor precondition to `scripts/evaluate_config_gate.py`: reject before significance testing when mean gross edge per trade is below the modelled round-trip cost.

### L9. Label survivor-only universes and refuse the statistic when coverage is padded
- **Source**: `arXiv 2603.19380v1` (2026) — survivorship bias.
- **Finding**: survivor-only backtests overstate annual return 23.3% and Sharpe 9.1% in Indian small-caps; the label and the coverage window must travel with the result.
- **Repo surface**: `tradingagents/strategies/coverage_window.py::SURVIVOR_ONLY` / `coverage_window` (consumed by `data_quality.panel_statistic`).
- **Status**: `shipped` (2026-10-04; was `partial`) — `coverage_window` and the `enable_coverage_window` refusal path are used by `data_quality.panel_statistic`, `triadic_stress.py` and `scripts/coverage_scorecard.py`, **and the label now reaches a findings record**: `coverage_window.universe_label()` returns `SURVIVOR_ONLY` for a current-constituent universe (fail-safe — only an explicit `point_in_time` declaration clears it), and `scripts/score_panel.build_panel` writes it as the panel record's `universe_label`, so the producer that *knows* the universe labels it instead of a frame reader guessing.
- **Concrete step**: ~~have backtest/findings writers attach `SURVIVOR_ONLY` when the universe is current-constituent~~ — **done 2026-10-04**: the findings writer is `scripts/score_panel.build_panel`, whose record carries `universe_label`.

### L10. Falsify the *workflow* against placebo/null reference classes, not just the thesis
- **Source**: `arXiv 2604.15531v1` (2026) — Spurious Predictability.
- **Finding**: run the entire pipeline (features → tuning → selection → portfolio map) on induced-null environments preserving financial stylistics; any workflow that produces significant walk-forward evidence there is falsified. Random CV mechanically inflates volatility forecasts under nulls.
- **Repo surface**: `tradingagents/strategies/falsification.py` (thesis-condition falsification — a *different* sense of "falsification") and `(new module)` for the workflow audit.
- **Status**: `absent` — `falsification.py` binds bull/bear theses to numeric invalidation levels and monitors closes; it has no placebo/reference-class machinery (verified).
- **Concrete step**: add a `null_audit` that replays the repo's evaluation path on a shuffled/zero-predictability panel and reports whether the pipeline still produces significant evidence (a `falsified` flag), gated off by default.

### L11. Multiple-testing control across a rule family, not per rule
- **Source**: `arXiv 1811.06766v2` (2018) — DFRD; `arXiv 2311.10685v3` (2023) — EB high-throughput.
- **Finding**: a family of >21,000 rules needs an FDR/FWER control; per-rule t-stats/IC alone generate false rejections. Common finance multiple-testing methods also fail to identify true OOS performers, so the correction must be dependence-aware (adaptive/knockoff/empirical-Bayes style).
- **Repo surface**: `tradingagents/strategies/evaluate.py::family_materiality` (Benjamini-Yekutieli step-up over the stationary-bootstrap machinery) and `tradingagents/strategies/rule_eval.py` (`evaluate_rule` — per-rule forward returns with no family adjustment).
- **Status**: `partial` — `family_materiality` exists (gate `enable_materiality_verdict`, default off) but `rule_eval.py` evaluates rules individually and never calls it (verified).
- **Concrete step**: batch `rule_eval` outputs through `family_materiality` so a rule is reported against the family's false-discovery rate rather than in isolation.

### L12. Regime-condition the strategy comparison instead of collapsing it to one number
- **Source**: `arXiv 2606.31251v1` (2026) — GAMLSS/ZAGA.
- **Finding**: over 146 walk-forward folds on the S&P 500, strategy dominance flips by regime; a single full-horizon metric hides the sign change. The distributional model reports regime-specific differences in expected performance and its variance.
- **Repo surface**: `tradingagents/strategies/regime_performance.py` and `tradingagents/strategies/regime.py`.
- **Status**: `partial` — the repo has regime-conditioned performance (`regime_split_performance` in `evaluate.py`) but no distributional test of whether a strategy's advantage *changes sign* by regime.
- **Concrete step**: extend `regime_performance` to report the sign of the strategy-minus-benchmark difference per regime with a bootstrap interval, so "dominance" is stated per state.

## 4. Where this repo is already ahead of the literature

- **Search-aware deflation with measured dispersion is already wired.** `evaluate.deflated_sharpe_report` accepts `sharpe_dispersion` read back from `trial_ledger.trial_stats` and tags the provenance `measured` vs `assumed` — the honest-evaluation paper's core architecture (2608.27734v1) is present, including the tag-on-the-number discipline. MinervaScore explicitly *asks* for N and V to come from a record; this repo already built that record (`trial_ledger.py`, H1).
- **Combinatorial purged CV with configurable embargo exists.** `evaluate.purged_cpcv_splits` yields all `C(N−1,k)` train/test paths with a purge around the test block (`alpha_zoo`, `score_panel`, `analysis_tools` consume it) — matching the CPCV the MinervaScore paper treats as state-of-the-art, including the paths-vs-splits distinction.
- **White's Reality Check and Hansen's SPA are implemented** (`evaluate.reality_check`, `evaluate.spa`) over a stationary bootstrap with block length — the familywise instruments the sweep's papers mostly only *cite*.
- **A three-way materiality verdict with an explicit INCONCLUSIVE** (`evaluate.materiality_verdict`) already refuses the common error of reading an underpowered test as a null — a discipline several papers in this category (e.g. 2607.12248v2) have to construct by hand.
- **Base-rate honesty from wave 1 is shipped**: `calibration.excess_accuracy` and `alpha_eval.ceiling_ratio` already implement the always-up-baseline and the accuracy-ceiling direction before the 2026 papers formalised it.
- **Survivorship refusal machinery exists** (`coverage_window` + `data_quality.panel_statistic` refuse padded windows) — ahead of the many survivor-only papers in the corpus; only the *label* propagation is missing (L9).

## 5. Defects or risks the literature exposes

1. **`pbo_flag` is a single-index boolean, but the repo calls it PBO.** `scripts/evaluate_config_gate.py` reports reason `"PBO"` from `pbo_flag` (line 46–51), and `score_panel._pbo` labels its output PBO. The literature's PBO is a CSCV *probability* over the candidate×fold matrix (2608.23808v2 §3; 2608.27734v1 §4.2), not "did the one best-IS candidate fail OOS". The boolean is strictly coarser and can be false-negative when the best-IS pick is merely second-worst OOS. Repo: `tradingagents/strategies/evaluate.py::pbo_flag`; `scripts/evaluate_config_gate.py:46`.
2. **G5 gate deflates by a hard-coded trial count — fixed 2026-10-04 (D2).** `gate_verdict` called `deflated_sharpe(returns, n_trials=trials)` with default `trials=20` and never read `trial_ledger` (verified `scripts/evaluate_config_gate.py:47`). Against 2608.27734v1 this was exactly the "author's estimate" failure the honest-evaluation paper removes — the deflation was decoupled from the search that produced the series, and the dispersion path (`deflated_sharpe_report`) was bypassed entirely. **Now** `gate_verdict` reads N and V from `trial_ledger.trial_stats` whenever `enable_trial_ledger` is on (default off, so a gate-off verdict is unchanged), and the returned record carries `n_trials` and `dispersion` (`measured` / `caller (...)`) so a published number can never be read without knowing which search deflated it.
3. **Purge without embargo is the default on the panel path.** `purged_cpcv_splits(..., embargo=0)` and every `score_panel`/`score_panel_eval` caller use `embargo=0`, so folds have a purge gap but no embargo after the test block (verified `evaluate.py:339–362`, `score_panel.py:1144,1242`, `score_panel_eval.py:103`). Only `analysis_tools.py` (embargo=1) and `alpha_zoo` (embargo=forward_days) pass a non-zero embargo. Lopez de Prado's CPCV (which 2608.23808v2 and 2608.27734v1 both require) needs *both* purge and embargo; an embargo of 0 re-admits leakage for serially correlated features.
4. **DEFLATED SHARPE MIXES UNITS — fixed 2026-10-04 (D1).** `deflated_sharpe` subtracts the selection threshold from `sharpe()`, which is an *annualized* CAGR-based Sharpe, while the assumed threshold `sqrt(2·ln N)` is the expected maximum of standard-normal (unit-variance, per-observation) Sharpe draws. The Bailey–López de Prado DSR (2608.27734v1 §4.1) applies the PSR/DSR correction to the *per-observation* SR with the T-dependent denominator `sqrt(1 − γ₃·SR + ((γ₄−1)/4)·SR²)`. The repo's version omits the T and the skew/kurtosis denominator from the deflation and mixes annualized with unit-scale thresholds; `probabilistic_sharpe` exists separately but was not composed in. **Now it is:** `evaluate.deflated_sharpe_ratio` applies the paper's Eq. (2) in per-observation units by composing `probabilistic_sharpe` with the selection threshold, and returns a probability; the legacy difference is retained (bit-for-bit promise) with the unit caveat stated in its docstring, and `deflated_sharpe_report` carries both. Repo: `tradingagents/strategies/evaluate.py::deflated_sharpe`, `::deflated_sharpe_ratio`, `::probabilistic_sharpe`.
5. **`SURVIVOR_ONLY` was defined but never written — fixed 2026-10-04 (D4).** The label existed solely at `tradingagents/strategies/coverage_window.py:45`; no findings record consumed it. Against 2603.19380v1 (a 23.3% return overstatement), a backtest could be published without carrying the survivor label — the coverage reader was ahead, the label propagation absent. It now propagates: `coverage_window.universe_label()` is the single label decision, and `scripts/score_panel.build_panel`'s record carries `universe_label`, defaulting to the labelled state (no point-in-time membership source exists in this repo) and clearing only on an explicit `point_in_time` declaration.
6. **No minimum-track-record-length check anywhere.** `grep min_track|mintrl|track_record_length` over `tradingagents/` and `scripts/` finds nothing, so a 6-month, Sharpe-2.9 backtest can clear `deflated_sharpe` while being far shorter than MinTRL requires (2608.23808v2 §3). The G5 gate's `pbo_flag`/DSR pair has no length floor.

## 6. Limits of this review

- I read the **full text of 16 papers** (abstract, introduction, and method/results sections within pages 1–~120 of each PDF as needed); several others in the high-relevance tier were read only at abstract/intro level from the evidence pack and are not listed in §2. The 82 high + 262 medium + 86 low evidence rows were used as an abstract-level map, not read in full.
- The repo statuses assert only what the cited symbol does in the module I read; I did not run any test, linter or the gates, and I did not execute `evaluate_config_gate.py`. Where a status is `shipped` (e.g. `excess_accuracy`, `reality_check`), the gate default (`enable_materiality_verdict`, `enable_accuracy_ceiling`, `enable_trial_ledger`, `enable_coverage_window` all default off) means the instrument is not exercised on the default path.
- Corpus composition in §1 uses the 268 dated rows of the evidence pack rather than all 430 (the remaining 162 medium rows are not itemised in the pack); the top-60 category table is a sample of the highest-scored papers, so its q-fin.ST share is a lower bound on the whole category's share.
- One booklist paper (`2412.11432v2`, deep-learning stat-arb replication with OOS Sharpe occasionally >10) could not be opened — the file is absent from `E:/fin paper/` — and is therefore not a §2 deep read; its point (a Sharpe >10 as a symptom of overfitting) is covered by the PBO/deflation papers.
