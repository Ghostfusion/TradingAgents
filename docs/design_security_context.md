# Design: Security Context and Theme Applicability

**Status:** DESIGN — not built
**Version:** 1.0
**Date:** 2026-09-22
**Scope:** Supply the missing front end to `docs/Conditional_Research_Overlays_Design.md` — a deterministic security-classification step that answers *"which themes are candidates for this company?"* — and fix the taxonomy claims the current code gets wrong.
**Parent doc:** `docs/Conditional_Research_Overlays_Design.md` (v1.0, DESIGN — not built)

---

## 1. Executive summary

### What the parent doc is missing

`docs/Conditional_Research_Overlays_Design.md` specifies a conditional research-overlay layer in 40 sections. Its §6.1 flow (`doc:238-275`) runs:

```text
Raw evidence → Universal Engines → Overlay Detector → Active Overlays → ...
```

and the Overlay Detector has exactly three sub-steps (`doc:263-265`):

1. `materiality test`
2. `evidence sufficiency`
3. `applicability test`

**Step 3 has no producer anywhere in the doc.** "Applicability" is named once (`doc:265`) and never defined. There is no step that reads any property of the company, and the word `sector` appears in the doc only as an *example* of a structural force (`doc:27`), as a goal about reuse (`doc:95`), and in §17 (`doc:725-772`) — which is **not** a candidate selector. §17's own summary sentence is:

> The **schema remains the same** while the evidence adapters differ. (`doc:772`)

Its four sector headings (`doc:729`, `740`, `751`, `762`) all sit under the *same* theme (`AI`) and enumerate the evidence a human would gather *for that theme inside that sector*. Sector there selects **which evidence fields to populate for an already-chosen theme**. It never selects which themes are candidates.

The registry (§18, `doc:782-789`) is keyed only on theme id:

```python
OVERLAY_REGISTRY = {"ai": AIOverlay, "tariff": TariffOverlay, ...}
```

and the contract (§19, `doc:814-820`) takes only `symbol` + `evidence`. No key, argument or method anywhere in the doc accepts a company attribute.

§36 (`doc:1397-1427`) lists ten open decisions. **None of them asks "which overlays are candidates for a given company."** That question is unlisted, and it is the one this doc answers.

### What this doc adds

Three things, in order of importance:

1. **`SecurityContext`** — a deterministic, provenance-carrying classification object built once per run from data the run already holds or already fetches. It is the missing producer for `doc:265`'s applicability test.
2. **The theme priority matrix, as a WIDENING-ONLY prior.** The matrix may *add* candidate themes. It may **never remove one.** This turns the parent doc's informal "sector is a prior, not the final decision" into a structural, testable property — and it is the single most important idea in this document (§11).
3. **A taxonomy honesty rule.** The repo currently labels four different provider taxonomies as "GICS" and stores no provenance. This doc defines one canonical internal vocabulary (the one already in the repo), records the raw label and its source, and never claims GICS.

### The one-sentence thesis

> Classification is **metadata**, not analysis: it runs before any theme is considered, it is deterministic and cached, it carries the source that produced it, and it can only ever *widen* the set of themes worth checking — never narrow it.

---

## 2. Goals

1. Give `doc:265`'s `applicability test` a real, deterministic producer.
2. Keep classification **out of the LLM's hands** (parent doc P6, `doc:159-161`; Risk 6, `doc:1451-1453`).
3. Add **zero** decision-context characters (parent doc §26, `doc:1028`).
4. Preserve the parent doc's reproducibility invariant (`doc:1215`).
5. Reuse the repo's existing canonical vocabulary rather than creating a second taxonomy (master rule 15).
6. Record **provenance** for every classification value.
7. Record **disagreement** between sources instead of silently resolving it.
8. Be correct when classification is unavailable — a missing sector must not empty the candidate set.
9. Make the applicability policy auditable and versioned.
10. Change no existing behaviour while its gate is off.

## 3. Non-goals

This design does **not**:

1. Build a GICS, SIC or NAICS taxonomy. The repo has none and this doc does not invent one (§7).
2. Map SEC SIC codes to sectors. That would be a new crosswalk producer and a new taxonomy; it is explicitly deferred (§9.4).
3. Change any score, gate, size or verdict.
4. Enter decision context. `SecurityContext` is research-context only (§15).
5. Replace `resolve_instrument_identity` — it *extends* it (§9.1).
6. Make the matrix a measurement. It is declared policy (§10.2).
7. Add an industry-group or sub-industry level the repo cannot populate (§7.4).

---

## 4. Design principles

**P1 — Classification is metadata, not analysis.** It consumes no LLM context and produces no judgement. It answers "what kind of company is this", never "is this company good".

**P2 — One canonical vocabulary, already in the repo.** The eleven SPDR labels in `sector_rank.SPDR_SECTORS` (`sector_rank.py:12`) are the de-facto internal vocabulary; `_SPDR_BY_LABEL` (`:160`) and `sector_group_of` (`:163`) already key on them. Extend that vocabulary; never add a second.

**P3 — Provenance travels with the value.** A sector string without its source is unusable: the four producer legs return four different taxonomies (§7.2). Every classification carries `_source` and `_as_of`.

**P4 — Disagreement is recorded, never resolved.** When two sources disagree, both values are kept and the disagreement is surfaced. A silently-resolved disagreement is a hidden error at the root of every downstream materiality judgement.

**P5 — A prior may only widen.** The applicability matrix adds candidates. It cannot remove one (§11).

**P6 — Declared policy, not measurement.** Every matrix cell is the engine's declared prior, versioned and printed, exactly as the score engines print their ramps. It is never presented as a measured quantity.

**P7 — Absence is not exclusion.** An unknown sector yields **all** themes as candidates, not none. This is the parent doc's P3 (`doc:139`) applied one layer earlier.

**P8 — Deterministic and cached.** Same inputs produce the same context (parent doc `doc:1215`). The classification is fetched at most once per ticker per run.

---

## 5. Terminology

**Classification** — assigning a company to a position in a taxonomy. Deterministic, from metadata.

