"""Credit-stress read from ICE BofA US high-yield option-adjusted spreads.

Deterministic, offline introspection of three FRED OAS series (the classic
forward-looking risk-off sentinel the regime/risk overlays care about):

  hy_oas    = ICE BofA US High Yield OAS              (BAMLH0A0HYM2)
  ccc_oas   = ICE BofA CCC & Lower US High Yield OAS (BAMLH0A3HYC)
  bb_oas    = ICE BofA BB US High Yield OAS        (BAMLH0A1HYBB)

The threshold bands mirror the standard credit-cycle read used by the macro
layer (see docs/api_reference.md + docs/massive_integration.md): widening HY
and CCC option-adjusted spreads past the warning levels signal credit stress
that historically precedes equities de-rating.

No network here - this module only classifies values the agent already holds.
"""

from __future__ import annotations

# OAS % thresholds (mind: FRED reports these series in %, not bps).
# Bands follow the credit-cycle table used by the macro layer: below the low
# bound = low; from low up to mid = moderate; mid..high = high; above = severe.
CCC_LOW = 8.0      # CCC OAS < 8%   -> low
CCC_MID = 11.0     # CCC OAS 10-12% -> moderate (mid ~11)
CCC_HIGH = 15.0    # CCC OAS > 15%  -> severe
HY_LOW = 3.0       # HY OAS < 3%    -> low
HY_MID = 4.5       # HY OAS 3.5-4.5% -> moderate
HY_HIGH = 5.5      # HY OAS > 5.5%  -> severe


def _band_of(value: float | None, low: float, mid: float, high: float) -> str | None:
    """Classify one OAS into low / moderate / high / severe."""
    if value is None:
        return None
    if value < low:
        return "low"
    if value < mid:
        return "moderate"
    if value <= high:
        return "high"
    return "severe"


def credit_stress_level(
    hy_oas: float | None,
    ccc_oas: float | None,
    bb_oas: float | None = None,
) -> dict:
    """Verdict dict for the credit regime from the HY/CCC/BB OAS values.

    Returns ``{"level", "scale", "reasons"}`` where ``level`` is the worst
    band observed across the available series (low -> moderate -> high ->
    severe) and ``scale`` (1.0 = no de-risk, 0.5 = full risk-off) is a
    deterministic multiplier an overlay consumer can apply. Missing series are
    skipped (never fabricated); if nothing is available the level is "unknown".
    """
    hy = _band_of(hy_oas, HY_LOW, HY_MID, HY_HIGH)
    ccc = _band_of(ccc_oas, CCC_LOW, CCC_MID, CCC_HIGH)
    bb = _band_of(bb_oas, HY_LOW, HY_MID, HY_HIGH)

    rank = {"low": 0, "moderate": 1, "high": 2, "severe": 3}
    active = [b for b in (hy, ccc, bb) if b is not None]
    if not active:
        return {"level": "unknown", "scale": 1.0, "reasons": []}

    level = max(active, key=lambda b: rank[b])
    scale = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.5}[rank[level]]

    reasons = []
    if hy is not None:
        reasons.append(f"hy_oas={hy_oas:.2f}% ({hy})")
    if ccc is not None:
        reasons.append(f"ccc_oas={ccc_oas:.2f}% ({ccc})")
    if bb is not None:
        reasons.append(f"bb_oas={bb_oas:.2f}% ({bb})")

    return {
        "level": level,
        "scale": scale,
        "reasons": reasons,
    }


def hazard_from_spread(spread: float | None, recovery_rate: float = 0.40) -> float | None:
    """Implied constant hazard rate ``lambda`` from a credit spread.

    ``s ~= lambda * (1 - RR)`` (the classic reduced-form relation), so
    ``lambda = s / (1 - RR)``. ``spread`` is the OAS in **decimal** (e.g.
    0.04 for 4%); ``recovery_rate`` default 0.40 (the standard assumption,
    documented in the tool output). None for non-positive / None spread.
    """
    if spread is None:
        return None
    try:
        s = float(spread)
        rr = float(recovery_rate)
    except (TypeError, ValueError):
        return None
    if s <= 0 or rr >= 1.0:
        return None
    return s / (1.0 - rr)


