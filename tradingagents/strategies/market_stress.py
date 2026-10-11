"""Market-stress reads: the turbulence index (FinRL 1; ``docs/design_finrl_integration.md`` §6.1/§7).

The turbulence index is the Mahalanobis distance of one day's **cross-section** of
asset returns from its own trailing history:

    ``tau_t = (x_t - mu)^T Sigma^-1 (x_t - mu)``

with ``mu`` and ``Sigma`` estimated on the window that **ends the day before**
``t``. Two properties matter more than the number:

* **no look-ahead** - the window is strictly prior to the observation it scores,
  so the read cannot see the cross-section it is judging;
* **a conditioned Sigma** - the inverse is taken on
  ``covariance_models.ledoit_wolf_shrink``'s shrunk matrix, because a raw sample
  covariance over a few tens of correlated names is the canonical
  ill-conditioned inverse.

The **arithmetic** is the engine's existing Mahalanobis producer
(``breadth_depth._mahalanobis_distance``, REG-18, until now private and awaiting a
consumer); this module owns the rolling window, the shrinkage, the own-history
gate and the refusal contract.

The gate is the read's own past: ``gate`` is True when the latest index sits above
the trailing ``quantile`` of the index series - the form FinRL uses to switch an
environment to risk-off. A gate here is a WARNING channel: it sizes nothing and
touches no rating.
"""

from __future__ import annotations

import math

from tradingagents.strategies.covariance_models import COV_MIN_OBS

__all__ = [
    "TURBULENCE_MIN_OBS",
    "TURBULENCE_QUANTILE",
    "turbulence_index",
    "turbulence_read",
]

#: The observation floor, imported from the covariance module rather than restated
#: so the two cannot drift: the shrinkage this read depends on refuses below it.
TURBULENCE_MIN_OBS = COV_MIN_OBS

#: The own-history quantile the gate compares the latest index against.
TURBULENCE_QUANTILE = 0.90


def _aligned(panel) -> tuple[list[str], list[list[float]], int]:
    """Usable names, their finite series aligned to the common tail, and that length.

    A name with fewer than two finite observations is dropped (never padded); the
    retained series are truncated to the shortest, so ``panel`` may be ragged.
    """
    usable: dict[str, list[float]] = {}
    for name, series in (panel or {}).items():
        vals: list[float] = []
        for v in series or []:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                vals.append(f)
        if len(vals) >= 2:
            usable[str(name)] = vals
    if not usable:
        return [], [], 0
    # A ONE-name panel is returned rather than swallowed, so the caller can name
    # what it found ("1 name is not a cross-section") instead of reporting none.
    n = min(len(v) for v in usable.values())
    names = sorted(usable)
    return names, [usable[name][-n:] for name in names], n


def _covariance(matrix_y, *, shrinkage: bool, min_obs: int) -> tuple[list[list[float]] | None, float | None, str | None]:
    """The covariance ``Sigma`` for the window, shrunk by default.

    Returns ``(cov, shrinkage_intensity, refusal_reason)``. The shrink is the
    engine's own estimator, fed the same ``{name: series}`` shape every allocator
    uses; with the shrink refused (too few observations for its floor) or turned
    off, the raw sample covariance is used **and the reason says so** - a raw
    inverse is a decision, never a silent fallback.
    """
    import numpy as _np

    from tradingagents.strategies.covariance_models import ledoit_wolf_shrink

    if shrinkage:
        shrink = ledoit_wolf_shrink(matrix_y, min_obs=min_obs)
        if shrink.get("cov") is not None:
            return shrink["cov"], shrink.get("shrinkage"), None
        reason = (
            f"the Ledoit-Wolf shrink refused this window (floor {min_obs} observations, "
            f"{shrink.get('n_obs')} available); set shrinkage=False to take the raw "
            "sample covariance instead"
        )
        return None, None, reason
    # The raw alternative, named: the same {name: series} shape, sample covariance
    # with no shrink (so a degenerate panel really can be singular here - the
    # refusal that follows is the read's, not the estimator's).
    rows = _np.array([list(series) for series in matrix_y.values()], dtype=float)
    return _np.cov(rows, bias=False).tolist(), None, None


