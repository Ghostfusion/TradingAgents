"""SecurityContext: deterministic classification metadata, and a prior that cannot gate.

Design: ``docs/design_security_context.md``. Three properties are load-bearing
and each is defended here by behaviour, not by wiring:

1. **Provenance travels with the value.** The repo's four provider legs return
   four different taxonomies under one string, so a sector without its source is
   unusable.
2. **The prior may only widen.** ``candidate_themes`` is a union, so every
   registered theme stays a candidate for every sector - including an unknown
   one. A prior that could exclude would be a decision.
3. **No taxonomy is claimed that the repo does not have.** No field is named
   GICS unless it is GICS, and there is no numeric relevance anywhere.

The validator's cases are tested with *negative* inputs (an unknown theme, an
unknown row, a numeric cell, a cell with no declared basis) because a declared
table that can silently grow a second vocabulary is worse than no table.
"""

from __future__ import annotations

import tradingagents.default_config as dc
from tradingagents.reporting import _run_card_security_context
from tradingagents.strategies.security_context import (
    ALL_REGISTERED_THEMES,
    HIGH,
    LOW,
    MATRIX_VERSION,
    MEDIUM,
    THEME_PRIORITY_BASIS,
    THEME_PRIORITY_MATRIX,
    THEME_REGISTRY,
    MatrixError,
    SecurityContext,
    _canonical_rows,
    _validate_matrix,
    build_security_context,
    candidate_themes,
    render_security_context_basis,
    theme_priority_order,
)

TECH_ROWS = {"ai": HIGH, "cyber": HIGH, "china": MEDIUM, "regulatory": MEDIUM}


# ---------------------------------------------------------------------------
# The registry and the matrix
# ---------------------------------------------------------------------------


def test_the_registry_is_the_parent_docs_own_theme_set():
    """The six ids are the parent design's §18 registry, not an invention here."""
    assert set(THEME_REGISTRY) == {"ai", "tariff", "china", "regulatory", "commodity", "cyber"}
    assert frozenset(THEME_REGISTRY) == ALL_REGISTERED_THEMES


def test_the_shipped_matrix_is_well_formed():
    _validate_matrix()
    assert set(THEME_PRIORITY_MATRIX) == set(_canonical_rows()), (
        "every canonical sector needs its own row: a missing row means 'no prior', "
        "and that must be a choice rather than an accident"
    )
    assert len(THEME_PRIORITY_MATRIX) == 11


def test_the_validator_rejects_an_unknown_theme_column():
    matrix = {s: dict(c) for s, c in THEME_PRIORITY_MATRIX.items()}
    matrix["technology"]["made_up_theme"] = HIGH
    try:
        _validate_matrix(matrix, THEME_PRIORITY_BASIS)
    except MatrixError as exc:
        assert "registered themes" in str(exc)
    else:
        raise AssertionError("an unregistered theme id was accepted")


def test_the_validator_rejects_an_unknown_sector_row():
    matrix = {s: dict(c) for s, c in THEME_PRIORITY_MATRIX.items()}
    matrix["profitable sector"] = dict(matrix["technology"])
    try:
        _validate_matrix(matrix, THEME_PRIORITY_BASIS)
    except MatrixError as exc:
        assert "canonical sectors" in str(exc)
    else:
        raise AssertionError("an unknown sector row was accepted")


def test_the_validator_rejects_a_numeric_relevance():
    """Relevance is categorical so that no cell can ever be quoted as a score."""
    matrix = {s: dict(c) for s, c in THEME_PRIORITY_MATRIX.items()}
    matrix["technology"]["ai"] = 0.8
    try:
        _validate_matrix(matrix, THEME_PRIORITY_BASIS)
    except MatrixError as exc:
        assert "categorical" in str(exc)
    else:
        raise AssertionError("a numeric relevance was accepted")


def test_the_validator_rejects_a_cell_with_no_declared_basis():
    basis = {k: v for k, v in THEME_PRIORITY_BASIS.items() if k != "technology.ai"}
    try:
        _validate_matrix(THEME_PRIORITY_MATRIX, basis)
    except MatrixError as exc:
        assert "no declared policy basis" in str(exc)
    else:
        raise AssertionError("a cell with no stated rationale was accepted")


def test_the_validator_rejects_a_basis_for_a_cell_that_does_not_exist():
    basis = dict(THEME_PRIORITY_BASIS)
    basis["technology.nonexistent"] = "why not"
    try:
        _validate_matrix(THEME_PRIORITY_MATRIX, basis)
    except MatrixError as exc:
        assert "does not have" in str(exc)
    else:
        raise AssertionError("a basis for a non-existent cell was accepted")


