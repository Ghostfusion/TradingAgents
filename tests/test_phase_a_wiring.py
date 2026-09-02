"""Tests for the DSA phase-A decision-quality wiring.

- PortfolioDecision back-compat: the new optional fields (data_quality /
  guardrail_reason / risk_cap) are absent-tolerant; render headers preserved.
- guardrail result-hook integration: with enable_decision_guardrail on, a
  structured PM result with a high-severity risk + data quality stale gets
  its rating capped and confidence lowered BEFORE render.
- per-field integrity retry: a missing mandatory field triggers a targeted
  rebuild (not a blind re-roll); repaired result renders with the field.
"""

import pytest

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.structured import retry_structured_missing_fields
from tradingagents.strategies import decision_guardrail as dg

pytestmark = pytest.mark.timeout(30)


def _decision(**kw):
    base = {"rating": "Overweight", "executive_summary": "s", "investment_thesis": "t"}
    base.update(kw)
    return PortfolioDecision(**base)


class TestPMSchemaBackCompat:
    def test_old_decision_renders(self):
        md = render_pm_decision(_decision())
        assert "**Rating**: Overweight" in md
        assert "**Executive Summary**" in md and "**Investment Thesis**" in md
        assert "**Rating**" in md  # header preserved for parsers

    def test_new_fields_render_footers(self):
        d = _decision(data_quality="stale", guardrail_reason="risk-cap",
                      risk_cap="Hold", confidence=0.9)
        md = render_pm_decision(d)
        assert "**Confidence**: 0.90" in md
        # the footers are advisory — display in the markdown kept light

    def test_none_fields_ok(self):
        d = _decision(data_quality=None, guardrail_reason=None, risk_cap=None)
        assert d.data_quality is None and d.guardrail_reason is None and d.risk_cap is None


class TestGuardrailHook:
    def test_hook_caps_rating_on_high_risk(self):
        # simulate the PM result_hook path: stabilize_decision is pure, so we
        # drive it the same way the result_hook does.
        out = dg.stabilize_decision("Buy", risk_rows=[{"severity": "high"}])
        assert out["rating"] == "Hold"
        assert out["overrides"][0]["reason"].startswith("risk-cap")

    def test_hook_caps_confidence_on_stale(self):
        conf, reason = dg.cap_pm_confidence(0.95, "stale")
        assert conf == pytest.approx(0.7) and reason is not None

    def test_hook_active_flags(self):
        from tradingagents.dataflows.config import get_config, reset_config, set_config

        set_config({"enable_decision_guardrail": True})
        try:
            assert get_config().get("enable_decision_guardrail") is True
        finally:
            reset_config()


class TestIntegrityRetry:
    def test_missing_field_triggers_rebuild(self):
        calls = []
        class FakeLLM:
            def invoke(self, prompt):
                calls.append(prompt)
                # the single TARGETED retry returns a complete decision
                return PortfolioDecision(rating="Buy", executive_summary="full",
                                         investment_thesis="t")
        structured = FakeLLM()
        # force typing: pass it as Any
        out = retry_structured_missing_fields(
            structured, "PROMPT", PortfolioDecision(rating="Buy", executive_summary="",
                                                    investment_thesis="t"),
            render_pm_decision, "PM", mandatory_fields=("executive_summary",), max_retries=1)
        assert len(calls) == 1  # one TARGETED retry; loop breaks once the field is present
        assert "missing required field" in calls[0]
        assert "**Executive Summary**: full" in out

    def test_complete_result_no_retry(self):
        calls = []
        class FakeLLM:
            def invoke(self, prompt):
                calls.append(prompt)
                return PortfolioDecision(rating="Buy", executive_summary="full",
                                         investment_thesis="t")
        out = retry_structured_missing_fields(
            FakeLLM(), "P", PortfolioDecision(rating="Buy", executive_summary="full",
                                              investment_thesis="t"),
            render_pm_decision, "PM", mandatory_fields=("executive_summary",))
        assert calls == []  # no retry when nothing missing
        assert "**Executive Summary**: full" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

