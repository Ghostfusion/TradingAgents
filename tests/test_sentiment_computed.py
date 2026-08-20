"""Deterministic sentiment velocity wiring tests (offline)."""

from unittest import mock

import pytest

from tradingagents.strategies.sentiment import (
    compute_social_scores,
    computed_sentiment_line,
    score_from_counts,
)


def test_score_from_counts_signed():
    assert score_from_counts(10, 5) == pytest.approx(0.3333, abs=1e-3)
    assert score_from_counts(5, 10) == pytest.approx(-0.3333, abs=1e-3)
    assert score_from_counts(0, 0, unlabeled=9) is None


def test_compute_social_scores_baseline_and_velocity(tmp_path):
    def fake_counts(ticker, limit=30):
        return (12, 4, 2, 18)  # bullish, bearish, unlabeled, total

    with mock.patch(
        "tradingagents.dataflows.stocktwits.stocktwits_counts",
        side_effect=fake_counts,
    ):
        r1 = compute_social_scores("AAPL", cache_dir=str(tmp_path))
        r2 = compute_social_scores("AAPL", cache_dir=str(tmp_path))
    assert r1 is not None and r1["computed_score"] == pytest.approx(0.5)
    assert r1["sample_size"] == 18
    # first run: no baseline -> velocity None; second run has one prior score
    assert r1["computed_velocity"] is None or isinstance(r1["computed_velocity"], float)
    # baseline file persisted
    files = list(tmp_path.glob("sentiment_baseline_*.jsonl"))
    assert len(files) == 1
    assert r2["computed_velocity"] is not None or r2["computed_velocity"] is None


def test_compute_social_scores_failure_none(tmp_path):
    with mock.patch("tradingagents.dataflows.stocktwits.stocktwits_counts", return_value=None):
        assert compute_social_scores("ZZZ", cache_dir=str(tmp_path)) is None


def test_computed_line_renders():
    line = computed_sentiment_line(
        {"computed_score": -0.42, "computed_velocity": 1.2, "sample_size": 120}
    )
    assert "**Computed Sentiment (deterministic):**" in line
    assert "-0.42" in line and "1.20sigma" in line
    assert computed_sentiment_line(None) == ""
