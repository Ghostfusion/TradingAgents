"""Hierarchical Risk Parity (HRP) — Lopez de Prado (design_quant_engine_additions A1).

Pure/offline portfolio construction that avoids inverting the covariance
matrix: (1) distance from the correlation matrix, (2) single-linkage
hierarchical clustering, (3) quasi-diagonalization (reorder so correlated
assets are adjacent), (4) recursive bisection splitting risk inverse to
cluster variance. Evidence: HRP is more robust out-of-sample than
unconstrained MVO and better at limiting extreme losses under noisy
covariance (2025 Columbia); returns tend to be more conservative. This is a
RISK-side construction, not an alpha source.

None-safe: any unusable input degrades to equal-weight with a note (the
``portfolio_optimizer`` convention). Weights sum to ~1.0.
"""

from __future__ import annotations

import math


def _aligned_covariance(returns_by_name: dict) -> dict | None:
    """Sample covariance over aligned return series (mirrors portfolio_optimizer).

    Returns ``{'names', 'cov'}`` (cov[i][j] for names[i]/names[j]) or None
    when fewer than two aligned names or degenerate variance.
    """
    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return None
    series = [list(returns_by_name[n]) for n in names]
    n = min(len(s) for s in series)
    if n < 2:
        return None
    mean = [sum(s[:n]) / n for s in series]
    cov: list = []
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


def _correlation_distance(cov: list, names: list) -> list | None:
    """Distance matrix ``d_ij = sqrt(0.5*(1 - rho_ij))`` (single-linkage input)."""
    n = len(names)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            s = math.sqrt(cov[i][i] * cov[j][j])
            if s <= 0:
                return None
            rho = cov[i][j] / s
            d = math.sqrt(max(0.5 * (1.0 - rho), 0.0))
            dist[i][j] = dist[j][i] = d
    return dist


def _cluster_tree(dist: list) -> list | None:
    """Single-linkage (min-distance) agglomerative clustering into pairs.

    Returns a list of (merged_a, merged_b) index-pair tuples over the
    progressive merge level; None on degenerate distances.
    """
    n = len(dist)
    if n < 1:
        return None
    if n == 1:
        return []
    active = [[i] for i in range(n)]
    merges: list = []
    while len(active) > 1:
        best = None
        best_d = float("inf")
        for a_i in range(len(active)):
            for b_i in range(a_i + 1, len(active)):
                # single-linkage distance = min pair distance between clusters
                dmin = min(dist[i][j]
                           for i in active[a_i] for j in active[b_i])
                if dmin < best_d:
                    best_d = dmin
                    best = (a_i, b_i)
        if best is None:
            return None
        ai, bi = best
        # record the merge as (list_a, list_b) of original indices
        merges.append((active[ai], active[bi]))
        merged = active[ai] + active[bi]
        active = [active[k] for k in range(len(active)) if k not in (ai, bi)]
        active.append(merged)
    return merges


def _quasi_diagonalize(merges: list, n: int) -> list | None:
    """Reorder the n asset indices so correlated assets are adjacent."""
    if n <= 1:
        return list(range(n))
    # Walk merges forward keeping active clusters; each merge splices the two
    # member clusters into one, so the root order places merged (correlated)
    # assets adjacent.
    active = [[i] for i in range(n)]
    for (left, right) in merges:
        li = next((i for i, c in enumerate(active) if c[0] in left), None)
        ri = next((i for i, c in enumerate(active) if c[0] in right), None)
        if li is None or ri is None or li == ri:
            continue
        merged = active[li] + active[ri]
        active = [active[k] for k in range(len(active)) if k not in (li, ri)]
        active.append(merged)
    tree = active[0] if active else list(range(n))
    return list(tree)


def _bisect_weights(cov: list, order: list, names: list) -> dict | None:
    """Recursive bisection: split risk inverse to cluster variance.

    Returns {name: weight} summing to ~1; None on degenerate.
    """
    def variance(cluster: list) -> float:
        if not cluster:
            return 0.0
        if len(cluster) == 1:
            return max(cov[cluster[0]][cluster[0]], 0.0)
        w = 1.0 / len(cluster)
        v = 0.0
        for i in cluster:
            for j in cluster:
                v += w * w * cov[i][j]
        return v

    def recurse(cluster: list) -> dict:
        if len(cluster) <= 1:
            return {names[cluster[0]]: 1.0}
        # split cluster into first half / second half (adjacent by order)
        mid = len(cluster) // 2
        left, right = cluster[:mid], cluster[mid:]
        v_l = variance(left)
        v_r = variance(right)
        total = v_l + v_r
        if total <= 0:
            w_l = w_r = 0.5
        else:
            w_l = v_r / total  # inverse-risk: less variance -> more weight
            w_r = v_l / total
        out = {}
        for k, w in recurse(left).items():
            out[k] = w * w_l
        for k, w in recurse(right).items():
            out[k] = w * w_r
        return out

    out = recurse(order)
    total = sum(out.values())
    if total <= 0 or not math.isfinite(total):
        return None
    return {k: round(v / total, 6) for k, v in out.items()}


def hrp_weights(returns_by_name: dict) -> dict:
    """Hierarchical Risk Parity weights for an aligned-returns book.

    Returns ``{'weights': {name: w}, 'order': [name...], 'note': str}``;
    degrades to equal-weight with a note when covariance is unusable.
    """
    cov_d = _aligned_covariance(returns_by_name)
    if cov_d is None:
        names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
        if not names:
            return {"weights": {}, "order": [], "note": "no aligned returns"}
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "order": names,
                "note": "equal-weight (covariance unavailable)"}
    names = cov_d["names"]
    cov = cov_d["cov"]
    dist = _correlation_distance(cov, names)
    if dist is None:
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "order": names,
                "note": "equal-weight (distance degenerate)"}
    merges = _cluster_tree(dist)
    if merges is None:
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "order": names,
                "note": "equal-weight (clustering failed)"}
    order = _quasi_diagonalize(merges, len(names))
    if order is None or len(order) != len(names):
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "order": names,
                "note": "equal-weight (reordering failed)"}
    weights = _bisect_weights(cov, order, names)
    if weights is None:
        w = 1.0 / len(names)
        return {"weights": dict.fromkeys(names, w),
                "order": names,
                "note": "equal-weight (bisection failed)"}
    return {"weights": weights, "order": [names[i] for i in order],
            "note": "hierarchical risk parity (single-linkage HRP)"}


__all__ = ["hrp_weights"]
