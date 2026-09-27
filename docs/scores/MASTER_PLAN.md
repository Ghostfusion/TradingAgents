# MASTER_PLAN — the set-wide implementation plan

**Part of the score-engine design set: [`README.md`](README.md)** (master design).
Every document in this directory has its own account; this one is the **work
order** across all of them.

**Scope: every document in `docs/scores/`** — the master (`README.md`), the build
order (`IMPLEMENTATION_PLAN.md`), the wiring and contract documents
(`ResearchLayerWiring.md`, `ScoreContextContract.md`), Phase C's live panel
(`MEASUREMENT_FINDINGS.md`), the engine documents
(`FundamentalScore.md`, `TechnicalScore.md`, `RegimeScore.md`, `RiskScore.md`,
`NewsScore.md`, `SentimentScore.md`, `EventScore.md`), the designed-not-built
engines (`MarketScore.md`, `ValuationScore.md`), the composite
(`CompositeTradeScore.md`) and the survey (`ScoreUniverse.md`).

Status: **a plan, nothing started.** No item here has been implemented unless §3.1
says so, and the items marked `DECISION` cannot start at all until the owner
answers §2. Every item was verified against the working tree this round by six
readers, one per document group; each row names the document that records it and
the check that proves it done.

---

## 0. How to read this plan

### 0.1 The ordering rule

Items carry **D** (difficulty) and **I** (impact), 1-5, judged by the reader who
verified them and justified in its report:

* **D** — how much code, measurement or owner decision the item needs.
* **I** — how much it changes what the system *decides or reports*. An item that
  changes a printed number, a gate, a size or a published score is 4-5; an item
  that adds a diagnostic nobody reads is 1.

Phases are **bands of that ordering**, not themes: Phase 0 is the easiest and
least consequential work in the set, Phase 7 the hardest and most consequential.
Within a phase, rows are ordered by D then I. The exception is §2: owner
decisions are cheap to take (D 1-2) and block the most work, so they are listed
first and marked as gates wherever they appear.

### 0.2 Three kinds of item

| Kind | Meaning | Who can start it |
| --- | --- | --- |
| `WORK` | Code or measurement that can start today | anyone |
| `DOC` | A claim in a document that the tree contradicts | anyone |
| `DECISION` | An owner answer; no code may precede it | the owner |

### 0.3 What is deliberately *not* here

The six readers checked every document's open items against the tree and found
**roughly sixty** that are presented as open but are already implemented, or that
the document itself closed. They are listed, with evidence, in the readers'
reports (§12 names the pattern and the biggest classes): the Donchian and
Parabolic-SAR flags, the momentum multi-horizon whitelist, the semivariance
producer, the `regime_label` chop branch, the gap-fill constants, Dechow-Dichev's
caller, the novelty producer, `mention_volume`/`sentiment_velocity` callers, the
sentiment toolset, the confirmation quadrant, the scale pin, the
`engine_score_tools` bindings (deleted, which *is* the resolution), Level 2's
report render, `WP-12`'s wiring, the panel's `INSUFFICIENT_CROSS_SECTION` label,
and Phase C's four recorded defects. **A document that presents one of these as
open is a `DOC` item** — correcting it is Phase 0 work, not new work.

### 0.4 The readers, and how to audit them

| Reader | Documents |
| --- | --- |
| `PlanMasterAndPlan` | `README.md`, `IMPLEMENTATION_PLAN.md` |
| `PlanWiringAndContext` | `ResearchLayerWiring.md`, `ScoreContextContract.md` |
| `PlanTechnicalRegimeRisk` | `TechnicalScore.md`, `RegimeScore.md`, `RiskScore.md` |
| `PlanFundamentalNewsSentiment` | `FundamentalScore.md`, `NewsScore.md`, `SentimentScore.md` |
| `PlanEventMarketValuation` | `EventScore.md`, `MarketScore.md`, `ValuationScore.md` |
| `PlanCompositeUniverseMeasure` | `CompositeTradeScore.md`, `ScoreUniverse.md`, `MEASUREMENT_FINDINGS.md` |

Each report carries four sections — items, already-done rows, cross-document
contradictions and defects — and every row names its verification. Where this plan
compresses several items into one row, it keeps their ids so the source row can be
found.

---

## 1. The phases at a glance

| Phase | Theme | D | I | Items | Gate before it starts |
| --- | --: | --: | --: | --: | --- |
| **0** | **Truth first** — correct the claims the tree contradicts | 1 | 1-2 | 24 `DOC` | none |
| **1** | **Wire what exists** — ratios, leaves and readers over data already fetched | 1-2 | 1-3 | 41 `WORK` | none |
| **2** | **Small new producers** over data already fetched | 2-3 | 2-4 | 44 `WORK` | none |
| **3** | **The measurement layer** (Phase C) — the evidence that promotes any weight | 2-4 | 3-5 | 12 `WORK` | Phase 1's panel wiring |
| **4** | **Contract repairs** — one number, one producer, on the report surface | 2-3 | 3-4 | 9 `WORK` | none (but each changes printed output) |
| **5** | **Data- and vendor-blocked work** | 3-4 | 1-3 | 14 `WORK` | the named source |
| **6** | **Owner decisions** — the gates §2 | 1-5 | 2-5 | 21 `DECISION` | none |
| **7** | **What the decisions unlock** — new engines and new objects | 4-5 | 4-5 | 14 `WORK` | the matching decision |

Counting note: an item that spans two documents is counted once, in the phase its
difficulty and impact put it in, with both sources named.

---

## 2. The decision gates

Nine decisions block work elsewhere. The first five block the most.

