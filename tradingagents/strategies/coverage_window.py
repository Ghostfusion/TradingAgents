"""Coverage window and survivor labelling (H10, paper-survey honest-evaluation).

No module records *when* a symbol's series begins, so a calendar-aligned panel
that pads a short listing history with missing positions silently feeds
truncated-window fallbacks and cross-sectional z-scores that mix 40-bar and
2,000-bar histories, with nothing in the output naming the differing coverage.

``coverage_window`` **reads** the window off the already-loaded frame. It is a
reader, never a second data-quality authority: it adds the *window*, not the
threshold, so ``market_data_validator._INDICATOR_MIN_BARS`` and
``volatility_models._IGARCH_AB`` stay exactly as they are.

``coverage_window(series, *, alignment=None) ->``

* ``first_valid`` / ``last_valid`` - the index labels of the first and last
  valid (non-missing) observation, i.e. when the series effectively begins and
  ends.
* ``n_bars`` - the number of valid observations (not the panel length: padded
  or interior positions are not bars).
* ``padded_days`` - the number of leading positions before the first valid
  observation in a calendar-aligned panel; the extension the paper measures.
* ``alignment`` - how the frame was aligned (``calendar-aligned``,
  ``index-aligned`` or ``positional``), stated rather than assumed.
* ``unavailable`` - a reason string when there is no window to report (empty or
  all-missing series); otherwise ``None``. Missing input is never read as a
  zero.

Missing data is never a measurement: an empty or all-missing series degrades to
``unavailable`` with the window fields ``None``, never to ``padded_days == 0``
presented as a coverage fact. ``SURVIVOR_ONLY`` names the label a backtest over
a current-constituent universe carries in the findings record.

Pure, deterministic, O(n). No network, no state.
"""

from __future__ import annotations

import math

import numpy as np

#: The findings-record label for any backtest over a *current-constituent*
#: universe: the universe is what survived to today, not what was investable
#: then. Defined here so the label has one definition site.
SURVIVOR_ONLY = "survivor_only"


def _is_missing(value) -> bool:
    """True for ``None`` and any float/numpy NaN; never raises on odd types."""
    if value is None:
        return True
    try:
        return bool(math.isnan(float(value)))
    except (TypeError, ValueError):
        return False


def _series_parts(series) -> tuple[list, list]:
    """``(values, labels)`` from a pandas Series, ndarray, list or ``None``."""
    if series is None:
        return [], []
    index = getattr(series, "index", None)
    if index is not None and hasattr(series, "tolist"):
        return list(series.tolist()), list(index.tolist())
    if isinstance(series, np.ndarray):
        values = series.tolist()
        return values, list(range(len(values)))
    try:
        values = list(series)
    except TypeError:
        values = [series]
    return values, list(range(len(values)))


def _infer_alignment(series) -> str:
    """How the frame is aligned, from its index - stated, never assumed."""
    index = getattr(series, "index", None)
    if index is None or callable(index):
        return "positional"
    try:
        import pandas as pd
    except Exception:  # noqa: BLE001 - pandas absent -> the index is still real
        return "index-aligned"
    if isinstance(index, pd.DatetimeIndex):
        return "calendar-aligned"
    return "index-aligned"


def coverage_window(series, *, alignment: str | None = None) -> dict:
    """The coverage window of one already-loaded series (H10).

    ``series`` is a pandas Series (its index labels the window), an ndarray or a
    plain list of floats/NaN. ``alignment`` is reported verbatim when supplied;
    otherwise it is inferred from the index.

    Returns the window dict described in the module docstring: ``first_valid``,
    ``last_valid``, ``n_bars``, ``padded_days``, ``alignment`` and
    ``unavailable``. An empty or all-missing series has no window: every field
    is ``None``/``0`` and ``unavailable`` carries the reason.
    """
    values, labels = _series_parts(series)
    align = alignment or _infer_alignment(series)
    n_total = len(values)

    if n_total == 0:
        return {
            "first_valid": None,
            "last_valid": None,
            "n_bars": 0,
            "padded_days": 0,
            "alignment": align,
            "unavailable": "empty series: no position to align",
        }

    valid = [i for i, value in enumerate(values) if not _is_missing(value)]
    if not valid:
        return {
            "first_valid": None,
            "last_valid": None,
            "n_bars": 0,
            "padded_days": 0,
            "alignment": align,
            "unavailable": (
                f"all {n_total} position(s) missing: no valid observation, so "
                "there is no window to report"
            ),
        }

    first_i, last_i = valid[0], valid[-1]
    return {
        "first_valid": labels[first_i],
        "last_valid": labels[last_i],
        "n_bars": len(valid),
        "padded_days": first_i,
        "alignment": align,
        "unavailable": None,
    }


__all__ = ["SURVIVOR_ONLY", "coverage_window"]
