"""The baseline-relative surface: one clock, one cost schedule, named refusals."""

import random

import pytest

from tradingagents.strategies.benchmark_surface import benchmark_rows, benchmark_surface
from tradingagents.strategies.evaluate import sharpe

pytestmark = pytest.mark.timeout(60)


def _series(mean=0.0008, vol=0.01, n=120, seed=5):
    rng = random.Random(seed)
    return [rng.gauss(mean, vol) for _ in range(n)]


def test_rows_cover_the_strategy_first_then_each_baseline_in_order():
    out = benchmark_rows(_series(), {"buy_and_hold": _series(seed=6), "equal_weight": _series(seed=7)})
    assert [row["name"] for row in out["rows"]] == ["strategy", "buy_and_hold", "equal_weight"]
    assert out["baselines"] == ["buy_and_hold", "equal_weight"]
    assert all(row["n"] == 120 for row in out["rows"])
    assert out["unavailable"] is None


def test_every_row_carries_the_loss_side_four():
    out = benchmark_rows(_series(), {"bm": _series(seed=6)})
    for row in out["rows"]:
        assert row["cvar"] is not None and row["cvar"] <= 0.0
        assert row["prob_ge_threshold"] is not None
        assert row["variance"] > 0.0
        assert row["ann_vol"] is not None and row["calmar"] is not None


def test_the_classic_sharpe_column_is_evaluate_sharpe_not_a_risk_free_binding():
    """The regression for the positional-argument defect in benchmark_table.

    ``sharpe(returns, risk_free, periods_per_year)`` means a positional 252.0
    bound to ``risk_free`` and printed ``(cagr - 252) / vol`` - thousands off on
    every benchmark row. Measured -1497.9 on a series whose true Sharpe is -0.15.
    """
    rets = _series()
    out = benchmark_rows(rets, {"bm": rets})
    expected = round(sharpe(rets, periods_per_year=252.0), 3)
    assert out["rows"][0]["sharpe"] == expected
    assert abs(out["rows"][0]["sharpe"]) < 10.0


def test_cost_is_charged_to_the_strategy_and_the_baseline_default_is_zero():
    rets = _series(n=60)
    free = benchmark_rows(rets, {"bm": rets})
    charged = benchmark_rows(rets, {"bm": rets}, cost_bps=10.0)
    assert free["rows"][0]["total_return"] > charged["rows"][0]["total_return"]
    # the baseline series is untouched at the default baseline_cost_bps
    assert free["rows"][1]["total_return"] == charged["rows"][1]["total_return"]
    assert charged["rows"][0]["cost_bps"] == 10.0
    assert charged["rows"][1]["cost_bps"] == 0.0


def test_the_window_is_the_common_tail_of_every_arm():
    out = benchmark_rows(_series(n=120), {"short": _series(n=90, seed=6)})
    assert out["window"] == 90
    assert all(row["n"] == 90 for row in out["rows"])


def test_surface_deltas_are_strategy_minus_baseline():
    rets = [0.01, 0.02, 0.03, 0.04]
    flat = [0.0, 0.0, 0.0, 0.0]
    out = benchmark_surface(rets, {"flat": flat})
    assert out["delta_vs_baseline"]["flat"]["total_return"] == pytest.approx(0.1036, abs=1e-4)
    assert out["delta_vs_baseline"]["flat"]["mean"] == pytest.approx(0.025, abs=1e-9)
    assert out["reason"] is None


def test_a_surface_without_a_baseline_is_a_named_refusal_not_a_curve():
    out = benchmark_surface(_series(n=60))
    assert out["rows"] and out["rows"][0]["name"] == "strategy"
    assert out["baseline_available"] is False
    assert out["delta_vs_baseline"] == {}
    assert "raw single curve is not a result" in out["reason"]


def test_short_or_unusable_arms_refuse_by_name():
    assert "strategy arm" in benchmark_rows([0.01], {"bm": _series(n=30)})["unavailable"]
    assert "baseline 'bm'" in benchmark_rows(_series(n=30), {"bm": [0.01]})["unavailable"]
    assert "strategy arm" in benchmark_rows("nope", {"bm": _series(n=30)})["unavailable"]
    assert "non-numeric" in benchmark_rows(_series(n=30), cost_bps="x")["unavailable"]
