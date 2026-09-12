"""Unit tests for regime.bocpd (Bayesian online change-point detection).

BOCPD is a pure calculator added next to cusum/ewma_control; these tests pin
its observable contract (change alarm at the manufactured index, silence on a
stationary series, degenerate-input handling) and guard that the pre-existing
shift detectors are byte-identical.
"""

import random

from tradingagents.strategies import regime


def _gauss(n, seed=101, scale=1.0):
    rnd = random.Random(seed)
    return [rnd.gauss(0.0, scale) for _ in range(n)]


# --------------------------------------------------------------------------
# Degenerate input -> None
# --------------------------------------------------------------------------


def test_bocpd_short_series_none():
    assert regime.bocpd([0.01, -0.01, 0.02]) is None


def test_bocpd_constant_series_none():
    # zero-variance warmup baseline -> no scale to standardise against
    assert regime.bocpd([0.01] * 50) is None


def test_bocpd_invalid_hazard_none():
    assert regime.bocpd(_gauss(60), hazard=0.0) is None
    assert regime.bocpd(_gauss(60), hazard=1.0) is None


# --------------------------------------------------------------------------
# Stationary series: no alarm, run length tracks the full sample
# --------------------------------------------------------------------------


def test_bocpd_stationary_does_not_flag_shift():
    out = regime.bocpd(_gauss(240))
    assert out is not None
    assert out["shift"] is False
    assert out["zero_run_prob"] < regime.BOCPD_SHIFT_THRESHOLD
    assert out["n"] == 240


def test_bocpd_map_run_length_grows_with_series():
    series = _gauss(240)
    short = regime.bocpd(series[:80])
    long = regime.bocpd(series)
    assert short["map_run_length"] < long["map_run_length"]
    # a stationary series never restarts: the mode sits at the full sample
    assert long["map_run_length"] == 240


def test_bocpd_deterministic():
    series = _gauss(120)
    assert regime.bocpd(series) == regime.bocpd(series)


def test_bocpd_basis_and_echo_fields():
    out = regime.bocpd(_gauss(60), hazard=1 / 20)
    assert isinstance(out["basis"], str) and out["basis"]
    assert out["hazard"] == 1 / 20
    assert out["n"] == 60


# --------------------------------------------------------------------------
# Manufactured level shift: alarm at the first post-shift sample
# --------------------------------------------------------------------------


def test_bocpd_flags_shift_at_the_manufactured_index():
    base = _gauss(160, seed=101)  # ~N(0, 1) pre-shift
    idx = 100
    # 12-sigma level shift from idx onward: large enough to clear the 0.5 Bayes
    # cut under the default 1/60 hazard (which spreads prior mass over short
    # runs that can partially explain a smaller jump).
    shifted = base[:idx] + [v + 12.0 for v in base[idx:]]

    # last pre-shift sample is still read as one continuous segment
    pre = regime.bocpd(shifted[:idx])
    assert pre["shift"] is False

    # the first shifted sample restarts the segment: the alarm appears exactly
    # at the manufactured index, as a run-length-0 read
    post = regime.bocpd(shifted[: idx + 1])
    assert post["shift"] is True
    assert post["zero_run_prob"] > pre["zero_run_prob"]
    assert post["map_run_length"] == 0

    # ... and nothing alarms on any earlier prefix
    assert not any(regime.bocpd(shifted[:k])["shift"] for k in range(20, idx))


# --------------------------------------------------------------------------
# Pre-existing shift detectors are untouched by the BOCPD addition
# --------------------------------------------------------------------------


def test_cusum_output_unchanged():
    series = [0.005, -0.005] * 10 + [0.06] * 10
    assert regime.cusum(series) == {
        "mu0": 0.0,
        "sigma": 0.00527,
        "k": 0.002635,
        "h": 0.026352,
        "signal": "up",
        "signal_at": 20,
        "max_cusum": 0.573648,
    }


def test_ewma_control_output_unchanged():
    series = [0.0] * 8 + [0.05] * 12
    assert regime.ewma_control(series) == {
        "mu0": 0.03,
        "sigma": 0.025131,
        "lambda": 0.2,
        "L": 3.0,
        "signal": "down",
        "signal_at": 7,
        "last_z": 0.04691,
    }
