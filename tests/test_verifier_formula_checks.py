"""Round-2 verifier families: tone-claim consistency (Q6) and valuation-band truth (Q3).

Docs: ``docs/design_quant_formulas_research_round2.md`` items N6/N2;
``docs/implementation_plan_quant_formula_additions.md`` phases Q6/Q3.
These are text-only metric families in ``agents/utils/report_verifier.py``.
"""

from __future__ import annotations

from tradingagents.agents.utils.report_verifier import (
    _text_metrics,
    _tone_claim_conflict,
    _valuation_band_conflict,
)

# --- Q6: tone claims must agree with the cited deterministic read -------------


def test_a_confident_claim_on_a_negative_cited_tone_is_a_conflict():
    text = (
        "Management's language on the call sounded confident about the outlook.\n"
        "disclosure tone GOOG (dictionary lm-seed-v1, 812 words): tone=-0.0041 (neg=31 pos=12)\n"
    )
    claims = _tone_claim_conflict(text)
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"
    assert "confident" in claims[0].claim


def test_a_consistent_tone_claim_is_not_flagged():
    text = (
        "The filing language reads confident about margins.\n"
        "disclosure tone GOOG (dictionary lm-seed-v1, 812 words): tone=+0.0031 (neg=8 pos=19)\n"
    )
    assert _tone_claim_conflict(text) == []


def test_a_direction_claim_over_a_zero_hit_read_is_a_conflict():
    text = (
        "The disclosure language turned cautious this quarter.\n"
        "tone=zero_hits (0 of 640 words in the dictionary)\n"
    )
    claims = _tone_claim_conflict(text)
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"


def test_generic_confidence_prose_without_a_cited_tone_is_not_flagged():
    # No tone= line at all: ordinary analyst prose must never fire the family.
    text = "We are confident in the dip thesis but the language in the filing was hedged.\n"
    assert _tone_claim_conflict(text) == []


def test_a_cited_tone_without_a_direction_claim_is_not_flagged():
    text = "disclosure tone GOOG: tone=-0.0041 (neg=31 pos=12)\n"
    assert _tone_claim_conflict(text) == []


# --- Q3: band coverage and inside/outside arithmetic --------------------------


def test_a_band_without_realized_coverage_is_flagged():
    text = "valuation band GOOG (nominal 90%): [280.0, 390.0]\n"
    claims = _valuation_band_conflict(text)
    assert len(claims) == 1
    assert "without realized coverage" in claims[0].claim


def test_a_truthful_band_is_not_flagged():
    text = (
        "valuation band GOOG (nominal 90%, realized 88.4% on 250 pairs, window 250): "
        "[280.0, 390.0] point value 336.37 is INSIDE the band\n"
    )
    assert _valuation_band_conflict(text) == []


def test_a_false_inside_verdict_is_flagged():
    text = (
        "valuation band GOOG (nominal 90%, realized 88.4% on 250 pairs): "
        "[280.0, 390.0] point value 412.5 is INSIDE the band\n"
    )
    claims = _valuation_band_conflict(text)
    assert len(claims) == 1
    assert "INSIDE" in claims[0].claim


def test_a_false_outside_verdict_is_flagged():
    text = (
        "valuation band GOOG (nominal 90%, realized 88.4% on 250 pairs): "
        "[280.0, 390.0] point value 336.37 is OUTSIDE the band\n"
    )
    claims = _valuation_band_conflict(text)
    assert len(claims) == 1
    assert "OUTSIDE" in claims[0].claim


def test_a_band_far_below_its_nominal_coverage_is_flagged():
    text = (
        "valuation band GOOG (nominal 90%, realized 41.0% on 250 pairs): "
        "[280.0, 390.0]\n"
    )
    claims = _valuation_band_conflict(text)
    assert len(claims) == 1
    assert "realized coverage" in claims[0].claim


def test_bands_are_registered_as_isolated_metric_families():
    """A crash in one family must not delete the rest of the payload."""
    claims, errors = _text_metrics(
        "valuation band X (nominal 90%): [1.0, 2.0]\n"
        "disclosure tone X: tone=-0.01\nManagement language sounded confident.\n"
    )
    assert errors == []
    assert {c.status for c in claims} == {"INTERNAL_CONFLICT"}
    assert any("band" in c.claim for c in claims)
    assert any("confident" in c.claim for c in claims)
