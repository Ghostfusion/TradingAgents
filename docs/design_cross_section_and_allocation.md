# Design: Cross-Sectional Structure, Peer Sets, and Allocation

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The cross-sectional channel - `cross_section`, `peer_universe`, `factor_expressions`, the
covariance and allocation stack, and the rank/selection machinery. Takes the 7 high- and 18
medium-relevance cross-section papers from the 2026 `q-fin` corpus survey.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Plan:** [`docs/implementation_plan_paper_survey_26.md`](implementation_plan_paper_survey_26.md) - the phased, gated adoption plan for these items (v1.0, PLAN).
**Rule-4 impact:** none. Allocation stays in the execution repo; nothing here changes the app surface.

---

## 1. Executive summary

### The corpus's central cross-sectional result is a negative one

**2607.27461** builds a trading system from three price-history matrices and reports, as its own
finding rather than a caveat, that **the cross-sectional volatility rank is forecastable one step
ahead while the return rank is close to unforecastable.** The numbers are unambiguous: the
volatility chain's out-of-sample monthly log-likelihood gain is **0.108** against the return chain's
**0.007**; the return rank's mean absolute error is 2.5 deciles and covariates do not move it, while
the volatility rank's falls from 2.05 to 1.78 with covariates. The portfolio built on the
combination posts Sharpe 1.06 and 1.32 on two non-overlapping out-of-sample windows against the
market's 0.78 and 1.14, net of 5bp - and the paper attributes the edge to the risk channel.

Read together with 2607.03858 (which splits the covariance eigenstructure into return-channel and
volatility-channel memory across horizons) and 2608.09641 (whose information sits in the **lower**
spectrum, not the largest eigenvalues), the corpus's cross-sectional message is consistent: **the
predictable structure is the risk structure.** A score engine that treats a return-forecast channel
and a volatility channel as equally weighted is mis-weighting its own information.

### Two other results worth acting on

- **Redundancy is measurable.** 2601.06499 tests 191 short-horizon signals against 151 fundamental
  controls over 4.9M observations using **double-selection LASSO** and keeps **17** survivors. This
  engine's `TechnicalScore` carries 39 components and its expression DSL can generate hundreds of
  factors. Nothing in the repo asks which of them are redundant given the others.
- **Very cheap synchronization reads exist.** 2608.09641's instrument is the count of eigenvalues
  below the Marchenko-Pastur lower bound, `(1 - sqrt(n/w))^2`, computed on an **11x11** sector-ETF
  correlation matrix. It rises when the effective number of independent bets collapses. Cheaper than
  anything else in this doc and it needs no new data.

### And one correction the survey itself got wrong

The survey routed 2607.01377 (Kyle's price-impact coefficient forecasting the cross-section of
returns) to `cross_section` as if the estimators were missing. They are not:
`strategies/liquidity_risk.py:71` `amihud_illiquidity` and `:262` `kyle_lambda` **already exist**. The
paper's actual contribution here is narrower and more useful - a *cross-sectional forward-rank test*
of an estimator the engine already computes, which is the shape most of this doc takes: **the
estimators largely exist; the validation does not.**

---

## 2. What this repo already has (verified)

