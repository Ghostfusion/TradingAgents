"""News-sentiment series vendor + tool wiring tests (Phase 3).

Hermetic: vendor network seams mocked (route_to_vendor / _eodhd_get-style
points helpers / OHLCV cache), no real API calls.
"""

import numpy as np
import pytest

from tradingagents.dataflows.eodhd import get_news_sentiment_eodhd
from tradingagents.dataflows.gdelt import get_news_sentiment_gdelt
from tradingagents.strategies import sentiment_research as _sr

pytestmark = pytest.mark.timeout(120)


# --- vendor renderers ------------------------------------------------------


def test_eodhd_sentiment_renders_table(monkeypatch):
    points = [
        {"date": "2026-08-25", "score": 0.5, "n": 10},
        {"date": "2026-08-26", "score": -0.3, "n": 4},
        {"date": "2026-08-27", "score": 0.2, "n": 7},
    ]
    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd",
        lambda *a: points,
    )
    out = get_news_sentiment_eodhd("AAPL", "2026-08-20", "2026-08-29")
    assert "Daily News Sentiment" in out
    assert "| 2026-08-26 | -0.30" in out
    assert "latest" in out and "sma_7d" in out


def test_eodhd_sentiment_no_data(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd",
        lambda *a: None,
    )
    out = get_news_sentiment_eodhd("AAPL", "2026-08-20", "2026-08-29")
    assert "unavailable" in out.lower()


def test_gdelt_sentiment_renders(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.gdelt._sentiment_points_gdelt",
        lambda *a: [
            {"date": "2026-08-25", "score": 1.2, "n": 3},
            {"date": "2026-08-26", "score": -2.0, "n": 2},
        ],
    )
    out = get_news_sentiment_gdelt("AAPL", "2026-08-20", "2026-08-29")
    assert "GDELT" in out and "2026-08-26" in out


def test_gdelt_sentiment_no_data(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.gdelt._sentiment_points_gdelt", lambda *a: None
    )
    out = get_news_sentiment_gdelt("AAPL", "2026-08-20", "2026-08-29")
    assert "unavailable" in out.lower()


# --- AV parser (aggregate path, hermetic feed) -----------------------------


def test_av_points_parses_ticker_scores(monkeypatch):
    from tradingagents.dataflows.alpha_vantage_news import _sentiment_points_alpha_vantage

    feed = {
        "feed": [
            {
                "time_published": "20260825T140000Z",
                "overall_sentiment_score": 0.9,
                "ticker_sentiment": [
                    {"ticker": "AAPL", "ticker_sentiment_score": 0.4, "relevance_score": 0.8}
                ],
            },
            {
                "time_published": "20260826T150000Z",
                "overall_sentiment_score": -0.9,
                "ticker_sentiment": [
                    {"ticker": "AAPL", "ticker_sentiment_score": -0.2, "relevance_score": 0.5}
                ],
            },
        ]
    }
    monkeypatch.setattr(
        "tradingagents.dataflows.alpha_vantage_news.get_news", lambda *a, **k: feed
    )
    pts = _sentiment_points_alpha_vantage("AAPL", "2026-08-20", "2026-08-29")
    assert pts is not None
    assert pts[0]["score"] == pytest.approx(0.4)
    assert pts[1]["score"] == pytest.approx(-0.2)
    assert [p["n"] for p in pts] == [1, 1]
    # Post-16:00 UTC rollover: 15:00 UTC is 11:00 ET -> same day; a 22:00 UTC article rolls.
    feed["feed"].append(
        {
            "time_published": "20260826T220000Z",
            "overall_sentiment_score": 0.5,
            "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": 0.5}],
        }
    )
    pts2 = _sentiment_points_alpha_vantage("AAPL", "2026-08-20", "2026-08-29")
    assert pts2[-1]["date"] == "2026-08-27"
    assert pts2[-1]["n"] == 1


# --- routed tool -----------------------------------------------------------


def test_get_news_sentiment_routes(monkeypatch):
    from tradingagents.agents.utils.news_data_tools import get_news_sentiment

    captured = {}

    def fake_route(method, ticker, start, end):
        captured.update(method=method, ticker=ticker, start=start, end=end)
        return "## series"

    monkeypatch.setattr(
        "tradingagents.agents.utils.news_data_tools.route_to_vendor", fake_route
    )
    out = get_news_sentiment.invoke(
        {"ticker": "AAPL", "start_date": "2026-08-01", "end_date": "2026-08-08"}
    )
    assert captured == {
        "method": "get_news_sentiment",
        "ticker": "AAPL",
        "start": "2026-08-01",
        "end": "2026-08-08",
    }
    assert out == "## series"


