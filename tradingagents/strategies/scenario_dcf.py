"""Scenario DCF (quant-engine v2 A2, advisory) — bear / base / bull.

The fork's deterministic ``dcf.py`` projects FCF at a single growth rate;
practice favors a scenario range (vary growth + margin + WACC + terminal g)
so the analyst sees where intrinsic value sits under bear/base/bull — and
the margin of safety under each. Pure / None-safe; reuses the Gordon
terminal-value convention.
"""

from __future__ import annotations


def _num(x, default=None):
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def scenario_dcf(
    fcf: float | None,
    wacc: float | None,
    *,
    shares: float | None = None,
    cash: float | None = None,
    debt: float | None = None,
    g_base: float | None = 0.03,
    g_bear: float | None = None,
    g_bull: float | None = None,
    margin_shock_bear: float | None = None,
    margin_shock_bull: float | None = None,
) -> dict:
    """Scenario DCF per bear/base/bull.

    Each scenario projects a constant FCF at its growth rate, discounts by the
    (constant) WACC, adds a Gordon terminal value, bridges EV -> equity ->
    per-share price, and reports the margin of safety (mos) vs a price when
    given. Scenario growth defaults: base = g_base, bear = g_base - 0.02,
    bull = g_base + 0.02; margin shocks scale the FCF (bear -%, bull +%).
    Returns ``{'scenarios': {name: {price, ev, equity, mos}},
    'inputs': ..}``; any missing core input -> all prices None (never
    fabricated).
    """
    f = _num(fcf)
    w = _num(wacc)
    sh = _num(shares)
    ca = _num(cash, 0.0) or 0.0
    db = _num(debt, 0.0) or 0.0
    g0 = _num(g_base, 0.03) or 0.03
    if f is None or w is None or w <= 0:
        return {"scenarios": {}, "inputs": {"fcf": fcf, "wacc": wacc,
                                              "shares": shares, "cash": cash, "debt": debt}}
    g_bear_v = _num(g_bear, g0 - 0.02)
    g_bull_v = _num(g_bull, g0 + 0.02)
    ms_bear = _num(margin_shock_bear, 0.0) or 0.0
    ms_bull = _num(margin_shock_bull, 0.0) or 0.0

    def value(g: float, fcf_scale: float) -> float | None:
        if g is None or w <= g:
            return None
        f_ = f * (1.0 + fcf_scale)
        if f_ < 0:
            return None
        # constant-FCF forever at rate g, discounted by wacc, Gordon TV:
        # EV ~= FCF/(wacc-g) (perpetuity with terminal-value bridge collapsed).
        denom = w - g
        if denom <= 0:
            return None
        ev = f_ / denom
        equity = ev + ca - db
        if sh and equity > 0:
            return equity / sh
        return None

    out = {}
    for name, g, ms in (("bear", g_bear_v, -abs(ms_bear)),
                        ("base", g0, 0.0),
                        ("bull", g_bull_v, abs(ms_bull))):
        p = value(g, ms)
        out[name] = {"price": round(p, 2) if p is not None else None,
                     "g": round(g, 4), "fcf_scale": round(ms, 4)}
    return {"scenarios": out, "inputs": {"fcf": fcf, "wacc": wacc,
                                          "shares": shares, "cash": cash, "debt": debt}}


__all__ = ["scenario_dcf"]
