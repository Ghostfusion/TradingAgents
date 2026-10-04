# Risk Management & Tail Risk

`book 08/19` · slug `risk-tail` · 510 papers in the corpus · 80 rated high-relevance by the sweep

## 0. Scope

This category covers the measurement and management of the loss distribution's
left tail and of path risk: VaR and expected shortfall and how each is
backtested, extreme-value theory and GPD peaks-over-threshold estimation,
drawdown-based risk measures, coherent and spectral risk measures, tail
dependence and copulas, risk budgeting and CVaR optimisation, stress/scenario
design, and the statistical pitfalls of every one of these under heavy tails.
It matters to this repo more than most categories: `book_risk.py`,
`tail_risk.py`, `risk_governor.py` and the sizing path are the surfaces every
`@tool` in the risk debate reads from, and the governing rule -- *compute, don't
narrate* -- means a mis-scaled or over-confident tail number is worse here than
anywhere else, because it silently propagates into every gate and every
position. The literature in this category is unusually normative (what a risk
measure *should* be) and unusually empirical (what estimators actually do on
finite samples), and both halves bear directly on code that already exists.

## 1. Corpus composition

The sweep labelled **510** rows in this category: **80 high**, **332 medium**,
**98 low**. Of those, **228** are filed here as their primary category in
`CORPUS_INDEX.md`; the remaining 282 are cross-listed from neighbouring
categories (volatility, correlation, portfolio, backtest-evaluation). The
top-60 booklist used to select deep reads is composed as follows.

By arXiv primary category (top-60 booklist):

| primary category | count |
| --- | --- |
| q-fin.RM (risk management) | 23 |
| q-fin.ST (statistical finance) | 21 |
| q-fin.PM (portfolio) | 4 |
| econ.GN / q-fin.TR / q-fin.CP | 3 / 3 / 2 |
| stat.ME, cs.AI, physics.soc-ph, q-fin.GN | 1 each |

By decade (top-60 booklist):

| decade | count |
| --- | --- |
| 2000s | 1 |
| 2010s | 18 |
| 2020s | 41 |

The category is dominated by *statistical* risk measurement rather than
execution-time risk *systems*: q-fin.RM and q-fin.ST together account for 44 of
the 60 selected papers, and the 2020s supply two thirds of them. The recurring
subjects are (i) estimators of VaR/ES and their finite-sample bias, (ii) the
elicitability/backtesting debate that decides whether a risk forecast can be
compared at all, and (iii) EVT/GPD tail extrapolation. Genuine drawdown and
stress-testing papers are a minority; coherent-measure theory is older
(2013-2016) and concentrated in RM. Very little of the category is about
*operational* risk gates, which is where this repo actually lives.

## 2. Deep reads

### arXiv 1611.04851 (2016) — Multinomial VaR Backtests: A simple implicit approach to backtesting expected shortfall
- **Question.** FRTB makes ES the trading-book measure, but ES is not
  elicitable; can it be backtested indirectly by simultaneously testing VaR
  exceptions at several levels?
- **Method.** Emmer et al.'s approximation ES_α(L) ≈ ¼[q(α) + q(.75α+.25) +
  q(.5α+.5) + q(.25α+.75)] motivates a multinomial test over N VaR levels;
  Pearson, Nass and likelihood-ratio variants are compared in simulation.
- **Finding.** Tests with N ≥ 4 are *much* more powerful at detecting
  misspecified loss models than the standard N=1 binomial (Kupiec) exception
  test; Pearson is simplest, Nass is size-robust to N, LRT is most powerful but
  slightly oversized in small samples.
- **Limitation.** The ES link is an approximation, not ES elicitability per se;
  power gains are demonstrated in simulation, and the traffic-light calibration
  is illustrative.

### arXiv 2404.14136 (2024) — Elicitability and identifiability of tail risk measures
- **Question.** A tail risk measure is determined by its generator evaluated on
  the tail; when is it jointly elicitable/identifiable with its quantile?
- **Method.** Definitions of identifiability, elicitability and convex level
  sets for tail risk functionals; theorems (4.3, 5.3) tying joint
  identifiability/elicitability to the generator's, under a monotonicity
  condition on the generator's consistent score.
- **Finding.** Joint identifiability and elicitability hold iff the generator's
  do; the consistent scores form a novel class of *weighted* scores nesting the
  Fissler-Ziegel (VaR, ES) score; the tail expectile plus its quantile is a
  worked example. This is the machinery for objective comparison of risk
  forecasts, distinct from coverage testing.
- **Limitation.** Theoretical; requires a monotonicity condition and does not
  prescribe a finite-sample estimator or a specific score choice.

### arXiv 1303.1690 (2013) — Coherence and elicitability
- **Question.** Is there a law-invariant coherent risk measure that is also
  elicitable (hence point-forecastable and comparable)?
- **Method.** Extends Gneiting's (2011) non-elicitability of ES to all
  law-invariant spectral risk measures; characterizes the elicitable
  law-invariant coherent measures.
- **Finding.** The only law-invariant spectral risk measure that is elicitable
  is minus the expected value; the elicitable law-invariant coherent measures
  are exactly the *expectiles* (Newey-Powell), which are coherent.
