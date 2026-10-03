# Implementation Plan — The Forecasting Layer (companion to `docs/design_forecasting_libraries.md`)

**Status:** PLAN — nothing built. **Zero dependencies are admitted by this plan as written.** FL-1…FL-6
are the contract, the registry, the refusal rows, the admission test, the ledger wiring and the benchmark
declaration. FL-7 is a policy bind; FL-8 is an owner decision.
**Version:** 1.1 (revises v1.0, 2026-10-03)
**Date:** 2026-10-03
**Parent design:** [`design_forecasting_libraries.md`](design_forecasting_libraries.md) (v1.1)
**Parent survey:** [`design_fin_paper_survey_26.md`](design_fin_paper_survey_26.md)
**Ground rules:** the eight inherited rules in [`paper_survey_26/README.md`](paper_survey_26/README.md) §1,
`docs/AGENT_ONBOARDING.md` §0, `MASTER_DESIGN.md` §2's eight invariants, and the design doc's **FD-1**
admission invariant (§3).
**Items:** FL-1…FL-4 (WORK, P1), FL-5/FL-6 (WORK, P2), FL-7 (DOC, P2), FL-8 (DECISION).
**Gates added:** **none.** Every artifact here is an always-on, read-only declaration or a test. The
producers it reads are each already individually gated; a gate over a manifest would gate a list.

---

## 0. Scope

The design doc's verdict is that the evaluated proposal's model families are already owned (§5.4, §6) and
that its one useful contribution is the **ForecastContract** shape (§7). This plan builds that and only
that:

- a **declaration** carrying target, definition, frequency, horizon, origin, status, machine-readable
  refusal code, production-time interval, provenance and a **post-hoc** evaluation block;
- a **registry** declaring one producer per `(key, frequency, horizon)`, with a symbol-resolution test;
- **visible refusals** for `absolute_return` and `return_rank`, as `declined` rows with reason codes;
- an **evidence-based admission test** — a capability gap alone never admits a dependency;
- the **ledger wiring** from contract to realized outcome to the honesty gates;
- a **benchmark declaration** per forecast family.

### The inherited rules that bind this theme

1. **Ground rule 2 / invariant 8 — one producer per derived quantity.** FL-2 exists only to enforce it.
2. **Ground rule 3 — no item adds a member to `COMPOSITE_ENGINES`** (stays
   `(fundamental, technical, regime, risk)`).
3. **Ground rule 4 — coverage travels with the number.** Every record carries window, `padded` and the
   imputation counts.
4. **Ground rule 7 — each new public symbol ships with its first caller in the same commit.** FL-1 lands
   with FL-2.
5. **Ground rule 8 — nothing here may be called from `prepare_initial_state`, `finalize_run`, or any agent
   tool.**
6. **FD-1** (design doc §3) — admission requires all five clauses **and** a benchmarked incremental value.

**Rule-4 impact: none.** No tool, gate, config key, report key or screener column.

---

## 1. Item cards

### FL-1 — The `ForecastRecord` declaration

**Target.** New `strategies/forecast_contract.py`: the §7.1 shape as a frozen dataclass (or validated
mapping) plus one validator.

**Behaviour.** Enforces at construction, not by documentation:

- `value is None` **iff** `status != "ok"` — a refusal can never carry `0.0`;
- `status == "unavailable"` **or** `"declined"` requires a non-empty `reason_code` **from the closed
  vocabulary** (`INSUFFICIENT_HISTORY`, `MISSING_VENDOR_SERIES`, `MODEL_FIT_FAILURE`, `COVERAGE_FAILURE`,
  `GATE_OFF` for `unavailable`; `RETURN_LEVEL_NOT_ADMITTED`, `RETURN_RANK_NOT_ADMITTED`,
  `TARGET_NOT_ADMITTED` for `declined`);
- `horizon >= 1` — **a state read is not a forecast** (design doc §7.2 rule 6, a v1.0 error);
- `target.name` / `target.definition` / `target.unit` / `frequency` are required and non-empty;
- `interval`, when present, carries `nominal_coverage` and `method` — and **never** `realized_coverage`,
  which is post-hoc (design doc §7.2 rule 5);
