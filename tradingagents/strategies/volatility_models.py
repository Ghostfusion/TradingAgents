"""Volatility models (quants.md / quant2.md §Volatility).

Pure, offline, deterministic estimators that complement the close-to-close
realized vol in ``regime.py``:

- Parkinson high-low range estimator (intraday range, day-only estimate),
- Garman-Klass OHLC estimator (range + open-close gap, day-only estimate),
- Yang-Zhang drift-independent OHLC estimator (overnight gap + range), as a
  scalar over a window and as a per-bar series for regime features,
- upside/downside semivariance over the close-to-close series, whose
  decomposition ``RS- + RS+ = RV`` is exact (the score consumes ``sqrt`` of the
  downside leg - `TechnicalScore.md` §4, pinned in `RiskScore.md` §0.3),
- EWMA volatility (RiskMetrics lambda=0.94) — the standard risk-neutral
  vol forecaster,
- GARCH(1,1) conditional volatility via pure-NumPy MLE (long-run vol =
  omega/(1-alpha-beta)).

Every function returns ``float | None`` / dicts with explicit None on
insufficient or degenerate input — never fabricated. All daily-frequency;
annualization uses 252 trading days.
"""

from __future__ import annotations

import math

__all__ = [
    "semivariance",
    "parkinson_vol",
    "garman_klass_vol",
    "yang_zhang_vol",
    "yang_zhang_vol_series",
    "ewma_vol",
    "garch11_fit",
]

_DAYS = 252.0
# alpha + beta at or above this is an IGARCH fit: no unconditional variance
# exists, so the long-run vol is not a measurement (see garch11_fit).
_IGARCH_AB = 0.999


def _clean(vals) -> list[float]:
    out = []
    for v in vals:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f) and f > 0:
            out.append(f)
    return out


def semivariance(
    closes: list,
    window: int | None = None,
    *,
    min_obs: int = 20,
    periods: float = _DAYS,
) -> dict:
    """Upside/downside semivariance over the close-to-close return series.

    ``RS- = sum(min(r,0)^2)/n`` and ``RS+ = sum(max(r,0)^2)/n`` over the SAME
    ``n`` returns (the full sample, not the count of each sign) - which is what
    makes the decomposition exact:

        ``RS- + RS+ = sum(r^2)/n = RV``

    exactly, not approximately (Patton & Sheppard 2015). A conditional
    ``sum(r^2)/n_down`` - the other thing "downside variance" often means -
    does **not** satisfy this and is not what this returns; neither is the
    ``sigma_up/sigma_down`` ratio, which is confounded with drift and partly
    re-measures momentum.

    The persistent leg is ``rs_minus``: it is the one that keeps rising through
    a decline. ``sqrt`` of either leg is a volatility in return units and is
    what a score consumes; the raw values are squared-return units.

    Returns ``{"rs_minus", "rs_plus", "rv", "sqrt_rs_minus", "sqrt_rs_plus",
    "asymmetry", "n", "annualized", "basis"}``. Every leg is ``None`` (with the
    reason in ``basis``) below ``min_obs`` returns - never ``0``, which would
    read as "no downside risk at all".
    """
    rets: list[float] = []
    cs = [c for c in (closes or []) if c is not None]
    try:
        cs = [float(c) for c in cs]
    except (TypeError, ValueError):
        cs = []
    for i in range(1, len(cs)):
        prev = cs[i - 1]
        if prev:
            r = cs[i] / prev - 1.0
            if math.isfinite(r):
                rets.append(r)
    if window:
        rets = rets[-int(window):]
    n = len(rets)
    empty = {
        "rs_minus": None,
        "rs_plus": None,
        "rv": None,
        "sqrt_rs_minus": None,
        "sqrt_rs_plus": None,
        "asymmetry": None,
        "n": n,
        "annualized": None,
        "basis": (
            f"semivariance unavailable: {n} return(s), needs {int(min_obs)} "
            f"(None, never 0 - a missing downside leg is not 'no downside')"
        ),
    }
    if n < int(min_obs):
        return empty
    down = sum(min(r, 0.0) ** 2 for r in rets) / n
    up = sum(max(r, 0.0) ** 2 for r in rets) / n
    rv = sum(r * r for r in rets) / n
    out = {
        "rs_minus": down,
        "rs_plus": up,
        "rv": rv,
        "sqrt_rs_minus": math.sqrt(down),
        "sqrt_rs_plus": math.sqrt(up),
        "asymmetry": (down / up) if up > 0 else None,
        "n": n,
        "annualized": {
            "sqrt_rs_minus": math.sqrt(down * periods),
            "sqrt_rs_plus": math.sqrt(up * periods),
            "rv": math.sqrt(rv * periods),
        },
        "basis": (
            f"semivariance over {n} close-to-close return(s) (window "
            f"{int(window) if window else 'all'}); RS- + RS+ = RV exactly "
            f"({down:.6g} + {up:.6g} = {rv:.6g}); asymmetry RS-/RS+ "
            f"{'n/a' if up <= 0 else f'{down / up:.3f}'}"
        ),
    }
    return out