- **Limitation.** Elicitability is about the functional, not the estimator; the
  paper explicitly notes the separate robustness problem (Cont et al. 2010) and
  that no quantile-regression analogue exists for ES.

### arXiv 1401.4787 (2014/2015) — On the Measurement of Economic Tail Risk
- **Question.** What risk measures satisfy both Choquet-expected-utility axioms
  (comonotonic independence, monotonicity, standardization, law-invariance,
  continuity) and elicitability?
- **Method.** Axiomatic representation theorem (Choquet integral over a
  distorted probability); elicitability imposed as a statistical axiom;
  extension to multiple scenarios for model uncertainty.
- **Finding.** The only risk measures satisfying both are the mean and the
  **median shortfall** -- the median of the tail loss distribution, equal to VaR
  at level (α+1)/2. Median shortfall is argued to be a better Basel capital
  measure than ES because it is backtestable (and inherits the statistical
  robustness of a quantile).
- **Limitation.** A normative/decision-theoretic argument; it trades ES's
  tail-sensitivity for quantile robustness, which is a policy choice, not a
  free improvement.

### arXiv 1103.5653 (2011) — Extreme Spectral Risk Measures: An Application to Futures Clearinghouse Margin Requirements
- **Question.** Can EVT tail estimators feed a spectral risk measure that
  reflects a user's risk aversion, and how precise are those estimators against
  VaR/ES?
- **Data.** Daily geometric returns, 1991-2003 (3,392 obs), of S&P500, FTSE100,
  DAX, Hang Seng, Nikkei 225 index futures.
- **Method.** POT/GPD fit to losses above 1.5-2% thresholds; plug into
  M_φ = ∫ φ(p) q_p dp with exponential risk-aversion weight
  φ(p) = R e^{−R(1−p)} / (1 − e^{−R}); compare to VaR_p and ES_p (both spectral
  special cases).
- **Finding.** GPD describes the tail indices adequately; the exponential
  spectral measure interpolates between ES and VaR as R grows, and its estimator
  is less precise than ES, which is less precise than VaR. Clearinghouse margins
  (SPAN) sit well below the ES/spectral estimates.
- **Limitation.** Estimator precision is compared by simulation, not a formal
  asymptotics; the exponential weight is one arbitrary choice among admissible
  risk-aversion functions.

### arXiv 1404.7493 (2014/2016) — Drawdown: From Practice to Theory and Back Again (Conditional Expected Drawdown)
- **Question.** Maximum drawdown is ubiquitous in fund practice but almost
  unmeasured as a risk measure; can it be formalized into an optimizable,
  attributable one?
- **Method.** Continuous-time path-dependent setup; CED_α = E[max drawdown |
  max drawdown > D_α] (tail mean of the maximum-drawdown distribution); proofs
  of degree-one homogeneity, convexity and deviation-measure status; empirical
  comparison to ES and volatility via AR(1) fits to US equities and bonds.
- **Finding.** CED is convex (promotes diversification), degree-one homogeneous
  (Euler attribution to factors) and unlike ES it is sensitive to *serial
  correlation* -- its correlation with the AR(1) parameter is substantially
  higher than ES's or volatility's.
- **Limitation.** Distribution of maximum drawdown must be estimated (bootstrap
  or simulation); the empirical study is two asset classes and one serial-
  correlation model.

### arXiv 2608.00127 (2026) — Drawdown Risk Beyond Brownian Motion
- **Question.** Given a Sharpe ratio and the statistical structure of returns,
  how deep and how long should a strategy's drawdowns run?
- **Method.** Reframes Rej-Seager-Bouchaud as a Monte-Carlo experiment; four
  measures (max drawdown, max loss, final negative time, longest recovery); then
  Cornish-Fisher draws with skew/kurtosis/clustering, then fractional Brownian
  motion.
- **Finding.** Depth ∝ SR⁻¹ and length ∝ SR⁻² (validated: at SR=1, ℓ₅%=2.144,
  d₅%=1.498). Depth, loss and duration do **not** move together under
  non-Gaussianity, so one Gaussian table mis-warns. Under long memory the
  apparent drawdown amplification for *depth* is almost entirely self-similar
  dispersion scaling T^{H−1/2} -- a square-root-of-time calibration error, not
  deeper path geometry.
- **Limitation.** The long-memory result is for maximum-drawdown depth only;
  duration measures keep their own horizon convention. Lookup tables are for the
  Brownian benchmark; the non-Gaussian maps are archetype illustrations.

### arXiv 2209.07092 (2022) — Measuring Tail Risks (MPMR)
- **Question.** VaR and ES require a subjective confidence level; can a tail
  measure instead be defined from the most probable maximum event over a time
  frame?
- **Method.** Block-maximum density for n i.i.d. events; MPMR is its mode.
  Analytic forms across distributions; for Pareto sizes MPMR(n) ∝ n^η.
- **Finding.** Unlike VaR/ES, MPMR needs no confidence level, is coherent, and
  makes the time-frame dependence explicit. The power-law scaling yields a
  robust, low-bias tail-index estimator ξ = 1/η. Demonstrated on market losses
  and natural hazards.
