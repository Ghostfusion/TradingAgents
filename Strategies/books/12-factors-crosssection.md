# Factors, Anomalies & Cross-Sectional Signals

`book 12/19` · slug `factors-crosssection` · 661 papers in the corpus · 68 rated high-relevance by the sweep

## 0. Scope

This category covers the cross-sectional pricing of equities: the factor zoo
(value, size, momentum, quality/profitability, investment, low-volatility,
liquidity), the replication crisis that surrounds it, the multiple-testing
machinery used to police it, and the portfolio mechanics (standardise,
neutralise, sort, long-short) that turn a characteristic into a tradable book.
It matters to this repo because the entire fundamental/market analyst stack is a
factor engine in disguise: `factors.py`, `cross_section.py`, `universe_factors.py`
and `factor_expressions.py` compute characteristic scores, and the repo's
credibility rule ("compute, don't narrate") only holds if the scores it emits
survive the tests this literature has already run. The category is large and
uneven: a small set of replication/decay papers is directly load-bearing, a
large tail of factor-model and covariance papers is adjacent, and a sizeable
minority is unrelated anomaly-detection applied to non-financial data.

## 1. Corpus composition

The evidence pack annotates **661** papers in this category (68 high, 413
medium, 180 low). I sampled the top 60 by relevance from
`booklists/factors-crosssection.json` for composition; decade and primary-category
counts below are over those 60.

| decade | papers (top-60 sample) |
| --- | --- |
| 2000s | 1 |
| 2010s | 10 |
| 2020s | 49 |

| primary category | papers |
| --- | --- |
| q-fin.ST (statistical finance) | 37 |
| q-fin.PR / cs.LG | 4 each |
| q-fin.MF / q-fin.CP | 3 each |
| econ.EM / q-fin.GN | 2 each |
| q-fin.TR / q-fin.PM / cs.AI / math.ST / stat.ME | 1 each |

The category is dominated by `q-fin.ST`, and within it by two distinct streams:
(a) empirical asset-pricing work on Fama-French model validity, factor
momentum, factor decay and replication, and (b) machine-learning factor models
(LSTM/transformer/graph/RL alpha-mining) that mostly optimise rank-IC rather
than test an economic hypothesis. The replication-crisis material — Harvey-Liu-Zhu
style multiplicity control, McLean-Pontiff style post-publication decay, and
Hou-Xue-Zhang style failed replications — is thinly represented by *publication
venue* in this corpus but heavily cited by the papers that are present, so the
practical guidance is recoverable even where the canonical paper is not on
arXiv. Among the 60 sampled, 14 are papers I read in depth; the remaining deep
reads came from the high-relevance evidence rows.

## 2. Deep reads

### arXiv 2009.04824v1 — Is Factor Momentum More than Stock Momentum? (Falck, Rej, Thesmar)
- Question: is factor-return momentum a distinct anomaly, or a mechanical
  consequence of stock momentum?
- Data/method: 72 documented US factors over CRSP/COMPUSTAT, Jan 1963-Apr 2014,
  restricted to the 1,000 most liquid stocks, beta-hedged on a 36-month rolling
  regression and risk-scaled; cross-sectional (`rank(F)·F`) and directional
  (`sgn(F)·F`) factor momentum, then spanning tests against stock momentum.
- Finding: a typical replicated factor has an annualised Sharpe of only 0.27 in
  the risk-managed sample, yet an equal-risk "menagerie" of all 72 factors earns
  Sharpe 0.96 and tapers off from the mid-2000s. Factor momentum exists at both
  implementations with Sharpe near 1, but after controlling for stock momentum
  and factor exposure, statistically significant residual Sharpe survives only
  for implementations that include the *last month* of returns.
- Finding: at monthly scale stocks mean-revert while factors persist; excluding
  the most recent month, factor momentum is spanned by stock momentum.
- Limitation: US-only factor definitions; the spanning conclusion is specific to
  the 72-factor menu and the risk-management convention chosen.

### arXiv 2105.01380v1 — Why and how systematic strategies decay (Falck, Rej, Thesmar)
- Question: which *ex-ante* characteristics predict the out-of-sample Sharpe
  decay of published anomalies?
- Data/method: the same 72 characteristics-based factors; 11 predictors split
  into four arbitrage proxies, six overfitting proxies, and publication date;
  post-publication and international validation samples.
