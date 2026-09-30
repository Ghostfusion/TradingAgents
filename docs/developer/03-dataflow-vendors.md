# 3. Dataflow layer: vendors, routing, errors, cache

This is how data reaches the analyst tool loops. It is the **vendor contract**
layer described in `docs/api_reference.md` §6. Everything here flows through
`tradingagents/dataflows/interface.py`.

## 3.1 The single entry point: `route_to_vendor(method, *args, **kwargs)`

All data tools in `agents/utils/*_tools.py` call this. It:

```
route_to_vendor(method, ...)
  1. get_category_for_method(method)      -> which TOOLS_CATEGORIES group
  2. get_vendor(category, method)          -> the configured vendor string
     (tool_vendors[method] wins over data_vendors[category])
  3. vendor_chain = split(",") of the configured string
     ("moomoo,yfinance", "default", or "none")
  4. check vendor_cache (TTL 6h; news excluded)
  5. for each vendor in the chain:
        call VENDOR_METHODS[method][vendor](*args, **kwargs)
        returns on successful non-sentinel result (cache it)
        catches VendorRateLimit / VendorNotConfigured / NoMarketData / generic
        -> continue to next vendor
  6. if no data: return NO_DATA_AVAILABLE / DATA_UNAVAILABLE / DATA_DISABLED
     (a total vendor outage degrades EVERY category to DATA_UNAVAILABLE,
     including the flow-critical ones - get_stock_data, get_indicators,
     the statement tools, news - so the run never aborts on a ToolNode
     exception; per-vendor failures are always logged, never silent)
```

**Key invariants**

- The configured chain is the **only** chain used. It never silently falls back
  to an un-listed vendor (that prevented cross-vendor inconsistency).
- A vendor setting of `"none"` / `"off"` / `"disabled"` disables that whole
  category (returns `DATA_DISABLED`).
- Every category degrades to a sentinel on a vendor outage (2026-09 outage
  hardening): flow-critical categories (core_stock_apis, technical_indicators,
  fundamental_data, news_data) were moved into `OPTIONAL_CATEGORIES` so a
  rate-limit / network storm produces `DATA_UNAVAILABLE` and the agent reports
  "unavailable" instead of aborting the run. Clean no-data and disabled-config
  sentinels are unchanged; vendor failure logs remain the audit trail.
- Successful results are cached in `vendor_cache` (skip category `news_data`).

### 3.1b Vendor failure policy — the retained design and the endorsed rules

**Status: the current design is retained.** Nothing here re-architects the
router — the configured chain is still the only chain, a failure still degrades
through the typed taxonomy to the next vendor, and no chain order or gate
default changes. What follows is the *policy* that behaviour is meant to
implement, recorded so a future change can be judged against it instead of
guessed at.

#### Retained design (do not "fix" these)

| element | where | why it stays |
| --- | --- | --- |
| Typed errors; no retry on 401/403 | `errors.py`; the router catches by *type* | a key/plan verdict is permanent for the process — retrying it only burns quota |
| Bounded retry on 429/5xx, then fall through | each vendor loop (`_MAX_RETRIES`, `2*(attempt+1)`) | a transient condition deserves one bounded attempt, never an unbounded storm |
| Sentinels + typed `absence` reason | `interface.route_to_vendor_typed` | degradation must be *observable*, not silent |
| Sentinel results are **not** cached | `vendor_cache` `_SENTINEL_PREFIXES` | a degraded result must never be replayed as a success |
| Vendor failure logs are the audit trail | `interface.py` `Vendor %r failed for %s` | the one forensic record of what a run could not get |

#### Endorsed response rules

| signal | response |
| --- | --- |
| **401/403** (key/plan) | don't retry · **remember it** for the process (negative cache, per vendor + endpoint) · don't keep that vendor ahead in that method's chain |
| **429 / 5xx** | bounded backoff honouring `Retry-After` where the vendor sends it, then skip **and** count toward the breaker |
| **any fall-through** | carry `source` + caliber — availability may degrade, identity may not |
| **panel / relative legs** | one source per panel, or drop the member and shrink `coverage` **with a reason** |

#### The one thing the design was missing, and how it is now wired

The failure mode was not "skip to the next vendor" — that is correct. It was
**re-asking a refusal already known**. Measured 2026-09-30 across one set of
batch logs: **575** FMP `profile` 429s, **60** Massive snapshot 403s (30
`gainers` + 30 per-ticker) and **26** Finnhub `get_analyst_ratings` 403s.

`vendor_breaker.py` already held both mechanisms
(`mark_capability_absent`/`capability_available` with
`DEFAULT_NEGATIVE_TTL_SECONDS = 900`, and `record_failure`/`allow_call`), but it
was consulted only on the `enable_market_routing` path. Four thin helpers now
expose it to the vendor modules themselves, market-free
(`ANY_MARKET = "*"` — a scope deliberately separate from the market-routing key):

- `vendor_skip_reason(vendor, capability)` → `"absent"` (a 401/403 verdict) |
  `"breaker"` (open after repeated transient failures) | `None`. The two are
  distinguishable **on purpose**: the vendor must raise
  `VendorNotConfiguredError`/`NoMarketDataError` for `"absent"` but let
  `VendorRateLimitError` **propagate** for `"breaker"` — otherwise a transient
  throttle would be reported as a served advisory "unavailable".
