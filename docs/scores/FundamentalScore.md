# FundamentalScore — design

**Part of the score-engine design set: [`docs/scores/README.md`](README.md)** (the
master document — architecture, cross-engine contracts, the composite, the phase
plan and the open questions). Sibling documents:
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`SentimentScore.md`](SentimentScore.md),
[`EventScore.md`](EventScore.md), [`RiskScore.md`](RiskScore.md).

**Scope of this document: the fundamental engine only.** It designs the
`FundamentalScore` — the 106-factor fundamental weight master table as an
adoption plan against what the engine already computes. The other six engines are
specified in their own documents; the composite they feed, the cross-engine
rules, and the code defects the whole set found are in the master.

Status: **design (2026-09-17), decisions recorded. Not started.** Nothing in
this document is implemented; it defines what would be built, in what order,
under which gates, and — more importantly — what is **already** in the engine so
that no second implementation is created. **All five open questions were answered
by the owner on 2026-09-17**: §0.5 summarises each decision and where it lands;
the full record with the rationale is in the master's decision record.

Source: an external, LLM-authored answer proposing a **106-factor fundamental
weight master table** in ten categories with "starting production weights"
(preserved verbatim in Appendix A). It cites no primary literature. This
document treats its **structure** as the proposal and its **numbers** as
hypotheses to be measured, per the repo's own rule 2
([`design_quant_formulas_research_round3.md`](../design_quant_formulas_research_round3.md):
*"No weight vector is invented"*).

Audience: whoever implements the fundamental engine. Read §1 and §2 before §3 —
the engine already computes most of this table, and §2 says exactly which third.

Related: [`design_quant_formulas_research.md`](../design_quant_formulas_research.md)
(round 1), [`design_quant_formulas_research_round2.md`](../design_quant_formulas_research_round2.md),
[`design_quant_formulas_research_round3.md`](../design_quant_formulas_research_round3.md)
(round 3 — the composite/normalisation round, §S3 is this document's closest
prior art), [`implementation_plan_quant_formula_additions_round3.md`](../implementation_plan_quant_formula_additions_round3.md)
(its phased plan and the inherited ground rules),
[`design_institutional_value_dip_workflow.md`](../design_institutional_value_dip_workflow.md)
(funnel-over-single-score constraint),
[`design_report_verification_llm.md`](../design_report_verification_llm.md).
The owner's own specification of record is preserved verbatim in
[`../ScoreWeight/fundamental.md`](../ScoreWeight/fundamental.md).

---

## 0. Method

---

### 0.1 What the source is, and what is wrong with it

The proposal's content is a weight table: ten categories (Profitability 18%,
Growth 15%, Cash Flow 17%, Valuation 20%, Balance Sheet 10%, Earnings/Accounting
Quality 8%, Capital Efficiency 4%, Capital Returns 4%, Distress 2%, Insider 2%),
106 factors with individual weights, each carrying a direction, a normalisation
rule, and a redundancy group. It then proposes a four-sub-score decomposition
(FQS/FGS/VS/FRS), an `EffectiveWeight = Base × Sector × DataQuality ×
Stability × Redundancy` multiplier chain, an A/B/C/D confidence table, a
correlation penalty `1/(1+Σ|Corr|)`, a `DCFConfidence` product, and a four-phase
implementation order ending in walk-forward-learned weights.

Three things are wrong or unproven at the level of arithmetic and evidence, and
they are the reason this document adopts the structure and not the numbers:

1. **The per-factor weights do not sum to the stated category totals.** As
   written, they sum to **104.00%**, not 100%: Cash Flow is 19.00 against a
   stated 17%, Valuation 21.25 against 20%, Earnings Quality 8.50 against 8%,
   Growth 15.25 against 15%. Four categories are internally inconsistent before
   anything is measured. (Verified by summing the source tables; Appendix A.2
   reproduces the check.)
2. **No weight is justified by any measurement.** The source says so itself
   ("starting production weights, not claimed to be universally optimal") and
   then, in its own Phase 1, asks for them to be shipped as production. The
   engine's ground rule 2 already refuses this: either a source publishes
   weights, or the item uses equal weights with the renormalise-over-present
   rule and **says so in its output**.
3. **The highest-weighted category is the one the engine is furthest from
   computing.** Of the proposed 104% of weight, the repo computes factors
   carrying **42.15 points**, partially computes **20.35**, and has nothing for
   **41.50** — and the largest single hole is Cash Flow (11.00 of 17 points
   absent) plus Balance Sheet (6.75 of 10 absent), while Valuation is
   the *most* complete category (13.25 of 20 computed). Ranked by "weight we
   cannot yet compute", the source's own priorities are inverted relative to
   what is implementable first.

---

### 0.2 Status vocabulary (used by every table in §2)

Read at the definition site; no fetch was executed.

| Status | Meaning |
| --- | --- |
| **COMPUTED** | A repo function computes the value from canonical line items, and it reaches at least one tool leaf, screen row, or score. |
| **PARTIAL** | One of: (a) computed only inside another ratio's internals and never exposed; (b) available only as a boolean/binary sub-score, not as a factor value; (c) surfaced only as a raw vendor passthrough with no repo-side computation. |
| **ABSENT** | No implementation found in `tradingagents/` or `scripts/`. |

---

### 0.3 Ground rules this design inherits (non-negotiable)

Inherited verbatim from round 2 by way of round 3, restated because they bind
this document:

1. **Deterministic first.** Every formula is a pure function over inputs the
   repo already fetches; no score lives in a prompt.
2. **One implementation per computation.** Extend the module that already owns
   the measure.
3. **No fabrication.** A missing input yields `unavailable`/`None`, rendered as
   "unavailable". Every score prints its basis (metric set, coverage, variant,
   window).
4. **Gates must be able to fail.** Each new test is proven failing under a
   targeted mutation of the code it guards.
5. **Default-off or existing flag.** New behaviour sits behind a config key that
   defaults to off.
6. **A score is not a rating.** Nothing here may feed
   `strategies/decision_guardrail.py::SCORE_BANDS`.
7. **No new vendors, no new models, no execution.**
8. **CHANGELOG + web impact.**
9. **Symmetry is measured, not assumed.**
10. **Dark launches are measured, not assumed** — one gate at a time, in a
    labelled run, diffed against a gate-off run on the same basket, using
    `scripts/repro_check.py --evidence`, `scripts/report_verify.py`, and
    `scripts/verify_sweep.py`.

---

### 0.4 External evidence used for the accept/reject calls

The source cites nothing; the following are the load-bearing findings this
document leans on when it accepts or refuses an item. Full ledger in Appendix C.

