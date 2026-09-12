# Quant Formula Additions - Implementation Plan

Status: **plan only (2026-09-11) - no code written yet.** Implements the adopted
list in
[`docs/design_quant_formulas_research_round2.md`](design_quant_formulas_research_round2.md)
(items **N1-N9**). Each phase names target files and symbols, the exact behaviour,
the config gate, the tests that must be **proven failing first**, and the
acceptance criteria. Nothing here changes an existing computation: every item is
additive, default-off, and degrades to `unavailable` when its inputs are missing.

---

## 0. Ground rules (inherited, non-negotiable)

1. **Deterministic first.** Every formula is a pure function over series the repo
already fetches; no formula lives in a prompt.
2. **One implementation per computation.** Extend the module that already owns the
measure; do not add a parallel path. The design doc's section 1 ledger is the
exclusion list.
3. **No fabrication.** Missing input yields `unavailable`/`None`, rendered as
"unavailable". Every estimator states its basis (window, sample length, dictionary
version).
4. **Gates must be able to fail.** Each new test is proven failing under a targeted
mutation of the code it guards (per phase, section 4). Tests assert observable
behaviour, never wiring or source text.
5. **Default-off or existing flag.** New behaviour sits behind a config key that
defaults to off, so a run's outputs cannot change silently.
6. **CHANGELOG + cross-repo rule.** Each landed phase gets a CHANGELOG entry; if it
reshapes a tool's JSON or a CLI flag the sibling web app consumes, the entry states
the **web impact** (CHANGELOG preamble; registry `trading_web/docs/web_TOPICS.md`).
7. **No new vendors.** All items use the existing OHLCV / statement / document /
option-chain chain.

---

## 1. Phase map

| Phase | Item | Lands in | Config gate | Size | Depends on |
| --- | --- | --- | --- | --- | --- |
| **Q1** | N1 spread estimators | `strategies/liquidity_risk.py`, `strategies/execution_schedule.py` | `enable_spread_estimator` | S | - |
| **Q2** | N5 min-CVaR/CDaR sizing + C4 copula scenarios | `strategies/book_risk.py`, `strategies/risk_governor.py` | `enable_book_risk_sizing` | M | - |
| **Q3** | N2 conformal valuation bands | `strategies/conformal.py` (new), `strategies/dcf.py`, `agents/utils/report_verifier.py` | `enable_conformal_bands` | M | run history |
| **Q4** | N3 GP/A + N4 NOA | `dataflows/quantitative_scores.py`, `strategies/normalized.py`, screener | always-on rows | S | - |
| **Q5** | N8 overnight/intraday decomposition | `strategies/market_session.py`, `agents/utils/analysis_tools.py` | `enable_return_decomposition` | S | `opens` (landed) |
| **Q6** | N6 LM tone + readability + divergence | `strategies/text_factors.py` (new), `agents/utils/news_data_tools.py`, verifier | `enable_text_factors` | M | text source decision (section 5) |
| **Q7** | N7 Reality Check / SPA | `strategies/evaluate.py`, `strategies/alpha_zoo.py` | `bench_zoo` extension | S | - |
| **Q8** | N9 BOCPD | `strategies/regime.py`, `strategies/knife_guard.py` | `enable_bocpd` | S | optional |

Landing order: **Q1, Q2, Q3, Q4, Q5, Q7, Q6, Q8** - cheapest-and-closes-a-blind-spot
first, the largest structural gap (Q2) next, and the optional/evidence-softer items
last.

---

## 2. Phase detail

### Q1 - Quote-free spread estimators (N1)

**Target.** `strategies/liquidity_risk.py`: add `corwin_schultz(closes, highs, lows)`
and `abdi_ranaldo(...)`, both returning `{"spread": float, "basis": str, "n": int}`
or `None`. `strategies/execution_schedule.py`: `default_temp_impact(price, spread)`
used by `almgren_chriss` when `temp_impact` is not supplied.

