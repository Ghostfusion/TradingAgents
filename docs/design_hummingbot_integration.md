# Hummingbot v2 — Teacher Study for TradingAgents

Status: **design study only — no code changes.** Direct-source study of
`github.com/hummingbot/hummingbot` (2025 V2 framework: `StrategyV2Base` /
Controllers / Executors / Connectors, backtesting executors-simulators,
paper-trade connector, candles feeds, MQTT/API remote iface, budget
checker, notifier, SQLite executor ledger), plus web grounding on the
current framework state, LLM/dashboard integrations and the encrypted
credential model. Everything here is **advisory and opt-in**; the fork's
"no execution, no RL runtime, advisory-first" mandates are unchanged.

---

## 1. The one-paragraph takeaway

Hummingbot is a **live-market execution framework**; TradingAgents is a
**research layering without an execution mandate**. The V2 framework's
core lesson is that the SAME executable contract (`ExecutorAction` /
executor lifecycle) runs identically in **live, paper-trade and backtest**
modes — the backtest is not a separate code path but the same strategy
loop replayed against a simulated connector with per-executor fill
simulators. The fork's equivalent contract is `research_decision.json` +
`market_tradability` + `backtest_engine`; what Hummingbot adds is the
discipline of making that contract **the only object the layers exchange**,
with explicit `CloseType` accounting, per-executor PnL columns, and a
persisted executor ledger.

## 2. What Hummingbot does that this fork's docs/plan already anticipated

| Hummingbot mechanism | Fork equivalent | Verdict |
| --- | --- | --- |
| `ExecutorAction` (Create/Stop/Store) as the single strategy→executor contract | `research_decision.json` (hash-pinned execution contract, fail-closed, `write_research_decision`) | already the fork's contract; Hummingbot validates the pattern |
| Paper-trade connector: live book + queued fills + simulated balances | `backtest_engine` next-bar fills + `market_tradability` gates + paper ledger (`pre_market.record_review` resolved returns) | fork is backtest/paper-analogue; the *live-book* fill latency model is new |
| `TripleBarrierConfig` (stop / take-profit / time-limit / trailing) | G1 position contract (`stop_loss`/`target`/`time_limit` + `exits.trailing_stop_exit` / `stop_to_breakeven`) | already adopted (trailing even has the ATR-multiplied variant) |
| Circuit breaker + kill switch + heartbeat (signald) | `vendor_breaker` (3-fail circuit), hash-chained risk/audit ledgers, `monitor.notify` webhook | already present; Hummingbot adds degraded-mode observability polish |
| Budget checker / `OrderCandidate` collateral | `risk_checks.pre_trade_check` notional cap + `RateLimiter` | notch below; see §3.2 |
| SQLite executor ledger with indexes + `to_executor_info()` | alpha ledger + prediction ledger + `positions_to_basket` book JSON | fork has distinct ledgers; Hummingbot's unified per-executor PnL columns are the inspiration for §3.4 |
| Candles feeds (typed `CandlesConfig` per exchange) | vendor `get_stock_data` chains + `_RUN_OHLCV_CACHE` | fork caches run-level; Hummingbot's historical-candle + webSocket candle polling is the fast-path T0 data source |

## 3. Adoptable lessons (phase-gated, advisory-first)

### 3.1 — Backtest honesty: per-executor ClosedType accounting (small, testable)

**What:** Hummingbot's backtesting engine drives the SAME controller loop
and attributes every executor with a `CloseType` from an enum — `STOP_LOSS`
/ `TAKE_PROFIT` / `TIME_LIMIT` / `TRAILING_STOP` / `EXPIRED` / `FAILED` / …
— plus `net_pnl_pct` / `net_pnl_quote` / `cum_fees_quote` /
`filled_amount_quote` per executor. The report's with/without-cost table
already separates cost; what's new is the **exit-accounting discipline**: a
maker order whose level never tagged within the window is `EXPIRED` (resting,
not failed), and the sim must not re-quote it every tick (a confirmed bug
they fixed — see `order_executor_simulator.py`).

