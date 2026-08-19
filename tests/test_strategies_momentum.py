"""Momentum signals: 5-pillar filter, first-pullback, session flags."""

import pytest

from tradingagents.strategies.momentum import (
    rvol, ema9, vwap, pillars, first_pullback, session_flags,
)


def test_rvol_50d():
    vols = [1_000_000.0] * 50 + [10_000_000.0]
    assert rvol(vols) and rvol(vols) > 8.0
    assert rvol([1.0]) is None


def test_ema9_and_vwap():
    series = [100.0 + 0.5 * i for i in range(30)]
    assert ema9(series) and ema9(series) > 100.0
    vw = vwap(series, [100.0] * 30)
    assert vw and 100.0 < vw < 120.0


def test_pillars_pass_set():
    p = pillars(close=15.0, day_volume=5_000_000, prev_close=14.0, day_open=14.5,
                rv=5.0, float_shares=4_000_000)
    assert p["rvol"] and p["high_volume"] and p["gap"] and p["price_band"] and p["float"]


def test_pillars_unknowns_none():
    p = pillars(close=15.0)
    assert p["float"] is None and p["gap"] is False  # no prev -> not gapping


def test_first_pullback_basic_shape():
    # No strong pattern on a steady ramp: candidate flag present but boolean.
    closes = [100.0 + 0.3 * i for i in range(60)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    vols = [1e6] * 60
    fp = first_pullback(closes, highs, lows, vols)
    assert "candidate" in fp and "rr" in fp and "stop" in fp
    assert isinstance(fp["candidate"], bool)


def test_market_tool_reports_scan():
    from unittest import mock

    from tradingagents.agents.utils.momentum_tools import get_momentum_scan

    bars = [{"t": f"d{i}", "o": 15.0 + i * 0.01, "h": 15.1, "l": 14.9,
             "c": 15.0 + i * 0.01, "v": 1_000_000} for i in range(60)]
    with mock.patch("tradingagents.dataflows.alpaca.get_bars", return_value=bars):
        out = get_momentum_scan.func("AAPL")
    assert "momentum scan AAPL:" in out
    assert "pillars:" in out and "setup=" in out


def test_session_flags():
    fl = session_flags(peak_pnl=0.10, current_pnl=0.03)
    assert fl["giveback_50"] is True
    fl2 = session_flags(peak_pnl=0.10, current_pnl=0.09)
    assert fl2["giveback_50"] is False
    fl3 = session_flags(peak_pnl=None, current_pnl=-0.05, max_daily_loss=0.03)
    assert fl3["max_daily_loss_hit"] is True
