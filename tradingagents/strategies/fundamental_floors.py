"""Fundamental value-floor calculations (pure, offline) — the "value dip" floor.

Adds the classic earnings-power / asset-value cheapness floors on top of the
existing DCF / margin-of-safety / FCF-yield:

  Graham Number  = sqrt(22.5 x EPS x BVPS)      (Graham's 15x P/E x 1.5x P/B rule)
  NCAV / share   = (CurrentAssets - TotalLiabilities) / shares   (net-net, Graham)
  Earnings Power Value (EPV) = adj EBIT x (1 - tax) / (WACC - g) (+ excess-RoIC check)

Each is an intrinsic "floor" for the value-dip: when price is at or below them
the dip buys with a margin of safety that is *structural* (asset/earnings
backed), not just a momentum artifact.

No-fabrication rule: every function returns None when an input is missing or
the result is degenerate (never estimate). Pure and offline-testable.
"""

from __future__ import annotations


def graham_number(eps: float | None, book_value_per_share: float | None) -> float | None:
    """Graham Number = sqrt(22.5 * EPS * BVPS).

    The 22.5 factor encodes Graham's ceiling of P/E=15 x P/B=1.5. Only valid
    for positive EPS and BVPS; None (no-fabrication) otherwise.
    """
    if eps is None or book_value_per_share is None:
        return None
    try:
        e = float(eps)
        b = float(book_value_per_share)
    except (TypeError, ValueError):
        return None
    if e <= 0 or b <= 0:
        return None
    return round((22.5 * e * b) ** 0.5, 4)


def graham_cheap(price: float | None, g: float | None) -> bool | None:
    """True when price <= Graham Number (cheap by Graham's rule)."""
    if price is None or g is None:
        return None
    return float(price) <= g


def ncav_per_share(
    current_assets: float | None,
    total_liabilities: float | None,
    shares: float | None,
) -> float | None:
    """Graham net-net: NCAV/share = (current assets - total liabilities) / shares.

    The classic deep-value floor. None when any input is missing or shares <= 0.
    """
    if current_assets is None or total_liabilities is None or shares is None:
        return None
    try:
        ca = float(current_assets)
        tl = float(total_liabilities)
        s = float(shares)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    return round((ca - tl) / s, 4)


def ncav_cheap(price: float | None, ncav: float | None) -> bool | None:
    """True when price below NCAV (deep net-net discount)."""
    if price is None or ncav is None:
        return None
    return float(price) < ncav


def earnings_power_value(
    adjusted_ebit: float | None,
    tax_rate: float | None,
    wacc: float | None,
    growth: float = 0.0,
    roic: float | None = None,
) -> dict:
    """Greenwald Earnings Power Value = adj EBIT x (1 - t) / (WACC - g).

    Returns a dict {epv, per_share, conclusion} with an **excess-RoIC check**:
    when ``roic`` is given and > WACC, the company earns above its cost of
    capital and the EPV is an earnings-power floor; when RoIC < WACC the
    "value" is weak (destroys capital) - flagged rather than a clean floor.
    None fields on missing input (WACC-must exceed growth).
    """
    if adjusted_ebit is None or wacc is None:
        return {"epv": None, "per_share": None, "excess_roi": None, "conclusion": "unknown"}
    try:
        eb = float(adjusted_ebit)
        w = float(wacc)
        t = float(tax_rate) if tax_rate is not None else 0.0
        g = float(growth)
    except (TypeError, ValueError):
        return {"epv": None, "per_share": None, "excess_roi": None, "conclusion": "unknown"}
    if w <= g:
        return {"epv": None, "per_share": None, "excess_roi": None, "conclusion": "wacc<=growth"}
    nopat = eb * (1.0 - t)
    epv = nopat / (w - g)
    excess_roi = None
    if roic is not None:
        try:
            excess_roi = float(roic) - w
        except (TypeError, ValueError):
            excess_roi = None
    conclusion = "earnings-power-floor"
    if excess_roi is not None and excess_roi < 0:
        conclusion = "earnings-power-weak (RoIC < WACC)"
    return {
        "epv": round(epv, 4),
        "per_share": None,
        "excess_roi": round(excess_roi, 4) if excess_roi is not None else None,
        "conclusion": conclusion,
    }


def epv_per_share(epv: float | None, shares: float | None) -> float | None:
    """EPV per share = EPV / shares."""
    if epv is None or shares is None:
        return None
    try:
        s = float(shares)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    return round(float(epv) / s, 4)


__all__ = [
    "graham_number",
    "graham_cheap",
    "ncav_per_share",
    "ncav_cheap",
    "earnings_power_value",
    "epv_per_share",
]
