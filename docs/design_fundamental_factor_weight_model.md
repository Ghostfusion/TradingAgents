# Fundamental Factor Weight Model — 106-Factor Master Table, Adoption Design

Status: **design (2026-09-17), decisions recorded. Not started.** Nothing in
this document is implemented; it defines what would be built, in what order,
under which gates, and — more importantly — what is **already** in the engine so
that no second implementation is created. **All five open questions were answered
by the owner on 2026-09-17**: §0.5 summarises each decision and where it lands,
§8 keeps the full record with the rationale.

Source: an external, LLM-authored answer proposing a **106-factor fundamental
weight master table** in ten categories with "starting production weights"
(preserved verbatim in Appendix A). It cites no primary literature. This
document treats its **structure** as the proposal and its **numbers** as
hypotheses to be measured, per the repo's own rule 2 (§0.3 of
[`design_quant_formulas_research_round3.md`](design_quant_formulas_research_round3.md):
*"No weight vector is invented"*).

Audience: whoever implements this. Read §1 and §2 before §3 — the engine
already computes most of this table, and §2 says exactly which third.

Related: [`design_quant_formulas_research.md`](design_quant_formulas_research.md)
(round 1), [`design_quant_formulas_research_round2.md`](design_quant_formulas_research_round2.md),
[`design_quant_formulas_research_round3.md`](design_quant_formulas_research_round3.md)
(round 3 — the composite/normalisation round, §S3 is this document's closest
prior art), [`implementation_plan_quant_formula_additions_round3.md`](implementation_plan_quant_formula_additions_round3.md)
(its phased plan and the inherited ground rules),
[`design_institutional_value_dip_workflow.md`](design_institutional_value_dip_workflow.md)
(funnel-over-single-score constraint),
[`design_report_verification_llm.md`](design_report_verification_llm.md).

---

## 0. Method

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

### 0.2 Status vocabulary (used by every table in §2)

Read at the definition site; no fetch was executed.

| Status | Meaning |
| --- | --- |
| **COMPUTED** | A repo function computes the value from canonical line items, and it reaches at least one tool leaf, screen row, or score. |
| **PARTIAL** | One of: (a) computed only inside another ratio's internals and never exposed; (b) available only as a boolean/binary sub-score, not as a factor value; (c) surfaced only as a raw vendor passthrough with no repo-side computation. |
| **ABSENT** | No implementation found in `tradingagents/` or `scripts/`. |

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

### 0.5 Recorded decisions (owner, 2026-09-17)

The five questions this design opened are closed. Each decision is stated with
the section it changes; §8 carries the full rationale.

| # | Question | Decision | Where it lands |
| --: | --- | --- | --- |
| Q1 | Does the composite reach `opportunity_score`? | **Never, for now.** It stays a tool-leaf / `run_card` advisory metric. `opportunity_score` keeps its `null` and gains a published *reason* — a deterministic `FundamentalScore = 84` does not mean `Opportunity = 84`; those are different questions, and the executor treats the second as a validated 0-100 measurement | §3.1, §5.2 |
| Q2 | Learned walk-forward weights? | **Yes, as a separate research layer — never in the deterministic production score.** Promotion is a ladder: `RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION`, each step evidenced, none automatic | §3.1, §6 Phase D |
| Q3 | Sector overlays? | **Architecture in scope now, suppliers deferred.** The factor schema carries `sector_scope`/`supplier`/`availability` from day one; bank/REIT metrics are `NA` until a supplier exists — **`NA ≠ 0`**, and missing data reduces the *available* weight instead of punishing the name | §3.2, §4.1 |
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

**Added 2026-09-17 (second pass): §3.7-§3.8 specify the score engines.** The
owner's staged `docs/ScoreWeight/{fundamental,market,news_sentiment}.md` refine
the four-score version to **six engines plus a recommended seventh**
(Fundamental, Technical, Regime, News, Sentiment, Risk, + Event), with a research
allocation of 35 / 20 / 15 / 7.5 / 7.5 / 15 and EventScore's weight still open
(§8.3). Where the staged weights differ from the first iteration they govern, and
the superseded numbers are kept in the tables for the record. Each is a
separate 0-100 score, all in the **same direction (100 = favourable, so
`RiskScore` 100 = low risk)**, and only then combined:
`TradeScore = 0.40·F + 0.25·T + 0.15·R + 0.20·K`, which **never overrides a hard
gate** and whose weights are learned empirically later (§6 Phase D). The
governing sentence is *"do not mix them into one score too early"* — the
evidence for keeping the dimensions separate (and for a regime **score** being
distinct from the regime **sizing scale**) is in §3.7 and Appendix C.2.

---

## 1. What already exists (read this before designing anything)

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

### 1.5 Defects found while grounding the four scores (2026-09-17, NOT fixed — this pass is docs-only)

Found by the TechnicalScore / RegimeScore / RiskScore inventories. Each is a
confirmed code defect with a named consequence; they are recorded here rather
than fixed because the owner's instruction for this pass was design-only. They
belong to the same class as §1.4's four (fixed) and should be fixed together
with their regression tests.

| # | Defect | Evidence | Consequence |
| --: | --- | --- | --- |
| 1 | **A dead branch makes the regime label trend-blind on the default path.** `overlays.build_strategy_overlays` calls `regime_label(vol_pct, trend, 0.4)` while `regime_label`'s default `chop_threshold` is `0.30`, so `chop <= chop_threshold` is **always False** | `strategies/overlays.py:57` vs `strategies/regime.py:126-145` | with `vol_pct == 0.5` (the middle band, the common case) `get_regime_read` returns `neutral` **regardless of the trend input** — the trend leg is inert, and every report that quotes "regime=neutral" is quoting a constant |
| 2 | **Choppiness is passed on two incompatible scales.** `get_regime_components` compares chop against `chop_threshold=30.0` (0-100) while `overlays.py` hardcodes `0.4` against a 0.30 default | `agents/utils/analysis_tools.py:2176` vs `strategies/overlays.py:57`; producer `strategies/regime.py:87 choppiness` | the two callers cannot both be right; whichever is wrong makes its branch either dead (see #1) or always-on |
| 3 | **Donchian breakout is unreachable.** `donchian_channel` returns `breakout_up/breakout_dn = None` by construction ("closes not passed; caller derives") and **no caller derives them** | `strategies/technical_factors.py:377` | the Breakout component's most canonical input is ABSENT as a value while the function appears to compute it |
| 4 | **`parabolic_sar` is called without `closes`**, so its `below`/`exit` flag is unreachable | call at `agents/utils/analysis_tools.py:1160`; def `strategies/technical_factors.py:432` | the mean-reversion leaf prints the SAR level but never the flag its consumers would read |
| 5 | **`BookState.net_beta` has no reader** | `../TradingExecution/signald/risk/state.py:77` | a book-level beta leg has a producer and no consumer; the RiskScore's concentration component cannot use it |
| 6 | **Gap fill probability / days-to-fill are constants**, not measurements | `strategies/market_session.py` / `pre_market.py` gap statistics | the Gap/execution component is the weakest of the eight for a data reason, not a modelling one |

Defects 1 and 2 are the pair that most affect *report text today*: #1 means a
quoted `regime=neutral` may carry no information, and #2 means the fix must
first decide which scale `choppiness` is defined on. Both are small, both are
test-provable (the label must move when the trend moves; the two callers must
agree on a unit), and neither is fixed in this pass.

---

## 2. The adoption ledger — all 106 factors against the engine

Legend: **C** = COMPUTED, **P** = PARTIAL, **A** = ABSENT (§0.2). "Prop. wt"
is the source's weight **as written**. `file:line` is the definition site of the
existing implementation.

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

### 2.7 Capital Efficiency — proposed 4.00, as-written 4.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 83 | Asset turnover | 0.75 | **C** | `enrich_screen_ratios:842` (internal, prioritised for Piotroski F9) + DuPont leaf `asset_turnover=` |
| 84 | Invested capital turnover | 0.75 | **A** | `invested_capital` built at `value_dip_tools.py:510` but only as a ΔIC denominator |
| 85 | Capital employed turnover | 0.50 | **A** | no capital-employed definition in the repo |
| 86 | Incremental ROIC | 1.00 | **C** | `capex_quality_read` key `incr_roic` (`capex_quality.py:184`) + `spread` vs WACC |
| 87 | Incremental asset efficiency | 0.50 | **P** | capex-based only (`cap_roi_3y`, `payback_3y`); no asset-based variant |
| 88 | NOA / Sales | 0.50 | **A** | NOA computed over PRIOR total assets (`quantitative_scores.py:322`); no sales denominator |

### 2.8 Capital Returns — proposed 4.00, as-written 4.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 89 | Dividend Yield | 0.50 | **C** | `ratios.compute_ratios:209` (nulled >25% as a scale artifact); `capital_income.indicated_yield:52` |
| 90 | Dividend growth | 0.50 | **P** | only raw history via `get_corporate_actions`; no growth RATE computed |
| 91 | Payout ratio | 0.50 | **P** | vendor passthrough (`finnhub.py:346`) |
| 92 | Buyback yield | 1.00 | **A** | alias `share_buybacks` exists (`statement_parsing.py:189`) with **no consumer**; repurchase $ surfaced only as raw trailing-4Q |
| 93 | Share count growth | 0.75 | **C** | `enrich_screen_ratios:845` `shares_issued`; consumed by Piotroski F7; raw change printed by `get_share_buyback_authorization` |
| 94 | Total Shareholder Yield | 0.75 | **A** | documented in `value_screener.py:19` docstring; no implementing symbol |

### 2.9 Distress / Financial Risk — proposed 2.00, as-written 2.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 95 | Altman Z | 0.50 | **C** | `quantitative_scores.altman_z_score:181` + variant family (`:409`, `:482`, `:511`) with zone bands |
| 96 | Ohlson O-Score | 0.40 | **C** | `normalized.ohlson_o_score:141`; leaf `ohlson_o:` |
| 97 | Distance to Default (Merton) | 0.40 | **P** | `credit_spread.merton_distance_to_default:104` exists but requires **caller-supplied** equity/debt/equity-vol; no tool resolves them |
| 98 | Interest-coverage stress | 0.25 | **A** | see #64 |
| 99 | Liquidity stress | 0.20 | **P** | market-liquidity verdict only (`liquidity_risk.liquidity_verdict:153`); balance-sheet side is `get_balance_sheet_health` + the capex funding-cover DISTRESS regime (`OCF/capex < 0.6`) |
| 100 | Debt maturity risk | 0.25 | **A** | no maturity-wall / WAM logic; `short_term_debt` parsed but only summed |

### 2.10 Insider Activity — proposed 2.00, as-written 2.00

| # | Factor | Prop. wt | St | Existing implementation |
| -: | --- | --: | :-: | --- |
| 101 | Net insider buying | 0.50 | **C** | two producers: `finnhub.get_insider_activity_finnhub` (net change, shares) and `massive.get_form4_insider_massive` (net open-market $) |
| 102 | Insider buy/sell ratio | 0.40 | **P** | both legs printed by the Massive path; ratio not computed |
| 103 | Open-market insider buying | 0.50 | **C** | transaction-code filter `P`/`S` (`massive.py:641`), grants/exercises excluded and stated |
| 104 | Selling acceleration | 0.25 | **P** | net-change halves trend (`finnhub.py:452`), not a sell-only slope |
| 105 | Executive participation | 0.20 | **P** | roles tagged `(director\|officer\|owner)`; no aggregation |
| 106 | Insider ownership change | 0.15 | **P** | 12-month net share change; not normalised by shares outstanding/float |

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

## 3. The design

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

  Only `FundamentalScore` was this document's original scope; the other three are
  now specified in **§3.7** (components, weights, readiness against the existing
  leaves, and the direction policy). They already exist in fragments —
  `strategies/sector_rank.py` for the sector composite, `strategies/risk_*` and
  `liquidity_risk.py` for risk conditions — and §3.7's readiness tables name
  every producer and every gap.

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
| `Sector` | 1.0 for universal factors; a per-category applicability map for `security_type`/sector-keyed factors (e.g. bank `pb` vs industrials `ev_ebit`) | `security_type.py`, `sector_rank.sector_group_of`, the canonical `sector` key | to build; architecture decided (Q3, §4.1), suppliers deferred |
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

### 3.7 The four-score architecture (Fundamental / Technical / Regime / Risk → TradeScore)

The owner's 2026-09-17 specification, refined the same day by three staged docs
(`docs/ScoreWeight/{fundamental,market,news_sentiment}.md`). **Separate** 0-100
scores, one per dimension, and only then a combination. The staged docs frame
the factor side as **four catalogs** — fundamental ~106, technical ~80-120,
market/regime ~50-80, risk/portfolio ~40-60, i.e. a **250-300 factor target
across the engines** — and make the point this document already enforces: *"106
does not mean your system has proven that 106 independent pieces of information
exist"* (FCF yield, price/FCF, normalized FCF yield and earnings yield overlap;
§3.2's redundancy leg is what handles it). The staged spec's formula is the same
renormalising mean this document specifies: `Score_j = Σ wᵢxᵢ / Σ wᵢ` over
normalised 0-100 factor scores, with missing factors excluded rather than scored
zero (`NA ≠ 0`, §3.2). The governing sentence is *"do not mix
them into one score too early"*, and there is literature behind it: Asness,
Moskowitz & Pedersen find value and momentum are **negatively correlated
(≈ −0.60)** and that separate sleeves / a 50-50 allocation historically beat
merging the signals into one ranking; composite-indicator practice recommends
keeping dimensions separate for root-cause attribution and to avoid a
**misleading cancellation** where one dimension deteriorates while the total
stays flat. The MSFT example in the owner's brief is exactly that case (strong
long-term trend, deteriorating MACD, RSI fallen, price below the 10/20 EMA,
swing setup NO) — a single "bullish" label would erase the disagreement.

