"""Scenario DCF (quant-engine v2 A2, advisory) — bear / base / bull.

The fork's deterministic ``dcf.py`` projects FCF at a single growth rate;
practice favors a scenario range (vary growth + margin + WACC + terminal g)
so the analyst sees where intrinsic value sits under bear/base/bull — and
the margin of safety under each vs a given market price. Pure / None-safe;
reuses the Gordon terminal-value convention from ``dcf.py``.
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
    market_price: float | None = None,
) -> dict:
    """Scenario DCF per bear/base/bull.

    Each scenario projects a constant FCF at its growth rate, discounts by the
    (constant) WACC, adds a Gordon terminal value, bridges EV -> equity ->
    per-share price, and — when ``market_price`` is given — reports each
    scenario's margin of safety (mos = (fair - mkt) / fair, positive = cheap)
    plus an overall band (below bear / bear-base / base-bull / above bull).
    Scenario growth defaults: base = g_base, bear = g_base - 0.02,
    bull = g_base + 0.02; margin shocks scale the FCF (bear -%, bull +%).
    Returns ``{'scenarios': {name: {price, g, fcf_scale, mos}}, 'inputs': ..,
    'market': {price, band} | {}}``; any missing core input -> all prices
    None (never fabricated).
    """
    f = _num(fcf)
    w = _num(wacc)
    sh = _num(shares)
    ca = _num(cash, 0.0)
    db = _num(debt, 0.0)
    g0 = _num(g_base, 0.03)
    if ca is None:
        ca = 0.0
    if db is None:
        db = 0.0
    if g0 is None:
        g0 = 0.03
    if f is None or w is None or w <= 0:
        return {"scenarios": {}, "inputs": {"fcf": fcf, "wacc": wacc,
                                              "shares": shares, "cash": cash, "debt": debt},
                "market": {}}
    g_bear_v = _num(g_bear, g0 - 0.02)
    g_bull_v = _num(g_bull, g0 + 0.02)
    ms_bear = _num(margin_shock_bear, 0.0) or 0.0
    ms_bull = _num(margin_shock_bull, 0.0) or 0.0

    def value(g: float | None, fcf_scale: float) -> float | None:
        if g is None or w <= g:
            return None
        f_ = f * (1.0 + fcf_scale)
        if f_ < 0:
            return None
        # constant-FCF forever at rate g, discounted by wacc, Gordon TV:
        # EV ~= FCF/(wacc-g) (perpetuity with terminal-value bridge collapsed).
        ev = f_ / (w - g)
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
                     "g": round(g, 4) if g is not None else None,
                     "fcf_scale": round(ms, 4) or 0.0}
    market: dict = {}
    mkt = _num(market_price)
    if mkt is not None and mkt > 0:
        pb, pbase, pbu = out["bear"]["price"], out["base"]["price"], out["bull"]["price"]
        band = None
        if pbase is not None:
            if pb is not None and mkt < pb:
                band = "below bear (deep value)"
            elif mkt < pbase:
                band = "bear-base (discounted)"
            elif pbu is not None and mkt <= pbu:
                band = "base-bull (fair-to-rich)"
            else:
                band = "above bull (premium)"
        for sc in out.values():
            if sc["price"] is not None:
                sc["mos"] = round((sc["price"] - mkt) / sc["price"], 4)
            else:
                sc["mos"] = None
        market = {"price": round(mkt, 2), "band": band,
                  "mos_base": out["base"]["mos"]}
    return {"scenarios": out, "inputs": {"fcf": fcf, "wacc": wacc,
                                          "shares": shares, "cash": cash, "debt": debt},
            "market": market}


__all__ = ["scenario_dcf"]
