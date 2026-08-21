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
| `TRADINGAGENTS_MASSIVE_API_KEY` | `massive_api_key` |
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
| `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` | `catalyst_hard_block_days` |
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
| `TRADINGAGENTS_ENABLE_MASSIVE_FLAT` | `enable_massive_flat` |
| `TRADINGAGENTS_MASSIVE_FLAT_DIR` | `massive_flat_dir` |

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
`risk_stress_shock_pct_1` / `risk_stress_shock_pct_2` (R2 scenario shocks, def -10%/-30%)
`evaluate_cost_bps=10`, `calibration_min_n=5`, `consensus_seeds=1`,
`max_book_names=10`, `max_name_weight=0.25`, `risk_audit_enabled` default True.
Catalyst: `catalyst_hard_block_days=0` - when > 0, an earnings print inside
that many days makes the risk governor **REJECT** new risk (section 5).

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
| Catalyst (B1) | `enable_events` (T) | `strategies/catalyst.py` | earnings/macro/Fed scale + verdict; `catalyst_hard_block_days` > 0 turns an imminent print into a risk-governor REJECT |
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

### ## 6.1 Tools by category (auto-generated)

- `core_stock_apis` : `get_stock_data`
- `technical_indicators` : `get_indicators`
- `fundamental_data` : `get_fundamentals`, `get_balance_sheet`, `get_cashflow`,
  `get_income_statement`, `get_basic_financials`, `get_company_peers`,
  `get_insider_activity`, `get_form4_insider`
- `news_data` : `get_news`, `get_global_news`, `get_insider_transactions`, `get_massive_news`
- `macro_data` : `get_macro_indicators`
- `prediction_markets` : `get_prediction_markets`
- `analyst_ratings` : `get_analyst_ratings`
- `earnings_calendar` : `get_earnings_calendar`
- `options_data` : `get_options_chain`
- `sec_filings` : `get_sec_filings`
- `short_interest` : `get_short_interest`, `get_short_volume`
- **computed-analysis tools** (bound to the analyst tool loops, see 6.4):
  `get_swing_set`, `get_relative_strength`, `get_earnings_event_read`,
  `get_catalyst_scale`, `get_position_sizing`, `get_risk_gate`,
  `get_regime_read`, `get_volatility_contraction`, `get_orderflow_read`,
  `get_analyst_verdict`, `get_earnings_surprise`, `get_portfolio_weights`,
  `get_sector_rank`, `get_strategy_quality`, `get_margin_of_safety`,
  `get_composite_rank`, `get_tail_risk`, `get_credit_spread_read`,
  `get_session_discipline`, `get_earnings_quality`
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
- news/global-news: `alpha_vantage`, `yfinance`, `finnhub`, `massive`
- macro: `fred`, `massive`, `moomoo` (optional)
- prediction markets: `polymarket`, `moomoo` (optional, SG/MY-gated)
- analyst ratings + earnings calendar: `finnhub`, `moomoo`
- finnhub free-tier extra (key-gated): `get_basic_financials` (metrics),
  `get_company_peers`, `get_insider_activity` (insider sentiment);
  `get_fundamentals` also accepts `finnhub` as a vendor
- options chain: `yfinance`, `moomoo`
- SEC filings: `sec_edgar`
- short interest: `yfinance`, `moomoo`, `massive`
- short volume (daily short-sale ratio, Massive-only): `massive`
- all A-series/tier tools: `moomoo` only (optional)

`VENDOR_LIST = yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo, massive`.

**Massive.com** (`MASSIVE_API_KEY`, key-gated) — US-centric additive vendor:
`get_massive_news` (`get_news` chain + dedicated tool on the news/social
nodes) returning per-article structured sentiment (positive/negative/neutral
+ reasoning); and `get_macro_indicators_massive` (`macro_data` chain) serving
treasury-yields / inflation / inflation-expectations / labor-market
(aliases match the FRED surface: `10y_treasury`, `yield_curve`, `cpi`, ...). The FRED `macro_data` vendor also exposes ICE BofA credit-OAS aliases for the credit-stress read: `hy_oas`/`hy_spread`/`high_yield_oas` → `BAMLH0A0HYM2`, `ccc_oas`/`ccc_and_lower_oas` → `BAMLH0A3HYC`, `bb_oas` → `BAMLH0A1HYBB`.
Massive also drives a deterministic `macro_backdrop` (yield-curve
inversion / elevated breakevens) that keeps the B1 catalyst overlay
de-risking even when the OpenD event calendar is unavailable (see
`strategies/catalyst.py` + `docs/massive_integration.md` §3a).
Short interest (`get_short_interest` chain, FINRA 2-week cadence) and a
`get_short_volume` tool (daily short-sale ratio, market analyst) come from the
`/stocks/v1/*` endpoints. Form-4 insider activity is a `get_form4_insider`
tool bound to the fundamentals analyst. (13-F is *not* wired: Massive's
`/stocks/filings/vX/13-F` has no security filter — only `filer_cik`/`filing_date`
— so a per-ticker aggregate would be misleading; moomoo
`get_institution_holdings` stays the source for that signal.) NOI
(`massive_noi.py`, WebSocket monitor) and Flat Files (`massive_flat.py`, bulk
OHLCV loader for the screener/backtests) are standalone monitored utilities,
not graph `@tool`s — see `docs/massive_integration.md` §3e. Row 5 (entitled on
the current plan): `get_company_peers` gains a `massive` option
(`related-companies`) to the fundamentals analyst; `get_corporate_actions` and
a dedicated `get_dividends` bind Massive dividends/splits to the fundamentals
analyst; `get_ipos` (IPO reference) binds to the news analyst.
Plan-dependent recency/entitlements; FMV/Greeks are Business-only
(unavailable, never invented). US-only — supplements, not replaces,
moomoo/yfinance non-US coverage. See `docs/massive_integration.md`.

