"""Covariance modeling (six-pillar / master-catalog PART XVII).

Pure, offline estimators that stabilize the sample covariance the
covariance-based allocators consume (risk-parity / min-variance /
Black-Litterman / max-diversification / risk contribution):

- ``ledoit_wolf_shrink`` - Ledoit-Wolf (2004) linear shrinkage toward a
  target (scaled identity ``mu*I`` or the diagonal of the sample), with the
  shrinkage intensity ``delta = clip(b^2 / d^2, 0, 1)`` where ``b^2`` is the
  average squared Frobenius error of the sample covariance rows and ``d^2``
  the target mismatch (web-verified against the standard implementation).
  Most valuable when ``n_names ~ n_obs`` (sample covariance overfits).
- ``ewma_covariance`` - RiskMetrics EWMA covariance
  ``Sigma_t = lam*Sigma_{t-1} + (1-lam)*r_{t-1} r_{t-1}'`` seeded on the
  sample covariance of the first window.

Every function returns a plain ``dict`` with explicit None fields on
insufficient/degenerate input - never fabricated. NumPy only (already a repo
dependency); all covariance output is ``list[list[float]]`` for the pure
callers.
"""

from __future__ import annotations

import math

__all__ = [
    "ledoit_wolf_shrink",
    "ewma_covariance",
]

_MIN_OBS = 30


def _aligned_matrix(returns_by_name: dict, min_obs: int = _MIN_OBS):
    """Aligned (T x N) centered return matrix over the last common window.

    Mirrors ``portfolio_optimizer._covariance_matrix`` alignment (per-name
    series aligned by index, last ``n`` rows). Returns ``(X_centered, names)``
    or ``(None, [])`` when fewer than two names or a name has too little
    history - never fabricates.
    """
    import numpy as _np

    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return None, []
    series = []
    for n in names:
        vals = [float(v) for v in returns_by_name[n] if v is not None]
        if len(vals) < min_obs:
            return None, []
        series.append(vals)
    n = min(len(s) for s in series)
    if n < 2:
        return None, []
    mat = _np.array([s[-n:] for s in series], dtype=float)  # N x T
    mat = mat.T  # T x N
    mat = mat - mat.mean(axis=0, keepdims=True)
    return mat, names


def ledoit_wolf_shrink(
    returns_by_name: dict,
    target: str = "scaled_identity",
    min_obs: int = _MIN_OBS,
) -> dict:
    """Ledoit-Wolf (2004) shrunk covariance matrix.

    ``Sigma = (1-delta)*S + delta*F`` with ``S`` the sample covariance
    (MLE convention) and ``F`` the target (``mu*I`` or ``diag(S)``). Returns
    ``{"names", "cov", "shrinkage", "target", "n_obs", "n_names"}``; the
    ``cov`` is a ``list[list[float]]`` keyed by ``names``. ``shrinkage`` in
    [0, 1]; a target that already equals the sample (shrinkage 0) is
    reported, never forced. None-degraded fields are ``None``.
    """
    import numpy as _np

    X, names = _aligned_matrix(returns_by_name, min_obs)
    if X is None:
        return {"names": [], "cov": None, "shrinkage": None, "target": target,
                "n_obs": 0, "n_names": 0}
    t, p = X.shape
    S = (X.T @ X) / t
    if target == "diag":
        F = _np.diag(_np.diag(S))
    else:  # scaled_identity
        mu = float(_np.trace(S)) / p
        F = mu * _np.eye(p)
    outer = _np.einsum("ni,nj->nij", X, X)
    b2 = float(_np.mean(_np.sum((outer - S) ** 2, axis=(1, 2))))
    d2 = float(_np.sum((S - F) ** 2))
    shrinkage = 0.0 if d2 <= 0 else min(max(b2 / d2, 0.0), 1.0)
    Sigma = (1.0 - shrinkage) * S + shrinkage * F
    cov = [[float(x) for x in row] for row in Sigma]
    return {
        "names": names,
        "cov": cov,
        "shrinkage": round(shrinkage, 6),
        "target": target,
        "n_obs": t,
        "n_names": p,
    }


def ewma_covariance(
    returns_by_name: dict,
    lam: float = 0.94,
    min_obs: int = _MIN_OBS,
    seed_window: int = 30,
) -> dict:
    """RiskMetrics EWMA covariance.

    ``Sigma_t = lam*Sigma_{t-1} + (1-lam)*r_{t-1} r_{t-1}'`` seeded with the
    sample covariance of the first ``seed_window`` aligned rows, then
    recursed over every later row. Returns ``{"names", "cov", "lam",
    "n_obs"}``; ``cov`` is a ``list[list[float]]`` (sample-degenerate input
    yields ``None`` cov with the counts still reported).
    """
    import numpy as _np

    X, names = _aligned_matrix(returns_by_name, min_obs)
    if X is None:
        return {"names": [], "cov": None, "lam": float(lam), "n_obs": 0}
    t, p = X.shape
    use_lam = float(lam)
    if not 0.0 < use_lam < 1.0:
        use_lam = 0.94
    seed = min(seed_window, t)
    seed_rows = X[:seed]
    Sigma = (seed_rows.T @ seed_rows) / max(1, seed - 1)
    if not math.isfinite(float(_np.trace(Sigma))):
        return {"names": names, "cov": None, "lam": use_lam, "n_obs": t}
    for i in range(seed, t):
        r = X[i]
        Sigma = use_lam * Sigma + (1.0 - use_lam) * _np.outer(r, r)
    cov = [[float(x) for x in row] for row in Sigma]
    return {"names": names, "cov": cov, "lam": use_lam, "n_obs": t}
