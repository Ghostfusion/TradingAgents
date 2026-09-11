"""Cross-module contract tests for the structured decision schemas.

Three defects fixed here, each pinned by a test that fails on the pre-fix
code and passes after:

1. ``PortfolioDecision.data_quality``: the schema coerced the placeholder
   ``"unknown"`` to ``None`` (the documented "confidence MUST be lowered"
   cap then never fired) while the hard-guard in
   ``graph/trading_graph.py`` blocked whenever the optional field was
   OMITTED (``or "unknown"``). Contract chosen: ``"unknown"``/omitted means
   "not reported" and never blocks; ONLY a positively reported
   ``stale``/``partial`` caps confidence and blocks the position.

2. The L1 wording: ``create_debate_l1`` emits the ``severity_tier``/
   ``l1_action`` dict from ``strategies.debate_score.classify_severity``.
   The dead ``L1Verdict``/``L1DeterministicResult`` PASS/FAIL mirror is gone;
   the emitted dict is the canonical contract, validated against
   ``L1SeverityTier``/``L1Action``/``L1ExecutionContext``.

3. ``PortfolioDecision.risk_cap`` was written by the guardrail and read by
   nothing; ``render_pm_decision`` now consumes it so the rendered/returned
   artefact reflects the cap.
"""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.researchers.structured_debate import (
    L1_KEY,
    create_debate_l1,
)
from tradingagents.agents.schemas import (
    DebaterTurnPayload,
    L1Action,
    L1ExecutionContext,
    L1SeverityTier,
    PortfolioDecision,
    PortfolioRating,
    RiskDebaterTurnPayload,
    RiskSeverity,
    render_pm_decision,
)
from tradingagents.dataflows.config import reset_config, set_config
from tradingagents.graph.trading_graph import _data_quality_blocks_position
from tradingagents.strategies import debate_score, decision_guardrail as dg

pytestmark = pytest.mark.timeout(60)

_DEGRADED = ("stale", "partial")


# ---------------------------------------------------------------------------
# 1. data_quality contract
# ---------------------------------------------------------------------------


class TestDataQualitySchema:
    def test_reported_values_survive_validation(self):
        for value in ("fresh", *_DEGRADED):
            d = PortfolioDecision(
                rating=PortfolioRating.OVERWEIGHT,
                executive_summary="s",
                investment_thesis="t",
                data_quality=value,
            )
            assert d.data_quality == value

    def test_unknown_placeholder_is_not_reported(self):
        """'unknown' is a placeholder, not a degraded read -> None."""
        for placeholder in ("unknown", "null", "N/A", ""):
            d = PortfolioDecision(
                rating=PortfolioRating.OVERWEIGHT,
                executive_summary="s",
                investment_thesis="t",
                data_quality=placeholder,
            )
            assert d.data_quality is None

    def test_bogus_value_still_rejected(self):
        with pytest.raises(ValidationError):
            PortfolioDecision(
                rating=PortfolioRating.OVERWEIGHT,
                executive_summary="s",
                investment_thesis="t",
                data_quality="rotten",
            )


class TestDataQualityGuard:
    def test_only_reported_degraded_blocks(self):
        for dq in _DEGRADED:
            assert _data_quality_blocks_position({"data_quality": dq}) is True

    def test_omitted_or_clean_does_not_block(self):
        # The pre-fix guard read `... or "unknown" in ("stale", "unknown")`,
        # so every omitted field blocked the position.
        assert _data_quality_blocks_position({}) is False
        assert _data_quality_blocks_position(None) is False
        assert _data_quality_blocks_position({"data_quality": None}) is False
        assert _data_quality_blocks_position({"data_quality": "fresh"}) is False
        # A raw placeholder (pre-schema) is still "not reported".
        assert _data_quality_blocks_position({"data_quality": "unknown"}) is False


class TestDataQualityConfidenceCap:
    def test_reported_degraded_caps_high_confidence(self):
        for dq in _DEGRADED:
            conf, reason = dg.cap_pm_confidence(0.95, dq)
            assert conf == pytest.approx(0.7)
            assert reason and dq in reason

    def test_omitted_quality_leaves_confidence(self):
        assert dg.cap_pm_confidence(0.95, None) == (0.95, None)
        assert dg.cap_pm_confidence(0.95, "fresh") == (0.95, None)


