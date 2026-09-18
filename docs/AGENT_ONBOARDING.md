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
1b. **Every code change: check calc -> tool -> prompt wiring** - ALL code
   changes (not just new calculators) must check whether the calculation can
   be wired into a `@tool` AND its prompt guidance added to the corresponding
   agent(s). The wiring chain is: `strategies/*` calculator -> `@tool` in
   `agents/utils/*_tools.py` -> tool list + import + `__all__` in
   `agent_utils.py` -> the analyst/agent that owns the claim -> a
   "cite it before any X claim" line in that agent's `system_message` ->
   the graph ToolNode list for that agent. Every hop must be checked and
   landed when the change produces a usable computed read; the gates in
   `tests/test_calc_agent_wiring.py` (test_public_calc_reachable_or_whitelisted,
   test_tool_bound_to_agent_surface, test_bound_tool_has_prompt_guidance)
   enforce the chain automatically - run them before finishing and add the
   prompt line whenever a new bound tool appears.
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
7. **All decision making should always do a deep web search first** - for any
   task that changes behaviour, picks between approaches, or grounds a
   recommendation (feature choice, model/provider selection, architecture,
   libraries, market/financial data claims), run a `web_search` BEFORE
   deciding and cite what it found. Decisions must be evidence-first, not
   remembered-from-training; if the search contradicts or doesn't cover the
   assumption, say so explicitly. (Applied this repo-wide: model choice for
   the debate roles, provider selection enforcement, key-normalization strategy, etc.
   were all verified against current web guidance before landing.)
8. **Report verifier → verify → fix the defects (permanent loop)** - after a
   report-verifier run finishes (batch `--verify`, `scripts/report_verify.py`,
   or the web Verify checkbox), the assistant MUST follow up on the flagged
   results before moving on: (a) inspect each `verify_flags.json` /
   per-stem flags, (b) adjudicate every non-GROUNDED claim - UNSUPPORTED,
   CONTRADICTED, MISQUOTED and INTERNAL_CONFLICT (`scripts/verify_sweep.py`
   classes CONTRADICTED/MISQUOTED/INTERNAL_CONFLICT as CONFIRMED and
   UNSUPPORTED as SUSPECT, and a MISQUOTED or INTERNAL_CONFLICT row is a real
   capture-or-citation defect, not noise) against the actual
   `tool_evidence.json` leaves — separating real defects
   (analyst-side citation errors, tool-side bugs, evidence-coverage gaps) from
   verifier noise — and (c) FIX every confirmed defect (code, prompt, evidence
   persistence) with a regression test, then commit + push. The verifier is a
   differentiator-detector, not a gate; its output is only useful when acted
   on. Document confirmed-but-unfixed defects in the design doc's reopen
   checklist (docs/design_report_verification_llm.md) rather than silently
   dropping them.
9. **Land every change, and never leave a doc stale (owner standing order, 2026-09-16)** -
   a task is not finished until its changes are **committed and pushed**
   (`git push origin main`, explicit `git add` paths) and every doc it touched or invalidated is
   corrected **in the same pass**: `README.md`, `CHANGELOG.md` (with the web-impact line whenever the
   web contract moves), `docs/AGENT_ONBOARDING.md`, `docs/api_reference.md`, `.env.example`
   (mirrors every code-read key), the plan/design doc that owns the behaviour, and the verifier
   design doc's reopen checklist. NEVER park a finished change uncommitted while asking whether to
   commit it, and NEVER leave a doc describing behaviour the code no longer has - when a check, a
   flag, an env key or a report format changes, find the doc that states the old behaviour and fix
   it in the same commit. The rule spans all three repos: this one, `TradingExecution`, and
   `trading_web` (which lives in the `TradingNew` repo root, so its commits go there).
