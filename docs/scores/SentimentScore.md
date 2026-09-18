# SentimentScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md).

**Scope: the sentiment engine only.** It designs `SentimentScore` — *"how are
investors, analysts, media and markets positioned or reacting?"* — from the
owner's ten categories in
[`../ScoreWeight/news_sentiment.md`](../ScoreWeight/news_sentiment.md).

The owner's illustration draws the boundary against `NewsScore`: a contract
announcement is *information* (news); analysts turning positive is
*interpretation* (sentiment); +8% on 3× volume is *price* (technical). **Three
separate observations.**

Status: **design (2026-09-17). Not started.** Most of the ten categories are
buildable from existing producers (§1); the engine has **four holes** and one
missing output shape (the confirmation quadrant, §0.3).

---

## 0. What this engine answers, and the four holes

### 0.1 The owner's weight table

| Category | Weight | Status |
| --- | --: | --- |
| News sentiment | **15%** | SCORABLE — `sentiment.aggregate_weighted_sentiment:616`, `daily_sentiment_sma:501` |
| Sentiment momentum | **15%** | **PARTIAL** — a **7-day innovation** exists; the owner's `Sentiment_today − Sentiment_20d` does not |
| Sentiment breadth | **10%** | **PARTIAL** — per-day `neutral_share` + modal agreement; no per-source positive share |
| Institutional sentiment | **15%** | **PARTIAL** — a raw holdings level, bound to the **fundamentals** toolset |
| Analyst sentiment | **10%** | SCORABLE — `analyst_revisions.revision_ratio:79`, `consensus.agreement_score:14` |
| Retail / social | **10%** | SCORABLE — `sentiment.compute_social_scores:273` |
| Options sentiment | **10%** | SCORABLE — `options_surface.iv_skew:25`, `put_call_oi_concentration:34`, `volatility_risk_premium:65` |
| Short interest | **5%** | **PARTIAL** — raw level only; no percentile or change basis |
| Dispersion | **5%** | SCORABLE — `sentiment.sentiment_dispersion:209` |
| Extreme / crowding | **5%** | **PARTIAL** — display-only bands from hardcoded constants |

**The four holes**: 20-day momentum (only a 7-day innovation exists),
acceleration (a producer exists and is unwired), per-source breadth, and
institutional sentiment on the sentiment surface.

### 0.2 What the evidence says, and how it constrains the score

1. **Sentiment is short-horizon and partly reversing.** Media pessimism predicts
   *next-day* declines that largely reverse within days; extremes predict
   *volume*; and low returns produce more pessimistic tone (a feedback loop). So
   this engine is an **event/confirmation variable**, not a permanent alpha
   weight — which is consistent with the owner's 7.5% research allocation.
2. **High aggregate sentiment predicts *lower* subsequent returns**, concentrated
   in hard-to-value, hard-to-arbitrage names. The cross-sectional sign is
   contrarian and name-dependent: a high `SentimentScore` is **not** a buy.
3. **Attention and tone are different signals with opposite short-horizon
   signs.** Attention spikes → negative next-day returns; bullish tone →
   positive. They must not be merged into one "buzz" number, which is exactly
   what `mention_volume:43` + `aggregate_weighted_sentiment:616` would do if
   summed naively.
4. **Short interest predicts negative returns** (transient, magnitude debated);
   **analyst dispersion predicts lower returns** (Diether-Malloy-Scherbina —
   with the caveat that some of it is PEAD); **the put-call ratio is a
   positioning gauge, not a predictor**, and extremes may be hedging rather than
   speculation. Three of the owner's ten categories therefore have a **negative
   or ambiguous** expected sign, which the direction column must state.

### 0.3 The missing output shape — Sentiment × Price Confirmation

The owner's rule: *"don't assume positive sentiment is bullish."* The 2×2:

| Sentiment | Price | Verdict |
| --- | --- | --- |
| positive | rising | **confirmed positive** |
| positive | falling | **divergence** |
| negative | falling | **confirmed negative** |
| negative | rising | **divergence** |

