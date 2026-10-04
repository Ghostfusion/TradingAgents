# Other / Unclassified

`book 19/19` · slug `other` · 269 papers in the corpus · 5 rated high-relevance by the sweep

## 0. Scope

The residue: 269 papers (of 4,372) that the abstract classifier could not place
in a named category — dense enough to matter, heterogeneous enough that no single
theme dominates. It is overwhelmingly (≈70%) econophysics and physical-statistics
work on financial time series plus a set of q-fin.ST descriptive studies, with a
thin admissible layer of statistical-methodology and ML papers. Most of it is not
actionable for this repo: it is single-market curve-fitting, distributional
taxonomy, or wealth-inequality physics. What survives is a handful of
position-sizing, correlation-estimation, technical-indicator and
calibration results that touch real `tradingagents/strategies/` surfaces — and a
re-homing problem, because several genuinely relevant papers were misclassified
into this bucket.

## 1. Corpus composition

Counts are from `evidence/other.md` (269 annotated rows: 5 high,
78 medium, 186 low) cross-joined against arXiv `primary_category` in
`E:/fin paper/.state/metadata.jsonl`; the 60-paper `booklists/other.json` is used
for the deep-read shortlist.

| primary_category | n | share | primary_category | n |
| --- | ---: | ---: | --- | ---: |
| q-fin.ST | 113 | 42.0% | q-fin.RM | 5 |
| cond-mat.stat-mech | 32 | 11.9% | cs.LG | 5 |
| physics.soc-ph | 29 | 10.8% | q-fin.TR / q-fin.PM / stat.AP | 4 each |
| q-fin.GN | 20 | 7.4% | cond-mat.dis-nn / q-fin.PR | 3 each |
| physics.data-an | 10 | 3.7% | all others (17 cats) | 1–2 each |
| stat.ME / math.PR | 6 each | 2.2% each | | |

| decade | n |
| --- | ---: |
| 1990s | 6 |
| 2000s | 87 |
| 2010s | 110 |
| 2020s | 66 |

The category is dominated by **q-fin.ST** (113, 42%) — descriptive
statistical-finance studies — glued to a large physical-statistics block
(`cond-mat.stat-mech` 32 + `physics.soc-ph` 29 + `physics.data-an` 10 = 71, 26%).
The modal paper is a single-index or single-market distributional study (tail
exponents, σ-stable fits, Gini/Pareto wealth curves, correlation-matrix
eigenstructure) from 2000–2015. The center of mass is 2010s (110) with a long
2000s tail (87); only 66 are 2020s. Neither half of the block is a market-data
strategy library: it is measurement of markets, not machinery for acting on them.

## 2. Deep reads

### arXiv 2607.28230v2 (2026) — Boundary-Induced Apparent Risk Aversion in Nonergodic Multiplicative Growth
- **Question**: does a finite absorbing continuation threshold change the ex-ante
  growth-optimal fixed exposure, and does ignoring it look like risk aversion?
- **Data/method**: finite-horizon binary multiplicative lattice,
  `W_{t+1}=W_t(1+fR_t)` with `R=+b/-a`, lower absorbing boundary at `L`, residual
  value `S=rho*L` after absorption; exact lattice probability propagation (no
  Monte Carlo), objective `max E[log W_T]`.
- **Finding**: with a costly boundary (`rho=0.1`) the optimal exposure is
  *compressed below* the no-boundary Kelly fraction near the boundary
  (`f_K=2p-1=0.10` at `p=0.55`), approaching it as `d=log(W0/L)` grows; mapped into
  an unconstrained CRRA coefficient the compression "rises sharply" — i.e. a
  boundary geometry masquerades as state-dependent risk aversion. With shallow
  residual loss (`rho→1`) a *local above-Kelly reversal* appears.
- **Limitation**: fixed ex-ante exposure (not a feedback policy); discrete
  finite-horizon lattice gives no strict pointwise monotonicity; the CRRA mapping
  is a representational diagnostic, explicitly not a preference measurement.

### arXiv 2603.13632v1 (2026) — Betting Around the Clock: Time Change and Long Term Model Risk
- **Question**: does the Kelly rule still maximize average growth when returns are
  a time-changed (subordinated) semi-martingale?
