"""Phase 3 - value + momentum factor composite.

Cross-sectional style factors computed from price histories, folding the
value screens (scripts/value_screener.py) into one composite rank:

  momentum = total return over (lookback) with (skip) days skipped
  52w distance = price / 52-week high
  vol-adjusted = momentum / realized vol (risk-normalized)

Composite rank uses percentile ranks so factors are comparable across
different magnitude scales; missing factors are skipped (never fabricated).

Also exposes a Fama-French 5-factor time-series regression (alpha + factor
loadings) for style decomposition of an excess return series.
"""

from __future__ import annotations

import math

from .cross_section import cross_sectional_z


def momentum(closes: list[float], lookback: int = 252, skip: int = 21) -> float | None:
    """Cross-sectional momentum (12-1m by default): return over [lookback, skip]."""
    if len(closes) <= lookback + skip:
        return None
    start = closes[-lookback - skip]
    end = closes[-1] if skip == 0 else closes[-skip]
    if start <= 0:
        return None
    return end / start - 1.0


def high_distance(closes: list[float], window: int = 252) -> float | None:
    """Distance from 52-week high: price / trailing high - 1 (<= 0 for losers)."""
    sample = closes[-window:]
    if not sample:
        return None
    hi = max(sample)
    if hi <= 0:
        return None
    return sample[-1] / hi - 1.0


def vol_adjusted_momentum(
    closes: list[float], lookback: int = 126, vol_window: int = 21
) -> float | None:
    """Momentum divided by realized vol (risk-normalized alpha)."""
    from tradingagents.strategies.regime import realized_vol

    mom = momentum(closes, lookback=lookback, skip=0)
    vol = realized_vol(closes, window=vol_window)
    if mom is None or vol is None or vol <= 0:
        return None
    return mom / vol


def percentile_rank(value, values) -> float:
    """Percentile rank (0-1) of `value` within `values`; 0.5 when unknown."""
    valid = [v for v in values if v is not None]
    if not valid:
        return 0.5
    below = sum(1 for v in valid if v <= value)
    return below / len(valid)


def z_score(value, values):
    """(value - mean) / std of a sample; None when insufficient."""
    valid = [float(v) for v in values if v is not None]
    if value is None or len(valid) < 2:
        return None
    m = sum(valid) / len(valid)
    var = sum((v - m) ** 2 for v in valid) / (len(valid) - 1)
    if var <= 0:
        return None
    return (float(value) - m) / (var ** 0.5)


def value_momentum_score(
    factors_by_ticker: dict,
    weights: dict | None = None,
) -> dict:
    """Combined value + momentum composite (AQR-style blend).

    Each ticker's factor dict may carry both momentum factors (``mom``,
    ``dist``, ``vol_adj_mom``) and value factors (``ey``, ``ev_ebit``,
    ``fcf_yield``, ``val_z``). Positive ``val_z`` means cheap-under-valued is
    encoded by the caller as already-inverted or via a negative weight. Uses
    percentile ranks so different magnitudes are comparable; missing factors
    are skipped (never fabricated).
    """
    names: set = set()
    for f in factors_by_ticker.values():
        names.update(k for k, v in f.items() if v is not None)
    names = sorted(names)
    if weights is None:
        weights = dict.fromkeys(names, 1.0)
    scores: dict = {}
    for ticker, factors in factors_by_ticker.items():
        acc = 0.0
        used = 0
        for name in names:
            val = factors.get(name)
            if val is None:
                continue
            rank = percentile_rank(val, [f.get(name) for f in factors_by_ticker.values()])
            w = weights.get(name, 1.0)
            acc += w * rank if w >= 0 else w * (1.0 - rank)
            used += 1
        scores[ticker] = acc / used if used else 0.5
    return scores


def composite_score(factors_by_ticker: dict, weights: dict = None) -> dict:
    """Composite (0-1) per ticker from factor dicts via cross-sectional ranks.

    factors_by_ticker: {ticker: {factor_name: value, ...}}
    weights: {factor_name: weight} (defaults equal weight; negative weights
    are allowed, e.g. {'ev_ebit': -1} for the Acquirer multiple).
    """
    names: set = set()
    for f in factors_by_ticker.values():
        names.update(k for k, v in f.items() if v is not None)
    names = sorted(names)
    if weights is None:
        weights = dict.fromkeys(names, 1.0)
    scores: dict = {}
    for ticker, factors in factors_by_ticker.items():
        acc = 0.0
        used = 0
        for name in names:
            value = factors.get(name)
            if value is None:
                continue
            rank = percentile_rank(value, [f.get(name) for f in factors_by_ticker.values()])
            acc += (
                weights.get(name, 1.0) * rank
                if weights.get(name, 1.0) >= 0
                else weights.get(name, 1.0) * (1.0 - rank)
            )
            used += 1
        scores[ticker] = acc / used if used else 0.5
    return scores