**Behaviour.**
- Two-day range correction; when the corrected term is negative the estimator
returns `None` (the paper's own treatment) - never a clamped fake spread.
- Both estimators returned side by side; the aggregate is the median of the two
when both exist, else the single available one, and the result carries `basis`
("corwin-schultz" / "abdi-ranaldo" / "median(both)").
- Liquidity gate input: a name's daily cost floor in bps; the gate keeps its
verdict shape and gains a `spread_bps` line.
- The AC default replaces the caller-supplied `eta` **only when unset**, and the
tool output labels which basis was used.

**Acceptance.** On a synthetic series with a known spread the estimator recovers it
within tolerance; on a series with a negative correction it returns `None`; the gate
renders `spread_bps` and still returns its previous verdict for names with quotes.

### Q2 - Minimum-CVaR/CDaR sizing under the budget (N5 + C4)

**Target.** `strategies/book_risk.py`: `min_cvar_weights(returns_by_name, alpha,
cap, max_delta)` (Rockafellar-Uryasev, sample-average LP) and
`copula_scenarios(returns_by_name, n, nu, family)` (t / Clayton lower-tail joint
scenarios). `strategies/risk_governor.py`: a `sizing` remedy beside PASS/WARN/REJECT.

**Behaviour.**
- Objective: minimise `zeta + 1/((1-alpha)T) * sum(max(L_t(w) - zeta, 0))`; weights
bounded by the existing per-name cap and by `max_delta` against the current book.
- Output: target weights, the resulting book CVaR and CDaR, the binding constraint,
and the sample/scenario count. Never an order - advisory numbers only, like every
other sizing read.
- Degradation: below `min_scenarios` (default 60) the optimiser returns
`unavailable` and the governor keeps today's verdict-only behaviour.
- Copula scenarios replace the single fixed -10% shock **only** as an input to this
optimiser; `book_correlated_stress` keeps its current output for compatibility.

**Acceptance.** On a two-asset book with known asymmetries the optimiser lowers CVaR
against equal weights; the resulting weights respect both caps; below the scenario
floor it returns `unavailable` and the governor verdict is unchanged.

### Q3 - Conformal valuation bands (N2)

**Target.** `strategies/conformal.py` (new): `quantile_band(model, X, alpha)`,
`calibrate(scores, alpha) -> Q`, `rolling_band(pairs, window, alpha)`. Consumers:
`strategies/dcf.py` (band on the model output), `agents/utils/report_verifier.py`
(tolerance from the band), fundamentals tool `get_valuation_band`.

**Behaviour.**
- Fit on a proper-training window, calibrate on the most recent calibration window;
report `nominal`, `realized_coverage`, `window`, `n`.
- The verifier flags a valuation claim only when the claimed number sits **outside**
the calibrated band; inside the band is not a flag.
- Rendering always prints the realized coverage next to the nominal level; a band
without a realized-coverage line is a bug, not a display choice.
- `n` below a floor (default 40 pairs) yields `unavailable`.

**Acceptance.** Coverage on a held-out synthetic series is within tolerance of
nominal; a claim inside the band produces no verifier flag and a claim outside does;
small `n` degrades to `unavailable`.

### Q4 - Gross profitability and net operating assets (N3, N4)

**Target.** `dataflows/quantitative_scores.py`: `gross_profitability(fin)` and
`net_operating_assets(fin)` next to `piotroski_f_score` / `beneish_m_score`;
exposed through `strategies/normalized.py` and as screener columns.

**Behaviour.**
- `GP/A = (revenue - cogs) / total_assets`; `NOA = (operating_assets -
operating_liabilities) / total_assets_prev`.
- Missing COGS or a missing prior balance sheet yields `unavailable` with the reason
(otherwise the value would be silently different from the paper's definition).
- Each row states the classification used for the operating/financial split.

**Acceptance.** Values reproduce hand-computed examples; a financial with no COGS
returns `unavailable`; the value-dip floors can cite the row without changing any
existing verdict (the rows are informational until a phase decides otherwise).

### Q5 - Overnight/intraday decomposition (N8)

**Target.** `strategies/market_session.py`: `decompose_returns(opens, closes)`
returning intraday and overnight legs, their means/vols, and the share of variance
by leg; a market-analyst tool row.

**Behaviour.**
- `intraday_t = ln(C_t/O_t)`, `overnight_t = ln(O_t/C_{t-1})`; both reported with the
window length.
- Text states it is a **decomposition**, never a cause.
- Missing opens (vendor branch without the column) yields `unavailable` - the same
`fields_unavailable` convention the screener OHLCV path now uses.

**Acceptance.** Legs sum to the close-to-close log return within floating tolerance;
a series without opens returns `unavailable`; per-name output is stable on rerun.

### Q6 - Text factors: LM tone, readability, call-vs-filing divergence (N6)

**Target.** `strategies/text_factors.py` (new): `lm_tone(text)`, `readability(text)`
(Flesch-Kincaid grade and a fog index), `divergence(a, b)`; consumers
`agents/utils/news_data_tools.py` and a verifier cross-check for tone claims.

**Behaviour.**
- Dictionary version and word counts are always reported; no tone verdict without
its counts.
- `divergence` compares two documents the engine already holds for the same period
(call transcript vs filing) and reports tone and complexity gaps separately (the
2025 evidence treats their persistence differently).
- Absent text => `unavailable`, never `0.0`-as-neutral.

**Acceptance.** A known-positive and a known-negative snippet produce ordered tone
scores; a snippet with no dictionary hits is reported as zero-hit, not neutral; the
verifier cross-check produces a flag only when the LLM's tone claim contradicts the
computed sign at a stated threshold.

### Q7 - Reality Check / SPA (N7)

**Target.** `strategies/evaluate.py`: `reality_check(candidates, benchmark,
block_len)` and `spa(...)`; `strategies/alpha_zoo.py::bench_zoo` gains a row per run.

**Behaviour.**
- Stationary bootstrap over candidate return series; report the test statistic, the
p-value, the block length, and the number of candidates.
- Fewer candidates than the test can distinguish => `unavailable` with the reason.

**Acceptance.** A universe containing one genuinely superior candidate yields a
small p-value; a universe of pure noise does not (both directions exercised).

### Q8 - BOCPD (N9, optional)

**Target.** `strategies/regime.py`: `bocpd(series, hazard)` returning the run-length
posterior summary and the zero-run probability; `strategies/knife_guard.py` may
consume the alarm.

**Behaviour.** CUSUM/EWMA output is untouched; BOCPD is an additional read, gated
off by default. A break signal resets the window-based statistics (Hurst/VR/half-life)
for the *next* read, and that reset is stated in the output.

**Acceptance.** A series with a manufactured mean shift raises the zero-run
probability at the shift; a stationary series does not; the existing shift-detection
output is byte-identical when the new key is off.

---

## 3. Cross-cutting wiring

| Surface | Change |
| --- | --- |
| `default_config.py` | the five `enable_*` keys of section 1, all `False` |
| `strategy_overlays` | nothing changes in the fold order; Q5/Q6 rows are advisory reads |
| Toolsets | Q1 `get_liquidity_risk` (extra line), Q2 `get_book_risk_budget`, Q3 `get_valuation_band`, Q5 market tool, Q6 news tool |
| Reports | each new read renders its basis line; no verdict text is authored by a formula |
| `report_verifier` | Q3 tolerance replaces the hand-set valuation tolerance when enabled; Q6 adds a tone cross-check |
| `docs/api_reference.md` | new config keys and tools added to the canonical tables in the same commit |

---

## 4. Test and mutation matrix

| Phase | Test file | Gates | Mutations that must break them |
| --- | --- | --- | --- |
| Q1 | `tests/test_liquidity_spread.py` | known-spread recovery; negative correction => `None`; gate verdict unchanged with quotes; AC default only when unset | drop the 2-day correction; clamp instead of `None`; use the default when `temp_impact` is supplied |
| Q2 | `tests/test_book_risk_sizing.py` | CVaR falls vs equal weights; caps respected; `unavailable` below the floor; governor verdict unchanged when disabled | remove the `max_delta` bound; ignore the scenario floor; let the optimiser emit weights when disabled |
| Q3 | `tests/test_conformal_bands.py` | coverage within tolerance; inside-band claim is not flagged; outside-band is; small `n` degrades | widen the band by a constant; drop the calibration step; flag inside-band claims |
| Q4 | `tests/test_quality_factors.py` | hand-computed GP/A and NOA; missing COGS => `unavailable`; classification line present | substitute operating income for COGS; use current instead of prior assets |
| Q5 | `tests/test_return_decomposition.py` | legs sum to close-to-close; no-opens => `unavailable`; deterministic rerun | use intraday twice; fabricate a zero overnight leg |
| Q6 | `tests/test_text_factors.py` | positive vs negative ordering; zero-hit vs neutral; divergence signs | constant offset on tone; map zero hits to neutral |
| Q7 | `tests/test_reality_check.py` | superior candidate detected; pure-noise universe not detected; block length reported | shuffle within blocks; drop the bootstrap |
| Q8 | `tests/test_bocpd.py` | shift raises the zero-run probability; stationary series does not; off => byte-identical output | disable the hazard update; always return the prior |

Every test file is proven failing under its mutation list before the phase is
considered landed, and the full suite plus `ruff check .` must be green per commit.

---

## 5. Risks, non-goals, and the one open decision

- **Risk: estimator bias.** High-low spread estimators are upward-biased on gap days
and thin names; the liquidity gate must treat them as a *floor* and keep the quoted
path authoritative when quotes exist.
- **Risk: optimiser instability.** LP solutions on short samples overshoot; the
`max_delta` bound and the scenario floor are the guardrails, and the remedy is
advisory, never an automatic position change.
- **Risk: conformal coverage in a non-exchangeable world.** Covered by always
printing realized coverage beside the nominal level; a bare nominal number is a bug.
- **Non-goals.** No execution, no order generation, no new vendor, no change to the
risk-gate verdict semantics, no re-implementation of anything in the design doc's
exclusion table (variance ratio, CUSUM, entropy, Ohlson, Dechow-Dichev, AC, vol
target, MAX/IVOL, copula-planned-in-quantlib aside from Q2's scenario input).
- **Open decision (owner):** Q6 needs a text source for filings/call transcripts.
Recommended: use the documents the news analyst already fetches for the symbol
(`seekingalpha` / `eodhd` paths) rather than adding a vendor, and restrict
`divergence` to periods where both documents are present - which keeps the item
vendor-free and honest about coverage.

---

## 6. Verification per landed phase

1. New tests written, then **proven failing** with the mutation applied and reverted.
2. Affected subset run, then the full suite (`py -3.12 -m pytest tests/ -q -p no:randomly`)
plus `py -3.12 -m ruff check .`.
3. CHANGELOG entry with the web impact when a consumed shape changes.
4. `docs/api_reference.md` updated for any new key or tool.
5. Commit + push per phase; no phase is left partially landed.
