# Massive.com integration

[Massive](https://massive.com/docs) (formerly Polygon.io lineage) is a
U.S.-centric market-data provider. This fork integrates it as an **additive
data vendor** so the analyst LLMs reason over computed, structured signals it
does not get from moomoo/yfinance — starting with **news + native sentiment**,
then economy, short interest, filings, and snapshots as they are wired up.

This doc records the plan, what is implemented, what each endpoint contributes,
and how to extend it. It follows the repo's vendor contract
(`docs/api_reference.md` §6) so a new source slots in cleanly.

---

## 1. Access methods (what Massive offers)

| Method | Purpose | Relevance to this fork |
| --- | --- | --- |
| **REST** (`/v2/...`) | on-demand historical/reference/snapshot | primary; wrapped as LangChain `@tool`s |
| **WebSocket** | real-time streams (NOI, LULD, FMV, agg) | out of scope for now (we're batch/analysis) |
| **Flat Files** (S3) | bulk CSV for backtesting/ML | useful for `scripts/evaluate_config_gate.py` later |
| **MCP** (`mcp.massive.com`, plus self-hosted `mcp_massive`) | LLM agent bridge | not consumed at runtime (we use plain LangChain tools), but see §8 |

Massive offers **stocks, options, futures, indices, forex, crypto** in
separate plans. This repo uses the **stocks** and **economy** datasets (US).

### Plan realities (matters for feasibility)

- **Stocks Basic: quote data only**. Snapshots/fundamentals require Starter+.
- **Starter/Developer = 15-min delayed quotes; Advanced/Business = real-time.**
- **FMV and Greeks are Business-plan only** → represent as *unavailable* per
  the no-fabrication contract, never invented.
- **News**: included in all Stocks plans, updated hourly, history since 2016.

Massive is **US-only**. It supplements — never replaces — the HK/JP/IN/SS/SZ
coverage that moomoo/yfinance already provide.

---

## 2. Implemented (first vendor module)

**Module**: `tradingagents/dataflows/massive.py`

**Key**: `MASSIVE_API_KEY` in `.env` (gitignored). Read via
`massive_api_key()` → config `massive_api_key` first, env second. No secret in
code/commits. Mirrored (blank) in `.env.example`.

### News with structured sentiment — `get_news_massive(ticker, start, end)`

The `GET /v2/reference/news` endpoint returns, per article, an `insights[]`
array assigning each mentioned ticker a `sentiment` (positive/negative/neutral)
plus a `sentiment_reasoning` string. This is the highest-leverage gap it fills:
the Sentiment/News analysts currently read raw headlines and guess polarity.

`get_news_massive`:
- requests a publishing window and caps the fetch (`limit`),
- **filters multi-ticker articles** down to those tagged for the requested
  symbol,
- renders each article with its per-ticker `Sentiment:` / `Sentiment reasoning:`
  so the LLM reads a computed signal, not prose.

Raises the typed errors the router understands: missing key →
`MassiveNotConfiguredError`, none tagged → `NoMarketDataError`, throttled →
`VendorRateLimitError`.

### Wiring

- `interface.py`: `massive` registered in `VENDOR_LIST` and as a `get_news`
  vendor (`VENDOR_METHODS["get_news"]["massive"]`).
- `default_config.py`: `massive_api_key` key + `TRADINGAGENTS_MASSIVE_API_KEY`
  env override.
- `news_data_tools.py`: dedicated `get_massive_news` LangChain tool.
- `agent_utils.py`: re-exported in the public tool surface.
- Bound to the tool loops of `get_news`'s fallback chain AND the dedicated tool
  is exposed to the **news** and **social** ToolNodes in
  `graph/trading_graph.py`, plus the `news_analyst` tool list + prompt.

The default `news_data` chain is unchanged (`moomoo,yfinance`). To route plain
`get_news` through Massive first, set `data_vendors.news_data = "massive,..."`.

### Verify live

```bash
py -3.12 -c "
from tradingagents.dataflows.massive import get_news_massive
print(get_news_massive('AAPL', '2026-08-13', '2026-08-20', limit=5))
"
```

---

## 3. Data mapped to the graph (planned / pipeline)

Prioritized by leverage vs effort. Implemented rows are marked ✅.

| # | Massive dataset / endpoint | Feeds | Status |
| --- | --- | --- | --- |
| 1 | `/v2/reference/news` (sentiment) | Sentiment + News analysts | ✅ implemented |
| 2 | `economy/treasury-yields`, `inflation`, `inflation-expectations`, `labor-market` | Macro analyst + catalyst overlay (B1) decoupled from OpenD | planned |
| 3 | `fundamentals/short-interest`, `short-volume` | Fundamentals + existing `short_interest` category | planned |
| 4 | `filings/13-f-filings`, `form-4` | institutional/insider fundamentals + screener | planned |
| 5 | `corporate-actions/dividends|splits|ipos|ticker-events`, `tickers/related-tickers`, `market-operations/*` | catalyst de-risk + peers + instrument context | planned |
| 6 | `fundamentals/ratios|balance-sheets|income-statements|cash-flow|float` | `get_analyst_verdict` inputs (EY, EV/EBIT, ROE) | planned |
| 7 | `snapshots/single-ticker|full-market|top-movers`, `aggregates/custom-bars`, `technical-indicators/*` | market analyst + `pipeline.py --universe` | planned |
| 8 | WebSocket NOI / Flat Files | real-time orderflow / backtest datasets | future |

---

## 4. Extension pattern (add the next vendor function)

Follow the existing contract (`docs/api_reference.md` §6):

1. Add `get_<x>_massive(ticker, ...)` to `dataflows/massive.py` using the
   `_get()` client (typed errors already handled).
2. Register in `interface.py`: `TOOLS_CATEGORIES` entry (or reuse an existing
   category like `short_interest`), `VENDOR_METHODS[<method>][massive]`,
   opt into `OPTIONAL_CATEGORIES` if optional.
3. Add the chain in `default_config.data_vendors` (e.g.
   `"moomoo,massive,yfinance"`; `"none"` disables).
4. Wrap as a LangChain `@tool` in `agents/utils/*_tools.py`; re-export in
   `agents/agents_utils.py` / `agent_utils.py`; add to the analyst's tool node
   + prompt in `graph/trading_graph.py` + `agents/analysts/*.py`.
5. Represent FMV/Business-only fields as *unavailable*, never invented /
   estimated (no-fabrication contract).
6. Add hermetic offline tests (`tests/test_massive_vendor.py`) with mocked
   `_get()`/HTTP; keep the key out of them.
7. Keep the docs (this file, api_reference, README/CHANGELOG) true.

---

## 5. MCP approach (reference, not runtime)

Massive's MCP server exposes only **3 composable tools** (`search_endpoints`,
`call_api`, `query_data` with built-in Greeks/returns/technical functions),
indexed dynamically from `llms.txt` — low token usage versus one tool per
endpoint. Two flavors:
- **Remote** (`https://mcp.massive.com/`, OAuth, nothing to install).
- **Self-hosted** (`github.com/massive-com/mcp_massive`, `uv`-installable,
  STDIO/SSE/streamable-http, local SQLite workspace + `apply` pipelines).

**Why we don't consume it at runtime**: this repo's analyst nodes bind plain
LangChain `@tool`s and call vendor modules directly / via `route_to_vendor`;
they are not MCP clients and adding an MCP transport layer would add moving
parts for no runtime benefit. The MCP server is still useful **during
development** — wrap `call_api`/`query_data` as a throwaway LangChain tool to
prototype an endpoint's response shape before writing the native
`dataflows/massive.py` client. Do not make it a dependency.

---

## 6. Footnotes for implementers

- **Multi-ticker articles**: `/v2/reference/news` returns one article once,
  tagged with many tickers. Always filter to the requested symbol and render
  only that symbol's `insights[].sentiment` — do not let a peer's sentiment
  leak into the report.
- **Entitlement vs auth**: HTTP 401 (bad key) and 403 (plan lacks dataset) both
  surface as `MassiveNotConfiguredError`. The router treats it as vendor
  unavailable and falls through — never breaks a run.
- **Recency**: below Advanced/Business, quotes are 15-min delayed. `news`
  itself is hourly, so the implemented news tool is unaffected.
- Keep `.env`/`.env.example` in sync when adding keys.
