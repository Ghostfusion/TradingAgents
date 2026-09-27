"""Tests for the absent technical producers of MASTER_PLAN §5.

Covers:

* the Keltner/Bollinger squeeze-momentum leg (TechnicalScore library §109/§110)
  in ``technical_factors.squeeze_momentum``;
* the score-layer readers of §129-§131 in ``technical_score`` -
  ``technical_state`` (the seven-state enum), ``technical_acceleration`` (the
  second difference) and ``technical_disagreement`` (dispersion / agreement
  across the category sub-scores).

Deterministic synthetic series only; no vendor calls, no network. Every reader
is exercised on input it can measure plus its refusal case (a reason string,
never a fabricated 0).
"""

import pytest

from tradingagents.strategies.technical_factors import squeeze_momentum
from tradingagents.strategies.technical_score import (
    TECHNICAL_STATES,
    technical_acceleration,
    technical_disagreement,
    technical_score,
    technical_state,
)

pytestmark = pytest.mark.timeout(600)


def _alternating(n=40, hi=100.0, lo=90.0):
    """A two-level series: over any even window it has mean (hi+lo)/2 and sd
    (hi-lo)/2, so the two band pairs are easy to force apart."""
    return [hi if i % 2 == 0 else lo for i in range(n)]


# ---------------------------------------------------------------------------
# 1. Keltner/Bollinger squeeze momentum (§109/§110)
# ---------------------------------------------------------------------------


def test_bollinger_inside_keltner_flags_a_squeeze():
    out = squeeze_momentum(_alternating(), atr_value=2.0, bb_k=0.5, kc_mult=2.0)
    assert out["reason"] is None
    assert out["squeeze"] is True
    # the flag is exactly §109's two inequalities
    assert out["bb_upper"] < out["kc_upper"]
    assert out["bb_lower"] > out["kc_lower"]


def test_bollinger_wider_than_keltner_does_not_flag():
    out = squeeze_momentum(_alternating(), atr_value=0.5, bb_k=2.0, kc_mult=1.0)
    assert out["reason"] is None
    assert out["squeeze"] is False
    # at least one side of §109's conjunction must fail
    assert out["bb_upper"] > out["kc_upper"]


def test_release_is_the_flag_clearing_after_compression():
    out = squeeze_momentum(
        _alternating(), atr_value=0.5, bb_k=0.5, kc_mult=2.0, atr_prev=2.0
    )
    assert out["reason"] is None
    assert out["release_reason"] is None
    assert out["squeeze"] is False
    assert out["release"] is True


def test_release_is_unmeasurable_without_prior_atr():
    out = squeeze_momentum(_alternating(), atr_value=0.5, bb_k=0.5, kc_mult=2.0)
    assert out["squeeze"] is False
    assert out["release"] is None
    assert isinstance(out["release_reason"], str)


def test_squeeze_momentum_direction_tracks_price_change():
    rise = [100.0 + i for i in range(40)]
    up = squeeze_momentum(rise, atr_value=1.0, bb_k=0.5, kc_mult=4.0)
    assert up["momentum"] > 0
    assert up["direction"] == "bullish"
    down = squeeze_momentum(rise[::-1], atr_value=1.0, bb_k=0.5, kc_mult=4.0)
    assert down["momentum"] < 0
    assert down["direction"] == "bearish"
    # §110's "compression without directional confirmation": a two-level series
    # returns to its starting level, so the momentum leg is exactly zero.
    flat_leg = squeeze_momentum(_alternating(), atr_value=2.0, bb_k=0.5, kc_mult=2.0)
    assert flat_leg["momentum"] == 0.0
    assert flat_leg["direction"] == "none"


def test_squeeze_refuses_without_a_usable_atr():
    out = squeeze_momentum(_alternating(), atr_value=None)
    assert out["squeeze"] is None
    assert out["momentum"] is None
    assert isinstance(out["reason"], str)
    short = squeeze_momentum([100.0] * 5, atr_value=1.0)
    assert short["squeeze"] is None
    assert isinstance(short["reason"], str)


# ---------------------------------------------------------------------------
# 2. Technical acceleration (§130)
# ---------------------------------------------------------------------------


def test_flat_series_has_zero_acceleration():
    out = technical_acceleration([5.0] * 5)
    assert out["reason"] is None
    assert out["acceleration"] == 0.0
    assert out["velocity"] == 0.0


def test_convex_series_has_positive_acceleration():
    out = technical_acceleration([1.0, 2.0, 4.0, 7.0, 11.0])
    assert out["reason"] is None
    assert out["acceleration"] > 0.0
    assert out["acceleration"] == 1.0


