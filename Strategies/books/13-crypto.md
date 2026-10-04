# Crypto & Digital Assets

`book 13/19` · slug `crypto` · 331 papers in the corpus · 27 rated high-relevance by the sweep

## 0. Scope

This category covers everything the corpus holds on crypto and digital assets: Bitcoin/Ethereum
return statistics, crypto volatility and tail dependence, cross-exchange and AMM routing costs,
on-chain and stablecoin/DeFi failure modes, crypto sentiment, and the large "predict BTC price
with an LSTM" literature. It matters to this repo only as an **out-of-domain testbed**.
TradingAgents is an equity engine — `dataflows/` has no crypto price vendor, `market_router.py::market_for_symbol`
has no crypto branch, and every sizing/risk path is calibrated on equity behaviour. Crypto is
therefore useful in exactly one direction: it is the extreme case that shows where equity-calibrated
methods (fixed-risk sizing, sqrt-time VaR scaling, cost assumptions, diversification claims) break,
and where the repo's cost/gate discipline already protects it. Findings that are crypto-specific —
on-chain flows, stablecoin depegs, AMM mechanics, 24/7 calendar — are flagged as non-transferable.

## 1. Corpus composition

Evidence-pack rows for this category: **331** (27 high · 180 medium · 124 background). The
canonical taxonomy assigns **53** papers to crypto on their *primary* label
(`Strategies/books/CORPUS_INDEX.md`, "Crypto & Digital Assets — `crypto` (53 papers)"); the 331 is
the multi-label membership total, i.e. every paper the abstract sweep judged crypto-relevant. The
60-paper relevance-ranked shortlist is the deep-read pool; its
composition:

| Period | Shortlist (n=60) | Primary arXiv category | Shortlist (n=60) |
| --- | --- | --- | --- |
| 2015–2019 | 13 | q-fin.ST | 44 |
| 2020–2024 | 35 | q-fin.{MF,PM,GN,PR,RM} | 6 |
| 2025–2026 | 12 | cs.{SI,LG,CE} | 5 |
| before 2015 | 0 | econ.{GN,EM} | 3 |
| | | physics.soc-ph | 2 |

The category is dominated by two things. First, **price-forecasting papers** — the bulk of the 180
medium/124 background rows are LSTM/GRU/TFT/GARCH horse-races on BTC/ETH daily data, of which the
recurring honest result is that naive/linear models match or beat deep nets. Second, a much
smaller and far more useful group of **market-structure and tail-risk measurements** (the high-27)
that quantify crypto's inefficiency, its cost floor, and its non-Gaussian joint tails. Recent
(2025–2026) work shifts toward execution/routing costs, cross-market comparison (crypto vs
equities under a matched protocol), and extreme-dependence graphs — the parts of the category that
transfer. The 2020–2024 concentration reflects the coin's attention cycle, not a methodology shift.

## 2. Deep reads

### arXiv 2608.21888v1 — Short-horizon mean reversion in cryptocurrency markets: a matched cross-market measurement (2026)
- **Question**: is the short-horizon inefficiency of crypto real and measurable under a protocol
  matched to a US-equity control, and is it large enough to trade?
- **Data/market**: 15-minute candles 2025-01-01 to 2026-02-11 over the 183 highest-volume Binance
  USDT spot pairs vs 187 liquid US stocks/ETFs; supporting multi-year 15-min histories back to
  2021, refetches from Coinbase/OKX/Bybit, a frozen 2026-02–2026-08 holdout.
- **Method**: a three-parameter constrained distributed-lag logit over 12 soft-clipped lagged
  returns used as a low-variance instrument; strictly out-of-sample walk-forward; base-rate-invariant
  AUC; exact permutation null; a second unconstrained AR(12) logit must agree.
- **Finding**: 90% of Binance pairs carry significant 15-minute directional reversal vs 2.7% of US
  stocks/ETFs; the signal lives in the *sign* (lag-one autocorrelation is ~0), AUC gap +0.031 as
  designed and +0.011 under the most conservative accounting; it concentrates after aggressive
  taker-flow moves and grows with flow intensity. US-listed funds whose NAV *is* a crypto/metal
  price inherit their underlying's reading, nulls included.
- **Limitation**: the gross edge peaks near **1.3bp per trade against a 5bp cheapest round-trip
  cost** — detectable, not capturable; and the flow mechanism cannot be separated from an
  informational account. This is a limits-to-arbitrage result, not a strategy.

### arXiv 2609.19013v2 — Routing Frictions and Executable Liquidity in Fragmented Markets (2026)
- **Question**: does mechanical cross-venue reachability on a public blockchain translate into
  economically integrated execution?
