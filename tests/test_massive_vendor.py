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
    MassiveNotConfiguredError,
    fetch_macro_backdrop,
    get_corporate_actions_massive,
    get_dividends_massive,
    get_form4_insider_massive,
    get_fundamentals_massive,
    get_ipos_massive,
    get_macro_indicators_massive,
    get_market_snapshot_massive,
    get_news_massive,
    get_ratios_massive,
    get_related_companies_massive,
    get_short_interest_massive,
    get_short_volume_massive,
    get_splits_massive,
    get_top_movers_massive,
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


@pytest.mark.unit
class MassiveShortInterestTests(unittest.TestCase):
    def test_short_interest_formats_latest_first(self):
        rows = [
            {"settlement_date": "2026-07-31", "short_interest": 53736062,
             "avg_daily_volume": 3150012, "days_to_cover": 17.06},
            {"settlement_date": "2026-07-15", "short_interest": 55426276,
             "avg_daily_volume": 3433961, "days_to_cover": 16.14},
        ]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_short_interest_massive("GME")
        self.assertIn("53,736,062", out)
        self.assertIn("17.1", out)
        self.assertIn("Days to cover: 17.1", out)

    def test_short_interest_empty_raises_no_market_data(self):
        with (
            mock.patch.object(massive, "_get", return_value={"results": []}),
            self.assertRaises(NoMarketDataError),
        ):
            get_short_interest_massive("GME")

    def test_short_volume_renders_ratio(self):
        rows = [
            {"date": "2026-08-10", "short_volume_ratio": 42.4,
             "short_volume": 6318868, "total_volume": 14914704},
        ]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_short_volume_massive("AAPL", "2026-08-10", "2026-08-19")
        self.assertIn("42.4%", out)
        self.assertIn("2026-08-10", out)

    def test_short_volume_empty_raises_no_market_data(self):
        with (
            mock.patch.object(massive, "_get", return_value=[]),
            self.assertRaises(NoMarketDataError),
        ):
            get_short_volume_massive("AAPL", "2026-08-10", "2026-08-19")

    def test_short_interest_registered_as_vendor(self):
        self.assertIn("massive", interface.VENDOR_METHODS["get_short_interest"])

    def test_route_short_interest_to_massive_when_configured(self):
        rows = [{"settlement_date": "2026-07-31", "short_interest": 1,
                 "avg_daily_volume": 2, "days_to_cover": 3.0}]
        config_module.set_config(
            {"data_vendors": {"short_interest": "massive"}}
        )
        with mock.patch.object(massive, "_get", return_value=rows):
            out = interface.route_to_vendor("get_short_interest", "GME")
        self.assertIn("Short Interest", out)


@pytest.mark.unit
class MassiveForm4Tests(unittest.TestCase):
    def test_form4_net_open_market(self):
        rows = [
            {"transaction_code": "P", "transaction_value": 500000,
             "transaction_date": "2026-01-05", "owner_name": "ALICE",
             "is_director": True, "transaction_shares": 100,
             "transaction_price_per_share": 100.0},
            {"transaction_code": "S", "transaction_value": 200000,
             "transaction_date": "2026-02-01", "owner_name": "BOB",
             "is_officer": True, "transaction_shares": 50,
             "transaction_price_per_share": 80.5},
            # grant/award A row excluded from net
            {"transaction_code": "A", "transaction_value": 999999,
             "transaction_date": "2026-03-01", "owner_name": "CAROL"},
        ]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_form4_insider_massive("AAPL", "2026-01-01", "2026-08-19")
        self.assertIn("Open-market buys (P): 1 tx", out)
        self.assertIn("Open-market sells (S): 1 tx", out)
        self.assertIn("+300,000", out)  # 500k - 200k
        # The A row must not appear as a sample transaction.
        self.assertNotIn("999,999", out)

    def test_form4_all_sells_negative_net(self):
        rows = [
            {"transaction_code": "S", "transaction_value": 100000,
             "transaction_date": "2026-01-05", "owner_name": "BOB"},
        ]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_form4_insider_massive("AAPL", "2026-01-01", "2026-08-19")
        self.assertIn("-100,000", out)

    def test_form4_empty_raises_no_market_data(self):
        with (
            mock.patch.object(massive, "_get", return_value=[]),
            self.assertRaises(NoMarketDataError),
        ):
            get_form4_insider_massive("AAPL", "2026-01-01", "2026-08-19")


