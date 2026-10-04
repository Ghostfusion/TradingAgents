# Correlation, Networks & Dependence

`book 11/19` · slug `correlation-networks` · 1053 papers in the corpus · 96 rated high-relevance by the sweep

## 0. Scope

This category covers how assets move together: estimation and cleaning of the
correlation/covariance matrix (random-matrix theory, Marchenko-Pastur edge,
linear and nonlinear shrinkage, rotationally invariant estimators), the
eigenvector structure that survives the cleaning, the network topology built
from correlations (MST, PMFG, core-periphery, spectral gap), conditional and
frequency-resolved dependence (DCC, variance-decomposition connectedness),
copulas and tail dependence, and directed/causal links (Granger, Helmholtz-Hodge,
DAG recovery) between financial variables.

It matters to this repo because the allocators in
`tradingagents/strategies/portfolio_optimizer.py` and
`hierarchical_risk_parity.py` all consume a covariance estimate, and because the
repo has already committed to two RMT reads — `covariance_models.py` (R3/V5
spectral movement) and `market_breadth.py::mp_below_count` (X3). The value of
the category is therefore mostly corrective: it says where a sample covariance
is untrustworthy, where an eigenvalue threshold is biased, and which dependence
object (a scalar correlation, an eigengap, a copula tail, a directed graph)
actually carries the information an analyst claims.

## 1. Corpus composition

The sweep annotated **1053** papers into this category (96 high, 609 medium, 348
low); the corpus index files **408** as primary-category. The decade table below
is derived from the **96 high-relevance rows** in the evidence pack (the medium
table only names 100 of 609, so it is not a valid denominator); the top-60
booklist is shown beside it for contrast.

| decade | high-relevance rows | top-60 booklist |
| --- | --- | --- |
| 1990s | 3 | 0 |
| 2000s | 18 | 2 |
| 2010s | 20 | 7 |
| 2020s | 55 | 51 |
| **total** | **96** | **60** |

The category is dominated by two things. First, the classic econophysics line
(1998–2009: Mantegna's minimum spanning tree, Plerou/Stanley GOE statistics,
Laloux/Bouchaud RMT cleaning) which supplies the theoretical spine every later
paper cites or extends. Second, a 2020s surge of deep-learning-on-graphs papers
(GNN/GAT over stock relation graphs) that mostly re-derive known topology with
more parameters; the booklist is 51/60 from the 2020s because relevance scoring
favoured recent work, but the high-relevance facts that survive replication are
overwhelmingly from the older RMT/network core.

## 2. Deep reads

### arXiv 1610.08104v1 — Cleaning large Correlation Matrices: tools from Random Matrix Theory (Bun, Bouchaud, Potters, 2016)

- **Question**: how to estimate a large correlation matrix from a finite sample
  without inverting noise, when the ratio *q = N/T* is not small.
- **Method**: a review of Marchenko-Pastur, the resolvent/Stieltjes transform,
  free probability (R-, S-, Blue-transforms) and Dyson Brownian motion, building
  to the "rotationally invariant estimator" (RIE): keep the sample eigenvectors,
  replace the sample eigenvalues by a nonlinear function of the observable
  spectrum only.
- **Headline**: the optimal nonlinear shrinkage function is *universal* — the
  same function cleans bulk and outlier eigenvalues — and the RIE framework is
  "superior in this case to all previously proposed methods" on financial data.
- **Key property**: the cleaned spectrum is strictly *narrower* than both the
  sample spectrum and the true population spectrum (top eigenvalues shrunk down,
  small ones shrunk up) while preserving the trace; estimating the population
  eigenvalues alone is *not* optimal when the eigenvectors are only partially
  known (Eq. 6.16, Fig. D.2).
- **Limitation**: results are asymptotic in *N, T → ∞* at fixed *q*, assuming no
  prior on the underlying structure; the review says the empirical case is made,
  not proved for finite panels.

### arXiv cond-mat/9902283v1 — Universal and non-universal properties of cross-correlations in financial time series (Plerou et al., 1999)

- **Question**: is the correlation matrix of stock returns distinguishable from
  random-matrix noise?
- **Data**: the largest 1000 US stocks, 1994–95, 30-minute price changes.
- **Method**: eigenvalue density, nearest- and next-nearest-neighbour spacing,
  number variance and spectral rigidity, plus the inverse participation ratio
  *I_k = Σ_l u_kl⁴* of eigenvectors.
- **Headline**: most eigenvalues obey GOE statistics (Wigner surmise spacing,
  number variance ~ ln L); deviations appear only above λ ≈ 1.94.
- **Localization**: large-*I* eigenvectors appear at *both* spectrum edges —
  ~4–5× the mean at the top (groups of ~50 correlated stocks) and up to 0.35 at
  the bottom (a few stocks each) — the signature of a random band matrix.
- **Limitation**: one 2-year window on large caps; no trading or portfolio test.

### arXiv cond-mat/9802256v1 — Hierarchical Structure in Financial Markets (Mantegna, 1998)

- **Question**: is there a meaningful economic taxonomy hidden in pairwise
  correlations?
- **Data**: DJIA and S&P 500 constituents, July 1989 – October 1995, daily log
  differences.