- **Data/market**: 13,768 sampled family-transactions from 29 Ethereum and Base token-pair families
  and 71 sibling AMM pools; exact pre-trade venue states, transaction-level access costs, realized
  venue use, all reconstructed from public chain records.
- **Method**: point identification of executable multi-venue opportunity from reconstructed states,
  then re-scoring under measured gross vs net access costs; comparison of Ethereum's cost regime
  against Base's lower-cost regime holding orders and states fixed.
- **Finding**: the equal-chain lower bound on gross multi-venue gains is 34.85%, but the upper bound
  after access costs is 6.89% — **access costs eliminate 80.45% of states with positive gross
  gains**; realized multi-pool activation is only 1.203%, yet among 170 eligible realized integrated
  routes, observed allocation captures 94.8% of feasible gain.
- **Limitation**: AMM-specific (gas, MEV, pool state); the numbers do not map onto an equity order
  book, though the *shape* of the result (gross → net compression) does.

### arXiv 2512.02029v1 — HODL Strategy or Fantasy? 480 Million Crypto Market Simulations (2025)
- **Question**: what does buy-and-hold actually deliver net of costs across the whole coin universe,
  and can realized risk-return distributions guide future outcomes?
- **Data/market**: 378 non-stablecoin assets; 480 million Monte Carlo paths, net of trading fees and
  the 1-month T-bill opportunity cost; eight baskets (BTC, ETH, ADA, BNB, DOGE, LINK, XRP, plus a
  market-wide random basket).
- **Method**: stationary block-bootstrap path simulation (preserving serial dependence); Bayesian
  multi-horizon local projections with hierarchical shrinkage for impulse responses of endogenous
  risk-return metrics vs macro-finance factors.
- **Finding**: at the 2–3 year horizon the market-wide **median excess return is −28.4%** with
  CVaR₁% ≈ 1.08 (tail scenarios wipe out principal), while the top-quartile mean is +1,326.7% — the
  "miracles" belong to the luckiest quarter and the narrative embeds survivorship bias. Realized
  risk-return metrics are economically negligible population predictors; the 24-week EMA of the
  Fear & Greed Index is the most stable, a 1-sd shock cutting forward top-quartile mean by 15–22pp.
- **Limitation**: simulated paths inherit one historical window; fee/T-bill assumptions are
  idealized; meme coins show ~3× the sentiment sensitivity, so the aggregate hides heterogeneity.

### arXiv 2606.16840v1 — Crashing Together, Rallying Apart: Dynamic Conditional Tail Dependence in Cryptocurrency Markets (2026)
- **Question**: does a basket of crypto assets offer genuine internal diversification, and is
  downside dependence stable or time-varying?
- **Data/market**: daily returns of the thirteen largest cryptocurrencies, 89 overlapping windows,
  late 2021 to 2025.
- **Method**: dynamic Hüsler-Reiss graphical models of extremes — the tail analogue of the Gaussian
  graphical model — estimated separately for joint crashes and rallies, benchmarked against a
  Gaussian graphical model of ordinary co-movement.
- **Finding**: a near-complete, stable lower-tail graph; an upper tail that thins over time to
  re-form sectoral structures; ordinary token categories dissolve into one Bitcoin-Ethereum-anchored
  block. Intra-crypto diversification fails on the downside and **standard risk models understate
  market-wide crash probability by roughly eightfold**.
- **Limitation**: thirteen assets only; HR graphs need enough joint extremes, so the upper-tail
  thinning may partly be a sample-size effect; results are conditional on the window set.

### arXiv 2606.04217v2 — Polymarket-v1 Database (2026)
- **Question**: how accurate are the standard trade-direction classifiers when ground truth is
  actually observable?
- **Data/market**: the complete on-chain trade archive of Polymarket's first-generation CTF Exchange
  on Polygon — 1.20 billion trades, 1.30 million markets, $61bn nominal — with **all aggressor
  direction derived from the blockchain settlement layer**.
- **Method**: benchmark the tick rule and bulk-volume classification against ground truth; propagate
  their errors into inferred VPIN and order-flow imbalance (OFI); test whether ground-truth
  microstructure predicts forecast Brier scores that classified proxies recover.
- **Finding**: the tick rule and bulk-volume classification achieve near-random aggregate accuracy
  (**49.83% and 50.51%**); inferred VPIN diverges substantially from true VPIN and OFI is
  directionally biased, degrading transaction-cost analysis; replacing ground-truth metrics with
  classified proxies attenuates forecasting relationships.
