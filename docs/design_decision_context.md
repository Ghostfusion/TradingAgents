# Design: Separating Research Context from Decision Context

**Status:** DESIGN — not built. No code changes accompany this document.
**Date:** 2026-09-19
**Scope:** the path from raw evidence to the final decision rating.
**Companion docs:** `docs/scores/ScoreContextContract.md` (what each analyst is *told*),
`docs/scores/README.md` (the engine set), `docs/execution_v1_emitter_plan.md` (what leaves the repo),
**`docs/implementation_plan_openrouter_large_prompt_ttft.md`** - whose W5 workstream this
document is the decision-quality half of, and whose §3.4 findings are load-bearing here.

---

## 0. Provenance and what this document is

This design was prompted by an owner proposal advancing an architecture in which the
final decision model **adjudicates already-compressed evidence** rather than accumulating
the whole evidence universe. The proposal's own summary of its thesis:

> *The LLM should not be the place where all evidence is accumulated. It should be the
> place where already-compressed evidence is adjudicated.*

and its key architectural claim:

> *Conservatism requires actual contradictory evidence rather than merely the existence of
> additional information.*

This document does four things:

1. States the hypothesis precisely and separates it from what the literature actually supports (§1–§2).
2. **Measures** what the decision layer receives today, from a real run (§3).
3. Maps the proposal against what this repository **already** has — a large fraction of it exists (§4–§5).
4. Specifies only the genuinely missing pieces, with an experiment that can falsify the premise (§6–§14).

**This is a design document, not a defect report.** Nothing here asserts that the current
behaviour is wrong. The one measured fact that *is* striking — §3.1 — is presented as a
measurement, not a verdict.

---

## 1. The hypothesis, stated so it can be falsified

> **H1.** Holding the underlying evidence and model parameters fixed, increasing the size of
> the decision-layer context makes the decision model **more conservative** — i.e. shifts its
> output distribution toward Hold/abstain and away from directional action.

Three sub-claims are worth separating, because they have different fixes:

| | Sub-claim | Failure it describes |
|---|---|---|
| **H1a** | *Volume* dilutes. More tokens, same evidence → more hedging. | context dilution |
| **H1b** | *Uncertainty* is miscounted as negative evidence. "Fed unknown" is weighed as a bearish fact. | category error in the prompt |
| **H1c** | *Debate* manufactures caution. Cross-talk converges on the least-committal position. | conformity in multi-agent debate |

H1a and H1b are the proposal's core. H1c is a distinct mechanism the proposal also touches
(§7 of the proposal). They must be measured separately — §12.

---

## 2. What the literature establishes, and what it does not

### 2.1 It establishes context degradation — clearly

**Hong, Troynikov & Huber, "Context Rot: How Increasing Input Tokens Impacts LLM
Performance", Chroma, 14 July 2025** (`https://research.trychroma.com/context-rot`).
18 models including GPT-4.1, Claude 4, Gemini 2.5, Qwen3. Verified from the primary source:

- Performance **degrades as input length grows**, and the study's design holds task
  complexity constant while varying only input length — *"allowing us to directly measure the
  effect of input length alone."*
- The degradation is **not a near-limit effect**: it appears well before the advertised
  context window is full.
- **Lower needle–question similarity degrades faster** with length. Verbatim: *"as
  needle-question similarity decreases, model performance degrades more significantly with
  increasing input length."*
- **Distractor impact amplifies with length**, across current frontier models.
- **Haystack structure matters**: shuffling sentences to destroy logical flow *"consistently
  shows an impact on how models process long inputs"* — i.e. coherence of the surrounding
  text is itself a variable.

The study explicitly separates **distractors** (topically related to the needle, but not
answering it) from **irrelevant content** (unrelated). Distractors are the harmful class.

**Liu et al., "Lost in the Middle: How Language Models Use Long Contexts", TACL 2023** —
the U-shaped positional bias: information at the beginning or end is used better than
information in the middle.

**Nisbett, Zukier & Lemley — the dilution effect.** The classic result: adding
**nondiagnostic** information (information independently judged to have little predictive
value) **reduces the influence of diagnostic information**, producing *less extreme*
judgments. This is the closest theoretical match to H1a, and it is a human-judgment result,
not an LLM result — it establishes the *phenomenon* is real and not an artifact of
transformers, but it does not establish the mechanism in an LLM.

### 2.2 It establishes LLM trading conservatism — but by a different mechanism

**Li, Kim, Cucuringu & Ma, "Can LLM-based Financial Investing Strategies Outperform the
Market in Long Run?" (FINSABER), arXiv:2505.07078.** Verified from the abstract, verbatim:

> *"Our market regime analysis further demonstrates that LLM strategies are **overly
> conservative in bull markets**, underperforming passive benchmarks, and **overly
> aggressive in bear markets**, incurring heavy losses. These findings highlight the need to
> develop LLM strategies that are able to prioritise **trend detection and regime-aware risk
> controls** over mere scaling of framework complexity."*

This is direct evidence that the *outcome* the owner observed is a known, documented
failure mode of LLM trading agents. **But the authors attribute it to regime
miscalibration, not to context volume.** That distinction matters: FINSABER supports the
*problem statement* and does **not** support the *proposed cause*.

