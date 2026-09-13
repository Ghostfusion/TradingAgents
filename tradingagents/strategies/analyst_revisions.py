"""S6 - Analyst revision / estimate-change index (MSCI recipe, coverage-guarded).

Docs: ``docs/design_quant_formulas_research_round3.md`` S6,
``docs/implementation_plan_quant_formula_additions_round3.md`` S6.

Pure, offline, deterministic-first. This module implements the two numeric legs
of the MSCI Analyst Sentiment Indexes methodology, on the inputs this engine
actually holds:

* ``revision_ratio`` - the weighted three-period upgrade/downgrade ratio from
  the ``{up, down}`` counts the vendor feed already returns. Its denominator is
  ``up + down``, explicitly a **deviation** from MSCI's analyst-coverage
  denominator (the feed has no per-analyst coverage counts) - and the deviation
  is printed on every output.
* ``estimate_change_index`` - the weighted quarterly estimate-level change on a
  four-change / five-level series. The engine has current consensus and price
  targets only, never a 3-4 quarter estimate history, so this leg returns
  ``unavailable`` **with the missing-input reason**; it never fabricates levels.
* ``winsor_z`` - the MSCI +/-3 winsorised z, reusing
  ``cross_section.cross_sectional_z`` (no second z implementation).
* ``revision_index`` - assembles the legs with their full basis. It informs,
  never gates: MSCI publishes no validation section for the recipe.

No network, no state, no LLM. A missing input degrades to ``unavailable`` with
a printed reason; nothing is ever substituted with a zero.
"""

from __future__ import annotations

import math

__all__ = [
    "DEFAULT_REVISION_WEIGHTS",
    "DEFAULT_ESTIMATE_WEIGHTS",
    "DENOMINATOR_NOTE",
    "revision_ratio",
    "estimate_change_index",
    "winsor_z",
    "revision_index",
]

DEFAULT_REVISION_WEIGHTS = (3, 2, 1)
DEFAULT_ESTIMATE_WEIGHTS = (9, 7, 5, 3)

DENOMINATOR_NOTE = (
    "denominator=up+down (DEVIATION from MSCI's analyst-coverage denominator: "
    "the engine's vendor feed carries no per-analyst coverage counts)"
)

_NO_GATE_NOTE = "informs, never gates (MSCI publishes no validation section)"