**Candidate relevance** — how worth-checking a theme is for a company, given its classification. **Not** a score, not a direction, not a materiality judgement.

**Applicability** — the parent doc's `doc:265` step: deciding which themes are worth evaluating for this company.

**Widening-only** — a mapping that can add elements to a set but never remove them.

**Provenance** — the source that produced a value, recorded beside it.

**Canonical sector** — one of the eleven internal labels in `sector_rank.SPDR_SECTORS` (`sector_rank.py:12`), lowercased by `_canonical_sector` (`:69`).

---

## 6. The gap, verified

Every claim below was read at the definition site.

| What | Where | Status |
| --- | --- | --- |
| Overlay Detector's `applicability test` | `doc:265` | Named once, never defined, no producer |
| A candidate-selection API | `doc:776-806` | Absent — the registry is keyed on theme id only |
| A sector-to-theme mapping | repo-wide | **Absent everywhere** |
| A ticker-to-industry producer | repo-wide | **Absent** — `INDUSTRY_ETFS` (`sector_rank.py:570`) is *industry ETFs*, not companies |
| A structured sector/industry field on any artefact | `reporting.py:2220-2301` | **Absent** — it survives only as text inside `tool_evidence['_rendered_block'][analyst]`, built by `evidence_gather._instrument_identity_line` (`evidence_gather.py:428`) |
| An open decision about candidate admission | `doc:1397-1427` | **Absent** — the ten items do not include it |
| Sector/industry in the vendor router | `interface.VENDOR_METHODS` (`interface.py:445`) | **Absent** — so it is invisible to `dataflows/registry.py` coverage |

And what *does* exist, which this design builds on:

| Asset | Where | Reuse |
| --- | --- | --- |
| Eleven-label canonical vocabulary | `sector_rank.SPDR_SECTORS` (`sector_rank.py:12`) | The canonical sector set |
| 73-label normalizer (sector **and** sub-industry names) | `sector_rank._GICS_TO_SPDR` (`sector_rank.py:78`) | The ONE normalizer — never a second |
| Canonical-sector function | `sector_rank._canonical_sector` (`sector_rank.py:69`) | Called, not reimplemented |
| Sector-to-SPDR bridge | `sector_rank.sector_group_of` (`sector_rank.py:163`) | The sector-to-ETF key |
| An identity carrier that already returns sector **and** industry | `agent_utils.resolve_instrument_identity` (`agent_utils.py:575`, lru-cached at `:574`) | **The object to extend** |
| Declaration-plus-validator pattern | `factor_schema.SUBSCORE_FACTORS` (`factor_schema.py:317`) + `validate_schema` (`:376`) | The pattern for the matrix |
| One-table-derives-everything pattern | `quant_scorecard.ENGINE_SECTIONS` (`quant_scorecard.py:119`) | The pattern for theme ownership |

---

## 7. The taxonomy problem

### 7.1 GICS is not available to this repo

GICS is owned by MSCI and S&P Global. Its current structure is **11 sectors, 25 industry groups, 74 industries, 163 sub-industries**, hierarchical, and **assigned at the company level**. The repo has no GICS source, no GICS code, and no licence. Any design that stores "GICS Sector → Industry Group → Industry → Sub-industry" would be building a taxonomy from nothing.

### 7.2 What the producers actually return

`yfinance_sector.fetch_sector` (`yfinance_sector.py:64`) is documented as returning "GICS sector". It does not. Its four legs return four taxonomies under one string:

| Leg | Where | What it really is |
| --- | --- | --- |
| repo ETF map | `yfinance_sector._etf_universe_sector` (`:39`) | the repo's own SPDR/industry-ETF issuer label |
| FMP `/profile` | `fmp.get_company_profile` (`fmp.py:68`) | FMP's own taxonomy, not documented as GICS |
| Finnhub `company_profile2` | `finnhub.get_profile_finnhub` (`finnhub.py:468`) | `finnhubIndustry` — Finnhub's **proprietary** classification |
| yfinance `info` | `_ticker_info` (`:21`) | Yahoo's label, which is **sub-industry granularity** for many names |

The repo already knows this last one — its own comment at `sector_rank.py:91-97` says *"yfinance `info.sector` returns SUB-INDUSTRY granularity (not GICS sector)"* — and `_GICS_TO_SPDR` absorbs both levels into one flat map. So the repo holds **two taxonomy levels flattened into one dict keyed by the word "GICS"**, with no code, no hierarchy, and no provenance.

### 7.3 The decision: name it what it is

**Do not build a GICS taxonomy. Do not claim GICS.**

Define the internal vocabulary as the eleven labels already in `SPDR_SECTORS` (`sector_rank.py:12`), reached through the existing `_canonical_sector` (`:69`). Store the provider's raw label **verbatim** beside its source. The canonical label is a *derived* value; the raw label is the *evidence*.

This is the honest version of the pasted brief's "store GICS-style Sector → Industry Group → Industry → Sub-industry": keep the *shape* (a hierarchy with provenance), drop the false *name*.

### 7.4 The levels the repo cannot populate

| Level | Status | Decision |
| --- | --- | --- |
| Sector | Available (raw + canonical) | Capture |
| Industry | Available from all three vendors, **discarded everywhere** | Capture as `industry_raw` + source. The bridge to a sector is the SAME `_canonical_sector` (it already maps 73 sector and sub-industry labels), stored as **`industry_implied_sector`** - an industry *mapped to a sector*, which is not a normalised industry, and is not named as one |
| Industry group | **No producer** | Do NOT claim. Named gap |
| Sub-industry | **No field**; only string aliases inside `_GICS_TO_SPDR` | Do NOT claim. Named gap |
| SEC SIC | Free, authoritative, **already fetched and discarded** (§9.3) | Capture opportunistically as a second opinion |

A design that stores four levels would be storing two empty ones. This doc stores what can be populated and names what cannot.

---

## 8. Architecture

The parent doc's §38 end-state gains one box, and its §6.1 detector's three sub-steps get owners:

```text
                         TICKER
                            │
                            ▼
                 SECURITY CONTEXT  (new)
        ┌───────────────────────────────────────┐
        │ sector_raw + source                   │
        │ industry_raw + source                 │
        │ sector_canonical  (existing map)      │
        │ spdr_etf          (existing map)      │
        │ sec_sic + description (opportunistic) │
        │ security_type     (existing producer) │
        │ agreement / disagreement              │
        └───────────────────┬───────────────────┘
                            │
                            ▼
              THEME APPLICABILITY MATRIX  (new)
                            │
                  WIDENING-ONLY: adds candidates,
                  never removes one  (see §11)
                            │
                            ▼
                    CANDIDATE THEMES
                            │
                            ▼
    ┌───────────────────────────────────────────────┐
    │  OVERLAY DETECTOR  (parent doc §6.1)          │
    │                                               │
    │  applicability test   ← THE CANDIDATE SET     │
    │  materiality test     ← parent doc §8         │
    │  evidence sufficiency ← parent doc §7.3       │
    └───────────────────┬───────────────────────────┘
                        │
                        ▼
                 ACTIVE OVERLAYS
                        │
                        ▼
              COMPACT DECISION CONTEXT
```

### 8.1 The three-way split

The pasted brief proposes splitting the parent doc's Materiality Detector into three responsibilities. That is right, and it maps cleanly onto steps the parent doc already has:

| Responsibility | Question | Producer | Parent doc anchor |
| --- | --- | --- | --- |
| **Classification** | What kind of company is this? | `SecurityContext` | *unlisted* |
| **Candidate detection** | Which themes are worth checking? | Applicability matrix | `doc:265` (undefined) |
| **Materiality** | Is this theme important for this company **now**? | Materiality Detector | §8, `doc:342-394` |

Only the third is a judgement. The first is metadata; the second is declared policy.

### 8.2 Why the split matters

It keeps the extension path linear. Adding a theme means adding a registry entry and (optionally) a matrix column. Adding a sector means adding a matrix row. Neither touches the detector. Without the split, sector logic and theme logic and materiality logic accumulate in one place and the layer becomes the rules engine the parent doc's §16 (`doc:675-724`) exists to prevent.

---

## 9. SecurityContext

### 9.1 It extends an existing object, it does not add one

`agent_utils.resolve_instrument_identity` (`agent_utils.py:575`) already returns `{company_name, sector, industry, exchange, quote_type}` from `yf.Ticker(...).info`, and is already `@functools.lru_cache(maxsize=256)` (`:574`). `build_instrument_context` (`:618`) already renders it as `Business classification: <Sector> / <Industry>`.

So the repo **already has a SecurityContext-shaped object**. What it lacks is:

- provenance (which source produced `sector`),
- the canonical sector and the SPDR key (only the raw string is kept),
- the SEC SIC (fetched elsewhere and discarded, §9.3),
- persistence to any artefact (it reaches a prompt line and nothing else),
- and any consumer that makes a decision from it.

**Decision:** `security_context.py` reads `resolve_instrument_identity` and *enriches* it. It does not fetch identity again, and it does not create a competing identity path (master rule 15).

### 9.2 Shape

```python
SecurityContext(
    symbol: str,
    company_name: str | None,

    sector_raw: str | None,          # verbatim from the provider
    sector_source: str | None,       # "yfinance" - the ONLY producer on this path (§9.4)
    industry_raw: str | None,
    industry_source: str | None,
    industry_implied_sector: str | None,  # industry_raw bridged to a canonical SECTOR (§7.4)

    sector_canonical: str | None,    # via sector_rank._canonical_sector
    spdr_etf: str | None,            # via sector_rank.sector_group_of

    sec_sic: str | None,             # opportunistic, see 9.3
    sec_sic_description: str | None,

    security_type: str | None,       # strategies.security_type.classify_security
    classification_as_of: str | None,
)
```

Every field is `None`-able. A `SecurityContext` with everything `None` is valid and means "unclassified" — it is not an error, and per P7 it yields the full candidate set.

### 9.3 Recovering the SEC SIC that is already on the wire

`sec_edgar.get_sec_filings` (`sec_edgar.py:387`) fetches the full submissions payload:

```python
payload = _json_get(_SUBMISSIONS_URL.format(cik=int(cik)))   # sec_edgar.py:406
```

and then reads **only** `payload["filings"]["recent"]` (`:411`). The payload's top-level `sic`, `sicDescription`, `name`, `exchanges` and `tickers` are fetched and discarded on every call.

SEC SIC is free, deterministic, and authoritative as a *regulatory* classification. It is a genuinely independent second opinion on what the company does.

**Decision:** capture `sic` and `sicDescription` **opportunistically** — from the existing fetch, never by adding a new SEC call. When `get_sec_filings` has not run in this run, both fields are `None` and the disagreement check simply does not fire.

**Do not** map SIC to a sector. A SIC-to-sector crosswalk is a new taxonomy and a new producer; it is deferred (§21, open decision 3).

### 9.4 Provenance and the disagreement surface

`sector_source` is the whole point of §7. Without it a caller cannot know whether it holds FMP's taxonomy, Finnhub's proprietary label, Yahoo's sub-industry string, or the repo's own ETF label — and the four are not interchangeable.

The repo has already been bitten by exactly this: `yfinance_sector._etf_universe_sector` (`:39`) exists *because* "IGV/SOXX/XLK all come back as `Financial Services` from yfinance/FMP" (documented at `:42-46`). That is a provider misclassification, and the repo's workaround is to override the provider for ETFs.

### 9.5 The agreement enum that could not fire - deleted

The first draft of this section specified `agreement` as one of `single_source` / `agree` / `disagree` / `unknown`, with a `disagreement` dict holding both raw values, and §12 handed `disagree` to the materiality layer as a confidence penalty.

**It was unreachable.** `resolve_instrument_identity` (`agent_utils.py:575`) makes exactly **one** vendor read - `yf.Ticker(normalize_symbol(ticker)).info` (`:595`) - and returns exactly one `sector`. So `sector_source` could only ever be `"yfinance"`, `agree` and `disagree` could never fire, and `disagreement` could never be non-empty. A second sector source would have to be fetched, and `fetch_sector` (`yfinance_sector.py:64`) is **not** `lru_cache`d, so that is a new network call - which §14 and §24 both forbid.

