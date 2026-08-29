"""CBOE delayed options-surface vendor: OCC parsing, DTE, greeks/no-greeks
honesty, empty-chain degradation, and router integration.

All network access is mocked, so these run offline.
"""

import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import cboe, interface
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError

pytestmark = pytest.mark.timeout(180)


def _option(symbol, expiry, cp, strike_1000):
    return f"{symbol}{expiry}{cp}{strike_1000:08d}"


# A realistic CBOE payload for AAPL (strike*1000 is 8 digits; greeks present
# on some rows, absent/0 on others, exactly as the real feed delivers).
_OPTIONS = [
    {"option": _option("AAPL", "260828", "C", 150_000), "bid": 5.1, "ask": 5.2,
     "iv": 0.32, "open_interest": 100, "volume": 10,
     "delta": 0.61, "gamma": 0.021, "theta": -0.15, "vega": 0.20, "rho": 0.05},
    {"option": _option("AAPL", "260828", "P", 150_000), "bid": 0.05, "ask": 0.06,
     "iv": 0.31, "open_interest": 50, "volume": 2,
     "delta": -0.39, "gamma": 0.021, "theta": -0.14, "vega": 0.20, "rho": -0.05},
    # No greeks on this row (as the free feed often returns 0/absent).
    {"option": _option("AAPL", "260904", "C", 155_000), "bid": 0, "ask": 0.01,
     "iv": 0, "open_interest": 0, "volume": 0},
    # A deep-ITM contract with deltas pinned to 1/0.
    {"option": _option("AAPL", "260904", "C", 110_000), "bid": 208.4, "ask": 211.65,
     "iv": 0, "open_interest": 3, "volume": 0,
     "delta": 1.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0},
]

_PAYLOAD = {"timestamp": "2026-08-29 05:20:00", "data": {"options": _OPTIONS}}


def _mock_fetch(payload):
    return lambda symbol: (payload.get("data") or {}, (payload.get("timestamp") or "").split(" ")[0])


def test_occ_parse_handles_8_digit_strike():
    assert cboe._parse_occ("AAPL260828C00150000") == {
        "expiry": "2026-08-28", "type": "C", "strike": 150.0
    }
    assert cboe._parse_occ("SPY260828C00500000") == {
        "expiry": "2026-08-28", "type": "C", "strike": 500.0
    }


def test_occ_parse_rejects_malformed():
    assert cboe._parse_occ("SHORT") is None
    assert cboe._parse_occ("AAPL260828X00150000") is None  # bad cp char
    assert cboe._parse_occ("") is None


def test_surface_renders_rows_and_dte():
    with __import__("unittest").mock.patch.object(cboe, "_fetch", side_effect=_mock_fetch(_PAYLOAD)):
        out = cboe.get_options_surface("AAPL")
    assert "CBOE Options Surface: AAPL" in out
    # 2026-08-28 expiry vs 2026-08-29 as-of -> DTE -1; 2026-09-04 -> DTE 6.
    assert "| 150.00 | -1 | C |" in out
    assert "| 110.00 | 6 | C |" in out
    assert "| 150.00 | -1 | P |" in out
    # greeks render from the payload where present
    assert "0.6100" in out
    assert "0.0210" in out


def test_missing_greeks_render_n_a_not_fabricated():
    with __import__("unittest").mock.patch.object(cboe, "_fetch", side_effect=_mock_fetch(_PAYLOAD)):
        out = cboe.get_options_surface("AAPL")
    # The 155_000 call has no greeks -> 'n/a', never an invented number.
    line = next(ln for ln in out.splitlines() if "155.00" in ln)
    assert "n/a" in line
    # 'n/a' for its delta slot (the row has no delta field)
    assert "| 0.0000 |" not in line.split("|")[5]


def test_empty_chain_raises_no_data():
    empty = {"timestamp": "2026-08-29 05:20:00", "data": {"options": []}}
    with __import__("unittest").mock.patch.object(cboe, "_fetch", side_effect=_mock_fetch(empty)), \
            pytest.raises(NoMarketDataError):
        cboe.get_options_surface("ZZZZ")


def test_unparseable_rows_only_raise_no_data():
    payload = {"timestamp": "2026-08-29 05:20:00", "data": {"options": [{"option": "GARBAGE"}]}}
    with __import__("unittest").mock.patch.object(cboe, "_fetch", side_effect=_mock_fetch(payload)), \
            pytest.raises(NoMarketDataError):
        cboe.get_options_surface("WEIRD")


def test_blank_symbol_raises_no_data():
    with pytest.raises(NoMarketDataError):
        cboe.get_options_surface("   ")


def test_http_429_raises_rate_limit():
    resp = __import__("unittest").mock.Mock()
    resp.status_code = 429
    with __import__("unittest").mock.patch("requests.get", return_value=resp), \
            pytest.raises(VendorRateLimitError):
        cboe._fetch("AAPL")


def test_http_404_raises_no_data():
    resp = __import__("unittest").mock.Mock()
    resp.status_code = 404
    with __import__("unittest").mock.patch("requests.get", return_value=resp), \
            pytest.raises(NoMarketDataError):
        cboe._fetch("NOPE")


def test_http_500_raises_rate_limit():
    resp = __import__("unittest").mock.Mock()
    resp.status_code = 503
    with __import__("unittest").mock.patch("requests.get", return_value=resp), \
            pytest.raises(VendorRateLimitError):
        cboe._fetch("AAPL")


# ---------------------------------------------------------------------------
# Router integration (category registration + chain)
# ---------------------------------------------------------------------------


class TestCboeRouting:
    def setup_method(self):
        config_module.reset_config()
        set_config({"vendor_cache_enabled": False})  # hermetic: no disk cache writes

    def teardown_method(self):
        config_module.reset_config()

    def test_category_routes_to_cboe(self):
        assert interface.get_category_for_method("get_options_surface") == "options_surface"
        assert "options_surface" in interface.OPTIONAL_CATEGORIES
        set_config({"data_vendors": {"options_surface": "cboe"}})
        with __import__("unittest").mock.patch.object(
            cboe, "_fetch", side_effect=_mock_fetch(_PAYLOAD)
        ):
            out = interface.route_to_vendor("get_options_surface", "AAPL")
        assert "CBOE Options Surface: AAPL" in out

    def test_no_data_degrades_to_sentinel(self):
        # Optional category: an all-no-data chain surfaces a sentinel, never a raise.
        set_config({"data_vendors": {"options_surface": "cboe"}})
        empty = {"timestamp": "2026-08-29 05:20:00", "data": {"options": []}}
        with __import__("unittest").mock.patch.object(
            cboe, "_fetch", side_effect=_mock_fetch(empty)
        ):
            out = interface.route_to_vendor("get_options_surface", "ZZZZ")
        assert out.startswith("NO_DATA_AVAILABLE")


if __name__ == "__main__":
    import unittest

    unittest.main()
