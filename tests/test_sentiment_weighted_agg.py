"""S4: weighted/unweighted news aggregation (round-3 formula additions).

Offline fixtures only; no vendor call. The equal-weight identity, the
syndication dedupe, the official-relevance boost, the min_n suppression and the
byte-identical legacy path are each pinned to a hand-computed value.
"""

import pytest

from tradingagents.strategies.sentiment import (
    aggregate_daily_sentiment,
    aggregate_weighted_sentiment,
)


def _art(day, hhmm, score, title, ticker="AAPL", rel=None, url=""):
    row = {"ticker": ticker, "ticker_sentiment_score": score}
    if rel is not None:
        row["relevance_score"] = rel
    art = {
        "time_published": f"202608{day:02d}T{hhmm}00",
        "ticker_sentiment": [row],
        "title": title,
    }
    if url:
        art["url"] = url
    return art


def test_equal_weight_identity_to_last_decimal():
    arts = [_art(1, "1000", 0.5, "A"), _art(1, "1100", -0.3, "B")]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL")
    assert out is not None and len(out) == 1
    row = out[0]
    assert row["unweighted"] == pytest.approx(0.1)
    # Equal weights (no relevance, no boost, decay off) -> exact identity.
    assert row["weighted"] == row["unweighted"]
    assert row["n"] == 2


def test_duplicate_headline_does_not_raise_n():
    arts = [
        _art(1, "1000", 0.5, "Apple beats on iPhone sales"),
        _art(1, "1100", -0.3, "Apple Beats on iPhone Sales!"),  # same normalised
        _art(1, "1200", 0.2, "Apple guidance raised"),
    ]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL")
    assert out[0]["n"] == 2
    assert out[0]["unweighted"] == pytest.approx((0.5 + 0.2) / 2)


def test_official_boost_moves_weighted_not_unweighted():
    arts = [
        _art(1, "1000", 1.0, "SEC filing", url="https://www.sec.gov/Archives/foo"),
        _art(1, "1100", 0.0, "Blog post", url="https://example.com/x"),
    ]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL", official_boost=3.0)
    row = out[0]
    assert row["unweighted"] == pytest.approx(0.5)
    # weights: official 3.0 vs plain 1.0 -> (3*1 + 1*0) / 4 = 0.75
    assert row["weighted"] == pytest.approx(0.75)
    assert row["weighted"] != row["unweighted"]


def test_one_article_day_renders_n_and_withholds_weighted():
    out = aggregate_weighted_sentiment([_art(1, "1000", 0.5, "Only")], ticker="AAPL")
    row = out[0]
    assert row["n"] == 1
    assert row["weighted"] is None
    assert row["unweighted"] == pytest.approx(0.5)


def test_neutral_share_and_relevance_weighting():
    arts = [
        _art(1, "1000", 0.4, "A", rel=100.0),
        _art(1, "1100", 0.0, "B", rel=0.0),
        _art(1, "1200", -0.4, "C", rel=50.0),
    ]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL")
    row = out[0]
    assert row["neutral_share"] == pytest.approx(1 / 3, abs=1e-4)
    # w = rel/100 -> (1.0*0.4 + 0.0*0.0 + 0.5*-0.4) / 1.5
    assert row["weighted"] == pytest.approx(0.2 / 1.5, abs=1e-4)


def test_empty_articles_none():
    assert aggregate_weighted_sentiment([], ticker="AAPL") is None


def test_legacy_aggregate_daily_unchanged():
    arts = [
        _art(1, "1000", 0.5, "Dup"),
        _art(1, "1100", -0.3, "Dup"),  # legacy does NOT dedupe
        _art(2, "0900", 0.8, "Next"),
    ]
    out = aggregate_daily_sentiment(arts, ticker="AAPL")
    assert out is not None and len(out) == 2
    for row in out:
        assert set(row) == {"date", "score", "n", "relevance_mean", "used_overall"}
    assert out[0]["score"] == pytest.approx(0.1)
    assert out[0]["n"] == 2  # the duplicate still counts on the legacy path
    assert out[1]["score"] == pytest.approx(0.8)


def test_news_tool_renders_n_a_for_a_withheld_weighted(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import config as config_module

    monkeypatch.setattr(
        at, "_av_news_articles", lambda *a, **k: [_art(1, "1000", 0.5, "Only")]
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor",
        lambda *a, **k: "## base series",
    )
    config_module.set_config({"enable_weighted_sentiment_agg": True})
    on = at.get_news_sentiment_series.invoke({"ticker": "AAPL"})
    assert "| 2026-08-01 | 1 |" in on
    assert "| n/a |" in on


def test_news_tool_appends_weighted_rows_only_when_gated(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import config as config_module

    arts = [_art(1, "1000", 0.5, "A"), _art(1, "1100", -0.3, "B")]
    monkeypatch.setattr(at, "_av_news_articles", lambda *a, **k: arts)
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor",
        lambda *a, **k: "## base series",
    )
    tool = at.get_news_sentiment_series
    # Explicit OFF for both rows this tool renders: the gates may be enabled in
    # the operator's .env (dark launch).
    config_module.set_config(
        {"enable_weighted_sentiment_agg": False, "enable_weighted_sentiment_window": False}
    )
    assert tool.invoke({"ticker": "AAPL"}) == "## base series"
    config_module.set_config({"enable_weighted_sentiment_agg": True})
    on = tool.invoke({"ticker": "AAPL"})
    assert on.startswith("## base series")
    assert "Weighted news aggregation" in on
    assert "unweighted = published per-day mean" in on
