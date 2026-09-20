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

**Revision history.** v1 (2026-09-19) grounded the proposal against the repository. v2
(2026-09-19, same day) incorporates owner feedback: the factorial experiment (§12.1), the
distribution metric set (§12.2), the packet's separation of evidence from recommendation
(§6), uncertainty moved into Packet v1 (§8), the contradiction materiality test (§10), and
the reordered phasing (§13). The earlier reasoning is kept rather than collapsed, so the
correction is legible.

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
| **H1b** | *Uncertainty framing* changes the decision. How unknowns are expressed - separately from evidence, or mixed into it - shifts the output. | presentation of epistemic uncertainty |
| **H1c** | *Debate* manufactures caution. Cross-talk converges on the least-committal position. | conformity in multi-agent debate |

H1a and H1b are the proposal's core. H1c is a distinct mechanism the proposal also touches
(§7 of the proposal). They must be measured separately - §12.

**H1b is stated as a *framing* effect, not as miscounting.** The stronger claim - that the
model literally counts an unknown as a bearish fact - is not what the experiment can isolate:
a packet that separates `UNCERTAINTY` also signals *that the architecture considers
uncertainty important*, so a behavioural change would not distinguish the two. The framing
hypothesis is the defensible one; the miscounting claim can be tested later if wanted.

---

### 1.1 The architectural invariant - true regardless of H1

One invariant is worth adopting on its own terms, because it asserts nothing causal:

> **Research can be large. Decision context cannot be large by accident.**

H1 claims *large context makes the model conservative*. The invariant claims only that the
size of the decision context is a **designed quantity with an owner**, rather than a byproduct
of how much evidence happened to be gathered. The invariant is the more defensible claim, it
is what §6-§7 implement, and it survives H1 being falsified.

This is the framing the rest of the document adopts: H1 is the *hypothesis*, the invariant is
the *design principle*.

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

**Independent reads are diagnostics, not evidence.** They must not become a second evidence
stream that the PM averages, or `independent_agreement` silently turns into a consensus the
model defers to. The question the architecture asks is not *"how many agents agree?"* but
*"given the bounded evidence, what does the decision model independently conclude?"* Under
that reading `independent_agreement` is a **measurement of disagreement** - which is exactly
what §11's conditional expansion needs as a trigger, and nothing else.

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

**The packet constrains the information channel, not the decision.** This is its most
important rule. A block printing `AGREEMENT 7/8` beside `COMPOSITE 82` invites the model to
compute `7/8 bullish -> BUY` instead of forming an independent judgement. The packet therefore
reports **evidence**, never a recommendation, and it carries **no `DECISION` line**.

The packet has **four semantic categories, kept visually distinct**:
`constraints != evidence != synthesis != decision`.

```
PACKET v1 - <TICKER> - <date>
=============================================
RISK CONSTRAINTS           <- NOT evidence; a decision-domain constraint
limits     max_position=.. book_cap=.. cvar_budget=.. drawdown_limit=.. sector_cap=..
book       cvar=<x> (budget <b>)  drawdown=<d> (limit <l>)  stress=<s>
liquidity  verdict=<...>  illiq=.. float_turnover=.. iwf=..
regime     verdict=<tradable|high-vol|fast-downtrend|catalyst-window|unknown> pass=<..>
permission unavailable_pre_decision - signal_action_split needs the post-decision gate verdict

EVIDENCE                   <- research evidence
engines  fundamental=<s> [cov c]  technical=<s> [cov c]  regime=<s> [cov c]
         risk=<s> [cov c]  sentiment=<s> [cov c]  news=<s|NA>  event=<s|NA>  trade=<s> [cov c]
DIRECTIONAL DISTRIBUTION   unavailable_pre_producer - no engine carries a directional sign,
                           and the independent stances are diagnostics, not evidence (§4.4)
UNCERTAINTY  <u> named gaps: <list>
CONFLICT     unavailable_pre_ledger - same-metric pairs are resolved post-hoc (§9, Phase 3)

SYNTHESIS                  <- labelled downstream, printed last
consensus  weighted_stance=<x>  label=<...>  agreement=<a>  n=<k>   (a DIAGNOSTIC, not evidence)
composite  score=<s>  coverage=<c>  floor=<f>  basis=<...>

TRADE PARAMETERS
levels  entry=<..> stop=<..> p1=<..> p2=<..> p3=<..> t1=<..> t2=<..>
size    shares=<..> capital_at_risk=<..> peak_deployed=<..>

FALSIFIERS
<the >=1 invalidation conditions already required by report_disclosure>
```

**Three rows in the sketch above cannot be filled at the packet's compile point, and each says
so.** `permission` and the `gate` verdict are **post-decision** facts - `risk_governor.govern`
produces `PASS|WARN|REJECT` in the graph's post-decision fold, and
`signal_action.portfolio_action_from_gate` derives the portfolio instruction from that verdict.
§16 puts the deterministic gates *downstream* of the decision, so a pre-decision packet cannot
carry them, and the packet prints the pre-decision constraints instead. `DIRECTIONAL
DISTRIBUTION` has no producer at all: the engine band tables are not directional and
`score_engine.align` erases each observation's sign, while the one existing counter measures
the independent stances - which §4.4 and criterion 22 forbid as evidence. `CONFLICT` is §9's
ledger, which is Phase 3. §13.4 records all of this as the build's findings.

**Why `permission` moved into its own block.** `PERMISSION TRADE_ALLOWED` is not evidence - it
is a *decision-domain constraint* already imposed by the deterministic gates. Listed among the
engine scores it would visually resemble one more bullish input. Under `RISK CONSTRAINTS` it
reads as what it is: a boundary the model reasons *within*, not a fact it weighs. (It is
printed as a named gap pre-decision - see above - and the same reasoning is why the row belongs
in this block and not in `EVIDENCE`.)

**Why a distribution would replace the agreement count - and why it cannot, yet.** `AGREEMENT
7/8` is the shape most likely to become an implicit instruction, and it also has no producer:
`agreement_score` (`tradingagents/strategies/consensus.py:14`) operates on ratings, not
engines, and nothing computes a directional agreement over engine scores. A **distribution**
would convey the same information without presenting a score to beat.

**But the counts are not cheap, and this sentence was wrong.** It read *"the engines already
carry a sign per component"*. Verified at the definition sites during the Phase 2 build, they
do not: every engine band table is non-directional (`REGIME_BANDS` =
benign/constructive/mixed/stressed/hostile, `RISK_BANDS` =
low risk/contained/moderate/elevated/high/severe, `NEWS_BANDS` =
high-information/informative/mixed/quiet/stale/no-signal), and `score_engine.align` maps each
component to a 0-100 value **in the favourable direction**, erasing the observation's sign. No
component dict carries a `sign` key. The one counter that exists measures the **independent
stances**, which §4.4 and acceptance criterion 22 forbid as evidence. The row is therefore a
**named gap** in v1 - see §13.4 Finding 2. A fabricated distribution would be worse than none,
because it would present a diagnostics stream as evidence and a reader could not tell.

**Why `UNCERTAINTY` is in v1 rather than a later phase.** Owner feedback accepted: if the
first packet omits it, the first experiment cannot test H1b at all. It costs nothing to add
(the engines already name their gaps) and it makes the H1b A/B nearly free (§8).

**Why `CONSENSUS` and `COMPOSITE` print last and carry a label.** The same reason `TradeScore`
already does (`docs/scores/ScoreContextContract.md` §13.2; master rule 17): the highest-level
summary is the most likely to be read as an instruction, so it goes last and says what it is.

Rules, each a testable invariant:

1. **Every number carries its coverage or a named gap** - never a bare number (`combine`'s
   existing contract; `NA` never `0`).
2. **The packet is a pure function** of state - no model call, no vendor call.
3. **The packet is bounded** (§7).
4. **The packet does not instruct**, and carries no `DECISION` line.
5. **Evidence is not a recommendation.** `ENGINE EVIDENCE`, `DIRECTIONAL DISTRIBUTION`,
   `CONSENSUS` and `COMPOSITE` are all classified as research evidence in the prompt text.

