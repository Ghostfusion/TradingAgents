# NewsScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md).

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

Status: **design (2026-09-17). Not started. This engine ships last.** Five of its
nine categories are **ABSENT** and two more are partial (§1) — a partial engine
that prints its coverage is the only honest form it can take today.

---

## 0. What this engine answers, and what it must not become

### 0.1 The owner's weight table

| Category | Weight | Status today |
| --- | --: | --- |
| News relevance / materiality | **20%** | **PARTIAL** — relevance is scored, **materiality is not** |
| News novelty | **15%** | **PARTIAL** — syndication dedupe exists, no novelty score |
| Fundamental impact | **20%** | **ABSENT** — no revenue- or margin-impact producer |
| Earnings / guidance news | **15%** | **PARTIAL** — surprise yes, guidance no |
| Corporate events | **10%** | **PARTIAL** — SEC form typing only |
| Regulatory / legal | **5%** | **PARTIAL** — a litigious word count |
| Analyst / rating changes | **5%** | **PARTIAL** — the revision index is flag-gated and **bound to the fundamentals toolset** |
| Macro / industry | **5%** | **PARTIAL** — macro context yes, industry shock no |
| News persistence | **5%** | **PARTIAL** — decay maths exists behind flags, unwired |

**4 of 9 categories have a computed input; the other five do not**, and the
largest single weight (20%, fundamental impact) has **no producer at all**.

### 0.2 Relevance is not materiality — quoted from the code

`news_relevance.score_news_article:53`'s docstring (`news_relevance.py:56`) reads
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
   `sentiment._normalise_headline:604` used for syndication dedupe).
2. **Coverage level is itself a factor.** Stocks with *less* media coverage have
   historically earned *higher* subsequent returns (the neglected-firm effect,
   strongest where information asymmetry is greatest). This means the **volume**
   of coverage is not a bullish input — the opposite of the intuition a "news
   score" invites. The engine's `mention_volume:43` (unwired) is a coverage
   measure, and its sign must be decided, not assumed.
