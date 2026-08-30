"""Twelve Data vendor tests (hermetic; mock the network seam ``_requests.get``).
"""

from __future__ import annotations

from unittest import mock

import pytest

import tradingagents.dataflows.twelve_data as module
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(180)


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("TWELVEDATA_API_KEY", "td_test")


def _resp(status=200, payload=None, is_error_payload=False):
    r = mock.Mock()
    r.status_code = status
    if is_error_payload:
        r.json.return_value = {"status": "error", "message": "out of API credits"}
    else:
        r.json.return_value = payload
    return r


def _time_series_payload():
    return {
        "meta": {"symbol": "AAPL", "interval": "1day"},
        "values": [
            {"datetime": "2026-08-04", "open": "302.73", "high": "310.42",
             "low": "301.32", "close": "309.38", "volume": "68001000"},
            {"datetime": "2026-08-03", "open": "309.58", "high": "311.80",
             "low": "302.56", "close": "303.42", "volume": "75052000"},
        ],
    }


# ---------------------------------------------------------------------------
# key resolution + errors
# ---------------------------------------------------------------------------


def test_missing_key_raises_not_configured(monkeypatch):
    from contextlib import ExitStack

    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
        monkeypatch.setattr(module, "twelve_data_api_key", lambda: None)
        with mock.patch.object(module, "_requests") as mreq:
            with pytest.raises(VendorNotConfiguredError):
                module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")
            mreq.get.assert_not_called()


def test_error_payload_raises_rate_limit(monkeypatch):
    with mock.patch.object(
        module, "_requests", spec=True
    ) as mreq:
        mreq.get.return_value = _resp(200, is_error_payload=True)
        with pytest.raises(VendorRateLimitError):
            module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")


def test_429_raises_rate_limit(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(429, {})
        with pytest.raises(VendorRateLimitError):
            module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")


def test_no_values_raises_no_data(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, {"meta": {}, "values": []})
        with pytest.raises(NoMarketDataError):
            module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")


# ---------------------------------------------------------------------------
# OHLCV CSV
# ---------------------------------------------------------------------------


def test_stock_data_csv_shape(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, _time_series_payload())
        out = module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")
    assert "Date,Open,High,Low,Close,Volume" in out
    # Twelve Data returns ascending here (order=asc); both rows present.
    assert "2026-08-03,309.58,311.80,302.56,303.42,75052000" in out
    assert "2026-08-04,302.73,310.42,301.32,309.38,68001000" in out


def test_stock_data_passes_interval_and_dates(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, _time_series_payload())
        module.get_stock_data_twelve_data("AAPL", "2026-08-01", "2026-08-08")
    kwargs = mreq.get.call_args[1]["params"]
    assert kwargs["interval"] == "1day"
    assert kwargs["symbol"] == "AAPL"
    assert kwargs["start_date"] == "2026-08-01"


# ---------------------------------------------------------------------------
# quote snapshot
# ---------------------------------------------------------------------------


def test_market_snapshot_renders(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(
            200,
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "close": "319.70",
                "open": "316.85",
                "high": "322.37",
                "low": "315.45",
                "change": "5.12",
                "percent_change": "1.63",
                "datetime": "2026-08-28",
            },
        )
        out = module.get_market_snapshot_twelve_data("AAPL")
    assert "## Market Snapshot — AAPL (Twelve Data)" in out
    assert "close: 319.70" in out
    assert "ticker: AAPL" in out


def test_market_snapshot_no_symbol_raises(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, {"name": "x"})
        with pytest.raises(NoMarketDataError):
            module.get_market_snapshot_twelve_data("AAPL")


# ---------------------------------------------------------------------------
# crypto
# ---------------------------------------------------------------------------


def test_crypto_code():
    assert module._crypto_code("BTC-USD") == "BTC/USD"
    assert module._crypto_code("eth-usd") == "ETH/USD"


def test_crypto_prices_csv(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(
            200,
            {
                "meta": {"symbol": "BTC/USD"},
                "values": [
                    {"datetime": "2026-08-28", "open": "80249.59",
                     "high": "81478.87", "low": "76888.00",
                     "close": "77845.87", "volume": "0"},
                ],
            },
        )
        out = module.get_crypto_prices_twelve_data("BTC-USD", "2026-08-28", "2026-08-30")
    assert "Date,Open,High,Low,Close,Volume" in out
    assert "BTC/USD" in str(mreq.get.call_args[1]["params"]["symbol"])
    assert "2026-08-28,80249.59,81478.87,76888.00,77845.87,0" in out


# ---------------------------------------------------------------------------
# interface registration
# ---------------------------------------------------------------------------


def test_registered_in_interface():
    from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS

    assert "twelve_data" in VENDOR_LIST
    assert "twelve_data" in VENDOR_METHODS["get_stock_data"]
    assert "get_market_snapshot_twelve_data" in dir(module)
