"""Tests for the decision guardrail (DSA phase A; design §6-1).

- INVARIANT (property): stabilize_decision NEVER upgrades — the output
  rating's strength is always <= the input's, per the 5-tier scale.
- risk-cap: a high-severity risk row caps an Overweight/Buy at Hold
  (severity >= HIGH, so CRITICAL caps too).
- near-resistance without inflow caps a buy; near-support without outflow
  softens a bearish call one tier.
- score<->rating validator flags documented mismatches, passes matches.
- confidence cap on degraded data quality.
"""

from unittest.mock import MagicMock

import pytest

from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    RiskDebaterTurnPayload,
    RiskSeverity,
)
from tradingagents.dataflows.config import reset_config, set_config
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

    def test_critical_risk_caps_at_hold(self):
        # CRITICAL is >= HIGH in the debate's LOW/MEDIUM/HIGH/CRITICAL
        # vocabulary, so it must cap exactly like HIGH (rule 1's documented
        # threshold). Pre-fix the predicate compared == "high", so a CRITICAL
        # row left a Buy untouched.
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": "critical"}])
        assert out["rating"] == "Hold"
        assert out["overrides"][0]["reason"].startswith("risk-cap")

    def test_critical_risk_enum_member_caps_at_hold(self):
        # Stored debate payloads keep the RiskSeverity MEMBER, whose str() is
        # "RiskSeverity.CRITICAL" — the predicate must read .value.
        out = dg.stabilize_decision("Overweight", risk_rows=[{"severity": RiskSeverity.CRITICAL}])
        assert out["rating"] == "Hold"
        assert out["overrides"][0]["reason"].startswith("risk-cap")

    def test_high_risk_enum_member_caps_at_hold(self):
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": RiskSeverity.HIGH}])
        assert out["rating"] == "Hold"

    def test_medium_risk_unchanged(self):
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": "medium"}])
        assert out["rating"] == "Buy" and out["overrides"] == []

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


class TestJudgeReliabilityConfidenceGate:
    """D1/D2 PM gate — a risk-debate judge that flipped or fell back must
    cap the PM's confidence (never raise) so a borderline/unreliable judge
    can't ride a high-conviction decision."""

    def test_clean_judge_passes(self):
        assert dg.cap_pm_confidence_on_judge(
            0.9, judge_agreement=1.0, judge_flip=False, judge_structured_fallback=False
        ) == (0.9, None)

    def test_flip_caps(self):
        conf, reason = dg.cap_pm_confidence_on_judge(0.9, judge_flip=True)
        assert conf == pytest.approx(0.5) and reason is not None
        assert "flipped" in reason

    def test_low_agreement_caps(self):
        conf, reason = dg.cap_pm_confidence_on_judge(0.8, judge_agreement=0.67)
        assert conf == pytest.approx(0.5) and reason is not None

    def test_fallback_caps(self):
        conf, reason = dg.cap_pm_confidence_on_judge(0.8, judge_structured_fallback=True)
        assert conf == pytest.approx(0.5) and reason is not None
        assert "fallback" in reason

    def test_below_new_cap_unchanged(self):
        assert dg.cap_pm_confidence_on_judge(0.4, judge_flip=True) == (0.4, None)

    def test_none_confidence(self):
        assert dg.cap_pm_confidence_on_judge(None, judge_flip=True) == (None, None)

    def test_never_raises_on_clean_with_missing_fields(self):
        # Missing judge fields (legacy state) must not trigger a cap.
        assert dg.cap_pm_confidence_on_judge(0.9) == (0.9, None)


# ---------------------------------------------------------------------------
# P0-5: the PM's deterministic guardrail must consult the risk-debate state.
# Pre-fix the hook fed `stabilize_decision` a row from the risk MATRIX STRING
# (`risk_matrix_block and [{}] or []`), i.e. always `[{}]` with severity "",
# so rule 1 (risk-cap) could never fire on a real HIGH/CRITICAL risk factor.
# ---------------------------------------------------------------------------


@pytest.fixture
def guardrail_on():
    set_config({"enable_decision_guardrail": True})
    yield
    reset_config()


def _pm_state(risk_factors):
    """Minimal Portfolio-Manager state carrying one structured risk round.

    The round payload is built through the real schema + ``model_dump()``, so
    the state matches what ``create_debater_turn`` stores (RiskSeverity
    members, not strings).
    """
    payload = RiskDebaterTurnPayload(
        round_index=1,
        stance="AGGRESSIVE",
        core_thesis="Momentum intact.",
        quantitative_claims=[],
        risk_factors=risk_factors,
        recommended_allocation_pct=5.0,
    ).model_dump()
    return {
        "company_of_interest": "NVDA",
        "risk_debate_state": {
            "history": "Risk debate history.",
            "aggressive_history": "a",
            "conservative_history": "c",
            "neutral_history": "n",
            "judge_decision": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 1,
        },
        "investment_plan": "Research plan.",
        "trader_investment_plan": "Trader plan.",
        "structured_risk_state": {"round_records": [{"aggressive": payload}]},
    }


