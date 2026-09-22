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


def industry_neutral_z(
    values, sector_map: dict | None = None,
    lower_q: float = 0.01, upper_q: float = 0.99,
) -> dict | None:
    """Industry-neutralized factor z (Grinold-Kahn): winsorize -> demean by
    sector -> z-score the residuals.

    ``values``: iterable aligned with ``sector_map`` entries (index -> sector
    name). Within each sector the factor is demeaned (removes the average
    sector effect), then the demeaned values are standardized cross-sectionally.
    Names NOT in ``sector_map`` are left in a residual "unknown" bucket (they
    are demeaned against each other, not dropped). Requires >= 2 finite
    sector-demeaned values and nonzero std; returns ``{"z": [..], "mean": ..,
    "std": .., "n_sectors": ..}`` or None. Pure / never fabricates.
    """
    wins = winsorize(values, lower_q, upper_q)
    sector_mean: dict = {}
    for idx, v in enumerate(wins):
        if v is None:
            continue
        sec = (sector_map.get(idx) if sector_map else None) or "unknown"
        sector_mean.setdefault(sec, [0.0, 0])
        sector_mean[sec][0] += float(v)
        sector_mean[sec][1] += 1
    demeaned: list = []
    for idx, v in enumerate(wins):
        if v is None:
            demeaned.append(None)
            continue
        sec = (sector_map.get(idx) if sector_map else None) or "unknown"
        m, cnt = sector_mean[sec]
        demeaned.append(float(v) - (m / cnt if cnt else 0.0))
    z = cross_sectional_z([x for x in demeaned if x is not None])
    if z is None:
        return None
    out = []
    zi = 0
    for v in demeaned:
        if v is None:
            out.append(None)
        else:
            out.append(z["z"][zi])
            zi += 1
    return {"z": out, "mean": z["mean"], "std": z["std"],
            "n_sectors": len(sector_mean)}


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

    Returns the weight dict (missing names dropped by the projection), or ``{}``
    when fewer than 2 names survive **or** when the projection annihilates the
    book - which happens exactly when the input already lay in the constraint
    space (all longs sharing one beta, all shorts another, equal-weighted). Then
    there is no neutral book carrying that alpha structure, and an empty result
    is the honest answer rather than the input handed back as if it were
    neutral.
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
    raw_gross = sum(abs(v) for v in raw)
    gross = sum(abs(v) for v in adj)
    # A projection that annihilates the book means the INPUT lay entirely in the
    # constraint space - an equal-weighted, beta-matched long/short leg set is
    # exactly that - so there is no neutral book carrying this alpha structure.
    # Two things were wrong here: the guard tested `gross <= 0`, which the
    # ~1e-16 residue of a correct projection never satisfies, so
    # `gross_target / 1e-15` amplified that noise into a fully-invested book
    # with a plausible gross of 1.0; and the fallback returned the RAW book,
    # which violates the very constraints the caller asked for while the
    # function's contract says it enforces them. Both are replaced by an honest
    # empty result - "no book survives" is not "a book that is not neutral".
    if not math.isfinite(gross) or gross <= 1e-12 * raw_gross:
        return {}
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


def group_median(values_by_key, groups, min_n=5):
    """Per-group median of ``values_by_key`` partitioned by ``groups``.

    ``values_by_key`` maps a key to a value; ``groups`` maps the same key to its
    group label (e.g. sector). Returns ``{group: {"median": float, "n": int} |
    None}`` - a group with fewer than ``min_n`` finite members maps to ``None``
    (never a median over a handful of names). Pure; no fabrication.
    """
    grouped: dict = {}
    for key, val in (values_by_key or {}).items():
        grp = (groups or {}).get(key)
        if grp is None:
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(f):
            continue
        grouped.setdefault(grp, []).append(f)
    out: dict = {}
    for grp in set((groups or {}).values()):
        if grp is None:
            continue
        vals = grouped.get(grp, [])
        if len(vals) < min_n:
            out[grp] = None
        else:
            out[grp] = {"median": _quantile(vals, 0.5), "n": len(vals)}
    return out


