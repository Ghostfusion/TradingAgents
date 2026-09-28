"""Phase 0 of the entry/exit price engine: the entry ceiling.

``entry_ceiling`` is the hard maximum price for a long entry: the ``min`` over
whichever ceiling sources could be measured. The tests here pin the locked
contract - long-only by construction (no ``direction`` argument), absent
sources never invented, ``NO_SOURCE`` never carrying a fallback price, and a
``min`` over 1 of 3 sources reading differently from 3 of 3.
"""

from __future__ import annotations

import inspect

import pytest

from tradingagents.strategies.entry_ceiling import (
    CEILING_SOURCES,
    CEILING_STATUSES,
    entry_ceiling,
)

pytestmark = pytest.mark.timeout(600)


def test_no_direction_parameter_long_only_by_construction():
    """Long-only is an invariant of the signature, not a runtime guard.

    A ``raise`` on ``direction != "long"`` would fire on every production run:
    the flow's ``direction`` is ``None`` and the LLM's is ``"neutral"``. The
    ceiling therefore takes no direction at all.
    """
    params = inspect.signature(entry_ceiling).parameters
    assert "direction" not in params
    assert set(params) == {
        "price",
        "valuation_ceiling",
        "expected_return_ceiling",
        "rr_ceiling",
    }


def test_min_over_all_three_sources():
    out = entry_ceiling(
        price=100.0,
        valuation_ceiling=110.0,
        expected_return_ceiling=120.0,
        rr_ceiling=130.0,
    )
    assert out["value"] == pytest.approx(110.0)
    assert out["binding_source"] == "valuation"
    assert out["available_sources"] == ["valuation", "expected_return", "risk_reward"]
    assert out["missing_sources"] == []
    assert out["coverage"] == 3
    assert out["coverage_ratio"] == pytest.approx(1.0)
    assert out["status"] == "PASS"


def test_min_picks_the_binding_source_not_the_first():
    out = entry_ceiling(
        price=100.0,
        valuation_ceiling=140.0,
        expected_return_ceiling=105.0,
        rr_ceiling=130.0,
    )
    assert out["value"] == pytest.approx(105.0)
    assert out["binding_source"] == "expected_return"


def test_tie_break_follows_declared_source_order():
    out = entry_ceiling(
        price=100.0,
        valuation_ceiling=110.0,
        expected_return_ceiling=110.0,
        rr_ceiling=None,
    )
    assert out["value"] == pytest.approx(110.0)
    assert out["binding_source"] == "valuation"


def test_zero_sources_is_no_source_never_a_fallback_price():
    out = entry_ceiling(price=168.20)
    assert out["value"] is None
    assert out["status"] == "NO_SOURCE"
    assert out["binding_source"] is None
    assert out["basis"] == {}
    assert out["coverage"] == 0
    assert out["coverage_ratio"] == pytest.approx(0.0)
    assert out["missing_sources"] == list(CEILING_SOURCES)
    assert out["ceiling_distance"] is None
    assert out["ceiling_margin"] is None
    assert out["reason"]


def test_coverage_one_of_three_reads_differently_from_three_of_three():
    one = entry_ceiling(price=100.0, valuation_ceiling=110.0)
    three = entry_ceiling(
        price=100.0,
        valuation_ceiling=110.0,
        expected_return_ceiling=120.0,
        rr_ceiling=130.0,
    )
    assert one["value"] == three["value"] == pytest.approx(110.0)
    assert one["status"] == three["status"] == "PASS"
    assert one["coverage"] == 1
    assert three["coverage"] == 3
    assert one["coverage_ratio"] == pytest.approx(1.0 / 3.0)
    assert three["coverage_ratio"] == pytest.approx(1.0)
    assert one["missing_sources"] == ["expected_return", "risk_reward"]
    assert len(one["available_sources"]) < len(three["available_sources"])


def test_distance_and_margin_use_different_denominators():
    out = entry_ceiling(price=100.0, valuation_ceiling=110.0)
    # distance: headroom as a fraction of the CURRENT price.
    assert out["ceiling_distance"] == pytest.approx(0.10)
    # margin: headroom as a fraction of the CEILING.
    assert out["ceiling_margin"] == pytest.approx(10.0 / 110.0)
    assert out["ceiling_distance"] != pytest.approx(out["ceiling_margin"])


def test_above_ceiling_is_a_distinct_verdict():
    out = entry_ceiling(price=120.0, valuation_ceiling=110.0)
    assert out["status"] == "ABOVE_CEILING"
    assert out["value"] == pytest.approx(110.0)
    assert out["ceiling_distance"] == pytest.approx(-10.0 / 120.0)
    assert out["ceiling_distance"] < 0


def test_at_the_ceiling_is_a_pass_not_above():
    out = entry_ceiling(price=110.0, valuation_ceiling=110.0)
    assert out["status"] == "PASS"
    assert out["ceiling_distance"] == pytest.approx(0.0)


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), 0.0, -5.0, "n/a", True])
def test_unusable_source_is_absent_not_zero(bad):
    """A constant must never stand in for a measurement: a non-level is a
    missing source, which shrinks coverage - it must not enter the min."""
    out = entry_ceiling(price=100.0, valuation_ceiling=bad, rr_ceiling=90.0)
    assert out["value"] == pytest.approx(90.0)
    assert out["binding_source"] == "risk_reward"
    assert "valuation" in out["missing_sources"]
    assert out["coverage"] == 1


def test_usable_price_reported_when_parsed_from_string_or_int():
    out = entry_ceiling(price="100", valuation_ceiling=110)
    assert out["value"] == pytest.approx(110.0)
    assert out["status"] == "PASS"


def test_unusable_reference_price_forms_no_verdict():
    out = entry_ceiling(price=None, valuation_ceiling=110.0)
    assert out["value"] == pytest.approx(110.0)
    assert out["coverage"] == 1
    assert out["status"] == "NO_SOURCE"
    assert out["ceiling_distance"] is None
    assert out["ceiling_margin"] is None
    assert out["reason"]


def test_status_is_always_one_of_the_locked_states():
    cases = [
        entry_ceiling(price=100.0),
        entry_ceiling(price=100.0, valuation_ceiling=110.0),
        entry_ceiling(price=120.0, valuation_ceiling=110.0),
    ]
    assert [c["status"] for c in cases] == ["NO_SOURCE", "PASS", "ABOVE_CEILING"]
    assert set(CEILING_STATUSES) == {"PASS", "ABOVE_CEILING", "NO_SOURCE"}
    for c in cases:
        assert c["status"] in CEILING_STATUSES