**What exists is PARTIAL and differently shaped.** `sentiment_research.sentiment_lead_lag:65`
(with `innovations=True`) computes `Corr(dSentiment, dPrice)` per name;
`sentiment_research.sentiment_factor_scale:570` turns sign-agreement with the
*measured historical IC direction* into a 0.8/1.0/1.2 sizing multiplier, wired
through `overlays.fold_sentiment_into_overlay:121` ←
`trading_graph._sentiment_factor_read:1178` and **gated off by default**
(`enable_sentiment_factor`, `default_config.py:815`).

Two things are wrong with using that as the owner's check, both recorded in §3:
the wired read is a **single-name self-correlation** used as a sign gate (not a
cross-sectional IC), and it hardcodes `source="eodhd"` with no fallback. **The
quadrant label and a market-adjusted (abnormal) return do not exist.** The
design: the quadrant **is** the interface — `sentiment = +0.72` alone is not
actionable.

---

## 1. Component ledger

| Component | Weight | Status | Producer (`module.function:line`) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| News sentiment | 15 | SCORABLE | `sentiment.aggregate_weighted_sentiment:616`; `sentiment.aggregate_daily_sentiment:438`; `sentiment.daily_sentiment_sma:501`; `sentiment.weighted_rolling_sentiment:722`; leaves `get_news_sentiment` (news_data_tools:110) / `get_news_sentiment_series` (analysis_tools:6793) | `score` / `unweighted` / `weighted` / `sma_7d` | higher = bullish | -1..1 per-day level; `neutral_share` 0-1 | GDELT fallback delivers -100..100 through the same route (defect) |
| News sentiment → weighted level (sub) | — | SCORABLE | `sentiment.aggregate_weighted_sentiment:616` | `weighted`, `unweighted`, `n` | higher = bullish | -1..1 | gated `enable_weighted_sentiment_agg` (default False, default_config.py:1044) |
| News sentiment → 7d SMA (sub) | — | SCORABLE | `sentiment.daily_sentiment_sma:501` | `sma_7d` | higher = bullish | -1..1 | — |
| News sentiment → innovation (sub) | — | SCORABLE | `sentiment.daily_sentiment_sma:501` | `innovation` | positive = improving | -1..1, `score_t − sma_7d_{t−1}` | 7-day, not 20-day |
| Sentiment momentum | 15 | PARTIAL | only `sentiment.daily_sentiment_sma:501` (`innovation`, 7-day) and `sentiment.weighted_rolling_sentiment:722` (10-day exp window) | `innovation`, `weighted` | positive = improving | -1..1 | spec's `Sentiment_today − Sentiment_20d` ABSENT |
| Momentum → acceleration (sub) | — | UNWIRED | `sentiment.sentiment_velocity:25` (OLS slope/day) | (none) | positive = accelerating | sentiment-points/day | no production caller (tests only) |
| Sentiment breadth | 10 | PARTIAL | `sentiment.aggregate_weighted_sentiment:616` (`neutral_share`); `sentiment.sentiment_dispersion:209` (`agreement`) | `neutral_share`, `agreement` | n/a | 0-1 share | no per-source positive-share producer |
| Breadth → crowd bull share (sub) | — | PARTIAL | `sentiment.crowd_ratio:163` | `ratio`, `net_share`, `band` | high = crowded-bullish | ratio 0-100 (B/(B+BE)×100) | social counts only, not news/analyst/institutional sources |
| Institutional sentiment | 15 | PARTIAL | leaf `get_institution_holdings` (moomoo_extra_tools:226); raw level only | institution % of float + Chg (pp) | rising = accumulation | % of float, pp change | bound to **fundamentals_company_tools (toolsets.py:395)**, no score/percentile/flow |
| Institutional → flow proxy (sub) | — | PARTIAL | leaf `get_orderflow_read` (analysis_tools:1215) ← `strategies.orderflow.summarize` | `inst_net`, `retail_net`, `distribution_score` | inst_net>0 = accumulation | shares; distribution 0-1 | market toolset only; not institutional ownership |
| Analyst sentiment | 10 | SCORABLE | `analyst_revisions.revision_ratio:79`; `consensus.agreement_score:14`; `consensus.weighted_consensus:32`; leaves `get_analyst_verdict` (analysis_tools:1383), `get_analyst_ratings` (analyst_data_tools:10), `get_analyst_revision_index` (analyst_revision_tools:43) | `index`, `ratio`, `agreement`, stance | higher index = net upgrades | index weighted `(up−down)/(up+down)`-style; ratio -1..1; agreement 0-1; stance -1..1 | revision index gated `enable_analyst_revision_index` (default False) |
| Retail & social | 10 | SCORABLE | `sentiment.compute_social_scores:273`; leaf `get_sentiment_computed` (analysis_tools:6759); sentiment_analyst prefetch (StockTwits/Reddit) | `computed_score`, `computed_velocity`, counts | higher = bullish | `computed_score` -1..1; `computed_velocity` z-score | velocity/breadth helpers unwired (below) |
| Retail → mention heat (sub) | — | UNWIRED | `sentiment.mention_volume:43` | (none) | >1 = hot | ratio recent/baseline | no production caller (tests only) |
| Options sentiment | 10 | SCORABLE | leaves `get_options_iv_read` (analysis_tools:6034), `get_derivatives_flow` (3142), `get_options_surface` (7553), `get_options_chain` (market_position_tools:121); producers `options_surface.iv_skew:25`, `put_call_oi_concentration:34`, `volatility_risk_premium:65`, `expected_move_from_chain:50` | skew, PCR, VRP, expected move, gamma regime | puts rich / PCR>1 = bearish/fear | skew ratio; PCR ratio; VRP %; move % | no composite options-sentiment score |
| Short interest | 5 | PARTIAL | leaf `get_short_interest` (market_position_tools:220) → `yfinance_short_interest.get_short_interest_yfinance:37` / `massive.get_short_interest_massive:485`; `get_short_sale_volume` (analysis_tools:8886); `get_short_volume` (market_position_tools:238) | shares short, days-to-cover, %float, short-sale % | high = bearish/crowding | %float, days, % of volume | raw only; no percentile/change-basis score |
| Dispersion | 5 | SCORABLE | `sentiment.sentiment_dispersion:209` | `dispersion`, `agreement`, `n` | higher = more disagreement | weighted population std ≥0 (polarity points); agreement 0-1 | fed by `compute_social_scores:308`, `aggregate_weighted_sentiment:704` |
| Extreme & crowding | 5 | PARTIAL | `sentiment.crowd_ratio:163` | `ratio`, `band` | crowded-bullish / crowded-bearish | 0-100 with hardcoded 40/60 bands | display-only bands, never a gate; no validated extreme measure |
| **Sentiment × Price Confirmation** (owner-named) | — | PARTIAL | `sentiment_research.sentiment_lead_lag:65` (`innovations=True`); `sentiment_research.sentiment_factor_scale:570`; wired via `overlays.fold_sentiment_into_overlay:121` ← `trading_graph._sentiment_factor_read:1178` | `rank_ic`, `innovation`, `scale` | sign agreement with measured IC | corr -1..1; scale 0.5-1.2 | no four-quadrant label, no market-adjusted (abnormal) return; gate `enable_sentiment_factor` default False (default_config.py:815) |