- the `evaluation` block is **declared but not required to be populated** at construction: `evaluated`
  defaults `False`.

**First caller.** `forecast_registry` (FL-2) — without it the symbol has no caller and
`tests/test_calc_agent_wiring.py` fails it by design.

**Phase / run mode.** P1 / in-run, pure, allocation-free, no I/O.

**Gate.** none.

**Failing-first tests.** `test_a_refusal_cannot_carry_a_zero`;
`test_a_state_read_is_not_a_forecast` (constructing `horizon=0` must fail by name);
`test_the_interval_carries_no_realized_coverage` (the production/evaluation split).

**Acceptance.** A record with `status="unavailable"` and `value=0.0` raises; the same record with
`value=None` and a valid code constructs and round-trips; `horizon=0` raises; an `interval` carrying
`realized_coverage` raises; an unknown `reason_code` raises; `padded` is required with no default.

**Depends on.** nothing.

**Doc caveat.** This is a **declaration**, not a calculator — it has no analytic claim, so it correctly
gets **no `@tool`** and **no prompt line** (design doc §2, §7.4). FL-2 is its real caller.

### FL-2 — The forecast registry and the second-producer gate

**Target.** New `strategies/forecast_registry.py`: one declared mapping
`(key, frequency, horizon) -> {target, unit, producer, gate, status}`.

**Behaviour.** A manifest. It reads no config and computes nothing. Seeded from the design doc §6.1's
verified table, with **separated** keys (`realized_volatility` @ `1d`/`1`, not `rv.d1`):
`realized_volatility` ← `strategies/long_memory.py::rv_forecast` (gate `enable_long_memory`);
`memory_parameter` ← `::memory_parameter` (same gate); `jump_share` ←
`volatility_models.py::bipower_proxy` (gate `enable_jump_robust_proxies`); `regime_stress_probability` ←
`regime.py` (gate `enable_hmm_heavy_tails`); plus the conformal interval axis and the declined return
families (FL-3).

**First caller.** the report/run-card writer that lists declared forecast keys beside the score engines —
the registry must be *reachable*, not merely present (ground rule 7) — plus its own tests.

**Phase / run mode.** P1 / in-run, pure.

**Failing-first tests.** `test_no_key_has_two_producers` (mutation: point one key at two producers);
`test_every_declared_producer_symbol_exists` (resolves each `producer` via `importlib`; mutation: rename
a producer symbol) — this is the structural fix for the anchor-drift defect found while writing v1.0
(§8.5); `test_no_state_reads_in_the_registry` (every row has `horizon >= 1`).

**Acceptance.** Every row resolves to exactly one existing symbol; renaming a producer fails the suite
with the key and missing path named; the registry imports no vendor and no optional dependency.

### FL-3 — `absolute_return` and `return_rank` ship as `declined`

**Target.** Two `declined` rows in FL-2's registry, each with its reason code and citation.

**Behaviour.** `absolute_return` carries `RETURN_LEVEL_NOT_ADMITTED` and cites Hjalmarsson (2006) and
Goyal/Welch/Zafirov (2021/2024). `return_rank` carries `RETURN_RANK_NOT_ADMITTED` and cites 2607.27461's
0.007 log-likelihood gain against the volatility rank's 0.108. **Neither produces a number, ever, and
neither states a universal claim** — they record that *this engine has not authorized* the target (design
doc §5.1).

**Phase / run mode.** P1 / in-run, pure.

**Gate.** none.

**Failing-first test.** `test_return_targets_are_declined_with_codes` — mutation: empty the reason code,
which must fail by name.

**Acceptance.** Both rows exist with valid codes and non-empty detail; nothing in `strategies/` computes
an absolute return forecast.

### FL-4 — The dependency-admission test

