"""Entry target price: §100's ``P_entry,target`` from the price anchors we have.

``Strategies/entry_exit.md`` §100 blends four price anchors - fundamental,
valuation, technical and momentum - into a weighted average. This repo's
engines emit **0-100 scores**, not prices, and no calibrated score -> price
bridge exists, so blending score values as though they were prices would be
false precision (the same objection the owner raised for momentum, and it
applies to all four anchors).

This module therefore blends only **price anchors the repo actually
produces**, and reports the regime / risk adjustment terms as *absent* rather
than inventing a map for them. Pure and deterministic. Advisory: this is the
*desired* entry, distinct from ``entry_ceiling`` (the hard maximum) - the card
shows both, and neither gates a decision.
"""

from __future__ import annotations

import math

from tradingagents.strategies.entry_ceiling import usable_price_level

#: The price anchors, in declared order (which is also the tie-break order).
ANCHOR_SOURCES = ("valuation", "technical", "tranche")

#: The §100 adjustment terms. Left NO_SOURCE in Phase 2: both are 0-100
#: scores in this repo, and turning one into a price multiplier needs a
#: calibration that does not exist yet.
ADJUSTMENT_TERMS = ("regime", "risk")


def _multiplier(v) -> float | None:
    """A usable multiplicative adjustment, or ``None``.

    ``None`` means *absent* - not a silent ``1.0``, which would make an
    unmeasured adjustment indistinguishable from a measured no-op.
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f <= 0.0:
        return None
    return f


def entry_target(
    *,
    valuation_price=None,
    technical_price=None,
    tranche_price=None,
    weights: dict | None = None,
    regime_multiplier=None,
    risk_multiplier=None,
) -> dict:
    """§100's ``P_entry,target`` over the price anchors that exist.

    ``value`` is the weight-normalised blend of the *available* anchors,
    scaled by whichever adjustment terms were supplied. A weight given for an
    absent anchor is dropped rather than applied to a placeholder. With no
    anchor available, ``value`` is ``None`` and ``status`` is ``NO_SOURCE`` -
    never a fallback to the current price.
    """
    supplied: dict[str, float | None] = {
        "valuation": usable_price_level(valuation_price),
        "technical": usable_price_level(technical_price),
        "tranche": usable_price_level(tranche_price),
    }
    pairs: list[tuple[str, float]] = []
    for src in ANCHOR_SOURCES:
        lv = supplied[src]
        if lv is not None:
            pairs.append((src, lv))
    available = [s for s, _ in pairs]
    missing = [s for s in ANCHOR_SOURCES if supplied[s] is None]

    adjustments = {
        "regime": _multiplier(regime_multiplier),
        "risk": _multiplier(risk_multiplier),
    }
    adjustments_missing = [k for k in ADJUSTMENT_TERMS if adjustments[k] is None]

    if not pairs:
        return {
            "value": None,
            "raw": None,
            "status": "NO_SOURCE",
            "basis": {},
            "weights": {},
            "available_sources": [],
            "missing_sources": missing,
            "coverage": 0,
            "coverage_ratio": 0.0,
            "adjustments": adjustments,
            "adjustments_missing": adjustments_missing,
            "reason": "no price anchor available; target is unset, never a fallback price",
        }

    weights_used = {s: 1.0 for s, _ in pairs}
    if weights:
        for s, _ in pairs:
            wv = _multiplier(weights.get(s))
            if wv is not None:
                weights_used[s] = wv
    total_w = sum(weights_used[s] for s, _ in pairs)
    raw = sum(weights_used[s] * lv for s, lv in pairs) / total_w
    value = raw
    for term in ADJUSTMENT_TERMS:
        mult = adjustments[term]
        if mult is not None:
            value *= mult

    return {
        "value": value,
        "raw": raw,
        "status": "OK",
        "basis": dict(pairs),
        "weights": weights_used,
        "available_sources": available,
        "missing_sources": missing,
        "coverage": len(pairs),
        "coverage_ratio": len(pairs) / len(ANCHOR_SOURCES),
        "adjustments": adjustments,
        "adjustments_missing": adjustments_missing,
        "reason": "",
    }


__all__ = ["ANCHOR_SOURCES", "ADJUSTMENT_TERMS", "entry_target"]
