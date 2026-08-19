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
    "TRADINGAGENTS_CHECKPOINT_ENABLED": "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER": "benchmark_ticker",
    "TRADINGAGENTS_TEMPERATURE": "temperature",
    "TRADINGAGENTS_LLM_MAX_RETRIES": "llm_max_retries",
    "TRADINGAGENTS_FINNHUB_API_KEY": "finnhub_api_key",
    "TRADINGAGENTS_FMP_API_KEY": "fmp_api_key",
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
    "TRADINGAGENTS_ENABLE_ORDERFLOW": "enable_orderflow",
    "TRADINGAGENTS_ENABLE_POSITION_CONTRACT": "enable_position_contract",
    "TRADINGAGENTS_ENABLE_CALIBRATION": "enable_calibration",
    "TRADINGAGENTS_ENABLE_AGREEMENT": "enable_agreement",
    "TRADINGAGENTS_ENABLE_COMPOSITE_RANK": "enable_composite_rank",
    "TRADINGAGENTS_ENABLE_EXITS": "enable_exits",
    "TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT": "enable_computed_context",
    "TRADINGAGENTS_ENABLE_RISK_GOVERNOR": "enable_risk_governor",
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
    "TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT": "risk_max_drawdown_pct",
    "TRADINGAGENTS_RISK_DAILY_CVAR_BUDGET_PCT": "risk_daily_cvar_budget_pct",
    "TRADINGAGENTS_MOOMOO_MAX_CONNECTIONS": "moomoo_max_connections",
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
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "max_recur_limit": 100,
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
            "core_stock_apis": "moomoo,yfinance",  # Options: alpha_vantage, yfinance, moomoo
            "technical_indicators": "moomoo,yfinance",  # Options: alpha_vantage, yfinance, moomoo
            "fundamental_data": "moomoo,yfinance",  # Options: alpha_vantage, yfinance, moomoo
            "news_data": "moomoo,yfinance",  # Options: alpha_vantage, yfinance, finnhub, moomoo
            "macro_data": "fred,moomoo",  # Options: fred (needs FRED_API_KEY), moomoo
            "prediction_markets": "polymarket,moomoo",  # Options: polymarket (keyless), moomoo (SG/MY event contracts)
            "analyst_ratings": "moomoo,finnhub",  # Options: finnhub (needs key), moomoo
            "earnings_calendar": "moomoo,finnhub",  # Options: finnhub (needs key), moomoo
            "options_data": "moomoo,yfinance",  # Options: yfinance (free, no key), moomoo
            "sec_filings": "sec_edgar",  # Options: sec_edgar (free, no key)
            "short_interest": "moomoo,yfinance",  # Options: yfinance (free, no key), moomoo
            # moomoo-only enrichment (Tier 1/2). Optional — failures degrade to
            # a DATA_UNAVAILABLE sentinel and the run proceeds without the signal.
            "capital_flow": "moomoo",
            "smart_money": "moomoo",
            "economic_calendar": "moomoo",
            "fed_watch": "moomoo",
            "market_breadth": "moomoo",
            "revenue_breakdown": "moomoo",
            "corporate_actions": "moomoo",
            "earnings_catalyst": "moomoo",
            "institution_data": "moomoo",
            "earnings_surprise": "moomoo",
            "expected_move": "moomoo",
        },
        # Tool-level configuration (takes precedence over category-level)
        "tool_vendors": {
            # Example: "get_stock_data": "alpha_vantage",  # Override category default
        },
        "finnhub_api_key": None,
        "fmp_api_key": None,  # FMP optional enrichment (fmp.py)
        "alpaca_api_key_id": None,  # Alpaca market-data analyst (alpaca.py)
        "alpaca_api_secret": None,  # Alpaca market-data analyst (alpaca.py)
        "enable_alpaca": False,  # Alpaca market-data (screener + analyst tool)
        # Moomoo OpenAPI (local OpenD gateway, quote-only).
        "moomoo_host": "127.0.0.1",
        "moomoo_port": 11111,
        "moomoo_account": None,  # moomoo ID for headless autostart (not a password)
        "moomoo_autostart": False,  # launch OpenD with -login_by_remember=1 when unreachable
        "moomoo_opend_path": None,  # explicit path to the OpenD executable
        # Vendor-result cache (operational): re-serve successful vendor fetches
        # within a TTL instead of re-hitting free-tier APIs on every run.
        # Researched strategies (enhancement_plan.md - Phase 0..6). All off by
        # default; each phase is a pure module under tradingagents/strategies/
        # with offline unit tests (tests/test_strategies_*).
        "evaluate_cost_bps": 10,  # Phase 0: per-trade cost in basis points
        "enable_regime": False,  # Phase 1: regime gate (vol/trend/HMM)
        "position_sizing": "kelly",  # Phase 2: kelly | vol_target | flat
        "target_vol": 0.15,  # Phase 2: annualized vol target
        "enable_factors": False,  # Phase 3: value+momentum composite
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
        "enable_reflection": True,  # Phase 5: post-trade analyst critique
        "enable_sentiment": False,  # Phase 6: sentiment velocity
        "enable_strategy_overlays": True,  # graph overlay wiring (regime/sizing/context)
        "enable_orderflow": False,  # L1-L4: capital-flow signals + flow-scaled sizing
        "orderflow_distribution_threshold": 0.7,
        # Decision hardening (decision_hardening_spec.md): compute, don’t narrate.
        "enable_position_contract": False,  # G1: deterministic size/stop
        "risk_per_trade": 0.01,  # risk budget per trade (G1)
        "max_position_pct": 0.30,  # portfolio cap (G1)
        "atr_mult": 2.0,  # ATR stop multiple (G1)
        "position_odds": 1.0,  # win/loss payoff (G1)
        "kelly_fraction": 0.25,  # quarter-Kelly (G1)
        "enable_calibration": False,  # G2: bucket win-rates from ledger
        "calibration_min_n": 5,  # min samples per bucket (G2)
        "enable_agreement": False,  # G3: computed consensus / agreement
        "enable_threshold_gate": False,  # G5: require PBO-clean tuning
        # Value-style enhancements (value_style_gap_plan.md).
        "enable_computed_context": False,  # V5: computed numbers into debate snippets
        "enable_composite_rank": False,  # V2: composite (value+momentum) ranking
        "enable_exits": False,  # V4: ATR exits / rebalance hints
        "breakeven_atr": 1.0,  # V4: stop-to-breakeven cushion (ATRs)
        "target_atr": 4.0,  # V4: profit target multiple
        "sector_cap_limit": 0.35,  # V3: max single-sector weight
        "max_name_weight": 0.25,  # V3: max single-name weight
        "max_book_names": 10,  # V3: minimum names for diversification
        # Risk governor (risk_management_plan.md): deterministic risk gate.
        "enable_risk_governor": False,
        "risk_max_position_pct": 0.45,  # R0: book cap
        "risk_daily_cvar_budget_pct": 0.03,  # R0/R2: daily tail budget
        "risk_max_drawdown_pct": 0.10,  # R0/R2: realized drawdown stop
        "risk_stress_shock_pct_1": -10.0,  # R2: scenario shock 1 (%)
        "risk_stress_shock_pct_2": -30.0,  # R2: scenario shock 2 (%)
        "risk_audit_enabled": True,  # R4: risk_audit.jsonl
        # Moomoo connection guard (parallel batch): cap open gateway contexts
        "moomoo_max_connections": 25,  # far below OpenD's 128-connection limit
        "risk_compact_report": False,  # R1b: verdict-only 4_risk/ instead of chat transcripts
        "consensus_seeds": 1,  # Phase 6: LLM samples for consensus; >1 enables
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
