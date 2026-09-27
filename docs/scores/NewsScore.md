# NewsScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md), [`MarketScore.md`](MarketScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the news engine only.** It designs `NewsScore` — *"what new information
has arrived, and how materially could it affect the company?"* — from the owner's
nine categories in [`../ScoreWeight/news_sentiment.md`](../ScoreWeight/news_sentiment.md).

**The boundary that makes this engine worth having.** The owner's illustration is
the test:

```
NVIDIA announces a major new AI contract
        ↓  NewsScore ↑↑          (information arrived)
Analysts become more positive
        ↓  SentimentScore ↑      (the market's interpretation moved)
Stock +8%, volume 3× normal
        ↓  TechnicalScore ↑      (price and participation confirmed)
```

**Three separate observations, not three votes for the same thing.** If
`NewsScore` reads the sentiment numbers, or `SentimentScore` reads the relevance
numbers, the set collapses into one signal with three labels. The couplings that
already exist are in §0.3.

Status: **built (2026-09-18); gate off by default.** `strategies/news_score.py` is the engine, `get_news_score` its leaf and `enable_news_score` its membership switch. It participates in the **research allocation only** - never in the decision composite (master rule 17). Five of its nine categories are still **ABSENT** and two more partial (§1): a partial engine that prints its coverage is the only honest form it can take. **Unmeasured** (vendor gate).

---

## 0. What this engine answers, and what it must not become

### 0.1 The owner's weight table

