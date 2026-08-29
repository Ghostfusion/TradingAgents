"""Rate / compounding / interpolation + downside helpers (QuantLib Q7/Q9/Q10).

Pure deterministic utilities: rate-convention equivalence (simple /
continuous / annualized), monotone-safe interpolation for sparse series
(never extrapolate), and target-relative downside measures from QuantLib's
risk-statistics toolkit.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Q10 - rate / compounding equivalence (quantlib InterestRate)
# ---------------------------------------------------------------------------


def discount_factor(rate: float, t: float, comp: str = "continuous") -> float | None:
    """Discount factor for a rate under a compounding convention."""
    try:
        r = float(rate)
        tt = float(t)
    except (TypeError, ValueError):
        return None
    if tt < 0 or (r < 0 and comp not in ("simple",)):
        return None
    c = (comp or "continuous").strip().lower()
    if tt == 0:
        return 1.0
    if c in ("simple",):
        if 1.0 + r * tt <= 0:
            return None
        return 1.0 / (1.0 + r * tt)
    if c in ("continuous", "cont"):
        return math.exp(-r * tt)
    if c in ("annual", "annually", "eff", "effective"):
        return (1.0 + r) ** -tt
    return None


def compound_factor(rate: float, t: float, comp: str = "continuous") -> float | None:
    df = discount_factor(rate, t, comp)
    return None if df is None or df <= 0 else 1.0 / df


def equivalent_rate(rate: float, comp: str, target_comp: str, t: float) -> float | None:
    """Convert a rate between conventions so the same discount factor results.

    E.g. a simple annual 5% over 1y <--> continuous ~ ln(1.05). Returns the
    target-convention rate, or None when the conversion is undefined.
    """
    df = discount_factor(rate, t, comp)
    if df is None or df <= 0:
        return None
    tt = float(t)
    tc = (target_comp or "continuous").strip().lower()
    if tt == 0:
        return rate
    if tc in ("continuous", "cont"):
        return -math.log(df) / tt
    if tc in ("simple",):
        return (1.0 / df - 1.0) / tt
    if tc in ("annual", "annually", "eff", "effective"):
        return df ** (-1.0 / tt) - 1.0
    return None


# ---------------------------------------------------------------------------
# Q9 - monotone / log interpolation (no overshoot, never extrapolate)
# ---------------------------------------------------------------------------


def monotone_fill(x: list[float], y: list[float], xi: list[float],
                  method: str = "log_linear", force_positive: bool = True) -> list:
    """Interpolate ``y`` at query points ``xi`` without fabricating tails.

    - ``linear``   : piecewise-linear on ``log(y)`` is ``log_linear``; plain
      linear uses raw values.
    - ``log_linear``: interpolate in log-space (natural for prices/rates that
      must stay positive).
    Points outside the observed ``x`` range are **dropped** (return None) — we
    never extrapolate beyond the data (risk noted in the design doc).
    """
    pts = sorted((float(a), float(b)) for a, b in zip(x, y, strict=True)
                 if a is not None and b is not None and math.isfinite(float(a))
                 and math.isfinite(float(b)))
    if len(pts) < 2:
        return [None] * len(xi)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    lo, hi = xs[0], xs[-1]
    out = []
    for q in xi:
        qf = float(q)
        if qf < lo or qf > hi:
            out.append(None)
            continue
        # locate bracketing node
        i = 0
        while i < len(xs) - 2 and xs[i + 1] < qf:
            i += 1
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        if x1 == x0:
            out.append(y0)
            continue
        f = (qf - x0) / (x1 - x0)
        value = None
        if method == "log_linear":
            if y0 > 0 and y1 > 0:
                value = math.exp(math.log(y0) + (math.log(y1) - math.log(y0)) * f)
            else:
                value = None
        else:  # linear
            value = y0 + (y1 - y0) * f
        if value is not None and force_positive and value < 0:
            value = 0.0
        out.append(value)
    return out


# ---------------------------------------------------------------------------
# Q7 - downside / regret measures (quantlib riskstatistics)
# ---------------------------------------------------------------------------


def downside_measures(returns: list, target: float = 0.0) -> dict:
    """Target-relative downside toolkit distinct from CVaR (QuantLib Q7).

    Ensemble of semi-deviation (about the mean), downside deviation (about the
    target), regret (mean squared shortfall, N/(N-1) biased), shortfall
    probability and average shortfall. Returns float-or-None values.
    """
    vals = [float(r) for r in returns if r is not None]
    out = {"semi_deviation": None, "downside_deviation": None,
           "regret": None, "shortfall_prob": None, "avg_shortfall": None,
           "n": len(vals)}
    if not vals:
        return out
    tgt = float(target)
    n = len(vals)
    mean = sum(vals) / n
    # semi-variance about the mean (observations below mean)
    below_mean = [v for v in vals if v < mean]
    if len(below_mean) >= 2:
        sv = sum((v - mean) ** 2 for v in below_mean) * n / (n - 1) / len(below_mean)
        out["semi_deviation"] = math.sqrt(max(sv, 0.0))
    # downside deviation about the target
    below_t = [v for v in vals if v < tgt]
    if below_t:
        out["downside_deviation"] = math.sqrt(
            sum((tgt - v) ** 2 for v in below_t) / len(below_t))
        out["shortfall_prob"] = len(below_t) / n
        out["avg_shortfall"] = sum(tgt - v for v in below_t) / len(below_t)
        if len(below_t) >= 2:
            out["regret"] = (n / (n - 1.0)) * sum((tgt - v) ** 2 for v in below_t) / n
    return out


__all__ = ["discount_factor", "compound_factor", "equivalent_rate",
           "monotone_fill", "downside_measures"]
