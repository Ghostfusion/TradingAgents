# 1. Topology — where every module lives

This is the full file map of the fork. It tells a developer which module owns
which concern. The three-layer split is the core: **`dataflows` = data,
`agents` = prompts + tools, `graph` = wiring, `strategies` = numbers,
`reporting` = output.**

## Repo root

```
README.md / CHANGELOG.md / .env(.example) / .gitignore
pyproject.toml / requirements.txt
main.py                 # minimal python API demo
batch.py                # headless concurrent runner (CLI)
pipeline.py             # multi-universe -> screen -> composite rank -> top-N -> batch
Strategies/             # strategy spec/plan markdowns (scan, momentum, etc.)
docs/                   # AGENT_ONBOARDING, api_reference, howto, developer/, massive_integration
scripts/                # value_screener, rebuild_report, smoke, evaluate scripts
tests/                  # pytest; conftest autouse fixtures
data/massive_flat/      # drop-folder for the (Starter+) Massive day-aggregates CSV
reports/                # run output (batch / pipeline)
```

## `tradingagents/agents` — LLM agent nodes

```
├─ __init__.py                    # re-exports create_* nodes
├─ schemas.py                     # pydantic structured output schemas
├─ analysts/
│   ├─ market_analyst.py          # market analyst (tool-calling loop)
│   ├─ sentiment_analyst.py       # = social; pre-fetches news+stocktwits+reddit
│   ├─ news_analyst.py            # news analyst (tool-calling loop)
│   ├─ fundamentals_analyst.py    # fundamentals analyst (tool-calling loop)
│   └─ social_media_analyst.py    # deprecated alias for create_sentiment_analyst
├─ researchers/
│   ├─ bull_researcher.py         # Bull Researcher (tool-calling debate)
│   └─ bear_researcher.py         # Bear Researcher
├─ managers/
│   ├─ research_manager.py        # Research Manager (structured plan)
│   └─ portfolio_manager.py       # Portfolio Manager (structured decision)
├─ risk_mgmt/
│   ├─ aggressive_debator.py / conservative_debator.py / neutral_debator.py
├─ trader/
│   └─ trader.py                  # Trader (structured proposal)
└─ utils/
    ├─ agent_states.py            # AgentState / InvestDebateState / RiskDebateState
    ├─ agent_utils.py             # re-export of all @tools + helpers
    ├─ analysis_tools.py          # computed-analysis tools (wrap strategies)
    ├─ analyst_data_tools.py, core_stock_tools.py, fundamental_data_tools.py,
    │   macro_data_tools.py, market_data_validation_tools.py,
    │   market_position_tools.py, momentum_tools.py, moomoo_extra_tools.py,
    │   news_data_tools.py, prediction_markets_tools.py,
    │   technical_indicators_tools.py, alpaca_tools.py
    ├─ rating.py                  # rating parsing (for agreement)
    ├─ structured.py              # bind_structured / invoke free-text fallback
    └─ memory.py                  # TradingMemoryLog (pending/resolved decision memory)
```

## `tradingagents/dataflows` — vendor layer

```
├── interface.py          # TOOLS_CATEGORIES, VENDOR_LIST, VENDOR_METHODS, route_to_vendor()
├── config.py             # thread-local set_config / get_config / reset_config
├── errors.py             # VendorError hierarchy
├── vendor_cache.py       # disk TTL cache (6h; news excluded)
├── symbol_utils.py       # Yahoo <-> broker normalization
├── .massive.py           # Massive.com (news sentiment, economy, short, form4, ratios, snapshots, movers, ipos)
├── .massive_flat.py      # Massive Flat-File day-aggregates loader + folder helper
└── .massive_noi.py       # Massive WebSocket NOI client (stream monitor)
```

The other vendors (moomoo, yfinance, finnhub, fred, polymarket, alpha_vantage,
fmp, alpaca, sec_edgar, float_shares, reddit, stocktwits) live in
`dataflows/` as well. Each vendor module presents functions matched to the
category/tool methods in `interface.py`.

## `tradingagents/graph/` — LangGraph wiring + run

```
├── setup.py               # GraphSetup: builds compile()-able workflow, edges, subgraphs
├── trading_graph.py       # TradingAgentsGraph: __init__/propagate/overlays/save
├── conditional_logic.py   # ConditionalLogic (should_continue_* routers)
├── analyst_execution.py   # build_analyst_execution_plan (parallel spec)
├── propagation.py         # Propagator (create_initial_state, get_graph_args)
├── reflection.py          # handle reflection
├── signal_processing.py   # process_signal (parse decision)
└── checkpointer.py       # SQLite per-ticker resume
```

## `tradingagents/strategies/` — deterministic calculators (no LLM)

```swing1 / swing2 / momentum / regime / relative_strength / sector_rank
overlays / size / book_risk / catalyst / events / risk_governor /
contract / calibration / consensus / exits / factors / normalized /
portfolio / reflection / sentiment / orderflow / debate_context / evaluate
journal / value_dip
```

Each wraps one signal the agents argue over (see 04-strategies.md).

## `tradingagents/llm_clients/` — providers

```
factory.py / base_client.py / openai_client.py / anthropic_client.py /
google_client.py / azure_client.py / bedrock_client.py / model_catalog.py /
validators.py / capabilities.py / api_key_env.py
```

## `tradingagents/` root

```
default_config.py     # DEFAULT_CONFIG dict + TRADINGAGENTS_* -> key overrides
reporting.py         # write_report_tree / TOC / risk block
__init__.py           # loads .env at import, forward-compat warning filters
```

## Layout conventions

- **Tool binding** lives in `agents/utils/*_tools.py` files.
- **Vendor methods** live in `dataflows/*/` modules; `interface.py` routes.
- **Deterministic analysis** lives in `strategies/*/` and is re-exported via
  `analysis_tools.get_*` so agents can `# bound tool`.
- **Graph shape** lives in `graph/setup.py`; everything the graph needs is
  injected.

Continue to [`02-graph-workflow.md`](02-graph-workflow.md).