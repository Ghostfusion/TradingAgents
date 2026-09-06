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




# ---------------------------------------------------------------------------
# Taylor-rule implied policy rate (P5, advisory macro stance)
# ---------------------------------------------------------------------------


def taylor_rule(
    policy_rate, inflation, output_gap=None,
    r_star=0.005, inflation_target=0.02,
    inflation_weight=0.5, output_weight=0.5,
):
    """Classic Taylor (1993) rule implied nominal policy rate.

    i = r* + pi + w_pi*(pi - pi*) + w_y*(y - y*) with r* neutral real rate
    (0.5%), pi inflation, pi* target (2%), y-y* output gap (default 0).
    Returns the implied nominal policy rate (fraction) or None on missing
    policy_rate/inflation.
    """
    try:
        float(policy_rate)
        infl = float(inflation)
        og = float(output_gap) if output_gap is not None else 0.0
        rs = float(r_star)
        pt = float(inflation_target)
        iw = float(inflation_weight)
        ow = float(output_weight)
    except (TypeError, ValueError):
        return None
    return rs + infl + iw * (infl - pt) + ow * og


def taylor_deviation(policy_rate, implied_rate):
    """Actual policy rate minus the Taylor-rule implied rate. Positive =
    policy tighter than the rule (restrictive); negative = looser. None when
    either input missing."""
    if policy_rate is None or implied_rate is None:
        return None
    try:
        return float(policy_rate) - float(implied_rate)
    except (TypeError, ValueError):
        return None


def macro_stance(pmi, spread10_2, hy_spread, policy_rate, inflation,
                 output_gap=None):
    """Combined advisory macro read: cycle phase + Taylor stance + deviation.

    Returns {'phase', 'taylor_implied', 'deviation', 'stance', 'tilt'};
    stance = tight/easy/neutral (None when unmeasurable). Missing inputs
    degrade to None. Advisory, never a gate."""
    phase = cycle_phase(pmi, spread10_2, hy_spread)
    implied = taylor_rule(policy_rate, inflation, output_gap)
    dev = taylor_deviation(policy_rate, implied)
    stance = None
    if dev is not None:
        stance = "tight" if dev > 0.005 else "easy" if dev < -0.005 else "neutral"
    return {
        "phase": phase,
        "taylor_implied": round(implied, 4) if implied is not None else None,
        "deviation": round(dev, 4) if dev is not None else None,
        "stance": stance,
        "tilt": list(TILT_MAP[phase]) if phase else [],
    }

__all__ = ["cycle_phase", "cycle_tilt", "TILT_MAP", "taylor_rule", "taylor_deviation", "macro_stance"]