- **Method**: correlation coefficient → metric distance → minimum spanning tree
  → subdominant ultrametric.
- **Headline**: the MST recovers a stable economic taxonomy; the number and
  nature of common factors can be read off the tree's branches.
- **Limitation**: static tree over one multi-year window; the tree is a
  filtering device, not a dynamics or risk model.

### arXiv 0909.1383v3 — Hidden Noise Structure and Random Matrix Models of Stock Correlations (Dimov, Kolm, Maclin, Shiber, 2009)

- **Question**: is the Marchenko-Pastur "noise band" really one homogeneous
  band?
- **Data**: N = 484 S&P 500 2-minute midquote returns (Jun–Sep 2007) and N = 451
  daily returns (2001–2007).
- **Method**: inverse participation ratio by eigenvector, seeded by groups of
  outlier stocks in the top few factors; a coarse-grained block model; a
  one-factor variance-gamma simulation with tail index ν ≈ 3.
- **Headline**: the noise band is **multiple subbands that do not fully mix** —
  upper-edge participation is dominated by weakly correlated small/liquidity
  stocks, lower-edge by strongly correlated sectoral outliers; group degeneracies
  were {46, 61, 377}.
- **Bias result**: flat-band RMT cleaning leaves opposite-signed risks by
  subband (δr = +26% ± 4%, +2% ± 4%, −17% ± 2%) that nearly cancel aggregate
  (δr_all = 2% ± 3%) — a purely *stationary* estimation bias in conventional
  cleaning.
- **Limitation**: separating multiple-band effects from tails and
  non-stationarity in real data is deferred; the block model is deliberately
  minimal.

### arXiv 1308.2608v2 — On the Strong Convergence of the Optimal Linear Shrinkage Estimator for Large Dimensional Covariance Matrix (Bodnar, Gupta, Parolya, 2013)

- **Question**: can the Ledoit-Wolf shrinkage intensity be made distribution-free
  and almost-surely optimal for an *arbitrary* positive-definite target, not just
  the identity?
- **Method**: random-matrix asymptotics with *p/n → c ∈ (0,∞)*; the Stieltjes
  transform of the sample covariance converges to a non-random function solving
  the Marchenko-Pastur equation; the optimal intensities and the Frobenius norm of
  the sample covariance are shown to converge to estimable deterministic limits.
- **Headline**: the resulting estimator obeys the smallest Frobenius loss over
  all linear shrinkage estimators *almost surely*, with weaker moment assumptions
  (4+ε) than Ledoit-Wolf's 8th moment.
- **Limitation**: Frobenius loss is the criterion — not portfolio variance — and
  the target must satisfy uniformly bounded trace norm.

### arXiv 2304.14098v2 — Optimal covariance cleaning for heavy-tailed distributions: insights from information theory (Bongiorno, Berritta, 2023)

- **Question**: is the Frobenius-norm-optimal (Oracle) cleaning still optimal
  when returns are Student-t rather than Gaussian?
- **Method**: compare the minimisers of Frobenius distance and Kullback-Leibler
  information loss for two RIE targets; derive the asymptotic normalized KL for
  multivariate t in the large-*n* limit.
- **Headline**: for Gaussian variables the two targets coincide exactly
  (∂F = ∂KL); for Student-t they **diverge in finite samples**, and the
  divergence vanishes as *n → ∞* or when the tail parameter dominates.
- **Consequence**: RMT cleaning results extend to heavy-tailed data only in the
  large-matrix limit; finite-sample heavy-tail cleaning is targeting the wrong
  loss.
- **Limitation**: closed-form KL for multivariate t remains elusive; the finite
  case is shown numerically (Monte Carlo + SLQP), not analytically.

### arXiv 2112.07521v2 — Non-linear shrinkage of the price return covariance matrix is far from optimal for portfolio optimisation (Bongiorno, Challet, 2021)

- **Question**: does the Frobenius-optimal Oracle eigenvalue correction also
  optimise a Global Minimum Variance portfolio?
- **Method**: solve the GMV objective directly over the RIE eigenvalues as a
  convex quadratic program (Eq. 11–12), and compare the resulting weights against
  the Oracle RIE on 10,000 random portfolios of n = 50 US equities, 1995–2017.
- **Headline**: "the weights from the QP problem are always better than the
  Oracle RIE" — NLS is *not* optimal for GMV because it minimises the wrong cost
  when the dependence structure is non-stationary.
- **When it agrees**: only when calibration and test windows are both very large
  relative to *n* and the two covariance matrices differ only by sampling noise.
- **Limitation**: the QP needs the *out-of-sample* covariance to define its
  optimum, so the result is an upper bound / diagnostic rather than a deployable
  estimator; the paper reopens the estimator question rather than closing it.

### arXiv 2305.12632v2 — Deformation of Marchenko-Pastur distribution for the correlated time series (Hisakado, Kaneko, 2023/24)

- **Question**: what happens to the Marchenko-Pastur law when the returns are
  serially (temporally) correlated?
- **Method**: Wishart matrix built from one product's series with a Toeplitz
  temporal-correlation matrix, exponential and power decay; moment computation
  and finite-size scaling; fBm simulation.
