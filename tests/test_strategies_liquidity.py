"""Liquidity & ownership-risk metrics (strategies/liquidity_risk.py) - pure tests.

Verifies the risk2.md formulas (IWF, float turnover, Amihud ILLIQ,
days-to-absorb, HHI) and the no-fabrication rule (missing input -> None).
"""

import pytest

from tradingagents.strategies.liquidity_risk import (
    amihud_illiquidity,
    days_to_absorb,
    float_turnover,
    free_float_factor,
    liquidity_verdict,
    ownership_hhi,
)


def test_free_float_factor_basic():
    # 30M float / 100M outstanding = 0.30 (matches risk2.md TR example)
    assert free_float_factor(30e6, 100e6) == pytest.approx(0.30)
    assert free_float_factor(100e6, 100e6) == pytest.approx(1.0)


def test_free_float_factor_missing_or_invalid():
    assert free_float_factor(None, 100e6) is None
    assert free_float_factor(30e6, None) is None
    assert free_float_factor(30e6, 0) is None
    assert free_float_factor(-5e6, 100e6) is None


def test_float_turnover_basic():
    # 1M ADV / 100M float = 1%
    assert float_turnover(1e6, 100e6) == pytest.approx(0.01)
    # below 0.5% floor -> thin
    assert float_turnover(1e5, 100e6) == pytest.approx(0.001)


def test_float_turnover_missing():
    assert float_turnover(None, 100e6) is None
    assert float_turnover(1e6, None) is None
    assert float_turnover(1e6, 0) is None


def test_amihud_illiquidity_basic():
    closes = [100.0, 101.0, 99.0]
    volumes = [1e6, 2e6, 1e6]
    illiq = amihud_illiquidity(closes, volumes)
    assert illiq is not None and illiq > 0


def test_amihud_illiquidity_flat_series_zero():
    # No price change -> no return -> ILLIQ = 0 (perfectly liquid in this metric)
    closes = [100.0, 100.0, 100.0, 100.0]
    volumes = [1e6, 1e6, 1e6, 1e6]
    assert amihud_illiquidity(closes, volumes) == pytest.approx(0.0)


def test_amihud_illiquidity_insufficient_history():
    assert amihud_illiquidity([100.0], [1e6]) is None
    assert amihud_illiquidity([], []) is None
    assert amihud_illiquidity(None, [1e6]) is None


def test_days_to_absorb():
    # 5M shares to liquidate / (1M ADV * 15%) = 33.3 days
    assert days_to_absorb(5e6, 1e6) == pytest.approx(33.33, rel=0.01)
    # tighter participation cap -> more days
    assert days_to_absorb(5e6, 1e6, alpha=0.10) == pytest.approx(50.0)


def test_days_to_absorb_missing():
    assert days_to_absorb(None, 1e6) is None
    assert days_to_absorb(5e6, None) is None
    assert days_to_absorb(5e6, 0) is None


def test_ownership_hhi():
    # 70% + 10% + 5% -> 4900 + 100 + 25 = 5025 (Django under-allocation example)
    assert ownership_hhi([70.0, 10.0, 5.0]) == pytest.approx(5025.0)
    # single 100% owner = 10000
    assert ownership_hhi([100.0]) == pytest.approx(10000.0)
    # widely dispersed -> near 0
    small = [0.1] * 50  # 50 holders at 0.1% each
    assert ownership_hhi(small) == pytest.approx(50 * 0.1 * 0.1)


def test_ownership_hhi_missing_or_empty():
    assert ownership_hhi([]) is None
    assert ownership_hhi(None) is None
    assert ownership_hhi([None, None]) is None


def test_liquidity_verdict_liquid_when_all_good():
    v = liquidity_verdict(illiq=1e-9, float_turnover=0.10, days_to_absorb=5.0)
    assert v["verdict"] == "liquid"
    assert v["dangers"] == []


def test_liquidity_verdict_caution_on_thin_turnover():
    v = liquidity_verdict(illiq=None, float_turnover=0.001, days_to_absorb=1.0)
    assert v["verdict"] == "caution"


def test_liquidity_verdict_illiquid_on_squeeze_or_days():
    v = liquidity_verdict(illiq=None, float_turnover=2.0, days_to_absorb=1.0)
    assert v["verdict"] == "illiquid"
    v2 = liquidity_verdict(illiq=None, float_turnover=0.10, days_to_absorb=60.0)
    assert v2["verdict"] == "caution"


def test_liquidity_verdict_bumps_illiquid():
    # high ILLIQ forces illiquid regardless of other ok inputs
    v = liquidity_verdict(illiq=1e-4, float_turnover=0.10, days_to_absorb=5.0)
    assert v["verdict"] == "illiquid"
    assert any("ILLIQ" in d for d in v["dangers"])


def test_liquidity_verdict_unknown_inputs_ignored():
    # all None -> liquid with no dangers (never fails on missing data)
    v = liquidity_verdict(None, None, None)
    assert v["verdict"] == "liquid"
    assert v["dangers"] == []
