"""Regime breadth-depth leaves: participation, correlation, concentration,
cross-asset spreads, interaction terms, declared composites and the
statistical-inference family (Phase 2, ``RegimeScore.md`` §8.1 groups 1 and 4).

Every producer here takes its series/panels as ARGUMENTS - this module fetches
nothing and calls no vendor, so a leaf supplies a panel the run already built
(the same ``{name: [close, ...]}`` shape ``market_breadth.market_breadth`` takes)
and reads a number back.

The refusal contract is master rule 1 / ``NA != 0``: a producer that cannot
measure returns ``None`` for an empty/absent input, or a dict whose measured
keys are ``None`` with an ``unavailable`` reason for a present but unmeasurable
input - never ``0``, never a fabricated fallback.

Where the library's §68-§73 composites define a weighted sum but publish NO
weight vector, the composite stays ``None`` and the components are reported
labelled - the owner's rule "report the components, do not invent an index".
"""

from __future__ import annotations

import math
import statistics

import numpy as np

from .ratios import MAD_SCALE as _MAD_TO_SIGMA
from .sector_screener import breadth_with_gate

#: The five cross-asset pair spreads the library names (§58-§63), each as the
#: two roles whose trailing returns are differenced (``R_a - R_b``). Declared
#: roles, not series: the caller supplies the two series, this module never
#: resolves a ticker.
CROSS_ASSET_PAIRS = {
    "risk_on_off": ("risk_assets", "defensive_assets"),
    "cyclical_defensive": ("cyclicals", "defensives"),
    "high_low_beta": ("high_beta", "low_beta"),
    "small_large_cap": ("small_cap", "large_cap"),
    "growth_value": ("growth", "value"),
    "momentum_low_vol": ("momentum", "low_volatility"),
}

#: The components each library composite is built from (§68-§73), in the
#: library's own order. The library publishes ``w_1..w_5`` symbols but no numeric
#: vector, so the composite cannot be formed without an owner-declared weight
#: vector - the components are reported labelled instead.
COMPOSITE_COMPONENTS = {
    "trend": ("ma_slope_z", "momentum_z", "adx", "efficiency_ratio", "breadth"),
    "volatility": ("vol_percentile", "vix_z", "vol_ratio", "vol_of_vol", "tail_risk"),
    "breadth": ("breadth_50", "breadth_200", "new_high_low_ratio", "ad_line", "participation"),
    "liquidity": ("dollar_volume_z", "amihud_z", "volume_participation"),
    "cross_asset": ("equities", "bonds", "credit", "dollar", "commodities", "volatility"),
}

#: Wilder's MAD-to-σ constant, single-sourced from ``ratios.MAD_SCALE``: for a
#: normal sample ``1.4826 * MAD`` estimates σ, so ``_robust_z`` is on the same
#: scale as a standard z (library §76). One definition in the repo.


def _finite(series) -> list[float] | None:
    """The finite floats of one series, or None when it has fewer than two."""
    if not series:
        return None
    try:
        vals = [float(v) for v in series if v is not None]
    except (TypeError, ValueError):
        return None
    vals = [v for v in vals if math.isfinite(v)]
    return vals if len(vals) >= 2 else None


# --- REG-7 / §12: participation counts -------------------------------------