| Category | Weight | Status today |
| --- | --: | --- |
| News relevance / materiality | **20%** | **PARTIAL** — relevance is scored, **materiality is not** |
| News novelty | **15%** | **PARTIAL** — syndication dedupe exists, no novelty score [CORRECTED 2026-09-26: stale — `news_score.news_novelty` exists and is wired: `analysis_tools._news_components`'s `nov = news_novelty(articles, window=days)` feeds the engine's `novelty` component (`news_score.COMPONENTS`'s `novelty` row). See §1, §8.1 row 7 and §8.4.] |
| Fundamental impact | **20%** | **ABSENT** — no revenue- or margin-impact producer |
| Earnings / guidance news | **15%** | **PARTIAL** — surprise yes, guidance no [CORRECTED 2026-09-26: a guidance source now **exists** — `tradingagents/agents/utils/benzinga_tools.py::get_guidance_revisions:34` returns management's **forward revenue and EPS range** "with the prior range when the vendor carries one", bound in `news_tools()` at `tradingagents/agents/toolsets.py:411` behind `enable_benzinga_surface` (`default_config.py:1174`, **default off**; each Benzinga leaf returns a DISABLED sentinel while off). So the honest reason is now "source gated off / not read by NewsScore", not "no guidance source".] |
| Corporate events | **10%** | **PARTIAL** — SEC form typing only |
| Regulatory / legal | **5%** | **PARTIAL** — a litigious word count |
| Analyst / rating changes | **5%** | **PARTIAL** — the revision index is flag-gated and **bound to the fundamentals toolset** |
| Macro / industry | **5%** | **PARTIAL** — macro context yes, industry shock no |
| News persistence | **5%** | **PARTIAL** — decay maths exists behind flags, unwired |

**4 of 9 categories have a computed input; the other five do not**, and the
largest single weight (20%, fundamental impact) has **no producer at all**.

### 0.2 Relevance is not materiality — quoted from the code

`news_relevance.score_news_article:56`'s docstring (`news_relevance.py:56`) reads
*"Deterministic relevance score (0-100) + <=5 explainable reasons"*, returning
`{"score": round(score, 1), "reasons": reasons[:5]}` (`:93`). Every point is a
lexical or membership flag: ticker-in-title +55, company-name +45 (with a +26
ambiguous case), official host +8, a macro term −12. It measures **whether the
article is about this ticker from a credible source**, not **how much it moves
the fundamental**. There is no magnitude, dollar value, percentage move or
event-severity term.

Consequence for the design: the owner's 20-point category is **half
unimplemented**, and today a reader sees a high relevance score for a trivial
press mention and would be wrong to read it as material. The report must
therefore print the two **separately named**, and materiality must stay `NA`
until §4's producer exists — never be approximated by relevance.

### 0.3 The couplings to `SentimentScore` — the separation is a naming rule

The owner requires that `NewsScore` not become a duplicate of `SentimentScore`.
It is **not** satisfied by construction; four couplings already exist:

| Coupling | Evidence |
| --- | --- |
| The news path's relevance **is** the sentiment aggregation's confidence weight | `strategies/sentiment.py:589 _weighted_basis` |
| One leaf serves both surfaces | `get_news_sentiment_series` is bound to `news_tools()` (`agents/toolsets.py:352`) **and** `market_tools()` (`:279`) |
| The sentiment analyst pre-fetches the news analyst's leaf | `agents/analysts/sentiment_analyst.py:88` |
| A bundled endpoint already merges the two feeds | `domain_bundles.get_sentiment_flow_feed:93` |

One producer feeding two readers is the repo's rule, not a violation of it — but
it means the separation must be **enforced by naming**: every component of this
engine states the producer it reads, and a component that would read a
`sentiment.py` number is either dropped or renamed. `NewsScore` reads the **news
pipeline** (`news_relevance`, `events`, `text_factors`, SEC form typing, the
analyst revision index); `SentimentScore` reads the **tone and positioning
pipeline**. Where they share a source (the article set itself), they must not
share a *number*.

### 0.4 What the evidence says — and why it changes the design

1. **Novelty has a known recipe and a known sign.** Tetlock's staleness measure
   is the **textual similarity of a story to the previous ten stories about the
   same firm**; returns respond *less* to stale news, and stale-news days
   *negatively predict* the following week's return (an overreaction that
   reverses). So novelty is not a nicety — it is the difference between an
   information event and an echo, and the engine already holds the primitives
   (article timestamps from every vendor, plus the headline normaliser
   `sentiment._normalise_headline:833` used for syndication dedupe).
2. **Coverage level is itself a factor.** Stocks with *less* media coverage have
   historically earned *higher* subsequent returns (the neglected-firm effect,
   strongest where information asymmetry is greatest). This means the **volume**
   of coverage is not a bullish input — the opposite of the intuition a "news
   score" invites. The engine's `mention_volume:43` (unwired) is a coverage
   measure, and its sign must be decided, not assumed.
3. **Management guidance changes carry incremental information and drift.**
   Guidance is currently **ABSENT** from the engine while being one of the
   better-documented news factors — which is why it is listed as a build item
   rather than a refinement. [CORRECTED 2026-09-26: a gated source exists — `benzinga_tools.get_guidance_revisions:34`, bound at `toolsets.py:411` behind `enable_benzinga_surface` (default off) — but it is not read by this engine, so the category is absent from the *score*, not from the tree.]
4. **Attention and sentiment are different signals with opposite short-horizon
   signs** (attention spikes → negative next-day returns; bullish tone →
   positive). That is a `SentimentScore` consequence (see that document), but it
   is also why this engine must not import a tone number to stand in for
   "how much attention this got".

---

## 1. Component inventory

Status vocabulary: SCORABLE / PARTIAL / ABSENT / UNWIRED.

| Component | Weight | Status | Producer (`module.function:line`) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| relevance & materiality | 20 | **PARTIAL** | `news_relevance.score_news_article:56` | `{"score", "reasons"}` | higher = more relevant | 0-100 floor-clamped | Scores relevance only; NO materiality term |
| → relevance (ticker/name/official) | — | SCORABLE | `news_relevance.score_news_article:56` | `score` | higher = more relevant | 0-100 | weights: code-title +55/snippet +34/url +18; name-title +45 (+26 amb)/snippet +28/+16; official +8; macro -12 |
| → materiality | — | **ABSENT** | — | — | — | — | no magnitude/size/impact input anywhere |
| novelty | 15 | **PARTIAL** | `sentiment._normalise_headline:833` + dedupe in `sentiment.aggregate_weighted_sentiment:845` | drops dupes; no novelty key | n/a | n/a (count of survivors) | syndication dedupe exists, no novelty score emitted; gated by `enable_weighted_sentiment_agg` (default False) [CORRECTED 2026-09-26: the gap cell is stale — `news_score.news_novelty` emits a novelty score (first-seen share over exact normalised keys) and it **is** wired, at `analysis_tools._news_components` (`nov = news_novelty(...)`) inside `_news_components`, with **no** sentiment gate; `enable_weighted_sentiment_agg` governs the separate `aggregate_weighted_sentiment` dedupe path, not this one.] |
| fundamental impact | 20 | **ABSENT** | — | — | — | — | no revenue/margin-impact producer |
| → revenue-impact estimate | — | ABSENT | — | — | — | — | grep `revenue_impact|impact_estimate` = 0 hits |
| → margin-impact estimate | — | ABSENT | — | — | — | — | grep `margin_impact` = 0 hits |
| earnings & guidance | 15 | **PARTIAL** | see sub-rows | — | — | — | surprise yes, guidance no |
| → earnings surprise | — | SCORABLE | `events.surprise_score:17` (surfaced by `analysis_tools.get_earnings_surprise:1671`, `get_earnings_event_read:535`; rows via `catalyst.last_earnings_surprise:77`) | return str `last_surprise/side/date` | higher = beat | signed ratio `(actual-estimate)/|estimate|` | — |
| → guidance change | — | **ABSENT** | — | — | — | — | no guidance field; `get_earnings_calendar:30` carries EPS estimate only [CORRECTED 2026-09-26: stale — a producer exists (`benzinga_tools.get_guidance_revisions:34`, forward revenue/EPS range **with the prior range**, bound at `toolsets.py:411`, `enable_benzinga_surface` default off); the engine still does not consume it, so the gap is `NA` with that reason, not "no guidance field".] |
| corporate events | 10 | **PARTIAL** | `sec_edgar.get_sec_filings:426` + `_FORM_LABELS:36` | form-type label | n/a (fact) | label only | only SEC form typing ("8-K (material event / M&A / guidance)"); rest is LLM prose |
| → M&A / partnership / contract / product | — | ABSENT | — | — | — | — | no classifier; prompt tells analyst not to over-read 8-K (`news_analyst.py:102`) |
| → dividend / buyback announcement | — | PARTIAL | `moomoo_extra_tools.get_dividends:157`, `get_corporate_actions:131`, `market_position_tools.get_share_buyback_authorization:49` | facts, not score | n/a | amounts/dates | remaining buyback authorization explicitly unavailable (`market_position_tools.py:112`) |
| → bankruptcy / distress | — | PARTIAL | `analysis_tools.get_analyst_verdict:1580` (Altman Z, Ohlson O, Zmijewski, trap-risk) | `altman_z/ohlson_o/zmijewski_x/trap_risk` | higher Z = safer (distress = Z low) | model scores | statement-driven, not news-driven |
| regulatory & legal | 5 | **PARTIAL** | `text_factors.lm_tone:121` (litigious count) | `litigious` | higher = more legal language | raw word count | no legal/regulatory event classifier; count only, no scale |
| → regulatory action | — | ABSENT | — | — | — | — | grep `regulatory_action` = 0 |
| analyst & rating changes | 5 | **PARTIAL** | `analyst_data_tools.get_analyst_ratings:10`; `analyst_revision_tools.get_analyst_revision_index:43` → `analyst_revisions.revision_ratio:79`/`revision_index:279` | rating trend + PT consensus; index ratio | index >0 = net upgrades | ratio (weighted up/down) | revision index flag-gated default False; bound to fundamentals NOT news |
| → price-target revision | — | **PARTIAL** | `analyst_revisions.estimate_change_index:176` | `index=None` + reason | — | — | always `unavailable` — engine holds no 3-4q estimate history |
| macro & industry | 5 | **PARTIAL** | `macro_data_tools.get_macro_indicators:9`; `analysis_tools.get_macro_regime_read:9486`, `get_credit_spread_read:4782`, `get_taylor_read:2866` | macro series / label | macro context | mixed (levels, bps, label) | no per-name macro-sensitivity or industry-shock producer |
| → industry shock | — | ABSENT | — | — | — | — | `get_market_breadth:98` = breadth, not industry shock |
| persistence | 5 | **PARTIAL** | `sentiment.decayed_weight:194`, `sentiment.aggregate_weighted_sentiment:845` (half-life), `sentiment.mention_volume:171` | decay factor / mention ratio | higher ratio = hotter | 0.5^(age/HL); ratio >=1 | `mention_volume`, `sentiment_velocity` have no callers [CORRECTED 2026-09-26: the "no callers" claim in this row's gap cell is stale — `mention_volume` is called at `analysis_tools._news_components`'s two `heat = mention_volume(...)` calls and `sentiment_velocity` (`vel = sentiment_velocity(...)`). The **decay** half is a mislabelled declaration: `news_score.COMPONENTS["persistence"].producer` cites `sentiment.decayed_weight:194` (`news_score.COMPONENTS`'s `persistence` producer declaration) but that half has no call site (`analysis_tools._news_components`'s NOTE comment ("the declaration also cites `sentiment.decayed_weight:194`. That half is NOT called here ... The citation's second half has no call site.")) — recorded as **D-9** in `IMPLEMENTATION_PLAN.md` §14.] |
| → news volume acceleration | — | UNWIRED | `sentiment.mention_volume:171` (also `sentiment_velocity:25`) | none | higher = accelerating | ratio | exported at `sentiment.py:825`; grep finds no caller [CORRECTED 2026-09-26: stale — `sentiment.mention_volume:171` **has callers**: `analysis_tools._news_components`'s sentiment-leaf `heat = mention_volume(...)` and the persistence leg's `heat = mention_volume(...)`, both fed from `daily_sentiment_sma`'s per-day `n`; `sentiment_velocity:25` is called (`vel = sentiment_velocity(...)`). What is still open is the *quantity*, not the wiring: the wired producer is the **level ratio** (recent/baseline mentions, inverted per owner Q9), **not** the owner's "news volume acceleration" (a first difference) — `NEWS-8`, `docs/scores/MASTER_PLAN.md:198`, open.] |
| → repeated-news decay | — | PARTIAL | `sentiment.decayed_weight:194` | weight | higher = fresher | half-life days (default 7.0) | used in the aggregation's weight loop (`sentiment.py:935`); `weighted_sentiment:109` was deleted (SENT-14) [CORRECTED 2026-09-26: the caller named here is gone — `sentiment.py:18-22` records the three dead seams deleted, not kept; `decayed_weight:194`'s surviving production reader is `aggregate_weighted_sentiment`'s per-message weight loop at `sentiment.py:935`. Article-level half-life only under flag.] |

---

## 2. Tool leaves (what the analysts can actually call)

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `news_data_tools.get_news_relevance_read:57` | `news_tools()` :350 | 0-100 relevance score + admitted + official + reasons | Yes (flag `enable_news_relevance` gates cache/degrade only, not the tool) |
| `news_data_tools.get_news:88` | news_tools :348 | vendor news string (title/source/summary/link) | Yes |
| `news_data_tools.get_news_sentiment:110` | news_tools :373 | daily -1..1 sentiment series + 7d SMA + innovation | Yes |
| `news_data_tools.get_global_news:126` | news_tools :353 | macro headline string | Yes |
| `news_data_tools.get_insider_transactions:152` | news_tools :364 | insider transaction report | Yes |
| `news_data_tools.get_massive_news:167` | news_tools :349 | per-article positive/negative/neutral + reasoning | Yes |
| `news_data_tools.get_gdelt_sentiment:196` | news_tools :351 | GDELT daily tone series | Yes |
| `analysis_tools.get_news_sentiment_series:9844` | news_tools :352 (also market_tools :279) | score/-1..1 + SMA + innovation + article count | Yes |
| `analysis_tools.get_earnings_event_read:660` | news_tools :371 | surprise% + side + print-day move/vol + PEAD verdict | Yes |
| `analysis_tools.get_earnings_surprise:1671` | fundamentals_company_tools :392 | last surprise% + side + date | Yes |
| `analysis_tools.get_analyst_verdict:1580` | fundamentals_company_tools :391 | value/trap/distress screens (EY, F, M, Altman Z, Ohlson O, Zmijewski) | Yes |
| `market_position_tools.get_sec_filings:141` | news_tools :360 | recent filings by form type (8-K/10-K/10-Q/S-1/13D) | Yes [CORRECTED 2026-09-26: the module was wrong — the tool lives in `agents/utils/market_position_tools.py:141` and routes to `dataflows/sec_edgar.py::get_sec_filings:426` via `route_to_vendor`; `analysis_tools` never defined it.] |
| `analysis_tools.get_beat_miss_sizing:2579` | news_tools :372 | position multiplier from beat/miss side + catalyst | Yes |
| `analysis_tools.get_macro_regime_read:9486` | news_tools :355 | single label Risk-On / Liquidity-Contraction / Stagflation | Yes |
| `analysis_tools.get_credit_spread_read:7393` | news_tools :374 | HY/CCC/BB OAS band + de-risk scale | Yes |
| `analysis_tools.get_taylor_read:3196` | news_tools :366 | Taylor implied rate + tight/easy/neutral | Yes |
| `analyst_data_tools.get_analyst_ratings:10` | fundamentals_company_tools :386 | recommendation trend + price-target consensus | Yes (not in news set) |
| `analyst_data_tools.get_earnings_calendar:30` | news_tools :359 | next earnings date + EPS est/actual + surprise_pct | Yes |
| `analyst_revision_tools.get_analyst_revision_index:43` | fundamentals_company_tools :393 | weighted up/down revision ratio | Gated `enable_analyst_revision_index` (default False) → DISABLED sentinel |
| `moomoo_extra_tools.get_corporate_actions:138` | fundamentals_company_tools :389 | dividends + splits | Yes |
| `moomoo_extra_tools.get_dividends:157` | fundamentals_company_tools :390 | dividend rows (declaration/ex/pay) | Yes |
| `market_position_tools.get_share_buyback_authorization:49` | fundamentals :362 | trailing buyback/repurchase rows; authorization = unavailable | Yes |
| `quant_formula_tools.get_disclosure_tone:381` | news_tools :361 | LM tone counts + readability + filing-vs-news gaps | Yes (litigious channel only) |
| `macro_data_tools.get_macro_indicators:9` | news_tools :354 | FRED macro series | Yes |

---

## 3. Defects and dead seams

1. **Relevance score is computed but not surfaced automatically.** `get_news_relevance_read:57` returns `Relevance score: X/100`, and `news_analyst.py:46` instructs the analyst to cite it — but there is no report-disclosure/attribution block emitting it. A reader sees the score only when the model volunteers it; every grep for `relevance` outside the tool/strategy found no report-side consumer. (Disagreement pair: `news_data_tools.py:80` vs the absence of any report renderer.)
2. **`mention_volume:43` and `sentiment_velocity:25` are exported with no caller.** `sentiment.py:824-825` lists them in `__all__`; repo-wide grep finds only the definitions and the docstring mention. The "news volume acceleration" component has a producer that nothing reads → UNWIRED. [CORRECTED 2026-09-26: stale — both symbols have callers now: `mention_volume` at `analysis_tools._news_components`'s two `heat = mention_volume(...)` calls, `sentiment_velocity` (`vel = sentiment_velocity(...)`). Retained as the record of the state at writing time.]
3. **`estimate_change_index:176` can never return a value.** Its own docstring/basis says the engine holds "current consensus and price targets only, not a 3-4 quarter estimate history"; `get_analyst_revision_index:43` therefore always prints the estimate-change leg as `unavailable`. The price-target-revision component has a producer shape with no data behind it.
4. **Revision index mis-homed.** `get_analyst_revision_index` (the only analyst-change score) is bound in `fundamentals_company_tools` (`toolsets.py:402`), not `news_tools()` — the NewsScore engine cannot reach it through the news analyst.
5. **Flag-gated producers.** `aggregate_weighted_sentiment` (novelty dedupe + decay) is reachable only via `_sentiment_agg_rows:6734` behind `enable_weighted_sentiment_agg=False` (`default_config.py:1050`); `enable_weighted_sentiment_window=False` (`:1049`); `enable_news_relevance=False` (`:903`). Default runs emit none of the novelty/persistence math. [CORRECTED 2026-09-26: stale for two of the three — `_news_components` calls `news_novelty` (`analysis_tools._news_components` (`nov = news_novelty(...)`)) and `mention_volume` (the persistence leg's `heat = mention_volume(...)`) with **no** sentiment gate, so those legs are emitted whenever the news engine runs (`enable_news_score` is its own gate). `enable_weighted_sentiment_agg` still gates the separate `aggregate_weighted_sentiment` path.]
6. **Materiality is not scored, only relevance.** `score_news_article:55` docstring: "Deterministic relevance score (0-100) + <=5 explainable reasons." The return is `{"score": round(score,1), "reasons": reasons[:5]}` built solely from lexical match flags (code/name presence, official host, macro term). There is no magnitude, dollar, %move, or event-severity term — so the owner's "materiality" half of the 20-point component is unimplemented, and a reader today would see a high relevance score for a trivial press mention and (wrongly) read it as material.

---

## 4. What is ABSENT, and the smallest honest producer

| ABSENT/PARTIAL | Data needed | Already fetched anywhere? | Smallest honest producer |
| --- | --- | --- | --- |
| materiality | event magnitude (dollar value, % move, volume multiple, market cap) | Partially: `get_earnings_event_read` has print-day move + volume ratio; no generic event magnitude | A materiality term = |expected/implied move| × event class weight, computed from existing `catalyst.implied_move_from_history:138` + volume ratio |
| novelty | article timestamps + near-duplicate key | YES: AV `time_published`, yfinance `pubDate/providerPublishTime`, GDELT `seendate`, EODHD `date`, NewsAPI `publishedAt`; dedupe key `_normalise_headline:604` | Count of not-yet-seen headline keys in the lookback window / total articles (0-1), reusing `_normalise_headline` + `seen` set in `aggregate_weighted_sentiment:616` |
| revenue-impact estimate | analyst estimate delta / guidance delta | No | Wrap `get_analyst_revision_index` ratio; refuses without estimate history (as `estimate_change_index` already does) |
| margin-impact estimate | margin guidance / cost shock | No | ABSENT — no source; label a constant, do not fabricate |
| guidance change | company guidance vs prior guidance | No (`get_earnings_calendar:30` = EPS only) | None honest; SEC 8-K label is the only inkling [CORRECTED 2026-09-26: "No" is stale — `benzinga_tools.get_guidance_revisions:34` returns company guidance with its prior range (bound at `toolsets.py:411`, gate `enable_benzinga_surface` default off), so the smallest honest producer is now "consume `get_guidance_revisions` (gated off by default; `NA` with the gate reason when off)" rather than "None honest".] |
| M&A / partnership / contract / product | event-type classification of article/filing text | Only SEC form label `_FORM_LABELS:36` | Extend `_FORM_LABELS` typing + a keyword classifier over `get_news` output; must print basis |
| management change | executive-change feed | No | ABSENT |
| regulatory action | regulator/action feed | No | ABSENT |
| price-target revision | historical PT series | `get_analyst_ratings:10` gives current consensus only | Snapshot PT consensus daily and diff; not available now |
| industry shock | sector-wide event/peer-move read | `get_market_breadth:98` (breadth), `sector_rotation_screen` | Sector-relative abnormal move over the news window |
| news volume acceleration | per-day article counts | YES: `daily_sentiment_sma` carries `n` per day; `mention_volume:43` already computes the ratio | Wire `sentiment.mention_volume` to the `n` series from `get_news_sentiment_series` [CORRECTED 2026-09-26: **wired** — `mention_volume` reads `daily_sentiment_sma`'s per-day `n` at `analysis_tools._news_components`'s `heat = mention_volume(...)`; the remaining gap is that it is the level ratio, not a first difference (`NEWS-8`, `MASTER_PLAN.md:198`).] |

**Relevance-vs-materiality, quoted:** the function's docstring (`news_relevance.py:56`) reads "Deterministic relevance score (0-100) + <=5 explainable reasons", and it returns `{"score": round(score, 1), "reasons": reasons[:5]}` (`:93`). Every point is a lexical/membership flag (code-in-title +55, company-name +45, official +8, macro -12). It measures *whether the article is about this ticker from a credible source*, not *how much it moves the fundamental*. `is_official:48`, `admit_article:97` and `degrade_triple:108` are all in the same module (`news_relevance.py`). The analyst leaf is `get_news_relevance_read` (`news_data_tools.py:57`, bound in `news_tools()` at `toolsets.py:355`); the score is printed by the leaf and the prompt asks the analyst to cite it (`news_analyst.py:46`), but nothing in the report assembly prints it — so today it is in the report only when the LLM includes it.

---

## 5. The composite — how `NewsScore` gets built

**This engine ships last, and only in a partial form.** The staged spec's own
ordering is explicit: `EventScore` should exist *before* `NewsScore` is allowed
to influence anything. The design constraints:

1. **Coverage is printed, always.** With five categories ABSENT, the score must
   ship with `coverage = available_weight / 100` beside it. A 40%-coverage
   `NewsScore` is a legitimate output; a 40%-coverage `NewsScore` printed without
   its coverage is a lie.
2. **`NA ≠ 0`** (master rule 1). The absent categories reduce the denominator.
3. **Relevance and materiality are separate rows** (§0.2), and materiality stays
   `NA` until its producer exists.
4. **Novelty is built before the score.** It is the highest-value item in the
   table — 15% of the weight, a known recipe, the data already fetched, and a
   known sign (stale news reverses). It should be built as a standalone leaf
   first, printed, and only then weighted.
5. **The sign of coverage is decided explicitly** (§0.4 point 2). A high
   `mention_volume` is not automatically bullish.
6. **No tone number crosses the boundary.** This engine may read
   `text_factors.lm_tone:121` (its own lexical pipeline) but not
   `sentiment.aggregate_weighted_sentiment:845` (§0.3).
7. **Its own band table**, advisory, feeding nothing (master rule 2).
8. **Nothing here sizes or gates.** `get_beat_miss_sizing:2252` keeps its own
   path; `NewsScore` never feeds it.

### 5.1 Build order (value ÷ effort)

| Order | Item | Why |
| --: | --- | --- |
| 1 | **Novelty** (15%) | known recipe (Tetlock similarity-to-prior-stories), data present, sign known |
| 2 | **Materiality** (half of 20%) | the largest weight currently has no producer; a move-based estimate is derivable from `catalyst.implied_move_from_history:138` + the print-day volume ratio |
| 3 | **Persistence / volume acceleration** (5%) | `mention_volume:43` and `decayed_weight:91` already exist — wiring, not building [CORRECTED 2026-09-26: the wiring has landed (`analysis_tools._news_components`'s `heat = mention_volume(...)`); what remains is the acceleration (first-difference) quantity, not the level ratio — `NEWS-8`, `MASTER_PLAN.md:198`.] |
| 4 | **Corporate-event typing** (10%) | extend `sec_edgar._FORM_LABELS:39` and add a keyword classifier over `get_news` output, printing its basis |
| 5 | **Guidance change** (part of 15%) | needs a data source the engine does not have; do not fake it from the EPS estimate [CORRECTED 2026-09-26: the "needs a data source" half is stale — `benzinga_tools.get_guidance_revisions:34` exists (bound at `toolsets.py:411`, gate default off); do not fake it from the EPS estimate still stands.] |
| 6 | **Fundamental impact** (20%) | needs an estimate history (`estimate_change_index:176` documents exactly this absence) — the honest answer today is `NA` |

---

## 6. Verification requirements

1. **Coverage is a tested output**, not a comment: with the five absent categories
   fed `None`, the score is `None` (0% coverage), and with the four present it
   equals the weighted mean of those four.
2. **Novelty moves the right way**: a repeated headline (same normalised key
   within the window) must score lower than a first-seen one.
3. **Materiality is never inferred from relevance**: a test asserts the two are
   independent inputs and that relevance alone cannot raise the composite.
4. **No cross-engine number**: a test asserts no `sentiment.py` aggregation
   function is imported by the news path.
5. **The absent categories are printed as `NA` with a reason**, never as 0.

---

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Which sign for coverage?** `mention_volume:43` is a coverage measure; the
   neglected-firm evidence says low coverage has historically meant *higher*
   forward returns. The owner's "news volume acceleration" implies high = good.
   These conflict, and the resolution decides the persistence category's direction. **CLOSED 2026-09-17 (plan §13 Q9): the neglected-firm sign** - lower abnormal coverage is the positive signal; do not reverse it into an attention-is-good factor.
2. **Is materiality a news property or an event property?** A magnitude estimate
   is arguably `EventScore`'s (it owns the expected move). If so, this category
   should read EventScore's number rather than build a second one — which is exactly the "one number, one producer" rule. **CLOSED 2026-09-17 (plan §13 Q6): `EventScore` owns it; this engine consumes that number.**
3. **Where does the analyst-revision index live?** It is currently bound to the
   fundamentals toolset (`toolsets.py:402`) while this engine's 5% category needs
   it. Either the news surface gains the leaf, or the category is dropped and the weight redistributed. **CLOSED 2026-09-17 (plan §13 Q4): the binding moves; the category keeps its weight.**
4. **Should `NewsScore` be per-name at all**, or is it a market-level flow
   measure? Most of the owner's categories are name-level; the macro/industry ones are not.
**DECIDED 2026-09-17:** primarily **per-name** - the score answers what the current
news environment implies *for this security*. Market-wide news belongs to
`RegimeScore` (environment) or `EventScore` (catalyst).
5. **Does the report print a per-article relevance list** (an attribution block),
   or only the aggregate? Today the score reaches the report only when the LLM volunteers it (defect 1 in §3).
**DECIDED 2026-09-17:** keep the per-article information **internally** (relevance,
sentiment, novelty, the materiality reference, timestamp) and make the **aggregate
the primary report output**, with a concise evidence section naming the
highest-impact articles. Auditability without an unreadable report.

---

## 8. The owner's formula library (`Strategies/scores/news_score.md`, 2026-09-26)

**2,670 lines, 119 headings, 213 display formulas.** The headings are 115 numbered
`# N.` sections, three lettered subsections (`### A/B/C` under §114) and one
unnumbered `## Recommended engine decomposition`. The formulas are the `$$…$$`
display blocks (a `$$` pair = one formula); 12 of them are `\boxed`, 2 use
`\begin{cases}`, and 4 headings carry none (`§1`, `§113`, `§114`, the
decomposition) because they are architecture prose or a rendered output sample.
Counted by script over the raw file, not by hand.

**What it is, and what it is not.** It is a *formula catalogue* — an exhaustive
menu of 115 candidate computations, several of which are alternative recipes for
the same quantity — not a spec of what is built and not the source of this
engine's weights. The nine categories and their weights come from
[`../ScoreWeight/news_sentiment.md`](../ScoreWeight/news_sentiment.md) (§0.1);
the library is the later, wider artefact and the delta between the two is the
whole point of this section. §1's inventory is the *engine-side* cut (9 categories
→ 24 producer rows); §8.1 is the same problem cut the *library-side* way (one row
per formula section), so the two are crosswalks of each other, not duplicates.

**Ledger: 6 `built`, 43 `PARTIAL`, 52 `ABSENT`, 18 `elsewhere`** (119 rows).
`built` = a producer exists and the news path can read it today; `PARTIAL` = a
producer exists but computes a materially narrower thing; `elsewhere` = a producer
exists in the tree but belongs to another engine (sentiment, portfolio, alpha or
event layer); `ABSENT` = no producer anywhere, with the smallest honest producer
named in the status cell. Every symbol below was read, not grepped for.

### 8.1 The library's sections against the engine

| § | Library section | Formulas | Status — producer (`module.symbol:line`) |
| --: | --- | --: | --- |
| 1 | NewsScore architecture | 0 | PARTIAL — `news_score.news_score:906` (one composite; 0-100 favourable, coverage emitted, confidence/regime/shock outputs absent) |
| 2 | Basic sentiment transformation | 4 | elsewhere — `sentiment_score.normalise_sentiment:80` (scale table → -1..1, refuses an unknown source; not on the news path) |
| 3 | Sentiment magnitude | 1 | PARTIAL — `sentiment.aggregate_weighted_sentiment:845` (`neutral_share` uses `abs(s) < eps`; no magnitude is emitted) |
| 4 | Sentiment confidence | 4 | ABSENT — nearest `sentiment.sentiment_dispersion:400` (dispersion, not a confidence) |
| 5 | Relevance score | 3 | built — `news_relevance.score_news_article:56` (the 5-term weighted sum reduced to lexical flags), wired at `analysis_tools._news_components:6982` |
| 6 | Entity prominence | 4 | PARTIAL — `news_relevance.score_news_article:56` (title +45 vs snippet +28 is a prominence proxy; no mentions/words ratio) |
| 7 | News novelty | 4 | built — `news_score.news_novelty:309` (first-seen share over exact normalised keys; no embedding cosine) |
| 8 | Duplicate suppression | 3 | PARTIAL — `news_score.news_novelty:309` (counts repeats) + `sentiment.aggregate_weighted_sentiment:845` (drops dupes outright; no `W_dup` weight) |
| 9 | Source quality score | 2 | PARTIAL — `news_relevance.is_official:51` + `OFFICIAL_HOSTS:24` (binary official flag, +8); no `Q_i` 0-1 composite |
| 10 | Primary-source multiplier | 1 | PARTIAL — `news_relevance.is_official:51`; the sentiment path's `official_boost` (`sentiment.aggregate_weighted_sentiment:845`) is gated and off the news path |
| 11 | News age / exponential decay | 3 | elsewhere — `sentiment.decayed_weight:194` (`2^(-age/HL)`, HL default 7d), used by `aggregate_weighted_sentiment:845` (the older `weighted_sentiment:109` caller was **deleted**, SENT-14); the news engine has no decay component (`news_score.RAMPS:129`) [CORRECTED 2026-09-26: the "no decay component" reading is **correct**, and it now disagrees with the engine's own declaration: `news_score.COMPONENTS["persistence"].producer` cites `sentiment.mention_volume:171 + decayed_weight:91` (`news_score.COMPONENTS`'s `persistence` row (`news_score.py:167`)), but only the `mention_volume` half is called (`analysis_tools._news_components`'s `heat = mention_volume(...)`) — `analysis_tools._news_components`'s NOTE comment ("the declaration also cites `sentiment.decayed_weight:194`. That half is NOT called here ... The citation's second half has no call site.") states "the declaration also cites `sentiment.decayed_weight:194`. That half is NOT called here ... The citation's second half has no call site." Recorded as the **mislabelled-declaration** defect **D-9** in `IMPLEMENTATION_PLAN.md` §14 — **not** as a built component. Do not read decay as built.] |
| 12 | Multiple news half-lives | 1 | ABSENT — nearest `sentiment.decayed_weight:194` (one half-life) |
| 13 | Event-type decay | 1 | ABSENT — nearest `sentiment.decayed_weight:194` |
| 14 | Event importance | 2 | ABSENT — nearest `event_state.event_state:591` (event imminence by family, not importance) |
| 15 | Event materiality | 3 | PARTIAL — `catalyst.implied_move_from_history:138` (`abs(expected move)`, the magnitude half); the ratio to market cap is absent and the engine's slot is caller-supplied (`news_score.ABSENT_REASONS:101`) |
| 16 | Earnings surprise | 4 | built — `events.surprise_score:17` via `catalyst.last_earnings_surprise:77`, wired at `analysis_tools._news_components:6982`; the σ-standardised `Z`/`tanh` legs are absent |
| 17 | Guidance surprise | 2 | ABSENT — `news_score.ABSENT_REASONS:101`; `analyst_data_tools.get_earnings_calendar:30` returns an EPS/revenue estimate, never guidance [CORRECTED 2026-09-26: a producer exists now — `benzinga_tools.get_guidance_revisions:34` (forward revenue/EPS range with the prior range), bound at `toolsets.py:411`, `enable_benzinga_surface` default off; it is not consumed by this engine, and `get_earnings_calendar` remains EPS/revenue estimates only.] |
| 18 | Revenue growth surprise | 2 | ABSENT — nearest `catalyst.last_earnings_surprise:77` (EPS only) |
| 19 | Margin surprise | 1 | ABSENT — no producer (grep `margin_surprise` = 0) |
| 20 | Multi-metric earnings surprise | 2 | ABSENT — nearest `analysis_tools.get_earnings_surprise:1671` (EPS leg only) |
| 21 | Event polarity | 2 | PARTIAL — `news_data_tools.get_massive_news:167` (vendor per-article positive/negative/neutral) + `text_factors.lm_tone:121`; no event-class `P_k` table |
| 22 | Event probability | 3 | elsewhere — `catalyst.fed_imminence:169` (`modal_prob`, the market-implied FOMC probability): one family, event layer not news |
| 23 | Event uncertainty penalty | 3 | PARTIAL — `text_factors.lm_tone:121` returns an `uncertainty` word count; nothing multiplies a score by `C` |
| 24 | Article-level news score | 1 | PARTIAL — `news_score.news_score:906` + `score_engine.combine:142` (weight-renormalised mean over components, not a per-article product) |
| 25 | Weighted news average | 2 | elsewhere — `sentiment.aggregate_weighted_sentiment:845` (`Σws/Σw`, `w` = relevance × decay × official), gated by `enable_weighted_sentiment_agg=False` |
| 26 | Positive news intensity | 1 | ABSENT — nearest `sentiment.score_from_counts:219` (signed share, not a weighted positive sum) |
| 27 | Negative news intensity | 1 | ABSENT — nearest `sentiment.score_from_counts:219` |
| 28 | News balance | 1 | PARTIAL — `sentiment.score_from_counts:219` (`(bullish - bearish)/labelled`) |
| 29 | Positive/negative ratio | 2 | PARTIAL — `sentiment.crowd_ratio:336` (`B/(B+BE)`, display-only bands) |
| 30 | Weighted positive count | 1 | ABSENT — nearest `sentiment._weighted_modal_share:388` (a weighted share, not a count) |
| 31 | Weighted negative count | 1 | ABSENT — nearest `sentiment._weighted_modal_share:388` |
| 32 | Weighted neutral count | 1 | PARTIAL — `sentiment.aggregate_weighted_sentiment:845` (`neutral_share`, an unweighted share of `abs(s) < eps`) |
| 33 | News breadth | 2 | PARTIAL — `sentiment.score_from_counts:219` (the same normalised difference as §28) |
| 34 | News volume | 3 | PARTIAL — `sentiment.mention_volume:171` + `sentiment.daily_sentiment_sma:730` (`n` per day), wired at `analysis_tools._news_components:6982` |
| 35 | Abnormal news volume | 2 | PARTIAL — `sentiment.mention_volume:171` (recent/baseline ratio = the section's second form; no z-score) |
| 36 | News volume z-score | 1 | ABSENT — nearest `sentiment.surprise_velocity:201` (a z-score of sentiment, not volume) |
| 37 | News intensity | 1 | ABSENT — nearest `sentiment.sentiment_dispersion:400` |
| 38 | News disagreement | 2 | elsewhere — `sentiment.sentiment_dispersion:400` (weighted population σ of per-item polarity = the section's `σ_s`) |
| 39 | News entropy | 3 | ABSENT — nearest `complexity.permutation_entropy:19` (price-series entropy) / `portfolio.weight_entropy:431` (weights) |
| 40 | News confidence | 2 | ABSENT — nearest `sentiment.aggregate_weighted_sentiment:845` (`min_n` withholding: a floor, not a confidence) |
| 41 | Sample-size confidence | 2 | ABSENT — nearest `sentiment.aggregate_weighted_sentiment:845` (`min_n`) |
| 42 | Bayesian news confidence | 3 | ABSENT — nearest `analyst_revisions.revision_ratio:79` (coverage guard, no Beta posterior) |
| 43 | Wilson confidence interval | 2 | ABSENT — grep `wilson` = 0 |
| 44 | News acceleration | 2 | ABSENT — nearest `sentiment.mention_volume:171` (a level ratio, no first difference) |
| 45 | News momentum | 2 | PARTIAL — `sentiment.sentiment_velocity:37` (OLS slope of sentiment, not a NewsScore difference) |
| 46 | Sentiment momentum | 1 | PARTIAL — `sentiment.sentiment_velocity:37` + `sentiment.weighted_rolling_sentiment:968` |
| 47 | News trend | 2 | PARTIAL — `sentiment.sentiment_velocity:37` (the β of S on t; on the sentiment series) |
| 48 | Exponentially weighted news trend | 2 | elsewhere — `sentiment.weighted_rolling_sentiment:968` (exp-weighted rolling sentiment); it emits a momentum, not a trend |
| 49 | News persistence | 2 | PARTIAL — the engine's `persistence` = `sentiment.mention_volume:171` inverted (`news_score.COMPONENTS:158`), wired at `analysis_tools._news_components:6982`; "share of positive periods" is absent |
| 50 | News reversal | 2 | ABSENT — nearest `momentum.momentum_12_1:358` (price short-term reversal) |
| 51 | Event clustering | 4 | ABSENT — nearest `sentiment.mention_volume:171` |
| 52 | Hawkes-process news intensity | 1 | ABSENT — grep `hawkes` = 0 |
| 53 | Event surprise | 2 | PARTIAL — `events.surprise_score:17` (the standardised ratio, no σ-`Z`) |
| 54 | Historical event-class surprise | 2 | ABSENT — nearest `analysis_tools.get_earnings_event_read:660` (print-day move + PEAD, earnings class only) |
| 55 | Event-class Bayesian prior | 2 | ABSENT — no `P(R>0 given k)` producer |
| 56 | Market reaction score | 3 | PARTIAL — `analysis_tools.get_earnings_event_read:660` (print-day return/volume/PEAD; earnings class only) |
| 57 | Abnormal return | 1 | elsewhere — `cross_section.residualize_returns:223` |
| 58 | CAPM abnormal return | 1 | elsewhere — `cross_section.residualize_returns:223` |
| 59 | Market-model abnormal return | 2 | elsewhere — `cross_section.residualize_returns:223` |
| 60 | Sector-adjusted return | 1 | ABSENT — nearest `cross_section.industry_neutral_z:111` (industry-neutral factor z, not a return) |
| 61 | Multi-factor abnormal return | 1 | elsewhere — `factors.fama_french_5_factor:518` |
| 62 | Cumulative abnormal return | 2 | ABSENT — grep `cumulative_abnormal` = 0; nearest `analysis_tools.get_earnings_event_read:660` |
| 63 | Volume confirmation | 2 | PARTIAL — `analysis_tools.get_earnings_event_read:660` (print-day `volume_ratio` with a 2.5× gate) |
| 64 | Price/news agreement | 1 | PARTIAL — `sentiment_score.confirmation_quadrant:342` (price × second read 2×2; the second read is sentiment, not news) |
| 65 | News-market confirmation | 1 | PARTIAL — `sentiment_score.confirmation_quadrant:342` |
| 66 | News-price divergence | 1 | PARTIAL — `sentiment_score.confirmation_quadrant:342` (`diverge-up`/`diverge-down`) + `text_factors.divergence:198` |
| 67 | Market surprise reaction | 2 | ABSENT — nearest `catalyst.implied_move_from_history:138` |
| 68 | Reaction persistence | 1 | PARTIAL — `events.expected_drift_after:56` + `events.drift_side:26` + `analysis_tools.get_earnings_event_read:660` (PEAD verdict) |
| 69 | News-to-price elasticity | 2 | elsewhere — `sentiment_research.multi_horizon_sentiment_regression:264` (`sent_coef` = ΔReturn/ΔSentiment) |
| 70 | Rolling news-return correlation | 1 | elsewhere — `sentiment_research.sentiment_lead_lag:172` + `rolling_information_coefficient:337` |
| 71 | Stock-specific news sensitivity | 2 | elsewhere — `sentiment_research.multi_horizon_sentiment_regression:264` |
| 72 | News-to-volatility effect | 2 | ABSENT — nearest `sentiment_research.multi_horizon_sentiment_regression:264` (volume is a control there, not the dependent) |
| 73 | News volatility shock | 1 | ABSENT — nearest `analysis_tools.get_garch_volatility:10046` (a vol level/regime, not a news vol shock) |
| 74 | News impact score | 1 | ABSENT — nearest `news_score.news_score:906` |
| 75 | Source disagreement | 1 | elsewhere — `sentiment.sentiment_dispersion:400` (σ across items, weights optional) |
| 76 | Cross-source consensus | 1 | PARTIAL — `sentiment.consensus_overlap:183` (share in the majority bucket, not `abs(Σws)/Σw`) |
| 77 | Cross-source contradiction | 1 | ABSENT — nearest `sentiment.consensus_overlap:183` |
| 78 | Headline/body disagreement | 1 | PARTIAL — `text_factors.divergence:198` (tone gap between two documents; no headline/body split) |
| 79 | Fact/opinion separation | 2 | ABSENT — no classifier (grep `factual` finds none) |
| 80 | Rumor probability | 2 | ABSENT — grep `rumor` = 0 |
| 81 | Information novelty × sentiment | 1 | ABSENT — nearest `news_score.news_novelty:309` (novelty alone) |
| 82 | Surprise × sentiment | 1 | ABSENT — nearest `events.surprise_score:17` |
| 83 | Novelty × importance | 1 | ABSENT — nearest `news_score.news_novelty:309` |
| 84 | Complete article weighting formula | 2 | PARTIAL — `news_score.news_score:906` (component weights, not the per-article product) |
| 85 | Event-type weighted score | 3 | ABSENT — nearest `news_score.COMPONENTS:158` (`corporate_events` is declared with `sec_edgar._FORM_LABELS:39` as producer but is never supplied by `_news_components:6698`) |
| 86 | Event-type weights | 1 | PARTIAL — `news_score.COMPONENT_WEIGHTS:65` (hard-coded owner weights; the IC-derived form is elsewhere) |
| 87 | Information coefficient weighting | 3 | PARTIAL — `alpha_health.rank_information_coefficient:173` + `sentiment_research.rolling_information_coefficient:444` produce IC; nothing weights news factors by it |
| 88 | ICIR weighting | 2 | PARTIAL — `alpha_health.per_period_ic:200` (returns `icir` = mean/std) + `signal_analysis.icir:77` |
| 89 | Rank-based normalization | 2 | elsewhere — `cross_section.centered_rank:162` + `alpha_health._rank_avg:143` |
| 90 | Cross-sectional z-score | 2 | elsewhere — `cross_section.cross_sectional_z:70` + `sentiment_research.sector_neutral_z:346` |
| 91 | Robust z-score | 2 | PARTIAL — `analyst_revisions.winsor_z:253` (winsorised z; the MAD form is absent, grep `median_absolute` = 0) |
| 92 | Winsorization | 1 | elsewhere — `cross_section.winsorize:31` |
| 93 | Logistic normalization | 2 | elsewhere — `normalized.ohlson_o_score:157` (the logistic link `p = 1/(1+e^-o)` for distress probability, not a score normaliser) |
| 94 | Hyperbolic tangent normalization | 1 | ABSENT — grep `tanh` = 0; nearest `score_engine.align:69` (linear ramp + clamp) |
| 95 | Final 0–100 mapping | 2 | built — `score_engine.align:69` + `news_score.align_components:882` (a ramp `lo→0`/`hi→100`, not `50(x+1)`) |
| 96 | Multi-horizon NewsScore | 6 | PARTIAL — `sentiment_research.multi_horizon_sentiment_regression:264` + `ic_term_structure:394`; the engine is a single 30-day window (`analysis_tools._news_components:6982`) |
| 97 | Short-term news score | 1 | PARTIAL — `sentiment.daily_sentiment_sma:730` (7d SMA) + `weighted_rolling_sentiment:739` |
| 98 | Medium-term news score | 1 | PARTIAL — same producers; only one window exists |
| 99 | Long-term news score | 2 | PARTIAL — same producers |
| 100 | News regime | 1 | ABSENT — nearest `analysis_tools.get_macro_regime_read:9486` (market regime, not news) |
| 101 | News shock score | 2 | PARTIAL — `sentiment.daily_sentiment_sma:730` (`innovation` = the daily sentiment shock), surfaced by `analysis_tools.get_news_sentiment_series:9844` |
| 102 | News pressure | 2 | ABSENT — nearest `sentiment.score_from_counts:219` (the identical normalised difference, unweighted) |
| 103 | News flow imbalance | 1 | ABSENT — nearest `sentiment.score_from_counts:219` |
| 104 | News breadth × intensity | 1 | ABSENT — no producer |
| 105 | News consensus × intensity | 1 | ABSENT — nearest `sentiment.consensus_overlap:183` |
| 106 | News confidence × conviction | 1 | ABSENT — no producer |
| 107 | News score with coverage | 1 | built — `score_engine.coverage_floor:53` + `combine:134`; `news_score.news_score:906` returns `coverage`, printed by `analysis_tools._render_news_score:7115` |
| 108 | Effective sample size | 1 | ABSENT — nearest `sentiment.mention_volume:171` |
| 109 | News coverage score | 1 | PARTIAL — `score_engine.combine:142` (a weight-share coverage, not `1-e^{-Neff/k}`) |
| 110 | Effective information score | 1 | ABSENT — nearest `news_score.news_novelty:309` |
| 111 | Final NewsScore candidate | 3 | built — `news_score.news_score:906` (weight-renormalised mean, 0-100; no `tanh`, no per-article product) |
| 112 | Recommended confidence formula | 3 | ABSENT — nearest `news_score.news_score:906` (coverage only) |
| 113 | Recommended NewsScore output | 0 | PARTIAL — `analysis_tools._render_news_score:7115` + `reporting._run_card_news_score:1604` (score/coverage/absent reasons; no Confidence/Materiality/Effective-Articles lines) |
| 114 | The most important distinction (Direction / Information / Reaction) | 0 | ABSENT — nearest `news_score.news_score:906` (one composite) |
| A | News Direction | 1 | ABSENT — same |
| B | News Information | 1 | ABSENT — same |
| C | News Market Confirmation | 2 | ABSENT — nearest `sentiment_score.confirmation_quadrant:342` (a sign quadrant, not a scored leg) |
| 115 | Recommended production formula | 5 | PARTIAL — `news_score.news_score:906` + `news_score.COMPONENT_WEIGHTS:65` (owner weights, not the learned α/β/γ blend) |
| — | Recommended engine decomposition | 0 | PARTIAL — `news_score.COMPONENTS:158` covers items 1-4 and 7-10 partly; item 5 (event classification), 6 (source quality), 9 (market reaction) and the OUTPUT block (NewsConfidence / NewsShock / NewsRegime) are absent |

### 8.2 Not built — the backlog the library names

The five gaps §0.1 already names, each checked against the library, with the
library sections that would close it. `regulatory/legal` and `industry shock` are
deliberately absent from this table: the library **cannot** close them — §13's
event list names "regulatory / legal" and "geopolitical" only as *decay classes*,
and no section gives a classifier or a producer recipe for either, so the two
gaps stay open with the library in hand.

| Backlog item (§0.1 / §1) | Library sections that would close it | What exists today | What is missing |
| --- | --- | --- | --- |
| **novelty** (15%) | §7 (4 recipes), §8 (`W_dup`), §81 (Novelty × Sentiment), §83 (Novelty × Importance), §110 (`Neff × Novelty × Importance`) | `news_score.news_novelty:309` — first-seen share over exact normalised keys, wired at `analysis_tools._news_components:6982` | the embedding forms (§7's `1 - max_j CosSim`, §7's `e^{-λD_i}`), the suppression *weight* (§8), and every product that consumes novelty |
| **materiality** (half of 20%) | §15 (the definition), §14 (importance inputs), §22 (event probability), §53 (standardised surprise), §84/§111 (`I_i` in the weight product) | `catalyst.implied_move_from_history:138` (`abs(expected move)`); the engine's slot is caller-supplied (`news_score.ABSENT_REASONS:101`, owner Q6) | the ratio to market cap (§15's own definition), the 5-term importance vector (§14), the probability weight (§22) |
| **fundamental impact** (20%) | §18 (revenue growth surprise), §19 (margin surprise), §20 (multi-metric `w1Z_EPS + … + w5Z_FCF`), §17 (the guidance leg of the same blend) | nothing; `analysis_tools.get_earnings_surprise:1671` is EPS-only | the revenue and margin surprise legs and the cross-metric `Z` blend |
| **guidance change** (part of 15%) | §17 (`(G_new - G_old)/abs(G_old)`, `(G_new - Consensus)/abs(Consensus)`), §21 (the raised/maintained/lowered polarity map), §20 (`Z_Guidance`) | nothing; `analyst_data_tools.get_earnings_calendar:30` carries an EPS/revenue estimate only | a guidance series to difference, and the polarity map [CORRECTED 2026-09-26: "nothing" is stale — a guidance producer exists (`benzinga_tools.get_guidance_revisions:34`, forward revenue/EPS range with the prior range, bound at `toolsets.py:411`, `enable_benzinga_surface` default off); what is missing is consumption by the engine plus the polarity map.] |
| **persistence** (5%) | §49 (share of positive periods; `Σ γ^k I(S_{t-k}>0)`), §11/§12/§13 (decay shapes), §44/§45/§48 (acceleration, momentum, EWMA), §50 (reversal), §68 (reaction persistence) | `sentiment.mention_volume:171` wired as the *inverted* attention ratio (`analysis_tools._news_components:6982`); `sentiment.decayed_weight:194` exists but has no news-path call site | the library's persistence quantity (positive-period share), the multi-λ decay, and the volume first-difference the owner's weight table calls "news volume acceleration" |

### 8.3 Library-internal defects

Verified against the library text itself; each is a defect of the *catalogue*,
not of the engine.

1. **One quantity, four names (§28, §33, §102, §103).** §28 `NewsBalance =
   (P-N)/(P+N+ε)`, §102 `NewsPressure* = (P-N)/(P+N+ε)`, §33 `Breadth =
   (N+ - N-)/(N+ + N-)`, §103 `NFI = (PF - NF)/(PF + NF)` are the same normalised
   difference on differently-labelled counts. Four sections, one formula — the
   exact shape master rule 15 forbids on the code side.
2. **One quantity, four "master formulas" (§24, §84, §111, §115).** §24
   `A_i = s·R·N·Q·I·D·C`; §84 `w_i = R·Q·N·I·C·D·U`, `ArticleScore = w·S`; §111
   `NS_raw = Σ S R Q N I C D U / Σ R Q N I C D U`; §115 `ArticleScore = S R Q N M C
   D U`. §24 and §84 differ only by `U`; §115 renames `I` to `M` and keeps the rest
   identical. The section titled "the most important distinction" (§114) and the
   "production formula" (§115) are not new quantities, they are §84 again.
3. **Materiality defined as surprise (§15).** §15 offers, for earnings,
   `Materiality = abs((Actual - Consensus)/Consensus)` — which is *verbatim* §16's
   `EPSSurprise`. The library thus conflates the two quantities this doc's §0.2
   exists to separate (relevance ≠ materiality; surprise ≠ materiality), and §24's
   single product `… R · I · …` would let either stand in for the other.
4. **Two confidence formulas presented as one `C_i` (§4).** §4 gives
   `C_i = max(P_pos, P_neu, P_neg)` *and* `C_i = 1 - H*` as alternatives for the
   same symbol. They are not the same number: for `p = (0.5, 0.5, 0)` the max is
   `0.5` and `1 - ln2/ln3 = 0.369`. Two different scales under one symbol.
5. **The sample-size term applied twice (§40, §41, §112).** §41's `C_N = 1 - e^{-N/k}`
   is also a factor inside §40's `Confidence = (1 - H*) × C_N`, and §112 then
   multiplies `C_N × C_agreement × C_source × C_novelty` while §41's own
   `AdjustedNewsScore = Raw × C_N` applies it to the score as well. Followed
   literally, the same shrinkage enters a confidence and a score multiplier.
6. **Two incompatible output scales (§1/§2 vs §95).** §1's architecture box ends
   `NewsScore -100/+100` and §2 maps `NewsScore_i = 100 s_i` (−100…+100), while §95
   maps `Score_100 = 50(x+1)` (0…100) and §113's example prints `73.4 / 100`. The
   library carries both conventions with no rule for which is the output.
7. **`λ` with two unit systems (§7 vs §11).** §11 defines `λ = ln2/h` (per day,
   from a half-life); §7's `N_i = e^{-λD_i}` uses `D_i` as a *count of prior
   stories*, so `λ` there is per story. Same symbol, incompatible units, in
   adjacent sections.
8. **§12 breaks the normalisation §11 establishes.** §11's `D(t) = 2^{-t/h}` has
   `D(0) = 1`. §12's `D(t) = w1e^{-λ1t} + w2e^{-λ2t} + w3e^{-λ3t}` carries no
   `Σw_k = 1` constraint, so `D(0) = Σw_k ≠ 1` and a "decay" can exceed 1 — while
   `w` is also the article weight in §24/§84, inviting the two to be confused.
9. **Undefined denominators (§7, §86).** §7's `N_i = 1 - similar/max_similar_count`
   is undefined when the maximum similar-article count is 0; §86's
   `W_k ∝ PredictivePower_k / Noise_k` is not normalised although §85 requires
   `Σ W_k = 1`, and §87 immediately re-derives `W_j = abs(IC_j)/Σabs(IC_j)` — a
   different weight recipe for the same symbol one section later.
10. **Title/content mismatches (§48, §56).** §48 is titled "Exponentially weighted
    news trend" but its boxed output is `NewsMomentum = S_t - S_t^{EWMA}` — a
    momentum, already §45's quantity. §56 is titled "Market reaction score" but
    contains only raw-return definitions (`R_30m`, `R_close`, `R_3d`) and no score;
    the scoring is §57-§62.

### 8.4 Contradictions between the library and the code

§0.2 (relevance ≠ materiality, quoted from `news_relevance.py`) and §0.3 (the
SentimentScore naming rule) are the comparison points.

| Library position | Code position | Nature |
| --- | --- | --- |
| §2/§3/§4/§24/§25/§26-§32/§37/§45/§46/§48/§81/§82/§111/§115 build the news number from a sentiment input `s_i`, and §24/§84/§111/§115 multiply by it | `news_score.py:13-16` states the engine "imports **no** `sentiment.py` aggregation"; the novelty helper is duplicated locally rather than imported (`news_score._normalise_headline:292` docstring); §0.3's naming rule | **Direct.** The library's NewsScore *is* a sentiment-weighted average — §25's `w_i = R N Q I D C` is the same weight vector `sentiment.aggregate_weighted_sentiment:845` computes. Followed literally it would make NewsScore read SentimentScore's number, the collapse §0.3 exists to prevent |
| §5's `R_i = 0.30 R_entity + 0.20 R_headline + 0.20 R_body + 0.20 R_event + 0.10 R_ticker`, and §15's materiality | `news_relevance.score_news_article:56` scores ticker/name presence, official host and a macro penalty only — no `R_body`, no `R_event`; materiality is caller-supplied (`news_score.ABSENT_REASONS:101`) and never inferred from relevance | **Partial.** The library's relevance vector has two terms with no producer; its §24 product `R · I` would let relevance and materiality be the same input, which §0.2 forbids |
| §40-§43 + §112 make NewsConfidence a first-class output, printed by §113 (`Confidence: 81.2%`) | `news_score.news_score:906` emits `coverage` (a weight share from `score_engine.combine:142`) and no confidence; §0.1's Status line says "Unmeasured (vendor gate)" | **Direct.** The library's output block has a field the engine deliberately does not have; coverage is not a substitute and the code never prints one as the other |
| §96 blends `News_1h/1d/3d/7d/30d`; §97-§99 blend short/medium/long EWMA scores | the engine is one 30-day window (`analysis_tools._news_components:6982`, `days: int = 30`) and one composite | **Direct.** The library's multi-horizon output is not built; `sentiment_research.ic_term_structure:501` measures horizon decay but does not feed a score |
| §13/§85/§86 group articles by event class `k` with weights `W_k`; §86 says "I would **not** hard-code these weights initially" | `news_score.COMPONENT_WEIGHTS:65` hard-codes the owner's weights; the only event-class artefact is `sec_edgar._FORM_LABELS:39`, declared as the `corporate_events` producer in `news_score.COMPONENTS:158` but never supplied by the live leaf `_news_components:6698` | **Partial, and a live gap.** A 10-weight component is declared with a producer that the only leaf never feeds — the component prints `NA` for a reason that is *not* "no producer exists" |
| §11/§12/§13 make time decay the core aggregation; §8 makes duplicate suppression a weight | the news engine has no decay component at all (`news_score.RAMPS:129`); the only decay producer is `sentiment.decayed_weight:194`, which §0.3 forbids importing; dedupe is a drop (`sentiment.aggregate_weighted_sentiment:845`) or a count (`news_score.news_novelty`), not a weight | **Direct.** The library's two most important aggregation terms are either forbidden by the boundary rule or unimplemented [CORRECTED 2026-09-26: retained and correct; the declaration string at `news_score.COMPONENTS`'s `persistence` row over-claims this half — see §8.1 row 11 and `IMPLEMENTATION_PLAN.md` §14 D-9.] |
| §1/§2 output `-100…+100` | `score_engine.align:69` maps to **0-100, 100 = favourable** (`news_score.align_components:882`) | **Direct.** House convention vs library convention; §95's `50(x+1)` matches the range but not the code's ramp semantics |

**Doc-side readings the code has moved past** `[ADDED 2026-09-26]` — found while
verifying the rows above, additive, nothing rewritten:

- §0.1's novelty row ("syndication dedupe exists, **no novelty score**") and §1's
  novelty row are stale: `news_score.news_novelty:309` exists and is wired at
  `analysis_tools._news_components:6982`.
- §0.1's analyst row ("bound to the fundamentals toolset") and §3 defect 4 are
  closed: `get_analyst_revision_index` is bound in `news_tools()` at
  `agents/toolsets.py:408` (P0-7b) as well as `fundamentals_company_tools` at
  `:441` — owner decision Q4's binding move has landed.
- §1's "news volume acceleration … UNWIRED" is stale: `sentiment.mention_volume:171`
  has a caller (`analysis_tools._news_components:6982`, the persistence leg). The
  second half of that citation, `sentiment.decayed_weight:194`, still has no
  news-path call site (the code comment at `analysis_tools.py:6766-6770` says so).
- Citation drift (line numbers, not claims): `news_relevance.score_news_article` is
  at `:56` (§0.2/§1 say `:53`), `is_official:51` (§4 says `:48`),
  `admit_article:100` (§4 says `:97`), `sentiment._weighted_basis:818` (§0.3 says
  `:589`), `_FORM_LABELS` at `dataflows/sec_edgar.py:39` (§1 and
  `news_score.COMPONENTS:158` say `:36`), `get_sec_filings` at
  `dataflows/sec_edgar.py:426` (§1 says `:109`), and the §2 leaf rows
  (`get_earnings_event_read:660`, `get_analyst_verdict:1554`,
  `get_earnings_surprise:1645`, `get_beat_miss_sizing:2451`, `get_taylor_read:3064`,
  `get_credit_spread_read:7011`, `get_macro_regime_read:8939`,
  `get_news_sentiment_series:9297`) all sit later than §2 records.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| **Staleness** = textual similarity to the previous ten stories about the firm; returns respond less to stale news, and stale-news days negatively predict the next week's return (overreaction that reverses) | Tetlock (2011), *All the News That's Fit to Reprint* | §0.4 point 1 and §5.1 item 1 — novelty is the highest-value build, with a known sign |
| **Low media coverage** predicts *higher* subsequent returns (neglected-firm effect), strongest where information asymmetry is high | Fang & Peress (2009) | §0.4 point 2 and §7 Q1 — coverage is not bullish by default |
| Management guidance changes carry **incremental** information, with post-guidance drift | the guidance literature | §0.4 point 3 — guidance is a real factor and currently ABSENT [CORRECTED 2026-09-26: still absent from the score, but a gated source exists in the tree — `benzinga_tools.get_guidance_revisions:34`, bound at `toolsets.py:411`, `enable_benzinga_surface` default off.] |
| Fresh, salient news is incorporated immediately; stale or competing information drifts | Barber & Odean (attention); the limited-attention reading of PEAD | §0.2 — why "count positive/negative headlines" is the wrong shape |
| Attention and tone are different signals with **opposite** short-horizon signs | Da, Engelberg & Gao; the StockTwits literature | §0.3 — no tone number may stand in for attention |
