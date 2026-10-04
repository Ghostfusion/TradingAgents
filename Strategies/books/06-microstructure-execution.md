# Market Microstructure, Liquidity & Execution

`book 06/19` · slug `microstructure-execution` · 703 papers in the corpus · 98 rated high-relevance by the sweep

## 0. Scope

This category covers how prices actually form and how size moves them: order-flow imbalance and its decay, price-impact laws (Kyle lambda, Amihud, the square-root law, Almgren-Chriss), optimal execution scheduling (TWAP/VWAP/POV/IS), spread estimation from daily OHLC, intraday seasonality and U-shape, opening-range and gap behaviour, limit-order-book imbalance, and the honest-testing evidence on intraday momentum signals. It matters to this repo because the whole engine is a *compute-don't-narrate* decision stack whose weakest physical link is the cost and tradability model: every "is this liquid enough / what will this cost / can I realistically fill it" claim an analyst makes resolves here. It is also where the corpus is most sceptical, which is useful — the honest-evaluation papers in this category are directly reusable gates.

## 1. Corpus composition

| decade | top-60 booklist | 98 high-relevance rows | 703-paper category |
| --- | --- | --- | --- |
| 1990s | 0 | 0 | (not itemised) |
| 2000s | 4 | 12 | (not itemised) |
| 2010s | 18 | 32 | (not itemised) |
| 2020s | 38 | 54 | (not itemised) |
| **total** | **60** | **98** | **703** |

Counts used: the evidence pack's category totals (`703` annotated sweep rows = 98 high / 462 medium / 143 low); the booklist's 60 full-metadata papers (years 2006–2026); and the 98 high-relevance rows parsed out of the evidence pack's high table.

The category is dominated by limit-order-book statistical physics and high-frequency order-flow modelling, including Hawkes-process intensity models, propagator/impact kernels, and deep-learning LOB predictors. The practically load-bearing subset — impact laws, execution schedules, spread estimation, and cost-honest signal tests — is a minority of the category but is where every repo-relevant learning sits. A large tail is electricity/energy intraday-market forecasting, which the sweep over-collected because it shares the words "intraday" and "order book" and is irrelevant here.

## 2. Deep reads

### arXiv 1011.6402v3 — The price impact of order book events (Cont, Kukanov, Stoikov, 2011)
- *Question*: can the impact of market orders, limit orders and cancellations be collapsed into one variable?
- *Data*: NYSE TAQ, 50 U.S. stocks.
- *Method*: define Order Flow Imbalance (OFI) — bid/ask queue-size changes plus price moves at the best quotes — and regress mid-price change on it; derive slope against a stylized book model.
- *Findings*: mid-price changes are linear in OFI with average R² ≈ 65% (vs ≈ 32% for trade imbalance); the slope is inversely proportional to market depth; the slope has intraday seasonality; the "square-root" price-vs-volume relation is a statistical artifact of aggregation, not a robust law.
- *Limitation*: OFI requires quote-event data; the model's slope must be re-estimated per name/depth regime and does not hold for volume directly.

### arXiv 1102.5457v4 — How efficiency shapes market impact (Farmer, Gerig, Lillo, Waelbroeck, 2013)
- *Question*: why is metaorder impact concave when market-clearing theory predicts linear impact?
- *Method*: stylized model of an algorithmic execution service with competitive informed traders, plus a *fair-pricing condition* (average transaction price = post-execution price).
- *Findings*: at equilibrium the volume distribution adjusts to information and dictates the impact shape; large-trade Pareto tails give impact rising roughly as the **square root of metaorder size**, with permanent impact relaxing to ≈ two-thirds of peak.
- *Limitation*: closed-form results depend on the assumed (Pareto) metaorder size distribution; it is a theory of averages, not a per-order forecast.

### arXiv 1802.08502v5 — Market Impact: A Systematic Study of Limit Orders (Said, Bel Hadj Ayed, Husson, Abergel, 2022)
- *Data*: proprietary European-equity metaorder database, Jan 2016 – Dec 2017, reconstructed algorithmically.
- *Method*: measure temporary and permanent impact separately for **aggressive** and **passive** limit orders.
- *Findings*: temporary impact obeys a power law in both cases; long-term impact stabilises at ≈ two-thirds of maximum; the fair-pricing condition is empirically validated. The default institutional order type is a limit order, so impact studies based only on market orders miss the main cost channel.
- *Limitation*: proprietary single-venue data; metaorders are reconstructed by algorithm, not tagged by the parent.

