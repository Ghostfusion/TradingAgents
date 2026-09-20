"""The closed-vocabulary challenge pass (design doc §10, Phase 5).

What is pinned here is **§10's four rules, each enforced mechanically** - the
closed vocabulary, the packet-row citation, downgrade-only, and the materiality
test on ground (b). The model proposes; `adjudicate_challenge` decides. Every
test asserts what a reader of the recorded outcome observes, not the wording of
the discard message.

The gate's own registration (DEFAULT_CONFIG / `_ENV_OVERRIDES` / the registry doc
/ `.env.example` / flippability) is enforced by `tests/test_gate_env_switches.py`;
it is not duplicated here.
"""

from __future__ import annotations

from tradingagents.strategies.decision_challenge import (
    CHALLENGE_GROUNDS,
    ChallengeVerdict,
    adjudicate_challenge,
    challenge_prompt,
    run_challenge,
)
from tradingagents.strategies.decision_packet import render_decision_packet

#: A report whose ONE metric is `unresolved` - the only class §10's ground (b)
#: may rest on. The stated basis on one side and none on the other is what makes
#: it `unresolved` rather than `defect`.
_REPORT = (
    "## Ratios\n"
    "get_ratios reports EV/EBIT 5.50 on the ratios table (ttm:ttm basis).\n"
    "## Analyst verdict\n"
    "EV/EBIT of 4.40 implies the name is cheap.\n"
)

#: The decision's prose. It NAMES `ev/ebit` and states two figures the packet
#: carries - so ground (b) is material and ground (c) is not met.
_PROSE = "**Investment Thesis**: EV/EBIT 4.40 is cheap against a 5.50 peer read."


def _packet() -> str:
    return render_decision_packet(
        {
            "company_of_interest": "TEST",
            "trade_date": "2026-01-02",
            "fundamentals_report": _REPORT,
        },
        {},
        closes=[],
    )


def _falsifier_row(packet: str) -> str:
    rows = [ln.strip() for ln in packet.splitlines() if ln.strip().startswith("- ")]
    assert rows, "the packet must carry at least one FALSIFIERS row"
    return rows[0]


def _unresolved_row(packet: str) -> str:
    rows = [ln.strip() for ln in packet.splitlines() if "[unresolved]" in ln]
    assert rows, "the packet must carry an unresolved CONFLICT row"
    return rows[0]


# ---------------------------------------------------------------------------
# Rule 1 - the closed vocabulary
# ---------------------------------------------------------------------------


def test_a_ground_outside_the_closed_vocabulary_is_discarded_not_mapped():
    """§10 rule 1: it cannot invent a new reason for caution.

    'd' is not a ground. A version that mapped an unknown ground onto the nearest
    member, or that let the pydantic schema reject it, would leave no record that
    the model tried - and an invented ground is exactly what must be visible.
    """
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="d", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is False
    assert out["ground"] is None
    assert "closed vocabulary" in out["discarded"]
    assert CHALLENGE_GROUNDS == ("a", "b", "c")


def test_the_vocabulary_is_enforced_by_the_adjudicator_not_the_schema():
    """A schema `Literal` would hide the invented ground inside a validation error.

    `run_challenge` catches that error as "the call failed", which is
    indistinguishable from an outage - so the record of WHAT was proposed is lost.
    The field is a plain `str` for this reason.
    """
    assert ChallengeVerdict.model_fields["ground"].annotation is str


# ---------------------------------------------------------------------------
# Rule 2 - the evidence must be a packet row
# ---------------------------------------------------------------------------


def test_an_objection_citing_nothing_is_discarded():
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(invalidated=True, ground="a", evidence=""),
        packet=packet,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is False
    assert "not a row of the packet" in out["discarded"]


def test_an_objection_citing_text_the_packet_does_not_carry_is_discarded():
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="a", evidence="the market looks risky here"
        ),
        packet=packet,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is False
    assert "not a row of the packet" in out["discarded"]


# ---------------------------------------------------------------------------
# Ground (a) - a breached falsifier
# ---------------------------------------------------------------------------


def test_ground_a_needs_a_falsifier_row_and_the_packet_has_one():
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="a", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is True
    assert out["ground"] == "a"