#

---

## 2. Tool leaves (what the analysts can actually call)

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `get_news_sentiment:110` (news_data_tools) | news_tools:373 | daily news-sentiment series (EODHD→AV→GDELT), -1..1 nominal | yes (news) |
| `get_news_sentiment_series:6793` (analysis_tools) | market_tools:279, news_tools:352 | per-day score/sma_7d/innovation + gated S4/S7 rows | yes |
| `get_sentiment_computed:6759` (analysis_tools) | market_tools:325 | `computed_score` + z velocity + counts (+ crowd row if gated) | yes (market only) |
| `get_sentiment_lead_lag:6821` (analysis_tools) | market_tools:280 | per-lag Pearson/Spearman vs forward returns | yes |
| `get_gdelt_sentiment:196` (news_data_tools) | news_tools:351 | GDELT tone series (-100..100) | yes |
| `get_orderflow_read:1215` (analysis_tools) | market_tools:274 | inst/retail net, distribution, divergence, alignment | yes |
| `get_order_imbalance:5218` (analysis_tools) | market_tools:260 | buy-heavy/sell-heavy/balanced verdict | yes |
| `get_derivatives_flow:3142` (analysis_tools) | market_tools:240 | gamma regime/walls + OPEX + embedded IV read | yes |
| `get_options_iv_read:6034` (analysis_tools) | market_tools:339 | ATM-IV move, put:call OI, put-skew, VRP | yes |
| `get_options_surface:7553` (analysis_tools) | market_tools:320 | CBOE 25Δ risk-reversal/fly, term slope | yes |
| `get_options_chain:121` (market_position_tools) | market_tools:236 | IV, OI, put/call ratio | yes |
| `get_short_interest:220` (market_position_tools) | market_tools:242 | shares short, days-to-cover, %float, ownership split | yes |
| `get_short_sale_volume:8886` (analysis_tools) | market_tools:243 | FINRA daily short-sale % of volume | yes |
| `get_short_volume:238` (market_position_tools) | market_tools:245 | daily short-volume ratio (Massive) | yes |
| `get_institution_holdings:226` (moomoo_extra_tools) | **fundamentals_company_tools:395** | institutional % of float + period change | yes — but fundamentals, not sentiment |
| `get_analyst_verdict:1383` (analysis_tools) | fundamentals_company_tools:391 | deterministic value screens (EY/EV-EBIT/F/M/Z) | yes |
| `get_analyst_revision_index:43` (analyst_revision_tools) | fundamentals_company_tools:393 | MSCI-style weighted revision ratio (gated) | yes (gated) |
| `get_analyst_ratings:10` (analyst_data_tools) | fundamentals_company_tools:386 | sell-side rating/price-target consensus | yes |
| `get_insider_transactions:152` (news_data_tools) | news_tools:364 | windowed insider-transaction flow | yes |