@pytest.mark.unit
class MassiveRatiosTests(unittest.TestCase):
    _RATIOS = {
        "results": [
            {
                "date": "2026-08-19", "ticker": "AAPL",
                "enterprise_value": 3555509835190, "ev_to_ebitda": 26.98,
                "ev_to_sales": 9.22, "price_to_earnings": 34.84,
                "price_to_book": 52.16, "price_to_sales": 9.02,
                "return_on_equity": 1.5284, "return_on_assets": 0.3075,
                "debt_to_equity": 1.52, "current": 0.68, "quick": 0.63,
                "cash": 0.19, "dividend_yield": 0.0044,
                "free_cash_flow": 104339000000, "market_cap": 3479770835190,
            }
        ]
    }

    def test_ratios_format(self):
        with mock.patch.object(massive, "_get", return_value=self._RATIOS):
            out = get_ratios_massive("AAPL", "2026-08-19")
        self.assertIn("EV/EBITDA: 26.98", out)
        self.assertIn("P/E: 34.84", out)
        self.assertIn("ROE: 152.84%", out)  # 1.5284 formatted as percent
        self.assertIn("Div yield: 0.44%", out)

    def test_ratios_empty_is_unavailable(self):
        with mock.patch.object(massive, "_get", return_value={"results": []}):
            out = get_ratios_massive("AAPL")
        self.assertIn("no data returned", out)

    def test_ratios_403_degrades(self):
        with mock.patch.object(
            massive, "_get", side_effect=MassiveNotConfiguredError("403 plan")
        ):
            out = get_ratios_massive("AAPL")
        self.assertIn("upgrade at massive.com/pricing", out)

    def test_fundamentals_uses_ratios(self):
        with mock.patch.object(massive, "_get", return_value=self._RATIOS):
            out = get_fundamentals_massive("AAPL", "2026-08-19")
        self.assertIn("Ratios", out)
        self.assertIn("EV/EBITDA", out)

    def test_fundamentals_registered_as_vendor(self):
        self.assertIn("massive", interface.VENDOR_METHODS["get_fundamentals"])
        self.assertIn("massive", interface.VENDOR_METHODS["get_basic_financials"])


@pytest.mark.unit
class MassiveSnapshotTests(unittest.TestCase):
    def test_snapshot_format(self):
        payload = {
            "ticker": {
                "day": {"c": 120.47, "o": 119.62, "h": 120.53, "l": 118.81,
                         "v": 28727868, "vw": 119.725},
                "prevDay": {"c": 119.49},
                "todaysChange": 0.98, "todaysChangePerc": 0.82,
                "lastQuote": {"p": 120.46, "P": 120.47},
                "lastTrade": {"p": 120.47, "s": 236},
            }
        }
        with mock.patch.object(massive, "_get", return_value=payload):
            out = get_market_snapshot_massive("AAPL")
        self.assertIn("Last: 120.5", out)
        self.assertIn("Today's change", out)
        self.assertIn("0.8%", out)  # todaysChangePerc

    def test_snapshot_empty(self):
        with mock.patch.object(massive, "_get", return_value={}):
            out = get_market_snapshot_massive("AAPL")
        self.assertIn("no data returned", out)

    def test_top_movers_format(self):
        rows = [
            {"ticker": "GME", "todaysChangePerc": 12.5, "day": {"c": 20.1}},
            {"ticker": "BBBY", "todaysChangePerc": 8.9, "day": {"c": 5.6}},
        ]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_top_movers_massive("gainers", 5)
        self.assertIn("GME", out)
        self.assertIn("12.5", out)

    def test_top_movers_bad_direction(self):
        out = get_top_movers_massive("sideways", 5)
        self.assertIn("invalid direction", out)

    def test_top_movers_empty(self):
        with mock.patch.object(massive, "_get", return_value=[]):
            out = get_top_movers_massive("gainers", 5)
        self.assertIn("unavailable", out)


@pytest.mark.unit
class MassiveRow5Tests(unittest.TestCase):
    def test_dividends_format(self):
        rows = [{"pay_date": "2022-11-10", "ex_dividend_date": "2022-11-04",
                 "cash_amount": 0.23, "currency": "USD", "frequency": 4,
                 "distribution_type": "recurring"}]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_dividends_massive("AAPL")
        self.assertIn("0.2", out)
        self.assertIn("2022-11-10", out)
        self.assertIn("freq 4x/yr", out)

    def test_dividends_empty_raises(self):
        with (
            mock.patch.object(massive, "_get", return_value=[]),
            self.assertRaises(NoMarketDataError),
        ):
            get_dividends_massive("AAPL")

    def test_splits_format(self):
        rows = [{"execution_date": "2020-08-31", "split_from": 1.0,
                 "split_to": 4.0, "adjustment_type": "forward_split",
                 "historical_adjustment_factor": 0.25}]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_splits_massive("AAPL")
        self.assertIn("1.0->4.0", out)
        self.assertIn("forward_split", out)

    def test_related_companies_matches_peers_format(self):
        rows = [{"ticker": "MSFT"}, {"ticker": "AMZN"}]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_related_companies_massive("AAPL")
        self.assertTrue(out.startswith("Peers: "))
        self.assertIn("MSFT", out)
        self.assertIn(", ", out)

    def test_ipos_format_and_status(self):
        rows = [{"last_updated": "2026-08-20", "ticker": "SCATU",
                 "issuer_name": "Acq Corp", "final_issue_price": 10.0,
                 "ipo_status": "pending"}]
        with mock.patch.object(massive, "_get", return_value=rows):
            out = get_ipos_massive(1, "pending")
        self.assertIn("SCATU", out)
        self.assertIn("pending", out)

    def test_corporate_actions_combines(self):
        def _fake(_path, params=None):
            if "dividend" in _path:
                return [{"cash_amount": 0.5, "pay_date": "2022-01-01"}]
            if "split" in _path:
                return [{"execution_date": "2020-01-01", "split_from": 1,
                         "split_to": 2, "adjustment_type": "forward_split"}]
            return []
        with mock.patch.object(massive, "_get", side_effect=_fake):
            out = get_corporate_actions_massive("AAPL")
        self.assertIn("Dividends", out)
        self.assertIn("Splits", out)

    def test_row5_registered_as_vendors(self):
        self.assertIn("massive", interface.VENDOR_METHODS["get_company_peers"])
        self.assertIn("massive", interface.VENDOR_METHODS["get_corporate_actions"])



