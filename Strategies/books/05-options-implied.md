# Options, Implied Volatility & Derivatives

`book 05/19` · slug `options-implied` · 234 papers in the corpus · 26 rated high-relevance by the sweep

## 0. Scope

This category covers everything the option price encodes beyond direction: the implied-volatility
surface and its no-arbitrage constraints, parametric surface fits (SVI/SABR/Hagan), risk-neutral
density recovery, variance/volatility risk premia and their harvesting, the VIX complex (term
structure, roll, contango/backwardation), and option-implied information used as a cross-sectional
predictor or as a hedging/risk input. It matters to this repo because the `strategies/options_*`
and `derivatives_gamma`/`rnd_recovery`/`volatility_models` modules already carry large, gated,
`None`-safe calculators whose governing rule is "compute, don't narrate" — the literature is the
check on whether those computed reads are the right quantities and whether their refusals are
honest. The category is Python-quant adjacent, not LLM-agent adjacent: only a minority of papers
(two of the high-relevance 26) touch the agent layer, and almost none touch execution.

## 1. Corpus composition

The sweep annotates 234 papers: **26 high**, **164 medium**, **44 background**. The evidence pack
prints all 26 high, the 100 most recent of the 164 medium, and the 44 background — 170 rows carrying
an author-year and arXiv id; of those 170, the decade split is 121 (2020s), 34 (2010s), 15 (2000s).
The top-60 booklist (the pool the deep reads were drawn from) is dominated by `q-fin.ST` (29),
then `q-fin.PR` (9), `q-fin.CP` (6), `q-fin.RM`/`q-fin.MF` (3 each), with the rest spread over
`q-fin.GN`, `q-fin.TR`, `q-fin.PM`, `econ.EM`, `cs.LG`, `cond-mat.stat-mech`, `physics.soc-ph`.

| decade | evidence rows (170) | high-relevance (26) | top-60 booklist |
| --- | --- | --- | --- |
| 2020–2026 | 121 | 14 | 41 |
| 2010–2019 | 34 | 10 | 17 |
| 2000s / earlier | 15 | 2 | 2 |

The category is dominated by two clusters. One is the **deep-learning-on-the-surface** cluster
(2020–2026): VAE/LSTM/neural-SDE/operator surface construction and prediction, neural hedging, and
RND recovery by learned operators — almost all indexed as `q-fin.ST` or `q-fin.CP`/`cs.LG`. The
other is the **classical implied–realized relation and RND extraction** cluster (2000s–2010s):
Fourier/COS and Breeden–Litzenberger recovery, MFIV vs corridor IV, fractional-cointegration
unbiasedness tests, VIX-futures tracking. The `q-fin.PR` share in the booklist (9/60) is the
pricing-theory rump: CEV, variance-gamma, jump-diffusion, spread options, entropy. Notably, the
paper that this repo's `rnd_recovery.py` implements (2607.27188) concludes that classical per-expiry
fits beat learned operators on held-out market prices, which is why the deployed module declines the
learned path.

## 2. Deep reads

### 2607.27188v1 — Inverse Learning of Latent Risk-Neutral Densities from Irregular Option Quotes
- **Question.** Does reconstructing observed option *prices* identify the latent risk-neutral
  density that generated them? The paper argues these are distinct questions.
- **Data/market.** A controlled synthetic benchmark (three martingale families: time-varying-vol
  GBM, inception-time lognormal mixture, compensated Merton jump-diffusion; 3,000 surfaces/seed ×
  10 seeds; 40–320 observed irregular quotes per surface), plus a chronological 2019–2020 NIFTY
  transaction-bar panel (6,191 calls, 295 dates, 19 expiries; 524 hidden test calls).
- **Method.** Four learned backbones (DeepONet, FNO, quote transformer, Deep Sets) vs direct
  parametric and regularized density estimators, surface smoothers, and Breeden–Litzenberger. A
  numerical conditioning analysis discretizes the 128-node pricing map and studies its singular
  spectrum under the mass + forward constraints.
- **Headline finding.** After enforcing mass and forward constraints, **95 of 126 pricing
  directions are numerically null**; two densities separated by L¹ = 0.061 produce identical prices
  on the covered strikes (condition number 6.89×10³ in the resolved subspace). A two-component
  lognormal mixture has the lowest aggregate synthetic price/L¹/Wasserstein/fixed-tail error;
  DeepONet wins the 1% quantile (−39.0%) and variance (−34.6%) functionals and the quote transformer
  wins under Merton misspecification (−16.4% L¹). On held-out NIFTY prices, test-time adaptation cuts
  DeepONet RMSE 28.3%, but per-expiry mixture (RMSE 0.000166) and SVI (0.000241) remain far more
  accurate than the adapted network (0.003464). Density-MSE supervision beats composite objectives by
  55–64% on L¹.
- **Stated limitation.** Simulator truth holds only conditional on the chosen families; NIFTY bars
  have no bid/ask and carry no latent label; certification is finite-grid, not a proof of continuous
  no-arbitrage.

### 2309.00943v2 — iCOS: Option-Implied COS Method
- **Question.** Can the risk-neutral density, option prices, and Greeks be extracted
  non-parametrically, without a parametric characteristic function and without optimization?