def market_participation(
    closes_by_name: dict,
    *,
    horizons: tuple = (20,),
    trend_windows: tuple = (50, 200),
    min_n: int = 20,
) -> dict | None:
    """Positive-return participation COUNTS over a panel (REG-7, §12).

    ``closes_by_name`` is the same ``{name: [close, ...]}`` panel
    ``market_breadth`` takes. For each horizon ``h`` the count of names whose
    trailing ``h``-bar return is positive is returned (the COUNT, not a
    percentage - ``market_breadth``'s ``pct_above_*`` are percentages and answer
    a different question), with the ratio supplied beside it. The trend leg
    (§12.3) counts names whose short SMA exceeds their long SMA.

    Returns::

        {
          "n": usable names, "coverage": usable / total,
          "small_sample": bool, "min_n": int, "reason": str (small sample),
          "positive_return_counts": {h: count},
          "positive_return_n": int (denominator of the PRIMARY horizon),
          "positive_return_n_by_horizon": {h: denominator},
          "participation_rate": float | None (PRIMARY horizon),
          "participation_rate_by_horizon": {h: ratio | None},
          "positive_trend_count": int | None,
          "positive_trend_rate": float | None,
          "positive_trend_n": int,
          "trend_unavailable": reason | None,
          "basis": str,
        }

    ``participation_rate``/``positive_return_n`` are the PRIMARY horizon's
    (``horizons[0]``) scalars for a single-read consumer, and the ``*_by_horizon``
    maps carry every horizon; ``positive_return_counts`` is the per-horizon count
    mapping - one producer's labelled views, never two producers.

    A panel below ``min_n`` keeps the counts (a count is a count) and withholds
    the RATES with the reason; an empty map returns ``None``. ``trend_windows``
    must be a ``(short, long)`` pair. A name shorter than a horizon is excluded
    from that horizon's denominator, so a positive count is never read over a
    denominator it cannot fill.
    """
    panel = {k: v for k, v in (closes_by_name or {}).items() if _finite(v)}
    if not panel:
        return None
    total = len(closes_by_name or {})
    n = len(panel)
    gated = breadth_with_gate({"n": n}, min_n=min_n)
    small = bool(gated.get("small_sample"))
    counts: dict = {}
    denoms: dict = {}
    rates: dict = {}
    for h in horizons:
        hit = 0
        denom = 0
        for vals in panel.values():
            if len(vals) > h and vals[-h - 1] != 0:
                denom += 1
                if vals[-1] / vals[-h - 1] - 1.0 > 0:
                    hit += 1
        counts[h] = hit
        denoms[h] = denom
        rates[h] = None if (small or denom == 0) else round(hit / denom, 4)
    primary = tuple(horizons)[0] if tuple(horizons) else None

    trend_count: int | None = None
    trend_rate: float | None = None
    trend_n = 0
    trend_unavailable: str | None = None
    if len(tuple(trend_windows)) != 2:
        trend_unavailable = f"trend_windows {tuple(trend_windows)} is not a (short, long) pair"
    else:
        short, long = int(trend_windows[0]), int(trend_windows[1])
        for vals in panel.values():
            if len(vals) >= long and short >= 1:
                trend_n += 1
                if sum(vals[-short:]) / short > sum(vals[-long:]) / long:
                    trend_count = (trend_count or 0) + 1
        if trend_n == 0:
            trend_unavailable = "no name carries both trend windows"
        elif small:
            trend_rate = None
            trend_unavailable = "rate withheld: " + str(gated.get("reason", f"sample {n} < {min_n}"))
        else:
            trend_rate = round((trend_count or 0) / trend_n, 4)

    out = {
        "n": n,
        "coverage": round(n / total, 3) if total else 0.0,
        "positive_return_counts": counts,
        "positive_return_n": None if primary is None else denoms.get(primary, 0),
        "positive_return_n_by_horizon": denoms,
        "participation_rate": None if primary is None else rates.get(primary),
        "participation_rate_by_horizon": rates,
        "positive_trend_count": trend_count,
        "positive_trend_rate": trend_rate,
        "positive_trend_n": trend_n,
        "trend_unavailable": trend_unavailable,
        "small_sample": small,
        "min_n": min_n,
        "basis": (
            f"{n}-name panel; counts of positive {tuple(horizons)}-bar returns "
            f"and of (SMA{int(trend_windows[0])} > SMA{int(trend_windows[1])})"
            if len(tuple(trend_windows)) == 2
            else f"{n}-name panel; counts of positive {tuple(horizons)}-bar returns"
        ) + "; the same-day pct above an SMA is market_breadth's, not this read",
    }
    if small:
        out["reason"] = str(gated.get("reason", f"sample {n} < {min_n}"))
    return out


# --- REG-8 / §13: average pairwise correlation + spike z --------------------


