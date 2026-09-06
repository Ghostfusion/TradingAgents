"""Options depth layer (W3-5): IV surface / rank / skew / OI / expected move.

Extends the existing ``options_math.py`` (Black-Scholes/implied vol) with the
market-structure reads the remediation plan asks for — so an agent can say
"the stock is bullish, but implied volatility already prices a 12% move,
making long calls unattractive" instead of a naked direction call.

All functions pure: inputs are option rows (strike, iv, expiry, oi, ask, bid,
spot) as dicts; missing data -> None, never a guess.
"""

from __future__ import annotations


def iv_percentile(iv_history: list[float | None], current_iv: float | None) -> float | None:
    """IV rank/percentile of ``current_iv`` within a trailing history (0..1);
    None when unmeasurable."""
    hist = [float(x) for x in (iv_history or []) if x is not None]
    if not hist or current_iv is None:
        return None
    below = sum(1 for x in hist if x <= current_iv)
    return below / len(hist)


def iv_skew(otm_put_iv: float | None, atm_iv: float | None,
            otm_call_iv: float | None) -> float | None:
    """Put-skew: (put IV - call IV) / ATM IV. Positive = puts rich (the
    common equity skew); None when any input missing."""
    if not atm_iv or otm_put_iv is None or otm_call_iv is None:
        return None
    return (float(otm_put_iv) - float(otm_call_iv)) / float(atm_iv)


def put_call_oi_concentration(put_oi: float | None, call_oi: float | None) -> float | None:
    """Put : call open-interest ratio (W3-5); >1 = put-side concentration.
    None when unmeasurable."""
    if (put_oi is None or call_oi is None) or call_oi <= 0:
        return None
    return put_oi / call_oi


def implied_move_pct(atm_iv: float | None, days_to_expiry: float | None) -> float | None:
    """ATM-implied one-standard-deviation move over the remaining term
    (%) — the 'options price a 12% move' figure. None when unmeasurable."""
    if atm_iv is None or not days_to_expiry or days_to_expiry <= 0:
        return None
    return atm_iv * (days_to_expiry / 365.0) ** 0.5 * 100.0


def expected_move_from_chain(rows: list[dict]) -> dict:
    """ATR-like + ATM-IV expected move from an options chain (best-effort).
    Returns mid/10d/ATM IV / expected move; None when the chain is empty or
    has no ATM row."""
    if not rows:
        return {"atm_iv": None, "ten_d_move_pct": None, "n_rows": 0}
    atm = min(rows, key=lambda r: abs(float(r.get("strike") or 0) - float(r.get("spot", 0)) or 0))
    iv = atm.get("iv")
    days = atm.get("days_to_expiry")
    if iv is None or days is None:
        return {"atm_iv": None, "ten_d_move_pct": None, "n_rows": len(rows)}
    return {"atm_iv": float(iv), "ten_d_move_pct": implied_move_pct(float(iv), float(days)),
            "n_rows": len(rows)}


def volatility_risk_premium(iv: float | None, realized_vol: float | None) -> float | None:
    """VRP = IV - realized vol (percent). Positive = options overpriced (a
    short-vol edge); None when unmeasurable."""
    if iv is None or realized_vol is None:
        return None
    return (float(iv) - float(realized_vol)) * 100.0


# ---------------------------------------------------------------------------
# Vol-surface shape (25-delta risk reversal / butterfly) + term-structure slope
# ---------------------------------------------------------------------------


def _side_delta_points(rows: list[dict], side: str) -> list[tuple[float, float]]:
    """(|delta|, iv) points for one side via Black-76 (F = spot, r = q = 0)."""
    try:
        from tradingagents.strategies.options_math import black76 as _b76
    except Exception:  # noqa: BLE001 - import guard
        return []
    pts = []
    for r in rows or []:
        if r.get("side") != side:
            continue
        iv = r.get("iv")
        k = r.get("strike")
        spot = r.get("spot")
        days = r.get("days_to_expiry")
        if iv is None or k is None or spot is None or days is None:
            continue
        try:
            ty = max(float(days) / 365.0, 1e-6)
            g = _b76(spot, float(k), ty, float(iv), side, 0.0)
        except (TypeError, ValueError):
            continue
        d = g.get("delta")
        if d is None or float(d) == 0:
            continue
        pts.append((abs(float(d)), float(iv)))
    return pts