3. **Management guidance changes carry incremental information and drift.**
   Guidance is currently **ABSENT** from the engine while being one of the
   better-documented news factors — which is why it is listed as a build item
   rather than a refinement.
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
| relevance & materiality | 20 | **PARTIAL** | `news_relevance.score_news_article:53` | `{"score", "reasons"}` | higher = more relevant | 0-100 floor-clamped | Scores relevance only; NO materiality term |
| → relevance (ticker/name/official) | — | SCORABLE | `news_relevance.score_news_article:53` | `score` | higher = more relevant | 0-100 | weights: code-title +55/snippet +34/url +18; name-title +45 (+26 amb)/snippet +28/+16; official +8; macro -12 |
| → materiality | — | **ABSENT** | — | — | — | — | no magnitude/size/impact input anywhere |
| novelty | 15 | **PARTIAL** | `sentiment._normalise_headline:604` + dedupe in `sentiment.aggregate_weighted_sentiment:616` | drops dupes; no novelty key | n/a | n/a (count of survivors) | syndication dedupe exists, no novelty score emitted; gated by `enable_weighted_sentiment_agg` (default False) |
| fundamental impact | 20 | **ABSENT** | — | — | — | — | no revenue/margin-impact producer |
| → revenue-impact estimate | — | ABSENT | — | — | — | — | grep `revenue_impact|impact_estimate` = 0 hits |
| → margin-impact estimate | — | ABSENT | — | — | — | — | grep `margin_impact` = 0 hits |
| earnings & guidance | 15 | **PARTIAL** | see sub-rows | — | — | — | surprise yes, guidance no |
| → earnings surprise | — | SCORABLE | `events.surprise_score:17` (surfaced by `analysis_tools.get_earnings_surprise:1474`, `get_earnings_event_read:535`; rows via `catalyst.last_earnings_surprise:70`) | return str `last_surprise/side/date` | higher = beat | signed ratio `(actual-estimate)/|estimate|` | — |
| → guidance change | — | **ABSENT** | — | — | — | — | no guidance field; `get_earnings_calendar:30` carries EPS estimate only |
| corporate events | 10 | **PARTIAL** | `sec_edgar.get_sec_filings:109` + `_FORM_LABELS:36` | form-type label | n/a (fact) | label only | only SEC form typing ("8-K (material event / M&A / guidance)"); rest is LLM prose |
| → M&A / partnership / contract / product | — | ABSENT | — | — | — | — | no classifier; prompt tells analyst not to over-read 8-K (`news_analyst.py:102`) |
| → dividend / buyback announcement | — | PARTIAL | `moomoo_extra_tools.get_dividends:150`, `get_corporate_actions:131`, `market_position_tools.get_share_buyback_authorization:49` | facts, not score | n/a | amounts/dates | remaining buyback authorization explicitly unavailable (`market_position_tools.py:112`) |
| → bankruptcy / distress | — | PARTIAL | `analysis_tools.get_analyst_verdict:1383` (Altman Z, Ohlson O, Zmijewski, trap-risk) | `altman_z/ohlson_o/zmijewski_x/trap_risk` | higher Z = safer (distress = Z low) | model scores | statement-driven, not news-driven |
| regulatory & legal | 5 | **PARTIAL** | `text_factors.lm_tone:121` (litigious count) | `litigious` | higher = more legal language | raw word count | no legal/regulatory event classifier; count only, no scale |
| → regulatory action | — | ABSENT | — | — | — | — | grep `regulatory_action` = 0 |
| analyst & rating changes | 5 | **PARTIAL** | `analyst_data_tools.get_analyst_ratings:10`; `analyst_revision_tools.get_analyst_revision_index:43` → `analyst_revisions.revision_ratio:79`/`revision_index:279` | rating trend + PT consensus; index ratio | index >0 = net upgrades | ratio (weighted up/down) | revision index flag-gated default False; bound to fundamentals NOT news |
| → price-target revision | — | **PARTIAL** | `analyst_revisions.estimate_change_index:176` | `index=None` + reason | — | — | always `unavailable` — engine holds no 3-4q estimate history |
| macro & industry | 5 | **PARTIAL** | `macro_data_tools.get_macro_indicators:9`; `analysis_tools.get_macro_regime_read:6492`, `get_credit_spread_read:4782`, `get_taylor_read:2866` | macro series / label | macro context | mixed (levels, bps, label) | no per-name macro-sensitivity or industry-shock producer |
| → industry shock | — | ABSENT | — | — | — | — | `get_market_breadth:98` = breadth, not industry shock |
| persistence | 5 | **PARTIAL** | `sentiment.decayed_weight:91`, `sentiment.aggregate_weighted_sentiment:616` (half-life), `sentiment.mention_volume:43` | decay factor / mention ratio | higher ratio = hotter | 0.5^(age/HL); ratio >=1 | `mention_volume`, `sentiment_velocity` have no callers |
| → news volume acceleration | — | UNWIRED | `sentiment.mention_volume:43` (also `sentiment_velocity:25`) | none | higher = accelerating | ratio | exported at `sentiment.py:825`; grep finds no caller |
| → repeated-news decay | — | PARTIAL | `sentiment.decayed_weight:91` | weight | higher = fresher | half-life days (default 7.0) | used in `weighted_sentiment:109`; article-level half-life only under flag |

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
| `analysis_tools.get_news_sentiment_series:6793` | news_tools :352 (also market_tools :279) | score/-1..1 + SMA + innovation + article count | Yes |
| `analysis_tools.get_earnings_event_read:535` | news_tools :371 | surprise% + side + print-day move/vol + PEAD verdict | Yes |
| `analysis_tools.get_earnings_surprise:1474` | fundamentals_company_tools :392 | last surprise% + side + date | Yes |
| `analysis_tools.get_analyst_verdict:1383` | fundamentals_company_tools :391 | value/trap/distress screens (EY, F, M, Altman Z, Ohlson O, Zmijewski) | Yes |
| `analysis_tools.get_sec_filings:141` | news_tools :360 | recent filings by form type (8-K/10-K/10-Q/S-1/13D) | Yes |
| `analysis_tools.get_beat_miss_sizing:2252` | news_tools :372 | position multiplier from beat/miss side + catalyst | Yes |
| `analysis_tools.get_macro_regime_read:6492` | news_tools :355 | single label Risk-On / Liquidity-Contraction / Stagflation | Yes |
| `analysis_tools.get_credit_spread_read:4782` | news_tools :374 | HY/CCC/BB OAS band + de-risk scale | Yes |
| `analysis_tools.get_taylor_read:2866` | news_tools :366 | Taylor implied rate + tight/easy/neutral | Yes |
| `analyst_data_tools.get_analyst_ratings:10` | fundamentals_company_tools :386 | recommendation trend + price-target consensus | Yes (not in news set) |
| `analyst_data_tools.get_earnings_calendar:30` | news_tools :359 | next earnings date + EPS est/actual + surprise_pct | Yes |
| `analyst_revision_tools.get_analyst_revision_index:43` | fundamentals_company_tools :393 | weighted up/down revision ratio | Gated `enable_analyst_revision_index` (default False) → DISABLED sentinel |
| `moomoo_extra_tools.get_corporate_actions:131` | fundamentals_company_tools :389 | dividends + splits | Yes |
| `moomoo_extra_tools.get_dividends:150` | fundamentals_company_tools :390 | dividend rows (declaration/ex/pay) | Yes |
| `market_position_tools.get_share_buyback_authorization:49` | fundamentals :362 | trailing buyback/repurchase rows; authorization = unavailable | Yes |
| `quant_formula_tools.get_disclosure_tone:379` | news_tools :361 | LM tone counts + readability + filing-vs-news gaps | Yes (litigious channel only) |
| `macro_data_tools.get_macro_indicators:9` | news_tools :354 | FRED macro series | Yes |

