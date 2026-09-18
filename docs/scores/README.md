# Score engines — master design

**The design set.** One document per score engine plus this master:

| Engine | Document | Owner's weight table | Readiness |
| --- | --- | --- | --- |
| FundamentalScore | [`FundamentalScore.md`](FundamentalScore.md) | 106 factors, 10 categories | largely computable; the ledger names the third that is not |
| TechnicalScore | [`TechnicalScore.md`](TechnicalScore.md) | 9 categories | **no composite exists**; components do |
| RegimeScore | [`RegimeScore.md`](RegimeScore.md) | 8 categories | **two independent paths**, no score |
| NewsScore | [`NewsScore.md`](NewsScore.md) | 9 categories | **5 of 9 ABSENT** |
| SentimentScore | [`SentimentScore.md`](SentimentScore.md) | 10 categories | mostly buildable, four holes |
| EventScore | [`EventScore.md`](EventScore.md) | *(none given)* | occurrence producers exist for 4 of 7 families |
| RiskScore | [`RiskScore.md`](RiskScore.md) | 8 categories | **no 0-100 risk score exists anywhere** |

The build order is [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) - the
prerequisites, the seven workstreams, the phases, the verification requirements
and the decisions still open. Two cross-cutting documents sit beside it:
[`ResearchLayerWiring.md`](ResearchLayerWiring.md) - how the scores reach the
research and debate layer, and the defects on that seam (§3.5) - and
[`MEASUREMENT_FINDINGS.md`](MEASUREMENT_FINDINGS.md), Phase C's live panel.

The owner's own specification of record is preserved verbatim, unedited, in
[`../ScoreWeight/fundamental.md`](../ScoreWeight/fundamental.md),
[`../ScoreWeight/market.md`](../ScoreWeight/market.md) and
[`../ScoreWeight/news_sentiment.md`](../ScoreWeight/news_sentiment.md). **This
document set is what interprets them against the engine**; where the documents
and the specs disagree, the specs govern the *intent* and the documents govern
what is *buildable*.

Status: **built (2026-09-18).** Every engine in this set - the shared kernel, the eight engines, the composite and the measurement layer - is implemented, and every gate ships **off** by default (`default_config.py`), flipped one at a time under the dark-launch protocol (§5). The design below is the contract the code is held to; `IMPLEMENTATION_PLAN.md` §9 carries each phase's **Exit - MET** block, and §3.4 records the one defect found by exercising the path rather than reading it.

Scope of this master: the architecture, the cross-engine rules, the composite and
its gate rules, the weight reconciliation between the owner's two iterations, the
**code defects the inventories found**, the wiring contracts, the phase plan, the
verification requirements, the decision record and the open questions. Each
engine's components, producers and gaps are in that engine's own document.

---

## 1. The architecture

### 1.1 Seven engines, not one composite

The owner's staged specification keeps the scores **completely separate** rather
than building one giant 250-300 factor composite:

```
                    STOCK
                      │
   ┌──────────┬───────┴───────┬──────────┐
   ▼          ▼               ▼          ▼
FUNDAMENTAL  TECHNICAL      REGIME      RISK          NEWS    SENTIMENT   EVENT
   │          │               │          │              │        │          │
   ▼          ▼               ▼          ▼              ▼        ▼          ▼
Fundamental Technical      Regime      Risk           News   Sentiment   Event
  Score       Score          Score      Score          Score     Score     Score
   │          │               │          │              │        │          │
   └──────────┴───────┬───────┴──────────┴──────────────┴────────┴──────────┘
                      ▼
              DECISION / OPPORTUNITY ENGINE
                      ▼
              Entry / Hold / Exit
                      ▼
                 Position Size
                      ▼
                 HARD GATES
```

The reason is diagnostic, and the owner states it: with four separate numbers you
can say *"excellent fundamental profile, constructive longer-term trend,
deteriorating short-term momentum, elevated risk"*; with one `MarketScore = 63`
you cannot. The repo already agrees — its own history is a **funnel over a single
score** (round 3 §S3, `design_institutional_value_dip_workflow.md`).

### 1.2 Direction convention — 100 = favourable, for every engine

Every engine scores **0-100 with 100 = favourable**. For RiskScore that means the
score is **inverted** relative to how risk is normally measured: a *high*
`RiskScore` means *low* risk. The alternative (high = dangerous) was rejected
because a reader comparing `Fundamental 88 / Technical 61 / Regime 68 / Risk 54`
must not have to remember that one of the four points the other way.

Consequence: **every component prints its raw value with units and sign beside
its aligned contribution.** The repo currently carries three incompatible
conventions for the same quantity (`CVaR` as a negative loss, as a positive
magnitude, and as an equity fraction; drawdown as a negative number and as a
labelled band; a notional cap and a correlation-cluster cap), and a single
aligned score would silently pick one of them. Printing both ends the ambiguity.


### 1.3 The engine map

| Engine | What it answers | Components with a real producer | Components ABSENT | Composite today |
| --- | --- | --: | --: | --- |
| FundamentalScore | *Is this a good business at a good price?* | see [`FundamentalScore.md`](FundamentalScore.md) §2 — the ledger marks all 106 | 0-100, advisory only |
| TechnicalScore | *What is this stock doing?* | 9 categories largely populated | the composite itself | **none** |
| RegimeScore | *What environment is this stock trading in?* | two independent paths | market-wide breadth, VIX percentile/term structure, credit | **none** |
| NewsScore | *What new information arrived, and how material is it?* | 4 of 9 categories | novelty, materiality, fundamental impact, guidance change, corporate events, persistence | **none** |
| SentimentScore | *How is the market positioned around it?* | 6 of 10 categories | 20-day momentum, acceleration, per-source breadth, institutional on this surface | **none** |
| EventScore | *Is a high-impact event happening now?* | 4 of 7 families | product/clinical, court, investor day | **none** |
| RiskScore | *How much can this hurt?* | all 8 categories as components | the aggregation | **none** |

**"Composite today: none" is a grep result, not an impression.** No 0-100
technical score, no market-level regime score and no 0-100 risk score exists
anywhere in `TradingAgents` or `TradingExecution`; the only existing composites
in this space are the LLM-produced analyst scores (`SentimentReport.overall_score`
0-10, `agents/schemas.py:463`) and the deterministic per-factor libraries. A
score that does not exist cannot be quoted, and no document in this set may
imply one does.


### 1.4 The composite — research allocation, and the gate-order conflict

The owner's staged research allocation for the six weighted engines:

| Engine | Fundamental | Technical | Regime | Risk | News | Sentiment |
| --- | --: | --: | --: | --: | --: | --: |
| Research weight | **35%** | **20%** | **15%** | **15%** | **7.5%** | **7.5%** |

He labels these **research weights, not production truth**, and pairs them with
the empirical ladder (IC, Rank IC, ICIR, decile spread, monotonicity, turnover,
persistence, sector and regime robustness, redundancy, OOS) before any of them
may replace the deterministic baseline. **EventScore has no weight in this
table** — the open question is in `IMPLEMENTATION_PLAN.md` §13 Q7 and in `EventScore.md` §7.

Two conflicts inside the owner's own diagrams were **flagged, not resolved**.
**Both are now resolved by the owner (2026-09-17):**

