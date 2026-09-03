"""Phase 3: data quality + disagreement + PIT + falsification (W3-1/2/4/7)."""

import pathlib
import tempfile

import pytest

from tradingagents.strategies.data_quality import (
    aggregate_quality,
    disagreement_flag,
    fundamentals_pit_ok,
)
from tradingagents.strategies.falsification import (
    FalsificationCondition,
    check_breached,
    monitor_conditions,
)

pytestmark = pytest.mark.timeout(30)


class TestAggregateQuality:
    def test_full_set_weights(self):
        out = aggregate_quality({"price": 95, "volume": 90, "fundamentals": 92,
                                 "news": 80, "options": 70, "macro": 98})
        assert out["score"] is not None and 85 <= out["score"] <= 95
        assert out["tier"] in ("full", "normal")

    def test_unmeasured_excluded_not_zero(self):
        # missing options/macro must not drag the score down to 0-weight
        out = aggregate_quality({"price": 100})
        assert out["score"] == 100.0 and out["tier"] == "full"
        assert out["weight_used"] == 22.0

    def test_empty_unknown(self):
        out = aggregate_quality({})
        assert out["score"] is None and out["tier"] == "unknown"

    def test_low_tier_none(self):
        out = aggregate_quality({"price": 40})
        assert out["tier"] == "none"


class TestDisagreement:
    def test_consistent_under_threshold(self):
        out = disagreement_flag([4.20, 4.19, 4.21])
        assert out["consistent"] is True and out["spread_pct"] < 5.0

    def test_conflict_flagged(self):
        out = disagreement_flag([4.20, 4.71, 4.19])  # ~12% spread
        assert out["consistent"] is False and out["spread_pct"] > 5.0

    def test_single_or_none(self):
        assert disagreement_flag([4.20])["consistent"] is True
        assert disagreement_flag([])["spread_pct"] is None
        assert disagreement_flag([None, None])["count"] == 0


class TestPit:
    def test_ok_when_period_le_effective(self):
        assert fundamentals_pit_ok("2026-06-30", "2026-09-02") is True

    def test_fail_when_future(self):
        assert fundamentals_pit_ok("2026-12-31", "2026-09-02") is False

    def test_fail_closed_on_missing(self):
        assert fundamentals_pit_ok(None, "2026-09-02") is False
        assert fundamentals_pit_ok("2026-06-30", None) is False
        assert fundamentals_pit_ok("", "") is False


class TestFalsification:
    def test_check_breached_ops(self):
        assert check_breached(FalsificationCondition("gross_margin", "<", 45.0), 40.0) is True
        assert check_breached(FalsificationCondition("gross_margin", "<", 45.0), 50.0) is False
        assert check_breached(FalsificationCondition("ev", ">", 1e9), 2e9) is True
        assert check_breached(FalsificationCondition("x", ">=", 1.0), 1.0) is True
        assert check_breached(FalsificationCondition("x", "<=", 1.0), 2.0) is False
        assert check_breached(FalsificationCondition("x", "<", 1.0), None) is False

    def test_bad_operator(self):
        with pytest.raises(ValueError):
            FalsificationCondition("x", "==", 1.0)

    def test_monitor_conditions(self):
        conds = [
            FalsificationCondition("gross_margin", "<", 45.0, thesis_impact="terminal_exit"),
            FalsificationCondition("revenue_growth", ">", 0.10),
        ]
        out = monitor_conditions(conds, {"gross_margin": 40.0, "revenue_growth": 0.05})
        assert out[0]["breached"] is True and out[1]["breached"] is False

    def test_record_breaches_writes_ledger(self):
        d = str(pathlib.Path(tempfile.mkdtemp()))
        conds = [FalsificationCondition("gross_margin", "<", 45.0)]
        breaches = monitor_conditions(conds, {"gross_margin": 40.0})
        recorded = __import__("tradingagents.strategies.falsification",
                              fromlist=["record_breaches"]).record_breaches(
            breaches, "MSFT", "2026-09-05", results_dir=d)
        assert len(recorded) == 1
        from tradingagents.strategies.invalidation_ledger import rows

        lr = rows("MSFT", results_dir=d)
        assert len(lr) == 1 and "falsification" in lr[0]["conditions"][0]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