- **Headline**: with temporal correlation the eigenvalue density converges to a
  **deformed MP** with a *fatter tail and higher peak*; the mean is invariant
  (µ₁ = 1) but the second moment rises with the correlation — µ₂ = 1 + 1/Q +
  Σᵢ dᵢ²/Q.
- **Phase transition**: for power-law decay dᵢ ~ i^−γ, the second moment and the
  largest eigenvalue are finite for γ > 1/2 and *infinite* for γ ≤ 1/2.
- **Empirical hook**: FX pairs with |lag-1 autocorrelation| ≥ 0.2 (USD/CAD,
  EUR/CHF, USD/CNH) fail the MP fit; soybean, VIX and NKY225 (|ρ₁| ≤ 0.08) fit.
- **Limitation**: single-product Wishart construction; the phase exponent is
  estimated numerically.

### arXiv 1111.1113v2 — Copula-based Hierarchical Aggregation of Correlated Risks (Bruneton, 2011)

- **Question**: how much does a risk-aggregation *tree* shape the diversification
  benefit when dependencies are set by copulas at each node?
- **Method**: formalise regular (k,m) trees with k-dimensional copulas at each
  aggregation; solve the Gaussian tree exactly for xTVaR, then extend to
  LogNormal; define diversification factor and benefit.
- **Headline**: for a fixed number of leaves, **"thin" trees diversify better
  than "fat" trees**; hierarchical trees *systematically lower* the overall
  dependency relative to the dependency parameter chosen at each step.
- **Second result**: the hierarchical mechanism does not require the full joint
  distribution, but the joint can be recovered exactly (Gaussian case) by adding
  conditional-independence assumptions.
- **Limitation**: regular equicorrelation trees; results are for TVaR-type
  coherent measures, not portfolio variance.

### arXiv 1507.01729v4 — Measuring the frequency dynamics of financial connectedness and systemic risk (Baruník, Křehlík, 2015/17)

- **Question**: connectedness aggregated over all horizons hides whether a shock
  transmits fast or slow — can it be measured per frequency band?
- **Method**: spectral representation of the generalized forecast-error variance
  decomposition (GFEVD) from a VAR; Fourier transform of the impulse responses
  yields per-band shares; local (rolling-window) estimation.
- **Data/headline**: main US financial institutions; total connectedness ranges
  55%–85% over 16 years, peaking in 2008 and at the 2012 European-debt peak and
  falling after Draghi's "whatever it takes".
- **Bands**: short (1–5 days), medium (5–20 days), long (20–300 days); high-
  frequency connectedness marks calm, rapid information processing; low-frequency
  marks persistent transmission.
- **Result**: contemporaneous correlation and connectedness are *not* the same —
  high cross-correlation during crises (Forbes–Rigobon) can bias contagion
  estimates.
- **Limitation**: VAR-based, so dependent on lag order and the generalized
  identification; results are descriptive system measurements, not forecasts.

### arXiv 2502.15458v2 — Clustered Network Connectedness: A New Measurement Framework (Buchwalter, Diebold, Yilmaz, 2025)

- **Question**: full orthogonalization (Sims) and no orthogonalization
  (Koop-Pesaran-Potter-Shin) are two extreme identification schemes; what lies
  between?
- **Method**: let nodes form "clusters" (asset class, industry, region); impose
  **orthogonal shocks across clusters but correlated shocks within clusters**;
  ordering is then relevant across clusters and irrelevant within.
- **Headline**: a general connectedness framework that nests both extremes;
  applied to sixteen country equity markets across three global regions.
- **Practical consequence**: centrality/spillover rankings become
  cluster-conditional — the same node can be central or peripheral depending on
  the assumed shock structure.
- **Limitation**: identification still requires an exogenous cluster ordering;
  the framework measures, it does not test which clustering is correct.

### arXiv 2408.12839v1 — Causal Hierarchy in the Financial Market Network — uncovered by the Helmholtz-Hodge-Kodaira Decomposition (Wand, Kamps, Iyetomi, 2024)

- **Question**: a Granger-causality network is full of cycles and hard to read;
  can it be given a direction hierarchy?
- **Method**: restricted conditional Granger causality (RCGCI) with BIC-selected
  sparse lags on 49 Ken French business-sector returns; PCA-noise filtering;
  Helmholtz-Hodge-Kodaira decomposition of the antisymmetric flow into a gradient
  (potential) field plus a divergence-free (rotational) field.
- **Headline**: during Covid, **precious metals and pharmaceuticals are causal
  drivers** of the financial network; Granger-network connectivity is high during
  crises.
- **Result**: the gradient component ranks nodes upstream/downstream — a causal
  hierarchy no raw correlation or pairwise test provides.
- **Limitation**: lag-1 linear Granger causality only; sector portfolios, not
  single names; "causality" is predictive precedence, not intervention.

### arXiv 2504.15268v17 — Causal Discovery via Simultaneous DAG Recovery Using the Angles Space of Directional Dependence Measures (Opdyke, 2025)

- **Question**: constraint- and score-based DAG learners are sequential/iterative
  and unstable; can the whole DAG be recovered in one shot?
