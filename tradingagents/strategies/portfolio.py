"""V3 - portfolio construction for the value watchlist.

Value-proportional weights with hard caps (per-name, per-sector). Caps are
strict by construction: any weight that would exceed its cap is clipped and
the remainder is left as cash (the returned weights sum to <= 1). Residual
cash is fine for a value book; a small crawler can push it toward the
uncapped names in production.
"""

from __future__ import annotations


def value_ratio_weights(scores: dict, min_weight: float = 0.0) -> dict:
    """Weight proportional to composite score (no cap); zero-score->min weight."""
    total = sum(float(scores[n]) for n in scores if float(scores[n]) > 0)
    w = {}
    if total > 0:
        w = {n: float(scores[n]) / total for n in scores if float(scores[n]) > 0}
    for n in scores:
        if n not in w:
            w[n] = min_weight
    return w


def _clip_weights(weights: dict, cap: float) -> dict:
    return {k: min(float(v), cap) for k, v in weights.items()}


def capped_weights(weights: dict, cap: float) -> dict:
    """Hard per-name cap; excess clipped (kept as cash, not redistributed)."""
    return _clip_weights(weights, cap)


def sector_cap(weights_by_sector: dict, cap: float = 0.35) -> dict:
    """Clip per-sector weight at `cap`; excess stays unallocated (cash)."""
    return {s: min(float(w), cap) for s, w in weights_by_sector.items()}


def adjust_for_caps(
    weights: dict, sector_weights: dict, sector_cap_limit: float = 0.35, max_name: float = 0.25
) -> dict:
    """Clip per-name then per-sector; both caps are hard."""
    out = capped_weights(weights, cap=max_name)
    sector_agg = {}
    for name, w in out.items():
        sector_agg[sector_weights.get(name, "?")] = sector_agg.get(
            sector_weights.get(name, "?"), 0.0
        ) + float(w)
    capped_sectors = sector_cap(sector_agg, sector_cap_limit)
    # scale names within an over-cap sector down to its cap (do not re-raise)
    for name, w in list(out.items()):
        sec = sector_weights.get(name, "?")
        agg = sector_agg.get(sec, 0.0)
        if agg > 0 and capped_sectors[sec] < agg:
            out[name] = float(w) * (capped_sectors[sec] / agg)
    return out


def _max_pairwise_corr(returns_by_name: dict, names: list[str]) -> float | None:
    """Max pairwise Pearson correlation across the candidate names.

    Simple, pure, no-fabrication: returns None when fewer than 2 names have a
    return series (or the series are empty) - the gate never fails on missing
    data. Used as a hard cluster ceiling (max_pairwise_corr) so a book of 10
    correlated names (semis/energy) isn't a single leveraged trade.
    """
    import numpy as np

    valid = {}
    for n in names:
        r = returns_by_name.get(n) or []
        if len(r) >= 2:
            valid[n] = [float(x) for x in r]
    if len(valid) < 2:
        return None
    keys = list(valid)
    best = None
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = np.array(valid[keys[i]]), np.array(valid[keys[j]])
            denom = float(np.std(a) * np.std(b))
            if denom == 0:
                continue
            c = float(np.cov(a, b)[0, 1]) / denom
            c = max(-1.0, min(1.0, c))
            if best is None or abs(c) > abs(best):
                best = c
    return best


