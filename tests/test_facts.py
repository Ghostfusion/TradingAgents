"""The Fact layer: a number, its qualifiers, and the rule that produced it.

The three defects the layer was built for are the fixtures here:

1. **coverage** - Piotroski's 3-of-9 read published as "3" (GMED 2026-10-14);
   ``derive`` keeps the partial value but marks the Fact not usable and names
   the withheld inputs, so a consumer cannot mistake it for a measurement.
2. **period** - the DCF bridge that read FY2025-12-31 while 2026-06-30 sat in
   the payload; every Fact carries the period its provenance recorded, and a
   period it cannot state stays unstated rather than borrowed.
3. **availability** - the 2026/Q3 Form 13F aggregate on 2026-10-14, whose
   filings are not due until 2026-11-16; a Fact knows whether a FILED basis for
   its period can exist.

And the one rule that keeps them from being re-authored per leaf: a Fact is
resolved from the SAME canonical/provenance pair the leaf consumed, never from a
second fetch (two consecutive pulls for GMED 2026-10-14 returned different
payload sets and moved P/E 19.05 -> 19.14).
"""

import pytest

from tradingagents.strategies.facts import (
    COVERAGE_RULES,
    FACT_UNITS,
    UNIT_LABELS,
    Fact,
    FactCoverage,
    FactError,
    basis_line,
    coverage_note,
    derive,
    fact_from_provenance,
    fact_layer_on,
    latest,
    prior,
    render_fact,
    resolve_facts,
)

pytestmark = pytest.mark.timeout(60)

PERIOD = {"source": "get_balance_sheet", "basis": "annual", "period": "2026-06-30",
          "observed_kind": "unstated", "basis_conflict": False}
PROV = {
    "cash_and_investments": dict(PERIOD),
    "total_debt": dict(PERIOD),
    "total_assets": dict(PERIOD),
    "net_income": {
        "source": "get_income_statement",
        "basis": "annual",
        "period": "2026-06-30",
        "observed_kind": "unstated",
        "basis_conflict": False,
    },
    "market_cap": {"source": "get_fundamentals", "basis": "info", "period": None,
                   "observed_kind": "unstated", "basis_conflict": False},
}
FIN = {
    "cash_and_investments": 595_140_000.0,
    "total_debt": 111_190_000.0,
    "total_assets": {"current": 9_000_000_000.0, "prior": 8_800_000_000.0},
    "net_income": 933_000_000.0,
    "market_cap": 10_245_000_000.0,
    "sector": "Healthcare",
    "currency": "USD",
    "revenue_series": [1.0, 2.0, 3.0],
}


def test_latest_and_prior_are_the_one_reader_of_the_current_prior_shape():
    assert latest({"current": 5.0, "prior": 4.0}) == 5.0
    assert prior({"current": 5.0, "prior": 4.0}) == 4.0
    assert latest({"value": 7.0}) == 7.0
    assert latest(3.5) == 3.5
    assert prior(3.5) is None
    assert latest(None) is None
    assert prior(None) is None


def test_a_resolved_fact_carries_its_period_unit_and_source():
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    fact = facts["cash_and_investments"]
    assert fact.value == 595_140_000.0
    assert fact.unit == "usd" == FACT_UNITS["cash_and_investments"]
    assert fact.period_end == "2026-06-30"
    assert fact.source == "get_balance_sheet"
    assert fact.basis_text == "annual"
    assert fact.usable is True
    assert fact.filed_basis is True  # 10-Q for a 2026-06-30 quarter was due 2026-08-14


def test_resolve_facts_skips_the_currency_marker_and_a_stacked_series():
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    assert "currency" not in facts
    assert "revenue_series" not in facts
    assert set(facts) == {
        "cash_and_investments",
        "total_debt",
        "total_assets",
        "net_income",
        "market_cap",
        "sector",
    }


def test_resolve_facts_keeps_the_prior_leg_on_the_same_fact():
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    assert facts["total_assets"].value == 9_000_000_000.0
    assert facts["total_assets"].prior_value == 8_800_000_000.0
    assert "prior" in render_fact(facts["total_assets"])


