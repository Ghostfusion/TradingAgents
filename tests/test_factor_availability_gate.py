"""H2: the availability-typed factor DSL gate.

Look-ahead is made *inexpressible* rather than discouraged: the registration-time
AST gate refuses both a forward shift and any field whose declared observability
class is later than the decision date, so a pure-but-not-causal expression never
reaches the evaluator. Static analysis only - the cost is paid at admission, not
per run.

Mutation to prove the failing-first test can fail: delete the
``if shifts: return False, ...`` branch of
``factor_expressions.availability_gate``; the forward-shift assertion in
``test_late_availability_field_rejected`` goes red by name.
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows.pit_registry import store_snapshot
from tradingagents.strategies.alpha_zoo import _COLUMNS, purity_gate
from tradingagents.strategies.factor_expressions import availability_gate
from tradingagents.strategies.factor_schema import (
    FACTOR_SCHEMA,
    FILING_DATE,
    MACRO_RELEASE_LAG,
    MARKET_CLOSE_FIELDS,
    NEXT_SESSION,
    PRESENT,
    SESSION_CLOSE,
    FactorSpec,
    observability_for,
    validate_schema,
)

pytestmark = pytest.mark.timeout(30)


def _on() -> dict:
    return {"enable_factor_availability_gate": True}


def _off() -> dict:
    return {"enable_factor_availability_gate": False}


def test_late_availability_field_rejected():
    """A field unobservable at the decision date, and a forward shift, are both
    refused at registration time - before either can run.

    Removing the forward-shift rejection fails this test by name.
    """
    late = {"eps_yoy": {"class": FILING_DATE, "as_of": "2025-06-15"}}

    # (a) the field's declared availability is LATER than the decision date
    ok, reason = availability_gate(
        "pct_change(eps_yoy, 4)", declared=late,
        decision_date="2025-05-01", cfg=_on(),
    )
    assert not ok, "a field filed after the decision date must be refused"
    assert "later than the decision date" in reason

    # the same declaration is admitted once the decision date follows the filing
    ok_late, _ = availability_gate(
        "pct_change(eps_yoy, 4)", declared=late,
        decision_date="2025-07-01", cfg=_on(),
    )
    assert ok_late

    # (b) a forward shift reads the future whatever the fields are
    ok_shift, reason_shift = availability_gate("ref(close, -1)", cfg=_on())
    assert not ok_shift, "a negative shift reads the future and must be refused"
    assert "forward shift" in reason_shift

    # ...and the zoo's own verdict on that expression is unchanged
    assert purity_gate("ref(close, -1)")[0]


def test_gate_off_leaves_every_expression_as_it_was():
    """Default off: the gate adds no refusal, so an unregistered gate cannot
    change the zoo's admission behaviour."""
    assert availability_gate("ref(close, -1)", cfg=_off()) == (True, "")
    assert availability_gate("close", cfg=_off()) == (True, "")
    assert availability_gate("__import__('os')", cfg=_off()) == purity_gate(
        "__import__('os')")


def test_undeclared_field_fails_closed():
    """A field with no declared availability is refused with its reason, never
    assumed safe (H8's per-field lag table is not built)."""
    ok, reason = availability_gate(
        "pct_change(mystery_factor, 4)",
        declared={"mystery_factor": None}, cfg=_on(),
    )
    assert not ok and "no declared observability class" in reason

    # a name outside both the market columns and the schema is refused by the
    # gate's vocabulary, i.e. it cannot even be named
    ok_unknown, reason_unknown = availability_gate("pct_change(news_tone, 4)", cfg=_on())
    assert not ok_unknown and "unknown name" in reason_unknown


def test_classes_that_are_later_than_a_session_close_decision_are_refused():
    """``next_session`` is after a decision taken at this session's close; a
    dated macro class is measured against its declared release date."""
    ok, reason = availability_gate(
        "mean(close, 5)", declared={"close": {"class": NEXT_SESSION}}, cfg=_on(),
    )
    assert not ok and "not observable until the next session" in reason

    macro = {"cpi_yoy": {"class": MACRO_RELEASE_LAG, "as_of": "2025-05-20"}}
    ok_macro, reason_macro = availability_gate(
        "mean(cpi_yoy, 3)", declared=macro, decision_date="2025-05-01", cfg=_on(),
    )
    assert not ok_macro and "later than the decision date" in reason_macro

    # a class that needs a date, given none, is refused rather than assumed
    ok_nodate, reason_nodate = availability_gate(
        "mean(eps_yoy, 3)",
        declared={"eps_yoy": {"class": FILING_DATE}},
        decision_date="2025-05-01", cfg=_on(),
    )
    assert not ok_nodate and "no as_of date" in reason_nodate


def test_a_declaration_names_the_pit_vintage_it_rests_on(tmp_path):
    """A declaration that names a symbol is corroborated by
    ``pit_registry.read_as_of``: no vintage visible at the decision date means
    the declaration cannot be placed and is refused."""
    decl = {"eps_yoy": {"class": FILING_DATE, "as_of": "2024-11-01", "symbol": "AAPL"}}
    root = str(tmp_path)
    ok, reason = availability_gate(
        "pct_change(eps_yoy, 4)", declared=decl, decision_date="2025-05-01",
        pit_root=root, cfg=_on(),
    )
    assert not ok and "no PIT snapshot" in reason

    store_snapshot("AAPL", "2024-11-01", {"eps_yoy": 0.12}, root=root)
    ok_with, _ = availability_gate(
        "pct_change(eps_yoy, 4)", declared=decl, decision_date="2025-05-01",
        pit_root=root, cfg=_on(),
    )
    assert ok_with


def test_the_nine_field_record_carries_the_declaration():
    """The record answers WHEN its value becomes observable, and it still has
    exactly nine fields."""
    spec = FACTOR_SCHEMA["return_on_equity"]
    assert len(FactorSpec._fields) == 9
    assert spec.observability == FILING_DATE
    assert spec.availability == PRESENT  # data presence is untouched
    # the one caller-supplied price field is a quote, i.e. known at session close
    assert FACTOR_SCHEMA["dcf_upside"].observability == SESSION_CLOSE


def test_every_market_column_is_declared_at_session_close():
    """The record's market-field vocabulary and the DSL's columns agree.

    A column added to the engine without a declaration would fail closed, so the
    drift is pinned here rather than discovered as a refusal.
    """
    assert set(MARKET_CLOSE_FIELDS) == set(_COLUMNS)
    for column in _COLUMNS:
        assert observability_for(column) == SESSION_CLOSE


def test_an_undeclared_name_has_no_class_and_the_schema_self_check_passes():
    assert observability_for("not_a_field") is None
    validate_schema()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