def allocation_block(
    scores: dict,
    cfg: dict | None = None,
    sector_map: dict | None = None,
    returns_by_name: dict | None = None,
) -> str:
    """Capped value-proportional allocation plan as a short markdown block.

    cfg keys: max_name_weight (0.25), sector_cap_limit (0.35),
    max_book_names (10), enable_correlation_penalty (False),
    correlation_threshold (0.6), correlation_penalty_frac (0.3). With a
    sector_map, per-sector caps apply too. When ``returns_by_name`` is
    provided AND ``enable_correlation_penalty`` is on, names whose average
    pairwise correlation with the rest of the book exceeds the threshold are
    down-weighted before the caps (risk-parity style concentration control,
    industry-practice item 1). Names without a measurable return series are
    left unchanged - correlation never fabricates.
    """
    cfg = cfg or {}
    max_n = float(cfg.get("max_name_weight", 0.25))
    sec_cap = float(cfg.get("sector_cap_limit", 0.35))
    min_n = int(cfg.get("max_book_names", 10))
    # Qlib strategy selection (design_qlib_integration.md §3.3): when the
    # opt-in flags are on, the allocation plan starts from Topk-Drop or the
    # convex enhanced-index instead of the value-ratio baseline. Everything
    # downstream (correlation penalty + caps) still applies to the chosen w.
    w = value_ratio_weights(scores, min_weight=0.0)
    strat_note = ""

    if cfg.get("enable_topk_drop"):
        try:
            from tradingagents.strategies.portfolio_strategy import topk_drop_weights

            plan = topk_drop_weights(
                scores, held=[], topk=max(1, min_n), n_drop=1
            )
            w = plan["weights"] if plan and plan["weights"] else w
            strat_note = " · topk-drop weights"
        except Exception:  # noqa: BLE001 - degrade to the baseline, never raise
            w = value_ratio_weights(scores, min_weight=0.0)
    elif cfg.get("enable_enhanced_index"):
        try:
            from tradingagents.strategies.portfolio_strategy import enhanced_index_weights

            names = list(scores)
            bench = {n: 1.0 / len(names) for n in names} if names else {}
            out = enhanced_index_weights(
                scores, bench, bench,  # w0 = benchmark: a pure tilt
                turnover_cap=0.2, b_dev=0.1,
            )
            w = out if out else w
            strat_note = " · enhanced-index weights"
        except Exception:  # noqa: BLE001 - degrade to the baseline, never raise
            w = value_ratio_weights(scores, min_weight=0.0)
    if not w:
        w = value_ratio_weights(scores, min_weight=0.0)
    corr_note = ""
    if returns_by_name and cfg.get("enable_correlation_penalty"):
        w = correlation_penalty(
            w,
            returns_by_name,
            threshold=float(cfg.get("correlation_threshold", 0.6)),
            penalty=float(cfg.get("correlation_penalty_frac", 0.3)),
        )
        corr_note = " · correlation-penalized"
    # Hard pairwise-correlation cluster gate (max_pairwise_corr, advisory):
    # a book of highly-correlated names is one leveraged trade; when the
    # configured ceiling is breached the offending names are dropped from the
    # plan (never fabricated - names without a return series are kept).
    pair_corr_cap = cfg.get("max_pairwise_corr")
    if returns_by_name and pair_corr_cap:
        cap = float(pair_corr_cap)
        base_names = list(w)
        # iterative: drop the name whose removal best reduces max pairwise
        # corr, until under the cap (max 3 rounds to bound runtime).
        for _ in range(3):
            mx = _max_pairwise_corr(returns_by_name, [n for n in base_names if w.get(n, 0) > 0])
            if mx is None or mx <= cap:
                break
            # drop the member with the highest average corr to the rest
            worst = _worst_correlated(returns_by_name, [n for n in base_names if w.get(n, 0) > 0])
            if not worst:
                break
            w.pop(worst, None)
            corr_note = f" · cluster-dropped {worst}"
        else:
            corr_note = " · cluster-gate (still > cap)"
    if sector_map:
        w = adjust_for_caps(w, sector_map, sector_cap_limit=sec_cap, max_name=max_n)
    else:
        w = capped_weights(w, cap=max_n)
    info = summary(w, min_n=min_n)
    lines = ["## Allocation plan", ""]
    for name, wt in sorted(w.items(), key=lambda kv: -kv[1])[:15]:
        lines.append(f"- {name}: {wt:.1%}")
    lines.append("")
    lines.append(
        f"allocated: {info['allocated']:.1%} · names: {info['active']}/{info['names']}"
        f" · min-names-ok: {info['min_names_satisfied']}"
    )
    if strat_note:
        lines.append(f"strategy:{strat_note}")
    if corr_note:
        lines.append(corr_note)
    return "\n".join(lines)


