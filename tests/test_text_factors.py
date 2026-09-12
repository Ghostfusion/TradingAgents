"""Q6 — disclosure text factors: tone, readability, cross-document divergence.

Docs: ``docs/design_quant_formulas_research_round2.md`` item N6;
``docs/implementation_plan_quant_formula_additions.md`` phase Q6.
"""

from __future__ import annotations

from tradingagents.strategies.text_factors import (
    DICTIONARY_VERSION,
    divergence,
    lm_tone,
    readability,
)

POSITIVE_PASSAGE = (
    "Revenue growth exceeded expectations and the company delivered strong "
    "results, improved margins and record profitability. Management is confident "
    "about the opportunity and expects to outperform last year."
)

NEGATIVE_PASSAGE = (
    "The company reported a significant loss and a material impairment charge, "
    "announced restructuring and litigation risks, and management expressed "
    "concern about continued weakness and a possible shortfall."
)

# Equal word and sentence counts on purpose: at equal length the only thing that
# can move the readability scores is word complexity, so a broken syllable term
# cannot hide behind a length difference.
SIMPLE_12 = "The firm made big gains and the stock rose on strong sales"
DENSE_12 = (
    "Notwithstanding the capitalization amortization depreciation impairment "
    "remeasurement methodologies the consolidated recalcitrance predominate"
)


def test_tone_orders_a_positive_and_a_negative_passage():
    pos = lm_tone(POSITIVE_PASSAGE)
    neg = lm_tone(NEGATIVE_PASSAGE)
    assert pos is not None and neg is not None
    assert pos["tone"] > 0
    assert neg["tone"] < 0
    assert pos["tone"] > neg["tone"]
    assert pos["positive"] > 0 and neg["negative"] > 0
    # The counts and the dictionary version are always carried.
    assert pos["dictionary"] == DICTIONARY_VERSION
    assert pos["words"] > 0 and "seed" in pos["basis"] or DICTIONARY_VERSION in pos["basis"]


def test_no_dictionary_hits_is_reported_as_zero_hits_not_neutral():
    """Absence of signal is not neutrality: 0.0 would read as 'balanced'."""
    read = lm_tone("the and of to a an it this that")
    assert read is not None
    assert read["hits"] == 0
    assert read["zero_hits"] is True
    assert read["tone"] is None


def test_readability_is_driven_by_word_complexity_at_equal_length():
    simple = readability(SIMPLE_12)
    dense = readability(DENSE_12)
    assert simple is not None and dense is not None
    assert simple["words"] == dense["words"] == 12
    assert simple["sentences"] == dense["sentences"] == 1
    assert simple["reading_ease"] > dense["reading_ease"]
    assert simple["fog"] < dense["fog"]
    assert simple["fk_grade"] < dense["fk_grade"]


def test_divergence_keeps_the_two_channels_separate():
    """Tone and complexity diverge independently (different persistence)."""
    # First document: positive tone AND simple prose; second: negative AND dense.
    read = divergence(POSITIVE_PASSAGE, NEGATIVE_PASSAGE)
    assert read is not None
    assert read["tone_gap"] > 0
    assert read["tone_direction"] == "a_more_positive"
    assert read["complexity_direction"] in ("a_more_complex", "b_more_complex", "equal")
    # A pair where tone agrees but complexity does not must still report the gap.
    read2 = divergence(SIMPLE_12, DENSE_12)
    assert read2 is not None
    assert read2["complexity_gap"] < 0
    assert read2["complexity_direction"] == "b_more_complex"


def test_divergence_requires_two_measured_tones():
    """One side with no signal must not read as 'the documents agree'."""
    assert divergence(POSITIVE_PASSAGE, "the and of to a an it this that") is None
    assert divergence(POSITIVE_PASSAGE, "") is None


def test_degenerate_text_returns_none():
    for bad in ("", "   ", "\n\t", "12 34 56", "!!! ???"):
        assert lm_tone(bad) is None, bad
        assert readability(bad) is None, bad
    assert divergence("", POSITIVE_PASSAGE) is None
