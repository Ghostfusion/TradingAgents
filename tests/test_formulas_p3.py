"""P3 tests: Kyle lambda (daily-bar impact slope) + multi-asset Kelly (offline)."""

import random

import pytest

from tradingagents.strategies.liquidity_risk import kyle_lambda
from tradingagents.strategies.portfolio import (
    allocation_block,
    kelly_weights,
)

pytestmark = pytest.mark.timeout(120)


# --- Kyle lambda ---


def test_kyle_lambda_positive_for_ordered_flow():
    """A series where price rises on high volume (and falls on low) reads a
    positive impact slope (larger lambda = thinner book)."""
    closes = [100.0]
    volumes = []
    rng = random.Random(2)
    for _ in range(80):
        v = rng.uniform(1e5, 1e6)
        if v > 5e5:
            closes.append(closes[-1] * (1 + 0.002))
        else:
            closes.append(closes[-1] * (1 - 0.002))
        volumes.append(v)
    lam = kyle_lambda(closes, volumes)
    assert lam is not None and lam > 0


def test_kyle_lambda_high_volume_lower_impact():
    """Same signed-move pattern but higher volume scale -> the per-unit flow
    slope is smaller (more liquid)."""
    rng = random.Random(3)
    closes_lo = [100.0]
    closes_hi = [100.0]
    vols_lo = []
    vols_hi = []
    for _ in range(80):
        v_lo = rng.uniform(1e4, 1e5)
        v_hi = v_lo * 100.0
        if v_lo > 5e4:
            closes_lo.append(closes_lo[-1] * 1.002)
            closes_hi.append(closes_hi[-1] * 1.002)
        else:
            closes_lo.append(closes_lo[-1] * 0.998)
            closes_hi.append(closes_hi[-1] * 0.998)
        vols_lo.append(v_lo)
        vols_hi.append(v_hi)
    lam_lo = kyle_lambda(closes_lo, vols_lo)
    lam_hi = kyle_lambda(closes_hi, vols_hi)
    assert lam_lo is not None and lam_hi is not None
    # Per-unit signed volume: 100x volume ~ 100x smaller lambda.
    assert lam_hi < lam_lo * 0.1


def test_kyle_lambda_degenerate_none():
    assert kyle_lambda([100.0] * 5, [1e5] * 5) is None  # too short
    assert kyle_lambda([100.0] * 40, [1e5] * 40) is None  # zero return variance


# --- Multi-asset Kelly ---


def test_kelly_single_asset_reduces_to_scalar_fraction():
    """For one name, w* = (mu - rf)/sigma^2; fractional Kelly x0.25 and
    normalized -> the same portfolio of one name (weight 1) with the sign of
    the raw exposure preserved.
    """
    rng = random.Random(4)
    mu = {"A": 0.10, "B": 0.08}
    rets = {
        "A": [rng.gauss(0.0002, 0.01) for _ in range(200)],
        "B": [rng.gauss(0.0001, 0.01) for _ in range(200)],
    }
    w = kelly_weights(mu, rets, fraction=0.25)
    assert set(w) == {"A", "B"}
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
    # The higher-mu name gets more weight (both same vol here).
    assert w["A"] > w["B"]

    # Single name: the multi-asset solver needs >= 2 names (the repo's
    # one-name Kelly is the scalar size.py path); degrade empty, never fake.
    w1 = kelly_weights({"A": 0.10}, rets, fraction=0.25)
    assert w1 == {}


def test_kelly_negative_mu_clips_to_zero():
    """A name whose excess return is negative cannot take a long position:
    the negative full weight is clipped, the rest renormalized."""
    rng = random.Random(5)
    rets = {"A": [rng.gauss(0.0, 0.01) for _ in range(200)],
            "B": [rng.gauss(0.0, 0.01) for _ in range(200)],
            "C": [rng.gauss(0.0, 0.01) for _ in range(200)]}
    # mu_B negative, mu_A/mu_C positive.
    w = kelly_weights({"A": 0.05, "B": -0.02, "C": 0.03}, rets, fraction=0.25)
    assert w["B"] == 0.0
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_kelly_degenerate_none():
    assert kelly_weights({}, {}) == {}
    assert kelly_weights({"A": 0.05}, {"A": [0.01] * 5}) == {}  # < 2 names


def test_allocation_block_kelly_flag_uses_kelly():
    """The allocation plan switches to Kelly weights when enable_kelly_alloc
    is on and return series are provided (advisory; the value-ratio baseline
    stays the default)."""
    scores = {"A": 50.0, "B": 30.0, "C": 20.0}
    cfg = {"enable_kelly_alloc": True, "kelly_alloc_fraction": 0.25,
           "max_name_weight": 1.0, "sector_cap_limit": 1.0, "max_book_names": 3}
    rng = random.Random(6)
    returns_by_name = {
        "A": [rng.gauss(0.0005, 0.01) for _ in range(200)],
        "B": [rng.gauss(0.0002, 0.01) for _ in range(200)],
        "C": [rng.gauss(0.0, 0.01) for _ in range(200)],
    }
    out = allocation_block(scores, cfg=cfg, returns_by_name=returns_by_name)
    assert "kelly weights" in out
    out_off = allocation_block(scores, cfg={"max_name_weight": 1.0, "sector_cap_limit": 1.0, "max_book_names": 3}, returns_by_name=returns_by_name)
    assert "kelly weights" not in out_off