### 2.3 It does NOT establish H1 as a law

This must be stated plainly, because the design's premise depends on it.

- There is **no established general rule** that long context makes LLMs risk-averse.
- Refusal behaviour under length is **model-specific and non-uniform**. The Context Rot
  report itself notes rare task refusals (69 of 194,480 calls, 0.035%) — a negligible rate,
  and *not* the phenomenon in question.
- Where conservatism has been observed under ambiguity, it is reported for **specific model
  families**, not universally.

**Wang et al., "Rethinking Prospect Theory for LLMs: Revealing the Instability of
Decision-Making under Epistemic Uncertainty", arXiv:2508.08992** is directly relevant to
H1b. Its finding: Prospect Theory does **not** consistently describe LLM decision-making,
and the fitted parameters are **sensitive to epistemic uncertainty** — i.e. how uncertainty
is *expressed* in the prompt changes the decision. That is evidence that uncertainty framing
is a live variable, which is what H1b claims.

**Multi-agent debate** (H1c) has a documented failure mode: LLM agents align with the
numerically dominant side and with more persuasive agents; homogeneous debate can amplify
errors through sycophantic conformity and *"consensus collapse"*, sometimes performing
worse than a single isolated model. More rounds do not reliably help.

### 2.4 Consequence for this design

**The premise is plausible and partially evidenced, not proven.** The design is therefore
built so that it is **cheap to falsify** (§12) and so that **no step depends on H1 being
true**. Every phase is independently justified by the degradation results in §2.1, which
are much better established.

---

## 3. Measured baseline: what the decision layer receives today

All figures from the live run `reports/QCOM_20260919_175840` (2026-09-19 17:58).
Token counts are `chars / 4` — **an approximation**, stated as such throughout.

### 3.1 The forced-evidence block — the dominant contributor

`TRADINGAGENTS_ANALYST_FORCED_TOOLS=ALL` is set in `.env` (code default `[]`,
`default_config.py:643`). With it set, `evidence_gather.gather_for_analyst_node`
(`tradingagents/agents/utils/evidence_gather.py:539`) deterministically gathers every
auto-gatherable tool and renders a block that is interpolated into each analyst's
**system message** as `{evidence_block}`.

The rendered blocks are persisted in `tool_evidence.json` under `_rendered_block`:

| Analyst | Rendered block | ~tokens |
|---|---:|---:|
| fundamentals | 64,443 chars | **~16,110** |
| market | 38,953 chars | ~9,738 |
| news | 35,976 chars | ~8,994 |
| **total** | **139,372 chars** | **~34,843** |

`evidence_gather.py:563` documents the split precisely: the rendered block is *"returned for
the reduce prompt"*, while the full leaf set *"stays in `tool_evidence` for the verifier;
only the prompt prefix must not move."* So the block is not an artifact of the report write —
it is the prompt payload.

**This is the single largest context contributor in the system**, and it sits on the
*analyst* prompts, upstream of every decision. The raw leaf store is larger still —
`tool_evidence.json` is 397,354 chars (~99,338 tokens) — but is not itself prompted.

### 3.2 What the analysts then produce, and what the decision layer reads

| Artifact | chars | ~tokens |
|---|---:|---:|
| `1_analysts/fundamentals.md` | 11,844 | 2,961 |
| `1_analysts/market.md` | 11,178 | 2,794 |
| `1_analysts/news.md` | 753 | 188 |
| `1_analysts/sentiment.md` | 402 | 100 |
| `2_research/` (bull, bear, manager, structured) | 7,764 | 1,941 |
| `3_trading/trader.md` | 7,827 | 1,956 |
| `4_risk/` (3 debators + structured) | 15,888 | 3,972 |
| `5_portfolio/decision.md` | 3,437 | 859 |
| `complete_report.md` | 55,300 | 13,825 |

**Correction to the naive picture: the PM never sees the analyst reports.** The
Portfolio Manager interpolates ten state-derived keys into a single f-string prompt
(`tradingagents/agents/managers/portfolio_manager.py:261`), and **none of them is an analyst
report** - grepping that module for `market_report`, `news_report`, `sentiment_report` and
`fundamentals_report` returns nothing. The four reports reach the decision only *through* the
Research Manager's `investment_plan` and the Trader's `trader_investment_plan`. So the
research/decision split the proposal asks for is **already enforced at the PM**: the analyst
reports are two compression hops away from the final decision, not one.

The engine blocks in `run_card.json` are small by comparison — the largest is
`event_state` at 3,863 chars, then `technical_score` 3,655, `fundamental_score` 3,316,
`quant_scorecard` 3,195, `regime_score` 3,160, `risk_score` 2,379, `sentiment_score` 1,636,
`trade_score` 824, `news_score` 75.

### 3.3 The observation that motivates the design

**~34,843 tokens of forced evidence are injected to produce ~6,044 tokens of analyst
report.** The compression ratio is roughly 5.8 : 1, and it is performed by the same model
that is then asked to be decisive.