---

## 3. Defects and dead seams

1. **Relevance score is computed but not surfaced automatically.** `get_news_relevance_read:57` returns `Relevance score: X/100`, and `news_analyst.py:46` instructs the analyst to cite it — but there is no report-disclosure/attribution block emitting it. A reader sees the score only when the model volunteers it; every grep for `relevance` outside the tool/strategy found no report-side consumer. (Disagreement pair: `news_data_tools.py:80` vs the absence of any report renderer.)
2. **`mention_volume:43` and `sentiment_velocity:25` are exported with no caller.** `sentiment.py:824-825` lists them in `__all__`; repo-wide grep finds only the definitions and the docstring mention. The "news volume acceleration" component has a producer that nothing reads → UNWIRED.
3. **`estimate_change_index:176` can never return a value.** Its own docstring/basis says the engine holds "current consensus and price targets only, not a 3-4 quarter estimate history"; `get_analyst_revision_index:43` therefore always prints the estimate-change leg as `unavailable`. The price-target-revision component has a producer shape with no data behind it.
4. **Revision index mis-homed.** `get_analyst_revision_index` (the only analyst-change score) is bound in `fundamentals_company_tools` (`toolsets.py:393`), not `news_tools()` — the NewsScore engine cannot reach it through the news analyst.
5. **Flag-gated producers.** `aggregate_weighted_sentiment` (novelty dedupe + decay) is reachable only via `_sentiment_agg_rows:6734` behind `enable_weighted_sentiment_agg=False` (`default_config.py:1044`); `enable_weighted_sentiment_window=False` (`:1049`); `enable_news_relevance=False` (`:903`). Default runs emit none of the novelty/persistence math.
6. **Materiality is not scored, only relevance.** `score_news_article:55` docstring: "Deterministic relevance score (0-100) + <=5 explainable reasons." The return is `{"score": round(score,1), "reasons": reasons[:5]}` built solely from lexical match flags (code/name presence, official host, macro term). There is no magnitude, dollar, %move, or event-severity term — so the owner's "materiality" half of the 20-point component is unimplemented, and a reader today would see a high relevance score for a trivial press mention and (wrongly) read it as material.

---

## 4. What is ABSENT, and the smallest honest producer

| ABSENT/PARTIAL | Data needed | Already fetched anywhere? | Smallest honest producer |
| --- | --- | --- | --- |
| materiality | event magnitude (dollar value, % move, volume multiple, market cap) | Partially: `get_earnings_event_read` has print-day move + volume ratio; no generic event magnitude | A materiality term = |expected/implied move| × event class weight, computed from existing `catalyst.implied_move_from_history:111` + volume ratio |
| novelty | article timestamps + near-duplicate key | YES: AV `time_published`, yfinance `pubDate/providerPublishTime`, GDELT `seendate`, EODHD `date`, NewsAPI `publishedAt`; dedupe key `_normalise_headline:604` | Count of not-yet-seen headline keys in the lookback window / total articles (0-1), reusing `_normalise_headline` + `seen` set in `aggregate_weighted_sentiment:616` |
| revenue-impact estimate | analyst estimate delta / guidance delta | No | Wrap `get_analyst_revision_index` ratio; refuses without estimate history (as `estimate_change_index` already does) |
| margin-impact estimate | margin guidance / cost shock | No | ABSENT — no source; label a constant, do not fabricate |
| guidance change | company guidance vs prior guidance | No (`get_earnings_calendar:30` = EPS only) | None honest; SEC 8-K label is the only inkling |
| M&A / partnership / contract / product | event-type classification of article/filing text | Only SEC form label `_FORM_LABELS:36` | Extend `_FORM_LABELS` typing + a keyword classifier over `get_news` output; must print basis |
| management change | executive-change feed | No | ABSENT |
| regulatory action | regulator/action feed | No | ABSENT |
| price-target revision | historical PT series | `get_analyst_ratings:10` gives current consensus only | Snapshot PT consensus daily and diff; not available now |
| industry shock | sector-wide event/peer-move read | `get_market_breadth:98` (breadth), `sector_rotation_screen` | Sector-relative abnormal move over the news window |
| news volume acceleration | per-day article counts | YES: `daily_sentiment_sma` carries `n` per day; `mention_volume:43` already computes the ratio | Wire `sentiment.mention_volume` to the `n` series from `get_news_sentiment_series` |

