"""Tests for weighted/thresholded consensus (strategies/consensus.py).

Extends the equal-weight agreement_score with calibration-weighted
arbitration (analyst blips weighted by their reliability) and a thresholded
HOLD default for weak/straddling signals, per the researched arbitration
pattern ("weighted consensus + threshold, else hold").
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.consensus import (
    agreement_score,
    consensus_from_score,
    rating_to_number,
    should_hold,
    weighted_consensus,
)


@pytest.mark.timeout(30)
class TestWeightedConsensus:
    def test_rating_to_number(self):
        assert rating_to_number("Buy") == 1.0
        assert rating_to_number("Sell") == -1.0
        assert rating_to_number("Hold") == 0.0
        assert rating_to_number("Unknown") is None

    def test_weighted_consensus_equal_weights_is_mean(self):
        # Equal weights 1.0 -> plain mean of the stances.
        stance, den = weighted_consensus([("Buy", 1.0), ("Sell", 1.0), ("Hold", 1.0)])
        assert stance == pytest.approx(0.0)
        assert den == 3.0

    def test_weighted_consensus_weights_dominate(self):
        # 2 buys at weight 1.0 + 1 sell at weight 10 -> heavily bearish.
        stance, den = weighted_consensus(
            [("Buy", 1.0), ("Buy", 1.0), ("Sell", 10.0)]
        )
        assert stance == pytest.approx(-0.6667, abs=1e-3)
        assert den == 12.0

    def test_weighted_consensus_ignores_unknown_rating(self):
        stance, _ = weighted_consensus([("Buy", 2.0), ("Mystery", 5.0)])
        assert stance == pytest.approx(1.0)

    def test_weighted_consensus_no_valid_returns_none(self):
        assert weighted_consensus([]) == (None, None)
        assert weighted_consensus([("Mystery", 1.0)]) == (None, None)

    def test_should_hold_on_weak_signal(self):
        assert should_hold(0.1) is True       # weak -> hold
        assert should_hold(0.24, 0.25) is True
        assert should_hold(0.31) is False      # above 0.25 -> tradeable
        assert should_hold(None) is True       # no signal -> hold
        assert should_hold(-0.1) is True       # weak negative also hold

    def test_agreement_and_threshold_compose(self):
        # A strongly-divided book (Buy+Sell) has low agreement; the stance is
        # ~0 -> should_hold True even though stances are extreme.
        ratings = ["Buy", "Sell"]
        score = agreement_score(ratings)
        assert score == pytest.approx(0.0)
        stance, _ = weighted_consensus([(r, 1.0) for r in ratings])
        assert should_hold(stance) is True
        # A unanimous Buy crosses the threshold.
        stance2, _ = weighted_consensus([("Buy", 1.0), ("Buy", 1.0)])
        assert should_hold(stance2) is False
        assert consensus_from_score(1.0) == "high"
