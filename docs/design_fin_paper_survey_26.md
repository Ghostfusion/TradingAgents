# Design: What the 2026 arXiv q-fin corpus says to this engine

**Status:** SURVEY - no code changes; feeds six design docs (see §7)
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** Read all 309 `26xx` papers in `e:\fin paper` (arXiv 2601-2609, Jan-Sep 2026), judge each
against this engine's actual surfaces, and route the ones that carry a usable producer into
per-theme design docs. Nothing here authorises a change: every adoption is proposed, gated and
default-off, per the house pattern.
**Method:** `.state/metadata.jsonl` supplied title/abstract for all 309; full text was extracted
from all 309 PDFs and read directly for the shortlist. Every claim of the form "the repo already
does this" was checked against the tree by grep, not recalled.

---

## 1. Executive summary

### The corpus in one paragraph

309 papers, all cross-listed into `q-fin`, dominated by `q-fin.ST` (133 primary). The single
largest concentration - 42
of the 142 papers that map to anything here - is **not** a signal
technique at all: it is a body of work on *how to tell whether a financial claim is real*.
Selection bias, look-ahead that survives statistical correction, base rates, placebo environments,
rejection auditing, and the measurement error carried by the data itself. That is the corpus's
most transferable content, and it is the theme this engine is least equipped for, because the
engine's own output is a claim.

The second observation is a negative one, and it recurs across independent papers: **most of what
can be forecast is volatility, not returns.** A cross-sectional volatility rank has multi-step
memory; the matching return rank is close to unforecastable. A trend-following P&L decomposes
into autocorrelation and drift terms that are separately measurable and usually small. Several
papers report an LLM's apparent edge dissolving against a non-LLM baseline fed the *same*
decision-time inputs. The engine scores four engines into one composite, and this corpus says the
volatility-and-structure channels are where the measured edges actually are.

### The verdict, by count

| Relevance | Papers | What it means here |
|---|---:|---|
| high | 31 | carries a producer that fits one engine's ownership today |
| medium | 111 | a usable method, but it needs data or training this engine lacks, or it duplicates a surface |
| low | 124 | correct and well-executed, but the object is out of scope (crypto, FX, insurance, energy, sports) or the method is standard under a new name |
| none | 43 | no tradable object for a daily-horizon US equity/ETF engine |

### The one-sentence thesis

> This corpus does not hand the engine new alpha; it hands it an audit standard, a set of
> coverage-aware estimators, and a repeated reminder that the volatility-and-structure channels
> are forecastable while the return channel mostly is not.

---

## 2. Why the evaluation theme dominates

Four independent papers converge on the same structural claim: **statistical correction alone is
not enough, because the correction is applied after the leak has already entered.**

- **2608.27734** builds a strategy-discovery agent that can only act through registry-validated
  tools whose feature space excludes look-ahead *by construction*. It then plants a deliberately
  leaky oracle posting **Sharpe 35** - and reports that the oracle **survives both the Deflated
  Sharpe Ratio and the probability-of-backtest-overfitting test completely**. No amount of
  deflation catches it. The fix is expressibility, not discipline. Its second contribution is a
  **trial ledger**: every evaluation the agent performs is recorded, and every reported Sharpe is
  deflated by that count. Across a 453-stock point-in-time US universe it certifies passive
  benchmarks and rejects every LLM-discovered strategy, while showing the leakiest constructions
  surviving the statistical net.
- **2609.00731** argues that an autonomous discovery system is itself a research process that can
  get lucky, and that backtesting its *output* cannot distinguish a well-calibrated gate from a
  leaked one from a favourable in-sample window. It proposes scoring **productivity, performance
  and novelty jointly** - no one meaningful without the other two - and re-executing the whole
  discovery loop at a sequence of historical decision dates.
- **2602.07841** supplies a hard, cheap ceiling: the out-of-sample R² of any return forecast is
  bounded above by `kappa * (2*DA - 1)^2`, with `kappa` estimated from the evaluated window's
  realized returns and a GARCH(1,1) conditional-vol series. A reported R² above that line is
  arithmetically impossible, which makes it a *falsifier* rather than a caution.
- **2607.20093** audits five popular retail signal families and finds them failing on three
  separate gates: statistical edge after multiplicity control, economic viability after costs, and
  finite-bankroll survival under leverage. Its methodological core is that a non-significant
  result is recorded as **INCONCLUSIVE, not as evidence of no edge**, with hierarchical
  Benjamini-Yekutieli control and an equivalence test to separate the two.

Three more papers make the leakage point concrete at the input boundary, which is where this
engine actually operates:

- **2606.22719** shows a walk-forward backtest reading the current-vintage CPI value leaks future
  information, because the BLS publishes about ten days after the month-end decision date. Its
  own honest pipeline, restricted to decision-time inputs plus an archived nowcast, reaches only a
  median monthly rank IC of +0.154 with a bootstrap interval **that includes zero** - and a plain
  kNN macro-analog baseline recovers a comparable median. The LLM's apparent advantage is largely
  the data, not the model.
- **2604.15531** falsifies a complete prediction-to-position workflow by re-running it against
  five synthetic reference classes (white noise, regime-switching volatility, bid-ask bounce,
  zero-alpha factor, GARCH clustering) and requiring the walk-forward winner to stay inside the
  null band before any factor is credited.
- **2607.02823** measures label error directly and finds it does not generalise over time - the
  ground truth itself is a decaying instrument.

## 3. The recurring negative result: forecasts exist, but in volatility

Stated separately because it is the corpus's most actionable *positive* finding, and because it
cuts against the engine's four-engine composite:

| Paper | The finding |
|---|---|
| 2607.27461 | From one year of daily returns, a name's 10-decile **volatility-rank** transition matrix is forecastable with multi-step memory; its **return-rank** matrix is close to unforecastable. Sharpe 1.06/1.32 OOS vs market 0.78/1.14 net of 5bp |
| 2607.19497 | Trend-following P&L decomposes into autocorrelation and drift terms on volatility-normalized returns; alpha is *excess low-frequency spectral mass*, and the cost-optimal filter span is closed-form |
| 2607.24410 | A forward covariance for the equity cross-section is estimable from point-in-time **characteristics alone**, which also covers names with too little return history to estimate covariance from returns |
| 2608.12251 | Regime information is most useful as a **soft gate routing residual corrections**, not as an input to the forecast |
| 2605.17117 | Regime detection: the classical **Absorption Ratio** (d=0.80 offline) nearly matches a learned geometric observable (d=0.83), while the geometric channel's out-of-sample stability drops sharply - and the winner by walk-forward produces ~67% fewer false alarms |

The pattern: structure, rank, volatility and covariance are estimable and stable; the level of
the return is the part that resists. A composite that treats a return-forecast channel as
evidence of equal weight to a volatility channel is mis-weighting its own information.

## 4. Coverage is a first-order variable, not preprocessing

**2603.20237** names and quantifies *temporal coverage bias*: calendar-aligning instruments with
different listing histories extends price history before valid trading began. On 486 instruments,
53 studied in depth, naive alignment **suppresses return volatility by ~20% on average**, distorts
GARCH unconditional variance by **>26%**, and the effect is present in **more than 90%** of
instruments; the severe construction breaks GARCH estimation outright in **22 of 53** cases.
Survivorship bias is distinct: it works by excluding dead instruments and *inflates* performance,
while this works by extending live ones and *depresses* volatility.
**2603.19380** measures the other direction: reconstructing true historical index membership for
India's NIFTY Smallcap 250 finds survivor-only backtests overstate returns by **4.94pp** and
Sharpe by **0.097**.

This lands directly on a house rule already in force - *coverage travels with the number; missing
data is `unavailable`, never zero* - and shows the rule needs a second half: a number computed
over a **padded** window is not merely low-confidence, it is biased in a known direction.

## 5. What already exists (do not rebuild)

Taken first, because a survey that proposes rebuilding shipped work is worthless. Each row was
verified in the tree.

| Paper's instrument | Already in this repo |
|---|---|
| Deflated Sharpe, PBO overfit flag, walk-forward splits, net-of-cost metrics | `tradingagents/strategies/evaluate.py` |
| Robust choice instead of argmax over a config grid | `tradingagents/strategies/config_robustness.py` |
| Immutable prediction rows scored against realized outcomes | `tradingagents/strategies/prediction_ledger.py` |
| Rank IC, IC-IR, quantile spreads, generic over any score series | `tradingagents/strategies/signal_analysis.py` |
| Structured thesis falsification bound to explicit numeric falsifiers | `tradingagents/strategies/falsification.py` |
| Conformal (CQR) bands with stated coverage | `tradingagents/strategies/conformal.py` |
| Decision-level input quality, cross-vendor disagreement, PIT invariant | `tradingagents/strategies/data_quality.py` |
| VaR/CVaR, scenario shocks, drawdown governor | `tradingagents/strategies/book_risk.py` |
| Covariance estimators + HRP + optimizer | `covariance_models.py`, `hierarchical_risk_parity.py`, `portfolio_optimizer.py` |
| HMM / BOCPD / GARCH family, entropy features | `volatility_models.py`, `complexity.py` |
| IV surface, skew, OI, expected move, GEX, OPEX, max pain | `options_surface.py`, `derivatives_gamma.py` |
| A bounded factor-expression DSL with an AST purity gate | `tradingagents/strategies/factor_expressions.py`, `alpha_zoo.py` |
| An LLM-free baseline stack ("does the LLM add anything?") | `tradingagents/strategies/quant_baseline.py` |
| Regime-conditioned performance attribution | `tradingagents/strategies/regime_performance.py` |

Only one of the 309 papers (`2602.00086`) is cited anywhere in the repo today. The rest are new
to it - but a large fraction describe machinery that already has a home.

## 6. Where each theme's design docs live

| Theme | high | medium | Design doc |
|---|---:|---:|---|
| Honest evaluation | 12 | 30 | `docs/design_research_honesty_gates.md` |
| Cross-section and allocation | 7 | 18 | `docs/design_cross_section_and_allocation.md` |
| Regime and state | 3 | 21 | `docs/design_regime_estimation_hardening.md` |
| Risk and tails | 5 | 11 | `docs/design_risk_tail_and_coverage.md` |
| Text, news, disclosure | 3 | 9 | `docs/design_news_and_filing_signals.md` |
| Volatility and options | 0 | 18 | `docs/design_vol_surface_and_vrp.md` |
| Fundamentals and filings | 1 | 4 | `docs/design_news_and_filing_signals.md` (partly) |

---

## 7. Appendix A - the 31 high-relevance papers

Each carries a producer that fits one engine's ownership today.