def _num(value) -> float | None:
    """Finite float or None (never raises)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _period_counts(entry) -> tuple[float, float] | None:
    """``(up, down)`` from one period dict; None when either count is missing."""
    if not isinstance(entry, dict):
        return None
    up = _num(entry.get("up"))
    down = _num(entry.get("down"))
    if up is None or down is None:
        return None
    return up, down


def _weights(weights, default) -> list[float]:
    ws = [_num(w) for w in (weights or default)]
    clean = [w for w in ws if w is not None]
    return clean or [float(w) for w in default]


def revision_ratio(
    history,
    weights=DEFAULT_REVISION_WEIGHTS,
    period: int = 21,
) -> dict:
    """Weighted, coverage-guarded upgrade/downgrade revision ratio (MSCI RR).

    ``history`` is a most-recent-first sequence of period counts
    ``{"up", "down"[, "net"]}`` - the shape ``fetch_revision_actions`` returns,
    one entry per period. ``weights`` is the MSCI recency vector (most recent
    period first); the ratio at lag ``l`` is ``(up - down) / (up + down)`` and
    the index is the weighted sum, exactly as MSCI publishes it (no
    renormalisation by the weight sum). With fewer periods than weights the
    leading weights are applied to the periods actually supplied and the
    shortfall is printed - a missing period is NEVER treated as a zero.

    Coverage guard: fewer than two actions (``up + down`` summed over the used
    window) returns ``unavailable`` with the count, because the feed carries no
    per-analyst identity and one firm's spree must not move a score.

    Returns a dict: ``index`` (None when unavailable), ``ratio`` (the
    unweighted mean ratio, shipped beside the weighted one so the weighting's
    effect is visible), ``coverage``, ``periods_used``, ``periods_supplied``,
    ``weights``, ``weights_applied``, ``denominator``, and ``unavailable`` with
    the reason on the degrading paths. ``basis`` names every one of them.
    """
    ws = _weights(weights, DEFAULT_REVISION_WEIGHTS)
    entries = list(history or [])
    used = [pc for pc in (_period_counts(e) for e in entries[: len(ws)]) if pc is not None]
    window = f"{len(ws)} x {int(period)}d"

    def _unavailable(reason: str, coverage: int) -> dict:
        return {
            "index": None,
            "ratio": None,
            "coverage": coverage,
            "periods_used": len(used),
            "periods_supplied": len(entries),
            "weights": ws,
            "weights_applied": ws[: len(used)],
            "window": window,
            "denominator": DENOMINATOR_NOTE,
            "unavailable": reason,
            "basis": f"revision ratio {window} unavailable: {reason}; {DENOMINATOR_NOTE}",
        }

    if not used:
        return _unavailable(
            "no period with both up and down counts was supplied", 0
        )

    coverage = int(sum(up + down for up, down in used))
    if coverage < 2:
        return _unavailable(
            f"coverage guard: {coverage} action(s) up+down in the {window} window "
            "(< 2) - the feed has no per-analyst identity, so a single firm's "
            "spree must not move a score",
            coverage,
        )

    applied = ws[: len(used)]
    terms: list[tuple[float, float]] = []
    for (up, down), w in zip(used, applied, strict=True):
        total = up + down
        if total <= 0:
            continue  # an empty period has no defined ratio; excluded, never zeroed
        terms.append((w, (up - down) / total))

    weighted = sum(w * r for w, r in terms)
    mean_ratio = sum(r for _, r in terms) / len(terms)
    shortfall = (
        f"; periods_used={len(used)} of {len(ws)} (the source returns one aggregate "
        "window, so only the leading weights apply - missing periods are absent, "
        "not zero)"
        if len(used) < len(ws)
        else ""
    )
    basis = (
        f"revision ratio: weighted={weighted:.4f} on weights_applied={applied} of "
        f"{list(ws)} over {len(used)}/{len(ws)} period(s) x {int(period)}d; "
        f"unweighted_mean={mean_ratio:.4f}; coverage={coverage} action(s) up+down "
        "(< 2 -> unavailable); " + DENOMINATOR_NOTE + shortfall + f"; {_NO_GATE_NOTE}"
    )
    return {
        "index": weighted,
        "ratio": mean_ratio,
        "coverage": coverage,
        "periods_used": len(used),
        "periods_supplied": len(entries),
        "weights": ws,
        "weights_applied": applied,
        "window": window,
        "denominator": DENOMINATOR_NOTE,
        "basis": basis,
    }


def estimate_change_index(levels, weights=DEFAULT_ESTIMATE_WEIGHTS) -> dict:
    """Weighted quarterly estimate-level change (MSCI EC leg).

    ``levels`` is a most-recent-first quarterly estimate series. The MSCI form
    needs ``len(weights) + 1`` levels (four quarterly changes over five level
    observations); fewer returns ``unavailable`` WITH the reason. The change at
    lag ``l`` is ``(E_l - E_{l+1}) / ((|E_l| + |E_{l+1}|) / 2)`` (the symmetric
    percentage change); all levels are used as given, never imputed. A level
    that is not a finite number, or a zero denominator at any lag, degrades the
    leg to ``unavailable`` with the reason rather than a value.
    """
    ws = _weights(weights, DEFAULT_ESTIMATE_WEIGHTS)
    needed = len(ws) + 1
    raw = list(levels or [])

    def _unavailable(reason: str) -> dict:
        return {
            "index": None,
            "changes": [],
            "weights": ws,
            "n_levels": needed,
            "n_supplied": len(raw),
            "unavailable": reason,
            "basis": f"estimate change index unavailable: {reason}",
        }

    if len(raw) < needed:
        return _unavailable(
            f"estimate levels supplied={len(raw)}, need {needed} "
            f"({len(ws)} quarterly changes over {needed} level observations); the "
            "engine has current consensus and price targets only, not a 3-4 "
            "quarter estimate history - levels are never fabricated"
        )

    nums = [_num(v) for v in raw[:needed]]
    bad = [i for i, n in enumerate(nums) if n is None]
    if bad:
        return _unavailable(
            f"level {bad[0]} (most-recent-first) is not a finite number; levels "
            "are used as given, never imputed"
        )

    changes: list[float] = []
    for lag in range(len(ws)):
        a, b = nums[lag], nums[lag + 1]
        denom = (abs(a) + abs(b)) / 2.0
        if denom == 0:
            return _unavailable(
                f"zero denominator at lag {lag} (both symmetric-change levels are 0)"
            )
        changes.append((a - b) / denom)

    weighted = sum(w * c for w, c in zip(ws, changes, strict=True))
    return {
        "index": weighted,
        "changes": changes,
        "weights": ws,
        "n_levels": needed,
        "n_supplied": len(raw),
        "basis": (
            f"estimate change index: weighted={weighted:.4f} on weights={list(ws)} "
            f"over {len(ws)} quarterly change(s) from {needed} level(s) "
            "(symmetric-percent change per lag); levels used as given"
        ),
    }


def winsor_z(values, limit: float = 3.0) -> dict | None:
    """MSCI +/-``limit`` winsorised z-score over a cross-section.

    Reuses ``cross_section.cross_sectional_z`` (the repo's single z
    implementation), then clips every z to +/-``limit`` - MSCI caps at +/-3.
    The basis names the clip and how many z-scores hit it, so a clipped tail is
    never silently smoothed. None when there are fewer than two finite
    observations or the sample has zero dispersion (a z is undefined there).
    """
    from tradingagents.strategies.cross_section import cross_sectional_z

    vals = [_num(v) for v in (values or [])]
    clean = [v for v in vals if v is not None]
    if len(clean) < 2:
        return None
    z = cross_sectional_z(clean)
    if not z:
        return None
    raw = z["z"]
    clipped = [max(-limit, min(limit, v)) for v in raw]
    n_clipped = sum(1 for v in raw if abs(v) > limit)
    return {
        "z": clipped,
        "raw_z": raw,
        "clip": float(limit),
        "n_clipped": n_clipped,
        "n": len(clean),
        "mean": z["mean"],
        "std": z["std"],
        "basis": (
            f"winsor-z: (x - mean) / std over n={len(clean)} then clip to "
            f"+/-{limit:g}; {n_clipped} value(s) clipped at the cap"
        ),
    }


def revision_index(
    history,
    levels=None,
    weights=DEFAULT_REVISION_WEIGHTS,
    estimate_weights=DEFAULT_ESTIMATE_WEIGHTS,
    period: int = 21,
) -> dict:
    """Assemble the MSCI analyst-sentiment index from its available legs.

    ``history`` feeds the revision-ratio leg; ``levels`` (optional) feeds the
    estimate-change leg. Each leg is reported raw and separately (their units
    differ - a ratio vs a symmetric percentage change), and ``index`` is the
    mean of the **available** legs, MSCI's "missing groups average the
    available ones" rule. The cross-sectional +/-3 winsor-z aggregation across
    the peer set is deferred to the consumer (``winsor_z``): one name cannot be
    z-scored. The basis prints the weights, the denominator convention, the
    coverage count, which legs are available, and the fact that the index
    informs and never gates.
    """
    rr = revision_ratio(history, weights=weights, period=period)
    if levels is None:
        ec = {
            "index": None,
            "unavailable": (
                "no estimate-level series supplied; the engine has current "
                "consensus and price targets only, never a 3-4 quarter estimate "
                "history"
            ),
        }
    else:
        ec = estimate_change_index(levels, weights=estimate_weights)

    legs = {"revision_ratio": rr.get("index"), "estimate_change": ec.get("index")}
    available = [name for name, value in legs.items() if value is not None]
    unavailable = {}
    if rr.get("index") is None:
        unavailable["revision_ratio"] = rr.get("unavailable")
    if ec.get("index") is None:
        unavailable["estimate_change"] = ec.get("unavailable")
    index = sum(legs[name] for name in available) / len(available) if available else None

    parts = [
        f"revision index (MSCI analyst-sentiment recipe): index={index} "
        f"(mean of {len(available)} available leg(s): {available or 'none'}); "
        f"weights revision_ratio={list(_weights(weights, DEFAULT_REVISION_WEIGHTS))} "
        f"estimate_change={list(_weights(estimate_weights, DEFAULT_ESTIMATE_WEIGHTS))}",
        rr.get("basis", ""),
        ec.get("basis", ""),
        f"coverage={rr.get('coverage')} action(s); " + DENOMINATOR_NOTE,
        "legs are raw (units differ; cross-sectional winsor-z +/-3 is deferred "
        "to the peer-set consumer)",
        _NO_GATE_NOTE,
    ]
    return {
        "index": index,
        "legs": legs,
        "available": available,
        "unavailable": unavailable,
        "coverage": rr.get("coverage"),
        "weights": {
            "revision_ratio": _weights(weights, DEFAULT_REVISION_WEIGHTS),
            "estimate_change": _weights(estimate_weights, DEFAULT_ESTIMATE_WEIGHTS),
        },
        "denominator": DENOMINATOR_NOTE,
        "period": int(period),
        "gates": False,
        "basis": " | ".join(p for p in parts if p),
    }
