"""yfinance P1: typed absence reasons through the read envelope.

The router already distinguishes typed vendor failures; this suite pins that
the *reason* survives the chain end:
- route_to_vendor keeps returning plain strings (public contract unchanged).
- route_to_vendor_typed attaches a machine-readable ``absence`` dict to the
  envelope whenever the chain ended on a typed failure, and stays None on
  success paths (no cross-call / cross-thread leakage).
"""

import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorAbsence,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(30)


def _reset_config():
    config_module.reset_config()


def _no_data(symbol, *a, **k):
    raise NoMarketDataError(symbol, symbol, "stale: latest row is 2025-06-11")


def _returns(value):
    def impl(symbol, *a, **k):
        return value

    return impl


def _raises(exc):
    def impl(symbol, *a, **k):
        raise exc

    return impl


class VendorAbsenceUnitTests(unittest.TestCase):
    def setUp(self):
        _reset_config()

    def tearDown(self):
        _reset_config()

    # -- VendorAbsence.from_error taxonomy -----------------------------------

    def test_no_data_maps_to_non_retryable_reason(self):
        a = VendorAbsence.from_error(NoMarketDataError("X", "X", "no rows"))
        self.assertEqual(a.reason, "no_data")
        self.assertFalse(a.retryable)
        self.assertEqual(a.detail, "no rows")

    def test_rate_limit_maps_to_retryable_reason(self):
        a = VendorAbsence.from_error(VendorRateLimitError())
        self.assertEqual(a.reason, "rate_limited")
        self.assertTrue(a.retryable)

    def test_not_configured_maps_to_non_retryable_reason(self):
        a = VendorAbsence.from_error(VendorNotConfiguredError("missing key"))
        self.assertEqual(a.reason, "not_configured")
        self.assertFalse(a.retryable)

    def test_unknown_maps_to_unknown(self):
        a = VendorAbsence.from_error(None)
        self.assertEqual(a.reason, "unknown")
        self.assertFalse(a.retryable)

    def test_generic_error_maps_to_error(self):
        a = VendorAbsence.from_error(ValueError("boom"))
        self.assertEqual(a.reason, "error")
        self.assertTrue(a.retryable)
        self.assertEqual(a.detail, "boom")

    def test_to_dict_is_json_safe(self):
        import json

        a = VendorAbsence.from_error(NoMarketDataError("X", "X", "nope"), source="yfinance")
        d = json.loads(json.dumps(a.to_dict()))
        self.assertEqual(d["reason"], "no_data")
        self.assertEqual(d["source"], "yfinance")
        self.assertIn("detail", d)


