# 2. Graph topology & the run

This is the heart of the fork. Read this fully: it explains how the LangGraph
state machine is assembled, how a run flows through it, and where to hook new
analysts/tools/overlays. Companion: `docs/api_reference.md` §3 (Graph & agents).

## 2.1 The five-layer model

```
  Graph (wiring)                 LLM agents (prompts+tools)        Overlays (deterministic)
  ----/----/----/----/----/----/----/----/----/----/----/----/----/----/----/----/----/----/----/--
  LangGraph StateGraph           @tool-calling LLM loops         regime -> catalyst -> contract -> gov
  START -> analysts* -> debate -> research -> trader -> risk
```

- **Graph** = LangGraph `StateGraph(AgentState)`; nodes are Python callables
  (factories), edges are routed by `ConditionalLogic`.
- **Agents** are `chat` / `tool` nodes; they run a tool-calling LLM loop.
- **Overlays** are pure functions applied **after** the graph in
  `_apply_strategy_overlays`, deterministic (no LLM).

## 2.2 `AgentState` (the shared message-pool)

`tradingagents/agents/utils/agent_states.py`. A `MessagesState` subclass:

```python
class AgentState(MessagesState):
    company_of_interest   # ticker
    asset_type            # stock / crypto
    instrument_context    # deterministic ticker identity string
    trade_date
    sender
    market_report / sentiment_report / news_report / fundamentals_report
    investment_debate_state   # InvestDebateState (bull/bear history...)
    investment_plan
    trader_investment_plan
    risk_debate_state         # RiskDebateState (aggr/cons/neutral)
    final_trade_decision
    past_context              # injected memory context
```

All agents write their report into the message pool **and** a state key. The
final decision is read from `final_trade_decision`.

## 2.3 The run (propagate)

`tradingagents/graph/trading_graph.py::TradingAgentsGraph.propagate(ticker, date, asset_type)`:

1. **Resolve identity** – `resolve_instrument_context` builds a deterministic
   instrument string (name, sector, exchange) used by all tools to avoid
   hallucinated-company tokens.
2. **Create initial state** – `Propagator.create_initial_state(...)`: populates
   `messages=[("human", ticker)]`, empty debate states, past context.
3. **Graph invoke/stream** – if `debug` prints a live dashboard; then
   merges chunk deltas into the same `final_state` that `invoke()` yields.
4. **Apply strategy overlays** – `_apply_strategy_overlays(...)` (next section).
5. **Persist** – `_log_state` writes a per-run JSON log under
   `results_dir/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`.
6. **Memory** – `memory_log.store_decision(...)` appends a *pending* entry.
7. **Checkpoint clear** – if enabled, clears the per-ticker SQLite resume.
8. Returns `(final_state, signal)` where `signal` is
   `process_signal(final_trade_decision)`.

## 2.4 The graph edges (setup.py)

`tradingagents/graph/setup.py::GraphSetup.setup_graph(selected_analysts)` builds
a `StateGraph`. In sequential mode (`analyst_concurrency=1`, the default), an
analyst loop is:

```
analyst_prompt -> [should_continue_<analyst> ?] -> tool node -> back to analyst_prompt (loop)
                                                          \--> clear node (done)
```

Then the fixed **debate/research/risk** chain:

```
START -> analyst(s) -> Bull Researcher -> Bear Researcher -> Research Manager -> Trader
     -> Aggressive Analyst -> Conservative Analyst -> Neutral Analyst
     -> Portfolio Manager -> END
```

Because the analyst set is configurable, a run may drop the market or
“social” analyst and keep the rest. `selected_analysts` order is the sequential
order.

### The debate loops

Each debate has a `should_continue_*` router:

- **Debate** (Bull/Bear): `should_continue_debate(state)` returns the next
  speaker or "Research Manager" after N rounds (`max_debate_rounds`).
- **Risk** (Aggressive/Conservative/Neutral): `should_continue_risk_analysis`
  returns the next speaker or "Portfolio Manager" after
  `max_risk_discuss_rounds`.

`DEBATE_PATH_MAP` / `RISK_ANALYSIS_PATH_MAP` in `setup.py` list **every**
possible router target so a fall-through never crashes (#1088).

## 2.5 Parallel analyst mode

`analyst_concurrency > 1` in `DEFAULT_CONFIG` (or env) runs the **4 analysts as
separate isolated subgraphs**, each in its own thread (see `graph/setup.py`: `_build_analyst_subgraph` / `make_parallel_analyst_node`). Each analyst gets its own copy of messages; when they all
finish the parallel node (`"Run Analysts"`) merges the reports back into one
pool and the debate chain reads the same keys. This is opt-in because it
multiplies LLM/provider load.

## 2.6 Strategy overlays (deterministic, after the graph)

`_apply_strategy_overlays(final_state, ticker)` — creates an `overlay` dict
from `strategies/overlays.py::build_strategy_overlays`, then folds additional
signals in, and finally `apply_overlay_to_state(state, overlay)` updates
`final_state["strategy_overlays"]` + any `computed_*` keys.

The **order of folds matters** (each multiplies / feeds the downstream):

1. **regime/size** – `strategies/regime.py`, `size.py`: volatility percentile +
   trend label + vol-target scale -> `position_scale`.
2. **order flow** (optional) – `strategies/orderflow.py::fetch_flow/summarize`:
   capital-flow buckets -> `distribution_score` -> fold into overlay.
3. **catalyst** (optional, `enable_events`) – `strategies/catalyst.py`:
   `fetch_catalyst_data` -> `build_catalyst_snapshot` (scale 0..1 +
   verdict) -> `fold_catalyst_into_overlay` multiplies `position_scale`.
4. **position contract** (optional, `enable_position_contract`) –
   `strategies/contract.py::build_position_contract`: size + stop, using
   `closes`, flow, agreement, calibrated_p, catalyst_scale.
5. **risk governor** (optional, `enable_risk_governor`) –
   `strategies/book_risk.cvar` + `risk_governor.govern`: PASS/WARN/REJECT.
   Hard-block (imminent earnings) → REJECT.
6. **computed context** (optional, `enable_computed_context`) –
   `strategies/debate_context.py::build_computed_context`: snippet fed into the
   debates.
7. `apply_overlay_to_state(final_state, overlay)`.

Only the flags enabled in config run; all others skip cleanly. `enable_*`
flags: default ON: `enable_strategy_overlays, enable_orderflow,
enable_position_contract, enable_calibration, enable_agreement,
enable_composite_rank, enable_exits, enable_computed_context,
enable_risk_governor, enable_events, enable_reflection`. Default OFF:
`enable_regime, enable_factors, enable_sentiment, enable_threshold_gate`.

## 2.7 Conditional logic

`graph/conditional_logic.py::ConditionalLogic` has routers:

```
should_continue_market / social / news / fundamentals (loop)
should_continue_debate / should_continue_risk_analysis (round)
get_recur_limit  (false default)
```

It is the single place to add a new analyst loop / new round logic.

## 2.8 Key entry/persistence wiring

- `TradingAgentsGraph.__init__` builds `tool_nodes` (`_create_tool_nodes`),
  `ConditionalLogic(...)`, `GraphSetup`, `Propagator`, then
  `setup_graph(selected_analysts)`.
- `self.save_reports(...)` / `reporting.write_report_tree(...)` writes the
  per-team tree + `complete_report.md` (see `07-persistence.md`).

Continue to [`02-01-graph-workflow.md`](02-01-graph-workflow.md).