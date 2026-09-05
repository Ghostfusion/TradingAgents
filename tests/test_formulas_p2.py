"""P2 tests: book concentration suite + EVT/GPD extreme-tail VaR (offline)."""

import random

import numpy as np
import pytest

from tradingagents.strategies.book_risk import extreme_quantile_var
from tradingagents.strategies.portfolio import (
    active_share,
    effective_holdings,
    weight_entropy,
    weight_hhi,
)

pytestmark = pytest.mark.timeout(120)


# --- concentration suite ---


def test_active_share_identical_zero():
    w = {"A": 0.5, "B": 0.5}
    assert active_share(w, dict(w)) == pytest.approx(0.0)


def test_active_share_disjoint_one():
    assert active_share({"A": 1.0}, {"B": 1.0}) == pytest.approx(1.0)
    assert active_share({"A": 0.6, "B": 0.4}, {"C": 1.0}) == pytest.approx(1.0)


def test_active_share_half_tilt():
    # A 0.6/0.4 book vs a 0.4/0.6 benchmark: |0.2|+|0.2| / 2 = 0.2.
    assert active_share({"A": 0.6, "B": 0.4}, {"A": 0.4, "B": 0.6}) == pytest.approx(0.2)


def test_active_share_empty_none():
    assert active_share({}, {"A": 1.0}) is None
    assert active_share({"A": 1.0}, {}) is None


def test_effective_holdings_equal_and_concentrated():
    assert effective_holdings({"A": 0.1, "B": 0.1, "C": 0.1, "D": 0.1, "E": 0.1, "F": 0.1, "G": 0.1, "H": 0.1, "I": 0.1, "J": 0.1}) == pytest.approx(10.0)
    assert effective_holdings({"A": 0.5, "B": 0.25, "C": 0.25}) == pytest.approx(1 / (0.25 + 0.0625 + 0.0625))
    assert effective_holdings({}) is None


def test_weight_hhi_bounds():
    assert weight_hhi({"A": 1.0}) == pytest.approx(1.0)
    assert weight_hhi({"A": 0.5, "B": 0.5}) == pytest.approx(0.5)
    assert weight_hhi({}) is None


def test_weight_entropy_single_and_equal():
    assert weight_entropy({"A": 1.0}) == pytest.approx(0.0)
    assert weight_entropy({"A": 0.5, "B": 0.5}) == pytest.approx(-1.0 * 2 * (0.5 * np.log(0.5)))
    assert weight_entropy({"A": -1.0, "B": 2.0}) is None  # non-positive weight


# --- EVT / GPD extreme tail ---


def _fat_tail_series(n=500, seed=9):
    """Heavy-tailed returns: a Normal bulk plus a handful of large crashes
    (a real fat tail the historical quantile understates)."""
    rng = random.Random(seed)
    rets = [rng.gauss(0.0003, 0.01) for _ in range(n)]
    for _ in range(int(n * 0.03)):
        rets[rng.randrange(n)] = -rng.gauss(0.06, 0.02)
    return rets


def _exact_gpd_series(n=1000, seed=4, tail_n=80, xi=0.25, beta=0.02, u=0.03):
    """Series whose worst `tail_n` losses are EXACTLY GPD(xi, beta)
    exceedances above a threshold u (inverse-CDF draws) - the estimator's
    ideal input, so the fitted shape/quantile must recover the true ones."""
    rng = random.Random(seed)
    rets = [rng.gauss(0.0002, 0.004) for _ in range(n)]
    for _ in range(tail_n):
        uu = rng.uniform(0.0, 1.0)
        y = (beta / xi) * (uu ** (-xi) - 1.0)  # inverse-CDF exceedance
        rets[rng.randrange(n)] = -(u + y)
    return rets


def test_extreme_var_recovers_exact_gpd_tail():
    xi, beta, u, n, tail_n = 0.25, 0.02, 0.03, 1000, 120
    rets = _exact_gpd_series(xi=xi, beta=beta, u=u, tail_n=tail_n)
    r = extreme_quantile_var(rets, alpha=0.02)
    assert r is not None
    assert r["xi"] == pytest.approx(xi, abs=0.08)  # shape recovered
    # True 2% quantile of the mixture: P(L > L*) = 0.02 with the GPD tail
    # (the tail spans P(L>u) = tail_n/n; beyond u it is the GPD).
    f_tail = 1.0 - 0.02 * n / tail_n  # tail F at the full-series alpha quantile
    true_var = u + (beta / xi) * ((1.0 - f_tail) ** (-xi) - 1.0)
    assert r["var"] == pytest.approx(-true_var, rel=0.25)
    assert r["es"] < r["var"]  # ES worse than VaR


def test_extreme_var_shape_sign():
    """A fat-tailed series must read a positive GPD shape (xi > 0)."""
    r = extreme_quantile_var(_fat_tail_series(), alpha=0.02)
    assert r is not None and r["xi"] > 0.0
    # Bounded series (uniform -0.01..+0.01) reads a negative shape.
    bounded = [random.uniform(-0.01, 0.01) for _ in range(500)]
    rb = extreme_quantile_var(bounded, alpha=0.01)
    assert rb is not None and rb["xi"] < 0.0


def test_extreme_var_shorter_than_required_none():
    assert extreme_quantile_var([0.01] * 20, min_exceed=10) is None
    assert extreme_quantile_var([]) is None


def test_extreme_var_constant_series_none():
    assert extreme_quantile_var([0.01] * 300) is None  # zero variance tail