- **Limitation.** Requires an i.i.d.-within-block assumption and a distributional
  family for MPMR; the tail-index estimator is still a tail-index estimator.

### arXiv 2304.06950 (2023) — Efficient Estimation in Extreme Value Regression Models of Hedge Fund Tail Risks
- **Question.** POT models require an *ex ante* threshold below which data are
  discarded; can the threshold be estimated jointly with the tail?
- **Data.** Pooled returns of 1,484 hedge funds; median reporting history only
  58 months.
- **Method.** GPD regression extended to non-tail observations with an auxiliary
  *splicing density* (automatic threshold selection) plus artificial censoring of
  bulk likelihood contributions.
- **Finding.** The approach beats classical POT for inference in simulation;
  empirically tail risk is significantly linked to equity momentum, a
  financial-stability index and credit spreads, and exposure to the tail measure
  sorts high- from low-alpha funds (a "fear premium").
- **Limitation.** stat.ME methodology; the wealth of covariates risks
  overfitting in short fund histories, and results are for hedge-fund returns.

### arXiv 2004.05894 (2020) — What You See and What You Don't See: The Hidden Moments of a Probability Distribution
- **Question.** With only n observations, how large is the bias between the
  visible in-sample moments and the true moments?
- **Method.** EVT on the "hidden tail" beyond the in-sample maximum; closed
  forms for hidden moments of order p and their ratio to total moments.