@pytest.fixture
def guardrail_on():
    set_config({"enable_decision_guardrail": True})
    yield
    reset_config()


def _pm_state(risk_factors):
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


def _pm_llm(**decision_kw):
    kw = {
        "rating": PortfolioRating.BUY,
        "executive_summary": "Synthesized view.",
        "investment_thesis": "Grounded in the risk debate.",
    }
    kw.update(decision_kw)
    decision = PortfolioDecision(**kw)
    structured = MagicMock()
    structured.invoke.return_value = decision
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


class TestDataQualityEndToEnd:
    def test_reported_stale_lowers_confidence(self, guardrail_on):
        # HIGH risk row + a positively reported stale slice: the guardrail
        # caps the rating AND the confidence, and marks the cap.
        state = _pm_state(
            [{"risk_id": "margin_compression", "severity": RiskSeverity.HIGH,
              "mitigation_stated": False}]
        )
        out = create_portfolio_manager(
            _pm_llm(data_quality="stale", confidence=0.95)
        )(state)
        pm = out["pm_decision"]
        assert pm["data_quality"] == "stale"
        assert pm["rating"] == "Hold"
        assert pm["confidence"] == pytest.approx(0.7)
        assert _data_quality_blocks_position(pm) is True

    def test_omitted_quality_does_not_block_or_cap(self, guardrail_on):
        # No risk row, no reported data quality: nothing degrades the call.
        state = _pm_state([])
        out = create_portfolio_manager(_pm_llm(confidence=0.95))(state)
        pm = out["pm_decision"]
        assert pm["data_quality"] is None
        assert pm["rating"] == "Buy"
        assert pm["confidence"] == pytest.approx(0.95)
        assert _data_quality_blocks_position(pm) is False


# ---------------------------------------------------------------------------
# 3. risk_cap is consumed by the renderer
# ---------------------------------------------------------------------------


class TestRiskCapConsumed:
    def test_rendered_decision_reflects_the_cap(self, guardrail_on):
        state = _pm_state(
            [{"risk_id": "margin_compression", "severity": RiskSeverity.HIGH,
              "mitigation_stated": False}]
        )
        out = create_portfolio_manager(_pm_llm())(state)
        assert out["pm_decision"]["risk_cap"] == "Hold"
        rendered = out["final_trade_decision"]
        assert rendered.startswith("**Rating**: Hold")
        assert "**Risk Cap**: Hold" in rendered

    def test_render_omits_cap_when_unset(self):
        md = render_pm_decision(
            PortfolioDecision(
                rating=PortfolioRating.BUY, executive_summary="s", investment_thesis="t"
            )
        )
        assert "Risk Cap" not in md


# ---------------------------------------------------------------------------
# 2. L1 vocabulary is single-sourced
# ---------------------------------------------------------------------------


class TestL1CanonicalVocabulary:
    def test_dead_verdict_mirror_is_gone(self):
        import tradingagents.agents.schemas as schemas

        for dead in (
            "L1Verdict",
            "L1DeterministicResult",
            "MetricVerification",
            "RiskGateEvaluation",
        ):
            assert not hasattr(schemas, dead), f"{dead} should have been deleted"

    def test_emitted_l1_dict_is_the_documented_contract(self):
        payload = DebaterTurnPayload(
            round_index=1,
            stance="BULL",
            core_thesis="Nothing quantitative to check.",
            quantitative_claims=[],
            recommended_allocation_pct=5.0,
        ).model_dump()
        l1_node = create_debate_l1({}, section="research")
        out = l1_node(
            {"debate_state": {"round_records": [{"bull": payload}], "last_side": "bull"}}
        )
        l1 = out["debate_state"][L1_KEY]

        # Same key set the deterministic classifier emits (one source).
        assert set(l1) == set(debate_score.classify_severity([])) | {"side"}
        assert l1["side"] == "bull"
        # The emitted strings are members of the canonical pydantic vocabulary.
        assert l1["severity_tier"] in {t.value for t in L1SeverityTier}
        assert l1["l1_action"] in {a.value for a in L1Action}
        ctx = L1ExecutionContext(
            severity_tier=l1["severity_tier"], l1_action=l1["l1_action"]
        )
        assert ctx.severity_tier.value == l1["severity_tier"]
        assert ctx.l1_action.value == l1["l1_action"]
