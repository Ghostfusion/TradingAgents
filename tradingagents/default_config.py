import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER": "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM": "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM": "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL": "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE": "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS": "max_risk_discuss_rounds",
    "TRADINGAGENTS_RESEARCH_DEPTH": "research_depth",
    "TRADINGAGENTS_ENABLE_DEBATE": "enable_debate",
    "TRADINGAGENTS_DEBATE_BULL_MODEL": "debate_bull_model",
    "TRADINGAGENTS_DEBATE_BEAR_MODEL": "debate_bear_model",
    "TRADINGAGENTS_DEBATE_JUDGE_MODEL": "debate_judge_model",
    "TRADINGAGENTS_DEBATE_NEUTRAL_MODEL": "debate_neutral_model",
    "TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE": "debate_judge_ensemble",
    "TRADINGAGENTS_DEBATE_MAX_ROUNDS": "debate_max_rounds",
    "TRADINGAGENTS_DEBATE_MAX_OUTPUT_TOKENS": "debate_max_output_tokens",
    "TRADINGAGENTS_DEBATE_TEMPERATURE": "debate_temperature",
    "TRADINGAGENTS_DEBATE_JSON_MODE": "debate_json_mode",
    "TRADINGAGENTS_DEBATE_MIN_GAIN": "debate_min_gain",
    "TRADINGAGENTS_DEBATE_STOP_CONSECUTIVE": "debate_stop_consecutive",
    "TRADINGAGENTS_DEBATE_CONSENSUS_THRESH": "debate_consensus_thresh",
    "TRADINGAGENTS_DEBATE_SCORING_WEIGHTS": "debate_scoring_weights",
    "TRADINGAGENTS_DEBATE_ABSTAIN_ALLOWED": "debate_abstain_allowed",
    "TRADINGAGENTS_DEBATE_FAST_ABORT": "debate_fast_abort",
    "TRADINGAGENTS_DEBATE_REGEN_MAX": "debate_regen_max",
    "TRADINGAGENTS_DEBATE_DIVERGENCE_CAP_ROUNDS": "debate_divergence_cap_rounds",
    "TRADINGAGENTS_DEBATE_REWEIGHT_TO_BASELINE": "debate_reweight_to_baseline",
    "TRADINGAGENTS_DEBATE_ENTRENCH_THRESH": "debate_entrench_thresh",
    "TRADINGAGENTS_DEBATE_DIVERGENCE_MIN": "debate_divergence_min",
    "TRADINGAGENTS_DEBATE_BASELINE_FALLBACK": "debate_baseline_fallback",
    "TRADINGAGENTS_DEBATE_REQUIRE_CAPABILITY_MATRIX": "debate_require_capability_matrix",
    "TRADINGAGENTS_CHECKPOINT_ENABLED": "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER": "benchmark_ticker",
    "TRADINGAGENTS_TEMPERATURE": "temperature",
    "TRADINGAGENTS_LLM_MAX_RETRIES": "llm_max_retries",
    "TRADINGAGENTS_FINNHUB_API_KEY": "finnhub_api_key",
    "TRADINGAGENTS_FMP_API_KEY": "fmp_api_key",
    "TRADINGAGENTS_EODHD_API_KEY": "eodhd_api_key",
    "TRADINGAGENTS_MASSIVE_API_KEY": "massive_api_key",
    "TIINGO_API_KEY": "tiingo_api_key",
    "TWELVEDATA_API_KEY": "twelve_data_api_key",
    "STOCKDATA_API_KEY": "stockdata_api_key",
    "NEWSAPI_API_KEY": "newsapi_api_key",
    "BENZINGA_API_KEY": "benzinga_api_key",
    "TRADINGAGENTS_ENABLE_MASSIVE_FLAT": "enable_massive_flat",
    "TRADINGAGENTS_MASSIVE_FLAT_DIR": "massive_flat_dir",
    "TRADINGAGENTS_ALPACA_API_KEY_ID": "alpaca_api_key_id",
    "TRADINGAGENTS_ALPACA_API_SECRET": "alpaca_api_secret",
    "TRADINGAGENTS_ENABLE_ALPACA": "enable_alpaca",
    # Moomoo OpenAPI: connection + headless autostart of the local OpenD gateway.
    # Credentials are never stored here — OpenD holds the logged-in session.
    # ``moomoo_account`` is only the moomoo ID used with ``-login_by_remember=1``
    # on autostart (requires a one-time "remember password" login in OpenD).
    "TRADINGAGENTS_MOOMOO_HOST": "moomoo_host",
    "TRADINGAGENTS_MOOMOO_PORT": "moomoo_port",
    "TRADINGAGENTS_MOOMOO_ACCOUNT": "moomoo_account",
    "TRADINGAGENTS_MOOMOO_AUTOSTART": "moomoo_autostart",
    "TRADINGAGENTS_MOOMOO_OPEND_PATH": "moomoo_opend_path",
    # Strategy overlays + reflection (Phase wiring) - settable via .env.
    "TRADINGAGENTS_ENABLE_STRATEGY_OVERLAYS": "enable_strategy_overlays",
    "TRADINGAGENTS_ENABLE_REFLECTION": "enable_reflection",
    "TRADINGAGENTS_ENABLE_SENTIMENT": "enable_sentiment",
    "TRADINGAGENTS_ENABLE_ORDERFLOW": "enable_orderflow",
    "TRADINGAGENTS_ENABLE_POSITION_CONTRACT": "enable_position_contract",
    "TRADINGAGENTS_ENABLE_CALIBRATION": "enable_calibration",
    "TRADINGAGENTS_ENABLE_AGREEMENT": "enable_agreement",
    "TRADINGAGENTS_ENABLE_COMPOSITE_RANK": "enable_composite_rank",
    "TRADINGAGENTS_ENABLE_FACTOR_PROFILE": "enable_factor_profile",
    "TRADINGAGENTS_ENABLE_TOPK_DROP": "enable_topk_drop",
    "TRADINGAGENTS_ENABLE_ENHANCED_INDEX": "enable_enhanced_index",
    "TRADINGAGENTS_BACKTEST_LIMIT_THRESHOLD": "backtest_limit_threshold",
    "TRADINGAGENTS_BACKTEST_VOLUME_PARTICIPATION": "backtest_volume_participation",
    "TRADINGAGENTS_BACKTEST_DEAL_PRICE": "backtest_deal_price",
    "TRADINGAGENTS_ENABLE_PIT_REGISTRY": "enable_pit_registry",
    "TRADINGAGENTS_ENABLE_FACTOR_MODEL": "enable_factor_model",
    "TRADINGAGENTS_ENABLE_DECISION_GUARDRAIL": "enable_decision_guardrail",
    "TRADINGAGENTS_ENABLE_FACTOR_PROPOSAL_LOOP": "enable_factor_proposal_loop",
    "TRADINGAGENTS_ENABLE_TUNER": "enable_tuner",
    "TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE": "enable_independent_vote",
    "TRADINGAGENTS_ENABLE_SENTIMENT_FACTOR": "enable_sentiment_factor",
    "TRADINGAGENTS_SENTIMENT_FACTOR_MIN_IC": "sentiment_factor_min_ic",
    "TRADINGAGENTS_SENTIMENT_FACTOR_MAX_SCALE": "sentiment_factor_max_scale",
    "TRADINGAGENTS_SENTIMENT_FACTOR_MIN_SCALE": "sentiment_factor_min_scale",
    "TRADINGAGENTS_VOLATILITY_ESTIMATOR": "volatility_estimator",
    "TRADINGAGENTS_ENABLE_EXITS": "enable_exits",
    "TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT": "enable_computed_context",
    "TRADINGAGENTS_ENABLE_RISK_GOVERNOR": "enable_risk_governor",
    "TRADINGAGENTS_ENABLE_DECISION_AUDIT": "enable_decision_audit",
    "TRADINGAGENTS_VALUE_DIP_REQUIRE_CATALYST": "value_dip_require_catalyst",
    "TRADINGAGENTS_VALUE_DIP_REGIME_GATE": "value_dip_regime_gate",
    "TRADINGAGENTS_VALUE_DIP_REGIME_VOL_CAP": "value_dip_regime_vol_cap",
    "TRADINGAGENTS_VALUE_DIP_REGIME_DOWNTREND_BAND": "value_dip_regime_downtrend_band",
    "TRADINGAGENTS_VALUE_DIP_REGIME_HALVE": "value_dip_regime_halve",
    "TRADINGAGENTS_RISK_DAILY_LOSS_BUDGET_PCT": "risk_daily_loss_budget_pct",
    "TRADINGAGENTS_RISK_HWM_SOFT_PCT": "risk_hwm_soft_pct",
    "TRADINGAGENTS_RISK_HWM_HARD_PCT": "risk_hwm_hard_pct",
    "TRADINGAGENTS_BREAKEVEN_TRIGGER": "breakeven_trigger",
    "TRADINGAGENTS_STOP_NEVER_WIDEN": "stop_never_widen",
    "TRADINGAGENTS_MIN_HOLDING_DAYS": "min_holding_days",
    "TRADINGAGENTS_MAX_TRADES_PER_PERIOD": "max_trades_per_period",
    "TRADINGAGENTS_SLEEVE_TAG_ENABLED": "sleeve_tag_enabled",
    "TRADINGAGENTS_DRIFT_THRESHOLD": "drift_threshold",
    "TRADINGAGENTS_ENABLE_PREOPEN_RVOL": "enable_preopen_rvol",
    "TRADINGAGENTS_PREOPEN_RVOL_INSTITUTIONAL_X": "preopen_rvol_institutional_x",
    "TRADINGAGENTS_PSR_BENCHMARK_SHARPE": "psr_benchmark_sharpe",
    "TRADINGAGENTS_ROLLING_WINDOW": "rolling_window",
    "TRADINGAGENTS_DOWNSIDE_MAR": "downside_mar",
    "TRADINGAGENTS_TRAILING_STOP_PCT": "trailing_stop_pct",
    "TRADINGAGENTS_ENABLE_TRAILING_EXIT": "enable_trailing_exit",
    "TRADINGAGENTS_RISK_PARITY_ENABLED": "risk_parity_enabled",
    "TRADINGAGENTS_RISK_MANAGER_DRAWDOWN_PCT": "risk_manager_drawdown_pct",
    "TRADINGAGENTS_ENABLE_RISK_MANAGER": "enable_risk_manager",
    "TRADINGAGENTS_VOLUME_SHARE_VOL_LIMIT": "volume_share_vol_limit",
    "TRADINGAGENTS_VOLUME_SHARE_PRICE_IMPACT": "volume_share_price_impact",

    "TRADINGAGENTS_ENABLE_EVENTS": "enable_events",
    # B1 scheduled-catalyst overlay tuning (on by default via enable_events).
    "TRADINGAGENTS_CATALYST_WINDOW_DAYS": "catalyst_window_days",
    "TRADINGAGENTS_CATALYST_BASELINE_MOVE": "catalyst_baseline_move",
    "TRADINGAGENTS_CATALYST_MACRO_WINDOW_DAYS": "catalyst_macro_window_days",
    "TRADINGAGENTS_CATALYST_MACRO_SCALE": "catalyst_macro_scale",
    "TRADINGAGENTS_CATALYST_FED_WINDOW_DAYS": "catalyst_fed_window_days",
    "TRADINGAGENTS_CATALYST_FED_SCALE": "catalyst_fed_scale",
    "TRADINGAGENTS_CATALYST_MISS_SCALE": "catalyst_miss_scale",
    "TRADINGAGENTS_CATALYST_SCALE_FLOOR": "catalyst_scale_floor",
    "TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS": "catalyst_hard_block_days",
    "TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT": "risk_max_drawdown_pct",
    "TRADINGAGENTS_RISK_DAILY_CVAR_BUDGET_PCT": "risk_daily_cvar_budget_pct",
    "TRADINGAGENTS_RISK_BASKET_TICKERS": "risk_basket_tickers",
    "TRADINGAGENTS_RISK_BASKET_WEIGHTS": "risk_basket_weights",
    "TRADINGAGENTS_HOLDINGS_TICKERS": "holdings_tickers",
    "TRADINGAGENTS_HOLDINGS_WEIGHTS": "holdings_weights",
    "TRADINGAGENTS_MOOMOO_MAX_CONNECTIONS": "moomoo_max_connections",
    "TRADINGAGENTS_MOOMOO_CALL_TIMEOUT": "moomoo_call_timeout",
    "TRADINGAGENTS_RISK_COMPACT_REPORT": "risk_compact_report",
    # Provider-specific reasoning/thinking knobs (None = each provider's own
    # default). Settable here for non-interactive runs; the CLI also offers an
    # interactive choice, which is skipped when the matching var is set.
    "TRADINGAGENTS_GOOGLE_THINKING_LEVEL": "google_thinking_level",
    "TRADINGAGENTS_OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "TRADINGAGENTS_ANTHROPIC_EFFORT": "anthropic_effort",
    # Opt-in analyst parallelism: >1 runs the analyst teams concurrently
    # (each in its own thread with isolated messages). Multiplies LLM/data load.
    "TRADINGAGENTS_ANALYST_CONCURRENCY": "analyst_concurrency",
    # OpenRouter provider routing: comma-separated provider slugs to always skip
    # (e.g. slow/unreliable endpoints). Sent as provider.ignore in the request
    # body via extra_body. Empty = no restriction.
    "TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS": "openrouter_ignore_providers",
    # Per-role max output tokens (cap; most-information-but-not-overflow).
    # quick/global is applied to analysts + debaters + trader; deep to RM/PM.
    "TRADINGAGENTS_MAX_OUTPUT_TOKENS": "max_output_tokens",
    "TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK": "max_output_tokens_quick",
    "TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP": "max_output_tokens_deep",
    # Value Dip + Swing hybrid (Strategies/Value_Dip_swing*.md): gate for the
    # screener --scan value-dip mode; the analyst @tools stay bound regardless.
    "TRADINGAGENTS_ENABLE_VALUE_DIP": "enable_value_dip",
    # Tranche-scaling risk fold (Value_Dip_swing_Continue.md): frozen config
    # drives the worst-case tranche plan the governor sizes/throttles against.
    "TRADINGAGENTS_ENABLE_TRANCHE_RISK": "enable_tranche_risk",
    "TRADINGAGENTS_TRANCHE_WEIGHTS": "tranche_weights",
    "TRADINGAGENTS_TRANCHE_STOP_MULT": "tranche_stop_mult",
    "TRADINGAGENTS_TRANCHE_RISK_PCT": "tranche_risk_pct",
    "TRADINGAGENTS_TRANCHE_ACCOUNT": "tranche_account",
    # Liquidity / ownership gate (Strategies/risk2.md): when on, the risk
    # governor REJECTs ILLIQUID names and WARNs on CAUTION ones (Amihud ILLIQ,
    # float turnover, days-to-absorb, IWF, HHI). Off by default - preserves
    # current behavior.
    "TRADINGAGENTS_ENABLE_LIQUIDITY_GATE": "enable_liquidity_gate",
    # Pre-market review (docs/pre_market_review.md): opt-in gate for the
    # in-batch same-night catalyst/quality re-check (choice (a)).
    "TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW": "enable_pre_market_review",
    # Correlation-aware allocation (Strategies/industry_practice_suggestions.md
    # item 1): when on, the allocation plan down-weights names whose average
    # pairwise correlation with the rest of the book exceeds the threshold.
    "TRADINGAGENTS_ENABLE_CORRELATION_PENALTY": "enable_correlation_penalty",
    "TRADINGAGENTS_CORRELATION_THRESHOLD": "correlation_threshold",
    "TRADINGAGENTS_CORRELATION_PENALTY_FRAC": "correlation_penalty_frac",
    # OpenBB Phase-3 free-tier data surfaces (off by default; opt-in via env).
    "TRADINGAGENTS_ENABLE_OPTIONS_SURFACE": "enable_options_surface",
    "TRADINGAGENTS_ENABLE_RISK_FREE_CURVE": "enable_risk_free_curve",
    "TRADINGAGENTS_ENABLE_SCREENER": "enable_screener",
    "TRADINGAGENTS_ENABLE_MARKET_MOVERS": "enable_market_movers",
}


