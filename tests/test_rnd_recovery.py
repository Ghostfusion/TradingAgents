"""V3 - risk-neutral density recovery from a covered option chain (2512.xxxx).

A density recovered from a chain whose covered strikes cannot identify it is a
fabrication, so the **failing-first** test is
``test_sparse_chain_returns_unavailable_not_a_density``: a tight cluster of
strikes whose conditioning spectrum is too poor must return ``unavailable`` with
``density is None`` and the conditioning number reported - the mutation that drops
the conditioning flag returns a fitted density and fails it.

There is no live option chain in the suite: the chains are synthetic and built
from a known two-component lognormal mixture, so the fit has a ground truth and
the test is fully deterministic.
"""

import math

import numpy as np
import pytest

from tradingagents.strategies.rnd_recovery import (
    RND_MAX_CONDITION,
    rnd_recovery,
)

pytestmark = pytest.mark.timeout(120)

FORWARD = 100.0
EXPIRY = 0.25
#: The ground-truth mixture the synthetic chains are priced from.
TRUTH = (0.55, -0.05, 0.12, 0.34)
#: A full span: OTM puts and calls reaching well past the mixture's tails.
FULL_STRIKES = np.arange(60.0, 160.1, 2.5)
#: A tight cluster a few percent either side of the forward - it cannot identify
#: the density's wings, so its conditioning spectrum is poor.
SPARSE_STRIKES = [97.0, 99.0, 101.0, 103.0]


def _ncdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _black76(forward: float, strike: float, t: float, vol: float,
             put: bool) -> float:
    d1 = (math.log(forward / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if put:
        return strike * _ncdf(-d2) - forward * _ncdf(-d1)
    return forward * _ncdf(d1) - strike * _ncdf(d2)


def _mix_price(strike: float, params, put: bool) -> float:
    w, a1, s1, s2 = params
    a2 = math.log((1.0 - w * math.exp(a1)) / (1.0 - w))
    return (w * _black76(FORWARD * math.exp(a1), strike, EXPIRY, s1, put)
            + (1.0 - w) * _black76(FORWARD * math.exp(a2), strike, EXPIRY, s2, put))


def _chain(strikes) -> dict:
    ks = [float(k) for k in strikes]
    return {
        "strikes": ks,
        "calls": [_mix_price(k, TRUTH, False) for k in ks],
        "puts": [_mix_price(k, TRUTH, True) for k in ks],
        "forward": FORWARD,
        "t": EXPIRY,
        "r": 0.0,
    }


def _pdf(grid, components) -> np.ndarray:
    """The mixture PDF on ``grid``, rebuilt from the returned components."""
    out = np.zeros_like(grid)
    for comp in components:
        mu = float(comp["forward"])
        s = float(comp["log_vol"])
        w = float(comp["weight"])
        z = (np.log(grid) - math.log(mu) + 0.5 * s * s) / s
        out += w * np.exp(-0.5 * z * z) / (grid * s * math.sqrt(2.0 * math.pi))
    return out


# --------------------------------------------------------------------------
# the card's failing-first test
# --------------------------------------------------------------------------


def test_sparse_chain_returns_unavailable_not_a_density() -> None:
    """A cluster of strikes that cannot identify the density refuses, with numbers.

    The four strikes sit within 3% of the forward, so the price-sensitivity
    matrix is ill-conditioned: the least-determined density direction is resolved
    far worse than the declared basis allows. The result must be
    ``unavailable`` with ``density is None`` and the conditioning spectrum
    reported - never a fitted density a few basis points of quote noise would
    move.
    """
    read = rnd_recovery(_chain(SPARSE_STRIKES))

    assert read["status"] == "unavailable"
    assert read["density"] is None
    assert read["method"]
    # the conditioning number travels WITH the refusal, and exceeds the basis
    cond = read["conditioning"]
    assert cond is not None
    assert cond["condition_number"] is not None
    assert cond["condition_number"] > RND_MAX_CONDITION
    assert cond["identifiable"] is False
    assert "do not identify the density" in read["unavailable"]
    assert cond["n_otm"] == len(SPARSE_STRIKES)


# --------------------------------------------------------------------------
# acceptance: a full span integrates to one and matches the forward
# --------------------------------------------------------------------------


def test_full_chain_density_integrates_to_one_and_matches_forward() -> None:
    """On a full span the density integrates to one and its mean is the forward."""
    read = rnd_recovery(_chain(FULL_STRIKES))

    assert read["status"] == "ok"
    density = read["density"]
    assert density is not None
    assert read["conditioning"]["identifiable"] is True
    assert read["conditioning"]["rank"] == 4

    grid = np.exp(np.linspace(math.log(FORWARD) - 2.0, math.log(FORWARD) + 2.0, 400_000))
    pdf = _pdf(grid, density["components"])
    integral = float(np.trapezoid(pdf, grid))
    mean = float(np.trapezoid(grid * pdf, grid))

    assert integral == pytest.approx(1.0, abs=1e-6)
    assert mean == pytest.approx(FORWARD, rel=1e-6)  # the forward constraint

    # the decision functionals are all present and finite
    assert 0.0 < density["quantile_01"] < FORWARD
    assert density["risk_neutral_variance"] > 0.0
    assert 0.0 < density["tail_probability"] < 1.0


def test_rnd_recovery_is_deterministic() -> None:
    assert rnd_recovery(_chain(FULL_STRIKES)) == rnd_recovery(_chain(FULL_STRIKES))


def test_a_chain_with_too_few_otm_quotes_refuses() -> None:
    read = rnd_recovery(_chain([98.0, 99.0, 101.0]))
    assert read["status"] == "unavailable"
    assert read["density"] is None
