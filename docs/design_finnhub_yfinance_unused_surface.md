# Design + implementation: the unused finnhub and yfinance surfaces

State 2026-09-18. Sources: the installed `finnhub-python` and `yfinance` (**1.5.2**)
packages, introspected directly, and **live calls** — finnhub against the repo's own
free-tier key (61 calls, paced 1.4 s) and yfinance against live Yahoo (32 calls, paced 1.0 s).
**No code changed by this document.**

Companion to `docs/design_moomoo_unused_api_surface.md` (same shape: enumerate the unused
surface, diff it against the tree, probe it live, and plan only what survives).

---

## Verdict

One finding justifies this document; the rest is boundary work that stops the next person
re-probing it.

**The headline: `yfinance.Ticker.eps_trend` supplies the exact input that
`strategies/analyst_revisions.py::estimate_change_index` documents itself as never having.**
That leg is **permanently `unavailable` in production today**, by the module's own account,
and the missing object is a five-level quarterly estimate series. `eps_trend` returns
`current` / `7daysAgo` / `30daysAgo` / `60daysAgo` / `90daysAgo` — five levels. One property
converts a documented gap into a measurement.

Everything else sorts into three buckets:

| | Finding |
|---|---|
| **Worth taking** | `eps_trend` + `eps_revisions` (fills the gap); `market_holiday` (half-day sessions, no current source) |
| **Cross-check only** | finnhub `financials_reported` / `filings` (as-reported + `acceptedDate`) — `sec_edgar` is already the producer; yfinance `ttm_*` — `trailing_twelve_months` is documented as *"one producer"* |
| **Do not wire** | the finnhub 403 set — 49 of 61 probed endpoints, listed in Appendix A |

---

## What the scan covered

| | finnhub | yfinance |
|---|---|---|
| public surface | **117** methods on `finnhub.Client` | 5 module functions, 15 classes; `Ticker` = **54 properties + 44 methods** |
| called by this repo | **9** | ~23 `Ticker` attributes + 4 module attributes |
| **unused** | **108** | ~31 properties, ~21 methods, 11 classes |
| live-probed | **61** | **32** |
| transport | SDK client over HTTP | keyless HTTP (Yahoo) |

The used sets were extracted from the tree, not from memory: `finnhub.py`'s nine
`_client().<method>` call sites, and every `<tk>.<attr>` bound to a `yf.Ticker(...)`
across the 24 files that import yfinance.

---

## Verified live (2026-09-18)

### finnhub — the free-tier wall is wide, and now enumerated

**12 of 61 probed endpoints work. 49 return HTTP 403 "You don't have access to this
resource."** This confirms the repo's own warning in `docs/AGENT_ONBOARDING.md`: *"the
SDK's `Client` exposes far more than the free key grants … never assume an endpoint works."*

| works (12) | verified payload |
|---|---|
| **`financials_reported(symbol, freq)`** | `{cik, data, symbol}` — **as-reported** financials |
| **`filings(symbol)`** | **500 rows**: `form`, `filedDate`, **`acceptedDate`** (precise timestamp), `reportUrl`, `filingUrl` |
| **`fda_calendar()`** | **593 rows**: `fromDate`, `toDate`, `eventDescription`, `url` |
| **`company_earnings(symbol, limit)`** | `estimate`, `actual`, `period`, `surprise`, `surprisePercent`, `year`, `quarter` |
| `stock_insider_transactions` | `name`, `share`, `change`, `filingDate`, `transactionCode`, `transactionPrice` |
| `ipo_calendar(from, to)` | `date`, `exchange`, `price`, `status`, `symbol`, `totalSharesValue` — forward-looking |
| **`market_holiday(exchange)`** | `eventName`, `atDate`, **`tradingHour`**, `postMarket` + timezone |
| `market_status(exchange)` | `isOpen`, `session`, `holiday`, `timezone` |
| `quote(symbol)` | `c, d, dp, h, l, o, pc, t` |
| `symbol_lookup(query)` | `description`, `displaySymbol`, `type` |
| `country()` | **249 countries** with `currencyCode`, `equityRiskPremium`, `defaultSpread`, rating |
| `stock_lobbying` | Senate LDA filings with `documentUrl` |

Measured, for the two that carry the most:

```
market_holiday('US') -> {'eventName': 'Thanksgiving Day', 'atDate': '2027-11-26',
                         'tradingHour': '09:30-13:00', 'postMarket': '13:00:17:00'}
company_earnings('AAPL', limit=4) -> [{estimate 1.9271, actual 1.91, period '2026-06-30',
                                      surprise -0.0171, surprisePercent -0.8873}, ...]
```

**Two caveats that decide how each is used.**

1. **`fda_calendar` is the advisory-committee meeting calendar, not PDUFA action dates.**
   It lists FDA advisory panels (`"Vaccines and Related Biological Products Advisory
   Committee October 1, 2026 Meeting Announcement"`). That is a **complement** to
   `dataflows/event_calendars.py`'s pdufa.bio source, never a replacement — conflating the
   two would put a committee meeting where the panel reads an approval date.
2. **A recorded claim needs one refinement, not a correction.** `AGENT_ONBOARDING.md`
   lists `earnings-surprises` as 403. It is — but **`company_earnings` works** and returns
   `surprise` / `surprisePercent`. They are different routes; the note is not wrong about
   the one it names, it simply does not cover the one that answers.

### yfinance — keyless, and almost all of it live

| surface | verified |
|---|---|
| **`eps_trend`** | `DataFrame (4, 6)` — `current`, `7daysAgo`, `30daysAgo`, `60daysAgo`, `90daysAgo` |
| **`eps_revisions`** | `DataFrame (4, 5)` — `upLast7days`, `upLast30days`, `downLast30days`, `downLast7Days` |
| `earnings_estimate` / `revenue_estimate` | `avg, low, high, yearAgoEps, numberOfAnalysts` |
| `earnings_history` | `epsActual, epsEstimate, epsDifference, surprisePercent` |
| `growth_estimates` | `stockTrend`, `indexTrend` |
| `calendar` | forward earnings date + `Earnings High/Low/Average`, `Revenue High/Low`, ex-div |
| `sec_filings` | 80 rows: `date`, `type`, `title`, `edgarUrl` |
| `valuation` (`get_valuation_measures`) | `DataFrame (9, 6)` — valuation measures over six periods |
| `ttm_income_stmt` / `ttm_cash_flow` / `ttm_financials` | 33 / 45 / 33 rows |
| `shares_full` | share-count **time series** (7 dated points) |
| `recommendations` | `strongBuy, buy, hold, sell` by period |
| `actions` | 97 rows — Dividends **and** Stock Splits |
| `mutualfund_holders` | 10 rows |
| `analyst_price_targets` | `current, high, low, mean, median` |
| **`yf.screen(EquityQuery(...))`** | the modern query screener → `{start, count, total, quotes}` |
| `yf.Calendars().get_earnings_calendar(start, end)` | earnings calendar by **date range** |
| `yf.Market('US').status`, `yf.Sector(...).overview`, `yf.Industry(...).overview` | market status; sector/industry `market_cap`, `employee_count`, `market_weight` |
| `yf.Search`, `yf.Tickers`, `yf.download` | symbol search; batch tickers; batch OHLCV |

**Empty or broken (do not plan against these):**

| surface | result |
|---|---|
| `sustainability` | **EMPTY** — `HTTP 404 "No fundamentals data found for symbol: AAPL"` |
| `capital_gains` | EMPTY — a fund-only field |
| `isin` | the placeholder `'-'`, not an ISIN |
| `Ticker.earnings` | **deprecated** (`DeprecationWarning`), returns `None` — use `income_stmt` |

---

## Fit against the repo (grounded, not inferred)

| Capability | What it replaces or fills | Existing seam |
|---|---|---|
| **`eps_trend`** | a **documented `unavailable`** | `strategies/analyst_revisions.py::estimate_change_index` (`:176`) |
| **`eps_revisions`** | the upgrade/downgrade **proxy** | `dataflows/yfinance_sector.py::fetch_revision_actions` (`:106`) → `analyst_revisions.revision_ratio` (`:79`) |
| `calendar`, `yf.Calendars` | a date-range earnings calendar | `moomoo.get_earnings_calendar_moomoo` (7-day cap) |
| `sec_filings`, finnhub `filings` | a filings index with precise acceptance times | `dataflows/sec_edgar.py` (already the producer) |
| `shares_full` | share-count history | `scripts/score_panel.py`'s market-cap join |
| `valuation` | valuation history | `strategies/ratios.py` |
| `yf.screen(EquityQuery)` | the legacy screener submodule | `dataflows/screener.py:22` (`from yfinance import screener as _yf_screener`) |
| finnhub `market_holiday` | no holiday/half-day source | `strategies/market_session.py` |
| finnhub `financials_reported` | as-reported + `acceptedDate` | `sec_edgar.py` (cross-check only) |
| finnhub `country` | a per-country ERP table | `strategies/dcf.py::wacc_from_beta` (`:28`) — the ERP is a hardcoded `erp=0.05` default, not a sourced value |

