# Screener scan modes

`scripts/value_screener.py --scan <mode>` turns the daily universe into a
strategy-targeted watchlist. Modes extend the classic value screens with
deterministic technical/relative-strength gates; every gate is computed, never
narrated, and a missing data point makes a gate "unknown" (ignored, not
failed). Source docs: `Strategies/value_strategy.md`, `Strategies/framework.md`,
`Strategies/momentum_day_trading.md`.

Mode gates run on top of the liquidity/price/market-cap/PE/ATR filters, so each
watchlist is tradeable-by-construction. The framework phase-1 gates below are
**optional flags** (all off by default, `0` disables):

| Flag | Rule (framework) | Data source |
| --- | --- | --- |
| `--min-eps-yoy 20` | EPS YoY >= 20% | moomoo statement YoY column |
| `--min-rev-yoy 15` | Revenue YoY >= 15% | moomoo statement YoY column |
| `--min-roe 15` | Return on Equity >= 15% | net income / total equity |
| `--max-mcap 100000000000` | market cap <= $100B ($2B-100B focus) | vendor cap |
| `--sector-rank` | sector in the top-3 SPDR group (1m/3m) | SPDR ETFs + yfinance sector |
| `--revision` | positive net analyst upgrades (60d) | yfinance upgrades/downgrades proxy |
| `--inst-accum` | institutional %-of-float rising (2 quarters) | moomoo shareholders |

A gate is applied **only when the metric is measured** - a symbol with missing
data keeps the row and renders `n/a` (never a fabricated pass or fail).

## `value` (classic)

Magic Formula (EY, EV/EBIT), Acquirer's Multiple, Piotroski F-Score,
Shareholder Yield, Net-Net and the Beneish/Altman guards - see
`Strategies/Math.md`. No OHLCV gates. The framework Phase-1 growth/structure
gates (EPS/revenue YoY, ROE, max cap, sector top-3, revisions, institutional
accumulation) are the optional flags above and work in every mode.

## `trend-pullback` (Strategy A)

Buy the dip inside an uptrend:

- close above SMA50 and SMA50 above SMA200
- last low traded into the 20-day EMA while the close held it
- RSI(14) in 40-55 (a healthy reset, not a break)
- last quarter >= +10%

## `breakout` (Strategy B)

Volatility-contraction breakout:

- within 10% of the 52-week high, close above SMA20/SMA50
- RVOL > 1.5 on the breakout day, or RVOL < 0.75 with a Bollinger squeeze
  (volatility contraction priming the break)

## `momentum` (day-trade)

Warrior-style 5-pillar pre-filter + first-pullback pattern (see
`Strategies/momentum_day_trading.md`): RVOL >= 2, volume >= 1M, gap >= 2%,
price in the $2-20 band, low float (with `--enable-float`); then the 9-EMA /
VWAP-hold first pullback with >= 2:1 reward:risk. Optional `--journal` appends
candidates to a JSONL trade journal.

## `swing` (techno-fundamental swing)

Multi-day to multi-week setups from `Strategies/framework.md`:

- **trend architecture** - price above a *rising* SMA50/SMA200 with the 20-day
  EMA stacked above the SMA50
- **RS leadership** - the stock's relative-strength line vs the benchmark
  (`benchmark_ticker`, default SPY) in an established uptrend (63-day slope)
  - `leading` / `uptrend` pass; `lagging` / `diverging` (price new-high
    without RS backing) fail; unknown RS (benchmark data missing) never blocks
- **pullback setup** - low trades into the 20-day EMA while the close holds
  it, on declining volume (accumulation, not distribution)
- **RSI discipline** - RSI in the 45-70 operating band or the 40-50 reset
  zone; broken below 40 is invalidated

Table columns for swing mode: `ScanC` (yes/no), `RS` (lead/up/lag/div/n/a),
`Stp` (risk % to the structure stop = 1 ATR below the swing low) and
`T2` (upside % to the 3R target). Position management per the framework
(50% off at 2R, break-even on the rest, trail the 20-day EMA) is covered by
`tradingagents/strategies/swing.py` and `exits.py`.

## `vcp` (volatility contraction pattern)

The classic Weinberger/Minervini base: a series of successively *shallower*
pullbacks off a base high on *declining* volume - volatility contracting
before a breakout (framework Phase 3: 15% -> 8% -> 3%).
`tradingagents/strategies/swing.py::vcp_setup`:

- pivot troughs over the trailing 90 bars (strict 3-bar lookback)
- last 3 pullback depths (vs the base high) must be **non-increasing** (later
  pullbacks shallower, 10% tolerance for noise)
- the deepest pullback stays inside **30%** of the base high
- mean volume between successive troughs must not expand (absent volume is
  ignored, never a failure)
- `Brk` column = distance from the close to the base high (the "spring")

## `all` (default)

Everything survives; `ScanA`/`ScanB` columns flag trend-pullback and breakout
setups, `ScanC`/`RS`/`Stp`/`T2` appear when any swing setup is present and
`VCP`/`Brk` when a volatility-contraction base is detected. A dedicated
`--scan <mode>` filters to that one setup; `all` only flags.

## Benchmark note

The swing mode fetches one benchmark close series per run (cached). With
`TRADINGAGENTS_BENCHMARK_TICKER` unset this is SPY via the configured vendor
chain (`moomoo,yfinance`); pick a market-representative index for non-US
universes.