def test_ground_a_cannot_cite_a_bullet_inside_an_attached_report():
    """§11's expansion appends the analyst reports, which carry `- ` bullets.

    A whole-packet scan for `- ` lines would accept one of those as a falsifier,
    and ground (a) would rest on a line the packet never offered as one.
    """
    from tradingagents.strategies.decision_packet import EXPANSION_HEADER

    packet = _packet()
    bullet = "- the report's own bullet, not a falsifier"
    expanded = (
        packet
        + f"\n\n{EXPANSION_HEADER}\nAttached because the evidence is divided.\n"
        + f"## market\n{bullet}\n"
    )
    out = adjudicate_challenge(
        ChallengeVerdict(invalidated=True, ground="a", evidence=bullet),
        packet=expanded,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is False
    assert "FALSIFIERS row" in out["discarded"]


# ---------------------------------------------------------------------------
# Ground (b) - the materiality test (§10's correction)
# ---------------------------------------------------------------------------


def test_ground_b_lands_only_on_an_unresolved_contradiction_the_decision_relied_on():
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True,
            ground="b",
            evidence=_unresolved_row(packet),
            metric="ev/ebit",
        ),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
    )
    assert out["invalidated"] is True
    assert out["ground"] == "b"


def test_a_contradiction_the_decision_never_mentions_is_recorded_not_acted_on():
    """§10: *"Otherwise: contradiction exists -> record the contradiction -> do
    NOT invalidate."* Legs 1 and 3 of the materiality test, enforced on the
    decision's own prose - the only in-run evidence of reliance.
    """
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True,
            ground="b",
            evidence=_unresolved_row(packet),
            metric="ev/ebit",
        ),
        packet=packet,
        decision_text="**Investment Thesis**: the balance sheet looks solid.",
        decision_prose="**Investment Thesis**: the balance sheet looks solid.",
    )
    assert out["invalidated"] is False
    assert "recorded, not invalidated" in out["discarded"]
    assert out["recorded_contradictions"], "the contradiction must still be recorded"


def test_ground_b_cannot_rest_on_a_defect_or_a_basis_difference():
    """§9: only `unresolved` may participate in a challenge invalidation.

    A `defect` row is one producer printing two values; a `basis_difference` is
    two producers each right on their own basis. Neither is a contradiction the
    decision has to reconcile, so neither may weaken it.
    """
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True,
            ground="b",
            evidence=_falsifier_row(packet),
            metric="market cap",
        ),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
    )
    assert out["invalidated"] is False
    assert "UNRESOLVED contradiction" in out["discarded"]


# ---------------------------------------------------------------------------
# Ground (c) - a number the packet does not carry
# ---------------------------------------------------------------------------


def test_ground_c_is_checked_not_trusted():
    """A model claiming (c) while every figure it stated IS in the packet is discarded."""
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="c", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
    )
    assert out["invalidated"] is False
    assert "every figure the decision states appears in the packet" in out["discarded"]


def test_one_number_at_two_precisions_is_one_number():
    """`4.40` in the decision and `4.4` in the packet are the SAME figure.

    A text comparison made ground (c) fire on a decision that had invented
    nothing - measured, not hypothesised. The repo has already had to fix this
    class once (`report_verifier._cluster_value_tokens`, LRCX 2026-09-14).
    """
    packet = _packet()
    assert "4.4" in packet and "4.40" not in packet
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="c", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        decision_text="**Investment Thesis**: EV/EBIT is 4.40 against a peer 5.50.",
        decision_prose="**Investment Thesis**: EV/EBIT is 4.40 against a peer 5.50.",
    )
    assert out["invalidated"] is False


def test_ground_c_lands_on_a_figure_the_packet_really_does_not_carry():
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="c", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE + " A hidden figure 987.654 proves it.",
    )
    assert out["invalidated"] is True
    assert "987.654" in out["reason"]


def test_the_decisions_own_parameters_are_not_assertions_about_the_world():
    """Ground (c) is scoped to the prose, never to `confidence`/`stop_loss`.

    Checking the decision's own parameters would make ground (c) fire on almost
    every decision - a fresh route to HOLD arriving through the check rather than
    through the model.
    """
    packet = _packet()
    out = adjudicate_challenge(
        ChallengeVerdict(
            invalidated=True, ground="c", evidence=_falsifier_row(packet)
        ),
        packet=packet,
        # The whole rendered decision carries the model's own 0.73 confidence;
        # the prose does not.
        decision_text=_PROSE + "\n**Confidence**: 0.73\n**Stop Loss**: 88.125\n",
        decision_prose=_PROSE,
    )
    assert out["invalidated"] is False


# ---------------------------------------------------------------------------
# §8's rule - an unknown is not evidence against a thesis
# ---------------------------------------------------------------------------


