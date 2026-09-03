"""Phase 7: costs + capacity + corporate actions + survivorship (W2-6/7/8/9/10)."""

import pytest

from tradingagents.dataflows.pit_registry import universe_membership
from tradingagents.strategies.backtest_models import (
    borrow_cost,
    capacity_pct,
    quote_adjust,
    square_root_impact,
    turnover,
)

pytestmark = pytest.mark.timeout(30)


class TestImpact:
    def test_square_root_impact(self):
        imp = square_root_impact(1_000_000, adv_usd=100_000_000, vol_pct=20.0)
        assert imp is not None and imp < 0.01 and imp > 0.0

    def test_impact_none_without_adv(self):
        assert square_root_impact(1_000_000, None) is None

    def test_impact_spread_adds(self):
        a = square_root_impact(1_000_000, 100_000_000, vol_pct=20.0)
        b = square_root_impact(1_000_000, 100_000_000, vol_pct=20.0, spread_bps=50)
        assert b is not None and a is not None and b > a


class TestTurnover:
    def test_turnover_one_way(self):
        assert turnover([100.0, 0.0], [100.0, 100.0]) == pytest.approx(0.5, abs=0.01)
        assert turnover([100.0], [100.0]) == 0.0

    def test_turnover_none(self):
        assert turnover([], []) is None
        assert turnover([1.0], []) is None


class TestCapacity:
    def test_capacity_pct(self):
        assert capacity_pct(1_000_000, 100_000_000) == pytest.approx(0.01, abs=0.001)

    def test_capacity_none(self):
        assert capacity_pct(1_000_000, None) is None


class TestBorrow:
    def test_borrow_cost(self):
        # 1M short, 5% annual, 30 days
        assert borrow_cost(1_000_000, 5.0, 30) == pytest.approx(1_000_000 * 0.05 * 30 / 365, abs=1.0)

    def test_borrow_none(self):
        assert borrow_cost(0, 5.0, 30) is None
        assert borrow_cost(100, 5.0, 0) is None


class TestCorporateAction:
    def test_split_adjust(self):
        assert quote_adjust(200.0, factor=0.5) == 100.0  # 2-for-1
        assert quote_adjust(100.0, factor=2.0) == 200.0

    def test_divisor_and_special_div(self):
        assert quote_adjust(100.0, factor=None, divisor=2.0) == 50.0
        assert quote_adjust(100.0, factor=None, special_dividend=5.0) == 95.0

    def test_no_change(self):
        assert quote_adjust(100.0) == 100.0


class TestSurvivorship:
    def test_universe_membership(self):
        reg = {"AAPL": {"first_active": "2010-01-01", "last_active": ""},
               "DEAD": {"first_active": "2010-01-01", "last_active": "2020-01-01"},
               "NEW": {"first_active": "2025-01-01", "last_active": ""}}
        out = universe_membership(["AAPL", "DEAD", "NEW", "UNKNOWN"], "2023-06-01", reg)
        assert out["AAPL"] == "listed"
        assert out["DEAD"] == "delisted"
        assert out["NEW"] == "not_yet_listed"
        assert out["UNKNOWN"] == "unknown"

    def test_empty_registry_unknown(self):
        out = universe_membership(["X"], "2023-01-01", {})
        assert out["X"] == "unknown"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
