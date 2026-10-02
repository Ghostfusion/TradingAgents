"""Phase 6 of the entry/exit price engine: the §103 assembly.

``entry_exit_price`` assembles the ENTRY and EXIT blocks. ``final_entry_price``
is §100's ``min(target, max)`` over the terms present - and **execution is not
one of them**, because §102's listing of it there double-counts a cost
adjustment as an economic ceiling (§100 applies the buffer *before* the min).
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.entry_exit_price import (
    FINAL_ENTRY_TERMS,
    entry_exit_price,
)

pytestmark = pytest.mark.timeout(600)


def test_final_entry_is_the_min_of_the_present_ceilings():
    out = entry_exit_price(
        price=100.0,
        valuation_ceiling=120.0,
        valuation_price=110.0,
        tranche_price=105.0,
        stop=95.0,
        max_stop_fraction=0.10,
    )["entry"]
    # ceiling = min(120) = 120; target = mean(110,105) = 107.5; risk = 95/0.9
    assert out["max_entry_price"] == pytest.approx(120.0)
    assert out["target_entry_price"] == pytest.approx(107.5)
    assert out["risk_adjusted_entry_price"] == pytest.approx(95.0 / 0.90)
    # the risk rule is the tightest of the three: 95/0.9 = 105.56 < 107.5 < 120
    assert out["final_entry_price"] == pytest.approx(95.0 / 0.90)
    assert out["final_entry_binding"] == "risk_adjusted_entry_price"


def test_execution_is_reported_but_not_a_member_of_the_final_min():
    """§102 lists execution inside the min; §100 applies the buffer before it.
    Taking that listing literally would double-count the cost."""
    out = entry_exit_price(
        price=100.0,
        tranche_price=99.0,
        execution_spread=0.002,
        execution_impact=0.003,
    )["entry"]
    assert out["liquidity_adjusted_entry_price"] == pytest.approx(99.5)
    assert out["final_entry_price"] == pytest.approx(99.0)
    assert "liquidity_adjusted_entry_price" not in FINAL_ENTRY_TERMS
    assert "liquidity_adjusted_entry_price" not in out["final_entry_basis"]
    assert set(out["final_entry_basis"]) <= set(FINAL_ENTRY_TERMS)


def test_final_is_none_when_no_term_is_available_never_a_fallback():
    out = entry_exit_price(price=100.0)["entry"]
    assert out["final_entry_price"] is None
    assert out["final_entry_binding"] is None
    assert out["final_entry_basis"] == {}
    assert out["max_entry_price"] is None
    assert out["ceiling_status"] == "NO_SOURCE"


def test_exit_block_carries_the_predicate_and_its_precedence():
    out = entry_exit_price(price=94.0, stop=95.0, target=110.0, risk_gate="REJECT")
    assert out["exit"]["reason"] == "risk_gate"
    assert out["exit"]["exit_price"] == pytest.approx(94.0)
    assert out["exit"]["precedence"][0] == "risk_gate"
    assert "target" in out["exit"]["precedence"]


def test_cvar_permission_is_reported_alongside_the_price():
    ok = entry_exit_price(
        price=100.0, stop=95.0, max_stop_fraction=0.10, name_cvar=0.02, cvar_budget=0.03
    )["entry"]
    over = entry_exit_price(
        price=100.0, stop=95.0, max_stop_fraction=0.10, name_cvar=0.09, cvar_budget=0.03
    )["entry"]
    assert ok["cvar_status"] == "OK"
    assert over["cvar_status"] == "OVER_BUDGET"
    # Owner invariant (2026-10-02): an over-budget CVaR is a STATUS. It must not
    # be folded into a smaller / less-attractive entry price - the risk
    # governor's PASS/FAIL stays the authoritative gate, and a price term must
    # never override it.
    assert over["risk_adjusted_entry_price"] == ok["risk_adjusted_entry_price"]
    assert over["max_entry_price"] == ok["max_entry_price"]


def test_the_object_carries_both_blocks_and_the_coverage_counts():
    out = entry_exit_price(price=100.0, valuation_ceiling=110.0, tranche_price=100.0)
    assert set(out) == {"entry", "exit"}
    entry = out["entry"]
    for key in (
        "max_entry_price", "ceiling_status", "target_entry_price",
        "risk_adjusted_entry_price", "cvar_status", "execution_price",
        "liquidity_adjusted_entry_price", "final_entry_price",
    ):
        assert key in entry
    assert entry["ceiling_coverage"] == 1
    assert entry["target_coverage"] == 1
