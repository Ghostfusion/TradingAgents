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
**All nine were answered by the owner on 2026-09-26** — the answers are §2.1 and
the questions they answer are kept verbatim in §2.2 as the record. Nothing in this
plan now waits on an owner decision except the narrower §9 rows.

### 2.1 The owner's answers, 2026-09-26

The owner's framing, which the five answers follow from:

> **Individual engines measure dimensions of evidence. Composite Trade Score
> measures the attractiveness of combining those dimensions for a trade. Risk
> gates constrain whether that opportunity can actually be acted upon.**
> `EngineScore` — what does this evidence dimension say?
> `CompositeTradeScore` — what does the combined quantitative evidence say about
> the trade setup? `DecisionGate` — is taking the trade permitted under the
> current constraints? **Those should not be collapsed into one number.**

| # | Answer | What it settles |
| --- | --- | --- |
| **D1** | **Three separate engines with an explicit ownership rule.** `TechnicalScore` = *what is this security doing?* (RSI, MACD, stochastic, Bollinger %B, ATR, ADX, MA distance and crossover, price and volume momentum, price structure, breakouts, support/resistance, trend strength, the security's own relative momentum). `MarketScore` = *what is the market doing around this security?* (index trend and momentum, market and sector breadth, advance/decline, new highs/lows, market volatility, credit conditions, market liquidity, cross-asset confirmation, index relative strength, participation). `RegimeScore` = *what statistical/economic state is the environment in?* (bull/bear, volatility, risk-on/off, liquidity, inflation, growth, monetary-policy, correlation, trend and crisis regimes). The three may legitimately all read bullish **because they are not duplicates**. | MKT-1 is **answered**: MKT-2 (market-wide breadth) goes to `MarketScore`; MKT-3's acceptance criterion is §1's rule made falsifiable; MKT-4–MKT-8, MKT-9–MKT-14 and VAL/D1-adjacent rows unblock. `RegimeScore`'s built `breadth` leg is a **state input** read from the same `market_breadth` producer `MarketScore` would score — one producer, two readers, per D2's rule |
| **D2** | **`ValuationScore` is its own engine; `FundamentalScore` consumes and attributes it, never re-derives it.** *"Calculate valuation once. Attribute it twice if necessary, but don't calculate it twice."* `FundamentalScore = w_Q·Quality + w_G·Growth + w_B·BalanceSheet + w_C·CashFlow + w_V·Valuation` where `V = ValuationScore`, so a DCF cannot reach the composite through two independent-looking paths | VAL-1 and FUND-20 are **answered**: VAL-2 (the allocation weight), VAL-3 (the floor), VAL-5 (the historical-position quantity is `ValuationScore`'s) follow from it; `FundamentalScore.valuation_subscore` becomes the **consumption** of `ValuationScore`, not a second producer of the multiples. The migration is Phase 7 (VAL-8 first), and until it lands the overlap is latent, not double-counted (no `ValuationScore` producer exists) |
| **D3** | **Keep the weighted mean; do not multiply by `RiskScore`.** The composite stays `0.40 F + 0.25 T + 0.15 R + 0.20 K` (acceptance case → **76.25** in the owner's arithmetic, 76.75 in the built code's alignment) because a product hides where the number came from and destroys leg attribution — *"you're building a research/audit-oriented quantitative engine, not merely an opaque ranking model."* One naming change: define `K = RiskScore` explicitly and state that **`RiskScore` is an input to the composite while the hard risk gates stay outside it** — `CompositeTradeScore ≠ RiskGate`, so a composite of 84 beside a `RiskGate = REJECT` is a valid pair | CTS-1 is **answered**: no multiplicative risk leg, invariant 18 unamended. The printed block, the coefficients and `COMPOSITE_MIN_COVERAGE` stay as built. **`RiskScore` is a composite input, not a gate** is now stated in the composite's own document (§6 Q1, amended) |
| **D4** | **No system becomes a tenth engine automatically.** The criterion is not "does it produce a number" but *"does it represent a sufficiently distinct economic information dimension that deserves independent lifecycle, coverage, attribution, validation and configuration?"*, tested by orthogonality (`1 − |Corr(SurveyScore, ExistingScores)|`): a survey correlating 0.94 with `SentimentScore` does not need an engine; one near 0 has an argument. Candidates that *could* qualify (positioning, options flow, institutional flow, capital-flow pressure, supply-chain stress, AI adoption, alternative data) are judged by that test, one at a time | UNIV-NEWENGINE is **answered and deferred**: every `UNIV-*` gap stays a component or a diagnostic. The gate/leaf/`ENGINE_GATES`/config/doc/web-surface plumbing set is **not** built speculatively. The orthogonality diagnostic becomes a Phase 3 measurement row (it needs the panel, like every other correlation) |
| **D5** | *(The built block already publishes three of the four the answer asks for: each leg prints `value (raw)`, the composite prints `coverage X%`, and `trade_score`'s own `basis` prints `coverage X% over N of 4`. **Confidence** is the one that does not exist yet — Phase 7.)* **Coverage does not deflate the score.** `80 × 0.50 = 40` says "the stock is bearish" when what is known is "the available evidence is bullish but incomplete". Instead shrink toward neutral — `Score_adjusted = 50 + Coverage^γ · (Score_raw − 50)`, `0 ≤ Coverage ≤ 1` (γ controls the penalty; γ = 1 with `Score_raw` 80 at 50% coverage → **65**) — and **publish the four numbers separately**: `Score_raw`, `Coverage`, `Confidence`, `N / total`, so a reader sees *"strong measured signal, incomplete evidence"* rather than missing data read as negative evidence | CTS-3 and MF-7 are **answered**: coverage stays a printed qualifier, and the adjusted form is a **shrink toward 50**, never a multiplier. The built "the reader must see both" rule already satisfies the display half; the confidence-adjusted producer is a Phase 7 row (CTS-1/CTS-9), and `Δ = 50`-centred shrinkage must be tested where the raw score is below 50 as well as above |

| **D6** | **A meta layer exists — as a LAYER, not a tenth or eleventh engine.** *"Agreement, model consensus, dispersion and conviction are meta-properties of the scorecard, not new evidence engines."* The engines answer *what does each dimension say?*; the meta layer answers *how much do they agree, and how reliable is the aggregate?* The owner's formulas: centre each engine (`x_i = (Score_i − 50)/50`), then `Agreement = |Σ wᵢxᵢ / Σ wᵢ|`, `Dispersion = √(Σ wᵢ(xᵢ − x̄)² / Σ wᵢ)` with `x̄ = Σ wᵢxᵢ / Σ wᵢ` (the owner's own worked contrast: two portfolios with a similar weighted mean and completely different dispersion must not carry the same confidence), `AgreementScore = 100·e^(−k·Dispersion)` (preferred over `100(1−D)` because it handles extreme dispersion smoothly), multi-model `Consensus = (1/M)Σ dⱼ` with `dⱼ ∈ [−1,+1]` and `ModelDispersion = Std(d)`, and **`Conviction = AgreementScore × EvidenceConfidence`** (or `Agreement × Coverage × DataQuality`), 0-100 — *"this makes conviction explainable."* **The meta layer is strictly DOWNSTREAM: no engine reads it** (*"avoid engine → meta → engine … that creates circularity"*) | **UNIV-AGREE, UNIV-META and CTS-8/UNIV-CONVICTION are answered.** Build `engine_agreement(scores)` over the engine vector to the formulas above (with the `< 2 engines` refusal and no `0` for `None` that UNIV-AGREE already required). **`Conviction` is `AgreementScore × EvidenceConfidence`, NOT the survey's `BaseSignal × DataConfidence × Agreement × (1 − Risk)`** — the survey's version is superseded: there is no `BaseSignal` leg and no risk term (risk is a gate, per D3). `UNIV-MODELCONS` stays **data-blocked**: the repo runs one model per role, so `Consensus`/`ModelDispersion` have no ensemble to measure — the *shape* is specified and the plumbing is not built speculatively |
| **D7** | **`MomentumScore` is a distinct CORE engine.** *"TechnicalScore should own indicators; MomentumScore owns cross-horizon return/momentum characteristics; MarketScore owns market-level behavior."* Its legs: price momentum `MOM_n = P_t/P_{t−n} − 1` for 5/21/63/126/252; risk-adjusted `RAMOM = R_n/σ_n`; relative `R_stock − R_benchmark`; sector-relative `R_stock − R_sector`; acceleration `MOM_short − MOM_long`; consistency `N_positive_periods / N_periods`; persistence `N_positive_returns / N`. The ownership matrix that follows: RSI, MACD, Bollinger %B, ATR, ADX and MA crossovers → `TechnicalScore`; **the 12-1 month return, multi-horizon returns, relative momentum and momentum acceleration → `MomentumScore`**; S&P/Nasdaq momentum, market breadth and advance/decline → `MarketScore`; VIX → `MarketScore` or `RegimeScore` **depending on definition** (the one row the answer leaves to be fixed when built); volatility/risk-on-off/liquidity regimes → `RegimeScore` | **UNIV-MOMSLOT is answered: `MomentumScore`.** `MarketScore` is a *market-level* engine, not the momentum slot. **Consequence to record and not act on yet:** `technical_score`'s built `momentum` category (weight 18) holds legs (12-1 return, multi-horizon, relative strength) that this matrix assigns to `MomentumScore`; the migration is a **Phase 7 re-cut** (build `MomentumScore`, then move the legs and re-cut `technical_score`'s weights with the owner), never a silent change |
| **D8** | **Fresh intraday event information may modify SIZING, only through a strictly bounded channel.** It never rewrites `EventScore` or the composite: *"CTS 82 / EventScore 76 / IntradayEventRisk HIGH / RiskGate CAUTION / PositionMultiplier 0.35"* — the longer-lived quantitative thesis and the fresh event risk stay distinct. The mechanism: an `IntradayEventState` beside the structural event score, feeding an **Event Risk Overlay** and then the position size, with a bounded multiplier `M_event = e^(−k·R_event)`, `0 ≤ M_event ≤ 1`, applied as `PositionSize = BaseSize × M_event` (*"an intraday event can reduce exposure without contaminating the fundamental score architecture"*). The **latency contract is named explicitly**: record `event_timestamp`, `source_timestamp`, `ingestion_timestamp`, `processing_timestamp`, `decision_timestamp`; publish `Latency = Decision − Event` **and** `DataAge = Decision − Source`; freshness is `e^(−λ·DataAge)` — an event stamped 10:02:01 must not read "fresh" at 15:55 because the system *retrieved* it then | **EVT-6 is answered with a contract to implement, not a question.** It is a Phase 7 build (a new sizing input with max-age, provenance, idempotency and fail-closed behaviour), and the ordering rule is the answer's own: sizing only, never the score. The timestamps and both ages are part of the artifact, not optional logging |
| **D9** | **Freeze the existing renderer and `basis` strings.** *"InternalScoreModel ≠ ReportContract"* — a new internal calculation renders through the existing contract unless the change is a deliberate **version migration**, and the one exception is a string whose **semantics are factually wrong**, which is a contract change (`basis_v1`/`basis_v2` or a `report_schema_version`), *"not ordinary refactoring"* | **RLW-3 is answered: no change to the seven engine renderers or the `basis` tails.** The freeze is now the documented rule for every future engine. This round's *semantic* corrections (the five stale printed provenance strings and the mislabelled producer declarations) fall under the exception and were fixed **with** the versioned-contract note rather than silently — a later reader must be able to see that the string changed because it was wrong, not because the maths moved |

### 2.2 The questions, as they were asked

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
| DOC-1 | **CLOSED 2026-09-27**: the residual gap is gone too — `technical_score`'s `breakout` category now consumes the Donchian value through the declared `breakout_persistence` component, fed by `_donchian_breakout` (`persistence_up - persistence_dn`), and the leaf passes it (`analysis_tools.py:6043`, `donchian=`). Was: the Donchian breakout is reachable but the breakout category does not consume the value | `README.md` §3.2, §3.1; `ScoreUniverse.md` §3, §7 |
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
| DOC-20 | `README.md` §3.1 defect 5 says `net_beta` has "neither producer nor reader"; the engine produces it (`book_risk.net_beta:179`) and the executor field is simply never written — the split is unstated | `README.md` §3.1; `ScoreUniverse.md` §4 |
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

### 5.1 Re-probed 2026-09-27 — can the provider chain feed each ABSENT producer?

§12.1 audited Phase 2 as over-reported. The owner then asked the prior question:
can the providers supply the absent producers' inputs at all? Six read-only probes
took every absent-producer row and answered, per row, whether the input is already
in the chain (and merely unread), a new endpoint of an integrated vendor, a vendor
purchase, or unpublished anywhere.

**Headline: not one of the 21 rows is vendor-blocked.** Eighteen are `REPO_SIDE`
(the input is held, or is plain arithmetic over data the repo already has) or
`FEEDABLE_NOW` (fetched today and dropped by a parser); one is `NO_SOURCE`. What
remains missing is *definitions* (three rows), *wiring*, and one *entitlement
question* — not data.

| verdict | rows | the one-line finding |
| --- | --- | --- |
| `FEEDABLE_NOW` | TECH-19, NEWS-7, NEWS-5 | the label, the series and the classifier are all in the chain today |
| `REPO_SIDE` | TECH-7/TECH-12, TECH-14, TECH-23, REG-4, REG-16, REG-17, RISK-5, RISK-7/RISK-12, SENT-7 (negation/intensifier half), SENT-9, SENT-10, SENT-11, FUND-15, FUND-16, NEWS-9, NEWS-12/NEWS-13, EVT-9 | a producer, an emitter or a definition — no fetch |
| `VENDOR_ONLY` | SENT-7 (aspect-taxonomy half) | the only leg with no cheap source |
| `NO_SOURCE` | RISK-20 (balance-sheet `FXExposure`) | probed against three real SEC XBRL instances: nothing files a currency split of total assets and liabilities |
| superseded | MKT-13, VAL-10/12/13/14/15/17 | belong to engines that D1/D2 move to Phase 7 |

**TECH-19 / NEWS-7 — `FEEDABLE_NOW`.** Label: `yfinance_sector.fetch_sector:64` (FMP profile → Finnhub `company_profile2` → yfinance `info` → the repo's own SPDR universe map) plus `sector_rank.sector_group_of:163` → the SPDR ticker; probed live: AAPL → Technology → XLK, XOM → Energy → XLE, JPM → Financial Services → XLF. Series: `_ohlcv(sector_etf)` (`stockstats_utils.load_ohlcv:254`, keyless) — live XLK/XLE 1,256 bars each, and the same call target already serves all eleven SPDR series in `get_sector_rank` and `get_sector_rotation_screen`. Arithmetic: `relative_strength.relative_strength_report:214`; the private `sector_screener._rel_outperformance:248` is exactly stock-return minus sector-ETF-return. When every label leg is unavailable the honest output is NA, never a bucket.

**NEWS-5 — `FEEDABLE_NOW`: the tags are fetched and thrown away.** Benzinga `/v2/news` carries `channels[]`, `tags[]` and `importance_rank` (`benzinga.py:401-414` renders title/date/author/url only); EODHD `/news` carries `tags[]` (50 standard tags) plus a `sentiment{polarity,neg,neu,pos}` object (`eodhd.py:262-271` renders title/content/date/source only); Alpha Vantage `NEWS_SENTIMENT` returns per-article `topics[]` (`sentiment.py:637-650` reads only `ticker_sentiment`). AV has no legal/regulatory topic, so the `regulatory_legal` half maps to GDELT GKG themes or Benzinga's channels; the tag→category table is repo-side either way.

**NEWS-9 — `REPO_SIDE`.** Headlines and timestamps are already fetched by every news vendor, so similarity needs a local embedding (`sentence-transformers` `all-MiniLM-L6-v2`, $0/CPU) or TF-IDF cosine; the only vendor publishing a duplicate signal is Marketaux (`similar[]`, free tier 100 req/day), which is optional. `news_novelty:309` is a first-seen count share today.

**NEWS-12/NEWS-13 — `REPO_SIDE`, needs a run.** The producers exist and are tested (`sentiment_research.multi_horizon_sentiment_regression:264`, `ic_term_structure:501`); `_news_components` hard-codes one 30-day window (`analysis_tools.py:7019`).

**SENT-7 — `REPO_SIDE` for the negation/intensifier half.** The library's own language (`SentimentScore.md` §10/§11: negation `S(w|neg) = −S(w)`, `(-1)^I(NegWithinK)`, booster α) is VADER's rule engine — its `NEGATE` set with a three-token look-back plus `BOOSTER_DICT` (±0.293), MIT-licensed and purely local over text the repo already holds (`text_factors.lm_tone:121` is unigram-only today, over a *reduced* Loughran-McDonald seed set). The **aspect taxonomy** is the one leg with no cheap source (MeaningCloud's ABSA tier is search-sourced only; Aylien/Lexalytics are enterprise quotes) — `VENDOR_ONLY`, and the only row in this table that is.

**SENT-9 — `REPO_SIDE`; source breadth is the weak leg.** The counts exist (`sentiment.compute_social_scores:1093` bullish/bearish/unlabeled/sample_size over `stocktwits.stocktwits_counts:83`; the per-day news count `n` through `aggregate_daily_sentiment:667`). Kish N_eff, HHI and Gini are closed-form over them. But only ONE social source is wired (Stocktwits; Reddit arrives as text) — per-source breadth needs a new call target: ApeWisdom's keyless Reddit+4chan mention API, or Finnhub `/stock/social-sentiment` (Premium).

**SENT-10 / SENT-11 — `REPO_SIDE`.** Both take series the repo already holds in-process (the daily sentiment series, the per-item polarity, `_ohlcv` returns), and the models to reuse already exist: `regime._hmm_em:355` / `hmm_filtered_regime:545`, `statistical_kalman.kalman_spread:42`, plus the entropy helpers.

**FUND-15 / FUND-16 — `REPO_SIDE`, but a definition must come first.** The inputs are present: the wide EDGAR panel (30 dates × 150 names, 24/28 fundamental factors) and `sec_edgar.financial_history_series:534` for the per-name statement history. §36's `MaximumPossibleStd` and §26's lags `n` / weights `w_i` are unbound in the library — a definition decision, not a producer. Vendor "dispersion" (Zacks, Bloomberg BEst) is analyst-estimate spread, a different quantity.

**TECH-7/TECH-12, TECH-14, TECH-23, RISK-5, RISK-7/RISK-12 — `REPO_SIDE`.** `technical_factors.bollinger_bandwidth:1169` and `keltner_channel:439` both exist, so the TTM squeeze histogram is unwritten arithmetic. The Zweig thrust exists and prints (`technical_depth.zweig_breadth_thrust:400`, `market_breadth.advance_decline_line:278`); it is not a `technical_score` component, which is a declared-table edit. The redundancy producers exist (`alpha_zoo.redundancy_screen:581`, `score_panel.redundancy_matrix:1419`) and §129's seven-state enum is a design choice. `derivatives_gamma.gex_per_strike:52` already returns per-strike `contributions` beside `spot`, so distance-to-spot and a ranked top-|GEX| list are arithmetic, and the chain rows are already fetched free (`cboe.get_options_surface:103`, `yfinance_options`). `cluster_exposure_share` is book-side: `BookState.cluster_notional():109` and `notional():103` already hold the numerator and denominator that `signald/risk/gate.py:369` compares, so it is a producer plus plumbing — no vendor publishes an account's cluster notional.

**REG-4 / REG-16 / REG-17 — `REPO_SIDE`.** All three producers exist and are tested; a scoped grep finds no caller outside `strategies/regime.py`. Emitter work only.

**RISK-20's balance-sheet leg — `NO_SOURCE`.** The probe downloaded three real XBRL instances and read them: JPM's 10-K carries 9,026 explicit members and puts `us-gaap:Assets` on `StatementGeographicalAxis` (18 facts — but the members are US *states*, and there is no `CurrencyAxis`); HSBC's 20-F uses `srt:CurrencyAxis` only for hedging instruments, derivative assets/liabilities, VaR and notionals; Unilever's only for borrowings plus one filer-defined extension. No standard, universe-wide tag carries a currency split of **total** assets and liabilities, and no vendor verified sells one (S&P Capital IQ has a liabilities-side subset, enterprise). The dimensional plumbing exists (free SEC FSDS `segments`; sec-api.io XBRL-to-JSON, $49/mo) — the facts do not. `_fx_exposure` stays private.

**EVT-9 — `REPO_SIDE` plus a contradiction to resolve.** `event_state.py:591` returns a 0-100 `{score, band, coverage, families}` while `scripts/score_panel.py:903` (`ENGINE_NOT_SCORED`) states "EventScore is a state/flag object, not a 0-100 score", and `engine_registry:954` imports only `ENGINE_MODULES:893`, which omits `event_state`. One of the two is wrong; an owner decision (add the panel column, or record it as out of panel scope) precedes any run.

**Defects this probe found.** Checking the GDELT rows live found that the vendor's tone claim was never real — the DOC 2.0 article-list response carries no per-article tone, the code parsed that field anyway, and a rate-limited (429) response was classified as no-data because the body was parsed before the status. Both fixed in `0fe27e7`, with the failing-first proof in the CHANGELOG entry. Flagged, not confirmed: `sp500_universe.fetch_sp500_universe` live-returned 317 bucketed rows for the current S&P 500 (its wikitext row regex appears to under-capture) — a keyless label fallback that under-covers silently.

**What this does not settle.** Three definition decisions (FUND-15's normaliser, FUND-16's lags and weights, TECH-23's state enum), one owner call (EVT-9), one entitlement question (enumerating Benzinga's news channels needs an entitled key), and one live probe (GDELT `mode=timelineTone`, blocked by GDELT answering 429 to this host on 2026-09-27).

---

## 6. Phase 3 — the measurement layer (Phase C) (`WORK`, D2-4, I3-5)

Nothing promotes a weight, a status or a composite rung without this phase. It is
the plan's spine: `RESEARCH_ONLY` is the state of every vector until a measurement
exists.

### 6.1 Measured 2026-09-26 — the wide EDGAR panel (MF-1 and MF-2, done)

The run that was missing exists. `scripts/score_panel.py` built **30 trading dates
(2026-08-06 … 2026-09-17) × 150 names** on the SEC EDGAR XBRL fundamentals leg —
**150 companyfacts requests**, one per filer, reused across every date (30 dates
fetched, no cache hits) — into a separate cache root so the old price-only panels
are untouched:

```
py -3.12 scripts/score_panel.py --dates 2026-08-06,...,2026-09-17 \
    --symbols-file ~/.tradingagents/cache/panel_universe_sample.txt \
    --cache-dir ~/.tradingagents/cache/panels_edgar
```

| Reading | Before | Now |
| --- | --- | --- |
| panel status / floors | `OK` on the price-only leg | **`OK`**, 30 dates, 150 names, 150 metrics |
| `fundamental_score` measured | **0** of 28 declared | **24** of 28 |
| `technical_score` measured | — | 40 of 42 |
| redundancy matrix | `n_pairs: 0` | **`n_pairs: 2006`** over 64 metrics |
| FCF-yield cluster block | no pairs (MF-2's exact gap) | **6 pairs over 5 members** (`fcf_yield`, `price_to_free_cash_flow`, `price_to_cash_flow`, `earnings_yield`, `val_z`) |
| technical trend/momentum/RS block | — | 136 pairs over 17 members |

**What this does and does not mean.** MF-1 and MF-2 are met on their own
verification (`n_measured > 0` with a panel label of `OK`; the FCF-yield cluster
reports `n_pairs > 0`), and the fundamental factors are now *measurable* rather
than vendor-blocked — one month, one market, 150 names is still a **diagnostic**,
not a validation, exactly as `MEASUREMENT_FINDINGS.md` §5 says. No weight was
promoted: every vector stays `RESEARCH_ONLY`, and MF-4/MF-6/`FUND-24`/`RLW-4`
still need the evidenced ladder.

`scripts/score_panel_eval.py` (PLAN-4) is built and evaluates the cached panels
with the **sector** and **regime** robustness splits (PLAN-6/MF-3) and the
**technical-category correlation matrix** (TECH-24, measured: status `ADVISORY`,
36 pairs, `relative_strength`/`breadth` withheld with their reason on a
single-date panel). Both splits are **mechanism-complete and label-blocked**, and
the run says so rather than guessing: a sector split needs a per-name sector
label (the repo's static map is sector-name → ETF, not ticker → sector, and the
bulk path carries no per-name vendor call — `MEASUREMENT_FINDINGS.md` §5 already
predicted exactly this), and a regime split needs a market-level regime series per
date, which `RegimeScore` does not yet persist. `--sector-map`/`--regime-map`
accept a caller-supplied mapping today.

**FUND-15 / FUND-16 now run on the panel (2026-09-27).** `scripts/score_panel.py`
gained `agreement_and_momentum`: per name, `factor_dispersion.factor_score_dispersion`
over that date's factor vector and `fundamental_momentum` over the date axis of the
same rows - the panel *is* those producers' source, so the panel reports them
(`report["factor_agreement"]`, printed as one summary line and the per-name blocks).
This is also what makes the two producers reachable outside their module, which
`tests/test_calc_agent_wiring.py` requires.

**Still open in this phase**: MF-5 (9 of 11 `news_score` components on the live
per-symbol path), MF-8 (`risk_score`/`sentiment_score` panel path — structurally
blocked by data shape: position/book-level and per-symbol vendor reads), MF-6 (the
momentum-redundancy reduction, which edits a declared owner table and needs the
owner's signature), and RLW-4 (`Movement` needs a vector at the `VALIDATED` rung).

**PLAN-5 met 2026-09-27.** The gate-on tree `reports/MSFT_20260927_001700`
(`batch.py --symbols MSFT --date 2026-09-25`, exit 0, ~53 min) reads
`report_verify.py` **0 CONFIRMED** on `CONFIRMED` (four stems `PASS`,
`sentiment` `FLAG`) and `verify_sweep.py` **148 GROUNDED / 0 CONFIRMED / 1
SUSPECT** — against **147 / 4 CONFIRMED / 11 SUSPECT** before it. All fifteen
adjudicated to the checker, not the report: four anchor false positives (a
multi-leg label cell binding the bear leg to `bull`; `_NET_FIGURE_RE`'s
separator class swallowing the minus sign, so a correct `Net debt
-19,820,000,000` line read as a contradiction; `50 / 200 SMA`'s shared label
cell taking the value cell's first `%`; `_repetition_loops` counting text with
no context) plus one evidence-model gap — `engine_score_block` renders the run's
own `quant_scorecard` into every prompt and the analyst quotes it back, so
grounding only against `tool_evidence.json` leaves made every engine line
UNSUPPORTED **by construction**. The run card is now a third prompt-level
evidence source beside `instrument_identity`/`reference_price`. The one
remaining SUSPECT is **pre-existing and correct**: `sentiment.md:14` calls the
leaf's 16-ticker list a 15-ticker portfolio, an analyst count error in a frozen
report (recorded in `docs/design_report_verification_llm.md`'s 2026-09-27
round).

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
| PLAN-5 | Land a gate-on tree on which `report_verify.py` and `verify_sweep.py` both exit 0 on `CONFIRMED` (Phase A's last clause) | `IMPLEMENTATION_PLAN.md` §9 | 3 | 3 | **MET 2026-09-27** on `reports/MSFT_20260927_001700`: 0 `CONFIRMED`, 1 pre-existing-and-correct `SUSPECT` (§6.1) |
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
| RISK-19 | Revenue and geographic concentration | a **concentration leg** over the per-dimension revenue leaf — the source is feedable and its dimension merge is fixed (2026-09-27, §8.1) | `RiskScore.md` §8.2 §50/§51 |
| REG-19 | MOVE / Treasury-volatility source | an external MOVE source or a DGS10 realised-vol proxy | `RegimeScore.md` §4 |
| NEWS-2/NEWS-6/NEWS-16 | Fundamental-impact surprises, price-target revisions, the estimate-level series | an estimate history (revenue/margin consensus, a persisted PT series, 3-4 quarters of estimates) | `NewsScore.md` §4, §8.2 |
| MKT-* | MarketScore's panel-dependent components | the cross-sectional universe decision (MKT-4) — the library's own warning is that a percentile over nine names is not a decile | `MarketScore.md` §7 Q4 |

### 8.1 Re-probed 2026-09-26 — can the CURRENT provider chain feed each row?

The owner asked whether the providers the repo has **today** can feed Phase 5. Four auditors opened the
vendor module behind every registered tool (`dataflows/interface.py::VENDOR_METHODS` — **24 vendors**),
read the SDK behind the moomoo-only ones, the FRED series were probed **live**, and the CBOE / Finnhub /
FMP tiers were checked against their published documentation. **Six of the sixteen rows are feedable from
the chain we already have** — no new vendor, no new key, with a parser or a store as the work — one is
internal, and the rest are genuinely absent, each with the exact read that shows it.

| Row | Verdict today | The read that answers it |
| --- | --- | --- |
| FUND-17 R&D / intangible set | **FEEDABLE-WITH-PARSING** | `sec_edgar.py:71-93`'s `_TAG_MAP` is a 21-row declared label→tag map, but `_company_facts:181` already fetches the **whole `companyfacts` payload in one request** and `_us_gaap_facts:199` returns the entire `us-gaap` namespace — `annual_facts:298` only filters it. `ResearchAndDevelopmentExpense` is **already in the bytes**: one declared row, zero extra requests |
| FUND-10 deferred revenue | **FEEDABLE-WITH-PARSING** | same mechanism — `ContractWithCustomerLiability*` / `DeferredRevenue*` ride the same payload. `statement_parsing.py:60-63` deliberately excludes 'deferred'/'unearned' from the `revenue` alias (correct, it is a liability) and declares no separate key, so the work is a declared tag plus a canonical key (`_SEC_SERIES_KEYS:717`) |
| FUND-10 debt-maturity wall | **PARTIAL — FEEDABLE-WITH-PARSING** | the six plain `LongTermDebtMaturitiesRepaymentsOfPrincipalIn*` buckets are non-dimensional and already in the payload; the **by-instrument** wall is reported dimensionally and `companyfacts` is strictly non-dimensional. That half needs the SEC Financial Statement Data Sets (`num.txt` carries a `segments` field / `dimh` key), so the plain-tag wall is the deliverable and the rest must refuse rather than sum |
| RISK-19 segment + geographic revenue | **FEEDABLE-WITH-PARSING** | `get_revenue_breakdown` exists and is **moomoo-only** (`interface.py:618-620`); `moomoo.py:1974-2000` calls `ctx.get_financials_revenue_breakdown(code)` and flattens `breakdown_list[*].item_list`, **dropping each group's `type`** — while the SDK's own `RevenueBreakdownType` is `Product\|Industry\|Region\|Business`. Product/segment **and** geographic lines arrive in ONE response and are merged today. Keep the type, split the dimensions, HHI the chosen one; `screenDateList` already exposes the periods a series needs. **[FIXED 2026-09-27**: the type is kept — every dimension renders under its own `###` label, with a lead line stating the shares are within-dimension and revenue must not be summed across dimensions. Probed **live**: MSFT FY2026 returns `REGION` (51.47% + 48.53%) and `BUSINESS` (42.19% + 41.52% + 16.29%), each summing to 100% and each to the **same** $331.839B, so the merged table had put a region's share in the same column as a business's **and** double counted the total. `moomoo._dimension_label`; tests in `tests/test_moomoo_vendor.py`, one proven failing-first against the pre-fix source. The HHI leg itself remains RISK-19's own work]** |
| VAL-16 CAPE / Shiller P/E | **FEEDABLE-WITH-PARSING** | all three byte sources are in the chain: `fred.py:48` `CPIAUCSL` (the deflator, as history via `fred.get_series_values:213`), SEC EDGAR EPS (~15 years for US filers) and multi-decade OHLCV. Shiller's own published series is not needed — and is not in the chain |
| REG-19 MOVE | **MOVE: NOT-FEEDABLE · proxy: FEEDABLE** | probed **live**: FRED returns **HTTP 400 for series `MOVE`**, and its only Treasury-vol series `VXTYN` is marked DISCONTINUED; the chain's only vol series is `vix`. ICE publishes MOVE as a product, not a free feed. But `fred.get_series_values(DGS10)` gives the dated history and `regime.realized_vol:39` already turns a series into a vol — the row's own second option |
| UNIV-GOV governance tables | **FEEDABLE-WITH-PARSING** | DEF 14A is free and the URL is already built — `_FORM_LABELS:47` names it and `get_sec_filings` prints the archive link — but nothing downloads or parses the proxy, and `get_edgar_fulltext_search:591` returns metadata only. FMP exposes a `governance-executive-compensation` endpoint and Finnhub an `executive` array; independence / related-party / auditor tables are proxy **text** |
| NEWS-2 revenue impact | **revenue: FEEDABLE (gate off) · margin: NOT-FEEDABLE** | the only forward measure in the chain is Benzinga's guidance revisions (`benzinga.py:1044`: forward revenue/EPS range **with the prior range**, behind `enable_benzinga_surface`, default off). No revenue or margin **consensus** exists in any tier and no margin field anywhere — that half stays NA |
| NEWS-6 PT revision | **FEEDABLE-WITH-PARSING (needs a store)** | every primary vendor returns a **current** consensus only (`finnhub.py:148-166`, `y_finance.py:912-922`, `moomoo.py:1355`); the only per-action PT series is Benzinga's (`benzinga.py:622-660`, `pt_current`/`pt_prior`, gated). Snapshot the consensus daily — the disk vendor cache already exists |
| NEWS-16 estimate series | **90-day trend: FEEDABLE (gate off) · 3-4 quarters: NOT-FEEDABLE** | `yfinance_sector.py:272-294` is a **90-day, one-quarter** window (`current`/`7`/`30`/`60`/`90daysAgo`, basis `'vendor 90-day estimate-trend'`), wired behind `enable_analyst_estimates`; the module says so itself and `analyst_revisions.py:190-205` documents the absence. A true four-quarter consensus needs a new vendor |
| EVT-7 (92 sections) | **reaction + base rates: FEEDABLE-WITH-PARSING · estimates: NOT-FEEDABLE** | the backward subset is reachable: moomoo's `get_earnings_surprise_history` (sole vendor) returns ~6 prints of actual-vs-estimate + day move + implied move, and the print-day reaction is rebuildable from stored OHLCV; `get_prediction_markets` (polymarket > moomoo) is a registered **forward-probability** source for the event classes it covers. The estimate-driven majority shares NEWS-16's block |
| EVT-3 court-decision calendar | **NOT-FEEDABLE as a forward calendar** | no vendor in the chain carries one, and the free external sources do not either: CourtListener serves docket metadata and entries — hearing dates appear as **entries once posted** — and has no upcoming-hearing endpoint. This is a docket-poller-plus-alert build, or it is dropped |
| UNIV-IVRANK IV rank | **history: NOT-FEEDABLE · current surface: FEEDABLE** | `get_options_surface` (CBOE, **no key**) is `cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json` — a **snapshot** with per-contract iv/delta/gamma; its only time series is the VIX9D/VIX3M daily **close** (`cboe.py` reads the last row), which is index-level, not a name's IV. CBOE's Option EOD Summary does carry IV history (2012–present) but as a **paid** add-on; the yfinance and moomoo chains are snapshots too. The leaf's `n/a (no per-day IV history source)` is therefore correct as written — the fix is an accumulation store (`score_history.py:9-11` is the pattern) or a paid dataset |
| UNIV-ETFFLOW ETF net flow | **NOT-FEEDABLE** | corroborated across the chain: no tool returns creations/redemptions or fund flow. moomoo's `get_capital_flow` is **secondary-market** net inflow by order size for a *stock* (weekly, ≤365d), `finra`'s dark-pool flow is ATS equity volume, and yfinance's `shares_outstanding` is a company share count. Direct flow needs a specialist (paid) provider; a labelled Δ-shares × NAV inference is the only free route |
| UNIV-MOAT | **NOT-FEEDABLE as a datum** | `value_dip.py:964`'s "not available from the vendors" stands — moat legs are qualitative. The chain does hold the raw **text** (FMP earnings transcripts, EDGAR filings), so this is a parsing/model project, not a feed |
| VAL-18 SOTP / liquidation / NAV | **NOT-FEEDABLE** | no segment **fair values** or appraisals anywhere in the chain; moomoo's revenue breakdown supplies a segment *revenue* denominator, not a value |
| RISK-3 / RISK-8 / RISK-9 gap-fill calibration | **INTERNAL** | no vendor needed: the fill-outcome sample is buildable from the OHLCV history the repo already stores, and the constants are already labelled fallbacks |
| UNIV-MODELCONS | **not a vendor item** | it needs an ensemble of independent model scores — a design question (D6's meta layer), not a data feed |
| MKT-* | **owner decision** | the block is the cross-sectional universe (MKT-4), not a vendor |

**What this changes.** Six rows can leave the waiting room as ordinary work items (FUND-17, FUND-10 ×2,
RISK-19, VAL-16, UNIV-GOV, REG-19's proxy, plus the gated NEWS-2/16 legs and NEWS-6's store). The
genuinely blocked set is smaller than §8's table implies — and two rows are blocked for a reason the
table does not state: `UNIV-IVRANK` needs a **store or a paid dataset**, not a vendor, and `EVT-3` needs a
**poller**, not an archive.

---

## 9. Phase 6 — the owner decisions (`DECISION`)

**Five of the nine gates were answered on 2026-09-26 (§2.1), and those answers
also settle several rows below.** Settled, with the reading they take from the
answer:

| Row | Now settled as | By |
| --- | --- | --- |
| **MKT-2** market-wide breadth | `MarketScore` owns the scored dimension; `RegimeScore` keeps the breadth *regime* as a state input over the same producer | D1 |
| **MKT-5** short interest / IV / insider / gaps | **Consumed as stated dependencies**, never re-derived — each already has a named producer and owner | D1 |
| **MKT-6** per-name vs market-wide | Market/index-level rows (the owner's own list is all market-level), joined to the name as its exposure; a per-name twin is not built | D1 |
| **VAL-4** who supplies `dcf_upside` | `ValuationScore` **owns** the DCF; the caller-supplied-supplier column is a pre-cutover state | D2 |
| **VAL-5** the historical-position quantity | `ValuationScore`'s (`val_z`), not a second `FundamentalScore` producer | D2 |
| **VAL-6** the confidence output shape | A **separate published field**, never folded into the score | D5 |
| **VAL-2** the research-allocation weight | Settlement in kind: `ValuationScore` enters the composite **through `FundamentalScore`'s valuation weight** (`w_V`), not as a seventh line — the number for `w_V` still needs the owner | D2 |
| **CTS-3** coverage as multiplier or qualifier | Shrink toward 50 (`50 + Coverage^γ(Score_raw − 50)`), four numbers published separately; γ still needs a number | D5 |
| **UNIV-NEWENGINE** | Not built speculatively; the orthogonality diagnostic decides, one system at a time | D4 |

**Still open, and genuinely requiring the owner**: `MKT-3` (the acceptance
criterion), `MKT-7` (MarketScore's weight and gate name), `MKT-8` (one convention
per quantity), `VAL-3` (the coverage floor), `CTS-2`, `CTS-5`, `CTS-6`, `CTS-7`
(the new objects and the V1 vector), `README-3`, `RLW-3`/D9 (the frozen
renderer strings), `SCC-4`, `PLAN-8`, `PLAN-9`, `PLAN-11`, `REG-20`, and the
owner-file rows `TECH-25/26`, `REG-21/22`, `RISK-25/26`. The remaining decisions
are otherwise cheaper and narrower:

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

**Unblocked 2026-09-26 for D1/D2/D3-dependent rows**: `MKT-*` (build `MarketScore`
over the market-around-the-name rows), `VAL-8`/`VAL-9`/`VAL-11`/`VAL-20` (build
`ValuationScore` as the valuation producer, then cut `FundamentalScore`'s
valuation leg over to consuming it — module first, `VS` second), and `CTS-1`/
`CTS-9` (the composite keeps its weighted mean; the *new* work the answers add is
the coverage-shrink producer of D5 and the explicit `RiskScore`-is-an-input,
gates-are-outside statement). Rows still waiting on an answer: `CTS-8`/`UNIV-AGREE`
(D6), `EVT-6` (D8), `FUND-11`/`FUND-12` (need the measurement layer), and
`UNIV-NEWENGINE` (D4 settled it: not built speculatively).

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

### 12.1 Audit 2026-09-26 — what Phases 0-4 left undone

**Why this section exists.** The round that executed Phases 0-4 (`a5b2b7e`, plus two doc commits)
reported all five phases done. The owner asked for a re-scan, and five read-only auditors then took
**every row** of §3, §4, §5, §6 and §7 and performed **that row's own Verification cell** against the
tree. Phase 0 is clean (§3.2's 22 rows all corrected, plus §3.1's four; the two residual nits are
named below). **Phases 1, 2 and 4 were over-reported** — the rows below are not met, and none of them
was recorded as open anywhere. **44 rows, counted by id.**

| id | Phase | Acceptance cell | Where it stops (audited 2026-09-26) |
| --- | --- | --- | --- |
| NEWS-3 | 1 | the component stops printing NA | **MET 2026-09-27** — `analysis_tools._news_components` now calls it behind its own gate: `benzinga.guidance_revision_rows` (the new structured producer, one fetch, two readers) -> `news_score.guidance_change_score`, feeding the SIGNED midpoint change (the engine's ramp), not the aligned score. Live: absent with the gate off (the declared reason), which is the honest state |
| NEWS-4 | 1 | the component stops printing absent | **MET 2026-09-27** — `sec_edgar.recent_filing_forms` (new structured producer behind `get_sec_filings`) -> `corporate_events_score`, windowed so a historical run cannot read a filing filed after its trade date. Live MSFT 2026-09-25: `corporate_events = 75.0` (the 8-K typing), and the component is no longer in the absent set |
| RISK-4 / PLAN-7 | 1 | an assignment at a `BookState(...)` site | **DECIDED 2026-09-27 (owner: extend `research_decision.json`)** — the engine writes its book beta (`book_risk.net_beta`, already emitted as `net_beta_raw`/`net_beta` by `cross_section.py:470-471`) into the decision payload and the executor reads it at its `BookState(...)` sites. That is a versioned-contract change, so it lands as its own step rather than inside a docs pass - **scoped 2026-09-27:** the field does NOT go in `execution_contract.risk_advisory`'s block, whose contract states the executor never reads a number out of it; it is a new envelope field beside `producer`/`body_sha256`, which means `tradingagents/execution_contract.py` (a MINOR bump from `1.1.0`), the vendored `contracts/research_decision.v1.schema.json` the emitter test asserts against, `../TradingExecution/signald/schema.py`'s parse/validate, and the `BookState(...)` sites that would finally populate `net_beta`. The value itself already exists engine-side (`book_risk.net_beta`, emitted as `net_beta_raw`/`net_beta` by `cross_section.py:470-471`), so no new computation is needed |
| FUND-8 | 1 | `normalized_cycle_fcf` gains `std` | **MET 2026-09-27** — `cycle_dcf.normalized_cycle_fcf` returns the sample σ beside `median/min/max/mean` (never a fabricated 0: `None` below the 3-year floor), and `get_normalized_cycle_dcf` prints it as `sd=`. A wide cycle and a flat one can share a median; only the dispersion separates them |
| FUND-21 | 1 | the leaf passes both; VS carries the factor | **MET 2026-09-27 on the outcome, by a better route** — VS carries the confidence-scaled factor for the whole panel through `_engine_dcf_upside` (`fundamental_score.py:750`), which derives it from the financials the resolver already fetched; a caller-supplied DCF remains the FIRST route and stays available, but making each of the three callers compute its own DCF would be three extra fetches for a number the engine already derives. The literal cell (a live caller passes both) is superseded, not unmet |
| PLAN-3 | 1 | a grep for the key **and** a run's `research_decision.json` | **closed 2026-09-27**: `reports/MSFT_20260927_001700/research_decision.json:193` carries `"opportunity_score_reason": "null by decision, not by failure: …"` beside `opportunity_score: null`. Every other tree in `reports/` predates the field, which is what kept this row open |
| NEWS-15 | 1 | an owner sentence, or the flags flipped under a labelled dark-launch diff | **CLOSED 2026-09-27 (owner decision: keep them off and record the policy)** — all four (`enable_weighted_sentiment_agg`, `enable_weighted_sentiment_window`, `enable_news_relevance`, `enable_crowd_ratio_bands`) stay off by default, each with its reason recorded in `docs/gate_registry.md`; `.env` is the owner's and is left alone, so the divergence between `.env` and the defaults is a local override rather than the de-facto policy |
| TECH-14 | 2 | a thrust producer over the panel | **MET 2026-09-27** (owner decision: a leg, not a new weight) — `technical_score.COMPONENTS` gains `zweig_thrust` in the existing `breadth` category, fed by the same panel's per-session advancers/decliners (`technical_depth.zweig_breadth_thrust`), raw = the window's EMA change in the advance ratio with the library's own 0.40→0.615 event as the ramp. `CATEGORY_WEIGHTS` is unchanged |
| TECH-7 / TECH-12 | 2 | a BBW producer + percentile | **MET 2026-09-27** — `technical_factors.squeeze_momentum` (BB inside KC, the release flag against the prior bar's ATR, and the momentum/direction at release). Tested in `tests/test_tech_state_readers.py`; no leaf wiring yet |
| TECH-19 | 2 | a leaf returns `relative_strength_vs_sector` | **MET 2026-09-27** — `relative_strength.relative_strength_vs_sector` (stock − sector-ETF return over a declared window, the benchmark reported BESIDE it, never blended) and `get_relative_strength` now resolves the ticker's sector label to its SPDR ETF and prints `vs_sector_etf=` |
| TECH-23 | 2 | a redundancy producer + the four readers | **MET 2026-09-27** — the redundancy producers already existed; `technical_score` now has `technical_state` (the library's state names), `technical_acceleration` (velocity/acceleration/jerk, the naming divergence stated) and `technical_disagreement` (over the category sub-scores, naming what it compared) |
| REG-4 | 2 | three separately-printed index reads | **MET 2026-09-27** — `analysis_tools.get_regime_components` emits one labelled read per index (live MSFT run: SPY +7.91%, QQQ +11.99%, IWM +2.75%, each above its 200-bar SMA, no cross-index mean) |
| REG-16 | 2 | a printed transition probability | **MET 2026-09-27** — emitted by `get_regime_components` off ONE HMM fit (live: state 0/2, persistence 0.9023, P(leave) 0.0977, expected durations [10.24, 1.89] bars) |
| REG-17 | 2 | the block is emitted | **MET 2026-09-27** — the §96 block is emitted beside the label (live: entropy 0.5100, confidence 0.7929, stability 0.2668, surprise 0.6348) and deliberately not folded into the number |
| RISK-5 | 2 | a producer returns named levels | **MET 2026-09-27** — `derivatives_gamma.gex_levels` ranks the top-|GEX| strikes with their signed gamma, share of total absolute dealer gamma and signed distance-to-spot, printed by `get_gamma_profile` |
| RISK-7 / RISK-12 | 2 | a scalar producer with a stated scale | **MET 2026-09-27** — `../TradingExecution/signald/risk/state.py::BookState.cluster_exposure_share` returns the largest cluster's share of book equity (a named cluster's share on request) on the 0..1 `portfolio_hhi` scale, `None` - never 0 - when equity is unmeasurable or the key maps to no position. The engine's declaration now names it (it previously cited a gate line and the wrong divisor). Executor commit `a2e74c0`; the gate's own per-key cap arithmetic is unchanged |
| RISK-16 | 2 | each has a named producer | **MET 2026-09-27** — `book_risk.stop_hit_probability` (the running-minimum breach over overlapping `horizon`-bar paths; the prescribed `copula_scenarios` route needs ≥2 names and so cannot answer a single-name read), printed as `stop_hit_1m` + `stop_dist` by `get_tail_risk` against the repo's own 2xATR stop. Live: NVDA 53.2% / 4.62%, TSLA 52.2% / 6.02% |
| RISK-18 | 2 | " | **MET 2026-09-27** — `compute_ratios` returns `cash_runway_years` (Cash / \|FCF<0\| — `None`, never an infinite ratio, when FCF funds no burn) and `fcf_deterioration`; `get_ratios` renders both. Live: MSFT −6.45%, NVDA +58.88% deterioration, both runways `n/a` (positive FCF) |
| RISK-19 | 2 | " | **MET 2026-09-27** — `liquidity_risk.revenue_concentration` (the §50/§51 HHI over ONE dimension's shares, on the `portfolio_hhi` 0-1 scale, never `ownership_hhi`'s 0-10000), printed per dimension by `moomoo.get_revenue_breakdown_moomoo`. Live MSFT: REGION 0.500 / N_eff 2.0 vs BUSINESS 0.377 / 2.7 |
| RISK-20 | 2 | " | **PARTIAL 2026-09-27** — the VaR leg is built (`book_risk.fx_move_var`: the library's `FXVol × z_c` as a per-unit-of-position factor, printed by `get_fx_snapshot`; live DTWEXBGS ±0.43%/day at z=1.645). The balance-sheet `FXExposure` stays `book_risk._fx_exposure` (**private**): no vendor in the chain returns a currency split of assets and liabilities, so nothing can supply its numerator |
| RISK-21 | 2 | " | **MET 2026-09-27** — `statistical.commodity_beta` (the §54 OLS beta fitted on the dates the asset and its mapped driver share, ≥20 returns), printed as the `beta` column of `get_sector_rotation_screen`'s driver table. Live: XLE vs wti 0.24 (t 12.1, R² 0.36, n 268); the monthly copper driver refuses |
| SENT-7 | 2 | a negation-adjusted intensity | **MET for the negation/intensifier half 2026-09-27** — `sentiment.negation_adjusted_polarity` (declared K=3 window + intensifier/diminisher tables over the LM lists). The **aspect taxonomy stays VENDOR_ONLY** (§5.1) and subjectivity/uncertainty remain open |
| SENT-9 | 2 | one producer per measure | **MET 2026-09-27** — `sentiment.effective_sample_size`, `herfindahl_index`, `gini_coefficient` and `source_breadth` (whose single-source case is a real low-breadth answer, not a refusal). Only Stocktwits is wired, so breadth is one source wide until a second joins |
| SENT-10 | 2 | one producer per transform | **MET 2026-09-27** — `sentiment.sentiment_asymmetry` (0 for a symmetric series) and `sentiment.event_study` (mean abnormal read against a declared pre-window baseline) |
| SENT-11 | 2 | one model + one transform | **MET 2026-09-27** — `sentiment.sentiment_uncertainty` (closed-form Shannon entropy over the pinned score histogram, `confidence = 1 - H*`) plus `sentiment.sentiment_output_map` (Φ/logistic/tanh, returning the map's name and the raw value beside the confidence) |
| FUND-15 | 2 | a dispersion producer | **MET 2026-09-27** — `strategies/factor_dispersion.factor_score_dispersion`, with `MaximumPossibleStd` DECLARED as the 0-100 scale's maximum population σ (50) and stated as a declaration, not a fit |
| FUND-16 | 2 | a weighted Δ-factor composite | **MET 2026-09-27** — `factor_dispersion.fundamental_momentum`: weighted Δ over a DECLARED lag and declared equal weights, plus acceleration and stability, refusing below `n + 1` periods |
| NEWS-5 | 2 | a scaled read, or a weight redistribution | **MET 2026-09-27** — `news_score.tag_category_read` over the declared `TAG_CATEGORIES` vocabulary (69 tags) with an importance severity, AND it is wired: the component's ramp was widened to the producer's own 0..1 scale (owner decision) and `_news_components` feeds it from the AV feed's per-article `topics[]`. `COMPONENTS['regulatory_legal'].producer` now names it |
| NEWS-7 | 2 | a sector-relative move, not breadth | **MET 2026-09-27** — `news_score.industry_shock(stock_returns, sector_returns)` and it IS fed: `analysis_tools._news_components` resolves the ticker's sector label to its SPDR ETF (the same map `get_relative_strength` uses), slices every bar after the trade date (`_closes_upto`) and passes the window's daily returns. Live MSFT 2026-09-25: `industry_shock = 0.0110` |
| NEWS-9 | 2 | a similarity measure + a weighted novelty | **MET 2026-09-27** — `news_score.headline_similarity` (dependency-free TF-IDF cosine), `duplicate_weight` (`W_dup = 1 - similarity`) and `weighted_novelty`, capped at 200 articles for the O(n²) pass |
| NEWS-12 / NEWS-13 | 2 | distinct horizon scores; a measured vector | producers exist (`multi_horizon_sentiment_regression`, `ic_term_structure`); the news engine is one 30-day window with a hardcoded table. **Needs a measurement** |
| EVT-9 | 2 | a measured panel row | **MET 2026-09-27 (owner: treat it as a 0-100 score)** — `event_state` moved from `ENGINE_NOT_SCORED` into `ENGINE_MODULES`, so the registry lists it with its declared component table and the panel carries its column; `ENGINE_NOT_SCORED` is now empty, kept as data so the old claim's reader finds the correction. **Its factors are event-driven** (calendars, filings, product dates), so on a price/fundamentals panel they report `measured: False` WITH their own reasons - the column is honest, not a fabricated score, and the engine's own 0-100 read still comes from the run's snapshot |
| MKT-13 | 2 | one test per producer | belongs to `MarketScore`, which does not exist. **Superseded by D1 (Phase 7)** |
| VAL-10 / VAL-12 / VAL-13 / VAL-14 / VAL-15 / VAL-17 | 2 | one producer per rank, `NA`-honest | belong to `ValuationScore`, which does not exist. **Superseded by D2 (Phase 7)** |
| MF-4 | 3 | a measured table or a WP-10 record per vector | **no engine prints a measured weight table**; every vector is still `RESEARCH_ONLY` (the record still reads `n_measured 0`) |
| MF-5 | 3 | a live run reporting 11 measured, or a named reason each | **MET 2026-09-27 on the second clause** — live MSFT 2026-09-25 measures **6 of 11** (relevance, materiality, novelty, corporate_events, industry_shock, persistence), and each of the other five carries its own reason: `fundamental_impact` (no revenue/margin-impact producer exists), `guidance_change` (behind `enable_benzinga_surface`, off by default), `regulatory_legal` (the NEWS-5 classifier exists but its declared ramp is a different scale - a rescale decision, not a missing producer), `earnings_surprise` (this run's catalyst snapshot carried no reported surprise in the window) and `analyst_revision` (the `enable_analyst_revision_index` gate is off). Was: 2 of 11 live, the rest without a producer |
| MF-6 | 3 | a revised `CATEGORY_WEIGHTS` with a record, or an owner sentence | neither; the table is unchanged. **Needs the owner's signature** |
| MF-8 | 3 | panel rows, or an owner sentence closing it | **CLOSED 2026-09-27 (owner decision)** — recorded permanently as panel-incompatible: `risk_score`'s inputs are position/book-level (`BookState`, cluster notional, ES) and `sentiment_score`'s are per-symbol vendor reads, so neither can be measured on the wide cross-sectional panel the way the fundamental and technical legs are. Their vectors stay `RESEARCH_ONLY` with that reason rather than waiting on a run that cannot exist |
| FUND-24 | 3 | a measured vector + OOS evidence → `VALIDATED` | `STATUS_RESEARCH_ONLY`; nothing promoted |
| RLW-4 | 3 | `scorecard_status(...)["movement"] != "UNAVAILABLE"` | no run reaches `VALIDATED`; `Movement` stays `UNAVAILABLE` |
| PLAN-5 | 3 | both scripts exit 0 | **MET 2026-09-27** against §9's own per-tool bar (`report_verify` → exit 0 **on `CONFIRMED`**; `verify_sweep` → **no new `SUSPECT`**) on `reports/MSFT_20260927_001700`: **0 `CONFIRMED`** both ways, **148 GROUNDED**, and the single `SUSPECT` was already flagged in the pre-fix run. Both processes still *exit* 1 — the sweep's exit covers the `SUSPECT` class and the verifier's covers any `FLAG` — and the one flag is a **correct detection** (a frozen report's own 16-into-15 ticker miscount), so a literal exit 0 would need that report regenerated, not the checker loosened. See §6.1 |
| RLW-2 | 4 | no `_call_engine` from the block | **MET 2026-09-27** — `_call_engine` is deleted and the fallback with it: `engine_score_block` now returns `""` without a snapshot, exactly like `scorecard_context_block` and `engine_report_section`. All four analysts pass `snapshot=state.get("quant_scorecard")`, so the run path is unchanged and one prompt can no longer carry two values for one engine. The two tests that pinned the fallback were replaced by one asserting its absence |
| NEWS-1 | 4 | the 20-weight component stops printing NA | **MET 2026-09-27** — `_news_components` supplies `materiality` from the catalyst snapshot's `implied_move` (the same figure EventScore reads, owner Q6). Live MSFT 2026-09-25: `materiality = 0.0661`, and the absent set shrank from five components to the four with no producer at all. **And it found a defect:** the surprise leg passed the snapshot DICT to `last_earnings_surprise`, which takes the vendor calendar LIST - every row was a `str`, so `earnings_surprise` could never measure (proven: `AttributeError: 'str' object has no attribute 'get'`) |
| the two mislabelled producer strings | 4 | the strings match the producers | **MET 2026-09-27** — the `persistence` declaration cites only `sentiment.mention_volume` (the wired half) and names `news_score.news_persistence` as a DIFFERENT measure, not this component's producer; the self-contradictory note is gone. `crowd_ratio`'s string was already correct |

**Phase 0's two residual nits** (outside the rows §3 names): `CompositeTradeScore.md:240` still reads
"the N-deflation question is open (decision 12)" with no marker — the same dangling reference §3.1
corrected at §3.5 — and `ScoreUniverse.md:503`'s Appendix-A citation still says "the
`donchian_channel:413` gap". Both are corrected in the same round as this audit.

**The other direction — documents that now under-report the tree.** `RiskScore.md` §8.1/§8.2 still mark
ABSENT nine quantities that Phases 1-2 built and tested: §2.4/§2.5 σ20/§60
(`book_risk.py::volatility_window_ratio:1633`), §3.3/§3.4 downside/upside beta
(`strategies/regime.py::upside_downside_beta:1871`), §6.4 Sterling (`book_risk.py::sterling_ratio:1691`),
§9.4/§9.5 + §10 the loss-frequency family (`book_risk.py::loss_frequency_family:1726`), §23
momentum reversal (`book_risk.py::momentum_reversal:1810`), §34 `P(R<0)` (`book_risk.py::prob_loss:1464`),
§58 tail-adjusted return (`book_risk.py::_tail_adjusted_return:1841`), §63 the nonlinear penalty
(`book_risk.py::_nonlinear_risk_penalty:1969`) and §68 liquidity-adjusted CVaR
(`book_risk.py::_liquidity_adjusted_cvar:1876`) — each exercised in `tests/test_risk_scalars.py`.
Three of them stay underscore-private, awaiting a leaf that holds both inputs.

**What this audit does not say.** Every row above still respects the constraints the phases were run
under: no fabricated number, no gate or size changed, and each absent quantity carries its reason. The
defect is in the *reporting* of the round, not in the work — a phase is not done because most of its
rows are. **Where each absent row's unblocking route is recorded:** §5.1, re-probed 2026-09-27 — 18 of
the 21 absent-producer rows are `REPO_SIDE` or `FEEDABLE_NOW`, one is `NO_SOURCE`, and the rest turn on
a definition or one vendor entitlement.

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
