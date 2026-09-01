"""Mean-reversion quality (quants.md §Statistical Arbitrage).

Pure, offline estimators that validate whether a series mean-reverts and at
what speed:

- AR(1) OLS: ``x_t = a + phi * x_{t-1}``; half-life = -ln(2)/ln(1+phi) for
  phi < 0 (the standard paired-trading half-life).
- OU process fit: ``dX = theta(mu - X)dt + sigma dW``; theta estimated via
  the AR(1) regression slope (phi = exp(-theta*dt)), half-life = ln(2)/theta.
- Hurst exponent: R/S rescaled-range analysis on log returns — H<0.5 mean
  reverting, H>0.5 persistent/trending, ~0.5 random walk. Distinguishes
  statistical arbitrage candidates from momentum series.

Both return ``float | None`` (None when the series is insufficient, has no
variance, or is non-reverting). The verdict helper classifies stable /
mean-reverting / keep-the-trend so the tool output is human-readable.
"""

from __future__ import annotations

import math

__all__ = ["ar1_half_life", "ou_half_life", "hurst_exponent", "mean_reversion_verdict"]


def _clean(series) -> list[float]:
    out = []
    for v in series:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _ar1_fit(series: list) -> dict | None:
    """Demeaned AR(1) slope phi + standard error (or None).

    Regresses ``dx_t = x_t - x_{t-1}`` on centered ``x_{t-1}`` and returns
    ``{"phi", "se", "t", "n"}``. ``se = sqrt(sse/(n-2) / den)``; the t-stat
    on phi follows the OLS regression (df = n-2).
    """
    vals = _clean(series)
    n = len(vals)
    if n < 30 or n < 3:
        return None
    mu = sum(vals) / n
    var = sum((v - mu) ** 2 for v in vals) / n
    if var <= 1e-12:
        return None
    # Centered regressors and residuals.
    xc = [vals[t - 1] - mu for t in range(1, n)]
    dx = [vals[t] - vals[t - 1] for t in range(1, n)]
    num = sum(a * b for a, b in zip(xc, dx, strict=False))
    den = sum(a * a for a in xc)
    if den <= 0:
        return None
    phi = num / den
    resid = [dx[i] - phi * xc[i] for i in range(len(dx))]
    sse = sum(r * r for r in resid)
    sigma2 = sse / max(1, len(dx) - 2)
    se = math.sqrt(sigma2 / den) if den > 0 else 1e9
    return {"phi": phi, "se": se, "t": phi / se if se > 0 else 0.0, "n": n}


def ar1_half_life(series: list, min_obs: int = 30) -> float | None:
    """Half-life of mean reversion from an AR(1) fit (phi < 0).

    Regresses the demeaned level on its own lag; ``half_life =
    -ln(2) / ln(1 + phi)``. Negative phi = mean-reverting; only a phi
    significantly below zero (|t| >= 2 on the OLS slope) is trusted, so a
    pure random walk's spurious small-negative phi is not mislabeled as
    reversion. None with insufficient rows, zero variance, or non-significant
    / non-reverting slope.
    """
    fit = _ar1_fit(series)
    if not fit or fit["n"] < min_obs:
        return None
    phi = fit["phi"]
    if phi >= 0 or phi <= -0.999 or abs(fit["t"]) < 2.0:
        return None
    hl = -math.log(2.0) / math.log(1.0 + phi)
    if not math.isfinite(hl) or hl <= 0 or hl > fit["n"] / 2:
        return None
    return round(hl, 2)


def ou_half_life(series: list, dt: float = 1.0, min_obs: int = 30) -> float | None:
    """OU-process half-life: ``theta = -ln(1+phi)/dt``, ``hl = ln(2)/theta``.

    Same demeaned AR(1) regression as :func:`ar1_half_life` mapped to the OU
    mean-reversion speed. None for non-reverting / non-significant /
    insufficient data.
    """
    fit = _ar1_fit(series)
    if not fit or fit["n"] < min_obs or dt <= 0:
        return None
    phi = fit["phi"]
    if phi >= 0 or phi <= -0.999 or abs(fit["t"]) < 2.0:
        return None
    theta = -math.log(1.0 + phi) / dt
    if theta <= 1e-9:
        return None
    hl = math.log(2.0) / theta
    if not math.isfinite(hl) or hl <= 0 or hl > fit["n"] / 2:
        return None
    return round(hl, 2)


