"""StockData.org vendor tests (hermetic; mock the network seam ``_requests.get``).
"""

from __future__ import annotations

from unittest import mock

import pytest

import tradingagents.dataflows.stockdata as module
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(180)


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("STOCKDATA_API_KEY", "sd_test")


def _resp(status=200, payload=None, error_body=False):
    r = mock.Mock()
    r.status_code = status
    if error_body:
        r.json.return_value = {"error": {"message": "quota exceeded"}}
    else:
        r.json.return_value = payload
    return r


def _eod_payload():
    # newest-first, as StockData.org actually returns
    return {
        "meta": {"date_from": "2026-03-03", "date_to": "2026-08-30"},
        "data": [
            {"date": "2026-08-27T00:00:00.000Z", "open": 310.54, "high": 315.38,
             "low": 309.42, "close": 314.54, "volume": 1062083},
            {"date": "2026-08-26T00:00:00.000Z", "open": 310.38, "high": 315.0,
             "low": 309.1, "close": 313.9, "volume": 1010000},
        ],
    }


# ---------------------------------------------------------------------------
# key resolution + errors
# ---------------------------------------------------------------------------


def test_missing_key_raises_not_configured(monkeypatch):
    from contextlib import ExitStack

    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("STOCKDATA_API_KEY", raising=False)
        monkeypatch.setattr(module, "stockdata_api_key", lambda: None)
        with mock.patch.object(module, "_requests") as mreq:
            with pytest.raises(VendorNotConfiguredError):
                module.get_stock_data_stockdata("AAPL", "2026-08-01", "2026-08-08")
            mreq.get.assert_not_called()


def test_error_body_raises_rate_limit(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, error_body=True)
        with pytest.raises(VendorRateLimitError):
            module.get_stock_data_stockdata("AAPL", "2026-08-01", "2026-08-08")


def test_429_raises_rate_limit(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(429, {})
        with pytest.raises(VendorRateLimitError):
            module.get_stock_data_stockdata("AAPL", "2026-08-01", "2026-08-08")


def test_no_rows_raises_no_data(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, {"meta": {}, "data": []})
        with pytest.raises(NoMarketDataError):
            module.get_stock_data_stockdata("AAPL", "2026-08-01", "2026-08-08")


# ---------------------------------------------------------------------------
# EOD OHLCV CSV (newest-first input -> oldest-first output)
# ---------------------------------------------------------------------------


def test_stock_data_csv_reversed_oldest_first(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, _eod_payload())
        out = module.get_stock_data_stockdata("AAPL", "2026-01-01", "2026-08-30")
    # Input newest-first; output must be oldest-first.
    assert out.index("2026-08-26") < out.index("2026-08-27")
    assert "Date,Open,High,Low,Close,Volume" in out


def test_stock_data_no_date_param(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, _eod_payload())
        module.get_stock_data_stockdata("AAPL", "2026-01-01", "2026-08-30")
    params = mreq.get.call_args[1]["params"]
    assert params["symbols"] == "AAPL"
    assert "date" not in params  # date param returns empty on free tier


# ---------------------------------------------------------------------------
# quote snapshot
# ---------------------------------------------------------------------------


def test_market_snapshot_renders(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(
            200,
            {
                "meta": {"requested": 1, "returned": 1},
                "data": [
                    {"ticker": "AAPL", "name": "Apple Inc", "price": 314.54,
                     "day_change": 0.32, "day_change_percent": 0.1,
                     "day_high": 315.38, "day_low": 309.42},
                ],
            },
        )
        out = module.get_market_snapshot_stockdata("AAPL")
    assert "## Market Snapshot — AAPL (StockData.org)" in out
    assert "price: 314.54" in out
    assert "ticker: AAPL" in out


def test_market_snapshot_no_rows_raises(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, {"meta": {}, "data": []})
        with pytest.raises(NoMarketDataError):
            module.get_market_snapshot_stockdata("AAPL")


# ---------------------------------------------------------------------------
# news
# ---------------------------------------------------------------------------


def test_news_renders(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(
            200,
            {
                "data": [
                    {
                        "title": "AAPL opens new center",
                        "date": "2026-08-30",
                        "source": "gurufocus.com",
                        "description": "Apple opens a new innovation center.",
                    },
                ]
            },
        )
        out = module.get_news_stockdata("AAPL", "2026-08-01", "2026-08-30")
    assert "## AAPL News — StockData.org" in out
    assert "AAPL opens new center" in out
    assert "gurufocus.com" in out


def test_news_no_articles_returns_message(monkeypatch):
    with mock.patch.object(module, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(200, {"data": []})
        out = module.get_news_stockdata("AAPL", "2026-08-01", "2026-08-30")
    assert "No news found" in out


# ---------------------------------------------------------------------------
# interface registration
# ---------------------------------------------------------------------------


def test_registered_in_interface():
    from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS

    assert "stockdata" in VENDOR_LIST
    assert "stockdata" in VENDOR_METHODS["get_stock_data"]
    assert "stockdata" in VENDOR_METHODS["get_news"]
