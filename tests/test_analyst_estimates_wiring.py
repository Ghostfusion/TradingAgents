"""P0/P1 of `docs/design_finnhub_yfinance_unused_surface.md`, offline.

`yfinance_sector.fetch_estimate_trend` / `::fetch_eps_revisions` (the readers)
and the `analyst_revisions` leg they feed. The point of the pair: the
estimate-change leg was permanently `unavailable` in production because no
caller ever supplied `levels`; `eps_trend` supplies exactly the five levels it
needs.

Offline: `yfinance.Ticker` is mocked, so nothing touches the network.
"""

from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from tradingagents.dataflows import yfinance_sector as ys
from tradingagents.strategies.analyst_revisions import (
    estimate_change_index,
    revision_index,
)

_PERIODS = ["0q", "+1q", "0y", "+1y"]


def _trend_frame(current_row=(1.98, 1.98, 1.98, 2.02, 2.01)):
    """A frame shaped like `yfinance.Ticker.eps_trend` (measured 2026-09-18)."""
    cols = list(ys._ESTIMATE_LEVEL_COLUMNS) + ["currency"]
    data = []
    for i, _p in enumerate(_PERIODS):
        row = list(current_row) if i == 0 else [9.0, 9.0, 9.0, 9.0, 9.0]
        data.append(row + ["USD"])
    return pd.DataFrame(data, columns=cols, index=_PERIODS)


def _revisions_frame():
    """A frame shaped like `yfinance.Ticker.eps_revisions` (measured 2026-09-18)."""
    cols = ["upLast7days", "upLast30days", "downLast30days", "downLast7Days", "currency"]
    data = [
        [1, 7, 14, 0, "USD"],
        [0, 1, 1, 1, "USD"],
        [0, 5, 2, 1, "USD"],
        [1, 2, 7, 1, "USD"],
    ]
    return pd.DataFrame(data, columns=cols, index=_PERIODS)


def _ticker(eps_trend=None, eps_revisions=None):
    tk = mock.Mock()
    tk.eps_trend = eps_trend if eps_trend is not None else pd.DataFrame()
    tk.eps_revisions = eps_revisions if eps_revisions is not None else pd.DataFrame()
    return tk


# --- the reader --------------------------------------------------------------


@pytest.mark.unit
def test_estimate_trend_returns_the_five_levels_most_recent_first():
    """The shape `estimate_change_index` needs: `len(weights) + 1` levels."""
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_trend=_trend_frame())):
        levels = ys.fetch_estimate_trend("AAPL")

    assert levels == [1.98, 1.98, 1.98, 2.02, 2.01]
    assert len(levels) == len(ys._ESTIMATE_LEVEL_COLUMNS) == 5


@pytest.mark.unit
def test_estimate_trend_reads_the_current_quarter_row_not_a_later_one():
    """Row selection matters: `+1y` is a different estimate entirely."""
    frame = _trend_frame(current_row=(1.0, 1.0, 1.0, 1.0, 1.0))
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_trend=frame)):
        assert ys.fetch_estimate_trend("AAPL") == [1.0, 1.0, 1.0, 1.0, 1.0]
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_trend=frame)):
        assert ys.fetch_estimate_trend("AAPL", period="+1y") == [9.0] * 5


@pytest.mark.unit
def test_estimate_trend_refuses_a_short_series_rather_than_trimming():
    """A short series silently changes what the index means, so it is None."""
    frame = _trend_frame()
    frame.loc["0q", "90daysAgo"] = None
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_trend=frame)):
        assert ys.fetch_estimate_trend("AAPL") is None


@pytest.mark.unit
def test_estimate_trend_degrades_on_an_empty_frame_or_a_missing_period():
    with mock.patch("yfinance.Ticker", return_value=_ticker()):
        assert ys.fetch_estimate_trend("AAPL") is None

    frame = _trend_frame().drop(index="0q")
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_trend=frame)):
        assert ys.fetch_estimate_trend("AAPL") is None


@pytest.mark.unit
def test_estimate_trend_never_raises_when_the_vendor_does():
    with mock.patch("yfinance.Ticker", side_effect=RuntimeError("yahoo down")):
        assert ys.fetch_estimate_trend("AAPL") is None