| Instrument | Where, verified |
|---|---|
| Winsorize, cross-sectional z, industry-neutral z | `strategies/cross_section.py:31`, `:70`, `:89` |
| Centered rank, quantile split | `strategies/cross_section.py:140` `centered_rank`, `:169` `quantile_split` |
| Return residualization against a market | `strategies/cross_section.py:201` `residualize_returns` |
| Dollar/beta/sector-neutral projection, no-trade band | `strategies/cross_section.py:237` `neutralize_book`, `:321` `no_trade_band` |
| Momentum book | `strategies/cross_section.py:376` `momentum_book` |
| Top-k drop weights | `strategies/portfolio_strategy.py:35` `topk_drop_weights` |
| Peer resolution (resolved names, sector medians) | `strategies/peer_universe.py:150` `resolved_peer_names`, `:174` `resolve_peer_universe`, `:304` `resolve_growth_medians` |
| Amihud illiquidity, **Kyle lambda** | `strategies/liquidity_risk.py:71` `amihud_illiquidity`, `:262` `kyle_lambda` |
| Roll spread, Corwin-Schultz, slippage models | `strategies/liquidity_risk.py:309`, `:363`, `:220`, `:243` |
| Covariance estimators (EWMA, Ledoit-Wolf) | `strategies/covariance_models.py:106`, `:63` |
| HRP, optimizer, Kelly weights | `strategies/hierarchical_risk_parity.py`, `portfolio_optimizer.py`, `portfolio.py:452` |
| Rank IC / IC-IR, quantile signal analysis | `strategies/signal_analysis.py:64` `rank_ic` |
| Factor-expression DSL + AST purity gate + zoo bench | `strategies/factor_expressions.py`, `alpha_zoo.py:243` `bench_zoo` |
| Breadth (market-wide and sector, McClellan, RRG) | `strategies/market_breadth.py`, `sector_breadth.py:60` `multi_breadth` |
| Rotation, relative strength, sector rank | `strategies/rotation.py`, `relative_strength.py`, `sector_rank.py` |

## 3. The gaps, as builders

### X1 - A volatility-rank state chain (and the honest case against the return-rank one)

**Finding.** The engine forecasts *levels* (momentum, trend, relative strength) and never forecasts a
*rank*. The corpus says the rank channel that works is volatility, not return.

**Paper.** 2607.27461 builds, from about a year of daily returns, a 10-decile transition matrix over
names ranked monthly by trailing return and another ranked by trailing volatility:
`P^X_ab(t) = P(rank_i(t+D) = b | rank_i(t) = a)`, pooled over names and optionally conditioned on
covariate deciles by a log-linear conditional-logit; then `pi^V_i = sum_{b<=2} P^V` (probability of
landing in the two calmest deciles) and a blend `S_i = (1-lam)*pi^R_i + lam*pi^V_i`.

**What to compute.** `rank_transition(returns, kind="volatility"|"return") -> {P, forward_rank_prob}`
with `kind="volatility"` as the default and `kind="return"` available **only** with the
`unforecastable` flag attached, because the paper's evidence says that chain carries no signal and
reporting it without the flag would invite exactly the misuse the paper documents.

**Inputs.** **A full cross-section on every run** - the transition matrices, the decile assignments
and the blend are panel objects and cannot be computed for one name. This is the doc's most
expensive item and it belongs on a weekly offline pass.

**PIT.** Ranks use trailing windows ending at `t` and deciles are formed within date `t`. Breaks if
today's universe list is used over the whole history (survivorship), or if the transition matrices or
blend hyperparameters are fit on the full sample.

**Cost.** `K x K = 10 x 10` plug-in counting once the panel exists; negligible. The panel is the cost.

**Owner.** New module (`strategies/rank_transition.py`); consumes `cross_section.centered_rank` and
feeds `portfolio_strategy.topk_drop_weights`, which already does the selection half.

**Caveat.** Author-run and LLM-assisted, self-reported with no replication. The diversification gain
from residual distance (Sharpe 1.08 and 1.44 with the long sleeve diversified) is a separate claim
from the rank forecast and should be evaluated separately.

### X2 - A redundancy screen over the engine's own components

**Finding.** `TechnicalScore` carries 39 components; the expression DSL can generate hundreds of
factors; nothing asks which are redundant given the rest. A score engine whose components are 80%
collinear is reporting the same information several times while appearing diversified.

**Paper.** 2601.06499 runs **double-selection LASSO** over 191 short-horizon signals against **151
fundamental controls** on S&P 500 constituents 2002-2022 (4.9M observations), keeping **17**
survivors which it then evaluates as cross-sectional premia.

