# TradingAgents/graph/trading_graph.py

import contextlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf
from langgraph.prebuilt import ToolNode

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_analyst_ratings,
    get_balance_sheet,
    get_capital_flow,
    get_cashflow,
    get_corporate_actions,
    get_dividends,
    get_earnings_calendar,
    get_earnings_catalyst,
    get_earnings_surprise_history,
    get_economic_calendar,
    get_expected_move,
    get_fed_watch,
    get_fundamentals,
    get_global_news,
    get_income_statement,
    get_indicators,
    get_insider_transactions,
    get_institution_holdings,
    get_ipos,
    get_macro_indicators,
    get_market_breadth,
    get_market_snapshot,
    get_massive_news,
    get_news,
    get_options_chain,
    get_prediction_markets,
    get_revenue_breakdown,
    get_sec_filings,
    get_short_interest,
    get_short_volume,
    get_smart_money,
    get_stock_data,
    get_top_movers,
    get_verified_market_snapshot,
    resolve_instrument_identity,
)

# Import the abstract tool methods from agent_utils
from tradingagents.agents.utils.alpaca_tools import get_market_snapshot_alpaca
from tradingagents.agents.utils.analysis_tools import (
    get_allocation,
    get_analyst_verdict,
    get_basic_financials,
    get_beat_miss_sizing,
    get_catalyst_scale,
    get_company_peers,
    get_composite_rank,
    get_credit_spread_read,
    get_dcf_valuation,
    get_earnings_event_read,
    get_earnings_quality,
    get_earnings_surprise,
    get_exit_check,
    get_form4_insider,
    get_insider_activity,
    get_margin_of_safety,
    get_momentum_detail,
    get_orderflow_read,
    get_portfolio_weights,
    get_position_sizing,
    get_ratios,
    get_regime_components,
    get_regime_read,
    get_relative_strength,
    get_risk_gate,
    get_sector_rank,
    get_session_discipline,
    get_strategy_quality,
    get_swing_set,
    get_tail_risk,
    get_volatility_contraction,
)
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.agents.utils.momentum_tools import get_momentum_scan
from tradingagents.agents.utils.value_dip_tools import (
    get_balance_sheet_health,
    get_bollinger_pct_b,
    get_decline_driver_check,
    get_fcf_yield,
    get_macd_divergence,
    get_support_structure,
    get_trade_expectancy,
    get_tranche_plan,
    get_valuation_z_score,
    get_value_dip_setup,
    get_vdu_entry_setup,
)
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client
from tradingagents.reporting import write_report_tree

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditional_logic import ConditionalLogic
from .propagation import Propagator
from .reflection import Reflector
from .setup import GraphSetup
from .signal_processing import SignalProcessor

logger = logging.getLogger(__name__)

# Process-lifetime cache for the realized-return yfinance fetches: multiple
# pending entries for the same ticker re-download the same window otherwise.
# Keyed by (canonical_symbol, start, end). Small, bounded by pending entries.
_returns_history_cache: dict[tuple[str, str, str], object] = {}


def _fetch_cached_history(symbol: str, start: str, end: str):
    """yfinance history with a process-lifetime memo (same window, same bars)."""
    if not symbol or not str(symbol).strip():
        # A blank symbol (e.g. a malformed memory-log entry) would hit
        # ``yf.Ticker(' ')`` and raise a raw TypeError + HTTP-4xx noise;
        # treat it as no data (the caller resolves it to return=None) instead.
        import pandas as pd

        return pd.DataFrame()
    key = (symbol, start, end)
    cached = _returns_history_cache.get(key)
    if cached is not None:
        return cached
    frame = yf.Ticker(symbol).history(start=start, end=end)
    if len(_returns_history_cache) < 256:  # bound the dict
        _returns_history_cache[key] = frame
    return frame