### arXiv 2606.24019v1 — Empirical Confirmation of the Square-Root Law of Market Impact in a U.S. Large-Cap Equity (Vasaikar, 2026)
- *Data*: Nasdaq TotalView-ITCH market-by-order, AAPL, 178 days (Dec 2024 – Aug 2025), ~0.5B events.
- *Method*: reconstruct metaorders from anonymous flow as dominant-side 30s-bin runs; fit I/(σ·V_D) = c·(Q/V_D)^{1/2} with the exponent **fixed** at 1/2.
- *Findings*: c_raw = 0.69 (bias-corrected c_eff = 0.34); model comparison decisively prefers square-root over linear (ΔAIC = 22) and logarithmic; sign-shuffling collapses directional impact 86% → 51%; chronology-scrambling destroys the law (0/80 fits viable); sign autocorrelation γ = 0.66 while the price stays diffusive (Hurst 0.49); size tail β = 1.54 ± 0.15; walk-forward c_raw stable at 0.75 over 32 weeks.
- *Limitation*: one name, one venue, 20-day calibration window; exponent assumed universal rather than estimated.

### arXiv 0904.0900v3 — The price impact of order book events: market orders, limit orders and cancellations (Eisler, Bouchaud, Kockelkoren, 2018)
- *Data*: order-by-order European/US equity data.
- *Method*: extract the "bare" impact each event would have in isolation; compare permanent vs history-dependent impact.
- *Findings*: for **large-tick** stocks the bare impact of all events is permanent and non-fluctuating; for **small-tick** stocks the bare impact needs a history-dependent (autoregressive) part reflecting internal book fluctuations. Impact decomposes into an instantaneous jump, modification of future event rates, and modification of future jump sizes.
- *Limitation*: no single model works across tick regimes; the tick-size classification is the conditioning variable.

### arXiv 1206.0682v1 — Calibration of optimal execution under transient market impact (Busseti, Lillo, 2012)
- *Question*: how do you solve and calibrate optimal execution when impact decays (Bouchaud propagator) rather than being purely instantaneous/permanent?
- *Method*: Bouchaud transient-impact model, solved analytically for risk-neutral and risk-averse investors; efficient frontier derived.
- *Findings*: transient impact is estimable in aggregated trade time or real time; adding spread costs forces a numerical solution and *regularises* it — spread costs are a stabiliser, not just a cost term.
- *Limitation*: model is linear in impact and needs a decay kernel estimate, which is noisy at short lags.

### arXiv 1210.7608v3 — Execution and block trade pricing with optimal constant rate of participation (Guéant, 2013)
- *Question*: how should a POV (percentage-of-volume) strategy choose its participation rate?
- *Method*: CARA-utility liquidation with linear permanent impact and convex instantaneous cost L(ρ) = ηρ^{1+φ}, optimised over the single parameter ρ; risk-liquidity premium derived.
- *Findings*: for flat volume a unique closed-form optimum **ρ\* = (γσ²q₀ / (6ηφV))^{1/(1+φ)}**; POV is suboptimal vs IS but is the desk default, and the risk-liquidity premium prices blocks.
- *Limitation*: deterministic volume curve; assumes constant participation, which forfeits the IS optimum's adaptivity.

### arXiv 1908.04333v1 — Random walk model from the point of view of algorithmic trading (Danyliv, Bland, Argenson, 2019)
- *Question*: what is the cost of a static passive slice (post at a limit, go aggressive if unfilled)?
- *Method*: exact binary-tree/reflection-probability solution for a symmetric random walk; induction on the limit level k.
- *Findings*: expected gain is **exactly zero for every limit level** — passive execution costs the same as immediate aggressive execution and has no optimal level. Matches Goldman's Piccolo algorithm (19,821 passive child orders 4.6 bps vs 6,919 aggressive 4.1 bps; 48% captured the spread, but cleanup cost ate it).
- *Limitation*: ignores queue position and adverse selection; only a zero-order approximation for fast liquid markets.

### arXiv 2407.17401v3 — Estimation of bid-ask spreads in the presence of serial dependence (Brouty, Garcin, Roccaro, 2025)
- *Question*: which OHLC-based spread estimators survive when price/noise are serially dependent (fBm price, OU noise)?
- *Method*: moment estimators at two time scales, with asymptotic normality for H ≤ 3/4; 10,000 simulated daily paths; bootstrap relevance test; benchmarks Roll, Corwin-Schultz (CS), Abdi-Ranaldo (AR), Ardia-Guidotti-Kroencke (AGK₁, AGK₂).
- *Findings*: **CS and AGK₂ are rejected** (biased but low-variance — overconfident). Roll has the lowest bias in the no-dependence baseline but systematically **underestimates** the spread when H > 0.5. Simplest moment estimators over/under-estimate by the sign of H − 1/2; only their autocorrelated-trade estimator avoids underestimation.
- *Limitation*: simulation-based; real intraday correlation structure is only approximately OU/fBm.

