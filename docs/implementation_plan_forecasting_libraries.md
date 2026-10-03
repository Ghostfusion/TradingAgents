# Implementation Plan — The Forecasting Layer (companion to `docs/design_forecasting_libraries.md`)

**Status:** PLAN — nothing built. **Zero dependencies are admitted by this plan as written**; FL-1…FL-4
are the declaration, the registry, the refusal record and the admission test. FL-5 is a policy bind and
FL-6 is an owner decision.
**Date:** 2026-10-03
**Parent design:** [`design_forecasting_libraries.md`](design_forecasting_libraries.md)
**Parent survey:** [`design_fin_paper_survey_26.md`](design_fin_paper_survey_26.md)
**Ground rules:** the eight inherited rules in
[`paper_survey_26/README.md`](paper_survey_26/README.md) §1, plus `docs/AGENT_ONBOARDING.md` §0 and the
eight invariants in `docs/MASTER_DESIGN.md` §2.
**Items:** FL-1 (WORK, P1), FL-2 (WORK, P1), FL-3 (WORK, P1), FL-4 (WORK, P2), FL-5 (DOC, P2),
FL-6 (DECISION).
**Gates added:** **none.** Every artifact here is always-on, read-only and pure; there is nothing to
switch off, and `tests/test_gate_env_toggles.py` is therefore not touched by this theme.

---

## 0. Scope

The design doc's verdict is that the proposal's model families are already owned (`design_forecasting_libraries.md`
§5) and that its one useful contribution is the **`ForecastContract` shape** (§6). This plan builds
exactly that, and nothing else:

- a **declaration** (`ForecastRecord`) that a forecast number carries its producer, gate, horizon, unit,
  status, named refusal, interval and provenance;
- a **registry** that declares one producer per `(key, horizon)` and makes invariant 8 checkable for
  forecasts;
- a **visible refusal** for `return_forecast`, so the engine's decision not to forecast returns is a
  cited record rather than a missing field;
- an **admission test** for forecasting dependencies, so a future `pip install` cannot silently introduce
  a second producer.

### The inherited rules that bind this theme specifically

1. **Ground rule 2 — one producer per derived quantity.** FL-2 exists *only* to enforce this; it is the
   whole point of the theme.
2. **Ground rule 3 — no item adds a member to `COMPOSITE_ENGINES`.** The contract is a declaration
   layer, not an engine; the tuple stays `(fundamental, technical, regime, risk)`.
3. **Ground rule 4 — coverage travels with the number.** Every `ForecastRecord` carries `as_of`, its
   window and `padded`.
4. **Ground rule 7 — each new public symbol ships with its first caller in the same commit.** FL-1 must
   therefore land with FL-2 (its first caller), or with one existing producer adapted to emit a record.
5. **Ground rule 8 — nothing here may be called from `prepare_initial_state`, `finalize_run`, or any
   agent tool.** The contract is read by producers; it never calls them.

**Rule-4 impact: none.** No tool, no gate, no config key, no report key, no screener column. The
declaration is internal to `tradingagents/strategies/` and adds no capability the web app can reach.

---

## 1. Item cards

### FL-1 — The `ForecastRecord` declaration

**Target.** New `strategies/forecast_contract.py`: a frozen `dataclass` (or equivalent validated
mapping) with the §6.1 shape of the design doc, plus one validator.

**Behaviour.** Constructs and validates a forecast record. Three rules are enforced at construction
rather than documented as guidance:

- `value is None` **iff** `status != "ok"` — a refusal can never carry a `0.0`;
- `status == "unavailable"` requires a non-empty `unavailable` reason;
- an `interval`, when present, must carry `nominal` **and** `realized_coverage` — the design doc's
  §6.2 rule 4, taken from `conformal.py`'s own module comment ("read the realized coverage, never the
  nominal level alone").

**First caller.** `forecast_registry` (FL-2). Without FL-2 the symbol has no caller and
`tests/test_calc_agent_wiring.py` will fail it by design.

**Phase / run mode.** P1 / in-run, pure, allocation-free, no I/O.

**Gate.** none — always available, because a declaration that has to be switched on is a declaration
nobody uses.

**Failing-first test.** `tests/test_forecast_contract.py::test_a_refusal_cannot_carry_a_zero` — mutating
the validator to admit `value=0.0` with `status="unavailable"` must fail the test by name.

**Acceptance.** A record with `status="unavailable"` and `value=0.0` raises; the same record with
`value=None` constructs and round-trips to a dict; an `interval` missing `realized_coverage` raises;
`padded` is a required field with no default.

**Depends on.** nothing.