- **Limitation**: prediction markets (positive trade-direction autocorrelation, concentrated
  market-making), not crypto spot or equities; but the lesson — never infer side by a heuristic when
  the venue can report it — is general.

### arXiv 2607.19453v1 — Predictive Extrema, Unprofitable Policies: An AI-Assisted Audit of Candle-Based Binance Spot Timing Models (2026)
- **Question**: can candle-based ML that predicts crypto extrema be turned into a positive
  policy after costs?
- **Data/market**: Binance Spot candles; a ten-pair mandatory-daily selector; OHLCV-only daily
  adaptation of a published paired-extrema policy; fixed-seed scripted runs and deterministic
  simulators.
- **Method**: predecessor search to bound the trial count, then chronological evaluation with an
  assumed **31-bps completed-cycle cost**, next-executable-price timing, and an explicit forensic
  audit of an earlier "30-day holdout" (dates influenced prior architecture work, four-hour outcome
  horizon not purged at split boundaries, same-close entry, raw result directories absent).
- **Finding**: the unchanged ten-pair selector **lost 6.72% over 19 cycles at 31bps cost (3 wins,
  16 losses)**; the validation-selected local-minimum policy returned −1.79% and the local-maximum
  policy underperformed continuous holding by 2.80%; a high-AUC (0.874/0.896) Gurgul-inspired model
  had average precision only 0.134/0.116 and lost 44.30%. **Every operational decision remains
  NO_TRADE** — ranking quality did not establish executable policy value.
- **Limitation**: one venue, exploratory protocols, assumed (not measured) cost; but it is a clean
  demonstration that classification AUC and policy P&L are different problems.

### arXiv 2203.08224v4 — Predicting Value at Risk for Cryptocurrencies With Generalized Random Forests (2024)
- **Question**: can a non-parametric quantile method beat classical VaR models on the most volatile
  asset class?
- **Data/market**: 105 major cryptocurrencies plus a simulation study on standard financial returns.
- **Method**: quantile-adapted Generalized Random Forests (Athey–Tibshirani–Wager) over rolling
  windows, benchmarked against quantile regression, GARCH-type, GJR-GARCH and CAViaR models, with
  covariates describing volatility, liquidity and supply.
- **Finding**: GRF is superior on crypto, and the advantage is **especially pronounced in unstable,
  highly volatile times and for the most volatile coin classes**; during stable periods long-term
  standard-deviation covariates dominate, during unstable periods they become irrelevant, and only
  lagged volatility and lagged returns matter. For stablecoin-like coins GJR-GARCH and quantile
  regression compete.
- **Limitation**: covariate-importance results are time-varying, so predictor selection cannot be
  frozen; 105 coins is a wide but shallow panel.

### arXiv 2209.12383v1 — On Robustness of Double Linear Trading with Transaction Costs (2022)
- **Question**: does a trading policy's guaranteed positive expected gain survive transaction costs?
- **Data/market**: Monte Carlo under geometric Brownian motion with jumps, plus a backtest on
  historical Bitcoin-USD.
- **Method**: a new class of "double linear" policies analysed against the Simultaneous Long-Short
  (SLS) family; conditions derived for retention of the positive-expectation property under costs.
- **Finding**: the desired robust positive expected gain **can disappear once transaction costs are
  modelled**, and the paper quantifies the cost/parameter conditions under which positivity is
  preserved; the BTC-USD backtest validates the boundary.
- **Limitation**: idealized price processes (GBM + jumps) and a theoretical cost model; the
  conclusion is a boundary statement, not a strategy.

### arXiv 2608.29025v1 — Deep Hedging Under Realistic Market Frictions (2026)
- **Question**: do neural-network ("deep") option hedges outperform classical delta hedges under a
  genuinely fair, real-data comparison?
- **Data/market**: five years of historical Deribit BTC options (2020–2024); 11,546 out-of-sample
  test episodes, September 2023 to December 2024.
- **Method**: three classical benchmarks (Black-Scholes delta, Leland cost-adjusted vol, Whalley-
  Wilmott no-trade band) vs three deep configurations (LSTM and feedforward, CVaR loss, two turnover
  penalties), all under an identical realistic 5-bps transaction cost.
- **Finding**: the **Whalley-Wilmott no-trade band** cuts transaction costs by $1.79 per episode vs
  Black-Scholes delta (95% CI [−2.21, −1.39], p<0.0001) by trading ~8× less often; **all three deep
  hedging configurations underperform every classical benchmark on every metric**, converging to
  continuous-hedging trade frequency despite a twentyfold turnover-penalty range.
