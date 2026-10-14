# Design — the Fact layer: a number, its qualifiers, and the rule that produced it

Status: **implemented (P1-P4), gated by `enable_fact_layer` (default OFF)**
Owner decision: proceed on the root-cause analysis of 2026-10-14 (the review of the
live `GMED_20261014_125508` tree).

## 1. The defect this exists for

The engine pulled an XBRL-shaped fact — a value WITH its context, unit and
declared precision — out of a vendor payload and then converted it to a bare
`float` at its internal interface. `_canonicalize` collapses a statement to
`{current, prior}` scalars; `fetch_ticker`'s `absorb` is last-writer-wins over
loosely-matched row labels and its per-key period map is **opt-in**. Every tool
leaf then re-authored the qualifiers it needed. Three live instances, one per
failure mode, all from 2026-10-14:

| mode | the claim that was not true | instance |
| --- | --- | --- |
| **coverage** | "3 means three" | `GMED` published `Piotroski F: 3.00` beside `trap_risk: MEDIUM`, whose only trigger was `f_score=3 (< 4)` — from a canonical missing the prior-period legs. The same name read `8.00 at 8 of 9 signals` an hour later. |
| **period** | "this is the value now" | the DCF bridge read FY2025-12-31 (cash + ST investments 557.243m / total debt 118.656m) while 2026-06-30 sat in the payload (595.142m / 111.192m): net cash 438.587m instead of 483.950m — $0.34/share of fair value, inherited by the reverse DCF. |
| **availability** | "this period has happened" | `get_institution_holdings` quoted `90.3 % of float in 2026/Q3` on a day when Form 13F filings for that quarter are not due until 2026-11-16, and `SentimentScore.inst_flow_z` z-scored that still-accumulating delta against completed quarters (component −0.03 where the newest complete period reads +1.80). |

The first two were fixed in place at `f08a18f`; the layer is what makes them
structural rather than three good habits.

## 2. Why the qualifiers are not decoration (the normative basis)

- **VIM 2.9 / GUM 3.1.2** (JCGM 200:2012): a measurement result is a value
  "together with any other available relevant information", and "is complete
  only when accompanied by a statement of the uncertainty of that estimate".
- **XBRL 2.1 §1.4**: an item "contains the value of the simple fact and a
  reference to the context (and unit for numeric items) needed to correctly
  interpret that fact"; numeric items are **required** to document their
  measurement accuracy and unit; a Period is "an instant or duration of time".
- **XBRL Precision/Decimals WGN**: `@decimals` states "the range in which the
  actual value ... lies" — i.e. the printed precision is part of the number, and
  half an ulp is the floor below which a disagreement is not a disagreement
  (`metric_authority.declared_decimals` already encodes this for prices).
- **Exchange Act Rule 0-3(a)**: a due date landing on a Saturday, Sunday or
  federal holiday moves to the next business day.
- **17 CFR 249.308a(a)**: Form 10-Q — 40 days after the fiscal quarter end for
  large accelerated and accelerated filers, 45 days for all other registrants.
- **17 CFR 249.310(b)**: Form 10-K — 60 / 75 / 90 days after the fiscal year end
  for large accelerated / accelerated / all other registrants.
- **17 CFR 240.13f-1(a)**: Form 13F — 45 days after each calendar quarter end
  (`filing_deadlines.form_13f_deadline`, the one producer).
