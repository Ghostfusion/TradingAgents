# Score engines — the research and debate layer

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (the build order) and
one document per engine.

**Status: design (2026-09-18) — not started.** This document specifies how the
eight engine scores reach the research and debate layer. It is a **design**, not
a build order: the workstream it defines is `WP-12`, and it is written to be
appended to `IMPLEMENTATION_PLAN.md` §6 as a new section rather than to be its
own plan.

**Why this document exists.** The owner asked whether the scores should be
exposed in the other research-layer reports and fed to the LLM debate, with the
scores as *structured evidence* rather than an instruction. The answer is yes, and
the repository is already shaped to do it at one seam — but three defects and one
hard constraint sit on that seam, and two of the three defects were found only by
executing the path. This document records them before any code is written.

---

## 0. What this document answers

| # | Question | Answer | Section |
| --: | --- | --- | --- |
| 1 | Can a debate agent see an engine score today? | **No.** Under default config, no. Under any config, only accidentally | §1.2, §1.3 |
| 2 | What is the seam? | `computed_decision_context` — one string, ten consumers, one verifier | §1.2 |
| 3 | What has to be true before a scorecard is added? | One producer, a bounded block, and a gate | §2, §3 |
| 4 | What should the block contain? | The composite, its four drivers, coverage, the missing list — never the composite alone | §4 |
| 5 | Should it carry score movement? | Yes, and it is the highest-value part — but it needs a history store, which does not exist | §4.3 |
| 6 | Should the LLM be allowed to "improve" a score? | **No.** It interprets; it never recomputes or overrides | §2 rule 5 |
| 7 | What should happen on disagreement? | A deterministic **flag**, never an override | §5 |

---

## 1. What exists today

### 1.1 The two surfaces the engines reach

The eight engines reach exactly two places, both verified:

| Surface | Mechanism | Gate | Consumers |
| --- | --- | --- | --- |
| **The eight LangChain tool leaves** | `agents/utils/analysis_tools.py::get_*_score`, appended to a toolset in `agents/toolsets.py` | one per engine, all default `False` | an analyst's LLM, if the ToolNode carries it |
| **`run_card.json`** | `reporting.py::_run_card_*` (eight builders, `859-1246`), assembled `1858-1891`, written `1893` | one per engine, all default `False` | a human reading the JSON |

All eight gates default `False` at `default_config.py:1062/1064/1070/1073/1074/1078/1082/1085`.

**The consequence for the research layer is stark: the engine scores reach
`run_card.json` — and `run_card.json` has no reader in the research layer at
all.** Verified across all three repositories:

- `../TradingExecution/signald/watch.py:6-8` **explicitly ignores** `run_card.json`
  and reads only `research_decision.json`.
- `../trading_web/backend/capabilities.py::read_report_tree:1699` serves every
  `*.md` of a report tree and reads no `run_card.json`.
- `complete_report.md` is built at `reporting.py:1788` from **state keys only**;
  within `reporting.py` the engine modules are referenced only inside the
  `_run_card_*` builders.

So the score engines' numbers today reach a JSON file that the executor refuses,
the web UI does not read, and no LLM ever sees.

### 1.2 The debate layer's one quantitative channel

`AgentState.computed_decision_context` (`agents/utils/agent_states.py:90`) is a
single deterministic string, built **once per run, before the graph starts**, by
`graph/trading_graph.py::_compiled_decision_context` (`:1243-1509`) and set at
`:649-651`.

It is the **only** place a number from the quant side reaches a debate prompt.
Its builder imports no score engine — verified — and carries the holdings block,
the regime gate, the trade plan card, the risk snapshot, the limits registry, the
vol estimates and the tranche risk. **None of the eight engine scores is in it.**

It is consumed at **ten** sites:

| # | Site | Bound |
| --: | --- | --- |
| 1 | `researchers/bull_researcher.py:52` | none |
| 2 | `researchers/bear_researcher.py:54` | none |
| 3 | `managers/research_manager.py:99` | none |
| 4 | `trader/trader.py:97` | none |
| 5 | `risk_mgmt/aggressive_debator.py:47` | none |
| 6 | `risk_mgmt/conservative_debator.py:47` | none |
| 7 | `risk_mgmt/neutral_debator.py:47` | none |
| 8 | `managers/portfolio_manager.py:287` | none |
| 9 | `utils/independent_vote.py:105` | none |
| 10 | `researchers/structured_debate.py:216` | **3000 chars** |

And at one more, indirectly: `researchers/structured_debate.py::ground_truth_from_state`
(`:298`) text-parses this string — and the four analyst reports — for `key=value`
numeric pairs (`_KEY_VALUE_RE:275-277`, `_parse_key_value_lines:280`) into the
**Ground Truth Key Index**. That index is the registry the L1 checker verifies a
debater's `quantitative_claims` against. **It is the only mechanism by which a
debate agent can cite a number and have it deterministically verified.**

> **This is why the seam is one string and not ten prompts.** A block appended to
> `computed_decision_context` reaches all ten prompt sites *and* the verification
> registry *and* — because `reporting.py:1644-1646` renders the same string as
> report section `IVa` — the human report. One producer, three readers.

### 1.3 The gap, per engine

| Engine | In `computed_decision_context` | Reachable by a debate agent | Reachable by an analyst's LLM (gate on) |
| --- | --- | --- | --- |
| `FundamentalScore` | no | no | yes — `fundamentals_company_tools` |
| `TechnicalScore` | no | no | yes — `fundamentals_company_tools` |
| `RegimeScore` | no | no | yes — `market_tools` |
| `RiskScore` | no | no | yes — `market_tools` |
| `NewsScore` | no | no | yes — `news_tools` |
| `EventState` | no | no | yes — `news_tools` |
| `SentimentScore` | no | no | **no — see below** |
| `TradeScore` | no | no | yes — `fundamentals_company_tools` |

**The `SentimentScore` row is not a defect but it is a hard constraint.**
`toolsets.py::sentiment_tools()` (`:530`) exists and `analyst_toolset("sentiment")`
resolves to it (`:587-588`), but **no ToolNode is built for the sentiment key**:
`trading_graph.py:343-345` builds nodes for `("market", "news", "fundamentals")`
only, and `tests/test_tool_binding_single_source.py:50` **asserts** exactly that
set. `toolsets.py:533-538` records it as deliberate — the sentiment analyst binds
no tools because its data is pre-fetched into the prompt from turn 0.

So with `enable_sentiment_score` on, the score is **computed but unreachable by
any agent**. For the scorecard this means the sentiment engine must enter through
the snapshot, **not** through an analyst's tool path — which the §3 design does
anyway, but it removes "just turn the gate on" as an alternative.

### 1.4 One accidental path, which must not be the design

An engine tool's rendered text (e.g. `- FQS: 72.3/100`, from
`_render_fundamental_score`) can be echoed by an analyst verbatim into its
`*_report`, and `ground_truth_from_state` would then harvest it into the registry.
It requires the engine's gate on **and** the analyst choosing to echo the line.
A number that arrives only when a model happens to repeat it is not a channel, and
the design must not depend on it.

---

## 2. The rules this must not break

These are the master's rules applied to this seam. Each one names a way this
feature could quietly break the set.

1. **One producer per number** (master rule 15). A derived quantity may have one
   authoritative producer; a secondary may be a fallback, a cross-check or a
   diagnostic, never a second contributor. **Today this seam already violates it**
   — see D-8 in §6.
2. **`NA` is not `0`, and coverage travels with the number** (master rule 1). An
   engine that cannot measure is reported as absent **with its reason**, and the
   composite's coverage is printed beside it.
3. **A gate is a toolset membership switch** (plan §6). With a gate off, nothing
   about the surface changes; with it on, exactly one thing appears.
4. **Advisory never a gate.** No score reaches `opportunity_score`, sizing, or
   `GATE_PRECEDENCE`. The executor's 17 checks run downstream and block
   regardless.
