# Design: The Score Context Contract — mandatory engine evaluation, supplied results

**Status: design only — no code changed (2026-09-19). All four open questions were
closed by the owner on 2026-09-19 — see §13.**

Specifies how the eight score engines become **mandatory and deterministic**, and
how their results — score, coverage, and supporting measurements — are **supplied
into the LLM context** rather than left to tool-calling discretion.

Companion to:
- [`README.md`](README.md) (the master architecture and the cross-engine rules),
- [`ResearchLayerWiring.md`](ResearchLayerWiring.md) (the engine ownership map and
  the three levels of visibility),
- [`../design_mapreduce_forced_tool_gathering.md`](../design_mapreduce_forced_tool_gathering.md)
  (the existing deterministic gatherer this design builds on),
- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (the phase plan and the
  per-engine component maps).

---

## 0. The one-sentence change

> **The LLM must not decide whether a mandatory scoring calculation happens, but
> it must receive that score, its coverage, and its supporting measurements
> before forming its thesis.**

This does not replace the LLM. It removes the LLM's ability to **implicitly invent
the weighting** of hundreds of measurements on every run.

---

## 1. The problem this closes

Before the score system, the shape was:

```text
raw measurements  ->  LLM  ->  BUY / SELL / HOLD
```

The LLM saw a flat list — strong fundamentals, RSI 53, positive regime, high
volatility, expensive valuation — and had to decide, silently and afresh each
run, **how much each item mattered**. The weighting was implicit, unauditable,
and not reproducible.

The score system moves the weighting into code:

```text
raw measurements  ->  deterministic producers  ->  8 engines  ->  explicit weights  ->  composite
```

But moving the *math* into code is only half of it. If the engines run but the
LLM never sees their output — or sees only a bare number — the LLM re-derives its
own implicit weighting anyway and the improvement is lost.

---

## 2. What is already deterministic (verified 2026-09-19)

**The engines already run in code, not in the LLM.** The scorecard is built at
graph setup, gated on the master gate:

```python
# tradingagents/graph/trading_graph.py:651
if self.config.get("enable_quant_scorecard"):
    ...
    snapshot = quant_scorecard(company_name, trade_date, self.config)   # :658
```

No LLM call participates in producing an engine score. This is the foundation the
rest of the design rests on — **the measurement is already non-discretionary**.

**The placement of each engine's result is already a single table.** The engine
ownership map (`f2755c2`) made `quant_scorecard.ENGINE_SECTIONS`
(`tradingagents/strategies/quant_scorecard.py:119`) the one source of truth, with
the tool binding and the prompt fragment **derived** from it rather than restated:

| Symbol | Site | Role |
|---|---|---|
| `ENGINE_GATES` | `quant_scorecard.py:70` | the eight per-engine gates |
| `COMPOSITE_ENGINES` | `quant_scorecard.py:86` | the four that feed `TradeScore` |
| `ENGINE_TOOLS` | `quant_scorecard.py:89` | engine -> its `@tool` leaf name |
| `ENGINE_SECTIONS` | `quant_scorecard.py:119` | engine -> its report section (`None` = report-level) |
| `ANALYST_SECTIONS` | `quant_scorecard.py:131` | the four analyst sections |
| `engines_for_analyst` | `quant_scorecard.py:134` | the derived ownership query |
| `engine_score_tools` | `tradingagents/agents/toolsets.py:450` | the derived **tool binding** |
| `engine_score_block` | `tradingagents/agents/utils/report_hygiene.py:77` | the derived **prompt fragment** |

So the placement contract exists. **This document specifies the delivery contract
that sits on top of it.**

---

## 3. The three discretionary surfaces that remain

Enumerated against the tree, not assumed.

### 3.1 The engine result is also a callable tool

`engine_score_tools(analyst_key)` (`toolsets.py:450`) binds each owned engine as a
**tool the model may or may not call**:

```text
market        owned=('technical',)          bound_as_tools=['get_technical_score']
news          owned=('news', 'event')       bound_as_tools=['get_news_score', 'get_event_state']
fundamentals  owned=('fundamental',)        bound_as_tools=['get_fundamental_score']
sentiment     owned=('sentiment',)          bound_as_tools=['get_sentiment_score']
```

**A tool the model may decline does not satisfy the invariant.** The model can
conclude *"TechnicalScore looks sufficient, I will skip the others"* — which is
precisely the discretion this design removes.

### 3.2 Raw tool selection is still model-driven