- **Data/market.** S&P 500 index options and Amazon (AMZN) equity options on an earnings-announcement
  day (1 day to maturity); SPX options 2017-01-03 to 2021-04-01 for a VIX error decomposition.
- **Method.** Combines the Carr–Madan spanning result with the Fang–Oosterlee Fourier-cosine
  machinery: the cosine coefficients themselves are *implied* from observed OTM option prices as a
  replicating portfolio, then used to build the RND, interpolated prices, and deltas. Asymptotic
  limiting distributions derived for the estimators.
- **Headline finding.** Fully non-parametric and optimization-free; smooths noisy short-dated
  chains (it recovers the W-shaped pre-earnings IV curve and its bimodal RND, which parametric
  curves fail to fit). The VIX error decomposition finds **observation errors centred at zero**
  (up to 0.04 index points) while **discretization errors are positive**, averaging ~0.135% of the
  index and reaching ~0.7 percentage points in high-volatility periods — i.e. the strike-grid
  discretization biases VIX upward.
- **Stated limitation.** VIX error estimates depend on a cubic-spline bias-reduction step; the
  asymptotic setup fixes maturity and the strike-support endpoints.

### 2106.07177v2 — A Two-Step Framework for Arbitrage-Free Prediction of the Implied Volatility Surface
- **Question.** How do you predict the whole IV surface forward in time while guaranteeing it is
  free of *static* arbitrage?
- **Data/market.** OptionMetrics SPX implied volatilities, 2009-01-01 to 2020-12-31 (3,021 days,
  374 (m, τ) points/day), split 9.5y train / 2.5y test including the 2020 crash.
- **Method.** Step 1 extracts surface features three ways — direct grid sampling (SAM), PCA of
  log-IV changes, or a VAE — and predicts them with an LSTM over monthly/weekly/daily moving
  averages. Step 2 maps predicted features to a full surface with a DNN whose architecture
  (Softplus output) guarantees positivity and twice-differentiability, with calendar-spread,
  Durrleman-butterfly and large-moneyness conditions added as loss penalties.
- **Headline finding.** SAM-DNN and VAE-DNN are the best out-of-sample predictors and beat the
  classical Dumas–Fleming–Whaley (DFW) fit by a wide margin (test RMSE 0.0245/0.0248 vs 0.0366;
  PCA-DNN is ~3× worse at 0.0544 — feature selection matters more than the predictor). The
  arbitrage-constrained DNN also reduces prediction error versus plain DFW interpolation, and the
  DFW baseline produces *negative* calendar-spread and butterfly penalties (real static arbitrage)
  where the DNN produces zero.
- **Stated limitation.** The framework does not enforce *dynamic* arbitrage; calibrated surface-SVI
  parameters are "too volatile to be predicted well," so SVI parameters are not used as features.

### 1407.5528v1 — Arbitrage-Free Prediction of the Implied Volatility Smile
- **Question.** How do you forecast an n-dimensional co-terminal option-price vector when the
  prices must satisfy non-linear, non-explicit no-arbitrage restrictions at every time step?
- **Data/market.** USDJPY FX options (RBS desk), daily.
- **Method.** Encode each day's option prices as the parameters of the risk-neutral measure (the
  SABR parameterization in closed form), run the time-series model in *parameter* space, then
  integrate the predicted risk-neutral measure against each payoff to get arbitrage-free predicted
  prices.
- **Headline finding.** Working in the parameter space makes the no-arbitrage constraint hold by
  construction; the resulting predictions beat the naive random-walk forecast, suggesting a
  derivatives-portfolio management strategy analogous to equity/futures strategies.
- **Stated limitation.** Demonstrated on FX with SABR; the SABR parameterization alone does not fit
  a whole surface well, and the method's accuracy depends on the chosen parameterization.

### 1907.00293v1 — Tracking VIX with VIX Futures: Portfolio Construction and Performance
- **Question.** Can static or dynamic portfolios of VIX futures track spot VIX?
- **Data/market.** VIX spot, front seven VIX futures, and VXX, 2011-01-03 to 2016-12-30 (1,510
  days); in-sample 2011–2015, out-of-sample 2016.
- **Method.** Regressions of futures returns on spot returns; constrained least-squares static
  portfolios optimized on price and on returns; a discrete-time mean-reverting dynamic strategy that
  rebalances daily.
- **Headline finding.** Futures returns have slopes well below 1 (1-month β = 0.604, R² = 0.792)
  and statistically significant **negative intercepts that grow with holding horizon** — the roll
  drag. Static price-tracking portfolios collapse to ~85–93% cash; static return-tracking portfolios
  require 1.3×–3.2× leverage and **go negative** in value. VXX loses 99% of its value over its life.
  A dynamic daily-adjusted strategy beats VXX but no static portfolio tracks VIX closely.
- **Stated limitation.** The spot is not tradable and VIX futures do not converge cleanly to spot at
  settlement (frictions, settlement rules); results are for 2011–2016 and one volatility ETN.

### 2608.26115v1 — Option-Implied Signals and Crash Risk (U.S. Equity Options, 2015–2026)
- **Question.** Do the canonical option-implied cross-sectional predictors survive the post-2020
  retail-option boom and the 2023–2026 AI/mega-cap regime?
- **Data/market.** OPRA end-of-day contract records, 12,362,276 firm-day observations, 10,026
  underlyings, 2,910 trading days; three regimes (2015–2019 low-vol, 2020–2022 high-vol,
  2023–2026 AI/mega-cap).
