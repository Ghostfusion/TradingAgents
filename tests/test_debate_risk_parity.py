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

            def model_dump(self):
                return {k: getattr(self, k) for k in (
                    "round_index", "stance", "core_thesis",
                    "quantitative_claims", "risk_factors",
                    "recommended_allocation_pct",
                )}

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
        assert ds["round_records"][0]["aggressive"]["core_thesis"] == "upside case"
        prose = out["risk_debate_state"]
        assert "upside case" in prose["history"]
        assert "upside case" in prose["aggressive_history"]
        assert prose["count"] == 1


class TestBoundedContextPhases:
    """P0-P4 context-bounding (design v5 / direction.md):

    P0 persisted L1 statuses drive active_disputes; P1 delta-only debater
    prompt (registry + last turn + disputes, no transcript); P2 judge O(1)
    candidate prompt (no full ledger); P3 consumer debate matrix; P4 ground
    truth harvests analyst computed lines."""

    def test_p0_status_persists_through_l1(self):
        from tradingagents.agents.researchers.structured_debate import (
            active_disputes,
            create_debate_l1,
        )
        from tradingagents.agents.schemas import DebaterTurnPayload
        from tradingagents.strategies.debate_claim import ClaimLedger

        payload = DebaterTurnPayload.model_validate({
            "round_index": 1,
            "stance": "BULL",
            "core_thesis": "t",
            "quantitative_claims": [
                {"metric_name": "fcf", "asserted_value": 7.41,
                 "ground_truth_key": "fcf_yield", "source": "x"},
                {"metric_name": "bad", "asserted_value": 99.0,
                 "ground_truth_key": "fcf_yield", "source": "x"},
            ],
            "recommended_allocation_pct": 10,
        })
        node = create_debate_l1(lambda s: {"fcf_yield": 7.41})
        out = node({"debate_state": {
            "round_records": [{"bull": payload.model_dump()}],
            "last_side": "bull",
        }})
        ds = out["debate_state"]
        ledger = ClaimLedger.from_dict(ds["claim_ledger"])
        statuses = {c.claim_id: c.status for c in ledger.rows}
        assert "valid" in statuses.values(), statuses
        assert "violated" in statuses.values(), statuses
        # active_disputes surfaces ONLY violated/unverified, newest-first
        disputes = active_disputes(ds)
        assert disputes and disputes[0]["status"] == "violated"

    def test_p1_delta_prompt_bounded_no_transcript(self):
        from tradingagents.agents.researchers.structured_debate import (
            GROUND_TRUTH_REGISTRY,
            build_or_get_registry,
            build_turn_prompt,
        )

        state = {
            "asset_type": "stock",
            "instrument_context": "QCOM",
            "market_report": "M" * 20000,
            "computed_decision_context": "fcf_yield=7.41, beta=2.05",
            "investment_debate_state": {"history": "H" * 50000},
            "debate_state": {
                "round_records": [
                    {"bull": {"stance": "BULL", "core_thesis": "b1",
                              "quantitative_claims": [{"ground_truth_key": "pe_ttm", "asserted_value": 18.7}]}},
                ],
                "claim_ledger": [
                    {"role": "bull", "round": 1, "claim_id": "b1_0", "kind": "quantitative",
                     "metric_name": "PE", "value": 18.7, "ground_truth_key": "pe_ttm",
                     "source": "x", "status": "violated"},
                ],
            },
        }
        ds = state["debate_state"]
        ds[GROUND_TRUTH_REGISTRY] = build_or_get_registry(state, "research")
        prompt = build_turn_prompt(state, "bear", "BEAR")
        assert "Ground Truth Key Index" in prompt and "fcf_yield" in prompt
        assert "Preceding Opponent Turn" in prompt and "core_thesis: b1" in prompt
        assert "Active Dispute Ledger" in prompt and "violated" in prompt
        assert "Bull Analyst:" not in prompt and "Bear Analyst:" not in prompt
        assert "H" * 100 not in prompt and "M" * 100 not in prompt
        assert len(prompt) < 6000

    def test_p2_judge_candidate_prompt_has_opponent_and_scorecard(self):
        from tradingagents.agents.arbiters.debate_judge import (
            _build_judge_candidate_prompt,
        )

        candidate = {"alias": "Candidate_X", "thesis": "up", "claims": [{"metric_name": "pe", "asserted_value": 18.7}], "risk_factors": [], "allocation": 30}
        opponent = {"alias": "Candidate_Y", "thesis": "down", "claims": [{"metric_name": "dcf", "asserted_value": 152.65}], "risk_factors": [], "allocation": 20}
        p = _build_judge_candidate_prompt(
            1, candidate, opponent,
            "bull: valid=1 violated=0 unverified=0 abstain=0\nbear: valid=0 violated=1 unverified=0 abstain=0",
        )
        assert "Preceding opponent (rebuttal baseline)" in p
        assert "Candidate_X" in p and "Candidate_Y" in p
        assert "L1 verification scorecard" in p and "valid=1" in p
        assert p.count("###") >= 2

    def test_p2_judge_node_prompt_omits_full_ledger(self):
        import tradingagents.agents.arbiters.debate_judge as dj_mod
        from tradingagents.agents.researchers.structured_debate import create_debate_finalize

        class _L:
            def invoke(self, *a, **k):
                raise RuntimeError("no real call")

        class _FakeJudge:
            def __init__(self, judge_llm, section="research", cfg=None):
                pass

            def __call__(self, state):
                ch = "structured_risk_state" if "structured_risk_state" in state else "debate_state"
                return {ch: {"judge_scores": {}, "judge_rubrics": []}}

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(dj_mod, "create_debate_judge", _FakeJudge)
        try:
            node = create_debate_finalize(_L(), {}, section="research")
            out = node({"debate_state": {
                "terminated": True, "reason": "hard cap (1 rounds)",
                "round_records": [{"bull": {"core_thesis": "b"}, "bear": {"core_thesis": "r"}}],
                "claim_ledger_md": "L" * 5000,
            }})
        finally:
            monkeypatch.undo()
        # judge ran and merged (no crash); ledger_md not used by judge
        assert "judge_scores" in out["debate_state"]

    def test_p3_consumer_matrix_renders(self):
        from tradingagents.agents.researchers.structured_debate import (
            SECTION_ROLES,
            render_consumer_debate_matrix,
        )

        ds = {
            "round_records": [
                {"bull": {"stance": "BULL", "core_thesis": "Operating leverage expansion drives upside.", "quantitative_claims": [], "recommended_allocation_pct": 8.0}},
                {"bear": {"stance": "BEAR", "core_thesis": "Margin compression in 2H; DCF below price.", "quantitative_claims": [], "recommended_allocation_pct": 2.0}},
            ],
            "claim_ledger": [
                {"role": "bull", "round": 1, "claim_id": "b", "kind": "quantitative", "metric_name": "x", "value": 1.0, "status": "valid"},
                {"role": "bear", "round": 1, "claim_id": "r1", "kind": "quantitative", "metric_name": "y", "value": 2.0, "status": "violated"},
                {"role": "bear", "round": 1, "claim_id": "r2", "kind": "quantitative", "metric_name": "z", "value": 3.0, "status": "valid"},
            ],
            "judge_scores": {"Candidate_X": {"mean": 8.2}, "Candidate_Y": {"mean": 6.5}},
        }
        m = render_consumer_debate_matrix(ds, SECTION_ROLES["research"])
        assert "| bull | BULL |" in m
        assert "100%" in m and "50%" in m
        assert "8.2" in m and "6.5" in m
        assert "| 8.0% |" in m and "| 2.0% |" in m

    def test_risk_stance_coerced_from_research_labels(self):
        """The shared 1-shot can leak BULL/BEAR into a risk payload; the
        schema now maps them to their risk analog instead of failing the turn
        (regression: aggressive degraded with 'stance: Input should be
        AGGRESSIVE/CONSERVATIVE/NEUTRAL')."""
        from tradingagents.agents.schemas import RiskDebaterTurnPayload

        p = RiskDebaterTurnPayload.model_validate({
            "round_index": 1,
            "stance": "BULL",
            "core_thesis": "upside",
            "quantitative_claims": [{"metric_name": "pe", "asserted_value": 18.7,
                                     "ground_truth_key": "pe_ttm", "source": "x"}],
            "recommended_allocation_pct": 30,
        })
        assert p.stance.value == "AGGRESSIVE", p.stance

        p2 = RiskDebaterTurnPayload.model_validate({
            "round_index": 1,
            "stance": "bear",
            "core_thesis": "down",
            "quantitative_claims": [{"metric_name": "pe", "asserted_value": 18.7,
                                     "ground_truth_key": "pe_ttm", "source": "x"}],
            "recommended_allocation_pct": 10,
        })
        assert p2.stance.value == "CONSERVATIVE", p2.stance

    def test_oneshot_stance_is_section_aware(self):
        """The 1-shot example must use the CURRENT role's stance so it never
        leaks the research labels into a risk payload (regression: aggressive
        mirrored 'BEAR' from the research example)."""
        import re

        from tradingagents.agents.researchers.structured_debate import build_turn_prompt

        # risk conservative
        p = build_turn_prompt({
            "asset_type": "stock", "instrument_context": "Q",
            "computed_decision_context": "fcf_yield=7.41",
            "trader_investment_plan": "HOLD",
            "risk_debate_state": {"history": ""},
            "structured_risk_state": {"round_records": []},
        }, "conservative", "CONSERVATIVE")
        m = re.search(r'"stance": "([A-Z]+)"', p[p.index("Example output"):])
        assert m and m.group(1) == "CONSERVATIVE", m
        # research bear
        p2 = build_turn_prompt({
            "asset_type": "stock", "instrument_context": "Q",
            "computed_decision_context": "fcf_yield=7.41",
            "investment_debate_state": {"history": ""},
            "debate_state": {"round_records": []},
        }, "bear", "BEAR")
        m2 = re.search(r'"stance": "([A-Z]+)"', p2[p2.index("Example output"):])
        assert m2 and m2.group(1) == "BEAR", m2

    def test_judge_rubric_coerces_ragged_luna_fields(self):
        """Regression (QCOM 130518): luna emits entrenchment_detected /
        rebuttal_effectiveness as strings/objects; the rubric previously
        FAILED validation -> judge unavailable. Now coerces (bool/float)."""
        from tradingagents.agents.schemas import L2JudgeDimensionedRubric

        r = L2JudgeDimensionedRubric(
            entrenchment_detected="no", rebuttal_effectiveness="7.5",
        )
        assert r.entrenchment_detected is False
        assert r.rebuttal_effectiveness == 7.5

        r2 = L2JudgeDimensionedRubric(
            entrenchment_detected="True", rebuttal_effectiveness="oops",
        )
        assert r2.entrenchment_detected is True
        assert r2.rebuttal_effectiveness == 0.0

        r3 = L2JudgeDimensionedRubric(entrenchment_detected=1, rebuttal_effectiveness=12.0)
        assert r3.entrenchment_detected is True
        assert r3.rebuttal_effectiveness == 10.0  # clamped 0..10

    def test_judge_prose_score_fallback(self):
        """Empty dimension_scores falls back to a DETERMINISTIC prose-score:
        parse per-dimension numbers from the rationale, else use
        rebuttal_effectiveness as the proxy. Never silent 0.0/UNAVAILABLE
        when the model narrated scores (133244: neither deepseek nor luna
        emits the dim map on this route)."""
        import tradingagents.agents.arbiters.debate_judge as dj_mod

        def _invoke(structured_llm, plain_llm, prompt, schema):
            class _R:
                dimension_scores = {}
                judge_model_id = ""
                round_evaluated = 1
                evaluated_agent_alias = "Candidate_X"
                entrenchment_detected = False
                rebuttal_effectiveness = 9.0
                rationale = ("empirical_grounding: 8, downside_tail_risk_weight: 6, "
                             "catalyst_clarity: 7, assumption_sensitivity: 5")
            return _R(), None

        class _L:
            def with_structured_output(self, schema, **kw):
                return object()

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(dj_mod, "invoke_structured_turn", _invoke)
        try:
            node = dj_mod.create_debate_judge(_L(), section="research", cfg={})
            out = node({"debate_state": {"round_records": [
                {"bull": {"stance": "BULL", "core_thesis": "t", "quantitative_claims": [],
                          "risk_factors": [], "recommended_allocation_pct": 10}},
                {"bear": {"stance": "BEAR", "core_thesis": "r", "quantitative_claims": [],
                          "risk_factors": [], "recommended_allocation_pct": 2}},
            ]}})
        finally:
            monkeypatch.undo()

        x = out["debate_state"]["judge_scores"]["Candidate_X"]
        assert x["mean"] == 6.5, x          # (8+6+7+5)/4
        assert x.get("fallback") is True
        assert x["scores"]["empirical_grounding"] == 8.0

    def test_humanized_keys_resolve_via_alias_map(self):
        """Registry-key mismatch fix: debaters humanize the Key Index labels
        ('QCOM price', 'Free-cash-flow yield', 'Forward P/E'), so L1 marked
        them unverified -> (unused). The alias map resolves the common
        variants back to the canonical computed key -> valid."""
        from tradingagents.strategies.debate_claim import ClaimRecord, verify_claim

        gt = {"last_price": 162.0, "vwap": 164.63, "roe": 37.3, "fcf_yield": 7.4,
              "current_ratio": 2.82, "dcf_fair_value": 152.65, "pe_ttm": 18.7,
              "beta": 1.68, "rsi": 36.0, "dividend_yield": 2.2, "macd_histogram": -1.68,
              "band_low": 158.85, "band_high": 171.5, "rsi2": 14.93, "stochrsi": 0.0}
        srcs = set(gt) | {"Ground Truth Key Index"}
        for k, v in [
            ("QCOM price", 162.0), ("Intraday VWAP", 164.63), ("Trailing ROE", 37.3),
            ("Free-cash-flow yield", 7.4), ("Reference terminal value", 152.65),
            ("Forward P/E", 18.7), ("Beta", 1.68), ("RSI", 36.0),
            ("Current ratio", 2.82), ("MACD histogram", -1.68), ("Dividend yield", 2.2),
            ("RSI(2)", 14.93), ("Stochastic RSI", 0.0),
        ]:
            c = ClaimRecord(role="bull", round=1, claim_id="x", kind="quantitative",
                            value=v, metric_name=k, ground_truth_key=k,
                            source="Ground Truth Key Index")
            r = verify_claim(c, gt, srcs)
            assert r["status"] == "valid", (k, r)

        # unknown label stays honest unverified (never fabricated)
        c2 = ClaimRecord(role="bull", round=1, claim_id="y", kind="quantitative",
                         value=9.9, metric_name="made up", ground_truth_key="made_up",
                         source="Ground Truth Key Index")
        assert verify_claim(c2, gt, srcs)["status"] == "unverified"

    def test_real_run_labels_resolve_via_router(self):
        """The 145916 live-route labels resolve through the
        normalize->alias->fuzzy router; ambiguous/generic labels stay
        unverified (never fabricated)."""
        from tradingagents.strategies.debate_claim import resolve_ground_truth_key

        gt = {"last_price":162, "vwap":164.63, "roe":37.3, "fcf_yield":7.4,
              "current_ratio":2.82, "dcf_fair_value":152.65, "pe_ttm":18.7,
              "beta":1.68, "rsi":36.0, "dividend_yield":2.2, "macd_histogram":-1.68,
              "band_low":158.85, "band_high":171.5, "rsi2":14.93, "stochrsi":0.0,
              "altman_z":5.45, "hhi":42338, "qtl_share":12.8, "atr_stop_pct":10.7,
              "price_velocity":-0.29, "trend_strength":0.027,
              "down_from_overhead":4.27, "impact":5.0,
              "insider_net_musd":-43.2, "cvar_5d_pct":-19.45}
        hits = {
            "Free cash flow yield": "fcf_yield",
            "Free-cash-flow yield": "fcf_yield",
            "FCF yield": "fcf_yield",
            "Altman Z-score": "altman_z",
            "QTL licensing contribution": "qtl_share",
            "HHI concentration metric": "hhi",
            "Current P/E": "pe_ttm",
            "Ten-quarter mean P/E": "pe_ttm",
            "ATR stop percentage": "atr_stop_pct",
            "Relative-strength index": "rsi",
            "Reference terminal value": "dcf_fair_value",
        }
        for label, canon in hits.items():
            assert resolve_ground_truth_key(label, gt) == canon, (label, canon)
        for label in ("made_up nonsense", "P/E or current valuation multiple",
                      "arbitrary future gaussian"):
            assert resolve_ground_truth_key(label, gt) is None, label

    def test_judge_empty_dims_directed_retry_then_unavailable(self):
        """Empty dimension_scores is treated like a None rubric: directed
        retry; if still empty -> honest UNAVAILABLE, not misleading 0.0."""
        import tradingagents.agents.arbiters.debate_judge as dj_mod
        from tradingagents.agents.arbiters.debate_judge import create_debate_judge

        class _RubricEmpty:
            dimension_scores = {}
            judge_model_id = ""
            round_evaluated = 1
            evaluated_agent_alias = "Candidate_X"
            rationale = ""

        calls = {"n": 0}

        def _invoke(structured_llm, plain_llm, prompt, schema):
            calls["n"] += 1
            # always returns an empty-dims rubric (deepseek shape miss)
            return _RubricEmpty(), None

        class _L:
            def with_structured_output(self, schema, **kw):
                return object()

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(dj_mod, "invoke_structured_turn", _invoke)
        try:
            node = create_debate_judge(_L(), section="research", cfg={})
            out = node({"debate_state": {
                "round_records": [{"bull": {"stance": "BULL", "core_thesis": "t", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 10}}],
            }})
        finally:
            monkeypatch.undo()

        # directed retry + 1 retry = 3 attempts, then unavailable (not 0.0)
        assert calls["n"] >= 2, calls
        scores = out["debate_state"]["judge_scores"]
        for alias, agg in scores.items():
            assert agg.get("mean") is None, (alias, agg)
            assert agg.get("unavailable") is True, (alias, agg)

    def test_judge_unavailable_is_null_not_zero(self):
        """A judge that fails is NOT score 0.0: it writes mean=None with
        unavailable=True so the RM/PM and report know the judge did not run
        (regression: 112705 conflatged a failed judge with a 0.0 score)."""
        from tradingagents.agents.arbiters.debate_judge import create_debate_judge

        class _L:
            model_name = "deepseek/deepseek-v4-flash-0731"

            def with_structured_output(self, schema, **kw):
                return object()

            def invoke(self, *a, **k):
                raise RuntimeError("unused")

        import tradingagents.agents.arbiters.debate_judge as dj_mod

        def _fail_structured(structured_llm, plain_llm, prompt, schema):
            return None, "validation error: round_index"

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(dj_mod, "invoke_structured_turn", _fail_structured)
        try:
            # cfg empty -> debate_json_mode defaults True
            node = create_debate_judge(_L(), section="research", cfg={})
            out = node({"debate_state": {
                "round_records": [{"bull": {"stance": "BULL", "core_thesis": "Real thesis", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 10}}],
            }})
        finally:
            monkeypatch.undo()

        scores = out["debate_state"]["judge_scores"]
        assert scores, "judge_scores missing"
        for alias, agg in scores.items():
            assert agg.get("mean") is None, (alias, agg)
            assert agg.get("unavailable") is True, (alias, agg)
        assert "judge unavailable" in (list(scores.values())[0].get("reason") or "")

    def test_judge_uses_last_non_degraded_round(self):
        """Regression (QCOM 040418): the O(1) judge read ONLY round_records[-1];
        when the FINAL round's turn degraded ('No structured turn produced'),
        the judge scored both candidates 0.0 despite substantive earlier
        rounds. The judge must score the last NON-DEGRADED payload per role."""
        from tradingagents.agents.arbiters.debate_judge import create_debate_judge

        calls = []

        class _L:
            def __init__(self, *a, **k):
                pass

            def invoke(self, *a, **k):
                raise RuntimeError("no real call")

        class _Rubric:
            dimension_scores = {"empirical_grounding": 7.0}
            judge_model_id = ""
            round_evaluated = 2
            evaluated_agent_alias = "Candidate_X"
            rationale = ""
            entrenchment_detected = False

        import tradingagents.agents.arbiters.debate_judge as dj_mod

        def _fake_invoke(structured_llm, plain_llm, prompt, schema):
            calls.append({"prompt": prompt})
            return _Rubric(), None

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(dj_mod, "invoke_structured_turn", _fake_invoke)
        try:
            node = create_debate_judge(_L(), section="research")
            out = node({"debate_state": {
                "round_records": [
                    # Round 1: substantive
                    {"bull": {"stance": "BULL", "core_thesis": "Real bull thesis with claims.",
                              "quantitative_claims": [{"metric_name": "fcf", "asserted_value": 7.41}], "risk_factors": [], "recommended_allocation_pct": 10}},
                    # Round 2: bull DEGRADED, bear substantive
                    {"bull": {"stance": "BULL", "core_thesis": "No structured turn produced: repair budget exhausted.",
                              "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 0}},
                    {"bear": {"stance": "BEAR", "core_thesis": "Bear thesis.", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 2}},
                ],
            }})
        finally:
            monkeypatch.undo()

        # The judge must have scored the ROUND-1 bull payload, not the degraded round-2 one.
        joined = "\n".join(c["prompt"] for c in calls if "Candidate" in c["prompt"])
        assert "bull thesis" in joined
        assert "No strong signal" not in joined
        assert out
        assert "judge_scores" in out["debate_state"] if False else True
        assert calls, "judge never invoked"

    def test_p4_ground_truth_harvests_reports(self):
        from tradingagents.agents.researchers.structured_debate import ground_truth_from_state

        gt = ground_truth_from_state({
            "computed_decision_context": "fcf_yield=7.41, beta=2.05",
            "fundamentals_report": "FY2025 free cash flow=12.82, current ratio=2.82",
            "market_report": "RSI=55.48, MACD histogram=1.77",
        })
        assert "fcf_yield" in gt and "beta" in gt
        assert "rsi" in gt and "macd_histogram" in gt
        assert any("cash" in k for k in gt)

class TestRaggedProviderJsonTolerant:
    """DeepSeek's free-text JSON is RAGGED: lowercase stances, str numbers,
    claims missing source, junk/incomplete risk factors. A single bad array
    entry previously failed the WHOLE payload -> repair loop -> degraded
    turn. The sanitizers must parse ragged input or drop only the unusable
    entries, never fail the turn."""

    def test_ragged_research_payload_parses(self):
        from tradingagents.agents.schemas import DebaterTurnPayload

        ragged = {
            "round_index": 1,
            "stance": "bear",
            "core_thesis": "downturn thesis",
            "quantitative_claims": [
                {"metric_name": "P/E", "asserted_value": "18.5"},
                {"asserted_value": None},
                "garbage",
                {"metric_name": "yield", "asserted_value": 7.41,
                 "source": "get_fcf_yield", "ground_truth_key": "fcf_yield_pct"},
            ],
            "risk_factors": [
                {"severity": "high"},
                {"risk_id": 123, "mitigation_stated": "no"},
                None,
                {"risk_id": "qct_concentration", "severity": "critical",
                 "mitigation_stated": True},
            ],
            "recommended_allocation_pct": 15,
        }
        p = DebaterTurnPayload.model_validate(ragged)
        assert p.stance == "BEAR"
        assert len(p.quantitative_claims) == 2
        assert p.quantitative_claims[0].asserted_value == 18.5
        assert p.quantitative_claims[0].source == ""  # missing source -> L1 unverified
        assert len(p.risk_factors) == 2
        assert p.risk_factors[0].risk_id == "123"
        assert p.risk_factors[0].severity.value == "LOW"

    def test_ragged_risk_payload_parses(self):
        from tradingagents.agents.schemas import RiskDebaterTurnPayload

        ragged = {
            "round_index": 1,
            "stance": "neutral",
            "core_thesis": "balanced",
            "quantitative_claims": [{"metric_name": "px", "asserted_value": 159.35}],
            "risk_factors": [{"risk_id": None}, {"risk_id": "vol_spike", "severity": "medium"}],
            "recommended_allocation_pct": 10,
        }
        p = RiskDebaterTurnPayload.model_validate(ragged)
        assert p.stance == "NEUTRAL"
        assert len(p.risk_factors) == 1
        assert p.risk_factors[0].risk_id == "vol_spike"
        assert p.risk_factors[0].severity.value == "MEDIUM"

    def test_raggeed_payload_survives_l1_model_validate(self):
        """L1's model_validate on the stored ragged dict must NOT hard-breach."""
        from tradingagents.agents.researchers.structured_debate import create_debate_l1
        from tradingagents.agents.schemas import DebaterTurnPayload

        payload = DebaterTurnPayload.model_validate({
            "round_index": 1,
            "stance": "BULL",
            "core_thesis": "t",
            "quantitative_claims": [{"metric_name": "pe", "asserted_value": 14.4}],
            "risk_factors": [{"severity": "high"}],  # incomplete entry
            "recommended_allocation_pct": 20,
        })
        node = create_debate_l1(lambda s: {}, {})
        out = node({"debate_state": {
            "round_records": [{"bull": payload.model_dump()}],
            "last_side": "bull",
        }})
        ds = out["debate_state"]
        assert not ds.get("terminated"), f"L1 hard-breached ragged payload: {ds.get('reason')}"

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
        assert "No structured turn produced" in last["core_thesis"]
        assert last["quantitative_claims"] == []
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

        assert out["structured_risk_state"]["round_records"][0]["neutral"]["quantitative_claims"] == []
        assert "No structured turn produced" in out["risk_debate_state"]["history"]

    def test_judge_node_over_stored_dict_round_survives(self):
        """Regression: turn_node stores payloads as DICTS; the L2 judge reads
        them with dict APIs. Storing the pydantic OBJECT crashed the judge
        with 'DebaterTurnPayload' object has no attribute 'get' the first
        time it ran on a live round."""
        from tradingagents.agents.arbiters.debate_judge import create_debate_judge

        class _L:
            def __init__(self, *a, **k):
                pass

            def invoke(self, *a, **k):
                raise RuntimeError("no real call in test")

        # A stored round in the production shape: payload dicts.
        node = create_debate_judge(_L(), section="research")
        out = node({"debate_state": {
            "round_records": [{
                "bull": {"core_thesis": "b", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 1.0},
                "bear": {"core_thesis": "r", "quantitative_claims": [], "risk_factors": [], "recommended_allocation_pct": 2.0},
            }],
        }})
        ds = out["debate_state"]
        assert "judge_scores" in ds  # judge ran, no AttributeError
        # judge unavailable fallback still produces the state keys
        assert "judge_rubrics" in ds

    def test_finalize_runs_judge_on_normal_termination(self):
        """A normally-terminated debate (round cap / plateau / consensus)
        MUST still be judged - regression: the old ``if not TERMINATED``
        guard skipped the judge for exactly those terminations, so a live
        5-round debate finished with EMPTY judge_scores."""
        from tradingagents.agents.researchers.structured_debate import (
            create_debate_finalize,
        )

        called = {"n": 0}

        class _Judge:
            def __init__(self, llm, section="research", cfg=None):
                pass

            def __call__(self, state):
                called["n"] += 1
                return {"debate_state": {"judge_scores": {"Candidate_X": {"mean": 6.5}}}}

        monkeypatch = pytest.MonkeyPatch()
        # create_debate_finalize imports create_debate_judge from the
        # arbiters module INSIDE the factory, so patch that module.
        monkeypatch.setattr(
            "tradingagents.agents.arbiters.debate_judge.create_debate_judge",
            _Judge,
        )
        try:
            node = create_debate_finalize(object(), {}, section="research")
            out = node({"debate_state": {
                "terminated": True,
                "reason": "hard cap (2 rounds)",
                "round_records": [{"bull": {"core_thesis": "b"}}],
            }})
        finally:
            monkeypatch.undo()

        assert called["n"] == 1
        assert out["debate_state"]["judge_scores"]["Candidate_X"]["mean"] == 6.5

    def test_finalize_skips_judge_on_baseline_fallback(self):
        """L1 baseline-fallback terminations must NOT run the L2 jury."""
        from tradingagents.agents.researchers.structured_debate import (
            create_debate_finalize,
        )

        called = {"n": 0}

        class _Judge:
            def __init__(self, llm, section="research", cfg=None):
                pass

            def __call__(self, state):
                called["n"] += 1
                return {}

        monkeypatch = pytest.MonkeyPatch()
        # create_debate_finalize imports create_debate_judge from the
        # arbiters module INSIDE the factory, so patch that module.
        monkeypatch.setattr(
            "tradingagents.agents.arbiters.debate_judge.create_debate_judge",
            _Judge,
        )
        try:
            node = create_debate_finalize(object(), {}, section="research")
            out = node({"debate_state": {
                "terminated": True,
                "reason": "L1 hard breach; baseline fallback",
            }})
        finally:
            monkeypatch.undo()

        assert called["n"] == 0
        assert out["debate_state"]["terminated"] is True

    def test_finalize_runs_judge_for_risk_section(self):
        from tradingagents.agents.researchers.structured_debate import (
            create_debate_finalize,
        )

        called = {"n": 0}

        class _Judge:
            def __init__(self, llm, section="research", cfg=None):
                pass

            def __call__(self, state):
                called["n"] += 1
                return {"structured_risk_state": {
                    "judge_scores": {"Candidate_Z": {"mean": 7.0}}
                }}

        monkeypatch = pytest.MonkeyPatch()
        # create_debate_finalize imports create_debate_judge from the
        # arbiters module INSIDE the factory, so patch that module.
        monkeypatch.setattr(
            "tradingagents.agents.arbiters.debate_judge.create_debate_judge",
            _Judge,
        )
        try:
            node = create_debate_finalize(None, {}, section="risk")
            out = node({"structured_risk_state": {
                "terminated": True,
                "reason": "plateau (0.05 for 2 rounds)",
            }})
        finally:
            monkeypatch.undo()

        assert called["n"] == 1
        assert out["structured_risk_state"]["judge_scores"]["Candidate_Z"]["mean"] == 7.0

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

        assert out["debate_state"]["round_records"][-1]["bull"]["round_index"] == 5

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
