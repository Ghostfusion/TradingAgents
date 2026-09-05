"""DuPont ROE decomposition (quant-engine v2 A1, advisory).

Explains WHERE ROE comes from (margin vs turnover vs leverage) — the
institutional check that distinguishes margin/turnover-led quality from
leverage-led ROE. Pure / None-safe: any missing input makes that leg None;
the driver verdict is advisory (largest relative deviation), never a gate.
"""

from __future__ import annotations


def _ratio(x: float | None) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _deviation(factor: float, roe: float) -> float | None:
    """Fraction of ROE this leg (abs) drives — for ranking which leg dominates."""
    if abs(roe) < 1e-9:
        return None
    return abs(factor) / abs(roe)


def dupont_5(
    net_margin: float | None,
    tax_burden: float | None,
    interest_burden: float | None,
    asset_turnover: float | None,
    equity_multiplier: float | None,
) -> dict:
    """5-factor DuPont: ROE = NM * TB * IB * AT * EM.

    Returns ``{'roe', 'factors', 'driver', 'note'}``; driver = the leg with
    the largest |deviation| from the observed ROE (advisory). None-safe.
    """
    nms = ["net_margin", "tax_burden", "interest_burden", "asset_turnover", "equity_multiplier"]
    vals = [net_margin, tax_burden, interest_burden, asset_turnover, equity_multiplier]
    factors = {nm: _ratio(v) for nm, v in zip(nms, vals, strict=True)}
    if any(v is None for v in factors.values()):
        return {"roe": None, "factors": factors, "driver": None,
                "note": "incomplete inputs - ROE unavailable (n/a)"}
    roe = 1.0
    for v in factors.values():
        roe *= float(v)  # type: ignore[arg-type]
    devs = {nm: d for nm, v in factors.items()
            if (d := _deviation(float(v), roe)) is not None}
    driver = max(devs, key=devs.get) if devs else None
    return {
        "roe": round(roe, 4),
        "factors": factors,
        "driver": driver,
        "note": f"ROE driven most by {driver}" if driver else "ROE: n/a",
    }


def dupont_3(
    net_margin: float | None,
    asset_turnover: float | None,
    equity_multiplier: float | None,
) -> dict:
    """3-factor DuPont: ROE = NM * AT * EM (the classic institutional view).

    Computes ROE directly from the three legs (not via dupont_5 which needs
    tax/interest burdens — those are the 5-factor extension).
    """
    factors = {
        "net_margin": _ratio(net_margin),
        "asset_turnover": _ratio(asset_turnover),
        "equity_multiplier": _ratio(equity_multiplier),
    }
    if any(v is None for v in factors.values()):
        return {"roe": None, "factors": factors, "driver": None,
                "note": "incomplete inputs - ROE unavailable (n/a)"}
    roe = float(factors["net_margin"]) * float(factors["asset_turnover"]) * float(factors["equity_multiplier"])  # type: ignore[arg-type]
    devs = {nm: d for nm, v in factors.items()
            if (d := _deviation(float(v), roe)) is not None}
    driver = max(devs, key=devs.get) if devs else None
    return {
        "roe": round(roe, 4),
        "factors": factors,
        "driver": driver,
        "note": f"ROE driven most by {driver}" if driver else "ROE: n/a",
    }


__all__ = ["dupont_5", "dupont_3"]
