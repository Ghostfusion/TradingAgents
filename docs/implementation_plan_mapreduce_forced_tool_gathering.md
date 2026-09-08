# Implementation Plan — Map–Reduce Forced Tool Gathering

**Status: plan — no code changed. Sources:** `docs/design_mapreduce_forced_tool_gathering.md`
(commits `527e2b8`, `31de259`); repo wiring verified against
`tradingagents/graph/trading_graph.py::_create_tool_nodes`,
`tradingagents/graph/analyst_execution.py::ANALYST_NODE_SPECS`,
`tradingagents/agents/utils/risk_tool_loop.py::ToolExecutor`,
`tradingagents/graph/conditional_logic.py::MAX_TOOL_ROUNDS`.

## Scope

Make the analyst evidence base **fixed in composition** per run: the runtime
(map) invokes a deterministic forced tool set; the analyst (reduce)
synthesizes from the merged evidence. Judge/PM/debate untouched. **Off by
default** — the current LLM-selected path remains the default.

**In scope:** the 4 information analysts (market / fundamentals / news /
sentiment).

**Deferred (tracked elsewhere, see §Tracked):** risk debaters + Trader
(own, plan-dependent) and true hung-thread termination.

## Architecture decision

Single **"Evidence Gather" node** with a bounded worker pool (per-tool
timeout, concurrency knob) writing one reducer-backed state key — not
LangGraph `Send` fan-out. One node = one barrier = simple reduce; `Send`
adds topology/checkpointer coupling for zero determinism gain.

## Operating philosophy (user directive, 2026-09-07)

1. **Feed as much registered-tool information to the LLM as possible** so it
   can make accurate decisions. `ALL` (every tool each analyst registers) is
   the intended operating mode; curated subsets are a lighter opt-in.
2. **Reduce vendor and LLM calls** — never request the same information over
   and over. Each tool is gathered at most once per analyst per run (cached
   on the state key), and the short-circuit tool node answers any repeated
   model request with "already provided in the Tool Evidence block" instead
   of re-hitting the vendor.
3. **Heavy local compute is acceptable** — the gather runs on the user's own
   hardware; the budget concern is vendor/LLM quota, not CPU.

Applied in code: `TRADINGAGENTS_ANALYST_FORCED_TOOLS=ALL` (local `.env`),
`evidence_gather.gather_for_analyst_node` (gather-once caching),
`evidence_gather.make_short_circuit_tool_node` (re-request → short-circuit),
wired from `tradingagents/graph/trading_graph.py::_create_tool_nodes`.

Gather-args extension (2026-09-07): the deterministic arg bag now carries the
date-window keys too — `symbol`, `start_date`, `end_date`,
`look_back_days` (rolling 30 calendar days on the trade date) — so data tools
that declare a window (`get_stock_data`, `get_news`, `get_massive_news`,
`get_news_sentiment`, `get_short_volume`, `get_verified_market_snapshot`, …)
return real data instead of a missing-arg `error` leaf. Pure-compute tools
(`get_scenario_dcf`, `get_allocation*`, `get_kalman_spread`, …) still need
model-supplied inputs and stay recorded `error`/`unavailable` — never
fabricated.

Tool pools (2026-09-07, user directive): tools are split at runtime by their
OWN schema into a **gather pool** (every required arg covered by the context;
~140 of 180) — force-gathered + short-circuited as above — and a **model
pool** (any required arg the context can't supply, e.g. `spot/strike` on
`get_bsm_option_quote`, `indicator` on `get_macro_indicators`, plus the
`TRADINGAGENTS_ANALYST_TOOLS_MODEL_SUPPLIED` escape hatch). Model-pool tools
are NEVER auto-attempted; they stay bound to the LLM, which owns their
inputs, and an explicit forced name in the model pool is skipped with one
warning. Classification is signature-derived so a FUTURE tool needing a
model input lands in the model pool automatically; the split is persisted
(`_model_pool` in `tool_evidence.json`) and shown by `repro_check --evidence`.

---

## Phase 0 — Config surface

| File | Change |
|---|---|
| `tradingagents/default_config.py` | 5 keys: `analyst_forced_tools` (`""`), `analyst_forced_tools_max_parallel` (`1`), `analyst_forced_tools_timeout_s` (`30`), `analyst_forced_tools_summary_window` (`12000`), mapped from env `TRADINGAGENTS_*` |
| `.env.example` | Document the new vars (commented) |
| `tests/test_env_overrides.py` (extend) | Hermetic: env → config parsed; `""` == off |

**Acceptance:** default behavior byte-identical; env parse test green.

## Phase 1 — Evidence gatherer (map)

New `tradingagents/agents/utils/evidence_gather.py`:

- `parse_forced_spec(spec, registered_names) -> list[str]` — comma list or
  `ALL`; unknown names skipped + logged (never raise).
- `gather_evidence(...)` — each tool in a bounded worker,
  `future.result(timeout_s)`; per-call **never raises** (leaf
  `ok|error|no_data|timeout`); content truncated to `summary_window`; args
  hashed.
