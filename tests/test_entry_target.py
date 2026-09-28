"""Phase 2 of the entry/exit price engine: the entry target price.

``entry_target`` is §100's ``P_entry,target`` over the **price anchors this
repo produces**. The score-weighted blend is deliberately not implemented
(no calibrated score -> price bridge exists), so the regime and risk
adjustment terms stay absent rather than invented.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.entry_target import (
    ADJUSTMENT_TERMS,
    ANCHOR_SOURCES,
    entry_target,
)

pytestmark = pytest.mark.timeout(600)


def test_equal_weight_blend_is_the_mean():
    out = entry_target(valuation_price=120.0, technical_price=110.0, tranche_price=100.0)
    assert out["value"] == pytest.approx(110.0)
    assert out["raw"] == pytest.approx(110.0)
    assert out["status"] == "OK"
    assert out["coverage"] == 3
    assert out["coverage_ratio"] == pytest.approx(1.0)
    assert out["basis"] == {"valuation": 120.0, "technical": 110.0, "tranche": 100.0}


def test_explicit_weights_shift_the_blend():
    out = entry_target(
        valuation_price=120.0,
        technical_price=100.0,
        weights={"valuation": 3.0, "technical": 1.0},
    )
    assert out["value"] == pytest.approx(115.0)
    assert out["weights"] == {"valuation": 3.0, "technical": 1.0}


def test_weight_for_an_absent_anchor_is_dropped_not_placeholder():
    """A weight naming a source that did not report must not pull the blend
    toward a placeholder - the denominator is the present weights only."""
    out = entry_target(technical_price=100.0, weights={"valuation": 9.0, "technical": 1.0})
    assert out["value"] == pytest.approx(100.0)
    assert out["weights"] == {"technical": 1.0}
    assert out["available_sources"] == ["technical"]
    assert "valuation" in out["missing_sources"]


def test_one_anchor_is_its_own_target():
    out = entry_target(tranche_price=97.5)
    assert out["value"] == pytest.approx(97.5)
    assert out["coverage"] == 1
    assert out["coverage_ratio"] == pytest.approx(1.0 / 3.0)


def test_no_anchor_is_no_source_never_a_fallback_price():
    out = entry_target()
    assert out["value"] is None
    assert out["raw"] is None
    assert out["status"] == "NO_SOURCE"
    assert out["basis"] == {}
    assert out["coverage"] == 0
    assert out["missing_sources"] == list(ANCHOR_SOURCES)
    assert out["reason"]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), 0.0, -3.0, "n/a", True])
def test_unusable_anchor_is_absent_not_zero(bad):
    out = entry_target(valuation_price=bad, tranche_price=90.0)
    assert out["value"] == pytest.approx(90.0)
    assert "valuation" in out["missing_sources"]
    assert out["coverage"] == 1


def test_adjustment_terms_are_absent_by_default_and_reported():
    """Regime and risk are 0-100 scores here, not price multipliers, so with
    no calibration they are NO_SOURCE - never a silent 1.0."""
    out = entry_target(tranche_price=100.0)
    assert out["adjustments"] == {"regime": None, "risk": None}
    assert out["adjustments_missing"] == list(ADJUSTMENT_TERMS)


def test_supplied_adjustment_multiplies_and_leaves_the_term_list():
    out = entry_target(tranche_price=100.0, regime_multiplier=0.98)
    assert out["value"] == pytest.approx(98.0)
    assert out["raw"] == pytest.approx(100.0)
    assert out["adjustments"]["regime"] == pytest.approx(0.98)
    assert out["adjustments_missing"] == ["risk"]