- **Method.** Xing-style screens; firm-day features (ATM/OTM IV bands, smirk, Cremers–Weinbaum IV
  spread, term-structure slope, a cross-strike risk-neutral-skewness proxy, OI-weighted Greeks,
  liquidity controls); two-way fixed-effects panel regressions with double-clustered SEs; rolling
  XGBoost/Elastic-Net benchmarks.
- **Headline finding.** The Xing smirk–return coefficient decays monotonically and loses
  significance in the AI/mega-cap regime (−0.023, t = −5.5 → −0.006, t = −1.5) and **reverses sign**
  at three months (+0.016). The **IV spread and risk-neutral skewness survive in every regime and
  specification (|t| > 4)**. XGBoost beats linear models only in the AI/mega-cap regime
  (R²_OOS +1.29% vs +0.07%); the dominant feature differs in every regime (OI-weighted vega, contract
  count, OTM call IV) and no canonical signal is top-five anywhere. Crash AUC is 0.706 in calm
  markets but falls to 0.561 in high-volatility regimes.
- **Stated limitation.** No CRSP/Compustat controls; a random subsample of 1.5M firm-days is used
  for the panel (inflated SEs); no signed retail flow; the risk-neutral skewness is a cross-strike IV
  proxy, not the strict BKM moment.

### 2201.09319v1 — Option Volume Imbalance as a Predictor for Equity Market Returns
- **Question.** Does the normalized imbalance between positive-view and negative-view option
  volumes predict directional spot moves, and does the decomposition by participant class matter?
- **Data/market.** Nasdaq NOM and PHLX 10-minute volume reports, 2015-01-02 to 2019-12-31,
  disaggregated over five market-participant classes (Firm, Broker, Market Maker, Customer,
  Professional Customer).
- **Method.** Signed OVI = (call buys + put sells − call sells − put buys) / total volume, per
  participant class; evaluated by cumulative P&L / Sharpe and a new "P&L regression" that jointly
  optimizes the trading P&L; extension to days-to-expiry, moneyness, and Greek conditioning.
- **Headline finding.** OVI predicts **excess overnight returns**; the strongest signal comes from
  **Market-Maker** volumes, most predictability comes from **high-implied-volatility** contracts, and
  **put** volume is more informative than call volume. Short-horizon predictability partially
  reverses at longer horizons.
- **Stated limitation.** Requires exchange-signed, participant-classified volume (only two Nasdaq
  venues); each trade is double-counted across both counterparties by construction.

### 2609.20224v1 — The Year-End Toll: Frictions Embedded in Option-Implied Rates
- **Question.** Is the option-implied discount rate recovered from put–call parity economically
  pure, or does it embed implementation frictions?
- **Data/market.** One-minute NBBO European-style SPX/RUT/SPXW/RUTW options, June 2012–December
  2025; benchmarks DGS and DTB.
- **Method.** Regress same-maturity call−put spreads on strike so the slope identifies the
  option-implied discount factor; define the Option Funding Basis (OFB) vs a benchmark; test for a
  discontinuity when maturity first crosses December 31.
- **Headline finding.** A **2–3 bp unannualized increase in the option funding basis** when maturity
  crosses December 31, in both SPX and RUT, behaving as a **fixed price wedge** (scaling ~κ/τ, so
  ~10 annualized bp at three months), strengthening in the mid-2010s, independently echoed in
  government-bond CIP. Conclusion: put–call parity identifies the discount rate *precisely* but does
  not establish its economic purity.
- **Stated limitation.** Long-dated support is thin so later December-31 crossings cannot be sharply
  identified; the finding is an existence proof, not a full decomposition of the wedge.

### 0809.3375v1 — Smile Dynamics: A Theory of the Implied Leverage Effect
- **Question.** Is the IV skew explainable by the historical leverage effect, and how should the
  smile move when the underlying moves?
- **Data/market.** OEX/SPX index and small/mid/large-cap US stocks, roughly 1990–2008.
- **Method.** Cumulant expansion of the near-the-money smile; the maturity dependence of skewness
  from a leverage correlation g_L(t) (exponential decay −A·e^(−t/t_L)); derive the implied-leverage
  coefficient γ(T) and compare to sticky-strike and sticky-delta bounds.
- **Headline finding.** γ(T) from history lies *between* sticky strike and sticky delta; sticky
  strike is exact only for very short maturities and is an upper bound otherwise. Option markets
  **overestimate the leverage effect** — implied skew is ~50% too large at short maturities and
  ~100% at long maturities, consistent with market makers using a sticky-strike rule with an
  exaggerated smile. Leverage strength rises roughly logarithmically with market cap.
- **Stated limitation.** Uses ATM vols only (no full smile data), so the "smile is too skewed"
  hypothesis is not directly tested; the daily-skewness term is neglected (checked small).

### 1208.4831v2 — Revisiting the Fractional Cointegrating Dynamics of Implied–Realized Volatility
- **Question.** Is ex-ante implied volatility an unbiased long-run forecast of ex-post realized
  volatility, and does the choice of implied measure matter?
