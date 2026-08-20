# AGENT ONBOARDING — TradingAgents fork (read first!)

This file tells a **fresh agent instance** everything it needs to operate in
this repo without burning time rediscovering the environment. Read it before
running anything.

---

## 0. WORKING AGREEMENT — read before EVERY task

These are permanent repo-wide rules the maintainer expects on **every** task;
a fresh agent must follow them without being reminded:

1. **Compute as tools, feed the agents** - the project has `~15` "computed"
   LangChain tools in `tradingagents/agents/utils/analysis_tools.py` (swing,
   relative strength, catalyst scale, risk gate, position sizing, VCP, regime,
   orderflow, analyst verdict, ...) that wrap the deterministic `strategies/*`
   calculators so the LLM analysts reason over computed numbers instead of
   re-deriving (or inventing) them from raw vendor output. When building or
   extending any calculation/analysis function, ALWAYS consider exposing it as
   a `@tool` bound to the relevant analyst (see the no-fabrication contract in
   `docs/api_reference.md` §6.4) - a pure function that never reaches the
   agent tool loops is incomplete work.
2. **Keep every doc true** - whenever code/behavior changes, update the
   relevant section(s) of the docs in `docs/` (api_reference.md,
   howto_end_to_end.md, AGENT_ONBOARDING.md gotchas/changelog) AND `README.md`
   (News entry + any feature bullet) AND `CHANGELOG.md`. Never leave a doc
   stale against the code.
3. **Always commit and push when done** - after changes pass the relevant
   tests (full suite ~6 min only if extensive), `git add -A`, commit with a
   descriptive Conventional-Commits-style message, and `git push origin main`.
   Never leave uncommitted/pushed work at the end of a task. If the commit
   hash is referenced in a doc (e.g. the onboarding changelog), commit it in a
   follow-up docs commit and push.
4. No personal info or secrets in commits (see §8 below); offline tests stay
   hermetic (mock vendor calls); `py -3.12` everywhere (below).

---

## 1. THE MOST COMMON MISTAKE — Python interpreter

There are **two Python environments** and they are NOT interchangeable:

| Command | Resolves to | pytest? | Use for |
| --- | --- | --- | --- |
| `python` (bare) | `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe` (agent venv) | **NO** (no pytest) | nothing in this repo |
| `py -3.12` | `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` | **YES** | EVERYTHING |

- If you see `No module named pytest` or `No module named pandas`, you ran the
  wrong interpreter. **Always** use `py -3.12` for runtime, tests, and scripts.
- Both `3.12` and `3.11` exist (`py -0p` lists them). Use 3.12.
- The moomoo SDK (`moomoo-api==10.10.7008`) and all project deps are installed
  **only in the py3.12 env**.

```bash
py -3.12 -c "import sys; print(sys.executable)"
py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider
py -3.12 scripts/value_screener.py --help
py -3.12 -m ruff check tradingagents/ ...
```

## Where the debugger/breakpoints live

- Unit tests run under pytest **not a debugger you must start**: `py -3.12 -m pytest tests/test_X.py -q -p no:cacheprovider`.
- For interactive debugging add a breakpoint: `breakpoint()` (pdb) in the code,
  or run `py -3.12 -m pytest tests/test_X.py::test_Y -s`.
- Jupyter/IPython is not used. Debug by minimal repro scripts: `py -3.12 -c "..."`
  or a temp file written with the `write` tool, run, deleted.

## Environment uniqueness (the gotchas that cost time)

1. **Shell heredocs mangle code** in the bash tool on Windows: `\n`, `\u2014`,
   arrows (`->`), and other escape/unicode sequences get corrupted inside
   `<< 'EOF'` heredocs. **Workaround**: any script or file content containing
   escapes, em-dashes, arrows, or non-ASCII must be written with the `write`
   tool (literal), then executed and deleted. Prefer the `edit` tool for
   surgical changes. Multi-line matches in existing files: they are CRLF —
   use `r"\r?\n"`-aware matching.