def hurst_exponent(series: list, min_obs: int = 64, min_chunk: int = 8) -> float | None:
    """Hurst exponent via rescaled-range (R/S) analysis (quants.md §1).

    H ~ 0.5 random walk, H < 0.5 mean-reverting, H > 0.5 persistent/trending.
    R/S is applied to the (cleaned) series directly; per-chunk mean
    subtraction removes drift. For each window size tau in a logarithmic
    ladder, mean(R/S) is regressed against log(tau); H = slope.

    IMPORTANT: feed the RETURN / DIFFERENCE series, not raw price levels — a
    positively-autocorrelated LEVEL process reports H>0.5 even when its
    returns mean-revert (H<0.5 on the returns). H is clamped to [0, 1]
    (finite-sample R/S of strong trends can exceed 1). None when the series
    is too short / degenerate (no variance).
    """
    vals = _clean(series)
    if len(vals) < min_obs:
        return None
    rets = vals
    n = len(rets)
    if n < min_obs:
        return None
    var = sum((r - sum(rets) / n) ** 2 for r in rets) / n
    if not math.isfinite(var) or var <= 1e-12:
        return None

    def _sub_r_s(y: list[float]) -> float:
        mean_y = sum(y) / len(y)
        cum = []
        acc = 0.0
        for v in y:
            acc += v - mean_y
            cum.append(acc)
        r = max(cum) - min(cum)
        s = math.sqrt(sum((v - mean_y) ** 2 for v in y) / len(y))
        return r / s if s > 1e-12 else 0.0

    xs, ys = [], []
    for size in range(math.ceil(math.log2(n)), max(1, math.ceil(math.log2(min_chunk)) - 1), -1):
        tau = 1 << size
        if tau > n // 2:
            continue
        k = n // tau
        if k == 0:
            continue
        rsvals = []
        for j in range(k):
            chunk = rets[j * tau:(j + 1) * tau]
            if len(chunk) >= min_chunk:
                rs = _sub_r_s(chunk)
                if rs > 0:
                    rsvals.append(rs)
        if not rsvals:
            continue
        mean_rs = sum(rsvals) / len(rsvals)
        xs.append(math.log(tau))
        ys.append(math.log(mean_rs))
    if len(xs) < 3:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    h = num / den
    if not math.isfinite(h):
        return None
    h = max(0.0, min(1.0, h))
    return round(h, 4)


def mean_reversion_verdict(
    series: list,
    min_obs: int = 30,
    reverting_max_half_life: float = 30.0,
) -> dict:
    """Human-readable classification: stable / mean-reverting / trending.

    Returns ``{"verdict", "half_life", "phi", "n"}``. ``verdict`` is
    ``mean-reverting`` (phi significantly negative AND half-life measured and
    <= ``reverting_max_half_life`` days), ``stable`` (not enough signal -
    short / low-variance series), or ``trending`` (phi >= 0 or non-significant
    - momentum, not mean reversion).
    """
    vals = _clean(series)
    n = len(vals)
    if n < min_obs:
        return {"verdict": "stable", "half_life": None, "phi": None, "n": n}
    fit = _ar1_fit(series)
    if not fit:
        return {"verdict": "stable", "half_life": None, "phi": None, "n": n}
    phi = fit["phi"]
    if phi >= 0 or phi <= -0.999 or abs(fit["t"]) < 2.0:
        return {"verdict": "trending", "half_life": None, "phi": round(phi, 4), "n": n}
    hl = -math.log(2.0) / math.log(1.0 + phi)
    hl = (
        round(hl, 2)
        if math.isfinite(hl) and 0 < hl <= min(reverting_max_half_life, n / 2)
        else None
    )
    verdict = "mean-reverting" if hl is not None else "trending"
    return {"verdict": verdict, "half_life": hl, "phi": round(phi, 4), "n": n}
