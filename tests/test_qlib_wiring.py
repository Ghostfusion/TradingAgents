"""Wiring tests for the Qlib Phase-1 integration.

Covers the tool/config/report seams from design_qlib_integration.md §4:
- get_factor_profile honors enable_factor_profile + returns computed rows
- get_topk_drop_plan / get_enhanced_index_tilt render advisory plans
- portfolio.allocation_block picks the Qlib strategy behind the flags, and
  the default (both off) path is unchanged value-ratio
- scripts/backtest_strategy.backtest applies the tradability gates
- strategy_quality_report.build_report emits the with/without-cost table
"""

import json
import os
import tempfile

import pytest

from tradingagents.strategies.portfolio import allocation_block

pytestmark = pytest.mark.timeout(30)


def _seed_ohlcv(cache, closes=None):
    """Seed the run-level OHLCV cache so tools never hit the vendor chain."""
    closes = closes or [100.0 + 2.0 * i for i in range(80)]
    cache[("TEST", 320)] = {
        "dates": [f"2026-01-{i % 28 + 1:02d}" for i in range(80)],
        "closes": closes,
        "opens": closes,
        "highs": [c + 3 for c in closes],
        "lows": [c - 3 for c in closes],
        "volumes": [1_000_000] * 80,
    }


class TestFactorProfileTool:
    def test_gated_off_returns_unavailable(self):
        from tradingagents.agents.utils.analysis_tools import get_factor_profile
        from tradingagents.dataflows.config import set_config

        set_config({"enable_factor_profile": False})
        try:
            out = get_factor_profile.invoke({"ticker": "TEST"})
            assert "enable_factor_profile is off" in out
        finally:
            from tradingagents.dataflows.config import reset_config

            reset_config()

    def test_gated_on_returns_computed_rows(self):
        import tradingagents.agents.utils.analysis_tools as at
        from tradingagents.dataflows.config import set_config

        _seed_ohlcv(at._RUN_OHLCV_CACHE)
        set_config({"enable_factor_profile": True})
        try:
            out = at.get_factor_profile.invoke({"ticker": "TEST"})
            assert "Factor profile TEST" in out
            assert "20d momentum" in out
            assert "computed, advisory" in out
        finally:
            from tradingagents.dataflows.config import reset_config

            reset_config()


class TestPlanTools:
    def test_topk_drop_plan(self):
        from tradingagents.agents.utils.analysis_tools import get_topk_drop_plan

        out = get_topk_drop_plan.invoke(
            {"scores": {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0},
             "topk": 3, "n_drop": 1, "held": ["C", "D"]}
        )
        assert "Topk-Drop rebalance plan" in out
        assert "hold:" in out and "turnover:" in out

    def test_enhanced_index_tilt(self):
        from tradingagents.agents.utils.analysis_tools import get_enhanced_index_tilt

        out = get_enhanced_index_tilt.invoke(
            {"scores": {"A": 5.0, "B": 4.0, "C": 3.0},
             "benchmark_weights": {"A": 0.4, "B": 0.3, "C": 0.3}}
        )
        assert "Enhanced-index tilt" in out
        assert "turnover vs w0" in out

    def test_enhanced_index_infeasible_holds(self):
        from tradingagents.agents.utils.analysis_tools import get_enhanced_index_tilt

        out = get_enhanced_index_tilt.invoke(
            {"scores": {"A": 5.0, "B": 4.0},
             "benchmark_weights": {"A": 0.5, "B": 0.5},
             "turnover_cap": 0.0, "b_dev": 0.0}
        )
        assert "infeasible, holdings unchanged" in out


class TestAllocationBlockStrategies:
    def test_default_unchanged_value_ratio(self):
        out = allocation_block(
            {"A": 1.0, "B": 0.5, "C": 0.25},
            cfg={"max_name_weight": 0.25, "sector_cap_limit": 0.35, "max_book_names": 2},
        )
        assert "## Allocation plan" in out
        assert "strategy:" not in out  # default path has no strategy note

    def test_topk_drop_flag(self):
        out = allocation_block(
            {"A": 1.0, "B": 0.9, "C": 0.8, "D": 0.7},
            cfg={"enable_topk_drop": True, "max_book_names": 2},
        )
        assert "topk-drop" in out

    def test_enhanced_index_flag(self):
        out = allocation_block(
            {"A": 1.0, "B": 0.9, "C": 0.8},
            cfg={"enable_enhanced_index": True, "max_book_names": 3},
        )
        assert "enhanced-index" in out


class TestBacktestTradability:
    def _bar(self, i, close, low, high, volume=1_000_000):
        class B:
            pass

        b = B()
        b.open = b.close = close
        b.low = low
        b.high = high
        b.volume = volume
        b.i = i
        return b

    def _bars(self, closes):
        bars = []
        prev = closes[0]
        for i, c in enumerate(closes):
            bars.append(self._bar(i, c, min(c, prev) * 0.99, max(c, prev) * 1.01))
            prev = c
        return bars

    def test_limit_up_blocks_buy_and_rides_through(self):
        from scripts import backtest_strategy as bs

        # Day 0 at 100; day 1 limit-up +12% (blocked for buys); day 2 normal.
        closes = [100.0, 112.0, 113.0]
        bars = self._bars(closes)
        res = bs.backtest(bars, entry=100.0, stop=90.0, targets=[150.0],
                          qty=100, side="long", fee_bps=5.0, slippage_ticks=0.0,
                          limit_threshold=0.10)
        # entry must not happen on the +12% bar (entry_bar > 0)
        assert res["fills"][0]["bar"] != 1

    def test_suspended_day_skipped(self):
        from scripts import backtest_strategy as bs

        class B:
            pass

        b1 = B()
        b1.open = b1.close = b1.high = b1.low = 100.0
        b1.volume = 1_000_000
        b2 = B()
        b2.open = b2.close = b2.high = b2.low = float("nan")
        b2.volume = 0
        b3 = B()
        b3.open = b3.close = b3.high = b3.low = 101.0
        b3.volume = 1_000_000
        res = bs.backtest([b1, b2, b3], entry=100.0, stop=95.0, targets=[120.0],
                          qty=50, side="long", fee_bps=5.0, slippage_ticks=0.0)
        assert res["fills"][0]["bar"] != 1  # not the NaN bar

    def test_participation_caps_qty(self):
        from scripts import backtest_strategy as bs

        closes = [100.0, 101.0]
        bars = self._bars(closes)
        bars[0].volume = 10_000
        res = bs.backtest(bars, entry=100.0, stop=95.0, targets=[120.0],
                          qty=5000, side="long", fee_bps=5.0, slippage_ticks=0.0,
                          participation=0.2)
        assert res["fills"][0]["qty"] <= 2000
        assert res["fill_model"]["participation"] == 0.2

    def test_quality_report_with_without_cost(self):
        from scripts import strategy_quality_report as sqr

        with tempfile.TemporaryDirectory() as d:
            rows = [{"realized_return": 0.01 * (1 if i % 2 else -0.005)} for i in range(12)]
            with open(os.path.join(d, "pre_market_ledger.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            out = sqr.build_report(d, cost_bps=10)
            wwc = out["metrics"].get("with_without_cost") or {}
            assert "without_cost" in wwc and "with_cost" in wwc
            assert wwc["with_cost"]["cagr"] <= wwc["without_cost"]["cagr"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
