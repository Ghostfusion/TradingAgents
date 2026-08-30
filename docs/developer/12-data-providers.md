# 12. Data providers

This fork uses **14 distinct data providers/sources**, in three tiers. It tells
a developer exactly which vendor supplies which signal and how each is wired
(routed `route_to_vendor` chain vs. direct import).

## Quick tally

| Tier | Count |
| --- | --- |
| Routed vendors (`VENDOR_LIST`) | 10 |
| Direct-but-not-routed sources | 5 |
| **Total distinct providers** | 15 |

---

## Tier 1 — the 10 routed vendors (`route_to_vendor`, `dataflows/interface.py`)

These sit behind the analyst `@tool` calls and are chosen per-category via
`data_vendors` chains (see `docs/developer/03-dataflow-vendors.md`).

```python
VENDOR_LIST = ['yfinance', 'fred', 'polymarket', 'alpha_vantage',
               'finnhub', 'sec_edgar', 'moomoo', 'massive', 'eodhd', 'tiingo']
```

| # | Vendor | Provider | What it supplies |
| --- | --- | --- | --- |
| 1 | **yfinance** | Yahoo Finance (via the `yfinance` lib) | OHLCV stock data, technical indicators, fundamentals, balance/income/cash-flow, options chain, short interest, news, sector fallback |
| 2 | **fred** | FRED (St. Louis Fed) | macro series: policy rates, Treasury yields, inflation, labor, growth |
| 3 | **polymarket** | Polymarket | prediction markets (market-implied event probabilities) |
| 4 | **alpha_vantage** | Alpha Vantage | stock data, indicators, fundamentals, statements, news |
| 5 | **finnhub** | Finnhub (free tier) | company news, analyst ratings, earnings calendar, basic financials, insider activity, company peers |
| 6 | **sec_edgar** | SEC EDGAR | SEC filings (8-K material events, 10-K/Q, S-1/S-3, 13D/G); when EDGAR fails the `get_sec_filings` tool falls back to Massive Form-4 insider activity |
| 7 | **moomoo** | Moomoo OpenAPI (via the local OpenD gateway) | US/HK/JP/SH/SZ/AU/CA/SG/MY quotes, fundamentals, earnings calendar, economic calendar, Fed watch, capital flow, corporate actions, options, short interest, top movers |
| 8 | **massive** | Massive.com (added in this fork) | news sentiment, economy (treasury/inflation/labor), short interest/volume, Form-4 insider, ratios, snapshots/top movers, related-companies, IPOs |
| 9 | **eodhd** | EODHD (added in this fork) | **primary OHLCV** (EOD plan $19.99/mo = 100k calls/day @ 1000/min, 30+ years) + news + splits/dividends + full US symbol list (~18k common stocks, the screener's default `--universe eodhd-us`) — replaces the moomoo K-line quota |
| 10 | **tiingo** | Tiingo (added in this fork) | free Starter tier: EOD OHLCV (7+ yrs), fundamental statements (JSON), IEX delayed quote, crypto OHLCV; ~1,000 calls/day so last in chains |
| 11 | **twelve_data** | Twelve Data (added in this fork) | free "Basic" tier: 800 credits/day, 8/min; realtime US stocks/forex/crypto quotes + historical time-series OHLCV (1 credit/symbol); tail of `core_stock_apis` + market-snapshot/crypto fallbacks |
| 12 | **stockdata** | StockData.org (added in this fork) | free "$0/mo" plan: 100 requests/day; `/v1/data/quote`, `/v1/data/eod` (~6 months), `/v1/data/intraday`, `/v1/news/all` (2 articles/req); tail of `core_stock_apis` + `news_data` + market-snapshot fallback |

### Default chains per category (from `data_vendors`)

```
core_stock_apis      : eodhd,moomoo,yfinance,tiingo,twelve_data,stockdata
technical_indicators : moomoo,yfinance
fundamental_data     : moomoo,yfinance,tiingo
news_data            : eodhd,moomoo,yfinance,alpha_vantage,stockdata
macro_data           : fred,moomoo
prediction_markets   : polymarket,moomoo
analyst_ratings      : moomoo,finnhub
earnings_calendar    : moomoo,finnhub
options_data         : moomoo,yfinance
sec_filings          : sec_edgar
short_interest       : moomoo,yfinance
exchange_symbols     : eodhd
corporate_actions    : eodhd,moomoo
moomoo-only extras   : capital_flow, smart_money, economic_calendar, fed_watch,
                       market_breadth, revenue_breakdown,
                       earnings_catalyst, institution_data, earnings_surprise,
                       expected_move
```

---

## Tier 2 — direct-but-not-routed sources

These are imported directly by agents/scripts (not through `VENDOR_METHODS`).
They are optional / key-gated or pre-fetch sources.

| Provider | Module | Consumed by | Gate |
| --- | --- | --- | --- |
| **Alpaca** | `dataflows/alpaca.py` | `get_market_snapshot_alpaca` (market analyst); screener `_fetch_ohlcv` fallback | `enable_alpaca` |
| **FMP** | `dataflows/fmp.py` | optional multi-year fundamentals/EV/surprise enrich in the screener | `fmp_api_key` |
| **Reddit** | `dataflows/reddit.py` | `fetch_reddit_posts` -> pre-fetched into the sentiment analyst | optional |
| **StockTwits** | `dataflows/stocktwits.py` | `fetch_stocktwits_messages` -> pre-fetched into the sentiment analyst | optional |
| **float_shares** | `dataflows/float_shares.py` | `fetch_float_shares` -> screener `--enable-float` momentum pillar | `--enable-float` |

### Why these are direct, not routed

These five are **not** in `VENDOR_LIST` / `VENDOR_METHODS`, so `route_to_vendor`
does not know about them (verified against `dataflows/interface.py`). They are
**imported and called directly** instead. The reason is architectural: they do
not fit the "per-category chain with fallback" model that `route_to_vendor`
provides.

- **Alpaca** — optional, opt-in analysis source (`enable_alpaca`). It returns a
  **live snapshot** (distinct shape) rather than a category-method result, and
  there is no chain/fallback — you either enable Alpaca or you don't. So it is
  wrapped as its own `get_market_snapshot_alpaca` tool and called directly.
- **FMP** — optional enrich (`fmp_api_key`); a *supplement* to the fundamental
  chain, not a first-class fallback vendor. The screener calls it directly to
  fill multi-year fundamentals/EV/surprises when the core chain is thin.
- **Reddit / StockTwits** — **pre-fetched as raw text directly into the
  sentiment analyst's prompt** (turn 0), not fetched on-demand by a tool call.
  They are prompt-injected content, not per-category methods.
- **float_shares** — a single-purpose lookup (public float shares) used only
  by the screener `--enable-float` momentum pillar. No category, no fallback
  needed.

The 9 routed vendors are the well-behaved *core* feeds (prices, fundamentals,
news) where resilience (fallback / TTL cache / typed errors) matters; the 5
direct sources are one-off / optional / special-purpose inputs that do not need
that resilience.

---

## Tier 3 — Massive sub-modules (part of provider 8)

| Provider | Module | Access method | Entitlement |
| --- | --- | --- | --- |
| **Massive REST** | `dataflows/massive.py` | `/v2/*`, `/fed/v1/*`, `/stocks/*` REST | plan-gated (some 403 on free Basic) |
| **Massive Flat Files** | `dataflows/massive_flat.py` | S3 bulk day-aggregate CSVs | Stocks Starter+ |
| **Massive WebSocket NOI** | `dataflows/massive_noi.py` | real-time net-order-imbalance stream | Imbalances Expansion add-on |

---

## Marketing / API-key source

| Provider | Env key (in `.env`) | Notes |
| --- | --- | --- |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | optional; chains first where configured |
| FRED | `FRED_API_KEY` | required for `macro_data` fred |
| Finnhub | `TRADINGAGENTS_FINNHUB_API_KEY` | free tier, key-gated |
| FMP | `TRADINGAGENTS_FMP_API_KEY` | optional enrich |
| EODHD | `TRADINGAGENTS_EODHD_API_KEY` | added in this fork (daily OHLCV) |
| Alpaca | `TRADINGAGENTS_ALPACA_API_KEY_ID` / `TRADINGAGENTS_ALPACA_API_SECRET` | optional; `enable_alpaca` |
| Massive | `MASSIVE_API_KEY` (a.k.a. `TRADINGAGENTS_MASSIVE_API_KEY`) | added in this fork |
| Moomoo | none in `.env` — credentials stay in OpenD (logged-in gateway) | not a key |

## Coverage notes

- **US-centric non-routed** sources (Yahoo, FRED, Finnhub, Massive, SEC)
  supplement; **moomoo** is the primary across US/HK/JP/SG/SS etc.
- **Crypto** (`BTC-USD`) auto-disables ratings/earnings/A-series tools.
- Adding a new provider = vendor contract (add to `VENDOR_LIST`,
  `TOOLS_CATEGORIES`, `VENDOR_METHODS`, `data_vendors`, wrap as `@tool`).

---

Related: `docs/developer/03-dataflow-vendors.md` (it lives the routing/error
taxonomy/cache), `docs/api_reference.md` §6 (vendor tables).