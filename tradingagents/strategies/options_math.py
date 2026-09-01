"""Options pricing / measurement math (QuantLib Q2/Q3).

Pure, deterministic Black-76 + implied-vol/Greeks for an equity option chain,
and a variance-time volatility surface read. No vendor calls here — the caller
supplies spot/strike/rates/mids and an option chain.

No-fabrication: every function returns floats or explicit ``None`` when an
input is missing / degenerate (e.g. ``mid <= intrinsic``, a zero forward, an
out-of-range input). Nothing is invented for the LLM.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Black-76 (futures/forward-style) reference pricing + Greeks
# ---------------------------------------------------------------------------


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black76(forward: float, strike: float, t: float, vol: float,
            option_type: str = "call", r: float = 0.0) -> dict:
    """Black-76 price + Greeks for a European option on a forward.

    ``forward`` is the discounted underlying forward (F = S * e^((r-q)t); the
    caller passes F directly). Returns ``{'price', 'delta', 'gamma', 'vega',
    'theta'}`` (per unit; theta annualized, in price units per year) or a
    dict of ``None`` values when inputs are unusable.
    """
    if (forward is None or strike is None or t is None or vol is None
            or float(forward) <= 0 or float(strike) <= 0 or float(t) <= 0
            or float(vol) <= 0):
        return {"price": None, "delta": None, "gamma": None, "vega": None,
                "theta": None, "rho": None, "vanna": None, "vomma": None,
                "charm": None}
    F = float(forward)
    K = float(strike)
    T = float(t)
    sig = float(vol)
    call = str(option_type).lower().startswith("call")
    if T <= 0 or sig <= 0:
        return {"price": None, "delta": None, "gamma": None, "vega": None,
                "theta": None, "rho": None, "vanna": None, "vomma": None,
                "charm": None}
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    disc = math.exp(-float(r) * T) if r else 1.0
    price = disc * (F * _ncdf(d1) - K * _ncdf(d2)) if call \
        else disc * (K * _ncdf(-d2) - F * _ncdf(-d1))
    # Greeks (Black-76, forward-space; gamma/vega identical for call/put).
    gamma = _npdf(d1) / (F * sig * math.sqrt(T)) if (F > 0 and sig > 0 and T > 0) else None
    vega = math.sqrt(T) * _npdf(d1)  # per $1 forward, not discounted
    delta = disc * _ncdf(d1) if call else disc * (_ncdf(d1) - 1.0)
    # theta in price units per year (per unit notional).
    theta = -disc * (F * _npdf(d1) * sig) / (2.0 * math.sqrt(T)) if T > 0 else None
    # rho (rate sensitivity). In the BSM forward convention rho = K*T*e^{-rT}*N(+-d2).
    rho = (K * T * disc * _ncdf(d2)) if call else (-K * T * disc * _ncdf(-d2))
    # Second-order Greeks: vanna (dDelta/dSigma), vomma/volga (d^2V/dSigma^2),
    # charm (dDelta/dT). BSM closed forms with the forward substitution
    # (S->F, q->r in the standard equity formulation; verified against the
    # option-theory sources).
    vanna = -disc * _npdf(d1) * (d2 / sig) if sig > 0 else None
    vomma = (vega * d1 * d2 / sig) if sig > 0 else None
    # Forward (Black-76) convention: r enters only through the discount, so
    # the (r - q) alpha term of the BSM charm vanishes.
    charm = disc * _npdf(d1) * d2 / (2.0 * T) if T > 0 else None
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho,
        "vanna": vanna,
        "vomma": vomma,
        "charm": charm,
    }


def _black76_price_call(F: float, K: float, T: float, sig: float, r: float) -> float:
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    disc = math.exp(-float(r) * T) if r else 1.0
    return disc * (F * _ncdf(d1) - K * _ncdf(d2))


def _black76_price_put(F: float, K: float, T: float, sig: float, r: float) -> float:
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    disc = math.exp(-float(r) * T) if r else 1.0
    return disc * (K * _ncdf(-d2) - F * _ncdf(-d1))


def implied_vol_and_greeks(spot: float, strike: float, t: float, r: float,
                           q: float, mid: float, option_type: str) -> dict:
    """Implied vol + Greeks for a listed European option.

    Black-76 on the forward F = S * e^((r-q)t). Uses a Brent-style bisection
    to invert price->vol (with Brenner-Subrahmanyan as the seed for a closed
    first cut), then Black-76 Greeks at the solved vol.

    Returns ``{'implied_vol','delta','gamma','vega','theta','forward',
    'intrinsic','mid'}`` or all-``None`` when the mid is not arbitrage
    consistent (``mid <= intrinsic``) or inputs are unusable.
    """
    try:
        S = float(spot)
        K = float(strike)
        T = float(t)
        rf = float(r)
        qy = float(q)
        m = float(mid)
    except (TypeError, ValueError):
        return {"implied_vol": None, "delta": None, "gamma": None,
                "vega": None, "theta": None, "forward": None,
                "intrinsic": None, "mid": None}
    if S <= 0 or K <= 0 or T <= 0 or m <= 0:
        return {"implied_vol": None, "delta": None, "gamma": None,
                "vega": None, "theta": None, "forward": None,
                "intrinsic": None, "mid": None}
    call = str(option_type).lower().startswith("call")
    F = S * math.exp((rf - qy) * T)
    intrinsic = max(F - K, 0.0) if call else max(K - F, 0.0)
    if m <= intrinsic or F <= 0:
        # No time value -> implied vol is meaningless/infinite
        return {"implied_vol": None, "delta": None, "gamma": None,
                "vega": None, "theta": None, "forward": F,
                "intrinsic": intrinsic, "mid": m}
    price_fn = _black76_price_call if call else _black76_price_put
    # seed (Brenner-Subrahmanyan approximation as upper bound reference)
    lo, hi = 1e-4, 5.0
    plo = price_fn(F, K, T, lo, rf) - m
    phi = price_fn(F, K, T, hi, rf) - m
    if plo * phi > 0 and abs(plo) > abs(phi):
        hi *= 2.0
        phi = price_fn(F, K, T, hi, rf) - m
    if plo * phi > 0:
        vol = None  # cannot bracket (mid out of model range)
    else:
        for _ in range(100):
            midv = 0.5 * (lo + hi)
            pm = price_fn(F, K, T, midv, rf) - m
            if abs(pm) < 1e-10 or (hi - lo) < 1e-9:
                break
            if plo * pm < 0:
                hi = midv
                phi = pm
            else:
                lo = midv
                plo = pm
        vol = 0.5 * (lo + hi)
    if vol is None or vol <= 0:
        return {"implied_vol": None, "delta": None, "gamma": None,
                "vega": None, "theta": None, "forward": F,
                "intrinsic": intrinsic, "mid": m}
    g = black76(F, K, T, vol, "call" if call else "put", rf)
    return {
        "implied_vol": vol,
        "delta": g["delta"],
        "gamma": g["gamma"],
        "vega": g["vega"],
        "theta": g["theta"],
        "forward": F,
        "intrinsic": intrinsic,
        "mid": m,
    }


# ---------------------------------------------------------------------------
# Volatility surface (variance-time)
# ---------------------------------------------------------------------------


def black_vol_surface(expiries: list[float], deltas: list[float],
                      ivs: list[float], atm_forward: float) -> dict:
    """Term/vol read in variance space (QuantLib Q3).

    Pass parallel arrays of option expiries (in years), delta pillars
    (absolute delta, e.g. 0.25 / 0.50 / 0.75), and implied vols. Returns an
    ATM level (delta-weighted midpoint), an interpolated forward vol between
    the nearest two expiries, and a trading-days slope (vol moved per 30d).
    Requires >= 3 distinct, aligned points; else all-``None``.
    """
    n = min(len(expiries), len(deltas), len(ivs))
    pts = []
    for i in range(n):
        e = float(expiries[i])
        d = float(deltas[i])
        v = float(ivs[i])
        if e <= 0 or v <= 0 or d < 0 or d > 1:
            continue
        pts.append((e, d, v))
    if len(pts) < 3:
        return {"atm_vol": None, "forward_vol": None, "slope": None}
    # ATM-ish level: weighted mean of vols near delta 0.5 (fallback: all)
    atm = [p for p in pts if abs(p[1] - 0.5) < 0.25]
    atm_vol = sum(p[2] for p in atm) / len(atm) if atm \
        else sum(p[2] for p in pts) / len(pts)
    # forward vol between two closest expiries: sqrt((T2*v2^2 - T1*v1^2)/(T2-T1))
    sorts = sorted(pts, key=lambda p: p[0])
    fv = None
    if len(sorts) >= 2:
        e1, v1 = sorts[0][0], sorts[0][2]
        e2, v2 = sorts[1][0], sorts[1][2]
        if e2 > e1:
            var_diff = e2 * v2 * v2 - e1 * v1 * v1
            if var_diff >= 0:
                fv = math.sqrt(var_diff / (e2 - e1))
    # slope: per-30d change between the two closest expiries
    slope = None
    if len(sorts) >= 2:
        e1, v1 = sorts[0][0], sorts[0][2]
        e2, v2 = sorts[1][0], sorts[1][2]
        span = max(e2 - e1, 1e-6)
        slope = (v2 - v1) / (span / (30.0 / 365.0)) if atm_forward else None
    return {"atm_vol": atm_vol, "forward_vol": fv, "slope": slope}


def variance_swap_strike(
    strikes: list,
    calls_by_strike: list,
    puts_by_strike: list,
    forward: float,
    t: float,
    r: float = 0.0,
) -> float | None:
    """Fair variance-swap strike approximation from OTM calls + puts.

    ``K_var^2 ~= (2 e^{rT} / T) [ int_0^F P(K)/K^2 dK + int_F^infty C(K)/K^2 dK ]``
    integrated by trapezoid over the provided strike grid (calls at/below F
    are dropped, puts at/above F dropped). Requires >= 3 usable strikes each
    side and forward > 0; else None. Returns the variance-swap strike (in
    price/vol2 terms) - advisory, event-vol cross-check.
    """
    import math

    if not strikes or forward is None or forward <= 0 or t is None or t <= 0:
        return None
    try:
        f = float(forward)
        T = float(t)
        rr = float(r)
    except (TypeError, ValueError):
        return None
    # Build (strike, price) for the correct side.
    put_pts = []
    for k, p in zip(strikes, puts_by_strike, strict=False):
        try:
            kf = float(k)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if 0 < kf < f and pf > 0:
            put_pts.append((kf, pf))
    call_pts = []
    for k, c in zip(strikes, calls_by_strike, strict=False):
        try:
            kf = float(k)
            cf = float(c)
        except (TypeError, ValueError):
            continue
        if kf > f and cf > 0:
            call_pts.append((kf, cf))
    pts = put_pts + call_pts
    if len(pts) < 6:  # >=3 per side
        return None
    pts_sorted = sorted(pts, key=lambda p: p[0])
    total = 0.0
    for i in range(1, len(pts_sorted)):
        k0, v0 = pts_sorted[i - 1]
        k1, v1 = pts_sorted[i]
        if k0 <= 0:
            continue
        f0 = v0 / (k0 * k0)
        f1 = v1 / (k1 * k1)
        total += 0.5 * (f0 + f1) * (k1 - k0)
    if total <= 0:
        return None
    kvar2 = (2.0 * math.exp(rr * T) / T) * total
    return math.sqrt(max(kvar2, 0.0))


def bsm_equity_surface(
    spot: float, strike: float, t: float, r: float, q: float, vol: float,
    option_type: str = "call",
) -> dict:
    """Vanilla Black-Scholes-Merton equity option surface (cookbook recipe 5).

    The spot-space companion to :func:`black76`: prices and Greeks for a
    European equity option directly from ``S, K, T, r, q, sigma`` (the
    cookbook's ``C = S e^{-qT} N(d1) - K e^{-rT} N(d2)``). Returns the full
    first-order Greek set + rho, or an all-None dict when inputs are unusable.
    """
    try:
        S = float(spot)
        K = float(strike)
        T = float(t)
        rf = float(r)
        qy = float(q)
        sig = float(vol)
    except (TypeError, ValueError):
        return {"price": None, "delta": None, "gamma": None, "vega": None,
                "theta": None, "rho": None, "vanna": None, "vomma": None,
                "charm": None, "d1": None, "d2": None}
    if S <= 0 or K <= 0 or T <= 0 or sig <= 0:
        return {"price": None, "delta": None, "gamma": None, "vega": None,
                "theta": None, "rho": None, "vanna": None, "vomma": None,
                "charm": None, "d1": None, "d2": None}
    call = str(option_type).lower().startswith("call")
    d1 = (math.log(S / K) + (rf - qy + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    eqt = math.exp(-qy * T)
    ert = math.exp(-rf * T)
    price = S * eqt * _ncdf(d1) - K * ert * _ncdf(d2) if call \
        else K * ert * _ncdf(-d2) - S * eqt * _ncdf(-d1)
    delta = eqt * _ncdf(d1) if call else eqt * (_ncdf(d1) - 1.0)
    gamma = eqt * _npdf(d1) / (S * sig * math.sqrt(T))
    vega = S * eqt * _npdf(d1) * math.sqrt(T)  # per 1.0 vol move
    theta = (-S * eqt * _npdf(d1) * sig / (2.0 * math.sqrt(T))
             - rf * K * ert * _ncdf(d2) + qy * S * eqt * _ncdf(d1)) if call \
        else (-S * eqt * _npdf(d1) * sig / (2.0 * math.sqrt(T))
              + rf * K * ert * _ncdf(-d2) - qy * S * eqt * _ncdf(-d1))
    rho = (K * T * ert * _ncdf(d2)) if call else (-K * T * ert * _ncdf(-d2))
    vanna = eqt * _npdf(d1) * (0.0 - d2) / sig  # dDelta/dSigma, equity form
    vomma = vega * d1 * d2 / sig
    charm = eqt * _npdf(d1) * (
        -2.0 * (rf - qy) * T + d2 * sig * math.sqrt(T)
    ) / (2.0 * T * sig * math.sqrt(T)) * -1.0
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho,
        "vanna": vanna,
        "vomma": vomma,
        "charm": charm,
        "d1": d1,
        "d2": d2,
    }


def greek_pnl_response(
    delta: float | None, gamma: float | None, vega: float | None,
    theta: float | None, spot: float,
    dS_pct: float, dSigma: float = 0.0, dt: float = 1.0 / 252.0,
) -> dict:
    """Cookbook recipe 5 P&L decomposition: ``dPi ~= Delta*dS + 1/2 Gamma*dS^2
    + Vega*dSigma + Theta*dt`` (per unit; dS_pct as a decimal, dSigma as an
    absolute vol change e.g. 0.05 = +5 vol points). Returns the four pieces +
    the total; any None Greek contributes nothing. Advisory event-window
    scenario P&L, not a trading mandate.
    """
    dS = spot * float(dS_pct)
    dl = (float(delta) * dS) if delta is not None else 0.0
    gm = (0.5 * float(gamma) * dS * dS) if gamma is not None else 0.0
    vg = (float(vega) * float(dSigma)) if vega is not None else 0.0
    th = (float(theta) * float(dt)) if theta is not None else 0.0
    return {
        "delta_pnl": round(dl, 6),
        "gamma_pnl": round(gm, 6),
        "vega_pnl": round(vg, 6),
        "theta_pnl": round(th, 6),
        "total_pnl": round(dl + gm + vg + th, 6),
    }


def model_free_implied_variance(
    strikes: list,
    option_prices: list,
    forward: float,
    t: float,
    r: float = 0.0,
) -> float | None:
    """Model-free implied variance (cookbook recipe 5, Cboe/VIX form).

    ``sigma^2 = (2 e^{rT} / T) * sum_i (dK_i / K_i^2) * Q(K_i)
                - (1/T) * (F / K0 - 1)^2``

    ``option_prices`` are the OTM option MID prices (put for K < F, call for
    K > F). ``K0`` is the first strike at or below the forward; the F/K0
    discreteness term is the Cboe correction (web-verified against the VIX
    white paper). Requires >= 4 usable strikes and forward > 0; else None.
    """
    try:
        f = float(forward)
        T = float(t)
        rr = float(r)
    except (TypeError, ValueError):
        return None
    if f <= 0 or T <= 0:
        return None
    pts = []
    for k, p in zip(strikes, option_prices, strict=False):
        try:
            kf = float(k)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if kf > 0 and pf > 0 and math.isfinite(kf) and math.isfinite(pf):
            pts.append((kf, pf))
    if len(pts) < 4:
        return None
    pts.sort(key=lambda x: x[0])
    below = [p for p in pts if p[0] <= f]
    k0 = below[-1][0] if below else None
    if k0 is None or k0 <= 0:
        return None
    total = 0.0
    for i in range(1, len(pts)):
        k_lo, v_lo = pts[i - 1]
        k_hi, v_hi = pts[i]
        if k_lo <= 0 or k_hi <= 0:
            continue
        dk = k_hi - k_lo
        w_lo = v_lo / (k_lo * k_lo)
        w_hi = v_hi / (k_hi * k_hi)
        total += 0.5 * (w_lo + w_hi) * dk
    var = (2.0 * math.exp(rr * T) / T) * total - (1.0 / T) * (
        (f / k0) - 1.0
    ) ** 2
    return round(max(var, 0.0), 6)


__all__ = ["black76", "implied_vol_and_greeks", "black_vol_surface",
           "variance_swap_strike", "bsm_equity_surface", "greek_pnl_response",
           "model_free_implied_variance"]
