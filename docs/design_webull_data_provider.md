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

## Empirical probe (2026-09-16, no credentials available)

Measured before writing P0, on this workstation (signer implemented from the signature page and
self-tested against the vendor's own published vector, which it reproduces exactly:
`kvlS6opdZDhEBo5jq40nHYXaLvM=`).

**What the probe proves.**

| Probe | Result | Reading |
|---|---|---|
| `POST {sandbox}/market-data/stocks/bars/list` unsigned | `401 {"error_code":"MISSING_APP_KEY","message":"Header x-app-key is missing."}` | route exists; auth is enforced first |
| `POST {sandbox}/market-data/nonsense/xyz` unsigned | `404 {"error_msg":"404 Route Not Found"}` | unknown routes are 404, so a 401 means the route is real |
| `POST {sandbox}/auth/tokens/create` unsigned | `401 MISSING_APP_KEY` | the token route exists at the **unprefixed** path |
| `POST {sandbox}/openapi/auth/tokens/create` unsigned | `404` | the `/openapi` prefix does **not** apply to the auth route |
| any path under `{sandbox}/openapi/market-data/...` unsigned (including nonsense) | `401 MISSING_APP_KEY` | that prefix is an auth-first gateway - a 401 there says nothing about the specific route |
| `POST {prod}/market-data/stocks/bars/list` unsigned | `404` | production does **not** serve the unprefixed market-data path |
| `POST {prod}/openapi/market-data/stocks/bars/list` unsigned | `401 MISSING_APP_KEY` | production's market-data gateway lives under `/openapi` |
| signed with a syntactically valid but unknown key (both hosts) | `401 {"error_code":"UNAUTHORIZED","message":"Invalid credentials. Please verify your credentials and ensure you are connecting to the correct environment"}` | the signature scheme is parsed; only the key is rejected |

**Two corrections to what the documentation alone implied.**

1. **The path prefix is per-environment, not an inconsistency.** Reference pages use
   `/market-data/...` (their `servers` block is the sandbox host) and the Data API example uses
   `/openapi/market-data/...`: both are real. The sandbox serves the unprefixed paths, production
   serves the prefixed ones. Hand-rolled code must switch the prefix with the host; the SDK
   already does.
2. **Auth precedes entitlement, so this probe cannot answer the subscription question.** The
   go/no-go still requires one valid sandbox key. The probe script that answers it is written and
   self-tested (it creates a token, then reads bars/snapshot/income/ratings/capital-flow/news/
   instruments and prints an explicit entitlement verdict); it lives outside the repo as a
   throwaway until P1 promotes it.

**Error envelopes the provider must parse (two shapes).** `401` and `417` carry
`{"error_code": ..., "message": ...}` (`MISSING_APP_KEY`, `UNAUTHORIZED`, `INVALID_PARAMETER`);
an unrouted path carries `{"error_msg": "404 Route Not Found"}`. Map the first to typed
`WebullAuthError`/`WebullPermissionError`, the second to `NoMarketDataError` rather than crashing on
`KeyError`.

**Token facts confirmed from the endpoint spec** (`/auth/tokens/create`): the response is
`{token (32-hex), expires_at (unix ms), status (PENDING|NORMAL|INVALID|EXPIRED)}`. The docs make two
statements about the 15-day figure - the token page says a token becomes `INVALID` after 15
consecutive days without API calls, the endpoint page says tokens are time-sensitive with a default
15-day expiry. Treat both as real until a live token says otherwise: check status before a run and
persist the token under `data_cache_dir/`.

## Fit against this repo's `data_vendors` categories

| Category | Webull endpoint | Verdict |
|---|---|---|
| `core_stock_apis` | bars (batch 20), snapshot | **Strong** (US only); the D-bars are forward-adjusted, M-bars unadjusted - journal which |
| `fundamental_data` | income / cashflow / balance sheet, indicators, company profile | **Strongest fit** - basis- and publish-date-tagged rows |
| `analyst_ratings` | analyst rating, analyst target price | **Strong** |
| `earnings_calendar` | earnings calendar, dividend calendar | **Strong** |
| `capital_flow` | capital flow distribution | **Strong** (currently moomoo-only) |
| `market_movers` / `equity_screener` | top gainers/losers, most active, market sectors (+detail), high dividend, 52-week high/low | **Partial** (rankings, not a screener DSL) |
| `options_data` | option tick / snapshot / historical bars | **Partial** - no chain summary or greeks; needs the OPRA non-display subscription |
| `corporate_actions` | corporate actions (Display Solution family) | **Partial** - note the Display-Solution caveat below |
| `prediction_markets` | event contracts | **Unproven** - verify breadth before touching that chain; it is not a Polymarket substitute |
| `sec_filings` | filings | **Low value** - `sec_edgar` is free and already wired |
| `news_data` / `news_sentiment` | news summary (LLM SSE) | **No** - not a headline feed; an LLM summary inside an LLM pipeline is circular |
| `technical_indicators` | - | **No** - but irrelevant: the repo computes indicators locally from OHLCV |
| `macro_data`, `exchange_symbols`, `short_interest`, `institution_data`, `insider_transactions` | - | **No endpoint** |

**Display Solution families are a different product.** The `broker-market-data-api/*` endpoints
(client token, watchlists, logos, some corporate actions, some ratings) exist for *displaying*
data to end users of a broker platform. A non-display analytics pipeline should use the primary
families and the non-display entitlement, not those endpoints.

