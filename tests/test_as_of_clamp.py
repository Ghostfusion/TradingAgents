"""As-of clamp tests: a model-supplied date can never reach past the run date.

Covers the pure helpers that own the look-ahead rule
(``tradingagents.dataflows.date_window``) and the end-to-end wiring into the
dated agent tool leaves (the OHLCV path is the one where the leak was real).
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils import core_stock_tools
from tradingagents.dataflows.date_window import (
    as_of,
    as_of_window,
    get_run_trade_date,
    set_run_trade_date,
)

pytestmark = pytest.mark.timeout(600)


def test_run_date_publishes():
    set_run_trade_date("2024-05-10")
    assert get_run_trade_date() == "2024-05-10"


def test_run_date_reset_between_tests():
    # The conftest ``_isolate_config`` autouse fixture must have cleared the run
    # date the previous test published, or it would leak into other suites.
    assert get_run_trade_date() == ""


def test_as_of_clamps_future_date_to_run_date():
    assert as_of("2024-12-31", "2024-05-10") == "2024-05-10"
    # On or before the run date is returned unchanged.
    assert as_of("2024-05-10", "2024-05-10") == "2024-05-10"
    assert as_of("2024-01-02", "2024-05-10") == "2024-01-02"


def test_as_of_window_clamps_end_and_start():
    assert as_of_window("2024-01-01", "2024-12-31", "2024-05-10") == (
        "2024-01-01",
        "2024-05-10",
    )
    # A fully-future window collapses onto the run date.
    assert as_of_window("2025-01-01", "2025-12-31", "2024-05-10") == (
        "2024-05-10",
        "2024-05-10",
    )


def test_as_of_empty_or_unparseable_run_date_is_noop():
    for bad in ("", None, "not-a-date", "2024-13-40"):
        assert as_of("2024-12-31", bad) == "2024-12-31"
        assert as_of_window("2024-01-01", "2024-12-31", bad) == (
            "2024-01-01",
            "2024-12-31",
        )
    # An unparseable / empty bound is likewise returned untouched.
    assert as_of("", "2024-05-10") == ""
    assert as_of(None, "2024-05-10") is None


def test_as_of_window_never_inverts_when_start_is_after_run_date():
    start, end = as_of_window("2024-12-01", "2024-01-01", "2024-05-10")
    assert start <= end
    assert (start, end) == ("2024-01-01", "2024-01-01")


def test_get_stock_data_leaf_clamps_end_to_run_date(monkeypatch):
    seen = {}

    def fake_route_to_vendor(name, symbol, start_date, end_date):
        seen.update(name=name, symbol=symbol, start_date=start_date, end_date=end_date)
        return "stub"

    monkeypatch.setattr(core_stock_tools, "route_to_vendor", fake_route_to_vendor)

    set_run_trade_date("2024-05-10")
    out = core_stock_tools.get_stock_data.invoke(
        {"symbol": "AAPL", "start_date": "2024-01-01", "end_date": "2024-12-31"}
    )

    assert out == "stub"
    assert seen["name"] == "get_stock_data"
    assert seen["symbol"] == "AAPL"
    assert seen["start_date"] == "2024-01-01"
    assert seen["end_date"] == "2024-05-10"


def test_get_stock_data_leaf_is_noop_without_run_date(monkeypatch):
    seen = {}

    def fake_route_to_vendor(name, symbol, start_date, end_date):
        seen.update(start_date=start_date, end_date=end_date)
        return "stub"

    monkeypatch.setattr(core_stock_tools, "route_to_vendor", fake_route_to_vendor)

    set_run_trade_date("")
    core_stock_tools.get_stock_data.invoke(
        {"symbol": "AAPL", "start_date": "2024-01-01", "end_date": "2024-12-31"}
    )

    assert seen["start_date"] == "2024-01-01"
    assert seen["end_date"] == "2024-12-31"
