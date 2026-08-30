# Alpaca Market-Data Integration Plan (analysis-only — no trading/execution)

**Scope constraint:** per project decision, *all trading-related Alpaca endpoints are
deliberately excluded*: no orders, positions, account/portfolio P&L, portfolio history, paper/live
brokerage, liquidations, or OAuth trading assets. This plan is strictly for the
**market-data/calendar/asset** endpoints to enrich the analysis pipeline.

Sources: Alpaca `llms.txt` docs; repo mapping below.

---

## Why Alpaca fits this project
Already: moomoo (OpenD), yfinance, FMP, alpha_vantage, finnhub, sec_edgar.
Alpaca adds **clean, adjustment-aware historical bars**, **multi-symbol snapshots**,
and a **market-hours calendar**, which fills the remaining hard data gaps:

| Gap | Where the repo currently falls short | Alpaca adds |
|---|---|---|
| Historical daily/1m OHLCV for every candidate | `_fetch_ohlcv` CSV/chain; yfinance daily only | `alpaca get-bars` (raw/adjustment=tick > full OHLCV+$vwap) — hardens ATR%/30d vol/SMA/RSI gates |
| Batch snapshot for the universe | one-by-one vendor calls | `snapshot multi-symbol` (batch quotes/snapshots for top-50 heat-proxy list in one request) |
| Session/clock | hard-coded date everywhere | `/clock` + `/calendar` (open/close, market-hours) for PEAD/session-aware gates |

Also: assets API can exclude halted/non-tradable ETFs (keeps our stock/equity filter honest); VWAP/adjusted bars
are historically the generated field, beneficial to the trend/pullback scan (scan.md).

---

## Functional design (integration points)

### Phase 1 — Alpaca client (`tradingagents/dataflows/alpaca_common.py` + `alpaca.py`)
- `alpaca_common.py`: key resolution (`alpaca_api_key_id/secret` via config/.env), `signed_get()` with automatic retry/timeouts, typed error fallback (`None`).
- `alpaca.py` data functions:
  - `get_bars(symbol, timeframe="1Day", limit=200, adjustment="raw")` — must use `get_stock_bars` on the Data API; returns [{date_open, high, low, close, volume, vwap}]
  - `get_bars_batch(symbols, timeframe, limit)` for up to 10 symbols
  - `get_latest_snapshot(symbols)` → per-symbol: latest/daily trade+quote+bar
  - `get_earnings_calendar`? skip; Alpaca doesn't expose a standard earnings surprise feed in v1 barriers (kept FMP/moomoo). Instead: **`get_clock` + `get_calendar`**:

### Phase 2 — Screener & session wiring
- In `scripts/value_screener.py`: when `enable_alpaca`:
  - `_fetch_ohlcv(ticker, ...)` is extended (inline in `value_screener.py`: it
    calls `get_bars(ticker, timeframe="1Day", limit=330)` when `route_to_vendor
    get_stock_data` returns an empty CSV, gated by `len>=15`); trend/ATR/volume
    gates are recomputed from Alpaca bars (instead of moomoo CSV).
  - A `get_clock()` closed-market note is appended to the output (only when
    `enable_alpaca`; e.g. `[alpaca] market CLOSED (use /calendar for next open)`).

### Phase 3 — Corporate/asset info (NOT implemented; optional tier)
- `get_assets()` (filter stock universe, exclude halted/non-tradable) and an
  Alpaca `get_corporate_actions(symbol)` are **documented but not implemented**.
  The vendor-agnostic `get_corporate_actions` tool (moomoo/`massive`) already
  serves dividends/splits to the fundamentals analyst, so this Alpaca tier is
  left out (low decision value).

---

## Tests / acceptance criteria

1. `tests/test_alpaca_client.py` (offline):
   - `f_key`/`s_secret` not configured → `get_bars == None` and no HTTP call (mock `requests`).
   - `get_bars` parses synthetic JSON (incl. vwap) correctly.
   - batch/snapshot map input symbols → per-symbol rows.
   - `get_calendar` returns open/close date/finishing; malformed → None.
2. `tests/test_alpaca_scan_sources.py`: when `enable_alpaca`, the scan-side kline tap is served from `alpaca.get_bars` for the exact synthetic CSV (parse math: fallback path remains best mock-fetch); plus status notes.
3. Full regression (timer); README adds an Alpaca enrichment bullet; .env optional keys are seeded (commented placeholders).

## Cost / limits / risks
- No cost on IEX feed tier (free); SIP and adjusted/historical are paid — default to the basic IEX free tier.
- Two signed headers (Key-ID + secret) per request; rate ~**200 requests/min** — screen-known max fine because IEX is combined with existing network chain.
- `.env` keys: `TRADINGAGENTS_ALPACA_API_KEY_ID`, `TRADINGAGENTS_ALPACA_API_SECRET` (keep gitignored).
- Kind off-topic but noteworthy: **no trade** touched; no order route included in the repo at all. Default idle `enable_*` gates.

## When asked for
1. `tradingagents/dataflows/alpaca_common.py` + `alpaca.py` (pure data client)
2. Screener OHLCV alt-source + calendar gate
3. Optional assets/corporate-actions columns
4. Tests, README, final regression.