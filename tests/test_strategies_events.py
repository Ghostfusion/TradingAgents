"""Phase 4 unit tests: earnings surprise / PEAD side / risk multipliers."""

import pytest

from tradingagents.strategies.events import (
    catalyst_risk_penalty,
    drift_side,
    expected_drift_after,
    position_mult_by_side,
    surprise_score,
)


def test_surprise_positive_beat():
    assert surprise_score(1.20, 1.00) == pytest.approx(0.2)


def test_surprise_none_on_missing_or_zero():
    assert surprise_score(None, 1.0) is None
    assert surprise_score(1.0, 0.0) is None


def test_drift_side_classification():
    assert drift_side(0.15) == "beat"
    assert drift_side(-0.15) == "miss"
    assert drift_side(0.0) == "flat"
    assert drift_side(None) == "flat"


def test_position_mult_capped():
    assert position_mult_by_side("flat") == 0.0
    assert 0.0 < position_mult_by_side("beat") <= 1.5
    assert position_mult_by_side("miss") < position_mult_by_side("beat")


def test_drift_return():
    assert expected_drift_after(100.0, 105.0) == pytest.approx(0.05)


def test_risk_penalty_bounds():
    p1 = catalyst_risk_penalty(0.05, 0.015)
    p2 = catalyst_risk_penalty(0.005, 0.015)
    assert 0.0 < p1 <= 1.0
    assert p1 < p2  # bigger expected move -> smaller size
    assert catalyst_risk_penalty(None) == 0.5


def test_gap_up_qualifies():
    from tradingagents.strategies.events import gap_up_qualifies

    assert gap_up_qualifies(0.04, 3.0) is True
    assert gap_up_qualifies(0.04, 2.49) is False          # volume below 2.5x
    assert gap_up_qualifies(-0.02, 3.0) is False          # gap DOWN
    assert gap_up_qualifies(0.04, None) is False         # unverifiable volume
    assert gap_up_qualifies(None, 3.0) is False
    assert gap_up_qualifies(0.01, 3.0, gap_min=0.02) is False  # gap size gate


def test_consolidation_and_break():
    from tradingagents.strategies.events import consolidation_and_break

    highs = [100.0, 102.0, 101.0, 103.0]  # post-print bars, range high 103
    closes = [101.0, 100.5, 101.5, 104.0]  # last close breaks 103
    c = consolidation_and_break(highs, closes, hold_days=4)
    assert c["range_high"] == 103.0
    assert c["breakout"] is True
    no_break = consolidation_and_break(highs, [101.0, 100.5, 101.5, 102.0], hold_days=4)
    assert no_break["breakout"] is False
    assert consolidation_and_break([], []) == {
        "range_high": None, "range_low": None, "breakout": None,
    }


def test_post_earnings_play_verdicts():
    from tradingagents.strategies.events import post_earnings_play

    highs = [100.0, 102.0, 101.0]
    # Qualified gap + breakout -> setup
    play = post_earnings_play(0.04, 3.0, highs, [101.0, 100.5, 104.5], hold_days=3)
    assert play["verdict"] == "setup"
    assert play["gap"] is True and play["breakout"] is True
    # Qualified gap, no break yet -> consolidating
    wait = post_earnings_play(0.04, 3.0, highs, [101.0, 100.5, 101.5], hold_days=3)
    assert wait["verdict"] == "consolidating"
    # Gap below the 2.5x volume bar -> no-gap
    weak = post_earnings_play(0.04, 1.2, highs, [101.0, 100.5, 105.0], hold_days=3)
    assert weak["verdict"] == "no-gap"
    # Missing data -> no-data
    assert post_earnings_play(None, None, [], []) == {"verdict": "no-data"}