- **Finding.** For tail index near 1 the visible mean badly understates the true
  mean (hidden share is large and grows with the tail's heaviness); the hidden
  *0th* moment (exceedance probability beyond max) is Exponential with mean 1/n
  regardless of scale and tail index.
- **Limitation.** Analytic results assume a power-law tail and i.i.d. sampling;
  practical bias depends on the (unknown) tail index.

### arXiv 1203.2564 (2012) — Percentiles of sums of heavy-tailed random variables
- **Question.** How to estimate high percentiles (VaR) of aggregate losses when
  the heavy tail has no finite mean?
- **Method.** Perturbative expansion of arbitrary order; zeroth order is the
  percentile of the *maximum term*; higher orders use right-truncated (censored)
  moments, always finite.
- **Finding.** The series has the same form whether or not the individual
  variables have finite mean -- unlike earlier single-loss approximations --
  and intermediate truncation orders are remarkably accurate across
  subexponential families; convergence deteriorates at very high order.
- **Limitation.** Independent positive variables; the optimal truncation order
  is distribution- and percentile-dependent, not given in closed form.

### arXiv 2104.10673 (2021) — Backtesting Systemic Risk Forecasts using Multi-Objective Elicitability
- **Question.** CoVaR, CoES and MES are not elicitable or identifiable, so
  classical forecast comparison/validation fails; can it be salvaged?
- **Method.** *Multi-objective* elicitability with two-dimensional scores under
  the lexicographic order; Diebold-Mariano-type tests; a traffic-light
  procedure.
- **Finding.** The lexicographic-score construction makes CoVaR/CoES/MES
  forecast comparison feasible; applied to DAX 30 and S&P 500 with regulator
  recommendations (report the pairwise score vector, not a single number).
- **Limitation.** Validates the *comparison* method, not the correctness of any
  single systemic-risk forecast; requires a chosen auxiliary elicitable
  objective.

### arXiv 2510.05809 (2025/2026) — Coherent estimation of risk measures
- **Question.** Risk measures are designed axiomatically, but their estimators
  are not -- can estimators inherit the same normative properties?
- **Method.** Defines "coherent risk estimator" (CRE) on samples; robust
  representation as suprema of linear estimators; law-invariant CREs are exactly
  suprema of L-estimators, comonotonic ones are single L-estimators.
- **Finding.** Coherence of the risk *measure* does not carry to its estimator;
  many popular parametric/semi-parametric VaR and ES estimators are not
  coherent; different admissible L-estimator weight schemes give substantially
  different capital adequacy even for the same underlying measure and
  distribution.
- **Limitation.** The framework is static and one-period; choosing among
  admissible weight schemes remains a policy decision, not implied by the
  axioms.

### arXiv 2511.07834 (2025) — Lévy-stable scaling of risk and performance functionals
- **Question.** Gaussian T^{1/2} propagation understates tail risk when returns
  scale with a stable index; what is the correct horizon scaling?
- **Method.** Finite-horizon model with a data-driven "Lévy window"
  [τ_UV, τ_IR]; tail index α from log-log slope and a two-segment scale-vs-
  horizon fit; closed forms for VaR, ES, p-Sharpe, p-Information, Kelly under a
  VaR constraint, and drawdown.
- **Finding.** Each horizon-correct law differs from the Gaussian one by an
  explicit bias term proportional to (τ/τ₀)^{1/α} − (τ/τ₀)^{1/2}. The Gaussian
  bias is measurable and horizon-specific; nonparametic up to α and fixed tail
  quantiles.
- **Limitation.** Assumes a scaling window inside which returns are
  location-scale α-stable; outside it variance aggregates. α estimation itself
  has error near the window edges.

### arXiv 1505.01333 (2015) — Sharper asset ranking from total drawdown durations
- **Question.** Moment-based Sharpe estimation is biased under heavy tails; is
  there a moment-free alternative?
- **Data.** 20 years, 3,449 liquid US equities.
- **Method.** Uses the total *duration* of drawdowns as a Sharpe-ratio estimator;
  derives the tail-exponent-dependent bias of moment-based Sharpe estimators.
- **Finding.** Total drawdown duration is an unbiased, efficient, moment-free
  Sharpe estimator for Gaussian and heavy-tailed returns; because tail exponents
  are heterogeneous across assets and time, the drawdown-duration ranking
  differs materially from the moment-based ranking, especially in high-volatility
  periods.
- **Limitation.** Requires a ranked portfolio construction to be interpreted as
  a Sharpe proxy; duration is sensitive to the sampling frequency used to build
  the equity curve.

### arXiv 2109.10946 (2021) — Marginals Versus Copulas: Which Account For More Model Risk In Multivariate Risk Forecasting?
- **Question.** In copula-GARCH VaR/ES forecasting, does model risk come from
  the marginals or the copula?
- **Method.** Fix marginals, fix copula, or neither, across a suite of
  Copula-GARCH models; compare one-day VaR/ES forecasts; apply a model
  confidence set to prune the candidate set.
- **Finding.** Model risk is economically significant, concentrated in crises,
  and **almost entirely due to the choice of copula**. Model-confidence-set
  pruning yields a significant improvement in mean absolute deviation of
  one-day forecasts.
- **Limitation.** Daily frequency and the selected model families; "copula
  dominates" is conditional on the marginal candidates considered.

### arXiv 2606.16840 (2026) — Crashing Together, Rallying Apart: Dynamic Conditional Tail Dependence in Cryptocurrency Markets
- **Question.** Is intra-crypto diversification genuine, and is the crash-rally
  dependence asymmetry stable?
- **Data.** Daily returns of the 13 largest cryptocurrencies, 89 overlapping
  windows, late 2021 to 2025.
- **Method.** Dynamic Hüsler-Reiss graphical models of extremes (tail analogue
  of the Gaussian graphical model), estimated separately for joint crashes and
  rallies and benchmarked against a Gaussian graphical model.
- **Finding.** The lower-tail graph is near-complete and stable -- the market
  crashes as one block -- while the upper tail thins and re-forms sectoral
  structure. Bitcoin and Ethereum form the strongest conditional pair in both
  tails. Standard covariance-based tools understate market-wide crash
  probability by roughly **eightfold**.
- **Limitation.** Crypto-specific; the dynamic windows overlap so consecutive
  estimates are not independent; only 13 assets.

### arXiv 2606.09274 (2026) — Reverse Stress Testing for Multivariate Scenarios
- **Question.** Conventional stress tests shock one asset in isolation and are
  internally inconsistent; can a coherent multivariate scenario be recovered
  from a prescribed loss?
- **Method.** Maximize the conditional density of the non-shocked components
  given an exogenous shock. Gaussian: closed-form mode = conditional mean.
  Semiparametric: empirical-likelihood mode with Gaussian/Student-t local
  sampling. Nonparametric: inverse-distance resampling in a Mahalanobis
  neighbourhood.
- **Finding.** All three variants produce economically coherent stressed
  scenarios that reproduce the observed risk-reward asymmetry; the framework
  inverts the usual scenario→loss direction to loss→scenario.
- **Limitation.** Requires estimating a joint dependence structure, and the
  nonparametric variant's Mahalanobis neighbourhood reintroduces a Gaussian
  metric; validated on a single market dataset.

### arXiv 2604.03499 (2026) — Marking-Aware Sequential VaR Recalibration for Standardized Option Books
- **Question.** Option-book VaR needs a precise loss target (book rule, marking
  rule, loss scale, information set) before any quantile model is evaluated.
- **Method.** Targets normalized book-level loss directly, restricts the
  forecast state to forecast-time information, and sequentially recalibrates an
  upper-tail VaR using only past forecast residuals.
- **Finding.** A reference VaR undercovers all three SPX/QQQ option books;
  sequential residual recalibration moves exceedance rates close to target and
  has the best aggregate performance across books.
- **Limitation.** Standardized/index-option books; the recalibration is
  empirical (residual-quantile) and offers no distributional guarantee.

### arXiv 1103.5665 (2011) — Evaluating the Precision of Estimators of Quantile-Based Risk Measures
- **Question.** How precise are VaR, ES and spectral risk-measure estimators,
  and can their precision be estimated without asymptotic assumptions?
- **Method.** A Monte-Carlo method for estimator precision; simulation of the
  estimator distributions.
- **Finding.** Relying on asymptotic normality is unreliable at common sample
  sizes; estimator distributions (especially for ES and spectral measures) are
  skewed and heavy-tailed, and precision itself depends on the true loss
  distribution.
- **Limitation.** Simulation-based; the Monte-Carlo precision estimate needs a
  model for the loss distribution, which is the same uncertainty being measured.

## 3. Learnings applicable to this repo

### L1. Backtest ES with a multinomial VaR test, not a single-level exception test
- **Source**: `arXiv 1611.04851` (2016) — Multinomial VaR backtests.
- **Finding**: ES can be validated indirectly by simultaneously testing VaR
  exceptions at N ≥ 4 levels (via the Emmer et al. ES quantile approximation);
  multinomial tests are far more powerful than the N=1 Kupiec binomial, with
  Nass most size-robust and LRT most powerful but slightly oversized.
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_coverage_test`.
- **Status**: `partial` — I read the function: it ships Kupiec POF plus
  Christoffersen independence/joint conditional coverage on a *single* VaR
  series, and no multi-level or ES-proxy test exists.
- **Concrete step**: add `multinomial_var_backtest(returns, levels=(0.01,0.025,0.05,0.10))`
  beside `var_coverage_test`, reusing its expanding-window `simple_var` path,
  and return Pearson/Nass/LRT statistics plus an ES-approximation verdict.

### L2. Compare risk forecasts with consistent scores (elicitability), not only coverage
- **Source**: `arXiv 2404.14136` (2024) — Elicitability of tail risk measures.
- **Finding**: A tail risk measure is jointly elicitable/identifiable with its
  quantile iff its generator is; the consistent scores are weighted scores that
  nest the Fissler-Ziegel (VaR, ES) score, enabling objective ranking of
  competing risk forecasters.
- **Repo surface**: `(new module) tradingagents/strategies/risk_scores.py`.
- **Status**: `absent` — a grep of `tradingagents/strategies/` finds no scoring
  function, elicitability or forecast-comparison surface; `alpha_eval.py` scores
  directional alpha, not risk forecasts.
- **Concrete step**: implement the FZ joint (VaR, ES) weighted score and
  `compare_risk_forecasts(forecasts, realized)` ranking producers by mean score,
  reported beside `var_coverage_test`.

### L3. Add the elicitable coherent alternatives: median shortfall and expectiles
- **Source**: `arXiv 1401.4787` (2014) and `arXiv 1303.1690` (2013).
- **Finding**: The only Choquet-expected-utility + elicitability-admissible
  measures are the mean and the *median shortfall* (= VaR at (α+1)/2); the only
  elicitable law-invariant coherent measures are *expectiles*. Both are
  backtestable by existing machinery; ES is not elicitable.
- **Repo surface**: `tradingagents/strategies/book_risk.py::simple_var`.
- **Status**: `partial` — `simple_var` computes a single historical quantile;
  no median shortfall or expectile is computed anywhere in the package.
- **Concrete step**: add `median_shortfall(returns, alpha)` returning
  `simple_var(returns, (1.0+alpha)/2.0)` and an asymmetric-least-squares
  `expectile(returns, tau)`, each fed to `var_coverage_test`.

### L4. A spectral risk measure with an explicit risk-aversion weight
- **Source**: `arXiv 1103.5653` (2011) — Extreme spectral risk measures.
- **Finding**: M_φ = ∫ φ(p) q_p dp with exponential weight φ(p) ∝ R e^{−R(1−p)}
  is coherent and parameterised by one risk-aversion coefficient R; VaR and ES
  are its degenerate limits; spectral estimators are less precise than ES.
- **Repo surface**: `tradingagents/strategies/book_risk.py::cvar`.
- **Status**: `partial` — I read `cvar` and `simple_var`; only the two
  degenerate spectral weights exist (a point mass for VaR, a constant for ES).
- **Concrete step**: add `spectral_risk_measure(returns, R)` by quadrature over
  the sorted sample, gated off by default, reported beside `cvar` with its
  estimation uncertainty.

### L5. Declare the estimator's L-estimator weights and test its coherence
- **Source**: `arXiv 2510.05809` (2025/2026) — Coherent estimation of risk measures.
- **Finding**: Coherence of a risk measure does not carry to its estimator;
  law-invariant coherent risk estimators are exactly suprema of L-estimators,
  and different admissible weight schemes give materially different capital.
- **Repo surface**: `tradingagents/strategies/book_risk.py::cvar` and `::simple_var`.
- **Status**: `partial` — the plug-in estimators are weighted order statistics,
  but the weight vector is implicit and no coherency diagnostic is reported.
- **Concrete step**: expose the L-estimator weights used by `cvar`/`simple_var`
  in their return dict and add one admissible alternative tail-weight scheme
  (e.g. exponential decay) so a caller can see the capital spread.

### L6. Select the POT threshold by stability, not by a fixed quantile
- **Source**: `arXiv 2304.06950` (2023) — EVT regression hedge-fund tails.
- **Finding**: An ex-ante threshold causes estimation inefficiency; joint
  estimation with a splicing density removes the subjectivity. The empirical
  tail is linked to equity momentum, financial stability and credit spreads.
- **Repo surface**: `tradingagents/strategies/book_risk.py::extreme_quantile_var`
  and `::_gpd_fit`.
- **Status**: `partial` — I read both: `threshold_quantile` defaults to a fixed
  0.90, and `_gpd_fit` silently falls back to its method-of-moments warm start
  when Nelder-Mead fails.
- **Concrete step**: add a threshold-stability scan (fit ξ, β across several
  thresholds and report the plateau) and mark the read `unstable`/refuse when
  ξ or β moves materially, instead of reporting a fit from one threshold.

### L7. Label the hidden-tail bias on every historical tail number
- **Source**: `arXiv 2004.05894` (2020) — Hidden moments.
- **Finding**: For tail index near 1 the visible in-sample mean badly
  understates the true mean; the hidden 0th moment beyond the sample max is
  Exponential with mean 1/n regardless of scale and index.
- **Repo surface**: `tradingagents/strategies/book_risk.py::simple_var` and `::cvar`.
- **Status**: `partial` — `extreme_quantile_var` extrapolates beyond the sample
  max, but the historical VaR/CVaR carry no hidden-tail bias label and its own
  floor is only 3 × `min_exceed` = 30 observations.
- **Concrete step**: when `extreme_quantile_var` returns a fitted ξ, also
  report the implied hidden-mean share and P(hidden exceedance) = 1/n in its
  record so the historical number is read with its censoring bias.

### L8. Scale multi-day VaR/ES by the tail index, not by sqrt(T)
- **Source**: `arXiv 2511.07834` (2025) + `arXiv 1103.5649` (2011).
- **Finding**: Under Lévy-stable scaling the correct T-day risk scales as
  T^{1/α}; the Gaussian bias is T^{1/α} − T^{1/2}. Normal-based multi-period
  estimates are biased even after GARCH filtering (1103.5649 finds the
  normality bias extends to the conditional setting).
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_cvar_horizon`.
- **Status**: `partial` — I read it: both `empirical` and `parametric` paths
  scale by `math.sqrt(T)`, and `scaling_valid` checks only return
  autocorrelation, never the tail index.
- **Concrete step**: add a tail-index branch scaling by T^{1/α} (or reporting
  the explicit bias term) and set `scaling_valid=False` when the fitted α < 2,
  so the sqrt(T) figure is not consumed silently.

### L9. A moment-free Sharpe estimator from total drawdown duration
- **Source**: `arXiv 1505.01333` (2015) — Total drawdown durations.
- **Finding**: Total drawdown duration is an unbiased, efficient, moment-free
  Sharpe estimator for Gaussian and heavy-tailed returns, and it re-ranks
  assets versus the moment-based Sharpe, most in high-volatility periods.
- **Repo surface**: `tradingagents/strategies/evaluate.py::sharpe`.
- **Status**: `absent` — no drawdown-duration estimator exists; `max_drawdown`
  and `calmar_ratio` measure depth only.
- **Concrete step**: add `total_drawdown_duration(equity_curve)` and a
  `sharpe_from_duration` estimator in `evaluate.py`, reported beside `sharpe`
  so the two rankings can be compared.

### L10. Prune copula families with a model confidence set and attribute copula vs marginal risk
- **Source**: `arXiv 2109.10946` (2021) — Marginals versus copulas.
- **Finding**: In Copula-GARCH VaR/ES forecasting, model risk is large,
  crisis-concentrated and almost entirely copula-driven; a model confidence set
  materially improves one-day forecast MAD.
- **Repo surface**: `tradingagents/strategies/book_risk.py::copula_scenarios`.
- **Status**: `partial` — I read it: four families are available with a fixed
  default `nu=5` and `seed=0`, but no family selection or risk attribution.
- **Concrete step**: add a held-out MCS pass over the candidate families and
  return the surviving set plus the copula-vs-marginal share of forecast
  dispersion.

### L11. Conditional (not pairwise) tail dependence, and its crash-understatement factor
- **Source**: `arXiv 2606.16840` (2026) — Dynamic conditional tail dependence.
- **Finding**: Pairwise and covariance-based dependence understate market-wide
  crash probability ~8×; a Hüsler-Reiss extremal graphical model recovers the
  conditional tail structure and shows a near-complete lower-tail graph.
- **Repo surface**: `tradingagents/strategies/book_risk.py::_tail_dependence`
  and `tradingagents/strategies/triadic_stress.py::triadic_stress`.
- **Status**: `partial` — `_tail_dependence` is pairwise, unconditional, at a
  single `quantile=0.1`; `triadic_stress` is a coincident spectral-gap scalar
  with no conditional tail edges.
- **Concrete step**: add a conditional tail-dependence adjacency (partial tail
  graph) beside the pairwise matrix and report the implied joint-loss
  understatement factor relative to the Gaussian/covariance read.

### L12. Reverse stress testing: recover a coherent scenario from a target loss
- **Source**: `arXiv 2606.09274` (2026) — Reverse stress testing.
- **Finding**: Maximizing the conditional density given a prescribed shock
  yields a coherent multivariate scenario (Gaussian mode = conditional mean;
  empirical-likelihood and inverse-distance resampling for weaker assumptions),
  resolving the inconsistency of single-asset shocks.
- **Repo surface**: `tradingagents/strategies/book_risk.py::book_correlated_stress`.
- **Status**: `partial` — I read it: it applies a uniform shock and averages the
  worst historical names, with no conditional-density inversion or target-loss
  reversal.
- **Concrete step**: add `reverse_stress_scenario(returns_by_name, target_loss)`
  returning the Gaussian conditional-mean vector under the observed covariance,
  with the empirical-likelihood variant behind a gate.

### L13. Recalibrate the VaR the coverage test measures
- **Source**: `arXiv 2604.03499` (2026) — Marking-aware sequential VaR recalibration.
- **Finding**: A reference VaR undercovers option books; recalibrating the
  upper-tail VaR on past forecast residuals moves exceedance rates to target and
  gives the best aggregate performance across books.
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_coverage_test`.
- **Status**: `absent` — the repo *tests* coverage but never recalibrates the
  series it tests; `tail_risk.py` widens a reported band, it does not correct the
  quantile.
- **Concrete step**: add `recalibrate_var(var_series, realized, alpha)` mapping
  the empirical residual quantile to a corrected VaR level, returned as a
  proposal beside the coverage verdict.

### L14. Multi-step VaR/ES by quantile scaling plus resampling
- **Source**: `arXiv 2502.20978` (2025) — Quantile time series and historical
  simulation.
- **Finding**: Scale returns by an estimated quantile series, then resample to
  build the multi-step forecast distribution (extendable to Realized GARCH and
  CAViaR via a measurement equation); this beats standard historical simulation
  for 1% and 2.5% VaR/ES at one and ten days.
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_cvar_horizon`.
- **Status**: `partial` — `var_cvar_horizon` offers only an empirical sqrt(T)
  scaling and a normal parametric path; there is no scaling/resampling path.
- **Concrete step**: add a `method="quantile_hs"` branch that scales by an
  estimated quantile series and resamples the scaled residuals to the horizon.

### L15. Conditional Expected Drawdown (CED) and drawdown attribution
- **Source**: `arXiv 1404.7493` (2014/2016) — Conditional Expected Drawdown.
- **Finding**: CED -- the tail mean of the maximum-drawdown distribution -- is
  degree-one homogeneous (Euler attribution) and convex (optimizable), and is
  more sensitive to serial correlation than ES or volatility.
- **Repo surface**: `tradingagents/strategies/book_risk.py::cdar`.
- **Status**: `partial` — `cdar` computes CDaR (mean of the worst draws of the
  running drawdown process), not CED (tail mean of the path-maximum drawdown
  distribution), and no drawdown attribution exists.
- **Concrete step**: add `conditional_expected_drawdown(equity_distribution, alpha)`
  over simulated paths (the `drawdown_envelope` machinery) plus an Euler
  per-name attribution.

## 4. Where this repo is already ahead of the literature

- **VaR/CVaR with a conformal band, quality tier and uncertainty**
  (`tail_risk.py::tail_risk`): the number travels with its calibration width,
  its data-quality verdict, its ensemble dispersion and its breach drift, and is
  refused below thresholds. No paper in this category couples a risk number to
  its reliability this way; `conformal.py` already exists for the band.
- **Kupiec + Christoffersen wired as a first-class producer against
  regime-conditional VaR** (`book_risk.var_coverage_test` +
  `regime.regime_conditional_var`): most backtesting papers stop at proposing
  the test; here the test is a tool the analyst loop reads.
- **GPD EVT plus a jump-shape leg** (`book_risk.extreme_quantile_var` +
  `_jump_read`): distinguishes a one-print gap from a diffuse stretch of the same
  variance via the bipower/quarticity proxy -- no tail paper in the set pairs a
  GPD fit with jump/one-print diagnosis.
- **Rockafellar-Uryasev minimum-CVaR LP and CDaR** (`book_risk.min_cvar_weights`,
  `book_risk.cdar`): a deterministic sample-average LP with a projected-
  subgradient fallback, plus CDaR, already shipped.
- **HRP and risk parity with marginal risk contributions**
  (`hierarchical_risk_parity.hrp_weights`,
  `portfolio_optimizer.risk_parity_weights` / `risk_contribution`): risk
  budgeting is present, not just proposed.
- **The drawdown envelope implements the paper's own result**
  (`book_risk.drawdown_envelope`, 2608.00127): four expectations, a
  T^{H−1/2} depth rescaling and Lo's Sharpe uncertainty, deliberately
  report-only -- at parity with the frontier.
- **Deflated Sharpe and PBO already shipped** (`evaluate.deflated_sharpe`,
  `alpha_zoo`): the multiple-testing correction the 2026 robustness papers
  propose.
- **A single drawdown resolver with provenance**
  (`book_context.measured_book_drawdown`): prevents two numbers under one name.
- **A measured (not chosen) stop distance** (`stop_mae.mae_stop_distance`): the
  MAE distribution, not a modelled stop.
- **Triadic stress with an explicit coincident label**
  (`triadic_stress.triadic_stress`): the spectral gap of the correlation network
  is reported as coincident, never leading.

## 5. Defects or risks the literature exposes

1. **Multi-day VaR/ES are under-scaled under heavy tails.**
   `book_risk.var_cvar_horizon` (`book_risk.py:390,412`) scales by `sqrt(T)` and
   sets `scaling_valid` from an autocorrelation check only. `arXiv 2511.07834`
   shows the correct scaling is T^{1/α} with a bias term T^{1/α} − T^{1/2}, and
   `arXiv 1103.5649` finds the normal bias persists in conditional estimates.
   A momentum book with α ≈ 1.5 has a 10-day VaR understated by roughly the
   factor 10^{1/1.5}−10^{1/2}; the flag does not catch it.
2. **Asymptotic chi-square VaR tests at small samples.**
   `book_risk.var_coverage_test` (`book_risk.py:1082`) relies on χ²(1) / χ²(2)
   limits with a 60-observation floor. `arXiv 1103.5665` shows risk-estimator
   distributions are far from normal at common sample sizes, so the test's size
   is not what its nominal p-value claims.
3. **Fixed POT threshold with a silent degradation path.**
   `book_risk.extreme_quantile_var` (`book_risk.py:562`) fixes
   `threshold_quantile=0.90`, and `_gpd_fit` (`book_risk.py:444`) returns its
   method-of-moments warm start when the optimizer fails -- so an unconverged
   fit is still published. `arXiv 2304.06950` shows ex-ante threshold choice is a
   first-order source of inefficiency.
4. **Empirical plug-in VaR/CVaR estimator coherence is unexamined.**
   `book_risk.simple_var` / `cvar` (`book_risk.py:9,18`) use `k=int(alpha*n)`
   order statistics with no declared weight scheme and no coherency check;
   `arXiv 2510.05809` shows a coherent measure's plug-in estimator need not be
   coherent and that admissible weight schemes give materially different capital.
5. **Pairwise unconditional tail dependence understates joint losses.**
   `book_risk._tail_dependence` (`book_risk.py:892`) reports P(U_j≤q | U_i≤q) at
   a single `q=0.1`. `arXiv 2606.16840` shows pairwise/covariance measures
   understate market-wide crash probability by roughly 8×, with conditional
   tail structure only recoverable from an extremal graph.
6. **Copula model risk is unpriced.**
   `book_risk.copula_scenarios` (`book_risk.py:912`) offers four families with a
   fixed default `nu=5` and `seed=0` and no selection. `arXiv 2109.10946` finds
   model risk is almost entirely copula-driven, so the choice between these
   families is exactly the risk that is not being reported.
7. **Book stress is a uniform shock, not a coherent scenario.**
   `book_risk.book_correlated_stress` (`book_risk.py:148`) applies one shock to
   all names and averages the worst historical losses. `arXiv 2606.09274` shows
   this is internally inconsistent with the empirical dependence structure and
   proposes the conditional-density inversion this repo lacks.
8. **Historical tail numbers carry no hidden-tail bias label.**
   `book_risk.simple_var` / `cvar` (`book_risk.py:9,18`) are in-sample
   order-statistic quantiles. `arXiv 2004.05894` shows that for tail index near
   1 the visible mean badly understates the true mean; the repo's GPD read
   extrapolates but does not surface this bias on the historical figures.
9. **A published reliability layer admits its own centre fails coverage.**
   `tail_risk.py::tail_risk` widens a conformal band around an expanding
   historical VaR while its `basis` string states "the producer's own VaR still
   fails the Kupiec test". The widening and the coverage failure are not
   reconciled, so a reader may consume the band's centre as a calibrated VaR.
10. **Cornish-Fisher modified VaR can be non-monotone.**
    `size.py::modified_var` (`size.py:206`) applies a fourth-order quantile
    expansion; `arXiv 1103.5665` documents the fragility of such
    distribution-free quantile asymptotics, and a CF quantile is not guaranteed
    monotone in α or a valid quantile for arbitrary skew/kurtosis.

## 6. Limits of this review

- **Read depth.** The 20 papers in §2 were read past the abstract -- introduction
  plus whichever of method, data, results and conclusion the PDF rendered; depth
  varies (1611.04851, 2608.00127, 2510.05809, 2606.16840 and 2109.10946 were
  read most fully). The remaining medium-relevance rows (332) were read only as
  the sweep's one-line takeaways. Several load-bearing claims (e.g. the
  exact traffic-light thresholds in 1611.04851, the empirical tables in
  2109.10946, 2608.00127 and 2606.16840) were taken from the abstracts and the
  results prose rather than recomputed.
- **Sampling.** Deep reads were chosen from the category's top-60 booklist keyed
  to the eight priority themes; the heavy-tailed-VaR and EVT families are
  over-represented relative to systemic-risk/network papers, which the
  correlation book covers.
- **Repo verification.** Every `Repo surface` symbol was opened with `read` or
  `grep` before its status was asserted. I verified line numbers only for the
  symbols named in §5; the line references there come from the same reads.
- **Not verified.** I did not run tests, backtests or any numerical
  reproduction. Whether these estimators behave as the papers report *on this
  repo's data* is unverified; the §3 steps are proposed changes, not measured
  improvements. Several §3 entries overlap with behaviours deliberately gated
  off (`enable_tail_risk_layer`, `enable_jump_robust_proxies`), so a step may be
  partly implemented behind a flag I did not exercise.