**A genuinely additive surface, not a substitution:** NOII bars/snapshot (net order imbalance,
i.e. auction imbalance) and Footprint (order-flow volume profile). Neither has a counterpart in
the current chains; the market analyst could use NOII for open/close auction context. Treat as a
separate, later proposal with its own evidence requirements - not as part of this integration.

## Constraints and blockers

1. **US-only.** `US_STOCK`/`US_ETF` categories, US options/futures/event contracts. `0700.HK`,
   `7203.T`, `BTC-USD` etc. have no path here. In this repo that is fine and already modelled:
   `dataflows/moomoo.py` raises `NoMarketDataError` for an unmapped symbol and the router falls
   through to the next vendor. Webull must behave identically.
2. **Real-time is a separately-purchased Nasdaq non-display subscription**, and app/QT
   subscriptions do not count. **Only one device may use L1/L2 at a time** - a batch of 4 workers
   *is* multiple consumers, so either every worker shares one HTTP path (it does: bars are
   snapshots, not a stream) or the operator's Webull app must not be streaming the same
   entitlement during a run. Worth an explicit note in the runbook.
3. **Token lifecycle is a real operational sharp edge for an on-demand tool.** Production tokens
   need in-app SMS verification within 5 minutes when created, and go `INVALID` after **15
   consecutive days without API calls** - a tool that runs on demand will hit that. Mitigations:
   persist the token under `data_cache_dir/`, check status before a run, and treat an invalid
   token as a typed auth error that falls back to the next vendor rather than failing the batch.
   **Sandbox tokens need no 2FA** - the development and CI-shaped path is clean.
4. **Per-endpoint limits are tighter than the global one** (60 req/60s for income statements).
   A provider-level limiter must respect the tightest budget it uses, not just 300/min.
5. **No fundamentals for ETFs in the statement family** (ETF coverage is the `Fund*`
   endpoints: brief, performance, net value, holdings, dividends, rating, splits, allocation,
   files). `IEI`-style names need their own mapping, or they fall through to the current vendor.

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

## Implementation plan

| Phase | Work | Acceptance |
|---|---|---|
| **P0** (operator, no code) | Create a Webull account, apply for the **sandbox** API (auto-approved, minutes), generate App Key/Secret. Decide on the production app (1-2 days) and on buying Nasdaq Basic/Totalview **non-display**. | Keys in `.env`; someone has answered "can the sandbox serve US daily bars at all?" (see open question 1) |
| **P1** | `webull_common.py` + a `--once`-style smoke script (not in the batch path). | Signature conformance test passes against the documented vector; token persist/check works; limiter math unit-tested; a live sandbox call returns bars |
| **P2** | `webull.py` bars + snapshot; chain adding Webull **last** in `core_stock_apis`; `--vendor webull` preset in `batch.py`. | Same-symbol OHLCV agrees with the primary vendor within tolerance on N symbols; `tests/test_batch_vendor_preset.py` still passes (a preset must cover every category key); fallback proven by simulating a 403 |
| **P3** | Fundamentals family into `fundamental_data` as a **co-equal head** (`webull,moomoo,yfinance,...`) and `analyst_ratings`/`earnings_calendar`/`capital_flow`. | A report tree whose `statement_parsing` reads a period-tagged series, and whose `verify_flags.json` `basis` registry shows provider-sourced `fy_annual`/`quarterly` instead of `level` fallbacks |
| **P4** (optional) | MQTT streaming (protobuf, 5-connection cap, no resubscribe on reconnect). | Only if a consumer needs sub-second quotes; the research pipeline does not |
| **P5** (optional) | NOII / Footprint as additive tools | Separate proposal with its own evidence plan |

Tests follow the repo's hermetic convention: a transport seam injected into `WebullSession`, no
network in unit tests, one signature vector test, one mapping test per endpoint, one fallback
test per typed error, and the existing preset-completeness test extended.

Rollout is zero-risk by construction: chains are unchanged unless `.env` selects Webull, keys
live in `.env` (mirrored in `.env.example`), and every failure degrades to the next vendor.

## Open questions (each with how to close it)

1. **Does the sandbox serve US daily bars and statements without a paid entitlement?** The
   overview says non-display OpenAPI usage requires Nasdaq Basic/Totalview, while the sandbox is
   documented as 15-minute delayed "by default" - these two statements only reconcile if the
   sandbox is usable unentitled. **This is the go/no-go for the whole integration** and it costs
   one P0 smoke call to answer - the probe for it is written and self-tested (creates a token,
   then reads bars/snapshot/income/ratings/capital-flow/news/instruments and prints an
   entitlement verdict); it only needs `WEBULL_APP_KEY`/`WEBULL_APP_SECRET` from an
   auto-approved sandbox application.
2. Are statements available for ETFs, or only the `Fund*` family? (Affects `IEI`-style names.)
3. Is `Filings` metadata-only, and does it add anything over `sec_edgar`? (Probably not - default: skip.)
4. Is the event-contract universe broad enough to be a `prediction_markets` source, or is it
   Webull's own product set? (Default: leave that chain alone.)
5. Subscription price for Nasdaq Basic/Totalview non-display: not published on the docs pages;
   the operator must price it on the purchase page before P2 goes to production.

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
