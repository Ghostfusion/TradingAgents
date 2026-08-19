"""Momentum signals: 5-pillar filter, first-pullback, session flags, journal.

Phases 1-4 of the Warrior Trading momentum adaptation:
  - phase 1: gap/float pillars honest (None = unknown, not a failure)
  - phase 2: volume-color + topping-tail rules in first_pullback
  - phase 3: session walk-away gates + JSONL journal analytics
  - phase 4: intraday pullback (session VWAP) + psychological levels
"""


import os

import pytest

from tradingagents.strategies.momentum import (
    ema9,
    first_pullback,
    intraday_pullback,
    past_optimal_window,
    pillars,
    psych_level,
    rvol,
    session_flags,
    vwap,
)

# Keep unit tests fully offline: no float lookups, no intraday bar calls.
os.environ.setdefault("TRADINGAGENTS_MOMENTUM_OFFLINE", "1")
os.environ.setdefault("TRADINGAGENTS_MOMENTUM_NO_INTRADAY", "1")


def bars_from(rows):
    """rows: list of (open, close, high, low, volume) -> o/c/h/l/v lists."""
    o = [r[0] for r in rows]
    c = [r[1] for r in rows]
    h = [r[2] for r in rows]
    lo = [r[3] for r in rows]
    v = [r[4] for r in rows]
    return o, c, h, lo, v


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


def test_pillars_unknowns_are_none_not_false():
    """Phase 1: missing data yields None so scaffolds never fail scans."""
    p = pillars(close=15.0)
    assert p["float"] is None
    assert p["gap"] is None  # no prev close/open -> unknown, not a non-gapper
    assert p["rvol"] is None and p["high_volume"] is None
    assert p["price_band"] is True  # close known -> measurable


def test_pillars_known_failures_are_false():
    p = pillars(close=25.0, day_volume=1000, prev_close=10.0, day_open=10.0,
                rv=1.0, float_shares=50_000_000)
    assert p["price_band"] is False
    assert p["gap"] is False
    assert p["float"] is False
    assert p["rvol"] is False and p["high_volume"] is False


