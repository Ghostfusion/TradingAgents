"""§93: the stop distance implied by the MAE distribution of past trades.

``prediction_ledger.outcome_metrics`` already measures maximum adverse (and
favourable) excursion per closed decision, but nothing *consumed* that
distribution - every stop in the tree is modelled (``swing_low_stop``,
``chandelier_exit``, ``exits.target_level``). This turns the measured sample
into the stop distance it implies, so a stop can be **measured** rather than
chosen.

Pure and deterministic: the samples are the caller's, and so is the ledger
read. Below a sample floor the read is absent with the count - never a
default stop distance, which would be a constant standing in for a
measurement.
"""

from __future__ import annotations

import math

#: Below this many observations a quantile is not yet a measurement.
MAE_MIN_SAMPLE = 8

#: The default stop quantile: the distance that would have contained this
#: share of past adverse excursions.
DEFAULT_QUANTILE = 0.90


def _quantile(ordered: list[float], q: float) -> float:
    """Linear-interpolation quantile (numpy's default), no dependency."""
    if len(ordered) == 1:
        return ordered[0]
    q = min(max(q, 0.0), 1.0)
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[int(pos)]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _clean(values) -> list[float]:
    """The usable observations, as positive magnitudes.

    MAE is a loss by definition, so the sign is ignored. Anything non-finite
    or non-numeric is dropped rather than coerced to zero (which would drag
    the quantile toward a stop that is too tight).
    """
    out: list[float] = []
    for v in values or []:
        if v is None or isinstance(v, bool):
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(abs(f))
    return out


def mae_stop_distance(
    maes,
    *,
    quantile=DEFAULT_QUANTILE,
    min_sample=MAE_MIN_SAMPLE,
) -> dict:
    """The stop distance the MAE sample implies.

    Args:
        maes: per-trade maximum adverse excursions, as fractions of entry.
        quantile: which share of past excursions the stop should contain.
        min_sample: the floor below which the read is not a measurement.

    Returns:
        ``stop_fraction`` (the ``quantile`` of the sample), ``median``,
        ``sample``, ``quantile``, ``status`` and ``reason``. ``status`` is
        ``NO_SAMPLE`` below the floor, with ``stop_fraction`` ``None`` - never
        a default distance.
    """
    sample = _clean(maes)
    n = len(sample)
    q = float(quantile)
    ordered = sorted(sample)
    median = _quantile(ordered, 0.5) if ordered else None

    if n == 0:
        return {
            "stop_fraction": None, "median": None, "sample": 0, "quantile": q,
            "status": "NO_SAMPLE", "reason": "no MAE observations",
        }
    if n < int(min_sample):
        return {
            "stop_fraction": None, "median": median, "sample": n, "quantile": q,
            "status": "NO_SAMPLE",
            "reason": f"{n} MAE observation(s) < min_sample {int(min_sample)}",
        }
    return {
        "stop_fraction": _quantile(ordered, q), "median": median, "sample": n,
        "quantile": q, "status": "OK", "reason": "",
    }


__all__ = ["DEFAULT_QUANTILE", "MAE_MIN_SAMPLE", "mae_stop_distance"]