No sentiment toolset exists: `sentiment_analyst` binds no tools (toolsets.py module docstring; `analyst_toolset` raises `KeyError: 'sentiment'`), so the leaves above reach the sentiment engine only through the market/news analysts.

#

---

## 3. Defects and dead seams

1. **`sentiment_velocity:25` and `mention_volume:43` have no reader.** Both are exported in `__all__` (sentiment.py:824-825) but the only importers are `tests/test_strategies_sentiment.py:11-12`. The owner's momentum (acceleration) and heat/mention legs have producers but no production consumer. A reader would see the report claim momentum/acceleration is measured while nothing computes it.
2. **GDELT scale mismatch on the news-sentiment route.** `interface.py:488-492` routes `get_news_sentiment` to `gdelt: get_news_sentiment_gdelt`, whose docstring/body (gdelt.py:278-279) renders tone on **-100..100**, while the category is advertised as `-1..1` (interface.py:187) and `news_data_tools.get_news_sentiment:110` says "scale -1..1 unless noted". `_sentiment_points_gdelt:250` returns -100..100 points that flow straight into `daily_sentiment_sma`/`get_news_sentiment_series` (analysis_tools:6793) unnormalized, so a GDELT-sourced `sma_7d`/`innovation` is ~100x an EODHD/AV one.
3. **PROBED 2026-09-17 (P0-9): EODHD `/sentiments` coverage is COMPLETE for this
universe, so the missing fallback is defensive, not live.**
`trading_graph._sentiment_factor_read` hardcodes `source="eodhd"` and returns
`None` when EODHD has no series, while the leaf
(`analysis_tools.get_sentiment_lead_lag`) falls back. The probe asked how often
that costs a read: **26 of 26 names returned a non-empty series** - 16 large caps
(AMZN MSFT NVDA TSM VST WDC LRCX AMKR ASML HPE IBM JCI LULU NFLX SIMO SMCI,
73-151 daily points each over a 150-day window), four ETFs (SPY 151, QQQ 146,
IEI 46, VTV 73), a foreign listing (0700.HK 102) and an OTC name (SKHY 83), plus
BRK.B (43), RIVN (143), ARM (128) and CART (84). **No empty result, no error.**
The answer to "what the fallback order should be" is therefore: **mirror the
leaf's existing chain (EODHD -> Alpha Vantage -> GDELT) if a gap ever appears, and
change nothing now** - a fallback that never fires would be untested code on a
path that cannot currently be exercised. The gap is recorded, with the probe as
its evidence, rather than fixed speculatively.
4. **Institutional sentiment is bound to the fundamentals toolset.** `get_institution_holdings` appears only at `toolsets.py:395` (fundamentals_company_tools), never in market_tools/news_tools. Combined with the sentiment analyst binding zero tools (toolsets.py:1-19 docstring), institutional sentiment is unreachable from the sentiment surface — it exists only as a raw holdings table for the fundamentals analyst.
4. **Dispersion/crowd producers are gated and mislocated.** `sentiment_dispersion:209` and `crowd_ratio:163` reach a tool only through `get_sentiment_computed` (analysis_tools:6759 → `_render_crowd_row:6661`), bound to **market_tools:325** behind `enable_crowd_ratio_bands` (default False, default_config.py:1045). The sentiment report is produced by the sentiment analyst, which never calls them.
5. **Weighted aggregation is gated off and off-surface.** `aggregate_weighted_sentiment:616` is reached only via `_sentiment_agg_rows:6735` under `enable_weighted_sentiment_agg` (default False, default_config.py:1044), and only from `get_news_sentiment_series` (market/news), not from the sentiment analyst.
6. **`_sentiment_factor_read:1178` hardcodes `source="eodhd"`** (trading_graph.py:1235) and, when EODHD returns nothing, returns None rather than falling back to AV/GDELT — while the leaf `get_sentiment_lead_lag` (analysis_tools:6846-6878) does fall back. The wired confirmation fold therefore silently degrades to neutral 1.0 on names where EODHD has no /sentiments coverage.
7. **`_sentiment_factor_read`'s `rank_ic` is a single-name self-correlation**, not a cross-sectional IC (trading_graph.py:1216-1230 correlates the name's own sentiment with its own forward returns, max_lags=5). It is used as a sign gate by `sentiment_factor_scale:570`, not as the owner's market-adjusted confirmation.
8. **Dead seams: `weighted_sentiment:109`, `blended_score:79`, `consensus_verdict:66`, `decayed_weight:91`** have no production readers (grep across engine + executor + web: module + tests only).
9. **Crowd bands are hardcoded constants** `_CROWD_BULL`/`_CROWD_BEAR` (sentiment.py, immediately above `crowd_ratio:163`) with no percentile basis — the source-convention 40/60 split is a constant by construction.

