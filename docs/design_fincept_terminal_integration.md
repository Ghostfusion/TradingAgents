# FinceptTerminal (Fincept-Corporation) — Teacher Study for TradingAgents

Status: **design study only — no code changes.** Direct-source study of
`github.com/Fincept-Corporation/FinceptTerminal` v4 (`fincept-qt/`: C++20 +
Qt6 desktop terminal with embedded Python 3.11; `src/datahub`,
`src/services/llm`, `src/trading`, `src/mcp`, `src/services/agents`;
`scripts/`: 1400+ Python connectors + `agents/` FinAgent Core, `ai_quant_lab/`
Qlib+RDAgent, `Analytics/` wrapper registry; `docs/` DATAHUB_TOPICS,
agentic-research), plus web grounding. Everything here is **advisory and
opt-in**; the fork's no-execution / advisory-first / deterministic-over-LLM
mandates and its Python+React web stack are unchanged. Where lessons land in
`trading_web`, they are web-mirror scope (the fork's REST+polling app is the
seam being upgraded).

---

## 1. The one-paragraph takeaway

FinceptTerminal proves a single-product principle the fork's web mirror has
not yet reached: **every data surface in the app is governed by one typed
topic registry** — per-family `TTL` / refresh `min_interval` /
`refresh_timeout` / `push_only` / `coalesce` / `drop_on_idle` /
`pause_when_inactive` policy, one producer per family, freshness conveyed to
the user (`age_ms` vs TTL), errors preserve last-known-good, and per-run
disposable topics are retired when done. Around that bus sit three disciplines
the fork can lift directly: **tool-result size budgets with park-and-page**
(oversized vendor reads are parked in a ResultStore, the envelope says
`truncated` + how to page the rest back — detail on demand, not by default),
**dual tool-loop budgets with visible exhaustion** (round cap for token spend
+ wall-clock deadline for wait; running out is a normal outcome that must be
VISIBLE, never mistaken for completion), and **a durable task lifecycle**
(SQLite per-step checkpoints + resume-after-failure + staged user answers).
The quant/AI-agent surfaces (persona hedge funds, Qlib lab, RDAgent) validate
fork work already shipped or studied; the transferable bits are governance
metadata (persona dataclasses with `seniority` / `reports_to` /
`risk_tolerance`, an investment-committee chair with explicit statistical-
rigor decision criteria) and a "Python single source of truth" contract
discipline that mirrors and extends the fork's own calc→agent wiring gate.

## 2. What FinceptTerminal does that the fork already implements (validated)

| FinceptTerminal mechanism | Fork equivalent | Verdict |
| --- | --- | --- |
| Persona hedge-fund/investor agents (Buffett/Graham, Bridgewater/RenTech orgs) | analyst personas + structured debate + consensus (`consensus.rating_to_number` / `agreement_score`) + PM finalize + hash-chained decision ledger | fork is already deterministic-led; the **governance metadata** (§3.5) is the new nugget, not the personas |
| `LlmService` multi-provider (OpenAI/Anthropic/Gemini/Groq/Ollama/DeepSeek) + capability matrix | `llm_clients/` provider registry (14 providers, capability matrix, per-provider rate limits) | fork is ahead |
| Qlib AI Quant Lab (14-module coverage: RL, online learning, HFT, meta, rolling retraining) | `docs/design_qlib_integration.md` teacher study + `strategies/evaluate.py` (CPCV/PBO/deflated Sharpe) shipped | fork studied Qlib critically rather than wrapping it wholesale — deliberate, keep |
| Backtesting providers (BT/VectorBT/Backtesting.py/Zipline) with C++→Python catalog cross-check | `scripts/backtest_strategy.py` (PIT, tradability fills, participation caps, ride-through) + `test_calc_agent_wiring` audit gate | fork's backtest semantics are richer; the **fallback/minimal-accuracy rule** (§3.6) is the new bit |
| Paper trading (OrderMatcher, SL-TP, PaperMarkService mark-to-market) | fork is **advisory-only by mandate**; TradingExecution is the phase-gated successor | non-goal — never adopt the execution runtime in research |
| SQLite persistence (agent sessions, task checkpoints, OI snapshots, IV history) | fork is deliberately stateless per run; audit chain pins outputs, jobs table pins web runs | contrast, not adoption (see §4) |
| M&A/gov-data/maritime/news services | fork's vendor-chain mosaic (`route_to_vendor`, news/events/catalyst reads) | fork is ahead on data-quality gating (PIT, sentinels) |
| 100+ data connectors behind one DataClient-style seam | fork's vendor chains with `vendor_cache` TTL + fail-closed | fork is ahead; connector breadth ≠ lesson |
| Agentic research design doc (Reflexion, budget, HITL, skill library…) | fork's one-shot batch pipeline + `retry_chain_if_truncated` report repair | assessment table in §3.7; adopt budget + visibility only |

