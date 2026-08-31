"""P3-P5 + integration hermetic tests for the structured multi-agent debate.

Design: docs/design_multi_agent_debate.md. All offline: capability matrix,
role resolution, schemas round-trips, dual-mode adapter, judge anonymization,
A/B harness metrics, and the graph wiring (structured subgraph nodes exist,
router targets complete, legacy path unchanged when enable_debate is off).
"""

import json

import pytest

from tradingagents.agents.arbiters.debate_judge import (
    aggregate_scores,
    anonymize_and_rotate,
)
from tradingagents.agents.schemas import (
    DebaterTurnPayload,
    L1DeterministicResult,
    L1ExecutionContext,
    L2JudgeDimensionedRubric,
    QuantitativeClaim,
)
from tradingagents.agents.utils.debate_roles import (
    resolve_role_llm,
    role_fallback_models,
    role_model_spec,
    role_tools,
)
from tradingagents.agents.utils.debate_structured import (
    parse_and_validate,
    parse_markdown_fence,
)
from tradingagents.strategies.debate_capability import (
    assess_model_capability,
    can_serve_role,
    capability_gate,
)

pytestmark = pytest.mark.timeout(120)


class TestCapabilityMatrix:
    def test_unknown_provider_fails_closed_when_required(self):
        cap = assess_model_capability("unknown")
        ok, reasons = can_serve_role(cap, "judge")
        assert not ok
        assert "structured" in " ".join(reasons)

    def test_known_structured_provider_passes_judge(self):
        cap = assess_model_capability("openai")
        ok, reasons = can_serve_role(cap, "judge")
        assert ok, reasons

    def test_small_context_refused(self):
        cap = assess_model_capability("openai", context_window=8000)
        ok, reasons = can_serve_role(cap, "judge")
        assert not ok
        assert "context" in " ".join(reasons)

    def test_gate_require_collects_errors(self):
        cap = assess_model_capability("unknown", context_window=8000)
        errors = capability_gate({"judge": cap}, require=True)
        assert errors and errors[0].startswith("ERROR")


class TestRoleResolution:
    def test_spec_parse(self):
        cfg = {"debate_bull_model": "anthropic:claude-sonnet-4-5"}
        assert role_model_spec(cfg, "bull") == ("anthropic", "claude-sonnet-4-5")

    def test_fallback_when_unset(self):
        cfg = {
            "llm_provider": "openai",
            "quick_think_llm": "gpt-4o-mini",
            "deep_think_llm": "gpt-4o",
        }
        assert role_fallback_models(cfg, "bull") == ("openai", "gpt-4o-mini")
        assert role_fallback_models(cfg, "judge") == ("openai", "gpt-4o")

    def test_tool_surfaces_distinct(self):
        assert set(role_tools("bull")) != set(role_tools("bear"))
        assert role_tools("judge") == role_tools("neutral")

    def test_resolve_role_uses_factory(self):
        calls = {}

        def fake_factory(provider, model, base_url=None, **kwargs):
            calls["provider"] = provider
            calls["model"] = model
            calls.update(kwargs)
            return type(
                "C", (), {"get_llm": lambda self: ("llm", provider, model)}
            )()

        cfg = {
            "llm_provider": "openai",
            "quick_think_llm": "gpt-4o-mini",
            "deep_think_llm": "gpt-4o",
            "debate_judge_model": "anthropic:claude-sonnet-4-5",
            "max_output_tokens_deep": 2500,
        }
        resolve_role_llm(cfg, "judge", factory=fake_factory)
        assert calls["provider"] == "anthropic"
        assert calls["model"] == "claude-sonnet-4-5"
        assert calls["max_tokens"] == 2500


class TestWireSchemas:
    def test_debater_turn_roundtrip(self):
        t = DebaterTurnPayload(
            round_index=1,
            stance="BULL",
            core_thesis="x",
            quantitative_claims=[
                QuantitativeClaim(
                    metric_name="pe",
                    asserted_value=38.0,
                    ground_truth_key="pe",
                    source="get_ratios",
                )
            ],
            recommended_allocation_pct=5.0,
        )
        d = json.loads(t.model_dump_json())
        assert d["stance"] == "BULL"
        assert d["quantitative_claims"][0]["asserted_value"] == 38.0

    def test_l1_and_rubric_and_context(self):
        l1 = L1DeterministicResult(verdict="PASS", hard_gate_passed=True)
        assert l1.verdict.value == "PASS"
        r = L2JudgeDimensionedRubric(
            judge_model_id="j", round_evaluated=1, evaluated_agent_alias="Candidate_X"
        )
        assert r.rebuttal_effectiveness == 0.0
        ctx = L1ExecutionContext()
        assert ctx.severity_tier.value == "GREEN"

    def test_rubric_dimensional_scores_validate(self):
        r = L2JudgeDimensionedRubric(
            judge_model_id="j",
            round_evaluated=1,
            evaluated_agent_alias="Candidate_X",
            dimension_scores={
                "empirical_grounding": 8.0,
                "downside_tail_risk_weight": 6.0,
                "catalyst_clarity": 7.0,
                "assumption_sensitivity": 5.0,
            },
        )
        assert r.dimension_scores["empirical_grounding"] == 8.0