def parkinson_vol(
    highs: list, lows: list, window: int | None = None, periods: float = _DAYS
) -> float | None:
    """Annualized Parkinson volatility estimator.

    ``sigma_P^2 = sum(ln(H_t/L_t)^2) / (4 * n * ln 2)`` — uses only the
    intraday high-low range. Day-only estimate: assumes continuous trading
    with no overnight gaps (label in the tool output). None with < 2 bars.
    """
    h = _clean(highs)
    lo = _clean(lows)
    n = min(len(h), len(lo))
    if n < 2:
        return None
    if window:
        h, lo = h[-window:], lo[-window:]
        n = min(len(h), len(lo))
        if n < 2:
            return None
    total = 0.0
    for i in range(n):
        if lo[i] <= 0:
            continue
        total += math.log(h[i] / lo[i]) ** 2
    if total <= 0:
        return None
    var = total / (4.0 * n * math.log(2.0))
    return math.sqrt(var * periods)


def garman_klass_vol(
    opens: list,
    highs: list,
    lows: list,
    closes: list,
    window: int | None = None,
    periods: float = _DAYS,
) -> float | None:
    """Annualized Garman-Klass volatility estimator.

    ``sigma_GK^2 = mean[ 0.5 ln^2(H/L) - (2 ln2 - 1) ln^2(C/O) ]``. Day-only
    estimate (no overnight gap term). None with < 2 bars or zero/open <= 0.
    """
    o = [float(x) for x in opens]
    h = [float(x) for x in highs]
    lo = [float(x) for x in lows]
    c = [float(x) for x in closes]
    n = min(len(o), len(h), len(lo), len(c))
    if n < 2:
        return None
    if window:
        o, h, lo, c = o[-window:], h[-window:], lo[-window:], c[-window:]
        n = min(len(o), len(h), len(lo), len(c))
        if n < 2:
            return None
    total = 0.0
    for i in range(n):
        if lo[i] <= 0 or o[i] <= 0:
            continue
        rng = math.log(h[i] / lo[i]) ** 2
        oc = math.log(c[i] / o[i]) ** 2
        total += 0.5 * rng - (2.0 * math.log(2.0) - 1.0) * oc
    if total <= 0:
        return None
    var = total / n
    return math.sqrt(max(var, 0.0) * periods)


def _yz_sample_var(vals: list[float]) -> float | None:
    """Sample variance (ddof=1) over already-collected terms; None below 2."""
    m = len(vals)
    if m < 2:
        return None
    mean = sum(vals) / m
    return sum((v - mean) ** 2 for v in vals) / (m - 1)


def _yz_k(m: int) -> float:
    """The Yang-Zhang weight for ``m`` aligned interior rows.

    **One definition.** The scalar and the per-bar series both call this, so the
    weight cannot drift between them. ``m`` is the number of rows that survived
    the price guard, NOT the requested window: a window containing a bad row has
    ``m < window`` and takes the weight for the rows it actually used.
    """
    return 0.34 / (1.34 + (m + 1.0) / (m - 1.0))


def _yz_legs(
    o: list, h: list, lo: list, c: list
) -> tuple[float, float, float, int] | None:
    """The three Yang-Zhang legs over aligned OHLC rows: ``(var_o, var_c, var_rs, m)``.

    **One alignment convention.** The interior rows are ``i = 1 .. n-1`` of the
    supplied lists, so a window of ``w`` bars yields ``w - 1`` overnight terms -
    the first takes the window's OWN first close, not the bar before it. Both
    callers slice identically, so the series value at bar ``i`` is exactly the
    scalar over the bars ending at ``i`` (pinned for every bar in
    ``tests/test_strategies_covariance_models.py``).

    None below 2 usable interior rows. ``var_rs`` is a MEAN, not mean-corrected:
    Rogers-Satchell is already an unbiased variance term.
    """
    o_terms: list[float] = []
    c_terms: list[float] = []
    rs_terms: list[float] = []
    m = 0  # aligned interior rows (i needs a prior close)
    for i in range(1, len(o)):
        if o[i] <= 0 or c[i - 1] <= 0 or c[i] <= 0 or lo[i] <= 0:
            continue
        m += 1
        o_terms.append(math.log(o[i] / c[i - 1]))
        c_terms.append(math.log(c[i] / o[i]))
        rs_terms.append(
            math.log(h[i] / c[i]) * math.log(h[i] / o[i])
            + math.log(lo[i] / c[i]) * math.log(lo[i] / o[i])
        )
    if m < 2:
        return None
    var_o = _yz_sample_var(o_terms)
    var_c = _yz_sample_var(c_terms)
    if var_o is None or var_c is None:
        return None
    return var_o, var_c, sum(rs_terms) / m, m


