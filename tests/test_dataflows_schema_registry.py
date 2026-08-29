"""Unit tests for OpenBB-derived dataflow envelope + registry (P1-P2)."""

from unittest.mock import patch

from tradingagents.dataflows import registry as R
from tradingagents.dataflows.schema import VendorResult, VendorWarning

# --------------------------------------------------------------------------
# VendorResult envelope
# --------------------------------------------------------------------------


def test_vendor_result_ok_default():
    r = VendorResult(results="data")
    assert r.ok is True and r.error_kind is None


def test_vendor_result_error_kind():
    r = VendorResult(results=None, error_kind="NoMarketDataError", extra={"detail": "x"})
    assert r.ok is False


def test_vendor_result_to_dict_json_safe():
    r = VendorResult(results=[{"a": 1}], provider="yfinance",
                     warnings=[VendorWarning("rate_limit", "degraded")])
    d = r.to_dict()
    assert d["provider"] == "yfinance"
    assert d["warnings"][0]["kind"] == "rate_limit"
    assert d["ok"] is True


def test_vendor_result_to_llm_error():
    r = VendorResult(results=None, error_kind="VendorRateLimitError", extra={"detail": "429"})
    assert "unavailable" in r.to_llm()


def test_vendor_result_to_llm_tabular_records():
    r = VendorResult(results=[{"ticker": "AAPL", "close": 200.5}])
    llm = r.to_llm()
    assert "AAPL" in llm and "200.5" in llm


def test_vendor_result_to_markdown_table():
    r = VendorResult(results=[{"ticker": "AAPL", "close": 200.5},
                              {"ticker": "NVDA", "close": 300.1}])
    md = r.to_markdown()
    assert "| ticker | close |" in md
    assert "AAPL" in md and "NVDA" in md


# --------------------------------------------------------------------------
# registry.coverage / credentials
# --------------------------------------------------------------------------


def test_coverage_get_stock_data_nonempty():
    cov = R.coverage("get_stock_data")
    assert isinstance(cov, list) and len(cov) >= 2


def test_required_credentials_mapping():
    assert "finnhub_api_key" in R.required_credentials("finnhub")
    assert R.required_credentials("alpaca") == ("alpaca_api_key_id", "alpaca_api_secret")
    assert R.required_credentials("yfinance") == ()


def test_missing_credentials():
    assert "alpaca_api_key_id" in R.missing_credentials("alpaca", {})
    assert R.missing_credentials("alpaca", {"alpaca_api_key_id": "x",
                                            "alpaca_api_secret": "y"}) == []


def test_command_map_shape():
    cm = R.command_map()
    assert "get_stock_data" in cm
    entry = cm["get_stock_data"]
    assert "vendors" in entry and "category" in entry
    assert isinstance(entry["vendors"], list)


# --------------------------------------------------------------------------
# registry.filter_params + route_to_vendor_typed (via patch)
# --------------------------------------------------------------------------


def test_filter_params_keeps_supported_warns_extra():
    import tradingagents.dataflows.interface as I

    with patch.object(I, "VENDOR_METHODS", {
        "get_stock_data": {"yfinance": lambda symbol, start_date, end_date: "x"}
    }):
        kept, warned = R.filter_params("get_stock_data",
                                       {"symbol": "AAPL", "bogus": 1})
        assert kept == {"symbol": "AAPL"}
        assert warned == ["bogus"]


def test_route_to_vendor_typed_sentinel_mapping():
    import tradingagents.dataflows.interface as I

    with patch.object(I, "route_to_vendor", return_value="NO_DATA_AVAILABLE: no data"):
        r = I.route_to_vendor_typed("get_stock_data", "AAPL", "a", "b")
        assert r.error_kind == "NoMarketDataError" and r.ok is False


def test_route_to_vendor_typed_ok_provenance():
    import tradingagents.dataflows.interface as I

    with patch.object(I, "route_to_vendor", return_value="csv,rows"):
        r = I.route_to_vendor_typed("get_stock_data", "AAPL", "a", "b")
        assert r.ok is True and r.results == "csv,rows"
        assert r.provider  # non-empty chain string


def test_route_to_vendor_typed_disabled():
    import tradingagents.dataflows.interface as I

    with patch.object(I, "route_to_vendor", return_value="DATA_DISABLED: off"):
        r = I.route_to_vendor_typed("get_stock_data", "AAPL", "a", "b")
        assert r.error_kind == "DataDisabled"
