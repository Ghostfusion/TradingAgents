# Sector Rotation Screen — Design

Status: **design doc (proposal — no code changed)**.
Source: `Strategies/sector_rotation.md` (731-line swing-rotation playbook) +
the adopted `Strategies/formulas/sector_rotation.md` (P1-P3/A1-A3 live in
`sector_rank.py` / `cycle_tilt.py`) + fresh deep web research (2026-09-06,
cited per claim).

---

## 1. The one-paragraph takeaway

Rotational markets are real but the profitable core is **not** macro
forecasting: the research consistently shows (a) cross-sectional stock
momentum is *largely industry momentum* (Moskowitz–Grinblatt), (b) sector
RS/momentum persistence is the best-supported rotation edge, and (c) the edge
is **cost-fragile** (turnover erodes or kills it — Korajczyk–Sadka 1.5%
round-trip zeroes momentum; UK 3×1 sector momentum = 37.8% costs vs 5.4% for
12×12). The 731-line doc's macro/VAR/OU/MS-AR machinery is over-engineered
for what the evidence supports. **Proposal: a separate, advisory
`get_sector_rotation_screen` screener — a sector-first pipeline (regime gate
→ RS/momentum sector rank → constituent breadth/cap-vs-equal-weight → stock
setup screens A/B inside the leaders) — built by *reusing* the existing
`sector_rank` / `cycle_tilt` / `regime_state` / screener fetch, not by
duplicating them, and validated against costs with `evaluate.py` before any
signal is trusted.**

## 2. What the web research supports (and does not)

| Claim (doc) | Evidence | Verdict |
| --- | --- | --- |
| Sector **RS/momentum persists** (rank by relative strength, not cheapness) | Moskowitz–Grinblatt 1999: industry momentum explains much of stock-momentum profit (~0.43%/mo → ~0.13%/mo industry-adjusted); strongest 1–6–12m, fades by 12m+. RRG JdK RS-Ratio/RS-Momentum persistence; "laggard catch-up trap" consistent with persistence | ✅ **core signal** |
| Business-cycle sector tilt (early=fin/discretionary/industrials; mid=tech/industrials/comm; late=energy/materials; recession=staples/utilities/health) | Multiple guides + cycle studies agree on the map | ✅ **but**: pure business-cycle rotation "no systematic sector performance… at best modest, disappears with mistiming or transaction costs" — a **tilt, never a gate** (`get_cycle_tilt` already this shape) |
| Sector momentum survives costs | Mixed: US GICS 2000–2025 top-3 monthly 11.3% vs 9.8% buy-hold SPY, Sharpe 0.72 vs 0.54; TSX60 median-performer quarterly 15.3% vs 10.35% (Sharpe 0.92 vs 0.62). Counter: turnover 83.7%/yr avg in a live momentum book; Korajczyk–Sadka profit → 0 at ~1.5–1.77% round-trip; UK 3×1 momentum costs 37.8% | ⚠️ **must validate after costs; cadence (monthly/quarterly) is a first-class dimension** |
| Market-bottom leadership: "first sector to stop falling leads the rally"; RS line new high before price breakout | Practitioner/MOSAIC-style + CANSLIM/Minervini tradition; **no rigorous study isolates the exact sequence** | ⚠️ **screen flag only, never a gate** |
| Breadth divergence: cap-weighted > equal-weight + weak %-above-MA = narrow fragile rally | Consistent across breadth literature; EWvs-CW read a genuine signal; %>200dMA regime gauge (>70% bull / <30% bear), most reliable long-run breadth measure | ✅ **screener dimension** (P2) |
| Cross-sectional dispersion as state variable (rotation regime) | Solnik et al.: dispersion ⇄ correlation inverse; dispersion forecasts vol/returns; regime-dependent | ✅ **P1 feature** (reuses regime_state + a computed dispersion series — NOT a full MS-AR) |
| High-tight base + volume contraction → breakout (Setup A) | Strong practitioner + semi-statistical support: volume contract ≤75% avg + ≥1.5–2× breakout volume filters false breakouts; prior uptrend 30–100%+ prerequisite | ✅ **stock-level screen** (P3) |
| Pullback to rising 20d EMA (Setup B) | Classic trend-continuation; **no peer-reviewed win rate for momentum-leader variant** (a ranging-market "EMA bounce" 52–55% is not comparable) | ⚠️ **screen flag; validate** |
| Heavy-volume sector breakdown below 20d EMA = distribution ("kill-switch") | IBD distribution-day cluster concept (≥0.2% down on higher volume, clustered 4–6 in a few weeks); 50-day-average-volume variant reasonable; probabilistic not guaranteed | ✅ **advisory overlay only** (never auto-sell — repo does not auto-execute) |
| VAR/Granger macro→sector lead-lag (10Y→Utilities-short / Regional-Banks-long) | Transmission is regim/requency-dependent, direction flips (yields Granger-cause oil; oil↔equity bidirectional varying by sample; stronger in crises) | ❌ **reject as screen rule** — keep `cycle_tilt` (PMI/spread/HY-OAS phase) as the only macro direction |
| OU cointegration sector-pair mean reversion (±2σ, XLE/XOM…) | A separate pairs-trading strategy (repo already has `get_pair_trade_signal`); adds no early-screen value | ❌ **keep out of the screener** |
| MS-AR 3-state Hamilton filter for dynamic vol targeting | Regime models fit well + detect breaks; **OOS gains vary**, weekly/monthly better than daily; repo has `regime_state` + HMM axis | ❌ **full filter is research-grade** — adopt only the *dispersion feature* feeding the existing regime read |
| ATR-buffer optimization (Type I/II, k*), dynamic sizing, ERC allocation | Sizing/execution discipline; the repo's no-execution mandate already defers it (§ formulas doc 8) | ❌ **out of scope** (note only) |

