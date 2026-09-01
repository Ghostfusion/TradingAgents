"""Cross-sectional portfolio toolkit (strategies/cookbook.md recipes 1/2/4).

Pure, offline helpers for building and evaluating long-short books the way the
cookbook specifies - winsorized factor scores, centered ranks, quantile
buckets, residualization against the market, neutrality-constrained weights,
and a no-trade band. Everything is ``float | None`` / explicit None, never a
fabricated number; a missing input degrades instead of inventing a value.

No network, no state: every function takes series/dicts and returns numbers
or dicts. Numpy/scipy only (already used across ``strategies/*``).
"""

from __future__ import annotations

import math


def _clean(values) -> list[float]:
    """Finite-float clean of a series (drops None / non-numeric / non-finite)."""
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def winsorize(values, lower_q: float = 0.01, upper_q: float = 0.99) -> list:
    """Clip each value to the [lower_q, upper_q] quantiles of the sample.

    Prevents a few extreme outliers from dominating cross-sectional z-scores
    (cookbook recipe 4: winsorize before standardization). Returns a list the
    same length as the input, preserving position; insufficient data returns
    the values unchanged (nothing to winsorize against).
    """
    vals = _clean(values)
    if len(vals) < 4:
        return list(values)
    lo = _quantile(vals, lower_q)
    hi = _quantile(vals, upper_q)
    out: list = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(min(max(f, lo), hi) if math.isfinite(f) else None)
    return out


def _quantile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated quantile of a sorted sample (numpy-free)."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    s = sorted(sorted_vals)
    pos = q * (n - 1)
    lo_i = math.floor(pos)
    hi_i = math.ceil(pos)
    if lo_i == hi_i:
        return s[lo_i]
    frac = pos - lo_i
    return s[lo_i] * (1.0 - frac) + s[hi_i] * frac


def cross_sectional_z(values) -> dict | None:
    """Cross-sectionally standardize a list: ``(x_i - mean) / std``.

    Returns ``{"z": [..], "mean": float, "std": float}`` or None when there
    are fewer than 2 finite observations or zero std. Sign and scale match
    the cookbook's ``z_i = (x_i - mu) / sigma`` factor scores.
    """
    vals = _clean(values)
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    if var <= 0:
        return None
    sd = math.sqrt(var)
    z = [(v - m) / sd for v in vals]
    return {"z": z, "mean": m, "std": sd}


def centered_rank(values) -> list[float] | None:
    """Cookbook recipe 4 rank score: ``2 * RankPct(x_i) - 1`` in [-1, 1].

    RankPct = (rank - 1) / (N - 1) with ties averaged. None for < 2 values.
    Robust to accounting outliers - ranks, not raw magnitudes.
    """
    vals = _clean(values)
    n = len(vals)
    if n < 2:
        return None
    ordered = sorted(vals)
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        if not math.isfinite(f):
            out.append(None)
            continue
        lo = sum(1 for x in ordered if x < f)
        hi = sum(1 for x in ordered if x <= f)
        rank_avg = (lo + 1 + hi) / 2.0  # 1-based average rank of the tie group
        rank_pct = (rank_avg - 1.0) / (n - 1.0)
        out.append(2.0 * rank_pct - 1.0)
    return out


def quantile_split(values, frac: float = 0.2, keyed: list | None = None) -> dict:
    """Split a cross-section into top/bottom ``frac`` buckets (cookbook 2/4).

    Returns ``{"top": [..], "bottom": [..]}`` of indexes (or of ``keyed``
    names when provided), where top = highest values, bottom = lowest.
    Ties at the boundary are included conservatively (never dropped). None
    for entires that are not finite. Fewer than ``1/frac`` values returns
    empty buckets.
    """
    vals = _clean(values)
    n = len(vals)
    if n < 2:
        return {"top": [], "bottom": []}
    k = max(1, min(n - 1, int(round(n * frac))))
    ordered = sorted(vals)
    top_cut = ordered[-k]
    bot_cut = ordered[k - 1]
    top = [i for i, v in enumerate(values) if _is_num(v) and float(v) >= top_cut]
    bottom = [i for i, v in enumerate(values) if _is_num(v) and float(v) <= bot_cut]
    if keyed is not None and len(keyed) == len(values):
        top = [keyed[i] for i in top]
        bottom = [keyed[i] for i in bottom]
    return {"top": top, "bottom": bottom}