| Claim used here | Evidence |
| --- | --- |
| Equal weights are a hard baseline to beat out-of-sample; estimated optimal weights are usually worse than `1/N`. | DeMiguel, Garlappi & Uppal (2009): across 14 optimisation models and 7 datasets, none consistently beat `1/N` on Sharpe, certainty-equivalent return or turnover; estimation error dominates the diversification benefit. Supports **equal-weight-first**, not "starting production weights". |
| Signal weighting by quality (IC / rank IC, covariance-aware) is standard; `IR ≈ TC·IC·√BR`. | Grinold–Kahn's Fundamental Law; rank IC is the robustness-preferred form (Spearman). Supports **Phase C before Phase D** — measure IC per factor, then weight. |
| "Quality" is a four-pillar construct: profitability, growth, safety, payout; and quality is strongest when *not* overpriced. | Asness, Frazzini & Pedersen, *Quality Minus Junk*: `quality = z(Profitability + Growth + Safety + Payout)`; lower prices for quality names predict higher returns. Directly supports the source's Q/G/BS/payout split **and** its insistence that valuation is not allowed to be cancelled by quality. |
| Gross profitability beats earnings-based profitability and subsumes ROE. | Novy-Marx (2013): GP/A has roughly book-to-market's predictive power and "completely subsumes" earnings-based measures. Supports the source's GP/A ≥ ROE ordering (2.5% vs 2.0%) — one of the few weight orderings with literature behind it. |
| Aggressive investment / asset growth predicts weak subsequent returns. | Titman, Wei & Xie (2004); Cooper, Gulen & Schill (2008). Supports treating asset growth and capex as **risk flags, not short signals** — exactly the asterisk the source puts on both. |
| Insider trades are only informative when non-routine. | Cohen, Malloy & Pomorski: routine trades (same calendar month ≥3 consecutive years) have ~zero predictive power; opportunistic-only portfolios earn 82 bps/month value-weighted. Supports keeping the insider category small **and** the real lever being the discretionary/compensation split, which needs Form 4 transaction-code XML (already a deferred data-source project). |
| Terminal value is 60–80% of a DCF and a 50bp error in WACC or `g` moves value ~10–20%. | Practitioner consensus across valuation sources. Supports a **confidence-scaled** DCF weight rather than a fixed one, and quantifies why. |
| Accruals are less persistent than cash flows; high-accrual firms underperform. | Sloan (1996). Supports the Earnings-Quality category's direction conventions (already implemented as `normalized.accruals_ratio`). |
| Correlated factors must be clustered/orthogonalised or their weights inflate. | Standard factor-combination practice: measure pairwise correlation, cluster, orthogonalise, then weight by unique predictive value; naive summation of correlated factors inflates exposure to one latent driver. Supports the **redundancy penalty as structure** while rejecting the source's specific `1/(1+Σ|Corr|)` constant as untested. |
| Published predictors decay: ~26% out-of-sample, ~58% post-publication. | McLean & Pontiff (2016), 97 predictors. Supports refusing fitted weights that are validated on one sample, and the repo's existing DSR/PBO discipline. |
| Factor timing is deceptively difficult; conditional weights rarely improve robustly. | Asness, Chandra, Ilmanen, Israel & Moskowitz. Supports **refusing** the source's Phase-4 learned/regime weights without an owner decision. |
| Bank valuation = P/B through ROE/ROTCE, NIM, CET1; REIT valuation = P/FFO, P/AFFO, NAV, not GAAP earnings. | Sector-valuation consensus. Supports the *existence* of sector overlays but shows the required metrics are not in the canonical vocabulary (Appendix B). |

---

### 0.5 Recorded decisions (owner, 2026-09-17)

The five questions this design opened are closed. Each decision is stated with
the section it changes; §8 carries the full rationale.

| # | Question | Decision | Where it lands |
| --: | --- | --- | --- |
| Q1 | Does the composite reach `opportunity_score`? | **Never, for now.** It stays a tool-leaf / `run_card` advisory metric. `opportunity_score` keeps its `null` and gains a published *reason* — a deterministic `FundamentalScore = 84` does not mean `Opportunity = 84`; those are different questions, and the executor treats the second as a validated 0-100 measurement | §3.1, §5.2 |
| Q2 | Learned walk-forward weights? | **Yes, as a separate research layer — never in the deterministic production score.** Promotion is a ladder: `RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION`, each step evidenced, none automatic | §3.1, §6 Phase D |
| Q3 | Sector overlays? | **Architecture in scope now, suppliers deferred.** The factor schema carries `sector_scope`/`supplier`/`availability` from day one; bank/REIT metrics are `NA` until a supplier exists — **`NA ≠ 0`**, and missing data reduces the *available* weight instead of punishing the name | §3.2; architecture decided in the master's decision record |
| Q4 | Evaluation universe? | **The full EODHD US panel** is the official validation universe. The named basket stays a dev/diagnostic set and is labelled `INSUFFICIENT_CROSS_SECTION` — it may never produce authoritative factor weights | §6 Phase C |
| Q5 | `factor_score=NN` in prose? | **No.** Scores live in structured output (`fundamental_score`, `fundamental_score_status`, `fundamental_score_confidence`); narrative states quality in words. A number in prose becomes apparent objective ground truth and turns an advisory composite into a quasi-official measurement | §3.1, §5.3 |

