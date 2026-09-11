"""Contract tests for the market-routing configuration surface (audit 2026-09-10).

- ``enable_market_routing`` / ``market_source_priority`` are read by
  ``route_to_vendor`` but were absent from ``DEFAULT_CONFIG`` and
  ``_ENV_OVERRIDES``, so the documented
  ``TRADINGAGENTS_MARKET_SOURCE_PRIORITY`` knob did nothing.
- ``resolve_market_priority`` returned configured names unfiltered, so a
  priority list naming a vendor not registered for the method raised an
  uncaught ``KeyError`` at ``VENDOR_METHODS[method][vendor]``.
- ``validate_config`` had no production caller.
- ``interface.VENDOR_LIST`` had drifted from ``VENDOR_METHODS``.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.dataflows.interface as I
import tradingagents.default_config as default_config_module
from tradingagents.dataflows import market_router as mr, vendor_breaker as vb

pytestmark = pytest.mark.timeout(30)

_FAKE_CHAIN = {
    "eodhd": lambda *a, **k: "eodhd",
    "yfinance": lambda *a, **k: "yfinance",
}


class _NoCache:
    """Vendor cache that never serves a hit (routing is what we assert)."""

    def get(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None


def _route_get_stock_data():
    vb.reset()
    with patch.object(I, "VENDOR_METHODS", {"get_stock_data": dict(_FAKE_CHAIN)}), \
         patch.object(I, "vendor_cache", _NoCache()):
        return I.route_to_vendor(
            "get_stock_data", "AAPL", "2026-01-01", "2026-02-01"
        )


def _restore_default_config(monkeypatch):
    for key in (
        "TRADINGAGENTS_ENABLE_MARKET_ROUTING",
        "TRADINGAGENTS_MARKET_SOURCE_PRIORITY",
        "TRADINGAGENTS_CATALYST_WINDOW_DAYS",
    ):
        monkeypatch.delenv(key, raising=False)
    importlib.reload(default_config_module)
    config_module.reset_config()


# ---------------------------------------------------------------------------
# (a) keys exist, are env-overridable, and the env var enables the branch
# ---------------------------------------------------------------------------


def test_market_routing_keys_present_and_off_by_default():
    assert default_config_module.DEFAULT_CONFIG["enable_market_routing"] is False
    assert default_config_module.DEFAULT_CONFIG["market_source_priority"] == {}


def test_market_routing_env_overrides(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_MARKET_ROUTING", "true")
    monkeypatch.setenv(
        "TRADINGAGENTS_MARKET_SOURCE_PRIORITY", '{"US": "eodhd,yfinance"}'
    )
    try:
        dc = importlib.reload(default_config_module)
        assert dc.DEFAULT_CONFIG["enable_market_routing"] is True
        assert dc.DEFAULT_CONFIG["market_source_priority"] == {
            "US": "eodhd,yfinance"
        }
    finally:
        _restore_default_config(monkeypatch)


def test_documented_env_enables_market_routing_branch(monkeypatch):
    """The documented env knob must actually reorder the chain for the market."""
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_MARKET_ROUTING", "true")
    monkeypatch.setenv("TRADINGAGENTS_MARKET_SOURCE_PRIORITY", '{"US": "yfinance"}')
    try:
        dc = importlib.reload(default_config_module)
        assert dc.DEFAULT_CONFIG["enable_market_routing"] is True
        config_module.reset_config()
        # The default core_stock_apis chain tries eodhd first; only the
        # env-enabled market-routing branch reorders it to yfinance for US.
        assert _route_get_stock_data() == "yfinance"
    finally:
        _restore_default_config(monkeypatch)


# ---------------------------------------------------------------------------
# (b) unregistered priority vendors are skipped, never a KeyError
# ---------------------------------------------------------------------------


def test_unregistered_priority_vendor_falls_through_to_configured_chain():
    config_module.set_config(
        {
            "enable_market_routing": True,
            "market_source_priority": {"US": "not_a_real_vendor"},
        }
    )
    assert _route_get_stock_data() == "eodhd"


def test_resolve_market_priority_skips_unregistered_vendors():
    chain = ["eodhd", "yfinance"]
    # Only names registered for the method survive, in priority order.
    assert mr.resolve_market_priority("US", {"US": "bogus,eodhd"}, chain, chain) == [
        "eodhd"
    ]
    # No registered name -> the configured chain is used unchanged.
    assert mr.resolve_market_priority("US", {"US": "bogus"}, chain, chain) == chain


# ---------------------------------------------------------------------------
# (c) validate_config runs on the real config load
# ---------------------------------------------------------------------------


def test_out_of_range_env_fails_at_config_load(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_CATALYST_WINDOW_DAYS", "-3")
    try:
        with pytest.raises(ValueError, match="catalyst_window_days"):
            importlib.reload(default_config_module)
    finally:
        _restore_default_config(monkeypatch)


# ---------------------------------------------------------------------------
# (d) the vendor registry is derived from VENDOR_METHODS
# ---------------------------------------------------------------------------


def test_vendor_list_derived_from_vendor_methods():
    expected = sorted({v for impls in I.VENDOR_METHODS.values() for v in impls})
    assert expected == I.VENDOR_LIST
    # The seven vendors the old hand-maintained literal omitted.
    for vendor in (
        "seekingalpha",
        "fmp",
        "congress",
        "patentsview",
        "finra",
        "fx",
        "treasury_fiscal",
    ):
        assert vendor in I.VENDOR_LIST
