# Design: The metric authority registry — one canonical producer per measured metric

Status: **BUILT** (P1–P4 landed 2026-10-06: `strategies/metric_authority.py`,
`tests/test_metric_authority.py`, and the `enable_metric_authority` gate — which
ships **off**). This doc is the *design + implementation plan* for a **manifest
and one resolver**, not a new reconciliation engine; the as-built deviations from
the plan below are named at the end of §4.
**Rule-4 impact:** none for P1–P3 (a manifest plus one resolver; no tool, no gate,
no report key, no screener column). P4 names its own gate and takes the seven-point
registration surface.
**Owner decision on P4 (2026-10-05): approved.** `enable_metric_authority` ships
**off** and is a **fail-closed publication gate**, not a feature flag — off leaves
the existing publication path byte-identical, on makes any metric with no named,
registered producer publish `unavailable` (never a legacy value). See §4 for the
approved acceptance bar.
**Trigger (what this is answering):** three published defects observed in one
day's shallow batch, all the same class — **one metric, two published values, and
nothing in the pipeline to pick one**:
- **Two P/Es for one name.** The vendor's `trailingPE` (20.33, via
  `yfinance info`, rendered by `get_fundamentals`) and the engine's own
  `ratios.compute_ratios` `p_e` (30.01) are both published; they differ because the
  vendor's TTM EPS includes a quarter whose revenue/income rows the vendor panel
  leaves blank, so the engine's `trailing_twelve_months` cannot sum it.
- **Two entry ceilings in one report tree** (`reports/FNF_20260930_150041`: 38.17
  vs 40.68).
- **An unstable `cash` key.** The same run can resolve the canonical `cash` line to
  `CashAndCashEquivalents` (net debt **66,177M**) or to
  `CashCashEquivalentsAndShortTermInvestments` (net debt **29,960M**) with **no
  period change**.
The AMZN FCF defect (`79a1379`) is a *sibling* class — a positional `values[-1]`
pairing of two independently-sourced series — and is already fixed; it is not a
registry row and is noted in §6.

---

## 1. The invariant this enforces

`docs/MASTER_DESIGN.md` §2.1 **rule 8** — *"One producer per number. A given
quantity has exactly one function that computes it; every consumer reads that
result rather than re-deriving it."* The repo restated the same rule for derived
quantities as *"no derived quantity may have two independent authoritative
producers — a secondary implementation may be a fallback, a validation
cross-check or a diagnostic, but must not independently contribute to the same
composite."*

Rule 8 is **stated** and it is **enforced for forecasts** (`forecast_registry.py`,
§2). It is **not enforced for measured input metrics** — a price, a multiple, a
cash balance, a ceiling. This doc closes that gap, using the repo's own forecast
registry as the template rather than inventing a second mechanism.

---

## 2. What already exists (verified against the tree)

Taken first, because most of the machinery is here. **Every row was read at its
definition site, not recalled.**

