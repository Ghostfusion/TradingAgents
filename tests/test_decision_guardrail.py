"""Tests for the decision guardrail (DSA phase A; design §6-1).

- INVARIANT (property): stabilize_decision NEVER upgrades — the output
  rating's strength is always <= the input's, per the 5-tier scale.
- risk-cap: a high-severity risk row caps an Overweight/Buy at Hold.
- near-resistance without inflow caps a buy; near-support without outflow
  softens a bearish call one tier.
- score<->rating validator flags documented mismatches, passes matches.
- confidence cap on degraded data quality.
"""

import pytest

from tradingagents.strategies import decision_guardrail as dg

pytestmark = pytest.mark.timeout(30)

STRENGTH = dg._STRENGTH


def _strength(rating: str) -> int:
    return STRENGTH[rating]


class TestDowngradeOnlyInvariant:
    @pytest.mark.parametrize("rating", list(dg.RATING_ORDER))
    @pytest.mark.parametrize("risk", [None, [], [{"severity": "high"}], [{"severity": "low"}]])
    @pytest.mark.parametrize("tech", [None, {"price": 100.0, "resistance": 101.0, "support": 90.0}])
    @pytest.mark.parametrize("flow", [None, {}, {"inflow_confirmed": True}, {"outflow_confirmed": True}])
    def test_never_upgrades(self, rating, risk, tech, flow):
        out = dg.stabilize_decision(rating, risk_rows=risk, technical_read=tech, flow_read=flow)
        out_strength = _strength(out["rating"])
        assert out_strength <= _strength(rating)  # THE invariant
        assert out["rating"] in dg.RATING_ORDER

    def test_unknown_rating_unchanged(self):
        out = dg.stabilize_decision("Weird", risk_rows=[{"severity": "high"}])
        assert out["rating"] == "Weird" and out["overrides"] == []


class TestRiskCap:
    def test_high_risk_caps_at_hold(self):
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": "high"}])
        assert out["rating"] == "Hold"
        assert out["overrides"][0]["reason"].startswith("risk-cap")

    def test_low_risk_unchanged(self):
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": "low"}])
        assert out["rating"] == "Buy"

    def test_risk_never_forces_sell(self):
        # a bearish call with high risk stays bearish (risk caps, never flips)
        out = dg.stabilize_decision("Sell", risk_rows=[{"severity": "high"}])
        assert out["rating"] == "Sell"


class TestStructureRules:
    def test_near_resistance_no_inflow_caps_buy(self):
        tech = {"price": 100.0, "resistance": 101.0, "support": 90.0}
        out = dg.stabilize_decision("Overweight", technical_read=tech, flow_read={"inflow_confirmed": False})
        assert out["rating"] == "Hold"
        assert any("near-resistance" in o["reason"] for o in (out["overrides"] or []))
        assert out["overrides"][0]["from"] == "Overweight" and out["overrides"][0]["to"] == "Hold"

    def test_near_resistance_with_inflow_keeps_buy(self):
        tech = {"price": 100.0, "resistance": 101.0, "support": 90.0}
        out = dg.stabilize_decision("Buy", technical_read=tech, flow_read={"inflow_confirmed": True})
        assert out["rating"] == "Buy"

    def test_near_support_no_outflow_softens_bearish(self):
        tech = {"price": 100.0, "resistance": 110.0, "support": 99.0}
        out = dg.stabilize_decision("Sell", technical_read=tech, flow_read={"outflow_confirmed": False})
        assert out["rating"] == "Underweight"  # softened one tier, never flips

    def test_near_support_with_outflow_keeps_sell(self):
        tech = {"price": 100.0, "resistance": 110.0, "support": 99.0}
        out = dg.stabilize_decision("Sell", technical_read=tech, flow_read={"outflow_confirmed": True})
        assert out["rating"] == "Sell"

    def test_absent_technical_leaves_unchanged(self):
        out = dg.stabilize_decision("Buy", technical_read=None, flow_read={})
        assert out["rating"] == "Buy" and out["overrides"] == []


class TestScoreActionValidator:
    def test_match(self):
        assert dg.validate_score_action_agreement("Buy", 85)["ok"] is True
        assert dg.validate_score_action_agreement("Sell", 10)["ok"] is True

    def test_mismatch_flagged(self):
        v = dg.validate_score_action_agreement("Buy", 20)  # 20 implies Underweight
        assert v is not None and v["ok"] is False
        assert v["implied"] == "Underweight"

    def test_unknown_scale_version_none(self):
        assert dg.validate_score_action_agreement("Buy", 85, scale_version="v9") is None

    def test_unparseable_none(self):
        assert dg.validate_score_action_agreement("Buy", None) is None
        assert dg.validate_score_action_agreement("Buy", 999) is None

    def test_bands(self):
        assert dg.score_band_for(100) == "Buy"
        assert dg.score_band_for(79) == "Overweight"
        assert dg.score_band_for(40) == "Hold"
        assert dg.score_band_for(39) == "Underweight"
        assert dg.score_band_for(0) == "Sell"
        assert dg.score_for_rating("buy") == 80


class TestConfidenceCap:
    def test_fresh_passes(self):
        assert dg.cap_pm_confidence(0.9, "fresh") == (0.9, None)

    def test_stale_caps(self):
        conf, reason = dg.cap_pm_confidence(0.95, "stale")
        assert conf == pytest.approx(0.7) and reason is not None

    def test_below_cap_unchanged(self):
        assert dg.cap_pm_confidence(0.5, "partial") == (0.5, None)

    def test_custom_cap(self):
        conf, _ = dg.cap_pm_confidence(0.9, "unknown", cap=0.5)
        assert conf == pytest.approx(0.5)

    def test_none_confidence(self):
        assert dg.cap_pm_confidence(None, "stale") == (None, None)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