def test_a_key_with_no_provenance_row_states_unknown_rather_than_borrowing():
    fact = fact_from_provenance("cash", 1.0, None, as_of="2026-10-14")
    assert fact.source == "unknown source"
    assert fact.period_end is None
    assert fact.availability_state == "unknown"
    assert fact.unit == "usd"  # the unit is declared by the registry, not the payload


def test_a_basis_conflict_is_recorded_on_the_fact_and_named_in_the_basis_line():
    prov = dict(PROV)
    prov["net_income"] = {
        "source": "get_income_statement",
        "basis": "annual",
        "period": "2026/Q2",
        "observed_kind": "quarterly",
        "basis_conflict": True,
    }
    facts = resolve_facts(FIN, prov, as_of="2026-10-14")
    assert facts["net_income"].basis_conflict is True
    assert "BASIS CONFLICT: net_income" in basis_line(facts, ["net_income"])


def test_a_missing_value_is_not_usable_and_says_missing():
    fact = fact_from_provenance("total_debt", None, PROV["total_debt"], as_of="2026-10-14")
    assert fact.usable is False
    assert fact.invalid_reason == "MISSING"
    assert "MISSING" in render_fact(fact)


def test_a_not_finite_value_is_not_usable():
    fact = fact_from_provenance("total_debt", float("nan"), PROV["total_debt"])
    assert fact.usable is False
    assert fact.invalid_reason == "NOT_FINITE"


def test_a_partial_derivation_keeps_its_value_but_is_not_usable():
    """The Piotroski case: 3 of 9 signals computable. The number is published
    (the owner already publishes it) WITH its coverage - and it may not be
    consumed as a measurement."""
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    partial = derive(
        "f_score",
        {"f_roa": True, "f_cfo": True, "f_droa": True, "f_eq": None},
        lambda measured: sum(1 for v in measured.values() if v),
        unit="score",
        coverage_rule="floor",
        required=9,
    )
    assert partial.value == 3
    assert partial.usable is False
    assert partial.invalid_reason == "COVERAGE_INCOMPLETE"
    assert partial.coverage.n_of == 3
    assert partial.coverage.required == 9
    assert partial.coverage.withheld == ("f_eq",)
    note = coverage_note(partial)
    assert "PARTIAL" in note and "3 of 9" in note and "f_eq" in note
    assert facts["cash_and_investments"].usable is True


def test_derive_all_requires_every_declared_input():
    inputs = {"a": 1.0, "b": 2.0, "c": None}
    out = derive("x", inputs, lambda m: sum(m.values()), coverage_rule="all")
    assert out.coverage.n_of == 2
    assert out.coverage.required == 3
    assert out.coverage.satisfied is False
    assert out.usable is False
    assert out.coverage.withheld == ("c",)


def test_derive_any_needs_one_input():
    out = derive("x", {"a": None, "b": 2.0}, lambda m: sum(m.values()), coverage_rule="any")
    assert out.coverage.required == 1
    assert out.coverage.satisfied is True
    assert out.usable is True


def test_derive_counts_a_fact_input_by_its_usability_not_its_presence():
    """A Fact that is present but PARTIAL is a withheld input: that is how one
    composite's coverage propagates into the next."""
    good = Fact(source="s", metric="a", value=1.0, unit="usd")
    partial = Fact(
        source="s",
        metric="b",
        value=2.0,
        unit="usd",
        coverage=FactCoverage(n_of=1, required=3, withheld=("x", "y")),
        invalid_reason="COVERAGE_INCOMPLETE",
    )
    out = derive("c", {"a": good, "b": partial}, lambda m: sum(m.values()))
    assert out.coverage.n_of == 1
    assert out.coverage.withheld == ("b",)
    assert out.derivation == ("a", "b")


def test_derive_rejects_an_unknown_rule():
    with pytest.raises(FactError):
        derive("x", {"a": 1.0}, lambda m: 1.0, coverage_rule="most")
    assert COVERAGE_RULES == ("all", "any", "floor")


