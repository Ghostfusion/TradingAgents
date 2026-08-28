"""DCF (Discounted Cash Flow) valuation — deterministic, computed from provider data.

A pragmatic free-cash-flow DCF based on the method in
``Strategies/Discounted_Cash_Flow.md``. It computes an intrinsic equity value
per share from *reported* historical free cash flow (provider-sourced) plus a
few explicit market inputs (risk-free rate, beta/ERP for WACC, shares, cash,
debt), rather than guessing a 5-10yr forecast — the analyst supplies/overrides
the growth assumption.

The derivation is deliberately simple (a "model risk" pragmatic DCF, per the
plan): project the latest FCF forward at a user growth rate ``g``, discount by
a constant WACC, add a Gordon-growth terminal value, then bridge EV -> equity
value -> price per share. It mirrors the document's maths:

    EV = sum FCFF_t / (1+WACC)^t  +  TV / (1+WACC)^n,  TV = FCF_n*(1+g)/(WACC-g)
    Equity = EV + cash - debt
    price = equity / shares

Every input is either provider-sourced or an explicit override; the function
returns "unavailable" (None) when there is no usable free-cash-flow series (the
DCF doc's stated weakness: negative / early-stage cash flows), so the analyst
falls back to multiples rather than fabricate a DCF.
"""

from __future__ import annotations


def wacc_from_beta(rf: float, beta: float, erp: float = 0.05) -> float | None:
    """WACC approx via CAPM cost-of-equity: rf + beta*erp.

    Ignores debt in the first model-risk cut (pragmatic DCF); ``rf`` is the
    10y Treasury yield (fraction), ``beta`` the stock's beta, ``erp`` the
    assumed equity risk premium (default 0.05 = 5%, the usual central bank
    range is 4.5-6%). Returns None when inputs are unusable.
    """
    if rf is None or beta is None:
        return None
    try:
        rf = float(rf)
        beta = float(beta)
        erp = float(erp)
    except (TypeError, ValueError):
        return None
    if beta < 0:
        return None
    return rf + beta * erp


def discount_factor(rate: float, year: int) -> float:
    """1 / (1+rate)^year; rate>=-1, year>=0."""
    if year == 0:
        return 1.0
    return 1.0 / ((1.0 + rate) ** year)


def terminal_value_gordon(latest_fcf: float, wacc: float, g: float) -> float:
    """Gordon growth terminal value = FCF_n*(1+g)/(wacc-g)."""
    denom = wacc - g
    if denom <= 0:
        return float("inf")
    return latest_fcf * (1.0 + g) / denom


def project_fcf(
    latest_fcf: float, g: float, years: int = 5,
) -> list[float]:
    """Project FCF over ``years`` at constant growth ``g`` (fraction)."""
    return [float(latest_fcf) * ((1.0 + float(g)) ** y) for y in range(1, years + 1)]


def compute_dcf(
    historical_fcf: list[float],
    *,
    rf: float,
    beta: float,
    erp: float = 0.05,
    growth: float = 0.025,
    years: int = 5,
    shares: float,
    cash: float = 0.0,
    debt: float = 0.0,
) -> dict | None:
    """Pragmatic DCF -> dict of fair value + breakdown, or None if unusable.

    Args:
        historical_fcf: annual free cash flow series (fraction units, e.g. $1e9).
        rf: risk-free (10y yield, fraction).
        beta: stock beta.
        erp: equity risk premium (default 0.05).
        growth: forward FCF growth rate g (fraction, default 0.025).
        years: explicit forecast years.
        shares: diluted shares outstanding.
        cash: cash + equivalents (bridge).
        debt: total debt (bridge).

    Returns:
        dict with keys {wacc, fcf_latest, growth, ev, tv, pv_tv, equity, price,
        breakdown_text, usable} or None (no usable FCF / inputs / price <= 0).
    """
    fcf = [float(x) for x in historical_fcf if x is not None]
    if not fcf or not shares:
        return None
    # Project the LATEST reported FCF forward (per the docstring), not the
    # historical peak: a declining/hump-shaped FCF history must not inflate the
    # intrinsic value by reusing an old high.
    latest = fcf[-1]
    if latest is None or float(latest) <= 0 or float(shares) <= 0:
        return None
    wacc = _wacc_from_beta(rf, beta, erp)
    if wacc is None or growth >= wacc:
        return None
    proj = project_fcf(latest, growth, years)
    pv_sum = sum(
        fcf * discount_factor(wacc, t + 1) for t, fcf in enumerate(proj)
    )
    tv = terminal_value_gordon(latest, wacc, growth)
    if tv == float("inf"):
        return None
    pv_tv = tv * discount_factor(wacc, years)
    ev = pv_sum + pv_tv
    equity = ev + float(cash) - float(debt)
    price = equity / float(shares) if shares else None
    if price is None or price <= 0:
        return None
    return {
        "wacc": round(wacc, 4),
        "ev": round(ev, 2),
        "pv_explicit": round(pv_sum, 2),
        "pv_tv": round(pv_tv, 2),
        "terminal_share": round(pv_tv / ev if ev else 0, 4),
        "equity_value": round(equity, 2),
        "price": round(price, 2),
        "growth": float(growth),
        "fcf_latest": round(latest, 2),
        "shares": float(shares),
        "usable": True,
    }


# rename helper so compute_dcf can call it; keep public alias too
def _wacc_from_beta(rf, beta, erp: float = 0.05):
    return wacc_from_beta(rf, beta, erp)


__all__ = [
    "wacc_from_beta",
    "discount_factor",
    "terminal_value_gordon",
    "project_fcf",
    "compute_dcf",
]
