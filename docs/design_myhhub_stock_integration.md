# myhhub/stock (InStock) — Teacher Study for TradingAgents

Status: **design study only — no code changes.** Direct-source study of
`github.com/myhhub/stock` (package `instock/`), a Chinese-language A-share
quant platform: MySQL-stored daily job pipeline (init → basic data →
selection → indicators → candlestick patterns → strategies → backtest →
after-close), tech indicators via TA-Lib, candlestick-pattern + chip
distribution (`cyq.py`) analytics, a uniform `check(...) -> bool` strategy
predicate layer, a Tornado + bokeh web UI over a declarative table registry,
and a live-trade robot (event/clock engines + easytrader broker adapters),
all fed by Eastmoney scraping with a cookie-triangle + Retry session. This is
a **rule-based technical platform, not an LLM agent system** (confirmed by
web grounding). Everything here is **advisory and opt-in**; the fork's
no-execution / advisory-first / deterministic-over-LLM mandates, its
stateless-per-run design, and its Python + React web stack are unchanged.

## 1. The one-paragraph takeaway

InStock runs an entire trading operation on three simple contracts that the
fork can borrow small pieces of: **(a) one uniform strategy predicate**
`check(code_name, data, date=None, threshold=60) -> bool` — every strategy
(turtle, volume-entry, climax-limitdown, platform-breakout…) is a pure
boolean over a date-capped dataframe, each carrying a **self-guard**
`len(data.index) < threshold: return False` so no strategy ever fires on
insufficient history; **(b) one trading-calendar singleton** —
`is_trade_date / get_previous_trade_date / get_next_trade_date` over a cached
full market calendar, with `None` fallbacks everywhere so a missing calendar
never blocks a run; **(c) one declarative table registry** (`web_module_data`:
mode/type/columns/primary-key/is_realtime) that turns any stored table into a
generic query/edit web surface. The genuinely NEW contribution for this fork
is the **managed trading-calendar cache** — the fork's `effective_date`
already has region timezones, weekend handling, and a caller-supplied
`non_trading_days` override; InStock's lesson is that the override should be
fed by a cached, validated market calendar rather than hand-supplied. The
rest mostly validates fork direction already planned elsewhere (the
FinceptTerminal topic-registry for the web-table pattern; stepwise jobs vs
the fork's batch/nightly; evaluate.py far richer than their `rate_stats.py`).

## 2. What InStock does that the fork already implements (validated)

| InStock mechanism | Fork equivalent | Verdict |
| --- | --- | --- |
| Stepwise daily jobs (init → basic → selection/indicators/kline/strategy → after-close; ThreadPoolExecutor for parallel steps) | `batch.py` nightly + `run_batch`/`run_pipeline` (worker caps) + web jobs runner | already adopted; ordering + optional parallel sub-steps matches |
| StratDateTime-aware scheduling (clock engine fires interval handlers only inside trading session) | wall-clock scheduled nightly/premarket; `effective_date` region-close logic | partial — the fork has market-local *dates*, not *session* scheduling (A2 below) |
| Calendar singleton (is_trade_date / prev / next) with None fallbacks | `effective_date._market_dt` (region tz) + `_is_weekend` + caller-supplied `non_trading_days` override | **the gap is the managed calendar source** (A1 below) |
| Uniform `check(...) -> bool` strategy predicate + threshold self-guard | min-obs guards scattered (event_study, Kelly, PEAD `_RETROSPECTIVE_CUTOFF_DAYS`); skills `select_skills(regime)` | validates; standardize the guard convention (A3) |
| Declarative web table registry (`web_module_data` → one `/instock/data?table_name=` endpoint) | trading_web per-capability REST handlers + provenance fields | validates the FinceptTerminal topic-registry direction (already planned) — no new layer |
| Eastmoney fetcher: cookie-triangle (env > file > default) + Retry HTTPAdapter + proxy singleton | `dataflows/registry.py` credentials (`.env`) + `yf_retry` + moomoo gateway probe | partial — the **env-first cookie priority** convention (A4, minor) |
| Chip distribution (cyq.py) + candlestick patterns via TA-Lib | `technical` reads + pattern-ish reads; fork's own formula suite | fork's formulas are richer; chip distribution is A-share-specific, not adopted |
| Backtest `rate_stats.py` (window pct-change + high/low stats) | `strategies/evaluate.py` (Sharpe/Sortino/Calmar/PSR/IC/decay/CPCV/PBO + benchmark + cost) | fork is far ahead — no lesson |
| MySQL schema-in-code + idempotent CREATE IF NOT EXISTS per job | stateless-per-run (results_dir + JSON ledger); FinceptTerminal P4 jobs-checkpoint is the planned persistence | non-goal (see §4) |
| Live-trade robot (event/clock engines + easytrader client adapters) | advisory-only by mandate; TradingExecution is the phase-gated successor | non-goal (see §4) |

## 3. Adoptable lessons (phase-gated, advisory-first, default-off)

### 3.1 — Managed trading-calendar cache (A1, the flagship)

**What:** `lib/trade_time.py` + `singleton_trade_date` expose a cached full
trading calendar with three functions (`is_trade_date`,
`get_previous_trade_date`, `get_next_trade_date`) and a hard rule: a missing
calendar returns `False`/the input date and **never blocks a run** — the
whole pipeline stays alive on weekends/holidays without the calendar.

**Gap in the fork:** `effective_date` already has the region timezone map
(`_REGION_CLOSE`), weekend logic, and a caller-supplied `non_trading_days`
override — but the override is **hand-supplied** (docs: "the override set the
caller may supply"). Nothing fetches/caches a per-market trading calendar, so
the "exchange closed vs no data" distinction the yfinance study flagged
(A2/P2 calendar half, previously judged skip) still cannot be made
automatically.

**Adopt (Phase-A1, small):**
- `dataflows/trading_calendar.py`: a cache around the existing
  `non_trading_days` hook — `is_trading_day(market, date)`,
  `previous_trading_day(market, date)`, `next_trading_day(market, date)`; the
  calendar is fetched best-effort ONCE (yfinance `Calendars` metadata or a
  tiny static holiday table) and cached to disk under `data_cache_dir`
  (validated + invalidated like the yfinance A2 tz-cache design), with a
  hard fallback to weekends-only when the fetch fails (the InStock None rule:
  a missing calendar degrades, never blocks).
- `effective_date` calls `is_trading_day` when no explicit override is
  supplied (default-off config key `enable_trading_calendar`); behavior
  unchanged while off.
- Tests: weekend False, known holiday False, prev/next navigation, fetch-fail
  → weekends-only fallback, cache invalidated on corrupt entry.

### 3.2 — Session-aware scheduling hint (A2, small)

**What:** InStock's clock engine fires interval handlers **only inside the
trading session** (`trading=True` + clock check) — the same handler is
session-agnostic and simply doesn't fire outside market hours.

**Adopt (Phase-A2, small, web + nightly):** `run_nightly` / web job requests
accept an optional `session` (`pre` / `after` / `any`); `after` (default)
skips execution when the region's current time is before its daily close
(the fork already computes market-local time in `effective_date._market_dt`),
so a cron/web trigger cannot run the "after close" job mid-session. Advisory:
scheduling is a hint, never a hard gate; the jobs runner stays wall-clock.
Tests: after-close job skipped at 10:00 market-local, runs after close, `any`
always runs.

### 3.3 — Uniform predicate + min-obs guard convention (A3, doc + helper)

**What:** every InStock strategy is `check(code_name, data, date, threshold)
-> bool` and begins with `len(data.index) < threshold: return False` — the
guard is structural, not per-strategy discretion.

**Gap in the fork:** the min-obs discipline exists (event_study t-test
min-obs, Kelly, PEAD retrospective cutoff, stockstats warm-up bars) but is
scattered conventions without a shared helper.

**Adopt (Phase-A3, tiny):** `strategies/obs_guard.py` —
`require_observations(df, n: int, *, name="") -> bool` (False when too short,
with one log line naming the series); new strategy reads that need a minimum
window call it; existing guards are NOT churned (clean-cutover principle:
add the helper, migrate only where a read is touched). The full uniform
predicate layer is deliberately NOT built — the ai-hedge-fund mandate study
(A1/A3: `AlphaModel.predict -> Signal`) is the correct shape for the fork's
typed views; a boolean-only contract would lose the fork's advisory nuance.

### 3.4 — Env-first cookie/credential priority (A4, minor)

**What:** Eastmoney fetcher resolves the cookie by priority
`env var > file > default`, so an operator overrides without editing code,
and the default is a documented fallback that can expire.

**Adopt (Phase-A4, minor):** note in `dataflows/registry.py` docstring /
`dataflows/README.md` that vendor secrets resolve `env var > .env file >
(no default for real keys)` — the fork already has this for keys; the *file*
middle tier (e.g. a gitignored vendor cookie file for scraping-style feeds)
is the new convention. Docs-only unless a scraping-style vendor appears.

## 4. Explicit non-goals (reasons)

| InStock surface | Why not adopt |
| --- | --- |
| Live-trade robot (event engine, clock engine, easytrader client adapters, order placement) | the fork is explicitly advisory-only; TradingExecution is the phase-gated successor — consistent with every prior teacher study |
| MySQL persistence + schema-in-code + CREATE IF NOT EXISTS per job | the fork is deliberately stateless per run (results_dir + JSON ledger); the FinceptTerminal P4 jobs-checkpoint plan is the extent of planned persistence |
| Chip distribution (cyq.js/cyq.py) | A-share-specific distribution analytics; the fork's own formula suite covers the underlying concepts; a JS port is content, not capability |
| GUI (Tornado + bokeh + SpreadJS tables, Docker compose) | the fork ships trading_web; the *declarative registry* idea is already covered by FinceptTerminal P1 (topic policy) |
| Eastmoney/A-share data crawling (akshare/tushare-style feeds) | the fork's vendor chains cover its markets; A-share feeds are not a research gap |
| Candlestick-pattern + selection table jobs | covered by the fork's pattern-ish + screener reads; no gap |

## 5. Phases (dependency-ordered, all advisory + default-off)

1. **P1 — Trading-calendar cache (A1)**: `dataflows/trading_calendar.py` +
   `effective_date` hook + `enable_trading_calendar` key. Tests: weekend /
   holiday / prev-next / fetch-fail fallback / cache invalidation.
2. **P2 — Session-aware scheduling (A2)**: `run_nightly` + web job
   `session` param. Tests: skip mid-session, run after close, `any` runs.
3. **P3 — Min-obs guard helper (A3)**: `strategies/obs_guard.py` +
   convention docs. Tests: too-short False + log, adequate True;
   existing guards untouched (suite green, no migration).
4. **P4 — Credential-priority note (A4)**: `dataflows/README.md` +
   registry docstring. Docs only.

## 6. Honest limits

- **A rule-based platform, not an agent system**: the only transferable core
  here is the calendar cache, the guard convention, and scheduling hints —
  everything else validates the fork's existing/planned direction.
- **A-share specificity**: the strategies, the feeds, and chip distribution
  are Chinese-market-shaped; the fork's markets (US + global) get the
  *contract* (uniform predicate, calendar, registry), not the *content*.
- **The calendar cache is the small, high-value exception**: cheap (one
  fetch per market, disk-cached, validated), directly serves the yfinance
  study's "exchange closed vs no data" gap (its P2 calendar half), and taps
  the existing `effective_date` override hook — no new subsystem.
- **No uniform-predicate layer built**: boolean-only signals would flatten
  the fork's advisory numeric reads into hard gates; the ai-hedge-fund
  mandate AlphaModel is the right shape, and A3 only standardizes the
  min-obs guard.
- **Scheduling is a hint, not enforcement**: a skipped "after-close" job
  could delay work if the clock is wrong; `any` remains available and the
  docs say so.

## 7. Validation & sequencing

Per phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs true, trading_web mirrored where a surface gains a
field (P2's `session` param in the jobs API + docs note). No behavior change
while the new config keys (`enable_trading_calendar`, session hints) are off
(defaults off). Live smokes: P1 —
`get_calendar_read('US')`-equivalent returns trading days and
`effective_date` labels a known holiday "closed" without a supplied override;
P2 — a web job with `session=after` started at 10:00 US/Eastern is skipped
and logged; P3 — a 5-row series into a 60-obs read returns False.

Mapping: **A1 → P1**, **A2 → P2**, **A3 → P3**, **A4 → P4**. P1 is the
flagship (serves the yfinance A2/P2 calendar half already identified) and
ships with P3 (both tiny, independent); P2 touches the web jobs API; P4 is
docs. Cross-study note: P1/P2 compose with the FinceptTerminal topic-policy
registry (P1: refresh timing) and the yfinance A2 tz/calendar phase.