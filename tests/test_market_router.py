"""Tests for the market router + vendor breaker (DSA phase B; design §6-4).

- market classification (US/CA/EU/JP/KR/TW suffixes; unknown -> US fail-open)
- per-market priority resolution honors config order; unconfigured ->
  default (bit-identical)
- gap-fill merges missing supplement fields from secondary sources
- breaker: 3 fails -> OPEN, cooldown blocks, half-open probe re-closes,
  negative capability cache with TTL
"""

import pytest

from tradingagents.dataflows import market_router as mr, vendor_breaker as vb

pytestmark = pytest.mark.timeout(30)


class TestMarketRouter:
    def test_classification(self):
        assert mr.market_for_symbol("AAPL") == "US"
        assert mr.market_for_symbol("AAPL.TO") == "CA"
        assert mr.market_for_symbol("SHOP.V") == "CA"
        assert mr.market_for_symbol("BP.L") == "EU"
        assert mr.market_for_symbol("AIR.PA") == "EU"
        assert mr.market_for_symbol("7203.T") == "JP"
        assert mr.market_for_symbol("005930.KS") == "KR"
        assert mr.market_for_symbol("2330.TW") == "TW"
        assert mr.market_for_symbol("^GSPC") == "US"
        assert mr.market_for_symbol("") == "US"
        assert mr.market_for_symbol("600519") == "US"  # fail-open default

    def test_priority_resolution(self):
        chain = ["eodhd", "tiingo", "yfinance", "moomoo"]
        cfg = {"US": "eodhd,yfinance"}
        assert mr.resolve_market_priority("US", cfg, chain) == ["eodhd", "yfinance"]
        # unconfigured market -> default (bit-identical)
        assert mr.resolve_market_priority("JP", None, chain) == chain
        assert mr.resolve_market_priority("JP", cfg, chain) == chain
        # case-insensitive market key
        assert mr.resolve_market_priority("us", cfg, chain) == ["eodhd", "yfinance"]
        # empty config value -> default
        assert mr.resolve_market_priority("US", {"US": ""}, chain) == chain

    def test_gap_fill(self):
        primary = {"close": 100.0, "volume": 1000}
        secondary = [{"_vendor": "v2", "pe_ratio": 12.5}]
        out = mr.gap_fill(primary, secondary)
        assert out["close"] == 100.0 and out["pe_ratio"] == 12.5
        assert out["_filled_from"]["pe_ratio"] == "v2"
        # does not override existing primary values
        assert mr.gap_fill({"close": 100.0, "pe_ratio": 10.0}, secondary)["pe_ratio"] == 10.0
        # primary None -> first non-empty secondary whole
        assert mr.gap_fill(None, [dict(secondary[0])])["pe_ratio"] == 12.5
        assert mr.gap_fill(None, []) == {}


class TestVendorBreaker:
    def setup_method(self):
        vb.reset()

    def test_trips_at_three_and_blocks(self):
        # 1 fail: allowed; 2: allowed; 3: TRIPS -> blocked within cooldown
        assert vb.allow_call("US", "eodhd", now=1000) is True
        assert vb.record_failure("US", "eodhd", now=1000) is False
        assert vb.record_failure("US", "eodhd", now=1001) is False
        assert vb.record_failure("US", "eodhd", now=1002) is True
        assert vb.allow_call("US", "eodhd", now=1003) is False  # cooldown
        assert vb.probe_due("US", "eodhd", now=1003) is False
        # after cooldown (300s): probe due -> allowed
        assert vb.allow_call("US", "eodhd", now=1303) is True
        assert vb.probe_due("US", "eodhd", now=1303) is True

    def test_success_resets(self):
        vb.record_failure("US", "yfinance", now=0)
        vb.record_failure("US", "yfinance", now=1)
        vb.record_failure("US", "yfinance", now=2)
        vb.record_success("US", "yfinance")
        assert vb.allow_call("US", "yfinance", now=4) is True

    def test_capability_negative_cache(self):
        assert vb.capability_available("US", "moomoo", "volume_ratio", now=0) is True
        vb.mark_capability_absent("US", "moomoo", "volume_ratio", ttl=900, now=0)
        assert vb.capability_available("US", "moomoo", "volume_ratio", now=100) is False
        assert vb.capability_available("US", "moomoo", "volume_ratio", now=901) is True
        # per-market isolation
        assert vb.capability_available("JP", "moomoo", "volume_ratio", now=100) is True

    def test_snapshot(self):
        vb.record_failure("US", "t", now=0)
        shot = vb.state_snapshot()
        assert "US:t" in shot and shot["US:t"]["fails"] == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