**Target.** The declared table from the design doc §9 (in this plan, §3) plus
`tests/test_forecast_dependency_admission.py`, which parses `pyproject.toml`'s optional-dependency groups.

**Behaviour.** Any forecasting-related extra must appear in the table with a **verdict**, a **categorized
reason**, and — for `CONDITIONAL` — (a) the FD-1 clauses it satisfies and (b) the **benchmark record** that
would admit it. A new extra with no row fails. **A capability gap alone is explicitly insufficient**:
the test asserts a `CONDITIONAL` row names a benchmark, not merely a missing package (design doc §3, §8.2).

**Phase / run mode.** P2 / test-only, offline.

**Failing-first test.** The test against a temp fixture with an unlisted extra, and against a second
fixture where a `CONDITIONAL` row omits its benchmark.

**Acceptance.** Both fixtures fail; the real `pyproject.toml` passes with **zero** forecasting extras.

**Doc caveat.** It enforces the *process*, not the *judgement* — a wrong verdict still passes.

### FL-5 — ForecastContract → prediction ledger → evaluation gates

**Target.** The wiring in the design doc §8.1: a thin adapter that writes a produced `ForecastRecord` into
`strategies/prediction_ledger.py` and, when the outcome resolves, fills the record's `evaluation` block.

**Behaviour.** One-way: **the ledger scores the producer; the producer never scores itself.** The adapter
carries the §8.2 `benchmark_ref` and `scoring_rule` so the ledger can record `benchmark_delta` without the
producer asserting it. It reads `enable_trial_ledger` (H1) and the H-theme's materiality verdict — it does
not re-implement either.

**Phase / run mode.** P2 / in-run write, offline read.

**Failing-first test.** `test_the_producer_cannot_populate_its_own_evaluation` — mutation: let the producer
set `realized_coverage`, which must fail by name.

**Acceptance.** A produced record lands in the ledger with `evaluated=False`; after the outcome resolves, the
ledger fills `realized_coverage` / `n_observations` / `benchmark_delta`; the producer path has no write
access to `evaluation`.

**Depends on.** FL-1, FL-2.

### FL-6 — The benchmark declaration per forecast family

**Target.** A declared table (design doc §8.2) and a test that every non-`declined` registry row names a
benchmark from it.

**Behaviour.** `volatility`/`variance` → HAR-RV + naive trailing realized vol (GARCH as a third reference);
`absolute_return` → historical mean / zero; `relative_return`/`residual_return` → factor/rank baseline;
ranks → persistence; `regime_probability` → sticky Markov; any `interval` → `conformal.iid_interval` as the
floor. Also binds `2602.07841`'s out-of-sample R² ceiling and H4's base-rate ceiling to any directional
claim.

**Phase / run mode.** P2 / in-run declaration + test.

**Failing-first test.** `test_every_admitted_forecast_names_a_benchmark` — mutation: add a registry row with
no benchmark.

**Depends on.** FL-2.

### FL-7 — Bind V1's learned members to the offline-refit mechanism