5. **The LLM interprets; it never recomputes or overrides.** The quant engine owns
   measurement, normalisation, weighting, coverage and missing-data handling. The
   LLM owns interpretation, contradiction detection and hypothesis generation.
   There is no path from an LLM output back into a score.
6. **The composite is an evidence summary for a human reviewer** (owner,
   2026-09-18) — `RESEARCH_ONLY` does not mean "do nothing", and the reviewer is
   the decision. This feature is what makes that framing operable.

---

## 3. The design — one snapshot, three readers

### 3.1 The shape

```
   run starts
       │
       ▼
   ┌──────────────────────────────────────────┐
   │  quant_scorecard(ticker, trade_date)      │   ONE producer
   │  → the four engine results + coverage     │
   └──────────────────────────────────────────┘
       │                    │                  │
       ▼                    ▼                  ▼
  rendered block      run_card.json      the leaf tool
  into computed_      _run_card_*        get_trade_score
  decision_context    read the snapshot  reads the snapshot
       │
       ├──► 10 debate/manager prompts
       ├──► Ground Truth Key Index (citable + verifiable)
       └──► report section IVa (the human)
```

**One computation, three surfaces.** The alternative — a third independent
computation feeding the debate — is the defect D-8 already demonstrates, and is
forbidden by master rule 15.

### 3.2 The producer

A new module `strategies/quant_scorecard.py` exporting one function:

```
quant_scorecard(ticker, trade_date, cfg) -> dict
```

It calls each engine's **own public entry point** — `fundamental_score_for_ticker`,
`technical_score`, `regime_score`, `risk_score`, `sentiment_score`, `news_score`,
`event_state`, `trade_score` — with the arguments the card blocks use today, and
returns their results verbatim. It computes nothing itself: no alignment, no
re-weighting, no substitution. An engine that raises or cannot measure returns
`None` with its reason, exactly as `_trade_score_engines` already does.

**Every engine is read through the date the run is for.** This is not a detail:
it is defect D-7 (§6). The card already applies the convention uniformly to the
three date-dependent engines — `_run_card_fundamental_score:881-882`,
`_run_card_sentiment_score:1203-1204` and `_run_card_news_score:1239-1240` all
read `pm_decision.trade_date`. The trade leaf was the one path that could not
receive a date at all, which is exactly how it drifted.

### 3.3 Where it is built, and why there

At run start, in `graph/trading_graph.py::propagate`, immediately before
`_compiled_decision_context` is called (`:649`), the snapshot is built once and
stored on the state as a new declared channel (`quant_scorecard`). The channel
**must** be declared in `AgentState.__annotations__` — native LangGraph drops
undeclared keys silently, which this repository has already been bitten by (see
`docs/AGENT_ONBOARDING.md`, the 2026-08-28 entry).

The trade-off, stated plainly:

| Choice | Cost | Benefit |
| --- | --- | --- |
| **Pre-graph (recommended)** | the engines fetch their own data before the analysts run; a slow engine can delay a run | the debate's number and the report's number are provably one number; the evidence the debate reasons over is the evidence the report shows |
| Post-analysts (a second node) | needs a new node, a new edge, and a second "is it built yet" check in every consumer | the engines could read the analysts' already-fetched data | 
| Per-consumer (today) | each consumer recomputes; two consumers can disagree | none — this is the defect |

The pre-graph cost is **not new spending**: the leaf and the card each pay that
fetch today. Doing it once is cheaper than the status quo.

### 3.4 The gate

One new gate, `enable_quant_scorecard`, **default `False`**, following the set's
dark-launch discipline. Its semantics, chosen to resolve D-8 rather than repeat
it:

- With the gate off, `computed_decision_context` is byte-identical to today and
  the card gains no key.
- With the gate on, exactly one block appears in the context and exactly one key
  (`quant_scorecard`) appears in the card.
- **An engine entry is present iff that engine's own gate is on.** This is the
  rule `_run_card_trade_score:996-1004` already applies. Adopting it everywhere
  gives one rule for all three readers.