2. **Default `python` is the hermes agent venv** — never use it (see above).
3. **Port 11111 quirk:** OpenD (moomoo gateway) at `127.0.0.1:11111`. When it
   is DOWN the TCP probe **times out** (not refuses), so tests must mock the
   probe to stay fast; the vendor caches the negative probe 20s.
4. **A running OpenD leaks non-daemon threads** — never leave an
   `OpenQuoteContext` open at interpreter exit (the process hangs). Contexts
   are closed at the end of `propagate()`, in the test teardown
   (`tests/conftest.py` -> `_close_all_ctxs()`), and via a daemon-guarded
   atexit in `dataflows/moomoo.py`.
5. **OpenD (moomoo gateway)** runs on the dev machine, logged into a free
   moomoo account ("remember password"). Live moomoo calls work as long as
   the gateway is up. The account is a US-market account (not SG/MY): US
   equities LV3 free, HK LV1, crypto free; **US options permission-gated**
   (>$3000 assets); **event contracts gated** to SG/MY (falls back to
   Polymarket); A-shares/LSE/India unsupported (falls back to yfinance).
6. **Full test suite takes ~3-5 minutes** (cache-dependent). Don't rerun it
   unless you changed something. Quick loop: `py -3.12 -m pytest tests/test_<area>.py`.
7. **ruff is the linter/formatter**: `py -3.12 -m ruff check` and
   `py -3.12 -m ruff format` (selectors E/W/F/I/B/UP/C4/SIM, line length 100).
   The whole repo (`tradingagents/`, `scripts/`, `tests/`, `cli/`, root
   scripts) passes `ruff check` — don't regress it. `main.py` keeps
   `# noqa: E402` imports on purpose (dotenv must load before config imports).
   Reformat previously-unformatted files as needed, but keep formatting
   scoped to the files you touch.
8. **`.env` holds the user's real API keys** (OpenRouter, Finnhub, FRED,
   Alpaca, FMP...) and is **gitignored**. NEVER print, commit, or paste them.
   Set `TRADINGAGENTS_*` overrides there, not in code. `.env.example`
   mirrors every supported `TRADINGAGENTS_*` key — keep it in sync when
   adding new config keys.

## Project structure (current `main`)

Repo root: this checkout (clone of the remote below).
Git: `origin` = `https://github.com/Ghostfusion/TradingAgents.git`, branch `main`.

```
tradingagents/
├─ agents/                 # LLM agent nodes (prompts + tool binding)
│  ├─ analysts/            # market, sentiment(news+reddit/stocktwits), news, fundamentals
│  ├─ researchers/         # bull / bear
│  ├─ risk_mgmt/           # aggressive / conservative / neutral
│  ├─ managers/            # research_manager, portfolio_manager (structured output)
│  ├─ trader/              # structured TraderProposal
│  └─ utils/               # agent_states (LangGraph state schema), agent_utils (tool registry),
│                          #   *tools.py wrappers (core/tech/fundamental/news/macro/prediction/
│                          #   position/analyst/market_position/moomoo_extra), memory.py (decision log),
│                          #   analysis_tools.py (computed-analysis: swing/RS/catalyst/sizing/risk)
├─ dataflows/              # VENDOR LAYER
│  ├─ interface.py        # route_to_vendor(): TOOLS_CATEGORIES, VENDOR_METHODS, chains
│  ├─ config.py           # thread-local config (set_config/get_config/reset_config)
│  ├─ errors.py           # NoMarketDataError / VendorRateLimitError / VendorNotConfiguredError
│  ├─ vendor_cache.py     # disk TTL cache (6h, news excluded, sentinels never cached)
│  └─ vendors: y_finance.py, alpha_vantage*.py, finnhub.py, sec_edgar.py, fred.py,
│     polymarket.py, moomoo.py (main live vendor, ~1500 lines), fmp.py, alpaca.py,
│     symbol_utils.py (Yahoo <-> broker mapping), ...
├── graph/                 # LangGraph state machine
│  ├─ trading_graph.py    # TradingAgentsGraph: propagate(), tool nodes, strategy overlays
│  ├─ setup.py            # graph wiring; parallel-analyst subgraphs (concurrency>1)
│  ├─ conditional_logic.py, analyst_execution.py, propagation.py, reflection.py,
│  │  signal_processing.py, checkpointer.py (SQLite resume)
├── strategies/            # deterministic overlays (compute, don't narrate)
│  ├─ regime.py size.py factors.py events.py catalyst.py orderflow.py
│  ├─ contract.py (G1) calibration.py consensus.py sentiment.py exits.py
│  ├─ risk_governor.py (R0-R4) book_risk.py debate_context.py portfolio.py
│  └─ swing.py relative_strength.py sector_rank.py  # techno-fundamental swing (--scan swing/vcp)
├── llm_clients/           # factory + provider registry (OpenAI/anthropic/google/azure/bedrock/
│                          #   openrouter/deepseek/qwen/glm/minimax/ollama/openai_compatible)
├── default_config.py      # DEFAULT_CONFIG + TRADINGAGENTS_* env overrides
└── reporting.py           # report-tree writer (heading hierarchy + auto TOC)
scripts/                   # value_screener.py, rebuild_complete_report.py, risk_report.py, ...
batch.py                   # headless concurrent runner (--vendor), memory logs
pipeline.py               # B2: screen -> composite rank -> top-N -> batch (moomoo-first)
main.py                    # minimal Python API demo
docs/                      # api_reference.md, howto_end_to_end.md, THIS FILE
tests/                     # conftest (autouse fixtures), test_* per area
```