| Instrument | Where | What it does | Why it is not the registry |
|---|---|---|---|
| **Forecast registry** | `strategies/forecast_registry.py` — `RegistryRow`, `FORECAST_REGISTRY`, `_module_and_attr`, `BENCHMARK_BY_FAMILY` | Declares **one AUTHORITATIVE producer per forecast key**. A row carries `producer_id` (a *stable semantic owner*, never a code path), `implementation_ref` (a *location*, `strategies/<mod>.py::<sym>`, resolved by a fixed transform), `gate`, `benchmark_ref`, `status` (`ok`/`declined`), and — for a refusal — `reason_code` + `citation`. `tests/test_forecast_registry.py` resolves every ref against the live tree, so a renamed symbol fails a build. | Covers **forecast keys** (`realized_volatility`, `regime_stress_probability`, …), not measured inputs. It is the exact shape to copy, and the proof the shape works here. |
| **Gather-time reconciliation** | `strategies/metric_reconcile.py` — `MATCH_TOLERANCE:30` (1%), `TOOL_METRIC_MAP:39`, `extract_metric_value:114`, `metric_for_tool:136`, `reconcile_metrics:139`, `render_reconcile:221` | Maps tool → **canonical metric id** so conflicting vendor values are *compared* (Market Cap / Market cap / marketCapitalization all feed `market_cap`), marks `CONFLICT` beyond 1%, renders the reconcile line into the evidence block. | It is the **reverse index with no authority column** — it names the metric id a tool feeds, never which producer is canonical. It surfaces a conflict to the analyst and leaves the choice to the LLM. |
| **Cross-vendor spread** | `strategies/data_quality.py:80` `disagreement_flag` | Given measured values of one metric across vendors, returns spread% and flags `DATA CONFLICT` **rather than silently trusting one vendor**. | Detection only; it has no opinion on which vendor wins. |
| **Report-side basis ledger** | `agents/utils/report_verifier.py` — `_basis_registry`, `basis_conflicts`, `report_ledger`, `_internal_conflicts` (~`:3519`, `:3548`, `:3777`, `:3841`, `:4212`) → `strategies/decision_packet.py:449` `_conflict_rows` (§9 CONFLICT ledger) | The typed `{metric, value, basis, source}` registry per stem, and the same-metric conflict scan that machines a `CONFLICT` row into the decision packet. | **Post-hoc and report-side.** It records what the analyst wrote and flags the disagreement; it cannot prevent the second value being produced. |
| **Deliberate non-reconciliation** | `strategies/regime_score.py:717` `_disagreement`; `strategies/sentiment_score.py:383` `_resolve_sources` | Two precedents for the right *refusal* behaviour: the regime paths ship an echo + a `disagree` flag with **no merge, no average, no precedence**; the sentiment tone legs **refuse** a mixed-scale source rather than average it. | They refuse *within one module*; there is no cross-module rule. |
| **Gate surface** | `docs/gate_registry.md`, `SHIPPED_DEFAULTS`, `_ENV_OVERRIDES`, `tests/test_gate_env_toggles.py` | The registration surface a *fail-closed* switch would use (§5 P4). | — |

**The gap, in one sentence:** the repo *detects* disagreement in four places and
*names one authority* for forecasts, but **no single manifest names the
authoritative producer of a measured metric** — so a report or a card can publish
either value, and the only thing that ever objects is a post-hoc verifier after
the number has already shipped.

---

## 3. The registry (shape)

Mirror `forecast_registry.RegistryRow` field-for-field, because it already encodes
rule 8 correctly. New module `tradingagents/strategies/metric_authority.py`:

```python
@dataclass(frozen=True, kw_only=True)
class MetricRow:
    metric: str                       # canonical id, e.g. "p_e"
    definition: str                   # the one-line meaning printed to a reader
    definition_version: str           # e.g. "p_e.v1" - a basis change is a version bump
    unit: str                         # "ratio" | "usd" | "usd_per_share" | ...
    status: str                       # "ok" | "declined"  (closed vocabulary)
    producer_id: str | None = None    # stable semantic owner - NEVER a code path
    implementation_ref: str | None = None  # "strategies/ratios.py::compute_ratios"
    basis: str | None = None          # the literal basis line the reader sees
    fallback: tuple[str, ...] = ()    # ordered implementation_refs; diagnostics
    tolerance_pct: float | None = None  # cross-check band; default METRIC_TOLERANCE_PCT
    gate: str | None = None
    reason_code: str | None = None    # declined only, closed vocabulary
    citation: str | None = None       # declined only
```

Constructor validation is copied from `RegistryRow.__post_init__` (a
`MetricAuthorityError` where that raises `ForecastRegistryError`):
- `status` in the closed vocabulary; a non-`ok` row carries `reason_code` +
  `citation`; a `declined` row carries **no** producer, gate or fallback
  (mirrors the forecast rule: *a cited refusal is a decision, an absent row is an
  invitation*);
- a non-declined row names **both** `producer_id` and `implementation_ref`, and
  `producer_id` is not a code path (`".py"`/`"::"` rejected);
- `implementation_ref` is `strategies/<module>.py::<symbol>`, validated by the
  **same `_module_and_attr` transform**, which is imported, not re-implemented
  (rule 8: one producer for the transform too);
- `gate`, when named, starts with `enable_`.

### 3.1 The resolver — where the refusal lives

```python
def resolve_metric(metric: str, *, values: dict[str, float] | None = None) -> dict:
    """The value, its declared producer, and its basis — or a refusal."""
```

