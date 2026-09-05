# Sector Rotation — Reference & Design

Status: **reference / design doc.** Distilled (2026-09-05) from two
LLM-generated specs that previously sat in this folder — `sector_calc.md`
(1,520 lines: the 100-point multi-factor sector score) and
`sector_instruction.md` (773 lines: the staged-pipeline correction). Both
are **deleted** after this distillation; this is the single surviving
source. No code changes.

---

## 1. The one-paragraph takeaway

The two source specs describe a 12-ETF (**XLK, SOXX, XLC, XLY, XLP, XLE,
XLF, XLV, XLI, XLB, XLRE, XLU**) sector-rotation system and make one point
each. `sector_instruction`: stage the pipeline — **regime is a gate, not a
factor**; sector ranking is momentum/RS/trend/risk-led; valuation belongs at
the stock layer, not the sector layer; entry timing is separate from
selection; and score must be separated from signal, or "everything becomes
Hold". `sector_calc`: the concrete 8-factor 100-point score
(momentum/RS/trend/risk/breadth/valuation/flow/fundamentals at
25/15/15/15/10/10/5/5), cross-sectional percentile normalization, and the
grade bands + regime cap. Both independently validate the fork's existing
architecture — regime gate, momentum-based sector rank, advisory
computed reads, deterministic backtest — and their genuinely new ideas are
**constituent breadth**, the **equal-weight vs cap-weight leadership ratio**
(SOXX concentration), and **two-level universe** (sectors → industries).

## 2. Where it maps onto the existing repo (validated)

| Spec stage | Existing repo machinery | Verdict |
| --- | --- | --- |
| Market regime gate (SPY trend / SMA200 slope / RV / breadth / VIX) | `strategies/regime.py` + `regime_state.py` (incl. HMM axis) + benchmark closes (`benchmark_ticker`, default SPY); `_benchmark_closes` in analysis_tools | already adopted — the gate exists |
| Sector ranking (11-12 SPDR groups) | `strategies/sector_rank.py` (`SPDR_SECTORS` 11 XL* groups, `_momentum` 1m/3m windows, `rank_sectors`, `sector_standing` top3/tracking/unknown) + `get_sector_rank` tool (market analyst) | **already exists — momentum-only today; the multi-factor extension is the gap** |
| Cross-sectional percentile normalization | `cross_section.py` + composite-rank flowing into the analysis | already adopted |
| Score ≠ signal, advisory grading | computed-tool discipline ("Use before any X claim", n/a never fabricated), risk governor PASS/WARN/REJECT | already adopted |
| Backtest validation of any strategy claim | `evaluate.py` (Sharpe/Sortino/Calmar/PSR/IC/decay, purged CPCV + PBO, benchmark hierarchy, with/without-cost) | already adopted |
| Industry level (SOXX/IGV/HACK/CLOU inside a sector) | no equivalent — sector rank is flat | **new** (P2) |
| Constituent breadth (SOXX 24/30 above MA50) | no per-constituent fetch path (screener OHLCV fetch exists per ticker) | **new** (P3; heavy) |
| EW vs CW leadership ratio | no equal-weight recomputation anywhere | **new** (P3; heavy) |

## 3. The architecture: three questions, one pipeline

Do NOT put everything into one giant Buy score — that is the documented
source of "too many Hold/Underweight, few actionable Buys". Ask three
different questions:

**Q1 — Where should I invest?** Market → Sector → Industry.
Factor set: regime + momentum + relative strength + trend + risk (breadth).
**Q2 — What should I buy?** Stock selection.
Factor set: growth + earnings revisions + quality + valuation + technical
strength.
**Q3 — How should I trade it?** Entry → sizing → portfolio risk → execution.
Factor set: entry setup (RSI/MACD/BB/ATR/volume/breakout), position size
(risk budget / risk-per-share or ATR), portfolio concentration
(correlation, covariance matrix), execution (liquidity/spread/VWAP/
participation — NOT part of the sector score).

```
MARKET REGIME (gate) → SECTOR RANK → INDUSTRY RANK → STOCK SELECT →
ENTRY TRIGGER → POSITION SIZE → PORTFOLIO RISK → EXECUTION/EXIT
```

### 3.1 Regime is a gate, not a factor

