"""Covariance-based portfolio construction (Lean L2/L9/L10).

Replaces value-ratio + hard-clip "diversification by guesstimate" with actual
risk-budgeting on the aligned return matrix: risk-parity (equalize per-name
risk contribution, Spinu-style Newton), minimum-variance, confidence-weighted
proportional sizing, and sector-exposure enforcement with budget
renormalization.

All pure / offline. Weight vectors always sum to ~1.0 (or None on unusable
covariance); no false-precision on tiny/singular sample histories — those
degrade to equal-weight.
"""

from __future__ import annotations

import math


def _covariance_matrix(returns_by_name: dict) -> dict | None:
    """Empirical covariance matrix over aligned return series (sample cov).

    Returns ``{'names', 'cov'}`` where ``cov[i][j]`` corresponds to
    ``names[i]``/``names[j]`` and diagonal variance is strictly positive.
    None when fewer than two aligned names or a degenerate (zero-variance)
    name.
    """
    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return None
    series = [list(returns_by_name[n]) for n in names]
    n = min(len(s) for s in series)
    if n < 2:
        return None
    mean = [sum(s[:n]) / n for s in series]
    cov = []
    for i in range(len(names)):
        row = []
        for j in range(len(names)):
            c = sum((series[i][k] - mean[i]) * (series[j][k] - mean[j])
                    for k in range(n)) / (n - 1)
            if not math.isfinite(c):
                return None
            row.append(c)
        cov.append(row)
    if any(cov[i][i] <= 0 for i in range(len(names))):
        return None
    return {"names": names, "cov": cov}


def _normalize(w: list[float]) -> list[float] | None:
    total = sum(w)
    if total <= 0 or not math.isfinite(total):
        return None
    return [x / total for x in w]


def _degrade_equal(names: list) -> tuple:
    w = 1.0 / len(names)
    return dict.fromkeys(names, w), "equal-weight (covariance unavailable)"


def _invert(mat: list[list[float]]) -> list[list[float]]:
    """Gaussian-elimination matrix inverse (small matrices only)."""
    n = len(mat)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)]
           for i, row in enumerate(mat)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col]
            aug[r] = [x - f * y for x, y in zip(aug[r], aug[col], strict=True)]
    return [row[n:] for row in aug]


def risk_parity_weights(returns_by_name: dict, lower: float = 0.0,
                        upper: float = 1.0, tol: float = 1e-9,
                        max_iter: int = 2000) -> dict:
    """Risk-parity weights: equalize each name's marginal risk contribution.

    Iterative Spinu-style update w ← cov^{-1} b / (R·diag) normalized, where
    b = 1/RC_i and RC_i is the i-th marginal risk contribution. Degrades to
    equal-weight on a singular/degenerate covariance.
    """
    m = _covariance_matrix(returns_by_name)
    if m is None:
        w, note = _degrade_equal(list(returns_by_name or {}))
        return {"weights": w, "note": note}
    names = m["names"]
    cov = m["cov"]
    n = len(names)
    w = [1.0 / n] * n
    for _ in range(max_iter):
        rc = [sum(cov[i][j] * w[j] for j in range(n)) * w[i] for i in range(n)]
        b = [1.0 / rc[i] if rc[i] > 0 else 0.0 for i in range(n)]
        try:
            inv = _invert(cov)
            nw = [sum(inv[i][j] * b[j] for j in range(n)) for i in range(n)]
        except Exception:  # noqa: BLE001 - singular; degrade
            w, note = _degrade_equal(names)
            return {"weights": w, "note": note}
        nw = _normalize(nw)
        if nw is None:
            break
        for i in range(n):
            nw[i] = max(lower, min(upper, nw[i]))
        s = sum(nw)
        if s > 0:
            nw = [x / s for x in nw]
        if all(abs(nw[i] - w[i]) < tol for i in range(n)):
            w = nw
            break
        w = nw
    return {"weights": {names[i]: w[i] for i in range(n)}, "note": "risk-parity"}


def min_variance_weights(returns_by_name: dict) -> dict:
    """Minimum-variance weights (sum=1 long-only) from the covariance matrix.

    Solves min w'Cov w s.t. sum w = 1 (analytic via cov^-1 ones). Degrades to
    equal-weight on singular covariance.
    """
    m = _covariance_matrix(returns_by_name)
    if m is None:
        w, note = _degrade_equal(list(returns_by_name or {}))
        return {"weights": w, "note": note}
    names = m["names"]
    cov = m["cov"]
    n = len(names)
    ones = [1.0] * n
    try:
        inv = _invert(cov)
        w = [sum(inv[i][j] * ones[j] for j in range(n)) for i in range(n)]
        denom = sum(w)
        if denom <= 0:
            raise ValueError("nonpositive row sum")
        w = [x / denom for x in w]
    except Exception:  # noqa: BLE001 - singular
        w, note = _degrade_equal(names)
        return {"weights": w, "note": note}
    return {"weights": {names[i]: w[i] for i in range(n)}, "note": "min-variance"}