## The pipeline (what this project does)

1. `propagate(ticker, date, asset_type)` initializes state (instrument identity,
   memory-log context).
2. LangGraph streams: analyst teams (tool-calling LLM loop) -> Bull/Bear debate
   -> Research Manager -> Trader -> risk debate -> **Portfolio Manager**
   -> structured decision (rating, confidence, position_size, stop_loss, consensus).
3. `_apply_strategy_overlays` (deterministic): regime/position_scale ->
   orderflow fold -> **catalyst fold (B1, on by default)** -> G1 position
   contract -> risk governor (PASS/WARN/REJECT + risk_halt) -> computed context.
4. Memory log appends a pending decision; next same-ticker run resolves the
   realized return + alpha (vs regional benchmark) and reflects.

## Vendor data contract (add a new source like this)

- Add vendor functions to `dataflows/VENDOR.py`; typed errors from `errors.py`.
- Register in `dataflows/interface.py`: `TOOLS_CATEGORIES` entry,
  `VENDOR_METHODS[<method>][<vendor>]`, and `OPTIONAL_CATEGORIES` if optional.
- Add chain in `default_config.data_vendors` (e.g., `"moomoo,yfinance"`;
  `"none"` disables, `"default"` = all).
- Wrap as a LangChain `@tool` in `agents/utils/*_tools.py`; re-export in
  `agents/agents_utils.py`; add to the analyst's tool node + prompt in
  `graph/trading_graph.py` + `agents/analysts/*.py`.
- Results are strings; the vendor cache wraps automatically (news excluded).

## The partners / key decisions already made (avoid re-litigating)

- **Moomoo** is quote-only; credentials live in OpenD (user logs in once,
  "remember password"); `TRADINGAGENTS_MOOMOO_AUTOSTART=true` launches OpenD
  headlessly. Never put the moomoo password in code/.env.
- **moomoo earnings calendar**: window cap is 7 days INCLUSIVE (begin..begin+6);
  the market-level call returns ALL securities - MUST filter by the ticker's
  code and normalize columns (`earnings_date`, `eps_predict`, `N/A` -> None).