10. **A confirmed defect is fixed on sight, without asking (owner standing order, 2026-09-16)** -
   when the verifier, a test, a log or a review surfaces a defect, the default is to **fix it in
   the same task**: no "want me to fix this?", no parking it for approval, no documenting it and
   moving on while the fix is reachable. Concretely: fix the SOURCE (not the test, not a symptom
   suppression), add the regression test that fails before the fix, run the affected suite, then
   land it per rule 9. A found defect is a work item, not a question.
   - **Ask first only** when the fix would be *destructive to user data* (deleting report trees,
     vendor/daemon state, force-pushing, rotating keys) or when it would silently rewrite a
     decision contract the owner set (a mandate, a threshold, a rating/veto semantic). Those are
     the only two categories; everything else is fix-and-report.
   - **Report-text defects count.** A wrong figure, a transposed count, a leaked self-correction
     marker or tool-call markup in a generated report is a defect: correct the artifact and fix the
     producer (prompt/tool/sanitizer) that let it through, so the next run cannot repeat it.
   - **Never** re-adjudicate a defect the owner already ruled on, and never re-open a
     documented-but-deferred item as though it were new.

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
4. **OpenD threads and interpreter exit.** The SDK's `CallbackExecutor` threads
   are non-daemon by default, and `open_context_base._close_callback_executor`
   installs a *fresh* executor while closing one, so a closed context can leave
   an orphan thread idling in `queue.get()`. `dataflows/moomoo.py` now sets
   `SysConfig.set_all_thread_daemon(True)` before the first context is built and
   stops the orphan on every close (`_close_orphan_executor`), so the process
   always exits. Contexts are still closed eagerly: at the end of `propagate()`,
   in the test teardown (`tests/conftest.py` -> `_close_all_ctxs()`), and via a
   daemon-guarded atexit.
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
│  ├─ toolsets.py          # SINGLE SOURCE of each analyst's bound toolset (bind == execute)
│  ├─ arbiters/            # debate_judge (L1 scorecard: per-claim grounding rows)
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
│  ├─ errors.py           # NoMarketDataError / VendorRateLimitError / VendorNotConfiguredError / VendorAbsence (chain-end reason)
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
│  ├─ risk_governor.py (R0-R4) book_risk.py portfolio.py
│  ├─ swing.py relative_strength.py sector_rank.py  # techno-fundamental swing (--scan swing/vcp)
│  └─ value_dip.py              # Value Dip hybrid + tranche risk fold (--scan value-dip)
├── llm_clients/           # factory + provider registry (OpenAI/anthropic/google/azure/bedrock/
│                          #   openrouter/deepseek/qwen/glm/minimax/ollama/openai_compatible)
├── default_config.py      # DEFAULT_CONFIG + TRADINGAGENTS_* env overrides
└── reporting.py           # report-tree writer (heading hierarchy + auto TOC)
scripts/                   # value_screener.py, rebuild_complete_report.py, risk_report.py, report_verify.py (LLM report verification vs tool_evidence), ...
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
  - `_match_row` (the alias scan) must NEVER bind a row that NEGATES the item:
    yfinance's balance sheet calls its current rows `Current Assets` /
    `Current Liabilities` (no "Total" prefix) and lists `Total Non Current
    Assets` / `Total Non Current Liabilities Net Minority Interest` FIRST, so
    the `current assets` fallback alias landed on the non-current line (MSFT
    2026-09-16: current ratio 3.74 vs 1.23, working capital 403.5bn vs
    38.9bn, and Altman Z / Ohlson / Zmijewski all read it); moomoo's income
    statement has no plain operating row but does carry `Other Non-Operating
    Income (Expenses)`, which matched the `operating income` alias (EBIT
    4.72bn vs 155.24bn -> EV/EBIT 779 vs 23.7, earnings yield 0.13% vs 4.22%,
    EPV 49.5bn vs 1,724.9bn). The scan now runs twice - negated labels are
    skipped first and only allowed if nothing plain matches (moomoo's
    `Non-Operating Interest Expense` IS MSFT's interest expense row). Keep the
    second pass: an item that is only ever reported negated must still bind.
  - `_ROW_LABEL_EXCLUDES` carries the wrong-adjacent-row cases that negation
    cannot express: `Gains Losses Not Affecting Retained Earnings` is not
    retained earnings (yfinance lists it first - Altman X2 read -3.28bn
    instead of +328.26bn on MSFT), `Accumulated Depreciation` is not the
    period's D&A (a negative expense poisons EV/EBITDA), and a deferred /
    unearned revenue liability is not revenue.
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

- 2026-09-17 `(working tree)` - **The poisoned-tree regeneration landed six fresh trees, all verified clean** (no code
  change). Regenerated with shallow depth + `--verify` and the production env (`TRADINGAGENTS_ANALYST_FORCED_TOOLS`
  popped): **AMKR, AMZN, ASML, HPE, IBM, JCI** (`*_20260917_*`); the run was then stopped on the owner's instruction and
  the other nine tickers keep their `POISONED_LEAF.md` markers for regeneration on demand. **All six verify clean by the
  same scan that found the poison** (health leaf `current_assets` matches a `Current Assets` row, no non-current one) -
  the fixed reader confirmed end to end on a fresh vendor payload. Poison vs fresh is visible side by side: AMZN's
  poisoned leaves read `588,959,000,000` (the 2025-12-31 non-current row) where the fresh tree reads `229,080,000,000`.
  Every fresh tree carries `run_card.evidence` (`mode=forced`, `rendered_blocks=3`), the mechanism added after the
  legacy-mode trees hid their gather-off downgrade, and all six carry `verify_flags.json`. Suites untouched: engine
  **4404 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **The six items outside the score set are decided.** One code change, one corpus
  regeneration, the rest documentation. **(1) The three legacy-mode trees** -> kept as the documented gather-off
  downgrade example, **explicitly labelled**: `LEGACY_GATHER_OFF.md` in each tree root records the leaked
  `TRADINGAGENTS_ANALYST_FORCED_TOOLS` value, the absent `_rendered_block`/`_model_pool`, the empty digest lines, and the
  missing `evidence` block in `run_card.json` (predates the writer at `reporting.py:1445`). **(2) The 25 poisoned trees**
  -> correct/regenerate: the list is **re-verified independently** by scanning each tree's own `get_balance_sheet` leaf
  for a `Current Assets` / `Total Non-Current Assets` row equal to the health leaf's `current_assets` **over every
  column** (the health tool merges the latest as-reported period per line item), reproducing exactly 25 of 37 with AMAT,
  LRCX, MSFT `231406`, NVDA `223229` and WDC `120300` clean; each carries `POISONED_LEAF.md` and a fresh tree is
  regenerated per ticker (run in flight). **(3) The DISCLOSED-vendor-pair tradeoff** -> keep both survivors flagged
  until a reproducer runs; **do not weaken the detector merely to eliminate the flags**. **(4) The weighting-decision
  UNSUPPORTED family** -> **the explicit exemption, implemented** in `report_verifier.py`: a stated analyst weighting is
  a **methodological judgment, not a claim about the external world** (`_is_weighting_statement` requires the analyst's
  own signal as the object plus a comparative token - "risk" excluded so "risk-weighted assets are higher" and
  "cap-weighted toward tech" are untouched; the `_anchor_claims` branch fires **only when the claim carries no decimal**,
  i.e. the statement and never the figures it cites; plus a `_VERIFY_INSTRUCTIONS` bullet). Two new tests, both failing
  against the pre-change module. **(5) The sentiment-score anchor** -> leave open until a live case occurs, then choose
  from what the pipeline produces; no pre-commitment on a hypothetical. **(6) Intraday event-risk sizing vs latency** ->
  **recorded with a document home** (`EventScore.md` §8): latency, data quality, idempotence/re-entry and fail-closed are
  the hard halves, the daily contract must not move, and any such path is a **separately authorised sizing input**, never
  a silent second `TradeScore` input. `IMPLEMENTATION_PLAN.md` §13.4 is now a **decision record**. Engine suite
  **4404 passed / 5 skipped** (2 new), executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** the owner **confirms both diagram completions** and the two
  **ledger statements** are now recorded verbatim in `IMPLEMENTATION_PLAN.md` §13.1 and `README.md` §1.4, and as binding
  rules: **`RiskScore` is a `TradeScore` engine, not a risk gate** (it contributes the `R` component of
  `0.40F + 0.25T + 0.15R + 0.20K`; the gates operate downstream and can hard-block regardless of the composite score -
  master **rule 18** / plan rule 12) and **the six-engine research allocation and the four-engine `TradeScore` are
  separate objects** (F/T/R/K feed `TradeScore`; News and Sentiment are attribution-only - master **rule 17** / plan rule
  11, *no engine enters the decision composite by adjacency*). The owner's implication is recorded: News and Sentiment
  can be highly informative without being decision-score inputs - attribution, diagnostics, explanations, and
  *potentially separately authorised sizing mechanisms* - but must never silently become a fifth/sixth `TradeScore`
  factor. **Two stale flags retired (rule 9):** §1.4's "two conflicts, flagged not resolved" is now a resolution (gate
  order = Q8, which composite = Q2 + this confirmation), §1.5's "withdrawn as a production score" is corrected (the
  withdrawal was of the four-score version as *the whole* score, not of `TradeScore` as the decision object), and §2.1's
  heading no longer says "seven". Suites untouched: engine **4402 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** the owner confirms the **architecture diagram's missing
  `FundamentalScore` was an oversight, not a design decision**, so `IMPLEMENTATION_PLAN.md` §13.1's flow diagram now
  carries it with its **own data root** (statements/filings, not market data) feeding `TradeScore` directly, and the
  "flagged, not resolved" caveat is gone. **Two completions named with it:** `RiskScore` is drawn as an **engine**, not
  only as "Risk Gates" (it is one of the four `TradeScore` inputs and a composite never overrides a hard gate - **my
  addition, flagged for confirmation**), and the two arrows out of the engine row are **separate objects** per decision
  Q2 - the **six** engines feed the research allocation (attribution only) while the **four** (F/T/R/K) feed
  `TradeScore`, so News and Sentiment reach the decision only through the research layer. Suites untouched: engine
  **4402 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** **all 28 engine-document questions are answered** - the 18
  still-open ones resolved by the owner plus the 10 closed earlier, so every §7 question in the six engine docs carries
  its decision inline and each §7 is retitled "Decisions (owner, 2026-09-17) - all resolved". Highlights: RegimeScore
  **drops its event category** when EventScore ships (same producer, would double-count), **variance ratio is the
  canonical persistence producer** with Hurst demoted to a diagnostic, a regime **change** is a separate state/flag;
  RiskScore's "correlation risk 15%" is the **cluster/notional share** renamed explicitly (never a correlation
  coefficient), the **executor owns the book-level computations** while RiskScore consumes them, `net_beta` is **planned
  WP-5 work**, and expected move is **options canonical / history fallback+validation** with **EventScore owning the
  field**; TechnicalScore is a **score composed from state leaves**, the **sector ETF is the primary** RS benchmark, and
  volatility does **not** mechanically invert; NewsScore is **per-name** with per-article evidence retained internally
  and the **aggregate as the primary output**; SentimentScore uses **delta institutional holdings**, the **regression
  slope** for velocity, and **percentile crowd bands** with the 40/60 constants as fallback; EventScore carries an
  explicit **`EventScope = NAME | MARKET`** and its four missing calendars are **implementation coverage** returning
  `available | missing | not_applicable`, never `score = 0`. **Two new invariants + one contract:** *no derived quantity
  may have two independent authoritative producers* (master rule 15 / plan rule 8 - covers expected move, materiality,
  volatility, sentiment velocity, institutional sentiment, relative strength), *daily is the canonical horizon* with
  explicit per-metric intraday promotion (master rule 16 / plan rule 9, with the full metric-class table), and *missing
  data is `unavailable`, never zero - a missing calendar is unknown, not "no event exists"* (master rule 1 extended).
  The **`verify_flags.json` contract** is recorded in `design_report_verification_llm.md`: missing is a
  contract/implementation gap, **not evidence of `false`**, with `status = VERIFIED | PARTIAL | UNAVAILABLE |
  NOT_APPLICABLE`. The owner's **second architecture diagram** is in the plan's §13.1 and **flagged, not resolved** - it
  omits `FundamentalScore` (and RiskScore as a node), so read it as the decision flow to execution, not the engine set.
  **Six items remain open** in the plan's new §13.4 and are explicitly not covered by this answer set: the three
  legacy-mode trees, the 25 poisoned trees, the DISCLOSED-vendor-pair tradeoff, the weighting-decision UNSUPPORTED
  family, the sentiment-score anchor when the computed block is absent, and the intraday event-risk latency question
  (still no document home). Suites untouched: engine **4402 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** **the twelve architecture decisions are recorded and
  propagated.** `IMPLEMENTATION_PLAN.md` §13 is now a **decision record** (each row keeps the recommendation that was on
  record beside the decision that governs): Q1 canonical regime path = **C** (market-level, B's four-axis vocabulary);
  Q2 `TradeScore` and the six-engine object are **separate names** (decision composite vs research allocation);
  Q3 `RiskScore` = **both** name- and book-level, only book-level feeding the composite; Q4 the mis-homed leaves
  **move** (weights preserved, never silently redistributed); Q5 the **sentiment toolset exists** and needs binding
  repair; Q6 **`EventScore` owns materiality/expected move**, `NewsScore` consumes it; Q7 the **structured event
  state** ships and macro/Fed/OPEX may **not** hard-block; Q8 **gates before sizing**; Q9 the **neglected-firm sign**
  for coverage; Q10 the score **informs only**; Q11 **daily** horizon; Q12 **semivariance, not the conditional-σ
  ratio**. **Seven anti-double-counting invariants** are now binding in the master's new §2.1 (rules 8-14), including
  "directional volatility -> the semivariance ratio, NOT σ_up/σ_down - the rule that stops the volatility factor
  quietly becoming a second momentum factor through drift contamination". The plan also gains **§13.1** (the
  architecture the decisions produce) and **§13.3** (what is *still* open, by document and question number), so the
  record cannot read as "everything is decided". **Ten engine-document questions are closed in place** - each resolved
  question in `RegimeScore.md`/`RiskScore.md`/`TechnicalScore.md`/`NewsScore.md`/`SentimentScore.md`/`EventScore.md`
  now carries a `**CLOSED 2026-09-17 (plan §13 Qn)**` line and each §7 opens with a status note; the unmarked ones
  stay open. **Kept explicit:** Q6 assigns *ownership* of materiality to `EventScore`, not the choice between the two
  producers (`options_surface.implied_move_pct:42` vs `catalyst.implied_move_from_history:111`), so `EventScore.md`
  §7 Q3 remains open as a producer question. All of the plan's inline `§13 Qn` references were updated with it (P0-7,
  WP-4's prerequisite 5, WP-5's book-mode, WP-6's materiality, WP-8's layer 3 and block note, WP-11's names and gate
  order, §11.2) - none is left dangling. Suites untouched: engine **4402 passed / 5 skipped**, executor **1105**,
  web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** **signed semivariance is specified** in the score-engine
  set - the one addition from the volatility-factor review that survived scrutiny. **Owner: `docs/scores/TechnicalScore.md`**
  (§1's volatility ledger gains three rows, §4 gains the producer spec, the methodology appendix gains three entries);
  **consumer: `docs/scores/RiskScore.md`** §1 (a named dependency, not a re-derivation) and §0.3 (a fourth pinned
  convention - the semivariance unit); **build row** in `IMPLEMENTATION_PLAN.md` §5.2 with the acceptance in §5.4; and
  the master's rule 3 now names the coupling so the shared producer has one owner. The spec: `volatility_models.semivariance(returns,
  *, min_obs=20) -> {"rs_up","rs_down","rs_total","rs_ratio","n"}` with `RS⁻ = Σ r²·1[r<0]`, `RS⁺ = Σ r²·1[r>0]` and
  **`RS⁻ + RS⁺ = RV` exactly** (Patton & Sheppard 2015); `None` below `min_obs`, never 0; the score consumes `√RS⁻`
  (return units, comparable to `regime.realized_vol:29`) plus the ratio, raw sums printed beside. **Rejected in the same
  pass:** the review's `σ_up = StdDev(r | r>0)` (a conditional std does not decompose - `evaluate.downside_deviation:430`
  is that object, not semivariance) and its `σ_up/σ_down` ratio (confounded with drift - it moves with the mean return,
  so it partly re-measures momentum). Direction pinned from the evidence: the **downside** leg is the persistent one, so
  it carries the risk weight, and volatility stays **risk-increasing** in every row. The methodology appendix now also
  carries the counter-evidence the review omitted: the **IVOL puzzle** (Ang/Hodrick/Xing/Zhang 2006), the
  **low-volatility anomaly** (Baker/Bradley/Wurgler 2011) and the **MAX/lottery effect** (Bali/Cakici/Whitelaw 2011) -
  which the repo already screens the other way (`get_lottery_factors:8739` → `strategies/lottery.py:88`, `toolsets.py:282`).
  Suites untouched: engine **4402 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **Design only, no code:** the score-engine set gets a **comprehensive
  implementation plan** - `docs/scores/IMPLEMENTATION_PLAN.md` (new, 73.6 KB, 16 numbered sections §0-§15), built from the
  eight design documents read end to end and grounded with web checks on every external source it depends
  on. Structure: **WP-0** the prerequisites (SEC XBRL structured series - `sec_edgar.get_financial_history:173`
  loops `_TAG_MAP:56-65` calling `companyconcept` once per tag and returns a *string*, so the CAGR path cannot
  consume it, while `companyfacts` returns every tag in one call against a published 10 req/s ceiling; the
  EODHD US panel - bulk fundamentals is stocks-only, needs the Extended Fundamentals plan, 100 calls per
  exchange request, 500-symbol cap, 100k/day paid; market-wide breadth from the S&P map the sector screens
  already fetch, no new vendor; VIX percentile from FRED `VIXCLS`; VIX term structure from the Cboe CDN CSVs
  - VIX9D is **not** on FRED; FINRA's bi-monthly short-interest settlement series; three toolset bindings on
  the wrong surface; the five recorded defects still open, `position_mult_by_side` first because it is a real
  sizing bug), **WP-1** the shared kernel (`align`/`combine`/`band_label`, three functions and no framework,
  because seven engines need the same three operations and ground rule 2 makes seven copies a defect),
  **WP-2..WP-8** the seven engines (each with its prerequisite order, component map, acceptance and the
  decision that gates it), **WP-9** the advisory surface, **WP-10** the measurement layer (the existing
  `alpha_health.score_evaluation_rows:440` harness plus the redundancy matrix as a **gate** on the weight
  tables), **WP-11** the composite. Then **six phases (0, A-E)** each default-off behind its own gate and
  flipped one at a time under the dark-launch protocol, with entry and exit criteria; the parallelism and
  **file-collision map** (`toolsets.py`, `default_config.py`, `analysis_tools.py`, `reporting.py`,
  `graph/trading_graph.py` - one owner at a time); a consolidated verification checklist; a ten-item risk
  register; the **eleven decisions the owner still has to make**, each with the recommendation already on
  record; and the external-source appendix with endpoints and limits. **The plan invents no weight (rule 6)
  and resolves no conflict the owner left open** (gate order, canonical regime path, whether macro/Fed/OPEX
  may hard-block). Gate names were checked before being proposed: `enable_factor_model` already means the
  *learned* model (`scripts/factor_model_train.py:7`), `enable_factors`/`enable_regime` are **inert**
  (`.env.example:470-471`, `tests/test_gate_env_toggles.py:87`), `enable_score_eval_rows` already gates the
  IC harness (`scripts/strategy_quality_report.py:340`). **Five documentation/hygiene defects recorded in the
  master's new §3.3:** (D-1) the master's §4/§5 were **stubs** - `68931f3` left the wiring contract as two
  sentences and the phase plan as a paragraph that stopped mid-sentence; (D-2) the master and
  `FundamentalScore.md` cited §3.7.x/§3.8.x/§4.2/§5.x/§6 Phases A-E/§8/§8.3, none of which exist any more -
  **all repointed**, with the dead names kept only inside the D-2 record; (D-3) `sec_edgar.py:30`'s
  `User-Agent` contact is the non-deliverable `research@example.com`; (D-4) 11 per-tag requests where one
  `companyfacts` call would do; (D-5) `enable_factor_model` is not a free name. The master's §4/§5 are
  repointed (cheap path vs expensive path; the plan's §9 plus the gate collisions) and the header names the
  plan as the build order. Suites untouched: engine **4402 passed / 5 skipped**, executor **1105**, web
  **149**.
- 2026-09-17 `(working tree)` - **The TWELVE remaining inventory defects are FIXED** (`docs/scores/README.md` §3.2), each
  with a regression test; **10 of the 11 new tests fail before the fix and pass after** (the 11th pins a producer key the
  graph was misreading). (7) `volume_profile`'s value-area loop carried a DEAD incremental add and its band could span the
  whole range for a bimodal distribution (AMAT `va_low == poc == 169.56`, `va_high == 424.64`) - the loop is now the band
  recomputation alone plus a new `value_area_pct` (printed as `va_pct=`). (8) `support_structure`'s primary branch was
  unreachable because the leaf never passed `atr_value` - it now measures ATR(14), so `multi-month-base-support` can be
  emitted. (9) **`size.atr` returned `0.0` on a missing/mismatched series** (NA-as-zero) - now `None`, matching
  `stop_loss_atr`/`etf_risk._atr`, with the four call sites that would have raised on None fixed too. (10) A missing
  drawdown percentile in `rank_sectors_multifactor` was substituted with 0.0 = the WORST rank - the risk leg now
  renormalises over the available legs (best sector on the available leg scores 100, was 60). (11) **`knife_factor` was
  model-supplied** - `get_position_risk_multiplier` now MEASURES all three factors (`knife_guard.knife_score`,
  `regime_state.regime_state` -> F_regime, `regime_state.vol_cap_factor`), labels an override `caller-supplied`, and reads
  1.0 + says so when unmeasurable. (12) **`trend_score` was model-supplied** - `get_skill_read` now prints provenance for
  both it and `baseline_score` (`[trend_score 72 (caller-supplied opinion, not measured)]`). (13) Unbounded Chaikin was
  labelled `(positive=buying pressure)` - now `(A/D units; sign = net accumulation vs distribution, magnitude not
  comparable across names)`. (14) The dead `implied_move_pct` key (the graph read a key the snapshot never emits) - now
  reads `implied_move`, with the producer contract pinned by a test. (15) **The premarket hard block was DEAD** - the leaf
  never passed `catalyst_snapshot` to `review_decision`; a new shared `_catalyst_snapshot(ticker)` feeds it and the line
  prints `catalyst=<verdict> scale=<scale> hard_block=<bool>`. (16) **The regime gate's catalyst veto was inert** -
  `catalyst_window` is now `bool | None = None` (omitted = measured from the snapshot), and the graph's compiled-context
  line derives it from the overlay's stamped snapshot and prints `catalyst_window=`. (17) `rule_signal_macd_hist_rising`
  (the only MACD-histogram-slope producer, script-reader only) and (18) `factors.momentum_multihorizon` (built,
  whitelisted unreachable) are both surfaced by `get_momentum_detail` (`momentum_mh: ... ensemble=`, `macd_hist_rising=`),
  and the wiring gate's whitelist entry is removed so the audit proves it. Suites: engine **4402 passed / 5 skipped**
  (baseline 4392 + 11 new - 1 exempted case that is now wired), executor **1105**, web **149**. Live MSFT:
  `execution multiplier MSFT: factor=0.75 (regime 0.75 (measured), vol_cap 1.0 (measured), knife 1.0 (measured))`,
  `momentum_mh: 21d=+3.2%, 63d=+31.2%, 126d=+27.2%, 252d=-1.7% ensemble=+15.0%`, `macd_hist_rising=True`,
  `volume_profile: ... va_pct=0.7463`, `premarket review MSFT: verdict=CONFIRM ... catalyst=no-imminent-catalyst
  scale=1.0 hard_block=False`.
- 2026-09-17 `(working tree)` - **The six code defects the score-engine inventories found are FIXED** (`docs/scores/README.md`
  §3.1), each with a regression test. (1) **The regime label was trend-blind**: `overlays.build_strategy_overlays` passed a
  literal `chop=0.4` against `regime_label`'s `0.30` default, so the choppiness branch could never fire and with the common
  `vol_pct == 0.5` the label was `neutral` whatever the trend was - proven before the fix (a monotone uptrend AND a monotone
  downtrend both returned `regime=neutral`); the overlay now passes a MEASURED choppiness and the label moves with the trend.
  (2) **Choppiness had two scales**: the producer returned 0-100 (canonical CHOP) but fell back to a 0-1 dispersion on closes
  alone (~8e-07 on a clean trend) while one caller compared `0.4` against `0.30` and the other the real value against `30.0`
  - now ONE scale (0-100 both branches; the close-only branch is `100 x (1 - Kaufman efficiency ratio)`), one exported
  `CHOP_TREND_THRESHOLD = 30.0`, and `None` (not a fabricated neutral) when unmeasurable. (3) **Donchian breakout flags were
  unreachable** (`None` by construction, no caller derived them) - `donchian_channel` now takes `closes` and compares the
  latest close against the PRIOR N-bar channel (the only definition that can be true), with the reference levels returned;
  every caller passes closes. (4) **`parabolic_sar`'s `below`/`exit` were unreachable** - the leaf now passes `closes` and
  prints the flags. (5) **`BookState.net_beta` was a declared field with no producer** defaulting to `0.0` (NA-as-zero) - now
  `float | None = None`, unknown until something computes it. (6) **Gap fill statistics were a constant table printed as a
  measurement** (0.3/0.6/0.4/0.8 and 5/3/4/2) - now MEASURED over the same-class gaps in the history the caller already
  passes (10-bar fill window, median days, current bar excluded), with the lookup kept only below
  `GAP_FILL_MIN_SAMPLE = 8` and a new `fill_basis` printed on every read; a measured 0% is now reachable. Prompt dose: the
  market analyst's `get_gap_type` line asks for the basis. Suites: engine **4392 passed / 5 skipped** (baseline 4385 + 7),
  executor **1105** (baseline 1104 + 1, `test_sleeves.py` +1), web **149**. Live smoke on MSFT: `chop=57.11 label=neutral`
  (0-100 scale), `donchian ... breakout_up=False breakout_dn=False (vs prior-20-bar 517.78/478.4593)`, `psar ... below=False
  exit=False`, `gap type MSFT: common gap_pct=1.53% fill_probability=92% days_to_fill=0 [measured (280 historical common
  gaps)]`.
- 2026-09-17 `(working tree)` - **Design only, no code:** the score-engine design is RESTRUCTURED into a master document plus one
  document per engine, in **`docs/scores/`**. `docs/design_fundamental_factor_weight_model.md` is **moved** (git mv) to
  `docs/scores/FundamentalScore.md` and **scoped to the fundamental engine only**; six new documents join it -
  `TechnicalScore.md`, `RegimeScore.md`, `NewsScore.md`, `SentimentScore.md`, `EventScore.md`, `RiskScore.md` - under
  `docs/scores/README.md` (master: architecture, direction convention, engine map, the composite + the gate-order conflict,
  cross-engine rules, the CODE-DEFECT LEDGER, wiring contracts, phase plan, verification requirements, decision record, open
  questions, Appendix B, evidence ledger). **Nothing was dropped in the move**: the fundamental document keeps §0 method, §1
  what exists, §2 the 106-factor ledger, §3.1-3.6 the four sub-scores, Appendix A and C.1; the other engines' material moved
  into their own documents, each expanded with a component ledger, tool-leaf map, defect list, build order and methodology
  ledger. **Every row in every ledger was re-verified at the definition site by a read-only scout** (six inventories), and
  the load-bearing findings are: `TechnicalScore` - no composite technical score exists in ANY of the three repos (the only
  0-100 "trend score" is an LLM-supplied argument at `analysis_tools.py:9247`), five of nine categories scorable, and six
  non-monotonic inputs that must be band-mapped rather than ramped; `RegimeScore` - the "regime conflict" is a NAME COLLISION
  between two paths sharing no inputs/scales/labels (`get_regime_read`→`overlays` with `enable_strategy_overlays` default
  True vs `get_regime_state`→`regime_state.regime_state` with `regime_state_enable` default False), both bound to the market
  analyst; `RiskScore` - no 0-100 risk score exists anywhere, all eight categories exist as components at THREE incompatible
  sign/unit conventions (CVaR negative vs positive vs equity fraction; drawdown positive vs negative-labelled vs negative; two
  cap families), so the document pins one convention each and prints raw values beside aligned contributions; `NewsScore` -
  5 of 9 categories ABSENT, `score_news_article:53` scores RELEVANCE not MATERIALITY (quoted), the duplicate-of-Sentiment
  question is NOT settled by construction (four couplings); `SentimentScore` - four holes (20d momentum, acceleration,
  per-source breadth, institutional bound to the FUNDAMENTALS toolset at `toolsets.py:395`), Sentiment x Price Confirmation
  PARTIAL (no quadrant, no abnormal return, and the wired fold is a single-name self-correlation, gated off), plus the GDELT
  -100..100 vs -1..1 scale mismatch on the news-sentiment route; `EventScore` - no weights from the owner and that is coherent
  (every producer is a multiplier/day-count/boolean), occurrence for 4 of 7 families, the ONLY event hard block is the
  earnings blackout, and the executor's 17 GATE_PRECEDENCE checks contain NO event check. The master's §3 is the defect
  ledger: the six §1.5 defects being fixed plus TWELVE more found by these inventories (dead value-area accumulator,
  unreachable `support_structure` branch, `size.atr` returning 0.0, an NA->0 substitution in `rank_sectors_multifactor`, two
  LLM-supplied numbers presented as computed, an unbounded Chaikin labelled a verdict, a dead `implied_move_pct` key, an
  unreachable premarket hard block, an inert `catalyst_window` veto, an unread MACD-slope producer, an unreachable
  multi-horizon momentum vector). References updated for the move: `scripts/value_screener.py`,
  `tradingagents/strategies/factors.py`, `docs/design_quant_formulas_research_round3.md` (earlier CHANGELOG/onboarding entries
  keep their original paths - they are dated records).
- 2026-09-17 `(working tree)` - **Design only, no code:** the owner staged `docs/ScoreWeight/{fundamental,market,news_sentiment}.md`
  (their own newer spec) and the design doc is folded into it. **Six engines plus a recommended seventh** (Fundamental,
  Technical, Regime, News, Sentiment, Risk, + Event), four factor catalogs targeting ~250-300 factors, research
  allocation 35/20/15/7.5/7.5/15 with EventScore's weight open. Staged weights GOVERN where they differ from the
  pasted-text iteration (TechnicalScore gains volatility-ATR + breadth; RegimeScore gains breadth 15% + macro-credit
  and drops relative-regime; RiskScore splits concentration out of correlation, raises drawdown to 15% and gap to
  10%); superseded numbers are kept in the tables. §3.8 grounds the new engines: **NewsScore is 5-of-9 ABSENT**
  (novelty, materiality, fundamental impact, guidance change, corporate events, persistence) with only relevance
  (`news_relevance.score_news_article:53` - relevance not materiality), the PEAD leg, analyst revisions and macro
  reads computed, so it ships PARTIAL with its coverage printed; **SentimentScore is mostly buildable** with four
  holes (momentum is only a 7-day innovation, acceleration ABSENT, no per-source breadth, institutional sentiment
  bound to the FUNDAMENTALS toolset). **The news/sentiment duplicate question is NOT settled by construction** -
  four couplings feed one number to both (`sentiment.py:589 _weighted_basis` uses the news relevance as the sentiment
  confidence weight; `get_news_sentiment_series` bound to both `news_tools()` and `market_tools()`; the sentiment
  analyst pre-fetches `get_news` at `sentiment_analyst.py:88`; `domain_bundles.get_sentiment_flow_feed:93` bundles
  them) - so the owner's separation requirement is a build-time NAMING rule. **Sentiment x Price Confirmation is
  PARTIAL**: `sentiment_lead_lag:65` gives Corr(dSentiment, dPrice) and `sentiment_factor_scale:570` uses sign
  agreement, but the owner's `Sign(dSentiment) x Sign(abnormal return)` quadrant with a market-adjusted return does
  not exist. **EventScore** (the staged spec's seventh engine, the gate before NewsScore touches `opportunity_score`)
  overlaps RiskScore's event leg: occurrence vs exposure, same producers, resolved by naming. Two conflicts in the
  owner's own diagrams are FLAGGED in §8.3, not silently resolved: gate order (pasted: gates before sizing; staged:
  after; the engine implements before) and which composite governs. Evidence added: Tetlock (pessimism -> next-day
  decline then reversal, extremes -> volume, price->tone feedback), Baker-Wurgler (high sentiment -> lower returns in
  hard-to-value names), Barber-Odean/PEAD (novelty and attention drive immediate incorporation), Da-Engelberg-Gao
  (**attention** -> negative next-day vs **bullish sentiment** -> positive: do not merge them).
- 2026-09-17 `(working tree)` - **Design only, no code:** the four-score architecture (owner's spec) is added to
  `docs/design_fundamental_factor_weight_model.md` as **§3.7**, grounded component-by-component against the engine by
  three read-only inventories (technical / regime / risk), with a literature pass. The shape: four SEPARATE 0-100
  scores - `FundamentalScore` (the ten categories + bands 80-100 exceptional / 65-79 strong / 50-64 average / 35-49
  weak / 0-34 poor; a high score is NOT Buy), `TechnicalScore` (trend 25 / momentum 20 / setup 20 / RS 12 / volume 10
  / breakout 8 / mean-reversion 5), `RegimeScore` (trend 20 / vol 20 / momentum 15 / choppiness 15 / sector 10 /
  relative 10 / event 10), `RiskScore` (portfolio 20 / tail 15 / vol 15 / liquidity 10 / concentration 15 / drawdown
  10 / event 10 / gap 5) - **all in one direction (100 = favourable), so `RiskScore` is inverted relative to how risk
  is measured**; then `TradeScore = 0.40F + 0.25T + 0.15R + 0.20K`, which **never overrides a hard gate** and whose
  weights are learned empirically later. Readiness measured: `TechnicalScore` is an aggregation over existing leaves
  (no composite technical score exists anywhere; five consumers read the OPPOSITE polarity - RSI band, MFI oversold,
  stochastic oversold, the elder thermometer's quiet dip, and `support_structure`'s near-200-SMA-good vs `swing`'s
  above-200-SMA-good), `RegimeScore` has no market-level score at all (only states, multipliers and raw numerics),
  and `RiskScore` has **no 0-100 producer anywhere** (grep both repos: zero hits) though all eight components have
  producers and six existing numbers already sit in the favourable direction. The reported MSFT regime conflict is
  resolved as a **name collision**: `get_regime_read` (3-valued vol proxy + hardcoded chop=0.4 -> neutral + scale
  0.47x) and `get_regime_state` (ATR/EMA/benchmark/252-bar high -> four labels + F_regime = min of three legs) share
  no call path, are gated independently, and are BOTH bound to the market analyst - so a RegimeScore must name one
  producer per component or arbitrate with a stored reason. Score/scale/state/confidence stay separate (sizing is not
  conviction). **Six code defects found and NOT fixed (design-only pass), recorded in §1.5:** (1) `overlays.py:57`
  passes a hardcoded `chop=0.4` against `regime_label`'s default `chop_threshold=0.30`, so the chop branch is dead
  and with the common `vol_pct == 0.5` the label is `neutral` REGARDLESS OF TREND - a quoted `regime=neutral` may
  carry no information; (2) the same quantity is passed on two incompatible scales (`chop_threshold=30.0` at
  `analysis_tools.py:2176`); (3) `donchian_channel` returns breakout flags None by construction with no caller
  deriving them; (4) `parabolic_sar` called without `closes` at `analysis_tools.py:1160`; (5) `BookState.net_beta`
  has no reader; (6) gap fill probability / days-to-fill are constants. **Next pass: fix those six** (rule 10) -
  defects 1-2 first, since they affect report text today and the RegimeScore arbitration is blocked on them.
- 2026-09-17 `(working tree)` - **Design only, no code:** the five open questions in
  `docs/design_fundamental_factor_weight_model.md` §8 are ANSWERED by the owner and the design is updated to them.
  Decisions: **Q1** the composite never reaches `opportunity_score` (stays a tool-leaf / `run_card` advisory metric;
  the slot keeps its `null` and gains a producer-owned `opportunity_score_reason`) - a `FundamentalScore = 84` is not
  an `Opportunity = 84`; **Q2** learned walk-forward weights are IN SCOPE as a separate research layer, never inside
  the deterministic production score, promoted only along `RESEARCH_ONLY -> VALIDATED -> CONTRACT_MIGRATION ->
  PRODUCTION`; **Q3** sector overlays are architecture-in-scope now (factor schema carries `sector_scope` /
  `supplier` / `availability`), suppliers deferred, and **`NA != 0`** - a missing metric reduces the available weight
  instead of punishing the name, and a missing metric is never manufactured from generic factors; **Q4** the full
  EODHD US panel is the official validation universe, the named basket is dev-only and labelled
  `INSUFFICIENT_CROSS_SECTION`; **Q5** no `factor_score=NN` in prose - scores live in structured output
  (`fundamental_score`, `..._status`, `..._confidence`), because a number in prose becomes apparent objective ground
  truth. The owner also withdrew his own earlier `TradeScore = 40/25/15/20` for the same reason, so the composite
  ships as a RESEARCH artifact with a status vocabulary and the four deterministic sub-scores are the advisory
  output. Doc changes: new §0.5 (decision summary + three-stage separation), §3.1 (score contract: Fundamental /
  Technical / Regime / Risk advisory, Opportunity separate and null), §3.2 (per-factor schema + `NA != 0`), §4
  restructured into decided / still-refused / deferred, §5.2 (the reason field, contract migration NOT scheduled),
  §5.3 (Q5 closes the prose-ground-truth coupling), Phase C (EODHD universe, IC/ICIR/decile-spread/monotonicity,
  the `score_evaluation_rows` floor gap), Phase D (the promotion ladder), §7 (four new verification requirements),
  §8 (the decision record with rationale). **No code defect was implicated:** no prompt requires a score in prose,
  the gated `quality composite` leaf is already the structured-diagnostics surface Q5 asks for, and the `NA != 0`
  convention is already implemented (coverage floor + `withheld`, omit-don't-zero in `growth_metrics`,
  renormalisation in `capex_quality_read`).
- 2026-09-17 `(working tree)` - **Design only, no code:** `docs/design_fundamental_factor_weight_model.md`, the adoption
  design for an external 106-factor fundamental weight master table. Method: inventory first (every factor read at its
  definition site), then accept/reject with cited evidence, then a four-phase plan. Findings that decide the design -
  **36 of 106 factors already computed here (42.15 points of the proposed weight), 26 partial (20.35), 44 absent
  (41.50)**; Valuation (20% of weight) is the most complete category at 13.25/20 while Cash Flow (17%) is the biggest
  hole at 11.00 absent; the source's own per-factor weights sum to **104.00%**, not the stated 100%, across four
  categories. Adopted: the four sub-score split (quality/growth/valuation/risk) instead of one master number, an
  `EffectiveWeight` chain over measured surfaces only, a derived A/B/C/D confidence grade, a `dcf_confidence` over four
  legs the DCF family already prints, and `capex_quality_read` as the capex direction source. Refused with evidence:
  unmeasured "production weights" (DeMiguel 1/N; round-3 rule 2), learned/regime weights (McLean-Pontiff; Asness
  factor-timing; ground rule 1), bank/REIT overlays (metrics absent from the canonical vocabulary - a data project),
  the literal `1/(1+Σ|Corr|)` constant, and wiring any composite into `opportunity_score` (owner decision; the slot is
  deliberately null at `execution_contract.py:240-252`). Structural defects recorded for the next pass:
  `roa_series`/`revenue_series` have **no producer** (G-Score G4/G5 are dead legs), `industry_neutral_z` demeans by
  sector while the final percentile is taken across the whole peer set (so `QUALITY_BANDS`' "sector median" band is
  mislabelled), and `scripts/value_screener.py`'s docstring advertises two screens with no implementing symbol.
  **All four were then fixed in the same pass** (owner: "fix all found defects"): (1) new
  `statement_parsing.annual_series` is the producer the G-Score G4/G5 and Dechow-Dichev readers never had - one
  canonical dict per fiscal year through the same row matcher, a moomoo payload's per-statement tables merged by
  year, `roa_series` derived on beginning-of-year assets aligned by fiscal year, no key spliced across payloads, and
  `fetch_ticker` attaching revenue / net income / total assets / operating cashflow series with provenance naming the
  period span; (2) the 50 band is renamed "peer median" because the percentile is over the scored peer set, with the
  within-sector percentile left as design work; (3) the screener docstring now marks Return on Capital and
  Shareholder Yield as unimplemented and names the missing inputs; (4) the Dechow-Dichev caller reads the real series
  with accruals on the Sloan proxy `(NI - CFO) / total assets`, the substitution printed beside the value, and
  `DD_MIN_PERIODS = 8` states the true bar (6 residual rows need n-2 >= 6) for both the function and the caller.
  11 new tests (7 statement-parsing incl. the producer->G-Score integration, 3 earnings-quality caller, 1
  Dechow-Dichev bar); affected suites 326 + 54 + 38 green, full suite **4385 passed / 5 skipped**. Live smoke: MSFT and AAPL now carry
  5 series keys over 4 annual periods (roa n=3, all `annual`, no conflicts) and the earnings-quality leaf prints
  `dd_aq=n/a (needs 8+ annual periods)` - so both new producers are correct and UNFIRED on today's vendor history: G4/G5 need a 5th
  period and Dechow-Dichev needs 8. `sec_edgar.get_financial_history` (15 annual years, US filers, tool at `analysis_tools.py:8783`) is
  the unlock and is design item §3.6/8. Remaining wiring opportunity unchanged and larger than
  before: level ROIC (invested capital is built at `value_dip_tools.py:510` only as a ΔIC denominator), gross margin
  (stored at `statement_parsing.py:841`, never rendered), interest coverage (`interest_expense` has no reader), and
  buyback/shareholder yield (`share_buybacks` has no reader).
- 2026-09-16 `(working tree)` - The MSFT fundamentals review round: the DCF family now says what a price REQUIRES, and
  the net-debt basis is disclosed instead of relabelled an error. Reviewer feedback on `reports/MSFT_20260916_231406` read
  against the tree + the FY2026 release: every quoted number checked out, and the diagnosis was sharper than the report's -
  `compute_dcf` is not *nearly* a current-FCF perpetuity, it **is** one (the N-year window at `g` plus Gordon at the same `g`
  telescopes: 8.85 x 1.025/0.075 + 3.84 bridge = **124.80**, the printed leaf to the cent). Chasing his net-debt point
  exposed a false claim in our own producer: `y_finance._net_debt_note` declared the vendor row "net-CASH ... do not quote
  it" and the report repeated it as "mis-signed" - the row reconciles exactly on the narrower basis (31,067 + 9,227 - 20,935 =
  19,359). The note now reconciles four standard bases and DISCLOSES (basis + widest basis + figure, one instruction not to
  call it a sign error); unreproducible rows (AMAT/WDC) are named, sign-agreeing rows (AMZN, whose net debt excludes
  operating leases) stay silent. Corpus: 8 of 20 stored payloads fired before and after, but **6 of the 8 were false
  vendor-error claims**. Fixes under the same pass: canonical `total_debt` now completes from the long/short-term legs when
  a payload has no total row (moomoo; reproduces the vendor's 47,599 + 9,227 = 56,826 exactly, prior period intact), a new
  `cash_and_investments` key gives the DCF bridge a payload-independent cash basis (76,651m vs the narrow 20,935m), Finnhub
  gap-fills `beta` (1.0626 for MSFT - previously always assumed), and `get_dcf_valuation` prints `cash=/debt=/net_debt=/
  bridge=/equity=` plus `beta_sensitivity=` when beta is assumed. Live MSFT: **124.80 -> 118.73**.
  New instruments (new `strategies/reverse_dcf.py` + `strategies/normalized_fcf.py`, both bound to the fundamentals analyst):
  `get_reverse_dcf(ticker, current_date, growths=?)` inverts the convention for the market price - MSFT at 490.30 implies
  **281.3bn** steady-state FCF at 2.5% (186.7bn at 5%, 114.3bn at 7%) or **8.35%/yr perpetual growth** on today's 66.98bn;
  `get_normalized_fcf_dcf(...)` runs the revenue-driven capex fade (capex/revenue 34.94% -> 11.61% = D&A/revenue over 5y)
  with the maintenance floor (OCF - D&A) in the same leaf and `defensive_capex_share` as the counterweight - MSFT: **437.55**
  faded / **217.94** defensive / **252.97** maintenance against the run-rate **118.73**. Prompt: `DCF PLAUSIBILITY CHECK` now
  REQUIRES basis-mismatch labeling (a 12-month PT is not an intrinsic value and never overrides a DCF), the price-implies
  question, and a valuation conclusion rather than "the model is an artifact"; new `NET-DEBT BASIS` and `INSIDER WEIGHTING`
  rules. See CHANGELOG.
  Tests: `test_reverse_dcf.py` +19, `test_normalized_fcf.py` +12, `test_analysis_tools.py` +6, `test_render_honesty.py` +3,
  `test_yfinance_keyless_vendor.py` re-pointed to the basis contract; full suite **4374 passed / 5 skipped**.
- 2026-09-16 `(working tree)` - Prompt-budget pass, on the owner's instruction plus one defect found while measuring. `MARKET_CEILING`
  raised 42_050 → **50_000** (standing headroom; the market prompt still measures 41,999, bullet count 79/95 and the
  longest-bullet pin 523 unchanged and still binding). The sentiment prompt's verbatim-counts item is now pinned by
  `test_report_verify.py::test_sentiment_prompt_requires_verbatim_counts`, which renders the real prompt, finds the item by its
  lead (renumbering is free) and asserts inside that item alone: the three governed figures (message counts, upvote/comment
  totals, computed-block values), the no-rounding prohibition, and the obligation wording - mutation-checked, and a match that
  finds nothing cannot pass. The counts half of that class has no deterministic backstop (`_anchor_claims` covers only
  `computed_score`), so the prompt is the control. **Defect fixed on sight:** `prompt_literal_text` excluded every `Constant`
  inside an `ast.JoinedStr` to avoid double counting, but `ast.walk` already visits f-string segments once - so f-string prompt
  text was invisible to the ceiling: news 13,160 → **15,337**, sentiment 1,406 → **7,105** (its whole system message is one
  f-string), market/fundamentals unchanged; `test_other_analyst_prompts_stay_bounded` now includes sentiment, so all four prompt
  modules are size-checked. See CHANGELOG.
  Tests: `test_prompt_budget_contract.py` (helper fix + ceiling), `test_report_verify.py` +1; full suite 4330 passed / 5 skipped.
- 2026-09-16 `(working tree)` - Analyst rule-prose consolidation across the market / news / fundamentals prompts (plus the
  sentiment prompt's conflict-weighting and verbatim-count rules): the same
  principle was stated two or three times under different headers (four basis rules → `BASIS DISCIPLINE`; six quote/session
  rules → `QUOTE-TYPE & SESSION INTEGRITY`, seven → `CANONICAL VALUE DISCIPLINE`, three → `ATR & STOP MECHANICS`;
  `FOMC DIRECTION`+`CATALYST LABEL` → `FED-EVENT LABELING`; `MACRO MUSTS`+`10Y FRED ID`+`DAY COUNTS` → `MACRO DATA
  PROVENANCE`; index/SEC-8-K/insider → `EVENT-SIGNAL RESTRAINT`; `EARNINGS DATE`+`TOOL-STATED CAVEAT` → `CONFIDENCE &
  CAVEAT CARRYING`), plus one new rule per prompt class: `DCF PLAUSIBILITY CHECK` (fundamentals), `INTRINSIC-VALUE
  PLAUSIBILITY` (market, against the options-implied read) and `SIGNAL SYNTHESIS` (all of them: name the conflict, state what
  was weighted). The sentiment macro pin takes the same `MACRO DATA PROVENANCE` header - `test_news_analyst_prompt.py` now
  asserts the two modules agree, so one rename cannot land without the other. Every tool name/parameter/citation verified
  preserved (the market indicator/tool block is byte-identical to the previous revision), the market tool block's stray
  4-space indent (which had pushed the longest bullet to 527 for a whitespace-only reason) is stripped, and `MARKET_CEILING`
  raised 40_300 → 42_050 (measured 41,999) with the reason in the comment - raised again to 50,000 the same day, and the
  news size quoted there corrected, in the entry above. See CHANGELOG.
  Tests: `test_prompt_budget_contract.py`, `test_analyst_evidence_wiring.py`, `test_news_analyst_prompt.py` (+1),
  `test_report_verify.py`, `test_structured_agents.py`; full suite 4324 passed / 5 skipped, all four rendered system
  messages carry every new section header.
- 2026-09-16 `(working tree)` - Two argument contracts inside the trader's tool loop, found by running its verify prompt
  against the live provider after the markup fix: (1) **the unit trap** - every sizing/risk argument is a FRACTION of
  capital while its name ends in `_pct`, so `get_risk_gate(size_pct=1.0)` for a 1% proposal answered
  `size 100.0% > cap 30.0% -> REJECT` (a REJECT the desk never issued, cited by the report), and the same trap pinned
  `risk_per_trade=1.5` to the cap and collapsed `stop_dist_pct=8.371` to a 0.12% size. New
  `analysis_tools._fraction_errors` refuses a percent number with the corrected form (fail closed, never coerce) and
  issues no verdict from it - size-like args from `1.0` up (the ambiguous value), rate-like args only above `1.0`;
  wired into `get_position_sizing`/`get_composite_sizing`/`get_risk_gate`/`get_composed_risk_gate`/`get_fixed_risk_size`.
  (2) **the invented level** - `get_exit_check`/`get_exit_plan` took close+ATR from the caller and the pass supplied
  `atr=7.0`, which no tool had returned, so a measured-value path now exists (`_measured_levels`: the run's own last
  close + 14d ATR), a measured value wins over a conflicting caller one, and without a ticker the output labels its
  levels `CALLER-SUPPLIED ... not measured`. Prompts state both contracts (loop system directive for the trader + risk
  debators; the trader's verify prompt names `ticker`; the market analyst's tool lines state the fraction convention)
  and `docs/api_reference.md` carries the new signatures. No report-tree correction needed - the only surviving REJECT
  claims in the 11 repaired trees are CVaR-budget rejects computed on a correct fraction. See CHANGELOG.
  Tests: `test_analysis_tools.py` +7; full suite 4257 passed / 5 skipped.
- 2026-09-16 `(working tree)` - The Trader's "Computed verification" block was, in 11 of 22 archived trees, the provider's raw
  tool-call markup instead of a computed spec: `risk_tool_loop.run_tool_loop` read `result.tool_calls` only, so a relay answering a
  tool-bound turn with its native markup in `content` and an EMPTY `tool_calls` list left `pending == []`, the `while` never ran, and
  the markup came back as the model's "final prose" - appended by the trader under a heading claiming deterministic verification while
  **no tool had run**. Same provider/model as a clean NVDA run three hours earlier (`openrouter` + `deepseek/deepseek-v4.1-flash`), i.e.
  intermittent emission; upstream it is the documented provider/parser mismatch. Fixed in three layers over one new vocabulary module
  (`agents/utils/tool_call_markup.py`: `parse_text_tool_calls` / `has_tool_call_markup` / `strip_tool_call_markup`): the loop dispatches
  markup turns through the same `ToolExecutor` (and rewrites the turn as a well-formed function call so strict backends accept the
  ToolMessages), `_final_prose` guarantees markup never returns as prose, `trader._verification_is_stub` refuses to append a markup reply,
  and `report_verifier._TOOL_CALL_MARKUP` is now the shared regex (it could not match the `tool_`-less spelling the reports carried). All
  11 leaking trees repaired in place (1700 lines removed from `trader.md` + the embedded copies; backup in `%TEMP%`). See CHANGELOG.
  Tests: `test_risk_agent_wiring.py` +3, `test_structured_agents.py` +1, `test_report_verify.py` detector spelling; full suite 4250
  passed / 5 skipped, web 149, executor 1102.
- 2026-09-15/16 `(working tree)` - IEI verification round + debate round separators + a docs pass. Verifying `reports/IEI_20260915_210623`
  (the first IEI run) returned FLAG on market/sentiment; adjudicating all 13 non-GROUNDED claims found one real report defect
  (`get_capital_flow` counted as "negative in 7 of the last 8 weeks" where its own weekly table shows 6 of 8) and two analyst-recall
  defects (a hedge-fund "basis-trade unwind" mechanism no leaf carries; a "~4-5 year duration" figure that the same tree's fundamentals
  section had correctly refused), plus five verifier false-positive classes, all fixed: `_PRIMARY_PRICE` had no leading `\b` (the market
  section's own caveat "Treat 114.33 as unverified" became the report's spot price, and two verbatim `get_swing_set` targets were flagged),
  `t1`/`t2` scoping was per line by the first tool named on it (now per SEGMENT, with a framework-label fallback for tool-less summary
  rows), a foreign metric's percent counted as a 200-SMA distance, a dated series read as two competing 10-EMAs, and the bare `fomc` macro
  trigger now accepts a leaf naming the central bank. Separately `2_research/bull.md`/`bear.md` never gained the risk section's
  `### Round N` separators - the writer passed `role="Bull"` while the debate state labels every turn `"Bull Analyst:"`. Then a docs pass
  against the code: the verifier design doc's reopen checklist refreshed (the 2026-09-08 "no open code defect" conclusion marked
  falsified, the closed `vrp` and `t1`/`t2`-SKHY classes moved to "closed", the survivors re-measured), `.env.example` backfilled to every
  code-referenced key (209 -> 248 names), README/api_reference/onboarding corrections, and the web repo's stale pointers fixed.
  See CHANGELOG. Tests: `test_report_verify.py` 180, `test_report_readable.py` +1; full suite 4246 passed / 5 skipped.
