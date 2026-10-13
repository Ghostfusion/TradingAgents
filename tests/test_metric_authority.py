"""Guards for the metric authority registry (design doc §3/§4/§7).

The subject is the registry's *claim about the tree*: what it declares, what it
refuses, and that a renamed producer fails a build rather than a report. Every
assertion below is written to be discriminable - each was checked to go red under
a mutation of the code it pins.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies import metric_authority as ma

pytestmark = pytest.mark.timeout(60)


def _row(**over):
    base = {
        "metric": "m",
        "definition": "a measure",
        "definition_version": "m.v1",
        "unit": "ratio",
        "status": "ok",
        "producer_id": "owner.of.m",
        "implementation_ref": "strategies/ratios.py::compute_ratios",
    }
    base.update(over)
    return ma.MetricRow(**base)


# ---------------------------------------------------------------------------
# §7.1 / §7.2 - the manifest's own claims
# ---------------------------------------------------------------------------


def test_no_metric_has_two_authoritative_rows():
    """One metric, one canonical producer - the invariant the registry exists for."""
    assert ma._duplicate_metrics(ma.METRIC_REGISTRY) == {}
    flagged = ma._duplicate_metrics((_row(), _row(producer_id="other.owner")))
    assert flagged == {"m": 2}


def test_every_declared_implementation_ref_resolves():
    """A renamed producer must fail a build, not a report - as forecast_registry does."""
    for row in ma.METRIC_REGISTRY:
        if row.status == "declined":
            continue
        assert ma._resolve_ref(row.implementation_ref) is not None
        for ref in row.fallback:
            assert ma._resolve_ref(ref) is not None
    with pytest.raises(AttributeError):
        ma._resolve_ref("strategies/long_memory.py::no_such_symbol")
    with pytest.raises(ModuleNotFoundError):
        ma._resolve_ref("strategies/definitely_not_a_module.py::nope")


def test_producer_ids_are_stable_and_never_code_paths():
    for row in ma.METRIC_REGISTRY:
        if row.status == "declined":
            continue
        assert ".py" not in row.producer_id and "::" not in row.producer_id
    with pytest.raises(ma.MetricAuthorityError):
        _row(producer_id="strategies/long_memory.py::rv_forecast")


def test_a_non_ok_row_must_name_both_producer_and_location():
    with pytest.raises(ma.MetricAuthorityError):
        _row(implementation_ref=None)
    with pytest.raises(ma.MetricAuthorityError):
        _row(producer_id=None)
    with pytest.raises(ma.MetricAuthorityError):
        _row(implementation_ref="strategies/long_memory.py")  # not <path>::<symbol>


def test_every_admitted_row_carries_a_basis():
    """A basis the reader can see is the point - a number with no basis is the defect."""
    for row in ma.METRIC_REGISTRY:
        if row.status != "declined":
            assert (row.basis or "").strip()


# ---------------------------------------------------------------------------
# §7.3 - the cited refusal
# ---------------------------------------------------------------------------


def test_a_declined_row_is_a_code_and_a_citation_and_nothing_else():
    declined = ma.MetricRow(
        metric="m",
        definition="a measure",
        definition_version="m.v1",
        unit="ratio",
        status="declined",
        reason_code="OWNER_BASIS_DECISION_PENDING",
        citation="design doc §9",
    )
    assert declined.producer_id is None and declined.basis is None
    with pytest.raises(ma.MetricAuthorityError):  # no citation
        _row(status="declined", reason_code="OWNER_BASIS_DECISION_PENDING",
             producer_id=None, implementation_ref=None)
    with pytest.raises(ma.MetricAuthorityError):  # free prose is not a code
        _row(status="declined", reason_code="BECAUSE", citation="x",
             producer_id=None, implementation_ref=None)
    with pytest.raises(ma.MetricAuthorityError):  # a refusal produces nothing
        _row(status="declined", reason_code="OWNER_BASIS_DECISION_PENDING",
             citation="x")


# ---------------------------------------------------------------------------
# §7.4 - the refusals
# ---------------------------------------------------------------------------


def test_resolve_metric_refuses_and_never_returns_zero():
    unknown = ma.resolve_metric("not_a_metric")
    assert unknown["status"] == "unknown"
    assert unknown["value"] is None
    # a declaration lookup names the producer and invents no value
    declaration = ma.resolve_metric("p_e")
    assert declaration["status"] == "ok" and declaration["value"] is None
    # the producer of record supplied nothing -> unavailable, never 0.0
    absent = ma.resolve_metric("p_e", values={"some_vendor": 20.33})
    assert absent["status"] == "unavailable"
    assert absent["value"] is None and absent["value"] != 0.0


# ---------------------------------------------------------------------------
# §7.5 / §7.6 - the canonical is named, the conflict is visible
# ---------------------------------------------------------------------------


def test_a_conflicting_secondary_is_visible_and_the_canonical_is_still_named():
    out = ma.resolve_metric(
        "p_e",
        values={"ratios.compute_ratios": 30.01, "vendor.yfinance.trailingPE": 20.33},
    )
    assert out["status"] == "conflict"
    assert out["value"] == 30.01
    assert out["producer_id"] == "ratios.compute_ratios"
    assert [c["source"] for c in out["conflicts"]] == ["vendor.yfinance.trailingPE"]
    assert out["spread_pct"] > ma.METRIC_TOLERANCE_PCT
    # inside the 1% band it is the same number, not a conflict
    same = ma.resolve_metric(
        "p_e", values={"ratios.compute_ratios": 30.01, "vendor": 30.02}
    )
    assert same["status"] == "ok" and same["conflicts"] == []


def test_the_three_cvar_readings_are_distinguishable_by_name():
    """The 2026-10-12 review's "one metric, two values" defect, at the registry.

    The decision-binding name CVaR and the market analyst's tail read became the
    SAME calculation on 2026-10-12 (one series, one convention), so passing two
    values under one metric id still names the canonical producer and now shows a
    spread as a DEFECT rather than as two bases to disclose. The book leg is its
    own metric id, so it can never be read as the candidate's risk.
    """
    out = ma.resolve_metric(
        "analyzed_name_cvar",
        values={"risk_context.single_cvar": 0.1468, "tool.tail_risk.cvar": 0.1242},
    )
    assert out["status"] == "conflict"
    assert out["value"] == 0.1468  # the gate's producer, not the analyst's read
    assert out["producer_id"] == "risk_context.single_cvar"
    assert [c["source"] for c in out["conflicts"]] == ["tool.tail_risk.cvar"]
    assert out["spread_pct"] > ma.METRIC_TOLERANCE_PCT

    book = ma.resolve_metric("book_cvar", values={"risk_context.book_cvar": 0.0102})
    assert book["status"] == "ok" and book["value"] == 0.0102
    assert "basket" in (book["basis"] or "")
    # The tail read carries its own id and its own window in the basis.
    tail = ma.resolve_metric("tail_read_cvar", values={"tool.tail_risk.cvar": 0.1242})
    assert tail["status"] == "ok" and "BARS" in (tail["basis"] or "")
    # v2 of both rows, and each says the two must agree (they are one
    # measurement now, so a spread is a defect and not a basis).
    name_row = next(r for r in ma.METRIC_REGISTRY if r.metric == "analyzed_name_cvar")
    assert name_row.definition_version == "cvar_1d95.v2"
    assert "AGREE" in (name_row.basis or "").upper()
    assert "_pit_closes" in (name_row.basis or "")
    assert tail["definition_version"] == "cvar_1d95.v2"
    # The candidate-inclusive book is its OWN id: it is the leg the governor
    # reads whenever a size was measured, and the configured reference can never
    # be mistaken for it.
    cand = ma.resolve_metric(
        "candidate_book_cvar", values={"risk_context.candidate_cvar": 0.0410}
    )
    assert cand["status"] == "ok" and cand["value"] == 0.0410
    assert cand["producer_id"] == "risk_context.candidate_cvar"
    assert "weight 0" in (cand["basis"] or "")
    book_row = next(r for r in ma.METRIC_REGISTRY if r.metric == "book_cvar")
    assert "candidate_book_cvar" in (book_row.basis or "")


def test_the_published_value_is_the_canonical_producer_never_the_other():
    """The two-P/Es defect, pinned: the flattering value is never the one published."""
    out = ma.resolve_metric(
        "p_e",
        values={"vendor.yfinance.trailingPE": 20.33, "ratios.compute_ratios": 30.01},
    )
    assert out["value"] == 30.01
    assert out["producer_id"] == "ratios.compute_ratios"


# ---------------------------------------------------------------------------
# §7.7 - the fail-closed gate
# ---------------------------------------------------------------------------


def test_the_gate_off_is_unchanged_and_on_fails_closed():
    off = {"enable_metric_authority": False}
    on = {"enable_metric_authority": True}
    # OFF: declared statuses, exactly as without a config.
    assert ma.resolve_metric("not_a_metric", config=off)["status"] == "unknown"
    assert ma.resolve_metric("entry_ceiling", config=off)["status"] == "ok"
    # ON: a metric with no named, registered producer cannot publish a value.
    blocked = ma.resolve_metric("not_a_metric", config=on)
    assert blocked["status"] == "unavailable" and blocked["value"] is None
    # ON: a named, registered producer keeps its normal value.
    assert ma.resolve_metric("entry_ceiling", config=on)["status"] == "ok"
    pinned = ma.resolve_metric("p_e", config=on, values={"ratios.compute_ratios": 30.01})
    assert pinned["value"] == 30.01 and pinned["status"] == "ok"


def test_the_gate_ships_off():
    """The fail-closed switch is off in the shipped defaults (the acceptance bar)."""
    import tradingagents.default_config as dc

    assert dc.SHIPPED_DEFAULTS["enable_metric_authority"] is False


# ---------------------------------------------------------------------------
# The reconciliation policy (owner review 2026-10-13, "multiple data
# providers"): Rule 1 (comparability), Rule 2 (validity), Rule 5 (materiality)
# and the canonical record. Each case is behaviour the review names, plus the
# two this repo actually hit in production.
# ---------------------------------------------------------------------------


def _obs(**over):
    base = {
        "source": "src.a",
        "metric": "m",
        "value": 1.0,
        "unit": "ratio",
        "scale": "one",
        "basis_group": "g",
    }
    base.update(over)
    return ma.Observation(**base)


def test_a_percent_scaled_field_is_not_a_conflict_once_its_scale_is_declared():
    """Rule 1, the measured case: AEM's vendor D/E is percent-scaled (1.12)
    while the engine's own is a ratio (0.0130) - one unit, not one disagreement."""
    a = _obs(source="vendor", value=1.12, scale="percent")
    b = _obs(source="engine", value=0.0112)
    rec = ma.reconcile_observations("m", [a, b], reconciled_at="T")
    assert rec["status"] == "accepted"
    assert rec["candidates"][0]["normalized"] == pytest.approx(0.0112)
    assert rec["value"] == pytest.approx(0.0112)