#### 3.7.1 Direction convention — 100 = favourable, for all four

| Score | 100 means | 0 means |
| --- | --- | --- |
| `FundamentalScore` | excellent fundamentals | poor fundamentals |
| `TechnicalScore` | excellent technical setup | broken setup |
| `RegimeScore` | highly favourable regime | hostile regime |
| `RiskScore` | **low risk / favourable risk conditions** | extreme risk |

`RiskScore` is therefore **inverted relative to how risk is measured**: CVaR,
drawdown and illiquidity are computed as *losses* (higher = worse) and must be
direction-aligned before weighting. The engine's conventions are currently
**inconsistent in three places** and the doc pins one rule instead of inheriting
the mixture (this is a finding, §1.5):

| Measure | Conventions in the tree today | Pinned rule |
| --- | --- | --- |
| CVaR / VaR | `book_risk.py:18 cvar` and `:9 simple_var` return **negative loss**; `size.py:187 modified_var` and `book_risk.py:628 min_cvar_weights['cvar']` return **positive loss magnitude**; `../TradingExecution/signald/risk/tail.py:56 ESResult.value_pct` is a **fraction of equity, higher = worse** | compute in the producer's native convention, **print the raw value**, and align to "higher = favourable" only at the score boundary |
| Drawdown | `book_risk.py:100 portfolio_drawdown` and `etf_risk.py:142 max_drawdown` are **negative**; `regime_state.py:146 regime_drawdown` is a **labelled band** on a negative magnitude; the governor's HWM tiers are positive fractions | same rule: raw value printed, sign named, aligned at the boundary |
| Concentration cap | a **notional** cap (`sector_cap_limit` 0.35, `max_name_weight` 0.25) versus a **correlation** cap (`max_pairwise_corr`) | the component names which one it read |

Every component therefore prints **both** numbers — the raw measurement with its
own units and sign, and the direction-aligned 0-100 contribution — which is the
same basis discipline the DCF family adopted (`cash=/debt=/bridge=`).

#### 3.7.2 FundamentalScore

Components are the ten categories of §2 with the owner's weights
(Quality 18, Growth 15, Cash Flow 17, Valuation 20, Balance Sheet 10, Earnings
Quality 8, Capital Efficiency 4, Capital Returns 4, Distress 2, Insider 2),
each already specified as an advisory sub-score in §3.1. Band table (owner's):

| Band | Reading |
| --- | --- |
| 80-100 | exceptional fundamentals |
| 65-79 | strong |
| 50-64 | average |
| 35-49 | weak |
| 0-34 | poor |

**A high FundamentalScore does not mean Buy.** MSFT can score high while being
unattractive at its price — which is why valuation is a component and why the
score never reaches the executor's `opportunity_score` (Q1, §5.2). This band
table is the score's own (`QUALITY_BANDS`' pattern), never
`decision_guardrail.SCORE_BANDS` (ground rule 6).

#### 3.7.3 TechnicalScore

Components and the owner's initial weights, with readiness measured against the
engine (§1 inventory, 2026-09-17):

**Weights: the owner's staged spec supersedes the first iteration.** The
pasted-text version (Trend 25 / Momentum 20 / Setup 20 / RS 12 / Volume 10 /
Breakout 8 / Mean-reversion 5) is superseded by
`docs/ScoreWeight/market.md` (Trend 20 / Momentum 18 / RS 12 / Price structure
12 / Volume 10 / Breakout-pullback 10 / Mean reversion 8 / **Volatility-ATR 5** /
**Breadth-participation 5**), which adds two components and re-weights the rest.
The table below keeps the superseded weights in a column so the change is
visible; the governing column is `Wt`.

| Component | Wt (superseded) | Status | Existing producers (exact) | What is missing |
| --- | --: | --- | --- | --- |
| Trend architecture | 20% (25%) | **SCORABLE** | `swing.trend_architecture:71` (`stacked`/`above50`/`above200`/`sma50_rising`/`sma200_rising`/`ema20_above_sma50`), `regime_state.regime_trend:65` (continuous `(EMA20−EMA50)/ATR14`), `technical_factors.adx:179` (adx + DI±), `aroon:495`, `extended_indicators.ichimoku:78`, `golden_death_cross:53`, `sector_rank._ma_alignment:236` | price-vs-10-SMA ABSENT; SMA slopes are **booleans**, not continuous values; no DI± comparison flag |
| Momentum | 18% (20%) | **SCORABLE** | `swing.rsi:39` + `rsi_band:118`, `stochastic_oscillator:146`, `kst:53`, `roc:149`, `momentum_oscillator:160`, `trix:171`, `rotation.clenow_momentum:89`, `momentum.momentum_12_1:358`, `factors.momentum:24`/`high_distance:35` | MACD line/histogram has no public leaf (`value_dip._macd_hist:500` is private; only `macd_divergence:540`); no momentum **slope** on the wire (`factors.momentum_multihorizon:400` is unwired) |
| Swing / setup quality (price structure in the staged spec) | 12% (20%) | **SCORABLE, but binary** | `swing.swing_report:441`, `pullback_setup:156`, `swing_low_stop:185`, `vcp_setup:326`, `momentum.first_pullback:210`, `value_dip.vdu_entry_setup:670` | entry-distance magnitude missing (fib unwired); breakout/pullback quality are booleans, so the component needs a graded wrapper, not a new measure |
| Relative strength | 12% (12%) | **PARTIAL** | `relative_strength.relative_strength_report:132` + `slope_pct:49`, `rotation.relative_rotation:43` (RRG), `regime_state.regime_relative:127`, `sector_rank.rank_sectors_multifactor:391` + `sector_standing:176` (ETF level) | **name-vs-sector and name-vs-industry strength is ABSENT** — only the sector's own rank vs SPY exists |
| Volume / accumulation | 10% (10%) | **SCORABLE** | `momentum.rvol:25`, `chaikin_money_flow:261`, `accumulation_distribution:222`, `vpt:246`, `mf_index:112`, `chaikin_oscillator:560`, `obv_divergence:396`, `elder_thermometer:476`, `volume_profile:654`, `value_dip.volume_dry_up:601` | A/D and VPT print **cumulative levels**, so direction is not derivable from the leaf |
| Breakout / pullback | 10% (8%) | **PARTIAL** | `swing.vcp_setup.near_breakout:326`, `market_session.opening_range:72` (`breakout=`), `value_dip.trigger_candle:625`, `higher_low_structure:656`, `scan_candlesticks:385`, `pivot_points:239`, `supertrend:619`, `keltner_channel:349` | `donchian_channel:377` returns `breakout_up/breakout_dn = None` **by construction** and no caller derives them (§1.5); `vcp_setup.pivot` (the buy point) is computed but not printed |
| Mean-reversion | 8% (5%) | **SCORABLE** | `stoch_rsi:283`, `rsi2:315`, `williams_r:338`, `cci:126`, `fisher_transform:523`, `bollinger_pct_b:75`, `mean_reversion.hurst_exponent:112`/`variance_ratio:216` via `get_mean_reversion_quality` | `parabolic_sar:432` is called without `closes` at `analysis_tools.py:1160`, so its `below/exit` flag is unreachable (§1.5) |

| **Volatility / ATR** (new) | 5% | **SCORABLE** | `size.atr:131`, `volatility_models` (Parkinson / Garman-Klass / Yang-Zhang / EWMA / GARCH11), `regime.vol_percentile:49`, `etf_risk:142` (ATR% + vol percentile), `momentum.rvol:25` | direction must be declared: for a *setup* score, lower volatility is generally favourable, which is the **opposite** polarity from the risk family — the same number serves both only because the polarity is explicit |
| **Breadth / participation** (new) | 5% | **PARTIAL** | `sector_rank.constituent_breadth:654`, `leadership_ratio:674`, `sector_screener.dispersion_trend:161`, `pullback_divergence:185` | these are **sector/ETF-level** breadth reads; a per-name "participation" measure does not exist (the closest is the name's own volume/RS legs) |

**No composite technical score exists** (verified): the nearest artifacts are
`quant_baseline.quant_signal` (unwired, tests only),
`sector_rank.rank_sectors_multifactor`'s cross-sectional `score` (sector/ETF
level), `factors.composite_score` as consumed by `get_composite_rank` (a peer
percentile over momentum + 52-week distance) and `knife_guard.knife_score`
(higher = **worse**). So `TechnicalScore` is new work, but it is an aggregation
of existing leaves rather than new computation.