- Finding: in-sample Sharpe is replicated (mean 0.98) but drops by about one
  half after publication; the publication year alone explains ~30% of the
  variance of Sharpe decay (~5ppt more decay per year of publication date), and
  overfitting proxies — the number of operations in the signal, plus two
  outlier-sensitivity measures — add another ~15%. Arbitrage-related variables
  contribute marginally.
- Finding: without a pool-size adjustment, international decay looks ~90%, but
  with size adjustment it falls to 25-50%, similar to the US post-publication
  haircut. In-sample t-stat is only a weak predictor of decay.
- Limitation: proxies are coarse (operation counts, draw-based sensitivity);
  the causality between publication and decay cannot be separated from
  concurrent information-technology improvements.

### arXiv 2311.10685v3 — High-Throughput Asset Pricing (Chen, Dim)
- Question: how should a searcher mine a huge strategy space without look-ahead
  bias or the conservatism of textbook multiple-testing corrections?
- Data/method: 136,000 systematic long-short strategies from accounting ratios,
  past returns and ticker strings; empirical-Bayes (EB) shrinkage of sample
  Sharpe to predict out-of-sample Sharpe; contrasts EB with Harvey-Liu-Zhu-style
  FDR (Benjamini-Yekutieli 2001 Thm 1.3) and Romano-Wolf/Chordia-Goyal-Saretto
  controls.
- Finding: the EB top-1% portfolio earns ~5.7%/yr out-of-sample (1983-2020),
  comparable to the ~5.9% mean of 200 published strategies, but constructible
  with only real-time information; 91% of survivors are equal-weighted
  accounting-ratio strategies, and returns concentrate pre-2004.
- Finding: nearly all 136,000 strategies fail the Harvey-Liu-Zhu FDR hurdle,
  yet thousands have notable out-of-sample returns — the recommended FDR control
  is too conservative for this null; Storey-style FDR captures most performers.
- Finding: naive max-Sharpe selection often picks the same strategies as the
  ideal Bayesian, but naive *performance estimates* are inflated.
- Limitation: EB assumes a probability model for true performance and a rolling
  window that misses the post-2004 structural break; ticker-based strategies have
  essentially no predictability.

### arXiv 2604.15531v1 — Spurious Predictability in Financial Machine Learning (Nikolopoulos)
- Question: how do we distinguish genuine predictability from artifacts of
  adaptive specification search and evaluation-protocol leakage?
- Method: a falsification audit that runs the *complete* predictive workflow on
  induced-null environments (zero conditional-mean predictability, microstructure
  placebos) with strict walk-forward ordering; the observed walk-forward winner
  is compared to its Monte-Carlo null distribution; a Backtest Inflation Factor
  (BIF) and absolute magnitude gap quantify selection inflation.
- Finding: under a global martingale-difference null the optimised in-sample
  winner statistic grows like `log K_eff` (effective multiplicity after
  correlation), while leakage-robust walk-forward evaluation stays stochastically
  bounded. Workflows that produce significant evidence under the induced null
  are falsified.
- Finding: common confounds reproduce systematic risk premia (significant gross
  returns, zero alpha after factor adjustment) and random cross-validation
  mechanically boosts volatility-forecast results under the null.
- Limitation: the induced-null environments must preserve the salient features of
  real data; the audit screens for workflow invalidity, not economic content.

### arXiv 2601.06499v2 — Cross-Market Alpha: Short-Term Trading Factors in the U.S. via Double-Selection LASSO (Du, Walter, Ulrich)
- Question: do 191 short-horizon price-volume/microstructure signals developed
  for Chinese retail markets carry non-redundant alpha in the S&P 500?
- Data/method: S&P 500, 2002-2022; double-selection (DS) LASSO controlling for
  151 canonical fundamental factors, benchmarked against elastic net and PCA.
- Finding: 17 distinct signals survive with significant, non-redundant monthly
  risk premia; the fast behavioral footprints are not diluted at a monthly
  rebalancing horizon and complement slow fundamental factors.
- Finding: the design deliberately tests a retail-born signal library on the most
  institutionalised large-cap universe as a conservative lower bound — small-cap
  anomalies are excluded as economically unexecutable for large managers.
- Limitation: monthly horizon chosen ex ante; factor-count and selection
  benchmark sensitivity are checked but the economic mechanism remains
  behavioural-adjacent.

