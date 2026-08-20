# TradingAgents API Reference (fork)

Complete reference for the `tradingagents` package: configuration, graph flow,
state, structured output, the vendor data contract, strategy overlays,
persistence, reporting, CLI, and scripts. Generated values are checked against
the code (config keys, tool/vendor tables). For environment and operational
quirks see `docs/AGENT_ONBOARDING.md`; for the daily workflow see
`docs/howto_end_to_end.md`.

---

## 1. Configuration

Two ways to configure: `DEFAULT_CONFIG` in `tradingagents/default_config.py`,
overridden by any `TRADINGAGENTS_*` env var in the table below (value type is
coerced from the existing default; a `TRADINGAGENTS_MAX_WORKERS` example lives
in `batch.py`).

### 1.1 Env -> config overrides (complete)

| Env var | Config key |
| --- | --- |
| `TRADINGAGENTS_LLM_PROVIDER` | `llm_provider` |
| `TRADINGAGENTS_DEEP_THINK_LLM` | `deep_think_llm` |
| `TRADINGAGENTS_QUICK_THINK_LLM` | `quick_think_llm` |
| `TRADINGAGENTS_LLM_BACKEND_URL` | `backend_url` |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | `output_language` |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | `max_debate_rounds` |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | `max_risk_discuss_rounds` |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | `checkpoint_enabled` |
| `TRADINGAGENTS_BENCHMARK_TICKER` | `benchmark_ticker` |
| `TRADINGAGENTS_TEMPERATURE` | `temperature` |
| `TRADINGAGENTS_LLM_MAX_RETRIES` | `llm_max_retries` |
| `TRADINGAGENTS_FINNHUB_API_KEY` | `finnhub_api_key` |
| `TRADINGAGENTS_FMP_API_KEY` | `fmp_api_key` |
| `TRADINGAGENTS_ALPACA_API_KEY_ID` | `alpaca_api_key_id` |
| `TRADINGAGENTS_ALPACA_API_SECRET` | `alpaca_api_secret` |
| `TRADINGAGENTS_ENABLE_ALPACA` | `enable_alpaca` |
| `TRADINGAGENTS_MOOMOO_HOST` | `moomoo_host` |
| `TRADINGAGENTS_MOOMOO_PORT` | `moomoo_port` |
| `TRADINGAGENTS_MOOMOO_ACCOUNT` | `moomoo_account` |
| `TRADINGAGENTS_MOOMOO_AUTOSTART` | `moomoo_autostart` |
| `TRADINGAGENTS_MOOMOO_OPEND_PATH` | `moomoo_opend_path` |
| `TRADINGAGENTS_MOOMOO_MAX_CONNECTIONS` | `moomoo_max_connections` |
| `TRADINGAGENTS_ENABLE_STRATEGY_OVERLAYS` | `enable_strategy_overlays` |
| `TRADINGAGENTS_ENABLE_REFLECTION` | `enable_reflection` |
| `TRADINGAGENTS_ENABLE_ORDERFLOW` | `enable_orderflow` |
| `TRADINGAGENTS_ENABLE_POSITION_CONTRACT` | `enable_position_contract` |
| `TRADINGAGENTS_ENABLE_CALIBRATION` | `enable_calibration` |
| `TRADINGAGENTS_ENABLE_AGREEMENT` | `enable_agreement` |
| `TRADINGAGENTS_ENABLE_COMPOSITE_RANK` | `enable_composite_rank` |
| `TRADINGAGENTS_ENABLE_EXITS` | `enable_exits` |
| `TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT` | `enable_computed_context` |
| `TRADINGAGENTS_ENABLE_RISK_GOVERNOR` | `enable_risk_governor` |
| `TRADINGAGENTS_ENABLE_EVENTS` | `enable_events` |
| `TRADINGAGENTS_CATALYST_WINDOW_DAYS` | `catalyst_window_days` |
| `TRADINGAGENTS_CATALYST_BASELINE_MOVE` | `catalyst_baseline_move` |
| `TRADINGAGENTS_CATALYST_MACRO_WINDOW_DAYS` | `catalyst_macro_window_days` |
| `TRADINGAGENTS_CATALYST_MACRO_SCALE` | `catalyst_macro_scale` |
| `TRADINGAGENTS_CATALYST_FED_WINDOW_DAYS` | `catalyst_fed_window_days` |
| `TRADINGAGENTS_CATALYST_FED_SCALE` | `catalyst_fed_scale` |
| `TRADINGAGENTS_CATALYST_MISS_SCALE` | `catalyst_miss_scale` |
| `TRADINGAGENTS_CATALYST_SCALE_FLOOR` | `catalyst_scale_floor` |
| `TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT` | `risk_max_drawdown_pct` |
| `TRADINGAGENTS_RISK_DAILY_CVAR_BUDGET_PCT` | `risk_daily_cvar_budget_pct` |
| `TRADINGAGENTS_RISK_COMPACT_REPORT` | `risk_compact_report` |
| `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` | `google_thinking_level` |
| `TRADINGAGENTS_OPENAI_REASONING_EFFORT` | `openai_reasoning_effort` |
| `TRADINGAGENTS_ANTHROPIC_EFFORT` | `anthropic_effort` |
| `TRADINGAGENTS_ANALYST_CONCURRENCY` | `analyst_concurrency` |
| `TRADINGAGENTS_RESULTS_DIR` | `results_dir` |
| `TRADINGAGENTS_CACHE_DIR` | `data_cache_dir` |
| `TRADINGAGENTS_MEMORY_LOG_PATH` | `memory_log_path` |

