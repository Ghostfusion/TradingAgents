"""Tests for `strategies/technical_depth` - the TechnicalScore §8.2 depth families.

Deterministic synthetic series only; no vendor calls, no network. Every
producer is exercised on a series long enough to measure, plus its refusal
case (``unavailable`` is a reason string, never a fabricated 0).
"""

import pytest

from tradingagents.strategies.technical_depth import (
    adv_participation,
    awesome_oscillator,
    candle_strength,
    coppock_curve,
    dpo,
    ease_of_movement,
    ema_stack,
    gap_depth,
    moving_average_depth,
    regression_read,
    relative_vigor_index,
    ultimate_oscillator,
    zweig_breadth_thrust,
)

pytestmark = pytest.mark.timeout(180)


def _line(n, start=100.0, step=0.5):
    return [start + step * i for i in range(n)]


def _noisy_line(n, start=100.0, step=0.5, amp=0.2):
    return [start + step * i + (amp if i % 2 else -amp) for i in range(n)]


def _bars(n, o=100.0, h=110.0, low=95.0, c=105.0, v=1000.0):
    return ([o] * n, [h] * n, [low] * n, [c] * n, [v] * n)


# ---------------------------------------------------------------------------
# 1. Regression family
# ---------------------------------------------------------------------------


def test_regression_read_computes():
    out = regression_read(_noisy_line(60), window=40)
    assert out["unavailable"] is None
    assert out["n"] == 40
    for k in ("slope", "intercept", "r2", "trend_quality",
              "channel_mid", "channel_upper", "channel_lower", "trend_to_noise"):
        assert out[k] is not None, k
    assert out["slope"] > 0 and 0.0 < out["r2"] <= 1.0
    assert out["trend_quality"] > 0
    assert out["channel_upper"] > out["channel_lower"]
    assert 0.0 <= out["channel_position"] <= 1.0


def test_regression_read_refuses():
    out = regression_read([100.0] * 5, window=20)
    assert out["slope"] is None and out["r2"] is None
    assert isinstance(out["unavailable"], str)
    flat = regression_read([100.0] * 30, window=20)
    assert flat["r2"] is None and isinstance(flat["unavailable"], str)


# ---------------------------------------------------------------------------
# 2. Moving-average depth
# ---------------------------------------------------------------------------


def test_moving_average_depth_computes():
    out = moving_average_depth(_line(260))
    assert out["unavailable"] is None
    assert out["n"] == 260
    assert out["wma"] is not None and out["hma"] is not None
    assert out["ema_slope"] is not None and out["ema_slope"] > 0
    assert out["golden_cross"] is True
    assert out["cross_spread"] > 0 and out["cross_velocity"] is not None


def test_moving_average_depth_refuses():
    out = moving_average_depth([100.0] * 30)
    assert out["wma"] is None and out["golden_cross"] is None
    assert isinstance(out["unavailable"], str)


def test_ema_stack_computes():
    out = ema_stack(_line(40), atr_value=2.0)
    assert out["unavailable"] is None
    assert out["stack"] > 0  # EMA5 above EMA20 on an uptrend
    assert out["ema_fast"] > out["ema_slow"]


def test_ema_stack_refuses():
    out = ema_stack(_line(40), atr_value=None)
    assert out["stack"] is None and isinstance(out["unavailable"], str)
    short = ema_stack([100.0] * 5, atr_value=1.0)
    assert short["stack"] is None and isinstance(short["unavailable"], str)


# ---------------------------------------------------------------------------
# 3. Candle / gap depth
# ---------------------------------------------------------------------------


def test_candle_strength_computes():
    out = candle_strength([100.0], [110.0], [90.0], [105.0])
    assert out["unavailable"] is None
    assert out["intraday_strength"] == pytest.approx(0.75)
    assert out["close_location"] == pytest.approx(0.5)
    assert out["body_pct"] == pytest.approx(0.25)
    assert out["range"] == pytest.approx(20.0)


def test_candle_strength_refuses():
    out = candle_strength([100.0], [100.0], [100.0], [100.0])
    assert out["intraday_strength"] is None
    assert isinstance(out["unavailable"], str)
    empty = candle_strength([], [], [], [])
    assert empty["intraday_strength"] is None and isinstance(empty["unavailable"], str)


def test_gap_depth_computes():
    out = gap_depth([100.0, 104.0], [100.0, 105.0], [101.0, 106.0], [95.0, 95.0])
    assert out["unavailable"] is None
    assert out["type"] == "up"
    assert out["gap_pct"] == pytest.approx(0.05)
    assert out["continuation"] == -1  # gap up, close below the open
    assert out["fill_fraction"] == pytest.approx(1.0)
    assert out["filled"] is True


def test_gap_depth_refuses():
    out = gap_depth([100.0], [100.0], [100.0], [100.0])
    assert out["type"] is None and isinstance(out["unavailable"], str)
    flat = gap_depth([100.0, 105.0], [100.0, 100.0], [101.0, 106.0], [95.0, 95.0])
    assert flat["type"] is None and isinstance(flat["unavailable"], str)  # zero gap


