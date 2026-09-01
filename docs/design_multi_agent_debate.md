# Architecture: Multi-Agent Debate for Financial Decisions

**Status: research + design only — no code changed.** Revised against
`Strategies/Multi_Agents_Debate.md` (the source document, whose content
repeats itself once — both copies agree) plus 2025-2026 literature. Maps the
ask (heterogeneous models, strict tool/data grounding, independent arbiter,
structured adversarial scoring) onto this fork's existing debate wiring
(heterogeneous models, strict tool/data grounding, independent arbiter,
structured adversarial scoring) onto this fork's existing debate wiring
(`graph/setup.py` bull/bear/research-manager chain, `independent_vote.py`,
`_compiled_decision_context`, the analyst tool loops, the deterministic
overlays). Companion to `docs/design_risk_calculations_agent_wiring.md`
(where "advisory-first" wiring is already done for the risk layer).

**Revision v2 — folded in from `Strategies/Multi_Agents_Debate.md`:**
- **(R1) L1 fast-abort + single-role regeneration** — any debate turn that
  fails a deterministic hard check (hallucinated multiple vs ground truth,
  gate violation) is penalised/invalidated before any LLM jury runs; a
  critical round-1 failure aborts or regenerates that one role instead of
  paying for the full jury pipeline.
- **(R2) Divergence caps + artificial-consensus alert** — convergence is
  decoupled from confidence: if both sides converge on identical price
  targets within 1 round without new external data, flag an *artificial
  consensus* and reweight the output toward the baseline risk
  distribution. Agreement != score.
- **(R3) Dual-mode schema adapter + config-time capability matrix** —
  structured-output API primary; markdown-fence parse + Pydantic repair
  loop fallback; a startup capability check
  (`Role = f(context window, structured-output support, tool latency)`)
  routes jury/debater roles only to models that can meet the role's
  strictness needs.
- **(R4) Matched-compute A/B harness** — even if a self-consistency
  ensemble (N=5 + median vote) matches debate directionally, debate wins
  on auditability (counter-thesis trail + risk-boundary discovery); score
  the harness with **Brier score** (calibration) and **maximum
  unforecasted drawdown**, not raw $P(\text{Up}) > 0.5$ accuracy.
- **(R5) State-machine orchestration + canonical wire schemas** — the
  source doc's FSM (PARSE_TURN -> RUN_L1 -> CHECK_EARLY -> ANONYMIZE_ROT ->
  RUN_L2 -> AGGREGATE_L2 -> FINAL_SYNTH, with severity-triage
  short-circuits — see v3 below)
  and its three JSON contracts (`debater_turn`, `l1_eval_result`,
  `l2_judge_rubric`) are the orchestrator's transition table and the
  debaters'/judges' pydantic payloads (§4.9): **L2 never runs unless L1
  fully passes**, schema faults and L1 hard-breaches fall back to the
  baseline risk view (v3), and the loop continues only when `Round < Max`
  and `DeltaScore >= eps`.
**Revision v3 — folded in from the source doc's hardening appendices
(`Strategies/Multi_Agents_Debate.md`, 2026-08-31 update):** the source doc
answered the §7 risk items with executable mechanics, now folded in here:

- **(R1') L1 severity triage instead of a binary gate** —
  `HARD_BREACH` (zero-tolerance: out-of-bounds leverage/constraint,
  math contradiction vs a verified feed, unparseable schema) short-circuits
  to the pre-computed baseline risk view; `RETRYABLE` (metric-key mismatch,
  scoped schema field fault) triggers exactly **one** single-field repair
  pass (`debate_regen_max`), then baseline on a second failure;
  `SOFT_WARNING` (timestamp drift, ungrounded qualitative claim, secondary
  rounding) applies `penalty_score` and proceeds to L2 **annotated**.
- **(R2') Entrenchment index + divergence-floor rule** —
  `I_entrench = CosineSim(v_R, v_{R−1}) · (1 − |ΔAlloc|/Alloc_{R−1})` gates
  an entrenchment penalty when a persona repeats itself past τ_entrench
  without addressing validated counter-points; `|Score_Bull − Score_Bear| <
  δ_divergence_min` with no new L1-verified evidence raises the
  **Artificial-Consensus Flag** and reweights
  `W_final = (1−α)·W_debate + α·W_baseline` toward the empirical base rate,
  α scaling dynamically with the consensus/entrenchment risk.
- **(R5') Fourth canonical wire schema** — `l1_execution_context.json` →
  `L1ExecutionContext` (severity_tier, l1_action, regen bookkeeping,
  entrenchment_metrics, baseline_fallback_payload) makes the recovery path
  explicit and replayable, and the FSM gains `EMIT_BASELINE_FALLBACK`,
  `REGEN_PROMPT_DISPATCH`, `CHECK_ENTRENCHMENT`, `REWEIGHT_TO_BASELINE`
  rows (§4.7).

---

## 0. TL;DR

The current debate is a **persuasion loop over one model family**: Bull and
Bear share the same `quick_thinking_llm`, produce free prose, cite only what
they happen to call, are judged by the Research Manager (same debate pool,
`NO_EXTERNAL_TOOLS`, holistic verdict), and the loop is a fixed 1-round
exchange (after the deep-run fix). Literature (Du et al. 2023; 2025 controlled
studies; adversarial-peer studies; LLM-as-judge bias work; Tool-MAD`ArgumentRecord` /
`DebaterTurnPayload`PROClaim / VeriFin) says three things decide whether debate helps:

1. **Diversity of error patterns drives gains** — model-family heterogeneity
   > parallelism; a homogeneous/adversarial same-family peer can *entrench*
   wrong consensus (+30% wrong-answer consensus; harmful-revision 89%→35%
   with an honest heterogeneous peer).
2. **Grounding beats rhetoric** — claims must be traceable to tool output
   (claim-level verification, citations, "abstain" when unsupported); up to
   10-40% accuracy loss when adversarial agents are allowed to persuade
   without evidence.
3. **Judging is the weak link** — judges are biased (self-preference,
   position, verbosity); score **dimensions separately**, use a judge that is
   neither debater, anonymize/rotate, and run **deterministic checks first**;
   stop when marginal information gain plateaus, never by "we all agree".

Design below keeps this repo's contract (compute-as-tools, no-fabrication,
advisory-first, deterministic overlays as the hard gate) and upgrades the
debate into an **evidence-producing hypothesis search with a two-layer
judiciary, a fast-abort short-circuit, and a provider-capability gate**, all
opt-in. The operative goal (source doc): **subordinate subjective LLM
evaluation to deterministic L1 gates and isolate orchestration state** so
the debate cannot become a "rhetorical echo chamber".

---

## 1. Current state (audited, working tree 2026-08-31)

```
analysts (market/social/news/fundamentals, tool loops, ~90 tools)
  -> Independent Researcher Stances (opt-in, pre-debate, no cross-talk)
  -> Bull Researcher (quick_llm, prose)
  -> Bear Researcher (quick_llm, prose)
  -> Research Manager (deep_llm, structured ResearchPlan, NO_EXTERNAL_TOOLS)
  -> Trader -> Independent Risk Stances -> risk debate (3 roles, in-node
     tool loops) -> Portfolio Manager (deep_llm, structured)
  -> deterministic overlays (regime -> catalyst -> contract -> governor)
```

Debate facts:

| Aspect | Today | Gap vs. ask |
| --- | --- | --- |
| Model assignment | Bull = Bear = RM-related single family (`quick_think_llm`; RM `deep_think_llm`) | no heterogeneity by design |
| Grounding | Analysts run tool loops; debaters receive report TEXT only, no tools, **no obligation to cite** | claims not anchored per-turn; no abstain discipline |
| Judge | RM is the arbiter, same debate pool, holistic `ResearchPlan`, no scores | no independence, no dimensioned rubric, no documented verdict |
| Scoring | none; `consensus.py` computes agreement from the RISK team only | no empirical-validity scoring, no marginal-info-gain |
| Termination | fixed `max_debate_rounds` (now 1) | no adaptive early stop; no plateau detection |
| Pre-debate sanity | `independent_vote` samples stances before debate (risk + research) | good seed — can be extended into the judge's base read |

Already-aligned assets to reuse: `_compiled_decision_context` (a computed
factsheet injected into the decision agents), the run-level OHLCV cache,
`strategies/*` calculators wrapped as `@tool`s, the deterministic overlays,
`independent_vote` sampling, the pydantic schema pattern, and
`risk_tool_loop`'s in-node capped tool loop.

---

## 2. Design principles

1. **Debate is hypothesis search, not persuasion.** Each turn must add
   verifiable information or it should not run.
2. **Evidence before opinion.** Every quantitative claim cites a tool call`ArgumentRecord` /
`DebaterTurnPayload`   state value; qualitative claims are tagged `qualitative` (weighted ~0) or
   abstained.
3. **Deterministic judiciary first.** Anything the repo can compute (governor
   verdict, CVaR, liquidity, consensus agreement, contract size) is a hard
   constraint the debate cannot override; the LLM arbiter only scores the
   residual qualitative margin.
4. **Heterogeneity by design.** Roles map to different model families and
   different tool surfaces; correlated-error consensus is treated as a risk,
   not a signal.
5. **Judge independence from debaters.** Different family, anonymized,
   dimensioned, deterministic-checks-first; ensemble for the final call.
6. **Cost is a first-class citizen.** Token budget, per-round cap, and an
   early-stop rule are part of the contract (deep runs already hit
   30-40min+).

---

## 3. Target topology

```
                       (config: bull_model, bear_model, judge_model)
                                        |
   analysts (tool loops, computed factsheet    -> clcaim ledger)
        |                                          ^
        v                                          |
   Independent stances (pre-debate, opt-in)         | (base read
        |                                          |  for judge)
        v                                          |
   --------  RESEARCH DEBATE (subgraph) -----------|
   |                                            |
   |  Round loop (max_rounds, cap, early-stop):   |
   |   Bull(claim+tools) -> Bear(critique+tools)  |
   |   -> Adversarial score (dims each other;    |
   |      novelty reducer) -> Claim ledger        |
   |                                            |
   |   terminate: judge_score_plateau |           |
   |              consensus>=thresh |            |
   |              max_rounds hit     |            |
   |--------------------------------------------|
        |
        v
   ADJUDICATOR (two layers):
     L1 deterministic: governor/contract/consensus/claim-verifier (abstain
                     when unsupported) -> severity tier
                      |-- [HARD_BREACH] -> baseline fallback (no jury)
                      |-- [RETRYABLE]   -> one scoped regen, then baseline
                      |-- [SOFT_WARNING]-> penalty_score, proceed annotated
                      |-- [ARTIFICIAL CONSENSUS] -> reweight toward baseline
     L2 LLM arbiter (3rd family, anonymized, dimensioned rubric:
                     correctness, evidence, calc, novelty, constraint)
        -> DebateVerdict {rating, confidence_bnd, evidence_ledger, scores}
   (capability gate: role/model matrix from config-time health check)
        |
        v
   Trader -> risk debate (existing) -> Portfolio Manager
        -> deterministic overlays (unchanged hard gate)
```

Key state keys added to `AgentState` (channels): `debate_state`
(round_records, score_series, claim_ledger, verdict), `judge_scores`
(per-dimension scores, abstains), `debate_terminated` (reason).

---

## 4. Design pieces (module-mapped)

### 4.1 Heterogeneous model / role assignment

- New config (all opt-in, empty default = current single-LLM behavior):
  `debate_bull_model` / `debate_bear_model` / `debate_judge_model`
  (provider family + model id, e.g. `"anthropic:claude-sonnet-4-5"``ArgumentRecord` /
`DebaterTurnPayload`  `"openrouter:gpt-4o"`). `DebateJudgeModel` additionally requires a provider
  **different from both debaters** when set (validation warning, not hard
  error).
- Model registration rides the existing `llm_clients/factory` registry —
  no new provider plumbing; fall back to `quick_think_llm``ArgumentRecord` /
`DebaterTurnPayload`  `deep_think_llm` when unset.
- Role separation extends beyond the model: each role binds a DIFFERENT tool
  surface. Bull: growth/insider/RS/technical tools. Bear: tail/liquidity/
  credit/short tools. (Reuses the 23-tool risk set pattern from
  `risk_tool_loop`.) A shared "neutral evidence" set (verified snapshot,
  computed context) is injected to both.
- **Config-time capability matrix (R3)** — a startup health check
  (`strategies/debate_capability.py`, pure): for each candidate role/model,
  measure `context_window`, `structured_output_support`, `tool_latency`
  against the role's requirement floor; refuse to route jury aggregation or
  complex tool-use roles to models lacking strict JSON guarantees (fail
  closed with a clear config error, not a silent degradation). Role matrix
  = `f(context window, structured-output support, tool latency)`.
- **Litmus test: correlated-error consensus** — a `consensus_coupling`
  detector flags when both debaters cite the SAME single source for a key
  claim (see 4.5), emitting `low_diversity_warning`.

### 4.2 Grounding contract (strict tool & data grounding)

Mirrors the no-fabrication rule, made per-turn and per-claim:

- **Claim ledger** (`strategies/debate_claim.py`, pure): each claim is
  `{role, round, claim_id, kind "quantitative"|"qualitative"|"abstain",
  value|None, tool_id|state_key|None, source_label, confidence 0..1}`.
  Quantitative claims REQUIRE `(measurable value, source)`;
  unsupported -> the claim is downgraded to `abstain` by the verifier.
- **L1 hard check layer (deterministic, no LLM)**: a claim whose value
  contradicts a computed state value (e.g. trailing P/E 12x vs ground truth
  38x, CVaR, stop, liquidity verdict) is flagged `violated` (reuse
  `reporting.audit_decision_numbers`-style comparison). Sources must exist
  in the run's tool/state ledger — "deceptive grounding" (real source,
  wrong entity) is caught by requiring the source to be a tool call that
  ACTUALLY happened for THIS ticker this run (`_evidence_of(tool_id)` absent
  -> `violated`).
- **L1 fast-abort / single-role regeneration (R1)** — a turn that fails a
  hard bound (gate violation, math contradiction) is **penalised or
  invalidated immediately**; the L2 jury is never asked to evaluate a
  mathematically invalid claim. A *critical* round-1 failure
  (`severity=hard` on a constraint like max drawdown / VaR) either aborts
  the debate (fall back to baseline risk distribution) or triggers ONE
  regeneration of the offending role — never a full 3-model jury run. Cost
  is preserved for the rounds that can actually contribute.
- **Prompt contract** (bull/bear/RM replacements): "Every number you state
  MUST be prefixed by its tool/state citation from the injected ledger;
  if you cannot ground a number, state it as `abstain`." The generated
  claims alone count toward scoring (4.3) — prose that makes ungrounded
  claims is penalized, not rewarded.
- **Abstention**: verifiable + relevant + stated

### 4.3 Structured adversarial scoring

Per round, each debater produces a structured `ArgumentRecord`
(schema) instead of free prose:

- **self**: claims[], weakpoints admitted
- **oppoent critique**: per claim `{valid, evidenced, calc_ok, new_info
  0..1}`, plus what the oppoent GOT WRONG (empirical, not rhetorical)
- Scoring functions(`strategies/debate_score.py`, pure, unit-testable):
  - `evidence_quality(q) = avg(opponent.valid & evidenced & calc_ok)`
  - `novelty_gain(q) = mean(new_info across claims not seen in prior rounds)`
  - `round_infomation_gain(q, q-1) = novelty_gain(q) - novelty_gain(q-1)`
  - `debate_score(q) = 0.6*evidence + 0.25*novelty + 0.15*constraint_ok`
  (weights config). Consensus is NOT a score — agreement only feeds
  termination (4.4).
- Rising `invalid` share across rounds for one side triggers an early-flag
  (the "adversarial entrenchment" guard): a debater that repeats the same
  unsupported claim twice is `entrenched` and its subsequent claims weigh
  0 until it adds a new grounded one.

### 4.4 Termination (adaptive + fail-safe)

`strategies/debate_score.py::termination_check(score_series, cfg) -> |
  ("continue") | ("stop", reason)`:

1. **Plateau**: information gain ≤ `debate_min_gain` (default 0.05) for
   ≥ `debate_stop_consecutive` (2) consecutive rounds → stop.
2. **Consensus exit**: independent agreement (from `consensus.py` on the
   pre-debate stances, NOT the rounded debate) ≥ `debate_consensus_thresh`
   (0.85) → stop (debate has nothing left to surface).
3. **Hard cap**: `debate_max_rounds` (default 3; current repo = 1).
Also: a **divergence / consensus-trap guard (R2)** — if `|bull_score -
bear_score|` grows for 2 rounds with no new claims, OR both sides converge
on identical targets within 1 round (artificial-consensus alert), cap at
min(hard cap, current+1) and reweight toward the baseline risk
distribution (Litmus: in adversarial settings more rounds can entrench;
cap it). The **L1 fast-abort (R1)** short-circuits termination too: a
critical hard-fail on round 1 stops the loop without running the L2 jury.

### 4.5 Independent arbiter / judge node

Two-layer, mirroring modern debate-eval practice:

- **L1 deterministic judiciary** (no LLM):
  - `consensus`/`agreement` (existing `consensus.py`)
  - `risk_governor` govern() on the state's numbers (existing)
  - `claim_verifier` (4.2) -> verdict on EVERY claim ledger row
  - `correlation_exposure` — if both sides' dominant claim cites the same
    single source, emit `low_diversty_warning` (correlated-error guard)
- **L2 LLM arbiter** (3rd model family, anonymized inputs, dimensioned
  rubric, `DebateVerdict` schema): scores `downside_tail_risk_weight,
  catalyst_clarity, empirical_grounding, assumption_sensitivity` each 0..2
  with a required one-line evidence per score; produces `rating` (5-tier,
  reuse `ResearchPlan` vocabulary) + `confidence_bnd` + `evidence_ledger_ref`.
  The vector rubric is orthogonal and audit-friendly (source doc:
  dimensioned rubrics over scalar scores). with a required one-line
  evidence per score; produces `rating` (5-tier, reuse `ResearchPlan`
  vocabulary) + `confidence_bnd` + `evidence_ledger_ref`.
  - **Order randomization + anonymized**: debater names/identities stripped;
    sides presented in rotated order to the judge (position-bias counter).
  - **Ensemble (opt-in, `debate_judge_ensemble`=2+)**: two judge models`ArgumentRecord` /
`DebaterTurnPayload`    two runs; disagreement → L1 deterministic verdict ties-breaks.
- Output replaces the current `judge_decision` — the existing Research
  Manager-style plan fields are kept for back-compat (report headers
  unchanged, `2_research/manager.md` still renders).

### 4.6 Orchestration (LangGraph, additive)

- The research debate becomes a **subgraph** (`GraphSetup` gets a
  `use_structured_debate` flag; default OFF = today's one-shot chain).
  Edges: `Bull -> Bear -> AdversarialScore -> judge L1 -> |continue:
  Bull|stop: JudgeL2 -> Trader`. Scorer + L1 are pure-node no-LLM costs.
- Router (`conditional_logic.py`): add `should_continue_structured_debate`
  consuming `termination_check`; keep `DEBATE_PATH_MAP` complete so a
  fall-through never raises (existing contract).
- Checkpointer graph-shape key includes the debate mode + model ids
  (existing per-shape keying already covers rounds; extend).
- **Dual-mode schema adapter (R3)** — debaters/judge emit `ArgumentRecord` /
`DebaterTurnPayload`  `DebateVerdict` via the provider's structured-output API when available;
  else a markdown-fence parser + Pydantic validation + bounded repair loop
  (reuse `structured.py`'s `bind_structured` / `invoke_structured_or_freetext`
  pattern). Fail closed: after a bounded repair budget, the turn is rejected,
  never silently coerced.
- **Capability gate at startup (R3)** — `debate_capability` health check
  runs before the graph compiles so a role is never routed to a model
  without the required JSON/tool guarantees.
- Concurrency (analyst concurrency > 1) unaffected; debate stays sequential.

### 4.7 State-machine orchestration (source doc: the missing content)

The source doc (`Strategies/Multi_Agents_Debate.md`) carries the concrete
**transition graph + state table** that turns the two-tiered design into an
enforceable FSM. The invariants: **L2 LLM judges are never invoked unless L1
deterministic validation fully passes**; a syntax/schema failure and an L1
hard breach short-circuit to the **pre-computed baseline risk view** (never to
nothing), while retryable faults get exactly one bounded regeneration;
anonymization+rotation happens between
L1 and L2; continuation only when `Round < Max` **and** `DeltaScore >= eps`.
This is exactly the "LLM as a state-local worker, controller owns the loop"
pattern the 2025 literature recommends for auditability and bounded execution.

```
       [INIT]
         |
         v
 +---------------+
 |  PARSE_TURN   |--- Fail (Syntax / Schema) --------------------+
 +-------+-------+                                              |
         | Valid Schema                                         v
         v                                            +----------------+
 +---------------+     HARD_BREACH                    |  EMIT_BASELINE |
 |   RUN_L1      |---> (leverage / math / schema) --> +----------------+
 +-------+-------+                                              ^
         | L1 Pass                                             |
         v                                                     |
 +---------------+     Divergence / Entropy Trap               |
 |  CHECK_EARLY  |---------------------------------->          |
 +-------+-------+                                              |
         | Proceed                                             |
         v                                                     |
 +---------------+
 | ANONYMIZE_ROT |  (Strip metadata, shuffle Agent order)
 +-------+-------+
         |
         v
 +---------------+
 |    RUN_L2     |  (Parallel blind dimensioned LLM judges)
 +-------+-------+
         |
         v
 +---------------+     Round < Max & DeltaScore > eps
 | AGGREGATE_L2  |---------------------------------->  (next round)
 +-------+-------+
         | (Round == Max OR Marginal Gain < eps)
         v
 +---------------+
 |  FINAL_SYNTH  |
 +---------------+
```

| Current state | Event / trigger | Condition | Next state | Action / output |
| --- | --- | --- | --- | --- |
| `IDLE` | `START_SIMULATION` | Config valid | `ROUND_DISPATCH` | Initialize turn context, reset state |
| `ROUND_DISPATCH` | `AGENTS_RESPONDED` | Both Bull & Bear output received | `PARSE_TURN` | Collect debater payloads |
| `PARSE_TURN` | `SCHEMA_VALIDATED` | JSON parse success | `RUN_L1_CHECKS` | Load verified data bounds |
| `PARSE_TURN` | `PARSE_ERROR` | Schema malformed / unrecoverable | `EMIT_BASELINE_FALLBACK` | Emit schema fault code; baseline fallback (no jury) |
| `RUN_L1_CHECKS` | `L1_HARD_BREACH` | Zero-tolerance (leverage/constraint, math contradiction, unparseable schema) | `EMIT_BASELINE_FALLBACK` | Route to pre-computed baseline risk distribution; no L2 |
| `RUN_L1_CHECKS` | `L1_RETRYABLE_ERROR` | `regen_count < debate_regen_max` | `REGEN_PROMPT_DISPATCH` | Increment `regen_count`; scoped single-field repair pass |
| `RUN_L1_CHECKS` | `L1_RETRYABLE_ERROR` | `regen_count >= debate_regen_max` | `EMIT_BASELINE_FALLBACK` | Budget exhausted; fall back safely to baseline |
| `RUN_L1_CHECKS` | `L1_SOFT_WARNING` | Non-critical (timestamp drift, ungrounded qualitative, rounding) | `CHECK_ENTRENCHMENT` | Apply `penalty_score`; forward annotated to L2 |
| `RUN_L1_CHECKS` | `L1_PASS` | Hard bounds and math checks green | `CHECK_ENTRENCHMENT` | Cache L1 metric penalties/scores |
| `CHECK_ENTRENCHMENT` | `ARTIFICIAL_CONSENSUS` | Divergence < `δ_divergence_min` (or entrenchment index > τ) | `REWEIGHT_TO_BASELINE` | Set α > 0; adjust output toward baseline |
| `CHECK_ENTRENCHMENT` | `VALID_DIVERGENCE` | Min ≤ divergence ≤ max; no entrenchment | `ANONYMIZE_ROTATE` | Proceed to blind, order-rotated L2 jury run |
| `ANONYMIZE_ROTATE` | `PAYLOAD_PREPARED` | Blind payloads generated | `RUN_L2_JURY` | Broadcast to heterogeneous LLM judges |
| `RUN_L2_JURY` | `JURY_RESPONDED` | All jury responses received | `AGGREGATE_L2` | Compute trimmed mean / L2 rubric |
| `AGGREGATE_L2` | `CONTINUE_DEBATE` | Round < Max & DeltaScore >= eps | `ROUND_DISPATCH` | Inject counter-arguments for round R+1 |
| `AGGREGATE_L2` | `CONVERGED` | Round == Max OR DeltaScore < eps | `FINAL_SYNTHESIS` | Emit structured debate record to audit trail |

**Mapping onto this repo (LangGraph)**: the FSM states are LangGraph nodes —
`PARSE_TURN` = the dual-mode schema adapter (R3) validating `ArgumentRecord` /
`DebaterTurnPayload`; `RUN_L1` = the pure `claim_verifier` + `govern` +
`divergence_check` + `classify_severity` (R1'); `REGEN_PROMPT_DISPATCH` = the
scoped single-field repair pass (R1'); `EMIT_BASELINE_FALLBACK` = the baseline
risk-view fallback (pre-debate stances); `CHECK_ENTRENCHMENT` =
`termination_check` (entrenchment index, artificial-consensus divergence
floor); `REWEIGHT_TO_BASELINE` = the α reweight (R2'); `ANONYMIZE_ROT` = an
identity-strip + order-shuffle node; `RUN_L2` = the dimensioned judges;
`AGGREGATE_L2` = trimmed-mean scorer; `FINAL_SYNTH` = the arbiter's
`DebateVerdict` synthesis. The router in `conditional_logic.py` consumes the
transition table's guards so a fall-through can never raise (existing
`DEBATE_PATH_MAP` contract). The `EMIT_BASELINE_FALLBACK` path lands on the
baseline risk view (pre-debate stances) and writes an explicit audit row;
`REGEN_PROMPT_DISPATCH` increments `regen_count` and re-enters `PARSE_TURN`.

The source doc's **four JSON schemas** (the original three + the 2026-08-31
`l1_execution_context.json`) are the canonical wire contracts and
**replace/extend** this doc's earlier claim-ledger sketches (4.2, 4.3). They
bind to pydantic models:

- **`debater_turn.json` to `DebaterTurnPayload`** — required: `round_index`
  (1..5), `stance` (BULL/BEAR), `core_thesis` (<=1500 chars),
  `quantitative_claims[]` (each: `metric_name`, `asserted_value`,
  `ground_truth_key`, `source`; `minItems:1`), `risk_factors[]` (each:
  `risk_id`, `severity` LOW/MEDIUM/HIGH/CRITICAL, `mitigation_stated` bool),
  `recommended_allocation_pct` (0..100).
- **`l1_eval_result.json` to `L1DeterministicResult`** — `verdict`
  (PASS / FAIL_HARD_GATE / FAIL_DATA_MISMATCH), `hard_gate_passed`,
  `metric_verification[]` (metric_name / asserted_value / ground_truth_value / error_margin_pct / is_valid), `risk_gate_evaluation` (max_drawdown_compliant,
  allocation_bound_compliant, calculated_var_95), `penalty_score` (0..100,
  the deterministic penalty from factual drift and constraint bounds).
- **`l2_judge_rubric.json` to `L2JudgeDimensionedRubric`** — `judge_model_id`,
  `round_evaluated`, `evaluated_agent_alias` (anonymized Candidate_X/Y),
  `dimension_scores` (empirical_grounding, downside_tail_risk_weight,
  catalyst_clarity, assumption_sensitivity; 0..10 each), `entrenchment_detected`,
  `rebuttal_effectiveness` (0..10), `rationale` (<=1000 chars).
- **`l1_execution_context.json` to `L1ExecutionContext`** — `round_index`,
  `regen_count` / `debate_regen_max` (regen bookkeeping), `severity_tier`
  (GREEN / SOFT_WARNING / RETRYABLE_ERROR / HARD_BREACH), `l1_action`
  (PROCEED / APPLY_PENALTY_AND_PROCEED / TRIGGER_REGEN / ABORT_TO_BASELINE),
  `entrenchment_metrics` (`entrenchment_index`, `divergence_delta`,
  `artificial_consensus_flag`, `reweight_alpha`), `baseline_fallback_payload`
  (`base_allocation_pct`, `var_95_limit`, `unconditional_risk_rating`) — the
  recovery-path record the FSM carries between states, so every
  fallback/regen decision is explicit and replayable.

All four validate with pydantic (the dual-mode adapter's structured path uses
these models directly; the markdown-fence fallback parses then validates the
same pydantic models), and every field feeds the pure L1 scorers / L2
aggregation with no fabrication.

### 4.8 Config & defaults

All `debate_*` keys default OFF/empty (current behavior bit-identical):

```
debate_enabled: false
debate_bull_model: ""   # family:id for bull (fallback quick)
debate_bear_model: ""   # family:id for bear (fallback quick)
debate_judge_model: ""  # FAMILY DIFFERENT from both (warn if not)
debate_judge_ensemble: 1
debate_max_rounds: 5  # matches DebaterTurnPayload.round_index (1..5); prior default 3
debate_min_gain: 0.05
debate_stop_consecutive: 2
debate_consensus_thresh: 0.85
debate_scoring_weights: {evidence:0.6, novelty:0.25, constraint:0.15}
debate_abstain_allowed: true
debate_fast_abort: true            # R1: hard-fail short-circuits / regenerates
debate_regen_max: 1                # R1: single-role regeneration budget
debate_divergence_cap_rounds: 1    # R2: artificial-consensus threshold (rounds)
debate_reweight_to_baseline: 0.5   # R2: base α: weight shift toward baseline on alert (α scales dynamically with risk)
debate_entrench_thresh: 0.8        # R2': I_entrench above this -> entrenchment penalty
debate_divergence_min: 0.15        # R2': |bull-bear score| below this -> artificial-consensus flag
debate_baseline_fallback: true     # R1': HARD_BREACH / exhausted-regen -> baseline risk view (never nothing)
debate_require_capability_matrix: false  # R3: startup health-check gate
```

### 4.9 File map (seams, no code yet)

| Concern | Where |
| --- | --- |
| Debater factories (model per role, tool surface, prompt contract) | `agents/researchers/bull_researcher.py` + `bear_researcher.py` (extend) |
| Arbiter | `agents/managers/research_manager.py` (or new `agents/arbiters/debate_judge.py`) + `agents/schemas.py` (`ArgumentRecord`, `DebateVerdict`) |
| FSM orchestrator / transition table | `graph/setup.py` (states as nodes) + `graph/conditional_logic.py` (router on the table's guards) |
| Canonical wire schemas | `agents/schemas.py`: `DebaterTurnPayload`, `L1DeterministicResult`, `L2JudgeDimensionedRubric`, `L1ExecutionContext` (pydantic mirrors of the source doc's four JSON schemas) |
| Claim ledger + scorer + termination | `strategies/debate_claim.py`, `strategies/debate_score.py` (pure) |
| L1 deterministic verifier | `reporting.audit_decision_numbers` pattern + `strategies/consensus.py` + `risk_governor` |
| Orchestration | `graph/setup.py` (subgraph + edges), `graph/conditional_logic.py` (router) |
| Pre-debate stances | `agents/utils/independent_vote.py` (reuse; feeds consensus-exit) |
| Evidence / tool ledger | run-level `_ohlcv` cache + a `tool_call_ledger` (new small state dict) |
| Capability matrix / dual-mode adapter | `strategies/debate_capability.py` (pure) + `agents/utils/structured.py` (extend) |
| Severity triage + regen budget | `strategies/debate_score.py::classify_severity` (pure) + `agents/utils/structured.py` (scoped repair pass) |
| Divergence / entrenchment / artificial-consensus | `strategies/debate_score.py::divergence_check` + `entrenchment_index` + `reweight_to_baseline` (pure) |
| A/B harness (R4) | `scripts/debate_ab_harness.py` (Brier + max-unforecasted-dd) |
| Report | `reporting.py` (2_research section gains `judge_scores` + `evidence_ledger` block, back-compat) |

---

## 5. What Literature says (sources, linke)

- Du, Li, Torralba, T-n Yen, Gashi 2023 — "Improving Factuality and
  Reasoning in Languge Models through Multiagent Debate" (founding result:
  inference-time debate improves facts/reasoning; no fine-tuning).
- 2025 controlled studies: intrinsic model strength + **group diversity**
  dominate gains; order/confidence visibility marginal; debate not
  consistently better than self-consistency/votng under matched compute —
  and adversarial peers can **entrench wrong consensus** (+30%).
- Heterogeneous cross-model critique: honest heterogeneous peer cuts harmful
  revisions (89%→35% on one MATH-hard setting); adversarial same-family peer
  reverts it; A-HMAD role-split agents +4-6% accuracy / 30% fewer factual
  errors. Caveat: cross-model consensus can still be correlated when models
  share training biases — diversity of error patterns, not branding.
- LLM-as-judge: independence from debaters, dimensioned rubrics >
  holistic verdicts, order/anonymization/rotation, deterministic checks
  first, ensembles for high stakes (position/verbos/self-prefernce biases
  are real).
- Grounding: claim-level verification + citation anchoring + abstain
  (Tool-MAD per-agent tools + faithfulness; PROClaim courtroom roles;
  VeriFin Verified/Viholated/Abstain; JADE evidence-vs-reasoning gating;
  "deceptive grounding" — right source, wrong entity — must be checked
  against the actual run ledger).
- Finance: outputs traceable to explicit source evidence = control risk,
  not just quality; structured reports + debate (TradingAgents paper,
  arXiv 2412.20138) is the framework we are sharpening.
- State-machine orchestration: an FSM controller (parse -> L1 gate ->
  halt/anonymize -> judge -> aggregate -> final synthesis) with the LLM as a
  **state-local worker** (not the loop owner) is the production answer for
  auditability, bounded execution and replayable stop conditions; simple
  gates own completion/failure/policy while LLM transitions are reserved for
  genuinely ambiguous decisions.
- Consensus illusion / entrenchment (2025-2026): debate can *reduce*
  accuracy when agents are homogeneous or pushed too many rounds — agreement
  can be illusory (consistency illusion, consensus collapse, sycophantic
  conformity; plurality voting can discard an already-correct answer; harmful
  correct→incorrect "answer flips"). Detect pathology from round-to-round
  stability / belief-update metrics (this design's `I_entrench`), never from
  final agreement; a no-debate baseline (majority vote over the same agents'
  FIRST answers) is the anchor any reweighting homes toward.

---

## 6. Phased rollout (advisory-first, opt-in)

- **P0 (already mostly present)**: deterministic overlays + computed
  context + independet stances — the "L1 judiciary" skeleton.
- **P1 — Grounding contract**: claim ledger + L1 hard verifier on the
  existing one-shot debate, no model changes. Pure, testable, low risk.
  Enforces citation before any LLM judge exists (R1 hard bounds included).
- **P2 — Structured scoring + termination + fast abort**: ArgumentRecord,
  scorer, plateau/consensus/max-cap stop, entrenchment guard, L1
  fast-abort / single-role regeneration, artificial-consensus reweight.
  Still advisory.
- **P3 — Heterogeneous models + tool surfaces + capability matrix**:
  bull/bear/judge families via config; per-role tool surfaces;
  `debate_capability` startup health check; correlated-error warning.
- **P4 — LLM arbiter (dual-mode)**: dimensioned vector rubric, anonymized,
  order-rotated, ensembled, via the dual-mode schema adapter (structured
  API + Pydantic repair fallback); replaces `judge_decision` (back-compat) —
  the visible quality jump.
- **P5 — Matched-compute A/B harness (R4)**: `scripts/debate_ab_harness.py`
  compares debate vs N=5 self-consistency + median voting under equal token
  budget, tracking **Brier score** (forecast calibration) and **maximum
  unforecasted drawdown** — not raw $P(\text{Up}) > 0.5$ accuracy. Debate's
  adoption case rests on auditability + risk-boundary discovery even where
  it only matches self-consistency directionally.
- **P6 — Gate evolution (optional later)**: once the A/B harness and
  calibration evidence support it, the L1 verdict may gate the Trader like
  the risk governor does — only after walk-forward / calibration evidence
  (repo rule: gates come last).

Each phase: `enable_*` flag OFF by default, hermetic tests with timers,
docs/README/CHANGELOG true, `py -3.12` everywhere.

---

## 7. Risks & honest limits

- **Cost & latency**: 3 model families × up to 3 rounds × scoring —
  must stay under the deep-run budget (the very thing the last fix freed).
  Mitigation: P1-P2 are LLM-cheap; P3-P4 opt-in with caps + early stop.
- **Judge bias**: no LLM judge is neutral; mitigation = dimensioned rubric,
  order rotation, anonymization, ensemble, and L1 deterministic votes that
  cannot be talked past.
- **Model availability / schema strictness**: some providers lack tool
  binding / structured output — per-role fallbacks to the quick/deep tiers
  (pattern from `risk_tool_loop`) + the **dual-mode adapter** (markdown-fence
  parse + Pydantic repair loop) and the **config-time capability matrix**
  (R3) re-route roles before the graph compiles; fail closed, never coerce.
- **Entrenched wrong consensus**: adversarial rounds can entrench; hence
  the **entrenchment index** `I_entrench` (round-over-round semantic/metric
  overlap with no new counter-evidence addressed), the divergence-floor rule
  (R2'): |bull−bear score| below `debate_divergence_min` without new
  L1-verified evidence raises the Artificial-Consensus Flag, and the
  **α-reweight** `W_final = (1−α)·W_debate + α·W_baseline` toward the
  empirical base rate — agreement is never a score.
- **L1 short-circuit over-trigger (R1/R1')**: a binary fast-abort could kill
  a valid debate turn early; mitigation — **severity triage** replaces the
  binary gate (`SOFT_WARNING` penalizes and proceeds annotated,
  `RETRYABLE` gets exactly one scoped single-field regeneration, only
  `HARD_BREACH` aborts), bounded by `debate_regen_max`, and the debate only
  aborts to the already-computed baseline risk view, never to nothing.
- **Determinism vs. LLM scoring**: claims/scoring/termination are pure
  functions with unit tests; only the dimensioned judge scores are LLM,
  and they cannot overrule L1.
- **Matched-compute caveat**: if debate ≤ single-model + voting on this
  repo's tasks, the arbiter layers still add value because the alternative
  (one deep model) cannot audit its own process; keep an A/B harness
  (`evaluate_config_gate`-style) before any gate ships.

---

## 8. Acceptance / evidence (for whoever builds it)

1. P1: a claim ledger row for every quantitative number in a debate turn;
   ≥1 `violated` detection when a claim contradicts a computed state value;
   `abstain` path verified.
2. P2: termination fires on plateau (synthetic score series), consensus,
   and hard cap; entrenchment flag after a repeated unsupported claim.
3. P3: bull/bear/judge resolve to three different provider ids when config —
   set; correlated-error warning when both sides cite one source; the
   capability matrix refuses a role/model pair that cannot meet the role's
   strictness floor (fail-closed config error).
4a. P4: `DebateVerdict` renders in `2_research/manager.md` (back-compat
   headers); judge scores per dimension with evidence lines; order rotation
   flips a synthetic biased sample; the dual-mode adapter round-trips a
   markdown-fenced response through Pydantic repair, and rejects (fail
   closed) an invalid one after the bounded repair budget.
4b. R1/R2: a round-1 hard fail aborts or triggers exactly one regeneration
   and never runs the jury; an artificial-consensus (identical targets, no
   new data) reweights the output toward the baseline risk distribution.
4c. R1'/R2': severity triage routes a synthetic `HARD_BREACH` to the baseline
   payload, a `RETRYABLE` metric-key mismatch to exactly one regen then
   baseline, a `SOFT_WARNING` to penalty + annotated L2 (`L1ExecutionContext`
   round-trips through pydantic); `I_entrench` on a repeated-persona series
   crosses τ and the divergence floor raises the flag with α>0, shifting
   `W_final` toward `W_baseline`.
5. Full suite hermetic (mocked LLMs per model), timers, ruff clean.
6. R4 A/B harness: debate vs N=5 self-consistency under matched tokens —
   report Brier score, max unforecasted drawdown, tokens/calls/latency, and
   the audit-trail counter-thesis count (the differentiator).
---

## 9. Risk-section parity (direction.md, v4)

The risk debate mirrors the research debate with the SAME structured
machinery. Direction: both sections run the same debater+judge pattern at
the same research depth, sharing the same model keys.

### 9.1 Scope of parity (implemented)

| Aspect | Research | Risk |
| --- | --- | --- |
| Structured turns | `DebaterTurnPayload` (bull/bear) | `RiskDebaterTurnPayload` (aggressive/conservative/neutral), same claim/risk/allocation contract |
| L1 verification | `create_debate_l1` (section="research") | same, section="risk" (final role = neutral) |
| Blind judge | `create_debate_judge` (2 candidates) | same node, 3 candidates (Candidate_X/Y/Z) |
| State channel | `debate_state` | `structured_risk_state` |
| Prose channel | `investment_debate_state.history` | `risk_debate_state.history` (reporting/PM consume unchanged) |
| Router | `should_continue_structured_debate(state)` | same, `section="risk"` |
| Depth knob | `max_debate_rounds` | `max_risk_discuss_rounds` — driven by ONE `TRADINGAGENTS_RESEARCH_DEPTH` |
| Models | `debate_bull_model` / `debate_bear_model` / `debate_judge_model` | aggressive→BULL key, conservative→BEAR key, neutral→quick fallback, judge→JUDGE key |

### 9.2 Model mapping (direction items 3-5)

- `TRADINGAGENTS_DEBATE_BULL_MODEL` → SD Bull (research) AND SD Risk
  Aggressive (risk)
- `TRADINGAGENTS_DEBATE_BEAR_MODEL` → SD Bear (research) AND SD Risk
  Conservative (risk)
- `TRADINGAGENTS_DEBATE_JUDGE_MODEL` → the L2 judge in BOTH sections
  (anonymized, order-rotated; Candidate_X/Y for research, X/Y/Z for risk)
- Neutral risk analyst has NO dedicated key → quick tier (user decision;
  it is the balancing role, stays on the run's fast model)

### 9.3 Depth parity (direction item 1)

One knob — `TRADINGAGENTS_RESEARCH_DEPTH` (1/3/5) or the CLI research-depth
selection — drives BOTH round counts to the same level:

- `max_debate_rounds` (research) and `max_risk_discuss_rounds` (risk) both
  = the selected depth on the structured path.
- Legacy path (`enable_debate` off): the research leg stays one-shot
  (bull/bear run once — 5 legacy turns degenerated and poisoned the RM,
  SKHY 08-31); the risk leg keeps its round-count loop.
- Explicit per-round env overrides (`TRADINGAGENTS_MAX_DEBATE_ROUNDS` /
  `_MAX_RISK_ROUNDS`) still win over the depth knob (#977 back-compat).

### 9.4 Router: round-cycling (fix applied)

`should_continue_structured_debate` previously hard-stopped after ANY bear
turn (`last_side != bull -> SD Finalize`) — with depth>1 the structured
research debate could never run a second round. The router now:

1. terminated / baseline fallback → Finalize
2. `pending_regen_role` (bounded) → the same role's node
3. else next role in the section order; when the round is complete and
   `rounds_done < max_rounds` → the first role starts the next round;
   otherwise Finalize.

This makes the depth knob actually take effect on the structured path.

### 9.5 Reporting

`4_risk/structured_risk_debate.md` mirrors `2_research/structured_debate.md`:
L1 verdict + judge scores per anonymized candidate + grounded claim ledger,
written from `structured_risk_state`.

### 9.6 Acceptance

- Risk graph with `enable_debate` on: Stances → SD Risk Aggressive → L1 →
  Conservative → L1 → Neutral → L1 → (rounds) → SD Risk Finalize → PM.
- `enable_debate` off: legacy risk chain bit-identical (Stances →
  Aggressive Analyst loop → PM); SD Risk nodes are no-op placeholders.
- All 5 debate test files green (claims, score, integration, stream
  hermetic, risk parity), ruff clean, full suite green.

---

## 10. Context-bounded debate FSMs (direction.md, v5)

Context breaks occur because full analyst reports, growing transcripts, and
expanding claim ledgers are repeatedly concatenated across multi-role,
multi-round loops (up to 15 risk debater turns at depth=5) and fed to the L2
judge and RM/PM. This section fixes it with bounded O(1) token overhead at
every node, without losing factual grounding or determinism.

### 10.1 Invariant & mitigation matrix (direction.md)

| Failure mode | Mitigation | Invariant preserved |
| --- | --- | --- |
| Hallucination / untethered claims | Ground-Truth Key-Value Registry + L1 deterministic gate | Factual grounding (debaters cite strict keys; L1 validates against computed values) |
| Superficial / disconnected judge rebuttals | Preceding-turn payload passed to L2 judge | Rubric parity (evaluates direct counterarguments w/o prior-round noise) |
| Decision degradation at RM/PM | Tabulated Debate Matrix + final-round theses + unresolved L1 disputes | Actionability (summary of verified numbers, not prose logs) |

### 10.2 State schema (mapped onto existing dict channels)

Direction.md's `CompactFSMState` pydantic classes are ADAPTED to the existing
`debate_state` / `structured_risk_state` dicts (no new AgentState channels):

- `ground_truth_registry`: `{keys: {k: v}, proposal_summary: ...}` — built ONCE
  per run from `ground_truth_from_state(state)` (parsed computed context) plus
  deterministic extractions from analyst computed lines (P4 coverage). Static
  and cache-friendly across all turns.
- `round_records`: full history kept IN MEMORY for reporting, but only a
  bounded slice surfaces in prompts.
- `active_disputes`: last ≤5 claims with L1 status `violated`/`unverified`
  (persisted via `ClaimRecord.status`, P0).
- `last_turn_payload`: `round_records[-1]` (the immediate prior speaker).
- `score_series` / `judge_scores`: unchanged.

### 10.3 Node changes

1. **create_debater_turn (P1)**: per-turn prompt = static Ground-Truth Key
   Index + Proposal Summary; dynamic = Preceding Opponent Turn (last round) +
   Active Dispute Ledger (≤5). Full analyst reports, full history, full claim
   ledger REMOVED from the prompt. Combined prompt: existing stance/schema
   contract + direction.md Operational Invariants (key binding, L1 audit,
   direct rebuttal, structured-only) + execution directives. `source` accepts
   `analyst_report | trade_proposal | macro_context | <tool/state key>`.
2. **create_debate_judge (P2)**: per-candidate call = candidate latest payload
   + preceding opponent payload + L1 verification vector. Full transcript and
   claim ledger dropped. Judge costs O(1).
3. **RM/PM (P3)**: `render_consumer_debate_matrix(channel)` table
   `| Role | Stance | Core Thesis | L1 Valid % | Judge Score | Rec Alloc |`
   replaces raw prose `{history}` in the consumer prompts. Reporting still
   writes the full prose transcripts.

### 10.4 Execution order

P0 (persist L1 statuses + registry) > P1 (delta debater prompt) > P2 (judge
O(1)) > P3 (matrix handoff) > P4 (registry coverage guard). All shared across
research + risk sections via the SECTION_* tables.

### 10.5 Acceptance

- Prompt-size bound: `build_turn_prompt` with 5-round history stays ≤ fixed
  budget; contains previous-turn payload + disputes + registry only.
- Judge prompt: candidate + opponent + scorecard only.
- RM/PM prompts: contain the matrix, not the transcript.
- Full suite + ruff clean; live QCOM: deepseek bull/conservative complete
  (no degraded turns), judge scores non-zero, RM/PM real plans.

### 10.6 Live-run validation (QCOM 145916, DELL 153305) + late fixes

The bounded architecture was exercised on live runs with real heterogeneous
models (all-`openai/gpt-5.6-luna` roles + judge). Findings and the fixes
they produced:

- **json_object 400 root cause**: the judge prompt lacked the literal token
  "json"; OpenRouter's json_object route (OpenAI/Azure backends) rejects such
  requests. The judge prompt now says "single JSON object" - the flat
  `scores[]` shape cue rides the same line. Without this token every judge
  call 400ed, the adapter fell back to a non-json_mode call, and the model
  returned empty dimensions. With it, real blind scores appear in both
  evidence files (verified on a fresh symbol).
- **#1A flattened rubric**: `L2JudgeDimensionedRubric.dimension_scores`
  (enum-keyed dict) -> `scores: [{dimension, score}]` array; legacy dict
  auto-normalizes; `_rubric_dimension_dict` keeps consumers unchanged.
- **Tolerant rubric coercion** + **empty-dim fallback** (directed retry ->
  prose-score parse -> rebuttal proxy -> honest UNAVAILABLE, never 0.0).
- **Claim-key resolution**: debaters humanize Key-Index labels; L1 kept
  marking them unverified -> `(unused)`. `resolve_ground_truth_key` now
  normalizes -> exact alias -> confidence-gated fuzzy (difflib, >=0.72,
  >=0.08 margin, token-overlap bonus) -> honest unverified. Tested against
  the real run labels.
- **Neutral model key**: `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL` resolves the
  neutral risk debater independently (was pinned to quick tier).
- Verdicts: no degraded turns, judge scores non-null, RM/PM decisions
  grounded in L1 + judge + independent reads. `(unused)` is now near-zero
  with the router; an empty result means L1 honestly cannot verify.