**The three-stage separation this produces** (owner's framing): `RESEARCH`
(factor measurements: IC / rank IC, decile spreads, stability, redundancy) →
`SCORE ENGINE` (deterministic weights → *ProductionScore*; learned weights →
*ResearchScore*) → `run_card` advisory. **Never automatically
`opportunity_score`.**

**The score contract** (§3.1): `FundamentalScore`, `TechnicalScore`,
`RegimeScore` and `RiskScore` are deterministic 0-100 **advisory** composites
that feed the decision/risk engine; `OpportunityScore` is a **separate validated
measurement** and stays `null` until empirical validation establishes it.

**Added 2026-09-17 (second pass): the score engines have their own documents.**
The owner's staged `docs/ScoreWeight/{fundamental,market,news_sentiment}.md` refine
the four-score version to **six engines plus a recommended seventh**
(Fundamental, Technical, Regime, News, Sentiment, Risk, + Event), with a research
allocation of 35 / 20 / 15 / 7.5 / 7.5 / 15 and EventScore's weight still open.
Where the staged weights differ from the first iteration they govern, and the
superseded numbers are kept in the tables for the record. This document now
covers **only** the fundamental engine; the architecture, the composite and the
open questions are in [`README.md`](README.md), and each other engine is in its
own document beside this one. Each is a
separate 0-100 score, all in the **same direction (100 = favourable, so
`RiskScore` 100 = low risk)**, and only then combined:
`TradeScore = 0.40·F + 0.25·T + 0.15·R + 0.20·K`, which **never overrides a hard
gate** and whose weights are learned empirically later (§6 Phase D). The
governing sentence is *"do not mix them into one score too early"* — the
evidence for keeping the dimensions separate (and for a regime **score** being
distinct from the regime **sizing scale**) is in [`README.md`](README.md) and
its evidence ledger.

---

---

## 1. What already exists (read this before designing anything)

---

### 1.1 The four tiers

Scores in this engine are built in four independent tiers and never compose into
one master number:

| Tier | What it is | Where |
| --- | --- | --- |
| 0 — point scores | Self-contained published formulas over canonical statements: Beneish M (with `_M_WEIGHTS`), Altman Z + Z'/Z''/Z''-EM variants and zones, Piotroski F (plain + paper-basis detailed), Ohlson O, Zmijewski X, Sloan accruals, GP/A, NOA, Tobin's Q, earnings yield, Acquirer's multiple, Mohanram G, Montier C, Graham/NCAV/EPV, CapEx-quality 0-100, earnings-quality verdict | `dataflows/quantitative_scores.py`, `strategies/normalized.py`, `strategies/capex_quality.py`, `strategies/earnings_quality.py`, `strategies/fundamental_floors.py` |
| 1 — normalisation | `winsorize(1/99)` → `cross_sectional_z` / `industry_neutral_z` (winsorise → demean by sector → z) → `centered_rank` / `quantile_split`; plus `group_median(min_n=5)` for sector medians | `strategies/cross_section.py` |
| 2 — composites over a peer panel | `composite_score` and `value_momentum_score` (percentile-rank means), `z_composite_alpha` (`Σ a_k·z_k`), and `quality_composite` (the round-3 S3 fundamental composite) | `strategies/factors.py` |
| 3 — surface | `get_composite_rank` (peer set = ticker + 8 Finnhub peers), the screener's `--rank composite`, and the gated `quality composite TICKER: NN/100 (band)` row | `agents/utils/analysis_tools.py`, `scripts/value_screener.py` |

Rating/decision flow is a **separate axis**: analyst prose →
`rating.parse_rating` → 5-tier label → `decision_guardrail.stabilize_decision`
(downgrade-only) → `PortfolioDecision.rating` → `research_decision.json`.

Evaluation is a **third axis**: rating-stance IC/dispersion/decay over the alpha
ledger (`alpha_health` + `scripts/alpha_health.py`, reading
`reports/*/research_decision.json`), price-expression IC/OOS/walk-forward/CPCV/DSR
(`alpha_zoo.bench_zoo` + `evaluate.py`), and generic score-panel IC for any
`{date: {ticker: score}}` panel (`alpha_health.score_evaluation_rows`).

---

### 1.2 The three surfaces this design has to reach, and the four that are empty

| Existing surface | Path:line | Relevance |
| --- | --- | --- |
| `quality_composite` — the only fundamental composite | `strategies/factors.py:248` | The exact chain to reuse: winsorise → z → direction sign → coverage-gated weighted mean → tie-aware percentile ×100. Weights are **caller-supplied only**; the basis string prints `"no weight vector published, equal weights used"`. |
| `QUALITY_DIRECTIONS` | `strategies/factors.py:205` | Seven metrics (`f`, `m`, `z`, `o`, `gp_a`, `noa`, `accruals`) with published signs. The seed of any larger factor catalogue. |
| `QUALITY_BANDS` | `strategies/factors.py:192` | 70 elite / 60 above-average / 50 sector median / 40 below-average / 20 poor. Note the 50 band is labelled "sector median" but the percentile is taken across the whole peer set — a real defect this design must not inherit (§3.4). |
| `_coverage_floor` + `withheld` | `strategies/factors.py` | The existing honest-missing-data policy: a name below the coverage floor is **withheld with a reason**, never scored. |
| `peer_universe.resolve_peer_universe` | `strategies/peer_universe.py` | The reference universe (EODHD US common stock filtered NYSE/Nasdaq, or an explicit list), metrics via `screen_ticker` + `normalized.ohlson_o_score`/`accruals_ratio`. |
| `alpha_health.score_evaluation_rows` | `strategies/alpha_health.py:440` | **The ready-made IC harness**: IC + ICIR, deciles + monotonicity, coverage, stability over an arbitrary score panel. Gated `enable_score_eval_rows` (default False, `default_config.py:1048`). No caller builds a fundamental panel today. |
| `evaluate.purged_cpcv_splits` / `deflated_sharpe` / `pbo_flag` / `reality_check` / `spa` | `strategies/evaluate.py` | Multiple-testing discipline, already available, unused on fundamentals. |
| `data_quality.aggregate_quality` + `disagreement_flag` | `strategies/data_quality.py:40` (`_INPUT_WEIGHT:24`, `disagreement_flag:74`, `fundamentals_pit_ok:96`) | The DataQuality multiplier's source: per-input weights (price 22, volume 15, fundamentals 22, news 14, options 12, macro 15) with missing inputs excluded and renormalised, plus cross-vendor spread flagging. |

Empty slots, all deliberate:

| Empty slot | Path:line | What it means for this design |
| --- | --- | --- |
| `opportunity_score` — declared 0-100, **always `null`** | `tradingagents/execution_contract.py:240-252` | The executor already validates a 0-100 producer-owned scale (`../TradingExecution/signald/contracts.py:215-227`). The docstring records the decision: publishing an estimate under a field the executor may rank on "would dress an estimate up as a measurement". **Wiring a fundamental composite here was an owner decision and is now answered: never, for now (Q1).** The slot keeps its `null` and gains a producer-owned reason string (§5.2). |
| `decision_guardrail.SCORE_BANDS` | `strategies/decision_guardrail.py:27` | The 0-100 ↔ rating contract; its only caller passes `None` (`agents/managers/portfolio_manager.py:364`). Ground rule 6 forbids this design from feeding it. |
| `quant_baseline.quant_signal` | `strategies/quant_baseline.py:74` | The only `{category: score}` dict in the repo (momentum/value/quality/trend/volatility with keyword weights) — computed but **unwired**; tests only. It is the shape template for §3.1, not a component. |
| `run_card["sections"]` | `tradingagents/reporting.py:1455` | Hard-coded `[]`, no reader anywhere. Not a usable slot. |
| `get_vif_read` | `agents/utils/analysis_tools.py:8213` | Measures VIF, but only over **technical** factor columns (`rsi`/`mom`/`bias`/…) from OHLCV. There is no fundamental-factor collinearity measure. |

---

### 1.3 The wiring gaps that matter more than the missing formulas

> **Status 2026-09-17: the four defects found by this inventory are FIXED** (see
> §1.4). The table below is kept as the record of what the gaps were and how
> large each fix is; the two structural defects in it — `roa_series` /
> `revenue_series` having no producer, and the mislabelled quality band — are
> closed. The remaining rows are **capability gaps** (values the engine does not
> yet compute), not defects, and are §3.6's ranked work.

The dominant pattern in the inventory is not "the engine lacks the inputs" — it
is **values computed and never exposed**, and **canonical keys with no
consumer**. Each of these is a small, high-value fix and several are
prerequisites for factors in §2:

| Gap | Evidence | Fix size |
| --- | --- | --- |
| Level ROIC (NOPAT / invested capital) | `invested_capital = debt + equity − cash` is already built per year at `agents/utils/value_dip_tools.py:435-513` but consumed only as the denominator of the 3-year ΔIC; a local `roic` is computed at `value_dip_tools.py:1342` and passed into `earnings_power_value(..., roic=...)` for an excess-ROIC check, never rendered | small — the level is a division away |
| Gross margin, current + prior | computed and stored at `dataflows/statement_parsing.py:841`; consumed by Piotroski (`f_dmargin`), Beneish (GMI) and the C-score; **no leaf renders it** | small — expose an existing value |
| Interest coverage | canonical alias `"interest_expense"` exists (`statement_parsing.py:105`) and is named in the `quantitative_scores.py` vocabulary docstring (`:32`); **no code reads the key** (grep: those two mentions are the only hits in `tradingagents/` + `scripts/`) | small — pure wiring |
| Working capital / assets | `canonical["working_capital"]` is built at `statement_parsing.py:1134-1139` with provenance; consumed only inside Altman X1 and Ohlson WCTA | small |
| Debt growth (numeric) | only the Piotroski `f_dlever` boolean exists | small |
| Asset growth (numeric) | only `overpriced_score` C6's `>0.10` boolean | small |
| Receivable-days / inventory-days | DSRI is an internal Beneish input; the C-score's C2/C3 are booleans | small |
| `roa_series` / `revenue_series` | read by `growth_metrics` (`quantitative_scores.py:786-818`) for G-Score G4/G5; **no producer exists anywhere**, so those legs are structurally dead and always emit "5-year ROA series unavailable" | **FIXED 2026-09-17 — §1.4** |
| 5Y CAGRs beyond revenue | `capex_quality._cagr(min_span=5)` needs ≥6 annual points; vendor history is ~4-5 years; `sec_edgar.get_financial_history` gives up to 15 years for US filers (tool at `analysis_tools.py:8783`) but **does not feed the CAGR path** | medium — the series producer now exists (§1.4); wiring SEC XBRL into it is the remaining step |
| Dechow-Dichev AQ | `earnings_quality.dechow_dichev_aq` needs ≥6 periods; the tool feeds a synthetic all-zero accruals list (`analysis_tools.py:4985-4993`) so it always returns `n/a` | **FIXED 2026-09-17 — §1.4** |
| Screener docstring vaporware | `scripts/value_screener.py:15,19` advertises "Magic Formula Return on Capital" and "Shareholder Yield"; **no implementing symbol exists** | **FIXED 2026-09-17 — §1.4** (docstring corrected; the two screens remain unbuilt and are §3.6 work) |

---

### 1.4 The four defects this design's inventory found, and how they were fixed

All four were fixed on sight on 2026-09-17 (owner standing order 10) with
regression tests; no score semantics changed.

| # | Defect | Fix | Test |
| --: | --- | --- | --- |
| 1 | `roa_series` / `revenue_series` had **no producer**, so the G-Score's G4/G5 legs could never compute (always "5-year ROA series unavailable (n=0)") | New `statement_parsing.annual_series` (+ `_period_canonicals`, `_period_token`): stacks one canonical dict per fiscal year through `_flat_canonical` — the same row matcher the merged payload uses — merging a moomoo payload's per-statement tables by year, deriving `roa_series` on **beginning-of-year** assets aligned **by fiscal year** (the convention `growth_metrics` uses for the ROA level), and never splicing one key's values across payloads. `fetch_ticker` attaches the four series (`revenue`, `net_income`, `total_assets`, `operating_cashflow`) with provenance naming the period span and re-using `_period_kind` | 7 in `test_statement_parsing.py`, incl. the moomoo year-merge, the cross-payload year join, the gap rule, and the producer→G-Score integration. **Live 2026-09-17:** MSFT/AAPL carry 5 series keys over 4 annual periods (`roa_series` n=3), all `annual`, no conflicts - so G4/G5 remain excluded on vendor history alone (4 < 5 periods) with an honest `n`; wiring SEC XBRL (15 years) into the producer is the unlock |
| 2 | `QUALITY_BANDS`' 50 band said **"sector median"** while the percentile is taken across the scored **peer set** | Renamed to "peer median"; the source table's label is quoted in the comment with the reason it does not apply. A within-sector percentile stays a design item (§3.2) | `test_quality_composite.py::test_bands_are_the_quality_bands_not_the_decision_rating_bands` |
| 3 | `scripts/value_screener.py`'s docstring advertised **Return on Capital** and **Shareholder Yield** with no implementing symbol | Docstring now marks both as not implemented, names the missing inputs (`invested_capital`; the `share_buybacks`/`debt_repayment` keys with no reader), and points at §3.6 | docstring only (no code claim left) |
| 4 | The Dechow-Dichev caller required `operating_cashflow` to be a **dict of ≥6 keys** — a shape the merge never produces — and fed an **all-zero accruals list** when it did fire | Reads the series from #1, accruals on the Sloan proxy `(NI − CFO) / total assets`, with the substitution printed beside the value. `DD_MIN_PERIODS = 8` now states the real bar (6 residual rows need n−2 ≥ 6), used by both the function and the caller, and the n/a text names it | 3 in `test_analysis_tools.py` (a perfect-fit value, the 7-period refusal, and a guard that a multi-key cash-flow dict no longer produces a number) + 1 in `test_quant_p4_accounting.py` |

**Not fixed, deliberately:** the two screens in #3 are *features* (they need an
invested-capital basis decision — the same basis problem the DCF bridge had —
and a shareholder-yield definition), not doc defects; they stay ranked in §3.6.
The remaining §1.3 rows are capability gaps of the same class.

