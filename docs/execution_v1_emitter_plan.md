# Research-side emitter plan — `research_decision.json` v1.1.0

Status: **implemented 2026-09-12** (R1-R5). The rules live in `tradingagents/execution_contract.py`
(one owner, shared by the emitter and the report verifier); the artifacts of the change are
`tradingagents/reporting.py::write_research_decision`, `agents/utils/report_verifier.py::_envelope_integrity`,
`scripts/report_verify.py`, `contracts/research_decision.v1.schema.json`, `tests/test_execution_contract.py`
(T1-T6) and the `envelope` tests in `tests/test_report_verify.py` (T9). T7/T8 already existed
(`tests/test_rebuild_gate_recovery.py`). Eight mutations were run against the new gates and all bit; §7 records
the decisions taken.
Owner: single operator. Date: 2026-09-12. Interpreter: `py -3.12`. Linter: ruff (E/W/F/I/B/UP/C4/SIM, line 100).

Scope: changes to **this** repo (`TradingAgents`, the research layer) so its artifacts satisfy the execution
layer's published contract. The consumer is `TradingExecution/signald/contracts.py`; nothing here imports it, and
the execution layer never imports anything here (independence, `Master_deign.md` §2.2).

Authority for *why* the boundary exists: `TradingExecution/docs/INTRADAY_ALGO_DESIGN.md` §2.
Authority for *what* the executor accepts: `TradingExecution/docs/INTRADAY_ALGO_IMPLEMENTATION.md` §2,
implemented in `signald/contracts.py` and proven by `tests/test_contracts.py`, `tests/test_inbox.py`,
`tests/test_envelope_v2.py`.

---

## 0. Why this plan exists

The execution layer now treats the artifact as a **versioned envelope**, not a loose JSON blob. Three facts make
the current emitter non-conformant, and all three are machine-checked there today:

| # | Fact (evidence in the execution repo) | Consequence for this repo |
|---|---|---|
| F1 | `contracts.SCHEMA_VERSION = "1.1.0"`. A version-less artifact is read as **1.0.0** and still ingests (`test_legacy_v1_artifact_needs_no_expiry`, `test_the_two_hash_orders`) — but a 1.1 artifact must carry `expires_at`, `idempotency_key`, `producer` and `artifact_sha256` (`test_v11_requires_idempotency_key_and_producer`, `test_v11_requires_the_artifact_hash`). | Emitting version 1.0.0 for ever means the executor can never check provenance, expiry or the artifact hash. |
| F2 | The emitter writes an **advisory** `binding_gate` (`tradingagents/reporting.py::_binding_gate`, values `halt` / `book_drawdown` / `analyzed_name_cvar` / `risk_gate`) under the same key name the executor reserves for **the gate-owned verdict label** (its own vocabulary: `house_drawdown`, `house_cvar`, …). | A name collision on a load-bearing field. `halt` happens to exist in both vocabularies, which hides the problem until the first `book_drawdown`. |
| F3 | Envelope timestamps must carry an **explicit UTC offset** (`contracts.naive_timestamp`, `test_a_naive_timestamp_is_rejected_on_the_wire`). | Any `expires_at` written as a naive local/UTC string is dead-lettered, not guessed at. |

F2 and F3 were found by writing the consumer's tests, not by reading this repo — which is exactly why the
interaction is written down here before either side ships.

---

## 1. What the executor accepts today (the rules the emitter must satisfy)

`signald/contracts.py::validate_envelope(raw, now)` — every failure is a `reason_code` on a dead-letter row
(`decisions/_dead_letter/<name>.reason.json`) plus an audit entry; nothing is partially applied.

