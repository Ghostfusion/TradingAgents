# ValuationScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`RiskScore.md`](RiskScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`MarketScore.md`](MarketScore.md).

**Scope: the valuation engine only.** It designs `ValuationScore` — *"is this
stock cheap or expensive?"* — from the owner's library in
[`../../Strategies/scores/valuation_score.md`](../../Strategies/scores/valuation_score.md)
(2,269 lines, 85 numbered sections + one unnumbered architecture block; refreshed
2026-09-26). The library's own framing, quoted
([`../../Strategies/scores/valuation_score.md:1-10`](../../Strategies/scores/valuation_score.md)):

> Yes. For a **quantitative Valuation Score**, I would treat valuation as a broad
> family of **intrinsic-value, relative-value, cash-flow, asset-value,
> growth-adjusted, and market-implied valuation calculations**, rather than simply
> P/E or P/B.
>
> $$\boxed{\text{Valuation Score}=f(\text{Intrinsic Value},\text{Relative Value},\text{Growth},\text{Cash Flow},\text{Enterprise Value},\text{Asset Value},\text{Market-Implied Expectations})}$$
>
> Below is a comprehensive formula inventory you can use when designing a
> `ValuationScore` engine.

That framing is the whole design brief: the library is **seven families**, not one
multiple, and its closing recommendation says explicitly *"I would **not** put all
of these formulas directly into one giant weighted average"* and *"while **not
mixing confidence into the score itself**"*
([`:2208-2269`](../../Strategies/scores/valuation_score.md)). This document
therefore designs an engine that reports a score **and** a separate confidence, and
that refuses the one-weight-vector composite the library sketches in §74/§85.

Status: **designed, not built (2026-09-26).** No producer, gate or config key
exists — proven by grep, not by assumption, in §0.1. Every formula in the library
is a hypothesis until a producer exists and a measurement is run (master rule 5,
rule 6). Nothing in this document is added to code or config; it is a design
record and an open question list.

---

## 0. What this engine answers, and what it must not become

### 0.1 Status proved by grep, not assumed

Run this round against the working tree:

```
$ grep -rn "valuation_score\|ValuationScore" --include=*.py tradingagents/ scripts/ tests/
(no output; exit status 1)
$ grep -rn "valuation_score" tradingagents/default_config.py .env.example
(no output; exit status 1)
```

**Zero Python hits, zero config hits.** There is no `strategies/valuation_score.py`,
no `get_valuation_score` leaf, no `enable_valuation_score` key, and no
`ValuationScore` entry in `tradingagents/default_config.py` or `.env.example`.
The name appears only in markdown — the owner's library
(`Strategies/scores/valuation_score.md`), the master's engine map
([`README.md`](README.md) §1.3, `[ADDED 2026-09-26]`) and its §2.1 note that this
engine and `MarketScore` are the two whose boundary is unsettled, the sibling
design docs, `Strategies/other_score.md:1154` (which names `ValuationScore` as
core engine #2 and puts the four trust scores in a separate meta tier) and
`CHANGELOG.md` — and in no Python or config file.

The engine map row is therefore honest and stays: **components with a real
producer: none; composite today: none.**

### 0.2 The boundary is the hard part, and it is not resolved here

The built `FundamentalScore` already contains a valuation sub-score. It is not a
proposal — it is running code:

| Fact | Evidence |
| --- | --- |
| `valuation_subscore` exists and is one of the engine's four published sub-scores | `tradingagents/strategies/fundamental_score.py::valuation_subscore:220`; registered in `SUBSCORE_FUNCS` (`fundamental_score.py:226`) and dispatched by `subscores:234` |
| It is the `VS` band table `cheap / below-market / fair / rich / expensive / priced-for-perfection` | `tradingagents/strategies/fundamental_score.py::VS_BANDS:75`; title `"valuation"` at `fundamental_score.py:94` |
| It carries **12 factors**, all direction-aligned `cheap = favourable` | `tradingagents/strategies/factor_schema.py:410-422` (`SUBSCORE_FACTORS["VS"]`) |
| Its proposed weight in the owner's master table is **20.00** (as-written 21.25) | [`FundamentalScore.md`](FundamentalScore.md) §2.4, "Valuation — proposed 20.00, as-written 21.25" |
| The four-sub-score composite ships **equal-weight (1/4 each)** because neither weight vector is measured | `tradingagents/strategies/fundamental_score.py::fundamental_score:252` docstring; `tradingagents/strategies/factor_schema.py::weights_for` returns `None` when no `base_weight` is published, and `_spec:128` sets `base_weight=None` on every record |

The 12 VS factors, read from `factor_schema.py` (name — direction — formula as the
schema states it):

| Factor | Dir. | Schema formula (`factor_schema.py`) |
| --- | :-: | --- |
| `ev_ebitda` | −1 | `ratios.compute_ratios['ev_ebitda'] = enterprise_value / EBITDA` (`:263`) |
| `ev_ebit` | −1 | `ratios.compute_ratios['ev_ebit'] = enterprise_value / operating_income` (`:270`) |
| `ev_sales` | −1 | `ratios.compute_ratios['ev_sales'] = enterprise_value / revenue` (`:277`) |
| `price_to_earnings` | −1 | `ratios.compute_ratios['price_to_earnings'] = market_cap / net_income` (`:284`) |
| `price_to_book` | −1 | `ratios.compute_ratios['price_to_book'] = market_cap / total_equity` (`:291`) |
| `price_to_sales` | −1 | `ratios.compute_ratios['price_to_sales'] = market_cap / revenue` (`:298`) |
| `price_to_cash_flow` | −1 | `ratios.compute_ratios['price_to_cash_flow'] = market_cap / operating_cashflow` (`:305`) |
| `price_to_free_cash_flow` | −1 | `ratios.compute_ratios['price_to_free_cash_flow'] = market_cap / free_cash_flow` (`:312`) |
| `earnings_yield` | **+1** | `quantitative_scores.earnings_yield(fin) -> panel key 'earnings_yield'` (`:319`) — **EBIT/EV**, a firm-value yield |
| `fcf_yield` | **+1** | `capex_quality_read['fcf_yield'] = free_cash_flow / market_cap` (`:326`) — `availability=NA` |
| `val_z` | −1 | `value_dip historical percentile of the name's own multiple (val_z)` (`:334`) — `availability=NA` |
| `dcf_upside` | **+1** | caller-supplied `price / fair value`, scaled by `fundamental_score.dcf_confidence` (`:342`) |

Two things follow, and both matter for this design:

1. **The direction convention is already settled by precedent, not by argument.**
   Nine of the twelve VS factors are inverse multiples (direction `−1`: a *lower*
   multiple scores *higher*); three are yields or upside (direction `+1`). That is
   exactly the master's rule — **0-100, 100 = favourable, so cheap = high** — and
   `ValuationScore` inherits it rather than inventing it.
2. **The engine already owns six of the seven families the library names** —
   relative earnings multiples, enterprise-value multiples, cash-flow multiples,
   asset value (only `price_to_book`), market-implied (`dcf_upside`), and a
   statistical-relative leg (`val_z`). What it does **not** own is intrinsic value
   as a first-class factor (the DCF is a single caller-supplied upside), the
   asset-value family beyond book value, capital efficiency, growth-adjusted
   multiples, and the scenario/uncertainty family.

### 0.3 The three candidate resolutions — recorded, not chosen

The library's §1-§85 and `FundamentalScore`'s VS overlap on the multiples. This
design **does not resolve it silently**; the three honest options are:

| # | Resolution | What it means | Cost |
| --: | --- | --- | --- |
| **A** | **`ValuationScore` absorbs VS.** The multiples move out of `fundamental_score.py`, `VS` is deleted from `SUBSCORE_FACTORS`, and `FundamentalScore` becomes a three-sub-score engine (FQS/FGS/FRS). | One producer per quantity (master rule 8, invariant 8). But it changes the meaning of an already-published 0-100 sub-score and re-writes the owner's 106-factor ledger ([`FundamentalScore.md`](FundamentalScore.md) §2.4), and it breaks every stored `VS` reading in `reports/*`. | High: a contract migration, not a new engine. |
| **B** | **`FundamentalScore` keeps VS; `ValuationScore` is a relative-value layer only.** `ValuationScore` owns the *statistical-relative* families (peer z, historical percentile, sector-neutral rank, regression residual, mean-reversion) and the *uncertainty* family (dispersion, confidence, implied expectations), and **reads** the VS multiples rather than recomputing them. | Preserves the built engine and the owner's ledger; keeps one producer per multiple. But "valuation" then means two things — the absolute/peer multiple level (Fundamental) and the position within the distribution (Valuation) — and the new engine's score would be meaningless without the other engine's panel. | Low: no code moves. Needs a naming rule. |
| **C** | **They are the same object under two names.** `ValuationScore` is a rename/extension of VS, published as its own engine and removed from the fundamental composite. | Simplest conceptually. But it is option A with the extra cost of two names for one quantity — the exact failure invariant 15 names (*"no derived quantity may have two independent authoritative producers"*). | High, and it violates a written invariant. |

**This design's recommendation is B**, for one reason: the engine map's whole point
is that a reader comparing `F 88 / T 61 / R 68 / K 54` must not get a fifth number
that is the second number recomputed. But **B is a recommendation, not a decision**
— the choice re-shapes the owner's 106-factor ledger and the meaning of a published
sub-score, so it is recorded as **OPEN Q1 in §7** and nothing here is implemented.

### 0.4 What this engine must not become

- **Not a second copy of the multiples.** `price_to_earnings`,
  `price_to_free_cash_flow`, `ev_ebitda`, `ev_ebit`, `ev_sales`, `price_to_book`,
  `price_to_sales`, `price_to_cash_flow`, `earnings_yield`, `fcf_yield` all have a
  producer today (see §2). A `ValuationScore` that recomputes any of them is the
  double-count the master's §2.1 forbids.
- **Not a rating.** It never feeds `decision_guardrail.SCORE_BANDS`
  (`tradingagents/strategies/decision_guardrail.py`); it carries its own band table
  (master rule 2).
- **Not a gate.** No composite overrides `GATE_PRECEDENCE`
  (`../TradingExecution/signald/contracts.py`). Cheap is not permission.
- **Not a confidence.** The library is emphatic
  ([`:2245-2262`](../../Strategies/scores/valuation_score.md)): *"a stock can have a
  very attractive calculated valuation but low confidence … That should be
  represented as valuation + uncertainty, rather than allowing the uncertainty to
  silently distort the valuation number."* The score and the confidence are two
  outputs.
- **Not an intrinsic-value oracle.** §5 pins the direction convention and the
  coverage floor so that a name with one usable multiple cannot score like a name
  with fifteen.

---

## 1. Component inventory

**How the formula counts were produced.** A script parsed the library by H1 and
counted `$$` display-math blocks per section (`text.count("$$") // 2`). The count
therefore includes blocks that name a quantity without an equation, and it
overstates three sections — §26's two blocks are bare labels (`OperatingMargin^*`,
`EBITDAMargin^*`), §28's nine blocks include seven bare multiple names (`P/E`,
`ForwardP/E`, `EV/EBITDA`, `EV/Sales`, `P/S`, `P/B`, `P/FCF`), and §61's ten
blocks include distributional placeholders (`g ~ Distribution`, `IV_1,…,IV_N`,
`P(IV>Price)`). Those three are flagged in the table's status column. Totals:
**86 H1 blocks (85 numbered + 1 unnumbered), 257 `$$` blocks.**