- **Data/market.** S&P 500 and DAX, monthly and bi-weekly options, covering the 2008 crisis.
- **Method.** Compare model-free implied volatility (MFIV, full-integral) to corridor implied
  volatility (CIV, fixed finite strike band); realized volatility via a jump- and noise-robust
  jump-wavelet two-scale estimator (JWTSRV); new wavelet band least squares (WBLS) for the
  fractional-cointegrating regression, checked against Fourier FMNBLS; wavelet coherence to find the
  informative frequency band.
- **Headline finding.** The implied–realized dependence comes **solely from the lower frequencies**;
  in the long run, **corridor IV (not MFIV) is the unbiased forecast of realized volatility**. MFIV's
  full-integral form introduces bias through extrapolation of noisy far-OTM quotes. Jump/noise
  robustness of the RV estimator does not change the relation.
- **Stated limitation.** Two indices and a crisis-era sample; CIV values depend on the chosen strike
  corridor (width and positioning).

### 1801.08007v2 — Financial Density Forecasts: Risk-Neutral vs Historical Schemes
- **Question.** Across the entire density range, do risk-neutral or historical density forecasts
  predict better, and which parametric family?
- **Data/market.** IBEX 35 futures options, Nov 1995–Dec 2016, 6,659 cleaned option prices over 254
  non-overlapping monthly cycles (28 days before expiry).
- **Method.** 15 schemes: historical (lognormal, bootstrap, GARCH-N, GARCH-t, GJR-FHS) vs risk-neutral
  (calibrated lognormal, Heston, Bates, Variance Gamma, Malz Breeden–Litzenberger). Validation by
  PIT/Berkowitz–KS–JB consistency, the logarithmic score, a return-based CRPS, and a composite
  Integrated Forecast Score (IFS).
- **Headline finding.** **Risk-neutral densities outperform historical ones on information content.**
  The **Variance Gamma** model gives the highest out-of-sample likelihood and lowest predictive
  errors; **GJR-FHS** is the most consistent across the whole density range. Lognormal densities, the
  Heston model, and the Breeden–Litzenberger formula are **biased and rejected** in statistical tests.
- **Stated limitation.** One index (IBEX 35); no mixed risk-neutral/historical densities; RNDs are
  calibrated to market prices only, not settlement prices.

### 2009.09770v1 — Implied Basket Correlation Dynamics
- **Question.** Can option-implied basket correlation be modelled and used to improve a dispersion
  strategy, given the physical and risk-neutral estimates disagree?
- **Data/market.** DAX and its 30 constituents, 2010-08-02 to 2012-08-01.
- **Method.** Impose equicorrelation to reduce dimensionality; imply the basket correlation from the
  index and constituent MFIVs; model the implied-correlation surface with a dynamic semiparametric
  factor model (FPCA basis + time-varying loadings); compare dispersion-strategy hedge schemes.
- **Headline finding.** The null H₀: realized correlation = implied correlation is strongly rejected
  for the DAX (evidence of a correlation risk premium, CRP); the implied correlation forecasts the
  future realized correlation, and using the model's hedge reduces potential losses and lifts average
  dispersion profitability. The H₀: RV = MFIV is rejected for the index but *not* for many
  constituents at longer maturities.
- **Stated limitation.** Equicorrelation is an approximation; two-year DAX sample; the dispersion
  payoff assumes constituent implied ≈ realized variance.

### 2607.08500v2 — Estimating the Stochastic Discount Factor from Option Prices and Predicting the Equity Premium
- **Question.** Can a volatility-scaled SDF be recovered from index options alone and forecast the
  equity premium better than existing bounds?
- **Data/market.** S&P 500 options.
- **Method.** Recover a time-varying-volatility-scaled SDF from option-implied prices and market
  data; compare the implied equity premium to the Martin lower bound out-of-sample.
- **Headline finding.** The recovered SDF is **stable and non-monotonic** — a hump on the shallow put
  side that becomes a W-shape with maturity; maturity is the key driver of the central hump, and the
  structure is rationalizable by stochastic-volatility dynamics under a constant market price of
  risk. The SDF-implied equity premium forecasts **better out-of-sample than the Martin bounds**.
- **Stated limitation.** Index-only, model-dependent SDF scaling; the shape result is descriptive and
  rationalized rather than structurally identified.

### 2411.02804v1 — Beyond the Traditional VIX: A Novel Approach to Identifying Uncertainty Shocks
- **Question.** Does a second-moment VIX miss the heavy-tailed character of option prices, and can a
  heavy-tailed "revised VIX" identify uncertainty shocks better?
- **Data/market.** S&P 500 option prices; fractional time series of risk–reward ratios.
- **Method.** Fit a **double-subordinated Normal Inverse Gaussian (NIG) Lévy process** to S&P 500
  option prices to construct a revised VIX, then compute an axiomatic family of risk–reward ratios
  over a fractional (long-memory) time series.
- **Headline finding.** The NIG-based measure captures the skew and fat tails that the standard
  second-moment VIX (and time-varying-volatility-of-VIX methods) miss, giving an arbitrage-free
  option-price model and a directional (risk/reward-based) uncertainty-shock read that plain variance
  cannot supply.
- **Stated limitation.** Parametric NIG fit; the argument is largely theoretical/methodological, with
  the empirical illustration on one index.

