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
    names = [n for n in scores if float(scores[n]) > 0]
    total = sum(float(scores[n]) for n in names)
    w = {}
    if total > 0:
        w = {n: float(scores[n]) / total for n in names}
    for n in scores:
        if n not in w:
            w[n] = min_weight
    return w


def _clip_weights(weights: dict, cap: float) -> dict:
    return {k: min(float(v), cap) for k, v in weights.items()}


def capped_weights(weights: dict, cap: float) -> dict:
    """Hard per-name cap; excess clipped (kept as cash, not redistributed)."""
    names = list(weights)
    cut = _clip_weights(weights, cap)
    kept = sum(cut.values())
    scale = 1.0 - kept
    # simplest: leave as cash
    _ = scale
    return cut


def sector_cap(weights_by_sector: dict, cap: float = 0.35) -> dict:
    """Clip per-sector weight at `cap`; excess stays unallocated (cash)."""
    return {s: min(float(w), cap) for s, w in weights_by_sector.items()}


def adjust_for_caps(weights: dict, sector_weights: dict,
                    sector_cap_limit: float = 0.35,
                    max_name: float = 0.25) -> dict:
    """Clip per-name then per-sector; both caps are hard."""
    out = capped_weights(weights, cap=max_name)
    sector_agg = {}
    for name, w in out.items():
        sector_agg[sector_weights.get(name, "?")] = \
            sector_agg.get(sector_weights.get(name, "?"), 0.0) + float(w)
    capped_sectors = sector_cap(sector_agg, sector_cap_limit)
    # scale names within an over-cap sector down to its cap (do not re-raise)
    for name, w in list(out.items()):
        sec = sector_weights.get(name, "?")
        agg = sector_agg.get(sec, 0.0)
        if agg > 0 and capped_sectors[sec] < agg:
            out[name] = float(w) * (capped_sectors[sec] / agg)
    return out


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
        "top3_weights": sorted([round(float(v), 4) for v in weights.values()],
                               reverse=True)[:3],
    }


__all__ = ["value_ratio_weights", "capped_weights", "sector_cap",
           "adjust_for_caps", "min_names_ok", "summary"]