A state that cannot occur is worse than a named absence: it reads as a check that ran and passed. Three enum values, a dict, a test and a success criterion were all dead, and the dead `disagree` fed a design decision. So the surface is deleted rather than shipped unreachable.

**What survives is the independent signal.** `sec_sic` is still captured - free, deterministic, and genuinely independent of any sector label - but it is **recorded, not compared**, because comparing it would require the SIC-to-sector crosswalk this design refuses to build (§9.3). The owner's decision, 2026-09-22.

**P4 is therefore scoped, not withdrawn.** "Disagreement is recorded, never resolved" still governs any signal that *can* differ; with one sector source there is simply nothing to record. If a second source is ever added, the enum comes back **with** it, and this section becomes the record of what had to be true first.

---

## 10. The theme PRIORITY matrix

### 10.1 Shape

```python
#: Declared policy: canonical sector -> {theme_id: priority}.
#: NOT a measurement, NOT a score, NOT a direction.
#: Named PRIORITY, not "applicability": applicability implies "not applicable -> not
#: evaluated", which is exactly what §11 forbids. The matrix orders effort.
THEME_PRIORITY_MATRIX: dict[str, dict[str, str]] = {
    "technology":   {"ai": HIGH,   "tariff": LOW,    "china": MEDIUM,
                     "commodity": LOW, "regulatory": MEDIUM, "cyber": HIGH},
    "energy":       {"ai": MEDIUM, "tariff": MEDIUM, "china": MEDIUM,
                     "commodity": HIGH, "regulatory": HIGH, "cyber": MEDIUM},
    ...
}

MATRIX_VERSION = "2026-09-22.1"
```

Rows are **canonical sectors** (the eleven from `SPDR_SECTORS`). Columns are **theme ids** that must exist in `OVERLAY_REGISTRY` (parent doc §18).

Relevance is **categorical** (`HIGH` / `MEDIUM` / `LOW`) and never numeric. The pasted brief's own warning — *"these values should mean candidate relevance, not an actual investment score"* — is enforced by making a numeric value unrepresentable, and by rendering the basis sentence (§18).

### 10.2 It is declared policy, versioned

This mirrors the score engines' ramp convention exactly. `risk_score.RAMPS` (`risk_score.py:264`) is documented as *"this engine's declared policy, printed in the basis and measured later"*. The matrix is the same kind of object: a prior the engine declares, printed with the output, revisable, and never presented as a finding.

Hence `MATRIX_VERSION` and a per-cell `rationale` string. A cell that cannot state its rationale does not belong in the matrix.

### 10.3 Validation

Mirror `factor_schema.validate_schema` (`factor_schema.py:376`), which raises on unknown keys:

- every row key is a canonical sector from `SPDR_SECTORS`;
- every column key is a theme id present in the overlay registry;
- every cell is one of `HIGH` / `MEDIUM` / `LOW`;
- no sector row is missing (a missing row means "no prior", which must be explicit, not accidental).

The validator is the mechanism that keeps the matrix from silently growing a second vocabulary.

---

## 11. The widening invariant

This is the core contribution of this document.

### 11.1 The rule

```python
def candidate_themes(context: SecurityContext) -> frozenset[str]:
    """Every registered theme, plus the matrix's HIGH/MEDIUM prior.

    The matrix can only ADD. It can never remove a theme from consideration.
    """
    return frozenset(ALL_REGISTERED_THEMES) | matrix_candidates(context.sector_canonical)
```

`ALL_REGISTERED_THEMES` is always a subset of the result. The matrix contributes *ordering*, never *gating*.

### 11.2 Why it must be this way

The pasted brief gives the example itself: a company in **Energy** whose AI exposure is nonetheless material because of data-centre electricity demand. If the matrix could exclude, `energy → ai: MEDIUM` would be read as permission to skip AI — and the XOM case would be missed.

Stated generally: **a prior that can exclude is not a prior, it is a decision.** The parent doc's principle is that the LLM should not decide what matters (`doc:1451-1453`); the symmetric error is letting a *sector label* decide it. A label is even blunter than an LLM.

### 11.3 What the matrix is actually for

Once it cannot gate, its real function is clear: **ordering evidence-gathering effort under a budget.** With `MAX_ACTIVE_OVERLAYS = 3` (`doc:1027`) and per-overlay evidence budgets (`doc:1029-1030`), the system cannot evaluate every theme for every company. The matrix says which to evaluate *first*:

```text
HIGH    → evaluate in this pass
MEDIUM  → evaluate if budget remains
LOW     → evaluate only if the evidence stage raises it
(absent) → no prior; falls through to the default order
```

This is genuinely useful and completely safe, because a wrong ordering costs a missed *earlier* check, not a missed theme.

### 11.4 It is testable

The invariant is a property, so it has a property test:

```python
def test_the_matrix_can_only_widen_the_candidate_set():
    """No sector prior may ever remove a registered theme."""
    for sector in SPDR_SECTORS.values():
        ctx = SecurityContext(symbol="X", sector_canonical=sector.lower())
        assert ALL_REGISTERED_THEMES <= candidate_themes(ctx)
```

That test cannot pass by accident, and it fails the moment someone adds an exclusion path.

### 11.5 Absence is not exclusion

With `sector_canonical = None`, `matrix_candidates` returns `{}` and the candidate set is all themes. An unclassified company is **checked more**, not less. This is P7, and it is the parent doc's P3 (`doc:139`, "not applicable is not zero") applied one layer earlier.

---

## 12. Handoff to the materiality detector

The candidate set is the input to the parent doc's §8 detector (`doc:342-394`), unchanged. What this layer adds:

1. **A defined candidate set** — previously undefined.
2. **An ordering hint** — so a budget-constrained detector spends its first effort well.
3. **Nothing that grades the classification.** The first draft handed `agreement == "disagree"` to the materiality layer as a confidence penalty; that state was unreachable (§9.5) and the input is deleted with it. A misclassified company is still a materiality error at the root, but this layer cannot detect that with one source, so it does not pretend to.
4. **Nothing else.** No score, no direction, no activation.