### arXiv 2607.01765v3 — A Cap-Axis Integral Diagnostic of Factor Models (Shin)
- Question: does a factor model that improves the maximum-Sharpe frontier also
  price the market's own internal capitalisation-rank coordinate?
- Method: pair each cumulative-capitalisation prefix with equal exposure to the
  aggregate market to form a zero-investment bridge; the bridge-alpha curve
  `α_m(p)` is summarised by signed area, IAE, ISE and SUP, with finite-grid
  HAC-Gaussian inference and residual-block calibration.
- Finding: over 1967-2024 CRSP, q5's negative daily bridge attenuates under
  lead-lag correction and is small monthly, while Fama-French and Carhart leave
  positive, nearly one-signed monthly curves — model-specific, horizon-dependent
  pricing errors rather than a universal ranking.
- Finding: across 155 factors added individually to the market, cap-axis
  magnitude is neither a monotone transform of maximum-Sharpe gain nor explained
  by FF3 SMB exposure.
- Limitation: the diagnostic prices only the subspace generated by one chosen
  capitalisation axis; it complements, not replaces, spanning and joint-alpha
  tests.

### arXiv 2607.05091v6 — Overshooting the Coordinate: Where Factor Corrections Land on Characteristic Axes (Shin)
- Question: where along a characteristic's full order does a counterpart factor
  leave the pricing-error curve?
- Method: sort by a predetermined characteristic (value, profitability,
  investment, momentum), form cap-weighted prefix-versus-market bridges, and trace
  model alpha over the whole order; contrast with decile GRS.
- Finding: counterpart factors generally push error curves downward but land
  differently — profitability and momentum flatten, value *overshoots* through
  zero into significantly negative full-sample errors (rank alphas near -28 bp),
  and investment crosses zero with weaker evidence. Adding UMD to FF3 moves the
  momentum rank alpha from +92.6 to -7.1 bp.
- Finding: value-axis rejection occurs even where FF5/FF6 pass decile GRS, and
  some factors that pass axis tests fail conventional momentum tests because
  their errors are localised and non-monotone; frontier expansion does not
  determine the destination.
- Limitation: claims are local to the chosen characteristic order and traversal
  measure; wider null bands can make non-rejection reflect weak resolution.

### arXiv 2208.01270v3 — Time Instability of the Fama-French Multifactor Models: An International Evidence (Moriya, Noda)
- Question: is the validity (and factor redundancy) of FF3/FF5 stable over time,
  across countries, and across portfolio-sorting schemes?
- Method: Fama-MacBeth rolling-window two-step estimation plus generalised
  Kamstra-Shi GRS statistics to rank nested models, on multiple countries/regions
  and multiple sortings.
- Finding: factor effectiveness in FF3 and FF5 is unstable over time in every
  country; it also depends on the sorting scheme; validity/redundancy do not stay
  stable except in Japan, consistent with efficient-market behaviour there.
- Finding: factor redundancy varies over time and is sorting-sensitive mainly in
  the US and Europe, so a single full-sample FF5 verdict is not a stable
  benchmark.
- Limitation: rolling-window length is a free choice; country conclusions rest on
  the available index histories.

### arXiv 1810.07790v1 — A six-factor asset pricing model (Roy, Shijin)
- Question: does adding a human-capital component to FF5 produce an equilibrium
  six-factor model that prices size/industry portfolios?
- Method: four portfolio families (size-to-B/M, size-to-investment, size-to-momentum,
  size-to-profitability, plus index and industry portfolios); OLS versus IVGMM
  with relevance/endogeneity/over-identification/Hausman diagnostics.
- Finding: the IVGMM estimates are robust and outperform OLS; the human-capital
  factor shares predictive power with the FF5 factors, and for the 83 IVGMM
  estimates its t-ratio exceeds 3.00 — explicitly judged against the Harvey-Liu-Zhu
  t>3 threshold.
- Limitation: single-market sample; "human capital" is a constructed aggregate
  whose economic channel is asserted rather than separately identified.

### arXiv 2003.08302v2 — The Low-volatility Anomaly and the Adaptive Multi-Factor Model (Jarrow, Murataj, Wells, Zhu)
- Question: is low-volatility outperformance an independent risk premium, or the
  equilibrium return of ordinary factors the low-vol book happens to load on?
- Method: Adaptive Multi-Factor model estimated by Groupwise Interpretable Basis
  Selection (GIBS) over ETF basis assets, comparing low- and high-volatility
  portfolio loadings against FF5.