**Direction polarity must be declared per component** — five existing consumers
read the *opposite* polarity from a naive "higher = better" score, and a
monotone term would invert the signal they were built for:

| Input | Consumer expecting the opposite | Evidence |
| --- | --- | --- |
| `swing.rsi_band:118` | RSI is graded 45-70 `strong`, 40-50 `reset`, <40 `broken`, >70 `hot`; `swing_report:441` gates on `label in ('strong','reset')` | a monotone RSI term inverts it |
| `mf_index:112` | `<20 oversold` is the *good* reading for the dip path (`get_dip_technical`, `analysis_tools.py:1108`) | oversold = constructive |
| `stochastic_oscillator:146` | `oversold = k < 20` is the entry condition (`value_dip._stochastic_oversold:825`) | oversold = constructive |
| `elder_thermometer:476` | ratio `< 0.8` = `quiet` = "a calm dip in a quiet tape" (`get_mean_reversion_tech`) | low = constructive |
| `value_dip.support_structure:714` | *near* the 200-SMA = `200-day-sma-support` = better dip entry, while `swing` reads *above* the 200-SMA as better | two live, opposite readings of one level |

The rule: **the component declares its polarity, and the two readings are not
averaged** — for the dip path "near support" is favourable, for the trend path
"above the 200-SMA" is favourable, and the same number serves both only because
the polarity is explicit.

**The mixed state must survive.** The owner's MSFT reading (strong trend, ADX
34.85, price above the 50/200 SMA, positive RS structure — *but* MACD
deteriorating, RSI fallen, price below the 10/20 EMA, swing setup NO, EMA20
trail triggered) is the acceptance case for this score: it must print a
moderate score with the *components* showing which way each leg leans, not a
verdict word. Note also the evidence quality per component: trend/momentum
(1-12 month time-series momentum) and the 52-week-high anchoring effect have
broad support; **volume is a confirmation variable, not a standalone
predictor**, and **ADX is non-directional and lagging** — it measures trend
strength, not direction, and the literature reports little standalone
predictive power. So ADX belongs in *Trend architecture* as a strength input and
must not be treated as a directional signal.

#### 3.7.4 RegimeScore

Components and the owner's weights, with readiness:

**Weights: staged spec governs.** The pasted-text set (trend 20 / vol 20 /
momentum 15 / choppiness 15 / sector 10 / relative 10 / event 10) is superseded
by `docs/ScoreWeight/market.md` (Market trend 20 / Volatility 20 / Market
momentum 15 / **Breadth 15** / Choppiness-persistence 10 / Sector rotation 10 /
**Macro-credit 5** / Event 5) — breadth rises to 15% and relative-regime is
replaced by macro-credit.

| Component | Wt (superseded) | Status | Existing producers | Gap |
| --- | --: | --- | --- | --- |
| Market trend regime | 20% (20%) | **SCORABLE** | `regime_state.regime_trend:65` (four labels + continuous score), `regime.regime_gate_read:178`, `sector_screener.classify_regime:108` (SPY vs SMA200 + slope) | three producers, no arbitration (below) |
| Volatility regime | 20% (20%) | **SCORABLE** | `regime.vol_percentile:49`, `regime_state.regime_vol_ratio:92` (ATR ratio → LOW/NORMAL/HIGH/EXTREME), all five `volatility_models.py` estimators incl. GARCH | two of these are already 0-1 percentiles with a stated direction → band map, not a model |
| Market momentum regime | 15% (15%) | **SCORABLE** | `regime_state.regime_relative:127`, `factors.momentum:24`, `momentum.momentum_12_1:358`, `rotation.clenow_momentum:89` | — |
| Choppiness / persistence | 10% (15%) | **PARTIAL** | `regime.choppiness:87`, `regime.hmm_regime:148`, `cusum:295`, `ewma_control:340`, `bocpd:389`, `mean_reversion.hurst_exponent:112`, `variance_ratio:216` | **unit + direction policy missing** and currently *contradictory*: `get_regime_components` compares chop against `chop_threshold=30.0` (0-100 scale) while `overlays.py:57` hardcodes `chop=0.4` against a default threshold of 0.30 (§1.5). Hurst/VR are complementary *shape* diagnostics, not robust regime detectors on their own |
| Sector rotation | 10% (10%) | **SCORABLE** | `sector_rank.rank_sectors_multifactor:391` (row `score` 0-100, `quadrant`), `sector_standing:176`, `constituent_breadth:654` | ETF level only, no per-name sector regime |
| Relative regime *(superseded by breadth + macro-credit)* | — (10%) | **SCORABLE** | `regime_state.regime_relative:127` (R_stock − R_bench), `rotation.relative_rotation:43` | overlaps the TechnicalScore RS component — the *reference* differs (regime = market-relative, RS = benchmark/sector), and both must say which |
| Event / macro regime | 5% (10%) | **PARTIAL** | `catalyst.build_catalyst_snapshot:219` (`scale` 0.25-1.0 + `hard_block`), `events.catalyst_risk_penalty:53`, `credit_spread.credit_stress_level:44` (level + scale), `cycle_tilt.macro_stance:128`, `taylor_rule:89`, `pre_market`, `get_shift_detection` | categorical + one 0..1 scale; no percentile basis |

| **Breadth** (new) | 15% | **SCORABLE (sector level)** | `sector_rank.constituent_breadth:654`, `leadership_ratio:674`, `sector_screener.dispersion_trend:161`, `% above MA` reads inside `rank_sectors_multifactor` | market-wide breadth (advance/decline, new highs/lows, % of stocks above the 50/200-SMA) is not computed — the existing reads are per-sector |
| **Macro / credit** (new) | 5% | **SCORABLE** | `credit_spread.credit_stress_level:44` (level + scale), `cycle_tilt.macro_stance:128`, `taylor_rule:89`, `get_macro_regime_read`, `get_sofr_curve`, `get_shift_detection` | the staged spec also names VIX term structure and Treasury volatility / yield curve — `get_vol_surface_shape` and the FRED chain partially cover these; a named term-structure regime read does not exist |

**The engine has no market-level regime score** — only categorical states,
sizing multipliers (`position_scale`, `F_regime`, `F_vol`, credit scale, catalyst
scale) and raw numerics. The only 0-100 numbers in this space are *cross-sectional
sector percentiles*. `RegimeScore` is therefore new, and the multipliers are
**not** its components (see the score/scale separation below).

**The reported MSFT conflict is a name collision, not a contradiction — and it
is why this score needs an arbitration rule.** `get_regime_read` →
`overlays.build_strategy_overlays` (`overlays.py:26-92`) classifies with a
**3-valued** close-dispersion proxy (`vol_pct ∈ {0.1, 0.5, 0.9}`,
`overlays.py:41-55`) and a **hardcoded `chop=0.4`** (`overlays.py:57`), and
returns `neutral` + a `position_scale` (0.47x = `target_vol / trailing realized
vol`, clamped). `get_regime_state` → `regime_state.regime_state:215` uses OHLC
ATR14, EMA20/EMA50, a benchmark series and the 252-bar rolling high, and returns
**four crisp axis labels plus `F_regime`** (`regime_factor:191` = the **worst**
of trend/vol/drawdown legs). They share no call path (`regime._lazy_regime_state:506`
is a naming re-export, not a composition), they are gated independently
(`enable_strategy_overlays` defaults **True**, `regime_state_enable` defaults
**False**), and **both are bound to the same market analyst**
(`agents/toolsets.py:267,270`) — so the disagreement surfaces *inside one
prompt*. A RegimeScore may not "read both and average": it must name **one
producer per component**, or apply an explicit arbitration rule that stores its
reason.

**Score, scale, state and confidence are four different outputs** (the owner's
framing): `RegimeScore = 68`, `RegimeScale = 0.47x`, `RegimeState = STRONG_BULL`,
`RegimeConfidence = 0.75`. The scale is a **sizing multiplier**, and sizing is
not conviction: volatility targeting sizes *inversely* to volatility, and
fractional Kelly discounts the edge for estimation error. Keeping them apart is
what stops a hostile regime from silently rewriting the score, and vice versa.

#### 3.7.5 RiskScore

Components and the owner's weights. **No 0-100 risk score exists anywhere**
(grep for `risk_score|RiskScore|risk_grade|risk_band` over `tradingagents/`,
`../TradingExecution/signald/` and `scripts/` returns zero hits), so this is a
**new model** — but every component has existing producers, and six existing
numbers already sit in the proposed favourable direction:

**Weights: staged spec governs.** The pasted-text set (portfolio 20 / tail 15 /
vol 15 / liquidity 10 / concentration-correlation 15 / drawdown 10 / event 10 /
gap 5) is superseded by `docs/ScoreWeight/market.md` (Volatility 15 / Tail 15 /
Liquidity 10 / **Gap 10** / Correlation 15 / Concentration 10 / Portfolio
drawdown 15 / Event 10) — drawdown rises to 15%, gap doubles to 10%,
concentration and correlation are **split into two components**, and the
portfolio/book leg is absorbed into drawdown + correlation.

| Component | Wt (superseded) | Status | Existing producers | Gap |
| --- | --: | --- | --- | --- |
| Portfolio / book risk *(superseded; absorbed into drawdown + correlation)* | — (20%) | **SCORABLE** | `book_risk.portfolio_cvar:28`, `book_correlated_stress:128`, `component_var:256`, `incremental_var:222`, `min_cvar_weights:628`; executor `risk/tail.py:145 es_estimate` (a tail-budget ratio already compares `es.value_pct + requested_risk_pct` against house/sleeve budgets); `book_context.measured_book_drawdown:102` | loss-fraction convention → inversion only |
| Tail risk | 15% (15%) | **SCORABLE, sign-hazardous** | `book_risk.simple_var:9`, `cvar:18`, `cdar:174`, `var_cvar_horizon:341`, `extreme_quantile_var:451` (GPD/EVT); `size.modified_var:187` | three conventions coexist (§3.7.1) — pin one |
| Volatility risk | 15% (15%) | **SCORABLE — easiest** | `regime.realized_vol:29`, `vol_percentile:49`; `volatility_models` (Parkinson/Garman-Klass/Yang-Zhang/EWMA/GARCH11); `regime_state.regime_vol_ratio:92`; `etf_risk:142`; executor `risk/voltarget.py:92 vol_scalar` | band map over existing percentiles |
| Liquidity risk | 10% (10%) | **PARTIAL** | `liquidity_risk.amihud_illiquidity:71`, `float_turnover:53`, `days_to_absorb:103`, `free_float_factor:34`, `ownership_hhi:130`, `kyle_lambda:262`, spread estimators `:309/:363/:407/:442`; executor `risk/gate.py:516 _liquidity` | `liquidity_verdict` is a 3-level ordinal string; no ILLIQ → 0-100 map |
| Correlation risk | 15% (15%) | **SCORABLE** | `portfolio.weight_hhi:417`, `effective_holdings:398`, `weight_entropy:431`, `active_share:379`, `_max_pairwise_corr:61`, `mean_correlation:252`, `correlation_penalty:274`; `hierarchical_risk_parity:165`; `portfolio_optimizer:82/:246` | no threshold→score map (only caps and an opt-in penalty); `weight_entropy`/`effective_holdings` are already higher = better |
| Portfolio drawdown | 15% (10%) | **SCORABLE** | `book_risk.portfolio_drawdown:100`, `cdar:174`, `drawdown_gate:167`; `regime_state.regime_drawdown:146` (bands NORMAL > −5% > CORRECTION > −15% > BEAR > −25% > SEVERE); governor HWM tiers (`risk_hwm_soft_pct` 0.10 / `risk_hwm_hard_pct` 0.20); executor `risk/ladder.py:82 rung_for` | the banding exists as labels, not a number |
| Event risk | 10% (10%) | **SCORABLE** | `catalyst.build_catalyst_snapshot:219` (`scale` 0.25-1.0 + `hard_block`), `last_earnings_surprise:70`, `next_earnings:90`, `fed_imminence:142`, `macro_imminence:123`; `events.surprise_score:17`, `catalyst_risk_penalty:53` | already in the favourable direction, but floored at 0.25 (a size multiplier, not a 0-100) |
| Gap risk | 10% (5%) | **WEAKEST — mostly PARTIAL** | `market_session.gap_type:137`, `pre_market.premarket_gap:40`; executor `signals/costgate.check_cost_gate:152` + `impact_bps:65`; `liquidity_risk.volume_share_slippage:220`, `market_impact_slippage:243`; `execution_schedule.almgren_chriss:47` | gap fill probability / days-to-fill are **constants**; execution risk exists only as a cost-gate decision (ok/not-ok) and per-share slippage, never as a 0-100 |