def average_pairwise_correlation(
    returns_by_name: dict,
    *,
    window: int = 60,
    min_obs: int = 20,
    min_names: int = 2,
) -> dict:
    """Average pairwise correlation and its spike z (REG-8, §13.1/§13.3).

    ``returns_by_name`` is ``{name: [return, ...]}`` - aligned simple returns,
    the panel the run already has. Names are aligned on their own last
    observation and the tail of ``window`` observations is used, so the read is
    one ``window``-long cross-section. ``avg_corr`` is the mean of the upper
    triangle of the pairwise Pearson matrix (§13.1; the ceiling form
    ``portfolio._max_pairwise_corr`` is a different, max read). ``spike_z`` ranks
    the LATEST window's average against the panel's own rolling average-correlation
    history (§13.3): ``(rho_t - mean) / sd`` - high = a market-wide risk-off
    regime.

    Returns ``{avg_corr, spike_z, n_names, n_obs, window, rolling_points,
    unavailable, basis}``. ``None`` for an empty map; the reason travels in
    ``unavailable`` when fewer than ``min_names`` usable series, fewer than
    ``min_obs`` aligned observations, or a degenerate rolling history (no
    variance / too few points) prevents the read - never a fabricated 0.
    """
    series = dict((returns_by_name or {}).items())
    if not series:
        return {
            "avg_corr": None,
            "spike_z": None,
            "n_names": 0,
            "n_obs": 0,
            "window": int(window),
            "rolling_points": 0,
            "unavailable": "no return series supplied",
            "basis": "average pairwise Pearson correlation (§13.1) + spike z (§13.3)",
        }

    clean = {}
    for name, vals in series.items():
        if not vals:
            continue
        try:
            f = [float(x) for x in vals if x is not None]
        except (TypeError, ValueError):
            continue
        f = [x for x in f if math.isfinite(x)]
        if len(f) >= 2:
            clean[name] = f

    base = {
        "avg_corr": None,
        "spike_z": None,
        "n_names": len(clean),
        "n_obs": 0,
        "window": int(window),
        "rolling_points": 0,
        "unavailable": None,
        "basis": "average pairwise Pearson correlation (§13.1) + spike z (§13.3)",
    }
    if len(clean) < min_names:
        base["unavailable"] = (
            f"{len(clean)} usable return series, below the {min_names} needed for "
            "a pairwise correlation read"
        )
        return base

    obs = min(len(v) for v in clean.values())
    if obs < min_obs:
        base["unavailable"] = (
            f"{obs} aligned observation(s), below the {min_obs} needed for a "
            "correlation read"
        )
        return base
    matrix = np.asarray([v[-obs:] for v in clean.values()], dtype=float)

    def _avg_corr(block: np.ndarray) -> float | None:
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = np.corrcoef(block)
        if corr.ndim != 2 or not np.all(np.isfinite(corr)):
            return None
        m = corr.shape[0]
        if m < 2:
            return None
        iu = np.triu_indices(m, k=1)
        return float(np.mean(corr[iu]))

    avg = _avg_corr(matrix[:, -min(window, obs):])
    base["avg_corr"] = None if avg is None else round(avg, 4)
    base["n_obs"] = int(obs)

    win = min(int(window), obs)
    rolling = []
    for end in range(win, obs + 1):
        v = _avg_corr(matrix[:, end - win:end])
        if v is not None:
            rolling.append(v)
    base["rolling_points"] = len(rolling)
    if len(rolling) < min_obs:
        base["unavailable"] = (
            f"{len(rolling)} rolling window(s), below the {min_obs} needed for a "
            "spike z"
        )
        return base
    mean = statistics.fmean(rolling)
    sd = statistics.stdev(rolling) if len(rolling) > 1 else 0.0
    if sd <= 0:
        base["unavailable"] = (
            "the rolling average-correlation history has no variance, so its "
            "spike z is undefined"
        )
        return base
    base["spike_z"] = round((rolling[-1] - mean) / sd, 4)
    base["basis"] = (
        f"{len(clean)} names x {obs} aligned observations; avg_corr over the "
        f"trailing {win}; spike_z over {len(rolling)} rolling windows"
    )
    return base


# --- REG-9 / §16: concentration HHI / effective-N --------------------------


def concentration_hhi(weights) -> dict | None:
    """HHI and effective-N from a weight vector (REG-9, §16).

    ``weights`` is an index weight vector, either ``{name: weight}`` or a list of
    weights. The weights are NORMALISED to sum to one, then ``hhi = sum(w_i**2)``
    and ``effective_n = 1 / hhi`` (§16.1/§16.2). A concentrated index has a high
    HHI and a low effective-N; the equal-weight case is HHI ``= 1/N`` and
    effective-N ``= N`` (an invariant the tests pin).

    Returns ``{hhi, effective_n, n_assets, total, basis}``. ``None`` for an empty
    vector; a vector with a non-positive total or a negative weight is refused
    with ``hhi``/``effective_n`` None and the reason in ``unavailable`` - a
    squared-share concentration over a negative or empty denominator is not a
    measurement.
    """
    if weights is None:
        return None
    vals = list(weights.values()) if isinstance(weights, dict) else list(weights)
    if not vals:
        return None
    try:
        clean = [float(x) for x in vals]
    except (TypeError, ValueError):
        return {
            "hhi": None,
            "effective_n": None,
            "n_assets": len(vals),
            "total": None,
            "unavailable": "weight vector carries a non-numeric entry",
            "basis": "HHI = sum(w_i^2); effective_n = 1 / HHI (§16)",
        }
    total = sum(clean)
    if any(w < 0 for w in clean):
        return {
            "hhi": None,
            "effective_n": None,
            "n_assets": len(clean),
            "total": round(total, 6),
            "unavailable": "weight vector carries a negative weight",
            "basis": "HHI = sum(w_i^2); effective_n = 1 / HHI (§16)",
        }
    if total <= 0:
        return {
            "hhi": None,
            "effective_n": None,
            "n_assets": len(clean),
            "total": None,
            "unavailable": f"weight vector sums to {total}, not a positive total",
            "basis": "HHI = sum(w_i^2); effective_n = 1 / HHI (§16)",
        }
    shares = [w / total for w in clean]
    hhi = sum(s * s for s in shares)
    return {
        "hhi": round(hhi, 6),
        "effective_n": round(1.0 / hhi, 4) if hhi > 0 else None,
        "n_assets": len(shares),
        "total": round(total, 6),
        "unavailable": None,
        "basis": f"HHI = sum(w_i^2) over {len(shares)} normalised weights; effective_n = 1 / HHI (§16)",
    }