- 2026-09-14 `(working tree)` - Verifier capture/binding hardening (adjudicating the MU/SNDK/DELL/SKHY batch: 727 claims, 639 GROUNDED, 78
  INTERNAL_CONFLICT, 6 UNSUPPORTED, 4 MISQUOTED, 0 CONTRADICTED). The deterministic same-metric scan was inflating its own list: `_DOLLAR_RE` stopped at the
  first comma (`$28,243,000,000` -> 28, `$1,166,000,000,000` -> 1), the `scenario dcf bear/base/bull` labels consumed the value's leading digit, the displayed
  raw string carried a 6-char slice of prose ("rice (919.97"), `stoch` matched `stochrsi`, a VIF row's score read as the RSI level, `>= 1.3` read as a second
  RVOL, `12m` read as 12 million, and a `[\d.]+` capture swallowed a sentence period, which made `_dupont_identity` raise (`float('1.5286.')`) and silently
  drop the DuPont check. Two binding errors: `_r_multiple_identity` crossed one tool's entry with another's stop (targets are verbatim tool output - swing_set
  2R/3R off the structure stop, swing_exits off the chandelier, tranche_plan off an averaged entry at 1.8R/3.0R), and `_valuation_band_conflict` demanded
  realized coverage from `get_expected_move`'s option-implied band (no calibration pairs; the conformal tool prints its own coverage). Fixed: comma+`T`
  figures, unit-boundary/R-suffix capture, prefix/VIF/threshold/growth-%/12m/period-qualifier guards, table-cell + slash-list pair binding by label ordinal,
  per-tool scoping for `t1`/`t2`, a conformal-context gate, line-local R-multiple binding (spot-price anchored, multiplier-aware), `(\d+(?:\.\d+)?)` captures.
  All 45 archived trees: conflict rows 409 -> 186, metric errors 0; four new trees: R-multiple/band claims 12 -> 0. Verifier tests 170 -> 180.
