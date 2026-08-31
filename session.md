# Session Handoff — TradingAgents + TradingNew/trading_web

Session date: 2026-08-30. Repos (both branch `main`, both pushed):
- Core: `D:/Users/vince/PycharmProjects/TradingNew/TradingAgents` — origin `git@github.com:Ghostfusion/TradingAgents.git`
- Web: `D:/Users/vince/PycharmProjects/TradingNew/trading_web` (sibling under `TradingNew`) — origin `github.com/Ghostfusion/TradingNew.git`
- Repo root for `session.md` = `TradingNew` (contains both `TradingAgents/` and `trading_web/`).

---

## 1. Task Objective & Scope

- **Goal:** Harden the TradingAgents fork + its web mirror by (a) parallelizing web `run_batch` with a worker cap, (b) fixing value-screener hangs + introducing two-stage gating (cheap OHLCV gate before any provider query), and (c) keeping every docs/help/web surface consistent with those changes.
- **Sub-task in progress:** NONE — all requested work is complete, tested, committed and pushed in BOTH repos this session.

### Commits this session (all pushed)
- Core `TradingAgents`: `8b39564` (Nerd Font CLI), `ff81092` (screener exit-hang fix), `3a151d2` (top-losers context-close test), `e02d493` (two-stage screener gating code+tests), `2d6e634` (docs: scan.md/entrypoints/onboarding/README).
- Web `trading_web`: `8ccdc71` (parallelize run_batch, worker cap), `d02967c` (web audit: /nightly + /history routes, screener --sentiment, capital_income --fi, pipeline/action-report/scripts param gaps, help text fixes), `619c9d0` (docs: two-stage gating in SPA help + manual + README).

---

## 2. File Manifest & Modifications

### Core `TradingAgents/`
- `scripts/value_screener.py` — (1) exit-hang fix: moomoo error paths (`_err()` helper) call `close_context()` before `parser.error` so a failed top-losers/heat-proxy run exits cleanly instead of blocking on the SDK's non-daemon receive thread; (2) **two-stage gating**: new `_cheap_gate(ohlcv, scan)` (pure OHLCV-only pre-filter — no provider call), `_fetch_fin_cached` (memoized `fetch_ticker` per ticker/date, `_FIN_CACHE`), `_CASHFLOW_CACHE` (fixed double cashflow fetch in `_value_dip_scan`), `_SECTOR_RANK_CACHE` restored. Main scan loop now: Stage A cheap gate (definitive non-candidates dropped, no fundamentals) → Stage B `_fetch_fin_cached` for survivors → Stage C provider enrichment (float/sector/revisions/inst/sentiment) on finalists. `value`/`all` have no cheap technical signal and fall straight through. Scan thresholds unchanged.
- `tests/test_value_screener.py` — restored clobbered bodies; added `test_moomoo_error_path_closes_context`, `test_moomoo_top_losers_error_path_closes_context`, `test_cheap_gate_deferred_before_fundamentals`, `test_eodhd_cheap_gate_before_fundamentals` (gated-out names never call `fetch_ticker`).
- `CHANGELOG.md` — exit-hang + two-stage gating entries under `### Fixed`.
- `cli/main.py` — Nerd Font TUI icons (`_USE_NERD_FONT`, `_glyph`/`_status_label`/`_team_label`, `TRADINGAGENTS_NERDFONT` env toggle), committed `8b39564`.
- Docs mirrored (commit `2d6e634`): `Strategies/scan.md` (new "Two-stage gating" section), `docs/developer/06-entrypoints.md`, `docs/AGENT_ONBOARDING.md` (changelog), `README.md` (News bullet + Nerd Font note committed earlier).

### `TradingNew/.env` (gitignored, local)
- Added `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT=5.0` (next to `TRADINGAGENTS_MAX_WORKERS=4` / `TRADINGAGENTS_MOOMOO_MAX_CONNECTIONS=20`). Belt-and-suspenders; code default is already 5.0.

### Web `trading_web/`
- `backend/capabilities.py` — `run_batch` rewritten: parallel via `ThreadPoolExecutor` (one symbol per worker), cap from `TRADINGAGENTS_MAX_WORKERS` (default 4, `_batch_max_workers()`), rejects `len(symbols) > cap` up front; added `_run_one_symbol`. `run_screener` gained `sentiment` param (`--sentiment`). `run_capital_income` gained `fi`/`fi_horizon` (`--fi`/`--fi-horizon`). Restored `intraday`/`enable_float`/`alloc` params.
- `backend/main.py` — added `POST /api/history` route (History screen was 404ing); kept `GET /api/history/ohlcv` (chart). `HistoryIn` model existed.
- `frontend/src/App.jsx` — registered `/nightly` route; Screener gained `sentiment` checkbox + accurate numeric-gate help (blank=script default, 0=off, value=filter) + two-stage gating help line; Scripts gained config-gate `--returns` + capital_income `--fi`/`--fi-horizon`; Pipeline gained movers-direction/limit/min-mcap/price-min/pe-max; Action report gained `--json` + `--llm-max`; ValueTools + RunBatch help corrected (36 tools, first 4 on by default; max 4 workers). Several edit-tool mangling/duplication defects were repaired during the session.
- `frontend/src/HelpGuide.jsx` — Screener card explains the fast price-only gate; tool-count text fixed.
- `tests/test_backend.py` — added `test_post_history_route`, `test_run_batch_rejects_more_symbols_than_worker_cap`, `test_run_batch_parallel_one_symbol_per_worker`, `test_run_screener` `--sentiment` forwarding assertion.
- `README.md` — sync-table rows (run_batch workers, screener --sentiment, action-report --json/--llm-max, two-stage gating).