#

---

## 4. What is ABSENT, and the smallest honest producer for it

| ABSENT / PARTIAL | Data needed | Already fetched? (adapter/leaf) | Smallest honest producer |
| --- | --- | --- | --- |
| Sentiment momentum `Sentiment_today − Sentiment_20d` | 20+ calendar days of daily sentiment | yes — `_sentiment_points_eodhd:153`, `_sentiment_points_alpha_vantage:5`; consumed by `daily_sentiment_sma:501`, `weighted_rolling_sentiment:722` | add a 20-day delta beside `sma_7d` in `daily_sentiment_sma` (calendar-reindex, None-safe) |
| Sentiment acceleration | daily sentiment series | yes — same points | surface `sentiment_velocity:25` on the series (it already takes `window=5` slope/day) |
| Sentiment breadth (per-source positive share) | per-article polarity + source tag | yes — `aggregate_weighted_sentiment:616` holds per-article `score`; `_article_url:612` gives the host | per-day `mean(s>0)` and a per-source-host breakdown; feed the same rows `neutral_share` uses |
| Institutional sentiment change/flow | institutional % of float history (13F cadence) | yes — `get_institution_holdings` (moomoo_extra_tools:226), `get_short_interest_yfinance:37` ownership split | period-over-period Δ in inst % of float, z-scored; bind the leaf to the sentiment/market surface |
| Sentiment heat / mention volume | per-day mention counts | yes — StockTwits counts in `compute_social_scores:273`, `_baseline_file:265` rolling buffer | surface `mention_volume:43` on the persisted count baseline |
| Short-interest percentile/change | short % of float over several settlements | yes — `get_short_interest_massive:485` (multi-settlement, newest-first); `get_short_interest_yfinance:37` | percentile of current short % of float vs the settlement series already returned |
| Extreme/crowding with a stated scale | crowd ratio history | yes — `compute_social_scores:273` + `_baseline_file:265` | percentile of `crowd_ratio` ratio vs the ticker's own persisted baseline (replaces the fixed 40/60 constant) |
| Sentiment × Price Confirmation quadrant `Sign(dSentiment) × Sign(abnormal return)` | dSentiment + market-adjusted return | sentiment: `daily_sentiment_sma:501` innovation / `_sentiment_factor_read:1178`; benchmark closes: `_ohlcv`/`get_relative_strength`/`_sentiment_factor_read` (closes passed in) | `sign(innovation) × sign(name_ret − bench_ret)` over the last session → {confirm-up, confirm-down, diverge-up, diverge-down}; no producer exists today |