| **Concentration risk** (split out) | 10% | **SCORABLE** | `portfolio.weight_hhi:417`, `effective_holdings:398`, `weight_entropy:431`, `active_share:379`; the caps `sector_cap_limit` 0.35 / `max_name_weight` 0.25 / `cluster_cap_pct` | no threshold→score map |

**Already in the proposed direction (higher = favourable)** — the model can lift
these rather than invent them: `regime_state.regime_factor:191` (1.0/0.5/0.25/0.0),
`regime_state.vol_cap_factor:169`, `knife_guard.knife_factor:245`,
`risk_multiplier.combine:37['factor']` (0-1; **0.0 when a hard flag is live**),
`catalyst.build_catalyst_snapshot['scale']` ([0.25, 1.0]), `events.catalyst_risk_penalty:53`
(≤1), `size.composite_position_size:62` legs, executor `risk/voltarget.VolScalar.scalar:92`
(clamped [0.10, 1.5]), `risk/ladder.LadderState.size_multiplier:49`.

**RiskScore is not another alpha factor.** The owner's case is the acceptance
test: `FundamentalScore 92 / TechnicalScore 85 / RegimeScore 78 / RiskScore 35`
must be able to produce **"high quality, strong setup, favourable regime, high
risk → NO NEW RISK"**. That is the repo's existing architecture, not a new
promise: every hard gate already acts **before or independently of** any score.
The repo governor (`risk_governor.govern:37`, called from
`graph/trading_graph.py:980-1071`) turns `risk_context` into PASS/WARN/REJECT +
`risk_halt` **after** the contract and never reads a score; the executor gate
(`../TradingExecution/signald/risk/gate.py`) evaluates **17 fail-closed checks**
in `contracts.GATE_PRECEDENCE` order and its verdict feeds
`risk/sizing.size:144` → `order/guard.guard:290` → `order/stops.protective_orders:194`;
its module docstring states the research risk context *"can never move a
verdict, and it is never read as a number"*, and `'if blocks: verdict, binding =
"BLOCK", blocks[0]'` is the binding rule. `risk_multiplier.combine:37` is the
existing precedent for precedence: `HARD_NAMES = {halt, insufficient_liquidity,
max_portfolio_risk, data_quality_failure, broker_safety}` force the soft product
to **0.0**, with `SOFT_CATALOG = (regime, vol_cap, knife, drawdown, liquidity,
momentum, flow)`.

#### 3.7.6 The composite, the research allocation, and the gate-order conflict

**The staged spec adds two engines and re-weights the composite.** The
pasted-text four-score composite `TradeScore = 0.40F + 0.25T + 0.15R + 0.20K`
is the **first iteration**. `docs/ScoreWeight/news_sentiment.md` (which the
owner staged after the Q1-Q5 decisions) supersedes it with **six engines** —
`FundamentalScore`, `TechnicalScore`, `RegimeScore`, `NewsScore`,
`SentimentScore`, `RiskScore` — and an initial **research** allocation:

| Engine | Initial research weight |
| --- | --: |
| Fundamental | 35% |
| Technical | 20% |
| Regime | 15% |
| Risk | 15% |
| News | 7.5% |
| Sentiment | 7.5% |

The owner labels those *"research weights, not production truth"*, which is the
same rule the category weights already ship under (Q2's ladder): the composite
is `RESEARCH_ONLY` until Phase C measures it. News and sentiment are explicitly
**event/confirmation variables**, not permanent alpha replacements for
fundamentals.

**A conflict between the owner's own two diagrams — flagged, not silently
resolved.** The pasted-text pipeline puts the hard gates *before* sizing
(`TradeScore → HARD GATES → Position sizing`); the staged `news_sentiment.md`
diagram puts them *after* (`DECISION ENGINE → Entry/Hold/Exit → Position Size →
HARD GATES`). They are not equivalent: a gate after sizing must unwind a size it
has already authorised. **The engine's existing behaviour is gates-before-sizing**
— the executor's `risk/gate.py` verdict feeds `risk/sizing.size:144`, then
`order/guard.guard:290`, then `order/stops.protective_orders:194` — so this
document keeps the pasted-text ordering (gates binding, before sizing) and
records the staged diagram as an open question rather than implementing an
inversion (§8.3).

#### 3.7.7 TradeScore — the combination, and what it may not do

```
TradeScore = 0.40·FundamentalScore + 0.25·TechnicalScore
           + 0.15·RegimeScore      + 0.20·RiskScore
```

The pipeline the owner specifies, with the engine's existing pieces named:

```
FundamentalScore ─┐
TechnicalScore   ─┤
RegimeScore      ─┼─→ TradeScore ─→ HARD GATES ─→ Position sizing
RiskScore        ─┘                (executor: 17    (executor risk/sizing.size:144
                                    fail-closed      + risk/voltarget.VolScalar
                                    checks,          + risk/ladder rungs;
                                    GATE_PRECEDENCE) repo size.composite_position_size)
```

Three rules the implementation inherits:

1. **TradeScore never overrides a hard gate.** The gates are evaluated after the
   scores and are binding; a high TradeScore cannot unlock a blocked trade. This
   matches the owner's principle *and* the literature (hard constraints define
   the feasible set; expected return is optimised only inside it) *and* the
   repo's own precedence precedent (`risk_multiplier.combine`).
2. **The weights are a starting hypothesis, learned later.** The owner asks for
   the four weights to be learned empirically rather than permanently
   hard-coded, which is §6 Phase D's ladder — and it is the same rule already
   applied to the category weights: `TradeScore` ships **advisory**, and its
   promotion follows `RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION →
   PRODUCTION`. This is consistent with the earlier withdrawal of
   `TradeScore = 40/25/15/20` *as a production score*: it exists as the
   interaction layer, it is printed, and it is not a measurement until it has
   out-of-sample evidence.
3. **The four scores are not averaged into it silently.** Each component's
   contribution and the weights used are printed (`TradeScore = 61.2
   (F 0.40·88 + T 0.25·61 + R 0.15·68 + K 0.20·54)`), so a reader can see which
   dimension drove the number — the attribution requirement the
   composite-indicator literature makes and the same basis discipline as §3.7.1.

#### 3.7.8 What the scores change in the existing contract

- `FundamentalScore` is §3.1's four sub-scores plus their composite; nothing new
  is needed for the contract, only the band table above.
- `TechnicalScore` / `RegimeScore` / `RiskScore` are **new aggregations over
  existing leaves** — no new vendor, no new model, no new fetch (ground rule 7).
- The score/scale separation means the existing multipliers (`position_scale`,
  `F_regime`, `F_vol`, catalyst scale, vol target scalar) **keep their current
  jobs** and are not folded into a score; the score and the scale are printed
  side by side.
- None of the four reaches `opportunity_score` (Q1) or `SCORE_BANDS` (ground
  rule 6), and none is required in prose (Q5) — they surface through the tool
  leaf / `run_card` block, and `TradeScore` likewise.

---

### 3.8 NewsScore, SentimentScore and EventScore (the staged spec's additions)

