# Implementation Plan — The Forecasting Layer (companion to `docs/design_forecasting_libraries.md`)

**Status:** PLAN — nothing built. Executes against the parent design **frozen at v1.2** (its §11.0); no item
here may change FD-1, the contract's semantics, or authoritative ownership. **Zero dependencies are admitted
by this plan as written.** FL-1…FL-6 are
the contract, the registry, the refusal rows, the admission test, the ledger wiring and the benchmark
declaration. FL-7 is a policy bind; FL-8 is an owner decision.
**Version:** 1.2 (revises v1.1 and v1.0, 2026-10-03)
**Date:** 2026-10-03
**Parent design:** [`design_forecasting_libraries.md`](design_forecasting_libraries.md) (v1.2)
**Parent survey:** [`design_fin_paper_survey_26.md`](design_fin_paper_survey_26.md)
**Ground rules:** the eight inherited rules in [`paper_survey_26/README.md`](paper_survey_26/README.md) §1,
`docs/AGENT_ONBOARDING.md` §0, `MASTER_DESIGN.md` §2's eight invariants, and the design doc's **FD-1**
(§3) with its **candidate-output exemption** (§3.2).
**Items:** FL-1…FL-4 (WORK, P1), FL-5/FL-6 (WORK, P2), FL-7 (DOC, P2), FL-8 (DECISION).
**Gates added:** **none.** Every artifact is an always-on, read-only declaration or a test.

---

## 0. Scope

The design doc's verdict is that the evaluated proposal's model families are already owned (§5.4, §6) and
that its one useful contribution is the **ForecastContract** shape (§7). This plan builds that and only
that:

- **three record types, two of them immutable** — `CandidateForecast` (a pool member, never authoritative),
  `ForecastRecord` (production-time immutable), `ForecastEvaluation` (post-hoc immutable, appended by the
  ledger);
- a **registry** declaring one **authoritative** producer per
  `(target.name, entity_scope, frequency, horizon_steps)`, with candidate members explicitly exempt;
- **visible refusals** for `absolute_return` and `return_rank` as `declined` rows with reason codes;
- an **evidence-based admission test** — a capability gap alone never admits a dependency — plus the
  licence-tier policy;
- the **ledger wiring** that produces `ForecastEvaluation`, one-way;
- a **benchmark declaration** per forecast family.

### The inherited rules that bind this theme

1. **Ground rule 2 / invariant 8 — one *authoritative* producer per derived quantity.** FL-2 enforces it;
   §3.2 of the design doc is what makes a pool legal under it.
2. **Ground rule 3 — no item adds a member to `COMPOSITE_ENGINES`.**
3. **Ground rule 4 — coverage travels with the number** (window, `padded`, imputation counts,
   `data_snapshot_id`).
4. **Ground rule 7 — each new public symbol ships with its first caller in the same commit.** FL-1 lands
   with FL-2.
5. **Ground rule 8 — nothing here may be called from `prepare_initial_state`, `finalize_run`, or any agent
   tool.** Design doc §9.1 makes the offline boundary explicit: a `CONDITIONAL` verdict is **refit-environment**
   admission, never a runtime dependency.
6. **FD-1** — all five clauses **plus** a benchmarked incremental value.
7. **The parent design is frozen at v1.2** (design §11.0). These items execute it; **none may alter FD-1, the
   contract's semantics, or authoritative ownership** — such a change is a design revision, not an FL item.

**Rule-4 impact: none.** No tool, gate, config key, report key or screener column.

---

## 1. Item cards

### FL-1 — The three record types

**Target.** New `strategies/forecast_contract.py`: `CandidateForecast`, `ForecastRecord` and
`ForecastEvaluation` in the §7.1 shapes, plus validators.

**Behaviour.** Enforced at construction, not by documentation:

- `value is None` **iff** `status != "ok"` — a refusal can never carry `0.0`;
- `status ∈ {ok, unavailable, declined}`; a non-`ok` row requires a **non-empty `reason_code` from the
  closed vocabulary** (`INSUFFICIENT_HISTORY`, `MISSING_VENDOR_SERIES`, `MODEL_FIT_FAILURE`,
  `COVERAGE_FAILURE`, `GATE_OFF`; `RETURN_LEVEL_NOT_ADMITTED`, `RETURN_RANK_NOT_ADMITTED`,
  `TARGET_NOT_ADMITTED`);
- **`horizon_steps >= 1`** — a state read is not a forecast (design doc §7.2 rule 6);
- `target.name` / `target.definition` / `target.definition_version` / `target.unit` / `entity_scope` /
  `frequency` / `horizon_steps` / `forecast_origin` are mandatory (§7.2 rule 7);
- **`interval` is all-or-nothing** — if present, `low`/`high`/`nominal_coverage`/`method` are mandatory;
  if absent, **no interval field may be populated**. `interval` can never carry `realized_coverage`
  (§7.2 rule 5);
- **`ForecastEvaluation` is a distinct type** and is **not constructible with a producer** — its writer is
  the ledger (FL-5). `ForecastRecord` has **no** `evaluation` field at all: that is the P0 fix, and it is
  what makes the immutability claim true rather than aspirational;
- `producer_id` and `implementation_ref` are both required and are **different fields** (§7.2 rule 8).

**First caller.** `forecast_registry` (FL-2) — without it the symbols have no caller and
`tests/test_calc_agent_wiring.py` fails them by design.

**Phase / run mode.** P1 / in-run, pure, allocation-free, no I/O.

**Gate.** none.

**Failing-first tests.**
`test_a_refusal_cannot_carry_a_zero`; `test_a_state_read_is_not_a_forecast` (constructing `horizon_steps=0`
must fail by name); `test_the_interval_is_all_or_nothing` (a partially populated interval must fail);
`test_the_interval_carries_no_realized_coverage`; `test_a_forecast_record_has_no_evaluation_field` (the
attribute must not exist — asserts the split structurally, not by convention);
`test_a_producer_cannot_construct_a_forecast_evaluation`.

**Acceptance.** A record with `status="unavailable"` and `value=0.0` raises; `horizon_steps=0` raises; an
unknown `reason_code` raises; `padded`, `data_snapshot_id` and `calendar_id` are required with no default;
`ForecastRecord` exposes no mutable evaluation surface.

**Depends on.** nothing.

**Doc caveat.** A **declaration**, not a calculator — no analytic claim, so **no `@tool`** and **no prompt
line** (design doc §2, §7.4). FL-2 is its real caller.

### FL-2 — The forecast registry and the authoritative-producer gate

**Target.** New `strategies/forecast_registry.py`: one declared mapping
`(target.name, entity_scope, frequency, horizon_steps) -> {unit, producer_id, implementation_ref, gate, status}`.

**Behaviour.** A manifest. It reads no config and computes nothing. Seeded from the design doc §6.1's
verified table, with **separated** keys and an explicit scope:
`realized_volatility · single_asset · 1d · 1` ← `strategies/long_memory.py::rv_forecast` (gate
`enable_long_memory`); `memory_parameter` ← `::memory_parameter`; `jump_share` ←
`volatility_models.py::bipower_proxy` (gate `enable_jump_robust_proxies`); `regime_stress_probability ·
index · 1d · 5` ← `regime.py` (gate `enable_hmm_heavy_tails`); plus the conformal interval axis and the
declined return families (FL-3).

**First caller.** the report/run-card writer that lists declared forecast keys beside the score engines —
the registry must be *reachable*, not merely present (ground rule 7) — plus its own tests.

**Phase / run mode.** P1 / in-run, pure.

**Failing-first tests.** `test_no_key_has_two_authoritative_producers` (mutation: point one key at two);
`test_candidate_members_do_not_collide_with_the_registry` (a pool's members must register as *candidates*
and must not trip the uniqueness gate — this is the FD-1 §3.2 exemption made executable);
`test_every_declared_implementation_ref_resolves` (resolves each `implementation_ref` via `importlib`;
mutation: rename a symbol); `test_every_producer_id_is_stable_and_not_a_code_path` (a `producer_id`
containing `.py` or `::` fails).