| id | surface | title | what it gives the engine |
|---|---|---|---|
| `2601.06499v2` | technical_factors | Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO | Offline, run double-selection LASSO over the engine's fundamental control factors to decide which short-horizon price-volume signals (VWAP deviation, volume-flow, reversal) are non-redundant; then compute only the survivors per symbol from daily bars at each rebalance. Owned by technical_factors, refit on a schedule and never inside a run. |
| `2602.00196v1` | technical_factors | Generative AI for Stock Selection | technical_factors (via the analyst layer) runs an LLM+RAG loop emitting point-in-time executable feature code over the engine's price-volume, options and analyst-estimate columns, producing lagged short-horizon signals that are leakage-checked before entering the factor set. |
| `2602.06198v1` | fundamental_engine | Insider Purchase Signals in Microcap Equities: Gradient Boosting Detection of Abnormal Returns | fundamental_engine parses Form 4 (transaction code P) from EDGAR to compute a per-symbol insider-purchase signal - title score, value vs the insider's history, distance from the 52-week high - point-in-time at disclosure, surfaced as a scored fundamental event input. |
| `2602.07066v1` | regime_engine | Algorithmic Monitoring: Measuring Market Stress with Machine Learning | regime_engine aggregates monthly cross-sectional fragility signals (return dispersion, downside extremes, higher moments) over the tracked universe into a calibrated forward stress probability that conditions the regime channel, reporting unavailable when the cross-section is too thin. |
| `2602.07841v3` | backtest_evaluation | A Nontrivial Upper Bound on the Out-of-Sample R^2 in Return Forecasting | Measurement layer computes the ceiling kappa_hat(2DA-1)^2, with kappa_hat formed from the evaluated window's realized returns and a GARCH(1,1) conditional-vol series, then flags any report or score-panel claim whose reported R2_OOS exceeds it. No score engine owns it; it only disciplines claims. |
| `2603.23300v2` | portfolio_construction | Designing Agentic AI-Based Screening for Portfolio Investment | Two LLM screeners (fundamentals, news) deliberate to narrow the candidate basket, then a precision-matrix estimator sets weights; portfolio_construction adopts this screen-then-weight decomposition using its analyst reports as the screeners. |
| `2604.08765v3` | risk_engine | Reliability-Aware ETF Tail-Risk Monitoring | Per held symbol each run, emit a next-day 5% lower-tail estimate plus a quality score (missing fields, OHLC inconsistency, return jump, volume anomaly, stale prices) and an uncertainty score (ensemble dispersion, PCA-Mahalanobis distance, recent breach drift) that widens the estimate or marks it unavailable; owned by risk_engine's risk_score. |
| `2604.15531v1` | backtest_evaluation | Spurious Predictability in Financial Machine Learning | Run each scored strategy end-to-end against five synthetic reference classes (white noise, regime-switching volatility, bid-ask bounce, zero-alpha factor, GARCH clustering) and require its walk-forward winner to stay inside the null band before any factor is credited; owned by backtest_evaluation, results written to the findings ledger. |
| `2604.17327v1` | measurement_provenance | Signal or Noise in Multi-Agent LLM-based Stock Recommendations? | Embed each analyst report and the PM's final thesis with the same text model, NNLS-project the thesis vector onto the four report vectors to attribute per-run influence, and score picks against same-date, same-count random baskets plus a cross-sectional IC; owned by measurement_provenance. |
| `2604.19476v2` | peer_universe | Cross-Stock Predictability via LLM-Augmented Semantic Networks | Build each symbol's candidate peers from 10-K embedding similarity, let the LLM classify every candidate edge (competitor, supply chain, peer, substitute and so on), drop competitor edges, then aggregate pair z-score divergence with co-movement weights into a per-symbol mean-reversion signal; owned by peer_universe. |
| `2605.30363v2` | regime_engine | Enhancing Regime Shift Detection Using Unstructured Data: A Study on the Treasury Market | regime_engine would feed central-bank/policy text to an LLM that proposes candidate shift dates, then validate each candidate with a likelihood-ratio VAR test on the market/macro panel (and accept data-detector candidates via an LLM text check), emitting a dated, cross-validated regime-shift set instead of a single-model label. |
| `2606.03457v1` | news_engine | Hybrid News Sentiment Engine: Real-Time Market Analysis via Adaptive Ensemble Learning on News-Price Pairs | news_engine would maintain TF-IDF clusters of incoming headlines and, per cluster, the rolling realized price reaction over the engine's horizon; new headlines are scored by their best-matching cluster mean, and lexicon/LLM/statistical signals are reweighted by each signal's recent Spearman correlation with realized moves. Inputs are timestamped headlines plus concurrent price snapshots. |
| `2606.22719v1` | backtest_evaluation | Leakage-Aware Benchmarking of LLM Forecasting: Real-Time Nowcasts as the Decision-Time Input for Macro Factor Ranking | The measurement layer adds a decision-time leakage guard: every input a report or score cites carries a publication timestamp, and anything not observable at the decision date (current-vintage CPI, revised macro, vendor restatements) is lag-shifted or replaced by an archived nowcast; any LLM signal is also re-scored against a non-LLM kNN analog on the identical input set. |
| `2607.01377v1` | cross_section | Liquidity Premium and Investment Horizons | Per symbol-month compute signed order flow and two lambda estimates (within-month price-impact regression and an Amihud ratio) from daily volume and returns, plus intraday trade direction where available, then rank them cross-sectionally one month ahead as an entry to the technical factor set and cross-sectional rank; emit unavailable when trade direction cannot be determined. |
| `2607.02830v1` | backtest_evaluation | Outcome-Classified Precision Auditing of Filter Rules in Algorithmic DEX Trading: Evidence from 2,400 Rejection Events | Log every candidate the engine's gates reject, with the rejection reason, then sample forward prices for those names over a fixed window and classify each rejection conservatively as saved, flat or missed; report a per-filter save-to-miss ratio and refuse the wider interpretive tiers unless a matched-comparison test supports them. |
| `2607.06373v1` | regime_engine | Error Propagation in Spectral Functionals of Shrinkage Covariance Estimators: Perturbation Bounds and Calibrated Inference | regime_engine already reads cross-sectional concentration; it would compute the projector movement between consecutive rolling covariance windows and the absorption ratio, then compare against the paper's first-order null band (with the debiased estimator under shrinkage) so structural change is only declared when the move exceeds noise; feeds regime_score. |
| `2607.06690v1` | coverage_measurement | tsbootstrap: Distribution-Free Uncertainty Quantification and Conformal Prediction for Time Series | The coverage scorecard would replace IID intervals with the library's block or sieve bootstrap and adaptive conformal calibrators when quoting uncertainty for any claim statistic (hit rate, score-vs-outcome correlation) over the historical report panel, letting diagnose() pick the block length from lag-1 autocorrelation and ADF; one producer of intervals in the measurement layer. |
| `2607.12248v2` | backtest_evaluation | When Directional Accuracy Lies: A Base-Rate-Honest Benchmark for LoRA-Adapted TimesFM on Equity Forecasting | The score panel would report excess accuracy (model minus always-up on identical windows) for any directional claim, computed with walk-forward folds, a held-out-ticker split, block-bootstrap intervals and paired McNemar or Diebold-Mariano tests under FDR control; owned by backtest_evaluation and quoted by the verifier whenever a report claims directional edge. |
| `2607.14174v1` | statement_parsing | How Much of a 10-K Matters? Aggregation-Dependent Value of Full-Text versus Risk-Factor Sentiment | statement_parsing, which already pulls Item 1A from EDGAR, would score each filing with a supervised lexicon trained against volatility labels and store a per-filing sentiment score plus its volatility-targeted variant, scoring Item 1A alone for firm-level use; the sentiment and fundamentals analysts read it as context. |
| `2607.19453v1` | backtest_evaluation | Predictive Extrema, Unprofitable Policies: An AI-Assisted Audit of Candle-Based Binance Spot Timing Models | backtest_evaluation would add the audit's protocol to the harness: purge and embargo at split boundaries, never same-close entry, a per-cycle cost applied to every policy number, and a triple report of ranking skill, average precision and realized net policy return, so prediction is never reported as edge. |
| `2607.19497v1` | technical_factors | The Science and Practice of Trend-Following Systems | technical_factors would compute the Poisson-kernel-weighted excess spectral mass of each symbol's volatility-normalized returns (the condition under which trend alpha exists at zero drift), the cost-optimal lookback span given the engine's cost estimate, and an attribution of the swing factor's realized P&L to autocorrelation, drift and skew; feeds technical_score. |
| `2607.20093v1` | verification | Retail Trader's Ruin: An Anatomy of Popular Signal Failure | The verifier and findings ledger would adopt the three-gate verdict (SUPPORTED, REFUTED, INCONCLUSIVE) with a predeclared materiality threshold, hierarchical Benjamini-Yekutieli control across the engine's candidate signals, and an equivalence test, so a non-significant result is recorded as unresolved rather than as evidence of no edge. |
| `2607.24410v1` | risk_engine | The Fundamental Structure of Risk: From Characteristics to Covariance | risk_engine would push each name's point-in-time characteristics (size, valuation, leverage, sector) through the trained encoder to obtain factor exposures and a forward covariance, using it for sleeve risk and for names with too little return history to estimate covariance from returns; feeds risk_score and portfolio_construction. |
| `2607.27461v1` | cross_section | Are Three Matrices All You Need To Beat the Market? Observable Matrix Dynamics for Portfolio Optimization | cross_section builds, from about a year of daily returns, each name's 10-decile volatility-rank and return-rank transition matrices (pooled and covariate-conditioned on size, beta, illiquidity and momentum) and emits one-step-ahead forward-rank forecasts: the volatility rank is forecastable with multi-step memory, the return rank is not. The market-mode-removed arccos distance matrix feeds portfolio_construction as a long-sleeve diversification penalty. |
| `2608.00127v1` | risk_engine | Drawdown Risk Beyond Brownian Motion: A Monte-Carlo Framework, Non-Gaussian Extensions, and Long Memory | risk_engine maps an estimated Sharpe, plus skew, kurtosis and Hurst from the strategy's own P&L, to median and 90th-percentile envelopes for maximum drawdown, maximum loss, time under water and longest recovery, and flags a live or backtested drawdown past the one-in-ten line as the evidence-based trigger to revise the Sharpe or cut. The fBm result makes backtest_evaluation rescale by T^(H-1/2), not root-time. |
| `2608.07479v2` | coverage_measurement | Marginally Useful: An Information-Gap Identity in Conformal Prediction | coverage_measurement extends the shipped conformal band with the paper's second axis: alongside realized coverage, compute the pooled-residual information gap - the log-score of the pooled band against a conditional-scale GARCH/EWMA alternative on the same calibration window - which equals I(R;X) and bounds what recalibration cannot repair. Reported per band, and 'unavailable' below the min_n floor. |
| `2608.14014v1` | news_engine | Buy the Rumor, Sell the News: When Is News Priced In? | news_engine would tag each article with an event type plus rumor/quantified/scheduled attributes, cluster repeat coverage into stories so first reports are separable from follow-ups, and emit a tag-conditional drift prior and a width term: volatility rises before publication and decays after, while the directional move is already spent by the closing bell. |
| `2608.14859v1` | risk_engine | Disclosed Human-Capital Disruption and Firm-Specific Risk | Classify each transcript excerpt for material workforce disruption, normalize by transcript length, and feed the firm score to risk_engine as a firm-specific risk state: one standard deviation maps to roughly 0.5pp higher idiosyncratic volatility and downside deviation and a lower worst monthly return over the following 42 trading days, with no market-beta relation. |
| `2608.26115v1` | risk_engine | Option-Implied Signals and Crash Risk: Predictability and Machine-Learning Evidence from U.S. Equity Options | risk_engine would take option-implied features computed per symbol by options_gamma - IV spread, risk-neutral skewness, smirk, term slope, open-interest-weighted vega and contract counts - and produce a regime-conditional five-day crash probability plus a next-month cross-sectional rank, reporting unavailable when the symbol's chain is missing. |
| `2608.27734v1` | backtest_evaluation | What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery | backtest_evaluation would route every candidate the engine's search produces through one recorded evaluation entry point, deflate each reported Sharpe against the ledger's own trial count and Sharpe dispersion, and run CSCV overfitting probability plus stationary-bootstrap intervals, making look-ahead unexpressible rather than merely discouraged, and showing why a leaky oracle at Sharpe 35 survives deflation. |
| `2609.00731v1` | backtest_evaluation | Agentic Empirical Asset Pricing: Methodological Foundations | The measurement layer re-runs the analyst/researcher/PM pipeline at a sequence of historical decision dates under point-in-time constraints and scores each cycle on productivity, performance and novelty at once, distinguishing a process that adapts from one that got lucky once. |

---

## 8. Appendix B - every paper, by verdict

All 309, newest verifier pass. `theme` is the engine surface the paper was routed to, or
`unmapped` where it was judged to map nowhere. `low` and `none` are recorded deliberately: a
corpus survey that lists only what it liked is a wish list, not a survey.

### High (31)

