"""Magnitude + horizon-scored alpha (Lean L7).

The repo's ``calibration.py`` scores direction-only (up/down hit vs realized
return). Real spectrum: an insight carries a *predicted magnitude* over a
*horizon*; we never learn "I said +12%/30d, realized +2%". This module scores
direction AND magnitude versus the realized return, and flags horizon
accuracy — so the journal/reflection can tell luck (right direction, bad
magnitude) from skill.

H4 (paper-survey honest-evaluation) adds the out-of-sample R-squared ceiling.
``ceiling_ratio`` reports the bound 2602.07841 derives —
``plim R^2_OOS <= kappa * (2*DA - 1)^2`` with
``kappa = (E[sqrt(eps)])^2 / E[eps] - 1`` and ``eps_t = r_t^2 / sigma_hat_t^2``
— as the point ``((2*DA - 1)^2, R^2_OOS / kappa)`` and flags a point above the
45-degree line. ``sigma_hat`` is an **out-of-sample** GARCH(1,1) fit: the model
is fitted on a prior window and every evaluated row's conditional variance is a
one-step-ahead forecast that has seen no part of the rows it scores. It is a
**falsifier, never a validator** — an inequality derived from a constructed
oracle can flag an impossible point and can never reject a forecast, and
``kappa`` assumes sign/magnitude independence between the forecast and the
realized return.

Pure / offline. Returns floats or explicit ``None`` — never fabricated.
"""

import math

#: H4: evaluated (hold-out) rows below this floor earn no ceiling verdict —
#: the record reads ``unavailable`` instead of a ratio computed off 12 rows.
CEILING_MIN_N = 40
#: H4: the share of the series the ``sigma_hat`` fit window takes. The rest is
#: the hold-out the ceiling is evaluated on.
CEILING_TRAIN_FRAC = 0.5


