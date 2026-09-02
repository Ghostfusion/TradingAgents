"""Phase B wiring tests: VendorResult honesty fields + nightly resume hook.

- VendorResult carries fallback_from/stale/data_quality/missing_fields.
- nightly main accepts --force-run (escape hatch wired to
  effective_trading_date).
"""

import pytest

from tradingagents.dataflows import schema as dflow_schema

pytestmark = pytest.mark.timeout(30)


class TestVendorResultHonesty:
    def test_defaults(self):
        v = dflow_schema.VendorResult(results="x", provider="eodhd")
        assert v.fallback_from is None and v.is_stale is False
        assert v.stale_seconds is None and v.data_quality is None
        assert v.missing_fields == []

    def test_populated(self):
        v = dflow_schema.VendorResult(
            results="x", provider="eodhd", fallback_from="tiingo",
            is_stale=True, stale_seconds=45.0, data_quality="stale",
            missing_fields=["volume_ratio"],
        )
        assert v.ok and v.data_quality == "stale" and v.fallback_from == "tiingo"
        assert v.to_dict()["missing_fields"] == ["volume_ratio"]

    def test_never_fabricates(self):
        v = dflow_schema.VendorResult(results=None, provider="eodhd", error_kind="NoMarketDataError")
        assert v.ok is False
        assert v.data_quality is None  # no fabricated quality on failure


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