### 1702.02777v1 — Rough Volatility: Evidence from Option Prices
- **Question.** Is the "rough volatility" (Hurst < 1/2) finding, established on high-frequency
  historical volatility, recovered from option-implied volatilities instead?
- **Data/market.** One-month ATM implied volatility on the S&P 500, 2006-01-05 to 2011-05-05
  (1,166 points).
- **Method.** Treat short-dated ATM implied vol as a spot-volatility proxy; estimate the scaling
  exponent ζ(q) of the structure function m(q,Δ) of log-vol increments; a Medvedev–Scaillet
  correction refines the proxy; a numerical/analytical bias analysis.
- **Headline finding.** Log-volatility is well approximated by a fractional Brownian motion with
  **H ≈ 0.32 < 1/2 — volatility is rough**, confirmed from option prices. The estimate is *larger*
  than from historical data (typically ~0.1–0.2) because a remaining time-to-maturity of one month
  **smooths** the estimate; log-vol increments are approximately Gaussian with monofractal scaling.
- **Stated limitation.** One index, one month maturity, provider-extrapolated IV; the upward Hurst
  bias is a smoothing artefact quantified but not eliminated.

### 2604.03499v3 — Marking-Aware Sequential VaR Recalibration for Standardized Option Books
- **Question.** What is the correct loss *target* for daily option-book VaR, given book construction,
  marking, loss scale, and available information?
- **Data/market.** S&P 500 (SPX) and QQQ ETF option books.
- **Method.** Target normalized book-level loss directly (marking-aware), restrict the forecast state
  to forecast-time information, and sequentially recalibrate an upper-tail VaR from past forecast
  residuals; rolling 50-day out-of-sample evaluation.
- **Headline finding.** The reference VaR **undercovers all three books in both markets**;
  sequential recalibration moves exceedance rates toward target and gives the best aggregate
  performance (lowest average violation, lowest pinball loss, smallest maximum exceedance), robust to
  direct marking, stricter book screens, VaR-floor removal, and alternative quantile learners.
- **Stated limitation.** Depends on the exact book/marking conventions chosen; the recalibration is a
  risk-control *layer*, not a pricing model.

## 3. Learnings applicable to this repo

### L1. The variance risk premium must be implied-variance minus *expected* realized variance, not a vol-point spread
- **Source**: `arXiv 2608.26115` (2026) — Option-Implied Signals and Crash Risk; and `arXiv 2009.09770`
  (2020) — Implied Basket Correlation Dynamics.
- **Finding**: The literature defines the VRP as implied *variance* minus a forecast of realized
  *variance* (Carr–Wu); Bollerslev et al.'s VRP predicts aggregate returns, and the dispersion paper
  tests H₀: RV = MFIV and rejects it for the index while failing to reject it for many constituents.
  The premium is a variance difference with a forward-looking expected-RV leg, and its sign/robustness
  is regime-dependent.
- **Repo surface**: `tradingagents/strategies/options_surface.py::volatility_risk_premium`
  (line 140).
- **Status**: `partial` — the function returns `(iv - realized_vol) * 100` on two caller-supplied
  scalars. It is wired into `analysis_tools.py::get_options_iv_read` (line ~10030) as a percentage-
  point difference of *volatilities* over an already-realized 20d window, with no expected-RV leg and
  no variance units.
- **Concrete step**: Add a sibling `variance_risk_premium(implied_var, rv_forecast)` that takes
  `options_math.model_free_implied_variance` (line 399) as the implied variance and a `volatility_models`/
  `long_memory` forecaster (`garch11_fit`:438 or `rv_forecast`:236) as the expected-RV leg, returning
  the variance-point spread and its sign, and keep `volatility_risk_premium` as the descriptive read.

### L2. Keep identifiability of the density explicit — and report the *ambiguity*, not just the fit
- **Source**: `arXiv 2607.27188` (2026) — Inverse Learning of Latent Risk-Neutral Densities.
- **Finding**: After the mass and forward constraints, 95 of 126 pricing directions are numerically
  null; two densities with L¹ = 0.061 produce identical covered-strike prices, so price accuracy is
  necessary but not sufficient for density identification. A well-specified two-component mixture beat
  every learned operator on aggregate price/L¹/Wasserstein/tail error.
- **Repo surface**: `tradingagents/strategies/rnd_recovery.py::rnd_recovery` (line 335) and its
  `_conditioning` singular-spectrum gate (`RND_MAX_CONDITION = 1000.0`).
- **Status**: `shipped` — the module fits the two-component lognormal mixture, declines the learned
  operator in writing, and refuses with the conditioning spectrum when the strikes cannot span the
  density. This is materially ahead of most RND papers.
- **Concrete step**: Extend `_conditioning`'s record with the paper's density-space ambiguity
  diagnostic — the number of numerically-null directions of the constrained pricing operator at the
  fitted point (a singular-value count below a relative threshold) — so a caller can see *how* price-
  equivalent the refusal margin is, not only the condition number.

### L3. No static-arbitrage certification exists on a fitted surface
- **Source**: `arXiv 2106.07177` (2021) — Two-Step Framework for Arbitrage-Free IVS Prediction;
  `arXiv 1407.5528` (2014) — Arbitrage-Free Prediction of the Smile; `arXiv 2607.27188` (2026).