`analyst_forced_tools` (`tradingagents/default_config.py:199`, consumed at
`tradingagents/agents/utils/evidence_gather.py:553`) makes the *raw tool* set
deterministic when it is set. It is **not set by default** (`default_config.py:643`
ships `[]`). The owner's `.env` currently sets it to `ALL`, so today's production
runs gather deterministically — but that is a configuration state, not a
guaranteed contract, and it constrains *raw tools*, not *engines*.

### 3.3 The supplied fragment covers one engine, not the scorecard

`engine_score_block(analyst_key, ...)` (`report_hygiene.py:77`) supplies the
analyst's **owned** engine only. The market analyst receives `TechnicalScore`; it
does not receive `RegimeScore` or `RiskScore` in the same block. An LLM reasoning
about whether a setup is attractive without seeing the regime and risk context is
reasoning on a fragment of the evidence the system already computed.

---

## 4. The required engine manifest

The design introduces an explicit **manifest** — the set of engines that must be
evaluated for every security, independent of any model decision.

```text
                    APPLICATION
                         |
                         v
            Required engine manifest
        (the eight registered engines,
         filtered only by their own gates)
                         |
                         v
              Deterministic execution
         (already true: trading_graph.py:651)
                         |
                         v
              score + coverage + detail
                         |
                         v
                 BUILD LLM PROMPT
                         |
                         v
                       LLM
```

**Manifest membership is decided by the gates, never by the model.** An engine
whose gate is off is `absent` and is reported as `absent` — it is not silently
skipped, and it is not a discretionary omission. This preserves the existing
convention that the scorecard prints `absent: {'event': 'enable_event_state is
off'}` rather than omitting the key.

**The manifest is the eight engines, not the four composite engines.** All eight
are evaluated and delivered for interpretation. Only the four in
`COMPOSITE_ENGINES` (`quant_scorecard.py:86`) contribute to `TradeScore` — see §9.

**The manifest is delivered to all four analysts** (§13.1), each also receiving
its normal owned research and evidence. The engine evidence comes first and
`TradeScore` last, labelled downstream and non-instructional (§13.2).

---

## 5. Two classes of tool use

This distinction is the operational core of the design.

### A. Mandatory analytical tools (deterministic, not model-chosen)

The producer/calculation tools behind the eight engines. The application
guarantees they run. The model cannot skip, reorder away, or substitute them.

```text
FundamentalScore   TechnicalScore   RegimeScore    RiskScore
SentimentScore     NewsScore        EventScore     TradeScore
```

### B. Exploratory research tools (discretionary, model-chosen)

Everything else. The model remains free to investigate:

```text
"Investigate why margins deteriorated."
"Look for recent management commentary."
"Check whether this unusual volume has a specific catalyst."
"Investigate the discrepancy between valuation and price."
```

This gives the model **judgment without discretion over the measurement**. It
keeps the LLM's real value — synthesizing conflicting evidence, qualitative news,
unusual circumstances, company-specific context, emerging catalysts — while
removing its ability to decide which measurements exist.

---

## 6. The prompt contract

The canonical block. Every enabled engine is named; discretion is explicitly
forbidden; the missing-value semantics are stated in the prompt itself.

```text
For every security, evaluate all 8 registered scoring engines:

1. FundamentalScore
2. TechnicalScore
3. RegimeScore
4. RiskScore
5. SentimentScore
6. NewsScore
7. EventScore
8. TradeScore

Do not selectively call engines based on discretion.

For each enabled engine:
- call all required producer/calculation tools;
- collect the returned measurements;
- allow the engine to calculate its score;
- record score and coverage;
- distinguish NA/unavailable from a measured score of 0.

An engine must not be treated as fully measured unless its required
coverage floor is satisfied.

After all enabled engines have been evaluated, produce the composite
from the engine outputs and their defined weights.

Do not invent missing measurements.
Do not substitute 0 for missing measurements.
Do not omit an enabled engine merely because another engine appears
more informative.
```

**Reading of this block.** The first four lines are an instruction to the *system*
(the manifest is executed regardless). The remainder is an instruction to the
*model* about how to treat what it is given. The design intent is that the model
**receives the results**; the imperative phrasing exists so that a model reading
its context understands the results are complete, mandatory, and not a menu.

---

## 7. The evidence and mapping requirement

A bare score is insufficient. The context must carry, per engine:

1. the **score**,
2. the **coverage**,
3. the **category breakdown**,
4. the **supporting measurements**, and
5. **the mapping** where it is non-monotonic.

### 7.1 The non-monotonic case