- **Limitation**: single historical window (regime-dependent — the P&L advantage narrows in a calmer
  validation period); likely limited training data and no sparsity-inducing architecture.

### arXiv 2602.07046v5 — Do Cryptocurrency Markets Differentiate Infrastructure from Regulatory Shocks? (2026)
- **Question**: do crypto markets price infrastructure shocks (outages, exploits) differently from
  regulatory shocks, and is the answer robust to how events are selected?
- **Data/market**: 50 events across six crypto assets, January 2019 to August 2025.
- **Method**: asymmetric GARCH with exogenous regressors (GJR-GARCH-X) under a dependence-aware
  inference design; event inclusion treated as an explicit design parameter; conditional fixed-path
  Student-t copula bootstrap against a sharp per-asset-equality null.
- **Finding**: under curated high-salience identification the infrastructure/regulatory variance
  differential is a **3.49× point-estimate multiplier**, but it is selection-conditional (≈0.5–1.6×
  when the impact filter is applied mechanically), and dependence-robust inference **removes
  significance (copula p ≈ 0.39)**; a naive i.i.d. test that had looked decisive is not robust. The
  six-contrast effective sample size is only 1.33–2.35.
- **Limitation**: small event count; the point-estimate pattern is descriptive, not an inferential
  comparison between screens; the first-moment CAR difference (+8.69pp) is not distinguishable from
  zero.

### arXiv 2504.01974v1 — Cryptocurrency Time Series on the Binary Complexity-Entropy Plane (2025)
- **Question**: which cryptocurrencies actually deviate from the random-walk efficiency benchmark?
- **Data/market**: 47 of the largest non-stablecoin coins, together ~90% of crypto market cap.
- **Method**: a tailored Binary Complexity-Entropy Plane (BiCEP) over daily up/down sequences,
  locating each coin against the random-walk backbone and defining an inefficiency score *I* with
  statistical testing.
- **Finding**: **only Shiba Inu is significantly inefficient**; the largest stake of crypto trading
  operates in close-to-efficient conditions. The authors argue a coin's design/consensus
  architecture is at least as relevant to efficiency as the usual fiat-market features.
- **Limitation**: binary (up/down) symbolisation discards magnitude and is sensitive to the
  tie/flat-bar convention; the inefficiency score is ordinal.

### arXiv 2009.12155v1 — A Decade of Evidence of Trend Following Investing in Cryptocurrencies (2020)
- **Question**: do crypto markets reward commodity-style trend following over a full decade?
- **Data/market**: crypto asset daily data from the infancy of Bitcoin (2009–2020); walk-forward
  evaluation.
- **Method**: a trend-following managed-futures framework applied to a crypto universe, reporting
  walk-forward annualised return and risk-adjusted characteristics against equities.
- **Finding**: **255% walkforward annualised returns**, with return characteristics akin to
  commodities and strong bear-market diversification against equities.
- **Limitation**: the sample covers crypto's birth-to-first-bull era; returns are walk-forward but
  the period is the least representative decade imaginable, and the headline is not survivorship-
  corrected.

### arXiv 2207.13914v3 — Anatomy of a Stablecoin's failure: the Terra-Luna case (2022)
- **Question**: how did Terra/UST fail, and what does the failure reveal about dependence structure?
- **Data/market**: Terra project news from heterogeneous social sources; hourly and transaction data
  for Bitcoin, Luna and TerraUSD around May 2022; 61 highly capitalised coins during the down-market.
- **Method**: systematic event reconstruction, the Anchor-protocol dependence, hourly/transaction
  analysis, and network-science analysis of dependency evolution plus cross-sectional absolute
  deviation for herding.
- **Finding**: the failure is traced to the vicious dependence on Anchor's yield and a reflexive
  Luna/UST mint-burn mechanism; the network analysis documents rearrangement of the coin dependency
  structure through the crash and **an absence of herding** by the cross-sectional measure.
- **Limitation**: a single (if paradigmatic) case; results are descriptive and do not generalize to
  all algorithmic stablecoins.

## 3. Learnings applicable to this repo

### L1. Never infer trade side by tick rule or bulk-volume heuristic; require venue-side truth
- **Source**: `arXiv 2606.04217v2` (2026) — Polymarket-v1 Database.
- **Finding**: with 1.2bn ground-truth-labelled trades, the tick rule and bulk-volume classification
  score 49.83% / 50.51% — near-random — and the errors propagate into VPIN divergence and OFI bias,
  which corrupt transaction-cost analysis. Ground-truth microstructure predicts outcomes that
  classified proxies cannot recover.
