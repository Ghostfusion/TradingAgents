"""P2 — Debate scoring / termination / severity / entrenchment hermetic tests.

Design: docs/design_multi_agent_debate.md §4.3-4.4 + R1'/R2' (rev v3). All
pure, offline, synthetic inputs; no LLM.
"""

import pytest

from tradingagents.strategies.debate_claim import ClaimRecord, verify_claim
from tradingagents.strategies.debate_score import (
    ABORT_TO_BASELINE,
    APPLY_PENALTY_AND_PROCEED,
    GREEN,
    HARD_BREACH,
    L1_RUBRIC_DIMENSIONS,
    PROCEED,
    RETRYABLE_ERROR,
    SOFT_WARNING,
    TRIGGER_REGEN,
    aligned_value_vectors,
    classify_severity,
    debate_score,
    direct_challenge_share,
    divergence_check,
    entrenchment_index,
    information_gain,
    l1_rubric,
    novelty_gain,
    reweight_to_baseline,
    termination_check,
)

pytestmark = pytest.mark.timeout(120)


def _verif(**claim_kwargs):
    c = ClaimRecord(
        role=claim_kwargs.pop("role", "bull"),
        round=claim_kwargs.pop("round_no", 1),
        value=claim_kwargs.pop("value", 10.0),
        ground_truth_key=claim_kwargs.pop("key", "k"),
        source=claim_kwargs.pop("source", "s"),
        kind=claim_kwargs.pop("kind", "quantitative"),
    )
    truth = claim_kwargs.pop("truth", {"k": 10.0})
    sources = claim_kwargs.pop("sources", {"s"})
    return verify_claim(c, truth, sources)


class TestScoring:
    def test_novelty_gain_new_vs_seen(self):
        assert novelty_gain([{"metric_name": "a"}], []) == 1.0
        assert novelty_gain([{"metric_name": "a"}], [{"metric_name": "a"}]) == 0.0
        assert novelty_gain([], []) is None

    def test_debate_score_weighted(self):
        verifs = [_verif()]  # valid
        claims = [{"metric_name": "a"}]
        out = debate_score(verifs, claims, [], constraint_ok=1.0)
        assert out["score"] == pytest.approx(1.0)
        assert out["evidence"] == 1.0
        assert out["novelty"] == 1.0
        # constraint budget must matter
        out2 = debate_score(verifs, claims, [], constraint_ok=0.0)
        assert out2["score"] < out["score"]

    def test_information_gain(self):
        cur = {"novelty": 0.8}
        prior = {"novelty": 0.3}
        assert information_gain(cur, prior) == pytest.approx(0.5)
        assert information_gain(cur, None) is None


class TestTermination:
    def test_hard_cap(self):
        decision, reason = termination_check([{}, {}, {}], max_rounds=3)
        assert decision == "stop"
        assert "cap" in reason

    def test_consensus_exit(self):
        decision, reason = termination_check([{}], max_rounds=5, consensus_score=0.9)
        assert decision == "stop"
        assert "consensus" in reason

    def test_plateau(self):
        series = [
            {"novelty": 0.5},
            {"novelty": 0.51},
            {"novelty": 0.5},
        ]
        decision, reason = termination_check(
            series, max_rounds=5, min_gain=0.05, stop_consecutive=2
        )
        assert decision == "stop"
        assert "plateau" in reason

    def test_continues_below_cap(self):
        decision, reason = termination_check([{}], max_rounds=3)
        assert decision == "continue"

    def test_hard_abort_wins(self):
        decision, reason = termination_check([{}], max_rounds=3, hard_abort=True)
        assert decision == "stop"
        assert "fast-abort" in reason


