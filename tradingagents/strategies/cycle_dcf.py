"""Normalized-cycle valuation for cyclical reporters (MU/SNDK/WDC/TSM ...).

Response to the review-loop finding that single-run-rate DCFs overstate value
at a memory/NAND pricing peak (and understate after a trough): this module
derives a MID-CYCLE FCF by taking the median of the recent annual free-cash
flows, then prices that with a perpetual-growth DCF. The median is deliberately
used over the mean: a pricing cycle produces fat-tailed years, and the median
is the robust center; the min/max span is rendered alongside so the analyst can
see the cycle range.

Everything is None-safe and degrades to "unavailable" when fewer than three
annual periods exist - it never manufactures a normalized number.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

MIN_YEARS = 3  # fewer annual FCFs -> no normalized figure


def normalized_cycle_fcf(fcf_series: Sequence[float | None]) -> dict:
    """Mid-cycle FCF = median of the annual FCF series (>= MIN_YEARS periods).

    Returns ``{"median": ..., "min": ..., "max": ..., "mean": ..., "n": ...}``
    with ``None`` fields when the series is too short. None entries are
    dropped before computing; the median is the anchor, min/max the span.
    """
    vals = [float(v) for v in fcf_series if v is not None]
    if len(vals) < MIN_YEARS:
        return {"median": None, "min": None, "max": None, "mean": None, "n": len(vals)}
    vals_sorted = sorted(vals)
    return {
        "median": statistics.median(vals),
        "min": vals_sorted[0],
        "max": vals_sorted[-1],
        "mean": statistics.mean(vals),
        "n": len(vals),
    }


def perpetuity_value(
    normalized_fcf: float | None,
    wacc: float | None,
    g: float = 0.025,
) -> float | None:
    """Perpetual-growth value of a normalized FCF: F * (1+g) / (wacc - g).

    None when either input is missing or wacc <= g (degenerate perpetuity).
    """
    if normalized_fcf is None or wacc is None:
        return None
    if wacc <= g:
        return None
    return float(normalized_fcf) * (1.0 + g) / (wacc - g)
