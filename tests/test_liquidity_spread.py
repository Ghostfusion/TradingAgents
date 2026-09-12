"""Quote-free spread estimators (Corwin-Schultz / Abdi-Ranaldo) and the
spread-implied Almgren-Chriss temporary impact.

Pure tests: deterministic synthetic OHLC series, no network, no wall clock.
"""

import math

import pytest

from tradingagents.strategies.execution_schedule import (
    almgren_chriss,
    default_temp_impact,
    pov_schedule,
    twap_schedule,
)
from tradingagents.strategies.liquidity_risk import (
    abdi_ranaldo,
    corwin_schultz,
    spread_estimate,
)


def _flat_spread(n=12, mid=100.0, spread=0.02):
    """Constant-mid bars whose high/low straddle a known proportional spread.

    high = mid*(1+s/2), low = mid*(1-s/2), close = high on every bar, so both
    estimators should recover ``s`` (within the log/level approximation).
    """
    high = mid * (1.0 + spread / 2.0)
    low = mid * (1.0 - spread / 2.0)
    return [high] * n, [high] * n, [low] * n


def _nested_ranges(n=12):
    """Wide day [99, 101] alternating with a narrow day nested inside it.

    The two-day union range is always the wide day's range, but beta sees
    both daily ranges -- the case the two-day range correction exists for.
    """
    highs, lows, closes = [], [], []
    for i in range(n):
        high, low = (101.0, 99.0) if i % 2 == 0 else (100.5, 99.5)
        highs.append(high)
        lows.append(low)
        closes.append(99.997)
    return closes, highs, lows


def _uptrend(n=12, step=0.02, close_at_high=False):
    """Monotone level drift: the two-day range overwhelms the daily ranges."""
    closes, highs, lows = [], [], []
    for i in range(n):
        mid = 100.0 * (1.0 + step) ** i
        high, low = mid * 1.01, mid * 0.99
        highs.append(high)
        lows.append(low)
        closes.append(high if close_at_high else mid)
    return closes, highs, lows


# --- Corwin-Schultz / Abdi-Ranaldo recovery ---------------------------------

def test_corwin_schultz_recovers_known_spread():
    closes, highs, lows = _flat_spread(spread=0.02)
    out = corwin_schultz(closes, highs, lows)
    assert out is not None
    assert out["basis"] == "corwin-schultz"
    assert out["n"] == 12
    # Exact for a constant spread: 0.02 within a 0.5% tolerance.
    assert out["spread"] == pytest.approx(0.02, rel=0.005)


def test_abdi_ranaldo_recovers_known_spread():
    closes, highs, lows = _flat_spread(spread=0.02)
    out = abdi_ranaldo(closes, highs, lows)
    assert out is not None
    assert out["basis"] == "abdi-ranaldo"
    assert out["n"] == 12
    assert out["spread"] == pytest.approx(0.02, rel=0.005)


def test_corwin_schultz_applies_two_day_range_correction():
    # Union range is the wide day's [99, 101] while beta sees both daily
    # ranges -> ~0.0057, not the wide-day 0.02. A single-day-range shortcut
    # would double-count the price move and report ~0.017 instead.
    closes, highs, lows = _nested_ranges()
    out = corwin_schultz(closes, highs, lows)
    assert out is not None
    assert out["spread"] == pytest.approx(0.005699, abs=1e-5)


# --- negative corrections degrade to None -----------------------------------

def test_estimators_none_on_negative_correction():
    # 2%/day drift: the two-day range correction and the AR moment both go
    # negative -> unavailable, never a clamped 0.0.
    closes, highs, lows = _uptrend(step=0.02)
    assert corwin_schultz(closes, highs, lows) is None
    assert abdi_ranaldo(closes, highs, lows) is None
    assert spread_estimate(closes, highs, lows) is None


def test_spread_estimate_keeps_available_component():
    # CS is defined (nested ranges), AR is not -> the single component wins
    # and the other is reported absent.
    closes, highs, lows = _nested_ranges()
    out = spread_estimate(closes, highs, lows)
    assert out is not None
    assert out["basis"] == "corwin-schultz"
    assert out["components"]["corwin-schultz"] is not None
    assert out["components"]["abdi-ranaldo"] is None
    assert out["spread"] == pytest.approx(out["components"]["corwin-schultz"])


