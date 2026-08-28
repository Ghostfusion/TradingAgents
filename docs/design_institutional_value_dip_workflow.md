# Design: Institutional Workflow for the Value-Dip + Swing Style

**Status:** design / research (no code).
**Goal:** compare this fork's value-dip + swing workflow against how institutional
investors and professional desks actually run similar strategies, and propose
concrete, module-mapped enhancements.

This is a *research-to-design* document. Sources are institutional value-investing
frameworks (CFA-style desk funnels, AQR-style systematic mean reversion), professional
swing-trade management practice, Minervini's VCP/SEPA process, desk risk policies,
execution/TCA practice, event-risk conventions, and systematic strategy-evaluation
(e.g. walk-forward, parameter drift, alpha decay). Nothing here is implemented yet.

---

## 1. Executive summary

Institutions do **not** run "buy the dip" as a single signal. They run a **funnel with
hard gates and layered controls**:

1. Screen a **liquid universe** for cheap-but-high-quality.
2. **Triage** out value traps by asking *why it is cheap* (earnings quality, leverage,
   accruals, moat).
3. Require an **identifiable catalyst or improving fundamentals** (re-rating evidence),
   because cheap stays cheap without one.
4. **Regime-gate the entry**: mean reversion is only allowed when volatility is
   contained, the market is not in a fresh/strong move, and no catalyst-driven gap is
   in flight. Trend-following and mean reversion are separate modules selected by regime.
5. Enter **with confirmation**, not on the first oversold print; trade in **pre-planned
   tranches** sized from a **fixed total-risk budget** with a **single unified stop**;
   the stop is mandatory and never widened.
6. **Manage the trade off a written plan**: tiered partial profits at structure/R,
   breakeven only after confirmation, one trailing method, and a journal reviewed on a
   cadence with **plan-adherence** tracked, not just P&L.
7. **Layered risk limits**: per-trade, daily-loss, portfolio-drawdown (high-water-mark),
   concentration/sector caps, and a risk-budget per sleeve.
8. **Execution is a cost center**: decisions are benchmarked to **arrival price**
   (implementation shortfall), limit/passive orders are tracked for fill rate and queue
   cost, illiquid names are sized down.
9. **Event risk is pre-sized**: shrink/avoid holding through earnings, size by the
   **implied move**, never buy naked into a catalyst you cannot win.
10. **Evaluate like a quant**: walk-forward + out-of-sample holdout, realistic costs,
    parameter-drift and alpha-decay monitoring, attribution by sleeve, review cadence.

**What this project already does well** (references included):

