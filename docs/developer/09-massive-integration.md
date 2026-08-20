# 9. Massive.com integration (developer reference)

This describes the Massive.com add-on added to this fork — its endpoints, the
entitlement boundary, the tools it exposes, and where each is bound. The
user-facing plan/doc is `docs/massive_integration.md`.

## 9.1 What Massive is

Massive (`api.massive.com`, the Polygon.io lineage) is a US-centric market
data provider. Access: REST (`/v2/*` etc.), WebSocket (streams), Flat Files
(S3 bulk CSVs), and MCP. This repo uses the **REST + Flat Files** datasets plus
a **NOI** WebSocket streamer.

**Key field in `.env`**: `MASSIVE_API_KEY` (config `massive_api_key`). It is
gitignored. Plan-dependent; free Basic is quote-only.

## 9.2 The entitlement boundary (probed live)

| Dataset | Endpoint | Current plan | State in this fork |
| --- | --- | --- | --- |
| News sentiment | `/v2/reference/news` | **entitled (200)** | `get_massive_news` tool -> news/social |
| Economy (treasury/inflation/labor) | `/fed/v1/*` | entitled | `get_macro_indicators_massive` + catalyst backdrop |
| Short interest/volume | `/stocks/v1/*` | entitled | `get_short_interest_massive` + `get_short_volume` |
| Form-4 insider | `/stocks/filings/vX/form-4` | entitled | `get_form4_insider` |
| Corporate actions (dividends/splits) | `/stocks/v1/*` | entitled | `get_corporate_actions_massive`, `get_dividends`, `get_splits` |
| Related companies (peers) | `/v1/related-companies/{t}` | entitled | `get_company_peers` `massive` option |
| IPOs | `/vX/reference/ipos` | entitled | `get_ipos` tool (news) |
| Fundamentals/ratios | `/stocks/financials/v1/ratios` | **403 on Basic** (needs paid) | `get_ratios_massive` (plan-aware) |
| Snapshots / top-movers | `/v2/snapshot/...` | 403 on Basic | `get_market_snapshot`, `get_top_movers` (plan-aware) |
| NOI (WebSocket) | `stocks/NOI` | needs Imbalances add-on | `massive_noi.py` stream monitor |
| Flat Files (S3) | day-aggregates | Starter+ (bulk) | `massive_flat.py` + `data/massive_flat/` + validator |

Only the **entitled** rows run as live tools today; the 403 endpoints degrade
to "upgrade at massive.com/pricing" and activate when the plan changes (no code
change).

## 9.3 The vendor module — `dataflows/massive.py`

- `massive_api_key()` — key from config/env.
- `_get(path, params)` — authenticated GET; raises typed errors
  (401/403 -> `MassiveNotConfiguredError`; 429/5xx -> `VendorRateLimitError`).
- Each `get_<x>_massive` returns a **string** (markdown) matching the vendor
  contract; raises `NoMarketDataError` on empty.

Tools exported:
`get_news_massive, get_macro_indicators_massive, get_short_interest_massive,
get_short_volume_massive, get_form4_insider_massive, get_ratios_massive,
get_fundamentals_massive, get_market_snapshot_massive, get_top_movers_massive,
get_dividends_massive, get_splits_massive, get_related_companies_massive,
get_ipos_massive, get_corporate_actions_massive, fetch_macro_backdrop`.

Registering in `interface.py`: added `massive` to `VENDOR_LIST` and several
`VENDOR_METHODS` maps; dedicated tools call the module directly.

## 9.4 Catalyst OpenD decoupling

`strategies/catalyst.py::fetch_catalyst_data` now fetches a Massive-derived
`macro_backdrop` (yield-curve inversion / elevated breakeven) independently of
the moomoo OpenD gateway, so the B1 catalyst overlay keeps a macro-stress read
even when OpenD is down. Applied only when no forward event calendar exists.

## 9.5 Flat Files screener seam (folder + toggle, OFF by default)

- Config: `enable_massive_flat` (bool, default False) + `massive_flat_dir`
  (default `data/massive_flat`). Env: `TRADINGAGENTS_ENABLE_MASSIVE_FLAT` /
  `TRADINGAGENTS_MASSIVE_FLAT_DIR`.
- `value_screener._fetch_ohlcv` reads the folder's day-aggregate CSV only when
  the toggle is on and it resolves >=15 rows; else falls back to the
  per-ticker chain.
- `scripts/validate_massive_flat.py` sanity-checks a dropped CSV.
- `data/massive_flat/README.txt` documents the schema.

## 9.6 Adding a new Massive endpoint

Follow §3.3 (vendor contract) + §5.2 (tool binding):

1. Add `get_<x>_massive` to `dataflows/massive.py` using `_get`.
2. Register in `interface.py` (category + VENDOR_METHODS[method][massive]);
   opt into `OPTIONAL_CATEGORIES` if optional.
3. Add chain in `default_config.data_vendors`.
4. Wrap as `@tool`, re-export, bind to the analyst tool node.
5. Tests (mock `_get`), hermetic.

## 9.7 Plan-awareness convention

Endpoints that 403 on the free plan should still work today via the *entitled*
chain. Represent FMV/Greeks/Business-only fields as "unavailable" per the
no-fabrication contract, never invented/estimated.

This completes the developer docs set. All plan rows in
`docs/massive_integration.md` are implemented (entitled live where possible,
degraded plan-aware otherwise).