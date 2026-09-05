"""Volatility models (quants.md / quant2.md §Volatility).

Pure, offline, deterministic estimators that complement the close-to-close
realized vol in ``regime.py``:

- Parkinson high-low range estimator (intraday range, day-only estimate),
- Garman-Klass OHLC estimator (range + open-close gap, day-only estimate),
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
    "parkinson_vol",
    "garman_klass_vol",
    "yang_zhang_vol",
    "ewma_vol",
    "garch11_fit",
]

_DAYS = 252.0


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

    def _var(vals: list[float]) -> float | None:
        m = len(vals)
        if m < 2:
            return None
        mean = sum(vals) / m
        s = sum((v - mean) ** 2 for v in vals)
        return s / (m - 1)

    o_terms: list[float] = []
    c_terms: list[float] = []
    rs_terms: list[float] = []
    m = 0  # aligned interior rows (i needs a prior close)
    for i in range(1, n):
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
    var_o = _var(o_terms)
    var_c = _var(c_terms)
    var_rs = sum(rs_terms) / m  # Rogers-Satchell is a mean, not mean-corrected
    if var_o is None or var_c is None:
        return None
    k = 0.34 / (1.34 + (m + 1.0) / (m - 1.0))
    var = var_o + k * var_c + (1.0 - k) * var_rs
    if var <= 0:
        return None
    return math.sqrt(var * periods)


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
    convergence.
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
    v_long = omega / max(1e-12, 1.0 - alpha - beta)
    return _Garch11Result(
        omega=round(omega, 8),
        alpha=round(alpha, 6),
        beta=round(beta, 6),
        long_run_vol=round(math.sqrt(v_long * periods), 4),
        series=[round(x, 6) for x in series],
        n=len(vals),
        converged=True,
    )