- Finding: low- and high-volatility portfolios load on very different basis
  assets, so volatility is not an independent risk; the low-vol premium is the
  equilibrium performance of those loaded factors. The AMF model beats FF5 both
  in and out of sample.
- Limitation: basis-asset selection is data-driven (LASSO plus prototype
  clustering), so interpretability depends on the ETF menu; the anomaly's
  behavioural and leverage-constraint explanations are not tested here.

### arXiv 1707.05552v1 — Wax and wane of the cross-sectional momentum and contrarian effects: Chinese markets (Shi, Zhou)
- Question: are cross-sectional momentum/contrarian premia in China stable, and
  what market conditions govern them?
- Data/method: Chinese A-shares; time-varying CAPM and FF3 risk-premium
  estimation; contrarian portfolio profitability related to market-state
  variables.
- Finding: the risk-premium relation varies over time and contrarian
  profitability waxes and wanes; higher contrarian returns coincide with upward
  market trend, higher volatility and liquidity, and lower macro-uncertainty.
- Finding: results are framed as consistent with the Adaptive Markets Hypothesis
  — anomaly premia are context-dependent, not constants.
- Limitation: market-condition relationships are associational; the portfolios
  are zero-cost academic constructions, not costed implementations.

### arXiv 1702.07374v1 — Time series momentum and contrarian effects in the Chinese stock market (Shi, Zhou)
- Question: does time-series (single-asset) momentum hold in China, and how does
  it depend on horizon and firm characteristics?
- Method: MOP-style TSMOM signals applied to major mainland indices, varying
  look-back and holding periods; relation to firm-specific characteristics.
- Finding: short-run time-series momentum and long-run contrarian effects both
  appear; performance is highly dependent on the look-back/holding pair and on
  firm characteristics.
- Limitation: index-level rather than full cross-section; no explicit transaction
  cost or capacity analysis.

### arXiv 2301.11394v1 — Customer Momentum (Pinchuk)
- Question: does the Cohen-Frazzini customer-momentum effect replicate, and is it
  distinct from price and earnings momentum?
- Data/method: US supply-chain customer links; long-short decile portfolios
  sorted on customers' past returns; factor-spanning and Fama-MacBeth tests.
- Finding: an equally-weighted (value-weighted) long-short decile earns 122 (106)
  bp/month with t above 4 (2.8) against FF factors; customer momentum neither
  explains nor is explained by price/earnings momentum.
- Finding: it is partly a small-versus-large lead-lag effect, and in the
  post-discovery sample it shrinks and loses significance — consistent with
  exploitation after publication.
- Limitation: customer links are hand-collected and sparsely available; the
  post-discovery decay is consistent with, but does not prove, arbitrage.

### arXiv 1402.3030v2 — Information ratio analysis of momentum strategies (Ferreira, Silva, Yen)
- Question: is momentum performance driven by return autocorrelation or by
  drift, and does the information ratio reveal which at each look-back?
- Method: closed-form theoretical IR of a moving-average momentum rule (average
  return and standard deviation), compared to empirical IR over stationary
  sub-periods and 100+ years of the Dow-Jones Industrial Average.
- Finding: for look-backs up to ~4 months the autocorrelation term dominates the
  IR; beyond ~4 months to a year the drift dominates; after 1975 the drift is the
  larger driver. IR shows damped oscillation with look-back, modelled as
  reversal to the mean growth rate.
- Limitation: single-asset time-series framing (no cross-section); stationarity
  patches are assumed and located heuristically.

### arXiv 2106.08420v4 — Trend-Following strategies via Dynamic Momentum Learning (Levy, Lopes)
- Question: does sequentially learning the time-varying importance of different
  look-back speeds beat naive TSMOM?
- Method: a dynamic binary classifier over 56 futures contracts that switches
  between constant and time-varying past-return relations, then mean-variance
  allocation across the dynamically selected momentum speeds.
- Finding: a mean-variance investor would pay a considerable management fee to
  switch from naive TSMOM to the dynamic-classifier approach, with improved
  signal accuracy around turning points.
- Limitation: 56 futures, single systemic model family; the classifier adds
  estimation risk that is not fully separated from the reported gain.

### arXiv 2306.12964v1 — Generating Synergistic Formulaic Alpha Collections via Reinforcement Learning (Yu et al.)
- Question: should formulaic alphas be mined one-by-one or as a set optimised
  for the downstream combination model?