## 3. Adoptable lessons (phase-gated, advisory-first, default-off)

### 3.1 — Topic registry: one typed policy per data surface (A1, flagship, web)

**What:** `DataHub` (in-process pub/sub) + `DATAHUB_TOPICS.md` register every
family (`market:quote:<sym>`, `news:symbol:<sym>`, `broker:*:*:positions`,
`agent:stream:<run_id>`…) with per-family policy: `ttl_ms` (freshness),
`min_interval_ms` (lower bound on refresh — many subscribers can't hammer the
producer), `refresh_timeout_ms` (stuck producer un-pins `in_flight`),
`push_only` (scheduler never polls), `coalesce_within_ms` (high-rate feeds
deliver newest-value-once-per-window), `drop_on_idle` (unbounded per-run
topics released when the last subscriber leaves), `pause_when_inactive`
(hidden windows stop fan-out but keep the cache). `request(topic,
force=true)` bypasses `min_interval` for user buttons but the per-producer
rate cap still holds — rage-clicking can't hammer upstream. Errors go to a
per-topic channel and the cache keeps last-known-good. Every topic exposes
`age_ms()` so a UI can show "fresh / stale / dead" — a price with no age
indicator is actively misleading. Idle, long-stale, unsubscribed topics are
swept (payloads released; a re-show inside the window is still a cache hit).

**Gap in the fork:** `trading_web` is REST + frontend polling
(`setInterval` + `/api/jobs`); vendor refresh cadence lives implicitly in
`vendor_cache` TTLs; responses carry no freshness metadata; a UI-driven
refresh hitting a cold vendor path can hammer upstream (the web backend caps
parallel workers but not per-surface refresh intervals).

**Adopt (Phase-A1, web only):**
- `backend/topic_policy.py`: a small registry (`dataclass TopicPolicy{ttl_s,
  min_interval_s, coalesce_ms}`) over the surfaces the app actually serves —
  `ohlcv`, `news_series`, `signals_feed`, `reports`, `summaries`, `jobs`,
  `value_tools:<tool>` — applied in `backend/main.py` handlers (and the
  per-tool value-tools path): serve cached value inside TTL, refresh outside;
  `force=1` on the request bypasses the interval but a per-surface rate cap
  still applies.
- Responses gain `{ticker/…, generated_at, age_s, ttl_s}` fields; the
  frontend renders a subtle freshness state on the data cards it polls.
- Job runs stay per-run disposable: `retire_topic`-equivalent = the existing
  jobs row lifecycle (keep).
- `docs/web_TOPICS.md` in trading_web: the canonical registry table (the
  DATAHUB_TOPICS analogue) — every surface, its policy, its single producer.

### 3.2 — Tool-result size budget with park-and-page (A2, pipeline tools)

**What:** every tool result is shaped to `tool_result_budget_bytes` (default
8 KB). Oversized payloads are parked in a `ResultStore` (TTL-swept) and the
envelope sent to the model says `truncated: true`, `result_id: …`, and tells
the model exactly how to page the rest back (`result_fetch(result_id,
offset, limit)`). The budget is described as "a budget, not a guillotine":
detail is available on demand instead of by default. Because every round
re-posts the whole message array, one unshaped 1 MB filing re-bills as input
on every remaining round — the cap protects cost AND context.

**Gap in the fork:** reads cap row counts per call (advisory), and report
truncation is repaired by `retry_chain_if_truncated` — an extra LLM call
after the fact, costing tokens and a round trip. No read has an explicit byte
budget with a park-and-page protocol.