This is the requirement that makes the design necessary rather than merely tidy.
A producer may map a raw measurement through a band table that is not monotonic:

```text
RSI raw:       53.26
RSI aligned:   85
Mapping:       producer-defined non-monotonic band
```

A generic model reading `RSI = 53` concludes *neutral*. The producer's methodology
concludes *85*. **Both must be visible**, or the model will silently substitute
its own mapping for the authoritative one — reintroducing exactly the implicit
weighting this design exists to eliminate.

The engine's own document remains the authority on its mapping. This contract
requires only that the mapping be **surfaced**, not that it be re-derived here.

### 7.2 Target shape

Per §13.4 each engine prints its score, coverage, required floor and status:

```text
TECHNICAL SCORE
Score: 62.29
Coverage: 95%
Required: 8 of 9 components present
Status: ABOVE FLOOR

Trend: 75.13   Momentum: 50.87   Relative Strength: 68.75
Price Structure: 65.00   Volume: 52.72   Breakout: 56.25
Mean Reversion: 51.70   Volatility: 78.11   Breadth: NA

Important measurements:
ADX   = 31.16  -> 64.64
RSI   = 53.26  -> aligned 85
ROC20 = 2.62%  -> 63.1
```

**Ordering is part of the contract** (§13.2): the engines first, `TradeScore`
last, labelled downstream and non-instructional — so the composite is a reference
point rather than an anchor.

`format_engine_detail` (`quant_scorecard.py:696`) already renders the
per-category weights, scores, bands and coverage for a snapshot; the live market
block measured 2026-09-19 is 4207 characters and carries the full
`## TechnicalScore - QCOM (advisory; 35 of 40 components measured)` body. The
delta this design specifies is **the supporting-measurement, mapping and
floor/status rows**, not the category table.

---

## 8. Coverage semantics

**`NA` is not `0`.** This is master rule 1 and it must survive all the way into
the LLM context.

| Value | Means |
|---|---|
| a measured score of `0` | measured, and extremely unfavourable |
| `NA` / `unavailable` | not measured — the evidence does not exist |

```text
Fundamental  62.50 / 100% coverage
Technical    62.29 /  95%
Regime       80.55 /  83%
Risk         79.35 /  45%
Sentiment    74.68 /  50%
News          NA
Event         NA
Trade        68.53 / 100%
```

