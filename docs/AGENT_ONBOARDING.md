# AGENT ONBOARDING — TradingAgents fork (read first!)

This file tells a **fresh agent instance** everything it needs to operate in
this repo without burning time rediscovering the environment. Read it before
running anything.

---

## 0. WORKING AGREEMENT — read before EVERY task

These are permanent repo-wide rules the maintainer expects on **every** task;
a fresh agent must follow them without being reminded:

1. **Compute as tools, feed the agents** - the project has ~40 "computed"
   LangChain `@tool`s in `tradingagents/agents/utils/analysis_tools.py` (swing,
   relative strength, catalyst scale, risk gate, position sizing, VCP, regime,
   orderflow, analyst verdict, ...) plus the value-dip / market-session / tool
   modules — all wrapping the deterministic `strategies/*`
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
4. **Every TradingAgents change reflects in trading_web** - the web app
   (`../TradingNew/trading_web`) is a thin passthrough to the repo's scripts
   and tools. Whenever a change adds/renames a capability, tool, script flag,
   or screener column, the matching web surface must be updated in the same
   task: the backend capability adapter (`backend/capabilities.py`), the job
   allowlist (`backend/main.py`), the raw-command allowlist
   (`backend/config.py`), the SPA page/help text (`frontend/src/App.jsx`),
   and the README sync table. Never leave a repo change that the web cannot
   reach.
5. **Every test has a timer** - every test file must carry a pytest-timeout
   deadline (`pytestmark = pytest.mark.timeout(N)`) so a hung vendor call or
   infinite loop can never block the session. New test files must include it;
   existing files without it should gain one when touched. When running tests
   from the shell, wrap the command in a `timeout` too (e.g.
   `timeout 900 py -3.12 -m pytest tests/ -q`).
6. No personal info or secrets in commits (see §8 below); offline tests stay
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
│                          #   analysis_tools.py (computed-analysis: swing/RS/catalyst/sizing/risk),
│                          #   value_dip_tools.py (Value Dip hybrid: %b/tranche/expectancy/FCFy/Z/matrix)
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
│  ├─ swing.py relative_strength.py sector_rank.py  # techno-fundamental swing (--scan swing/vcp)
│  └─ value_dip.py              # Value Dip hybrid + tranche risk fold (--scan value-dip)
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
- **Every test has a timer** (`pytest-timeout`): 180s per-test default (thread
  method), 30-minute session cap, and a 600s module-level override for the
  live-vendor modules (`value_screener`/`scan_strategies`/`growth_screens`/
  `structured_agents`). Adds a real deadline so a hung vendor call can't block
  the session indefinitely - see `docs/developer/10-tests-layout.md`.

