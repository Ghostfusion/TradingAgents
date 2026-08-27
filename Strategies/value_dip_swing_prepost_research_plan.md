# Value-Dip + Swing + Pre/Post-Market — Combined Research & Implementation Plan

Status: **research complete, plan for approval — no code changes yet.**

This combines two research passes:
1. **Value-dip + swing** tools/utilities/calculations (mean reversion, VWAP, volume
   strategies, oscillators, channels, exits).
2. **Pre-market + post-market** tools/utilities/calculations (opening range,
   opening cross/auction, order imbalance, gaps, after-hours, MOC, overnight,
   earnings surprise / PEAD).

Each section lists what the **web research** says, what the **project already
has**, and the **gap** (what to add). The plan at the end prioritizes the gaps
that fit the project's no-fabrication, deterministic-first philosophy.

---

## Part A — Value-Dip + Swing (research pass 1)

### A1. Mean reversion (Investopedia)
- **Z-score** = (price − mean) / std; |Z| ≥ 1.5–2 signals over/undervalued.
- Tools: moving averages, Bollinger Bands, RSI (70/30), Stochastic (80/20), MACD.
- **Project has**: `value_dip.zscore`, `valuation_z_read`, `bollinger_pct_b`,
  `swing.rsi`, `technical_factors.stochastic_oscillator`, `_macd_hist`.
- **Gap**: none material — covered.

### A2. VWAP (Investopedia)
- VWAP = Σ(typical price × volume) / Σ volume; typical = (H+L+C)/3.
- Buy below VWAP / sell above; institutional benchmark.
- **Project has**: `momentum.vwap(closes, volumes)` (daily approximation).
- **Gap**: no intraday VWAP (needs 1-min bars); Alpaca `get_intraday` exists but
  only for the screener's L1 columns. **Add**: an intraday VWAP read for the
  pre-market/open path (see Part B).

### A3. Volume strategies (Investopedia)
- OBV (on-balance volume), volume-by-price (support/resistance at high-volume
  price levels), volume confirms breakouts.
- **Project has**: `technical_factors.obv_divergence`, `elder_thermometer`,
  `momentum.rvol`, `value_dip.volume_dry_up`.
- **Gap**: **volume-by-price / volume profile** (POC = point of control, value
  area) — not implemented. High-value for dip support/resistance.

### A4. Oscillators (Investopedia)
- Aroon (trend age), Fisher Transform (normalize turning points), Chaikin
  Oscillator (3-EMA − 10-EMA of A/D), Elder-Ray (bull/bear power), ROC, TRIX,
  Force Index (volume × price change), A/D line (MFM × volume).
- **Project has**: KST, MFI, Stoch, ADX, pivots, StochRSI, RSI2, W%R, Keltner,
  Donchian, OBV, PSAR, Elder thermometer.
- **Gap**: **Aroon**, **Fisher Transform**, **Chaikin Oscillator**, **Elder-Ray
  bull/bear power**, **ROC**, **TRIX**, **Force Index**, **A/D line** — none
  implemented. These are cheap, pure, and fit the technical_factors module.

### A5. Channels / trend (Investopedia)
- Keltner (EMA ± 2×ATR), Donchian (20-day high/low), Supertrend (ATR-based
  trailing), Parabolic SAR.
- **Project has**: Keltner, Donchian, PSAR, chandelier exit, fib levels.
- **Gap**: **Supertrend** (ATR-based trailing stop) — not implemented; overlaps
  with chandelier but is a distinct, widely-used trailing line.

### A6. Exits / risk (Investopedia)
- Stop below OR low / breakout candle; profit = multiple of risk; trailing stop
  on MA close.
- **Project has**: `exits.stop_to_breakeven`, `target_level`, `exit_check`,
  `swing.chandelier_exit`, `trail_ema`, `targets_rr`, `scaleout_plan`.
- **Gap**: none material — covered.

---

## Part B — Pre-Market + Post-Market (research pass 2)

### B1. Pre-market trading (Investopedia)
- Session 4am–9:30am ET; low liquidity, wide spreads, institutional dominance,
  retail order restrictions.