**What to compute.** `redundancy_screen(candidates, controls) -> {kept, dropped, coefficients}`,
run **offline on a schedule**, never inside a run - the paper's own warning is that survivors are
single-market, single-horizon in-sample selections. Its consumption is a decision: a component that
never survives should be a *documented* component rather than a scored one.

**Inputs.** The engine's candidate factors plus a control set. Both are already computable from bars.

**PIT.** Selection windows must not overlap the evaluation window; a survivor list is a hypothesis.

**Cost.** LASSO over a few hundred candidates x a few thousand days: minutes, offline.

**Owner.** `strategies/factor_expressions.py` and `alpha_zoo.py`, consumed by the score-engine
documentation.

**Caveat.** No stability test across refits is reported by the paper - a survivor list that changes
every refit is not a finding. Any use here must re-run the screen and compare.

### X3 - The lower spectrum as a synchronization read

**Finding.** The engine reads the *largest* eigenvalues implicitly (concentration, breadth) and never
the smallest. The corpus says the smallest carry the synchronization information.

**Paper.** 2608.09641 counts the eigenvalues of a correlation matrix **below the Marchenko-Pastur
lower bound** `(1 - sqrt(n/w))^2`, which rises when the effective number of independent bets
collapses. Over S&P 500 GICS sector indices 1990-2020 and constituents 2005-2020.

**What to compute.** `mp_below_count(corr, n, w) -> {count, mp_lower, status}` with `status =
unavailable` when `w <= n` - on an 11x11 sector-ETF matrix this is cheap enough to run per panel.

**Inputs.** The 11 SPDR sector ETFs `sector_rank` already tracks - no new data at all.

**PIT.** Rolling window ending at `t`.

**Cost.** An 11x11 eigendecomposition. Trivial.

**Owner.** `strategies/market_breadth.py` or `sector_breadth.py`, which already hold the panel.

**Caveat.** **Coincident and direction-blind** - it cannot separate a crash from a bubble - and the
paper's predictive claim is asserted more than demonstrated. Report it as a state, never as a signal.

### X4 - Which half of the covariance is persistent, at what horizon

**Finding.** The engine estimates a covariance at one horizon and uses it at another. 2607.03858's
result is that the return channel and the volatility channel have **different memory across
horizons**, so an H-day risk estimate mixes a persistent component with a reverting one without
saying how much of each.

**Paper.** 2607.03858 computes an eigenmode-indexed variance-ratio matrix over horizons from one day
to several years, then fits persistent, anti-persistent and multi-scale memory components - on FF49
industries, FF100 size-by-book-to-market, and FF Europe 25, with a 1000-replicate bootstrap.

**What to compute.** `horizon_memory(corr_series, horizons) -> {vr_by_mode, persistent_share}` so
that a risk estimate can state how much of itself is persistent versus reverting.

**Inputs.** Long return histories over a cross-section.

**PIT.** Backward windows.

**Cost.** Variance ratios over a horizon grid; `O(T * horizons)` per pair, so it is a panel-offline
job, not per-symbol.

**Owner.** New module beside `covariance_models.py`.