### The headline, in full

`strategies/analyst_revisions.py` states its own gap in its module docstring (`:14-18`):

> `estimate_change_index` … **"The engine has current consensus and price targets only,
> never a 3-4 quarter estimate history, so this leg returns `unavailable` with the
> missing-input reason; it never fabricates levels."**

The producer needs `len(weights) + 1` levels — `DEFAULT_ESTIMATE_WEIGHTS = (9, 7, 5, 3)`
(`:43`), so **five** — and its refusal message names the missing object verbatim
(`"the engine has current consensus and price targets only, not a 3-4 quarter estimate
history - levels are never fabricated"`).

**Production never supplies them.** `revision_index(history, levels=None, ...)` (`:279`)
defaults `levels` to `None`, and the only call site that ever passes a value is a test
(`tests/test_analyst_revision_index.py:180`). The leg is therefore structurally
`unavailable` in every real run.

`eps_trend` returns exactly five levels. The gap and the fill are the same shape.

---

## Constraints

1. **Rule 15 governs two of these.** `statement_parsing.trailing_twelve_months` (`:1270`)
   opens with *"**One producer** for a trailing-twelve-month total."* — so yfinance's
   `ttm_income_stmt` / `ttm_cash_flow` **cannot** be adopted as a contributor. Same for
   finnhub `financials_reported` beside `sec_edgar`: a cross-check, never a second
   contributor.
2. **The finnhub free tier is a hard wall, and it has moved before.** 49 of 61 probed
   endpoints are 403. Anything finnhub-backed must degrade to `unavailable` and fall
   through, and the probe in this document is the boundary to re-check, not a guarantee.
3. **yfinance is keyless but unversioned.** It scrapes Yahoo; field names and availability
   shift between releases, and `Ticker.earnings` is already deprecated in this one. Every
   adopted property needs its columns asserted in a test, and a missing frame must degrade
   rather than raise.
4. **`eps_trend` is point-in-time only.** It returns the *current* five-level snapshot with
   no date parameter, so it cannot be backfilled — the same limitation the Heat List has.
   A factor built on it can only be accumulated forward.
5. **Gate-off byte-identity.** The new leg lands behind a gate, default `False`, and a
   gate-off run must be byte-identical to today's (`docs/gate_registry.md`, machine-checked
   by `tests/test_gate_env_toggles.py`).
6. **Do not collapse the two revision sources.** `eps_revisions` gives direct up/down
   *counts*; `upgrades_downgrades` gives graded *actions*. They are different objects with
   different denominators, and `analyst_revisions.py` already prints a
   `DENOMINATOR_NOTE` (`:45`) precisely because the denominator is not MSCI's. A new source
   must state its own denominator rather than inheriting the old one.

---

## Design

### Gate

**`enable_analyst_estimates`** — new, verified absent from the tree. Default `False`, with
an `_ENV_OVERRIDES` row, a `.env.example` line, and a `docs/gate_registry.md` row added in
the same commit that adds the `DEFAULT_CONFIG` key (the registry is machine-checked, so the
row and the key must land together).

### Module layout

The estimator is a **reader**, and it belongs beside the existing proxy rather than in a new
file — `dataflows/yfinance_sector.py` already owns *"the two Phase-1/2 inputs the moomoo
vendor chain does not cover"* (`:1-3`), one of which is the revision proxy this replaces.

```
tradingagents/dataflows/yfinance_sector.py
   fetch_revision_actions      (:106)   existing - graded actions (the proxy)
   fetch_estimate_trend        (new)    the five-level estimate series  <- the fill
   fetch_eps_revisions         (new)    the direct up/down counts
```

Both new readers follow the module's existing contract: daemon-thread guarded with a
timeout, `None` on any failure, and the caller prints `n/a` rather than fabricating.

### Wiring into the engine

