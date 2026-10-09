"""Hermetic tests for the new technical factors (Aroon, Fisher, Chaikin,
Elder-Ray, Supertrend, volume profile) and the market-session module
(opening range, gap type, order imbalance, premarket liquidity, post-close
confirmation). Pure/offline; no network.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradingagents.dataflows import date_window  # noqa: E402
from tradingagents.graph.propagation import Propagator  # noqa: E402
from tradingagents.strategies import (  # noqa: E402
    market_session as ms,
    momentum,
    technical_factors as tf,
    value_dip,
)

pytestmark = pytest.mark.timeout(120)


def _uptrend(n=60):
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    vols = [1_000_000.0] * n
    return closes, highs, lows, vols


def _random_walk(seed=7, n=80):
    import random

    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1 + rng.uniform(-0.02, 0.02)))
    highs = [c * (1 + rng.uniform(0.005, 0.02)) for c in closes]
    lows = [c * (1 - rng.uniform(0.005, 0.02)) for c in closes]
    vols = [rng.uniform(500_000, 2_000_000) for _ in closes]
    return closes, highs, lows, vols


# ---------------------------------------------------------------------------
# Technical factors
# ---------------------------------------------------------------------------


def test_aroon_uptrend():
    _, highs, lows, _ = _uptrend()
    r = tf.aroon(highs, lows)
    assert r["aroon_up"] == 100.0
    assert r["aroon_down"] == 0.0
    assert r["verdict"] == "uptrend"


def test_aroon_insufficient():
    r = tf.aroon([1, 2], [1, 2])
    assert r["aroon_up"] is None and r["aroon_down"] is None


def test_fisher_transform_returns_values():
    closes, _, _, _ = _random_walk()
    r = tf.fisher_transform(closes)
    assert r["fisher"] is not None
    assert r["trigger"] is not None
    assert r["verdict"] in ("up", "down", "reversal-up", "reversal-down")


def test_fisher_insufficient():
    r = tf.fisher_transform([1, 2])
    assert r["fisher"] is None


def test_chaikin_oscillator_asymmetric():
    closes, highs, lows, vols = _random_walk()
    v = tf.chaikin_oscillator(highs, lows, closes, vols)
    assert v is not None
    assert isinstance(v, float)


def test_chaikin_insufficient():
    assert tf.chaikin_oscillator([1], [1], [1], [1]) is None


def test_elder_ray_returns_powers():
    closes, highs, lows, _ = _random_walk()
    r = tf.elder_ray(highs, lows, closes)
    assert r["bull_power"] is not None
    assert r["bear_power"] is not None
    assert r["verdict"] in ("buying-pressure", "selling-pressure", "mixed-bull", "mixed-bear")


def test_elder_ray_insufficient():
    r = tf.elder_ray([1], [1], [1])
    assert r["bull_power"] is None


def test_supertrend_returns_line():
    closes, highs, lows, _ = _random_walk()
    r = tf.supertrend(highs, lows, closes)
    assert r["line"] is not None
    assert r["direction"] in ("up", "down")


def test_supertrend_insufficient():
    r = tf.supertrend([1], [1], [1])
    assert r["line"] is None


def test_volume_profile_returns_poc():
    closes, _, _, vols = _random_walk()
    r = tf.volume_profile(closes, vols)
    assert r["poc"] is not None
    assert r["value_area_high"] is not None
    assert r["value_area_low"] is not None
    assert r["value_area_low"] <= r["poc"] <= r["value_area_high"]


def test_volume_profile_insufficient():
    r = tf.volume_profile([1], [1])
    assert r["poc"] is None


# ---------------------------------------------------------------------------
# Market session
# ---------------------------------------------------------------------------


def test_opening_range_up_breakout():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 105])
    assert r["or_high"] == 104.0
    assert r["or_low"] == 96.0
    assert r["breakout"] == "up"
    assert r["stop"] == 96.0
    assert r["target"] == 120.0  # or_high + 2*width


def test_opening_range_down_breakout():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 95])
    assert r["breakout"] == "down"
    assert r["stop"] == 104.0
    assert r["target"] == 80.0


def test_opening_range_inside():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 100])
    assert r["breakout"] is None


def test_opening_range_insufficient():
    r = ms.opening_range([101], [99])
    assert r["or_high"] is None


def test_gap_type_breakaway():
    # A real OPEN gap (102.0 open vs 100.0 prev close = +2%) on 3x volume -> breakaway.
    closes = [100.0] * 25 + [103.0]
    opens = [100.0] * 25 + [102.0]
    highs = [101.0] * 25 + [104.0]
    lows = [99.0] * 25 + [102.0]
    vols = [1_000_000.0] * 25 + [3_000_000.0]
    r = ms.gap_type(closes, opens, highs, lows, vols)
    assert r["type"] == "breakaway"
    assert r["gap_pct"] == round((102.0 - 100.0) / 100.0, 6)  # open-gap, not close-gap
    assert r["fill_probability"] is not None


def test_gap_type_uses_real_open_not_close_proxy():
    """SKHY 2026-09-09 review-loop bug: the gap must be (open_t - close_t-1),
    NOT (close_t - close_t-1). A +7.32% session change must NOT be labeled an
    overnight gap when the actual open was near-flat."""
    closes = [100.0] * 25 + [107.3]
    opens = [100.0] * 25 + [100.4]   # real open: +0.4% gap
    highs = [101.0] * 25 + [108.0]
    lows = [99.0] * 25 + [100.0]
    vols = [1_000_000.0] * 26
    r = ms.gap_type(closes, opens, highs, lows, vols)
    assert r["type"] == "common"          # +0.4% gap, not exhaustion
    assert abs(r["gap_pct"] - (100.4 - 100.0) / 100.0) < 1e-6


def test_gap_type_common():
    closes = [100.0] * 25 + [100.5]
    opens = [100.0] * 25 + [100.2]  # +0.2% open gap
    highs = [101.0] * 25 + [101.0]
    lows = [99.0] * 25 + [99.5]
    vols = [1_000_000.0] * 26
    r = ms.gap_type(closes, opens, highs, lows, vols)
    assert r["type"] == "common"
    assert r["fill_probability"] >= 0.5


def test_gap_type_insufficient():
    r = ms.gap_type([1, 2], [1, 2], [1, 2], [1, 2], [1, 2])
    assert r["type"] is None


def _gap_history(n_bars: int = 40, fill_at: tuple = ()) -> tuple:
    """A rising series that gaps up +0.5% (class `common`) every bar.

    Bars in ``fill_at`` dip back through the prior close on the gap day, so
    they FILL; every other bar's low stays above the prior close for the whole
    horizon, so it never fills. Returns (closes, opens, highs, lows, volumes).
    """
    closes, opens, highs, lows = [100.0], [100.0], [100.0], [100.0]
    for i in range(1, n_bars):
        prev = closes[-1]
        c = prev * 1.005
        closes.append(c)
        opens.append(c)
        lows.append(prev * (0.999 if i in fill_at else 1.002))
        highs.append(c * 1.002)
    return closes, opens, highs, lows, [1_000_000.0] * n_bars


def test_gap_fill_statistics_are_measured_not_constant():
    """Regression: fill_probability/days_to_fill were literal per-class
    constants (0.8/0.3/0.4/0.6) printed as if measured. They are now measured
    over the same-class gaps in the history the caller passed, and the basis
    says which one was used."""
    fills = (22, 24, 26, 28, 30, 32)
    closes, opens, highs, lows, vols = _gap_history(fill_at=fills)
    r = ms.gap_type(closes, opens, highs, lows, vols)
    assert r["type"] == "common"
    assert r["fill_basis"].startswith("measured"), r["fill_basis"]
    assert r["fill_sample"] >= ms.GAP_FILL_MIN_SAMPLE
    # the scan covers bars [20, 38]; exactly the 6 marked bars filled, and all
    # of them on the gap day
    expected = len(fills) / (len(closes) - 2 - 20 + 1)
    assert r["fill_probability"] == pytest.approx(round(expected, 4))
    assert r["days_to_fill"] == 0
    # a measured 0% is reachable - the constant table could never produce it
    closes2, opens2, highs2, lows2, vols2 = _gap_history(fill_at=())
    r2 = ms.gap_type(closes2, opens2, highs2, lows2, vols2)
    assert r2["fill_basis"].startswith("measured")
    assert r2["fill_probability"] == 0.0
    assert r2["days_to_fill"] is None


def test_gap_fill_statistics_labelled_heuristic_when_the_sample_is_thin():
    """Below GAP_FILL_MIN_SAMPLE same-class gaps the lookup heuristic is used,
    and the basis says so - it must never be quoted as a measurement."""
    closes, opens, highs, lows, vols = _gap_history(n_bars=26, fill_at=(22,))
    r = ms.gap_type(closes, opens, highs, lows, vols)
    assert r["type"] == "common"
    assert r["fill_sample"] < ms.GAP_FILL_MIN_SAMPLE
    assert r["fill_basis"].startswith("heuristic")
    assert r["fill_probability"] == ms._GAP_HEURISTIC["common"][0]
    assert r["days_to_fill"] == ms._GAP_HEURISTIC["common"][1]


def test_order_imbalance_buy_heavy():
    r = ms.order_imbalance(0.5, -0.2)
    assert r["verdict"] == "buy-heavy"
    assert r["ratio"] > 0.3


def test_order_imbalance_sell_heavy():
    r = ms.order_imbalance(-0.5, 0.2)
    assert r["verdict"] == "sell-heavy"


def test_order_imbalance_balanced():
    r = ms.order_imbalance(0.1, -0.1)
    assert r["verdict"] == "balanced"


def test_order_imbalance_none():
    r = ms.order_imbalance(None, None)
    assert r["verdict"] is None


def test_premarket_liquidity_thin():
    r = ms.premarket_liquidity(50_000, 1_000_000)
    assert r["verdict"] == "thin"
    assert r["ratio"] == 0.05


def test_premarket_liquidity_liquid():
    r = ms.premarket_liquidity(200_000, 1_000_000)
    assert r["verdict"] == "liquid"


def test_premarket_liquidity_none():
    r = ms.premarket_liquidity(None, None)
    assert r["verdict"] is None


def test_post_close_stopped_out():
    r = ms.post_close_confirmation(95, 100, 120)
    assert r["verdict"] == "stopped-out"
    assert r["action"] == "exit"


def test_post_close_target_hit():
    r = ms.post_close_confirmation(125, 100, 120)
    assert r["verdict"] == "target-hit"
    assert r["action"] == "take-profit"


def test_post_close_holding():
    r = ms.post_close_confirmation(110, 100, 120)
    assert r["verdict"] == "holding"
    assert r["action"] == "hold"


def test_post_close_none():
    r = ms.post_close_confirmation(None, 100, 120)
    assert r["verdict"] is None


# ---------------------------------------------------------------------------
# RISK-3 / RISK-8 - the per-class gap-fill outcome sample
# ---------------------------------------------------------------------------


def test_gap_fill_sample_is_per_class_and_reports_provenance():
    """The sample producer behind gap_type: one entry per gap class, its
    empirical fill rate and median days-to-fill, and the bars it looked at.
    A class with no occurrence reports None - never 0, never the heuristic."""
    closes, opens, highs, lows, vols = _gap_history(fill_at=(22, 24, 26, 28, 30, 32))
    s = ms.gap_fill_sample(closes, opens, highs, lows, vols)
    assert s["bars"] == len(closes)
    assert s["lookback"] == 20
    assert s["horizon"] == ms.GAP_FILL_HORIZON
    common = s["common"]
    assert common["sample"] == 19          # range(20, len-1) over 40 bars
    assert common["filled"] == 6
    assert common["fill_probability"] == pytest.approx(6 / 19)
    assert common["median_days"] == 0      # every fill was on the gap day
    for cls in ("breakaway", "exhaustion", "runaway"):
        assert s[cls]["sample"] == 0
        assert s[cls]["fill_probability"] is None
        assert s[cls]["median_days"] is None
    # nothing filled at all is a measured 0.0 with no day count - the constant
    # table could never produce either
    never = ms.gap_fill_sample(*_gap_history(fill_at=()))
    assert never["common"]["fill_probability"] == 0.0
    assert never["common"]["median_days"] is None


def test_gap_fill_sample_spans_the_whole_history_it_is_given():
    """The sample is whatever history the caller passes. The leaf feeds the
    stored OHLCV cache rather than the 320-bar default precisely here: a class
    count has to clear GAP_FILL_MIN_SAMPLE, and it rises with the window."""
    short = ms.gap_fill_sample(*_gap_history(n_bars=60))
    long = ms.gap_fill_sample(*_gap_history(n_bars=400))
    assert short["common"]["sample"] == 39
    assert long["common"]["sample"] == 379
    assert long["bars"] == 400


def test_gap_fill_sample_empty_history_reports_no_measurement():
    s = ms.gap_fill_sample([], [], [], [], [])
    assert s["bars"] == 0
    assert s["common"]["sample"] == 0
    assert s["common"]["fill_probability"] is None


# ---------------------------------------------------------------------------
# Partial-session volume (the run clock)
#
# A forming bar's volume divided by a full-day mean reads LOW by the share of
# the session elapsed, so every RVOL read is annualised by that share. The
# adjustment is OFF unless a run clock was published inside a live session -
# which is why these tests publish one explicitly and clear it in a finally.
# ---------------------------------------------------------------------------

_ET = timezone(timedelta(hours=-4))


def _et(hour, minute, day=8):
    return datetime(2026, 10, day, hour, minute, tzinfo=_ET)


def _exchange_zone():
    """ET, or None when no tz database is reachable.

    ``zoneinfo`` needs one: Windows ships none and relies on the ``tzdata``
    package (pandas pulls it in there), Linux/macOS have the system database.
    Returning None here - rather than skipping inside the ``except`` - is what
    lets the two conversion tests below SKIP on a box that has neither; the
    code's own fallback is a fixed -05:00, an hour off, which is not what they
    assert.
    """
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001 - optional tzdata; documented fallback
        return None


def test_session_progress_reads_the_regular_window():
    assert ms._session_progress(_et(9, 0))["fraction"] == 0.0  # pre-open
    mid = ms._session_progress(_et(12, 0))
    assert mid["label"] == "regular" and mid["open"] is True
    assert mid["minutes_elapsed"] == 150
    assert mid["fraction"] == pytest.approx(150 / 390, rel=1e-4)
    post = ms._session_progress(_et(18, 0))
    assert post["label"] == "post" and post["fraction"] == 1.0
    sat = ms._session_progress(_et(12, 0, day=10))
    assert sat["label"] == "weekend" and sat["fraction"] == 1.0


def test_forming_bar_progress_is_a_no_op_without_a_published_clock():
    date_window.set_run_clock(None)
    assert ms.forming_bar_progress() == 1.0
    assert momentum.rvol([1000.0] * 50 + [400.0]) == pytest.approx(0.4)


def test_forming_bar_progress_annualises_inside_a_live_session():
    date_window.set_run_clock(_et(15, 23))  # 353 of 390 minutes
    try:
        assert ms.forming_bar_progress() == pytest.approx(353 / 390, rel=1e-4)
        # 40% of a normal day at 90% elapsed is not a light day: 0.4 / 0.9051
        assert momentum.rvol([1000.0] * 50 + [400.0]) == pytest.approx(0.4419, rel=1e-3)
    finally:
        date_window.set_run_clock(None)


def test_a_too_partial_bar_is_unmeasured_not_a_wild_number():
    date_window.set_run_clock(_et(9, 35))  # 5 minutes in: ~77x if annualised
    try:
        assert momentum.rvol([1000.0] * 50 + [400.0]) is None
    finally:
        date_window.set_run_clock(None)


def test_a_machine_local_clock_is_converted_to_exchange_time():
    """The graph publishes the MACHINE's instant; the session leaves read that
    wall clock AS ET. A Central-time box (UTC-5, ET is UTC-4 in October) running
    at 12:22 ET published 11:22, so the session looked 60 minutes young and
    every forming bar was annualised by 0.3282 where ET says 0.4821: the live
    2026-10-09 batch read TMUS RVOL 1.99 against an ET-correct ~1.35."""
    if _exchange_zone() is None:
        pytest.skip("no tzdata: the exchange-time conversion is unavailable")
    central = datetime(2026, 10, 9, 11, 22, tzinfo=timezone(timedelta(hours=-5)))
    published = ms.to_exchange_time(central)
    assert published.utcoffset() == timedelta(hours=-4)  # EDT, not the box's -05:00
    assert (published.hour, published.minute) == (12, 22)  # 11:22 CT is 12:22 ET
    assert ms._session_progress(published)["minutes_elapsed"] == 172
    # the reader stays hour-raw: a naive value is read as ET as-is (112 of 390)
    assert ms._session_progress(datetime(2026, 10, 9, 11, 22))["minutes_elapsed"] == 112
    date_window.set_run_clock(published)
    try:
        assert momentum.rvol([1000.0] * 50 + [400.0]) == pytest.approx(
            0.4 / (172 / 390), rel=1e-3
        )
    finally:
        date_window.set_run_clock(None)


def test_the_graph_publishes_the_run_clock_in_exchange_time():
    """``create_initial_state`` is the only publisher of the run clock, so a
    live run must hand the leaves an ET instant rather than the box's zone."""
    et = _exchange_zone()
    if et is None:
        pytest.skip("no tzdata: the exchange-time conversion is unavailable")
    date_window.set_run_clock(None)
    try:
        Propagator().create_initial_state("AAPL", datetime.now(et).date().isoformat())
        published = date_window.get_run_clock()
        assert published is not None, "a live run publishes the clock"
        assert published.tzinfo is not None
        assert published.utcoffset() == datetime.now(et).utcoffset()
        assert abs((published - datetime.now(et)).total_seconds()) < 120
    finally:
        date_window.set_run_clock(None)


def test_annualise_partial_ratio_honours_an_explicit_progress():
    assert momentum.annualise_partial_ratio(0.4, 1.0) == pytest.approx(0.4)
    assert momentum.annualise_partial_ratio(0.4, 0.5) == pytest.approx(0.8)
    assert momentum.annualise_partial_ratio(0.4, 0.05) is None
    assert momentum.annualise_partial_ratio(None, 0.5) is None


def test_the_trigger_candle_reads_the_same_adjusted_ratio():
    """The value-dip trigger and the momentum pillar must share one basis."""
    vols = [1000.0] * 25 + [400.0]
    closes = [100.0 + i for i in range(26)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    date_window.set_run_clock(None)
    raw = value_dip.trigger_candle(closes, highs, lows, vols, window=20)["rvol"]
    date_window.set_run_clock(_et(15, 23))
    try:
        adjusted = value_dip.trigger_candle(closes, highs, lows, vols, window=20)["rvol"]
    finally:
        date_window.set_run_clock(None)
    assert raw is not None and adjusted is not None
    assert adjusted == pytest.approx(raw / (353 / 390), rel=2e-2)
