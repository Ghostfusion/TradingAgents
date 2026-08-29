"""Tiingo vendor tests (hermetic; mock the network seam ``_tiingo_get``).

Covers the free-tier surfaces live-probed for this integration: EOD OHLCV as
CSV, fundamental statements rendered as canonical-friendly text (so
``statement_parsing._canonicalize`` maps them), the IEX quote snapshot, crypto
OHLCV, the crypto symbol normalizer, and the typed-error taxonomy on a missing
key / rate limit / no rows. All vendor calls are mocked - no network.
"""

from unittest import mock

import pytest

from tradingagents.dataflows import tiingo as module
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(180)


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "tk_test")


def _balance_payload():
    return [
        {
            "date": "2026-06-27T00:00:00.000Z",
            "year": 2026,
            "quarter": 3,
            "statementData": {
                "balanceSheet": [
                    {"dataCode": "totalAssets", "value": 383266000000.0},
                    {"dataCode": "totalLiabilities", "value": 275746000000.0},
                    {"dataCode": "equity", "value": 107520000000.0},
                    {"dataCode": "cashAndEq", "value": 39544000000.0},
                    {"dataCode": "inventory", "value": 11092000000.0},
                    {"dataCode": "acctRec", "value": 58907000000.0},
                    {"dataCode": "debt", "value": 84344000000.0},
                ]
            },
        }
    ]


# ---------------------------------------------------------------------------
# key resolution + errors
# ---------------------------------------------------------------------------


def test_missing_key_raises_not_configured(monkeypatch):
    from contextlib import ExitStack
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "tiingo_api_key", return_value=None))
        with pytest.raises(VendorNotConfiguredError):
            module.get_stock_data_tiingo("AAPL", "2026-08-01", "2026-08-08")


def test_429_raises_rate_limit(monkeypatch):
    from contextlib import ExitStack

    def fake(path, params=None):
        raise VendorRateLimitError("Tiingo 429")

    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "_tiingo_get", side_effect=fake))
        with pytest.raises(VendorRateLimitError):
            module.get_stock_data_tiingo("AAPL", "2026-08-01", "2026-08-08")


def test_no_rows_raises_no_data(monkeypatch):
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "_tiingo_get", return_value=[]))
        with pytest.raises(NoMarketDataError):
            module.get_stock_data_tiingo("AAPL", "2026-08-01", "2026-08-08")


# ---------------------------------------------------------------------------
# EOD OHLCV CSV
# ---------------------------------------------------------------------------


def test_stock_data_csv_shape(monkeypatch):
    payload = [
        {"date": "2026-08-03T00:00:00.000Z", "open": 309.58, "high": 311.8,
         "low": 302.56, "close": 303.42, "volume": 75051951},
        {"date": "2026-08-04T00:00:00.000Z", "open": 302.73, "high": 310.42,
         "low": 301.32, "close": 309.38, "volume": 68000969},
    ]
    with mock.patch.object(module, "_tiingo_get", return_value=payload) as mget:
        out = module.get_stock_data_tiingo("AAPL", "2026-08-01", "2026-08-08")
    # request passes the resampleFreq param when given
    mget.assert_called_once()
    assert "Date,Open,High,Low,Close,Volume" in out
    assert "2026-08-03,309.58,311.80,302.56,303.42,75051951" in out
    # oldest-first order preserved
    assert out.index("2026-08-03") < out.index("2026-08-04")


def test_stock_data_resample_param(monkeypatch):
    from contextlib import ExitStack
    with ExitStack() as stack:
        mget = stack.enter_context(
            mock.patch.object(module, "_tiingo_get", return_value=[{}])
        )
        with pytest.raises(NoMarketDataError):
            module.get_stock_data_tiingo("AAPL", "2026-08-01", "2026-08-08",
                                         resample_freq="weekly")
    assert mget.call_args[0][1]["resampleFreq"] == "weekly"


# ---------------------------------------------------------------------------
# fundamental statements -> canonical text
# ---------------------------------------------------------------------------


def test_balance_sheet_renders_canonical_labels(monkeypatch):
    with mock.patch.object(module, "_tiingo_get", return_value=_balance_payload()):
        out = module.get_balance_sheet_tiingo("AAPL", "2025-01-01", "2026-08-28")
    for label in ("total assets", "total liabilities", "total equity",
                  "cash and cash equivalents", "inventory", "net receivables",
                  "total debt"):
        assert label in out


def test_canonicalize_maps_tiingo_balance(monkeypatch):
    with mock.patch.object(module, "_tiingo_get", return_value=_balance_payload()):
        out = module.get_balance_sheet_tiingo("AAPL", "2025-01-01", "2026-08-28")
    from tradingagents.dataflows.statement_parsing import _canonicalize
    canon = _canonicalize(out)
    for k in ("total_assets", "total_equity", "total_liabilities", "cash",
              "inventory", "net_receivables", "total_debt"):
        assert k in canon, k
    assert canon["total_assets"] == 383266000000.0


def test_income_statement_renders(monkeypatch):
    payload = [{"date": "2026-06-27", "year": 2026, "quarter": 3,
                "statementData": {"incomeStatement": [
                    {"dataCode": "revenue", "value": 109417000000.0},
                    {"dataCode": "netIncComStock", "value": 29789000000.0},
                    {"dataCode": "epsDil", "value": 2.02},
                ]}}]
    with mock.patch.object(module, "_tiingo_get", return_value=payload):
        out = module.get_income_statement_tiingo("AAPL", "2026-01-01", "2026-08-28")
    assert "revenue : 109417000000" in out
    assert "net income : 29789000000" in out
    assert "diluted eps : 2.02" in out


