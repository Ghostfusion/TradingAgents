"""S7: exponentially weighted rolling sentiment window (round-3 addition).

Reuses ``daily_sentiment_sma``'s calendar reindexing; the legacy 7d SMA path is
asserted unchanged and the warm-up guard is exercised on both sides.
"""

import math
from datetime import date, timedelta

import pytest

from tradingagents.strategies.sentiment import (
    daily_sentiment_sma,
    weighted_rolling_sentiment,
)


def _points(scores_by_day):
    return [
        {"date": f"2026-08-{day:02d}", "score": score, "n": 1}
        for day, score in sorted(scores_by_day.items())
    ]


def test_recent_spike_weighted_exceeds_sma_and_both_print():
    pts = _points({d: (1.0 if d == 10 else 0.0) for d in range(1, 11)})
    out = weighted_rolling_sentiment(pts, window=10, min_history=5)
    assert out["sufficient_history"] is True
    assert out["weighted"] is not None and out["unweighted_sma"] is not None
    assert out["weighted"] > out["unweighted_sma"]
    assert out["unweighted_sma"] == pytest.approx(1 / 7, abs=1e-4)
    assert out["rows"][-1]["weighted"] == out["weighted"]
    assert out["rows"][-1]["sma_7d"] == out["unweighted_sma"]


def test_min_history_guard_reports_observed_length():
    pts = _points(dict.fromkeys(range(1, 13), 0.1))
    out = weighted_rolling_sentiment(pts, window=10, min_history=30)
    assert out["sufficient_history"] is False
    assert out["weighted"] is None
    assert out["n_history"] == 12
    assert "unavailable" in out["basis"]


def test_missing_day_carries_no_score_not_a_zero_fill():
    scores = {d: 0.0 for d in range(1, 11) if d != 5}
    scores[10] = 1.0
    pts = _points(scores)
    out = weighted_rolling_sentiment(pts, window=10, min_history=5)
    present_slots = [d - 1 for d in sorted(scores)]
    present_ref = math.exp(1.0) / sum(math.exp(k / 9) for k in present_slots)
    zero_fill_ref = math.exp(1.0) / sum(math.exp(k / 9) for k in range(10))
    assert out["weighted"] == pytest.approx(present_ref, abs=1e-3)
    assert abs(out["weighted"] - zero_fill_ref) > 0.01


def test_sma_path_unchanged_and_shared():
    pts = _points({d: 0.1 * d for d in range(1, 11)})
    legacy = daily_sentiment_sma(pts, window=7)
    assert legacy is not None
    assert set(legacy[0]) == {"date", "score", "sma_7d", "innovation", "n"}
    assert legacy[6]["sma_7d"] == pytest.approx(
        round(sum(0.1 * d for d in range(1, 8)) / 7, 4)
    )
    out = weighted_rolling_sentiment(pts, window=7, min_history=1)
    assert [r["sma_7d"] for r in out["rows"]] == [r["sma_7d"] for r in legacy]
    assert [r["innovation"] for r in out["rows"]] == [r["innovation"] for r in legacy]


def test_equal_weights_match_sma_when_window_matches():
    pts = _points({d: 0.1 * d for d in range(1, 11)})
    out = weighted_rolling_sentiment(pts, window=7, exponential=False, min_history=1)
    assert out["rows"][-1]["weighted"] == out["rows"][-1]["sma_7d"]


def test_empty_points_none():
    assert weighted_rolling_sentiment([]) is None


def test_weighted_window_row_gated_on_the_tool(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import config as config_module

    base_day = date(2026, 8, 1)
    pts = [
        {
            "date": (base_day + timedelta(days=i)).isoformat(),
            "score": (1.0 if i == 30 else 0.0),
            "n": 1,
        }
        for i in range(31)
    ]
    monkeypatch.setattr(at, "_news_sentiment_points", lambda *a, **k: pts)
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor",
        lambda *a, **k: "## base series",
    )
    tool = at.get_news_sentiment_series
    assert tool.invoke({"ticker": "AAPL"}) == "## base series"
    config_module.set_config({"enable_weighted_sentiment_window": True})
    on = tool.invoke({"ticker": "AAPL"})
    assert "Weighted rolling sentiment" in on
    assert "unweighted 7d SMA beside it" in on
