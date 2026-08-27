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
     (or re-raise the first error for a non-optional category)
```

**Key invariants**

- The configured chain is the **only** chain used. It never silently falls back
  to an un-listed vendor (that prevented cross-vendor inconsistency).
- A vendor setting of `"none"` / `"off"` / `"disabled"` disables that whole
  category (returns `DATA_DISABLED`).
- Optional categories degrade to a sentinel string; core categories re-raise
  the first error so a broken primary is loud.
- Successful results are cached in `vendor_cache` (skip category `news_data`).

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

All tools read through `get_config()`.

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