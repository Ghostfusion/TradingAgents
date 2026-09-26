"""Business-cycle -> sector tilt tests (sector-rotation Action 2, cycle_tilt.py).

The manufacturing leg is industrial-production GROWTH, not a PMI diffusion level
(owner decision 2026-09-25): the `pmi` FRED alias pointed at the discontinued
NAPM series, so the leg could only read None. The expansion boundary moved with
it - PMI >= 50 becomes IP growth >= 0.
"""

import pytest

from tradingagents.strategies.cycle_tilt import (
    MANUFACTURING_EXPANSION_PCT,
    TILT_MAP,
    cycle_phase,
    cycle_tilt,
    industrial_production_growth,
)

pytestmark = pytest.mark.timeout(60)


def test_phase_from_growth_expansion_mid():
    # IP growth >= 0, curve positive, no credit stress -> mid (expansion).
    assert cycle_phase(1.2, 0.40, 3.5) == "mid"


def test_phase_early_with_steep_curve_no_growth():
    # No manufacturing read, positive curve -> early.
    assert cycle_phase(None, 0.40, None) == "early"


def test_phase_recession_when_manufacturing_contracts():
    assert cycle_phase(-0.8, -0.20, 6.5) == "recession"
    assert cycle_phase(-0.8, 0.40, 3.0) == "recession"  # growth is primary


def test_the_expansion_boundary_is_zero_growth_not_fifty():
    """The PMI's 50 has no meaning on an index-level series.

    INDPRO is a level, so the boundary is the SIGN of its growth; a level of 103
    passed against 50 would have called every month an expansion.
    """
    assert MANUFACTURING_EXPANSION_PCT == 0.0
    assert cycle_phase(0.0, 0.40, 3.0) == "mid"       # flat = expansion, as PMI 50 was
    assert cycle_phase(103.07, 0.40, 3.0) == "mid"    # a LEVEL is still >= 0 - which
    #                                                    is exactly why the caller must
    #                                                    pass growth, not the level
    assert cycle_phase(-0.01, 0.40, 3.0) == "recession"


def test_phase_late_credit_stress():
    # Expansion + widening HY spread -> late.
    assert cycle_phase(1.2, 0.10, 6.5) == "late"
    # Expansion + inverted curve -> late.
    assert cycle_phase(1.2, -0.10, 3.0) == "late"


def test_phase_no_inputs_unknown():
    assert cycle_phase(None, None, None) is None


def test_phase_late_inverted_without_growth():
    assert cycle_phase(None, -0.10, None) == "late"
    assert cycle_phase(None, -0.10, 6.0) == "recession"  # inverted + stress


def test_cycle_tilt_returns_phase_and_sectors():
    til = cycle_tilt(1.2, 0.40, 3.5)
    assert til["phase"] == "mid"
    assert "Technology" in til["tilt"]
    assert til["inputs"]["manufacturing_growth_pct"] == 1.2


def test_cycle_tilt_unknown_returns_empty_tilt():
    til = cycle_tilt(None, None, None)
    assert til["phase"] is None
    assert til["tilt"] == []  # never a fabricated map


def test_tilt_map_complete_for_all_phases():
    for phase in ("early", "mid", "late", "recession"):
        assert TILT_MAP[phase]
        assert len(TILT_MAP[phase]) >= 3


# --- the industrial-production growth read ----------------------------------


def _monthly(n: int, *, start: float = 100.0, step: float = 0.0,
             first: tuple = (2025, 8)) -> list:
    """FRED's own shape: (date, value) oldest -> newest, CONTIGUOUS months.

    Contiguous matters: the growth compares the last observation against the one
    ``months`` observations back, and the dates are what let a reader see whether
    that really is a year apart (they would read it as a shorter span if the
    series had a gap).
    """
    year, month = first
    out = []
    for i in range(n):
        out.append((f"{year}-{month:02d}-01", start + step * i))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def test_growth_is_year_over_year_and_carries_its_dates():
    """A monthly series is published with a lag, so the reading names the months
    it compared rather than letting a reader assume today's."""
    obs = _monthly(12, start=100.0)  # 2025-08 .. 2026-07
    obs.append(("2026-08-01", 103.0))
    g = industrial_production_growth(obs)
    assert g["growth_pct"] == pytest.approx(3.0)
    assert g["latest"] == 103.0 and g["latest_date"] == "2026-08-01"
    assert g["base"] == 100.0 and g["base_date"] == "2025-08-01"
    assert g["observations"] == 13 and g["months"] == 12


def test_a_contracting_series_reads_negative_growth():
    obs = _monthly(13, start=100.0, step=-0.25)
    g = industrial_production_growth(obs)
    assert g["growth_pct"] < 0
    # and that feeds the classifier as recession
    assert cycle_phase(g["growth_pct"], 0.40, 3.0) == "recession"


def test_a_series_too_short_for_a_year_is_unmeasured_never_zero():
    g = industrial_production_growth(_monthly(6, start=100.0, step=1.0))
    assert g["growth_pct"] is None and g["latest_date"] is None
    assert g["observations"] == 6
    assert industrial_production_growth([])["growth_pct"] is None
    # a non-positive base cannot produce a growth rate
    bad = _monthly(13, start=0.0, step=0.0)
    assert industrial_production_growth(bad)["growth_pct"] is None
