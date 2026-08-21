"""Credit-spread stress classifier - pure/offline tests.

The thresholds mirror the credit-cycle table in docs/massive_integration.md:
  HY OAS <3% low, 3.5-4.5% moderate, >5.5% severe
  CCC OAS <8% low, 10-12% moderate, >15% severe
The worst band observed drives the de-risk scale.
"""

import pytest

from tradingagents.strategies.credit_spread import credit_stress_level


@pytest.mark.unit
def test_unknown_when_no_data():
    assert credit_stress_level(None, None) == {
        "level": "unknown", "scale": 1.0, "reasons": [],
    }


@pytest.mark.unit
def test_calm_hy_flows_low():
    res = credit_stress_level(2.7, 7.5)
    assert res["level"] == "low"
    assert res["scale"] == 1.0


@pytest.mark.unit
def test_moderate_ccc_drives_worst_band():
    # HY calm but CCC in the 10-12% moderate band -> moderate.
    res = credit_stress_level(2.9, 10.5)
    assert res["level"] == "moderate"
    assert res["scale"] == 0.85


@pytest.mark.unit
def test_high_when_hy_past_45():
    res = credit_stress_level(4.8, 9.0)
    assert res["level"] == "high"
    assert res["scale"] == 0.7


@pytest.mark.unit
def test_severe_when_ccc_past_15():
    res = credit_stress_level(3.0, 15.5)
    assert res["level"] == "severe"
    assert res["scale"] == 0.5


@pytest.mark.unit
def test_component_reasons_present():
    res = credit_stress_level(3.0, None, 1.6)
    assert any("hy_oas" in r for r in res["reasons"])
    assert any("bb_oas" in r for r in res["reasons"])
    assert any("ccc_oas" not in r for r in res["reasons"])  # ccc was None


@pytest.mark.unit
def test_bb_alone_drives_band():
    res = credit_stress_level(None, None, 4.0)
    assert res["level"] == "moderate"  # BB uses HY thresholds
