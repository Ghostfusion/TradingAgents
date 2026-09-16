# Design + implementation: Webull OpenAPI as a data provider

State 2026-09-16. Sources are Webull's own documentation (links inline; all pages read
2026-09-16). No code changed by this document.

## Verdict

Webull OpenAPI is **worth adding as a US-only fundamentals + bars provider**, and the
reason is narrower and better than "one more quote vendor":

- **Its statements are natively basis-tagged.** Every income/cashflow/balance row carries
  `fiscal_year`, `fiscal_period` (0 = FY, 1..4 = Q), `end_date` and `publish_date`
  ([income](https://developer.webull.com/apis/docs/reference/financial-income.md)). That is
  the exact provenance this repo spent 2026-09-14..16 chasing: the AMZN drift where the same
  call returned FY-annual flows at 22:5xZ and TTM quarters at 19:08Z, and the report-side
  basis registry added in `169289a`. A vendor that hands over the basis and the publish date
  is the upstream half of that fix, and `publish_date` also gives point-in-time selection for
  free (see `tradingagents/dataflows/pit_registry.py`).
- **300 requests/minute** on the Data API and **20 symbols per bars call**
  ([rate limits](https://developer.webull.com/apis/docs/market-data-api/data-api.md),
  [bars](https://developer.webull.com/apis/docs/reference/historical-bars.md)) is more
  headroom than the current chains have: `batch.py` currently caps workers at 4 "to stay under
  moomoo connection limits".
- **A Python SDK exists** (`pip install webull-openapi-python-sdk`, Python 3.8-3.14) that
  signs requests and manages the token, plus an official MCP server
  ([SDK](https://developer.webull.com/apis/docs/sdk.md)).

It is **not** a replacement for EODHD or moomoo: it is US-only, its news endpoint is not a
headline feed, and real-time entitlement is a paid, separately-purchased Nasdaq
non-display subscription (below).

## Verified API facts

| Fact | Value | Source |
|---|---|---|
| Access patterns | Data API (HTTP) + Data Streaming (MQTT over WS/TCP, protobuf payloads) | [overview](https://developer.webull.com/apis/docs/market-data-api/overview/) |
| Hosts (server-to-server) | prod `api.webull.com` / streaming `data-api.webull.com`; test `api.sandbox.webull.com` / `data-api.sandbox.webull.com` | [sdk](https://developer.webull.com/apis/docs/sdk.md) |
| Auth | HMAC-SHA1 signature headers + `x-access-token`; app secret is **never** sent | [signature](https://developer.webull.com/apis/docs/authentication/signature.md) |
| Signed string | `path` + `&` + `sorted(k=v)` of (query params + `x-app-key`/`x-signature-algorithm`/`x-signature-version`/`x-signature-nonce`/`x-timestamp`/`host`) + `&` + `toUpper(MD5(body))`, then URL-encode, HMAC-SHA1 with key `app_secret + "&"`, base64 | signature (same page) |
| Signature test vector | worked example result `kvlS6opdZDhEBo5jq40nHYXaLvM=` | signature (same page) |
| Test environment token | valid by default, **no 2FA** | [token](https://developer.webull.com/apis/docs/authentication/token.md) |
| Prod token | 2FA: SMS verified **in the Webull app within 5 minutes**; `INVALID` after **15 consecutive days with no API calls** | token (same page) |
| Rate limits | 300 req/min overall; **60 req/60s** on the income-statement endpoint; MQTT subscribe/unsubscribe unlimited | [data-api](https://developer.webull.com/apis/docs/market-data-api/data-api.md), [faq](https://developer.webull.com/apis/docs/market-data-api/faq.md) |
| Streaming limits | **max 5 concurrent MQTT connections per App Key**; subscriptions are **not** restored after reconnect; protobuf except the `notice` topic | faq (same page) |
| Categories | `US_STOCK`, `US_ETF` (futures/crypto/event contracts use their own paths) | data-api (same page) |
| Real-time entitlement (US stocks/ETFs) | subscribe **Nasdaq Basic (L1) or Nasdaq Totalview (L2) for Non-Display OpenAPI**; app/QT subscriptions do **not** count; **only one device may use L1/L2 at a time** | overview + [subscribe-quotes](https://developer.webull.com/apis/docs/market-data-api/subscribe-quotes.md) |
| Sandbox data | 15-minute delayed by default; upgraded to real-time if prod is subscribed | overview (same page) |
| App eligibility | retail individual: Webull account + application reviewed **1-2 business days**; **sandbox application auto-approved in minutes** | [application](https://developer.webull.com/apis/docs/authentication/IndividualApplicationAPI.md) |
| Bars | `POST /market-data/stocks/bars/list`, ≤20 symbols, `timespan` M1..M240/D/W/M/Y, `count` default 200 max **1200** (M1: 1650), `trading_sessions` PRE/RTH/ATH/OVN, `real_time_required`, `start_time`/`end_time` ms; **daily and above are forward-adjusted, minute bars unadjusted** | bars (same page) |
| Statements | `type=ANNUAL|QUARTERLY`, `count` default 5 max 20, rows carry `fiscal_year`/`fiscal_period`/`end_date`/`publish_date`/`currency`, figures as **strings** | income (same page) |
| Fundamentals family | company profile, analyst target price, analyst rating, forecast EPS, filings, earnings calendar, dividend calendar, capital flow, industry comparison, indicators, income, cashflow, balance sheet, fund brief/performance/net value/holdings/dividends/rating/splits/files/allocation | [llms.txt](https://developer.webull.com/apis/llms.txt) |
| News | `POST /market-data/news/summaries/get` — **an LLM-generated summary stream (SSE) over a watchlist**, not a headline feed | [news-summary](https://developer.webull.com/apis/docs/reference/news-summary.md) |

Two documentation inconsistencies to code against deliberately (the SDK sidesteps both):

1. Reference schemas list **`x-app-secret` as a required request header**, while the Data API,
   signature and token pages all state the secret is used only client-side for signing. Follow
   the prose/signature page; never transmit the secret.
2. `x-version`: the signature page says it accepts `v2`, the reference schemas say `v2|v3`
   (default `v3`). Every example uses `v2`; use `v2` and pin it in one constant.2. `x-version`: the signature page says it accepts `v2`, the reference schemas say `v2|v3`
   (default `v3`). Every example uses `v2`; use `v2` and pin it in one constant.

The measurement below resolved a third apparent contradiction (the `/openapi` prefix) in
favour of "both exist, per environment".

## Verified against the live API (2026-09-16)

Everything below was measured with a real **sandbox** App Key in `TradingAgents/.env`
(`TRADINGAGENTS_WEBULL_APP_KEY` / `_SECRET`, gitignored), a signer reproducing the vendor's own
published vector (`kvlS6opdZDhEBo5jq40nHYXaLvM=`), and a token from `POST /auth/tokens/create`
(`status=NORMAL`, no 2FA in the sandbox). The full sweep covered all **167 operations** harvested
from the 184 reference pages (Appendix A).

### The headline

**A large part of the API works with no subscription and no purchase of any kind.** In the
sandbox, with a plain app key: bars, snapshots, ticks, five screener/ranking feeds, an instrument
master of 1000 rows, and most of the fundamentals family (profiles, ratios, ratings, price
targets, filings, capital flows, forecast EPS, earnings/dividend calendars, financial alerts, fund
brief and fund performance) all return real payloads. The paid entitlement is **not** required for
those.

### Path and environment matrix (do not guess these)

| Family | Sandbox (`api.sandbox.webull.com`) | Production (`api.webull.com`) |
|---|---|---|
| Auth/token `/auth/tokens/create` | unprefixed works | unprefixed route; **an unknown key returns `401 UNAUTHORIZED` "…correct environment"** |
| Market data `/market-data/...` | **unprefixed works** | **`/openapi/market-data/...`** (unprefixed `404`s) |
| `/openapi/*` gateway | auth-first: a nonsense path still returns `401 MISSING_APP_KEY`, so a 401 there proves nothing about the route | same |

The sandbox key in `.env` is **sandbox-only**: against production the same key returns
`401 UNAUTHORIZED`. Questions that need production (financial statements first among them) cannot
be answered with it.

### Works in the sandbox, no subscription (measured)

| Endpoint | What came back |
|---|---|
| `POST /market-data/stocks/bars/list` | real daily bars, e.g. AAPL `2026-09-15` open 330.135 / close 331.340 / vol 31,748,183; also for `US_ETF` (`IEI`) |
| `GET /market-data/stocks/snapshots/list` | quote row with `price/open/high/low/volume/change/ask/bid/bps/lot_size` |
| `GET /market-data/stocks/ticks/list` | tick rows (`result[2]`) |
| `GET /market-data/screeners/{gainers-losers,top-actives,high-dividend-ranks,week52-high-low}/list` | 200 rows each |
| `GET /market-data/screeners/market-sectors/list` | 20 sector rows (`data[20]`) |
| `GET /market-data/fundamentals/company-profiles/get` | 10 fields (address, ceo, employees, establish_date, …) |
| `GET /market-data/fundamentals/indicators/get` | `currency` + a `values` map (cap_surplus_ps, debt_to_assets, diluted_eps_incl_extra, …) |
| `GET /market-data/fundamentals/analysis/ratings/get` | buy/hold/sell counts, `effective_start_date` |
| `GET /market-data/fundamentals/analysis/target-prices/get` | mean/high/low, `effective_start_date` |
| `GET /market-data/fundamentals/filings/list` | 6 filing rows |
| `GET /market-data/fundamentals/capital-flows/get` | 5 rows |
| `GET /market-data/fundamentals/forecast-eps/get` | 5 rows |
| `GET /market-data/fundamentals/{earnings-calendars,dividend-calendars}/list` | 2 rows each |
| `GET /market-data/fundamentals/financial-alerts/get` | next report `2026-10-28`, `fiscal_year=2026 fiscal_period=4`, `eps_est=1.97754` vs `eps_ly=1.85`, `rev_est=113.6B` |
| `GET /market-data/fundamentals/fund-brief/get` (`IEI`) | aum, benchmark, custodian, investment_objective, issuer, launch_date |
| `GET /market-data/fundamentals/fund-performances/get` (`IEI`) | returns 1m/3m/6m/1y/3y/5y |
| `GET /trading/instruments/stocks/profiles/list` | **1000 instruments** with `exchange_code`, `shortable`, `marginable`, `lot_size`, `sub_category` (e.g. `ETF`) + `pagination_key` |

### Reachable but empty in the sandbox

`income-statements/get`, `balance-sheets/get`, `cash-flows/get` returned `[]` for every variant
tried (AAPL/MSFT/TSLA, `type=ANNUAL|QUARTERLY`, `count` 1-8) - the routes are authorized but the
sandbox carries no statement data. Same for the rest of the `fund-*` family (holdings, net-values,
ratings, splits, files, allocations, dividends), `industry-comparisons/get` (empty body),
`watchlists/list` (no lists on this account), and the event-contract `events`/`markets` lists.

### Refused, with an explicit reason (the entitlement vocabulary)

| Endpoint | Error | Meaning |
|---|---|---|
| `GET /market-data/stocks/footprints/list` | `403 MARKET_DATA_NOT_SUBSCRIBED` | order-flow needs the paid subscription - and the API says so, in code |
| `GET /trading/{assets/balances,assets/positions,orders/*,activities/*}` | `403 ACCOUNT_ACCESS_DENIED` | no funded account linked to this app (irrelevant for research) |
| futures/options/crypto endpoints | `417 UNSUPPORTED_CATEGORY` | they take their own category values; not chased (see open questions) |
| `news/summaries/get`, NOII, `/broker*` (50 ops), event market data | `404` / `400` | not exposed in the sandbox (Display-Solution families are a different product) |

### Behaviour facts worth coding against

- **`real_time_required=false` moves the window**: with it, daily bars ended `2026-09-11`; with the
  default they ended `2026-09-15`. The flag is a data-basis choice, not a nicety.
- **Daily and above are forward-adjusted; minute bars are unadjusted** - the provider text must say
  which, because the verifier journals bases.
- **`category=US_ETF` works** end to end: `IEI` bars, snapshot, fund brief and fund performance all
  returned data with it.
- **Token responses carry both `expires` and `expires_at`** (ms) - read `expires_at`.
- **Error-code vocabulary for typed mapping**: `MISSING_APP_KEY`, `UNAUTHORIZED`,
  `MARKET_DATA_NOT_SUBSCRIBED`, `ACCOUNT_ACCESS_DENIED`, `ILLEGAL_PARAMETER`,
  `UNSUPPORTED_CATEGORY`, `UNSUPPORTED_SYMBOL`, `WATCHLIST_NOT_FOUND`, `SYSTEM_ERROR` - all under
  `{"error_code","message"}`, while unrouted paths use `{"error_msg":"404 Route Not Found"}`.
- **The instrument master is a usable asset on its own**: 1000 rows with ETF/shortability/margin
  metadata and a `pagination_key`, i.e. a candidate source for symbol validation, ETF
  classification and an `exchange_symbols` chain that today rests on one vendor.

## Fit against this repo's `data_vendors` categories (measured, not inferred)

| Category | Webull surface | Verdict after the sweep |
|---|---|---|
| `core_stock_apis` | bars (batch, US_STOCK + US_ETF), snapshots, ticks | **Works, no subscription** - US only; journal adjusted-vs-unadjusted and the `real_time_required` basis |
| `fundamental_data` | company profiles, indicators, ratings, target prices, filings, capital flows, forecast EPS, alerts | **Works**; the three financial STATEMENTS come back empty in the sandbox (prod unverified) |
| `analyst_ratings` | `analysis/ratings` + `analysis/target-prices` | **Works, no subscription** |
| `earnings_calendar` | `earnings-calendars`, `dividend-calendars`, `financial-alerts` | **Works** |
| `capital_flow` | `capital-flows` | **Works** (currently a moomoo-only category) |
| `equity_screener` / `market_movers` | 5 screener feeds, 200 rows each; market sectors | **Works** (rankings, not a screener DSL) |
| `sec_filings` | `filings` (6 rows for AAPL) | **Works** - but `sec_edgar` is free and richer; keep it first |
| `exchange_symbols` | instrument master (1000 rows, ETF/short/margin metadata, pagination) | **Strong candidate** - today this category rests on one vendor |
| `options_data` | options bars/snapshots/ticks | Category value + OPRA entitlement unresolved; the repo's tools need a chain summary Webull does not expose |
| `prediction_markets` | event-contract categories/series lists | Instrument lists work; the market-data side was not exposed in the sandbox - not a Polymarket substitute |
| `institution_data`, `short_interest`, `insider_transactions`, `macro_data`, `news_sentiment` | - | **No endpoint** |
| `news_data` | `news/summaries/get` (LLM SSE over a watchlist) | **No** - 404 in the sandbox, and an LLM summary inside an LLM pipeline is circular |
| `technical_indicators` | - | **No** (irrelevant: the repo computes indicators from OHLCV) |

**Additive surfaces with no counterpart today:** the instrument master with ETF/shortability
metadata, the five screener feeds, financial alerts (next-report estimate vs last year, useful for
the catalyst overlay), and - once entitled - NOII auction imbalance and Footprint order flow. The
one endpoint that *proves* the entitlement boundary is `footprints` with its explicit
`403 MARKET_DATA_NOT_SUBSCRIBED`.

## Constraints and blockers

1. **US-only.** `US_STOCK`/`US_ETF` categories, US options/futures/crypto/event contracts.
   Non-US symbols must raise a typed `NoMarketDataError` and fall through, exactly like
   `moomoo.py`. The measured route/auth behaviour in the sandbox confirms this is enforced at the
   endpoint, not in configuration.
2. **Two keys, two environments.** The key now in `.env` is a **sandbox** key: it authenticates on
   `api.sandbox.webull.com` and is rejected by production (`401 UNAUTHORIZED` "…correct
   environment"). Production needs its own application (1-2 business days) and its own key, and
   production market-data paths live under `/openapi`. Nothing above should be read as "prod
   behaves like the sandbox".
3. **Financial statements are the open surface.** Income/balance/cash-flow returned `[]` in the
   sandbox for every symbol/type/count variant tried. Whether they work in production is the
   question a prod key answers; until then the provider must not be the *only* statement source.
4. **Real-time is a separately-purchased Nasdaq non-display subscription**, and app/QT
   subscriptions do not count; only one device may use L1/L2 at a time. The API states the boundary
   itself: `footprints` answers `403 MARKET_DATA_NOT_SUBSCRIBED` today.
5. **Token lifecycle.** Sandbox tokens are `NORMAL` immediately with no 2FA (measured). Production
   tokens need in-app SMS verification within 5 minutes and are documented as expiring after 15
   days (and as going `INVALID` after 15 idle days) - check status before a run, persist the token
   under `data_cache_dir/`, and treat an invalid token as a typed auth error that falls through.
6. **Per-endpoint limits are tighter than the global one** (60 req/60s for income statements vs
   300/min overall). The limiter must respect the tightest budget it uses.
7. **ETF coverage is a different family** (`fund-brief`, `fund-performances` returned real data for
   `IEI`; holdings/net-values/ratings/splits/files/allocations were empty in the sandbox), so the
   provider needs an explicit instrument-type branch, not a statement call with a different symbol.

## Design

### Module layout (mirrors `moomoo.py`, which is this repo's template for a gated vendor)

```
tradingagents/dataflows/webull_common.py   signing, session, token store, limiter, typed errors
tradingagents/dataflows/webull.py          the category functions the router dispatches to
```

`webull_common.py`

- `generate_signature(path, query, body_string, app_key, app_secret, host, timestamp, nonce)` -
  the 6-step recipe, with the documented worked example as the conformance fixture
  (`kvlS6opdZDhEBo5jq40nHYXaLvM=`). Body strings must be compact JSON
  (`json.dumps(body, separators=(",", ":"))`) and the *same* string must be both MD5'd and
  transmitted - a documented trap that re-serialisation silently breaks.
- `WebullSession` - one `requests.Session` per thread (the repo's existing per-thread pattern in
  `moomoo.py`), honouring `TRADINGAGENTS_WEBULL_TIMEOUT_S`.
- Token store: `data_cache_dir/webull_token.json`, `0600`; `check_token` before use; sandbox
  skip.
- Limiter: token bucket per budget class (global 300/min, statements 60/min), injectable clock.
- Errors, matching the contract the router already handles: `WebullNotConfiguredError`
  (no keys) -> fall through; `WebullAuthError` (token pending/invalid/expired) -> fall through;
  `WebullPermissionError` (HTTP 403, entitlement missing) -> fall through with
  `NO_DATA_AVAILABLE`; `WebullRateLimitError` -> fall through; `NoMarketDataError` (non-US
  symbol, no rows) -> `NO_DATA_AVAILABLE`.

`webull.py` (each returns the repo's canonical text/JSON shape for its category)

- `webull_available()`, `get_stock_data_webull(symbol, start, end)`, `get_snapshot_webull`,
  `get_fundamentals_webull`, `get_income_statement_webull(freq)`, `get_balance_sheet_webull`,
  `get_cashflow_webull`, `get_analyst_ratings_webull`, `get_earnings_calendar_webull`,
  `get_capital_flow_webull`, `get_market_movers_webull`.

### Mapping rules that matter here

- **Category by instrument type**: `US_ETF` vs `US_STOCK` decided from the repo's existing
  security classification (the ETF engine already owns that gate) - not from the symbol string.
- **Bars -> OHLCV**: `D/W/M/Y` come back forward-adjusted, `M1..M240` unadjusted. The provider
  text must state which, because the verifier journals bases and a report that mixes an adjusted
  daily level with an unadjusted intraday level is exactly the class of defect the basis registry
  exists to catch.
- **Statements -> the repo's basis vocabulary**: `fiscal_period` 0 -> `fy_annual`, 1..4 ->
  `quarterly`; `end_date` is the period the figures belong to; `publish_date` is when they became
  knowable (use it for point-in-time selection instead of relying on the run date).
- **Numbers are strings** in every response - parse with the repo's existing money parser, and
  keep the raw string in evidence text so the verifier's numeric anchoring has something exact.
- **One call, many symbols**: batch the run's tickers into one bars request (20 max), which is
  what makes the provider cheap inside a 4-worker batch. Reuse the run-level OHLCV cache rather
  than re-fetching per analyst.

## Implementation plan (P0 is done)

| Phase | Work | Acceptance |
|---|---|---|
| **P0** ✅ **done** | Sandbox application + App Key/Secret in `.env`; signer verified against the vendor vector; full 167-operation sweep with statuses recorded (Appendix A); path/environment matrix measured | Keys stored (never committed); probe runs; the usable set is known rather than assumed |
| **P1** | `webull_common.py` (signing, token store, limiter, typed errors from the measured vocabulary) + `webull.py` with bars/snapshots; chain Webull **last** in `core_stock_apis`; `--vendor webull` preset | Signature conformance test; a live sandbox bars+snapshot call from inside the package; preset-completeness test passes; fallback proven against a simulated `403` |
| **P2** | Fundamentals-lite (profiles, indicators, ratings, targets, filings, capital flows, calendars, alerts) + ETF branch via the `fund-*` family | Trees where those reads appear in evidence with the provider named, and the `basis` registry shows the provider's own `fiscal_*`/`effective_start_date` fields |
| **P3** | Instrument master (`/trading/instruments/stocks/profiles/list`, 1000 rows + `pagination_key`) as a candidate `exchange_symbols`/ETF-classification source | Symbol validation and ETF detection served from a second source; no behaviour change while it is a fallback |
| **P4** | Production application + keys; re-probe the statement endpoints there | The statement question answered with data, then statements wired or explicitly not wired |
| **P5** (optional) | Streaming (MQTT/protobuf, 5-connection cap) and, *only after* the purchase, NOII + Footprint | A consumer that actually needs sub-second or order-flow data |

Tests keep the repo's hermetic convention: a transport seam, no network in unit tests, one
signature-vector test, one mapping test per endpoint family, one fall-through test per typed error,
plus the existing preset-completeness test.

Rollout stays zero-risk: chains unchanged unless `.env` selects Webull, keys in `.env`
(mirrored in `.env.example`), every failure degrades to the next vendor.

## Open questions (each with how to close it)

1. **Do the financial statements work in production?** The sandbox returns `[]` for all three. Close
   with a prod key (P4) and one call each to `income-statements/get`, `balance-sheets/get`,
   `cash-flows/get`.
2. **Which category values do options/futures/crypto endpoints take, and are they entitled?** They
   answered `417 UNSUPPORTED_CATEGORY` for `US_STOCK`; their reference pages carry the enums. Close
   by reading those pages, then one call each with a real contract/pair symbol.
3. **NOII parameters.** `noii-snapshots` answered `400 Parameters not valid`; the reference page
   lists the required set. Close by reading it and re-probing; then decide whether L1/L2 is needed.
4. **Depth (`stocks/depths/list`)**: `400 Parameters not valid` with a minimal parameter set -
   parameter gap, entitlement, or both. Close the same way.
5. **Price of the advanced-quotes subscription** (not published on the docs pages): the operator
   prices it on the purchase page before any P5 work. Note the measured evidence that the surfaces
   the repo actually wants (bars, snapshots, screeners, fundamentals-lite, instrument master) need
   no purchase at all.

## Recommendation

Do **P0-P3**: a US-only, basis-tagged fundamentals and bars provider is exactly the missing
piece this repo's basis work pointed at, and it is the cheapest way to get a provider that
states its period instead of merging four payloads last-writer-wins. Keep EODHD for OHLCV
breadth, keep moomoo for the non-US universe, skip the news endpoint (it is an LLM summary, not
a feed), skip the Display Solution families (wrong product for non-display analytics), and treat
streaming and NOII/Footprint as separate, later decisions.

The two things that can still kill it: entitlement economics (open question 5) and the 15-day
idle token invalidation (constraint 3) - the first is a purchase decision, the second is a
design detail that must not be allowed to break a batch.

## Appendix A — full endpoint inventory (167 operations, swept 2026-09-16)

Harvested from the 184 reference pages in Webull's `llms.txt` index and probed against the sandbox
with a real token. "not called (mutating)" = deliberately not invoked (order/account/watchlist
mutations). The `/auth/tokens/create` and `/auth/tokens/check` rows carry their measured results
rather than the sweep's skip classification.

### Auth & tokens

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| POST | `/auth/client-tokens/create` | createClientToken | not called (mutating) |
| POST | `/auth/client-tokens/refresh` | refreshClientToken | `404` — not in sandbox |
| POST | `/auth/tokens/check` | checkToken | `400` — needs a request body (token/phone) |
| POST | `/auth/tokens/create` | createToken | not called (mutating) |

### Stocks market data

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/stocks/bars/get` | barsUsingGET | `404` — not in sandbox |
| POST | `/market-data/stocks/bars/list` | historicalBars | `200` — result[1] |
| GET | `/market-data/stocks/depths/list` | quotes | `200` — asks,bids,instrument_id,quote_time,symbol |
| GET | `/market-data/stocks/footprints/list` | footprint | `400` — 400: Parameters type miss match |
| GET | `/market-data/stocks/noii-bars/list` | getNoiiBars | `400` — 400: Parameters not valid |
| GET | `/market-data/stocks/noii-snapshots/list` | getNoiiSnapshot | `400` — 400: Parameters not valid |
| GET | `/market-data/stocks/snapshots/list` | snapshot | `200` — list[1] |
| POST | `/market-data/stocks/snapshots/list` | snapshotUsingGET | `404` — not in sandbox |
| GET | `/market-data/stocks/ticks/list` | tick | `200` — result[2] |

### Fundamentals

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/fundamentals/analysis/ratings/get` | listAnalystRatingUsingGET | `200` — buy,category,effective_start_date,hold,number |
| GET | `/market-data/fundamentals/analysis/target-prices/get` | listAnalystTargetPriceUsingGET | `200` — category,currency,effective_start_date,high,low |
| GET | `/market-data/fundamentals/balance-sheets/get` | financialBalancesheet | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/capital-flows/get` | capitalFlow | `200` — list[5] |
| GET | `/market-data/fundamentals/cash-flows/get` | financialCashflow | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/company-profiles/get` | listCompanyProfileUsingGET | `200` — address,category,ceo,company_name,employees |
| GET | `/market-data/fundamentals/dividend-calendars/list` | dividendCalendar | `200` — list[2] |
| GET | `/market-data/fundamentals/earnings-calendars/list` | earningsCalendar | `200` — list[2] |
| GET | `/market-data/fundamentals/filings/list` | filings | `200` — category,filings,symbol |
| GET | `/market-data/fundamentals/financial-alerts/get` | financialAlert | `200` — currency,end_date,eps_est,eps_ly,fiscal_period |
| GET | `/market-data/fundamentals/forecast-eps/get` | forecastEps | `200` — list[5] |
| GET | `/market-data/fundamentals/fund-allocations/get` | fundAllocation | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-brief/get` | fundBrief | `200` — issuer |
| GET | `/market-data/fundamentals/fund-dividends/get` | fundDividends | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-files/get` | fundFiles | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-holdings/get` | fundHoldings | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-net-values/get` | fundNetValue | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-performances/get` | fundPerformance | `200` —  |
| GET | `/market-data/fundamentals/fund-ratings/get` | fundRating | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/fund-splits/get` | fundSplits | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/income-statements/get` | financialIncome | `200` — route live, no data in sandbox |
| GET | `/market-data/fundamentals/indicators/get` | financialIndicators | `200` — currency,values |
| GET | `/market-data/fundamentals/industry-comparisons/get` | industryComparison | `200` —  |
| POST | `/market-data/fundamentals/logos/list` | batchLogoUsingPOST | `404` — not in sandbox |

### Screener / rankings

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/screeners/gainers-losers/list` | topGainersUsingGETNew | `200` — list[200] |
| GET | `/market-data/screeners/high-dividend-ranks/list` | getHighDividend | `200` — list[200] |
| GET | `/market-data/screeners/market-sectors/get` | getMarketSectorsDetail | `200` — advanced,change_ratio,declined,flat,id |
| GET | `/market-data/screeners/market-sectors/list` | getMarketSectors | `200` — data[20] |
| GET | `/market-data/screeners/top-actives/list` | topActiveUsingGETNew | `200` — list[200] |
| GET | `/market-data/screeners/week52-high-low/list` | getWeek52HighLow | `200` — list[200] |

### Watchlists

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| POST | `/market-data/watchlists/create` | createWatchlist | `400` — 400: Request body not readable |
| POST | `/market-data/watchlists/delete` | deleteWatchlist | `417` — WATCHLIST_NOT_FOUND: The watchlist does not exist or d… |
| POST | `/market-data/watchlists/instruments/add` | addWatchlistInstruments | `417` — ILLEGAL_PARAMETER: instruments is empty. |
| GET | `/market-data/watchlists/instruments/list` | getWatchlistInstruments | `417` — WATCHLIST_NOT_FOUND: The watchlist does not exist or d… |
| POST | `/market-data/watchlists/instruments/remove` | removeWatchlistInstruments | `417` — ILLEGAL_PARAMETER: instruments is empty. |
| POST | `/market-data/watchlists/instruments/update` | updateWatchlistInstruments | `417` — ILLEGAL_PARAMETER: instruments is empty. |
| GET | `/market-data/watchlists/list` | getWatchlist | `200` — route live, no data in sandbox |
| POST | `/market-data/watchlists/update` | updateWatchlist | `417` — WATCHLIST_NOT_FOUND: The watchlist does not exist or d… |

### Futures

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/futures/bars/list` | futuresHistoricalBars | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/market-data/futures/depths/list` | futuresDepthOfBook | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/market-data/futures/footprints/list` | futuresFootprint | `400` — 400: Parameters type miss match |
| GET | `/market-data/futures/snapshots/list` | futuresSnapshot | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/market-data/futures/ticks/list` | futuresTick | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |

### Options

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/options/bars/list` | optionHistoricalBars | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/market-data/options/snapshots/list` | optionSnapshot | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/market-data/options/ticks/list` | optionTick | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |

### Crypto

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/crypto/bars/list` | cryptoBars | `400` — 400: Parameters type miss match |
| GET | `/market-data/crypto/snapshots/list` | cryptoSnapshot | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |

### Event contracts (market data)

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/event-contracts/bars/list` | eventBars | `400` — 400: Parameters type miss match |
| GET | `/market-data/event-contracts/depths/list` | eventDepth | `417` — UNSUPPORTED_SYMBOL: invalid symbols: [AAPL] |
| GET | `/market-data/event-contracts/game-stats/get` | eventGameStatsUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/live-data/get` | eventLiveDataUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/markets/bars/list` | eventMarketBarsUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/markets/bars/list-by-event` | eventMarketBarsByEventUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/markets/depths/list` | eventMarketDepthUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/markets/snapshots/list` | eventMarketSnapshotUsingGET | `404` — not in sandbox |
| GET | `/market-data/event-contracts/snapshots/list` | eventSnapshot | `417` — UNSUPPORTED_SYMBOL: invalid symbols: [AAPL] |
| GET | `/market-data/event-contracts/ticks/list` | eventTick | `417` — UNSUPPORTED_SYMBOL: invalid symbols: [AAPL] |

### News

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| POST | `/market-data/news/summaries/get` | newsSummary | `404` — not in sandbox |

### Instruments & profiles (trading API)

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/trading/instruments/crypto/profiles/list` | cryptoInstrumentList | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/trading/instruments/event-contracts/categories/list` | eventCategoriesList | `200` — list[9] |
| GET | `/trading/instruments/event-contracts/events/list` | eventEventsList | `200` — route live, no data in sandbox |
| GET | `/trading/instruments/event-contracts/markets/list` | eventMarketList | `200` — route live, no data in sandbox |
| GET | `/trading/instruments/event-contracts/series/list` | eventSeriesList | `200` — data[500] |
| GET | `/trading/instruments/futures/contracts/list` | futuresInstrumentList | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/trading/instruments/futures/product-classes/list` | futuresProductsClass | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/trading/instruments/futures/product-codes/list` | futuresProducts | `417` — UNSUPPORTED_CATEGORY: The category is not supported by… |
| GET | `/trading/instruments/stocks/profiles/list` | instrumentList | `200` — data[1000] |

### Accounts / orders / assets (trading API)

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/trading/accounts/list` | accountList | `200` — list[5] |
| GET | `/trading/activities/cash-activities/list` | tradeCashActivityByType | `403` — ACCOUNT_ACCESS_DENIED |
| GET | `/trading/assets/balances/get` | accountBalance | `403` — ACCOUNT_ACCESS_DENIED |
| GET | `/trading/assets/positions/list` | accountPosition | `403` — ACCOUNT_ACCESS_DENIED |
| POST | `/trading/orders/batch-place` | Order Batch Place | not called (mutating) |
| POST | `/trading/orders/cancel` | Common Order Cancel | not called (mutating) |
| GET | `/trading/orders/get` | orderDetail | `403` — ACCOUNT_ACCESS_DENIED |
| GET | `/trading/orders/historical-orders/list` | orderHistory | `403` — ACCOUNT_ACCESS_DENIED |
| GET | `/trading/orders/open-orders/list` | orderOpen | `403` — ACCOUNT_ACCESS_DENIED |
| POST | `/trading/orders/place` | Common Order Place | not called (mutating) |
| POST | `/trading/orders/preview` | Common Order Preview | not called (mutating) |
| POST | `/trading/orders/replace` | Common Order Replace | not called (mutating) |

### Broker / Display Solution

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/broker/accounts/applications/get` | getAccountApplicationDetail | `404` — not in sandbox |
| POST | `/broker/accounts/close` | closeAccount | `404` — not in sandbox |
| POST | `/broker/accounts/create` | createAccountApply | not called (mutating) |
| GET | `/broker/accounts/get` | getAccountDetail | `404` — not in sandbox |
| GET | `/broker/accounts/list` | listAccounts | `404` — not in sandbox |
| POST | `/broker/accounts/update` | updateAccountApply | not called (mutating) |
| GET | `/broker/activities/cash-activities/list` | brokerCashActivityByType | `404` — not in sandbox |
| GET | `/broker/agreements/get` | brokerGetAgreementDetails | not called (mutating) |
| GET | `/broker/agreements/list` | brokerListAgreementsByType | not called (mutating) |
| GET | `/broker/assets/balances/get` | accountBalance | `404` — not in sandbox |
| GET | `/broker/assets/positions/list` | accountPosition | `404` — not in sandbox |
| GET | `/broker/assets/summaries/get` | summary | `404` — not in sandbox |
| POST | `/broker/credits/create` | brokerFundingCreditCreate | not called (mutating) |
| GET | `/broker/credits/get` | brokerFundingCreditQuery | not called (mutating) |
| GET | `/broker/documents/download` | documentDownload | not called (mutating) |
| POST | `/broker/documents/upload` | documentUpload | not called (mutating) |
| POST | `/broker/fees/create` | brokerFundingFeeCreate | not called (mutating) |
| GET | `/broker/fees/get` | brokerFundingFeeQuery | not called (mutating) |
| GET | `/broker/forms/get` | getFormContent | `404` — not in sandbox |
| GET | `/broker/forms/list` | getFormList | `404` — not in sandbox |
| GET | `/broker/forms/versions/list` | getFormVersionList | `404` — not in sandbox |
| POST | `/broker/funding/ach-relationships/create` | createAchRelationship | not called (mutating) |
| POST | `/broker/funding/ach-relationships/delete` | deleteAchRelationship | not called (mutating) |
| GET | `/broker/funding/ach-relationships/list` | listAchRelationships | not called (mutating) |
| POST | `/broker/funding/bank-relationships/create` | createBankRelationship | not called (mutating) |
| POST | `/broker/funding/bank-relationships/delete` | deleteBankRelationship | not called (mutating) |
| GET | `/broker/funding/bank-relationships/list` | listLinkedBankAccounts | not called (mutating) |
| POST | `/broker/funding/instant-funding/create` | brokerFundingInstantCreate | not called (mutating) |
| GET | `/broker/funding/instant-funding/get` | brokerFundingInstantQuery | not called (mutating) |
| POST | `/broker/funding/transfers/cancel` | cancelTransfer | not called (mutating) |
| POST | `/broker/funding/transfers/create` | createTransfer | not called (mutating) |
| GET | `/broker/funding/transfers/get` | transferDetail | not called (mutating) |
| GET | `/broker/funding/transfers/list` | transferList | not called (mutating) |
| GET | `/broker/instruments/event-contracts/categories/list` | brokerEventCategoriesList | `404` — not in sandbox |
| GET | `/broker/instruments/event-contracts/events/list` | brokerEventEventsList | `404` — not in sandbox |
| GET | `/broker/instruments/event-contracts/markets/list` | brokerEventMarketList | `404` — not in sandbox |
| GET | `/broker/instruments/event-contracts/series/list` | brokerEventSeriesList | `404` — not in sandbox |
| GET | `/broker/instruments/stocks/corporate-actions/get` | brokerCorporateActionsDetail | `404` — not in sandbox |
| GET | `/broker/instruments/stocks/profiles/list` | listStockInstruments | `404` — not in sandbox |
| POST | `/broker/journals/cash-journals/create` | brokerJournalCashCreate | not called (mutating) |
| GET | `/broker/journals/cash-journals/get` | brokerJournalCashQuery | `404` — not in sandbox |
| GET | `/broker/master-data/enums/list` | listEnums | `404` — not in sandbox |
| GET | `/broker/master-data/trading-calendars/list` | listTradeCalendar | `404` — not in sandbox |
| POST | `/broker/orders/cancel` | Common Order Cancel | not called (mutating) |
| GET | `/broker/orders/get` | orderDetail | `404` — not in sandbox |
| GET | `/broker/orders/historical-orders/list` | orderHistory | `404` — not in sandbox |
| GET | `/broker/orders/open-orders/list` | orderOpen | `404` — not in sandbox |
| POST | `/broker/orders/place` | Common Order Place | not called (mutating) |
| POST | `/broker/orders/preview` | Common Order Preview | not called (mutating) |
| POST | `/broker/orders/replace` | Common Order Replace | not called (mutating) |

### Connect API (OAuth)

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/oauth2/auth-codes/get` | getAuthorizationCode | `404` — not in sandbox |
| POST | `/oauth2/tokens/create` | CreateAndRefreshToken | not called (mutating) |

### Other

| Method | Path | What it is | Sandbox result |
|---|---|---|---|
| GET | `/market-data/instruments/event-contracts/categories/tags/list` | allTagsUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/event-contracts/events/list` | eventListUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/event-contracts/milestones/list` | milestonesUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/event-contracts/series/list` | seriesListUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/event-contracts/sports-filters/list` | sportsFilterUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/stocks/corporate-actions/list` | corpActionUsingGET | `404` — not in sandbox |
| GET | `/market-data/instruments/stocks/corporate-actions/list-by-market` | corpMarketUsingGET | `404` — not in sandbox |
| POST | `/market-data/instruments/stocks/profiles/list` | listUsingGET | `404` — not in sandbox |
| POST | `/market-data/streaming/subscribe` | subscribeUsingPOST | not called (mutating) |
| POST | `/market-data/streaming/unsubscribe` | unsubscribeUsingPOST | not called (mutating) |