def z_composite_alpha(factors_by_ticker: dict, weights: dict | None = None) -> dict:
    """Cookbook recipe 4 composite alpha: ``A_i = sum_k a_k * z_ik``.

    Standardizes each factor cross-sectionally (``z = (x - mu)/sigma``) and
    sums the weighted z-scores per ticker (``a_V z_value + a_Q z_quality +
    ...``; equal weights by default). Handles negative factor signs via
    negative weights (e.g. ``{'ev_ebit': -1.0}``). A factor with fewer than 2
    finite observations or zero std contributes nothing (honest partial
    score). Returns ``{ticker: score}``.
    """
    factors_by_ticker = factors_by_ticker or {}
    names: set = set()
    for f in factors_by_ticker.values():
        names.update(k for k, v in f.items() if v is not None)
    names = sorted(names)
    if weights is None:
        weights = dict.fromkeys(names, 1.0)
    zs: dict[str, dict] = {}
    for name in names:
        joined = cross_sectional_z([f.get(name) for f in factors_by_ticker.values()])
        if joined is None:
            continue
        zs[name] = joined["z"]
    scores: dict = {}
    for i, ticker in enumerate(factors_by_ticker):
        acc = 0.0
        used = 0
        for name in names:
            zlist = zs.get(name)
            if zlist is None or not ticker or zlist[i] is None:
                continue
            acc += weights.get(name, 1.0) * zlist[i]
            used += 1
        scores[ticker] = round(acc / used, 6) if used else None
    return scores


def momentum_multihorizon(
    closes: list[float],
    horizons: tuple = (21, 63, 126, 252),
) -> dict:
    """Cookbook recipe 1 multi-horizon momentum ensemble (1/3/6/12 months).

    Returns per-horizon simple momentum ``P_t / P_{t-h} - 1`` (None when the
    series is too short) plus ``ensemble`` = the mean of the measurable
    horizons - a single-number trend read that is not hostage to one lookback.
    """
    closes = [c for c in (closes or []) if isinstance(c, (int, float))]
    out: dict = {"horizons": {}, "ensemble": None}
    if not closes:
        return out
    vals: list[float] = []
    for h in horizons:
        h = int(h)
        if len(closes) > h and closes[-(h + 1)] != 0:
            mom = float(closes[-1]) / float(closes[-(h + 1)]) - 1.0
            out["horizons"][str(h)] = round(mom, 6)
            vals.append(mom)
    if vals:
        out["ensemble"] = round(sum(vals) / len(vals), 6)
    return out


# Fama-French 5-factor factor names (order of columns in the regression).
FF5_FACTORS = ("mkt_rf", "smb", "hml", "rmw", "cma")


def _ols5(excess: list[float], factors: dict[str, list[float]]) -> dict:
    """OLS of ``excess ~ intercept + 5 factors`` on aligned, finite rows.

    Returns ``{"alpha", "loadings": {factor: beta}, "r2", "n", "ok": bool}``.
    Uses normal-equation multiply (small matrices); None-safe: any row with a
    non-finite value is dropped, and fewer than 7 aligned rows degrades
    ``ok=False`` (never fabricated).
    """
    n = len(excess)
    X = []
    y = []
    names = list(FF5_FACTORS)
    for i in range(n):
        row = [1.0] + [factors[f][i] if i < len(factors[f]) else float("nan") for f in names]
        yi = excess[i]
        if all(math.isfinite(v) for v in row) and math.isfinite(yi):
            X.append(row)
            y.append(yi)
    m = len(X)
    if m < 7:
        return {"alpha": None, "loadings": dict.fromkeys(names, None),
                "r2": None, "n": m, "ok": False}
    # normal equations: (X'X) beta = X'y  -> use Gaussian elimination
    k = 6
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, yi in zip(X, y, strict=True):
        for a in range(k):
            xty[a] += row[a] * yi
            for b in range(k):
                xtx[a][b] += row[a] * row[b]
    try:
        beta = _solve(xtx, xty)
    except ValueError:
        return {"alpha": None, "loadings": dict.fromkeys(names, None),
                "r2": None, "n": m, "ok": False}
    pred = [sum(beta[j] * row[j] for j in range(k)) for row in X]
    ss_res = sum((y[i] - pred[i]) ** 2 for i in range(m))
    ybar = sum(y) / m
    ss_tot = sum((v - ybar) ** 2 for v in y)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    return {
        "alpha": round(beta[0], 4),
        "loadings": {names[i]: round(beta[i + 1], 4) for i in range(5)},
        "r2": round(r2, 4) if r2 is not None else None,
        "n": m,
        "ok": True,
    }


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination solve of Ax=b (small, dense). Raises on singular."""
    n = len(b)
    aug = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col]
            if f != 0.0:
                aug[r] = [vr - f * vc for vr, vc in zip(aug[r], aug[col], strict=True)]
    return [aug[i][-1] for i in range(n)]


def fama_french_5_factor(
    excess_returns: list[float],
    factors: dict[str, list[float]],
    label: str = "",
) -> dict:
    """Fama-French 5-factor time-series regression (quants.md §Multi-Factor).

    ``excess_returns``: ticker/portfolio return minus risk-free per period.
    ``factors``: dict keyed by FF5_FACTORS (``mkt_rf/smb/hml/rmw/cma``) of
    equal-length series. Returns ``{alpha, loadings, r2, n, ok}``; ``ok``
    False (loadings None) when the aligned sample is too small/singular —
    never fabricated coefficients.
    """
    if not factors or not excess_returns:
        return {"alpha": None, "loadings": None, "r2": None, "n": 0, "ok": False}
    return _ols5(list(excess_returns), factors)


__all__ = [
    "momentum",
    "high_distance",
    "vol_adjusted_momentum",
    "percentile_rank",
    "z_score",
    "value_momentum_score",
    "composite_score",
    "fama_french_5_factor",
    "FF5_FACTORS",
]