def _pm_llm(rating):
    """Structured LLM stub returning `rating` (no network)."""
    decision = PortfolioDecision(
        rating=rating,
        executive_summary="Synthesized view.",
        investment_thesis="Grounded in the risk debate.",
    )
    structured = MagicMock()
    structured.invoke.return_value = decision
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


class TestPortfolioManagerRiskCapWiring:
    def test_high_risk_factor_caps_rating_at_hold(self, guardrail_on):
        # The stored shape: `DebaterTurnPayload.model_dump()` keeps the
        # RiskSeverity MEMBER (str(member) == "RiskSeverity.HIGH").
        state = _pm_state(
            [
                {
                    "risk_id": "margin_compression",
                    "severity": RiskSeverity.HIGH,
                    "mitigation_stated": False,
                }
            ]
        )
        out = create_portfolio_manager(_pm_llm(PortfolioRating.BUY))(state)
        assert out["pm_decision"]["rating"] == "Hold"
        assert "risk-cap" in out["pm_decision"]["guardrail_reason"]
        assert out["pm_decision"]["risk_cap"] == "Hold"
        # the rendered decision the pipeline stores carries the capped rating
        assert out["final_trade_decision"].startswith("**Rating**: Hold")

    def test_critical_risk_factor_caps_rating_at_hold(self, guardrail_on):
        # CRITICAL is >= HIGH in the debate's severity vocabulary.
        state = _pm_state(
            [
                {
                    "risk_id": "going_concern",
                    "severity": RiskSeverity.CRITICAL,
                    "mitigation_stated": False,
                }
            ]
        )
        out = create_portfolio_manager(_pm_llm(PortfolioRating.OVERWEIGHT))(state)
        assert out["pm_decision"]["rating"] == "Hold"
        assert "risk-cap" in out["pm_decision"]["guardrail_reason"]

    def test_medium_risk_factor_does_not_cap(self, guardrail_on):
        state = _pm_state(
            [{"risk_id": "fx", "severity": "medium", "mitigation_stated": True}]
        )
        out = create_portfolio_manager(_pm_llm(PortfolioRating.BUY))(state)
        assert out["pm_decision"]["rating"] == "Buy"
        assert not out["pm_decision"]["guardrail_reason"]

    def test_no_risk_factors_does_not_cap(self, guardrail_on):
        out = create_portfolio_manager(_pm_llm(PortfolioRating.BUY))(_pm_state([]))
        assert out["pm_decision"]["rating"] == "Buy"
        assert not out["pm_decision"]["guardrail_reason"]


class TestPhase0DecisionContextBoundary:
    """Phase 0 (docs/design_decision_context.md §12.4): the PM model's
    structured emit is recorded BEFORE any deterministic postprocess.

    The mutation this defends against is a one-line reorder: capturing
    ``pm_llm_output`` after ``_guardrail_hook`` instead of before it. The
    guardrail rewrites ``result.rating`` in place, so the reordered capture
    returns the GUARDRAILED rating under a "raw" label - and every Phase 1
    arm would then measure the gates instead of the model. ``pm_decision``
    already IS the post-guardrail object; the two must differ here or the
    boundary is not being recorded at all.
    """

    def test_raw_emit_survives_a_guardrail_downgrade(self, guardrail_on):
        state = _pm_state(
            [{"risk_id": "going_concern", "severity": RiskSeverity.HIGH,
              "mitigation_stated": False}]
        )
        out = create_portfolio_manager(_pm_llm(PortfolioRating.BUY))(state)

        # The guardrail capped Buy -> Hold (pre-existing behaviour, unchanged).
        assert out["pm_decision"]["rating"] == "Hold"
        # ...and the raw emit still says what the model actually decided.
        assert out["pm_llm_output"]["rating"] == "Buy"

    def test_raw_emit_records_the_prompt_size(self, guardrail_on):
        out = create_portfolio_manager(_pm_llm(PortfolioRating.BUY))(_pm_state([]))
        entry = out["prompt_metrics"]["pm"]
        assert entry["chars"] > 0
        assert entry["tokens_est"] == entry["chars"] // 4