- Method: an RL alpha generator whose reward is the marginal contribution to the
  combined model's performance, so the generator searches for synergistic sets
  rather than individually strong alphas.
- Finding: the synergy-optimised sets improve stock-trend forecasting and
  simulated investment returns over one-by-one mining, in real market data.
- Limitation: reward is tied to the downstream combination model and the specific
  market; no explicit multiplicity or overfitting control on the search.

### arXiv 2103.05921v1 — Financial factors selection with knockoffs (Challet, Bongiorno, Pelletier)
- Question: can factor selection control the false-discovery rate without the
  conservatism of permutation/null-hacking approaches?
- Method: the knockoff procedure builds fake-but-realistic factors alongside real
  ones so that discovery thresholds control the fraction of false discoveries;
  applied to fund replication and to explanatory/prediction lead-lag networks.
- Finding: knockoffs give a principled FDR handle on an arbitrary factor set and
  remain usable for network inference, not just linear regressions.
- Limitation: knockoff construction quality determines power; the procedure is
  more expensive than a marginal t-test screen.

### arXiv 2511.08571v1 — Forecast-to-Fill: Benchmark-Neutral Alpha and Billion-Dollar Capacity in Gold Futures (Singha et al.)
- Question: can a simple trend-momentum signal survive execution frictions at
  scale?
- Method: rolling 10-year train / 6-month test walk-forward on gold futures
  2015-2025; volatility-targeted positions via fractional, impact-adjusted Kelly
  sizing and ATR-based exits; costs of 0.7 bps plus a square-root impact term
  (γ = 0.02); a capacity frontier `g(L) = μ_u L - ½(σ_u L)² - nkL - γ(nL)^{3/2}`.
- Finding: out-of-sample Sharpe 2.88, max drawdown 0.52% net of costs, β = 0.03
  against spot gold, with a positive-growth frontier up to ~$1bn AUM; bootstrap
  CI [2.49, 3.27] and SPA p = 0.000.
- Limitation: one asset (deep, information-driven gold) and one signal family;
  the square-root impact coefficient is calibrated rather than estimated across
  venues.

## 3. Learnings applicable to this repo

### L1. Factor momentum is not a separate premium from stock momentum except at the one-month lag
- **Source**: `arXiv 2009.04824` (2020) — Is Factor Momentum More than Stock Momentum?
- **Finding**: after controlling for stock momentum and factor exposure, signifi-
  cant factor-momentum Sharpe survives only in implementations that include the
  last month of returns; factors persist monthly while stocks mean-revert there.
- **Repo surface**: `tradingagents/strategies/momentum.py::momentum_12_1` and
  `tradingagents/strategies/factors.py::momentum_multihorizon`
- **Status**: partial — both compute the standard 12-1 skip-one-month momentum
  (`momentum_12_1` is `P(t-21)/P(t-252-21)-1`), i.e. they already exclude the
  month whose inclusion is what makes "factor momentum" distinct. Nothing records
  this as a deliberate decision, and no one-month reversal leg is offered.
- **Concrete step**: add a `momentum_1m_reversal` (last-month return) leg beside
  `momentum_multihorizon`'s 1/3/6/12-month ensemble, with a docstring stating that
  12-1 and 1-month legs are the two ends of the factor-momentum/stock-reversal
  distinction, and cite 2009.04824 in the module.

### L2. Published anomaly Sharpes decay by about half after publication, and signal complexity predicts the decay
- **Source**: `arXiv 2105.01380` (2021) — Why and how systematic strategies decay
- **Finding**: for 72 replicated factors, post-publication Sharpe drops ~50%;
  publication year explains ~30% of decay variance, and complexity/outlier-
  sensitivity add ~15%; in-sample t-stat is a weak decay predictor.
- **Repo surface**: `tradingagents/strategies/evaluate.py::deflated_sharpe_report`
  and `tradingagents/strategies/signal_analysis.py::ic_decay_half_life`
- **Status**: partial — the repo has the multiplicity penalty and an IC-decay
  half-life, but no ex-ante complexity proxy or outlier-sensitivity read attached
  to a candidate.
- **Concrete step**: add an advisory `signal_complexity` count (number of DSL
  operations in an alpha expression, from the AST the purity gate already walks)
  and expose it beside `ic_decay_half_life` so a complex, fast-decaying signal is
  visibly discounted before it is scored.