**Acceptance.** Every row resolves to exactly one existing symbol; renaming a producer fails the suite with
the key and missing path named; the registry imports no vendor and no optional dependency.

### FL-3 — `absolute_return` and `return_rank` ship as `declined`

**Target.** Two `declined` rows in FL-2's registry, each with its reason code and citation.

**Behaviour.** `absolute_return` carries `RETURN_LEVEL_NOT_ADMITTED`, citing Hjalmarsson (2006) and
Goyal/Welch/Zafirov (2021/2024). `return_rank` carries `RETURN_RANK_NOT_ADMITTED`, citing 2607.27461's
0.007 log-likelihood gain against the volatility rank's 0.108. **Neither produces a number, ever, and
neither states a universal claim** — they record that *this engine has not authorized* the target.

**Phase / run mode.** P1 / in-run, pure.

**Gate.** none.

**Failing-first test.** `test_return_targets_are_declined_with_codes` — mutation: empty the reason code.

**Acceptance.** Both rows exist with valid codes and non-empty detail; nothing in `strategies/` computes an
absolute return forecast. **Owner-ratified 2026-10-03** (design doc §11.1) — this is acceptance, not an
option.

### FL-4 — The dependency-admission test and the licence tiers

**Target.** The declared table from the design doc §9 (plan §3) plus
`tests/test_forecast_dependency_admission.py`, parsing `pyproject.toml`'s optional-dependency groups.

**Behaviour.** Any forecasting-related extra must appear in the table with a **verdict**, a **categorized
reason**, and — for `CONDITIONAL` — (a) the FD-1 clauses it satisfies and (b) the **benchmark record** that
would admit it. **A capability gap alone is explicitly insufficient.** Additionally, the licence tier is
declared per row (design doc §11.3): `default` (MIT/BSD/Apache), `osi_review` (other OSI-approved
permissive, incl. NCSA), `custom_review` (non-OSI, custom and **model-checkpoint** licences).

**Phase / run mode.** P2 / test-only, offline.

**Failing-first tests.** `test_a_new_forecasting_extra_requires_a_verdict`;
`test_a_conditional_row_must_name_its_benchmark`;
`test_every_admitted_row_declares_a_licence_tier`.

**Acceptance.** All three fixtures fail; the real `pyproject.toml` passes with **zero** forecasting extras.

**Doc caveat.** It enforces the *process*, not the *judgement* — a wrong verdict still passes.

### FL-5 — Forecast contract → prediction ledger → ForecastEvaluation

**Target.** The wiring in the design doc §8.1: an adapter that writes a produced `ForecastRecord` into
`strategies/prediction_ledger.py` and, when the outcome resolves, appends a **separate `ForecastEvaluation`**
keyed by `forecast_id`.

**Behaviour.** One-way, and structurally so: the ledger is the **only** writer of `ForecastEvaluation`, and
`ForecastRecord` has no evaluation field to mutate (FL-1). The adapter carries `benchmark_ref` and
`scoring_rule` so the ledger can record `benchmark_delta` without the producer asserting it. It reads
`enable_trial_ledger` (H1) and the H-theme's materiality verdict; it re-implements neither.

**Phase / run mode.** P2 / in-run write, offline read.

**Failing-first tests.** `test_the_producer_cannot_populate_its_own_evaluation` (mutation: give the producer
a write path, which must fail by name); `test_the_record_is_unchanged_by_a_later_evaluation` (hash the
record before and after the evaluation is appended — the immutability invariant, made executable).

**Acceptance.** A produced record lands with no evaluation attached; after the outcome resolves an
`ForecastEvaluation` exists keyed to it; the original record is byte-identical afterwards; the producer path
has no write access.

**Depends on.** FL-1, FL-2.

### FL-6 — The benchmark declaration per forecast family

**Target.** A declared table (design doc §8.2) and a test that every non-`declined` registry row names a
benchmark from it.