def turbulence_index(
    panel,
    *,
    target=None,
    window: int | None = None,
    shrinkage: bool = True,
    min_obs: int = TURBULENCE_MIN_OBS,
) -> dict | None:
    """One cross-section's turbulence against its own strictly-prior window.

    ``panel`` is ``{name: [return, ...]}`` (the series' own order; the tail is what
    is scored). ``target`` is the cross-section to score, one value per name - by
    default the **last** observation of each name, which is then EXCLUDED from the
    window it is measured against. ``window`` caps how many prior observations the
    mean/covariance use (default: all strictly-prior ones).

    Returns ``{"index", "n_obs", "n_dim", "window", "shrinkage", "names",
    "unavailable", "basis"}``; ``index`` is ``None`` - never ``0.0`` - with the
    reason when the panel is too short, a value is non-finite, the covariance is
    singular, or the quadratic form is negative. ``None`` for a degenerate panel.
    """
    import numpy as _np

    names, series, n = _aligned(panel)
    if len(names) < 2 or n < 2:
        return None
    scored = None
    if target is None:
        scored = [row[-1] for row in series]
        history = [row[:-1] for row in series]
    else:
        if not isinstance(target, dict):
            return None
        values = []
        for name in names:
            try:
                values.append(float(target[name]))
            except (KeyError, TypeError, ValueError):
                return {
                    "index": None,
                    "n_obs": 0,
                    "n_dim": len(names),
                    "window": 0,
                    "shrinkage": None,
                    "names": names,
                    "unavailable": f"target is missing a finite value for {name!r}",
                    "basis": "tau = (x - mu)^T Sigma^-1 (x - mu) on the strictly-prior window",
                }
        scored = values
        history = series
    if not math.isfinite(sum(scored)):
        return None
    take = int(window) if window else len(history[0])
    take = max(2, min(take, len(history[0])))
    hist = [row[-take:] for row in history]
    covariance, intensity, reason = _covariance(
        {name: hist[i] for i, name in enumerate(names)},
        shrinkage=shrinkage,
        min_obs=min_obs,
    )
    basis = (
        f"tau = (x - mu)^T Sigma^-1 (x - mu), {len(names)} names x {take} strictly-prior "
        f"observation(s)" + (f", Sigma from covariance_models.ledoit_wolf_shrink "
                             f"(delta={intensity})" if intensity is not None else
                             ", Sigma from the raw sample covariance" if covariance else "")
    )
    if covariance is None:
        return {
            "index": None,
            "n_obs": take,
            "n_dim": len(names),
            "window": take,
            "shrinkage": intensity,
            "names": names,
            "unavailable": reason,
            "basis": basis,
        }
    matrix = _np.array(hist, dtype=float)  # (n_dim, n_obs)
    mu = matrix.mean(axis=1)
    from tradingagents.strategies.breadth_depth import _mahalanobis_distance

    read = _mahalanobis_distance(scored, mu.tolist(), covariance)
    return {
        "index": None if read is None else read.get("distance"),
        "n_obs": take,
        "n_dim": len(names),
        "window": take,
        "shrinkage": intensity,
        "names": names,
        "unavailable": None if read is not None and read.get("distance") is not None
        else (read or {}).get("unavailable", "the distance read returned nothing"),
        "basis": basis,
    }


def turbulence_read(
    panel,
    *,
    quantile: float = TURBULENCE_QUANTILE,
    window: int | None = None,
    shrinkage: bool = True,
    min_obs: int = TURBULENCE_MIN_OBS,
    min_history: int | None = None,
) -> dict:
    """The rolling turbulence series and the own-history gate on its latest point.

    Every point ``t`` is scored against the window ending at ``t-1``, so the series
    is the same read as :func:`turbulence_index` repeated without look-ahead. The
    gate is ``latest > quantile(series[:-1])``, at ``quantile`` over at least
    ``min_history`` prior points (default ``min_obs``): below that floor ``gate`` is
    ``None`` with the reason - never a fabricated ``False``.

    Returns ``{"series", "latest", "quantile", "threshold", "gate", "n_points",
    "n_dim", "n_obs", "shrinkage", "names", "unavailable", "basis"}``.
    """
    names, series, n = _aligned(panel)
    if len(names) < 2 or n < 2:
        return {
            "series": [],
            "latest": None,
            "quantile": float(quantile),
            "threshold": None,
            "gate": None,
            "n_points": 0,
            "n_dim": len(names),
            "n_obs": 0,
            "shrinkage": None,
            "names": names,
            "unavailable": "fewer than two names or two aligned observations",
            "basis": "turbulence_read needs a cross-section to be cross-sectional",
        }
    try:
        q = float(quantile)
    except (TypeError, ValueError):
        q = TURBULENCE_QUANTILE
    if not 0.0 < q < 1.0:
        q = TURBULENCE_QUANTILE
    floor = int(min_obs if min_history is None else min_history)
    scored: list[float | None] = []
    intensities: list[float | None] = []
    for end in range(2, n + 1):
        point = {
            name: series[i][:end] for i, name in enumerate(names)
        }
        read = turbulence_index(
            point, window=window, shrinkage=shrinkage, min_obs=min_obs
        )
        scored.append(None if read is None else read.get("index"))
        intensities.append(None if read is None else read.get("shrinkage"))
    usable = [v for v in scored if v is not None]
    latest = scored[-1] if scored else None
    prior = [v for v in scored[:-1] if v is not None]
    threshold = None
    gate = None
    reason = None
    if latest is None:
        reason = "the latest cross-section could not be scored"
    elif len(prior) < max(1, floor):
        reason = (
            f"{len(prior)} prior index point(s) of the {max(1, floor)} needed for a "
            f"{q:.2f}-quantile gate"
        )
    else:
        ordered = sorted(prior)
        rank = max(1, min(len(ordered), int(math.ceil(q * len(ordered)))))
        threshold = ordered[rank - 1]
        gate = bool(latest > threshold)
    return {
        "series": scored,
        "latest": latest,
        "quantile": q,
        "threshold": threshold,
        "gate": gate,
        "n_points": len(usable),
        "n_dim": len(names),
        "n_obs": n,
        "shrinkage": next((v for v in reversed(intensities) if v is not None), None),
        "names": names,
        "unavailable": reason,
        "basis": (
            f"rolling turbulence over {len(usable)} of {n} cross-sections, each scored "
            f"on the strictly-prior window (no look-ahead); gate = latest above the "
            f"own-history {q:.2f} quantile of the {len(prior)} prior point(s)"
            + (f"; unavailable: {reason}" if reason else "")
        ),
    }