### L3. Harvey-Liu-Zhu-style FDR control is too conservative; empirical-Bayes shrinkage recovers real performers
- **Source**: `arXiv 2311.10685` (2025) — High-Throughput Asset Pricing
- **Finding**: nearly all of 136,000 strategies fail the Benjamini-Yekutieli
  t-hurdle, yet thousands have notable out-of-sample returns; EB top-1% matched
  published-strategy performance without look-ahead.
- **Repo surface**: `tradingagents/strategies/evaluate.py::family_materiality`
  and `tradingagents/strategies/alpha_zoo.py::bench_zoo` (its `deflated_ic` path)
- **Status**: partial — `family_materiality` is an FDR over a claim family and
  `bench_zoo` deflates IC per expression using trial-ledger N and dispersion; both
  are penalties, not EB shrinkage to a predicted value.
- **Concrete step**: add an advisory `empirical_bayes_sharpe(sharpe, n_trials,
  dispersion)` that reports the shrunk expected out-of-sample Sharpe next to the
  deflated value inside `deflated_sharpe_report`, tagged as an EB estimate.

### L4. Characteristic-axis diagnostics separate frontier expansion from where a factor leaves pricing errors
- **Source**: `arXiv 2607.05091` (2026) — Overshooting the Coordinate; `arXiv 2607.01765` (2026) — Cap-Axis Integral Diagnostic
- **Finding**: value factors overshoot (HML pushes value rank alpha to ~-28 bp),
  momentum/profitability flatten, and Sharpe gains do not determine the landing;
  a model can pass decile GRS and still leave large interior pricing errors.
- **Repo surface**: `tradingagents/strategies/factors.py::fama_french_5_factor`
  and `tradingagents/strategies/signal_analysis.py::quantile_long_short`
- **Status**: partial — `fama_french_5_factor` runs a time-series OLS on FF5 but
  only reports the intercept/alphas; `quantile_long_short` does a decile
  decomposition without a full-order characteristic-axis curve.
- **Concrete step**: add an advisory `characteristic_axis_alpha(caracteristic_sort,
  returns, factor_returns)` that regresses prefix-minus-market bridges over the
  full sorted order and returns signed area and IAE, so a factor's localised vs
  cumulative pricing error is visible.

### L5. Naive max-Sharpe selection can pick good strategies, but its performance estimate is inflated by effective multiplicity
- **Source**: `arXiv 2604.15531` (2026) — Spurious Predictability in Financial ML
- **Finding**: under a global null the in-sample winner grows like `log K_eff`,
  where `K_eff` is the effective independent strategy count after correlation;
  leakage-robust walk-forward stays bounded.
- **Repo surface**: `tradingagents/strategies/evaluate.py::deflated_sharpe_report`
  and `tradingagents/strategies/trial_ledger.py::trial_stats`
- **Status**: partial — `deflated_sharpe_report` uses a `sqrt(2 log N)` threshold
  and `trial_stats` supplies N and Sharpe dispersion from the ledger, but N counts
  ledger rows, not correlation-adjusted `K_eff`.
- **Concrete step**: add a correlation-adjusted effective-trial count (participation
  ratio of the trial-ledger return-series correlation matrix) and feed it as
  `n_trials` so the deflation reflects `K_eff`, not the raw candidate count.

### L6. FF3/FF5 validity and factor redundancy are time-varying and sorting-sensitive
- **Source**: `arXiv 2208.01270` (2024) — Time Instability of the Fama-French Multifactor Models
- **Finding**: factor effectiveness is unstable over time in every country and
  depends on the portfolio-sorting scheme; redundant factors change over time,
  mostly in the US and Europe.
- **Repo surface**: `tradingagents/strategies/factors.py::fama_french_5_factor`
- **Status**: partial — the regression is a single full-sample OLS with fixed FF5
  columns and no rolling-window validity or redundancy check.
- **Concrete step**: add an advisory `ff5_rolling_validity` that runs
  `fama_french_5_factor` on a rolling window and flags windows where an intercept
  or a factor is insignificant, so a full-sample fit is never read as a stable
  benchmark.

### L7. Low-volatility outperformance is factor loading, not an independent risk premium
- **Source**: `arXiv 2003.08302` (2021) — The Low-volatility Anomaly and the Adaptive Multi-Factor Model
- **Finding**: low- and high-volatility portfolios load on different basis assets;
  the low-vol premium is the equilibrium return of those loaded factors, not a
  standalone volatility risk.
