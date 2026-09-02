"""Topk-Drop + convex enhanced-indexing portfolio strategies (Qlib pillars 3, 14).

Pure portfolio-strategy functions over a ``pred_score`` series:

- ``topk_drop_weights`` — the Qlib ``TopkDropoutStrategy`` selection as a pure
  function: hold the top-``topk`` by score, sell the worst-``n_drop`` of the
  current holdings, buy the best unheld names, equal-weight the result
  (turnover = ``2 * len(dropped) / topk``).
- ``enhanced_index_weights`` — the Qlib ``EnhancedIndexingOptimizer`` convex
  program as a pure function: ``max d.r - lam*(v'Cov v + var_u*d.d)`` s.t.
  long-only, ``sum(w) = 1``, ``||w - w0||_1 <= turnover_cap``,
  benchmark-deviation bounds, factor-deviation bounds, force-hold / force-sell
  masks, epsilon cleanup, and the **two-stage fallback** (drop the turnover
  cap, then return ``w0``) on solver failure. cvxpy not required: scipy's
  SLSQP is the default solver; a pure-python water-fill fallback keeps the
  core path dependency-free. ``None`` under degenerate input
  (no-fabrication).

Advisory only: consumed by the PM toolset and the screener allocation block —
never a gate.
"""

from __future__ import annotations

import numpy as np

try:  # optional; the pure fallback covers the no-scipy path
    import scipy.optimize as _sp_opt
    _HAS_SCIPY = True
except Exception:  # pragma: no cover - env-dependent
    _sp_opt = None  # type: ignore[assignment]
    _HAS_SCIPY = False


def topk_drop_weights(scores: dict, held: list | None = None,
                      topk: int = 10, n_drop: int = 1) -> dict | None:
    """Qlib Topk-Drop selection over ``{name: score}``.

    Sells the worst-``n_drop`` of the current holdings (if any), buys the
    highest-scored unheld names so the book holds ``topk`` total, and
    equal-weights the result. Returns ``{held, dropped, added, turnover,
    weights}`` or None under degenerate input (no names / topk < 1).
    """
    if not scores or topk < 1:
        return None
    ranked = sorted(scores.items(), key=lambda kv: -float(kv[1]))
    top_names = {name for name, _ in ranked[:topk]}
    current = {str(n).upper() for n in (held or [])}
    worst_held = sorted(current, key=lambda n: float(scores.get(n, float("-inf"))))[:n_drop]
    dropped = [n for n in worst_held if n in top_names or n in current]
    # Qlib: sell the worst n_drop of the CURRENT holdings regardless of
    # top-k membership; buy the best names NOT held to refill to topk.
    kept = top_names - set(dropped)
    unheld_top = [name for name, _ in ranked if name not in current][: topk - len(kept)]
    new_hold = sorted(kept | set(unheld_top))[:topk]
    added = [n for n in unheld_top if n in new_hold]
    weights = {n: round(1.0 / len(new_hold), 6) for n in new_hold} if new_hold else {}
    return {
        "held": new_hold,
        "dropped": sorted(dropped),
        "added": sorted(added),
        "turnover": round(2.0 * len(dropped) / len(new_hold), 4) if new_hold else None,
        "weights": weights,
    }


def _as_vector(names: list, src: dict) -> np.ndarray:
    return np.asarray([float(src.get(n, 0.0)) for n in names], dtype=float)


def _project_simplex(v: np.ndarray, total: float = 1.0) -> np.ndarray:
    """Orthogonal projection of ``v`` onto the simplex ``{w >= 0, sum = total}``.

    Standard water-filling (Holder/Luenberger); pure numpy, no solver needed.
    """
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - total
    idx = np.arange(1, len(v) + 1)
    cond = u - css / idx > 0
    rho = int(np.where(cond)[0][-1]) if cond.any() else 0
    theta = css[rho] / (rho + 1)
    return np.maximum(v - theta, 0.0)


def _fallback_enhanced(scores: np.ndarray, wb: np.ndarray, w0: np.ndarray,
                       turnover_cap: float, b_dev: float,
                       force_hold: set, force_sell: set) -> np.ndarray | None:
    """Feasible-score-tilt fallback when scipy is unavailable.

    Moves ``w0`` toward the score tilt, caps total turnover, clamps to
    long-only + benchmark-deviation bounds + masks, water-fills back onto the
    simplex (3 passes), then honesty-checks every constraint: any violation
    beyond epsilon -> return None so the caller falls back to ``w0``.
    """
    n = len(scores)
    if n == 0:
        return None
    d_raw = scores - float(np.mean(scores))
    denom = float(np.sum(np.abs(d_raw)))
    if denom <= 1e-12:
        return None
    gamma = turnover_cap / denom
    w = w0 + gamma * d_raw
    lo = np.maximum(0.0, w0) if force_hold else np.zeros(n)
    hi = np.minimum(1.0, w0) if force_sell else np.ones(n)
    for _ in range(3):
        w = np.clip(w, lo, hi)
        w = np.maximum(0.0, w)
        w = _project_simplex(w, 1.0)
        w = np.clip(w, wb - b_dev, wb + b_dev)
    w = np.clip(w, lo, hi)
    w = _project_simplex(w, 1.0)
    if float(np.sum(np.abs(w - w0))) > turnover_cap + 1e-6:
        return None
    if float(np.max(np.abs(w - wb))) > b_dev + 1e-6:
        return None
    if not np.all(np.isfinite(w)):
        return None
    return w