- **Finding**: A surface is static-arbitrage-free iff it is positive, twice-differentiable,
  non-decreasing in total variance (calendar-spread), satisfies Durrleman's butterfly condition, and
  is linear in |moneyness| at the extremes; the DFW baseline in the paper smugly produces *negative*
  butterfly and calendar-spread penalties where a constrained model produces zero. The repo's own
  RND paper certifies against call bounds, strike monotonicity, vertical-spread slopes, convexity,
  and calendar monotonicity.
- **Repo surface**: `tradingagents/strategies/options_surface.py::surface_shape` (line 201) and
  `rn_skew_proxy` (line 489) consume a chain but never test the chain for static arbitrage;
  `options_math.py::black_vol_surface` (line 199) reads a variance-time surface with no constraints.
- **Status**: `absent` — there is no function that returns per-condition arbitrage flags over a
  chain or a fitted surface (the only related check is put–call parity in `parity_violation`, which
  is a different restriction).
- **Concrete step**: Add `static_arbitrage_flags(rows)` to `options_surface.py`: positivity,
  monotonicity of total implied variance in T for matched strikes, vertical-spread convexity in K,
  and Durrleman's condition, each returning `None`/flag/basis rather than a fabricated pass, and
  surface it in `get_vol_surface_shape`.

### L4. No SVI (or other convenient parametric) slice fit
- **Source**: `arXiv 2607.27188` (2026); `arXiv 2106.07177` (2021) — Arbitrage-Free SVI.
- **Finding**: On held-out NIFTY prices SVI (RMSE 0.000241) is the strongest classical fit behind the
  two-component mixture (0.000166) and far ahead of adapted learned operators (0.003464); Gatheral–
  Jacquier SVI carries closed-form static-arbitrage conditions. But the IVS-prediction paper finds
  *calibrated* surface-SVI parameters too volatile to forecast, so SVI is useful as a per-slice
  smoother/benchmark, not as a state vector.
- **Repo surface**: `(new module)` — no `svi` symbol exists anywhere under `tradingagents/`; the
  nearest surface is `options_math.py::black_vol_surface` (line 199), a variance-time read, not a
  parametric slice.
- **Status**: `absent`.
- **Concrete step**: Add an arbitrage-free SVI slice fit (`raw SVI` five-parameter per expiry, then
  Gatheral–Jacquier butterfly/calendar constraints) returning the slice params, fitted IVs, and a
  per-slice residual; use it as a second candidate in `rnd_recovery.py` (alongside the mixture) so the
  record carries the paper's classical baseline.

### L5. Prefer the IV spread and risk-neutral skewness over the smirk; condition any implied predictor on regime
- **Source**: `arXiv 2608.26115` (2026) — Option-Implied Signals and Crash Risk.
- **Finding**: The Xing smirk decays monotonically across regimes and reverses sign in the
  2023–2026 AI/mega-cap regime, while the Cremers–Weinbaum IV spread and a Bakshi-style risk-neutral
  skewness survive in every regime and specification (|t| > 4). Option-implied slope reads are
  regime-conditional, not constants.
- **Repo surface**: `tradingagents/strategies/options_surface.py::rn_skew_proxy` (line 489), gated by
  `enable_rn_skew_proxy` (`default_config.py:306`, default off) and wired in
  `analysis_tools.py::get_vol_surface_shape` (line 10123, `proxy_gate` at line ~10203).
- **Status**: `partial` — the proxy exists and correctly carries a `regime_cell`/`conditioned` flag,
  but it is the *cross-strike IV sample slope*, not the matched-strike IV spread, and it is off by
  default.
- **Concrete step**: Add a matched-strike `iv_spread(atm_call_iv, atm_put_iv)` producer beside
  `iv_skew` (line 33) and render both `rn_skew_proxy` and `iv_spread` with the regime cell in
  `get_vol_surface_shape`, so the analyst cites the survivor signals rather than the smirk.

### L6. The VIX roll is a term-structure *slope* the repo already measures, but there is no roll-yield read
- **Source**: `arXiv 1907.00293` (2019) — Tracking VIX with VIX Futures.
- **Finding**: VIX futures returns have statistically significant *negative* intercepts that grow
  with the holding period (roll drag), the term structure is typically upward-sloping/concave
  (contango) and inverts under stress, and no static futures portfolio tracks VIX — a rolling long
  position loses even when spot is unchanged.
- **Repo surface**: `tradingagents/dataflows/cboe.py::vix_term_structure` (VIX9D/VIX3M levels, slope,
  `contango`/`backwardation` state) and `tradingagents/strategies/regime_score.py::vix_term_structure`
  (line 408), which aligns on the scale-free ratio.
- **Status**: `partial` — the real VIX term structure (index levels) is shipped and explicitly
  guarded against substitution by the equity-IV slope, but there is no VIX-futures curve and no roll-
  yield/contango-magnitude estimate.
- **Concrete step**: Derive an implied roll carry from the VIX9D/VIX3M slope (annualized per roll) and
  return it in `vix_term_structure` with a `basis` line stating it is an *index-slope* proxy for the
  futures roll, not a futures curve — never a silent substitution.

### L7. Model-free implied variance is biased by tail extrapolation; corridor IV is the unbiased read
- **Source**: `arXiv 1208.4831` (2012) — Fractional Cointegrating Dynamics of Implied–Realized Vol.
- **Finding**: Corridor implied volatility (a fixed finite strike band) is the *unbiased* long-run
  forecast of realized volatility, while full-integral MFIV introduces bias through noisy far-OTM
  quotes; the dependence is concentrated at low frequencies.