## Changelog of this fork (most recent first)
- 2026-08-29 `(working tree)` - Canonical output root: all reports / screener /
  action_report / nightly-review / pre-market-review / rebuild outputs now
  resolve against the TradingAgents repo root (new
  `tradingagents.dataflows.utils.repo_root()` / `resolve_output_path()`) instead
  of the process CWD, so scripts and the web app (launched from TradingNew or
  trading_web) never write `reports/` into the parent folders. Stale
  `TradingNew/reports` + `trading_web/reports` migrated into
  `TradingAgents/reports`. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - Provider-endpoint + calc-wiring pass: yfinance
  keyless fallbacks added for `analyst_ratings` (recommendation summary +
  price-target consensus), `earnings_calendar` (earnings dates + EPS surprise)
  and `institution_data` (institutional + major holders) — registered in
  VENDOR_METHODS + default chains (`moomoo,finnhub,yfinance` /
  `moomoo,yfinance`) so no key is needed for those signals; new market tools
  `get_scaleout_plan` (swing.scaleout_plan), `get_payoff_asymmetry`
  (statistical.omega) and `get_book_correlation` (statistical.correlation_matrix),
  plus `get_strategy_quality` extended with calmar/ulcer/tail_ratio/expectancy.
  See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - Full-set audit fixes (correctness + wiring):
  `exit_check` profit target anchored at entry (was never-firing "target"),
  horizon parametric CVaR sign/tail fix, `first_pullback` R:R dead-pattern fix,
  yfinance statement CSV parsed newest-first + `# comment` header no longer
  misroutes to the text parser, `tracking_error` demeaned, `ev_ebitda` no longer
  P/EBITDA, FCF/dividend sign-safe on negative capex/divs, Alpha-Vantage error
  string no longer cached, screener/movers invalid-arg sentinels, EODHD routed
  symbol list is a string; new `get_exit_plan` tool + `get_consensus` /
  `get_sentiment_computed` now bound to analyst ToolNodes; batch `--vendor`
  presets keep all 27 data categories. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - Tiingo data vendor (free Starter tier): `dataflows/tiingo.py` (EOD OHLCV, fundamental statements JSON, IEX quote, crypto OHLCV) registered in the vendor chains (eodhd/moomoo first, tiingo last) + `get_crypto_prices` market tool + `--vendor tiingo` preset. News/intraday not on free tier. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - NautilusTrader deep-study implementation (all 3 phases): backtest harness (`strategies/backtest_engine.py` + `backtest_models.py` + `scripts/backtest_strategy.py`), risk sizing + pre-trade checks (`strategies/risk_sizing.py`, `risk_checks.py`), `evaluate.py` stats (calmar/ulcer/capture/tail/expectancy), and `validate_config()` in `default_config.py`; web `run_backtest`. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - Per-analyst tool-round cap + empty-report guard (NVDA missing `1_analysts/market.md` defect): `graph/conditional_logic.py` forces the terminal report turn after `MAX_TOOL_ROUNDS` (8) tool rounds (market/news/fundamentals routers return the analyst node, not the tool node), `agents/utils/structured.py::finalize_messages` runs that turn with dangling tool_calls stripped, and `reporting.py` writes an explicit "report unavailable" block when an analyst report is empty instead of silently dropping the file. Tests: `tests/test_tool_round_cap.py` (12) + 3 reporting guard tests.
- 2026-08-29 `(working tree)` - OpenBB deep-study **implementation** (all 4
  phases + quick wins): `strategies/statistical.py` + `rotation.py` (normality,
  unit-root ADF/KPSS, omega, correlation, cointegration/Granger, CAPM, VIF,
  relative-rotation, Clenow, vol-cones) + 5 market tools; typed dataflow layer
  (`dataflows/schema.py` VendorResult + `registry.py` + `route_to_vendor_typed`);
  free-tier data surfaces (`cboe.py` options, `federal_reserve.py` SOFR/treasury,
  `screener.py` universe+movers); trading_web watchlist/grid/charts/presets/
  credentials/timeline. Tests: 41 + 14 + 32 + 54. ruff clean.
- 2026-08-29 `(working tree)` - OpenBB deep-study enhancement roadmap
  (`docs/design_openbb_enhancements.md`): research-to-design mapping OpenBB's
  typed provider envelopes (VendorResult/error_kind), self-describing
  REST/CLI/MCP surface, statistical/econometrics toolkit (normality/unit-root/
  CAPM/VIF/relative-rotation/Clenow/omega/vol-cones), free data surfaces
  (cboe options IV + greeks, federal_reserve risk-free curve, finviz/yfinance
  screener), and trading_web product gaps (watchlist/data grid/charts/
  credentials/presets/MCP). No code yet — phased plan with quick-wins verdict.
