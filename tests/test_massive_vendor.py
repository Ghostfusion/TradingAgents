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
from tradingagents.dataflows.massive import (
    fetch_macro_backdrop,
    get_macro_indicators_massive,
    get_news_massive,
    is_yield_curve_inverted,
    latest_breakeven,
    massive_api_key,
)


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


@pytest.mark.unit
class MassiveMacroTests(unittest.TestCase):
    def test_macro_indicator_formats_report(self):
        rows = [
            {"date": "2026-08-01", "yield_10_year": 4.5},
            {"date": "2026-08-18", "yield_10_year": 4.71},
        ]
        with mock.patch.object(massive, "_get", return_value={"results": rows}):
            out = get_macro_indicators_massive("10y_treasury", "2026-08-18", 60)
        self.assertIn("**Latest:** 4.71", out)
        self.assertIn("yield_10_year", out)

    def test_macro_yield_curve_derives_spread(self):
        rows = [
            {"date": "2026-08-01", "yield_10_year": 4.5, "yield_2_year": 4.0},
            {"date": "2026-08-18", "yield_10_year": 4.71, "yield_2_year": 4.19},
        ]
        with mock.patch.object(massive, "_get", return_value={"results": rows}):
            out = get_macro_indicators_massive("yield_curve", "2026-08-18", 60)
        self.assertIn("0.52", out)  # 4.71 - 4.19

    def test_unknown_alias_returns_guidance_not_exception(self):
        out = get_macro_indicators_massive("not_a_real_alias", "2026-08-18", 60)
        self.assertIn("not a known macro alias", out)

    def test_macro_registered_as_get_macro_indicators_vendor(self):
        self.assertIn("massive", interface.VENDOR_METHODS["get_macro_indicators"])

    def test_route_macro_to_massive_when_configured(self):
        rows = [{"date": "2026-08-18", "market_10_year": 2.25}]
        config_module.set_config({"data_vendors": {"macro_data": "massive"}})
        with mock.patch.object(massive, "_get", return_value={"results": rows}):
            out = interface.route_to_vendor(
                "get_macro_indicators", "inflation_expectations", "2026-08-18", 60
            )
        self.assertIn("2.25", out)


@pytest.mark.unit
class MassiveBackdropTests(unittest.TestCase):
    def test_is_yield_curve_inverted(self):
        self.assertTrue(
            is_yield_curve_inverted([{"yield_10_year": 4.0, "yield_2_year": 4.5}])
        )
        self.assertFalse(
            is_yield_curve_inverted([{"yield_10_year": 4.5, "yield_2_year": 4.0}])
        )
        self.assertIsNone(is_yield_curve_inverted([]))

    def test_latest_breakeven(self):
        self.assertEqual(
            latest_breakeven([{"market_10_year": 2.25}]), 2.25
        )
        self.assertIsNone(latest_breakeven([]))

    def test_fetch_macro_backdrop_stressed_on_inversion(self):
        trees = {"results": [{"date": "2026-08-18", "yield_10_year": 4.0, "yield_2_year": 4.5}]}
        ie = {"results": [{"date": "2026-08-18", "market_10_year": 2.0}]}
        def _fake_get(path, params=None):
            return trees if "treasury" in path else ie
        with mock.patch.object(massive, "_get", side_effect=_fake_get):
            out = fetch_macro_backdrop("2026-08-18")
        self.assertEqual(out["verdict"], "macro-backdrop")
        self.assertEqual(out["scale"], 0.7)
        self.assertTrue(out["curve_inverted"])

    def test_fetch_macro_backdrop_calm(self):
        trees = {"results": [{"date": "2026-08-18", "yield_10_year": 4.5, "yield_2_year": 4.0}]}
        ie = {"results": [{"date": "2026-08-18", "market_10_year": 2.2}]}
        def _fake_get(path, params=None):
            return trees if "treasury" in path else ie
        with mock.patch.object(massive, "_get", side_effect=_fake_get):
            out = fetch_macro_backdrop("2026-08-18")
        self.assertEqual(out["verdict"], "no-macro-stress")
        self.assertEqual(out["scale"], 1.0)

    def test_fetch_macro_backdrop_returns_none_on_failure(self):
        with mock.patch.object(massive, "_get", side_effect=RuntimeError("boom")):
            out = fetch_macro_backdrop("2026-08-18")
        self.assertIsNone(out)