1. **Gate order -> gates before sizing** (decision Q8). His first diagram puts the
   hard gates *before* position size; his staged diagram puts them *after* it. The
   engine implements **gates-before-sizing** - the gate verdict feeds
   `strategies/risk/sizing.py:144` - and this document keeps that, because a gate
   *after* sizing must unwind a size it has already authorised.
2. **Which composite governs -> both, as separate objects** (decision Q2, confirmed
   by the owner the same day). `TradeScore = 0.40F + 0.25T + 0.15R + 0.20K` is the
   **four-engine decision composite**; the staged table above is the **six-engine
   research allocation**. Different objects, different names, different jobs - so
   the two weight sets are not in conflict. Two ledger statements make it explicit:

   > **`RiskScore` is a `TradeScore` engine, not a risk gate.** `RiskScore`
   > contributes the `R` component to the four-engine `TradeScore`. Risk Gates
   > operate **downstream** of `TradeScore` and can hard-block a proposed action
   > regardless of the composite score.

   > **The six-engine Research Allocation and the four-engine `TradeScore` are
   > separate objects.** Fundamental, Technical, Regime and Risk feed `TradeScore`.
   > News and Sentiment participate in the Research Allocation for attribution and
   > do **not** directly contribute to `TradeScore`.

   `NewsScore` and `SentimentScore` can still be highly informative without being
   direct decision-score inputs: their information may affect research attribution,
   diagnostics, explanations and *potentially separately authorised sizing
   mechanisms* - but must not silently become a fifth/sixth `TradeScore` factor.

**What the composite is for** (owner, 2026-09-18). `TradeScore` is the
**highest-level quantitative evidence summary** this system produces: it answers
*how favourable is the total quantitative evidence*, across the four engines —
and that is what a human reviewer reads it as. It is **not** an autonomous
trading command, and `RESEARCH_ONLY` does **not** mean "do nothing". It means the
evidence has been summarised, and converting that summary into an action is
deliberately not this object's job.

A high composite with an unfavourable `K` is the clearest case. `F 92 / T 85 /
R 78 / K 35` is *not* the system saying "no trade"; it is saying **the
quantitative evidence is favourable overall, but the application is not
authorised to convert that evidence into a trade automatically**. The reviewer's
job — and the reason the four engines are reported separately rather than
averaged away — is to ask *why* risk is the low leg, inspect the underlying
metrics, valuation, catalysts, price action and portfolio context, and then
decide. "I agree, no trade" and "I disagree, that risk reading is temporary" are
both legitimate outcomes, and the platform exists to support exactly that
judgment. This is a **research-only quant system with human-in-the-loop
execution**; the separation below is what makes it one, not what makes the score
inert.

**A number is only as good as its coverage, and the reader must see both.** The
composite is consumed by a human making a manual decision, so `TradeScore 72` at
`coverage 68%` must never be read as "the system has reasonably strong
evidence" — it means **72 over 68% of the intended evidence**, with the missing
components named. The printed block carries the coverage and the absent list
beside the score for that reason, and the floor withholds the number entirely
rather than reporting a partial one as whole.

**What the composite may not do** (unchanged from the earlier pass, and the
reason the repo already behaves correctly): a composite score **never overrides a
hard gate**. 17 fail-closed checks live in `GATE_PRECEDENCE`
(`../TradingExecution/signald/contracts.py:42`); the risk governor never reads a
score; `risk_multiplier.combine` zeroes the soft product when a hard flag fires.
The acceptance case is `F 92 / T 85 / R 78 / K 35`: the composite's own read is
*"evidence favourable overall, risk conditions unfavourable"*, and the
**`NO NEW RISK` that follows is the downstream gate's verdict, not this
module's** — the composite neither produces it nor overrides it.

**Score, scale, state and confidence are four different outputs.** `RegimeScore
68` (a score), `RegimeScale 0.47x` (a sizing multiplier), `RegimeState
STRONG_BULL` (a label) and `RegimeConfidence 0.75` (how much to trust the first
three) must never be collapsed into one number. Sizing is not conviction:
volatility targeting sizes *inversely* to volatility, and fractional Kelly
discounts for estimation error.


---


### 1.5 The earlier four-score iteration — recorded, superseded in weights

The first iteration of this design (before the owner's staged spec) proposed
**four** scores — Fundamental, Technical, Regime, Risk — combined as

$$TradeScore = 0.40\,F + 0.25\,T + 0.15\,R + 0.20\,K$$

with every score on the same 0-100 convention and `RiskScore` inverted (100 =
low risk). The owner withdrew that weight vector as *the whole* production score
and staged the six-engine allocation of §1.4 - **but re-affirmed it on 2026-09-17
as the four-engine decision composite** (§1.4, ledger statements): the withdrawal
was of the four-score version as the entire score, not of `TradeScore` as the
decision object. **The four-score version is
kept here as the record** — it is what produced the direction convention (§1.2),
the four output types (score / scale / state / confidence), and the readiness
measurements that the engine map in §1.3 summarises. Where the two disagree, the
staged set governs (§3).

The owner's 2026-09-17 specification, refined the same day by three staged docs
(`docs/ScoreWeight/{fundamental,market,news_sentiment}.md`). **Separate** 0-100
scores, one per dimension, and only then a combination. The staged docs frame
the factor side as **four catalogs** — fundamental ~106, technical ~80-120,
market/regime ~50-80, risk/portfolio ~40-60, i.e. a **250-300 factor target
across the engines** — and make the point this document already enforces: *"106
does not mean your system has proven that 106 independent pieces of information
exist"* (FCF yield, price/FCF, normalized FCF yield and earnings yield overlap;
§3.2's redundancy leg is what handles it). The staged spec's formula is the same
renormalising mean this document specifies: `Score_j = Σ wᵢxᵢ / Σ wᵢ` over
normalised 0-100 factor scores, with missing factors excluded rather than scored
zero (`NA ≠ 0`, §3.2). The governing sentence is *"do not mix
them into one score too early"*, and there is literature behind it: Asness,
Moskowitz & Pedersen find value and momentum are **negatively correlated
(≈ −0.60)** and that separate sleeves / a 50-50 allocation historically beat
merging the signals into one ranking; composite-indicator practice recommends
keeping dimensions separate for root-cause attribution and to avoid a
**misleading cancellation** where one dimension deteriorates while the total
stays flat. The MSFT example in the owner's brief is exactly that case (strong
long-term trend, deteriorating MACD, RSI fallen, price below the 10/20 EMA,
swing setup NO) — a single "bullish" label would erase the disagreement.

---

## 2. Cross-engine rules (non-negotiable)

1. **`NA ≠ 0`.** A missing input reduces the *available* weight; it never becomes
   a zero that punishes the name. A missing metric is never manufactured from a
   generic factor. Every score prints its coverage. **A missing calendar is
   `unknown`, not "no event exists" and not a negative reading** - the four event
   calendars return `available | missing | not_applicable`.
2. **A score is not a rating.** Nothing feeds `decision_guardrail.SCORE_BANDS`;
   each engine carries its own band table.
3. **One number, one producer.** If two engines would read the same computation,
   that is a naming problem. The engine's rule is *one implementation, many
   readers* — and the documents must therefore name, per component, which
   producer it reads. The known couplings are in `IMPLEMENTATION_PLAN.md` §5 (the per-engine component maps). One is now explicit: **semivariance is owned by `TechnicalScore.md`** (§1 and §4) and read by `RiskScore.md`'s volatility leg, which names it as a dependency rather than re-deriving it.