- 2026-08-28 `(working tree)` - QuantLib + Lean enhancements (deep-study
  implementation): new pure `strategies/*` modules `options_math` (Black-76
  IV / Greeks / vol surface), `rate_utils` (discount / compound / equiv-rate +
  downside measures), `portfolio_optimizer` (risk-parity / min-variance /
  confidence-weighted alloc from a real covariance matrix), `risk_manager`
  (two-pass exit override, advisory, off by default, not wired into runtime),
  `alpha_eval`, `config_robustness`; `evaluate.py` gained sortino /
  probabilistic_sharpe / rolling_beta / underwater_drawdowns and friends;
  `exits.py` trailing_stop_exit + max_giveback_exit, `book_risk.py`
  var_cvar_horizon, `journal.py` trade_excursions (MAE/MFE), `liquidity_risk.py`
  volume-share / market-impact slippage; 4 new market analyst tools
  (`get_downside_read`, `get_horizon_var`, `get_trailing_exit`,
  `get_risk_parity_alloc`) + `get_strategy_quality` sortino/psr; 10 new config
  keys with `TRADINGAGENTS_*` env overrides, all gates default OFF /
  advisory-only. See CHANGELOG [Unreleased] ### Added. Web: the 4 new tools
  added to the Value Tools market-tools whitelist (capabilities.py + App.jsx).
- 2026-08-28 `(working tree)` - Empty-final-decision hardening: a model that
  misses `with_structured_output` can answer the free-text retry with only a
  bare header (`**Decision`), which silently became an empty
  `5_portfolio/decision.md`. `invoke_structured_or_freetext` now detects a
  stub, re-invokes once, and if still degenerate returns an explicit
  "**Decision**: unavailable" notice. See CHANGELOG [Unreleased] ### Fixed.
- 2026-08-28 `(working tree)` - End-to-end advisory-context wiring fix: the
  Phase A-E decision context (`computed_decision_context` / `risk_context`)
  were seeded onto `AgentState` but not declared as LangGraph channels, so
  native LangGraph dropped them — the Trader / PM / 3 risk debators never saw
  the regime gate / plan card / pre-open rows and the report's IVa section
  never rendered. Declared both keys on `AgentState` (now flow to nodes +
  output); also dedented the pre-market reviewer's RVOL / gap / book-depth
  lines out of the `if news_titles:` block so they print unconditionally.
  Regression tests in `test_structured_agent_prompts.py` +
  `test_reporting.py`. (see CHANGELOG.md under [Unreleased] ### Fixed)
- 2026-08-27 `(working tree)` - EODHD real-time snapshot + top movers
  (Massive 403 fallback): `get_market_snapshot_eodhd` (`/api/real-time/
  {ticker}`, live OHLCV + prev close + change%) and `get_top_movers_eodhd`
  (`/api/real-time/{ticker}?ex=US`, ~18k US stocks sorted by change_p). The
  `get_market_snapshot` / `get_top_movers` tools fall back to EODHD when
  Massive returns 'unavailable' (403) or raises. Fixed `_eodhd_get` error
  detection (a `code` field without `message` is a normal payload). Tests:
  `test_eodhd_vendor.py` (7 new) + `test_massive_vendor.py` failover
  updated.

- 2026-08-27 `(working tree)` - Truncation-retry enforcement: when an LLM
  response is cut at the output cap (ends mid-sentence), the agent re-invokes
  with a continuation prompt and merges, so reports are never truncated.
  Wired into every agent path: `structured.py::_retry_if_truncated`
  (PM/RM/trader/sentiment free-text fallback), `retry_chain_if_truncated`
  (market/news/fundamentals analyst chains), `retry_llm_if_truncated`
  (bull/bear researchers + 3 risk debators). Up to 2 continuation attempts,
  only when a cut is detected; a failed continuation degrades to the
  original text. Tests: `tests/test_truncation_retry.py` (7).

- 2026-08-27 `(working tree)` - Tool-wiring audit: 4 new market tools +
  run-level OHLCV cache + computed sentiment on. New market tools:
  `get_technical_factors` (ADX/pivots/Aroon/Fisher/Chaikin/Elder-Ray/
  Supertrend/volume-profile in one call), `get_book_tail_risk` (portfolio
  CVaR + correlated stress + drawdown gate), `get_liquidation_days`
  (block-absorption days), `get_premarket_review` (CONFIRM/REVISE/REJECT
  arbiter). `_RUN_OHLCV_CACHE` in analysis_tools.py makes every tool share
  ONE vendor fetch per (ticker, days) per run (no duplicate data / quota
  burn; cleared in conftest). `enable_sentiment` now True (computed
  StockTwits score + surprise velocity injected into the sentiment report).
  Tests: 8 new hermetic tool tests + cache test + market-toolnode guard.

- 2026-08-27 `(working tree)` - Market tool-node binding fix + higher output
  cap: the market analyst's prompt listed `get_swing_exits` / `get_dip_technical`
  / `get_mean_reversion_tech` and the 5 market-session tools, but they were never
  registered in the market `ToolNode` (a wiring gap from the original
  value-dip+swing commits) — every run had the LLM call tools that error "not a
  valid tool". All 8 are now bound (41 market tools). `max_output_tokens` /
  `max_output_tokens_quick` raised 6000 → 8000 after 2026-08-27 WDC analyst
  reports truncated mid-sentence at the 6000 cap. Tests:
  `test_market_toolnode.py` regression guard.

- 2026-08-27 `(working tree)` - EODHD primary + eodhd-us default universe:
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance fallback); `news_data` = `eodhd,moomoo,yfinance` and
  `corporate_actions` = `eodhd,moomoo`. New EODHD endpoints on the EOD plan:
  `get_news_eodhd`, `get_corporate_actions_eodhd` (splits + dividends),
  `get_exchange_symbols_eodhd` (full US symbol list, ~18k common stocks). The
  value screener's default `--universe` is now `eodhd-us` (no moomoo quota);
  `top-losers`/`heat-proxy` (moomoo movers) stay optional. Fundamentals /
  technicals / intraday / options are NOT on the EOD plan, so those chains
  keep moomoo/yfinance first. Tests: `test_eodhd_vendor.py` (14) +
  `test_value_screener.py` eodhd-us (1).