# --- REG-13 / §58-§63: cross-asset pair spreads ----------------------------


def pair_spread(series_a, series_b, *, window: int = 21, label_a: str = "a",
                label_b: str = "b") -> dict | None:
    """Trailing return spread of two series (REG-13, §58-§63).

    The library's cross-asset spreads are all ``R_a - R_b`` over a window. The
    caller supplies the two close series (the ``CROSS_ASSET_PAIRS`` registry names
    the roles); each trailing ``window``-bar return is differenced.

    Returns ``{label_a, label_b, ret_a, ret_b, spread, window, n_bars, basis,
    unavailable}``. ``None`` when either series is missing or unusable (fewer than
    two points); a series shorter than the window, or a non-positive base close,
    is refused with the measured keys ``None`` and the reason in ``unavailable`` -
    never a spread over a non-computable return.
    """
    a = _finite(series_a)
    b = _finite(series_b)
    if a is None or b is None:
        return None
    n_bars = min(len(a), len(b))
    out = {
        "label_a": label_a,
        "label_b": label_b,
        "ret_a": None,
        "ret_b": None,
        "spread": None,
        "window": int(window),
        "n_bars": n_bars,
        "unavailable": None,
        "basis": f"R_{label_a} - R_{label_b} over {int(window)} bars (§58-§63)",
    }
    if n_bars <= window:
        out["unavailable"] = (
            f"{n_bars} aligned bar(s), need more than the {window}-bar window"
        )
        return out
    base_a, base_b = a[-window - 1], b[-window - 1]
    if base_a <= 0 or base_b <= 0:
        out["unavailable"] = "a base close is non-positive, so a return is undefined"
        return out
    ra = a[-1] / base_a - 1.0
    rb = b[-1] / base_b - 1.0
    out["ret_a"] = round(ra, 6)
    out["ret_b"] = round(rb, 6)
    out["spread"] = round(ra - rb, 6)
    return out


# --- REG-14 / §64-§66: interaction terms -----------------------------------


def interaction_terms(
    *,
    trend_strength=None,
    breadth=None,
    volatility_stress=None,
    correlation=None,
    volatility=None,
) -> dict:
    """The three regime interaction products (REG-14, §64-§66).

    ``trend_breadth = trend_strength * breadth`` (§64 - an index rising because
    most names rise vs a handful). ``trend_vol = trend_strength * (1 -
    volatility_stress)`` (§65, the library's own form: an UNSTABLE trend is the
    trend discounted by the volatility STRESS share). ``correlation_vol =
    correlation * volatility`` (§66, systemic stress).

    All inputs are optional; a term is ``None`` when one of its inputs is
    missing, with the reason in ``unavailable`` per term - never a product over a
    missing factor. Returns ``{terms, inputs, unavailable, basis}``.
    """
    terms: dict = {}
    unavail: dict = {}
    if trend_strength is not None and breadth is not None:
        terms["trend_breadth"] = round(float(trend_strength) * float(breadth), 6)
    else:
        terms["trend_breadth"] = None
        unavail["trend_breadth"] = "needs trend_strength and breadth"
    if trend_strength is not None and volatility_stress is not None:
        terms["trend_vol"] = round(float(trend_strength) * (1.0 - float(volatility_stress)), 6)
    else:
        terms["trend_vol"] = None
        unavail["trend_vol"] = "needs trend_strength and volatility_stress"
    if correlation is not None and volatility is not None:
        terms["correlation_vol"] = round(float(correlation) * float(volatility), 6)
    else:
        terms["correlation_vol"] = None
        unavail["correlation_vol"] = "needs correlation and volatility"
    return {
        "terms": terms,
        "inputs": {
            "trend_strength": trend_strength,
            "breadth": breadth,
            "volatility_stress": volatility_stress,
            "correlation": correlation,
            "volatility": volatility,
        },
        "unavailable": unavail,
        "basis": (
            "§64 trend*breadth; §65 trend*(1-volatility_stress); "
            "§66 correlation*volatility"
        ),
    }


# --- REG-15 / §68-§73: declared composites ---------------------------------


