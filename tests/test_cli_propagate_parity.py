"""CLI / propagate state parity: one producer for the pre- and post-graph steps.

The interactive CLI builds its own state and streams the raw compiled graph
instead of going through ``propagate()``. It used to re-implement the graph's
setup by hand and had drifted out of parity:

* it seeded ``risk_context`` (#814) but never ``quant_scorecard``, so every
  interactive run's four analyst reports and ``run_card.json`` were missing the
  engine sections the batch path renders;
* it stopped after the strategy overlays, so an interactive run wrote no state
  log, no prediction-ledger row and no memory-log entry - its decisions never
  reached deferred reflection, and the memory log only ever held batch runs;
* it never set ``self.ticker``, which ``_log_state`` reads to name the log file.

Both paths now call ``TradingAgentsGraph.prepare_initial_state`` and
``.finalize_run``. These tests pin the behaviour those two producers owe every
entry point, so a future edit cannot make one path drift again without failing
here.
"""

from __future__ import annotations

import json


def _graph(tmp_path, monkeypatch, **overrides):
    """A hermetic TradingAgentsGraph: no LLM, no vendor reads, tmp output roots."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    class _L:
        def __init__(self, *a, **k):
            pass

        def get_llm(self):
            return _L()

        def invoke(self, *a, **k):
            return type("R", (), {"content": "x", "tool_calls": []})()

    monkeypatch.setattr("tradingagents.graph.trading_graph.create_llm_client", _L)

    cfg = dict(DEFAULT_CONFIG)
    cfg.update(
        {
            "results_dir": str(tmp_path / "logs"),
            "memory_log_path": str(tmp_path / "memory" / "trading_memory.md"),
            "data_cache_dir": str(tmp_path / "cache"),
            # Keep every seed step offline and inert unless a test opts in.
            "enable_risk_governor": False,
            "enable_strategy_overlays": False,
            "enable_prediction_ledger": False,
            "enable_computed_context": False,
            "enable_decision_packet": False,
            "enable_quant_scorecard": False,
            "checkpoint_enabled": False,
        }
    )
    cfg.update(overrides)
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    # Identity resolution and the close series are vendor reads; keep them offline.
    monkeypatch.setattr(
        ta, "resolve_instrument_context", lambda t, a="stock": f"ticker: {t}"
    )
    monkeypatch.setattr(ta, "_try_fetch_closes", lambda t: [])
    return ta


def _state(company="NVDA", date="2026-09-23"):
    """The minimum state ``_log_state`` reads, plus a decision to record."""
    return {
        "company_of_interest": company,
        "trade_date": date,
        "market_report": "market prose",
        "sentiment_report": "sentiment prose",
        "news_report": "news prose",
        "fundamentals_report": "fundamentals prose",
        "investment_debate_state": {
            "bull_history": "bull",
            "bear_history": "bear",
            "history": "hist",
            "current_response": "cur",
            "judge_decision": "judge",
        },
        "risk_debate_state": {
            "aggressive_history": "agg",
            "conservative_history": "con",
            "neutral_history": "neu",
            "history": "hist",
            "judge_decision": "rjudge",
        },
        "trader_investment_plan": "trader plan",
        "investment_plan": "manager plan",
        "final_trade_decision": "**Rating**: BUY\n\nBuy NVDA.",
    }


class TestPreGraphParity:
    def test_engine_scorecard_reaches_the_state_when_the_gate_is_on(
        self, tmp_path, monkeypatch
    ):
        """The defect: the CLI seeded risk_context but never quant_scorecard."""
        ta = _graph(tmp_path, monkeypatch, enable_quant_scorecard=True)
        import tradingagents.strategies.quant_scorecard as qs

        monkeypatch.setattr(
            qs,
            "quant_scorecard",
            lambda ticker, date, cfg: {"composite": 55.0, "engines": {}, "ticker": ticker},
        )

        state = ta.prepare_initial_state("NVDA", "2026-09-23")

        assert state["quant_scorecard"]["composite"] == 55.0

    def test_no_scorecard_key_at_all_when_the_gate_is_off(self, tmp_path, monkeypatch):
        """The documented guarantee: gate off => no key, not a null one.

        ResearchLayerWiring.md §9.3 - with the scorecard off the state must stay
        byte-identical to a pre-scorecard run, which is why the seed block
        writes nothing rather than writing None.
        """
        ta = _graph(tmp_path, monkeypatch, enable_quant_scorecard=False)

        assert "quant_scorecard" not in ta.prepare_initial_state("NVDA", "2026-09-23")

    def test_resolved_memory_entries_reach_the_state(self, tmp_path, monkeypatch):
        """The CLI passed no past_context, so its agents lost the memory log."""
        ta = _graph(tmp_path, monkeypatch)
        log = tmp_path / "memory" / "trading_memory.md"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            "[2026-09-01 | NVDA | BUY | +3.1% | +1.2% | 5d]\n\n"
            "DECISION:\nBought the breakout.\n\n"
            "REFLECTION:\nWorked as intended.\n\n"
            "<!-- ENTRY_END -->\n\n",
            encoding="utf-8",
        )

        state = ta.prepare_initial_state("NVDA", "2026-09-23")

        assert "Bought the breakout." in state["past_context"]
        assert "Worked as intended." in state["past_context"]

    def test_the_run_ticker_is_available_to_the_state_log(self, tmp_path, monkeypatch):
        """``_log_state`` names the log with ``self.ticker``.

        Only ``propagate()`` used to set it, so a CLI run left it None and the
        state log could not be written at all.
        """
        ta = _graph(tmp_path, monkeypatch)
        assert ta.ticker is None

        ta.prepare_initial_state("NVDA", "2026-09-23")

        assert ta.ticker == "NVDA"


class TestPostGraphParity:
    def test_the_decision_is_recorded_for_deferred_reflection(self, tmp_path, monkeypatch):
        """The CLI wrote no memory entry, so no interactive run ever resolved."""
        ta = _graph(tmp_path, monkeypatch)
        state = _state()

        ta.finalize_run(state, "NVDA", "2026-09-23")

        entries = ta.memory_log.load_entries()
        assert [e["ticker"] for e in entries] == ["NVDA"]
        assert entries[0]["pending"] is True
        assert "Buy NVDA." in entries[0]["decision"]

    def test_the_state_log_is_written(self, tmp_path, monkeypatch):
        ta = _graph(tmp_path, monkeypatch)
        state = _state()

        ta.finalize_run(state, "NVDA", "2026-09-23")

        log = (
            tmp_path / "logs" / "NVDA" / "TradingAgentsStrategy_logs"
            / "full_states_log_2026-09-23.json"
        )
        assert log.exists()
        assert json.loads(log.read_text(encoding="utf-8"))["market_report"] == "market prose"

    def test_the_returned_state_is_the_one_the_entry_point_saves(
        self, tmp_path, monkeypatch
    ):
        """finalize_run returns the post-overlay state, which callers then save.

        The recorded marker proves the overlay step ran on the returned object
        rather than on a discarded copy.
        """
        ta = _graph(tmp_path, monkeypatch)
        monkeypatch.setattr(
            ta, "_apply_strategy_overlays", lambda s, t: {**s, "strategy_overlays": {"ran": t}}
        )

        returned = ta.finalize_run(_state(), "NVDA", "2026-09-23")

        assert returned["strategy_overlays"] == {"ran": "NVDA"}

    def test_a_second_run_for_the_same_ticker_appends(self, tmp_path, monkeypatch):
        """One entry per run - the log is append-only, never overwritten."""
        ta = _graph(tmp_path, monkeypatch)

        ta.finalize_run(_state(), "NVDA", "2026-09-23")
        ta.finalize_run(_state(date="2026-09-24"), "NVDA", "2026-09-24")

        assert len(ta.memory_log.load_entries()) == 2