- **Data/method**: theory — `R_i = exp(s_i Z_i dt)` with `Z` an i.i.d.
  subordinator; geometric average becomes a Kolmogorov/`psi^{-1}` average where
  `psi` is the clock's moment generating function; worked against a Variance-Gamma
  (gamma clock) case, reusing Rotando–Thorp (1992) framing.
- **Finding**: Kelly is optimal **only if gross returns are log-normal**; under a
  stochastic clock the Kelly position is *too large* and a less aggressive
  investment earns a higher average growth. Failure grows with stochastic-clock
  variance; the Thorp (1969) ruin threshold is closer but examples put Kelly
  "safely in the ruin-free region".
- **Limitation**: theory-first; the variance-clock estimates are borrowed from the
  literature rather than fitted here; no out-of-sample trading evaluation.

### arXiv 2001.04237v1 (2020, stat.OT) — Exponential Moving Average versus Moving Exponential Average
- **Question**: what do EMA and MACD actually compute, rigorously?
- **Method**: formal definitions of a weighted/recursive "average"; shows the EMA is
  a recursive weighted average (weights `alpha(1-alpha)^i`, not a sliding-window
  mean), defines the "moving exponential average" properly, and gives the MACD as
  `E^{12}(c) - E^{26}(c)` with a 9-day EMA signal line.
- **Finding**: a precise algebraic relation between averages, moving averages and
  the EMA; MACD is a **trend follower** whose signal always appears *after* the
  extremum. With small `N` and range-bound closes it emits "unnecessary" buy/sell
  signals; ADX/RSI are suggested to filter them.
- **Limitation**: pedagogical/expository (Math. Semesterber. 2011), illustrated on
  a single 2008–2009 window; no backtest, no statistical significance.

### arXiv 2010.01157v1 (2020) — Gold Standard Pairs Trading Rules: Are They Valid?
- **Question**: do the canonical distance/cointegration pairs-trading rules still
  work on modern US equities?
- **Data/method**: NYSE daily, ~2,800 stocks, 1990-01-01 → 2020-06-01 including
  Covid; distance and Engle-Granger cointegration formation, 2-sigma entry, zero
  exit, one-period execution lag; 35→26 bps one-way costs, 0.6% p.a. short fee;
  full hyperparameter grid (pairs, threshold, period multiplier, coint level).
- **Finding**: base parameters **fail to beat the market** over 1990–2020
  (<0.2%/month vs market 0.47%), even after tuning; but the strategy earns
  ~+2%/month excess in bear markets and lags ~1% behind the market in bull
  markets. Market factors strongly relate to the *optimal* parameterization.
- **Limitation**: bear/bull split "utilizes significant foresight bias" — knowing
  bear-market start/end ex ante is not tradable; distance and cointegration only;
  no GARCH/copula/ML variants.

### arXiv 0802.0984v2 (2011, q-fin.ST) — Moving Mini-Max — a new indicator for technical analysis
- **Question**: can local price maxima/minima be located in one pass with inherent
  smoothing instead of a pre-smoothing filter?
- **Data/method**: an algorithm borrowed from nuclear γ-ray spectroscopy (Gamow
  tunneling analogue): a Markov chain over bars with tunneling probabilities
  `Q_{i,i±1} = exp(Σ_k (S_{i±k}-S_i)^2 / (S_{i±k}+S_i))`, recursively normalized
  to a `u(S)_i ∈ [0,1]` series; a sign-flipped variant `d(S)_i` emphasizes minima;
  width `m` controls smoothing.
- **Finding**: the moving mini-max emphasizes peaks/troughs with smoothing built
  into the transform and is proposed for both mechanical rules and chart-pattern
  detection.
- **Limitation**: the paper is a proposal with illustrative figures — no
  backtest, no statistical evaluation, no comparison against SMA/ZigZag pivots.

### arXiv 2301.02692v1 (2023, stat.ME) — Isotonic Recalibration under a Low Signal-to-Noise Ratio
- **Question**: can any regression model be made auto-calibrated (no systematic
  cross-financing between price cohorts) while staying explainable?
- **Method**: apply isotonic regression as a post-hoc recalibration step to an
  arbitrary regression/pricing model; prove complexity bounds.
