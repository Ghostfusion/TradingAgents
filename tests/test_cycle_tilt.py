"""Business-cycle -> sector tilt tests (sector-rotation Action 2, cycle_tilt.py)."""

import pytest

from tradingagents.strategies.cycle_tilt import TILT_MAP, cycle_phase, cycle_tilt

pytestmark = pytest.mark.timeout(60)


def test_phase_from_pmi_expansion_mid():
    # PMI >= 50, curve positive, no credit stress -> mid (expansion).
    assert cycle_phase(52.0, 0.40, 3.5) == "mid"


def test_phase_early_with_steep_curve_no_pmi():
    # No PMI, positive curve -> early.
    assert cycle_phase(None, 0.40, None) == "early"


def test_phase_recession_pmi_below_50():
    assert cycle_phase(49.0, -0.20, 6.5) == "recession"
    assert cycle_phase(49.0, 0.40, 3.0) == "recession"  # PMI is primary


def test_phase_late_credit_stress():
    # Expansion + widening HY spread -> late.
    assert cycle_phase(51.0, 0.10, 6.5) == "late"
    # Expansion + inverted curve -> late.
    assert cycle_phase(51.0, -0.10, 3.0) == "late"


def test_phase_no_inputs_unknown():
    assert cycle_phase(None, None, None) is None


def test_phase_late_inverted_no_pmi():
    assert cycle_phase(None, -0.10, None) == "late"
    assert cycle_phase(None, -0.10, 6.0) == "recession"  # inverted + stress


def test_cycle_tilt_returns_phase_and_sectors():
    til = cycle_tilt(52.0, 0.40, 3.5)
    assert til["phase"] == "mid"
    assert "Technology" in til["tilt"]
    assert til["inputs"]["pmi"] == 52.0


def test_cycle_tilt_unknown_returns_empty_tilt():
    til = cycle_tilt(None, None, None)
    assert til["phase"] is None
    assert til["tilt"] == []  # never a fabricated map


def test_tilt_map_complete_for_all_phases():
    for phase in ("early", "mid", "late", "recession"):
        assert TILT_MAP[phase]
        assert len(TILT_MAP[phase]) >= 3