- 2026-08-27 `(working tree)` - EODHD vendor (daily OHLCV):
  `dataflows/eodhd.py` serves daily bars in the same CSV shape as
  yfinance/moomoo, registered in the `core_stock_apis` chain
  (`moomoo,eodhd,yfinance` by default) and as a `--vendor eodhd` preset
  (`batch.py`/`pipeline.py`). Key `TRADINGAGENTS_EODHD_API_KEY` in `.env`.
  Free tier 20 calls/day; EOD plan $19.99/mo = 100k calls/day @ 1000/min,
  30+ years — replaces the moomoo K-line quota (100 calls/7 days) the value
  screener exhausts. Tests: `tests/test_eodhd_vendor.py` (8).

- 2026-08-27 `(working tree)` - Value-screener web-timeout fixes: (1)
  `moomoo_call_timeout` (default 5.0s, env `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`)
  wraps every moomoo SDK call in a wall-clock timeout (`_sdk_call`) instead of
  the SDK's own 20s `ReqInfo.wait()`; (2) the value-dip gating pass pre-filters
  on cheap OHLCV-only technicals (`_value_dip_technical_prefilter`: RSI <= 35,
  %b <= 0.10, stop <= 2%) before the heavy fundamentals fetch, dropping ~7
  vendor calls/symbol to 1 for non-candidates; (3) the web `run_screener`
  budget is 2400s and a timed-out capability kills its whole process tree
  (`taskkill /F /T`) so no orphaned process holds a moomoo connection.

- 2026-08-26 `(working tree)` - Correlation-aware allocation wired into the
  allocation plan (industry-practice item 1): `portfolio.allocation_block` and
  the `get_allocation` tool now accept `returns_by_name` and, when
  `enable_correlation_penalty` is on (default False, + `correlation_threshold`
  0.6 / `correlation_penalty_frac` 0.3), down-weight names whose average
  pairwise correlation with the rest of the book exceeds the threshold before
  the per-name/per-sector caps; the screener's `--alloc` builds return series
  from the run's OHLCV cache and passes them through. Names without a
  measurable series are never penalized (no fabrication).