Activation remains exactly where the parent doc puts it: `MATERIAL` and `HIGHLY_MATERIAL` enter decision context (`doc:373`); `MONITOR` stays in research context (`doc:375`).

---

## 13. Relationship to the parent doc, section by section

| Parent section | Relationship |
| --- | --- |
| §6.1 flow (`doc:238-275`) | Inserts Classification before the Overlay Detector; gives `doc:265` its producer |
| §7 lifecycle (`doc:277-340`) | Slots before `DISCOVER` (`doc:299`). Adds **no** lifecycle stage and does not change the overlay object |
| §8 materiality (`doc:342-394`) | Consumes the candidate set and the ordering hint. Dimensions and activation states unchanged |
| §17 sector adaptation (`doc:725-772`) | **Not** replaced. §17 adapts *evidence fields* for a chosen theme; this doc selects *themes*. Two different jobs, deliberately kept apart |
| §18 registry (`doc:776-806`) | Unchanged, and is the source of truth for valid theme ids. This doc adds an orthogonal, sector-keyed map beside it |
| §19 contract (`doc:807-838`) | Unchanged. `detect(symbol, evidence)` still takes symbol + evidence; the candidate set is *which* detectors run, not what they receive |
| §20 decision context (`doc:839-883`) | Unchanged. `SecurityContext` never enters this contract (§15) |
| §26 budgets (`doc:1020-1038`) | Satisfied by construction: the layer runs before any overlay text exists and adds zero decision-context chars |
| §27 reproducibility (`doc:1039-1064`) | Satisfied: deterministic, cached, versioned matrix |
| §36 open decisions (`doc:1397-1427`) | **Adds item 11** — candidate admission (see §21) |
| §39 order (`doc:1506-1525`) | Slots between item 2 (`OverlayRegistry`) and item 3 (`OverlayMaterialityDetector`) — see §22 |

---

## 14. Determinism and caching

| Requirement | Mechanism |
| --- | --- |
| Same inputs → same context | Pure derivation from `resolve_instrument_identity` (already lru-cached at `agent_utils.py:574`) + a pure matrix lookup |
| At most one classification fetch per run | `resolve_instrument_identity` is already cached. This layer adds **no** network call of its own |
| SIC is not an extra fetch | Read from the existing `get_sec_filings` payload when present; never a new call (§9.3) |
| Reproducible matrix | `MATRIX_VERSION` is recorded in the rendered basis and in any persisted block |

The repo's own audit already flags the uncached paths: `reporting.py:1043-1046` records that `resolve_peer_universe` "re-fetches statements and sectors live on every call with no cache". This design deliberately does not add another such path.

**Cost:** zero new network calls. `SecurityContext` reads cached identity and, opportunistically, an already-fetched payload.

---

## 15. Context safety

The parent doc's §26 (`doc:1020-1038`) sets `MAX_ACTIVE_OVERLAYS = 3` and `MAX_OVERLAY_CHARS = 8,000` and requires that an overlay be "compact by construction". §20's decision-context block (`doc:841-883`) has slots for the scorecard, active overlays, key evidence, counter-evidence and gate state — **and no classification slot**.

Therefore:

- `SecurityContext` is **research context only**. It never enters the decision-context block.
- The candidate set never enters it either. Only the *materiality outcome* does, which is the parent doc's existing rule.
- The rendered basis sentence (§18) goes to the research artefact, not the decision channel.

**Measured claim to verify at build time:** the decision-context character delta of this layer must be exactly zero. That is a test (§19), not an assertion.

---

## 16. Configuration and gates

One gate, registered in the six places the repo's own rule requires (`docs/gate_registry.md` §8 - the rule said five until 2026-09-22 and omitted the last row):

```text
enable_security_context   (default False)
TRADINGAGENTS_ENABLE_SECURITY_CONTEXT
```

| # | Place | Anchor |
| --- | --- | --- |
| 1 | `tradingagents/default_config.py` `DEFAULT_CONFIG` literal | pattern at `default_config.py:1106` |
| 2 | `_ENV_OVERRIDES` row | pattern at `default_config.py:342` |
| 3 | `docs/gate_registry.md` table row | pattern at `gate_registry.md:61` |
| 4 | `REGISTRY` in `tests/test_gate_env_toggles.py` | pattern at `test_gate_env_toggles.py:55` |
| 5 | `.env.example` | pattern at `.env.example:446` |
| 6 | `docs/api_reference.md` §1.1 env-var table (machine-checked against every env var the config reads) | `py -3.12 scripts/gen_api_reference_table.py --write` |

Gate off ⇒ `SecurityContext` is not built, no card block is written, and the run is byte-identical to today. This is the repo's established contract for an added block (`reporting.py:1242`).

The parent doc's own master gate `enable_research_overlays` (`doc:1096-1100`) does not exist yet; this gate is a sibling, not a child, so the classification layer can land before the overlay framework.

---

## 17. Persistence

No artefact currently persists sector or industry as a structured key — it survives only as text inside `tool_evidence['_rendered_block'][analyst]` via `evidence_gather._instrument_identity_line` (`evidence_gather.py:428`).

**Proposal:** a gated `security_context` block in `run_card.json`, assembled in `reporting.write_report_tree` (`reporting.py:1712`, card assembly at `:2220-2301`), following the existing `_run_card_*` producer pattern.

**Web impact: none required.** `trading_web`'s `read_report_tree` (`../trading_web/backend/capabilities.py:1773`) walks `rglob("*.json")` and returns every artefact generically — it does not enumerate card keys. Verified: the frontend's only `run_card.json` reference is prose (`../trading_web/frontend/src/App.jsx:1101`).

**Cross-run tracking** (parent doc §14, `doc:608-644`) follows the `scripts/coverage_scorecard.py` shape — `DEFAULT_REPORTS_DIR` (`:51`), `CARD_NAME` (`:54`), a `load_cards` reader that skips malformed cards (`:87`), a pure `build_*` (`:598`), and `main()` with `--json` (`:747`) — emitting one repo-root artefact, the `reports/alpha_ledger.jsonl` precedent.