---

## 2. The adoption ledger — all 106 factors against the engine

Legend: **C** = COMPUTED, **P** = PARTIAL, **A** = ABSENT (§0.2). "Prop. wt"
is the source's weight **as written**. `file:line` is the definition site of the
existing implementation.

---

### 2.1 Profitability / Quality — proposed 18.00, as-written 18.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 1 | ROIC (NOPAT/invested capital) | 3.00 | **A** | level absent; only ΔNOPAT/ΔIC exists (`strategies/capex_quality.py:184`) |
| 2 | ROE | 2.00 | **C** | `strategies/ratios.py:203` (`return_on_equity`); screen row `roe` (`statement_parsing.py:1289`); DuPont leaf `get_dupont_read` (`analysis_tools.py:3242`) |
| 3 | ROA | 1.50 | **C** | `strategies/ratios.py:204`; internal `fin["roa"]` (`statement_parsing.py:827`) |
| 4 | Gross Profit / Assets | 2.50 | **C** | `quantitative_scores.gross_profitability:299`; leaf `gp_a=` (`quant_format_tools.py:203`) |
| 5 | Operating margin | 2.00 | **P** | vendor passthrough only (`y_finance.py:396`, Finnhub `operatingMargin*`) |
| 6 | Gross margin | 1.50 | **P** | computed at `statement_parsing.py:841`, never rendered |
| 7 | EBITDA margin | 1.00 | **A** | EBITDA only as an intermediate for `ev_ebitda` (`ratios.py:162`) |
| 8 | EBIT margin | 1.00 | **P** | series built inside `normalized.median_norm_ebit:24`, never exposed |
| 9 | FCF margin | 1.50 | **A** | — |
| 10 | Operating-margin stability (−std) | 1.00 | **A** | no std of any margin series anywhere |
| 11 | Gross-margin stability (−std) | 0.50 | **A** | — |
| 12 | ROIC stability (−std) | 0.50 | **A** | — |

---

### 2.2 Growth — proposed 15.00, as-written 15.25

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 13 | Revenue growth YoY | 2.00 | **C** | `statement_parsing.sane_revenue_yoy:755`; leaf `Revenue YoY` (`analysis_tools.py:1430`) |
| 14 | Revenue CAGR 3Y | 1.50 | **A** | no 3-year CAGR anywhere |
| 15 | Revenue CAGR 5Y | 1.00 | **C** | `capex_quality_read` key `rev_cagr5` (`capex_quality.py:252`), leaf `Rev CAGR5=` (`value_dip_tools.py:571`); needs ≥6 annual points |
| 16 | EPS growth YoY | 1.50 | **C** | `statement_parsing.sane_eps_yoy:735` (vendor-sourced, degenerate-base guard >300% nulled) |
| 17 | EPS CAGR 3Y | 1.00 | **A** | no EPS series exists |
| 18 | EPS CAGR 5Y | 0.75 | **A** | — |
| 19 | FCF growth YoY | 1.50 | **A** | `fcf_growth` is a caller-supplied argument to `earnings_quality_verdict`; no producer |
| 20 | FCF CAGR 3Y | 1.25 | **A** | — |
| 21 | EBITDA growth | 0.75 | **A** | no EBITDA series |
| 22 | EBIT growth | 0.75 | **A** | EBIT enters only as per-year `nopat` inside `capex_quality` |
| 23 | Operating-income CAGR | 0.75 | **A** | — |
| 24 | Margin expansion | 1.00 | **P** | Piotroski `f_dmargin` (`quantitative_scores.py:679`) is boolean; `get_financial_trends` renders the cells a reader can difference |
| 25 | FCF margin expansion | 0.75 | **A** | — |
| 26 | Growth quality (FCF/EPS growth) | 0.75 | **A** | — |

---

### 2.3 Cash Flow — proposed 17.00, as-written 19.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 27 | FCF yield | 3.00 | **C** | `value_dip.fcf_yield:153`; leaf `get_fcf_yield` (`value_dip_tools.py:380`); also `capex_quality` key `fcf_yield` (`capex_quality.py:247`) |
| 28 | OCF yield | 1.00 | **A** | only FCF/mcap exists |
| 29 | FCF margin | 1.50 | **A** | — |
| 30 | OCF margin | 1.00 | **P** | printed as `cash_margin=` by `get_normalized_fcf_dcf` (`analysis_tools.py:2842`) |
| 31 | FCF / net income | 2.00 | **A** | only the OCF/NI variant exists |
| 32 | OCF / net income | 1.00 | **C** | `earnings_quality_verdict` key `cash_conversion` (`earnings_quality.py:103`), leaf `cash_conversion=` |
| 33 | FCF / EBITDA | 1.00 | **A** | — |
| 34 | OCF / EBITDA | 0.50 | **A** | — |
| 35 | CapEx / revenue | 1.00 | **C** | `capex_quality_read` key `cap_rev` (`capex_quality.py:248`); also `capex_intensity` in `growth_metrics` |
| 36 | CapEx / OCF | 1.00 | **A** | inverse computed as `funding = OCF/\|capex\|` (`capex_quality.py:173`) |
| 37 | FCF stability (−std) | 1.00 | **P** | `cycle_dcf.normalized_cycle_fcf:23` gives median/min/max/mean/n, not std (`analysis_tools.py:4455`) |
| 38 | FCF CAGR 5Y | 1.00 | **A** | — |
| 39 | Cash-conversion stability | 0.50 | **A** | — |
| 40 | Accrual-adjusted FCF | 0.50 | **A** | accruals exist as a standalone ratio, not as a FCF adjustment |
| 41 | Maintenance-CapEx FCF | 1.00 | **C** | `normalized_fcf.maintenance_fcf:81` (= OCF − D&A), leaf `maintenance_fcf=` |
| 42 | Normalized FCF yield | 2.00 | **A** | normalized FCF is only ever a DCF numerator, never divided by mcap |

---

