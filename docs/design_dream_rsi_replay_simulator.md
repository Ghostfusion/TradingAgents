# Design: Dream-RSI, and what a replay simulator would have to be built from here

**Source.** Zheng et al., *Dream-RSI: Recursive Self-Improvement through Evolving Worlds*,
arXiv:2609.14858v1 [cs.CL], 2026-09-14 (Google / UMD / Google DeepMind / UVA).
`github.com/zhengkid/Dream-RSI`.

**Status.** Design only. No code changed, no gate added, no behaviour touched.

**One-line finding.** The paper's *mechanism* does not transfer to this project, because the
artifacts this project records are not a discovery tree — but its *constraints* do, and two of
them name real gaps here: the project has no explicit research-allocation policy object, and the
paper's own policy-selection guarantee is an in-sample claim that this repo already owns the
machinery to correct and has never applied.

---

## 1. What the paper actually claims

Dream-RSI optimises the **exploration policy** of a long-horizon program-discovery loop — not the
program, and not the model weights. Three stages, repeated:

1. **Online explore.** The current policy drives a coding agent to expand a *discovery tree*. Each
   non-root node is one generation–evaluation attempt, recording its workspace, artifact,
   diagnostics and score.
2. **Construct a replay simulator.** The finished tree is frozen. A different policy traversing it
   "reveals" recorded children in a different order, with different batching and stopping. **No
   execution happens** — outcomes are read, not produced.
3. **Dream.** Many candidate policies are scored on the frozen history; the best is redeployed.

The decision interface is shared between online and replay. The policy observes a tree `T` and
picks a batch `C ⊆ A(T; W)` of nodes to continue from, where `W` is the worker count and `A(T)`
is the root plus the current leaves. The replay objective is

```
V_im = max_{v ∈ T_im*} s_v  −  β₁·N_im  +  β₂·( N_im / max(1, k_i*) )
       \___quality___/     \_cost_/      \_______parallelism_______/
```

where `N_im` counts revealed non-root nodes (the generation–evaluation requests the trajectory
represents) and `k_i*` is the number of decision rounds.

**The selection rule, and the claim that matters here:** after `M` revisions,
`π_{t+1} = π_{t m*}`, `m* ∈ arg max_m V^m`. Because the candidate set *includes the current
policy* (`π_t^0 = π_t`), the paper states `V^{m*} ≥ V^0` — "the selected policy is no worse than
the current policy". §5 is the honest part of the paper: the learned policy conserves compute
when improving, and re-expands when progress plateaus.

**The result that contradicts an instinct this repo acts on (§5.1).** Explicit directional
guidance — abstracting prior trajectories into high-level insights and injecting them into the
prompt — *consistently underperforms* its unguided counterpart, in both the fixed and the learned
paradigm, at equal budget. The paper's reading: in parallel exploration, strong semantic
priors over future search directions **over-constrain the space and impede diversity**.

---

## 2. What this project already has

This is not a greenfield comparison. Three of the paper's four ingredients exist here in some
form, and the prior work should be credited rather than rebuilt.

| Paper ingredient | In this repo | Verdict |
|---|---|---|
| Frozen history of completed runs | 56 report trees, each with `tool_evidence.json` + `run_card.json` | **BUILT** |
| Replay over recorded history at zero vendor cost | `scripts/context_ab.py` — `decision_items_from_tree:1189` reads a real tree's evidence and card; `ARMS:396` = `c1/c2/p1/p2`; `compact_prose:454` truncates deterministically | **BUILT, for context policies only** |
| An evaluator that scores a recorded run | `report_verifier.report_ledger:377` + `scripts/report_verify.py` → per-claim verdicts in `verify_flags.json` | **BUILT** |
| Parallel refining, the paper's controlled baseline | `batch.py:effective_workers:37` × per-symbol independent runs | **BUILT** |
| The depth knob | `research_depth` (`default_config.py:18`, `:595`) driving `max_debate_rounds` + `max_risk_discuss_rounds` | **BUILT, as a scalar** |
| The per-round cap `K₁` | `MAX_TOOL_ROUNDS = 8` (`conditional_logic.py:16`) | **BUILT** |
| Cost of a run | `reporting._run_card_llm_cost_est:980`; OpenRouter usage per call | **BUILT, unjoined** |
| **An explicit, executable allocation policy** | scattered across config keys, gates and the analyst list | **NOT PRESENT** |
| **An objective trading quality against cost** | quality and cost are measured in separate artifacts and never combined | **NOT PRESENT** |
| **A selection rule for "which policy"** | the multiple-testing machinery exists and is unused on this question | **NOT PRESENT (as applied)** |

