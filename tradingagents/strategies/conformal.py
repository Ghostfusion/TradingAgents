"""Conformalised quantile bands (CQR) for point predictions.

Turns a point estimate into an interval with a *stated* coverage. The point
spread defines the raw quantile interval; conformal calibration then widens it
by the empirical ``(1-alpha)`` quantile of the calibration nonconformity
scores (``|actual - predicted|``).

Honesty contract
----------------
Coverage is guaranteed *marginally only under exchangeability*, so finance
(a drifting, non-exchangeable process) never gets to print a bare nominal
level. Every band carries its ``realized_coverage`` next to ``nominal`` - a
band without a realized-coverage line is a bug, not a display choice. Below the
``min_n`` floor the band degrades to ``None`` rather than emit an uncalibrated
interval.
"""

from __future__ import annotations

import math


def _finite(values) -> list[float]:
    """Coerce a sequence to finite floats, dropping None / non-numeric / nan."""
    out: list[float] = []
    for v in values or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolated empirical quantile of a pre-sorted-friendly sample."""
    vals = sorted(values)
    n = len(vals)
    if n == 1:
        return vals[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def calibrate(scores, alpha: float) -> float | None:
    """Empirical ``(1-alpha)`` quantile of the calibration scores.

    Uses the finite-sample conformal order statistic
    ``ceil((n+1)*(1-alpha))`` (1-based). Returns ``None`` for empty /
    all-degenerate input or an ``alpha`` outside ``(0, 1)``.
    """
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        return None
    if not (0.0 < a < 1.0):
        return None
    vals = sorted(_finite(scores))
    if not vals:
        return None
    n = len(vals)
    level = math.ceil((n + 1) * (1.0 - a))
    level = max(1, min(level, n))
    return vals[level - 1]


def coverage(pairs, low, high) -> float | None:
    """Fraction of ``(predicted, actual)`` pairs whose actual lies in [low, high]."""
    if low is None or high is None:
        return None
    try:
        lo = float(low)
        hi = float(high)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return None
    actuals = [a for _, a in _clean_pairs(pairs)]
    if not actuals:
        return None
    inside = sum(1 for a in actuals if lo <= a <= hi)
    return inside / len(actuals)


def _clean_pairs(pairs):
    """Keep ``(predicted, actual)`` pairs where both sides are finite floats."""
    out: list[tuple[float, float]] = []
    for pair in pairs or []:
        try:
            p, a = pair
        except (TypeError, ValueError):
            continue
        pf, af = _finite([p]), _finite([a])
        if pf and af:
            out.append((pf[0], af[0]))
    return out


def quantile_band(points, alpha: float, scores=None) -> dict | None:
    """CQR band from point-prediction spread, widened by calibrated scores.

    ``points`` are the model's point predictions whose spread defines the raw
    interval ``[q_{alpha/2}, q_{1-alpha/2}]``. When ``scores`` (calibration
    nonconformity scores) are supplied the band is widened by their empirical
    ``(1-alpha)`` quantile. Returns ``{"low", "high", "nominal", "basis"}`` or
    ``None`` for empty / degenerate input / invalid ``alpha``.

    Coverage is marginal only under exchangeability; use :func:`rolling_band`
    (which reports realized coverage) whenever a backtest window exists.
    """
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        return None
    if not (0.0 < a < 1.0):
        return None
    pts = _finite(points)
    if not pts:
        return None
    if scores is None:
        q = 0.0
        calibrated = False
    else:
        q = calibrate(scores, a)
        if q is None:
            return None
        calibrated = True
    low = _quantile(pts, a / 2.0) - q
    high = _quantile(pts, 1.0 - a / 2.0) + q
    basis = (
        f"CQR quantile band: {len(pts)} point predictions, "
        f"q[{a / 2.0:.3f},{1.0 - a / 2.0:.3f}]"
        + (f" widened by calibrated |residual| quantile of {len(_finite(scores))} scores"
           if calibrated else " uncalibrated (no calibration scores)")
    )
    return {"low": low, "high": high, "nominal": 1.0 - a, "basis": basis}


def rolling_band(
    pairs, window: int = 250, alpha: float = 0.1, min_n: int = 40
) -> dict | None:
    """Rolling conformal band over ``(predicted, actual)`` history.

    A proper split: the most recent ``window`` pairs calibrate, the earlier
    pairs train (their point predictions define the raw quantile interval; when
    there are no earlier pairs the calibration predictions are used). The
    calibration window's ``|actual - predicted|`` scores are the nonconformity
    scores, widened by their ``(1-alpha)`` empirical quantile.

    Returns ``{"low", "high", "nominal", "realized_coverage", "window", "n",
    "basis"}`` or ``None`` when the calibration window has fewer than ``min_n``
    usable pairs / invalid ``alpha``.

    Coverage is guaranteed marginally only under exchangeability - the realized
    coverage is therefore always reported next to the nominal level.
    """
    try:
        a = float(alpha)
        w = int(window)
        floor = int(min_n)
    except (TypeError, ValueError):
        return None
    if not (0.0 < a < 1.0) or w < 1 or floor < 1:
        return None
    clean = _clean_pairs(pairs)
    if len(clean) < floor:
        return None
    calib = clean[-w:]
    train = clean[:-w]
    n = len(calib)
    if n < floor:
        return None
    q = calibrate([abs(actual - pred) for pred, actual in calib], a)
    if q is None:
        return None
    pts = [pred for pred, _ in train] if train else [pred for pred, _ in calib]
    low = _quantile(pts, a / 2.0) - q
    high = _quantile(pts, 1.0 - a / 2.0) + q
    realized = coverage(calib, low, high)
    basis = (
        f"rolling conformal band: {len(train)} train / {n} calibration pairs "
        f"(most recent window={w}); score=|actual-predicted|"
    )
    return {
        "low": low,
        "high": high,
        "nominal": 1.0 - a,
        "realized_coverage": realized,
        "window": w,
        "n": n,
        "basis": basis,
    }


__all__ = ["calibrate", "coverage", "quantile_band", "rolling_band"]
