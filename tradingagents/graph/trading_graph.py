# TradingAgents/graph/trading_graph.py

import contextlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf
from langgraph.prebuilt import ToolNode

from tradingagents.agents.toolsets import analyst_toolset
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    resolve_instrument_identity,
)

# Import the abstract tool methods from agent_utils
from tradingagents.agents.utils.debate_roles import resolve_role_llm
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client
from tradingagents.reporting import write_report_tree

from .checkpointer import (
    checkpoint_step,
    clear_checkpoint,
    forget_run,
    get_checkpointer,
    resolve_run_id,
    thread_id,
)
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


def _data_quality_blocks_position(pm_decision: dict | None) -> bool:
    """True only when the PM POSITIVELY reported a degraded data slice.

    Contract (PortfolioDecision.data_quality): 'fresh' is clean, 'stale'/
    'partial' are degraded reads that block a new position, and an OMITTED
    field (or the placeholder string 'unknown', coerced to None at the schema
    boundary) means "not reported" — never a reason to block. Reading the
    field with a blanket ``or "unknown"`` default used to block every decision
    whose model left the optional field out.
    """
    dq = str((pm_decision or {}).get("data_quality") or "").strip().lower()
    return dq in ("stale", "partial")


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

        # Backup LLM (TRADINGAGENTS_BACKUP_LLM): a second model used ONLY for
        # the truncation-continuation retry - when a response is cut at the
        # output cap, the continuation runs on this model instead of re-paying
        # the one that keeps truncating. Spec format: "provider:model" (e.g.
        # "openrouter:deepseek/deepseek-chat") or a bare model id that uses
        # the primary provider. Empty/unset -> no backup, same-model
        # continuations (legacy behavior).
        self.backup_thinking_llm = None
        _backup_spec = str(self.config.get("backup_llm") or "").strip()
        if _backup_spec:
            _backup_provider = self.config.get("llm_provider", "")
            _backup_model = _backup_spec
            if ":" in _backup_spec:
                _bp, _bm = _backup_spec.split(":", 1)
                _backup_provider, _backup_model = _bp.strip(), _bm.strip()
            try:
                _backup_kwargs = dict(self._get_provider_kwargs(_backup_provider))
                _backup_cap = (
                    self.config.get("max_output_tokens_quick")
                    or self.config.get("max_output_tokens")
                )
                if _backup_cap:
                    _backup_kwargs["max_tokens"] = int(_backup_cap)
                _backup_client = create_llm_client(
                    provider=_backup_provider,
                    model=_backup_model,
                    base_url=self.config.get("backend_url"),
                    **_backup_kwargs,
                )
                self.backup_thinking_llm = _backup_client.get_llm()
                print(
                    f"[backup-llm] truncation continuation will retry on "
                    f"{_backup_provider}:{_backup_model}",
                    file=sys.stderr,
                )
            except Exception as exc:  # noqa: BLE001 - advisory; degrade to same-model
                print(
                    f"[backup-llm] unavailable ({exc}); truncation retries stay "
                    "on the primary model",
                    file=sys.stderr,
                )
                self.backup_thinking_llm = None

        # Per-role structured-debate LLMs (opt-in enable_debate): research
        # (bull/bear/judge) and risk (aggressive/conservative) resolve from
        # the debate_*_model config keys ("family:id") through
        # resolve_role_llm — direction.md maps aggressive->BULL_MODEL and
        # conservative->BEAR_MODEL, so both sections share the SAME debate
        # models. Neutral risk analyst has no key and falls back to the quick
        # tier in setup. Empty keys fall back to quick/deep.
        self.debate_llms = {}
        if self.config.get("enable_debate"):
            for _role in ("bull", "bear", "judge", "aggressive", "conservative", "neutral"):
                self.debate_llms[_role] = resolve_role_llm(
                    self.config, _role, factory=create_llm_client
                )
            # R3 config-time capability matrix (strategies/debate_capability.py):
            # warn (or fail closed under debate_require_capability_matrix) when a
            # resolved role model cannot meet its strictness floor (context /
            # structured-output / tool-binding). Advisory by default - the matrix
            # only refuses when the flag demands it.
            try:
                from tradingagents.agents.utils.debate_roles import role_model_spec
                from tradingagents.strategies.debate_capability import (
                    assess_model_capability,
                    capability_gate,
                )

                caps = {}
                for _role in self.debate_llms:
                    spec = role_model_spec(self.config, _role)
                    if spec:
                        provider, model = spec
                        caps[_role] = assess_model_capability(provider, model)
                for _msg in capability_gate(
                    caps, require=bool(self.config.get("debate_require_capability_matrix", False))
                ):
                    print(f"[debate-capability] {_msg}", file=sys.stderr)
            except Exception:  # noqa: BLE001 - advisory startup check
                pass

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
            config=self.config,
            debate_llms=self.debate_llms,
            backup_llm=self.backup_thinking_llm,
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
        # (signature, run_id) of the in-flight checkpointed run; set by propagate.
        self._checkpoint_scope: tuple[str, str] | None = None

    def _get_provider_kwargs(self, provider: str | None = None) -> dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation.

        ``provider`` overrides the config's ``llm_provider`` so the backup
        client (TRADINGAGENTS_BACKUP_LLM) gets ITS provider's knobs, not the
        primary's (a google thinking_level must never ride an anthropic
        backup model).
        """
        kwargs = {}
        provider = (provider or self.config.get("llm_provider", "")).lower()

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

        # Anti-repetition sampling controls are cross-provider: forward them
        # whenever set, float() for env strings ("0.9") like temperature. Each
        # client only forwards what its SDK supports.
        for key in ("top_p", "frequency_penalty", "presence_penalty"):
            v = self.config.get(key)
            if v is not None and v != "":
                kwargs[key] = float(v)

        # SDK retry budget is cross-provider. Forward it only when explicitly set
        # so each provider keeps its own default (usually 2) otherwise (#1091).
        max_retries = self.config.get("llm_max_retries")
        if max_retries is not None and max_retries != "":
            kwargs["max_retries"] = _coerce_max_retries(max_retries)

        return kwargs

    def _create_tool_nodes(self) -> dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods.

        Each node is wrapped so tools already gathered deterministically
        (forced-tool evidence) short-circuit instead of re-hitting the vendor
        (user directive; see evidence_gather.make_short_circuit_tool_node).
        """
        nodes: dict[str, ToolNode] = {
            # Derived from the analyst's own toolset (tradingagents.agents
            # .toolsets): the node executes exactly what the analyst binds, so
            # a bound tool can never be rejected as unknown and a node can
            # never carry a tool no analyst binds (P0-4 / S1).
            key: ToolNode(analyst_toolset(key), handle_tool_errors=True)
            for key in ("market", "news", "fundamentals")
        }
        from tradingagents.agents.utils.evidence_gather import (
            make_short_circuit_tool_node,
        )

        return {
            key: make_short_circuit_tool_node(node, key)
            for key, node in nodes.items()
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
            self._maybe_record_calibration(ticker, entry["date"], alpha)
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
        selection, debate/risk depth, debate mode, or asset mode starts fresh
        instead of silently continuing the previous graph (#1089). ``enable_debate``
        swaps the whole research-debate node set (structured Bull/Bear/L1/
        Finalize vs the legacy Bull/Bear/Aggressive/Conservative/Neutral), so a
        checkpoint from the other mode would replay a pending node the resumed
        graph does not contain.
        """
        return "|".join(
            [
                "analysts=" + ",".join(self.selected_analysts),
                f"debate={self.config['max_debate_rounds']}",
                f"risk={self.config['max_risk_discuss_rounds']}",
                f"asset={asset_type}",
                f"conc={self.config.get('analyst_concurrency', 1)}",
                f"debate_mode={bool(self.config.get('enable_debate', False))}",
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
        Each run checkpoints under its own thread id (``config["run_id"]`` when
        given, else an id resolved by ``checkpointer.resolve_run_id``) so two
        concurrent runs of the same ticker+date never clear each other's rows.
        """
        self.ticker = company_name

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            data_dir = self.config["data_cache_dir"]
            self._checkpointer_ctx = get_checkpointer(data_dir, company_name)
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            signature = self._run_signature(asset_type)
            run_id = resolve_run_id(
                data_dir,
                company_name,
                str(trade_date),
                signature,
                str(self.config.get("run_id") or ""),
            )
            self._checkpoint_scope = (signature, run_id)
            step = checkpoint_step(data_dir, company_name, str(trade_date), signature, run_id)
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
                self._checkpoint_scope = None
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
        # Seed the deterministic risk context BEFORE the Portfolio Manager runs:
        # the PM reads state["risk_context"] to ground its tail-risk / liquidity
        # / book-drawdown language, but it was previously only computed in
        # _apply_strategy_overlays AFTER the graph completed, so the PM never
        # saw it (cvar_line/liq_line were always empty). This precompute is the
        # single producer of those quantities; the post-graph overlays CONSUME
        # them instead of recomputing, so one number has one producer.
        if self.config.get("enable_risk_governor") and not init_agent_state.get("risk_context"):
            rc = self._precompute_risk_context(company_name)
            if rc:
                init_agent_state["risk_context"] = rc
        # Phase A-E: compile + inject the deterministic decision context (regime
        # gate, re-rating evidence, trade plan card, risk snapshot, drift hint)
        # so the Trader / PM / 3 risk debators get hard computed data, not LLM
        # prose. Always advisory - never blocks.
        init_agent_state["computed_decision_context"] = self._compiled_decision_context(
            company_name, init_agent_state
        )
        args = self.propagator.get_graph_args()

        # Inject thread_id so same ticker+date+graph-shape+run resumes; a
        # different date, graph shape or run starts fresh (#1089).
        if self._checkpoint_scope is not None:
            signature, run_id = self._checkpoint_scope
            tid = thread_id(company_name, str(trade_date), signature, run_id)
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

        # W1-1 prediction ledger: every decision becomes a scorable prediction
        # row (advisory; never gates). Guarded by enable_prediction_ledger.
        try:
            if self.config.get("enable_prediction_ledger"):
                from tradingagents.strategies.prediction_ledger import log_decision

                log_decision(
                    ticker=company_name,
                    date=trade_date,
                    rating=str((final_state.get("pm_decision") or {}).get("rating") or ""),
                    direction="",
                    entry=None,
                    confidence=None,
                    horizon_days=int(self.config.get("prediction_horizon_days", 60)),
                    data_quality=(final_state.get("pm_decision") or {}).get("data_quality") or "unknown",
                    results_dir=self.config.get("results_dir"),
                )
        except Exception:  # noqa: BLE001 - ledger is advisory
            pass

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear this run's checkpoint on successful completion to avoid stale
        # state; never a concurrent run's thread.
        if self._checkpoint_scope is not None:
            signature, run_id = self._checkpoint_scope
            clear_checkpoint(
                self.config["data_cache_dir"],
                company_name,
                str(trade_date),
                signature,
                run_id,
            )
            forget_run(
                self.config["data_cache_dir"],
                company_name,
                str(trade_date),
                signature,
                run_id,
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
            # Regime/sizing overlays need >= 60 bars; a thinner series (new
            # listing, thinly-traded ADR, partial vendor history) yields None.
            # Treat it as an EMPTY overlay so the order-flow / contract /
            # governor / context folds below no-op cleanly instead of raising
            # "'NoneType' object has no attribute 'get'" for each fold.

            if overlay is None:
                logger.warning(
                    "strategy overlays skipped for %s: %d close bars (< 60 required)",
                    ticker,
                    len(closes) if closes else 0,
                )
                overlay = {}
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
            # News-sentiment factor fold (opt-in `enable_sentiment_factor`): the
            # position scale only moves when the name's measured IC clears the
            # floor; otherwise neutral 1.0 (never blocks).
            if self.config.get("enable_sentiment_factor"):
                try:
                    from tradingagents.strategies.overlays import fold_sentiment_into_overlay

                    sent_ctx = self._sentiment_factor_read(ticker, closes)
                    if sent_ctx:
                        overlay = fold_sentiment_into_overlay(
                            overlay,
                            sent_ctx,
                            min_ic=float(self.config.get("sentiment_factor_min_ic", 0.02)),
                            max_scale=float(self.config.get("sentiment_factor_max_scale", 0.2)),
                            min_scale=float(self.config.get("sentiment_factor_min_scale", 0.5)),
                        )
                except Exception as sent_exc:
                    logger.warning("sentiment factor overlay skipped: %s", sent_exc)
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
                    regime_label = None
                    if isinstance(overlay, dict) and overlay.get("regime"):
                        regime_label = str(overlay.get("regime"))
                    calibrated_p = self._calibrated_p(
                        str(final_state.get("final_trade_decision") or ""),
                        regime=regime_label,
                    )
                    tranche_read = self._tranche_risk_read(closes)
                    entry_price = None
                    if tranche_read and tranche_read.get("valid"):
                        entry_price = tranche_read.get("avg_entry")
                    _hard_guards: tuple[str, ...] = ()
                    if self.config.get("enable_hard_guards"):
                        # hard-guard sources from the deterministic risk state:
                        # liquidity ILLIQUID, data-quality failure, risk_halt.
                        _hard_guards = []
                        _rg = final_state.get("risk_gate") or {}
                        _verdict = str(_rg.get("verdict") or "")
                        if _verdict == "REJECT":
                            _hard_guards.append("max_portfolio_risk")
                        if _data_quality_blocks_position(final_state.get("pm_decision")):
                            _hard_guards.append("data_quality_failure")
                        # The liquidity verdict lives in the risk context (the
                        # pre-graph precompute is its single producer). The old
                        # read was a dict-key read on `risk_snapshot`, which
                        # build_risk_snapshot returns as a STR - so the guard
                        # could never fire. Unknown/absent verdicts stay silent;
                        # only a genuine ILLIQUID read blocks.
                        _liq = (final_state.get("risk_context") or {}).get("liquidity") or {}
                        if str(_liq.get("verdict") or "").upper() == "ILLIQUID":
                            _hard_guards.append("insufficient_liquidity")
                        _hard_guards = tuple(_hard_guards)
                    _rf = 1.0
                    _vcf = 1.0
                    if self.config.get("regime_state_enable") or self.config.get("vol_cap_enable"):
                        try:
                            from tradingagents.strategies.regime_state import (
                                regime_state as _rs,
                                vol_cap_factor as _vcfn,
                            )

                            _ohlcv_state = final_state.get("ohlcv") or {}
                            _rsd = _rs(
                                closes,
                                _ohlcv_state.get("highs") or None,
                                _ohlcv_state.get("lows") or None,
                            )
                            _rf = _rsd["factor"]
                            if self.config.get("vol_cap_enable"):
                                # double-count guard: F_regime drops its vol leg
                                # when the standalone ladder carries it.
                                from tradingagents.strategies.regime_state import (
                                    regime_factor as _rfn,
                                )

                                _rf = _rfn(
                                    _rsd["trend"]["label"], "NORMAL", _rsd["drawdown"]["label"],
                                    include_vol_leg=False,
                                )
                                _vcf = _vcfn(_rsd["vol_ratio"])
                        except Exception:  # noqa: BLE001 - advisory scale degrades
                            _rf = 1.0
                            _vcf = 1.0
                    _kf = 1.0
                    if self.config.get("knife_composite_enable"):
                        try:
                            from tradingagents.strategies.knife_guard import knife_score as _ks

                            _kc = _ks(
                                closes,
                                (final_state.get("ohlcv") or {}).get("highs") or None,
                                (final_state.get("ohlcv") or {}).get("lows") or None,
                                (final_state.get("ohlcv") or {}).get("volumes") or None,
                            )
                            _kf = _kc["factor"]
                        except Exception:  # noqa: BLE001 - advisory scale degrades
                            _kf = 1.0
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
                        knife_factor=_kf,
                        regime_factor=_rf,
                        vol_cap_factor=_vcf,
                        hard_guards=_hard_guards,
                    )
                    if contract is not None:
                        final_state["position_contract"] = contract.summary()
                        overlay["position_contract"] = (
                            f"{contract.size_pct:.1%} @ stop {contract.stop_loss} "
                            f"({contract.reason()})"
                        )
                except Exception as contract_exc:
                    logger.warning("position contract skipped: %s", contract_exc)
            if self.config.get("enable_risk_governor"):
                try:
                    from tradingagents.strategies.risk_governor import (
                        build_risk_snapshot,
                        default_limits,
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
                    # Single source (W4): the pre-graph precompute produced the
                    # CVaR / liquidity / drawdown context the Portfolio Manager
                    # reasoned on; the gate consumes those numbers instead of
                    # recomputing them, so each quantity has one producer.
                    risk_ctx = final_state.setdefault("risk_context", {})
                    if not risk_ctx:
                        risk_ctx.update(self._precompute_risk_context(ticker))
                    cvar_pct = risk_ctx.get("book_cvar")
                    if cvar_pct is None:
                        cvar_pct = risk_ctx.get("single_cvar")
                    # Book-level correlated stress (item 2): shock the whole
                    # basket together, not just single names. Surfaces in the
                    # risk snapshot and the report's risk-gate block.
                    basket_stress = self._basket_stress(ticker)
                    if basket_stress is not None:
                        risk_ctx["book_stress"] = basket_stress
                    # risk2.md liquidity/ownership read: the pre-graph
                    # precompute is its single producer (gated on
                    # enable_liquidity_gate); this gate and the PM prompt
                    # consume one read, never a second computation.
                    liq = risk_ctx.get("liquidity") or {}
                    liq_verdict = liq.get("verdict")
                    liq_dangers = liq.get("dangers")
                    basket_dd = risk_ctx.get("book_drawdown")
                    verdict = govern(
                        govern_size,
                        self.config,
                        cvar_pct=cvar_pct,
                        # measured book drawdown, not the config limit - a
                        # realized >limit drawdown must actually block new risk
                        # (previously the limit was passed to itself: the
                        # R0/R2 drawdown stop could never fire).
                        drawdown_pct=basket_dd,
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
                    # drawdown_limit is hoisted by the pre-graph precompute
                    # (single source); setdefault keeps a direct-call fallback
                    # reading the same limits registry the governor gates on.
                    risk_ctx.setdefault(
                        "drawdown_limit", default_limits(self.config)["risk_max_drawdown_pct"]
                    )
                    if verdict["verdict"] in ("WARN", "REJECT"):
                        final_state["risk_snapshot"] = build_risk_snapshot(
                            verdict,
                            govern_size,
                            stop_pct,
                            cvar_pct,
                            capital_at_risk_pct=cap_at_risk,
                            drawdown_pct=basket_dd,
                        )
                    if verdict["verdict"] == "REJECT":
                        final_state["risk_halt"] = True
                    if self.config.get("risk_audit_enabled"):
                        from tradingagents.strategies.hash_chain_audit import (
                            append as _chain_append,
                        )

                        base = Path(
                            self.config.get("data_cache_dir", "~/.tradingagents")
                        ).expanduser()
                        audit = base / "risk_audit.jsonl"
                        # Hash-chained tamper-evident ledger (Vibe-Trading
                        # audit_chain): every row pins the previous row's hash,
                        # so a later edit breaks the chain (risk_report.py
                        # --audit verifies).
                        _chain_append(
                            audit,
                            {
                                "ticker": ticker,
                                "verdict": verdict["verdict"],
                                "reasons": verdict.get("reasons", []),
                            },
                        )
                except Exception as risk_exc:
                    logger.warning("risk governor skipped: %s", risk_exc)
        except Exception as exc:
            logger.warning("strategy overlays skipped: %s", exc)
            return final_state
        return apply_overlay_to_state(final_state, overlay)

    def _try_fetch_closes(self, ticker, days=320):
        from tradingagents.dataflows.interface import route_to_vendor

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        rows: list[tuple[str, float]] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) >= 5:
                with contextlib.suppress(ValueError):
                    rows.append((parts[0].strip(), float(parts[4])))
        # Some vendors (e.g. EODHD) return rows NEWEST-first; every consumer of
        # this series treats ``closes[-1]`` as the latest close (the trade-plan
        # reference price, basket return mixes, regime reads ...), so normalize
        # to ASCENDING date order after parsing. Same fix as analysis_tools._ohlcv
        # (the ABNB $128.56 / TSM 288.88 stale-close incidents: closes[-1] was the
        # OLDEST row). ISO dates sort lexicographically.
        if len(rows) > 1:
            rows.sort(key=lambda r: r[0])
        return [close for _, close in rows]

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

    def _sentiment_factor_read(self, ticker: str, closes: list) -> dict | None:
        """Measured news-sentiment factor read for the opt-in overlay fold.

        Returns ``{"rank_ic", "innovation", "sma_7d", "source"}`` or None when
        the run-level series is missing / coverage is insufficient (the fold
        then stays neutral 1.0 — never blocks). ``rank_ic`` is the name's own
        measured 5-day rank IC over the trailing window (deterministic);
        ``innovation`` is the latest sentiment innovation.
        """
        if not self.config.get("enable_sentiment_factor"):
            return None
        try:
            from tradingagents.dataflows.eodhd import _sentiment_points_eodhd
            from tradingagents.strategies import sentiment_research as _sr

            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
            points = _sentiment_points_eodhd(ticker, start, end)
            if not points:
                return None
            sent = sorted(points, key=lambda p: p["date"])
            scores = [float(p["score"]) for p in sent]
            if len(scores) < 20:
                return None
            # 7-day SMA + latest innovation (mirrors the series tool).
            smas = []
            acc, count = 0.0, 0
            for i, s in enumerate(scores):
                acc += s
                count += 1
                if i >= 7:
                    acc -= scores[i - 7]
                    count -= 1
                smas.append(acc / count if count else None)
            latest_sma = smas[-1]
            latest_inn = None
            if len(smas) >= 2 and smas[-2] is not None:
                latest_inn = scores[-1] - smas[-2]
            # Name-level 5-day rank IC: cross-correlate sentiment with the
            # name's own forward returns (the strongest |spearman| lag).
            if len(closes) < 40:
                return None
            closes_f = [float(c) for c in closes]
            rets = [(closes_f[i] / closes_f[i - 1] - 1.0) for i in range(1, len(closes_f))]
            n = min(len(scores), len(rets))
            use_s = scores[-n:]
            use_r = [rets[-i] if i <= len(rets) else None for i in range(1, n + 1)]
            ll = _sr.sentiment_lead_lag(use_s, [r for r in use_r if r is not None], max_lags=5)
            rank_ic = None
            if ll:
                best = max(ll, key=lambda r: abs(r["spearman_corr"]))
                rank_ic = round(best["spearman_corr"], 4)
            if rank_ic is None:
                return None
            return {
                "rank_ic": rank_ic,
                "innovation": round(latest_inn, 4) if latest_inn is not None else None,
                "sma_7d": round(latest_sma, 4) if latest_sma is not None else None,
                "source": "eodhd",
            }
        except Exception as sent_exc:  # noqa: BLE001 - fold degrades to neutral
            logger.warning("sentiment factor read skipped: %s", sent_exc)
            return None

    def _compiled_decision_context(self, ticker: str, state: dict | None = None) -> str:
        """Compile the deterministic decision context fed to the Trader, PM
        and the 3 risk debators (Phase A-E). All advisory; never blocks.

        Includes the regime gate, re-rating evidence, a trade plan card (unified
        stop + tranche levels + tiers + BE rule + adherence checklist) and the
        current book risk/daily-loss/HWM snapshot when measurable. Every number
        is computed or explicit 'unavailable' - never imagined. Best-effort:
        any hiccup degrades to a short line, never breaks the run.
        """
        out = []
        closes = []
        try:
            closes = self._try_fetch_closes(ticker)
        except Exception:  # noqa: BLE001
            closes = []
        try:
            from tradingagents.strategies.book_positions import render_holdings_block

            book_line = render_holdings_block(self.config)
            if book_line:
                out.append(book_line)
        except Exception:  # noqa: BLE001
            pass
        try:
            from tradingagents.strategies.regime import regime_gate_read

            rg = regime_gate_read(closes, cfg=self.config, catalyst_window=False) or {}
            out.append(
                "Computed regime gate (mean-reversion entry): "
                f"verdict={rg.get('verdict')} pass={rg.get('pass')} "
                f"vol_pct={rg.get('vol_pct')} fast_downtrend={rg.get('fast_downtrend')} "
                f"reasons={'; '.join(rg.get('reasons') or [])}"
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            from tradingagents.strategies.trade_plan import (
                build_trade_plan,
                measured_inputs,
            )

            plan = build_trade_plan(
                ticker=ticker,
                price=(closes[-1] if closes else None),
                config=self.config,
                **measured_inputs(closes, self.config),
            )
            out.append(plan)
        except Exception:  # noqa: BLE001
            pass
        # Book risk / daily-loss / HWM (B1) - from the memory ledger when the
        # track record exposes realized returns, else the governor's context.
        try:

            rctx = (state or {}).get("risk_context") or {}
            line = "Computed risk snapshot (advisory): "
            if rctx.get("single_cvar") is not None:
                line += f"analyzed-name CVaR {rctx['single_cvar']:.2%}; "
            if rctx.get("book_cvar") is not None:
                line += f"book CVaR {rctx['book_cvar']:.2%}; "
            if rctx.get("book_stress") is not None:
                line += f"book stress {rctx['book_stress']:.2%}; "
            if line.endswith(": "):
                line += "no CVaR measured"
            out.append(line)
        except Exception:  # noqa: BLE001
            pass
        # Risk factsheet (Phase-3 audit wiring): limits registry + vol
        # estimates + tranche capital-at-risk + fixed-risk size. All pure /
        # best-effort; every number is computed or explicit 'unavailable'.
        try:
            if self.config.get("enable_risk_governor"):
                from tradingagents.strategies.risk_governor import default_limits

                lim = default_limits(self.config)
                out.append(
                    "Computed limits registry (advisory): "
                    f"max_position={lim['max_position_pct']:.0%} "
                    f"book_cap={lim['max_book_position_pct']:.0%} "
                    f"cvar_budget={lim['risk_daily_cvar_budget_pct']:.1%} "
                    f"drawdown_limit={lim['risk_max_drawdown_pct']:.0%} "
                    f"sector_cap={self.config.get('sector_cap_limit', 0.35):.0%}"
                )
        except Exception:  # noqa: BLE001
            pass
        try:
            import math

            if closes and len(closes) >= 60:
                rets = []
                for i in range(1, len(closes)):
                    if closes[i - 1] > 0:
                        rets.append(math.log(closes[i] / closes[i - 1]))
                from tradingagents.strategies.volatility_models import (
                    ewma_vol,
                    garch11_fit,
                )

                mean = sum(rets) / len(rets)
                var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
                close_vol = math.sqrt(var) * math.sqrt(252)
                ew = ewma_vol(rets)
                gc = garch11_fit(rets)
                lr = gc.get("long_run_vol") if gc else None
                line = f"Computed vol estimates (advisory): close_vol={close_vol:.1%}"
                if ew is not None:
                    line += f" ewma={ew:.1%}"
                if lr is not None:
                    line += f" garch_long_run={lr:.1%}"
                out.append(line)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.config.get("enable_tranche_risk") and closes:
                from tradingagents.strategies.value_dip import tranche_risk_read

                tr = tranche_risk_read(
                    closes,
                    weights=tuple(self.config.get("tranche_weights") or (0.3, 0.3, 0.4)),
                    stop_mult=float(self.config.get("tranche_stop_mult", 1.5)),
                    risk_pct=float(self.config.get("tranche_risk_pct", 0.015)),
                    account=float(self.config.get("tranche_account", 100000.0)),
                    max_position_pct=float(self.config.get("max_position_pct", 0.30)),
                    max_book_position_pct=self.config.get("risk_max_position_pct"),
                )
                if tr.get("valid"):
                    out.append(
                        "Computed tranche risk (worst-case scale-in, advisory): "
                        f"peak_deployed={tr['peak_deployed_pct']:.1%} "
                        f"capital_at_risk={tr['capital_at_risk_pct']:.2%} "
                        f"avg_entry={tr.get('avg_entry')} stop={tr.get('stop')}"
                    )
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.config.get("enable_risk_governor") and closes and closes[-1] > 0:
                from tradingagents.strategies.contract import _atr_or_proxy
                from tradingagents.strategies.risk_sizing import risk_money

                atr_v = _atr_or_proxy(closes, None, None, window=14)
                if atr_v and atr_v > 0:
                    entry = float(closes[-1])
                    stop = entry - 2.0 * atr_v
                    if stop > 0:
                        shares = risk_money(
                            entry,
                            stop,
                            float(self.config.get("tranche_account", 100000.0)),
                            float(self.config.get("risk_per_trade", 0.01)),
                            commission_rate=0.0,
                        )
                        out.append(
                            "Computed fixed-risk size (advisory): "
                            f"{shares:.0f} units at {entry:.2f} with a "
                            f"2-ATR stop {stop:.2f} (risk {self.config.get('risk_per_trade', 0.01):.1%} "
                            f"of {self.config.get('tranche_account', 100000.0):,.0f} account)"
                        )
        except Exception:  # noqa: BLE001
            pass
        # D2 drift/alpha-decay monitor hint (cheap, from the strategy-quality
        # report's drift block when available).
        try:

            mlog = self.memory_log.load_entries() if getattr(self, "memory_log", None) else []
            resolved = [
                float(e["raw"]) for e in mlog
                if e.get("raw") is not None and not e.get("pending")
                and isinstance(e.get("raw"), (int, float))
            ]
            if len(resolved) >= 12:
                recent = resolved[-8:]
                base_win = sum(1 for r in resolved if r > 0) / len(resolved)
                rec_win = sum(1 for r in recent if r > 0) / len(recent)
                if rec_win < base_win - 0.15:
                    out.append(
                        "Alpha-decay monitor: recent win rate "
                        f"{rec_win:.0%} trails baseline {base_win:.0%} "
                        "- REVIEW before adding risk."
                    )
        except Exception:  # noqa: BLE001
            pass
        # P1/P2/C3 pre-open + execution-quality advisory reads (Alpaca free
        # IEX). All degrade to '' on missing data - never fabricated. Feed the
        # 5 decision agents the same measurements the pre-market reviewer sees.
        try:
            if self.config.get("enable_preopen_rvol"):
                from tradingagents.dataflows.preopen import (
                    premarket_rvol,
                    preopen_book_depth,
                    preopen_gap,
                )

                rv = premarket_rvol(ticker) or {}
                if rv.get("rvol") is not None:
                    x = float(self.config.get("preopen_rvol_institutional_x", 2.0))
                    tag = "institutional" if rv["rvol"] >= x else "retail/quiet"
                    out.append(
                        f"Pre-market RVOL {rv['rvol']:.2f}x ({tag}; "
                        f"today {rv.get('today_vol'):.0f} vs "
                        f"{rv.get('avg_vol'):.0f} 30d pre-open avg)"
                    )
                pg = preopen_gap(ticker) or {}
                if pg.get("gap_pct") is not None:
                    out.append(
                        f"Pre-open gap {pg['gap_pct']:+.2%} vs live pre-open "
                        f"price {pg.get('preopen_price')}"
                    )
                if self.config.get("enable_preopen_depth"):
                    pd = preopen_book_depth(ticker) or {}
                    if pd.get("thin") is not None:
                        out.append(
                            f"Pre-open book: spread_bps={pd.get('spread_bps')} "
                            f"bid/ask imbalance={pd.get('bid_ask_imbalance')} "
                            f"thin={'YES' if pd.get('thin') else 'no'}"
                        )
        except Exception:  # noqa: BLE001 - advisory, never breaks a run
            pass
        # G2 calibration: inject the PM's own confidence->win-rate track record
        # when enable_calibration is on, so it calibrates its declared
        # confidence against realized outcomes (decision_hardening_spec G2).
        try:
            if self.config.get("enable_calibration"):
                from tradingagents.strategies.calibration import (
                    calibration_table_text,
                    fit_buckets,
                )

                base = Path(self.config.get("data_cache_dir", "~/.tradingagents")).expanduser()
                cal_file = base / "calibration_ledger.jsonl"
                if cal_file.exists():
                    rows = []
                    import json as _json

                    for ln in cal_file.read_text(encoding="utf-8").splitlines():
                        if ln.strip():
                            rows.append(_json.loads(ln))
                    table = fit_buckets(rows)
                    txt = calibration_table_text(table)
                    if txt and txt != "no calibration history yet":
                        out.append(
                            f"**Confidence calibration** (deterministic, G2):\n{txt}"
                        )
        except Exception:  # noqa: BLE001 - advisory, never breaks a run
            pass
        return "\n\n".join(out) if out else "Computed decision context: unavailable."

    def _precompute_risk_context(self, ticker: str) -> dict:
        """Deterministic pre-decision risk context for the PM prompt, computed
        BEFORE the graph runs so the Portfolio Manager can ground its
        tail-risk / liquidity / book-drawdown / limits language in numbers that
        exist at decision time.

        Single producer (W4): the post-graph risk governor CONSUMES these
        values from ``state['risk_context']`` instead of recomputing them, so
        each quantity has exactly one producer. Best-effort - never raises.
        """
        out: dict = {}
        try:
            closes = self._try_fetch_closes(ticker)
            rets = self._log_returns_from_closes(closes)
            if len(rets) >= 5:
                from tradingagents.strategies.book_risk import cvar as _cvar

                cv = _cvar(rets, alpha=0.05)
                if cv is not None:
                    out["single_cvar"] = abs(cv)
            basket = self._basket_cvar(ticker)
            if basket is not None:
                out["book_cvar"] = basket
            drawdown = self._basket_drawdown(ticker)
            if drawdown is not None:
                out["book_drawdown"] = drawdown
            # Limits registry (same source the governor gates against), so a
            # PM prompt rule can cite the cap / budget / drawdown limit it is
            # actually measured against.
            from tradingagents.strategies.risk_governor import default_limits

            limits = default_limits(self.config)
            out["drawdown_limit"] = limits["risk_max_drawdown_pct"]
            out["max_position_pct"] = limits["max_position_pct"]
            out["cvar_budget_pct"] = limits["risk_daily_cvar_budget_pct"]
            liquidity = self._liquidity_context(ticker, closes)
            if liquidity is not None:
                out["liquidity"] = liquidity
        except Exception:  # noqa: BLE001 - precompute is best-effort
            pass
        return out

    def _liquidity_context(self, ticker: str, closes: list) -> dict | None:
        """Composite liquidity/ownership read for the analyzed name.

        Single producer of ``risk_context['liquidity']``: the pre-graph
        precompute calls it and the post-graph risk governor consumes the
        result. Gated on ``enable_liquidity_gate`` (None when off, so the gate
        stays opt-in). Volume is not loaded on this pre-graph path, so the
        Amihud / dollar-volume legs read None (unknown, never fabricated); the
        close-based Roll spread and the share-count IWF still resolve. Never
        raises.
        """
        if not self.config.get("enable_liquidity_gate"):
            return None
        try:
            from tradingagents.strategies.liquidity_risk import (
                amihud_illiquidity,
                float_turnover as _ft,
                free_float_factor as _iwf,
                liquidity_verdict as _lv,
                roll_spread as _roll,
            )

            closes = list(closes or [])
            illiq = amihud_illiquidity(closes, [])
            float_sh = None
            try:
                from tradingagents.dataflows.float_shares import fetch_float_shares

                float_sh = fetch_float_shares(ticker)
            except Exception:  # noqa: BLE001 - a missing float drops that leg only
                float_sh = None
            tot_sh = None
            try:
                from tradingagents.dataflows.statement_parsing import (
                    fetch_ticker as _ftk,
                )

                fin = _ftk(ticker, self.config.get("date") or "") or {}
                tot_sh = (
                    (fin.get("shares") or {}).get("current")
                    if isinstance(fin.get("shares"), dict)
                    else fin.get("shares")
                )
            except Exception:  # noqa: BLE001 - a missing share count drops that leg
                tot_sh = None
            ft = _ft(None, float_sh)
            iwf = _iwf(float_sh, tot_sh)
            spread = _roll(closes)
            spread_bps = (spread * 1e4) if spread is not None else None
            lv = _lv(
                illiq,
                ft,
                None,  # days-to-absorb needs a liquidation block
                iwf=iwf,
                min_dollar_volume=self.config.get("min_dollar_volume"),
                spread_bps=spread_bps,
                max_spread_bps=self.config.get("max_spread_bps"),
            )
            return {
                "verdict": lv.get("verdict"),
                "illiq": illiq,
                "float_turnover": ft,
                "iwf": iwf,
                "dangers": lv.get("dangers"),
            }
        except Exception:  # noqa: BLE001 - gate must never crash
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

    def _basket_stress(self, ticker: str, shock: float = -0.10) -> float | None:
        """Book-level correlated stress loss for the configured basket, or None.

        Shares the basket-resolution logic with ``_basket_cvar``: fetches each
        basket name's daily returns, mixes them with the config weights, and
        measures the historical tail loss under a simultaneous ``shock``
        (``book_risk.book_correlated_stress``). Firms stress the whole book
        together (not single names), so this surfaces in the risk snapshot as
        "if the basket drops with correlated moves, the book loses X%".
        Returns None when the basket can't be resolved.
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
            from tradingagents.strategies.book_risk import book_correlated_stress

            return book_correlated_stress(returns_by_name, weights=weights, shock=shock)
        except Exception:  # noqa: BLE001 - fall back gracefully
            return None

    def _basket_drawdown(self, ticker: str) -> float | None:
        """Measured drawdown of the weighted book, or None (unknown never
        fails the gate).

        Resolves the configured risk basket exactly like ``_basket_cvar`` /
        ``_basket_stress`` (same names + weights + fetch pattern), mixes the
        daily returns and returns the max peak-to-trough drop of the equity
        curve (``book_risk.portfolio_drawdown``). This is the *measured* book
        drawdown - the governor compares it against ``risk_max_drawdown_pct``
        so a realized >limit drawdown actually blocks new risk. None when the
        basket is unconfigured or unresolvable.
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
            from tradingagents.strategies.book_risk import portfolio_drawdown

            return portfolio_drawdown(weights, returns_by_name)
        except Exception:  # noqa: BLE001 - fall back gracefully
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

    def _maybe_record_calibration(self, ticker, trade_date, alpha):
        """G2: stamp {confidence, won=delta_r>0} into calibration_ledger.jsonl.

        Wired at resolve time (a prior pending decision realized its return) so
        the PM's declared confidence is paired with a realized win/loss. The
        confidence is parsed from the decision text the PM already wrote
        (``**Confidence**: 0.72``); a missing/unparseable confidence skips the
        stamp (no fabrication). Mirrors decision_hardening_spec G2.
        """
        if not self.config.get("enable_calibration") or alpha is None:
            return
        try:
            pending = [
                e
                for e in self.memory_log.get_pending_entries()
                if e.get("ticker") == ticker and e.get("date") == trade_date
            ]
            if not pending:
                return
            import re as _re

            m = _re.search(
                r"\*\*Confidence\*\*:?\s*([0-9]*\.?[0-9]+)", pending[-1].get("decision", "")
            )
            if not m:
                return
            confidence = float(m.group(1))
            if not (0.0 <= confidence <= 1.0):
                return
            from tradingagents.strategies.calibration import record_calibration_entry

            base = Path(self.config.get("data_cache_dir", "~/.tradingagents")).expanduser()
            record_calibration_entry(
                str(base / "calibration_ledger.jsonl"),
                "market",
                ticker,
                trade_date,
                confidence,
                won=float(alpha) > 0,
            )
        except Exception as exc:
            logger.warning("calibration record skipped: %s", exc)

    def _agreement_from_state(self, final_state) -> "float | None":
        if not self.config.get("enable_agreement"):
            return None
        try:
            # Option-A hybrid: prefer the INDEPENDENT pre-debate agreement
            # (sampled before any cross-talk) — the debate transcript can
            # converge on a wrong answer under conformity pressure, so the
            # G1 contract multiplies by the uncontaminated number. Falls back
            # to parsing the debate history when the independent pass did not
            # run (flag off or a sampling failure).
            from tradingagents.agents.utils.independent_vote import (
                independent_agreement,
            )

            risk_stances = final_state.get("risk_independent_stances") or {}
            independent = independent_agreement(risk_stances)
            if independent is not None:
                return independent

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

    def _calibrated_p(self, decision_text: str = "", regime: str | None = None) -> "float | None":
        """G2: return the calibrated win-probability for the decision's declared
        confidence. Reads calibration_ledger.jsonl (written at resolve time),
        buckets the historical confidence->win-rate, and returns
        ``calibrated_confidence`` (identity when the bucket has < min_n samples
        or the ledger is empty). When ``regime`` is given, uses the regime-aware
        calibration (``fit_buckets_by_regime`` / ``calibrated_confidence_by_regime``,
        falling back to the ``_all`` table) so confidence is mapped per market
        regime instead of globally. None when calibration is disabled.
        """
        if not self.config.get("enable_calibration"):
            return None
        try:
            import re as _re

            m = _re.search(r"\*\*Confidence\*\*:?\s*([0-9]*\.?[0-9]+)", decision_text or "")
            if not m:
                return None
            declared = float(m.group(1))
            if not (0.0 <= declared <= 1.0):
                return None
            base = Path(self.config.get("data_cache_dir", "~/.tradingagents")).expanduser()
            cal_file = base / "calibration_ledger.jsonl"
            if not cal_file.exists():
                return None
            from tradingagents.strategies.calibration import (
                calibrated_confidence,
                calibrated_confidence_by_regime,
                fit_buckets,
                fit_buckets_by_regime,
            )

            rows = []
            import json as _json

            for ln in cal_file.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    rows.append(_json.loads(ln))
            min_n = int(self.config.get("calibration_min_n", 5))
            if regime:
                tables = fit_buckets_by_regime(rows)
                return calibrated_confidence_by_regime(
                    declared, tables, regime=regime, min_n=min_n
                )
            table = fit_buckets(rows)
            return calibrated_confidence(declared, table, min_n=min_n)
        except Exception:
            return None

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
