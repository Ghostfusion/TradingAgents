"""Schema render includes deterministic computed-sentiment line."""

from tradingagents.agents.schemas import (
    SentimentBand,
    SentimentReport,
    render_sentiment_report,
)


def test_render_includes_computed_when_set():
    report = SentimentReport(
        overall_band=SentimentBand.MILDLY_BULLISH,
        overall_score=5.8,
        confidence="medium",
        narrative="narrative body",
        computed_score=0.45,
        computed_velocity=1.1,
        sample_size=40,
    )
    text = render_sentiment_report(report)
    assert "**Computed Sentiment:** +0.45 (velocity +1.10sigma, n=40)" in text
    assert "narrative body" in text


def test_render_omits_computed_when_unset():
    report = SentimentReport(
        overall_band=SentimentBand.NEUTRAL,
        overall_score=5.0,
        confidence="low",
        narrative="body",
    )
    text = render_sentiment_report(report)
    assert "Computed Sentiment" not in text