def regime_composite(components: dict, *, weights=None, label: str | None = None) -> dict:
    """A library composite, reported rather than invented (REG-15, §68-§73).

    The library defines five composites as ``sum_i w_i x_i`` (trend, volatility,
    breadth, liquidity, cross-asset) but publishes NO numeric weight vector - only
    the symbols ``w_1..w_5``. So this producer **reports the components labelled
    and refuses the composite** unless the caller supplies a declared ``weights``
    mapping: the owner's rule "report the components, do not invent an index".

    Returns ``{label, components, weights, weights_declared, composite,
    coverage, n_components, n_measured, unavailable, basis}``.

    With ``weights=None`` the composite is ``None`` and ``unavailable`` says the
    vector is not declared. With ``weights`` given, only measured (non-``None``)
    components enter ``composite = sum w_i x_i / sum w_i`` over their own weights,
    and ``coverage`` is the measured share; a weight total of zero or a
    non-numeric value is refused with the reason. Never returns ``None`` - the
    caller always sees the components and the reason.
    """
    comps = dict(components or {})
    out = {
        "label": label,
        "components": comps,
        "weights": dict(weights) if isinstance(weights, dict) else weights,
        "weights_declared": isinstance(weights, dict) and bool(weights),
        "composite": None,
        "coverage": None,
        "n_components": len(comps),
        "n_measured": sum(1 for v in comps.values() if v is not None),
        "unavailable": None,
        "basis": (
            "§68-§73 define sum_i w_i x_i but publish no numeric w_i; the "
            "components are reported and the composite is refused until the owner "
            "declares the vector"
        ),
    }
    if not out["weights_declared"]:
        out["unavailable"] = (
            "no declared weight vector: the library names w_1..w_5 but publishes "
            "no numbers, so the composite is withheld and the components reported"
        )
        return out
    try:
        num = 0.0
        den = 0.0
        for key, val in comps.items():
            if val is None or key not in weights:
                continue
            w = float(weights[key])
            num += w * float(val)
            den += w
    except (TypeError, ValueError):
        out["unavailable"] = "a supplied weight or component is non-numeric"
        return out
    if den <= 0:
        out["unavailable"] = "the declared weights covering the measured components sum to zero"
        return out
    out["composite"] = round(num / den, 6)
    out["coverage"] = round(out["n_measured"] / out["n_components"], 4) if out["n_components"] else None
    out["basis"] = "sum_i w_i x_i / sum_i w_i over the measured components, w_i declared by the caller"
    return out


# --- REG-18 / §43, §76-§78, §81, §85-§88, §92, §95 -------------------------


def _ols_sse(y: list[float], x: list[float]) -> float:
    """Residual sum of squares of an OLS ``y = a + b x`` fit."""
    n = len(y)
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = 0.0 if sxx == 0 else sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=False))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    return sum((yi - (a + b * xi)) ** 2 for xi, yi in zip(x, y, strict=False))


def _chow_test(y, break_index: int, *, x=None, k: int = 2) -> dict | None:
    """Chow structural-break F statistic (REG-18, §43).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``y`` is the series and ``break_index`` the index of the first observation in
    the second segment (``0 < break_index < len(y)``). ``x`` is an optional
    regressor aligned to ``y``; the default is the observation index, so the
    default model is a linear trend with ``k = 2`` parameters (intercept + slope).
    The library's form is
    ``F = ((SSE_R - (SSE_1 + SSE_2)) / k) / ((SSE_1 + SSE_2) / (N - 2k))``.

    Returns ``{f_stat, sse_restricted, sse_segment1, sse_segment2, k, n, n1, n2,
    break_index, unavailable, basis}``. ``None`` for a missing/short series or an
    out-of-range break; a perfect fit (``SSE_1 + SSE_2 == 0``) or an insufficient
    residual df refuses with ``f_stat`` None and the reason.
    """
    if not y:
        return None
    try:
        yy = [float(v) for v in y]
    except (TypeError, ValueError):
        return None
    n = len(yy)
    if not (0 < int(break_index) < n):
        return None
    kk = int(k)
    if n - 2 * kk <= 0:
        return None
    if x is None:
        xx = [float(i) for i in range(n)]
    else:
        if len(x) != n:
            return None
        xx = [float(v) for v in x]
    b = int(break_index)
    sse1 = _ols_sse(yy[:b], xx[:b])
    sse2 = _ols_sse(yy[b:], xx[b:])
    sse_r = _ols_sse(yy, xx)
    out = {
        "f_stat": None,
        "sse_restricted": round(sse_r, 8),
        "sse_segment1": round(sse1, 8),
        "sse_segment2": round(sse2, 8),
        "k": kk,
        "n": n,
        "n1": b,
        "n2": n - b,
        "break_index": b,
        "unavailable": None,
        "basis": "Chow F = ((SSE_R - (SSE_1+SSE_2))/k) / ((SSE_1+SSE_2)/(N-2k)) (§43)",
    }
    denom_df = n - 2 * kk
    if (sse1 + sse2) <= 0:
        out["unavailable"] = "a segment fits the data exactly (SSE_1 + SSE_2 = 0), so F is undefined"
        return out
    out["f_stat"] = round(((sse_r - (sse1 + sse2)) / kk) / ((sse1 + sse2) / denom_df), 6)
    return out