---

## 18. Rendering

One deterministic sentence, printed in the research artefact. Example:

```text
One line, as delivered:

```text
Security context: sector=Technology (source: yfinance); canonical=technology;
spdr=XLK; industry=Consumer Electronics (source: yfinance); type=operating_company.
Candidate themes: 6 registered (prior order, 2026-09-22.1: ai=HIGH, cyber=HIGH,
china=MEDIUM, regulatory=MEDIUM, commodity=LOW, tariff=LOW). This is a declared
prior, not a measurement, and it does not gate: every registered theme remains a
candidate.
```

**It is deliberately ONE line** (403 characters for AAPL). It is read by analysts, so the structured detail lives in the run card and not in an LLM's context. The three properties below are each tested.
```

Three properties this rendering must have:

1. **The source is always named** — a sector without its source is unusable (§9.4).
2. **The matrix version is always named** — a prior without a version is not auditable (§10.2).
3. **The widening disclaimer is always present** — so no reader mistakes the prior for a gate (§11).

---

## 19. Testing strategy

**Unit**

1. Provenance travels: `sector_source` is set whenever `sector_raw` is.
2. `_canonical_sector` is *called*, not reimplemented — a mutation to the existing map changes this layer's output.
3. `sector_source` names only a producer that can have produced the value (§9.5).
4. There is no `agreement` / `disagreement` field - the unreachable enum is not shipped.
5. An unclassified context yields `None` for every derived field and does not raise.
6. The matrix validator rejects an unknown theme id, an unknown sector row, and a numeric relevance.

**Property**

7. **The widening invariant** (§11.4): for every canonical sector, `ALL_REGISTERED_THEMES <= candidate_themes(ctx)`.
8. A `None` sector yields all themes, not none.

**Integration**

9. Gate off ⇒ the run card is byte-identical to a pre-change card.
10. Gate on ⇒ the `security_context` block appears with provenance and the matrix version.
11. The decision-context character delta is **zero** (§15).
12. No new network call: with `resolve_instrument_identity` stubbed, this layer performs no fetch.

**Failing-first proofs.** Per the repo's standard, the behaviour-changing parts (the invariant, provenance capture, the disagreement record, the gate) each need a mutation that restores the pre-change code and turns exactly the defending test RED, with a byte-identical sha256 restore.

---

## 20. Defects found while grounding this design

The repo's recurring defect class is **"a field whose name promises more than it measures"**. This investigation found six instances on the classification path. Three are documentation-only and were corrected; three are behavioural, were reported for the owner's decision, and were then **fixed on his instruction** (§20.2) - one of them showing the report itself was wrong; plus one unrelated registry-coverage defect (§20.3), whose first stage is now applied.

### 20.1 Corrected (documentation-only, no behaviour change)

| # | Where | Defect | Fix |
| --- | --- | --- | --- |
| 1 | `yfinance_sector.py:5` module docstring | claimed `fetch_sector` returns "the ticker's GICS sector" | states it returns the provider's sector label |
| 2 | `yfinance_sector.py:65` `fetch_sector` docstring | "GICS sector for the ticker" — but four legs return four taxonomies; also omitted the Finnhub leg entirely | lists all four legs, states the source is discarded and the value is not GICS |
| 3 | `finnhub.py:482` comment | "Finnhub returns the GICS sector under `finnhubIndustry`" — Finnhub documents `finnhubIndustry` as its **own** classification, not GICS | corrected, with the `sector`-filled-from-`Industry` naming collapse noted |

### 20.2 Reported, then fixed (behavioural)

| # | Where | Defect | Resolution |
| --- | --- | --- | --- |
| 4 | `finnhub.py:468` | the key named `sector` was populated from a field named **`finnhubIndustry`**. **This report was wrong on one point:** live-probed 2026-09-22, `company_profile2` carries **no `sector` key and no `industry` key at all** — the old rename was the only reason `prof["sector"]` existed | **FIXED.** `get_profile_finnhub` returns the vendor payload unmodified (the comment is at `finnhub.py:482-493`) and `fetch_sector` does the mapping, preserving the old precedence exactly: `prof.get("sector") or prof.get("finnhubIndustry")` (`yfinance_sector.py:112`). The old rename only fired when `sector` was absent, so **behaviour is unchanged for real payloads** — the mapping moved, the precedence did not |
| 5 | `statement_parsing.py:187` | `"sector": ["sector", "industrygroup"]` — the canonical `sector` key accepted an **industry-group** value. **This report was wrong about the alias being dead:** `_norm` replaces non-alphanumerics with a SPACE, so the spaced label "Industry Group" never matched — but an **unseparated** label (`IndustryGroup`) did, which a failing-first test caught. `fin["sector"]` is the Altman variant selector (`statement_parsing.py:1565`) and feeds the Piotroski basis, and `altman_variant_for` routes it through `sector_group_of`, where a stray financial group resolves to `XLF` and **withholds the variant** for a non-financial company | **FIXED.** The alias is deleted (`"sector": ["sector"]`). A payload carrying an `IndustryGroup` row no longer fills `sector`; the variant then falls back to the manufacturer test instead of being suppressed |
| 6 | `cross_section.py:89` | `industry_neutral_z` took a parameter named `sector_map` (`:90`), and `peer_universe.resolve_growth_medians` (`:304`) computed "Industry medians" by partitioning on a **sector** label | **FIXED (naming only).** The parameter is `group_map` (`:90`), with the docstring stating the grouping is the caller's — in this repo a provider sector label from `fetch_sector`, which is neither GICS nor an industry group. `resolve_growth_medians` now says peer-group medians. The **function name is unchanged**: `industry-neutral` is the standard Grinold-Kahn term for neutralising within the peer group, and renaming it is a 4-site public change for a cosmetic gain. Both callers pass positionally, so no caller changed and no behaviour changed. The returned key stays `n_sectors` — a returned-dict contract is wider than a parameter name, so it is reported rather than renamed |

### 20.3 Reported, unrelated to classification