# ---------------------------------------------------------------------------
# The widening invariant
# ---------------------------------------------------------------------------


def test_the_invariant_holds_for_every_canonical_sector():
    """No sector prior may ever remove a registered theme.

    This is the property the whole layer rests on: a prior that can exclude is
    not a prior, it is a decision. It holds for the eleven canonical sectors, for
    an unclassified company, and for a sector label the matrix has never seen.
    """
    for sector in sorted(_canonical_rows()):
        ctx = SecurityContext(symbol="X", sector_canonical=sector)
        assert candidate_themes(ctx) >= ALL_REGISTERED_THEMES, sector
    for rogue in (None, "", "not a sector", "TECHNOLOGY", "technology "):
        ctx = SecurityContext(symbol="X", sector_canonical=rogue)
        assert candidate_themes(ctx) >= ALL_REGISTERED_THEMES, repr(rogue)
        assert len(candidate_themes(ctx)) == len(ALL_REGISTERED_THEMES), repr(rogue)


def test_an_unclassified_company_is_checked_more_not_less():
    """Absence is not exclusion: no classification yields the full set."""
    empty = build_security_context("ZZZZ", identity={})
    assert empty.sector_canonical is None
    assert candidate_themes(empty) == ALL_REGISTERED_THEMES
    d = empty.to_dict()
    assert d["symbol"] == "ZZZZ"
    # Nothing classified is claimed - no raw value, no source, no SPDR key.
    assert not [k for k in d if k in ("sector_raw", "sector_source", "spdr_etf", "sec_sic")]


# ---------------------------------------------------------------------------
# The context: provenance, the one normalizer, and honest naming
# ---------------------------------------------------------------------------


def test_provenance_is_set_whenever_a_raw_value_is():
    ctx = build_security_context(
        "AAPL", identity={"sector": "Information Technology", "industry": "Software"}
    )
    assert ctx.sector_raw == "Information Technology"
    assert ctx.sector_source == "yfinance"
    assert ctx.industry_raw == "Software"
    assert ctx.industry_source == "yfinance"
    # ...and a context with no raw value claims no source.
    bare = build_security_context("AAPL", identity={})
    assert bare.sector_source is None and bare.industry_source is None


def test_the_canonical_sector_comes_from_the_repos_own_normalizer():
    """Call the existing 73-entry map, never a second one.

    ``Consumer Electronics`` is not a sector name any GICS list carries; only the
    repo's existing map knows it belongs to Consumer Discretionary. A
    reimplementation would answer "consumer electronics".
    """
    ctx = build_security_context(
        "AAPL", identity={"sector": "Consumer Electronics", "industry": "Consumer Electronics"}
    )
    assert ctx.sector_canonical == "consumer disc."
    assert ctx.spdr_etf == "XLY"
    assert ctx.industry_implied_sector == "consumer disc."


def test_the_industry_bridge_is_named_for_what_it_is():
    """An industry mapped to a *sector* is not a normalized industry."""
    fields = set(SecurityContext.__dataclass_fields__)
    assert "industry_implied_sector" in fields
    assert "industry_canonical" not in fields


def test_no_field_claims_a_taxonomy_the_repo_does_not_have():
    ctx = build_security_context("AAPL", identity={"sector": "Technology"})
    assert not [k for k in ctx.to_dict() if "gics" in k.lower()], (
        "the repo has no GICS source, code or licence - no field may be named GICS"
    )
    assert ctx.to_dict().get("sec_sic") is None, (
        "SIC is captured opportunistically and is absent when no payload was fetched"
    )
    assert not [k for k in ctx.to_dict() if "naics" in k.lower()]


def test_there_is_no_cross_source_agreement_field():
    """One reachable sector source means a sibling agreement enum is unreachable.

    ``resolve_instrument_identity`` makes a single vendor read, so an ``agree`` /
    ``disagree`` enum could only ever hold the two states that mean "nothing to
    reconcile". A state that cannot occur reads as a check that ran and passed,
    which is worse than a named absence.
    """
    fields = set(SecurityContext(symbol="X").to_dict()) | {
        f.name for f in SecurityContext.__dataclass_fields__.values()
    }
    assert "agreement" not in fields
    assert "disagreement" not in fields


def test_the_context_is_deterministic():
    identity = {"sector": "Technology", "industry": "Software", "company_name": "Apple Inc."}
    a = build_security_context("AAPL", identity=identity, as_of="2026-09-22")
    b = build_security_context("AAPL", identity=dict(identity), as_of="2026-09-22")
    assert a == b and a.to_dict() == b.to_dict()
    assert a.classification_as_of == "2026-09-22"


