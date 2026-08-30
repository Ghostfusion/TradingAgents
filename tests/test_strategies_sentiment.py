"""Phase 6 unit tests: sentiment velocity, mention spike, seed consensus."""

import pytest

from tradingagents.strategies.sentiment import (
    aggregate_daily_sentiment,
    blended_score,
    consensus_overlap,
    consensus_verdict,
    daily_sentiment_sma,
    mention_volume,
    sentiment_velocity,
)

pytestmark = pytest.mark.timeout(60)


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


# --- News-sentiment daily series (News_Sentiment.md §1) ---


def _av_article(day, hhmm, score, ticker="AAPL", overall=None, rel=None, ts=None):
    ticker = ticker.upper()
    if hhmm:
        published = f"202608{day:02d}T{hhmm}00"
        if ts:
            published += "Z"
    else:
        published = ts
    art = {
        "time_published": published,
        "overall_sentiment_score": overall if overall is not None else score,
    }
    if ticker:
        row = {"ticker": ticker, "ticker_sentiment_score": score}
        if rel is not None:
            row["relevance_score"] = rel
        art["ticker_sentiment"] = [row]
    return art


def test_aggregate_daily_mean_and_ticker_preference():
    arts = [
        _av_article(1, "1000", 0.5, overall=0.2),
        _av_article(1, "1100", -0.3, overall=0.9),
        _av_article(2, "0900", 0.8, overall=-0.5),
    ]
    out = aggregate_daily_sentiment(arts, ticker="AAPL")
    assert out is not None
    assert [d["date"] for d in out] == ["2026-08-01", "2026-08-02"]
    # Ticker scores preferred: day1 mean of (0.5, -0.3).
    assert out[0]["score"] == pytest.approx(0.1)
    assert out[1]["score"] == pytest.approx(0.8)


def test_aggregate_overall_fallback_flagged():
    arts = [
        _av_article(1, "1000", 0.5, ticker="AAPL"),
        # This article does not mention AAPL -> overall fallback.
        _av_article(1, "1200", 0.7, ticker="MSFT", overall=0.7) | {"ticker_sentiment": [{"ticker": "MSFT", "ticker_sentiment_score": 0.7}]},
    ]
    out = aggregate_daily_sentiment(arts, ticker="AAPL")
    assert out is not None
    assert out[0]["n"] == 2
    # 1 of 2 articles used the overall fallback.
    assert out[0]["used_overall"] == 1


def test_aggregate_post_close_buckets_next_day():
    # 15:59 ET stays on the 1st; 16:00 ET rolls to the 2nd.
    arts = [
        _av_article(1, "1459", 0.1),  # 14:59 UTC is 10:59 ET - stays same day.
        _av_article(1, "2359", 0.2),  # 23:59 UTC = 19:59 ET (Aug EDT) - next day.
    ]
    out = aggregate_daily_sentiment(arts, ticker="AAPL")
    assert out is not None
    assert out[0]["date"] == "2026-08-01"
    assert out[0]["score"] == pytest.approx(0.1)
    assert len(out) == 2 and out[1]["date"] == "2026-08-02"


def test_aggregate_empty_and_invalid_none():
    assert aggregate_daily_sentiment([], ticker="AAPL") is None
    bad = [
        {"time_published": "20260801T100000Z", "ticker_sentiment": []},
        {"time_published": "garbage", "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": 0.5}]},
    ]
    assert aggregate_daily_sentiment(bad, ticker="AAPL") is None


def test_sma_reindexes_calendar_and_innovation():
    # Six scored days then a gap: day 1..6 then day 8 (skips day 7).
    points = [
        {"date": f"2026-08-{d:02d}", "score": 0.1 * d, "n": 1} for d in range(1, 7)
    ] + [{"date": "2026-08-08", "score": 0.7, "n": 3}]
    out = daily_sentiment_sma(points, window=7)
    assert out is not None
    assert len(out) == 8  # 01..08 calendar days
    assert out[0]["sma_7d"] == pytest.approx(0.1)
    assert out[5]["sma_7d"] == pytest.approx((0.1 + 0.2 + 0.3 + 0.4 + 0.5 + 0.6) / 6)
    # Day 6 scores 0.6; day-6 sma uses days 1..6 = 0.35.
    # Day 7 has no score; day 7 sma still = 0.35 (window includes day 1..7, day 7 miss).
    assert out[6]["score"] is None
    assert out[6]["sma_7d"] == pytest.approx(0.35)
    # Day 8: score 0.7, prev sma (day7) 0.35 -> innovation 0.35.
    assert out[7]["innovation"] == pytest.approx(0.35)


def test_sma_min_days_none():
    out = daily_sentiment_sma([{"date": "2026-08-01", "score": 0.5, "n": 1}], min_score_days=3)
    assert out is None
    assert daily_sentiment_sma([]) is None