| Rule | Reason code | Note |
|---|---|---|
| `schema_version` is semver; `MAJOR` must be 1 (a bare `1` = `1.0.0`; missing = `1.0.0`) | `unknown_major`, `invalid_version` | `MINOR`/`PATCH` may rise freely (BACKWARD_TRANSITIVE) |
| `ticker` non-empty | `missing_field` | |
| `direction` ∈ {add, buy, hold, reduce, sell, exit, none}; `action` ∈ {BUY, HOLD, REDUCE, EXIT, NONE}; `data_quality` ∈ {fresh, stale, partial, unknown}; `sleeve` ∈ {swing, intraday} | `invalid_enum` | closed enums, never coerced |
| `direction` or `rating` must resolve to an action | `unresolvable_action` | same mapping as `RATING_TO_DIRECTION` |
| `opportunity_score`, when present, is a number in **0..100** | `invalid_opportunity_score` | producer-owned |
| **v1.1 only:** `expires_at`, `idempotency_key`, `producer`, `artifact_sha256` present | `missing_field` | |
| `idempotency_key` is a **UUIDv4** | `invalid_idempotency_key` | |
| `producer` is an object with a non-empty `service` | `invalid_producer` | |
| `artifact_sha256` matches the body (recipe §2.2) | `artifact_hash_mismatch` | |
| `expires_at` / `produced_at` carry an offset, `expires_at >= produced_at`, and `expires_at` is in the future | `naive_timestamp`, `invalid_timestamp`, `expired` | compared against the executor's injected clock |
| `trade_permission` **must not be set** by the producer | `producer_set_permission` | the gate owns it (`TradingExecution` design D4) |
| `binding_gate` on an ingested artifact is **display data**: accepted and ignored | — | the gate always computes its own; see §3 R2 for the rename |
| unknown fields anywhere | — | ignored (`additionalProperties: true`) |

Idempotency at the boundary: the inbox keys on `{producer.service}:{producer.run_id}:{artifact_sha256}`
(falling back to `decision_hash`, then the body hash).

---

## 2. What to emit — v1.1.0

### 2.1 Additive fields (this repo's current keys are all retained)

```json
{
  "schema_version": "1.1.0",
  "idempotency_key": "<uuid4>",
  "produced_at": "2026-09-12T13:45:02+00:00",
  "expires_at": "2026-09-12T20:00:00+00:00",
  "producer": {"service": "tradingagents", "git_sha": "1cbadba", "run_id": "<uuid4>"},
  "opportunity_score": 42.0,
  "risk_context": {"regime": "risk-on", "research_cvar_975_1d_pct": 1.1,
                   "book_drawdown": 0.0724, "drawdown_limit": 0.10,
                   "single_cvar": 0.0483, "cvar_budget_pct": 0.03,
                   "risk_gate": {"verdict": "PASS", "reasons": []}},
  "artifact_sha256": "<64 hex>"
}
```

### 2.2 The hash recipes (both sides already share them)

```
body            = every key except the hash fields
artifact_sha256 = sha256(json.dumps(body minus decision_hash, sort_keys=True, default=str))
decision_hash   = "sha256:" + sha256(json.dumps(body minus artifact_sha256, sort_keys=True, default=str))
```

Both are computed with `sort_keys=True, default=str` over the **body**, not over the file bytes: `reporting.py`
already writes `decision_hash` this way, and the executor recomputes it identically (`schema.sha256_of`). The
two hashes exclude each other so either can be computed first — the same self-exclusion idiom the mandate
already uses. `artifact_sha256` must be **bare hex** (the executor strips an optional `sha256:` prefix, but do
not add one).

### 2.3 Field ownership (who may write what)

| Field | Owner | Rule |
|---|---|---|
| `opportunity_score` | **producer (this repo)** | 0..100, "how attractive is this idea on its own merits" |
| `confidence`, `thesis`, `rationale`, `invalidations`, `disclosure`, `risk_context` | producer | `risk_context` is advisory only: the executor records it and never reads a number out of it |
| `binding_constraint` (renamed), `action_basis`, `binding_reason` | producer | advisory labels that explain the *research* verdict |
| `sleeve` | **executor router** | do not set it. The router always routes research to `swing`, and a non-`swing` value is refused and quarantined |
| `trade_permission`, `binding_gate`, `permission_reason*` | **executor gate** | do not set them. A producer-set `trade_permission` is a dead-letter (`producer_set_permission`) |
| `decision_hash`, `artifact_sha256` | producer | hash-pinned; the executor verifies both |

---

## 3. Code changes (one work item each, in this order)

### R1 — emit the v1.1 envelope · `tradingagents/reporting.py::write_research_decision`

1. Add to `doc`: `schema_version: "1.1.0"` (string, replacing the int `1`), `produced_at`, `expires_at`,
   `idempotency_key`, `producer`, `opportunity_score`, `risk_context` (all values from state already in
   `final_state`; a field with no source stays `null` and the artifact is still emitted).