# ---------------------------------------------------------------------------
# 4. Zweig breadth thrust
# ---------------------------------------------------------------------------


def test_zweig_breadth_thrust_computes():
    adv = [30.0] * 25 + [90.0] * 5
    dec = [70.0] * 25 + [10.0] * 5
    out = zweig_breadth_thrust(adv, dec)
    assert out["unavailable"] is None
    assert out["ratio"] == pytest.approx(0.9)
    assert out["ema"] > 0.60 and out["ema_change"] > 0
    assert out["signal"] is True


def test_zweig_breadth_thrust_refuses():
    out = zweig_breadth_thrust([10.0] * 5, [10.0] * 5)
    assert out["ema"] is None and isinstance(out["unavailable"], str)


# ---------------------------------------------------------------------------
# 5. ADV participation
# ---------------------------------------------------------------------------


def test_adv_participation_computes():
    out = adv_participation([100.0] * 21 + [200.0], window=21)
    assert out["unavailable"] is None
    assert out["adv"] == pytest.approx(100.0)
    assert out["latest_volume"] == pytest.approx(200.0)
    assert out["participation"] == pytest.approx(2.0)


def test_adv_participation_refuses():
    out = adv_participation([100.0] * 5, window=21)
    assert out["participation"] is None and isinstance(out["unavailable"], str)


# ---------------------------------------------------------------------------
# 6. Legacy oscillators
# ---------------------------------------------------------------------------


def test_dpo_computes():
    out = dpo(_line(60), n=20)
    assert out["unavailable"] is None
    assert out["dpo"] < 0  # the shifted price sits left of (below) the SMA
    assert out["shift"] == 11


def test_dpo_refuses():
    out = dpo([100.0] * 5, n=20)
    assert out["dpo"] is None and isinstance(out["unavailable"], str)


def test_ultimate_oscillator_computes():
    closes = _line(60)
    highs = [c + 2.0 for c in closes]
    lows = [c - 2.0 for c in closes]
    out = ultimate_oscillator(closes, highs, lows)
    assert out["unavailable"] is None
    assert 0.0 <= out["uo"] <= 100.0
    assert out["avg7"] is not None and out["avg28"] is not None


def test_ultimate_oscillator_refuses():
    out = ultimate_oscillator([100.0] * 5, [101.0] * 5, [99.0] * 5)
    assert out["uo"] is None and isinstance(out["unavailable"], str)


def test_awesome_oscillator_computes():
    closes = _line(60)
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    out = awesome_oscillator(highs, lows)
    assert out["unavailable"] is None
    assert out["ao"] > 0  # faster average above the slower one on an uptrend


def test_awesome_oscillator_refuses():
    out = awesome_oscillator([100.0] * 5, [99.0] * 5)
    assert out["ao"] is None and isinstance(out["unavailable"], str)


def test_relative_vigor_index_computes():
    n = 20
    out = relative_vigor_index(
        [100.0] * n, [110.0] * n, [95.0] * n, [105.0] * n
    )
    assert out["unavailable"] is None
    assert out["rvi"] == pytest.approx(5.0 / 15.0)
    assert out["signal"] == pytest.approx(5.0 / 15.0)


def test_relative_vigor_index_refuses():
    out = relative_vigor_index([100.0] * 5, [110.0] * 5, [95.0] * 5, [105.0] * 5)
    assert out["rvi"] is None and isinstance(out["unavailable"], str)


def test_coppock_curve_computes():
    out = coppock_curve(_line(60))
    assert out["unavailable"] is None
    assert out["coppock"] > 0  # positive ROCs on an uptrend
    assert out["roc_sum"] > 0


def test_coppock_curve_refuses():
    out = coppock_curve([100.0] * 5)
    assert out["coppock"] is None and isinstance(out["unavailable"], str)


def test_ease_of_movement_computes():
    highs = [100.0 + 0.5 * i for i in range(30)]
    lows = [h - 2.0 for h in highs]
    volumes = [1000.0] * 30
    out = ease_of_movement(highs, lows, volumes, n=14)
    assert out["unavailable"] is None
    assert out["emv"] > 0 and out["emv_avg"] > 0


def test_ease_of_movement_refuses():
    out = ease_of_movement([100.0] * 5, [99.0] * 5, [1000.0] * 5, n=14)
    assert out["emv"] is None and isinstance(out["unavailable"], str)


def test_no_fabricated_zero_on_missing_input():
    """Every refusal is a reason string, never a silent 0 (the NA != 0 contract)."""
    for out in (
        regression_read([]),
        moving_average_depth([]),
        ema_stack([], None),
        candle_strength([], [], [], []),
        gap_depth([], [], [], []),
        zweig_breadth_thrust([], []),
        adv_participation([]),
        dpo([]),
        ultimate_oscillator([], [], []),
        awesome_oscillator([], []),
        relative_vigor_index([], [], [], []),
        coppock_curve([]),
        ease_of_movement([], [], []),
    ):
        assert isinstance(out["unavailable"], str) and out["unavailable"]
        assert all(v != 0 for k, v in out.items() if k not in ("n", "unavailable"))