### 2.4 Valuation — proposed 20.00, as-written 21.25

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 43 | P/E | 2.00 | **C** | `ratios.compute_ratios:198`; historical series via `get_valuation_z_score` |
| 44 | Forward P/E | 1.50 | **P** | vendor passthrough (`y_finance.py:382`); computed for ETFs (`strategies/etf_valuation.py:148`) |
| 45 | PEG | 1.50 | **P** | vendor passthrough (`y_finance.py:383`); `forward_peg` is a `value_dip` input only |
| 46 | EV/EBIT | 2.00 | **C** | `quantitative_scores.acquirers_multiple:260`; screen row `ev_ebit`; ratios key |
| 47 | EV/EBITDA | 1.50 | **C** | `ratios.compute_ratios:195` |
| 48 | EV/Sales | 0.75 | **C** | `ratios.compute_ratios:197` |
| 49 | P/S | 0.75 | **C** | `ratios.compute_ratios:200` |
| 50 | P/B | 0.75 | **C** | `ratios.compute_ratios:199` |
| 51 | P/CF | 1.00 | **C** | `ratios.compute_ratios:201` |
| 52 | Price / FCF | 1.50 | **C** | `ratios.compute_ratios:202` |
| 53 | FCF yield | 2.00 | **C** | see #27 (duplicate of #27 in the source's own table — a redundancy the source flags) |
| 54 | Earnings yield | 1.00 | **C** | `quantitative_scores.earnings_yield:251` (EBIT/EV); leaf `EY` |
| 55 | EV / FCF | 1.00 | **A** | — |
| 56 | DCF upside | 1.50 | **P** | `normalized.margin_of_safety:104` needs a caller-supplied intrinsic; `get_margin_of_safety` leaves print `price/fv` |
| 57 | Normalized DCF upside | 1.50 | **P** | `get_normalized_cycle_dcf` prints `MoS(fv-basis)`; `get_normalized_fcf_dcf` prints no upside line |
| 58 | PEG-adjusted FCF | 0.50 | **A** | — |
| 59 | EV/FCF growth | 0.50 | **A** | — |

---