**Gap in the fork:** `backtest_engine`/`backtest_strategy` report
`exit_label` (`stop`/`target{tgt}`/`none`) but there is no ledger of
exit-cause frequency. The alpha-decay monitor tracks *hit rate*, not
*which barrier exits* (a stop-heavy book behaves differently from a
time-limit-heavy one).

**Adopt (Phase-1, small):**
- New pure fn `strategies/exits.py::exit_cause_frequency(rows,
  causes=("stop","target","trailing","time","expired"))` — histogram over
  backtest rows.
- Extend `scripts/backtest_strategy.py` to tag fills with a canonical
  `close_type` (map `exit_label` → enum string) and `backtest_engine`
  execution rows with `net_pnl_pct` / `cum_fees_quote` columns.
- `strategy_quality_report` gains an "exit causes" block.
- Web Value Tools += `exit_cause_read` (advisory, market node).

### 3.2 — Pre-trade budget as a *stateful*, cash-aware checker (small)

**What:** Hummingbot's `BudgetChecker` is a persistent object: it locks
collateral on order placement, holds it while the order rests, and releases
on fill/cancel — one place answers "what can this book actually afford"
(notional + locked balance + fees), and the paper-trade connector uses the
SAME checker for its simulated balances.

**Gap in the fork:** `risk_checks.pre_trade_check` validates a single order
(notional cap + rolling rate) but is **stateless** — no notion of a resting
book's locked collateral, and the paper/backtest fills don't share its
envelope. The G1 contract handles one position; a multi-position plan has
no collateral lock.

**Adopt (Phase-2, small):**
- `strategies/risk_checks.py`: add `CollateralLock` (per-symbol locked
  notional, acquire/release, `available(account, locked_by_symbol)`), pure +
  documented. Wire `get_pre_trade_read` to report `locked`/`available`
  next to `max_notional`.