- `note_vendor_refused` / `note_vendor_transient` / `note_vendor_ok` record the
  outcome.

Wired at the three chokepoints that produced the measured refused calls:

| module | capability key | marked on |
| --- | --- | --- |
| `fmp_common.fmp_get` | the endpoint `path` | 401/403 → refused; terminal 429/5xx → transient; 200 → ok |
| `massive._get` | `_capability(path)` — the path minus a trailing symbol, so `.../tickers/ZM` and `.../tickers/NVDA` share one entry | same |
| `finnhub.get_analyst_ratings_finnhub` | `"analyst-ratings"` | `FinnhubAPIException` 401/403 → refused |

The capability is the **endpoint, never the symbol**: a plan gates per endpoint,
so keying per symbol would need a new entry for every name in the universe and
would never suppress the re-ask.

`tests/conftest.py::_isolate_config` resets the gate before and after every test
— it is process-global, so one test's 403 would otherwise silence that vendor
for the rest of the session.

**Left open, by decision** (both change routing behaviour and are the owner's
call): dropping a plan-blocked vendor from a chain's order (the last clause of
rule 1), and moving the market-routing breaker off its default-off switch.

## 3.2 `TOOLS_CATEGORIES`, `VENDOR_LIST`, `VENDOR_METHODS`

- `TOOLS_CATEGORIES`: group -> {tools}. e.g. `fundamental_data` has
  `get_fundamentals`, `get_balance_sheet`, ...
- `VENDOR_LIST`: the flat set of vendors
  (`yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo,
  massive`).
- `VENDOR_METHODS[method][vendor]`: implementations. A method may have multiple
  vendors (fallback chain) or one vendor.

**Moomoo per-call timeout**: every moomoo SDK call runs under a wall-clock
timeout wrapper (`dataflows/moomoo.py::_sdk_call`, default 5s,
`moomoo_call_timeout` / `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`). The SDK's own
`ReqInfo.wait()` allows 20s per call; a degraded gateway can burn 20s per call
across hundreds of calls (the value screener's gating pass makes ~7
calls/symbol), which is how a web job hits its subprocess budget. On expiry the
wrapper raises `VendorRateLimitError` and closes the thread's context so the
in-flight request unblocks.

## 3.3 Vendor data contract

When you add a new vendor (e.g. a new REST source):

1. Put functions in `dataflows/<vendor>.py` that match the method signature and
   return a **string** (the LLM sees text, not a dict).
2. Register it in `interface.py`:
   - import the function in the top block,
   - add to the relevant `TOOLS_CATEGORIES` "tools" list,
   - add `VENDOR_METHODS[method][<vendor>] = <func>`,
   - if optional, add the category to `OPTIONAL_CATEGORIES`.
3. Add the chain in `default_config.data_vendors[category]`
   (e.g. `"yfinance,massive"`; `"default"` = all available).
4. Wrap as a LangChain `@tool` in `agents/utils/*_tools.py`; bind to the
   analyst's tool node + prompt in `graph` + `agents/*`.
5. Return sentinel strings, never empty strings, for "no data" so the agent
   reports "unavailable" rather than fabricating.

## 3.4 Errors — `dataflows/errors.py`

```
VendorError
├── NoMarketDataError          (empty or stale rows -> skip to next vendor)
├── VendorRateLimitError      (transient 429 -> skip to next vendor)
└── VendorNotConfiguredError  (missing key/config -> vendor unavailable)
```

The router catches these by *type*, so a new vendor raises the base classes
and needs no new except clause.

## 3.5 Config — `dataflows/config.py`

Thread-local to keep concurrent batch workers isolated:
- `initialize_config()` / `get_config()` (deep copy) / `set_config(partial)`
  / `reset_config()`.

All tools read through `get_config()`. `initialize_config()` populates from
`DEFAULT_CONFIG` — shipped defaults **plus** the ambient `TRADINGAGENTS_*`
environment, i.e. what this machine runs; `reset_config()`, the test-isolation
path, restores `SHIPPED_DEFAULTS` instead, so a developer's `.env` cannot leak
into a test.

## 3.6 Cache — `dataflows/vendor_cache.py`

Disk TTL cache (6h default), keyed by method + args; network fetch skipped on
hit. Categories in `vendor_cache_skip_categories` (news_data) are never
cached. Sentinels (NO_DATA / DATA_UNAVAILABLE) are not cached as success.

## 3.7 Symbol mapping — `dataflows/symbol_utils.py`

`normalize_symbol()` maps broker symbols to Yahoo-style gold `XAUUSD -> GC=F`,
forex `EURUSD -> EURUSD=X`, crypto `BTCUSD -> BTC-USD`, indices `SPX500 ->
^GSPC`.

## 3.8 The Massive.com vendor

`dataflows/massive.py` follows the same contract (`_get`, typed errors,
`NoMarketDataError`). It exposes many endpoints — see
[`09-massive-integration.md`](09-massive-integration.md). It registers
`massive` in several categories and adds derived tools.

For the full **catalog of every provider/source** (routed vendors, direct
sources, Massive sub-modules, API keys, per-category chains), see
[`12-data-providers.md`](12-data-providers.md).

Continue to [`04-strategies.md`](04-strategies.md).