"""P0-6: the short-interest percentile over a name's own settlement series."""

import pytest

from tradingagents.strategies.short_interest import DIRECTION, short_interest_percentile


def test_a_six_settlement_series_gives_a_known_percentile():
    """Acceptance: 6 settlements, latest is the highest -> 100th percentile, with
    the raw value, the series length and the period-over-period change beside it."""
    got = short_interest_percentile([10.0, 12.0, 11.0, 13.0, 14.0, 20.0])
    assert got["n"] == 6
    assert got["latest"] == pytest.approx(20.0)
    assert got["prior"] == pytest.approx(14.0)
    assert got["change_pct"] == pytest.approx((20.0 / 14.0 - 1.0) * 100.0)
    assert got["percentile"] == pytest.approx(1.0)
    assert "6 settlements" in got["basis"]
    # The direction is stated, never implied.
    assert got["direction"] == DIRECTION
    assert "not a bullish signal" in got["direction"]

    # A middle settlement ranks in the middle of its own history.
    mid = short_interest_percentile([10.0, 12.0, 11.0, 13.0, 14.0, 12.5])
    assert mid["percentile"] == pytest.approx(4 / 6)


def test_a_single_settlement_reports_no_rank_with_its_reason():
    """One settlement has no rank to report: None with the reason, never a
    fabricated 0.5 that would read as "mid-range"."""
    got = short_interest_percentile([12.0])
    assert got["percentile"] is None
    assert got["n"] == 1
    assert got["latest"] == pytest.approx(12.0)
    assert got["change_pct"] is None
    assert "1 settlement(s) held, 4 needed" in got["basis"]


def test_an_empty_series_is_none_not_zero():
    got = short_interest_percentile([])
    assert got["percentile"] is None
    assert got["latest"] is None
    assert got["n"] == 0