**Consequence, and it is the point of D-8:** the composite's gate governs the
composite, and the engine gates govern the engines' own surfaces. A
`trade_score` key must therefore carry its own four inputs so the number stays
recomputable from the card alone — which `_run_card_trade_score` already does via
its `engines` map. That is what makes the card honest when a sub-gate is off.

---

## 4. The scorecard block

### 4.1 Format

The block must be (a) `key=value`-parseable so `ground_truth_from_state` adopts it
as verifiable ground truth, (b) human-readable in `IVa`, and (c) **bounded**.

```
Quant scorecard (deterministic, advisory - evidence for review, not an order):
trade_score=76.75 trade_status=RESEARCH_ONLY trade_coverage=0.95
fundamental_score=92.0 fundamental_coverage=1.00
technical_score=85.0 technical_coverage=0.95
regime_score=78.0 regime_coverage=0.83
risk_score=35.0 risk_coverage=0.45
absent=none
```

Three properties are non-negotiable:

- **The four drivers are always printed beside the composite.** `76.75` alone is
  a different story from `76.75 because F 92 / T 85 / R 78 / K 35`, and a reader
  cannot tell them apart without the drivers. The engine's own render helpers
  (`_render_fundamental_score` and siblings) already print this way.
- **Coverage is printed per engine and on the composite.** Per rule 2, `72` at
  `coverage 68%` means *72 over 68% of the intended evidence* — with the missing
  components named.
- **The purpose is stated, not only the constraint.** Every existing printed score
  block ends *"advisory only — never a gate, never a size, never an
  `opportunity_score`"* — the negative constraint only. The owner corrected this
  framing on 2026-09-18 (master §1.4). This block carries the positive statement.

### 4.2 Three levels of visibility

| Level | Where | Content |
| --- | --- | --- |
| **1 — Executive** | the debate block (§4.1), the report's executive summary | composite, four drivers, coverage, status |
| **2 — Research sections** | each engine's own section in `complete_report.md` | that engine's category sub-scores beside the raw measurements they came from |
| **3 — Quant diagnostics** | the card and the leaf tool text (unchanged) | the full component → category → engine chain, e.g. the 40 technical components into 9 categories |

Level 3 already exists and needs no work. Level 2 is where the owner's
"research evidence → score → interpretation" chain becomes visible; it is an
addition to `write_report_tree` (`reporting.py:1392`) that renders each engine's
already-computed result, and adds no producer.

### 4.3 Score movement — the highest-value part, and the one with no producer

The owner's strongest point is that movement can matter more than level: a
`TradeScore` that rose `61 → 76` is a different research situation from one that
fell `91 → 76`.

**No history store exists in this repository.** There is a per-run memory log and
the WP-10 panel cache (`~/.tradingagents/cache/panels/`), but nothing keyed on
`(ticker, date)` holding prior engine scores.

Design: `<data_cache_dir>/score_history/<TICKER>.jsonl`, one row per scored run
date, written by the snapshot producer. The block then carries:

```
trade_score=76.75 trade_prev=73.20 trade_delta=+3.55 trade_prev_date=2026-09-11
```

**`NA` rules, per rule 2:** no prior row → no delta keys at all, never `0`. The
delta is against the **previous scored observation**, and its date is always
printed — a delta against an unstated date is a disguised fabrication.

This is a real workstream of its own: a store, a retention rule, and the
reproducibility question of what happens when the engine's weights change between
the two observations. **A delta across a weight change is not a delta.** The
store must record the vector it scored under, and the block must refuse the delta
when the vector differs.

### 4.4 The bound

Site 10 (`structured_debate.py:216`) bounds the whole context to **3000
characters**. A block appended to the tail of `_compiled_decision_context` can
therefore be silently truncated away for the structured debate — the one path
with deterministic claim verification.

Two changes, both required:

1. The block is placed **first** in `_compiled_decision_context`'s output, so any
   truncation consumes something else.