| Institutional practice | Project equivalent | Status |
| --- | --- | --- |
| Funnel: screen cheap+quality | `value_screener` (EY/EV-EBIT/F/M/Z, ROE, growth gates, sector rank, revisions, inst-accum); `pipeline.py` screen→rank→top-N | strong |
| Value-trap triage / declining fundamentals | `decline_driver_check` (clean/caution/**structural**), earnings-quality (accruals/Beneish/Piotroski), `balance_sheet_health` | strong; structural ⇒ **reject** value-dip |
| Fixed-total-risk tranche sizing, single unified stop | `tranche_plan` / `tranche_risk_read`: risk-first sizing, weighted entry, composite stop, `peak_deployed_pct`/`capital_at_risk_pct` fold into the governor | strong (better than most retail docs) |
| Catalyst / event risk | B1 `catalyst` overlay (scale + verdict + hard block), `expected_move` (implied), contract takes `implied_move_pct` | strong |
| Trade tiers, BE, trail | `scaleout_plan` (50% @ T1 → BE), 2R/3R, `trail_ema`, `chandelier_exit` (true highs) | good |
| Mandatory stop policy | composite stop always computed; `pre_market` REJECTs gap-through-stop | partial (no explicit *policy* prohibition on widening) |
| Overnight / pre-open re-check | `pre_market_review` CONFIRM/REVISE/REJECT + paper ledger + `nightly_review` | ahead of most public frameworks |
| Trade journal / plan adherence | memory log (pending→resolved+alpha), `strategy_ledger`, `action_report` conditions | good basis |
| Walk-forward / overfitting control | `evaluate_config_gate.py` (walk-forward + PBO on `--returns`) | exists, under-wired |
| No-fabrication / compute-as-tools | every strategy function is a deterministic tool; explicit "unavailable" | unique strength |

**What is missing or weak** (the gap this design closes):

1. **No regime switch.** Mean reversion and trend are blended; the regime row is
   reported but not an entry gate. Institutions block counter-trend fades in
   high-vol/strong-move/transition regimes.
2. **No catalyst-first value requirement.** Value-dip can pass without any re-rating
   evidence; institutional practice asks *what closes the gap* (acceleration/revision/
   accumulation) before entry.
3. **No explicit daily-loss / high-water-mark risk gate.** The governor checks
   per-trade and portfolio CVaR/drawdown snapshot, but there is no **daily loss
   budget → auto-risk-reduction** and no **drawdown-from-high-water-mark** de-risking
   (soft/hard tiers).
4. **Trade-management plan is implicit, not pre-written per trade.** Exits exist as
   functions; there is no per-position "plan card" (entry, tier levels, BE rule,
   trailing method, invalidation, journal) that the analyst/trader/reviewer all read,
   and no plan-adherence score.
5. **Breakeven timing can be too early.** Current BE is a fixed ATR cushion; practice
   says move to BE only after confirmation (1R+ or a structure higher-low), otherwise
   normal pullbacks stop winners early.
6. **Execution is not measured.** Decisions are benchmarked vs close/last, not
   **arrival price**; no fill log, no slippage/TCA, no limit-order fill tracking; the
   paper ledger stores review gap but not execution quality.
7. **Turnover control is weak.** `rebalance_due` exists but nothing penalizes or
   caps churn (min-holding, per-period trade budget, tax/basis awareness).
8. **Strategy evaluation is not operational.** Walk-forward exists but there is no
   **parameter-drift monitor**, no **alpha-decay cadence**, no **per-sleeve (value-dip
   vs swing vs vcp) attribution**, no live-vs-backtest tracking.

---

## 2. Research synthesis — the institutional workflow (what the web says)

### 2.1 The value desk funnel (CFA-style)
1. **Universe screen** — cheap + quality + liquidity + sector filters.
2. **Triage** — eliminate value traps (accounting quality, leverage, broken stories).
3. **Qualitative overlay** — moat, management, industry, earnings durability.
4. **Fundamental research** — normalized earnings, scenarios (base/bull/bear).
5. **Valuation** — DCF/EPV/multiples with a **margin of safety (20–50%)**.
6. **Catalyst analysis** — what re-rates it (operational inflection, buyback, spin,
   relative convergence).
7. **Position sizing** — conviction × downside × correlation × risk budget.
8. **Monitoring** — thesis KPI dashboard, exit triggers, watchlist.

### 2.2 Systematic mean reversion (AQR-style)
- Build it as a **liquid, large-cap universe**; effect is cleaner and more tradable.
- **Oversold is a condition, not an entry** — wait for confirmation (cross-back,
  divergence, support hold, failure swing).
- **Blend signals** (reversal + relative value + short-horizon) rather than trade
  reversal alone.
- Scale by **risk and liquidity**, not equal dollars; **exit systematically** as the
  rebound normalizes — never "feels expensive".

### 2.3 Scaling in / tranches
- **Define total risk first**, then size tranches so the fully built position stays
  inside that budget.
- **2–4 pre-planned tranches**; later tranches **confirmation-triggered** (retest,
  higher low, trigger candle), not emotional adds while falling.
- One **unified invalidation / stop** for the whole thesis; **averaging down only if
  the thesis is intact** and concentration is within limits.

### 2.4 Risk policy (desk-level)
- **Per-trade max loss** (stop/exit rule), **daily loss limit**, **portfolio
  drawdown control** (high-water-mark, soft+hard gates), **desk limits** (VaR,
  position, inventory) with daily reporting and breach follow-up, reviewed
  periodically.
- **Stop is mandatory only if policy says so** — best practice: it is policy, and the
  stop is **never widened**.

### 2.5 Execution / TCA
- Benchmark = **arrival/decision price**; measure **implementation shortfall**
  (explicit + impact + timing + opportunity on unfilled).
- Limit orders: track **fill rate, queue position, unexecuted residual**.
- Participation algo / POV to bound impact; illiquid names sized down.

### 2.6 Event risk
- **Size down or avoid holding naked through earnings**; size by the **implied move**;
  after the print, IV crush means an event trade must beat the priced move.

### 2.7 Regime filter (trend vs mean reversion)
- **Volatility regime first, direction second.**
  - Low vol + range-bound + no catalyst → allow mean reversion.
  - High vol + directional trend → allow trend, **block fades**.
  - Transition/chop → reduce or stand aside.
- Never fade a **fresh/strong move** or a **catalyst-driven gap**.

### 2.8 Trade management (professional swing)
- Written plan before entry: **risk %, invalidations, tiered partials at 1R/2R-3R or
  structure, BE after confirmation (1R+ or higher low), one trailing method (ATR
  1.5–2x or structure), never widen the stop**, journal with **plan-adherence score**,
  weekly review.

### 2.9 Minervini VCP/SEPA (the closest public "process")
- Trend Template first (price>50/150/200, 50>150>200, 200 rising, RS>70, near highs).
- **Fundamental quality before pattern**: EPS acceleration, revenue, margins,
  institutional accumulation.
- VCP: progressively smaller contractions, volume dry-up, then **pivot breakout on
  volume**; stop ~7–8% below entry / below last contraction low.

### 2.10 Strategy evaluation / decay
- Walk-forward (re-optimize in-sample, test next window), **untouched OOS holdout**,
  realistic costs, **parameter-drift monitor**, **performance attribution**,
  **alpha-decay review cadence** (fixed trade count / rebalance / underperformance
  trigger).

---

## 3. Comparison: institutional practice → this project (detailed)

| # | Institutional practice | This project | Gap / note |
|---|---|---|---|
| 1 | Liquid-universe screen first | `eodhd-us` default; ILLIQ/FltTurn columns; `--min-avg-vol`/`--min-mcap` gates | ✅ mostly covered |
| 2 | Triage: why is it cheap (accounting quality) | `decline_driver_check` structural ⇒ reject; accruals/Beneish/Piotroski/Altman rows; `balance_sheet_health` | ✅ strong |
| 3 | Qualitative overlay (moat/management) | Not automated (no moat/management signal); analyst LLMs can reason from tools but no hard gate | ⚠️ partial — see S4 |
| 4 | Valuation + margin of safety 20–50% | DCF (`get_dcf_valuation`), value floors (Graham/NCAV/EPV), `value_floor` row (MoS≥20% **or** FCFY≥6%) | ✅ |
| 5 | Catalyst-first / re-rating evidence | `--revision`, `--inst-accum`, growth gates, `get_earnings_surprise`; but **not required** for value-dip | ⚠️ see S5 |
| 6 | Regime switch (MR vs trend) | `regime` label + `vol_pct` computed; `trend` row opt-in (`require_trend`); no entry-gate by regime | ❌ see S1 |
| 7 | Confirmation entry, not first oversold | VDU ladder (volume dry-up → divergence/higher-low → trigger candle RVOL≥1.3); technical_entry row RSI+%b | ✅ |
| 8 | Risk-first tranches, single stop | `tranche_plan` (fixed risk budget, weighted entry, composite stop, capital-at-risk loop), `peak_deployed_pct` fold | ✅ (ahead) |
| 9 | Daily loss limit / HWM de-risk | `risk_max_drawdown_pct` snapshot + book drawdown gate; **no daily-loss budget, no high-water-mark de-risking** | ❌ see S3 |
| 10 | Mandatory stop, never widened | Stops always computed; `tranche`/contract/risk governor; `action_report`/`pre_market` reference them | ⚠️ make it an explicit policy artifact (S4, S7) |
| 11 | Trade plan card + tiers + BE-after-confirm + one trail | `scaleout_plan` (50% @T1→BE), 2R/3R, `trail_ema`, chandelier; BE is fixed-A TR cushion | ⚠️ BE timing (S6), plan card (S7) |
| 12 | Structure-based targets | `targets_rr` fixed 1.8R/3.0R; no nearest-swing-high option | ⚠️ S8 |
| 13 | Execution benchmark = arrival, TCA | Decision recorded at close/last; no fill log, no slippage vs arrival, no fill-rate tracking | ❌ see S9 |
| 14 | Turnover control / tax / basis | `rebalance_due` (30d hint) only | ❌ see S10 |
| 15 | Walk-forward + OOS + drift + decay | `evaluate_config_gate` (walk-forward+PBO); `strategy_quality_report` (net-of-cost Sharpe/DD); `risk_report`; `orderflow_evaluate` | ⚠️ missing drift/decay/attribution (S11) |
| 16 | Review cadence + plan adherence | memory log resolves alpha; `pre_market_ledger` track record; no plan-adherence score | ⚠️ S7/S11 |
| 17 | Per-sleeve attribution | none (all decisions share one ref ledger) | ❌ S11 |

---

## 4. Design proposals (phased, module-mapped, no code yet)

### Phase A — regime & catalyst gating (closest to institutional identity)
**A1. Regime switch for entries (`strategies/regime.py`, `value_dip.py`, screener)**
- Compute a **tradability regime** at scan time: `vol_pct` (have), 200-SMA trend
  direction (have), price vs 200-SMA distance, and ATR percentile.
- New row `regime_gate` for `value_dip_setup`: allow mean reversion only when
  `vol_pct <= threshold` (config, default ~0.8) **and** not in a fast-downtrend
  (e.g. price below falling 200-SMA by > 8% **and** 50-SMA below 200-SMA, matching the
  "no falling knives in high-vol" finding), **and** no catalyst window open
  (reuse `catalyst_hard_block_days` + `implied_move_pct`).
- In high-vol/transition regime: keep the scan but **demote** entries (row = `blocked`,
  candidate cannot go long) or **size-half** (scale multiplier 0.5) — config-selected.
- Wire the same gate into `pipeline.py`'s screen (skip or mark candidates that fail
  regime when `--scan value-dip`).

**A2. Catalyst-first value (`value_dip.py`, screener gates)**
- New `re_rating` row: pass if any of (latest EPS surprise > 0 **and** positive trend),
  `--revision`>0, `--inst-accum`, or forward-PEG < config (default 1.0). Reported
  always; **hard gate in `strict` mode** (`value_dip_require_catalyst=true` config).
- Uses existing signals only (`get_earnings_surprise`, `--revision`, `--inst-accum`,
  forwardPEG from `get_ratios`) — no new vendors.

### Phase B — risk & trade-management policy
**B1. Daily-loss + high-water-mark gate (`strategies/risk_governor.py`, memory)**
- Track per-day realized loss from the memory/ledger; `risk_daily_loss_budget_pct`
  (config, default e.g. 0.02): breach ⇒ governor returns `WARN`/`REJECT` and a new
  `de_risk=True` (like `risk_halt`) blocks new entries until next session.
- High-water-mark: `drawdown_from_hwm` row; soft tier (`>0.10` ⇒ size×0.5), hard tier
  (`>0.20` ⇒ REJECT new risk) — config keys `risk_hwm_soft_pct` / `risk_hwm_hard_pct`.

**B2. Trade plan card + builder (`strategies/trade_plan.py` — new pure module)**
- One function `build_trade_plan(...)` that emits a single text/markdown plan from the
  existing pieces: setup rows, tranche levels + shares, composite stop, tier targets
  (structure or R), BE rule (see B3), trailing method, invalidation, and a
  **plan-adherence checklist**.
- Expose as `get_trade_plan` tool bound to the trader/PM node; render into
  `3_trading/trader.md` and the web Value-Tools screen; the pre-market reviewer reads
  the same plan (already anchored on `tranche_plan`).
- `action_report.py` gains a plan-adherence pass: was the BE move/target/stop followed
  per the plan card? (`adherence: MET/NOT_MET`), feeding the journal score.

**B3. BE-after-confirmation (`strategies/exits.py`, `swing.py`)**
- Add `breakeven_trigger: "atr" | "r" | "structure"` (config).
  - `atr` = current behaviour (entry + cushion×ATR).
  - `r` = after `stop_to_breakeven_r` 1R (have).
  - `structure` = after a higher-low (reuse `higher_low_structure`) **or** 1R,
    whichever comes later — matches "don't move BE too early".
- Default recommendation: `structure` (matches practice; the current fixed-ATR BE is
  too early for a retestable dip setup).

**B4. Explicit stop policy artifact**
- `tranche_plan`/`trade_plan` already emit a single composite stop; add a
  `stop_policy` engine check: reject/flag any plan where a later tranche or LLM
  modifies the stop wider than the composite (`stop_never_widen=True`), surfaced in
  the trader prompt and `action_report` (a NOT_MET when a stop was widened).

### Phase C — execution & turnover measurement
**C1. Arrival-benchmark ledger (`strategies/pre_market.py`, `memory.py`)**
- When a decision stores an entry tranche level, also store the **arrival price**
  (the vendor quote at decision time) and later the **fill proxy** (the open or a
  limit level). Extend `pre_market_ledger` rows with `arrival`, `fill_estimate`,
  `slippage_bps = (fill - arrival)/arrival`.
- `strategy_quality_report.py` gains an **execution block**: avg slippage vs arrival,
  fill-rate estimate, per-sleeve cost — the TCA analogue (full IS/queue metrics are
  out of scope for an analysis-only repo; state so).

**C2. Turnover control (`strategies/portfolio.py`, `journal.py`)**
- Config `min_holding_days` (default e.g. 5) and `max_trades_per_period`
  (default e.g. 4/week): `rebalance_due`/journal counts churn; `get_allocation`
  flags names violating min-hold on re-entry; screener `--alloc` already exists — add
  a turnover note to the allocation block.

### Phase D — evaluation ops
**D1. Sleeve-tagged ledgers (`memory.py`, `reflection.py`)**
- Tag each decision with its **sleeve** (`value-dip | swing | vcp | momentum | hold`)
  from the scan/entry used; `strategy_quality_report` and `evaluate_config_gate`
  filter by sleeve → **per-style Sharpe/hit-rate/alpha** (attribution).

**D2. Parameter-drift + alpha-decay monitor (`scripts/strategy_quality_report.py`)**
- Weekly report compares live rolling hit-rate/Sharpe (4-wk) vs the walk-forward
  baseline; flag `DRIFT` when |live − baseline| > config threshold for 2 consecutive
  periods; **review cadence** default weekly, plus a trigger on underperformance.

### Phase E — education & UX (web)
- Value-Tools screen shows the new rows (`regime_gate`, `re_rating`, plan card,
  adherence, execution block) with plain-language hints; Pre-Market/Nightly show
  `drawdown_from_hwm`.

---

## 5. Proposed end-to-end workflow (after Phase A–C)

```
1. SCREEN (daily)        eodhd-us / movers universe, --scan value-dip all
                         rows: value_floor, quality(trap), re_rating, regime_gate,
                         technical entry, tranche risk, plan stop
2. TRIAGE                decline_driver != structural; earnings-quality clear;
                         balance_sheet pass; ILLIQ within bounds
3. REGIME GATE           vol_pct <= high-vol cap AND no fast downtrend AND no
                         catalyst window -> else BLOCKED / halved
4. CATALYST CHECK        re_rating evidence present (surprise>0 / revisions /
                         accumulation / PEG<1) -> hard in strict mode
5. PLAN CARD             build_trade_plan: tranches, unified stop, tiers (R or
                         structure), BE rule (structure), trailing method,
                         invalidation, adherence checklist
6. EXECUTE (paper)       arrival price recorded; tranches at levels; limit-order
                         note from ILLIQ; slippage vs arrival logged
7. MANAGE                BE after confirmation; partial at T1(50%);
                         trail remainder (EMA/chandelier); never widen stop
8. OVERNIGHT             pre_market_review: CONFIRM/REVISE/REJECT vs measured
                         delta; gap-through-stop => REJECT
9. REVIEW (daily/weekly) daily loss budget + HWM de-risk; journal adherence;
                         per-sleeve attribution; drift/alpha-decay flags
```

---

## 6. Suggested config surface (all new keys, gated off by default)

| Key | Default | Meaning |
| --- | --- | --- |
| `value_dip_require_catalyst` | `false` | strict: re-rating evidence required |
| `value_dip_regime_gate` | `false` | strict: block/halve on high-vol or fast-downtrend |
| `value_dip_regime_vol_cap` | `0.8` | vol_pct above this ⇒ blocked |
| `value_dip_regime_downtrend_band` | `0.08` | price below falling 200-SMA by > 8% ⇒ blocked |
| `value_dip_regime_halve` | `false` | instead of blocking, size ×0.5 |
| `risk_daily_loss_budget_pct` | `0.02` | daily realized-loss cap → de-risk |
| `risk_hwm_soft_pct` / `risk_hwm_hard_pct` | `0.10` / `0.20` | drawdown-from-HWM tiers |
| `breakeven_trigger` | `structure` | atr \| r \| structure |
| `stop_never_widen` | `true` | enforce in plan/action report |
| `min_holding_days` | `5` | turnover guard |
| `max_trades_per_period` | `4` | per-week churn cap |
| `sleeve_tag_enabled` | `false` | tag decisions for attribution |
| `drift_threshold` / `drift_periods` | `0.5` / `2` | alpha-decay monitor |

All new gating is **opt-in** (default false) so existing scans/runs keep their
behaviour; the machine stays deterministic and no-fabrication (each new row is a
pure function over existing tools).

---

## 7. Non-goals / risks

- **No real execution**: TCA here means *measuring* arrival-to-fill on the paper
  book; full algos (POV/TWAP), queue-position models and live order routing are out
  of scope.
- **No moat/management automation**: a qualitative layer can only be *prompted*, not
  computed; provide the `moat`/`management` checklist as report rows the LLM answers
  with tools, never as hard gates.
- **Overfitting new rows**: every new gate is added with a default-off flag and must
  pass the existing walk-forward (`evaluate_config_gate`) before being defaulted on;
  prefer fewer degrees of freedom (reuse existing signals).
- **Avoid double-counting catalyst risk**: `catalyst_hard_block_days`,
  `implied_move_pct`, and the new `regime_gate` all touch event risk — wire them as
  one composable `event_window` read, not three independent penalties.
- **BE too early is a real cost**: switching default to `structure` will stop some
  winners that the old cushion spared — this is the *intended* tradeoff (higher
  win-rate, smaller runners), and is why the key is config.

---

## 8. Definition of done

Per phase, when implemented (separate task, after approval):
- New pure functions + hermetic tests (`test_strategies_value_dip`,
  `test_strategies_risk_governor`, `test_strategies_exits`, `test_trade_plan`),
  all `py -3.12 -m pytest`, `ruff clean`.
- All new keys in `default_config.py` + `.env.example` + `docs/api_reference.md §1.1`.
- Ops docs updated (README News, CHANGELOG), and `trading_web` screens surfaced for
  the new rows where applicable.
- Walk-forward gate (`scripts/evaluate_config_gate.py`) green on the new defaults
  before any Phase A gate moves from opt-in to default.