def test_acceleration_refuses_a_series_shorter_than_the_second_difference():
    out = technical_acceleration([1.0, 2.0])
    assert out["acceleration"] is None
    assert out["velocity"] is None
    assert isinstance(out["reason"], str)


# ---------------------------------------------------------------------------
# 3. Technical disagreement (§131)
# ---------------------------------------------------------------------------


def test_fully_agreeing_categories_have_minimum_disagreement():
    out = technical_disagreement({"a": 50.0, "b": 50.0, "c": 50.0})
    assert out["reason"] is None
    assert out["disagreement"] == 0.0
    assert out["agreement"] == 1.0
    assert out["compared"] == ["a", "b", "c"]


def test_maximally_split_categories_have_maximum_disagreement():
    out = technical_disagreement({"a": 0.0, "b": 100.0})
    assert out["reason"] is None
    assert out["disagreement"] == 1.0
    assert out["agreement"] == 0.0
    even = technical_disagreement({"a": 0.0, "b": 0.0, "c": 100.0, "d": 100.0})
    assert even["disagreement"] == 1.0
    # the split vector is strictly more disagreeing than the agreeing one
    assert even["disagreement"] > technical_disagreement({"a": 50.0, "b": 50.0})["disagreement"]


def test_disagreement_refuses_fewer_than_two_scores():
    out = technical_disagreement({"a": 50.0})
    assert out["disagreement"] is None
    assert out["agreement"] is None
    assert isinstance(out["reason"], str)


def test_disagreement_reads_the_technical_score_categories():
    ts = technical_score({
        "sma_stack": True, "aroon_osc": 40.0, "momentum_12_1": 0.2,
        "stoch_rsi": 0.5, "obv_bullish_div": True, "cmf": 0.05,
        "sqrt_rs_minus": 0.02, "pct_above_50d": 55.0, "pct_above_200d": 50.0,
        "ad_ratio": 0.1,
    })
    out = technical_disagreement(ts)
    assert out["reason"] is None
    assert out["compared"]  # names the inputs it compared
    assert len(out["compared"]) >= 2
    for name in out["compared"]:
        assert ts["categories"][name]["score"] is not None
    assert 0.0 <= out["disagreement"] <= 1.0


# ---------------------------------------------------------------------------
# 4. Technical state (§129)
# ---------------------------------------------------------------------------


def test_state_enum_is_exactly_the_library_seven():
    assert TECHNICAL_STATES == (
        "STRONG_UPTREND", "UPTREND", "WEAK_UPTREND", "NEUTRAL",
        "WEAK_DOWNTREND", "DOWNTREND", "STRONG_DOWNTREND",
    )
    assert len(TECHNICAL_STATES) == 7


def test_state_maps_a_hand_built_indicator_set_to_the_expected_state():
    up = {"ma_alignment": 1, "ma_slope": 1, "macd": 1, "structure": 1}
    assert technical_state(up, adx=30.0)["state"] == "STRONG_UPTREND"
    assert technical_state(up, adx=10.0)["state"] == "UPTREND"
    assert technical_state(
        {"ma_alignment": 1, "ma_slope": 1, "macd": -1, "structure": 0}
    )["state"] == "WEAK_UPTREND"
    assert technical_state(
        {"ma_alignment": 1, "ma_slope": -1, "macd": 1, "structure": -1}
    )["state"] == "NEUTRAL"
    assert technical_state(
        {"ma_alignment": -1, "ma_slope": -1, "macd": 1, "structure": -1}
    )["state"] == "WEAK_DOWNTREND"
    assert technical_state(
        {"ma_alignment": -1, "ma_slope": -1, "macd": -1, "structure": 0}
    )["state"] == "DOWNTREND"
    down = {"ma_alignment": -1, "ma_slope": -1, "macd": -1, "structure": -1}
    assert technical_state(down, adx=40.0)["state"] == "STRONG_DOWNTREND"
    assert technical_state(down, adx=5.0)["state"] == "DOWNTREND"


def test_state_reports_the_legs_it_compared_and_refuses_empty_input():
    out = technical_state({"ma_alignment": 1, "structure": 1, "adx": 30.0})
    assert out["state"] == "WEAK_UPTREND"
    assert out["legs_compared"] == ["ma_alignment", "structure"]
    assert out["net"] == 2
    empty = technical_state({})
    assert empty["state"] is None
    assert isinstance(empty["reason"], str)
    assert empty["legs_compared"] == []
