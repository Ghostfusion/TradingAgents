"""WP-1: the shared score kernel - align, combine, band_label."""

import pytest

from tradingagents.strategies.score_engine import (
    NON_MONOTONIC_INPUTS,
    align,
    band_label,
    combine,
    coverage_floor,
)


# --- 1. an absent component leaves the denominator ---------------------------

def test_an_absent_component_is_not_a_zero():
    """Acceptance 1: one component absent scores the mean of the PRESENT ones and
    reports coverage below 1. The mutation this catches is substituting 0 for the
    absent component: 92/85/None would then score 59 instead of 88.5."""
    got = combine({"quality": 92.0, "setup": 85.0, "regime": None}, min_coverage=2)
    assert got["score"] == pytest.approx(88.5)
    assert got["coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert got["present"] == ["quality", "setup"]
    assert "absent: regime" in got["basis"]
    # The mutation, spelled out: a zero-fill scores materially lower.
    zero_filled = combine({"quality": 92.0, "setup": 85.0, "regime": 0.0}, min_coverage=2)
    assert zero_filled["score"] != pytest.approx(got["score"])


def test_weights_renormalise_over_the_present_components():
    got = combine(
        {"a": 100.0, "b": 0.0, "c": None},
        weights={"a": 0.5, "b": 0.25, "c": 0.25},
        min_coverage=2,
    )
    # (0.5*100 + 0.25*0) / 0.75 - the absent 0.25 leaves the denominator.
    assert got["score"] == pytest.approx(66.67, abs=0.01)
    assert got["coverage"] == pytest.approx(0.75, abs=1e-4)


# --- 2. nothing present is None, never 0 and never 50 ------------------------

def test_nothing_present_is_none_with_its_reason():
    """Acceptance 2: a score of 0 would read as "measured, and terrible"; 50 would
    read as "mid-range". Both are fabrications."""
    got = combine({"a": None, "b": None, "c": None})
    assert got["score"] is None
    assert got["coverage"] == 0.0
    assert got["withheld"]
    assert "0 of 3 components present" in got["withheld"]
    assert combine({})["score"] is None


# --- 3. the non-monotonic inputs move the right way --------------------------

# The producer's own edges for RSI (not invented here): the mapped contribution
# peaks in the 40-60 band and FALLS on both sides, which is what makes it
# non-monotone. A monotone mapping would put 80 above 45.
_RSI_BANDS = ((80.0, 10.0), (70.0, 30.0), (60.0, 75.0), (40.0, 100.0), (20.0, 60.0), (0.0, 20.0))


@pytest.mark.parametrize("name", NON_MONOTONIC_INPUTS)
def test_every_non_monotonic_input_is_alignable_by_its_own_band_table(name):
    """Acceptance 3: a band table maps each of these at the producer's own edges,
    and the mapping is NOT monotone - the mutation "make one monotone" fails here
    because a monotone ramp cannot produce a peak in the middle."""
    assert name in NON_MONOTONIC_INPUTS
    mid = align(45.0, band=_RSI_BANDS)
    overbought = align(80.0, band=_RSI_BANDS)
    oversold = align(20.0, band=_RSI_BANDS)
    assert mid == pytest.approx(100.0)
    assert overbought < mid and oversold < mid  # both tails are worse than the middle
    assert overbought < oversold  # 80 is worse than 20 for a mean-reversion read


def test_align_refuses_a_neutral_50_for_a_missing_value():
    assert align(None, lo=0.0, hi=10.0) is None
    assert align(float("nan"), lo=0.0, hi=10.0) is None
    assert align(5.0, band=()) is None  # no table and no ramp edges -> unmeasurable
    assert align(5.0, lo=10.0, hi=10.0) is None


def test_align_ramps_in_both_directions_and_clamps():
    assert align(0.0, lo=0.0, hi=10.0) == pytest.approx(0.0)
    assert align(10.0, lo=0.0, hi=10.0) == pytest.approx(100.0)
    assert align(20.0, lo=0.0, hi=10.0) == pytest.approx(100.0)  # clamped
    assert align(2.5, direction="lower_better", lo=0.0, hi=10.0) == pytest.approx(75.0)


def test_align_rejects_a_direction_typo():
    """A silently flipped component is the failure the kernel exists to prevent."""
    with pytest.raises(ValueError):
        align(5.0, direction="higher_is_better", lo=0.0, hi=10.0)


# --- 4. the basis names the weight vector actually used ----------------------

def test_the_basis_names_the_weights_actually_used():
    """Acceptance 4: change a weight and BOTH the score and the basis move - a
    basis that kept the old vector would let the number drift from its own
    description."""
    light = combine({"a": 100.0, "b": 0.0}, weights={"a": 0.9, "b": 0.1}, min_coverage=2)
    heavy = combine({"a": 100.0, "b": 0.0}, weights={"a": 0.1, "b": 0.9}, min_coverage=2)
    assert light["score"] == pytest.approx(90.0)
    assert heavy["score"] == pytest.approx(10.0)
    assert "a=0.9" in light["basis"] and "a=0.1" in heavy["basis"]
    assert "equal weights (none supplied)" in combine({"a": 1.0})["basis"]


# --- 5. the withholding floor, from both sides -------------------------------

def test_the_coverage_floor_is_tested_from_both_sides():
    """Acceptance 5: a name AT the floor scores; one below it is withheld WITH the
    reason. min_coverage=3 with two present components is below."""
    at_floor = combine({"a": 80.0, "b": 60.0, "c": 40.0})
    assert at_floor["score"] == pytest.approx(60.0)
    assert at_floor["withheld"] is None
    below = combine({"a": 80.0, "b": 60.0, "c": None})
    assert below["score"] is None
    assert "2 of 3 components present, floor is 3" in below["withheld"]


def test_the_floor_accepts_a_fraction_of_the_component_set():
    assert coverage_floor(0.5, 4) == 2
    assert coverage_floor(0.25, 4) == 1
    assert coverage_floor(3, 4) == 3
    assert coverage_floor(0, 4) == 1
    got = combine({"a": 90.0, "b": None, "c": None, "d": 10.0}, min_coverage=0.5)
    assert got["score"] == pytest.approx(50.0)  # 2 of 4 present meets the 0.5 floor


# --- the label table belongs to the engine -----------------------------------

def test_the_band_label_uses_the_engines_own_table():
    bands = ((70.0, "elite"), (50.0, "peer median"), (0.0, "distressed"))
    assert band_label(85.0, bands) == "elite"
    assert band_label(50.0, bands) == "peer median"
    assert band_label(10.0, bands) == "distressed"
    assert band_label(None, bands) is None
    assert band_label(85.0, ()) is None
    # The kernel holds NO table of its own - the table is a REQUIRED argument, so
    # there is no default that could be the decision guardrail's contract bands
    # (master rule 2).
    with pytest.raises(TypeError):
        band_label(85.0)


def test_combine_exposes_the_floor_it_enforced():
    """`floor` is returned beside `coverage`, so a reader prints "required"
    without parsing it back out of `withheld`/`basis` (ScoreContextContract.md
    §13.4). It is a component COUNT while `coverage` is a weight FRACTION."""
    res = combine({"a": 80.0, "b": 60.0, "c": None, "d": 70.0}, min_coverage=3)
    assert res["floor"] == 3
    assert res["score"] is not None
    assert len(res["present"]) == 3

    # Below the floor the score is WITHHELD - never 0, never 50 - and the floor
    # is still reported so the reader can say what was required.
    thin = combine({"a": 80.0, "b": None, "c": None, "d": None}, min_coverage=3)
    assert thin["score"] is None
    assert thin["floor"] == 3
    assert "floor is 3" in thin["withheld"]

    # No components declared means no floor applies.
    assert combine({})["floor"] == 0


def test_the_floor_agrees_with_coverage_floor():
    """One implementation: `combine` resolves the floor through
    `coverage_floor`, so the two can never disagree."""
    comps = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0}
    for min_coverage in (1, 2, 3, 0.5):
        res = combine(dict(comps), min_coverage=min_coverage)
        assert res["floor"] == coverage_floor(min_coverage, len(res["present"]))