class TestSeverity:
    def test_green_proceed(self):
        out = classify_severity([_verif()])
        assert out["severity_tier"] == GREEN
        assert out["l1_action"] == PROCEED
        assert out["hard_gate_passed"] is True

    def test_hard_breach_triggers_regen(self):
        out = classify_severity([_verif(), _verif(value=99.0, truth={"k": 10.0})])
        assert out["severity_tier"] == HARD_BREACH
        assert out["l1_action"] == TRIGGER_REGEN
        assert out["regen_requested"] is True

    def test_hard_breach_aborts_after_regen_budget(self):
        out = classify_severity(
            [_verif(value=99.0, truth={"k": 10.0})], regen_count=1, regen_max=1
        )
        assert out["l1_action"] == ABORT_TO_BASELINE
        assert out["regen_requested"] is False

    def test_all_abstain_retryable(self):
        out = classify_severity([_verif(kind="abstain")])
        assert out["severity_tier"] == RETRYABLE_ERROR
        assert out["l1_action"] == TRIGGER_REGEN

    def test_unverified_soft_warning_annotated(self):
        out = classify_severity([_verif(key="unknown", truth={"k": 10.0})])
        assert out["severity_tier"] == SOFT_WARNING
        assert out["l1_action"] == APPLY_PENALTY_AND_PROCEED
        assert out["penalty_score"] == 100.0

    def test_schema_fail_hard_abort(self):
        out = classify_severity([], schema_ok=False)
        assert out["severity_tier"] == HARD_BREACH
        assert out["l1_action"] == ABORT_TO_BASELINE


class TestEntrenchmentReweight:
    def test_entrenchment_identical_high(self):
        idx = entrenchment_index([1.0, 0.0], [0.95, 0.05], 50.0, 50.0)
        assert idx > 0.8

    def test_entrenchment_alloc_shift_lowers(self):
        idx = entrenchment_index([1.0, 0.0], [0.95, 0.05], 60.0, 50.0)
        assert idx < 0.8

    def test_entrenchment_empty_vector(self):
        assert entrenchment_index([], [1.0], None, None) == 0.0

    def test_divergence_floor_flags(self):
        out = divergence_check(0.8, 0.7, divergence_min=0.15)
        assert out["artificial_consensus"] is True
        assert out["divergence_delta"] == pytest.approx(0.1)

    def test_divergence_above_floor_ok(self):
        out = divergence_check(0.9, 0.3, divergence_min=0.15)
        assert out["artificial_consensus"] is False

    def test_divergence_none_no_flag(self):
        out = divergence_check(None, 0.3)
        assert out["flag"] is False
        assert out["divergence_delta"] is None

    def test_reweight_to_baseline(self):
        assert reweight_to_baseline(0.8, 0.5, alpha=0.5) == pytest.approx(0.65)
        assert reweight_to_baseline(0.8, 0.5, alpha=1.0) == pytest.approx(0.5)
        assert reweight_to_baseline(0.8, 0.5, alpha=0.0) == pytest.approx(0.8)


def _q(metric, value, kind="quantitative"):
    return {"metric_name": metric, "value": value, "kind": kind}


