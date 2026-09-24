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
py -3.12 -m ruff check .   # the WHOLE repo - CI runs exactly this (`.github/workflows/ci.yml`)
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
- **The validation panel's fundamentals leg is SEC EDGAR XBRL** (owner decision
  2026-09-18), NOT EODHD's bulk endpoint. Why EODHD could not be bought into
  reach: Extended Fundamentals is priced **"By request"** on the vendor's own page
  and is excluded from every published tier, so spending more there could not
  clear the 403 — it is plan-gating, not spend-more. The SEC leg is one keyless
  `companyfacts` request per filer, fetched once and reused for every panel date
  (a 30-date panel over 464 names is 464 requests, not 13,920), paced to SEC's
  published 10 requests/second ceiling. Two properties are load-bearing and must
  not be "simplified": the read is **point-in-time** (only facts FILED on or
  before the panel date are eligible — otherwise a past panel reads the future
  and every measured IC is inflated), and every leg is aligned to **one fiscal
  year** (a tag with no value at the reference end is absent, never substituted
  from another year). `_meta.fundamentals_gaps` names every name the leg could
  not supply (no CIK, pre-XBRL, IFRS) with its reason — never dropped silently.
  Market cap is derived from the panel's own close × the EDGAR cover-page share
  count, because EDGAR carries no price.
- **The forward company-event calendars** (owner decision 2026-09-18):
  `dataflows/event_calendars.py`, gated by **`enable_event_calendars`** (default
  off, and deliberately **separate** from `enable_event_state` — this is the only
  part of the event state that leaves the machine). Three facts to keep:
  - **pdufa.bio** answers FDA/clinical (free, keyless) and makes that family
    `SCORABLE`. **Only rows with `date_precision == "day"` are used**: the source
    nulls `date` for every month/quarter/year estimate (its own 2026-09-09
    breaking change, because it used to serve a month midpoint as an announced
    day), and a day-count built on a month midpoint would be an invented number.
    Live 2026-09-18: 456 catalysts tracked, **120 carrying an announced day**.
    `calendar_coverage` prints `rows_held` beside `rows_with_announced_day` so an
    undated family reads as an absence of *dates*, not of catalysts.
  - **CourtListener cannot answer the court family.** It is a filing archive, not
    a forward calendar: its docket endpoints need a token and its anonymous
    `/search/` exposes only `dateArgued`/`dateFiled`/`dateTerminated`, all
    backward-looking (probed live: zero future-dated rows across three result
    sets of 144,748 / 4,563 / 61,937,018 matches). The family reports
    **`missing`**, never `not_applicable` — "this source cannot carry a forward
    date" is not the claim "no court event is scheduled", and only the second one
    would be a false assertion. `event_calendars.court_probe` keeps the finding
    re-verifiable.
  - **The investor-day family is DROPPED**, not unbuilt: no free source exists,
    and the one priced source (Wall Street Horizon via IBKR, $49/mo) was
    declined. The design permits it — the families are independent and coverage
    prints per family.
  - **`None` is never `[]`.** `None` means the question was not answered
    (`missing`); `[]` means it was answered and holds nothing
    (`not_applicable`). `event_state.calendar_answers` is the one place that
    turns adapter rows into the three-status answer, so the leaf and the run card
    cannot drift into collapsing them.

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

- 2026-09-23 `(working tree)` - **A deflated Sharpe is now deflated by a measured search.** H1 of the survey's adoption set, behind `enable_trial_ledger` (default off). `strategies/trial_ledger.py` (new) records one immutable row per evaluated candidate and reads `N` and the trials' Sharpe **variance** `V` back from those rows - never from a caller's assertion - reporting `unavailable` below two usable Sharpes. `evaluate.deflated_sharpe(sharpe_dispersion=...)` uses the closed form `sqrt(V)*[(1-g)*Phi^-1(1-1/N) + g*Phi^-1(1-1/(N*e))]` when the dispersion is supplied AND the gate is on, and is otherwise **bit-for-bit** the old `sqrt(2 ln N)` approximation; `deflated_sharpe_report` carries `N` beside the number and tags `measured` vs `assumed`. `alpha_zoo.bench_zoo(trial_ledger_dir=...)` records, reads back and publishes `deflated_ic_n_trials` / `deflated_ic_dispersion` without adding a key on the default path. Two card corrections: `V` is a variance (dimensional necessity - a caller passing a std must square it), and the card's `S = 8` instruction has no target in this tree (`evaluate.py` has no `S`; the knob is `purged_cpcv_splits(n, n_splits=5)`, pinned by an existing test, deliberately unchanged). Stated gap: `scripts/score_panel.py` still passes its own `n_trials` - that site's switch to the ledger is a follow-up. `gate_on` now reads its literal key, because a gate read through a `GATE_NAME` constant is a gate the registry's read-site scan cannot see (it read as "wired but nothing reads it"). Failing-first: `test_trial_ledger.py::test_dispersion_changes_deflated_sharpe` fails by name when the dispersion branch is made unreachable, source restored byte-identical.

- 2026-09-23 `(working tree)` - **The survey's adoption set landed its first three items: a coverage window (H10), a cross-strike skew proxy (K3), and a trend-spectral read beside the swing factor (X8).** All additive, all default off. `strategies/coverage_window.py` (new) reads the window of the already-loaded frame as a **reader**, never a second data-quality authority (`_INDICATOR_MIN_BARS` and `_IGARCH_AB` are untouched), and `data_quality.panel_statistic` reports the statistic `unavailable` over a padded one while keeping the dense result byte-identical; `coverage_scorecard.py` gains a per-symbol section off each tree's own `tool_evidence.json` - the plan had assumed that script had a per-symbol view and it reports per-engine fill rates. `options_surface.rn_skew_proxy` needs five OTM strikes, returns `unavailable` below that, names itself a **cross-strike IV proxy** (never a BKM moment) and carries its regime cell; its only read site is `get_vol_surface_shape`, and the plan's named risk_score site is deliberately NOT wired because scoring a regime-conditional read is the owner's decision. `technical_factors.spectral_excess_mass` / `cost_optimal_span` are reported BESIDE the swing factor - one additive `trend_spectral` key when the gate is on, the same 12 keys as before when it is off, verdict unchanged (asserted). H10's first cut never read its own gate and the registry test caught it ("claimed wired but nothing reads it"); both callers now read it through `get_config()`. Failing-first proofs re-run by the integrator against the final source, each restored byte-identical: `test_coverage_window.py::test_padded_panel_is_unavailable`, `test_rn_skew_proxy.py::test_proxy_unavailable_below_five_strikes`, `test_strategies_technical_factors.py::test_cost_optimal_span_is_monotone_in_cost`.

- 2026-09-23 `(working tree)` - **The survey's adoption plan became six per-theme plans, one in the folder beside each design doc.** `docs/paper_survey_26/` now holds the six themed design docs, six implementation plans (one per theme) and a `README.md` that owns what is shared - the eight ground rules, the measured dependency surface, the cross-theme phase map, the hard ordering constraints, the in-run-versus-offline split and the landing protocol. The single combined plan (`docs/implementation_plan_paper_survey_26.md`) is deleted; item content is unchanged (49 items, 34 gates plus one extension, P0 first, nothing entering `COMPOSITE_ENGINES`). The move repaired one defect: the survey's plan cross-link had been inserted into the middle of its `**Method:**` paragraph, splitting the sentence.
- 2026-09-23 `(working tree)` - **The corpus survey's adoption plan was written, and grounding it found an undeclared dependency.** That plan (since split into the six per-theme plans above) phases the six themed docs into P0-P4 with a gate, a failing-first test and acceptance criteria per item, and all 44 anchors it reuses were re-verified in the tree. Measured rather than assumed: **sklearn is absent** (X2, X5 and V1 need it or a hand-rolled equivalent), **torch is installed but undeclared and imported nowhere**, and `tsbootstrap` is a real public library. Separately fixed: **numpy and scipy were undeclared** while `strategies/statistical.py:18` imports scipy directly - every scipy edge from a declared dependency is extras-gated, so a clean install resolved none. Both manifests now declare `numpy>=1.26.0` and `scipy>=1.11.2`.
- 2026-09-23 `(working tree)` - **The interactive CLI and the batch path stopped producing different reports.** They differed because `cli/main.py` builds its own state and streams the raw compiled graph instead of calling `propagate()`, so it had re-implemented the graph's setup by hand - and the copy had drifted: it seeded `risk_context` but never `quant_scorecard` (every interactive run's four analyst reports and `run_card.json` lacked the engine sections the batch path renders), it passed no `past_context`, and it stopped after the overlays so it wrote no state log, ledger row or memory entry. **Both paths now call `TradingAgentsGraph.prepare_initial_state(...)` and `.finalize_run(...)`** - one producer per step, no second copy left to drift; `_log_state` also takes the ticker explicitly, because `self.ticker` was only ever set by `propagate()`. Differences that REMAIN and are NOT defects: the CLI picks its own models/provider where batch reads `.env` (so `config_hash` and the prose differ), batch's `--depth` defaults to `deep` while the picker starts on Shallow, batch writes `jev_verdict.json`/`verify_flags.json`, and the memory log is split - batch writes `memory/<TICKER>.md` (deliberate: parallel workers must not interleave appends) while the CLI writes `memory/trading_memory.md`, so the two still cannot see each other's history. That last one is a real gap and the owner's call. See `tests/test_cli_propagate_parity.py`.
- 2026-09-23 `(working tree)` - **The 2026 arXiv corpus was read end to end and wrote seven docs.** 309 papers in `e:\fin paper` with a `26*` id, each given a recorded verdict (31 high / 111 medium / 124 low / 43 none) and routed to an engine surface or to `none`. Start at `docs/design_fin_paper_survey_26.md` - it carries the theme synthesis and all 309 by verdict - then the six themed docs it points to (`research_honesty_gates`, `regime_estimation_hardening`, `risk_tail_and_coverage`, `vol_surface_and_vrp`, `cross_section_and_allocation`, `news_and_filing_signals`). Three things worth knowing before proposing anything from a paper: the corpus's biggest theme is honest *evaluation*, not alpha; the repeatedly-confirmed finding is that volatility/structure is forecastable and the return level is not; and the survey itself was wrong once - it routed a paper to `cross_section` whose estimators (`liquidity_risk.amihud_illiquidity:71`, `kyle_lambda:262`) already exist. Every proposal in those docs is unbuilt and untested against this engine; none is a gate and none enters `COMPOSITE_ENGINES` by adjacency.
- 2026-09-23 `(working tree)` - **Max pain scored + two gates on.** `derivatives_gamma.max_pain(rows)` = `argmin_S[sum(max(S-K,0)*call_OI) + sum(max(K-S,0)*put_OI)]` over listed strikes, `None` below two OI-carrying strikes; duplicate rows ADD (tested - overwriting would halve a strike's weight). Monthly expiry via `_options_chain_rows_lambda(monthly=True)`, selecting the third Friday from `opex_dates` rather than the third listed expiry. **Scored as `max_pain_dist_atr`** in `price_structure`, `lower_better`, ramp 0-2 ATRs - **which changes the composition** (4 -> 5 components in the family, so the 12 points now split five ways). **The one component that fetches:** its docstring claimed "no new fetch"; the monthly chain is not in the OHLCV cache, so the docstring names the exception, the fetch is best-effort, and absence beats a fabricated 0 (live call: 39 components, `max_pain_dist_atr=1.1467`, 92 s). **Gates turned on in `.env`** (gitignored, recorded here because the behaviour is not): `enable_security_context` (the SC card block, built earlier today and so far producing nothing) and `enable_options_surface` (**web impact additive: the app's registered `options_iv_read` becomes functional**). Tests: 3 new (no score test - `test_monotone_ramps_are_ordered` already covers every ramp); full suite 5341 passed, 6 skipped, 0 failed (the previous run 5341 passed + 1 failed, now green).; `ruff` clean.
- 2026-09-23 `(working tree)` - **Three standard-instrumentation gaps closed.** `pivot_points` returned P/R1/S1/R2/S2 while its docstring claimed the classic set - now returns **R3/S3** too (R3 = H + 2(P-L), S3 = L - 2(H-P)), so the name matches the function; pivots are rendered, not a score input, so no score moved. `fib_levels` now returns the standard retracement set with **0.236 and 0.786** added (0.786 = sqrt(0.618)) - and **a correction: widening the set does NOT widen `fib_zone`**, which reads 0.382/0.618 only; the earlier caution that it would move a score was wrong. New **`technical_factors.pivot_distance_atr`** = `(close - pivot)/ATR`, the stationary form (a dollar gap is not comparable across names; in ATRs it is), surfaced by `get_technical_factors`, returning **None for a non-positive ATR, never 0.0**. **The invariant nearly broken:** `fib_levels` has four return paths and `pivot_points` three, and adding keys to only some is a KeyError waiting for the right input - a partial edit did exactly that mid-change, so both now have a test that every degenerate path returns the same key set as the live path. Web impact additive only (the app renders the string; the new r3/s3 and pivot-distance line). Tests: 4 new; full suite 5339 passed, 6 skipped, 0 failed (baseline 5335 + the 4 new tests).; `ruff` clean.
- 2026-09-23 `(working tree)` - **The four analyst reports stopped carrying a vote.** Each analyst prompt asked for a `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` prefix "so the team knows to stop", and reports often opened and closed with one. **Nothing consumed it** - an exhaustive grep across all three repos found no parser, counter, schema field, gate or card key on the analyst side, and no reference at all in `trading_web` or `TradingExecution`. **The trader's line is a different object and stays:** `schemas.render_trader_proposal` renders it from the validated `TraderProposal.action` enum, so it is generated, never inherited; `report_verifier`'s conflicting-verdict scan reads that text and also stays. Removed: the two-line instruction in the four analyst prompts and the `report_hygiene.py` clause naming the line. **Unchanged:** the stub guard keys on length/degeneracy (`_REPORT_STUB_MIN_CHARS = 400`), never on the vote, so its bare-verdict fixtures still describe a real shape. Existing trees keep their votes - this is future runs only. **Accepted trade-off:** the instruction was also the analysts' only explicit stop affordance; the tool loop's caps are code, so termination does not depend on it, but a longer monologue is the plausible cost. **v2:** the same day, the stop affordance came back vote-free as one line per prompt ("When your report is complete, deliver it in full and stop."), placed above the `#1130` comment in sentiment so it reads as completion, not tool guidance. Tests: full suite 5335 passed, 6 skipped, 0 failed (unchanged - nothing consumed the vote).; `ruff` clean.
- 2026-09-22 `(working tree)` - **The classification layer gained its cross-run ledger.** `scripts/security_context_ledger.py` reads the `security_context` blocks the runs already wrote and counts **what was classified, and how** - canonical-sector and source distributions, the unclassified rate, SIC presence, per-theme trigger/promotion counts, and the matrix/trigger versions in the wild. One run classifies one company; drift is only visible across runs, and the classification is deterministic and versioned, so it is checkable. **Three distinctions it refuses to blur** (the ledger's whole risk is claiming more than it can see): a tree with **no block** is not evidence the gate was off (it may predate the gate) and the note says so; an **unreadable card** is a card problem, counted apart from "no block"; an empty sector on a *present* block **is** an unclassified company. **Trees are ordered by mtime, not name** - names are `TICKER_YYYYMMDD_HHMMSS`, so a name sort would make `--limit` sample the alphabet; that was a real bug caught by the `--limit` test. Read-only, and carries no score, rating or verdict. Run live: `trees: 5, with block: 0` - correct, every tree predates the gate. Tests: 9 new; full suite 5335 passed, 6 skipped, 0 failed (+9, exactly the new tests).; `ruff check .` clean.
- 2026-09-22 `(working tree)` - **The `LOW` line stopped being circular: a cheap trigger scan promotes a deprioritised theme.** The priority matrix orders effort and can only *add* attention, so a `LOW` theme is evaluated last - which left §11.3 asserting an escalation (*"LOW -> evaluate only if the evidence stage raises it"*) with **no producer**, since with a fixed budget nothing would read the evidence that should raise it. `strategies/theme_triggers.py` scans text the run **already holds** (its own analyst reports - no fetch, no LLM) for a declared lexicon per registered theme and names the hit themes the prior had put last. **Additive by construction:** it can only move a theme earlier, never later, and cannot change the candidate set - so the widening invariant survives a trigger. **Matching is word-bounded and that is load-bearing:** a substring match fires `ai` on *said*, *airline*, *chain*, *retail*, *campaign*, and a test pins exactly those decoys. Nothing consumes a promotion as a decision yet (the overlay framework does not exist), so it is recorded in the card block only. Tests: 11 new; full suite 5326 passed, 6 skipped, 0 failed (+11, exactly the new tests).; `ruff check .` clean.
- 2026-09-22 `(working tree)` - **The classification front end the overlay layer was missing, and the prior it prints cannot gate.** `docs/Conditional_Research_Overlays_Design.md`'s Overlay Detector has three sub-steps, and the third - the `applicability test` (`doc:265`) - **had no producer anywhere in that doc**. `tradingagents/strategies/security_context.py` is it, behind `enable_security_context` (default off). `candidate_themes()` is a **union**, so every registered theme stays a candidate for every company and the priority matrix orders evidence-gathering effort without ever removing a theme - property-tested over all eleven sectors, an unclassified company and an unknown label. Provenance travels with every value (the repo has four taxonomies under one "GICS" string and discarded the source), and no field is named GICS. **Three decisions taken explicitly:** the cross-source `agreement` enum is **deleted** because one reachable sector read made it unreachable and a state that cannot occur reads as a check that ran and passed; the matrix is renamed `THEME_PRIORITY_MATRIX` because "applicability" implies the exclusion the invariant forbids; and the industry bridge is `industry_implied_sector` because it maps an industry to a *sector*. No network call of its own - the SEC SIC comes from the payload `get_sec_filings` already fetched and discarded (new `sec_edgar.peek_sic`, which never fetches, so `None` means "not read"). The 66-cell matrix is declared policy awaiting the owner's review. **Two defects found while building, both fixed:** `classify_security` advertised an `operating_company` state it could not return (its docstring, `api_reference.md:1054`, `design_etf_fundamental_valuation.md:233` and the P0-9 criterion all agreed, the code did not) - fixed at the PRODUCER, since a provider `EQUITY` quote_type is positive evidence and every consumer branches only on `== "ETF"`, so nothing downstream moves; and `gate_registry.md` §8's gate-registration rule said FIVE places when there are SIX (the `api_reference.md` §1.1 env table is machine-checked, so a gate missing from it fails the suite) - both the rule and the table are corrected. Tests: 24 new; full suite 5315 passed, 6 skipped, 0 failed; `ruff check .` clean.
- 2026-09-22 `(working tree)` - **The gate registry's scope paragraph named 8 of the 48 keys it omits.** Stage 1 narrowed the title away from "every gate" and named the eight score-engine gates as covered elsewhere - but **48 `enable_*` keys have no row** and the paragraph named only those eight, so `enable_reflection`, `enable_debate`, `enable_independent_vote`, `enable_events`, `enable_factor_model` and `enable_screener` still read as "no such gate" to anyone trusting the absence of a row. The title now says **registered**, and the paragraph states **40 of the 88** covered / **48 with no row**, lists every omitted key in six families, and adds the sentence that makes the omission safe to read: a missing row means *not registered yet*, never "no such gate". A new test recomputes both numbers from `DEFAULT_CONFIG` and `REGISTRY` and fails if any omitted key goes unnamed, so stage 2 cannot add a family and leave the doc behind. No row added. Tests: 1 new; full suite 5292 passed, 6 skipped, 0 failed (5291 before, +1).; `ruff check .` clean.
- 2026-09-22 `(working tree)` - **Four reported defects fixed - and the report itself was WRONG about one of them.** The four behavioural defects the security-context design reported for a
  decision (`docs/design_security_context.md` §20.2) are fixed on the owner's instruction, each with a failing-first proof. **R1** `finnhub.get_profile_finnhub` no longer renames the vendor's field:
  it copied `finnhubIndustry` onto a key named `sector` so its one caller could read `prof["sector"]`, which made a key named *sector* hold an *industry* value and hid the taxonomy from its consumer -
  while the function's own docstring promised the "raw" profile dict. It returns the payload unmodified now (`finnhub.py:468`, comment at `:482-493`) and `fetch_sector` does the mapping
  (`yfinance_sector.py:112`) with the OLD precedence preserved (`prof.get("sector") or prof.get("finnhubIndustry")`), so **behaviour is unchanged for real payloads**. **R2** the `industrygroup`
  alias at `statement_parsing.py:187` is DELETED - and the earlier "dead alias" claim was wrong: `_norm` keeps the space in "Industry Group", so the SPACED label never matched, but an UNSEPARATED
  `IndustryGroup` label DID, which the failing-first test caught. The consequence is real: `fin["sector"]` is the Altman variant selector (`:1565`) and feeds the Piotroski basis, and
  `altman_variant_for` routes it through `sector_group_of`, where a stray financial group resolves to `XLF` and **withholds the variant** for a non-financial company. **R3** naming only -
  `industry_neutral_z`'s parameter is `group_map` (`cross_section.py:90`), both docstrings state the grouping is the caller's (a provider sector label, neither GICS nor an industry group), and
  `resolve_growth_medians:304` says peer-group medians now; the FUNCTION name is unchanged (standard Grinold-Kahn term; renaming it is a 4-site public change for a cosmetic gain) and both callers
  pass positionally, so no caller changed. **R4 stage 1** `docs/gate_registry.md` no longer titles itself "every gate" over 40 of the 88 `enable_*` keys: the title names the three families it covers
  and a new paragraph names where the eight score-engine gates ARE covered (`tests/test_quant_scorecard.py`, `tests/test_engine_ownership_map.py`); the 48 rows are deliberately NOT bulk-added, since
  an unverified "Proven by" cell is the failure mode the file exists to prevent. Tests: 8 new - 6 of them failing-first, 2 pinning behaviour the change had to preserve; full suite 5291 passed (5283 before, +8), 6 skipped, 0 failed; `ruff check .` clean.
- 2026-09-22 `(working tree)` - **Design: the overlay layer's missing front end, and the taxonomy the repo mislabels as GICS.**
  `docs/Conditional_Research_Overlays_Design.md`'s Overlay Detector has three sub-steps (`doc:263-265`): materiality test, evidence sufficiency, **applicability test**.
  **The third has no producer anywhere in that doc** - "applicability" is named once and never defined, no step reads any property of the company, the registry is keyed
  only on theme id (`doc:782-789`), and §36's ten open decisions do not include "which overlays are candidates for a given company". §17 (`doc:725-772`) is NOT that step:
  its four sector headings all sit under the same theme and enumerate *evidence fields for an already-chosen theme* ("the schema remains the same while the evidence
  adapters differ", `doc:772`). **NEW `docs/design_security_context.md`** supplies the producer: a deterministic `SecurityContext` (sector + industry + provenance +
  canonical sector + SPDR key + SEC SIC + security type), a versioned theme applicability matrix, and the three-way split into Classification / Candidate / Materiality.
  **THE KEY IDEA - the widening invariant:** the matrix may **add** candidates and may **never remove** one (`candidates = ALL_REGISTERED_THEMES | matrix_candidates(sector)`).
  The brief's own example is why: a company in **Energy** whose AI exposure is material anyway (data-centre electricity demand) would be silently missed by a prior that
  can exclude. **A prior that can exclude is not a prior, it is a decision.** Monotonicity makes "sector is a prior, not the final decision" a property-tested guarantee
  rather than a discipline, and the matrix's real job becomes ORDERING evidence effort under `MAX_ACTIVE_OVERLAYS = 3`. Absence is not exclusion - an unclassified company
  yields ALL themes. **DEFECT - four taxonomies labelled one "GICS":** `fetch_sector` (`yfinance_sector.py:64`) was documented as "GICS sector" but its four legs return
  FMP's taxonomy, Finnhub's **proprietary** `finnhubIndustry`, Yahoo's label (which the repo's OWN comment at `sector_rank.py:91` calls **sub-industry granularity**), or
  the repo's ETF issuer label - and **the answering source is discarded**. GICS is licensed by MSCI/S&P and assigned at company level; the repo has no GICS source, no GICS
  code, and no SIC or NAICS anywhere. Three documentation-only claims corrected (zero behaviour change): the module docstring, the `fetch_sector` docstring (which also
  omitted the Finnhub leg), and the `finnhub.py:482` comment claiming `finnhubIndustry` is GICS. **Reported, NOT changed (behavioural) - [CLOSED 2026-09-22: all four fixed, see the newest entry].** `finnhub.py:487-488` fills the key
  named `sector` from a field named *Industry* while the payload's real `industry` goes unread - **WRONG on the second half: live-probed 2026-09-22, `company_profile2` carries no
  `sector` key and no `industry` key at all, so the old rename was the only source of `sector`**; `statement_parsing.py:187` lets the canonical `sector` key accept an
  `industrygroup` value (a DEAD alias - no payload emits that row - but a latent trap, and `fin["sector"]` selects the Altman variant at `:1565`); and
  `cross_section.industry_neutral_z:89` takes `sector_map` while `peer_universe.resolve_growth_medians:304` computes "Industry medians" by partitioning on a SECTOR label.
  **Also reported:** `docs/gate_registry.md` titles itself "every gate" and §8 (`:229`) requires a row for every gate, yet **48 of the 88 `enable_*` keys in `DEFAULT_CONFIG`
  have no row** - including all eight score-engine gates and `enable_quant_scorecard`. The doc and `REGISTRY` agree with each other (40 rows), so nothing is inconsistent;
  coverage is 45% of the `enable_*` surface. Not changed: 48 judgement-heavy evidence rows, and an unverified row is worse than a missing one in a doc whose purpose is to
  stop gates that cannot fire. Tests: comment-only code change; full suite green; 357 passed across the seven touched-module files; `ruff check .` clean.