def test_derive_can_decline_to_claim_a_single_period():
    """A derivation over mixed bases must not inherit the one label its inputs
    happen to agree on (the DCF: a TTM cash-flow series plus a quarterly bridge)."""
    a = fact_from_provenance("cash", 1.0, PROV["cash_and_investments"], as_of="2026-10-14")
    b = fact_from_provenance("total_debt", 2.0, PROV["total_debt"], as_of="2026-10-14")
    claimed = derive("x", {"a": a, "b": b}, lambda m: 3.0)
    assert claimed.period_label == "2026-06-30"
    declined = derive("x", {"a": a, "b": b}, lambda m: 3.0, claim_period=False)
    assert declined.period_label is None


def test_a_derivation_that_raises_over_a_partial_set_is_missing_not_a_crash():
    def boom(_measured):
        raise ZeroDivisionError

    out = derive("x", {"a": None}, boom)
    assert out.value is None
    assert out.invalid_reason == "MISSING"


def test_render_fact_states_value_unit_period_and_source():
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    line = render_fact(facts["cash_and_investments"])
    assert line.startswith("cash_and_investments: 595,140,000 usd (")
    assert "2026-06-30" in line
    assert "get_balance_sheet" in line


def test_render_fact_says_unit_undeclared_rather_than_omitting_it():
    fact = Fact(source="s", metric="mystery", value=1.5)
    assert "unit undeclared" in render_fact(fact)


def test_render_fact_names_a_not_yet_filed_period():
    fact = fact_from_provenance(
        "total_assets",
        1.0,
        {"source": "get_balance_sheet", "basis": "quarterly", "period": "2026-09-30",
         "observed_kind": "quarterly", "basis_conflict": False},
        as_of="2026-10-14",
    )
    assert fact.availability_state == "not_yet_due"
    assert fact.filed_basis is False
    line = render_fact(fact)
    assert "NOT FILED YET" in line
    assert "2026-11-16" in line


def test_basis_line_groups_by_period_and_source_and_names_the_missing_keys():
    facts = resolve_facts(FIN, PROV, as_of="2026-10-14")
    line = basis_line(facts, ["cash_and_investments", "total_debt", "net_income", "beta"])
    assert "cash_and_investments/total_debt 2026-06-30 (get_balance_sheet)" in line
    assert "net_income 2026-06-30 (get_income_statement)" in line
    assert "NOT SUPPLIED BY THE CHAIN: beta" in line


def test_basis_line_with_no_facts_at_all_still_states_the_period_is_unstated():
    assert "period unstated" in basis_line({}, ["revenue"])


def test_basis_line_names_a_partial_and_an_unfiled_key():
    partial = Fact(
        source="derived",
        metric="f_score",
        value=3.0,
        unit="score",
        coverage=FactCoverage(n_of=3, required=9, withheld=("f_eq",)),
    )
    unfiled = fact_from_provenance(
        "total_assets",
        1.0,
        {
            "source": "get_balance_sheet",
            "basis": "quarterly",
            "period": "2026-09-30",
            "observed_kind": "quarterly",
            "basis_conflict": False,
        },
        as_of="2026-10-14",
    )
    line = basis_line({"f_score": partial, "total_assets": unfiled}, ["f_score", "total_assets"])
    assert "PARTIAL: f_score (3 of 9 inputs measured; missing: f_eq)" in line
    assert "NOT FILED YET: total_assets" in line


def test_the_fact_layer_ships_off_and_reads_its_gate(monkeypatch):
    from tradingagents.dataflows.config import reset_config, set_config

    reset_config()
    assert fact_layer_on() is False
    try:
        set_config({"enable_fact_layer": True})
        assert fact_layer_on() is True
    finally:
        reset_config()


def test_the_unit_vocabulary_is_closed():
    assert set(FACT_UNITS.values()) <= set(UNIT_LABELS)
    assert len(FACT_UNITS) == len(set(FACT_UNITS))
