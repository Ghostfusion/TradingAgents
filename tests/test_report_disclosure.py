"""Tests for report disclosure + invalidation conditions (DSA phase D; §6-7).

- attribution sums 100 when all four given; missing-note otherwise
- consensus supporting/opposing readout
- watch_conditions/next_check_time render
- every decision carries >= 1 invalidation; stop-loss/take-profit/data-quality
  generate the right ones; manual:thesis_reassessment fallback
- disclosure footers list sources used vs empty + models
"""

import pytest

from tradingagents.strategies import report_disclosure as rd

pytestmark = pytest.mark.timeout(30)


class TestAttribution:
    def test_sums_100_when_all_given(self):
        out = rd.signal_attribution(technical=40.0, news=30.0, fundamental=20.0, market=10.0)
        assert out["sum"] == pytest.approx(100.0, abs=0.2)
        assert out["missing"] == []
        assert abs(sum(out["weights"].values()) - 100) < 0.2

    def test_partial_normalizes_with_missing_note(self):
        out = rd.signal_attribution(technical=50.0, news=50.0)
        assert out["sum"] == pytest.approx(100.0, abs=0.2)
        assert set(out["missing"]) == {"fundamentals", "market_conditions"}

    def test_none_all(self):
        out = rd.signal_attribution()
        assert out["weights"] == {} and out["sum"] == 0

    def test_zero_total_none(self):
        # all-zero inputs -> total 0: no fabricated weights; missing lists the
        # truly unprovided drivers
        out = rd.signal_attribution(technical=0.0, news=0.0)
        assert out["sum"] == 0
        assert set(out["missing"]) == {"fundamentals", "market_conditions"}

    def test_strongest_signals(self):
        out = rd.signal_attribution(technical=1.0, strongest_bullish="bias_20",
                                    strongest_bearish="flow divergence")
        assert out["strongest_bullish"] == "bias_20"
        assert out["strongest_bearish"] == "flow divergence"


class TestConsensus:
    def test_readout(self):
        out = rd.consensus_readout(["ma_bull_trend"], ["shrink_pullback"])
        assert out["supporting"] == ["ma_bull_trend"]
        assert out["opposing"] == ["shrink_pullback"] and out["disagreement"] is True

    def test_no_opposition(self):
        out = rd.consensus_readout(["vol"], [])
        assert out["opposing"] == [] and out["disagreement"] is False


class TestInvalidation:
    def test_stop_loss_invalidation(self):
        conds = rd.invalidation_conditions(stop_loss=95.0)
        assert any("price_stop_loss" in c and "95" in c for c in conds)

    def test_take_profit_review(self):
        conds = rd.invalidation_conditions(take_profit=120.0)
        assert any("price_take_profit_status" in c for c in conds)

    def test_data_quality_invalidation(self):
        conds = rd.invalidation_conditions(data_quality="stale")
        assert any("data_quality: stale" in c for c in conds)
        assert rd.invalidation_conditions(data_quality="fresh") == ["manual:thesis_reassessment"]

    def test_always_at_least_one(self):
        assert rd.invalidation_conditions() == ["manual:thesis_reassessment"]
        conds = rd.invalidation_conditions(extra=["x"])
        assert len(conds) >= 1 and "x" in conds[-1]

    def test_multiple(self):
        conds = rd.invalidation_conditions(stop_loss=95, take_profit=120, data_quality="partial")
        assert len(conds) == 3


class TestDisclosure:
    def test_footers(self):
        out = rd.disclosure_footers(["eodhd", "tiingo"], ["moomoo"], models_used=["gpt-4.1"])
        assert out["sources_used"] == ["eodhd", "tiingo"]
        assert out["sources_empty"] == ["moomoo"]
        assert out["models_used"] == ["gpt-4.1"]

    def test_no_models(self):
        out = rd.disclosure_footers(["eodhd"], [])
        assert out["models_used"] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