## 3. Where it maps onto the existing repo (reuse, don't rebuild)

| Need | Existing machinery | Verdict |
| --- | --- | --- |
| Market regime gate (SPY trend / SMA200 slope / RV / breadth / VIX) | `strategies/regime.py`, `regime_state.py`, `benchmark_closes` (default SPY) | reuse |
| Sector rank (11 SPDR + XLC, momentum 1m/3m + multifactor incl. RS-vs-SPY, trend, Sharpe/MDD, acceleration) + RRG quadrant + standing | `sector_rank.py` (`rank_sectors`, `rank_sectors_multifactor`, `rrg_quadrant`, `sector_standing`) + `get_sector_rank` (market analyst) | reuse — **this is the screener's sector layer already** |
| Business-cycle tilt | `cycle_tilt.py` + `get_cycle_tilt` | reuse as tilt (not gate) |
| Sector-ETF OHLCV | `yfinance_sector.py`, screener OHLCV fetch path | reuse |
| Stock OHLCV / fundamentals per constituent | screener fetch + FMP `get_company_profile` / `get_key_metrics_ttm` | reuse (cached for ~500 names) |
| Validation vs costs | `evaluate.py` (Sharpe/Sortino/CPCV/PBO, with/without-cost) | the only acceptable proof of any rotation edge |
| Score ≠ signal, advisory, None-safe | computed-tool discipline + risk governor | adopt identically |

## 4. Scope of the new screener

One new pipeline + one new tool. The existing `screen_equities` is a
single-name static screener (yfinance predefined queries) — this is a
**separate sector-first screener**, as requested, not an extension of it.

```
REGIME (SPY trend + dispersion) ─gate→ SECTOR RANK (RS/momentum, multifactor)
   → SECTOR SCREEN (top-3-5 leaders; pullback-divergence flags; breadth where
     constituents exist; cycle tilt context; RRG quadrant exit flags)
→ STOCK SCREEN inside leaders (Setup A high-tight shelf | Setup B first
  pullback to rising 20d EMA; trend architecture P>EMA20>SMA50>SMA200;
  ≥30d) sortable, capped at 3-6% above 20d EMA (no extended chase))
→ OVERLAY (kill-switch flags when a parent sector breaks its 20d EMA on
  ≥125% of its 50d volume; note-only, never auto-sell)
```