2. `build_turn_prompt` renders the scorecard **as its own bounded field**, so the
   3000-character bound applies only to the rest of the context.

A truncation that removes the scorecard silently is the same failure shape as the
rest of this document's defects, and the fix must not be "the block is short
enough".

### 4.5 The mapping is evidence too

Eight components are **non-monotonic**: `NON_MONOTONIC_INPUTS`
(`strategies/score_engine.py:33`) names `rsi`, `mfi`, `stochastic`, `StochRSI`,
`RSI2`, `Williams %R`, `Bollinger %b` and the Elder thermometer. `score_engine.align`
(`:61`) maps each through a producer-defined ramp, so a high raw value can align
*low* — RSI `82` aligns below RSI `55`, because the producer's band says so, not
because the sign flipped.

A debate that sees only `technical_score=85` cannot tell a healthy momentum read
from an overbought one, and the owner's point is that it must be able to
**challenge the interpretation without touching the mathematics**. So wherever a
cited driver is non-monotonic, the evidence shown must be the triple:

```
rsi=82 rsi_aligned=45 mapping=producer-defined non-monotonic band
```

`align` already returns the aligned value and the engines already carry it in
their `components` maps, so this is a rendering requirement on levels 2 and 3,
not a new producer. It is what makes "the score is 85" a claim the debate can
interrogate rather than a fact it must accept.

---

## 5. The quant / LLM disagreement detector

The owner's proposal — flag when the LLM's risk read contradicts `RiskScore` —
should be built, in its weak form.

**Where.** A deterministic post-debate check over material the run already
produced: the `RiskScore` band (from the snapshot) against the risk debate's own
aggregate stance (`structured_risk_state` round records, or the PM's
`risk_debate_state` verdict when the structured path did not run). No new
producer; both sides already exist.

**What it emits.** A flag with both values and the reason, into the report and one
`run_card.json` key. It **never** changes a score, a rating, a size or a gate.

**Why not the strong form.** The owner is explicit that the LLM must not override
the score, and equally that the disagreement is *valuable* — the trade is to
surface it and route it to the human. A detector that suppressed the LLM's read,
or rewrote the score toward it, would destroy the measurement layer it is supposed
to protect. "Quant `35`, LLM assessment favourable, required review: identify the
evidence causing disagreement" is worth more than either number alone.

---

## 6. Defects found while writing this document

Found by executing the path, not by reading the set. Recorded in the master's
§3.5 with the same table.

| # | Defect | Evidence | Status |
| --: | --- | --- | --- |
| **D-7** | **The leaf scores the wall clock, the card scores the run date.** `_trade_score_engines` called `fundamental_score_for_ticker(ticker)` — no date, so `fundamental_score_for_ticker` falls back to `datetime.now()` (`strategies/fundamental_score.py:550`) — while `_run_card_fundamental_score:881-882` passes `pm_decision.trade_date`. On the documented `batch.py --date 2026-07-22` invocation (batch.py:5) that is one vector printed as two numbers | measured on MSFT: leaf `66.25`, card `62.50`, same basis string, same `panel_n=9`. The leaf is the wrong one — it scored a July decision against September's peer panel | **FIXED** |
| **D-8** | **The D-6 class is not closed.** `_trade_score_engines` computes all four engines unconditionally; `_run_card_trade_score:996-1004` reads each engine from the sibling card block, which exists only when that engine's own gate is on. With `enable_trade_score` on and any sub-gate off, the leaf and the card print **different composites** | `agents/utils/analysis_tools.py::_trade_score_engines` vs `reporting.py::_run_card_trade_score` | **open — §3.4 resolves it by design** |
| **D-9** | **A gate-on `enable_sentiment_score` is unreachable by any agent.** `sentiment_tools()` and `analyst_toolset("sentiment")` exist, but no ToolNode is built for the sentiment key | `trading_graph.py:343-345` builds `market, news, fundamentals`; `tests/test_tool_binding_single_source.py:50` asserts exactly that set; `toolsets.py:533-538` records it as deliberate | **deliberate, not a defect — but it bounds the design (§1.3)** |
| **D-10** | **The structured debate's consensus exit is dead.** `structured_debate.py:644` reads `ds.get("independent_agreement")`; nothing writes that key — `independent_agreement` is computed as a local in `trading_graph.py:1770-1788` and never stored | already on the books: `docs/implementation_plan_defect_audit.md:51` (its line references, `:605` and `:2208`, have drifted) | **pre-existing, open, not this workstream's** |