`context_ab.py` deserves emphasis: it **is** a replay simulator over recorded trees, and its own
docstrings already carry the discipline the paper requires — items are built from the real
renders, and the expected numbers are parsed back out of the render "so the harness cannot drift
from the real card". What it replays is *what to show the decision model*. It does not replay
*how much research to buy*.

---

## 3. The two blockers, stated plainly

The paper's loop cannot be built here from the artifacts that exist, for two independent reasons.
Both were checked against the live trees, not inferred.

### 3.1 A recorded tree here is a chain, not a tree

Dream-RSI's replay works because its discovery tree holds outcomes for branches a *different*
policy would have taken. The tree is built by many parallel workspaces, so siblings exist to
choose between.

This project runs **one trajectory per analyst**. The four analyst reports are a contract
(`report_verifier.REPORT_STEMS:43`), not a search dimension. So the recorded structure is a
sequence of decisions with no unvisited siblings, and replay can only ever evaluate policies that
are **truncations** of what was actually run. You can ask "what if the debate had stopped one
round earlier" (the outcome is on record). You cannot ask "what if we had opened a different
branch" (there is no record of it, and no way to get one without running it).

This is not a fatal objection — it is a **scope limit**, and it happens to align with the question
this project actually has, which is cost, not breadth. `context_ab.compact_prose:454` already
exploits exactly the valid half of replay: truncation. The invalid half is extension.

### 3.2 The round structure is not recorded at all

Checked on `reports/WDC_20260915_120300`:

- `tool_evidence.json` carries `fundamentals` 46 / `market` 89 / `news` 31 / `sentiment` 5 leaves,
  each with keys `args, args_hash, content, status, tool, ts`. **`ts` is `time.monotonic()`**
  (`evidence_gather._leaf`), a process-relative float — not a wall clock, and not a round index.
- Those leaves come from the **deterministic gather**, which invokes every forced tool in one pass
  (`evidence_gather.gather_evidence`). They are not the LLM's exploration rounds.
- `run_card.json` top-level keys are `analyst_consistency, commit, config_hash, data_absence,
  debate, decision, generated, llm, llm_cost_est, sections, ticker`. **No round counts.**
- The LLM's own tool calls *are* journaled (`tool_call_log.log_tool_call`), but to
  `<data_cache_dir>/tool_calls/<SYMBOL>_tool_calls.jsonl` — **outside the report tree** — and the
  line records `ts, symbol, trade_date, analyst, tool, event, args` with **no round index**.

So the artifact that would answer "how many rounds did this analyst spend, and what did each
round buy" does not exist. `N_im` and `k_i*` in the replay objective have no producer here.

**Consequence.** A replay simulator for *allocation* is not constructible from the current trees.
A replay simulator for *context* is, and is built.

---

## 4. What does transfer

Ranked by value per unit of risk. None of these is the paper's loop.

### 4.1 The selection rule must not be the paper's (highest value)

The paper's `V^{m*} ≥ V^0` is a guarantee **on the fixed history H_t**. Selecting the argmax of
`M` candidates scored on the same `t` worlds is precisely the winner's-curse setting: the winner
is upward-biased because it was selected, not because it is best. Taken literally, the guarantee
licenses deploying a policy that is worse out-of-sample — the failure mode this repo already
names elsewhere.

This repo owns the correction and has never pointed it at this question:

| Symbol | Purpose, from its own docstring | Location |
|---|---|---|
| `deflated_sharpe` | "Lopez de Prado style deflated Sharpe: penalize multi-trial tuning" | `strategies/evaluate.py:103` |
| `pbo_flag` | "Crude overfit flag: best-trial in-sample picks fail out-of-sample" | `strategies/evaluate.py:235` |
| `reality_check` | White's Reality Check over a universe of candidates vs one benchmark | `strategies/evaluate.py:311` |
| `spa` | Hansen's studentised SPA test over a universe vs one benchmark | `strategies/evaluate.py:351` |
| `purged_cpcv_splits` | Naive-combinatorial purged CV fold indices, with embargo | `strategies/evaluate.py:181` |