class TestPhase0TelemetryBlock:
    """The card block keeps the three decision layers apart."""

    def test_llm_output_is_not_the_guardrailed_rating(self):
        from tradingagents.agents.utils.prompt_metrics import decision_telemetry_block

        state = {
            "company_of_interest": "QCOM",
            "trade_date": "2026-09-19",
            "pm_decision": {"rating": "Hold", "guardrail_reason": "risk-cap: high"},
            "pm_llm_output": {"rating": "Buy", "confidence": 0.72},
            "risk_gate": {"verdict": "REJECT"},
        }
        block = decision_telemetry_block({}, state)
        assert block["llm_output"]["rating"] == "Buy"
        assert block["llm_output"]["direction"] == "bullish"
        assert block["deterministic_postprocess"]["guardrail_rating"] == "Hold"
        assert block["deterministic_postprocess"]["guardrail_changed_rating"] is True
        assert block["deterministic_postprocess"]["risk_gate"] == "REJECT"

    def test_signal_action_split_is_populated_not_phantom(self):
        # An earlier draft read these from state, where nothing writes them, and
        # silently recorded four nulls. The block must call the one real producer.
        from tradingagents.agents.utils.prompt_metrics import decision_telemetry_block

        block = decision_telemetry_block({}, {
            "pm_decision": {"rating": "Buy"},
            "pm_llm_output": {"rating": "Buy"},
            "risk_gate": {"verdict": "REJECT", "reasons": ["portfolio drawdown over limit"]},
        })
        split = block["deterministic_postprocess"]["signal_action"]
        assert split["security_signal"] == "BUY"
        assert split["portfolio_action"] == "NO_NEW_RISK"
        assert split["gated"] is True
        # The execution layer carries the engine's last action value, not null.
        assert block["execution"]["final_action"] == split["combined_action"]

    def test_absent_raw_emit_is_null_not_the_guardrailed_value(self):
        from tradingagents.agents.utils.prompt_metrics import decision_telemetry_block

        # A tree rebuilt from markdown has pm_decision but no raw emit: the
        # block must say null, never fall back to the post-guardrail rating.
        block = decision_telemetry_block({}, {"pm_decision": {"rating": "Hold"}})
        assert block["llm_output"]["rating"] is None
        assert block["llm_output"]["captured"] is False

    def test_prompt_metrics_reducer_merges_across_nodes(self):
        from tradingagents.agents.utils.prompt_metrics import (
            merge_prompt_metrics,
            record_stage,
        )

        # Last-write-wins would keep only the PM stage; the reducer keeps both.
        merged = merge_prompt_metrics(
            record_stage("analyst_market", "x" * 400)["prompt_metrics"],
            record_stage("pm", "y" * 800)["prompt_metrics"],
        )
        assert sorted(merged) == ["analyst_market", "pm"]
        assert merged["pm"]["tokens_est"] == 200

    def test_uncertainty_count_is_null_when_nothing_counted_it(self):
        # The rule Phase 0 established and Phase 2 preserves: a counter that
        # cannot be honestly taken is `None`, never `0` - `0` reads as "no
        # uncertainty was present" rather than "nothing counted it". With no
        # scorecard snapshot, nothing examined the engines.
        from tradingagents.reporting import _run_card_evidence_counts

        counts = _run_card_evidence_counts(
            {"researcher_independent_stances": {"bull": {"rating": "Buy"},
                                                "bear": {"rating": "Sell"}}}
        )
        assert counts["bullish_count"] == 1
        assert counts["bearish_count"] == 1
        assert counts["uncertainty_count"] is None
        assert "no scorecard snapshot" in counts["uncertainty_count_reason"]
        assert counts["counted_sources"] == ["researcher_independent_stances"]

    def test_uncertainty_count_is_taken_once_the_snapshot_exists(self):
        # Phase 2 supplied the vocabulary, so the same field is now a real count
        # over the named gaps the enabled engines declare. An engine whose gate is
        # OFF is not a gap - it is intentionally not running.
        from tradingagents.reporting import _run_card_evidence_counts

        def entry(enabled, score, reason=None):
            return {"enabled": enabled, "score": score, "reason": reason}

        counts = _run_card_evidence_counts(
            {
                "quant_scorecard": {
                    "engines": {
                        "fundamental": entry(True, 67.7),
                        "event": entry(True, None, "the catalyst snapshot is stamped after the graph"),
                        "news": entry(False, None, "enable_news_score is off"),
                    }
                }
            }
        )
        assert counts["uncertainty_count"] == 1
        assert "event" in counts["uncertainty_gaps"][0]
        assert "news" not in counts["uncertainty_gaps"][0]

    def test_snapshot_identity_is_stable_and_content_addressed(self):
        from tradingagents.agents.utils.prompt_metrics import snapshot_identity

        state = {"company_of_interest": "QCOM", "trade_date": "2026-09-19"}
        a = snapshot_identity({}, state)
        b = snapshot_identity({}, dict(state))
        assert a == b, "same evidence must hash the same"
        # A different trade date is different evidence - the pair is invalid.
        c = snapshot_identity({}, {**state, "trade_date": "2026-09-18"})
        assert c["data_snapshot_hash"] != a["data_snapshot_hash"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