**Behaviour.** `volatility`/`variance` → HAR-RV + naive trailing realized vol (GARCH as a third reference);
`absolute_return` → **zero-return**, **expanding historical mean** and **rolling historical mean** as three
distinct baselines; `relative_return`/`residual_return` → the applicable factor baseline;
`return_rank`/`volatility_rank` → **cross-sectional persistence** and a **rank-neutral / cross-sectional-mean**
baseline; `regime_probability` → sticky Markov; any `interval` → `conformal.iid_interval` as the floor.
Also binds `2602.07841`'s out-of-sample R² ceiling and H4's base-rate ceiling to any directional claim.

**Phase / run mode.** P2 / in-run declaration + test.

**Failing-first test.** `test_every_admitted_forecast_names_a_benchmark` — mutation: add a registry row with
no benchmark.

**Depends on.** FL-2.

### FL-7 — Bind V1's members to FD-1, including the unsupplied `-t`/FIGARCH members

**Target.** A paragraph in `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md`'s V1 card (the
item's owner), pointing at FD-1 and FL-4.

**Behaviour.** Records three things and decides none of them:

1. if V1 unblocks and its learned members (`GRU`, `XGBoost`) are not expressible with the in-house
   regressions, the dependency enters as a **versioned offline refit artefact** under ground rule 8 — never
   a live call from the decision path;
2. a pool's members are **candidates** under FD-1 §3.2 and cannot trip the one-producer rule;
3. **`GARCH(1,1)-t` and `FIGARCH(1,1)-t` have no confirmed supplier** — in-house `garch11_fit` is Gaussian
   (no t/skew/GED), `statsforecast` has neither a t option nor a FIGARCH class, and `arch` has Student's-t
   but lists FIGARCH only under *Contributing* (design doc §4.2). V1's owner must drop or re-scope them.

**Phase / run mode.** P2 / doc.

**Acceptance.** V1's card names its admission path; this plan does not restate V1's content.

### FL-8 — Owner decisions

Design doc §11: the licence-tier default (§11.3), `declined` vs `not_admitted` (§11.4, one constant), V1's
unsupplied members (§11.5) and V1's vendor unblock (§11.6). **None blocks implementation-plan execution.**
But a downstream decision that would change FD-1, the `ForecastContract`'s semantics, or authoritative
ownership is a **design revision**, not an FL item — it must return to the design doc as a numbered revision
(design §11.0).

---

## 2. Item table

| id | kind | item | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|---|
| **FL-1** | `WORK` | `CandidateForecast` / `ForecastRecord` / `ForecastEvaluation` | `strategies/forecast_contract.py` (new) | P1 | in-run, pure | none |
| **FL-2** | `WORK` | registry + authoritative-producer gate + candidate exemption | `strategies/forecast_registry.py` (new) | P1 | in-run, pure | none |
| **FL-3** | `WORK` | `absolute_return` / `return_rank` `declined` + codes | FL-2's registry | P1 | in-run, pure | none |
| **FL-4** | `WORK` | admission test + licence tiers | `tests/test_forecast_dependency_admission.py` (new) | P2 | test-only | none |
| **FL-5** | `WORK` | contract → ledger → `ForecastEvaluation` | `strategies/prediction_ledger.py` (+ adapter) | P2 | in-run write | none |
| **FL-6** | `WORK` | benchmark declaration per family + enforcement | FL-2's registry + `tests/` | P2 | in-run + test | none |
| **FL-7** | `DOC` | bind V1's members to FD-1; record the unsupplied `-t`/FIGARCH | `paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 | P2 | doc | — |
| **FL-8** | `DECISION` | licence tiers; `declined` vs `not_admitted`; V1 members; vendor unblock | owner | — | — | — |

**Ordering.** FL-1 + FL-2 land together (ground rule 7). FL-3 rides FL-2. FL-4 and FL-6 are independent.
FL-5 needs FL-1/FL-2. FL-7 follows FL-4.

---

## 3. The admission table (what FL-4 enforces)

