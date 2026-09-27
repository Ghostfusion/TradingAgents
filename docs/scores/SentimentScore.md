# SentimentScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md), [`MarketScore.md`](MarketScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the sentiment engine only.** It designs `SentimentScore` — *"how are
investors, analysts, media and markets positioned or reacting?"* — from the
owner's ten categories in
[`../ScoreWeight/news_sentiment.md`](../ScoreWeight/news_sentiment.md).

The owner's illustration draws the boundary against `NewsScore`: a contract
announcement is *information* (news); analysts turning positive is
*interpretation* (sentiment); +8% on 3× volume is *price* (technical). **Three
separate observations.**

Status: **built (2026-09-18); gate off by default.** `strategies/sentiment_score.py` is the engine (including the confirmation quadrant §0.3 recorded as missing), `get_sentiment_score` its leaf and `enable_sentiment_score` its membership switch. It participates in the **research allocation only** - never in the decision composite (master rule 17). The four holes §1 records are still holes. **[CORRECTED 2026-09-26: three holes — §7 Q4 closed the 20-day delta by making the OLS slope `sentiment.sentiment_velocity:37` canonical and refusing a second 20-day delta producer.]** **Unmeasured** (vendor gate).

---

## 0. What this engine answers, and the four holes

### 0.1 The owner's weight table

| Category | Weight | Status |
| --- | --: | --- |
| News sentiment | **15%** | SCORABLE — `sentiment.aggregate_weighted_sentiment:845`, `daily_sentiment_sma:501` |
| Sentiment momentum | **15%** | **PARTIAL** — a **7-day innovation** exists; the owner's `Sentiment_today − Sentiment_20d` does not **[CORRECTED 2026-09-26: §7 Q4 retired this hole — the OLS slope `sentiment.sentiment_velocity:37` is the canonical momentum measure and a second 20-day delta is explicitly not built]** |
| Sentiment breadth | **10%** | **PARTIAL** — per-day `neutral_share` + modal agreement; no per-source positive share |
| Institutional sentiment | **15%** | **PARTIAL** — a raw holdings level, bound to the **fundamentals** toolset |
| Analyst sentiment | **10%** | SCORABLE — `analyst_revisions.revision_ratio:79`, `consensus.agreement_score:14` |
| Retail / social | **10%** | SCORABLE — `sentiment.compute_social_scores:488` |
| Options sentiment | **10%** | SCORABLE — `options_surface.iv_skew:25`, `put_call_oi_concentration:34`, `volatility_risk_premium:65` |
| Short interest | **5%** | **PARTIAL** — raw level only; no percentile or change basis |
| Dispersion | **5%** | SCORABLE — `sentiment.sentiment_dispersion:400` |
| Extreme / crowding | **5%** | **PARTIAL** — display-only bands from hardcoded constants |

**The four holes**: 20-day momentum (only a 7-day innovation exists),
acceleration (a producer exists and is unwired), per-source breadth, and
institutional sentiment on the sentiment surface. **[CORRECTED 2026-09-26: it is
now **three** holes — §7 Q4 closed the 20-day delta by making the OLS slope
`sentiment.sentiment_velocity:37` canonical and forbidding a second 20-day delta
producer.]**

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

**What exists is PARTIAL and differently shaped.** `sentiment_research.sentiment_lead_lag:172`
(with `innovations=True`) computes `Corr(dSentiment, dPrice)` per name;
`sentiment_research.sentiment_factor_scale:677` turns sign-agreement with the
*measured historical IC direction* into a 0.8/1.0/1.2 sizing multiplier, wired
through `overlays.fold_sentiment_into_overlay:198` ←
`trading_graph._sentiment_factor_read:1420` and **gated off by default**
(`enable_sentiment_factor`, `default_config.py:821`).