_BOOL_TRUE = ("true", "1", "yes", "on")
_BOOL_FALSE = ("false", "0", "no", "off")


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value.

    Invalid values raise ``ValueError`` rather than silently falling back to a
    default — a misspelled boolean (e.g. ``treu``) or non-numeric int should fail
    loudly at startup, not quietly misconfigure an unattended run.
    """
    if isinstance(reference, bool):
        normalized = value.strip().lower()
        if normalized in _BOOL_TRUE:
            return True
        if normalized in _BOOL_FALSE:
            return False
        raise ValueError(
            f"expected a boolean ({'/'.join(_BOOL_TRUE + _BOOL_FALSE)}), got {value!r}"
        )
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    if isinstance(reference, list):
        # Comma-separated list, e.g. "SPY,QQQ,AAPL" -> ["SPY", "QQQ", "AAPL"].
        items = [item.strip() for item in value.split(",") if item.strip()]
        # Coerce each element to the existing default's element type so a
        # numeric list (e.g. TRADINGAGENTS_TRANCHE_WEIGHTS=0.3,0.3,0.4) lands
        # as floats, not strings. Previously this returned raw strings, which
        # made value_dip.tranche_plan's sum(weights) raise and silently disabled
        # the tranche risk fold precisely for .env-configured runs.
        if items and reference and not isinstance(reference[0], bool):
            elem_type = type(reference[0])
            if elem_type in (int, float):
                try:
                    return [elem_type(item) for item in items]
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"expected a comma-separated list of numbers, got {value!r}"
                    ) from exc
        return items
    if isinstance(reference, dict):
        # Accept either JSON ("{\"SPY\": 0.4}") or comma-separated key=value
        # pairs ("SPY=0.4,QQQ=0.6").
        import json

        saw_pairs = "=" in value or ("=" not in value and "{" not in value)
        if not saw_pairs:
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"expected a JSON object, got {value!r}") from exc
        out = {}
        for part in value.split(","):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                out[k.strip()] = float(v.strip())
            elif part:
                raise ValueError(f"expected key=value pairs or JSON, got {value!r}")
        return out
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        try:
            config[key] = _coerce(raw, config.get(key))
        except ValueError as exc:
            raise ValueError(f"Invalid value for {env_var}: {exc}") from exc
    return config


DEFAULT_CONFIG = _apply_env_overrides(
    {
        "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "results_dir": os.getenv(
            "TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")
        ),
        "data_cache_dir": os.getenv(
            "TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")
        ),
        "memory_log_path": os.getenv(
            "TRADINGAGENTS_MEMORY_LOG_PATH",
            os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md"),
        ),
        # Optional cap on the number of resolved memory log entries. When set,
        # the oldest resolved entries are pruned once this limit is exceeded.
        # Pending entries are never pruned. None disables rotation entirely.
        "memory_log_max_entries": None,
        # LLM settings
        "llm_provider": "openai",
        "deep_think_llm": "gpt-5.5",
        "quick_think_llm": "gpt-5.4-mini",
        # When None, each provider's client falls back to its own default endpoint
        # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
        # The CLI overrides this per provider when the user picks one. Keeping a
        # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
        # being forwarded to Gemini, producing malformed request URLs).
        "backend_url": None,
        # OpenRouter provider routing: provider slugs to always skip (slow /
        # unreliable endpoints). Sent as provider.ignore via extra_body. Empty
        # list = downstream of OpenRouter's own defaults.
        "openrouter_ignore_providers": [],
        # Per-role max output tokens (hard ceiling via max_tokens when the
        # provider accepts it). Basis: measured max outputs in this repo
        # (analysts ~5k, RM 1.9k, trader .7k, PM 1.4k) + ~20% headroom, well
        # under the formula's 1,310,720 - input ceiling for these inputs.
        # quick/global = analysts + debaters + trader (8000 - raised from 6000
        # after 2026-08-27 WDC reports truncated mid-sentence at the 6000 cap),
        # deep = RM + PM (2500).
        "max_output_tokens": 8000,
        "max_output_tokens_quick": 8000,
        "max_output_tokens_deep": 2500,
        # Provider-specific thinking configuration
        "google_thinking_level": None,  # "high", "minimal", etc.
        "openai_reasoning_effort": None,  # "medium", "high", "low"
        "anthropic_effort": None,  # "high", "medium", "low"
        # Sampling temperature, forwarded to every provider when set. None leaves
        # each provider at its own default. Lower values reduce run-to-run
        # variation on models that honor it; reasoning models largely ignore it
        # and no setting makes LLM output bit-identical across runs (see README).
        "temperature": None,
        # SDK retry budget forwarded to every provider chat client. None leaves each
        # provider/SDK at its own default (usually 2). Raise it to ride out bursty
        # 429 throttling on rate-limited deployments instead of aborting a run (#1091).
        "llm_max_retries": None,
        # Checkpoint/resume: when True, LangGraph saves state after each node
        # so a crashed run can resume from the last successful step.
        "checkpoint_enabled": False,
        # Output language for analyst reports and final decision
        # Internal agent debate stays in English for reasoning quality
        "output_language": "English",
        # Debate and discussion settings
        # ``research_depth`` is the single depth knob (direction.md item 1):
        # the CLI selection OR TRADINGAGENTS_RESEARCH_DEPTH drives BOTH the
        # research (max_debate_rounds, structured path) and the risk
        # (max_risk_discuss_rounds) round counts to the SAME level.
        "research_depth": 1,
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        # Structured multi-agent debate (design docs/design_multi_agent_debate.md,
        # research->implementation). All keys default OFF/empty so the current
        # one-shot bull/bear/RM chain is bit-identical when unused. When
        # ``enable_debate`` is on, the research debate runs as an FSM-ish
        # subgraph: structured debater turns (DebaterTurnPayload) -> L1
        # deterministic severity triage (classify_severity) -> blind
        # order-rotated L2 judge (L2JudgeDimensionedRubric) -> termination by
        # plateau/consensus/hard cap. Rejected/hard-breached turns fall back
        # to the pre-debate independent stances (baseline risk view).
        "enable_debate": False,
        "debate_bull_model": "",   # "family:id" for bull; fallback quick
        "debate_bear_model": "",   # "family:id" for bear; fallback quick
        "debate_judge_model": "",  # "family:id" for judge; fallback deep; family should differ from both debaters
        "debate_neutral_model": "",  # "family:id" for the neutral RISK debater; fallback quick
        "debate_judge_ensemble": 1,
        "debate_max_rounds": 5,    # matches DebaterTurnPayload.round_index (1..5)
        # Output budget for debate roles. A payload needs ~500-1500 visible
        # tokens; the schema now bounds the claim/risk lists (max_length=25),
        # so rambling to 8000 is structurally impossible. A THINKING model
        # (deepseek-v4) counts its hidden reasoning inside this budget — 2500
        # truncated mid-JSON -> degraded turns. 4000 leaves reasoning headroom
        # while the list bounds still cap the payload.
        "debate_max_output_tokens": 4000,
        # Sampling temperature for debate roles (low = less formatting drift;
        # 0.1 recommended, None = provider default). See direction.md /
        # deepseek JSON-enforcement notes.
        "debate_temperature": 0.1,
        # DeepSeek native JSON mode on the DEBATE path only (response_format
        # json_object): server-side valid-JSON constraint. Schema conformance
        # still Pydantic-checked. Only applies when the provider supports
        # json_mode (deepseek/openai-compatible); no-op routing wars.
        "debate_json_mode": True,
        "debate_min_gain": 0.05,
        "debate_stop_consecutive": 2,
        "debate_consensus_thresh": 0.85,
        "debate_scoring_weights": {"evidence": 0.6, "novelty": 0.25, "constraint": 0.15},
        "debate_abstain_allowed": True,
        "debate_fast_abort": True,          # R1: hard-fail short-circuits / regenerates
        "debate_regen_max": 2,              # R1': single-role regeneration budget (2: deepseek often lands the JSON on a 2nd attempt)
        "debate_divergence_cap_rounds": 1,  # R2: artificial-consensus threshold (rounds)
        "debate_reweight_to_baseline": 0.5, # R2': base alpha toward baseline on alert
        "debate_entrench_thresh": 0.8,      # R2': I_entrench above -> entrenchment penalty
        "debate_divergence_min": 0.15,      # R2': |bull-bear score| below -> artificial consensus
        "debate_baseline_fallback": True,   # R1': HARD_BREACH/exhausted regen -> baseline (never nothing)
        "debate_require_capability_matrix": False,  # R3: startup health-check gate
        # Analyst-team execution: 1 = sequential (default); >1 = concurrent
        # threads (opt-in — multiplies LLM/provider load and free-tier quota burn).
        "analyst_concurrency": 1,
        # News / data fetching parameters
        # Increase for longer lookback strategies or to broaden macro coverage;
        # decrease to reduce token usage in agent prompts.
        "news_article_limit": 20,  # max articles per ticker (ticker-news)
        "global_news_article_limit": 10,  # max articles for global/macro news
        "global_news_lookback_days": 7,  # macro news lookback window
        # Search queries used by get_global_news for macro headlines. Extend or
        # replace to broaden geographic / sector coverage.
        "global_news_queries": [
            "Federal Reserve interest rates inflation",
            "S&P 500 earnings GDP economic outlook",
            "geopolitical risk trade war sanctions",
            "ECB Bank of England BOJ central bank policy",
            "oil commodities supply chain energy",
        ],
        # Data vendor configuration
        # Category-level configuration (default for all tools in category).
        # The configured value is the exact vendor chain — requests are NOT silently
        # routed to vendors you didn't choose. For ordered fallback, list several,
        # e.g. "yfinance,alpha_vantage". "default" uses all available vendors.
        "data_vendors": {
            # EODHD is the primary OHLCV source (100k calls/day @ 1000/min on
            # the EOD plan); moomoo/yfinance stay as fallbacks. EODHD cannot
            # serve fundamentals/technicals/intraday/options on the EOD plan,
            # so those chains keep moomoo/yfinance first.
            "core_stock_apis": "eodhd,moomoo,yfinance,tiingo,twelve_data,stockdata",  # Options: ... , tiingo, twelve_data, stockdata
            "technical_indicators": "moomoo,yfinance,alpha_vantage",  # Options: alpha_vantage, yfinance, moomoo
            "fundamental_data": "moomoo,yfinance,tiingo,alpha_vantage",  # Options: alpha_vantage, yfinance, moomoo, tiingo
            "news_data": "eodhd,moomoo,yfinance,alpha_vantage,stockdata,newsapi",  # Options: + newsapi; set "...,gdelt" to use GDELT (keyless, may be network-flaky)
            # Daily news-sentiment series (-1..1) + 7d SMA. EODHD /sentiments
            # (primary, EOD plan entitled); AV NEWS_SENTIMENT (25 req/day tail);
            # GDELT native tone (keyless, flaky, ~3-month window) last.
            "news_sentiment": "eodhd,alpha_vantage,gdelt",
            "macro_data": "fred,moomoo",  # Options: fred (needs FRED_API_KEY), moomoo
            "prediction_markets": "polymarket,moomoo",  # Options: polymarket (keyless), moomoo (SG/MY event contracts)
            "analyst_ratings": "moomoo,finnhub,yfinance",  # Options: finnhub (needs key), moomoo, yfinance (keyless)
            "earnings_calendar": "moomoo,finnhub,yfinance",  # Options: finnhub (needs key), moomoo, yfinance (keyless)
            "options_data": "moomoo,yfinance",  # Options: yfinance (free, no key), moomoo
            "sec_filings": "sec_edgar",  # Options: sec_edgar (free, no key)
            "short_interest": "moomoo,yfinance",  # Options: yfinance (free, no key), moomoo
            "exchange_symbols": "eodhd",  # Options: eodhd (EOD plan)
            # moomoo-only enrichment (Tier 1/2). Optional — failures degrade to
            # a DATA_UNAVAILABLE sentinel and the run proceeds without the signal.
            "capital_flow": "moomoo",
            "smart_money": "moomoo",
            "economic_calendar": "moomoo",
            "fed_watch": "moomoo",
            "market_breadth": "moomoo",
            "revenue_breakdown": "moomoo",
            "corporate_actions": "eodhd,moomoo",
            "earnings_catalyst": "moomoo",
            "institution_data": "moomoo,yfinance",  # Options: moomoo, yfinance (keyless holders)
            "earnings_surprise": "moomoo",
            "expected_move": "moomoo",
            # OpenBB Phase-3 free-tier data surfaces (all keyless where possible,
            # all optional, and each gated by its own enable_* flag, default off).
            "options_surface": "cboe",  # CBOE delayed options quotes (no key)
            "risk_free_curve": "federal_reserve",  # NY Fed SOFR + Treasury CSV (no key)
            "equity_screener": "yfinance",  # yfinance screener (free)
            "market_movers": "yfinance",  # yfinance discovery/movers (free)
        },
        # Tool-level configuration (takes precedence over category-level)
        "tool_vendors": {
            # Example: "get_stock_data": "alpha_vantage",  # Override category default
        },
        "finnhub_api_key": None,
        "fmp_api_key": None,  # FMP optional enrichment (fmp.py)
        "eodhd_api_key": None,  # EODHD daily OHLCV (eodhd.py)
        "massive_api_key": None,  # Massive.com US data (massive.py)
        "tiingo_api_key": None,  # Tiingo market data (tiingo.py)
        "twelve_data_api_key": None,  # Twelve Data (twelve_data.py): 800 credits/day free
        "stockdata_api_key": None,  # StockData.org (stockdata.py): 100 requests/day free
        "newsapi_api_key": None,  # NewsAPI.org (newsapi.py): free Developer 100 req/day
        "benzinga_api_key": None,  # Benzinga (benzinga.py): free Basic Financial News tier
        # Optional path to a Massive Flat-File day-aggregates CSV. When set, the
        # value-screener's OHLCV fetch checks it first (bulk history for ATR /
        # scan bases) before falling back to the per-ticker vendor chain. This
        # is the plan-aware Flat-File seam (see docs/massive_integration.md).
        # Massive Flat-File (day-aggregates) bulk OHLCV import for the
        # value-screener's ATR / ATR-pct / scan bases. OFF by default: you must
        # (1) put a downloaded Massive day-aggregates CSV in `massive_flat_dir`
        # and (2) set enable_massive_flat=true. When on, the screener reads a
        # ticker's series from the folder's CSV (bulk) before the per-ticker
        # vendor chain; only used when it resolves >=15 rows. Stocks Starter+.
        "enable_massive_flat": False,
        "massive_flat_dir": "data/massive_flat",
        "alpaca_api_key_id": None,  # Alpaca market-data analyst (alpaca.py)
        "alpaca_api_secret": None,  # Alpaca market-data analyst (alpaca.py)
        "enable_alpaca": False,  # Alpaca market-data (screener + analyst tool)
        # Moomoo OpenAPI (local OpenD gateway, quote-only).
        "moomoo_host": "127.0.0.1",
        "moomoo_port": 11111,
        "moomoo_account": None,  # moomoo ID for headless autostart (not a password)
        "moomoo_autostart": False,  # launch OpenD with -login_by_remember=1 when unreachable
        "moomoo_opend_path": None,  # explicit path to the OpenD executable
        # Per-call wall-clock timeout (seconds) for moomoo SDK calls. The SDK's
        # own ReqInfo.wait() allows 20s per call; a degraded gateway can burn
        # 20s per call across hundreds of calls (the value screener's gating
        # pass makes ~7 calls/symbol), which is how a web job hits its
        # subprocess budget. 5s keeps a degraded gateway from stalling a run.
        "moomoo_call_timeout": 5.0,
        # Vendor-result cache (operational): re-serve successful vendor fetches
        # within a TTL instead of re-hitting free-tier APIs on every run.
        # Researched strategies (enhancement_plan.md - Phase 0..6). All off by
        # default; each phase is a pure module under tradingagents/strategies/
        # with offline unit tests (tests/test_strategies_*).
        "evaluate_cost_bps": 10,  # Phase 0: per-trade cost in basis points
        "enable_regime": False,  # RESERVED (not yet wired): regime gate (vol/trend/HMM)
        "position_sizing": "kelly",  # Phase 2: kelly | vol_target | flat
        "target_vol": 0.15,  # Phase 2: annualized vol target
        "enable_factors": False,  # RESERVED (not yet wired): value+momentum composite
        "enable_events": True,  # Phase 4: PEAD / catalyst sizing (B1, on by default)
        # B1 scheduled-catalyst overlay tuning (used when enable_events is on).
        "catalyst_window_days": 5,  # earnings within N days -> scale down
        "catalyst_baseline_move": 0.02,  # baseline expected move for the penalty
        "catalyst_macro_window_days": 3,  # HIGH macro events within N days
        "catalyst_macro_scale": 0.6,  # multiplier per imminent HIGH macro event
        "catalyst_fed_window_days": 10,  # FOMC within N days
        "catalyst_fed_scale": 0.6,  # multiplier when FOMC is imminent
        "catalyst_miss_scale": 0.5,  # last earnings miss during earnings window
        "catalyst_scale_floor": 0.25,  # never scale below this via catalysts
        "catalyst_hard_block_days": 0,  # >0: REJECT new risk within N calendar
        #   days of a scheduled earnings print (framework Phase-4 hard rule)
        "enable_reflection": True,  # Phase 5: post-trade analyst critique
        # News-sentiment factor overlay (News_Sentiment.md): position scale
        # x 1 ± max_scale ONLY when the name's measured rank IC >= min_ic
        # (else neutral 1.0, never blocks). Volatility estimator for the
        # overlay sizing/regime path: close (default) | ewma | garch
        # (close-series only); Parkinson / Garman-Klass need OHLC and are
        # exposed as analyst tools instead.
        "enable_sentiment_factor": False,
        "sentiment_factor_min_ic": 0.02,
        "sentiment_factor_max_scale": 0.2,
        "sentiment_factor_min_scale": 0.5,
        "volatility_estimator": "close",
        # Decision hardening (decision_hardening_spec.md): compute, don’t narrate.
        "enable_position_contract": False,  # G1: deterministic size/stop
        "risk_per_trade": 0.01,  # risk budget per trade (G1)
        "max_position_pct": 0.30,  # portfolio cap (G1)
        "atr_mult": 2.0,  # ATR stop multiple (G1)
        "position_odds": 1.0,  # win/loss payoff (G1)
        "kelly_fraction": 0.25,  # quarter-Kelly (G1)
        "enable_calibration": False,  # G2: bucket win-rates from ledger
        "calibration_min_n": 5,  # RESERVED (not yet wired): min samples per bucket (G2)
        "enable_agreement": False,  # G3: computed consensus / agreement
        "enable_threshold_gate": False,  # RESERVED (not yet wired): G5 PBO tuning gate
        "enable_independent_vote": False,  # Option-A hybrid: pre-debate independent stances feed G3/consensus
        # Institutional workflow (design_institutional_value_dip_workflow.md).
        # All advisory rows are computed + injected into the decision agents
        # (Trader / PM / risk debators); nothing gates by default.
        "value_dip_require_catalyst": False,  # A2: re-rating evidence required
        "value_dip_regime_gate": False,  # A1: hard-gate on regime (advisory by default)
        "value_dip_regime_vol_cap": 0.8,  # A1: vol_pct above this blocks MR entries (opt-in)
        "value_dip_regime_downtrend_band": 0.08,  # A1: price below 200-SMA by this -> knife guard
        "value_dip_regime_halve": False,  # A1: instead of block, size x0.5
        "risk_daily_loss_budget_pct": 0.03,  # B1: daily realized-loss cap -> de-risk
        "risk_hwm_soft_pct": 0.10,  # B1: drawdown-from-HWM soft tier (WARN)
        "risk_hwm_hard_pct": 0.20,  # B1: drawdown-from-HWM hard tier (REJECT new risk)
        "breakeven_trigger": "structure",  # B3: atr | r | structure (BE after confirmation)
        "stop_never_widen": True,  # B4: enforce unified stop never widened
        "min_holding_days": 5,  # C2: turnover guard
        "max_trades_per_period": 4,  # C2: weekly churn cap
        "sleeve_tag_enabled": True,  # D1: tag decisions with style sleeve
        "drift_threshold": 0.15,  # D2: alpha-decay win-rate drift trigger
        # P1/P2/P3: pre-open + execution-quality advisory rows (Alpaca free IEX).
        "enable_preopen_rvol": True,  # P1: pre-market RVOL vs 30d pre-open avg
        "preopen_rvol_institutional_x": 2.0,  # P1: RVOL threshold for institutional read
        "enable_preopen_depth": True,  # P2: live IEX quote-depth proxy (thin-book)
        # QuantLib + Lean enhancements (design_quantlib_lean_enhancements.md).
        # Read-only deterministic calculators; all advisory, default-off gates.
        "psr_benchmark_sharpe": 0.0,  # L3: PSR benchmark Sharpe for comparison
        "rolling_window": 132,  # L3: rolling-beta window (Lean default 132)
        "downside_mar": 0.0,  # L3: Sortino/downside minimum-return target (MAR)
        "trailing_stop_pct": 0.05,  # L4: peak-trailing stop (% from peak)
        "enable_trailing_exit": False,  # L4: emit peak-trail exit overrides
        "risk_parity_enabled": False,  # L2: use covariance risk-parity in alloc
        "risk_manager_drawdown_pct": 0.05,  # L1: two-pass exit-minus-% override
        "enable_risk_manager": False,  # L1: active position-exit override layer
        "volume_share_vol_limit": 0.1,  # L6: slippage participation cap
        "volume_share_price_impact": 0.025,  # L6: slippage impact coefficient

        # Value-style enhancements (value_style_gap_plan.md).
        "enable_computed_context": False,  # V5: computed numbers into debate snippets
        "enable_composite_rank": False,  # V2: composite (value+momentum) ranking
        "enable_exits": False,  # V4: ATR exits / rebalance hints
        # Qlib integration (design_qlib_integration.md): advisory calculators,
        # all default-off; the factor profile tool returns "unavailable" when
        # its flag is off (mirrors the OpenBB gated-tool convention).
        "enable_factor_profile": False,  # Q1: get_factor_profile tool + expression cache
        "enable_topk_drop": False,  # Q3: screener alloc block uses Topk-Drop
        "enable_enhanced_index": False,  # Q3: screener alloc block uses the convex enhanced-index
        "backtest_limit_threshold": 0.0,  # Q13: |day change| fraction for limit-up/down gate (0 = off)
        "backtest_volume_participation": 0.0,  # Q13: cap order % of day volume (0 = off; 0.2 recommended)
        "backtest_deal_price": "close",  # Q13: close | open | vwap, or "buy,sell" pair



        "enable_factor_model": False,  # Q5: advisory factor-model score (gated research artifact)
        "enable_decision_guardrail": False,  # DSA-1: post-decision downgrade-only stabilizer (advisory)
        "enable_factor_proposal_loop": False,  # Q11: LLM-proposed candidates, math decides (gated)
        "enable_tuner": False,  # Q19: hyperparam grid search front-end (gate decides)
        "breakeven_atr": 1.0,  # V4: stop-to-breakeven cushion (ATRs)
        "target_atr": 4.0,  # V4: profit target multiple
        "sector_cap_limit": 0.35,  # V3: max single-sector weight
        "max_name_weight": 0.25,  # V3: max single-name weight
        "max_book_names": 10,  # V3: minimum names for diversification
        # Risk governor (risk_management_plan.md): deterministic risk gate.
        "enable_risk_governor": False,
        "enable_decision_audit": False,  # item 6: PM claim-vs-computed audit note
        "risk_max_position_pct": 0.45,  # R0: book cap
        "risk_daily_cvar_budget_pct": 0.03,  # R0/R2: daily tail budget
        "risk_max_drawdown_pct": 0.10,  # R0/R2: realized drawdown stop
        "risk_stress_shock_pct_1": -10.0,  # RESERVED (not yet wired): R2 scenario shock 1 (%)
        "risk_stress_shock_pct_2": -30.0,  # RESERVED (not yet wired): R2 scenario shock 2 (%)
        # R2: true portfolio CVaR. When ``risk_basket_tickers`` is non-empty and
        # at least two of its names resolve aligned return series via the vendor
        # chain, the risk governor computes the daily tail budget from the
        # *weighted basket*'s historical CVaR (book_risk.portfolio_cvar) instead
        # of the single analyzed name's series. ``risk_basket_weights`` is an
        # optional per-name weight map ({ticker: weight}); missing/absent names
        # are equal-weighted when no weights are given. Falls back to the
        # single-name series when the basket cannot be resolved.
        "risk_basket_tickers": [],  # e.g. ["SPY", "QQQ", "AAPL"]
        "risk_basket_weights": {},  # e.g. {"SPY": 0.4, "QQQ": 0.6}
        # Option-B holdings read (PM advisory block). When set, these describe
        # the ACTUAL book for the decision agents ("you hold NVDA 10.4%, cash
        # remainder"); when empty the risk basket is used (Option A - the
        # basket IS the book). weights are fractions of the whole book incl.
        # cash; the < 1.0 remainder is the cash sleeve (never a ticker).
        "holdings_tickers": [],  # Option-B: actual-book tickers (else basket used)
        "holdings_weights": {},  # Option-B: actual-book weights (else basket used)
        "risk_audit_enabled": True,  # R4: risk_audit.jsonl
        # Moomoo connection guard (parallel batch): cap open gateway contexts
        "moomoo_max_connections": 25,  # far below OpenD's 128-connection limit
        "risk_compact_report": False,  # R1b: verdict-only 4_risk/ instead of chat transcripts
        "consensus_seeds": 1,  # RESERVED (not yet wired): LLM samples for consensus
        # Value Dip + Swing hybrid (Strategies/Value_Dip_swing*.md). On = the
        # screener's --scan value-dip mode runs; the deterministic analyst
        # @tools (get_bollinger_pct_b / get_tranche_plan / get_trade_expectancy /
        # get_fcf_yield / get_valuation_z_score / get_value_dip_setup) stay bound
        # to the market/fundamentals analyst tool loops regardless of the flag.
        "enable_value_dip": False,
        # Value Dip tranche-scaling risk fold (Strategies/Value_Dip_swing_Continue.md).
        # When enable_position_contract + enable_risk_governor are also on, the
        # risk governor sizes and throttles against the *worst-case tranche
        # plan* with config-frozen parameters (weights / stop multiple / risk
        # budget / account - never the LLM). Enforces BOTH the capital-at-risk
        # budget (sum of per-tranche losses at the hard stop) and the
        # peak-deployed-capital-at-scale-in per-trade cap (scale-in ties up
        # more capital near the lows than a single entry).
        "enable_tranche_risk": False,
        "tranche_weights": [0.3, 0.3, 0.4],
        "tranche_stop_mult": 1.5,
        "tranche_risk_pct": 0.015,
        "tranche_account": 100_000.0,
        # Correlation-aware allocation (Strategies/industry_practice_suggestions.md
        # item 1). When on, allocation_block / get_allocation down-weight names
        # whose average pairwise correlation with the rest of the book exceeds
        # ``correlation_threshold`` by ``correlation_penalty_frac`` before the
        # per-name/per-sector caps (risk-parity style concentration control).
        # Off by default - preserves current behavior; names without a
        # measurable return series are never penalized (no fabrication).
        "enable_correlation_penalty": False,
        "correlation_threshold": 0.6,
        "correlation_penalty_frac": 0.3,
        # Liquidity / ownership gate (Strategies/risk2.md). When on, the risk
        # governor REJECTs ILLIQUID names and WARNs on CAUTION ones using the
        # computed Amihud ILLIQ / float turnover / days-to-absorb / IWF / HHI.
        # Off by default - preserves current behavior.
        "enable_liquidity_gate": False,
        # Pre-market review (docs/pre_market_review.md, choice (a)): when on,
        # batch.py writes a same-night catalyst/quality re-check
        # (pre_market_review_<date>.md) next to each report. The pre-open gap /
        # re-anchor path stays the standalone scripts/pre_market_review.py.
        # OpenBB Phase-3 free-tier data surfaces. Each is keyless/free and
        # analysis-only; all default OFF. Flip an env override (e.g.
        # TRADINGAGENTS_ENABLE_OPTIONS_SURFACE=true) to let its @tool fetch
        # real data; when off the tool returns a clear DISABLED sentinel and
        # never fabricates.
        "enable_options_surface": False,
        "enable_risk_free_curve": False,
        "enable_screener": False,
        "enable_market_movers": False,
        "vendor_cache_enabled": True,
        "vendor_cache_ttl_seconds": 21600,  # 6 hours
        # Categories excluded from the cache because their content is genuinely
        # live and must not be frozen (news moves continuously).
        "vendor_cache_skip_categories": {"news_data"},
        # Benchmark for alpha calculation in the reflection layer.
        # ``benchmark_ticker`` (when set) overrides the suffix map for all
        # tickers; leave it None to use ``benchmark_map`` for auto-detection
        # based on the ticker's exchange suffix. SPY remains the US default
        # so the reflection label keeps reading "Alpha vs SPY" for US tickers
        # while non-US tickers get their regional index automatically.
        "benchmark_ticker": None,
        "benchmark_map": {
            ".NS": "^NSEI",  # NSE India (Nifty 50)
            ".BO": "^BSESN",  # BSE India (Sensex)
            ".T": "^N225",  # Tokyo (Nikkei 225)
            ".HK": "^HSI",  # Hong Kong (Hang Seng)
            ".L": "^FTSE",  # London (FTSE 100)
            ".TO": "^GSPTSE",  # Toronto (TSX Composite)
            ".AX": "^AXJO",  # Australia (ASX 200)
            ".SS": "000001.SS",  # Shanghai (SSE Composite)
            ".SZ": "399001.SZ",  # Shenzhen (SZSE Component)
            "": "SPY",  # default for US-listed tickers (no suffix)
        },
    }
)


def validate_config(config: dict) -> list[str]:
    """Range-check runtime config and return human-readable violations.

    The env overrides coerce `TRADINGAGENTS_*` to the default's *type*, but a
    well-typed value can still be nonsense (negative window, fraction > 1,
    tranche weights that do not sum to ~1), which silently skews every run.
    This collects all violations so they can be logged once at startup -
    advisory, never raised, missing keys are simply skipped (a caller may pass
    a config sub-slice). Mirrors NautilusTrader's ConfigErrorCollector pattern
    (collect every field violation instead of failing on the first).
    """
    violations: list[str] = []

    def frac(key: str, lo: float = 0.0, hi: float = 1.0) -> None:
        v = config.get(key)
        if v is None:
            return
        try:
            v = float(v)
        except (TypeError, ValueError):
            violations.append(f"{key} is not a number: {v!r}")
            return
        if not (lo <= v <= hi):
            violations.append(f"{key}={v} outside [{lo}, {hi}]")

    def positive(key: str, allow_zero: bool = False) -> None:
        v = config.get(key)
        if v is None:
            return
        try:
            v = float(v)
        except (TypeError, ValueError):
            violations.append(f"{key} is not a number: {v!r}")
            return
        if (not allow_zero and v <= 0) or (allow_zero and v < 0):
            violations.append(f"{key}={v} must be {'>= 0' if allow_zero else '> 0'}")

    # Fractions / scales / rates that must live in [0, 1].
    for key in (
        "kelly_fraction",
        "target_vol",
        "position_odds",
        "catalyst_scale_floor",
        "catalyst_baseline_move",
        "catalyst_macro_scale",
        "catalyst_fed_scale",
        "catalyst_miss_scale",
        "risk_daily_cvar_budget_pct",
        "risk_max_drawdown_pct",
        "risk_daily_loss_budget_pct",
        "risk_hwm_soft_pct",
        "risk_hwm_hard_pct",
        "risk_manager_drawdown_pct",
        "tranche_risk_pct",
        "correlation_threshold",
        "correlation_penalty_frac",
        "debate_min_gain",
        "debate_consensus_thresh",
        "debate_reweight_to_baseline",
        "debate_entrench_thresh",
        "debate_divergence_min",
    ):
        frac(key)

    # debate_scoring_weights: three weights summing to ~1, each in [0,1].
    dw = config.get("debate_scoring_weights")
    if dw is not None:
        if not isinstance(dw, dict):
            violations.append(f"debate_scoring_weights is not a dict: {dw!r}")
        else:
            vals = [v for v in dw.values() if v is not None]
            if vals and all(isinstance(v, (int, float)) for v in vals) and abs(sum(vals) - 1.0) > 1e-6:
                    violations.append(
                        f"debate_scoring_weights sum to {sum(vals):.4f}, expected ~1.0"
                    )
    # Non-negative numeric knobs (0 allowed where it means "off").
    for key in (
        "catalyst_window_days",
        "catalyst_macro_window_days",
        "catalyst_fed_window_days",
        "catalyst_hard_block_days",
        "rolling_window",
        "calibration_min_n",
        "min_holding_days",
        "max_trades_per_period",
        "tranche_stop_mult",
        "atr_mult",
        "target_atr",
        "debate_max_rounds",
        "debate_judge_ensemble",
        "debate_stop_consecutive",
        "debate_regen_max",
        "debate_divergence_cap_rounds",
    ):
        positive(key, allow_zero=True)
    # Monotonic HWM tiers: soft cannot exceed hard.
    soft = config.get("risk_hwm_soft_pct")
    hard = config.get("risk_hwm_hard_pct")
    if soft is not None and hard is not None:
        try:
            if float(soft) > float(hard):
                violations.append(
                    f"risk_hwm_soft_pct={soft} must be <= risk_hwm_hard_pct={hard}"
                )
        except (TypeError, ValueError):
            pass

    # Tranche weights: each in [0,1] and sum to ~1.
    tw = config.get("tranche_weights")
    if tw is not None:
        try:
            vals = list(tw)
        except TypeError:
            violations.append(f"tranche_weights is not a sequence: {tw!r}")
            vals = []
        if vals:
            all_num = True
            for i, v in enumerate(vals):
                try:
                    float(v)
                except (TypeError, ValueError):
                    all_num = False
                    violations.append(f"tranche_weights[{i}] is not a number: {v!r}")
            if all_num:
                total = sum(float(x) for x in vals)
                if abs(total - 1.0) > 1e-6:
                    violations.append(f"tranche_weights sum to {total:.4f}, expected ~1.0")

    return violations