def test_two_units_that_are_not_convertible_are_a_definition_mismatch():
    """Rule 1: an unconvertible unit is never compared as a provider conflict."""
    rec = ma.reconcile_observations(
        "m",
        [_obs(value=1.0, unit="usd"), _obs(source="b", value=1.0, unit="ratio")],
        reconciled_at="T",
    )
    assert rec["status"] == "definition_mismatch"
    assert rec["reason_code"] == "SOURCES_NOT_COMPARABLE"
    assert rec["definition_mismatches"][0]["reason_code"] == "UNIT_NOT_CONVERTIBLE"


def test_two_declared_bases_keep_the_majority_measurement_and_name_the_other():
    """The D/E case post-fix: the engine's two computed readings (0.06, 0.0552)
    are one measurement, the vendor's is a DIFFERENT one - so the number
    published is the comparable group's, and it is never called a range."""
    rec = ma.reconcile_observations(
        "m",
        [
            _obs(source="vendor", value=0.0562, decimals=4, basis_group="vendor_reported"),
            _obs(source="engine.ratios", value=0.06, decimals=2, basis_group="engine_computed"),
            _obs(source="engine.health", value=0.0552, decimals=4, basis_group="engine_computed"),
        ],
        reconciled_at="T",
    )
    assert rec["status"] == "definition_mismatch"
    assert rec["value"] == 0.06
    assert [m["source"] for m in rec["definition_mismatches"]] == ["vendor"]
    assert rec["rounding_applied"] is True