`analyst_revisions.revision_index(history, levels=...)` already accepts `levels`. The
change is at the **caller**: `scripts/value_screener.py::_fetch_revision_guarded` (`:988`)
currently supplies only `history` (for `revision_ratio`); it gains the levels when the gate
is on, and passes `levels=None` when it is off — which is today's path exactly.

**No new computation is added to `analyst_revisions.py`.** The module is pure and offline
by design (*"No network, no state, no LLM"*, `:24`); the fetch belongs in the dataflow layer
and the arithmetic stays where it is.

### What the output must print

Per the house convention, and because this leg exists to replace an `unavailable`:

- the **five levels as given**, most-recent-first, with the source named — the leg's own
  docstring says levels are *"used as given, never imputed"*;
- the **as-of time** of the snapshot (it is a current read, not a dated close);
- **which leg is measured and which is not** — the whole point of the change is that a
  previously-`unavailable` leg now reports a number, so a run where it is still absent must
  say why rather than looking like the old behaviour;
- the **denominator note** for the ratio leg, unchanged.

---

## Implementation plan

| Phase | Work | Acceptance |
|---|---|---|
| **P0** **BUILT 2026-09-18** | `fetch_estimate_trend` + `fetch_eps_revisions` in `yfinance_sector.py`, behind `enable_analyst_estimates` | Live: a five-level series for a large cap; `estimate_change_index` returns an index instead of `unavailable`; gate off ⇒ byte-identical |
| **P1** **BUILT 2026-09-18** | `_fetch_revision_guarded` supplies `levels` when the gate is on | The `RevIdx` column carries both legs; a run with the source down still prints the old `unavailable` with its reason |
| **P2** | finnhub `market_holiday` reader + a holiday/half-day basis in the session read | Thanksgiving renders `09:30-13:00` as a half-day, not a full session; a missing holiday table degrades to today's behaviour |
| **P3** | `shares_full` as a **diagnostic** on the panel's market-cap join | A share-count change between two periods is named, not silently multiplied through — the SIMO defect class, detected mechanically |
| **P4** | finnhub `country` as an ERP source for the DCF's discount rate | The ERP prints its country and its source, or stays the current override with the reason |
| **P5** | Deferred: `yf.screen(EquityQuery)` replacing the legacy screener submodule | Only if a screener query needs the modern operators; the legacy path works today |

Each phase lands alone, gate off by default, with its own failing-first test and a
`CHANGELOG` entry. **P0/P1 is the one worth doing**; P2–P5 are independent.

---

## Open questions

1. **Is `eps_trend`'s "current" the same consensus as `earnings_estimate`'s `avg`?** If
   they disagree, one is a different basis and the leg would splice two sources. Close by
   comparing both for 20 names on one date and recording the result.
2. **What is `eps_trend`'s window convention?** The columns are `7daysAgo`…`90daysAgo`, but
   `estimate_change_index` documents *"a most-recent-first **quarterly** estimate series"*.
   A 90-day trailing window is not four quarters. Close by reading the vendor's definition
   before wiring — and if it is not quarterly, the leg must say which series it used.
3. **Does the free-tier finnhub key change between sessions?** The 403 set was measured
   once. Close by re-running the probe in Appendix A before adding any finnhub dependency.
4. **Does `shares_full` cover the foreign-filer case?** The SIMO defect was an ADS ratio,
   not a share-count change; confirm what the series returns for a 20-F filer.
5. **Is `sustainability` empty only for AAPL?** It 404s here; that may be per-symbol rather
   than unavailable. Not worth closing unless an ESG input is ever wanted.

---

## Recommendation

Do **P0 and P1**. They are small, additive, gated, and they close a gap the repo wrote down
about itself — a production leg that can never fire because its input has no producer. That
is a better reason to act than "one more data source".

Do **P2** if the session logic is being touched anyway (half-day handling has no source
today). Treat **P3–P5** as separate decisions.

**Do not** adopt the finnhub 403 set, the yfinance `ttm_*` family as a contributor, or
`financials_reported` as a second statement producer. Those are three different routes into
the same rule-15 violation, and two of them are already documented as single-producer seams.

---

## Appendix A — finnhub: the 403 set (probed 2026-09-18, never wire)

**48 endpoints, grouped. Every one returned `403 You don't have access to this resource.`**