2. Compute `artifact_sha256` (bare hex) and then `decision_hash` with the §2.2 recipes, in that order.
3. `expires_at` policy (proposal, owner decision in §7): **the session that follows `effective_date`** —
   `effective_date` at 20:00 ET, converted to UTC with an explicit offset. An artifact produced before the open
   must not be actionable after the close of the next session.
4. `producer.run_id`: one uuid4 **per research run**, persisted with the run (see §5 R1-risk).
5. `git_sha`: `git rev-parse --short HEAD` at write time, best-effort, empty on failure (the executor requires a
   non-empty `service` only).
6. Keep the existing fail-closed guard: no `pm_decision` **and** an existing contract → do not write (never null
   history; the 2026-09-12 rebuild defect).

### R2 — rename the advisory `binding_gate` → `binding_constraint`

Call sites (all of them; a missed one leaves a key the executor reserves):

| File | Line | Change |
|---|---|---|
| `tradingagents/reporting.py` | 470, 625, 676 | the local unpack, the assignment, and the emitted key |
| `tradingagents/reporting.py` | 532-564 | `_binding_gate()` keeps its body; rename the *docstring*'s first return value and consider renaming the function to `_binding_constraint()` with all three callers updated |
| `tests/test_reporting.py` | 760, 773, 777, 782 | assertions on the new key |
| `tests/test_research_decision_emission.py` | 94-100 | same |
| `CHANGELOG.md` | 53, 69 | leave historical entries; add a new entry for the rename |

The rendered report prose (`reporting.py:470` renders "Basis: **risk reduction** (binding: …)") does not change —
it is a tuple, not a key lookup.

### R3 — teach the verifier the v1.1 rules · `scripts/report_verify.py` + `agents/utils/report_verifier.py`

Add `verify_flags.json` checks (the same machine-checked shape as the debate degradation flag): missing
`expires_at`; `expires_at` already in the past relative to the run's clock; `producer.service` empty; an
`artifact_sha256` that does not recompute; an `opportunity_score` outside 0..100. Each is a **flag**, not a
crash: the report tree must still render.

### R4 — docs

`docs/execution_v1_emitter_plan.md` (this file) is the contract note; add a one-paragraph pointer from
`docs/api_reference.md` (or the run-card doc) and record the field ownership table in the repo's CHANGELOG entry.

### R5 — tests (see §4)

---

## 4. Acceptance tests (each named, each with its mutation)

| # | Test | Mutation that must make it fail |
|---|---|---|
| T1 | A freshly emitted artifact validates against the executor's rules **using a local copy of the contract**: `contracts/research_decision.v1.schema.json` is vendored into this repo (duplicated by design — the two repos share a published interface, not code) and a test asserts the emitted keys/required set match it | drop one required key from the emitter |
| T2 | The two hashes recompute: `artifact_sha256` over the body-minus-both-hashes, `decision_hash` over the body-minus-itself | change one field after hashing |
| T3 | `expires_at > produced_at`, both offset-aware, and the expiry covers the next session's open | emit a naive stamp |
| T4 | `idempotency_key` is UUIDv4 and stable for one run, different across runs | reuse a module-level constant |
| T5 | `opportunity_score` is 0..100 or `null` | emit a raw debate score of 0..1 without scaling |
| T6 | The emitted artifact carries **no** `sleeve` / `trade_permission` / `binding_gate` | re-add the old key name |
| T7 | A rebuild (`scripts/rebuild_complete_report.py`) leaves an existing `research_decision.json` byte-identical | re-enable `emit_run_artifacts` |
| T8 | An artifact with no `pm_decision` is not written over an existing contract | remove the guard |
| T9 | `report_verify.py` flags a fabricated broken artifact (missing expiry, bad hash, out-of-range score) | neuter one flag |

T1 is the anti-drift gate: the schema copy is the published interface, and a change to the emitter that is not
mirrored in the copy (or vice versa) fails the test rather than a live run.

---

## 5. Rollout order and risks

**Order matters.** R2 (the rename) must ship **before** anything emits a non-null advisory constraint alongside
R1 (the version bump), so the two never coexist on the wire:

1. R2 rename (safe alone: the executor ignores an unknown field, and `binding_gate` on ingest is display-only).
2. R1 + R5 emitter and tests (the executor is already backward compatible with version-less artifacts, so a
   mixed fleet is fine during the transition).