| Dependency | Verdict | Categorized reason | Licence tier | Admitted by |
|---|---|---|---|---|
| `statsforecast` | `CONDITIONAL` | candidate classical forecasters for a declared pool; **not** the `-t`/FIGARCH source | `default` | V1 unblocked **and** a benchmark row exists |
| `mlforecast` | `CONDITIONAL` | candidate **tabular** learned members; not a neural framework | `default` | same |
| `arch` | `REJECT_DUPLICATE` | `garch11_fit` owns GARCH conditional variance (cl. 5) | `osi_review` (NCSA) | — |
| `statsmodels` | `REJECT_DIRECT` | existing surface; transitive via `statsforecast` | `default` | — |
| `hmmlearn` | `REJECT_DUPLICATE` | `hmm_filtered_regime` feeds `book_risk` | unverified | — |
| `ruptures` | `REJECT_DUPLICATE` | `cusum` + `bocpd` + `spectral_change_read` | unverified | — |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | `REJECT_NO_CONSUMER` | no declared producer | unverified | a hypothesis naming a producer |
| `pymc`, `pyro`, `tensorflow-probability` | `REJECT_NO_CONSUMER` | no declared probabilistic producer | unverified | ditto |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | `REJECT_THIS_PASS` | no consumer + no demonstrated value | `custom_review` (TimesFM 3.0 weights are non-commercial; Chronos is Apache-2.0) | that review + a benchmark |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | `REJECT_NO_RESEARCH_CASE` | no research case | unverified | — |
| `qlib`, `finrl` | `ALREADY_COVERED` | territory covered by existing design+plan pairs; **not** installed producers | `default` | — |

**Today's net change: zero.** `pyproject.toml` gains no forecasting extra.

---

## 4. Gates

**None.** No `enable_*` key is added, so `docs/gate_registry.md`, `.env.example` and
`tests/test_gate_env_toggles.py` are untouched.

---

## 5. Dependencies and ordering

```
FL-4 (admission + licence tiers) ──► FL-7 (bind V1)      FL-6 (benchmarks) ─┐
FL-1 (3 records) ──► FL-2 (registry) ──► FL-3 (declined)                  ├──► FL-5 (ledger → evaluation)
                                          └───────────────────────────────┘
                       reads producers owned by:
                       volat doc V1/V2/V6 · regime doc R2 · honesty doc H1/H4/H5/H10/H11
```

**Hard prerequisites.** None from other themes. The registry names symbols and computes nothing; FL-2's
resolution test imports them at test time only — so this plan cannot deadlock on V1 (blocked) or on any
other theme's phase.

**Cross-theme rule.** Any registry row for a key owned by another doc must cite that doc's item id, never
restate it. FL-7 is the only place this plan touches V1, and it adds a bind plus a recorded finding.

---

## 6. Tests and acceptance

| Test | Proves | Mutation that must fail it by name |
|---|---|---|
| `test_a_refusal_cannot_carry_a_zero` | `value is None` iff `status != "ok"` | admit `0.0` with `status="unavailable"` |
| `test_a_state_read_is_not_a_forecast` | §7.2 rule 6 | accept `horizon_steps=0` |
| `test_the_interval_is_all_or_nothing` | §7.2 rule 5 | populate `low` without `method` |
| `test_the_interval_carries_no_realized_coverage` | production ≠ evaluation | add `realized_coverage` to `interval` |
| `test_a_forecast_record_has_no_evaluation_field` | **the P0 split** | re-add an `evaluation` attribute |
| `test_a_producer_cannot_construct_a_forecast_evaluation` | §8.1 one-way | expose the evaluation writer |
| `test_the_record_is_unchanged_by_a_later_evaluation` | immutability | let the append mutate the record |
| `test_a_non_ok_row_carries_a_closed_vocabulary_code` | §7.2 rule 4 | accept free prose as the code |
| `test_no_key_has_two_authoritative_producers` | invariant 8 for forecasts | point one key at two producers |
| `test_candidate_members_do_not_collide_with_the_registry` | FD-1 §3.2 | register a pool member as authoritative |
| `test_every_declared_implementation_ref_resolves` | the registry cannot drift | rename a producer symbol |
| `test_every_producer_id_is_stable_and_not_a_code_path` | §7.2 rule 8 | use `a.py::f` as a `producer_id` |
| `test_return_targets_are_declined_with_codes` | the refusal is cited | empty the code |
| `test_every_admitted_forecast_names_a_benchmark` | §8.2 | add a row with no benchmark |
| `test_a_new_forecasting_extra_requires_a_verdict` | FL-4 | append an unlisted extra |
| `test_a_conditional_row_must_name_its_benchmark` | evidence-based admission | strip the benchmark |
| `test_every_admitted_row_declares_a_licence_tier` | §11.3 | drop the tier |
| `tests/test_calc_agent_wiring.py` (existing) | FL-1 has a real caller | — |