---

## 5. The composite — how `SentimentScore` gets built

1. **The quadrant is the headline output, not the score.** Per §0.3, the
   actionable object is `Sign(dSentiment) × Sign(abnormal return)`. The 0-100
   score is the second output.
2. **Attention and tone stay separate rows.** Per §0.2 point 3, `mention_volume`
   (attention) and the tone aggregates must never be summed into one number; they
   have opposite short-horizon signs.
3. **Signs are stated per component, including the negative ones.** Short
   interest, dispersion and the put-call ratio do not have "higher = bullish"
   directions (a high PCR may be hedging); the direction column is part of the
   component contract, and the report prints the raw value beside the aligned
   contribution.
4. **`NA ≠ 0`** (master rule 1): the four holes reduce the available weight.
5. **Its own band table**, advisory, feeding nothing (master rule 2).
6. **This engine never sizes.** `sentiment_factor_scale:570`'s 0.8/1.0/1.2
   multiplier is a *sizing* output and stays where it is; the score is
   diagnostic. If the owner later wants the score to size, that is a new
   decision, not a consequence of this document.
7. **No news number crosses the boundary.** The couplings in
   [`NewsScore.md`](NewsScore.md) §0.3 are the constraint; this engine reads the
   tone and positioning pipeline, not `news_relevance.score_news_article:53`.

### 5.1 The scale hazard this engine inherits

The news-sentiment route has **two scales behind one name**: EODHD/Alpha Vantage
deliver −1..1, GDELT delivers **−100..100** (`gdelt.get_news_sentiment_gdelt:278`,
`_sentiment_points_gdelt:250`) and the routing (`interface.py:488-492`) does not
normalise, while the category is advertised as −1..1
(`interface.py:187`, `news_data_tools.get_news_sentiment:110`). A GDELT-sourced
`sma_7d` or `innovation` is therefore ~100× an EODHD one.

**Consequence: the score cannot be built on the raw aggregate without first
pinning the unit.** This is a prerequisite, not a refinement — and it is the same
class of defect as the choppiness double-scale in
[`RegimeScore.md`](RegimeScore.md) §3. Recorded in §3 defect 2 and in the
master's §3.2.

---

## 6. Verification requirements

1. **Unit test for the scale**: a GDELT-sourced series and an EODHD-sourced
   series over the same window must produce comparable `sma_7d`/`innovation`
   values, or the code must refuse to mix them.
2. **The quadrant is tested with four fixtures** (one per cell) and must produce
   four distinct labels.
3. **Attention ≠ tone**: a test asserts `mention_volume` and the tone aggregate
   enter the score as separate components.
4. **`NA ≠ 0`**: with the four holes absent, coverage drops and the score is the
   weighted mean of what remains; with nothing available, `None`.
