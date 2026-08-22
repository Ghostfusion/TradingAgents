# 2.1 The end-to-end run — from decision to memory to report

This is a walk-through of one `propagate()` call, tying the topology
(`01-topology.md`) and edges (`02-graph-workflow.md`) to a concrete run. It is
the single best doc for understanding *what the system actually does* when you
run a ticker.

## Step 0 — a ticker arrives

```python
ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG)
final_state, decision = ta.propagate("NVDA", "2026-08-19")
ta.save_reports(final_state, "NVDA")
```

`propagate` is called with a `company_name` (or symbol) and a `trade_date`. It
optionally takes `asset_type` and `past_context`. Everything downstream is
driven by the graph + overlay flags.

## Step 1 — instrument identity + memory context

`create_initial_state` builds `messages=[("human","NVDA")]` plus:

- `instrument_context` — resolved by `resolve_instrument_context` (name,
  sector, exchange), injected into every analyst so they don't hallucinate a
  different company.
- `past_context` — the **memory log** ("past_context") string: same-ticker
  past decisions (pending vs resolved) + cross-ticker lessons. This is what
  makes repeat runs *remember*.

## Step 2 — the analyst teams & tool loops

Parallel (`concurrency>1`) or sequential, each analyst runs a
**tool-calling LLM loop**. The market, news, and fundamentals analysts call
`@tool`s that go through `route_to_vendor`; the sentiment analyst reads
pre-fetched news+stocktwits+reddit blocks injected in the prompt (no tools).
Each writes a report:
- `market_report` — technical/price regime + computed swings/RS/verdict.
- `sentiment_report` (social) — news/stocktwits/reddit.
- `news_report` — world + macro events + catalyst.
- `fundamentals_report` — value screens, quality, ownership.

The tool loops are **bounded** by `ConditionalLogic.should_continue_<analyst>`.

## Step 3 — Bull/Bear debate → Research Manager

Bull and Bear researchers argue over the analysts' reports for
`max_debate_rounds`. The **Research Manager** (a deep-think model) synthesizes
a `ResearchPlan` (`strategies/debate_context` may inject computed numbers) and
returns `investment_plan`.

## Step 4 — Trader

The Trader (quick-think) reads `investment_plan` and produces a
`TraderProposal` (action Buy/Hold/Sell, entry_price, stop_loss, position_sizing).

## Step 5 — Risk debate → Portfolio Manager

Aggressive/Conservative/Neutral risk analysts debate (`max_risk_discuss_rounds`).
The **Portfolio Manager** (deep-think) emits a structured `PortfolioDecision`
(rating, confidence, position_size, stop_loss, consensus). This lands in
`final_trade_decision` (or `trader_investment_plan` if earlier).

## Step 6 — deterministic overlays (post-graph)

`_apply_strategy_overlays` adjusts the decision deterministically:
regime/vol-target → orderflow → catalyst → position contract → risk governor →
computed context. It writes `strategy_overlays`, `position_contract`, `risk_gate`,
`risk_halt`, `computed_context` keys. With `enable_tranche_risk` on, the contract
uses the weighted tranche entry and the governor sizes against the worst-case
peak-deployed-at-scale-in + capital-at-risk (`tranche_context` on the state). A
REJECT sets `risk_halt=True`, which a downstream decision / portfolio step
 treats as "no position".

## Step 7 — persistence + memory

- `_log_state` writes `full_states_log_<date>.json`.
- `memory_log.store_decision(...)` appends a pending entry `[<date> |
  TICKER | rating | pending]`.
- On a **later** same-ticker run, `resolve` computes the realized return vs the
  regional benchmark index and marks it resolved with a reflection note.
- If `checkpoint_enabled`, a per-ticker SQLite resume is cleared on success.

## Step 8 — report + result

`save_reports` calls `reporting.write_report_tree` which writes:
- `1_analysts/{market,news,fundamentals,sentiment}.md`
- `2_research/{bull,bear,manager}.md`
- `3_trading/trader.md`
- `4_risk/{aggressive,conservative,neutral}.md`
- `5_portfolio/decision.md`
- `complete_report.md` (with TOC, auto-demoted hierarchy)

The `decision` string returned is `process_signal(final_trade_decision)`.

## Where a developer hooks in

| Want to... | Touch |
| --- | --- |
| Add an analyst | `agents/analysts/*` + `graph/setup.py:setup_graph` + `conditional_logic` |
| Add a tool bound to an analyst | `agents/utils/<tools>.py` + bind in `graph/trading_graph._create_tool_nodes` |
| Add a data source | `dataflows/<vendor>.py` + `interface.py` + `default_config.data_vendors` |
| Add a deterministic overlay | `strategies/*` + `_apply_strategy_overlays` + a config flag |
| Add a provider | `llm_clients/factory.py` + a client module |
| Change the debate rounds | `max_debate_rounds` / `max_risk_discuss_rounds` env/config |

Next: [`03-dataflow-vendors.md`](03-dataflow-vendors.md).