| id | surface | title | what |
|---|---|---|---|
| `2601.06499v2` | technical_factors | Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO | Tests whether short-horizon trading signals built for Chinese retail markets carry non-redundant cross-sectional premia in S&P 500 names once established fundamental factors are controlled. |
| `2602.00196v1` | technical_factors | Generative AI for Stock Selection | Whether LLMs with retrieval-augmented and programmatic prompting can auto-discover economically motivated features for short-horizon US equity return prediction. |
| `2602.06198v1` | fundamental_engine | Insider Purchase Signals in Microcap Equities: Gradient Boosting Detection of Abnormal Returns | Whether SEC Form 4 insider open-market purchases predict abnormal returns in US microcap stocks. |
| `2602.07066v1` | regime_engine | Algorithmic Monitoring: Measuring Market Stress with Machine Learning | A one-month-ahead probability that the US equity market enters a high-stress regime, built from the cross-section of stock fragility signals. |
| `2602.07841v3` | backtest_evaluation | A Nontrivial Upper Bound on the Out-of-Sample R^2 in Return Forecasting | Derives a tractable upper bound on the out-of-sample R^2 of any return forecast as a quadratic function of its realized directional accuracy. |
| `2603.23300v2` | portfolio_construction | Designing Agentic AI-Based Screening for Portfolio Investment | An agentic pipeline where LLM fundamental and news screeners deliberate to select stocks, then precision-matrix estimation sets weights. |
| `2604.08765v3` | risk_engine | Reliability-Aware ETF Tail-Risk Monitoring | A next-day ETF lower-tail (5% VaR) estimate shipped together with an input-quality and prediction-uncertainty score that widens the estimate or flags it as untrustworthy. |
| `2604.15531v1` | backtest_evaluation | Spurious Predictability in Financial Machine Learning | Whether a complete prediction-to-position workflow is falsified by producing statistically significant walk-forward evidence in null or placebo data environments. |
| `2604.17327v1` | measurement_provenance | Signal or Noise in Multi-Agent LLM-based Stock Recommendations? | Whether a deployed four-analyst LLM system's strong-buy picks beat matched random portfolios, and which agent drives each thesis. |
| `2604.19476v2` | peer_universe | Cross-Stock Predictability via LLM-Augmented Semantic Networks | A peer graph whose edges are LLM-classified economic relations, used to aggregate pair-level mean reversion into stock-level signals. |
| `2605.30363v2` | regime_engine | Enhancing Regime Shift Detection Using Unstructured Data: A Study on the Treasury Market | Detects the timestamps of market regime shifts by cross-validating LLM-proposed candidates from policy text against a likelihood-ratio VAR test on a price/macro panel. |
| `2606.03457v1` | news_engine | Hybrid News Sentiment Engine: Real-Time Market Analysis via Adaptive Ensemble Learning on News-Price Pairs | Produces a news-sentiment score by TF-IDF semantic clustering of headlines that tracks each cluster's realized price reaction and auto-calibrates ensemble weights. |
| `2606.22719v1` | backtest_evaluation | Leakage-Aware Benchmarking of LLM Forecasting: Real-Time Nowcasts as the Decision-Time Input for Macro Factor Ranking | Whether a retrieval-augmented LLM can rank US equity style factors when restricted to information actually observable at the decision date, and how much of any signal survives against non-LLM baselines. |
| `2607.01377v1` | cross_section | Liquidity Premium and Investment Horizons | Whether Kyle's price-impact coefficient, estimated directly from daily equity order flow, forecasts the cross-section of subsequent stock returns. |
| `2607.02830v1` | backtest_evaluation | Outcome-Classified Precision Auditing of Filter Rules in Algorithmic DEX Trading: Evidence from 2,400 Rejection Events | Whether a production filter stack's rejections actually saved capital rather than missing winners, measured against post-rejection forward outcomes. |
| `2607.06373v1` | regime_engine | Error Propagation in Spectral Functionals of Shrinkage Covariance Estimators: Perturbation Bounds and Calibrated Inference | Whether movement in a covariance estimator's leading eigenspace (projector distance) or in scalar spectral functionals (absorption ratio, leading-eigenvalue share) is real structural change or estimation noise, with a calibrated null law and tests. |
| `2607.06690v1` | coverage_measurement | tsbootstrap: Distribution-Free Uncertainty Quantification and Conformal Prediction for Time Series | An MIT-licensed library exposing block, residual, sieve and wild bootstrap, classical bootstrap confidence intervals, and adaptive conformal calibrators (EnbPI, ACI, NexCP, AgACI) behind one typed spec-selected API. |
| `2607.12248v2` | backtest_evaluation | When Directional Accuracy Lies: A Base-Rate-Honest Benchmark for LoRA-Adapted TimesFM on Equity Forecasting | Whether a fine-tuned time-series foundation model has any directional skill once the always-up base rate is subtracted, measured as excess accuracy under walk-forward folds and a held-out-ticker split. |
| `2607.14174v1` | statement_parsing | How Much of a 10-K Matters? Aggregation-Dependent Value of Full-Text versus Risk-Factor Sentiment | Whether sentiment trained on the whole 10-K or on its Item 1A risk-factor section predicts firm return and volatility better, evaluated at sector, portfolio and single-firm aggregation. |
| `2607.19453v1` | backtest_evaluation | Predictive Extrema, Unprofitable Policies: An AI-Assisted Audit of Candle-Based Binance Spot Timing Models | Whether high event-ranking skill on candle-based models converts into net-of-cost policy return, answered negatively under a provenance-aware evidence audit. |
| `2607.19497v1` | technical_factors | The Science and Practice of Trend-Following Systems | The exact relation between P&L, autocorrelation and drift in volatility-normalized returns, with trend-following alpha expressed as excess low-frequency spectral mass and closed-form Sharpe, skewness and cost-optimal filter span. |
| `2607.20093v1` | verification | Retail Trader's Ruin: An Anatomy of Popular Signal Failure | Whether five retail signal families (trend, oscillator, candlestick, volume, calendar) clear a joint bar of statistical edge after multiplicity correction, economic viability after costs, and finite-bankroll survival under leverage. |
| `2607.24410v1` | risk_engine | The Fundamental Structure of Risk: From Characteristics to Covariance | A forward covariance estimator for the equity cross-section learned from observable firm characteristics alone, with interpretable factor exposures and zero-shot embedding of unseen assets. |
| `2607.27461v1` | cross_section | Are Three Matrices All You Need To Beat the Market? Observable Matrix Dynamics for Portfolio Optimization | Whether three price-history matrices - an arccos correlation-distance matrix and two decile Markov chains ranked by trailing return and trailing volatility - suffice to build a market-beating portfolio. |
| `2608.00127v1` | risk_engine | Drawdown Risk Beyond Brownian Motion: A Monte-Carlo Framework, Non-Gaussian Extensions, and Long Memory | How deep and how long the drawdowns of a systematic strategy should run, given its Sharpe ratio and return structure. |
| `2608.07479v2` | coverage_measurement | Marginally Useful: An Information-Gap Identity in Conformal Prediction | What a split-conformal residual-pooling band costs in log-score terms relative to the conditional distribution it claims to summarise. |
| `2608.14014v1` | news_engine | Buy the Rumor, Sell the News: When Is News Priced In? | When in event time the price move attached to a news event occurs, and how much drift remains after publication by event tag. |
| `2608.14859v1` | risk_engine | Disclosed Human-Capital Disruption and Firm-Specific Risk | A firm-level score of disclosed human-capital disruption from earnings calls and its relation to subsequent firm-specific risk. |
| `2608.26115v1` | risk_engine | Option-Implied Signals and Crash Risk: Predictability and Machine-Learning Evidence from U.S. Equity Options | Which option-implied signals still predict next-month returns and five-day crash risk once the sample is split by market regime. |
| `2608.27734v1` | backtest_evaluation | What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery | What remains of LLM-discovered strategy performance once look-ahead is structurally inexpressible and every trial the agent runs is recorded and deflated. |
| `2609.00731v1` | backtest_evaluation | Agentic Empirical Asset Pricing: Methodological Foundations | An evaluation standard and out-of-sample protocol for LLM-agent factor/trading discovery systems, scoring the discovery process (rolling re-execution) rather than one static output. |

### Medium (111)

