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


def allocation_block(scores: dict, cfg: dict | None = None, sector_map: dict | None = None) -> str:
    """Capped value-proportional allocation plan as a short markdown block.

    cfg keys: max_name_weight (0.25), sector_cap_limit (0.35),
    max_book_names (10). With a sector_map, per-sector caps apply too.
    """
    cfg = cfg or {}
    max_n = float(cfg.get("max_name_weight", 0.25))
    sec_cap = float(cfg.get("sector_cap_limit", 0.35))
    min_n = int(cfg.get("max_book_names", 10))
    w = value_ratio_weights(scores, min_weight=0.0)
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
