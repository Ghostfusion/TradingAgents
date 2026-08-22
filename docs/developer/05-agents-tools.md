# 5. Agents, structured output & tool binding

This describes the LLM agent nodes, the tool-binding graph, and how structured
output works.

## 5.1 Agent inventory

| Agent | Node factory | LLM | Output |
| --- | --- | --- | --- |
| Market Analyst | `create_market_analyst` | quick | market_report |
| Sentiment Analyst (social) | `create_sentiment_analyst` | quick | sentiment_report (pre-fetched blocks) |
| News Analyst | `create_news_analyst` | quick | news_report |
| Fundamentals Analyst | `create_fundamentals_analyst` | quick | fundamentals_report |
| Bull / Bear Researcher | `create_bull_researcher` / `create_bear_researcher` | quick | investment_debate_state |
| Research Manager | `create_research_manager` | **deep** | ResearchPlan |
| Trader | `create_trader` | quick | TraderProposal |
| Aggressive / Conservative / Neutral | `create_aggressive_debator` etc | quick | risk_debate_state |
| Portfolio Manager | `create_portfolio_manager` | **deep** | PortfolioDecision |

`quick_thinking_llm` runs analysts/researchers/trader/risk; `deep_thinking_llm`
runs Research + Portfolio managers.

## 5.2 Tool binding

`@tool`-wrapped functions live in `agents/utils/*_tools.py` (data-tool files
per source; `analysis_tools.py` wraps the deterministic `strategies/*`
calculators; `value_dip_tools.py` wraps the Value Dip + Swing hybrid:
`get_bollinger_pct_b` / `get_tranche_plan` / `get_trade_expectancy` on the
market node and `get_fcf_yield` / `get_valuation_z_score` / `get_value_dip_setup`
on the fundamentals node). `agent_utils.py` re-exports them all (:keyword
`__all__`). The graph's `_create_tool_nodes` binds a per-analyst `ToolNode(...)`
list.

Each analyst prompt lists its tools by signature so the LLM calls them with the
right args (a `get_news(ticker, start_date, end_date)` style). The route goes:

```
@tool fn -> route_to_vendor("get_news", ...) -> VENDOR_METHODS[...] -> result str
```

Computed-analysis tools (`analysis_tools.get_*`) wrap strategies directly.

## 5.3 Structured output

`agents/schemas.py` defines pydantic models:
- `ResearchPlan` (recommendation, rationale, strategic_actions)
- `TraderProposal` (action, reasoning, entry_price?, stop_loss?, position_sizing?)
- `PortfolioDecision` (rating, executive_summary, investment_thesis, price_target,
  time_horizon, confidence, position_size, stop_loss, consensus)
- `SentimentReport` (overall_band, overall_score, confidence, narrative, plus
  computed_* injected by the deterministic sentiment layer)

`agents/utils/structured.py::bind_structured(llm, schema, name)` returns a
"structured" bind if the provider supports it; otherwise
`invoke_structured_or_freetext` falls back to free-text generation and the
report is still rendered with the expected markdown headers (so downstream logs
stay stable).

## 5.4 Memory log

`agents/utils/memory.py::TradingMemoryLog` is a markdown append-only file
(`~/.tradingagents/memory/trading_memory.md`, or `TRADINGAGENTS_MEMORY_LOG_PATH`).
Entries are keyed `date | TICKER | rating | pending`. `store_decision` appends;
a later same-ticker `resolve` computes realized return vs regional benchmark
and marks resolved + reflection. The track parameter feeds the PM context.

## 5.5 No-fabrication / computed-context

The framework's rule: **agents reason over computed numbers** (from tools that
wrap `strategies/*`), never invented ones. Every tool advertises an exact value
or "unavailable". Adds strike frontier code in `analysts/*.py` prompts.

Continue to [`06-entrypoints.md`](06-entrypoints.md).