- **Repo surface**: `tradingagents/strategies/options_math.py::model_free_implied_variance` (line 399,
  Cboe full-integral form) and `variance_swap_strike` (line 244, OTM trapezoid).
- **Status**: `partial` — both are shipped and `rnd_recovery.py` carries them as anchors, but neither
  is a *corridor* measure over an explicit moneyness band, and `model_free_implied_variance` uses the
  full observed strike range.
- **Concrete step**: Add `corridor_implied_variance(strikes, prices, forward, t, band)` integrating
  OTM prices only over `[αF, βF]`, and report it beside `model_free_implied_variance` in
  `rnd_recovery`'s record so the tail-extrapolation bias is visible per chain.

### L8. Put–call parity recovers a rate, but the year-end funding wedge is not an arbitrage
- **Source**: `arXiv 2609.20224` (2026) — The Year-End Toll.
- **Finding**: Regressing same-maturity call−put spreads on strike identifies the option-implied
  discount factor precisely, but a 2–3 bp unannualized fixed wedge appears the moment maturity first
  crosses December 31; the option funding basis also covaries with funding conditions. Parity
  identifies the rate, not its economic purity.
- **Repo surface**: `tradingagents/strategies/options_surface.py::parity_violation` (line 578),
  wired in `analysis_tools.py::get_parity_screen` (line ~10294).
- **Status**: `partial` — it flags |violation|/S above a caller `cost_bps` against a caller-supplied
  `r`, but it neither extracts an implied rate from the strike slope nor knows a maturity crosses a
  reporting boundary.
- **Concrete step**: Add `implied_discount_factor(strikes, calls, puts)` that regresses C−P on K,
  returns the slope-derived factor/rate and residual, and tag maturities crossing Dec-31 so a
  detected "violation" carries whether it is a funding-boundary wedge rather than an arb.

### L9. Implied skew overreacts to price moves; a computed overreaction read is absent
- **Source**: `arXiv 0809.3375` (2008) — Smile Dynamics and the Implied Leverage Effect.
- **Finding**: The implied leverage coefficient γ(T) from market ATM vols lies between the sticky-
  strike and sticky-delta bounds but overstates the historical leverage effect by ~50% at short
  maturities and ~100% at long maturities; strength rises logarithmically with market cap.
- **Repo surface**: `tradingagents/strategies/options_surface.py::iv_skew` (line 33) and
  `surface_shape` (line 201); `volatility_models.py::semivariance` (line 68) measures the return-side
  asymmetry but is not linked to the smile.
- **Status**: `absent` — no function regresses ΔATM IV on the return (the implied leverage) or compares
  it to the historical leverage correlation implied by the repo's own return series.
- **Concrete step**: Add `implied_leverage(at_iV_changes, returns)` returning γ and flagging
  overreaction against a sticky-strike upper bound derived from the historical leverage term
  (`volatility_models.semivariance` asymmetry / a lagged return-squared correlation).

### L10. Density forecasts need a scoring rule; the repo has RND recovery with no calibration score
- **Source**: `arXiv 1801.08007` (2018) — Financial Density Forecasts.
- **Finding**: Risk-neutral densities beat historical ones on information content; Variance Gamma
  gives the best likelihood/lowest errors and GJR-FHS is most consistent, while lognormal, Heston and
  Breeden–Litzenberger are biased and rejected. Validation uses PIT/Berkowitz, the log score, and a
  return-based CRPS.
- **Repo surface**: `tradingagents/strategies/book_risk.py::var_coverage_test` (line 1082) and
  `evaluate.py` (cost-aware evaluation harness) exist, and `rnd_recovery.py` produces a density, but
  nothing scores the recovered density against realized outcomes.
- **Status**: `absent` — no PIT/CRPS/log-score producer consumes an RND.
- **Concrete step**: Add `rnd_score(density_cdf_or_samples, realized, history)` computing PIT,
  log-score and CRPS, and emit it in the `get_options_iv_read` RND read beside the recovered density,
  so a density claim carries an out-of-sample calibration number.

### L11. Signed option-volume imbalance (OVI) has no producer
- **Source**: `arXiv 2201.09319` (2022) — Option Volume Imbalance.
- **Finding**: OVI (call buys + put sells − call sells − put buys, normalized) predicts excess
  overnight returns; the signal concentrates in market-maker volumes, in high-implied-volatility
  contracts, and puts carry more information than calls.
- **Repo surface**: `(new module)` — `dataflows/yfinance_options.py` (line 68) and `cboe.py` supply
  only *unsigned* aggregate volume/open interest; `strategies/orderflow.py` is equity order flow with
  no option signing.
- **Status**: `absent` — no signed option-volume decomposition exists, and the free vendors available
  here do not sign trades, so the honest form is a documented proxy or a refusal.
- **Concrete step**: Add `ovi_proxy(put_volume, call_volume, opening_put_oi, opening_call_oi)` that
  returns a *proxy* (OI-change-signed volume is the only free approximation) with an explicit
  `basis` stating it is not the exchange-signed OVI, plus a refusal path when only unsigned totals
  exist.

## 4. Where this repo is already ahead of the literature

