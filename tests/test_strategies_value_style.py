"""V3/V4/V5 unit tests (offline)."""

import pytest

from tradingagents.strategies.debate_context import build_computed_context
from tradingagents.strategies.exits import (
    exit_check,
    net_of_cost,
    rebalance_due,
    stop_to_breakeven,
    target_level,
)
from tradingagents.strategies.portfolio import (
    adjust_for_caps,
    capped_weights,
    min_names_ok,
    sector_cap,
    summary,
    value_ratio_weights,
)


def test_value_ratio_weights_proportional():
    w = value_ratio_weights({"A": 0.8, "B": 0.2})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["A"] == pytest.approx(0.8)
    z = value_ratio_weights({"A": 0.8, "B": 0.0}, min_weight=0.01)
    assert z["B"] == pytest.approx(0.01)


def test_caps_are_hard_and_leave_cash():
    w = value_ratio_weights({"A": 0.8, "B": 0.2})
    capped = capped_weights(w, cap=0.3)
    assert capped["A"] == pytest.approx(0.3)
    assert sum(capped.values()) < 1.0


def test_sector_cap_hard():
    g = {"tech": 0.6, "health": 0.25, "staples": 0.15}
    capped = sector_cap(g, cap=0.35)
    assert capped["tech"] == pytest.approx(0.35)


def test_adjust_and_min_guard():
    w = {"A": 0.5, "B": 0.5}
    sectors = {"A": "tech", "B": "health"}
    adj = adjust_for_caps(w, sectors, sector_cap_limit=0.4, max_name=0.3)
    assert all(v <= 0.3 + 1e-9 for v in adj.values())
    assert sum(adj.values()) <= 1.0 + 1e-9
    assert min_names_ok(10) is True
    assert min_names_ok(3, min_n=10) is False
    assert summary(w, min_n=2)["min_names_satisfied"] is True


def test_exits():
    close = 100.0
    atr = 2.0
    entry = 98.0
    assert stop_to_breakeven(entry, atr, cushion_atr=1.0) == 100.0
    assert target_level(close, atr, atr_mult=4.0) == 108.0
    assert net_of_cost(0.05, cost_bps=10) == pytest.approx(0.049)
    # item 3: illiquid name scales cost up; None keeps flat cost
    assert net_of_cost(0.05, cost_bps=10, illiq=1e-5) == pytest.approx(0.049 - 1e-5 * 1e5 / 10000.0)
    assert net_of_cost(0.05, cost_bps=10, illiq=None) == pytest.approx(0.049)
    assert rebalance_due(31, interval_days=30) is True
    assert rebalance_due(5, 30) is False
    e = exit_check(entry=98.0, close=100.0, atr=0.5, target_mult=4.0)
    assert e["holding_action"] in ("target", "stop", "hold")


def test_build_computed_context():
    ctx = build_computed_context(
        nebit=1.2e9,
        ev_nebit=12.5,
        pe_hist_pct=0.35,
        trap={"level": "LOW", "evidence": []},
        margin=0.18,
    )
    assert "Computed context" in ctx
    assert "trap_risk=LOW" in ctx
    assert build_computed_context() == ""
