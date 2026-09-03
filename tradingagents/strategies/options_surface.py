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


__all__ = ["iv_percentile", "iv_skew", "put_call_oi_concentration",
           "implied_move_pct", "expected_move_from_chain",
           "volatility_risk_premium"]