Return shape: `{metric, status, value, producer_id, implementation_ref, basis,
spread_pct, conflicts}` with `status ∈ {ok, unavailable, conflict, unknown,
declined}` — the **same five-state discipline** the report verifier already uses
(`GROUNDED | UNSUPPORTED | CONTRADICTED | MISQUOTED | INTERNAL_CONFLICT`), and the
same `None ≠ 0` rule (`NA != 0` is a standing rule of this codebase; a refusal can
never carry `0.0`).

**Refusal semantics (the whole point):**
- **zero producers with a value** → `unavailable` — never `0`, never "pick one".
- **two or more with values** → the canonical is chosen by `implementation_ref`
  **identity**, not by position; a secondary producer whose value sits outside
  `tolerance_pct` of the canonical is reported as a `conflict` row **and the
  canonical is still named** — the number is published *with its basis*, and the
  disagreement is visible, never silently resolved (the `regime_score` /
  `disagreement_flag` precedent).
- **a metric named nowhere in the registry** → `MetricAuthorityError` at the
  registry's own test time, `unknown` at runtime — a *named absence*, not a guess.
- **a `declined` row** → `declined` + `reason_code` + `citation`.

---

## 4. Implementation plan

**P1 — the manifest and the resolver (new `strategies/metric_authority.py`).**
Copy `forecast_registry`'s construction and validation. Seed the **five numbers
first** — an explicit, small starting set, expanded only once those are stable
(the "five-number starting point" discipline, §7):
`price`, `p_e`, `cash`, `fcf`, `entry_ceiling`. New
`tests/test_metric_authority.py` **resolves every `implementation_ref` against the
live tree**, exactly as `test_forecast_registry.py` does — a renamed producer
fails a build, not a report.
*Rule 7:* `resolve_metric` ships with its caller in the same commit (P2 below).

**P2 — register the producers.** Each seed metric's canonical producer registers
a row: `ratios.compute_ratios` → `p_e`; the statement layer → `cash` and `fcf`;
the card's ceiling path → `entry_ceiling`; the price caliber
(`dataflows/market_router.py::price_caliber_for`) → `price`. This is where the
**unstable `cash` binding is ended**: the row names one tag, and the other binding
becomes a labelled `fallback`, not a coin-flip.

**P3 — wire the consumers.** `metric_reconcile` gains the authority column, so a
`CONFLICT` names the canonical instead of leaving the choice open;
`trade_plan.measured_inputs` resolves each input instead of taking whatever it
happened to compute; the report evidence block prints the row's `basis` line. The
report verifier's `_basis_registry` stays — it is the post-hoc check that the
producers' contract holds.

**P4 — the fail-closed gate (owner-approved 2026-10-05).** `enable_metric_authority`.
The gate is an **enforcement switch, not a feature flag**:

```text
gate OFF   ->  the existing metric-publication path, unchanged
               (byte-identical compatibility mode, rule 6)

gate ON    ->  metric has a named, registered producer   ->  publish normally
               metric has NO named, registered producer ->  publish `unavailable`
                                                           NEVER the computed value
```

"No named producer" means exactly that — it is **not** "use the best available
producer" and **not** "fall back to the legacy value". The **absence of authority
is itself the reason for `unavailable`**; falling back would defeat the
fail-closed purpose. A `declined` row (a cited refusal) fails closed the same way.

