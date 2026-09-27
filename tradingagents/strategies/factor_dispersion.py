"""Cross-metric factor dispersion (FUND-15) and fundamental momentum (FUND-16).

Two pure-arithmetic producers over plain Python structures - no vendor call, no
config key, no gate, and no weight table the owner owns:

- ``factor_score_dispersion`` (FUND-15, library §36 *Cross-metric agreement*):
  given one name's vector of standardised factor scores, how much do the metrics
  agree (``Agreement = 1 - Std(FactorScores) / MaximumPossibleStd``) and how wide
  is the spread (the population ``Std``). The library names ``MaximumPossibleStd``
  and never defines it, so this module **declares** it (see the constant).
- ``fundamental_momentum`` (FUND-16, library §26 *Fundamental momentum*, §27
  *Fundamental acceleration*, §28 *Fundamental stability*):
  the weighted ``Σ w_i ΔFactor_i`` composite over a per-name factor history,
  the weighted second difference (acceleration) and the dispersion of the
  per-factor changes (stability). The library leaves the lag ``n`` and the
  weights ``w_i`` open (§33: *"I would not hard-code these weights
  permanently"*), so this module **declares** them (see the constants).

Sources the functions read, named where the docstrings ask for it: the panel's
per-name factor rows (the ``factor_schema`` factors, as scored by
``factors.category_scores``) for FUND-15, and the stacked annual series
``dataflows.sec_edgar.financial_history_series`` returns under ``"series"`` -
``{label: {fiscal_end: value}}``, flattened per label to oldest-first - for
FUND-16. Both take dictionaries and lists of numbers; neither fetches anything.

``NA`` is not ``0``: a missing or non-finite entry is skipped, never substituted,
and a vector too short to measure returns ``None`` values with a ``reason`` -
never a fabricated ``0``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

__all__ = [
    "FACTOR_SCORE_MIN",
    "FACTOR_SCORE_MAX",
    "FACTOR_SCORE_NEUTRAL",
    "MAXIMUM_POSSIBLE_STD",
    "MOMENTUM_LAG",
    "MOMENTUM_DEFAULT_WEIGHT",
    "MOMENTUM_FACTOR_WEIGHTS",
    "factor_score_dispersion",
    "fundamental_momentum",
]

# --- FUND-15: the cross-metric agreement scale -----------------------------

# The engine's factor scores are 0-100 (the direction-signed percentile
# ``factors.category_scores`` publishes), so the bounded scale is declared here
# rather than assumed: the library §36 examples are 0-100 scores too.
FACTOR_SCORE_MIN = 0.0
FACTOR_SCORE_MAX = 100.0
FACTOR_SCORE_NEUTRAL = (FACTOR_SCORE_MIN + FACTOR_SCORE_MAX) / 2.0  # 50.0

# DECLARED DEFINITION, NOT A FITTED CONSTANT.
#
# The library's §36 formula is ``Agreement = 1 - Std(FactorScores) /
# MaximumPossibleStd`` and it names ``MaximumPossibleStd`` without giving it a
# value (this is the unbound definition the MASTER_PLAN §5 FUND-15 row records).
# This module declares it as the **population** sigma of a variable bounded to
# the engine's 0-100 factor-score scale. Over any distribution on ``[min, max]``
# the population standard deviation is bounded by ``(max - min) / 2`` - attained
# by the two-point extreme (half the mass at each end) - so on ``[0, 100]`` the
# maximum possible population sigma is ``50``. It is a scale fact, not a fitted
# quantity, and a caller using a different scale passes its own ``scale_min`` /
# ``scale_max`` to ``factor_score_dispersion``.
MAXIMUM_POSSIBLE_STD = (FACTOR_SCORE_MAX - FACTOR_SCORE_MIN) / 2.0  # 50.0


def _population_std(values: Sequence[float]) -> float | None:
    """The population sigma of ``values``, or ``None`` below two points."""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / n)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _finite_entries(values: Mapping) -> tuple[list[float], int]:
    """``(finite floats in iteration order, count skipped)`` - ``NA`` dropped."""
    kept: list[float] = []
    skipped = 0
    for v in values:
        if v is None:
            skipped += 1
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not math.isfinite(f):
            skipped += 1
            continue
        kept.append(f)
    return kept, skipped


def factor_score_dispersion(
    factor_scores: Mapping[str, float],
    *,
    scale_min: float = FACTOR_SCORE_MIN,
    scale_max: float = FACTOR_SCORE_MAX,
) -> dict:
    """Cross-metric agreement and factor-score dispersion (FUND-15, library §36).

    Reads one name's factor vector: a mapping of factor name -> standardised
    0-100 factor score, the shape the panel's factor rows carry (the
    ``factor_schema`` factors as scored by ``factors.category_scores``). No
    fetch is made.

    Returns a dict with:

    - ``dispersion`` - the population sigma of the scores.
    - ``agreement`` - the library's ``1 - dispersion / maximum_possible_std``,
      clamped to the documented ``[0, 1]`` range (an out-of-scale input is a
      caller error, not a negative agreement).
    - ``sign_agreement`` - the share of the scores on the majority side of
      ``FACTOR_SCORE_NEUTRAL`` ("how many metrics point the same way"); ``1.0``
      when every score points the same way, ``0.5`` for a perfect split at
      ``n = 4``.
    - ``mean``, ``n``, ``skipped``, ``maximum_possible_std``.
    - ``reason`` - ``None`` when measured, else why it could not be (never a
      fabricated ``0``).

    Fewer than two finite scores leaves ``dispersion``, ``agreement``,
    ``sign_agreement`` and ``mean`` at ``None`` with a ``reason``.

    Args:
        factor_scores: Factor name -> standardised factor score. ``None`` or a
            non-finite value is skipped, not treated as ``0``.
        scale_min: Lower bound of the score scale (default ``FACTOR_SCORE_MIN``).
        scale_max: Upper bound of the score scale (default ``FACTOR_SCORE_MAX``).

    Raises:
        ValueError: if ``scale_max <= scale_min`` (no positive width to bound).
    """
    width = float(scale_max) - float(scale_min)
    if width <= 0:
        raise ValueError(
            f"scale_max ({scale_max!r}) must exceed scale_min ({scale_min!r})"
        )
    maximum_possible_std = width / 2.0

    scores, skipped = _finite_entries(factor_scores.values())
    n = len(scores)

    out: dict = {
        "dispersion": None,
        "agreement": None,
        "sign_agreement": None,
        "mean": None,
        "n": n,
        "skipped": skipped,
        "maximum_possible_std": maximum_possible_std,
        "reason": None,
    }
    if n < 2:
        out["reason"] = (
            f"need at least 2 finite factor scores to measure dispersion, "
            f"got {n}"
        )
        return out

    neutral = (float(scale_min) + float(scale_max)) / 2.0
    dispersion = _population_std(scores)
    mean = sum(scores) / n
    positive = sum(1 for v in scores if v > neutral)
    negative = sum(1 for v in scores if v < neutral)

    out["dispersion"] = dispersion
    out["agreement"] = _clamp01(1.0 - dispersion / maximum_possible_std)
    out["sign_agreement"] = max(positive, negative) / n
    out["mean"] = mean
    return out


# --- FUND-16: fundamental momentum, acceleration, stability ----------------

# The library leaves the momentum window ``n`` open: §26 names no lag, and
# §1.3/§4.2 record that "nothing in the library says 3 years or 5 years". This
# module DECLARES one annual period - the smallest lag the stacked per-name
# statement history (``sec_edgar.financial_history_series``) can support - and
# refuses any history shorter than ``n + 1``. A caller with a different window
# passes ``lag=``.
MOMENTUM_LAG = 1

# The library leaves the weights ``w_i`` open too (§26 shows ``Σ w_i ΔFactor_i``
# with no vector; §33 says "I would not hard-code these weights permanently").
# This module DECLARES equal weights: the repo's no-invented-weights rule, and
# the library's own evidence ledger (§0.4, DeMiguel, Garlappi & Uppal 2009 -
# ``1/N`` is a hard baseline to beat). One entry per factor §26 names; any other
# factor name takes ``MOMENTUM_DEFAULT_WEIGHT``. Only the ratios matter, because
# the composite renormalises by ``Σ w_i`` over the factors present.
MOMENTUM_DEFAULT_WEIGHT = 1.0
MOMENTUM_FACTOR_WEIGHTS: dict[str, float] = {
    "roic": 1.0,
    "roe": 1.0,
    "gross_margin": 1.0,
    "operating_margin": 1.0,
    "fcf_margin": 1.0,
    "asset_turnover": 1.0,
    "revenue_growth": 1.0,
    "eps_growth": 1.0,
}


def _finite_series(seq: Sequence[float]) -> list[float]:
    """The finite tail-preserving floats of ``seq`` (non-finite entries dropped)."""
    kept: list[float] = []
    for v in seq or []:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            kept.append(f)
    return kept


def fundamental_momentum(
    factor_history: Mapping[str, Sequence[float]],
    *,
    lag: int = MOMENTUM_LAG,
    weights: Mapping[str, float] | None = None,
) -> dict:
    """Weighted Delta-factor composite, acceleration and stability (FUND-16).

    Reads a per-name factor history: a mapping of factor name -> its values over
    consecutive periods, **oldest first**. The source named by the library is the
    stacked annual statement series the repo already fetches -
    ``dataflows.sec_edgar.financial_history_series`` returns
    ``{"series": {label: {fiscal_end: value}}, ...}``, so a caller flattens one
    label to its oldest-first value list (the panel's factor rows are the same
    shape once stacked). No fetch is made.

    Library §26 is the composite ``Σ w_i ΔFactor_i``, §27 the acceleration
    ``(X_t - X_{t-1}) - (X_{t-1} - X_{t-2})``, §28 the stability (here the
    dispersion of the per-factor changes). ``Δ`` is taken over the declared
    ``lag``: ``X_t - X_{t-n}``.

    Returns a dict with:

    - ``momentum`` - the renormalised weighted mean of the per-factor changes
      (factor units per period), or ``None`` with ``reason``.
    - ``acceleration`` - the renormalised weighted mean of the per-factor second
      differences, or ``None`` with ``acceleration_reason`` (needs ``2n + 1``
      periods).
    - ``stability`` - the population sigma of the per-factor changes
      ("dispersion of the changes"), or ``None`` with ``stability_reason``
      (needs at least two measurable factors).
    - ``lag``, ``n_factors`` (usable factors in the momentum leg),
      ``n_periods`` (the longest usable history).
    - ``reason`` - ``None`` when momentum is measured; else why it refused.
      A too-short history yields ``None`` fields, never a fabricated ``0``.

    A factor whose history is shorter than ``lag + 1`` (or whose values are all
    missing) is skipped, not zero-filled, and the remaining weights renormalise.

    Args:
        factor_history: Factor name -> oldest-first value list.
        lag: Periods per change, ``n`` (default ``MOMENTUM_LAG``).
        weights: Factor name -> weight; defaults to ``MOMENTUM_FACTOR_WEIGHTS``,
            with any unlisted factor at ``MOMENTUM_DEFAULT_WEIGHT``.

    Raises:
        ValueError: if ``lag < 1``.
    """
    if lag < 1:
        raise ValueError(f"lag must be >= 1, got {lag!r}")
    w_map = MOMENTUM_FACTOR_WEIGHTS if weights is None else weights
    required = lag + 1
    accel_required = 2 * lag + 1

    changes: dict[str, float] = {}
    weighted: list[tuple[float, float]] = []  # (weight, delta) for the momentum leg
    accel_weighted: list[tuple[float, float]] = []
    n_periods = 0
    for name, raw in (factor_history or {}).items():
        series = _finite_series(raw)
        n_periods = max(n_periods, len(series))
        if len(series) < required:
            continue
        w = w_map.get(name, MOMENTUM_DEFAULT_WEIGHT)
        if w is None or not math.isfinite(float(w)) or float(w) == 0.0:
            continue
        w = float(w)
        delta = series[-1] - series[-1 - lag]
        changes[name] = delta
        weighted.append((w, delta))
        if len(series) >= accel_required:
            prior_delta = series[-1 - lag] - series[-1 - 2 * lag]
            accel_weighted.append((w, delta - prior_delta))

    out: dict = {
        "momentum": None,
        "acceleration": None,
        "stability": None,
        "lag": lag,
        "n_factors": len(weighted),
        "n_periods": n_periods,
        "reason": None,
        "acceleration_reason": None,
        "stability_reason": None,
    }

    if not weighted:
        out["reason"] = (
            f"no factor has at least {required} finite periods "
            f"(lag + 1 = {required}); longest history has {n_periods}"
        )
        out["acceleration_reason"] = out["reason"]
        out["stability_reason"] = out["reason"]
        return out

    total_w = sum(w for w, _ in weighted)
    out["momentum"] = sum(w * d for w, d in weighted) / total_w

    if accel_weighted:
        total_aw = sum(w for w, _ in accel_weighted)
        out["acceleration"] = sum(w * a for w, a in accel_weighted) / total_aw
    else:
        out["acceleration_reason"] = (
            f"no factor has at least {accel_required} finite periods "
            f"(2*lag + 1 = {accel_required}); longest history has {n_periods}"
        )

    disp = _population_std(list(changes.values()))
    if disp is None:
        out["stability_reason"] = (
            "need at least 2 measurable factor changes to measure the "
            f"dispersion of the changes, got {len(changes)}"
        )
    else:
        out["stability"] = disp

    return out