### arXiv 1812.07369v1 — Emergence of stylized facts during the opening of stock markets (Fiegen, Krause, Guhr, 2018)
- *Data*: Nasdaq TotalView-ITCH, 96 stocks, 5 days (Mar 2016).
- *Method*: reconstruct visible order books; activity-adaptive moving average of the relative spread.
- *Findings*: after a highly fluctuating opening burst, rescaled spreads for many stocks **collapse onto one slow power-law decline** over the whole day — a non-stationary state, not a constant. 30/96 large-tick stocks instead close to the one-tick floor within ~10 minutes. Opening-period duration varies widely by stock.
- *Limitation*: 5 days, one venue; the adaptive smoothing is a method choice, not a physical model.

### arXiv 2607.01377v1 — Liquidity Premium and Investment Horizons (Aldridge, 2026)
- *Data*: CRSP universe, daily/monthly, 2020–2025.
- *Method*: estimate Kyle's λ two ways — a within-month price-impact regression and an Amihud-style ratio — from signed order flow; panel and Fama-MacBeth regressions.
- *Findings*: signed order flow strongly predicts contemporaneous and one-month-ahead returns, dominating unsigned volume and surviving size/BM/momentum/Amihud controls; volume volatility predicts *lower* subsequent returns. Resolves the liquidity-premium puzzle via adverse selection (low signed flow widens λ and depresses prices; normalisation restores them), not risk compensation.
- *Limitation*: λ̂ sign and magnitude are specification-sensitive; result is a cross-sectional/relative read, not an absolute impact quote.

### arXiv 1907.06230v2 — Multi-Level Order-Flow Imbalance in a Limit Order Book (Xu, Gould, Howison, 2019)
- *Data*: 6 liquid Nasdaq stocks, LOBSTER-style order-by-order data.
- *Method*: extend OFI to an M-dimensional MLOFI vector over the M best populated levels; fit mid-price change linearly.
- *Findings*: out-of-sample goodness-of-fit **improves with every added price level** for all 6 stocks; OFI (level 1) already achieves ≈65% R² vs ≈32% for trade imbalance; order activity deep in the book carries real price-formation content.
- *Limitation*: contemporaneous linear fit, single-asset, small cross-section; no economic-gain test.

### arXiv 2112.13213v4 — Cross-Impact of Order Flow Imbalance in Equity Markets (Cont, Cucuringu, Zhang, 2023)
- *Data*: Nasdaq ITCH/Lobster, top-100 S&P 500, 2017–2019.
- *Method*: integrate multi-level OFIs into a single "integrated OFI"; compare same-level, integrated, and cross-asset regressions; then test lagged cross-OFI for return forecasting.
- *Findings*: PC1 of multi-level OFIs explains 89% of variance; once integrated OFI is used, contemporaneous cross-impact terms add **no** explanatory power; but **lagged** cross-asset OFI predicts short-horizon (up to a few minutes) returns with rapid decay.
- *Limitation*: contemporaneous results are in-sample-heavy; cross-asset forecasting edge is short-lived and trading-cost sensitive.

### arXiv 2605.04004v3 — Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures (Mesfin, 2026)
- *Data*: 947 RTH days, MNQ 5-minute OHLCV, Dec 2021 – Aug 2025.
- *Method*: 14 signal families under expanding-window walk-forward; five simultaneous gates (OOS T ≥ 2, ≥ 30 trades/fold, positive net of 2.0-point round-trip friction, direction stable across 2023/24/25, permutation p < 0.05).
- *Findings*: **none pass all five**. 11 families never clear the friction floor (gross 0.07–1.50 pts vs 2.0-pt friction). Opening-range-breakout long net +2.82 pts, T = 0.88 — fails T and year stability. VVG reversal net +13.49 pts, T = 1.26 on 35 OOS trades — fails. Gap-continuation short net +14.52 pts, T = 1.46 — fails year stability and trade count. Two structurally different positive-control signals (session-confluence, London-session) pass with margin, showing the protocol is not a universal rejecter.
- *Limitation*: one instrument, one decade, 5-minute bars; failure is about *single-bar OHLCV pattern prediction*, not about all intraday structure.

