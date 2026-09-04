"""Kalman-filter spread + Black-Litterman optimiser tests (six-pillar adds)."""

from __future__ import annotations

import random

import pytest

from tradingagents.strategies.portfolio_optimizer import black_litterman_weights
from tradingagents.strategies.statistical_kalman import kalman_spread

pytestmark = pytest.mark.timeout(120)


# --- Kalman spread ---


def _pair(n=80, beta=2.0, seed=3, noise_x=0.2, noise_y=0.4):
    rng = random.Random(seed)
    x = [100.0 + 0.3 * i + rng.uniform(-noise_x, noise_x) for i in range(n)]
    y = [beta * xi + rng.uniform(-noise_y, noise_y) for xi in x]
    return x, y


def test_kalman_converges_to_true_beta():
    x, y = _pair(beta=2.0)
    k = kalman_spread(x, y)
    assert k["n"] == 80
    assert k["last_beta"] is not None
    assert abs(k["last_beta"] - 2.0) < 0.3
    assert len(k["beta"]) == 80 and len(k["spread"]) == 80


def test_kalman_beta_tracks_regime_shift():
    """A beta that shifts mid-sample: the filter should adapt (unlike static OLS)."""
    rng = random.Random(5)
    x = [100.0 + 0.3 * i + rng.uniform(-0.2, 0.2) for i in range(100)]
    y = [(1.5 * xi if i < 60 else 3.0 * xi) + rng.uniform(-0.5, 0.5) for i, xi in enumerate(x)]
    k = kalman_spread(x, y)
    assert k["last_beta"] > 2.0  # adapted toward the new 3.0 hedge
    assert k["last_beta"] > k["beta"][30] + 0.5  # moved up from the 1.5 era


def test_kalman_short_input_empty():
    k = kalman_spread([1, 2, 3], [1, 2, 3])
    assert k["beta"] == [] and k["n"] == 0
    assert k["signal"] is None


def test_kalman_signal_extremes():
    # flat spread (y ~ x): signal should be 0
    x = [100.0 + i * 0.1 for i in range(60)]
    y = list(x)
    assert kalman_spread(x, y)["signal"] == 0


def test_kalman_deterministic():
    x, y = _pair(seed=9)
    assert kalman_spread(x, y)["beta"] == kalman_spread(x, y)["beta"]


# --- Black-Litterman (already-implemented add; sanity + view blending) ---


def _ret_byname(names, seed=1, n=120):
    rng = random.Random(seed)
    out = {}
    for name in names:
        base = 0.001
        out[name] = [base + rng.uniform(-0.02, 0.02) for _ in range(n)]
    return out


def test_bl_equilibrium_without_views():
    rets = _ret_byname(["A", "B", "C"])
    caps = {"A": 1e12, "B": 2e12, "C": 5e12}
    r = black_litterman_weights(rets, caps)
    assert set(r["weights"]) == {"A", "B", "C"}
    assert abs(sum(r["weights"].values()) - 1.0) < 1e-6
    assert r["note"] == "black-litterman"
    # market-cap bias: the largest cap should be the biggest weight
    assert r["weights"]["C"] > r["weights"]["A"]


def test_bl_view_blends_toward_view():
    rets = _ret_byname(["A", "B"])
    caps = {"A": 10e12, "B": 1e12}  # A is the market giant
    equil = black_litterman_weights(rets, caps)
    # strong bullish view on B (the laggard): P=[-1,1], Q=+0.10, low Omega
    view = black_litterman_weights(
        rets, caps,
        views_p=[[-1.0, 1.0]],
        views_q=[0.10],
        view_uncertainty_omega=[0.01],
    )
    # the view should lift B's weight relative to equilibrium
    assert view["weights"]["B"] > equil["weights"]["B"]


def test_bl_degrades_equal_without_caps():
    rets = _ret_byname(["A", "B"])
    r = black_litterman_weights(rets, {})
    assert "equal-weight" in r.get("note", "")
    assert set(r["weights"]) == {"A", "B"}
