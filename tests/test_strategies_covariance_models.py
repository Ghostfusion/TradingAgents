"""Covariance modeling tests (six-pillar/master-catalog PART XVII; offline).

Yang-Zhang volatility (overnight+range, drift-independent), Ledoit-Wolf
shrinkage (scaled-identity + diag targets) and RiskMetrics EWMA covariance.
All pure/NumPy over synthetic input; hermetic.
"""

import math

import numpy as np
import pytest

from tradingagents.strategies.covariance_models import (
    ewma_covariance,
    ledoit_wolf_shrink,
)
from tradingagents.strategies.volatility_models import yang_zhang_vol

pytestmark = pytest.mark.timeout(120)


# --- Yang-Zhang ---


def _flat_ohlc(n=60, base=100.0, day_range=2.0):
    return (
        [base] * n,
        [base + day_range] * n,
        [base - day_range] * n,
        [base] * n,
    )


def test_yang_zhang_flat_range_recovers_formula():
    o, h, lo, c = _flat_ohlc(n=60, base=100.0, day_range=2.0)
    v = yang_zhang_vol(o, h, lo, c)
    assert v is not None
    # Flat OHLC: overnight leg 0, intraday leg 0, only the Rogers-Satchell
    # range term contributes: var = (1-k) * mean(ln(H/C)ln(H/O)+ln(L/C)ln(L/O)).
    m = 59
    k = 0.34 / (1.34 + (m + 1.0) / (m - 1.0))
    rs_row = math.log(102.0 / 100.0) ** 2 + math.log(98.0 / 100.0) ** 2
    expected = math.sqrt((1.0 - k) * rs_row * 252.0)
    assert v == pytest.approx(expected, rel=1e-9)


def test_yang_zhang_captures_overnight_gap():
    """A one-day overnight gap (open jumps vs prior close) must raise the
    Yang-Zhang estimate vs the no-gap flat series — the overnight leg is what
    makes YZ complete over the day."""
    o, h, lo, c = _flat_ohlc(n=60)
    v_flat = yang_zhang_vol(o, h, lo, c)
    o2 = list(o)
    o2[30] = 105.0  # overnight gap into day 30
    v_gap = yang_zhang_vol(o2, h, lo, c)
    assert v_flat is not None and v_gap is not None
    assert v_gap > v_flat


def test_yang_zhang_insufficient_degenerate_none():
    assert yang_zhang_vol([], [], [], []) is None
    assert yang_zhang_vol([100.0] * 2, [101.0] * 2, [99.0] * 2, [100.0] * 2) is None  # < 3 bars


# --- Ledoit-Wolf ---


def _block_returns(n_obs=80, names=8, base=1e-4, seed=3):
    rng = np.random.default_rng(seed)
    # Two correlated blocks + one orphan; a realistic N~T regime.
    groups = {0: [0, 1, 2, 3], 1: [4, 5, 6], 2: [7]}
    rets = {}
    for name_i in range(names):
        r = rng.normal(base, 0.01, n_obs)
        for gi, members in groups.items():
            if name_i in members:
                r += rng.normal(0.0, 0.005, n_obs) if gi < 2 else 0.0
        rets[f"N{name_i}"] = list(r)
    return rets


def test_lw_shrinkage_in_unit_interval_and_shrinks():
    rets = _block_returns()
    r = ledoit_wolf_shrink(rets)
    assert r["cov"] is not None
    assert 0.0 <= r["shrinkage"] <= 1.0
    assert r["n_names"] == 8 and r["n_obs"] == 80
    # Sample covariance from numpy directly to confirm the shrunk matrix is
    # the claimed convex combination (delta = b^2/d^2 clipped).
    names = r["names"]
    mat = np.array([rets[n][-80:] for n in names], dtype=float).T
    mat = mat - mat.mean(axis=0, keepdims=True)
    S = (mat.T @ mat) / 80
    mu = np.trace(S) / 8
    T = mu * np.eye(8)
    outer = np.einsum("ni,nj->nij", mat, mat)
    b2 = np.mean(np.sum((outer - S) ** 2, axis=(1, 2)))
    d2 = np.sum((S - T) ** 2)
    expected_delta = 0.0 if d2 <= 0 else min(max(b2 / d2, 0.0), 1.0)
    expected = (1 - expected_delta) * S + expected_delta * T
    assert r["shrinkage"] == pytest.approx(expected_delta, abs=1e-6)
    np.testing.assert_allclose(np.array(r["cov"]), expected, atol=1e-12)


def test_lw_diag_target_preserves_diagonal():
    rets = _block_returns()
    r = ledoit_wolf_shrink(rets, target="diag")
    assert r["cov"] is not None
    diag = [r["cov"][i][i] for i in range(r["n_names"])]
    assert all(d > 0 for d in diag)
    # Diag target: the target equals the sample diagonal exactly, so the
    # shrunk diagonal is the sample diagonal (MLE convention) regardless of
    # the shrinkage intensity.
    names = r["names"]
    mat = np.array([rets[n][-80:] for n in names], dtype=float)
    sample_diag = [float(np.var(row)) for row in mat]  # MLE: divide by n
    for i, sv in enumerate(sample_diag):
        assert diag[i] == pytest.approx(sv, rel=1e-6)


def test_lw_insufficient_none():
    assert ledoit_wolf_shrink({})["cov"] is None
    assert ledoit_wolf_shrink({"A": [0.01] * 10, "B": [0.01] * 10})["cov"] is None  # too short
    assert ledoit_wolf_shrink({"A": [0.01] * 60})["cov"] is None  # < 2 names


# --- EWMA covariance ---


def test_ewma_covariance_flat_series_vol_approx():
    import random as _r

    rng = _r.Random(5)
    a = [round(rng.uniform(-0.01, 0.01), 6) for _ in range(60)]
    b = [-x for x in a]  # perfect mirror
    r = ewma_covariance({"A": a, "B": b}, seed_window=20)
    assert r["cov"] is not None
    # Mirror series: same vol, strongly negative covariance.
    v_a = math.sqrt(r["cov"][0][0]) * math.sqrt(252)
    v_b = math.sqrt(r["cov"][1][1]) * math.sqrt(252)
    assert v_a == pytest.approx(v_b, rel=1e-6)
    assert r["cov"][0][1] < 0
    # Covariance ~= -variance (perfectly anti-correlated).
    assert r["cov"][0][1] == pytest.approx(-r["cov"][0][0], rel=1e-4)


def test_ewma_covariance_degenerate_none():
    assert ewma_covariance({})["cov"] is None
    assert ewma_covariance({"A": [0.01] * 5, "B": [0.01] * 5})["cov"] is None  # too short
