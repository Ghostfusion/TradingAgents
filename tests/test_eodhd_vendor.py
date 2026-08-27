"""EODHD vendor tests (offline; mock the HTTP layer).

Covers the ``get_stock_data`` vendor contract: CSV shape matching
yfinance/moomoo, oldest-first ordering, typed-error degradation (no data /
rate limit / bad key), and the router fallback chain.
"""

from unittest import mock

import pytest

from tradingagents.dataflows import eodhd
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(180)

# A realistic EODHD /eod response (newest-first, as the API returns).
_EODHD_ROWS = [
    {"date": "2026-08-26", "open": 310.25, "high": 315.43, "low": 308.8, "close": 313.45, "volume": 33571543},
    {"date": "2026-08-25", "open": 310.79, "high": 313.59, "low": 308.21, "close": 309.9, "volume": 25869800},
    {"date": "2026-08-24", "open": 311.47, "high": 313.36, "low": 309.97, "close": 310.34, "volume": 34673600},
]


def _patch_get(rows):
    return mock.patch.object(eodhd, "_eodhd_get", return_value=rows)


def test_formats_csv_oldest_first():
    """The CSV body must be oldest-first with the yfinance column order
    (Date,Open,High,Low,Close,Volume) so the screener parser consumes it."""
    with _patch_get(list(_EODHD_ROWS)):
        out = eodhd.get_stock_data_eodhd("AAPL", "2026-08-01", "2026-08-27")
    lines = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    assert lines[0] == "Date,Open,High,Low,Close,Volume"
    # Oldest first: 2026-08-24 row comes before 2026-08-26.
    assert "2026-08-24" in lines[1]
    assert "2026-08-26" in lines[-1]
    # Column order: Open=311.47, High=313.36, Low=309.97, Close=310.34, Vol=34673600
    assert lines[1].startswith("2026-08-24,311.47,313.36,309.97,310.34,34673600")


def test_empty_rows_raises_no_data():
    with _patch_get([]), pytest.raises(NoMarketDataError):
        eodhd.get_stock_data_eodhd("ZZZZ", "2026-08-01", "2026-08-27")


def test_error_body_raises_no_data():
    """EODHD reports errors as a JSON body with a 'code' field."""
    with mock.patch.object(
        eodhd, "_eodhd_get", return_value={"code": 404, "message": "Not found"}
    ), pytest.raises(NoMarketDataError):
        eodhd.get_stock_data_eodhd("NOPE", "2026-08-01", "2026-08-27")


def test_rate_limit_body_raises_rate_limit():
    """EODHD reports errors as a JSON body with a 'code' field; the
    classification happens inside _eodhd_get, so mock the HTTP layer."""
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {"code": 429, "message": "Limit reached"}
    with mock.patch("requests.get", return_value=resp), pytest.raises(VendorRateLimitError):
        eodhd._eodhd_get("eod/AAPL", {})


def test_missing_key_raises_not_configured():
    with mock.patch.object(eodhd, "eodhd_api_key", return_value=None), pytest.raises(
        VendorNotConfiguredError
    ):
        eodhd.get_stock_data_eodhd("AAPL", "2026-08-01", "2026-08-27")


def test_http_429_raises_rate_limit():
    """A raw HTTP 429 (not a JSON body) must also raise VendorRateLimitError."""
    resp = mock.Mock()
    resp.status_code = 429
    with mock.patch("requests.get", return_value=resp), pytest.raises(VendorRateLimitError):
        eodhd._eodhd_get("eod/AAPL", {})


def test_http_401_raises_not_configured():
    resp = mock.Mock()
    resp.status_code = 401
    with mock.patch("requests.get", return_value=resp), pytest.raises(VendorNotConfiguredError):
        eodhd._eodhd_get("eod/AAPL", {})


def test_router_falls_through_to_eodhd():
    """With the chain forced to eodhd, route_to_vendor serves EODHD data."""
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.interface import route_to_vendor

    set_config({"data_vendors": {"core_stock_apis": "eodhd"}})
    with _patch_get(list(_EODHD_ROWS)):
        out = route_to_vendor("get_stock_data", "AAPL", "2026-08-01", "2026-08-27")
    assert "EODHD" in str(out)
    assert "2026-08-24" in str(out)