- **Identifiability is a gate, not a footnote.** `rnd_recovery.py` derives the sensitivity spectrum of
  the covered strikes and refuses with the reason when the density is not identified. Most RND papers
  (including several booklist entries) report a fit and no identifiability diagnostic; this matches the
  strongest 2026 result (2607.27188) and operationalizes it.
- **The learned-operator decline is recorded with its evidence.** `rnd_recovery.py`'s card states the
  classical per-expiry mixture beat the adapted learned operator on held-out quotes and declines to
  train a surrogate — the exact conclusion of 2607.27188, written as a decision rather than an
  aspiration.
- **No silent substitution of equity-IV slope for the VIX term structure.** `regime_score.py` §4 and
  `dataflows/cboe.py::vix_term_structure` both refuse to feed `options_surface.term_structure_slope`
  in as a VIX read — a discipline the older IV-prediction literature does not enforce (2106.07177's
  own SVI-parameter remark highlights the reverse failure).
- **Dealer-gamma sign convention and levels.** `derivatives_gamma.py` documents the GEX sign
  convention (call OI positive dealer gamma, put OI negative), renders top-|GEX| strikes as explicit
  price levels with distance-to-spot, and labels GEX/zero-gamma "market-structure heuristics with weak
  standalone predictive evidence" — the practitioner read (2512.17923) without the over-claim.
- **Parity is screened against costs, not called an arbitrage.** `parity_violation` requires
  |violation|/S to exceed `cost_bps` before flagging; the year-end-toll paper (2609.20224) is the
  caution that even that is not purity, which the repo already states by labelling it a "screen, not a
  trade".

## 5. Defects or risks the literature exposes

- **Unresolvable citation in the RND module.** `tradingagents/strategies/rnd_recovery.py:1` cites
  "V3, 2512.xxxx" for the two-component-lognormal-mixture method, but the method, the 524 held-out
  NIFTY calls, and the declined learned operator match `arXiv 2607.27188v1` (2026) exactly. A
  placeholder id is not a citable source; the docstring and card should cite the real id.
- **An unwired calculator.** `tradingagents/strategies/derivatives_gamma.py:184` defines `max_pain`,
  but a repo-wide search finds no reference outside that module (the only other match is the
  *retired* `max_pain_dist_atr` in `technical_score.py:252`). Under the repo's own rule that "a
  calculator that never reaches a tool loop is incomplete work" (SURFACE.md), `max_pain` is dead
  weight or an unexposed read; either wire it or delete it.
- **Parity violations can be year-end funding wedges, not arbitrage.**
  `tradingagents/strategies/options_surface.py:578` (`parity_violation`) flags any |violation|/S above
  `cost_bps` as `call_rich`/`put_rich` with no notion of a maturity crossing December 31. Per
  `arXiv 2609.20224v1`, a contract first spanning a year-end carries a systematic 2–3 bp unannualized
  price wedge that behaves exactly like a small parity violation; on such a chain the repo's screen
  will produce a false positive that is a funding-boundary effect, not a conversion/reversal.
- **The VRP read is a trailing-window vol spread, which the literature treats as an upward-biased
  proxy.** `tradingagents/strategies/options_surface.py:140` computes IV minus a *realized* vol. The
  canonical construction (`arXiv 2608.26115v1`, summarising Bollerslev et al., and the H₀ test in
  `arXiv 2009.09770v1`) is implied variance minus *expected* realized variance, and the implied–realized
  unbiasedness result (`arXiv 1208.4831v2`) shows full-range MFIV is itself biased. A trailing
  realized-vol difference therefore mixes two biases; it is a descriptive read, not a harvestable
  premium, and should not be cited as one.

## 6. Limits of this review

- **Read depth.** 16 papers were read at depth (abstract through conclusion or method/results), the
  strongest being 2607.27188, 2106.07177, 0809.3375, 2608.26115, 1907.00293, 2201.09319 and 2609.20224;
  several (1407.5528, 2607.08500, 2411.02804, 1702.02777, 2604.03499) were read at abstract +
  intro + primary method/results only. The remaining 24 high-relevance and 163 medium-relevance
  papers were swept at the abstract level via the evidence pack, not read.
- **Sampling.** The category is large (234) and heavily duplicated across neighbouring slices
  (crypto/volatility/ML-methods books overlap the neural-hedging and neural-surface papers). Deep
  reads were chosen for direct application to the six named option modules rather than for bibliometric
  completeness; the RND/identifiability, no-arbitrage, VRP, VIX-roll, parity and cross-sectional-
  predictor themes each have at least one deep read.
- **Not verified.** Exact replication of the papers' numbers was not attempted; the quantitative
  claims are quoted from the papers. Repo status was verified by reading the named modules and by
  `grep` for symbol usage, but no test, linter or runtime check was executed (per the standing rule
  not to run repo tests). The `max_pain` "unwired" finding is a static-reference search, not a
  runtime reachability proof.
- **Not covered.** Full-text reading of SABR/Hagan asymptotic corrections (0708.0998), the
  neural-SDE market-model line (2105.11053, 2202.07148, 2205.15991), the FuNVol / normalization-flow
  surface simulators, and the crypto/jump-diffusion pricing papers was not done; they are noted in the
  evidence pack and left for the ML-methods or crypto books.
