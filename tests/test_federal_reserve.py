"""Federal Reserve risk-free curves: SOFR + Treasury yield-curve parsing, row
shape, lookahead-safety, empty-data degradation, and router integration.

All network access is mocked, so these run offline.
"""

import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import federal_reserve, interface
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError

pytestmark = pytest.mark.timeout(180)

_SOFR_JSON = {
    "refRates": [
        {"effectiveDate": "2026-08-27", "type": "SOFR", "percentRate": 3.64,
         "percentPercentile25": 3.62, "percentPercentile75": 3.7,
         "volumeInBillions": 2836},
        {"effectiveDate": "2026-08-26", "type": "SOFR", "percentRate": 3.64,
         "percentPercentile25": 3.6, "percentPercentile75": 3.7,
         "volumeInBillions": 2859},
    ]
}

_TREASURY_CSV = (
    'Date,"1 Mo","2 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","10 Yr","30 Yr"\n'
    "08/28/2026,3.84,3.86,3.90,4.02,4.15,4.34,4.41,4.48,4.73,5.22\n"
    "08/27/2026,3.81,3.81,3.84,3.94,4.04,4.20,4.30,4.38,4.67,5.19\n"
)


def _resp(json_data=None, text=None, status=200):
    resp = __import__("unittest").mock.Mock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.text = text
    resp.raise_for_status = __import__("unittest").mock.Mock()
    return resp


def test_sofr_renders_rows_oldest_first():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(_SOFR_JSON)):
        out = federal_reserve.get_sofr_curve("2026-08-28")
    assert "SOFR curve" in out
    assert out.index("2026-08-26") < out.index("2026-08-27")
    assert "| 2026-08-27 | 3.64 | 3.62 | 3.7 | 2836 |" in out
    # lookahead-safe window end
    assert "Window: " in out


def test_sofr_no_data_raises():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp({"refRates": []})), \
            pytest.raises(NoMarketDataError):
        federal_reserve.get_sofr_curve("2026-08-28")


def test_sofr_429_raises_rate_limit():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(status=429)), \
            pytest.raises(VendorRateLimitError):
        federal_reserve.get_sofr_curve("2026-08-28")


def test_sofr_5xx_raises_rate_limit():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(status=502)), \
            pytest.raises(VendorRateLimitError):
        federal_reserve.get_sofr_curve("2026-08-28")


def test_treasury_renders_maturity_rows():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(text=_TREASURY_CSV)):
        out = federal_reserve.get_treasury_curve("2026-08-28")
    assert "US Treasury par yield curve" in out
    assert "| 1 Mo | 3.84 |" in out
    assert "| 10 Yr | 4.73 |" in out
    assert "As of: 08/28/2026" in out
    # 14 maturities from the fixture header (Date + 10)
    rows = [ln for ln in out.splitlines() if ln.startswith("| ") and "| ---" not in ln]
    assert len(rows) == 11  # header + 10 maturity rows


def test_treasury_picks_row_at_or_before_current_date():
    # current_date 08/27 -> must NOT pull the future-dated 08/28 row.
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(text=_TREASURY_CSV)):
        out = federal_reserve.get_treasury_curve("2026-08-27")
    assert "As of: 08/27/2026" in out
    assert "| 10 Yr | 4.67 |" in out


def test_treasury_empty_raises():
    with __import__("unittest").mock.patch("requests.get", return_value=_resp(text="")), \
            pytest.raises(NoMarketDataError):
        federal_reserve.get_treasury_curve("2026-08-28")


def test_treasury_404_raises_http_error():
    resp = _resp(status=404)
    resp.raise_for_status.side_effect = __import__("unittest").mock.Mock(
        side_effect=__import__("requests").exceptions.HTTPError("404")
    )
    with __import__("unittest").mock.patch("requests.get", return_value=resp), \
            pytest.raises(__import__("requests").exceptions.HTTPError):
        federal_reserve.get_treasury_curve("2026-08-28")


# ---------------------------------------------------------------------------
# Router integration (category registration + chain)
# ---------------------------------------------------------------------------


class TestFederalReserveRouting:
    def setup_method(self):
        config_module.reset_config()
        set_config({"vendor_cache_enabled": False})  # hermetic: no disk cache writes

    def teardown_method(self):
        config_module.reset_config()

    def test_category_routes_to_federal_reserve(self):
        assert interface.get_category_for_method("get_sofr_curve") == "risk_free_curve"
        assert interface.get_category_for_method("get_treasury_curve") == "risk_free_curve"
        assert "risk_free_curve" in interface.OPTIONAL_CATEGORIES
        set_config({"data_vendors": {"risk_free_curve": "federal_reserve"}})
        with __import__("unittest").mock.patch("requests.get", return_value=_resp(_SOFR_JSON)):
            out = interface.route_to_vendor("get_sofr_curve", "2026-08-28")
        assert "SOFR curve" in out

    def test_no_data_degrades_to_sentinel(self):
        set_config({"data_vendors": {"risk_free_curve": "federal_reserve"}})
        with __import__("unittest").mock.patch("requests.get", return_value=_resp({"refRates": []})):
            out = interface.route_to_vendor("get_sofr_curve", "2026-08-28")
        assert out.startswith("NO_DATA_AVAILABLE")


if __name__ == "__main__":
    import unittest

    unittest.main()