Classify SPY: `SPY > SMA200` and rising slope → **BULL**; below and falling →
**BEAR**; else transitional. Plus a volatility regime (RV20 percentile).
Cap the sector grade by regime — Bull allows Overweight, Neutral caps at
Moderate Overweight, Bear caps at Neutral, Crisis = capital preservation.
A sector score of 91 means different things in each.

The fork already implements this shape (`regime_state` feeds the risk
governor); the spec's contribution is the *explicit cap table* (see §5).

### 3.2 Two-level universe (conflict resolved)

The source specs contradict themselves: rank all 12 (XLK **and** SOXX) in
one pool, then later admit XLK is the GICS sector while SOXX is a strategic
industry. **Resolved: never rank them in the same pool.** Level 1 = the 11
SPDR sectors (already in `sector_rank.SPDR_SECTORS`, optionally + XLC, =
12); Level 2 = industries inside the top sectors (SOXX, IGV, HACK, CLOU…).
This also avoids double-counting semiconductor exposure when XLK and SOXX
both rank highly.

## 4. The sector score — reconciled weights

The two specs disagree on valuation weight (instruction: "don't give it 10%
automatically"; calc: 10%). **Reconciled position: for tactical price-based
rotation, valuation is secondary at the sector layer and primary at the
stock layer.** Two sanctioned variants:

**Variant A — price rotation (default, matches the fork's momentum-first
sector rank):**

| Factor | Weight | Components |
| --- | --- | --- |
| Momentum | 25% | 21d 5% · 63d 30% · 126d 30% · 252d 25% (percentile-normalized) · acceleration 10% |
| Relative strength | 15% | percentile of RSR(n) vs SPY (21d 10 / 63d 30 / 126d 35 / 252d 15) · RS accel 10% |
| Trend | 15% | P/SMA20·50·200, MA alignment (+1 per condition), MA slope, MACD |
| Risk-adjusted | 15% | Sharpe, Sortino, MDD, downside beta, volatility |
| Breadth | 10% | % constituents > MA20/50/200, A/D line |
| Valuation | 10% | sector-relative P/E, fwd P/E, EV/EBITDA, P/B, P/S (z vs sector universe) |
| Flow/volume | 5% | volume ratio, dollar volume, OBV, MFI |
| Fundamentals | 5% | EPS growth, revenue growth, EPS revisions, margin trend |

Sum = 100. **Variant B — momentum-heavy** (when breadth/valuation data is
unavailable): move Breadth+Value+Fundamental weight into
Momentum/RS/Trend. Marked "advisory — pick per data availability".

**Key discipline: normalize every factor cross-sectionally (percentile
rank, `100*(rank-1)/(N-1)`) — never sum raw values.** Z-scores (50+10Z,
clipped 0-100) are a valid alternative; percentile is preferred for
outlier robustness. This matches `cross_section.py` house style.

## 5. Score ≠ signal (the Hold-heavy fix)

**Score** = relative attractiveness (0-100). **Signal** = decision from
(score, regime, momentum-state, risk-state):

| Score | Grade |
| --- | --- |
| 90-100 | Strong Overweight |
| 80-89 | Overweight |
| 70-79 | Moderate Overweight |
| 60-69 | Slight Overweight |
| 45-59 | Neutral |
| 35-44 | Slight Underweight |
| 25-34 | Underweight |
| 10-24 | Strong Underweight |
| 0-9 | Avoid |

Regime cap (from §3.1) is applied to the grade, not the score — the score
stays comparable across regimes. Example: Score 91 + BULL/ACCELERATING/
NORMAL → Strong Overweight; the same 91 + BEAR/DECELERATING/EXTREME →
Hold / no new entry.

## 6. Genuinely new additions worth keeping

1. **Constituent breadth** — rank the ETF is not enough; breadth =
   fraction of constituents above their MAs (SOXX 24/30 = 80% = healthy vs
   an NVDA-only rally). Data-heavy (see §7).
2. **EW-vs-CW leadership ratio** — cap-weighted sector ETF / equal-weight
   reconstruction of the same constituents. Cap >> EW = concentration in a
   few mega-caps (SOXX). Novel and cheap conceptually; data-heavy to
   compute.
3. **Accelerations** — momentum accel (`R63 - 0.5*R126`), trend accel
   (`Slope50,t - Slope50,t-20`), RS accel (`RSR63 - 0.5*RSR126`) — catch
   "emerging leadership" before the long trend confirms. Cheap on existing
   OHLCV (P1-eligible).
4. **Score≠signal framing** (§5) — the explicit answer to the
   Hold-overweight problem.
5. **RSI healthy-momentum scoring** (RSI 60-70 = 100, ≥80 = 40) — fine as a
   *heuristic table*, house-styled to advisory (never a gate).

## 7. Data feasibility: factor → source

| Factor | Sourceable today? | Notes |
| --- | --- | --- |
| Regime (SPY trend/RV) | **Yes** | benchmark closes (SPY) exist; RV20 computable in-house; VIX not in `volatility_models` → use SPY RV20 (n/a honest) |
| Sector momentum/RS/trend/risk | **Yes** | OHLCV via the vendor chain for 11-12 ETFs; benchmark closes for RSR — reuses `_ohlcv`/screener fetch |
| Accelerations | **Yes** | same series |
| Valuation (sector-relative P/E, fwd P/E) | **Partial → n/a** | ETF-level fundamentals limited by providers; house rule: render n/a, never fabricate |
| Constituent breadth | **Heavy** | ~500 tickers × 250d via the screener OHLCV fetch; needs a cache; P3 |
| EW/CW ratio | **Heavy** | requires the same constituent set; P3 |
| Flow (OBV/MFI/dollar vol) | **Yes** | from OHLCV (`volumes` present in the existing fetch shape) |
| Fundamentals (rev/eps/margin at sector level) | **Partial → n/a** | stock-layer only today |

## 8. Non-goals

- **"Expected return / risk score"** (§43 of calc — a made-up weighted
  `E[R]`/vol) — rejected outright; `evaluate.py` + purged CPCV/PBO is the
  repo's method for any forward-looking claim.
- **Execution layer** (VWAP/TWAP/participation/max-slippage, position
  sizing for live portfolios) — out of scope by the no-execution /
  advisory-only mandate; TradingExecution is the phase-gated successor.
- **A hard RSI-score table as a gate** — advisory heuristic only.
- **The full 8-factor build as one phase** — phased below, each gated.

## 9. Phases (advisory, default-off)

1. **P1 — Multi-factor sector rank (extends `sector_rank.py`)** — add
   RS-vs-benchmark, trend (P/SMA), risk-adjusted (Sharpe/MDD on
   percentile), and momentum acceleration to the existing momentum-only
   rank; keep `rank_sectors`/`sector_standing` output shape; add an
   `acceleration` column to the read. Reuses benchmark closes + the
   11-12 ETF OHLCV. Tests: synthetic closes → correct order, None-safe,
   min-bars guard.
2. **P2 — Two-level industry rank** — `sector_rank.py` industry layer
   (SOXX/IGV/HACK/CLOU…), ranked only inside their parent sector; renders
   "Technology bullish, semiconductors strongest subgroup". Tests: parent
   gating, no cross-pool ranking.
3. **P3 — Breadth + EW/CW** — per-constituent close fetch (cached; reuse
   the screener OHLCV fetch), breadth50/200 + EW/CW leadership ratio into
   the read. Tests: ratio sign/scale on synthetic constituents.
4. **Valuation stays n/a** unless an ETF-level fundamental source lands;
   then sector-relative z only, house-styled.

## 10. Honest limits

- **Universe choice is opinion, not signal**: the 11-12 X* set is a fixed
  US sector menu; the fork's `sector_rank.py` already carries this.
- **Breadth/EW-CW are fetch-heavy**: ~500 daily pulls; only worth P3 with a
  disk cache (the vendor-cache / trading-calendar pattern).
- **No regime-tuning of weights yet**: the spec suggests shifting weight to
  Sortino/drawdown/downside-beta in high-vol regimes — documented as a
  future knob, not built (regime_state is the hook).
- **Everything is advisory**: no behavior change while phases are off; the
  fork's PIT / sentinel / n/a-not-fabricated rules apply to every factor.
- **Unvalidated claim**: "staging fixes Hold-heavy behavior" is the specs'
  hypothesis — P1's tests + evaluate.py are the actual check.

## 11. Validation & sequencing

Per phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs true, trading_web mirrored where a read gains a
field. No behavior change while the phase config keys are off (defaults
off). P1 is self-contained (extends the existing sector read); P2 builds on
P1's two-level framing; P3 depends on the fetch cache. Source of truth for
universe/weights: **this file** — the two deleted specs are superseded.