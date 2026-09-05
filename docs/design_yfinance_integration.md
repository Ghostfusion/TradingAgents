# yfinance (ranaroussi) — Teacher Study for TradingAgents

Status: **design study only — no code changes.** Direct-source study of
`github.com/ranaroussi/yfinance` v1.7.0 (the v2 rewrite: `data.py` YfData +
Auth, `_http.py` backend abstraction, `cache.py` SQLite KV caches,
`base.py` TickerBase, `scrapers/` price-history/quote/fundamentals,
`multi.py` download, `calendars.py`, `live.py` WebSocket, `pricing.proto`,
`screener/` typed queries, `lookup.py`, `exceptions.py`), plus a full
inventory of the fork's existing yfinance integration and web grounding on
the 1.x migration. Everything here is **advisory and opt-in**; the fork's
no-execution / advisory-first / stateless-per-run conventions stand. yfinance
is one of the fork's no-key vendors (OHLCV, fundamentals, statements,
options, short interest, insider/13F, news, screener); the mapping targets
`tradingagents/dataflows/` and the web mirror where a read envelope changes.

---

## 1. The one-paragraph takeaway

yfinance at 1.7.0 is a mature tolerance lab for exactly the fork's hardest
vendor problem: an **unauthenticated scraping-style data source**. Three
disciplines carry the whole library and are the transferable core:

1. **A typed absence taxonomy, not a bare "no data".** Every failure mode has
   its own exception carrying the *reason*: `YFTickerMissingError` (with a
   rationale and a "possibly delisted" speculation flag that callers can
   switch off when the real cause is known), `YFPricesMissingError` (with
   `yahoo_reason` — when Yahoo itself explains the absence, the explicit
   reason REPLACES the speculation), `YFTzMissingError`, `YFInvalidPeriodError`
   (carries the valid options in the message), `YFRateLimitError`. "Why is
   the data missing" survives the data layer in a machine-readable form.
2. **A graceful-degrade vs fail-loud split.** Transient or optional failures
   degrade and continue — the cookie fetch from `fc.yahoo.com` can fail
   behind a proxy and the data request proceeds without it; a rate-limited
   crumb fetch is skipped because the target endpoint may not need a crumb;
   a consent page is auto-accepted by form parsing. Structural failures
   still raise. Nothing ever masquerades as data.
3. **Persistent per-ticker metadata with validation and invalidation.**
   Exchange timezone is fetched once per ticker, cached to disk (SQLite,
   WAL), validated with `is_valid_timezone`, invalid entries evicted and
   re-fetched, with a capped fallback; `HistoryMetadata` attaches
   `currency` / `tradingPeriods` lazily so the base history fetch never pays
   for an intraday metadata call it doesn't need.

The fork has already adopted several yfinance-adjacent halves (retry with
backoff, typed vendor errors, stale-frame guards, statement-currency
heuristics — §2). The genuinely new adoptions are the **exchange-tz cache on
OHLCV reads** (the fork's daily closes are naive dates; no per-ticker tz or
currency is carried), **typed absence reasons reaching the ledger/run_card**
(instead of silent n/a), **100x OHLCV currency-unit repair** (detected and
flagged, never silent), **batch error grouping** and a **deliberate version
pin** on the 1.x line.

## 2. What yfinance does that the fork already implements (validated)

