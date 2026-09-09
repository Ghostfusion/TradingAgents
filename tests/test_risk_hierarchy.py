"""Tests for the hard-gate precedence resolver (strategies/risk_hierarchy.py).

The desk rule: risk controls compose in fixed precedence order, earliest
REJECT wins — kill > portfolio > trade > liquidity > regime > data. A lower
gate that would have PASSed never overrides a higher REJECT.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.risk_hierarchy import (
    evaluate_hierarchy,
    kill_switch_state,
    render_hierarchy,
)


@pytest.mark.timeout(30)
class TestRiskHierarchy:
    def test_no_gate_blocks_is_pass(self):
        r = evaluate_hierarchy()
        assert r["verdict"] == "PASS"
        assert r["blocker"] is None

    def test_kill_switch_wins_over_all(self):
        # Kill + drawdown + trade all blocked -> kill is the blocker.
        r = evaluate_hierarchy(halt=True, drawdown_over=True, trade_reject=True)
        assert r["verdict"] == "REJECT"
        assert r["blocker"] == "kill_switch"

    def test_portfolio_blocks_despite_ok_trade(self):
        # The TJX case: drawdown_gate=True but trade-level risk_ok would pass.
        r = evaluate_hierarchy(halt=False, drawdown_over=True, trade_reject=False)
        assert r["verdict"] == "REJECT"
        assert r["blocker"] == "portfolio"

    def test_trade_blocks_when_no_higher_gate(self):
        r = evaluate_hierarchy(trade_reject=True)
        assert r["blocker"] == "trade"

    def test_liquidity_blocks(self):
        r = evaluate_hierarchy(illiquid=True)
        assert r["blocker"] == "liquidity"

    def test_highest_blocker_is_returned_not_multiple(self):
        r = evaluate_hierarchy(
            drawdown_over=True, trade_reject=True, illiquid=True, regime_veto=True
        )
        assert r["blocker"] == "portfolio"  # earliest of the active set

    def test_kill_switch_state_day_loss(self):
        assert kill_switch_state(-0.03, hard_day_limit_pct=-0.02) is True
        assert kill_switch_state(-0.01, hard_day_limit_pct=-0.02) is False
        assert kill_switch_state(-0.03) is False  # no tier configured

    def test_kill_switch_state_drawdown(self):
        assert kill_switch_state(None, hard_max_drawdown_pct=0.20, drawdown_pct=0.25) is True
        assert kill_switch_state(None, hard_max_drawdown_pct=0.20, drawdown_pct=0.15) is False

    def test_render_reports_blocker(self):
        r = evaluate_hierarchy(halt=True)
        text = render_hierarchy(r)
        assert "REJECT" in text
        assert "kill_switch" in text