**Relevance-vs-materiality, quoted:** the function's docstring (`news_relevance.py:56`) reads "Deterministic relevance score (0-100) + <=5 explainable reasons", and it returns `{"score": round(score, 1), "reasons": reasons[:5]}` (`:93`). Every point is a lexical/membership flag (code-in-title +55, company-name +45, official +8, macro -12). It measures *whether the article is about this ticker from a credible source*, not *how much it moves the fundamental*. `is_official:48`, `admit_article:97` and `degrade_triple:108` are all in the same module (`news_relevance.py`). The analyst leaf is `get_news_relevance_read` (`news_data_tools.py:57`, bound in `news_tools()` at `toolsets.py:350`); the score is printed by the leaf and the prompt asks the analyst to cite it (`news_analyst.py:46`), but nothing in the report assembly prints it — so today it is in the report only when the LLM includes it.

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
   `sentiment.aggregate_weighted_sentiment:616` (§0.3).
7. **Its own band table**, advisory, feeding nothing (master rule 2).
8. **Nothing here sizes or gates.** `get_beat_miss_sizing:2252` keeps its own
   path; `NewsScore` never feeds it.

### 5.1 Build order (value ÷ effort)

| Order | Item | Why |
| --: | --- | --- |
| 1 | **Novelty** (15%) | known recipe (Tetlock similarity-to-prior-stories), data present, sign known |
| 2 | **Materiality** (half of 20%) | the largest weight currently has no producer; a move-based estimate is derivable from `catalyst.implied_move_from_history:111` + the print-day volume ratio |
| 3 | **Persistence / volume acceleration** (5%) | `mention_volume:43` and `decayed_weight:91` already exist — wiring, not building |
| 4 | **Corporate-event typing** (10%) | extend `sec_edgar._FORM_LABELS:36` and add a keyword classifier over `get_news` output, printing its basis |
| 5 | **Guidance change** (part of 15%) | needs a data source the engine does not have; do not fake it from the EPS estimate |
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

## 7. Open questions

**Status 2026-09-17:** the questions the implementation plan raised are
answered - see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13 (twelve
decisions). The marked ones below are **closed**; the unmarked ones remain open
and are listed in that section's §13.3.


1. **Which sign for coverage?** `mention_volume:43` is a coverage measure; the
   neglected-firm evidence says low coverage has historically meant *higher*
   forward returns. The owner's "news volume acceleration" implies high = good.
   These conflict, and the resolution decides the persistence category's direction. **CLOSED 2026-09-17 (plan §13 Q9): the neglected-firm sign** - lower abnormal coverage is the positive signal; do not reverse it into an attention-is-good factor.
2. **Is materiality a news property or an event property?** A magnitude estimate
   is arguably `EventScore`'s (it owns the expected move). If so, this category
   should read EventScore's number rather than build a second one — which is exactly the "one number, one producer" rule. **CLOSED 2026-09-17 (plan §13 Q6): `EventScore` owns it; this engine consumes that number.**
3. **Where does the analyst-revision index live?** It is currently bound to the
   fundamentals toolset (`toolsets.py:393`) while this engine's 5% category needs
   it. Either the news surface gains the leaf, or the category is dropped and the weight redistributed. **CLOSED 2026-09-17 (plan §13 Q4): the binding moves; the category keeps its weight.**
4. **Should `NewsScore` be per-name at all**, or is it a market-level flow
   measure? Most of the owner's categories are name-level; the macro/industry
   ones are not.
5. **Does the report print a per-article relevance list** (an attribution block),
   or only the aggregate? Today the score reaches the report only when the LLM
   volunteers it (defect 1 in §3).

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| **Staleness** = textual similarity to the previous ten stories about the firm; returns respond less to stale news, and stale-news days negatively predict the next week's return (overreaction that reverses) | Tetlock (2011), *All the News That's Fit to Reprint* | §0.4 point 1 and §5.1 item 1 — novelty is the highest-value build, with a known sign |
| **Low media coverage** predicts *higher* subsequent returns (neglected-firm effect), strongest where information asymmetry is high | Fang & Peress (2009) | §0.4 point 2 and §7 Q1 — coverage is not bullish by default |
| Management guidance changes carry **incremental** information, with post-guidance drift | the guidance literature | §0.4 point 3 — guidance is a real factor and currently ABSENT |
| Fresh, salient news is incorporated immediately; stale or competing information drifts | Barber & Odean (attention); the limited-attention reading of PEAD | §0.2 — why "count positive/negative headlines" is the wrong shape |
| Attention and tone are different signals with **opposite** short-horizon signs | Da, Engelberg & Gao; the StockTwits literature | §0.3 — no tone number may stand in for attention |