- `scripts/backtest_strategy.py` fills call the same `CollateralLock` so
  a backtest can never over-commit the simulated account (parity with the
  paper connector's budget model).

### 3.3 — A paper-connector analogue: live-book fill-latency model (Phase-3)

**What:** the paper-trade connector is a real `ExchangeBase` that consumes
the LIVE tracked order book: market orders queue for `TRADE_EXECUTION_DELAY`
seconds then fill at the book midpoint; limit orders rest until crossed by
an actual `OrderBookTradeEvent`. It is a live-market **simulation
connector**, distinct from the historical backtest.

**Gap in the fork:** `market_tradability` (limit-up/down, suspension,
participation, deal-price) + Alpaca IEX checks cover fills's constraints but
there is no fill-latency model — a "paper" that fills instantly vs a real
queue.

**Adopt (Phase-3, advisory tool, default-off):**
- `strategies/market_tradability.py`: `fill_latency_model(bar, delay_secs,
  trade_volume)` + `paper_fill_price(book_mid, kind)` (queued-market /
  crossed-limit, deterministic, seeded) — mirrors Hummingbot's
  `TRADE_EXECUTION_DELAY` + crossed-limit match. Rendered in
  `get_fill_model_read` as advisory "paper-fill model" columns, default off.
- Gate note: this models latency, never the availability of a fill — the
  fork stays **advisory**, no live order is emitted.

### 3.4 — One unified executor-ledger row shape (Phase-4)

**What:** `hummingbot/model/executors.py` persists every executor as ONE
row: id, type, close_type, status, config(JSON), net_pnl_pct, net_pnl_quote,
cum_fees_quote, filled_amount_quote, is_active/is_trading, custom_info,
controller_id — indexed on (type,status) and (type,timestamp).

**Gap in the fork:** the alpha ledger, prediction ledger and
positions_to_basket book are separate JSONL/JSON artifacts with partially
overlapping fields (rating vs outcome vs pnl) and no unified "did this
decision cost money" row.

**Adopt (Phase-4, docs-only today):** a `strategies/executor_ledger.py`
schema spec (not code yet) that future paper-book writes can conform to:
reuse the alpha-ledger row, add `close_type` + `net_pnl_quote` +
`cum_fees_quote` + `filled_amount_quote` + `controller_id` — the columns
that already exist across ledgers, unified. Keeps `run_card` +
`research_decision.json` as the emission contract.

### 3.5 — Async queue notifier (small, adopt now)

`monitor.notify` is a synchronous webhook POST (default-off). Hummingbot's
`NotifierBase` is an async queue + a pollable `_send_message` with a
retry-safe loop. Adopt: make `monitor.notify` push to a module-level
`asyncio.Queue` drained by one task (config-gated, default off), so a slow
webhook can never block the decision path.

## 4. Explicit non-goals (reasons)

| Hummingbot surface | Why not adopt |
| --- | --- |
| Live-exchange execution / order management (CEX/DEX connectors, Gateway) | fork is explicitly **advisory-only, no execution layer**; `TradingExecution` is the phase-gated successor and already consumes the contract |
| `StrategyV2Base` + Controllers + Executors runtime loop | a runtime of concurrent live strategies conflicts with the fork's single-shot research graph; the fork's overlay pipeline (regime→catalyst→contract→governor) is its analogue |
| Triple-barrier full runtime (activation/trailing state machine) | the fork's G1 + exits layer already covers the barriers; only the **accounting** discipline is adopted (§3.1) |
| Encrypted credential keystore / dashboard auth | fork is analysis-only, `.env` API keys, no broker keys to store; `trading_web` already holds its own HMAC/scrypt auth |
| WebSocket market-data feeds per exchange | fork is daily-bar research; the fast-path T0 design (design_market_refresh_fastpath.md) is the right place, not this study |
| MCP/skills for LLM control of the bot | the fork's "LLM proposes, math decides" is exactly the inverse (no LLM executes); the dashboard's MQTT command surface is antithetical |

## 5. Phases (dependency-ordered, all advisory + default-off)

1. **P1 — Exit-accounting** (§3.1): `exit_cause_frequency` +
   `close_type` tagging in backtest fills + "exit causes" report block +
   `exit_cause_read` tool. Tests: histogram of planted rows, unknown-cause
   slot, empty → None.
2. **P2 — Collateral lock** (§3.2): `CollateralLock` + `available()`
   surfaced in `get_pre_trade_read`; backtest fills share the envelope.
   Tests: acquire/release, account-deficit → blocked, multi-symbol locks.
3. **P3 — Fill-latency paper model** (§3.3): `fill_latency_model` +
   `paper_fill_price` advisory reads (default off) + `get_fill_model_read`
   tool. Tests: queued-market fills after delay, crossed-limit never fills
   without a trade, deterministic seed.
4. **P4 — Executor-ledger schema** (§3.4): docs-only spec +
   `executor_ledger.py` schema; future paper-book writes conform. Test:
   schema-validate the existing alpha-ledger rows.
5. **P5 — Async notifier** (§3.5): queue-drain `monitor.notify` (config
   gate, default off). Test: queue drains in order, slow webhook never
   blocks.

## 6. Honest limits

- **No live-market validation**: every adopted piece is exercised in the
  hermetic backtest suite only; the fill-latency model is a **model**,
  stated as such (deterministic, seeded — never a claim of real fill
  behavior).
- **Backtest-vs-paper gap accepted**: our paper/backtest shares the OHLCV
  close path; Hummingbot's paper-trade connector simulates against a LIVE
  order book. We adopt the *contract* (`ExecutorAction`-like rows,
  `CloseType` accounting, budget lock), not the live-book simulation —
  covers the same decision inputs without a market-data plumbing change.
- **Notational matching**: `close_type` strings must match
  `backtest_strategy` exit labels exactly; keep a single canonical map to
  avoid drift between the tool and the report.

## 7. Validation & sequencing

Each phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs (`api_reference.md` §6 tool row + §1.1 config
keys, `Strategies/index.md`, AGENT_ONBOARDING.changelog, CHANGELOG,
README News) and trading_web mirror (Value Tools += the new reads). No
behavior changes when the config keys are off (defaults off).

Mapping: **§3.1 → P1** (backtest + report + tool), **§3.2 → P2** (risk
checks + backtest), **§3.3 → P3** (tradability + tool), **§3.4 → P4**
(ledger spec), **§3.5 → P5** (monitor). P1/P2/P3/P5 are independent; P4 is
a spec only and depends on nothing.