4. **A composite never overrides a hard gate.** See §1.4.
5. **Measure, don't assume.** Anything that can only be a constant is labelled a
   constant, in the document *and* in the output.
6. **No weight vector is invented.** Every weight in this set is the owner's,
   labelled as a starting hypothesis, and every one is subject to Phase C of `IMPLEMENTATION_PLAN.md` §9.
7. **No `factor_score=NN` in prose.** The scores are tool leaves and printed
   blocks, not sentences the LLM may paraphrase. (Owner decision Q5.)

### 2.1 The anti-double-counting invariants (owner, 2026-09-17)

Each one names a way this set could silently collapse into fewer signals than it
claims. They are binding on every workstream, and `IMPLEMENTATION_PLAN.md` §13.2
carries them beside the decisions that produced them.

8. **One quantity -> one authoritative producer.**
9. **`EventScore` owns materiality and the expected move; `NewsScore` consumes
   it** - it does not build a second estimate.
10. **Book risk -> the composite. Name risk -> diagnostic/reporting.**
11. **Score -> decision information. Sizing multiplier -> sizing. Do not merge
    them.**
12. **Market regime -> market-level. Security regime -> name-level diagnostic.**
13. **Daily `TradeScore` -> daily inputs.** Intraday indicators remain leaves
    unless explicitly promoted.
14. **Directional volatility -> the semivariance ratio, NOT `sigma_up/sigma_down`**
    - the rule that stops the volatility factor quietly becoming a second momentum
    factor through drift contamination. Specified in `TechnicalScore.md` §1/§4.
15. **No derived quantity may have two independent authoritative producers.** A
    secondary implementation may be a **fallback**, a **validation cross-check** or
    a **diagnostic**, but it must not independently contribute to the same
    composite. Expected move, materiality, volatility, sentiment velocity,
    institutional sentiment and relative strength are all instances of this rule.
16. **Daily is the canonical horizon.** An intraday refresh does not make an
    intraday metric part of the daily score: `RSI_daily` and `RSI_intraday` are
    separate fields. Promotion is explicit, per metric - the full contract is in
    `IMPLEMENTATION_PLAN.md` §13.2.
17. **The research allocation and the decision composite are separate objects.**
    Fundamental, Technical, Regime and Risk feed `TradeScore`; News and Sentiment
    participate in the research allocation for attribution, diagnostics and
    explanation and do **not** directly contribute to `TradeScore`. **No engine
    enters the decision composite by adjacency** - an engine joins only by an
    explicit decision, never by being drawn next to the others.
18. **`RiskScore` is a `TradeScore` engine, not a risk gate.** It contributes the
    `R` component of the four-engine composite. The hard gates operate
    **downstream** of `TradeScore` and can block a proposed action regardless of
    the composite score. The two must never be drawn or implemented as one
    object, or the producer of one of the four numbers disappears.


---

---

## 3. Code defects found by the inventories (2026-09-17)

