# Momentum Day-Trading Framework (analysis-only adaptation)

Source: Ross Cameron / Warrior Trading 5-step momentum playbook
(*Growing a $2k Account to $65,662.04 in 30 Days*).

**Project rule:** analysis-only - no order/execution endpoints are ever added;
this doc turns the framework into detectable *screening & risk signals*.

---

## The framework

### Step 1 - Stock selection ("5 Pillars")
1. **RVOL ≥ 5-20x** the 50-day average volume (retail/trader interest)
2. **High total volume** (liquidity / turnover)
3. **Gap / % gain** ≥ 2-10% from prior close (leading market gainer)
4. **Price band** ~$2-$20 (low-priced momentum)
5. **Low public float** < 20M shares (ideally < 3-5M) - supply/demand imbalance

### Step 2 - Entry ("First Pullback" pattern)
- Initial surge, then pullback that:
  * does not retrace > 50% of the prior move
  * light volume on red (pullback) candles, heavy on green
  * holds **above 9 EMA and VWAP**
  * avoids prominent topping tails/upper wicks
- **Trigger:** first candle making a **new high** above the pullback high
- **Risk/Reward:** ≥ **2:1**, hard stop = low of the pullback

### Step 3 - Execution
- Bids at psychological levels (whole/half-dollar), L2 depth + time&sales
  for bid support (confirmation only - proxy in this repo).

### Step 4 - Exits & "walk away for the day"
- Exit: L2 sell wall / iceberg, heavy red prints, topping-tail/breakdown candle.
- Day off: gave back **50% of peak profit**, hit **max daily loss**, past the
  optimal window (~10:00 ET), no setups / bearish tape.

### Step 5 - Journal & metrics
- Log every trade; run win vs loss analytics; flag FOMO / chase / no-stop.

---

## Mapping to this repo (what exists)
| Pillar/rule | Module |
|---|---|
| RVOL | `scan_signals` (20d) in `scripts/value_screener.py`; extend to 50d |
| Gap % | new (open vs prior close from daily bars) |
| 9 EMA / VWAP hold | `_ema` + Alpaca 1m bars VWAP; candlestick helpers |
| 2:1 R:R / pullback-low stop | `strategies/contract.py` ATR/reward |
| 50% peak / max-loss / time window | `strategies/book_risk.py` + `risk_governor` - extend to intraday session |

## Planned analysis-only implementation (`Strategies/momentum_day_plan.md` green-light)
1. **`--scan momentum`** in the screener: 5-pillar pre-filter (RVOL 50d,
   volume, gap %, price band $2-$20, low float via FMP float), then **first
   pullback** flag from 1m/daily OHLCV (9EMA/VWAP hold, <=50% retrace,
   light-red/heavy-green volume, new-high trigger candle) with **R/R >= 2**.
2. **Session gates** (intraday, simulated): give-back 50% of peak, max daily
   loss, time-window (~10:00/calct) as analysis "risk flags", not execution.
3. **Journal collector**: reuse `strategies/reflection` ledger with a
   momentum-specific row type (pillars, pattern, R:R, exit flag, stop-hit).
4. **Units/regression**: pure functions + mocked bars; no real Broker call.

## Limitations (honest)
- **No L2 / time & sales**: free Alpaca Data API offers IEX quotes/trades
  (1m bars), not full Level-2; bid support is proxied by latest quotes.
- **No execution**: signals only.
- **Free-tier data depth**: daily history thin per tier; use moomoo/yfinance
  daily + Alpaca 1m intraday where available.

Status: implemented - module (`strategies/momentum.py`), screener `--scan momentum`,
  Market Analyst tool `get_momentum_scan`; session-risk/journal steps remain on request.