**Suite impact.** Seventeen new tests, all offline, sub-second. No vendor call, no network, no GPU.

---

## 7. Definition of done

1. `strategies/forecast_contract.py` and `strategies/forecast_registry.py` exist; every public symbol has a
   caller outside its own module.
2. The registry declares every forecast-like number the engine emits today, each resolving to exactly one
   existing symbol, with `(target.name, entity_scope, frequency, horizon_steps)` separated per design doc
   §7.3.
3. `ForecastRecord` carries **no** evaluation field; `ForecastEvaluation` is written only by the ledger.
4. `absolute_return` and `return_rank` are `declined` with codes that cite the design doc — and neither
   states a universal claim about markets.
5. The admission test passes against the real `pyproject.toml` (no extra) and fails against all three
   fixtures.
6. `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 names its admission path and the
   unsupplied `-t`/FIGARCH members.
7. `docs/AGENT_ONBOARDING.md`'s changelog, `CHANGELOG.md`, `README.md` and `MASTER_DESIGN.md` §19.4 are
   updated in the same pass (rule 9).
8. No item has changed FD-1, the `ForecastContract`'s semantics, or authoritative ownership without a
   design revision (design §11.0).
9. `py -3.12 -m ruff check .` clean; affected suites then the full suite with `--session-timeout=5400`.

---

## 8. Risks

1. **The registry becoming a second place a number is *described*.** Mitigated: `implementation_ref` is a
   symbol path, **resolved in a test**; `producer_id` is asserted not to look like a path.
2. **Over-reach into other themes.** Mitigated by §5's cross-theme rule.
3. **`test_calc_agent_wiring.py` whitelist temptation.** FL-1 must have a real caller, never a whitelist
   entry.
4. **Scope creep into building a forecast engine.** If a reviewer finds a `vol_forecast_pool` in this
   theme's diff, this plan has failed.
5. **Contract ossification.** The record is wide (target, scope, frequency, horizon, origin, interval,
   provenance, status). Mitigated by the design doc's separation of concerns — `ForecastEvaluation` is a
   *different object*, so the production record stays small — and by FL-1 accepting a plain mapping so a
   minimal producer is not forced through a heavy constructor.
6. **Anchor drift — already found and fixed once.** While writing v1.0, two `docs/paper_survey_26/`
   "verified" tables were found to have drifted (`design_vol_surface_and_vrp.md` §2: eight of ten rows;
   `design_cross_section_and_allocation.md` §2: eight rows), and `design_vol_surface_and_vrp.md` §3 still
   described V2–V6 as open gaps after all five had shipped. FL-2's resolution test is the structural fix.

---

## 9. Honest limits

1. **No dependency is admitted, so nothing here is validated by a library run.**
2. **FL-4 tests the process, not the verdicts.** A wrong `REJECT` still passes.
3. **The registry is seeded from a doc table**, so it inherits that table's coverage; the first pass is a
   seed, not a proof of completeness.
4. **`absolute_return` and `return_rank` stay declined until the evidence changes** — and §8.2 names the
   benchmark that would change it locally, so the refusal is testable rather than permanent.
5. **No library was evaluated for forecast quality on this engine's production universe** (design doc
   §13.1). Library capability is not evidence of financial usefulness.
6. **The `-t`/FIGARCH finding is a negative read of one ref on one day** (design doc §13.5); V1's owner
   should re-verify when the item unblocks.