def _yz_variance(legs: tuple[float, float, float, int]) -> float:
    """Combine the three legs under the shared weight - the ONE combination."""
    var_o, var_c, var_rs, m = legs
    k = _yz_k(m)
    return var_o + k * var_c + (1.0 - k) * var_rs


def yang_zhang_vol(
    opens: list,
    highs: list,
    lows: list,
    closes: list,
    window: int | None = None,
    periods: float = _DAYS,
) -> float | None:
    """Annualized Yang-Zhang drift-independent volatility estimator.

    ``sigma_YZ^2 = sigma_o^2 + k*sigma_c^2 + (1-k)*sigma_RS^2`` (Yang & Zhang
    2000) where the overnight leg ``sigma_o^2`` is the sample variance of
    ``ln(O_t / C_{t-1})``, the intraday leg ``sigma_c^2`` is the sample
    variance of ``ln(C_t / O_t)``, ``sigma_RS^2`` is the Rogers-Satchell
    range term, and ``k = 0.34 / (1.34 + (m+1)/(m-1))`` with ``m`` the number
    of aligned interior rows. Unlike Parkinson / Garman-Klass (day-only
    estimates), the overnight leg captures the news-gap component, so the
    estimator is drift-independent and complete over the full day. None with
    < 3 bars or a zero total variance (degenerate) — never fabricated.

    One window, one number. For the per-bar series a regime model needs, use
    ``yang_zhang_vol_series``: the same core, so the two cannot disagree.
    """
    o = [float(x) for x in opens]
    h = [float(x) for x in highs]
    lo = [float(x) for x in lows]
    c = [float(x) for x in closes]
    n = min(len(o), len(h), len(lo), len(c))
    if n < 3:
        return None
    if window:
        o, h, lo, c = o[-window:], h[-window:], lo[-window:], c[-window:]
        n = min(len(o), len(h), len(lo), len(c))
        if n < 3:
            return None
    legs = _yz_legs(o[:n], h[:n], lo[:n], c[:n])
    if legs is None:
        return None
    var = _yz_variance(legs)
    if var <= 0:
        return None
    return math.sqrt(var * periods)


def yang_zhang_vol_series(
    opens: list,
    highs: list,
    lows: list,
    closes: list,
    window: int,
    periods: float = _DAYS,
) -> dict:
    """Per-bar Yang-Zhang volatility: the SAME estimator, one window per bar.

    The scalar answers "how volatile was the last window"; a regime model needs
    the whole series. This is **not** a second estimator - it calls the same
    ``_yz_legs`` / ``_yz_k`` / ``_yz_variance`` core, so the value at bar ``i``
    is exactly the scalar over the bars ending at ``i``, for every bar.

    Returns ``{"series", "n", "measured", "window", "basis"}``:

    * ``series`` - aligned to the input and the same length. ``None`` before the
      first full window and for any degenerate window. The warm-up is
      ``window - 1`` bars; a naive nested-rolling implementation (mean, then
      squared deviation, then a second rolling sum) needs ``2 * window`` and
      silently drops rows from whatever trains on it.
    * ``measured`` - how many bars carry a number. Coverage travels with the
      series, so a caller can see how much it actually got.
    * ``None`` rather than ``0`` for an unmeasurable window: a window with no
      measurable variance is a gap, not a quiet market.

    ``window`` must be >= 3 (the core needs 2 interior rows); a smaller window
    yields an all-``None`` series rather than a number nobody should trust.
    """
    o = [float(x) for x in opens]
    h = [float(x) for x in highs]
    lo = [float(x) for x in lows]
    c = [float(x) for x in closes]
    n = min(len(o), len(h), len(lo), len(c))
    o, h, lo, c = o[:n], h[:n], lo[:n], c[:n]
    w = int(window)
    series: list[float | None] = [None] * n
    if w >= 3:
        for i in range(w - 1, n):
            start = i - w + 1
            legs = _yz_legs(
                o[start : i + 1], h[start : i + 1], lo[start : i + 1], c[start : i + 1]
            )
            if legs is None:
                continue
            var = _yz_variance(legs)
            if var <= 0:
                continue
            series[i] = math.sqrt(var * periods)
    measured = sum(1 for v in series if v is not None)
    return {
        "series": series,
        "n": n,
        "measured": measured,
        "window": w,
        "basis": (
            f"Yang-Zhang over {w}-bar windows, annualized x sqrt({periods:g}); "
            f"{measured} of {n} bars measured, first at index {w - 1} "
            f"(warm-up {w - 1} bars, not 2x window); None where a window had "
            f"< 2 usable interior rows or zero variance - never 0"
        ),
    }


