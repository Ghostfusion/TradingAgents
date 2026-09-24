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


def _with_long_regime(n_pre=140, n_regime=120, n_post=60, seed=202, jump=10.0):
    """Unit noise carrying one manufactured long regime (a +jump stretch)."""
    base = _gauss(n_pre + n_regime + n_post, seed=seed)
    return (
        base[:n_pre]
        + [v + jump for v in base[n_pre:n_pre + n_regime]]
        + base[n_pre + n_regime:]
    )


def _equal_regimes(block=80, seed=202, jump=10.0):
    """Three manufactured regimes of exactly the same length."""
    return _with_long_regime(n_pre=block, n_regime=block, n_post=block,
                             seed=seed, jump=jump)


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
# R1: a duration-law hazard instead of the constant hazard
# --------------------------------------------------------------------------


def test_bocpd_constant_hazard_mode_is_unchanged():
    # the duration-law addition must not move the constant-hazard read: exact
    # values for fixed series, in the style of the cusum/ewma pins below
    out = regime.bocpd(_gauss(240))
    assert out["zero_run_prob"] == 0.01465
    assert out["expected_run_length"] == 160.0563
    assert out["map_run_length"] == 240
    assert out["hazard"] == 1 / 60
    assert regime.bocpd(_gauss(60), hazard=1 / 20)["zero_run_prob"] == 0.031843


def test_hazard_mode_lognormal_is_run_length_dependent():
    series = _with_long_regime()

    constant = regime.bocpd(series)
    lognormal = regime.bocpd(series, hazard_mode="lognormal")
    assert constant["hazard_mode"] == "constant"
    assert lognormal["hazard_mode"] == "lognormal"

    # the hazard varies with the run length instead of being one scalar: a
    # regime is no longer as likely to end on its first day as on its longest
    curve = lognormal["hazard_curve"]
    assert len(set(curve.values())) > 1
    assert curve[0] < curve[max(curve)]

    # ... because the law was compiled from the run lengths observed so far
    law = lognormal["duration_params"]
    assert law["law"] == "lognormal"
    assert law["n_runs"] >= 2

    # the different hazard moves the read off the constant-hazard one
    assert lognormal["zero_run_prob"] != constant["zero_run_prob"]

    # the covering metric travels beside zero_run_prob, against the read the
    # duration law replaces
    covering = lognormal["covering"]
    assert covering["metric"] == "length_weighted_jaccard"
    assert covering["reference"] == "constant_hazard"
    assert 0.0 <= covering["value"] <= 1.0


def test_bocpd_duration_law_is_inert_until_two_runs_are_observed():
    series = _gauss(240)  # stationary: one open run, no completed one
    out = regime.bocpd(series, hazard_mode="lognormal")
    assert out["duration_params"] is None  # nothing observed -> nothing fitted
    assert len(set(out["hazard_curve"].values())) == 1
    # the declared scalar hazard governs, so the read matches the constant one
    assert out["zero_run_prob"] == regime.bocpd(series)["zero_run_prob"]


def test_bocpd_hazard_mode_degenerate_fit_is_none():
    # three manufactured regimes of exactly equal length: every observed run
    # length is then the same, so the fitted log-normal and Pareto have zero
    # spread and the read refuses rather than substituting the constant hazard
    # - the same None path an out-of-range hazard takes
    equal = _equal_regimes()
    assert regime.bocpd(equal, hazard_mode="lognormal") is None
    assert regime.bocpd(equal, hazard_mode="pareto") is None

    # the same series under a law with no spread parameter: identified, and the
    # hazard applied is the fitted one, not the scalar prior
    geometric = regime.bocpd(equal, hazard_mode="geometric")
    assert geometric is not None
    assert geometric["duration_params"]["law"] == "geometric"
    assert len(set(geometric["hazard_curve"].values())) == 1
    assert geometric["hazard_curve"][0] == geometric["duration_params"]["p"]
    assert geometric["hazard_curve"][0] != geometric["hazard"]


def test_bocpd_unknown_hazard_mode_is_none():
    # a mode the module cannot compile is refused, never read as constant
    assert regime.bocpd(_gauss(60), hazard_mode="geometrico") is None


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
