"""Cross-metric factor dispersion (FUND-15) and fundamental momentum (FUND-16).

Every assert is falsifiable: the expected number or ordering is written out, so
a change to the arithmetic - or to the declared ``MaximumPossibleStd``, ``n`` or
``w_i`` constants - fails the test rather than silently moving the score.
"""

from __future__ import annotations

import math

import pytest

from tradingagents.strategies.factor_dispersion import (
    FACTOR_SCORE_MAX,
    FACTOR_SCORE_NEUTRAL,
    MAXIMUM_POSSIBLE_STD,
    MOMENTUM_FACTOR_WEIGHTS,
    MOMENTUM_LAG,
    factor_score_dispersion,
    fundamental_momentum,
)

pytestmark = pytest.mark.timeout(600)


# --- FUND-15: cross-metric agreement / dispersion -------------------------


def test_maximum_possible_std_is_the_declared_bounded_scale_normaliser():
    # The library names MaximumPossibleStd and defines nothing; the module
    # declares (max - min) / 2 for the 0-100 factor-score scale. Pin the
    # declaration so a silent retune is caught.
    assert MAXIMUM_POSSIBLE_STD == (FACTOR_SCORE_MAX - 0.0) / 2.0
    assert pytest.approx(50.0) == MAXIMUM_POSSIBLE_STD
    assert pytest.approx(50.0) == FACTOR_SCORE_NEUTRAL


def test_dispersion_is_zero_for_identical_scores_and_grows_with_the_spread():
    identical = factor_score_dispersion({"a": 70.0, "b": 70.0, "c": 70.0})
    narrow = factor_score_dispersion({"a": 70.0, "b": 80.0})
    wide = factor_score_dispersion({"a": 50.0, "b": 90.0})

    assert identical["dispersion"] == pytest.approx(0.0)
    assert identical["reason"] is None
    # population sigma of {70, 80} is 5; of {50, 90} is 20.
    assert narrow["dispersion"] == pytest.approx(5.0)
    assert wide["dispersion"] == pytest.approx(20.0)
    assert wide["dispersion"] > narrow["dispersion"]


def test_agreement_is_the_library_formula_and_is_one_when_dispersion_is_zero():
    identical = factor_score_dispersion({"a": 70.0, "b": 70.0})
    spread = factor_score_dispersion({"a": 80.0, "b": 60.0, "c": 70.0, "d": 90.0})

    assert identical["agreement"] == pytest.approx(1.0)
    # 1 - 11.18034 / 50 for the spread vector.
    assert spread["dispersion"] == pytest.approx(math.sqrt(125.0))
    assert spread["agreement"] == pytest.approx(1.0 - math.sqrt(125.0) / 50.0)


def test_all_same_sign_scores_maximum_agreement_and_alternating_the_minimum():
    same_sign = {"roic": 80.0, "roe": 60.0, "fcf_margin": 70.0, "gross": 90.0}
    alternating = {"roic": 90.0, "roe": 10.0, "fcf_margin": 90.0, "accrual": 10.0}
    candidates = [
        same_sign,
        {"roic": 70.0, "roe": 70.0},
        {"roic": 80.0, "roe": 20.0},
        alternating,
    ]

    same = factor_score_dispersion(same_sign)
    alt = factor_score_dispersion(alternating)

    assert same["sign_agreement"] == pytest.approx(1.0)
    assert alt["sign_agreement"] == pytest.approx(0.5)
    shares = [factor_score_dispersion(c)["sign_agreement"] for c in candidates]
    assert alt["sign_agreement"] == pytest.approx(min(shares))
    assert alt["sign_agreement"] < same["sign_agreement"]


def test_fewer_than_two_scores_refuses_with_a_reason_never_zero():
    single = factor_score_dispersion({"roic": 90.0})
    empty = factor_score_dispersion({})
    missing = factor_score_dispersion({"roic": 90.0, "roe": None})

    for res in (single, empty, missing):
        assert res["dispersion"] is None
        assert res["agreement"] is None
        assert res["sign_agreement"] is None
        assert res["dispersion"] != 0
        assert res["reason"]

    assert single["n"] == 1
    assert missing["skipped"] == 1
    assert empty["reason"]


