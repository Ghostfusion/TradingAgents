"""P1 — Grounding contract: claim ledger + L1 verifier hermetic tests.

Design: docs/design_multi_agent_debate.md §4.2. Pure/offline; synthetic
claims only. Every quantitative-claim path (valid / violated / abstain /
unverified / deceptive-grounding) plus the ledger and rendering are covered.
"""

import pytest

from tradingagents.strategies.debate_claim import (
    ABSTAIN,
    QUALITATIVE,
    UNVERIFIED,
    VALID,
    VIOLATED,
    ClaimLedger,
    ClaimRecord,
    verify_claim,
)

pytestmark = pytest.mark.timeout(120)


def _claim(
    value=None,
    key="pe",
    source="get_ratios",
    kind="quantitative",
    role="bull",
    round_no=1,
):
    return ClaimRecord(
        role=role,
        round=round_no,
        value=value,
        ground_truth_key=key,
        source=source,
        kind=kind,
    )


class TestVerifyClaim:
    def test_valid_claim_within_tolerance(self):
        out = verify_claim(_claim(value=38.0), {"pe": 38.0}, {"get_ratios"})
        assert out["status"] == VALID
        assert out["is_valid"] is True
        assert out["error_margin_pct"] == 0.0

    def test_violated_claim_beyond_tolerance(self):
        out = verify_claim(_claim(value=12.0), {"pe": 38.0}, {"get_ratios"})
        assert out["status"] == VIOLATED
        assert out["is_valid"] is False
        assert out["error_margin_pct"] > 5.0

    def test_deceptive_grounding_source_not_in_ledger(self):
        out = verify_claim(_claim(value=38.0), {"pe": 38.0}, {"get_swing_set"})
        assert out["status"] == VIOLATED
        assert "deceptive grounding" in out["reason"]

    def test_unknown_ground_truth_with_source_unverified(self):
        out = verify_claim(_claim(key="nope"), {"pe": 38.0}, {"get_ratios"})
        assert out["status"] == UNVERIFIED
        assert out["is_valid"] is False

    def test_unsupported_claim_downgraded_to_abstain(self):
        out = verify_claim(_claim(source=""), {}, None)
        assert out["status"] == ABSTAIN
        assert "no source" in out["reason"]

    def test_qualitative_claim_weighs_zero(self):
        out = verify_claim(_claim(kind="qualitative"), {"pe": 38.0}, {"get_ratios"})
        assert out["status"] == QUALITATIVE

    def test_abstain_claim(self):
        out = verify_claim(_claim(kind="abstain"), {"pe": 38.0}, {"get_ratios"})
        assert out["status"] == ABSTAIN

    def test_custom_tolerance(self):
        out = verify_claim(_claim(value=38.5), {"pe": 38.0}, {"get_ratios"}, tolerance_pct=2.0)
        assert out["status"] == VALID


class TestClaimLedger:
    def test_append_assigns_id_and_round_trip(self):
        led = ClaimLedger()
        led.append(_claim(value=1.0))
        assert led.rows[0].claim_id == "bull_1_0"
        roundtrip = ClaimLedger.from_dict(led.to_dict())
        assert roundtrip.rows[0].value == 1.0
        assert roundtrip.rows[0].role == "bull"

    def test_by_role_and_previous_claims(self):
        led = ClaimLedger()
        led.append(_claim(role="bull", round_no=1))
        led.append(_claim(role="bull", round_no=2, value=2.0, key="x"))
        led.append(_claim(role="bear", round_no=1))
        assert len(led.by_role("bull")) == 2
        assert len(led.previous_claims("bull", 2)) == 1

    def test_render_markdown_marks_unused(self):
        led = ClaimLedger()
        led.append(_claim(value=1.0, key="pe"))
        md = led.render_markdown(used_claim_ids=set())
        assert "(unused)" in md
        assert "get_ratios" in md


def test_roundtrip_json_stable():
    import json

    led = ClaimLedger()
    led.append(_claim(value=38.0))
    assert json.loads(json.dumps(led.to_dict())) == led.to_dict()