| id | surface | title | what |
|---|---|---|---|
| `2601.06088v1` | backtest_evaluation | PriceSeer: Evaluating Large Language Models in Real-Time Stock Prediction | A live, contamination-controlled benchmark that scores LLM next-close forecasts by sector and horizon and tests susceptibility to fabricated news. |
| `2601.07588v1` | statement_parsing | Temporal-Aligned Meta-Learning for Risk Management: A Stacking Approach for Multi-Source Credit Scoring | Aligns statement reference dates with evaluation dates so annual-statement models are not scored using data that was published months later. |
| `2601.07687v4` | portfolio_construction | Physics-Informed Singular-Value Learning for Cross-Covariances Forecasting in Financial Markets | Cleans a rectangular two-block cross-covariance matrix under drifting dependence, improving out-of-sample block prediction and portfolio replication. |
| `2601.08571v1` | regime_engine | Regime Discovery and Intra-Regime Return Dynamics in Global Equity Markets | Labels Normal, High and Extreme regimes from EMD-based Hilbert instantaneous energy and estimates return-state transition probabilities inside each regime. |
| `2601.10732v1` | regime_engine | Regime-Dependent Predictive Structure Between Equity Factors: Evidence from Granger Causality | Tests whether factor-to-factor predictability, specifically HML leading SMB, exists only inside crisis regimes identified by a fat-tailed hidden Markov model. |
| `2601.11201v1` | volatility_models | Fast Times, Slow Times: Timescale Separation in Financial Timeseries Data | Separates slow and fast components of an asset panel and estimates each component's relaxation timescale from variance and tail stationarity criteria. |
| `2601.14062v1` | technical_factors | Demystifying the trend of the healthcare index: Is historical price a key driver? | Predicts whether the next session's open index exceeds the current day's level for healthcare sector indices from same-day OHLC shape features. |
| `2601.21447v1` | regime_engine | Trade uncertainty impact on stock-bond correlations: Insights from conditional correlation models | Time-varying US stock-bond conditional correlation and how Trade Policy Uncertainty and the presidential cycle drive it. |
| `2601.23172v2` | volatility_models | A unified theory of order flow, market impact, and volatility | A single core-flow persistence statistic H0 that pins down signed-flow memory, rough volume and volatility, and the power-law market-impact exponent. |
| `2602.00080v1` | backtest_evaluation | The GT-Score: A Robust Objective Function for Reducing Overfitting in Data-Driven Trading Strategies | A composite objective that embeds significance, consistency and downside risk to reduce data-snooping overfitting in strategy optimization. |
| `2602.00133v1` | backtest_evaluation | PredictionMarketBench: A SWE-bench-Style Framework for Backtesting Trading Agents on Prediction Markets | An execution-realistic, event-driven replay benchmark that scores trading agents with maker/taker fees and settlement losses. |
| `2602.00383v2` | regime_engine | Null-Validated Topological Signatures of Financial Market Dynamics | Whether the topological complexity of an index's return embedding (persistence-landscape norm) carries information beyond volatility. |
| `2602.07020v1` | peer_universe | Financial Bond Similarity Search Using Representation Learning | Whether learned embeddings of categorical bond attributes (sector, domicile) beat one-hot for similarity search and spread-curve estimation. |
| `2602.07046v5` | backtest_evaluation | Do Cryptocurrency Markets Differentiate Infrastructure from Regulatory Shocks? A Multi-Moment Event Study with Dependence-Robust Inference | A dependence-robust inference ladder for cross-asset event-study contrasts, demonstrated by correcting an earlier significance claim. |
| `2602.07048v2` | cross_section | LLM as a Risk Manager: LLM Semantic Filtering for Lead-Lag Trading in Prediction Markets | Whether an LLM semantic filter over Granger-causality lead-lag screens improves PnL by rejecting mechanically implausible directions. |
| `2602.07085v3` | cross_section | QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining | An LLM evolutionary framework that mines alpha factors via trajectory-level mutation/crossover with semantic-consistency and crowding gates. |
| `2602.07096v2` | verification | RealFin: How Well Do LLMs Reason About Finance When Users Leave Things Unsaid? | A bilingual benchmark testing whether finance LLMs recognize missing premises and withhold unjustified answers. |
| `2602.11020v2` | backtest_evaluation | When Fusion Helps and When It Breaks: View-Aligned Robustness in Same-Source Financial Imaging | Tests whether multi-view (chart plus indicator-matrix) fusion improves next-day direction prediction and how gracefully it degrades under adversarial perturbation. |
| `2602.19732v1` | dataflows_vendor | VOLatility Archive for Realized Estimates (VOLARE) | Provides an open archive of standardized realized volatility and covariance measures computed from ultra-high-frequency data. |
| `2603.05260v2` | risk_engine | Extreme Value Analysis for Finite, Multivariate and Correlated Systems with Finance as an Example | Estimates extremal tail behaviour of a finite correlated return panel by rotating returns into the correlation-matrix eigenbasis. |
| `2603.10202v2` | regime_engine | Hybrid Hidden Markov Model for Modeling Equity Excess Growth Rate Dynamics: A Discrete-State Approach with Jump-Diffusion | Generates synthetic equity return series that simultaneously reproduce heavy tails, near-zero autocorrelation and volatility clustering. |
| `2603.11408v2` | sentiment_engine | Beyond Polarity: Multi-Dimensional LLM Sentiment Signals for WTI Crude Oil Futures Return Prediction | Tests whether LLM-extracted multi-dimensional news sentiment (relevance, polarity, intensity, uncertainty, forwardness) predicts weekly WTI futures returns. |
| `2603.12040v1` | regime_engine | Entropic signatures of market response under concentrated policy communication | Measures Shannon entropy of index returns jointly with dispersion, plus a sliding cumulative entropy, to localize policy-driven turbulence. |
| `2603.13632v1` | position_sizing | Betting Around the Clock: Time Change and Long Term Model Risk | Shows the Kelly rule overbets when log-returns follow a time-changed (stochastic-clock) semimartingale rather than a lognormal. |
| `2603.16886v1` | backtest_evaluation | A Controlled Comparison of Deep Learning Architectures for Multi-Horizon Financial Forecasting: Evidence from 918 Experiments | Ranks nine deep architectures on multi-horizon financial forecasting under a controlled protocol and tests whether any has directional skill. |
| `2603.17463v2` | risk_engine | Multivariate GARCH and portfolio variance prediction: A forecast reconciliation perspective | Reconciles univariate GARCH portfolio-variance forecasts with MGARCH covariance forecasts to improve predicted portfolio risk. |
| `2603.19136v2` | regime_engine | Adaptive Regime-Aware Stock Price Prediction Using Autoencoder-Gated Dual Node Transformers with Reinforcement Learning Control | An unsupervised regime/anomaly score derived from autoencoder reconstruction error on price windows that gates dual prediction pathways. |
| `2603.19286v1` | news_engine | Generalized Stock Price Prediction for Multiple Stocks Combined with News Fusion | A multi-stock price predictor that filters daily news by stock-name-embedding attention before fusing text with prices. |
| `2603.19380v1` | backtest_evaluation | Survivorship Bias in Emerging Market Small-Cap Indices: Evidence from India's NIFTY Smallcap 250 | Quantifies how survivor-only backtests overstate returns and Sharpe by reconstructing historical index membership. |
| `2603.19944v2` | verification | Large Language Models and Stock Investing: Is the Human Factor Required? | Tests whether LLMs produce reliable stock recommendations and whether prompting or regulatory-filing grounding improves them. |
| `2603.20237v2` | dataflows_vendor | Temporal Coverage Bias in Financial Panel Data: A Coverage-Aware Structuring Framework with Evidence from the Dhaka Stock Exchange | Formalizes temporal coverage bias where calendar-aligned panels fabricate pre-listing price history, and proposes an availability-matrix correction. |
| `2603.20965v2` | news_engine | Learning to Aggregate Zero-Shot LLM Agents for Corporate Disclosure Classification | A trained logistic meta-classifier aggregates three zero-shot LLM sentiment judgments on disclosures to predict next-day return direction. |
| `2603.21672v3` | regime_engine | Mislearning of Factor Risk Premia under Structural Breaks: A Misspecified Bayesian Learning Framework | A predictive-likelihood-ratio measure of investor mislearning of factor risk premia under structural breaks. |
| `2603.24215v3` | fundamental_engine | Adapting Altman's bankruptcy prediction model to the compositional data methodology | Adapts Altman's bankruptcy model to compositional log-ratios of balance-sheet components. |
| `2604.02549v1` | regime_engine | Financial Anomaly Detection for the Canadian Market | Detects market-stress events from rolling correlation-graph anomalies using topological and graph-neural methods. |
| `2604.03499v3` | risk_engine | Marking-Aware Sequential VaR Recalibration for Standardized Option Books | A marking-aware sequential recalibration of option-book VaR targeting normalized next-day book loss. |
| `2604.06116v2` | verification | Sequential Audit Sampling for Finite Populations with Exact and Simulation-based Guarantee | Stopping boundaries that tell an auditor when to stop inspecting items of a finite population and conclude that the deviation rate is inside or outside tolerance. |
| `2604.10402v4` | volatility_models | Risk-Sensitive Specialist Routing for Volatility Forecasting | A single next-day ETF realized-variance forecast assembled by routing among competing volatility models according to the current market state. |
| `2604.14619v1` | news_engine | The Acoustic Camouflage Phenomenon: Re-evaluating Speech Features for Financial Risk Prediction | Whether speech acoustics add anything over text for flagging bottom-15% five-day return events around earnings calls. |
| `2604.19107v1` | regime_engine | Structural Dynamics of G5 Stock Markets During Exogenous Shocks: A Random Matrix Theory-Based Complexity Gap Approach | A scalar measuring how far the market's dominant eigen-mode sits above its average pairwise correlation, and how that gap relates to future basket volatility. |
| `2604.19580v1` | backtest_evaluation | Probabilistic Forecasting for Day-ahead Electricity Prices, Battery Trading Strategies and the Economic Evaluation of Predictive Accuracy | Whether ranking probabilistic forecasts by the profit of a downstream trading strategy is a proper, discriminating evaluation criterion. |
| `2604.26063v1` | technical_factors | A Volume-Price-Adjusted MACD Trading Strategy with Sensitivity Calibration for U.S. Equity Indices | A volume-, volatility- and intraday-structure-adjusted MACD whose crossover threshold is relaxed by a sensitivity parameter to enter earlier. |
| `2604.26811v2` | sentiment_engine | Do News and Social Media Tell the Same Story? Constructing and Comparing Sentiment Spillover Networks | Directed networks quantifying how much news versus social-media sentiment flows from one tech company to another. |
| `2605.00196v1` | volatility_models | Modeling Stock Returns and Volatility Using Bivariate Gamma Generalized Laplace Law | A joint distribution for returns and an observed volatility proxy with closed-form regression-based estimators. |
| `2605.04004v3` | backtest_evaluation | Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study | Whether fourteen OHLCV intraday momentum signal families carry any net-of-cost edge, answered by a five-criterion simultaneous gate. |
| `2605.05211v1` | backtest_evaluation | A Review of Large Language Models for Stock Price Forecasting from a Hedge-Fund Perspective | The question of which evaluation and leakage pitfalls the LLM stock-forecasting literature understates, and what practice it should follow. |
| `2605.11423v3` | regime_engine | A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday Data | A per-session flag for structurally extreme days, fired when three pre-market conditions are simultaneously elevated. |
| `2605.12099v1` | volatility_models | Bayesian Dynamic Modeling of Realized Volatility in Financial Asset Price Forecasting | A joint price and realized-volatility Bayesian filter that carries lagged and contemporaneous realized volatility into price forecasts. |
| `2605.12977v1` | risk_engine | Enhancing a Risk Model by Adding Transient Statistical Factors | An MLE extension that refines a supplied factor risk model and adds transient statistical factors, tolerating missing returns. |
| `2605.14976v3` | regime_engine | Multi-regime Markov-switching models with time-varying transition probabilities: An application to U.S. Treasury yields | Whether K-regime Markov-switching with time-varying transition probabilities is identifiable and improves fit on yield changes. |
| `2605.17117v2` | regime_engine | Geometric Observables for Financial Regime Detection | Four unsupervised geometric observables (Berry Phase Rate, spectral entropy, reduced purity, Hamiltonian sensitivity) used as regime-shift detectors. |
| `2605.23978v1` | backtest_evaluation | Algometrics: Forecasting Under Algorithmic Feedback | Whether deployment risk is identifiable from passive historical data once forecasts are converted into trades that change the data being forecast. |
| `2605.24285v1` | volatility_models | Memory, Roughness, and Information Persistence in Financial Markets: A Structural Approach to Volatility Forecasting | Whether rolling persistence (long-memory) features add out-of-sample volatility forecast power beyond HAR and HAR-X. |
| `2605.29413v1` | portfolio_construction | From Classical Optimization to Bayesian Integration: A Comprehensive Analysis of Systematic Portfolio Management | Compares whether constraints, factor models, Monte Carlo simulation and Black-Litterman views change the concentration, performance and stability of mean-variance portfolios. |
| `2606.00061v1` | analyst_prompt | Reflexivity as Prompt: Does Awareness of Self-Reinforcing Market Dynamics Improve LLMs as Financial Market Forecasters? | Measures whether prompting frontier LLMs with Soros reflexivity/boom-bust awareness improves their directional forecasts. |
| `2606.02657v1` | backtest_evaluation | Regime-Arrival Uncertainty in Generalization Bounds under Distribution Shift | Quantifies the extra deployment risk caused by mismatch between training and deployment regime composition under Markov-switching shifts. |
| `2606.03184v1` | backtest_evaluation | FinStressTS: A Parametric Synthetic Benchmark for Time-Series Forecasting in Finance | Provides a synthetic mechanism-aware benchmark (30 environments, 6 mechanism families) that attributes forecasting failures to specific structural causes. |
| `2606.04153v1` | technical_engine | A new decomposition approach to modeling financial returns: Conditioning sign on magnitude | Forecasts expected returns by combining a magnitude model with a sign model conditioned on contemporaneous magnitude. |
| `2606.06190v1` | volatility_models | Multi-Scale Markov Switching GARCH | Detects volatility regimes on three timescales and combines them into a 27-state cross-scale probability tensor. |
| `2606.06823v1` | analyst_prompt | PandaAI: A Practical Agent CQ2 for Neuro-symbolic Data Analysis And Integrated Decision-Making in Quantitative Finance | Builds a closed-loop neuro-symbolic LLM agent that mines constrained alpha factors and conditions decisions on a latent market-regime state. |
| `2606.08228v1` | verification | Post-Rejection Follow-up Sampling: A Methodology for Counterfactual Outcome Measurement in Algorithmic DEX Trading | Measures the forward outcomes of rejected trading candidates to audit filter precision against actual, not simulated, market behavior. |
| `2606.08791v1` | backtest_evaluation | Evaluating AI Investment Strategies | Decomposes the cumulative regret of a dynamic policy into the sum of per-period covariances between cost and decision. |
| `2606.09274v1` | risk_engine | Reverse Stress Testing for Multivariate Scenarios: A Conditional Framework for Stressed Time Series | Reconstructs a coherent multivariate stress scenario from a single prescribed shock by maximizing the conditional density given that shock. |
| `2606.11859v2` | risk_engine | Scenario Generation for Time Series and Curves: A Comparison of Nonparametric and Semiparametric Bootstrap | Compares stationary-bootstrap and semiparametric simulation of realistic asset-class paths and yield curves. |
| `2606.16840v1` | risk_engine | Crashing Together, Rallying Apart: Dynamic Conditional Tail Dependence in Cryptocurrency Markets | The conditional extremal dependence graph among a cross-section of assets, estimated separately for joint crashes and joint rallies. |
| `2606.20145v1` | volatility_models | Trends, Volatility, Correlations, and Critical Phenomena in Financial Markets | Next-day variance and next-day pairwise correlation forecasts expressed as second-order polynomials of today's trend strength alongside today's variance and correlation. |
| `2606.23492v1` | volatility_models | Continuous Hidden Markov Models for Equity Returns: Heavy-Tail Emission Families and Regime-Conditional Value-at-Risk | A continuous-emission hidden Markov model of daily equity returns with heavy-tailed per-regime densities, and the regime-conditional Value-at-Risk built from it. |
| `2606.30037v1` | backtest_evaluation | Heads, Not Backbones: Output Heads Dominate Architectures on Fat-Tailed Returns | Whether the output head (point, Gaussian, Gaussian mixture) or the backbone architecture dominates forecast skill on fat-tailed returns. |
| `2606.31251v1` | coverage_measurement | Regime-Conditional Distributional Comparison of Trading Strategies: A GAMLSS/ZAGA Framework Applied to the S&P 500 | How a strategy's performance distribution differs from its benchmark's as a function of market regime, rather than as one backtest-wide number. |
| `2607.00475v1` | portfolio_construction | End-to-End Parametric Portfolio Policies for Cross-Asset Futures Timing: When Do AI Models Beat Simple Rules? | When an end-to-end AI policy mapping market states directly to portfolio weights beats simple rules such as equal weighting, risk parity and time-series momentum. |
| `2607.01765v3` | backtest_evaluation | A Cap-Axis Integral Diagnostic of Factor Models | Where inside the market, along the capitalization axis, a factor model leaves pricing errors, summarized as a bridge-alpha curve. |
| `2607.02823v4` | measurement_provenance | Auditing Collector-Generated Graduation Labels on Pump.fun: Measurement Error and Temporal Non-Generalization | Whether a data collector's terminal labels mean the platform-side event, and whether a model fitted on them generalises to a later cohort. |
| `2607.03082v1` | portfolio_construction | Portfolio Optimization and Tail-Risk Analytics of Actively Managed ETFs | How buy-and-hold, mean-variance, CVaR and tangency portfolios of actively managed ETFs differ in risk-adjusted performance and tail exposure. |
| `2607.03858v1` | risk_engine | A Spectral Generalisation of the Variance Ratio: Eigenstructure of Long-Horizon Portfolio Covariance and a Multi-Memory Factor Model of U.S. Equity Returns | How the cross-sectional covariance of returns reorganises across holding horizons, splitting return-channel from volatility-channel memory. |
| `2607.03888v2` | risk_engine | Local Gaussian Correlation in the Tails: A Scarcity Diagnostic, an Optimal Local Bandwidth, and the Limits of Adaptivity | How much of a tail-dependence estimate is limited by local sample scarcity rather than by bandwidth choice. |
| `2607.05091v6` | backtest_evaluation | Overshooting the Coordinate: Where Factor Corrections Land on Characteristic Axes | Traces model alphas as a bridge-alpha curve across the full order induced by a prespecified characteristic (value, profitability, investment, momentum, or market cap), localizing where a factor model underprices, flattens, or overshoots zero. |
| `2607.05291v1` | volatility_models | Forecasting Realized Volatility with Time Series Foundation Models: A Comparison with Econometric Benchmarks | Whether nine zero-shot time-series foundation models beat eight econometric specifications including the HAR family for realized-volatility forecasting across 50 assets and three horizons. |
| `2607.06220v1` | news_engine | Stable Sentiment and Persistent Dynamics in U.S. Economic News over 45 Years | Whether the temporal memory of US economic news sentiment changed over 45 years: persistence, residence times in optimistic/pessimistic states, reversal rate, volatility and bimodality. |
| `2607.06908v1` | market_breadth | Iterative detection of global factors near the BBP phase transition | The number of global factors in a high-dimensional correlation matrix, via iterative Marchenko-Pastur edge recalibration combined with a participation-ratio eigenvector delocalization filter. |
| `2607.08500v2` | options_gamma | Estimating the Stochastic Discount Factor from Option Prices and Predicting the Equity Premium | A volatility-scaled stochastic discount factor recovered solely from S&P 500 option prices, and the forward-looking equity premium it implies. |
| `2607.10297v1` | cross_section | Recovering Structural Organization in Noisy Correlation Networks Using Financial Systems as a Testbed | A structure/noise split of the return correlation matrix by Marchenko-Pastur bounds, the resulting stable core-periphery network, and a portfolio built from its peripheral assets. |
| `2607.12407v1` | coverage_measurement | Statistical Properties and Power Analysis of Divergence Measures for Credit Risk Model Monitoring | Chi-square benchmark values and Type-I/power trade-offs for Jensen-Shannon and KL divergence versus PSI as distributional-shift detectors. |
| `2607.18813v1` | position_sizing | Mixing-Law Uncertainty in Multivariate Normal Mean-Variance Mixtures: Semi-parametric Estimation and Robust Cumulative-Prospect Decisions | The ambiguity set of mixing laws for a normal mean-variance mixture that the data cannot distinguish, and the distributionally robust exposure maximizing the worst-case cumulative-prospect value. |
| `2607.19005v2` | regime_engine | Observable Matrix Dynamics of Stocks | Trajectory observables of a fixed-size distance matrix: the effective dimension of arccos-correlation geometry, name-level sector rotation, and Markov chains on the daily return and volatility ranking spaces. |
| `2607.21826v1` | regime_engine | Are cryptocurrencies real financial bubbles? Evidence from quantitative analyses | Whether a price series is in a speculative bubble phase, flagged by log-periodic power-law fits and Phillips-Shi-Yu right-tailed unit-root tests. |
| `2607.27070v1` | backtest_evaluation | Where does the criticality live? Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades | Whether crypto perpetual liquidation cascades carry a reproducible critical-slowing-down fingerprint, and in which state variable, across seven cascades. |
| `2607.27188v1` | options_gamma | Inverse Learning of Latent Risk-Neutral Densities from Irregular Option Quotes | Whether accurate option prices imply accurate recovery of the latent risk-neutral density, and which estimator wins under sparse irregular quotes. |
| `2607.28230v2` | position_sizing | Boundary-Induced Apparent Risk Aversion in Nonergodic Multiplicative Growth | How a lower absorbing wealth threshold reshapes the growth-optimal fixed exposure. |
| `2608.00761v1` | backtest_evaluation | AI and Exchange Rate Predictability | Whether an LLM can score a currency's fundamental strength from economic data releases well enough to predict cross-sectional currency returns. |
| `2608.02311v2` | verification | AI Governance for Institutional Readiness in Finance | What governance architecture agentic AI in asset management needs, why static validation fails, and how policy drift is detected in production. |
| `2608.05373v1` | security_context | Velocity- and Regime-Aware Detection of Intraday Options Market Manipulation, with Explainable Attribution | Whether pump-and-crash manipulation is detectable from the velocity rather than the level of market state. |
| `2608.06618v1` | portfolio_construction | Beyond Co-Movement: Locality by Exposures Enables a Joint Factor-Graph Framework for Portfolio Diversification | Whether defining asset neighbourhoods by factor-exposure similarity, learned jointly with the graph, gives better-conditioned portfolios than correlation-based graphs. |
| `2608.09641v1` | market_breadth | Lower spectrum of financial correlation matrices: a new perspective on market synchronization | Whether the smallest eigenvalues of a financial correlation matrix carry information about market synchronization that the largest eigenvalues miss. |
| `2608.10693v1` | options_gamma | When the Fed Speaks: Dynamics and Forecasts of the Volatility Surface | Whether implied volatility rises before scheduled FOMC meetings, strongest for short-dated out-of-the-money options, and whether an ML model can forecast the surface better than a random walk. |
| `2608.10788v1` | regime_engine | The Triadic Stress Index in Financial Markets | Whether a four-factor network index built from closed triangles, density, modularity and degree variance registers systemic stress better than spectral benchmarks, and which asset carries the concentration. |
| `2608.11505v1` | backtest_evaluation | Does a Structural Model Add Anything to the Closing Price? Calibrated forecasting, incremental information, and match leverage in the Italian Serie A | Whether a structural forecast carries information a margin-free market price has not already absorbed, quantified as the fitted weight in a logarithmic opinion pool. |
| `2608.12251v1` | volatility_models | Regime-Gated Residual Mixture-of-Experts for Cross-Sectional Volatility Forecasting | Five-day forward realized volatility per stock when regime information enters only as a soft gate routing residual expert corrections instead of as a forecasting input. |
| `2608.12594v1` | peer_universe | What Makes a Peer? Valuation-Anchored Similarity in Private Markets | A company similarity metric learned from observed valuations, used to form economically meaningful peer sets rather than static feature or text-similarity neighbours. |
| `2608.20020v1` | regime_engine | The Reconfiguration Premium: Co-movement Structure as an Unspanned Dimension of the Variance Risk Premium | How fast the eigenbasis of the correlation matrix rotates between consecutive windows, and whether that rotation rate is priced. |
| `2608.23808v2` | backtest_evaluation | Equity Strategy Backtesting: Luck or Edge? The MinervaScore as a Statistical Robustness Grade | A post-selection robustness grade combining deflated Sharpe, overfitting probability, superior predictive ability, minimum track-record length and regime stability into one verdict. |
| `2608.24786v1` | position_sizing | Harvesting the Volatility Risk Premium: A Learning-to-Rank Approach | Which of a daily cross-section of candidate short-put strategies to hold, including the choice to hold nothing, under margin and fee constraints. |
| `2608.26128v1` | market_breadth | Analysis of the Principal Components of Correlation Matrices of S&P 500 Financial Data from an Econophysics Perspective | Market states and each stock's relative participation, read from the spectral structure of rolling S&P 500 correlation matrices. |
| `2608.29669v1` | peer_universe | Wasserstein-Barycentric Interaction Fields for Spatial Factor Models: Evidence from Language-Model Representations | A directed peer-interaction field built from firms' article-embedding distributions, and the exposure penalty that misalignment with peers implies. |
| `2608.29692v1` | risk_engine | Portfolio Risk Bounds without Cross-Asset Return Covariances: Distributional Fields from Language-Model Representations | A one-sided certificate (upper bound) on systematic portfolio variance, and the normalized allocation attaining it, computed from Wasserstein-2 dispersion of firms' news-embedding distributions instead of a cross-asset return covariance. |
| `2608.30446v1` | risk_engine | End-to-End Neural Shrinkage of Indefinite Pairwise Correlation Matrices for Small-Cap-Inclusive Portfolios | A positive-definite covariance estimate for ragged pairwise-complete return panels, trained end-to-end to minimize realized five-day global-minimum-variance risk. |
| `2609.04420v1` | regime_engine | Optimal Stratified Allocation for Rare-Event Onset Forecasting in Dependent Sequences | An optimal stratified-sampling allocation for class-weighted rare-event risk estimation, applied to forecasting when the Phillips-Shi-Yu explosive-regime detector begins firing. |
| `2609.06422v1` | volatility_models | Asymmetric Long-Memory GARCH: Sign-Dependent Kernel Injection in a Two-Dimensional Markov Chain | An asymmetric long-memory GARCH in which positive and negative innovations inject variance with different amplitudes and kernel ages, splitting level and memory channels. |
| `2609.07989v1` | volatility_models | Regimes in the Order Flow | Duration-aware and multivariate Bayesian online changepoint detection of regime breaks in signed order flow. |
| `2609.09405v1` | volatility_models | The Log S-fBM model: Statistical analysis | Statistical properties, deviation inequalities and a Hurst-exponent hypothesis test for the Log S-fBM model reconciling rough (H~0.1) and multifractal (H~0) volatility. |
| `2609.20224v1` | options_gamma | The Year-End Toll: Frictions Embedded in Option-Implied Rates | A 2-3 bp unannualized increase in the option funding basis when index-option maturity first crosses December 31. |
| `2609.20550v1` | measurement_provenance | Principal component error in high-dimensional factor models | Decomposes the error of sample-covariance principal directions into an estimable out-of-subspace term and a non-estimable in-subspace term, with almost-sure high-dimension limits. |

