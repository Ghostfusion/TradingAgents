"""yfinance screener + market movers: row shape, rendering, invalid-kind
guidance, empty-data degradation, and router integration.

All network access is mocked at the screener seam, so these run offline.
"""

import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface, screener
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError

pytestmark = pytest.mark.timeout(180)


def _quote(symbol, price, change_pct, name="X"):
    return {
        "symbol": symbol,
        "shortName": name,
        "regularMarketPrice": price,
        "regularMarketChangePercent": change_pct,
        "trailingPE": 12.5 if change_pct > 0 else -3.1,
        "epsTrailingTwelveMonths": 2.4 if change_pct > 0 else -0.7,
        "beta": 1.25 if change_pct > 0 else 0.8,
        "marketCap": 340_000_000_000 if change_pct > 0 else 25_000_000,
        "regularMarketVolume": 1_200_000,
    }


_QUOTES = [_quote("AAPL", 340.5, 1.25, "Apple"), _quote("ZZZZ", 0.38, -1.08, "Mercer")]


def test_screen_renders_row_shape():
    with __import__("unittest").mock.patch.object(
        screener, "_fetch_quotes", return_value=_QUOTES
    ):
        out = screener.screen_equities("us", limit=5)
    assert "Equity screen" in out
    assert "| Symbol | Name | Price | Chg % | P/E | EPS | Beta | Mkt Cap |" in out
    assert "| AAPL | Apple | 340.5 | 1.25 | 12.5 | 2.4 | 1.25 | 340.00B |" in out


def test_screen_market_mapping():
    # friendly market names resolve to predefined Yahoo queries
    assert screener._resolve_query("us") == "aggressive_small_caps"
    assert screener._resolve_query("value") == "undervalued_large_caps"


def test_screen_unknown_query_returns_guidance():
    with __import__("unittest").mock.patch.object(
        screener, "_fetch_quotes", return_value=[]
    ):
        out = screener.screen_equities("us", limit=5, filters="not_a_real_query")
    # A sentinel prefix (not a plain guidance string) so route_to_vendor does
    # not cache the bad-argument reply for 6h as if it were real data.
    assert out.startswith("DATA_UNAVAILABLE:")
    assert "Known predefined" in out


def test_screen_empty_raises_no_data():
    with __import__("unittest").mock.patch.object(screener, "_fetch_quotes", return_value=[]), \
            pytest.raises(NoMarketDataError):
        screener.screen_equities("us", limit=5)


def test_screen_network_failure_raises_rate_limit():
    # Patch the yfinance seam (the real `_fetch_quotes` wraps any network
    # failure into VendorRateLimitError; patching it directly would bypass
    # that wrapping).
    def boom(*a, **k):
        raise RuntimeError("HTTP Error 429")

    with __import__("unittest").mock.patch.object(
        screener._yf_screener, "screen", side_effect=boom
    ), pytest.raises(VendorRateLimitError):
        screener.screen_equities("us", limit=5)


def test_movers_renders_gainers():
    with __import__("unittest").mock.patch.object(
        screener, "_fetch_quotes", return_value=_QUOTES
    ):
        out = screener.get_market_movers("gainers", limit=3)
    assert "Market movers: gainers" in out
    assert "| AAPL | Apple | 340.5 | 1.25 |" in out
    assert "| Volume |" in out


def test_movers_invalid_kind_returns_guidance():
    out = screener.get_market_movers("bogus")
    assert "invalid kind" in out
    assert "gainers" in out


def test_movers_empty_raises_no_data():
    with __import__("unittest").mock.patch.object(screener, "_fetch_quotes", return_value=[]), \
            pytest.raises(NoMarketDataError):
        screener.get_market_movers("losers")


# ---------------------------------------------------------------------------
# Router integration (category registration + chain)
# ---------------------------------------------------------------------------


class TestScreenerRouting:
    def setup_method(self):
        config_module.reset_config()
        set_config({"vendor_cache_enabled": False})  # hermetic: no disk cache writes

    def teardown_method(self):
        config_module.reset_config()

    def test_categories_route_to_yfinance(self):
        assert interface.get_category_for_method("screen_equities") == "equity_screener"
        assert interface.get_category_for_method("get_market_movers") == "market_movers"
        assert "equity_screener" in interface.OPTIONAL_CATEGORIES
        assert "market_movers" in interface.OPTIONAL_CATEGORIES
        set_config({"data_vendors": {"equity_screener": "yfinance"}})
        with __import__("unittest").mock.patch.object(
            screener, "_fetch_quotes", return_value=_QUOTES
        ):
            out = interface.route_to_vendor("screen_equities", "us", 5, None)
        assert "Equity screen" in out

    def test_no_data_degrades_to_sentinel(self):
        set_config({"data_vendors": {"market_movers": "yfinance"}})
        with __import__("unittest").mock.patch.object(screener, "_fetch_quotes", return_value=[]):
            out = interface.route_to_vendor("get_market_movers", "gainers")
        assert out.startswith("NO_DATA_AVAILABLE")


if __name__ == "__main__":
    import unittest

    unittest.main()