### 6.1 Two stale documents on this seam

Both are the D-6 failure mode — a stale claim hiding a wire — and both are
corrected in the same pass as this document:

- `agents/utils/agent_states.py:90` describes `computed_decision_context` as
  injected "to the Trader, Portfolio Manager and the 3 risk debators". It reaches
  **ten** sites (§1.2), including both researchers, the Research Manager and the
  independent-vote node.
- `docs/design_risk_calculations_agent_wiring.md:238` records the bull/bear
  researchers as having "**no computed context** (only analyst reports)" and the
  Research Manager as "none (plan from debate)". Both inject it today
  (`bull_researcher.py:52`, `bear_researcher.py:54`, `research_manager.py:99`).

### 6.2 Why D-7 was reachable the whole time

`_trade_score_engines`' own regression test (`tests/test_trade_score.py`) patched
`_risk_components` and asserted on the *returned* dict — it never asserted what
the function passed *in*. D-6 was found by walking a live example; D-7 was found
the same way, by calling the two paths with different dates and comparing. **A
test that pins a function's output but not its arguments cannot see this class.**

---

## 7. Workstream `WP-12` — build order

Each item is default-off, lands as one commit, and has an observable acceptance.

| # | Item | Depends on | Acceptance |
| --: | --- | --- | --- |
| P12-1 | **The snapshot producer.** `strategies/quant_scorecard.py::quant_scorecard`, reading every engine through its own entry point, keyed on the run's date | — | a unit test scoring a fixed component set returns the engines' own numbers; no arithmetic in the module |
| P12-2 | **The state channel.** Declare `quant_scorecard` on `AgentState`; build it in `propagate` before `:649` | P12-1 | a probe node reads it back through the graph — the undeclared-channel trap is tested, not assumed |
| P12-3 | **The block.** Render it into `_compiled_decision_context`, **first in the output** | P12-2 | a live run's `IVa` shows the block; `ground_truth_from_state` returns the score keys |
| P12-4 | **The bound.** `build_turn_prompt` renders the scorecard as its own bounded field | P12-3 | a structured-debate turn prompt contains the scorecard even when the rest of the context exceeds 3000 chars |
| P12-5 | **The card and the leaf read the snapshot** — resolving D-8 by making all three readers use one rule | P12-2 | with `enable_trade_score` on and a sub-gate off, the leaf and the card print the **same** composite; the regression test fails before the change |
| P12-6 | **The gate.** `enable_quant_scorecard`, default `False` | P12-3 | gate off: context and card byte-identical to today. Gate on: one block, one card key |
| P12-7 | **The history store and the deltas** | P12-1 | first run: no delta keys. Second run: `trade_delta` against the printed prior date. Vector changed: delta refused |
| P12-8 | **The disagreement detector** | P12-3 | a fixture where the risk debate reads favourable against `RiskScore` band `unfavourable` produces the flag; a fixture where they agree produces none |
| P12-9 | **Level 2 in the report** — each engine's category sub-scores beside their measurements | P12-2 | the rendered report shows an engine's categories and its composite, recomputing |

**Verification (plan §11 applies unchanged).** Every new pure function gets a test
that fails under a mutation of the code it guards. The two acceptance cases this
document adds to plan §11.3:

- The debate's number and the report's number are **the same number** — asserted
  by comparing the rendered `IVa` block against the card key and the leaf's text
  in one run.
- Gate off is **byte-identical** to a pre-engine tree, for the context and the
  card.

---

## 8. Risks