| yfinance mechanism | Fork equivalent | Verdict |
| --- | --- | --- |
| `YFRateLimitError` on HTTP 429 | `stockstats_utils.yf_retry` (exponential backoff, 3 retries, base 2.0s, only rate limits retried) + `VendorRateLimitError` routing fall-through | already adopted; the 429→distinct-backoff nuance is noted in A3 |
| Typed error taxonomy (`NoMarketDataError`-style signals) | `dataflows/errors.py` (`NoMarketDataError`, `VendorRateLimitError`, `MoomooNotConfiguredError`) + `route_to_vendor_typed` → `VendorResult` | already adopted; the **absence *reason* propagation** (§3.1) is the new bit |
| Only successes cached; failures never cached | `vendor_cache.py` disk TTL 6h, successes only, sentinels (`NO_DATA_AVAILABLE` / `DATA_UNAVAILABLE` / `DATA_DISABLED`) never cached; `news_data` skipped as live | already adopted |
| `end` is EXCLUSIVE (callers must +1 day) | `stockstats_utils` comment-guaranteed `end_str = today + 1d` (#986) | already adopted |
| Stale-frame guard against year-old frames | `MAX_OHLCV_STALE_DAYS = 10` vs the #1021 quirk | already adopted |
| Financial statements newest-first columns | `statement_parsing._parse_csv_statements` takes the FIRST numeric cell (the rightmost-cell bug is fixed and commented) | already adopted |
| Currency-mixup detection in statements | ADR heuristic in `statement_parsing`: assets/market-cap > 1000x ⇒ mixed currencies, USD-only metrics refuse | already adopted for statements; **OHLCV 100x unit repair (A4) is the gap** |
| Blank/garbage ticker must not reach the vendor | `symbol_utils.normalize_symbol` central mapping + blank guard (no raw `TypeError` from yfinance) | already adopted |
| One fetch per (ticker, window) per run | `_RUN_OHLCV_CACHE`, news `CoalescingCache` (owner-wait), factor-expression cache | already adopted |
| Cookie-strategy toggle on repeated 4xx | moomoo gateway probe TTL (`_PROBE_FAIL_TTL` — degradable fallback stays cheap) | analogous discipline, already adopted |
| Free screener via predefined queries | `dataflows/screener.py` wraps `yfinance.screener` predefined queries + movers | already adopted |
| Instrument identity (type/exchange) as context | `agent_utils` instrument identity (fail-open, cached once per process per ticker) | already adopted |

## 3. Adoptable lessons (phase-gated, advisory-first, default-off)

### 3.1 — Typed absence reasons through the read envelope (A1)

**What:** yfinance's exception classes carry *why* data is absent:
`YFPricesMissingError` with `yahoo_reason` (an explicit vendor explanation
replaces delisting speculation), `YFTickerMissingError` with `rationale` +
`possibly_delisted` flag, `YFInvalidPeriodError` with `valid_ranges`. The
reason is machine-readable and survives to the caller.

**Gap in the fork:** the vendor seam degrades to sentinel strings (`n/a`,
`NO_DATA_AVAILABLE`), which is correct fail-closed behavior, but the *reason*
is dropped — the ledger/run_card/"no data" rows do not record whether the
absence was "ticker not found", "no price data for range", "rate-limited",
or "vendor disabled". A disputed or repeated "no data" cannot be audited
without re-running the fetch.

**Adopt (Phase-A1):**
- `dataflows/errors.py` gains `VendorAbsence(reason, source, retryable,
  yahoo_reason=None)` — a data class, not an exception, produced by the
  router when every vendor in the chain reports the same typed absence (the
  router already distinguishes `NoMarketDataError` from
  `VendorRateLimitError`; now carry which one ended the chain).
- The OHLCV read envelope (`analysis_tools._ohlcv`) gains
  `absence: {reason, source, retryable} | null`; the batch/run_card renders
  it when present instead of a bare n/a.
- CLI period/interval validation (backtest/pipeline/ohlcv commands):
  validate up front with the valid options in the error message
  (`YFInvalidPeriodError` pattern) instead of a vendor round-trip.
- No behavior change when the envelope field is unused (defaults null).

### 3.2 — Exchange-tz cache for OHLCV reads (A2, the flagship)

**What:** `TickerBase._get_ticker_tz` fetches the exchange timezone once per
ticker, caches it to a disk KV (SQLite WAL), validates reads with
`is_valid_timezone`, evicts invalid entries and re-fetches, falls back to
`info` metadata at most twice (`_tz_info_fetch_ctr` cap), and passes the tz
into `PriceHistory` so history timestamps are exchange-local and
tz-aware (`ignore_tz` controls the returned index: intraday → most-common
exchange tz since 1.4.0; day+ → naive).

**Gap in the fork:** `stockstats_utils` / `_ohlcv` handle naive dates only;
no per-ticker exchange tz is fetched, cached, or validated. Daily-bar
alignment is fine for `1d` reads, but (a) session windows for intraday
vendors (Alpaca 1m, prepost) are not tz-correct, (b) `effective_date`
day-boundary logic cannot distinguish "exchange closed" from "no data",
(c) the currency of the price series (needed for §3.3) is nowhere on the
read.

**Adopt (Phase-A2, advisory, default-off key `enable_exchange_tz_cache`):**
- `dataflows/exchange_tz.py`: a small disk KV under `data_cache_dir`
  (JSON, atomic write — the `vendor_cache` pattern, not a new DB),
  `lookup(ticker) → tz | None`, `store` only on validated tz, invalid
  entries deleted. Reads validate via `zoneinfo`; a corrupt/unknown value
  is treated as a miss (the `is_valid_timezone` discipline).
- The OHLCV envelope gains `tz: str | null` (and `currency` when the vendor
  reports it — yfinance `info['currency']` / history metadata);
  intraday vendor windows align to the exchange tz instead of naive
  comparisons.
- Fallback is capped (at most one tz fetch per ticker per run) so a failing
  tz source never doubles vendor calls the way a per-row bug would.

### 3.3 — Lazy per-ticker metadata (currency/market-hours) (A3)

**What:** `HistoryMetadata` is a dict-like lazy wrapper — the intraday-only
`tradingPeriods` key is fetched on first access, never eagerly; currency and
exchange timezone ride the base history fetch as metadata formatted once
(`format_history_metadata`). `_CURRENCY_CONVERSIONS` (GBp/ILA/ZAc → 0.01)
turns quoted units into price-scale facts.

**Gap in the fork:** `statement_parsing` *infers* currency from
asset/market-cap scale (the 1000x ADR heuristic) because statements carry no
marker; the DCF/ADR logic comments call this out. A first-class
per-ticker `currency` from the vendor (already half-present via the
instrument-identity fetch in `agent_utils`) would turn inference into a
signal.

**Adopt (Phase-A3, small, rides A2):** reuse the A2 tz KV to also cache
`currency` (+ `exchange`); `statement_parsing` keeps its heuristic but
prefers the cached currency when present; OHLCV/statement reads accept the
envelope currency. Default-off; no behavior change while off.

### 3.4 — 100x OHLCV currency-unit repair, detected and flagged (A4)

**What:** yfinance `repair=True` detects "newer prices are 100x" unit
mixups (GBp = pence on LSE; KWF ÷1000; `_CURRENCY_CONVERSIONS`) by ratio
checks with tolerance (`abs(ss / currency_divide - 1) > 0.25` to suspect,
then per-row `(ratio / divide - 1).abs() < 0.05` to confirm), repairs the
series, and also fixes missing prices / bad dividend adjusts. Repair is
explicitly opt-in and documented.

**Gap in the fork:** the OHLCV price series has no unit-mixup detection —
a cross-listed ticker (e.g. LSE pence vs GBP) can quietly render 100x
returns into the momentum/knife/backtest layers. The fork already does the
statement-side version of this discipline (currency mixup refuse in
`statement_parsing`); the price side is missing.

**Adopt (Phase-A4, config-gated `repair_ohlcv_unit`, default off):**
- `dataflows/vendor_repair.py`: on OHLCV reads, when the series has a
  detectable ~100x/÷1000 unit step between two regimes, repair the newer
  bulk with the same tolerance discipline — and ALWAYS record a
  `repair: {detected, divide, rows}` field on the envelope. Repair is
  flagged, never silent; a repaired series is labeled advisory in the
  report.
- Refuse to repair when evidence is ambiguous (no tolerance pass) — same
  fail-closed spirit as `market_data_validator`.

### 3.5 — Batch error grouping + debug-serialize rule (A5)

**What:** `multi.py::download` collects per-ticker failures in a per-call
context (never raises for one bad ticker), then reports them GROUPED by
message with the symbol list per group (`errors.setdefault(err,
[]).append(ticker)`), with tracebacks at DEBUG level only. It also disables
multithreading when DEBUG logging is enabled because interleaved logs
defeat debugging — a deliberate observability rule.

**Gap in the fork:** `run_batch` records per-symbol success/failure rows
(fine), but the summary is not grouped by failure kind, and the
"debug ⇒ serialize" rule is absent (debug runs interleave per-ticker logs).

**Adopt (Phase-A5, small):** `batch.py` / `run_batch` summary section
groups failures by message with symbol lists (the exact
`errors.setdefault` shape); when `logging.DEBUG` is on for the run, batch
workers run single-threaded unless `--parallel` is explicit. Tests: grouped
summary shape; debug-serialize toggle.

### 3.6 — Deliberate version pin on the 1.x line (A6, doc + pin)

**What:** yfinance 1.4.0 changed `ignore_tz` semantics (intraday index now
converts to the most-common exchange tz instead of UTC); the 1.x line is a
rewrite (protobuf pricing, SQLite caches, `_http.py` backend). The fork's
quirk-guards (#986 exclusive-end, #1021 stale frames, unnamed-index rename)
are version-coupled by construction.

**Adopt (Phase-A6):** pin `yfinance~=1.4` (caret constraint preserves
quirk-compat within the studied line) in `requirements.txt` +
`pyproject.toml`, with a `dataflows/README` vendor-notes section listing the
guarded quirks + the version they were verified against; any major/minor
bump is a deliberate step with a re-run of the vendor tests (P5 A5 grouped
failure report makes the diff legible). Assessment only otherwise.

## 4. Explicit non-goals (reasons)

| yfinance surface | Why not adopt |
| --- | --- |
| WebSocket live pricing (`live.py`, `AsyncWebSocket`, `pricing.proto`) | streaming/real-time is out of scope in every prior teacher study; the fork is an advisory batch/research surface |
| Login cookies + subscription-tier scraping (`Auth`, OBI subscriptions endpoint) | no secrets or login states in the fork; the fork's vendors are keyed or anonymous APIs |
| SQLite persistent caches (peewee tz/cookie/ISIN KV, WAL) | the fork is deliberately stateless per run; A2's tz cache uses the existing `data_cache_dir` JSON/atomic-write pattern, not a new DB |
| curl_cffi TLS impersonation + session-type guard | the fork talks to keyed vendor APIs, not browser-fronted pages; only yfinance itself needs impersonation, and it owns that |
| ISIN→ticker lookup + ISIN cache | the fork's inputs are tickers; no ISIN-first requirement today |
| Typed screener query DSL (`EquityQuery`/`FundQuery`/`ETFQuery` + `screen`) | assessment only — the fork's `scan:` modes already cover the used cases; a DSL is a refactor, not a gap |
| `domain/` typed objects, `Lookup`, `Calendars` | stack-specific convenience layers with no fork gap |
| Persistent cookie/session reuse across runs | yfinance rotates its own; the fork's per-process sessions are the right lifetime for batch runs |

## 5. Phases (dependency-ordered, all advisory + default-off)

1. **P1 — Typed absence reasons (A1)**: `VendorAbsence` data class +
   router end-of-chain reason; OHLCV envelope `absence` field; CLI
   period/interval validation with valid options. Tests: chain-wide
   `NoMarketDataError` → typed absence; `VendorRateLimitError` →
   `retryable=true`; envelope null by default (no behavior change).
2. **P2 — Exchange-tz + currency cache (A2/A3)**: `dataflows/exchange_tz.py`
   (JSON KV, validated, invalidated, capped fetch) + `tz`/`currency` on the
   OHLCV envelope + `statement_parsing` prefers cached currency. Tests:
   valid/invalid tz cache entries, eviction+refetch, corrupt value =
   miss, one-fetch cap, currency preferred over the ADR heuristic.
3. **P3 — 100x unit repair (A4)**: `dataflows/vendor_repair.py`
   (config-gated) + `repair` field on the envelope; ambiguous series refuse
   to repair. Tests: synthetic 100x step repaired+flagged, ÷1000 (KWF),
   ambiguous refuses, off ⇒ passthrough.
4. **P4 — Batch grouping + debug-serialize (A5)**: `batch.py`/`run_batch`
   grouped failure summary + debug single-thread rule. Tests: grouped
   summary shape, serial toggle.
5. **P5 — Pin + vendor notes (A6)**: `yfinance~=1.4` pin +
   `dataflows/README` quirk notes (verified 1.4+), version-bump checklist.
   Doc + requirements only.

## 6. Honest limits

- **yfinance's tunings are its own**: `YfConfig.network.retries = 0`
  (no built-in retry — they let callers decide), 30 s timeouts, 8 KB→64
  activation budgets; the fork already chose `yf_retry`'s 3×2.0 s for the
  rate-limit case. Adopt the *taxonomy and the degrade/fail split*, not
  their knobs.
- **Repair is a heuristic**: the 100x check uses tolerance bands and can
  mis-detect in dead markets; A4's rule is "flag always, fix only when the
  ratio pass is unambiguous, refuse otherwise" — the fork's
  `market_data_validator` fail-closed spirit, not yfinance's
  `repair=True` default-off convenience.
- **The tz cache is the one persistent exception**: justified because
  exchange tz/currency change rarely and their cost is a whole vendor call;
  it stays validated + invalidatable + capped so it cannot silently serve
  stale metadata (mirrors `vendor_cache` TTL discipline).
- **No intraday adoption**: the study is about read-envelope discipline;
  intraday tz-awareness only lands where a vendor already serves intraday
  bars (Alpaca with a session window), not a new data source.
- **Version drift**: 1.x is actively rewritten (protobuf, SQLite caches);
  A6 pin is the shield — the quirk guards are coupled to the studied line.

## 7. Validation & sequencing

Per phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs true, trading_web mirrored where a read envelope
gains fields. No behavior change while the new config keys
(`enable_exchange_tz_cache`, `repair_ohlcv_unit`) are off (defaults off).
Live smokes: P1 — `get_ohlcv('ZZZZZZ')` envelope shows
`absence: {reason: "no data", retryable: true}` instead of a bare n/a;
P2 — `get_ohlcv('AAPL')` returns `tz: "America/New_York"` +
`currency: "USD"`; P3 — a synthetic 100x series (fixture) reports
`repair: {detected: true, divide: 100, rows: n}`; P5 — `pip check` +
vendor suite green under `yfinance~=1.4`.

Mapping: **A1 → P1**, **A2/A3 → P2**, **A4 → P3**, **A5 → P4**, **A6 → P5**.
P1 is the smallest and ships alone; P2 is the flagship and composes with the
ai-hedge-fund A2/P2 event-study phase (CAR significance wants
tz-consistent daily closes); P3 can batch with P2 (both touch the OHLCV
envelope); P4 is independent; P5 is the last gate before any future 1.x
bump.