- 2026-09-14 `(working tree)` - Sentiment macro leaf (S11b for the sentiment stem, gate `enable_evidence_symmetry`): SKHY 2026-09-14 stated "US 10-year above
  5%" with no macro leaf in its own evidence (this node binds no tools, so `gather_for_analyst_node` never runs for it) and the verifier flagged it. The node
  now fetches `get_macro_indicators("10y_treasury", end_date, 30)` once under the gate, journals it as a leaf under `tool_evidence.sentiment`, adds it to the
  prompt as the only quotable macro level, and requires a disagreeing headline to be reported as disagreeing. Gate off = byte-identical stem. Tests:
  `tests/test_structured_agents.py` (+1 node, 2 pinned gate-off), `tests/test_report_verify.py` (+1 prompt).
- 2026-09-13 `(working tree)` - S11c wiring: the mirrored discretionary budget was implemented in
  `evidence_gather._journal_executed` but its allowance came from `evidence_symmetry_pairs`, a key that was
  **undeclared and env-unreachable**, so the mirror could never activate (nothing was ever suppressed; the
  standalone `mirror_discretionary_budget` API had no caller). The key is now in `default_config.py` (`[]` = inert)
  and reaches `.env` as `TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS` - a JSON list of `{roles, budget}` specs, accepted by
  any list-valued override (malformed JSON raises at startup). One split rule (`_split_discretionary`) and one
  suppression-journal helper are shared by the pair API and the live path; a forced (S11b) leaf is never suppressed
  and no longer consumes the allowance. Measured: budget 1 suppresses the surplus with its args in the tool-call log;
  a pair without a budget mirrors the smallest count an already-run partner recorded; no pair declared = byte-
  identical to gate off; the deterministic gather is untouched. Caveat: the mirror drops the evidence **leaf** after
  the call executed, so keep budgets at or above a pair's natural counts (the transcript still holds the result).
  Tests: `tests/test_evidence_symmetry.py` (+7).
