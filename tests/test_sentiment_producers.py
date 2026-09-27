"""Tests for the SENT-7/9/10/11 sentiment producers (arithmetic, not wiring)."""

import pytest

from tradingagents.strategies.sentiment import (
    effective_sample_size,
    event_study,
    gini_coefficient,
    herfindahl_index,
    negation_adjusted_polarity,
    sentiment_asymmetry,
    sentiment_output_map,
    sentiment_uncertainty,
    source_breadth,
)

pytestmark = pytest.mark.timeout(600)


# ---------------------------------------------------------------------------
# SENT-9 - volume / attention
# ---------------------------------------------------------------------------


def test_kish_effective_sample_size_equals_n_for_equal_weights():
    out = effective_sample_size([1.0, 1.0, 1.0, 1.0])
    assert out["n_eff"] == 4.0
    assert out["n"] == 4


def test_kish_effective_sample_size_shrinks_with_unequal_weights():
    # (1+1+1+3)^2 / (1+1+1+9) = 36/12 = 3.0
    out = effective_sample_size([1.0, 1.0, 1.0, 3.0])
    assert out["n_eff"] == pytest.approx(3.0)


def test_kish_effective_sample_size_refuses_without_positive_weight():
    out = effective_sample_size([])
    assert out["n_eff"] is None
    assert "reason" in out


def test_hhi_of_single_source_is_one():
    out = herfindahl_index([7])
    assert out["hhi"] == pytest.approx(1.0)
    assert out["effective_n"] == pytest.approx(1.0)


def test_hhi_of_equal_sources_is_inverse_n():
    out = herfindahl_index([1, 1, 1, 1])
    assert out["hhi"] == pytest.approx(0.25)
    assert out["effective_n"] == pytest.approx(4.0)


def test_gini_of_equal_vector_is_zero():
    out = gini_coefficient([5, 5, 5, 5, 5])
    assert out["gini"] == pytest.approx(0.0)


def test_gini_hand_computed_unequal_vector():
    # sorted [1,1,1,7], n=4, total=10 -> 18/(4*10) = 0.45
    out = gini_coefficient([7, 1, 1, 1])
    assert out["gini"] == pytest.approx(0.45)


def test_gini_refuses_below_two_items():
    out = gini_coefficient([5])
    assert out["gini"] is None
    assert "reason" in out


def test_source_breadth_single_source_is_low_not_refusal():
    out = source_breadth({"reuters": 5})
    assert out["single_source"] is True
    assert out["n_sources"] == 1
    assert out["breadth"] == pytest.approx(0.2)
    assert out["independence"] == pytest.approx(0.0)
    assert "one source" in out["basis"]


def test_source_breadth_multiple_sources():
    out = source_breadth({"a": 1, "b": 1, "c": 1, "d": 1})
    assert out["single_source"] is False
    assert out["n_sources"] == 4
    assert out["breadth"] == pytest.approx(1.0)
    assert out["independence"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# SENT-7 - negation window and intensifier
# ---------------------------------------------------------------------------


def test_negation_window_flips_polarity():
    out = negation_adjusted_polarity("the results are not good")
    assert out["polarity"] == pytest.approx(-1.0)
    assert out["negated_terms"] == 1


def test_negation_outside_window_does_not_flip():
    # "not" sits four tokens before "good": outside the default window of 3,
    # so the polarity stays positive.
    out = negation_adjusted_polarity("not the results are really good")
    assert out["polarity"] > 0.0
    assert out["negated_terms"] == 0


def test_intensifier_raises_magnitude():
    plain = negation_adjusted_polarity("good")
    boosted = negation_adjusted_polarity("very good")
    assert plain["polarity"] == pytest.approx(1.0)
    assert boosted["polarity"] == pytest.approx(1.5)
    assert abs(boosted["polarity"]) > abs(plain["polarity"])


def test_negation_adjusted_polarity_refuses_without_terms():
    out = negation_adjusted_polarity("the quick brown fox")
    assert out["polarity"] is None
    assert "reason" in out


# ---------------------------------------------------------------------------
# SENT-10 - asymmetry split and event study
# ---------------------------------------------------------------------------


def test_asymmetry_is_zero_for_symmetric_series():
    out = sentiment_asymmetry([-0.5, 0.5, -0.5, 0.5])
    assert out["asymmetry"] == pytest.approx(0.0)
    assert out["upside"] == pytest.approx(out["downside"])


def test_asymmetry_positive_for_upside_skewed_series():
    out = sentiment_asymmetry([0.8, 0.6, -0.2])
    assert out["asymmetry"] > 0.0


def test_event_study_hand_computed_five_point_series():
    out = event_study([0.1, 0.2, 0.3, 0.4, 0.5], 2, window=2)
    assert out["baseline"] == pytest.approx(0.15)
    assert out["abnormal"] == [pytest.approx(0.15), pytest.approx(0.25)]
    assert out["car"] == pytest.approx(0.4)
    assert out["mean_car"] == pytest.approx(0.2)


def test_event_study_refuses_when_window_does_not_fit():
    out = event_study([0.1, 0.2, 0.3], 2, window=3)
    assert out["car"] is None
    assert "reason" in out


# ---------------------------------------------------------------------------
# SENT-11 - uncertainty model and output map
# ---------------------------------------------------------------------------


def test_uncertainty_confidence_is_one_for_a_point_mass():
    out = sentiment_uncertainty([0.0, 0.0, 0.0, 0.0, 0.0])
    assert out["entropy"] == pytest.approx(0.0)
    assert out["confidence"] == pytest.approx(1.0)
    assert out["uncertainty"] == pytest.approx(0.0)


def test_uncertainty_falls_when_the_series_spreads():
    tight = sentiment_uncertainty([0.0, 0.0, 0.0, 0.0, 0.0])
    spread = sentiment_uncertainty([-0.9, -0.4, 0.0, 0.4, 0.9])
    assert spread["entropy_norm"] > tight["entropy_norm"]
    assert spread["confidence"] < tight["confidence"]


def test_uncertainty_refuses_below_point_floor():
    out = sentiment_uncertainty([0.1, 0.2])
    assert out["confidence"] is None
    assert "reason" in out


def test_output_map_carries_name_and_raw_value():
    for kind in ("phi", "logistic", "tanh"):
        out = sentiment_output_map(0.0, kind=kind)
        assert out["map"] == kind
        assert out["raw"] == pytest.approx(0.0)
        assert out["confidence"] == pytest.approx(0.5)
    out = sentiment_output_map(2.0, kind="tanh")
    assert out["raw"] == pytest.approx(2.0)
    assert 0.0 < out["confidence"] < 1.0


def test_output_map_refuses_unknown_kind():
    out = sentiment_output_map(1.0, kind="sqrt")
    assert out["confidence"] is None
    assert "reason" in out
