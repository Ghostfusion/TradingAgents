"""Tests for P3: Lo-MacKinlay variance ratio, CUSUM/EWMA shift detection,
complexity / entropy features."""

import random

import pytest

from tradingagents.strategies.complexity import (
    approximate_entropy,
    lz_complexity,
    permutation_entropy,
)
from tradingagents.strategies.mean_reversion import variance_ratio
from tradingagents.strategies.regime import cusum, ewma_control

pytestmark = pytest.mark.timeout(60)


def _random_returns(n: int = 300, seed: int = 1) -> list[float]:
    rnd = random.Random(seed)
    return [rnd.gauss(0.0, 0.01) for _ in range(n)]


def _trend_series(n: int = 300) -> list[float]:
    """Pure positive-drift series (momentum structure)."""
    return [0.001 * i for i in range(n)]


# --- variance ratio --------------------------------------------------------


def test_vr_random_walk_approx_one():
    vr = variance_ratio(_random_returns(), k=5)
    assert vr is not None
    assert 0.6 < vr["vr"] < 1.4  # random walk ~ 1


def test_vr_trend_greater_than_one():
    vr = variance_ratio(_trend_series(), k=5)
    assert vr is not None
    assert vr["vr"] > 1.2  # positive autocorrelation -> momentum


def test_vr_none_safe():
    assert variance_ratio([], k=5) is None
    assert variance_ratio(_random_returns(30), k=5) is None  # too short


# --- CUSUM / EWMA ---------------------------------------------------------


def test_cusum_detects_mean_shift():
    # Calibrated low-noise base then a sustained +2% (>> h) step. Seed 11 was
    # empirically verified: the detector fires AT the step boundary (200) with
    # the same base registering no false signal.
    base = [1e-4 * r for r in _random_returns(200, seed=11)]
    tail = [0.02 + (1e-4 * r) for r in _random_returns(100, seed=51)]
    series = base + tail
    r = cusum(series)
    assert r["signal"] == "up"
    assert r["signal_at"] == 200


def test_cusum_no_false_positive_on_flat():
    # The SAME base without the step -> no signal.
    r = cusum([1e-4 * x for x in _random_returns(200, seed=11)])
    assert r["signal"] is None


def test_ewma_detects_slow_drift():
    drift = [0.001 * i + r for i, r in enumerate(_random_returns(200, seed=5))]
    r = ewma_control(drift)
    assert r["signal"] in ("up", "down")


def test_ewma_none_on_short():
    r = ewma_control([])
    assert r["signal"] is None and r["mu0"] is None


# --- entropy --------------------------------------------------------------


def test_permutation_entropy_random_high():
    pe = permutation_entropy(_random_returns(500, seed=6))
    assert pe is not None and 0.9 <= pe <= 1.0


def test_permutation_entropy_trend_low():
    pe = permutation_entropy(_trend_series(500))
    assert pe is not None and pe < 0.7


def test_permutation_entropy_none_safe():
    assert permutation_entropy([], m=3) is None
    assert permutation_entropy(_random_returns(10), m=3) is None


def test_lz_complexity_random_high_structured_low():
    rnd = random.Random(7)
    noisy = [rnd.random() for _ in range(300)]
    periodic = [0.5 + 0.4 * (i % 4) for i in range(300)]
    c_noisy = lz_complexity(noisy)
    c_period = lz_complexity(periodic)
    assert c_noisy is not None and c_period is not None
    assert c_noisy > c_period


def test_approximate_entropy_sane():
    ae = approximate_entropy(_random_returns(300, seed=8), m=2)
    assert ae is not None and ae > 0  # irregular series -> positive ApEn