- 2026-09-13 `(working tree)` - Launcher env vs `.env`: importing `tradingagents` reloaded the whole `.env` with
  `override=True` to force the three output-cap keys and restored only those, so every other declared key (~190)
  overwrote the caller's `os.environ` - an exported `TRADINGAGENTS_ENABLE_*` / provider / temperature was silently
  ignored, and the only way to flip a round-3 gate was editing `.env`. The force-set is now scoped
  (`dotenv_values` + `os.environ.update` for the three cap keys only), so both paths work:
  `TRADINGAGENTS_ENABLE_GROWTH_SCORES=true py -3.12 batch.py ...` and `.env`. Tests: `tests/test_env_overrides.py`
  (+3: the exported temperature survives the import, a gate flips for one process, a low launcher cap is still raised).
- 2026-09-13 `(working tree)` - Drafting-monologue guard: a free-text deliverable can arrive as the model's
  private planning/self-correction monologue (MU 2026-09-13 research run: 5.6 KB of "why does my decimal become
  asterisks" ahead of the real plan in `2_research/manager.md`, and therefore inside the Trader / Portfolio Manager
  prompts that read `investment_plan`). `agents/utils/structured.py` now detects it
  (`_looks_like_drafting_monologue`; thresholds measured against every report file on disk - only the leaked
  monologue matches), keeps the monologue's own final draft when there is one (`_salvage_final_draft`, free - it
  recovered the real plan from the same response), else re-asks once on the backup model, else emits the explicit
  unavailable notice; wired into all three free-text chokepoints - `invoke_structured_or_freetext`
  (RM/trader/PM), `retry_chain_if_stub` (analyst reports) and `retry_llm_if_truncated` (bull/bear researchers
  + the three risk debators) - each writing a `monologue/<agent>` journal note. Tests:
  `tests/test_structured_monologue.py` (16).
