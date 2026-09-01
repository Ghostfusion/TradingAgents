"""Risk-section structured-debate parity (direction.md).

The risk debate must mirror the research debate: same structured debater
payloads, same L1 verification, the SAME judge, and the SAME depth knob.
Tests: model mapping (aggressive->BULL, conservative->BEAR, judge->JUDGE,
neutral->quick), section-aware router round-cycling for both sections, the
SD Risk subgraph edges in the compiled graph (on) vs the legacy risk chain
(off), the risk debater turn writing the structured channel + legacy prose
keys, and the judge-evidence block renderer.
"""

import pytest

from tradingagents.agents.researchers.structured_debate import (
    create_debate_l1,
    create_debater_turn,
    render_judge_evidence,
)
from tradingagents.graph.conditional_logic import ConditionalLogic


class TestRiskModelMapping:
    def test_aggressive_uses_bull_model_key(self):
        from tradingagents.agents.utils.debate_roles import role_model_spec

        cfg = {
            "debate_bull_model": "openrouter:openai/gpt-5.6-luna",
            "debate_bear_model": "openrouter:z-ai/glm-5.3-flash",
            "debate_judge_model": "openrouter:deepseek/deepseek-v4-flash-0731",
        }
        assert role_model_spec(cfg, "aggressive") == (
            "openrouter",
            "openai/gpt-5.6-luna",
        )
        assert role_model_spec(cfg, "conservative") == (
            "openrouter",
            "z-ai/glm-5.3-flash",
        )
        # Neutral has NO dedicated key -> fallback (quick tier).
        assert role_model_spec(cfg, "neutral") is None

    def test_resolve_risk_roles_uses_mapped_models(self):
        from tradingagents.agents.utils.debate_roles import resolve_role_llm

        cfg = {
            "debate_bull_model": "openrouter:openai/gpt-5.6-luna",
            "debate_bear_model": "openrouter:z-ai/glm-5.3-flash",
            "debate_judge_model": "openrouter:deepseek/deepseek-v4-flash-0731",
        }
        seen = {}

        class _C:
            def __init__(self, provider, model, **kw):
                seen[(provider, model)] = kw

            def get_llm(self):
                return type("L", (), {})()

        resolve_role_llm(cfg, "aggressive", factory=_C)
        resolve_role_llm(cfg, "conservative", factory=_C)
        resolve_role_llm(cfg, "neutral", factory=_C)
        assert ("openrouter", "openai/gpt-5.6-luna") in seen
        assert ("openrouter", "z-ai/glm-5.3-flash") in seen
        # Neutral resolves to the fallback tier (no dedicated key): the run's
        # provider + quick model — here empty provider/model from the minimal
        # cfg, i.e. a 4th client distinct from the two mapped debates.
        assert len(seen) == 3


class TestSectionRouter:
    def test_research_default_one_round(self):
        cl = ConditionalLogic()
        # One completed round (1 score entry) with cap=1 -> finalize.
        state = {"debate_state": {
            "last_side": "bear",
            "terminated": False,
            "score_series": [{"round": 1}],
        }}
        assert cl.should_continue_structured_debate(state) == "SD Finalize"

    def test_research_cycles_to_next_round_within_cap(self):
        cl = ConditionalLogic(max_debate_rounds=3)
        state = {"debate_state": {
            "last_side": "bear",
            "terminated": False,
            "score_series": [{"round": 1}, {"round": 2}],
        }}
        assert cl.should_continue_structured_debate(state) == "SD Bull"

    def test_research_cap_reached(self):
        cl = ConditionalLogic(max_debate_rounds=1)
        state = {"debate_state": {
            "last_side": "bear",
            "terminated": False,
            "score_series": [{"round": 1}],
        }}
        assert cl.should_continue_structured_debate(state) == "SD Finalize"

    def test_risk_role_order(self):
        cl = ConditionalLogic(max_debate_rounds=5)
        state = {"structured_risk_state": {"last_side": "aggressive"}}
        assert cl.should_continue_structured_debate(state, "risk") == (
            "SD Risk Conservative"
        )
        state["structured_risk_state"]["last_side"] = "conservative"
        assert cl.should_continue_structured_debate(state, "risk") == (
            "SD Risk Neutral"
        )

    def test_risk_round_complete_start_next(self):
        cl = ConditionalLogic(max_debate_rounds=2)
        state = {"structured_risk_state": {
            "last_side": "neutral",
            "terminated": False,
            "score_series": [{"round": 1}],
        }}
        assert cl.should_continue_structured_debate(state, "risk") == (
            "SD Risk Aggressive"
        )

    def test_risk_terminated_routes_finalize(self):
        cl = ConditionalLogic()
        state = {"structured_risk_state": {
            "last_side": "neutral", "terminated": True,
        }}
        assert cl.should_continue_structured_debate(state, "risk") == (
            "SD Risk Finalize"
        )

    def test_pending_regen_same_role_node(self):
        cl = ConditionalLogic()
        state = {"structured_risk_state": {
            "pending_regen_role": "conservative", "terminated": False,
        }}
        assert cl.should_continue_structured_debate(state, "risk") == (
            "SD Risk Conservative"
        )