@pytest.mark.unit
class MassiveFailoverTests(unittest.TestCase):
    """The direct Massive tool wrappers must degrade to 'unavailable' when the
    vendor raises NoMarketDataError - not abort the whole analyst/batch symbol.
    Regression for the batch failure seen when Massive lacks a symbol's data."""

    def _patch(self, fn, module_path):
        # Patch the module where the function lives (imports are local in tools).
        import importlib
        mod = importlib.import_module(module_path)
        return mock.patch.object(mod, fn, side_effect=NoMarketDataError("x", "x", "none"))

    def test_get_short_volume_degrades(self):
        from tradingagents.agents.utils.market_position_tools import get_short_volume

        with self._patch("get_short_volume_massive", "tradingagents.dataflows.massive"):
            out = get_short_volume.invoke(
                {"ticker": "hd", "start_date": "2026-08-13", "end_date": "2026-08-20"}
            )
        self.assertIn("short volume unavailable", out)

    def test_get_market_snapshot_degrades(self):
        from tradingagents.agents.utils.market_position_tools import get_market_snapshot

        # Massive 403s AND the EODHD fallback fails -> the tool degrades to an
        # explicit 'unavailable' (never fabricates).
        with self._patch("get_market_snapshot_massive", "tradingagents.dataflows.massive"), mock.patch(
            "tradingagents.dataflows.eodhd.get_market_snapshot_eodhd",
            side_effect=RuntimeError("eodhd down"),
        ):
            out = get_market_snapshot.invoke({"ticker": "nue"})
        self.assertIn("market snapshot unavailable", out)

    def test_get_top_movers_degrades(self):
        from tradingagents.agents.utils.market_position_tools import get_top_movers

        # Massive 403s AND the EODHD fallback fails -> the tool degrades to an
        # explicit 'unavailable' (never fabricates).
        with self._patch("get_top_movers_massive", "tradingagents.dataflows.massive"), mock.patch(
            "tradingagents.dataflows.eodhd.get_top_movers_eodhd",
            side_effect=RuntimeError("eodhd down"),
        ):
            out = get_top_movers.invoke({"direction": "losers"})
        self.assertIn("top movers unavailable", out)

    def test_get_massive_news_degrades(self):
        from tradingagents.agents.utils.news_data_tools import get_massive_news

        with self._patch("get_news_massive", "tradingagents.dataflows.massive"):
            out = get_massive_news.invoke(
                {"ticker": "bby", "start_date": "2026-08-13", "end_date": "2026-08-20"}
            )
        self.assertIn("massive news unavailable", out)

    def test_get_form4_degrades(self):
        from tradingagents.agents.utils.analysis_tools import get_form4_insider

        with self._patch("get_form4_insider_massive", "tradingagents.dataflows.massive"):
            out = get_form4_insider.invoke(
                {"ticker": "x", "start_date": "2026-01-01", "end_date": "2026-08-20"}
            )
        self.assertIn("form-4 insider activity unavailable", out)

    def test_get_ratios_degrades(self):
        from tradingagents.agents.utils.analysis_tools import get_ratios

        with self._patch("get_ratios_massive", "tradingagents.dataflows.massive"):
            out = get_ratios.invoke({"ticker": "x"})
        self.assertIn("ratios unavailable", out)

    def test_get_dividends_degrades(self):
        from tradingagents.agents.utils.moomoo_extra_tools import get_dividends

        with self._patch("get_dividends_massive", "tradingagents.dataflows.massive"):
            out = get_dividends.invoke({"ticker": "x"})
        self.assertIn("dividends unavailable", out)

    def test_get_ipos_degrades(self):
        from tradingagents.agents.utils.moomoo_extra_tools import get_ipos

        with self._patch("get_ipos_massive", "tradingagents.dataflows.massive"):
            out = get_ipos.invoke({"limit": 3})
        self.assertIn("ipos unavailable", out)