- **Repo surface**: `tradingagents/strategies/orderflow.py::vpin` (and `knife_guard_vpin`).
- **Status**: **shipped** — verified: `vpin` consumes per-trade `{'volume', 'side': 'B'|'S'}` and
  refuses ambiguous input, returning `unclassified_volume_share`; it never applies a tick rule.
- **Concrete step**: none required for the classifier path; the smallest reinforcement is to surface
  `unclassified_volume_share` as a gate so a high unclassified share marks the VPIN read unavailable
  rather than publishing an imbalance computed on the labelled subset.

### L2. Report gross edge beside the configured round-trip cost; refuse a signal below the cost floor
- **Source**: `arXiv 2608.21888v1` (2026) — Short-horizon mean reversion in cryptocurrency markets.
- **Finding**: 90% of 183 Binance pairs carry significant 15-minute reversal vs 2.7% of 187 US
  stocks/ETFs, yet the gross edge ≈1.3bp sits under a 5bp cheapest round-trip cost — detectable and
  untradeable. Also `arXiv 2209.12383v1` (2022): a guaranteed-positive-expectation policy can lose
  its positivity once costs are modelled. Crypto's weaker efficiency does **not** mean free alpha;
  it means the cost/edge ratio, not the IC, decides.
- **Repo surface**: `tradingagents/strategies/mean_reversion.py::mean_reversion_verdict` and
  `tradingagents/strategies/backtest_models.py::make_cost_fn`.
- **Status**: **partial** — verified: `mean_reversion_verdict` classifies stable/mean-reverting/
  trending from AR(1)/half-life but reports no gross-edge-in-bp and has no cost comparison;
  `make_cost_fn` exists and is used by the backtest harness, not by the mean-reversion read. The repo
  has no crypto vendor so this is a discipline gap, not a live defect.
- **Concrete step**: have `memory_profile` also emit the AR(1) sign edge in basis points and a
  `below_cost` flag computed against the configured `fee_bps`/round-trip cost, so a reversal read
  that cannot clear the cost floor is labelled not-tradeable.

### L3. Report lower-tail dependence for the book, not just ordinary correlation
- **Source**: `arXiv 2606.16840v1` (2026) — Dynamic Conditional Tail Dependence in Cryptocurrency
  Markets.
- **Finding**: in the joint tail, the 13 largest coins form a near-complete, stable *lower*-tail
  graph while the upper tail thins — intra-basket diversification fails on the downside, and
  covariance-based models **understate crash probability ~8-fold**. This is the strongest case in
  the book for a downside-dependence read that is separate from the correlation matrix.
- **Repo surface**: `tradingagents/strategies/book_risk.py::copula_scenarios` /
  `_tail_dependence`, and `tradingagents/strategies/covariance_models.py::spectral_null_band`.
- **Status**: **partial** — verified: `copula_scenarios` already computes an empirical lower-tail
  dependence `P(U_j≤q|U_i≤q)` at a single `quantile=0.1` with a fitted rank copula (t/Gaussian/
  Clayton/independent); there is no lower-vs-upper asymmetry read and no conditional extremal graph.
- **Concrete step**: add a small asymmetry block beside `tail_dependence` comparing the empirical
  lower-tail dependence at q=0.05 against the upper-tail analogue, so a book whose downside
  dependence far exceeds its upside dependence is flagged rather than trusted to the Gaussian leg.

### L4. Long-horizon outcome reads must carry the survivorship and cost adjustment
- **Source**: `arXiv 2512.02029v1` (2025) — HODL Strategy or Fantasy?
- **Finding**: over 378 coins, the market-wide median 2–3-year net excess return is −28.4% with
  CVaR₁% ≈ 1.08, while the top-quartile mean is +1,326.7% — the "miracle" is a survivorship artefact
  and the typical outcome is a deep loss. A naive backtest over today's coin list would report the
  top-quartile story.
- **Repo surface**: `tradingagents/strategies/coverage_window.py::SURVIVOR_ONLY` and
  `tradingagents/strategies/book_risk.py::extreme_quantile_var`.
- **Status**: **partial** — verified: `coverage_window` defines the `SURVIVOR_ONLY` label and
  reports `padded_days`/`first_valid`; `extreme_quantile_var` provides EVT/GPD tail quantiles. There
  is no multi-horizon basket Monte Carlo that reports median outcome beside the top quartile.
- **Concrete step**: add a `coverage_window` helper that turns a current-constituent panel into a
  `survivor_only`-labelled findings row, so any long-horizon basket statistic is tagged with the
  universe bias that produced it.

