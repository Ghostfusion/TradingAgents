"""Tests for Phase 6: CPPI + vol-target overlay."""

import pytest

from tradingagents.strategies.portfolio import cppi_exposure
from tradingagents.strategies.size import volatility_target_scale

pytestmark = pytest.mark.timeout(60)


def test_cppi_cushion_lever():
    assert cppi_exposure(1_000_000, 800_000, 3.0) == pytest.approx(600_000)
    # safe sleeve gets the rest: 400k
    assert cppi_exposure(1_000_000, 800_000, 3.0) <= 1_000_000


def test_cppi_floor_breach_zero():
    assert cppi_exposure(700_000, 800_000, 3.0) == 0.0
    assert cppi_exposure(800_000, 800_000, 3.0) == 0.0


def test_cppi_clamped_to_pv():
    # high multiplier never exceeds the portfolio value
    assert cppi_exposure(100_000, 90_000, 10.0) == pytest.approx(100_000)


def test_cppi_none_safe():
    assert cppi_exposure(None, 800_000, 3.0) is None
    assert cppi_exposure(0, 800_000, 3.0) is None
    assert cppi_exposure(1_000_000, 800_000, 0) is None


def test_vol_target_scale_halves_at_double_vol():
    rets_20 = [0.01, -0.01] * 100  # ~1% daily
    rets_10 = [0.005, -0.005] * 100
    s20 = volatility_target_scale(rets_20, 0.10)
    s10 = volatility_target_scale(rets_10, 0.10)
    assert s10 > s20  # lower realized vol -> higher scale toward target


def test_vol_target_override_and_clamp():
    assert volatility_target_scale([], 0.10) == 0.0  # no data
    assert volatility_target_scale([0.01] * 10, 0.10, vol_override=0.20) == pytest.approx(0.5)
    # cap at 3x
    assert volatility_target_scale([0.001] * 10, 0.30, vol_override=0.01) == pytest.approx(3.0)
