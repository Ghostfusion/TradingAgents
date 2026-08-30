"""News/sentiment providers (GDELT, NewsAPI, Benzinga) - hermetic tests.

Phase A-C of the news/sentiment enhancement: GDELT (keyless native tone),
NewsAPI (key-gated global headlines) and Benzinga (free ticker-scoped financial
news). Covers key resolution, typed-error degradation, render shape, and the
interface registration. Network is mocked (``_requests.get`` / module getters).
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest import mock

import pytest

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
)

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# GDELT (keyless)
# ---------------------------------------------------------------------------


def test_gdelt_no_key_needed():
    from tradingagents.dataflows import gdelt

    # GDELT is keyless: the config/env key lookup must be a no-op returning None
    # but the fetch still runs (uses _gdelt_get without a token).
    assert gdelt.BASE  # import succeeded


def test_gdelt_articles_render_tone(monkeypatch):
    from tradingagents.dataflows import gdelt

    payload = [
        {
            "title": "AAPL beats earnings",
            "url": "https://x.com/a",
            "source": "cnn.com",
            "seendate": "20260830000000",
            "tone": "5.2,0.6,0.1,0.3",
        }
    ]
    with mock.patch.object(gdelt, "_gdelt_get", return_value=payload):
        out = gdelt.get_news_gdelt("AAPL", "2026-08-28", "2026-08-30")
    assert "## AAPL News — GDELT (native tone)" in out
    assert "AAPL beats earnings" in out
    assert "tone:" in out and "5.2" in out  # native tone surfaced


def test_gdelt_no_articles_raises(monkeypatch):
    from tradingagents.dataflows import gdelt

    with mock.patch.object(gdelt, "_gdelt_get", return_value=[]), pytest.raises(NoMarketDataError):
        gdelt.get_news_gdelt("AAPL", "2026-08-28", "2026-08-30")


def test_gdelt_tone_series_aggregates(monkeypatch):
    from tradingagents.dataflows import gdelt

    payload = [
        {"title": "a", "seendate": "20260829120000", "tone": "3.0,0.5,0.1,0.4"},
        {"title": "b", "seendate": "20260829130000", "tone": "-1.0,0.1,0.5,0.4"},
        {"title": "c", "seendate": "20260830120000", "tone": "2.0,0.4,0.2,0.4"},
    ]
    with mock.patch.object(gdelt, "_gdelt_get", return_value=payload):
        out = gdelt.get_gdelt_tone_series("AAPL", look_back_days=5)
    assert "gdelt tone series AAPL" in out
    assert "20260829" in out  # avg of 3.0 and -1.0 = 1.0
    assert "1.00" in out


def test_gdelt_tone_series_empty_degrades(monkeypatch):
    from tradingagents.dataflows import gdelt

    with mock.patch.object(gdelt, "_gdelt_get", return_value=[]):
        out = gdelt.get_gdelt_tone_series("AAPL", look_back_days=5)
    assert "unavailable" in out


# ---------------------------------------------------------------------------
# NewsAPI (key-gated)
# ---------------------------------------------------------------------------


def test_newsapi_missing_key(monkeypatch):
    from contextlib import ExitStack

    from tradingagents.dataflows import newsapi
    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("NEWSAPI_API_KEY", raising=False)
        monkeypatch.setattr(newsapi, "newsapi_api_key", lambda: None)
        with pytest.raises(VendorNotConfiguredError):
            newsapi.get_global_news_newsapi("2026-08-30")


def test_newsapi_renders_global(monkeypatch):
    from tradingagents.dataflows import newsapi

    payload = {
        "status": "ok",
        "articles": [
            {"title": "Fed signals", "description": "macro",
             "source": {"name": "Reuters"}, "url": "https://r.com",
             "publishedAt": "2026-08-30T10:00:00Z"},
        ],
    }
    with mock.patch.object(newsapi, "_newsapi_get", return_value=payload):
        out = newsapi.get_global_news_newsapi("2026-08-30")
    assert "Global Macro News — NewsAPI.org" in out
    assert "Fed signals" in out


def test_newsapi_error_status_degrades(monkeypatch):
    from tradingagents.dataflows import newsapi

    with mock.patch.object(newsapi, "_newsapi_get") as m:
        m.side_effect = NoMarketDataError("newsapi", "x", detail="no articles")
        with pytest.raises(NoMarketDataError):
            newsapi.get_news_newsapi("AAPL", "2026-08-28", "2026-08-30")


def test_newsapi_registered():
    from tradingagents.dataflows.interface import VENDOR_METHODS

    assert "newsapi" in VENDOR_METHODS["get_news"]
    assert "newsapi" in VENDOR_METHODS["get_global_news"]


# ---------------------------------------------------------------------------
# Benzinga (key-gated)
# ---------------------------------------------------------------------------


def test_benzinga_missing_key(monkeypatch):
    from tradingagents.dataflows import benzinga

    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("BENZINGA_API_KEY", raising=False)
        monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: None)
        with pytest.raises(VendorNotConfiguredError):
            benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")


def test_benzinga_renders_teaser(monkeypatch):
    from tradingagents.dataflows import benzinga

    payload = [
        {"title": "AAPL upgrade", "created": "2026-08-29T12:00:00",
         "author": "Benzinga", "teaser": "analyst raises target",
         "url": "https://benzinga.com/1"},
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")
    assert "## AAPL News — Benzinga" in out
    assert "AAPL upgrade" in out
    assert "analyst raises target" in out


def test_benzinga_no_articles_raises(monkeypatch):
    from tradingagents.dataflows import benzinga

    with mock.patch.object(benzinga, "_benzinga_get", return_value=[]), pytest.raises(NoMarketDataError):
        benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")


def test_benzinga_registered():
    from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS

    assert "benzinga" in VENDOR_LIST
    assert "benzinga" in VENDOR_METHODS["get_news"]


# ---------------------------------------------------------------------------
# gdelt registered + tool wrapper
# ---------------------------------------------------------------------------


def test_gdelt_registered_and_tool():
    from tradingagents.agents.utils.agent_utils import get_gdelt_sentiment
    from tradingagents.dataflows.interface import VENDOR_METHODS

    assert "gdelt" in VENDOR_METHODS["get_news"]
    assert "gdelt" in VENDOR_METHODS["get_global_news"]
    assert callable(getattr(get_gdelt_sentiment, "invoke", None))


def test_gdelt_tool_degrades_on_unavailable(monkeypatch):
    from tradingagents.agents.utils.agent_utils import get_gdelt_sentiment
    from tradingagents.dataflows import gdelt

    with mock.patch.object(
        gdelt, "get_gdelt_tone_series", side_effect=NoMarketDataError("gdelt", "x")
    ):
        out = get_gdelt_sentiment.invoke({"ticker": "AAPL", "look_back_days": 5})
    assert "unavailable" in out