### Low (124)

| id | surface | title | what |
|---|---|---|---|
| `2601.00011v1` | none | Ultimate Forward Rate Prediction and its Application to Bond Yield Forecasting: A Machine Learning Perspective | Estimates the ultimate forward rate from Chinese treasury yields and macro variables and uses it to predict ultra-long bond yields. |
| `2601.00395v1` | none | Core-Periphery Dynamics in Market-Conditioned Financial Networks: A Conditional P-Threshold Mutual Information Approach | Describes how dependence networks among large caps in four QUAD markets reorganise across the COVID crash. |
| `2601.00810v1` | none | Can Large Language Models Improve Venture Capital Exit Timing After IPO? | Asks whether an LLM given only point-in-time post-IPO information picks better VC exit dates than investors actually did. |
| `2601.01216v2` | none | Order-Constrained Spectral Causality for Multivariate Time Series | Defines directional dependence between series as the sensitivity of second-order dependence operators to order-preserving time deformations of a source component. |
| `2601.01871v1` | none | On lead-lag estimation of non-synchronously observed point processes | Estimates the prevailing lead-lag time between two non-synchronously observed sequences of order arrival timestamps. |
| `2601.02677v1` | none | Uni-FinLLM: A Unified Multimodal Large Language Model with Modular Task Heads for Micro-Level Stock Prediction and Macro-Level Systemic Risk Assessment | A single fine-tuned multimodal LLM with task-specific heads jointly predicts stock direction, credit risk and systemic-risk early warnings. |
| `2601.04959v1` | none | Intraday Limit Order Price Change Transition Dynamics Across Market Capitalizations Through Markov Analysis | Estimates how consecutive limit-order price changes transition among nine states by market-cap tier and intraday interval. |
| `2601.08896v1` | none | XGBoost Forecasting of NEPSE Index Log Returns with Walk Forward Validation | Forecasts one-step-ahead daily log-returns and directional sign for the Nepal Stock Exchange index. |
| `2601.10517v2` | none | From rough to multifractal multidimensional volatility: A multidimensional Log S-fBM model | A multivariate stationary fractional Brownian motion model whose co-Hurst and co-intermittency matrices describe joint volatility scaling across assets. |
| `2601.11305v1` | none | Multiscaling in the Rough Bergomi Model: A Tale of Tails | Asks whether the multiscaling observed in the rough Bergomi model originates from rough volatility paths or from fat-tailed returns. |
| `2601.11601v1` | none | Latent Variable Phillips Curve | Tests whether medium-horizon inflation forecasts improve when the Phillips curve's slack measure is treated as a latent variable. |
| `2601.11602v2` | none | The Physics of Price Discovery: Deconvolving Information, Volatility, and the Critical Breakdown of Signal during Retail Herding | Measures the impulse response of price to foreign, institutional and retail order flow and how it breaks down during retail herding. |
| `2601.12990v1` | none | Beyond Visual Realism: Toward Reliable Financial Time Series Generation | Shows that generated return series can pass stylized-fact tests yet collapse in trading backtests, and fixes it by making stylized facts differentiable training constraints. |
| `2601.16274v2` | none | A Nonlinear Target-Factor Model with Attention Mechanism for Mixed-Frequency Data | Estimates factor models on panels whose series arrive at different frequencies by replacing fixed linear loadings with attention. |
| `2601.17773v1` | none | MarketGANs: Multivariate financial time-series data augmentation using generative adversarial networks | Generates joint high-dimensional asset returns with an explicit factor structure and uses the synthetic samples to estimate covariances. |
| `2601.19321v1` |  | Predictive Accuracy versus Interpretability in Energy Markets: A Copula-Enhanced TVP-SVAR Analysis | Whether copula-enhanced time-varying structural VARs can match machine learning in forecasting energy-macro dynamics while keeping causal interpretability. |
| `2601.21272v2` |  | Finite-Sample Properties of Model Specification Tests for Multivariate Dynamic Regression Models | A finite-sample-valid test of exogeneity/specification for multi-equation dynamic regressions, applied to Fama-French factor models. |
| `2601.22200v1` |  | Adaptive Benign Overfitting (ABO): Overparameterized RLS for Online Learning in Non-stationary Time-series | A numerically stable overparameterized recursive-least-squares learner for online forecasting under non-stationarity. |
| `2602.00037v2` |  | Bitcoin Price Prediction using Machine Learning and Combinatorial Fusion Analysis | Whether fusing many ML price models via Combinatorial Fusion Analysis yields more robust Bitcoin price forecasts. |
| `2602.00049v1` |  | Exploring the Interpretability of Forecasting Models for Energy Balancing Market | Accuracy-vs-interpretability trade-off for forecasting mFRR balancing-market activation price. |
| `2602.00073v1` |  | Test-Time Adaptation for Non-stationary Time Series: From Synthetic Regime Shifts to Financial Markets | Whether small-footprint test-time adaptation helps causal forecasting and direction classification under regime shifts. |
| `2602.00082v1` |  | Design and Empirical Study of a Large Language Model-Based Multi-Agent Investment System for Chinese Public REITs | An LLM multi-agent analysis-prediction-decision system for Chinese public REITs and whether a fine-tuned small model matches a large one. |
| `2602.00086v3` |  | Impact of LLMs news Sentiment Analysis on Stock Price Movement Prediction | Whether FinBERT/RoBERTa/DeBERTa news-sentiment features improve stock-movement prediction models. |
| `2602.00548v2` |  | The Impact of Trump-Era Tariffs on Financial Market Efficiency | How the COVID-19 shock and the 2025 Trump tariffs shifted market efficiency, measured by multifractal Hurst exponents. |
| `2602.00776v1` |  | Explainable Patterns in Cryptocurrency Microstructure | Whether engineered limit-order-book and trade features have stable predictive importance across crypto assets. |
| `2602.07018v4` |  | Does Crypto Sentiment Extremity Widen Estimated Spreads? Evidence Depends on the Specification | Whether extreme Crypto Fear & Greed values widen a daily Bitcoin high-low spread estimate. |
| `2602.07659v1` |  | Continuous Program Search | Whether learning a behavior-meaningful continuous program space improves mutation locality for genetic-programming trading-strategy search. |
| `2602.08182v1` |  | Nansde-net: A neural sde framework for generating time series with memory | Builds a Neural-SDE generator whose noise kernel is a neural-network ARMA-type process so long- and short-memory can be simulated inside Ito calculus. |
| `2602.17851v1` |  | Beyond the Numbers: Causal Effects of Financial Report Sentiment on Bank Profitability | Estimates causal effects of quarterly-report sentiment on bank profitability, with heterogeneity conditioned on leverage and asset composition. |
| `2602.18572v1` |  | Sub-City Real Estate Price Index Forecasting at Weekly Horizons Using Satellite Radar and News Sentiment | Forecasts sub-city weekly real-estate price indices by fusing transaction history, satellite radar and news tone. |
| `2602.19590v2` |  | Metaorder modelling and identification from public data | Tests whether Lillo-Mike-Farmer order-splitting can be recovered from anonymous public trade-and-quote data. |
| `2602.19841v1` |  | Detecting and Explaining Unlawful Insider Trading: A Shapley Value and Causal Forest Approach to Identifying Key Drivers and Causal Relationships | Classifies unlawful insider trades and ranks the features that drive the classification. |
| `2602.21869v3` |  | A Bayesian approach to out-of-sample network reconstruction | Predicts the next snapshot of a partially observed financial network and quantifies the uncertainty on each link. |
| `2603.02898v1` |  | Range-Based Volatility Estimators for Monitoring Market Stress: Evidence from Local Food Price Data | Applies OHLC range-based volatility estimators to local food prices as an early distress signal. |
| `2603.05119v1` |  | Asymptotic Separability of Diffusion and Jump Components in High-Frequency CIR and CKLS Models | Separates jump from diffusion increments in discretely observed CIR/CKLS processes using extremal behaviour of standardized residuals. |
| `2603.05917v3` |  | Stock Market Prediction Using Node Transformer Architecture Integrated with BERT Sentiment Analysis | Forecasts stock prices with a node transformer over a stock graph fused with BERT social-media sentiment. |
| `2603.10272v2` |  | An operator-level ARCH Model | Defines an ARCH model whose conditional object is a full covariance operator on a separable Hilbert space. |
| `2603.18107v1` |  | ARTEMIS: A Neuro Symbolic Framework for Economically Constrained Market Dynamics | A neuro-symbolic forecaster that enforces no-arbitrage through PDE and market-price-of-risk penalties while distilling symbolic trading rules. |
| `2603.20271v1` |  | Information Propagation Across Investor Types: Transfer Entropy Networks in the Korean Equity Market | Whether investor-type flow transfer-entropy networks carry exploitable cross-stock information. |
| `2603.20456v1` |  | Neural Hidden Markov Model with Adaptive Granularity Attention for High-Frequency Order Flow Modeling | Multi-scale neural HMM for high-frequency order-flow and duration modeling. |
| `2603.22886v1` |  | Conditionally Identifiable Latent Representation for Multivariate Time Series with Structural Dynamics | An identifiable variational dynamic factor model learning latent factors from multivariate time series. |
| `2603.28198v1` |  | Policy-Controlled Generalized Share: A General Framework with a Transformer Instantiation for Strictly Online Switching-Oracle Tracking | A strictly-online expert-aggregation framework tracking a switching best expert, with a Transformer update controller. |
| `2603.28257v2` |  | Nonlinear Factor Decomposition via Kolmogorov-Arnold Networks: A Spectral Approach to Asset Return Analysis | KAN-PCA, a nonlinear B-spline autoencoder generalizing PCA for asset-return factor decomposition. |
| `2604.00346v2` |  | Forecasting duration in high-frequency financial data using a self-exciting flexible residual point process | Forecasts limit-order-book interarrival durations via a self-exciting flexible residual point process. |
| `2604.04662v1` |  | Anticipatory Reinforcement Learning: From Generative Path-Laws to Distributional Value Functions | An RL framework lifting the state space into a signature-augmented manifold for non-Markovian decisions under a single observed trajectory. |
| `2604.05008v1` |  | Generative Path-Law Jump-Diffusion: Sequential MMD-Gradient Flows and Generalisation Bounds in Marcus-Signature RKHS | A generative jump-diffusion flow synthesizing forward c�l�dl�g paths consistent with time-evolving path-law proxies. |
| `2604.07159v1` |  | SBBTS: A Unified Schrödinger-Bass Framework for Synthetic Financial Time Series | A generator of synthetic price paths that reproduces both the drift and the stochastic volatility of a real series. |
| `2604.09650v1` |  | Dynamic Forecasting and Temporal Feature Evolution of Stock Repurchases in Listed Companies Using Attention-Based Deep Temporal Networks | Probability that a listed company repurchases shares in the next period, computed from evolving financial ratios. |
| `2604.09821v2` |  | Global Persistence, Local Residual Structure: Forecasting Heterogeneous Investment Panels | Out-of-sample panel forecasts built by separating shared persistence from block-specific residual dynamics. |
| `2604.15519v1` |  | Broken Symmetry, Conservation Law, and Scaling in Accumulated Stock Returns -- a Modified Jones-Faddy Skew t-Distribution Perspective | How mean, skew and realized variance of S&P 500 returns scale with the number of days over which returns are accumulated. |
| `2604.16835v1` |  | The CTLNet for Shanghai Composite Index Prediction | A next-period point forecast of the Shanghai Composite Index from multivariate time-series inputs. |
| `2604.19796v1` |  | Systemic Risk and Default Cascades in Global Equity Markets: A Network and Tail-Risk Approach Based on the Gai Kapadia Framework | The probability and size of default-cascade propagation across a threshold-filtered equity exposure network. |
| `2604.22801v2` |  | Beyond Sequential Prediction: Learning Financial Market Dynamics in Volatile and Non-Stationary Environments through Sentiment-Conditioned Generative Modelling | A sentiment-conditioned generative forecast of a volatile price series built from mixed numerical and textual inputs. |
| `2604.23087v1` |  | Beyond Picking Winners: Correlation-Driven Tail Risk in Venture Capital Portfolio Construction | How deal-level correlation reshapes the distribution of portfolio success counts while leaving the expected outcome unchanged. |
| `2604.23608v2` |  | Non-unique time and market incompleteness | Whether asynchronous, event-driven order flow breaks the unique-calendar-time and no-arbitrage assumptions of continuous-time pricing. |
| `2605.06818v1` |  | Modeling Dynamic Correlation Matrices with Shrinkage Priors | A time-varying correlation matrix with locally adaptive shrinkage, plus a scalar total-correlation summary of cross-sectional dependence. |
| `2605.13407v1` |  | Vector-Quantized Discrete Latent Factors Meet Financial Priors: Dynamic Cross-Sectional Stock Ranking Prediction for Portfolio Construction | A dynamic factor model whose latent factors are vector-quantized discrete codes of cross-sectional structure with mixture-of-experts loadings. |
| `2605.16324v1` |  | Bi-Level Chaotic Fusion Based Graph Convolutional Network for Stock Market Prediction Interval | Calibrated and sharp upper/lower forecast intervals for stock returns, with regime-dependent width. |
| `2605.17724v1` |  | Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ | Whether five-minute OHLCV bar sequences in a single futures instrument carry exploitable sequential predictive structure. |
| `2605.20142v1` |  | Mining Financial Data using Mixtures of Mirrored Weibull Distributions | A flexible two-sided return distribution whose fitted tails drive single-name Value-at-Risk estimates. |
| `2605.21504v1` |  | Multivariate Financial Forecasting using the Chronos Time Series Foundation Models | Whether multivariate inputs improve Chronos-2 forecasts of equities and Treasury rates over univariate baselines. |
| `2605.23962v1` |  | From Index to Equity: Pre-Training Transformers for Stock Return Prediction | Whether pre-training a transformer on an index improves fine-tuned per-stock return-direction and return-value prediction. |
| `2605.25894v1` |  | Predicting Stock Price Direction on Earnings Announcement Days using Multi-modal Deep Learning | Whether pre-announcement news sentiment, fundamentals and price dynamics jointly predict earnings-day price direction. |
| `2605.27848v1` |  | Regime-Based Portfolio Allocation Using Hidden Markov Models and Reinforcement Learning | Whether a three-state HMM regime signal plus a reinforcement-learning policy beats static rotation and a passive benchmark out of sample. |
| `2605.27945v1` |  | Stochastic Volatility, Jumps, and Rates: A Unified Framework for Option Pricing and Term-Structure Simulation | Whether Heston, Bates jump and CIR calibrations differ across Fourier pricing schemes and matter by maturity. |
| `2605.27977v1` |  | Deep Learning Forecasting of the U.S. Aggregate Bond Index | Which series transform and which architecture best predict short-horizon returns of a broad US bond index. |
| `2605.29541v1` | volatility_models | Change-point estimation for Weibull time series with copula-based Markov models | Estimates an offline change point in the joint marginal-and-dependence structure of a nonnegative series such as a volatility measure. |
| `2606.00624v1` | regime_engine | Macro-aware time series forecasting via hierarchical mixed-frequency attention models | Forecasts asset returns via attention over long-run macro contexts nested within daily return signals. |
| `2606.00800v2` | volatility_models | Multiplicative Langevin Process for Volatilities Produces Observed Q-Variance Regularities | Shows the Q-variance relation E(sigma^2/z)=sigma_0^2+0.5 z^2 is exactly equivalent to an Inverse-Gamma law for sigma^2 generated by a multiplicative Langevin process. |
| `2606.04217v2` | none | Polymarket-v1 Database | Releases the Polymarket on-chain trade archive with ground-truth aggressor direction and benchmarks microstructure classifiers against it. |
| `2606.04574v2` | none | Dynamic Multi-Pair Trading Strategy in Cryptocurrency Markets with Deep Reinforcement Learning | Tests whether a PPO+LSTM execution overlay improves crypto pair trading inside deterministic risk bounds. |
| `2606.05138v1` | none | Generating Financial Time Series by Matching Random Convolutional Features | Generates synthetic financial time series by matching differentiable random-convolutional features of real and generated paths. |
| `2606.07450v1` | peer_universe | Information Networks of Stock Prices | Tests whether mutual-information dependency estimators and richer graph filters recover market structure better than Pearson correlation. |
| `2606.08232v3` | none | Hour-Aware Adaptive Risk Management for Autonomous Memecoin Trading on Solana DEXs: Evidence, Theory, and Design Lessons from a 15-Day Deployment | Reports a 15-day memecoin deployment measuring time-of-day returns, filter-stack value against counterfactuals, and small-sample fragility. |
| `2606.08586v1` | cross_section | Cross-sectional topological anomaly scores and intraday return predictability in the S&P 500: A BallMapper, decoder-conditional VAE, and Function-on-Function regression approach | Constructs a stock-level topological anomaly score conditioned on market topology and peer context and tests its predictive content for intraday return curves. |
| `2606.11962v2` | volatility_models | Composite likelihood inference of fractional Gaussian processes with sequentially optimal subset selection | Estimates long-memory/fractional-Gaussian process parameters cheaply via composite likelihood with subset selection maximizing Godambe information. |
| `2606.14182v3` | risk_engine | Correlation emergence and the Epps effect in two coupled limit order books | Explains the Epps effect by deriving realized cross-asset correlation from two coupled limit order books as a function of aggregation time. |
| `2606.15701v1` | technical_engine | Robust Transformer-Based One-Step Stock Index Forecasting via Shifted Data Augmentation | One-step (next-day) index-level forecasts from a modified Transformer trained with shifted data augmentation and a warmup cosine learning-rate schedule. |
| `2606.15755v1` | none | A Multiplex Network Hawkes Model for Systemic Risk Measurement | An inferred directed contagion network among firms whose excitation is split into covariate-weighted transmission-channel layers. |
| `2606.19318v1` | none | Fitting Accumulated Stock Returns with Tempered Skew t-Distribution | The distributional family (tempered skew-t) that fits S&P 500 returns accumulated over 20-120 days, showing tail tempering and gain/loss asymmetry. |
| `2606.24019v1` | position_sizing | Empirical Confirmation of the Square-Root Law of Market Impact in a U.S. Large-Cap Equity | Whether the square-root law of market impact holds for one US large-cap, and with what prefactor, when metaorders are reconstructed from the anonymous order tape. |
| `2606.27670v1` | cross_section | CryptoGAT: Are Time Series Models Effective for Cryptocurrency Forecasting? | Whether pure-price temporal models are effective for cryptocurrency prediction relative to a cross-asset graph model. |
| `2606.27932v1` | volatility_models | (In)Efficient Market States and Rough Volatility Detected via Grunwald-Letnikov Fractional Derivative | A self-similarity test and Hurst estimator that stays valid under long-range dependence, classifying market states as persistent, anti-persistent or efficient. |
| `2606.31475v2` | volatility_models | Real-time identification of the onset of financial rogue waves | Whether the numerical gradient of a Schrodinger operator's minimum eigenvalue spikes at the onset of extreme volatility peaks. |
| `2607.02795v3` | none | Coordinated Sniper Cohorts on Pump.fun: Detection of 1,012 Persistent Wallet Rings and a Contamination-Adjusted Estimate of Coordination-Specific First-Hour Buyer-Flow Lift | Whether persistent coordinated wallet cohorts cause additional first-hour buyer flow in a Solana memecoin launch venue. |
| `2607.06355v1` | none | Entropic Dynamics of Jump-Diffusion Option Pricing | Derives Merton jump-diffusion, the Kolmogorov-Feller equation, the Esscher martingale measure and the implied volatility smile from information constraints instead of postulating a price process. |
| `2607.09906v1` | none | Depth-Efficient Quantum Topological Data Analysis for Regime-Specific Detection of Financial Stress | Betti numbers of a Vietoris-Rips filtration of S&P 500 returns, computed by a depth-efficient Pauli-correlation-encoding variational optimizer, used as a regime-specific financial-stress classifier. |
| `2607.15119v1` | none | Thermodynamic theory of voting and EU elections | Whether a Rayleigh-Jeans thermalization model of coupled nonlinear oscillators reproduces EU party-vote distributions and the associated Lorenz and Pareto curves. |
| `2607.16281v1` | none | A Novel Hybrid Quantum Reservoir Computing (nHQRC) for Phase Transition Detection in Non-Equilibrium Dynamical Systems | Detects latent phase transitions in a non-stationary stochastic driving field using a frozen disordered Ising quantum reservoir, entropy and quantum Fisher information witnesses, and a stochastic Schrodinger-bridge readout. |
| `2607.24065v1` | none | Variational Quantum Conditional Boltzmann Machines for Time-Series Forecasting: Architectures, Symmetric Hyperparameter Evaluation, and a Nonlinear Benchmark | Whether quantum conditional Boltzmann machines beat a classical conditional RBM on financial and NARMA-10 forecasting under a symmetric hyperparameter search. |
| `2607.25189v1` | none | Long-memory GARCH via a two-dimensional Markov chain | A GARCH-type volatility model whose long-memory persistence arises from level-and-slope updates of a latent power-law kernel in a two-dimensional Markov state, with a Foster-Lyapunov stability condition. |
| `2607.25459v1` | none | Emergent Latent-State Computation under Stochastic Volatility | How sequence models internally represent a hidden latent volatility state, showing a two-stage computation from hidden representation to squared-return forecast and locating where readout misalignment degrades it. |
| `2607.26188v1` | none | Bitcoin Runs on a Clock: Why Every Price Indicator Dies and the Halving Clock Doesn't | Why threshold-calibrated cycle indicators degrade in one sequence (precise, then early, then silent) while Bitcoin's time-since-halving structure stays fixed, tested against timing-free and block-bootstrapped nulls. |
| `2607.27099v1` | none | Rainfall is rough | Whether rain-cell arrivals are better described by a critical Hawkes process with a heavy-tailed power-law kernel than by classical Bartlett-Lewis and Neyman-Scott models. |
| `2607.28127v1` | none | FinSMART: Financial Sentiment Analysis for Algorithmic Trading through Market-Aligned Reinforcement Learning | Whether a sentiment model retrained by reinforcement learning against realized market outcomes beats label-supervised financial sentiment models. |
| `2607.28294v1` | none | Bootstrap inference in autoregressive duration models | Whether bootstrap inference stays valid for autoregressive conditional duration models observed over a fixed calendar span so the event count is random. |
| `2608.02828v2` | none | Proper-score observation-driven filters: local geometry, estimation, and continuous-time limits | How an observation-driven filter changes when its update is driven by the derivative of any proper scoring rule instead of the likelihood score. |
| `2608.03088v1` | none | A New Approach to Goodness of Fit for Ergodic Markov Processes | Whether an ergodic Markov model class can reproduce the stationary density of an observed process. |
| `2608.03616v1` | none | Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition | What mechanism drives a liquidation cascade, what its branching ratio is, and whether a Galton-Watson cascade accounts for the pre-cascade state. |
| `2608.05755v2` | none | Cross-Sectional Heterogeneity in LSTM Networks for Financial Time Series | Whether an LSTM with learnable sector embeddings and macro covariates beats pooled LSTMs, random forests and buy-and-hold on S&P 500 daily direction. |
| `2608.07690v1` | none | On a Simple Relationship Between Order Imbalance, Skew and Width in Over-The-Counter Trading | How a market maker's quote skew and width respond to imbalanced customer order flow in sealed-bid enquiries. |
| `2608.08825v1` | none | Hybrid Neural-Classical Correction for Frozen Time Series Foundation Models: A Comprehensive Ablation Study on High-Frequency Stock Prediction | Whether a frozen time-series foundation model can be adapted to opening-hour stock return prediction by hybrid neural and classical residual correction. |
| `2608.10852v2` | none | Universality and Heterogeneity of Stylized Facts in Cryptocurrency and Equity Markets | Whether crypto markets are dynamically equivalent to an equity benchmark once conventional stylized facts overlap. |
| `2608.12424v2` |  | AI-Driven Multiscenario Interest Rate Forecasting: A Proof of Concept for Banking Asset Management | Multi-scenario interest-rate forecasts for asset-liability management, blending BVAR simulation with topic-model and sentiment signals from policy documents. |
| `2608.12634v1` |  | The Price of Permission: Classification Uncertainty in Constrained Capital Markets | How close a security sits to a screening-rule boundary and how much rulebooks disagree, treated as a monitorable classification-risk state. |
| `2608.14323v1` |  | Dependence-Informed Sparse Neural Architecture for Stock Return Prediction | A sparse neural architecture whose depth, widths and connections are fixed by an estimated dependence graph among firm characteristics. |
| `2608.20727v1` |  | A Multiscale Ball Test for Conditional Mean Independence | A test for conditional mean independence with power against departures confined to a bounded region of a multivariate predictor space. |
| `2608.21888v1` |  | Short-horizon mean reversion in cryptocurrency markets: a matched cross-market measurement | How much fifteen-minute directional mean reversion exists in crypto relative to US equities under one matched out-of-sample protocol. |
| `2608.22864v1` |  | From Exponential to Polynomial: An Exact Filter for High-Dimensional MSM Models | An exact Bayesian filter for the Markov-switching multifractal volatility model whose cost is polynomial rather than exponential in dimension. |
| `2608.24703v1` |  | Lead-Lag Relationships in Financial Markets: A Comparison of Multiple Clustering Algorithms | Which clustering algorithm best recovers lead-lag structure across stocks for a lead-follow trading rule. |
| `2608.26106v1` |  | A Statistical-Finance Benchmark for Same-Day Directional Stock Prediction: Walk-Forward Evidence from SPY | Whether the current day's close direction can be predicted from the open and two lagged target-specific prices. |
| `2608.26127v1` |  | Graph-Based Modeling of Financial Volatility Dynamics | Realized-volatility forecasts obtained by modelling the implied-volatility surface as an evolving spatio-temporal graph rather than a static image. |
| `2608.29025v1` |  | Deep Hedging Under Realistic Market Frictions: A Regime-Conditional Empirical Study of Dynamic Option Hedging on Bitcoin Options | Whether neural hedgers beat friction-aware classical hedges on real option data once transaction costs bind. |
| `2609.02660v1` |  | Modeling Trade Durations under Temporal Granularity Effects in Forex Markets | A granularity-adjusted ACD model that corrects integer-value 'heaping' in high-frequency FX trade durations. |
| `2609.06267v1` | report_rendering | From Discrete Trailing Returns to a Continuous Graphical Profile: Return-to-Present Curves | A continuous 'Return-to-Present' curve expressing realized return as a function of hypothetical purchase date with the evaluation date fixed. |
| `2609.07207v1` | volatility_models | Filtering without recursion and some of its uses in financial economics | A non-recursive robust filter defined at each time as the minimizer of a discounted combination of observed and expected losses. |
| `2609.08060v1` |  | Pre-game paired-comparison modeling of professional League of Legends map outcomes | A pre-game win-probability model for individual League of Legends maps combining dynamic form, shrunk stable strength, and a draft covariate. |
| `2609.08106v1` | peer_universe | Nystrom Attention Matches Full Attention for Cross-Sectional Stock Prediction | Decomposition of a neural cross-sectional stock-prediction attention module, showing near-uniform yet low-rank, complementarity-seeking inter-stock attention. |
| `2609.10865v1` |  | The Elliptically Optimal Confidence Interval: A Bivariate Extension of Wilson's Score Method | A closed-form confidence interval for the difference of two independent binomial proportions. |
| `2609.12227v1` | swing | Seasonal Trading in Commodity Futures: Evidence from Regression and Singular Spectrum Signals | Compares seasonal-signal models (dummy-variable regression, SSA, robust low-rank SSA) for trading commodity futures under common implementation constraints. |
| `2609.12793v1` | none | VertiFuseX: Generalizable Financial Forecasting via Multi-Stream Temporal Fusion | A multi-branch LSTM that fuses penultimate-layer features from LSTM/Bi-LSTM/St-LSTM for stock price-level forecasting. |
| `2609.14029v2` | portfolio_construction | Special Markowitz: Thermodynamic Formalism for the Joint Regularisation of Returns and Covariance | A thermodynamic formalism that jointly shrinks returns and covariance per eigenmode using an estimation-quality spectral reliability weight. |
| `2609.14733v1` | none | WaVeFuse: Regime-Adaptive Equity Index Forecasting via Channel-Wise Wavelet Denoising and Vertical Attention Fusion | A wavelet-denoised, channel-wise multi-scale hybrid DL model for equity index forecasting. |
| `2609.20264v1` |  | Risk-Set Transported Synthetic Control with Difference-in-Differences Adjustment under Staggered Treatment Adoption | A synthetic-control estimator for staggered-adoption designs that shrinks horizon-specific donor weights toward a transported reference. |