- 2026-08-26 `(working tree)` - Industry-practice suggestions implemented (7
  items): correlation-aware allocation (`portfolio.correlation_penalty`),
  book-level correlated stress (`book_risk.book_correlated_stress`, surfaced
  in the risk snapshot), liquidity-aware costs (`exits`/`evaluate` illiq),
  paper-ledger track record (`pre_market.ledger_track_record`), limit-order
  directive in `pre_market_review.py`, claim-vs-computed audit
  (`reporting.audit_decision_numbers`, opt-in `enable_decision_audit`), and
  `scripts/strategy_quality_report.py`.

- 2026-08-26 `00a77d1` - Value-dip + swing + pre/post-market research
  implementation: 6 new technical factors (`aroon`, `fisher_transform`,
  `chaikin_oscillator`, `elder_ray`, `supertrend`, `volume_profile`) in
  `technical_factors.py`; new `market_session.py` (opening range/ORB, gap
  type, order imbalance, premarket liquidity, post-close confirmation); 5 new
  market-analyst tools (`get_opening_range`, `get_gap_type`,
  `get_order_imbalance`, `get_premarket_liquidity`, `get_post_close_confirmation`);
  screener columns `Aroon`/`Fisher`/`Supertrend`/`POC`. Tests:
  `test_strategies_market_session.py` (30) + extended
  `test_strategies_technical_factors.py` (17 new). Full suite 1413 passed.

- 2026-08-26 `7e01b06` - Conditional action report (`scripts/action_report.py`):
  flags basket names (TRADINGAGENTS_RISK_BASKET_WEIGHTS) on their newest
  Underweight/Sell verdict (reduce/trim) + non-basket names on their newest
  Overweight/Buy verdict (add); extracts each report's stated condition
  (re-entry level, trim zone, scale-in confirmation) from Position Size +
  Executive Summary and checks it against live OHLCV via the vendor chain —
  deterministic MET / NOT_MET / UNKNOWN, never fabricated. Stop/ATR levels are
  informational; unmeasurable qualifiers (PUC, VDU trigger, stabilization)
  render UNKNOWN. Optional `--llm` judge (`ActionConditionVerdict` schema +
  `agents/overrides/action_condition_judge.py`, deep-think, snapshot-only,
  advisory). Output: final action report (ADD/BUY / TRIM/REDUCE / MONITOR)
  printed + saved keep-only-newest; `--json` for machine-readable rows.
  Tests: `tests/test_action_report.py` (21).

- 2026-08-26 `26c18eb` - Report truncation marker (`reporting._finalize_section`
  appends a visible blockquote when a section ends mid-sentence at the LLM
  max_tokens cap) + full 11-SPDR sector ranking table in the screener report
  (`value_screener._sector_table_markdown`, appended with `--sector-rank` /
  `--enrich-sector`).

- 2026-08-24 `(working tree)` - Per-role max output tokens
  (`TRADINGAGENTS_MAX_OUTPUT_TOKENS[_QUICK|_DEEP]`, 6000/6000/2500) + per-role
  density/tool-call directives (`get_output_budget`) wired into all 12 agent
  prompts; grounded in measured report sizes + the
  `min(1,048,576, 1,310,720 - input)` formula.

- 2026-08-24 `(working tree)` - OpenRouter provider-ignore routing:
  `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` (.env, CSV) -> `provider.ignore`
  in the request body via `extra_body` to block slow OpenRouter endpoints.


- 2026-08-23 `(working tree)` - Free computed ratios: `strategies/ratios.py`
  replicates the plan-gated Massive `get_ratios` (EV/EBITDA, P/E, P/B, ROE…)
  from our own canonical statements, exposed as `get_ratios` on the
  fundamentals analyst; added `inventory` canonical alias for Quick ratio; fixed
  a latent double-`@tool` bug in analysis_tools.py.

- 2026-08-23 `(working tree)` - SEC EDGAR -> Massive insider fallback:
  `get_sec_filings` falls back to `get_form4_insider_massive` (Form-4 insider
  activity) when EDGAR fails (403/network/non-US no-CIK); result is labelled
  so the agent distinguishes it from the full 8-K/10-K set; both-down degrades
  to unavailable (no fabrication).