- **moomoo statement period order + prior periods**: statement payloads list
  periods NEWEST-FIRST (2025, 2024, ...) and a `get_fundamentals` payload
  concatenates income + balance + cashflow (12 tables for 4 years). The
  screener's canonical parser (_parse_markdown_periods/_markdown_canonical in
  scripts/value_screener.py) sorts tables by period year and emits
  `{"current": .., "prior": ..}` dicts for keys present in two periods, so the
  Beneish M-Score (needs prior) and the Piotroski time-components actually
  compute instead of returning n/a. Gotchas to preserve:
  - moomoo `-`-prefixed labels are sub-item/contra breakdowns (`-Accumulated
    Depreciation`, `-Cash and Cash Equivalents`) and are SKIPPED - the
    aggregate line always wins.
  - the old `d&a` depreciation alias normalized to `"d a"` and substring-
    matched "Selling and Admin Expenses" ("and admin") - depreciation aliases
    must NOT include a bare `d&a`.
  - `net_receivables` prefers the aggregate `receivables` row (the `-Accounts
    Receivable` sub-line must be skipped).
  - DO NOT "fix" the period-year regex (`r"(20\d{2})"`) with a doubled
    backslash - a raw-string `\\d` matches a literal backslash and breaks the
    newest-first sort (current/prior dicts silently become flat values).
  - canonical `{current, prior}` dicts: the quantitative_scores._num() reads
    `current`, _prv() reads `prior`; the screener's other reads use
    `_latest()` to unwrap. Keep _latest() at every flat read site.
- **Catalyst (B1)** is on by default (`enable_events=True`); tuning keys
  `catalyst_*`; it only de-risks (scale <= 1), guarded fetch returns None
  when OpenD is down.
- **Parallel analysts** (`analyst_concurrency`>1) run each analyst as its own
  sub-graph in a thread with isolated messages; default 1.
- **Analyst concurrency / strategy overlays** are deterministic and tested
  offline; LLMs only argue from the reports.

## Finnhub (free tier — behavior learned by live probing)

`TRADINGAGENTS_FINNHUB_API_KEY` is set in `.env` (40-char key, free tier).
Everything below was live-verified against the key, so don't re-discover it:

**What the free tier actually allows (200):**
- `company_basic_financials` (metrics: epsGrowthQuarterlyYoy,
  revenueGrowthTTMYoy, roeTTM, margins, payout, current ratio, 52w high/low,
  average volumes)
- `company_profile2` (sector/industry/country/marketCap/float/ipo)
- `quote`, `company_news`, `general_news`, `earnings_calendar` (symbol-scoped),
  `company_peers`, `stock_insider_transactions`, `stock_insider_sentiment`,
  `stock_symbols` (full US list)

**❌ NOT on the free tier (403 — never wire these):** `news/sentiment`,
`index/constituents` (S&P 500 list), `economic-calendar`, `press-releases`,
`upgrade-downgrade`, `sector-performance` (needs an extra request header),
`earnings-surprises`. The `--revision` flag therefore stays on the yfinance
upgrade/downgrade **proxy** — don't "fix" it to finnhub, it will 403.

**Rate limits:** free tier throttles hard with **429** (shared with FMP). A 429
must degrade to "source unavailable" and fall through to the next vendor
(yfinance/moomoo), never break a run. Treat the Finnhub key as a fourth data
source in the growth/insider paths, NOT a replacement.

**Scale gotcha:** Finnhub reports `marketCapitalization` in **millions**
(e.g. `4430136` ≈ $4.43T for AAPL). `get_basic_financials_finnhub` multiplies
by 1e6 to raw USD so the screener's `--min-mcap` floor compares correctly —
don't "fix" that or the cap gate breaks by 1000x.

**Wiring (all key-gated / guarded / no-fabrication):**
- `get_basic_financials` (metrics) — feeds `fetch_ticker`'s growth/ROE gaps
  so `--min-eps-yoy / --min-rev-yoy / --min-roe` work off Finnhub when the
  statement chain lacks them; also a `get_fundamentals` vendor option
- `get_insider_activity` (12m net insider change + mspr + trend) and
  `get_company_peers` — bound to the Fundamentals analyst as tools
- `get_profile_finnhub` → sector fallback for `--sector-rank`:
  FMP → Finnhub → yfinance (sector is under `finnhubIndustry`, mapped to
  `sector`)
