# Design: Map–Reduce Forced Tool Gathering for Stable, Evidence-Complete Decisions

**Status: research + design only — no code changed (2026-09-07).**

Maps the research synthesized from the 2025-2026 tool-calling / map-reduce
literature against this fork's actual wiring (the analyst tool loops,
`MAX_TOOL_ROUNDS` cap, `_deorphan_tool_calls`, the structured-debate judge
ensemble + PM reliability gate added today, `risk_tool_loop`, the debate
`Send`-style fan-out) to give the analyst stages a deterministic, complete,
reproducible evidence base instead of LLM-selected, budget-capped, partial
tool subsets.

Companion to:
- `docs/design_multi_agent_debate.md` (the debate/FSM it feeds),
- `docs/design_risk_calculations_agent_wiring.md` (advisory-first coding),
- `CHANGELOG.md` 2026-09-07 entries (judge ensemble, PM gate, de-orphan).

---

## 1. Problem statement (why this document exists)

The 2026-09-07 reproducibility probe (3× TSM at old and at new config) showed
both runs yielded **2/3 self-agreement** (Underweight, Underweight,
Overweight → Hold, Overweight, Hold). The judge ensemble + `temperature=0.1`
+ judge→gpt-5.6-luna reduced but **did not eliminate** the flip. Two of the
root causes live in the *evidence-gathering* stage, not the debate/judge:

1. **The analyst LLM selects which tools to call.** Nothing forces a fixed
   superset. Run-to-run sampling changes call counts, order, and args → the
   final report is written against *different information*.

2. **The tool budget caps completeness.** `MAX_TOOL_ROUNDS=8` truncates a
   heavy analyst (fundamentals ~50 registered tools; observed multi-call
   turns of 7-30 per round, de-orphaning many unfulfilled calls). The report
   is written from *at most 8 executed rounds*, not "all tools called".

3. **Vendor failures are inconsistent across runs.** moomoo connect drops,
   Massive 403, fmp 429, EDGAR 404 make even the *same* call name return
   different content/amount of data run to run. The de-orphan log across the
   3 runs lists ~39 stripped calls spanning `get_basic_financials`,
   `get_smart_money`, `get_insider_transactions`, etc.

**Goal:** the analyst's evidence set becomes **deterministic in composition**
(which tools were asked) and **ordered/resolvable in value** (which calls
returned, which failed), so that judge/PM agreement is a read of the *model
consensus* on a fixed evidence base, not of *which tools happened to run*.

---
## 2. The technique: map–reduce with fan-out/fan-in, applied to tools

The literature consensus: **you cannot prompt an LLM to call "all tools"** —
standard function-calling APIs model-chooses-subset, and enforcement lives in
the **orchestration layer, not the model**. The canonical pattern is:

1. **DECOMPOSE** — split the task into fixed subproblems (the registered
   tools or a curated subset per analyst).
2. **MAP (fan out)** — the runtime, not the model, invokes each tool in
   parallel (or bounded concurrency); each result becomes a leaf in an
   aggregate state. This replaces "model asks for tools" with "code runs the
   fixed set."
3. **REDUCE / FAN-IN** — an LLM (the analyst) receives the **merged,
   deduplicated, ordered** tool outputs and writes the report/decision.
   optionally dedupes/truncates before the synthesis to control context.

LangGraph-native fit (already the graph library used here):
- **fan-out**: route to N concurrent tool-execution branches with a
  *reducer-backed* `results: Annotated[list, operator.add]` key — the
  branches run in parallel, no concurrent-write hazard.
- **fan-in**: a downstream barrier node that runs only after all branches
  resolve; the analyst's report node is that barrier.
- `max_concurrency` + node-level retries bound `moomoo`-style outages.

### 2.1 Why this reduces deviation (the mechanism)

| Source of flip | Under old design | Under forced-tool map |
|---|---|---|
| LLM picks different tools | report differs in *kind* of evidence | same tool set each run → only *values* differ |
| `MAX_TOOL_ROUNDS` cap truncates | report from ≤8 rounds | evidence gathered by code, cap applied to *width*, not depth |
| de-orphan strips mid-turn calls | input changes per run | tools run deterministically; failures recorded (not dropped) |
| vendor flakiness | silent absence | recorded `unavailable`/error leaf, still surfaced |
| judge/debate over the report | inherits analyst variance | judge sees a stable evidence base |

---
## 3. Design

### 3.1 New config knobs (no behavioral change when off)

All gated; default keeps the current LLM-selected path.

| Key | Default | Meaning |
|---|---|---|
| `analyst_forced_tools` | `""` | Comma list (or `ALL`) of tools the analyst must call; empty = current |
| `analyst_forced_tools_max_parallel` | 1 | concurrency for the fan-out executor |
| `analyst_forced_tools_timeout_s` | 30 | per-tool wall-clock cap (moomoo calls can hang) |
| `analyst_forced_tools_summary_window` | 12_000 | chars assigned to the reduce step per tool output |
| `analyst_tool_evidence_key` | `tool_evidence` | state key accumulating tool results |