### None (43)

| id | surface | title | what |
|---|---|---|---|
| `2601.05274v1` | none | On the use of case estimate and transactional payment data in neural networks for individual loss reserving | Compares neural architectures for predicting an individual claim's remaining payments from its transaction and case-estimate history. |
| `2601.12175v2` | none | Distributional Fitting and Tail Analysis of Lead-Time Compositions: Nights vs. Revenue on Airbnb | Fits and compares daily lead-time distributions for Airbnb nights booked and gross booking value. |
| `2601.16821v3` | none | Directional-Shift Dirichlet ARMA Models for Compositional Time Series with Structural Break Intervention | Forecasts a compositional vector through a structural break using an interpretable direction, amplitude and logistic-gate intervention. |
| `2602.01122v1` |  | Was Benoit Mandelbrot a hedgehog or a fox? | An essay arguing Mandelbrot's diverse work is unified by the single principle of scaling. |
| `2602.10960v1` |  | Integrating granular data into a multilayer network: an interbank model of the euro area for systemic risk assessment | Constructs a multilayer euro-area interbank exposure network from supervisory collections and measures channel-specific contagion. |
| `2602.14860v1` |  | Predicting the success of new crypto-tokens: the Pump.fun case | Predicts the graduation probability of Pump.fun tokens from bonding-curve state and launch-level structural and behavioural features. |
| `2602.15474v1` |  | Quantum Reservoir Computing for Statistical Classification in a Superconducting Quantum Circuit | Benchmarks a superconducting-circuit quantum reservoir for classifying heavy-tailed distributions and volatility regimes. |
| `2602.18358v4` |  | Forecasting the Evolving Composition of Inbound Tourism Demand: A Bayesian Compositional Time Series Approach Using Platform Booking Data | Forecasts the evolving composition of guest-origin market shares for tourism destinations. |
| `2603.00422v3` |  | Coupled Supply and Demand Forecasting in Platform Accommodation Markets | Reframes accommodation demand forecasting under endogenous, censored supply in platform-mediated markets. |
| `2603.16720v2` |  | Discrimination-insensitive pricing | Constructs a pricing measure under which the pricing principle is insensitive to protected covariates. |
| `2603.18021v2` |  | Anomaly prediction in XRP price with topological features | Predicts extreme XRP price surges from topological properties of XRP transaction graphs. |
| `2603.21797v1` |  | Connecting Distributed Ledgers: Surveying Novel Interoperability Solutions in On-chain Finance | Surveys cross-chain interoperability protocols and their role in on-chain finance. |
| `2603.24190v2` |  | Dynamical thermalization and turbulence in social stratification models | Nonlinear chaotic thermalization of a coupled-oscillator model of social stratification and wealth. |
| `2603.25338v2` |  | Optimal threshold resetting in collective diffusive search | Optimal event-driven threshold resetting for N diffusive searchers in a box. |
| `2603.29763v1` |  | Option Pricing on Automated Market Maker Tokens | Closed-form European option prices for AMM-traded tokens whose price follows a CEV process. |
| `2604.01431v1` |  | Do Prediction Markets Forecast Cryptocurrency Volatility? Evidence from Kalshi Macro Contracts | Whether Kalshi macro-contract probability changes forecast cryptocurrency realized volatility. |
| `2604.07567v2` |  | Marginal Persistence and Dynamic Copula Dependence in Sovereign Rating Migration Counts: A Discrete Interval-Likelihood MAGMAR Analysis | Latent-dependence estimates for sovereign rating-migration counts that are only observed as interval-censored annual counts. |
| `2604.11413v1` |  | A Herding-Based Model of Technological Transfer and Economic Convergence: Evidence from Central and Eastern Europe | A convergence path for total factor productivity in catching-up economies under peer-influenced technology adoption. |
| `2604.22976v1` |  | Statistical Mechanics of Household Income and Wealth: Derivation from Firm Dynamics via Maximum Entropy and Mixture Aggregation | Derives the two-class income and wealth distribution from firm growth, wages and capital returns. |
| `2604.22995v1` |  | Equations of Motion for an Economy: Capital Deepening, Technology, and Firm Survival | Coupled relaxation equations for capital deepening, capital productivity, frontier productivity and the labor share. |
| `2605.02248v1` |  | Statistics of a multi-factor function from its Fourier transform | Computes the moments of a multi-factor function from its Fourier transform via an index-annihilation condition. |
| `2605.10447v1` |  | Statistical Model Checking of the Keynes+Schumpeter Model: A Transient Sensitivity Analysis of a Macroeconomic ABM | Which parameter families of a Keynes+Schumpeter macro ABM drive transient effects, with simulation effort set by precision targets. |
| `2605.11645v1` |  | GeomHerd: A Forward-looking Herding Quantification via Ricci Flow Geometry on Agent Interactive Simulations | Whether Ollivier-Ricci curvature of agent action graphs anticipates herding earlier than price-correlation statistics. |
| `2605.12151v2` |  | RED-2400: A Public Benchmark of Algorithmically-Rejected Trading Events with Outcome Labels | A labelled benchmark of algorithmically rejected DEX trading events paired with their forward price and liquidity trajectories. |
| `2605.12547v2` |  | The Payment Heterogeneity Index: An Integrated Unsupervised Framework for High-Volume Procurement Oversight and Decision Support | A composite heterogeneity index over a one-dimensional payment sample that isolates structurally distinct supplier cohorts. |
| `2605.15767v1` |  | Market Makers and Risk Aversion: A Hamiltonian Approach to the Excess Volatility Puzzle | Whether chaotic price dynamics emerge purely from anharmonic-oscillator coupling between price and market-maker inventory. |
| `2605.21009v1` |  | Wartime Controls, Political Connections, and the Pricing of Zaibatsu Rents in Japan, 1930-1943 | How wartime controls and zaibatsu affiliation shaped Japanese stock-price formation between 1930 and 1943. |
| `2606.04715v1` | none | How the interpolation of life tables affects the decomposition of life insurance surplus | Measures how interpolating annual life tables changes the Shapley-based decomposition of life-insurance surplus. |
| `2606.12446v2` | none | Temporal Coarse-Graining of Latent Default-Probability Paths Generates Effective Default Correlation | Shows that temporal coarse-graining of a persistent latent default-probability path generates effective default correlation. |
| `2606.21515v1` | none | A Censored Transformed Model for Proportional Outcomes with Boundary Mass and an Application to Loss Given Default Modeling | A regression model for proportional responses that carry probability mass at the boundaries 0 and 1. |
| `2606.23337v1` | none | When Staking Rewards Compound: Measuring the Impact of Ethereum's Pectra Upgrade | How Ethereum's Pectra compounding validators change consensus-layer rewards, consolidation behaviour and staker APR. |
| `2606.25007v1` | none | Multi-Stream Temporal Fusion for Financial Fraud Detection | Which fusion strategy best combines heterogeneous event streams (transactions, logins, risk signals) for detecting fraudulent accounts. |
| `2606.25986v1` | none | The Inference-Compute Frontier and a Latency-Efficient Architecture for Limit Order Book Prediction | Whether limit-order-book predictive loss relates to forward compute by a power law, and a low-latency architecture exploiting that frontier. |
| `2607.28847v1` | none | Effort-Centric Fairness in Lending Decisions | How much minimum feature-effort a rejected loan applicant must spend to cross the approval boundary, and whether that burden differs across protected groups. |
| `2608.06048v1` | none | Thermodynamic statistics of given names in USA and France | Whether the popularity distribution of given names in the US and France behaves like a Rayleigh-Jeans thermalization and condensation system. |
| `2608.09378v1` | none | Scaling laws of Stablecoin Transactions: Evidence from USDT and USDC on the Ethereum blockchain | Whether stablecoin transaction values follow power-law tails and whether the exponent differs by counterparty category. |
| `2608.12259v1` |  | Calibration Bets on the Past: Post-Training Quantization for Financial Time-Series Forecasting | How the choice of activation calibration in post-training 4-bit quantization changes cross-sectional volatility forecast quality. |
| `2608.26122v1` |  | From electricity prices to profits: multidimensional probabilistic forecasting for BESS trading | Multidimensional probabilistic electricity price forecasts and the implied distribution of daily battery-storage trading profits. |
| `2608.26158v1` |  | A Frequency-Controlled Comparison of Tick- and Minute-Based Information Bars for Cryptocurrency Markets | How tick-built versus minute-built information bars (dollar, volume, volatility, range, Renko, hybrid) differ in statistical quality. |
| `2608.26174v1` |  | Forecasting Economically Significant Bitcoin Moves: A Multi-Scale TCN with Profit-Optimized Thresholds | Whether Bitcoin rises more than five percent within seven days, using on-chain, market and sentiment inputs. |
| `2609.17415v1` | none | Financial Contagion Networks as Annealing-Ready Ising Systems Cascades, Bailout Optimization, and Susceptibility | An Ising/QUBO optimization framework for financial-contagion cascades, bailout allocation and institution susceptibility. |
| `2609.18975v1` | none | Sniper Cohorts and Algorithmic Filter Rejections in Solana Memecoin Markets: Two-Window Replication of Lifecycle-Stage Population Separation | Tests whether sniper-cohort detection and algorithmic filter-rejection streams in Solana memecoin markets identify overlapping token populations. |
| `2609.19013v2` | none | Routing Frictions and Executable Liquidity in Fragmented Markets | Measures the gap between gross multi-venue opportunity and net executable liquidity caused by per-venue routing/access costs. |

---

## 9. Honest limits of this survey

1. **Abstracts for all 309, full text for the shortlist.** Every paper was classified from its
   abstract and metadata; 64 were then read in full and 31 promoted to `high`. A paper marked
   `low` on its abstract could still hide a mechanism - the abstracts in this corpus are unusually
   forthcoming about method, which is why the risk is acceptable, but it is not zero.
2. **`relevance` is a judgement against a moving target.** It was assessed against the engine as
   it stands on 2026-09-23. Several `low` verdicts are `low` only because the corresponding
   surface already exists.
3. **A mechanism in a paper is not evidence of an edge.** Most of these results come from one
   asset class, one window, or one vendor's data. The design docs carry the paper's own caveats
   into each proposal for exactly this reason; none of them propose a gate.
4. **Nothing here was backtested against this engine.** Every proposal is untested against this
   engine's data until the harness in
   `docs/design_research_honesty_gates.md` says otherwise.
5. **The corpus is not representative of arXiv.** It is a bulk `q-fin` scrape with a long tail
   (crypto launchpads, sports models, hydrology, EU elections, insurance reserving). 43 papers
   have no equity object at all; they are counted and dismissed rather than silently dropped.