### L5. Route through the measured access-cost regime, not the displayed-liquidity regime
- **Source**: `arXiv 2609.19013v2` (2026) — Routing Frictions and Executable Liquidity.
- **Finding**: measured access costs eliminate **80.45%** of states with positive gross gains
  (34.85% gross lower bound → 6.89% net upper bound); realized multi-pool activation is 1.203%.
  Connectivity and displayed liquidity do not equal executable integration — integration is an
  order-specific property.
- **Repo surface**: `tradingagents/strategies/market_tradability.py::volume_gate` and
  `tradingagents/strategies/backtest_models.py::capacity_pct` / `square_root_impact`.
- **Status**: **partial** — verified: `volume_gate` enforces a participation cap and
  `market_tradability` gates suspension/limit moves, but there is no per-route access-cost
  comparison that discounts a venue by its activation cost. `dataflows/market_router.py` routes by
  vendor priority, not by measured access cost.
- **Concrete step**: extend the tradability model with a per-venue `access_cost_pct` that turns a
  gross candidate gain into a net one, and refuse the route when net ≤ 0 — the equity analogue is
  per-venue fees plus borrow, which the router currently does not score.

### L6. Prefer a no-trade band to more frequent rebalancing; hedge frequency is a cost lever
- **Source**: `arXiv 2608.29025v1` (2026) — Deep Hedging Under Realistic Market Frictions.
- **Finding**: on real Deribit BTC options, the Whalley-Wilmott no-trade band beat Black-Scholes
  delta by $1.79/episode (p<0.0001) by trading ~8× less often; three deep-hedging configs lost to
  every classical benchmark on every metric.
- **Repo surface**: `tradingagents/strategies/execution_schedule.py::almgren_chriss` and
  `tradingagents/strategies/options_math.py::greek_pnl_response`.
- **Status**: **partial** — verified: `almgren_chriss` solves the optimal liquidation trajectory
  with temporary/permanent impact; there is no no-trade-band gate around a target hedge, and the
  repo has no deep-hedging claim to correct (it is already classical).
- **Concrete step**: add a `no_trade_band` helper (trade only when |current − target| exceeds a
  band proportional to spread/cost) and report the implied trade-count reduction beside the
  existing Greek response, making "hedge less often" an explicit, measured option.

### L7. VaR must be regime-conditional; a static quantile breaks exactly in unstable periods
- **Source**: `arXiv 2203.08224v4` (2024) — Predicting VaR for Cryptocurrencies With Generalized
  Random Forests.
- **Finding**: non-parametric quantile forests beat quantile regression, GARCH and CAViaR on 105
  coins, and the advantage is concentrated in unstable/high-volatility periods; predictor
  importance rotates (long-term sd dominates in stable times, lagged vol/returns in unstable times).
- **Repo surface**: `tradingagents/strategies/book_risk.py::_regime_var_coverage`,
  `var_coverage_test`, and `tradingagents/strategies/tail_risk.py::tail_risk`.
- **Status**: **partial** — verified: `_regime_var_coverage` builds a mixture quantile from the
  running state posterior and always pairs it with the Kupiec/Christoffersen coverage test, and
  `extreme_quantile_var` adds EVT — but there is no covariate-conditioned (forest/ML) quantile
  leg, and no explicit "unstable-period" importance rotation report.
- **Concrete step**: expose the existing regime-conditional VaR and its coverage verdict side by
  side with the unconditional historical VaR, so a VaR that only covers in calm windows is visible;
  a forest quantile leg is the larger follow-up.

### L8. Treat event inclusion as a design parameter; guard against selection-on-the-dependent-variable
- **Source**: `arXiv 2602.07046v5` (2026) — Infrastructure vs Regulatory Shocks.
- **Finding**: a 3.49× event-variance multiplier under curated, high-salience events collapses to
  ≈0.5–1.6× under mechanical selection and loses significance under dependence-robust inference
  (p≈0.39); the effective sample for six contrasts is 1.33–2.35. Event-study effect sizes are
  selection-conditional.
- **Repo surface**: `tradingagents/strategies/events.py::catalyst_risk_penalty` /
  `expected_drift_after` and `tradingagents/strategies/catalyst.py`.
- **Status**: **partial** — verified: `events.py` computes a surprise score and a catalyst penalty
  but reports no effective-sample or selection-sensitivity qualification on its drift estimate.
- **Concrete step**: record the event-selection rule and an effective-sample count alongside every
  catalyst drift read, forbidding a point estimate from being reported without its inclusion screen.

