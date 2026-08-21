"""DCF valuation unit tests (pure/offline)."""

import pytest

from tradingagents.strategies.dcf import (
    compute_dcf,
    discount_factor,
    project_fcf,
    terminal_value_gordon,
    wacc_from_beta,
)


@pytest.mark.unit
def test_wacc_from_beta():
    # rf 0.04, beta 1.0, default erp 0.05 -> 0.09
    assert wacc_from_beta(0.04, 1.0) == pytest.approx(0.09)
    assert wacc_from_beta(0.04, 0.0, erp=0.06) == pytest.approx(0.04)
    assert wacc_from_beta(None, 1.0) is None
    assert wacc_from_beta(0.04, -1.0) is None


@pytest.mark.unit
class TestComputeDcf:
    def test_returns_sensible_price(self):
        fcf = [110.0, 120.0, 130.0, 140.0, 150.0]
        r = compute_dcf(
            fcf, rf=0.04, beta=1.0, erp=0.06, growth=0.025, years=5,
            shares=100.0, cash=50.0, debt=30.0,
        )
        assert r is not None
        assert r["wacc"] == pytest.approx(0.10)
        assert r["price"] > 0
        assert r["usable"] is True

    def test_empty_fcf_returns_none(self):
        assert compute_dcf([], rf=0.04, beta=1.0, shares=100.0) is None

    def test_negative_fcf_returns_none(self):
        r = compute_dcf([-10.0, -5.0], rf=0.04, beta=1.0, shares=100.0)
        assert r is None

    def test_no_shares_returns_none(self):
        assert compute_dcf([100.0], rf=0.04, beta=1.0, shares=0) is None

    def test_growth_gte_wacc_returns_none(self):
        r = compute_dcf([100.0], rf=0.04, beta=1.0, erp=0.0, growth=0.05, shares=100.0)
        assert r is None  # wacc=0.04, g=0.05 >= 0.04

    def test_terminal_dominates_breakdown(self):
        f = [100.0] * 5
        r = compute_dcf(
            f, rf=0.04, beta=1.0, erp=0.06, growth=0.025, years=5,
            shares=100.0, cash=0.0, debt=0.0,
        )
        assert r is not None
        assert r["terminal_share"] > 0.5  # TV dominates (doc note)

    def test_discount_and_growth_helpers(self):
        assert discount_factor(0.10, 0) == 1.0
        assert [round(x, 2) for x in project_fcf(100.0, 0.10, years=3)] == [110.0, 121.0, 133.1]
        assert terminal_value_gordon(100.0, 0.10, 0.03) == pytest.approx(1471.4286, rel=1e-2)