(Secrets are read from env inside the vendors; `TRADINGAGENTS_DISABLE_REDDIT=1`
in `.env` turns off Reddit fetches.)

### 1.2 All `DEFAULT_CONFIG` keys

Run `py -3.12 -c "from tradingagents.default_config import DEFAULT_CONFIG as D; print(sorted(D))"`
for the canonical list; the important groups:

**LLM** - `llm_provider`, `deep_think_llm`, `quick_think_llm`, `backend_url`,
`openai_reasoning_effort`, `google_thinking_level`, `anthropic_effort`,
`temperature`, `llm_max_retries`.

**Graph/run** - `max_debate_rounds`, `max_risk_discuss_rounds`, `max_recur_limit`,
`checkpoint_enabled`, `analyst_concurrency` (1 = sequential; >1 = parallel
analysts), `output_language`.

**Persistence** - `data_cache_dir` (~/.tradingagents/cache),
`results_dir` (~/.tradingagents/logs), `memory_log_path`
(~/.tradingagents/memory/trading_memory.md), `memory_log_max_entries` (None =
unbounded rotation), `benchmark_ticker` + `benchmark_map` (per-exchange alpha
benchmarks: `.NS->^NSEI`, `.BO->^BSESN`, `.T->^N225`, `.HK->^HSI`, `.L->^FTSE`,
`.TO->^GSPTSE`, `.AX->^AXJO`, `.SS->000001.SS`, `.SZ->399001.SZ`, `''->SPY`).

**News/input limits** - `news_article_limit=20`, `global_news_article_limit=10`,
`global_news_lookback_days=7`, `global_news_queries` (macro headlines).

**Data vendors** - `data_vendors: dict` (per-category chains), `tool_vendors: dict`
(per-tool overrides), `finnhub_api_key`, `fmp_api_key`, `alpaca_api_key_id`,
`alpaca_api_secret`, `enable_alpaca`, `moomoo_host/port/account/autostart/
opend_path/max_connections`.

**Vendor cache** - `vendor_cache_enabled=True`, `vendor_cache_ttl_seconds=21600`,
`vendor_cache_skip_categories={'news_data'}`.

**Strategy flags** - see section 5; `enable_regime`, `enable_factors`,
`enable_sentiment`, `enable_threshold_gate` default **False**; the rest
(`enable_strategy_overlays`, `enable_orderflow`, `enable_position_contract`,
`enable_calibration`, `enable_agreement`, `enable_composite_rank`,
`enable_exits`, `enable_computed_context`, `enable_risk_governor`,
`enable_events`, `enable_reflection`) default **True**; `enable_events` is the
B1 catalyst gate. Sizing: `position_sizing='kelly'`, `target_vol=0.15`,
`risk_per_trade=0.01`, `max_position_pct=0.30`, `atr_mult=2.0`,
`kelly_fraction=0.25`, `position_odds=1.0`, `breakeven_atr=1.0`,
`target_atr=4.0`, `sector_cap_limit=0.35`, `risk_max_drawdown_pct=0.10`,
`risk_daily_cvar_budget_pct=0.03`, `risk_max_position_pct=0.45`,
`risk_stress_shock_pct`, `orderflow_distribution_threshold=0.7`,
`evaluate_cost_bps=10`, `calibration_min_n=5`, `consensus_seeds=1`,
`max_book_names=10`, `max_name_weight=0.25`, `risk_audit_enabled` default True.