`deflated_sharpe` and `pbo_flag` are exactly the two corrections the paper's selection step needs
and does not apply. **This is the single transferable idea with a correctness payoff**: adopt
"score candidate policies on recorded history" *only together with* a selection rule that
discounts for how many were tried. A raw argmax over `M` candidates on `t` worlds is a
measurement artefact, and this repo would be re-learning a lesson its own `evaluate.py` already
encodes.

Note the `deflated_sharpe` body is the simplified `observed − sqrt(2·ln n_trials)`, not the
Euler-Mascheroni form its docstring names. That is a pre-existing discrepancy, recorded here
because any adoption should not assume more rigour than the function has.

### 4.2 An explicit, prefix-only allocation policy object

The paper's most reusable engineering constraint is in Appendix B.2: a policy may use **only
revealed observations** — never unrevealed scores, a true optimum, hardcoded winning cell ids,
absolute score targets, or internal trace data. Every prune, widen, batch and stop decision "must
be explainable from the current prefix".

This project's allocation is currently implicit. It lives in `research_depth`
(`default_config.py:595`), `MAX_TOOL_ROUNDS` (`conditional_logic.py:16`), the analyst list, the
vendor chain, and roughly a dozen `enable_*` gates. Nothing states what those knobs are allowed to
read, and nothing records *why* a given allocation was chosen for a given run.

Adopting the **interface** — not the loop — means: one object that answers "how much research does
this symbol get", which may read only what is known before the research is bought (ticker, date,
instrument identity, vendor availability, prior track record), and **must not** read the rating,
the verify flags, the scorecard, or the realized return. That is a real constraint this repo does
not state anywhere, it is cheap, and it makes the existing knobs auditable.

The failure it prevents is concrete: an allocation policy that reads the final rating to decide
how much evidence to gather is a policy that cannot run.

### 4.3 A cost term, so quality and cost can be traded

The paper's objective is `quality − β₁·cost + β₂·parallelism`. This project measures all three and
combines none:

- quality: `verify_flags.json`, the engine scorecards, `run_card.json`
- cost: `reporting._run_card_llm_cost_est:980`, per-call OpenRouter usage
- parallelism: `batch.py:effective_workers:37`

There is no artifact that answers "was the 5-round debate worth its cost for this symbol". The
`research_depth` knob is a scalar set by hand, and the project's own history shows the cost side
is real: the forced-evidence block was measured at **139,372 chars (~34,843 tokens)** for one
fundamentals analyst against ~6,044 tokens of report produced.

This does not require the replay loop. It requires **joining two artifacts that already exist**.

### 4.4 §5.1 as a falsifiable experiment on an always-on feature

The paper's measured result is that explicit directional guidance **underperforms** its unguided
counterpart. This project injects exactly that kind of guidance, on by default:

- `enable_reflection` defaults **True** (`default_config.py:819`), and it is in-run guidance, not
  only post-trade: `reflection_hint` (`strategies/reflection.py:83`) produces a directive line
  ("what to re-check next") and `build_reflection_context:109` assembles
  `- {analyst}: score=… (h/t), hint: …` into the analyst prompt.
- `past_context` — same-ticker decisions and cross-ticker lessons — is injected at run start
  (`trading_graph.py:619-625`) and read into the Portfolio Manager prompt
  (`portfolio_manager.py:134-139`).
- `memory_log_path` (`default_config.py:491`) with pending entries that feed reflection.

**Why this is the highest-value experiment the paper licenses here.** It is a cheap ablation of a
feature that is *already on in production*, it has a measured prior from a peer-reviewed source
pointing the opposite way from the instinct that added it, and the repo has the machinery to run
it honestly: `context_ab.mcnemar_exact:309` for the paired test, `ungrounded_figures:297` for the
fabrication cost, `retention_table:536` for what an ablation actually removed, and 56 recorded
trees to run it over.