class VendorAbsenceRouterTests(unittest.TestCase):
    def setUp(self):
        _reset_config()

    def tearDown(self):
        _reset_config()

    def _route(self, vendors_for_get_stock_data):
        return mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_stock_data": vendors_for_get_stock_data},
            clear=False,
        )

    # -- route_to_vendor string contract is preserved -------------------------

    def test_string_contract_unchanged_on_no_data(self):
        # #regression-guard: direct string callers (scripts/*) must keep
        # receiving a plain sentinel string, never a tuple/dict.
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _no_data}):
            result = interface.route_to_vendor("get_stock_data", "ZZZZ", "2026-01-01", "2026-01-10")
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("NO_DATA_AVAILABLE"))

    def test_string_contract_unchanged_on_success(self):
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _returns("Date,Open,High,Low,Close,Volume")}):
            result = interface.route_to_vendor("get_stock_data", "AAPL", "2026-01-01", "2026-01-10")
        self.assertIsInstance(result, str)

    # -- typed envelope carries the absence reason ---------------------------

    def test_typed_wrapper_attaches_no_data_absence(self):
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _no_data}):
            vr = interface.route_to_vendor_typed("get_stock_data", "ZZZZ", "2026-01-01", "2026-01-10")
        self.assertEqual(vr.error_kind, "NoMarketDataError")
        self.assertIsNotNone(vr.absence)
        self.assertEqual(vr.absence["reason"], "no_data")
        self.assertIsNotNone(vr.absence.get("source"))
        self.assertFalse(vr.absence["retryable"])
        self.assertIn("stale", vr.absence.get("detail", ""))

    def test_typed_wrapper_rate_limited_core_raises_no_envelope(self):
        # A single core vendor throttled is a REAL failure per the router
        # contract (#989): it raises, so the typed wrapper cannot attach an
        # envelope. The absence reason only materializes on sentinel paths.
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _raises(VendorRateLimitError())}), self.assertRaises(
            VendorRateLimitError
        ):
            interface.route_to_vendor_typed("get_stock_data", "AAPL", "2026-01-01", "2026-01-10")

    def test_typed_wrapper_rate_limit_then_no_data_attaches_verdict_reason(self):
        # [rate_limited, no_data] -> NO_DATA sentinel; the reason follows the
        # VERDICT (no_data from the no-data vendor), never the earlier rate-limit.
        set_config({"data_vendors": {"core_stock_apis": "yfinance,alpha_vantage"}})
        with self._route(
            {"yfinance": _raises(VendorRateLimitError()), "alpha_vantage": _no_data}
        ):
            vr = interface.route_to_vendor_typed("get_stock_data", "ZZZZ", "2026-01-01", "2026-01-10")
        self.assertEqual(vr.error_kind, "NoMarketDataError")
        self.assertIsNotNone(vr.absence)
        self.assertEqual(vr.absence["reason"], "no_data")
        self.assertEqual(vr.absence["source"], "alpha_vantage")
        self.assertFalse(vr.absence["retryable"])

    def test_typed_wrapper_optional_category_absence(self):
        # optional enrichment: DATA_UNAVAILABLE sentinel + absence reason.
        set_config({"data_vendors": {"macro_data": "fred"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_macro_indicators": {"fred": _raises(ValueError("FRED 400"))}},
            clear=False,
        ):
            vr = interface.route_to_vendor_typed("get_macro_indicators", "cpi", "2026-01-01")
        self.assertEqual(vr.error_kind, "VendorNotConfiguredError")
        self.assertEqual(vr.absence["reason"], "error")
        self.assertTrue(vr.absence["retryable"])
        self.assertIn("FRED 400", vr.absence.get("detail", ""))

    def test_typed_wrapper_optional_rate_limit_absence(self):
        # optional single vendor throttled -> DATA_UNAVAILABLE + rate_limited reason.
        set_config({"data_vendors": {"macro_data": "fred"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_macro_indicators": {"fred": _raises(VendorRateLimitError())}},
            clear=False,
        ):
            vr = interface.route_to_vendor_typed("get_macro_indicators", "cpi", "2026-01-01")
        # error_kind is the wrapper's coarse sentinel mapping; the precise
        # reason (rate_limited) lives in absence.
        self.assertEqual(vr.error_kind, "VendorNotConfiguredError")
        self.assertEqual(vr.absence["reason"], "rate_limited")
        self.assertTrue(vr.absence["retryable"])
        self.assertEqual(vr.absence["source"], "fred")

    def test_success_path_absence_is_none_and_no_leak(self):
        # A failure followed by a success must NOT leak the prior absence.
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _no_data}):
            vr_bad = interface.route_to_vendor_typed("get_stock_data", "ZZZZ", "a", "b")
        with self._route({"yfinance": _returns("Date,Open,High,Low,Close,Volume")}):
            vr_ok = interface.route_to_vendor_typed("get_stock_data", "AAPL", "a", "b")
        self.assertIsNotNone(vr_bad.absence)
        self.assertIsNone(vr_ok.absence)

    def test_direct_string_call_does_not_leak_into_next_typed_call(self):
        # A plain string caller hits a sentinel (sets the side channel); the
        # NEXT route_to_vendor call resets it, so a later success typed call
        # must not see the stale reason.
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        with self._route({"yfinance": _no_data}):
            interface.route_to_vendor("get_stock_data", "ZZZZ", "a", "b")
        with self._route({"yfinance": _returns("Date,Open,High,Low,Close,Volume")}):
            vr_ok = interface.route_to_vendor_typed("get_stock_data", "AAPL", "a", "b")
        self.assertIsNone(vr_ok.absence)


if __name__ == "__main__":
    unittest.main()