**Status vocabulary** (three values, because the engine is not built):

| Status | Meaning |
| --- | --- |
| **elsewhere** | The library quantity **is computed today** by a repo symbol, which is cited and which was read this round. The row names the exact formula it computes. |
| **PARTIAL** | An **adjacent** quantity is computed; the library's exact definition is not. The row says what differs. |
| **ABSENT** | No producer in `tradingagents/` or `scripts/`. |

Paths are repo-relative (`tradingagents/…`); `::symbol:line` is the definition site.

| § | Library section | :line | Formulas | Status | Producer today (verified) — or the exact gap |
| --: | --- | --: | --: | --- | --- |
| 1 | Market-Capitalization Valuation | :13 | 5 | PARTIAL | MC + EV exist: `tradingagents/strategies/ratios.py::compute_ratios:437` returns `ev` (`:194`) and `market_cap` (`:215`), and `tradingagents/dataflows/quantitative_scores.py::enterprise_value:241` computes `MC + TotalDebt − Cash`. **Net Debt** is printed only as `net_debt=cash − debt` (`tradingagents/agents/utils/analysis_tools.py:2879`), the **negative** of the library's `TotalDebt − Cash`. Equity Value and Fully Diluted MC: ABSENT |
| 2 | Earnings Multiples | :55 | 12 | PARTIAL | P/E `ratios.py::compute_ratios:437` (`price_to_earnings`); Forward P/E, Earnings Yield, FCF yield of an ETF basket `tradingagents/strategies/etf_valuation.py::etf_valuation:80`; forward PEG `tradingagents/agents/utils/value_dip_tools.py::_forward_peg_read:659`. **CAPE, PEGY, Growth-Adjusted P/E, Forward EY: ABSENT.** The library's `EY = EPS/Price` (equity) is *not* what the repo's `earnings_yield` computes — see §4.5 |
| 3 | EV/Earnings Valuation | :133 | 6 | PARTIAL | EV/EBITDA `ratios.py:195`; EV/EBIT `ratios.py:196` and `quantitative_scores.py::acquirers_multiple:260`; `EV/OCF`, Forward EV/EBITDA, EV/EBITDAR: ABSENT. **The section is internally duplicated** (Appendix A.1) |
| 4 | Revenue Multiples | :178 | 5 | PARTIAL | P/S `ratios.py:200`; EV/Sales `ratios.py:197`. Forward P/S, EV/Forward Sales, Price/Revenue Growth: ABSENT |
| 5 | Book-Value Valuation | :214 | 5 | PARTIAL | P/B `ratios.py:199` (`mc / total_equity`). Tangible BV, Tangible P/B, Price/Tangible Book, Book-Value Yield: ABSENT |
| 6 | Enterprise Value to Assets | :249 | 4 | ABSENT | No `ev/assets`, `market_cap/assets` or `EV/InvestedCapital` anywhere. The IC *series* exists as an internal: `tradingagents/agents/utils/value_dip_tools.py:498-512` builds `invested_capital = debt + equity − cash` per year |
| 7 | Cash-Flow Valuation | :277 | 8 | PARTIAL | P/CF `ratios.py:201`; P/FCF `ratios.py:202`; FCF yield `tradingagents/strategies/value_dip.py::fcf_yield:155` + `tradingagents/strategies/capex_quality.py::capex_quality_read:126` (`fcf_yield` key at `:247`); Cash Conversion `tradingagents/strategies/earnings_quality.py::earnings_quality_verdict:24` (`cc = o / ni` at `:64`; the key is returned at `:103`). Enterprise FCF Yield, OCF Yield, FCF Conversion, FCF Margin: ABSENT |
| 8 | Free Cash Flow Calculations | :333 | 6 | PARTIAL | Basic FCF `= OCF − CapEx` exists twice: `tradingagents/strategies/ratios.py:169` and `tradingagents/strategies/normalized_fcf.py::maintenance_fcf:81` (`reported_fcf`); the same function's `maintenance_fcf` is `OCF − D&A`. Unlevered FCF, Levered FCF, FCF/share, FCF Growth, FCF CAGR: ABSENT |
| 9 | DCF Valuation | :377 | 2 | **elsewhere** | `tradingagents/strategies/dcf.py::compute_dcf:71` (project → discount → Gordon TV → EV→equity→price); leaf `tradingagents/agents/utils/analysis_tools.py::get_dcf_valuation:2932` |
| 10 | Gordon Growth Terminal Value | :400 | 3 | **elsewhere** | `tradingagents/strategies/dcf.py::terminal_value_gordon:56` = `latest_fcf*(1+g)/(wacc−g)` |
| 11 | Exit-Multiple Terminal Value | :423 | 3 | ABSENT | No `metric × exit multiple` TV anywhere |
| 12 | WACC | :444 | 5 | PARTIAL | Cost of equity (CAPM) **is** the repo's WACC: `tradingagents/strategies/dcf.py::wacc_from_beta:28` = `rf + beta·erp`. The debt leg and the after-tax cost of debt do not exist; `erp` is a caller constant (`dcf.py:28`, default 0.05; the omission is documented at `:31`). ERP, after-tax Kd, the general `w_e·K_e + w_d·K_d(1−T) + w_p·K_p`: ABSENT |
| 13 | Multi-Stage DCF | :481 | 1 | PARTIAL | A multi-year explicit projection with a fading capex ratio exists (`tradingagents/agents/utils/analysis_tools.py::get_normalized_fcf_dcf:3085`, backed by `tradingagents/strategies/normalized_fcf.py`), but growth is constant, not phased high-growth → transition → terminal |
| 14 | Dividend Discount Models | :503 | 5 | PARTIAL | Dividend Yield `ratios.py:209` (`dividends_paid / market_cap`, capped at 25%). Gordon equity value, multi-stage DDM, payout ratio: ABSENT |
| 15 | Residual Income Valuation | :543 | 3 | ABSENT | Zero producers |
| 16 | Economic Value Added | :571 | 3 | ABSENT | NOPAT exists only as a `capex_quality` input (`tradingagents/strategies/capex_quality.py:130,149`); no EVA, EVA margin or EVA yield |
| 17 | Economic Profit | :596 | 2 | ABSENT | Same formula as §16 under a second name; neither is built |
| 18 | ROIC-Based Valuation | :614 | 4 | PARTIAL | Incremental ROIC `ΔNOPAT/ΔIC` and its spread vs WACC: `tradingagents/strategies/capex_quality.py:184-188` (`incr_roic`, `spread`). A level ROIC proxy `NOPAT/total assets` at `tradingagents/agents/utils/value_dip_tools.py:1476` (denominator is total assets, **not** invested capital). Level ROIC on IC, Excess Return, Value Creation Spread as published factors: ABSENT |
| 19 | Growth-Based Valuation | :647 | 5 | ABSENT | No sustainable growth rate, reinvestment rate, ROIC-growth relationship or growth-quality factor |
| 20 | PEG / Growth-Adjusted Valuation | :685 | 4 | PARTIAL | PEG only, forward basis: `tradingagents/agents/utils/value_dip_tools.py::_forward_peg_read:659` (gated `enable_analyst_estimates`). EV/EBITDA-to-growth, EV/Sales-to-growth, P/FCF-to-growth: ABSENT |
| 21 | Rule of 40 / Growth-Profitability Valuation | :716 | 2 | ABSENT | Zero hits for `rule_of_40`/`rule40` |
| 22 | Implied Growth From P/E | :736 | 3 | PARTIAL | Implied growth exists, but from an FCF perpetuity, not from P/E: `tradingagents/strategies/reverse_dcf.py::implied_growth_for_fcf:202`; leaf `analysis_tools.py::get_reverse_dcf:3019` |
| 23 | Implied WACC | :761 | 3 | ABSENT | No producer inverts for the discount rate |
| 24 | Implied Terminal Growth | :784 | 3 | **elsewhere** | `tradingagents/strategies/reverse_dcf.py::implied_growth_for_fcf:202` bisects `g ∈ (0, wacc)` so the perpetuity value equals the price; surfaced as `crossing_g` (`analysis_tools.py:2941`) |
| 25 | Implied Revenue Growth | :810 | 1 | ABSENT | — |
| 26 | Implied Margin | :826 | 2 | ABSENT | Also: the two "formulas" are labels, not equations (counting caveat above) |
| 27 | Reverse DCF | :844 | 3 | **elsewhere** | `tradingagents/strategies/reverse_dcf.py::reverse_dcf:90`; leaf `analysis_tools.py::get_reverse_dcf:3019` |
| 28 | Relative Valuation | :876 | 9 | PARTIAL | Peer ranking exists (`tradingagents/strategies/factors.py::percentile_rank:59`, `composite_score:115`; universe `tradingagents/strategies/peer_universe.py::resolve_peer_universe:233`), but **no peer-median premium/discount ratio**. 7 of the 9 blocks are bare multiple names (counting caveat) |
| 29 | Relative Valuation Z-Score | :926 | 2 | **elsewhere** | `tradingagents/strategies/cross_section.py::cross_sectional_z:70` and `industry_neutral_z:89` (winsorise → demean by sector → z); historical route `tradingagents/strategies/value_dip.py::valuation_z_read:122` |
| 30 | Historical Valuation Percentile | :951 | 2 | **elsewhere** | `tradingagents/strategies/normalized.py::percentile_hist:53` / `percentile_hist_or_none:37`; `tradingagents/strategies/value_dip.py::valuation_z_read:122`; ETF basket percentile `tradingagents/strategies/etf_valuation.py::etf_valuation:80` |
| 31 | Historical Premium/Discount | :977 | 2 | ABSENT | `valuation_z_read` returns a z, not `current/median − 1` |
| 32 | Sector-Adjusted Valuation | :993 | 2 | PARTIAL | Sector neutralisation exists as a z (`cross_section.py::industry_neutral_z:111`, `group_median:344`); the company/peer-median **ratio** does not |
| 33 | Quality-Adjusted Valuation | :1010 | 3 | ABSENT | — |
| 34 | PEG-ROIC | :1038 | 1 | ABSENT | — |
| 35 | Earnings Yield vs Bond Yield | :1050 | 3 | ABSENT | No EY − Rf, no FCF-yield − Rf spread |
| 36 | Equity Risk Premium From Market Valuation | :1076 | 1 | ABSENT | `erp` is a constant parameter (`dcf.py:28`), never derived from market valuation |
| 37 | Buffett-Style Owner Earnings | :1088 | 3 | PARTIAL | `normalized_fcf.py::maintenance_fcf:81` = `OCF − D&A` is owner earnings **without** the ΔNWC leg; no owner-earnings yield or multiple |
| 38 | Graham Valuation | :1116 | 2 | PARTIAL | A **different** Graham formula is built: `tradingagents/strategies/fundamental_floors.py::graham_number:21` = `√(22.5·EPS·BVPS)`, not the library's `EPS×(8.5+2g)`; plus `graham_cheap:39` |
| 39 | Asset-Based Valuation | :1137 | 4 | ABSENT | No NAV, NAV/share, P/NAV or NAV discount (zero hits for `nav`) |
| 40 | Sum-of-the-Parts Valuation | :1174 | 3 | ABSENT | Zero hits for `sotp` / sum-of-the-parts |
| 41 | Liquidation Value | :1199 | 2 | ABSENT | No liquidation value; `liquidation` hits in `tradingagents/strategies/liquidity_risk.py` are share-liquidation, not asset liquidation |
| 42 | Replacement-Cost Valuation | :1216 | 1 | PARTIAL | `tradingagents/dataflows/quantitative_scores.py::tobins_q:269` = `(MC + TotalLiabilities)/TotalAssets` is the market/book proxy for replacement cost, explicitly labelled as book-based |
| 43 | Net-Net Valuation | :1232 | 3 | **elsewhere** | `tradingagents/strategies/fundamental_floors.py::ncav_per_share:46` = `(CurrentAssets − TotalLiabilities)/shares`; `ncav_cheap:68` |
| 44 | Dividend Yield Relative Valuation | :1256 | 3 | ABSENT | No current/historical-median dividend-yield ratio |
| 45 | Dividend Discount Implied Value | :1279 | 2 | ABSENT | — |
| 46 | Buyback-Adjusted Shareholder Yield | :1295 | 3 | ABSENT | No buyback yield or shareholder yield. `tradingagents/agents/utils/market_position_tools.py::get_share_buyback_authorization:49` returns the *authorization*, not net repurchases |
| 47 | Total Yield | :1320 | 2 | ABSENT | — |
| 48 | Enterprise Yield | :1336 | 2 | **elsewhere** | `tradingagents/dataflows/quantitative_scores.py::earnings_yield:251` = `EBIT/EV`; leaf key `EY` (`analysis_tools.py:1464`) |
| 49 | EBITDA Yield | :1351 | 1 | ABSENT | EBITDA itself is built (`ratios.py:162`, `ebitda = op + dep`) but never divided by EV |
| 50 | EBIT Yield | :1360 | 1 | **elsewhere** | Same symbol as §48: `quantitative_scores.py::earnings_yield:251` |
| 51 | Earnings Yield Quality | :1369 | 2 | ABSENT | No `FCF/NI` quality ratio and no `EY × FCFConversion` |
| 52 | Cash-Adjusted Valuation | :1387 | 2 | ABSENT | No `(MC − Cash)/NI` |
| 53 | Debt-Adjusted Valuation | :1406 | 3 | ABSENT | `ratios.py:205` `debt_to_equity` is a leverage ratio, not a valuation adjustment; no Debt/EV, Net Debt/EBITDA or Net Debt/FCF |
| 54 | Dilution-Adjusted Valuation | :1433 | 3 | ABSENT | Zero hits for share-count dilution |
| 55 | Share-Based Compensation Adjustment | :1461 | 3 | ABSENT | Zero hits for SBC |
| 56 | Margin-of-Safety Calculations | :1486 | 4 | **elsewhere** | `tradingagents/strategies/normalized.py::margin_of_safety:120` = `(IV − P)/IV`; `margin_of_safety_bases:127` also gives the price basis; leaf `analysis_tools.py::get_margin_of_safety:5010`; scenario mos `tradingagents/strategies/scenario_dcf.py::scenario_dcf:22` |
| 57 | Weighted Intrinsic Value | :1518 | 3 | ABSENT | No multi-model IV weighting |
| 58 | Valuation Dispersion | :1543 | 5 | ABSENT | No `σ(IV)/median(IV)`; no multi-model IV panel to take a σ over |
| 59 | Intrinsic Value Confidence | :1576 | 1 | PARTIAL | `tradingagents/strategies/fundamental_score.py::dcf_confidence:430` scores a DCF from four **legs** (basis conflict, beta assumption, FCF CV, terminal share) — not from the library's `1 − σ(IV)/median(IV)` |
| 60 | Scenario Valuation | :1592 | 3 | **elsewhere** | `tradingagents/strategies/scenario_dcf.py::scenario_dcf:22` (bear/base/bull growth + margin shocks, price band, per-scenario mos); leaf `analysis_tools.py::get_scenario_dcf:3703`. **Probabilities are absent** — the library's `P_B, P_Base, P_Bull` weights have no producer |
| 61 | Monte Carlo Valuation | :1622 | 10 | ABSENT | Zero valuation-simulation producers (`monte_carlo` hits are `tradingagents/strategies/book_risk.py` drawdown envelopes and `conformal.py` bootstrap, both unrelated). 10 blocks include placeholders (counting caveat) |
| 62 | Valuation VaR | :1676 | 3 | ABSENT | Depends on §61 |
| 63 | Probability of Overvaluation | :1700 | 2 | ABSENT | Depends on §61 |
| 64 | Expected Valuation Gap | :1716 | 1 | PARTIAL | `tradingagents/strategies/normalized.py::margin_of_safety_bases:127` `price_basis` is `(IV − P)/P` — the library's gap shape — but the **probability-weighted Expected IV** does not exist (§60 has no probabilities) |
| 65 | Bear-Case Downside | :1725 | 2 | **elsewhere** | `tradingagents/strategies/scenario_dcf.py::scenario_dcf:22` returns per-scenario prices and `mos`; the band label (below bear / bear-base / base-bull / above bull) at `scenario_dcf.py:99-105` |
| 66 | Valuation Asymmetry | :1741 | 1 | ABSENT | No `(Bull − P)/(P − Bear)` |
| 67 | Market-Implied Multiple | :1753 | 4 | **elsewhere** | The implied multiple *is* the ratio: `tradingagents/strategies/ratios.py::compute_ratios:194-202` (`price_to_earnings:198`, `ev_ebitda:195`, …). Forward-metric variants: ABSENT |
| 68 | Historical Multiple Mean Reversion | :1782 | 3 | ABSENT | No partial-adjustment `α` model |
| 69 | Relative Valuation Regression | :1805 | 3 | ABSENT | `tradingagents/strategies/factors.py::fama_french_5_factor:518` and `_ols5:448` regress **returns**, not multiples |
| 70 | Cross-Sectional Residual Valuation | :1837 | 2 | ABSENT | No multiple-on-fundamentals regression |
| 71 | Factor-Adjusted Valuation | :1868 | 2 | ABSENT | Depends on §70 |
| 72 | Sector-Neutral Valuation Score | :1888 | 1 | PARTIAL | `tradingagents/strategies/cross_section.py::industry_neutral_z:111` gives the sector z; the within-sector **rank** does not exist |
| 73 | Market-Neutral Valuation Score | :1904 | 1 | PARTIAL | `tradingagents/strategies/cross_section.py::centered_rank:162` and `tradingagents/strategies/factors.py::percentile_rank:59` give percentile ranks; the `100×(1 − Percentile)` inverse-multiple score is not built |
| 74 | Composite Valuation Factor | :1918 | 2 | ABSENT | The composite itself — by decision, not by omission (§5) |
| 75 | Normalized Valuation Components | :1941 | 5 | PARTIAL | Z and percentile exist (`cross_section.py::cross_sectional_z:70`, `centered_rank:140`; `value_dip.py::zscore:104`); winsorisation exists (`cross_section.py::winsorize:31`); **Min-Max and the robust z (`1.4826·MAD`) do not** |
| 76 | Winsorized Valuation Factors | :1987 | 1 | **elsewhere** | `tradingagents/strategies/cross_section.py::winsorize:31` (default `0.01/0.99` = the library's P1/P99) |
| 77 | Missing-Data / Coverage Score | :2004 | 4 | PARTIAL | The repo's policy exists and is **not** the library's: `tradingagents/strategies/factors.py::_coverage_floor:246` + the `withheld` path in `category_scores:258` (a name below the floor is withheld with a reason). The library's `RawScore × Coverage` multiplication is deliberately **not** used — it shrinks the score toward 0, which master rule 1 (`NA ≠ 0`) forbids |
| 78 | Valuation Stability | :2037 | 2 | ABSENT | Needs a valuation-score time series (none) and an undefined `MaximumPossibleVolatility` |
| 79 | Valuation Trend | :2054 | 2 | ABSENT | Same dependency |
| 80 | Fundamental-Adjusted Valuation | :2077 | 2 | ABSENT | Deliberately not built: the library itself says *"I would generally keep these as **separate engines**"*; its `ValuationScore × QualityScore` would also produce a 0-10,000 product |
| 81 | Valuation vs Growth Matrix | :2098 | 2 | ABSENT | No growth-vs-valuation premium spread |
| 82 | Valuation vs Quality Spread | :2119 | 1 | ABSENT | — |
| 83 | Valuation Regime | :2130 | 1 | PARTIAL | The percentile exists (`normalized.py::percentile_hist:53`) and `value_dip.py::valuation_z_read:122` returns a `cheap/fair/rich` verdict; the three-way percentile regime label does not |
| 84 | Valuation Mean-Reversion Potential | :2149 | 2 | ABSENT | — |
| 85 | Valuation Composite With Multiple Independent Models | :2166 | 3 | ABSENT | The composite — by decision (§5) |
| — | Recommended ValuationScore Architecture for Your System (unnumbered) | :2208 | 1 | ABSENT | Design only: 10 sub-engines + a 14-key output contract. This document adopts the *separation* it recommends and rejects its `f(...)` composite sketch |

**Tally: 14 `elsewhere`, 25 `PARTIAL`, 47 `ABSENT` (of 86).**

---

## 2. What already exists elsewhere

The complete list, split by **who calls it**. Paths are repo-relative; every symbol
below was read this round.

### 2.1 Engine components (pure functions other code calls)

| Symbol | Library formulas it computes | Read as |
| --- | --- | --- |
| `tradingagents/dataflows/quantitative_scores.py::enterprise_value:241` | §1 `EV = MC + TotalDebt − Cash` (no preferred, no minority interest) | `mc + debt − cash`, `None` on any missing input |
| `tradingagents/dataflows/quantitative_scores.py::earnings_yield:251` | **§48 Enterprise Yield / §50 EBIT Yield** (`EBIT/EV`) — *not* §2 Earnings Yield | `_ratio(ebit, ev)` |
| `tradingagents/dataflows/quantitative_scores.py::acquirers_multiple:260` | §3 EV/EBIT | `_ratio(ev, ebit)` |
| `tradingagents/dataflows/quantitative_scores.py::tobins_q:269` | §42 replacement cost, as a book-value proxy | `(MC + TotalLiabilities)/TotalAssets` |
| `tradingagents/strategies/ratios.py::compute_ratios:437` | §2 P/E, §3 EV/EBIT + EV/EBITDA, §4 P/S + EV/Sales, §5 P/B, §7 P/CF + P/FCF, §8 Basic FCF, §14 Dividend Yield | returns `ev:194`, `ev_ebitda:195`, `ev_ebit:196`, `ev_sales:197`, `price_to_earnings:198`, `price_to_book:199`, `price_to_sales:200`, `price_to_cash_flow:201`, `price_to_free_cash_flow:202`, `dividend_yield:209`, `free_cash_flow:214`; `fcf = ocf − |capex|` at `:169`, `ebitda = op + dep` at `:162` |
| `tradingagents/strategies/dcf.py::compute_dcf:71` | §9 DCF, §10 Gordon TV, §12 CAPM cost of equity, §13 projection | projects the **latest reported** FCF at constant `g`, discounts at `wacc`, Gordon TV anchored to the last projected year, EV→equity→price |
| `tradingagents/strategies/dcf.py::terminal_value_gordon:56` | §10 `TV = FCF_n(1+g)/(WACC−g)` | returns `inf` when `wacc ≤ g` |
| `tradingagents/strategies/dcf.py::wacc_from_beta:28` | §12 **cost of equity only** (`rf + beta·erp`) | consumed and printed as "WACC" |
| `tradingagents/strategies/cycle_dcf.py::normalized_cycle_fcf:23` | §58-adjacent: a robust mid-cycle FCF anchor (median of annual FCFs, ≥3 years) | `{median, min, max, mean, n}` |
| `tradingagents/strategies/cycle_dcf.py::perpetuity_value:43` | §10 Gordon/perp value of a normalized FCF | returns `None` when `wacc ≤ g` — **a different sentinel from `terminal_value_gordon`** |
| `tradingagents/strategies/scenario_dcf.py::scenario_dcf:22` | §60 Scenario Valuation, §65 Bear/Bull prices + mos | bear/base/bull prices, a price band, per-scenario `mos` |
| `tradingagents/strategies/reverse_dcf.py::reverse_dcf:90` | §27 Reverse DCF | implied steady-state FCF per growth rate |
| `tradingagents/strategies/reverse_dcf.py::implied_growth_for_fcf:202` | §24 Implied Terminal Growth, §22-adjacent | bisects the perpetual `g` at which the DCF equals price |
| `tradingagents/strategies/normalized.py::margin_of_safety:120` | §56 `MOS = (IV − P)/IV` | — |
| `tradingagents/strategies/normalized.py::margin_of_safety_bases:127` | §56 both denominators, §64's gap shape | `fv_basis`, `price_basis`, `price_to_intrinsic` |
| `tradingagents/strategies/normalized.py::percentile_hist:53` / `percentile_hist_or_none:37` | §30 Historical Valuation Percentile | percentile of the latest value in its own history |
| `tradingagents/strategies/normalized.py::median_norm_ebit:14` | §18-adjacent: normalized EBIT = 5y median margin × current sales | — |
| `tradingagents/strategies/value_dip.py::fcf_yield:155` | §7 FCF Yield | `fcf / market_cap`, `None` on non-positive MC |
| `tradingagents/strategies/value_dip.py::zscore:104` | §29 Z-score | `(value − mean)/std`, sign-preserving |
| `tradingagents/strategies/value_dip.py::valuation_z_read:122` | §29/§30/§83 | `{z, mean, std, n, verdict}` with `cheap ≤ −1.5`, `rich ≥ +1.5` |
| `tradingagents/strategies/fundamental_floors.py::graham_number:21` | §38 **a different Graham formula** (`√(22.5·EPS·BVPS)`) | — |
| `tradingagents/strategies/fundamental_floors.py::graham_cheap:39` | §38 comparison | `price ≤ graham_number` |
| `tradingagents/strategies/fundamental_floors.py::ncav_per_share:46` / `ncav_cheap:68` | §43 Net-Net | `(CA − TL)/shares` |
| `tradingagents/strategies/fundamental_floors.py::earnings_power_value:75` | §37-adjacent (Greenwald EPV) | `adj EBIT·(1−t)/(WACC−g)` + an excess-ROIC check |
| `tradingagents/strategies/normalized_fcf.py::maintenance_fcf:81` | §8 Basic FCF (`reported_fcf`) + a maintenance-capex floor | `{maintenance_fcf, reported_fcf, growth_capex, basis}` |
| `tradingagents/strategies/earnings_quality.py::earnings_quality_verdict:24` | §7 Cash Conversion | `cc = OCF/NI` with bands, plus the Sloan accrual `(NI−OCF)/TA` |
| `tradingagents/strategies/capex_quality.py::capex_quality_read:126` | §7 FCF Yield, §18 incremental ROIC + spread | `fcf_yield` at `:247`; `incr_roic` at `:184-187`, `spread` at `:188` |
| `tradingagents/strategies/etf_valuation.py::etf_valuation:80` | §2 P/E (harmonic), forward P/E, earnings yield; §7 FCF yield; §30 valuation percentile vs own history | ETF basket aggregate |
| `tradingagents/strategies/cross_section.py::winsorize:31` | §76 Winsorized Valuation Factors | default `0.01/0.99` |
| `tradingagents/strategies/cross_section.py::cross_sectional_z:70` / `industry_neutral_z:89` | §29, §32, §72 | winsorise → demean (by sector) → z |
| `tradingagents/strategies/cross_section.py::centered_rank:162` / `quantile_split:169` / `group_median:344` | §30, §73, §32 | rank / split / sector median |
| `tradingagents/strategies/factors.py::percentile_rank:59` | §30, §73 | tie-aware percentile |
| `tradingagents/strategies/factors.py::_coverage_floor:246` + `category_scores:258` | §77 | the honest-missing-data policy (`withheld` with a reason) |
| `tradingagents/strategies/fundamental_score.py::dcf_confidence:430` | §59-adjacent | confidence from four measured legs, product-capped |
| `tradingagents/strategies/fundamental_score.py::valuation_subscore:220` | §2/§3/§4/§5/§7 multiples, as a 0-100 sub-score | the boundary object of §0.2 |

### 2.2 Tool leaves (what the model can actually call)

| Leaf | Bound in | What it returns | Library section |
| --- | --- | --- | --- |
| `analysis_tools.py::get_dcf_valuation:2932` | `tradingagents/agents/toolsets.py::fundamentals_company_tools:458` | fair value + WACC + TV share + bridge | §9 |
| `analysis_tools.py::get_reverse_dcf:3019` | `toolsets.py:459` | implied steady-state FCF per `g`, `crossing_g` | §27, §24 |
| `analysis_tools.py::get_normalized_fcf_dcf:3085` | `toolsets.py:460` | capex-fade DCF + maintenance-capex floor | §13, §8 |
| `analysis_tools.py::get_normalized_cycle_dcf:4931` | `toolsets.py:461` | mid-cycle median-FCF perpetuity + FV-basis mos | §58-adjacent |
| `analysis_tools.py::get_scenario_dcf:3703` | `toolsets.py:462`, `toolsets.py::market_tools:330` | bear/base/bull + band + mos | §60, §65 |
| `analysis_tools.py::get_margin_of_safety:5010` | `toolsets.py:465` | `(IV − P)/IV` against a caller-supplied intrinsic | §56 |
| `value_dip_tools.py::get_fcf_yield:380` | `toolsets.py:468` | TTM FCF (OCF − \|CapEx\|, newest 4 quarters) / market cap | §7 |
| `value_dip_tools.py::get_valuation_z_score:581` | `toolsets.py:470` | z of `pe` / `ev_ebitda` / `p_fcf` vs its own history | §29, §30 |
| `quant_formula_tools.py::get_valuation_band:279` | `toolsets.py:472` | a **conformal** band around a model fair value (gated `enable_conformal_bands`) | §58-adjacent |
| `analysis_tools.py::get_etf_valuation:1791` | `toolsets.py::fundamentals_etf_tools:505` | ETF basket multiples + valuation percentile | §2, §7, §30 |
| `value_dip_tools.py::get_tranche_plan:178` | `toolsets.py:303` | tranche caps for a value-dip entry | — (not a valuation) |

**Which are engine components vs tool leaves.** Everything in §2.1 is an engine
component: a pure function with a caller (a leaf, a screen row, a score, or another
strategy). Everything in §2.2 is a **tool leaf** — a `@tool`-decorated renderer the
LLM may choose, gated by the analyst toolset it is bound into. Two facts matter for
this design:

1. **The leaves are the model's, not the engine's.** A `ValuationScore` composite
   must be fed by the §2.1 functions, never by parsing a leaf's text (master rule 7:
   no `factor_score=NN` in prose).
