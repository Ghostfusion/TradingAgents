"""Phase 0 unit tests: cost-aware evaluation metrics (offline)."""

import pytest

from tradingagents.strategies.evaluate import (
    cagr,
    deflated_sharpe,
    deflated_sharpe_ratio,
    deflated_sharpe_report,
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

pytestmark = pytest.mark.timeout(120)


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


# Alternating +/- returns: per-observation SR ~0.08 (mean 0.0008, sd 0.01), so
# the ANNUALIZED Sharpe is ~1.3 while the 50-trial per-observation selection
# threshold is ~2.80 - the scale gap the legacy difference mixes.
_ALTERNATING = [0.0108, -0.0092] * 250


def test_deflated_sharpe_ratio_is_per_observation_and_probabilistic():
    """Eq. (2) is applied in per-observation units and returns a probability.

    The legacy ``deflated_sharpe`` subtracts a unit-scale threshold from an
    annualized Sharpe, so its value here is a large negative Sharpe-unit
    difference; the DSR is a confidence in [0, 1] and reads the same series as
    indistinguishable from noise after 50 trials.
    """
    dsr = deflated_sharpe_ratio(_ALTERNATING, n_trials=50)
    assert dsr is not None
    assert 0.0 <= dsr <= 1.0
    assert dsr < 0.5
    assert deflated_sharpe(_ALTERNATING, n_trials=50) < 0.0


def test_deflated_sharpe_ratio_falls_as_trials_grow():
    small = deflated_sharpe_ratio(_ALTERNATING, n_trials=10)
    large = deflated_sharpe_ratio(_ALTERNATING, n_trials=1000)
    assert small is not None and large is not None
    assert large <= small


def test_deflated_sharpe_ratio_guards_degenerate_inputs():
    assert deflated_sharpe_ratio(_ALTERNATING, n_trials=1) is None        # N < 2
    assert deflated_sharpe_ratio([0.01, 0.02], n_trials=10) is None       # < 4 obs
    assert deflated_sharpe_ratio(_ALTERNATING, n_trials=10,
                                 sharpe_dispersion=0.0) is None           # no dispersion


def test_deflated_sharpe_ratio_uses_the_measured_dispersion():
    """A tightly clustered search deflates less than the unit-variance default:
    V is what the selection threshold is actually built from."""
    assumed = deflated_sharpe_ratio(_ALTERNATING, n_trials=50)
    measured = deflated_sharpe_ratio(_ALTERNATING, n_trials=50,
                                     sharpe_dispersion=0.0005)
    assert assumed is not None and measured is not None
    assert measured > assumed


def test_deflated_sharpe_report_carries_the_ratio():
    rep = deflated_sharpe_report([0.001, -0.002, 0.003] * 40, n_trials=10)
    assert rep["ratio"] is not None and 0.0 <= rep["ratio"] <= 1.0
    assert rep["ratio"] != rep["value"]  # a probability beside the difference