➠ `get_market_snapshot` / `get_top_movers` also bound to the market analyst
  (plan-gated, see §6.4), and `get_ratios` to the fundamentals analyst; a
  `pipeline.py --universe top-movers-massive` option supplies a Massive mover
  universe (plan-gated). These degrade to "upgrade at massive.com/pricing"
  on the free plan and activate when the account's plan includes them.

### 6.3 Symbol mapping (Yahoo <-> moomoo / broker)

`dataflows/symbol_utils.py::normalize_symbol()` maps broker symbols to Yahoo
gold `XAUUSD -> GC=F`, forex `EURUSD -> EURUSD=X`, crypto
`BTCUSD -> BTC-USD`, indices `SPX500 -> ^GSPC`; moomoo code map
(`_moomoo_code()`: US., HK. pad, JP., SH., SZ., AU., CA., SG., MY., CC.USD).

### 6.4 Computed-analysis tools

**Market-analyst house tools** (bound only to the market node, not part of the
vendor category system - see `6.1`): `get_verified_market_snapshot`
(deterministic OHLCV/indicator verification snapshot, the market analyst's
source of truth), `get_momentum_scan` (5-pillar day-trade pre-filter +
first-pullback + intraday confirmation), `get_market_snapshot_alpaca` (live
1-minute Alpaca L1 price/VWAP/volume when configured). News/earnings house
tools bound to the news node: `get_catalyst_scale`, `get_earnings_event_read`.

The analyst tool loops bind deterministic calculators from `tradingagents/strategies/*`
so the LLM reasons over computed numbers rather than re-deriving them:

| Tool | Wraps | Bound to | Returns |
| --- | --- | --- | --- |
| `get_swing_set(ticker)` | `swing.swing_report` | market | trend stack, RSI band, 1-ATR stop, 2R/3R targets, VCP, trail |
| `get_relative_strength(ticker)` | `relative_strength.relative_strength_report` | market | leading/uptrend/lagging/diverging/unknown vs SPY |
| `get_earnings_event_read(ticker, date)` | `events.post_earnings_play` + `catalyst.last_earnings_surprise` | news | surprise %, drift side, print-day move, PEAD setup |
| `get_catalyst_scale(ticker, date)` | `catalyst.build_catalyst_snapshot` | news | 0..1 scale + verdict + reasons |
| `get_position_sizing(confidence, stop_dist_pct, ...)` | `size.kelly + risk-budget` | market | min(kelly_quarter, risk/stop, cap) |
| `get_risk_gate(size_pct, ...)` | `risk_governor.govern` | market | PASS / WARN / REJECT |
| `get_regime_read(ticker)` | `overlays.build_strategy_overlays` | market | regime label + position scale + momentum/52w |
| `get_volatility_contraction(ticker)` | `swing.vcp_setup` | market | VCP base depths + contraction + near-breakout |
| `get_orderflow_read(ticker)` | `orderflow.summarize` (+ guarded fetch) | market | inst/retail net, distribution, divergence, alignment |
| `get_analyst_verdict(ticker, date)` | `screener screen_ticker` + `normalized.trap_verdict` | fundamentals | EY, EV/EBIT, F/M/Z, Net-Net, trap risk, ROE, YoY |
| `get_earnings_surprise(ticker, date)` | `events.surprise_score` + `catalyst.last_earnings_surprise` | fundamentals | surprise % + side |
| `get_portfolio_weights(scores, sector_map, ...)` | `portfolio.value_ratio_weights + adjust_for_caps` | fundamentals | cap-respecting value weights |
| `get_basic_financials(ticker)` | `finnhub.get_basic_financials_finnhub` | fundamentals | EPS/revenue YoY, ROE/ROA, margins, payout (free tier) |
| `get_insider_activity(ticker)` | `finnhub.get_insider_activity_finnhub` | fundamentals | 12m net insider change + mspr + trend |
| `get_company_peers(ticker)` | `finnhub.get_company_peers_finnhub` | fundamentals | comparable peer group |
| `get_form4_insider(ticker, start, end)` | `massive.get_form4_insider_massive` | fundamentals | net open-market Form 4 buys - sells (excl. A/M) |
| `get_ratios(ticker, date?)` | `massive.get_ratios_massive` | fundamentals | precomputed EV/EBITDA, P/E, P/B, ROE/ROA, FCF (plan-gated) |
| `get_exit_check(entry, close, atr)` | `strategies.exits.exit_check` | market | stop-to-breakeven, ATR target, holding action |
| `get_allocation(scores, sector_map?)` | `strategies.portfolio.adjust_for_caps` | fundamentals | cap-respecting book allocation |
| `get_regime_components(ticker)` | `strategies.regime` | market | vol_pct / trend / chop / regime label breakdown |
| `get_consensus(ratings)` | `strategies.consensus` | PM tool + injected | numeric agreement -> high/low consensus |
| `get_momentum_detail(ticker)` | `strategies.momentum` | market | pillars, rvol, vwap, ema9, first-pullback |
| `get_beat_miss_sizing(side, catalyst)` | `strategies.events.position_mult_by_side` | news | post-earnings key multiplier |
| `get_dcf_valuation(ticker, date, growth?, erp?)` | `strategies.dcf.compute_dcf` | fundamentals | provider-sourced DCF fair value + WACC / EV breakdown |
| `get_sector_rank(ticker)` | `strategies.sector_rank.rank_sectors` + `sector_standing` | market | 11-SPDR 1m/3m momentum ranking + the ticker's sector standing |
| `get_strategy_quality(ticker, returns?)` | `strategies.evaluate` | market | net CAGR / annualized vol / Sharpe / max drawdown over a return series |
| `get_margin_of_safety(ticker, intrinsic)` | `strategies.normalized.margin_of_safety` | fundamentals | (intrinsic - price)/intrinsic safety band (wide/modest/negative) |
| `get_composite_rank(ticker, factors?)` | `strategies.factors.composite_score` | fundamentals | cross-sectional value+momentum composite percentile vs industry peers |
| `get_tail_risk(ticker, alpha?)` | `strategies.book_risk.cvar` / `simple_var` / `stress_loss` | market | historical VaR / CVaR tail budget + -10% uniform stress loss |
| `get_credit_spread_read(date)` | `strategies.credit_spread.credit_stress_level` | market | FRED ICE BofA HY/CCC/BB OAS + deterministic credit-cycle band (low/mod/high/severe) + de-risk scale |
| `get_session_discipline(ticker, peak_pnl?, current_pnl?)` | `strategies.momentum.session_flags` + `psych_level` + `past_optimal_window` | market | intraday walk-away rules (giveback, max-daily-loss, past 10:00 ET optimal) + nearest psych levels |
| `get_earnings_quality(ticker, date)` | `strategies.normalized.accruals_ratio` + `trap_verdict` | fundamentals | Sloan accruals ratio + the forensic trap verdict incl. the accrual evidence trigger |

Every tool follows the no-fabrication contract: exact computed numbers or an
 explicit "unavailable" message (both recorded in the agent's tool history for
 auditability), never an invented value.

### 6.6 Canonical line items & prior periods

The value screens read a canonical line-item dict (scripts/value_screener
``_canonicalize``). For moomoo markdown the parser emits ``{"current": ..,
"prior": ..}`` dicts for keys present in two consecutive periods (statements
list newest-first; tables are sorted by period year). The Beneish M-Score and
Piotroski time-components use ``current``/``prior`` via
``quantitative_scores``' ``_num()``/``_prv()``; every other read unwraps with
``scripts.value_screener._latest()``. moomoo ``-``-prefixed sub-item / contra
lines (``-Accounts Receivable``, ``-Accumulated Depreciation``) are skipped so
the aggregate value wins. Because the M-Score needs both periods, its M column
now computes on moomoo data (previously always n/a), and the latest-value bug
(which silently kept the OLDEST period) is fixed.

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
  `--pe-max` `--min-avg-vol` `--min-atr-pct` `--max-mcap` `--min-eps-yoy`
  `--min-rev-yoy` `--min-roe` `--sector-rank` `--revision` `--inst-accum`
  `--intraday` `--scan`
  (value|trend-pullback|breakout|momentum|swing|vcp|all)
  `--out-dir` `--rank` `--enable-float` `--journal` `--alloc`.

## 10. Docs index

- `docs/AGENT_ONBOARDING.md` - environment runbook (interpreter, quirks, layout)
- `docs/howto_end_to_end.md` - screener -> pipeline -> reports walkthrough
- `docs/developer/` - full developer map (topology, graph/workflow, dataflow,
  strategies, agents/tools, entrypoints, persistence, dev guide, tests layout,
  Massive)
- `docs/massive_integration.md` - the Massive.com add-on plan + entitlement map
- `docs/developer/11-agent-decision-tools.md` - the six decision-grounding tools
  implemented for the analyst LLMs
- `docs/developer/12-data-providers.md` - the 13 data providers/sources and
  per-category vendor chains
- `Strategies/*` - strategy plans and specs (index: `Strategies/index.md`)