def merton_distance_to_default(
    equity: float | None,
    debt: float | None,
    equity_vol: float | None,
    r: float = 0.03,
    t: float = 1.0,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> dict | None:
    """Merton structural distance-to-default (quants.md §Credit).

    Treats equity as a call on firm assets and calibrates the unobservable
    asset value V and asset vol sigma_V by iterating the system (web-verified
    scheme; Merton 1974 / KMV practice):

        E = V N(d1) - D e^{-rT} N(d2),  d1 = [ln(V/D) + (r + 1/2 sV^2) T] /
        (sV sqrt(T)),  d2 = d1 - sV sqrt(T),  E sE = V sV N(d1).

    Starts from V0 = E + D, sV0 = E/(E+D) * sE and fixed-point updates V and
    sV. Returns ``{'distance_to_default', 'asset_value', 'asset_volatility',
    'd1', 'd2', 'risk_neutral_pd', 'converged', 'n_iter'}`` (DtD = d2, the
    standard Merton distance; PD = N(-d2)) or None when any input is missing /
    non-positive / fails to converge. Structural credit read alongside the
    spread-based hazard - not a substitute for it.
    """
    import math

    try:
        E = float(equity)
        D = float(debt)
        sE = float(equity_vol)
        rf = float(r)
        T = float(t)
    except (TypeError, ValueError):
        return None
    if E <= 0 or D <= 0 or sE <= 0 or T <= 0:
        return None

    def _ncdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    V = E + D
    sV = (E / V) * sE
    converged = False
    n_iter = 0
    for _ in range(max_iter):
        if sV <= 0:
            break
        d1 = (math.log(V / D) + (rf + 0.5 * sV * sV) * T) / (sV * math.sqrt(T))
        if math.isnan(d1) or math.isinf(d1):
            break
        d2 = d1 - sV * math.sqrt(T)
        E_model = V * _ncdf(d1) - D * math.exp(-rf * T) * _ncdf(d2)
        if E_model <= 0:
            break
        sE_model = (V / E_model) * sV * _ncdf(d1)
        V_new = V * (E / E_model)
        sV_new = sV * (sE / sE_model) if sE_model > 0 else sV
        if abs(V_new - V) < tol and abs(sV_new - sV) < tol:
            V, sV = V_new, sV_new
            converged = True
            n_iter += 1
            break
        V, sV = V_new, sV_new
        n_iter += 1
    if V <= 0 or sV <= 0:
        return None
    d1 = (math.log(V / D) + (rf + 0.5 * sV * sV) * T) / (sV * math.sqrt(T))
    d2 = d1 - sV * math.sqrt(T)
    return {
        "distance_to_default": round(float(d2), 4),
        "asset_value": round(float(V), 2),
        "asset_volatility": round(float(sV), 6),
        "d1": round(float(d1), 4),
        "d2": round(float(d2), 4),
        "risk_neutral_pd": round(float(_ncdf(-d2)), 6),
        "converged": bool(converged),
        "n_iter": n_iter,
    }


def default_probability(
    spread: float | None,
    years: float = 1.0,
    recovery_rate: float = 0.40,
) -> float | None:
    """Cumulative default probability by ``years`` under a constant hazard.

    ``PD(0, t) = 1 - exp(-lambda * t)`` with ``lambda`` from
    :func:`hazard_from_spread`. Returns the probability (0..1); None for
    non-positive / None spread or horizon. The recovery-rate assumption is
    stated so the number is auditable (no fabrication).
    """
    import math

    lam = hazard_from_spread(spread, recovery_rate)
    if lam is None or years is None:
        return None
    try:
        t = float(years)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    return 1.0 - math.exp(-lam * t)


__all__ = ["credit_stress_level", "CCC_LOW", "CCC_MID", "CCC_HIGH", "HY_LOW", "HY_MID", "HY_HIGH", "hazard_from_spread", "default_probability", "merton_distance_to_default"]