- **Project has**: `pre_market_review.py` (standalone pre-open), `pre_market.py`
  (deterministic gap/catalyst/re-anchor arbiter), `_realtime_price` (Alpaca →
  yfinance).
- **Gap**: no **pre-market volume/liquidity read** (thin-book warning). The
  screener has ILLIQ/FltTurn/IWF for daily, but not a pre-market-specific
  liquidity check.

### B2. Opening range (OR) + ORB (Investopedia)
- OR = first ~15 min high/low. ORB: buy above OR high / sell below OR low; stop
  below OR low; target = multiple of risk; trailing exit on 10-SMA close.
- **Project has**: nothing for intraday OR/ORB (the framework is daily/swing).
- **Gap**: **opening-range breakout (ORB)** — a pre-market/open-path read:
  compute OR high/low from the first N minutes, flag a breakout, suggest
  stop/target. High-value for the pre-market reviewer.

### B3. Opening cross / auction (Investopedia)
- Nasdaq Opening Cross: matches buy/sell orders at open; orders can be
  submitted/changed/canceled until 9:28am ET; auction sets a fair opening price;
  reflects overnight sentiment. Closing Cross sets the close.
- **Project has**: nothing (no auction data source).
- **Gap**: **auction mechanics** are informational — no vendor exposes the
  cross directly. **Add**: a deterministic "auction read" that uses the
  pre-market quote vs prior close + order-imbalance proxy (see B4) to flag
  likely open direction. Data-limited; degrade to UNKNOWN.

### B4. Order imbalance (Investopedia)
- Imbalance = buy/sell/limit orders lacking matching counterpart; resolves
  quickly in liquid markets; market makers intervene; limit orders shield
  volatility.
- **Project has**: `orderflow.py` (institutional/retail net, distribution score,
  divergence, alignment) from moomoo capital-flow buckets.
- **Gap**: **order-imbalance proxy** — the orderflow module already computes
  institutional vs retail net; add an explicit "imbalance" verdict (buy-heavy /
  sell-heavy / balanced) from the existing nets. Cheap, fits.

### B5. Gaps (Investopedia)
- 4 types: common (fills fast), breakaway (out of range/pattern), runaway
  (trend continuation), exhaustion (trend end). Gap-fill: common gaps fill
  quickly; price-gap risk = close-to-open discontinuity.
- **Project has**: `pre_market.premarket_gap` (gap_pct, gap_atr, through_stop,
  vacuum_to_stop, direction), `events.gap_up_qualifies` (PEAD gate).
- **Gap**: **gap-type classification** (common/breakaway/runaway/exhaustion)
  and **gap-fill statistics** (historical fill rate / days-to-fill). The
  pre-market reviewer would benefit from knowing "this is a breakaway gap (low
  fill probability)" vs "common gap (likely fills)". **Add**: a `gap_type`
  classifier + fill-rate stats from the OHLCV history.

### B6. After-hours / MOC / overnight (Investopedia)
- After-hours 4pm–8pm ET via ECNs; low liquidity, wide spreads. MOC orders
  execute at/near close, subject to imbalance. Overnight positions carry gap
  risk.
- **Project has**: `alpaca.get_clock`/`get_calendar` (market open/close),
  `pre_market_review` (overnight gap), `catalyst` (earnings window).
- **Gap**: **post-market close review** — a "did the close confirm the plan?"
  read (close vs stop/target, MOC-style exit suggestion). The nightly review
  exists but is pre-open focused. **Add**: a post-close confirmation read.

### B7. Earnings surprise / PEAD (Investopedia)
- Surprise = (actual − estimate) / |estimate|; positive surprise → immediate +
  gradual price increase (PEAD); negative → decline.
- **Project has**: `events.surprise_score`, `drift_side`, `expected_drift_after`,
  `post_earnings_play` (gap gate → consolidation → break), `catalyst` earnings
  window, `get_earnings_surprise` tool.
