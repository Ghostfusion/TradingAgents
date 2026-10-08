# Design: Longbridge (Longport) OpenAPI as a data provider

State 2026-10-08. Sources are Longbridge's own documentation
([open.longbridge.com/docs](https://open.longbridge.com/docs), the full page
index at [`/llms.txt`](https://open.longbridge.com/llms.txt), read 2026-10-08)
plus a live probe of the credentials the owner supplied that day. **No code
changed by this document.**

## Verdict

**Not worth wiring as a data vendor — the US catalogue is redundant with the
chains in force, and the surface that *is* unique has no consumer.**

Three findings decide it, in order of weight:

1. **The credentials supplied cannot authenticate.** The app key + app secret
   alone are not a credential set; the SDK requires a third value (see
   *Probed* below). Everything past authentication is therefore still
   documentation, not measurement.
2. **The project is US-first and Longbridge's US coverage is a near-total
   overlap.** Every US category it carries — bars, fundamentals, statements,
   valuations, analyst consensus, calendars, screener, short interest, options,
   news — is already routed to two-to-five vendors (`interface.py`
   `VENDOR_METHODS`). A sixth US source for the same reads buys nothing.
3. **Its genuinely unique surface is HK/CN** — HK kline/depth, the CCASS broker
   queue, HK short positions, warrants and CBBCs, the A/H premium, CN indices —
   and **no consumer exists for any of it**: `Strategies/preferred_universe.txt`
   is US-listed preferred/hybrid shares (30 lines, **zero** `.HK`/`.SS`/`.SZ`
   symbols), and `docs/design_daily_stock_analysis_research.md` §4 records *"No
   A-share data pipeline … the fork is US-first; adopt the routing/health/resume
   patterns, not the sources"* as a standing non-goal.

**One line stays on the candidate list.** `QuoteContext.capital_flow` +
`capital_distribution` cover **US and HK**, and `get_capital_flow` is routed to
**`moomoo` alone** (`interface.py`: `"get_capital_flow": {"moomoo": …}`) — a
single-vendor category with a single point of failure. That is the same gap the
Webull study called the highest-value single entry
(`docs/design_webull_data_provider.md`), and it is a **resilience** win, not a
new capability. It still needs the token, and the docs mark it
`<QuotePermission command="capital" />` — a quote permission, not merely a key.

**Licence: non-commercial, personal use only.** The
[HK API Non-Commercial Licence Agreement](https://open.longbridge.com/docs/legal/api-license-agreement-hk)
grants a "personal, revocable, royalty-free, non-exclusive, non-sublicensable,
non-transferable, restricted right … solely for Non-Commercial Purposes", where
that means "for your personal use" with no commercial application "regardless of
whether You receive any consideration". Personal research is in scope; anything
resold or server-side for others is not. This belongs beside the repo's open
licence-tier question (FL-8 §11.3), not in front of it.

## Probed: the credentials are incomplete

The app key + app secret the owner supplied on 2026-10-08 are **two of the three
values the legacy flow needs**. `LONGBRIDGE_ACCESS_TOKEN` is a separate
credential — the "application credential" shown in the
[User Center](https://open.longbridge.com/), explicitly *not* the OAuth access
token. Probed against the installed SDK (`longbridge`, Python 3.12) with the key
and secret set and no token:

```text
Config.from_apikey_env()
  -> OpenApiException: missing environment variable: LONGBRIDGE_ACCESS_TOKEN

Config.from_apikey(app_key, app_secret, "")
  -> Config built, but the call fails:
     OpenApiException: (kind=ErrorKind.OpenApi, code=401001, trace_id=…)
     token empty
```

So `Config` accepts an empty token and the **server** rejects it — `401001 token
empty`. To go further the owner must supply either (a) the legacy
`LONGBRIDGE_ACCESS_TOKEN` from the User Center, or (b) an OAuth `client_id` plus
a browser authorisation (`OAuthBuilder(...).build(...)` → `Config.from_oauth`).
**Neither can be fabricated and neither is in the repo.**

## Verified API facts

| Fact | Value | Source |
|---|---|---|
| Product | Longbridge OpenAPI, i.e. the Longport SDK/platform after the rename | [docs](https://open.longbridge.com/docs) |
| Python package | `longbridge` (the old `longport` package is deprecated — uninstall before installing) | [sdk](https://open.longbridge.com/sdk) |
| SDK shape | Rust core with Python/Node/Java/C++/Go bindings; one wheel, no pure-Python fallback | sdk |
| HTTP host | `https://openapi.longbridge.com` (`.cn` mirror for mainland routing) | [getting-started](https://open.longbridge.com/docs/getting-started) |
| WS hosts | quote `wss://openapi-quote.longbridge.com/v2`, trade `wss://openapi-trade.longbridge.com/v2` | getting-started |
| Auth (legacy) | `LONGBRIDGE_APP_KEY` + `LONGBRIDGE_APP_SECRET` + `LONGBRIDGE_ACCESS_TOKEN` | getting-started |
| Auth (OAuth 2.0, recommended) | `client_id` + browser authorisation + persisted, auto-refreshed bearer token | getting-started |
| Data centres | `ap` (Longbridge SG/HK) and `us` (US accounts); `.cn` has no route to `us`, and US accounts must use `.cn`-less `.com` — several fundamental methods are **US-data-centre only** | getting-started |
| Quote rate limit | one long connection; ≤ 500 subscribed symbols; ≤ 10 calls/second; ≤ 5 concurrent (the SDK self-throttles `QuoteContext`) | [docs §rate-limit](https://open.longbridge.com/docs) |
| Trade rate limit | ≤ 30 calls per 30 s, ≥ 0.02 s apart (SDK does **not** throttle these) | docs §rate-limit |
| Cost | no fee for the API itself; quote-data subscriptions are separate and paid | docs §pricing |
| Prerequisite | an opened Longbridge brokerage account + developer verification | docs §how-to-enable |
| Licence | Non-Commercial, personal use, HK law and exclusive HK jurisdiction | licence agreement |
| Quote coverage | HK: equities/ETFs/warrants/CBBCs + HSI. US: stocks/ETFs + Nasdaq + **OPRA options**. CN: securities + index | docs |
| Trade coverage | HK: stock/ETF + warrant/CBBC. US: stock/ETF + warrant/CBBC + options | docs |

## The catalogue against the chains in force

Read through the app's own loader (`DEFAULT_CONFIG['tool_vendors']` /
`interface.py` `VENDOR_METHODS`). "Redundant" means the category already has a
working chain and Longbridge would be one more member of it.

| Longbridge surface | Routed today to | Reading |
|---|---|---|
| Historical/real-time candlesticks, depth, intraday, ticks | `get_stock_data` / OHLCV refresh: yfinance, moomoo, alpha_vantage, massive | redundant |
| US option chain + quotes (OPRA) | `get_options_chain`: yfinance, moomoo; `get_options_surface`: CBOE (delayed) | redundant, and needs a paid non-display entitlement |
| Short positions (US FINRA bi-monthly / HK daily) | `get_short_interest`: yfinance, moomoo, massive | redundant for US; the HK rows have no consumer |
| **Capital flow + capital distribution** | `get_capital_flow`: **moomoo only** | **the one additive entry** — a second vendor in a single-vendor category |
| Fundamentals: profile, statements/reports, key metrics, valuations, valuation history, industry peers/rank/valuation, dividends, buyback, corporate actions, executives, shareholders, fund holdings, business segments | SEC EDGAR, FMP, alpha_vantage, EODHD, finnhub; `price_targets` for targets | redundant (several are US-DC-only anyway) |
| Analyst consensus / institution ratings / forecast EPS | finnhub, FMP, alpha_vantage, `price_targets` | redundant |
| Calendars: earnings, dividend, IPO, macro, meeting, merge, split | `event_calendars` (FDA/court etc.), yfinance | redundant |
| Screener + indicators + preset strategies; rank list; market temperature; top movers; unusual items | `screener.py` (yfinance), `value_screener`, `market_panel`, market movers | redundant |
| Broker queue / broker holdings / participants (CCASS) | — nothing | HK-only, no consumer |
| A/H premium (+ intraday) | — nothing | CN/HK cross-listing, no consumer (no A-share pipeline) |
| Warrants / CBBCs: filter, quotes, issuers | — nothing | HK derivatives, no consumer |
| HK short-selling volume/balance | — nothing | HK-only, no consumer |
| Security news; community topics | reddit, stocktwits, seekingalpha, newsapi, gdelt, benzinga, yfinance/alpha_vantage news | redundant (stocktwits already is the social read) |
| Trade + account: orders, executions, positions, assets, margin ratio, cash flow, DCA, alerts, watchlist, sharelists | the executor is paper (`TradingExecution/signald`); Alpaca is the portfolio side | **not a data-provider question** — live broker order placement is a policy decision |
| CLI (`longbridge`) and MCP server | the repo has its own tool surface | not adopted; no code consequence |

## Explicit exclusions

- **Do not add it for HK/CN data.** There is no consumer: the universe is
  US-only and the A/HK pipeline is a recorded non-goal. Adding the vendor first
  and the market later is the backwards half of rule 7.
- **Do not add it for US fundamentals, options, short interest, screener or
  calendars.** Each category already has a chain; a new member with a paid
  entitlement and a third credential is strictly more to break for the same read.
- **Do not wire the trade API** without a separate owner decision. It is a
  brokerage integration carrying real money, and the repo's executor is
  deliberately a paper one.
- **Do not treat the licence as settled** because the API is free. It is free
  *because* it is non-commercial.

## If the owner wants it wired

1. Supply `LONGBRIDGE_ACCESS_TOKEN` (User Center) or an OAuth `client_id`; then
   re-run the probe above to reach a real response before writing anything.
2. The only entry worth landing first is a second `get_capital_flow` vendor.
   Note the shape difference: moomoo's read is a **weekly net split by order
   size** (super/big/mid/small) plus a session distribution, while Longbridge's
   `capital_flow` is a **per-minute intraday inflow** series and
   `capital_distribution` is the size split — the two must not be blended
   silently (the C3 rule: one parse, so the prose and the signal cannot
   disagree).
3. Ship it as an **optional extra** (the SDK is a Rust wheel) that degrades to a
   typed reason when the key or the quote permission is absent, so the chain
   advances instead of returning an empty table.

## During this check

No code changed. Two side effects, both local: the `longbridge` SDK was
installed into the live `py -3.12` environment to run the auth probe, and the app
key + secret were written to the gitignored `.env` (`LONGBRIDGE_APP_KEY`,
`LONGBRIDGE_APP_SECRET`) so the probe could read them. Nothing was committed to
`.env.example` — no code reads those names yet, and that file mirrors
*code-read* keys only.