def test_the_declared_precision_decides_a_rounding_disagreement():
    """Rule 5: 8.7% apart is the SAME number when one side printed 2 decimals."""
    cmp_ = ma.compare_observations(
        _obs(value=0.06, decimals=2), _obs(source="b", value=0.0552, decimals=4)
    )
    assert cmp_["within"] is True and cmp_["rounding_applied"] is True
    assert cmp_["deviation_pct"] > 0.01
    # ...and the same pair printed precisely stays a disagreement.
    cmp_ = ma.compare_observations(
        _obs(value=0.0600, decimals=4), _obs(source="b", value=0.0552, decimals=4)
    )
    assert cmp_["within"] is False


def test_a_literal_precision_beats_the_float_it_parses_to():
    """`0.10` was printed to two decimals even though its float is `0.1`."""
    assert ma.declared_decimals("0.10") == 2
    assert ma.declared_decimals("250.27") == 2
    assert ma.declared_decimals("1,234,567") == 0
    assert ma.declared_decimals(0.1 + 0.2) is None


def test_an_invalid_canonical_source_falls_back_and_names_the_rejection():
    """Rule 2/4: authority does not exempt a value from the checks."""
    rec = ma.reconcile_observations(
        "p_e",
        [
            ma.Observation(
                source="ratios.compute_ratios",
                metric="p_e",
                value=float("nan"),
                unit="ratio",
            ),
            ma.Observation(
                source="vendor.yfinance.trailingPE",
                metric="p_e",
                value=20.33,
                unit="ratio",
            ),
        ],
        reconciled_at="T",
    )
    assert rec["status"] == "fallback"
    assert rec["reason_code"] == "CANONICAL_INVALID"
    assert rec["value"] == 20.33
    assert rec["selected_source"] == "vendor.yfinance.trailingPE"
    assert rec["rejected"][0]["reason_code"] == "NOT_FINITE"
    assert rec["rejected"][0]["source"] == "ratios.compute_ratios"