2. **`_forward_peg_read:659` is a private helper, not a leaf.** The only PEG
   producer in the repo is not callable by the model; it is read by
   `tradingagents/agents/utils/value_dip_tools.py::get_value_dip_setup:712`
   (the call is at `:833`). §3 ranks a public PEG leaf as cheap work.

---

## 3. The smallest honest producer

Ranked by **value ÷ effort**. "Inputs" are the vendor fields each needs; "supply"
is the call that already fetches them. Nothing here is implemented.

| Rank | Piece | Library § | Inputs needed | Already fetched by | Effort | Why this rank |
| --: | --- | --- | --- | --- | --- | --- |
| 1 | **Valuation dispersion + confidence** | §58, §59 | ≥2 intrinsic values for one name: `compute_dcf` price, `perpetuity_value(normalized_cycle_fcf)` price, `scenario_dcf` base price | all three functions are pure and already called by leaves (`get_dcf_valuation:2804`, `get_normalized_cycle_dcf:4799`, `get_scenario_dcf:3571`) — no new fetch | **S** — one pure function `dispersion(ivs) -> {mean, median, std, dispersion, confidence}` | It is the library's stated core requirement (*"valuation + uncertainty"*, `:2255-2262`), it needs **zero** new data, and it is the one thing no producer computes today |
| 2 | **EBITDA yield / Net Debt-to-EBITDA** | §49, §53 | EBITDA, EV, net debt | `ratios.py:162` builds `ebitda = op + dep`; `ev` at `:194`; `cash`/`debt` are already in the DCF context (`analysis_tools.py::_dcf_context:2838`) | **S** — two divisions | Cheapest real gap; `net_debt` is currently only printed with an inverted sign (`analysis_tools.py:2879`) |
| 3 | **Coverage + floor, printed** | §77 | the VS factor panel + which factors are `NA` | `factor_schema.availability_report` and `factors._coverage_floor:246` exist | **S** — reuse, not build | The repo already has the honest policy; the engine only needs to *print* it beside the score |
| 4 | **Peer-relative valuation z + sector-neutral rank** | §29, §32, §72, §73 | the peer panel of multiples the VS sub-score already assembles | `strategies/peer_universe.py::resolve_peer_universe`, `factors.category_scores:258`, `cross_section.industry_neutral_z:111`, `group_median:344` | **S–M** — wire an existing panel into an existing normaliser | The hardest input (a peer set) is already built for `FundamentalScore`; this turns "how cheap" into "how cheap *for this sector*" |
| 5 | **Historical premium / mean-reversion gap** | §31, §68, §84 | the name's own multiple history | `value_dip.py::valuation_z_read:122` already builds the series from the vendor's per-period tables; leaf `get_valuation_z_score:581` | **M** — same series, a ratio instead of a z, plus a partial-adjustment `α` | High value (mean reversion is the library's §68/§84 theme) and the series is already assembled |
| 6 | **Implied expectations beyond growth** | §23, §25, §26 | WACC / revenue growth / margin that make the DCF equal price | `reverse_dcf.py` bisects on `g` only (`implied_growth_for_fcf:202`) | **M** — three more bisections on the same machinery | Turns the library's "market-implied expectations" family from ABSENT to built with one shared solver |
| 7 | **EV/Assets, EV/Invested Capital** | §6 | total assets, invested capital | `value_dip_tools.py:498-512` already stacks `invested_capital` per year | **M** — expose an existing internal | The series exists but is consumed only as a ΔIC denominator |
| 8 | **CAPE / Shiller P/E** | §2 | 10 years of real EPS + real price | **not fetched today**: `dataflows/sec_edgar.py` gives up to 15 years for US filers (tool at `tradingagents/agents/utils/analysis_tools.py::get_financial_history:11900`), but no CAGR/series path consumes it | **L** — a new series producer + CPI deflation | High value (the one macro-scale valuation measure with a long literature) but it is the only item here that needs a **new data path** |
| 9 | **Owner earnings / shareholder yield / buyback yield** | §37, §46, §47 | ΔNWC; net share repurchases | `maintenance_fcf:81` gives OCF − D&A; the `share_buybacks` key has **no reader** (`FundamentalScore.md` §1.4 #3) | **M–L** — one new statement key with a reader | Needs a canonical-vocabulary addition before it can be computed |
| 10 | **SOTP, liquidation value, NAV, replacement cost** | §39–§42 | segment-level fair values, appraisals | nothing | **L** — data does not exist in the vendor chain | Honest ABSENT; the smallest honest producer is *no producer* until a segment data source exists |
| 11 | **Monte Carlo valuation, valuation VaR, P(IV > price)** | §61–§63 | distributions for `g`, margin, WACC | nothing | **L** — a simulation layer over the existing DCF | The library calls it *"extremely powerful"*; it is also the only item that needs a new statistical layer. Build last, after §58's dispersion proves the IV inputs are sane |

**The recommended first step is rank 1** — one pure function, no new fetch, and it
satisfies the library's own central requirement. It also produces the number §5's
coverage rule needs.

---

## 4. What the evidence says

Every row was **fetched this round**; the URL is the resource actually read (a PDF
page, an HTML page, or an OpenAlex works record carrying the bibliographic fields
and the abstract). Where the library's formula differs from the standard
definition, the difference is stated.

| Claim used here | Source (fetched) | URL | Where the library differs |
| --- | --- | --- | --- |
| **Forward-earnings multiples are the best price explainers; cash flow and book value tie for third; sales is worst; short-cut residual income is *worse* than simple multiples.** Pricing errors within 15% of price for ~half the sample. | Liu, Nissim & Thomas (2002), *Equity Valuation Using Multiples*, Journal of Accounting Research 40(1):135-172 | `https://api.openalex.org/works/doi:10.1111/1475-679X.00042` (DOI `10.1111/1475-679X.00042`) | The library gives **equal weight** to every family (§74's `w_1…w_7`, §85's `w_...`) and puts intrinsic value first (`IV = 0.40·DCF + …`, §57). The paper's ranking implies the opposite ordering: forward earnings ≫ intrinsic-value shortcuts. §74/§85 are therefore unsupported by this evidence, and §5 must not adopt them |
| **Size and book-to-market capture the cross-section; the relation between market β and average return is flat.** | Fama & French (1992), *The Cross-Section of Expected Stock Returns*, Journal of Finance 47(2):427-465 | `https://api.openalex.org/works/doi:10.1111/j.1540-6261.1992.tb04398.x` | The library has **no** size leg and gives P/B one of five slots in §5 (1/5 of the book-value family). Book-to-market is the strongest single documented value measure; the library's asset-value family is built on NAV/NCAV/replacement cost (§39-§43) instead |
| **The size premium is weak until quality (its inverse, junk) is controlled for; then it is stable across time, specification, 30 industries and 24 markets.** | Asness, Frazzini, Israel, Moskowitz & Pedersen (2018), *Size matters, if you control your junk*, Journal of Financial Economics 129(3):479-509 | `https://api.openalex.org/works/doi:10.1016/j.jfineco.2018.05.006` | Directly supports the library's own §33 *"cheap companies can be cheap for good reasons"* and §80's warning to keep quality and valuation separate — but §33's `QualityAdjustedPE = PE/ROE` pairs the wrong multiple with ROE (see the next row) |
| **Quality is profitability + growth + safety; high-quality stocks have only modestly higher prices, hence high risk-adjusted returns (QMJ).** | Asness, Frazzini & Pedersen (2019), *Quality minus junk*, Review of Accounting Studies 24:34-112 | `https://api.openalex.org/works/doi:10.1007/s11142-018-9470-2` | The library's quality interaction (§33, §82) is a *ratio* between a valuation multiple and a quality score with no stated direction convention; the QMJ construction is a z-score sum with published signs |
| **A low multiple is not evidence of cheapness unless the multiple is paired with its own companion variable: PE with growth, PBV with ROE, PS with net margin. Multiples are skewed and unbounded above, so the median beats the mean; dropping negative-earnings firms biases the average upward; the earnings yield can be computed for all firms where the P/E cannot; `PEG` implicitly assumes PE and growth are linearly related, and there are very few linear relationships in valuation.** | Damodaran, *Investment Valuation*, 2nd ed., ch. 17, "Fundamental Principles of Relative Valuation" (fetched in full) | `https://pages.stern.nyu.edu/~adamodar/pdfiles/valn2ed/ch17.pdf` | **Three differences.** (1) §33 pairs `PE/ROE`; Damodaran pairs **PBV/ROE** — the library's pairing mixes an earnings multiple with an equity return. (2) The library never states a consistency rule (equity numerator ⇒ equity denominator); it defines `P/EBITDA`-style inconsistency nowhere and its §52 `EV = MC + Debt − Cash` contradicts §1's `EV = MC + Debt + Preferred + Minority − Cash`. (3) The library's §30 uses the **percentile** of the historical distribution but never states the median-over-mean or negative-earnings rules; the repo's `percentiles` do, `means` do not |
| **The PEG ratio is not a constant: the justifiable PEG is u-shaped in the growth rate and depends on the length of the rapid-growth period, the long-run sustainable growth rate and the discount rate. The 1.0/1.5 benchmarks are harder to justify than commonly supposed.** | Arak & Foster (2003), *PEG Ratios*, The Journal of Investing 12(2):19-24 | `https://api.openalex.org/works/doi:10.3905/joi.2003.319540` | The library gives `PEG = PE/g` twice (§2 and §20) with **no benchmark, no unit convention and no growth horizon**; §2 even gives both the fraction form and the percent form without saying which produces "1.0 = fair". This is the library's most consequential definitional trap |
| **PEG implicitly assumes the short-run growth forecast persists; the implied-return ranking it produces is "arguably still too simplistic".** | Easton (2004), *PE Ratios, PEG Ratios, and Estimating the Implied Expected Rate of Return on Equity Capital*, The Accounting Review 79(1):73-95 | `https://api.openalex.org/works/doi:10.2308/accr.2004.79.1.73` | The library's `PEG` and `PEGY` (§2) and `PEG-ROIC` (§34) all inherit the persistence assumption and none states it |
| **For correctly valued firms PEG frequently *exceeds* 1.0, especially at low cost of capital; PEG should not be used to choose among different types of firms; its best use is within-industry screening.** | Trombley (2008), *Understanding the PEG Ratio*, The Journal of Investing 17(1):22-25 | `https://api.openalex.org/works/doi:10.3905/joi.2008.701953` | Reinforces the same gap: the library's `PEG < 1 = cheap` is stated nowhere in the library, but its §73 inverse-percentile convention (`100×(1−Percentile)`) would silently encode it |
| **The traditional PEG benchmark of 1 is not appropriate; the benchmark must be customised to the share's own growth rate and cost of equity, and using 1.0 induces measurable error.** | Schnabel (2009), *Benchmarking the PEG Ratio*, The Journal of Wealth Management 12(3):89-94 | `https://api.openalex.org/works/doi:10.3905/jwm.2009.12.3.089` | Same conclusion, stated as an error magnitude. Any PEG leg in `ValuationScore` must be a **rank within a peer set**, never a threshold against 1.0 |
| **CAPE = real price ÷ the 10-year average of inflation-adjusted earnings; it is a long-horizon (≈10-20 year) return forecast, not a timing signal; Shiller publishes the series monthly from 1871.** | Shiller, *Online Data* (Yale), the page that hosts the *Irrational Exuberance* data and the CAPE series | `http://www.econ.yale.edu/~shiller/data.htm` | The library's §2 CAPE is the standard definition, but the library gives it no horizon statement and no data requirement — the repo has **no** 10-year real-EPS series producer (§3 rank 8) |
| **Valuation ratios (P/E, CAPE, dividend yield) predict long-horizon returns; the relationship is strongest over multi-year horizons and weak at short horizons.** | Campbell & Shiller (2001), *Valuation Ratios and the Long-Run Stock Market Outlook: An Update*, NBER Working Paper 8221 | `https://api.openalex.org/works/doi:10.3386/w8221` (record fetched; the fetched abstract is encoding-corrupted, so only the bibliographic identity is relied on here) | The library's §83 "valuation regime" and §79 "valuation trend" are short-horizon by construction (`Score_t − Score_{t−n}`); the literature's horizon is 10+ years. The two must not share a name |
| **High-accrual firms underperform: prices do not fully reflect the information in accruals and cash flows about future earnings.** | Sloan (1996), *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?*, The Accounting Review 71(3):289-315 | `https://api.openalex.org/works/doi:10.2308/tar-9608042309` | The library's §51 "Earnings Yield Quality" uses `FCF/NetIncome` and `EY × FCFConversion` — a **cash-versus-accrual** idea with no accrual term. The repo already has the accrual ratio (`earnings_quality.py:24`, `(NI−OCF)/TA`) and it is *not* wired into any valuation factor |
| **Value investing works best when combined with historical financial-statement information that separates winners from losers within the cheap universe.** | Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*, Journal of Accounting Research 38 (Supplement):1-41 | `https://api.openalex.org/works/doi:10.2307/2672906` | The library's §82 "Valuation vs Quality Spread" gestures at this and then multiplies two 0-100 scores (`QualityScore − ValuationPremiumScore`) without a scale contract. The repo has the F-Score (`quantitative_scores.py::piotroski_f_score:202`) and no valuation-side join |
| **Value strategies outperform because they exploit suboptimal investor behaviour, not because they are fundamentally riskier.** | Lakonishok, Shleifer & Vishny (1994), *Contrarian Investment, Extrapolation, and Risk*, Journal of Finance 49(5):1541-1578 | `https://api.openalex.org/works/doi:10.1111/j.1540-6261.1994.tb04772.x` | The **mispricing** side of the debate. It justifies a valuation score existing at all (as opposed to being absorbed into a risk model) |
| **A risk-based explanation of the value premium exists: value firms covary more with cash-flow shocks, growth firms more with discount-rate shocks; the model accounts for the premium and the CAPM's failure.** | Lettau & Wachter (2007), *Why Is Long-Horizon Equity Less Risky? A Duration-Based Explanation of the Value Premium*, Journal of Finance 62(1):55-92 | `https://api.openalex.org/works/doi:10.1111/j.1540-6261.2007.01201.x` | The **risk** side. Taken with LSV, the conclusion for this design is that a low multiple is *either* a mispricing *or* a risk premium and the score cannot tell which — so `ValuationScore` must never be read as an expected-return forecast |
| **Book-to-price decomposes into an enterprise component (positively related to subsequent returns) and a leverage component (negatively related, conditional on enterprise B/P).** | Penman, Richardson & Tuna (2007), *The Book-to-Price Effect in Stock Returns: Accounting for Leverage*, Journal of Accounting Research 45(2):427-467 | `https://api.openalex.org/works/doi:10.1111/j.1475-679X.2007.00240.x` | The library has P/B (§5) and Debt/EV (§53) as separate, unlinked factors. Penman's decomposition says the two must be read **jointly** — a leveraged cheap stock is not the same signal as an unlevered one |
| **A pure-earnings value factor in China is subsumed by the earnings-price ratio, not book-to-market.** | Liu, Stambaugh & Yuan (2019), *Size and value in China*, Journal of Financial Economics 134(1):48-69 | `https://api.openalex.org/works/doi:10.1016/j.jfineco.2019.03.008` | Supports the repo's choice of `earnings_yield` (+1) as the value-side factor alongside the inverse multiples, and warns that the *best* value measure is market- and sample-specific |

**Not fetched, therefore not claimed:** Fama & French (2012) *Size, value, and momentum
in international stock returns* (JFE 105(3):457-472,
`https://api.openalex.org/works/doi:10.1016/j.jfineco.2012.05.011`) — the record was
fetched and the bibliographic fields verified, but its abstract was not returned, so
this document makes no content claim about it. Likewise the owner's library cites
**no** primary literature at all: the 85 sections carry formulas and no references.

### 4.5 Where the library's formulas differ from the standard definition (summary)

| Library formula | Standard definition | The difference |
| --- | --- | --- |
| §2 `EY = EPS/Price` | Earnings yield = earnings/price (equity-level) | The repo's `earnings_yield` is `EBIT/EV` — a **firm-value** yield, i.e. the library's §48/§50. One name, two quantities |
| §1 `EV = MC + Debt + Preferred + Minority − Cash` vs §52 `EV = MC + Debt − Cash` | One EV definition | The library contradicts itself: §1 includes preferred and minority interest, §52 omits both. The repo follows §52 (`quantitative_scores.py::enterprise_value:241`) |
| §33 `QualityAdjustedPE = PE/ROE` | Damodaran pairs **PBV/ROE** (and PE/growth) | The library pairs the wrong multiple with ROE |
| §38 `V = EPS×(8.5 + 2g)` | The "Graham formula" with a growth multiplier | The repo's Graham Number is `√(22.5·EPS·BVPS)` — a different Graham construction (`fundamental_floors.py::graham_number:21`) |
| §22 `ImpliedGrowth ≈ PE/FairPE` | A growth rate | **Dimensionally wrong**: the ratio of two multiples is a unitless number, not a rate. The library's own second form (`IntrinsicValue(g) = Price`, solve for `g*`) is the correct one and is what `reverse_dcf` implements |
| §20 `PEG = PE/Growth` vs §2 `PEG = PE/g_%` | PEG with a stated growth unit | The two are off by 100×. Neither states which produces "1.0 = fair" |
| §12 `WACC = w_e·K_e + w_d·K_d(1−T) + w_p·K_p` | Standard WACC | The repo's `wacc_from_beta:28` implements only the `K_e` term |
| §77 `CoverageAdjustedScore = RawScore × Coverage` | Master rule 1: `NA ≠ 0`; missing inputs reduce *available weight* | Multiplication drags the score toward 0, i.e. it punishes a name for missing data. The library itself offers the better alternative in the next block (`ValuationScore = RawScore`, `ValuationCoverage = Coverage`, with a floor) — that is the form §5 adopts |
| §80 `FAV = ValuationScore × QualityScore` | A bounded score | The product of two 0-100 scores is 0-10,000. The library's alternative `ValuationScore / RiskAdjustedQuality` names a denominator that is never defined |
| §78 `ValuationStability = 1 − σ(Score_t)/MaximumPossibleVolatility` | — | `MaximumPossibleVolatility` is never defined; the quantity is not computable as written |

---

## 5. The composite

### 5.1 Shape

`ValuationScore` would be **one pure aggregation over the components §1 marks
`elsewhere`/`PARTIAL`**, returning
`{"score": 0-100, "confidence": 0-100, "components": [...], "coverage": {...}, "withheld": {...}}`
— mirroring the shape `fundamental_score.py::fundamental_score:252` already
returns, so a reader can recompute the score from the printed contributions.

It would **not** be a new fetch, and it would **not** recompute a multiple that
§2 already produces.

### 5.2 Proposed gate name

**`enable_valuation_score`** — proposed only. It is **not** added to
`tradingagents/default_config.py` or `.env.example` (proof in §0.1). It would
follow the repo's existing pattern: a boolean defaulting to `False`
(`enable_fundamental_score` is at `default_config.py:1234`, default `False`),
read by a leaf via the `_r3_flag` helper, and it would sit behind
`enable_quant_scorecard` for scorecard membership.

### 5.3 Proposed research-allocation weight — a hypothesis, not a number in code

The master's research allocation ([`README.md`](README.md) §1.4) covers six
engines and **does not contain `ValuationScore` or `MarketScore`**. There is no
owner weight for this engine, so this document proposes one and labels it a
hypothesis (master rule 6: *"No weight vector is invented"* — so it is stated as
proposed and recorded as OPEN Q2):

| Engine | Fundamental | Technical | Regime | Risk | News | Sentiment | **Valuation (proposed)** |
| --- | --: | --: | --: | --: | --: | --: | --: |
| Research weight | 35% | 20% | 15% | 15% | 7.5% | 7.5% | **7.5% (carved out of Fundamental → 27.5%, or added as a seventh line → the table no longer sums to 100)** |

Both carve-out and seventh-line readings are recorded; **neither is adopted here**.
The engine joins no composite by adjacency (master invariant 17): it joins only by
an explicit owner decision, and until then its weight is `0` in every composite and
it is reported as a **standalone advisory read**.

### 5.4 Direction convention

**0-100, 100 = favourable, so cheap = high.** The engine inherits this from the
master ([`README.md`](README.md) §1.2) and from the precedent already in code:
`factor_schema.py` gives nine of the twelve VS factors direction `−1` (a lower
multiple scores higher) and three direction `+1` (yields and upside).

**What this does to a raw P/E.** A raw P/E of 8 and a raw P/E of 40 do **not**
enter the score as numbers. Each is:

1. **winsorised** at P1/P99 across the comparison set (`cross_section.py::winsorize:31`),
2. **z-scored** cross-sectionally or within sector (`cross_section.py::cross_sectional_z:70`, `industry_neutral_z:89`),
3. **sign-aligned** by the factor's declared direction (`−1` for a multiple, `+1` for a yield), and
4. **mapped to 0-100** by a tie-aware percentile (`factors.py::percentile_rank:59`, `cross_section.py::centered_rank:162`).

So a P/E of 8 in a sector whose median is 25 becomes a *high* aligned contribution,
and a P/E of 8 in a sector whose median is 7 becomes a *low* one. **The raw value
and its unit are printed beside the aligned contribution** (master §1.2's hard
requirement, restated by `RiskScore.md` §0.2): the report shows
`price_to_earnings 8.0 (x) → aligned 91.2 / 100`.

Two quantities must never be aligned into one number: the **absolute** multiple and
its **relative** position. They are separate component rows with separate names —
the rule that stops `ValuationScore` becoming a second `FundamentalScore.VS`.

### 5.5 Coverage and floor rule

Adopted from the repo's existing policy, not from the library's §77 multiplication:

1. **`NA ≠ 0`** (master rule 1). A factor the panel does not carry for a name is
   absent from that name's row; the remaining weights renormalise.
2. **A coverage floor.** `factors.py::_coverage_floor:246` already implements
   "below the floor ⇒ withheld with a reason, never scored on what it lacks". The
   proposed floor is **≥3 of the engine's factor rows present** — the same floor
   `fundamental_score.py::_subscore:116` uses for its sub-scores (`min_coverage=3`)
   — with the exact number an OPEN item (Q3).
3. **Coverage is printed, never multiplied into the score.** The score and
   `ValuationCoverage` are two outputs (the library's own preferred form, §77's
   second block).
4. **Confidence is a separate 0-100 output**, from §58's dispersion (rank 1 in §3):
   high dispersion across the available intrinsic-value models ⇒ low confidence.
   It never distorts the score. The owner's own wider design says the same thing
   in a second place: `Strategies/other_score.md:1177-1183` puts
   `DataConfidenceScore`, `SignalAgreementScore`, `ForecastUncertaintyScore` and
   `ModelConsensusScore` in a **"Meta-scores — keep these separate"** tier, because
   they answer *"How much should I trust the evidence?"* rather than *"Is the stock
   attractive?"*. `ValuationConfidence` belongs to that tier, not to this score.
5. **No-data ⇒ `None`.** Never 0, never 50 (the same rule `fundamental_score` and
   `risk_score` follow).

---

## 6. Verification requirements

1. **The engine does not recompute a multiple.** A test asserts every component of
   the composite resolves to a symbol in §2.1 and that no `price_to_*`, `ev_*`,
   `*_yield` arithmetic appears inside the new module. (Master invariant 8; the
   boundary with `FundamentalScore` is the thing this test exists to hold.)
2. **Direction is tested at the boundary.** A test feeds a raw P/E of 8 and a raw
   P/E of 40 into the same peer set and asserts the lower one aligns higher, and
   that a yield factor aligns the *opposite* way.
3. **`NA ≠ 0` for every component.** A missing multiple must **raise** reported
   uncertainty and reduce the available weight; it must never lower the score.
4. **No-data run returns `None`**, never 50 and never 0.
5. **The score never reaches a gate.** A test asserts the value appears in no
   `GATE_PRECEDENCE` check (`../TradingExecution/signald/contracts.py`) and in no
   `risk_multiplier` input, and that it never reaches
   `decision_guardrail.SCORE_BANDS`.
6. **Reproducibility.** The printed component contributions must recompute the
   printed score.
7. **Score ≠ confidence.** A test asserts the two are separate keys and that
   setting the confidence to its minimum does not move the score.
8. **The peer panel is shared, not rebuilt.** A test asserts the engine reads the
   same panel `FundamentalScore.VS` reads, so one name's multiples are measured
   once.
9. **PEG is a rank, never a threshold.** A test asserts no code path compares a PEG
   to `1.0` (Schnabel 2009, §4).
10. **A dark launch is measured, not assumed.** Gate off vs gate on on the same
    basket, using `scripts/repro_check.py --evidence`, `scripts/report_verify.py`
    and `scripts/verify_sweep.py` (inherited ground rule 10 from
    [`FundamentalScore.md`](FundamentalScore.md) §0.3).

---

## 7. OPEN questions for the owner

**Q1 — the `FundamentalScore` boundary (first, and blocking).** The built
`FundamentalScore` already owns a `valuation_subscore` (`fundamental_score.py:211`)
carrying 12 factors, 9 of them inverse multiples, at a proposed 20.00 of the
owner's 106-factor table ([`FundamentalScore.md`](FundamentalScore.md) §2.4). Does
`ValuationScore`:

- **(A)** absorb it — moving the multiples out of `fundamental_score.py`, deleting
  `VS` from `SUBSCORE_FACTORS` (`factor_schema.py:410`), and re-writing the owner's
  ledger and every stored `VS` reading;
- **(B)** leave it and be a **relative-value + uncertainty layer only**, reading the
  VS multiples instead of recomputing them; or
- **(C)** accept that they are the same object under two names (which violates
  master invariant 15)?

This document recommends **B** and implements nothing. **No work on this engine may
start before Q1 is answered** — the answer determines whether a new module may
compute a multiple at all.

**[ANSWERED 2026-09-26 by the owner: `ValuationScore` becomes its own engine and
`FundamentalScore` CONSUMES it — the closest reading to (B), with the ownership
made explicit rather than left implicit.** The owner's rule:

> *"Calculate valuation once. Attribute it twice if necessary, but don't calculate
> it twice."*

The architecture the answer fixes:

```
ValuationScore  ← DCF, multiples, EV/EBITDA, P/E, P/S, FCF yield, PEG,
                  residual income, relative valuation — computed ONCE here
      │
      ▼
FundamentalScore = w_Q·Quality + w_G·Growth + w_B·BalanceSheet
                 + w_C·CashFlow + w_V·Valuation,   V = ValuationScore
```

That is the whole point of the answer: the failure it prevents is a DCF that
reaches the final composite **through two independent-looking paths** — once as
`ValuationScore` and once inside `FundamentalScore.valuation_subscore` — which is
the double count master rule 3/15 forbids, not a weighing question.

Consequences, recorded so the migration cannot drift:

* **This is not (A).** The multiples do not move out of `fundamental_score.py`
  before `ValuationScore` exists and produces them; `VS` in `SUBSCORE_FACTORS`
  (`factor_schema.py:410`) stays until the cutover, and no stored `VS` reading is
  rewritten. The migration order is VAL-8 (the module) before any `VS` change.
* **This is not (C).** They are not one object under two names: `ValuationScore`
  is the producer of the valuation dimension; `FundamentalScore`'s valuation leg
  becomes a **consumption** of it, named as a dependency in the schema.
* **Until the migration lands the overlap is latent, not live** — there is no
  `ValuationScore` producer in the tree (zero code hits), so nothing is counted
  twice today. The risk is a future module duplicating the calculation, which is
  what the rule above forbids.
* **Q2 (the allocation weight) and Q5 (who owns the historical-position quantity)
  now follow**: the valuation dimension must have exactly one weight wherever it
  enters, and `val_z` is `ValuationScore`'s rather than a second
  `FundamentalScore` producer.

`MASTER_PLAN.md` §2.1 records the answer; Phase 7's VAL rows are unblocked.

**Q2 — the research-allocation weight.** `ValuationScore` is absent from the
master's six-engine allocation. Is its weight a carve-out from Fundamental (→
27.5 / 7.5) or a seventh line that breaks the 100% sum? Proposed 7.5%, unadopted.

**Q3 — the coverage floor.** Is it `≥3` factors (matching `_subscore`'s
`min_coverage=3`), or a higher bar for an engine whose whole claim is coverage?

**Q4 — is `dcf_upside` a factor or an input?** Today it is a *caller-supplied*
VS factor (`factor_schema.py:342`), scaled by `dcf_confidence:421`, and its
supplier column literally reads `"caller (confidence grade D …)"`. If
`ValuationScore` owns intrinsic value, does it become the producer of that leg —
and does `VS` then read it rather than the caller supplying it?

**Q5 — does `ValuationScore` own the historical percentile, or does
`FundamentalScore`'s `val_z`?** `val_z` is `availability=NA` in the VS schema
(`factor_schema.py:332`) and `value_dip.py::valuation_z_read:122` produces it. One
of the two engines must own the historical-position quantity.

**Q6 — the confidence output.** Is `ValuationConfidence` a second published 0-100
score (the library's 14-key output contract, `:2240-2254`), a sub-field of the
score block, or out of scope? The library is emphatic that it must not be folded
into the score, and the owner's `Strategies/other_score.md:1177-1183` already names
a separate meta-score tier for exactly this kind of quantity — is
`ValuationConfidence` a member of it?

**Q7 — CAPE.** §3 rank 8 needs a 10-year real-EPS series, which does not exist.
Is SEC EDGAR XBRL history (`dataflows/sec_edgar.py`, tool at
`analysis_tools.py::get_financial_history:11900`) the sanctioned source, as it is
for the fundamental panel (`FundamentalScore.md` §0.5 Q4), or is CAPE out of scope
for v1?

---

## Appendix — the library's sections, verbatim

Line numbers are the H1 line in
[`../../Strategies/scores/valuation_score.md`](../../Strategies/scores/valuation_score.md)
(2,269 lines). "Formulas" is the `$$`-block count as described in §1 (86 H1 blocks
— 85 numbered plus the unnumbered architecture block — and 257 `$$` blocks).

| § | Section (verbatim) | Line | Formulas | `###` subsections |
| --: | --- | --: | --: | --: |
| 1 | Market-Capitalization Valuation | 13 | 5 | 5 |
| 2 | Earnings Multiples | 55 | 12 | 8 |
| 3 | EV/Earnings Valuation | 133 | 6 | 6 |
| 4 | Revenue Multiples | 178 | 5 | 5 |
| 5 | Book-Value Valuation | 214 | 5 | 5 |
| 6 | Enterprise Value to Assets | 249 | 4 | 4 |
| 7 | Cash-Flow Valuation | 277 | 8 | 8 |
| 8 | Free Cash Flow Calculations | 333 | 6 | 6 |
| 9 | DCF Valuation | 377 | 2 | 2 |
| 10 | Gordon Growth Terminal Value | 400 | 3 | 0 |
| 11 | Exit-Multiple Terminal Value | 423 | 3 | 0 |
| 12 | WACC | 444 | 5 | 4 |
| 13 | Multi-Stage DCF | 481 | 1 | 0 |
| 14 | Dividend Discount Models | 503 | 5 | 4 |
| 15 | Residual Income Valuation | 543 | 3 | 1 |
| 16 | Economic Value Added | 571 | 3 | 3 |
| 17 | Economic Profit | 596 | 2 | 1 |
| 18 | ROIC-Based Valuation | 614 | 4 | 3 |
| 19 | Growth-Based Valuation | 647 | 5 | 4 |
| 20 | PEG / Growth-Adjusted Valuation | 685 | 4 | 4 |
| 21 | Rule of 40 / Growth-Profitability Valuation | 716 | 2 | 0 |
| 22 | Implied Growth From P/E | 736 | 3 | 0 |
| 23 | Implied WACC | 761 | 3 | 0 |
| 24 | Implied Terminal Growth | 784 | 3 | 0 |
| 25 | Implied Revenue Growth | 810 | 1 | 0 |
| 26 | Implied Margin | 826 | 2 | 0 |
| 27 | Reverse DCF | 844 | 3 | 0 |
| 28 | Relative Valuation | 876 | 9 | 2 |
| 29 | Relative Valuation Z-Score | 926 | 2 | 0 |
| 30 | Historical Valuation Percentile | 951 | 2 | 0 |
| 31 | Historical Premium/Discount | 977 | 2 | 0 |
| 32 | Sector-Adjusted Valuation | 993 | 2 | 0 |
| 33 | Quality-Adjusted Valuation | 1010 | 3 | 0 |
| 34 | PEG-ROIC | 1038 | 1 | 0 |
| 35 | Earnings Yield vs Bond Yield | 1050 | 3 | 3 |
| 36 | Equity Risk Premium From Market Valuation | 1076 | 1 | 0 |
| 37 | Buffett-Style Owner Earnings | 1088 | 3 | 0 |
| 38 | Graham Valuation | 1116 | 2 | 0 |
| 39 | Asset-Based Valuation | 1137 | 4 | 4 |
| 40 | Sum-of-the-Parts Valuation | 1174 | 3 | 1 |
| 41 | Liquidation Value | 1199 | 2 | 1 |
| 42 | Replacement-Cost Valuation | 1216 | 1 | 0 |
| 43 | Net-Net Valuation | 1232 | 3 | 1 |
| 44 | Dividend Yield Relative Valuation | 1256 | 3 | 0 |
| 45 | Dividend Discount Implied Value | 1279 | 2 | 0 |
| 46 | Buyback-Adjusted Shareholder Yield | 1295 | 3 | 2 |
| 47 | Total Yield | 1320 | 2 | 0 |
| 48 | Enterprise Yield | 1336 | 2 | 0 |
| 49 | EBITDA Yield | 1351 | 1 | 0 |
| 50 | EBIT Yield | 1360 | 1 | 0 |
| 51 | Earnings Yield Quality | 1369 | 2 | 0 |
| 52 | Cash-Adjusted Valuation | 1387 | 2 | 0 |
| 53 | Debt-Adjusted Valuation | 1406 | 3 | 3 |
| 54 | Dilution-Adjusted Valuation | 1433 | 3 | 0 |
| 55 | Share-Based Compensation Adjustment | 1461 | 3 | 0 |
| 56 | Margin-of-Safety Calculations | 1486 | 4 | 2 |
| 57 | Weighted Intrinsic Value | 1518 | 3 | 0 |
| 58 | Valuation Dispersion | 1543 | 5 | 0 |
| 59 | Intrinsic Value Confidence | 1576 | 1 | 0 |
| 60 | Scenario Valuation | 1592 | 3 | 1 |
| 61 | Monte Carlo Valuation | 1622 | 10 | 0 |
| 62 | Valuation VaR | 1676 | 3 | 0 |
| 63 | Probability of Overvaluation | 1700 | 2 | 1 |
| 64 | Expected Valuation Gap | 1716 | 1 | 0 |
| 65 | Bear-Case Downside | 1725 | 2 | 1 |
| 66 | Valuation Asymmetry | 1741 | 1 | 0 |
| 67 | Market-Implied Multiple | 1753 | 4 | 0 |
| 68 | Historical Multiple Mean Reversion | 1782 | 3 | 0 |
| 69 | Relative Valuation Regression | 1805 | 3 | 0 |
| 70 | Cross-Sectional Residual Valuation | 1837 | 2 | 0 |
| 71 | Factor-Adjusted Valuation | 1868 | 2 | 0 |
| 72 | Sector-Neutral Valuation Score | 1888 | 1 | 0 |
| 73 | Market-Neutral Valuation Score | 1904 | 1 | 0 |
| 74 | Composite Valuation Factor | 1918 | 2 | 0 |
| 75 | Normalized Valuation Components | 1941 | 5 | 4 |
| 76 | Winsorized Valuation Factors | 1987 | 1 | 0 |
| 77 | Missing-Data / Coverage Score | 2004 | 4 | 0 |
| 78 | Valuation Stability | 2037 | 2 | 0 |
| 79 | Valuation Trend | 2054 | 2 | 0 |
| 80 | Fundamental-Adjusted Valuation | 2077 | 2 | 0 |
| 81 | Valuation vs Growth Matrix | 2098 | 2 | 0 |
| 82 | Valuation vs Quality Spread | 2119 | 1 | 0 |
| 83 | Valuation Regime | 2130 | 1 | 0 |
| 84 | Valuation Mean-Reversion Potential | 2149 | 2 | 0 |
| 85 | Valuation Composite With Multiple Independent Models | 2166 | 3 | 0 |
| — | Recommended ValuationScore Architecture for Your System (unnumbered H1) | 2208 | 1 | 0 |

### A.1 Duplicate and mislabelled `###` headings

Read at both line ranges this round:

| Heading | Line 1 | Line 2 | Verdict |
| --- | --: | --: | --- |
| `### EV/EBIT` | **:135** (`EV/EBIT = EV/EBIT`) | **:163** (`EV/EBIT = EnterpriseValue/OperatingIncome`) | **Duplicate heading, two different denominators.** The same name is given for `EBIT` and for `OperatingIncome`; the second block is the repo's own convention (`factor_schema.py:270` uses `operating_income`), so :135 is the mislabel |
| `### PEG` | **:107** (`PEG = PE/EPS Growth Rate`, plus the percent variant) | **:687** (`PEG = PE/Growth`) | **Duplicate heading, and the two forms disagree by 100×** on the growth unit. Neither states a benchmark (§4) |

### A.2 Library-internal defects (verified by reading)

1. **`### EV/EBIT` twice, §3:135 and §3:163**, with different denominators (A.1).
2. **`### PEG` twice, §2:107 and §20:687**, with inconsistent growth units (A.1).
3. **`ExcessReturn = ROIC − WACC` (§18:626) and `VCS = ROIC − WACC` (§18:632)** — one formula, two names, in the same section.
4. **`EnterpriseYield = EBIT/EV` (§48:1339) and `EBIT Yield = EBIT/EV` (§50:1363)** — one formula, two names, in adjacent sections.
5. **`ShareholderYield = DividendYield + BuybackYield` (§46:1307) and `TotalYield = DividendYield + BuybackYield` (§47:1323 and again :1330)** — §47 offers two variants, one of which is identical to §46.
6. **Two EV definitions.** §1:24 includes preferred equity and minority interest; §52:1392 omits both. The repo follows §52.
7. **`ImpliedGrowth ≈ PE/FairPE` (§22:741)** — dimensionally wrong; the ratio of two multiples is not a growth rate.
8. **`ValuationConfidence}}` (§85:2187)** — unbalanced brace inside the `\boxed{}` (`\boxed{ValuationConfidence}}`), a typo.
9. **`FAV = ValuationScore × QualityScore` (§80:2082)** — the product of two 0-100 scores is 0-10,000; the alternative on the next lines (`ValuationScore / RiskAdjustedQuality`, :2089) names a denominator that is never defined.
10. **`ValuationStability = 1 − σ(Score_t)/MaximumPossibleVolatility` (§78:2048; the denominator is at :2049)** — `MaximumPossibleVolatility` is never defined anywhere in the library.
11. **`Coverage = AvailableFactors/RequiredFactors` (§77:2009)** — `RequiredFactors` is never enumerated, although the library's own closing contract lists 14 output keys.
12. **`CoverageAdjustedScore = RawScore × Coverage` (§77:2017)** contradicts master rule 1 (`NA ≠ 0`); the library itself supersedes it two blocks later (:2028).
13. **`FAV = ValuationScore / RiskAdjustedQuality` (§80:2089)** and **`VQSpread = QualityScore − ValuationPremiumScore` (§82:2122)** — a 0-100 score minus an undefined "premium score": no unit contract.
14. **`VGSpread = ExpectedGrowth − ValuationPremium` (§81:2103)** — a growth rate minus a multiple-relative premium fraction: no unit contract.
15. **`AdjustedEY = EarningsYield × FCFConversion` (§51:1381)** — a yield multiplied by a conversion ratio, with no stated scale; and `EYQuality = FCF/NetIncome` (§51:1374) is a cash-conversion ratio under a valuation name.
16. **Counting artefacts.** §28's 9 "formulas" include 7 bare multiple names (`P/E`, `ForwardP/E`, `EV/EBITDA`, `EV/Sales`, `P/S`, `P/B`, `P/FCF`, at :880-906); §61's 10 include distributional placeholders (`g ~ Distribution`, `IV_1,…,IV_N`, `MedianIV`, `P(IV>Price)`, `P(IV<Price)`, `VaR`, `CVaR`, at :1633-1661); §26's 2 are labels (`OperatingMargin^*` at :830, `EBITDAMargin^*` at :836). The 257 total therefore overstates the true equation count.
17. **No references.** The library cites no primary literature in any of its 85 sections; every weight and every ordering in it is a hypothesis (master rule 6).

### A.3 Library-vs-code contradictions (verified by reading the code)

1. **"Earnings yield" means two different things.** Library §2 `EY = EPS/Price` (equity) versus `quantitative_scores.py::earnings_yield:251` `EBIT/EV` (firm) — the latter is the library's §48/§50. The repo's VS factor `earnings_yield` (`factor_schema.py:317-321`) inherits the collision.
2. **Graham.** Library §38 `V = EPS×(8.5+2g)` versus `fundamental_floors.py::graham_number:21` `√(22.5·EPS·BVPS)` — two different Graham constructions under one name.
3. **WACC.** Library §12 gives the full `w_e·K_e + w_d·K_d(1−T) + w_p·K_p`; `dcf.py::wacc_from_beta:28` returns `rf + beta·erp` — cost of equity only — and it is printed as "WACC" by `get_dcf_valuation:2804` (`dcf.py:31` documents the omission).
4. **Coverage.** Library §77 multiplies; the repo withholds below a floor and renormalises (`factors.py::_coverage_floor:246`, `category_scores:258`) per master rule 1.
5. **Quality adjustment.** Library §33 `PE/ROE` versus Damodaran's `PBV/ROE` pairing (the companion-variable rule in §4's Damodaran row).
6. **PEG benchmark.** Library §2/§20 give `PEG` with no benchmark; the literature (Arak & Foster 2003; Schnabel 2009; Trombley 2008) shows a fixed benchmark of 1.0 is wrong, and the repo's only PEG producer (`value_dip_tools.py::_forward_peg_read:659`) returns a bare number with no peer context.