def _robust_z(value, values) -> dict | None:
    """Median/MAD robust z-score (REG-18, §76).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``z = (value - median(values)) / (1.4826 * MAD(values))`` with
    ``MAD = median(|x - median|)``. The ``1.4826`` constant puts the read on a
    standard-z scale for a normal sample. ``ratios.robust_z`` is the SAME §23/§76
    primitive read over a whole series; this is its single-point form (the MAD
    scale is single-sourced from ``ratios.MAD_SCALE``), so one formula, two
    shapes. Returns ``{z, median, mad, scale, n, unavailable, basis}``. ``None``
    for an empty ``values``; a zero MAD refuses ``z`` with the reason (a scale of
    zero has no z) rather than returning 0.
    """
    if values is None:
        return None
    try:
        vals = [float(v) for v in values if v is not None]
    except (TypeError, ValueError):
        return None
    if not vals:
        return None
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    scale = _MAD_TO_SIGMA * mad
    out = {
        "z": None,
        "median": med,
        "mad": mad,
        "scale": scale,
        "n": len(vals),
        "unavailable": None,
        "basis": "z = (x - median) / (1.4826 * MAD) (§76)",
    }
    if scale <= 0:
        out["unavailable"] = "MAD is zero, so the robust scale is zero and no z exists"
        return out
    out["z"] = round((float(value) - med) / scale, 6)
    return out


def _winsorize_series(values, *, lower: float = 0.01, upper: float = 0.99) -> dict | None:
    """Winsorised series: clip to the ``[lower, upper]`` quantiles (REG-18, §77).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``X* = min(max(X, P_lower), P_upper)``. Returns ``{winsorized, lower_value,
    upper_value, lower, upper, n, unavailable, basis}``. ``None`` for an empty
    series; ``upper <= lower`` refuses with the values None and the reason. The
    quantiles are interpolated on the sample (numpy's default), so the clip is
    data-driven rather than a hardcoded band.
    """
    if values is None:
        return None
    try:
        vals = [float(v) for v in values if v is not None]
    except (TypeError, ValueError):
        return None
    if not vals:
        return None
    out = {
        "winsorized": None,
        "lower_value": None,
        "upper_value": None,
        "lower": lower,
        "upper": upper,
        "n": len(vals),
        "unavailable": None,
        "basis": "X* = clip(X, P_lower, P_upper) (§77)",
    }
    if not 0.0 <= lower < upper <= 1.0:
        out["unavailable"] = f"quantiles {lower}/{upper} are not a lower < upper pair in [0, 1]"
        return out
    arr = np.asarray(vals, dtype=float)
    lo = float(np.quantile(arr, lower))
    hi = float(np.quantile(arr, upper))
    out["lower_value"] = lo
    out["upper_value"] = hi
    out["winsorized"] = [min(max(v, lo), hi) for v in vals]
    return out


def _logistic_normalize(value, *, k: float = 1.0, x0: float = 0.0) -> float:
    """Logistic normalisation ``100 / (1 + exp(-k (x - x0)))`` (REG-18, §78).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    A pure 0-100 read on economically meaningful thresholds. The exponent is
    clamped so a large ``k (x - x0)`` saturates to 100 (never overflows) and a
    very negative one to 0.
    """
    z = float(k) * (float(value) - float(x0))
    if z >= 700.0:
        return 100.0
    if z <= -700.0:
        return 0.0
    return 100.0 / (1.0 + math.exp(-z))


def _rolling_z(series, *, window: int = 20, min_obs: int = 2) -> dict | None:
    """Rolling z-normalisation over a trailing window (REG-18, §81).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``Z_t = (X_t - mean(X_{t-L+1..t})) / sd(X_{t-L+1..t})``, the window ending at
    and including ``t``, so the engine adapts to changing conditions. A point
    whose window holds fewer than ``min_obs`` observations, or whose window has
    zero variance, is ``None`` (never 0).

    Returns ``{z, window, min_obs, n, unavailable, basis}``. ``None`` for an empty
    series; ``unavailable`` carries the reason when no point could be normalised.
    """
    if series is None:
        return None
    try:
        vals = [float(v) for v in series if v is not None]
    except (TypeError, ValueError):
        return None
    if not vals:
        return None
    out: list = []
    for t in range(len(vals)):
        start = max(0, t - window + 1)
        block = vals[start:t + 1]
        if len(block) < min_obs:
            out.append(None)
            continue
        mean = statistics.fmean(block)
        sd = statistics.stdev(block) if len(block) > 1 else 0.0
        out.append(None if sd <= 0 else round((vals[t] - mean) / sd, 6))
    n_ok = sum(1 for v in out if v is not None)
    return {
        "z": out,
        "window": int(window),
        "min_obs": int(min_obs),
        "n": len(vals),
        "unavailable": None if n_ok else "no window held enough non-degenerate observations",
        "basis": f"Z_t = (X_t - mean) / sd over the trailing {int(window)} window (§81)",
    }