- **Item 8 of Form 20-F**: 4 months after the fiscal year end for foreign
  private issuers (dates per Mayer Brown's 2023 SEC filing-deadline note).
- **Rule 12b-25**: a late-filing notification buys 5 extra calendar days for a
  10-Q and 15 for a 10-K — which is why a due date is a *lower* bound.
- **Knowledge time is not valid time.** Livnat's WRDS note documents the vendor
  behaviour this engine reads: quarterly data is first updated from the earnings
  press release (update code 2), then from the 10-Q (code 3), and a subsequent
  revision is written into the database, "essentially 'rewriting history'". A
  point-in-time database exists precisely to "simulate what Compustat information
  a user had at a particular point in time" (Charter Oak PIT). This is the
  standard two-axis temporal model (valid time vs transaction/knowledge time).

## 3. The design

`tradingagents/strategies/facts.py` — `Fact(Observation)`, extending the
reconcile layer's `Observation` rather than duplicating it. `metric` is the
canonical key; the three added qualifier groups are:

- **coverage** — `FactCoverage(n_of, required, rule, withheld)` plus
  `Fact.usable`. A composite's coverage is `min` over its inputs, so a partial
  leg arrives at `score_engine.combine` as an **absent** component (which that
  kernel already handles with a named reason) instead of as a smaller number.
- **period** — `period_label` (the vendor's own label), `period_kind` and
  `period_end` (ISO, only when the label STATES one), `basis_text` (what the
  merge asked for), `basis_conflict`.
- **availability** — `available_at`/`available_latest`/`availability_state`/
  `availability_reason`/`availability_basis`, from
  `tradingagents/strategies/availability.py`, plus `Fact.filed_basis`.

`tradingagents/strategies/availability.py` — the POLICY table (`FORM_LAG_DAYS`,
`FILER_STATUSES`, `LATE_FILING_EXTENSION_DAYS`), the filer-class resolution
(unknown resolves to the **slowest** statutory bound and says so), and
`fact_availability(...)`. It delegates the Form 13F deadline to
`filing_deadlines` so the 45-day rule has one producer; the business-day roll is
the same `next_business_day`.

One producer per concept:

| concept | producer |
| --- | --- |
| the `{current, prior}` shape | `facts.latest` / `facts.prior` (`statement_parsing._latest`/`_prior` delegate) |
| a canonical line item's unit | `facts.FACT_UNITS` |
| a derived value's coverage | `facts.derive` |
| a fact's qualifier text | `facts.render_fact` |
| a leaf's grouped basis line | `facts.basis_line` |
| a filing class's due date | `availability.form_deadline` (13F → `filing_deadlines.form_13f_deadline`) |
| the run clock | `date_window.get_run_trade_date` / `get_run_clock` |

## 4. The rule that keeps it honest

**A Fact is resolved from the SAME canonical/provenance pair the leaf
consumed — never from a second vendor pull.** Two consecutive `fetch_ticker`
calls for GMED on 2026-10-14 returned different payload sets and moved P/E from
19.05 to 19.14; a qualifier built from a second read would describe a different
measurement than the number it qualifies. The first implementation of P1 broke
this rule and the gate test caught it:
`tests/test_measurement_contract.py::test_the_gate_never_causes_a_second_vendor_pull`.

## 5. Phases

- **P1 — the type and the renderer.** `Fact`, `resolve_facts`, `derive`,
  `render_fact`, `basis_line`, wired to the statement leaves
  (`get_analyst_verdict`'s basis line, `get_ratios`' trailing qualifier, the
  DCF's `fair_value_fact`).
- **P2 — coverage for composites.** `derive` produces the F-Score's coverage in
  `statement_parsing.screen_ticker` (the hand-rolled `f_score_n` count is now
  read off `FactCoverage`), and the DCF's per-share value is derived over its
  five measured legs so an ASSUMED cash/debt leg becomes a PARTIAL rather than
  prose. `score_engine.combine` needed no change: its `coverage`/`floor`/
  `withheld` contract was already the right shape.
- **P3 — availability.** `availability.py`, the run-clock comparison, and the
  maker of `inst_flow_z`'s refusal (landed at `f08a18f` for 13F) generalised to
  10-K / 10-Q / 20-F / 13F.
- **P4 — the contract tests.** `tests/test_measurement_contract.py` holds
  `FACT_UNITS` to set equality with the parser's own canonical keys (a new
  statement field cannot enter the tree without a declared unit), and pins the
  gate's two promises: gate-off byte-identical, gate-on qualifier-only.

## 6. Deliberate non-goals

- **No raw-payload store.** The vendors' own terms require the durable
  reference branch, not a mirror of their payloads.
- **No `metric_authority` rewrite.** `Fact` extends `Observation`; the
  reconcile layer's `TOOL_SEMANTICS` stays the declaration table for what a
  *tool leaf prints*, while `FACT_UNITS` declares what a *canonical line item
  is*. Different roles, no overlap.
- **No per-value measurement blocks in every leaf.** The grouped basis line plus
  the DCF's derived-fact line are what carried information the legacy text could
  not; a block of nine `key: value unit (period)` lines per tool is noise.
- **No relation to `enable_factor_availability_gate`** (H2 in
  `strategies/factor_expressions.py`): that gate rejects a factor *registration*
  whose field was unobservable at the decision date. Same word, different axis —
  this layer asks when a FILING could exist.
- **No web surface.** No tool, flag, script signature or JSON shape moved, so
  `trading_web` needs nothing (rule 4).
- **The gate is a RELEASE toggle** (Martin Fowler's taxonomy: a transient toggle
  with a carrying cost) and is meant to be deleted when the qualifier rendering
  is unconditional — i.e. when the message corpus no longer needs an A/B.

## 7. Open items this design does NOT close

1. **The gate is OFF by default.** Turning it on changes the text of three tool
   leaves; the owner's call, and blocked on nobody.
2. **`FACT_UNITS` covers canonical *inputs*, not derived ratios.**
   `strategies/ratios.py::RENDER_ORDER` is the unit registry for the computed
   ratio block; a future pass could unify them.
3. **The availability gate is declarative for vendor statement payloads.** A
   vendor payload whose basis names no form has `availability: unknown` — the
   honest answer, since a company may publish a preliminary earnings figure in a
   press release weeks before its 10-Q (banks often report within ~14 days of
   quarter end, so no press-release lag is safe to assume). Only a source that
   DECLARES a filing (SEC XBRL series, Form 13F) gets a real deadline, and a
   period whose ISO end is in the future is refused.
4. **The bar series still filters on valid time only** (`stockstats_utils.py`,
   `auto_adjust=True`), so an adjusted series is restated retroactively by
   dividends and splits. `availability` is the vocabulary that would express a
   bar's knowledge time; the detector is not built.
5. **Structured `provider` + fetch instant on the tool-evidence leaf** remains
   unbuilt (the `Fact` carries both, but the evidence writer does not read it).

## 8. Evidence read while landing this

Primary sources, all read 2026-10-14: the CFR text of 17 CFR 249.308a and
249.310 (eCFR via the Legal Information Institute); `jcgm.bipm.org/vim/en/2.9.html`;
the XBRL 2.1 Recommendation and the Precision/Decimals WGN; Mayer Brown's *2023
SEC Filing Deadlines and Financial Statement Staleness Dates* (Rule 0-3(a), the
20-F four-month date, the 12b-25 rule); Livnat's HBS-WRDS note on the
preliminary-vs-filed earnings dates and Compustat's history rewrite; Martin
Fowler's *Feature Toggles* for the release-toggle taxonomy; JSR-385 (Units of
Measurement API) as the type-level precedent for carrying a unit with a number.