### L9. Add an efficiency/complexity read so "is this tradeable" is not answered by IC alone
- **Source**: `arXiv 2504.01974v1` (2025) — Binary Complexity-Entropy Plane.
- **Finding**: across 47 coins covering ~90% of market cap, **only Shiba Inu is significantly
  inefficient**; most large crypto trades close to the random-walk benchmark, despite crypto's
  reputation for inefficiency. A coin's design/consensus architecture matters at least as much as
  standard fiat-market features.
- **Repo surface**: `tradingagents/strategies/complexity.py::permutation_entropy` /
  `lz_complexity` / `approximate_entropy`.
- **Status**: **partial** — verified: `complexity.py` implements permutation/approximate/LZ entropy
  as measurement-only advisory features, but there is no complexity-entropy *plane* that locates a
  symbol against the random-walk backbone and produces an inefficiency verdict.
- **Concrete step**: combine the existing entropy and LZ legs into a single normalised inefficiency
  score against a synthetic random-walk null, so `complexity.py` answers "how far from efficient"
  rather than emitting three raw entropies.

### L10. Do not let a stablecoin/DeFi risk surface leak into the equity engine
- **Source**: `arXiv 2207.13914v3` (2022) — Anatomy of a Stablecoin's failure: the Terra-Luna case
  (and `arXiv 2609.19013v2` on AMM routing).
- **Finding**: Terra/UST failed through a reflexive mint-burn dependence on Anchor's yield — a
  failure mode with no equity counterpart (no NAV floor, no bankruptcy process, redemption is
  mechanical). The network analysis finds dependence-structure rearrangement plus an *absence* of
  herding, i.e. the crash was not a simple panic cascade.
- **Repo surface**: `(new module)` — there is no stablecoin, depeg or protocol-risk surface, and
  none is needed for an equity engine.
- **Status**: **absent** — verified: no crypto/stablecoin/depeg/AMM symbol exists under
  `tradingagents/strategies/`; `market_for_symbol` has no crypto branch; `dataflows/` has no crypto
  vendor. This is the intended state.
- **Concrete step**: none for the equity path. The only actionable rule is a guard: if a future
  crypto/stablecoin data source is added, protocol/depeg risk must be a first-class refusal input,
  not folded into equity price risk, because the failure is reflexive and has no price-process
  analogue.

### L11. Treat an ML-timing "edge" as unproven until a costed, purged policy test says otherwise
- **Source**: `arXiv 2607.19453v1` (2026) — Predictive Extrema, Unprofitable Policies.
- **Finding**: a ten-pair Binance selector lost 6.72% over 19 cycles at 31bps cost; a model with
  ROC-AUC 0.874/0.896 had average precision only 0.134/0.116 and lost 44.30%. Ranking rare events
  did not produce executable policy value; every decision stayed NO_TRADE.
- **Repo surface**: `tradingagents/strategies/evaluate.py::deflated_sharpe` /
  `purged_cpcv_splits` / `pbo_flag` and `tradingagents/strategies/trial_ledger.py`.
- **Status**: **shipped** — verified: `evaluate.py` provides deflated Sharpe, purged CPCV with
  embargo, PBO/overfit flags and reality-check/SPA; `trial_ledger` records trials. This is exactly
  the discipline the paper's audit demands.