def test_a_value_beyond_the_declared_cap_is_rejected_not_clamped():
    rec = ma.reconcile_observations(
        "m", [_obs(value=12.5)], cap=10.0, reconciled_at="T"
    )
    assert rec["status"] == "unavailable"
    assert rec["reason_code"] == "NO_VALID_OBSERVATION"
    assert rec["value"] is None
    assert rec["rejected"][0]["reason_code"] == "ABOVE_PLAUSIBLE_CAP"


def test_an_undeclared_scale_is_never_assumed_to_be_one():
    rec = ma.reconcile_observations(
        "m", [ma.Observation(source="a", metric="m", value=1.0, scale="weird")], reconciled_at="T"
    )
    assert rec["status"] == "unavailable"
    assert rec["rejected"][0]["reason_code"] == "UNIT_UNDECLARED"


def test_a_stale_observation_is_rejected_under_a_declared_staleness_policy():
    rec = ma.reconcile_observations(
        "m",
        [_obs(source="old", as_of="2026-01-01"), _obs(source="fresh", value=1.0, as_of="2026-10-13")],
        as_of="2026-10-13",
        max_staleness_days=5,
        reconciled_at="T",
    )
    assert rec["staleness_checked"] is True
    assert {r["source"]: r["reason_code"] for r in rec["rejected"]} == {"old": "STALE_BEYOND_POLICY"}


def test_no_authority_publishes_nothing_when_the_sources_disagree():
    """Rule 6: with no registered producer there is nothing to break the tie
    with, so the disagreement stands and NO value is published."""
    rec = ma.reconcile_observations(
        "market_snapshot",
        [_obs(source="a", value=248.81), _obs(source="b", value=260.00)],
        reconciled_at="T",
    )
    assert rec["status"] == "conflict"
    assert rec["reason_code"] == "NO_AUTHORITY"
    assert rec["value"] is None
    assert rec["disagreement"]["spread_pct"] > 0.04


def test_agreement_without_two_declared_upstreams_is_not_independent_confirmation():
    """The review's §4 warning: two vendors on one upstream are not two votes."""
    same = ma.reconcile_observations(
        "m",
        [_obs(source="a", upstream="yahoo"), _obs(source="b", value=1.0, upstream="yahoo")],
        reconciled_at="T",
    )
    assert same["independent_confirmation"] is False
    undeclared = ma.reconcile_observations(
        "m", [_obs(source="a"), _obs(source="b", value=1.0)], reconciled_at="T"
    )
    assert undeclared["independent_confirmation"] is False
    distinct = ma.reconcile_observations(
        "m",
        [_obs(source="a", upstream="yahoo"), _obs(source="b", value=1.0, upstream="finnhub")],
        reconciled_at="T",
    )
    assert distinct["independent_confirmation"] is True
    assert distinct["independent_upstreams"] == ["finnhub"]


def test_no_observation_at_all_is_unknown_never_zero():
    rec = ma.reconcile_observations("m", [], reconciled_at="T")
    assert rec["status"] == "unknown" and rec["reason_code"] == "NO_OBSERVATION"
    assert rec["value"] is None


def test_undeclared_semantics_are_reported_never_assumed():
    rec = ma.reconcile_observations(
        "m",
        [_obs(source="a", unit=None, basis_group=None), _obs(source="b", value=1.0)],
        reconciled_at="T",
    )
    assert rec["semantics_undeclared"] is True


def test_the_reconciliation_vocabularies_are_closed():
    assert set(ma.RECONCILE_STATUSES) == {
        "accepted", "fallback", "conflict", "definition_mismatch", "unavailable", "unknown",
    }
    # UNIT_UNDECLARED is the one code that is BOTH a mismatch (no common unit to
    # compare on) and an invalidity (a value that cannot be placed on its unit).
    assert set(ma.SEMANTIC_MISMATCH_CODES) & set(ma.INVALID_REASON_CODES) == {"UNIT_UNDECLARED"}
    assert set(ma.RECONCILE_REASON_CODES).isdisjoint(ma.INVALID_REASON_CODES)
