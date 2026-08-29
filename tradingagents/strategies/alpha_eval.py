"""Magnitude + horizon-scored alpha (Lean L7).

The repo's ``calibration.py`` scores direction-only (up/down hit vs realized
return). Real spectrum: an insight carries a *predicted magnitude* over a
*horizon*; we never learn "I said +12%/30d, realized +2%". This module scores
direction AND magnitude versus the realized return, and flags horizon
accuracy — so the journal/reflection can tell luck (right direction, bad
magnitude) from skill.

Pure / offline. Returns floats or explicit ``None`` — never fabricated.
"""


def _magnitude_error(predicted: float | None, actual: float | None) -> float | None:
    if predicted is None or actual is None:
        return None
    return float(actual) - float(predicted)


def alpha_score(direction: str, predicted_magnitude: float | None,
                period_days: int | None, actual_return: float | None,
                confidence: float | None = None) -> dict:
    """Score one insight against its realized outcome.

    ``direction`` is 'up'/'long' or 'down'/'short'.
    ``actual_return`` is the realized return over ``period_days``.

    Returns ``{'hit', 'magnitude_err', 'score', 'horizon_ok', 'confidence'}``.
    - ``hit``: bool | None — None when direction/actual are unusable.
    - ``score``: +1/-1/0 directional contribution, scaled by magnitude
      accuracy when both predicted & actual are present (0..1 blend).
    - ``horizon_ok``: bool | None — True when predicted magnitude sign matches
      actual for the stated horizon.
    """
    d = (direction or "").strip().lower()
    if not d:
        return {"hit": None, "magnitude_err": None, "score": None,
                "horizon_ok": None, "confidence": None}
    long = d in ("up", "long", "long-only", "buy")
    if actual_return is None:
        return {"hit": None, "magnitude_err": None, "score": None,
                "horizon_ok": None, "confidence": confidence}
    actual = float(actual_return)
    expected_sign = 1.0 if long else -1.0
    hit = (actual * expected_sign) > 0
    err = _magnitude_error(predicted_magnitude, actual)
    # magnitude accuracy: how close predicted|sign-adjusted| was to actual
    mag_score = 1.0
    if predicted_magnitude is not None and err is not None:
        pred = float(predicted_magnitude) * expected_sign
        if abs(pred) > 1e-12:
            mag_score = max(0.0, 1.0 - abs(err) / abs(pred))
        else:
            mag_score = 1.0 if abs(actual) < 1e-12 else 0.0
    # directional score: +1 on a correct call, -1 on a wrong one, scaled by
    # magnitude accuracy (a hit is positive regardless of direction/sign).
    score = (1.0 if hit else -1.0) * mag_score
    # horizon_ok: pred magnitude sign matches actual sign for this horizon
    horizon_ok = None
    if predicted_magnitude is not None:
        pred = float(predicted_magnitude)
        horizon_ok = (pred * actual) > 0 if actual != 0 else (pred == 0)
    return {
        "hit": hit,
        "magnitude_err": round(err, 6) if err is not None else None,
        "score": round(score, 4),
        "horizon_ok": horizon_ok,
        "confidence": confidence,
    }


def insight_accuracy(insights: list[dict]) -> dict:
    """Aggregate accuracy over a list of insight/outcome dicts.

    Each item may be the output of :func:`alpha_score` or a raw dict. Returns
    ``{'n', 'hit_rate', 'avg_score', 'magnitude_hit_rate'}`` (floats or None).
    """
    n = len(insights)
    if not n:
        return {"n": 0, "hit_rate": None, "avg_score": None, "magnitude_hit_rate": None}
    hits = [i for i in insights if i.get("hit") is True]
    mags = [i for i in insights if i.get("horizon_ok") is True]
    scored = [i["score"] for i in insights
              if isinstance(i.get("score"), (int, float))]
    return {
        "n": n,
        "hit_rate": round(len(hits) / n, 4),
        "avg_score": round(sum(scored) / len(scored), 4) if scored else None,
        "magnitude_hit_rate": round(len(mags) / n, 4),
    }


__all__ = ["alpha_score", "insight_accuracy"]