**Target.** A paragraph in `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md`'s V1 card
(the item's owner), pointing at FD-1 and FL-4.

**Behaviour.** Records that if V1 unblocks and its learned members (`GRU`, `XGBoost`) are not expressible
with the in-house regressions, the dependency enters as a **versioned offline refit artefact** under ground
rule 8 — never as a live call from the decision path — and only after clearing FD-1 and a §8.2 benchmark.

**Phase / run mode.** P2 / doc.

**Acceptance.** V1's card names its admission path; this plan does not restate V1's content.

### FL-8 — Owner decisions

Design doc §11: whether the return families ship `declined` or omitted (recommend `declined`), and whether
the dependency policy is permissive-OSI-only. Neither blocks FL-1…FL-7.

---

## 2. Item table

| id | kind | item | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|---|
| **FL-1** | `WORK` | `ForecastRecord` + validator (§7.1 shape) | `strategies/forecast_contract.py` (new) | P1 | in-run, pure | none |
| **FL-2** | `WORK` | forecast registry + no-two-producers + symbol resolution | `strategies/forecast_registry.py` (new) | P1 | in-run, pure | none |
| **FL-3** | `WORK` | `absolute_return` / `return_rank` declared `declined` + codes | FL-2's registry | P1 | in-run, pure | none |
| **FL-4** | `WORK` | dependency-admission test (verdict + reason + benchmark) | `tests/test_forecast_dependency_admission.py` (new) | P2 | test-only | none |
| **FL-5** | `WORK` | contract → prediction ledger → evaluation gates | `strategies/prediction_ledger.py` (+ adapter) | P2 | in-run write | none |
| **FL-6** | `WORK` | benchmark declaration per family + enforcement | FL-2's registry + `tests/` | P2 | in-run + test | none |
| **FL-7** | `DOC` | bind V1's learned members to the offline-refit path | `paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 | P2 | doc | — |
| **FL-8** | `DECISION` | declined-vs-omitted; dependency-licence policy | owner | — | — | — |

**Ordering.** FL-1 + FL-2 land together (ground rule 7). FL-3 rides FL-2. FL-4 and FL-6 are independent.
FL-5 needs FL-1/FL-2. FL-7 follows FL-4. FL-8 is asked, never assumed.

---

## 3. The admission table (what FL-4 enforces)

| Dependency | Verdict | Categorized reason | Admitted by |
|---|---|---|---|
| `statsforecast` | `CONDITIONAL` | FD-1 cl.1–2 met for V1 only; cl.3 pending | V1 unblocked **and** a `CONDITIONAL` benchmark row exists |
| `mlforecast` | `CONDITIONAL` | same; the learned-member source | same |
| `arch` | `REJECT_DUPLICATE` | `garch11_fit` owns GARCH (cl.5) | new evidence of numerical necessity |
| `statsmodels` | `REJECT_DIRECT` | existing surface; transitive via `statsforecast` | — |
| `hmmlearn` | `REJECT_DUPLICATE` | `hmm_filtered_regime` feeds `book_risk` | — |
| `ruptures` | `REJECT_DUPLICATE` | `cusum` + `bocpd` + `spectral_change_read` | — |
| `darts`, `neuralforecast`, `gluonts`, `pytorch-forecasting`, `autogluon-timeseries` | `REJECT_NO_CONSUMER` | no declared producer | a hypothesis naming a producer |
| `pymc`, `pyro`, `tensorflow-probability` | `REJECT_NO_CONSUMER` | no declared probabilistic producer | ditto |
| `chronos`, `timesfm`, `moirai`/`uni2ts`, `lag-llama`, `moment` | `REJECT_THIS_PASS` | no consumer + no demonstrated value; licence/checkpoint/hardware/leakage review required | that review + a benchmark |
| `prophet`, `pyaf`, `greykite`, `kats`, `pyflux` | `REJECT_NO_RESEARCH_CASE` | no research case | — |
| `qlib`, `finrl` | `ALREADY_OWNED` | existing design+plan pairs | — |

**Today's net change: zero.** `pyproject.toml` gains no forecasting extra.

---

## 4. Gates

**None.** No `enable_*` key is added, so `docs/gate_registry.md`, `.env.example` and
`tests/test_gate_env_toggles.py` are untouched.

---

## 5. Dependencies and ordering

```
FL-4 (admission) ──► FL-7 (bind V1)          FL-6 (benchmarks) ──┐
FL-1 (contract) ──► FL-2 (registry) ──► FL-3 (declined rows)     ├──► FL-5 (ledger wiring)
                                          └──────────────────────┘
                          reads producers owned by:
                          volat doc V1/V2/V6 · regime doc R2 · honesty doc H1/H4/H5/H10/H11
```

**Hard prerequisites.** None from other themes. The registry names symbols and computes nothing; FL-2's
resolution test imports them at test time only — so this plan cannot deadlock on V1 (blocked) or on any
other theme's phase.

**Cross-theme rule.** Any registry row for a key owned by another doc must cite that doc's item id, never
restate it. FL-7 is the only place this plan touches V1, and it adds a bind.

---

## 6. Tests and acceptance

| Test | Proves | Mutation that must fail it by name |
|---|---|---|
| `test_a_refusal_cannot_carry_a_zero` | `value is None` iff `status != "ok"` | admit `0.0` with `status="unavailable"` |
| `test_a_state_read_is_not_a_forecast` | §7.2 rule 6 | accept `horizon=0` |
| `test_the_interval_carries_no_realized_coverage` | production ≠ evaluation | add `realized_coverage` to `interval` |
| `test_a_non_ok_row_carries_a_closed_vocabulary_code` | §7.2 rule 4 | accept free prose as the code |
| `test_no_key_has_two_producers` | invariant 8 for forecasts | point one key at two producers |
| `test_every_declared_producer_symbol_exists` | the registry cannot drift | rename a producer symbol |
| `test_return_targets_are_declined_with_codes` | the refusal is cited | empty the code |
| `test_every_admitted_forecast_names_a_benchmark` | §8.2 | add a row with no benchmark |
| `test_the_producer_cannot_populate_its_own_evaluation` | §8.1 one-way | let the producer set coverage |
| `test_a_new_forecasting_extra_requires_a_verdict` | FL-4 | append an unlisted extra |
| `test_a_conditional_row_must_name_its_benchmark` | evidence-based admission | strip the benchmark |
| `tests/test_calc_agent_wiring.py` (existing) | FL-1 has a real caller | — |

**Suite impact.** Eleven new tests, all offline, sub-second. No vendor call, no network, no GPU.

---

## 7. Definition of done

1. `strategies/forecast_contract.py` and `strategies/forecast_registry.py` exist; every public symbol has a
   caller outside its own module.
2. The registry declares every forecast-like number the engine emits today, each resolving to exactly one
   existing symbol, keys/horizons separated per design doc §7.3.
3. `absolute_return` and `return_rank` are `declined` with codes that cite the design doc — and neither
   states a universal claim about markets.
4. The admission test passes against the real `pyproject.toml` (no extra) and fails against both fixtures.
5. The ledger wiring records `evaluated=False` on creation and fills `evaluation` only from the ledger.
6. `docs/paper_survey_26/implementation_plan_vol_surface_and_vrp.md` §V1 names its admission path.
7. `docs/AGENT_ONBOARDING.md`'s changelog, `CHANGELOG.md`, `README.md` and `MASTER_DESIGN.md` §19.4 are
   updated in the same pass (rule 9).
8. `py -3.12 -m ruff check .` clean; affected suites then the full suite with `--session-timeout=5400`.

---

## 8. Risks

1. **The registry becoming a second place a number is *described*.** Mitigated: `producer` is a symbol
   path, **resolved in a test** — a description with no producer fails.
2. **Over-reach into other themes.** Mitigated by §5's cross-theme rule.
3. **`test_calc_agent_wiring.py` whitelist temptation.** FL-1 must have a real caller, never a whitelist
   entry — a whitelist would be the exact "pure function that never reaches the tool loop is incomplete
   work" failure rule 1 names.
4. **Scope creep into building a forecast engine.** If a reviewer finds a `vol_forecast_pool` in this
   theme's diff, this plan has failed.
5. **Anchor drift — already found and fixed once.** While writing v1.0, two `docs/paper_survey_26/`
   "verified" tables were found to have drifted (`design_vol_surface_and_vrp.md` §2: eight of ten rows;
   `design_cross_section_and_allocation.md` §2: eight rows), and `design_vol_surface_and_vrp.md` §3 still
   described V2–V6 as open gaps after all five had shipped. Corrected in the v1.0 pass. FL-2's
   symbol-resolution test is the structural fix for the same failure mode inside the new surface.
6. **The contract ossifying into a bureaucracy** — eleven required fields on a number. Mitigated by FL-1's
   rule that `evaluation` is declared but unpopulated at creation, and by the contract accepting a plain
   mapping so a small producer is not forced through a heavy constructor.

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