The staged `docs/ScoreWeight/news_sentiment.md` adds two engines and recommends a
third, with the separation principle stated as: **NewsScore = information flow**
("what new information has arrived, and how materially could it affect the
company"), **SentimentScore = interpretation/positioning** ("how are investors,
analysts, media and markets positioned or reacting"), **EventScore = occurrence**
("is a high-impact event happening right now"). The owner's own illustration is
the test: *NVIDIA announces a major AI contract* (NewsScore ↑) → *analysts turn
positive* (SentimentScore ↑) → *the stock is +8% on 3× volume* (TechnicalScore ↑)
are **three separate observations, not three votes for the same thing**.

#### 3.8.1 NewsScore — mostly NOT buildable today

Nine components, the owner's weights, readiness measured against the engine
(2026-09-17 inventory):

| Component | Wt | Status | Existing producers | Gap |
| --- | --: | --- | --- | --- |
| News relevance / materiality | 20% | **PARTIAL** | `news_relevance.score_news_article:53` is the only news-side 0-100 score — it scores **relevance, not materiality**; `admit_article:97`, `is_official:48`, `degrade_triple:108` | materiality (would this move the stock?) has no producer |
| News novelty | 15% | **ABSENT** | — | the spec's "repeated-news decay" has no implementation |
| Fundamental impact | 20% | **ABSENT** | — | revenue-impact and margin-impact estimates do not exist |
| Earnings / guidance news | 15% | **PARTIAL** | `events.surprise_score:17`, `drift_side:26`, `position_mult_by_side:37`, `post_earnings_play` (the PEAD leg), `get_earnings_surprise`, `get_earnings_event_read` | **guidance change** has no producer; the surprise leg is real and is the best-supported piece here |
| Corporate events | 10% | **ABSENT** | — | product/partnership/contract/management-change classification does not exist |
| Regulatory / legal | 5% | **PARTIAL** | `text_factors.divergence:198` is the only lexical lawsuit/regulatory signal | no event typing, no severity |
| Analyst / rating changes | 5% | **SCORABLE** | `analyst_revisions.revision_ratio:79` (coverage-guarded), `estimate_change_index:176` (unavailable by construction), `consensus.agreement_score:14` | — |
| Macro / industry news | 5% | **SCORABLE** | `get_macro_regime_read`, `events.catalyst_risk_penalty:53`, `cycle_tilt.macro_stance:128` | industry-level news is not separated from market-level |
| News persistence | 5% | **ABSENT** | — | — |

So **4 of 9 categories have computed inputs** and five are ABSENT. The
literature agrees with the owner's emphasis: **novelty and attention drive
immediate incorporation, and stale or competing information drifts** (Barber &
Odean attention-based trading; the limited-attention reading of PEAD), which is
exactly why "count positive/negative headlines" is the wrong shape and why the
one strong leg here (the earnings surprise + drift) is already implemented.

#### 3.8.2 SentimentScore — buildable from existing leaves, with four holes

| Component | Wt | Status | Existing producers | Gap |
| --- | --: | --- | --- | --- |
| News sentiment | 15% | **SCORABLE** | `sentiment.aggregate_weighted_sentiment:616`, `weighted_rolling_sentiment:722`, `score_from_counts:149`, `aggregate_daily_sentiment:438`, `daily_sentiment_sma:501`; leaves `get_sentiment_computed`, `get_news_sentiment_series` | — |
| Sentiment momentum | 15% | **PARTIAL** | a **7-day innovation** exists (`sentiment_research.sentiment_lead_lag:65` with `innovations=True`) | the spec's `Sentiment_today − Sentiment_20d` has no producer |
| Sentiment breadth | 10% | **PARTIAL** | per-day aggregates exist | no per-source **positive-share** producer (the spec's "percentage of sources expressing positive sentiment") |
| Institutional sentiment | 15% | **PARTIAL** | exists only as a raw level, and it is **bound to the fundamentals toolset** | not on the sentiment surface at all; no change/flow measure |
| Analyst sentiment | 10% | **SCORABLE** | `analyst_revisions.revision_ratio:79`, `consensus.agreement_score:14` / `weighted_consensus:32`, `get_analyst_verdict` | — |
| Retail / social sentiment | 10% | **SCORABLE** | `sentiment.compute_social_scores:273`, `crowd_ratio:163`, `mention_volume:43`, `sentiment_velocity:25` | the two most useful helpers (`sentiment_velocity`, `mention_volume`) are **unwired** |
| Options sentiment | 10% | **SCORABLE** | `get_options_iv_read:6034`, `get_derivatives_flow:3142`, `get_options_surface:7553`, `get_orderflow_read:1215` | — |
| Short-interest sentiment | 5% | **PARTIAL** | `get_short_sale_volume:8886` (raw) | no percentile or change basis |
| Sentiment dispersion | 5% | **SCORABLE** | `sentiment.sentiment_dispersion:209` | — |
| Sentiment extreme / crowding | 5% | **PARTIAL** | a display-only social band | no crowding/extreme measure with a stated scale |

The evidence says the same thing about *how* to read these: media pessimism
predicts **next-day declines followed by a reversal within days** and extremes
predict **volume** (Tetlock); high aggregate sentiment predicts **lower**
subsequent returns in hard-to-value, hard-to-arbitrage names (Baker & Wurgler);
and attention and sentiment are **different signals with opposite short-horizon
signs** — attention spikes predict negative next-day returns while bullish
sentiment predicts positive ones, with small caps more sensitive to both (Da,
Engelberg & Gao and the StockTwits literature). Three consequences the design
must carry:

1. **Sentiment is short-horizon and partly reversing**, so it cannot be a
   permanent alpha weight — consistent with the owner's 7.5% research weight and
   with its placement as an event/confirmation variable.
2. **Attention ≠ sentiment.** The engine must not merge mention volume with
   tone: they point in opposite directions at short horizons.
3. **The price→sentiment feedback is real** (low returns produce more pessimistic
   tone), which is precisely why the confirmation check below matters.

#### 3.8.3 The duplicate question is NOT settled by construction

The owner requires that NewsScore not become a duplicate of SentimentScore. The
inventory found **four places where the same numbers already feed both**:

| Coupling | Evidence |
| --- | --- |
| The news path's relevance **is** the sentiment aggregation's confidence weight | `strategies/sentiment.py:589 _weighted_basis` |
| One leaf serves both surfaces | `get_news_sentiment_series` is bound to `news_tools()` (`agents/toolsets.py:352`) **and** `market_tools()` (`:279`) |
| The sentiment analyst pre-fetches the news analyst's leaf | `agents/analysts/sentiment_analyst.py:88` |
| A bundled endpoint already merges the two feeds | `domain_bundles.get_sentiment_flow_feed:93` |

This is not a defect in itself — one producer feeding two readers is the repo's
rule, not a violation of it — but it means the *separation the owner wants is a
design requirement that must be enforced by naming*, not an emergent property:
each engine states which producer each of its components read, and a component
that would read the other engine's number is either dropped or renamed. Without
that, "NewsScore" and "SentimentScore" would be two labels over one signal.

#### 3.8.4 Sentiment × Price Confirmation — the divergence verdict

The owner's rule is *"don't assume positive sentiment is bullish"*, with the
2×2: positive+rising = confirmed positive, positive+falling = **divergence**,
negative+falling = confirmed negative, negative+rising = **divergence**.

Today this is **PARTIAL**: `sentiment_research.sentiment_lead_lag:65` (with
`innovations=True`) computes `Corr(dSentiment, dPrice)` per name and is surfaced
by `get_sentiment_lead_lag`; the wired fold
`sentiment_research.sentiment_factor_scale:570` uses sign-agreement between the
**measured historical IC direction** and today's innovation (gated off by
default). What is missing is the owner's actual output shape: a
`Sign(dSentiment) × Sign(abnormal return)` **quadrant label**, and a
market-adjusted (abnormal) return on that path. Design: the quadrant is the
*interface* — "sentiment = +0.72" alone is not actionable, and the literature's
attention-versus-sentiment split shows why the sign of the tone is not the
signal.

#### 3.8.5 EventScore — the seventh engine, and its overlap with RiskScore

The staged spec recommends adding **EventScore** *"before allowing NewsScore to
influence `opportunity_score`"*, to separate *"the company received positive
news"* from *"there is a high-impact event occurring right now"* (earnings, FDA,
CPI/FOMC, product launches, court decisions, investor days, OPEX).

Producers already exist and are the *same family* the RiskScore's event
component reads: `catalyst.build_catalyst_snapshot:219` (a `scale` in [0.25, 1.0]
**plus a `hard_block` flag**), `next_earnings:90`, `fed_imminence:142`,
`macro_imminence:123`, `events.surprise_score:17` / `catalyst_risk_penalty:53`,
`pre_market` gap/event reads, and the options/OPEX family
(`get_options_*`, `get_derivatives_flow`).

**The overlap must be resolved explicitly**, because two engines claiming one
number is the failure mode this document keeps refusing: EventScore answers
**"is a high-impact event occurring now"** (occurrence + imminence + the hard
block), while RiskScore's event leg answers **"how dangerous is that event for
this position"** (the implied/expected move against the loss budget). Same
producers, different questions — so EventScore's components must be the
*occurrence* measures and RiskScore's the *exposure* measures, and neither may
re-derive the other's number (§3.8.3's naming rule).

#### 3.8.6 What the three engines change

- The composite becomes **seven engines** if EventScore is adopted. The staged
  spec's research allocation covers six (35/20/15/15/7.5/7.5); **EventScore has
  no weight in it** — either it takes a slice of the existing weights, or it
  enters as *context* (a hard block plus a printed imminence) rather than as a
  weighted score. That is an open question, recorded in §8.3.
- NewsScore ships **late**: five of its nine categories are ABSENT, so Phase E
  can only ship a partial engine, and a partial engine must print its coverage
  (the same rule as `NA ≠ 0`).
- No news/sentiment/event 0-100 score exists anywhere today. The only existing
  composites in this space are the LLM-produced `SentimentReport.overall_score`
  (0-10, `agents/schemas.py:463`, anchored to the deterministic `computed_score`),
  `aggregate_weighted_sentiment`'s per-day weighted score, and the
  `sentiment_factor_scale` multiplier (0.8/1.0/1.2, gated off). The 0-10
  `overall_score` is the **analyst's** output, not an engine score, and must not
  be re-labelled as one.

---

## 4. Decisions, refusals, and deferrals

### 4.1 Decided by the owner (2026-09-17) — three items this document had refused

Each was refused here for lack of an owner decision or lack of evidence, not on
principle. The decisions change the *scope*, never the ground rules.

| Item | Decision | What it changes |
| --- | --- | --- |
| Walk-forward **learned** weights | **In scope as a separate research layer**, never inside the deterministic production score. The vector must earn its way: `RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION` | §3.1's status vocabulary; §6 Phase D's ladder; the comparison is baseline-vs-learned on **IC, decile monotonicity, spread, stability** — an in-sample improvement promotes nothing |
| **Sector overlays** (banks/REITs/insurance) | **Architecture in scope now; suppliers deferred.** The factor schema carries `sector_scope`/`supplier`/`availability` from the first commit; the metrics stay `NA` until a supplier exists | §3.2's schema table and the `NA ≠ 0` rule. **Do not manufacture a missing metric from generic factors** — a bank scored on `ev_ebit` is not a bank score |
| **Evaluation universe** | **The full EODHD US panel** (`resolve_peer_universe`) is the official validation universe; the named basket is dev/diagnostic only and is labelled `INSUFFICIENT_CROSS_SECTION` | §6 Phase C. A 9-name cross-section is useful for diagnostics and inadequate for factor validation — it may not produce authoritative weights |

### 4.2 Still refused outright

| Source item | Why not |
| --- | --- |
| "Starting **production** weights" shipped as production (its Phase 1) | Ground rule 2 ("no weight vector is invented") and DeMiguel et al.: estimated weights usually lose to `1/N` out of sample. The weights ship as an **equal-weight default plus a named table that is printed as a hypothesis**, and the table is only promoted after §6 Phase C measures it. The owner's 2026-09-17 decision extends this to *any* composite, including his own earlier `TradeScore = 40/25/15/20`: an unvalidated combination is a research artifact. |
| **Regime-conditional** weights as a default | Asness et al.: factor timing is deceptively difficult; conditional weights rarely improve robustly. Keep `regime` as a *printed context*, not a weight modifier, until Phase C evidence exists. |
| Manufacturing bank/REIT metrics from **generic** factors | Q3 keeps the architecture overlay-ready but forbids substitution: `NA` is not `0`, and a proxy is not the metric. The missing inputs are listed in Appendix B. |
| The literal `1/(1+Σ|Corr_ij|)` penalty constant | Structure yes, constant no: it is untested, and on a 106-factor panel with correlated families it can drive a redundant pair's combined weight below a single member's. Use cluster-representative selection or the penalty with a floor, and measure the effect (§6 Phase B). |
| A single master number as the interface to the executor | **Decided: never, for now** (Q1). The `opportunity_score` slot is deliberately `null` (`execution_contract.py:240-252`) and now gains a published *reason* (§5.2) instead of a number. |
| ML replacement of the deterministic scores | Round-3 already refused this (McLean–Pontiff decay is the supporting evidence). Q2 does not reopen it: the learned vector lives in the research layer, and only a validated vector with a completed contract migration may reach production. |

### 4.3 Deferred (in scope later, each with a trigger)