def momentum_book(
    closes_by_name: dict,
    *,
    betas: dict | None = None,
    sector_map: dict | None = None,
    lookback: int = 126,
    vol_window: int = 21,
    frac: float = 0.2,
    min_n: int = 8,
    gross_target: float = 1.0,
) -> dict | None:
    """An advisory cross-sectional momentum BOOK over a caller-supplied panel.

    Composes the primitives rather than re-deriving any of them: the score is
    the ONE risk-adjusted momentum producer (``factors.vol_adjusted_momentum``),
    the rank is ``centered_rank``, the legs are ``quantile_split``, the
    neutralization is ``neutralize_book`` (dollar + beta + sector) and the book
    beta is ``book_risk.net_beta``. Nothing here is a second producer.

    The two legs are equal-weighted (long the top ``frac``, short the bottom
    ``frac``) and then neutralized **within the selected legs**, and the book's
    net beta is reported BEFORE and AFTER the projection so the gate's effect
    is visible rather than asserted.

    ADVISORY, and not an engine: the result never enters ``TradeScore`` and is
    not a gate (master rule 17). It is also **not market breadth** - the panel
    is whatever the caller could see, so ``n`` travels with the read and a book
    over a handful of names must never be read as a decile book of the market.

    ``betas``/``sector_map`` are the caller's: a name missing from ``betas``
    makes the book beta ``None`` (``net_beta`` refuses a partial sum that would
    read as a flat book), and a missing ``sector_map`` simply leaves the book
    dollar+beta neutral instead of sector neutral.

    Returns ``None`` when fewer than ``min_n`` names carry a measurable score -
    a long/short book over four names is not a cross-section - and never a
    fabricated one.
    """
    from .book_risk import net_beta
    from .factors import vol_adjusted_momentum

    scored: dict = {}
    dropped: dict = {}
    for name, closes in (closes_by_name or {}).items():
        key = str(name)
        if not isinstance(closes, list) or not closes:
            dropped[key] = "no close series"
            continue
        score = vol_adjusted_momentum(closes, lookback=lookback, vol_window=vol_window)
        if score is None:
            dropped[key] = f"fewer than {lookback + vol_window} bars"
            continue
        scored[key] = float(score)
    if len(scored) < min_n:
        return None

    names = sorted(scored)
    scores = [scored[n] for n in names]
    ranks = centered_rank(scores)
    buckets = quantile_split(scores, frac=frac, keyed=names)
    top, bottom = list(buckets["top"]), list(buckets["bottom"])

    leg_weights = dict.fromkeys(names, 0.0)
    for n in top:
        leg_weights[n] = 1.0 / len(top)
    for n in bottom:
        leg_weights[n] = -1.0 / len(bottom)
    # Neutralize ONLY the selected legs. Projecting over the whole panel also
    # spreads the hedge onto names that were never selected (the orthogonal
    # adjustment is distributed across every name in the input), which turns a
    # "long the top quintile / short the bottom" book into a book that quietly
    # holds the middle too.
    legs = {n: w for n, w in leg_weights.items() if w != 0.0}
    weights = neutralize_book(
        legs, betas=betas, sector_map=sector_map, gross_target=gross_target
    )
    gross = sum(abs(v) for v in weights.values())

    return {
        "n": len(names),
        "n_scored": len(scored),
        "dropped": dropped,
        "lookback": lookback,
        "vol_window": vol_window,
        "frac": frac,
        "top": top,
        "bottom": bottom,
        "k_top": len(top),
        "k_bottom": len(bottom),
        "scores": {n: round(scored[n], 6) for n in names},
        "ranks": {n: round(ranks[i], 6) for i, n in enumerate(names)},
        "leg_weights": {n: round(v, 6) for n, v in leg_weights.items()},
        "weights": weights,
        "net_beta_raw": net_beta(legs, betas or {}),
        "net_beta": net_beta(weights, betas or {}),
        "gross": round(gross, 6),
        "sector_neutral": bool(sector_map),
        "basis": (
            f"risk-adjusted momentum (lookback {lookback}, vol window {vol_window}) "
            f"over {len(names)} scored name(s), top/bottom {frac:.0%} "
            f"({len(top)}/{len(bottom)} names), neutralized "
            f"{'dollar+beta+sector' if sector_map else 'dollar+beta'} "
            f"within the selected legs"
        ),
    }


__all__ = [
    "winsorize",
    "cross_sectional_z",
    "industry_neutral_z",
    "centered_rank",
    "quantile_split",
    "residualize_returns",
    "neutralize_book",
    "no_trade_band",
    "group_median",
    "momentum_book",
]