def enhanced_index_weights(
    scores: dict,
    benchmark_weights: dict,
    w0: dict,
    turnover_cap: float = 0.2,
    b_dev: float = 0.02,
    f_dev: float | None = None,
    force_hold: set | None = None,
    force_sell: set | None = None,
    cov: np.ndarray | None = None,
    lam: float = 0.5,
    var_u: float = 0.01,
) -> dict | None:
    """Qlib enhanced-indexing convex program as a pure function.

    Returns the target weight dict, ``w0`` when the problem is infeasible
    (two-stage fallback: drop the turnover cap, then hold), or ``None`` under
    degenerate input. Constraint set:
    ``w >= 0, sum(w) = 1, ||w - w0||_1 <= turnover_cap, |w - wb| <= b_dev``,
    optional ``|f'(w - wb)| <= f_dev`` with ``f`` = the score vector, and
    force-hold / force-sell masks (``w >= w0`` / ``w <= w0`` per name).
    """
    if not scores or not benchmark_weights or not w0:
        return None
    try:
        turnover_cap = float(turnover_cap)
        b_dev = float(b_dev)
    except (TypeError, ValueError):
        return None
    if turnover_cap < 0 or b_dev < 0:
        return None
    names = sorted(set(scores) | set(benchmark_weights) | set(w0))
    if len(names) < 1:
        return None
    r = _as_vector(names, scores)
    wb = _as_vector(names, benchmark_weights)
    w0a = _as_vector(names, w0)
    if not (np.all(np.isfinite(r)) and np.all(np.isfinite(wb)) and np.all(np.isfinite(w0a))):
        return None
    wb_sum = float(np.sum(wb))
    if wb_sum <= 0:
        return None
    wb = wb / wb_sum
    w0a = _project_simplex(w0a, 1.0)
    n = len(names)
    force_hold = {str(x).upper() for x in (force_hold or set())}
    force_sell = {str(x).upper() for x in (force_sell or set())}
    lo = np.array([float(w0a[i]) if names[i] in force_hold else 0.0 for i in range(n)])
    hi = np.array([float(w0a[i]) if names[i] in force_sell else 1.0 for i in range(n)])
    if cov is None:
        sigma = np.eye(n)
    else:
        sigma = np.asarray(cov, dtype=float)
        if sigma.shape != (n, n) or not np.all(np.isfinite(sigma)):
            sigma = np.eye(n)

    def _objective(w: np.ndarray) -> float:
        d = w - wb
        return float(lam * (d @ sigma @ d + var_u * float(np.sum(d * d))) - d @ r)

    def _feasible(w: np.ndarray, tol: float = 1e-6) -> bool:
        if not np.all(np.isfinite(w)):
            return False
        if float(np.sum(w)) < 1.0 - tol or float(np.sum(w)) > 1.0 + tol:
            return False
        if float(np.min(w)) < -tol:
            return False
        if float(np.sum(np.abs(w - w0a))) > turnover_cap + tol:
            return False
        if float(np.max(np.abs(w - wb))) > b_dev + tol:
            return False
        if f_dev is not None and abs(float(r @ (w - wb))) > float(f_dev) + tol:
            return False
        for i in range(n):
            if names[i] in force_hold and w[i] < w0a[i] - tol:
                return False
            if names[i] in force_sell and w[i] > w0a[i] + tol:
                return False
        return True

    def _solve(use_turnover: bool) -> np.ndarray | None:
        if _HAS_SCIPY and _sp_opt is not None:
            try:
                cons = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
                if use_turnover:
                    cons.append({
                        "type": "ineq",
                        "fun": lambda w: turnover_cap - float(np.sum(np.abs(w - w0a))),
                    })
                cons.append({"type": "ineq",
                             "fun": lambda w: b_dev - float(np.max(np.abs(w - wb)))})
                if f_dev is not None:
                    cons.append({"type": "ineq",
                                 "fun": lambda w: float(f_dev) - abs(float(r @ (w - wb)))})
                res = _sp_opt.minimize(
                    _objective, w0a.copy(), method="SLSQP",
                    bounds=list(zip(lo, hi, strict=True)), constraints=cons,
                    options={"maxiter": 300, "ftol": 1e-9},
                )
                if res.success and _feasible(res.x):
                    return _epsilon_cleanup(res.x)
            except Exception:  # noqa: BLE001 - solver failure -> fallback chain
                pass
        else:
            w = _fallback_enhanced(r, wb, w0a, turnover_cap if use_turnover else 1.0,
                                   b_dev, force_hold, force_sell)
            if w is not None and _feasible(w):
                return _epsilon_cleanup(w)
        return None

    result = _solve(use_turnover=True)
    if result is None:
        result = _solve(use_turnover=False)
    if result is None:
        return {n: round(float(w0a[i]), 6) for i, n in enumerate(names)}  # fallback: hold
    return {n: round(float(result[i]), 6) for i, n in enumerate(names)}


def _epsilon_cleanup(w: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    w = np.where(np.abs(w) < eps, 0.0, w)
    s = float(np.sum(w))
    return w / s if s > 1e-12 else w


__all__ = [
    "topk_drop_weights",
    "enhanced_index_weights",
]