- 2026-08-22 `(working tree)` - Pre-market review (design `docs/pre_market_review.md`):
  deterministic arbiter `strategies/pre_market.py` (gap / catalyst-window /
  re-anchored tranche / cap breach -> CONFIRM/REVISE/REJECT), `PreMarketVerdict`
  schema + `agents/overrides/pre_market_reviewer.py` (deep-think prompt variant,
  no new graph node), standalone `scripts/pre_market_review.py` (pre-open,
  `--report-dir` / `--prior-date` / `--skip-llm` / `--dry-run`), and the opt-in
  same-night `batch.py` step (`enable_pre_market_review`).

- 2026-08-22 `(working tree)` - Blank-symbol hardening: a whitespace/empty
  ticker reaching a yfinance entry point (e.g. a malformed LLM tool call in
  ``batch.py --symbols ...``) previously leaked a raw TypeError + noisy
  yfinance HTTP-4xx ERROR logs; it now canonicalizes to ``""``
  (``normalize_symbol``) and raises the typed NoMarketDataError via
  ``require_symbol`` at every yfinance entry point, so the router returns the
  clean ``NO_DATA_AVAILABLE: blank/empty ticker symbol`` sentinel the agents
  can report honestly.

- 2026-08-22 `(working tree)` - Value Dip Step-1/Step-2 gap strategies:
  balance_sheet_health (D/E + current ratio), profitability_quality (FCF +
  ROE), the Step-2 technical ladder (macd_divergence / volume_dry_up /
  trigger_candle / higher_low_structure / vdu_entry_setup), support_structure
  (multi-month base / 200-SMA), decline_driver_check (negative-force screen);
  five new analyst @tools (market: get_macd_divergence / get_vdu_entry_setup /
  get_support_structure; fundamentals: get_balance_sheet_health /
  get_decline_driver_check); value_dip_setup + --scan value-dip gate on the
  new rows when measured.

- 2026-08-22 `(working tree)` - Tranche risk fold for the Value Dip + Swing
  hybrid: `tranche_risk_read` (config-frozen weights/stop/risk/account, never
  the LLM) feeds the risk governor the worst-case peak-deployed-at-scale-in
  fraction (per-trade cap) + capital-at-risk budget (sum of per-tranche losses
  at the hard stop); `build_position_contract` takes a weighted `entry_price`
  hook; `govern()` gains a `capital_at_risk_pct`/`risk_cap_pct` check; reports
  show `Tranche peak-deployed` / `Tranche capital-at-risk` in the Risk Gate
  block. Gated by `enable_tranche_risk` (+ `tranche_*` keys).

- 2026-08-22 `(working tree)` - Value Dip + Swing hybrid: `strategies/value_dip.py`
  (Bollinger %b, historical valuation Z, FCF yield, breakeven rate / expectancy,
  tranche scale-in plan, hybrid allocation matrix) + six analyst `@tool`s
  (market: get_bollinger_pct_b / get_tranche_plan / get_trade_expectancy;
  fundamentals: get_fcf_yield / get_valuation_z_score / get_value_dip_setup) +
  `--scan value-dip` screener mode; `enable_value_dip` config gate.