class TestRiskTurnChannels:
    def test_risk_turn_writes_structured_channel_and_prose(self):
        class _L:
            def __init__(self, *a, **k):
                pass


        class _Payload:
            round_index = 1
            stance = "AGGRESSIVE"
            core_thesis = "upside case"
            quantitative_claims = []
            risk_factors = []
            recommended_allocation_pct = 30.0

        import tradingagents.agents.researchers.structured_debate as sd_mod

        def _fake_invoke(structured_llm, plain_llm, prompt, schema):
            return _Payload(), None

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sd_mod, "invoke_structured_turn", _fake_invoke)
        try:
            node = create_debater_turn(
                "aggressive", _L(), ground_truth=lambda s: {}, section="risk"
            )
            out = node({"structured_risk_state": {}, "risk_debate_state": {
                "history": "", "aggressive_history": "", "count": 0,
            }})
        finally:
            monkeypatch.undo()

        ds = out["structured_risk_state"]
        assert ds["last_side"] == "aggressive"
        assert ds["round_records"][0]["aggressive"].core_thesis == "upside case"
        prose = out["risk_debate_state"]
        assert "upside case" in prose["history"]
        assert "upside case" in prose["aggressive_history"]
        assert prose["count"] == 1


class TestDegradedTurnNeverCrashes:
    """Regression: the LLM returning NO structured payload must degrade to an
    honest empty turn, never raise. The pre-fix fallback constructed
    DebaterTurnPayload(quantitative_claims=[]) which violated min_length=1,
    raised ValidationError inside the node, and the unhandled exception
    wedged the whole run (moomoo non-daemon threads block interpreter
    shutdown -> flat CPU + CLOSE_WAIT hang)."""

    def test_research_bear_none_payload_survives(self):
        class _L:
            def __init__(self, *a, **k):
                pass

        import tradingagents.agents.researchers.structured_debate as sd_mod

        node = create_debater_turn(
            "bear", _L(), ground_truth=lambda s: {}, section="research"
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sd_mod, "invoke_structured_turn", lambda *a, **k: (None, "provider boom"))
        try:
            out = node({
                "debate_state": {"round_records": [{"bull": {"core_thesis": "b"}}]},
                "investment_debate_state": {"history": "bull prose", "count": 1},
            })
        finally:
            monkeypatch.undo()

        ds = out["debate_state"]
        last = ds["round_records"][-1]["bear"]
        assert "No structured turn produced" in last.core_thesis
        assert last.quantitative_claims == []
        inv = out["investment_debate_state"]
        assert "No structured turn produced" in inv["history"]
        assert inv["count"] == 2

    def test_risk_neutral_none_payload_survives(self):
        class _L:
            def __init__(self, *a, **k):
                pass

        import tradingagents.agents.researchers.structured_debate as sd_mod

        node = create_debater_turn(
            "neutral", _L(), ground_truth=lambda s: {}, section="risk"
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sd_mod, "invoke_structured_turn", lambda *a, **k: (None, "bad json"))
        try:
            out = node({
                "structured_risk_state": {},
                "risk_debate_state": {"history": "", "count": 0},
            })
        finally:
            monkeypatch.undo()

        assert out["structured_risk_state"]["round_records"][0]["neutral"].quantitative_claims == []
        assert "No structured turn produced" in out["risk_debate_state"]["history"]

    def test_round_index_capped_at_five(self):
        """The degraded fallback caps round_index at the schema's le=5."""
        class _L:
            def __init__(self, *a, **k):
                pass

        import tradingagents.agents.researchers.structured_debate as sd_mod

        node = create_debater_turn(
            "bull", _L(), ground_truth=lambda s: {}, section="research"
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sd_mod, "invoke_structured_turn", lambda *a, **k: (None, "x"))
        try:
            out = node({
                "debate_state": {
                    "round_records": [{"bull": {}}, {"bear": {}}, {"bull": {}}, {"bear": {}}, {"bull": {}}],
                },
                "investment_debate_state": {"history": "", "count": 4},
            })
        finally:
            monkeypatch.undo()

        assert out["debate_state"]["round_records"][-1]["bull"].round_index == 5

    def test_l1_risk_round_complete_triggers_scoring(self):
        from tradingagents.agents.schemas import (
            RiskDebaterTurnPayload,
        )

        class _L:
            def __init__(self, *a, **k):
                pass

        # L1 is pure deterministic; drive it with a completed risk round.
        payload = RiskDebaterTurnPayload(
            round_index=1,
            stance="NEUTRAL",
            core_thesis="balanced",
            quantitative_claims=[{
                "metric_name": "test",
                "asserted_value": 1.0,
                "ground_truth_key": "x",
                "source": "none",
            }],
            recommended_allocation_pct=20.0,
        )
        node = create_debate_l1(lambda s: {}, {}, section="risk")
        out = node({
            "structured_risk_state": {
                "round_records": [{"neutral": payload.model_dump()}],
                "last_side": "neutral",
            }
        })
        ds = out["structured_risk_state"]
        # Round complete (neutral = final risk role) -> score series recorded.
        assert ds.get("score_series"), "risk round must be scored"