def test_an_explicit_identity_performs_no_lookup(monkeypatch):
    """The layer is handed its identity; it must not reach for one of its own."""
    import tradingagents.agents.utils.agent_utils as agent_utils

    def _boom(*_a, **_k):
        raise AssertionError("build_security_context fetched identity it was given")

    monkeypatch.setattr(agent_utils, "resolve_instrument_identity", _boom)
    ctx = build_security_context("AAPL", identity={"sector": "Technology"})
    assert ctx.sector_canonical == "technology"


def test_an_identity_failure_degrades_to_unclassified(monkeypatch):
    """Identity is best-effort by contract: never block the run."""
    import tradingagents.agents.utils.agent_utils as agent_utils

    def _boom(*_a, **_k):
        raise RuntimeError("vendor down")

    monkeypatch.setattr(agent_utils, "resolve_instrument_identity", _boom)
    ctx = build_security_context("AAPL")
    assert ctx.sector_canonical is None
    assert ctx.sector_source is None


# ---------------------------------------------------------------------------
# Ordering and rendering
# ---------------------------------------------------------------------------


def test_the_priority_order_puts_high_first_and_is_stable():
    ctx = SecurityContext(symbol="MSFT", sector_canonical="technology")
    order = theme_priority_order(ctx)
    assert order[:2] == ("ai", "cyber"), "the two HIGH cells come first, id-tied"
    assert set(order[:4]) == set(TECH_ROWS)
    assert set(order[4:]) == {t for t in ALL_REGISTERED_THEMES if t not in TECH_ROWS}
    assert order == theme_priority_order(ctx), "the order must be deterministic"


def test_an_unknown_sector_falls_through_to_no_prior():
    ctx = SecurityContext(symbol="X", sector_canonical="not a sector")
    assert theme_priority_order(ctx) == tuple(sorted(ALL_REGISTERED_THEMES))


def test_the_basis_line_is_one_line_and_names_source_version_and_disclaimer():
    ctx = build_security_context(
        "AAPL", identity={"sector": "Technology", "industry": "Software"}
    )
    line = render_security_context_basis(ctx)
    assert "\n" not in line, "the LLM-facing form must stay one line"
    assert "source: yfinance" in line, "a sector without its source is unusable"
    assert MATRIX_VERSION in line, "a prior without a version is not auditable"
    assert "does not gate" in line, "the disclaimer must always be present"
    assert "declared prior" in line
    assert "ai=HIGH" in line


def test_the_line_still_names_the_disclaimer_when_nothing_is_classified():
    line = render_security_context_basis(build_security_context("ZZZZ", identity={}))
    assert "sector=unclassified" in line
    assert "does not gate" in line
    assert MATRIX_VERSION in line


# ---------------------------------------------------------------------------
# The gate and the card block
# ---------------------------------------------------------------------------


def test_the_gate_is_read_both_ways():
    """Off writes nothing; on writes a block that is classification, not a score."""
    assert _run_card_security_context("AAPL", {"enable_security_context": False}) is None
    assert _run_card_security_context("AAPL", {}) is None
    assert _run_card_security_context("AAPL", None) is None

    block = _run_card_security_context(
        "AAPL", {"enable_security_context": True}, "/reports/AAPL_20260922_101010"
    )
    assert block is not None
    assert block["status"] == "ok"
    assert block["matrix_version"] == MATRIX_VERSION
    assert block["candidate_themes"] == sorted(ALL_REGISTERED_THEMES)
    assert block["context"]["sector_source"] == "yfinance"
    # The as-of date comes from the run directory, never the clock.
    assert block["context"]["classification_as_of"] == "2026-09-22"
    # A classification block carries no score, rating or direction to mistake.
    assert not [k for k in block if k in ("score", "rating", "direction", "signal")]


def test_the_shipped_gate_defaults_off():
    assert dc.DEFAULT_CONFIG["enable_security_context"] is False
    key_to_env = {v: k for k, v in dc._ENV_OVERRIDES.items()}
    assert key_to_env["enable_security_context"] == "TRADINGAGENTS_ENABLE_SECURITY_CONTEXT"


def test_the_low_cells_are_the_ones_with_no_ordering_prior():
    """LOW is the only priority that can be promoted by a cheap trigger scan."""
    lows = {f"{s}.{t}" for s, cells in THEME_PRIORITY_MATRIX.items()
            for t, p in cells.items() if p == LOW}
    assert lows, "the matrix must have LOW cells, or nothing escalates"
    assert all(THEME_PRIORITY_BASIS[k] for k in lows)