`RiskScore = 79.35` at 45% coverage does **not** carry the same evidentiary
strength as `RiskScore = 79.35` at 100% coverage, and the prompt must let the
model say so. The observed consequence is already visible in production: the
verifier's engine cross-check fired on `SentimentScore composite 78.6/100
(constructive) at coverage 50%`.

**An engine below its coverage floor has its score WITHHELD — not degraded.**
This is implemented, not aspirational: `combine`
(`tradingagents/strategies/score_engine.py:134`) withholds when
`len(present) < floor` (`:206`), and the withheld `score` is `None` — **never `0`
and never `50`** (`:141-157`). The `withheld` string already names both the count
and the floor (`"5 of 10 components present, floor is 6"`, `:208`).

Per §13.4 the floor is printed beside the coverage, read from the one
implementation `coverage_floor` (`score_engine.py:45`) rather than restated.

---

## 9. What must NOT change

This design adds a delivery contract. It does not reopen settled architecture.

1. **Master rule 17 — no engine enters the composite by adjacency.** All eight
   engines are *delivered for interpretation*; only `COMPOSITE_ENGINES`
   (`quant_scorecard.py:86`) feed `TradeScore`. Supplying `NewsScore` and
   `SentimentScore` to the model is **display by adjacency, which is permitted**;
   feeding them into the composite is not.
2. **Master rule 18 — `RiskScore` is a `TradeScore` engine, not a risk gate.** The
   hard gates operate downstream. Nothing in this contract moves a gate.
3. **Master rule 2 — a score is not a rating.** Nothing here feeds
   `decision_guardrail.SCORE_BANDS`.
4. **The composite's printed `basis` contract is frozen (D3).** New fields only.
5. **The ownership map governs RENDERING; this contract governs READING.** These
   are different questions and they must not be collapsed:
   - *Ownership* (`ENGINE_SECTIONS`) decides **where an engine's result appears as
     a section** — `fundamental -> fundamentals`, `technical -> market`, and
     `regime`/`risk`/`trade` report-level by decision.
   - *Context* (this document) decides **what the model is shown** — the full
     scorecard.
   A market analyst that *reads* `RegimeScore` does not thereby *own* the regime
   section. Widening the reading does not move a section.
6. **Gate names are new, never reused.** This design needs no new gate: the
   manifest is filtered by the existing eight `ENGINE_GATES`
   (`quant_scorecard.py:70`) under the master gate.
7. **`NA != 0`, and `None` is never `[]`.** `None` = not answered (`missing`);
   `[]` = answered and empty (`not_applicable`).

---

## 10. A found redundancy this design resolves

**The same engine currently reaches one report twice.**

Verified 2026-09-19: for each of the four analysts, the owned engine is *both*
supplied by `engine_score_block` **and** bound as a callable tool by
`engine_score_tools` — and both derive from the same `engines_for_analyst`
(`quant_scorecard.py:134`).

```text
market        owned=('technical',)     supplied by block AND bound as ['get_technical_score']
news          owned=('news','event')   supplied by block AND bound as ['get_news_score','get_event_state']
fundamentals  owned=('fundamental',)   supplied by block AND bound as ['get_fundamental_score']
sentiment     owned=('sentiment',)     supplied by block AND bound as ['get_sentiment_score']
```

For the first three this is a redundant second route to one number in one report.
For `sentiment` it is not even that: that analyst binds **no tools at all** (its
prompt carries `NO_EXTERNAL_TOOLS`, `tradingagents/agents/utils/structured.py:44`)
and runs schema-only structured output
(`bind_structured`, `structured.py:1240` -> `with_structured_output`), so its
`get_sentiment_score` binding is unreachable.

This sits close to master rule 15 (no derived quantity with two independent
authoritative producers). It is not a rule-15 violation in the strict sense — the
block and the tool read the *same* producer, so they cannot disagree — but it is
**two routes to one number**, and it invites exactly the ambiguity the design is
meant to remove.

**Resolution specified here:** under the manifest, the **supplied block is
authoritative**. An engine that the block already supplies is **not** also bound
as a discretionary tool. The tool binding remains only for an engine the block
does not supply.

---

## 11. Implementation phases

Each phase is independently landable, gated, and byte-identical when off.

### Phase 1 — the full-scorecard context block

Extend the delivered context from the owned engine to the **whole manifest**
(all eight, with `absent` named). Keep `ENGINE_SECTIONS` as the ownership table;
this changes *reading*, not *rendering* (see §9.5).

- **Touches:** `report_hygiene.engine_score_block` (`report_hygiene.py:77`), or a
  sibling `scorecard_context_block` if the owned-engine block is retained for the
  analyst's own section.
- **Gate:** the existing master gate. No new key.
- **Exit:** each analyst report carries the full scorecard; the ownership map's
  placement assertions are unchanged.

### Phase 2 — the manifest drives execution, and every engine binding is dropped

Make the manifest explicit in code (a derived tuple, not a literal list) and
**drop all eight LLM-facing engine-score tool bindings** (§13.3).

> **Superseded (2026-09-19):** this phase as first written dropped the binding
> only where the supplied block already covered that engine. The owner's decision
> is broader — *engine-score tools are application-internal calculation
> mechanisms, not LLM-facing analytical tools*, so **all eight** bindings go. The
> earlier scope is retained here as the record; the wider rule supersedes it.

- **Touches:** `toolsets.engine_score_tools` (`toolsets.py:450`),
  `quant_scorecard.engines_for_analyst` (`quant_scorecard.py:134`).
- **Scope:** all eight — `get_fundamental_score`, `get_technical_score`,
  `get_regime_score`, `get_risk_score`, `get_sentiment_score`, `get_news_score`,
  `get_event_state`, `get_trade_score`. The underlying **exploratory** tools stay
  bound (§5).
- **Watch:** `tests/test_calc_agent_wiring.py::test_tool_bound_to_agent_surface`
  requires every public `@tool` be bound **or** declared in `TOOL_LEGACY_BINDING`
  with its real consumer and a reason — and *"nothing uses it" is not an
  acceptable reason*. All eight must be declared with their actual consumer, **the
  supplied scorecard**, before the suite will pass.
- **Exit:** no engine reaches one report by two routes; no engine-score tool is
  LLM-facing.

### Phase 3 — evidence, mapping and floor rows

Add the supporting-measurement rows (§7) to the delivered block, including the
explicit mapping where the producer's band table is non-monotonic, and the
coverage floor with its status (§13.4).

- **Touches:** `quant_scorecard.format_engine_detail` (`quant_scorecard.py:696`)
  and the block builder; and `score_engine.combine`
  (`tradingagents/strategies/score_engine.py:134`) to expose the floor it already
  computes at `:190` as a structured field beside `coverage`.
- **Do not duplicate the floor.** It is resolved by the one implementation,
  `coverage_floor` (`score_engine.py:45`). A second hand-maintained constant is
  forbidden by the same rule as any other two-producer quantity (master rule 15).
- **Units:** the floor is a component **count** (`len(present) < floor`, `:206`);
  `coverage` is a weight **fraction**. Print them as the units they are — the
  implemented count form (`"5 of 10 components present, floor is 6"`) is
  unambiguous and already exists in `withheld` (`:208`).
- **Exit:** a reader can see, for a named measurement, both the raw and aligned
  values; and for each engine, its score, coverage, required floor and status.

### Phase 4 — the prompt contract text

Adopt §6 as the canonical wording in the analyst prompts, replacing any softer
phrasing that implies the engines are optional.

- **Exit:** the wording is identical across the four analyst prompts, or derived
  from one constant.

---

## 12. Acceptance and verification

1. **Gate off is byte-identical.** A run with `enable_quant_scorecard` off writes
   a card and report byte-identical to a pre-engine tree. (Existing acceptance
   (a), `IMPLEMENTATION_PLAN.md` §6.)
2. **Every enabled engine is present or explicitly `absent`.** No enabled engine
   is silently missing from the delivered context.
3. **`NA` survives.** A run with an unmeasurable engine shows `NA`/`absent` in the
   context — never `0`.
4. **Coverage travels with every number.** No score is delivered without its
   coverage.
5. **The mapping is visible.** For at least one non-monotonic component, the raw
   and aligned values both appear.
6. **The composite is unchanged.** `TradeScore` for a given symbol/date is
   identical before and after the delivery change — this contract changes what the
   model *reads*, never what the system *computes*.
7. **Ownership placement is unchanged.** `ENGINE_SECTIONS` assertions in
   `tests/test_engine_ownership_map.py` continue to hold.
8. **No engine reaches one report twice** (Phase 2 exit).
9. **All four analysts receive the full scorecard** (§13.1) — not only the engine
   they own.
10. **`TradeScore` is present, labelled downstream and non-instructional, and
    printed after the underlying engines** (§13.2).
11. **No engine-score tool is LLM-facing** (§13.3) — all eight bindings dropped,
    the exploratory tools retained.
12. **Every engine prints score, coverage, required floor and status** (§13.4),
    with the floor read from `coverage_floor` (`score_engine.py:45`) rather than a
    second constant.

**Method note.** Every behavioural claim above must be proven by **mutating
behaviour, not by stashing the source** — stashing a file whose new symbols the
test imports produces an `ImportError`, which is not a proof.

---

## 13. Decision record (owner, 2026-09-19)

All four questions below were **closed by the owner on 2026-09-19**. The questions
are retained verbatim as the record; each resolution states the consequence for
the phases and acceptance in §11 and §12.

### 13.1 Full scorecard to **all four analysts** — CLOSED

**Question (as put):** deliver the full scorecard to every analyst, or to the
decision layer only?

**Decision: deliver it to all four analysts.**

The reason is this design's own objective. If each analyst sees only its owned
engine, each still forms a thesis from an incomplete quantitative picture:

```text
market        -> Technical
fundamentals  -> Fundamental
news          -> News + Event
sentiment     -> Sentiment
```

The market analyst would see `Technical = 62` without seeing `Regime = 81` or
`Risk = 79`, and would therefore still *implicitly* decide how much technical
condition matters relative to regime and risk — the exact failure this contract
exists to remove (§3.3).

```text
all analysts:
    full 8-engine scorecard
  + their normal owned research/evidence