Found while grounding the seven engines against the engine. Each is a confirmed
defect with a named consequence and a pair of `file:line`s that disagree. **§3.1
is the set being fixed in this pass** (the owner's instruction); §3.2 is the rest,
recorded with their evidence.

### 3.1 Fixed in this pass (`ba50b5f` in TradingAgents, `a4f8ecf` in TradingExecution)

**All six are fixed, each with a regression test.** The before/after is recorded
where it is provable: a monotone uptrend and a monotone downtrend both returned
`regime=neutral` before the fix and return `bull`/`bear` after; the close-only
choppiness was `7.9e-07` (a 0-1 dispersion) against a `30.0` threshold; the
Donchian and PSAR flags were `None` in every call; the gap fill table printed
`0.8`/`2` as if measured and now prints `measured (280 historical common gaps)`.
Defect 5's fix is deliberately minimal: the field is `None` until something
measures it, rather than a `0.0` nobody computed.

| # | Defect | Evidence | Consequence |
| --: | --- | --- | --- |
| 1 | **A dead branch makes the regime label trend-blind on the default path.** `overlays.build_strategy_overlays` calls `regime_label(vol_pct, trend, 0.4)` while `regime_label`'s default `chop_threshold` is `0.30`, so `chop <= chop_threshold` is **always False** | `strategies/overlays.py:57` vs `strategies/regime.py:126-145` | with `vol_pct == 0.5` (the middle band, the common case) `get_regime_read` returns `neutral` **regardless of the trend input** — the trend leg is inert, and every report that quotes `regime=neutral` is quoting a constant |
| 2 | **Choppiness is passed on two incompatible scales.** `get_regime_components` compares chop against `chop_threshold=30.0` (0-100) while `overlays.py` hardcodes `0.4` against a 0.30 default | `agents/utils/analysis_tools.py:2176` vs `strategies/overlays.py:57`; producer `strategies/regime.py:87 choppiness` | the two callers cannot both be right; whichever is wrong makes its branch either dead (see #1) or always-on |
| 3 | **Donchian breakout is unreachable.** `donchian_channel` returns `breakout_up/breakout_dn = None` by construction ("closes not passed; caller derives") and **no caller derives them** | `strategies/technical_factors.py:377` | the Breakout component's most canonical input is ABSENT as a value while the function appears to compute it |
| 4 | **`parabolic_sar` is called without `closes`**, so its `below`/`exit` flag is unreachable | call at `agents/utils/analysis_tools.py:1160`; def `strategies/technical_factors.py:432` | the mean-reversion leaf prints the SAR level but never the flag its consumers would read |
| 5 | **`BookState.net_beta` is a dead field** — it has **neither producer nor reader** | `../TradingExecution/signald/risk/state.py:77`; every `BookState(...)` construction site omits it | a book-level beta leg is declared and never populated; the RiskScore's concentration component cannot use it, and a reader of the state sees a permanently-`None` field |
| 6 | **Gap fill probability / days-to-fill are constants**, not measurements | `strategies/market_session.py:178-193` (`fill_probability` 0.3/0.6/0.4/0.8 and `days_to_fill` 5/3/4/2, literals per branch) | the Gap/execution component is the weakest of the eight for a data reason, not a modelling one — and the report prints a lookup table as if it were measured |

### 3.2 Fixed in this pass (`2c05701`) — the remaining twelve

**All twelve are fixed, each with a regression test.** 10 of the 11 new tests
fail before the fix and pass after; the eleventh pins the producer key the graph
was misreading (it was correct at the producer and wrong at the reader, so it
cannot fail on the producer side). **Correction 2026-09-18: eleven of the twelve
are fixed — defect 16 is not. See the second correction below.**

**One correction to the table below:** defect 7's stated consequence was
overstated. The dead `acc +=` line could not change the result (the accumulator
was recomputed from the bins on the next line), and the AMAT read
(`va_low == poc == 169.56`, `va_high == 424.64`) is a *genuine* 70% band for a
bimodal distribution, not a broken sum. What was missing was any way to see
that — so the fix is the dead-line removal plus a new `value_area_pct`, printed
by the leaf.

**A second correction, made 2026-09-18: defect 16 is not fixed.** The `2c05701`
change made the compiled-context line *derive* `catalyst_window` from the
overlay's stamped snapshot — but the context is compiled **before** the graph
runs (`graph/trading_graph.py:645-647`) and the snapshot is stamped **after** it
(`:686`). The read is therefore always `None` and the line always prints
`catalyst_window=False`, exactly as before. Re-confirmed by execution against 160
persisted runs: 15 of them hold a snapshot whose own reader says the window is
active, while all 19 printed occurrences in the report corpus read `False`.
Carried as **D-11** (§3.5); it bounds WP-12 and needs an owner decision on which
resolution to take.

| # | Defect | Evidence | Consequence |
| --: | --- | --- | --- |
| 7 | `volume_profile`'s value-area accumulator is dead arithmetic (`acc` incremented then overwritten) | `strategies/technical_factors.py:688-692` | the value area can collapse to the whole price range — measured on `reports/AMAT_20260914_191359/tool_evidence.json:3341`: `poc=169.56 va_high=424.64 va_low=169.56` on a 424 close |
| 8 | `support_structure`'s primary branch is unreachable from its only leaf (no `atr_value` passed) | `strategies/value_dip.py:738` vs `agents/utils/value_dip_tools.py:1018` | "multi-month-base support" can never be emitted; only the 3%-proximity branch fires |
| 9 | `size.atr` returns **`0.0`**, not `None`, on insufficient data | `strategies/size.py:131-140` | an `atr is not None` caller reads "unknown volatility" as "zero volatility" — an `NA ≠ 0` violation (§2 rule 1) |
| 10 | `rank_sectors_multifactor` substitutes `0.0` for a missing percentile in the risk leg | `strategies/sector_rank.py:536` | a sector with unmeasurable drawdown is scored as if it had the **worst** percentile — `NA ≠ 0` violation |
| 11 | `get_position_risk_multiplier` takes `knife_factor` (0..1) from the LLM; no leaf computes the composite K | `agents/utils/quant_adds_tools.py:96-125` vs `strategies/knife_guard.py:156` | a "computed execution multiplier" is fed an invented factor; 0.0 (block) and 1.0 (no reduction) both look measured |
| 12 | `get_skill_read` accepts a 0-100 `trend_score` from the model and prints a folded number | `agents/utils/analysis_tools.py:9247` + `:9294-9300` | the report can quote `trend_score=72` / `Fold 60 + 12 = 72.0/100` with no producer behind either number (live evidence: `ToolCallLog/MSFT_tool_calls.jsonl:187`) |
| 13 | `chaikin_oscillator` returns an unbounded A/D-unit difference while the leaf labels it `(positive=buying pressure)` | `strategies/technical_factors.py:560` vs the leaf's suffix in `get_technical_factors` | the sign is a scale artefact, not a verdict — the AMAT tree shows `chaikin=869687.156 (positive=buying pressure)` beside `di- > di+` |
| 14 | A dead `implied_move_pct` key: the graph reads a key `build_catalyst_snapshot` never emits | `graph/trading_graph.py:966` vs `strategies/catalyst.py:219` | the premarket path silently loses the implied move |
| 15 | The premarket hard block is unreachable — the leaf never passes `catalyst_snapshot` | `agents/utils/analysis_tools.py:6561` (`get_premarket_review`) vs `strategies/pre_market.py:198-240` | a fail-closed path is dead: a catalyst block cannot REJECT through the premarket review |
| 16 | `regime_gate_read`'s `catalyst_window` veto is inert — no producer ever sets it | `strategies/regime.py:261` vs `strategies/catalyst.py` | the regime gate advertises a veto that can never fire. **NOT FIXED — see the correction below and §3.5 D-11** |
| 17 | `rule_signal_macd_hist_rising` (the only MACD-histogram-slope producer) has no production reader | `strategies/rule_eval.py:103` | the momentum sub-factor is unscoreable from any analyst leaf |
| 18 | `factors.momentum_multihorizon` is built and unreachable (whitelisted as legacy) | `strategies/factors.py:400` vs `tests/test_calc_agent_wiring.py:40` | a per-name 21/63/126/252 momentum vector exists and no analyst can call it |

**Still open** (recorded in the per-engine documents, not fixed here): the
`position_mult_by_side` catalyst argument is inert (`events.py:42` compares a
0..1 scale as if it were >1, so the beat/miss multiplier is only ever 1.0/0.5);
`get_earnings_calendar`'s `look_back_days` names a forward window
(`analyst_data_tools.py:33` vs `finnhub.py:195`); `get_tail_risk` passes a
close-price series as an equity curve to CDaR (`analysis_tools.py:4690`);
`portfolio_cvar` and `book_correlated_stress` re-implement the same
weight-normalisation rules twice; the two regime-path limitations (the
3-valued `vol_pct` proxy and `get_regime_components`' non-overlapping windows);
`get_macro_regime_read` requiring caller-supplied markers when the FRED leaves
hold the same data; and the NewsScore/SentimentScore wiring items in their own
documents. Defects 7, 8, 11, 12, 13, 17 and 18 are either arithmetic inside a
producer, or a producer/leaf pair that was never joined.

---

### 3.3 Found while writing the implementation plan (2026-09-17)

Five defects found by reading the set end to end to write
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (its §14 has the same table with
the consequences spelled out). **All five are fixed (2026-09-17).** Two - D-3 and
D-4 - turned out to be **code defects**, not documentation: this ledger said "none
of them code" until they were repaired.

| # | Defect | Evidence | Consequence | Status |
| --: | --- | --- | --- | --- |
| D-1 | **This document's §4 and §5 were stubs.** The restructure of `68931f3` left "Wiring and contracts" as two sentences and "Phased plan" as one paragraph that stopped mid-sentence | `README.md` as committed at `68931f3` | the set had **no wiring contract and no phase plan** - the two things an implementation needs. §4 and §5 above are now the pointer and the summary; the bodies are the plan's §3-§8 and §9 | **FIXED** - §4/§5 above are the pointers; re-verified 2026-09-17 |
| D-2 | **Cross-references to sections that no longer exist.** §6 cited §3.7.1/3.7.3/3.7.4/3.7.5/3.7.6, §3.8.2, §3.8.4 and §4.2; §7 cited §5.2/§5.3 and "§6 Phase C/D"; §1.4 cited §8.3. `FundamentalScore.md` cited "§8", §5.2/§5.3 and §6 Phase C/D | the master's headings end at §7 plus appendices; `FundamentalScore.md`'s end at §3.6 plus appendices. The pre-split document (`git show 68931f3^:docs/design_fundamental_factor_weight_model.md`) carried §3.7 (the four-score architecture), §3.8 (news/sentiment/event), §4 (decisions and refusals), §5 (wiring, with §5.1-§5.3), §6 (Phases A-E) and §8 (the decision record with §8.3) | a reader following a cross-reference landed nowhere. Every reference is now repointed at the live section (this document, the plan, or the engine document that owns the material) | **FIXED** - every reference repointed; re-verified 2026-09-17 by a headings-vs-references scan (the dead names survive only in this row, as the record) |
| D-3 | **The SEC `User-Agent` carries a placeholder contact** | `dataflows/sec_edgar.py:30` sends `TradingAgentsResearch/1.0 (... contact: research@example.com)`; the comment at `:28` states a descriptive UA with a contact is required | `example.com` is not a deliverable address; the SEC's published fair-access ceiling is 10 requests/second per IP and a reachable contact is what the policy asks for | **FIXED 2026-09-17** - `sec_edgar.py:33` carries the owner's reachable contact; the same string replaced the Wikipedia placeholder at `sp500_universe.py:124` |
| D-4 | **The per-tag fetch pattern is 11 requests where 1 would do** | `sec_edgar.get_financial_history:173` loops `_TAG_MAP:56-65` calling `_COMPANYCONCEPT_URL:66` once per tag (`:206-215`) | the `companyfacts` endpoint returns every tag in one payload; 11x the requests against a 10 req/s ceiling for the same data, and it is why extending the tag set is expensive as written | **FIXED 2026-09-17** - one `companyfacts` call for every tag (`_us_gaap_facts`), with the per-tag loop kept as the fallback; two tests, both failing against the pre-change module. Live smoke test 2026-09-17: MSFT rendered 6 annual periods from 2 requests (pre-change: 12), UA accepted |
| D-5 | **`enable_factor_model` is not a free name.** Three design documents describe it as "the score" gate, and `scripts/factor_model_train.py:7` consumes it for the **learned** advisory model | `default_config.py:899`; `design_qlib_integration.md:217`, `design_finrl_integration.md:251`, `implementation_plan_finrl.md:109` | a plan that reused it for the deterministic composite would silently couple two different objects; the plan's six engine gates are new names for this reason | **FIXED 2026-09-17** - all three documents now name the flag as the **learned** model's gate only, in the body and the seam table |

---

### 3.4 Found while explaining the set (2026-09-18)

One defect, found by walking a live example end to end rather than by reading the
set: the composite's **leaf** path never read the risk engine, so the number the
research agents were shown was not the number this design defines.

| # | Defect | Evidence | Consequence | Status |
| --: | --- | --- | --- | --- |
| D-6 | **`TradeScore`'s leaf assembler never read `RiskScore`.** `_trade_score_engines` carried three blocks (fundamental, technical, regime) and returned with the comment *"WP-5 fills `risk` in through its own public entry point, never its internals; until it lands the engine is absent"* — but WP-5 had landed (`strategies/risk_score.py`, `1260329`) and the sibling leaf had read it ever since | `agents/utils/analysis_tools.py::_trade_score_engines` vs `strategies/risk_score.py::risk_score`; the sibling leaf `get_risk_score` calls `_risk_components(ticker)` then `risk_score(vals)`, and the assembler's own test already patched `_risk_components` as if it were in the path | the leaf's `K` was **`None` unconditionally**, so `get_trade_score` never applied the owner's published `K = 0.20` and its coverage was capped at **80%**. The run-card path was never affected — `_run_card_trade_score` reads all four engine blocks — so **one vector produced two different numbers on two surfaces**. Measured on MSFT: the leaf printed `67.65` at 80% coverage; with the engine wired it prints `70.00` at 100% | **FIXED 2026-09-18** - the fourth block mirrors the other three (`_risk_components` -> `risk_score`); the regression test fails before the fix (`assert None == 74.0`) and passes after |

**How it was found, and why it matters.** The four engines were called directly
for a worked example and returned `fundamental 66.25`, `technical 62.61`,
`regime 79.78`, **`risk null`** — while `_risk_components('MSFT')` returned 13
real components and `risk_score` scored them **79.39**. Components present, score
withheld, and the stale comment naming a workstream that had already shipped.
This is the *third* instance of one failure shape in this repo (see
`CHANGELOG.md` 2026-09-18 (e) in `TradingExecution` and the `ba50b5f`/`2c05701`
sets): **a producer exists, a reader exists, and the wire between them was never
run.** A defect ledger built by reading documents cannot see it; only executing
the path can.

---

### 3.5 Found while designing the research-layer wiring (2026-09-18)

Found by executing both paths to the same number, again rather than by reading the
set — and recorded in full in
[`ResearchLayerWiring.md`](ResearchLayerWiring.md) §6. **The design that follows
from them is in that document**; this is the ledger.

| # | Defect | Evidence | Consequence | Status |
| --: | --- | --- | --- | --- |
| D-7 | **The leaf scores the wall clock, the card scores the run date.** `_trade_score_engines` called `fundamental_score_for_ticker(ticker)` with no date — so `fundamental_score_for_ticker` fell back to `datetime.now()` (`strategies/fundamental_score.py:550`) — while `_run_card_fundamental_score` passes `pm_decision.trade_date` | measured on MSFT for the documented `batch.py --date 2026-07-22` invocation (`batch.py:5`): leaf **`66.25`**, card **`62.50`**, identical basis string and `panel_n=9` | **one vector, two numbers on two surfaces** — and the leaf was the wrong one: it scored a July decision against September's peer panel | **FIXED** (`_trade_score_engines` gained `current_date`, mirrored from the sibling `get_fundamental_score`; two regression tests fail before the fix) |
| D-8 | **The D-6 class is not closed.** `_trade_score_engines` computes all four engines unconditionally, while `_run_card_trade_score` reads each engine from the sibling card block — which exists only when **that engine's own gate** is on | `agents/utils/analysis_tools.py::_trade_score_engines` vs `reporting.py::_run_card_trade_score` | with `enable_trade_score` on and any sub-gate off, the leaf and the card print **different composites** | **FIXED** (`P12-5`, 2026-09-18): both readers now take their four values from the run's snapshot through `quant_scorecard.engine_scores`, so one rule decides for all three surfaces. Fails-before proof by executing the pre-`P12-5` assembly from git: leaf **`84.55`** (risk `74.0` measured with its gate off) vs card **`87.19`**; both **`87.19`** after |
| D-9 | **A gate-on `enable_sentiment_score` is unreachable by any agent.** `sentiment_tools()` and `analyst_toolset("sentiment")` exist, but no ToolNode is built for the sentiment key | `graph/trading_graph.py:343-345` builds `market, news, fundamentals` only; `tests/test_tool_binding_single_source.py:50` asserts exactly that set; `agents/toolsets.py:533-538` records it as deliberate | the sentiment score can be computed and never read — so the scorecard must carry it through the snapshot, not an analyst's tool path | **deliberate, not a defect** — but it bounds the design |
| D-10 | **The structured debate's consensus exit is dead.** `structured_debate.py:644` reads `ds.get("independent_agreement")`; nothing writes that key — `independent_agreement` is computed as a local in `trading_graph.py:1770-1788` and never stored | already on the books at `docs/implementation_plan_defect_audit.md:51`, whose line references (`:605`, `:2208`) have drifted | the independent-consensus termination contour never fires; debates run to the cap | **pre-existing, open, outside this workstream** |
| D-11 | **The compiled context's `catalyst_window` can never be `True`.** `_compiled_decision_context` is called with `init_agent_state` **before** `graph.invoke` (`graph/trading_graph.py:645-647`), and `create_initial_state` sets no `strategy_overlays` (`graph/propagation.py`). The only writer of that key is `overlays.apply_overlay_to_state` (`overlays.py:178`), called from `_apply_strategy_overlays` **after** the graph (`trading_graph.py:686`). So `cat_snap` at `trading_graph.py:1275` is always `None` and `catalyst_window` is always `False` | 160 persisted runs carry `strategy_overlays`; **15** hold a snapshot whose own reader (`pre_market.catalyst_window_read`) says the window is **active** (`scale` 0.25/0.6, verdicts `earnings-window`/`fed-catalyst`); all 19 printed `catalyst_window=` occurrences in the report corpus read `False`; executed on NFLX 2026-09-15 (`fed-catalyst`, `scale` 0.6) the context printed `verdict=tradable pass=True reasons=['volatility contained + no fast downtrend + no catalyst']`, where the snapshot implies `verdict=catalyst-window pass=False reasons=['catalyst window open']` | the context **asserts "no catalyst"** for runs whose own snapshot says a catalyst window is open — a false positive assertion reaching ten prompt sites, not an honest `NA` | **open — confirmed implementation defect, semantic resolution pending.** The `2c05701` "FIXED" claim for defect 16 (§3.2) is wrong. The resolution is a **contract decision with a fixed sequence** (contract first, ordering second) and a hard constraint that it must not move the decided `RegimeScore → EventScore` boundary — recorded in `ResearchLayerWiring.md` §6.4. Bounds WP-12: the event engine cannot enter the pre-graph snapshot |

**Two stale claims on this seam, both corrected in the same pass.** They are the
D-6 failure mode — a stale line hiding a wire — and both understated what the
research layer already receives: `agents/utils/agent_states.py` described
`computed_decision_context` as reaching "the Trader, Portfolio Manager and the 3
risk debators" when it in fact reaches **ten** prompt sites, the L1 ground-truth
registry and report section `IVa`; `docs/design_risk_calculations_agent_wiring.md`
§3 recorded the bull/bear researchers as having *"no computed context"* and the
Research Manager as *"none (plan from debate)"*, both false.

**The finding that motivates the whole design.** The eight engine scores reach
exactly two surfaces — a gated tool leaf and `run_card.json` — and
`run_card.json` has **no reader in the research layer at all**: the executor
explicitly ignores it (`TradingExecution/signald/watch.py:6-8`), the web UI reads
only `*.md` (`trading_web/backend/capabilities.py:1699`), and `complete_report.md`
is built from state keys alone (`reporting.py:1788`). Meanwhile
`computed_decision_context` — one deterministic string, built once at
`trading_graph.py:649` — already reaches all ten prompt sites, is parsed into the
L1 verifiable-claim registry, and is rendered as report section `IVa`. **One
producer, three readers, already wired**; the scores simply are not in it.

---

## 4. Wiring and contracts

**The contracts are in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §3-§8** -
the prerequisites, the shared kernel, the per-engine component maps, the advisory
surface, the measurement layer and the composite boundary. The two paths this
section exists to separate are still worth naming here, because the blast radius
differs by an order of magnitude:

- **The cheap path** is a tool leaf: a pure function over inputs the run already
  fetched, printed beside the evidence, reading no gate and sizing nothing. Every
  engine in this set ships this way first.
- **The expensive path** is a number on the wire: a producer-owned 0-100 value the
  executor may rank on. `opportunity_score` is that slot and it stays `null`
  (§7 Q1) - the reason string is the only part of it that ships.

**Two couplings the wiring must respect** (rule 3): `get_news_sentiment_series` is
bound to both `news_tools()` (`agents/toolsets.py:352`) and `market_tools()`
(`:279`), and `news_relevance.score_news_article:53` **is** the confidence weight
of `sentiment.aggregate_weighted_sentiment:616`. One producer feeding two readers
is the repo's rule; the separation is enforced by **naming the producer per
component**, which is what `IMPLEMENTATION_PLAN.md` §5 does row by row.
---

## 5. Phased plan

**The phase plan is [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §9** -
Phase 0 (the data and wiring prerequisites), A (the kernel plus the two engines
whose components already exist), B (the environment, the risk and the event
state), C (measure, don't assume), D (news and sentiment), E (the composite).

Each phase is **default-off behind its own gate**, flipped **one at a time** under
the dark-launch protocol (ground rule 10): a labelled run on the same basket, a
`scripts/repro_check.py --evidence` diff against the gate-off run, then
`scripts/report_verify.py` and `scripts/verify_sweep.py` exiting 0 on
`CONFIRMED`. The gate names are in the plan's §1.1, with the collisions to avoid:
`enable_factor_model` already means the *learned* advisory model
(`scripts/factor_model_train.py:7`), `enable_factors` and `enable_regime` are
documented **inert** (`.env.example:470-471`, `tests/test_gate_env_toggles.py:87`),
and `enable_score_eval_rows` already gates the IC harness
(`scripts/strategy_quality_report.py:340`).
---

## 6. Verification requirements

- Every new pure function gets a test that **fails under a mutation** of the
  code it guards (ground rule 4). For a composite: flip a direction sign, drop
  the coverage floor, remove the renormalisation — each must break a test.
- The renormalisation and coverage behaviour is pinned on a synthetic panel with
  known answers (a name with 3 of 7 metrics present must be withheld at
  `min_coverage=3` if the floor resolves above 3, and scored otherwise).
- Weights must be **printed**: a test asserts the `basis` string contains the
  weight vector actually used, so no run can silently change its weights.
- No factor may be scored from a vendor passthrough without the leaf saying so.
- With the gate off, the tool must not exist in the toolset and the run output
  must be byte-identical (the existing gate convention).
- `metric_reconcile` / `disagreement_flag` must fire on a synthetic
  two-vendor disagreement, proving the confidence leg can fail.
- **`NA ≠ 0` is pinned (Q3):** a panel where one factor is absent for a name
  must renormalise over the present factors and never score the absent one as
  `0`; a name below the coverage floor is withheld with its reason, and a
  `sector_scope` factor with no supplier contributes no weight at all.
- **No score in prose (Q5):** a test asserts no analyst prompt string requires a
  composite score in the narrative (the existing
  `tests/test_analyst_evidence_wiring.py` pattern for named rule strings is the
  place), and that the score reaches the reader only through the structured
  leaf / `run_card` block.
- **Validation status is pinned (Q4):** a panel below the cross-section floors
  reports `INSUFFICIENT_CROSS_SECTION` and yields no weight vector; the test
  must fail if the label is dropped.
- **The composite is not on the wire (Q1):** a test asserts the advisory score
  does not reach `research_decision.json` / `opportunity_score`, and that the
  reason constant is present and stable when that key is added.
- **Direction is pinned per component (master §1.2, and each engine document’s component ledger):** a test asserts each component's
  raw value and its aligned contribution have the declared relationship (e.g.
  inverting the alignment must move the score the other way), and that the
  `RiskScore` leg is *inverted* relative to its producers' native loss sign.
- **The five polarity conflicts stay declared (TechnicalScore.md §0.3):** RSI, MFI, stochastic,
  the elder thermometer and the support-proximity read must each carry their
  polarity, and a mutation that makes one of them monotone must fail a test.
- **`TradeScore` cannot unlock a gate (master §1.4):** a test drives the executor's
  gate to BLOCK and asserts a maximal `TradeScore` changes nothing — the same
  shape as the existing `risk_multiplier.combine` hard-flag test.
- **Score and scale stay separate (master §1.4):** a test asserts the regime sizing
  scale is not an input to `RegimeScore` and vice versa, so a hostile regime
  cannot rewrite the score and a good score cannot inflate the size.
- **Arbitration is recorded (master §1.4):** whichever regime producer a component
  reads, the leaf names it, and a test asserts the name is printed.

---
---

## 7. Decision record (owner, 2026-09-17)

**The three research-layer decisions of 2026-09-18 are in
[`ResearchLayerWiring.md`](ResearchLayerWiring.md) §9** — the scorecard's gate
(one master gate, independent engine gates, partial made explicit), movement held
until the vector is validated, and the **preservation** of the composite's printed
`basis` contract, whose purpose line goes on the new surface instead. **All three
are design decisions for `WP-12`, which is not yet built; none of them changes a
shipped string.** D3 was answered twice — the first answer was implemented in
`02145fe` and reverted on the second — and §9.1 records both, because the reversal
is part of the seam's history.

**The twelve architecture decisions of the same day are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13** — the canonical regime
path, the two composite names, the per-name/book `RiskScore` split, the moved
bindings, the sentiment toolset, EventScore's ownership of materiality, the structured event state, the gate order, the coverage sign, score-vs-sizing, the
daily horizon, and the semivariance measure. The five below are this document's own; the vendor
decision of 2026-09-18 follows them as Q6. **The owner's confirmation the same day of two ledger statements - `RiskScore`
is a `TradeScore` engine and not a risk gate, and the six-engine research
allocation is a separate object from the four-engine decision composite - is
recorded in §1.4 and, as binding rules 17-18, in §2.1.** The six items that sit
**outside** the score set - the three legacy-mode trees, the 25 poisoned trees, the
DISCLOSED-vendor-pair tradeoff, the weighting-decision UNSUPPORTED family, the
sentiment-score anchor when the computed block is absent, and intraday event-risk
sizing - are decided too, and recorded with their evidence in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13.4 and
[`../design_report_verification_llm.md`](../design_report_verification_llm.md).

The five questions this document opened are answered, and the vendor decision of
2026-09-18 is appended below them as Q6. Recorded with the rationale, because the
reasoning is what future changes have to respect.

**Q1 — Does a composite fundamental score ever reach `opportunity_score`?**
**Decided: (a) never, for now.** It stays a tool-leaf / `run_card` advisory
metric. *Rationale (owner):* "The current 'would dress an estimate up as a
measurement' rationale is sound." A deterministic `FundamentalScore = 84` does
not imply `Opportunity = 84` — a name can have outstanding fundamentals with
poor current opportunity characteristics (`FundamentalScore 92`,
`TechnicalScore 61`, `RegimeScore 68`, `RiskScore 54`, `ValuationScore 37`). The
distinction preserved is **measurement vs interpretation**: the artifact keeps
`opportunity_score: null` and gains a producer-owned
`opportunity_score_reason` (`IMPLEMENTATION_PLAN.md` §6).

**Q2 — Learned walk-forward weights?**
**Decided: yes, as a separate research/experimental layer — not in the
deterministic production score yet.** *Rationale (owner):* removing Phase 4
merely because the current rule is deterministic would be wrong; what matters is
that the learned vector is compared against the deterministic baseline on IC,
decile monotonicity, spread and stability, and does not become production "merely
because it improves in-sample results". Promotion is the ladder
`RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION`; the schema /
contract / hash migration is only reached at step three (`IMPLEMENTATION_PLAN.md` §6, §9 Phase D).

**Q3 — Sector overlays?**
**Decided: yes — architecture in scope now, suppliers deferred.** The factor
schema carries `sector_scope` / `supplier` / `availability` from the first
commit (`ROIC scope=ALL`, `NIM scope=BANKS`, `CET1 scope=BANKS`,
`ROTCE scope=BANKS`, `FFO_Yield scope=REITS`, `AFFO_Yield scope=REITS`,
`NAV_Discount scope=REITS`, `Occupancy scope=REITS`). Until a supplier exists
they are `NA`, **not zero** — *"missing data should reduce the available factor
weight, rather than punish the company"* — and the design must **not manufacture
missing metrics from generic factors** (master §2 rule 1).

**Q4 — Evaluation universe?**
**Decided: the full US panel** is the official validation universe; the
named basket stays a development/test universe and is labelled
`VALIDATION_STATUS = INSUFFICIENT_CROSS_SECTION` — *"rather than allowing it to
produce authoritative factor weights"*. The panel's fundamentals leg sources
from **SEC EDGAR XBRL** (free, keyless, point-in-time) as of 2026-09-18, not the
vendor's bulk-fundamentals endpoint. IC, ICIR, decile spread and
monotonicity only become meaningful with hundreds/thousands of eligible names
(`IMPLEMENTATION_PLAN.md` §9 Phase C).

**Q5 — `factor_score=NN` in prose?**
**Decided: no.** The number lives in structured output
(`fundamental_score`, `fundamental_score_status`,
`fundamental_score_confidence`); narrative states quality in words. *Rationale
(owner):* a bare score in prose "creates an apparent objective ground truth",
after which every verifier/report comparison asks why 84.2 and not 81.7, which
factor moved it, and whether 84.2 beats 78.4 — turning an **advisory composite
into a quasi-official measurement** (`IMPLEMENTATION_PLAN.md` §6).

**Q6 — Where do the panel's fundamentals leg and the forward event calendars
source from?** (owner, 2026-09-18.)
**Decided: three parts, all binding.** *(a) The panel's fundamentals leg sources
from **SEC EDGAR XBRL** — free, keyless and point-in-time — not the vendor's
bulk-fundamentals endpoint.* EODHD's Extended Fundamentals plan is priced "By
request" on the vendor's own page and is excluded from every published tier (EOD
$19.99 / EOD+Intraday $29.99 / Fundamentals $59.99 / All-in-One $99.99), so the
403 on `/api/bulk-fundamentals/NASDAQ` and `/api/fundamentals/AAPL.US` is
plan-gating, not spend-more; the one publicly priced bulk alternative (FMP's
Premium/Ultimate tiers) was not needed. The `companyfacts` payload is per-filer
and date-independent, so one request per filer serves every date (a 30-date
panel over 464 names = 464 requests, not 13,920), paced to the SEC's published
10 req/s ceiling; the read is **point-in-time** (only facts filed on or before
the panel date are eligible) and every leg is aligned to **one fiscal year** — a
tag with no value at the reference end is ABSENT, never substituted from another
year. Market cap is the panel's own close × the EDGAR cover-page share count
(`dei:EntityCommonStockSharesOutstanding`). Coverage limits are named per name in
`_meta.fundamentals_gaps` — no market cap from the source, no TTM, no
10-K/20-F/40-F row (pre-XBRL or IFRS), Beneish M unmeasurable for want of a
consistent marketable-securities concept — and never silently dropped; the
former `_meta.vendor_gate` is now `_meta.fundamentals_error`. Live 2026-09-18: 7
names at 17-25 metrics each, one named gap (TSM, an IFRS filer).
*(b) The forward company-event calendars.* **pdufa.bio** answers the FDA /
clinical family (free, keyless, 1,000 req/day), which makes `product_clinical`
**SCORABLE**; **CourtListener** — the owner's pick for the court family —
**cannot answer**: it is a filing archive, its docket endpoints need a token and
its anonymous search exposes only `dateArgued` / `dateFiled` / `dateTerminated`,
all backward-looking (zero future-dated rows across three live result sets), so
`court` stays **`missing`, not `not_applicable`**; the **investor-day family is
DROPPED** by owner decision, because no free source exists. Only
`date_precision == "day"` rows become forward events (pdufa.bio nulls `date` for
month/quarter/year precision since 2026-09-09), and the undated rows are counted,
not discarded: `event_calendars.calendar_coverage` prints `rows_held` beside
`rows_with_announced_day`.
*(c) The calendars' gate is **`enable_event_calendars`, default False, SEPARATE
from `enable_event_state`*** — this is the one part of the state that leaves the
machine, so enabling the engine must not silently acquire a third-party fetch;
off leaves every family at the answer it had before the adapters existed.

---

## Appendix B — what the canonical vocabulary cannot express

From `dataflows/statement_parsing._ROW_ALIASES` (75-192): **35 keys**, aliases in
match-priority order. The factors in §2 marked ABSENT are bounded by these gaps,
not by missing formulas:

| Missing key | Blocks |
| --- | --- |
| `ebitda` | #7 EBITDA margin, #21 EBITDA growth, #33/#34 FCF\|OCF ÷ EBITDA, #60 net debt/EBITDA |
| `deferred_revenue` | #79 (and `revenue` deliberately excludes `deferred`/`unearned` labels) |
| `goodwill` / `intangibles` | bank P/TBV reasoning, ROTCE |
| R&D / advertising (referenced by `growth_metrics` but never aliased) | G-Score G6/G8 legs |
| `roa_series` / `revenue_series` | #80 earnings volatility, G-Score G4/G5 — produced since 2026-09-17 (§1.4), still bounded by the 4-5 year vendor history |
| multi-year tag series | #14/#17/#18/#20/#23/#38/#90 CAGR family |
| segment data | any segment-level factor (vendor passthrough only) |
| bank/REIT operating metrics | NIM, CET1, ROTCE, FFO, AFFO, NAV, occupancy, non-performing loans, deposit growth, efficiency ratio |
| debt maturity schedule | #100 |

Keys that exist with **zero code consumers** (their only mentions are the alias
table and the `quantitative_scores.py` vocabulary docstring): `interest_expense`
(#64, #98), `share_buybacks` (#92, #94), `debt_repayment`; plus `sga`, `cogs`
and `retained_earnings`, which are read only inside Beneish/GP-A/Altman.

---
---

### C.2 Evidence ledger for the score architecture

| # | Source | Used for |
| --: | --- | --- |
| 13 | Grinold & Kahn, *Active Portfolio Management* — the risk model is built and used separately from the alpha model; "risk is not alpha"; the optimiser trades alpha against a risk forecast | `RiskScore` as its own dimension, and the rule that it is not an alpha factor (RiskScore.md §5) |
| 14 | Sizing practice: volatility targeting sizes *inversely* to volatility; fractional Kelly discounts full Kelly for estimation error; conviction is bounded by volatility, correlation and drawdown tolerance | the score ≠ scale separation (`RegimeScore` 68 vs `RegimeScale` 0.47x, master §1.4) and `TradeScore` not being a size |
| 15 | Rockafellar & Uryasev — CVaR/expected shortfall is convex and optimisable as an LP; ES/CVaR is **coherent**, VaR is not (subadditivity) | the tail-risk component's measure choice, and why the loss-sign conventions must be pinned (RiskScore.md §0.3) |
| 16 | Moreira & Muir, volatility-managed portfolios — scaling by inverse recent variance raised Sharpe in the original evidence (50-100% of the original), with later work finding no systematic improvement | the sizing multiplier's existence *and* its limits: it is a sizing rule, not a score input |
| 17 | Moskowitz, Ooi & Pedersen (time-series momentum, 1-12 months, across asset classes); George & Hwang (nearness to the 52-week high) | the trend and momentum components are the best-supported legs; `high_distance` already exists here |
| 18 | Technical-indicator evidence quality: ADX is non-directional and lagging with little standalone predictive power (best used as a filter); volume is a **confirmation** variable, not a standalone predictor | ADX belongs in Trend *strength*, not as a directional signal; the volume component (10%) is a confirmer |
| 19 | Jegadeesh (1990) — short-term reversal ≈2%/month at a one-month horizon; De Bondt & Thaler (long-horizon overreaction, a different mechanism) | the mean-reversion component is real but small — consistent with its 5% weight |
| 20 | Asness, Moskowitz & Pedersen, "Value and Momentum Everywhere" — value and momentum are negatively correlated (≈ −0.60); separate sleeves / 50-50 allocation historically beat merging the signals into one ranking | **the evidence for "do not mix them into one score too early"** (master §1.1) and for a dimension-level combination layer rather than factor-level blending |
| 21 | Composite-indicator practice — decomposed dimensions give root-cause attribution and avoid a **misleading cancellation**; a composite is defensible when its components belong together | four scores, printed with their components and their attribution (master §1.4) |
| 22 | Regime detection: Hurst exponent and variance ratio are complementary *shape* diagnostics (VR(k) ≈ k^(2H−1)), not robust regime detectors on their own; Markov-switching models infer the volatility state and its persistence (expected duration 1/(1−p)) | the choppiness/persistence component's role and its limits (RegimeScore.md §0.3) |
| 23 | Liquidity and gap risk: Amihud measures price impact per unit of volume, the bid-ask spread measures execution cost, and overnight gap risk is neither — size on the plausible gap, and cut overnight/event exposure to roughly 25-50% of normal; earnings implied move is read from the ATM straddle | the liquidity, gap and event components' distinct measures, and the event-risk sizing rule (RiskScore.md §5) |
| 24 | Hard-constraint practice — risk, leverage, liquidity and mandate limits define the feasible set **before** optimisation; expected return never overrides a hard risk limit | `TradeScore` never overrides a hard gate (master §1.4), which the repo already implements (17 fail-closed checks, `GATE_PRECEDENCE`; `risk_multiplier.combine` zeroes the soft product on a hard flag) |
| 25 | Tetlock, "Giving Content to Investor Sentiment" — media pessimism predicts **next-day declines then a reversal within days**; extreme pessimism predicts **volume**; low returns produce more pessimistic tone (a feedback loop) | sentiment is short-horizon and partly reversing, not a permanent alpha weight; and the price→sentiment feedback is why the confirmation check exists (SentimentScore.md §0.2, §0.3) |
| 26 | Baker & Wurgler, investor sentiment — high sentiment predicts **lower** subsequent returns, concentrated in hard-to-value, hard-to-arbitrage names | the sentiment leg is contrarian in the cross-section and name-dependent; supports the small research weight |
| 27 | Barber & Odean (attention-based trading) and the limited-attention reading of PEAD — fresh, salient news is incorporated immediately while stale or competing information drifts | NewsScore's novelty/materiality emphasis is the right shape, and the one strong leg (earnings surprise + drift) is already implemented |
| 28 | Da, Engelberg & Gao and the StockTwits literature — **attention** spikes predict negative next-day returns while **bullish sentiment** predicts positive ones; small caps are more sensitive to both | attention and sentiment are different signals with opposite short-horizon signs and must not be merged (SentimentScore.md §0.2 point 3) |