- **Gap**: none material — PEAD is well covered. Could add a **surprise
  magnitude band** (small/large) to the existing read.

---

## Implementation Plan (prioritized)

### Phase 1 — Technical factors additions (pure, cheap, high-value)
**File**: `tradingagents/strategies/technical_factors.py`
Add pure functions (all return None on insufficient data — no fabrication):
- `aroon(highs, lows, n=25)` → `{aroon_up, aroon_down, verdict}`
- `fisher_transform(closes, n=9)` → `{fisher, trigger, verdict}`
- `chaikin_oscillator(highs, lows, closes, volumes, fast=3, slow=10)` → float
- `elder_ray(highs, lows, closes, n=13)` → `{bull_power, bear_power, verdict}`
- `roc(closes, n=12)` → float
- `trix(closes, n=15)` → float
- `force_index(closes, volumes, n=13)` → float
- `accumulation_distribution(highs, lows, closes, volumes)` → float
- `supertrend(highs, lows, closes, atr_mult=3.0, n=10)` → `{line, direction}`
- `volume_profile(closes, volumes, bins=20)` → `{poc, value_area_high, value_area_low}`

**Tests**: `tests/test_strategies_technical_factors.py` (extend existing).

### Phase 2 — Pre/post-market additions
**File**: `tradingagents/strategies/pre_market.py` (extend) + new
`tradingagents/strategies/market_session.py`:
- `opening_range(highs, lows, n_minutes=15)` → `{or_high, or_low, breakout, stop, target}`
- `gap_type(closes, highs, lows, volumes)` → `{type, fill_probability, days_to_fill}`
- `order_imbalance(inst_net, retail_net)` → `{verdict, ratio}` (reuse orderflow nets)
- `premarket_liquidity(volume, avg_volume)` → `{ratio, verdict}` (thin-book warning)
- `post_close_confirmation(close, stop, target)` → `{verdict, action}`

**Wire into**:
- `scripts/pre_market_review.py` — add ORB + gap-type + premarket-liquidity to
  the deterministic summary.
- `scripts/nightly_review.py` — add post-close confirmation.
- `scripts/action_report.py` — optionally surface gap-type in the condition check.

### Phase 3 — Analyst tools + screener columns
- Add `get_opening_range`, `get_gap_type`, `get_order_imbalance`,
  `get_premarket_liquidity`, `get_post_close_confirmation` to
  `analysis_tools.py` / a new `market_session_tools.py`; bind to the market
  analyst.
- Add screener columns: `Aroon`, `Fisher`, `Chaikin`, `ElderRay`, `ROC`, `TRIX`,
  `Force`, `A/D`, `Supertrend`, `POC` (volume profile).

### Phase 4 — Docs + web
- Update `Strategies/index.md`, `CHANGELOG.md`, `docs/developer/04-strategies.md`,
  `docs/developer/06-entrypoints.md`.
- trading_web: add the new tools to the Value Tools / a new "Market Session"
  page; update README.

### Validation
- Full suite `py -3.12 -m pytest tests/` (target: all pass, no regressions).
- ruff clean.
- Live smoke: `scripts/pre_market_review.py --ticker EIX --skip-llm` shows the
  new ORB/gap-type/liquidity lines.

### Not doing (data-limited or low-value)
- **Auction cross data** (no vendor exposes it) — informational only.
- **Intraday VWAP** (needs 1-min bars; Alpaca free tier is daily-only) — defer.
- **Volume profile** is Phase 1 but POC from daily bars is approximate; label it.

---

## Open questions for approval
1. Phase 1 scope: add **all 10** technical factors, or a subset (Aroon, Fisher,
   Chaikin, Elder-Ray, Supertrend, volume-profile are the highest-value)?
2. Phase 2: OK to add a new `market_session.py` module, or keep everything in
   `pre_market.py`?
3. Phase 3: bind the new tools to the **market analyst** only, or also the
   fundamentals analyst where relevant?
4. Screener columns: add all 10, or only the ones with clear dip/swing value
   (Aroon, Fisher, Supertrend, POC)?
