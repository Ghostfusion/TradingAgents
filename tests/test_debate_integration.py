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
)
from tradingagents.agents.utils.debate_structured import (
    invoke_structured_turn,
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

    def test_parse_markdown_fence_ignores_stray_brace_in_prose(self):
        """Deepseek rambles prose before the payload and the prose may hold a
        stray '{' — the greedy first-brace-to-last-brace span is not the
        payload, so the parser must recover the largest valid object."""
        text = 'The bull {see the table below} argues:\n{"a": 1}'
        assert json.loads(parse_markdown_fence(text)) == {"a": 1}

    def test_parse_markdown_fence_keeps_nested_payload_whole(self):
        """The largest accepted balanced block wins, so a payload is never
        truncated to one of its nested sub-objects."""
        text = 'prose {"outer": {"inner": 1}, "n": 2} trailing'
        assert json.loads(parse_markdown_fence(text)) == {"outer": {"inner": 1}, "n": 2}

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

    def test_invoke_structured_turn_uses_backup_on_structured_failure(self):
        """A structured call that raises (e.g. max_tokens cut) falls back to
        the BACKUP model, not the model that failed (TRADINGAGENTS_BACKUP_LLM)."""
        from unittest import mock

        structured_llm = mock.MagicMock()
        structured_llm.invoke.side_effect = RuntimeError("length limit was reached")
        plain_llm = mock.MagicMock()
        backup = mock.MagicMock()
        backup.invoke.return_value = mock.MagicMock(
            content='{"round_index": 1, "stance": "BULL", "core_thesis": "t", '
                    '"quantitative_claims": [], "recommended_allocation_pct": 5.0}'
        )
        m, err, mode = invoke_structured_turn(
            structured_llm, plain_llm, "prompt", DebaterTurnPayload, backup_llm=backup
        )
        assert m is not None, err
        assert m.round_index == 1
        backup.invoke.assert_called_once()
        plain_llm.invoke.assert_not_called()  # the failed model is never re-paid
        assert mode == "plain"  # the structured call failed -> fell back (D2 reliability flag)

    def test_invoke_structured_turn_uses_backup_on_repair(self):
        """When the fallback content does not parse, the bounded repair runs
        on the backup model."""
        from unittest import mock

        plain_llm = mock.MagicMock()
        plain_llm.invoke.return_value = mock.MagicMock(content="cut off mid-jso")
        backup = mock.MagicMock()
        backup.invoke.return_value = mock.MagicMock(
            content='{"round_index": 2, "stance": "BEAR", "core_thesis": "r", '
                    '"quantitative_claims": [], "recommended_allocation_pct": 2.0}'
        )
        # structured_llm None -> plain invoke is the PRIMARY attempt (stays on
        # plain_llm); the repair (a retry) swaps to the backup.
        m, err, mode = invoke_structured_turn(
            None, plain_llm, "prompt", DebaterTurnPayload, backup_llm=backup
        )
        assert m is not None, err
        assert m.stance == "BEAR"
        assert plain_llm.invoke.call_count == 1  # primary attempt only
        backup.invoke.assert_called_once()  # repair on the backup
        assert mode == "repair"

    def test_invoke_structured_turn_no_backup_keeps_same_model(self):
        """No backup configured -> the repair stays on the plain LLM (legacy)."""
        from unittest import mock

        plain_llm = mock.MagicMock()
        plain_llm.invoke.side_effect = [
            mock.MagicMock(content="cut off mid-jso"),
            mock.MagicMock(
                content='{"round_index": 1, "stance": "BULL", "core_thesis": "t", '
                        '"quantitative_claims": [], "recommended_allocation_pct": 5.0}'
            ),
        ]
        m, err, mode = invoke_structured_turn(None, plain_llm, "prompt", DebaterTurnPayload)
        assert m is not None, err
        assert plain_llm.invoke.call_count == 2  # primary + repair, same model
        assert mode == "repair"


class TestJudgeAnonymization:
    def test_rotate_flips_aliases(self):
        bull = {"core_thesis": "b", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 1.0}
        bear = {"core_thesis": "r", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 2.0}
        c0 = anonymize_and_rotate({"bull": bull, "bear": bear}, ("bull", "bear"), seed=0)
        c1 = anonymize_and_rotate({"bull": bull, "bear": bear}, ("bull", "bear"), seed=1)
        # Aliases always label the presentation slots; the ORDER of the
        # underlying theses is what rotates so the judge can't map an alias
        # back to bull/bear across runs.
        assert [c["alias"] for c in c0] == [c["alias"] for c in c1]
        assert [c["thesis"] for c in c0] == ["b", "r"]
        assert [c["thesis"] for c in c1] == ["r", "b"]

    def test_rotate_three_risk_roles(self):
        """Risk section has THREE candidates; aliases must cover all of them
        and the rotation must still hide which role is which."""
        turns = {
            "aggressive": {"core_thesis": "a", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 10.0},
            "conservative": {"core_thesis": "c", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 20.0},
            "neutral": {"core_thesis": "n", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 30.0},
        }
        roles = ("aggressive", "conservative", "neutral")
        c0 = anonymize_and_rotate(turns, roles, seed=0)
        c1 = anonymize_and_rotate(turns, roles, seed=1)
        assert [c["alias"] for c in c0] == ["Candidate_X", "Candidate_Y", "Candidate_Z"]
        assert sorted(t["thesis"] for t in c0) == ["a", "c", "n"]
        # rotation reverses the presentation order under seed=1
        assert [t["thesis"] for t in c0] == ["a", "c", "n"]
        assert [t["thesis"] for t in c1] == ["n", "c", "a"]

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


class TestRoleLlmWiring:
    def test_trading_graph_resolves_debate_llms_and_passes_to_setup(self, tmp_path, monkeypatch):
        """The debate_*_model config keys MUST drive the graph's SD nodes via
        resolve_role_llm — not the quick/deep defaults (regression: SD nodes
        were previously hardwired to quick_thinking_llm / deep_thinking_llm,
        making the keys no-ops)."""
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        seen = {}

        class _C:
            def __init__(self, provider, model, base_url=None, **kw):
                seen[f"{provider}:{model}"] = kw

            def get_llm(self):
                return type("L", (), {"invoke": lambda s, p: type("R", (), {"content": "x", "tool_calls": []})()})()

        monkeypatch.setattr(
            "tradingagents.graph.trading_graph.create_llm_client", _C
        )
        cfg = dict(DEFAULT_CONFIG)
        cfg["enable_debate"] = True
        cfg["debate_bull_model"] = "openrouter:openai/gpt-5.6-luna"
        cfg["debate_bear_model"] = "openrouter:z-ai/glm-5.3-flash"
        cfg["debate_judge_model"] = "openrouter:deepseek/deepseek-v4-flash-0731"
        ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
        assert seen, "resolve_role_llm never created per-role clients"
        assert "openrouter:openai/gpt-5.6-luna" in seen, f"bull key not used: {seen}"
        assert "openrouter:z-ai/glm-5.3-flash" in seen, f"bear key not used: {seen}"
        assert "openrouter:deepseek/deepseek-v4-flash-0731" in seen, f"judge key not used: {seen}"
        # The GraphSetup must receive them (SD nodes consume the role LLMs).
        assert ta.graph_setup.debate_llms.get("bull") is not None

    def test_debate_llms_not_resolved_when_disabled(self, tmp_path, monkeypatch):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        seen = {}

        class _C:
            def __init__(self, provider, model, **kw):
                seen[f"{provider}:{model}"] = True

            def get_llm(self):
                return type("L", (), {"invoke": lambda s, p: "x"})()

        monkeypatch.setattr("tradingagents.graph.trading_graph.create_llm_client", _C)
        cfg = dict(DEFAULT_CONFIG)
        cfg["enable_debate"] = False
        ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
        # Only the 2 base clients (quick/deep) + the optional backup client
        # (TRADINGAGENTS_BACKUP_LLM, when configured) are created; no debate
        # role clients.
        assert len(seen) <= 3, f"role clients created while disabled: {seen}"
        assert ta.graph_setup.debate_llms == {}


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

    def test_structured_debate_nodes_registered(self, monkeypatch):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        # Offline stub: graph construction must not depend on a live LLM
        # factory or an API key (the SD placeholders are registered regardless
        # of the flag). Any construction error is a real regression, not a
        # reason to skip.
        stub = type(
            "L",
            (),
            {
                "invoke": lambda s, p: type("R", (), {"content": "", "tool_calls": []})(),
                "bind_tools": lambda s, *a, **k: s,
            },
        )()
        monkeypatch.setattr(
            "tradingagents.graph.trading_graph.create_llm_client",
            lambda *a, **k: type("C", (), {"get_llm": lambda self: stub})(),
        )
        cfg = dict(DEFAULT_CONFIG)
        cfg["enable_debate"] = False
        # Building the graph with the flag OFF must keep the legacy chain and
        # register the SD nodes as no-op placeholders (targets always exist).
        ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
        nodes = set(ta.workflow.nodes)
        for n in ("SD Bull", "SD Bear", "SD L1", "SD Finalize"):
            assert n in nodes, f"missing node {n}"