def test_first_pullback_basic_shape():
    # No strong pattern on a steady ramp: candidate flag present but boolean.
    closes = [100.0 + 0.3 * i for i in range(60)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    vols = [1e6] * 60
    fp = first_pullback(closes, highs, lows, vols)
    assert "candidate" in fp and "rr" in fp and "stop" in fp
    assert isinstance(fp["candidate"], bool)
    # Without opens the extra rules are unknown, never failures.
    assert fp["volume_ok"] is None and fp["tail_ok"] is None


def test_volume_rule_light_red_heavy_green():
    """Phase 2: red candles must print light volume vs green candles."""
    o, c, h, lo, v = bars_from([
        (100.0, 100.2, 101.0, 99.6, 1.0e6),
        (100.1, 101.0, 101.5, 100.0, 1.0e6),
        (99.0, 99.2, 99.8, 98.8, 1.0e6),
        (99.2, 99.8, 100.1, 99.1, 1.0e6),
        (99.8, 99.9, 100.3, 99.5, 1.0e6),
        (99.9, 100.0, 100.4, 99.6, 1.0e6),
        (101.0, 100.6, 101.2, 100.3, 0.3e6),   # red, light
        (100.6, 101.8, 102.0, 100.5, 2.0e6),   # green, heavy
        (101.8, 101.9, 102.2, 101.2, 0.5e6),   # red, light
        (101.4, 103.0, 103.2, 101.3, 2.4e6),   # green, heavy
        (103.0, 102.6, 103.2, 102.4, 0.4e6),   # red, light
        (102.6, 104.0, 104.2, 102.5, 2.6e6),   # green, heavy
    ])
    fp = first_pullback(c, h, lo, v, opens=o, window=6)
    assert fp["volume_ok"] is True
    assert fp["tail_ok"] is not None


def test_volume_rule_rejects_heavy_red_printing():
    """Phase 2: heavy red prints (sell pressure) fail the setup."""
    o, c, h, lo, v = bars_from([
        (100.0, 100.2, 101.0, 99.6, 1.0e6),
        (100.1, 101.0, 101.5, 100.0, 1.0e6),
        (99.0, 99.2, 99.8, 98.8, 1.0e6),
        (99.2, 99.8, 100.1, 99.1, 1.0e6),
        (99.8, 99.9, 100.3, 99.5, 1.0e6),
        (99.9, 100.0, 100.4, 99.6, 1.0e6),
        (101.0, 100.6, 101.2, 100.3, 2.0e6),   # red, heavy
        (100.6, 101.8, 102.0, 100.5, 0.5e6),   # green, light
        (101.8, 101.9, 102.2, 101.2, 2.4e6),   # red, heavy
        (101.4, 103.0, 103.2, 101.3, 0.6e6),   # green, light
        (103.0, 102.6, 103.2, 102.0, 2.2e6),   # red, heavy
        (102.6, 104.0, 104.2, 102.5, 0.7e6),   # green, light
    ])
    fp = first_pullback(c, h, lo, v, opens=o, window=6)
    assert fp["volume_ok"] is False
    assert fp["candidate"] is False


def test_first_pullback_rejects_topping_tail():
    """Phase 2: a prominent upper wick (topping tail) fails the setup."""
    rows = [
        (100.0, 100.2, 101.0, 99.6, 1.0e6),
        (100.1, 101.0, 101.5, 100.0, 1.0e6),
        (99.0, 99.2, 99.8, 98.8, 1.0e6),
        (99.2, 99.8, 100.1, 99.1, 1.0e6),
        (99.8, 99.9, 100.3, 99.5, 1.0e6),
        (99.9, 100.0, 100.4, 99.6, 1.0e6),
        (101.0, 100.6, 101.2, 100.3, 1.0e6),
        (100.6, 101.8, 102.0, 100.5, 1.0e6),
        (101.8, 101.9, 102.2, 101.2, 1.0e6),
        # giant upper wick: open 101.4, close 103.0, high 112.0 (tail ~8.6x body)
        (101.4, 103.0, 112.0, 101.3, 1.0e6),
        (103.0, 102.6, 103.2, 102.4, 1.0e6),
        (102.6, 104.0, 104.2, 102.5, 1.0e6),
    ]
    o, c, h, lo, v = bars_from(rows)
    fp = first_pullback(c, h, lo, v, opens=o, window=6)
    assert fp["tail_ok"] is False
    assert fp["candidate"] is False


def test_session_flags():
    fl = session_flags(peak_pnl=0.10, current_pnl=0.03)
    assert fl["giveback_50"] is True
    fl2 = session_flags(peak_pnl=0.10, current_pnl=0.09)
    assert fl2["giveback_50"] is False
    fl3 = session_flags(peak_pnl=None, current_pnl=-0.05, max_daily_loss=0.03)
    assert fl3["max_daily_loss_hit"] is True


def test_session_flags_walk_away_rules():
    """Phase 3: optimal-window and no-setup gates fold into walk_away."""
    fl = session_flags(peak_pnl=None, current_pnl=None,
                       past_optimal_window=True, no_quality_setups=True)
    assert fl["past_optimal_window"] is True
    assert fl["no_quality_setups"] is True
    assert fl["walk_away"] is True
    fl2 = session_flags(peak_pnl=None, current_pnl=None,
                        past_optimal_window=False, no_quality_setups=False)
    assert fl2["walk_away"] is False
    # Unknowns never force a walk-away.
    fl3 = session_flags(peak_pnl=None, current_pnl=None)
    assert fl3["past_optimal_window"] is None
    assert fl3["walk_away"] is False


def test_past_optimal_window():
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    # 09:00 UTC in January == 04:00 ET -> before the 10:00 ET cutoff.
    assert past_optimal_window(base) is False
    # 15:00 UTC == 10:00 ET -> at the boundary -> past/at window end -> True.
    assert past_optimal_window(base + timedelta(hours=6)) is True
    # 17:00 UTC == 12:00 ET -> after the cutoff.
    assert past_optimal_window(base + timedelta(hours=8)) is True


def test_psych_level():
    pl = psych_level(7.2)
    assert pl["above"] == 7.5 and pl["below"] == 7.0
    assert pl["dist_pct"] is not None and pl["dist_pct"] > 0
    assert psych_level(8.0)["above"] == 8.0  # whole dollar is a level
    assert psych_level(0)["above"] is None


def test_intraday_pullback_bars():
    """Phase 4: 1m/5m bars -> session VWAP hold + pattern flags."""
    bars = []
    price = 100.0
    for i in range(40):
        bars.append({"o": price, "h": price + 0.2, "l": price - 0.2,
                     "c": price, "v": 10_000 + i * 100, "vw": price})
        price += 0.05
    fp = intraday_pullback(bars)
    assert fp["bar_count"] == 40
    assert fp["session_vwap"] is not None
    assert fp["holds_session_vwap"] is not None
    assert "candidate" in fp
    empty = intraday_pullback([])
    assert empty["candidate"] is False


def test_market_tool_reports_scan():
    from unittest import mock

    from tradingagents.agents.utils.momentum_tools import get_momentum_scan

    bars = [{"t": f"d{i}", "o": 15.0 + i * 0.01, "h": 15.1, "l": 14.9,
             "c": 15.0 + i * 0.01, "v": 1_000_000} for i in range(60)]
    with mock.patch("tradingagents.dataflows.alpaca.get_bars", return_value=bars):
        out = get_momentum_scan.func("AAPL")
    assert "momentum scan AAPL:" in out
    assert "pillars:" in out and "setup=" in out
    assert "float_ok=" in out  # phase 1: float pillar surfaced
    assert "volrule=" in out and "tailok=" in out  # phase 2 flags surfaced


def test_journal_roundtrip_and_stats(tmp_path):
    """Phase 3: JSONL journal + win/loss analytics."""
    from tradingagents.strategies.journal import (
        format_summary,
        momentum_stats,
        record_momentum_trade,
    )

    j = str(tmp_path / "mom.jsonl")
    record_momentum_trade(
        j, "AAB", pillars={"rvol": True, "gap": False, "float": None},
        pullback={"candidate": True, "rr": 2.4, "stop": 8.1},
        session={"giveback_50": False, "walk_away": False},
        price=8.8, exit_class="win")
    record_momentum_trade(
        j, "BAB", pillars={"rvol": True, "gap": True, "float": True},
        pullback={"candidate": True, "rr": 3.1, "stop": 8.0},
        session={"giveback_50": True, "walk_away": True},
        price=8.9, exit_class="loss", fomo=True)
    stats = momentum_stats(j)
    assert stats["trades"] == 2
    assert stats["candidates"] == 2
    assert stats["win_rate"] == 0.5
    assert stats["avg_rr"] == pytest.approx(2.75)
    assert stats["pillar_pass_rate"]["rvol"] == 1.0
    assert stats["pillar_pass_rate"]["gap"] == 0.5
    assert stats["fomo_count"] == 1
    assert stats["session_flag_hits"]["giveback_50"] == 1
    text = format_summary(stats)
    assert "win_rate=50.0" in text and "trades=2" in text
