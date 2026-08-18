"""Phase 0 unit tests: cost-aware evaluation metrics (offline)."""

import pytest

from tradingagents.strategies.evaluate import (
    net_returns, total_return, cagr, volatility, sharpe, deflated_sharpe,
    max_drawdown, equity_curve, walk_forward_splits, pbo_flag,
)


def test_net_returns_subtracts_costs():
    out = net_returns([0.01, -0.005], cost_bps=10)
    assert abs(out[0] - (0.01 - 0.001)) < 1e-9
    assert abs(out[1] - (-0.005 - 0.001)) < 1e-9


def test_total_return_compounds():
    assert abs(total_return([0.1, 0.1]) - 0.21) < 1e-9
    assert total_return([]) == 0.0


def test_cagr_zero_on_empty():
    assert cagr([]) == 0.0
    assert cagr([0.0, 0.0]) == 0.0


def test_sharpe_positive_for_up_trend():
    r = [0.0012 if i % 2 else 0.0005 for i in range(252)]
    assert sharpe(r) > 0
    assert volatility(r) > 0


def test_deflated_sharpe_penalizes_trials():
    r = [0.01, -0.005, 0.008, -0.003, 0.012]
    one = deflated_sharpe(r, n_trials=1)
    many = deflated_sharpe(r, n_trials=1000)
    assert many < one


def test_max_drawdown():
    curve = [100.0, 120.0, 110.0, 130.0]
    assert abs(max_drawdown(curve) - (120 - 110) / 120) < 1e-9


def test_equity_curve_compounds():
    eq = equity_curve([0.01] * 3, start=100)
    assert abs(eq[-1] - 100 * 1.01 ** 3) < 1e-6


def test_walk_forward_splits():
    splits = list(walk_forward_splits(list(range(10)), train_len=3, test_len=2))
    assert len(splits) == 3
    assert splits[0][0] == [0, 1, 2]
    assert splits[0][1] == [3, 4]


def test_pbo_flag_detects_overfit():
    assert pbo_flag([1.0, 2.0, 0.5], [0.2, -0.5, 0.3]) is True  # best trial tanks
    assert pbo_flag([1.0, 2.0], [0.4, 0.5]) is False