@pytest.mark.unit
def test_eps_revisions_returns_the_counts_and_their_net():
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_revisions=_revisions_frame())):
        rev = ys.fetch_eps_revisions("AAPL")

    assert rev["up"] == 7 and rev["down"] == 14
    assert rev["net"] == -7
    assert rev["up_7d"] == 1 and rev["down_7d"] == 0
    assert rev["period"] == "0q"


@pytest.mark.unit
def test_eps_revisions_is_none_when_the_period_is_absent():
    frame = _revisions_frame().drop(index="0q")
    with mock.patch("yfinance.Ticker", return_value=_ticker(eps_revisions=frame)):
        assert ys.fetch_eps_revisions("AAPL") is None


# --- the leg -----------------------------------------------------------------


@pytest.mark.unit
def test_the_default_basis_still_says_quarterly():
    """Byte-identity for every existing caller: the label only moves when asked."""
    read = estimate_change_index([110.0, 100.0, 90.0, 80.0, 70.0])
    assert "over 4 quarterly change(s)" in read["basis"]
    assert read["level_basis"] == "quarterly"


@pytest.mark.unit
def test_a_supplied_level_basis_names_the_series_it_came_from():
    """The vendor series is a 90-day window, so the basis must not claim MSCI's."""
    read = estimate_change_index(
        [1.98, 1.98, 1.98, 2.02, 2.01], level_basis=ys.ESTIMATE_LEVEL_BASIS
    )
    assert ys.ESTIMATE_LEVEL_BASIS in read["basis"]
    assert "quarterly" not in read["basis"]
    assert read["level_basis"] == ys.ESTIMATE_LEVEL_BASIS


@pytest.mark.unit
def test_the_arithmetic_is_unchanged_by_the_label():
    """Only the label moves: the index must not depend on `level_basis`."""
    levels = [110.0, 100.0, 90.0, 80.0, 70.0]
    a = estimate_change_index(levels)
    b = estimate_change_index(levels, level_basis="anything")
    assert a["index"] == b["index"]
    assert a["changes"] == b["changes"]


@pytest.mark.unit
def test_the_leg_is_unavailable_with_its_reason_when_the_source_is_down():
    """The pre-existing behaviour: a missing input is named, never scored 0."""
    read = revision_index([{"up": 3, "down": 1}], levels=None)
    assert read["legs"]["estimate_change"] is None
    assert "never a 3-4 quarter estimate history" in read["unavailable"]["estimate_change"]
    assert read["available"] == ["revision_ratio"]


@pytest.mark.unit
def test_supplying_the_vendor_levels_turns_the_leg_from_unavailable_to_measured():
    """The whole point of P0/P1, asserted as the transition it is."""
    history = [{"up": 3, "down": 1}, {"up": 1, "down": 1}, {"up": 0, "down": 2}]
    before = revision_index(history, levels=None)
    after = revision_index(
        history,
        levels=[1.98, 1.98, 1.98, 2.02, 2.01],
        level_basis=ys.ESTIMATE_LEVEL_BASIS,
    )

    assert before["available"] == ["revision_ratio"]
    assert "estimate_change" in before["unavailable"]

    assert set(after["available"]) == {"revision_ratio", "estimate_change"}
    assert after["unavailable"] == {}
    assert after["legs"]["estimate_change"] is not None
    assert ys.ESTIMATE_LEVEL_BASIS in after["basis"]


@pytest.mark.unit
def test_the_index_averages_the_available_legs_not_both_always():
    """MSCI's rule: the mean is over what is available, not over a padded pair."""
    history = [{"up": 3, "down": 1}, {"up": 1, "down": 1}, {"up": 0, "down": 2}]
    one = revision_index(history, levels=None)
    two = revision_index(history, levels=[1.98, 1.98, 1.98, 2.02, 2.01])

    assert one["index"] == pytest.approx(one["legs"]["revision_ratio"])
    assert two["index"] == pytest.approx(
        (two["legs"]["revision_ratio"] + two["legs"]["estimate_change"]) / 2.0
    )