- **Finding**: isotonic recalibration guarantees auto-calibration; under a **low
  signal-to-noise ratio** the recalibrated function is provably of **low
  complexity** — a coarse partition of the covariate space — so explainability is
  a by-product, not a trade-off.
- **Limitation**: insurance-pricing framing; low-SNR is the assumed regime, not
  tested per dataset; requires enough data to fit the isotonic step.

### arXiv 0910.2909v3 (2010, q-fin.ST) — Compensating asynchrony effects in the calculation of financial correlations
- **Question**: how much of the Epps effect (correlation falling as the sampling
  interval shrinks) is pure statistical artefact of asynchronous trading?
- **Data/method**: model correlation on asynchronous series by assuming an
  underlying synchronous series, derive a correction from trading prices and
  trading times alone; apply to empirical data.
- **Finding**: observation asynchrony is a **major cause** of the Epps effect,
  especially for less frequently traded securities; the estimator quantifies and
  compensates it without external data.
- **Limitation**: assumes an underlying synchronous return series; the residual
  (non-statistical) share of the Epps effect is left open.

### arXiv physics/0701110v3 (2007, physics.soc-ph) — On the origin of the Epps effect
- **Question**: is trading asynchronicity *sufficient* to explain the Epps effect,
  isolated from lead-lag?
- **Data/method**: select stock pairs where lead-lag is negligible and study
  short-window correlations directly.
- **Finding**: asynchronicity is important but **alone insufficient** to account
  for the whole Epps effect even where lead-lag is negligible — there is a further
  microstructural component.
- **Limitation**: pairwise, a small set of pairs; the extra mechanism is not
  itself identified.

### arXiv 1110.1006v1 (2011, q-fin.ST) — Returns in futures markets and ν = 3 t-distribution
- **Question**: what distribution describes high-frequency futures log-returns?
- **Data/method**: a large set of futures time series, fit to a Student-t.
- **Finding**: a **t-distribution with ν ≈ 3** describes "almost all" series, robust
  across series and across sampling frequencies **below one hour**.
- **Limitation**: single-letter, futures-only; the ν≈3 claim is descriptive and
  the paper does not tie it to a trading or risk-sizing rule.

### arXiv 2301.05080v1 (2023, q-fin.ST) — Non-linear correlation analysis in financial markets using hierarchical clustering
- **Question**: can a dependence measure that is zero *iff* independent expose
  structure Pearson misses?
- **Method**: distance correlation coefficient (DCC) on S&P 500 stock pairs, then
  agglomerative clustering of the DCC matrix into market states.
- **Finding**: DCC detects non-linear associations invisible to Pearson and yields
  a lower-dimensional informative variable set; the correlation-based market-state
  evolution is characterised.
- **Limitation**: small universe, no economic evaluation of the clustering; DCC is
  `O(n²)` in samples, not a cheap daily instrument.

### arXiv 2402.05364v2 (2024, q-fin.ST) — Coarse graining correlation matrices according to macrostructures
- **Question**: can sector coarse-graining replace full Pearson matrices for
  market-state tracking?
- **Method**: Guhr's method (Rinn et al. 2015) to build sector-averaged
  ("Guhr") matrices from Pearson matrices; compare market-state evolution and
  transition matrices.
- **Finding**: market-state behaviour is **similar** between Guhr and Pearson
  matrices, but the number of relevant variables drops by orders of magnitude.
- **Limitation**: state-tracking only; no risk or portfolio evaluation of the
  coarse-grained matrix as a covariance input.

### arXiv 2010.15105v1 (2020, q-fin.ST) — Price response functions and spread impact in correlated financial markets
- **Question**: how sensitive is measured price impact to the *definition* of the
  response function?
- **Data/method**: NASDAQ TAQ order-book data; two time-scale definitions of the
  trade-response function; test ordering of trade signs vs returns and spread
  conditioning.
- **Finding**: the response can vary by **up to a factor of two** across
  definitions; delayed responses are suppressed, confirming the dominant
  *immediate* price response right after a trade; **large spreads have stronger
  impact**. Price formation is non-Markovian.
- **Limitation**: one venue (NASDAQ), one period; correlational response, no
  causal or execution-algorithm evaluation.

### arXiv 2309.12082v2 (2023, q-fin.ST) — Estimating Stable Fixed Points and Langevin Potentials for Financial Dynamics
- **Question**: GBM's drift has no stable nonzero price — does a richer drift?
- **Method**: generalise GBM to an SDE with polynomial drift of order `q`;
  Kramers-Moyal coefficient estimation + model selection; MCMC ensembles of the
  potential function.
- **Finding**: `q=2` is most frequently optimal; the potential shows a clear well,
  i.e. a **stable price** the GBM cannot represent.
- **Limitation**: stochastic fixed points, not deterministic price targets; no
  trading rule and no out-of-sample forecast test.

## 3. Learnings applicable to this repo

### L1. Position sizing near a continuation threshold
- **Source**: `arXiv 2607.28230v2` (2026) — Boundary-Induced Apparent Risk Aversion
- **Finding**: with a costly absorbing boundary, exact lattice optimal exposure is
  compressed **below** the no-boundary Kelly fraction by an amount that is a
  function of log-distance-to-boundary `d`, horizon `T` and residual ratio `rho`;
  the compression vanishes once `d > -T·log(1-f·a)` (boundary dynamically
  irrelevant).
- **Repo surface**: `tradingagents/strategies/size.py::kelly_fraction` (line 14)
  and `size.py::risk_of_ruin` (line 240).
- **Status**: `partial` — `kelly_fraction` is pure `(bp-q)/b` with no boundary
  term; `risk_of_ruin` exists but is a separate survival check, never folded into
  the Kelly size. There is no distance-to-boundary argument anywhere.
- **Concrete step**: add
  `kelly_with_ruin_buffer(p_win, odds, distance, horizon, residual_ratio)` that
  multiplies `kelly_fraction` by the boundary-compression factor, returning the
  no-boundary Kelly when `distance > -horizon*log(1 - f*a)`, and wire it behind a
  config gate.

### L2. Kelly overbets when returns are time-changed (non-lognormal)
- **Source**: `arXiv 2603.13632v1` (2026) — Betting Around the Clock
- **Finding**: Kelly maximizes growth only if gross returns are log-normal; under
  a subordinated (stochastic-clock) process — e.g. Variance-Gamma — the Kelly
  position is too large and a lower exposure earns a higher average growth, with
  the error growing in the variance of the clock.
- **Repo surface**: `tradingagents/strategies/size.py::position_size_kelly`
  (line 24), consumed by `size.py::composite_position_size` (line 70).
- **Status**: `absent` — the sizer scales Kelly by a fixed fractional constant and
  a cap; no assumption on the return law is declared or adjusted for.
- **Concrete step**: add an optional `clock_variance` attenuation factor
  (`f_eff = f_K / (1 + k·Var(clock))`) documented as the single non-lognormal
  correction, default off, so today's behaviour is byte-identical when the gate
  is off.

### L3. MACD is a lagging trend follower — filter it in range-bound regimes
- **Source**: `arXiv 2001.04237v1` (2020) — EMA vs. MEA / MACD
- **Finding**: MACD signals always print *after* the extremum and, with small `N`,
  fire spuriously in range-bound closes; the paper's own remedy is to combine with
  ADX or RSI.
- **Repo surface**: `tradingagents/strategies/technical_factors.py::macd_depth`
  (line 1106) and `technical_factors.py::ema` (line 40); extended indicators reach
  `strategies/extended_indicators.py`.
- **Status**: `partial` — the EMA/MACD arithmetic is implemented (with the single
  `ema` producer), but no consumer gates the MACD cross on a trend-strength filter
  (`adx` is computed in `technical_factors.py::adx`, line 230, and is not wired
  to `macd_depth`).
- **Concrete step**: have the MACD consumers require `adx` above a floor before
  treating a cross as a signal (a range-bound guard), so MACD crosses no longer
  produce signals in chop.

### L4. Short-window correlations are downward-biased by asynchrony (Epps)
- **Source**: `arXiv 0910.2909v3` (2010) and `arXiv physics/0701110v3` (2007)
- **Finding**: asynchrony in observation times produces a large downward bias in
  correlation as the sampling interval shrinks, especially for thinly traded
  names; asynchronicity is a major but not exhaustive cause of the Epps effect.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::_aligned_matrix`
  (line 57) and `covariance_models.py::panel_spectrum` (line 272).
- **Status**: `absent` — `_aligned_matrix` simply takes the "last common window"
  of already-aligned returns and silently accepts the asynchrony bias; no minimum
  window guard or asynchrony compensation exists.
- **Concrete step**: state a minimum sampling interval / trading-frequency floor
  in `_aligned_matrix`'s docstring-derived guard and refuse (return no matrix)
  below it, rather than reporting a correlation that the Epps effect has
  deflated; the compensated estimator itself is a larger follow-up.

### L5. Pairs trading is regime-conditional, not standalone
- **Source**: `arXiv 2010.01157v1` (2020) — Gold Standard Pairs Trading Rules
- **Finding**: distance/cointegration pairs trading fails to beat the market over
  1990–2020 after costs, but earns ~+2%/month excess in bear markets and lags the
  market in bull markets; the *optimal parameters* are themselves a function of
  market factors.
- **Repo surface**: `tradingagents/strategies/mean_reversion.py::mean_reversion_verdict`
  (line 226) and the regime gate in `tradingagents/strategies/regime.py`
  (`hmm_filtered_regime`, line ~545).
- **Status**: `partial` — `mean_reversion_verdict` classifies
  stable/reverting/trending from the series alone (half-life, `phi`) and never
  consults the market regime; the regime machinery exists but is not joined to the
  mean-reversion verdict.
- **Concrete step**: gate *entry* on a bear / high-volatility regime label so a
  mean-reversion read in a bull regime is reported as low-conviction, matching the
  paper's bear-market-only excess return.

### L6. A dependence measure that is zero iff independent
- **Source**: `arXiv 2301.05080v1` (2023) — Non-linear correlation via hierarchical clustering
- **Finding**: distance correlation detects non-linear associations Pearson is
  structurally blind to and is zero only under independence; agglomerative
  clustering of DCC maps market states.
- **Repo surface**: `tradingagents/strategies/statistical.py::correlation_matrix`
  (line 203).
- **Status**: `absent` — `correlation_matrix` offers only pearson/spearman/kendall
  (line 214), none of which is zero-iff-independent for non-linear dependence.
- **Concrete step**: add a `method="distance"` branch computing distance
  correlation over aligned returns, reported beside — never replacing — the
  Pearson matrix, with the same small-`n` refusal contract.

### L7. Sector coarse-graining of the correlation matrix
- **Source**: `arXiv 2402.05364v2` (2024) — Coarse graining correlation matrices
- **Finding**: Guhr (sector-averaged) matrices reproduce market-state evolution
  and transition matrices nearly identically to full Pearson matrices while
  reducing the number of relevant variables by orders of magnitude.
- **Repo surface**: `tradingagents/strategies/covariance_models.py::panel_spectrum`
  (line 272) and `covariance_models.py::ledoit_wolf_shrink` (line 85);
  `tradingagents/strategies/sector_breadth.py` owns the sector map.
- **Status**: `absent` — the covariance engine consumes the full per-name panel;
  there is no sector-coarsened matrix producer to trade dimensionality for
  stability.
- **Concrete step**: add `coarse_grain_by_sector(returns_by_name, sectors)` that
  average-correlates within sectors to a small Guhr matrix, as an alternative
  input to `panel_spectrum` for regime-state tracking.

### L8. A declared return law for the tail layer
- **Source**: `arXiv 1110.1006v1` (2011) — Returns in futures markets and ν=3 t
- **Finding**: high-frequency (sub-hourly) futures log-returns are well described
  by a Student-t with ν≈3, robust across series and sampling frequency.
- **Repo surface**: `tradingagents/strategies/tail_risk.py::tail_risk`
  (line 174) and `tradingagents/strategies/regime.py::EMISSION_NU` (line 252).
- **Status**: `partial` — the HMM emission layer already supports a Student-t
  family but fixes `EMISSION_NU = 5.0` ("the paper's low-dof heavy tail"), while
  the K1 `tail_risk` read is empirical-historical VaR with no fitted tail law; the
  ν≈3 literature value is inconsistent with the hard-coded 5.0.
- **Concrete step**: expose `EMISSION_NU` as a config value defaulting to 3.0 for
  intraday horizons and report the fitted/externally-set ν beside `tail_risk` so
  the tail number names the law it assumes.

### L9. Price response is definition-sensitive and spread-conditioned
- **Source**: `arXiv 2010.15105v1` (2020) — Price response functions and spread impact
- **Finding**: measured price response can vary by a factor of two across
  definitions; delayed response is suppressed (immediate impact dominates); large
  spreads have stronger impact; price formation is non-Markovian.
- **Repo surface**: `tradingagents/strategies/orderflow.py::vpin` (line 198) and
  `orderflow.py::knife_guard_vpin` (line 103).
- **Status**: `partial` — the flow layer measures toxicity/VPIN and tiered flows
  but has no trade-response/impact estimate, so the factor-of-two
  definition-sensitivity and the spread conditioning are uncaptured.
- **Concrete step**: add an impact read that conditions immediately-post-trade
  response on spread bucket, so any cost model derived from it carries the spread
  term the paper shows dominates.

## 4. Where this repo is already ahead of the literature

- `tradingagents/strategies/calibration.py::isotonic_calibrate` already implements
  the isotonic recalibration of `arXiv 2301.02692v1` (2023), and goes further with
  `fit_buckets_by_regime` / `calibrated_confidence_by_regime` — regime-partitioned
  calibration the paper does not attempt.
- `tradingagents/strategies/covariance_models.py::eigen_projector_distance` and
  `spectral_null_band` implement a first-order null band for spectral movement
  (2607.06373) — a falsifiable "is this eigenstructure change real?" read that
  none of this category's correlation papers provide; they report eigenstructure
  shifts without an estimation-noise band.
- `tradingagents/strategies/tail_risk.py::tail_risk` reports VaR/CVaR *with* a
  quality score, estimation uncertainty and a refusal contract (K1) — ahead of the
  category's tail-fit papers, which report point parameters with no uncertainty.
- `tradingagents/strategies/hierarchical_risk_parity.py::hrp_weights` implements
  single-linkage HRP; the category's clustering papers (2301.05080, 2005.02482,
  2402.05364) stop at descriptive clustering.
- `tradingagents/strategies/regime.py` already offers heavy-tailed HMM emissions
  (student_t/laplace/ged) behind a gate — the distributional realism this
  category's "returns are not normal" papers argue for, in usable form.

## 5. Defects or risks the literature exposes

- **Kelly is applied as if returns were log-normal and continuation were
  uninterrupted.** `tradingagents/strategies/size.py:14` (`kelly_fraction`),
  `size.py:24` (`position_size_kelly`) and `size.py:70`
  (`composite_position_size`) apply `(bp-q)/b` with no declared return law and no
  boundary term. `arXiv 2603.13632v1` (2026) shows Kelly is *too large* under any
  time-changed process, and `arXiv 2607.28230v2` (2026) shows a costly
  continuation threshold compresses the optimum below Kelly. Both point the same
  way: the current sizer can oversize.
- **Correlation is estimated on aligned-but-asynchronous windows with no guard.**
  `tradingagents/strategies/covariance_models.py:57` (`_aligned_matrix`) takes the
  last common window of aligned returns. `arXiv 0910.2909v3` (2010) and
  `arXiv physics/0701110v3` (2007) show short-interval correlations are deflated
  by asynchrony, most for thin names. If any caller feeds sub-daily or
  irregular-spacing returns, the reported matrix understates dependence — a
  risk-management-relevant bias, not a cosmetic one.
- **Mean-reversion verdicts are regime-blind.** `mean_reversion.py:226`
  (`mean_reversion_verdict`) classifies purely from the price series.
  `arXiv 2010.01157v1` (2020) shows the equivalent rule set loses to the market in
  bull regimes and only wins in bear regimes; a verdict that ignores the regime
  will over-signal in exactly the regime where the edge is documented to vanish.
- **A declared heavy-tail parameter that contradicts the literature.**
  `regime.py:252` fixes `EMISSION_NU = 5.0`, documented as "the paper's low-dof
  heavy tail", while `arXiv 1110.1006v1` (2011) reports ν≈3 for sub-hourly data.
  Whether 5.0 or 3.0 is right is horizon-dependent, but a hard-coded 5.0 with no
  horizon argument is an unexamined constant.
- **Corpus gap (data, not code).** The evidence pack lists
  `arXiv 1906.05057v2` ("distance measure incorporating time-varying lead-lag for
  pairs selection") as high-relevance, but `E:/fin paper/1906.05057v2.pdf` is
  absent from the corpus (only `1906.04822`, `1906.05327`, … are present). The
  abstract-level finding stands but could not be verified against full text here.

## 6. Limits of this review

- **Residual, not sampled for coverage.** The category exists only because the
  classifier abstained; I prioritised the 5 high-relevance rows and the
  medium rows whose `repo surface` named a real module. 17 papers were read at
  page level, the rest only from abstract. The 186 low-relevance rows are
  represented by their titles (wealth inequality, insurance, energy, quantum-walk,
  demographic and macroeconomic papers) — that block is genuinely off-repo and was
  not deep-read.
- **Composition derived from 269 evidence rows**, joined to
  `metadata.jsonl` by arXiv id (0 misses); the `booklists/other.json` shortlist
  (top 60) was used only for deep-read selection, so §1 primary-category shares
  are over all 269, not the 60.
- **One high-relevance paper unreadable** (`1906.05057v2`, file absent — §5).
- **Unverified**: whether any live dataflow actually feeds sub-daily returns into
  `covariance_models` (the Epps defect is a latent risk if it does, harmless if all
  callers are daily); and whether `macd_depth`'s consumers can observe `adx` — the
  wiring was not traced past the strategy layer in this pass, and is flagged for
  the parent to confirm before acting on L3.
- **Re-homing recommendations** (priority order). The bulk of this bucket is
  misclassified econophysics: the ~71 `cond-mat.stat-mech` + `physics.soc-ph` +
  `physics.data-an` papers belong in **Econophysics** (e.g. 1005.0378v1
  correlation asymmetry on index falls, physics/0601002v1 inverse statistics,
  physics/0510112v2 nonextensive volume, cond-mat/0301268v1 Kramers-Moyal
  Markov tests). Beyond that:

  | arXiv id | year | target category |
  | --- | --- | --- |
  | 0910.2909v3, physics/0701110v3 | 2010/2007 | Correlation |
  | 2301.05080v1, 2402.05364v2, 2005.02482v1, 1310.3984v1, 1311.0657v1, 0709.0281v1 | 2007–2024 | Correlation |
  | 1110.1006v1, 1111.2038v1, 2108.10176v1 | 2011–2021 | Risk / Tail |
  | 0806.2617v2, 1510.07280v1, physics/0502119v1, 0901.2271v2 | 2005–2015 | Volatility |
  | 2010.15105v1, 0709.3261v1, cond-mat/0403662v1, cond-mat/0403469v1, cond-mat/9912051v1, 1803.09432v1 | 1999–2020 | Microstructure |
  | 2309.12082v2, 1503.02177v1, 1205.0332v2 | 2012–2023 | Forecasting |
  | 2212.07944v4, 2311.00964v3, 2402.11066v1, 2308.14215v1, 2409.11524v1, 2207.04867v2 | 2022–2024 | ML Methods |
  | 2608.03088v1, 1102.5431v1, 1309.0602v1, 1907.10306v1, 2104.00262v3 | 2011–2026 | Statistical Methodology |
  | 2010.01157v1, 1906.05057v2 | 2019–2020 | Backtest / Market Efficiency |
  | 2607.28230v2, 2603.13632v1, 1510.03550v3 | 2015–2026 | Portfolio |
  | 2403.18126v2, 2201.01330v3, 0804.1039v1 | 2008–2024 | Options / Fixed Income |
  | 2512.07887v1, 1209.6369v1, 1004.0685v3 | 2010–2025 | Risk / Tail (credit) |
  | 1409.5321v1, 1206.5224v4, 0802.0984v2 | 2008–2014 | Factors / technical |

  The two `extended_indicators` high-relevance rows (2001.04237v1, 0802.0984v2)
  have no better home in the 19-book taxonomy — they should stay in `other`, and
  L3 keeps the actionable part (the MACD lag/range-bound filter).
