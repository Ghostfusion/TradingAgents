"""Preferred-income / fixed-income analytics (quants.md §Fixed Income).

Pure, offline calculators for bond-like preferreds: yield-to-maturity approx,
Macaulay / modified duration, DV01, and convexity. Preferreds pay fixed
dividends (perpetual) with a par/redemption reference; YTM is rendered only
when a maturity/redemption horizon is inferable (never fabricate a YTM for a
perpetual without a date).

Every function returns ``float | None`` (or a None field in a dict) on
missing / non-positive input - no fabrication.
"""

from __future__ import annotations

__all__ = [
    "indicated_yield",
    "preferred_ytm",
    "macaulay_duration",
    "modified_duration",
    "dv01",
    "bond_convexity",
]


def indicated_yield(annual_dividend: float | None, price: float | None) -> float | None:
    """Indicated annual yield = annual dividend / price."""
    try:
        d = float(annual_dividend)
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p is None or p <= 0 or d is None or d < 0:
        return None
    return d / p


def preferred_ytm(
    annual_dividend: float | None,
    price: float | None,
    par: float | None = 100.0,
    years: float | None = None,
) -> float | None:
    """Approximate yield to maturity (preferred approximation).

    ``YTM ~= (C + (F - P)/n) / ((F + P)/2)`` where C = annual coupon/dividend,
    F = par, P = price, n = years. ``years=None`` (a perpetual with no call /
    redemption date) is **not** converted to a fake YTM - returns None so the
    caller renders ``n/a``; pass ``years`` only when a call/redemption horizon
    is inferable.
    """
    try:
        c = float(annual_dividend)
        p = float(price)
        f = float(par)
        n = float(years) if years is not None else None
    except (TypeError, ValueError):
        return None
    if p is None or p <= 0 or c is None or c < 0 or f is None or f <= 0:
        return None
    if n is None or n <= 0:
        return None  # perpetual: no maturity => no YTM (never fabricated)
    num = c + (f - p) / n
    den = (f + p) / 2.0
    if den <= 0:
        return None
    return num / den


def macaulay_duration(
    cashflows: list[dict] | None,
    yield_pct: float | None,
) -> float | None:
    """Macaulay duration (years) from a cashflow schedule.

    ``cashflows`` = ``[{"t": years_from_now, "amount": $}]``; ``yield_pct`` is
    the annual yield (0.05 = 5%). Only positive-discount cashflows with t > 0
    count. None with insufficient / non-positive inputs.
    """
    if not cashflows or yield_pct is None:
        return None
    try:
        y = float(yield_pct)
    except (TypeError, ValueError):
        return None
    pv_sum = 0.0
    tw = 0.0
    for cf in cashflows:
        try:
            t = float(cf["t"])
            a = float(cf["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if t <= 0 or a <= 0:
            continue
        pv = a / (1.0 + y) ** t
        pv_sum += pv
        tw += t * pv
    if pv_sum <= 0:
        return None
    return tw / pv_sum


def modified_duration(
    macaulay: float | None,
    yield_pct: float | None,
    periods_per_year: float = 1.0,
) -> float | None:
    """Modified duration = Macaulay / (1 + y/m), the first-order price
    sensitivity: ``dP/P ~= -D_mod * dy``."""
    if macaulay is None or yield_pct is None:
        return None
    try:
        m = float(macaulay)
        y = float(yield_pct)
        ppy = float(periods_per_year) or 1.0
    except (TypeError, ValueError):
        return None
    den = 1.0 + y / ppy
    if den <= 0:
        return None
    return m / den


def dv01(
    modified: float | None,
    price: float | None,
) -> float | None:
    """Dollar value of 1bp = D_mod * price * 0.0001."""
    if modified is None or price is None:
        return None
    try:
        dm = float(modified)
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return dm * p * 0.0001


def bond_convexity(
    cashflows: list[dict] | None,
    yield_pct: float | None,
) -> float | None:
    """Convexity = (1/P) * sum_t [ CF_t * t*(t+1) / (1+y)^(t+2) ];

    the second-order price term ``0.5 * Convexity * (dy)^2``.
    """
    if not cashflows or yield_pct is None:
        return None
    try:
        y = float(yield_pct)
    except (TypeError, ValueError):
        return None
    pv_sum = 0.0
    cv = 0.0
    for cf in cashflows:
        try:
            t = float(cf["t"])
            a = float(cf["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if t <= 0 or a <= 0:
            continue
        pv_sum += a / (1.0 + y) ** t
        cv += a * t * (t + 1.0) / (1.0 + y) ** (t + 2.0)
    if pv_sum <= 0:
        return None
    return cv / pv_sum