def test_cashflow_renders(monkeypatch):
    payload = [{"date": "2026-06-27", "year": 2026, "quarter": 3,
                "statementData": {"cashFlow": [
                    {"dataCode": "ncfo", "value": 34369000000.0},
                    {"dataCode": "capex", "value": -2455000000.0},
                ]}}]
    with mock.patch.object(module, "_tiingo_get", return_value=payload):
        out = module.get_cashflow_tiingo("AAPL", "2026-01-01", "2026-08-28")
    assert "operating cash flow : 34369000000" in out
    assert "capital expenditure : -2455000000" in out


def test_fundamentals_combines(monkeypatch):
    def fake(path, params=None):
        st = (params or {}).get("statementType")
        if st == "incomeStatement":
            return [{"date": "2026-06-27", "year": 2026, "quarter": 3,
                     "statementData": {"incomeStatement": [
                         {"dataCode": "revenue", "value": 1.0}]}}]
        if st == "balanceSheet":
            return [{"date": "2026-06-27", "year": 2026, "quarter": 3,
                     "statementData": {"balanceSheet": [
                         {"dataCode": "totalAssets", "value": 2.0}]}}]
        return [{"date": "2026-06-27", "year": 2026, "quarter": 3,
                 "statementData": {"cashFlow": [
                     {"dataCode": "ncfo", "value": 3.0}]}}]
    with mock.patch.object(module, "_tiingo_get", side_effect=fake):
        out = module.get_fundamentals_tiingo("AAPL", "2026-01-01", "2026-08-28")
    assert "revenue : 1" in out
    assert "total assets : 2" in out
    assert "operating cash flow : 3" in out


# ---------------------------------------------------------------------------
# IEX quote snapshot
# ---------------------------------------------------------------------------


def test_market_snapshot_renders(monkeypatch):
    payload = [{"ticker": "AAPL", "timestamp": "2026-08-28T20:00:00+00:00",
                "open": 316.845, "high": 322.37, "low": 315.4504,
                "tngoLast": 319.7, "prevClose": 314.58, "volume": 38649398}]
    with mock.patch.object(module, "_tiingo_get", return_value=payload):
        out = module.get_market_snapshot_tiingo("AAPL")
    assert "IEX snapshot" in out
    assert "last: 319.7" in out
    assert "prev_close: 314.58" in out


def test_market_snapshot_no_rows_raises(monkeypatch):
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "_tiingo_get", return_value=[]))
        with pytest.raises(NoMarketDataError):
            module.get_market_snapshot_tiingo("AAPL")


# ---------------------------------------------------------------------------
# crypto
# ---------------------------------------------------------------------------


def test_crypto_code():
    assert module._crypto_code("BTC-USD") == "btcusd"
    assert module._crypto_code("ethusd") == "ethusd"


def test_crypto_prices_csv(monkeypatch):
    payload = [{"ticker": "btcusd", "baseCurrency": "btc", "quoteCurrency": "usd",
                "priceData": [{"date": "2026-08-20T00:00:00+00:00",
                               "open": 69300.88, "high": 69536.45,
                               "low": 69281.95, "close": 69521.18,
                               "volume": 87.75146086000007}]}]
    with mock.patch.object(module, "_tiingo_get", return_value=payload):
        out = module.get_crypto_prices_tiingo("btcusd", "2026-08-20", "2026-08-28")
    assert "Date,Open,High,Low,Close,Volume" in out
    assert "2026-08-20,69300.88,69536.45,69281.95,69521.18,87.7515" in out


def test_crypto_no_rows_raises(monkeypatch):
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "_tiingo_get", return_value=[{}]))
        with pytest.raises(NoMarketDataError):
            module.get_crypto_prices_tiingo("btcusd", "2026-08-20", "2026-08-28")


# ---------------------------------------------------------------------------
# interface registration (routing)
# ---------------------------------------------------------------------------


def test_tiingo_registered_in_interface():
    from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS
    assert "tiingo" in VENDOR_LIST
    assert "tiingo" in VENDOR_METHODS["get_stock_data"]
    assert "tiingo" in VENDOR_METHODS["get_fundamentals"]
    assert "tiingo" in VENDOR_METHODS["get_balance_sheet"]
    assert "tiingo" in VENDOR_METHODS["get_cashflow"]
    assert "tiingo" in VENDOR_METHODS["get_income_statement"]


def test_route_to_vendor_tiingo_only(monkeypatch):
    # Force a single-vendor chain and confirm the route hits tiingo.
    from tradingagents.dataflows.config import reset_config, set_config
    from tradingagents.dataflows.interface import route_to_vendor

    with mock.patch.object(module, "_tiingo_get",
                           return_value=[{"date": "2026-08-03", "open": 1.0,
                                          "high": 2.0, "low": 0.5, "close": 1.5,
                                          "volume": 100}]):
        set_config({"data_vendors": {"core_stock_apis": "tiingo"}})
        try:
            out = route_to_vendor("get_stock_data", "AAPL", "2026-08-01", "2026-08-08")
        finally:
            reset_config()
    assert "Date,Open,High,Low,Close,Volume" in out