- 2026-09-22 `(working tree)` - **Four declared fields are now MEASURED, and the wiring exposed that FIVE of the sixteen gaps are DECLARATION defects rather than wiring gaps.**
  The coverage scorecard named sixteen fields whose declared producer is never reached. Wiring four of them showed that in five cases the DECLARATION is wrong:
  the named producer **cannot emit the declared quantity at all** - the same class as `ad_ratio` and the breadth legs, now five instances in one engine family.
  **Tier 1 (`risk_score`, the only tier inside `TradeScore` at 0.20):** **`gap_atr`** - `pre_market.premarket_gap` over the run's own last two bars
  (`closes[-2]` -> `opens[-1]`) with `size.atr`; `_risk_components` never touched either gap leg. **`through_stop` is deliberately NOT read from that call** -
  `premarket_gap` answers `False` when handed no prior stop/entry, which would report "the gap did not trade through the stop" when the truth is that no prior
  plan was ever in hand (those levels live behind `pre_market.load_prior_state` / `parse_planned_levels`, which nothing under `tradingagents/` holds).
  **`implied_move_pct` - THE UNITS TRAP:** `options_surface.implied_move_pct` returns **PERCENT** (docstring "(%)", multiplies by 100.0) while `risk_score`
  declares a **FRACTION** with ramp `(0.01, 0.10)`, so a naive wiring delivers a 1-sigma 7% move as 7.17 and **saturates the ramp** - a confident wrong number
  with no error anywhere. The seam divides by 100.0 and a test pins the result INSIDE the declared ramp. No new fetch and no gate flip:
  `_options_chain_rows_lambda` is the builder the gamma/derivatives leaves already read.
  **Tier 2 (advisory - `sentiment_score` and `news_score` are OUTSIDE `COMPOSITE_ENGINES`):** `mention_heat` and `persistence` both read `sentiment.mention_volume`,
  which takes a per-day mention COUNT history - a series that **already existed**: `daily_sentiment_sma` returns `n` per calendar day (0 on a day with no articles).
  `_sentiment_components` held the rows and never read `n`; `_news_components` carried a comment claiming the series did not exist. **It does.** The news leg sits
  OUTSIDE its `if articles:` block on purpose - mentions and headlines are different feeds, so an empty headline window must not withhold an attention leg.
  **DEFECT (rule 15, BEHAVIOUR-PRESERVING):** `aggregate_weighted_sentiment` re-derived the freshness weight inline instead of calling `decayed_weight`; the two agreed
  ONLY because the caller clamps `age_days >= 0`, so the copy inherited the `age_days < 0 -> 0.0` guard by accident. **This one has no behavioural test and cannot
  have one** - the mutation that reverts it leaves the suite GREEN, which is the evidence it is a dedup, not a fix.
  **THE DECLARATION DEFECTS (reported, NOT built):** `sector_max_share` <- `enforce_sector_exposure:169` returns the adjusted weight **DICT** (`:196`), not a scalar;
  `short_pct_float` <- `get_short_interest_yfinance:37` returns a **markdown STRING** (`:95`) - and that producer is **NOT dead**, it is dispatched through
  `interface.VENDOR_METHODS['get_short_interest']:591`, which an AST call scan cannot see, so the scorecard's `unwired` means "no DIRECT call site", not "dead";
  `iv_percentile` needs a per-day IV history no producer can supply; `guidance_change`/`industry_shock` are BUILDABLE (Benzinga already parses numeric guidance
  min/max/prior before discarding them into prose; the 11 SPDR series are already fetched by `get_sector_rank`); `fundamental_impact` and the cheap `regulatory_legal`
  are REFUSALS. **`scripts/coverage_scorecard.py` now prints WHY every field is empty** - authored reason first, then the engine's OWN `ABSENT_REASONS` (so the report
  and the engine cannot drift), then a class default; `--actionable` prints it inline. Rule 4 checked: `trading_web` holds ZERO references to any field touched here.

- 2026-09-22 `(working tree)` - **Market-wide breadth is now MEASURED: P0-3's producer had zero callers, and `ad_ratio` had no producer at all.**
  `strategies/market_breadth.py` (P0-3) was fully implemented with seven tests and both consumers declared it in their component tables -
  `technical_score`'s `pct_above_50d` / `pct_above_200d` / `ad_ratio` and `regime_score`'s `breadth` - while **nothing in the live path ever called it**.
  Every run, every symbol, those four fields were declared and absent. `regime_score`'s own table recorded the caller it did not have
  ("prerequisite 2 (P0-3); the leaf passes pct_above_50d") and both assemblers carried a comment explaining the missing panel.
  **The panel (P0-2): NEW `dataflows/market_panel.py::market_closes(fetch_closes, *, universe=None, limit=None)`** builds the
  `{name: closes}` map `market_breadth` takes, over the full S&P 500 (`sp500_universe`, disk-cached weekly), and caches it for the
  process - the owner chose the full universe over a sample, **fetched once per run**. The fetcher is INJECTED, not imported: the run's
  OHLCV cache lives in `agents/utils/analysis_tools` and a `dataflows` module must not import from `agents`. Every series comes from that
  same `_ohlcv` cache, so the panel cannot describe a different price basis than the rest of the run, and a name whose fetch failed stays
  in the map with an empty series so `market_breadth`'s `coverage` reports it instead of dropping it from the denominator.
  **One read, five consumers:** `analysis_tools._market_breadth_read()` assembles the panel once per process and is read by BOTH assemblers
  (`_technical_components`, `_regime_components`), so the two agent tools and the run card share one panel. `_clear_ohlcv_cache` now clears
  the breadth read and the panel too.
  **DEFECT found while wiring - `ad_ratio` had no producer.** `technical_score` declares `ad_ratio` with `market_breadth` as producer and a
  `(-0.30, 0.30)` ramp, but the module returned only `advance_decline` (a difference), never a ratio - so even with the panel wired that leg
  could not be measured. The ratio is now emitted by the one module that already computes numerator and denominator (rule 15), withheld on a
  small sample like the percentages. Nothing else produced `ad_ratio`, so this is the single producer, not a second one.
  **Absent stays absent:** a panel below `min_n`, an unavailable universe, or a failing read leaves the components OUT of the denominator
  rather than scoring a zero.
  Verification: `tests/test_market_panel.py` (14) + `tests/test_strategies_market_breadth.py` +2 (engine suite 5252 -> 5268, 0 failed), five mutations RED with byte-identical
  sha256 restores. Web impact: none.