def confidence_weights(conf: dict) -> dict:
    """Proportional weight-from-confidence (Lean L10).

    ``w_i = conf_i / sum(conf)`` — preserves relative ranking (unlike hard
    clips that dump excess to cash). Zero/total->0 guard drops names with no
    confidence. Returns zero-weights when nothing is confident.
    """
    total = sum(float(v) for v in (conf or {}).values() if v and float(v) > 0)
    if total <= 0:
        return dict.fromkeys((conf or {}), 0.0)
    return {k: (float(v) / total if v and float(v) > 0 else 0.0)
            for k, v in conf.items()}


def enforce_sector_exposure(weights_by_name: dict[str, float], sector_of: dict,
                            max_sector: float = 0.20) -> dict:
    """Scale down over-cap sectors and renormalize the freed budget (Lean L9).

    Names whose sector is unknown (``sector_of``) keep their weight (never
    dropped on a mapping gap). Returns the adjusted weight dict summing to 1
    (or weights unchanged when there is nothing to enforce).
    """
    if not weights_by_name:
        return {}
    sectors: dict[str, float] = {}
    for name, w in weights_by_name.items():
        s = sector_of.get(name)
        if s is not None:
            sectors.setdefault(s, 0.0)
            sectors[s] += float(w)
    over: set[str] = {s for s, v in sectors.items() if v > max_sector}
    if not over:
        return dict(weights_by_name)
    scale = {s: (max_sector / sectors[s]) if s in over else 1.0 for s in sectors}
    out: dict[str, float] = {}
    for name, w in weights_by_name.items():
        s = sector_of.get(name)
        out[name] = float(w) * (scale.get(s, 1.0))
    total = sum(out.values())
    if total <= 0:
        return dict(weights_by_name)
    return {k: v / total for k, v in out.items()}


def _std(vals: list) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))


def max_diversification_weights(returns_by_name: dict) -> dict:
    """Maximum-diversification portfolio (Choueifaty): ``w ~= Sigma^-1 * sigma``.

    Maximizes the diversification ratio ``DR(w) = w' * sigma / sqrt(w' Sigma w)``;
    the unconstrained optimizer is proportional to ``Sigma^-1 sigma``
    (web-verified closed form), then non-negative clipped + renomalized
    (approximate constrained MDP, labelled). Degrades to equal-weight when the
    covariance is singular/unavailable (never a fabricated precision).
    """
    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return {"weights": dict.fromkeys(names, 0.0) if names else {},
                "note": "insufficient names"}
    cov = _covariance_matrix(returns_by_name)
    if cov is None:
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "note": "equal-weight (covariance unavailable)"}
    sig = []
    for n in names:
        vals = [float(v) for v in returns_by_name[n] if v is not None]
        sig.append(max(_std(vals), 1e-12))
    try:
        inv = _invert(cov["cov"])
        raw = [sum(inv[i][j] * sig[j] for j in range(len(names))) for i in range(len(names))]
        raw = [max(0.0, x) for x in raw]  # long-only clip
        norm = _normalize(raw)
        if norm is None:
            raise ValueError("degenerate")
        return {
            "weights": {names[i]: round(float(norm[i]), 6) for i in range(len(names))},
            "note": "max-diversification (Sigma^-1 sigma, long-only approx)",
        }
    except Exception:  # noqa: BLE001 - no fabrication
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "note": "equal-weight (covariance unavailable)"}


def risk_contribution(weights_by_name: dict[str, float],
                      returns_by_name: dict) -> dict:
    """Per-name marginal risk contribution = w_i * (Cov·w)_i / total var.

    Answers "how much risk does each name actually contribute" (the input the
    LLM currently guesstimates). Returns ``{name: pct}`` or ``{}`` when the
    covariance is unavailable.
    """
    m = _covariance_matrix(returns_by_name)
    if m is None:
        return {}
    names = m["names"]
    cov = m["cov"]
    n = len(names)
    w = [float(weights_by_name.get(names[i], 0.0)) for i in range(n)]
    cw = [sum(cov[i][j] * w[j] for j in range(n)) for i in range(n)]
    rc = [w[i] * cw[i] for i in range(n)]
    total = sum(rc)
    if total <= 0:
        return {}
    return {names[i]: rc[i] / total for i in range(n)}


