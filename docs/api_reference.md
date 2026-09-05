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
| `TRADINGAGENTS_RESEARCH_DEPTH` | `research_depth` | ONE depth knob (1/3/5): drives BOTH research and risk debate rounds to the same level |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | `max_risk_discuss_rounds` | per-round override; wins over RESEARCH_DEPTH |
| `TRADINGAGENTS_ENABLE_DEBATE` | `enable_debate` | structured multi-agent debate on (default off — legacy one-shot chain unchanged) |
| `TRADINGAGENTS_DEBATE_BULL_MODEL` / `_BEAR_MODEL` / `_JUDGE_MODEL` | `debate_bull_model` / `debate_bear_model` / `debate_judge_model` | per-role `family:id` models; empty = quick/deep fallback. BULL drives bull (research) + aggressive (risk); BEAR drives bear + conservative; JUDGE drives both blind judges; neutral = quick |
| `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL` | `debate_neutral_model` | `family:id` for the neutral RISK debater; empty = quick fallback |
| `TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE` | `debate_judge_ensemble` |
| `TRADINGAGENTS_DEBATE_MAX_ROUNDS` | `debate_max_rounds` | 5 (DebaterTurnPayload round_index 1..5) |
| `TRADINGAGENTS_DEBATE_MIN_GAIN` / `_STOP_CONSECUTIVE` / `_CONSENSUS_THRESH` | `debate_min_gain` / `debate_stop_consecutive` / `debate_consensus_thresh` | termination knobs |
| `TRADINGAGENTS_DEBATE_REGEN_MAX` | `debate_regen_max` | R1' bounded single-role regeneration budget (1) |
| `TRADINGAGENTS_DEBATE_DIVERGENCE_CAP_ROUNDS` | `debate_divergence_cap_rounds` |
| `TRADINGAGENTS_DEBATE_REWEIGHT_TO_BASELINE` | `debate_reweight_to_baseline` | R2' base α toward baseline (0.5) |
| `TRADINGAGENTS_DEBATE_ENTRENCH_THRESH` | `debate_entrench_thresh` | I_entrench above this -> penalty (0.8) |
| `TRADINGAGENTS_DEBATE_DIVERGENCE_MIN` | `debate_divergence_min` | |bull−bear| below → artificial-consensus flag (0.15) |
| `TRADINGAGENTS_DEBATE_BASELINE_FALLBACK` | `debate_baseline_fallback` |
| `TRADINGAGENTS_DEBATE_REQUIRE_CAPABILITY_MATRIX` | `debate_require_capability_matrix` | R3 fail-closed startup check (default false) |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | `checkpoint_enabled` |
| `TRADINGAGENTS_BENCHMARK_TICKER` | `benchmark_ticker` |
| `TRADINGAGENTS_TEMPERATURE` | `temperature` |
| `TRADINGAGENTS_LLM_MAX_RETRIES` | `llm_max_retries` |
| `TRADINGAGENTS_FINNHUB_API_KEY` | `finnhub_api_key` |
| `TRADINGAGENTS_MASSIVE_API_KEY` | `massive_api_key` |
| `TRADINGAGENTS_FMP_API_KEY` | `fmp_api_key` |
| `TRADINGAGENTS_EODHD_API_KEY` | `eodhd_api_key` | EODHD daily OHLCV (free 20 calls/day; EOD plan $19.99/mo = 100k calls/day @ 1000/min, 30+ years) — a replacement for the moomoo K-line quota (100 calls/7 days) |
| `TIINGO_API_KEY` | `tiingo_api_key` | Tiingo market data (free Starter tier: EOD OHLCV + fundamental statements + IEX quote + crypto; ~1,000 calls/day) |
| `TWELVEDATA_API_KEY` | `twelve_data_api_key` | Twelve Data (free "Basic": 800 credits/day, 8/min; realtime US stocks/forex/crypto quotes + historical time-series OHLCV; tail of `core_stock_apis`) |
| `STOCKDATA_API_KEY` | `stockdata_api_key` | StockData.org (free "$0/mo": 100 requests/day; quote/EOD/intraday/news; tail of `core_stock_apis` + `news_data`) |
| `NEWSAPI_API_KEY` | `newsapi_api_key` | NewsAPI.org (free Developer: 100 req/day; global macro headlines; tail of `news_data`/`get_global_news`) |
| `BENZINGA_API_KEY` | `benzinga_api_key` | Benzinga Basic Financial News API (free tier; headline+teaser+link; ticker news). GDELT is keyless. |
| `TRADINGAGENTS_ALPACA_API_KEY_ID` | `alpaca_api_key_id` |
| `TRADINGAGENTS_ALPACA_API_SECRET` | `alpaca_api_secret` |
| `TRADINGAGENTS_ENABLE_ALPACA` | `enable_alpaca` |
| `TRADINGAGENTS_MOOMOO_HOST` | `moomoo_host` |
| `TRADINGAGENTS_MOOMOO_PORT` | `moomoo_port` |
| `TRADINGAGENTS_MOOMOO_ACCOUNT` | `moomoo_account` |
| `TRADINGAGENTS_MOOMOO_AUTOSTART` | `moomoo_autostart` |
| `TRADINGAGENTS_MOOMOO_OPEND_PATH` | `moomoo_opend_path` |
| `TRADINGAGENTS_MOOMOO_MAX_CONNECTIONS` | `moomoo_max_connections` |
| `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT` | `moomoo_call_timeout` | per-call wall-clock timeout (s) for moomoo SDK calls; the SDK's own `ReqInfo.wait()` allows 20s, this caps a degraded gateway at 5s (default) so a run can't stall on hundreds of slow calls |
| `TRADINGAGENTS_ENABLE_STRATEGY_OVERLAYS` | `enable_strategy_overlays` |
| `TRADINGAGENTS_ENABLE_REFLECTION` | `enable_reflection` |
| `TRADINGAGENTS_ENABLE_SENTIMENT` | `enable_sentiment` | when on (default True), the sentiment report gets the computed StockTwits score + surprise velocity injected |
| `TRADINGAGENTS_ENABLE_ORDERFLOW` | `enable_orderflow` |
| `TRADINGAGENTS_ENABLE_POSITION_CONTRACT` | `enable_position_contract` |
| `TRADINGAGENTS_ENABLE_CALIBRATION` | `enable_calibration` |
| `TRADINGAGENTS_ENABLE_AGREEMENT` | `enable_agreement` |
| `TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE` | `enable_independent_vote` | when on, the 3 risk + bull/bear stances are sampled INDEPENDENTLY before the debate and the agreement/consensus (G3 + the PM's dissent flag + the G1 contract multiply) comes from those uncontaminated pre-debate opinions — the debate stays the risk-surfacing layer |
| `TRADINGAGENTS_ENABLE_SENTIMENT_FACTOR` | `enable_sentiment_factor` | when on (default off), the position scale multiplies by 1 ± `sentiment_factor_max_scale` ONLY when the name's measured news-sentiment rank IC ≥ `sentiment_factor_min_ic` (else neutral 1.0, never blocks) |
| `TRADINGAGENTS_SENTIMENT_FACTOR_MIN_IC` | `sentiment_factor_min_ic` | measured rank-IC floor for the sentiment fold (default 0.02) |
| `TRADINGAGENTS_SENTIMENT_FACTOR_MAX_SCALE` | `sentiment_factor_max_scale` | max +/- position-scale move from the sentiment fold (default 0.2) |
| `TRADINGAGENTS_SENTIMENT_FACTOR_MIN_SCALE` | `sentiment_factor_min_scale` | floor for the sentiment fold scale (default 0.5) |
| `TRADINGAGENTS_VOLATILITY_ESTIMATOR` | `volatility_estimator` | overlay sizing estimator: `close` (default) \| `ewma` \| `garch` (parkinson / garman-klass / yang-zhang are analyst tools, need OHLC) |
| `TRADINGAGENTS_COVARIANCE_SHRINKAGE_ENABLE` | `covariance_shrinkage_enable` | Ledoit-Wolf shrunk covariance in the covariance allocators (advisory, default off) |
| `TRADINGAGENTS_COVARIANCE_SHRINKAGE_TARGET` | `covariance_shrinkage_target` | shrinkage target: `scaled_identity` (default) \| `diag` |
| `TRADINGAGENTS_ENABLE_KELLY_ALLOC` | `enable_kelly_alloc` | allocation block uses multi-asset fractional Kelly (advisory, default off) |
| `TRADINGAGENTS_KELLY_FRACTION` | `kelly_alloc_fraction` | fractional-Kelly scaling (default 0.25) |
| `TRADINGAGENTS_ENABLE_COMPOSITE_RANK` | `enable_composite_rank` |
| `TRADINGAGENTS_ENABLE_EXITS` | `enable_exits` |
| `TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT` | `enable_computed_context` |
| `TRADINGAGENTS_ENABLE_RISK_GOVERNOR` | `enable_risk_governor` |
| `TRADINGAGENTS_ENABLE_DECISION_AUDIT` | `enable_decision_audit` | on, the PM's report shows a claim-vs-computed audit note |
| `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE` | `enable_liquidity_gate` | on, the risk governor sizes against the ILLIQ/float-turnover/IWF liquidity verdict (Strategies/risk2.md) |
| `TRADINGAGENTS_ENABLE_EVENTS` | `enable_events` |
| `TRADINGAGENTS_CATALYST_WINDOW_DAYS` | `catalyst_window_days` |
| `TRADINGAGENTS_CATALYST_BASELINE_MOVE` | `catalyst_baseline_move` |
| `TRADINGAGENTS_CATALYST_MACRO_WINDOW_DAYS` | `catalyst_macro_window_days` |
| `TRADINGAGENTS_CATALYST_MACRO_SCALE` | `catalyst_macro_scale` |
| `TRADINGAGENTS_CATALYST_FED_WINDOW_DAYS` | `catalyst_fed_window_days` |
| `TRADINGAGENTS_CATALYST_FED_SCALE` | `catalyst_fed_scale` |
| `TRADINGAGENTS_CATALYST_MISS_SCALE` | `catalyst_miss_scale` |
| `TRADINGAGENTS_CATALYST_SCALE_FLOOR` | `catalyst_scale_floor` |
| `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` | `catalyst_hard_block_days` |  # default 5 (forward earnings blackout) | `market_stress_index`/`market_stress_vol_cap` (index vol cap) | `min_dollar_volume`/`max_spread_bps` (liquidity guards)
| `TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT` | `risk_max_drawdown_pct` |
| `TRADINGAGENTS_RISK_DAILY_CVAR_BUDGET_PCT` | `risk_daily_cvar_budget_pct` |
| `TRADINGAGENTS_RISK_BASKET_TICKERS` | `risk_basket_tickers` |
| `TRADINGAGENTS_RISK_BASKET_WEIGHTS` | `risk_basket_weights` |
| `TRADINGAGENTS_HOLDINGS_TICKERS` | `holdings_tickers` | Option B: actual-book tickers for the PM holdings read; empty = the risk basket is used (Option A) |
| `TRADINGAGENTS_HOLDINGS_WEIGHTS` | `holdings_weights` | Option B: actual-book weights (fractions of the whole book incl. cash; <1.0 remainder = cash sleeve). See `scripts/positions_to_basket.py` to derive them from position CSVs |
| `TRADINGAGENTS_RISK_COMPACT_REPORT` | `risk_compact_report` |
| `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` | `google_thinking_level` |
| `TRADINGAGENTS_OPENAI_REASONING_EFFORT` | `openai_reasoning_effort` |
| `TRADINGAGENTS_ANTHROPIC_EFFORT` | `anthropic_effort` |
| `TRADINGAGENTS_ANALYST_CONCURRENCY` | `analyst_concurrency` |
| `TRADINGAGENTS_ENABLE_VALUE_DIP` | `enable_value_dip` |
| `TRADINGAGENTS_ENABLE_TRANCHE_RISK` | `enable_tranche_risk` |
| `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` | `openrouter_ignore_providers` | comma-separated provider slugs to always skip (sent as `provider.ignore` in the OpenRouter request body via `extra_body`) to block slow/unreliable endpoints; empty = no restriction |
| `TRADINGAGENTS_MAX_OUTPUT_TOKENS` | `max_output_tokens` | per-role max output tokens (hard ceiling via `max_tokens`); default 8000; the fallback for both tiers |
| `TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK` | `max_output_tokens_quick` | quick-tier cap (analysts / researchers / debaters / trader); default 8000 (raised from 6000 after 2026-08-27 reports truncated mid-sentence at the 6000 cap) |
| `TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP` | `max_output_tokens_deep` | deep-tier cap (Research Manager + Portfolio Manager); default 2500 |
| `TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW` | `enable_pre_market_review` |
| `TRADINGAGENTS_VALUE_DIP_REQUIRE_CATALYST` | `value_dip_require_catalyst` | strict: value-dip needs re-rating evidence |
| `TRADINGAGENTS_VALUE_DIP_REGIME_GATE` | `value_dip_regime_gate` | strict: block dip entries in high-vol/fast-downtrend/catalyst windows |
| `TRADINGAGENTS_VALUE_DIP_REGIME_VOL_CAP` | `value_dip_regime_vol_cap` | vol_pct above this blocks MR entries (gate ON) |
| `TRADINGAGENTS_VALUE_DIP_REGIME_DOWNTREND_BAND` | `value_dip_regime_downtrend_band` | knife guard: price below 200-SMA by this |
| `TRADINGAGENTS_VALUE_DIP_REGIME_HALVE` | `value_dip_regime_halve` | instead of block, size x0.5 |
| `TRADINGAGENTS_RISK_DAILY_LOSS_BUDGET_PCT` | `risk_daily_loss_budget_pct` | daily realized-loss cap -> de-risk |
| `TRADINGAGENTS_RISK_HWM_SOFT_PCT` / `_HARD_PCT` | `risk_hwm_soft_pct` / `risk_hwm_hard_pct` | drawdown-from-HWM tiers |
| `TRADINGAGENTS_BREAKEVEN_TRIGGER` | `breakeven_trigger` | atr \| r \| structure (BE after confirmation) |
| `TRADINGAGENTS_STOP_NEVER_WIDEN` | `stop_never_widen` | unified stop never widened |
| `TRADINGAGENTS_MIN_HOLDING_DAYS` / `_MAX_TRADES_PER_PERIOD` | `min_holding_days` / `max_trades_per_period` | turnover guards |
| `TRADINGAGENTS_SLEEVE_TAG_ENABLED` | `sleeve_tag_enabled` |
| `TRADINGAGENTS_ENABLE_PREOPEN_RVOL` / `_PREOPEN_RVOL_INSTITUTIONAL_X` | `enable_preopen_rvol` / `preopen_rvol_institutional_x` | P1: pre-market RVOL vs 30d pre-open avg (Alpaca free IEX) |
| `TRADINGAGENTS_ENABLE_PREOPEN_DEPTH` | `enable_preopen_depth` | P2: live IEX quote-depth thin-book proxy |
| `TRADINGAGENTS_ENABLE_ALPHA_PROFILE` | `enable_alpha_profile` | C3: post-fill drift vs arrival in strategy-quality report | tag decisions with style sleeve |
| `TRADINGAGENTS_DRIFT_THRESHOLD` | `drift_threshold` | alpha-decay win-rate drift trigger |
| `TRADINGAGENTS_PSR_BENCHMARK_SHARPE` | `psr_benchmark_sharpe` | PSR benchmark Sharpe (default 0.0) |
| `TRADINGAGENTS_ROLLING_WINDOW` | `rolling_window` | rolling evaluation window (default 132) |
| `TRADINGAGENTS_DOWNSIDE_MAR` | `downside_mar` | minimum acceptable return for downside measures (default 0.0) |
| `TRADINGAGENTS_TRAILING_STOP_PCT` | `trailing_stop_pct` | peak-to-exit trail % for trailing exits (default 0.05) |
| `TRADINGAGENTS_ENABLE_TRAILING_EXIT` | `enable_trailing_exit` | peak-trailing / give-back exits on (default OFF) |
| `TRADINGAGENTS_RISK_PARITY_ENABLED` | `risk_parity_enabled` | risk-parity / min-variance allocation on (default OFF) |
| `TRADINGAGENTS_RISK_MANAGER_DRAWDOWN_PCT` | `risk_manager_drawdown_pct` | risk-manager drawdown trigger (default 0.05) |
| `TRADINGAGENTS_ENABLE_RISK_MANAGER` | `enable_risk_manager` | two-pass risk manager on (default OFF; not wired to runtime) |
| `TRADINGAGENTS_VOLUME_SHARE_VOL_LIMIT` | `volume_share_vol_limit` | volume-share slippage volume limit (default 0.1) |
| `TRADINGAGENTS_VOLUME_SHARE_PRICE_IMPACT` | `volume_share_price_impact` | volume-share slippage price impact (default 0.025) |
| `TRADINGAGENTS_ENABLE_OPTIONS_SURFACE` | `enable_options_surface` | CBOE delayed options chain -> IV/greeks surface (default OFF) |
| `TRADINGAGENTS_ENABLE_RISK_FREE_CURVE` | `enable_risk_free_curve` | NY Fed SOFR + Treasury par-yield curve (default OFF) |
| `TRADINGAGENTS_ENABLE_SCREENER` | `enable_screener` | yfinance universe screener (symbol/PE/EPS/beta/mkt-cap) (default OFF) |
| `TRADINGAGENTS_ENABLE_MARKET_MOVERS` | `enable_market_movers` | yfinance gainers/losers/actives (default OFF) |

| `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY` | `enable_correlation_penalty` | when on, the allocation plan (`allocation_block` / `get_allocation`) down-weights names whose average pairwise correlation with the rest of the book exceeds `correlation_threshold` (risk-parity concentration control) |
| `TRADINGAGENTS_CORRELATION_THRESHOLD` | `correlation_threshold` | avg pairwise correlation above this triggers the penalty (default 0.6) |
| `TRADINGAGENTS_MAX_PAIRWISE_CORR` | `max_pairwise_corr` | hard cluster ceiling on pairwise position correlation (default off) |  | `get_live_price_sanity` / `live_price_sanity` (below-day-low / mismatch flag)
| `TRADINGAGENTS_TRAILING_STOP_ATR_MULT` | `trailing_stop_atr_mult` | ATR-multiplied trailing stop (atr*mult) instead of static %% (default off) |
| `TRADINGAGENTS_CORRELATION_PENALTY_FRAC` | `correlation_penalty_frac` | weight cut for a penalized name, renormalized across the book (default 0.3) |
| `TRADINGAGENTS_TRANCHE_WEIGHTS` | `tranche_weights` |
| `TRADINGAGENTS_TRANCHE_STOP_MULT` | `tranche_stop_mult` |
| `TRADINGAGENTS_TRANCHE_RISK_PCT` | `tranche_risk_pct` |
| `TRADINGAGENTS_TRANCHE_ACCOUNT` | `tranche_account` |
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
opend_path/max_connections/call_timeout` (`moomoo_call_timeout` = per-call
wall-clock timeout in seconds, default 5.0; the SDK's own `ReqInfo.wait()`
allows 20s per call, so a degraded gateway can burn 20s per call across
hundreds of calls — the value screener's gating pass makes ~7 calls/symbol —
which is how a web job hits its subprocess budget).

**Vendor cache** - `vendor_cache_enabled=True`, `vendor_cache_ttl_seconds=21600`,
`vendor_cache_skip_categories={'news_data'}`.

**Strategy flags** - see section 5; `enable_regime`, `enable_factors`,
`enable_threshold_gate` default **False**; `enable_sentiment` default **True**
(computed sentiment score + surprise velocity injected into the sentiment
report). Only `enable_events` (B1 catalyst gate), `enable_reflection`,
`enable_sentiment`, and `enable_strategy_overlays` default **True**;
`enable_orderflow`, `enable_position_contract`, `enable_calibration`,
`enable_agreement`, `enable_independent_vote`, `enable_composite_rank`,
`enable_exits`, `enable_computed_context`, and `enable_risk_governor` default
**False** (opt-in;
the dev machine enables most via the gitignored `.env`). Sizing: `position_sizing='kelly'`, `target_vol=0.15`,
`kelly_fraction=0.25`, `position_odds=1.0`, `breakeven_atr=1.0`,
`target_atr=4.0`, `sector_cap_limit=0.35`, `risk_max_drawdown_pct=0.10`,
`risk_daily_cvar_budget_pct=0.03`, `risk_max_position_pct=0.45`,
`enable_tranche_risk` (default **False**) + `tranche_weights` (0.3,0.3,0.4),
`tranche_stop_mult` (1.5), `tranche_risk_pct` (0.015), `tranche_account` (100000)
— the deterministic tranche-scaling risk fold (`Value_Dip_swing_Continue.md`):
with `enable_position_contract` + `enable_risk_governor` on, the governor sizes
and throttles against the worst-case 3-tranche scale-in with config-frozen
parameters (never the LLM), enforcing BOTH the capital-at-risk budget (sum of
per-tranche losses at the hard stop) and the peak-deployed-at-scale-in
per-trade cap;
`risk_stress_shock_pct_1` / `risk_stress_shock_pct_2` (R2 scenario shocks, def -10%/-30%)
`evaluate_cost_bps=10`, `calibration_min_n=5`, `consensus_seeds=1`,
`max_book_names=10`, `max_name_weight=0.25`, `risk_audit_enabled` default True.
Correlation-aware allocation (industry-practice item 1):
`enable_correlation_penalty` (default **False**) + `correlation_threshold` (0.6)
+ `correlation_penalty_frac` (0.3) — when on, `allocation_block` and the
`get_allocation` tool down-weight names whose average pairwise correlation
with the rest of the book exceeds the threshold before the per-name/per-sector
caps (risk-parity style concentration control; names without a measurable
return series are never penalized).
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
| Order flow | `enable_orderflow` (F) | `strategies/orderflow.py` | distribution/divergence fold -> scale |
| Catalyst (B1) | `enable_events` (T) | `strategies/catalyst.py` | earnings/macro/Fed scale + verdict; `catalyst_hard_block_days` > 0 turns an imminent print into a risk-governor REJECT |
| Position contract | `enable_position_contract` (F) | `strategies/contract.py` | min(Kelly, risk/stop)*vol*flow*agree*catalyst; when a tranche plan is in play (`enable_tranche_risk`) the dollar stop/BE/target are measured from the weighted tranche `entry_price` hook |
| Risk governor | `enable_risk_governor` (F) | `strategies/risk_governor.py` | PASS/WARN/REJECT, `risk_halt`; CVaR from the configured `risk_basket_tickers` weighted mix (`book_risk.portfolio_cvar`) when set, else the analyzed name's series. If the weights sum `< 1.0` the remainder is treated as zero-return cash (dilutes the tail) - "include cash as overall portfolio". With `enable_tranche_risk` on it also sizes/throttles against the worst-case 3-tranche scale-in (`strategies/value_dip.py::tranche_risk_read`): the peak-deployed-at-scale-in fraction vs the per-trade cap and the capital-at-risk budget (sum of per-tranche losses at the hard stop vs `tranche_risk_pct`) |
| Calibration | `enable_calibration` (F) | `strategies/calibration.py` | calibrated P from ledger |
| Agreement | `enable_agreement` (F) | `strategies/consensus.py` | debate agreement -> size; with `enable_independent_vote` the agreement comes from the INDEPENDENT pre-debate stances, not the debate transcript (no conformity contamination) |
| Sentiment factor | `enable_sentiment_factor` (F) | `strategies/sentiment_research.py` + `overlays.fold_sentiment_into_overlay` | position scale x 1 ± `sentiment_factor_max_scale` ONLY when the name's measured rank IC ≥ `sentiment_factor_min_ic`; else neutral 1.0 (never blocks) |
| Computed context | `enable_computed_context` (F) | `strategies/debate_context.py` | numbers into debate |
| Exits | `enable_exits` (F) | `strategies/exits.py` | stops/BE/targets |
| Reflection | `enable_reflection` (T) | `strategies/reflection.py` | ledger, analyst hit-rates |
| Composite rank | `enable_composite_rank` (F) | `strategies/factors.py` | EY + momentum + 52w composite |
| Factor profile | `enable_factor_profile` (F) | `strategies/factor_expressions.py` | `get_factor_profile` — Alpha158-style 16-factor subset (momentum/reversal/volatility/value) off the OHLCV cache with expression-string cache + learn/infer fit-apply split (moments fit on train only); advisory, gated |
| Topk-Drop alloc | `enable_topk_drop` (F) | `strategies/portfolio_strategy.py` | screener alloc block + `get_topk_drop_plan` — hold top-k by score, sell worst-held, equal-weight (turnover = 2·drop/topk) |
| Enhanced-index alloc | `enable_enhanced_index` (F) | `strategies/portfolio_strategy.py` | screener alloc block + `get_enhanced_index_tilt` — convex program (long-only, Σw=1, turnover cap, b_dev, force-hold/sell masks, two-stage fallback); scipy SLSQP + pure-python fallback, cvxpy optional |
| Signal analysis | — (always-on pure calc) | `strategies/signal_analysis.py` | rank IC/ICIR, quantile long-short, IC-decay half-life, pred-autocorrelation; `strategy_quality_report` gains the with/without-cost excess-return table |
| Skill overlays | `enable_skill_overlays` (F) + `skill_dir` | `strategies/skills.py` + `strategies/skills/*.yaml` | declarative YAML strategy skills (instructions/tools/regimes/priority + bounded score adjustments), regime-from-opinion thresholds (bullish>=70 / bearish<=30 / 35-65), router precedence user->regime->priority |
| Prediction ledger + cost | `enable_prediction_ledger` (F) + `prediction_horizon_days` | `strategies/prediction_ledger.py` + `llm_cost.py` | log every decision as a scorable prediction (rating/direction/levels/confidence/horizon); score against realized closes at N days (return, hit, MAE/MFE, stop/target); provider cost estimate for quality-per-dollar |
| Report disclosure + invalidation | `enable_report_attribution` (F) | `strategies/report_disclosure.py` + `reporting.write_report_tree` | computed driver attribution (sum-100), consensus support/oppose, watch_conditions/next_check_time, >=1 invalidation per decision (stop/tp/data-quality/manual fallback), sources-used-vs-empty + models footers |
| News relevance + coalescing | `enable_news_relevance` (F) | `strategies/news_relevance.py` + `dataflows/news_cache.py` | deterministic relevance scoring (code/company/official +8, macro -12, clamp), spam admission, degrade triple (all_failed/empty/unavailable), owner-wait coalescing TTL cache |
| Market routing + health | `market_source_priority` / `vendor_breaker_*` (F) | `dataflows/market_router.py` + `vendor_breaker.py` + `effective_date.py` | market-classified priority chains (opt-in `MARKET_SOURCE_PRIORITY`), 3-fail/300s breaker + half-open probe + negative capability cache, `VendorResult` honesty fields (fallback_from/stale/data_quality/missing_fields), effective-trading-date + all-closed skip (fail-open) |
| Decision guardrail | `enable_decision_guardrail` (F) | `strategies/decision_guardrail.py` | post-PM downgrade-only stabilizer (risk-cap at Hold, near-resistance/no-flow, near-support/no-outflow) with recorded `guardrail_reason`; versioned 0-100 <-> rating consistency check; PM `data_quality`/`guardrail_reason`/`risk_cap` fields + confidence cap on stale data; per-field integrity retry in `structured.retry_structured_missing_fields` |
| Backtest tradability | `backtest_limit_threshold` / `backtest_volume_participation` / `backtest_deal_price` | `strategies/market_tradability.py` | limit-up/down gates, suspended days (NaN close), participation caps, deal-price selector; wired into `scripts/backtest_strategy.py` fills (flags `--limit-threshold` etc.) + `fill_model` honesty block |

Off by default: `enable_regime`, `enable_factors`,
`enable_threshold_gate`. `enable_sentiment` is now **on** (computed sentiment
score + surprise velocity injected into the sentiment report). Pure
`strategies/risk_manager.py` (`manage_risk` two-pass exit override +
`trailing_stop_targets`) also ships advisory: `enable_risk_manager` is OFF by
default and it is not wired into the runtime graph yet. Strategy-eval
scripts: `scripts/evaluate_config_gate.py`
(G5 walk-forward/PBO), `scripts/orderflow_evaluate.py` (ledger evaluation),
`scripts/risk_report.py` (risk audit).

## 6. Vendor data contract

Everything flows through `route_to_vendor(method, *args, **kwargs)` in
`dataflows/interface.py`. The vendor chain per category is configured in
`data_vendors` (default chains: `eodhd,moomoo,yfinance`, `fred,moomoo`,
`polymarket,moomoo`, `moomoo,finnhub,yfinance`, `sec_edgar`). Errors propagate through
`dataflows/errors.py`, the router converts to sentinel strings
(`NO_DATA_AVAILABLE`, `DATA_UNAVAILABLE` optional, `DATA_DISABLED`).
`technical_indicators` / `fundamental_data` / `news_data` end their chains with
`alpha_vantage` (key-gated last fallback via `ALPHA_VANTAGE_API_KEY` in `.env`).

### ## 6.1 Tools by category (auto-generated)

- `core_stock_apis` : `get_stock_data`
- `technical_indicators` : `get_indicators`
- `fundamental_data` : `get_fundamentals`, `get_balance_sheet`, `get_cashflow`,
  `get_income_statement`, `get_basic_financials`, `get_company_peers`,
  `get_insider_activity`, `get_form4_insider`
- `news_data` : `get_news`, `get_global_news`, `get_insider_transactions`, `get_massive_news`
- `news_sentiment` (optional): `get_news_sentiment` — daily series via
  `eodhd,alpha_vantage,gdelt` (EODHD `/sentiments` primary)
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
  `get_session_discipline`, `get_earnings_quality`,
  `get_bollinger_pct_b`, `get_tranche_plan`, `get_trade_expectancy`,
  `get_fcf_yield`, `get_valuation_z_score`, `get_value_dip_setup`,
  `get_balance_sheet_health`, `get_macd_divergence`, `get_vdu_entry_setup`,
  `get_support_structure`, `get_decline_driver_check`,
  `get_extended_indicators` (Ichimoku/CCI/ROC/momentum/TRIX/Force/A-D/VPT/CMF/
  anchored VWAP/golden-death — `strategies.extended_indicators`),
  `get_candlestick_patterns` (doji/hammer/shooting-star/engulfing/morning+
  evening star — `strategies.extended_indicators.scan_candlesticks`),
  `get_news_sentiment_series` (daily news-sentiment -1..1 + 7d SMA + latest
  innovation, `news_sentiment` chain),
  `get_sentiment_lead_lag` (Pearson/Spearman cross-correlation vs forward
  returns — `strategies.sentiment_research`)
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

- stock/indicators/financials/insiders: `alpha_vantage`, `yfinance`, `moomoo`, `eodhd` (OHLCV only), `tiingo`, `twelve_data` (OHLCV only), `stockdata` (OHLCV only)
- news/global-news: `alpha_vantage`, `yfinance`, `finnhub`, `massive`, `stockdata`, `gdelt`, `benzinga`, `newsapi` (GDELT keyless native tone; NewsAPI 100 req/day; Benzinga free tier - GDELT/Benzinga opt-in via `news_data` chain, not default)
- news-sentiment: `eodhd` `/sentiments` (primary, EOD plan), `alpha_vantage` `NEWS_SENTIMENT` (25 req/day), `gdelt` tone
- quant calculators (tools, `strategies/*`): `get_volatility_estimators` (Parkinson/GK/YZ/EWMA/GARCH), `get_garch_volatility`, `get_covariance_read` (Ledoit-Wolf shrunk + EWMA covariance), `get_concentration_read` (active share / effective holdings / HHI / entropy), `get_tail_decomposition` (incremental/component VaR), `get_tail_extreme_var` (EVT/GPD extreme-quantile VaR/ES), `get_mean_reversion_quality` (AR(1)/OU half-life), Roll spread + Kyle lambda (`get_liquidity_risk`/`get_kyle_lambda`), `get_kelly_alloc` (multi-asset fractional Kelly), preferred YTM/duration (capital_income `--fi`), credit hazard/default-prob (`get_credit_spread_read`), variance-swap strike (`get_variance_premium`), implementation shortfall (strategy_quality `avg_is_bp`)
- market snapshot fallbacks: Massive -> EODHD -> Tiingo -> Twelve Data
- crypto prices fallbacks: Tiingo -> Twelve Data
- macro: `fred`, `massive`, `moomoo` (optional)
- prediction markets: `polymarket`, `moomoo` (optional, SG/MY-gated)
- analyst ratings + earnings calendar: `finnhub`, `moomoo`, `yfinance` (keyless
  fallback: `get_analyst_ratings_yfinance` = recommendation summary +
  price-target consensus; `get_earnings_calendar_yfinance` = earnings dates +
  EPS surprise). Institutional holdings also add a keyless `yfinance` option
  (`get_institution_holdings_yfinance`).
- finnhub free-tier extra (key-gated): `get_basic_financials` (metrics),
  `get_company_peers`, `get_insider_activity` (insider sentiment);
  `get_fundamentals` also accepts `finnhub` as a vendor
- options chain: `yfinance`, `moomoo`
- SEC filings: `sec_edgar` (when EDGAR fails for any reason — e.g. HTTP 403 from
  SEC fair-access throttling or a non-US ticker with no EDGAR record — the
  `get_sec_filings` tool falls back to Massive's `get_form4_insider_massive`
  Form-4 insider-activity data, returned under an explicit label so the agent
  does not mistake it for the full 8-K/10-K set)
- short interest: `yfinance`, `moomoo`, `massive`
- short volume (daily short-sale ratio, Massive-only): `massive`
- all A-series/tier tools: `moomoo` only (optional)

`VENDOR_LIST = yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo, massive, eodhd, cboe, federal_reserve, tiingo, twelve_data, stockdata, gdelt, benzinga, newsapi`.

**EODHD** (`TRADINGAGENTS_EODHD_API_KEY`, key-gated) — the **primary OHLCV
vendor** (EOD plan $19.99/mo = 100k calls/day @ 1000/min, 30+ years):
`get_stock_data_eodhd` serves daily bars as the same CSV shape yfinance/moomoo
produce, registered first in the `core_stock_apis` chain
(`eodhd,moomoo,yfinance` by default) so moomoo/yfinance stay as fallbacks.
The EOD plan also unlocks `get_news_eodhd` (news), `get_corporate_actions_eodhd`
(splits + dividends), `get_exchange_symbols_eodhd` (full US symbol list,
~18k common stocks) — the screener's default `--universe eodhd-us` source —
replacement; `get_top_movers_symbols_eodhd` is the machine-readable symbol
table behind it, consumed by the screener's `--universe eodhd-losers`
(equity-filtered against the exchange-symbol common-stock list).
`--value-dip-loose` relaxes the value-dip technical entry to RSI<=35 OR
%b<=0.10 and appends a ranked near-miss table).
These back the `get_market_snapshot` / `get_top_movers` tools
when Massive 403s on the free plan.
Fundamentals/technicals/intraday/options are **not** on the EOD plan (they
need the $59.99 Fundamentals feed), so those chains keep moomoo/yfinance
first. A `--vendor eodhd` preset (`batch.py`/`pipeline.py`) puts EODHD first
in the OHLCV + news + corporate-actions chains and disables the moomoo-only
enrichment.

**Tiingo** (`TIINGO_API_KEY`, free *Starter* tier, key-gated) — additive market
data: deep EOD OHLCV (`/tiingo/daily/{t}/prices`, 7+ yrs, with `resampleFreq`
daily/weekly/monthly/annually), **fundamental statements in JSON**
(`/tiingo/fundamentals/{t}/statements` — income/balance/cashflow keyed by
``dataCode``, rendered to canonical-friendly ``label : value`` blocks that
`statement_parsing` maps via `_ROW_ALIASES`), a delayed **IEX quote**
(`/iex/{t}`), and **crypto OHLCV** (`/tiingo/crypto/prices`). News (403) and
intraday (404) are NOT on the free tier. Low caps (~1,000 calls/day, 50/hr,
500 symbols/mo) mean it sits *last* in the chains after eodhd/moomoo/massive,
relying on the 6h disk TTL cache; a 429 degrades to the next vendor via
`VendorRateLimitError`. The IEX snapshot backs `get_market_snapshot` as a
third fallback (Massive -> EODHD -> Tiingo).

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
  **EODHD fallback**: when Massive 403s (free plan), `get_market_snapshot`
  falls back to `eodhd.get_market_snapshot_eodhd` (`/api/real-time/{ticker}`,
  live 15-20 min delayed OHLCV + change, works on the EOD plan) and
  `get_top_movers` falls back to `eodhd.get_top_movers_eodhd`
  (`/api/real-time/{ticker}?ex=US`, one call returns ~18k US stocks sorted by
  change_p — a movers + universe replacement).

### 6.3 Symbol mapping (Yahoo <-> moomoo / broker)

`dataflows/symbol_utils.py::normalize_symbol()` maps broker symbols to Yahoo
gold `XAUUSD -> GC=F`, forex `EURUSD -> EURUSD=X`, crypto
`BTCUSD -> BTC-USD`, indices `SPX500 -> ^GSPC`; moomoo code map
(`_moomoo_code()`: US., HK. pad, JP., SH., SZ., AU., CA., SG., MY., CC.USD).

**US share classes are quoted with a hyphen on Yahoo** (`BRK-B`, `BF-A`), but
moomoo emits dotted (`BRK.B`, `MOG.A`, `MOG.B`, `PBR.A`), which Yahoo cannot
resolve. `normalize_symbol` converts a dotted single-letter share-class suffix
(`.A`/`.B`/`.C`/`.K`...) to the hyphen form (`BRK.B -> BRK-B`), while leaving
London's single-letter `.L` exchange and all multi-letter exchange suffixes
(`.SA` Brazil, `.TO`, `.AX`, `.HK`, `.NS`, `.BO`, ...) untouched. Moomoo's
`_moomoo_code` deliberately does NOT use this - it keeps the raw dotted form
the movers rank returns - so both vendors resolve the same symbol.

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
| `get_swing_exits(ticker)` | `swing.chandelier_exit` + `trail_ema` + `targets_rr` | market | chandelier trailing stop (3x ATR below 22-bar high) + 20-day EMA trail + 2R/3R targets |
| `get_dip_technical(ticker)` | `swing.rsi` + `technical_factors` (KST/MFI/Stoch) + `value_dip.bollinger_pct_b` | market | RSI/%b + Stochastic + MFI + KST dip-timing read (OVERSOLD / not-oversold) |
| `get_mean_reversion_tech(ticker)` | `technical_factors` (StochRSI/RSI2/W%R/Keltner/Donchian/OBV/PSAR/Elder) | market | mean-reversion dip-timing + exit technicals |
| `get_opening_range(ticker)` | `market_session.opening_range` | market | ORB breakout + 2R stop/target |
| `get_gap_type(ticker)` | `market_session.gap_type` | market | common/breakaway/runaway/exhaustion + fill stats |
| `get_order_imbalance(ticker)` | `market_session.order_imbalance` | market | buy/sell-heavy from flow nets |
| `get_premarket_liquidity(ticker)` | `market_session.premarket_liquidity` | market | thin-book warning |
| `get_post_close_confirmation(ticker)` | `market_session.post_close_confirmation` | market | stopped-out / target-hit / holding |
| `get_gdelt_sentiment(ticker, look_back_days?)` | `gdelt.get_gdelt_tone_series` | news | GDELT native daily news-tone series (keyless, -100..100) - a computed sentiment read |
| `get_technical_factors(ticker)` | `technical_factors` (ADX/pivots/Aroon/Fisher/Chaikin/Elder-Ray/Supertrend/volume-profile) | market | extended technicals in one call (shares the run-level OHLCV cache) |
| `get_extended_indicators(ticker)` | `strategies.extended_indicators` (Ichimoku/CCI/ROC/momentum/TRIX/Force/A-D/VPT/CMF/anchored VWAP/golden-death) | market | the standard trend/momentum/volume group plus cloud + VWAP cost basis, one call (shares the OHLCV cache) |
| `get_candlestick_patterns(ticker)` | `strategies.extended_indicators.scan_candlesticks` | market | latest-bar doji/hammer/shooting-star/engulfing/morning+evening star scan |
| `get_book_tail_risk(ticker, weights?)` | `book_risk.portfolio_cvar` + `book_correlated_stress` + `drawdown_gate` | market | book-level portfolio CVaR + correlated -10% stress + drawdown gate |
| `get_covariance_read(tickers)` | `covariance_models.ledoit_wolf_shrink` + `ewma_covariance` | market | Ledoit-Wolf shrunk covariance (delta = b2/d2) + EWMA vol for a name list |
| `get_concentration_read(weights, benchmark_weights?)` | `portfolio.active_share` + `weight_hhi` + `effective_holdings` + `weight_entropy` | market | how concentrated a proposed book is (active share vs benchmark, HHI, entropy) |
| `get_tail_extreme_var(ticker, alpha?)` | `book_risk.extreme_quantile_var` | market | EVT/GPD extreme-quantile VaR/ES (extrapolates beyond the observed worst day) |
| `get_kyle_lambda(ticker)` | `liquidity_risk.kyle_lambda` | market | daily-bar price-impact slope (cross-sectional liquidity proxy) |
| `get_kelly_alloc(expected_excess_returns)` | `portfolio.kelly_weights` | market + fundamentals | multi-asset fractional Kelly alloc (w = f·Σ⁻¹μ, long-only) |
| `get_liquidation_days(ticker, shares_to_liquidate?)` | `liquidity_risk.days_to_absorb` | market | days for the market to absorb a block at a 15% participation cap |
| `get_premarket_review(ticker, prior_close?, open_price?, prior_stop?, entry_price?)` | `pre_market.review_decision` | market | deterministic CONFIRM / REVISE / REJECT arbiter from measured deltas |
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
| `get_ratios(ticker, date?)` | `strategies.ratios.compute_ratios` (local derivation; Massive plan-gated cross-check via `get_fundamentals`) | fundamentals | computed EV/EBITDA, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash ratio, dividend yield, FCF, market cap (free, no paid plan; missing inputs n/a) |
| `get_exit_check(entry, close, atr)` | `strategies.exits.exit_check` | market | stop-to-breakeven, ATR target, holding action |
| `get_allocation(scores, sector_map?, returns_by_name?)` | `strategies.portfolio.adjust_for_caps` (+ `correlation_penalty` when `enable_correlation_penalty` is on and return series are provided) | fundamentals | cap-respecting book allocation; optionally correlation-penalized (down-weights names whose avg pairwise correlation with the book exceeds the threshold) |
| `get_regime_components(ticker)` | `strategies.regime` | market | vol_pct / trend / chop / regime label breakdown |
| `get_consensus(ratings)` | `strategies.consensus` | PM tool + injected | numeric agreement -> high/low consensus |
| `get_momentum_detail(ticker)` | `strategies.momentum` | market | pillars, rvol, vwap, ema9, first-pullback |
| `get_beat_miss_sizing(side, catalyst)` | `strategies.events.position_mult_by_side` | news | post-earnings key multiplier |
| `get_dcf_valuation(ticker, date, growth?, erp?)` | `strategies.dcf.compute_dcf` | fundamentals | provider-sourced DCF fair value + WACC / EV breakdown |
| `get_sector_rank(ticker)` | `strategies.sector_rank.rank_sectors` + `sector_standing` | market | 11-SPDR 1m/3m momentum ranking + the ticker's sector standing |
| `get_strategy_quality(ticker, returns?)` | `strategies.evaluate` | market | net CAGR / annualized vol / Sharpe / Sortino / PSR / max drawdown over a return series |
| `get_downside_read(ticker, target?)` | `strategies.rate_utils.downside_measures` | market | semi-deviation / downside deviation / shortfall probability / average shortfall vs a target (MAR) |
| `get_horizon_var(ticker, horizon_days?, alpha?)` | `strategies.book_risk.var_cvar_horizon` | market | empirical + parametric VaR/CVaR at a multi-day horizon, with the sqrt(T) i.i.d. scaling gate |
| `get_trailing_exit(ticker, entry, peak, current, trail_pct?)` | `strategies.exits.trailing_stop_exit` | market | peak-trailing / give-back stop verdict + exit price |
| `get_exit_plan(entry, atr, current, peak?, stop?, giveback_pct?)` | `strategies.exits.breakeven_after_confirmation` + `max_giveback_exit` | market | structure/R breakeven trigger + margin-giveback stop in one exit-management read |
| `get_scaleout_plan(entry, stop, t1_fraction?)` | `strategies.swing.scaleout_plan` | market | tiered partial-profit plan (sell T1 fraction -> break-even -> trail) |
| `get_payoff_asymmetry(ticker, returns?, threshold?)` | `strategies.statistical.omega` | market | Omega ratio (gains/losses payoff asymmetry) about a threshold |
| `get_book_correlation(returns_by_name, method?)` | `strategies.statistical.correlation_matrix` | market | full pairwise correlation (avg + max pair) over a book |
| `get_risk_parity_alloc(ticker, returns_by_name)` | `strategies.portfolio_optimizer` (risk_parity + min_variance + **max_diversification** + risk_contribution) | market | risk-parity weights, min-variance weights, max-diversification weights (Choueifaty `Σ⁻¹σ`) and per-name risk contributions from a real covariance matrix |
| `get_margin_of_safety(ticker, intrinsic)` | `strategies.normalized.margin_of_safety` | fundamentals | (intrinsic - price)/intrinsic safety band (wide/modest/negative) |
| `get_composite_rank(ticker, factors?)` | `strategies.factors.composite_score` | fundamentals | cross-sectional value+momentum composite percentile vs industry peers |
| `get_tail_risk(ticker, alpha?)` | `strategies.book_risk.cvar` / `simple_var` / `stress_loss` + **`cdar`** | market | historical VaR / CVaR tail budget + CDaR/DVaR drawdown-tail + -10% uniform stress loss |
| `get_credit_spread_read(date)` | `strategies.credit_spread.credit_stress_level` | market | FRED ICE BofA HY/CCC/BB OAS + deterministic credit-cycle band (low/mod/high/severe) + de-risk scale |
| `get_session_discipline(ticker, peak_pnl?, current_pnl?)` | `strategies.momentum.session_flags` + `psych_level` + `past_optimal_window` | market | intraday walk-away rules (giveback, max-daily-loss, past 10:00 ET optimal) + nearest psych levels |
| `get_earnings_quality(ticker, date)` | `strategies.normalized.accruals_ratio` + `trap_verdict` | fundamentals | Sloan accruals ratio + the forensic trap verdict incl. the accrual evidence trigger |
| `get_bollinger_pct_b(ticker)` | `strategies.value_dip.bollinger_pct_b` | market | Bollinger %b (price position inside the 20-day 2-sigma band); %b <= 0 at/piercing the lower band, <= 0.10 the mean-reversion entry zone |
| `get_tranche_plan(ticker, weights?, risk_pct?, account?)` | `strategies.value_dip.tranche_plan` | market | 3-tranche scale-in plan (P1/P2/P3 at 1.0/2.0 ATR, weighted avg entry, composite stop P3-1.5ATR, capital-at-risk check, 1.8R/3.0R targets + blended R:R + breakeven win rate) |
| `get_trade_expectancy(p_win, avg_win, avg_loss, rr?)` | `strategies.value_dip.expectancy` + `breakeven_win_rate` | market | per-trade expectancy E = p*W - (1-p)*L and breakeven win rate 1/(1+R:R) |
| `get_fcf_yield(ticker, date)` | `strategies.value_dip.fcf_yield` | fundamentals | FCF / market cap (>= 6% is the value-dip value-floor row) |
| `get_valuation_z_score(ticker, date, multiple?)` | `strategies.value_dip.valuation_z_read` | fundamentals | historical valuation Z (current vs own trailing P/E, EV/EBITDA or P/FCF; Z <= -1.5 = cheap vs history) |
| `get_value_dip_setup(ticker, date)` | `strategies.value_dip.value_dip_setup` | fundamentals | the hybrid allocation matrix (value floor + technical entry + trade risk + exit target) as one computed candidate verdict |
| `get_balance_sheet_health(ticker, date)` | `strategies.value_dip.balance_sheet_health` | fundamentals | D/E < 1.0 OR current ratio > 1.5 (Step-1 balance-sheet gate) |
| `get_macd_divergence(ticker)` | `strategies.value_dip.macd_divergence` | market | Daily RSI(14) / MACD-histogram momentum divergence (bullish-divergence / higher-low / lower-low-confirmation) |
| `get_vdu_entry_setup(ticker)` | `strategies.value_dip.vdu_entry_setup` | market | Step-2 entry ladder: volume dry-up near support -> divergence/higher-low -> trigger candle (close above prior high, RVOL >= 1.3x) |
| `get_support_structure(ticker)` | `strategies.value_dip.support_structure` | market | major weekly / multi-month base support + 200-day SMA proximity |
| `get_decline_driver_check(ticker, date)` | `strategies.value_dip.decline_driver_check` | fundamentals | negative-force screen (clean/caution/structural): trap-HIGH, accruals>6%, negative 12-1m momentum, non-positive FCF/ROE, severe EPS decline |

| `get_regime_gate_read(ticker, catalyst_window?)` | `strategies.regime.regime_gate_read` | market / risk debators | mean-reversion knife guard: vol_pct + fast-downtrend + pass/block verdict |
| `get_fixed_risk_size(equity, risk_frac, entry, stop_loss, commission_rate?, units?)` | `strategies.risk_sizing` | market / risk debators / trader | commission-aware, tranche-aware fixed-risk share count (the governor-budget sizer) |
| `get_exit_overrides(targets, state_by_name, max_drawdown_pct?, trail_pct?)` | `strategies.risk_manager.manage_risk` + `trailing_stop_targets` | risk debators | two-pass liquidate/shrink overrides (Lean L1) from persisted entry/peak/current state |
| `get_pre_trade_read(symbol, notional, max_notional?, max_rate?, window_secs?)` | `strategies.risk_checks.pre_trade_check` + `RateLimiter` + `notional` | risk debators | notional-cap + rolling-rate submission gate (advisory) |
| `get_ledger_risk_state(ticker)` | memory log + `strategies.pre_market.ledger_track_record` | risk debators | realized win-rate drift + paper-reviewer track record (daily-loss/HWM inputs) |
| `get_trade_plan(ticker, price?)` | `strategies.trade_plan.build_trade_plan` | risk debators / trader | the written plan card as a callable |
| `get_fixed_income_risk(ticker, years?)` | `strategies.fixed_income` | fundamentals | preferred yield + duration/DV01/convexity risk rows (perpetual YTM n/a) |
| `get_pair_risk(x, y, maxlag?)` | `strategies.statistical.cointegration_pair` + `granger_causality` | market | Engle-Granger cointegration + lag-wise Granger causality |
| `get_pair_trade_signal(x, y, entry?, exit_thresh?, stop?)` | `strategies.statistical.pair_signal` (`spread_zscore` + cointegration + half-life) | market | cookbook recipe-3 pairs signal: entry \|z\|≥2 / exit ≤0.5 / stop ≥3, dollar-neutral `pair_quantities` + VECM `ecm_loading` advisory |
| `get_ts_momentum_weights(closes_by_name, horizon?, target_vol?, max_leverage?)` | `strategies.momentum.ts_momentum_weights` | market | MOP-style time-series momentum weights: `sign(12m log return) / EWMA vol`, target-vol normalized, gross-leverage capped |
| `get_event_pnl_response(spot, delta, gamma, vega, theta, dS_pct, dSigma?)` | `strategies.options_math.greek_pnl_response` | market | cookbook recipe-5 scenario P&L: `Δ·dS + ½Γ·dS² + ν·dσ + Θ·dt` per option unit |
| `get_merton_distance(equity, debt, equity_vol, r?, t?)` | `strategies.credit_spread.merton_distance_to_default` | market / risk debators | structural distance-to-default (equity-as-a-call fixed-point; DtD = d2 + risk-neutral PD) |
| `get_book_depth_read(bid, ask, bid_size, ask_size)` | `strategies.market_session.book_depth_read` | market | microprice `(bid·ask_sz + ask·bid_sz)/(bid_sz+ask_sz)` + order-book imbalance + thin-side verdict |
| `get_vif_read(columns)` | `strategies.statistical.variance_inflation_factor` | market | per-column VIF (collinearity check; > 5 = HIGH) |
| `get_vol_cones(ticker)` | `strategies.rotation.vol_cones` | market / risk debators | multi-horizon realized-vol percentiles (5/10/21/63/126d) |
| `get_trade_excursions(trades)` | `strategies.journal.trade_excursions` | market | MAE / MFE / profit-factor / max intra-trade drawdown (exit quality) |
| `get_alpha_scoring(direction, predicted_magnitude?, period_days?, actual_return?, confidence?)` | `strategies.alpha_eval.alpha_score` | fundamentals | direction + magnitude-scored alpha ("said +12%, realized +2%") |

### 6.5b Decision-agent wiring (risk debators / Trader / PM / researchers)

- The 3 risk debators (aggressive/conservative/neutral) now run an **in-node
  risk-tool loop** (`agents/utils/risk_tool_loop.py`): the plain LLM is bound
  to a 23-tool risk set (gate/tail/liquidity/vol/tranche/sizing/exits/credit/
  pre-trade/ledger), capped at `MAX_TOOL_ROUNDS` (8), and degrades to a plain
  invocation when the provider cannot bind tools.
- The **Trader** runs a 12-tool verification pass after its structured
  proposal (sizing / exit / tranche / expectancy / plan-card tools).
- The **Research Manager** and **Bull/Bear researchers** receive the computed
  decision context (regime gate, plan card, risk snapshot, factsheet).
- `get_risk_gate` exposes the full governor surface: `book_total_pct`,
  `daily_loss_pct` (daily-loss budget), `hwm_drawdown_pct` (soft/hard
  high-water-mark tiers), `sector_pct` (sector cap), `capital_at_risk_pct` /
  `risk_cap_pct` (tranche capital-at-risk), `liquidity_verdict`, `halted`.



Every tool follows the no-fabrication contract: exact computed numbers or an
 explicit "unavailable" message (both recorded in the agent's tool history for
 auditability), never an invented value.

### 6.6 Canonical line items & prior periods

The value screens read a canonical line-item dict (the vendor-output ->
canonical layer in ``tradingagents.dataflows.statement_parsing``, re-exported
by ``scripts/value_screener`` for the backend CLI). For moomoo markdown the
parser emits ``{"current": .., "prior": ..}`` dicts for keys present in two
consecutive periods (statements list newest-first; tables are sorted by period
year). The Beneish M-Score and Piotroski time-components use
``current``/``prior`` via ``quantitative_scores``' ``_num()``/``_prv()``;
every other read unwraps with ``statement_parsing._latest()``. moomoo
``-``-prefixed sub-item / contra lines (``-Accounts Receivable``,
``-Accumulated Depreciation``) are skipped so the aggregate value wins.
Because the M-Score needs both periods, its M column now computes on moomoo
data (previously always n/a), and the latest-value bug (which silently kept
the OLDEST period) is fixed.

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
When the risk governor ran, the `Risk Gate (computed)` block also renders the
`Analyzed-name CVaR` and (with a configured risk basket) the
`Portfolio (book) CVaR — this fed the gate` lines from `risk_context`; with the
tranche fold on, it additionally shows `Tranche peak-deployed` (cap-ok) and
`Tranche capital-at-risk` from `tranche_context`.
`scripts/rebuild_complete_report.py` re-renders folders without a re-run and
preserves `Risk Gate (computed)` blocks.

## 9. Entry points

| Command | Purpose |
| --- | --- |
| `tradingagents` | interactive   CLI (typer/rich), full flow |
| `python batch.py --symbols ...` | headless concurrent; `--vendor`, `--workers`, `--analysts`, `--depth`, `--date` |
| `python pipeline.py --universe top-losers --top 5` | screener + composite rank + batch (B2) |
| `python scripts/value_screener.py ...` | value screens / scans / composite |
| `python scripts/action_report.py ...` | conditional action report (basket vs report verdicts vs live market) |
| `python scripts/positions_to_basket.py ...` | combine broker position CSVs -> TRADINGAGENTS_RISK_BASKET_* weights (cash in the denominator; `--apply` rewrites .env) |
| `python scripts/rebuild_complete_report.py reports/<dir>` | re-render TOC reports |
| `python scripts/smoke_structured_output.py` | smoke structured output |
| `python main.py` | minimal Python API demo |

### Entry points: detailed flags

- batch.py: `--symbols` (required) `--date` `--workers` (1-4 default=capped,
  via `batch.effective_workers`; `TRADINGAGENTS_MAX_WORKERS` raises the cap)
  `--depth` (shallow|medium|deep) `--analysts` (market|social|news|fundamentals)
  `--vendor` (default|moomoo|yfinance|eodhd).
- pipeline.py: `--universe` (tickers|top-losers|heat-proxy|top-movers-massive)
  `--file` `--top` `--limit` `--market` `--movers-count` `--min-mcap`
  `--price-min` `--pe-max` `--workers` (capped via `batch.effective_workers`)
  `--analysts` `--depth` `--vendor`.
  `-u/--universe` (eodhd-us default | tickers | top-losers | heat-proxy |
  eodhd-losers | moomoo-screen) `--market` `-n/--movers-count` `--min-mcap`
  `--price-min` `--pe-max` `--min-avg-vol` `--min-atr-pct` `--max-mcap`
  `--min-eps-yoy` `--min-rev-yoy` `--min-roe` `--max-chg5d` `--max-rsi`
  `--max-debt-assets` `--dip-days` `--pb-min` `--pb-max` `--exchanges`
  (NYSE,NASDAQ default, '' = off) `--sector-rank`
  `--revision` `--inst-accum`
  `--intraday` `--enrich-sector` `--enrich-rev` `--enrich-inst` `--scan`
  (value|trend-pullback|breakout|momentum|swing|vcp|value-dip|all)
  `--value-dip-loose` `--knife-z` `--out-dir` `--rank` `--enable-float` `--journal`
  `--alloc`.
- action_report.py: `--basket` (SYM=W,SYM=W override; default config
  `risk_basket_weights`) `--reports-dir` (default `reports/`) `--date`
  `--llm` (judge UNKNOWN conditions) `--json` `--dry-run` `--out-dir`
  (default `action_reports/`, keep-only-newest).
- positions_to_basket.py: `--positions DIR` (default repo `positions/`) +
  explicit CSV files; `--apply` (backup `.env.bak`, rewrite the two basket
  lines); `--min-value` / `--exclude SYM` (repeatable); `--write-book-json`
  (dollar book to `positions/book_value.json`, gitignored); `--json`.

## 10. Docs index

- `docs/AGENT_ONBOARDING.md` - environment runbook (interpreter, quirks, layout)
- `docs/howto_end_to_end.md` - screener -> pipeline -> reports walkthrough
- `docs/EasyManual.md` - the same project explained for a teenager (no finance
  degree needed): web app first, then terminal, reading reports, glossary
- `docs/developer/` - full developer map (topology, graph/workflow, dataflow,
  strategies, agents/tools, entrypoints, persistence, dev guide, tests layout,
  Massive)
- `docs/massive_integration.md` - the Massive.com add-on plan + entitlement map
- `docs/pre_market_review.md` - design + **implemented** (choice (a)): a pre-market overnight
  reviewer that CONFIRMs / REVISEs / REJECTs a prior close-time decision against
  measured deltas (gap, catalyst window, re-anchored tranche/contract, governor)
  — `strategies/pre_market.py` (deterministic arbiter + paper-book ledger) +
  `scripts/pre_market_review.py` (standalone pre-open; real pre-market quote,
  planned-level re-anchor), `scripts/nightly_review.py` (batch-summary driver;
  `--mode recent` reviews each symbol's newest report folder instead, covering
  CLI/API runs that never write a batch summary),
  `scripts/decision_history.py` (decision series), and the opt-in `batch.py`
  same-night step (`enable_pre_market_review`).
- `docs/developer/11-agent-decision-tools.md` - the six decision-grounding tools
  implemented for the analyst LLMs
- `docs/developer/12-data-providers.md` - the 13 data providers/sources and
  per-category vendor chains
- `Strategies/*` - strategy plans and specs (index: `Strategies/index.md`)
- `docs/design_multi_agent_debate.md` - research + design (no code) for the
  bull/bear research debate: two-layer judiciary (deterministic L1 gates
  before a blind dimensioned L2 LLM judge), heterogeneous per-role models +
  capability matrix, FSM orchestrator + canonical wire schemas
  (`DebaterTurnPayload` / `L1DeterministicResult` / `L2JudgeDimensionedRubric`)
  from `Strategies/Multi_Agents_Debate.md`, phased P0-P6 all `enable_*`-flagged
  OFF.
- `docs/design_quantlib_lean_enhancements.md` - research-to-design: deep study
  of QuantLib (pricing/measurement rigor) + Lean (framework/operational rigor)
  mapped to concrete deterministic `strategies/*` enhancements, phased
  (highest ROI first) with quick-wins verdict.
- `docs/design_nautilus_trader_enhancements.md` - research-to-design: deep study of NautilusTrader (execution/evaluation rigor) mapped to a backtest harness, consistent risk sizing, statistics and config validation - implemented (see CHANGELOG).
- `docs/design_openbb_enhancements.md` - research-to-design: deep study of
  OpenBB (typed provider envelopes, self-describing REST/CLI/MCP surface,
  quantitative/econometrics/technical toolkit, Tauri desktop + SPA product
  surfaces) mapped to TradingAgents `dataflows/` + `strategies/` and
  `trading_web` (watchlist/grid/charts/credentials/presets/MCP), phased with a
  quick-wins verdict.