def _interp_iv_at(pts: list[tuple[float, float]], target: float = 0.25) -> float | None:
    """Linear-interpolate IV at a target |delta| (e.g. 0.25) over sorted
    (|delta|, iv) points; None when no bracketing pair."""
    pts = sorted(pts)
    # Drop out-of-domain deltas: exactly 0 or 1 (deep-ITM saturation) cannot
    # bracket a 25-delta target and would corrupt the interpolation.
    pts = [(d, v) for d, v in pts if 0.0 < d < 1.0]
    if len(pts) < 2:
        return None
    for i in range(len(pts) - 1):
        d0, v0 = pts[i]
        d1, v1 = pts[i + 1]
        if d0 <= target <= d1 and d1 > d0:
            frac = (target - d0) / (d1 - d0)
            return v0 + frac * (v1 - v0)
    # target outside the observed delta range (e.g. only deep-OTM) -> no
    # bracketing pair -> None (never extrapolate).
    return None


def surface_shape(rows: list[dict]) -> dict:
    """25-delta risk reversal + butterfly from an options chain.

    ``rows``: option rows (strike / iv / days_to_expiry / spot / side). Uses
    Black-76 delta pillars (F = spot, r = q = 0) and linear interpolation to
    25-delta IV per side. Returns ``{'rr25', 'bf25', 'n'}`` where
    ``rr25 = IV(25d call) - IV(25d put)`` (negative = puts rich, the common
    equity skew) and ``bf25 = (IV(25d call) + IV(25d put))/2 - IV(ATM)``
    (smile curvature); all None when either side lacks a bracketing pair.
    """
    call_pts = _side_delta_points(rows, "call")
    put_pts = _side_delta_points(rows, "put")
    iv_c25 = _interp_iv_at(call_pts) if len(call_pts) >= 2 else None
    iv_p25 = _interp_iv_at(put_pts) if len(put_pts) >= 2 else None
    atm = None
    if rows:
        atm = min(rows, key=lambda r: abs(float(r.get("strike") or 0) - float(r.get("spot", 0)) or 0))
    atm_iv = atm.get("iv") if atm else None
    rr = bf = None
    if iv_c25 is not None and iv_p25 is not None:
        rr = iv_c25 - iv_p25
        if atm_iv is not None:
            bf = (iv_c25 + iv_p25) / 2.0 - float(atm_iv)
    return {"rr25": rr, "bf25": bf, "n": len(rows or [])}


def term_structure_slope(atm_iv_short: float | None, atm_iv_long: float | None) -> float | None:
    """Term-structure slope = IV(long) - IV(short) (fraction). Positive =
    backwardation-free / contango (long-dated richer); None when either is
    missing. Compare like-delta ATM vols across expiries."""
    if atm_iv_short is None or atm_iv_long is None:
        return None
    return float(atm_iv_long) - float(atm_iv_short)


# ---------------------------------------------------------------------------
# Put-call parity / conversion-reversal arbitrage screen
# ---------------------------------------------------------------------------


def parity_violation(
    call_mid: float | None,
    put_mid: float | None,
    spot: float | None,
    strike: float | None,
    t: float | None,
    r: float = 0.0,
    div_yield: float = 0.0,
    cost_bps: float = 5.0,
) -> dict:
    """Put-call parity check (European, dividends via q).

    Violation = (C - P) - (S*e^{-qT} - K*e^{-rT}); positive = call rich
    (conversion), negative = put rich (reversal). Returns
    ``{'violation_bps', 'direction', 'flag'}``; ``direction`` in
    (call_rich / put_rich / fair), ``flag`` True when |violation|/S exceeds
    ``cost_bps`` (1bp = 1e-4 of spot) — the arb is only tradable past costs.
    None-safe: any missing input -> all ``None``.
    """
    try:
        c = float(call_mid)
        p = float(put_mid)
        s = float(spot)
        k = float(strike)
        tt = float(t)
        rr = float(r)
        qq = float(div_yield)
    except (TypeError, ValueError):
        return {"violation_bps": None, "direction": None, "flag": None}
    if s <= 0 or k <= 0 or tt <= 0:
        return {"violation_bps": None, "direction": None, "flag": None}
    import math

    parity = s * math.exp(-qq * tt) - k * math.exp(-rr * tt)
    viol = (c - p) - parity
    bps = viol / s * 1e4
    threshold = float(cost_bps)
    direction = "fair"
    if bps > threshold:
        direction = "call_rich"
    elif bps < -threshold:
        direction = "put_rich"
    return {"violation_bps": round(bps, 2), "direction": direction,
            "flag": direction != "fair"}


__all__ = ["iv_percentile", "iv_skew", "put_call_oi_concentration",
           "implied_move_pct", "expected_move_from_chain",
           "volatility_risk_premium", "surface_shape", "term_structure_slope",
           "parity_violation"]
