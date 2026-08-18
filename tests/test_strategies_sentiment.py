"""Phase 6 unit tests: sentiment velocity, mention spike, seed consensus."""

import pytest

from tradingagents.strategies.sentiment import (
    sentiment_velocity, mention_volume, consensus_overlap, consensus_verdict,
    blended_score,
)


def test_velocity_positive_on_rising_sentiment():
    v = sentiment_velocity([0.1, 0.2, 0.3, 0.4, 0.5])
    assert v is not None and v > 0


def test_velocity_negative_on_falling():
    v = sentiment_velocity([0.5, 0.4, 0.3, 0.2, 0.1])
    assert v is not None and v < 0


def test_velocity_insufficient_none():
    assert sentiment_velocity([0.1, 0.2]) is None


def test_mention_spike_hot():
    assert mention_volume([10, 12, 11, 50], recent=1) > 3.0
    assert 0.0 < mention_volume([10, 12, 11, 8], recent=1) < 1.0


def test_consensus_overlap():
    assert consensus_overlap(["buy", "buy", "hold"]) == pytest.approx(2 / 3)
    assert consensus_overlap(["buy", "sell"]) == 0.5
    assert consensus_overlap([]) is None


def test_consensus_needs_threshold():
    assert consensus_verdict(["buy", "buy", "sell"]) == "buy"
    assert consensus_verdict(["buy", "sell", "hold"]) == "mixed"


def test_blend_respects_weights():
    out = blended_score({"sent": 0.8, "value": 0.2}, {"sent": 1.0, "value": 3.0})
    # (0.8*1 + 0.2*3)/4 = 0.35
    assert out == pytest.approx(0.35)
    assert blended_score({}) == 0.0