def _mahalanobis_distance(x, mu, cov) -> dict | None:
    """Mahalanobis distance from a point to a regime centroid (REG-18, §85).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``D = sqrt((x - mu)^T Sigma^{-1} (x - mu))``. ``x`` and ``mu`` are vectors and
    ``cov`` the covariance matrix; the inverse is taken here. Returns
    ``{distance, n_dim, unavailable, basis}``. ``None`` for missing inputs; a
    shape mismatch or a singular/non-finite covariance refuses ``distance`` with
    the reason - never a number from a degenerate inverse.
    """
    if x is None or mu is None or cov is None:
        return None
    try:
        xv = np.asarray([float(v) for v in x], dtype=float)
        mv = np.asarray([float(v) for v in mu], dtype=float)
        cv = np.asarray(cov, dtype=float)
    except (TypeError, ValueError):
        return None
    out = {
        "distance": None,
        "n_dim": int(xv.size),
        "unavailable": None,
        "basis": "D = sqrt((x - mu)^T Sigma^{-1} (x - mu)) (§85)",
    }
    if xv.ndim != 1 or mv.ndim != 1 or xv.size != mv.size or cv.shape != (xv.size, xv.size):
        out["unavailable"] = (
            f"shapes x={xv.shape}, mu={mv.shape}, cov={cv.shape} do not agree at dim {xv.size}"
        )
        return out
    if not (np.all(np.isfinite(xv)) and np.all(np.isfinite(mv)) and np.all(np.isfinite(cv))):
        out["unavailable"] = "a non-finite entry in x, mu or cov"
        return out
    try:
        precision = np.linalg.inv(cv)
    except np.linalg.LinAlgError:
        out["unavailable"] = "the covariance matrix is singular, so no inverse exists"
        return out
    diff = xv - mv
    quad = float(diff @ precision @ diff)
    if quad < 0:
        out["unavailable"] = "the quadratic form is negative, so the covariance is not positive-definite"
        return out
    out["distance"] = round(math.sqrt(quad), 6)
    return out


def _regime_similarity(distances) -> dict | None:
    """Regime similarity and normalised probability from distances (REG-18, §86).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``Similarity_k = exp(-D_k^2 / 2)`` and ``P_k = Similarity_k / sum_j
    Similarity_j`` - a probabilistic regime classification. ``distances`` is
    ``{regime: D_k}`` or a list of distances. Returns ``{similarity,
    probability, argmax, n, unavailable, basis}``. ``None`` for no distances; a
    non-positive similarity total refuses with the reason.
    """
    if distances is None:
        return None
    if isinstance(distances, dict):
        items = [(str(k), v) for k, v in distances.items()]
    else:
        items = [(str(i), v) for i, v in enumerate(distances)]
    if not items:
        return None
    sims: dict = {}
    try:
        for name, d in items:
            sims[name] = math.exp(-(float(d) ** 2) / 2.0)
    except (TypeError, ValueError):
        return None
    total = sum(sims.values())
    if total <= 0:
        return {
            "similarity": sims,
            "probability": dict.fromkeys(sims),
            "argmax": None,
            "n": len(sims),
            "unavailable": "every similarity underflowed to zero, so no distribution exists",
            "basis": "Similarity_k = exp(-D_k^2/2); P_k = Sim_k / sum Sim_j (§86)",
        }
    probs = {k: round(v / total, 6) for k, v in sims.items()}
    return {
        "similarity": {k: round(v, 8) for k, v in sims.items()},
        "probability": probs,
        "argmax": max(probs, key=probs.get),
        "n": len(sims),
        "unavailable": None,
        "basis": "Similarity_k = exp(-D_k^2/2); P_k = Sim_k / sum Sim_j (§86)",
    }


