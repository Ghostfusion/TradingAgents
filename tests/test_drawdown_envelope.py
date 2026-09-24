"""K2 (2608.00127): four drawdown expectations and the T^(H-1/2) rescaling.

The engine measures the realized drawdown and cannot say how deep or how long a
drawdown at a given Sharpe SHOULD run. ``drawdown_envelope`` reports four
separate expectations; the paper's point is that a Gaussian table conflates them
and that under long memory the maximum-drawdown amplification is dispersion
scaling ``T^(H - 1/2)``, not path geometry.

Offline and deterministic: the Monte-Carlo table uses a fixed seed, so every
number here is stable across runs. Assertions are tolerant to the table's own
resolution (tolerance bands, never exact floats that float noise can move).
"""

from __future__ import annotations

import math

import pytest

from tradingagents.dataflows.config import get_config, reset_config, set_config
from tradingagents.strategies.book_risk import drawdown_envelope
from tradingagents.strategies.evaluate import benchmark_table

HORIZON = 252


def test_hurst_rescales_mdd():
    """At H > 0.5 the p90 maximum drawdown scales as T^(H-1/2), not T^(1/2).

    With no Hurst estimate the envelope uses the square-root-of-time convention
    and says so (``hurst: "assumed"``).
    """
    skew, kurt = -0.6, 6.0
    assumed = drawdown_envelope(1.0, HORIZON, skew, kurt, None)
    assert assumed["hurst"] == "assumed"
    assert assumed["hurst_scale"] == 1.0

    h = 0.72
    scaled = drawdown_envelope(1.0, HORIZON, skew, kurt, h)
    assert scaled["hurst"] == pytest.approx(h)
    assert scaled["hurst_exponent"] == pytest.approx(h - 0.5)

    ratio = scaled["mdd_p90"] / assumed["mdd_p90"]
    assert ratio == pytest.approx(HORIZON ** (h - 0.5), rel=1e-9)
    # it is NOT the square-root-of-time amplification the convention would apply
    assert ratio != pytest.approx(math.sqrt(HORIZON), rel=1e-3)

    # and a mean-reverting book (H < 0.5) shrinks the same way
    shrunk = drawdown_envelope(1.0, HORIZON, skew, kurt, 0.35)
    assert shrunk["mdd_p90"] < assumed["mdd_p90"]


def test_the_four_measures_move_independently_with_skew_and_kurtosis():
    """The four expectations are not one Gaussian table: their orderings differ."""
    grid = [(0.0, 3.0), (-1.0, 6.0), (0.5, 9.0), (-1.5, 12.0)]
    envs = [drawdown_envelope(1.0, HORIZON, sk, ku, None) for sk, ku in grid]
    mdd = [e["mdd_p90"] for e in envs]
    ml = [e["max_loss"] for e in envs]
    tuw = [e["time_under_water"] for e in envs]
    lr = [e["longest_recovery"] for e in envs]

    def _non_decreasing(xs):
        return all(xs[i] <= xs[i + 1] + 1e-9 for i in range(len(xs) - 1))

    # depth grows monotonically as the left tail fattens...
    assert _non_decreasing(mdd)
    assert _non_decreasing(ml)
    # ...but the duration measures do not track it, so no single table reproduces
    # all four (they are separate expectations, not one amplified number)
    assert not _non_decreasing(tuw)
    assert not _non_decreasing(lr)


def test_the_envelope_carries_the_sharpes_estimation_uncertainty():
    env = drawdown_envelope(1.0, HORIZON, 0.0, 3.0, None)
    u = env["sharpe_uncertainty"]
    assert u is not None and u["se"] > 0.0
    assert u["n"] == HORIZON
    assert u["ci95"][0] < 1.0 < u["ci95"][1]
    assert "Lo (2002)" in u["method"]

    # no Sharpe -> no envelope and no uncertainty, never a fabricated number
    none = drawdown_envelope(None, HORIZON)
    assert none["status"] == "unavailable"
    assert none["mdd_p90"] is None and none["sharpe_uncertainty"] is None
    assert drawdown_envelope(1.0, 1)["status"] == "unavailable"


def test_the_envelope_is_deterministic():
    a = drawdown_envelope(0.8, 126, -0.4, 5.0, 0.6)
    b = drawdown_envelope(0.8, 126, -0.4, 5.0, 0.6)
    assert a == b


def _series(n: int = 220, seed: int = 3) -> list[float]:
    import random

    rng = random.Random(seed)
    return [rng.gauss(0.0006, 0.011) for _ in range(n)]


def test_the_envelope_is_reported_beside_the_realized_drawdown_only_when_gated():
    """The row gains the EXPECTED envelope only behind ``enable_drawdown_envelope``.

    The governor leg is deliberately NOT wired (the mandate answer on letting the
    ``T^(H-1/2)`` rescaling reach ``risk_governor`` is still open), so the
    consumer is the evaluation row that already prints a Sharpe and a realized
    ``max_drawdown``.
    """
    saved = dict(get_config() or {})
    rets = _series()
    try:
        set_config({**saved, "enable_drawdown_envelope": False})
        off = benchmark_table(rets, rets)
        assert off["rows"] and all("drawdown_envelope" not in r for r in off["rows"])

        set_config({**saved, "enable_drawdown_envelope": True})
        on = benchmark_table(rets, rets)
        assert on["rows"] and all("drawdown_envelope" in r for r in on["rows"])
        env = on["rows"][0]["drawdown_envelope"]
        assert env["status"] == "ok"
        for key in ("mdd_median", "mdd_p90", "max_loss", "time_under_water",
                    "longest_recovery"):
            assert env[key] is not None
        assert env["sharpe_uncertainty"] is not None
    finally:
        reset_config()
