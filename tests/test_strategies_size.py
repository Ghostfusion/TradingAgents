"""Phase 2 unit tests: Kelly sizing, vol targeting, ATR stops, CVaR budget."""

import pytest

from tradingagents.strategies.size import (
    kelly_fraction, position_size_kelly, volatility_target_scale, atr,
    stop_loss_atr, cvar_budget, position_size_with_risk,
)


def test_kelly_bounds():
    assert abs(kelly_fraction(0.6, 1.0) - 0.2) < 1e-9
    assert kelly_fraction(0.4, 1.0) == 0.0  # no edge
    assert kelly_fraction(1.0, 2.0) == 1.0


def test_quarter_kelly_capped():
    assert position_size_kelly(0.8, fraction=0.25) < 0.5
    assert 0.0 <= position_size_kelly(0.9, max_size=0.05) <= 0.05


def test_vol_target_scale():
    calm = [0.002, -0.001, 0.003, -0.002, 0.001, 0.002, -0.001]
    scale = volatility_target_scale(calm, target_vol=0.15)
    assert 0.0 < scale <= 3.0
    assert volatility_target_scale([], 0.15) == 0.0


def test_atr_positive():
    high = [100.0] * 3 + [102.0] * 3
    low = [99.0] * 6
    close = [99.5] * 6
    assert atr(high, low, close) > 0


def test_stop_below_close():
    high = [100.0, 100.0, 102.0]
    low = [99.0, 99.0, 98.0]
    close = [99.5, 100.0, 101.0]
    assert stop_loss_atr(close, high, low) < close[-1]


def test_cvar_negative_tail():
    bad = [-0.1, -0.08, -0.05, 0.01, 0.05]
    assert cvar_budget(bad, alpha=0.2) < 0


def test_risk_cap_respected():
    size = position_size_with_risk(0.7, 1.0, atr=2.0, close=100.0,
                                   risk_per_trade=0.01)
    assert 0.0 < size <= 0.10  # quarter-Kelly (0.1) is the binding cap