### 3.2 Fan-out: a deterministic "tool gatherer" node

New node/helper `gather_tools(tools, ticker/args)` that:

- resolves the fixed ordered list (curated `, or `ALL` of `tools_by_name`),
- executes each via the **existing `ToolExecutor`/ToolNode machinery**
  (same `ToolMessage` shape, same per-call error containment — reuse
  `risk_tool_loop.ToolExecutor.run` semantics),
- writes to a reducer-backed `tool_evidence` key:
  `{tool: {args (hash), content (truncated), status: ok|error|no_data, ts}}`,
- is deterministic in **composition** (every tool in `analyst_forced_tools`
  is called), though values still vary with vendors.

This is a code-driven **map** with no LLM deciding anything.

### 3.3 Reduce: the analyst synthesizes from the merged evidence

The analyst chain (prompt → `bind_tools`) is unchanged in *shape*; only the
audit of evidence changes:

- the prompt gains a **`Tool Evidence` section**: the gathered
  `{tool → result}` aggregated summary (truncated to
  `analyst_forced_tools_summary_window` chars per tool), and
- tools that were already run deterministically are marked `# taken` in the
  tool list (with a synthetic "evidence already gathered" no-op arg), so the
  model doesn't call it again; the model fills the *gaps* only (optional,
  model still free to call anything else).

Result: the analyst's job becomes **reduce**: synthesize the fixed evidence
into the report; it cannot change the fact that a tool was/wasn't called.

### 3.4 Failure semantics (deliberate)

- A tool that fails (raises / returns "NO_DATA" / 429 / 404) → leaf
  `status=error` + `content=<error first line>`, never re-raised.
- A tool that never got a value in the old design was de-orphaned + dropped.
  In this design it is *recorded-missing*: the report can state
  "get_X: unavailable" explicitly (already the analyst's instinct), and the
  reproducibility check sees WHY it differed.
- `analyst_forced_tools` with a large set risks context blow-up → the
  `analyst_forced_tools_summary_window` truncation is the reduce/squeeze
  step. The literature recommends keeping the *active* set to ~10-20 tools
  and retrieving dynamically when a catalog is larger; our default should be
  a curated `fundamentals` subset of ~12-15 highest-signal tools, with
  `ALL` opt-in.

## 5. Interaction with today's code (what would change)

1. **`tradingagents/graph/setup.py` + `analyst_execution.py`** — optional
   pre-node "Evidence Gather" before each analyst when
   `analyst_forced_tools` is set; routes to gather node.
2. **`tradingagents/agents/analysts/*.py`** — the node's prompt builds from
   a `tool_evidence` block instead of a raw conversational history; the
   `chain.invoke` receives `state["tool_evidence"]` merged into messages or
   a system block.
3. **`tradingagents/agents/utils/risk_tool_loop.py`** — reuse `ToolExecutor`
   for the gather (no new executor), sharing its "never raises" contract.
4. **`structured.py` / `finalize_messages` / `_deorphan_tool_calls`** —
   unchanged; since evidence is predigested and complete, the cap-forced
   terminal turn has a full evidence base even if the model burns budget.
5. **`scripts/repro_check.py`** — add `--evidence` flag printing the
   tool→status table per run so a reproducibility probe proves *which*
   tools failed differ per run (the "information same?" question made
   answerable).

## 6. Hard limits & known tradeoffs

1. **Cost/scale**: a deterministic "call all tools" can multiply vendor hits
   per symbol. Mitigations: curated subset, `max_parallel`, per-tool
   timeout, intelligent truncation (`analyst_forced_tools_summary_window`).
2. **Vendor variance is not eliminated**: the *composer* is fixed, values
   still vary; the product claims determinism of *composition*, not *facts*.
3. **Model value is retained**: we do *not* remove the analyst's judgment —
   only its *tool-selection* freedom; it still synthesizes and prioritizes.
4. **The same "all tools" floor could over-notify**: tools whose data is
   inappropriate for a ticker (e.g. crypto tools on a stock) should stay
   OUT of the forced set — curate per analyst.
5. **No change to the PM gate**: the gate (judge flip / fallback) stays
   orthogonal; it reads the debate state, not the tool set.

## 7. Concrete next-step implementation plan (if approved)

1. Config keys + graph wiring (gather node; reducer-backed state) — pure,
   hermetic-testable.
2. Curate per-analyst forced sets (market/news/fundamentals/social) from
   each `ToolNode` list, ~10-20 tools each, in a new
   `analyst_forced_tools` default.
3. Analyst prompt upgrade: `## Tool Evidence (deterministic, all of these
   were invoked)` + no-arg marker on those tools for optional gap-fill.
4. `repro_check --evidence` output; run 3× tsm to compare the "which tools
   differed" table against the current probe.
5. Full suite + ruff + docs (this doc is step 0 — already written).

---

**Conclusion:** map-reduce + tool-call *fan-out in code / fan-in in the
analyst* is the recognized technique for "force all tools" without breaking
model workflow, and it maps cleanly to a LangGraph `Send`+reducer+aggregate
shape already in the repo's graph library. Research + design complete; no
code changed.