### arXiv 2605.11423v3 — A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday Data (Mesfin, 2026)
- *Data*: same 947 MNQ days.
- *Method*: VVG-positive when the first-30-minute return, the overnight gap and the first-bar volume z-score are all in their expanding-window top tercile (no lookahead).
- *Findings*: activates on 40/947 days (≈4.2%); classifier days show 25.6 bp higher next-day return spread; 77.6% reverse from an intraday peak (mean giveback 11.73 pts), peaking 14:00–15:30; the sign is regime-dependent (2024 closed +40.74 pts, 2025 −42.48). **Eight directional configurations all fail** (best T = 1.46, 127 OOS trades).
- *Limitation*: 40 positive days, ~10/year; the classifier is a valid *volatility/regime* flag with no deployable directional edge.

### arXiv 2502.07625v1 — Intraday order transition dynamics by market cap: a Markov chain approach (Luwang et al., 2025)
- *Data*: tick-by-tick Nasdaq-100 listed stocks, split high/medium/low cap.
- *Method*: first-order discrete-time Markov chains on order-type transitions, estimated per intraday hour.
- *Findings*: limit-order degree of inertia peaks in the **opening hour**, then falls while market-order inertia rises; limit-order additions/deletions surge after the open; executions surge as the close approaches; inertia is stronger for high/medium-cap names, while low-cap names show more modifications and more reactive limit submissions. Transitions cluster except at open and close.
- *Limitation*: time-homogeneous within each hour; no cost or profitability claim.

### arXiv cond-mat/0406696v1 — Short-term market reaction after extreme price changes of liquid stocks (Zawadowski, Andor, Kertész, 2004)
- *Data*: NYSE TAQ 2000–2002 and Nasdaq, minute bars, liquid names.
- *Method*: identify large intraday price changes in transaction price **and** in the bid-ask midpoint; measure subsequent reversal and the cost of a contrarian strategy.
- *Findings*: significant short-term reversal follows both large up and down moves. On the NYSE the post-event **bid-ask-spread widening eliminates most contrarian profit**; on Nasdaq the spread stays roughly flat so the profit survives. Volatility, volume and (NYSE) spread decay as power laws and stay elevated for days.
- *Limitation*: 2000–2002 market structure (pre-decimalisation-era venue differences); the reversal is statistically robust but economically venue-dependent.

### arXiv 2511.07434v1 — RL-Exec: Impact-Aware Reinforcement Learning for Opportunistic Optimal Liquidation (Duflot, Robineau, 2025)
- *Data*: BTC-USD LOB; train Jan 2020, test Feb 2020, per-day protocol with 10 intra-day starts.
- *Method*: PPO agent on depth-20 features with endogenous transient impact, partial fills, maker/taker fees and latency; baselines TWAP and a book-liquidity VWAP on identical timestamps/costs; one-sided Wilcoxon with BH-FDR.
- *Findings*: significant gains growing with horizon: +2.25–2.68 bps at 1,800s, +7.59–7.70 bps at 3,600s, +22.96–23.02 bps at 7,200s vs both baselines.
- *Limitation*: one month of test data, one asset class; the replay environment's simplicity is itself a confound.

### arXiv 2502.13722v2 — Deep Learning for VWAP Execution in Crypto Markets: Beyond the Volume Curve (Genet, 2025)
- *Question*: is forecasting the volume curve the right intermediate step for VWAP execution?
- *Method*: allocate order volume with a network whose custom loss directly minimises absolute/quadratic VWAP slippage, bypassing volume-curve prediction.
- *Findings*: direct-objective optimisation consistently lowers VWAP slippage vs conventional two-step methods, even with a naive linear allocator; VWAP-optimal allocation *diverges* from accurate volume-curve prediction because prediction error is unavoidable.
- *Limitation*: crypto, static allocation, no live-volume feedback; findings are about a benchmark objective, not profitability.

### arXiv 2510.24467v1 — The Omniscient yet Lazy Investor (Halkiewicz, 2025)
- *Question*: is there an optimal trading *frequency* under execution frictions?
- *Method*: deterministic geometric construction plus an fBm extension; derive closed-form expected profit in (frequency, cost, path roughness).
- *Findings*: a unique optimal frequency exists and is interpretable through the price path's fractal dimension / Hurst exponent; comparative statics follow from roughness.
- *Limitation*: perfect foresight is a stylised upper bound; the frequency optimum is a benchmark, not an implementable rule.

## 3. Learnings applicable to this repo

