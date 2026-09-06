"""Lottery-factor screens: MAX + IVOL (Phase 6, advisory).

Bali et al. (2011, JFE): stocks with the largest single-day returns (MAX)
or highest idiosyncratic volatility (IVOL) underperform — a lottery-preference
anomaly confirmed across later samples (US, China, Brazil). These are
cross-sectional predictors; a stock is REJECTED for the lottery tilt when
MAX/IVOL are high. Pure / None-safe; the residual-vol estimate uses the
repo's ols_factors when the market series is given, else total-vol as a fall
(clearly labeled).
"""

from __future__ import annotations


def max_daily_return(closes: list, window: int = 21) -> float | None:
    """MAX = the largest single-day return over ``window`` bars (monthly).

    ``closes`` in date order. None when < 2 usable closes in the window.
    """
    vals = [float(c) for c in (closes or []) if c is not None and c > 0]
    if len(vals) < 2:
        return None
    tail = vals[-window:]
    if len(tail) < 2:
        return None
    best = None
    for i in range(1, len(tail)):
        r = tail[i] / tail[i - 1] - 1.0
        if best is None or r > best:
            best = r
    return best


def max_drawdown_of_closes(closes: list, window: int | None = None) -> float | None:
    """(optional helper) max drawdown over the tail — used to sanity-check a
    lottery reading is not redundant with a distressed name."""
    vals = [float(c) for c in (closes or []) if c is not None and c > 0]
    if len(vals) < 2:
        return None
    if window:
        vals = vals[-int(window):]
    peak = vals[0]
    mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def idiosyncratic_vol(returns: list, market_returns: list | None = None,
                      min_obs: int = 30) -> float | None:
    """IVOL = residual vol of a 1-factor CAPM regression (Bali 2011).

    Regresses ``returns`` on ``market_returns`` (the repo's ols_factors) and
    returns the residual standard deviation (annualized * sqrt(252)). When
    ``market_returns`` is None, falls back to plain total vol (labeled —
    callers expect a 'residual vs total' marker). None when insufficient data.
    """
    r = [float(x) for x in (returns or []) if x is not None]
    if len(r) < min_obs:
        return None
    mu = sum(r) / len(r)
    var = sum((x - mu) ** 2 for x in r) / (len(r) - 1)
    if var <= 1e-12:
        return None
    if market_returns is None:
        # total-vol fallback (no benchmark provided) — NOT idiosyncratic.
        return round((var * 252.0) ** 0.5, 4)
    m = [float(x) for x in market_returns if x is not None]
    if len(m) != len(r) or len(m) < min_obs:
        return round((var * 252.0) ** 0.5, 4)  # honest fallback (total)
    try:
        from .statistical import ols_factors

        fit = ols_factors(r, {"market": m})
        resid = fit.get("residuals") if isinstance(fit, dict) else None
        if not isinstance(resid, list) or not resid:
            return round((var * 252.0) ** 0.5, 4)
        rv = sum(x * x for x in resid) / (len(resid) - 1)
        if rv <= 1e-12:
            return None
        return round((rv * 252.0) ** 0.5, 4)
    except Exception:  # noqa: BLE001 - total-vol fallback is honest
        return round((var * 252.0) ** 0.5, 4)


def lottery_verdict(closes: list, returns: list,
                    market_returns: list | None = None,
                    max_cap: float = 0.15,
                    ivol_cap: float = 0.60) -> dict:
    """Lottery-tilt verdict for one name.

    HIGH MAX (> ``max_cap``) and/or high IVOL (> ``ivol_cap``) flag the
    lottery tilt (over-priced skew -> EXPECTED underperformance). Returns
    ``{'max', 'max_volatile', 'ivol', 'ivol_kind', 'verdict', 'note'}`` where
    ``verdict`` is ``lottery-tilt`` / ``high-vol`` / ``ok``. ``ivol_kind`` =
    ``residual`` or ``total`` (when the market series was unavailable). None
    fields when the inputs are unusable (never fabricated).
    """
    mx = max_daily_return(closes)
    iv = idiosyncratic_vol(returns, market_returns)
    max_volatile = mx is not None and mx > float(max_cap)
    iv_high = iv is not None and iv > float(ivol_cap)
    if mx is None and iv is None:
        return {"max": None, "max_volatile": None, "ivol": None,
                "ivol_kind": None, "verdict": "ok", "note": "n/a (no data)"}
    if max_volatile or iv_high:
        flags = []
        if max_volatile:
            flags.append(f"high MAX {mx:.1%}")
        if iv_high:
            flags.append(f"high IVOL {iv:.0%}")
        verdict = "lottery-tilt"
        if iv is not None and iv > 1.0:
            verdict = "high-vol"  # extreme vol, not just a lottery preference
        return {"max": round(mx, 4) if mx is not None else None,
                "max_volatile": max_volatile,
                "ivol": round(iv, 4) if iv is not None else None,
                "ivol_kind": ("residual" if market_returns is not None else "total") if iv is not None else None,
                "verdict": verdict,
                "note": "; ".join(flags) if flags else "advisory"}
    return {"max": round(mx, 4) if mx is not None else None,
            "max_volatile": False,
            "ivol": round(iv, 4) if iv is not None else None,
            "ivol_kind": ("residual" if market_returns is not None else "total") if iv is not None else None,
            "verdict": "ok", "note": "no lottery tilt (MAX/IVOL within band)"}


__all__ = ["max_daily_return", "max_drawdown_of_closes",
           "idiosyncratic_vol", "lottery_verdict"]