def black_litterman_weights(
    returns_by_name: dict,
    market_caps: dict[str, float],
    views_p: list[list[float]] | None = None,
    views_q: list[float] | None = None,
    view_uncertainty_omega: list[float] | None = None,
    risk_aversion: float = 2.5,
    tau_scale: float = 0.05,
) -> dict:
    """Black-Litterman posterior weights (quants.md §Portfolio).

    Combines the market-implied equilibrium excess returns
    (Pi = lambda * cov * w_mkt) with investor views (P Q / Omega) into the
    posterior expected returns, then maximizes Sharpe on them (closed form):

        mu_post = [ (tau*Cov)^-1 + P' Om^-1 P ]^-1
                  [ (tau*Cov)^-1 * Pi + P' Om^-1 Q ]

    ``market_caps``: name -> market cap for the market-cap weights (fell to
    ``_normalize``). ``views_p``: k x n pick matrix (row = a view's exposure
    to each name; None = no views -> pure equilibrium). ``views_q``: k-vector
    of view expected excess returns. ``view_uncertainty_omega``: k-vector of
    per-view variances (diagonal Omega). Degrades to equal-weight when
    covariance is unavailable.

    Returns ``{"weights", "posterior_excess_returns", "note"}``.
    """
    m = _covariance_matrix(returns_by_name)
    if m is None:
        w, note = _degrade_equal(list(returns_by_name or {}))
        return {"weights": w, "posterior_excess_returns": None, "note": note}
    names = m["names"]
    cov = m["cov"]
    n = len(names)
    caps = [float(market_caps.get(nm, 0.0)) for nm in names]
    if sum(caps) <= 0:
        w, note = _degrade_equal(names)
        return {"weights": w, "posterior_excess_returns": None,
                "note": "equal-weight (no market caps)"}
    w_mkt = [c / sum(caps) for c in caps]
    try:
        inv_cov = _invert(cov)
    except Exception:  # noqa: BLE001 - singular
        w, note = _degrade_equal(names)
        return {"weights": w, "posterior_excess_returns": None, "note": note}
    # implied equilibrium excess returns Pi = lambda * cov * w_mkt
    pi = [risk_aversion * sum(cov[i][j] * w_mkt[j] for j in range(n)) for i in range(n)]
    # posterior precision/mean: (tau*Cov)^-1 + P' Om^-1 P etc.
    tau_inv = [[inv_cov[i][j] / tau_scale for j in range(n)] for i in range(n)]
    if not views_p or not views_q or len(views_p) != len(views_q) or len(views_q) == 0:
        # no views -> posterior = equilibrium
        post_inv = tau_inv
        post = pi
    else:
        k = len(views_q)
        omeg = view_uncertainty_omega or [1.0] * k
        p = views_p
        # build P' Om^-1 P and P' Om^-1 Q
        pt_om_p = [[0.0] * n for _ in range(n)]
        pt_om_q = [0.0] * n
        for r in range(k):
            wv = 1.0 / (omeg[r] if omeg[r] > 0 else 1e-9)
            for a in range(n):
                pt_om_q[a] += p[r][a] * wv * views_q[r]
                for b in range(n):
                    pt_om_p[a][b] += p[r][a] * wv * p[r][b]
        post_inv = [[tau_inv[i][j] + pt_om_p[i][j] for j in range(n)] for i in range(n)]
        rhs = [sum(tau_inv[i][j] * pi[j] for j in range(n)) + pt_om_q[i] for i in range(n)]
        try:
            post = _invert(post_inv)
            post = [sum(post[i][j] * rhs[j] for j in range(n)) for i in range(n)]
        except Exception:  # noqa: BLE001 - singular posterior
            post = pi
    # max-Sharpe closed form on posterior: w = (Cov^-1 mu) / (1' Cov^-1 mu)
    obs = [sum(inv_cov[i][j] * post[j] for j in range(n)) for i in range(n)]
    denom = sum(obs)
    if denom <= 0:
        w, note = _degrade_equal(names)
        return {"weights": w, "posterior_excess_returns": [round(x, 6) for x in post],
                "note": "degraded: posterior not investable"}
    w = [x / denom for x in obs]
    return {"weights": {names[i]: round(w[i], 6) for i in range(n)},
            "posterior_excess_returns": [round(x, 6) for x in post],
            "note": "black-litterman"}


__all__ = ["risk_parity_weights", "min_variance_weights",
           "confidence_weights", "enforce_sector_exposure",
           "risk_contribution", "black_litterman_weights",
           "max_diversification_weights"]