- 2026-09-13 `(working tree)` - Round-3 scoring/sentiment implementation (S1-S11; ten `enable_*` gates, all
  default-off): `quantitative_scores.altman_variant`/`altman_zone` + `piotroski_f_score_detailed` +
  `growth_score`(G1-G8)/`overpriced_score`(C1-C6), `strategies/peer_universe.py` (ONE resolver for the screener
  scan universe - `tickers=`/`financials=` let the screener pass its own scanned cross-section - plus
  `resolve_growth_medians`/`sector_medians_for`, all built on `statement_parsing.screen_ticker` so the columns and
  the medians cannot drift), `strategies/analyst_revisions.py` (weighted coverage-guarded revision ratio;
  estimate-change leg prints why it is unavailable), `factors.quality_composite` (0-100 winsorised-z percentile,
  coverage floor, published quality bands - never `decision_guardrail.SCORE_BANDS`; `QUALITY_DIRECTIONS` is the one
  direction table), `sentiment.aggregate_weighted_sentiment`/`crowd_ratio`/`sentiment_dispersion`/
  `weighted_rolling_sentiment`, `alpha_health.score_evaluation_rows`, and S11 in `evidence_gather` (symmetry
  report + declared-default args + mirrored discretionary budget + the gated plan call, wired into the three
  analyst nodes so the planner is inert until the gate flips). New tools: `get_analyst_revision_index`
  (fundamentals, gather pool); new rows on `get_quality_factors` / `get_composite_rank` /
  `get_news_sentiment_series` / `get_sentiment_computed`; screener columns G/C/Qual/RevIdx. **Also fixed while
  landing:** S11b's declared-default table was its own fallback, so an ungated `classify_tool_pools` /
  `gather_evidence` call moved `get_macro_indicators` into the deterministic gather - both now default to no
  table (gate-on callers pass `TOOL_ARG_DEFAULTS`) and the ungated split is byte-identical to HEAD. S9 stays
  unscheduled (plan Appendix A). 147 phase tests + 19 wiring tests, every phase's primary mutation proven
  failing first; design/plan docs marked landed. See CHANGELOG.
- 2026-09-13 `(working tree)` - QQQI news-review loop: the forced-tool short-circuit was never active -
  `evidence_gather.make_short_circuit_tool_node` guarded on `callable(node)` and a LangGraph `ToolNode` is a
  Runnable (not callable), so every production node returned unwrapped: no short-circuit, no tool-call journal
  and no model-pool evidence leaves (0 of 38 archived runs has one, though the QQQI news analyst really called
  `get_macro_indicators`/`get_prediction_markets`/`get_news_relevance_read` and the report quotes their outputs).
  The macro-authority gate therefore flagged five correct 10Y/RRP/Polymarket lines. Runnable nodes now get a
  `RunnableLambda` subclass that forwards the graph config and delegates unknown attributes (so `tools_by_name` keeps
  answering for the tool-binding contract tests); unwrappable nodes log a warning instead of returning silently.
  Model-pool leaves carry their call args. Also: `get_catalyst_scale` printed the modal probability as `8650%`
  (already a percent number, formatted again with `:.0%`) - now `86.5%`. See CHANGELOG.
- 2026-09-14 `(working tree)` - OpenRouter prompt caching + request shaping
  (plan: `docs/implementation_plan_openrouter_large_prompt_ttft.md`). The
  analyst system message is `messages[0]` and carries the forced-evidence
  block, but it was re-rendered on every tool-loop re-entry from state that had
  grown since (the tool node journals a leaf per LLM-called tool) and without
  the first render's S11b notes — so the prefix moved at token 0 and the
  implicit prefix cache never hit. `gather_for_analyst_node` now freezes the
  first render under the reserved `_rendered_block` key (list-of-rows; skipped
  by `_evidence_sources` and by `repro_check`'s `_`-prefix rule) and re-serves
  it byte-for-byte. Opt-in OpenRouter knobs: `OPENROUTER_STREAMING`,
  `OPENROUTER_SESSION_ID` (`auto` = per-client sticky id, ≤256 chars),
  `OPENROUTER_PROVIDER_SORT` / `_PREFERRED_MAX_LATENCY` /
  `_PREFERRED_MIN_THROUGHPUT` / `_REQUIRE_PARAMETERS` / `_ALLOW_FALLBACKS`;
  never `provider.order` (disables sticky routing). Footer prints `(cache N)`;
  the failure journal records `error_type`/`error_code`/`status_code` and the
  token+cache counters; `llm_cost.estimate_cost` prices cached input at the
  0.1x DeepSeek cache-read rate. Measured live: same client, same prompt,
  `cache_read` 0 -> 5888/6043 on turn 2. Tests: +8 client, +2 evidence.
  See CHANGELOG.
- 2026-09-13 `(working tree)` - QQQI market-review options loop: `strategies/options_math.py::expiry_days`
  reads the vendor's expiry label (ISO date / 6-digit contract stamp / 8-digit basic ISO; None when
  unreadable) and the five yfinance-chain readers (`_options_chain_rows_lambda`, `get_options_iv_read`,
  `get_vol_surface_shape`, `get_parity_screen`, `_machine_chain_vrp`) take T from it. Before, all five matched
  a 6-digit stamp against an ISO date, fell back to T=30/365, and priced a 68-day chain at 30 days - implied
  variance 0.1034 vs the correct 0.0458, gamma call wall 55.0 vs 56.0, an expected move labelled 30d off a
  68-day ATM IV, and an OI note claiming two tools' ratios came from one universe when they come from
  different expiries. Leaves now print expiry + horizon (and implied/realized VOL beside the variances). See
  CHANGELOG.
- 2026-09-13 `(working tree)` - QQQI fund-run data-quality loop: metric reconciliation is
  label-anchored (`TOOL_VALUE_RE` — first-number extraction was reading a note date as
  `get_fundamentals`' market cap and `10DayAverageTradingVolume` as 10, rendering a phantom
  `market_cap: VALUES CONFLICT range=10 .. 2026` that the report quoted as AUM), and a
  multi-vendor metric with no labelled value renders `NO VALUE IN EVIDENCE` instead of a range;
  `report_verifier._dividend_yield_sanity` parses fund distribution lists (cadence inferred from
  the dated prints, quarterly never annualized x12) and flags understated quotes (QQQI 9.00% vs
  14.02% implied by its own monthly prints); `y_finance.get_fundamentals` cross-checks
  `dividendYield` against `Ticker.dividends` TTM (>25% gap -> correction NOTE in the leaf). A
  157-report sweep gives exactly two yield-sanity claims, both true positives (MU stale field,
  QQQI understated). See CHANGELOG.
- 2026-09-07 `(working tree)` - Map-reduce forced tool gathering DESIGN + IMPLEMENTATION:
  design `docs/design_mapreduce_forced_tool_gathering.md`; plan
  `docs/implementation_plan_mapreduce_forced_tool_gathering.md`; code
  `tradingagents/agents/utils/evidence_gather.py` + state key `tool_evidence`
  + 4 analyst node wiring (market/fundamentals/news; sentiment is exempt —
  its 3 sources are already pre-fetched deterministically) + `repro_check
  --evidence` + `tool_evidence.json` persistence. Config:
  `TRADINGAGENTS_ANALYST_FORCED_TOOLS*` (off by default = legacy path).
  Addresses the analyst-side root cause of the 2/3 reproducibility probe.
- 2026-09-07 `(working tree)` - Debate reproducibility toolkit: judge ensemble
  (`TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE`) + `judge_agreement`/`judge_flip` in
  debate state, structured-fallback reliability flags (`judge_structured_fallback`,
  per-role `_structured_fallback`) via the new `invoke_structured_turn` `mode`
  return, field-level consensus in the RM/PM matrix, and `scripts/repro_check.py`.
  Configured ensemble=5 / temp=0.1 / judge=gpt-5.6-luna, plus a deterministic
  PM confidence gate (`cap_pm_confidence_on_judge`): judge flip / agreement<1 /
  free-text fallback caps the PM's confidence (default 0.5) and injects a
  "judge reliability" prompt line, so a borderline judge flip degrades
  confidence instead of silently swinging the verdict. A 2×3 TSM probe: both
  old & new config 2/3 self-agreement — flips reduced, not eliminated. See CHANGELOG.
- 2026-09-07 `(working tree)` - Reasoning-budget bound for OpenRouter models:
  `TRADINGAGENTS_OPENROUTER_REASONING_EFFORT` (`low|medium|high`, off by
  default) forwards `reasoning: {effort}` for the openrouter provider so a
  reasoning model (deepseek-v4-flash) that burns its WHOLE max_tokens on
  hidden reasoning (completion==reasoning==4000, empty report / JSON-parse
  fail) keeps output budget for the report/JSON. See CHANGELOG.
- 2026-09-07 `(working tree)` - Tool-not-found 400 on the cap-forced report
  retry: `structured._deorphan_tool_calls` strips unfulfilled tool calls
  before ANY chain re-invoke (`finalize_messages`, `retry_chain_if_truncated`,
  `retry_chain_if_stub`) so the strict OpenAI/Azure backup no longer 400s
  (TSM 2026-09-07: "No tool output found for function call"). Regression
  tests +3. See CHANGELOG.

  `graph.trading_graph._try_fetch_closes` now normalizes vendor OHLCV to
  ASCENDING date order (a NEWEST-first vendor left `closes[-1]` as the
  OLDEST close — TSM 2026-09-07 trade-plan card used 288.88 vs the verified
  428.91 bar). Mirrors `analysis_tools._ohlcv`; regression-tested. See
  CHANGELOG.

  on the backup LLM: when the `MAX_TOOL_ROUNDS` terminal turn returns
  empty content (reasoning model burned its output budget), the analyst
  is re-asked ONCE (backup chain when set, else same chain) with the
  completion directive, then emits an explicit `**Report unavailable**`
  notice if still empty - never a silent "" bare placeholder (QCOM
  fundamentals + NXPI market 2026-09-07). See CHANGELOG.

  retries: `TRADINGAGENTS_BACKUP_LLM` (`.env`, `backup_llm` config,
  `provider:model` or bare model on the primary provider). When ANY LLM
  response is cut at the output cap, the continuation retry runs on the backup
  model instead of re-paying the one that truncated; empty = same-model
  (legacy). One backup client resolved in `trading_graph` (its own provider's
  kwargs + quick-tier output budget) and threaded via `GraphSetup` into every
  analyst chain (`retry_chain_if_truncated` + cap `finalize_messages`),
  plain researcher/risk-debator (`retry_llm_if_truncated` / `run_tool_loop`),
  structured manager/trader/sentiment/independent-stance
  (`invoke_structured_or_freetext`), AND the structured debate turns + L2
  judge (`invoke_structured_turn`: a cut/unparseable structured call falls
  back + repairs on the backup). See CHANGELOG.
- 2026-09-06 `(working tree)` - Sector-rotation screen curated-breadth crash
  fix: `get_sector_rotation_screen`'s curated branch referenced `_top_note`
  before assignment (UnboundLocalError — the nxpi batch death) and the shared
  breadth block used `breadth_with_gate`/`leadership_ratio_ewcw` imported only
  inside the eodhd branch; both fixed, regression-tested. See CHANGELOG.
- 2026-09-03 `(working tree)` - PM node persists structured `pm_decision`
  (post-guardrail, model_dump json) -> research_decision.json carries real
  rating/data_quality on new runs; legacy nulls fail closed.
- 2026-09-03 `(working tree)` - `reporting.write_research_decision` emits the
  hash-pinned `research_decision.json` execution contract (TradingExecution
  daemon input; advisory; nulls for unproducible fields).
- 2026-09-02 `(working tree)` - remediation W1-5/W3-5/6/8 + W4-5/7/8: quant baseline, options depth, thesis matrix, injection detect, hybrid tier, notifier.
- 2026-09-02 `(working tree)` - remediation W2-6..10: impact/turnover/capacity/borrow/corporate-action models + survivorship guard.
- 2026-09-02 `(working tree)` - remediation W1-10/W2-11/W4-6/W1-11: regime-conditioned performance, stress grid, macro regime, ablation script.
- 2026-09-08 `(working tree)` - IT subsector ETF universe + dual-benchmark RS:
  `sector_rank.INDUSTRY_ETFS` extended with the IT subsector set (SOXX/IGV/
  CIBR/SKYY/AIQ/BOTZ/DTCR/NXTG/IYW/FINX/XSD, parent XLK; VGT = benchmark,
  excluded from the pool) so subsectors rank within IT; `get_sector_rank`
  industry layer emits `rs2` (percentile vs VGT) alongside the SPY-relative
  rank on the XLK pool ("strongest IT subsector" vs "beats the market", one
  pass).
