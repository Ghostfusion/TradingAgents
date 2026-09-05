"""DuPont ROE decomposition (quant-engine v2 A1, advisory).

Explains WHERE ROE comes from (margin vs turnover vs leverage) — the
institutional check that distinguishes margin/turnover-led quality from
leverage-led ROE. Pure / None-safe: any missing input makes that leg None;
the driver verdict is advisory, never a gate.

Driver attribution (log-DuPont): each leg's |ln(factor)| deviation from the
neutral 1.0 benchmark, shared over the total — the leg whose *level* deviates
most from "no effect" is the driver (margin-led / turnover-led /
leverage-led / tax- or interest-driven / mixed). When any leg is non-positive
(ln undefined) the losing leg is the story (e.g. a loss-making margin
dominates any turnover/leverage contribution).
"""

from __future__ import annotations

import math

_LABELS = {
    "net_margin": "margin-led",
    "asset_turnover": "turnover-led",
    "equity_multiplier": "leverage-led",
    "tax_burden": "tax-burden-driven",
    "interest_burden": "interest-burden-driven",
}


def _ratio(x: float | None) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _driver(factors: dict[str, float]) -> tuple[str | None, str | None]:
    """(driver leg, label) via log-DuPont attribution vs the 1.0 benchmark."""
    if any(v <= 0 for v in factors.values()):
        if factors["net_margin"] <= 0:
            return "net_margin", "margin-led (non-positive margin)"
        for nm, v in factors.items():
            if v <= 0:
                return nm, f"non-positive {nm} leg"
        return None, "neutral (no leg deviates from 1.0)"
    total = sum(abs(math.log(v)) for v in factors.values())
    if total < 1e-9:
        return None, "neutral (no leg deviates from 1.0)"
    shares = {nm: abs(math.log(v)) / total for nm, v in factors.items()}
    mx = max(shares, key=shares.get)  # type: ignore[arg-type]
    if shares[mx] < 0.40:  # type: ignore[index]
        return "mixed", "no single leg dominates (mixed)"
    return mx, _LABELS[mx]


def _verdict(factors: dict[str, float], roe: float) -> dict:
    driver, label = _driver(factors)
    return {
        "roe": round(roe, 4),
        "factors": factors,
        "driver": driver,
        "note": label,
    }


def dupont_5(
    net_margin: float | None,
    tax_burden: float | None,
    interest_burden: float | None,
    asset_turnover: float | None,
    equity_multiplier: float | None,
) -> dict:
    """5-factor DuPont: ROE = NM * TB * IB * AT * EM.

    ``net_margin`` here is the operating margin (EBIT/revenue); ``tax_burden``
    = NI/pretax, ``interest_burden`` = pretax/EBIT. Returns
    ``{'roe', 'factors', 'driver', 'note'}``; driver/note are the log-DuPont
    attribution (advisory). None-safe.
    """
    nms = ["net_margin", "tax_burden", "interest_burden", "asset_turnover", "equity_multiplier"]
    vals = [net_margin, tax_burden, interest_burden, asset_turnover, equity_multiplier]
    factors = {nm: _ratio(v) for nm, v in zip(nms, vals, strict=True)}
    if any(v is None for v in factors.values()):
        return {"roe": None, "factors": factors, "driver": None,
                "note": "incomplete inputs - ROE unavailable (n/a)"}
    factors = {nm: v for nm, v in factors.items() if v is not None}
    roe = 1.0
    for v in factors.values():
        roe *= v
    return _verdict(factors, roe)


def dupont_3(
    net_margin: float | None,
    asset_turnover: float | None,
    equity_multiplier: float | None,
) -> dict:
    """3-factor DuPont: ROE = NM * AT * EM (the classic institutional view).

    Computes ROE directly from the three legs (not via dupont_5 which needs
    tax/interest burdens — those are the 5-factor extension). Returns
    ``{'roe', 'factors', 'driver', 'note'}``; driver/note are the log-DuPont
    attribution (advisory). None-safe.
    """
    factors = {
        "net_margin": _ratio(net_margin),
        "asset_turnover": _ratio(asset_turnover),
        "equity_multiplier": _ratio(equity_multiplier),
    }
    if any(v is None for v in factors.values()):
        return {"roe": None, "factors": factors, "driver": None,
                "note": "incomplete inputs - ROE unavailable (n/a)"}
    factors = {nm: v for nm, v in factors.items() if v is not None}
    roe = factors["net_margin"] * factors["asset_turnover"] * factors["equity_multiplier"]
    return _verdict(factors, roe)


__all__ = ["dupont_5", "dupont_3"]