| # | Risk | Why it is real | Mitigation |
| --: | --- | --- | --- |
| W1 | **The scorecard becomes a third producer** | the leaf and the card already disagree (D-8); adding a third is the obvious naive implementation | §3.1 — one snapshot, three readers; P12-5 is the test that proves it |
| W2 | **The block is silently truncated for the structured debate** | `structured_debate.py:216` bounds the whole context to 3000 chars | §4.4 — first in the output, plus its own bounded field; tested at P12-4 |
| W3 | **The LLM treats the score as its answer** | it is the most convenient number in the prompt | §2 rule 5, §5; the block states the purpose, not only the constraint |
| W4 | **A delta across a changed weight vector reads as signal** | the promotion ladder can move the vector between two observations | §4.3 — the store records the vector; the delta is refused when it differs |
| W5 | **Coverage is dropped in a compact rendering** | a compact block is tempting to trim to the composite | rule 2; §4.1 requires coverage per engine; plan §11.1 already tests it |
| W6 | **The block leaks into the executor's contract** | `run_card.json` gains a key | the executor reads only `research_decision.json` (`signald/watch.py:6-8`); P12-6's gate-off byte-identity test is the guard |

---

## 9. Open questions for the owner

1. **The scorecard's gate, or the composite's?** §3.4 proposes `enable_quant_scorecard`
   governing the block, with each engine appearing iff its own gate is on. The
   alternative is one gate that implies all eight. The proposal keeps the
   dark-launch discipline (one gate, one observable change) but means a
   half-configured run shows a partial scorecard.
2. **Movement before vector validation.** A delta is only meaningful once the
   vector has been measured (plan WP-10 / Phase C). Should the block ship deltas
   at all while the status is `RESEARCH_ONLY`, or hold them until a vector is
   promoted?
3. **Does the composite's printed `basis` string get corrected too?** Every
   generated report's `TradeScore` block currently ends with the negative
   constraint only. §4.1 gives the block a purpose line; the existing printed
   string is report output and changing it alters every generated report and the
   tests that pin it. Carried forward from the 2026-09-18 pass, still unanswered.

---

## Appendix A — evidence ledger

| Claim | Evidence |
| --- | --- |
| The context is the only quantitative channel into the debate | `trading_graph.py::_compiled_decision_context:1243-1509`, set `:649`; imported by no other builder |
| It is consumed at ten sites, one bounded | §1.2 table; `structured_debate.py:216` is the bound |
| The scores reach only a tool and the card | `agents/toolsets.py`; `reporting.py:859-1246`, `1893` |
| The card has no research-layer reader | `signald/watch.py:6-8`; `capabilities.py:1699`; `reporting.py:1788` |
| All eight gates default off | `default_config.py:1062/1064/1070/1073/1074/1078/1082/1085` |
| The context becomes verifiable ground truth | `structured_debate.py::ground_truth_from_state:298`, `_parse_key_value_lines:280` |
| The context becomes report section IVa | `reporting.py:1644-1646` |
| D-7 | measured: leaf `66.25` vs card `62.50`, MSFT, `--date 2026-07-22`; `fundamental_score.py:550` |
| D-9 | `trading_graph.py:343-345`; `tests/test_tool_binding_single_source.py:50` |
| D-10 | `structured_debate.py:644`; `trading_graph.py:1770-1788`; `docs/implementation_plan_defect_audit.md:51` |

### A.1 External sources

| Source | Used for |
| --- | --- |
| Federal Reserve SR 11-7 / SR 26-2 model risk guidance | §4.3 and the traceability principle: documentation must let a third party reconstruct the *rationale*, not just the final output. SR 11-7's conceptual-soundness review covers design, assumptions, qualitative judgments and data selection — which is exactly the conclusion → score → components → raw-evidence chain this document builds |
| Finance-domain LLM evaluation work arguing against collapsing multi-dimensional performance into one scalar | §4.1's rule that the composite is never printed alone: a single aggregate score masks component failures, which is the `76.75-because-everything-was-77` case |