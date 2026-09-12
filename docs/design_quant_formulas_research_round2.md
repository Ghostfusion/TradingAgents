# Quant-Finance Formulas Research, Round 2 — delta scan vs. the landed library

Status: **research/design only (2026-09-11) — no code changed.** Round 2 of
[`design_quant_formulas_research.md`](design_quant_formulas_research.md)
(2026-09-05). Round 1 produced an adopted list; most of it has since **landed**
in the library. This round (a) records which round-1 items are now shipped, so
nothing is re-planned, and (b) adds the formulas a second, style-directed web
sweep surfaced that are still **absent** — chosen for fit to *this* project's
trading style: value-dip swing entries on daily bars, a gated book with hard
CVaR/drawdown limits, and an LLM multi-agent analysis path whose claims must be
checkable.

Companion: [`docs/implementation_plan_quant_formula_additions.md`](implementation_plan_quant_formula_additions.md)
(the phased build plan for the adopted list; designed, not started).

---

## 0. Method

1. **Style first.** Fixed the target profile before searching: fundamentals-anchored
   **value-dip swing** entries (`Strategies/Value_Dip_swing.md`), daily bars, tranche
   scale-in, ATR stops, days-to-weeks holds, book-level CVaR (3.00% daily budget) and
   drawdown (10.00% limit) gates, and an LLM debate path whose numeric claims are
   harvested as ground-truth by the debate and audited by `report_verifier`.
2. **Inventory.** 107 `tradingagents/strategies/*.py` modules, the 24-row
   [`Strategies/index.md`](../Strategies/index.md) plan→module→flag→consumer map, the
   `docs/design_*` and `docs/implementation_plan_*` families, and the agent tool
   surface (market/news/fundamentals/value-dip toolsets).
3. **Round-1 ledger.** Read [`design_quant_formulas_research.md`](design_quant_formulas_research.md)
   in full and checked **every** adopted item against source, marking landed /
   still-open / rejected. Result in §1.
4. **Gap sweep.** Web search across: LLM/text factors and factor mining, conformal
   prediction in finance, cross-sectional anchoring and return decomposition,
   high-low spread estimation and market impact, portfolio optimisation under tail
   constraints, copula dependence, and evaluation statistics beyond DSR/PBO.
5. **Exclusion rule.** A candidate is listed only if it is **absent from source**
   (verified by definition-site grep, not by prose mentions in prompts) **and** has a
   named consumer in this repo. Everything already present or already planned
   elsewhere is in §3 with the pointer.

---

## 1. Round-1 ledger — what landed since 2026-09-05

| Round-1 item | Status | Landed as |
| --- | --- | --- |
| C1 Lo–MacKinlay variance ratio | **landed** | `strategies/mean_reversion.py::variance_ratio`, surfaced as `get_mean_reversion_quality` |
| C2 complexity/entropy | **landed** | `strategies/complexity.py::permutation_entropy`, `approximate_entropy` |
| C3 CUSUM/EWMA online shift | **landed** | `strategies/regime.py::cusum`, `ewma_control`, surfaced as `get_shift_detection` |
| C4 Kendall τ + t-copula tail dependence | **open** | planned here (§2 N6) and sketched in `design_quantlib_lean_enhancements.md::tail_dependence` |
| D1 MAX + IVOL lottery screens | **landed** | cross-sectional MAX/IVOL reads in `analysis_tools` (with the correct "expected to underperform" interpretation) |
| D2 Harvey–Liu multiple-testing haircut | **open, low** | — (DSR/PBO landed independently) |
| E1 Ohlson O-score + Zmijewski | **landed** | `strategies/normalized.py::ohlson_o_score`, `zmijewski_score` |
| E2 Dechow–Dichev accrual quality | **landed** | accrual-quality reads in the fundamentals/value-dip path |
| F1 Taylor rule | **landed** | macro stance read (`cycle_tilt` family) |
| G1 Almgren–Chriss + TWAP/VWAP/POV | **landed** | `strategies/execution_schedule.py`, tool `get_execution_schedule` |
| H1 volatility-targeting overlay | **landed** | `strategies/size.py::volatility_target_scale` (`target_vol`), folded in `strategies/overlays.py` |
| H2 CPPI | **open, low** | — |
| B1–B5 (Cornish–Fisher VaR, Kappa/LPM, Burke/Martin/Pain, gain-to-pain, ruin/optimal-f) | **landed** | `book_risk.py`, `evaluate.py`, journal/quality rows |
| A1–A4 (speed/zomma, RR/BF/TS, var-swap strike, parity screen) | **landed** (A2/A3/A4 per options layer) | `options_math.py`, `options_surface.py` |
| I1 calendar windows | **not adopted** | round-1 caveat stands; see §3 |

