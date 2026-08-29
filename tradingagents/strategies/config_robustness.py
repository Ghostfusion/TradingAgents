"""Config-robustness analysis — robust choice, not argmax (Lean L8).

``evaluate_config_gate.py`` grid-searches and returns the single best config by
score → that is overfit-to-one-point. Lean's optimizer reports a richer
landscape: per-parameter 1-D slices (is the best at the search-box edge?),
and a cluster of near-best solutions (is the optimum a flat plateau or an
isolated spike?). This module reproduces those *advisory* reads purely, so a
strategy choice is judged on robustness, not on one lucky cell.

Advisory only — never a causal sensitivity claim; inputs are the evaluation
rows ``[{'<param>': value, 'score': float}, ...]``.
"""

from __future__ import annotations

import math


def _edge_flag(results: list[dict], param_names: list[str],
               box: dict | None) -> dict:
    """Is the best cell sitting at the edge of the searched box per param?"""
    best = max(results, key=lambda r: r.get("score", -math.inf)) if results else None
    if best is None:
        return {}
    flags = {}
    for p in param_names:
        v = best.get(p)
        if v is None:
            flags[p] = None
            continue
        if box and p in box:
            lo, hi = box[p]
            flags[p] = bool(abs(float(v) - lo) < 1e-12 or abs(float(v) - hi) < 1e-12)
        else:
            vals = [float(r[p]) for r in results if r.get(p) is not None]
            if not vals:
                flags[p] = None
            else:
                flags[p] = bool(abs(float(v) - min(vals)) < 1e-12
                                or abs(float(v) - max(vals)) < 1e-12)
    return flags


def _cluster_plateau(results: list[dict], score_key: str = "score",
                     top_frac: float = 0.1, min_cluster: int = 3) -> dict:
    """1-D k-means-ish cluster of the top-scoring cells, split at the gap."""
    scores = sorted(
        [float(v) for r in results
         if (v := r.get(score_key)) is not None],
        reverse=True,
    )
    if len(scores) < min_cluster:
        return {"clusters": 1, "top_count": len(scores), "spread": None}
    # take the top `top_frac` of cells
    k = max(min_cluster, int(round(len(results) * top_frac)))
    top = scores[:k]
    spread = top[0] - top[-1]
    # crude single-split gap: largest normalized gap within the top slice
    gaps = [top[i] - top[i + 1] for i in range(len(top) - 1)]
    big_gap = max(gaps) if gaps else 0.0
    mean_gap = sum(gaps) / len(gaps) if gaps else 1.0
    clusters = 2 if (big_gap > 2.0 * mean_gap and mean_gap > 0) else 1
    return {"clusters": clusters, "top_count": k, "spread": round(spread, 4)}


def config_robustness(results: list[dict], param_names: list[str],
                      box: dict | None = None, score_key: str = "score") -> dict:
    """Robustness read over an evaluated config grid.

    Returns ``{'n', 'edge_flag': {param: bool|None}, 'clusters', 'top_count',
    'spread', 'best': {...}, 'note'}``. A best cell sitting on the box edge, a
    single isolated spike (``spread`` large, ``clusters``>1), or a tiny
    plateau are all reasons to treat the argmax with caution.
    """
    if not results:
        return {"n": 0, "edge_flag": {}, "clusters": 1, "top_count": 0,
                "spread": None, "best": None, "note": "no results"}
    edge = _edge_flag(results, param_names, box)
    plat = _cluster_plateau(results, score_key)
    best = max(results, key=lambda r: r.get(score_key, -math.inf))
    notes = []
    if any(v is True for v in edge.values()):
        notes.append("best at search-box edge (may be untested further)")
    if plat["clusters"] > 1 or (plat["spread"] is not None and plat["spread"] > 0.1 * max(abs(best.get(score_key, 0.0)), 1e-9)):
        notes.append("top configs form a fragile spike (advisory)")
    return {
        "n": len(results),
        "edge_flag": edge,
        "clusters": plat["clusters"],
        "top_count": plat["top_count"],
        "spread": plat["spread"],
        "best": best,
        "note": "; ".join(notes) if notes else "robust plateau (advisory)",
    }


__all__ = ["config_robustness"]