### Untouched Dependencies (read/audited, not changed this session)
- `tradingagents/dataflows/moomoo.py` (`close_context`, `_sdk_call`, `moomoo_call_timeout`, movers fns) — consumed, not edited.
- `tradingagents/strategies/*`, `dataflows/{eodhd,statement_parsing,interface}.py`, `docs/*` and `Strategies/*` fully read for the audit.
- `trading_web/backend/{config,jobs,security,db}.py`.

---

## 3. Current State & Validation

### Working/Passing
- Core `tests/test_value_screener.py`: **25 passed** (incl. 4 new two-stage/context-close tests). Ruff clean on `scripts/value_screener.py` + test file.
- Web `tests/test_backend.py`: **60 passed** (incl. run_batch cap/parallel, history route, sentiment forwarding). Full-suite bash-wrapper "timeout at exit" is the known benign moomoo-daemon teardown — tests themselves finish in ~20s, NOT a failure.
- Live smoke (this session): `--universe eodhd-us --scan value-dip --limit 15` completes in **~12s** (was effectively hanging per-name before); `--scan value AAPL MSFT` ~10s clean exit with `on_disconnect: reason=CallClose`; `--universe heat-proxy --scan value-dip -n 30` exits cleanly code=2 (~2s) on "no symbols after price/P-E/equity gates".
- Frontend: `npm run build` clean; served dist bundle `index-VhNsdR9I.js` verified (server reads dist from disk per request). Browser-verified (throwaway admin, removed after): `/screener` help shows "Two-stage gating", `/guide` Screener card shows "price-only gate", `/nightly` route loads, `/scripts` config-gate Returns + capital-income fi fields, `/pipeline` 5 new fields, `/history` returns real decision rows.
- Web app running via hub name `web` on http://127.0.0.1:8000 (persistent; admin login from `.env`: user `admin`, pass `8802667`).

### Failing/Incomplete (deliberate/documented)
- GDELT network-unreachable on this machine (ConnectTimeout) — stays out of default `news_data` chain (only `news_sentiment` chain tail). Benzinga opt-in, no real key.
- Value-dip over eodhd/heat-proxy yields few/no candidates (inherently rare gate: value floor + bal-sheet + profitability + RSI≤35 + %b≤0.10 + stop≤2%). The first-15 alphabetical eodhd names all cheap-gated out. Not a bug; eodhd slices alphabetically, so harvest needs a large `--limit` or movers universe (now tractable post-fix).
- Pre-existing tiingo vendor warning `time data 'annual' does not match format '%Y-%m-%d'` in screener logs — noisy but degrades to moomoo fallback; NOT fixed this session (out of scope, no correctness impact).

### Active Errors / Stack Traces
- None blocking. Known benign: bash-wrapper "timed out at process exit" on moomoo daemon threads (tests pass); `[open_context_base.py] Disconnected: reason=CallClose` = clean context close (expected).

---

## 4. Technical Constraints & Decisions

- **`py -3.12` only** — bare `python` is the hermes agent venv (no pytest). Never deviate (see `docs/AGENT_ONBOARDING.md`).
- **Windows bash tool mangling** — never use heredocs for file content; use `write`/`edit`. The `edit` tool repeatedly dropped/duplicated lines/cache-declarations and doubled README rows this session — always re-read the edited region and verify imports with `py -3.12 -m py_compile` + `ruff`.
- **No-fabrication contract** — every tool returns exact numbers or explicit `unavailable`; value-dip/perpetual/var-degradations never invented.
- **Two-stage gating decision (user-directed):** keep the scan gates as tight as each scan's own definition, but move the cheap OHLCV-only check before ANY provider call; fetch fundamentals only for survivors (memoized once); run provider enrichment (float/sector/revisions/inst/sentiment) only on finalists. `value`/`all` bypass Stage A (no cheap technical signal) and go straight to fundamentals. User's two choices honored: (1) YES — also gate movers on the free price/PE/mcap rank columns; (2) YES — list ALL survivors ranked, do NOT silently cap at 50.
- **Web `run_batch`** — user required: max workers from `TRADINGAGENTS_MAX_WORKERS` (default 4, repo `.env` sets 4), ONE symbol per worker, and reject (> workers) with a clear UI error instead of throttling/serializing.
- **`TRADINGAGENTS_*` env overrides** win over `.env`; both override code defaults; `.env` gitignored. `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT=5.0` pinned locally.
- **CRLF** — use `write`/`edit`; `edit` bare `»` markers mangle indentation. Web README was rewritten with `\n` newlines (git will CRLF-normalize).
- **Docs true on every change** — scan.md, developer entrypoints, AGENT_ONBOARDING changelog, README News, CHANGELOG, web App.jsx help + HelpGuide + web README all mirrored the two-stage gating and audit changes before committing.

---

## 5. Next Actions (for fresh session) — mostly optional/exploratory
1. If you want real value-dip candidates, run a **large** `--limit` eodhd slice (now fast) or `--universe top-losers/heat-proxy --scan value-dip`, and expect few names (rare gate). The two-stage gating makes thousands-name scans tractable.
2. `get_variance_premium` live machine-chain integration remains the one deferred follow-up from the quant plan (needs a structured option-chain feed; tool degrades honestly today).
3. GDELT unreachable — re-probe before ever adding to `news_data`; optionally add `benzinga` to `news_data` once a real key is registered.
4. Optional: scale `sentiment_factor_eval.py` (larger universe, longer look-back) to see if rank IC firms (~0.016 live, not yet trusted) before enabling `enable_sentiment_factor`.
5. Run the full core suite periodically: `py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider` (~5 min, network-flaky yfinance-sector tests may fail hyper-offline).