| # | Decision | Blocks | Source |
| --: | --- | --- | --- |
| **D1** | `MarketScore` ↔ `TechnicalScore`/`RegimeScore`: who owns momentum, relative strength, volatility, breadth and market regime (invariant 8 cannot satisfy both readings) | MKT-4, MKT-6, MKT-7, MKT-8, MKT-9..MKT-14 — the whole engine | `MarketScore.md` §7 Q1; `README.md` §1.1 |
| **D2** | `ValuationScore` ↔ `FundamentalScore.valuation_subscore`: absorb VS, layer over it, or same object under two names | VAL-2..VAL-6, VAL-8..VAL-20; `FUND-20` | `ValuationScore.md` §7 Q1; `FundamentalScore.md` §4.4 |
| **D3** | The composite's **shape**: keep the weighted mean with `K` at 0.20, or move risk to a multiplier (reading (a) `K` leaves the legs; reading (b) keep-and-multiply, which invariants 11/15 forbid) | CTS-9; the printed block; invariant 18 | `CompositeTradeScore.md` §6 Q1 |
| **D4** | Does **any survey system become a tenth engine**? If yes it needs a gate, a leaf, an `ENGINE_GATES`/`ENGINE_TOOLS` entry, a `default_config.py` key, a doc and the five web-app surfaces | every `UNIV-*` gap's *form*; UNIV-NEWENGINE | `ScoreUniverse.md` §8 Q5 |
| **D5** | **Coverage / `N` deflation**: does coverage deflate the number (a multiplier), or stay a printed qualifier the reader applies? | CTS-3, MF-7; the "reader must see both" rule | `CompositeTradeScore.md` §6 Q3 |
| **D6** | The **meta layer**: a cross-engine agreement read, and the multi-model consensus/dispersion pair | UNIV-AGREE, UNIV-META, UNIV-MODELCONS, CTS-8/UNIV-CONVICTION | `ScoreUniverse.md` §8 Q3–Q4 |
| **D7** | `MomentumScore` (core, no library) vs `MarketScore` (library, not one of the 24 names) — the core slot for the stock's own market behaviour | UNIV-MOMSLOT; D1 | `ScoreUniverse.md` §8 Q6 |
| **D8** | Does fresh **intraday event information** modify sizing, and under what latency/data-quality contract? | EVT-6 | `EventScore.md` §8 |
| **D9** | Do the seven engine renderers' and `basis` tails' **frozen strings** change (D3's freeze reasoning applied to them)? | RLW-3 | `ResearchLayerWiring.md` §9.2 |

**One decision is recorded but unresolved in a second place:** the note's V1
seven-engine vector (CTS-7) cannot be adopted as written — it weights
`ValuationScore` (no producer), `EventScore` (no composite by decision) and
`Sentiment` (which the note's own Layer-2 list drops, against invariant 17).

---

## 3. Phase 0 — truth first (`DOC`, D1, I1-2)

The six readers found **twenty-four** claims that the tree contradicts, several of
them in the same document as their own correction. These are the cheapest items in
the plan and the only ones that cost nothing but attention.

### 3.1 Corrected in this round (done, kept for the record)

| Item | Fix |
| --- | --- |
| Two `## V.` headings in `complete_report.md` — the advisory engine-detail block and the Portfolio Manager decision both claimed section V | The detail block is now `## IVc. Engine score detail (advisory)`, beside `IVa`/`IVb`; the decision keeps `V`. Fixed with a failing-first test (mutation proved, source restored byte-identical) |
| `docs/design_security_context.md` §20.3 counted the gate registry against 88 keys (now 112) and 40 rows (now 64) | Dated `[CORRECTED 2026-09-26]` marker with the re-counted numbers; the unregistered 48 is unchanged |
| `README.md` §3.2 defects 3, 4 and 5 — the Donchian flags, the PSAR flag and `net_beta` | Dated `[CORRECTED 2026-09-26]` markers: the first two are fixed and the callers prove it (§3.1 agrees); the third is a missing **writer**, not a missing producer — the engine computes a book beta and the executor's `BookState` never receives it |
| `CompositeTradeScore.md` §3.5/§6 Q3 cited "decision 12" for the coverage question | Corrected in place: the panel's coverage question is owner Q4's label plus that document's own Q3; `IMPLEMENTATION_PLAN.md` §13 Q12 is the semivariance measure |

### 3.2 To correct

| id | Item | Source |
| --- | --- | --- |
| DOC-1 | The Donchian breakout is **reachable**: `donchian_channel` takes `closes` and callers pass it. `README.md` §3.2 defect 3 and `ScoreUniverse.md` §3/§7 still say `None` with no caller; the residual gap is only that `technical_score`'s breakout category does not consume the value | `README.md` §3.2, §3.1; `ScoreUniverse.md` §3, §7 |
| DOC-2 | `TechnicalScore.md` §1 records the **pre-fix** `0.5` vol percentile as current (`regime.vol_percentile` returns `None`); its own §8.4 #5 flags this | `TechnicalScore.md` §1, §8.4 |
| DOC-3 | `TechnicalScore.md` §1 lists upside/downside **semivariance ABSENT** and momentum multi-horizon **UNWIRED**; both are built (`volatility_models.semivariance:68`; `analysis_tools.py:2433`) | `TechnicalScore.md` §1 vs §8.1 |
| DOC-4 | `TechnicalScore.md` §3 defect 9 (dead chop branch) and §1's gap-fill "hardcoded" row are fixed; the doc carries both readings | `TechnicalScore.md` §1, §3 |
| DOC-5 | `EventScore.md` §3 D4/D5 present two fixed defects as open; §7 Q1 ("no 0-100 `EventScore`") contradicts the code, which returns a 0-100 score with equal weights | `EventScore.md` §3, §7, §9 |
| DOC-6 | `EventScore.md` says "4 of 7 families" in its status line and "5 of 7" in §9; `FAMILY_AVAILABILITY` has five `SCORABLE` | `EventScore.md` status, §9 |
| DOC-7 | `README.md` §3.5 **D-10 is fixed** (the structured debate's consensus exit now writes and reads `independent_agreement`) and §7's "`WP-12`, which is not yet built" is stale (the scorecard reaches four analyst prompts, `report_hygiene`, `structured_debate` and `agent_states`) | `README.md` §3.5, §7 |
| DOC-8 | `IMPLEMENTATION_PLAN.md` §15's P0-2 row still says the panel's fundamentals leg is EODHD bulk fundamentals; §3.2 and the code say SEC EDGAR XBRL | `IMPLEMENTATION_PLAN.md` §3.2, §15 |
| DOC-9 | `ScoreContextContract.md` still specifies `engine_score_tools` (`toolsets.py:450/460`) as a live binding and says `format_engine_detail`'s Level 2 "remains unbuilt"; the symbol was deleted in Phase 2 and Level 2 is built in two surfaces | `ScoreContextContract.md` §2/§3/head |
| DOC-10 | `ScoreContextContract.md`'s prose cites `ENGINE_SECTIONS` at `:119`; its own table says `:127` (correct) | `ScoreContextContract.md` §2 |
| DOC-11 | `FundamentalScore.md` §3.6 says Dechow-Dichev is "not in Phase A … unreachable"; §1.4 #4 marks it fixed and the tree agrees | `FundamentalScore.md` §1.4, §3.6 |
| DOC-12 | `FundamentalScore.md` §1.3 conflates two line references (`gross_margin` vs `working_capital`); §4.4 C12 names one `NA` factor where three are `NA` | `FundamentalScore.md` §1.3, §4.4 |
| DOC-13 | `NewsScore.md` §0.1/§1/§4 and `news_score.py:94` say guidance is "no guidance source"; `benzinga_tools.get_guidance_revisions` exists behind `enable_benzinga_surface` | `NewsScore.md` §0.1, §1, §4 |
| DOC-14 | `NewsScore.md` §1's "UNWIRED" rows (novelty, volume acceleration) are stale; §8.4 says so itself | `NewsScore.md` §1, §8.4 |
| DOC-15 | `SentimentScore.md` §0.3/§1/§4 say the quadrant and the abnormal-return read "do not exist"; §8.1 §99/§100 say built, and the tree agrees | `SentimentScore.md` §0.3, §1, §4, §8.1 |
| DOC-16 | `SentimentScore.md` §0.1/§4 list the 20-day sentiment delta as a hole; §7 Q4 closed it (the regression slope is canonical) | `SentimentScore.md` §0.1, §4, §7 |
| DOC-17 | `SentimentScore.md` §2 says no sentiment toolset exists and `analyst_toolset` raises `KeyError`; `toolsets.py:523/577` | `SentimentScore.md` §2, §7 |
| DOC-18 | `SentimentScore.md` §3 numbers two consecutive defects "4." | `SentimentScore.md` §3 |
| DOC-19 | `CompositeTradeScore.md` §3.5/§6 Q3 cite "decision 12" for coverage deflation; `IMPLEMENTATION_PLAN.md` §13 Q12 is the semivariance measure — the reference dangles | `CompositeTradeScore.md` §3.5, §6 |
| DOC-20 | `README.md` §3.1 defect 5 says `net_beta` has "neither producer nor reader"; the engine produces it (`book_risk.net_beta:177`) and the executor field is simply never written — the split is unstated | `README.md` §3.1; `ScoreUniverse.md` §4 |
| DOC-21 | `MEASUREMENT_FINDINGS.md` §1 still says `regime.vol_percentile` returns `0.5` (**the owner's document** — report, do not edit) | `MEASUREMENT_FINDINGS.md` §1 |
| DOC-22 | `TechnicalScore.md` §1's volatility row, `MEASUREMENT_FINDINGS.md:126`'s "not measured" rows, and the `Strategies/scores/*.md` library-internal defects (TECH-25/26, REG-21/22, RISK-25/26, EVT-7's doc side) are the **owner's** files: report only | several |

---

## 4. Phase 1 — wire what exists (`WORK`, D1-2, I1-3)

Everything here reads data the repo already fetches; the producer or the key
exists and no reader uses it. No new vendor, no new measurement.

| id | Item | Source | D | I | Verification |
| --- | --- | --- | --: | --: | --- |
| PLAN-3 | Ship the producer-owned `opportunity_score_reason` string beside `opportunity_score: null` | `IMPLEMENTATION_PLAN.md` §6/§9, `README.md` §7 Q1 | 1 | 2 | a grep for the key in `tradingagents/` and a run's `research_decision.json` |
| SENT-14 | Delete or wire the three dead sentiment helpers (`weighted_sentiment`, `blended_score`, `consensus_verdict`) | `SentimentScore.md` §3 | 1 | 1 | callers exist, or the symbols are gone |
| TECH-1 | Return the OBV **level** `obv_divergence` computes and discards | `TechnicalScore.md` §8.1 §47/§48 | 1 | 1 | the level is non-None on a 30-bar series |
| TECH-2/3/4 | Five-day momentum (`roc(closes,5)`), range/position depth (time since high, distance from low, position in range), SMA20/SMA100 | `TechnicalScore.md` §1, §8.1 §101/§103/§104 | 1 | 1 | the named outputs are non-None on a 250-bar series |
| NEWS-15 | Decide the flag policy for the default-off news/sentiment producers (`enable_weighted_sentiment_agg`, `enable_weighted_sentiment_window`, `enable_news_relevance`, `enable_crowd_ratio_bands`) | `NewsScore.md` §3 defect 5 | 1 | 2 | an owner sentence, or the flags flipped under a labelled dark-launch diff |
| FUND-4 | Cash-flow family: OCF yield, FCF margin, FCF/NI, FCF/EBITDA, OCF/EBITDA, CapEx/OCF, EV/FCF, OCF/NI growth divergence | `FundamentalScore.md` §3.6 ranks 4+7 | 1 | 3 | `ratios.py` gains the keys; a leaf prints them |
| FUND-1 | Interest coverage and the debt-service family from `interest_expense` (an alias with **zero** consumers) | `FundamentalScore.md` §3.6 rank 1 | 2 | 3 | a grep for `interest_coverage` |
| FUND-5 | Leverage family: net debt/EBITDA, debt/assets, net debt/FCF, cash/debt, net cash yield, OCF/debt | `FundamentalScore.md` §3.6 rank 5 | 2 | 3 | shares one EBITDA helper with FUND-1 |
| FUND-2 | Level ROIC, invested-capital turnover and a capital-employed definition (`invested_capital` is built; only incremental ROIC is exposed) | `FundamentalScore.md` §3.6 rank 2 | 3 | 4 | a level `roic` producer + leaf |
| FUND-21 | Supply `dcf_upside` + `dcf_confidence_value` on the live leaf so the built confidence-scaled DCF factor enters VS (defect D-4) | `FundamentalScore.md` §3.4, §4.1 | 2 | 3 | the leaf passes both; VS carries the factor |
| FUND-3 | Buyback yield and total shareholder yield from `share_buybacks` (a second alias with no reader), with a stated net-issuance sign | `FundamentalScore.md` §3.6 rank 3 | 3 | 2 | a consumer exists; a leaf prints the yield |
| FUND-6 | Expose gross margin and the EBIT-margin series; add the margin-stability legs | `FundamentalScore.md` §3.6 rank 6 | 2 | 2 | `gross_margin` is rendered somewhere |
| FUND-8 | Normalized-FCF yield, FCF-stability σ, cash-conversion stability | `FundamentalScore.md` §3.6 rank 9 | 2 | 2 | `normalized_cycle_fcf` gains `std`; a leaf prints the yield |
| FUND-9 | Numeric asset/debt/receivables/inventory growth and WC/assets (exist only as booleans) | `FundamentalScore.md` §3.6 rank 10 | 2 | 2 | greps for the four names |
| FUND-22 | Declare the six Insider Activity factors in `FACTOR_SCHEMA`/`SUBSCORE_FACTORS`, or drop the category (declared at `factor_schema.py:50`, fed by nothing — defect D-16 in `ScoreUniverse.md`) | `FundamentalScore.md` §2.10 | 2 | 2 | `_spec` rows carrying the category, or its removal |
| NEWS-4 | Feed `corporate_events` from SEC form typing (`sec_edgar._FORM_LABELS` is already the declared producer; the leaf never supplies it — defect D-2) | `NewsScore.md` §5.1, §8.4 | 2 | 3 | the component stops printing absent |
| SENT-1 | Supply `bull_share` from the per-article scores the aggregation already holds | `SentimentScore.md` §1, §4 | 2 | 3 | the breadth category stops printing NA |
| SENT-2/SENT-4 | Supply `inst_flow_z` (the Q2 canonical measure; the leaf is already bound to the sentiment surface) | `SentimentScore.md` §1, §4, §7 Q2 | 2 | 4 | the 15-weight institutional category measures |
| SENT-5 | Supply the options components (`iv_skew`, `put_call_ratio`) and/or an options-sentiment composite | `SentimentScore.md` §1 | 3 | 3 | the options category stops printing NA |
| SENT-3 | Wire the short-interest percentile/change basis from the settlement series already returned | `SentimentScore.md` §1, §4 | 2 | 2 | `short_pct_float` stops printing NA |
| SENT-13 | Fix `_sentiment_factor_read`: remove the hardcoded `eodhd` source and either drop or rename the single-name self-correlation labelled `rank_ic` (defect D-7) | `SentimentScore.md` §3 defects 6-7 | 3 | 3 | a test on the degraded path and the statistic's name |
| SENT-12 | Normalise or refuse the GDELT −100..100 series on the **legacy** leaves (the engine pins the unit; these paths do not — defect D-6) | `SentimentScore.md` §3 defect 2 | 2 | 3 | the leaves emit a unit-scale series or refuse to mix |
| NEWS-3 | Wire the guidance-change component now that a source exists (`benzinga_tools.get_guidance_revisions:34`) | `NewsScore.md` §0.1, §4, §8.2 | 2 | 3 | the component stops printing NA |
| NEWS-8 | News-volume **acceleration** (first difference), distinct from the level ratio now wired | `NewsScore.md` §4, §8.2 | 2 | 2 | a flat count series scores 0 acceleration |
| NEWS-14 | Emit the per-article relevance/materiality evidence block | `NewsScore.md` §3 defect 1 | 2 | 2 | the rendered block carries the relevance line |
| REG-1 | Replace the 3-valued `vol_pct` proxy in `build_strategy_overlays` with a measured percentile (defect: `vol_pct ∈ {0.1, 0.5, 0.9}`) | `RegimeScore.md` §3 defect 2 | 2 | 3 | a synthetic vol ramp yields distinct labels |
| REG-2 | Make the volatility estimator move the **label**, not only `position_scale` | `RegimeScore.md` §3 defect 4 | 2 | 2 | the estimator changes the label, or the doc says scale-only |
| REG-3 | Make the realized-vol percentile granular (overlapping windows; drop the self-inclusive rank floor) | `RegimeScore.md` §3 defect 5 | 2 | 2 | the printed `vol_pct` can fall below ~0.067 |
| README-5 | Same as REG-3, seen from the master's §3.2 tail | `README.md` §3.2 | 2 | 2 | a test over a fixture where the two window counts differ |
| RISK-2 | Portfolio concentration scalar over position weights (reuse the HHI formula) | `RiskScore.md` §4 | 2 | 3 | a portfolio HHI, not a holder HHI |
| RISK-6 | Fix `get_tail_risk` passing a **close-price series** as an equity curve to `cdar` — the printed CDaR is not the book's | `RiskScore.md` §3.6 | 3 | 3 | the input is a labelled equity proxy or the tool says which book |
| RISK-1 | De-duplicate the cash-sleeve/equal-weight/normalise rules re-implemented in `book_risk.portfolio_cvar` and `book_risk.book_correlated_stress` | `RiskScore.md` §3.7 | 3 | 2 | one shared helper |
| RISK-4 / PLAN-7 | Wire `book_risk.net_beta` into the executor's book builder so `BookState.net_beta` is populated (the field is declared and never written) | `RiskScore.md` §1/§3.3; `IMPLEMENTATION_PLAN.md` §5.4 | 2 | 2 | an assignment at a `BookState(...)` site |
| TECH-6/TECH-9/TECH-11/TECH-16 | Make `_macd_hist` public and add line/signal/hist + slopes; wire a per-signal mean-reversion z; volume spike/trend/breakout ratio; MACD crossover and histogram acceleration | `TechnicalScore.md` §1, §8.1 | 2 | 2 | the named leaf outputs exist |
| EVT-5 | Raise `catalyst.next_earnings`' `lookahead_days` above the 60-day read horizon (the fetch already spans +95d) | `EventScore.md` §4 | 1 | 1 | the read returns >60d |

---

## 5. Phase 2 — small new producers (`WORK`, D2-3, I2-4)

Data is already fetched; the producer does not exist.

| id | Item | Source | D | I | Verification |
| --- | --- | --- | --: | --: | --- |
| UNIV-PTARGET | `(target − price)/price` and a target-price dispersion read from the vendor target triple (fetched and only printed) | `ScoreUniverse.md` §7 | 1 | 2 | a producer + an `NA` test |
| UNIV-INSIDER | `IBS = buys/(buys+sells)` and a historical-average transaction size from the Form-4 counts | `ScoreUniverse.md` §7 | 2 | 2 | a producer + a no-trades `NA` test |
| UNIV-ADLINE | Cumulative A/D line and a market-wide Zweig thrust over the same breadth panel | `ScoreUniverse.md` §7 | 2 | 3 | a producer + a known-series test |
| REG-5/REG-6 | Same two readings, from `RegimeScore.md`'s §8.1 §10.2/§11 | `RegimeScore.md` §8.1 | 2 | 2 | a cumulative series producer |
| TECH-14 | Zweig breadth thrust as a `technical_score` component | `TechnicalScore.md` §8.1 §120 | 2 | 2 | a thrust producer over the panel |
| TECH-7/TECH-12 | Bollinger-bandwidth family (`BBW`, percentile, squeeze, expansion) and the Keltner/Bollinger squeeze-momentum | `TechnicalScore.md` §8.1 §21-§25, §109/§110 | 2 | 2 | a BBW producer + percentile |
| TECH-10/TECH-15/TECH-18 | Breakout persistence/false flags; the regression family (R², trend quality, channel, trend-to-noise); candle/gap depth | `TechnicalScore.md` §8.1 §43/§44, §74-§79, §66-§69 | 3 | 2 | named producers exist |
| TECH-19 | The per-stock relative-strength-vs-sector-ETF leg (the owner decided the sector ETF is primary) | `TechnicalScore.md` §1 | 3 | 3 | a leaf returns `relative_strength_vs_sector` |
| TECH-23 | Indicator-redundancy control, technical state enum, acceleration and disagreement — §0.4/§6.5 call redundancy **mandatory** before the weights are trusted | `TechnicalScore.md` §8.1 §127/§129-§131 | 3 | 3 | a redundancy producer + the four readers |
| REG-4 | SPY/QQQ/IWM index-trend producers (only one benchmark exists; market-level trend is a prerequisite to not being a second TechnicalScore) | `RegimeScore.md` §1/§4 | 2 | 3 | three separately-printed index reads |
| REG-7..REG-15, REG-18 | Breadth/participation, correlation and concentration, upside/downside beta, the market-stress composite, cross-asset spreads, interaction terms, the trend/vol/breadth/liquidity composites, the statistical-inference family | `RegimeScore.md` §8.1 | 3 | 2 | each has a named producer |
| REG-16 | Surface the HMM transition probability / expected duration (the matrix is computed and never reaches the score; a state/meta output, not a weight) | `RegimeScore.md` §8.1 §46/§47/§51 | 3 | 3 | a printed transition probability |
| REG-17 | The confidence/state metadata block (entropy, confidence, stability, change, velocity, acceleration, surprise) — emitted **beside** the score | `RegimeScore.md` §8.1 §49-§56, §96-§102 | 4 | 3 | the block is emitted |
| RISK-5 | Top |GEX| strikes as explicit price levels with distance-to-spot | `RiskScore.md` §1 | 3 | 2 | a producer returns named levels |
| RISK-7/RISK-12 | Portfolio correlation-risk scalar (the owner pinned the notional **share** proxy) | `RiskScore.md` §4 | 3 | 3 | a scalar producer with a stated scale |
| RISK-10/RISK-11/RISK-13..RISK-24 | The σ20/σ60 ratio, downside/upside beta, Sterling, the loss-frequency family, momentum reversal, stop-hit probability, `P(R<0)`, cash runway, FX exposure, commodity beta, tail-adjusted return, the nonlinear penalty, liquidity-adjusted CVaR | `RiskScore.md` §8.2 | 2-3 | 1-2 | each has a named producer |
| FUND-14 | Robust (median/MAD) z-score primitive | `FundamentalScore.md` §4.1 §23 | 2 | 2 | one function, no `1.4826` today |
| FUND-19 | Earnings-yield-over-bonds spread (one owner call on which engine owns the leg) | `FundamentalScore.md` §4.1 §14 | 2 | 2 | a leaf prints the spread |
| FUND-15 | Cross-metric agreement / factor-score dispersion | `FundamentalScore.md` §4.1 §36 | 3 | 2 | a dispersion producer |
| FUND-27 | Resolve the Merton distance-to-default inputs and the balance-sheet liquidity-stress leg | `FundamentalScore.md` §2.9 | 3 | 2 | the function is callable from a leaf |
| NEWS-7 | Industry-shock leg (sector-relative abnormal move over the news window) | `NewsScore.md` §4, §8.2 | 3 | 2 | a sector-relative move, not breadth |
| NEWS-10 | The persistence quantity the library names (positive-period share, multi-λ decay) | `NewsScore.md` §8.2 | 3 | 2 | a component over the series |
| NEWS-11 | A first-class NewsConfidence output (sample size / Wilson / Bayesian), distinct from coverage | `NewsScore.md` §8.1, §8.4 | 3 | 3 | a `confidence` field that is not `coverage` |
| NEWS-12/NEWS-13 | Multi-horizon blend; IC-derived component weights instead of the hardcoded table | `NewsScore.md` §8.1, §8.4 | 4 | 2-3 | distinct horizon scores; a measured vector |
| SENT-6 | Crowd bands as percentile-over-own-history, keeping 40/60 as the documented fallback | `SentimentScore.md` §7 Q5 | 3 | 2 | a percentile path with configurable thresholds |
| SENT-8 | Sentiment dynamics: second difference, AR(1) φ / half-life, mean-reversion speed, persistence coefficient | `SentimentScore.md` §8.2 | 3 | 2 | producers over the existing series |
| SENT-10 | Relative normalisation set: robust z, percentile, sentiment β, asymmetry split, event study | `SentimentScore.md` §8.2 | 3 | 3 | one producer per transform |
| SENT-7 | Raw-NLP layer (negation window, intensifier, subjectivity/uncertainty, aspect taxonomy) — the largest ABSENT cluster | `SentimentScore.md` §8.2 | 4 | 3 | a negation-adjusted intensity |
| SENT-9 | Volume/attention set: `N_eff` (Kish), HHI, Gini, source breadth/independence | `SentimentScore.md` §8.2 | 4 | 2 | one producer per measure |
| SENT-11 | Uncertainty models and the output map (entropy/Bayesian/Kalman/HMM; Φ/logistic/tanh; `Confidence`) | `SentimentScore.md` §8.2 | 5 | 3 | one model + one transform |
| FUND-18 | Turnover/working-capital family: DIO, DSO, DPO, the turnover ratios and the cash-conversion cycle | `FundamentalScore.md` §4.1 §6 | 4 | 2 | a CCC producer |
| FUND-16 | Fundamental momentum, acceleration and factor-level stability | `FundamentalScore.md` §4.1 §26-§28 | 4 | 3 | a weighted Δ-factor composite |
| FUND-13 | Take the percentile **within sector**, or keep the renamed "peer median" band as the stated policy | `FundamentalScore.md` §3.2, §4.4 C6 | 3 | 3 | a test asserting the reference set |
| NEWS-5 | A regulatory/legal event classifier, or explicitly drop the 5% category | `NewsScore.md` §4, §8.2 | 4 | 2 | a scaled read, or a weight redistribution |
| NEWS-9 | Novelty embedding forms, the duplicate-suppression weight and the novelty products | `NewsScore.md` §8.2 | 4 | 3 | a similarity measure + a weighted novelty |
| FUND-23 | The value screener's Return-on-Capital and Shareholder-Yield screens (needs FUND-2/FUND-3) | `FundamentalScore.md` §1.4, §2.8 | 3 | 1 | both columns print |
| EVT-9 | Measure EventScore (built, "unmeasured"): both gates on, then the Phase C panel | `EventScore.md` §9 | 3 | 3 | a measured panel row |
| MKT-13 | MarketScore's remaining ranked producers: ADV/dollar volume, beta compression and correlation regime, Bollinger bandwidth series, the conditional-deviation label | `MarketScore.md` §3 ranks 8-12 | 3 | 2 | one test per producer |
| VAL-10/VAL-15/VAL-12/VAL-13/VAL-14/VAL-17 | ValuationScore's cheap ranks: EBITDA yield and net-debt/EBITDA; EV/assets and EV/invested capital; the peer-relative z + sector-neutral rank; the historical premium gap; implied WACC/growth/margin bisections; owner earnings and shareholder yield | `ValuationScore.md` §3 ranks 2-9 | 1-3 | 2-3 | one producer per rank, `NA`-honest |

---

## 6. Phase 3 — the measurement layer (Phase C) (`WORK`, D2-4, I3-5)

Nothing promotes a weight, a status or a composite rung without this phase. It is
the plan's spine: `RESEARCH_ONLY` is the state of every vector until a measurement
exists.

| id | Item | Source | D | I | Verification |
| --- | --- | --- | --: | --: | --- |
| MF-1 / PLAN-1 | Run the **wide** SEC EDGAR XBRL panel across the date range so the fundamental factors stop reading `n_measured: 0` (one wide date exists: 286 names, EDGAR basis, 221 with fundamentals) | `MEASUREMENT_FINDINGS.md` §4/§7; `IMPLEMENTATION_PLAN.md` §3.2 | 2 | 5 | `n_measured > 0` with a panel label of `OK` |
| PLAN-4 | Build `scripts/score_panel_eval.py` — the caller that runs `alpha_health.score_evaluation_rows` plus the multiple-testing machinery over the panel | `IMPLEMENTATION_PLAN.md` §7 | 3 | 3 | the script exists and prints the full row set |
| PLAN-6 / MF-3 | Emit the **sector and regime robustness** splits the WP-10 deliverable names (the panel records them as unimplemented) | `IMPLEMENTATION_PLAN.md` §7; `MEASUREMENT_FINDINGS.md` §5 | 3 | 3 | both splits present |
| MF-2 | Measure the FCF-yield cluster, the valuation category and the growth category once MF-1 exists | `MEASUREMENT_FINDINGS.md` §2/§4 | 2 | 4 | the redundancy matrix reports `n_pairs > 0` |
| MF-6 | Act on the measured momentum redundancy (8 pairs at |ρ| ≥ 0.80; `williams_r` ≡ `stoch_k`): reduce to one oscillator and one MA-regime leg, or record why not — this edits a **declared** owner table | `MEASUREMENT_FINDINGS.md` §2 | 2 | 4 | a revised `CATEGORY_WEIGHTS` with a record, or an owner sentence declining |
| MF-4 | Produce readable weight vectors for the engines that have none (`fundamental_score` prints equal 1/4 unvalidated; `news_score`/`regime_score` print no table) | `MEASUREMENT_FINDINGS.md` §4 | 3 | 4 | a measured table or a WP-10 record per vector |
| MF-5 | Measure the remaining 9 of 11 `news_score` components on the live per-symbol path | `MEASUREMENT_FINDINGS.md` §4 | 3 | 3 | a live run reporting 11 measured, or a named reason each |
| MF-8 | Give `risk_score`/`sentiment_score` a panel path, or record permanently that their inputs are book- and vendor-read-only | `MEASUREMENT_FINDINGS.md` §4 | 4 | 3 | panel rows, or an owner sentence closing it |
| TECH-24 | Measure the pairwise correlation of `technical_score`'s nine category sub-scores over the panel (50% of the weight sits on correlated inputs) | `TechnicalScore.md` §6.5 | 4 | 3 | a reported correlation matrix |
| FUND-24 | Promote the four sub-score weights and the composite out of `RESEARCH_ONLY` via the evidenced ladder | `FundamentalScore.md` §3.1 | 5 | 5 | a measured vector + OOS evidence → `VALIDATED` |
| PLAN-5 | Land a gate-on tree on which `report_verify.py` and `verify_sweep.py` both exit 0 on `CONFIRMED` (Phase A's last clause) | `IMPLEMENTATION_PLAN.md` §9 | 3 | 3 | both scripts exit 0 |
| RLW-4 | Measure, validate and promote the composite's vector so `Movement` can leave `UNAVAILABLE` (the store and the rule are built; no run reaches `VALIDATED`) | `ResearchLayerWiring.md` §4.3/§7.1 | 4 | 3 | `scorecard_status(...)["movement"] != "UNAVAILABLE"` |

---

## 7. Phase 4 — contract repairs on the report surface (`WORK`, D2-3, I3-4)

Each of these changes what a reader sees. They are ordered after the cheap wiring
because they touch printed output, and before the new engines because every new
engine inherits the same surface.

| id | Item | Source | D | I | Verification |
| --- | --- | --- | --: | --: | --- |
| RLW-2 | Make `engine_score_block` read the run's one snapshot instead of re-calling the engine leaf — it is currently a **second producer** of a number the scorecard block already supplies, and the two can disagree in one prompt | `ResearchLayerWiring.md` §3.1/§3.4 | 3 | 4 | no `_call_engine` from the block; the prompt's number equals the snapshot's |
| RLW-1 | Render the per-analyst engine section from the same view the card and §V use, so an enabled EventState cannot read `NA` in one section and measured in another | `ResearchLayerWiring.md` §4.2 | 2 | 3 | one number across the card and both report surfaces |
| SCC-5 | Remove the second render of one engine in `complete_report.md` (the per-analyst section and §V both print it) | `ScoreContextContract.md` §12 #8 | 2 | 2 | each engine named once |
| RLW-5 | Stop gating the scorecard's human surface on the unrelated string `"Trade plan card"` (a run without that card loses the scorecard from the report) | `ResearchLayerWiring.md` §1.2/§3.1 | 1 | 2 | the scorecard renders without the card |
| NEWS-1 | Consume EventScore's materiality number as the `materiality` component (the consumption side is built; the producer is EventScore's) | `NewsScore.md` §4, §7 Q6 | 3 | 4 | the 20-weight component stops printing NA |
| — | Give `news_score` the `categories` key both renderers read (defect D-1: `news_score()` never returns it, so the per-category breakdown is silently empty in the tool output and `run_card.json`) | `NewsScore.md` §3; defect D-1 | 2 | 3 | `res["categories"]` exists and the renderers print rows |
| — | Attach a reason to every component `_render_news_score` lists under "absent (NA with a reason, never 0)" (defect D-10) | `NewsScore.md` §3; defect D-10 | 1 | 2 | every absent component prints its reason |
| — | Fix the two mislabelled producer strings (`crowd_ratio` "0-100 ratio/percentile" — no percentile path exists; `persistence` citing a `decayed_weight` half with no call site) | defects D-9 | 1 | 2 | the strings match the producers |
| — | Render `net_debt` with the library's sign in the one leaf a reader compares (defect D-8: `analysis_tools.py:2879` prints `cash − debt`) | defect D-8 | 1 | 2 | the leaf prints `debt − cash` or labels the convention |

---

## 8. Phase 5 — data- and vendor-blocked (`WORK`, D3-4, I1-3)

Listed so the block is explicit rather than forgotten. Each row names the source
that would unblock it; three of them are **closed by the producer's own
statement** that no vendor publishes the input.

| id | Item | Blocked by | Source |
| --- | --- | --- | --- |
| UNIV-IVRANK | IV rank (min-max) | no per-day IV history source — the leaf prints `n/a` for exactly this reason | `ScoreUniverse.md` §7 |
| UNIV-ETFFLOW | ETF net flow / creation-redemption | "no vendor here publishes either" (`sector_screener.ETF_VOLUME_NOTE:888`) | `ScoreUniverse.md` §7 |
| UNIV-MOAT | Moat legs beyond the loss-of-moat proxy | "not available from the vendors" (`value_dip.py:964`) | `ScoreUniverse.md` §7 |
| UNIV-GOV | Board independence, related-party, auditor, turnover, compensation | filing-block parsing | `ScoreUniverse.md` §7 |
| UNIV-MODELCONS | Multi-model consensus/dispersion | no ensemble of independent model scores exists to feed it | `ScoreUniverse.md` §7 |
| EVT-3 | Court-decision forward calendar | the chosen source is a filing archive with backward-looking date fields only; `court_calendar_rows` returns `None` always | `EventScore.md` §4 |
| EVT-7 | EventScore's 92 ABSENT library sections (magnitude, hazard, market-reaction battery, base rates, quality composites) | mostly analyst estimates and forward probabilities the repo does not fetch | `EventScore.md` §9 |
| VAL-18 | SOTP / liquidation / NAV / replacement cost | no segment-level fair values or appraisals in the vendor chain | `ValuationScore.md` §3 rank 10 |
| VAL-16 | CAPE / Shiller P/E | needs a new series producer + CPI deflation (a data-path decision first: VAL-7) | `ValuationScore.md` §3 rank 8 |
| FUND-17 | R&D / intangible-investment set | a stacked R&D series | `FundamentalScore.md` §4.1 §12 |
| FUND-10 | Deferred-revenue growth and debt-maturity risk | a canonical deferred/unearned key; a maturity-wall feed | `FundamentalScore.md` §2.6/§2.9 |
| RISK-3/RISK-8/RISK-9 | Gap fill probability and days-to-fill calibration | a stored gap-fill outcome sample (the constants are already labelled fallbacks) | `RiskScore.md` §4 |
| RISK-19 | Revenue and geographic concentration | a segment-revenue store | `RiskScore.md` §8.2 §50/§51 |
| REG-19 | MOVE / Treasury-volatility source | an external MOVE source or a DGS10 realised-vol proxy | `RegimeScore.md` §4 |
| NEWS-2/NEWS-6/NEWS-16 | Fundamental-impact surprises, price-target revisions, the estimate-level series | an estimate history (revenue/margin consensus, a persisted PT series, 3-4 quarters of estimates) | `NewsScore.md` §4, §8.2 |
| MKT-* | MarketScore's panel-dependent components | the cross-sectional universe decision (MKT-4) — the library's own warning is that a percentile over nine names is not a decile | `MarketScore.md` §7 Q4 |

---

## 9. Phase 6 — the owner decisions (`DECISION`)

§2 lists the nine gates. The remaining decisions are cheaper and narrower:

| id | Item | D | I | Source |
| --- | --- | --- | --: | --: | --- |
| UNIV-NAMES | Do the tree's names follow the survey (`EarningsScore`, `FlowScore`, …), or do the tree's component names stand with the survey names treated as families? | 1 | 1 | `ScoreUniverse.md` §8 Q7 |
| UNIV-DILOWN | Which survey section owns dilution (§18/§24/§25) and buyback yield (§18/§26); is Piotroski's `f_eq` re-pointed or kept as a cross-check? | 1 | 2 | `ScoreUniverse.md` §8 Q2 |
| CTS-2 | Is a second, research-side `OpportunityScore` object wanted — under a name distinct from the executor's `opportunity_score` slot? | 1 | 2 | `CompositeTradeScore.md` §6 Q2 |
| MKT-3 | The acceptance criterion for MarketScore: "every §1 section built or declared out of scope" vs "the nine subscores exist" | 1 | 4 | `MarketScore.md` §7 Q3 |
| VAL-3 | The coverage floor for ValuationScore's composite | 1 | 2 | `ValuationScore.md` §7 Q3 |
| VAL-2 | ValuationScore's research-allocation weight (7.5% carved from Fundamental, or a seventh line that breaks the 100% sum) | 1 | 3 | `ValuationScore.md` §7 Q2 |
| VAL-4 | Does `dcf_upside` stay caller-supplied in VS, or does ValuationScore become its producer? | 2 | 2 | `ValuationScore.md` §7 Q4 |
| VAL-5 | Who owns the historical-position quantity (`ValuationScore` or `FundamentalScore.val_z`)? | 2 | 3 | `ValuationScore.md` §7 Q5 |
| VAL-6 | ValuationScore's confidence output shape (a second published score, a sub-field, or out of scope) | 2 | 3 | `ValuationScore.md` §7 Q6 |
| MKT-5 | Ownership of short interest, IV percentile/implied move, insider flow and gaps — each already has a home | 2 | 3 | `MarketScore.md` §7 Q5 |
| MKT-8 | One convention per quantity: RS as a return difference or a ratio; realized vol annualised or window-summed; the conditional-deviation vs semivariance label | 2 | 3 | `MarketScore.md` §7 Q8 |
| MKT-6 | Per-name, market-wide, or both — the scope contract mirroring RiskScore's book/engine split | 2 | 4 | `MarketScore.md` §7 Q6 |
| MKT-7 | MarketScore's weight and gate (research-only, or a composite participant with `enable_market_score`) | 2 | 4 | `MarketScore.md` §7 Q7 |
| MKT-2 | Does market-wide breadth belong to MarketScore or to `RegimeScore`? | 3 | 4 | `MarketScore.md` §7 Q2 |
| CTS-5 | Are interaction terms `γᵢⱼ` in scope, or does the composite stay additive? | 5 | 3 | `CompositeTradeScore.md` §6 Q5 |
| CTS-6 | A distinct `CompositeAlphaScore`, under a non-colliding name? (its inputs are what Phase C measures) | 5 | 4 | `CompositeTradeScore.md` §6 Q6 |
| CTS-7 | Is the note's V1 seven-engine vector withdrawn, or proposed as a replacement? (it cannot be adopted as written) | 5 | 4 | `CompositeTradeScore.md` §6 Q7 |
| README-3 | Build a `RegimeConfidence` 0-1 output, or record the explicit refusal of the fourth output type | 2 | 2 | `README.md` §1.4 |
| RLW-3 | Do the seven renderers' and `basis` tails' frozen strings change? (D3's freeze reasoning) | 1 | 2 | `ResearchLayerWiring.md` §9.2 |
| SCC-4 | Should `analyst_forced_tools` be a guaranteed default rather than the owner's local `.env` setting? | 1 | 2 | `ScoreContextContract.md` §3.2 |
| PLAN-9 | The sentiment-score anchor fallback when the computed block is absent (statement-based vs source-derived) — deliberately deferred until a live case occurs | 2 | 1 | `IMPLEMENTATION_PLAN.md` §13.4 |
| PLAN-8 | Run a reproducer on the two surviving DISCLOSED-vendor-pair flags, then widen the detector or clear them | 2 | 2 | `IMPLEMENTATION_PLAN.md` §13.4 |
| PLAN-11 | Regenerate the nine still-marked poisoned trees now, or keep them "on demand" | 2 | 1 | `IMPLEMENTATION_PLAN.md` §13.4 |
| REG-20 | Liquidity-conditions composite weights — "report the components, do not invent an index" | 2 | 2 | `RegimeScore.md` §4 |
| TECH-25/TECH-26/REG-21/REG-22/RISK-25/RISK-26 | Correct the library-internal defects and library-vs-code contradictions in the owner's `Strategies/scores/*.md` (duplicate formulas, mislabels, three mutually inconsistent composites) | 1 | 1 | the engine docs' §8.3/§8.4 |

---

## 10. Phase 7 — what the decisions unlock (`WORK`, D4-5, I4-5)

| id | Item | Depends on | D | I |
| --- | --- | --- | --: | --: |
| MKT-9 | Build the `MarketScore` module over the component dicts through `score_engine.combine` (no new fetch) | D1, MKT-3 | 4 | 4 |
| MKT-10/MKT-11/MKT-12/MKT-14 | Its component list, the promoted distance-from-high and RS-vs-sector fields, the robust z and market-wide numeric breadth, and its nine §6 verification tests | MKT-9 | 3-4 | 3-4 |
| VAL-8 | Build the `ValuationScore` module (`{score, confidence, components, coverage, withheld}`) with its proposed gate behind `enable_quant_scorecard` | D2 | 4 | 4 |
| VAL-9 | The dispersion/confidence function over the ≥2 intrinsic values the repo already produces (the library's stated core requirement) | D2 | 2 | 4 |
| VAL-11/VAL-20 | Print coverage + floor beside the score; implement the ten §6 verification requirements | VAL-8 | 1-3 | 3 |
| CTS-1/CTS-9 | Land the decided composite shape and the six verification requirements §5 states (attribution recomputes the score; `NA ≠ 0`; no config promotes; coefficients need a record; one direction convention; the gate boundary untouched) | D3 | 2-3 | 3-5 |
| CTS-8 / UNIV-CONVICTION | Build `Conviction` as a **separate** object (`BaseSignal × DataConfidence × Agreement × Risk/100`), with `BaseSignal` explicitly not `TradeScore` and the risk leg corrected from the survey's `1 − Risk` | D6, UNIV-AGREE | 5 | 4 |
| UNIV-AGREE | `engine_agreement(scores)` over the engine vector, refusing below two measured engines and never returning 0 for `None` | D6 | 3 | 4 |
| UNIV-NEWENGINE | Whatever system the owner promotes becomes a tenth engine: gate, leaf, `ENGINE_GATES`/`ENGINE_TOOLS` entry, `default_config.py` key, doc, and the five web-app surfaces | D4 | 5 | 5 |
| FUND-11/FUND-12 | The `EffectiveWeight` chain (base table, sector applicability, stability multiplier, redundancy penalty) and the A/B/C/D confidence grades | FUND-24, FUND-12's agreement leg | 5 | 4 |
| FUND-7 | Extend the annual series producer with EPS/FCF/EBITDA/EBIT/book-value keys and wire the SEC XBRL depth into the CAGR path (the CAGR family and the G- and O-legs stay blocked otherwise) | MF-1 | 4 | 4 |
| PLAN-2 | The ten ranked FundamentalScore factors the plan defers to "the next pass" | PLAN-1 for the deep ones | 4 | 3 |
| README-6 | Replace or de-gate the single-name self-correlation `rank_ic` in `_sentiment_factor_read` and drop the hardcoded `source="eodhd"` (same object as SENT-13, from the master's §5.6) | — | 3 | 2 |
| README-7 | Give the three zero-consumer canonical keys (`interest_expense`, `share_buybacks`, `debt_repayment`) a consumer, or delete them from the vocabulary | FUND-1, FUND-3 | 3 | 3 |
| TECH-22/TECH-21/TECH-13 | Per-name ADV participation; the legacy oscillators (DPO, Ultimate, Awesome, RVI, Coppock, EOM); ATR depth | — | 3 | 1-2 |
| EVT-1 | Supply a per-family impact/severity weight vector for the 0-100 score the code emits with equal weights, **or** decide to remove the score and keep only the structured state | — | 4 | 4 |
| EVT-6 | Intraday event-risk sizing: a separately authorised sizing input with a max-age, provenance, idempotency and fail-closed contract — or explicitly nothing | D8 | 5 | 4 |

---

## 11. The critical path

1. **Phase 0** first, always: several Phase 1 items are invisible while the
   document that names them says they are already fixed (DOC-1, DOC-2, DOC-3).
2. **Phase 1 → Phase 3**: the panel work (MF-1) is the gate for every weight,
   status and composite rung. `PLAN-4` (the eval caller) and `MF-1` (the wide
   panel) unlock `MF-2`, `MF-4`, `MF-6`, `FUND-24`, `RLW-4` and `PLAN-2`.
3. **The five decisions (D1-D5) should be taken early even though they are
   listed in Phase 6**, because each blocks a whole engine or object: D1 blocks
   all fourteen `MKT-*` build items, D2 blocks the eleven `VAL-*` items, D3
   blocks the composite's shape and its printed block, D4 decides whether the
   survey's gaps become engines or components, D5 decides the coverage contract.
4. **Phase 4 before Phase 7**: every new engine renders through the same report
   surface, so the second-producer seams (RLW-2, RLW-1, SCC-5) should be fixed
   while there are seven engines rather than eight or nine.
5. **Phase 5 is a waiting room, not a queue.** Three of its rows are closed by the
   producer's own statement that no vendor publishes the input; they should be
   recorded as `unavailable` with that reason rather than left as gaps.

---

## 12. Exit criteria per phase

| Phase | Done when |
| --- | --- |
| 0 | Every claim in §3.2 either corrected in the document that makes it, or marked as the owner's file and reported. The check is a re-read of the named section against the named symbol |
| 1 | Every item's verification column passes: a grep finds the consumer, or a leaf prints the number. No new vendor call and no new measurement is introduced by this phase |
| 2 | Each new producer returns a number or `None` with a reason, has a test, and names its source data in its docstring. None of them changes a gate, a size or a published composite |
| 3 | The panel reports per-factor IC / rank IC / ICIR / decile spread / monotonicity / turnover / persistence / OOS / redundancy, with the sector and regime splits, over a panel wide enough for a percentile to mean something. Every vector it touches either gains a record or stays `RESEARCH_ONLY` with the reason printed |
| 4 | One engine, one number, one render: the prompt block, the per-analyst section, the card and §V all print the same value for the same engine, and each engine appears once in `complete_report.md` |
| 5 | Each row either has its source, or carries the producer's own sentence saying the source does not exist — recorded in the document that asks for it |
| 6 | The owner has answered §2 and §9. No code precedes an answer |
| 7 | The unlocked object exists with its gate off by default, its verification tests from its own document, and its five web-app surfaces in the same round |

---

## 13. What is *not* in this plan

The readers' "already done, or not an item" sections list roughly sixty claims the
tree contradicts in the *other* direction — documents presenting as open what is
implemented. The largest classes:

* **The six defects fixed in `2c05701`/`ba50b5f`** (Donchian and PSAR flags, the
  dead chop branch, the value-area accumulator, `support_structure`'s branch,
  `atr`'s `0.0`, the sector percentile's `0.0`) — `README.md` §3.1-§3.2, and
  `TechnicalScore.md` §1/§3 still carry some of them as open (DOC-1, DOC-4).
* **The wiring workstreams**: `momentum_multihorizon`, `mention_volume`,
  `sentiment_velocity`, the sentiment toolset, the confirmation quadrant, the
  scale pin, Dechow-Dichev's caller, `rrg_heading`/`msi_zone`'s missing callers
  (advisory reads by design), `engine_score_tools` (deleted — the deletion *is*
  the resolution), Level 2's report render.
* **The measurement layer's four recorded defects** (`MEASUREMENT_FINDINGS.md`
  §6), all fixed failing-first.
* **Decisions already taken**: `opportunity_score` stays `null`; EventScore has no
  composite; the event/risk key disjointness; the two expected-move producers
  (canonical + fallback); per-name *and* market-level event scope; the calendars'
  separate gate; `analyst_forced_tools`' default; the sentiment momentum slope
  (no second 20-day delta); the sentiment score never sizing.
* **The thirteen items this round already fixed**: the two `## V.` headings
  (§3.1), the five stale printed provenance strings, and the 378 drifted
  `module.symbol:LINE` citations across these documents.

---

## 14. The defects this round found

Ten code defects, each verified against the tree. One is fixed (§3.1); the rest
are items above, with their ids.

| # | Defect | Item |
| --: | --- | --- |
| 1 | `news_score()` never returns the `categories` key **both** renderers read, so the per-category breakdown is silently empty in the tool output and `run_card.json` | Phase 4 |
| 2 | `news_score.COMPONENTS["corporate_events"]` names `sec_edgar._FORM_LABELS` as its producer and the only leaf never supplies it | NEWS-4 |
| 3 | Seven `sentiment_score.COMPONENTS` are declared with named producers and never supplied by the only assembly function (11 of 18 supplied) | SENT-1..SENT-5 |
| 4 | The live `FundamentalScore` leaf never supplies `dcf_upside`/`dcf_confidence_value`, so the confidence-scaled DCF factor is dead on the production path | FUND-21 |
| 5 | Three `FACTOR_SCHEMA` factors are declared `availability=NA` although their producers exist and are leafed — the printed coverage denominator overstates what the engine could measure | Phase 2 (with FUND-2) |
| 6 | The legacy GDELT route still mixes scales: a GDELT `sma_7d` is ~100× an EODHD one on those leaves | SENT-12 |
| 7 | `_sentiment_factor_read` hardcodes the EODHD source and labels a single-name self-correlation `rank_ic` | SENT-13 |
| 8 | `net_debt` is printed with the opposite sign to the library's definition in the one leaf a reader compares | Phase 4 |
| 9 | Two mislabelled producer strings (`crowd_ratio`'s "0-100 ratio/percentile"; `persistence`'s uncalled `decayed_weight` half) | Phase 4 |
| 10 | `_render_news_score` labels its absent list "NA with a reason" and lists components that carry none | Phase 4 |

Two further findings that are **not** defects: `book_risk.net_beta` has a producer
and no executor writer (RISK-4/PLAN-7), and `overlays`' 3-valued `vol_pct` is a
recorded limitation (REG-1).

---

## 15. Cross-document contradictions the readers found

These are the ones that would mislead a reader of the set today. Each is a Phase 0
item or a note on the item it affects.

| Contradiction | Both sides |
| --- | --- |
| The Donchian breakout | `README.md` §3.1 "fixed" vs §3.2 "unreachable"; `ScoreUniverse.md` §3 repeats the stale side |
| `net_beta` | `README.md` §3.1 "fixed" (the default) vs `ScoreUniverse.md` §4 "a dead field"; the truth is a producer with no executor writer |
| `WP-12` | `README.md` §7 "not yet built" vs `IMPLEMENTATION_PLAN.md`'s own workstream naming and the wired tree |
| The wide panel | `MEASUREMENT_FINDINGS.md` §4 "no wide panel run has been done yet" vs one 286-name EDGAR-basis date on disk |
| The panel's fundamentals leg | `IMPLEMENTATION_PLAN.md` §3.2 (SEC XBRL) vs §15's P0-2 row (EODHD bulk) |
| Level 2's render | `ScoreContextContract.md` "remains unbuilt" vs `ResearchLayerWiring.md` §4.2 "BUILT, in two surfaces" |
| The structured debate's consensus exit | `ResearchLayerWiring.md` §6 D-10 "open" vs the tree, which writes and reads the key |
| The EventState seam | the card's docstring ("the card's row is the number `event_state` carries") vs the report section's ("the report's number and the prompt's number cannot disagree") — together they say the report tree and the card disagree |
| Guidance as a news source | `NewsScore.md` "no guidance source" vs `benzinga_tools.get_guidance_revisions` behind a gate |
| Sentiment's holes | `SentimentScore.md` §0.1/§4 vs its own §7 Q4 (the slope is canonical) and §8.1 §99/§100 (built) |
| "decision 12" | `CompositeTradeScore.md` §3.5 vs `IMPLEMENTATION_PLAN.md` §13 Q12 (the semivariance measure) |

---

## Appendix A — item index by document

| Document | Item ids |
| --- | --- |
| `README.md` | README-1..README-7, DOC-1, DOC-7, DOC-20, DOC-3 (via TechnicalScore) |
| `IMPLEMENTATION_PLAN.md` | PLAN-1..PLAN-11, DOC-8, DOC-19 |
| `ResearchLayerWiring.md` | RLW-1..RLW-5, DOC-9 |
| `ScoreContextContract.md` | SCC-4, SCC-5, DOC-9, DOC-10 |
| `MEASUREMENT_FINDINGS.md` | MF-1..MF-8, DOC-21 (owner's document — report only) |
| `TechnicalScore.md` | TECH-1..TECH-26, DOC-2..DOC-4 |
| `RegimeScore.md` | REG-1..REG-22, DOC-22 |
| `RiskScore.md` | RISK-1..RISK-26 |
| `FundamentalScore.md` | FUND-1..FUND-27, DOC-11, DOC-12 |
| `NewsScore.md` | NEWS-1..NEWS-15, DOC-13, DOC-14 |
| `SentimentScore.md` | SENT-1..SENT-15, DOC-15..DOC-18 |
| `EventScore.md` | EVT-1..EVT-9, DOC-5, DOC-6 |
| `MarketScore.md` | MKT-1..MKT-14 |
| `ValuationScore.md` | VAL-1..VAL-20 |
| `CompositeTradeScore.md` | CTS-1..CTS-9, DOC-19 |
| `ScoreUniverse.md` | UNIV-* (24 systems), DOC-1 |

## Appendix B — the nine gates, and what each unblocks

D1 MarketScore boundary → 14 items · D2 ValuationScore boundary → 11 · D3
composite shape → the printed block + invariant 18 · D4 the tenth engine → every
`UNIV-*` gap's form · D5 coverage deflation → the coverage contract · D6 the meta
layer → agreement + Conviction · D7 the momentum slot → D1 · D8 intraday event
sizing → EVT-6 · D9 frozen renderer strings → RLW-3.

---

## Related documents

* [`README.md`](README.md) — the master design; §2.1's invariants are the
  constraints every item here must respect.
* [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — the original build order
  (WP-0..WP-11, Phases 0/A-E). This plan does not replace it: it covers the
  documents written after it and the items it leaves open.
* [`ScoreUniverse.md`](ScoreUniverse.md) §7 and [`CompositeTradeScore.md`](CompositeTradeScore.md)
  §4/§6 — the cost tables and questions this plan phases.
* [`MarketScore.md`](MarketScore.md) §7 and [`ValuationScore.md`](ValuationScore.md)
  §7 — the two boundary decisions that gate the most work.