- 2026-09-02 `(working tree)` - remediation W4 architecture: composite domain bundles, typed graph state, judge falsification grounding.
- 2026-09-02 `(working tree)` - remediation W1-2/4/6/7: calibration, scorecard, benchmark hierarchy, stop-outcome feedback.
- 2026-09-02 `(working tree)` - remediation W3 data integrity: quality score, disagreement flag, fundamentals-PIT invariant, falsification monitor.
- 2026-09-02 `(working tree)` - remediation W2 validation: CPCV/OOS/walk-forward/DSR guards on factor bench + proposal loop.
- 2026-09-02 `(working tree)` - remediation W1 measurement: `strategies/prediction_ledger.py` (decision prediction rows + MAE/MFE + hit/stop/target outcome scoring), `strategies/llm_cost.py` (rate-table cost estimates), wired behind `enable_prediction_ledger`. Plan: `docs/master_implementation_plan.md`.
- 2026-09-02 `(working tree)` - DSA phase D reporting: `strategies/report_disclosure.py` (driver attribution sum-100, consensus support/oppose, watch_conditions/next_check_time, >=1 invalidation per decision with manual fallback, sources-vs-empty + models footers); `reporting.write_report_tree` appends the advisory disclosure block to decision.md.
- 2026-09-02 `(working tree)` - DSA phase C polish: `strategies/skills.py` (YAML skill overlays + regime-from-opinion + router, `enable_skill_overlays` default off), `strategies/news_relevance.py` (relevance scoring + official boost + spam admission + degrade triple), `dataflows/news_cache.py` (owner-wait coalescing TTL cache).
- 2026-09-02 `(working tree)` - DSA phase B robustness: `dataflows/market_router.py` (market-classified vendor priority), `vendor_breaker.py` (3-fail/300s breaker + half-open + negative cache), `VendorResult` honesty fields, `dataflows/effective_date.py` (effective-trading-date + all-closed skip, fail-open). All opt-in (`market_source_priority`), default bit-identical.
- 2026-09-02 `(working tree)` - DSA phase A decision quality: `strategies/decision_guardrail.py` (downgrade-only stabilizer + risk-cap-at-Hold + versioned score<->rating validator + confidence cap on degraded data), PM schema `data_quality`/`guardrail_reason`/`risk_cap`, per-field integrity retry (`structured.retry_structured_missing_fields`); advisory, default-off `enable_decision_guardrail`.
- 2026-09-02 `(working tree)` - Qlib Phase-1 pure calculators (advisory,
  default off): `strategies/factor_expressions.py` (Alpha158-style profile +
  expression cache + learn/infer train-only moments), `signal_analysis.py`
  (rank IC/ICIR, quantile L-S, IC decay, pred-autocorr, with/without-cost
  table), `portfolio_strategy.py` (Topk-Drop + convex enhanced-index),
  `market_tradability.py` (limit/suspension/participation/deal-price in
  `backtest_strategy.py` fills); tools `get_factor_profile` /
  `get_topk_drop_plan` / `get_enhanced_index_tilt`; alloc-block strategy
  options; see `docs/design_qlib_integration.md`.
- 2026-09-02 `(working tree)` - Batch + structured-output robustness: `batch.py`
  gains the `_CLI_ENTRY` flush + `os._exit()` hard-exit (moomoo shutdown block
  no longer hangs a finished batch at interpreter exit; the entry block moved
  to file end); `invoke_structured_or_freetext` now runs the truncation
  continuation retry on the structured-success render (previously only the
  free-text fallback had it - a max_tokens cut inside a parsed structured
  result passed through to the report marker, e.g. ADSK deep PM 2026-09-02).
  Config guidance (gitignored `.env`): deep tier
  `deepseek/deepseek-v4-pro-0813`, `MAX_OUTPUT_TOKENS_DEEP=4000`,
  `LLM_MAX_RETRIES=3`. See CHANGELOG.
- 2026-09-02 `(working tree)` - `positions_to_basket` cash detection: Fidelity
  "Pending activity" settlement rows (blank quantity, symbol marker) now count
  as cash, not a phantom ticker (Sep-02 Account1 export had $8,993 pending
  that was being emitted as `PENDING_ACTIVITY` in the basket). See CHANGELOG.
- 2026-09-02 `(working tree)` - Analyst report-stub guard: market / news /
  fundamentals analysts now run `retry_chain_if_stub` when their final turn is
  a status/progress note instead of the report (217-byte NVDA fundamentals
  stub 2026-09-02); the analyst is re-asked once to write the full report,
  else an explicit unavailable notice. See CHANGELOG.
- 2026-09-02 `(working tree)` - Nightly-review driver `--mode recent`:
  `scripts/nightly_review.py` gains a `--mode recent` option that reviews each
  symbol's MOST RECENT `reports/<TICKER>_<ts>/` folder (keyed on the
  folder-name timestamp; only folders with a prior decision; batch mode
  unchanged) - interactive CLI / `propagate()` / `pipeline.py` runs that never
  write a `batch_summary_*.jsonl` are now covered by the scheduled 07:35
  review. Tests `test_nightly_review_recent_mode_*` (2, hermetic); web
  `run_nightly` forwards `--mode`. Also: the driver hard-exits (`os._exit`,
  `_CLI_ENTRY` pattern) after a completed run so the moomoo shutdown-block can
  no longer hang the scheduled task, and the scheduled wrapper runs
  `--mode recent --max-symbols 25`. See CHANGELOG.
- 2026-08-31 `(working tree)` - Multi-agent debate architecture design
  (research-only, no code): `docs/design_multi_agent_debate.md` + the source
  `Strategies/Multi_Agents_Debate.md` — two-layer judiciary (deterministic L1
  gates first, then a blind dimensioned L2 LLM judge), heterogeneous models +
  config-time capability matrix, FSM orchestrator + 3 canonical wire schemas
  mapped to pydantic (`DebaterTurnPayload` / `L1DeterministicResult` /
  `L2JudgeDimensionedRubric`), R1 fast-abort / single-role regen, R2
  artificial-consensus reweight to baseline, R4 matched-compute A/B (Brier +
  max unforecasted drawdown). All `debate_*` config keys OFF by default;
  phased rollout P0-P6 (grounding contract → scoring/termination → models/
  capability → judge → A/B harness). See CHANGELOG.