The evidence block is not a distractor set in the Context Rot sense — it is the run's own
measured facts, which is exactly what the forced-tool design intends. But by the report's
own finding, *"lower similarity needle-question pairs increases the rate of performance
degradation"*: a tool leaf is a high-similarity item for the question it answers and a
low-similarity one for every other question in the same prompt. With ~47 leaves for
fundamentals (`tool_evidence.json` `fundamentals` key), most of the block is low-similarity
relative to any single claim the report must make.

`[INFERENCE]` The above does not prove H1a. It establishes that the condition H1a describes
is present and large. §12 is how it gets tested.

---

### 3.4 Prior in-repo measurement of exactly this axis

`docs/implementation_plan_openrouter_large_prompt_ttft.md` (implemented 2026-09-14) already
framed and partly measured this. Its **W5** workstream is *"Shrink the prompt that actually
504s (Trader/RM/PM terminals, tool catalog, evidence blocks)"*, and its §9 records what
remains open:

> *"W5 items 1-3 (analyst-side prefix) - the only remaining lever on absolute prefill time,
> and the one that is paid on every round: **115 bound tools for the market analyst
> (~48k-token static prefix: tool schema + the hand-written prose catalog that restates it)**
> plus the `_ALL` evidence block (87 gathered tools, `summary_window=12000` per leaf, no cap
> in `_render_evidence`). Needs its own quality-gated A/B (`scripts/context_ab.py`)."*

So §3.1's ~34,843 tokens of rendered evidence is **one of two** large contributors. The tool
schema plus the prose catalog that restates it is the other, and for the market analyst it is
larger still. Any design that only addresses the evidence block addresses the smaller half.

**W5 item 4 - the debate-stage report digest - was measured, and deliberately not shipped.**
A paired harness over 38 archived report trees (8 sets x 2 debate questions = 16 pairs),
condition A = reports verbatim, B = a recall-preserving digest (headings + first sentence per
section + a label-to-figures ledger, 55% smaller, 91% of distinct figures retained):

| metric (median) | A verbatim | B digest |
|---|---:|---:|
| prompt input tokens | 8,204 | **4,530 (-45%)** |
| fabricated figures (total across pairs) | 21 | **10** |
| grounded figures cited | 39 | 28 (-29%) |

The plan's recommendation: *"not worth shipping ahead of W5 items 1-3."*

**Two consequences that shape this design.**

1. **The harness already exists.** `scripts/context_ab.py` is titled *"Context A/B: does
   sending MORE computed results make the agent more accurate?"*. It runs paired experiments
   (tool selection, full surface vs shortlist; a computed block present vs absent), scores
   them per item, and reports an **exact McNemar** test plus the cost side, stating plainly:
   *"accuracy is not monotonic in context size, and the useful number is where it turns."*
   §12 must **extend** this harness, not build a parallel one.
2. **A smaller context has a measured quality cost, not only a benefit.** The digest arm cut
   tokens by 45% and *halved* fabrications (21 -> 10), but also cut grounded citations by 29%
   (39 -> 28). Any budget in §7 must therefore be validated on **grounding**, not only on
   decisiveness - which is exactly what `report_verifier` already measures.

## 4. What the repository already has

A substantial fraction of the proposal is **already built**. This section is the honest
mapping, and it is the reason the remaining design is small.

### 4.1 "Level 0 — deterministic gates" — BUILT

The proposal asks for gates the LLM should not debate. These exist.

| Component | Site | Behaviour |
|---|---|---|
| `risk_governor.govern` | `tradingagents/strategies/risk_governor.py:37` | PASS/WARN/REJECT over size, cap, drawdown, CVaR, liquidity, daily loss, HWM |
| `risk_hierarchy.evaluate_hierarchy` | `tradingagents/strategies/risk_hierarchy.py` | fixed precedence KILL > PORTFOLIO > TRADE > LIQUIDITY > REGIME; earliest REJECT wins |
| `risk_gate` producer | `tradingagents/graph/trading_graph.py:1113` | writes `final_state["risk_gate"]`, with a catalyst hard-block override |
| `get_risk_gate`, `get_composed_risk_gate` | `tradingagents/agents/utils/analysis_tools.py:821`, `:7148` | tool wrappers around `govern()` |
| `decision_guardrail.stabilize_decision` | `tradingagents/strategies/decision_guardrail.py:105` | **downgrade-only**; caps at Hold on severity ≥ high, or near-resistance without inflow |
| `signal_action.signal_action_split` | `tradingagents/strategies/signal_action.py:95` | gate can only downgrade; kill switch forces EXIT/NO_TRADE |

Note `_clamp_toward_hold` (`decision_guardrail.py:77`): positive strength → Hold, negative
strength passes through. The gates cap the **upside**; they do not manufacture direction.

### 4.2 "Decision context compiled deterministically" — BUILT

`trading_graph.py:688` builds `init_agent_state["computed_decision_context"]` from `_compiled_decision_context` (`trading_graph.py:1282`, returning at `:1568`) - **unconditionally**, not behind a gate. It compiles compact deterministic lines:

- the computed regime gate (`regime_gate_read`), with `catalyst_window` named
  `unavailable_pre_graph` rather than asserted false (the D-11 resolution),
- the trade plan card (`build_trade_plan`),
- the risk snapshot (CVaR, book CVaR, book stress, measured book drawdown vs limit),
- the limits registry and fixed-risk size (`enable_risk_governor`).

The comment at `:685` states the intent: *"so the Trader / PM / 3 risk debators get hard
computed data, not LLM prose. Always advisory - never blocks."*

### 4.3 "Deterministic synthesis: composite, agreement, confidence" — BUILT

The proposal's §2 asks for a deterministic synthesis block. It exists:

| Component | Site |
|---|---|
| `weighted_consensus` | `tradingagents/strategies/consensus.py:32` |
| `consensus_from_score` | `tradingagents/strategies/consensus.py:25` |
| `should_hold` (divided book → HOLD) | `tradingagents/strategies/consensus.py:57` |
| `score_band_for` | `tradingagents/strategies/decision_guardrail.py:39` |
| `score_engine.combine` | `tradingagents/strategies/score_engine.py:134` |

`combine` returns `{score, coverage, floor, components, present, withheld, label, basis}` —
a score **with its coverage, its required floor, and a named withholding reason**, which is
strictly more informative than the proposal's `{score, direction, confidence}` shape.

**What does NOT exist: a directional agreement count over the engines.** `agreement_score`
(`tradingagents/strategies/consensus.py:14`) operates on **ratings/stances**, not on engine
scores. Nothing computes "7 of 8 engines lean the same way", and `trade_score` carries no
direction (`band=None`). The proposal's illustrative `Agreement 7/8` line has no producer
today - the engines report scores, not directions.