def test_spread_estimate_abdi_ranaldo_only():
    # 1%/day drift with close at the high: CS correction is negative, AR stays
    # positive -> the AR component alone is returned.
    closes, highs, lows = _uptrend(step=0.01, close_at_high=True)
    assert corwin_schultz(closes, highs, lows) is None
    ar = abdi_ranaldo(closes, highs, lows)
    assert ar is not None
    out = spread_estimate(closes, highs, lows)
    assert out is not None
    assert out["basis"] == "abdi-ranaldo"
    assert out["components"]["corwin-schultz"] is None
    assert out["spread"] == pytest.approx(ar["spread"])


def test_spread_estimate_median_when_both_available():
    closes, highs, lows = _flat_spread(spread=0.02)
    cs = corwin_schultz(closes, highs, lows)
    ar = abdi_ranaldo(closes, highs, lows)
    out = spread_estimate(closes, highs, lows)
    assert out is not None
    assert out["basis"] == "median(both)"
    assert out["components"]["corwin-schultz"] == pytest.approx(cs["spread"])
    assert out["components"]["abdi-ranaldo"] == pytest.approx(ar["spread"])
    assert out["spread"] == pytest.approx((cs["spread"] + ar["spread"]) / 2.0, rel=1e-9)
    assert out["spread"] == pytest.approx(0.02, rel=0.005)


def test_spread_estimators_degrade_to_none():
    for fn in (corwin_schultz, abdi_ranaldo, spread_estimate):
        assert fn(None, None, None) is None
        assert fn([], [], []) is None
        assert fn([100.0] * 4, [101.0] * 4, [99.0] * 4) is None  # too short
        assert fn([100.0] * 6, [101.0] * 6, [99.0] * 5) is None  # misaligned
        assert fn([0.0] * 6, [0.0] * 6, [0.0] * 6) is None  # non-positive
        assert fn([None] * 6, [101.0] * 6, [99.0] * 6) is None  # non-numeric


# --- spread-implied temporary impact ---------------------------------------

def test_default_temp_impact_scales_with_spread_and_price():
    base = default_temp_impact(100.0, 0.002)
    assert base == pytest.approx(0.5 * 0.002 * 100.0 / 1e6)
    assert default_temp_impact(100.0, 0.004) > base  # wider spread -> more impact
    assert default_temp_impact(200.0, 0.002) > base  # higher price -> more impact


def test_default_temp_impact_none_on_degenerate_inputs():
    assert default_temp_impact(0.0, 0.01) is None
    assert default_temp_impact(-1.0, 0.01) is None
    assert default_temp_impact(100.0, 0.0) is None
    assert default_temp_impact(100.0, -0.01) is None
    assert default_temp_impact(float("nan"), 0.01) is None
    assert default_temp_impact(100.0, None) is None
    assert default_temp_impact(None, 0.01) is None
    assert default_temp_impact("x", 0.01) is None


def test_almgren_chriss_default_only_when_temp_impact_unset():
    base = almgren_chriss(10000, 10, 0.02, eta=1e-6, lam=1e-6)
    # Explicit coefficient wins even when price/spread would derive another.
    explicit = almgren_chriss(10000, 10, 0.02, eta=1e-6, lam=1e-6,
                              temp_impact=1e-6, price=50.0, spread=0.002)
    assert explicit == base
    # Unset -> the spread-implied default replaces the positional eta:
    # eta = (0.002/2)*50/1e6 = 5e-8, kappa = sqrt(1e-6*0.02^2/5e-8).
    derived = almgren_chriss(10000, 10, 0.02, lam=1e-6,
                             price=50.0, spread=0.002)
    assert derived["kappa"] == pytest.approx(math.sqrt(1e-6 * 0.02 ** 2 / 5e-8), rel=1e-3)
    assert derived["kappa"] != base["kappa"]
    # No price/spread -> positional eta still used (old behaviour).
    assert almgren_chriss(10000, 10, 0.02, 1e-6, 1e-6) == base


def test_explicit_schedule_outputs_unchanged():
    ac = almgren_chriss(10000, 10, 0.02, 1e-6, 1e-6)
    assert ac["kappa"] == 0.02
    assert ac["e_is"] == pytest.approx(10.000348, rel=1e-6)
    assert ac["var_is"] == pytest.approx(113301.778078, rel=1e-6)
    assert ac["schedule"][0] == (1, 8988.634599, 1011.365401)
    assert ac["schedule"][-1] == (10, 0.0, 993.430539)

    twap = twap_schedule(10000, 5)
    assert twap["n"] == 5
    assert twap["schedule"][0] == (1, 8000.0, 2000.0)

    pov = pov_schedule(1000, 500, 0.10)
    assert pov["n"] == 20
    assert pov["schedule"][0] == (1, 950.0, 50.0)