- **Repo surface**: `tradingagents/strategies/quant_baseline.py::volatility` and
  `tradingagents/strategies/factor_expressions.py::_side_vol`
- **Status**: partial — `quant_baseline.quant_signal` includes a volatility leg
  (lower vol treated as better) with no check of what the low-vol name loads on.
- **Concrete step**: in `quant_baseline`, gate the volatility leg's contribution
  by the name's existing FF5/industry loadings (or, absent loadings, print the
  leg as `NA` with a reason) so low-vol is not double-counted as independent alpha.

### L8. Transaction costs and square-root market impact bound cross-sectional alpha's capacity
- **Source**: `arXiv 2511.08571` (2025) — Forecast-to-Fill
- **Finding**: net-of-cost Sharpe (0.7 bps + γ(nL)^{3/2}, γ=0.02) still gives a
  positive-growth frontier only up to ~$1bn AUM; turnover churn, not the raw
  signal, sets capacity.
- **Repo surface**: `tradingagents/strategies/evaluate.py::turnover_cost` and
  `tradingagents/strategies/signal_analysis.py::with_without_cost_table`
- **Status**: partial — both subtract a per-trade cost, but neither applies a
  square-root impact term nor reports a capacity frontier.
- **Concrete step**: add an advisory `capacity_frontier(weights_history, adv,
  gamma)` that applies the `g(L) = μL - ½(σL)² - nkL - γ(nL)^{3/2}` form and returns
  the AUM at which expected growth crosses zero.

### L9. Supply-chain (customer) momentum is a distinct, decaying anomaly
- **Source**: `arXiv 2301.11394` (2023) — Customer Momentum
- **Finding**: sorting on customers' past returns earns 122 bp/month (EW) with
  t>4, is not spanned by price or earnings momentum, and loses significance
  post-discovery; it is partly a small-versus-large lead-lag effect.
- **Repo surface**: `tradingagents/strategies/peer_universe.py` (peer/link
  resolution) with `tradingagents/strategies/momentum.py::momentum_12_1`
- **Status**: absent — `peer_universe` resolves peers/suppliers for cross-sectional
  scoring but no module forms a customer-return momentum signal.
- **Concrete step**: add an advisory `customer_momentum(names, customer_links,
  closes)` in `peer_universe.py` that aggregates each name's customers' 12-1
  returns, and label it post-discovery-decayed per 2301.11394.

### L10. A falsification audit against induced-null environments is the gate that makes any backtest interpretable
- **Source**: `arXiv 2604.15531` (2026) — Spurious Predictability in Financial ML
- **Finding**: workflows must run on zero-predictability and microstructure-placebo
  nulls before their walk-forward results are trusted; systematic significance
  under the null falsifies the workflow.
- **Repo surface**: `tradingagents/strategies/evaluate.py::pbo_flag`,
  `purged_cpcv_splits`, and `tradingagents/strategies/falsification.py`
- **Status**: shipped — `evaluate.py` provides purged CPCV, a PBO flag, White
  Reality Check and Hansen SPA; `falsification.py` binds a thesis to numeric
  invalidation conditions. What is missing is an explicit induced-null reference
  class run.
- **Concrete step**: add an advisory `induced_null_audit(trial_returns, seed)`
  that shuffles/phase-randomises the return series to a zero-mean null and reports
  whether the pipeline still produces significant walk-forward evidence.

### L11. Temporal coverage / survivorship labelling must be attached to every cross-sectional statistic
- **Source**: `arXiv 2603.20237` (2026, high-relevance sweep row) — temporal coverage bias in calendar-aligned panels
- **Finding**: naive calendar alignment of panels with differing listing histories
  distorts cross-sectional statistics; instrument observation windows must be
  stated, not assumed.
- **Repo surface**: `tradingagents/strategies/coverage_window.py::coverage_window`
  and `SURVIVOR_ONLY`, consumed by `tradingagents/strategies/data_quality.py::panel_statistic`
- **Status**: shipped — `coverage_window` reads `first_valid`/`last_valid`/
  `padded_days` and `data_quality.panel_statistic` reports `unavailable` when the
  window is padded; the gate default is off.
- **Concrete step**: keep the reader but document, in `cross_section.py::
  residualize_returns`, that length-truncated alignment pairs different sessions,
  and route that function through a date-aligned window so the H10 label is
  emitted wherever a cross-sectional statistic is produced.