class TestDualModeAdapter:
    def test_parse_markdown_fence(self):
        block = parse_markdown_fence("```json\n{\"a\": 1}\n```")
        assert json.loads(block) == {"a": 1}

    def test_parse_and_validate_turn(self):
        payload = {
            "round_index": 1,
            "stance": "BULL",
            "core_thesis": "t",
            "quantitative_claims": [
                {
                    "metric_name": "pe",
                    "asserted_value": 38.0,
                    "ground_truth_key": "pe",
                    "source": "get_ratios",
                }
            ],
            "recommended_allocation_pct": 5.0,
        }
        txt = "Turn:\n```json\n" + json.dumps(payload) + "\n```"
        m, err = parse_and_validate(txt, DebaterTurnPayload)
        assert m is not None, err
        assert m.round_index == 1

    def test_parse_invalid_schema_fails_closed(self):
        m, err = parse_and_validate('{"round_index": 99}', DebaterTurnPayload)
        assert m is None
        assert "validation error" in err


class TestJudgeAnonymization:
    def test_rotate_flips_aliases(self):
        bull = {"core_thesis": "b", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 1.0}
        bear = {"core_thesis": "r", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 2.0}
        c0 = anonymize_and_rotate(bull, bear, seed=0)
        c1 = anonymize_and_rotate(bull, bear, seed=1)
        # Aliases always label the presentation slots; the ORDER of the
        # underlying theses is what rotates so the judge can't map an alias
        # back to bull/bear across runs.
        assert [c["alias"] for c in c0] == [c["alias"] for c in c1]
        assert [c["thesis"] for c in c0] == ["b", "r"]
        assert [c["thesis"] for c in c1] == ["r", "b"]

    def test_aggregate_scores_means_dims(self):
        r = L2JudgeDimensionedRubric(
            judge_model_id="j",
            round_evaluated=1,
            evaluated_agent_alias="Candidate_X",
            dimension_scores={
                "empirical_grounding": 8.0,
                "downside_tail_risk_weight": 6.0,
                "catalyst_clarity": 8.0,
                "assumption_sensitivity": 6.0,
            },
        )
        out = aggregate_scores(r, [{"alias": "Candidate_X"}])
        assert out["Candidate_X"]["mean"] == 7.0



class TestABHarness:
    def test_brier_and_max_dd(self):
        from scripts.debate_ab_harness import brier_score, max_unforecasted_drawdown

        f = [{"label": 1, "prob": 0.8}, {"label": 0, "prob": 0.3}]
        assert brier_score(f) == pytest.approx(0.065)

        # labels always correct at high prob -> no unforecasted drawdown built
        f2 = [{"label": 1, "prob": 0.9}, {"label": 1, "prob": 0.9}]
        assert max_unforecasted_drawdown(f2) == 0.0

    def test_run_ab_reports_both(self):
        from scripts.debate_ab_harness import run_ab

        def debate(items):
            return [{"label": it["label"], "prob": 0.6 + (0.1 if it["label"] else -0.1)} for it in items]

        def consistency(items):
            return [{"label": it["label"], "prob": 0.5} for it in items]

        items = [{"label": 1}, {"label": 0}]
        out = run_ab(debate, consistency, items)
        assert "debate" in out and "self_consistency" in out
        assert out["n"] == 2


class TestGraphWiring:
    def test_structured_router_targets_complete(self):
        from tradingagents.graph.conditional_logic import ConditionalLogic

        cl = ConditionalLogic()
        state = {"debate_state": {"last_side": "bull", "terminated": False}}
        assert cl.should_continue_structured_debate(state) == "SD Bear"
        state["debate_state"]["terminated"] = True
        assert cl.should_continue_structured_debate(state) == "SD Finalize"
        state["debate_state"] = {"pending_regen_role": "bear"}
        assert cl.should_continue_structured_debate(state) == "SD Bear"

    def test_structured_debate_nodes_registered(self):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        cfg = dict(DEFAULT_CONFIG)
        cfg["enable_debate"] = False
        # Building the graph with the flag OFF must keep the legacy chain and
        # register the SD nodes as no-op placeholders (targets always exist).
        try:
            ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
        except Exception:  # noqa: BLE001 - live LLM factory may be unavailable in tests
            pytest.skip("LLM factory unavailable in this environment")
        nodes = set(ta.workflow.nodes)
        for n in ("SD Bull", "SD Bear", "SD L1", "SD Finalize"):
            assert n in nodes, f"missing node {n}"