class TestL1Rubric:
    """L1's dimensioned rubric: the six names the L2 judge scores, filled only
    where a deterministic producer exists."""

    def test_every_member_obeys_the_ok_iff_present_contract(self):
        r = l1_rubric([], [], current_values={"a": 1.0}, prior_values={"a": 1.0})
        assert set(r["dimensions"]) == set(L1_RUBRIC_DIMENSIONS)
        for name, member in r["dimensions"].items():
            assert member["reason"], name
            assert (member["status"] == "NO_SOURCE") is (member["value"] is None)
            assert (name in r["present"]) is (member["value"] is not None)

    def test_empirical_grounding_is_ten_times_the_valid_share(self):
        verifs = [_verif(value=10.0, truth={"k": 10.0}), _verif(value=99.0, truth={"k": 10.0})]
        r = l1_rubric(verifs, [])
        assert r["dimensions"]["empirical_grounding"]["value"] == pytest.approx(5.0)

    def test_empirical_grounding_absent_when_nothing_verifiable(self):
        member = l1_rubric([], [])["dimensions"]["empirical_grounding"]
        assert member["value"] is None
        assert member["status"] == "NO_SOURCE"

    def test_downside_tail_risk_weight_is_the_high_severity_share(self):
        claims = [
            _q("risk:a", None, kind="qualitative"),
            {"metric_name": "risk:b", "value": None, "kind": "qualitative", "severity": "CRITICAL"},
            {"metric_name": "risk:c", "value": None, "kind": "qualitative", "severity": "high"},
            {"metric_name": "risk:d", "value": None, "kind": "qualitative", "severity": "LOW"},
        ]
        member = l1_rubric([], claims)["dimensions"]["downside_tail_risk_weight"]
        # The member is rounded to 4 dp for rendering.
        assert member["value"] == pytest.approx(10.0 * 2 / 3, abs=1e-3)

    def test_downside_tail_risk_weight_absent_without_risk_factors(self):
        member = l1_rubric([], [_q("pe", 18.0)])["dimensions"]["downside_tail_risk_weight"]
        assert member["value"] is None

    def test_rebuttal_effectiveness_counts_met_premises(self):
        mine = [_q("pe_ttm", 12.0), _q("rsi", 55.0)]
        theirs = [_q("pe_ttm", 38.0), _q("rsi", 55.0)]
        # One of two claims contradicts the opponent's number -> 5.0 of 10.
        assert direct_challenge_share(mine, theirs) == pytest.approx(0.5)
        member = l1_rubric([], mine, opponent_claims=theirs)["dimensions"][
            "rebuttal_effectiveness"
        ]
        assert member["value"] == pytest.approx(5.0)

    def test_rebuttal_effectiveness_absent_without_an_opponent(self):
        member = l1_rubric([], [_q("pe_ttm", 12.0)])["dimensions"]["rebuttal_effectiveness"]
        assert member["value"] is None
        assert "no preceding opposing claim" in member["reason"]

    def test_rebuttal_never_reads_an_empty_turn_as_ineffective(self):
        # A turn with no quantitative claim of its own is not a 0.
        assert direct_challenge_share([], [_q("pe_ttm", 38.0)]) is None

    def test_entrenchment_detected_on_a_repeated_position(self):
        r = l1_rubric(
            [],
            [],
            current_values={"pe_ttm": 38.0, "rsi": 55.0},
            prior_values={"pe_ttm": 38.0, "rsi": 55.0},
            allocation=2.0,
            prior_allocation=2.0,
        )
        assert r["dimensions"]["entrenchment_detected"]["value"] is True

    def test_entrenchment_not_detected_on_new_numbers(self):
        r = l1_rubric(
            [],
            [],
            current_values={"pe_ttm": 12.0},
            prior_values={"pe_ttm": 38.0},
            allocation=2.0,
            prior_allocation=8.0,
        )
        assert r["dimensions"]["entrenchment_detected"]["value"] is False

    def test_entrenchment_absent_on_a_first_turn(self):
        member = l1_rubric([], [], current_values={"pe_ttm": 38.0})["dimensions"][
            "entrenchment_detected"
        ]
        assert member["value"] is None

    def test_entrenchment_says_so_when_allocation_is_missing(self):
        r = l1_rubric(
            [],
            [],
            current_values={"pe_ttm": 38.0},
            prior_values={"pe_ttm": 38.0},
        )
        assert "allocation unavailable" in r["dimensions"]["entrenchment_detected"]["reason"]

    def test_the_two_unproducible_dimensions_say_why(self):
        dims = l1_rubric([], [])["dimensions"]
        assert "forward calendar" in dims["catalyst_clarity"]["reason"]
        assert "valuation perturbation" in dims["assumption_sensitivity"]["reason"]
        assert dims["catalyst_clarity"]["value"] is None
        assert dims["assumption_sensitivity"]["value"] is None

    def test_aligned_vectors_pad_a_metric_present_in_only_one_turn(self):
        a, b = aligned_value_vectors({"x": 2.0, "y": 3.0}, {"x": 2.0})
        assert a == [2.0, 3.0]
        assert b == [2.0, 0.0]