### L1. Quote-based order-flow imbalance is the right price-pressure primitive, and the repo computes a snapshot proxy
- **Source**: `arXiv 1011.6402v3` (2011) — The price impact of order book events; corroborated by `arXiv 1907.06230v2` (2019).
- **Finding**: mid-price change is linear in OFI with average R² ≈ 65% (vs ≈ 32% for trade imbalance), the slope ∝ 1/depth, and every added LOB level improves out-of-sample fit.
- **Repo surface**: `tradingagents/strategies/orderflow.py` (capital-flow bucket layer, no quote-event OFI) and `tradingagents/strategies/market_session.py::book_depth_read` (snapshot microprice + OBI from one quote pair).
- **Status**: absent. Verified: `orderflow.py` operates on moomoo capital-flow buckets (`tier_nets`, `distribution_score`, `vpin`) and has no OFI accumulator; `book_depth_read` is a single-snapshot OBI, not an event-aggregated OFI.
- **Concrete step**: add an OFI accumulator keyed on (bid, ask, bid_size, ask_size) transitions alongside `book_depth_read`, and reuse the exact same sign convention (`market_session.book_depth_read`'s OBI is the endpoint of that vector); the data dependency is a quote-event feed the repo does not currently carry.

### L2. Impact shape must be square-root, and the repo carries three mutually inconsistent shapes
- **Source**: `arXiv 2606.24019v1` (2026) — square-root law on AAPL (c_raw = 0.69); `arXiv 1102.5457v4` (2013) — √Q theory.
- **Finding**: I/(σ·V_D) = c·(Q/V_D)^{1/2} with c ≈ 0.69; linear and logarithmic forms are decisively rejected (ΔAIC = 22); the exponent 1/2 survives sign-shuffle and chronology nulls.
- **Repo surface**: `tradingagents/strategies/backtest_models.py::square_root_impact` (√, k≈0.1), `tradingagents/strategies/liquidity_risk.py::volume_share_slippage` (quadratic in participation, line 325), `tradingagents/strategies/liquidity_risk.py::market_impact_slippage` (linear, line 348).
- **Status**: partial. All three verified present; the √ model lives in the backtest harness while the live-cost paths use quadratic/linear forms.
- **Concrete step**: pick √ as the single default cost shape for advisory impact reads and document `k` against the measured c (0.69 raw / 0.34 bias-corrected in `I/(σ_D√(Q/V_D))` units), rather than leaving three shapes for callers to choose between.

### L3. Permanent impact relaxes to ≈ two-thirds of peak and the fair-pricing condition holds
- **Source**: `arXiv 1102.5457v4` (2013) — How efficiency shapes market impact; `arXiv 1802.08502v5` (2022) — limit-order impact.
- **Finding**: temporary impact is a concave power law; long-term impact stabilises at ≈ 2/3 of maximum; average execution price equals the post-completion price (fair pricing) across a proprietary European-equity metaorder sample.
- **Repo surface**: `tradingagents/strategies/execution_schedule.py::almgren_chriss` (linear permanent `gamma`, no decay-to-2/3).
- **Status**: absent. Verified: `almgren_chriss` implements `e_is = 0.5*gamma*X^2 + eta*Σv_t^2` with no permanent/temporary split ratio and no fair-pricing check.
- **Concrete step**: add an optional `permanent_fraction` (default 0.667) applied to the peak impact and expose a fair-pricing residual (execution VWAP vs post-trade mid) as a reported read in the execution result.

### L4. The optimal POV participation rate has a closed form the repo ignores
- **Source**: `arXiv 1210.7608v3` (2013) — optimal constant rate of participation.
- **Finding**: with L(ρ) = ηρ^{1+φ} and flat volume, the CARA-optimal rate is ρ\* = (γσ²q₀ / (6ηφV))^{1/(1+φ)}; POV is suboptimal vs IS but its single-parameter optimum is communicable and yields a closed-form risk-liquidity premium.
- **Repo surface**: `tradingagents/strategies/execution_schedule.py::pov_schedule` (fixed `participation: float = 0.10`).
- **Status**: partial. The schedule builder exists and is wired (`analysis_tools.py:13087` calls it at 0.10) but participation is a caller constant, not derived.
- **Concrete step**: add an optional participation solver taking (risk aversion, sigma, q₀, eta, phi, V) and emitting ρ\* (plus its inputs) as an advisory default for `pov_schedule`.

### L5. Passive limit execution is zero-EV on a random walk — do not credit spread capture
- **Source**: `arXiv 1908.04333v1` (2019) — exact binary-tree solution; Goldman Piccolo evidence.
- **Finding**: expected gain is exactly zero for every limit price; all levels cost the same as immediate aggressive execution. Measured child orders: 4.6 bps passive vs 4.1 bps aggressive, despite 48% capturing the spread.
- **Repo surface**: `tradingagents/strategies/execution_price.py::execution_price` and `tradingagents/strategies/execution_schedule.py` (no passive/limit-order cost term).
- **Status**: absent. Verified: `execution_price` prices only the cost terms the caller measured (spread/impact/slippage as fractions) and has no passive-capture credit — which is the correct default — but nothing records *why*.
- **Concrete step**: document in `execution_price`'s contract that spread capture by passive posting is not credited absent an alpha/queue model, citing the zero-EV result; this prevents a future caller from "improving" fills by posting.

### L6. Spread-estimator choice is biased, and the repo's aggregate includes the worst estimator
- **Source**: `arXiv 2407.17401v3` (2025) — spread estimation under serial dependence.
- **Finding**: Corwin-Schultz and AGK₂ are rejected by a bootstrap relevance test for bias-with-small-variance (overconfidence) even with no serial dependence; Roll underestimates when H > 0.5; simpler moment estimators over/under-estimate by sign(H − 1/2).
- **Repo surface**: `tradingagents/strategies/liquidity_risk.py::spread_estimate` (median of `corwin_schultz` and `abdi_ranaldo`), `::roll_spread`, `::corwin_schultz`, `::abdi_ranaldo`.
- **Status**: shipped. Verified: all four functions exist; `spread_estimate` returns `median(both)` when both survive.
- **Concrete step**: drop Corwin-Schultz from the aggregate default (prefer Abdi-Ranaldo, or the two-scale moment form) and record the estimator-specific bias in each result's `basis`, since a median over two estimators half-weighted by the rejected one propagates its bias.

### L7. Intraday liquidity follows a U/power-law profile the VWAP scheduler assumes away
- **Source**: `arXiv 1812.07369v1` (2018) — spread collapses to a slow power-law decline; `arXiv 2502.07625v1` (2025) — order-type inertia by session hour.
- **Finding**: after a volatile open, rescaled spreads follow a slow power-law decline across many stocks (large-tick names floor at one tick within ~10 min); order-type mix and throughput shift systematically from open to close.
- **Repo surface**: `tradingagents/strategies/execution_schedule.py::vwap_schedule` (requires a caller-supplied volume list), `tradingagents/strategies/market_session.py` (session reads, no intraday profile).
- **Status**: absent. Verified: `vwap_schedule(X, volumes)` refuses without `volumes`; no module produces a default intraday seasonality curve.
- **Concrete step**: add a default intraday volume/spread profile generator (U-shape with a heavy open and a closing ramp, calibrated to the instrument's own bars where available) so VWAP/AC schedules have a defensible baseline instead of a hand-supplied list.

### L8. Kyle lambda is validated as a cross-sectional return signal, not an absolute quote
- **Source**: `arXiv 2607.01377v1` (2026) — Kyle-lambda liquidity premium.
- **Finding**: signed order flow predicts contemporaneous and one-month-ahead returns after size/BM/momentum/Amihud controls; λ̂ is specification-sensitive in sign and magnitude, so it is usable cross-sectionally and unreliable as an absolute impact number.
- **Repo surface**: `tradingagents/strategies/liquidity_risk.py::kyle_lambda` and `scripts/liquidity_forward_rank.py` (already measures rank IC of `amihud_illiquidity`/`kyle_lambda`).
- **Status**: shipped/partial. Both verified: `kyle_lambda` exists and the forward-rank script already evaluates it forward.
- **Concrete step**: ensure λ is only read as a relative/cross-sectional liquidity rank (never as a per-trade cost quote), and keep the forward-rank harness as the gate before any λ-based cross-sectional signal is enabled.

### L9. Cross-impact and multi-level OFI are real but data-limited here
- **Source**: `arXiv 2112.13213v4` (2023) — cross-impact; `arXiv 1907.06230v2` (2019) — multi-level OFI.
- **Finding**: integrated multi-level OFI removes the need for contemporaneous cross-impact terms; lagged cross-asset OFI predicts returns only over a few minutes and decays fast; PC1 of multi-level OFIs explains 89% of variance.
- **Repo surface**: `tradingagents/strategies/market_session.py::book_depth_read` (level-1 only), `tradingagents/strategies/orderflow.py` (no cross-asset OFI).
- **Status**: absent. Verified: no multi-level or cross-asset OFI producer exists.
- **Concrete step**: record the missing L2/L3 and cross-asset quote feed as the blocking prerequisite (see §5) rather than approximating multi-level OFI from daily bars, which would fabricate the signal.

### L10. Intraday momentum and gap signals must not carry a directional default
- **Source**: `arXiv 2605.04004v3` (2026) — 14 families fail all five gates; `arXiv 2605.11423v3` (2026) — VVG regime valid, direction non-significant.
- **Finding**: opening-range-breakout and gap-continuation have no OOS edge net of friction; a validated gap/volatility regime flag reverses from peak 77.6% of the time but its sign flips by year; the friction floor kills 11/14 families outright.
- **Repo surface**: `tradingagents/strategies/market_session.py::opening_range` (emits a 2R target on any breakout) and `::gap_type`/`::classify_gap` (measured fill stats, advisory).
- **Status**: partial. Verified: `opening_range` returns `target = or_high + 2*width` whenever `breakout == "up"`; `gap_type` reports fill probabilities with a measured/heuristic `basis`.
- **Concrete step**: keep the ORB 2R target as a *reported* structural level and require the `falsification.py` / `rule_eval.py` gate before any consumer treats ORB or gap-continuation as directional edge; the gap fill statistics are already honestly labelled and should stay that way.

### L11. Reversal profits are decided by the spread, which the repo already gates
- **Source**: `arXiv cond-mat/0406696v1` (2004) — extreme-move reversals defeated by NYSE spread widening.
- **Finding**: short-term reversal after large intraday moves is statistically robust, but the contrarian profit survives only where the post-event spread stays flat (Nasdaq); where the spread widens (NYSE) it is eliminated.
- **Repo surface**: `tradingagents/strategies/liquidity_risk.py::liquidity_verdict` (`max_spread_bps` / `spread_bps` inputs), `tradingagents/strategies/mean_reversion.py`.
- **Status**: shipped. Verified: `liquidity_verdict` accepts `spread_bps`/`max_spread_bps` and bumps the verdict to ILLIQUID above the cap; `mean_reversion.py` exists.
- **Concrete step**: verify the mean-reversion path feeds a *measured* spread into `liquidity_verdict` (not merely dollar-volume) before emitting any contrarian entry — the literature's margin is exactly the spread term.

### L12. Transient (decaying) impact, not instantaneous linear impact, is what execution calibration needs
- **Source**: `arXiv 1206.0682v1` (2012) — optimal execution under transient impact.
- **Finding**: the Bouchaud propagator describes both the size and time dependence of impact; optimal trajectories under transient impact differ from Almgren-Chriss, and including spread costs regularises the numerical solution.
- **Repo surface**: `tradingagents/strategies/execution_schedule.py::almgren_chriss` (linear permanent `gamma`, no transient kernel).
- **Status**: partial. Verified: `almgren_chriss` is the linear-impact AC model only; `default_temp_impact` converts a spread into `eta` but there is no decay kernel.
- **Concrete step**: add an optional propagator/decay-kernel mode alongside the AC branch, defaulting off, with the AC result retained as the benchmark trajectory.

## 4. Where this repo is already ahead of the literature

- **No-fabrication spread floors.** `liquidity_risk.corwin_schultz` / `abdi_ranaldo` return `None` when the corrected spread is negative, refusing to clamp — whereas the Abdi-Ranaldo paper's own published treatment floors the sub-root term at zero. The repo's stricter contract is the safer one.
- **Execution-cost provenance contract.** `execution_price.execution_price` returns `NO_SOURCE` for an unmeasured cost term instead of defaulting it to zero; most backtest cost models silently assume free. This matches the literature's repeated warning that mis-measured costs are what kills apparent edge.
- **Spread-implied impact coefficient.** `execution_schedule.default_temp_impact` derives `eta` from a proportional spread and a reference clip, tying the AC temporary-impact term to a measured microstructure quantity rather than a free parameter.
- **Directional VPIN conditioning.** `orderflow.knife_guard_vpin` only suppresses dip-buying when VPIN is high *and* price moved down, addressing the standard critique that VPIN is non-directional — a refinement the VPIN literature itself rarely implements.
- **Mechanical-volume discounting.** `volume_flags.mechanical_volume_flags` / `rvol_ex_mechanical` strip OPEX/witching sessions from RVOL, which almost no OHLCV signal paper does and which the order-flow seasonality literature implies is necessary.
- **Cost-honest signal gates.** `falsification.py`, `rule_eval.py` and `trial_ledger.py` implement exactly the multi-criterion, friction-aware, permutation-tested protocol that `2605.04004v3` and `2607.20093v1` use to refute intraday signals — the repo has the gate before it has the signal.
- **Participation caps with refusal accounting.** `market_tradability.volume_gate` truncates at a participation cap and records the refusal in the H7 ledger, which the execution-cost literature's "participation rate" framing never operationalises.

## 5. Defects or risks the literature exposes

1. **`liquidity_risk.kyle_lambda`'s regressor is a deterministic function of the regressand's sign.** Line 398 builds `q = sign(ΔP)·V`, so `Σ(ΔP−Δ̄P)(q−q̄)` contains `Σ|ΔP|·V > 0` by construction — λ is mechanically positive and its magnitude is not identified from trade direction, only from volume scaling. `arXiv 2607.01377v1` estimates λ from signed order flow (not from the sign of the return); `arXiv 2606.04217v2` (sweep) shows tick-rule signing is close to random (49.8%/50.5%). Repo: `tradingagents/strategies/liquidity_risk.py:398`.
2. **`market_session.order_imbalance` docstring contradicts its code.** The docstring (line 336) states `ratio = inst_net / (|inst_net| + |retail_net|)`, but line 349 computes `(inst + retail) / (|inst| + |retail|)` — the *total* net flow normalized, not the institutional share. A caller reading the contract will mis-scale the ratio by up to 2×. Repo: `tradingagents/strategies/market_session.py:336` vs `:349`.
3. **Three incompatible impact shapes across one cost decision.** `backtest_models.square_root_impact` is √, `liquidity_risk.volume_share_slippage` is quadratic in participation (line 325), and `liquidity_risk.market_impact_slippage` is linear (line 348). The corpus (`arXiv 2606.24019v1`, `arXiv 1102.5457v4`) consistently finds the concave square-root form and decisively rejects linear. Repo: `tradingagents/strategies/liquidity_risk.py:325,348` and `tradingagents/strategies/backtest_models.py:74`.
4. **`spread_estimate` half-weights the estimator the literature rejects.** `liquidity_risk.spread_estimate` returns `median(corwin_schultz, abdi_ranaldo)`; `arXiv 2407.17401v3` rejects Corwin-Schultz as biased with an overconfident variance, even in the no-serial-dependence baseline. The aggregate is therefore not a bias-minimising floor. Repo: `tradingagents/strategies/liquidity_risk.py::spread_estimate`.
5. **Participation policy is inconsistent across three modules.** `market_tradability.volume_gate` caps at 20% of day volume, `liquidity_risk.days_to_absorb` defaults to a 15% participation `alpha`, and `execution_schedule.pov_schedule` defaults to a 10% rate. A 20% cap is far into the regime the square-root-impact literature shows is very costly, and no single policy binds them. Repo: `tradingagents/strategies/market_tradability.py:117`, `tradingagents/strategies/liquidity_risk.py::days_to_absorb`, `tradingagents/strategies/execution_schedule.py::pov_schedule`.
6. **VPIN is only as good as its side labels.** `orderflow.vpin` requires explicit per-trade `{'volume', 'side'}` items. If any caller supplies tick-rule-inferred sides, the sweep row `arXiv 2606.04217v2` reports tick-rule and bulk-volume classification at 49.8%/50.5% accuracy and inferred VPIN diverging — i.e. an input-quality risk that the function cannot detect. Repo: `tradingagents/strategies/orderflow.py::vpin` (with `market_session.book_depth_read` as the only quote-based alternative).

## 6. Limits of this review

- **Read in full text (20)**: `1011.6402v3`, `1102.5457v4`, `1802.08502v5`, `2606.24019v1`, `0904.0900v3`, `1206.0682v1`, `1210.7608v3`, `1908.04333v1`, `2407.17401v3`, `1812.07369v1`, `2607.01377v1`, `1907.06230v2`, `2112.13213v4`, `2605.04004v3`, `2605.11423v3`, `2502.07625v1`, `cond-mat/0406696v1`, `2511.07434v1`, `2502.13722v2`, `2510.24467v1` (abstract, intro, method and results ranges; appendices skimmed).
- **Skimmed via the evidence pack only**: the remaining high-relevance rows, including Hawkes/LOP/LOB-prediction papers and the crypto-market papers, plus the entire medium/low tail. Two sweep rows are cited in §5 (`2606.04217v2`, and the `2607.20093v1` mention in §4) from their one-line evidence-pack findings, not from full text.
- **Sampling**: deep reads were selected from the top-60 booklist and the 98 high-relevance rows for direct mapping to the priority surfaces (`orderflow`, `execution_schedule`, `execution_price`, `liquidity_risk`, `market_session`, `market_tradability`, `volume_flags`, `compression`); papers whose surface was a covariance, options or regime module were left to the sibling books.
- **Not verified**: no repo tests, linters or git state were run (per task rules). Wiring claims (e.g. `analysis_tools.py:13087` calling `pov_schedule`, `agents/toolsets.py` exposing `get_spread_estimate`/`get_book_depth_read`) come from `grep` of the live source, not from execution. Whether the engine's *data feeds* actually carry quote-event or L2 depth needed for OFI/multi-level OFI was not established — the modules read as if they do not, which is why L1/L9 are marked absent rather than partial.
