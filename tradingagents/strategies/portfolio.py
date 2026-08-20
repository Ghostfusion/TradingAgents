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


__all__ = [
    "value_ratio_weights",
    "capped_weights",
    "sector_cap",
    "adjust_for_caps",
    "min_names_ok",
    "summary",
    "allocation_block",
]