def _gaussian_mixture_probability(x, components) -> dict | None:
    """Gaussian-mixture regime posterior ``P(k|x)`` (REG-18, §88).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``components`` is a list of ``{weight, mean, cov}``; ``x`` the feature vector.
    ``P(k|x) = pi_k N(x | mu_k, Sigma_k) / sum_j pi_j N(x | mu_j, Sigma_j)``.
    Multivariate-normal densities are evaluated with the covariance inverse and
    determinant from numpy. Returns ``{probability, density, argmax,
    n_components, unavailable, basis}``. ``None`` for missing inputs; a component
    with a singular covariance or mismatched shape refuses with the reason.
    """
    if x is None or not components:
        return None
    try:
        xv = np.asarray([float(v) for v in x], dtype=float)
    except (TypeError, ValueError):
        return None
    weights: list[float] = []
    densities: list[float] = []
    try:
        for comp in components:
            mean = np.asarray([float(v) for v in comp["mean"]], dtype=float)
            cov = np.asarray(comp["cov"], dtype=float)
            if mean.shape != xv.shape or cov.shape != (xv.size, xv.size):
                return {
                    "probability": None,
                    "density": None,
                    "argmax": None,
                    "n_components": len(components),
                    "unavailable": "a component's mean/cov shape does not match x",
                    "basis": "P(k|x) = pi_k N(x|mu_k, Sigma_k) / sum_j pi_j N(...) (§88)",
                }
            det = float(np.linalg.det(cov))
            if det <= 0 or not math.isfinite(det):
                return {
                    "probability": None,
                    "density": None,
                    "argmax": None,
                    "n_components": len(components),
                    "unavailable": "a component covariance is singular (non-positive determinant)",
                    "basis": "P(k|x) = pi_k N(x|mu_k, Sigma_k) / sum_j pi_j N(...) (§88)",
                }
            inv = np.linalg.inv(cov)
            diff = xv - mean
            quad = float(diff @ inv @ diff)
            dens = math.exp(-0.5 * quad) / math.sqrt(((2.0 * math.pi) ** xv.size) * det)
            weights.append(float(comp.get("weight", 1.0)))
            densities.append(dens)
    except (KeyError, TypeError, ValueError, np.linalg.LinAlgError):
        return None
    num = [w * d for w, d in zip(weights, densities, strict=False)]
    total = sum(num)
    if total <= 0:
        return {
            "probability": None,
            "density": None,
            "argmax": None,
            "n_components": len(components),
            "unavailable": "the mixture density underflowed to zero at x",
            "basis": "P(k|x) = pi_k N(x|mu_k, Sigma_k) / sum_j pi_j N(...) (§88)",
        }
    probs = [n_i / total for n_i in num]
    return {
        "probability": [round(p, 6) for p in probs],
        "density": [round(d, 10) for d in densities],
        "argmax": int(max(range(len(probs)), key=lambda i: probs[i])),
        "n_components": len(components),
        "unavailable": None,
        "basis": "P(k|x) = pi_k N(x|mu_k, Sigma_k) / sum_j pi_j N(...) (§88)",
    }


def _coverage_confidence(coverage, data_quality) -> dict:
    """Coverage x data-quality confidence (REG-18, §92).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``CoverageConfidence = Coverage * DataQuality``, both 0-1. Returns
    ``{confidence, coverage, data_quality, unavailable, basis}``. Either input
    missing refuses ``confidence`` with the reason - never a confidence over an
    absent factor.
    """
    out = {
        "confidence": None,
        "coverage": coverage,
        "data_quality": data_quality,
        "unavailable": None,
        "basis": "CoverageConfidence = Coverage * DataQuality (§92)",
    }
    if coverage is None or data_quality is None:
        out["unavailable"] = "needs both a coverage share and a data-quality share"
        return out
    out["confidence"] = round(float(coverage) * float(data_quality), 6)
    return out


def _factor_weighted_confidence(rows) -> dict | None:
    """Weighted availability x quality x freshness confidence (REG-18, §95).

    Built, tested and awaiting its consumer (``RegimeScore.md`` §8.2 group
    4); private so the wiring gate does not require a fabricated caller.

    ``rows`` is a list of ``{weight, availability, quality, freshness}``;
    ``Confidence = sum_i w_i A_i Q_i F_i / sum_i w_i``. Only rows with a numeric
    ``weight`` enter. Returns ``{confidence, n_components, weight_total,
    unavailable, basis}``. ``None`` for no rows; a non-positive weight total
    refuses with the reason.
    """
    if not rows:
        return None
    num = 0.0
    den = 0.0
    used = 0
    for row in rows:
        try:
            w = float(row.get("weight", 0.0))
            num += w * float(row.get("availability", 0.0)) * float(
                row.get("quality", 0.0)
            ) * float(row.get("freshness", 0.0))
            den += w
            used += 1
        except (AttributeError, TypeError, ValueError):
            continue
    out = {
        "confidence": None,
        "n_components": used,
        "weight_total": round(den, 6),
        "unavailable": None,
        "basis": "sum_i w_i A_i Q_i F_i / sum_i w_i (§95)",
    }
    if den <= 0:
        out["unavailable"] = "no row carried a positive weight"
        return out
    out["confidence"] = round(num / den, 6)
    return out


__all__ = [
    "market_participation",
    "average_pairwise_correlation",
    "concentration_hhi",
    "pair_spread",
    "interaction_terms",
    "regime_composite",
    "CROSS_ASSET_PAIRS",
    "COMPOSITE_COMPONENTS",
]