| Item | Trigger to start |
| --- | --- |
| Insider routine-vs-opportunistic classification (#101-#106) | Needs Form 4 transaction codes in XML (already a deferred data-source project). Until then the prompt rule `INSIDER WEIGHTING` stands and the category stays at 2%. |
| Distress maturity-wall (#100) | Needs a debt-maturity dataset; no vendor currently supplies it. |
| Capital-returns dividend growth (#90) | Needs a dividend series producer; `get_corporate_actions` supplies raw history only. |
| Bank/REIT overlay **metrics** (the architecture is already in scope, Q3) | A data-supplier decision (Appendix B lists exactly what is missing). |
| Merton distance-to-default as a factor (#97) | Needs a tool that resolves equity/debt/equity-vol from the statement chain instead of requiring caller input. |

### 4.4 Two source items that are actually already better in this repo

1. **Distress (2%).** The source asks for Altman Z, Ohlson O, Merton, coverage
   stress, liquidity stress, maturity risk at 2% total. The repo has Altman Z
   **plus three variants with zone bands and applicability selection**
   (`altman_variant_for` withholds the score for non-manufacturers),
   Ohlson O **and** Zmijewski X. Do not re-implement; re-point.
2. **CapEx quality (§3.5).** `capex_quality_read` is more complete than the
   source's two-line formula and already carries the AMZN review's lesson.

---

## 5. Wiring and contracts

The cheap path and the expensive path differ by an order of magnitude in blast
radius. Decide deliberately.

### 5.1 Cheap path — a tool leaf (recommended for Phases A-B)

A new `get_fundamental_factor_model(ticker, current_date)` (or an extension of
`get_quality_factors`) that returns the sub-scores, the factor book, the
weights used, coverage and withheld names. Consequences:

| Must update | Why |
| --- | --- |
| `agents/toolsets.py::fundamentals_company_tools` (`:378-435`) | else `tests/test_calc_agent_wiring.py:239-244` fails (every `@tool` must be bound or declared) |
| `agents/utils/analysis_tools.py` `__all__` (`:9150-9215`) | registry export |
| `agents/analysts/fundamentals_analyst.py` | one trigger line (`tests/test_prompt_trigger_contract.py`) + arity matching the real signature (`tests/test_prompt_signature_contract.py`); stays under `MARKET_CEILING = 50_000` (fundamentals measured 27,617) |
| `docs/api_reference.md` "Bound to" table | machine-checked by `tests/test_doc_binding_claims.py` |
| `agents/utils/report_verifier.py::_INTERNAL_CONFLICT_METRICS` (`:880-977`) | only if the score becomes a quotable metric in prose |
| Evidence is automatic | a tool leaf lands in `tool_evidence.json` + the frozen rendered block + `run_card["evidence"]` with no extra wiring |

No cross-repo change, no hash change, no `research_decision.json` change.

### 5.2 Expensive path — a numeric decision score on the wire

Wiring the composite into `opportunity_score` would touch, in order:
`tradingagents/execution_contract.py:240-296` (the deliberate `None` and
`envelope_fields`) → `reporting.write_research_decision:583-730` (the sealed
body, hence `artifact_sha256` and `decision_hash` for **every** artifact) →
`contracts/research_decision.v1.schema.json` **and** the byte-identical copy at
`../TradingExecution/contracts/research_decision.v1.schema.json`
(`tests/test_execution_contract.py:134-142` diffs them) →
`../TradingExecution/signald/{schema,contracts,processor}.py` (range check
`215-227`, envelope emission `323-370`).

**Q1 decided: never, for now.** The composite stays a tool leaf + `run_card`
advisory key, and `opportunity_score` stays `null`. The migration above is
therefore **not scheduled** — it is the cost of a future decision, not this
one's.

**What does change (still a contract migration, so designed, not built):** the
`null` gains a published **reason**, so a reader of the artifact knows the
absence is a decision rather than a missing value. The owner's shape:

```json
"opportunity_score": null,
"opportunity_score_reason": "Not published: composite fundamental score has not
  demonstrated sufficient out-of-sample predictive validity to qualify as an
  opportunity measurement."
```

That string is a *producer-owned constant*, not prose the model writes — it
belongs beside `opportunity_score()` in `execution_contract.py` (which already
returns the deliberate `None` with its rationale in the docstring, so the reason
exists today only where a reader of the source can see it). Adding the key
touches the sealed body, so it carries the same `artifact_sha256` /
`decision_hash` consequences as any envelope change and must land with the
vendored-schema diff test (`tests/test_execution_contract.py:134-142`). Note
also that a *constant* reason string adds no per-run variance: it cannot leak
into the executor's ranking because the executor does not read it as a number.

### 5.3 Two silent couplings to respect

- `agents/researchers/structured_debate.py:280-313` parses `key=value` numeric
  pairs out of the fundamentals **prose** into debate ground truth. Any
  `factor_score=NN` line printed into the report text becomes a debated claim
  automatically. **Q5 decided: no score in prose**, which closes this coupling
  rather than exploiting it. Consequences, all of which the implementation must
  respect:
  - The composite reaches the reader through **structured output** —
    `{fundamental_score, fundamental_score_status, fundamental_score_confidence}`
    in the tool leaf / `run_card` advisory block — never as a narrative number.
  - **No prompt rule may require quoting the score.** The prompt may say what
    the *factors* show ("profitability and cash generation are strong, valuation
    is a constraint"); it may not ask for `FundamentalScore = NN`.
  - The existing `get_composite_rank` prompt line ("cite its standing vs peers")
    stays as it is: a percentile *standing within a named peer set* is a
    measurement of position, not a weighted quality index — the distinction the
    decision turns on. The gated `quality composite` row is already a structured
    diagnostic line, which is exactly where Q5 wants scores to live.
  - The verifier therefore gains **no** new quotable metric, and
    `_INTERNAL_CONFLICT_METRICS` stays untouched by this feature.
- `alpha_health.score_evaluation_rows` is the IC harness and
  `scripts/alpha_health.py` the wired ledger reader; a fundamental panel is a
  new *caller*, not a new evaluator. One implementation per computation.

---

## 6. Phased plan

Each phase is default-off behind a new gate (`enable_fundamental_factor_model`,
plus `enable_factor_confidence` and `enable_factor_redundancy` if they land
separately), flipped one at a time under the dark-launch protocol (ground rule
10): labelled run, same basket, `scripts/repro_check.py --evidence` diff,
`scripts/report_verify.py`, `scripts/verify_sweep.py` exiting 0 on CONFIRMED.

### Phase A — the catalogue and the VS sub-score (no new numbers, no new weights)

1. Extract the shared core out of `factors.quality_composite` into a
   category-parameterised pure function; four wrappers; per-category band
   tables; the `basis` string names the metric set, floor, weights and whether
   they were equal.
2. **Fix the sector-percentile defect** (§3.2): within-sector percentile, or
   rename the band label. Test either way.
3. Ship the VS sub-score first — 13.25 of 20.0 weight is already COMPUTED, so
   it is the only category that can be scored honestly on day one.
4. Expose the §1.3 wiring gaps that are pure expositions (gross margin, WC/TA,
   debt growth, asset growth, receivable/inventory days, `interest_expense`
   coverage, level ROIC, IC turnover, buyback/total shareholder yield, EV/FCF).
   These are not scoring changes; they are values the engine already has.

Acceptance: a tool leaf prints `quality/growth/valuation/risk: NN/100 (band)` +
coverage + withheld, on the real peer universe; with the gate off, byte-identical
output to today; every new number reproducible from the leaf's own printed
inputs.

### Phase B — confidence, redundancy, data quality

1. Implement the derived A/B/C/D grade (§3.3) over
   `data_quality.aggregate_quality`/`disagreement_flag` + coverage + basis
   conflicts. No hand-assigned grades.
2. Build the fundamental correlation panel (the repo has none) and implement
   redundancy as cluster representatives, with the naive `1/(1+Σ|Corr|)` behind
   a flag so the two can be compared.
3. Implement `dcf_confidence` over the four printed legs (§3.4) and scale the
   DCF upside factors by it.

Acceptance: a factor that is a vendor passthrough, or whose input is
`unavailable`, or whose producers disagree, demonstrably loses weight, and the
loss is printed per factor.

### Phase C — measure, don't assume (universe decided: the full EODHD panel)

**Q4 decided: the full EODHD US panel is the official validation universe**
(`peer_universe.resolve_peer_universe` — the EODHD US common-stock list filtered
to NYSE/Nasdaq, or an explicit list), with eligibility filters, survivorship
controls, a minimum-liquidity floor and a minimum-observations floor before any
factor is computed. The named basket stays a **dev/diagnostic** universe.

1. Build the fundamental panel `{date: {ticker: score}}` over that universe with
   a point-in-time discipline (the `PIT` invariant already exists in
   `data_quality.fundamentals_pit_ok`; `enable_pit_registry` is the existing
   gate). Forward-return labels come from the `_ohlcv` chain, joined exactly as
   `scripts/alpha_health.py::_monitor_report` already joins them.
2. **Label the cross-section before computing anything on it.** Any panel that
   fails the floors is reported `VALIDATION_STATUS = INSUFFICIENT_CROSS_SECTION`
   and produces **no** authoritative factor weight. *Known gap to close here:*
   `alpha_health.score_evaluation_rows(scores_by_date, prices, holding=5,
   n_buckets=10, min_names=4, min_obs=5)` is the ready-made harness, but its
   floors are a smoke floor (4 names) and it emits no insufficiency status — it
   does say its rows "are inputs to the DSR/PBO multiple-testing check, never a
   standalone verdict", so nothing today reads it as one. Adding the status is
   part of this phase, before any weight fitting is authorised.
3. Compute, per factor and per category, over the panel:
   `IC_i,t = Corr(Factor_i,t, Return_t+H)`; `MeanIC_i = (1/T)·Σ_t IC_i,t`;
   `ICIR_i = Mean(IC_i) / Std(IC_i)`; `DecileSpread = Return(D10) − Return(D1)`;
   `Monotonicity = (# correctly ordered adjacent decile pairs) / 9`. The
   harness's rows supply IC/ICIR, deciles + monotonicity, coverage and
   stability; the multiple-testing discipline is
   `evaluate.purged_cpcv_splits` / `deflated_sharpe` / `pbo_flag` /
   `reality_check` / `spa`.
4. Report per-factor rank IC with its t-stat, turnover and stability by year;
   **then, and only then**, compare the candidate weight vector against equal
   weights on the same panel. Publish the result either way — a table that loses
   to `1/N` is a finding, not a failure.

Acceptance: a table of measured IC per factor with the weight comparison, the
`VALIDATION_STATUS` line on every panel, and a written decision on whether the
source's weights are promoted, modified, or replaced by equal weights.

### Phase D — the research layer and the promotion ladder (Q2 decided: yes, as research)

**In scope, but never inside the deterministic production score.** Phase D
estimates `w*_i = f(IC_i, IC stability_i, decile spread_i, redundancy_i,
sector_i)` on walk-forward samples and compares the learned vector against the
deterministic baseline on the same four statistics — IC, decile monotonicity,
spread, stability. An in-sample improvement promotes nothing.

The promotion ladder, each step evidenced and none automatic:

```
RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION
```

- `RESEARCH_ONLY`: computed, stored, labelled; no consumer beyond the research
  path. The repo's precedents for this shape are `enable_tuner` (Q19) and
  `enable_factor_proposal_loop` (Q11, "LLM-proposed candidates, math decides").
- `VALIDATED`: out-of-sample evidence on the full panel, with the DSR/PBO
  multiple-testing discipline and the CPCV masks — i.e. the vector survived the
  tests designed to kill it.
- `CONTRACT_MIGRATION`: only if the validated vector is ever to reach a
  consumer, which for `opportunity_score` is the §5.2 migration and remains
  **not scheduled** (Q1).
- `PRODUCTION`: the deterministic score stays the production score unless the
  owner promotes a validated vector explicitly. Ground rule 1's
  deterministic-and-auditable requirement is not relaxed by this phase.

### Phase E — the other three scores and TradeScore (§3.7)

Independent of Phase A's fundamental work, and ordered so that nothing new
reaches a decision:

1. **Arbitration first (RegimeScore).** Pick one producer per component, or
   define an explicit arbitration rule that stores its reason. The engine has two
   independent regime producers bound to the same analyst (§3.7.4), so this step
   is a decision, not a wiring job — and it is blocked on defects 1-2 of §1.5,
   because the label one of them returns can be trend-blind.
2. **Direction policy.** Every component declares its polarity and prints the
   raw value with its units beside the aligned contribution (§3.7.1). The three
   inconsistent conventions (CVaR sign, drawdown sign, cap type) are resolved at
   this boundary, not by changing the producers.
3. **TechnicalScore** as an aggregation of existing leaves (§3.7.3), with the
   five polarity conflicts declared per component and the mixed-state case
   (strong trend + deteriorating momentum + setup NO) as its acceptance test.
4. **RiskScore** as a new model over existing producers (§3.7.5), with the
   score/scale separation respected: the existing multipliers keep their jobs.
5. **NewsScore and SentimentScore** (§3.8) — separate engines for *information
   flow* and *interpretation*, with the duplicate-question test the owner
   insists on ("NVIDIA announces a contract" is one observation, "analysts turn
   positive" is another, "the stock is +8% on 3x volume" is a third) and the
   sentiment × price confirmation check (positive sentiment with falling price
   is a **divergence**, not a buy).
6. **EventScore** (§3.8.5) — occurrence, not exposure — with the overlap against
   RiskScore's event leg resolved by naming, and the staged spec's own reason for
   it respected: it is the gate between NewsScore and any influence on
   `opportunity_score`.
7. **The composite** last, printed advisory with its attribution
   (`61.2 (F 0.35·88 + T 0.20·61 + R 0.15·68 + N 0.075·72 + S 0.075·54 + K 0.15·54)`),
   and with a test proving it cannot unlock a blocked trade.

Acceptance: the four scores and `TradeScore` print on one leaf; a hard-gate
block survives a maximal `TradeScore`; the mixed-state MSFT case produces a
moderate score whose components show the disagreement; and with the gate off the
run output is byte-identical.

---

## 7. Verification requirements

- Every new pure function gets a test that **fails under a mutation** of the
  code it guards (ground rule 4). For a composite: flip a direction sign, drop
  the coverage floor, remove the renormalisation — each must break a test.
- The renormalisation and coverage behaviour is pinned on a synthetic panel with
  known answers (a name with 3 of 7 metrics present must be withheld at
  `min_coverage=3` if the floor resolves above 3, and scored otherwise).
- Weights must be **printed**: a test asserts the `basis` string contains the
  weight vector actually used, so no run can silently change its weights.
- No factor may be scored from a vendor passthrough without the leaf saying so.
- With the gate off, the tool must not exist in the toolset and the run output
  must be byte-identical (the existing gate convention).
- `metric_reconcile` / `disagreement_flag` must fire on a synthetic
  two-vendor disagreement, proving the confidence leg can fail.
- **`NA ≠ 0` is pinned (Q3):** a panel where one factor is absent for a name
  must renormalise over the present factors and never score the absent one as
  `0`; a name below the coverage floor is withheld with its reason, and a
  `sector_scope` factor with no supplier contributes no weight at all.
- **No score in prose (Q5):** a test asserts no analyst prompt string requires a
  composite score in the narrative (the existing
  `tests/test_analyst_evidence_wiring.py` pattern for named rule strings is the
  place), and that the score reaches the reader only through the structured
  leaf / `run_card` block.
- **Validation status is pinned (Q4):** a panel below the cross-section floors
  reports `INSUFFICIENT_CROSS_SECTION` and yields no weight vector; the test
  must fail if the label is dropped.
- **The composite is not on the wire (Q1):** a test asserts the advisory score
  does not reach `research_decision.json` / `opportunity_score`, and that the
  reason constant is present and stable when that key is added.
- **Direction is pinned per component (§3.7.1):** a test asserts each component's
  raw value and its aligned contribution have the declared relationship (e.g.
  inverting the alignment must move the score the other way), and that the
  `RiskScore` leg is *inverted* relative to its producers' native loss sign.
- **The five polarity conflicts stay declared (§3.7.3):** RSI, MFI, stochastic,
  the elder thermometer and the support-proximity read must each carry their
  polarity, and a mutation that makes one of them monotone must fail a test.
- **`TradeScore` cannot unlock a gate (§3.7.6):** a test drives the executor's
  gate to BLOCK and asserts a maximal `TradeScore` changes nothing — the same
  shape as the existing `risk_multiplier.combine` hard-flag test.
- **Score and scale stay separate (§3.7.4):** a test asserts the regime sizing
  scale is not an input to `RegimeScore` and vice versa, so a hostile regime
  cannot rewrite the score and a good score cannot inflate the size.
- **Arbitration is recorded (§3.7.4):** whichever regime producer a component
  reads, the leaf names it, and a test asserts the name is printed.

---

## 8. Decision record (owner, 2026-09-17)

The five questions this document opened are answered. Recorded with the
rationale, because the reasoning is what future changes have to respect.

**Q1 — Does a composite fundamental score ever reach `opportunity_score`?**
**Decided: (a) never, for now.** It stays a tool-leaf / `run_card` advisory
metric. *Rationale (owner):* "The current 'would dress an estimate up as a
measurement' rationale is sound." A deterministic `FundamentalScore = 84` does
not imply `Opportunity = 84` — a name can have outstanding fundamentals with
poor current opportunity characteristics (`FundamentalScore 92`,
`TechnicalScore 61`, `RegimeScore 68`, `RiskScore 54`, `ValuationScore 37`). The
distinction preserved is **measurement vs interpretation**: the artifact keeps
`opportunity_score: null` and gains a producer-owned
`opportunity_score_reason` (§5.2).

**Q2 — Learned walk-forward weights?**
**Decided: yes, as a separate research/experimental layer — not in the
deterministic production score yet.** *Rationale (owner):* removing Phase 4
merely because the current rule is deterministic would be wrong; what matters is
that the learned vector is compared against the deterministic baseline on IC,
decile monotonicity, spread and stability, and does not become production "merely
because it improves in-sample results". Promotion is the ladder
`RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION`; the schema /
contract / hash migration is only reached at step three (§5.2, §6 Phase D).

**Q3 — Sector overlays?**
**Decided: yes — architecture in scope now, suppliers deferred.** The factor
schema carries `sector_scope` / `supplier` / `availability` from the first
commit (`ROIC scope=ALL`, `NIM scope=BANKS`, `CET1 scope=BANKS`,
`ROTCE scope=BANKS`, `FFO_Yield scope=REITS`, `AFFO_Yield scope=REITS`,
`NAV_Discount scope=REITS`, `Occupancy scope=REITS`). Until a supplier exists
they are `NA`, **not zero** — *"missing data should reduce the available factor
weight, rather than punish the company"* — and the design must **not manufacture
missing metrics from generic factors** (§3.2, §4.2).

**Q4 — Evaluation universe?**
**Decided: the full EODHD US panel** is the official validation universe; the
named basket stays a development/test universe and is labelled
`VALIDATION_STATUS = INSUFFICIENT_CROSS_SECTION` — *"rather than allowing it to
produce authoritative factor weights"*. IC, ICIR, decile spread and
monotonicity only become meaningful with hundreds/thousands of eligible names
(§6 Phase C).

**Q5 — `factor_score=NN` in prose?**
**Decided: no.** The number lives in structured output
(`fundamental_score`, `fundamental_score_status`,
`fundamental_score_confidence`); narrative states quality in words. *Rationale
(owner):* a bare score in prose "creates an apparent objective ground truth",
after which every verifier/report comparison asks why 84.2 and not 81.7, which
factor moved it, and whether 84.2 beats 78.4 — turning an **advisory composite
into a quasi-official measurement** (§3.1, §5.3).

### 8.1 What the decisions changed in this document

| Section | Change |
| --- | --- |
| §0.5 | new — the decision summary and the three-stage separation |
| §3.1 | the sub-scores are advisory, the composite is a research artifact with a status vocabulary; the five-score contract |
| §3.2 | the per-factor schema (`sector_scope`/`supplier`/`availability`) and the `NA ≠ 0` rule |
| §4.1 | new — the three previously-refused items are now decided, with scope; §4.2 keeps the genuine refusals |
| §5.2 | Q1's reason field designed (a producer-owned constant, contract migration, not scheduled) |
| §5.3 | Q5 closes the prose-ground-truth coupling; the prompt may state factors, not the score |
| §6 Phase C | the EODHD validation universe, the four statistics, `INSUFFICIENT_CROSS_SECTION`, and the `score_evaluation_rows` floor gap |
| §6 Phase D | the research layer and the promotion ladder |
| §7 | verification requirements for `NA ≠ 0`, no-score-in-prose, the validation status and the wire exclusion |
| **§1.5** | **new (second pass)** — six code defects found while grounding the four scores, recorded and NOT fixed (design-only pass): the dead chop branch that makes `get_regime_read` trend-blind, the two incompatible choppiness scales, the unreachable Donchian breakout flags, `parabolic_sar` called without `closes`, `BookState.net_beta` with no reader, and the constant gap statistics |
| **§3.7** | **new (second pass)** — the four-score architecture: direction convention (100 = favourable, `RiskScore` inverted), `FundamentalScore` bands, `TechnicalScore` / `RegimeScore` / `RiskScore` component tables with per-component readiness against the existing leaves, the five technical polarity conflicts, the regime name-collision and its arbitration requirement, the score/scale/state/confidence separation, and `TradeScore` with the three rules it inherits |
| **§6 Phase E** | **new (second pass)** — the ordering for the other three scores and `TradeScore`, arbitration first, and the acceptance test that a hard-gate block survives a maximal `TradeScore` |
| Appendix C.2 | **new (second pass)** — the evidence ledger for the four-score architecture |

### 8.2 The architecture the decisions produce

```
                    RESEARCH
                       │
            ┌──────────▼──────────┐
            │ Factor measurements │   IC / rank IC · decile spreads
            │                     │   stability · redundancy
            └──────────┬──────────┘
                       │
                 SCORE ENGINE
                       │
            ┌──────────┴──────────┐
            │                     │
     Deterministic             Learned
        weights                weights
            │                     │
            ▼                     ▼
     ProductionScore        ResearchScore
            │                     │
            ▼                     └── RESEARCH_ONLY → VALIDATED →
     run_card advisory                 CONTRACT_MIGRATION → PRODUCTION
            │
            X   NOT automatically opportunity_score (Q1)
            │
            ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  FundamentalScore  TechnicalScore  RegimeScore  NewsScore      │  §3.7-§3.8
   │  SentimentScore    RiskScore       (EventScore recommended)    │
   │  (100 = favourable for all; RiskScore 100 = low risk)          │
   └───────────────────────────┬───────────────────────────────────┘
                               ▼
      research allocation: 35 / 20 / 15 / 7.5 / 7.5 / 15   (owner's
      staged spec; the earlier 4-score TradeScore = .40F+.25T+.15R+.20K
      is the first iteration, §3.7.6)                      advisory,
                               │                           weights learned later
                               ▼
                  ┌────────────────────────────┐
                  │  HARD GATES (binding)      │  executor: 17 fail-closed
                  │  never overridden by a     │  checks, GATE_PRECEDENCE;
                  │  score                     │  repo: risk_governor PASS/WARN/REJECT
                  └────────────┬───────────────┘
                               ▼
                  Position sizing (score ≠ scale: the
                  multipliers keep their own jobs)
```

### 8.3 Open questions raised by the staged spec (2026-09-17, second pass)

1. **Gate order.** The pasted-text pipeline puts the hard gates *before* sizing;
   the staged `news_sentiment.md` diagram puts them *after*. The engine
   implements gates-before-sizing (the executor's gate verdict feeds
   `risk/sizing.size:144`). This document keeps the implemented order and treats
   the staged diagram as unconfirmed — an inversion must be an explicit
   decision, because a gate after sizing has to unwind a size it already
   authorised (§3.7.6).
2. **Which composite governs.** `TradeScore` (4 scores, 40/25/15/20) versus the
   six-engine research allocation (35/20/15/15/7.5/7.5). Both are the owner's;
   the staged one is newer and the document treats it as governing, with the
   4-score version recorded as the first iteration. If both are wanted — a
   4-score decision composite *and* a 6-engine research composite — they must be
   named differently so a reader cannot confuse them.
3. **EventScore's weight.** The staged spec recommends the engine but its
   allocation covers only six (35/20/15/15/7.5/7.5). Either EventScore takes a
   slice, or it enters as context (hard block + printed imminence) rather than as
   a weighted score — and if it is weighted, its components must be the
   *occurrence* measures while RiskScore's event leg keeps the *exposure* ones
   (§3.8.5), or two engines will claim one number.
4. **The news/sentiment separation must be enforced by naming.** Four couplings
   already feed one number to both engines (§3.8.3). The owner's requirement
   ("don't let NewsScore become a duplicate of SentimentScore") is therefore a
   build-time rule, not an emergent property: each engine names the producer of
   each component, and a component that would read the other engine's number is
   dropped or renamed.
5. **The owner's staged docs themselves** (`docs/ScoreWeight/*.md`) are
   uncommitted and modified in the working tree. They are the owner's work, so
   they are **not** committed by this document's commits; whether they should be
   tracked as the specification of record is the owner's call.

**Still open, and only these** (each is a data or measurement question, not a
design question):

1. **Suppliers** for the sector-overlay metrics (bank NIM/CET1/ROTCE, REIT
   FFO/AFFO/NAV/occupancy) — Q3 defers them.
2. **Whether the validation panel can be built** from the EODHD bulk fetch
   within the existing rate limits and run budget — Q4 names the universe, not
   the fetch plan.
3. **The measured IC table** — until Phase C produces it, every weight in §2 is
   still a hypothesis, and the document's stance on the source's numbers does
   not change.

---

## Appendix A — the source tables, verbatim

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

### A.2 The arithmetic check

The right-hand column is the sum of the individual factor weights the source
prints inside each category. Four categories do not add up to their own stated
total; the grand total is 104.00% against a stated 100%. Reproduce by summing
the tables in §2.1-2.10 (the "Prop. wt" column).

### A.3 Per-factor weights as proposed

Reproduced in the "Prop. wt" column of every §2 table, in the source's own
order (#1-#106), so §2 doubles as the verbatim weight table. Factor names,
directions, normalisation rules and redundancy groups are as printed by the
source; where a source direction carries an asterisk the asterisk is reproduced
in §2's notes.

### A.4 Source's other proposals (not tables)

Four sub-scores with coefficients `0.35/0.25/0.25/0.15`; the `EffectiveWeight`
product chain; the A/B/C/D confidence multipliers `1.00/0.85/0.60/0.30/0`;
`RedundancyPenalty_i = 1/(1+Σ_j|Corr_ij|)`;
`DCFConfidence = DataQuality × AssumptionStability × FCFStability ×
TerminalSensitivity`; `CapExQuality = GrowthGeneratedByCapEx −
CapitalIntensityPenalty`; sector overlays for Technology / Banks / Utilities /
REITs; four implementation phases. All are addressed in §3 and §4.

---

## Appendix B — what the canonical vocabulary cannot express

From `dataflows/statement_parsing._ROW_ALIASES` (75-192): **35 keys**, aliases in
match-priority order. The factors in §2 marked ABSENT are bounded by these gaps,
not by missing formulas:

| Missing key | Blocks |
| --- | --- |
| `ebitda` | #7 EBITDA margin, #21 EBITDA growth, #33/#34 FCF\|OCF ÷ EBITDA, #60 net debt/EBITDA |
| `deferred_revenue` | #79 (and `revenue` deliberately excludes `deferred`/`unearned` labels) |
| `goodwill` / `intangibles` | bank P/TBV reasoning, ROTCE |
| R&D / advertising (referenced by `growth_metrics` but never aliased) | G-Score G6/G8 legs |
| `roa_series` / `revenue_series` | #80 earnings volatility, G-Score G4/G5 — produced since 2026-09-17 (§1.4), still bounded by the 4-5 year vendor history |
| multi-year tag series | #14/#17/#18/#20/#23/#38/#90 CAGR family |
| segment data | any segment-level factor (vendor passthrough only) |
| bank/REIT operating metrics | NIM, CET1, ROTCE, FFO, AFFO, NAV, occupancy, non-performing loans, deposit growth, efficiency ratio |
| debt maturity schedule | #100 |

Keys that exist with **zero code consumers** (their only mentions are the alias
table and the `quantitative_scores.py` vocabulary docstring): `interest_expense`
(#64, #98), `share_buybacks` (#92, #94), `debt_repayment`; plus `sga`, `cogs`
and `retained_earnings`, which are read only inside Beneish/GP-A/Altman.

---

## Appendix C — source ledger (external evidence)

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

### C.2 Evidence ledger for the four-score architecture (§3.7)

| # | Source | Used for |
| --: | --- | --- |
| 13 | Grinold & Kahn, *Active Portfolio Management* — the risk model is built and used separately from the alpha model; "risk is not alpha"; the optimiser trades alpha against a risk forecast | `RiskScore` as its own dimension, and the rule that it is not an alpha factor (§3.7.5) |
| 14 | Sizing practice: volatility targeting sizes *inversely* to volatility; fractional Kelly discounts full Kelly for estimation error; conviction is bounded by volatility, correlation and drawdown tolerance | the score ≠ scale separation (`RegimeScore` 68 vs `RegimeScale` 0.47x, §3.7.4) and `TradeScore` not being a size |
| 15 | Rockafellar & Uryasev — CVaR/expected shortfall is convex and optimisable as an LP; ES/CVaR is **coherent**, VaR is not (subadditivity) | the tail-risk component's measure choice, and why the loss-sign conventions must be pinned (§3.7.1) |
| 16 | Moreira & Muir, volatility-managed portfolios — scaling by inverse recent variance raised Sharpe in the original evidence (50-100% of the original), with later work finding no systematic improvement | the sizing multiplier's existence *and* its limits: it is a sizing rule, not a score input |
| 17 | Moskowitz, Ooi & Pedersen (time-series momentum, 1-12 months, across asset classes); George & Hwang (nearness to the 52-week high) | the trend and momentum components are the best-supported legs; `high_distance` already exists here |
| 18 | Technical-indicator evidence quality: ADX is non-directional and lagging with little standalone predictive power (best used as a filter); volume is a **confirmation** variable, not a standalone predictor | ADX belongs in Trend *strength*, not as a directional signal; the volume component (10%) is a confirmer |
| 19 | Jegadeesh (1990) — short-term reversal ≈2%/month at a one-month horizon; De Bondt & Thaler (long-horizon overreaction, a different mechanism) | the mean-reversion component is real but small — consistent with its 5% weight |
| 20 | Asness, Moskowitz & Pedersen, "Value and Momentum Everywhere" — value and momentum are negatively correlated (≈ −0.60); separate sleeves / 50-50 allocation historically beat merging the signals into one ranking | **the evidence for "do not mix them into one score too early"** (§3.7's opening) and for a dimension-level combination layer rather than factor-level blending |
| 21 | Composite-indicator practice — decomposed dimensions give root-cause attribution and avoid a **misleading cancellation**; a composite is defensible when its components belong together | four scores, printed with their components and their attribution (§3.7.6 rule 3) |
| 22 | Regime detection: Hurst exponent and variance ratio are complementary *shape* diagnostics (VR(k) ≈ k^(2H−1)), not robust regime detectors on their own; Markov-switching models infer the volatility state and its persistence (expected duration 1/(1−p)) | the choppiness/persistence component's role and its limits (§3.7.4) |
| 23 | Liquidity and gap risk: Amihud measures price impact per unit of volume, the bid-ask spread measures execution cost, and overnight gap risk is neither — size on the plausible gap, and cut overnight/event exposure to roughly 25-50% of normal; earnings implied move is read from the ATM straddle | the liquidity, gap and event components' distinct measures, and the event-risk sizing rule (§3.7.5) |
| 24 | Hard-constraint practice — risk, leverage, liquidity and mandate limits define the feasible set **before** optimisation; expected return never overrides a hard risk limit | `TradeScore` never overrides a hard gate (§3.7.6 rule 1), which the repo already implements (17 fail-closed checks, `GATE_PRECEDENCE`; `risk_multiplier.combine` zeroes the soft product on a hard flag) |
| 25 | Tetlock, "Giving Content to Investor Sentiment" — media pessimism predicts **next-day declines then a reversal within days**; extreme pessimism predicts **volume**; low returns produce more pessimistic tone (a feedback loop) | sentiment is short-horizon and partly reversing, not a permanent alpha weight; and the price→sentiment feedback is why the confirmation check exists (§3.8.2, §3.8.4) |
| 26 | Baker & Wurgler, investor sentiment — high sentiment predicts **lower** subsequent returns, concentrated in hard-to-value, hard-to-arbitrage names | the sentiment leg is contrarian in the cross-section and name-dependent; supports the small research weight |
| 27 | Barber & Odean (attention-based trading) and the limited-attention reading of PEAD — fresh, salient news is incorporated immediately while stale or competing information drifts | NewsScore's novelty/materiality emphasis is the right shape, and the one strong leg (earnings surprise + drift) is already implemented |
| 28 | Da, Engelberg & Gao and the StockTwits literature — **attention** spikes predict negative next-day returns while **bullish sentiment** predicts positive ones; small caps are more sensitive to both | attention and sentiment are different signals with opposite short-horizon signs and must not be merged (§3.8.2 consequence 2) |

