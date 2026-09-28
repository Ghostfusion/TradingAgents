"""Entry-price ceiling: the maximum economically acceptable long entry.

Institutions cap what they will pay: above the ceiling the trade's *own*
economics fail even though every setup gate still passes. This module
composes that cap from computed pieces the project already produces.

Pure and deterministic - no I/O, no LLM, no vendor calls. Advisory by design:
the result rides the trade plan card as a status string and is never a
registered gate (hard gating stays in the risk governor / strict value-dip
flags).

Locked contract (Phase 0):

* the ceiling is the ``min`` over the **available** sources. Long-only by
  construction, so there is deliberately **no** ``direction`` argument - a
  short would make the ceiling a floor and invert the composition, and this
  repo's entry path produces long entries only;
* a source that could not be measured is **absent**, never defaulted - a
  constant must never stand in for a measurement;
* with no source available the ceiling is ``None`` with status
  ``NO_SOURCE``: **never** a fallback to the current price or any other
  number, which would turn "no source" into a numeric signal;
* three states, because a ceiling that was never checked must not read as a
  pass. ``coverage`` is emitted alongside so ``1/3`` never looks like
  ``3/3``.

``momentum`` is deliberately not a source: no deterministic
momentum-score -> price-ceiling mapping exists yet, and inventing one would
put false precision into ``coverage``. Add it later as a fourth,
explicitly specified source.
"""

from __future__ import annotations

import math

#: The ceiling sources, in declared order (which is also the tie-break order:
#: the first source holding the minimum is named as ``binding_source``).
CEILING_SOURCES = ("valuation", "expected_return", "risk_reward")

#: The three locked states. ``PASS`` and ``ABOVE_CEILING`` require a usable
#: reference price; ``NO_SOURCE`` never carries a fabricated number.
CEILING_STATUSES = ("PASS", "ABOVE_CEILING", "NO_SOURCE")

_DENOMINATOR = len(CEILING_SOURCES)


def _level(v) -> float | None:
    """A usable price level, or ``None``.

    A ceiling is a positive, finite number; anything else (``None``, bool,
    NaN, inf, <= 0) is an *absent* source rather than a zero ceiling.
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


def entry_ceiling(
    *,
    price,
    valuation_ceiling=None,
    expected_return_ceiling=None,
    rr_ceiling=None,
) -> dict:
    """Compose the entry ceiling from whichever sources are available.

    Args:
        price: the reference price the ceiling is compared against.
        valuation_ceiling: the valuation construct's price ceiling. Phase 0
            passes the DCF fair value; the permanent owner is decided by the
            valuation-score question, so this argument is deliberately a
            plain number rather than a choice of construct.
        expected_return_ceiling: the price above which expected return fails.
        rr_ceiling: the price above which risk/reward fails.

    Returns:
        A dict with ``value`` / ``status`` / ``binding_source`` / ``basis`` /
        ``available_sources`` / ``missing_sources`` / ``coverage`` /
        ``coverage_ratio`` / ``ceiling_distance`` / ``ceiling_margin`` /
        ``reason``. ``value`` is ``None`` when no source is available, and
        ``ceiling_distance`` / ``ceiling_margin`` are ``None`` whenever no
        verdict could be formed.
    """
    supplied: dict[str, float | None] = {
        "valuation": _level(valuation_ceiling),
        "expected_return": _level(expected_return_ceiling),
        "risk_reward": _level(rr_ceiling),
    }
    # ``pairs`` narrows float | None -> float once, for both the min and the
    # binding-source lookup, so no ``type: ignore`` is needed.
    pairs: list[tuple[str, float]] = []
    for src in CEILING_SOURCES:
        lv = supplied[src]
        if lv is not None:
            pairs.append((src, lv))
    available = [s for s, _ in pairs]
    missing = [s for s in CEILING_SOURCES if supplied[s] is None]
    coverage = len(available)
    basis = dict(pairs)

    if not pairs:
        return {
            "value": None,
            "status": "NO_SOURCE",
            "binding_source": None,
            "basis": {},
            "available_sources": available,
            "missing_sources": missing,
            "coverage": 0,
            "coverage_ratio": 0.0,
            "ceiling_distance": None,
            "ceiling_margin": None,
            "reason": "no ceiling source available; ceiling is unset, never a fallback price",
        }

    value = min(lv for _, lv in pairs)
    binding = next(s for s, lv in pairs if lv == value)

    p = _level(price)
    distance = margin = None
    reason = ""
    status = "NO_SOURCE"
    if p is None:
        reason = "reference price unavailable; no verdict formed"
    else:
        distance = (value - p) / p
        if value != 0.0:
            margin = (value - p) / value
        status = "ABOVE_CEILING" if p > value else "PASS"

    return {
        "value": value,
        "status": status,
        "binding_source": binding,
        "basis": basis,
        "available_sources": available,
        "missing_sources": missing,
        "coverage": coverage,
        "coverage_ratio": coverage / _DENOMINATOR,
        "ceiling_distance": distance,
        "ceiling_margin": margin,
        "reason": reason,
    }


__all__ = ["CEILING_SOURCES", "CEILING_STATUSES", "entry_ceiling"]
