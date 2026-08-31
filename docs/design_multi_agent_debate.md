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
  RUN_L2 -> AGGREGATE_L2 -> FINAL_SYNTH, with HALT_REJECT short-circuits)
  and its three JSON contracts (`debater_turn`, `l1_eval_result`,
  `l2_judge_rubric`) are the orchestrator's transition table and the
  debaters'/judges' pydantic payloads (§4.9): **L2 never runs unless L1
  fully passes**, schema faults and L1 hard-fails halt-and-reject, and the
  loop continues only when `Round < Max` and `DeltaScore >= eps`.

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
                     when unsupported) -> PASS/WARN/REJECT
                      |-- [HARD FAIL] -> FAST-ABORT / single-role regen
                      |-- [FAILED CLAIM] -> per-claim penalty, no jury
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
hard failure both **halt and reject**; anonymization+rotation happens between
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
 +---------------+     L1 Hard Failure               |  HALT_REJECT   |
 |   RUN_L1      |---> (e.g., Risk / Math) --------> +----------------+
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
| `PARSE_TURN` | `PARSE_ERROR` | Schema malformed / unrecoverable | `HALT_REJECT` | Emit schema validation fault code |
| `RUN_L1_CHECKS` | `L1_PASS` | Hard bounds and math checks green | `CHECK_EARLY_HALT` | Cache L1 metric penalties/scores |
| `RUN_L1_CHECKS` | `L1_FAIL` | Hard bound breach (VaR, bounds) | `HALT_REJECT` | Short-circuit round; bypass L2 calls |
| `CHECK_EARLY_HALT` | `ENTRENCHMENT_HIT` | Entrenchment index > threshold | `FINAL_SYNTHESIS` | Flag artificial consensus; freeze debate |
| `CHECK_EARLY_HALT` | `PROCEED` | Divergence within bounds | `ANONYMIZE_ROTATE` | Strip agent IDs; shuffle payload order |
| `ANONYMIZE_ROTATE` | `PAYLOAD_PREPARED` | Blind payloads generated | `RUN_L2_JURY` | Broadcast to heterogeneous LLM judges |
| `RUN_L2_JURY` | `JURY_RESPONDED` | All jury responses received | `AGGREGATE_L2` | Compute trimmed mean / L2 rubric |
| `AGGREGATE_L2` | `CONTINUE_DEBATE` | Round < Max & DeltaScore >= eps | `ROUND_DISPATCH` | Inject counter-arguments for round R+1 |
| `AGGREGATE_L2` | `CONVERGED` | Round == Max OR DeltaScore < eps | `FINAL_SYNTHESIS` | Emit structured debate record to audit trail |

**Mapping onto this repo (LangGraph)**: the FSM states are LangGraph nodes —
`PARSE_TURN` = the dual-mode schema adapter (R3) validating `ArgumentRecord` /
`DebaterTurnPayload`; `RUN_L1` = the pure `claim_verifier` + `govern` +
`divergence_check`; `CHECK_EARLY` = `termination_check` (entrenchment index,
consensus exit); `ANONYMIZE_ROT` = an identity-strip + order-shuffle node;
`RUN_L2` = the dimensioned judges; `AGGREGATE_L2` = trimmed-mean scorer;
`FINAL_SYNTH` = the arbiter's `DebateVerdict` synthesis. The router in
`conditional_logic.py` consumes the transition table's guards so a fall-
through can never raise (existing `DEBATE_PATH_MAP` contract). The
`HALT_REJECT` path falls back to the baseline risk view (pre-debate stances)
and writes an explicit audit row.

The source doc's **three JSON schemas** are the canonical wire contracts and
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

All three validate with pydantic (the dual-mode adapter's structured path uses
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
debate_reweight_to_baseline: 0.5   # R2: weight shift toward baseline on alert
debate_require_capability_matrix: false  # R3: startup health-check gate
```

### 4.9 File map (seams, no code yet)

| Concern | Where |
| --- | --- |
| Debater factories (model per role, tool surface, prompt contract) | `agents/researchers/bull_researcher.py` + `bear_researcher.py` (extend) |
| Arbiter | `agents/managers/research_manager.py` (or new `agents/arbiters/debate_judge.py`) + `agents/schemas.py` (`ArgumentRecord`, `DebateVerdict`) |
| FSM orchestrator / transition table | `graph/setup.py` (states as nodes) + `graph/conditional_logic.py` (router on the table's guards) |
| Canonical wire schemas | `agents/schemas.py`: `DebaterTurnPayload`, `L1DeterministicResult`, `L2JudgeDimensionedRubric` (pydantic mirrors of the source doc's three JSON schemas) |
| Claim ledger + scorer + termination | `strategies/debate_claim.py`, `strategies/debate_score.py` (pure) |
| L1 deterministic verifier | `reporting.audit_decision_numbers` pattern + `strategies/consensus.py` + `risk_governor` |
| Orchestration | `graph/setup.py` (subgraph + edges), `graph/conditional_logic.py` (router) |
| Pre-debate stances | `agents/utils/independent_vote.py` (reuse; feeds consensus-exit) |
| Evidence / tool ledger | run-level `_ohlcv` cache + a `tool_call_ledger` (new small state dict) |
| Capability matrix / dual-mode adapter | `strategies/debate_capability.py` (pure) + `agents/utils/structured.py` (extend) |
| Divergence / artificial-consensus | `strategies/debate_score.py::divergence_check` (pure) |
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
  entrenchment guard, divergence cap, **artificial-consensus reweight to
  baseline (R2)**, and the rule "agreement is NOT a score".
- **L1 short-circuit over-trigger (R1)**: a too-aggressive fast-abort could
  kill a valid debate turn early; mitigation — `severity` tiers (hard vs
  soft), single regeneration budget (`debate_regen_max`), and the debate
  only aborts to the already-computed baseline risk view, never to nothing.
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
5. Full suite hermetic (mocked LLMs per model), timers, ruff clean.
6. R4 A/B harness: debate vs N=5 self-consistency under matched tokens —
   report Brier score, max unforecasted drawdown, tokens/calls/latency, and
   the audit-trail counter-thesis count (the differentiator).