Two things are wrong with using that as the owner's check, both recorded in §3:
the wired read is a **single-name self-correlation** used as a sign gate (not a
cross-sectional IC), and it hardcodes `source="eodhd"` with no fallback. **The
quadrant label and a market-adjusted (abnormal) return do not exist.** **[CORRECTED
2026-09-26: both are built. `tradingagents/strategies/sentiment_score.py::confirmation_quadrant:342`
returns four distinct labels — `confirm-up` / `diverge-up` / `confirm-down` /
`diverge-down`, keyed on the *price* direction — and
`tradingagents/agents/utils/analysis_tools.py::_sentiment_price_read:6712` computes
the market-adjusted (abnormal) return (name return − benchmark return). This
document's own §8.1 §99/§100 already record them built.]** The
design: the quadrant **is** the interface — `sentiment = +0.72` alone is not
actionable.

---

## 1. Component ledger

| Component | Weight | Status | Producer (`module.function:line`) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| News sentiment | 15 | SCORABLE | `sentiment.aggregate_weighted_sentiment:845`; `sentiment.aggregate_daily_sentiment:667`; `sentiment.daily_sentiment_sma:730`; `sentiment.weighted_rolling_sentiment:968`; leaves `get_news_sentiment` (news_data_tools:110) / `get_news_sentiment_series` (analysis_tools:6793) | `score` / `unweighted` / `weighted` / `sma_7d` | higher = bullish | -1..1 per-day level; `neutral_share` 0-1 | GDELT fallback delivers -100..100 through the same route (defect) |
| News sentiment → weighted level (sub) | — | SCORABLE | `sentiment.aggregate_weighted_sentiment:845` | `weighted`, `unweighted`, `n` | higher = bullish | -1..1 | gated `enable_weighted_sentiment_agg` (default False, default_config.py:1044) |
| News sentiment → 7d SMA (sub) | — | SCORABLE | `sentiment.daily_sentiment_sma:730` | `sma_7d` | higher = bullish | -1..1 | — |
| News sentiment → innovation (sub) | — | SCORABLE | `sentiment.daily_sentiment_sma:730` | `innovation` | positive = improving | -1..1, `score_t − sma_7d_{t−1}` | 7-day, not 20-day |
| Sentiment momentum | 15 | PARTIAL | only `sentiment.daily_sentiment_sma:730` (`innovation`, 7-day) and `sentiment.weighted_rolling_sentiment:968` (10-day exp window) | `innovation`, `weighted` | positive = improving | -1..1 | spec's `Sentiment_today − Sentiment_20d` ABSENT **[CORRECTED 2026-09-26: §7 Q4 closed this — the regression slope `sentiment_velocity:25` is canonical; the 20-day delta is deliberately not built]** |
| Momentum → acceleration (sub) | — | UNWIRED | `sentiment.sentiment_velocity:37` (OLS slope/day) | (none) | positive = accelerating | sentiment-points/day | no production caller (tests only) |
| Sentiment breadth | 10 | PARTIAL | `sentiment.aggregate_weighted_sentiment:845` (`neutral_share`); `sentiment.sentiment_dispersion:400` (`agreement`) | `neutral_share`, `agreement` | n/a | 0-1 share | no per-source positive-share producer |
| Breadth → crowd bull share (sub) | — | PARTIAL | `sentiment.crowd_ratio:336` | `ratio`, `net_share`, `band` | high = crowded-bullish | ratio 0-100 (B/(B+BE)×100) | social counts only, not news/analyst/institutional sources |
| Institutional sentiment | 15 | PARTIAL | leaf `get_institution_holdings` (moomoo_extra_tools:226); raw level only | institution % of float + Chg (pp) | rising = accumulation | % of float, pp change | bound to **fundamentals_company_tools (toolsets.py:395)**, no score/percentile/flow |
| Institutional → flow proxy (sub) | — | PARTIAL | leaf `get_orderflow_read` (analysis_tools:1215) ← `strategies.orderflow.summarize` | `inst_net`, `retail_net`, `distribution_score` | inst_net>0 = accumulation | shares; distribution 0-1 | market toolset only; not institutional ownership |
| Analyst sentiment | 10 | SCORABLE | `analyst_revisions.revision_ratio:79`; `consensus.agreement_score:14`; `consensus.weighted_consensus:32`; leaves `get_analyst_verdict` (analysis_tools:1383), `get_analyst_ratings` (analyst_data_tools:10), `get_analyst_revision_index` (analyst_revision_tools:43) | `index`, `ratio`, `agreement`, stance | higher index = net upgrades | index weighted `(up−down)/(up+down)`-style; ratio -1..1; agreement 0-1; stance -1..1 | revision index gated `enable_analyst_revision_index` (default False) |
| Retail & social | 10 | SCORABLE | `sentiment.compute_social_scores:488`; leaf `get_sentiment_computed` (analysis_tools:6759); sentiment_analyst prefetch (StockTwits/Reddit) | `computed_score`, `computed_velocity`, counts | higher = bullish | `computed_score` -1..1; `computed_velocity` z-score | velocity/breadth helpers unwired (below) |
| Retail → mention heat (sub) | — | UNWIRED | `sentiment.mention_volume:171` | (none) | >1 = hot | ratio recent/baseline | no production caller (tests only) |
| Options sentiment | 10 | SCORABLE | leaves `get_options_iv_read` (analysis_tools:6034), `get_derivatives_flow` (3142), `get_options_surface` (7553), `get_options_chain` (market_position_tools:121); producers `options_surface.iv_skew:25`, `put_call_oi_concentration:34`, `volatility_risk_premium:65`, `expected_move_from_chain:50` | skew, PCR, VRP, expected move, gamma regime | puts rich / PCR>1 = bearish/fear | skew ratio; PCR ratio; VRP %; move % | no composite options-sentiment score |
| Short interest | 5 | PARTIAL | leaf `get_short_interest` (market_position_tools:220) → `yfinance_short_interest.get_short_interest_yfinance:81` / `massive.get_short_interest_massive:485`; `get_short_sale_volume` (analysis_tools:8886); `get_short_volume` (market_position_tools:238) | shares short, days-to-cover, %float, short-sale % | high = bearish/crowding | %float, days, % of volume | raw only; no percentile/change-basis score |
| Dispersion | 5 | SCORABLE | `sentiment.sentiment_dispersion:400` | `dispersion`, `agreement`, `n` | higher = more disagreement | weighted population std ≥0 (polarity points); agreement 0-1 | fed by `compute_social_scores:308`, `aggregate_weighted_sentiment:704` |
| Extreme & crowding | 5 | PARTIAL | `sentiment.crowd_ratio:336` | `ratio`, `band` | crowded-bullish / crowded-bearish | 0-100 with hardcoded 40/60 bands | display-only bands, never a gate; no validated extreme measure |
| **Sentiment × Price Confirmation** (owner-named) | — | PARTIAL | `sentiment_research.sentiment_lead_lag:172` (`innovations=True`); `sentiment_research.sentiment_factor_scale:677`; wired via `overlays.fold_sentiment_into_overlay:198` ← `trading_graph._sentiment_factor_read:1420` | `self_lead_lag`, `innovation`, `scale` | sign agreement with measured IC | corr -1..1; scale 0.5-1.2 | no four-quadrant label, no market-adjusted (abnormal) return; gate `enable_sentiment_factor` default False (default_config.py:815) **[CORRECTED 2026-09-26: both now exist — `sentiment_score.confirmation_quadrant:342` (four labels) and `analysis_tools._sentiment_price_read:6712` (abnormal return); see §0.3. The gate note applies only to the legacy sign-gate fold]** |

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

No sentiment toolset exists: `sentiment_analyst` binds no tools (toolsets.py module docstring; `analyst_toolset` raises `KeyError: 'sentiment'`), so the leaves above reach the sentiment engine only through the market/news analysts. **[CORRECTED 2026-09-26: the toolset now exists — `tradingagents/agents/toolsets.py:523` defines `sentiment_tools()` (11 leaves, including `get_institution_holdings`), and `:577-578` `analyst_toolset("sentiment")` returns it; §7 Q3 records the decision. This paragraph describes the pre-2026-09-17 state.]**

#

---

## 3. Defects and dead seams

1. **`sentiment_velocity:25` and `mention_volume:43` have no reader.** Both are exported in `__all__` (sentiment.py:824-825) but the only importers are `tests/test_strategies_sentiment.py:11-12`. The owner's momentum (acceleration) and heat/mention legs have producers but no production consumer. A reader would see the report claim momentum/acceleration is measured while nothing computes it.
2. **GDELT scale mismatch on the news-sentiment route.** `interface.py:488-492` routes `get_news_sentiment` to `gdelt: get_news_sentiment_gdelt`, whose docstring/body (gdelt.py:278-279) renders tone on **-100..100**, while the category is advertised as `-1..1` (interface.py:187) and `news_data_tools.get_news_sentiment:110` says "scale -1..1 unless noted". `_sentiment_points_gdelt:250` returns -100..100 points that flow straight into `daily_sentiment_sma`/`get_news_sentiment_series` (analysis_tools:6793) unnormalized, so a GDELT-sourced `sma_7d`/`innovation` is ~100x an EODHD/AV one.
3. **PROBED 2026-09-17 (P0-9): EODHD `/sentiments` coverage is COMPLETE for this
universe, so the missing fallback is defensive, not live.**
`trading_graph._sentiment_factor_read` hardcodes `source="eodhd"` and returns
`None` when EODHD has no series, while the leaf
(`analysis_tools.get_sentiment_lead_lag`) falls back. [CORRECTED 2026-09-26: the hardcoding is gone (SENT-13) — the read calls `_sentiment_points_fallback:1392`, which walks the EODHD → Alpha Vantage → GDELT chain, and returns `"source": str(source or "")` (`trading_graph.py:1420-1500`) naming the feed that actually answered; every point is normalised through `normalise_sentiment` on arrival. The probe's 26-of-26 result is unchanged, so the fallback remains defensive rather than live.] The probe asked how often
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
4. **Institutional sentiment is bound to the fundamentals toolset.** `get_institution_holdings` appears only at `toolsets.py:404` (fundamentals_company_tools), never in market_tools/news_tools. Combined with the sentiment analyst binding zero tools (toolsets.py:1-19 docstring), institutional sentiment is unreachable from the sentiment surface — it exists only as a raw holdings table for the fundamentals analyst.
5. **Dispersion/crowd producers are gated and mislocated.** `sentiment_dispersion:209` and `crowd_ratio:163` reach a tool only through `get_sentiment_computed` (analysis_tools:6759 → `_render_crowd_row:6661`), bound to **market_tools:325** behind `enable_crowd_ratio_bands` (default False, default_config.py:1045). The sentiment report is produced by the sentiment analyst, which never calls them.
6. **Weighted aggregation is gated off and off-surface.** `aggregate_weighted_sentiment:616` is reached only via `_sentiment_agg_rows:6735` under `enable_weighted_sentiment_agg` (default False, default_config.py:1044), and only from `get_news_sentiment_series` (market/news), not from the sentiment analyst.
7. **`_sentiment_factor_read:1420` hardcodes `source="eodhd"`** (trading_graph.py:1235) and, when EODHD returns nothing, returns None rather than falling back to AV/GDELT — while the leaf `get_sentiment_lead_lag` (analysis_tools:6846-6878) does fall back. The wired confirmation fold therefore silently degrades to neutral 1.0 on names where EODHD has no /sentiments coverage. [CORRECTED 2026-09-26: **fixed (SENT-13)** — the read no longer hardcodes the source: `_sentiment_points_fallback:1392` walks EODHD → Alpha Vantage → GDELT and `"source"` names the feed that answered (`trading_graph.py:1420-1500`); the stated consequence (a silent neutral fold on an EODHD miss) no longer applies, and the method's line is `:1420`, not `:1178`. The §-number and the coverage probe's conclusion stand.]
8. **`_sentiment_factor_read`'s `rank_ic` is a single-name self-correlation**, not a cross-sectional IC (trading_graph.py:1216-1230 correlates the name's own sentiment with its own forward returns, max_lags=5). It is used as a sign gate by `sentiment_factor_scale:570`, not as the owner's market-adjusted confirmation. [CORRECTED 2026-09-26: **the statistic now carries its real name (SENT-13)** — the read returns `self_lead_lag` (the lead/lag block is `trading_graph.py:1479-1493`), `overlays.fold_sentiment_into_overlay:198` passes `sentiment_ctx["self_lead_lag"]` into the gate (the call itself is `overlays.py:223`), and the key `rank_ic` is gone from that path. Only `sentiment_research.sentiment_factor_scale`'s own **parameter** is still spelled `rank_ic` (`sentiment_research.py:678`) — a private helper name, not the read's key. The reading here (a single-name self-correlation, not a cross-sectional IC; replaced by `sentiment_score.confirmation_quadrant`) stands.]
9. **Dead seams: `weighted_sentiment:109`, `blended_score:79`, `consensus_verdict:66`, `decayed_weight:91`** have no production readers (grep across engine + executor + web: module + tests only). [CORRECTED 2026-09-26: **resolved (SENT-14)** — the first three were **deleted**, not kept (`sentiment.py:18-22`), so they no longer exist to be dead; `decayed_weight` survives at `:194` (the `:91` here was stale) and **does** have a production reader, the aggregation's per-message weight loop (`sentiment.py:935`), so the "no production readers" claim is now false for it. The row's remaining open half is the news path's: `_news_components` never calls the decay half (D-9).]
10. **Crowd bands are hardcoded constants** `_CROWD_BULL`/`_CROWD_BEAR` (sentiment.py, immediately above `crowd_ratio:163`) with no percentile basis — the source-convention 40/60 split is a constant by construction.

#

---

## 4. What is ABSENT, and the smallest honest producer for it

| ABSENT / PARTIAL | Data needed | Already fetched? (adapter/leaf) | Smallest honest producer |
| --- | --- | --- | --- |
| Sentiment momentum `Sentiment_today − Sentiment_20d` | 20+ calendar days of daily sentiment | yes — `_sentiment_points_eodhd:153`, `_sentiment_points_alpha_vantage:5`; consumed by `daily_sentiment_sma:501`, `weighted_rolling_sentiment:722` | add a 20-day delta beside `sma_7d` in `daily_sentiment_sma` (calendar-reindex, None-safe) **[CORRECTED 2026-09-26: no longer a hole — §7 Q4 makes the slope `sentiment_velocity:25` canonical and refuses this second 20-day delta producer]** |
| Sentiment acceleration | daily sentiment series | yes — same points | surface `sentiment_velocity:25` on the series (it already takes `window=5` slope/day) |
| Sentiment breadth (per-source positive share) | per-article polarity + source tag | yes — `aggregate_weighted_sentiment:616` holds per-article `score`; `_article_url:612` gives the host | per-day `mean(s>0)` and a per-source-host breakdown; feed the same rows `neutral_share` uses |
| Institutional sentiment change/flow | institutional % of float history (13F cadence) | yes — `get_institution_holdings` (moomoo_extra_tools:226), `get_short_interest_yfinance:37` ownership split | period-over-period Δ in inst % of float, z-scored; bind the leaf to the sentiment/market surface |
| Sentiment heat / mention volume | per-day mention counts | yes — StockTwits counts in `compute_social_scores:273`, `_baseline_file:265` rolling buffer | surface `mention_volume:43` on the persisted count baseline |
| Short-interest percentile/change | short % of float over several settlements | yes — `get_short_interest_massive:485` (multi-settlement, newest-first); `get_short_interest_yfinance:37` | percentile of current short % of float vs the settlement series already returned |
| Extreme/crowding with a stated scale | crowd ratio history | yes — `compute_social_scores:273` + `_baseline_file:265` | percentile of `crowd_ratio` ratio vs the ticker's own persisted baseline (replaces the fixed 40/60 constant) |
| Sentiment × Price Confirmation quadrant `Sign(dSentiment) × Sign(abnormal return)` | dSentiment + market-adjusted return | sentiment: `daily_sentiment_sma:501` innovation / `_sentiment_factor_read:1420`; benchmark closes: `_ohlcv`/`get_relative_strength`/`_sentiment_factor_read` (closes passed in) | `sign(innovation) × sign(name_ret − bench_ret)` over the last session → {confirm-up, confirm-down, diverge-up, diverge-down}; no producer exists today. **[CORRECTED 2026-09-26: produced now — `sentiment_score.confirmation_quadrant:342` (four labels) + `analysis_tools._sentiment_price_read:6712` (abnormal return), see §0.3]** |

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
4. **`NA ≠ 0`** (master rule 1): the four holes reduce the available weight. **[CORRECTED 2026-09-26: three holes — see §0.1]**
5. **Its own band table**, advisory, feeding nothing (master rule 2).
6. **This engine never sizes.** `sentiment_factor_scale:570`'s 0.8/1.0/1.2
   multiplier is a *sizing* output and stays where it is; the score is
   diagnostic. If the owner later wants the score to size, that is a new
   decision, not a consequence of this document.
7. **No news number crosses the boundary.** The couplings in
   [`NewsScore.md`](NewsScore.md) §0.3 are the constraint; this engine reads the
   tone and positioning pipeline, not `news_relevance.score_news_article:56`.

### 5.1 The scale hazard this engine inherits

The news-sentiment route has **two scales behind one name**: EODHD/Alpha Vantage
deliver −1..1, GDELT delivers **−100..100** (`gdelt.get_news_sentiment_gdelt:317`,
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
   weighted mean of what remains; with nothing available, `None`. **[CORRECTED 2026-09-26: three holes — see §0.1]**
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

## 8. The owner's formula library (`Strategies/scores/sentiment_score.md`, 2026-09-26)

**What it is: 2,913 lines, 156 numbered sections, 163 headings** (`grep -c
'^#\{1,3\} '` = 163; the 156 numbered `# N.` sections plus the seven `### Layer
N` / closing sub-headings under §155). **251 display-math blocks**, counted as
`grep -cE '^\$\$[[:space:]]*$'` = 502 delimiters divided by two; **31 carry
`\boxed`**, the library's own headline formulas. Inline notation is not counted
and would raise the number; the section-by-section counts below use the display
blocks only.

**Its relationship to `../ScoreWeight/news_sentiment.md` is supersession, not
duplication.** The older spec is 334 lines, 14 headings, and carries two things
only: the ten-category weight table this document quotes as §0.1, and the
`Sentiment × Price Confirmation` rule quoted as §0.3. The new library keeps both
conclusions and adds the formulas underneath them — it is about seven times
longer and names roughly an order of magnitude more quantities. **It supplies no
weight vector**, so §0.1's ten weights remain the owner's, unchanged, and §0.2's
evidence still governs their sign.

**Its relationship to the component inventory is the headline finding of this
section.** §1's ledger declares **17 components over the ten categories**
(`sentiment_score.COMPONENTS`, `sentiment_score.py:193-269`). The library's §155
six-layer architecture names ~35 quantities on its own, and the 156 sections
specify 251 formulas. **The built engine is a small, deliberate slice of a very
large library**, and the counts below make the size of that slice explicit: 33 of
156 sections are built, 22 are partial, 7 exist elsewhere under another shape,
93 have no producer, and 1 is a diagram. Every row cites a `path::symbol` or
`path:LINE` that was read while writing this section; a row that says ABSENT has
no producer in the five modules of the sentiment path (`sentiment_score.py`,
`sentiment.py`, `sentiment_research.py`, `text_factors.py`,
`analysis_tools.py`).

The engine's own rules bound the reading: every component is aligned so **100 =
favourable** (`sentiment_score.align_components:423` → `score_engine.align:69`),
each quantity is measured once and owned by one engine (master §2.1), and the
composite is advisory. Those three rules are the comparison points for §8.4.

### 8.1 The library's sections against the engine

Formula count = display-math blocks (`$$…$$`) in that section. Status legend:
**built** = a producer computes the quantity; **PARTIAL** = a producer computes
part of it; **elsewhere** = the same quantity is produced under a different shape
or name; **ABSENT** = no producer in the repo; **n/a** = not a formula.

| § | Library section | Fmls | Status (producer read) |
| --: | --- | --: | --- |
| 1 | SentimentScore mathematical architecture | 0 | n/a — a data-flow diagram; the engine mirrors its level→momentum→normalisation spine (`sentiment_score.py:180,271`), but its Layer 1 (raw NLP) has no code |
| 2 | Basic polarity | 1 | built — `sentiment.score_from_counts:219` (`(bull−bear)/labeled` ≡ `(P−N)/(P+N)`); counts in `text_factors.lm_tone:121` |
| 3 | Positive intensity | 1 | ABSENT — nearest honest producer `text_factors.lm_tone:121` (a positive count, no `P/(P+N)`) |
| 4 | Negative intensity | 2 | ABSENT — nearest honest producer `text_factors.lm_tone:121` (negative count only) |
| 5 | Net sentiment | 2 | built — `sentiment.score_from_counts:219` |
| 6 | Weighted lexical sentiment | 1 | ABSENT — no per-word lexicon strength; `text_factors.lm_tone:121` weights every hit equally |
| 7 | TF-IDF-weighted sentiment | 2 | ABSENT — no TF-IDF anywhere in the five modules |
| 8 | Financial-domain dictionary score | 1 | built (variant) — `text_factors.lm_tone:121` over the LM seed lists (`DICTIONARY_VERSION:41`); denominator is `/words`, not `/(P+N)` |
| 9 | Financial phrase scoring | 2 | ABSENT — no phrase lexicon; `text_factors.lm_tone:121` is unigram-only |
| 10 | Negation adjustment | 2 | ABSENT — no negation pass in `text_factors.py` |
| 11 | Negation-window formula | 2 | ABSENT |
| 12 | Intensifier adjustment | 1 | ABSENT |
| 13 | Diminisher adjustment | 1 | ABSENT |
| 14 | Contrast adjustment | 2 | ABSENT |
| 15 | Clause-level sentiment | 2 | ABSENT |
| 16 | Sentence-level sentiment | 1 | ABSENT — `text_factors.readability:170` counts sentences, but scores none |
| 17 | Paragraph-level sentiment | 1 | ABSENT |
| 18 | Headline sentiment | 1 | ABSENT — the headline is used only as a dedupe key (`sentiment._normalise_headline:833`) |
| 19 | Body sentiment | 2 | ABSENT |
| 20 | Headline/body divergence | 1 | elsewhere — `text_factors.divergence:198` computes a cross-document `tone_gap`, not headline-vs-body |
| 21 | Title-weighted sentiment | 2 | ABSENT |
| 22 | Transformer probability sentiment | 3 | ABSENT — the polarity is a vendor/model number (`sentiment._article_polarity:629`); no `P+,P0,P−` |
| 23 | Expected sentiment | 2 | ABSENT — duplicate of §22 (see §8.3) |
| 24 | Sentiment confidence | 4 | ABSENT — no entropy/softmax confidence producer |
| 25 | Sentiment uncertainty | 2 | ABSENT |
| 26 | Sentiment variance | 4 | elsewhere — `sentiment.sentiment_dispersion:400` (weighted population std of polarity) |
| 27 | Sentiment magnitude | 1 | ABSENT |
| 28 | Expected sentiment magnitude | 1 | ABSENT |
| 29 | Conviction | 2 | ABSENT |
| 30 | Subjectivity | 3 | ABSENT — no subjectivity/objectivity input in the pipeline |
| 31 | Sentiment reliability | 1 | ABSENT |
| 32 | Entity sentiment | 1 | built — `sentiment._article_polarity:629` selects the per-ticker row from `ticker_sentiment` |
| 33 | Aspect sentiment | 8 | ABSENT — no aspect taxonomy or aspect scorer |
| 34 | Aspect sentiment dispersion | 1 | ABSENT |
| 35 | Source-weighted sentiment | 1 | PARTIAL — `sentiment.aggregate_weighted_sentiment:845` weights by `relevance/100 × official_boost`, an unsigned proxy, not a source-reliability `Q_j` (`_weighted_basis:599`) |
| 36 | Author-weighted sentiment | 1 | ABSENT — no per-author reliability |
| 37 | Account/source independence | 2 | ABSENT — no `1/N_source` weight |
| 38 | Duplicate-adjusted sentiment | 2 | PARTIAL — `aggregate_weighted_sentiment:626` **drops** syndicated duplicates (`_normalise_headline:614`) rather than weighting by `1−D_i` |
| 39 | Time decay | 2 | built — `sentiment.decayed_weight:194` (`2^{−age/h}`) |
| 40 | Exponentially weighted sentiment | 2 | PARTIAL — `sentiment.weighted_rolling_sentiment:968` uses `exp(linspace)` weights, not `α=2/(N+1)` |
| 41 | Half-life-based EWMA | 1 | PARTIAL — `sentiment.decayed_weight:194` is the `2^{−t/h}` form, not `α=1−e^{−ln2/h}` |
| 42 | Exponentially weighted individual messages | 2 | built — `sentiment.weighted_sentiment:109` (decay × credibility per message) [CORRECTED 2026-09-26: **the named helper was deleted** as a dead seam (SENT-14; `sentiment.py:18-22`), so this row's producer no longer exists. The nearest surviving producer of a per-message decay × credibility weight is `sentiment.decayed_weight:194` inside `aggregate_weighted_sentiment`'s weight loop (`sentiment.py:935`, `official_boost` supplying the credibility half); the row's `built` status now rests on that pair, not on `weighted_sentiment`.] |
| 43 | Sentiment volume | 1 | built — the per-day `n` from `sentiment.aggregate_daily_sentiment:667`, carried through `daily_sentiment_sma:511` |
| 44 | Sentiment-bearing volume | 1 | ABSENT — `n` counts all scored articles, not `P++P−>threshold` |
| 45 | Sentiment volume z-score | 1 | ABSENT — only the ratio `mention_volume:43`; no volume z |
| 46 | Sentiment buzz | 1 | built — `sentiment.mention_volume:171` (recent/baseline ratio) |
| 47 | Relative sentiment buzz | 1 | ABSENT — no universe denominator |
| 48 | Abnormal sentiment volume | 1 | ABSENT — duplicate of §45 (see §8.3) |
| 49 | Positive volume | 1 | PARTIAL — `sentiment.compute_social_scores:488` bullish count (social only) |
| 50 | Negative volume | 1 | PARTIAL — `sentiment.compute_social_scores:488` bearish count (social only) |
| 51 | Sentiment breadth | 1 | built — `sentiment.score_from_counts:219`; `crowd_ratio:163` `net_share` |
| 52 | Weighted breadth | 1 | ABSENT — no weighted positive/negative sums |
| 53 | Positive sentiment intensity | 1 | ABSENT |
| 54 | Negative sentiment intensity | 1 | ABSENT |
| 55 | Sentiment pressure | 1 | ABSENT |
| 56 | Positive/negative sentiment ratio | 2 | ABSENT — no PNR producer |
| 57 | Sentiment imbalance | 1 | built — `sentiment.score_from_counts:219` (the ε-free form) |
| 58 | Sentiment dispersion | 1 | built — `sentiment.sentiment_dispersion:400` |
| 59 | Sentiment entropy | 2 | ABSENT — no entropy producer in the five modules |
| 60 | Sentiment consensus | 1 | PARTIAL — `sentiment.sentiment_dispersion:400` `agreement` / `consensus_overlap:55` (modal share, not `1−H*`) |
| 61 | Source dispersion | 1 | ABSENT |
| 62 | Source consensus | 1 | ABSENT |
| 63 | Sentiment velocity | 1 | built (variant) — `sentiment.sentiment_velocity:37` (OLS slope/day is canonical per §7 Q4; the library is the 1-step delta) |
| 64 | Percentage sentiment velocity | 1 | ABSENT |
| 65 | Sentiment acceleration | 2 | ABSENT — no second difference; nearest producer `sentiment_velocity:25` |
| 66 | Sentiment jerk | 2 | ABSENT |
| 67 | Sentiment momentum | 1 | PARTIAL — `sentiment.daily_sentiment_sma:730` `innovation` (7-day, not `S_t−S_{t−k}`) |
| 68 | Normalized sentiment momentum | 1 | ABSENT |
| 69 | Sentiment trend | 2 | PARTIAL — `sentiment_velocity:25` is the slope; no intercept or fit beyond it |
| 70 | Rolling sentiment slope | 1 | built — `sentiment.sentiment_velocity:37` (`Cov(t,S)/Var(t)` form) |
| 71 | Sentiment regression trend strength | 2 | ABSENT — no `R²` producer |
| 72 | Sentiment persistence | 1 | ABSENT — and mislabelled (see §8.3) |
| 73 | Negative persistence | 1 | ABSENT |
| 74 | Positive persistence | 1 | ABSENT |
| 75 | Sentiment half-life | 2 | ABSENT — no AR(1) φ estimate |
| 76 | Sentiment mean reversion | 2 | elsewhere — `sentiment.surprise_velocity:201` is the standardized form `(S−mean)/std` |
| 77 | Sentiment z-score | 1 | built — `sentiment.surprise_velocity:201` |
| 78 | Rolling z-score | 1 | built — `sentiment.surprise_velocity:201` (rolling baseline window) |
| 79 | Robust sentiment z-score | 1 | ABSENT — no MAD |
| 80 | Percentile sentiment | 2 | ABSENT — the crowd bands are fixed constants (`sentiment.py:159-160`) |
| 81 | Cross-sectional sentiment rank | 2 | built — `sentiment_research._bucket:566`; `sector_neutral_z:239` |
| 82 | Cross-sectional sentiment z-score | 1 | built — `sentiment_research.sector_neutral_z:346` |
| 83 | Sector-relative sentiment | 1 | built — `sentiment_research.sector_neutral_z:346` |
| 84 | Industry-relative sentiment | 1 | PARTIAL — `sector_neutral_z:239` is sector granularity only; no industry map |
| 85 | Market-relative sentiment | 1 | built — `sentiment_research.residualize_sentiment:383` (log-mcap + sector dummies); universe fallback in `sector_neutral_z:239` |
| 86 | Sentiment beta | 2 | ABSENT — no regression of sentiment on a market sentiment index |
| 87 | Idiosyncratic sentiment | 1 | PARTIAL — `residualize_sentiment:276` residualizes on mcap+sector, not on a sentiment β |
| 88 | Sentiment-price correlation | 1 | built — `sentiment_research.sentiment_lead_lag:172` |
| 89 | Sentiment predictive beta | 2 | built — `sentiment_research.multi_horizon_sentiment_regression:264` (Newey-West HAC) |
| 90 | Sentiment-return information coefficient | 2 | built — `sentiment_research.rolling_information_coefficient:444`; `ic_term_structure:394` |
| 91 | IC information ratio | 1 | built — `sentiment_research.ic_term_structure:501` (`ic_ir`) |
| 92 | Sentiment volatility | 1 | elsewhere — `sentiment.sentiment_dispersion:400` is cross-item std, not the time-series std |
| 93 | EWMA sentiment volatility | 1 | ABSENT |
| 94 | Sentiment shock | 1 | elsewhere — `sentiment.daily_sentiment_sma:730` `innovation` (unnormalised) |
| 95 | Abnormal sentiment shock | 1 | built — `sentiment.surprise_velocity:201` |
| 96 | Sentiment regime | 1 | ABSENT — no regime classifier on the sentiment surface |
| 97 | Sentiment reversal | 2 | ABSENT |
| 98 | Sentiment divergence from price | 2 | PARTIAL — `sentiment_score.confirmation_quadrant:342` is the sign quadrant, not `Z_S−Z_R` |
| 99 | Sentiment-price confirmation | 2 | built — `sentiment_score.confirmation_quadrant:342` |
| 100 | Sentiment-price disagreement | 2 | built — `confirmation_quadrant:330` (the two `diverge-*` cells) |
| 101 | Sentiment elasticity | 2 | ABSENT |
| 102 | Sentiment-to-volatility relationship | 2 | ABSENT |
| 103 | Sentiment asymmetry | 4 | ABSENT |
| 104 | Negative sentiment amplification | 1 | ABSENT |
| 105 | Sentiment saturation | 1 | ABSENT — `score_engine.align:69` is a clamped linear ramp, not tanh |
| 106 | Sentiment threshold | 2 | PARTIAL — `sentiment_score.SENTIMENT_BANDS:274` labels, not an `I(S>θ)` gate |
| 107 | Dynamic threshold | 1 | ABSENT |
| 108 | Sentiment surprise | 2 | built — `sentiment.surprise_velocity:201` |
| 109 | Sentiment change relative to expectation | 1 | ABSENT |
| 110 | Sentiment acceleration × volume | 1 | ABSENT — no interaction term; sign contradicts the code (see §8.4) |
| 111 | Sentiment momentum × breadth | 1 | ABSENT |
| 112 | Sentiment conviction × volume | 1 | ABSENT — no interaction term; sign contradicts the code (see §8.4) |
| 113 | Sentiment intensity × dispersion | 1 | ABSENT |
| 114 | Effective sentiment sample size | 1 | ABSENT — no `N_eff`; `sentiment_dispersion:209` carries an item count, not Kish's |
| 115 | Sentiment coverage | 1 | PARTIAL — `score_engine.coverage_floor:53` / `combine:134` coverage is a **weight** fraction, not `N_eff/N_target` |
| 116 | Confidence adjusted sentiment | 1 | ABSENT |
| 117 | Bayesian sentiment | 4 | ABSENT |
| 118 | Bayesian shrinkage | 2 | ABSENT |
| 119 | Kalman-filter sentiment | 3 | ABSENT |
| 120 | Hidden Markov sentiment regime | 2 | ABSENT |
| 121 | Sentiment transition probability | 2 | ABSENT |
| 122 | Sentiment persistence coefficient | 2 | ABSENT |
| 123 | Sentiment mean-reversion speed | 2 | ABSENT |
| 124 | Sentiment half-life | 1 | ABSENT — duplicate of §75 (see §8.3) |
| 125 | Sentiment autocorrelation | 2 | ABSENT |
| 126 | Sentiment cross-correlation with returns | 1 | built — `sentiment_research.sentiment_lead_lag:172` (≡ §88/§90, see §8.3) |
| 127 | Sentiment lead/lag | 1 | built — `sentiment_research.sentiment_lead_lag:172` (`lag_days` over `±max_lags`) |
| 128 | Sentiment event study | 2 | ABSENT — no CAR producer |
| 129 | Sentiment-adjusted expected return | 2 | PARTIAL — `multi_horizon_sentiment_regression:157` gives the β, not the fitted `E[R]` |
| 130 | Sentiment residual | 1 | built — `sentiment_research.residualize_sentiment:383` |
| 131 | Market sentiment index | 3 | PARTIAL — `sentiment_research._cross_section:336` builds per-date cross-sections; no explicit MSI |
| 132 | Equal-weighted market sentiment | 1 | PARTIAL — as §131; no equal-weight mean producer |
| 133 | Sentiment breadth index | 1 | elsewhere — `sentiment.score_from_counts:219` (different denominator) |
| 134 | Sector sentiment | 1 | built — `sentiment_research.sector_neutral_z:346` (sector means) |
| 135 | Sector-relative sentiment | 1 | built — `sentiment_research.sector_neutral_z:346` (≡ §83, see §8.3) |
| 136 | Sentiment dispersion across stocks | 1 | PARTIAL — `sentiment_research._cross_section:336` gives the cross-section; no explicit std |
| 137 | Sentiment concentration | 1 | ABSENT — no HHI |
| 138 | Gini coefficient of sentiment participation | 1 | ABSENT |
| 139 | Source breadth | 1 | ABSENT — no unique/total source ratio |
| 140 | Sentiment independence | 2 | ABSENT |
| 141 | Complete item-level sentiment formula | 1 | ABSENT — the six-factor product needs confidence, entity relevance, source reliability and independence, of which only time decay exists |
| 142 | Complete aggregate sentiment formula | 1 | PARTIAL — `sentiment.aggregate_weighted_sentiment:845` is the weighted mean, with none of the four non-decay factors |
| 143 | Multi-horizon sentiment | 7 | PARTIAL — `sentiment_research.multi_horizon_sentiment_regression:264` for research; `daily_sentiment_sma:511` for the 7-day horizon |
| 144 | Short/medium/long sentiment spread | 2 | ABSENT |
| 145 | Sentiment regime transition | 2 | ABSENT |
| 146 | Sentiment shock persistence | 1 | ABSENT |
| 147 | Sentiment decay estimate | 2 | ABSENT |
| 148 | Sentiment score normalization | 2 | elsewhere — `score_engine.align:69` maps each component by its own ramp; the composite is a weighted mean (`combine:134`), not `50(1+S)` |
| 149 | Z-score-to-100 transformation | 2 | ABSENT — no normal CDF |
| 150 | Logistic z-score transformation | 1 | ABSENT |
| 151 | Tanh normalization | 1 | ABSENT — no tanh in the five modules |
| 152 | Robust final score | 2 | ABSENT — needs the robust z of §79 |
| 153 | Sentiment confidence | 3 | ABSENT |
| 154 | Sentiment coverage | 1 | built (variant) — `sentiment_score.COMPOSITE_MIN_COVERAGE:296` + `score_engine.coverage_floor:53` enforce a floor; the `N_eff` form is absent |
| 155 | Recommended production SentimentScore | 0 | PARTIAL — the six-layer target; Layers 1-2 mostly absent, 3-5 partial, Layer 6 built |
| 156 | The formula I'd actually implement first | 9 | PARTIAL — the v1 pipeline's weighted mean, slope, breadth and dispersion exist; its `N_eff` and tanh normalisation do not |

**Counts: 33 built, 22 PARTIAL, 7 elsewhere, 93 ABSENT, 1 n/a.**

### 8.2 Not built — the backlog the library names

The 93 ABSENT sections are not 93 independent items; they cluster into **five
layers, four of which have no code at all**.

1. **Raw NLP (Layer 1) — the largest cluster.** §3, §4, §6, §7, §9-§19, §21-§31,
   §33, §34, §36, §37. The engine consumes a vendor/model polarity
   (`sentiment._article_polarity:629`) and never constructs one: no negation
   window, no intensifier/diminisher, no clause/sentence/paragraph split, no
   aspect taxonomy, no subjectivity, uncertainty, entropy or conviction. The one
   producer that *does* build polarity deterministically is
   `text_factors.lm_tone:121`, which already holds the finance word lists and the
   counts — **the smallest honest next producer is a negation flag over its
   existing token list plus a `P/(P+N)` intensity beside the count**. The
   library's own §156 v1 asks for confidence, entity relevance, source
   reliability, independence and time decay as item weights; the code has one
   (`decayed_weight:91`) plus an unsigned relevance proxy (`_weighted_basis:599`
   states it is "NOT a model probability").
2. **Dynamics beyond the slope.** §65, §66, §68, §71-§75, §97, §112(part),
   §122-§125, §146, §147. `sentiment.sentiment_velocity:37` is the only wired
   dynamics producer; §7 Q4 makes its OLS slope the canonical direction, so the
   missing pieces are the **three-point second difference** (§65/§66) and an
   **AR(1) φ** (§75/§122-§124) — both one short function over the series
   `daily_sentiment_sma:511` already returns.
3. **Volume, attention and participation.** §44, §45, §47, §48, §52-§56, §59-§62,
   §110, §112, §114, §137-§140. `sentiment.mention_volume:171` is the only volume
   producer; there is **no effective sample size (`N_eff`, §114)** and no
   HHI/Gini/concentration measure. The code's own comment explains why the
   attention leg is a separate row (`sentiment_score.py:236`), so §110/§112's
   volume-amplifiers cannot be built on this surface without deciding the sign
   first (§8.4 point 2).
4. **Relative normalisation and market relationship.** §79, §80, §86, §87, §101-§104,
   §128-§132, §136, §144, §145. `sentiment_research` already produces sector and
   universe z-scores (`sector_neutral_z:239`) and a residual
   (`residualize_sentiment:276`); absent are the **robust (MAD) z**, the
   **percentile**, a **sentiment β to a market sentiment index**, the
   **asymmetry/amplification split** (§103/§104) and an **event study** (§128).
5. **Uncertainty models and the final-output map.** §93, §105, §107, §109, §116-§121,
   §149-§153. There is **no entropy, Bayesian, Kalman or HMM producer** anywhere in
   the five modules, and the final map is a **clamped linear ramp per component**
   (`score_engine.align:69`) with a weighted-mean composite (`combine:134`) — no
   Φ, logistic or tanh transform (§149-§152). `Confidence` and `Coverage` are
   separate first-class outputs in the library (§153/§154); in code `coverage` is
   a **weight fraction**, a different unit from the library's `N_eff/N_target`.

Nothing here changes the four holes §1 already records (20-day momentum,
acceleration, per-source breadth, institutional sentiment). **[CORRECTED
2026-09-26: three holes — §7 Q4 closed the 20-day momentum hole (the slope
`sentiment_velocity:25` is canonical).]** The library adds a
fifth class of hole — **the whole raw-NLP layer** — which §1 did not name because
the engine's design intentionally delegates polarity to the vendor/model feed.

### 8.3 Library-internal defects

Verified by reading the formulas as printed; each is a defect *inside the
library*, independent of the code.

1. **§22 ≡ §23.** Both define `S = P+ − P−`, both boxed, under "Transformer
   probability sentiment" and "Expected sentiment" — one formula, two names.
2. **§45 ≡ §48.** `Z_V = (V_t − μ_V)/σ_V` and `ASV = (V_t − E[V_t])/σ_V` are the
   identical statistic; `μ_V` is `E[V_t]`. Two names, one formula.
3. **§72 ≡ §74, and §72 is mislabelled.** §72 "Sentiment persistence" is defined
   `#{S_{t−k}>0}/k` — the *positive* count share — which is exactly §74 "Positive
   persistence". The generic title is wrong; the formula is §74's.
4. **§69 ≡ §70.** `Trend = β` from `S_t = α + βt + ε` and the rolling
   `β_t = Cov(t,S)/Var(t)` are the same ordinary-least-squares slope.
5. **§75 ≡ §124.** Both print `HalfLife = −ln2/ln|φ|` from the same AR(1). §41
   (`α = 1 − e^{−ln2/h}`) and §147 (`HalfLife = ln2/λ`) are two further
   half-life routes on different inputs — four sections, one quantity.
6. **§83 ≡ §135.** With §134 defining `SectorSentiment_s = Σ w_i S_i`,
   §135's `S_i − SectorSentiment` is §83's `S_i − S̄_sector`. Sector-relative
   sentiment is specified twice.
7. **§88 ≡ §90 ≡ §126.** `Corr(S_t, R_{t+k})` appears as "sentiment-price
   correlation", "information coefficient" and "cross-correlation with returns";
   §89 is its regression twin. Three names for one correlation.
8. **§39 ≡ §42.** `D(t) = 2^{−t/h}` and `w_i = 2^{−Age_i/h}` are the same decay on
   the time axis and the item axis.
9. **The `1 − H*` cluster: §24, §29, §60, §153.** `Confidence = 1 − H*` (§24),
   `Conviction = 1 − H/H_max` (§29), `Consensus = 1 − H*` (§60) and
   `C_consensus = 1 − H*` (§153) are one number under four names, because
   `H* = H/ln3 = H/H_max`. §31 then multiplies that same `Confidence` into
   `Reliability`.
10. **§100 is a dead formula against §99's first form.** §99's discrete
    `Confirmation = Sign(S) × Sign(R)` is always `±1`, so §100's
    `Disagreement = 1 − |Confirmation|` is **identically 0**. §100 is only
    meaningful against §99's *second* (tanh) form; as printed the two sections
    contradict.
11. **§97 mislabels a signed change as a magnitude.** For the bull→bear reversal
    the section defines, `ReversalMagnitude = S_t − S_{t−1}` is **negative**; a
    magnitude would be `S_{t−1} − S_t` or its absolute value.
12. **§72/§73/§74 index the count set incoherently.** `#{S_{t−k} > 0}` keeps `k`
    as *both* the window length and the index of the single observation `t−k`,
    so the set has at most one element; the index should vary across the window.
13. **Two definitions inside one section, undecided.** §24 prints
    `C = max(P+, P0, P−)` and then "a better measure is entropy" → `1 − H*`; §25
    prints `U = 1 − C` and `U = H*`. Each section carries two different
    definitions without choosing.
14. **§156 drifts from the sections it summarises.** Its boxed `Breadth_t`
    carries an `ε` that §51 omits, and its `Dispersion_t = Std_w(S_i)` is the
    shorthand of §58's full weighted population std. Summary drift, not a new
    formula.

### 8.4 Contradictions between the library and the code

Comparison points: the engine's alignment rule (**100 = favourable**, every
component; raw value printed with units and sign beside its aligned contribution)
and the two couplings recorded in [`NewsScore.md`](NewsScore.md) §0.3.

1. **Direction — levels the library calls bullish that the engine refuses to
   score as such.** The engine aligns every component to 100 = favourable
   (`sentiment_score.align_components:423`; `score_engine.align:69`; the `RAMPS`
   table at `sentiment_score.py:155`). The library presents several *levels* as
   bullish-positive with no alignment rule: **§77** ("this is a core
   institutional-style calculation", i.e. a high z is strong), **§89/§90**
   (IC/β as evidence of predictive information) and **§131/§132** (a market
   sentiment index). §0.2 point 2 (Baker-Wurgler) makes the cross-sectional sign
   **contrarian** and §0.3 says a high `SentimentScore` is **not** a buy; the code
   reads `rank_ic` only as a **sign gate** — `sentiment_research.sentiment_factor_scale:677`
   sets `direction = 1.0 if (rank_ic > 0) == (innovation > 0) else −1.0`, never a
   0-100 direction. Mapping §77, §90 or §131 straight onto a 0-100 with
   higher = favourable **inverts** the engine's rule precisely on the
   hard-to-value, hard-to-arbitrage names §0.2 names.
2. **Volume sign — the sharpest contradiction.** §110
   (`Acceleration × Z_Volume`) and §112 (`Conviction × Z_Volume`) use volume as a
   **positive amplifier** of the directional signal, and §43/§46/§47 leave it
   unsigned. The engine declares the attention leg `mention_heat` **lower_better**
   (`sentiment_score.py:236`, "ATTENTION, not tone"), on the neglected-firm sign
   [`NewsScore.md`](NewsScore.md) §0.4 point 2 records. A literal implementation
   of §110 or §112 would score high attention as favourable — the opposite of the
   component the engine wires for volume.
3. **Dispersion sign — the library gives no direction, the engine gives a
   negative one.** §58 ("investors disagree") and §136 ("stock-specific rather
   than broad market") present dispersion as a neutral statistic. The engine
   scores `dispersion` **lower_better** (`sentiment_score.py:240`) and
   `dispersion_agreement` higher_better, on §0.2 point 4
   (Diether-Malloy-Scherbina). The engine's direction is therefore an **addition
   the library does not state** — a reader must not read §58 as an aligned 0-100.
4. **Confirmation shape — 2 cells vs 4.** §99's `Sign(S) × Sign(R)` is
   two-valued, and §100's discrete form is identically 0 (defect 8.3-10). The
   engine's `sentiment_score.confirmation_quadrant:342` returns **four** distinct
   labels keyed on the **price** direction (`CONFIRMATION_QUADRANTS:282`:
   `confirm-up`, `diverge-up`, `confirm-down`, `diverge-down`). The owner's two
   cells in §0.3 — *positive sentiment with rising price confirms; with falling
   price diverges* — need the price direction the library's product discards.
   The library cannot express the engine's interface.
5. **Normalisation — one tone to one score vs a per-component ramp.** §148 maps a
   single signed tone with `Score = 50(1+S)`; §156's v1 then applies
   `50[1 + tanh(Z/k)]`. The engine's map is a **clamped linear ramp per
   component** (`score_engine.align:69`, edges from the `RAMPS` table) combined by
   weighted mean over categories (`combine:134`); **no library formula is the
   composite**, and §149-§152's transforms have no producer.
6. **Sentiment `Confidence`/`SourceReliability` must not be the shared
   `news_relevance` number.** §35 (`Q_j`), §36 (`A_i`), §141 and §142 all require
   a confidence/reliability term. The code has exactly one weight input and
   names what it is not — `sentiment._weighted_basis:818`: "relevance is an
   unsigned proxy for confidence, NOT a model probability". [`NewsScore.md`](NewsScore.md)
   §0.3 already records that this same relevance **is** the sentiment
   aggregation's weight and that one leaf serves both surfaces. Building §35 or
   §141 by wiring `news_relevance.score_news_article:56` into both engines would
   create exactly the shared number the master's anti-double-counting rule
   (§2.1) forbids: one quantity, two owners. The library's Confidence leg needs a
   **different** producer, not the news relevance score.
7. **Unit — the library assumes −1..1 with no scale declaration.** §2, §5 and
   §148 all take the tone as bounded in −1..1. The code's route carries a
   **−100..100 GDELT leg** beside the −1..1 EODHD/AV ones — the defect §5.1
   records — which is why the engine pins the scale first
   (`sentiment_score.SCALE_TABLE:56`, `normalise_sentiment:80`, and the
   two-source **refusal** in `normalise_components:394`). §148's `50(1+S)` on a
   GDELT value yields ±5050. The library never names the unit, so any formula
   taken from it is unbuildable on the raw aggregate until §5.1's unit pin is
   honoured.

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