`docs/gate_registry.md` titles itself **"every gate"** and its own §8 (`gate_registry.md:229`) says a gate is not done without a row in it — yet **48 of the 88 `enable_*` keys in `DEFAULT_CONFIG` have no row**, including all eight score-engine gates and `enable_quant_scorecard`. The doc and `tests/test_gate_env_toggles.REGISTRY` (`:35`) agree with each other (40 rows), so nothing is inconsistent — the coverage is simply 45% of the `enable_*` surface while the title claims all of it. The engine gates are instead covered by `tests/test_quant_scorecard.py:442-444` and `tests/test_engine_ownership_map.py`. **Stage 1 applied (2026-09-22):** the title is narrowed to the families the file actually covers and a new paragraph names where the eight score-engine gates are covered, so the doc no longer implies a row for every gate; a test fails if the over-claim returns. **Not done:** authoring the 48 remaining rows of "Enforced at"/"Proven by" evidence is a substantial, judgement-heavy task, and an unverified row is worse than a missing one in a document whose stated purpose is to stop gates that cannot fire.

---

## 21. Open decisions

The parent doc's ten (`doc:1397-1410`) stand. This layer adds:

11. **Candidate admission — ANSWERED 2026-09-22: ordering only, never exclusion.** The widening invariant stands as written and is enforced by a property test over every canonical sector. Exclusion was offered and declined; the XOM/AI case stays caught.
12. **Matrix ownership** — who may edit a cell, and does a cell change require a version bump? (Proposed: yes, always.)
13. **SIC-to-sector crosswalk** — build one, or keep SIC as an independent second opinion only? (Proposed: second opinion only; a crosswalk is a new taxonomy.)
14. **Disagreement handling — CLOSED 2026-09-22: the surface is deleted.** Not "surface only": with one reachable sector source there was nothing to surface (§9.5). Reopens automatically if a second source is ever added.
15. **`industry_raw` normalization — ANSWERED 2026-09-22: reuse `_canonical_sector`, stored as `industry_implied_sector`.** Named for what it is - an industry bridged to a *sector* - so no reader mistakes it for a normalised industry (a second normalizer would violate rule 15).

---

## 22. Work items

These slot into the parent doc's §39 order (`doc:1506-1525`) **between items 2 and 3** — after `OverlayRegistry` (which supplies the valid theme ids) and before `OverlayMaterialityDetector` (which consumes the candidate set).

| # | Deliverable | Depends on | Acceptance |
| --- | --- | --- | --- |
| SC-1 | `SecurityContext` object + `build_security_context` | `resolve_instrument_identity` (`agent_utils.py:575`) | provenance and canonical sector present; no new network call |
| SC-2 | SEC SIC capture from the existing submissions payload | `sec_edgar.py:406` | `sic`/`sicDescription` recovered when present, `None` otherwise, no extra fetch |
| SC-3 | `agreement` / `disagreement` record | SC-1, SC-2 | two sources disagreeing are both retained |
| SC-4 | `THEME_APPLICABILITY` + `MATRIX_VERSION` + validator | parent doc §18 registry | validator rejects unknown theme id / sector row / numeric cell |
| SC-5 | `candidate_themes` with the widening invariant | SC-4 | property test §11.4 passes for every sector |
| SC-6 | `enable_security_context` gate, five places | — | gate off ⇒ byte-identical run card |
| SC-7 | `security_context` run-card block | SC-1, SC-6 | block present when on; **zero** decision-context chars |
| SC-8 | Deterministic rendering (§18) | SC-1, SC-4 | source, matrix version and widening disclaimer always present |
| SC-9 | Cross-run tracker (`scripts/`) | SC-7 | follows the `coverage_scorecard.py` shape |
| SC-10 | Parent doc §36 gains item 11 | SC-5 | the open decision is recorded |

**SC-1 to SC-8 are BUILT (2026-09-22, commit pending).** `tradingagents/strategies/security_context.py`, the `enable_security_context` gate in all five places, and the `security_context` run-card block are in the tree; SC-2's SIC capture is `sec_edgar.peek_sic`, which reads the payload the run already fetched and never fetches.

SC-5b is the next item. Do not begin with SC-8 or SC-9.

