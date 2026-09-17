"""Phase 0 unit tests: cost-aware evaluation metrics (offline)."""

from tradingagents.strategies.evaluate import (
    cagr,
    deflated_sharpe,
    equity_curve,
    information_ratio,
    max_drawdown,
    net_returns,
    pbo_flag,
    sharpe,
    total_return,
    tracking_error,
    volatility,
    walk_forward_splits,
)


def test_net_returns_subtracts_costs():
    out = net_returns([0.01, -0.005], cost_bps=10)
    assert abs(out[0] - (0.01 - 0.001)) < 1e-9
    assert abs(out[1] - (-0.005 - 0.001)) < 1e-9


def test_net_returns_illiq_scales_cost():
    # item 3: illiquid name scales cost up; None illiq keeps flat cost.
    out = net_returns([0.01], cost_bps=10, illiq=1e-5)
    extra = 1e-5 * 1e5 / 10000.0  # +1bp
    assert abs(out[0] - (0.01 - 0.001 - extra)) < 1e-9
    flat = net_returns([0.01], cost_bps=10, illiq=None)
    assert abs(flat[0] - (0.01 - 0.001)) < 1e-9


def test_total_return_compounds():
    assert abs(total_return([0.1, 0.1]) - 0.21) < 1e-9
    assert total_return([]) == 0.0


def test_tracking_error_of_a_constant_offset_is_zero():
    """A flat cost offset on an exactly-tracked series is zero TE, not float
    noise: the std of the ~1e-18 residuals annualized to a TE ~7e-18 and then
    divided into a nonsense information ratio (IEI 2026-09-16 shipped
    info_ratio=-2.9e17 in an analyst prompt)."""
    raw = [0.012345, -0.009876, 0.004321, 0.007654,
           -0.003210, 0.001234, -0.005432, 0.002345]
    offset = [r - 0.001 for r in raw]
    assert tracking_error(offset, raw) == 0.0
    assert information_ratio(offset, raw) is None
    # A genuinely divergent series still measures.
    te = tracking_error(raw, [r * 1.5 for r in raw])
    assert te is not None and te > 1e-3


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
    assert abs(eq[-1] - 100 * 1.01**3) < 1e-6


def test_walk_forward_splits():
    splits = list(walk_forward_splits(list(range(10)), train_len=3, test_len=2))
    assert len(splits) == 3
    assert splits[0][0] == [0, 1, 2]
    assert splits[0][1] == [3, 4]


def test_pbo_flag_detects_overfit():
    assert pbo_flag([1.0, 2.0, 0.5], [0.2, -0.5, 0.3]) is True  # best trial tanks
    assert pbo_flag([1.0, 2.0], [0.4, 0.5]) is False