def ewma_vol(
    returns: list, lam: float = 0.94, periods: float = _DAYS, min_obs: int = 20
) -> float | None:
    """Annualized EWMA (RiskMetrics) volatility.

    ``sigma_t^2 = lam * sigma_{t-1}^2 + (1 - lam) * r_{t-1}^2`` seeded with
    the sample variance of the series. None with fewer than ``min_obs``
    returns.
    """
    vals = []
    for r in returns:
        try:
            f = float(r)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            vals.append(f)
    if len(vals) < min_obs:
        return None
    lam = float(lam)
    if not 0.0 < lam < 1.0:
        lam = 0.94
    n = len(vals)
    mean = sum(vals) / n
    var0 = sum((v - mean) ** 2 for v in vals) / max(1, n - 1)
    var = var0
    for r in vals:
        var = lam * var + (1.0 - lam) * (r * r)
    return math.sqrt(max(var, 0.0) * periods)


class _Garch11Result(dict):
    """dict with .omega/.alpha/.beta/.long_run_vol/.series for convenience."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(name) from exc


def garch11_fit(
    returns: list,
    periods: float = _DAYS,
    min_obs: int = 60,
) -> dict | None:
    """Fit GARCH(1,1) by maximum likelihood (pure NumPy) and return params.

    Model: ``sigma_t^2 = omega + alpha*eps_{t-1}^2 + beta*sigma_{t-1}^2``,
    long-run variance ``VL = omega / (1 - alpha - beta)``.

    Uses ``scipy.optimize.minimize`` (Nelder-Mead) on the negative Gaussian
    log-likelihood with constraints (alpha, beta >= 0, alpha + beta <= 1-eps).
    Returns ``{"omega", "alpha", "beta", "long_run_vol", "series", "n",
    "converged"}`` (annualized long-run vol, conditional-vol series on the
    last ``min_obs`` scale), or None with < ``min_obs`` returns / no
    convergence. ``long_run_vol`` is None on an IGARCH fit (alpha + beta >=
    ``_IGARCH_AB``), where no finite unconditional variance exists.
    """
    vals = []
    for r in returns:
        try:
            f = float(r)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            vals.append(f)
    if len(vals) < min_obs:
        return None
    import numpy as _np
    from scipy.optimize import minimize

    y = _np.array(vals, dtype=float)
    mean = y.mean()
    e = y - mean
    init_var = float(e.var(ddof=1))
    if init_var <= 0:
        return None

    def negll(params):
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1.0:
            return 1e15
        var = _np.empty_like(e)
        var[0] = init_var
        for t in range(1, len(e)):
            var[t] = omega + alpha * e[t - 1] ** 2 + beta * var[t - 1]
        v = _np.clip(var, 1e-12, None)
        ll = -0.5 * _np.sum(_np.log(2.0 * _np.pi * v) + e**2 / v)
        return float(-ll)

    # Warm start: unconditional variance split.
    omega0 = init_var * 0.05
    alpha0 = 0.10
    beta0 = 0.85
    try:
        res = minimize(
            negll,
            _np.array([omega0, alpha0, beta0]),
            method="Nelder-Mead",
            options={"maxiter": 2000, "xatol": 1e-8, "fatol": 1e-10},
        )
    except Exception:  # noqa: BLE001 - degenerate input degrades
        return None
    if not res.success:
        return None
    omega, alpha, beta = [float(x) for x in res.x]
    omega, alpha, beta = max(omega, 1e-12), max(0.0, alpha), max(0.0, beta)
    # A finite long-run variance VL = omega / (1 - alpha - beta) needs the
    # persistence below 1 by a real margin. A fit landing ON the boundary
    # leaves 1 - alpha - beta a floating-point residual, which turns VL into
    # an artifact: NVDA 2026-09-12 fit alpha=0.006751 beta=0.993249 (sum
    # 1 - 2.7e-13) and reported a 1,355,146% annualized "long-run vol".
    identifiable = (alpha + beta) < _IGARCH_AB
    if alpha + beta >= 1.0:
        alpha *= 0.99 / (alpha + beta)
        beta = 1.0 - alpha - 1e-8
    # Conditional-vol series.
    var = init_var
    series = []
    for t in range(len(e)):
        if t > 0:
            var = omega + alpha * e[t - 1] ** 2 + beta * var
        series.append(math.sqrt(max(var, 0.0) * periods))
    v_long = omega / (1.0 - alpha - beta) if identifiable else None
    return _Garch11Result(
        omega=round(omega, 8),
        alpha=round(alpha, 6),
        beta=round(beta, 6),
        long_run_vol=round(math.sqrt(v_long * periods), 4) if v_long else None,
        series=[round(x, 6) for x in series],
        n=len(vals),
        converged=True,
    )