# --- analysis tools --------------------------------------------------------


def test_news_sentiment_series_tool_routes(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import get_news_sentiment_series

    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools.route_to_vendor",
        lambda *a, **k: "## AAPL Daily News Sentiment.",
    )
    out = get_news_sentiment_series.invoke({"ticker": "AAPL"})
    assert "Daily News Sentiment" in out


def test_sentiment_lead_lag_tool_renders(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import (
        _RUN_OHLCV_CACHE,
        get_sentiment_lead_lag,
    )

    dates = [f"2026-08-{d:02d}" for d in range(1, 41)]
    closes = [100.0 + i for i in range(40)]
    _RUN_OHLCV_CACHE[("AAPL", 320)] = {
        "dates": dates,
        "closes": closes,
        "opens": closes,
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [1_000_000.0] * 40,
    }
    points = [
        {"date": f"2026-08-{d:02d}", "score": 0.05 * d, "n": 3} for d in range(1, 41)
    ]

    def fake_points(*a, **k):
        return points

    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd", fake_points
    )
    out = get_sentiment_lead_lag.invoke({"ticker": "AAPL", "max_lags": 3})
    assert "Sentiment Lead/Lag" in out
    assert "spearman" in out.lower()
    _RUN_OHLCV_CACHE.clear()


def test_sentiment_lead_lag_no_sentiment_degrades(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import get_sentiment_lead_lag

    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.alpha_vantage_news._sentiment_points_alpha_vantage",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.gdelt._sentiment_points_gdelt", lambda *a, **k: None
    )
    out = get_sentiment_lead_lag.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


# --- agent_utils / graph binding -------------------------------------------


def test_agent_utils_exports_new_tools():
    from tradingagents.agents.utils import agent_utils as au

    for name in ("get_news_sentiment", "get_news_sentiment_series", "get_sentiment_lead_lag"):
        assert hasattr(au, name)
        assert name in au.__all__


def test_research_scale_usable_by_overlay():
    # The overlay fold uses the computed series' innovation + name-level IC.
    scale = _sr.sentiment_factor_scale(0.05, 0.3, min_ic=0.02)
    assert scale == 1.2
    assert _sr.sentiment_factor_scale(-0.05, 0.3) == 0.8


# --- Phase 4: factor eval script (hermetic panel + render) ------------------


def test_eval_panel_and_render(monkeypatch):
    from scripts import sentiment_factor_eval as ev

    tickers = [f"T{i}" for i in range(12)]
    dates = [f"2026-08-{d:02d}" for d in range(1, 61)]
    rng = np.random.default_rng(11)
    close_maps, pts = {}, {}
    for t in tickers:
        closes = [100.0 * (1 + 0.001 * i + 0.02 * rng.standard_normal()) for i in range(60)]

        closes = list(np.cumprod([1.0] + [0.001 + 0.02 * rng.standard_normal() for _ in range(59)])) * 100
        cm = {d: float(c) for d, c in zip(dates, closes, strict=False)}
        close_maps[t] = cm
        # Planted signal from the name's 3-day forward return + noise.
        fwd = [cm[d2] / cm[d] - 1.0 for d, d2 in zip(dates[:-3], dates[3:], strict=False)] + [0.0] * 3
        pts[t] = [
            {"date": d, "score": float(3.0 * fwd[i] + rng.standard_normal()), "n": 2}
            for i, d in enumerate(dates)
        ]

    monkeypatch.setattr(ev, "_fetch_close_map", lambda t, days=320: close_maps[t])
    monkeypatch.setattr(ev, "_fetch_points", lambda t, s, e: pts[t])
    sent, prices = ev.build_panel(tickers, dates[0], dates[-1])
    assert len(sent) >= 10 and len(prices) >= 10
    report = ev.run_eval(tickers, dates[0], dates[-1], horizons=(3,), holding=3, fees_bps=10, oos_split=0.3)
    assert report["ok"] is True
    assert report["rolling_ic"]["metrics"]["periods"] > 5
    md = ev._render(report, dates[-1])
    assert "Sentiment Factor Evaluation" in md
    assert "mean_rank_ic" in md


def test_eval_panel_too_thin():
    from scripts import sentiment_factor_eval as ev

    report = ev.run_eval(["A"], "2026-08-01", "2026-08-10")
    assert report["ok"] is False
    assert "insufficient" in report["message"].lower()