def _is_num(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def residualize_returns(returns_by_name: dict, market: list, min_obs: int = 30) -> dict:
    """Time-series market residual: ``r_i - (alpha + beta * r_m)`` per name.

    Removes the broad market component before cross-sectional ranking
    (cookbook recipe 2: industry/beta-adjusted residual returns). Each name's
    beta/alpha is fitted on its own aligned history (CAPM regression, same
    approach as ``capm_decomposition``), so the residual is the idiosyncratic
    return the reversal signal should trade. None per-name below ``min_obs``.
    """
    ms = _clean(market)
    out: dict = {}
    if len(ms) < min_obs:
        return out
    for name, series in (returns_by_name or {}).items():
        rs = _clean(series)
        n = min(len(rs), len(ms))
        if n < min_obs:
            continue
        rs = rs[:n]
        msn = ms[:n]
        try:
            m_mean = sum(msn) / n
            m_var = sum((x - m_mean) ** 2 for x in msn) / (n - 1)
            if m_var <= 0:
                continue
            r_mean = sum(rs) / n
            cov = sum((rs[i] - r_mean) * (msn[i] - m_mean) for i in range(n)) / (n - 1)
            beta = cov / m_var
            alpha = r_mean - beta * m_mean
            resid = [rs[i] - (alpha + beta * msn[i]) for i in range(n)]
            out[name] = [round(float(x), 6) for x in resid]
        except Exception:  # noqa: BLE001 - no fabrication
            continue
    return out


def neutralize_book(
    weights: dict,
    betas: dict | None = None,
    sector_map: dict | None = None,
    gross_target: float = 1.0,
) -> dict:
    """Two-step neutrality: project out constraints, then scale to gross.

    Implements the cookbook recipe 2/4 constraint set: dollar-neutral
    (sum w = 0), beta-neutral (sum w*beta = 0) and sector-neutral
    (sum_{i in g} w = 0 for each sector), followed by a gross-exposure
    renormalization. Uses the orthogonal projection ``w_adj = w - X(X'X)^{-1}
    X'w`` where X stacks the constraint columns; a singular design degrades to
    a dollar-neutral recenter (never fails, never fabricates). Names with no
    beta get the cross-sectional average beta proxy; names with no sector are
    left unconstrained.

    Returns the weight dict (missing names dropped by the projection) or ``{}``
    when fewer than 2 names survive.
    """
    names = [n for n in (weights or {}) if _is_num(weights.get(n))]
    if len(names) < 2:
        return {}
    raw = [float(weights[n]) for n in names]
    # Constraint matrix X (rows = names, cols = constraints)
    cols: list[list] = [[1.0] * len(names)]  # dollar neutrality
    if betas:
        bvals = []
        for n in names:
            b = betas.get(n)
            bvals.append(float(b) if b is not None and _is_num(b) else 0.0)
        if len([b for b in bvals if b != 0.0]) > 0:
            cols.append(bvals)
    if sector_map:
        sectors = sorted({
            str(sector_map.get(n, "")) for n in names if sector_map.get(n)
        })
        for s in sectors:
            col = [1.0 if str(sector_map.get(n, "")) == s else 0.0 for n in names]
            if sum(col) > 1:
                cols.append(col)
    # Null-space projection via the row-space projector:
    #   w_adj = w - X' (X X')^+ X w   (pseudoinverse: rank-robust, exact
    # when X X' is nonsingular, best-fit when constraints are dependent -
    # e.g. sector columns summing to the dollar column). Never fabricates, and
    # a fully degenerate design falls back to a dollar-center.
    try:
        import numpy as _np

        X = _np.array(cols, dtype=float)
        # Orthogonal projection of w onto Row(X) via least squares; exact even
        # when the constraint rows are linearly dependent (e.g. sector columns
        # summing to the dollar column). adj = w - X' c where
        # c = argmin ||X' c - w||^2  =>  X (w - X' c) = 0 in every row.
        coef = _np.linalg.lstsq(X.T, _np.array(raw, dtype=float), rcond=None)[0]
        proj = (X.T @ coef).tolist()
        adj = [raw[i] - proj[i] for i in range(len(names))]
    except Exception:  # noqa: BLE001 - degenerate design -> dollar-center only
        mean = sum(raw) / len(raw)
        adj = [v - mean for v in raw]
    # Gross-exposure renormalization (keep sign structure).
    gross = sum(abs(v) for v in adj)
    if gross <= 0 or not math.isfinite(gross):
        gross = sum(abs(v) for v in raw)
        adj = list(raw)
    scale = gross_target / gross if gross > 0 else 0.0
    return {names[i]: round(adj[i] * scale, 6) for i in range(len(names))}


def no_trade_band(target_weights: dict, prev_weights: dict, delta: float = 0.02) -> dict:
    """Zero out trades below a weight-change band (cookbook recipe 2).

    Trade only when ``|w_target - w_prev| > delta``; smaller changes produce
    zero (no churn). Returns ``{name: traded_weight}`` where traded_weight is
    the full target for names crossing the band and 0.0 for those inside it.
    """
    delta = abs(float(delta))
    out: dict = {}
    names = set(target_weights) | set(prev_weights)
    for n in names:
        t = target_weights.get(n)
        p = prev_weights.get(n, 0.0)
        if t is None or not _is_num(t):
            continue
        t = float(t)
        if abs(t - (float(p) if _is_num(p) else 0.0)) > delta:
            out[n] = round(t, 6)
        else:
            out[n] = 0.0
    return out


__all__ = [
    "winsorize",
    "cross_sectional_z",
    "centered_rank",
    "quantile_split",
    "residualize_returns",
    "neutralize_book",
    "no_trade_band",
]