### 2.5 Balance Sheet — proposed 10.00, as-written 10.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 60 | Net debt / EBITDA | 1.50 | **A** | no EBITDA denominator anywhere; `net_debt` exists only as a DCF bridge line |
| 61 | Debt / equity | 1.00 | **C** | `ratios.compute_ratios:205`; `value_dip.balance_sheet_health:381` leaf |
| 62 | Debt / assets | 0.75 | **A** | only the Piotroski `f_dlever` boolean; the moomoo vendor filter is server-side |
| 63 | Net debt / FCF | 1.00 | **A** | — |
| 64 | Interest coverage | 1.00 | **A** | alias exists (`statement_parsing.py:105`), zero consumers |
| 65 | Current ratio | 0.75 | **C** | `ratios.compute_ratios:206`; internal `fin["current_ratio"]` |
| 66 | Quick ratio | 0.50 | **C** | `ratios.compute_ratios:207` |
| 67 | Cash / debt | 1.00 | **A** | `cash_ratio` is cash/**current liabilities** — a different ratio |
| 68 | Net cash yield | 0.50 | **A** | — |
| 69 | Working capital / assets | 0.50 | **P** | `canonical["working_capital"]` (`statement_parsing.py:1134`), internal to Altman/Ohlson |
| 70 | Debt growth | 0.50 | **P** | boolean only (`piotroski_f_score_detailed` `f_dlever`) |
| 71 | Debt service capacity (OCF/debt) | 1.00 | **A** | Ohlson FUTL (`normalized.py:179`) never leaves the O-score |

---

### 2.6 Earnings / Accounting Quality — proposed 8.00, as-written 8.50

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 72 | Piotroski F-Score | 1.25 | **C** | `quantitative_scores.piotroski_f_score:202`; detailed paper-basis variant gated `enable_f_score_detail` |
| 73 | Beneish M-Score | 1.00 | **C** | `quantitative_scores.beneish_m_score:113`, `_M_WEIGHTS:97` |
| 74 | Accrual ratio | 1.25 | **C** | `normalized.accruals_ratio:46`; key `accrual` in `earnings_quality_verdict` |
| 75 | CFO − Net Income | 0.75 | **C** | same gap, two normalisations (`earnings_quality.py:68-103`) |
| 76 | Asset growth | 0.50 | **P** | boolean (`overpriced_score` C6) |
| 77 | Receivables growth vs revenue | 0.75 | **P** | DSRI internal to Beneish; C2 boolean |
| 78 | Inventory growth vs revenue | 0.50 | **P** | C3 boolean |
| 79 | Deferred revenue growth | 0.50 | **A** | no canonical key; `revenue` explicitly excludes deferred/unearned labels |
| 80 | Earnings volatility (−std) | 0.50 | **P** | G-Score G4/G5 read `roa_series`/`revenue_series` — the producer now exists (`statement_parsing.annual_series`, §1.4) but needs 5+ annual periods, and vendor history is 4-5; below that the leg is excluded with its `n` printed |
| 81 | OCF/NI divergence | 0.50 | **P** | the LEVEL is computed (`cash_conversion`); the growth-rate divergence is not |
| 82 | Quality of earnings | 1.00 | **C** | `earnings_quality_verdict:24` + `normalized.trap_verdict:57`; leaves `get_earnings_quality` |

---

### 2.7 Capital Efficiency — proposed 4.00, as-written 4.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 83 | Asset turnover | 0.75 | **C** | `enrich_screen_ratios:842` (internal, prioritised for Piotroski F9) + DuPont leaf `asset_turnover=` |
| 84 | Invested capital turnover | 0.75 | **A** | `invested_capital` built at `value_dip_tools.py:510` but only as a ΔIC denominator |
| 85 | Capital employed turnover | 0.50 | **A** | no capital-employed definition in the repo |
| 86 | Incremental ROIC | 1.00 | **C** | `capex_quality_read` key `incr_roic` (`capex_quality.py:184`) + `spread` vs WACC |
| 87 | Incremental asset efficiency | 0.50 | **P** | capex-based only (`cap_roi_3y`, `payback_3y`); no asset-based variant |
| 88 | NOA / Sales | 0.50 | **A** | NOA computed over PRIOR total assets (`quantitative_scores.py:322`); no sales denominator |

---

### 2.8 Capital Returns — proposed 4.00, as-written 4.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 89 | Dividend Yield | 0.50 | **C** | `ratios.compute_ratios:209` (nulled >25% as a scale artifact); `capital_income.indicated_yield:52` |
| 90 | Dividend growth | 0.50 | **P** | only raw history via `get_corporate_actions`; no growth RATE computed |
| 91 | Payout ratio | 0.50 | **P** | vendor passthrough (`finnhub.py:346`) |
| 92 | Buyback yield | 1.00 | **A** | alias `share_buybacks` exists (`statement_parsing.py:189`) with **no consumer**; repurchase $ surfaced only as raw trailing-4Q |
| 93 | Share count growth | 0.75 | **C** | `enrich_screen_ratios:845` `shares_issued`; consumed by Piotroski F7; raw change printed by `get_share_buyback_authorization` |
| 94 | Total Shareholder Yield | 0.75 | **A** | documented in `value_screener.py:19` docstring; no implementing symbol |

---

### 2.9 Distress / Financial Risk — proposed 2.00, as-written 2.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 95 | Altman Z | 0.50 | **C** | `quantitative_scores.altman_z_score:181` + variant family (`:409`, `:482`, `:511`) with zone bands |
| 96 | Ohlson O-Score | 0.40 | **C** | `normalized.ohlson_o_score:141`; leaf `ohlson_o:` |
| 97 | Distance to Default (Merton) | 0.40 | **P** | `credit_spread.merton_distance_to_default:104` exists but requires **caller-supplied** equity/debt/equity-vol; no tool resolves them |
| 98 | Interest-coverage stress | 0.25 | **A** | see #64 |
| 99 | Liquidity stress | 0.20 | **P** | market-liquidity verdict only (`liquidity_risk.liquidity_verdict:153`); balance-sheet side is `get_balance_sheet_health` + the capex funding-cover DISTRESS regime (`OCF/capex < 0.6`) |
| 100 | Debt maturity risk | 0.25 | **A** | no maturity-wall / WAM logic; `short_term_debt` parsed but only summed |

---

### 2.10 Insider Activity — proposed 2.00, as-written 2.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 101 | Net insider buying | 0.50 | **C** | two producers: `finnhub.get_insider_activity_finnhub` (net change, shares) and `massive.get_form4_insider_massive` (net open-market $) |
| 102 | Insider buy/sell ratio | 0.40 | **P** | both legs printed by the Massive path; ratio not computed |
| 103 | Open-market insider buying | 0.50 | **C** | transaction-code filter `P`/`S` (`massive.py:641`), grants/exercises excluded and stated |
| 104 | Selling acceleration | 0.25 | **P** | net-change halves trend (`finnhub.py:452`), not a sell-only slope |
| 105 | Executive participation | 0.20 | **P** | roles tagged `(director\|officer\|owner)`; no aggregation |
| 106 | Insider ownership change | 0.15 | **P** | 12-month net share change; not normalised by shares outstanding/float |

---

### 2.11 Roll-up

| Status | Factors | Share of the 104% as written |
| --- | --: | --: |
| COMPUTED | 36 | 42.15 |
| PARTIAL | 26 | 20.35 |
| ABSENT | 44 | 41.50 |

By category — the decision-relevant view, because it says which categories can
be scored this month and which cannot:

| Category | Stated | Computed | Partial | Absent | Read |
| --- | --: | --: | --: | --: | --- |
| Valuation | 20.0 | **13.25** | 6.00 | 2.00 | nearly complete — the one category ready to weight first |
| Profitability/Quality | 18.0 | 6.00 | 4.50 | 7.50 | needs level ROIC + margin exposure; stability legs are all absent |
| Cash Flow | 17.0 | 6.00 | 2.00 | 11.00 | **largest hole**; the FCF-family denominators are unwired |
| Growth | 15.0 | 4.50 | 1.00 | 9.75 | CAGR family blocked on a multi-year series producer |
| Balance Sheet | 10.0 | 2.25 | 1.00 | 6.75 | leverage/coverage family unwired; one alias has no consumer |
| Earnings Quality | 8.0 | 5.25 | 2.75 | 0.50 | essentially done |
| Capital Efficiency | 4.0 | 1.75 | 0.50 | 1.75 | needs IC turnover (invested capital already built) |
| Capital Returns | 4.0 | 1.25 | 1.00 | 1.75 | buyback $ exists in the payload, unwired |
| Distress | 2.0 | 0.90 | 0.60 | 0.50 | done (variants + Ohlson + Zmijewski exceed the proposal) |
| Insider | 2.0 | 1.00 | 1.00 | 0.00 | all three legs exist; only the ratio is uncomputed |

---

---

## 3. The design

---

### 3.1 Four sub-scores, not one master number — and the reason is the engine's own contract

The source proposes `Composite = 0.35·FQS + 0.25·FGS + 0.25·VS + 0.15·FRS`.
**Adopt the decomposition; reject the four coefficients as anything but a
hypothesis** (they are four more unmeasured weights; DeMiguel et al. is the
reason to start at `1/4` and print that fact).

Why the decomposition is right for this engine specifically: the recurring
defect this project keeps fixing is a report that *cancels* two facts against
each other — "the DCF says \$125, the analysts say \$573, therefore the DCF is an
artifact" (see `design_report_verification_llm.md`, the closed DCF-leaf item).
The source's own framing of the MSFT case is the same diagnosis: a
high-quality, high-growth, expensive company should be reported as exactly
that. Four sub-scores make "excellent business, expensive", "weak business,
cheap", "excellent and cheap" and "weak and expensive" four distinct outputs
instead of one number whose sign hides which of the four you have.

Design, in the shape the repo already implements:

```
category_scores(panel, *, weights=None, directions, min_coverage=3, sector_map=None,
                industry_neutral=False, min_peers=8)
  -> {scores: {ticker: 0-100}, z: {...}, coverage, withheld, metrics_used,
      metrics_dropped, peer_n, floor, industry_neutral, basis, weights_used}
```

Implement it as four thin wrappers over the existing `factors.quality_composite`
body (rename the shared core, do not fork it — ground rule 2), one per
category group, with `QUALITY_BANDS`-style band tables per sub-score and a
`basis` string that names the metric set, the coverage floor, the weight vector
and whether the weights were equal or published.

Sub-score metric sets, chosen **only from factors already COMPUTED** (§2) so
Phase A can ship something real:

| Sub-score | Metrics available today | Proposal weight it covers |
| --- | --- | --- |
| FQS (quality/profitability) | `roe`, `roa`, `gp_a`, `f` (Piotroski), `m` (Beneish, −), `accruals` (−), `o` (Ohlson, −), plus exposed `gross_margin`, level `roic` once built | 6.00 of 18.00 today, 8.50 after the two small exposures |
| FGS (growth) | `revenue_yoy`, `eps_yoy`, `rev_cagr5` | 4.50 of 15.25 — this is why the CAGR series producer is a Phase-2 prerequisite, not a nice-to-have |
| VS (valuation) | `pe`, `ev_ebit`, `ev_ebitda`, `ev_sales`, `ps`, `pb`, `pcf`, `p_fcf`, `ey`, `fcf_yield`, `val_z` (historical percentile), `dcf`-family upside (`price/fv`, MoS bases) | 13.25 of 21.25 — **the most complete category; ship it first** |
| FRS (financial risk) | `z` (+ variants/zones), `o`, `zmijewski_x`, `d_e`, `current`, `quick`, `trap_verdict`, `altman_zone`, capex quality `DISTRESS` regime | 2.25 + 0.90 — small weights, fully covered |

The composite is then `Σ w_c · S_c` over **present** sub-scores, renormalised,
with the weights printed. Ground rule 6 applies: this composite never reaches
`SCORE_BANDS`.

#### The sub-scores are advisory; the composite is a RESEARCH artifact (Q1, Q2, Q5)

The owner's decision of 2026-09-17 draws the line this design must not blur:

- **Published (advisory, 0-100, deterministic):** the four category sub-scores,
  each with its band table, coverage, withheld names and printed basis. They are
  diagnostics a reader can check against the factors that produced them.
- **Not published as a production score:** the *composite*. The owner withdrew
  his own earlier `TradeScore = 40/25/15/20` proposal for the same reason he
  withdrew the source's `0.35/0.25/0.25/0.15`: unless the combination is shown
  to have out-of-sample predictive validity, it is a **research composite**, not
  an empirically validated measurement. It ships only inside the research layer
  (§6 Phase C/D), labelled `RESEARCH_ONLY`, and only a validated vector may be
  promoted (§6 Phase D).
- **The status vocabulary** every published score carries:
  `ADVISORY` (deterministic diagnostic) / `RESEARCH_ONLY` (a fitted or
  unvalidated combination) / `VALIDATED` (out-of-sample evidence, still not the
  executor's measurement) — plus the confidence grade from §3.3.
- **The score contract.** Four deterministic advisory composites feed the
  decision/risk engine; `OpportunityScore` is separate and stays `null`:

  | Score | Kind | Status | Feeds |
  | --- | --- | --- | --- |
  | `FundamentalScore` | deterministic composite of fundamental factors, 0-100 | advisory | tool leaf + `run_card` |
  | `TechnicalScore` | deterministic technical/setup composite, 0-100 | advisory | tool leaf + `run_card` |
  | `RegimeScore` | market/sector/regime composite, 0-100 | advisory + sizing context | tool leaf + `run_card` |
  | `RiskScore` | risk-condition composite, 0-100 | advisory | tool leaf + `run_card` |
  | `OpportunityScore` | **separate validated measurement** | `null` until validated | the executor's existing 0-100 slot |
  | `TradeScore` | `0.40·F + 0.25·T + 0.15·R + 0.20·K` over the four above | advisory (weights learned later, §6 Phase D) | tool leaf + `run_card`, **before** the hard gates |

  Only `FundamentalScore` is this document's scope; the other engines are
  specified in their own documents beside this one
  ([`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
  [`RiskScore.md`](RiskScore.md), [`NewsScore.md`](NewsScore.md),
  [`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md)),
  each with its components, weights, readiness against the existing leaves, and
  the direction policy. They already exist in fragments —
  `strategies/sector_rank.py` for the sector composite, `strategies/risk_*` and
  `liquidity_risk.py` for risk conditions — and those documents' readiness tables
  name every producer and every gap.

---

### 3.2 `EffectiveWeight` — adopt the chain, define every multiplier over a measured input

```
W_eff(i) = W_base(i) · Sector(i) · DataQuality(i) · Stability(i) · Redundancy(i)
```

then renormalise over present factors. Each multiplier must be a **measured**
number, not a grade the implementer assigns; the mapping below is the design,
and each leg names the existing surface it reads:

| Multiplier | Definition | Source in the repo | Status |
| --- | --- | --- | --- |
| `Base` | The proposal's weight, or equal weights (rule 2) | new literal table, gated | to build |
| `Sector` | 1.0 for universal factors; a per-category applicability map for `security_type`/sector-keyed factors (e.g. bank `pb` vs industrials `ev_ebit`) | `security_type.py`, `sector_rank.sector_group_of`, the canonical `sector` key | to build; architecture decided (Q3; the master's decision record), suppliers deferred |
| `DataQuality` | `data_quality.aggregate_quality(...)['score']/100` mapped to [0.3, 1.0], plus a hard 0 for a factor whose input is `unavailable` | `strategies/data_quality.py:24,63` (and `disagreement_flag` for cross-vendor spread) | exists |
| `Stability` | 1 − (rank autocorrelation penalty) over consecutive snapshots, or a coverage-derived floor while no history exists | `alpha_health.score_evaluation_rows` **stability** row | exists (unused) |
| `Redundancy` | `1 / (1 + Σ_j |Corr_ij|)` **or** cluster-representative selection (§3.3) | `cross_section` primitives; **no fundamental correlation panel exists** | to build |

**Every factor carries a schema record** (Q3), so an overlay is a data event,
never a code fork:

| Field | Values | Why it exists |
| --- | --- | --- |
| `factor` | canonical name (e.g. `roic`, `nim`, `ffo_yield`) | one identity per measure (ground rule 2) |
| `category` | the ten categories of §2 | the weight vector's unit |
| `formula` | the pure function that computes it | auditability |
| `direction` | `+1` / `-1` | the sign the composite applies |
| `base_weight` | the (hypothesis) weight, or equal | printed in `basis` |
| `sector_scope` | `ALL` / `BANKS` / `REITS` / … | an overlay is a scope, not a new model |
| `normalization_method` | percentile / z / winsorised-z / sector percentile | must match the band table's claim (§3.2 below) |
| `supplier` | the vendor or the repo module that carries it | names what has to exist before the factor can score |
| `availability` | `present` / `NA` | **`NA` is not `0`** |

**`NA ≠ 0` is a hard rule (Q3).** A missing factor is excluded and the remaining
weights renormalise — so a bank without a NIM feed is scored on the factors it
*does* have, rather than penalised for a metric no supplier provides. This is
the convention the engine already implements (`quality_composite`'s coverage
floor and `withheld`, `growth_metrics`' omit-don't-zero, `capex_quality_read`'s
"renormalizes over measured components", `signal_summary`'s refusal to print a
partial sum under the full denominator); the design extends it rather than
introducing it. The opposite rule — scoring `NA` as `0` — would make every bank
look distressed and every REIT look unprofitable on the day the overlay lands.

The **sector-relative percentile defect** must be fixed in the same pass:
`industry_neutral_z` demeans by sector but the final percentile is taken across
the whole peer set, while `QUALITY_BANDS` calls its 50 band "sector median".
Either the percentile becomes within-sector (preferred; it is what the source
assumes and what the band table claims) or the band label is renamed. Do not
ship a band table whose label lies.

---

### 3.3 Confidence grades — derived, never asserted

The source's A/B/C/D table (1.00 / 0.85 / 0.60 / 0.30 / 0) is adoptable as a
**mapping from measurable conditions**, which is the only form ground rule 3
allows. Note what already exists: a **coverage floor** that withholds rather
than down-weights (`_coverage_floor`, `withheld`), cross-vendor disagreement
detection (`data_quality.disagreement_flag`), and gather-time metric
reconciliation (`strategies/metric_reconcile.py`). The grade is therefore:

| Grade | Derivation (all measurable) | Multiplier |
| --- | --- | --- |
| A | factor present on the primary basis, ≥2 independent producers agree, period span ≥ the factor's requirement | 1.00 |
| B | present, single producer, span met | 0.85 |
| C | present but a basis conflict, a period-span shortfall, or only a vendor passthrough | 0.60 |
| D | computed from a caller-supplied input (e.g. Merton E/D/σ, DCF intrinsic) or a degenerate base | 0.30 |
| N/A | input unavailable | 0 |

This is the honest version of "if DCF confidence is low, its weight falls
automatically" — and it is exactly the mechanism class the MSFT review asked
for: a DCF whose beta is assumed, whose terminal share is 80%, and whose basis
conflicts with the balance sheet should not carry the same weight as a DCF with
all three measured.

---

### 3.4 `DCFConfidence` — the one item with immediate, measurable value

The source's `DCFConfidence = DataQuality × AssumptionStability × FCFStability ×
TerminalSensitivity` is adoptable **today**, because every leg is already
printed by the DCF family:

| Leg | Current evidence | Availability |
| --- | --- | --- |
| DataQuality | payload basis registry + `basis_conflict`; the `NET-DEBT BASIS` disclosure; cash/debt basis in the leaf | exists |
| AssumptionStability | `beta_sensitivity=(0.8-> … 1.2-> …)` when beta is assumed; WACC derivation line | exists (`get_dcf_valuation`, 2026-09-16) |
| FCFStability | `normalized_cycle_fcf` median/min/max/mean/n over annual FCF; **std is absent** | partial |
| TerminalSensitivity | `terminal_share=` already printed by `compute_dcf` | exists |

Design: `dcf_confidence` returns a 0-1 score plus the four legs and the
thresholds it used, and the **DCF upside factor (#56/#57) is scaled by it** —
so a low-confidence DCF contributes less to VS without anyone writing "the DCF
is an artifact" in prose. Fixed thresholds are hypotheses (§6 Phase C measures
them against realised forward returns from the alpha ledger).

---

### 3.5 CapEx direction — use the engine's existing counterweight, not a `↓`

The source gives CapEx/Revenue and CapEx/OCF a `↓*` with an asterisk and the
formula `CapExQuality = GrowthGeneratedByCapEx − CapitalIntensityPenalty`. The
engine already implements the substance of that asterisk:
`strategies/capex_quality.py::capex_quality_read` returns intensity vs the
name's own history, FCF margin/yield, funding cover `OCF/|capex|`, cap-ex CAGR
vs revenue CAGR, incremental ROIC, CapEx ROI 3y, payback 3y, economic spread vs
WACC, a funding-stress regime and a 0-100 score with penalty points. **Adopt it
as the direction/penalty source** for Cash Flow and Capital Efficiency instead
of adding a second capex model. Its own docstring records the design rule from
the AMZN review: "one trailing FCF sign is NOT a quality verdict for a
high-capex name".

The 2026-09-16 MSFT round added the mirror: `get_normalized_fcf_dcf`'s
`defensive_capex_share` (share of today's excess capex intensity treated as
permanently required) and the `maintenance_fcf` floor (OCF − D&A). The
cash-flow category's capex legs should read those two, so the category can say
"temporarily capex-depressed" instead of "bad".

---

### 3.6 The factors worth building first (ranked by value ÷ effort)

Every row is a **wiring** job unless stated; §1.3 gives the evidence.

| Rank | Factor(s) | Why | Where |
| --: | --- | --- | --- |
| 1 | `interest_expense` → interest coverage (#64, #98) | an alias with zero consumers; the highest-value single line in the ledger | `analysis_tools` leaf + a `coverage` key in `ratios`/`normalized` |
| 2 | Level ROIC (#1) + Invested-capital turnover (#84) | `invested_capital` already built; unlocks 3.00% of the source's top category | `capex_quality_read` or `quantitative_scores`, exposed via `get_quality_factors` |
| 3 | Buyback yield (#92) + Total shareholder yield (#94) | `share_buybacks` alias has no consumer; the screener docstring already promises it | `ratios.compute_ratios` + a leaf |
| 4 | OCF yield (#28), FCF margin (#29), FCF/NI (#31) | three divisions over keys the merge already carries; 4.5% of weight | `ratios.compute_ratios` |
| 5 | Net debt/EBITDA (#60), net debt/FCF (#63), OCF/debt (#71), cash/debt (#67) | the leverage family, 3.5% of weight; needs an EBITDA helper (already inline at `ratios.py:162`) | `ratios.compute_ratios` |
| 6 | Gross margin + EBIT-margin series + margin stability (#6, #8, #10, #11) | value computed and stored but never rendered; stability legs unlock 1.5% | expose `fin["gross_margin"]`, return the margin series from `median_norm_ebit`'s caller |
| 7 | EV/FCF (#55) | trivial given `ev` and `free_cash_flow` | `ratios.compute_ratios` |
| 8 | Multi-year series producer — **partly built 2026-09-17** (`annual_series`: revenue / net income / total assets / operating cashflow / ROA) | the CAGR family (#14/#17/#18/#20/#23/#38/#90) is still blocked on EPS/FCF/EBITDA/EBIT series; `sec_edgar.get_financial_history` (15 years, US filers) exists and does not feed the path — and it is the one source that can clear the 5-period bar G4/G5 need | extend `annual_series` with the remaining keys, then wire SEC XBRL |
| 9 | Normalized FCF yield (#42), FCF stability std (#37), cash-conversion stability (#39) | normalized FCF and cycle-FCF stats already exist; only the division/std is missing | `normalized_fcf.py`, `cycle_dcf.py` |
| 10 | Asset growth numeric (#76), receivables/inventory-days exposure (#77, #78), WC/assets (#69), debt growth numeric (#70) | boolean-only today; the underlying values exist inside Beneish/C-score | `quantitative_scores` + `normalized` |

Explicitly **not** in Phase A: deferred revenue (#79, no canonical key and
`revenue` deliberately excludes unearned labels), debt-maturity risk (#100, no
maturity data), capital-employed turnover (#85, no definition in the repo),
Dechow-Dichev (#unreachable as currently wired).

---

---

## Appendix A — the source tables, verbatim

---

### A.1 Category architecture as proposed

| Category | Weight | As-written sum of its factors |
| --- | --: | --: |
| Profitability / Quality | 18% | 18.00 |
| Growth | 15% | **15.25** |
| Cash Flow | 17% | **19.00** |
| Valuation | 20% | **21.25** |
| Balance Sheet | 10% | 10.00 |
| Earnings / Accounting Quality | 8% | **8.50** |
| Capital Efficiency | 4% | 4.00 |
| Capital Returns | 4% | 4.00 |
| Distress / Financial Risk | 2% | 2.00 |
| Insider Activity | 2% | 2.00 |
| **TOTAL** | **100%** | **104.00** |

---

### A.2 The arithmetic check

The right-hand column is the sum of the individual factor weights the source
prints inside each category. Four categories do not add up to their own stated
total; the grand total is 104.00% against a stated 100%. Reproduce by summing
the tables in §2.1-2.10 (the "Prop. wt" column).

---

### A.3 Per-factor weights as proposed

Reproduced in the "Prop. wt" column of every §2 table, in the source's own
order (#1-#106), so §2 doubles as the verbatim weight table. Factor names,
directions, normalisation rules and redundancy groups are as printed by the
source; where a source direction carries an asterisk the asterisk is reproduced
in §2's notes.

---

### A.4 Source's other proposals (not tables)

Four sub-scores with coefficients `0.35/0.25/0.25/0.15`; the `EffectiveWeight`
product chain; the A/B/C/D confidence multipliers `1.00/0.85/0.60/0.30/0`;
`RedundancyPenalty_i = 1/(1+Σ_j|Corr_ij|)`;
`DCFConfidence = DataQuality × AssumptionStability × FCFStability ×
TerminalSensitivity`; `CapExQuality = GrowthGeneratedByCapEx −
CapitalIntensityPenalty`; sector overlays for Technology / Banks / Utilities /
REITs; four implementation phases. All are addressed in §3 and §4.

---

---

## Appendix C — source ledger (external evidence)

---

### C.1 Method, decisions and the 106-factor table (§0-§6)

| # | Source | Used for |
| --: | --- | --- |
| 1 | DeMiguel, Garlappi & Uppal, "Optimal Versus Naive Diversification" (RFS 2009) — 14 models, 7 datasets, none consistently beats `1/N`; estimation windows of 3,000+ months needed for 25 assets | equal weights as the default; refusing unmeasured "production weights" |
| 2 | Grinold & Kahn, *Active Portfolio Management* — `IR ≈ TC·IC·√BR`; rank IC as the robust form; IC/covariance-aware signal weighting | Phase C before Phase D; rank IC as the factor metric |
| 3 | Asness, Frazzini & Pedersen, "Quality Minus Junk" — `quality = z(Profitability + Growth + Safety + Payout)`; lower prices for quality predict higher returns | the Q/G/BS/payout category split; valuation must not be cancelled by quality |
| 4 | Novy-Marx, "The Other Side of Value: The Gross Profitability Premium" — GP/A roughly matches book-to-market and subsumes earnings-based measures | GP/A ≥ ROE ordering (the one ordering with literature behind it) |
| 5 | Titman, Wei & Xie (2004); Cooper, Gulen & Schill (2008) | asset growth and capex as **risk flags**, not short signals |
| 6 | Cohen, Malloy & Pomorski, "Decoding Inside Information" — routine trades ~zero, opportunistic-only 82bps/month VW | insider category stays small; the lever is the routine/opportunistic split |
| 7 | Sloan (1996), accruals anomaly | Earnings-Quality direction conventions (already implemented) |
| 8 | McLean & Pontiff (2016), 97 predictors — ~26% out-of-sample decay, ~58% post-publication | refusing weights fitted to one sample; DSR/PBO discipline |
| 9 | Asness, Chandra, Ilmanen, Israel & Moskowitz, "Contrarian Factor Timing is Deceptively Difficult" | refusing default regime/conditional weights |
| 10 | Valuation practitioner consensus on terminal value share (60-80% of DCF) and 50bp WACC/`g` sensitivity (~10-20% of value) | the confidence-scaled DCF weight and its thresholds |
| 11 | Sector-valuation consensus (bank P/B ↔ ROE/ROTCE with NIM and CET1; REIT P/FFO/AFFO, NAV, occupancy) | sector overlays are structurally right but data-blocked here |
| 12 | Factor-combination practice (measure correlation → cluster → orthogonalise → weight by unique predictive value; naive summation inflates exposure) | redundancy as structure; reject the untested constant |

Primary-source retrieval was performed for every row; the two claims this
document leans on hardest (1 and 8) are also the two that most directly
contradict the source's Phase 1 and Phase 4.

---

## Related documents

- Master: [`README.md`](README.md) — the seven engines, the composite and its gate
  rules, the cross-engine contracts, the phase plan, the verification
  requirements, the decision record, the open questions, and the **code defects**
  the inventories found (this document's former §1.5).
- The other engines: [`TechnicalScore.md`](TechnicalScore.md),
  [`RegimeScore.md`](RegimeScore.md), [`NewsScore.md`](NewsScore.md),
  [`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
  [`RiskScore.md`](RiskScore.md).
- The owner's specification of record: [`../ScoreWeight/fundamental.md`](../ScoreWeight/fundamental.md).