- The three analyst tools call the Finnhub module DIRECTLY (not
  `route_to_vendor`) because `get_insider_activity` / `get_company_peers`
  have no category chain; offline tests must mock
  `tradingagents.dataflows.finnhub.get_basic_financials_finnhub` etc.

**Re-probed endpoint availability** before adding anything new (the free tier
has changed before); never assume an endpoint works — the SDK's
`Client` exposes far more than the free key grants.

## Testing conventions

- conftest autouse fixtures reset the thread-local config, clear the vendor
  cache, and close moomoo contexts before/after each test.
- `tests/test_moomoo_vendor.py` has `_reset()` (autostart off + close ctx +
  reset flags) - keep new moomoo tests hermetic even when OpenD is UP.
- Strategy tests are pure/offline (no network).
- Slow tests exist: value_screener (network), structured_agents (LLM mocks) -
  ~30-70s each. Only full-suite when needed.

## Changelog of this fork (most recent first)

- 2026-08-20 `a22092c` - Developer docs: added `docs/developer/` full developer set (topology, graph workflow, dataflow/vendors, strategies, agents/tools, entrypoints, persistence, dev guide, Massive integration) covering the whole project for a joining developer.
- 2026-08-20 `1557954` - Developer docs: added `docs/developer/10-tests-layout.md` (tests/ directory map, fixtures, hermetic conventions) + index/dev-guide cross-links.
- 2026-08-20 `35e7e3f` - `Strategies/index.md`: navigation map linking each strategy plan doc under Strategies/ to its implementation modules, config gates, scan modes, and consumers.
- 2026-08-20 `135361c` - `docs/developer/11-agent-decision-tools.md`: audit + plan (no code) listing decision-critical strategy/dataflow functions to expose as agent @tools.

- 2026-08-20 `b08c25b` - Massive.com vendor (first integration): `dataflows/massive.py` + `get_news_massive` with per-article structured news sentiment; registered in `VENDOR_LIST`/`get_news` chain; dedicated `get_massive_news` tool bound to news/social nodes + news analyst prompt; `MASSIVE_API_KEY` config/env; `tests/test_massive_vendor.py`; `docs/massive_integration.md`. US-only additive vendor (see docs).
- 2026-08-20 `308492c` - Massive economy + catalyst OpenD decoupling: `get_macro_indicators_massive` (macro_data chain: treasury-yields/inflation/inflation-expectations/labor-market, FRED-compatible aliases); `fetch_macro_backdrop` (yield-curve-inversion / elevated-breakeven deterministic macro-stress read) keeps the B1 catalyst overlay de-risking when the OpenD event calendar is unavailable; `fetch_catalyst_data` now degrades per-section instead of returning None on moomoo failure.
- 2026-08-20 `37301c7` - Massive short-interest/short-volume: `get_short_interest_massive` registered in the `short_interest` category (FINRA 2-week settlement, days-to-cover/shares-short); dedicated `get_short_volume` tool bound to the market analyst (daily short-sale volume ratio).
- 2026-08-20 `96e0575` - Massive Form-4 insider transactions: `get_form4_insider(ticker, start, end)` bound to the fundamentals analyst — net open-market insider buys-minus-sells (P/S), excluding grant/exercise (A/M); 13-F deferred (no security filter on the endpoint).
- 2026-08-20 `370a6ad` - Massive fundamentals/ratios + snapshots (plan-aware): `get_ratios` (precomputed EV/EBITDA/P/E/ROE), `get_market_snapshot`, `get_top_movers` bound to market/fundamentals analysts + `pipeline.py --universe top-movers-massive`; `massive` registered in `fundamental_data`. These 403 on free Basic so they degrade with an explicit upgrade message until the plan includes them.
- 2026-08-20 `39e30a1` - Massive NOI + Flat Files (item 8): `massive_noi.py` (WebSocket NOI monitor + `scripts/massive_noi_monitor.py`) and `massive_flat.py` (bulk Flat-File OHLCV loader for screener/backtests). Plan-gated standalone utilities (Imbalances add-on / Starter+), not batch @tools.
- 2026-08-20 `a606378` - Massive corporate actions/peers/IPOs (row 5): `get_company_peers` gains a `massive` option; `get_corporate_actions`/`get_dividends` (dividends+splits) and `get_ipos` bind Massive to fundamentals/news analysts. All entitled on current tier.
- 2026-08-20 `c34358e` - Massive Flat-File import behind off-by-default toggle + folder: `enable_massive_flat` (default False) + `massive_flat_dir` (default data/massive_flat) replace `massive_flat_path`; screener reads the folder only when the toggle is ON. genuine day-aggregates CSV goes in data/massive_flat/ (Starter+).
- 2026-08-20 `6ee432f` - `scripts/validate_massive_flat.py`: small validator that parses a dropped day-aggregates CSV and reports per-ticker close counts / date ranges / usability (>=15 rows) via the screener's exact folder lookup, so you confirm a genuine file before enabling the import.
- 2026-08-20 `ac1a80e` - Massive Flat-File screener seam + live run: value-screener `_fetch_ohlcv` reads a Massive flat-file folder first (`TRADINGAGENTS_MASSIVE_FLAT_DIR`, default `data/massive_flat`) when the toggle is ON for bulk ATR/scan bases; validated a live end-to-end `batch.py` run to AAPL (Underweight) exercising the new tools.

