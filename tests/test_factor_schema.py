"""The factor-schema record: availability declarations, the categories, the gate.

Covers the two schema items of the round: **D-5** (three factors declared ``NA``
although their producers are reachable - which of them the peer panel can
genuinely supply) and **FUND-22 / D-16** (the ``Insider Activity`` category was
declared and fed by nothing).

Offline and deterministic: the schema is a record, so these tests read it and
call no producer and no vendor.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.factor_schema import (
    CATEGORIES,
    FACTOR_SCHEMA,
    FILING_DATE,
    NA,
    PRESENT,
    SUBSCORE_FACTORS,
    availability_report,
    observability_for,
    validate_schema,
)

pytestmark = pytest.mark.timeout(180)


# --------------------------------------------------------------------------
# the record's own invariants (unchanged by either fix)
# --------------------------------------------------------------------------


def test_the_schema_self_check_still_passes() -> None:
    validate_schema()


def test_every_record_keeps_its_nine_fields_and_one_direction() -> None:
    for spec in FACTOR_SCHEMA.values():
        assert spec.factor and spec.category and spec.formula
        assert spec.direction in (1, -1)
        assert spec.base_weight is None  # no fabricated coefficients
        assert spec.sector_scope and spec.normalization_method and spec.supplier
        assert spec.availability in (PRESENT, NA)


# --------------------------------------------------------------------------
# D-5 - which of the three NA factors the panel can genuinely supply
# --------------------------------------------------------------------------


def test_fcf_yield_is_declared_present_because_the_panel_supplies_it() -> None:
    """The one of the three whose legs the panel already holds."""
    assert FACTOR_SCHEMA["fcf_yield"].availability == PRESENT
    assert "fcf_yield" in availability_report(SUBSCORE_FACTORS["VS"])["present"]
    assert "fcf_yield" not in availability_report(SUBSCORE_FACTORS["VS"])["NA"]


def test_rev_cagr5_and_val_z_stay_na_with_the_honest_reason() -> None:
    """Neither is carried by the peer panel, and the record now says why.

    ``rev_cagr5`` needs six annual periods and the panel's statement fetch holds
    ~4-5; ``val_z`` needs the name's own per-period multiple series, which a
    one-statement panel never carries. Both keep the producer named, and the
    ``NA`` reason is on the record rather than implied.
    """
    for factor in ("rev_cagr5", "val_z"):
        spec = FACTOR_SCHEMA[factor]
        assert spec.availability == NA
        assert "NOT carried by the peer panel" in spec.formula
        assert spec.supplier.strip()
    assert "rev_cagr5" in availability_report(SUBSCORE_FACTORS["FGS"])["NA"]
    assert "val_z" in availability_report(SUBSCORE_FACTORS["VS"])["NA"]


def test_no_factor_moved_between_sub_scores() -> None:
    """The fixes changed availability, never a sub-score's membership."""
    assert SUBSCORE_FACTORS["FGS"] == ("revenue_yoy", "eps_yoy", "rev_cagr5")
    assert "fcf_yield" in SUBSCORE_FACTORS["VS"]
    assert "dcf_upside" in SUBSCORE_FACTORS["VS"]


# --------------------------------------------------------------------------
# FUND-22 / D-16 - the Insider Activity category
# --------------------------------------------------------------------------


def test_the_insider_category_is_declared_and_no_longer_empty() -> None:
    """Declared-not-fed is recorded as six NA factors, not left invisible."""
    assert "Insider Activity" in CATEGORIES
    insider = {
        f: s for f, s in FACTOR_SCHEMA.items() if s.category == "Insider Activity"
    }
    assert len(insider) == 6
    assert all(s.availability == NA for s in insider.values())
    assert all("NOT carried by the peer panel" in s.formula for s in insider.values())
    # the producers are named on the record even though they are off-panel
    assert any("finnhub" in s.supplier for s in insider.values())
    assert any("massive" in s.supplier for s in insider.values())


def test_no_insider_factor_enters_a_sub_score() -> None:
    """No sub-score owns insider activity, so none may silently adopt it."""
    insider = {
        f for f, s in FACTOR_SCHEMA.items() if s.category == "Insider Activity"
    }
    in_subscores = {f for factors in SUBSCORE_FACTORS.values() for f in factors}
    assert not (insider & in_subscores)
    # and the coverage denominators of the four sub-scores are unchanged
    assert len(SUBSCORE_FACTORS["FQS"]) == 7
    assert len(SUBSCORE_FACTORS["FGS"]) == 3
    assert len(SUBSCORE_FACTORS["VS"]) == 12
    assert len(SUBSCORE_FACTORS["FRS"]) == 6


def test_an_insider_factor_is_observable_at_its_form_4_filing_date() -> None:
    """A Form-4 fact is known at its filing date - declared, never assumed safe."""
    for factor, spec in FACTOR_SCHEMA.items():
        if spec.category == "Insider Activity":
            assert observability_for(factor) == FILING_DATE
            assert spec.observability == FILING_DATE


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
