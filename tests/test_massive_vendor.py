"""Massive.com vendor: news sentiment rendering, ticker filtering, error
taxonomy, and router integration. All API access is mocked, so these run
without a network connection.
"""

import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface, massive
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from tradingagents.dataflows.massive import get_news_massive, massive_api_key


def _article(title, tickers, *, published="2026-08-20T10:00:00Z"):
    """A single provider article carrying several tickers, each with sentiment."""
    insights = [
        {"ticker": t, "sentiment": s, "sentiment_reasoning": r}
        for t, s, r in tickers
    ]
    return {
        "title": title,
        "tickers": [t for t, _, _ in tickers],
        "insights": insights,
        "description": "A sample description.",
        "published_utc": published,
        "article_url": "https://example.com/a",
        "publisher": {"name": "ExampleNews"},
    }


_AAPL_ARTICLES = {
    "results": [
        _article(
            "Apple rallies on AI",
            [("AAPL", "positive", "Strong AI-driven upside."), ("MSFT", "neutral", "Context.")],
        ),
        _article(
            "Apple under pressure",
            [("AAPL", "negative", "Valuation concerns.")],
        ),
        _article(
            "Microsoft earnings",
            [("MSFT", "positive", "Cloud growth.")],
        ),
    ]
}


@pytest.mark.unit
class MassiveKeyTests(unittest.TestCase):
    def test_key_from_env(self):
        with mock.patch.dict("os.environ", {"MASSIVE_API_KEY": "k"}, clear=False):
            self.assertEqual(massive_api_key(), "k")


@pytest.mark.unit
class MassiveNewsTests(unittest.TestCase):
    def test_renders_only_requested_tickers_sentiment(self):
        with mock.patch.object(massive, "_get", return_value=_AAPL_ARTICLES):
            out = get_news_massive("AAPL", "2026-08-13", "2026-08-20")
        # Only the two AAPL articles survive the ticker filter.
        self.assertIn("Apple rallies on AI", out)
        self.assertIn("Apple under pressure", out)
        self.assertNotIn("Microsoft earnings", out)
        # Per-article sentiment is rendered.
        self.assertIn("Sentiment: positive", out)
        self.assertIn("Sentiment reasoning: Strong AI-driven upside.", out)
        self.assertIn("Sentiment: negative", out)

    def test_no_matching_ticker_raises_no_market_data(self):
        with (
            mock.patch.object(massive, "_get", return_value=_AAPL_ARTICLES),
            self.assertRaises(NoMarketDataError),
        ):
            get_news_massive("TSLA", "2026-08-13", "2026-08-20")

    def test_empty_payload_raises_no_market_data(self):
        with (
            mock.patch.object(massive, "_get", return_value={"results": []}),
            self.assertRaises(NoMarketDataError),
        ):
            get_news_massive("AAPL", "2026-08-13", "2026-08-20")


@pytest.mark.unit
class MassiveErrorTaxonomyTests(unittest.TestCase):
    def test_missing_key_raises_not_configured(self):
        with (
            mock.patch.object(massive, "massive_api_key", return_value=None),
            self.assertRaises(VendorNotConfiguredError),
        ):
            massive._get("/v2/reference/news")

    def test_http_429_raises_rate_limit(self):
        resp = mock.Mock(status_code=429, json=lambda: {})
        with (
            mock.patch("requests.get", return_value=resp),
            mock.patch("time.sleep"),
            self.assertRaises(VendorRateLimitError),
        ):
            massive._get("/v2/reference/news", {})

    def test_http_401_raises_not_configured(self):
        resp = mock.Mock(status_code=401, json=lambda: {})
        with (
            mock.patch("requests.get", return_value=resp),
            self.assertRaises(VendorNotConfiguredError),
        ):
            massive._get("/v2/reference/news", {})


@pytest.mark.unit
class MassiveRouterTests(unittest.TestCase):
    def test_massive_registered_as_news_vendor(self):
        self.assertIn("massive", interface.VENDOR_METHODS["get_news"])
        self.assertIn("massive", interface.VENDOR_LIST)

    def test_get_news_routes_to_massive_when_configured(self):
        config_module.set_config(
            {"data_vendors": {"news_data": "massive"}}
        )
        with mock.patch.object(massive, "_get", return_value=_AAPL_ARTICLES):
            out = interface.route_to_vendor("get_news", "AAPL", "2026-08-13", "2026-08-20")
        self.assertIn("Apple rallies on AI", out)
