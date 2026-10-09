# TradingAgents/graph/propagation.py

from typing import Any

from tradingagents.agents.utils.agent_states import (
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        asset_type: str = "stock",
        past_context: str = "",
        instrument_context: str = "",
    ) -> dict[str, Any]:
        """Create the initial state for the agent graph.

        ``instrument_context`` is the deterministic ticker-identity string
        resolved once at run start (see
        ``TradingAgentsGraph.resolve_instrument_context``). When empty, agents
        fall back to ticker-only context via
        ``get_instrument_context_from_state``.

        Also publishes the run's ``trade_date`` for the dated tool leaves
        (:mod:`tradingagents.dataflows.date_window`) - this is the single
        pre-graph point every entry point (``propagate``/``_run_graph`` and the
        interactive CLI, both via ``prepare_initial_state``) runs, so a
        model-supplied date can never reach past the run date. Thread-scoped
        via contextvars; an empty date leaves the clamp a no-op.
        """
        from tradingagents.dataflows.date_window import set_run_clock, set_run_trade_date
        from tradingagents.strategies.market_session import to_exchange_time

        set_run_trade_date(trade_date)
        # Publish the run's wall-clock instant too, beside the date: the volume
        # leaves read it to annualise a FORMING bar's volume
        # (``market_session.forming_bar_progress``). A live run - the run date is
        # today - gets the real instant; a historical run publishes None, which
        # clears it, so a backtest is never adjusted by the present time of day.
        # The reader takes the published wall clock AS ET, so the machine's own
        # zone must be converted here: ``now().astimezone()`` alone made a
        # Central-time box read the session 60 minutes young (0.2872 where ET
        # says 0.4410), annualising every forming bar's volume ~1.5x high.
        _today = to_exchange_time()
        set_run_clock(_today if str(trade_date)[:10] == _today.date().isoformat() else None)
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "asset_type": asset_type,
            "instrument_context": instrument_context,
            "trade_date": str(trade_date),
            "past_context": past_context,
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
        }

    def get_graph_args(self, callbacks: list | None = None) -> dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }
