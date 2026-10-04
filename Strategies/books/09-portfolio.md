# Portfolio Construction & Allocation

`book 09/19` · slug `portfolio` · 573 papers in the corpus · 113 rated high-relevance by the sweep

## 0. Scope

This category covers turning a set of return forecasts, scores or positions into
a target weight vector: mean-variance / minimum-variance optimisation, the
estimation error that makes naive Markowitz fail out-of-sample, shrinkage and
Bayesian priors, hierarchical and robust allocation schemes (HRP, NCO), Kelly
sizing, Black-Litterman, constrained optimisation (box, tracking-error,
cardinality, turnover) and the empirical horse-races between allocation rules.
It matters to this repo because `tradingagents/strategies/portfolio.py`,
`portfolio_optimizer.py`, `hierarchical_risk_parity.py`,
`portfolio_strategy.py`, `book_positions.py` and `overlays.py` already emit
target weights, and the sweep's high-relevance set is overwhelmingly about the
one question those modules answer least defensibly: **how noisy is the
covariance and the mean the weights are computed from, and what does that noise
do out-of-sample.** The alpha side of this corpus (LLM selectors, factor
models) mostly touches other books; here the signal is the risk model.

## 1. Corpus composition

The sweep annotated **573** papers for this category: **113 high**, 347 medium,
113 low. The 60-paper booklist (the sample used to pick deep reads) is
distributed by decade as:

| decade | booklist papers |
| --- | --- |
| 2000s | 2 |
| 2010s | 16 |
| 2020s | 42 |
| **total** | **60** |

Counts are from `evidence/portfolio.md` (573 rows) and
the relevance-ranked shortlist (60 rows); the per-decade table is
computed from the booklist ids.

The category is dominated by **high-dimensional covariance estimation and the
estimation-error problem** — random-matrix theory (RMT), linear and non-linear
shrinkage, spectral cleaning, factor/graph structure for the correlation matrix,
and sparse/cardinality selection. A second cluster is **Bayesian / prior
allocation** (Black-Litterman and its non-normal extensions, posterior-predictive
mean-variance). A third, smaller cluster is **robust allocation schemes** (HRP,
NCO, sparse spanning) and **risk measures for portfolios** (CVaR, tail, GARCH
reconciliation). The category is 2020s-heavy: the field is still actively
arguing about how to regularise the covariance, not about new closed-form
allocators.

## 2. Deep reads

### 2507.21824v1 — Markowitz Variance May Vastly Undervalue or Overestimate Portfolio Variance and Risks
- **Question**: is Markowitz's portfolio-variance quadratic form the market
  variance of an untraded book?
- **Data/market**: analytic; no panel. The investor holds a fixed basket and
  only observes the *trades* made in the market with its securities.
- **Method**: builds a portfolio-level trade time series (value `Q(t_i)`,
  volume `W(t_i)`) and its VWAP; derives market-based variance `Θ(t,t0)` and its
  Taylor expansion in the coefficient of variation `χ` of trade volumes, taking
  Markowitz variance as the zero-order term: `Θ ≈ [ψ0² − 2aψ0χ + (1−ψ0²)χ²]·R²`.
- **Finding**: Markowitz variance is exact only when trade volumes are constant
  (`χ = 0`); with realistic volume-of-trade fluctuations the true variance can be
  **vastly higher or lower** than the Markowitz number.
- **Limitation**: a one-author analytic note; no empirical calibration of `χ`,
  no selection problem, and the "market-based variance" is not the standard
  time-series variance a backtest uses.

### 2508.08148v1 — Unwitting Markowitz' Simplification of Portfolio Random Returns
- **Question**: the companion derivation — where exactly does Markowitz's
  random-return equation `R = Σ R_j X_j(t0)` hide an assumption?
- **Method**: shows the linear form follows only if every volume of every
  consecutive trade with every security is assumed constant over the averaging
  interval; the exact relation carries the *ratio of random trade volumes* with
  each security to the random portfolio volume.
- **Finding**: the omitted volume-ratio terms are what make the market-based
  variance differ from Markowitz's; the approximation is "unwitting", not a
  modelling choice.
- **Limitation**: same note as above; no data, and the corrected object requires
  trade-level (tick) data the repo does not ingest.

### 2605.29413v1 — From Classical Optimization to Bayesian Integration (2026)
- **Question**: how do unconstrained MVO, constrained MVO, Fama-French 5-factor
  regression, Monte Carlo simulation and Black-Litterman compare on the same
  book?
- **Data/market**: 10 US stocks (TSLA, WMT, BAC, GS, LLY, MRK, GOOG, META, AAPL,
  XOM), Sep 2023 – Dec 2025, with a train/out-of-sample split.
- **Method**: builds each portfolio family, evaluates out-of-sample, and inspects
  factor exposures of the constrained portfolio; Monte Carlo convergence is
  checked against an analytic box-constrained solution.