def test_an_uncertainty_row_is_never_a_valid_ground():
    packet = _packet()
    rows = [ln.strip() for ln in packet.splitlines() if ln.startswith("UNCERTAINTY")]
    assert rows, "the packet must carry an UNCERTAINTY row for this test to mean anything"
    out = adjudicate_challenge(
        ChallengeVerdict(invalidated=True, ground="a", evidence=rows[0]),
        packet=packet,
        decision_text=_PROSE,
    )
    assert out["invalidated"] is False
    assert "UNCERTAINTY" in out["discarded"]


# ---------------------------------------------------------------------------
# Rule 3 - downgrade only
# ---------------------------------------------------------------------------


def test_the_only_available_move_is_toward_hold():
    """§10 rule 3, and the same shape `stabilize_decision` uses.

    Nothing in this module can raise a rating: `downgrade_toward_hold` is the
    sole mutation the pass exposes.
    """
    from tradingagents.strategies.decision_guardrail import downgrade_toward_hold

    assert downgrade_toward_hold("Buy") == "Hold"
    assert downgrade_toward_hold("Overweight") == "Hold"
    assert downgrade_toward_hold("Sell") == "Hold"
    assert downgrade_toward_hold("Underweight") == "Hold"
    assert downgrade_toward_hold("Hold") == "Hold"
    assert downgrade_toward_hold("nonsense") is None


# ---------------------------------------------------------------------------
# Failure paths - a failure is never an invalidation
# ---------------------------------------------------------------------------


class _Boom:
    def invoke(self, _prompt):
        raise RuntimeError("provider exploded")


class _Stub:
    def __init__(self, verdict):
        self._verdict = verdict

    def invoke(self, _prompt):
        return self._verdict


def test_a_provider_failure_never_invalidates():
    """An outage must not downgrade every decision.

    Treating a failure as an invalidation would make the conservatism §10 exists
    to remove arrive through the back door.
    """
    packet = _packet()
    out = run_challenge(
        _Boom(),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
        cfg={"enable_decision_challenge": True},
    )
    assert out["invalidated"] is False
    assert "failed" in out["discarded"]


def test_the_gate_off_makes_no_call_at_all():
    packet = _packet()
    out = run_challenge(
        _Boom(),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
        cfg={"enable_decision_challenge": False},
    )
    assert out["invalidated"] is False
    assert out["challenge_enabled"] is False
    assert "off" in out["discarded"]


def test_no_packet_is_not_a_pass_and_not_an_invalidation():
    out = run_challenge(
        _Stub(ChallengeVerdict(invalidated=True, ground="a", evidence="x")),
        packet="",
        decision_text=_PROSE,
        decision_prose=_PROSE,
        cfg={"enable_decision_challenge": True},
    )
    assert out["invalidated"] is False
    assert "no packet in state" in out["discarded"]


def test_a_full_pass_records_both_what_was_proposed_and_what_landed():
    """The record is what makes the pass auditable after the fact."""
    packet = _packet()
    out = run_challenge(
        _Stub(
            ChallengeVerdict(
                invalidated=True,
                ground="b",
                evidence=_unresolved_row(packet),
                metric="ev/ebit",
                reason="the decision leans on a metric the packet contradicts",
            )
        ),
        packet=packet,
        decision_text=_PROSE,
        decision_prose=_PROSE,
        cfg={"enable_decision_challenge": True},
    )
    assert out["invalidated"] is True
    assert out["ground"] == "b"
    assert out["challenge_enabled"] is True
    assert out["proposed"]["ground"] == "b"


# ---------------------------------------------------------------------------
# The prompt states the boundaries, including the non-grounds
# ---------------------------------------------------------------------------


def test_the_prompt_names_the_non_grounds_as_well_as_the_grounds():
    """A model told only what IS allowed reaches for the nearest substitute."""
    text = challenge_prompt("PACKET ROW", "DECISION TEXT")
    assert "may ONLY invalidate" in text
    for token in ("(a)", "(b)", "(c)"):
        assert token in text
    assert "uncertainty" in text.lower()
    assert "not a contradiction" in text
    assert "basis_difference" in text
    assert "verbatim" in text


def test_the_rendered_decision_shows_a_challenge_downgrade():
    """§10: a lowered rating with no stated ground IS the new caution rationale.

    The rendered decision must carry the ground, or a reader cannot tell why the
    recommendation moved.
    """
    from tradingagents.agents.schemas import (
        PortfolioDecision,
        PortfolioRating,
        render_pm_decision,
    )

    plain = render_pm_decision(
        PortfolioDecision(
            rating=PortfolioRating.HOLD, executive_summary="x", investment_thesis="y"
        )
    )
    assert "Challenge" not in plain

    challenged = render_pm_decision(
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
            challenge_ground="b",
            challenge_reason="relies on a contradicted metric",
        )
    )
    assert "closed ground (b)" in challenged