**Adopt (Phase-A2):** `tradingagents/agents/utils/result_store.py` — `put`
(shaped payload, TTL sweep modelled on the repo's own report retention) +
one `fetch_result(result_id, offset, limit)` tool bound to the market/funda
analysts; the biggest vendor reads (news chains, 13F files, OHLCV histories)
gain a `max_bytes` envelope with `truncated` + `result_id`; keep
`retry_chain_if_truncated` as the report-level backstop. Pure additive —
smallest phase, ships alone.

### 3.3 — Dual tool-loop budget + visible exhaustion + progress narration (A3)

**What:** the tool loop has TWO budgets because one round can start a 300 s
background job: `max_tool_rounds` caps token spend, `tool_loop_deadline_ms`
(default 10 min) caps the wait. Exhausting either is a normal outcome, not an
error, but it must be VISIBLE — the loop records `exhaustion_note()` naming
which budget ran out, logs it, and hands it to the model's final-summary
prompt so a truncated turn is never indistinguishable from a finished one.
Progress narration is pushed per round through a scoped emitter:
`tool_progress_label` renders "find tools · q" / "get_news · MARKETS" (first
short string arg; positional keys excluded; run-collapsing "×N" is the
consumer's job). Tool visibility itself is scoped per request via
thread-local `ToolPolicy` (RAII guard): the floating chat bubble hides
`navigation` tools while the tab gets the full catalog — request-scoped, no
shared-instance races.

**Gap in the fork:** analyst generation is retried on truncation but the run
card/job row doesn't record loop-exhaustion (rounds, deadline); the web job
view shows status only — no "now computing X" line; tools are bound
statically per analyst at graph build (fine today; per-request scoping is the
future knob if the tool set outgrows the context budget).

**Adopt (Phase-A3, small):**
- `run_card` gains `tool_rounds_used` / `tool_deadline_exhausted: bool` /
  `exhaustion_note` (the fork's run_card already carries `llm_cost_est` —
  same slot); job rows gain the same two fields for the web view.
- Web job view: a one-line "now computing…" from the capability's stdout
  ticks (batch.py `--probe` trace already exists — surface the last probe
  line; exclude numeric-only args like "· 0 / · 1").
- Note (no change): per-request tool scoping stays a documented future knob;
  our policy is static bindings + the wiring gate, which is deliberate.

### 3.4 — Durable task lifecycle: per-step checkpoints + resume (A4, largest)

**What:** `TaskStateManager` + `ResumableTaskRunner` implement Plan-and-Solve
with SQLite: `tasks` table (status/plan/checkpoints), `save_checkpoint(task,
step_index, step_result)` after every step, `resume_task(task_id)` continuing
from the last checkpoint after a crash, `save_question`/`consume_answer` for
staged user replies threaded into context, `complete/fail/delete`, `list`
with status filter. Their own agentic-research doc calls this "the simplest
durable design" — a LangGraph-style `(task, step, state_blob)` on SQLite.

**Gap in the fork:** `trading_web/backend/jobs.py` runs capabilities in a
bounded threadpool with a SQLite `jobs` row (`status/error/result_path` only)
and `recover_stale_jobs()` marks crash victims failed — a crash mid-batch
discards the run; the partial per-ticker report dirs stay on disk but nothing
resumes from them. `batch.py` has no in-flight checkpoint index.

**Adopt (Phase-A4, web + pipeline):**
- `jobs` table gains `checkpoint_json` (step index + per-ticker done list)
  written by `run_batch`/`run_pipeline` after each symbol completes (the
  per-ticker report dirs are already the durable state — the checkpoint is a
  small index over them).
- New capability `resume_job(job_id)`: re-runs only the un-done symbols under
  the original args JSON; `recover_stale_jobs` keeps its fail-marking (a
  list of resumable rows becomes a UI affordance later).
- DB migration + `test_jobs_resume` (crash mid-run → resume → no re-work of
  completed symbols).

### 3.5 — Organization-as-data governance metadata (A5, pipeline)

**What:** every persona is a dataclass — `AgentPersona{id, name, title,
department, seniority, background, expertise, responsibilities,
decision_style, communication_style, risk_tolerance, reports_to,
collaborates_with, tools, instructions, example_reasoning}` — and the
RenTech-style org wires a hierarchy: `InvestmentCommitteeChair` with
`PortfolioTools + RiskTools`, an explicit decision framework in its prompt
("demand p-value < 0.01, require out-of-sample validation, be skeptical of
overfitting; never exceed position limits; encourage dissent"), a
`compliance_officer`, `risk_quant`, `quant_researcher`, `signal_scientist`
roles with tools per role. Team-level config is JSON (`team_config.json`).

**Gap in the fork:** analyst personas exist and are priced; consensus is
flat (`agreement_score`, equal weights); the PM finalize block has prose but
no explicit statistical-rigor decision criteria; role metadata
(seniority/reports_to/risk_tolerance) isn't carried into the debate or the
ledger.

**Adopt (Phase-A5, small):**
- `strategies/consensus.py` gains `agreement_weighted(views, weights)`
  (seniority/role weights, default equal ⇒ current behavior unchanged) and
  the decision context carries `n_voting` / `n_abstained` per participant.
- The PM agent's decision-criteria block gains the explicit rigor text
  (demand OOS-validated evidence before conviction; cite the
  `evaluate.py` PBO/CPCV numbers when claiming robustness).
- Persona metadata table in `docs/api_reference.md` (id, seniority,
  reports_to, risk_tolerance) — docs-only, no runtime change.
  (This composes with the ai-hedge-fund A3 "abstention ≠ neutral" study —
  same `n_abstained` field.)

### 3.6 — Single-source-of-truth contract: minimal accurate fallbacks (A6, gate)

**What:** the backtesting-provider integration process treats **Python as the
single source of truth** for strategies/indicators/commands; C++ keeps only
"accurate but minimal" offline fallbacks and every layer cross-checks the
other (commands, strategy IDs, categories, indicator IDs, param names — exact
case) before a provider ships; one provider at a time, all 6 steps, then
verify live. "Never change `all_providers()` command lists without verifying
Python handles them."

**Gap in the fork:** `test_calc_agent_wiring` already enforces module
reachability + `@tool`→agent binding (the fork's own version of this gate —
validated). The NEW nuance: the web frontend hardcodes capability names in
`App.jsx` while `backend/capabilities.py` is the actual runner — a
duplicate-mind hazard of exactly the kind their cross-check exists to catch
(C++ types vs Python catalog). And offline/error fallbacks should be
"accurate but minimal" — the fork's batch path has explicit fallbacks
(no-LLM modes); no gate audits them for drift.

**Adopt (Phase-A6, gate only):**
- Extend `test_calc_agent_wiring` (or a sibling `test_web_capabilities.py`)
  with a capability-name cross-check: every capability string used in
  `frontend/src/*.jsx` must resolve in `backend/capabilities.py`, and every
  public capability must be referenced from the frontend or documented as
  API-only (the exact Command-List rule, mirrored).
- Rule note in the gate docstring: fallback lists exist for
  offline/error state — keep them accurate but minimal; never a second
  source of truth.

### 3.7 — Agentic-system gap checklist (A7, assessment only)

Their agentic-research doc scores a system against: durable task lifecycle,
per-step event streaming, adaptive re-planning, reflection/self-correction,
budget controller, HITL interrupt, skill library / cross-task memory, eval
harness. Fork score today: lifecycle = jobs table (no resume), streaming =
status-only, re-plan = none (batch is fixed-flow), reflection = report-level
retry only, budget = `llm_cost_est` + worker caps (no round/deadline note),
HITL = none (batch is fire-and-forget), skills = DSA-3 YAML strategy skills,
eval = `scripts/evaluate.py` + `evaluate_config_gate`. **Adopted now:** A3
budget+visibility, A4 resume. **Documented future:** adaptive re-planning and
HITL interrupt would change batch semantics — out of scope unless asked.

## 4. Explicit non-goals (reasons)

| FinceptTerminal surface | Why not adopt |
| --- | --- |
| C++20/Qt6 desktop frontend + embedded Python | fork is Python + React web mirror; stack lesson is the bus/policy discipline, which A1 extracts without the stack |
| Paper trading (OrderMatcher, SL-TP triggers, PaperMarkService, broker adapters) | fork is explicitly advisory-only; TradingExecution is the phase-gated successor |
| Crypto wallet / Solana / $FNCPT tokenomics / billing tiers (stake, veFNCPT, buyback) | commercial product layer, no research value here |
| MCP marketplace (McpManager, Gemini schema, tool marketplace) | consistent with the Hummingbot study non-goal; MCP stays out of the research fork |
| Local-first LLM via Ollama as the default runtime | fork uses cloud providers; local inference is a config choice, not a lesson |
| Qlib 100%-coverage wrapper suite + RDAgent hypothesis generation | separate Qlib teacher study exists; wholesale wrapping buys coverage, not correctness; the fork's own evaluate.py is the rigor layer |
| Analytics wrapper registry (ffn/fortitudo/gluonts/pmdarima/py_vollib/pypme wrappers) | the fork deliberately hand-rolls + tests its formulas (deterministic, hermetic); a wrapper registry is a future optionality note, not an adoption |
| Agent session memory / per-persona SQLite state | fork is stateless-by-design per run; the audit trail is outputs, not chat state |

## 5. Phases (dependency-ordered, all advisory + default-off)

1. **P1 — Topic registry (A1)**: `backend/topic_policy.py` + freshness fields
   + `docs/web_TOPICS.md` (web only). Tests: TTL served-from-cache vs
   refreshed, min-interval honored under burst, force=1 bypass, per-surface
   rate cap; no behavior change with policy defaults off.
2. **P2 — Result budget + park-and-page (A2)**: `agents/utils/result_store.py`
   + `fetch_result` tool + max_bytes envelopes on the biggest reads. Tests:
   under-budget passthrough, over-budget park + round-trip fetch, TTL sweep,
   envelope fields.
3. **P3 — Dual budget + visible exhaustion + progress line (A3)**:
   `run_card` + jobs rows gain `tool_rounds_used` /
   `tool_deadline_exhausted` / `exhaustion_note`; web job view shows last
   probe line. Tests: exhaustion note present when capped, absent when clean;
   jobs columns migrate safely.
4. **P4 — Durable resume (A4)**: `jobs.checkpoint_json` + `resume_job`
   capability + `recover_stale_jobs` update. Tests: crash mid-batch →
   resume → completed symbols not re-run, args JSON preserved,
   stale-recovery list correct.
5. **P5 — Org governance metadata (A5)**: `consensus.agreement_weighted` +
   `n_abstained` in decision context + PM rigor criteria + persona metadata
   doc. Tests: default-weights identity with current behavior, weighted
   disagreement, all-abstain → no-opinion (not 0).
6. **P6 — Single-source gate (A6)**: `test_web_capabilities` capability-name
   cross-check + fallback-minimal rule note. Tests: unknown capability in
   JSX fails, orphan backend capability flagged, everything currently wired
   passes green.

## 6. Honest limits

- **The bus is C++ in-process**: A1 extracts the *policy* (registry + TTL +
  rate caps + freshness), not the pub/sub engine — trading_web is a small
  REST app and a full bus would be over-engineering; the registry discipline
  is the transferable half.
- **No streaming protocol adopted**: agent:stream-style token firehose and
  WebSocket producers are out of scope (REST + polling lease is fine at this
  scale); the freshness metadata is the cure for the staleness polling hides.
- **Their numbers are their scale**: 8 KB result budget / 10 min deadline /
  24 activated tools are their tunings — adopt the discipline, calibrate to
  the fork's actual payloads (news chains and 13F reads are smaller).
- **Persona hierarchy ≠ our debate**: the fork's RenTech org runs as a
  delegation tree with a chair's veto; our G3 consensus + PM finalize serve
  the same governance goal without role hierarchy — A5 adds metadata and
  weights, not a new org.
- **No lookahead / no cost regression**: A2/A3 must reuse the repo's
  existing PIT gates and `llm_cost` accounting; budgets are caps, never
  behavior changes when defaults are off.

## 7. Validation & sequencing

Per phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs true, trading_web mirrored where the surface is
web (P1/P3/P4 are web; P2/P5 are pipeline + web tool wiring; P6 is a test
file). No behavior change while the new config keys (`enable_topic_policy`,
`result_store_enabled`, etc.) are off (defaults off). Live smokes: P1 —
`GET /api/ohlcv?ticker=AAPL&force=0` twice in TTL shows `age_s` field and the
second call serves cache; P2 — a news read over budget returns `truncated` +
`result_id` and `fetch_result` round-trips; P4 — kill a batch mid-run,
`POST /api/jobs/<id>/resume`, completed tickers not re-researched.

Mapping: **A1 → P1**, **A2 → P2**, **A3 → P3**, **A4 → P4**, **A5 → P5**,
**A6 → P6**; A7 is assessment-only. P1/P2 are independent (batch);
P3 depends on the run_card/jobs seams already shipping; P4 is the largest
and lands last; P5 composes with the ai-hedge-fund A3 study (shared
`n_abstained` field).