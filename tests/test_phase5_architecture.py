"""Phase 5: composite bundles + typed state + falsification schema + factor
bridge (W4-1/2/3/4)."""

import pytest

from tradingagents.strategies.domain_bundles import (
    _quality_of,
    news_relevance_profile,
)
from tradingagents.strategies.falsification import (
    FalsificationCondition,
    evaluate_debate_claims,
)
from tradingagents.strategies.typed_state import (
    AnalystSummary,
    Decision,
    RiskVerdict,
    TradeProposal,
    summarize_report,
)

pytestmark = pytest.mark.timeout(30)


class TestBundles:
    def test_quality_mix(self):
        assert _quality_of("fresh", "fresh") == "fresh"
        assert _quality_of("fresh", "stale") == "stale"
        assert _quality_of("fresh", "partial") == "partial"
        assert _quality_of("unknown") == "unknown"
        assert _quality_of("unknown", "fresh") == "partial"  # at least one measured
        assert _quality_of("unknown", "unknown") == "unknown"

    def test_news_relevance_profile(self):
        p = news_relevance_profile("MSFT beats on cloud", ticker="MSFT",
                                   source_url="https://www.sec.gov/x", company_name="Microsoft")
        assert p["score"] >= 55 and p["admitted"] is True and p["official"] is True


class TestJudgeGrounding:
    def test_rejects_unverified_metric(self):
        bull = [FalsificationCondition("gross_margin", "<", 45.0)]
        v = evaluate_debate_claims(bull, [], {})  # metric not in computed set
        assert any("unverified metric" in i for i in v["issues"])
        assert v["verdict"] == "PROCEED_TO_SCORING"  # not an invalidation, just a citation

    def test_rejects_already_invalidated_thesis(self):
        bull = [FalsificationCondition("gross_margin", "<", 45.0)]
        v = evaluate_debate_claims(bull, [], {"gross_margin": 40.0})  # already breaches
        assert v["verdict"] == "REJECT_INVALIDATED_THESIS"
        assert any("ALREADY invalidated" in i for i in v["issues"])

    def test_passes_when_grounded_and_unbreached(self):
        bull = [FalsificationCondition("gross_margin", "<", 45.0)]
        bear = [FalsificationCondition("ev_to_ebitda", ">", 30.0)]
        v = evaluate_debate_claims(bull, bear, {"gross_margin": 50.0, "ev_to_ebitda": 20.0})
        assert v["verdict"] == "PROCEED_TO_SCORING" and not v["issues"]

    def test_unfalsifiable_side_flagged(self):
        v = evaluate_debate_claims([], [], {})
        assert any("no falsification conditions" in i for i in v["issues"])


class TestTypedState:
    def test_compact_drops_raw_text(self):
        a = AnalystSummary(role="market", conclusion="up",
                           computed_levels={"rsi": 61}, data_quality="fresh",
                           raw_tool_dump=True)
        c = a.to_compact()
        assert "computed_levels" in c and c["data_quality"] == "fresh"
        assert "conclusion" in c  # head only
        assert len(c["conclusion"]) <= 2000

    def test_artifacts_roundtrip(self):
        d = Decision(rating="Underweight", invalidation_conditions=["stop"])
        assert d.to_compact()["rating"] == "Underweight"
        r = RiskVerdict(verdict="REJECT", reasons=["x"], risk_halt=True)
        assert r.to_compact()["risk_halt"] is True
        t = TradeProposal(direction="long", entry=100.0, stop=95.0, targets=[110])
        assert t.to_compact()["entry"] == 100.0 and t.to_compact()["stop"] == 95.0

    def test_summarize_report(self):
        s = summarize_report("First line\nSecond line\n", "news", {"x": 1})
        assert s.conclusion == "First line" and s.computed_levels == {"x": 1}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