def min_names_ok(count: int, min_n: int = 10) -> bool:
    return count >= max(1, min_n)


def summary(weights: dict, min_n: int = 10) -> dict:
    total = sum(float(v) for v in weights.values())
    active = sum(1 for v in weights.values() if float(v) > 0)
    return {
        "names": len(weights),
        "active": active,
        "allocated": round(total, 4),
        "min_names_satisfied": min_names_ok(active, min_n),
        "top3_weights": sorted([round(float(v), 4) for v in weights.values()], reverse=True)[:3],
    }


def _pearson(a: list, b: list) -> float | None:
    """Pearson correlation of two aligned numeric lists; None when degraded."""
    if not a or len(a) != len(b) or len(a) < 3:
        return None
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    sxy = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    sxx = sum((x - ma) ** 2 for x in a)
    syy = sum((y - mb) ** 2 for y in b)
    denom = (sxx * syy) ** 0.5
    if denom <= 0:
        return None
    return sxy / denom


def mean_correlation(returns_by_name: dict, name: str) -> float | None:
    """Average Pearson correlation of one name vs every other aligned name.

    None when the series cannot be aligned, the name is absent, or fewer than
    one peer exists.
    """
    if name not in returns_by_name or not returns_by_name[name]:
        return None
    peers = [k for k in returns_by_name if k != name and returns_by_name[k]]
    if not peers:
        return None
    base = returns_by_name[name]
    corrs = []
    for p in peers:
        c = _pearson(base, returns_by_name[p])
        if c is not None:
            corrs.append(c)
    if not corrs:
        return None
    return sum(corrs) / len(corrs)


def correlation_penalty(
    weights: dict,
    returns_by_name: dict,
    threshold: float = 0.6,
    penalty: float = 0.3,
    min_weight: float | None = None,
) -> dict:
    """Down-weight names whose average pairwise correlation with the rest of
    the book exceeds ``threshold`` (concentration risk, risk-parity style).

    A name with avg correlation > threshold gets its weight scaled by
    ``(1 - penalty)``; the freed weight is renormalized back across the book
    so total still sums to ~1. Returns the adjusted weights (same keys). When
    a name has no measurable correlation (missing/short series) it is left
    unchanged - correlation never fabricates. ``min_weight`` (optional) floors
    any adjusted weight.
    """
    out = dict(weights)
    penalty_frac = float(penalty)
    for name in list(out):
        corr = mean_correlation(returns_by_name, name)
        if corr is None or corr <= float(threshold):
            continue
        out[name] = max(0.0, float(out[name]) * (1.0 - penalty_frac))
    total = sum(float(v) for v in out.values())
    # renormalize so total sums to 1 (only when all weights are non-negative;
    # leverage/negative weights are left untouched to avoid distortion).
    if total > 0 and all(v >= 0 for v in out.values()):
        out = {k: float(v) / total for k, v in out.items()}
    if min_weight is not None:
        out = {k: max(float(min_weight), float(v)) for k, v in out.items()}
    return out


__all__ = [
    "value_ratio_weights",
    "capped_weights",
    "sector_cap",
    "adjust_for_caps",
    "min_names_ok",
    "summary",
    "allocation_block",
    "mean_correlation",
    "correlation_penalty",
]


def _worst_correlated(returns_by_name: dict, names: list[str]) -> str | None:
    """Name with the highest average |corr| to the rest (cluster-gate drop)."""
    import numpy as np

    valid = {}
    for n in names:
        r = returns_by_name.get(n) or []
        if len(r) >= 2:
            valid[n] = [float(x) for x in r]
    if len(valid) < 2:
        return None
    keys = list(valid)
    avg = {}
    for i, n in enumerate(keys):
        a = np.array(valid[n])
        cs = []
        for j in range(len(keys)):
            if i == j:
                continue
            b = np.array(valid[keys[j]])
            denom = float(np.std(a) * np.std(b))
            if denom == 0:
                continue
            cs.append(abs(float(np.cov(a, b)[0, 1]) / denom))
        avg[n] = sum(cs) / len(cs) if cs else 0.0
    return max(avg, key=avg.get) if avg else None