- `format_evidence_block(evidence)` — deterministic `## Tool Evidence`
  prompt fragment; failed/timeout leaves printed explicitly `unavailable`.

**Reuse:** `ToolExecutor`/`_by_name` resolver from `risk_tool_loop.py` — no
new executor class.

**Tests (new `tests/test_evidence_gather.py`):** spec parse / `ALL` /
unknown-name / truncation / failure→status leaf / timeout leaf (fake slow
fn, tiny timeout).

## Phase 2 — Wire into graph (fan-in)

| File | Change |
|---|---|
| `tradingagents/agents/utils/agent_states.py` | Add `tool_evidence: list` (reducer `operator.add`) |
| `tradingagents/agents/analysts/*.py` (4) | Each analyst, **only when config on**, prepends `format_evidence_block()` to system/user content; forced names marked; `chain`/`bind_tools` surface unchanged (model still free to gap-fill) |
| `tradingagents/graph/analyst_execution.py` + `setup.py` | `EvidenceGatherSpec` + insert "Evidence Gather <Key>" node ahead of each analyst agent node when forced set non-empty; writes `tool_evidence` |
| `tradingagents/graph/conditional_logic.py` | No change — routers run off `tool_rounds`; evidence node executes before the analyst's normal loop |

## Phase 3 — repro_check evidence diff

`scripts/repro_check.py --evidence`: per-run `tool_evidence.json`
(analyst → tool/status table) in the report dir; cross-run status-diff
prints "which tools failed in which runs".

## Phase 4 — curated defaults + docs + full verification

1. Curate per-analyst forced sets from the real ToolNode registries in
   `_create_tool_nodes` (~10-15 highest-signal; skip ticker-arg tools —
   those remain model gap-fill).
2. `CHANGELOG.md` + AGENT_ONBOARDING line (this file is written).
3. Full affected suites + ruff (E/W/F/I/B/UP/C4/SIM, 100 cols).
4. Live smoke `py -3.12 batch.py … --symbol tsm` with forced set on →
   report shows `## Tool Evidence`; no de-orphan drops for forced tools
   (log diff).

---

## Commit sequence (each green → push `origin main`)

1. `feat: config keys for analyst forced-tool gathering (off by default)`
2. `feat: evidence gatherer — deterministic tool map with timeouts`
3. `feat: wire evidence fan-in; analyst reduce prompt block`
4. `feat: repro_check --evidence per-run tool status`
5. `feat: curated forced sets + docs`

## Risks

| Risk | Mitigation |
|---|---|
| Context blow-up | `summary_window` truncation + curated set |
| Hung thread (moomoo) | timeout records leaf + proceeds; real termination deferred (tracked) — today's behavior is worse |
| Ticker-arg tools | excluded from forced set; model gap-fill |
| Vendor values still vary | composition-only determinism, documented |
| Live probe cost (~1h45m/3 runs) | only with user confirmation |

---

## Tracked & deferred items

### TRACKED-1 — Hung-thread termination (deferred beyond v1)

- **Problem:** today there is **no tool-execution deadline at all** —
  `ToolExecutor.run` (`risk_tool_loop.py:143-153`) invokes synchronously
  with no timeout wrapper; a grep for `timeout` across
  `tradingagents/agents/utils` returns no tool-execution hits; the only
  deadlines in the codebase are LLM-provider request configs. Moomoo tools
  (`moomoo_extra_tools.py`) are thin `route_to_vendor(...)` wrappers with no
  connect/request deadline. A hung moomoo/OpenD call blocks the analyst node
  thread **indefinitely**; LangGraph `recursion_limit` bounds iterations,
  not wall-clock.
- **v1 provides:** `analyst_forced_tools_timeout_s` (default 30) marks a
  `timeout` leaf and the gatherer proceeds — strictly better than today.
- **Why deferred:** Python cannot preempt a thread wedged in C/blocking I/O,
  so the stuck tool drains in the background even after the timeout records
  it. Safe termination needs a per-tool subprocess / worker process with
  OS-level kill, or a signal-free cancellable executor — a portability and
  safety decision, deliberately not bundled into the gatherer.
- **Future acceptance:** a hung tool call terminates and the node continues
  with a `status=timeout` leaf within the recorded bound, with no leaked
  worker.
- **Reference:** design doc §3.5, §6.2.

### TRACKED-2 — Phase 5 scope: risk debaters + Trader (plan-derived tools)

- Boundary decision, not an omission: those roles compute deterministic
  strategies (`RISK_DEBATOR_TOOLS`, `TRADER_TOOLS` in `risk_tool_loop`) over
  cached run data — plan-dependent subsets cannot be gathered before the
  plan exists. Extend the same reducer when the plan is fixed; no new
  topology needed (they run in-node via `ToolExecutor` already).
- **Reference:** design doc §1 problem framing; on-screen Q&A 2026-09-07.

---

**Not started:** all code phases pending user "go". Design + plan docs are
the only artifacts so far.