- 2026-08-20 `1a87063` - README: fork-additions highlighted with a purple left
  border (HTML tables), matching the diff-vs-upstream intent; replaces the
  grey blockquote (7a3bfac). Refined in `e68778a` to per-section borders
- 2026-08-20 `bc24e79` - working-agreement policy §0: always expose calculations as
  tools for the agents, keep docs + README true on every change, commit + push
- 2026-08-20 `8947ea2` - moomoo period-order + prior-period fix (M column now
  computes; latest values were the OLDEST period)
- 2026-08-19 `2ab7a8c` - Finnhub free-tier integration (basic financials -> growth
  gates, insider activity, peers, sector fallback, 3 analyst tools)
- 2026-08-19 `4df08d9` - computed-analysis tools follow-up (regime/VCP/orderflow/verdict/surprise/portfolio)
- 2026-08-19 `3b4084d` - computed-analysis tools for analyst LLMs (lean batch: swing/RS/earnings-event/catalyst/position/risk-gate)
- 2026-08-19 `92ae6b8` - Phase-1 screens (growth YoY, ROE, max-cap, sector
  top-3, revisions proxy, inst-accum; moomoo markdown parse fix)
- 2026-08-19 `29e291b` - VCP scan (`--scan vcp`, volatility contraction)
- 2026-08-19 `9a71cea` - swing scan + RS + PEAD entry + catalyst hard veto
- 2026-08-19 `a69fba7` - repo hygiene: lint cleanup, defect fixes, docs
- 2026-08-19 `d0a60ce` - docs: api_reference + howto full coverage
- 2026-08-19 `7185307` - this onboarding file
- 2026-08-19 `404c2c5` - README fork changelog entry
- 2026-08-19 `796cd64` - B2 pipeline, A-series tools (institutions/surprises/
  expected-move), catalyst on-by-default, docs (api_reference, howto)
- 2026-08-19 `378ed8c` - catalyst default + moomoo calendar fixes
- 2026-08-19 `3ca585e` - B1 scheduled-catalyst overlay
- 2026-08-19 `bd950aa`/`a78ddd5`/`f364e3a` - report hierarchy + TOC + docs
- 2026-08-19 `0ed81a3` - review fixes: indicator warmup, parallelism, caching
- 2026-08-19 `1e2246b` - moomoo vendor integration + event contracts + --vendor

Full suite: **969+ tested** (2 skipped: bedrock extra, live DeepSeek).

---

Run order sanity check:

```bash
py -3.12 -c "import tradingagents; print('ok')"
py -3.12 -m pytest tests/test_moomoo_vendor.py -q -p no:cacheprovider
```