- **Finding**: unconstrained MVO collapses to **highly concentrated corner
  portfolios**; constraints materially reshape the frontier; Monte Carlo needs a
  large simulation count to reproduce the box-constrained optimum; Black-Litterman
  produces more economically intuitive and **more stable** allocations than plain
  MVO by blending equilibrium returns with views.
- **Limitation**: 10 names, ~2 years, a single split; no transaction costs, no
  turnover analysis, no statistical tests on the Sharpe differences.

### 2310.12333v1 — Black-Litterman Asset Allocation under Hidden Truncation Distribution (2023)
- **Question**: what happens to BL when returns are skew-normal rather than
  normal?
- **Data/market**: empirical illustration on equities; theory is the contribution.
- **Method**: assumes the hidden-truncation skew-normal (Arnold-Beaver) return
  model, proves the BL posterior after views is also skew-normal, and applies
  Simaan's three-moment (mean-variance-skewness) optimisation.
- **Finding**: the skew-normal optimal portfolio has **the same expected return
  with less risk** than the classical BL portfolio; portfolios become more
  negatively skewed as target returns rise (investors trade negative skewness for
  return), and portfolio volatility and skewness are negatively related.
- **Limitation**: requires estimating a skewness parameter λ that is very hard
  to pin down; empirical evidence is a single illustration, not an out-of-sample
  horse-race.

### 2202.06666v1 — Two is better than one: Regularized shrinkage of large minimum variance portfolio (2022)
- **Question**: can one combine covariance regularisation and weight shrinkage
  for the global-minimum-variance (GMV) portfolio?
- **Data/market**: simulation plus empirical equity panels; no distributional
  assumption beyond finite 4+ε moments.
- **Method**: Tikhonov-regularises the sample covariance
  (`min w'Sn w + λ w'w s.t. w'1=1`) then shrinks the resulting weights to a target
  `b`; both intensities are chosen by minimising a *consistent estimate of the
  out-of-sample variance* derived with RMT, no cross-validation grid search.
- **Finding**: the double-shrinkage estimator **significantly beats** both its
  non-regularised predecessor and the non-linear-shrinkage (NLS) estimator on
  out-of-sample variance and Sharpe in most scenarios, and has the **most stable
  weights and uniformly smallest turnover**.
- **Limitation**: theory assumes i.i.d. location-scale rows with a bounded
  spectrum; real non-stationarity violates that, and the RMT intensities are
  asymptotic in `p/n → c`.

### 2112.07521v2 — Non-linear shrinkage of the price-return covariance matrix is far from optimal for portfolio optimisation (2021/2022)
- **Question**: is the popular non-linear shrinkage (NLS) covariance actually
  optimal for portfolio construction?
- **Method**: compares the Oracle eigenvalues (Frobenius-optimal) with the
  eigenvalues that minimise realised GMV variance, both as rotationally-invariant
  estimators, and quantifies the gap on historical data.
- **Finding**: NLS minimises the **wrong cost function** when the dependence
  structure is non-stationary; the Frobenius-optimal eigenvalues are not the
  GMV-optimal ones. Only when calibration and test windows are both very large
  relative to the number of assets, and the dependence structure is effectively
  constant, do the two coincide.
- **Limitation**: the optimal-target construction needs an out-of-sample window
  to solve for; the paper's remedy is more diagnostic than a turn-key estimator.

### 2106.02131v3 — Dynamic Shrinkage Estimation of the High-Dimensional Minimum-Variance Portfolio (2021)
- **Question**: can shrinkage handle a *random* target — the portfolio you
  already hold?
- **Data/market**: simulation plus S&P 500 constituents.
- **Method**: extends RMT so a shrinkage estimator of the GMV weights can be
  shrunk toward the **holding portfolio** estimated from previous data (overlapping
  and non-overlapping samples), under only finite 4+ε moments and possibly
  unbounded covariance spectrum.
- **Finding**: shrinking the new GMV estimate toward the previous holding gives a
  dynamic strategy that controls the cost of reallocation; it removes the large
  position changes a direct re-solve would produce.
- **Limitation**: still a second-moment method; the shrinkage intensity, not the
  target, carries all the model risk, and the empirical exercise is one index.

### 1803.03573v1 — Bayesian mean-variance analysis: Optimal portfolio selection under parameter uncertainty (2018)
- **Question**: how should one optimise when μ and Σ are unknown?
- **Method**: writes the mean-variance problem in terms of the **posterior
  predictive** distribution of future returns (not a point-estimated μ, Σ),
  gives a stochastic representation to simulate it, and derives the Bayesian
  efficient frontier; requires only exchangeable, spherically-symmetric returns
  (heavier-tailed than Gaussian).
- **Finding**: the Bayesian efficient frontier **outperforms the sample efficient
  frontier**, which is over-optimistic; the solution is expressed in data only,
  so no plug-in step is needed.