5. **No cross-engine import**: a test asserts no `news_relevance` function is
   imported by the sentiment path.
6. **The gated producers are exercised in the test** (`enable_weighted_sentiment_agg`,
   `enable_crowd_ratio_bands`) so the default-off flags do not hide a broken path.

---

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Does the score size, or only inform?** Today the only wired confirmation
   path is a *sizing* multiplier (`sentiment_factor_scale:570`, default off).
   The owner's staged table puts SentimentScore at 7.5% of a research composite —
   a score, not a multiplier. Both can exist; they must not be the same object. **CLOSED 2026-09-17 (plan §13 Q10): the score informs only** — `sentiment_factor_scale` stays a separate sizing multiplier.
2. **Which institutional measure** — holdings level, period-over-period Δ, or the
   orderflow proxy (`orderflow.summarize` via `get_orderflow_read:1215`)? They answer different questions and only the first is currently on the fundamentals
surface. **DECIDED 2026-09-17:** the **period-over-period change** in institutional
holdings is canonical - a 70% institutional level says nothing about whether
institutional sentiment is improving. The level stays contextual and the orderflow
proxy stays a **separate diagnostic**, never a silent substitute.
3. **Is a "sentiment toolset" needed?** `sentiment_analyst` binds **no tools**
   (`agents/toolsets.py`; `analyst_toolset` raises `KeyError: 'sentiment'`), so
   every leaf in §2 reaches this engine only through the market or news analyst.
   If SentimentScore is to be built, this is the wiring decision that gates it. **CLOSED 2026-09-17 (plan §13 Q5): the toolset exists** — bind `sentiment_analyst` and register `sentiment`.
4. **Should the 20-day momentum be a delta or a regression slope?**
   `sentiment_velocity:25` already computes an OLS slope/day (unwired);
   `daily_sentiment_sma:501` gives a 7-day innovation. The owner's formula is a simple difference. **DECIDED 2026-09-17:** the
**regression slope is canonical** (`sentiment_velocity:25`) - no second 20-day
delta producer. The three outputs answer different questions: **level** (where
sentiment is), **slope** (its direction and rate), **innovation** (the recent shock).
5. **Do the crowd bands become percentile-based?** Today `_CROWD_BULL`/`_CROWD_BEAR`
   are hardcoded 40/60 (`sentiment.py`, above `crowd_ratio:163`) with no percentile basis, and the baseline file exists to compute one. **DECIDED
2026-09-17:** move to **percentile bands over the name's own history** (<= 20th
crowd-bearish extreme, 20-80 neutral/mixed, >= 80th crowd-bullish extreme), keep the
current 40/60 constants as the **fallback until enough history exists**, and keep the
percentile thresholds **configuration, not hard-coded methodology**.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Media pessimism predicts next-day declines that **reverse within days**; extremes predict volume; low returns produce more pessimistic tone | Tetlock | §0.2 point 1 — event/confirmation variable, not a permanent alpha weight |
| High aggregate sentiment predicts **lower** subsequent returns, concentrated in hard-to-value, hard-to-arbitrage names | Baker & Wurgler | §0.2 point 2 — the cross-sectional sign is contrarian |
| **Attention** spikes predict negative next-day returns while **bullish sentiment** predicts positive ones; small caps are more sensitive | Da, Engelberg & Gao; the StockTwits literature | §0.2 point 3 and §5 item 2 — attention and tone must not be merged |
| Short interest predicts negative future returns (transient; economic significance debated) | the short-interest literature | §0.2 point 4 and §5 item 3 — a negative-direction component |
| Analyst forecast **dispersion** predicts lower returns (Diether, Malloy & Scherbina), with some of the effect attributed to PEAD | the dispersion literature | §0.2 point 4 — dispersion's sign is negative |
| The put-call ratio is a positioning gauge, not a standalone predictor; extremes may reflect hedging | options-sentiment reviews | §0.2 point 4 and §5 item 3 — ambiguous sign, stated as such |
| Crowded positions suffer more severe drawdowns in bad states | the crowding literature | §0.2 point 2 — supports the small research weight and the extreme/crowding row |
