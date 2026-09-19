"""The shared score kernel (WP-1): align, combine, band_label - and nothing else.

Seven engines need the same three operations: map a raw value to a 0-100
*favourable* contribution, drop an absent component from the denominator, and
print the basis. Ground rule 2 (*one implementation per computation*) and master
rule 3 (*one number, one producer*) make seven copies a defect by construction, so
they live here.

**Three functions and no framework.** No registry, no plugin table, no engine
import, no ticker, no I/O, and **no weight table** - weights are each engine's own
(master rule 6), passed in by the caller. Each engine's module owns its component
list, its directions, its band edges and its weights.

**The two semantics extracted, not re-derived:**

- ``coverage_floor`` is the resolution ``factors._coverage_floor`` already
  implemented (a count, or a fraction of the set); ``factors`` now reads this one.
- ``band_label`` is the lookup shape ``factors.quality_band`` already implemented
  (first floor the score clears, walking the table top-down).

**What is deliberately NOT here:** ``decision_guardrail.SCORE_BANDS``. The
decision guardrail's bands are a decision contract; an engine's bands are advisory
labels, and master rule 2 forbids the kernel from touching the guardrail's.
"""

from __future__ import annotations

import math

#: The six non-monotonic technical inputs whose mapped value must MOVE THE RIGHT
#: WAY at the producer's own band edges rather than rise with the raw value. Named
#: here so an engine declaring one of them cannot quietly treat it as monotone.
NON_MONOTONIC_INPUTS: tuple = (
    "rsi",
    "mfi",
    "stochastic",
    "stochrsi",
    "rsi2",
    "williams_r",
    "bollinger_pct_b",
    "elder_thermometer",
)


def coverage_floor(min_coverage, n_components: int) -> int:
    """Resolve a coverage floor: an absolute count, or a fraction of the set.

    A float in ``(0, 1]`` is a fraction (``0.5`` of four components -> 2); anything
    else is read as a count and floored at 1. One implementation - the quality
    composite reads this rather than carrying its own copy.
    """
    if isinstance(min_coverage, float) and 0.0 < min_coverage <= 1.0:
        return max(1, math.ceil(min_coverage * int(n_components)))
    try:
        k = int(min_coverage)
    except (TypeError, ValueError):
        return 1
    return max(1, k)


def align(
    value,
    *,
    direction: str = "higher_better",
    band=None,
    lo: float | None = None,
    hi: float | None = None,
) -> float | None:
    """Map a raw value to a 0-100 contribution in the FAVOURABLE direction.

    Two shapes:

    - **A ramp**: ``lo`` -> 0 and ``hi`` -> 100 (clamped outside), inverted for
      ``direction="lower_better"``. Both edges are required; a one-sided ramp is
      a band table's job.
    - **A band table**: ``band`` is the producer's own ``[(edge, score), ...]``
      walked top-down, for the inputs whose relationship is **not monotone** (RSI,
      MFI, stochastic, StochRSI, RSI2, Williams %R, Bollinger %b, the Elder
      thermometer - see ``NON_MONOTONIC_INPUTS``). The edges are the producer's,
      never invented here.

    ``None`` in -> ``None`` out, and an unusable input (non-finite, or a ramp with
    no edges) is ``None`` too: **never a neutral 50**, which would enter the
    denominator as if it had been measured (master rule 1). ``direction`` must be
    ``higher_better`` or ``lower_better``; anything else raises, because a typo
    silently flipping a component is the failure this kernel exists to prevent.
    """
    if direction not in ("higher_better", "lower_better"):
        raise ValueError(
            f"direction must be 'higher_better' or 'lower_better', got {direction!r}"
        )
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if band:
        for edge, score in band:
            if v >= float(edge):
                return float(score)
        return None
    if lo is None or hi is None:
        return None
    if float(hi) == float(lo):
        return None
    frac = (v - float(lo)) / (float(hi) - float(lo))
    if direction == "lower_better":
        frac = 1.0 - frac
    return max(0.0, min(100.0, frac * 100.0))


def band_label(score, bands) -> str | None:
    """The engine's own advisory label for a 0-100 score, or None when unscored.

    ``bands`` is the engine's own ``[(floor, label), ...]`` walked top-down, so the
    first floor the score clears wins. This is the shape ``factors.quality_band``
    already used; the table itself belongs to the engine (master rule 2).
    """
    if score is None:
        return None
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    for floor, label in bands or ():
        if s >= float(floor):
            return label
    return None