It also rhymes with this repo's own hard-won conclusion, recorded in
`docs/design_decision_context.md` §13.3: the Decision Packet proceeds *as a bound, not a lever*,
with H1a withdrawn as its justification. **This project has already learned once that adding
structure to a prompt does not reliably improve the decision.** §5.1 says the same thing about
adding direction to a prompt, and the same standard of evidence should apply.

The paper's own caveat is the reason this is an experiment and not a conclusion: its §5.1 is
measured on program-discovery search, where "guidance" names *search directions*. Analyst
reflection names *what to re-check*, which is a different object. The transfer is the hypothesis,
not the result.

---

## 5. What does not transfer

Stated explicitly, because the headline numbers are not comparable.

| Paper element | Why it does not apply |
|---|---|
| "162× fewer agent calls", "over 50× budget savings" | The denominator is SimpleTES at **51,200 generations**. A run here is ~12 LLM calls. There is no two-orders-of-magnitude budget to recover. |
| The recursive redeploy loop | Needs a growing pool of replay worlds. This repo has 56 one-shot trees, heterogeneous in date, vendor and config — enough for a paired test, not for recursive improvement across rounds. |
| The discovery tree as a search structure | §3.1: one trajectory per analyst is a chain. There are no unvisited siblings to replay. |
| `GridPlan(branch_count=W, refine_count=R)` | `W` maps to `batch.py` workers, `R` to `research_depth`. But branch count here is fixed at 4 by contract, not a search dimension. Cutting to 2 analysts is a different product, not a policy. |
| Appendix C, the discovered Lasso solver | Domain content, not method. |
| `noul` / TypeSafe decisions API | Unrelated to this paper; noted only because `scripts/jev_decide.py` now exists and is the natural place to ask typed questions of a document. |

---

## 6. A plan, if any of this is wanted

Ordered so that each phase is independently useful and nothing depends on the loop.

**Phase A — state the constraint (no code).** Write down, in the allocation policy's own terms,
what may be read before research is bought and what may not. This is documentation of a rule that
already holds implicitly; it costs nothing and it is the prerequisite for everything else.

**Phase B — join quality to cost.** Extend the existing run-card path so a single artifact carries
both the cost (`_run_card_llm_cost_est:980`) and the quality signal for the same run. No new
measurement, no new vendor call. This makes "was the depth worth it" answerable per run.

**Phase C — the §5.1 ablation.** Extend `context_ab.py` with a guidance arm, in the same shape as
the existing four, scored on the decision category with `mcnemar_exact`. Run it over the recorded
trees. Report the paired transition matrix first, then grounding, then retention — the order
§12.1 of the decision-context design already established. **This is the phase with a real chance
of changing production behaviour**, because `enable_reflection` is on by default.

**Phase D — only if Phase B and C justify it — record the round structure.** The missing
producer for `N_im` and `k_i*`: a per-round index on the tool-call journal, written *into the
report tree* rather than to the cache dir. Without this, no allocation replay is possible. Note
this is a prerequisite, not a win: it buys the ability to run Phase E, and Phase E is only worth
running if the truncation-only scope (§3.1) is enough for the question being asked.

**Phase E — replay + corrected selection.** Build the allocation replay over truncations, and
select with `pbo_flag` / `deflated_sharpe` rather than a raw argmax. Ship only behind a gate,
default off, in the pattern the eight score-engine gates already use.

**Do not start at Phase E.** The paper's loop is the last thing that should be built here, and it
is the only thing the paper is about.

---

## 7. What this document does not claim

- **It does not claim Dream-RSI would improve this project.** The mechanism does not transfer
  (§3), and the headline savings are measured against a baseline three orders of magnitude larger
  (§5).
- **It does not claim the paper is wrong.** Its claim is scoped to program-discovery search; the
  in-sample selection issue in §4.1 is a gap in the guarantee, not an error in the result, and the
  paper's own §5.1 negative result is a point in its favour.
- **It does not claim §5.1 transfers to analyst reflection.** The hypothesis transfers; the result
  was measured on a different object (§4.4).
- **It does not propose a gate, a config key, or a code change.** No code was changed.
- **It does not credit this repo with the replay idea.** `scripts/context_ab.py` had it first, for
  context policies, and it is the reason the comparison in §2 is possible at all.