def _ceiling_gate() -> bool:
    """Is the H4 accuracy ceiling switched on? (``enable_accuracy_ceiling``)

    Off by default, so a gate-off caller reads exactly what it read before the
    ceiling existed. A config read must never break the read it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_accuracy_ceiling", False))


def _finite_pairs(returns, forecasts) -> list[tuple[float, float]]:
    """``(realized, forecast)`` pairs where both sides are finite floats."""
    out: list[tuple[float, float]] = []
    for r, f in zip(returns or [], forecasts or [], strict=False):
        try:
            rv = float(r)
            fv = float(f)
        except (TypeError, ValueError):
            continue
        if math.isfinite(rv) and math.isfinite(fv):
            out.append((rv, fv))
    return out


def _oos_sigma_series(train: list[float], evaluated: list[float],
                      fit: dict) -> list[float]:
    """One-step-ahead conditional vol for ``evaluated``, from a fit on ``train``.

    The recursion carries the fit window's last conditional variance into the
    evaluated window and then consumes each realized return only *after* the
    row it belongs to, so ``sigma_hat_t`` is measurable at ``t-1`` — the
    assumption the ceiling is derived under. A sigma_hat fitted on the rows it
    scores makes ``eps_t`` the model's own standardized residual and the
    bound circular, which is the defect this split exists to prevent.
    """
    omega = float(fit["omega"])
    alpha = float(fit["alpha"])
    beta = float(fit["beta"])
    n = len(train)
    mean = sum(train) / n
    err = [x - mean for x in train]
    var = sum(x * x for x in err) / max(1, n - 1)
    for i in range(1, n):
        var = omega + alpha * err[i - 1] ** 2 + beta * var
    out = []
    for r in evaluated:
        # sigma_t is emitted from information through t-1, and only THEN does the
        # row's own return update the variance. The opposite order - update, then
        # emit - makes sigma_hat_t a function of r_t, so eps_t = r_t/sigma_hat_t
        # is the model's own standardized residual and the ceiling circular: the
        # exact defect this split exists to prevent.
        out.append(math.sqrt(max(var, 0.0)))
        var = omega + alpha * r * r + beta * var
    return out


def _kappa_hat(returns: list[float], sigmas: list[float]) -> float | None:
    """``(E[sqrt(eps)])^2 / E[eps] - 1`` over ``eps_t = r_t^2 / sigma_hat_t^2``.

    Never positive: ``(E[sqrt(eps)])^2 <= E[eps]`` by Jensen, with equality
    only for a constant ``eps`` — which is exactly the degenerate case the
    ceiling refuses, because the ratio divides by it.
    """
    eps = [r * r / (s * s) for r, s in zip(returns, sigmas, strict=True) if s > 0.0]
    if len(eps) < 5:
        return None
    mean_sqrt = sum(math.sqrt(e) for e in eps) / len(eps)
    mean = sum(eps) / len(eps)
    if mean <= 0.0:
        return None
    return (mean_sqrt * mean_sqrt) / mean - 1.0


def ceiling_ratio(returns, forecasts, *, train_frac: float = CEILING_TRAIN_FRAC,
                  min_n: int = CEILING_MIN_N) -> dict:
    """H4: the out-of-sample R-squared ceiling as a point and a flag.

    ``returns`` are the realized returns and ``forecasts`` their forecasts on
    the same rows, in the same order. The series is split: a GARCH(1,1) is
    fitted on the leading ``train_frac`` share and the ceiling is evaluated on
    the **hold-out** rows only, each row's ``sigma_hat`` being a one-step-ahead
    forecast from the fitted model.

    Returns ``{kappa_hat, da_squared, r2_ratio, r2_oos, da, n, train_n,
    flagged, basis, unavailable}``:

    * ``kappa_hat`` — ``(E[sqrt(eps)])^2/E[eps] - 1`` over the hold-out.
    * ``da_squared`` — ``(2*DA - 1)^2``: DA is the share of hold-out rows whose
      realized sign matches the forecast's, zero rows excluded, never counted
      as a miss.
    * ``r2_ratio`` — ``R2_OOS / kappa_hat``, against the realized mean.
    * ``flagged`` — the point sits **above** the 45-degree line.

    **Read the ceiling as a falsifier, never as a validator.** 2602.07841 is an
    inequality derived from a constructed oracle: a flagged point is
    arithmetically impossible, and an unflagged one is *not* evidence of skill.
    ``kappa`` assumes sign/magnitude independence between the forecast and the
    realized return, and the bound is a claim about a limit, not a test.

    Missing, thin or degenerate input — no fit, a hold-out under ``min_n``, a
    ``kappa_hat`` that is not negative — is ``unavailable`` with the reason,
    never a zero and never a substituted default.
    """
    rec = {
        "kappa_hat": None,
        "da_squared": None,
        "r2_ratio": None,
        "r2_oos": None,
        "da": None,
        "n": 0,
        "train_n": 0,
        "flagged": None,
        "basis": None,
        "unavailable": None,
    }
    if not _ceiling_gate():
        rec["unavailable"] = "accuracy ceiling off (enable_accuracy_ceiling)"
        return rec
    pairs = _finite_pairs(returns, forecasts)
    train_n = max(0, min(len(pairs), int(round(len(pairs) * float(train_frac)))))
    held = pairs[train_n:]
    rec["n"] = len(held)
    rec["train_n"] = train_n
    if len(held) < max(5, int(min_n)):
        rec["unavailable"] = (
            f"accuracy ceiling unavailable: {len(held)} evaluated row(s) below "
            f"the {int(min_n)}-row floor"
        )
        return rec
    from tradingagents.strategies.volatility_models import garch11_fit

    fit = garch11_fit([r for r, _ in pairs[:train_n]])
    if fit is None:
        rec["unavailable"] = (
            f"accuracy ceiling unavailable: no GARCH(1,1) fit for sigma_hat on "
            f"the {train_n}-row prior window"
        )
        return rec
    realized = [r for r, _ in held]
    sigmas = _oos_sigma_series([r for r, _ in pairs[:train_n]], realized, fit)
    kappa = _kappa_hat(realized, sigmas)
    rec["kappa_hat"] = kappa
    signed = [(r, f) for r, f in held if r != 0.0 and f != 0.0]
    if not signed:
        rec["unavailable"] = (
            "accuracy ceiling unavailable: no signed hold-out forecast to score"
        )
        return rec
    da = sum(1.0 for r, f in signed if f * r > 0.0) / len(signed)
    rec["da"] = da
    rec["da_squared"] = (2.0 * da - 1.0) ** 2
    mean = sum(realized) / len(realized)
    ss_tot = sum((r - mean) ** 2 for r in realized)
    if ss_tot <= 0.0:
        rec["unavailable"] = (
            "accuracy ceiling unavailable: no dispersion in the hold-out returns"
        )
        return rec
    ss_res = sum((f - r) ** 2 for r, f in held)
    rec["r2_oos"] = 1.0 - ss_res / ss_tot
    if kappa is None or kappa >= 0.0:
        rec["unavailable"] = (
            "accuracy ceiling unavailable: kappa_hat is not negative, so the "
            "standardized-residual dispersion is degenerate and the ratio is "
            "undefined"
        )
        return rec
    ratio = rec["r2_oos"] / kappa
    rec["r2_ratio"] = ratio
    rec["flagged"] = bool(ratio > rec["da_squared"])
    rec["basis"] = (
        f"R2_OOS ceiling over {len(held)} hold-out row(s) after a {train_n}-row "
        f"sigma_hat fit window (one-step-ahead GARCH(1,1), out of sample); "
        f"kappa_hat={kappa:.4f}, (2DA-1)^2={rec['da_squared']:.4f}, "
        f"R2_OOS/kappa={ratio:.4f} - "
        f"{'above' if rec['flagged'] else 'below'} the 45-degree line; a flagged "
        f"point is arithmetically impossible, an unflagged one is not evidence "
        f"of skill"
    )
    return rec


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


__all__ = ["alpha_score", "insight_accuracy", "ceiling_ratio",
           "CEILING_MIN_N", "CEILING_TRAIN_FRAC"]
