"""Phase 6: regime-conditioned performance + stress grid + macro regime
(W1-10, W2-11, W4-6)."""

import pytest

from tradingagents.strategies.regime_performance import (
    macro_regime,
    regime_conditioned_performance,
    stress_grid,
)

pytestmark = pytest.mark.timeout(30)


class TestRegimePerformance:
    def test_tabulate_by_regime(self):
        rows = [
            {"regime": "bull", "outcome": {"hit": True, "return_pct": 2.0}},
            {"regime": "bull", "outcome": {"hit": False, "return_pct": -1.0}},
            {"regime": "bear", "outcome": {"hit": True, "return_pct": 0.5}},
        ]
        out = regime_conditioned_performance(rows)
        assert out["bull"]["n"] == 2 and out["bull"]["hit_rate"] == 0.5
        assert out["bear"]["avg_return_pct"] == pytest.approx(0.5, abs=0.01)
        assert out["bull"]["avg_return_pct"] == pytest.approx(0.5, abs=0.01)  # (2 + -1)/2

    def test_no_scored_rows_none(self):
        out = regime_conditioned_performance([{"regime": "bull", "outcome": None}])
        assert out["bull"]["n"] == 0 and out["bull"]["hit_rate"] is None

    def test_unknown_regime(self):
        out = regime_conditioned_performance([{"outcome": None}])
        assert "unknown" in out


class TestStressGrid:
    def test_cells_computed(self):
        g = stress_grid(100.0)
        assert g["base"] == 100.0
        assert len(g["rows"]) == 20  # 5 revenue x 4 discount shifts
        assert g["rows"][0]["value"] == pytest.approx(90.25, abs=0.5)  # 100 -10*1 +(-50)*(-0.5/100)

    def test_base_none(self):
        assert stress_grid(None)["rows"] == []

    def test_custom_sensitivity(self):
        g = stress_grid(100.0, revenue_shifts_pct=[-10, 0, 10],
                        discount_shifts_bps=[0], sensitivity={"revenue_pct": 2.0})
        assert len(g["rows"]) == 3
        vals = [r["value"] for r in g["rows"]]
        assert vals[0] == pytest.approx(80.0, abs=0.1)  # -10*2


class TestMacroRegime:
    def test_stagflation(self):
        r = macro_regime(rate_change_bps=25, credit_spread_bps=400,
                         dollar_index_chg_pct=1.0, vol_percentile=0.8)
        assert r["regime"] == "stagflation"

    def test_liquidity_contraction(self):
        r = macro_regime(rate_change_bps=50, vol_percentile=0.85)
        assert r["regime"] == "liquidity_contraction"

    def test_risk_on(self):
        r = macro_regime(rate_change_bps=-25, credit_spread_bps=100, vol_percentile=0.3)
        assert r["regime"] == "risk_on"

    def test_no_inputs_none(self):
        assert macro_regime()["regime"] is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