**Caveat.** The paper's multi-year memory sits far outside this engine's days-to-weeks mandate, and
its 28-year window precludes narrower regime dating. Adopt the *question* ("how much of this
estimate persists?"), and expect the engine's own answer at short horizons to be unimpressive.

### X5 - Peers anchored to valuation rather than to labels

**Finding.** `peer_universe.resolve_peer_universe` (`:174`) resolves peers from labels and sector
medians. Peer *relative* multiples are then computed against a set chosen by taxonomy rather than by
economic similarity.

**Paper.** 2608.12594 trains a gradient-boosted tree on a valuation multiple (EV/EBITDA or EV/Sales)
from point-in-time fundamentals, then defines peer weights by **importance-weighted leaf-node
co-occurrence** in that tree - so two companies are peers because the model prices them alike, not
because they share a sector code.

**What to compute.** `valuation_anchored_peers(characteristics) -> {weights_by_peer}` feeding the
existing peer-relative multiples.

**Inputs.** Point-in-time fundamentals the fundamentals engine already assembles.

**PIT.** Strictly point-in-time characteristics, or the similarity leaks the valuation it is anchored
to.

**Cost.** One GBT fit offline; leaf co-occurrence at inference is trivial.

**Owner.** `strategies/peer_universe.py`, **replacing** the label-based resolver rather than sitting
beside it - a second peer producer is exactly what rule 15 forbids.

**Caveat.** Built on **private-market deals**, so the similarity's stability is inherited from a
valuation target that behaves differently in public markets, and the peer set already has a producer
here, making this the item in this doc most likely to become duplication.

### X6 - A forward-rank test for the liquidity estimators that already exist

**Finding and correction.** `liquidity_risk.amihud_illiquidity` (`:71`) and `kyle_lambda` (`:262`)
are **already built**. What is missing is the question the paper asks of them: does a per-symbol-month
price-impact estimate rank the cross-section of subsequent returns?

**Paper.** 2607.01377 computes signed order flow and two lambda estimates per symbol-month, ranks
them cross-sectionally one month ahead, and (the paper's own caveat) emits `unavailable` where trade
direction cannot be determined.

**What to compute.** Nothing new; instead an offline study: `rank_ic(lambda_month_t, fwd_return_t+1)`
over the report panel, using `signal_analysis.rank_ic` (`:64`) which already does exactly this.

**Inputs.** The engine's own `kyle_lambda` output plus forward returns.

**PIT.** Lambda at `t`, return over `t+1`; the trade-direction input must be available at `t`.

**Cost.** `O(months)` once the panel exists.

**Owner.** `strategies/signal_analysis.py` (the test) over `liquidity_risk.py` (the estimator). **No
new estimator.**

**Caveat.** Daily bars give a crude trade-direction proxy; the paper's own result uses intraday
direction and the estimator's quality on daily data is unmeasured.

### X7 - Peer edges classified rather than assumed

**Finding.** `peer_universe` resolves peers; nothing tests whether a resolved peer is a *competitor*
(whose divergence should mean-revert differently) or a *supply-chain* relation.

**Paper.** 2604.19476 builds candidate peers from 10-K embedding similarity, has an **LLM classify
every candidate edge** into economic relations, **drops competitor edges**, then aggregates pair
z-score divergence with co-movement weights into a per-symbol mean-reversion signal.

**What to compute.** An edge classifier over `resolve_peer_universe`'s output, plus the
relation-conditioned aggregation. The engine's `security_context.py` already classifies securities,
and `text_factors.py` already computes cross-document divergence - both are inputs to this.

**Inputs.** 10-K text (via `dataflows/sec_edgar.py`) plus the existing peer candidates.

**PIT.** Filings are dated; the classifier runs on text available at `t`.

**Cost.** One LLM call per candidate edge, offline and cached per filing pair.

**Owner.** `strategies/peer_universe.py` and `strategies/theme_triggers.py` (whose cheap-scan pattern
fits the candidate generation).

**Caveat.** The pair-divergence signal is a mean-reversion claim on a horizon this engine's mandate
may not hold long enough to realise.

### X8 - Trend-following as spectral excess mass, with a cost-optimal span

**Finding.** `technical_factors` and `swing` compute trend indicators. Nothing states the condition
under which trend-following *can* work, or how long a lookback should be given the engine's costs.

**Paper.** 2607.19497 expresses P&L in volatility-normalized returns and decomposes trend-following
alpha as **excess low-frequency spectral mass** - the condition under which trend alpha exists at
zero drift - and gives a closed-form cost-optimal filter span.

**What to compute.** `spectral_excess_mass(returns) -> {mass, condition_met}` and
`cost_optimal_span(cost_bps, vol) -> int`, reported beside the swing factor rather than inside its
score. The second is directly actionable: it converts the engine's cost estimate into a lookback.

**Inputs.** The symbol's own return history plus the engine's cost estimate.

**PIT.** Backward window.

**Cost.** An FFT over the return series; trivial.

**Owner.** `strategies/technical_factors.py`, consumed by `swing`.

**Caveat.** The decomposition is a *condition*, not a signal: it says when to expect trend alpha, not
which direction. Read it as a filter on when the swing factor deserves weight.

---

## 4. Recorded negatives and declines

Worth recording, because each one stops a plausible change:

- **2606.07450** tests mutual-information dependency estimators and richer graph filters against
  plain Pearson correlation on 2,328 rolling windows across 24 configurations, and finds **linear
  Pearson plus a minimum spanning tree stays the most robust**. Do not replace the correlation
  machinery with mutual information on the strength of the graph literature.
- **2608.14323** (sparse architecture fixed by a dependence graph) is an architecture-search result
  for a training pipeline this engine does not have; the only reusable object is a standard
  dependence graph, which `covariance_models` already effectively has.
- **2606.08586** (topological anomaly scores) uses ten S&P 500 names and intraday bars over one year,
  and its reversal timing depends on regime; too thin to act on.
- **2607.25459** is a controlled synthetic study of latent-state computation with no market data and
  no forecast-utility claim.
- **2605.12977** (transient statistical factors by half-life-weighted MLE, tolerating missing
  returns) is recorded rather than proposed: it needs a **base factor model this engine does not
  have** (the paper measures against a Barra risk model), and adding it would create a second
  covariance producer unless it replaces the existing path.

**Cross-references.** 2607.24410 (covariance from characteristics) is specified as **K4** in
`docs/design_risk_tail_and_coverage.md`; 2608.29692 (a Wasserstein-2 variance certificate from
language-model news embeddings) is recorded there as out of reach. Neither is duplicated here.

---

## 5. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| X1 | volatility-rank transition chain (+ flagged return chain) | new (`rank_transition.py`) | yes |
| X2 | redundancy screen over components/factors | `factor_expressions.py`, `alpha_zoo.py` | no |
| X3 | Marchenko-Pastur lower-spectrum count | `market_breadth.py`, `sector_breadth.py` | no |
| X4 | eigenmode variance ratio by horizon | new, beside `covariance_models.py` | yes |
| X5 | valuation-anchored peer weights | `peer_universe.py` (**replaces**) | no |
| X6 | forward-rank test of existing liquidity estimators | `signal_analysis.py` + `liquidity_risk.py` | no |
| X7 | relation-classified peer edges | `peer_universe.py`, `theme_triggers.py` | no |
| X8 | spectral excess mass + cost-optimal span | `strategies/technical_factors.py` | no |

## 6. Honest limits

1. **The theme's headline is that the return rank is unforecastable.** Any adoption here should
   reduce confidence in the return-forecasting halves of the score engines, not increase it.
2. **X1 and X4 need a full cross-section every run**, against a ~40-minute four-symbol budget. Both
   are weekly-offline candidates, and the doc says so.
3. **X5 and X6 are the two items most likely to violate a house rule** - X5 by becoming a second peer
   producer, X6 by being mistaken for a new estimator. Both are constrained in place, and both were
   nearly mis-specified by the survey itself.
4. **The survey's own routing was wrong once** (2607.01377's estimators already exist). Every
   "already" claim in this doc was checked in the tree; the survey's were not always.
5. **Nothing here enters `COMPOSITE_ENGINES`.** X1-X8 feed existing engines' inputs or measure
   existing estimators.

## 7. Recommended build order

1. **X3** - trivial, new data-free information, and it pairs with the regime doc's concentration
   reads.
2. **X6** - a test, not a build, of estimators that already exist.
3. **X2** - the only item that can *remove* work, by finding components that earn nothing.
4. **X8** - small, and the cost-optimal span is immediately usable by the swing factor.
5. **X1** (offline), **X4** (offline), **X7**, **X5** - the panel-scale and producer-replacing items
   last.

**Decision requested:** whether X3 + X6 + X2 land first, and whether the panel-scale items (X1, X4)
should be scoped as a weekly offline job rather than per-run producers.
