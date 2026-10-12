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