def combine(
    components: dict,
    *,
    weights: dict | None = None,
    min_coverage=3,
    bands=None,
) -> dict:
    """Combine aligned components into one score, or withhold it with the reason.

    ``components`` is ``{name: aligned 0-100 | None}`` - an absent component is
    **not in the dict or is None**, never 0. ``weights`` is the engine's own
    ``{name: weight}``; a component with no declared weight is dropped with the
    reason printed, and equal weights are used only when no vector is given at all.

    Semantics:

    - The score is the **weight renormalised over the present components**:
      ``sum(w_i * v_i) / sum(w_i for present i)``. An absent component leaves the
      denominator rather than contributing a zero.
    - ``coverage`` is ``sum(w present) / sum(w total)`` - the fraction of the
      engine's own weight that was measured.
    - Below the floor (``coverage_floor(min_coverage, n_present)`` components) the
      score is **withheld** with its reason; ``score`` is ``None``, never 0 and
      never 50.
    - ``bands`` supplies the advisory label; the kernel holds no table.

    Returns ``{"score", "coverage", "floor", "components", "present",
    "withheld", "label", "basis"}``. ``floor`` is the resolved coverage floor as
    a component COUNT (``coverage_floor``), to be read beside ``coverage``, which
    is a weight FRACTION - the two are different units. ``basis`` names the weight
    vector actually used and the components that were present, so a reader can see
    what the number is made of.
    """
    comps = dict(components or {})
    if not comps:
        return {
            "score": None,
            "coverage": 0.0,
            "components": {},
            "present": [],
            # No components declared means no floor applies: there is nothing a
            # count could be required against. `0` here, not `coverage_floor`'s
            # `max(1, ...)` - that floor guards a real component set.
            "floor": 0,
            "withheld": "no components declared",
            "label": None,
            "basis": "no components declared",
        }
    if weights is None:
        w = dict.fromkeys(comps, 1.0)
        weight_basis = "equal weights (none supplied)"
    else:
        w = {name: float(weights.get(name, 0.0) or 0.0) for name in comps}
        weight_basis = "weights: " + ", ".join(f"{k}={v:g}" for k, v in sorted(w.items()))
    present = [
        name
        for name, value in comps.items()
        if value is not None and w.get(name, 0.0) > 0.0
    ]
    dropped = sorted(name for name in comps if name not in present and w.get(name, 0.0) <= 0.0)
    total_w = sum(w.values())
    present_w = sum(w[name] for name in present)
    coverage = (present_w / total_w) if total_w > 0 else 0.0
    floor = coverage_floor(min_coverage, len(present))
    basis_bits = [weight_basis]
    if dropped:
        basis_bits.append(f"dropped (no weight): {', '.join(dropped)}")
    absent = sorted(name for name in comps if comps[name] is None and name not in dropped)
    if absent:
        basis_bits.append(f"absent: {', '.join(absent)}")
    out = {
        "score": None,
        "coverage": round(coverage, 4),
        # The resolved floor, exposed so a reader can print "required" beside
        # the coverage instead of parsing it back out of `withheld`/`basis`.
        # It is a COMPONENT COUNT (`len(present) < floor`), while `coverage` is
        # a weight FRACTION - the two are different units and must be rendered
        # as such. Resolved by `coverage_floor`, the one implementation.
        "floor": floor,
        "components": {k: comps[k] for k in sorted(comps)},
        "present": sorted(present),
        "withheld": None,
        "label": None,
        "basis": "",
    }
    if len(present) < floor or present_w <= 0:
        out["withheld"] = (
            f"{len(present)} of {len(comps)} components present, floor is {floor}"
        )
        basis_bits.append(f"WITHHELD: {out['withheld']}")
        out["basis"] = " | ".join(basis_bits)
        return out
    score = sum(w[name] * float(comps[name]) for name in present) / present_w
    out["score"] = round(score, 2)
    out["label"] = band_label(out["score"], bands)
    basis_bits.append(f"score over {len(present)} present component(s), floor {floor}")
    out["basis"] = " | ".join(basis_bits)
    return out


__all__ = [
    "NON_MONOTONIC_INPUTS",
    "align",
    "band_label",
    "combine",
    "coverage_floor",
]