def _coerce_max_retries(value):
    """Validate an ``llm_max_retries`` value to a non-negative int.

    Accepts an int or a numeric string (env vars arrive as strings). Rejects
    booleans and negatives loudly so a misconfiguration fails at startup rather
    than silently disabling retries.
    """
    if isinstance(value, bool):
        raise ValueError(f"llm_max_retries must be an integer, not a boolean: {value!r}")
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"llm_max_retries must be an integer, got {value!r}") from exc
    if n < 0:
        raise ValueError(f"llm_max_retries must be >= 0, got {n}")
    return n


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=("market", "social", "news", "fundamentals"),
        debug=False,
        config: dict[str, Any] = None,
        callbacks: list | None = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        def _tier_kwargs(tier: str) -> dict:
            """Per-role max output tokens: quick = analysts/researchers/debaters/trader,
            deep = RM/PM. Only when the provider accepts max_tokens (OpenAI /
            OpenRouter / Anthropic / Bedrock all do).
            """
            cfg = self.config or {}
            if tier == "deep":
                v = cfg.get("max_output_tokens_deep") or cfg.get("max_output_tokens")
            else:
                v = cfg.get("max_output_tokens_quick") or cfg.get("max_output_tokens")
            out = dict(llm_kwargs)
            if v:
                out["max_tokens"] = int(v)
            return out

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **_tier_kwargs("deep"),
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **_tier_kwargs("quick"),
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()

        self.memory_log = TradingMemoryLog(self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            analyst_concurrency=self.config.get("analyst_concurrency", 1),
        )

        self.propagator = Propagator(
            max_recur_limit=self.config.get("max_recur_limit", 100),
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Graph-shape-affecting run choices, kept for the checkpoint signature.
        self.selected_analysts = tuple(selected_analysts)

        # Set up the graph: keep the workflow for recompilation with a checkpointer.
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _get_provider_kwargs(self) -> dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        # Sampling temperature is cross-provider: forward it whenever set.
        # float() here so a value coming from a TRADINGAGENTS_TEMPERATURE env
        # string ("0.2") works the same as a programmatic float.
        temperature = self.config.get("temperature")
        if temperature is not None and temperature != "":
            kwargs["temperature"] = float(temperature)

        # SDK retry budget is cross-provider. Forward it only when explicitly set
        # so each provider keeps its own default (usually 2) otherwise (#1091).
        max_retries = self.config.get("llm_max_retries")
        if max_retries is not None and max_retries != "":
            kwargs["max_retries"] = _coerce_max_retries(max_retries)

        return kwargs

    def _create_tool_nodes(self) -> dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                    # Deterministic verification snapshot (bound to the analyst
                    # LLM and required by its prompt; must be executable here or
                    # the call fails and the model reports it "unavailable").
                    get_verified_market_snapshot,
                    # Forward-looking positioning (free yfinance sources)
                    get_options_chain,
                    get_short_interest,
                    get_short_volume,
                    # Massive.com verification + movers (plan-gated, degrade)
                    get_market_snapshot,
                    get_top_movers,
                    # Money-flow positioning (moomoo; optional, degrades)
                    get_capital_flow,
                    get_expected_move,
                    get_market_snapshot_alpaca,
                    get_momentum_scan,
                    # Computed-analysis tools (deterministic signals).
                    get_swing_set,
                    get_relative_strength,
                    get_position_sizing,
                    get_risk_gate,
                    get_regime_read,
                    get_regime_components,
                    get_exit_check,
                    get_momentum_detail,
                    get_volatility_contraction,
                    get_orderflow_read,
                    get_sector_rank,
                    get_session_discipline,
                    get_strategy_quality,
                    get_tail_risk,
                    get_credit_spread_read,
                    # Value Dip + Swing hybrid (deterministic, computed signals).
                    get_bollinger_pct_b,
                    get_tranche_plan,
                    get_trade_expectancy,
                    get_macd_divergence,
                    get_vdu_entry_setup,
                    get_support_structure,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                    get_massive_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_massive_news,
                    get_global_news,
                    get_insider_transactions,
                    get_macro_indicators,
                    get_prediction_markets,
                    get_earnings_calendar,
                    get_sec_filings,
                    get_ipos,
                    # Scheduled catalysts + regime (moomoo; optional, degrades)
                    get_economic_calendar,
                    get_fed_watch,
                    get_market_breadth,
                    get_earnings_catalyst,
                    # Computed-analysis tools (deterministic signals).
                    get_catalyst_scale,
                    get_earnings_event_read,
                    get_beat_miss_sizing,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                    get_analyst_ratings,
                    # Smart-money + quality signals (moomoo; optional, degrades)
                    get_smart_money,
                    get_revenue_breakdown,
                    get_corporate_actions,
                    get_dividends,
                    get_institution_holdings,
                    get_earnings_surprise_history,
                    # Computed-analysis tools (deterministic signals).
                    get_analyst_verdict,
                    get_earnings_surprise,
                    get_earnings_quality,
                    get_portfolio_weights,
                    get_basic_financials,
                    get_insider_activity,
                    get_company_peers,
                    get_form4_insider,
                    get_ratios,
                    get_allocation,
                    get_dcf_valuation,
                    get_margin_of_safety,
                    get_composite_rank,
                    # Value Dip + Swing hybrid (deterministic, computed signals).
                    get_fcf_yield,
                    get_valuation_z_score,
                    get_value_dip_setup,
                    get_balance_sheet_health,
                    get_decline_driver_check,
                ]
            ),
        }

    def _resolve_benchmark(self, ticker: str) -> str:
        """Pick the benchmark ticker for alpha calculation against ``ticker``.

        ``config["benchmark_ticker"]`` overrides everything when set; otherwise
        the suffix map matches the ticker's exchange suffix (e.g. ``.T`` for
        Tokyo). US-listed tickers without a dotted suffix fall through to the
        empty-suffix entry (SPY by default). Unrecognised suffixes (including
        US tickers with dots like ``BRK.B``) also fall back to the empty-suffix
        entry, which is the right default because the alpha calculation works
        in USD.
        """
        explicit = self.config.get("benchmark_ticker")
        if explicit:
            return explicit
        benchmark_map = self.config.get("benchmark_map", {})
        ticker_upper = ticker.upper()
        for suffix, benchmark in benchmark_map.items():
            if suffix and ticker_upper.endswith(suffix.upper()):
                return benchmark
        return benchmark_map.get("", "SPY")

    def _resolve_returns_end(self, ticker: str, trade_date: str, holding_days: int) -> datetime:
        """Pick an end date whose window contains ~``holding_days`` trading days.

        Uses moomoo's trading-day calendar (exact market holidays/weekends)
        when OpenD is reachable; falls back to a calendar-day buffer heuristic.
        ``trade_date`` is inclusive, so we ask for ``holding_days + 2`` trading
        days and take the last one + 1 calendar day (yfinance ``end`` is
        exclusive).  Any failure (OpenD down, unsupported market) degrades to
        the old ``holding_days + 7``-calendar-day heuristic.
        """
        start = datetime.strptime(trade_date, "%Y-%m-%d")
        try:
            from tradingagents.dataflows.moomoo import get_trading_days_between

            probe = start + timedelta(days=holding_days * 2 + 21)
            days = get_trading_days_between(ticker, trade_date, probe.strftime("%Y-%m-%d"))
            # days[0] is the trade_date (or the first trading day after it).
            # We need holding_days + 1 return observations → holding_days + 2 rows.
            if len(days) >= holding_days + 2:
                target = days[holding_days + 1]
                return datetime.strptime(target, "%Y-%m-%d") + timedelta(days=1)
        except Exception:
            pass  # fall through to the calendar heuristic
        return start + timedelta(days=holding_days + 7)

    def _fetch_returns(
        self,
        ticker: str,
        trade_date: str,
        holding_days: int = 5,
        benchmark: str = "SPY",
    ) -> tuple[float | None, float | None, int | None]:
        """Fetch raw and alpha return for ticker over holding_days from trade_date.

        ``benchmark`` is the index used as the alpha baseline (resolved by the
        caller via ``_resolve_benchmark``). Returns ``(raw_return, alpha_return,
        actual_holding_days)`` or ``(None, None, None)`` if price data is
        unavailable (too recent, delisted, or network error).
        """
        from tradingagents.dataflows.symbol_utils import normalize_symbol

        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            end = self._resolve_returns_end(ticker, trade_date, holding_days)
            end_str = end.strftime("%Y-%m-%d")

            # Normalize so the realized-return lookup hits the same instrument
            # the analysis priced (e.g. XAUUSD -> GC=F) (#984). The benchmark is
            # already a canonical Yahoo symbol from ``_resolve_benchmark``.
            stock = _fetch_cached_history(normalize_symbol(ticker), trade_date, end_str)
            bench = _fetch_cached_history(benchmark, trade_date, end_str)

            if len(stock) < 2 or len(bench) < 2:
                return None, None, None

            actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0]) / stock["Close"].iloc[0]
            )
            bench_ret = float(
                (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0]) / bench["Close"].iloc[0]
            )
            alpha = raw - bench_ret
            return raw, alpha, actual_days
        except Exception as e:
            logger.warning(
                "Could not resolve outcome for %s on %s vs %s (will retry next run): %s",
                ticker,
                trade_date,
                benchmark,
                e,
            )
            return None, None, None

    def _resolve_pending_entries(self, ticker: str) -> None:
        """Resolve pending log entries for ticker at the start of a new run.

        Fetches returns for each same-ticker pending entry, generates reflections,
        then writes all updates in a single atomic batch write to avoid redundant I/O.
        Skips entries whose price data is not yet available (too recent or delisted).

        Trade-off: only same-ticker entries are resolved per run.  Entries for
        other tickers accumulate until that ticker is run again.
        """
        pending = [e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker]
        if not pending:
            return

        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker,
                entry["date"],
                benchmark=benchmark,
            )
            if raw is None:
                continue  # price not available yet — try again next run
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
                benchmark_name=benchmark,
            )
            self._maybe_record_reflection_outcome(ticker, entry["date"], alpha)
            updates.append(
                {
                    "ticker": ticker,
                    "trade_date": entry["date"],
                    "raw_return": raw,
                    "alpha_return": alpha,
                    "holding_days": days,
                    "reflection": reflection,
                }
            )

        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def resolve_instrument_context(self, ticker: str, asset_type: str = "stock") -> str:
        """Resolve ticker identity once and return the full instrument context.

        Deterministic yfinance lookup (cached, fail-open) injected into a
        context string so every agent anchors to the real company instead of
        hallucinating one from the price chart (#814). Both the propagate()
        path and the CLI call this so the resolved identity reaches the whole
        graph regardless of entry point.
        """
        identity = resolve_instrument_identity(ticker)
        context = build_instrument_context(ticker, asset_type, identity)
        # Analysis-only Alpaca enrichment: one live 1m snapshot line shared by
        # every analyst via the instrument context.
        try:
            from tradingagents.dataflows.alpaca import intraday_context as _intraday_ctx
            from tradingagents.dataflows.config import get_config

            if get_config().get("enable_alpaca"):
                extra = _intraday_ctx(ticker)
                if extra:
                    context = f"{context}\n{extra}"
        except Exception:
            pass
        return context

    def _run_signature(self, asset_type: str) -> str:
        """Graph-shape inputs that must invalidate a checkpoint if changed.

        Keyed into the checkpoint thread ID so a resume under a different analyst
        selection, debate/risk depth, or asset mode starts fresh instead of
        silently continuing the previous graph (#1089).
        """
        return "|".join(
            [
                "analysts=" + ",".join(self.selected_analysts),
                f"debate={self.config['max_debate_rounds']}",
                f"risk={self.config['max_risk_discuss_rounds']}",
                f"asset={asset_type}",
                f"conc={self.config.get('analyst_concurrency', 1)}",
            ]
        )

    def propagate(self, company_name, trade_date, asset_type: str = "stock"):
        """Run the trading agents graph for a company on a specific date.

        ``asset_type`` selects between the stock pipeline (default) and the
        crypto pipeline (``"crypto"``) shipped in #567 — the CLI auto-detects
        from the ticker; programmatic callers pass it explicitly. When
        ``checkpoint_enabled`` is set in config, the graph is recompiled with
        a per-ticker SqliteSaver so a crashed run can resume from the last
        successful node on a subsequent invocation with the same ticker+date.
        """
        self.ticker = company_name

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(self.config["data_cache_dir"], company_name)
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            step = checkpoint_step(
                self.config["data_cache_dir"],
                company_name,
                str(trade_date),
                self._run_signature(asset_type),
            )
            if step is not None:
                logger.info("Resuming from step %d for %s on %s", step, company_name, trade_date)
            else:
                logger.info("Starting fresh for %s on %s", company_name, trade_date)

        try:
            return self._run_graph(company_name, trade_date, asset_type=asset_type)
        finally:
            # Release this thread's moomoo gateway connection while the process
            # is healthy: the SDK's background threads tear down cleanly here,
            # whereas closing at interpreter exit can block on the dead recv
            # loop and hang the process (see dataflows/moomoo._close_all_ctxs).
            with contextlib.suppress(Exception):
                from tradingagents.dataflows.moomoo import close_context as _close_moomoo

                _close_moomoo()
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

    def save_reports(self, final_state, ticker, save_path=None) -> Path:
        """Write the markdown report tree for a completed run, like the CLI does.

        Programmatic callers get the same on-disk reports the CLI produces. Pass
        an explicit ``save_path`` or let it default under ``results_dir``.
        """
        if save_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = (
                Path(self.config["results_dir"])
                / "reports"
                / f"{safe_ticker_component(ticker)}_{stamp}"
            )
        return write_report_tree(final_state, ticker, save_path)

    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        """Execute the graph and write the resulting state to disk and memory log."""
        # Initialize state — inject memory log context for PM and the
        # deterministically resolved instrument identity for all agents.
        past_context = self.memory_log.get_past_context(company_name)
        # Append the aggregate track record (win rate / mean return / mean
        # alpha) so the Portfolio Manager can weigh its own historical accuracy,
        # not just individual past decisions.
        track_record = self.memory_log.get_track_record_stats(company_name)
        if track_record:
            past_context = f"{past_context}\n\n{track_record}" if past_context else track_record
        instrument_context = self.resolve_instrument_context(company_name, asset_type)
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        args = self.propagator.get_graph_args()

        # Inject thread_id so same ticker+date+graph-shape resumes; a different
        # date or graph shape starts fresh (#1089).
        if self.config.get("checkpoint_enabled"):
            tid = thread_id(company_name, str(trade_date), self._run_signature(asset_type))
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = tid

        if self.debug:
            trace = []
            last_printed = None
            for chunk in self.graph.stream(init_agent_state, **args):
                if chunk["messages"]:
                    msg = chunk["messages"][-1]
                    # Nodes after the trader don't append to messages, so the
                    # same trailing message repeats across chunks. Print it only
                    # when it changes (#1027); the trace/state merge is unchanged.
                    signature = (type(msg).__name__, getattr(msg, "content", None))
                    if signature != last_printed:
                        msg.pretty_print()
                        last_printed = signature
                    trace.append(chunk)
            # Streamed chunks are per-node deltas. Merge them so the returned
            # state matches what graph.invoke() yields in the non-debug path.
            final_state = {}
            for chunk in trace:
                final_state.update(chunk)
        else:
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection.
        self.curr_state = final_state
        # Wiring: attach config-gated strategy overlays (regime/sizing/context).
        final_state = self._apply_strategy_overlays(final_state, company_name)

        # Log state to disk.
        self._log_state(trade_date, final_state)

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear checkpoint on successful completion to avoid stale state.
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"],
                company_name,
                str(trade_date),
                self._run_signature(asset_type),
            )

        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"]["current_response"],
                "judge_decision": final_state["investment_debate_state"]["judge_decision"],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
            "strategy_overlays": final_state.get("strategy_overlays"),
        }

        # Save to file. Reject ticker values that would escape the
        # results directory when joined as a path component.
        safe_ticker = safe_ticker_component(self.ticker)
        directory = Path(self.config["results_dir"]) / safe_ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict[str(trade_date)], f, indent=4)

    def _apply_strategy_overlays(self, final_state, ticker):
        if not self.config.get("enable_strategy_overlays"):
            return final_state
        try:
            closes = self._try_fetch_closes(ticker)
            from tradingagents.strategies.overlays import (
                apply_overlay_to_state,
                build_strategy_overlays,
                fold_flow_into_overlay,
            )

            overlay = build_strategy_overlays(self.config, closes)
            if self.config.get("enable_orderflow"):
                try:
                    from tradingagents.strategies.orderflow import fetch_flow, summarize

                    flow_payload = fetch_flow(ticker)
                    if flow_payload is not None:
                        flow_summary = summarize(
                            flow_payload.get("buckets", {}),
                            weekly_nets=flow_payload.get("weekly_nets"),
                            thresholds={
                                "distribution_threshold": float(
                                    self.config.get("orderflow_distribution_threshold", 0.7)
                                )
                            },
                        )
                        overlay = fold_flow_into_overlay(overlay, flow_summary)
                except Exception as flow_exc:
                    logger.warning("orderflow fetch skipped: %s", flow_exc)
            # B1: scheduled-catalyst overlay (Phase-4 PEAD wiring) — `enable_events`.
            catalyst_snapshot = None
            if self.config.get("enable_events"):
                try:
                    from tradingagents.strategies.catalyst import (
                        build_catalyst_snapshot,
                        fetch_catalyst_data,
                        fold_catalyst_into_overlay,
                    )

                    trade_date_s = str(
                        final_state.get("trade_date") or datetime.now().strftime("%Y-%m-%d")
                    )
                    cat_data = fetch_catalyst_data(ticker, trade_date_s)
                    if cat_data is not None:
                        catalyst_snapshot = build_catalyst_snapshot(
                            cat_data, trade_date_s, self.config
                        )
                        overlay = fold_catalyst_into_overlay(overlay, catalyst_snapshot)
                except Exception as cat_exc:
                    logger.warning("catalyst overlay skipped: %s", cat_exc)
            if self.config.get("enable_position_contract"):
                try:
                    from tradingagents.strategies.contract import (
                        build_position_contract,
                    )

                    flow_use = None
                    flow = overlay.get("flow")
                    if flow is not None:
                        flow_use = {"distribution_score": flow.get("distribution_score")}
                    agreement = self._agreement_from_state(final_state)
                    calibrated_p = self._calibrated_p()
                    tranche_read = self._tranche_risk_read(closes)
                    entry_price = None
                    if tranche_read and tranche_read.get("valid"):
                        entry_price = tranche_read.get("avg_entry")
                    contract = build_position_contract(
                        cfg=self.config,
                        closes=closes,
                        flow_summary=flow_use,
                        agreement=agreement,
                        calibrated_p=calibrated_p,
                        catalyst_scale=(catalyst_snapshot or {}).get("scale"),
                        entry_price=entry_price,
                        trail_stop=(final_state.get("swing_exits") or {}).get("chandelier"),
                        implied_move_pct=(catalyst_snapshot or {}).get("implied_move_pct"),
                    )
                    if contract is not None:
                        final_state["position_contract"] = (
                            f"size {contract.size_pct:.1%}, stop "
                            f"{contract.stop_loss}, reason: {contract.reason()}"
                        )
                        overlay["position_contract"] = (
                            f"{contract.size_pct:.1%} @ stop {contract.stop_loss} "
                            f"({contract.reason()})"
                        )
                except Exception as contract_exc:
                    logger.warning("position contract skipped: %s", contract_exc)
            if self.config.get("enable_risk_governor"):
                try:
                    from tradingagents.strategies.book_risk import cvar as book_cvar
                    from tradingagents.strategies.risk_governor import (
                        build_risk_snapshot,
                        govern,
                    )

                    size_pct = None
                    stop_pct = None
                    if final_state.get("position_contract"):
                        size_pct = 0.0
                    contract = overlay.get("position_contract")
                    # best-effort size from the contract text we stored
                    import re as _re

                    for cand in (final_state.get("position_contract") or "").split(","):
                        m = _re.search(r"size ([0-9.]+)%", cand)
                        if m:
                            size_pct = float(m.group(1)) / 100.0
                    # Tranche fold: the governor sizes against the worst-case
                    # fully-scaled position (peak-deployed) and enforces the
                    # capital-at-risk budget, both from config-frozen params.
                    govern_size = size_pct
                    cap_at_risk = None
                    risk_cap = None
                    tranche_read = self._tranche_risk_read(closes)
                    if tranche_read and tranche_read.get("valid"):
                        govern_size = tranche_read.get("peak_deployed_pct")
                        cap_at_risk = tranche_read.get("capital_at_risk_pct")
                        risk_cap = self.config.get("tranche_risk_pct")
                        final_state.setdefault("tranche_context", {}).update(
                            {
                                "avg_entry": tranche_read.get("avg_entry"),
                                "peak_deployed_pct": tranche_read.get("peak_deployed_pct"),
                                "capital_at_risk_pct": tranche_read.get("capital_at_risk_pct"),
                                "peak_ok": tranche_read.get("peak_ok"),
                                "book_ok": tranche_read.get("book_ok"),
                            }
                        )
                    rets = None
                    if closes:
                        rets = __import__(
                            "tradingagents.strategies.contract", fromlist=["_log_returns"]
                        )._log_returns(closes)
                    cvar_pct = None
                    if rets and len(rets) >= 5:
                        cv = book_cvar(rets, alpha=0.05)
                        cvar_pct = abs(cv) if cv is not None else None
                    # The analyzed name's own daily-tail CVaR, kept for display
                    # alongside the (possibly basket-derived) gate input.
                    single_name_cvar = cvar_pct
                    # True portfolio CVaR (R2): when a risk basket is configured,
                    # mix the basket names' daily return series (weighted) and
                    # take the basket's historical CVaR as the daily tail budget
                    # instead of the analyzed name's own series. Falls back to
                    # the single-name series when the basket can't be resolved.
                    basket_budget = self._basket_cvar(ticker)
                    if basket_budget is not None:
                        cvar_pct = basket_budget
                    # Surface both numbers on the state so the report / agents
                    # can compare the analyzed name's own tail vs the book tail.
                    risk_ctx = final_state.setdefault("risk_context", {})
                    if basket_budget is not None:
                        risk_ctx["book_cvar"] = basket_budget
                    if single_name_cvar is not None:
                        risk_ctx["single_cvar"] = single_name_cvar
                    # risk2.md liquidity/ownership gate (opt-in). When
                    # enable_liquidity_gate is on, compute the composite
                    # liquidity verdict from the vendor OHLCV + float + short
                    # interest and pass it to the governor (ILLIQUID REJECTs,
                    # CAUTION WARNs). Off by default -> no behavior change.
                    liq_verdict = None
                    liq_dangers = None
                    if self.config.get("enable_liquidity_gate"):
                        try:
                            from tradingagents.strategies.liquidity_risk import (
                                amihud_illiquidity,
                                float_turnover as _ft,
                                free_float_factor as _iwf,
                                liquidity_verdict as _lv,
                            )

                            closes = final_state.get("closes") or []
                            volumes = final_state.get("volumes") or []
                            illiq = amihud_illiquidity(closes, volumes)
                            adv = (
                                sum(volumes[-30:]) / len(volumes[-30:])
                                if len(volumes) >= 30
                                else None
                            )
                            float_sh = None
                            try:
                                from tradingagents.dataflows.float_shares import (
                                    fetch_float_shares,
                                )

                                float_sh = fetch_float_shares(ticker)
                            except Exception:  # noqa: BLE001
                                float_sh = None
                            tot_sh = None
                            try:
                                from tradingagents.dataflows.statement_parsing import (
                                    fetch_ticker as _ftk,
                                )

                                fin = _ftk(ticker, self.config.get("date") or "") or {}
                                tot_sh = (fin.get("shares") or {}).get("current") if isinstance(
                                    fin.get("shares"), dict
                                ) else fin.get("shares")
                            except Exception:  # noqa: BLE001
                                tot_sh = None
                            ft = _ft(adv, float_sh)
                            iwf = _iwf(float_sh, tot_sh)
                            lv = _lv(
                                illiq,
                                ft,
                                None,  # days-to-absorb needs a liquidation block
                                iwf=iwf,
                            )
                            liq_verdict = lv.get("verdict")
                            liq_dangers = lv.get("dangers")
                            risk_ctx["liquidity"] = {
                                "verdict": liq_verdict,
                                "illiq": illiq,
                                "float_turnover": ft,
                                "iwf": iwf,
                                "dangers": liq_dangers,
                            }
                        except Exception:  # noqa: BLE001 - gate must never crash
                            liq_verdict = None
                    verdict = govern(
                        govern_size,
                        self.config,
                        cvar_pct=cvar_pct,
                        drawdown_pct=self.config.get("risk_max_drawdown_pct"),
                        capital_at_risk_pct=cap_at_risk,
                        risk_cap_pct=risk_cap,
                        liquidity_verdict=liq_verdict,
                        liquidity_dangers=liq_dangers,
                    )
                    # Catalyst hard block (framework Phase 4): "never initiate"
                    # inside the earnings window - a scheduled print within
                    # catalyst_hard_block_days forces REJECT regardless of size.
                    hard_block = (catalyst_snapshot or {}).get("hard_block")
                    if hard_block:
                        verdict = {
                            "verdict": "REJECT",
                            "reasons": [
                                f"catalyst hard block: earnings {hard_block['earnings_date']} "
                                f"in {hard_block['days_until']}d (window {hard_block['window_days']}d)"
                            ],
                            "numbers": "catalyst-hard-block",
                        }
                    final_state["risk_gate"] = verdict
                    if verdict["verdict"] in ("WARN", "REJECT"):
                        final_state["risk_snapshot"] = build_risk_snapshot(
                            verdict,
                            govern_size,
                            stop_pct,
                            cvar_pct,
                            capital_at_risk_pct=cap_at_risk,
                        )
                    if verdict["verdict"] == "REJECT":
                        final_state["risk_halt"] = True
                    if self.config.get("risk_audit_enabled"):
                        import json as _json

                        base = Path(
                            self.config.get("data_cache_dir", "~/.tradingagents")
                        ).expanduser()
                        audit = base / "risk_audit.jsonl"
                        audit.parent.mkdir(parents=True, exist_ok=True)
                        with audit.open("a", encoding="utf-8") as fh:
                            fh.write(
                                _json.dumps(
                                    {
                                        "ticker": ticker,
                                        "verdict": verdict["verdict"],
                                        "reasons": verdict.get("reasons", []),
                                    }
                                )
                                + "\n"
                            )
                except Exception as risk_exc:
                    logger.warning("risk governor skipped: %s", risk_exc)
            if self.config.get("enable_computed_context"):
                try:
                    from tradingagents.strategies.debate_context import (
                        build_computed_context,
                    )

                    overlay = overlay or {}
                    extra = [
                        f"regime={overlay.get('regime', '?')}",
                        f"flow={overlay.get('flow', {}).get('flag', 'n/a')}",
                    ]
                    if overlay.get("position_contract"):
                        extra.append("contract=" + overlay["position_contract"])
                    snippet = build_computed_context(self.config, extra=extra)
                    if snippet:
                        final_state["computed_context"] = snippet
                        overlay["context"] = overlay.get("context", "") + " | " + snippet
                except Exception as ctx_exc:
                    logger.warning("computed context skipped: %s", ctx_exc)
        except Exception as exc:
            logger.warning("strategy overlays skipped: %s", exc)
            return final_state
        return apply_overlay_to_state(final_state, overlay)

    def _try_fetch_closes(self, ticker, days=320):
        from tradingagents.dataflows.interface import route_to_vendor

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        closes = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) >= 5:
                with contextlib.suppress(ValueError):
                    closes.append(float(parts[4]))
        return closes

    def _log_returns_from_closes(self, closes) -> list:
        """Daily log-return series from closes (skips non-positive steps)."""
        return __import__(
            "tradingagents.strategies.contract", fromlist=["_log_returns"]
        )._log_returns(closes)

    def _tranche_risk_read(self, closes) -> dict | None:
        """Deterministic tranche worst-case read for the risk fold, or None.

        Only computes when ``enable_tranche_risk`` is on; uses measured closes
        (last close = P1) and config-frozen weights/stop/risk/account (never
        the LLM) so an agent's tranche choice can not inflate approved size.
        Returns the peak-deployed and capital-at-risk fractions, or None when
        the fold is off / the plan is unusable.
        """
        if not self.config.get("enable_tranche_risk"):
            return None
        try:
            from tradingagents.strategies.value_dip import tranche_risk_read

            return tranche_risk_read(
                closes,
                weights=tuple(self.config.get("tranche_weights") or (0.3, 0.3, 0.4)),
                stop_mult=float(self.config.get("tranche_stop_mult", 1.5)),
                risk_pct=float(self.config.get("tranche_risk_pct", 0.015)),
                account=float(self.config.get("tranche_account", 100_000.0)),
                atr_value=None,
                max_position_pct=float(self.config.get("max_position_pct", 0.30)),
                max_book_position_pct=float(self.config.get("risk_max_position_pct", 0.45)),
            )
        except Exception as tranche_exc:  # noqa: BLE001 - fold degrades silently
            logger.warning("tranche risk read skipped: %s", tranche_exc)
            return None

    def _basket_cvar(self, ticker: str, alpha: float = 0.05) -> float | None:
        """True portfolio CVaR for the configured risk basket, or None.

        Reads ``risk_basket_tickers`` (list) + optional ``risk_basket_weights``
        (dict) from config. When at least two basket names resolve aligned daily
        return series via the vendor chain (``_try_fetch_closes``), returns the
        abs() of the weighted basket's historical CVaR (``book_risk.portfolio_cvar``)
        so the risk governor budgets against the basket tail, not the single
        name. Returns None when the basket is unconfigured, cannot be resolved,
        or fewer than two names have usable series - the governor falls back
        to the analyzed name's own series.
        """
        tickers = [t for t in (self.config.get("risk_basket_tickers") or []) if t]
        if len(tickers) < 2:
            return None
        weights = self.config.get("risk_basket_weights") or {}
        returns_by_name: dict[str, list] = {}
        for name in tickers:
            try:
                closes = self._try_fetch_closes(str(name))
                rets = self._log_returns_from_closes(closes)
                if len(rets) >= 5:
                    returns_by_name[str(name)] = rets
            except Exception:  # noqa: BLE001 - a missing name just drops out
                continue
        if len(returns_by_name) < 2:
            return None
        try:
            from tradingagents.strategies.book_risk import portfolio_cvar

            cv = portfolio_cvar(returns_by_name, weights=weights, alpha=alpha)
            return abs(cv) if cv is not None else None
        except Exception:  # noqa: BLE001 - fall back to single-name
            return None

    def _maybe_record_reflection_outcome(self, ticker, trade_date, alpha):
        if not self.config.get("enable_reflection") or alpha is None:
            return
        try:
            from tradingagents.strategies.overlays import record_reflection_outcome

            base = Path(self.config.get("data_cache_dir", "~/.tradingagents")).expanduser()
            record_reflection_outcome(
                self.config,
                str(base / "strategy_ledger.jsonl"),
                "market",
                ticker,
                trade_date,
                float(alpha),
            )
        except Exception as exc:
            logger.warning("reflection record skipped: %s", exc)

    def _agreement_from_state(self, final_state) -> "float | None":
        if not self.config.get("enable_agreement"):
            return None
        try:
            from tradingagents.agents.utils.rating import parse_rating
            from tradingagents.strategies.consensus import agreement_score

            state = final_state.get("risk_debate_state") or {}
            stances = []
            for key in ("aggressive_history", "conservative_history", "neutral_history"):
                for chunk in (state.get(key) or [])[-3:]:
                    if isinstance(chunk, str):
                        stances.append(parse_rating(chunk))
            return agreement_score(stances)
        except Exception:
            return None

    def _calibrated_p(self) -> "float | None":
        if not self.config.get("enable_calibration"):
            return None
        try:
            base = Path(self.config.get("data_cache_dir", "~/.tradingagents")).expanduser()
            cal_file = base / "calibration_ledger.jsonl"
            if not cal_file.exists():
                return None
            from tradingagents.strategies.calibration import fit_buckets

            rows = []
            for ln in cal_file.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    import json

                    rows.append(json.loads(ln))
            _ = fit_buckets(rows)  # warm the table; used at decision-time later
            return None  # identity until confidence is stamped into the ledger
        except Exception:
            return None

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