- **Limitation**: needs a prior (Jeffreys here) and `n > p`; the stochastic
  representation uses inverse-Wishart-type draws whose simulation cost grows with
  the panel.

### 1312.0557v7 — Asymptotic Distribution of the Markowitz Portfolio (2020 revision)
- **Question**: what is the sampling distribution of the tangency (Markowitz)
  portfolio weights `Σ⁻¹μ`?
- **Method**: derives asymptotic normality for general returns (fourth moments,
  HAC-robust) and for Gaussian returns, via the augmented second-moment matrix;
  gives a likelihood-ratio test generalising Dempster's covariance-selection test.
- **Finding**: the covariance of the estimated portfolio and the precision matrix
  are obtainable, so one can estimate the **proportion of weight error due to
  mis-estimating Σ** (vs μ) and Wald-test individual weights for sparsification.
- **Limitation**: asymptotic; with `p` comparable to `n` the normal approximation
  and the plug-in variance are unreliable, and the higher moments of the sample
  weights may not exist.

### 2306.05667v1 — Random matrix theory and nested clustered portfolios on Mexican markets (2023)
- **Question**: can RMT-cleaned covariance plus Nested Clustered Optimization
  (NCO) tame Markowitz's instability on a small market?
- **Data/market**: Mexican Stock Exchange (BMV) instruments, 2018–2022,
  moving-window.
- **Method**: replaces NCO's k-means on the dissimilarity matrix with **spectral
  clustering + minimum spanning tree**, and feeds RMT covariance estimators (the
  optimal linear estimator and a Tracy-Widom-based estimator).
- **Finding**: the modified NCO yields **stable, non-negative weights that sum to
  1 without explicit constraints** — avoiding short positions that unconstrained
  Markowitz produces.
- **Limitation**: one emerging market, one window; comparison is against classical
  MVO, not against HRP or shrinkage GMV, and the RMT estimators assume Gaussian
  Wishart structure that real returns violate.

### 2003.05807v1 — Covariance matrix filtering with bootstrapped hierarchies (2020)
- **Question**: can the hierarchical ansatz be made robust and flexible at once?
- **Method**: Bootstrapped Average Hierarchical Clustering (BAHC) — averages
  hierarchical structures computed over many bootstrap resamples of the data,
  instead of committing to a single dendrogram.
- **Finding**: in the high-dimensional case BAHC gives **significantly lower
  realised risk for GMV portfolios** than state-of-the-art linear and non-linear
  filtering, and its spectral decomposition better captures the persistence of
  the dependence structure between calibration and test windows.
- **Limitation**: an ansatz, not a closed-form estimator; bootstrap cost, and the
  test set is DNA microarray plus one financial panel.

### 2105.10306v1 — Turnover-Adjusted Information Ratio (2021)
- **Question**: what does the fundamental law `IR = IC·√BR` look like once IC is
  volatile and turnover costs returns?
- **Method**: extends the IR decomposition to include IC volatility *and* a
  turnover-cost term, for mean-variance and quintile portfolios, by derivation and
  simulation; turnover is driven by alpha-signal decay (one minus the signal's
  autocorrelation).
- **Finding**: the turnover-adjusted IR is **always lower** than the cost-blind IR,
  and — contrary to the naive reading of the fundamental law — managers can
  *improve* IR by limiting or optimising turnover.
- **Limitation**: the cost model is a stylised per-turnover charge; the result is
  an expectation over a signal model, not an empirical fund study.

### 2004.12400v1 — A Dynamic Conditional Approach to Portfolio Weights Forecasting (2020)
- **Question**: should one model the covariance and then invert it, or model the
  optimal *weights* directly?
- **Data/market**: Dow Jones 30 components, high-frequency realised measures.
- **Method**: builds realised optimal weights from high-frequency data and
  proposes a Dynamic Conditional Weights (DCW) model — the conditional weights are
  a linear function of past conditional and past realised weights — benchmarked
  against model-based (realised-GARCH-type) and model-free (random-walk) schemes.
- **Finding**: DCW attains the best minimum-variance allocations on out-of-sample
  variance, certainty-equivalent and turnover for all risk aversions; the paper
  adds **break-even transaction costs** as a measure of the cost range over which
  one allocation beats another.
- **Limitation**: day-trader framing (positions closed daily); the high-frequency
  realised measures are a data dependency the repo may not have for all names.

### 2410.17366v1 — Kendall Correlation Coefficients for Portfolio Optimization (2024)
- **Question**: RMT cleans *eigenvalues*; what cleans *eigenvectors*?
- **Method**: generalises Kendall's rank correlation into a family of estimators
  that are copula-based (margin-free, outlier- and fat-tail-robust), and compares
  Markowitz portfolios built from them against rotationally-invariant (RMT)
  estimators on synthetic and real data.
