"""E7: the producers behind ``forecast_contract.SCORING_RULES``.

``SCORING_RULES = ("CRPS", "QLIKE", "RMSE", "MAE")`` declares the rules a
``ForecastEvaluation`` may be scored under, but until now only the vocabulary
existed - neither CRPS nor QLIKE had an implementation anywhere (FINDINGS §3).
All four are LOWER-IS-BETTER, so a score is comparable to the benchmark on the
same rule. This module is the ONE producer of each rule's number; it is offline
and pure, and :func:`score_forecast` is the dispatcher the offline caller
(``scripts/forecast_scores.py``) uses.

This is not the frozen forecasting contract (§11.0): it adds no field to
``ForecastEvaluation`` and duplicates no authoritative producer - it is the
arithmetic the declared rules always implied.
"""

from __future__ import annotations

import math

from tradingagents.strategies.forecast_contract import SCORING_RULES


def _pairs(actual, forecast):
    """Aligned finite ``(actual, forecast)`` pairs; non-numeric / None dropped."""
    out = []
    for a, f in zip(actual or [], forecast or [], strict=False):
        if a is None or f is None:
            continue
        try:
            out.append((float(a), float(f)))
        except (TypeError, ValueError):
            continue
    return out


def rmse(actual, forecast) -> float | None:
    """Root-mean-square error (lower is better). ``None`` on no usable pair."""
    pairs = _pairs(actual, forecast)
    if not pairs:
        return None
    return math.sqrt(sum((a - f) ** 2 for a, f in pairs) / len(pairs))


def mae(actual, forecast) -> float | None:
    """Mean absolute error (lower is better). ``None`` on no usable pair."""
    pairs = _pairs(actual, forecast)
    if not pairs:
        return None
    return sum(abs(a - f) for a, f in pairs) / len(pairs)


def qlike(actual, forecast) -> float | None:
    """QLIKE for VARIANCE forecasts: ``mean(a/f - ln(a/f) - 1)``.

    Lower is better and the loss is 0 at a perfect variance forecast; it is the
    standard robust loss for a variance/volatility forecast (it penalises
    under-prediction more than over-prediction). Non-positive actuals or
    forecasts carry no ratio and are dropped; ``None`` when none survives.
    """
    out = []
    for a, f in _pairs(actual, forecast):
        if a <= 0.0 or f <= 0.0:
            continue
        ratio = a / f
        out.append(ratio - math.log(ratio) - 1.0)
    if not out:
        return None
    return sum(out) / len(out)


def crps(actual, members) -> float | None:
    """CRPS of an ENSEMBLE forecast, in the energy (sample) form.

    ``members`` is one ensemble per origin (a list of member values per actual).
    ``CRPS = (1/M) sum_i |m_i - a| - (1/(2 M^2)) sum_i sum_j |m_i - m_j|``, the
    unbiased sample estimator. A degenerate ensemble (every member equal)
    reduces to ``|x - a|`` - i.e. MAE. ``None`` when no origin carries a usable
    ensemble.
    """
    total = 0.0
    n = 0
    for a, ens in zip(actual or [], members or [], strict=False):
        if a is None or not ens:
            continue
        vals = []
        for m in ens:
            try:
                vals.append(float(m))
            except (TypeError, ValueError):
                continue
        if not vals:
            continue
        try:
            av = float(a)
        except (TypeError, ValueError):
            continue
        m = len(vals)
        term1 = sum(abs(v - av) for v in vals) / m
        term2 = sum(abs(v - w) for v in vals for w in vals) / (2.0 * m * m)
        total += term1 - term2
        n += 1
    return total / n if n else None


def score_forecast(rule, actual, forecast) -> dict:
    """Dispatch a declared scoring rule to its producer.

    ``forecast`` is a list of point values (RMSE/MAE/QLIKE) or a list of
    ensembles (CRPS). Returns ``{rule, score, n, basis}``; ``score`` is ``None``
    when the rule refuses or is not one of ``SCORING_RULES``.
    """
    name = str(rule or "").upper()
    if name == "RMSE":
        s = rmse(actual, forecast)
    elif name == "MAE":
        s = mae(actual, forecast)
    elif name == "QLIKE":
        s = qlike(actual, forecast)
    elif name == "CRPS":
        s = crps(actual, forecast)
    else:
        return {
            "rule": rule, "score": None, "n": 0,
            "basis": f"unknown scoring rule {rule!r}; declared rules are {SCORING_RULES}",
        }
    n = len(list(actual or []))
    return {
        "rule": name, "score": s, "n": n,
        "basis": (
            f"{name} over {n} origin(s); every SCORING_RULE is lower-is-better, "
            "so this is comparable to a benchmark scored on the same rule"
        ),
    }


__all__ = ["rmse", "mae", "qlike", "crps", "score_forecast", "SCORING_RULES"]