**Doc caveat.** This is a **declaration**, not a calculator. It has no analytic claim to cite, so it
correctly gets **no `@tool`** and **no prompt line** — the design doc's §6.3 draws that boundary. The
wiring gate is satisfied by FL-2 being a real caller, not by a tool binding.

### FL-2 — The forecast registry and the second-producer gate

**Target.** New `strategies/forecast_registry.py` (or the registry half of FL-1's module): one declared
mapping `key -> {horizon, unit, producer, gate, status}` for every forecast-like number the engine emits.

**Behaviour.** Declares, in one place, which module is the authority for each `(key, horizon)`. It
**reads no config and computes nothing** — it is a manifest. Its output is the list of declared keys,
each pointing at a symbol that must exist.

Seeded from the design doc §5.2's verified table: `rv.d1` ← `strategies/long_memory.py::rv_forecast`
(gate `enable_long_memory`); `memory.d` ← `::memory_parameter` (same gate); `jump_share` ←
`strategies/volatility_models.py::bipower_proxy`/`quarticity_proxy` (gate
`enable_jump_robust_proxies`); `regime.p_stress` ← `strategies/regime.py` (gate
`enable_hmm_heavy_tails`); plus the conformal interval axis and the already-declined `return.*`.

**First caller.** `tests/test_forecast_registry.py` **and** the run-card/report writer path that lists
declared forecast keys beside the score engines — the registry must be *reachable*, not merely present
(ground rule 7).

**Phase / run mode.** P1 / in-run, pure.

**Gate.** none.

**Failing-first test.** `tests/test_forecast_registry.py::test_no_key_has_two_producers` — the mutation
is to point one key at two producers, which must fail by name. A second test resolves every declared
`producer` symbol via `importlib` and fails when a declared symbol is renamed or deleted (the failure
mode that made the forecast doc's own anchor tables drift — see §8.5).

**Acceptance.** Every declared key resolves to exactly one existing symbol; renaming a producer symbol
fails the suite with the key and the missing path named; the registry itself imports no vendor, no
config and no optional dependency.

**Depends on.** FL-1.

**Doc caveat.** The registry is the **only** new place a forecast key is named. A producer that emits a
forecast without a registry row is the exact defect the gate is meant to catch, so the gate is a
*completeness* test, not merely a uniqueness test.

### FL-3 — `return_forecast` ships as `declined`

**Target.** A single `declined` row in the FL-2 registry, with its reason text drawn from the design
doc §4 and the existing `CHANGELOG.md` decision.

**Behaviour.** Declares `return.*` as `status="declined"`, carrying: the corpus result
(`design_fin_paper_survey_26.md` §3 — return-rank log-likelihood gain 0.007 against volatility-rank
0.108), Hjalmarsson (2006) on out-of-sample return predictability under a small coefficient, and the
repo's own recorded rejection of an expected-return construction. It produces **no number, ever**.

**Phase / run mode.** P1 / in-run, pure.

**Gate.** none.

**Failing-first test.** `tests/test_forecast_registry.py::test_return_forecast_is_declined_with_a_reason`
— the mutation is to remove the reason, which must fail by name.

**Acceptance.** The registry contains the declined key; its reason is non-empty and cites the design
doc; nothing in `strategies/` computes a return forecast.

**Depends on.** FL-2.

**Doc caveat.** The point is *discoverability*, not decoration: an absent key invites a future
contributor to add one; a `declined` key with a cited reason makes that a visible reversal (design doc
§9.1).

### FL-4 — The dependency-admission test

**Target.** A declared table (in this plan, §3) plus
`tests/test_forecast_dependency_admission.py`, which parses `pyproject.toml`'s optional-dependency groups
and asserts every forecasting-related extra appears in the table with a verdict.

**Behaviour.** Any dependency added for forecasting must carry: a verdict
(`INTEGRATE`/`CONDITIONAL`/`REJECT`), a reason, and — for `CONDITIONAL` — the FL item that unblocks it.
A new extra with no row fails the suite. This is the mechanism that turns "should we adopt X?" into a
reviewable declaration instead of a silent install.

**Phase / run mode.** P2 / test-only, offline.

**Gate.** none.

**Failing-first test.** The test itself, against a synthetic extra appended to a temp `pyproject.toml`
fixture.

**Acceptance.** Adding a hypothetical `forecasting = ["statsforecast"]` extra to a fixture fails the
test until a verdict row exists; the real `pyproject.toml` passes with **zero** forecasting extras today.

**Depends on.** nothing (can land independently).

**Doc caveat.** It enforces the *process*, not the *judgement*. It cannot tell whether a verdict is
right — only that one was recorded.

### FL-5 — Bind V1's learned members to the offline-refit mechanism

**Target.** A paragraph in `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md`'s V1 card
(the owner of the item), pointing at FL-4.

**Behaviour.** Records that if V1 unblocks and its learned members (`GRU`, `XGBoost`) are not expressible
with the in-house regressions, the dependency enters as a **versioned offline refit artefact** under
ground rule 8 — never as a live call from the decision path.

**Phase / run mode.** P2 / doc.

**Gate.** none.

**Failing-first test.** none (a cross-reference has no behaviour to mutate).

**Acceptance.** V1's card names its admission path; this plan does not restate V1's content.

**Depends on.** FL-4.

**Doc caveat.** This is a **two-line bind**, not a re-design. V1's own plan already states the
offline-artefact shape; this only connects it to the admission rule.

### FL-6 — Owner decisions

The two open decisions in the design doc §9: whether `return_forecast` ships `declined` or is omitted,
and whether the dependency policy admits NCSA-licensed packages. Both are one sentence each and neither
blocks FL-1…FL-5.

---

## 2. Item table

| id | kind | item | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|---|
| **FL-1** | `WORK` | `ForecastRecord` declaration + validator | `strategies/forecast_contract.py` (new) | P1 | in-run, pure | none |
| **FL-2** | `WORK` | forecast registry + the no-two-producers test | `strategies/forecast_registry.py` (new) | P1 | in-run, pure | none |
| **FL-3** | `WORK` | `return_forecast` declared `declined`, with its reason | FL-2's registry | P1 | in-run, pure | none |
| **FL-4** | `WORK` | dependency-admission test over `pyproject.toml` extras | `tests/test_forecast_dependency_admission.py` (new) | P2 | test-only | none |
| **FL-5** | `DOC` | bind V1's learned members to the offline-refit admission path | `paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 | P2 | doc | — |
| **FL-6** | `DECISION` | `return_forecast` declined-vs-omitted; NCSA policy | owner | — | — | — |

**Ordering.** FL-1 and FL-2 land **together** (ground rule 7 — FL-2 is FL-1's first caller). FL-3 rides
FL-2. FL-4 is independent and may land first or last. FL-5 follows FL-4. FL-6 is asked, never assumed.

---

## 3. The admission rule (the declared table FL-4 enforces)

| Dependency | Verdict | Reason | Unblocked by |
|---|---|---|---|
| `statsforecast` | `CONDITIONAL` | V1's forecast pool is the only genuine gap; the block is a **vendor state vector**, not a library. Offline refit only. | V1's vendor decision |
| `mlforecast` | `CONDITIONAL` | V1's learned members. Brings `scikit-learn` **and `optuna`**. | V1's vendor decision |
| `arch` | `REJECT` | `volatility_models.garch11_fit` is already the GARCH producer (with an IGARCH guard). NCSA licence. | — |
| `statsmodels` | `REJECT` | Arrives transitively with `statsforecast`; duplicates `regime`/`covariance_models` surface. | — |
| `hmmlearn` | `REJECT` | `regime.hmm_filtered_regime` already produces the regime label and feeds `book_risk`. | — |
| `ruptures` | `REJECT` | `regime.spectral_change_read` + `complexity.py` own the change-point surface. | — |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | `REJECT` | No declared consumer; large compiled/torch deps. | new hypothesis naming a producer |
| `pymc`, `pyro`, `tensorflow-probability` | `REJECT` | No declared consumer; `conformal.py` supplies calibrated intervals. | ditto |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | `REJECT` | Code and checkpoint licences differ; weights + GPU; 2607.12248 is a warning about this class. | ditto |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | `REJECT` | Agreed with the proposal's own Tier 4. | — |
| `qlib`, `finrl` | `ALREADY OWNED` | Existing design+plan pairs in `docs/`. | — |

**Today's net change: zero.** `pyproject.toml` gains no forecasting extra.

---

## 4. Gates

**None.** No `enable_*` key is added, so `docs/gate_registry.md`, `.env.example` and
`tests/test_gate_env_toggles.py` are untouched. This is deliberate: the contract is a declaration read by
producers that are *already* gated individually (`enable_long_memory`, `enable_jump_robust_proxies`,
`enable_hmm_heavy_tails`, `enable_bootstrap_intervals`, …). Adding a gate over a manifest would gate a
list, not a computation.

---

## 5. Dependencies and ordering

```
FL-4 (admission test)  ──► FL-5 (bind V1)
FL-1 (declaration) ──► FL-2 (registry) ──► FL-3 (declined return)
                             │
                             └── reads the producers owned by:
                                 volat doc V1/V2/V6 · regime doc R2 · honesty doc H11
```

**Hard prerequisites.** None from other themes. The registry **reads no** producer at import time — it
names symbols; FL-2's resolution test imports them at test time only, so this plan cannot deadlock on
V1 (which is blocked) or on any other theme's phase.

**Cross-theme rule.** This plan must not restate any item owned by another doc. FL-5 is the only place
this plan touches V1, and it adds a bind rather than an item.

---

## 6. Tests and acceptance

| Test | Proves | Mutation that must fail it by name |
|---|---|---|
| `test_forecast_contract.py::test_a_refusal_cannot_carry_a_zero` | `value is None` iff `status != "ok"` | admit `0.0` with `status="unavailable"` |
| `test_forecast_contract.py::test_an_interval_must_declare_its_realized_coverage` | rule 4 of §6.2 | drop `realized_coverage` from the validator |
| `test_forecast_registry.py::test_no_key_has_two_producers` | invariant 8 for forecasts | point one key at two producers |
| `test_forecast_registry.py::test_every_declared_producer_symbol_exists` | the registry cannot drift | rename a declared producer symbol |
| `test_forecast_registry.py::test_return_forecast_is_declined_with_a_reason` | the refusal is cited | empty the reason |
| `test_forecast_dependency_admission.py::test_a_new_forecasting_extra_requires_a_verdict` | the admission rule | append an unlisted extra to the fixture |
| `tests/test_calc_agent_wiring.py` (existing) | FL-1's symbol has a real caller | — |

**Suite impact.** Six new tests, all offline, all sub-second. No vendor call, no network, no GPU.

---

## 7. Definition of done

1. `strategies/forecast_contract.py` and `strategies/forecast_registry.py` exist; every public symbol has
   a caller outside its own module (`test_calc_agent_wiring.py` green).
2. The registry declares every forecast-like number the engine emits today, each resolving to exactly one
   existing symbol, with the seed set from `design_forecasting_libraries.md` §5.2.
3. `return.*` is declared `declined` with a reason that cites the design doc.
4. The admission test passes against the real `pyproject.toml` (which gains no extra) and fails against
   a fixture with an unlisted extra.
5. `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 names its admission path.
6. `docs/AGENT_ONBOARDING.md`'s changelog, `CHANGELOG.md` and the `docs/MASTER_DESIGN.md` §19.4 doc list
   are updated in the same pass (rule 9).
7. `py -3.12 -m ruff check .` clean; the affected suites and the full suite run with
   `--session-timeout=5400`.

---

## 8. Risks

1. **The registry becoming a second place a number is *described*.** Mitigated by FL-2 declaring
   `producer` as a symbol path and *resolving* it in a test: a description with no producer fails.
2. **Over-reach into other themes' ownership.** Mitigated by §5's cross-theme rule and FL-5 being a bind.
   Any registry row for a key owned by another doc must cite that doc's item id, not restate it.
3. **`test_calc_agent_wiring.py` whitelist temptation.** FL-1 must NOT be whitelisted; it must have a
   real caller (FL-2). A whitelist entry would be the exact "a pure function that never reaches the tool
   loop is incomplete work" failure rule 1 names.
4. **Scope creep into building a forecast engine.** The plan builds a declaration, a registry, a refusal
   and a test. If a reviewer finds a `vol_forecast_pool` in this theme's diff, this plan has failed.
5. **Anchor drift, which this work already found.** While writing the design doc, the two `docs/paper_survey_26/`
   "verified" tables were found to have drifted (`design_vol_surface_and_vrp.md` §2: eight of ten rows;
   `design_cross_section_and_allocation.md` §2: eight rows), and `design_vol_surface_and_vrp.md` §3 still
   described V2/V3/V4/V5/V6 as open gaps after all five had shipped. Both were corrected in this pass.
   FL-2's symbol-resolution test is the structural fix for the same failure mode inside the new surface.

---

## 9. Honest limits

1. **No dependency is admitted, so nothing here is validated by a library run.** The plan's claims are
   architectural and testable in-tree.
2. **FL-4 tests the process, not the verdicts.** A wrong `REJECT` still passes.
3. **The registry is seeded from a doc table**, so it inherits the doc's coverage. A forecast number the
   engine emits but nobody noticed is not in the registry until FL-2's completeness test is extended —
   the first pass is a seed, not a proof of completeness.
4. **`return_forecast` stays declined until the evidence changes.** Nothing in this plan makes it easy to
   reverse, which is the intent (design doc §9.1) — and if the owner prefers omission over a declined
   row, FL-3 is deleted, not rewritten.