| # | Deliverable | Status |
| --- | --- | --- |
| SC-1 | `SecurityContext` + `build_security_context` | **built** |
| SC-2 | SEC SIC from the existing payload (`sec_edgar.peek_sic`) | **built** |
| SC-3 | `agreement` / `disagreement` | **deleted** - unreachable (§9.5) |
| SC-4a | `THEME_REGISTRY` / `ALL_REGISTERED_THEMES` | **built** (the parent doc's six ids) |
| SC-4 | `THEME_PRIORITY_MATRIX` + `MATRIX_VERSION` + validator | **built** - 66 cells, each with a declared basis |
| SC-5 | `candidate_themes` + the widening invariant | **built** - property-tested over every sector |
| SC-5b | `theme_triggers` - the cheap escalation scan | **NEXT** - the one thing §11.3's `LOW` line still needs |
| SC-6 | the gate, five places | **built** |
| SC-7 | the `security_context` run-card block | **built** |
| SC-8 | deterministic one-line rendering | **built** |
| SC-9 | cross-run tracker (`scripts/`) | not started |
| SC-10 | parent doc §36 gains item 11 | not started (owner's file) |

---

## 23. Risks

**Risk 1 — The matrix becomes a rules engine.** Mitigation: rows are canonical sectors, columns are registered theme ids, cells are three categorical values, and a validator rejects anything else. It cannot grow branching logic.

**Risk 2 — The prior is mistaken for a judgement.** Mitigation: the rendering always carries the widening disclaimer and the matrix version (§18); relevance is categorical, so no number can be quoted as a score.

**Risk 3 — A wrong classification silently suppresses a theme.** Mitigation: impossible by construction — the matrix cannot suppress (§11).

**Risk 4 — Provenance is dropped again by a future consumer.** Mitigation: `sector_source` is part of the object and part of the rendered sentence; a test asserts source is set whenever raw is.

**Risk 5 — The layer creeps into decision context.** Mitigation: the decision-context delta is a **tested** zero (§19), not a convention.

**Risk 6 — A second taxonomy appears.** Mitigation: the canonical set is `SPDR_SECTORS` and the normalizer is `_canonical_sector`, both existing; the validator rejects rows outside the canonical set.

**Risk 7 — Stale matrix.** Mitigation: `MATRIX_VERSION` travels with every rendered basis; a cell edit requires a bump (§21 item 12).

---

## 24. Success criteria

**Architecture**
- The parent doc's §6.1 `applicability test` (`doc:265`) has a named producer.
- No second taxonomy, no second normalizer, no second identity fetch.
- The parent doc's §39 order absorbs these items without renumbering.

**Correctness**
- The widening invariant holds for every canonical sector (property test).
- An unclassified company is checked *more*, not less.
- No state is advertised that cannot occur: the only classification source is named, and the unreachable agreement enum is absent (§9.5).

**Safety**
- Decision-context character delta is exactly zero.
- Gate off ⇒ byte-identical run card.
- Zero new network calls.

**Honesty**
- No field in this layer is named GICS, SIC or NAICS unless it *is* that.
- Every classification value carries its source.

---

## 25. Final design decision

### Adopt

**A deterministic `SecurityContext` + a widening-only theme applicability matrix, sitting between the overlay registry and the materiality detector.**

### Reject

**A GICS taxonomy the repo cannot source. An industry-group or sub-industry level the repo cannot populate. An LLM that decides which themes apply.**

### Adopt

**Provenance on every classification value. Recorded disagreement. A versioned, declared-policy matrix.**

### Preserve

**The parent doc's eight universal engines, its materiality detector, its decision-context contract, and its budgets.**

### Key invariant

> **The applicability matrix may add candidate themes. It may never remove one.**

A sector label is a prior. A prior that can exclude is a decision, and this layer is not permitted to make decisions.

---

## Appendix A — Verified anchors used in this document

| Symbol | Location |
| --- | --- |
| `fetch_sector` | `tradingagents/dataflows/yfinance_sector.py:64` |
| `_etf_universe_sector` | `tradingagents/dataflows/yfinance_sector.py:39` |
| `_ticker_info` | `tradingagents/dataflows/yfinance_sector.py:21` |
| `get_company_profile` | `tradingagents/dataflows/fmp.py:68` |
| `get_profile_finnhub` | `tradingagents/dataflows/finnhub.py:468` |
| `get_sec_filings` / submissions fetch | `tradingagents/dataflows/sec_edgar.py:387` / `:406` |
| `_SUBMISSIONS_URL` | `tradingagents/dataflows/sec_edgar.py:35` |
| `resolve_instrument_identity` (+ `lru_cache`) | `tradingagents/agents/utils/agent_utils.py:575` / `:574` |
| `build_instrument_context` | `tradingagents/agents/utils/agent_utils.py:618` |
| `classify_security` | `tradingagents/strategies/security_type.py:72` |
| `SPDR_SECTORS` | `tradingagents/strategies/sector_rank.py:12` |
| `_canonical_sector` | `tradingagents/strategies/sector_rank.py:69` |
| `_GICS_TO_SPDR` | `tradingagents/strategies/sector_rank.py:78` |
| `_SPDR_BY_LABEL` | `tradingagents/strategies/sector_rank.py:160` |
| `sector_group_of` | `tradingagents/strategies/sector_rank.py:163` |
| `INDUSTRY_ETFS` | `tradingagents/strategies/sector_rank.py:570` |
| `_GICS_MAP` | `tradingagents/dataflows/sp500_universe.py:29` |
| `_ROW_ALIASES` (`sector` alias) | `tradingagents/dataflows/statement_parsing.py:75` / `:187` |
| `industry_neutral_z` | `tradingagents/strategies/cross_section.py:89` |
| `VENDOR_METHODS` | `tradingagents/dataflows/interface.py:445` |
| `SUBSCORE_FACTORS` / `validate_schema` | `tradingagents/strategies/factor_schema.py:317` / `:376` |
| `ENGINE_SECTIONS` / `ENGINE_GATES` | `tradingagents/strategies/quant_scorecard.py:119` / `:70` |
| `write_report_tree` / card assembly | `tradingagents/reporting.py:1712` / `:2220-2301` |
| `_instrument_identity_line` | `tradingagents/agents/utils/evidence_gather.py:428` |
| `REGISTRY` | `tests/test_gate_env_toggles.py:35` |
| `read_report_tree` (web) | `../trading_web/backend/capabilities.py:1773` |
| Parent doc anchors | `docs/Conditional_Research_Overlays_Design.md` §6.1 `:238-275`, §8 `:342-394`, §17 `:725-772`, §18 `:776-806`, §19 `:807-838`, §20 `:839-883`, §26 `:1020-1038`, §27 `:1039-1064`, §36 `:1397-1427`, §39 `:1506-1525` |

## Appendix B — External sources

- GICS structure (11 sectors / 25 industry groups / 74 industries / 163 sub-industries; assigned at company level; owned by MSCI and S&P Global) — MSCI/S&P Global GICS documentation, as summarised in the search results cited during this investigation.
- Finnhub `company_profile2.finnhubIndustry` is Finnhub's **own** industry classification, not GICS — Finnhub API documentation and issue tracker.
- FMP `/profile` returns `sector` / `industry` in FMP's own taxonomy; the documentation does not establish them as official GICS labels.
- Yahoo Finance exposes eleven sector-level values (`Technology`, `Financial Services`, `Consumer Cyclical`, …) whose naming diverges from GICS (`Information Technology`, `Financials`, `Consumer Discretionary`).
- SEC EDGAR exposes `sic` and `sicDescription` on `https://data.sec.gov/submissions/CIK##########.json`, with ticker-to-CIK via `https://www.sec.gov/files/company_tickers.json`. The SEC does not store GICS.
- Thematic-exposure practice: sector labels alone are considered too blunt; a defensible framework combines sector classification with revenue linkage, business-description linkage, and holdings/consensus validation, and distinguishes core enablers, partial beneficiaries and incidental exposure. The more defensible terminology is "thematic exposure matrix" or "sector-theme relevance matrix" rather than "applicability matrix".