The PM prompt already consumes these. `portfolio_manager.py` assembles a `consensus_line`
(*"**Computed risk-consensus** (deterministic): agreement=… label=… weighted_stance=… (n=…)
- set your PortfolioDecision.consensus to this level, not a guess"*), a `cvar_line`, a
`liq_line`, and `computed_context`.

### 4.4 "Pre-debate independent reads" — BUILT

`independent_vote.create_independent_stance_node` (`tradingagents/agents/utils/independent_vote.py:156`)
samples stances **before any cross-talk**, via `_sample_stance` (`:117`) and
`IndependentStance` (`tradingagents/agents/schemas.py:354`), and computes
`independent_agreement` (`:205`). Roles: `RISK_ROLES = ("aggressive","conservative","neutral")`
and `RESEARCHER_ROLES = ("bull","bear")` (`:37-38`).

This is the proposal's §5 concern (separating independent judgment from debate contamination)
**already implemented for the decision roles**.

### 4.5 "Engine ownership / compact per-analyst evidence" — BUILT

`quant_scorecard.ENGINE_SECTIONS` (`tradingagents/strategies/quant_scorecard.py:119`) is the
single table deciding where each engine's result appears; `ANALYST_SECTIONS` (`:131`) and
`engines_for_analyst` (`:134`) are derived from it. `report_hygiene.engine_score_block`
(`tradingagents/agents/utils/report_hygiene.py:77`), `scorecard_context_block` (`:228`) and
`engine_report_section` (`:301`) render engines into prompts and reports from one snapshot.

### 4.6 Claim-level verification — BUILT

`debate_claim.verify_claim` (`tradingagents/strategies/debate_claim.py`) verifies each
debater claim against deterministic ground truth, with severity triage driving
penalty / TRIGGER_REGEN / ABORT_TO_BASELINE via `structured_debate.create_debate_l1`.
`report_verifier.verify_report_dir` (`tradingagents/agents/utils/report_verifier.py:4320`)
runs post-hoc over ~27 deterministic metric families plus an LLM claim pass.

---

## 5. Gap analysis

| Proposal item | Status | Evidence |
|---|---|---|
| §1 Separate research vs decision context | **PARTIAL** | `computed_decision_context` is the decision channel (`trading_graph.py:688`); but the analyst prompts receive ~34,843 tokens of forced evidence (§3.1) and no budget is enforced anywhere |
| §2 Decision Packet | **PARTIAL** | engines + `consensus.py` + PM compact lines exist; no single bounded packet, no enforced size |
| §3 Level 0 gates | **BUILT** | §4.1 |
| §3 Level 1 quant evidence | **BUILT** | `score_engine.combine`, `ENGINE_SECTIONS` |
| §3 Level 2 analyst summaries | **PARTIAL** | the PM never reads the reports directly (§3.3); compression is via RM `investment_plan` + Trader plan, i.e. LLM-authored, not deterministic |
| §3 Level 3 conditional expansion | **NOT PRESENT** | the debate always runs; nothing triggers retrieval on disagreement |
| §4 Evidence budget | **PARTIAL** - see also W5 | two char bounds exist (`quant_scorecard.SCORECARD_MAX_CHARS = 1200` at `quant_scorecard.py:545`; `structured_debate.py:239` bounds ctx_rest to 3000 chars, and `:753` slices `computed_decision_context` to 3000). No bound or measurement on the PM/Trader/RM prompts or the analyst evidence blocks |
| §5 Uncertainty vs negative evidence | **NOT PRESENT** | no such distinction exists anywhere in the codebase |
| §6 Contradiction detection | **PARTIAL** | `report_verifier` flags same-metric conflicts post-hoc; nothing feeds a conflict ledger into the decision |
| §7 Challenge pass | **NOT PRESENT** | see §5.1 |
| §8 Invalidation threshold | **PARTIAL** | `falsification.FalsificationCondition.invalidation_level` (`tradingagents/strategies/falsification.py:30`) exists per-metric; `invalidation_ledger` is advisory and never gates |
| §9 Decision vs explanation | **PARTIAL** | the PM chooses; `_binding_constraint` (`reporting.py:548`) labels afterwards |
| §10 Conservatism metric | **PARTIAL** | `scripts/context_ab.py` already A/Bs context size against *accuracy* with an exact McNemar test; the missing arm is the **decision-outcome** variable (BUY/HOLD/SELL), i.e. conservatism |

### 5.1 The challenge pass, precisely

The scout finding is worth quoting because it is the sharpest gap:

> *"there is NO post-decision 'challenge pass that can only invalidate, never add caution',
> and NO decision-level 'invalidation threshold' — invalidation exists only as
> thesis-formation falsification conditions and an advisory ledger."*

What exists instead:

- `falsification.monitor_conditions` (`tradingagents/strategies/falsification.py:58`) —
  per-metric breach monitoring with an `invalidation_level` (`:30`).
- `invalidation_ledger` — *"advisory persistent invalidation record; never gates a
  decision."*
- `report_disclosure.invalidation_conditions()` — *">=1 invalidation per decision, rendered
  only."*

So the repo records invalidations. It never **runs a pass whose only permitted output is
invalidation**. That is the gap the proposal's §7–§8 target, and §10 below is its design.

---

## 6. Design: the Decision Packet

**Principle.** The decision model receives one bounded, deterministic block. Nothing else
about the trade is in the prompt.

**Content** (all already computable from §4; the work is assembly and bounding, not new
maths):

```
PACKET v1 — <TICKER> — <date>
─────────────────────────────────────────────
PERMISSION   <TRADE_ALLOWED | BLOCKED>  gate=<PASS|WARN|REJECT> reason=<...>
COMPOSITE    <score>  coverage=<c>  floor=<f>  basis=<...>
ENGINES      fundamental <s> [cov c]  technical <s> [cov c]  regime <s> [cov c]
             risk <s> [cov c]  sentiment <s> [cov c]  news <s|NA>  event <s|NA>
AGREEMENT    <n>/<m> directional  weighted_stance=<x>  label=<...>
CONFLICT     <k> same-metric conflicts (see ledger)
RISK         CVaR <x> (budget <b>)  drawdown <d> (limit <l>)  liquidity <verdict>
LEVELS       entry <..>  stop <..>  target <..>  size <..>
FALSIFIERS   <the >=1 invalidation conditions already required by report_disclosure>
```

Rules, each of which is a testable invariant:

1. **Every number carries its coverage or a named gap.** Never a bare number (the existing
   `combine` contract; `NA` never `0`).
2. **The packet is a pure function** of state — no model call, no vendor call.
3. **The packet is bounded** (§7).
4. **The packet does not instruct.** It reports; the model decides.
5. **`TradeScore` is not in the packet as an instruction** — it is already labelled
   downstream (master rule 17; `ScoreContextContract.md` §13.2).

**Where it is consumed:** the Trader, the PM, and the three risk debators — i.e. the same
set that today receives `computed_decision_context` (`trading_graph.py:688`). The packet is
the *bounded successor* to that channel, not a parallel one.

---

## 7. Design: the evidence budget

The proposal's §4. Made enforceable rather than aspirational:

```python
DECISION_PACKET_BUDGET = {
    "packet_max_chars": 12_000,     # ~3,000 tokens
    "engine_row_max_chars": 160,
    "conflict_max_rows": 12,
    "falsifier_max_rows": 8,
}
```

**Enforcement.** A pure function `render_decision_packet(state, cfg) -> str` that
**asserts** its own size and truncates by dropping whole rows — never mid-row, never a
number without its label. When it must drop, it appends a visible
`[packet truncated: N rows dropped]` marker, in the same spirit as `_finalize_section`'s
truncation marker (`tradingagents/reporting.py:135`).

**Measurement is the point.** A `packet_chars` field written into `run_card.json` makes the
budget observable per run. Today no such measurement exists for any prompt.

**Non-goal:** the packet budget is **not** applied to the analyst prompts. §3.1 is a real
finding, but shrinking the forced-evidence block changes what the analysts can know — that is
a separate decision for the owner, and it is listed as such in §13 Phase 0.

---

## 8. Design: uncertainty vs negative evidence

The proposal's §5, and the one genuinely new *conceptual* contribution.

**The defect it targets.** A prompt containing 6 bullish facts and 4 unknowns invites the
model to compute "mixed". The unknowns are not evidence against the thesis; they are
*absence of evidence*. The literature (§2.3, arXiv:2508.08992) shows LLM decisions are
sensitive to exactly this — how epistemic uncertainty is expressed.

**The design.** Three counters, never one:

```
EVIDENCE     bullish=<b>  bearish=<d>  neutral=<n>
UNCERTAINTY  <u> named gaps: <list>
```

with a hard rule stated in the prompt:

> **An uncertainty is not a bearish fact.** `NA`/`unavailable`/`unmeasured` entries must
> never be counted as evidence against a thesis. Only measured facts with an adverse sign
> are bearish.

**Implementation note.** The repo already distinguishes these rigorously at the data layer —
`None` is never `[]`, missing is `unavailable` never `0`, a gap is named with a reason
(`GAP_FPI_MARKET_CAP` etc.). What is missing is the **aggregate count** that lets the model
see the distinction without re-deriving it. The counters are a rendering of facts the
engines already carry, so this is a presentation change, not a new measurement.

**Testable invariant.** A run with identical bullish facts but additional *unmeasured*
engines must produce identical `bullish`/`bearish` counts and a larger `UNCERTAINTY` count.

---

## 9. Design: the conflict ledger

The proposal's §6. Partially exists — `report_verifier` already detects same-metric
conflicts (`verify_flags.json`, the `INTERNAL_CONFLICT` class).

**Design.** Promote the detected conflicts into a compact ledger in the packet:

```
CONFLICT  ev/ebit      5.50 vs 4.40     sections: ratios vs analyst-verdict
CONFLICT  altman_z     19.70 vs 20.84   sections: quality-factors vs analyst-verdict
```

Each row names **both source sections**, so the model adjudicates a *named* disagreement
rather than discovering it in 20,000 tokens. Unresolved conflicts are counted
(`CONFLICT <k>`) so the model can weigh disagreement explicitly.

**Dependency:** this is only as good as the verifier's classification. The currently-open
same-metric pairs (LULU `ev/ebit`, LULU `scenario dcf base`, LRCX `diluted eps`, LRCX
`altman z`, AMZN `ev/ebit`) must first be classified as real two-producer defects or
expected basis differences — otherwise the ledger will faithfully report noise.

---

## 10. Design: the challenge pass

The proposal's §7–§8, and the sharpest genuine gap (§5.1).

**Design.** After the decision, one additional call with a **closed output vocabulary**:

```
CHALLENGE — you may ONLY invalidate.
Question: does any of the following hold?
  (a) a falsifier from the FALSIFIERS list is breached
  (b) the packet contains a contradiction that the decision did not address
  (c) the decision asserts a number the packet does not carry
Output: {invalidated: bool, which: <(a)|(b)|(c)|none>, evidence: <packet row>}
```

**Rules that make it different from the debate:**

1. **Closed vocabulary.** The pass cannot invent a new reason for caution. "Something could
   go wrong" is not in the vocabulary.
2. **Evidence must be a packet row.** An objection citing nothing is discarded.
3. **It can only downgrade.** Same shape as `stabilize_decision`
   (`decision_guardrail.py:105`) — a downgrade-only stabilizer, already an established
   pattern in this repo.
4. **It cannot raise caution from absence.** An `UNCERTAINTY` entry is not a valid
   invalidation (the §8 rule, enforced mechanically here).

**Why this is not the existing debate.** The debate's job is to surface risk and explain.
Its failure mode is documented (§2.3): conformity, consensus collapse, and a persuasive
agent dragging the group. A closed-vocabulary pass has no room for that — it either finds a
breach or it does not.

---

## 11. Design: conditional expansion

The proposal's §3 Level 3 — *"retrieve evidence only when there is disagreement."*

```
composite direction  ──►  agreement high  ──►  decide from the packet
                          agreement low   ──►  expand: attach the analyst reports
```

**Trigger inputs already exist:** `independent_agreement` (`independent_vote.py:205`),
`weighted_consensus`/`should_hold` (`consensus.py:32`, `:57`), and the conflict count (§9).

**Rule.** Expansion is **additive and bounded**: the expanded context attaches named
sections, and the run records `context_mode: "packet" | "packet+expanded"` in
`run_card.json`. This makes the expansion rate measurable — a precondition for §12.

**Design caution.** `should_hold` already implements *"a divided book is not a directional
call"*. Conditional expansion must not become a second, weaker route to the same
conclusion. Expansion adds *information*; it must not add *caution*. The distinction is
enforced by keeping the challenge pass (§10) closed-vocabulary.

---

## 12. The experiment: measuring H1 instead of assuming it

The proposal's §10, and the highest-value item in this document. **If H1 is false, most of
§6–§11 is unnecessary** — so this is Phase 1, not Phase 5.

### 12.1 Design

Four arms, same ticker, same date, same market snapshot, same model parameters:

| Arm | Context |
|---|---|
| **A** | quant engines only |
| **B** | quant + Decision Packet (§6) |
| **C** | quant + packet + analyst summaries |
| **D** | full current context (today's behaviour) |

Measure per arm: `BUY`/`HOLD`/`SELL` distribution, decision entropy, confidence,
`packet_chars`, and — where the tree allows — subsequent realized return.

### 12.2 The metric

```
CCI = P(no-trade | full context) − P(no-trade | compact context)
```

`CCI > 0` supports H1a. `CCI ≈ 0` falsifies it, and the conservatism must be explained by
H1b, H1c, or something outside this design.

### 12.3 What the repo already provides - do not build a new harness

`scripts/context_ab.py` **is** this experiment, minus the outcome variable. It already:

- builds paired items from the tool surfaces and from the real card builders
  (`trade_plan.measured_inputs` + `build_trade_plan`, `risk_governor.build_risk_snapshot`) so
  *"the harness cannot drift from the real card"*;
- scores per item and runs an **exact McNemar** paired test (`mcnemar_exact`);
- counts **ungrounded figures** (`ungrounded_figures`) - the grounding metric §3.4 shows a
  budget can damage;
- reports the **cost side** (tools presented, characters of context);
- runs hermetically (`--demo`) or live (`--live --provider --model`).

**The one missing thing is the outcome variable.** Every existing item is scored on
*accuracy* or *grounding*. To test H1 the harness needs a third item type whose score is the
**decision category** (Buy/Overweight/Hold/Underweight/Sell), so the report can print the
distribution per arm and the CCI of §12.2. That is an addition to an existing script, not a
new subsystem.

Other repo affordances that make the ablation cheap:

- `batch.py --symbols ... --date ... --depth shallow` runs a real end-to-end decision.
- `scripts/score_panel.py` already evaluates offline over a symbol/date grid
  (`--evaluate-only`, `--json`).
- `score_history.record_score` / `score_movement` (`tradingagents/strategies/score_history.py`)
  persists per-run observations.
- The rating is a **structured field**, not prose - `pm_decision.rating`
  (`reporting.py:636`) - so the outcome is a clean categorical variable needing no parsing.

This is unusually cheap here, because the machinery exists:

- `batch.py --symbols ... --date ... --depth shallow` runs a real end-to-end decision.
- `scripts/score_panel.py` already runs offline engine evaluation over a symbol/date grid
  with `--evaluate-only` and `--json`.
- `score_history.record_score` / `score_movement`
  (`tradingagents/strategies/score_history.py`) already persists per-run observations.
- The rating is a **structured field**, not prose — `pm_decision.rating`
  (`reporting.py:636`) — so the outcome is a clean categorical variable with no parsing.

**A note on cost.** Arm D is today's behaviour and its cost is already known. Arms A–C are
cheaper than D by construction (that is the hypothesis). So the experiment's marginal cost
is roughly 3 extra runs per ticker.

### 12.4 The honest caveat

`reports/` is gitignored and the historical record is real but not a controlled sample. A
retrospective CCI computed from existing trees is **not** an experiment — it confounds
context size with ticker, date, and regime. The four-arm design must run fresh, on one
snapshot, to be evidence. `[INFERENCE]` A retrospective pass is still worth running first as
a cheap signal, with its confounds stated.

---

## 13. Phasing

Each phase is independently justified; none requires H1 to be true.

| Phase | Work | Gate |
|---|---|---|
| **0** | **Measure only.** Record `packet_chars`, `analyst_prompt_chars`, `evidence_block_chars` into `run_card.json`. No behaviour change. | the numbers in §3.1 become per-run observable |
| **1** | **The ablation** (§12). Answer H1 before building for it. | a CCI figure with its confounds stated |
| **2** | `render_decision_packet` (§6) + budget (§7), consumed by the same three roles that read `computed_decision_context` today | packet ≤ budget; byte-identical when the master gate is off |
| **3** | Uncertainty/evidence counters (§8) | the §8 invariant test |
| **4** | Conflict ledger (§9), after the open verifier pairs are classified | conflicts named with both sections |
| **5** | Closed-vocabulary challenge pass (§10) | cannot raise caution from an uncertainty entry |
| **6** | Conditional expansion (§11) | `context_mode` recorded; expansion rate measurable |

**Phase 0 is the recommendation.** It is small, it is not a behaviour change, and it turns
§3's one-off measurement into a per-run series — which is what Phase 1 needs and what the
repo currently lacks for any prompt.

---

## 14. Acceptance criteria

1. **Byte-identical when off.** Every phase behind a gate defaulting `False`; gate off ⇒
   byte-identical output. (The repo's established gate contract.)
2. **A gate is a membership switch, not an inert body** — same rule.
3. **New gates registered in five places**: `default_config.py` `DEFAULT_CONFIG`, an
   `_ENV_OVERRIDES` row, `docs/gate_registry.md` §6, the `REGISTRY` dict in
   `tests/test_gate_env_toggles.py`, and `.env.example`.
4. **The packet is a pure function** — no vendor call, no model call, no state mutation.
5. **No number without its coverage or a named gap.**
6. **An uncertainty is never counted as bearish** — asserted by test, not by prompt text.
7. **The challenge pass cannot raise caution from an uncertainty entry.**
8. **Every new public function in `tradingagents/strategies/` or `tradingagents/dataflows/`
   has a reference outside its own module** (`tests/test_calc_agent_wiring.py`).
9. **No new derived quantity with two independent producers** (master rule 15).
10. **Failing-first proofs mutate behaviour, never stash the source.**

---

## 15. Non-goals and risks

**Non-goals.**

- **Not** an attempt to make the model less conservative by prompt tuning. The proposal is
  explicit on this and the design follows it: *"I wouldn't try to make DeepSeek less
  conservative. I'd make the architecture ensure that conservatism requires actual
  contradictory evidence."*
- **Not** a change to the risk gates (§4.1). They cap the upside by design and that is a
  separate, deliberate contract.
- **Not** a change to the analyst prompts. §3.1 identifies the forced-evidence block as the
  largest contributor, but shrinking it changes what the analysts can know — an owner
  decision, not a design consequence.
- **Not** a rewrite of the debate.

**Risks.**

| Risk | Mitigation |
|---|---|
| **H1 is false** — the conservatism comes from elsewhere (regime miscalibration per FINSABER) | Phase 1 before Phase 2; the packet is independently justified by §2.1 |
| **Compression loses a decisive fact** — semantic drift, constraint loss | the packet is a *pure function of state*, so nothing is summarized away by a model; and the full evidence remains retrievable (§11) |
| **The packet becomes a second decision-maker** — a high composite starts to read as an instruction | `RESEARCH_ONLY` labelling; `TradeScore` printed last and labelled downstream (already the owner's §13.2 decision) |
| **The budget silently truncates a decisive row** | truncation is visible and counted, never silent |
| **The challenge pass becomes a caution generator** | closed vocabulary; evidence must be a packet row; downgrade-only |
| **Conditional expansion becomes a second route to HOLD** | §11's caution; the challenge pass stays closed-vocabulary |

---

## 16. Summary

The proposal is **directionally right and mostly already built**. The repository has the
deterministic gates, the deterministic decision context, the deterministic synthesis
(`consensus.py`), the pre-debate independent reads, and the engine ownership map.

What it does **not** have, in order of value:

1. **Any measurement of prompt size.** §3.1 is a one-off; nothing records it per run.
2. **Any test of the hypothesis on the axis that matters.** The premise is plausible
   (§2.2) but not established (§2.3). The harness exists - `scripts/context_ab.py` already
   A/Bs context size against accuracy and grounding with an exact McNemar test - but nothing
   measures the **decision outcome** (Buy/Hold/Sell) against context size. That is one item
   type, not a new subsystem.
3. **A bounded decision packet** — the compact channel exists (`computed_decision_context`)
   but is neither bounded nor measured.
4. **The uncertainty/evidence distinction** (§8) — the one genuinely new concept, and the
   one that maps directly onto this repo's existing rigour about `NA` vs `0`.
5. **A challenge pass that can only invalidate** (§10) — recorded invalidations exist;
   an invalidating *pass* does not.

The single most useful next action is **Phase 0**: record the sizes. It is small, it changes
no behaviour, and it converts the motivating observation from an anecdote into a time series.

---

## 17. References

1. Hong, K., Troynikov, A., Huber, J. **"Context Rot: How Increasing Input Tokens Impacts
   LLM Performance."** Chroma Technical Report, 14 July 2025.
   https://research.trychroma.com/context-rot — 18 models; performance degrades with input
   length at constant task complexity; lower needle–question similarity degrades faster;
   distractor impact amplifies with length; haystack structure matters. *(verified from the primary source)*
2. Liu, N. F. et al. **"Lost in the Middle: How Language Models Use Long Contexts."**
   TACL 2023. — U-shaped positional bias.
3. Li, W. W., Kim, H., Cucuringu, M., Ma, T. **"Can LLM-based Financial Investing Strategies
   Outperform the Market in Long Run?"** arXiv:2505.07078 (FINSABER). — *"LLM strategies are
   overly conservative in bull markets … and overly aggressive in bear markets."*
   *(verified from the primary source)*
4. Wang, R. et al. **"Rethinking Prospect Theory for LLMs: Revealing the Instability of
   Decision-Making under Epistemic Uncertainty."** arXiv:2508.08992. — Prospect Theory does
   not consistently describe LLM decisions; parameters are sensitive to epistemic
   uncertainty. *(verified from the primary source)*
5. Nisbett, R. E., Zukier, H., Lemley, R. E. **The dilution effect** — nondiagnostic
   information reduces the influence of diagnostic information, producing less extreme
   judgments.
6. Multi-agent debate literature on LLM conformity, sycophancy, and consensus collapse.
7. Over-refusal / over-abstention: the standard terms for refusing when an answer is possible.

**In-repo prior work (primary sources for §3.4).**

8. `docs/implementation_plan_openrouter_large_prompt_ttft.md` - W5 (prompt size), the
   measured digest A/B, and the still-open analyst-side prefix items.
9. `scripts/context_ab.py` - the existing context-size A/B harness (exact McNemar, grounding
   and fabrication scoring, hermetic `--demo` / live `--live`).
10. `reports/experiments_20260914/_digest_ab.json`, `_digest_ab_v3.json` - the raw digest
    A/B rows (gitignored; regenerable with the harness).