class TestJudgeEvidenceBlock:
    def test_render_judge_evidence_empty(self):
        assert render_judge_evidence({}) == ""

    def test_render_judge_evidence_with_scores(self):
        ds = {
            "l1": {"severity_tier": "GREEN", "l1_action": "PROCEED", "side": "neutral"},
            "judge_scores": {
                "Candidate_X": {"mean": 6.5, "scores": {"empirical_grounding": 6.5}},
            },
        }
        block = render_judge_evidence(ds)
        assert "L1 verdict: GREEN" in block
        assert "Candidate_X: mean 6.5" in block

    def test_render_judge_evidence_no_judge_but_l1(self):
        block = render_judge_evidence({"l1": {"severity_tier": "RETRYABLE_ERROR"}})
        assert "RETRYABLE_ERROR" in block


class TestRiskGraphWiring:
    def _build(self, monkeypatch, enable_debate):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        class _L:
            def __init__(self, *a, **k):
                pass

            def get_llm(self):
                return _L()

            def invoke(self, *a, **k):
                return type("R", (), {"content": "x", "tool_calls": []})()

        monkeypatch.setattr(
            "tradingagents.graph.trading_graph.create_llm_client", _L
        )
        cfg = dict(DEFAULT_CONFIG)
        cfg["enable_debate"] = enable_debate
        ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
        # TradingAgentsGraph exposes the compiled graph as .graph
        assert ta.graph is not None
        return ta

    def _edges(self, ta):
        return {
            (getattr(e, "source", None), getattr(e, "target", None))
            for e in ta.graph.get_graph().edges
        }

    def test_structured_risk_edges_present(self, monkeypatch):
        ta = self._build(monkeypatch, True)
        edges = self._edges(ta)
        assert ("Independent Risk Stances", "SD Risk Aggressive") in edges
        for role in ("SD Risk Aggressive", "SD Risk Conservative", "SD Risk Neutral"):
            assert (role, "SD Risk L1") in edges
        assert ("SD Risk Finalize", "Portfolio Manager") in edges

    def test_legacy_risk_chain_when_off(self, monkeypatch):
        ta = self._build(monkeypatch, False)
        edges = self._edges(ta)
        assert ("Independent Risk Stances", "Aggressive Analyst") in edges
        # legacy loop targets the risk debators + PM
        assert any(
            s == "Aggressive Analyst" or s == "Conservative Analyst"
            for s, _ in edges
        )
        assert ("Portfolio Manager", "__end__") in edges
        # structured risk nodes must NOT be reached from stances
        assert ("Independent Risk Stances", "SD Risk Aggressive") not in edges

    def test_research_edges_still_present_when_on(self, monkeypatch):
        ta = self._build(monkeypatch, True)
        edges = self._edges(ta)
        assert ("Independent Researcher Stances", "SD Bull") in edges
        assert ("SD Finalize", "Research Manager") in edges


class TestDepthParity:
    def test_build_run_config_research_depth_drives_both(self, monkeypatch):
        """TRADINGAGENTS_RESEARCH_DEPTH sets BOTH round counts (direction item 1)."""
        monkeypatch.setenv("TRADINGAGENTS_RESEARCH_DEPTH", "3")
        monkeypatch.delenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", raising=False)
        monkeypatch.delenv("TRADINGAGENTS_MAX_RISK_ROUNDS", raising=False)

        import importlib

        import cli.main as main_mod

        # _build_run_config needs selections dict + config template

        importlib.reload(main_mod)
        cfg = main_mod._build_run_config(
            {
                "research_depth": 5,  # interactive/SYMBOL choice is IGNORED when env set
                "shallow_thinker": "q",
                "deep_thinker": "d",
                "backend_url": "",
                "llm_provider": "openai",
                "output_language": "English",
            },
            checkpoint=None,
        )
        # research_depth mirrors DEFAULT_CONFIG (the env is read back into it at
        # module import); the ROUND COUNTS are what the knob must drive.
        assert cfg["max_risk_discuss_rounds"] == 3
        assert cfg["max_debate_rounds"] == 3