**Tool**: `get_sector_rotation_screen(...)` → market analyst, advisory,
default-off behind `enable_sector_rotation_screen` (matching
`enable_sector_multifactor` convention). Renders **screens** (ranked rows +
flags), not buy signals.

## 5. Signals and thresholds (screener spec)

### 5.1 Sector layer (reuses `rank_sectors_multifactor` + `rrg_quadrant`)
- Rank sectors (top 3–5 pass-through).
- **Pullback-divergence flag**: when SPY closes down 2+ sessions or undercuts
  a recent swing low, flag sectors closing green or holding above prior-day
  high → "rotation leaders" (practitioner evidence; flag only).
- **Exit flag**: RRG quadrant = Weakening (RS above 100, momentum below) →
  trim; Lagging → avoid (encodes the laggard trap: rank by RS, not cheapness).
- **Dispersion context line**: cross-sectional std of sector returns (trend
  up = rotation regime) — feeds the regime gate as a feature, not a filter.

### 5.2 Stock layer (inside the top 2–3 sectors; P3)
- Filters: market cap ≥ $2B, 20d avg vol ≥ 1.5M shares, liquidity.
- Trend architecture: `P > EMA20 > SMA50 > SMA200`.
- Relative outperformance: 20d perf vs sector ETF ≥ +2% (leaders, not
  beta-riders).
- **Setup A**: 5–15d tight shelf within 3–6% of the 52-week high, volume
  ≤ 75% of 20d avg, price has NOT yet cleared the shelf high (or cleared on
  ≥1.5× avg volume).
- **Setup B**: momentum leader retracing to its rising 20d EMA + reversal
  candle on the MA (hammer / bullish engulfing / inside-day up-break).
- No extended chase: drop candidates > 5% above their 20d EMA.

### 5.3 Breadth / concentration (P2)
- % constituents above MA50/MA200 per sector (breadth) — from the
  constituent cache.
- **EW-vs-CW leadership ratio**: equal-weight reconstruction of the same
  constituents vs the cap-weighted ETF; cap ≫ EW = narrow mega-cap rally
  (fragile). Rendered as a flag, never a law.

### 5.4 Overlay
- Sector ETF closes below its 20d EMA on volume ≥ 125% of its 50d average,
  or a 4+ distribution-days cluster → advisory kill-switch note for that
  sector ("tighten / no new entries here") — **note only**; the repo never
  auto-sells.

## 6. Data feasibility (free)

| Data | Free path | Risk |
| --- | --- | --- |
| 12 sector ETF OHLCV | yfinance via existing fetcher | fine (~12 series) |
| SPY benchmark | existing `benchmark_closes` | fine |
| Sector constituents | (a) **EODHD full-US symbol list** (major-exchange filtered, `get_exchange_symbols_eodhd`) bucket via `sector_group_of` (GICS + yfinance sub-industry aliases), capped per sector + budget + early-bail (built) or (b) State Street **SPY holdings XLS** / AmericanETP daily CSV (official-ish, free) or (b) curated universe + `yfinance info["sector"]` | (b) is **rate-limit fragile** (~2k–2.5k req/hr anecdotal cap; `YFRateLimitError`) → **disk-cache the membership + OHLCV** (the repo already has a vendor/trading-calendar cache pattern); fetch weekly, not per-run |
| Stock fundamentals (mkt cap, eps) | FMP (key present, 250 req/day free) | plan budget: ~50 universe rows × few calls, cached |
| Costs for validation | `backtest_models` (square-root impact, capacity) | built-in |

## 7. Phased implementation (advisory, default-off)

1. **P1 — `sector_screener.py` sector screen** — wrap the existing multifactor
   rank + quadrant + cycle tilt + regime gate into
   `get_sector_rotation_screen(sector_level=True)`; add the pullback-divergence
   flag and dispersion-context line. Zero new fetch beyond the 12 ETFs.
   Tests: synthetic closes → correct leader/flag/None-safe/min-bars.
2. **P2 — constituent breadth + EW/CW** — disk-cached constituent cache
   (SPY/SSO holdings or curated universe + yfinance sector); breadth
   %-above-MA50/200, EW-vs-CW ratio per top sector. Tests: ratio sign/scale on
   synthetic constituents (cap>EW narrow; EW>cap broad).
