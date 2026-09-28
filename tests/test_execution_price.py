"""Phase 3 of the entry/exit price engine: the execution cost buffer.

``execution_price`` prices the §74-§78 cost terms the caller measured and
reports the ones it did not. An absent term shrinks coverage - it is never
defaulted to zero, because "not measured" and "free" are different claims.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.execution_price import COST_SOURCES, execution_price

pytestmark = pytest.mark.timeout(600)


def test_buffer_is_the_sum_of_the_measured_cost_fractions():
    out = execution_price(price=100.0, spread=0.001, impact=0.002, slippage=0.0005)
    assert out["buffer_fraction"] == pytest.approx(0.0035)
    assert out["buffer"] == pytest.approx(0.35)
    assert out["execution_price"] == pytest.approx(99.65)
    assert out["coverage"] == 3
    assert out["coverage_ratio"] == pytest.approx(1.0)
    assert out["status"] == "OK"


def test_liquidity_adjusted_entry_price_is_the_same_number():
    out = execution_price(price=100.0, impact=0.002)
    assert out["liquidity_adjusted_entry_price"] == pytest.approx(out["execution_price"])


def test_partial_coverage_reads_differently_from_full():
    one = execution_price(price=100.0, impact=0.002)
    three = execution_price(price=100.0, spread=0.001, impact=0.002, slippage=0.0005)
    assert one["coverage"] == 1
    assert three["coverage"] == 3
    assert one["missing_sources"] == ["spread", "slippage"]
    assert one["execution_price"] > three["execution_price"]


def test_no_cost_term_is_not_a_free_trade():
    out = execution_price(price=100.0)
    assert out["buffer"] is None
    assert out["execution_price"] is None
    assert out["status"] == "NO_SOURCE"
    assert out["coverage"] == 0
    assert out["missing_sources"] == list(COST_SOURCES)
    assert out["reason"]


def test_no_reference_price_is_no_source():
    out = execution_price(price=None, spread=0.001)
    assert out["buffer"] is None
    assert out["status"] == "NO_SOURCE"
    assert "price" in out["reason"]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -0.01, 1.0, 2.0, "n/a", True])
def test_unusable_cost_fraction_is_absent_not_zero(bad):
    out = execution_price(price=100.0, spread=bad, impact=0.002)
    assert out["available_sources"] == ["impact"]
    assert out["coverage"] == 1
    assert out["buffer_fraction"] == pytest.approx(0.002)


def test_liquidity_status_is_passed_through_not_derived():
    out = execution_price(price=100.0, spread=0.001, liquidity_status="CAUTION")
    assert out["liquidity_status"] == "CAUTION"
    assert execution_price(price=100.0, spread=0.001)["liquidity_status"] is None