## 4. Where this repo is already ahead of the literature

- `evaluate.py` already ships the full multiplicity battery the factor-zoo
  literature spends papers assembling: `reality_check` (White), `spa` (Hansen),
  `pbo_flag`, `purged_cpcv_splits`/`cpcv_overfit_mask`, `deflated_sharpe_report`,
  `probabilistic_sharpe`, and a three-way `materiality_verdict`/`family_materiality`
  that refuses to collapse INCONCLUSIVE into REFUTED — matching 2604.15531's
  discipline more explicitly than most papers do.
- `alpha_zoo.py::redundancy_screen` implements the exact double-selection-LASSO
  design of 2601.06499 in-house (coordinate-descent L1, no sklearn dependency) and
  logs every dropped component to the refusal ledger.
- `factor_expressions.py::availability_gate` refuses forward-shifting expressions
  and unobserved fields at *registration* time — a stronger look-ahead control
  than the after-the-fact leakage diagnostics the ML papers propose.
- `coverage_window.py` + `data_quality.panel_statistic` formalise the
  temporal-coverage and survivor labels that most cross-sectional studies omit.
- `report_attribution.py::novelty`/`admit_factor` screen a proposed factor against
  a reference set at |corr| > 0.90 (`NOVELTY_MAX_CORR`), implementing the
  relabelling check of 2609.00731 before a factor is admitted.

## 5. Defects or risks the literature exposes

- **Look-ahead gate is off by default.** `factor_expressions.py::availability_gate`
  only refuses forward shifts when `enable_factor_availability_gate` is true, and
  `default_config.py:1182` ships it `False`; with the gate off the function returns
  the plain `purity_gate` verdict (line 632-633). 2604.15531 shows leakage is the
  first link in the spurious-predictability cascade, and an off-by-default gate
  means a `ref(close, -1)` expression is admitted silently. The risk is the
  default, not the mechanism.
- **Coverage-window refusal is off by default.** `data_quality.py:134-146` gates
  the H10 padded-window refusal behind `enable_coverage_window`, default `False`
  (`default_config.py:1187`). 2603.20237 documents the distortion that
  calendar-aligned panels with mixed histories produce; with the gate off,
  `panel_statistic` computes over padded windows.
- **Length-truncated residualisation can misalign sessions.**
  `cross_section.py::residualize_returns` (around line 250) pairs a name's series
  with the market over the *common length*, not common dates; when a name has a
  gap this pairs different sessions. The `get_cross_section_momentum` tool already
  documents a date-aligned workaround (`analysis_tools.py:5483-5488`), but the
  underlying function remains length-based — the classic temporal-misalignment
  bias the coverage literature names.
- **Deflation counts raw candidates, not effective trials.**
  `alpha_zoo.py::bench_zoo` (lines 370-390) deflates per-expression IC by the
  trial-ledger N when the ledger is on, else by the caller's `n_trials`, and tags
  the dispersion `"assumed"` when the ledger measured nothing. 2604.15531 shows
  the growth of the in-sample winner is governed by `K_eff` after correlation, not
  the nominal count; assuming either the caller's N or an uncorrelated ledger N
  can under-penalise correlated expression families.

## 6. Limits of this review

I read abstract, introduction, method and results for the 18 papers in §2, and
for the decay/multiplicity core (2105.01380, 2311.10685, 2604.15531, 2601.06499)
I read substantive results and conclusion ranges. Corpus composition in §1 is
derived from the 60-paper booklist only, not from all 661 evidence rows, because
the evidence pack reports counts (68/413/180) but not full per-paper metadata for
the medium and low tiers. I did not attempt to locate the canonical
Harvey-Liu-Zhu, McLean-Pontiff or Hou-Xue-Zhang papers as primary sources — where
this book cites their results it is because a paper I did read reports them
(notably 1810.07790 for the t>3 threshold and 2311.10685 for the FDR result).
Repo symbols were verified by reading the modules named in §3/§5; wiring claims
(e.g. `redundancy_screen` being offline-only) come from the module docstrings,
and I did not run tests, linters or git commands to confirm reachability. The
learnings on neutralisation practice rest more on the repo's own
`cross_section.py` (Grinold-Kahn industry-neutral z, orthogonal projection
neutrality) than on a single corpus paper, since this corpus carries no dedicated
standardisation/neutralisation methods paper.