3. R3 verifier flags, R4 docs.

| Risk | Why it matters | Mitigation |
|---|---|---|
| A re-emit changes the body after the hashes | `artifact_sha256` no longer matches → dead-letter, and the inbox key changes → a duplicate signal | hash last, in `write_research_decision`, immediately before writing; never post-edit the file |
| A rebuild re-emits the artifact | a new body ⇒ a new `artifact_sha256` ⇒ a *new* inbox key ⇒ the executor treats it as a second signal for the same decision | the executor also dedupes on `decision_hash` (journal) and the `write_research_decision` guard refuses to write without a `pm_decision`; keep both. If a re-emit is ever needed, bump `producer.run_id` deliberately and say so in the run card |
| The expiry policy is wrong for the swing sleeve | the executor refuses an expired artifact (`expired`) and the swing sleeve stops taking new positions | the next-session policy in R1; the executor's `ingest_window_hours` is the backstop, and the verifier flag (R3) surfaces it before the gate does |
| Clock skew between the two processes | an "expired" artifact that is really fresh | the emitter uses UTC-aware stamps only; the executor compares against its own injected clock and rejects naive stamps rather than guessing |
| The executor is absent (independence) | this repo must still work alone | nothing in R1-R5 reads or imports the execution repo; the schema copy in T1 is a copy |

---

## 6. Out of scope (and must not happen here)

- No order, broker, sizing or gate logic in this repo (`Master_deign.md` §2). This repo emits an *advisory*
  artifact and nothing else.
- No import of, or `sys.path` entry for, `TradingExecution`; no execution code vendored here.
- No broker credentials (`ALPACA_*` / `TRADINGAGENTS_ALPACA_*`) used by any artifact path: the execution layer
  deliberately does **not** read this repo's environment, and its `config.py` no longer accepts the
  `TRADINGAGENTS_ALPACA_*` names (boundary rule design §2.2 rule 3).
- No free prose parsed on either side: `thesis`/`rationale` travel as text, are never read as data.

---

## 7. Decisions taken (2026-09-12)

1. **`expires_at` policy** — the close of the session following `effective_date`, 20:00 ET, converted to UTC
   (`execution_contract.next_session_expiry`). Weekends are skipped here; the exchange holiday calendar stays
   the executor's, with its ingest window as the backstop. Always offset-aware: a naive stamp is rejected, not
   guessed at.
2. **`opportunity_score` source** — **`null`**, deliberately. This repo has no *deterministic* producer for
   "attractiveness on its own merits": the only candidates in state are the debate judge's LLM rubric mean
   (stochastic between runs) and the PM's prose confidence, and publishing either under a numeric field the
   executor may rank on would dress an estimate up as a measurement — the same defect class as the
   number/label integrity fixes of 2026-09-12. The schema allows `null` and the artifact still ingests. If a
   deterministic composite is ever computed on this side, `execution_contract.opportunity_score()` is the one
   place to change.
3. **`risk_context` contents** — an explicit allow-list (`ADVISORY_RISK_KEYS`: `book_drawdown`,
   `drawdown_limit`, `single_cvar`, `book_cvar`, `cvar_budget_pct`, `liquidity`, `regime`) plus the gate
   verdict; never a passthrough, so a key added to `final_state["risk_context"]` upstream cannot leak by
   default. `null` when nothing ran — an empty object would read as "the governor ran and had nothing to say".
4. **`producer.run_id` lifetime** — the **report directory name** (`NVDA_20260912_005957`), with a uuid4
   fallback when there is no directory to name. The inbox keys on `service:run_id:artifact_sha256`, so a run id
   that changed on a re-emit would turn a rebuild into a *second signal* for the same decision; the directory
   name is also the human-traceable one.
5. **Vendored schema location** — `contracts/research_decision.v1.schema.json` at the repo root, byte-identical
   to the executor's copy, diffed by a test that skips when the sibling repo is absent.

Also decided: `binding_gate` → `binding_constraint` (§3 R2) shipped **in the same batch** as the version bump,
so the two never coexisted on the wire; `confidence` travels only when the PM's value validates as 0..1
(dropped, never clamped — a clamp would present a broken value as a sound one).