```

**Ownership and rendering are unchanged.** The §9.5 distinction stands: who *owns*
a section and what the model can *read* are different questions.

### 13.2 `TradeScore` — **included, labelled downstream, ordered last** — CLOSED

**Question (as put):** does `TradeScore` belong in the analyst context?

**Decision: include it, but present it as downstream and non-instructional, and
place it after the underlying engines.**

```text
TradeScore: 68.53
Role: downstream composite / research allocation
Do not treat as a trading instruction.
```

The rationale is that an analyst shown seven or eight engines but *not* the
system's own composite would form yet another interpretation layer. The composite
is a **reference point**; the engines remain the evidence.

**Ordering is deliberate and part of the contract** — evidence first, composite
last, to reduce anchoring:

```text
ENGINE EVIDENCE
    Fundamental   Technical   Regime   Risk   Sentiment   News   Event
        |
        v
    TradeScore
```

This is consistent with master rule 17: `TradeScore` is a *research allocation*,
not an instruction.

### 13.3 Engine tool bindings — **drop all eight** — CLOSED

**Question (as put):** retain or drop the engine tool bindings entirely? Phase 2
as first written dropped the binding only where the supplied block already covered
that engine.

**Decision: drop every LLM-facing engine-score tool binding.**

> **Engine-score tools are application-internal calculation mechanisms, not
> LLM-facing analytical tools.**

Once the scorecard is computed deterministically and supplied, an engine score
does not need a second discretionary access path. Keeping both invites the
ambiguity *"is the supplied score authoritative, or should I call the tool and
obtain it again?"* — and is the duplicate route §10 identifies.

**The underlying exploratory tools stay.** Only the eight engine-score bindings
are removed. This preserves the §5 split: mandatory score calculation is the
application's; exploratory investigation remains the LLM's.

**Consequence for Phase 2 (§11):** the scope widens from "where the block already
supplies" to **all eight** — `get_fundamental_score`, `get_technical_score`,
`get_regime_score`, `get_risk_score`, `get_sentiment_score`, `get_news_score`,
`get_event_state`, `get_trade_score`. Three of those (`regime`, `risk`, `trade`)
are already bound to no analyst, so the change is five live bindings plus the
consolidation of all eight under one rule. Every one must be declared in
`TOOL_LEGACY_BINDING` with its real consumer — the supplied scorecard — because
that list refuses *"nothing uses it"* as a reason.

### 13.4 Coverage floor — **print coverage, required floor and status** — CLOSED

**Question (as put):** should the floor value be printed beside the coverage?

**Decision: yes — print `score / coverage / required floor / status`.**

```text
RiskScore
Score:       79.35
Coverage:    45%
Required:    50%
Status:      BELOW FLOOR
```

`Coverage = 45%` tells the model the evidence is incomplete but not **whether 45%
is acceptable**. The model must not have to know the floor from another document.

**Grounding — the floor already exists and must not be duplicated.** It is
resolved by `coverage_floor(min_coverage, n_components)`
(`tradingagents/strategies/score_engine.py:45`), the one implementation, read by
`risk_score.py:489`, `news_score.py:362`, `event_state.py:546` and
`factors.py:314`. `combine` (`score_engine.py:134`) computes it at `:190` and
**enforces** it at `:206` — below the floor the score is withheld, never `0` and
never `50`:

```python
floor = coverage_floor(min_coverage, len(present))          # :190
if len(present) < floor or present_w <= 0:                  # :206
    out["withheld"] = f"{len(present)} of {len(comps)} components present, floor is {floor}"