- 2026-08-21 `(working tree)` - Risk Gate renders both CVaRs: with a risk
  basket configured, `5_portfolio/decision.md`'s `Risk Gate (computed)` block
  shows `Analyzed-name CVaR` (the analyzed ticker's own daily tail) next to
  `Portfolio (book) CVaR — this fed the gate` (the weighted-basket CVaR the
  governor budgets against); the same numbers are computed-injected into the
  PM prompt (`**Computed daily-tail CVaR**`) via `final_state["risk_context"]`.

- 2026-08-21 `(working tree)` - Session-discipline + earnings-quality tools:
  `get_session_discipline` (market, momentum.session_flags walk-away + psych
  levels) and `get_earnings_quality` (fundamentals, Sloan accruals_ratio +
  trap verdict) bound + hermetic-tested (6 cases); docs backfilled the
  missing `TRADINGAGENTS_ENABLE_MASSIVE_FLAT`/`_MASSIVE_FLAT_DIR` env keys in
  api_reference §1.1 and synced `.env.example` for `TRADINGAGENTS_MASSIVE_API_KEY`
  and the REDDIT/MOMENTUM runtime toggles.

- 2026-08-21 `a70e3b6` - Credit-stress read (FRED ICE BofA OAS):
  `get_credit_spread_read(date)` (market node) + `strategies/credit_spread.py`
  `credit_stress_level`, flattening the HY/CCC/BB option-adjusted spreads
  (FRED aliases `hy_oas`/`ccc_oas`/`bb_oas`) into a credit-cycle band +
  de-risk scale. Thresholds: HY <3% low/3.5-4.5% mod/>5.5% severe; CCC <8%
  low/10-12% mod/>15% severe. Degrades to 'unavailable' without FRED_API_KEY.
- 2026-08-21 `c7405b3` - Second decision-tool batch for the analyst LLMs:
  `get_sector_rank` (11-SPDR 1m/3m momentum + sector standing, market),
  `get_strategy_quality` (net CAGR/vol/Sharpe/max-drawdown, market),
  `get_margin_of_safety` ((intrinsic-price)/intrinsic band, fundamentals),
  `get_composite_rank` (value+momentum composite percentile vs peers,
  fundamentals), `get_tail_risk` (VaR/CVaR tail budget + stress loss, market).
  Each wraps an existing deterministic `strategies/*` function, bound in
  `_create_tool_nodes` + the market/fundamentals analyst tools lists+prompts,
  hermetic-tested (12 cases), docs+README+CHANGELOG kept true.
- 2026-08-20 `a22092c` - Developer docs: added `docs/developer/` full developer set (topology, graph workflow, dataflow/vendors, strategies, agents/tools, entrypoints, persistence, dev guide, Massive integration) covering the whole project for a joining developer.
- 2026-08-20 `1557954` - Developer docs: added `docs/developer/10-tests-layout.md` (tests/ directory map, fixtures, hermetic conventions) + index/dev-guide cross-links.
- 2026-08-20 `35e7e3f` - `Strategies/index.md`: navigation map linking each strategy plan doc under Strategies/ to its implementation modules, config gates, scan modes, and consumers.
- 2026-08-20 `135361c` - `docs/developer/11-agent-decision-tools.md`: audit + plan (no code) listing decision-critical strategy/dataflow functions to expose as agent @tools.
- 2026-08-20 `d918206` - Agent decision tools implemented: `get_exit_check`, `get_allocation`, `get_regime_components`, `get_consensus`, `get_momentum_detail`, `get_beat_miss_sizing` - exposed as @tools, bound to market/fundamentals/news tool nodes (consensus also computed-injected into the PM prompt), hermetic-tested.
- 2026-08-20 `9c2aebe` - `docs/developer/12-data-providers.md`: the 13 data providers (8 routed vendors + 5 direct sources) and per-category chains, for a joining developer.
- 2026-08-20 `4ee08ee` - Massive no-data failover fix: the direct Massive tool wrappers (get_short_volume / get_market_snapshot / get_top_movers / get_massive_news) now return "unavailable" on NoMarketDataError instead of aborting the batch symbol; regression-tested (8 cases).
- 2026-08-20 `e981232` - DCF valuation: `strategies/dcf.py` (pragmatic FCF-DCF) + `get_dcf_valuation` tool bound to the fundamentals analyst, built from `Strategies/Discounted_Cash_Flow.md`; provider-sourced (cashflow, 10y, beta, shares); tests: test_strategies_dcf + test_analysis_tools.

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

Full suite: **1153 passed** (2 skipped: bedrock extra, live DeepSeek).

---

Run order sanity check:

```bash
py -3.12 -c "import tradingagents; print('ok')"
py -3.12 -m pytest tests/test_moomoo_vendor.py -q -p no:cacheprovider
```