- **Concrete step**: none required; the smallest reinforcement is to ensure any crypto-like
  short-horizon policy evaluation routes through `purged_cpcv_splits` with a non-zero embargo (the
  paper's forensic audit found an unpurged 4-hour horizon at the split boundary).

## 4. Where this repo is already ahead of the literature

- **Side classification without heuristics.** `orderflow.py::vpin` requires explicit per-trade
  `side` labels and reports `unclassified_volume_share`, refusing ambiguous input. `arXiv 2606.04217v2`
  shows the standard tick-rule/bulk-volume alternatives are near-random (49.83%/50.51%) — the repo
  never had that failure mode.
- **VaR with a coverage test attached.** `book_risk.py::var_coverage_test` (Kupiec POF +
  Christoffersen independence) and `_regime_var_coverage` make a VaR unusable without its breach
  record. None of the crypto-VaR papers reviewed here (2203.08224, 2309.06393, 2307.09137) ships a
  formal coverage gate alongside the number.
- **Deflated-Sharpe / PBO / SPA evaluation.** `evaluate.py` already implements the multi-trial
  overfitting controls that `arXiv 2209.05559v6` and `arXiv 2607.19453v1` argue are the difference
  between a backtest and an edge.
- **Almgren-Chriss trajectory + capacity model.** `execution_schedule.py::almgren_chriss` and
  `backtest_models.py::square_root_impact`/`capacity_pct` already price market impact; the crypto
  execution papers (2503.02680, 2511.07434, 2502.13722) add ML to the same objective but do not
  exceed the deterministic baseline in a way that transfers.
- **Advisory, None-safe, refusal-first design.** `complexity.py`, `triadic_stress.py` and
  `market_tradability.py` all return `unavailable` with a reason instead of a fabricated zero, which
  is the discipline the thin-sample crypto literature (e.g. `arXiv 2602.07046v5`) recommends but
  rarely follows.

## 5. Defects or risks the literature exposes

1. **Fixed-risk sizing is equity-calibrated and will mis-size crypto-like volatility.**
   `risk_sizing.py::risk_quantity`/`risk_money` size from the entry-to-stop distance with no
   volatility target: a stop placed at an equity-typical percentage on an asset with crypto-like
   vol implies a much larger risk-per-unit than intended, and `regime_state.py::vol_cap_factor`'s
   ATR-ratio ladder (bands 1.2/1.5/2.0/3.0) is the only volatility brake. `arXiv 2404.04962v1`
   (crypto vol rises with *positive* returns, unlike equities) and `arXiv 2512.02029v1`
   (CVaR₁%≈1.08 on a broad crypto basket) show that an equity stop distance understates tail risk
   by multiples. **Transferable**: for any high-vol equity (small caps, biotech) the same defect
   applies; the sizing path should scale the stop distance to the name's realized vol, not a fixed
   percentage.
2. **`events.py::catalyst_risk_penalty` bakes in `baseline_move=0.015`.** A hard-coded 1.5%
   baseline event move is an equity-calibration constant; on a higher-vol name it would read a
   perfectly normal move as a "surprise". `arXiv 2602.07046v5` shows event-variance estimates are
   selection- and regime-conditional; a fixed baseline ignores that. Should be a function of the
   name's own pre-event realized vol.
3. **Sqrt-time VaR scaling is explicitly gated but the gate is narrow.**
   `book_risk.py::var_cvar_horizon` sets `scaling_valid = len(vals) >= 32 and |acf[0]| < 0.2` — a
   one-lag test. `arXiv 2512.02029v1` and `arXiv 2606.16840v1` show crypto-like series have strong
   higher-lag and tail dependence; a one-lag autocorrelation check can pass while multi-horizon
   scaling is still invalid. Consider testing a small lag set, not just lag 1.
4. **No gross-vs-net cost gate on the reversal/momentum reads.** Confirmed: `mean_reversion.py`
   and `momentum.py` produce signals with no comparison against the configured cost floor.
   `arXiv 2608.21888v1` (1.3bp gross vs 5bp cost) and `arXiv 2607.19453v1` (−6.72% at 31bps) show
   this is the single most common way a measured signal is mistaken for an edge.
5. **No lower-vs-upper tail-dependence asymmetry read.** `book_risk.py::copula_scenarios` reports a
   single lower-tail quantile at q=0.1. `arXiv 2606.16840v1` shows downside dependence is
   near-complete while upside dependence thins; the repo cannot currently express that asymmetry,
   so a book's crash co-movement is not separately measured from its rally co-movement.

## 6. Limits of this review

- **Read vs skimmed.** Twelve papers were read in full text (§2). The remaining high-relevance rows
  and all medium/background rows were assessed from the abstract-level sweep only. The 124 background
  rows are dominated by price-prediction horse-races (LSTM/GRU/TFT/GARCH on BTC/ETH) whose recurring
  finding — naive/linear models match deep nets — is consistent enough that individual papers would
  not change the conclusions.
- **Sampling.** The deep-read pool is the 60-paper relevance shortlist; selection was biased toward
  market-structure, tail-risk and cost papers that could touch an equity surface, and away from
  pure on-chain analytics (address clustering, ponzi/Ponzi detection, NFT ecosystems) that have no
  equity analogue and were excluded by design.
- **Not verified.** I did not execute any repo code, test, linter or git command. Repo surfaces were
  verified by reading the actual module source; the "status" judgements are source-based, not
  run-based. Where I claim a signal lacks a cost gate (defect 4), that is from reading the module,
  not from running it on data.
- **No crypto data in-repo.** Because `dataflows/` has no crypto vendor, none of the transferable
  learnings could be validated against this repo's own data; they are proposed as discipline and
  degenerate-case tests, not as confirmations.
- **arXiv-id risk.** Several ids in the 331-row sweep carry future-style years (2025–2026); these
  were read from the PDFs on disk as presented, and the findings quoted are from those texts.