```

**Two precision points this decision must respect.**

1. **The floor is already printed, in prose, but not as a field.** It appears in
   `withheld` (`:208`) and in `basis` (`:216`, `"score over N present
   component(s), floor M"`). The returned dict is `{"score", "coverage",
   "components", "present", "withheld", "label", "basis"}` — there is **no
   structured `floor` key**. Printing `Required:` therefore means **exposing an
   existing value as a field**, not inventing one. This is the preferred route:
   the alternative — parsing the prose — is exactly the fragile coupling the
   contract exists to avoid.
2. **The floor is a component COUNT; `coverage` is a weight FRACTION.** The
   comparison at `:206` is `len(present) < floor`, a count. Rendering the floor as
   a percentage requires choosing a base — fraction of the declared set, or of the
   present set (`coverage_floor` uses `len(present)`, which is circular for a
   fraction reading). **The two must not be printed as if they were the same
   unit**; the count form (`"5 of 10 components present, floor is 6"`) is
   unambiguous and already implemented.

### 13.5 The resulting contract

```text
              APPLICATION
                  |
                  v
        Mandatory 8-engine execution
                  |
                  v
        Full scorecard: score, coverage, required floor, status,
        category breakdown, supporting measurements, mappings
                  |
                  v
           ALL FOUR ANALYSTS
                  |
                  v
              LLM THESIS
                  |
                  v
            DECISION LAYER
             /            \
        Composite       Hard gates
             \            /
                  v
              POSITION
```

**Separation of responsibilities:**

| Layer | Decides |
|---|---|
| Application | what is measured |
| Scoring engines | how measurements are weighted |
| LLM | how the resulting evidence is interpreted |
| Risk/decision layer | what risk is permitted |