3. **P3 — stock setup screens A/B** inside the top 2–3 sectors — the 5.2
   filters; fetch per-constituent OHLCV from the cache (no new vendor).
   Tests: each setup's entry predicate on synthetic OHLCV incl. the
   no-chase cap and the volume footprint.
4. **P4 — validation, the gate** — `evaluate.py` backtest: monthly top-3
   sector RS/momentum vs equal-weight sectors vs SPY buy-hold, with costs,
   purged CPCV + PBO; Setup A/B stock variants vs parent-sector baseline.
   **Nothing above is "trusted" until P4's after-cost numbers clear this.**

Wiring: tool to the market analyst (import + tool list + prompt "use
before any 'sector is rotating / leadership is shifting' claim"), graph
ToolNode, `agent_utils`; wiring gate + prompt-guidance gate green
(`tests/test_calc_agent_wiring.py`). Each phase: hermetic tests
(`pytestmark.timeout`), ruff clean, affected suite, commit + push, docs true.
No `trading_web` surface while the read is LLM-facing (same as
`get_sector_rank` today).

## 8. Honest disagreements with `Strategies/sector_rotation.md`

- **Rejected as screen rules**: the VAR/Granger macro→sector short-legging
  (evidence flips by regime/frequency), the OU cointegration pair-spread
  trades (separate strategy; repo has pairs tooling), the 3-state MS-AR
  Hamilton-filter vol throttle (research-grade; OOS gains mixed; repo's
  regime/HMM machinery already covers the use), the ATR-buffer k* optimizer +
  dynamic sizing + chandelier/two-tier trailing frameworks (execution-layer;
  the repo's no-execution mandate already defers these). None of these make
  an *early-sector-identification* screener measurably better in the
  research, and each adds real complexity + parameter risk.
- **"First sector to stop falling leads the rally"** — keep as a *flag* with
  practitioner-grade evidence; do not build sizing on it.
- **The "fix Hold-heavy" framing from the earlier specs** is already handled
  by the adopted score≠signal + RRG quadrant split in `sector_rank.py` —
  the new screener inherits that discipline rather than re-deriving it.
- **Every signal is a screen, not a gate** — including the kill-switch
  overlay: the repo does not auto-execute, and distribution days are
  probabilistic (guidance "does not guarantee a correction").

## 9. Sources

- Moskowitz & Grinblatt (1999) "Do Industries Matter?" / industry momentum —
  industry component explains much of stock momentum (~0.43%→~0.13%/mo
  industry-adjusted), strongest 1–12m.
- Cohen & Polk industry-adjusted momentum; factor-momentum follow-ups.
- Korajczyk & Sadka — momentum gone at ~1.5% round-trip costs.
- Sector-ETF backtests: US GICS top-3 monthly 2000–2025 (11.3% vs 9.8% SPY,
  Sharpe 0.72 vs 0.54); TSX60 median-performer quarterly 2000–2025 (15.3% vs
  10.35%, Sharpe 0.92 vs 0.62); UK momentum costs 3×1=37.8% vs 12×12=5.4%;
  Alpha Architect live momentum turnover 83.7%/yr.
- RRG: JdK RS-Ratio/RS-Momentum quadrant rotation (Leading/Weakening/Lagging/
  Improving, clockwise); RRG sector backtest 2000–2022 (424%/16.8% CAGR/−9.1%
  MDD — in-sample, not alpha proof).
- Solnik et al. — cross-sectional dispersion ⇄ correlation; dispersion as a
  state variable forecasting vol/returns.
- Breadth: %-above-200dMA regime gauge (>70 bull / <30 bear); A/D ratio
  noisy; EW-vs-CW narrow-rally divergence.
- IBD distribution days (≥0.2% down on higher volume, clustered) as a
  probabilistic top/correction warning; 50d-average-volume variant.
- CANSLIM/Minervini RS-line-new-high-before-price: practitioner tradition,
  no rigorous isolated study.
- Free data: State Street SPY daily holdings XLS; AmericanETP daily ETF
  holdings CSV; yfinance `Ticker.info` rate-limit fragility (~2–2.5k req/hr
  anecdotal).