- **Method**: "Angles-based Directional Dependence" (ADD) — compute two all-pairwise
  directional-dependence matrices (one per direction), place significant
  directional dependence in the angles space of a positive-definite measure,
  derive empirical confidence bounds by simulation, then enforce acyclicity.
- **Headline**: only two matrix estimations and two simulations are needed
  regardless of DAG size, giving better coherence, adaptivity across dependence
  measures (Pearson, Spearman, Kendall, tail-dependence, Chatterjee's ξ), and
  speed.
- **Caveat**: the paper calls the empirical study "preliminary", on nonlinear,
  asymmetric, heavy-tailed synthetic data, and explicitly defers benchmarking
  against NOTEARS, LiNGAM, PC/GES.
- **Limitation**: assumes acyclicity, causal sufficiency, faithfulness,
  i.i.d. sampling and a monotone link from dependence to asymmetry; positive
  definiteness of the chosen directional measure is required and not proven for
  several candidates.

### arXiv 2308.05564v4 — Large Skew-t Copula Models and Asymmetric Dependence in Intraday Equity Returns (Deng, Smith, Maneesoonthorn, 2024)

- **Question**: correlation alone cannot express that dependence differs across
  quantiles and is stronger in the tails; can a high-dimensional skew-t copula be
  estimated fast enough to use?
- **Method**: Azzalini-Capitanio skew-t factor copula with up to 15 factors,
  fitted by Bayesian variational inference with a stochastic-gradient-ascent
  algorithm; 93 US equities, intraday returns 2017–2021, moving windows.
- **Headline**: the copula captures "substantial heterogeneity in asymmetric
  dependence over equity pairs" *on top of* pairwise-correlation variability; the
  asymmetric dependencies vary over time and are more accurate in intraday
  predictive densities than benchmark copulas.
- **Economic result**: portfolio-selection strategies built on the estimated
  **pairwise asymmetric dependencies improve performance relative to the index**.
- **Limitation**: computational cost grows with the factor count; benchmarks are
  other copulas, not a tradable live book.

### arXiv 2607.10297v1 — Recovering Structural Organization in Noisy Correlation Networks Using Financial Systems as a Testbed (Ansari, Jain, Iyer, 2026)

- **Question**: does the structured (above-MP) part of a correlation matrix carry
  the *network topology*, and does that topology have economic value?
- **Method**: split the correlation matrix into eigenmodes above vs below the
  Marchenko-Pastur bounds; build full/structured/random networks; measure
  core-periphery organisation by a Markov-chain persistence algorithm; NIFTY 200,
  NIFTY 500, S&P 500 daily returns 2010–2022.
- **Headline**: only 10–16 eigenmodes reproduce the principal statistical
  properties of the full matrix; the structured network has significantly
  stronger and more stable core-periphery organisation; Indian structured
  networks are scale-free while random ones are not.
- **Economic result**: portfolios of **peripheral assets of the denoised network**
  achieve consistently higher risk-adjusted performance than unfiltered
  correlation or benchmarks, robust to Monte Carlo subsampling.
- **Limitation**: structural separation relies on MP bounds, which assume i.i.d.
  noise; core-periphery detection is one algorithmic family.

### arXiv 2405.12993v1 — A novel portfolio construction strategy based on the core-periphery profile of stocks (Ansari, Sharma, Agrawal, Sahni, 2024)

- **Question**: does mesoscale network structure beat local centrality for
  portfolio selection?
- **Method**: build correlation networks, filter with a Planar Maximally Filtered
  Graph (PMFG), extract the core-periphery profile per the Markov-chain
  persistence method, and compare periphery vs centrality portfolios by Sharpe
  ratio on NSE data (high-frequency and daily).
- **Headline**: "portfolios constructed from stocks within the periphery segment
  of the PMFG subgraph exhibit superiority" over centrality-based strategies in
  Sharpe ratio, returns and volatility; the periphery part from persistence
  probabilities beats the core-score periphery.
- **Robustness**: 77% of 686 two-hour windows (2014 CNX100) show a significant
  core-periphery profile at 5%; core stocks are stable (financials, metals,
  chemicals) while periphery names rotate.
- **Limitation**: Indian single-market, single-year windows; PMFG construction is
  O(N) edges and not scale-free; no transaction costs.

### arXiv 2608.10788v1 — The Triadic Stress Index in Financial Markets (Acedo, 2026)

- **Question**: can a domain-agnostic network quantity (closed-triangle count,
  density, inverse spectral gap, degree variance) register systemic stress in a
  correlation network better than spectral measures?
- **Method**: A = |ρ|, TSI = (C·D/M)·Coex with C = normalised Tr(A³), D = density,
  M = 1/λ₂, Coex = Var(degree); per-node attribution diag(A³); asymmetric
  persistence filter; five markets, 2006–2026, F1@90th-percentile against
  labelled crises with block bootstrap.
- **Headline**: TSI beats the Absorption Ratio out-of-sample by ΔF1 = 0.219
  (95% CI [0.070, 0.410], p < 0.0005) but **ties the sharper spectral baselines**
  (effective rank / Vendi score, 0.447 vs 0.377, interval includes zero); alarms
  are the cleanest of anything tested.
- **Attribution**: diag(A³) is parameter-free and flat (0.975–0.994) across one to
  four epicentres, while a fixed spectral k = 2 loses ~a quarter of accuracy and
  the Kaiser rule (k ≈ 5.87) collapses to ~0; but an **MP-edge adaptive k ties
  the triangle rule everywhere** — the value is robustness, not resolution.
- **Register**: lead-lag analysis peaks at zero lag — TSI is **coincident, not
  leading**; the paper also reports that on real matrices simple node degree
  gives the same attribution.
- **Limitation**: cross-sectional size not comparable (raw TSI scales with n);
  a scale-normalised variant scored *below chance*, i.e. much of TSI is the
  correlation *level*; evidence for attribution is synthetic.

### arXiv 2608.20020v1 — The Reconfiguration Premium: Co-movement Structure as an Unspanned Dimension of the Variance Risk Premium (Carvalho, 2026)

- **Question**: every priced co-movement measure is a function of the correlation
  *eigenvalues*; is the *eigenvector* motion separately priced?
- **Method**: REC = mean squared sine of the principal angles between the
  subdominant eigenspaces of consecutive twelve-month S&P 500 correlation
  matrices (market mode removed), 1995–2025; regress the log variance risk
  premium on REC with level controls and Newey-West(12) / simulation-based
  inference.
- **Headline**: REC couples to the aggregate VRP at **t = 5.40**; no level
  measure correlates above 0.32 and the implied-correlation surface spans only
  5.0–6.7% of it. A typical month rewrites ~a fifth of the structure.
- **Anatomy**: only the **persistent** component is priced (three-month average
  t = 5.40, monthly innovation t = 0.30); the mechanism is prepayment — implied
  variance rises on impact while realized volatility arrives two to three
  quarters later, then the premium converges.
- **Validity**: modes two and three sit above the refitted MP edge in essentially
  every window; the Davis-Kahan degradation channel bounds at 12.1% of the
  index's variance.
- **Limitation**: the VRP convention is non-standard (one-month implied vs
  twelve-month equal-weighted realized); the panel is survivor-tilted; the paper
  reports no timing alpha and no crash protection — it is state measurement, not
  a strategy.

## 3. Learnings applicable to this repo

### L1. Prefer a rotationally invariant (nonlinear-shrinkage) estimator over linear shrinkage alone

- **Source**: `arXiv 1610.08104` (2016) — Cleaning large Correlation Matrices.
- **Finding**: the optimal eigenvalue cleaning keeps the sample eigenvectors and
  applies a *universal* nonlinear shrinkage driven only by the sample Stieltjes
  transform; it dominates all earlier proposed cleaning methods on financial
  data, strictly narrows the spectrum versus both sample and truth, and preserves
  the trace. Estimating population eigenvalues while keeping noisy eigenvectors
  is provably sub-optimal.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink`
  (linear shrinkage toward `mu*I` or `diag(S)` only).
- **Status**: `partial` — the module header and `__all__` show linear shrinkage is
  the only eigenvalue-targeting cleaner; no nonlinear/RIE estimator exists.
- **Concrete step**: add an `rie_clean` read beside `ledoit_wolf_shrink` that
  consumes the same `_aligned_matrix` output and returns a cleaned `cov`, the
  per-eigenvalue shrinkage applied, and the trace check, so
  `portfolio_optimizer._covariance_matrix` can choose it.

### L2. The MP "noise band" is not homogeneous — report subband structure, not a flat count

- **Source**: `arXiv 0909.1383` (2009) — Hidden Noise Structure and Random Matrix
  Models of Stock Correlations.
- **Finding**: the eigenvalues below the MP lower edge split into *multiple
  subbands that do not mix* (upper edge = weakly correlated liquidity/small-cap
  names, lower edge = sectoral outliers); flat-band cleaning leaves opposite-signed
  risks by subband (+26% vs −17%) that nearly cancel in aggregate (2%), a purely
  stationary estimation bias.
- **Repo surface**: `tradingagents/strategies/market_breadth.py::mp_below_count`
  (counts eigenvalues below the lower edge) and
  `tradingagents/strategies/eigen_rotation.py::eigen_rotation` (reads the
  subdominant block as one homogeneous block).
- **Status**: `partial` — the repo measures and guards the edge but treats the
  below-edge spectrum as one undifferentiated set.
- **Concrete step**: have `mp_below_count` additionally return the subband
  partition (contiguous eigenvalue clusters / inverse-participation groups) so a
  single-count risk read is not mistaken for a homogeneous-noise read.

### L3. Frobenius-optimal cleaning is not portfolio-optimal under non-stationary dependence

- **Source**: `arXiv 2112.07521` (2021) — Nonlinear shrinkage is far from optimal
  for portfolio optimisation.
- **Finding**: solving the GMV objective directly over RIE eigenvalues beats the
  Frobenius-optimal Oracle RIE on 10,000 random n = 50 portfolios — "always
  better" — because NLS minimises the wrong cost when the dependence structure
  changes between calibration and test windows.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py::min_variance_weights`
  and `::_covariance_matrix` (raw sample covariance; no eigenvalue cleaning).
- **Status**: `absent` — the repo builds covariance-based portfolios from the
  sample covariance and has no GMV-optimal eigenvalue read.
- **Concrete step**: document in `min_variance_weights` that its covariance is
  uncleaned, and (optionally, behind a gate) add a diagnostic that solves the
  GMV-over-eigenvalues QP of the paper's Eq. 11 to measure how far the sample
  estimator is from the portfolio-optimal one.

### L4. Under heavy tails the Frobenius and information (KL) targets diverge

- **Source**: `arXiv 2304.14098` (2023) — Optimal covariance cleaning for
  heavy-tailed distributions.
- **Finding**: for Gaussian variables the Frobenius-minimising and KL-minimising
  RIE eigenvalues coincide; for Student-t they diverge in finite samples and the
  divergence vanishes only as the matrix grows — so finite-sample RMT cleaning of
  fat-tailed returns targets the wrong loss.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink`
  (Frobenius-style intensity) and `tradingagents/strategies/tail_risk.py::tail_risk`
  (already models fat tails elsewhere).
- **Status**: `absent` — no KL-based target and no heavy-tail flag on the
  covariance read.
- **Concrete step**: add an information-loss diagnostic option to
  `ledoit_wolf_shrink` that reports the estimated tail index and flags when
  finite-sample divergence is material, rather than silently assuming Gaussian.

### L5. Generalise the shrinkage target beyond scaled identity / diagonal

- **Source**: `arXiv 1308.2608` (2013) — Strong convergence of the optimal linear
  shrinkage estimator.
- **Finding**: the Ledoit-Wolf intensities extend to *any* symmetric positive-definite
  target with bounded trace norm; the estimator then obeys the smallest Frobenius
  loss over all linear shrinkage estimators almost surely, under only 4+ε moments
  and with no distributional assumption.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ledoit_wolf_shrink`.
- **Status**: `partial` — only `target="scaled_identity"` and `target="diag"` are
  supported; no data-derived or factor-model target.
- **Concrete step**: accept a caller-supplied positive-definite target matrix in
  `ledoit_wolf_shrink` and compute the RMT-consistent intensity against it, so a
  factor-model or EWMA target can be shrunk toward.

### L6. Eigenvector rotation is a priced, *coincident* state — surface it as a state, never a signal

- **Source**: `arXiv 2608.20020` (2026) — The Reconfiguration Premium.
- **Finding**: the mean squared sine of principal angles between consecutive
  subdominant eigenspaces (market mode removed) couples to the aggregate variance
  risk premium at t = 5.40 and is largely unspanned by option-implied correlation;
  only its persistent component is priced. It is a *state* variable, not a timing
  signal (no timing alpha, no crash protection).
- **Repo surface**: `tradingagents/strategies/eigen_rotation.py::eigen_rotation`
  (V5, returns `rec` and `angles`; gated by `enable_eigen_rotation`).
- **Status**: `shipped` — the measurement already exists and is explicitly
  labelled "a state, not a signal".
- **Concrete step**: expose `rec` (and the R3 `spectral_functionals` rotation
  block) to the news/market analyst as a state read alongside the VRP-adjacent
  reads, keeping the coincident, direction-blind label; no new maths.

### L7. A fixed eigenvector count is a silent cost — derive k from the MP edge

- **Source**: `arXiv 2608.10788` (2026) — The Triadic Stress Index in Financial
  Markets.
- **Finding**: node attribution from a fixed spectral k = 2 loses ~a quarter of
  its accuracy when the true number of epicentres differs, and the equally
  standard Kaiser rule (k ≈ 5.87) collapses; an adaptive k chosen at the
  Marchenko-Pastur edge ties the parameter-free triangle rule in every regime.
  Parameter-free attribution (diag(A³)) is flat across regimes for exactly this
  reason.
- **Repo surface**: `tradingagents/strategies/eigen_rotation.py::SUBSPACE_MODES`
  (hard-coded 3) and `tradingagents/strategies/triadic_stress.py::triadic_stress`
  (parameter-free diag(A³) attribution, `EPICENTRE_CUT`).
- **Status**: `partial` — TSI's attribution is parameter-free and shipped, but
  `eigen_rotation` fixes its mode count at 3 with no adaptive rule.
- **Concrete step**: report the MP-edge eigenvalue count (from
  `market_breadth.mp_below_count`) beside `eigen_rotation`'s fixed-block `rec`,
  so a caller can see whether the tracked block is inside the bulk; keep 3 as the
  default but make it overridable from the edge count.

### L8. Peripheral-asset portfolios beat centrality portfolios, after spectral denoising

- **Source**: `arXiv 2405.12993` (2024) and `arXiv 2607.10297` (2026).
- **Finding**: portfolios built from the *periphery* of a filtered correlation
  network (PMFG; or the above-MP structured component) consistently outperform
  centrality-based and unfiltered-correlation portfolios in Sharpe ratio, across
  Indian and US markets and both daily and intraday windows; core-periphery
  organisation is statistically significant in 77% of 686 windows.
- **Repo surface**: `tradingagents/strategies/portfolio_optimizer.py`
  (risk-parity / min-variance / max-diversification) and
  `tradingagents/strategies/hierarchical_risk_parity.py::hrp_weights`.
- **Status**: `absent` — neither module builds a core-periphery profile or a
  periphery-tilted book.
- **Concrete step**: add a `core_periphery_weights` read: build the correlation
  network (PMFG or above-MP structured), compute the Markov-chain persistence
  profile, and weight the periphery; compare against `hrp_weights` on the same
  panel.

### L9. Tree shape systematically changes the diversification benefit

- **Source**: `arXiv cond-mat/9802256` (1998) — Hierarchical Structure in
  Financial Markets; `arXiv 1111.1113` (2011) — Copula-based Hierarchical
  Aggregation.
- **Finding**: the correlation MST recovers a stable economic taxonomy
  (Mantegna); and for a fixed number of leaves, copula-aggregated *thin* trees
  diversify better than *fat* trees, while hierarchical aggregation
  systematically lowers the overall dependency relative to the per-step
  parameter.
- **Repo surface**: `tradingagents/strategies/hierarchical_risk_parity.py::hrp_weights`
  (single-linkage clustering + quasi-diagonalization; no tree-shape reporting).
- **Status**: `partial` — HRP clusters and bisects but does not report the tree
  shape or the diversification effect of the linkage choice.
- **Concrete step**: return the linkage tree's depth/branching summary from
  `hrp_weights` and (as a diagnostic) the same weights under average/complete
  linkage, so the sensitivity to tree shape is visible rather than implicit.

### L10. Frequency-resolve connectedness, not just contemporaneous correlation

- **Source**: `arXiv 1507.01729` (2015) — Measuring the frequency dynamics of
  financial connectedness.
- **Finding**: the spectral representation of a VAR's generalized forecast-error
  variance decomposition yields connectedness per frequency band; total US
  financial-institution connectedness runs 55–85% and peaks in crises, but the
  *band* carrying it changes — high-frequency connectedness marks calm,
  fast information processing, low-frequency marks persistent transmission.
  Contemporaneous correlation during crises can bias contagion estimates.
- **Repo surface**: `tradingagents/strategies/statistical.py::granger_causality`
  (time-domain pairwise F-test) and
  `tradingagents/strategies/breadth_depth.py::average_pairwise_correlation`
  (single scalar correlation spike).
- **Status**: `absent` — no spectral variance-decomposition connectedness read.
- **Concrete step**: add a rolling spectral-GFEVD read (short/medium/long bands)
  over the run's panel, returning per-band total connectedness with the band edges
  reported, next to `average_pairwise_correlation`.

### L11. Shock identification can be cluster-structured, not all-or-nothing

- **Source**: `arXiv 2502.15458` (2025) — Clustered Network Connectedness.
- **Finding**: connectedness measures sit between full orthogonalization (Sims)
  and none (generalized); assuming orthogonal shocks *across* clusters
  (industry/region/asset class) but correlated shocks *within* clusters nests both
  extremes, and makes ordering relevant across but not within clusters. Applied to
  sixteen country equity markets.
- **Repo surface**: `tradingagents/strategies/statistical.py` (has
  `correlation_matrix`, `granger_causality`) — no variance-decomposition
  connectedness at all.
- **Status**: `absent`.
- **Concrete step**: implement the clustered GFEVD on top of a sector/industry
  partition the repo already has (`peer_universe`, `sector_*`), returning
  spillover tables under the clustered identification.

### L12. Turn a Granger network into a directed hierarchy

- **Source**: `arXiv 2408.12839` (2024) — Causal Hierarchy in the Financial
  Market Network.
- **Finding**: restricted conditional Granger causality with BIC-selected sparse
  lags produces a directed network that is cyclic and unreadable; the
  Helmholtz-Hodge-Kodaira decomposition splits its flow into a gradient field
  (giving an upstream→downstream node ranking) and a rotational field. During
  Covid, precious metals and pharmaceuticals ranked as causal drivers.
- **Repo surface**: `tradingagents/strategies/statistical.py::granger_causality`
  (pairwise `x_causes_y` F-test only).
- **Status**: `partial` — pairwise directed tests exist; no network assembly and
  no decomposition.
- **Concrete step**: assemble the pairwise `granger_causality` results into an
  antisymmetric flow matrix over the run's names and add a gradient-potential
  ranking, so a "driver vs driven" claim has a computed source.

### L13. Tail dependence is asymmetric and extra to correlation

- **Source**: `arXiv 2308.05564` (2024) — Large Skew-t Copula Models and
  Asymmetric Dependence in Intraday Equity Returns.
- **Finding**: a skew-t factor copula over 93 US equities captures substantial
  heterogeneity in *asymmetric* dependence beyond pairwise-correlation
  variability, and it varies over time; portfolio selection built on the
  estimated pairwise asymmetric dependencies improves performance relative to the
  index.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::ewma_covariance`
  / `ledoit_wolf_shrink` (linear/Gaussian dependence) and
  `tradingagents/strategies/tail_risk.py::tail_risk` (univariate tails).
- **Status**: `absent` — the repo's dependence reads are all linear correlation;
  it has no tail-dependence or asymmetric-dependence measure.
- **Concrete step**: add a pairwise (upper/lower) tail-dependence read over the
  same aligned panel — a simpler, testable first step before a full skew-t
  copula — and report it beside `correlation_matrix`, so diversification claims
  that fail in the tails are visible.

## 4. Where this repo is already ahead of the literature

- **A calibrated null band on spectral movement.**
  `covariance_models.py::spectral_null_band` / `spectral_functionals` (R3,
  2607.06373) report the absorption-ratio and leading-share moves *against a
  first-order null band calibrated from window length and shrinkage intensity*,
  and a non-rejection reads `"not detectable"` — not `"no change"`. The
  descriptive RMT literature typically reports the absorption ratio with no
  sampling band at all.
- **A refusenik MP guard on eigenspace rotation.**
  `eigen_rotation.py::eigen_rotation` refuses to report a rotation unless the
  *entire* subdominant block sits below the MP lower edge (the conservative
  sufficient condition) and the block is a genuine market-mode-plus-3 subspace.
  The literature usually clips at the *upper* edge of the top eigenvalues; this
  repo's rule is stricter and fails closed.
- **A zero band is a refusal, not a licence.** `covariance_models.py::_band_refusal`
  refuses rather than flagging every move when shrinkage has driven the sampling
  noise to zero — a discipline the paper's own framing supports ("non-rejections
  partly reflect wide null bands").
- **Parameter-free, coincident systemic-stress attribution.**
  `triadic_stress.py::triadic_stress` ships `diag(A³)` node attribution with no
  *k* to select and labels every reading `COINCIDENT` — matching the TSI paper's
  best property while avoiding the *k*-selection failure mode it documents.
- **Inversion-free, degradation-safe allocation.** `hrp_weights` avoids
  inverting the covariance matrix and degrades to equal weight with a note;
  `portfolio_optimizer` refuses to invert a singular matrix rather than emitting
  garbage weights.

## 5. Defects or risks the literature exposes

1. **Possible stale or incomplete Ledoit-Wolf correction.**
   `tradingagents/strategies/covariance_models.py:445` (docstring of
   `_engine_shrinkage`) states that "on every panel this engine's estimator has
   been asked about the intensity saturates at `1.0` (its `b^2` is a per-row
   residual rather than the textbook beta)", yet the module header
   (`covariance_models.py:9-16`) documents that the missing `/t` was corrected on
   2026-09-27 so the intensity is no longer `t` times too large. One of these is
   wrong: either the estimator still saturates (the correction is incomplete) or
   the docstring is stale and misleads a future caller. `arXiv 1308.2608` gives
   the textbook intensity that resolves which. **Action for parent: reconcile the
   comment against the implementation and re-measure.**

2. **The Marchenko-Pastur edge assumes i.i.d. returns.**
   `tradingagents/strategies/market_breadth.py:102` sets the lower edge to
   `(1 - sqrt(n/w))²` and `tradingagents/strategies/eigen_rotation.py:155-161`
   consumes `mp_lower` to decide whether the subdominant block is signal or
   noise. `arXiv 2305.12632` shows temporal correlation deforms the MP density
   (fatter tail, higher peak; largest eigenvalue *infinite* when the power-decay
   index γ ≤ 1/2), and `arXiv 0909.1383` shows heavy tails localise edge
   eigenvectors and split the band. The repo's own `MP-lower-count` therefore
   counts a boundary that is biased when returns are autocorrelated or fat-tailed.
   **Action for parent: gate/report an autocorrelation or tail check before
   trusting the X3/V5 edges on high-frequency or thin panels.**

3. **Fixed subdominant-block size in the rotation read.**
   `tradingagents/strategies/eigen_rotation.py:40` hard-codes `SUBSPACE_MODES = 3`.
   `arXiv 2608.10788` quantifies the cost of a mis-specified *k* in the adjacent
   attribution problem (fixed k = 2 loses ~25% of accuracy; the Kaiser rule
   collapses) while showing an MP-edge adaptive k ties the best methods. The
   rotation read's choice of 3 is likewise a parameter with no shown
   sensitivity. **Action for parent: expose the mode count and report the MP-edge
   count beside it.**

## 6. Limits of this review

- **Sampled, not exhaustive.** The category holds 1053 papers; I read 16 in full
  text (abstract + introduction + method + results), chosen for the priority
  themes. The remaining 1037 are known only through the sweep's one-line rows.
- **RMT and networks dominate the deep reads.** Deep-learning-on-graph papers
  (GNN/GAT over stock relation graphs) are numerous in the 2020s but were read at
  abstract level only; they mostly re-derive topology and were not the highest
  information-per-page for this repo.
- **Copulas and DAG discovery are under-sampled.** I read one skew-t copula paper
  and one DAG-recovery paper; the copula family (vine, Bernstein, CoVaR) and the
  causal-discovery literature (NOTEARS, LiNGAM, PC/GES) are much larger, and my
  §3 entries there are therefore the weakest — they name a first testable step,
  not a settled method.
- **No code was run.** Every `status` was verified by reading the named module,
  not by executing it; the LW reconciliation in §5 is a documentation-level
  contradiction I could not settle without running the estimator.
- **The "high relevance" list is uncalibrated reviewer judgement** (per the
  corpus README, the high-fraction ranges ~2%–36% across slices); I used it as a
  lead list, not a ranking, and re-judged relevance myself in §3.
