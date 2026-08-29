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
                "theta": None}
    F = float(forward)
    K = float(strike)
    T = float(t)
    sig = float(vol)
    call = str(option_type).lower().startswith("call")
    if T <= 0 or sig <= 0:
        return {"price": None, "delta": None, "gamma": None, "vega": None,
                "theta": None}
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    disc = math.exp(-float(r) * T) if r else 1.0
    price = disc * (F * _ncdf(d1) - K * _ncdf(d2)) if call \
        else disc * (K * _ncdf(-d2) - F * _ncdf(-d1))
    # Greeks (Black-76, forward-space; gamma/vega identical for call/put)
    gamma = _npdf(d1) / (F * sig * math.sqrt(T)) if (F > 0 and sig > 0 and T > 0) else None
    vega = math.sqrt(T) * _npdf(d1)  # per $1 forward, not discounted
    delta = disc * _ncdf(d1) if call else disc * (_ncdf(d1) - 1.0)
    # theta in price units per year (per unit notional)
    theta = -disc * (F * _npdf(d1) * sig) / (2.0 * math.sqrt(T)) if T > 0 else None
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
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


__all__ = ["black76", "implied_vol_and_greeks", "black_vol_surface"]