**Where it is consumed:** the Trader, the PM, and the three risk debators - the same set that
today receives `computed_decision_context` (`trading_graph.py:688`). The packet is the
*bounded successor* to that channel, not a parallel one.

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

The one genuinely new *conceptual* contribution - and, per owner feedback, **part of Packet v1,
not a later phase**.

**The defect it targets.** A prompt containing 6 bullish facts and 4 unknowns invites the
model to compute "mixed". The unknowns are not evidence against the thesis; they are *absence
of evidence*. The literature (§2.3, arXiv:2508.08992) shows LLM decisions are sensitive to
exactly this: how epistemic uncertainty is expressed changes the choice.

**The design.** Three counters, never one:

```
EVIDENCE     bullish=<b>  bearish=<d>  neutral=<n>
UNCERTAINTY  <u> named gaps: <list>
```

with a hard rule stated in the prompt:

> **An uncertainty is not a bearish fact.** `NA` / `unavailable` / `unmeasured` entries must
> never be counted as evidence against a thesis. Only measured facts with an adverse sign are
> bearish.

**The H1b experiment is nearly free.** Because the counters render facts the engines already
carry, the two packet variants differ only in presentation:

| Variant | Content |
|---|---|
| **Packet-A** | `bullish` / `bearish` / `neutral` only |
| **Packet-B** | the same counts, with `UNCERTAINTY` **explicitly separated** |

Comparing A and B on one snapshot isolates H1b: if B is materially more decisive than A, the
category error is real and the fix is a presentation change, not an architecture change.

**Implementation note.** The repo already distinguishes these rigorously at the data layer -
`None` is never `[]`, missing is `unavailable` never `0`, a gap is named with a reason
(`GAP_FPI_MARKET_CAP` etc.). What is missing is the **aggregate count** that lets the model see
the distinction without re-deriving it. This is a presentation change, not a new measurement.

**Testable invariant.** A run with identical bullish facts but additional *unmeasured* engines
must produce identical `bullish`/`bearish` counts and a larger `UNCERTAINTY` count.

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

**Classification is mechanical, and it matters.** Every conflict row carries a
`classification` computed from the verifier, not from the model:

```
CONFLICT #1  metric=EV/EBIT  source A=5.50 (ratios)  source B=4.40 (analyst-verdict)
             classification = unresolved
```

The three values are `unresolved`, `basis_difference` (both producers correct on their own
stated basis) and `defect` (one producer is wrong). Only `unresolved` may participate in a
challenge invalidation (§10) - and only under the materiality test there.

**Dependency: this is only as good as the verifier's classification. The currently-open
same-metric pairs have now been triaged, and the result is the opposite of what this section
assumed.** The five pairs, each traced to its mechanism by running the verifier's own
extractors over the trees that produced them:

| pair | classification | mechanism |
|---|---|---|
| LULU `ev/ebit` 5.50 / 4.40 | **detector defect** | a header cell naming two metrics - ``\| P/E / EV/EBIT / EV/EBITDA \| 7.68 / 5.50 / 4.40 \|`` - handed the **EV/EBITDA** leg to EV/EBIT |
| LULU `scenario dcf base` 173.58 / 132.5 | **detector defect** | ``\| Scenario DCF bear/base/bull \| 132.5 / 173.58 / 249.05 \|`` bound `base` to the **bear** value |
| JCI `altman z` 2.90 / 7.2461 | **detector defect** | ``\| Trap risk / Altman Z \| LOW / 2.90 (grey); Ohlson -7.2461 healthy \|`` read the **Ohlson** score as Altman Z |
| AMZN `ev/ebit` 35.02 / 32.79 | **basis_difference (disclosed)** | the verdict's value vs `get_ratios`; the report itself says *"Both pairs are basis differences to quote with their producers, not one number"* |
| QCOM `diluted eps` 1.87 / 5.01 | **basis_difference (disclosed)** | `$1.87 (2026/Q3)` vs `FY2025` - two labelled periods on one line |

**Not one is a two-producer defect (master rule 15).** Three are false positives in the
verifier's own value extraction, and two are basis differences the report disclosed. The
detector's flags are therefore **not yet trustworthy enough to feed a ledger** - which is
exactly what this section's dependency note warned about, now confirmed by measurement rather
than assumed.

Three defects were found and fixed on sight (§13.5), which took the corpus from **70 conflict
rows over 26 trees to 30 over 24** on the analyst reports. The flags that remain need a
**value-to-basis binding** these line-scoped regexes cannot express: when a line states two
periods *and* two values, binding each value to the period nearest it is still not enough,
because a value that recurs on a second line collects a second tag and the "every cluster has
its own period" test fails. That is a different mechanism, and it is **not** attempted here.

---

## 10. Design: the challenge pass

The proposal's §7-§8, and the sharpest genuine gap (§5.1). **Per owner feedback this is the
LAST phase, not the first**: it adds an LLM call and a fresh route to HOLD while the
fundamental question is still open.

**Design.** After the decision, one additional call with a **closed output vocabulary**:

```
CHALLENGE - you may ONLY invalidate.
Output: {invalidated: bool, which: <(a)|(b)|(c)|none>, evidence: <packet row>}
```

The only admissible grounds are:

| | Ground |
|---|---|
| **(a)** | a falsifier from the `FALSIFIERS` list is breached |
| **(b)** | the decision relied on a metric with an **unresolved** contradiction |
| **(c)** | the decision asserts a number the packet does not carry |

**Ground (b) carries a materiality test - this is the correction.** "The packet contains a
contradiction" is dangerous as stated: a model could read `fundamental = bullish` beside
`regime = bearish` as a contradiction and invalidate, which recreates exactly the conservatism
the design exists to remove. Contradiction invalidation is therefore **mechanical and
material**:

```
invalidate on (b) ONLY IF ALL THREE hold:
  1. the decision relied upon metric X,
  2. X has an UNRESOLVED contradiction
     (not basis_difference, not a resolved defect), AND
  3. the decision's conclusion depends materially on X.

Otherwise:
  contradiction exists -> record the contradiction -> do NOT invalidate.
```

**Directional disagreement is not a contradiction.** Two engines disagreeing about direction is
the normal state of evidence, and it is already represented by the distribution and the
consensus line (§6). A contradiction means **one metric, two incompatible values** - the shape
`report_verifier` already detects.

**The invariant, stated precisely:** *the challenge pass may downgrade only on one of the
three closed-vocabulary grounds; it may not create a new caution rationale.*

**Rules that make it different from the debate:**

1. **Closed vocabulary.** It cannot invent a new reason for caution. "Something could go wrong"
   is not in the vocabulary.
2. **Evidence must be a packet row.** An objection citing nothing is discarded.
3. **It can only downgrade** - the same shape as `stabilize_decision`
   (`tradingagents/strategies/decision_guardrail.py:105`), an established pattern in this repo.
4. **It cannot introduce a new caution rationale.** Invalidation *is* an increase in
   caution, so "cannot add caution" would be false. The real invariant is sharper: the pass
   may downgrade **only** on one of the three closed grounds, and may **not** create a new
   rationale for caution. It may legitimately turn `BUY -> HOLD` on a breached falsifier or a
   materially-relied-upon unresolved contradiction; it must never turn `BUY -> HOLD` because
   *"there is uncertainty"*, *"markets are unpredictable"*, or *"another engine is bearish"*.
   An `UNCERTAINTY` entry is not a valid invalidation - the §8 rule, enforced mechanically.
5. **Directional disagreement is not a contradiction** (the materiality test above).

**Why this is not the existing debate.** The debate's job is to surface risk and explain. Its
failure mode is documented (§2.3): conformity, consensus collapse, and a persuasive agent
dragging the group. A closed-vocabulary pass with a materiality test has no room for that - it
either finds a mechanical breach or it does not.