- **Finding**: Kendall-like estimators give **lower out-of-sample risk** than RMT
  estimators and, unlike Pearson, produce zero eigenvalues only when the number of
  assets approaches the *square* of the number of observations — i.e. they stay
  invertible in regimes where Pearson is singular.
- **Limitation**: rank correlation loses the linear-factor interpretation; the
  comparison is on minimum-variance/frontier portfolios, not full mean-variance.

### 2402.01951v2 — Sparse spanning portfolios and under-diversification with second-order stochastic dominance (2024)
- **Question**: how many assets does a risk-averse investor actually need?
- **Data/market**: large US equity panels.
- **Method**: sparse second-order-stochastic-dominance spanning, estimated with a
  greedy forward-stepwise algorithm plus linear programming (no tuning parameter,
  only the sparsity `q`); short-sale constraints promote sparsity.
- **Finding**: there is **no benefit to expanding beyond 45 assets**; the optimal
  sparse portfolio holds 10 industry sectors, cuts tail risk versus a sparse
  mean-variance portfolio, and shrinks to **25 assets in crisis periods**; standard
  factor models cannot explain its performance.
- **Limitation**: SSD spanning is a utility-based criterion, not a Sharpe test;
  the greedy guarantee is asymptotic in `T`, and results are US-equity-specific.

### 2607.03082v1 — Portfolio Optimization and Tail-Risk Analytics of Actively Managed ETFs (2026)
- **Question**: which allocation rule survives when the universe is heterogeneous
  active ETFs and tail risk is measured directly?
- **Data/market**: 30 funds (mostly active ETFs + one bond mutual fund), daily
  Bloomberg data, 4 Dec 2020 – 24 Dec 2025.
- **Method**: buy-and-hold vs mean-variance vs CVaR-optimised vs tangency, under
  long-only and long-short, historical and 3-year rolling (dynamic) allocation;
  tail diagnostics are empirical VaR, Expected Shortfall, max drawdown, Hill and
  POT-GPD.
- **Finding**: **no single rule dominates**; tangency is the strongest competitor
  to buy-and-hold on risk-adjusted terms, min-variance and CVaR sacrifice upside
  for downside control. In long-only the dynamic CVaR-95 portfolio is most
  consistently attractive; long-short dynamic tangency-CVaR is strong but
  turnover/implementation-sensitive. Tail exposure **remains meaningful after
  aggregation** and varies with the rule, the constraint regime and the rebalancing
  spec.
- **Limitation**: 30 funds over ~5 years; no explicit transaction-cost model in
  the main comparison, and the dynamic results are regime-dependent.

### 2402.17523v2 — Portfolio Analysis in High Dimensions with TE and Weight Constraints (2024)
- **Question**: can constrained portfolios be estimated consistently when `p > T`?
- **Data/market**: simulation and empirical equity data.
- **Method**: CROWN — factor model plus residual nodewise regression — for
  portfolios with tracking-error (TE) constraints, with TE and weight constraints
  jointly, and with weight constraints alone; gives convergence rates for the
  weights, risk and Sharpe, and a data-based test of whether a constraint binds.
- **Finding**: consistency holds **even when assets outnumber the time span**
  (the proof avoids the maximal eigenvalue that diverges at rate `p`); constraints
  reduce risk by shrinking the plausible-portfolio set.
- **Limitation**: needs an observed factor set and strong mixing; TE constraints
  are treated as linear onesides, and the empirical horse-race is vs unconstrained
  and a few benchmarks.

### 2111.12532v1 — Is the empirical out-of-sample variance an informative risk measure for the high-dimensional portfolios? (2021)
- **Question**: can you trust the *empirical* out-of-sample variance when picking
  a portfolio?
- **Method**: derives the high-dimensional asymptotic behaviour of the true and
  empirical out-of-sample variance and of the out-of-sample *relative loss*, for
  the sample GMV, two shrinkage estimators (Frahm-Memmel; Bodnar et al.) and the
  equal-weight target.
- **Finding**: the empirical out-of-sample variance is **misleading in many
  practical situations**, whereas the **relative loss** (normalised by the target
  portfolio) is well-behaved — the paper recommends it as the comparison metric.
- **Limitation**: asymptotic and scale-family assumptions; the practical message
  (use relative loss) is clear, the remedy for the variance itself is not.

### 2203.13740v1 — A generalized precision matrix for t-Student distributions in portfolio optimization (2022)
- **Question**: is `Σ⁻¹` the right dependence object when returns are fat-tailed?
- **Method**: defines a generalised precision matrix (GPM) from the local
  dependence function; for multivariate t-Student it shows conditional
  independence depends on more than `Σ⁻¹`.
- **Finding**: GMV portfolios built on the GPM have **statistically significantly
  lower out-of-sample variance** than the inverse sample covariance on S&P 100 and
  Fama-French industry data, and the GPM is more stable across consecutive
  estimates by Frobenius norm.