## 2. LLM providers

`deep_think_llm` models the Research Manager + Portfolio Manager; `quick` the
analysts/researchers/debaters/reflection. Client code:
`llm_clients/factory.py` -> `llm_clients/{openai,anthropic,google,azure,
bedrock}_client.py` + `model_catalog.py` (CLI model lists).

| Provider | Config value | Env key | Notes |
| --- | --- | --- | --- |
| `openai` | `openai` | `OPENAI_API_KEY` | Responses API; `openai_reasoning_effort` |
| `google` | `google` | `GOOGLE_API_KEY` | `google_thinking_level` |
| `anthropic` | `anthropic` | `ANTHROPIC_API_KEY` | `anthropic_effort` |
| `xai` | `xai` | `XAI_API_KEY` | |
| `deepseek` | `deepseek` | `DEEPSEEK_API_KEY` | reasoning_content round-trip |
| `mistral` | `mistral` | `MISTRAL_API_KEY` | |
| `kimi` | `kimi` | `MOONSHOT_API_KEY` | |
| `groq` | `groq` | `GROQ_API_KEY` | |
| `nvidia` | `nvidia` | `NVIDIA_API_KEY` | |
| `openrouter` | `openrouter` | `OPENROUTER_API_KEY` | default provider in `.env` |
| `qwen` / `qwen-cn` | `qwen`/`qwen-cn` | `DASHSCOPE_API_KEY` / `DASHSCOPE_CN_API_KEY` | intl / CN |
| `glm` / `glm-cn` | `glm`/`glm-cn` | `ZHIPU_API_KEY` / `ZHIPU_CN_API_KEY` | |
| `minimax` / `minimax-cn` | `minimax`/`minimax-cn` | `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` | reasoning_split |
| `ollama` | `ollama` | `OLLAMA_BASE_URL` | keyless local |
| `openai_compatible` | `openai_compatible` | `TRADINGAGENTS_LLM_BACKEND_URL` | vLLM / LM Studio / llama.cpp |
| `azure` | `azure` | Azure OpenAI env | see `.env.enterprise.example` |
| `bedrock` | `bedrock` | AWS creds / `AWS_BEARER_TOKEN_BEDROCK` | `pip install ".[bedrock]"` |

## 3. Graph & subagents

`AgentState` (LangGraph `MessagesState`): `messages, company_of_interest,
asset_type, instrument_context, trade_date, sender, market_report,
sentiment_report, news_report, fundamentals_report, investment_debate_state,
investment_plan, trader_investment_plan, risk_debate_state,
final_trade_decision, past_context`.

- `InvestDebateState`: `bull_history, bear_history, history, current_response,
  judge_decision, count`.
- `RiskDebateState`: `aggressive_history, conservative_history, neutral_history,
  history, latest_speaker, current_aggressive_response,
  current_conservative_response, current_neutral_response, judge_decision, count`.

Pipeline (see `graph/setup.py` for wiring):

```
START -> analysts* (tool loop each) -> Bull/Bear debate (rounds) -> Research Manager
      -> Trader -> Aggressive/Conservative/Neutral debate -> Portfolio Manager -> END
```

- `analyst_concurrency > 1` wraps analysts in isolated per-analyst subgraphs
  running in threads.
- `graph/checkpointer.py`: per-ticker SQLite checkpoints keyed on
  ticker+date+graph-shape (analyst set, debate/risk rounds, asset type,
  concurrency). `--checkpoint` enables; cleared on successful completion.
- `graph/conditional_logic.py`: routers bound to the message tail; the
  path maps in `setup.py` are complete so a fall-through can never raise.

## 4. Structured output (pydantic in `agents/schemas.py`)

