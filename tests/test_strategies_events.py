"""Phase 4 unit tests: earnings surprise / PEAD side / risk multipliers."""

import pytest

from tradingagents.strategies.events import (
    surprise_score, drift_side, position_mult_by_side,
    expected_drift_after, catalyst_risk_penalty,
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