P4 is the **only phase that changes the publication contract**, and therefore the
only phase that takes the seven-point registration surface: `SHIPPED_DEFAULTS`; an
`_ENV_OVERRIDES` row; a `docs/gate_registry.md` row *with the enforcement site*; a
`tests/test_gate_env_toggles.py` `REGISTRY` entry; `.env.example`;
`docs/api_reference.md` §1.1 regenerated by `scripts/gen_api_reference_table.py
--write`; and the live `.env` (the deployment's actual setting). It moves
`docs/gate_registry.md:27`'s coverage count by **one**. P1–P3 add no gate and are
byte-identical while this is off.

**Acceptance bar (owner, 2026-10-05):** default **off**; off-path byte-identical;
on-path fails closed; an unnamed/unregistered metric cannot publish a value; a
named/registered metric keeps its normal value; the gate is represented
consistently across all seven registration locations; the registry coverage count
is updated; generated API documentation is regenerated rather than hand-edited;
the live `.env` reflects the owner's actual runtime setting.

**As built (2026-10-06).** The seed is the five numbers, each with the owner's
basis: `price` ← `dataflows/stockstats_utils.py::load_ohlcv` (the price **value**'s
producer — the plan's example named `price_caliber_for`, which produces the
*caliber*, not the number, so the row names the number's producer and records the
caliber in its `basis`); `p_e` ← `strategies/ratios.py::compute_ratios` (the
engine's basis, owner 2026-10-05; the vendor field is a labelled `fallback`);
`cash` ← `dataflows/statement_parsing.py::fetch_ticker` (tag
`CashAndCashEquivalents`); `fcf` ← `dataflows/statement_parsing.py::_add_derived_series`;
`entry_ceiling` ← `strategies/entry_ceiling.py::entry_ceiling` (§103's
`max_entry_price`). **P3 wired two consumers, both GATED so a gate-off path is
byte-identical:** `trade_plan.build_trade_plan` publishes its entry ceiling through
`resolve_metric("entry_ceiling")` (the two-ceilings fix), and
`metric_reconcile.reconcile_metrics` attaches the authority column with
`render_reconcile` naming the canonical on a conflict. **NOT wired:
`trade_plan.measured_inputs`** — its inputs (`technical_price` / `execution_spread`
/ `fair_value`) are not in the seed, and because the gate refuses any metric with
no named producer, wiring it today would suppress them. The rule that follows:
**a consumer may be wired only once the registry covers its whole metric
vocabulary** — the P2 expansion step (this is the §3/candidate-name mismatch the
plan did not resolve).

---

## 5. The four defects, mapped

| Defect | Registry action | Needs owner? |
|---|---|---|
| Two P/Es (20.33 vendor vs 30.01 engine) | Row `p_e`; canonical = the **engine** (`ratios.compute_ratios`), non-canonical = the vendor field as a labelled fallback/diagnostic. | **Yes** — which basis is canonical is a decision, not a fact (see §6, and the same question governs the two entry ceilings). |
| Two entry ceilings (FNF 38.17 vs 40.68) | Row `entry_ceiling`; one producer named. | **Yes.** |
| Unstable `cash` key (net debt 66,177M ↔ 29,960M) | Row `cash`; one tag named, the other a labelled fallback. | **Yes** — which tag. |
| AMZN FCF `values[-1]` pairing | **Not a registry row.** It is the *pairing* rule — fixed in `79a1379` (merge by period, not position). Recorded here because a registry that names one producer per metric does **not** fix a consumer that pairs two *different* metrics positionally. | No (done). |

---

## 6. The refusals are policy, not fact

The external practice is unambiguous that a golden source is **a rule, not a
vendor loyalty** — "choosing Vendor A over B does not make A correct, it just makes
the firm's own numbers consistent with each other." The registry makes the repo
*self-consistent*; it does not make either value *true*. That is why §5's three
rows are owner decisions and not cold fixes under onboarding rule 10: naming a
canonical basis **rewrites a decision contract**, and rule 10's carve-out applies.

---

## 7. Test plan

`tests/test_metric_authority.py` (new), shaped on `test_forecast_registry.py`:
1. **Every `implementation_ref` resolves** against the live tree.
2. **Two canonical producers for one metric raise** at construction.
3. **A `declined` row carries `reason_code` + `citation`, and nothing else.**
4. **`resolve_metric` refuses**: unknown metric → `unknown`; no value → `unavailable`
   (and `None`, never `0.0`).
5. **A conflicting secondary value flags `conflict` and still names the canonical.**
6. **`consumer == producer by construction`**: `resolve_metric("p_e")` and the
   report's basis row cannot disagree (the two-entry-ceilings defect class).
7. **Gate-off byte-identity.** With `enable_metric_authority=False` the publication
   path is byte-identical to the pre-registry path (rule 6) — the regression the
   P4 gate must never break.
Discriminating, not tautological: each assertion is proven by a mutation that
turns it red.

---

## 8. Risks

- **A registry row naming a producer the tree does not have** is the failure the
  resolve-in-test step (P1) prevents — the same protection `forecast_registry`
  already relies on.
- **Tolerance choice.** `metric_reconcile` uses 1% (`MATCH_TOLERANCE:30`);
  `data_quality.disagreement_flag` defaults to 5%. Pick **1% for same-basis**
  comparisons and **never auto-pick within tolerance** — publish the canonical and
  the spread. A wide tolerance that "keeps the peace" is the silent-reconciliation
  failure `regime_score` exists to forbid.
- **Do not let this become a second reconciler.** It is a manifest plus **one**
  resolver. The four detectors in §2 stay as they are; the registry is what they
  consult, not what replaces them.
- **Gate-off is byte-identical** (rule 6) — P4 only, and regression-tested.

---

## 9. Owner decisions

1. **RESOLVED (owner).** `p_e` canonical basis = the **engine**
   (`ratios.compute_ratios`, 30.01) — the repo's own reproducible TTM. The vendor
   `trailingPE` (20.33) becomes a labelled *fallback/diagnostic*, never authoritative.
2. **RESOLVED (owner).** `cash` canonical tag = **`CashAndCashEquivalents`**
   (net debt 66,177M); the short-term-investments tag is a labelled fallback.
3. **RESOLVED (owner).** `entry_ceiling` canonical producer = the **§103 card's
   `max_entry_price`** (§100's min-of-terms; FNF 40.68), i.e.
   `strategies/entry_ceiling.py::entry_ceiling`. The 38.17 the Trader's
   computed-verification line cites is not the authority.
4. **RESOLVED (owner, 2026-10-05).** P4's gate is **approved**: `enable_metric_authority`
   is a fail-closed publication gate, **off by default**, off-path byte-identical,
   on-path refusing to publish any metric that lacks a named, registered producer
   (**never** falling back to a legacy value); the full seven-point registration
   surface is required (§4). *Still open, the same class:* whether
   `get_scenario_dcf` should *require* a provenance guard on its caller-supplied
   `fcf`/`wacc`.

---

## 10. External precedent (the research this rests on)

- **Golden record / golden source / survivorship rules** — one *designated*
  authoritative source per field, decided in advance, with an ordered fallback and
  a lineage record of every value.
  [Accio, *The Golden Record*](https://accioanalytics.io/insights/golden-record-single-source-truth-financial-data/);
  [QuantMemo, *Golden Source and Reference Data Lineage*](https://quantmemo.com/concepts/reference-data-golden-source-and-lineage)
  ("golden source is a policy decision, not a fact").
- **Semantic / metric layer** — define a metric once, compile it to every
  consumer, so a consumer *cannot* compute its own version.
  [dbt Semantic Layer / MetricFlow](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works).
- **Provenance vs lineage** — provenance answers "where did this come from, and
  what authority does it carry?" (lineage answers "what transformed it").
  [DataHub](https://datahub.com/blog/data-lineage-vs-data-provenance/).
- **Fail-closed, verify-before-commit publication** — a commit whose proof fails
  yields no consumer-visible snapshot.
  [PVDM, arXiv 2608.14643](https://arxiv.org/abs/2608.14643).
- **Source-aware verification with per-claim source verdicts** — the failure mode
  is *cross-source conflation*: a claim true somewhere, attributed to the wrong
  source; a source-blind check passes it, a source-aware one blocks it.
  [ProvenanceGuard, 2606.18037](https://huggingface.co/blog/MultiverseComputingCAI/getting-the-source-right-not-just-the-fact-source).
- **The finance-domain precedent** — an LLM finance agent's answers checked
  against the SEC excerpts it retrieved, with per-claim allow/block and **zero
  false allows**. [NVFlow PR #9](https://github.com/NVIDIA/nvflow/pull/9).
- **Cross-system reconciliation in regulated enterprises** — a four-layer
  architecture (ingestion → staging → core models → semantic serving) with
  governed semantic standardization. [GERA, arXiv 2604.15108](https://arxiv.org/abs/2604.15108).

The repo's own `forecast_registry` is already an instance of the first and fourth
items; this doc lifts it from forecast keys to measured metrics.