- 2026-09-22 `(working tree)` - **A field-level coverage scorecard, and the twelve producers it found that nothing calls.**
  Coverage measured near-identical across four unrelated symbols (`technical_score` 0.95 four times, `regime_score` 0.83
  four times, `news_score` 0.25 four times), which says the gaps are a property of the PIPELINE, not of the stock. Nothing
  read the per-field picture across runs, so a field that is never populated looked identical to one populated on most runs.
  **NEW: `scripts/coverage_scorecard.py`** - reads every `run_card.json` under a reports dir and asks one question per
  declared field: was it measured, and if not, why not? The declared universe comes from `score_panel.engine_registry()`
  (the one place each engine's own component table is read - no second vocabulary). The denominator is the trees where the
  engine was actually MEASURED, so a gated-off engine cannot drag a field's fill rate down.
  **The classification is the point.** A zero fill rate is one of three things and only one is a defect here: `unbuilt`
  (the declared producer is empty), `unwired` (a producer is named and nothing outside its own module calls it), or
  `structural` (the producer is reached and this run supplied no value). Fill rate alone cannot separate them; the declared
  producer string plus an AST call-site scan can. **The scan resolves import aliases** - the live path renames producers on
  import (`analysis_tools.get_liquidation_days` does `from ...liquidity_risk import days_to_absorb as _dta` then `_dta(...)`),
  and reading only the call node's own name reported five live producers as never called. That was a false defect the scan
  produced itself, caught before shipping. A producer string that names no callable, resolves to no file, or names a
  function its file does not define returns "cannot tell" rather than a false `unwired`.
  **FOUND on the 68 trees - twelve fields whose declared producer is never reached from the live path.** The largest family
  is `strategies/market_breadth.py::market_breadth` at **four fields across two engines**: `technical_score`
  `pct_above_50d` / `pct_above_200d` / `ad_ratio`, and `regime_score` `breadth`. That module is fully implemented and has
  7 tests, and it has **zero production callers** - `regime_score`'s own component table even records the caller it does
  not have ("prerequisite 2 (P0-3); the leaf passes pct_above_50d"), and `analysis_tools:5299` states the reason
  ("market-wide breadth needs a panel this call does not fetch"). `[CLOSED 2026-09-22: both were wired the same day - see the market-breadth wiring entry above.]` Also: `sentiment.mention_volume` (2 fields),
  `pre_market.premarket_gap` (2), `options_surface.implied_move_pct` / `iv_percentile`,
  `portfolio_optimizer.enforce_sector_exposure`, `yfinance_short_interest.get_short_interest_yfinance`. Four further
  `news_score` components declare no producer at all.
  **Presence is read from explicit lists, never from a value** - a measured `0.0` is a measurement, not a gap (`adx: 0.0`
  is present). Each engine publishes presence differently (`technical_score` category `components`, `risk_score` category
  `present`, `fundamental_score` subscore `coverage.metrics`, `regime_score` engine `components`, and for
  `sentiment_score`/`news_score` the complement of `absent`, which those engines define as the complement of what they
  measured); each shape is read as itself, not unified. A field the card says nothing about leaves the denominator.
  **Not a defect, checked:** `risk_score`'s `liquidity` reports 2/3 not 4/5 because `risk_score.category_score:486` scores
  over `SCORED` components only and leaves the `PRINTED` ones out; and the registry's declared set is a superset of the
  live engine's for `fundamental_score` (28 declared against 25 counted), which is why an engine whose declaration carries
  no producer column is reported as "cannot tell" rather than `unbuilt`.
  Verification: `tests/test_coverage_scorecard.py` (25), four mutations RED with byte-identical sha256 restores. Web
  impact: none - a new `scripts/` entry point, no tool, CLI flag or JSON shape the app consumes changed.

- 2026-09-22 `(working tree)` - **The web app is synced with the 49 engine commits that landed after its last one** (trading_web commit `83345c6`).
  The app's HEAD was 2026-09-18 21:53:59 -0500, which lines up with engine `4acc555` (21 s earlier); 49 engine commits
  landed after that. Rule 4 ("every TradingAgents change reflects in trading_web") is now discharged for the window:
  **6 new tools** (`get_cross_section_momentum` + the five Benzinga event readers - `VALUE_TOOL_SPECS` + the dispatch
  map + `valueTools.js` + a regenerated `docs/web_TOPICS.md`; 56 -> 62 declared, 9 -> 10 themes), **4 screener flags**
  (`--rates`, plus `--revision-index` / `--growth-scores` / `--quality-score`, which shipped 2026-09-13 and had never
  been wired), **the report viewer renders JSON at all now** (it globbed `*.md` only, so `run_card.json`,
  `research_decision.json`, `jev_verdict.json`, `verify_flags.json` and `tool_evidence.json` were all invisible;
  each artefact now carries its byte size and a `truncated` flag - a real `tool_evidence.json` is ~350 KB), and the
  two new entry points joined the Raw allowlist (`jev_decide.py`, `gen_api_reference_table.py`; 22 -> 24).
  **Two defects fell out.** (1) `read_report_tree` built its keys with `str(Path.relative_to(...))`, which is
  backslash-separated on Windows, while `ReportView` auto-opens on `k == "5_portfolio/decision.md"` and HelpGuide
  documents that same POSIX key - so the final decision, the grade and the position size, was NEVER auto-opened on
  this platform; the producer now emits `as_posix()`. (2) The app's README claimed the DSA advisory gates were
  "visible read-only on the Config screen" - false from the commit that wrote it (`af57ea1`): that screen is a
  curated security allowlist (`main.py:CONFIG_ALLOWED_KEYS`, 25 keys) covering 4 of this repo's **88** `enable_*`
  gates. `[SUPERSEDED 2026-09-22: the owner chose to expose them - see the v2 bullet below.]`
  Verification: app suite 149 -> 152, frontend vitest 49, live-checked in a browser (artefacts render with sizes,
  `5_portfolio/decision.md` opens, "62 tools in 10 themes", all four screener toggles bind), three failing-first
  mutations with byte-identical restores. **This repo is unchanged by the sync** - no engine symbol, CLI flag, gate
  or JSON shape moved.
  **v2 (2026-09-22):** the owner chose **expose all 88 `enable_*` gates**, so the allowlist is no longer
  hand-listed on the gate side. `main.py:allowed_config_keys` now returns `CONFIG_ALLOWED_KEYS | {every enable_*
  boolean in DEFAULT_CONFIG}` - 109 keys, derived at request time, so a gate the engine adds appears on the Config
  screen on its own. The curated 25 still guard the keys they exist for (`project_dir` / `results_dir` /
  `data_cache_dir` / `memory_log_path` / `moomoo_account` all stay out), and the derivation is safe precisely
  because every gate is a boolean - it cannot carry a path or an account the way the W-P2-5 denylist predecessors
  did. The app's README Config + DSA rows now state the true shape instead of my earlier "not visible" correction.
  `test_config_returns_no_paths_and_no_secret_values` (which pinned the bare constant) was updated to the derived
  contract, and a new test asserts the ENDPOINT carries every engine gate while no path key leaks - both directions,
  with the wiring and the helper mutated separately to prove each fails. App suite 152 -> 153; live-verified: 107
  rows rendered, 88 of them gates, zero leaked keys. trading_web commit `c010147`.

- 2026-09-22 `(working tree)` - **Cross-sectional momentum is now an advisory READ, and building it found two defects - one of which could hand back an all-long book as "dollar+beta neutral".**
  The pasted strategy brief's top pick ("cross-sectional momentum with factor neutralization") was ~70% ALREADY IN THE REPO as pure functions with no production caller:
  `cross_section.neutralize_book:233` (dollar+beta+sector orthogonal projection), `quantile_split:165`, `centered_rank:136`, `factors.vol_adjusted_momentum:46`, `book_risk.net_beta:177`. What was missing was the composition, the panel and the wiring.
  **NEW: `cross_section.momentum_book`** - composes those primitives (never re-derives one, rule 15), splits the top/bottom quintiles, equal-weights the legs, neutralizes them
  **within the selected legs** (projecting over the whole panel spreads the orthogonal adjustment onto UNSELECTED names, so the book quietly holds the middle), and reports net beta
  BEFORE -> AFTER so the gate's effect is measured. Advisory: not an engine, not a gate, not in `TradeScore` (rule 17), and NOT market breadth - the panel size travels with the read.
  `None` below 8 scored names. **NEW tool `get_cross_section_momentum`** (market analyst): bounded panel (caller names, or ticker + vendor peers), closes from the run's `_ohlcv` cache,
  betas **date-aligned** to the benchmark (`residualize_returns` truncates to common LENGTH, which pairs different sessions when a name has a gap - so an unalignable name gets NO beta
  and `net_beta` reports the book beta as unknown rather than summing a partial). Live-verified: 8-name panel, net beta **+1.6258 -> +0.0000**, only the 4 selected legs held.
  **DEFECT 1 (`neutralize_book`): float residue amplified into a book.** The projection is CORRECT - an equal-weighted leg set with one beta per leg lies entirely in the constraint space,
  so it leaves `~1e-16`. But the guard tested `gross <= 0`, which residue never satisfies, so `gross_target / 1e-15` **renormalized the noise into a fully-invested book with a plausible gross
  of 1.0** (observed `{0.25, 0.25, 0.25, 0.25}` - all long). The fallback also returned the RAW book, which violates the constraints the caller asked for. Now: guard is relative
  (`1e-12 * raw_gross`) and the annihilation case returns `{}`. **When a projection "never fails", check what it returns when it produces nothing.**
  **DEFECT 2 (`volatility_target_scale`): the producer could not be called with the input it exists for.** `vol_override` (GARCH long-run vol) sat BELOW the `len(returns) < 5` guard, so it
  returned **0.0** with no series - and 0.0 zeroes a position size rather than scaling it. That is why `size.composite_position_size` and `analysis_tools.get_risk_overlay` re-derived
  `max(0, min(target_vol/vol, 3))` inline. Guard order fixed, both delegate, delegation **bit-identical** for existing callers. **CHECKED, NOT A DEFECT:** `momentum.ts_momentum_weights`'s
  `target_vol / mean(sigma_i)` is a BOOK-level ex-ante quantity, not the portfolio realized-vol scale - the review claimed three re-derivations, two were real.
  Tests: `test_cookbook_gaps.py` 27 -> 33, `test_strategies_size.py` +1; both defects RED under a faithful mutation with byte-identical sha256 restores.

- 2026-09-22 `(working tree)` - **A test sat one second inside its own timeout and killed the whole suite.** `tests/test_debate_stream_hermetic.py` capped itself at
  `pytest.mark.timeout(120)` while `test_full_stream_reaches_research_manager_when_structured_on` performs the **real ~87-tool vendor gather** (the LLM factory is
  stubbed; the vendor calls are not). Measured call time **119.21s** = 99.3% of the cap. `pytest-timeout`'s thread method does not fail one test when the cap is
  crossed - it dumps stacks and **terminates the process** - so a full-suite run died at 216s with **no summary and a bare exit 1**, and an immediate re-run passed
  green (5220). The module now carries **300s** (2.5x the measured cost); the global 180s default is untouched. **When a suite dies with no summary and a
  `++++ Timeout ++++` dump, look for a module-level `pytest.mark.timeout(...)` set BELOW the global default and a test whose cost approaches it.**

- 2026-09-22 `(working tree)` - **The market-breadth read promised measurements the vendor never sends, and its one live table rendered REVERSED.** `get_market_breadth`
  (moomoo) returns the vendor's rise/fall distribution and nothing else. The market prompt claimed "percent above the 20/50/200-day, advance-decline, new highs/lows ...
  with its panel size printed"; the news prompt told the model to call `get_market_breadth(ticker)` when the tool takes **no arguments** - a call that cannot succeed.
  **Measured across 91 report trees:** 42 got a real read, **0** contained a `% above the 20/50/200-day` claim, and the analysts correctly reported `NO_DATA_AVAILABLE`
  instead of substituting - so the false promise was **latent**, not active. The prompts were corrected anyway: a surface that promises a measurement nothing produces
  is this repo's recurring defect class.
  **The live defect was the RENDER.** The vendor NAMES each band's shape in `type` (`POSITIVE_INFINITY` = `(7%, +inf)`, `NEGATIVE_INFINITY` = `(-inf, -7%)`) and puts a
  sentinel on the border it does NOT mean; `get_market_breadth_moomoo` read the sentinel off the BORDER, so both open-end branches were dead code and the table rendered
  `| 7% … 0% | 494 |` / `| 0% … -7% | 731 |`. Those labels reached analyst reports verbatim, and two reports summed them into an "advancers" figure no band held.
  `_rise_fall_rows` now reads the shape from `type`, sorts the bands ascending, and renders an absent border (the vendor sends the string `'N/A'`, never `None`) as `?`
  rather than an invented infinity. **The panel is a NAMED GAP, not a promise:** market-wide breadth needs a `{name: closes}` panel, `market_breadth` takes one
  pre-fetched, `constituent_universe` is budget-bounded against fetching it ("FMP 250 req/day, yfinance throttled"), and `_technical_components`
  (`analysis_tools.py:5036-5041`) already declined it. The prompt now points at the participation read that EXISTS - `get_sector_rotation_screen(enable_breadth=True)`,
  per-sector `% above 50d SMA` with its own sample size - and `docs/design_sector_rotation_screener.md` §5.5 records both options and why wiring the panel would **not**
  close the score leaf's gap (different surface). Tests: `tests/test_moomoo_vendor.py` 54 -> 57, plus the existing breadth test strengthened - it asserted only the
  section headers, which is why the reversed table survived. All three RED under a faithful mutation (sentinel read off the border) with a byte-identical restore.

- 2026-09-21 `(working tree)` - **The three genuinely-absent regime reads are built, each on an EXISTING producer.** From the screener review's "only
  defensible build" list. **(1) Event-anchored AVWAP** - `extended_indicators.anchored_vwap_levels` locates anchors as bar INDICES and computes each level
  with the existing `anchored_vwap` over the slice from that bar (one implementation of the arithmetic). Anchors: `swing_low`/`swing_high` via the new
  `swing_pivots` (requires the right-hand CONFIRMATION bars - a low that can still be undercut is not a swing; a tied minimum is not a pivot),
  `opex_monthly`/`opex_quarterly` from `derivatives_gamma.opex_dates` (the repo's ONE third-Friday calendar), and any `event_dates` the CALLER supplies -
  FOMC/earnings dates come from a calendar, so they are input, never inferred from bars. `shift` = price below the swing-low VWAP **and** volume >=
  `volume_multiple` (1.5x) its average since that anchor. Surfaced in the existing `get_extended_indicators` tool; prompt trigger extended.
  **(2) True 52-week NH/NL** - new fields `new_highs_52w`/`new_lows_52w`/`net_new_highs_52w` on the ONE breadth producer, counted over a FIXED
  252-session year so a 60-bar and a 300-bar panel agree for the same last year; a name short of a year is excluded and reported in `new_highs_52w_n`;
  no year at all gives `None`, not `0`. New fields only - the printed `basis` keeps its meaning and now states the 52-week coverage.
  **(3) Walk-forward HMM with FILTERED probabilities** - `regime.hmm_filtered_regime`, pure NumPy (no optional dependency), forward recursion ONLY so
  row `t` is `P(S_t | x_1:t)`; `hmmlearn.predict_proba` runs the backward pass too and its rows use the future. Refit on `x[:t]` every 20 bars, filter
  re-run over that past window after each refit, states canonicalized by mean return; features `[log return, yang_zhang_vol_series]`. **`hmm_regime` now
  DELEGATES to it** - one HMM producer, two entry points - which retires the `hmmlearn` gate that made it return `unknown` on every run (247 occurrences,
  zero real labels, 91 trees). **Measured, not asserted:** appending 50 future bars to a 300-bar series left **0 of 39** overlapping filtered rows changed;
  the filter recovers a seeded two-regime series; deterministic across runs; `None` on too-short history. **A defect my own test caught:** `date_anchor_index`
  length-checked the date string, and `"not-a-date"` is exactly 10 chars, so it string-compared against every ISO date and returned a bar instead of `None` -
  it now PARSES the date, and a FUTURE event is a named gap rather than an anchor at the last bar. Also: `regime_score.py`'s citation of
  `market_breadth.py::market_breadth` moved 37 -> 44 and was updated in the same pass (the `test_every_component_names_one_producer_with_a_line` gate
  checks it points at the `def`).

- 2026-09-21 `(working tree)` - **Yang-Zhang gained a per-bar SERIES, on a shared core rather than as a second implementation.** A regime
  model needs a vol *series*; the repo had only the scalar `yang_zhang_vol` over a window. `yang_zhang_vol_series(opens, highs, lows, closes,
  window, periods=252)` returns `{series, n, measured, window, basis}` - aligned to the input, `None` before the first full window and for any
  degenerate one. The shared core is `_yz_legs` / `_yz_k` / `_yz_variance`, which `yang_zhang_vol` was refactored onto, so alignment, the weight
  and the combination each have ONE definition (rule 15: the two forms cannot disagree). **The refactor is bit-identical** - measured against a
  verbatim copy of the pre-change scalar on 179 real SPY bars, identical at windows None/5/20/60/120/400 and on all five edge cases (empty, 2
  bars, zero variance, a zero-price row, mismatched lengths). **The series matches the scalar at EVERY bar**, not just the last: 0 mismatching
  indices out of 160 (window 20) and 120 (window 60), including windows holding a bad row, where `k` is keyed on the aligned row count and not
  the requested window. **Warm-up is `window - 1`, not `2 * window`** - measured, first non-None at index 19 (w=20) and 59 (w=60); the nested
  rolling form a naive rewrite produces needs 40 and 120 and would silently drop that many rows from anything training on the series. **`None`,
  never `0`.** Three tests in `tests/test_strategies_covariance_models.py`; two faithful mutations RED with byte-identical sha256 restores
  (keying `k` on the requested window reddens the pinning test alone; doubling the warm-up reddens all three). Same pass: the module docstring's
  own inventory omitted `yang_zhang_vol` and `docs/developer/04-strategies.md` omitted it and `semivariance` - both corrected. **STALE CITATIONS
  REPORTED, NOT FIXED:** `docs/scores/{RiskScore,TechnicalScore,RegimeScore}.md` cite `volatility_models.*` at lines 48/78/116/185/226, but the
  real pre-change lines were 139/169/207/276/317 - those are owner-attributed score docs, and the citations were already stale before this change
  (this change shifts `ewma_vol` to 384 and `garch11_fit` to 425).

- 2026-09-21 `(working tree)` - **The analyst report-stub guard COULD NOT FIRE for a bare verdict line - the NTR tree shipped two stub
  analyst reports.** Reported by the owner as "missing content in several report belong to ntr". `reports/NTR_20260921_151301`'s
  `1_analysts/market.md` and `1_analysts/sentiment.md` looked plausible on disk (1,843 and 1,564 bytes) but their **model text was 36 and 407
  chars**. `_looks_report_stub` tested `len(t) < 400 and _ANALYST_STATUS_TURN_RE.search(t)`, and that regex is
  `\b(progress|let me (now )?(continue|gather|fetch|pull|collect|check|dig))\b` - a bare verdict line matches NONE of those alternatives, so
  the length clause was **structurally unreachable** for exactly this shape. Reproduced: `_looks_report_stub("FINAL TRANSACTION PROPOSAL:
  **HOLD**")` returned `False` on a 36-char "report". **The engine-score block masked both stubs**: `report_hygiene.engine_report_section`
  appends the TechnicalScore/SentimentScore section *after* the guard runs, adding ~1,157-1,807 chars, so the saved artefact reads as
  substantial while the model contributed 36 chars - **never length-check the saved file**. **Fix:** the test is length ALONE
  (`len(t) < _REPORT_STUB_MIN_CHARS`, 400); the regex is deleted rather than kept as a second condition, because it was a proxy for "not a
  real report" that could not fire for the pathology it existed to catch. The floor was chosen from measurement, not taste - across **64
  report trees** the shortest genuine report is ~8.4 KB (market), ~6.2 KB (fundamentals), ~2.7 KB (sentiment) against stubs at 36 and 149
  chars, a 20x margin; applying it to that corpus newly classifies exactly **two** reports as stubs (NTR market 36, MSFT 2026-09-16
  fundamentals 149), both unambiguous. **Tests:** `tests/test_analyst_report_stub.py` gains the bare-verdict shape (the exact NTR text, plus
  that the retry path replaces it with `**Report unavailable**` instead of shipping it) and a short-but-real report just over the floor; the
  bare-verdict test is **RED** under a faithful mutation restoring the regex gate, with a byte-identical sha256 restore. **Web impact:** none.
  **Known gap, NOT fixed here - and it is the reason NTR's sentiment is STILL a stub: the sentiment analyst has NO stub guard at all.**
  `retry_chain_if_stub` is wired into the market, news and fundamentals nodes only; `sentiment_analyst.py` renders from the structured
  `SentimentReport` via `invoke_structured_or_freetext` and stores the result unconditionally, and the schema's required `narrative` field
  has no substance floor - so a one-sentence narrative renders a report with no analysis. Closing it means either a `narrative` minimum (a
  schema/contract change) or wiring the guard into the structured node, and **the floor is a genuine judgement call, not a clear-cut fix**:
  short sentiment reports are a CLUSTER, not a one-off (across 64 trees HPE 390, QCOM 402, NTR 407, NVDA 531/611, AMZN 1,188 against a p10 of
  2,694), so raising the floor reclassifies ~9% of sentiment runs. Left to the owner.

- 2026-09-21 `(working tree)` - **The Benzinga firehose miss was reported as a DEFINITIVE ABSENCE after a BOUNDED scan - and probing the
  endpoints first changed the fix.** `get_insider_transactions_benzinga` and `get_congress_trades_benzinga` scan the market-wide Form 4 /
  congressional firehoses and filter locally, because both endpoints ignore every ticker parameter. The budget was **four pages of
  `pagesize=100`**, and the miss path raised `NoMarketDataError(detail="no Form 4 transactions for this symbol in the most recent filings")` -
  a flat claim of absence after looking at a prefix of one filing day. **Both phases of the recorded plan now land: the budget is ROWS, and the
  miss names the window it covered.** **Phase 0 changed the fix.** The two routes DO honour `date_from`/`date_to` - but only the **plain**
  spelling; the bracketed `parameters[date_from]` the calendars use is IGNORED there (a 2020 and a 2024 window both returned 0 rows, so the
  filter is real rather than ignored). Three further measurements then decided it: (1) `pagesize` is **not a cap** - `pagesize=100` returned
  233 / 100 / 275 / 289 rows on consecutive pages and `pagesize=1000` returned 2,425 in one response; (2) the page cursor is **stable**
  (identical row sets on back-to-back walks) but pages 1-4 of a trailing window ALL cover the SAME newest filing day as different slices, so the
  walk never steps back in filing time **[SUPERSEDED 2026-09-21 - see the Phase 3 record below: the UNFILTERED walk these readers make DOES step
  back monotonically (12 pages, 12/12 unique page hashes, 2026-09-17 back to 2026-08-18). The observation holds only of a windowed walk, and only
  at the top of the window]**; (3) a date window therefore *bounds* the query but does not *extend* the scan **[SUPERSEDED - a date window WOULD
  extend it; the row budget still stands, on the request count rather than on this]**. The plan's step (1), the row budget, is what shipped. **Phase 1:** `_filtered_pages` takes `page_size`/`max_rows`,
  inspects every row a page returns, and ends on an empty page or the budget - never on a short page. The old `if len(batch) < page_size: break`
  was unsound on ragged slices (a 3-row page ended the scan with rows still arriving). It returns a `_Scan` record
  (`rows`/`inspected`/`pages`/`truncated`/`lo`/`hi`) so truncation is observable rather than inferred. **Phase 2:** `_Scan.describe()` renders
  into both miss paths, e.g. `first 3,425 rows of the newest filings (2026-09-14..2026-09-17), a bounded sample - an older filing may sit
  beyond it`; a scan that reached the end of the stream drops the hedge. The date axis is the SERVED one - the **filing** date for Form 4
  (never `date_transaction`, which spans a year inside a single filing day) and the disclosure `report_date` for congress - so the window is
  not overstated. **Measured live:** a symbol absent from the scanned window (`AAPL`, `SPY`) gets the honest bounded-sample message naming 3,425
  rows and the window; a present one (`DELL`, 194 rows in the live window) is reached in **1 request inspecting 2,425 rows** where the old budget
  spent 4 requests for 400 nominal rows; congress `AAPL` renders `4 buys / 4 sells (net +0)`. **Tests:** `tests/test_benzinga_surface.py`
  27 -> 30, two of them failing-first by mutation with a byte-identical sha256 restore - reinstating the short-page break, and reverting the miss
  detail to the flat absence claim. **Web impact:** none - both render shapes are unchanged and no tool, CLI flag, env var or JSON key moves.
  **Phase 3 (2026-09-21) - the live verification, on the owner-named symbol `SKHY`, and it REFUTED two recorded claims.** Ground truth came from
  walking past the shipped budget: 12 pages x `pagesize=1000` = **20,811 Form 4 rows, 12/12 unique page hashes**, and 6 congressional pages =
  5,568 rows. **Verified:** `SKHY` has no row anywhere in that walk, and both readers return the honest miss naming the real inspected count
  (`first 4,304 rows ... (2026-09-11..2026-09-17), a bounded sample - an older filing may sit beyond it`) - so a true absence IS distinguishable
  from a truncated scan, which was the point of the fix. The 4,304 is the real count, not the 3,000 budget: a page is inspected whole and the
  budget is checked after it. **Verified:** `DELL` (first row at global index 1,789) still hits in 1 request. **Known-good arm, RESOLVED by owner
  decision 2026-09-21:** the plan's known-good symbol `AAPL` sits at global index **5,354** - beyond the then-shipped `_FIREHOSE_MAX_ROWS = 3000` -
  so that budget MISSED a mega-cap that genuinely has filings. The owner raised it to **7000**, re-verified live on all three arms: `AAPL` HIT in
  4 requests, `DELL` still 1 request, `SKHY` still an honest MISS now naming 8,674 rows instead of 4,304. The cost is confined to the miss path.
  **Both `_Scan` branches are now exercised live** (the first pass never did): the insider route always truncates - its stream dwarfs any sane
  budget - so it always hedges, while the **congressional** route reaches end-of-stream inside the budget and drops the hedge (`truncated=False`,
  7 requests). The end-of-stream is confirmed rather than assumed: a `pagesize=500` cross-check terminates the same way and bottoms out at the
  same oldest disclosure date, 2025-09-23. **Observation, NOT changed:** the two page sizes returned different totals for the same stream (5,568
  at `pagesize=1000`, 6,068 at `pagesize=500`), so the slices overlap rather than partition it - "rows inspected" is request volume, not distinct
  rows. **REFUTED #1:** the paging claim tagged SUPERSEDED above - the unfiltered walk DOES step back in filing time (pages 1-4:
  2,349 / 1,955 / 2,199 / 2,171 rows over 11 distinct filing days, 2026-09-17 back to 2026-09-04), so `describe()` reports a real date PERIOD and
  a date window WOULD extend the scan. **REFUTED #2, and it was this ledger's own error:** "AAPL has no Form 4 rows in the current window and was
  never a valid known-good" was concluded from a 3,000-row bounded scan - it repeated the very defect under repair. The `benzinga.py` module
  docstring and the `_filtered_pages` docstring now carry the corrected measurement.

- 2026-09-21 `(working tree)` - **Every finished report now carries its own TypeSafe verdict: `enable_jev_verdict` writes
  `jev_verdict.json` into the report tree.** Owner instruction: run jev each time a report has finished generating, and put the
  verdict JSON in the corresponding report folder. **The jev core MOVED out of `scripts/` into the package** -
  `tradingagents/jev.py` now holds the model client, the neutraliser, the batteries and the tree readers, and
  `scripts/jev_decide.py` is only the argument surface. The verdict must be callable from the pipeline (`batch.py`, which
  trading_web also calls), and production code importing from `scripts/` inverts the dependency while duplicating the logic
  would create a SECOND authoritative producer of the same numbers. **The 353-line core was SLICED, never retyped** (verified
  byte-identical after the move) and the 37 existing tests were repointed by one import line plus three `main`/`_parse_args`
  call sites. **New `judge_tree(tree, key=...)`** = the `--verdict` recipe + `write_verdict` into the tree, one call so a caller
  cannot judge without storing; `verdict_for_tree` returns `ratings` (rating/confidence/probabilities/evidence/horizon per
  stem), `neutralized` counts, raw `results`, `failures`, `cost`. **The hook is best-effort, like `enable_pre_market_review`** -
  a judge that annotates a finished run must never fail it: a missing `OPENROUTER_API_KEY` skips with a log line (the engine
  does not require that key), and a vendor failure or transport exception is RECORDED in the payload with the vendor's own
  message. Both asserted. **New gate `enable_jev_verdict`** (`TRADINGAGENTS_ENABLE_JV_VERDICT`), five places, **ships off**
  (matching `enable_pre_market_review`, so the web app's runs do not silently start paying) and set `true` in the owner's
  `.env`. **A NEW registry section was needed - §7c "Post-run output gates"**: this gate is not §6/§7b (adds no source the
  model reads), not §7 (changes nothing the model reads) and not §1/§2 (cannot stop, shrink or reroute anything) - by the time
  it runs the decision is already saved, so it can only add a file. `batch.py`'s two post-save hooks were extracted into
  `_post_save_annotations` so the gate is testable without running the graph. New `tests/test_jev_verdict_hook.py` (12),
  **failing-first by mutation** (calling the hook unconditionally turns `test_gate_off_never_calls_the_judge` red, sha256
  restore MATCH). **One test had to be written differently and the reason generalises:** `assert DEFAULT_CONFIG["x"] is False`
  passed BEFORE the `.env` flip and failed after - `DEFAULT_CONFIG` is the default *after* `_apply_env_overrides`, so it asserts
  the developer's `.env`, not the shipped default. It now reads the `DEFAULT_CONFIG` **literal** structurally via AST. **Any
  "defaults off" test that reads `DEFAULT_CONFIG` is machine-dependent.** Measured live: the hook run against the real vendor
  on `NVDA_20260921_114014` and `MSFT_20260921_114625` wrote a 5.8 KB `jev_verdict.json` into each (NVDA `fundamentals=hold,
  market=hold, news=buy, sentiment=hold`; MSFT all four `hold`), 0 failures. **Web impact: a real one** - `analyze()` now calls
  the hook and trading_web calls `analyze` directly, so a web run writes the file when the flag is on; off by default and
  additive, so an app that does not set the flag is unaffected.

- 2026-09-21 `(working tree)` - **The jev judgement recipe is now `--verdict`: analyst reports only, de-biased, judged
  buy/hold/sell.** Owner instruction - when asked to send a set of reports for a stock symbol, do three things: (1) send ONLY
  the analyst reports, (2) strip position language ("buy", "hold", "sell", ...) before sending so the judge is not handed the
  conclusion, (3) ask for a three-way buy/hold/sell rating. **One flag, because it is one intent:** `--verdict` = the four
  analyst reports only (never the research/risk/portfolio documents, which already carry a conclusion) + position language
  neutralised + the buy/hold/sell battery. `--verdict` and `--all` are MUTUALLY EXCLUSIVE (`--all` contradicts "analyst reports
  only"); the pieces are available alone as `--neutralize` / `--rating`, so the composition is testable rather than implied.
  **Neutralising is the substantive part:** the analyst reports STATE a rating and a rating is what is being asked for, so
  without stripping it the judge measures agreement with the document rather than with the evidence. Words become `[POSITION]`,
  never deleted - the substitution stays visible and is counted per report. **The word list is deliberately NARROW:**
  `buy`/`sell`/`hold`, `strong buy`/`strong sell`, the weight and perform scales, `accumulate`/`distribute`. It EXCLUDES `long`,
  `short`, `add`, `reduce`, `trim`, `neutral` - each is ordinary English in a market report (`long-term`, `short interest`,
  `adds to risk`, `reduces margin`), so stripping them removes EVIDENCE, not bias. Case-insensitive on word boundaries, so
  `buy` does not touch `buyback` and `hold` does not touch `shareholders`/`holdings`; multi-word positions are consumed whole
  so `strong buy` leaves no orphan `strong`. **Measured live on `NVDA_20260921_114014`:** 20 terms replaced (fundamentals 9,
  market 4, news 5, sentiment 2); ratings `fundamentals hold 0.85`, `market hold 0.67`, `news buy 0.25`, `sentiment hold 0.90`,
  cost $0.000909. **The de-biasing CHANGED AN ANSWER:** under the old stance battery without neutralisation sentiment read
  `bullish` at confidence 1.00; with its stated position stripped it reads `hold` at 0.90 on evidence 2.01 - the bullish call
  was the DOCUMENT's, not the evidence's. **And note the cross-check this enables:** the analyst evidence judged blind gives a
  HOLD consensus while the run's own decision was `Underweight` - the bearish conclusion is produced by the
  research/risk/portfolio stages, not by the analyst evidence. `tests/test_jev_decide.py` **27 -> 37** (the replacement count,
  multi-word consumption, the word-boundary guards, the deliberate non-stripping of ambiguous English, the no-op case, the
  battery vs the discriminator, `--verdict` end-to-end asserting ALL THREE requirements at once, `--rating` alone NOT
  neutralising, `--neutralize` alone keeping the default battery, `--verdict`/`--all` rejecting each other). Docs:
  `docs/developer/06-entrypoints.md` + `docs/api_reference.md`.

- 2026-09-21 `(working tree)` - **`scripts/jev_decide.py` could only reach 4 of a report tree's 15 reports - the stem list is now
  stage-aware.** `report_states` resolved every stem as `<tree>/1_analysts/<stem>.md`, so the utility could judge an ANALYST
  report and nothing else. A tree is STAGED (`2_research/`, `3_trading/`, `4_risk/`, `5_portfolio/`, plus the root roll-up), so
  the research, trading, risk and portfolio reports were unreachable - and the 11 it could not reach included the one document
  that matters most, `5_portfolio/decision`. Found by ACTUALLY RUNNING IT on a fresh tree (`NVDA_20260921_114014`, from the
  "nvda msft goog ibm" 4-worker batch): the CLI reported `states: ['fundamentals','market','news','sentiment']` while the tree
  held 15 `.md`. **`--stems` now takes two forms:** a BARE name still resolves to `1_analysts/<name>.md` (what it has always
  meant; the analyst report wins if a root file shares the name) and falls back to a tree-root report so `complete_report`
  resolves; a SLASHED name is a path relative to the tree (`2_research/bull`, `5_portfolio/decision`). **A resolved path outside
  the tree is refused** - `--stems ../../etc/passwd` is a bug, not a feature; `--state-file` remains the flag that deliberately
  takes any file. New **`--all`** sends every report in the tree in PIPELINE order (stages first, roll-up last) rather than the
  alphabet, so a read-out follows the run. Verified live: `--stems 2_research/bull` resolves and judges (`bullish`, conf 1.00,
  evidence 2.81 - the same read the ad-hoc driver produced), and `--all` enumerates exactly the 15 reports in pipeline order;
  the throwaway driver is deleted. `tests/test_jev_decide.py` **19 -> 27** (stage-qualified resolution, root fallback,
  analyst-wins precedence, the escape refusal, `--all` pipeline order, an empty tree, `--all` through `main()` with the injected
  transport proving ONE CALL PER REPORT rather than one per tree, and the no-match path exiting 1 with no request). Docs:
  `docs/developer/06-entrypoints.md` + `docs/api_reference.md`. Lesson: **a reader that takes a stem list will silently
  under-report when the thing it reads grows a stage** - run it on a real tree, do not read it.

- 2026-09-21 `(working tree)` - **A dangling test reference, and `ruff check .` (CI's own command) was FAILING while three documents
  claimed the repo was clean.** **(1)** `tests/test_decision_challenge.py`'s docstring said the gate registration "is enforced by
  `tests/test_gate_env_switches.py`" - the registrar is `tests/test_gate_env_toggles.py` and the named file has never existed.
  Fixed, and the class is now checked: `test_every_test_file_a_test_module_names_exists` in `tests/test_doc_binding_claims.py`
  (the doc-claims gate, whose docstring already frames the mission as "the false claim outlived the gate that produced it")
  asserts every `tests/test_*.py` named by another test module exists. **Third instance of the class this session** (the gate
  registry's "Proven by" column named two more), each previously caught by hand. **Scoped to test-module references on purpose**:
  measured over `docs/`, **28** `tests/test_*.py` references resolve to nothing and ALL are legitimate - `docs/implementation_plan_*.md`
  and `docs/design_*.md` are forward-looking plans naming tests still to be written, several in the sibling repos
  (`test_doc_claims.py`/`test_engine_contract.py` are `trading_web`'s, `test_inbox.py`/`test_envelope_v2.py` are
  `TradingExecution`'s), and the CHANGELOG records renames. A blanket doc check would be an over-strict invariant failing on 28
  TRUE statements. Word-boundary anchored so `strategies/backtest_engine.py` is not read as a `test_engine.py`. Failing-first:
  restoring the stale reference turns the guard red, sha256 restore MATCH. **(2)** `.github/workflows/ci.yml:61` runs `ruff check .`
  under a job literally named "ruff (strict, full repo)", and `AGENT_ONBOARDING.md:183-184`, `docs/developer/08-development.md:26`
  and the README all state the whole repo is clean. **It was not - 4 findings:** `scripts/score_panel.py:1274` UP034,
  `:1336` C401, `:1714` B905 (the INNER `zip(train, test)` lacked `strict=`; the outer call had it), `cli/stats_handler.py:1` I001.
  All four fixed behaviour-preservingly (`set(gen) == {gen}`, `zip(a,b) == zip(a,b,strict=False)`); B905 takes `strict=False`
  NOT `True` - `strict=True` would raise on ragged pairs and a lint fix must not change behaviour. **So my initial framing
  ("widen the scope") was WRONG: the scope was already documented whole-repo in three places - the defect was that the repo
  did not meet its own stated bar and nothing caught it locally.** The real trap was the copy-pasteable quick command:
  `AGENT_ONBOARDING.md:140` read `py -3.12 -m ruff check tradingagents/ ...`, so an agent copying it lints ONE directory and
  reports clean - that is how `scripts/` and `cli/` rotted. It now reads `ruff check .`, matching the contract the same file
  states 40 lines later. **`ruff check .` passes.** Lesson: when a doc states a repo-wide bar, the fix is to MEET it, not to
  narrow the bar to what currently passes - and check the copy-pasteable command, not just the prose.

- 2026-09-21 `(working tree)` - **`docs/api_reference.md` §1.1 said "(complete)" over a table that was 36% empty, so the
  table is now GENERATED from the code and a test keeps it that way.** The heading documented **165 of 258** `_ENV_OVERRIDES`
  rows: **95 knobs were missing** - the whole debate block (`TRADINGAGENTS_DEBATE_*`), `TRADINGAGENTS_BACKTEST_*`,
  `enable_decision_guardrail`, `enable_tuner`, `enable_prediction_ledger`, `enable_news_relevance`, `llm_tier_*`, `monitor_*`,
  `knife_*`, `moomoo_screen_*`, `patentsview_api_key`, `tool_call_log_dir`, every `enable_*_score` gate. Same class as the bugs
  this session has been fixing: **a name that promises more than it measures.** Hand-patching was the cause - the table has been
  backfilled by hand at least three times (2026-08-21 `TRADINGAGENTS_ENABLE_MASSIVE_FLAT`, and twice more), and it showed:
  **~15 duplicate rows**, **3 mangled rows** that had lost their env cell and merged into a neighbour (`catalyst_hard_block_days`,
  `enable_alpha_profile`, `max_pairwise_corr`), an **unescaped `|` in the `debate_divergence_min` note** (`|bull−bear|`) that
  split that row into five cells, and 2-cell rows under a 2-column header beside 3-cell rows. **One knob did not exist:**
  `TRADINGAGENTS_ENABLE_ALPHA_PROFILE` -> `enable_alpha_profile` - no file reads the env var, the key is in neither
  `DEFAULT_CONFIG` nor `_ENV_OVERRIDES`, and the real `alpha_profile` is a **report output key** in
  `scripts/strategy_quality_report.py:211`. That row conflated a report field with a gate; removed. **Two mechanisms reach the
  config and the doc now covers the union:** `_ENV_OVERRIDES` (258) plus the six literal `os.getenv("TRADINGAGENTS_...", fb)`
  reads inside `DEFAULT_CONFIG` (`results_dir`, `data_cache_dir`, `llm_failure_journal_dir`, `report_verify_model`,
  `report_verify_max_calls`, `memory_log_path`) = **264 pairs**, ordered by the code's own declaration order. New
  `scripts/gen_api_reference_table.py` (`--write` / `--check`) preserves every existing human note verbatim and adds only a
  code-derived `default X` note for new rows - never an invented semantic one, never a value for a credential-shaped key. New
  `tests/test_api_reference_env_table.py` (4) asserts the table lists exactly the code's surface, keys each row correctly, uses
  one cell count, and has no duplicate env var. **Failing-first against the pre-fix document: 3 of 4 red (102 omitted, cell
  counts `{23: 2, 43: 5}`, the duplicate set), sha256 restore MATCH.** Lesson: a doc that claims completeness needs a check that
  FAILS when it stops being complete, or the claim decays on the next hand-edit.

- 2026-09-20 `(working tree)` - **The FundamentalScore appendix was arithmetically impossible, and the card's number was a second producer.**
  Found by reading `reports/MSFT_20260920_145644/1_analysts/fundamentals.md`, which prints `### FundamentalScore - 67.71/100` above
  `- FQS: 0/100`, `- FGS: 0/100 over 1 components`, `withheld: {'FTNT': ..., 'GEN': ..., 'NOW': ..., 'RBRK': ..., 'ZS': ...}`,
  `- VS: 0/100 over 2 components`, `- FRS: 0/100`. No weighted average of four zeroes is 67.71, and the `withheld` dict names
  PEER-PANEL tickers. **Defect 1 - the renderer read a panel-keyed structure as a category-keyed one.** `format_engine_detail`
  (`quant_scorecard.py`) was written for TechnicalScore/regime/risk/sentiment, whose categories carry `score`/`present`/`withheld`
  as SCALARS. FundamentalScore is a PANEL engine: each sub-score keys `scores`/`bands`/`coverage`/`withheld` BY TICKER. Three
  misreads: (a) the score came from `next(iter(scores.values()))`, and `factors.category_scores` inserts names in ASCENDING
  percentile order (`sector_rank._pct_rank` walks sorted values), so the first entry is always the WORST peer, whose percentile
  is `0.0` - that is why all four printed zero, a structural certainty not a coincidence; (b) `withheld` was printed verbatim and
  is ticker-keyed; (c) `present` fell through to `factors_NA`, which is the set of factors with NO SUPPLIER, so `over 1
  components` counted a MISSING factor (`rev_cagr5`) - and the `components` lookup could never match anyway, since the panel
  engine's `components` is keyed by ticker too. **Fix:** resolve the analysed ticker's own row from the snapshot's own `ticker`,
  print the sub-score's band and its coverage over its own factor set, and name NA factors as the gap they are
  (`factors NA: rev_cagr5`). **Verified on live MSFT output:** FQS 75 (elite) + FGS 40 (stalling) + VS 75 (below-market) + FRS
  87.5 (fortress) = 277.5 / 4 = 69.375 ~= **69.38**, the printed composite. **Defect 2 - D-8 recurring.**
  `_run_card_fundamental_score` called `fundamental_score_for_ticker` AGAIN at write time, so one run had TWO producers: the
  prompt's scorecard said **67.71** and the card said **55.21**. `_run_card_trade_score` already carries this fix (`P12-5`:
  "reads the run's own score snapshot when there is one ... so all three surfaces print one number rather than three assemblies
  (defect D-8)"). The fundamental block never got it; it now reads
  `final_state["quant_scorecard"]["engines"]["fundamental"]["result"]`, recomputing ONLY as the legacy fallback. **The old
  docstring claim "recomputed deterministically at write time" was FALSE:** `peer_universe.resolve_peer_universe` re-fetches
  statements and sectors LIVE on every call with NO CACHE, and a transient vendor failure returns `None` metrics that silently
  drop names from the cross-sectional scored set - measured on `(MSFT, 2026-09-20)`: **113 metric diffs between two identical
  calls** and **three consecutive composites 61.25 / 69.38 / 79.17**. **Noted, NOT fixed:** `_pct_rank` does not round, so a
  3-way tie over 7 scored names renders as the literal `33.333333333333336/100` (the composite IS rounded by `combine`); the
  renderer's `_plain` is documented as EXACT for detail surfaces, so this is a producer characteristic, shared with the ETF
  ranking path, and changing it is out of scope. Regression tests:
  `tests/test_quant_scorecard.py::test_level_two_reads_the_analysed_tickers_own_row_in_a_panel_engine`,
  `tests/test_fundamental_score.py::test_run_card_block_reads_the_runs_own_snapshot`. Both confirmed FAILING before the fix
  (the first reproduced the report's block byte-for-byte).
- 2026-09-20 `(working tree)` - **Design study: Dream-RSI (arXiv:2609.14858) read against this repo.**
  `docs/design_dream_rsi_replay_simulator.md`, new. No code changed. The paper optimises the *exploration policy* of a
  long-horizon program-discovery loop by turning completed discovery trees into a **replay simulator** (score candidate
  policies offline against recorded outcomes, redeploy the best). **The mechanism does not transfer here, for two
  independently checked reasons.** (1) **A recorded tree here is a chain, not a tree** - Dream-RSI replays because its tree
  holds outcomes for branches a different policy would have taken; this repo runs ONE trajectory per analyst, so replay can
  only evaluate TRUNCATIONS of what actually ran. (2) **The round structure is not recorded at all** - verified on
  `reports/WDC_20260915_120300`: `tool_evidence.json` leaves carry `ts` = `time.monotonic()` (`evidence_gather._leaf`), a
  process-relative float and not a round index; those leaves are the deterministic gather's SINGLE pass, not the LLM's
  rounds; `run_card.json` has no round counts; and `tool_call_log.log_tool_call` writes to `<data_cache_dir>/tool_calls/`,
  OUTSIDE the report tree, with no round index either. So the paper's `N_im` / `k_i*` have no producer here. **What does
  transfer:** (a) **the selection rule must not be the paper's** - its `V^{m*} >= V^0` is an IN-SAMPLE guarantee, i.e. the
  winner's curse, and this repo already owns the correction unused on this question (`strategies/evaluate.py`:
  `deflated_sharpe:103`, `pbo_flag:235`, `reality_check:311`, `spa:351`, `purged_cpcv_splits:181`); (b) the **prefix-only**
  constraint (a policy may read only what it could have observed at decision time - the allocation is currently scattered
  across `research_depth`, `MAX_TOOL_ROUNDS` and a dozen gates with no such statement); (c) a **cost term** - quality
  (`verify_flags.json`) and cost (`reporting._run_card_llm_cost_est:980`) are measured and NEVER joined; (d) **§5.1 as a
  falsifiable experiment** - the paper measures explicit directional guidance as consistently UNDERPERFORMING its unguided
  counterpart, and this repo injects exactly that on by default (`enable_reflection` `default_config.py:819`;
  `reflection_hint` `strategies/reflection.py:83`; `build_reflection_context:109`; `past_context` `trading_graph.py:619-625`
  -> `portfolio_manager.py:134-139`). Cheap ablation of an always-on feature, runnable with `context_ab.mcnemar_exact:309`
  over the 56 recorded trees. **Prior work credited:** `scripts/context_ab.py` IS a replay simulator over recorded trees
  already (`decision_items_from_tree:1189`, `ARMS:396`, `compact_prose:454`) - for CONTEXT policies; it does not replay how
  much research to buy. **Pre-existing discrepancy recorded:** `deflated_sharpe`'s docstring says "Euler-Mascheroni-based"
  but its body is the simplified `observed - sqrt(2*ln n_trials)`. **Do not start at the replay loop** - the plan's Phase E
  is the last thing to build, not the first.
- 2026-09-20 `(working tree)` - **`scripts/jev_decide.py`: a utility for the TypeSafe decisions model
  (`typesafe/jev-1.13` on OpenRouter), plus the two facts that make it necessary.** Both obstacles were found by CALLING the
  model, not by reading anything. **(1) It is not a chat model.** `POST /chat/completions` returns `400` and names the endpoint
  that does work: *"typesafe/jev-1.13 is a decisions model and cannot be used with the chat/completions endpoint. Use the
  /api/alpha/decisions endpoint instead."* That endpoint takes `{model, state, questions}` - there is **no `messages` field**, so a
  document is sent as `state` and the ask as `questions`. **(2) The question schema is a discriminated union on `type`**:
  `noul` | `choice` | `score`. `choice` takes `criteria` as a **record** (label -> rubric or null), `score` as an **array**
  (lowest -> highest), `noul` neither; and **`noul` answers with a FLOAT, not prose** (`0.67`) - it is a numeric judgment, not a
  free-text channel. `validate_questions` enforces the contract before spending a request, so a shipped default battery cannot be
  a 400. **(3) The key-resolution trap.** A hand-rolled byte parse of `.env` returned a **75-char** token where `dotenv_values`
  returns the real **73-char** one: the value is **quoted** in `.env`, so the raw bytes carry the quote characters into the token.
  OpenRouter replies `401 Missing Authentication header` - which blames the header, not the token - and the tell is that an
  **arbitrary garbage token returns the same sentence** while a well-formed-but-unknown key returns `401 User not found.` So
  `/models` proves nothing (it is a PUBLIC endpoint: it validated no key), and the utility uses `dotenv_values` like the engine.
  **(4) The slug is absent from the public `/models` catalog** (446 entries, no `jev`/`typesafe`) and serves anyway - catalog
  absence is not unavailability. The default battery asks about the document (stance, evidence strength, horizon) and encodes no
  trading policy; `--questions FILE` overrides it. Live on `MSFT_20260920_145644`: ~0.7 s and ~$0.0002 per report; the two
  price/valuation stems read `neutral` with the strongest evidence scores and the two narrative stems read `bullish` with weaker
  evidence. 19 hermetic tests (`tests/test_jev_decide.py`), transport injectable, no vendor and no key. Documented in
  `docs/developer/06-entrypoints.md` §6.5 and `docs/api_reference.md` §9.
- 2026-09-20 `170d503` - **Owner decision: the Decision Packet PROCEEDS - as a BOUND, not a lever.** Asked whether the packet
  should proceed at all given that Phase 1 measured `P1 -> P2` flip rate of **exactly 0.000**, the owner answered *"Proceed - the
  packet is a bound, not a lever."* Recorded in `docs/design_decision_context.md` §13.3: **H1a is WITHDRAWN as the packet's
  justification** (it was tested and is not supported in either representation), the packet's defence is its own contract (the §7
  budget, §8 vocabulary, §9 ledger), the **representation axis is left OPEN and NAMED** (58% of decisions change, 6:1 toward HOLD,
  `P(no-trade)` 0.417 -> 0.833, confidence 0.652 -> 0.248, ungrounded 2/12 -> 9/12 - a COST, on n=12), and Phases 3-5 stay built
  and **gated OFF**. The doc claims nowhere that the packet makes decisions better. **Do not re-open this as a quality claim.**
- 2026-09-20 `4072c64` (TradingExecution) - **Owner decision: signald recovery stays MANUAL.** Detection works and recovery is
  manual by choice, not by omission: an auto-restart would mask a daemon that is *wedged* rather than dead (the PID lock refuses a
  second instance, so the attempt is a silent no-op exactly when it matters) and would turn a visible outage into an invisible
  restart loop. The cost - a Friday-afternoon death stays down until Monday 08:00 - is stated in
  `TradingExecution/docs/RUNBOOK.md` rather than discovered at the next incident. **Do not add an auto-restart.**
- 2026-09-20 `(working tree)` - **Nine standing defects fixed, and ONE OF THE RECORDED DEFECTS WAS WRONG: the signald "no
  supervisor exists" finding was a false premise.** **(0) The signald claim, corrected.** The record said *"the daemon is DEAD and
  nothing restarts it - no supervising restart process exists."* **False.** `Signald_Daemon` exists (logon + weekly MON-FRI 08:00,
  `RestartOnFailure` PT1M x10, `ExecutionTimeLimit` PT0S) and `Signald_Watchdog` exists (weekdays 08:00, every 5 min for 7h30m).
  Measured on the 2026-09-18 death: died **15:15 CT** (`^C`; `Last Result` `-1073741510` = `0xC000013A` `STATUS_CONTROL_C_EXIT` - a
  deliberate `schtasks /end`, not a crash); `RestartOnFailure` **cannot** fire (it retries a *failed* run, and a deliberate end is not
  one); the watchdog **did** fire at **15:30**, `Last Result: 1` (the `heartbeat_loss` page). So **detection works, recovery is
  manual**, and the weekday 08:00-15:30 window means a Friday-afternoon death is paged **exactly once** then silent all weekend.
  `TradingExecution/docs/RUNBOOK.md:36` said *"Nothing runs the watchdog for you"* while line 56 of the same section documented the
  scheduled task - **stale and self-contradicting, corrected** (`TradingExecution 3423f2b`). The D-6 failure mode (*a stale line
  hiding a wire*) in our own record. **(1) ATR windows are now part of the basis.** `_basis_of` recorded only the unit class, so ATR
  quoted at several windows collapsed into one basis and read as `defect`. New `_windowed_basis` binds the window printed beside the
  figure (`ATR(14)`/`ATR-14`/`atr_14`/`14-bar ATR`/`ATR 14` -> `atr:14`; `ATR(14, simple mean of TR)` -> `atr:14-simple`) and does
  NOT read the `(n x ATR)` multiple leg or a `22-bar` anchor as a window. **Re-measured over the same 56 trees in ONE run, before and
  after: `defect` 59 -> 32 (-27, exactly the ATR rows), `basis_difference` 186 -> 215, `unresolved` 18 -> 16, TOTAL 263 -> 263.**
  The unchanged total is the evidence it is a pure RECLASSIFICATION, not a quiet excuse. **(2) The kill-switch state is PRODUCED.**
  Three readers (`prompt_metrics.py`, `reporting.py` x2) read `state["kill_switch_state"]["active"]` and NOTHING wrote the key, so
  `portfolio_action_from_gate`'s `kill_switch` leg (`EXIT`/`NO_TRADE`) was dead. Measured from the one realized book drawdown the run
  already resolved against the configured HWM hard tier; the session-p&l leg has **no in-engine producer** (the executor owns live
  p&l) so it is passed `None` and NAMED in `unmeasured_legs`, never guessed. **(3) `TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT` was INERT**
  - documented in `.env` since 2026-09-04 and read by nothing; the block was built unconditionally. Real gate now, registered in all
  five places, and **`True` is its default - the only context gate that is** (the shipped behaviour was "always on"; `False` would
  have silently dropped a shipped prompt block from every run without `.env`). **(4) D-10: the debate consensus exit was dead.**
  `_complete_round` reads the agreement off the section CHANNEL while the stances live in the graph STATE, which only `l1_node` sees -
  so the key was never written and every debate ran to its round cap. `independent_agreement` gained `roles` so the research debate
  scores its OWN bull/bear pair (parameterised, one producer); `None` keeps the contour off, because a fabricated `1.0` would terminate
  a debate that never converged. **(5) A forward `PEG` had no caller** - wired to `dataflows/yfinance_sector.fetch_estimate_trend`
  (price / next-FY consensus EPS over next-FY vs current-FY growth) behind the EXISTING `enable_analyst_estimates` gate, with the basis
  printed; trailing `eps_yoy`/`revenue_yoy` were REJECTED as proxies that do not measure forward growth. **(6) `value_dip_setup`'s
  `catalyst_window: bool = False`** was the last false assertion of the D-11 class; now tri-state, forwarded unchanged. **(7) The
  sentiment baseline was written TWICE per run** - `compute_social_scores` APPENDS to the baseline `surprise_velocity` z-scores
  against, and had three callers in one run (the prefetch + two tool-side readers); the second reader also passed no `cache_dir`, so it
  could write a DIFFERENT baseline file than the prefetch reads. New `record: bool = True` makes the prefetch the single RECORDER and
  every other caller a READER. **(8) A provider failure was counted as a verifier SUCCESS and lost its reason** - the exception branch
  fell through with no `reason` and still incremented `stem_succeeded`, so a run whose calls were all rejected read `UNKNOWN`
  everywhere with nothing to distinguish it from a verifier that never started (Alibaba's "inappropriate content" rejection did
  exactly this). **(9) The recorded `sentiment_tools()` "defect" is NOT a defect** - the sentiment analyst binding no tools is
  documented deliberate design in four places, and the toolset exists so the ENGINE can reach those leaves; the real defect in that
  cluster was the double-append above. **Failing-first by mutation, byte-identical restore:** kill-switch producer removed ->
  `test_kill_switch_state_is_produced_and_can_fire` fails (`assert None is True`); D-10 join removed ->
  `test_d10_consensus_exit_reads_the_section_agreement` fails (`KeyError: 'independent_agreement'`). **The mutation harness itself had
  to be fixed** - it round-tripped through `str` with `newline=""` on a `core.autocrlf=true` mixed CRLF/LF tree, silently rewriting two
  source files' line endings; it now reads/writes BYTES, and both files were restored to CRLF with `git diff` confirming identical
  content (96 insertions / 4 deletions). **Also:** the 47 pre-existing ruff findings in `tests/` cleared (behaviour-preserving), so
  `ruff check tradingagents/ tests/` is clean for the first time; and `docs/scores/MEASUREMENT_FINDINGS.md:262-263`'s stale
  `news_score ... **0** measured` was RE-MEASURED - the panel axis is genuinely `0` (structural: none of the engine's 11 component
  names is in the panel's 37-name vocabulary) but the live path now measures **2 of 11** (of 8 cards carrying `news_score`, 3 real -
  MSFT 57.6 x2, QCOM 58.8 - and 5 `"score": null, "unavailable": "no news producer measured"`). `test_report_verify.py` 233 -> 237,
  `test_sentiment_computed.py` +1, `test_debate_risk_parity.py` +1, `test_risk_context_hoist.py` +1.

- 2026-09-20 `(working tree)` - **The Benzinga surface: five new capabilities, six backup registrations, and three transport
  defects that made two thirds of the API unreachable.** Owner instruction: put Benzinga in the `news_data` chain, implement the
  five capabilities from the entitlement assessment, wire the vendor as a backup wherever an alternative exists, and re-rank every
  multi-vendor chain by payload richness then quota. **The chain:** `news_data` is now `eodhd,benzinga,moomoo,yfinance,alpha_vantage,
  stockdata,newsapi` - Benzinga is SECOND because it is the rare free feed that is both ticker-filtered and financial-first, so it
  precedes the generic keyword feeds; the exclusion it replaces was justified by "no real key registered yet", a reason that lapsed
  the moment the key was exercised. **Five capabilities, four with no producer at all before this:** `get_guidance_revisions`
  (`/v2.1/calendar/guidance`, management's own forward revenue/EPS range - the only forward GROWTH producer in the data layer),
  `get_fda_calendar` (`/v2.1/calendar/fda`), `get_offerings_calendar` (`/v2.1/calendar/offerings`, a dilution signal),
  `get_analyst_actions` (`/v2.1/calendar/ratings`, the event view complementary to `get_analyst_ratings`' consensus), and
  `get_news_removed` (`/v2/news-removed`, the only feed here that can INVALIDATE evidence already collected). All five sit behind ONE
  new gate, `enable_benzinga_surface` (default OFF, registered in all five places) - one vendor's surface, one risk profile, one
  opt-in; while off each returns a `DATA_DISABLED` sentinel and never fetches. **Six backup registrations** on `get_stock_data`,
  `get_earnings_calendar`, `get_analyst_ratings`, `get_insider_transactions`, `get_congress_trades`, `get_corporate_actions`.
  **Re-ranking:** one chain was ordered AGAINST the criterion - `get_insider_transactions` ran `alpha_vantage,yfinance,moomoo`, a
  25 req/day keyed vendor in front of `moomoo` (local OpenD, no quota, richest rows) and `yfinance` (keyless); now
  `moomoo,yfinance,alpha_vantage,benzinga` via a `tool_vendors` override, needed because the method lives in the `news_data`
  CATEGORY and would otherwise inherit the news chain and put the Form 4 firehose first on every lookup. **Three transport defects,
  each of which broke something: (1) `BASE` hardcoded the `/v2` version segment**, so `v2.1/calendar/ratings` was requested as
  `/api/v2/v2.1/calendar/ratings` and answered with the gateway's own `no Route matched with those values` 404 - the module could
  only ever reach the `/v2` routes, so NO calendar was implementable (news is `/api/v2`, calendars `/api/v2.1`, alt-data `/api/v1`).
  **(2) Every dict-wrapped 200 was collapsed to `None`** - `/v2/news` is a bare list but every calendar is a dict keyed by its own
  family (`{"ratings": [...]}`), the alt-data surface is `{"data": [...]}` and `/v2.1/fundamentals` is `{"result": [...]}`; returning
  `None` for any dict reported each of those as "no data" on a 200 that carried rows, so only the bare-list news route ever worked.
  **(3) `congress.get_congress_trades` could not fail, so it could not fall back** - `route_to_vendor` treats ANY returned string as
  success, so the prose `"congress trades unavailable..."` stopped the chain and every later vendor for that method was unreachable
  (the Benzinga backup added here would have been dead code); it now raises the typed `NoMarketDataError` with the reason as detail,
  and a partial result (one chamber answering) still renders. **Three parameters that do nothing, so none was shipped:**
  `/v2/news-removed` ignores EVERY date parameter (empty filter, one-day window and three-month window all return identical rows)
  while `pageSize`/`page` work, so that reader takes a limit and a page and states it offers no window; both alt-data endpoints
  ignore EVERY ticker parameter (`tickers`/`symbols`/`parameters[tickers]`/`company_symbol` all returned the identical market-wide
  stream), so those readers page the stream, filter locally, and say so; and `/v2/bars` REQUIRES `interval`, without which the
  vendor answers 200 with a stub row carrying no candles. **Tests:** `tests/test_benzinga_surface.py`, 25 tests; the two transport
  tests are failing-first proofs - each re-run against a faithful reconstruction of the pre-fix behaviour (`BASE` re-pinned to
  `/api/v2`; `_unwrap_records` reverted to collapsing every dict) turned RED, with a byte-identical sha256 restore. **A pre-existing
  registration gap fixed in the same pass:** `enable_options_surface` and `enable_risk_free_curve` shipped with a `DEFAULT_CONFIG`
  key, an `_ENV_OVERRIDES` row and a `.env.example` line but NO `docs/gate_registry.md` row and no registry entry - three of the
  five places - and were UNREGISTERABLE, because their only read site is `_feature_gate("enable_x", ...)`, an idiom the
  Status-enforcing scan did not match, so the scan found no read site and the registry could only have called a live gate `inert`.
  The scan now matches `_feature_gate(`, and both are declared `wired` with a doc row. **Web impact:** additive - five new tool
  names, all returning `DATA_DISABLED` while the gate is off (it is off in `.env`); two existing chains change order (`news_data`,
  `get_insider_transactions`), so the served vendor for those methods can differ from a previous run's.

- 2026-09-20 `(working tree)` - **Phases 3-5 of `docs/design_decision_context.md` built: the conflict ledger renders, the context can expand, the
  challenge pass is closed-vocabulary.** Three gates, all default `False`. **PHASE 3 (§9) - the render had to MOVE.** §9 promotes the
  same-metric disagreements "into the packet", and §13.4 rendered the packet **pre-graph**; but the ledger is a property of the ANALYST
  REPORTS (which do not exist yet) and the verifier that resolves the pairs is a POST-HOC tree pass (`batch --verify`,
  `scripts/report_verify.py`) that never runs inside a run. So the `CONFLICT` row could only ever be a gap. Fix: a `Decision Packet` graph
  NODE at the head of the post-analyst chain; `propagate` keeps only the handoff of the ONE close series onto the declared
  `decision_packet_closes` channel. One node, one render, one `packet_chars`. `report_verifier.report_ledger(state)` applies the verifier's
  own `_basis_registry` + `basis_conflicts` to the reports **in state**, so the packet's ledger and the tree's `conflicts` key agree **by
  construction** (rule 15; a test pins it row for row). `ConflictRow` gained `section`. **Rows print most-actionable-first** - the ledger
  is bounded at 12 and the measured distribution is 199 `basis_difference` / 63 `defect` / 22 `unresolved`, so metric-order truncation
  would routinely hide the one row §10 can act on. **Three states, never conflated:** `unavailable_pre_reports` / a real `0 unresolved` /
  the count line. **`conflict_count` in the card is now real** - Phase 0's `null` reason ("resolved post-hoc ... not in run state") is now
  FALSE, so it reads the same producer, with the per-class breakdown, and stays `null` with a stated reason when the packet gate is off.
  **PHASE 4 (§11) - a CHANNEL, not a longer packet.** `expansion_decision` reads §11's own producers (`independent_agreement`,
  `weighted_consensus`/`should_hold`, the ledger's `unresolved`) rather than deriving its own agreement number. **A missing input is not
  agreement**: no stance sampled counts toward neither. The separate `decision_expansion` key with its own bound (24,000 / 6,000 per
  section) is load-bearing - appending to the packet would make `packet_chars` grow with the research and §7's bound would stop being a
  bound. `context_mode` = `packet` / `packet+expanded` makes the expansion RATE measurable. **PHASE 5 (§10) - the model proposes, the code
  decides.** `strategies/decision_challenge.py`; the site is `portfolio_manager._challenge_hook`, BEFORE `_guardrail_hook` (§16's order).
  All four rules enforced by code, not prompt wording: closed vocabulary; evidence must be a packet row; downgrade-only
  (`decision_guardrail.downgrade_toward_hold`); an UNCERTAINTY row is rejected and only `unresolved` carries ground (b). **Ground (b) is
  material** - an `unresolved` contradiction AND reliance, checked against the decision's own PROSE; a contradiction the decision never
  mentions is RECORDED, not acted on. `ground` is a plain `str`, NOT a `Literal`: a `Literal` makes an invented ground a pydantic
  validation error, which the runner catches as "the call failed" - indistinguishable from an outage, losing the record of what was
  proposed. A failure is NEVER an invalidation, in the SAME key set as an adjudicated outcome. **TWO DEFECTS, both found by running it,
  both proven failing-first by mutation (sha256 `ae775cf4…` restored):** (1) the block scan assumed a block's rows are the INDENTED lines -
  they are not (`conditions  1 declared` prints at column zero), so `_falsifier_rows` returned `[]` for every packet and **ground (a)
  could never be met**; a check that always fails looks strict and is simply broken. (2) ground (c) compared figures as TEXT, so the
  packet's `4.4` vs the decision's `4.40` fired (c) on a decision that invented nothing - the repo had already fixed this class once
  (`_cluster_value_tokens`); now NUMERIC at the same 0.5% tolerance, and scoped to the PROSE (`confidence`/`stop_loss` are the decision's
  own proposals, and checking them would fire (c) on almost every decision). Tests: `test_decision_packet.py` 28 -> 39,
  `test_decision_challenge.py` 21 new; suite 5059 -> **5091 passed / 6 skipped**, 0 failures; `tradingagents/` ruff clean.

- 2026-09-20 `(working tree)` - **Phase 3 UNBLOCKED: the conflict ledger gets a mechanical, provenance-carrying producer.** §9 needed each row
  to carry a `classification`; §13.5 left Phase 3 blocked because the detector's flags were dominated by its own extraction defects. **THE MOVE:
  classify from the typed basis registry, not from the prose scan.** `_basis_registry` already produced a deduped `list[BasisAssertion]` of
  `(metric, value, basis, source)` per report, so the conflict becomes a GROUP BY. That matters for rule 15 - the prose scan and a registry scan
  would otherwise be two independent producers of "the same metric at two values". **SUPPRESSION BECOMES LABELLING:** the three suppression rules
  (`_period_tag`, `_disclosed_pair`, `_UNIT_SCOPED_METRICS`) were each a classification the code computed and then THREW AWAY; they now emit it. A
  suppressed row was invisible; a labelled row is visible, inert and auditable, and §10 reads only `unresolved`.
  `classify_conflict` is arithmetic on provenance, no prose, no model call:
  `≥2 producers -> basis_difference` / `≥2 stated bases -> basis_difference` / `≥2 unit classes -> basis_difference` / `stated beside unstated ->
  unresolved` / `else (one producer, one basis) -> defect`.
  **FOUR PROVENANCE FIXES, each closing a measured gap.** (1) `BasisAssertion.producer` via `_producer_near` - `t1`/`t2` are quoted by
  `get_tranche_plan` AND `get_swing_set` by design, `vrp` is pp in one tool and a variance ratio in another; without the producer every such pair was
  a defect. **166 -> 75.** (2) A parenthesised SHORT-NAME attribution: multiples rows write `(fundamentals)` / `(ratios)`, never `get_fundamentals`,
  so the tool-scope regex could not see it; a parenthesised token is an attribution only when it carries NO digit (so `(2026-03-31)` stays a basis).
  **75 -> 65.** (3) Producer-name normalisation - `get_fundamentals` and `(fundamentals)` are one producer named two ways. **65 -> 67** (the count
  ROSE: it correctly stopped excusing two rows it had been excusing wrongly). (4) `pp` recorded as `percent`, so two unit classes read as two bases.
  **67 -> 63.** **MEASURED over 53 trees, 284 rows: 199 `basis_difference` / 63 `defect` / 22 `unresolved`.** Ten tests, each proven
  **failing-first by mutation** (sha256 restore verified); verifier suite 223 -> 233. **NOT claimed:** 27 of the 63 remaining defects are `atr` at
  different WINDOWS (the basis records only the unit class), so a windowed-basis concept for ATR-like metrics is the largest remaining item; `t1`/`t2`
  contribute 12 more with one side unattributed; a handful are extraction artefacts (`AMZN 'current ratio' 249.26`, `NVDA 'earnings power value' 14`,
  `NVDA 'rsi' 4.14e37`). None is hidden - each is a payload row with its sides printed.

- 2026-09-20 `(working tree)` - **The §9 conflict-ledger dependency checked: the open verifier pairs were NOT classified, and the triage found NO
  two-producer defect.** A `verify_flags.json` conflict row carries exactly three keys - `claim` (free prose), `status`, `reason` - with no
  `classification`, no `metric`, and no source sections; §9's vocabulary (`unresolved`/`basis_difference`/`defect`) appears nowhere in the code.
  **Triage of the five named pairs, each mechanism proven by running the verifier's own extractors:**
  LULU `ev/ebit` 5.50/4.40 = **detector defect** (a header cell naming two metrics - `| P/E / EV/EBIT / EV/EBITDA | 7.68 / 5.50 / 4.40 |` - handed
  the EV/EBITDA leg to EV/EBIT); LULU `scenario dcf base` 173.58/132.5 = **detector defect** (`| Scenario DCF bear/base/bull | 132.5 / 173.58 /
  249.05 |` bound `base` to the BEAR value); JCI `altman z` 2.90/7.2461 = **detector defect** (the Ohlson score read as Altman Z); AMZN `ev/ebit`
  35.02/32.79 = **basis_difference** (the report says so itself: "Both pairs are basis differences to quote with their producers, not one number");
  QCOM `diluted eps` 1.87/5.01 = **basis_difference** (`$1.87 (2026/Q3)` vs `FY2025`). **Not one is a rule-15 two-producer defect.** The verifier
  HAS classification logic - `_period_tag`, `_disclosed_pair`, `_UNIT_SCOPED_METRICS` - but uses it only to SUPPRESS, never to LABEL. So §9's
  `classification` field is the same judgement emitted instead of discarded.
  **Three detector defects, confirmed and fixed on sight.** (1) `_table_cell_pair_value` computed the ordinal from `prefix.count("/")` - a `/` inside
  a LABEL (`P/E`) is not a separator - and used the match's START; fixed by cutting BOTH cells with one separator rule (`_table_legs`), taking the leg
  the match's LAST character occupies (these phrases read `<context> <label>`), and reading that leg's FIRST figure (a leg naming a second metric can
  no longer donate its number). (2) `_period_tag` returns ONE tag per LINE, so two labelled bases on one line got one shared tag; `_period_tag_near`
  binds each figure to the nearest token - and its first version was wrong: it iterated `_PERIOD_TAG_RES` in precedence order and returned the first
  KIND matching anywhere, so a distant `FY2025` beat the adjacent `2026/Q3`. **Distance decides first; precedence is only the tie-break.** A
  `\d{4}/Q[1-4]` spelling was also missing. (3) The disclosed-basis test was **silently inert on the reader path**: `_METRIC_VALUE_READERS` builds
  entries as `(raw, value, None)` - no line - so `if line:` was false for every metric with a reader; `_line_carrying` recovers the line.
  **Effect:** analyst-report conflict rows 70/26 trees -> 30/24. Five regression tests, each proven **failing-first by mutation** (reverting the three
  behaviours fails all five; sha256 restore verified). Verifier suite 223 pass. Full suite 5044 -> **5049 passed, 6 skipped**. **Still open and named:**
  30 survivors include false positives (`AMZN 'current ratio' 249.26` - a price; `NVDA 'rsi' 45.21; 41414141...` - masked digits), and the
  disclosed-basis suppression still fails when a value RECURS on a second line and collects a second tag. That needs a value-to-basis binding these
  line-scoped regexes cannot express. **Phase 3 stays blocked on the detector, now for a measured reason.**

- 2026-09-20 `(working tree)` - **Phase 2 of `docs/design_decision_context.md` is BUILT - the Decision Packet - and it found that §6's packet sketch
  contradicts §16's own architecture.** New `tradingagents/strategies/decision_packet.py`. The graph renders the packet ONCE before the graph into
  `state["decision_packet"]`; the five consumers §6 names (trader, PM, the three risk debators) read the decision channel through
  `decision_packet_or_context`, which is the gate. Gate `enable_decision_packet`, default False, registered in the five places; off ⇒ every consumer
  gets `computed_decision_context` byte-for-byte. **Four findings.**
  (1) **`gate` and `permission` are POST-DECISION facts.** `PASS|WARN|REJECT` is `risk_governor.govern`'s vocabulary and `govern` runs in the graph's
  post-decision fold; `TRADE_ALLOWED` comes from `signal_action.portfolio_action_from_gate`, which derives it FROM that verdict; `BLOCKED` has no
  producer at all (the live vocabulary is `PORTFOLIO_ACTIONS`, seven values). §16 puts the deterministic gates DOWNSTREAM of the decision, so a
  pre-decision packet cannot carry either. The packet prints the pre-decision constraints instead - limits registry, measured book state, liquidity
  verdict, and the regime gate (the one gate readable pre-graph, vocabulary `tradable|high-vol|fast-downtrend|catalyst-window|unknown` - a different
  axis) - and names `permission` `unavailable_pre_decision` with the reason, the D-11 discipline.
  (2) **`DIRECTIONAL DISTRIBUTION` HAS NO VALID PRODUCER.** §6 justified it with "the engines already carry a sign per component"; verified at the
  definition sites, they do not - every engine band table is non-directional (`REGIME_BANDS` = benign/constructive/mixed/stressed/hostile,
  `RISK_BANDS` = low risk/contained/moderate/elevated/high/severe, `NEWS_BANDS` = high-information/informative/mixed/quiet/stale/no-signal), and
  `score_engine.align` maps every component to 0-100 IN THE FAVOURABLE DIRECTION, erasing the sign. No component dict carries a `sign` key. The one
  counter that exists measures the INDEPENDENT STANCES, which §4.4 and acceptance criterion 22 FORBID as evidence. So the row is a NAMED GAP - a
  fabricated distribution would present a diagnostics stream as evidence and a reader could not tell.
  (3) **§8's three counters reduce to one.** `UNCERTAINTY` is built and honest (count + named gaps from `quant_scorecard`'s own `absent` map and each
  engine's own `absent`/`absent_reasons`; an engine whose gate is OFF is NOT a gap - the `DISABLED`/`NA` distinction). The `EVIDENCE` half is the row
  finding 2 rules out. `reporting._run_card_evidence_counts` now reads the same counter via `prompt_metrics.stance_direction_counts` (ONE producer),
  so the card and the packet cannot disagree, and Phase 0's `null` becomes a real count - still `null` when there is NO snapshot.
  (4) **The recorded scorecard is a PROJECTION**: `_run_card_quant_scorecard` drops each engine's `result`, so the card's `trade` entry carries no
  `floor` and no `basis` and a card reader cannot recompute the composite. The live state snapshot does carry them. Not fixed - a WP-12 decision.
  **Three defects in the packet's own first draft, all caught by RUNNING it:** `DECISION PACKET vv1` (doubled version); truncation picked victims by a
  text heuristic that could have dropped the purpose line or a category note (now STRUCTURAL - only rows are droppable); and
  `engine_row_max_chars` was declared in §7's budget and **never enforced** (now enforced by dropping WHOLE CELLS, never cutting a cell in half).
  28 tests in `tests/test_decision_packet.py` (verified by `--collect-only`), plus the
  Phase 0 uncertainty contract strengthened in `tests/test_decision_guardrail.py`. Suite
  5015 -> **5044 passed, 6 skipped** (539 s). ruff clean.
  **Live-verified** on `MSFT_20260920_145644` with both gates on: `run_card.json` carries
  `context_mode="packet"`, `packet_version="v1"`, `packet_truncated=false`, `packet_chars=2796`,
  and `uncertainty_count=10` with ten real named gaps - the field Phase 0 recorded as `null`.
  A prompt-capture run proves the wiring both ways: gate on ⇒ the packet text is in the
  trader's prompt and the compiled string is not; gate off ⇒ the reverse.

- 2026-09-20 `(working tree)` - **Phase 1 of `docs/design_decision_context.md` is BUILT and RUN - and the measurement does NOT support the
  doc's premise.** The experiment: a 2x2 factorial (prose vs packet) x (compact vs large) over 12 real snapshots, 4 arms each, scored on the
  DECISION CATEGORY. Extended `scripts/context_ab.py` as the doc required - no parallel harness; `mcnemar_exact`, `ungrounded_figures`, the
  producers and the report are all reused. **The result:**
  `C1->C2` (volume, prose) flip 0.333, dir->hold 1 vs hold->dir 3, **p=0.625** - the large context is marginally LESS conservative.
  `P1->P2` (volume, packet) flip **0.000** - IDENTICAL ratings in all twelve.
  `C1->P1` (representation, compact) flip 0.583, dir->hold **6** vs 1, p=0.125 - P(no-trade) 0.417 -> **0.833**, confidence 0.652 -> **0.248**,
  ungrounded figures 2/12 -> **9/12**. **There is no measured volume effect to build for, in either representation.** What signal exists is on the
  REPRESENTATION axis, and it points the WRONG way: a structured rendering made the model markedly more conservative and LESS grounded - the
  opposite of what the architecture assumed a bounded packet would do. **n=12 is underpowered; nothing reaches p<0.05** (the representation
  contrast needs ~20-25 snapshots at this effect size). Directional signals, not established findings.
  **Four findings from building the instrument.** (1) **C2 - C1 cannot be a pure volume effect on this evidence**: two C1 constructions were
  measured - the doc's literal "bounded to first/last rows" (chars 70%, bullish facts 50%, figures 56%) and dropping only non-evidential lines
  (chars 95%, bearish facts 87%). Neither reaches 100%. On QCOM `20260920_013202` the evidence is already evidence-dense - 330 metrics, 2,597
  figures, 256 sections in 136,335 chars - and removing every line with no figure or metric buys **5%**. **The volume of this context IS its
  information**; a smaller context means less evidence, which is a content-retention effect by definition. (2) **The verdict needed a second
  condition**: the first draft reported a "context-volume effect" for a C1 that was **TWO CHARACTERS** smaller than C2. A contrast must now both
  retain the evidence AND shrink by >=5%, else it reports NO VOLUME ABLATION AVAILABLE. (3) **The repr error, a third time**: C2 was first built
  with `join(str(r) for r in rendered)` but the render is a list of `{analyst, block}` DICTS, so it joined Python reprs and the metric/section
  counts read **0**. Fixed to `entry["block"]` -> 330 metrics, 256 sections. Same mistake as Phase 0's finding 6, different file, found the same
  way. (4) **THE IDENTITY CHECK WAS OVER-STRICT AND REJECTED 8 OF 12 VALID PAIRS.** `_snapshot_matches` treated a MISSING hash as a mismatch;
  eight snapshots predate the scorecard gate and carry `engine_output_hash: None`, though all four arms had consumed the SAME evidence. The
  invariant requires the snapshot to be the SAME, not RICH. Now three outcomes: match (incl. None == None), mismatch (invalidates), unverifiable
  (kept, counted, reported). **An over-strict invariant is not a safe one** - it discards valid pairs and calls the loss rigour. Re-scoring the
  saved run confirmed all 8 are `match`. **The representation arm is a labelled STAND-IN** (built from the run's own deterministic blocks; no
  budget, no uncertainty vocabulary, no conflict ledger) because Phase 1 runs before the packet exists - a representation effect measured here
  must not be read as a measurement of the packet. 20 tests in `tests/test_decision_factorial.py`.
- 2026-09-20 `(working tree)` - **Phase 0 of `docs/design_decision_context.md` is BUILT - and building it found that the boundary it was meant
  to name did not exist.** The doc's §12.4 insists the telemetry distinguish `llm_output` (the PM model's structured emit, before ANY
  transformation) from `deterministic_postprocess` and `execution`. **`pm_decision` is not that.** `portfolio_manager._result_hook` called
  `_guardrail_hook(result)` FIRST, and the guardrail rewrites `result.rating` and `result.confidence` **in place**; only then did it capture
  `result.model_dump()`. So the state key the entire pipeline reads as "the PM's decision" was the **post-guardrail** object, and no record of the
  model's own emit existed anywhere in a run. That is exactly the corruption §12.4 predicted for "six months from now"; it had already happened.
  The capture now happens before the guardrail and lands in a new **`pm_llm_output`** channel. **Why it matters:** a `HOLD` may be the model's own
  `HOLD` or an `llm_output.rating = "Buy"` plus a REJECT gate, and collapsing the two makes the Phase 1 factorial measure the gates instead of the
  model. **Fails-before proof by MUTATION, not stash:** moving the capture back after `_guardrail_hook` makes `pm_llm_output["rating"]` read
  `"Hold"` where it must read `"Buy"`; the source was restored byte-identical (sha256 checked in the `finally`).
  **New `agents/utils/prompt_metrics.py`** owns the telemetry: per-stage prompt sizes for all seven LLM nodes (four analysts, trader, RM, PM), the
  three decision layers, `context_mode`/`packet_version`/`packet_truncated`, directional evidence counts, and the §12.3 snapshot identity hashes
  (`data_snapshot_hash` / `engine_output_hash` / `model_parameters_hash`). It assembles into an ADDITIVE `decision_context` key in `run_card.json`.
  **Two LangGraph traps avoided.** (1) `prompt_metrics` needs an **additive reducer** - `Annotated[dict, merge_prompt_metrics]` - because every node
  returns its own one-stage fragment and the default last-write-wins would keep only the final stage. (2) Both new channels must be declared on
  `AgentState`, or LangGraph silently drops them. **Three honest nulls, never zeros:** `uncertainty_count` (Phase 2 owns the vocabulary) and
  `conflict_count` (the verifier resolves same-metric pairs post-hoc, they are not in run state) are `null` with a `_reason`; a `0` would read as
  "none present" when the truth is "nothing counted it". The three counts that CAN be taken are taken over the structured independent stances, and
  `counted_sources` travels with them so nobody reads five stances as the whole decision context. **`PortfolioDecision` has no `direction` field** -
  the model emits `rating` and `confidence` only - so `llm_output.direction` is a deterministic PROJECTION of the rating, computed in the same
  expression that records it so the two cannot diverge. **Zero behaviour change:** no gate, and nothing reads a telemetry value back into a prompt
  or a decision. Three pre-existing exact-set assertions on node return channels (`test_dead_state_dedupe.py` x2, `test_analyst_etf_routing.py`)
  were updated for the new **declared** channel - the real invariant, "no node writes an UNDECLARED channel", is still enforced by the subset
  assertion above each. 7 tests added. **4988 passed, 6 skipped** (baseline 4981 + 7).
- 2026-09-18 `(working tree)` - **P0+P1 of both vendor-surface designs are built**, behind two new default-off gates. **`enable_moomoo_snapshot`**:
  `moomoo.get_kl_quota_moomoo` / `kl_quota_remaining_moomoo` (the live K-line quota, read as a screener pre-flight that warns and refuses cleanly at
  zero) and `moomoo.get_market_snapshot_moomoo` / `_batched_snapshot` (142 columns for a whole symbol list in one call; live 122 requested -> 120
  returned, 2 dropped, 0 failed). **The all-or-nothing endpoint is survived by a bisect** - `_batched_snapshot` chunks, drops the symbol the refusal
  NAMES, and retries; bounded, so an all-bad chunk terminates. **The design's per-symbol pre-validation is deliberately NOT built**: it is one
  `get_stock_basicinfo` call per name, i.e. N calls to save N calls - the bisect finds the same symbols for one retry each and names every one.
  `None` is not `0` for the quota (unreadable != exhausted). **`enable_analyst_estimates`**: `yfinance_sector.fetch_estimate_trend` supplies the
  five levels `eps_trend` carries, so `analyst_revisions.estimate_change_index` - which documented itself as permanently `unavailable` because
  "the engine has ... never a 3-4 quarter estimate history" and whose only `levels=` caller was a test - is now MEASURED. **The 90-day window is
  NOT four quarters**: `estimate_change_index`/`revision_index` gained an optional `level_basis` so the basis line cannot claim MSCI's series;
  the default is unchanged (byte-identical for existing callers) and a test asserts the index is independent of the label. New `RevEC` watchlist
  column. **Also fixed on sight**: `cell(v, fmt)` uses `fmt.format(v)`, so the printf specs `"%+d"`/`"%+.1f"` on the watchlist row rendered as
  LITERAL TEXT - and because that literal is non-empty the column survived the empty-column pruning, so an unmeasured column looked measured. Both
  are now `{:+d}`/`{:+.1f}`. Tests: `test_moomoo_snapshot.py` (14), `test_analyst_estimates_wiring.py` (12), `test_value_screener.py` +2.
- 2026-09-18 `(working tree)` - **The unused finnhub and yfinance surfaces are enumerated, and one finding closes a leg that could never fire.** New doc
  `docs/design_finnhub_yfinance_unused_surface.md`. `finnhub.Client` has 117 methods (repo calls 9); `yfinance.Ticker` has 54 properties + 44 methods (~23 attrs
  used). Live-probed: 61 finnhub calls, 32 yfinance calls. **Headline: `yfinance.Ticker.eps_trend` supplies the five-level estimate series
  `analyst_revisions.estimate_change_index` documents itself as never having** - it needs `len(weights)+1 = 5` levels (`DEFAULT_ESTIMATE_WEIGHTS=(9,7,5,3)`,
  `analyst_revisions.py:43`), and `revision_index(history, levels=None, ...)` (`:279`) defaults `levels=None` with **the only caller passing a value being a
  test**, so the leg is structurally `unavailable` in production. `eps_trend` returns `current`/`7daysAgo`/`30daysAgo`/`60daysAgo`/`90daysAgo`;
  `eps_revisions` gives the direct up/down counts behind the `upgrades_downgrades` proxy. **finnhub free tier: 12 of 61 work, 48 return 403** (all listed in
  Appendix A) - working ones include `financials_reported`, `filings`, `fda_calendar`, `company_earnings`, `market_holiday` (`tradingHour 09:30-13:00` on
  half-days), `country` (249 with `equityRiskPremium`). **Caveats**: `fda_calendar` is advisory-committee meetings, NOT PDUFA dates (complements pdufa.bio);
  and `company_earnings` WORKS while the recorded note names `earnings-surprises` as 403 - different routes. **Rule 15 blocks two adoptions**:
  `trailing_twelve_months` (`statement_parsing.py:1270`) says *"One producer for a trailing-twelve-month total"* so yfinance `ttm_*` is cross-check only, and
  finnhub `financials_reported` must not sit beside `sec_edgar`. Plan P0-P5 behind the new `enable_analyst_estimates`, gate off byte-identical.
- 2026-09-18 `(working tree)` - **The unused moomoo surface is enumerated (103 data methods), and four are worth taking.** New doc
  `docs/design_moomoo_unused_api_surface.md`. `OpenQuoteContext` exposes 166 public callables; this repo calls 31; 32 are lifecycle. The used set was
  extracted from the tree (every `ctx.<name>` across the 78 files mentioning moomoo), not from memory. **Headline: `get_market_snapshot(code_list)`
  returns 142 columns for a whole batch in one call** - valuation block, pre/after/overnight session families, short-interest fields, ETF NAV/premium,
  option greeks - verified live at 50 and 120 symbols. **The deciding constraint is that the batch call is all-or-nothing**: one unknown/renamed/OTC
  symbol fails the whole call naming only the first offender (hit live: `Unknown stock. SQ`; `US OTC market quote is not available for SSLZY`).
  **Analytical find: batch IV rank / IV percentile / HV** (`get_option_underlying_overview`, live AAPL `iv_rank 33.837`) plus a 251-row IV/HV series -
  the variance risk premium recorded as "asserted, not quantified". **Also**: `get_valuation_detail` (valuation percentile + peer distribution),
  `get_research_morningstar_report` (independent fair value 290.0 vs AAPL 336.13), `get_rating_change` (replaces the yfinance proxy),
  `get_history_kl_quota` (the K-line bottleneck read). **Tier 2 is gated, not absent**: `get_order_book`/`get_rt_ticker`/`get_rt_data` need a
  `subscribe` call. **`get_corporate_actions_buybacks` is HK/A-share only** - confirms the existing correct claim at `moomoo.py:1911`. Plan is P0-P5
  behind a new `enable_moomoo_snapshot`, gate off byte-identical. **One open question blocks the valuation fields**: they overlap `statement_parsing`
  and the SEC XBRL leg, and master rule 15 forbids two contributors - measure the disagreement on 20 names before choosing.
- 2026-09-18 `(working tree)` - **The Heat List IS available - `get_hot_list` (`Qot_GetHotList`) - and the repo's "not exposed by any moomoo API"
  claim was false in five places.** Found by asking whether moomoo could supply the attention legs a screener factor would need, instead of trusting the
  tree's own claim. `OpenQuoteContext.get_hot_list(market, sort_field, sort_dir, count, offset, filter_list)` returns per name `search_heat`, `trade_heat`,
  `news_heat` and `average_heat`, each with a `*_heat_change` delta, plus `news_type`/`news_title`/`news_url`. **Verified live against OpenD 2026-09-18:** US
  `all_count` 9,072, HK 3,030; 200 rows per call with `offset` paging; `sort_field` re-orders by any of the four; `HotListFilter(HotListIndicatorType.
  MARKET_CAP, interval_min=...)` is a server-side cap filter (9,072 -> 1,259 at >= $10B); raw scale 0-10,000,000, so the app's 0-100 display is that /
  100,000. **`average_heat` is the equal-weighted mean of the three** - verified over 400 rows to within integer rounding (max |delta| = 2/3) - so there is
  **no proprietary weight vector to reverse-engineer**, and **no decay parameter exists**: the request carries exactly `market`, `sortField`, `sortDir`,
  `offset`, `count`, `filterList`. **Corrected in five places** (`moomoo.py::get_hot_movers_moomoo`'s docstring, `value_screener.py`'s `--universe` help and
  its `heat-proxy` comment, `README.md`, the 2026-08 CHANGELOG entry - amended in place with a `[CORRECTED 2026-09-18]` tag, never rewritten - and
  `trading_web/frontend/src/screenerSources.js`). **No behaviour changed**: `heat-proxy` is a *separate signal* (price movement), not a stand-in for an
  unavailable one, and wiring the Heat List into a screener factor is a separate decision not taken here.
- 2026-09-18 `(working tree)` - **SIMO's panel market cap was 4x too high: an ADS price multiplied by an ordinary share count.** Found by
  checking a number that looked wrong instead of trusting it. The live panel read `price_to_earnings=277.28`, `price_to_book=40.93`,
  `altman_z=54.15`. Both legs are individually correct - the price leg supplies a real close of `253.30` (2026-09-17, from a continuous
  series back to 65.88 in 2021), and the SEC leg's net income $122.635M / EPS $0.91 / 134,244,840 cover-page shares are internally
  consistent. The **join** is the defect: `market_cap = close x shares_outstanding` multiplies a per-**ADS** price by an **ordinary** share
  count. SIMO files 20-F and its ADS represents **4 ordinary shares**, so the panel derived **$34.0B** against a real **$8.1-8.6B**.
  **Fixed by refusing to guess:** `sec_edgar.annual_facts` now returns `foreign_private_issuer` (True when the cover page came from a
  20-F/40-F), `canonical_fin_from_sec` carries it, and `build_panel` withholds the derived market cap and records `GAP_FPI_MARKET_CAP`.
  EDGAR does not carry the ADS ratio, so no honest derivation exists, and a wrong market cap poisons P/E, P/B, EV/EBIT, earnings yield,
  FCF yield and Altman Z's X4. **Fails before, passes after:** the panel test failed pre-fix with `price_to_earnings=97687062.49`; the
  reader test with the flag `False`. **A named gap, not a permanent loss** - an ADS-ratio source would let the derivation resume.
- 2026-09-18 `(working tree)` - **D-11 FIXED: the owner decided it the same day, and the resolution went the other way from the
  sequence the design set had on record.** The owner chose **§6.4 row 2 - the gate reads its own explicit argument** - and was
  explicit that this is **not** a licence to move the snapshot or to make the printed context the sole consumer: the distinction
  is **decision semantics vs observability**. `_compiled_decision_context` runs *before* `graph.invoke`, so it cannot consume
  `strategy_overlays` as though those overlays existed; moving the snapshot earlier would mean moving the production of the event
  information earlier too (a graph-ordering change), and making the context the only consumer would turn an observability
  artifact into the source of truth. **The reporting defect is separate and real** - `catalyst_window=False` was a false
  assertion, not an NA. **Built:** `regime.regime_gate_read`'s axis is now **tri-state** (`bool | None = None`); `None` = the
  caller supplied no event fact, reported **unmeasured**, never coerced to `False`, with the trailer now reading "volatility
  contained + no fast downtrend (catalyst window not measured)". The context supplies none and prints
  `catalyst_window=unavailable_pre_graph`; `value_dip_tools.get_value_dip_setup` - the same defect one layer down, passing an
  explicit `False` it never measured - now supplies none too. **The veto is not reinstated anywhere**, so the 2026-09-17
  `RegimeScore -> EventScore` boundary stands. **Failing-first:** against the pre-fix code both new tests
  (`tests/test_strategies_regime.py`) reproduce the exact false string from the corpus -
  `catalyst_window=False reasons=volatility contained + no fast downtrend + no catalyst`. The ground-truth parser is unaffected
  (`structured_debate._KEY_VALUE_RE` requires a numeric value, so `unavailable_pre_graph` registers no key, as `False` did not).
  Recorded in `ResearchLayerWiring.md` §6.4/§6.6, master §3.5 D-11, `EventScore.md` D3.
- 2026-09-18 `(working tree)` - **Closed on sight in the same pass: a dead constant, a stale docstring, and the second caller
  asserting the same false catalyst measurement.** (1) `sec_edgar._REFERENCE_TAGS` was declared with a docstring pointing at
  `annual_facts` and read by **nothing** - the reference-year rule lives with the canonical assembly at
  `scripts/score_panel.py::SEC_REFERENCE_LABELS`, which reads assembled labels rather than raw tags. Removed, with a note
  recording where the rule actually lives and not to re-add a tuple. (2) `statement_parsing.annual_series`'s docstring described
  only the vendor stacking path; it now names its SEC XBRL sibling `sec_annual_series`, the per-key longest-series merge rule
  (never a splice), and why a non-USD filer skips the SEC leg. (3) `value_dip_tools.get_value_dip_setup` passed
  `catalyst_window=False` explicitly - the D-11 defect one layer down; see the entry above.
- 2026-09-18 `(working tree)` - **The four WP-12 findings resolved by category** (owner's framing: implementation defects vs
  parser-contract defects vs semantic-state defects vs test-assumption defects). **(1) D-11 stays OPEN as a contract decision
  with a fixed sequence** - establish where the authoritative catalyst-window value belongs, then whether it stays an
  `EventScore` input/output, and ONLY THEN change the ordering/compilation; the hard constraint is that no step may move the
  decided `RegimeScore -> EventScore` boundary by accident (a naive timing fix would quietly restore the regime veto). The
  printed `catalyst_window=False` stays until then (`ResearchLayerWiring.md` §6.4). **[SUPERSEDED 2026-09-18 - the owner decided it the same day and the line moved *as* that decision, not as a side effect; see the D-11 FIXED entry above.]** **(2) The three parser traps are frozen as
  tests** in the new `tests/test_scorecard_contracts.py`, which pins the PARSER's real behaviour rather than our formatting: a
  non-numeric pair before a numeric one is swallowed; a leading `+` registers no key at all; an ISO date registers as its year.
  **(3) The three engine states are now NAMED** - `quant_scorecard.engine_state` returns `DISABLED` / `MEASURED` / `NA`, every
  entry carries it, the card reports it, and `scorecard_status` also returns `measured`/`unmeasured`. Conflating DISABLED with
  NA is what would let an engine that FAILED TO MEASURE vanish from the count and make a partial scorecard look complete.
  **(4) Monotonicity is now DEMONSTRATED, not presumed** - a declared non-monotonic input must show a raw value aligning lower
  than a smaller raw value, checked against the producer's own ramp; writing it caught a second assumption of the same kind
  (the sweep covered 0..100 but Williams %R lives on -100..0), so it now sweeps both conventions and fails loudly on a flat
  curve. `tests/test_scorecard_contracts.py` new (9); 187 passed across the WP-12 test files.
- 2026-09-18 `(working tree)` - **WP-12 `P12-10` + `P12-12` landed: level 2 in the report, and the non-monotonic mapping as
  evidence.** Report section **`V. Engine score detail`** renders each engine's categories beside the measurements they came from,
  with their weights, so the composite can be RECOMPUTED rather than trusted (no new producer; gated-off engines are skipped, an
  enabled-but-unmeasurable one is `NA` with its reason). **§4.5's triple** now prints at BOTH levels - `rsi=82 rsi_aligned=45
  mapping=producer-defined non-monotonic band` - because `align` maps eight inputs through a producer-defined ramp and a high raw
  value can align low; a monotonic component prints `adx=25 -> 40` and no mapping note. Level 3 is the leaf's own text
  (`_render_technical_score`), so this is a TOOL-CARD change: the web contract tests were re-run explicitly (`test_doc_claims.py` +
  `test_engine_contract.py` 15 passed; engine doc/claim/render selection 193 passed). `run_card.json`'s `technical_score` block
  gains the additive `non_monotonic` key. 207 passed across the WP-12 test files.
- 2026-09-18 `(working tree)` - **WP-12 `P12-9` landed: the quant/LLM risk-disagreement detector (§5's weak form).** New
  `strategies/score_disagreement.py` - a deterministic POST-debate check over material the run already produced: `RiskScore`'s
  band from the snapshot against the risk debate's own words. **No new producer.** It **never changes anything** (the flag carries
  no rating/size/score/gate - asserted). The LLM side is read with **RiskScore's own band vocabulary**, and the counts are
  returned so the classification is checkable; the **structured path is preferred when it ran** (§5's "or", not both -
  concatenating two disagreeing transcripts would tie the classifier). **Only opposite stances are a contradiction** (a
  `moderate` on either side is a difference of degree); an unreadable side produces NO flag with its reason recorded, because a
  guess would be a manufactured disagreement. Two surfaces: one additive `run_card.json` key `risk_disagreement`, and report
  section **IVb** emitted only when the flag fires. Both gated by `enable_quant_scorecard`. `tests/test_score_disagreement.py`
  new (15); 120 passed across it, `test_reporting.py`, `test_quant_scorecard.py`, `test_score_history.py`.
- 2026-09-18 `(working tree)` - **WP-12 `P12-8` landed: the score-history store and the held deltas.** New
  `strategies/score_history.py` - one JSONL row per scored run date under `<data_cache_dir>/score_history/<TICKER>.jsonl`,
  each row carrying the composite, its coverage and **the weight vector it scored under**. One row per date: re-running a date
  does not rewrite history. **The rule is enforced, not documented** (§9 D2): *no validated vector -> no delta -> no movement* -
  a prior row must exist, under the **same** vector, and the vector must be **validated**; the reason is vector validity, not
  `RESEARCH_ONLY`. Every withheld case names its reason. `NA` rules: no prior row means **no delta keys at all**, never a zero.
  **Wiring:** the graph reads the prior row THEN records this run's observation (read-then-write, so a run can never be its own
  prior); the producer stays pure and the whole block is inside the `enable_quant_scorecard` gate. **A third parser trap found in
  §4.3's own example:** `trade_delta=+3.55` **never registers** (the number pattern is `-?\d+`, so `+` fails the match) and
  `trade_prev_date=2026-09-11` registers as `trade_prev_date = 2026` - a year under a name that reads like a metric. The example
  is corrected; the sign is carried by the absence of `-`, and the date is parenthesised so it yields no key. `tests/test_score_history.py`
  new (20); 156 passed across it, `test_quant_scorecard.py`, `test_trade_score.py`, `test_reporting.py`.
- 2026-09-18 `(working tree)` - **WP-12 `P12-11` + the three-surface verification case landed.** `scorecard_basis` is an ADDITIVE
  field on the card's `quant_scorecard` key (§9 D3: a field `basis`'s consumer still reads is `basis`, so the scorecard's
  explanation gets its own name and home; `trade_score`'s shipped `basis` and its rendered text are untouched, and the test
  asserts the frozen wording is smuggled into neither the new field nor the new block). **The verification case the design adds
  to plan §11.3 is now a test:** one run, three surfaces - the rendered block (what `IVa` prints and the debate reads), the card
  key, and the leaf's rendered text - all carrying the snapshot's composite, with the card's per-engine map equal to the leaf's
  input value-for-value. **A fixture bug worth recording:** the render fixture hardcoded a composite (`67.925`) inconsistent with
  its own drivers (which imply `76.75`) - exactly what the real producer never does - which made the three-surface test unable to
  mean anything; the fixture now computes the composite from the drivers unless a test passes one explicitly. 154 passed across
  `test_quant_scorecard.py`, `test_trade_score.py`, `test_reporting.py`, `test_structured_agent_prompts.py`.
- 2026-09-18 `(working tree)` - **WP-12 `P12-6` + `P12-7` landed: the card key and §4.6's explicit status.** `enable_quant_scorecard`
  (default off) governs the scorecard SURFACE only; the engine gates decide what populates it. With the gate on `run_card.json`
  gains exactly one key, `quant_scorecard`, carrying **the same rendered block the debate read** plus each engine's
  `score`/`coverage`/`band`/`enabled`/`reason` - so "the prompt's number is the card's number" is checkable in the artifact. Gate
  off: the key is absent, not empty. **§4.6's three axes are printed:** `Scorecard status: DISABLED|PARTIAL|COMPLETE - enabled:
  ...; disabled: ...`, `Vector status:`, `Movement:`. **`COMPLETE` requires every engine gate on AND every engine measured** - a
  scorecard with three engines switched off is `PARTIAL`, which is what stops a half-configured run reading as a whole one. Vector
  status is the composite's OWN status word (one producer): `trade_score` emits `RESEARCH_ONLY`/`VALIDATED`/`PRODUCTION`, and
  §4.6's `ACTIVE` names the promoted rung. `Movement: UNAVAILABLE` is the honest default (no validated vector -> no delta -> no
  movement); `P12-8` adds the store. The status lines are digit-free by construction, for the same reason the block's ordering
  rule exists. 90 passed, including §9.3's invariant in its strong form: adding the block leaves everything after it byte-identical
  to the gate-off context.
- 2026-09-18 `(working tree)` - **WP-12 `P12-5` / D-8 FIXED: one vector, one composite, on both surfaces.** `_trade_score_engines`
  measured all four engines unconditionally while `_run_card_trade_score` read only the sibling card blocks (present only when
  that engine's gate is on), so with `enable_trade_score` on and `enable_risk_score` off the leaf applied the owner's `K=0.20` to
  a risk score the card never saw. **Executed against the pre-`P12-5` assembly reconstructed from git:** leaf **`84.55`** (risk
  `74.0`, gate off) vs card **`87.19`**; both **`87.19`** after. **The fix is §3.4's rule applied by every reader:** an engine
  contributes iff its own gate is on, and both readers take their four values from the run's snapshot via the new
  `quant_scorecard.engine_scores`. The card reads the run's own snapshot from state (`_run_card_trade_score(card, cfg,
  final_state)`) and falls back to the sibling blocks only for a tree written without one - a fallback, never a second
  contributor. **Fails-before test:** `test_the_leaf_and_the_card_print_one_composite_when_a_sub_gate_is_off` asserts
  `leaf["risk"] is None` (it was `74.0`). Three tests that pinned the old gate-ignoring behaviour now enable the gates, so they
  exercise the exception path instead of passing because nothing was called. 367 passed across `test_trade_score.py`,
  `test_quant_scorecard.py`, `test_reporting.py` and the engine suites.
- 2026-09-18 `(working tree)` - **WP-12 `P12-1`-`P12-3` landed: one score snapshot, its state channel, and the block.** All gated by
  the new `enable_quant_scorecard` (**default off**, `default_config.py`, `_ENV_OVERRIDES` row and `.env.example` row added), so
  gate-off stays byte-identical to a pre-scorecard tree. **`P12-1`**: `strategies/quant_scorecard.py::quant_scorecard(ticker,
  trade_date, cfg, *, catalyst_snapshot=None)` - the ONE producer for the engines on the research surface. Every engine is read
  through its own public entry point with the run's date and its result returned **verbatim**; the module computes nothing
  (no alignment, no re-weighting, no substitution). Each entry carries `enabled` (gate on?) separately from `score` (did it
  measure?), because a gated-off engine is NOT part of the scorecard while an enabled engine that cannot measure is ABSENT
  EVIDENCE - the renderer and §4.6's status both need the distinction. **`P12-2`**: `quant_scorecard` declared on `AgentState`
  and built in `_run_graph` before `_compiled_decision_context`; the undeclared-channel trap is tested by a real `StateGraph`
  round trip. **`P12-3`**: `format_quant_scorecard` renders the §4.1 block and `_compiled_decision_context` PREPENDS it
  (`structured_debate` bounds the context to 3000 chars, so a tail block can be truncated away). **A parser trap found and
  fixed:** §4.1's own example line parses to the key `research_only_trade_coverage` - `_parse_key_value_lines` is
  case-insensitive and its key class admits spaces - so `trade_coverage` never registers. Rule now encoded: a non-numeric
  `key=value` goes LAST on its line, digit-free. Verified live: the real context returns the block first (460 chars),
  `ground_truth_from_state` recovers all ten keys at exact values (`trade_score=67.925`), and a state with no snapshot contains
  no block. `tests/test_quant_scorecard.py` new, 27 tests.
- 2026-09-18 `(working tree)` - **D-11: the compiled context's `catalyst_window` can never be `True` - and the `2c05701` "FIXED"
  claim for defect 16 is wrong.** Found while building WP-12, by executing the path instead of reading the ledger.
  `_compiled_decision_context` is called with `init_agent_state` **before** `graph.invoke` (`graph/trading_graph.py:645-647`),
  and `create_initial_state` sets no `strategy_overlays` (`graph/propagation.py`); the only writer is
  `overlays.apply_overlay_to_state` (`overlays.py:178`), called from `_apply_strategy_overlays` **after** the graph (`:686`).
  So `cat_snap` at `trading_graph.py:1275` is always `None` and the line always prints `catalyst_window=False` - a positive
  assertion, not an NA. **Measured:** 160 persisted runs carry `strategy_overlays`; **15** hold a snapshot whose own reader
  (`pre_market.catalyst_window_read`) says the window is **active** (`scale` 0.25/0.6); all **19** printed
  `catalyst_window=` occurrences read `False`; on NFLX 2026-09-15 the context printed `verdict=tradable pass=True
  reasons=['...no catalyst']` where the snapshot implies `verdict=catalyst-window pass=False reasons=['catalyst window open']`.
  **[SUPERSEDED 2026-09-18 - the owner decided it the same day; see the D-11 FIXED entry above.]** **Recorded, not unilaterally fixed:** reviving the veto re-introduces the event read into `RegimeScore`, which the owner's
  2026-09-17 decision moved to `EventScore`; removing the flag or printing `unavailable` both change a shipped context
  string (forbidden as a side effect by §9 D3). Corrected in the same pass: master ledger §3.2 framing + defect 16's row,
  `EventScore.md` D3, and the entry (16) below - which also claimed `regime.py` declares `catalyst_window: bool | None =
  None` when it still declares `bool = False` (`regime.py:252`). Earlier claims kept and tagged, never deleted.
- 2026-09-18 `(working tree)` - **`WP-12` enumerated into a work list, which found a third stale claim on this seam.** The build order in
  `docs/scores/ResearchLayerWiring.md` §7 is now the tracked work list (14 open, 2 blocked): `P12-1` .. `P12-11` verbatim, plus the two
  acceptance cases §7's Verification paragraph adds. Enumerating it exposed a requirement with **no build item**: **§4.2 claimed *"Level 3
  already exists and needs no work"***, while §4.5 requires the non-monotonic `raw`/`aligned` evidence triple at **levels 2 and 3**. The
  level-3 renderer does exist (`_render_technical_score` at `agents/utils/analysis_tools.py:5046`) but prints categories, bands, weights
  and coverage only; the producer already carries the pair (`strategies/technical_score.py:319-327` returns
  `{raw, aligned, direction, category, producer}` per component), so the work is **rendering only** - it had simply never been given a
  row. Corrected in §4.2 with the anchors, recorded as the third entry in §6.1 (the same D-6 failure shape: a stale claim hiding a
  wire), and given the row it was missing - **`P12-12`**, acceptance *a level-3 line for a non-monotonic component reads
  `rsi=82 rsi_aligned=45 mapping=producer-defined non-monotonic band`; a monotonic component prints no mapping note*. Docs only; no
  code or test changed, so the engine suite was not re-run for this pass (the doc-claim and engine-contract tests were).
- 2026-09-19 `(working tree)` - **The engine ownership map: one table decides where a score appears.**
  Two defects, found by inspecting a live batch, closed together. (1) **`get_technical_score` was bound to the
  FUNDAMENTALS analyst** - the market analyst is the price/trend/momentum domain, so the agent receiving the tool
  did not own the domain it represents, and the TechnicalScore landed in the wrong report. Regime and risk were
  bound to market and `trade` to fundamentals, though all three are report-level. (2)
  **`repro_check._config_hash` listed all eight engine gates but not `enable_quant_scorecard`**, so flipping the
  master gate changed what a run emitted without moving the hash - the claim `same hash => same effective inputs`
  did not hold for the gate governing whether anything renders. **The fix is one table**:
  `quant_scorecard.ENGINE_SECTIONS` maps engine -> analyst section (`fundamental`->fundamentals,
  `technical`->market, `sentiment`->sentiment, `news`->news, `event`->news, `regime`/`risk`/`trade`->`None` =
  report-level **by decision, not omission**), and **two surfaces are derived from it rather than restated**: the
  tool binding (`toolsets.engine_score_tools`) and the prompt fragment (`report_hygiene.engine_score_block`).
  **The prompt gap was the real one**: the leaves were bound but **no analyst prompt named any of them** - zero
  mentions across all four files - so a score reaching a report was pure model discretion. **The result is now
  SUPPLIED, not offered**: `engine_score_block` pre-computes the owned engines and inlines them, because *"the
  model may interpret an engine result, but does not decide whether or where the authoritative engine result
  appears"* - and because the **sentiment analyst binds no tools at all** (its prompt carries
  `NO_EXTERNAL_TOOLS`), supplying the text is the ONLY route that reaches that report; a "call
  `get_sentiment_score`" instruction there would invite a hallucinated call. Gate-off prompts stay byte-identical
  (empty block) and gate-off toolsets bind zero score leaves. 11 tests; **five mutations, all failing-first**,
  then byte-identical restore across three source files.
- 2026-09-19 `(working tree)` - **The yfinance analyst-ratings leg raised on every call - three defects in one
  function.** Same live batch. `get_analyst_ratings` failed on **both** vendors and the yfinance failure was an
  `AttributeError`, not an entitlement error - the tell. (1) **`analyst_price_targets` is a dict and the code read
  it as a DataFrame**; the vendor's own signature is `def get_analyst_price_targets(self) -> dict:` with the
  docstring *"Keys: current low high mean median"* (`yfinance/base.py:317`), so `.empty`/`.iloc[-1]` raised
  `'dict' object has no attribute 'empty'` **on every call** - the leg was dead, and with Finnhub 403 on this tool
  the whole leaf had **no working vendor**. (2) **The recommendation columns were wrong**: 1.5.2 uses
  `strongBuy/buy/hold/sell/strongSell`, there is no `underperform`, so the **strong-sell count was silently
  dropped**; a `numberOfAnalystOpinions` lookup read a key the vendor does not publish. (3)
  **`recommendations_summary` is newest-first** (`0m,-1m,-2m,-3m`) so `iloc[-1]` read the **three-month-old**
  consensus and labelled it *"latest period"*; it now selects `0m` and prints the period used. **The test mocked
  shapes the vendor never produces** - a one-row `_recs_df` with an invented `underperform` column and no `period`,
  and a `_targets_df` **DataFrame** where the vendor returns a dict - which is why all three survived; the
  fixtures now carry the measured shapes and the test asserts the `0m` row (`hold: 3`, not the `-3m` `6`). Three
  mutations, all failing-first with the exact expected errors, then byte-identical restore. Live: QCOM 0m
  strongBuy 2 / buy 9 / hold 23 / sell 1 / strongSell 2, mean PT 194.13; NVDA mean PT 327.70; APP mean PT 501.94.
  **Class: a parser-contract defect plus a test-assumption defect** - the test agreed with the code and neither
  agreed with the vendor.
- 2026-09-19 `(working tree)` - **The net-debt identity check read a correct report as a 35% contradiction.**
  Found by running a live 4-symbol batch (NVDA QCOM SMCI APP, shallow, 4 workers) and reading the resulting
  `run_card.json` - QCOM carried an `analyst_consistency` `INTERNAL_CONFLICT` that no amount of reading the
  verifier would have surfaced. `report_verifier._net_debt_identity` paired a report's quoted net figure against
  **cash + short-term investments** and nothing else, but **a vendor's "Net Debt" row is normally on the OTHER
  basis - cash and cash equivalents alone**. QCOM 2026-06-30 fundamentals.md prints both on one line and the
  arithmetic is exact: `15,270,000,000 - 4,533,000,000 = 10,737,000,000`; the checker used
  `Cash + ST Investments 8,304,000,000`, got 6,966, and flagged a **true** report at 35% - while the report was
  itself *disclosing* the basis difference, which is what the fundamentals prompt explicitly asks it to do
  (`fundamentals_analyst.py:255` NET-DEBT BASIS). **The check now resolves the net line against every cash basis
  the report prints and flags only when it resolves from none**, naming the bases tried in the claim and reason.
  **The pinned NVDA 2026-09-12 defect is untouched** - that report prints only cash+ST investments, so it has one
  basis and still flags (its own test, unchanged). Two regression tests, **both proven failing-first by mutation**
  (dropping the second basis; accepting a net line that resolves from neither). 203 passed in
  `tests/test_report_verify.py`. **Class: a test-assumption defect in a checker, not a producer defect** - the
  numbers were right on both sides; the checker assumed one basis was the only one.
- 2026-09-19 `(working tree)` - **EODHD P0 built: TIPS real yields + the single producer of the inflation
  expectation.** Gate `enable_eodhd_rates`, default off. `dataflows/eodhd.real_yield_points_eodhd` /
  `::get_real_yield_rates_eodhd` (895 rows / 179 dates, tenors 5Y-30Y) and `::inflation_expectation_eodhd`
  (the ONE producer of `nominal - real`, carrying both legs' dates, the gap and the basis). **Nothing read a
  real yield before this**, while `dcf.wacc_from_beta:28` already consumed a nominal 10y and *assumed*
  `erp = 0.05`; measured live at 2026-09-17: 5Y 2.32 / 7Y 2.34 / 10Y 2.33 / 20Y 2.45 / 30Y 2.25.
  **Three corrections the build forced, each measured:** (1) **`year` is not a parameter this endpoint has** -
  the vendor ignores *every* query param (`year`, `filter[date]`, `filter[tenor]`, `from`/`to` all returned the
  identical 895-row body), so the design's `(tenor=None, year=None)` sketch would have shipped a parameter that
  **silently did nothing**; dropped, filtering is client-side. (2) The pairing needed a **structured** nominal
  leg, so `federal_reserve.treasury_curve_points` now performs the parse and `get_treasury_curve` renders **from
  it** - one producer, two presentations, byte-identical output (a second parser would have been a second
  producer for the same read). (3) **The first consumer was wrong twice and only running it showed that** - the
  screener called the pairing six times, each re-reading both whole-surface legs (twelve reads where two
  suffice, 158 s), and printed the whole 179-row series into the report head. Fixed via pre-fetched legs
  (`real_points=` / `nominal_curve=`, so the subtraction still happens in exactly one place) and
  `tail=N` on the renderer (60 s, 10 rows). **The legs are date-matched in production only because the
  screener passes `--date`**; with no date, nominal reads 2026-09-18 against real 2026-09-17 and `aligned=False`
  says so. **`dcf.wacc_from_beta` still carries `erp = 0.05`** - P0 makes the premium measurable; promoting it
  into the valuation is a decision contract, not a defect. 20 tests; **seven behaviour mutations each turn their
  test red**, then byte-identical restore.
- 2026-09-19 `(working tree)` - **The unused EODHD surface is enumerated, and the supplied 68-endpoint catalog was
  corrected against the live key.** `docs/design_eodhd_unused_surface.md` (new; docs index updated). **Two premise
  corrections first: EODHD is NOT a removed vendor** - the repo calls 8 of its paths today, all returning 200 (the
  earlier "EODHD leg removed" note referred only to `score_panel.py --exchange`); and **the catalog is materially wrong
  about reachability** - probed live across five rounds (~100 URLs incl. path variants), the 68 split into **9
  reachable-and-unused, 20 plan-gated (403), ~9 not found**. **The `/ust/*` Treasury family is not in the catalog as a
  family and is fully open** (found by guessing paths: real-yield 895 rows, bill 1,253, long-term 537, yield 2,506),
  while the catalog's own `GBOND` and `MONEY` are **both 403**. **The rule this leaves: probe path variants, and treat a
  422 as proof the route is authorized** - `/calendar/dividends` returned 422 *"filter.date eq field is required"*
  without params and 403 with them, which is how a plan-gated endpoint was separated from a mistyped URL; a 404 is not
  evidence of absence either. **Six of the nine reachable endpoints are REJECTED under master rule 15** - reachability
  is not a reason to adopt: `/ust/yield-rates` and `/ust/long-term-rates` duplicate
  `federal_reserve.get_treasury_curve:116`, `/us-quote-delayed` duplicates `yfinance_sector.fetch_sector:64` plus the
  already-used `/real-time`, `/id-mapping`'s `cik` duplicates `sec_edgar._cik_for:175`, and `/eod-bulk-last-day`
  (45,009 rows / 6.6 MB in ONE call) is the same producer batched - transport, not a source. **The adopted set is three
  endpoints**: P0 `/ust/real-yield-rates` - nothing in the tree reads TIPS, while `strategies/dcf.py::wacc_from_beta:28`
  already consumes a *nominal* 10y as `rf` and **assumes** the premium (`erp: float = 0.05`), so a real yield is the
  missing half that turns an assumption into a reading; P1 `/ust/bill-rates`; P2 `/id-mapping`'s **FIGI / LEI /
  CUSIP** with **CIK demoted to a fallback** (SEC is the authority for its own identifier). Behind one new gate,
  `enable_eodhd_rates`, default off. **Design only - no code, no gate, no test.**
- 2026-09-19 `(working tree)` - **Two real defects were hiding inside a lint count reported as "pre-existing, not mine".** The
  23 tree-wide `ruff check tradingagents/` findings were dismissed without ever being enumerated - and the extraction command
  used to justify that was itself broken (ruff prints absolute Windows paths, and the filename regex had no `:` in its class,
  so it died at the drive letter and printed nothing). **The `grep -c` count of 0 was valid evidence; the conclusion drawn from
  a command that produced no output was not.** Two of the 23 were not style. **Rule this leaves: enumerate a dismissed finding
  set before calling it pre-existing, and never report a conclusion from a command whose output was empty.** **Defect 1 -
  `risk_tool_loop._final_prose` raised `NameError` in the handler commented *"degrade, never raise mid-loop"***: `logger` was
  never bound anywhere in the file (one occurrence, no import, no `getLogger`), so a transient provider failure during the
  prose retry - the exact case the handler exists for - raised `NameError` out of the node, **and replaced the original
  exception, so the log never showed the real cause.** Fixed with the house binding. **Defect 2 - `report_verifier._period_tag`
  put a backslash inside an f-string expression (PEP 701, 3.12+)** while `pyproject.toml` declares `requires-python = ">=3.10"`,
  so the module could not be *parsed* on 3.10/3.11. It was the **only** such site repo-wide (`ruff --target-version py310`: 1
  `invalid-syntax` -> 0), so the honest fix is the code, not the declared floor. **The rule: when a declared compatibility
  floor and a single syntax site disagree, fix the site - do not raise the floor to match a line nobody needs.** Both proven
  failing-first by mutation (removing the binding, not stashing the file): `NameError: name 'logger' is not defined`, then
  green. Engine suite **4923 passed / 6 skipped**.
- 2026-09-18 `(working tree)` - **D3 REVERSED by the owner: the composite's printed `basis` contract is preserved.** The owner re-answered the
  third research-layer question in the opposite direction; `02145fe` is **reverted** here. `strategies/trade_score.py` is back to
  *"Advisory only: never a gate, never a size, never an `opportunity_score`"* in the framing sentence and to the same tail in
  `basis`; the rendered block is **byte-identical to `6047071`**.
  `tests/test_trade_score.py::test_the_printed_block_carries_weights_status_and_coverage` again pins the negative clause, with a
  comment recording that the wording is a *preserved contract*, not an oversight. **Why:** *"changing it alters every generated
  report"* is exactly why a contract change must not ride along with the scorecard rollout. **The owner's principle:** *"Enablement
  can be incremental; measurement cannot be pretend. And existing report contracts should not be changed merely to introduce the
  new scorecard."* **The rule this leaves:** the scorecard's explanation goes in **new** fields (`scorecard_basis`, and
  `basis_constraints` if the constraints need enumerating) - never a rewrite of a shipped string, so a gate-off `run_card.json`
  stays byte-identical to a pre-scorecard tree. **D1 and D2 are unchanged** (one `enable_quant_scorecard` block gate with engine
  gates underneath; deltas held until the vector is measured/validated/promoted). **The state machine is reconciled** to the owner's
  ladder (`ResearchLayerWiring.md` §4.6): enablement and measurement are now **two printed axes** - `DISABLED / PARTIAL / COMPLETE`
  and `RESEARCH_ONLY -> ACTIVE` - with the hard invariant **no validated vector -> no delta -> no movement**; research calculations
  may still be logged internally, but their presentation as movement is withheld. Both answers are recorded in §9.1 rather than
  quietly corrected, since the first was implemented and pushed before the second arrived. `tests/test_trade_score.py` 50 passed.
- 2026-09-18 `(working tree)` - **The three research-layer questions answered by the owner; D3 implemented. [D3 REVERSED - see the entry above; `basis` is preserved.]** Decisions in
  `docs/scores/ResearchLayerWiring.md` §9. **D1:** `enable_quant_scorecard` is the single top-level gate and the engine gates
  decide which rows populate - the master gate must NOT imply all eight, and the partial state must be **explicit**
  (state machine in §4.6: `DISABLED -> PARTIAL -> COMPLETE -> COMPLETE+VECTOR_VALIDATED -> COMPLETE+MOVEMENT_AVAILABLE`,
  with `Scorecard status` / `Vector status` / `Movement` printed). **D2:** movement is **held until the vector is
  validated** - `RESEARCH_ONLY` is not the reason to suppress a delta, *vector validity* is; do not manufacture a
  movement field because the score exists. **D3 (implemented, a report-contract change):** the composite's printed block
  now leads with its purpose. `strategies/trade_score.py` - the framing sentence became *"Purpose: the highest-level
  quantitative evidence summary, for human research review - not an order, not a position size and not a gate"*, and the
  `basis` field's duplicate restatement was dropped so the constraint is stated once.
  `tests/test_trade_score.py::test_the_printed_block_carries_weights_status_and_coverage` now pins **both halves** (purpose
  and constraints), so removing either fails. Reported but **not** inferred: the seven engine renderers
  (`analysis_tools.py:5053/:5261/:5849/:6008`) and the engines' own basis tails still carry their negative-only line -
  the owner named the composite, so those are a separate call. `tests/test_trade_score.py` 50 passed.
- 2026-09-18 `(working tree)` - **D-7 fixed, and the research-layer wiring designed** (`docs/scores/ResearchLayerWiring.md`, a new
  doc in the set). Found by executing both paths to the same number with different dates: `_trade_score_engines` called
  `fundamental_score_for_ticker(ticker)` with no date (`fundamental_score.py:550` falls back to `datetime.now()`) while
  `_run_card_fundamental_score` (`reporting.py:881-882`) passes `pm_decision.trade_date`. Measured on MSFT for the
  documented `batch.py --date 2026-07-22`: leaf **`66.25`** vs card **`62.50`**, same basis, same `panel_n=9` - and the
  leaf was the wrong one. **Fixed** by threading `current_date` (mirroring the sibling `get_fundamental_score`); two
  regression tests fail before (`TypeError`; `assert None == '2026-07-22'`) and pass after; `tests/test_trade_score.py`
  **50 passed**. **The design finding:** the eight scores reach only a gated tool leaf and `run_card.json`, which has **no
  research-layer reader at all** (executor ignores it, `signald/watch.py:6-8`; web reads only `*.md`), while
  `computed_decision_context` - one string built at `trading_graph.py:649` - already reaches **ten** prompt sites, the L1
  ground-truth registry (`structured_debate.py:298`) and report section `IVa` (`reporting.py:1644-1646`). One producer,
  three readers, already wired. **The design:** one `quant_scorecard` snapshot, pre-graph, read by the context block, the
  card and the leaf - never a third producer; one new gate, default `False`; the block goes **first** because
  `structured_debate.py:216` bounds the context to 3000 chars. Also recorded: **D-8** (leaf vs card composites disagree
  when a sub-gate is off - the D-6 class, not closed), **D-9** (a gate-on `enable_sentiment_score` is unreachable: no
  sentiment ToolNode, `trading_graph.py:343-345`, pinned by a test - deliberate, but it bounds the design), **D-10**
  (`independent_agreement` read at `structured_debate.py:644` and never written; pre-existing, on the books at
  `docs/implementation_plan_defect_audit.md:51` with drifted line numbers). Two stale docs corrected: `agent_states.py`'s
  channel docstring named 3 of 10 consumers, and `docs/design_risk_calculations_agent_wiring.md` §3 gave the bull/bear
  researchers "no computed context" and the RM "none" - both false.
- 2026-09-18 `(working tree)` - **The composite's purpose is stated; the verdict attribution corrected (owner).** Docs
  and a docstring only - no behaviour, no printed output. The set stated only the *negative* constraint (`TradeScore`
  reaches no gate, no size, no `opportunity_score`) and nowhere said what the composite is *for*; worse, master §1.4
  and the plan's §8 attributed the acceptance case's verdict to the composite (`F 92 / T 85 / R 78 / K 35 -> NO NEW
  RISK`), when that verdict is the downstream gate's. **Recorded at both definition sites:** `TradeScore` is the
  **highest-level quantitative evidence summary**, its consumer is a human reviewer, and `RESEARCH_ONLY` does **not**
  mean "do nothing" - it means the evidence is summarised and the conversion to an action is deliberately not this
  object's job. `F92/T85/R78/K35` says *"the quantitative evidence is favourable overall, but the application is not
  authorised to convert it into a trade automatically"*; the reviewer asks why risk is the low leg and decides, and
  "I agree, no trade" / "I disagree, that risk reading is temporary" are both legitimate. **Coverage travels with the
  number** (`72` at `coverage 68%` = 72 over 68% of the intended evidence, missing components named) because a human
  makes the decision. Nothing functional changed: no score reaches `opportunity_score` (owner Q1 keeps it `null`),
  sizing or the gate. Edited: `docs/scores/README.md` §1.4, `IMPLEMENTATION_PLAN.md` §8 + R10,
  `strategies/trade_score.py` docstring. Engine suite **4770 passed / 5 skipped**.
- 2026-09-18 `(working tree)` - **D-6 found and fixed: the leaf's `TradeScore` never read `RiskScore`** (master §3.4).
  Walking a worked example of the score pipeline end to end - not reading the set - returned `fundamental 66.25`,
  `technical 62.61`, `regime 79.78`, **`risk null`** from `_trade_score_engines`, while `_risk_components('MSFT')`
  returned 13 real components and `strategies/risk_score.risk_score` scored them **79.39**. The assembler carried
  three engine blocks and returned behind a stale *"WP-5 fills `risk` in ... until it lands the engine is absent"*
  comment; WP-5 had shipped in `1260329`, and the assembler's own test already patched `_risk_components` as if it
  were in the path. **Consequence: one vector, two numbers on two surfaces.** The leaf's `K` was `None`
  unconditionally, so `get_trade_score` never applied the owner's published `K = 0.20` (coverage capped at **80%**)
  while `_run_card_trade_score` - which reads all four engine blocks - applied all four (MSFT: leaf `67.65` at 80%
  vs `70.00` at 100%). **Fixed** by mirroring the other three blocks (`_risk_components` -> `risk_score`); the
  regression test fails before the fix (`assert None == 74.0`) and passes after. **Same pass, the doc set's status
  lines were corrected**: all seven engine documents and the master still read *"design ... Not started"* and the
  plan *"Nothing implemented"*, while that same plan's §9 carried **Exit - MET** for every phase - each status line
  now names the module, the leaf, the gate and the measurement state. **Third instance of one failure shape**
  (producer exists, reader exists, the wire was never run) after the executor's ingest boundary and the
  `ba50b5f`/`2c05701` sets: a ledger built by reading documents cannot see it, only executing the path can.
  Engine suite **4770 passed / 5 skipped** (1 new).
- 2026-09-17 `(working tree)` - **WP-2 step 1 landed: `factors.quality_composite` -> `factors.category_scores`** (the
  shared cross-sectional core renamed, not forked; the caller owns the metric set, directions, weights and band table, and
  only `label` reaches the printed `basis`). The old name is gone rather than wrapped - both callers
  (`scripts/value_screener.py:2367`, `analysis_tools._quality_composite_row:4594`) call `category_scores(...,
  label="quality composite")` and print the identical basis string. `QUALITY_DIRECTIONS` / `QUALITY_BANDS` /
  `quality_band` / `enable_quality_composite` are untouched. Tests: `test_quality_composite.py` ->
  `test_category_scores.py`, 12 tests re-pointed; 44 passed across it + `test_round3_wiring.py`. Live docs re-pointed.
- 2026-09-18 `(working tree)` - **WP-10 measured live.** `scripts/score_panel.py` ran for real: 30 dates
  (2026-08-06...2026-09-17) under `~/.tradingagents/cache/panels/`, 149 of 150 NASDAQ common stocks, 154,188 metric
  cells, cost + fetch timestamp per file, and a second invocation with **0 network calls** (30 cache hits). The EODHD
  **bulk-fundamentals leg is 403 (support-gated)** and `_meta.vendor_gate` records it per date rather than caching an
  empty panel. Statistics measured for 36 of TechnicalScore's 40 components (IC, ICIR, decile spread, monotonicity,
  turnover, persistence, OOS split, deflated Sharpe, purged-CPCV, family PBO/White/Hansen); the redundancy matrix gives
  136 pairs in the trend+momentum+RS block (mean |rho| 0.36, 8 pairs >= 0.80). **Two defects fixed failing-first:**
  `evaluate.cagr` returned a complex number on a <= -100% compounding series, and `alpha_health` printed nan as a rank
  IC. `docs/scores/MEASUREMENT_FINDINGS.md` labels every line MEASURED/UNMEASURED/DECLARED. **Full engine suite: 4769
  passed / 5 skipped** (the 4454 baseline plus the six engines' and the panel's tests); executor 1105, web 149.
- 2026-09-18 `(working tree)` - **WP-4 ... WP-11 landed: the remaining six engines, their leaves, the composite and
  the measurement harness.** `strategies/regime_score.py` (market-level; the two regime paths printed unreconciled - live
  Path A `neutral` vs Path B `BULL`), `risk_score.py` (inverted, 100 = low risk; the three shipped sign conventions
  aligned in the score, raw -> pinned -> aligned printed per row; `net_beta` producer in `book_risk`),
  `event_state.py` (one imminence clamp for seven families, monotone and bounded; the hard block still earnings-only;
  the company calendars ABSENT with the P0-9 evidence), `sentiment_score.py` (scale pinned first and printed; two tone
  sources REFUSED, not averaged; four quadrant labels), `news_score.py` (five unsupplied categories print NA with a
  reason; materiality caller-supplied from EventScore per Q6), `trade_score.py` (prints weights/status/coverage, reaches
  no gate/size/opportunity_score, reads no config, ladder clamped to evidenced rungs) and `scripts/score_panel.py`.
  **Eight gates, all default off, all toolset-membership switches**: gate off = byte-identical toolset and card; gate on
  = exactly one tool and one card block. **Two defects fixed on sight:** `regime.vol_percentile` returned a fabricated
  `0.5` (now `None` + reason, with `regime_label` None-tolerant) and its caller `get_regime_components` formatted the
  value outside its try. The `RISK_WEIGHTS` conflict flagged earlier is resolved by the master itself (rule 18: 0.40F +
  0.25T + 0.15R + 0.20K, Regime inside, the six-engine allocation a separate object).
- 2026-09-17 `(working tree)` - **WP-3 landed: the `TechnicalScore` engine** (`strategies/technical_score.py`,
  `volatility_models.semivariance`, leaf `get_technical_score`, run-card block, gate `enable_technical_score`). Nine
  category sub-scores over 40 components, all from the run's own cached bars; every non-monotonic input band-mapped over
  its producer's own edges (a first draft had five tables inverted - the smoke test caught it); `NA != 0` throughout; a
  count floor capped at the category's own size. **Two producer-side corrections:** the RS level is a scale-dependent
  price ratio and is not a component (the scale-free `rs_trend.above_sma` replaces it), and `regime.vol_percentile`
  returns `0.5` on failure (a fabricated neutral) so the leaf does not consume it - the defect's home is WP-4.
  `semivariance` lands with `RS- + RS+ = RV` exact and `None` below the floor. Both card keys are now written only when
  their own gate is on, so a gate-off run's card is byte-identical. Live MSFT 61.25 / NVDA 55.34 (both neutral,
  coverage 0.95). `test_technical_score.py` +30; 72 passed across the technical/fundamental/gate suites. **Phase 0 exit
  recorded in the plan §9** (engine 4454/5 skipped, executor 1105, web 149).
- 2026-09-17 `(working tree)` - **WP-2 landed: the `FundamentalScore` engine** (`strategies/fundamental_score.py`,
  `strategies/factor_schema.py`, leaf `get_fundamental_score`, run-card block, gate `enable_fundamental_score`). Four
  advisory category sub-scores (FQS/FGS/VS/FRS) as thin wrappers over `factors.category_scores`, each with its own band
  table, factor set and floor; the composite ships `RESEARCH_ONLY` with equal weights printed. `NA != 0`: an unsupplied
  factor is named (`rev_cagr5`, `fcf_yield`, `val_z`) and dropped, a name below the floor is withheld with its reason,
  and coverage is stated over the sub-score's own factor set. `dcf_confidence` (four measured legs, capped at 0.6 when
  one is unreadable) scales the DCF upside before it enters VS. **Two defects fixed on sight:** `category_scores`
  raised `KeyError` on any partial weight vector, and the design's floor of 3 withheld every name from FGS forever (it
  has two factors with a supplier) - a count floor is now capped at the sub-score's own factor count. Also recorded:
  the design listed the Ohlson O in both FQS and FRS (a master-rule-15 double count); FRS owns it. The peer panel
  gained an opt-in score-metric extension so the round-3 quality row does not move. Live MSFT: FQS 75.0 (7/7),
  FGS 33.3 (2/2), VS 62.5 (9/10), FRS 87.5 (6/6), composite 64.6 over 4/4, 0 withheld. `test_fundamental_score.py`
  +36; 93 passed across the score/schema/wiring suites.
- 2026-09-17 `(working tree)` - **P0-9 landed: both vendor probes answered** (recorded answers, no code). **(1) EODHD
  `/sentiments` coverage is COMPLETE for this universe** - 26 of 26 names returned a non-empty series (16 large caps at
  73-151 daily points, four ETFs, 0700.HK, SKHY, BRK.B, RIVN, ARM, CART; no empty result, no error), so the hardcoded
  `source="eodhd"` in `_sentiment_factor_read` costs nothing today and the answer is **mirror the leaf's EODHD -> AV ->
  GDELT chain if a gap appears; change nothing now** (a fallback that never fires is untested code on an unreachable
  path). **(2) The moomoo economic calendar does NOT carry the company-level calendars** - 50 rows over 14 days, every
  one macro (Fed projections, TIC flows, jobless claims, housing, auctions, Philly Fed, GDPNow), and **zero** matching
  FDA/clinical/trial/phase/court/litigation/ruling/investor day/analyst day/drug/approval, so the three calendars are
  **ABSENT with evidence** and need a company-events source of their own. Recorded in `SentimentScore.md` §3,
  `EventScore.md` §4 and the plan's §3.9. Engine **4454 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **WP-1 landed: the shared score kernel.** `strategies/score_engine.py` - three
  functions and no framework (no registry, no engine import, no weight table): `align` (a `lo`→0/`hi`→100 ramp or a
  **band table over the producer's own edges**, with `NON_MONOTONIC_INPUTS` naming the eight non-monotone technical
  inputs so none can be treated as monotone; `None` in → `None` out, **never a neutral 50**; a direction typo RAISES),
  `combine` (renormalise over the **present** components, `coverage` = the measured weight share, **withhold below the
  floor with the reason** - `score` is `None`, never 0/50 - and a `basis` naming the weights actually used and the
  absent components), and `band_label` (the engine's own table, a **required argument** so no default could be the
  guardrail's contract bands). **The two semantics were extracted, not re-derived**: `factors._coverage_floor` and
  `factors.quality_band` now delegate to the kernel and the 13 quality-composite tests pass unchanged. Eighteen
  acceptance tests including the plan's five with their mutations. Engine **4454 passed / 5 skipped**, executor
  **1105**, web **149**.
- 2026-09-17 `(working tree)` - **P0-5 landed: the VIX term structure.** `dataflows/cboe.py::vix_term_structure()`
  reads the two Cboe CDN history CSVs (daily-cached, one fetch per day) and returns `{vix9d, vix3m, slope, state,
  as_of, basis, reason}` on the **shared long-minus-short sign**; a flat curve is `contango` (not stress), only a
  negative slope is `backwardation`, and an unreachable CSV leaves `None` + the reason - **never** the equity-IV slope
  under a VIX name. **`dataflows/cboe.py` already existed** (the CBOE delayed options-chain vendor): the function was
  ADDED to it, and a test pins that the routed `get_options_surface` is untouched. **Live: `vix9d=13.39, vix3m=18.55,
  slope=5.16, contango`, `as_of=09/17/2026`** - Cboe writes MM/DD/YYYY, so the docstring's "ISO" claim was corrected
  against the observed payload. Six tests. Engine **4436 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **P0-6 landed: the short-interest percentile.** `strategies/short_interest.py` ranks the
  latest settlement within the name's OWN series (percentile, raw, prior, change, n, basis) and carries the **direction**
  sentence - *high short interest is bearish positioning with a squeeze RISK, not a bullish signal* - so the number cannot
  be quoted as a squeeze thesis alone. `min_obs` counts **settlements, not days** (FINRA settles twice a month): below it
  the percentile is `None` **with the reason**, never a fabricated 0.5. Wired into `massive.get_short_interest_massive`,
  which had the series and printed only raw levels. Four tests. Engine **4431 passed / 5 skipped**, executor **1105**,
  web **149**.
- 2026-09-17 `(working tree)` - **P0-3 landed: market-wide breadth from the panel the run already fetched.**
  `strategies/market_breadth.py::market_breadth(closes_by_name, *, windows=(20,50,200), min_n=20)` - percent-above-MA from
  the shared `sector_breadth.multi_breadth`, with A/D, new-high/new-low and coverage computed from the **same map** so
  the numbers cannot describe different panels. The denominator gate is `sector_screener.breadth_with_gate`: below
  `min_n` the percentages are `None` **with the reason** while the counts still travel (a count is not a rate); an empty
  map is `None`, never 0; and the high/low counts are measured against the caller's own window with the basis naming it
  (a 60-bar panel cannot be quoted as a 52-week figure). **Real run** over 22 names from the in-repo S&P map (315
  constituents): `n=22, coverage=1.0, pct_above_20d=45.5, 50d=54.5, 200d=40.9, A/D=-2, new_highs=1, new_lows=1` - the
  panel size prints beside the percentages. Five tests. Engine **4427 passed / 5 skipped**, executor **1105**, web
  **149**.
- 2026-09-17 `(working tree)` - **P0-4 + P0-7 + P0-8 landed.** (P0-8a) `position_mult_by_side` tested
  `catalyst > 1` while every caller supplies 0..1, so `event_scale` was **always 1.0** - a real sizing bug; now
  `0 < catalyst <= 1`. (P0-8b) `get_earnings_calendar`'s `look_back_days` named the opposite direction to the
  `[curr_date, curr_date + N]` it queries - renamed `look_ahead_days` on all three vendors + the tool. (P0-8c)
  `get_tail_risk` printed a single name's price-path drawdown as `cdar=`, the name the BOOK owns; now labelled
  `price_path_dd_tail_mean` / `price_path_dd_var` / `price_path_max_dd` with "not the book CDaR". (P0-8d) the
  cash-sleeve normalisation had two copies; `normalize_book_weights` is the one, and a test replaces it and shows
  BOTH paths move. (P0-8e) `get_macro_regime_read` now **derives** all five markers from the run's own leaves
  (T10Y2Y, HY OAS, EFFR/DTWEXBGS changes, the VIX percentile) - supplied wins, unmeasurable stays `None`, and the
  leaf prints which it derived. (P0-4) `_vix_percentile_read` ranks VIXCLS on `fred.get_series_values` +
  `normalized.percentile_hist_or_none` (None below min_obs, never a fabricated 0.5) and feeds the market-level
  regime path; `get_macro_indicators` is bound to `market_tools()`. (P0-7) all four bindings in one commit:
  `sentiment_tools()` (11 leaves) registered as the `sentiment` key - the analyst itself still binds none by design
  - plus `get_institution_holdings` (sentiment), `get_analyst_revision_index` (news), `get_market_breadth` (market);
  the market prompt gained the two trigger lines the contract test demands (79/95 bullets, under the ceiling).
  15 new tests, 11 failing without the sources. Engine **4422 passed / 5 skipped**, executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **P0-1 landed: the structured SEC XBRL series and its consumer.** `sec_edgar.financial_history_series`
  is the structured producer (`get_financial_history` renders from it - one implementation, two readers); `_TAG_MAP` grew 8 -> 12
  rows (diluted EPS, operating income, D&A, gross profit) and the row reader accepts `USD/shares` for per-share concepts;
  **EBITDA and FCF are derived and labelled `derived: true`** (no us-gaap tag exists - fetching one would be a fabrication).
  `statement_parsing.sec_annual_series` maps labels to canonical series keys, keeps only the **longest run of consecutive
  fiscal years** per key (readers index positionally, so a hole misaligns them), and calls the same `_add_roa` the vendor
  path calls. The `fetch_ticker` merge is **opt-in** (`with_sec_series=True`) at the two leaves that need depth -
  `get_quality_factors` (G4/G5) and `get_earnings_quality` (Dechow-Dichev) - because one EDGAR request plus an as-reported
  USD basis is a cost the default vendor path must not pay; a test asserts the default call never touches EDGAR, the longer
  series wins **per key** (never spliced across bases), and provenance names `source: "sec_xbrl"`. Four new tests, all
  failing pre-change; three test doubles gained `**kw` for the new parameter. Engine suite **4410 passed / 5 skipped**,
  executor **1105**, web **149**.
- 2026-09-17 `(working tree)` - **All five §14 defects fixed; two were code.** (D-3) the SEC `User-Agent`'s placeholder
  contact (`research@example.com`) is replaced with the owner's real address (`sec_edgar.py:33`) - and the same defect
  class was found next door at `sp500_universe.py:122` (`contact@example.com`, Wikimedia asks for the same thing), fixed
  with the identical string, both sites cross-referenced in comments. (D-4) `get_financial_history` no longer makes 11
  `companyconcept` calls: `_us_gaap_facts` reads every us-gaap tag from ONE `companyfacts` payload, with the per-tag loop
  **kept as the fallback** (a multi-MB payload can fail where a small one would not; losing every tag at once is worse),
  and `_annual_rows` holds the shared 10-K FY filter so both paths use one rule - two new tests, both **failing against
  the pre-change module**. (D-1/D-2) re-verified fixed: master §4/§5 are pointers, and a headings-vs-references scan of
  all nine docs finds the dead section names only inside the D-2 record row. (D-5) the three documents that read
  `enable_factor_model` as "the score" gate now say, in body and seam table, that it gates the **learned** model only
  (`factor_model_train.py:7`, `default_config.py:899`, `.env.example:227`). The plan's §14 and the master's §3.3 became
  **status tables**; the plan's P0-1 text is corrected to past tense. Engine suite **4406 passed / 5 skipped**, executor
  **1105**, web **149**.
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
  line derives it from the overlay's stamped snapshot and prints `catalyst_window=`. **[CORRECTED 2026-09-18: this entry is
  wrong on both counts, and the veto is still inert. `strategies/regime.py:252` still declares `catalyst_window: bool =
  False`, not `bool | None = None`; and the compiled-context line is built from `init_agent_state` BEFORE `graph.invoke`
  (`graph/trading_graph.py:645-647`) while the overlay snapshot is stamped AFTER the graph (`:686`), so the read is always
  `None` and the line always prints `False`. Re-confirmed by execution against 160 persisted runs — 15 hold a snapshot whose
  own reader says the window is active, and all 19 printed occurrences in the report corpus read `False`. Carried as defect
  D-11 in `docs/scores/README.md` §3.5 and `EventScore.md` D3.]** (17) `rule_signal_macd_hist_rising`
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
  estimate-change leg prints why it is unavailable), `factors.category_scores` (0-100 winsorised-z percentile,
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