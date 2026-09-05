"""Business-cycle -> sector-tilt map (sector-rotation Action 2, advisory).

Institutional sector rotation leads with a macro regime read: which phase
the economy is in (early / mid / late / recession) maps to historically
favored sectors. This module classifies the phase from the published signal
set — PMI growth momentum, the Treasury yield curve, and credit spreads —
and returns an advisory sector tilt. Everything is None-safe: a missing
input makes the phase unknown (``None``), never fabricated; the tilt is
context for the analyst, not a gate.

Sources: synthetized from web research on institutional sector rotation
(business-cycle phase maps; PMI above/below 50; steepening curve = early;
flattening/inversion + widening spreads = late/recession). The fork's
advisory/no-execution mandate stands.
"""

from __future__ import annotations

# Phase -> preferred SPDR sectors (verbose names matching SPDR_SECTORS).
TILT_MAP: dict[str, tuple[str, ...]] = {
    "early": ("Financials", "Consumer Disc.", "Industrials", "Materials"),
    "mid": ("Technology", "Industrials", "Materials"),
    "late": ("Energy", "Materials", "Consumer Staples", "Health Care", "Utilities"),
    "recession": ("Consumer Staples", "Health Care", "Utilities"),
}


def _classify(pmi: float | None, spread10_2: float | None, hy_spread: float | None) -> str | None:
    """Cycle phase from the three macro signals (published rules).

    - PMI >= 50 -> expansion; < 50 -> contraction.
    - ``spread10_2`` = 10y-2y Treasury spread in pct points (e.g. 0.40 =
      40bp positive): positive/steepening favors early; flattening/inverted
      (<= 0) favors late/recession.
    - ``hy_spread`` = high-yield option-adjusted spread in pct points:
      widening (> 5.0) raises stress -> late/recession.

    Missing inputs degrade: PMI is the primary classifier; yield curve leans
    (early vs late); credit spread confirms stress. Returns None only when
    nothing usable is supplied.
    """
    if pmi is not None:
        expansion = pmi >= 50.0
        stress = hy_spread is not None and hy_spread > 5.0
        inverted = spread10_2 is not None and spread10_2 <= 0.0
        if not expansion:
            return "recession"  # PMI < 50 = contraction -> defensives
        if stress:
            return "late"       # expansion + widening credit = late cycle
        if inverted:
            return "late"       # expansion + flat/inverted curve = late
        return "mid"            # expansion, no stress, curve positive
    # No PMI: yield curve + credit fall back.
    if spread10_2 is not None:
        if spread10_2 <= 0.0:
            return "recession" if (hy_spread is not None and hy_spread > 5.0) else "late"
        return "early"
    if hy_spread is not None:
        return "recession" if hy_spread > 5.0 else "late"
    return None


def cycle_phase(pmi: float | None, spread10_2: float | None, hy_spread: float | None) -> str | None:
    """Public cycle-phase classifier (missing inputs -> None, never fabricated)."""
    return _classify(pmi, spread10_2, hy_spread)


def cycle_tilt(pmi: float | None, spread10_2: float | None, hy_spread: float | None) -> dict:
    """Advisory sector tilt for the current cycle phase.

    Returns ``{"phase": .., "tilt": [..], "inputs": {pmi, spread10_2,
    hy_spread}}``; phase None -> tilt [] (never a fabricated map).
    """
    phase = cycle_phase(pmi, spread10_2, hy_spread)
    return {
        "phase": phase,
        "tilt": list(TILT_MAP[phase]) if phase else [],
        "inputs": {"pmi": pmi, "spread10_2": spread10_2, "hy_spread": hy_spread},
    }


__all__ = ["cycle_phase", "cycle_tilt", "TILT_MAP"]