def test_non_finite_and_none_entries_are_skipped_not_counted_as_zero():
    res = factor_score_dispersion(
        {"a": 70.0, "b": None, "c": float("nan"), "d": 70.0, "e": "x"}
    )
    assert res["n"] == 2
    assert res["skipped"] == 3
    assert res["dispersion"] == pytest.approx(0.0)
    assert res["mean"] == pytest.approx(70.0)


def test_scale_width_must_be_positive():
    with pytest.raises(ValueError):
        factor_score_dispersion({"a": 1.0, "b": 2.0}, scale_min=1.0, scale_max=1.0)


# --- FUND-16: fundamental momentum, acceleration, stability ---------------


def test_declared_lag_and_weights_are_the_stated_choice():
    assert MOMENTUM_LAG == 1
    assert set(MOMENTUM_FACTOR_WEIGHTS) >= {
        "roic",
        "roe",
        "gross_margin",
        "operating_margin",
        "fcf_margin",
        "asset_turnover",
        "revenue_growth",
        "eps_growth",
    }
    assert set(MOMENTUM_FACTOR_WEIGHTS.values()) == {1.0}


def test_momentum_is_positive_for_a_rising_factor_and_negative_for_falling():
    rising = fundamental_momentum({"roic": [0.10, 0.12, 0.15]})
    falling = fundamental_momentum({"roic": [0.15, 0.12, 0.10]})

    assert rising["momentum"] == pytest.approx(0.03)
    assert rising["momentum"] > 0
    assert falling["momentum"] == pytest.approx(-0.02)
    assert falling["momentum"] < 0


def test_momentum_renormalises_the_declared_weights_over_present_factors():
    # equal declared weights -> the plain mean of the two changes.
    res = fundamental_momentum({"roic": [0.10, 0.20], "roe": [0.05, 0.15]})
    assert res["n_factors"] == 2
    assert res["momentum"] == pytest.approx(0.10)


def test_history_shorter_than_lag_plus_one_refuses_with_a_reason_never_zero():
    short = fundamental_momentum({"roic": [0.10]})
    too_short_for_lag = fundamental_momentum({"roic": [0.10, 0.20]}, lag=3)

    assert short["momentum"] is None
    assert short["momentum"] != 0
    assert short["reason"] and "2" in short["reason"]

    assert too_short_for_lag["momentum"] is None
    assert too_short_for_lag["momentum"] != 0
    assert too_short_for_lag["reason"] and "4" in too_short_for_lag["reason"]


def test_a_factor_with_too_little_history_is_skipped_and_the_rest_still_scores():
    res = fundamental_momentum({"roic": [0.10, 0.15], "roe": [0.20]})
    assert res["n_factors"] == 1
    assert res["momentum"] == pytest.approx(0.05)
    assert res["reason"] is None


def test_acceleration_is_the_second_difference():
    res = fundamental_momentum({"roic": [0.10, 0.13, 0.15]})
    # (0.15 - 0.13) - (0.13 - 0.10) = 0.02 - 0.03 = -0.01
    assert res["acceleration"] == pytest.approx(-0.01)
    # momentum itself is the last first difference.
    assert res["momentum"] == pytest.approx(0.02)


def test_acceleration_refuses_below_two_lag_plus_one_periods():
    res = fundamental_momentum({"roic": [0.10, 0.15]})
    assert res["momentum"] == pytest.approx(0.05)
    assert res["acceleration"] is None
    assert res["acceleration_reason"]


def test_stability_is_the_dispersion_of_the_per_factor_changes():
    res = fundamental_momentum({"roic": [0.10, 0.20], "roe": [0.30, 0.20]})
    # changes: +0.10 and -0.10 -> population sigma 0.10
    assert res["stability"] == pytest.approx(0.10)
    assert res["momentum"] == pytest.approx(0.0)


def test_stability_refuses_with_one_measurable_factor():
    res = fundamental_momentum({"roic": [0.10, 0.20]})
    assert res["stability"] is None
    assert res["stability_reason"]


def test_lag_must_be_at_least_one():
    with pytest.raises(ValueError):
        fundamental_momentum({"roic": [0.1, 0.2]}, lag=0)
