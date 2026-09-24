"""Long-memory parameter + HAR-family realized-variance forecast (V2; 2605.24285).

``mean_reversion.hurst_exponent`` estimates *roughness* - the rescaled-range
slope of a return series - and says nothing about the *memory* of the variance
process: whether a shock's effect on variance decays geometrically (short
memory, ``d = 0``) or hyperbolically (long memory, ``d > 0``). This module adds
that second read and leaves the roughness leg exactly where it is.

- :func:`memory_parameter` - the semiparametric memory parameter ``d`` from two
  estimators over one window: GPH log-periodogram regression and local Whittle,
  both fitting ``log I(lambda_j) = c - 2 d log(lambda_j) + e``.
- :func:`rv_forecast` - a HAR-family next-day realized-variance forecast
  ``RV_{t+1} = b0 + b_d RV_t + b_w RV_w + b_m RV_m (+ X_t)``. The ``X_t``
  regressors are the cross-sectional and sector persistence aggregates; those
  need a panel read this engine does not hold, so the leg is reported
  ``unavailable`` rather than invented, and the fit is the plain HAR.

Two rules bind both, and they are why the record shapes are what they are:

- **Strictly backward.** A window that still contains any observation at or
  after the as-of date is refused (``status: "unavailable"``), never silently
  trimmed - the estimate must not see a future stressed name.
- **``d`` beside the forecast, never instead of it.** Every forecast record
  carries ``d`` (and the full memory record), because a forecast from a series
  with ``d = 0`` and one with ``d = 0.44`` are different objects.

Missing data is ``unavailable``, never zero. Pure, deterministic, O(n log n).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize_scalar

__all__ = [
    "MEMORY_WINDOW",
    "MIN_MEMORY_OBS",
    "HAR_MIN_OBS",
    "long_memory_enabled",
    "memory_parameter",
    "rv_forecast",
]

#: The rolling window the paper estimates its memory parameter on (trading days).
MEMORY_WINDOW = 750

#: Below this many finite observations the semiparametric fit is not identified
#: - the record is ``unavailable``, never a number from a handful of ordinates.
MIN_MEMORY_OBS = 128

#: Below this many realized-variance observations the HAR regression has no
#: degrees of freedom left after its 22-day monthly term - ``unavailable``.
HAR_MIN_OBS = 64


def long_memory_enabled(config: dict | None = None) -> bool:
    """Whether the ``enable_long_memory`` gate is on (default **off**).

    This helper is the gate's **enforcement site**: ``memory_parameter`` and
    ``rv_forecast`` stay pure - they never read the config themselves - and
    every caller reads the switch from here, so the gate has one home rather
    than one per call site.

    ``config`` may be supplied explicitly (the ``strategies/overlays.py``
    convention), so a caller already holding the run's config does not re-fetch
    it. A missing or unreadable config is an **ungated** read, never a crash.
    """
    if config is None:
        try:
            from tradingagents.dataflows.config import get_config

            config = get_config() or {}
        except Exception:  # noqa: BLE001 - a config read must never break a read
            return False
    return bool((config or {}).get("enable_long_memory", False))


def _finite_pairs(series) -> list[tuple]:
    """``(label, value)`` for every finite observation, labels kept aligned.

    A pandas Series supplies its index as the labels; a plain sequence uses its
    positions. A missing / non-finite value is dropped **together with its
    label**, so an interior hole cannot shift the alignment the backwardness
    check depends on.
    """
    if series is None:
        return []
    items = list(series.items()) if hasattr(series, "items") else list(enumerate(series))
    out: list[tuple] = []
    for label, value in items:
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append((label, f))
    return out


def _periodogram(values, m: int) -> tuple[np.ndarray, np.ndarray]:
    """``(lambda_j, I(lambda_j))`` for the first ``m`` Fourier frequencies."""
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    n = x.size
    spectrum = np.fft.rfft(x)
    density = (np.abs(spectrum) ** 2) / (2.0 * math.pi * n)
    freq = 2.0 * math.pi * np.arange(density.size) / n
    return freq[1:m + 1], density[1:m + 1]


def _gph_d(freq: np.ndarray, density: np.ndarray) -> float:
    """GPH log-periodogram regression: the slope of ``log I`` on ``log lambda``
    is ``-2 d``, so ``d = -slope / 2`` (Geweke-Porter-Hudak 1983)."""
    y = np.log(density)
    x = np.log(freq)
    mx = x.mean()
    my = y.mean()
    slope = float(((x - mx) * (y - my)).sum() / ((x - mx) ** 2).sum())
    return -0.5 * slope


def _whittle_d(freq: np.ndarray, density: np.ndarray) -> float:
    """Local Whittle (Robinson 1995): the minimizer of
    ``R(d) = log(mean(lambda^{2d} I)) - 2 d mean(log lambda)`` over ``(-0.5, 0.5)``."""
    log_freq = np.log(freq)
    mean_log = float(log_freq.mean())

    def objective(d: float) -> float:
        weighted = (freq ** (2.0 * d)) * density
        return math.log(float(weighted.mean())) - 2.0 * d * mean_log

    result = minimize_scalar(objective, bounds=(-0.499, 0.499), method="bounded")
    return float(result.x)


def _refuse(record: dict, reason: str) -> dict:
    """Mark a memory/forecast record ``unavailable`` with the reason named."""
    record["status"] = "unavailable"
    record["unavailable"] = reason
    record["basis"] = f"unavailable: {reason}"
    return record


def memory_parameter(returns, as_of=None, *, window: int = MEMORY_WINDOW) -> dict:
    """Semiparametric memory parameter ``d`` by GPH and local Whittle (V2).

    ``returns`` is the series the window is cut from - a pandas Series (its
    index supplies the dates) or a plain sequence (positions are the labels).
    ``as_of`` is the as-of label. When it is given, every observation at or
    after it must already be absent from ``returns``: a window that still
    contains one is **refused**, never silently trimmed, so the estimate is
    strictly backward and a future stressed name can never enter it. When
    ``as_of`` is None the series is taken as already cut.

    The window is the last ``window`` observations (the paper's 750 trading
    days). Both estimators fit the same low-frequency ordinates
    ``log I(lambda_j) = c - 2 d log(lambda_j) + e`` over the first
    ``m = floor(sqrt(n))`` Fourier frequencies; ``se`` is the GPH asymptotic
    standard error ``pi / sqrt(24 m)``, which the local-Whittle estimate is also
    compared against (its own asymptotic se ``1 / (2 sqrt(m))`` is smaller).

    Returns ``{'gph_d', 'whittle_d', 'se', 'status', 'unavailable', 'n',
    'window', 'bandwidth', 'basis'}``. Too short a window, no finite
    observations, or a window reaching the as-of date returns
    ``status: "unavailable"`` with the estimates None and the reason named -
    never a zero.
    """
    record: dict = {
        "gph_d": None,
        "whittle_d": None,
        "se": None,
        "status": "unavailable",
        "unavailable": None,
        "n": 0,
        "window": window,
        "bandwidth": None,
        "basis": "",
    }
    pairs = _finite_pairs(returns)
    if not pairs:
        return _refuse(record, "no finite observations in the series")
    if as_of is not None:
        try:
            future = [label for label, _ in pairs if label >= as_of]
        except TypeError:
            return _refuse(
                record, f"as-of label {as_of!r} is not comparable with the series index"
            )
        if future:
            return _refuse(
                record,
                f"window contains {len(future)} observation(s) at or after the as-of "
                f"date {as_of!r}; the memory estimate is strictly backward",
            )
    if len(pairs) < MIN_MEMORY_OBS:
        return _refuse(
            record, f"needs at least {MIN_MEMORY_OBS} finite observations, got {len(pairs)}"
        )
    used = pairs[-window:]
    n = len(used)
    values = [value for _, value in used]
    m = math.isqrt(n)
    if m < 8:
        return _refuse(
            record, f"bandwidth floor: {n} observations give {m} usable ordinates (< 8)"
        )
    freq, density = _periodogram(values, m)
    gph = _gph_d(freq, density)
    whittle = _whittle_d(freq, density)
    se = math.pi / math.sqrt(24.0 * m)
    record.update({
        "gph_d": round(gph, 6),
        "whittle_d": round(whittle, 6),
        "se": round(se, 6),
        "status": "ok",
        "n": n,
        "bandwidth": m,
        "basis": (
            f"GPH log-periodogram + local Whittle over the last {n} observations "
            f"(window {window}), m = {m} low-frequency ordinates; "
            "log I(lambda) = c - 2 d log(lambda); se = pi/sqrt(24m) (GPH asymptotic)"
        ),
    })
    return record


def _trailing_mean(values: list[float], end: int, length: int) -> float:
    """Mean of the ``length`` observations ending at index ``end`` (inclusive)."""
    lo = max(0, end - length + 1)
    window = values[lo:end + 1]
    return sum(window) / len(window)


def rv_forecast(
    returns,
    as_of=None,
    *,
    window: int = MEMORY_WINDOW,
    rv=None,
    extra=None,
) -> dict:
    """HAR-family next-day realized-variance forecast, ``d`` beside it (V2).

    ``RV_{t+1} = b0 + b_d RV_t + b_w RV_w + b_m RV_m (+ X_t)`` is fitted by OLS
    on the backward window, where ``RV_w`` / ``RV_m`` are the trailing 5- and
    22-day means of ``RV``. ``RV`` is ``returns ** 2`` - a daily squared-return
    proxy, the closest thing to a realized measure a daily engine holds - unless
    ``rv`` supplies the realized-variance series directly.

    ``extra`` is the optional ``X_t`` regressor column (one value per
    observation, aligned with ``rv``) - the cross-sectional / sector persistence
    aggregates. No panel read exists in this engine, so with ``extra`` omitted
    the leg is reported ``unavailable`` and the fit is the plain HAR; the
    missing leg is named, never filled with a zero.

    The record **always** carries ``d`` (the GPH memory parameter) and the full
    ``memory`` record beside the ``forecast``, never instead of it - a forecast
    from ``d = 0`` and one from ``d = 0.44`` are different objects. A window
    reaching the as-of date, too few observations, or a rank-deficient design
    returns ``status: "unavailable"``.
    """
    memory = memory_parameter(returns, as_of, window=window)
    if extra is None:
        extra_record = {
            "status": "unavailable",
            "reason": (
                "cross-sectional / sector persistence aggregates need a panel read "
                "the engine does not hold; the HAR-X leg is not fitted (H10 reports "
                "the panel window once one exists)"
            ),
            "n": 0,
        }
    else:
        extra_record = {"status": "ok", "reason": None, "n": 1}
    record: dict = {
        "status": "unavailable",
        "unavailable": None,
        "forecast": None,
        "d": memory["gph_d"],
        "memory": memory,
        "coeffs": None,
        "extra": extra_record,
        "n": 0,
        "window": window,
        "basis": "",
    }
    rv_pairs = (
        [(label, value * value) for label, value in _finite_pairs(returns)]
        if rv is None
        else _finite_pairs(rv)
    )
    if not rv_pairs:
        return _refuse(record, "no finite realized-variance observations")
    if as_of is not None:
        try:
            future = [label for label, _ in rv_pairs if label >= as_of]
        except TypeError:
            return _refuse(
                record, f"as-of label {as_of!r} is not comparable with the series index"
            )
        if future:
            return _refuse(
                record,
                f"window contains {len(future)} observation(s) at or after the as-of "
                f"date {as_of!r}; the forecast is strictly backward",
            )
    if len(rv_pairs) < HAR_MIN_OBS:
        return _refuse(
            record,
            f"needs at least {HAR_MIN_OBS} realized-variance observations, got {len(rv_pairs)}",
        )
    used = rv_pairs[-window:]
    n = len(used)
    values = [value for _, value in used]
    if extra is not None:
        extra_values = list(extra)[-n:]
        if len(extra_values) != n:
            return _refuse(
                record,
                f"X_t column has {len(extra_values)} value(s) for {n} observations; "
                "the aggregate must align with the realized-variance window",
            )
    else:
        extra_values = None
    rows: list[list[float]] = []
    targets: list[float] = []
    for t in range(22, n - 1):
        row = [
            1.0,
            values[t],
            _trailing_mean(values, t, 5),
            _trailing_mean(values, t, 22),
        ]
        if extra_values is not None:
            row.append(float(extra_values[t]))
        rows.append(row)
        targets.append(values[t + 1])
    design = np.asarray(rows, dtype=float)
    target = np.asarray(targets, dtype=float)
    if design.shape[0] < design.shape[1] + 1 or np.linalg.matrix_rank(design) < design.shape[1]:
        return _refuse(
            record,
            f"HAR design is rank-deficient or too small ({design.shape[0]} rows, "
            f"{design.shape[1]} columns)",
        )
    coeffs, *_ = np.linalg.lstsq(design, target, rcond=None)
    next_row = [
        1.0,
        values[n - 1],
        _trailing_mean(values, n - 1, 5),
        _trailing_mean(values, n - 1, 22),
    ]
    if extra_values is not None:
        next_row.append(float(extra_values[n - 1]))
    names = ["b0", "b_d", "b_w", "b_m"] + (["b_x"] if extra_values is not None else [])
    forecast = float(np.asarray(next_row) @ coeffs)
    record.update({
        "status": "ok",
        "forecast": round(forecast, 12),
        "coeffs": {name: round(float(c), 12) for name, c in zip(names, coeffs, strict=True)},
        "n": n,
        "basis": (
            f"HAR{'-X' if extra_values is not None else ''} OLS on the last {n} "
            f"observations (window {window}), RV_{'{t+1}'} = b0 + b_d RV_t + "
            "b_w mean(RV,5) + b_m mean(RV,22)"
            + (" + b_x X_t" if extra_values is not None else " (X_t unavailable)")
            + f"; d = {memory['gph_d']} (GPH) beside the forecast"
        ),
    })
    return record