| Agent | Schema | Fields |
| --- | --- | --- |
| Research Manager | `ResearchPlan` | `recommendation` (5-tier), `rationale`, `strategic_actions` |
| Trader | `TraderProposal` | `action` (Buy/Hold/Sell), `reasoning`, `entry_price?`, `stop_loss?`, `position_sizing?` |
| Portfolio Manager | `PortfolioDecision` | `rating`, `executive_summary`, `investment_thesis`, `price_target?`, `time_horizon?`, `confidence` (0-1), `position_size`, `stop_loss?`, `consensus` (high/low) |
| Sentiment Analyst | `SentimentReport` | `overall_band` (6-tier), `overall_score` (0-10), `confidence` (low/med/high), `narrative` (+ computed fields) |

Each agent falls back to free-text when the provider lacks structured output;
rendered markdown preserves backward-compatible headers for the log/site.

## 5. Strategy overlays (compute, don't narrate)

Applied after the graph in `graph/trading_graph.py::_apply_strategy_overlays`:

| Layer | Flag (default) | Module | Effect |
| --- | --- | --- | --- |
| Regime / size | `enable_strategy_overlays` (T) | `strategies/regime.py`, `size.py` | vol-percentile/trend label + vol-target scale |
| Order flow | `enable_orderflow` (T) | `strategies/orderflow.py` | distribution/divergence fold -> scale |
| Catalyst (B1) | `enable_events` (T) | `strategies/catalyst.py` | earnings/macro/Fed scale + verdict |
| Position contract | `enable_position_contract` (T) | `strategies/contract.py` | min(Kelly, risk/stop)*vol*flow*agree*catalyst |
| Risk governor | `enable_risk_governor` (T) | `strategies/risk_governor.py` | PASS/WARN/REJECT, `risk_halt` |
| Calibration | `enable_calibration` (T) | `strategies/calibration.py` | calibrated P from ledger |
| Agreement | `enable_agreement` (T) | `strategies/consensus.py` | debate agreement -> size |
| Computed context | `enable_computed_context` (T) | `strategies/debate_context.py` | numbers into debate |
| Exits | `enable_exits` (T) | `strategies/exits.py` | stops/BE/targets |
| Reflection | `enable_reflection` (T) | `strategies/reflection.py` | ledger, analyst hit-rates |
| Composite rank | `enable_composite_rank` (T) | `strategies/factors.py` | EY + momentum + 52w composite |

Off by default: `enable_regime`, `enable_factors`, `enable_sentiment`,
`enable_threshold_gate`. Strategy-eval scripts: `scripts/evaluate_config_gate.py`
(G5 walk-forward/PBO), `scripts/orderflow_evaluate.py` (ledger evaluation),
`scripts/risk_report.py` (risk audit).

## 6. Vendor data contract

Everything flows through `route_to_vendor(method, *args, **kwargs)` in
`dataflows/interface.py`. The vendor chain per category is configured in
`data_vendors` (default chains: `moomoo,yfinance`, `fred,moomoo`,
`polymarket,moomoo`, `moomoo,finnhub`, `sec_edgar`). Errors propagate through
`dataflows/errors.py`, the router converts to sentinel strings
(`NO_DATA_AVAILABLE`, `DATA_UNAVAILABLE` optional, `DATA_DISABLED`).

### 6.1 Tools by category (auto-generated)

- `core_stock_apis` : `get_stock_data`
- `technical_indicators` : `get_indicators`
- `fundamental_data` : `get_fundamentals`, `get_balance_sheet`, `get_cashflow`,
  `get_income_statement`
- `news_data` : `get_news`, `get_global_news`, `get_insider_transactions`
- `macro_data` : `get_macro_indicators`
- `prediction_markets` : `get_prediction_markets`
- `analyst_ratings` : `get_analyst_ratings`
- `earnings_calendar` : `get_earnings_calendar`
- `options_data` : `get_options_chain`
- `sec_filings` : `get_sec_filings`
- `short_interest` : `get_short_interest`
- moomoo-only optional: `capital_flow` (`get_capital_flow`),
  `smart_money` (`get_smart_money`), `economic_calendar` (`get_economic_calendar`),
  `fed_watch` (`get_fed_watch`), `market_breadth` (`get_market_breadth`),
  `revenue_breakdown` (`get_revenue_breakdown`),
  `corporate_actions` (`get_corporate_actions`),
  `earnings_catalyst` (`get_earnings_catalyst`),
  `institution_data` (`get_institution_holdings`),
  `earnings_surprise` (`get_earnings_surprise_history`),
  `expected_move` (`get_expected_move`).