**Consequence:** this round adds no variance-ratio, CUSUM, entropy, AC, vol-target,
Ohlson or MAX/IVOL work. The open items above are the only carry-over, and C4 is
folded into N6 below rather than planned twice.

---

## 2. Adopted list — genuinely absent, style-relevant, buildable

Each item: formula → provenance → why it fits *this* style → consumer in this
repo → data → failure mode / honest degradation.

### N1 — Quote-free spread estimators (Corwin–Schultz; Abdi–Ranaldo)

$$\beta=\left[\ln\tfrac{H_t}{L_t}\right]^2+\left[\ln\tfrac{H_{t+1}}{L_{t+1}}\right]^2,\qquad \gamma=\left[\ln\tfrac{H^{(2)}_t}{L^{(2)}_t}\right]^2$$
$$\alpha=\frac{\sqrt{2\beta}-\sqrt{\beta}}{3-2\sqrt2}-\sqrt{\frac{\gamma}{3-2\sqrt2}},\qquad \hat S=\frac{2\left(e^{\alpha}-1\right)}{1+e^{\alpha}}$$

Abdi–Ranaldo adds the daily close and mid-range $\eta_t=(H_t+L_t)/2$ and is the
more efficient of the two.

- **Provenance:** Corwin & Schultz, *A Simple Way to Estimate Bid-Ask Spreads from
  Daily High and Low Prices*, Journal of Finance 67(2), 2012
  ([scholar](https://scholar.google.com/scholar?q=Corwin+Schultz+simple+way+to+estimate+bid-ask+spreads+from+daily+high+and+low+prices));
  Abdi & Ranaldo, *A Simple Estimation of Bid-Ask Spreads from Daily Close, High,
  and Low Prices*, Review of Financial Studies 30(12), 2017
  ([scholar](https://scholar.google.com/scholar?q=Abdi+Ranaldo+simple+estimation+of+bid-ask+spreads+from+daily+close+high+low)).
- **Fit:** the liquidity gate today rests on Amihud / Kyle λ / Roll and on quoted
  spreads where the vendor provides them. The dip universe (US mid-caps, HK names
  via moomoo, sparse bars) often has no clean quote, and both estimators need only
  the **already-fetched daily OHLC**. They give the gate a cost floor per name
  instead of a blanket verdict, and they are the empirical anchor for the temporary
  impact coefficient η in the **already-landed** Almgren–Chriss tool
  (`get_execution_schedule(temp_impact=...)` currently takes it from the caller).
- **Consumer:** `strategies/liquidity_risk.py` (new estimator + gate input),
  `strategies/execution_schedule.py` (η default when unset), tool rows next to
  `get_liquidity_risk`.
- **Data:** OHLCV only. **Failure mode:** high-low estimators are biased upward on
  gap days and on very low-priced names — report a two-sided value and mark the
  estimator unavailable (never fabricate a spread) when the two-day range
  correction goes negative.

### N2 — Conformalised quantile bands for valuation and targets

Quantile regression gives $\hat q_{\alpha/2}(x),\hat q_{1-\alpha/2}(x)$; conformal
calibration widens them by the empirical $(1-\alpha)$ quantile $\hat Q$ of the
calibration-set scores:
$$\hat C(x)=\left[\hat q_{\alpha/2}(x)-\hat Q,\;\hat q_{1-\alpha/2}(x)+\hat Q\right]$$

- **Provenance:** Vovk, Gammerman & Vovk–Shafer line of work — overview in
  [Conformal prediction](https://en.wikipedia.org/wiki/Conformal_prediction);
  conformalised quantile regression (CQR) is the standard finance-ready wrapper.
- **Fit:** the project's DCF / fair value / price-target reads are **point
  estimates**, and the verifier compares them against hand-set tolerances. A
  calibrated band turns "trading at a 22% discount to fair value" into a statement
  with a stated coverage, and gives `report_verifier` a principled tolerance: a
  claim outside the band is flagged, inside it is not. Applies to the DCF family and
  to any model-implied target (expectancy, PMCC breakeven).
- **Consumer:** `strategies/dcf.py` / `cycle_dcf.py` (band), a `get_valuation_band`
  fundamentals tool, `agents/utils/report_verifier.py` (tolerance).
- **Data:** needs a **history of model-vs-realized pairs** (the run store / memory log
  holds the reports). Rolling calibration window, because the exchangeability
  assumption is violated by regime drift — state the window and the realized
  coverage, and degrade to "band unavailable (n<k)" rather than emitting an
  uncalibrated interval.
- **Risk:** coverage is guaranteed *marginally under exchangeability*; finance is not
  exchangeable. The honest output is "nominal 90% band, realized 87% over the last
  250 pairs" — never a bare "90%".

### N3 — Gross profitability (Novy–Marx)

$$\text{GP/A}=\frac{\text{Sales}-\text{COGS}}{\text{Total assets}}$$

- **Provenance:** Novy-Marx, *The Other Side of Value: The Gross Profitability
  Premium*, Journal of Financial Economics 108(1), 2013
  ([scholar](https://scholar.google.com/scholar?q=Novy-Marx+the+other+side+of+value+gross+profitability+premium)).
- **Fit:** the dip screen answers "is it cheap" and, via Piotroski/Beneish/Ohlson,
  "is it distressed or manipulating". It does not answer "is the *business* good".
  GP/A is the cheapest such measure from statements the repo already parses, it is
  near-orthogonal to the value stack, and it is a **quality counterweight to a dip**:
  a cheap, gross-profitable name is a different proposition from a cheap,
  gross-unprofitable one.
- **Consumer:** `dataflows/quantitative_scores.py` (next to `piotroski_f_score`),
  `strategies/normalized.py` (normalization), value-dip floors, screener column.
- **Data:** income statement + balance sheet, already in the statement chain.
  **Failure mode:** COGS is missing for some financials/REITs — emit unavailable,
  do not substitute operating income.

### N4 — Net operating assets (NOA)

$$\text{NOA}=\frac{\text{Operating assets}-\text{Operating liabilities}}{\text{Total assets}_{t-1}}$$

- **Provenance:** Hirshleifer, Hou, Teoh & Zhang, *Do Investors Overvalue Firms with
  Bloated Balance Sheets?*, Journal of Accounting and Economics 38, 2004
  ([scholar](https://scholar.google.com/scholar?q=Hirshleifer+Hou+Teoh+Zhang+do+investors+overvalue+firms+with+bloated+balance+sheets)).
- **Fit:** the balance-sheet bloat factor — high NOA predicts lower returns. It is the
  balance-sheet sibling of the accrual work already present, and it is a genuine
  *dip-risk* filter: a name whose assets have been inflating without cash backing is
  not the same bargain as one that has been deleveraging into the dip.
- **Consumer:** same homes as N3; screener column.
- **Data:** two consecutive balance sheets. **Failure mode:** operating-vs-financial
  split is ambiguous for hybrids — label the classification used.

### N5 — Minimum-CVaR / minimum-CDaR sizing under the existing budget (§C4 folded in)

$$\min_{w,\zeta}\;\zeta+\frac{1}{(1-\alpha)T}\sum_{t=1}^{T}\max\!\big(L_t(w)-\zeta,0\big)$$

- **Provenance:** Rockafellar & Uryasev, *Optimization of Conditional Value-at-Risk*,
  Journal of Risk 2(3), 2000
  ([scholar](https://scholar.google.com/scholar?q=Rockafellar+Uryasev+optimization+of+conditional+value+at+risk));
  CDaR is the drawdown analogue. HRP/NCO clustering is already in the library.
- **Fit (the strongest structural gap):** the book **measures** CVaR (1.21%), CDaR,
  component and incremental VaR, and **gates** on a 3.00% budget and a 10.00%
  drawdown limit — but nothing **solves for weights under those constraints**. The
  gate can only say REJECT; this turns it into "size to X", which is what the
  position-contract arithmetic already does by hand for a single name. Folding in
  round-1 C4: a t/Clayton copula replaces the single fixed −10% `book_correlated_stress`
  shock with joint tail scenarios, which is the honest input to the same optimisation.
- **Consumer:** `strategies/book_risk.py` (optimiser next to the measures),
  `strategies/risk_governor.py` (a *sizing* remedy beside PASS/WARN/REJECT),
  `strategies/portfolio_optimizer.py` (weight target), tool `get_book_risk_budget`.
- **Data:** the book return matrix the risk basket already builds
  (`risk_basket_tickers`/`risk_basket_weights`), plus a scenario set. **Failure
  mode:** LP solutions on short samples are unstable — report the sample length,
  cap the weight delta from the current book, and degrade to the existing gate when
  the scenario count is below a floor.

### N6 — Loughran–McDonald tone, readability, and call-vs-filing divergence

- **Provenance:** Loughran & McDonald, *When Is a Liability Not a Liability?*,
  Journal of Finance 66(1), 2011
  ([scholar](https://scholar.google.com/scholar?q=Loughran+McDonald+when+is+a+liability+not+a+liability));
  2025 work finds **tone divergence** between earnings calls and 10-K/MD&A predicts
  returns (temporary) while **complexity/readability divergence** is more persistent
  ([scholar](https://scholar.google.com/scholar?q=%22Off+Script%22+earnings+calls+filings+different+stories)).
- **Fit:** this is the LLM-native item. The engine already reads filings, calls, news
  and analyst text, but the only text signal is a **model/vendor sentiment number**.
  A dictionary-based tone count and a readability measure are *deterministic and
  reproducible*, so they can (a) sit beside the LLM narrative read as a second,
  non-model opinion, and (b) give `report_verifier` something to check the LLM's
  tone/"management sounded confident" claims against. Divergence between two
  documents the engine both holds is exactly the kind of cross-section the verifier
  already does for numbers.
- **Consumer:** `agents/utils/news_data_tools.py` (additive reads),
  `dataflows/*` text sources (e.g. `seekingalpha`, `eodhd`, filings), verifier hooks.
- **Data:** document text the engine already fetches. **Failure mode:** dictionary
  counts are period-dependent and myopic to domain drift — always report the count
  and the dictionary version, never a verdict alone.

### N7 — White's Reality Check / Hansen's SPA

- **Provenance:** White (2000), *A Reality Check for Data Snooping*; Hansen (2005),
  *A Test for Superior Predictive Ability*
  ([scholar](https://scholar.google.com/scholar?q=White+reality+check+data+snooping+Hansen+test+superior+predictive+ability)).
- **Fit:** DSR corrects a *single* strategy's Sharpe for the number of trials, and
  PBO measures how often the in-sample winner fails out-of-sample. When the factor
  zoo compares a **universe** of candidate expressions (`alpha_zoo.bench_zoo`), the
  missing step is the bootstrap test of whether the *best* candidate beats the
  benchmark after the search. It is the statistical close-out for any future
  LLM-proposed factor run, and it needs only the per-candidate return series the zoo
  already produces.
- **Consumer:** `strategies/evaluate.py` (next to `deflated_sharpe`, `pbo_flag`),
  `strategies/alpha_zoo.py::bench_zoo` (a row per bench run).
- **Data:** candidate return matrix. **Failure mode:** needs a stationary bootstrap
  with a block length — report the block length; do not run it on fewer trials than
  it can distinguish.

### N8 — Overnight-vs-intraday return decomposition

$$r_t = \underbrace{\ln(C_t/O_t)}_{\text{intraday}} + \underbrace{\ln(O_t/C_{t-1})}_{\text{overnight}}$$

- **Provenance:** the momentum-decomposition literature finds the predictive content
  concentrated **intraday**, with overnight returns largely explainable by news
  ([scholar](https://scholar.google.com/scholar?q=overnight+intraday+return+decomposition+momentum+predictability)).
- **Fit:** the repo has the pieces (`get_gap_type`, pre-market liquidity, pre-open
  RVOL, opening-range reads) but no *statistical* split of a name's returns into the
  two legs. That split closes a real loop for a dip buyer: whether a dip is being
  driven by overnight repricing (news-driven, gap risk, the thing an ATR stop is
  least able to protect against) or by intraday selling (the mean-reversion case the
  strategy is written for). It also gives the gap tools an empirical baseline per
  name instead of a narrative.
- **Consumer:** `strategies/market_session.py` (decomposition per name),
  market-analyst toolset, and a factor row for the swing overlay.
- **Data:** OHLCV with opens — note the engine now returns `opens` from the vendor
  chain (`_fetch_ohlcv`), which this item depends on. **Failure mode:** daily-bar
  decomposition cannot separate news from noise; label it as a decomposition, never
  as a cause.

### N9 — Bayesian online changepoint detection (optional complement to CUSUM)

Run-length posterior over $r_t$, updated per bar; alarm when the zero-run probability
spikes. Provenance: Adams & MacKay, [arXiv:0710.3742](https://arxiv.org/abs/0710.3742).

- **Fit:** CUSUM/EWMA **already landed** (`get_shift_detection`) and covers the
  frequentist small-shift case. BOCPD adds a *calibrated changepoint probability*
  and an explicit run-length, which is the right shape for the falling-knife question
  ("has the mean-reverting process just been replaced?") and for resetting
  window-based statistics (Hurst/VR/half-life) after a break.
- **Consumer:** `strategies/regime.py`, `strategies/knife_guard.py`.
- **Data:** OHLCV. **Status:** lowest priority of the list precisely because CUSUM
  exists; adopt only if a decision needs the probability rather than a signal flag.

---

## 3. Explicitly excluded (present, already planned, or evidence-weak)

| Candidate | Why excluded |
| --- | --- |
| Variance ratio, CUSUM/EWMA, permutation entropy, Ohlson/Zmijewski, Dechow–Dichev, Taylor rule, MAX/IVOL, Cornish–Fisher, Kappa/LPM, Burke/Martin/Pain, gain-to-pain, ruin/optimal-f, Almgren–Chriss, TWAP/VWAP/POV, vol-target scale, square-root impact, Hurst/half-life, PSR/DSR/PBO/CPCV | **already implemented** — verified at the definition site (see §1) |
| Kendall τ + t-copula tail dependence | already **planned** in round 1 (C4) and sketched in `design_quantlib_lean_enhancements.md`; adopted here only as the scenario input to N5 |
| Triple-barrier / meta-labeling (López de Prado) | the exits/barrier layer and the calibration+agreement gates already implement the *behaviour*; `design_hummingbot_integration.md` records that only the accounting discipline is worth adopting |
| 52-week-high proximity (George–Hwang) | **partially present** — the screener already computes `hi52_dist` (`scripts/value_screener.py`) and the vendors expose `high_52w`/`low_52w`; no new module needed, and the swing shelf rules already use the anchor |
| Turn-of-month / day-of-week seasonality | round-1 caveat stands and is *stronger* now: recent work reports the effect largely vanishing after 2001 once costs and data-mining corrections are applied |
| Implied-volatility skew as a standalone cross-sectional factor | 2025 evidence indicates most apparent predictability is confounded by stock borrow fees; the **variance risk premium** — which the repo already computes — is the more robust implied measure |
| Harvey–Liu t-haircut (round-1 D2) | DSR/PBO landed independently; the haircut is a reporting nicety, not a mechanism |
| CPPI (round-1 H2) | the drawdown gate and tranche risk already bound the downside; no named consumer |

---

## 4. Priority and the binding constraint

The evidence in this sweep points at a non-formula conclusion worth recording:
**the constraint on this project is validation discipline, not formula coverage.**
The library already has CPCV, DSR, PBO, purged splits, a purity gate and
calibration; the highest-value additions are therefore the ones that *feed or
sharpen* that machinery (N2 bands, N7 SPA, N5 sizing-under-the-budget) rather than
new indicator families.

Suggested order (detail in the implementation plan):

1. **N1** spread estimators — small, OHLCV-only, closes a real cost blind spot on
   names with no quotes, and calibrates a tool that already exists.
2. **N5** minimum-CVaR/CDaR sizing — the largest structural gap (measure-and-gate
   today, no solve), and it upgrades the existing governor rather than adding a
   parallel path.
3. **N2** conformal bands — gives the verifier a defensible tolerance; needs the
   historical model-vs-realized pairs the run store already holds.
4. **N3+N4** GP/A and NOA — small, additive, statements already parsed.
5. **N8** overnight/intraday decomposition — small, depends on `opens` (landed).
6. **N6** LM tone + readability + divergence — medium, the LLM-native differentiator,
   needs a dictionary and a text source decision.
7. **N7** Reality Check/SPA — small, lands with the next `alpha_zoo` bench extension.
8. **N9** BOCPD — optional, only if a consumer needs a probability not a flag.
