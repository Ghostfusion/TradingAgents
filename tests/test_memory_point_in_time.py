"""Memory-log lessons must be point-in-time safe in a backtest (#1251).

``get_past_context`` used to return every resolved lesson regardless of the run
date, so a historical run could learn from an outcome that had not happened yet.
Resolved entries now record the date their outcome became known
(``resolved:YYYY-MM-DD``), and ``get_past_context(as_of=...)`` filters on it.
Legacy entries with no resolution date are excluded from a point-in-time query
(conservative migration) but still shown on a live, unfiltered run.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from tradingagents.agents.utils.memory import TradingMemoryLog

# Cold-start hazard: a file-level mark overrides ``--timeout``. Keep it high so
# a slow import/collection does not spuriously fail the suite.
pytestmark = pytest.mark.timeout(600)


def _make_log(tmp_path):
    return TradingMemoryLog({"memory_log_path": str(tmp_path / "mem.md")})


def _resolve(log, ticker, trade_date, resolution_date, reflection):
    """Store a pending decision then resolve it, stamping the outcome date."""
    log.store_decision(ticker, trade_date, f"Rating: Buy\n{reflection}")
    log.update_with_outcome(
        ticker,
        trade_date,
        0.05,
        0.02,
        5,
        reflection,
        resolution_date=resolution_date,
    )


def test_resolution_date_is_stored_and_parsed(tmp_path):
    log = _make_log(tmp_path)
    _resolve(log, "NVDA", "2026-01-05", "2026-01-10", "outcome known 01-10")

    entry = log.load_entries()[0]
    assert entry["resolved"] == "2026-01-10"
    assert "resolved:2026-01-10" in (tmp_path / "mem.md").read_text(encoding="utf-8")


def test_lesson_resolved_after_as_of_is_filtered_out(tmp_path):
    log = _make_log(tmp_path)
    # Decision on 01-05, outcome only knowable on 01-10.
    _resolve(log, "NVDA", "2026-01-05", "2026-01-10", "great trade")

    # A run as-of 01-07 must not see it (the outcome was still in the future)...
    assert log.get_past_context("NVDA", as_of="2026-01-07") == ""
    # ...but a run as-of 01-10 (the resolution date) and later does.
    assert "great trade" in log.get_past_context("NVDA", as_of="2026-01-10")
    assert "great trade" in log.get_past_context("NVDA", as_of="2026-02-01")


def test_lesson_resolved_before_as_of_is_kept(tmp_path):
    log = _make_log(tmp_path)
    _resolve(log, "NVDA", "2026-01-05", "2026-01-10", "old lesson")
    assert "old lesson" in log.get_past_context("NVDA", as_of="2026-03-01")


def test_legacy_entry_without_resolution_date(tmp_path):
    log = _make_log(tmp_path)
    # Simulate a pre-migration resolved entry: no resolution_date recorded.
    log.store_decision("NVDA", "2026-01-05", "Rating: Buy\nlegacy lesson")
    log.update_with_outcome("NVDA", "2026-01-05", 0.05, 0.02, 5, "legacy lesson")

    entry = log.load_entries()[0]
    assert entry["resolved"] is None

    # Conservative: excluded from a point-in-time query — it can't be proven to
    # predate the as_of date...
    assert log.get_past_context("NVDA", as_of="2026-06-01") == ""
    # ...but still available on a live (unfiltered) run.
    assert "legacy lesson" in log.get_past_context("NVDA")


def test_as_of_none_is_unfiltered_live_behavior(tmp_path):
    log = _make_log(tmp_path)
    _resolve(log, "NVDA", "2026-01-05", "2026-01-10", "same lesson")
    _resolve(log, "AAPL", "2026-01-06", "2026-01-11", "cross lesson")

    live = log.get_past_context("NVDA")
    assert "same lesson" in live
    assert "cross lesson" in live


def test_cross_ticker_lessons_are_gated_too(tmp_path):
    log = _make_log(tmp_path)
    _resolve(log, "AAPL", "2026-01-05", "2026-01-10", "cross lesson")

    # Querying a different ticker as-of before resolution: no cross leak.
    assert log.get_past_context("NVDA", as_of="2026-01-07") == ""
    assert "cross lesson" in log.get_past_context("NVDA", as_of="2026-01-10")


def test_graph_as_of_gates_backtest_but_not_live():
    """The graph filters only for a past trade date; live passes None (#1251)."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    graph = object.__new__(TradingAgentsGraph)
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    past = "2024-01-01"
    future = (_dt.datetime.now() + _dt.timedelta(days=30)).strftime("%Y-%m-%d")

    assert graph._memory_as_of(past) == past  # backtest -> filter on trade date
    assert graph._memory_as_of(today) is None  # live -> no filter
    assert graph._memory_as_of(future) is None  # future-dated run -> no filter