### 6.2 Vendor implementations per tool (exact)

- stock/indicators/financials/insiders: `alpha_vantage`, `yfinance`, `moomoo`
- news/global-news: `alpha_vantage`, `yfinance`, `finnhub`
- macro: `fred`, `moomoo` (optional)
- prediction markets: `polymarket`, `moomoo` (optional, SG/MY-gated)
- analyst ratings + earnings calendar: `finnhub`, `moomoo`
- options chain: `yfinance`, `moomoo`
- SEC filings: `sec_edgar`
- all A-series/tier tools: `moomoo` only (optional)

`VENDOR_LIST = yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo`.

### 6.3 Symbol mapping (Yahoo <-> moomoo / broker)

`dataflows/symbol_utils.py::normalize_symbol()` maps broker symbols to Yahoo
gold `XAUUSD -> GC=F`, forex `EURUSD -> EURUSD=X`, crypto
`BTCUSD -> BTC-USD`, indices `SPX500 -> ^GSPC`; moomoo code map
(`_moomoo_code()`: US., HK. pad, JP., SH., SZ., AU., CA., SG., MY., CC.USD).

## 7. Persistence & recovery

- Memory log (`agents/utils/memory.py`): append-only markdown; pending entries
  resolved at the next same-ticker run with realised return/alpha + reflection;
  track-record stats injected into the PM context; mtime-cached parse.
- Checkpoints: per-ticker SQLite under `~/.tradingagents/cache/checkpoints/`,
  `--checkpoint` opt-in, `clear_checkpoint`/`clear_all_checkpoints`.
- Vendor cache: disk TTL (6h) under `data_cache_dir/vendor_cache/`.

## 8. Reporting

`reporting.py::write_report_tree(state, ticker, path)` writes the per-section
tree plus `complete_report.md` with H1 report -> H2 team -> H3 role -> H4+
agent content (agent headings demoted 3 levels) and an auto Table of Contents.
`scripts/rebuild_complete_report.py` re-renders folders without a re-run and
preserves `Risk Gate (computed)` blocks.

## 9. Entry points

| Command | Purpose |
| --- | --- |
| `tradingagents` | interactive   CLI (typer/rich), full flow |
| `python batch.py --symbols ...` | headless concurrent; `--vendor`, `--workers`, `--analysts`, `--depth`, `--date` |
| `python pipeline.py --universe top-losers --top 5` | screener + composite rank + batch (B2) |
| `python scripts/value_screener.py ...` | value screens / scans / composite |
| `python scripts/rebuild_complete_report.py reports/<dir>` | re-render TOC reports |
| `python scripts/smoke_structured_output.py` | smoke structured output |
| `python main.py` | minimal Python API demo |

### Entry points: detailed flags

- batch.py: `--symbols` (required) `--date` `--workers` (1-3 default=capped)
  `--depth` (shallow|medium|deep) `--analysts` (market|social|news|fundamentals)
  `--vendor` (default|moomoo|yfinance).
- pipeline.py: `--universe` (tickers|top-losers|heat-proxy) `--file` `--top`
  `--limit` `--market` `--movers-count` `--min-mcap` `--price-min` `--pe-max`
  `--workers` `--analysts` `--depth` `--vendor`.
- value_screener.py: `tickers` `-f/--file` `-d/--date` `-l/--limit`
  `-u/--universe` `--market` `-n/--movers-count` `--min-mcap` `--price-min`
  `--pe-max` `--min-avg-vol` `--min-atr-pct` `--intraday` `--scan`
  `--out-dir` `--rank` `--enable-float` `--journal` `--alloc`.

## 10. Docs index

- `docs/AGENT_ONBOARDING.md` - environment runbook (interpreter, quirks, layout)
- `docs/howto_end_to_end.md` - screener -> pipeline -> reports walkthrough
- `Strategies/*` - strategy plans and specs