- **Limitation**: needs the t-Student (or similar) fit; the GPM definitions are
  several and the paper does not settle which is best for all uses.

### 2103.15232v1 — Portfolio Optimization with Sparse Multivariate Modelling (2021)
- **Question**: how long a training window should a covariance model use when the
  market is non-stationary?
- **Method**: L0-norm sparse elliptical modelling (topologically-regularised
  precision matrix), compared in- and out-of-sample likelihood across train-set
  lengths, against full models.
- **Finding**: **two to three years** of daily observations is the sweet spot;
  beyond that portfolio performance deteriorates and *detaches* from likelihood —
  non-stationarity dominates sampling error. Sparse models give higher
  out-of-sample likelihood, lower realised volatility and more stable weights.
- **Limitation**: the "optimal" window is defined in terms of the holding period;
  results are on one market and the L0 sparsification is computationally heavy.

### 2409.15103v1 — Consistent Estimation of the High-Dimensional Efficient Frontier (2024)
- **Question**: are the three efficient-frontier parameters (`R_GMV`, `V_GMV`,
  slope `s`) correctly estimated by their sample counterparts?
- **Method**: RMT asymptotics with `p/n → c ∈ (0,1)`, no distributional
  assumption, deriving deterministic equivalents of the plug-in estimators.
- **Finding**: **two of the three** frontier quantities are biased and
  *overestimated* by the sample plug-ins, and the additive/multiplicative biases
  are **functions of `c` alone**; consistent corrected estimators are constructed.
- **Limitation**: asymptotics require fourth moments; `c → 0` (low-dimensional)
  is not the regime and real estimates still need `p` chosen.

### 2603.17463v2 — Multivariate GARCH and portfolio variance prediction: a forecast reconciliation perspective (2026)
- **Question**: does combining univariate and multivariate portfolio-variance
  forecasts beat a pure multivariate GARCH?
- **Method**: forecast reconciliation across the univariate/multivariate hierarchy
  for a *known* weight vector; simulation with known and with noisy covariance
  proxies, then a real-data GARCH study.
- **Finding**: reconciliation improves on the multivariate approach, **especially
  when the multivariate model is misspecified**, but with noisy covariance proxies
  correctly- and mis-specified models are often indistinguishable and the gain
  shrinks; the noise in the proxy is the key driver.
- **Limitation**: assumes weights are known (does not couple to allocation);
  reconciliation helps risk reporting more than it changes weights.

## 3. Learnings applicable to this repo

### L1. Wire the Ledoit-Wolf shrinkage into the covariance-based allocators
- **Source**: `arXiv 2202.06666` (2022) — Regularized shrinkage of large minimum variance portfolio; `arXiv 2112.07521` (2021) — NLS far from optimal for portfolio optimisation.
- **Finding**: sample covariance overfits when `p/n` is not small, and *any*
  well-chosen shrinkage/regularisation beats the raw sample matrix for
  out-of-sample GMV variance; the double-shrinkage estimator additionally has the
  smallest turnover.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py::_covariance_matrix` (line 19) and `tradingagents/strategies/hierarchical_risk_parity.py::_aligned_covariance` (line 21). The shrunk matrix exists at `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink` (line 85) but **no allocator consumes it**.
- **Status**: `partial` — estimator shipped; the allocators still build their own raw sample covariance.
- **Concrete step**: add an optional `cov: dict | None` parameter to `risk_parity_weights`, `min_variance_weights`, `max_diversification_weights` and `hrp_weights` that, when supplied (e.g. `ledoit_wolf_shrink(returns)["cov"]`), is used instead of the internal sample matrix; default unchanged.

### L2. Bootstrap-averaged hierarchies beat a single dendrogram for covariance filtering
- **Source**: `arXiv 2003.05807` (2020) — Covariance matrix filtering with bootstrapped hierarchies.
- **Finding**: averaging hierarchical structures over bootstrap resamples
  (BAHC) yields significantly lower realised GMV risk than single-tree or
  shrinkage filtering, because a single tree discards structure that a bootstrap
  reveals to be unstable.
- **Repo surface**: `tradingagents/strategies/hierarchical_risk_parity.py::_cluster_tree` (line 65) — one deterministic single-linkage pass.
- **Status**: `partial` — HRP shipped, bootstrap robustness absent.
- **Concrete step**: add `hrp_weights(..., n_boot=0)`; when `n_boot > 0`, resample rows of the return panel, build each tree, and average the resulting `_bisect_weights` vectors, keeping `n_boot=0` as today's single-linkage behaviour.

### L3. Kelly weights must account for estimation error in μ and Σ, not just scale a full-Kelly solve
- **Source**: `arXiv 1312.0557` (2020 rev.) — Asymptotic distribution of the Markowitz portfolio; `arXiv 2202.06666` (2022).
- **Finding**: the tangency/Markowitz weight vector is noisy and its higher
  moments can be non-finite; the fraction of weight error attributable to
  mis-estimated covariance is measurable, and shrinkage-then-shrink-weights
  controls both error and turnover.
- **Repo surface**: `tradingagents/strategies/portfolio.py::kelly_weights` (line 452) — solves `Σ⁻¹μ` on the **raw sample** covariance and only clips the result to long-only. Fractional Kelly exists at `tradingagents/strategies/size.py::position_size_kelly` (default 0.25).
- **Status**: `partial` — fractional Kelly shipped; the covariance is unregularised and there is no confidence adjustment for estimation error.
- **Concrete step**: route `kelly_weights` through `ledoit_wolf_shrink` (L1) for `Σ`, and scale `fraction` by a documented confidence factor when `n_names/n_obs` exceeds a threshold, so a `p ≈ n` book cannot emit a near-full-Kelly bet.

### L4. Model allocation *turnover* and its break-even transaction cost, not just the target weights
- **Source**: `arXiv 2004.12400` (2020) — A Dynamic Conditional Approach to Portfolio Weights Forecasting; `arXiv 2106.02131` (2021) — Dynamic shrinkage GMV.
- **Finding**: forecasting the *weights* directly (DCW) and shrinking the new GMV
  estimate toward the **holding portfolio** both control reallocation cost; the
  break-even transaction cost is the correct yardstick for choosing between two
  allocations, and shrinking to the held book removes the large trades a direct
  re-solve produces.
- **Repo surface**: `tradingagents/strategies/portfolio_strategy.py::enhanced_index_weights` (line 122) has a `turnover_cap`; `topk_drop_weights` (line 35) reports `turnover`; there is **no break-even transaction cost** and no statistical shrink-to-holding path.
- **Status**: `partial` — turnover is capped in the convex program and measured in topk-drop; not priced.
- **Concrete step**: add a `rebalance_cost(weights_new, weights_held, cost_bps)` helper (and a `w_held` argument to the allocators) that reports the break-even bps at which the new target is no longer preferred — a pure arithmetic addition the PM report can cite.

### L5. Report a turnover-adjusted information ratio alongside IC
- **Source**: `arXiv 2105.10306` (2021) — Turnover-Adjusted Information Ratio.
- **Finding**: accounting for IC volatility and turnover cost makes the achievable
  IR always lower than the cost-blind `IC·√BR`, and limiting turnover can *raise*
  realised IR — the opposite of the naive fundamental-law reading.
- **Repo surface**: `tradingagents/strategies/signal_analysis.py` (IC / quantile signal analysis over any score series).
- **Status**: `absent` — no turnover-adjusted IR anywhere.
- **Concrete step**: add `turnover_adjusted_ir(ic_series, signal_autocorr, cost_bps)` to `signal_analysis.py` and surface it in the existing IC tool output as a second number, keeping the raw IC.

### L6. Support an explicit tracking-error constraint (not only weight deviation) in the enhanced-index program
- **Source**: `arXiv 2402.17523` (2024) — Portfolio Analysis in High Dimensions with TE and Weight Constraints.
- **Finding**: TE-constrained portfolios can be estimated consistently even when
  `p > T`, and jointly imposing TE and weight bounds is what compliance actually
  requires; the effect is distinct from a per-name deviation bound.
- **Repo surface**: `tradingagents/strategies/portfolio_strategy.py::enhanced_index_weights` — `b_dev` bounds `|w − w_b|` per name and `f_dev` bounds a factor exposure, but the active-return *variance* (TE) is not constrained.
- **Status**: `absent` — no TE constraint.
- **Concrete step**: add an optional `te_cap` that constrains `sqrt((w−w_b)' Σ (w−w_b)) ≤ te_cap` (the `cov` argument is already accepted), with the same two-stage fallback already used for `turnover_cap`.

### L7. Treat the covariance window as a tuned, holding-period-dependent choice
- **Source**: `arXiv 2103.15232` (2021) — Portfolio Optimization with Sparse Multivariate Modelling.
- **Finding**: two to three years of daily data maximises out-of-sample
  likelihood and portfolio performance; longer windows *hurt* because
  non-stationarity dominates, and sparse precision matrices are more stable.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::_MIN_OBS` (line 54, `= 30`) is the only floor; the allocators accept as few as two observations (`portfolio_optimizer.py::_covariance_matrix` line 32, `if n < 2`).
- **Status**: `partial` — a floor exists; no upper window and no non-stationarity penalty.
- **Concrete step**: default the allocator return panels to a ~500-750 bar (≈2-3y) trailing window and document the choice in the module docstring, rather than silently using whatever length the caller passes.

### L8. Add a rank-correlation (Kendall/Spearman) covariance estimator for data-poor panels
- **Source**: `arXiv 2410.17366` (2024) — Kendall Correlation Coefficients for Portfolio Optimization.
- **Finding**: copula-based rank correlation improves *both* eigenvalues and
  eigenvectors relative to Pearson in data-poor regimes, gives Markowitz
  portfolios with lower out-of-sample risk, and stays non-singular far longer
  (zero eigenvalues appear only when `p ~ T²`).
- **Repo surface**: `tradingagents/strategies/covariance_models.py` (has `ledoit_wolf_shrink` / `ewma_covariance` but no rank estimator) and `portfolio.py::_pearson` (line 236, Pearson pairwise correlation used by the cluster gate).
- **Status**: `absent`.
- **Concrete step**: add `kendall_correlation(returns_by_name)` to `covariance_models.py` and let `allocation_block`'s correlation gate use it when an aligned panel is flagged data-poor.

### L9. Bayesian posterior-predictive mean-variance is the principled fix for plug-in weights
- **Source**: `arXiv 1803.03573` (2018) — Bayesian mean-variance analysis under parameter uncertainty; `arXiv 2605.29413` (2026).
- **Finding**: solving the optimisation against the **posterior predictive**
  distribution (integrating parameter uncertainty *before* optimising) dominates
  the two-step plug-in, and the Black-Litterman blend of equilibrium and views is
  materially more stable than plain MVO.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py::black_litterman_weights` (the repo's only Bayesian allocator; wired at `agents/utils/quant_adds_tools.py:233`).
- **Status**: `partial` — BL shipped; no posterior-predictive mean-variance, and BL requires caller-supplied caps/views.
- **Concrete step**: add a `posterior_predictive_mv_weights(returns_by_name, risk_aversion)` that applies the `c_{k,n}` inflation factor of the posterior predictive variance to `min_variance_weights`/tangency, so the reported frontier is not the over-optimistic plug-in one.

### L10. Estimate the skew/higher-moment shape of the return distribution and expose a mean-variance-skewness option for BL
- **Source**: `arXiv 2310.12333` (2023) — Black-Litterman under Hidden Truncation Distribution.
- **Finding**: with skew-normal returns the BL posterior is skew-normal, and
  Simaan three-moment optimisation yields the same expected return at lower risk;
  ignoring skew leaves measurable risk on the table for skewed books.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py::black_litterman_weights` — assumes Gaussian returns throughout.
- **Status**: `absent` — no higher-moment handling.
- **Concrete step**: compute the sample skewness of the book's return series (already available in the allocator's `returns_by_name`) and report it beside the BL output, flagging when `|skew|` is large enough that the mean-variance frontier is the wrong object; a full three-moment optimiser can follow if the flag fires.

### L11. Tikhonov-regularise the covariance before inverting it
- **Source**: `arXiv 2202.06666` (2022) — Two is better than one.
- **Finding**: adding `λI` to the sample covariance before inversion (ridge)
  stabilises the smallest eigenvalues that dominate the minimum-variance
  direction; combined with weight shrinkage it beats NLS on variance, Sharpe and
  turnover.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py::_invert` (line 62) inverts the raw covariance with no ridge; `min_variance_weights` (line 128) calls it directly.
- **Status**: `absent` — no ridge term.
- **Concrete step**: add an optional `ridge` parameter to `min_variance_weights` / `max_diversification_weights` that adds `ridge·trace(Σ)/n · I` to the diagonal before `_invert`, default 0.

### L12. Cap and shrink a book toward its current holdings by default
- **Source**: `arXiv 2106.02131` (2021) — Dynamic shrinkage GMV; `arXiv 2004.12400` (2020).
- **Finding**: a re-solve each period is statistically worse and costlier than
  shrinking the new optimum toward the holding portfolio; dynamic shrink-to-hold
  is the low-turnover, low-variance choice.
- **Repo surface**: `tradingagents/strategies/portfolio_strategy.py::enhanced_index_weights` — already accepts `w0` and a `turnover_cap`, i.e. a mechanical shrink-to-hold; `rotation.py` and `portfolio.py::allocation_block` re-solve from scratch when `enable_topk_drop`/`enable_enhanced_index` are off.
- **Status**: `partial` — the convex program has the mechanism; the default value-ratio path does not use it.
- **Concrete step**: when a `holdings_weights` config is present, default `w0` in `allocation_block` to the held book so the value-ratio path shrinks toward holdings rather than re-solving to new names.

## 4. Where this repo is already ahead of the literature

- **Zero-fabrication degradation on every allocator**: the literature almost never
  reports what happens when `Σ` is unusable; `portfolio_optimizer.py` and
  `hierarchical_risk_parity.py` degrade to equal-weight with an explicit `note`
  rather than raising or emitting a pseudo-inverse.
- **Explicit cash-sleeve semantics**: `book_risk.py::portfolio_cvar` (line 61)
  documents and implements weights summing to `< 1.0` as cash dilution; the
  allocation modules leave the clipped excess as cash — a distinction the papers
  do not make.
- **Concentration read surface**: `portfolio.py::active_share` (line 379),
  `effective_holdings` (line 398), `weight_hhi`, `weight_entropy` give
  Cremers-Petajisto active share and inverse-HHI effective holdings, which most
  allocation papers omit entirely.
- **HRP already shipped** with the correct Lopez de Prado pipeline
  (`hierarchical_risk_parity.py::hrp_weights`) and wired as a tool
  (`agents/utils/analysis_tools.py:3801`), so the auditable robustness the
  bootstrapped-hierarchy papers argue for is at least partly present.
- **A convex enhanced-index program with a two-stage fallback**
  (`portfolio_strategy.py::enhanced_index_weights`) already implements
  long-only + `sum(w)=1` + turnover cap + benchmark-deviation bounds + force-hold
  masks and falls back cleanly — far beyond the constrained-MVO comparison in
  `arXiv 2605.29413`.
- **Survivorship is named, not hidden**: `coverage_window.py` defines
  `SURVIVOR_ONLY` and reads the true observation window off the frame — the
  honest-evaluation point behind `arXiv 2603.19380`/`2603.20237` is already an
  explicit label in this repo.

## 5. Defects or risks the literature exposes

- **D1 — Shrinkage exists but is not in the optimisation path.**
  `tradingagents/strategies/portfolio_optimizer.py::_covariance_matrix` (line 19)
  builds the raw sample covariance and `min_variance_weights` inverts it, while
  `covariance_models.py::ledoit_wolf_shrink` is only surfaced by a *diagnostic*
  tool (`agents/utils/analysis_tools.py::get_covariance_read`, line 9697).
  `arXiv 2202.06666`, `2112.07521` and `2106.02131` all show the raw-sample
  solve is dominated out-of-sample. The allocators should consume the shrunk
  matrix (L1). Grounded in the two modules' own docstrings and the wiring grep.

- **D2 — The allocators will invert a covariance built from as few as two
  observations.** `portfolio_optimizer.py::_covariance_matrix` returns a matrix
  whenever `n >= 2` (line 32), and `hrp_weights` likewise accepts `n >= 2`
  (`hierarchical_risk_parity.py::_aligned_covariance`, line 21). `arXiv
  2202.06666`, `2111.12532` and `2409.15103` require the opposite regime: GMV
  estimates are only meaningful when `n ≫ p`, and the sample efficient frontier
  over-estimates risk-adjusted performance when `p/n → c`. A two-observation
  covariance passed to `min_variance_weights` produces a mathematically clean but
  statistically meaningless book with no warning. Add a minimum-observation guard
  (L7).

- **D3 — Reported risk-reward is the over-optimistic in-sample quantity.**
  `arXiv 2409.15103` proves two of the three efficient-frontier parameters are
  *overestimated* by their sample plug-ins as a function of `c = p/n`, and
  `arXiv 2111.12532` shows the empirical out-of-sample variance is a misleading
  selection metric while the out-of-sample *relative loss* is not. Nothing in
  `strategies/evaluate.py` (the cost-aware harness) or `book_risk.py` reports a
  relative-loss or a `c`-corrected frontier, so any in-sample Sharpe the PM cites
  from these allocators is biased upward. This is a reporting gap, not a shipped
  bug; flag when quoting in-sample frontier numbers.

- **D4 — Kelly can bet near-full size on a noisy `Σ⁻¹μ`.**
  `portfolio.py::kelly_weights` (line 452) computes `Σ⁻¹μ` on the raw sample
  covariance of `returns_by_name` and only clips negatives to zero; it is called
  from `portfolio.py::allocation_block` when `enable_kelly_alloc` is on. The
  fraction default (0.25) mitigates the level but not the *direction* error that
  `arXiv 1312.0557` shows makes the Markowitz weight vector noisy with possibly
  non-finite higher moments. Combined with L3, the missing regularisation is the
  exposure.

## 6. Limits of this review

I read full text (abstract, introduction, and the method/results sections) for
the 22 papers in §2 and pulled bibliographic metadata for the 60-paper booklist
and the 573-row evidence pack. I did **not** reproduce any empirical result; all
quantitative claims are the papers' own. The per-decade composition table is
computed only from the 60-paper booklist (years derived from arXiv ids), not from
the full 573-paper category, because the evidence pack gives year + takeaway but
not a machine-readable per-paper table for the medium slice. I did not read the
low-relevance/background tail. Repo statuses were verified by reading the named
modules and grepping the tool wiring; I did not run any test, linter or backtest.
The Olkhov papers (`2507.21824`, `2508.08148`) are single-author analytic notes
whose "market-based variance" is not the variance a bar-based backtest measures;
they are included as a caveat on volume-of-trade weighting, not as an actionable
shipped method.