| family | endpoints |
|---|---|
| Estimates (11) | `company_eps_estimates`, `company_revenue_estimates`, `company_ebitda_estimates`, `company_fcf_estimates`, `company_ebit_estimates`, `company_net_income_estimates`, `company_capex_estimates`, `company_dps_estimates`, `company_gross_income_estimates`, `company_pretax_income_estimates`, `company_ocf_estimates` |
| Analyst / ownership (7) | `upgrade_downgrade`, `institutional_ownership`, `fund_ownership`, `ownership`, `price_metrics`, `sector_metric`, `historical_market_cap` |
| News / sentiment / regulatory (7) | `news_sentiment`, `sec_sentiment_analysis`, `sec_similarity_index`, `congressional_trading`, `press_releases`, `stock_investment_theme`, `stock_presentation` |
| Technicals (6) | `technical_indicator`, `pattern_recognition`, `support_resistance`, `aggregate_indicator`, `stock_candles`, `last_bid_ask` |
| Filings / corporate (5) | `international_filings`, `isin_change`, `symbol_change`, `historical_employee_count`, `stock_revenue_breakdown` |
| Options / ETFs (4) | `option_chain`, `etfs_holdings`, `etfs_profile`, `etfs_sector_exp` |
| Transcripts / executives / ESG / quality (4) | `transcripts_list`, `company_executive`, `company_esg_score`, `company_earnings_quality_score` |
| Dividends (2) | `stock_dividends`, `stock_basic_dividends` |
| Macro / reference (2) | `economic_data`, `indices_const` |

**Also failing, differently:** `exchange` returned HTML rather than JSON
(`FinnhubRequestException: Invalid Response`), so it is not a 403 — it is not a usable
route in this SDK version at all.

---

## Appendix B — yfinance: the unused surface

**Module functions (5):** `download` *(used)*, `screen` *(unused — the repo drives the
legacy `screener` submodule instead, `dataflows/screener.py:22`)*, `enable_debug_mode`,
`set_config`, `set_tz_cache_location`.

**Classes (15):** `Ticker` *(used)* and `Search` *(used)*; unused — `AsyncWebSocket`,
`Auth`, `Calendars`, `EquityQuery`, `ETFQuery`, `FundQuery`, `Industry`, `Lookup`, `Market`,
`MarketRegion`, `Sector`, `Tickers`, `WebSocket`.

**`Ticker` properties — 17 of 54 used, 37 unused** (8 of the 37 are pure aliases of a
sibling, marked *alias*):

| status | properties |
|---|---|
| **USED (17)** | `analyst_price_targets`, `balance_sheet`, `cashflow`, `dividends`, `fast_info`, `funds_data`, `income_stmt`, `info`, `insider_transactions`, `institutional_holders`, `major_holders`, `options`, `quarterly_balance_sheet`, `quarterly_cashflow`, `quarterly_income_stmt`, `recommendations_summary`, `upgrades_downgrades` |
| **UNUSED — the useful ones** | `eps_trend`, `eps_revisions`, `earnings_estimate`, `revenue_estimate`, `earnings_history`, `growth_estimates`, `calendar`, `sec_filings`, `valuation`, `ttm_income_stmt`, `ttm_cash_flow`, `ttm_financials`, `shares_full`, `shares`, `recommendations`, `actions`, `splits`, `mutualfund_holders`, `insider_purchases`, `insider_roster_holders`, `history_metadata`, `financials`, `quarterly_financials`, `quarterly_earnings` |
| **UNUSED — empty or dead** | `sustainability` *(404, empty)*, `capital_gains` *(fund-only, empty)*, `isin` *(returns `'-'`)*, `earnings` *(deprecated, `None`)* |
| **UNUSED — aliases** | `balancesheet`, `cash_flow`, `incomestmt`, `quarterly_balancesheet`, `quarterly_cash_flow`, `quarterly_incomestmt`, `ttm_cashflow`, `ttm_incomestmt` |

**`Ticker` methods — unused:** `get_calendar`, `get_capital_gains`, `get_earnings`,
`get_earnings_estimate`, `get_earnings_history`, `get_eps_revisions`, `get_eps_trend`,
`get_growth_estimates`, `get_history_metadata`, `get_isin`, `get_mutualfund_holders`,
`get_recommendations`, `get_revenue_estimate`, `get_sec_filings`, `get_shares`,
`get_shares_full`, `get_sustainability`, `get_valuation_measures`, `live`.

**Methods used (for contrast):** `history`, `option_chain`, `get_info`, `get_news`,
`get_earnings_dates`, `get_funds_data`.