- 2026-09-01 `(working tree)` - Parent-repo ports (#1/#2, no merge):
  `dataflows/date_window.py` centralizes the half-open UTC content window;
  StockTwits + Reddit trim to the run as-of window (look-ahead safe, #1220);
  the 5 legacy debators use `opponent_argument_or_opening` so round-1 openers
  get an explicit "has not spoken yet" marker instead of fabricating the
  opponent's position (#1176). Tests `tests/test_parent_ports.py` (12);
  `test_news_lookahead.py` migrated to the shared module. See CHANGELOG.
- 2026-09-01 `(working tree)` - Cookbook quant-strategy gap implementation
  (`Strategies/cookbook.md`): MOP-style `ts_momentum_weights`; new
  `strategies/cross_section.py` (winsorize / centered-rank / quantile-split /
  market-residualize / dollar+beta+sector-neutral book / no-trade band);
  pairs `spread_zscore` / `pair_signal` / `pair_quantities` / `ecm_loading`;
  `z_composite_alpha` + multi-horizon momentum; portfolio stats (turnover /
  turnover-cost / exposure / rolling-Sharpe / regime-split); Black-76
  rho/vanna/vomma/charm + `bsm_equity_surface` + `greek_pnl_response` +
  Cboe/VIX-style `model_free_implied_variance` (repairs the always-degrading
  `get_variance_premium`); CDaR; max-diversification weights; Merton
  distance-to-default; `forward_rate`; microprice/OBI `book_depth_read`.
  Agent tools `get_ts_momentum_weights` / `get_pair_trade_signal` /
  `get_event_pnl_response` / `get_book_depth_read` / `get_merton_distance`
  bound to the market analyst + graph ToolNode; Merton in the risk-debator
  loop; `get_tail_risk`/`get_risk_parity_alloc` extended. Tests:
  `tests/test_cookbook_gaps.py` (27 hermetic), affected suites 349 passed.
  See CHANGELOG.
- 2026-09-01 `(working tree)` - Structured-debate robustness: json_object
  route fix ("json" token in the judge prompt + flat `scores[]` rubric +
  tolerant coercion + deterministic prose-score fallback), claim-key
  resolution (normalize -> alias -> gated fuzzy), context-bounded debater
  prompts, 4000-token cap, section-aware 1-shot, risk-stance coercion,
  `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL`, CLI deterministic exit. Verified on
  live QCOM + DELL: no degraded turns, real judge scores, sound RM/PM. See
  CHANGELOG / design doc §10.6.
- 2026-08-31 `(working tree)` - Risk-section structured-debate parity
  (direction.md): the risk debate mirrors the research one — risk debators
  emit `RiskDebaterTurnPayload` grounded turns into `structured_risk_state`,
  the SAME blind L2 judge generalizes to 3 candidates (Candidate_X/Y/Z),
  model keys are shared (BULL → bull+aggressive, BEAR → bear+conservative,
  JUDGE → both judges; neutral = quick), ONE `TRADINGAGENTS_RESEARCH_DEPTH`
  knob drives BOTH round counts, the research router cycles rounds within
  the cap instead of hard-stopping after one, RM + PM get the judge
  evidence block, and `4_risk/structured_risk_debate.md` mirrors the
  research evidence block. Off-mode legacy chain bit-identical. Tests:
  `tests/test_debate_risk_parity.py` (18 hermetic) + 5 debate files total
  78. See CHANGELOG / design doc §9.
- 2026-08-31 `(working tree)` - Structured multi-agent debate IMPLEMENTED
  (opt-in `enable_debate`; design `docs/design_multi_agent_debate.md` P1-P5 +
  graph wiring): `strategies/debate_claim.py` (claim ledger + L1 verifier),
  `strategies/debate_score.py` (score / termination / severity triage /
  entrenchment index / divergence-floor / α-reweight),
  `strategies/debate_capability.py` (R3 role×model matrix),
  `agents/utils/debate_roles.py` (`resolve_role_llm` per-role + tool
  surfaces), `agents/utils/debate_structured.py` (dual-mode adapter),
  `agents/arbiters/debate_judge.py` (blind order-rotated L2 judge),
  `scripts/debate_ab_harness.py` (Brier + max-unforecasted-DD), the SD
  subgraph in `graph/setup.py` + `should_continue_structured_debate` router,
  `debate_state` channel, and reporting `2_research/structured_debate.md`.
  New `TRADINGAGENTS_DEBATE_*` env keys (+ `.env.example`). Legacy chain is
  bit-identical when OFF. Tests: 4 debate files, 56 hermetic. See CHANGELOG.
- 2026-08-31 `(working tree)` - CLI deep-run defect fixes: `--depth` / the
  interactive research-depth selection now map to the RISK rounds only;
  the bull/bear researchers each run exactly ONCE per analysis (previously
  'deep' = 5 bull + 5 bear turns, which multiplied runtime, and the later
  debate turns degenerated into rambling/empty arguments that poisoned the
  Research Manager — SKHY 20260831_130816 had a 300-line garbage bear turn
  + 3 empty bear turns and a 0-byte `2_research/manager.md`). Added an
  empty-argument retry + honest-note guard to both researchers and an
  explicit "plan unavailable" block in `reporting.py` when the Manager
  produces no plan (never a 0-byte file). Risk-debator and Trader in-node
  tool loops are capped at 2 tool rounds per turn to bound runtime.
  Docs/CHANGELOG updated. Tests: `test_reporting` available-block guards.
- 2026-08-31 `(working tree)` - Risk-calc to agent wiring (7-phase audit,
  `docs/design_risk_calculations_agent_wiring.md`): 18 previously-unreachable
  quant-risk tools bound to the market analyst; 12 new @tools (`get_fixed_risk_size`,
  `get_exit_overrides`, `get_pre_trade_read`, `get_ledger_risk_state`,
  `get_trade_plan`, `get_fixed_income_risk`, `get_pair_risk`, `get_vif_read`,
  `get_vol_cones`, `get_trade_excursions`, `get_alpha_scoring`,
  `get_regime_gate_read`); `get_risk_gate` now covers the full governor surface
  (daily-loss/HWM/sector/liquidity/capital-at-risk/halt); the computed
  decision context gained a risk factsheet (limits registry, vol estimates,
  tranche peak-deployed + capital-at-risk, fixed-risk size); the 3 risk
  debators run an in-node 23-tool risk loop and the Trader a 12-tool
  verification pass (`agents/utils/risk_tool_loop.py`, capped at
  MAX_TOOL_ROUNDS, plain-invocation fallback when the provider cannot bind
  tools); news analyst gains credit-stress + news-sentiment, fundamentals
  gains fixed-income + alpha-scoring, RM + bull/bear researchers get the
  computed context. Web value-tools += 5 new ticker tools. Tests:
  `tests/test_risk_agent_wiring.py` (22 hermetic).
- 2026-08-31 `(working tree)` - Report-truncation fix: interactive runs (SKHY
  08-30/08-31) saved only analysts + bull/bear/research-manager — the graph
  **ended after the Research Manager judge** because `graph/setup.py` had lost
  the `Research Manager -> Trader` edge (and the Bull/Bear debate conditional
  edges in the same block), so LangGraph had no path onward and
  `write_report_tree` skipped the absent Trader/risk/PM sections
  (`3_trading/ 4_risk/ 5_portfolio/`). Restored the Bull/Bear ->
  (Bull|Bear|Research Manager) conditionals and the full
  Research Manager -> Trader -> ... -> Portfolio Manager -> END chain;
  hermetic full-stream verification emits all decision keys;
  `test_production_setup_research_risk_chain_edges_are_wired` guards it.
- 2026-08-31 `(working tree)` - Tool-round cap `KeyError '<Analyst>'` fix: a
  run whose market/news/fundamentals analyst hit the 8-tool-round cap crashed
  with `KeyError: 'Market Analyst'` (LangGraph "During task with name ..."
  wrapper) because the cap routers return the analyst node name but
  `graph/setup.py` only registered `[tools, clear]` (sequential) /
  `{tools, clear}` (parallel subgraphs) as conditional-edge targets. The
  analyst node is now a registered self-loop target in both modes, and the
  three analyst nodes short-circuit the cap turn (strip dangling tool_calls
  via `structured.finalize_messages`, one terminal prose turn) so the loop
  always terminates and reports are never empty. Hermetic SKHY end-to-end
  repro in both concurrency modes; regression tests
  `test_production_setup_registers_analyst_cap_self_loop` +
  `test_parallel_subgraph_registers_analyst_cap_self_loop`.
- 2026-09-03 - cluster/exit gates: `allocation_block` hard `max_pairwise_corr` cluster gate (drop worst-correlated name when max pairwise corr exceeds the cap) + `trailing_stop_exit` ATR-adaptive trailing (`trailing_stop_atr_mult`); advisory/default-off; precedence documented (terminal risk > stop-loss > trailing > min-holding).
- 2026-09-03 - `--universe moomoo-screen` in the value screener: a
  whole-market value-dip scan via moomoo Stock Screening V2 (local OpenD) -
  server-side AND of value anchors (PE_TTM, market cap, ROE, optional net
  margin / debt-to-assets) with dip timing (5-day change, RSI 14, optional
  52-week-high distance), paginated, sorted by 5-day change; filter defaults
  from config (`TRADINGAGENTS_MOOMOO_SCREEN_*`, env-overridable) with
  per-flag overrides (`--max-chg5d`/`--max-rsi`/`--max-debt-assets`); a
  server-side price floor and P/B band (`--price-min`, `--pb-min`/`--pb-max`)
  and a configurable pullback window (`--dip-days`, default 5, reference 20)
  mirror the reference recipe; `-n` caps total symbols. Need: OpenD logged
  in, `moomoo-api`, protobuf pin; a client-side NYSE/Nasdaq exchange gate
  (`--exchanges`, default `NYSE,NASDAQ`, every universe) drops OTC/AMEX
  listings (screen V2's EXCHANGE field is non-functional for US; the gate
  uses `get_stock_basicinfo` exchange_type or the EODHD list). Web
  Screener exposes the universe + dip flags. Tests:
  `test_moomoo_value_dip_screen` + web forwarding. See repo CHANGELOG.
- 2026-08-31 `(working tree)` - `--value-dip-loose` harvest mode + eodhd-losers
  equity filter: the value-dip technical entry relaxes to `RSI<=35 OR %b<=0.10`
  (new `loose_technical` param on `value_dip_setup`, default False) and the
  screener appends a ranked near-miss table naming each near candidate's
  failed gate; `eodhd-losers` now cross-checks the exchange-symbol
  common-stock list (one cached call) so warrants/units/leveraged ETFs don't
  dominate the decliner seed. Web Screener exposes the Loose dip gate
  checkbox. Tests: `test_value_dip_loose_prefilter_or_semantics` +
  `test_eodhd_losers_equity_filter_drops_non_common` +
  `test_eodhd_losers_loose_near_miss_renders` + web forwarding case.
- 2026-08-31 `(working tree)` - `--universe eodhd-losers` in the value
  screener: the EODHD bulk US real-time feed (one call, ~18k rows,
  OpenD-independent) seeds a **loss-ordered** scan — the biggest intraday
  decliners by change% — so value-dip/momentum candidates (RSI/%b oversold,
  stop <= 2%) are harvested from today's actual dips instead of an alphabetical
  `eodhd-us` slice. New `get_top_movers_symbols_eodhd` (machine-readable
  symbol table behind `get_top_movers_eodhd`; `.US` suffix stripped, change_p
  kept as percent). `-n/--movers-count` sets the decliner count (moomoo movers
  cap at 200; eodhd-losers accepts up to the whole feed); `--price-min` gates
  on the feed's live close; mcap/PE/ATR gates still run per-symbol. The feed
  rows carry price + change only (no name/mcap/type), so ETF/ETN rows are not
  name-filtered at seed time. Tests:
  `test_eodhd_losers_universe_seeds_scan` +
  `test_get_top_movers_symbols_eodhd_sorts_strips_caps`. See CHANGELOG.
- 2026-08-30 `(working tree)` - Two-stage screener gating: every OHLCV-capable
  scan mode (`trend-pullback`/`breakout`/`momentum`/`swing`/`vcp`/`value-dip`)
  now runs a cheap OHLCV-only gate (Stage A, `_cheap_gate` — no provider call)
  before any fundamentals fetch, then memoized fundamentals for survivors
  (Stage B, `_fetch_fin_cached` + `_CASHFLOW_CACHE`), then provider enrichment
  only on finalists (Stage C). Non-candidates cost ~1 vendor call (OHLCV)
  instead of ~6-7 (statements + cashflow); a large `eodhd-us` slice is now
  tractable. `value`/`all` fall straight through. Tests:
  `test_cheap_gate_deferred_before_fundamentals` +
  `test_eodhd_cheap_gate_before_fundamentals`. See CHANGELOG.
- 2026-08-30 `(working tree)` - News/sentiment providers A-C: GDELT
  (`dataflows/gdelt.py`, keyless native tone + daily sentiment, new
  `get_gdelt_sentiment` news tool), NewsAPI.org (`dataflows/newsapi.py`,
  free 100 req/day global headlines, `NEWSAPI_API_KEY`), Benzinga
  (`dataflows/benzinga.py`, free ticker financial news, `BENZINGA_API_KEY`).
  NewsAPI in the default `news_data` chain; GDELT/Benzinga opt-in (GDELT
  endpoint is network-flaky). See CHANGELOG.
- 2026-08-30 `(working tree)` - Quant-formula calculations (quants.md +
  quant2.md implementation): volatility estimators (Parkinson/GK/EWMA/GARCH
  + `volatility_estimator` overlay switch), book tail decomposition
  (incremental/component VaR), mean-reversion quality (AR(1)/OU half-life
  with t-test gate), Roll effective-spread, preferred/fixed-income
  YTM/duration/DV01/convexity (capital_income `--fi`), credit
  hazard/default-probability, variance-swap strike, implementation
  shortfall (strategy_quality execution block). New market tools bound +
  web Value Tools 33->36. See CHANGELOG.
- 2026-08-30 `(working tree)` - News-sentiment factor (News_Sentiment.md
  implementation): EODHD `/sentiments` primary daily series +
  Alpha-Vantage/GDELT fallbacks (optional `news_sentiment` chain),
  `strategies/sentiment.py` series + `strategies/sentiment_research.py`
  (lead/lag, Newey-West regression, IC/decay, quintile LS), tools
  `get_news_sentiment_series` / `get_sentiment_lead_lag` (market + news
  nodes), `scripts/sentiment_factor_eval.py` + screener `--sentiment`
  (Sent7/SentZ), opt-in `enable_sentiment_factor` overlay fold. trading_web
  Value Tools + README. See CHANGELOG.
- 2026-08-30 `(working tree)` - Docs/reference sync + web mirror: the
  value-dip research plan's stale "ROC/TRIX/Force/A-D not implemented" note
  corrected (they shipped in `extended_indicators.py`), its phases marked
  DONE + open questions resolved; `docs/api_reference.md` §6.1 lists
  `get_extended_indicators` / `get_candlestick_patterns`, §6.2 `VENDOR_LIST`
  updated to 17 vendors; `docs/developer/12-data-providers.md` re-tallied
  (22 providers) with the cboe/federal_reserve/gdelt/benzinga/newsapi rows +
  corrected `news_data` chain; trading_web Value Tools gained
  extended-indicator/candlestick/GDELT-sentiment tools (trading_web commit
  `db3217d`). See CHANGELOG.
- 2026-08-30 `(working tree)` - Extended technical indicators
  (`strategies/extended_indicators.py`): Ichimoku, golden/death cross, CCI,
  ROC, momentum oscillator, TRIX, Force Index, A/D, VPT, CMF, anchored VWAP +
  a candlestick pattern scanner. Two new market tools `get_extended_indicators`
  + `get_candlestick_patterns` (market analyst prompt + ToolNode). Pure local
  calc, no vendor/quota. See CHANGELOG.
- 2026-08-30 `(working tree)` - New free-tier vendors: Twelve Data
  (`dataflows/twelve_data.py`, free 800 credits/day; time-series OHLCV + realtime
  quote + crypto) and StockData.org (`dataflows/stockdata.py`, free 100 req/day;
  EOD OHLCV + quote + news). Registered in `VENDOR_LIST` + `VENDOR_METHODS`
  (`get_stock_data`, `get_news`) as key-gated tails of `core_stock_apis` /
  `news_data`; market snapshot + crypto tools gain fallbacks. Keys:
  `TWELVEDATA_API_KEY` / `STOCKDATA_API_KEY` in `.env` (gitignored). See CHANGELOG.
- 2026-08-30 `(working tree)` - Option-A hybrid: independent pre-debate
  stances (`independent_vote.py`). With `enable_independent_vote`, the 3 risk
  + bull/bear roles each emit ONE structured stance BEFORE the debate (no
  transcript / no opponents' responses — the independence invariant), so G3
  agreement, the G1 contract multiply, and the PM's dissent flag come from
  conformity-free opinions; the debate stays the risk-surfacing layer. The PM
  + Research Manager prompts receive the independent vote/reads; the legacy
  parse-from-history path is unchanged when the flag is off. See CHANGELOG.
- 2026-08-29 `(working tree)` - Risk gate moved out of the analyst reports
  (now once in 4_risk + 5_portfolio decision); compact verdict.md no longer
  duplicates the PM decision; rebuild_complete_report gate recovery hardened
  + _readable_section idempotent. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - Interactive CLI always writes the verbose
  risk-debate files (aggressive/conservative/neutral.md) - an ambient
  TRADINGAGENTS_RISK_COMPACT_REPORT=true was producing a single verdict.md;
  `.env` reset to false + CLI forces verbose. Reports readability: new
  `reporting._readable_section` adds paragraph spacing + Round headings to the
  prose debate/trader reports (analyst-style readability), applied to
  research/trading/risk sections; re-render with rebuild_complete_report.py.
  See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - G2 calibration feedback loop wired:
  `calibration_ledger.jsonl` now stamped at resolve time (confidence parsed
  from the PM decision), `_calibrated_p` returns a real calibrated probability,
  and the calibration table is injected into the decision-context prompt.
  Fixed a `get_ratios` abs(None) crash (missing capex) that aborted the
  fundamentals tool node; corrected Strategies/*.md doc-misnomers found in the
  audit. See CHANGELOG [Unreleased].
- 2026-08-29 `(working tree)` - CLI one-input mode: `tradingagents analyze
  --symbol <TICKER>` runs with no other prompts (all 4 analysts, deep research,
  provider + models from TRADINGAGENTS_LLM_PROVIDER/_DEEP_THINK_LLM/
  _QUICK_THINK_LLM, report auto-saved to reports/, CWD-independent). Interactive
  flow unchanged. See CHANGELOG [Unreleased].
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