---

## 11. Design: conditional expansion

The proposal's §3 Level 3 — *"retrieve evidence only when there is disagreement."*

```
composite direction  ──►  agreement high  ──►  decide from the packet
                          agreement low   ──►  expand: attach the analyst reports
```

**Trigger inputs already exist** - and they are diagnostics (§4.4), not evidence:
`independent_agreement` (`independent_vote.py:205`),
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

The highest-value item in this document, and - per owner feedback - the thing to do **before**
touching the production architecture. **If H1 is false, most of §6-§11 is unnecessary.**

### 12.1 The methodological correction: a 2x2 factorial, not four arms

The original four arms (A quant only / B quant+packet / C quant+packet+summaries / D full)
**confound two variables**. The packet changes both the *volume* of information and its
*representation*. If B produced more BUYs than A, that could be fewer tokens, or deterministic
structure, or explicit uncertainty, or the removal of prose - and the four-arm design cannot
say which. That is acceptable for an architecture decision but **not** acceptable as a test of
H1a.

The correction is a factorial:

|  | **Compact** | **Large** |
|---|---:|---:|
| **Same (prose) representation** | C1 | C2 |
| **Decision Packet representation** | P1 | P2 |

```
C2 - C1  estimates the effect of moving from compact to large context
         WITHIN the prose representation.
P1 - C1  estimates the representation effect at compact size.
```

This separates *"the model is sensitive to context volume"* from *"the model decides better
when the information is structured"* - an important distinction the four-arm design cannot
make.

**But the volume claim must be qualified, and v2 overstated it.** `C2 - C1` is *not* pure
context volume. A digest changes the amount of information, the number of facts, ordering,
redundancy, positional placement, and possibly the linguistic form. So the honest reading is:

> **C2 - C1 isolates volume only to the extent that the two representations preserve the same
> evidence and differ primarily in context length.**

That is a requirement on the construction, not a property of the subtraction. **C1 must
therefore be built from C2 by a deterministic, information-preserving transformation with a
known deletion rule** - not by free summarization:

```
C2 = all evidence, original ordering
C1 = the same evidence CLASSES, bounded to first/last/representative rows
```

and the harness must **measure and report what was retained**:

| retention check | C1 vs C2 |
|---|---|
| unique metrics | |
| unique figures | |
| bullish facts | |
| bearish facts | |
| uncertainty facts | |
| source sections | |

**If retention is materially below 100% on any row, the contrast is not a *pure* volume
effect.** It is still a valid experiment - it demonstrates that the shorter representation
changes behaviour. What it cannot establish is that the difference is attributable **solely to
token volume**. So the finding is reported under its correct name rather than discarded:

| C1 vs C2 | conclusion |
|---|---|
| same evidence, different length | **context-volume effect** |
| different evidence, different length | **context-compression / content-retention effect** |
| same evidence, different organization | **representation effect** |

Without the retention table the first contrast is uninterpretable - you cannot tell which of
the three you measured.

### 12.2 Report the distribution, not only the CCI

CCI alone can mislead. Two cases with similar CCI and very different behaviour:

```
Full: BUY 10% HOLD 80% SELL 10%   Compact: BUY 20% HOLD 60% SELL 20%
Full: BUY 20% HOLD 60% SELL 20%   Compact: BUY 40% HOLD 20% SELL 40%
```

The second is more directional **and more volatile**: the model has not become better
calibrated, it has become less stable. CCI cannot distinguish these, so the primary output is
the full distribution:

| metric | C1 | C2 | P1 | P2 |
|---|---:|---:|---:|---:|
| BUY | | | | |
| HOLD | | | | |
| SELL | | | | |
| P(action) | | | | |
| P(no-trade) | | | | |
| Decision entropy | | | | |
| Directional entropy | | | | |
| Confidence | | | | |
| Expected-value direction | | | | |

plus `dHOLD`, `dBUY`, `dSELL` and `CCI` for each contrast.

**And the metric that matters most for H1a: the paired decision flip rate.** Aggregates can
hide the phenomenon - a model that flips `BUY` to `HOLD` on the same snapshot while other
snapshots flip the other way can leave the distribution nearly unchanged. Because the arms are
**paired on identical snapshots**, the transitions are directly observable:

```
flip_rate = changed_decisions / paired_runs

C1 -> C2 and P1 -> P2 transition matrices:
    directional -> hold        <- the phenomenon H1a predicts
    hold -> directional
    bullish -> bearish
    bearish -> bullish
```

For this application a **paired transition matrix is more informative than CCI**, and it is
what the harness should print first. Per paired snapshot the harness prints:

```
              C1 compact prose        C2 large prose
              -----------------       ----------------
LLM rating    HOLD                    BUY
direction     neutral                 bullish
confidence    0.61                    0.72
```

then aggregates the transitions with counts:

```
C1 -> C2
BUY   -> HOLD     17
HOLD  -> BUY       5
SELL  -> HOLD      9
HOLD  -> SELL      3
BUY   -> SELL      1
SELL  -> BUY       0
```

which shows whether the apparent conservatism is a **systematic directional -> HOLD
transition** - something the aggregate `HOLD: C1 63% / C2 71%` cannot distinguish from
unrelated churn in both directions.

### 12.3 Snapshot identity is an invariant, not an assumption

Pairing is only meaningful if the arms consume the **same deterministic evidence**. A market
refresh, changed news, or a regenerated engine result would masquerade as a context effect -
and this experiment is trying to detect something subtle in the model while everything else is
held constant. Every paired observation therefore records and asserts:

```
experiment:
    snapshot_id
    ticker              as_of
    data_snapshot_hash
    engine_output_hash
    model
    model_parameters_hash
```

> **Invariant: all arms for a paired observation must consume the same deterministic evidence
> snapshot.** A mismatch invalidates the pair; it is not a footnote in the report.

**The question the experiment answers is not "does HOLD decrease?".** It is:

> **Does removing context recover directional decisions without simultaneously making the model
> substantially less grounded, or less consistent with the available evidence?**

Every arm is therefore scored on **grounding** as well as decisiveness - which §3.4's digest
A/B already showed is necessary (tokens -45%, fabrications 21 -> 10, but grounded citations
39 -> 28). A budget that buys decisiveness with fabrication is a regression, not a fix.

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

**The one missing thing is the outcome variable.** Every existing item is scored on *accuracy*
or *grounding*. Testing H1 needs a third item type whose score is the **decision category**
(Buy / Overweight / Hold / Underweight / Sell), so the report can print the §12.2 distribution
and the CCI. That is an addition to an existing script, not a new subsystem.

Other repo affordances that make the ablation cheap:

- `batch.py --symbols ... --date ... --depth shallow` runs a real end-to-end decision.
- `scripts/score_panel.py` evaluates offline over a symbol/date grid (`--evaluate-only`, `--json`).
- `score_history.record_score` / `score_movement` (`tradingagents/strategies/score_history.py`)
  persists per-run observations.
- The rating is a **structured field**, not prose - `pm_decision.rating`
  (`tradingagents/reporting.py:636`) - so the outcome is a clean categorical variable needing no
  parsing.

### 12.4 Separate the raw decision from the gated action

The hypothesis concerns the **LLM decision**, not whether execution is permitted. In this
architecture a large share of `HOLD`/no-trade outcomes can originate *downstream* of the model:

```
LLM rating -> risk gate -> decision guardrail -> signal/action split -> execution permission
```

So an observed `HOLD` may be `LLM = BUY`, `risk_gate = REJECT`, `final = HOLD/NO_TRADE` - a
completely different phenomenon, and one this repo's gates produce **by design**
(`decision_guardrail.stabilize_decision:105` caps the upside; `signal_action.signal_action_split:95`
can only downgrade).

Every arm must therefore record both layers:

| layer | fields |
|---|---|
| **llm_output** (the PM model's structured decision, before ANY transformation) | `rating`, `direction`, `confidence` |
| **deterministic_postprocess** | `guardrail_rating`, `risk_gate`, `signal_action` |
| **execution** | `final_action` |

**The boundary is named, not implied.** `raw_rating` was the wrong label: it says "raw"
without saying *raw relative to what*, and six months from now it could be populated from an
already-normalised `PortfolioDecision` without anyone noticing. `llm_output` names the exact
point - the PM model's structured emit - so the experiment's definition is unambiguous:

> **Decision conservatism = change in the PM model's structured output, before any
> deterministic post-processing.**

with two separately reported quantities:

> **decision conservatism** = change in the PM model's structured output, *before* any
> deterministic post-processing.

> **execution conservatism** = change in the final executable action, *after* the gates.

Without this split, a conservatism result could be entirely an artifact of the risk system
doing its job.

### 12.5 The honest caveat

`reports/` is gitignored and the historical record is real but not a controlled sample. A
retrospective CCI computed from existing trees is **not** an experiment - it confounds context
size with ticker, date and regime. The factorial must run fresh on one snapshot to be evidence.
`[INFERENCE]` A retrospective pass is still worth running first as a cheap signal, with its
confounds stated.

---

## 13. Phasing

Per owner feedback the order is **measure, then experiment, then build** - and the challenge
pass is LAST, not first.

| Phase | Work | Gate |
|---|---|---|
| **0** | **Measure only** - the full telemetry block below into `run_card.json`. No behaviour change. **BUILT** (see §13.1). | the §3 numbers become a per-run series |
| **1** | **The factorial experiment** (§12). Answer H1a / H1b / the representation question *before* building for them. **BUILT** (see §13.2). | the §12.2 distribution + grounding per arm, confounds stated |
| **2** | **Decision Packet v1 + uncertainty counters** (§6, §8) - uncertainty is IN v1. **BUILT** (see §13.4). | packet <= budget; byte-identical when the master gate is off; the §8 invariant test |
| **3** | Conflict ledger (§9), after the open verifier pairs are classified | conflicts named with both sections + a mechanical classification |
| **4** | Conditional expansion (§11) | `context_mode` recorded; expansion rate measurable |
| **5** | Closed-vocabulary challenge pass (§10) | cannot raise caution from an uncertainty entry; materiality test enforced |

**Do not implement Phase 5 before Phase 1.** The challenge pass adds an LLM call and another
possible source of HOLD bias while the fundamental question - whether the large-context
architecture is producing the observed behaviour at all - is still open.

**Phase 0 is the recommendation to start with.** It is small, it is not a behaviour change, and
it turns §3's one-off measurement into a per-run series, which is what Phase 1 needs and what
the repo currently lacks for any prompt.

**Phase 0 telemetry - record more than character counts.** The run card becomes a
decision-context observability layer:

```
prompt_metrics:
    analyst_prompt_chars        analyst_prompt_tokens_est
    evidence_block_chars        evidence_block_tokens_est
    trader_prompt_chars         trader_prompt_tokens_est
    research_manager_prompt_chars   research_manager_prompt_tokens_est
    pm_prompt_chars             pm_prompt_tokens_est
    decision_packet_chars       decision_packet_tokens_est

llm_output:
    rating              direction           confidence

deterministic_postprocess:
    guardrail_rating    risk_gate           signal_action

execution:
    final_action

context:
    context_mode        packet_version      packet_truncated

evidence:
    bullish_count   bearish_count   neutral_count
    uncertainty_count               conflict_count
```

**The immediate implementation target is deliberately small - eight items, zero behavioural
change:**

```
1. identify the exact PM LLM-output boundary
2. persist prompt sizes
3. persist llm rating / direction / confidence
4. persist postprocess / gate / final action separately
5. persist context mode / version
6. persist evidence counts
7. persist snapshot identity / hash
8. make zero behavioural changes
```

Six months later this answers *"when the PM prompt exceeds 12k tokens, does HOLD
probability change?"* without reconstructing prompts from report trees - which is not possible
today, because prompts are never persisted.

### 13.1 Phase 0 as built, and the three things it found

**Where the code lives.** `tradingagents/agents/utils/prompt_metrics.py` (new) owns the
telemetry; `agent_states.AgentState` declares the two new channels; the seven LLM nodes
record their own stage; `reporting._run_card_decision_context` assembles the block into
`run_card.json`. The block is `decision_context`, and it is **additive** - a reader that
ignores it sees the card it saw before.

**Finding 1 - the boundary did not exist, and the capture point was already wrong.**
`pm_decision` is not the model's output. `portfolio_manager._result_hook` called
`_guardrail_hook(result)` **first**, and the guardrail rewrites `result.rating` and
`result.confidence` **in place**; only then did it capture `result.model_dump()`. So the
state key the whole pipeline reads as "the PM's decision" is the **post-guardrail** object,
and no record of the model's own emit existed anywhere in the run. This is precisely the
corruption §12.4 predicted would happen "six months from now" - it had already happened.
The fix is a capture before the guardrail; `pm_llm_output` is the new channel, and the
regression test asserts the two differ under a real downgrade.

**Finding 2 - the PM schema has no `direction` field.** `PortfolioDecision` emits `rating`
and `confidence` only. `llm_output.direction` is therefore a **deterministic projection** of
`llm_output.rating` onto the three-class axis, computed in the same expression that records
the rating so the two cannot diverge. It is not a second producer of the direction - no
other code derived one before this.

**Finding 3 - two of the five evidence counters cannot be honest yet, so they are null.**
`uncertainty_count` requires the Phase 2 uncertainty vocabulary; recording `0` would read as
"no uncertainty was present" when the truth is "nothing counted it". `conflict_count`
requires the same-metric pairs the report verifier resolves **post-hoc over the tree**, and
those are not in run state. Both are recorded as `null` with a `_reason` string. The three
directional counts that CAN be taken are taken over the structured independent stances (the
risk trio and the researcher pair), and the block carries `counted_sources` so a reader can
see the count is over five stances and not over the whole decision context.

**Finding 4 - the first draft recorded two phantom fields, and a live run caught it.**
`signal_action` was read from `state["security_signal"]` / `["portfolio_action"]` /
`["combined_action"]` / `["gated"]`, and `execution.final_action` from
`state["final_action"]`. **None of those five keys is ever written to state** - the split is
computed inside `write_research_decision` as a local and goes straight into
`research_decision.json`. So the first live card carried four nulls and a null under names
that read like measurements. This is the same failure mode the document is about, committed
by the telemetry itself: **a field that silently does nothing is worse than a named gap.**
Fixed by calling the one real producer (`signal_action_split`) with the same inputs the
execution contract's emitter uses, so the two cannot disagree; `execution.final_action` now
carries that split's `combined_action` and names its source. The executor's own binding gate
is deliberately **not** fabricated - it is not engine state. A test asserts the split is
populated rather than null, because the null version passed every other test.

**Finding 5 - `analyst_prompt_chars` did not measure the prompt.** The three tool-loop
analysts do not build one string: they render a static prefix (boilerplate + system message
+ evidence block + the bound tool catalog) and then append `MessagesPlaceholder("messages")`,
which grows with every tool round. The first draft measured only
`system_message + evidence_block` and filed it under a field named "prompt". The excluded
static parts alone are ~600 chars of boilerplate plus the tool catalog - **2,432 chars for
the market analyst's 117 tools, 1,174 for fundamentals' 54** - and the message history is
unbounded. Corrected to record the breakdown explicitly: `prefix_chars` (the static part, and
the quantity §3 measures, stable across rounds - which is what makes the W4 prefix cache
work), `messages_chars` (the rendered conversation at the final call, labelled a proxy), and
`chars` = the sum, which is what the model actually received. A test asserts `chars ==
prefix_chars + messages_chars`, so the two cannot silently diverge again.

**The pattern across findings 4, 5 and 6 is one thing, and it is worth naming: a field whose
name promises more than it measures.** All three were in new code written in a single session,
and all three passed every test that did not specifically ask what the field contained. That is
the same failure the document exists to catch - and the telemetry is not exempt from it.

**Finding 6 - the fix for finding 5 introduced the same error again.** The first repair
measured the message history as ``len(str(messages))``. A LangChain message's repr carries
Python scaffolding the provider never sees - ``content=``, ``additional_kwargs={}``,
``response_metadata={}``, ``id=`` - which measured **9.8% over** on a realistic tool-loop
history (6,319 chars repr vs 5,700 chars content). So the field went from undercounting the
prompt to overcounting it, which is the identical mislabelling wearing a different sign.
Corrected to sum the message **content** and the tool-call payloads directly, counting nothing
else, with a test that asserts the repr scaffolding is excluded. The lesson is that "the number
changed" is not evidence the number is now right; only asking what it contains is.

**A pre-existing latent defect found by the same audit, NOT introduced here.** Auditing every
state key the block reads against `AgentState` turned up three that are undeclared. One is
legitimate: `risk_gate` is injected post-invoke (`trading_graph.py:1113`,
`final_state["risk_gate"] = verdict`) and is present at report time - the live card carried
`PASS`. One is documented as never populated: `price_caliber` has no producer reaching state
(`dataflows/interface.py:910` sets it on a vendor result, not on the graph state), and
`research_decision.json` already says so; it is kept in the identity hash deliberately, so the
hash would change if a producer ever appears.

**The third is a real dead branch.** `state.get("kill_switch_state")` is read in
`prompt_metrics.py:274` **and in two pre-existing sites** (`reporting.py:380`, `reporting.py:665`),
but nothing ever writes that key - `risk_hierarchy.kill_switch_state:81` is a *function*, not a
state channel. So `kill_switch` is **always `False`** at every caller, and
`signal_action_split`'s kill-switch branch (`EXIT` / `NO_TRADE`) can never fire from any of
them. The kill switch is still evaluated inside `risk_hierarchy.evaluate_hierarchy` (precedence
KILL > PORTFOLIO > TRADE > LIQUIDITY > REGIME), so the gate is not absent - but the rendered
security/portfolio action never reflects it. **Not fixed here:** it changes execution semantics,
so it is an owner call, not a telemetry change.

**What it deliberately does not do.** No gate. No behaviour change: nothing reads a
telemetry value back into a prompt or a decision, so a run with the block removed produces
the same reports and the same rating. `context_mode` / `packet_version` /
`packet_truncated` are recorded as `null` because Phase 2 owns them, and a defaulted
`"compact"` would be a fabricated measurement.

### 13.2 Phase 1 as built: the decision factorial, and what it measured

**Where the code lives.** `scripts/context_ab.py`, extended - not a parallel harness
(§12.3). The existing `mcnemar_exact`, `ungrounded_figures`, the producers, the item
builders and the report are all reused; the addition is a third item type whose score is the
**decision category**, plus the §12.2/§12.3 apparatus around it. CLI:
`--experiment decision --trees reports/<TREE>`.

**The output order is the doc's order**: paired transitions first, then the distribution,
then grounding, then the execution layer, then the retention table.

**Finding 1 - `C2 - C1` cannot be a pure volume effect on this evidence, and the harness now
says so.** The doc requires C1 to be built by an *information-preserving* transformation so
the subtraction isolates volume. Two constructions were tried and measured:

| construction | chars retained | evidence retained | verdict |
|---|---:|---|---|
| `bounded` - the doc's literal *"first/last/representative rows"* | 70% (fixture) | bullish facts **50%**, figures **56%** | content-retention effect |
| `evidence` - drop only non-evidential lines | **95%** on a real tree | bearish facts **87%** | content-retention effect |

Neither reaches the 100% the volume reading requires. On a real tree (QCOM
`20260920_013202`) the evidence is **already evidence-dense**: 330 unique metrics, 2,597
figures, 256 source sections in 136,335 chars, and removing every line that carries no
figure or metric buys only **5%**. **The volume of this context IS its information.** A
smaller context means less evidence, which is a content-retention effect by definition - and
that is a finding about the architecture, not a failure of the instrument.

**Finding 2 - the verdict logic needed a second condition.** The first draft checked only
that evidence survived, and reported a **"context-volume effect" for a C1 that was 2
characters smaller than C2**. A contrast between two identical-size contexts measures
nothing, and naming it a volume effect is precisely the vacuous result §12.1 warns about. A
contrast must now BOTH retain the evidence AND actually shrink by at least 5% before it may
be called a volume effect; otherwise it is reported as `NO VOLUME ABLATION AVAILABLE`.

**Finding 3 - the same repr error, a third time.** `decision_items_from_tree` first built C2
with `"\n\n".join(str(r) for r in rendered)`. The rendered block is a list of
`{analyst, block}` **dicts**, so that joined Python reprs and produced an evidence block
whose metric and section counts were **0**. Fixed to read `entry["block"]`, after which the
same tree yields 330 metrics and 256 sections. This is the identical mistake §13.1's finding
6 records, in a different file, found the same way - by asking what the number contained.

**Finding 4 - the representation arm is a stand-in, and is labelled as one.** Phase 1 runs
*before* the Decision Packet exists (§13), so the P arms are built from the run's own
deterministic blocks (`_packet_stand_in`) - engine scores, the trade score, the risk
disagreement flag, the decision telemetry - in a fixed key/value shape. It has **no budget,
no uncertainty vocabulary and no conflict ledger**, so it is not the packet, and a
representation effect measured here must not be read as a measurement of the packet.

**What it pins by test** (`tests/test_decision_factorial.py`, 20 tests): the retention table
counts both sides; a same-size contrast is reported as no ablation; lost evidence is named
content-retention rather than volume; a directional→hold drift is counted separately from
hold→directional; entropy separates "more directional" from "more volatile"; an unparseable
rating is never defaulted to `Hold`; and a snapshot mismatch **invalidates** the pair rather
than merely noting it.

**Finding 5 - the identity check was over-strict and rejected 8 of 12 valid pairs.** The
first `_snapshot_matches` treated a **missing** hash as a mismatch. Eight of the twelve
snapshots predate the scorecard gate and therefore carry `engine_output_hash: None`; all four
arms had consumed the *same* evidence, but the check was demanding that the snapshot be
**rich** when section 12.3's invariant only requires it to be **the same**. Re-scoring the
saved run confirmed all eight are `match`. The check now returns three outcomes - `match`
(including `None == None`), `mismatch` (a real disagreement, which invalidates), and
`unverifiable` (no identity at all, kept but counted and reported). **An over-strict
invariant is not a safe one**: it discards valid pairs and calls the loss rigour.

### 13.3 The Phase 1 result, and it does not support H1a

12 snapshots across 9 tickers and 6 dates, 4 arms each (48 model calls), one model
(`openrouter/deepseek/deepseek-v4.1-flash`), every pair snapshot-verified.

| contrast | flip rate | directional→hold | hold→directional | McNemar p |
|---|---:|---:|---:|---:|
| **C1 → C2** (volume, within prose) | 0.333 | 1 | 3 | 0.625 |
| **P1 → P2** (volume, within packet) | **0.000** | 0 | 0 | 1.000 |
| **C1 → P1** (representation, at compact size) | 0.583 | **6** | 1 | 0.125 |

| metric | C1 prose-compact | C2 prose-large | P1 packet-compact | P2 packet-large |
|---|---:|---:|---:|---:|
| P(no-trade) | 0.417 | 0.250 | **0.833** | **0.833** |
| confidence | 0.652 | 0.667 | **0.248** | 0.283 |
| ungrounded figures | **2/12** | 7/12 | 9/12 | 9/12 |

**H1a is not supported, in either representation.** Moving from compact to large prose flips
33% of decisions with a **1:3** directional split that runs the *other* way - the large
context is marginally *less* conservative (`P(no-trade)` 0.417 → 0.250, p=0.625). Inside the
packet representation the large and compact arms produced **identical ratings in all twelve
snapshots** - a flip rate of exactly zero. **There is no measured volume effect to build for.**

**The representation axis carries what signal there is, and it points the wrong way.** The
prose→packet contrast at compact size is the largest in the experiment: 58% of decisions
change, 6:1 toward HOLD, `P(no-trade)` doubles to 0.833, and mean confidence **collapses from
0.652 to 0.248** - while ungrounded figures *rise* from 2/12 to 9/12. A structured rendering
did not make the model more decisive or better grounded here; it made it markedly more
conservative and less grounded. That is the opposite of the outcome the architecture assumed
a bounded packet would produce, and it is a reason to test a packet design before adopting
one, not a reason to assume it helps.

**n=12 is underpowered and nothing reaches p<0.05.** The representation contrast is the only
one approaching significance (p=0.125 on 6 discordant pairs one way). Reaching p<0.05 at this
effect size needs roughly 8-9 discordant pairs in the same direction, i.e. on the order of
20-25 paired snapshots. **These are directional signals, not established findings.**

**The retention caveat applies to the prose contrast.** C1 was 94% of C2's length and lost
bearish facts (92%), so `C2 − C1` is a **content-retention effect**, not a volume effect - and
it is a 6% ablation regardless, which is small even for that reading. The packet contrast
(C1 → P1) is a genuine **representation** effect: same size class, different structure.

**What this changes.** Section 12's premise - that the observed conservatism is plausibly a
large-context phenomenon - is not what the measurement shows. The next experiment should
target the **representation** axis, and it should first ask whether the packet's own shape
(engine scores, fixed key/value rows, no prose) is what suppresses confidence, rather than
assuming a bounded packet is an improvement.

### 13.4 Phase 2 as built, and the four rows it could not fill

**Where the code lives.** `tradingagents/strategies/decision_packet.py` (new) owns the
render; `tradingagents/graph/trading_graph.py` renders it **once** before the graph and stores
it under `DECISION_PACKET_KEY`; `decision_packet_or_context` is the gate, and the five
consumers named in §6 read the decision channel through it. `reporting` records
`packet_chars` / `packet_version` / `packet_truncated` / `context_mode` in the card's
`decision_context` block.

**The packet is a pure function of state** - no model call, no vendor call, no state mutation.
The one input not already in state is the close series, and the graph now fetches it **once**
and hands it to both the compiled context and the packet, so the packet's regime and plan rows
cannot come from a second read of the same series.

**FINDING 1 - §6's packet sketch is internally inconsistent with §16's architecture.** §6's
`RISK CONSTRAINTS` block specifies `gate = <PASS|WARN|REJECT>` and
`permission = <TRADE_ALLOWED | BLOCKED>`. Both are **post-decision** facts:

* `PASS|WARN|REJECT` is `risk_governor.govern`'s vocabulary, and `govern` runs in the graph's
  **post-decision** fold, writing `final_state["risk_gate"]`. No pre-graph producer emits it.
  The one gate readable before the decision is the **regime gate**, whose vocabulary is
  `tradable | high-vol | fast-downtrend | catalyst-window | unknown` - a different axis
  entirely, and the packet now prints that, labelled.
* `TRADE_ALLOWED` is produced by `signal_action.portfolio_action_from_gate`, which derives it
  **from the gate verdict** - so it is unavailable for the same reason. `BLOCKED` has no
  producer at all: the live vocabulary is `PORTFOLIO_ACTIONS` (seven values), and the
  two-value form exists only in this document.

§16's own diagram puts the deterministic gates **downstream of the decision**
(`RAW DECISION → CLOSED CHALLENGE → DETERMINISTIC GATES → ACTION`), so a pre-decision packet
*cannot* carry them. The packet therefore prints the pre-decision constraints - the limits
registry, the measured book state, the liquidity verdict, the regime gate - and names
`permission` as `unavailable_pre_decision` with the reason, in the same spirit as
`catalyst_window=unavailable_pre_graph` (D-11). **A row whose producer has not run is a named
gap, never a default.**

**FINDING 2 - the directional distribution has NO valid producer.** §6 justifies
`bullish=<b> bearish=<d> neutral=<n>` with *"the engines already carry a sign per component"*.
They do not, verified at the definition sites: every engine band table is non-directional
(`REGIME_BANDS` = benign/constructive/mixed/stressed/hostile; `RISK_BANDS` = low
risk/contained/moderate/elevated/high/severe; `NEWS_BANDS` =
high-information/informative/mixed/quiet/stale/no-signal; `QUALITY_BANDS` =
elite/above-average/peer median/below-average/poor/distressed), and `score_engine.align` maps
each component to a 0-100 value **in the favourable direction**, erasing the observation's
sign. No component dict carries a `sign` key; the only signed field is `raw`, whose arithmetic
sign is meaningless for the band-mapped and boolean components (RSI, MFI, stochastic, Williams
%R).

The one counter that exists, `prompt_metrics.stance_direction_counts`, counts the
**independent stances** - and §4.4 with acceptance criterion 22 makes those *"diagnostics, not
evidence … they must not become a second evidence stream that the PM averages"*. Feeding them
into the packet's `EVIDENCE` block would silently turn `independent_agreement` into the
consensus the model defers to, which is the failure §4.4 exists to prevent. So the row is a
**named gap**. A fabricated distribution would be worse than none: it would present a
diagnostics stream as evidence, and a reader could not tell.

**FINDING 3 - §8's three counters reduce to one.** `UNCERTAINTY` is built and honest: the
count and the named gaps come from the one place each is declared - `quant_scorecard`'s own
`absent` map for an engine that was enabled and could not measure, and the engine's own
`absent` / `absent_reasons` for a component it could not measure. **An engine whose gate is
off is not a gap**: it is intentionally not running, which is the `STATE_DISABLED` / `STATE_NA`
distinction the scorecard already draws. The `EVIDENCE` side of the pair
(`bullish`/`bearish`/`neutral`) is the row Finding 2 rules out, so the pair collapses to the
uncertainty half. The §8 invariant is therefore enforced on what exists: *adding an enabled
engine that cannot measure grows the `UNCERTAINTY` count and produces no directional count*.

`reporting._run_card_evidence_counts` now reads the same `uncertainty_read`, so the card and
the packet cannot disagree - and the field Phase 0 recorded as `null` is a real count, while
staying `null` when there is **no snapshot** (nothing examined the engines).

**FINDING 4 - the recorded scorecard is a projection, so a card reader cannot recompute the
composite.** `reporting._run_card_quant_scorecard` writes each engine as
`enabled`/`state`/`score`/`coverage`/`band`/`status` and **drops `result`**, so the card's
`trade` entry carries no `floor` and no `basis`. The live snapshot in state does carry them,
so the packet's `composite` row is complete in production - but a reader working from
`run_card.json` alone cannot reproduce the composite's floor or its shipped `basis` string.
**Not fixed here:** widening the card is a WP-12 decision, and it is not required by any
Phase 2 criterion.

**Two defects in the packet's own first draft, both caught by running it.** (1) The
wiring-defect string printed `DECISION PACKET vv1` - a doubled version prefix. (2) The
truncation pass picked victims by a text heuristic (`not line.isupper()`), which could have
dropped the purpose line or a category note; it is now **structural** - only rows can be
dropped, never a heading, a note or the header, so the labelling survives pressure. A third,
found by a test: `engine_row_max_chars` was declared in the budget and **never enforced** - a
declared bound that does nothing is the same defect class as a parameter that silently does
nothing. It is now enforced by dropping **whole cells**, never by cutting a cell in half.

**What the packet deliberately does not do.** No `DECISION` line (§6 rule 4, asserted). The
`CONFLICT` row is a named gap, because §9's ledger is Phase 3 and the same-metric pairs are
resolved post-hoc over the report tree. The consensus line sits under `SYNTHESIS` and is
labelled a **diagnostic over independent reads**, not evidence - it is the line the PM already
received, and §11 classifies `weighted_consensus` as a diagnostic. `reporting`'s section IVa
still renders `computed_decision_context`, because the researchers keep the unbounded channel
(§1.1: research can be large) and IVa is the report's research-side advisory block; **the
packet's own text is not rendered into the report**, which is a gap worth closing when the
packet is dark-launched for real.

### 13.5 The §9 dependency: the verifier's flags, triaged and three defects fixed

§9 says the conflict ledger "is only as good as the verifier's classification". Checking
whether the open pairs were classified answered the question in one step: **they were not
classified at all.** A `verify_flags.json` conflict row carries exactly three keys - `claim`
(free prose), `status`, `reason` - with no `classification`, no `metric` key and no source
sections. §9's three-value vocabulary (`unresolved` / `basis_difference` / `defect`) appears
nowhere in the codebase.

What the verifier *does* have is classification **logic used only to suppress**. Three rules
already decide "this is not a conflict" - `_period_tag` (a disclosed period is a basis),
`_disclosed_pair` (the report named both values and their producers), and `_UNIT_SCOPED_METRICS`
(two unit classes are two bases). None of them **labels** the row it spares. So the ledger's
`classification` field is not a re-derivation; it is the same judgement, emitted instead of
discarded - which is a smaller build than §9 implies, and the reason this triage mattered.

**THE TRIAGE (§9's table) FOUND NO TWO-PRODUCER DEFECT.** Three of the five pairs were false
positives in the verifier's own value extraction; two were basis differences the report itself
disclosed. Running the verifier's extractors over the trees proved the mechanism for each.

**Three detector defects, all confirmed and fixed on sight.**

**Finding 1 - `_table_cell_pair_value` computed the ordinal from `prefix.count("/")`.** A `/`
inside a **label** (`P/E`) is not a separator, and the count used the match's **start**. Three
distinct false positives followed:

* `| P/E / EV/EBIT / EV/EBITDA | 7.68 / 5.50 / 4.40 |` - the `P/E` label and the ` / `
  separator both contributed a `/`, giving ordinal 2 and reading the **EV/EBITDA** value as
  EV/EBIT (LULU 2026-09-15).
* `| Scenario DCF bear/base/bull | 132.5 / 173.58 / 249.05 |` - the label regex legitimately
  matches the whole `bear/base/bull` phrase, so the match started at leg 0 and **both** `base`
  and `bull` were bound to the **bear** value (LULU: 173.58 beside 132.5, and 249.05 beside
  132.5).
* `| Trap risk / Altman Z | LOW / 2.90 (grey); Ohlson -7.2461 healthy |` - the value leg named
  a **second metric** and donated its number (JCI 2026-09-17: Altman Z 2.90 beside the Ohlson
  score 7.2461).

The fix: cut **both** cells the same way (`_table_legs`, a spaced `/` as the separator with a
bare `/` fallback), take the leg the match's **last character** occupies - these phrases read
`<context> <label>`, so the metric is the tail - and read **that leg's first figure**, so a leg
that goes on to name another metric cannot donate it.

**Finding 2 - the period tag was taken per LINE, not per figure.** `_period_tag` returns one
tag for the whole line, so a line stating two labelled bases gave both figures the same tag and
the disjointness test saw one shared period. `_period_tag_near` binds each figure to the token
**nearest it**. Its first version was wrong in a way worth recording: it iterated
`_PERIOD_TAG_RES` in precedence order and returned the first *kind* that matched anywhere, so a
**distant** `FY2025` beat the `2026/Q3` sitting immediately beside the figure. **Distance must
decide first; precedence is only the tie-break.** A `\d{4}/Q[1-4]` spelling was also missing
from the table, so the vendor's own `2026/Q3` was not a period at all.

**Finding 3 - the disclosed-basis test was silently inert on the reader path.** The
`_METRIC_VALUE_READERS` branch builds its entries as `(raw, value, None)` - no line - so
`if line:` was false for every metric that has a reader, and the suppression below it could
never run. The fallback extractor supplied lines; the readers did not. `_line_carrying`
recovers the line from the report text, which is cheaper and safer than widening the readers'
contract.

**What the fixes did, and what they did not.** Conflict rows over the analyst reports fell from
**70 over 26 trees to 30 over 24**. Five regression tests were added, each proven **failing-first
by mutation**: reverting the three behaviours to their original bodies fails all five, and the
restored file is byte-identical by sha256. The verifier's own suite (223 tests) passes
unchanged.

**What remains, named.** The 30 surviving flags still contain false positives - `AMZN
2026-09-17 'current ratio' 249.26; 1.0508` (a price read as a ratio), `IBM 'scenario dcf bear'
113.47; 0.3908`, `NVDA 'rsi' 45.21; 41414141...` (the masked-digit corruption), `NVDA 'earnings
power value' 722,598,607,888.63; 14`. The disclosed-basis suppression also still fails on JCI
`ev/ebit` and LULU `debt/equity`, because a value that **recurs** on a second line collects a
second tag and the "every cluster carries its own period" test then fails. **Fixing that needs
a value-to-basis binding these line-scoped regexes cannot express**, and it is not attempted
here. The honest statement to §9 is therefore: **the detector is better, and it is not yet good
enough to feed a ledger** - so Phase 3 stays blocked on it, now for a measured reason.

---

## 14. Acceptance criteria

1. **Byte-identical when off.** Every phase behind a gate defaulting `False`; gate off ⇒
   byte-identical output. (The repo's established gate contract.)
2. **A gate is a membership switch, not an inert body** — same rule.
3. **New gates registered in five places**: `default_config.py` `DEFAULT_CONFIG`, an
   `_ENV_OVERRIDES` row, a `docs/gate_registry.md` table row (now §7, *context gates*),
   the `REGISTRY` dict in `tests/test_gate_env_toggles.py`, and `.env.example`.
4. **The packet is a pure function** — no vendor call, no model call, no state mutation.
5. **No number without its coverage or a named gap.**
6. **An uncertainty is never counted as bearish** — asserted by test, not by prompt text.
7. **The challenge pass cannot raise caution from an uncertainty entry.**
8. **Every new public function in `tradingagents/strategies/` or `tradingagents/dataflows/`
   has a reference outside its own module** (`tests/test_calc_agent_wiring.py`).
9. **No new derived quantity with two independent producers** (master rule 15).
10. **Failing-first proofs mutate behaviour, never stash the source.**
11. **The packet carries no `DECISION` line**, and `ENGINE EVIDENCE` /
    `DIRECTIONAL DISTRIBUTION` / `CONSENSUS` / `COMPOSITE` are each labelled research
    evidence, not a recommendation (§6).
12. **`UNCERTAINTY` ships in Packet v1** - the first packet experiment must be able to test
    H1b (§8).
13. **A contradiction may invalidate only under the materiality test** - relied upon, AND
    unresolved, AND materially decisive; directional disagreement never qualifies (§10).
14. **The factorial runs before the challenge pass** (§13).
15. **The retention table is reported for C1 vs C2** (unique metrics, unique figures,
    bullish/bearish/uncertainty facts, source sections). If retention is materially below
    100%, the contrast is **not** reported as a volume effect (§12.1).
16. **The paired decision transition matrix is printed**, not only CCI (§12.2).
17. **Raw decision and gated action are recorded and reported separately** (§12.4) - decision
    conservatism is measured before deterministic risk gating. **MET (Phase 0).**
18. **The packet keeps `constraints != evidence != synthesis != decision` visually distinct**;
    `permission` lives under `RISK CONSTRAINTS` (§6).
19. **The challenge pass may not create a new caution rationale** - downgrade only on the three
    closed grounds (§10).
20. **The telemetry boundary is named, not implied** - `llm_output` (the PM's structured emit,
    before ANY transformation) is distinct from `deterministic_postprocess` and `execution`
    (§12.4).
21. **Every paired observation records snapshot identity** (`snapshot_id`, `data_snapshot_hash`,
    `engine_output_hash`, `model_parameters_hash`), and a mismatch **invalidates the pair**
    (§12.3).
22. **Independent reads are diagnostics** - they may measure disagreement and may trigger
    conditional expansion, but never enter the packet as evidence (§4.4).
23. **A contrast with materially reduced retention is reported as a content-retention effect**,
    never as a pure volume effect (§12.1).

**Phase 0 criteria, met by the build recorded in §13.1.**

24. **The PM model's structured emit is captured before any deterministic postprocess.** A
    regression test asserts `llm_output.rating` and `deterministic_postprocess.guardrail_rating`
    **differ** under a real guardrail downgrade - the mutation that breaks it is a one-line
    reorder of the capture.
25. **Prompt size is recorded per stage**, merged across nodes by an additive reducer (the
    default last-write-wins would keep only the final stage).
26. **A counter that cannot be honestly taken is `null` with a reason**, never `0` - `0` reads
    as "none present" when the truth is "nothing counted it".
27. **The telemetry block changes no behaviour**: no gate, and nothing reads a value back into
    a prompt or a decision.

**Phase 2 criteria, met by the build recorded in §13.4.**

28. **The packet fits its budget, and truncation is structural and visible.** Only rows can be
    dropped - never a heading, a category note or the header - and the count of dropped rows
    appears in the text. `engine_row_max_chars` is enforced by dropping **whole cells**, so a
    surviving cell is always `name=value`.
29. **A row whose producer has not run is a named gap.** `unavailable_pre_<stage>` with the
    reason, never a plausible default: a default would read as a measurement nobody made, the
    failure `catalyst_window=False` already committed (D-11).
30. **The packet is rendered once and read by every consumer.** One producer of the string, one
    `packet_chars` measurement; a consumer that re-rendered could disagree with the block the
    model actually read.
31. **The gate is read in exactly one place** (`decision_packet_or_context`), and a gate-on run
    with no packet rendered reports a wiring defect rather than silently falling back to the
    compiled context - a silent fallback would hide the defect behind plausible output.
32. **The uncertainty counter draws the `DISABLED` / `NA` distinction.** An engine that is
    enabled and could not measure is a named gap; an engine whose gate is off is not a gap at
    all. `reporting._run_card_evidence_counts` reads the same counter, so the card and the
    packet cannot disagree, and the field stays `null` when there is no snapshot.
33. **The packet's text is not rendered into the report.** Section IVa still renders
    `computed_decision_context`, because the researchers keep the unbounded channel (§1.1) and
    IVa is the report's research-side block. **Named as an open gap**, not silently accepted.

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
- **Not** a claim that the proposed architecture is correct. §17 states only that the
  *primitives* exist.
- **Not** an implementation of the challenge pass ahead of the experiment. Adding a second
  LLM call and a fresh route to HOLD while H1 is untested would confound the very
  measurement the design depends on (§13).

**Risks.**

| Risk | Mitigation |
|---|---|
| **H1 is false** — the conservatism comes from elsewhere (regime miscalibration per FINSABER) | Phase 1 before Phase 2; the packet is independently justified by §2.1 |
| **Compression loses a decisive fact** — semantic drift, constraint loss | the packet is a *pure function of state*, so nothing is summarized away by a model; and the full evidence remains retrievable (§11) |
| **The packet becomes a second decision-maker** — a high composite starts to read as an instruction | `RESEARCH_ONLY` labelling; `TradeScore` printed last and labelled downstream (already the owner's §13.2 decision) |
| **The budget silently truncates a decisive row** | truncation is visible and counted, never silent |
| **The challenge pass becomes a caution generator** | closed vocabulary; evidence must be a packet row; downgrade-only |
| **Conditional expansion becomes a second route to HOLD** | §11's caution; the challenge pass stays closed-vocabulary |
| **`AGREEMENT` becomes an implicit instruction** - the model computes `7/8 -> BUY` instead of judging | the distribution replaces the ratio, `COMPOSITE`/`CONSENSUS` print last and labelled, and no `DECISION` line exists (§6) |
| **A directional disagreement is mistaken for a contradiction** and invalidates | the materiality test: contradiction means one metric with two incompatible values, never two engines disagreeing (§10) |
| **The four-arm design answers the architecture question but not H1a** | the 2x2 factorial separates volume from representation (§12.1) |
| **A smaller context buys decisiveness with fabrication** | every arm is scored on grounding; §3.4 measured this cost at -29% grounded citations |

---

## 16. The frozen architecture contract

**The Decision Packet is an information boundary, not a decision boundary.** That distinction
is what makes the contracts clean: the packet controls *what the decision model sees*, not
*what it decides*, and not *what executes*.

```
                    EVIDENCE BUS
              unlimited / research-oriented
                         |
              deterministic synthesis
                         |
              verification / conflicts
                         |
                 DECISION PACKET
                    hard budget
              +----------+----------+
              |                     |
       independent reads       decision model
       diagnostic only              |
              |                     |
              +----------+----------+
                         |
                    RAW DECISION
                  (LLM output only)
                         |
                 CLOSED CHALLENGE
                  closed vocabulary
                         |
                DETERMINISTIC GATES
                         |
                      ACTION
```

**The layer contracts.** Each layer has a permission and a prohibition; the prohibitions are
what keep the boundaries real.

| Layer | May do | May not do |
|---|---|---|
| Evidence Bus | accumulate everything | decide |
| Synthesis | calculate / compress | invent evidence |
| Packet | constrain information | recommend |
| Independent reads | measure disagreement | become consensus |
| PM | adjudicate evidence | override hard constraints |
| Challenge | invalidate on closed grounds | invent caution |
| Gates | constrain action | create research evidence |
| Execution | act | reinterpret research |

The design principle it encodes:

> **Research can be large. Decision context cannot be large by accident.** (§1.1)

## 17. Summary


Per owner feedback the conclusion is stated as what has actually been established:

> **The repository already contains most of the primitives required for a bounded
> research-to-decision architecture. The remaining work is primarily deterministic assembly,
> explicit uncertainty/conflict representation, and experimental validation of whether context
> size materially affects decision behaviour.**

That is more defensible than "the proposal is directionally right and mostly already built",
because the experiment has not run. What §4 establishes is that the *primitives* exist - the
gates, the deterministic context, the synthesis, the independent reads, the ownership map -
not that the proposed architecture is correct.

**The strongest part of this design is not the packet.** It is the decision to experimentally
separate **context-volume effects** from **representation effects** (§12.1) before changing the
production architecture.

What the repository does **not** have, in order of value:

1. **Any measurement of prompt size.** §3 is a one-off; nothing records it per run.
2. **Any test of the hypothesis on the axis that matters.** `scripts/context_ab.py` already
   A/Bs context size against accuracy and grounding with an exact McNemar test, but nothing
   measures the **decision outcome** (Buy/Hold/Sell) against context size.
3. **A bounded decision packet** - the compact channel exists (`computed_decision_context`) but
   is neither bounded nor measured.
4. **The uncertainty/evidence distinction** (§8) - the one genuinely new concept, now part of
   Packet v1 rather than a later phase.
5. **A challenge pass that can only invalidate** (§10) - recorded invalidations exist; an
   invalidating *pass* does not.

With the v3 corrections the design is no longer a proposal to "shrink prompts". It is a
**controlled decision-context architecture with an experimental method** for determining
whether context volume, representation, uncertainty framing, or downstream gating is actually
responsible for the observed behaviour.

**Phase 0 is built** (§13.1): the telemetry is in `run_card.json`, it changes no behaviour, and
it converts the motivating observation from an anecdote into a time series. Its build also
found that the boundary it was meant to name did not exist - `pm_decision` had been the
post-guardrail object all along.

The single most useful next action is therefore **Phase 1: the factorial experiment** (§12),
run *before* the Decision Packet is introduced. Its build will extend `scripts/context_ab.py`
with a third item type scored on the decision category, print the paired transition matrix
with counts first, and report the retention table for C1 vs C2 so each contrast is named a
volume, content-retention, or representation effect.

---

## 18. References

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
