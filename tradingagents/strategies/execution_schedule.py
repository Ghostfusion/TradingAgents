"""Execution scheduling (Phase 6, advisory): Almgren-Chriss optimal trajectory
+ TWAP/VWAP/POV benchmarks.

Almgren & Chriss (2000): liquidate ``X`` over ``T`` intervals minimizing
expected implementation shortfall + a risk penalty (risk-aversion ``lam``).
Linear permanent impact g(v)=gamma*v and temporary h(v)=eta*v give the
closed-form hyperbolic schedule. The repo's execution-cost model
(backtest_models.square_root_impact + capacity) is the cost input; this module
converts a size into an actual per-interval trading plan, advisory-only (the
trader sizes by risk gates; the schedule is context, never an order).
"""

from __future__ import annotations

import math


def almgren_chriss(
    X: float,
    T: int,
    sigma: float,
    eta: float,
    lam: float,
    gamma: float = 0.0,
) -> dict:
    """Optimal liquidation trajectory (Almgren-Chriss, linear impact).

    ``x_t = X * sinh(kappa*(T-t)) / sinh(kappa*T)``, ``kappa = sqrt(lam *
    sigma^2 / eta)``; per-interval trade ``v_t = x_{t-1} - x_t``. Returns
    ``{'schedule': [(t, x_remaining, v_t), ...], 'kappa', 'e_is', 'var_is',
    'lambda', 'n'}`` with expected shortfall ``0.5*gamma*X^2 +
    eta*sum(v_t^2)`` and variance ``sigma^2 * sum(x_t^2)`` (AC formulas;
    gamma=0 drops the permanent-impact term). None-safe: bad inputs -> all
    None. Advisory (never an order).
    """
    try:
        X = float(X)
        T = int(T)
        sig = float(sigma)
        et = float(eta)
        L = float(lam)
        ga = float(gamma)
    except (TypeError, ValueError):
        return {"schedule": [], "kappa": None, "e_is": None, "var_is": None,
                "lambda": None, "n": 0}
    if X <= 0 or T <= 0 or sig <= 0 or et <= 0 or L <= 0:
        return {"schedule": [], "kappa": None, "e_is": None, "var_is": None,
                "lambda": None, "n": 0}
    kappa = math.sqrt(L * sig * sig / et)
    sinh_kT = math.sinh(kappa * T)
    if sinh_kT <= 1e-12:
        return {"schedule": [], "kappa": None, "e_is": None, "var_is": None,
                "lambda": None, "n": 0}
    schedule = []
    x_prev = X
    for t in range(1, T + 1):
        x_t = X * math.sinh(kappa * (T - t)) / sinh_kT
        v_t = x_prev - x_t
        schedule.append((t, round(x_t, 6), round(v_t, 6)))
        x_prev = x_t
    e_is = 0.5 * ga * X * X + et * sum(v[2] * v[2] for v in schedule)
    var_is = sig * sig * sum(v[1] * v[1] for v in schedule)
    return {"schedule": schedule, "kappa": round(kappa, 6),
            "e_is": round(e_is, 6), "var_is": round(var_is, 6),
            "lambda": round(L, 6), "n": T}


def twap_schedule(X: float, T: int) -> dict:
    """Time-weighted schedule: v_t = X/T each interval (uniform). Returns
    ``{'schedule': [(t, x_remaining, v_t), ...], 'n': T}``; None-safe."""
    try:
        X = float(X)
        T = int(T)
    except (TypeError, ValueError):
        return {"schedule": [], "n": 0}
    if X <= 0 or T <= 0:
        return {"schedule": [], "n": 0}
    v = X / T
    sched, x = [], X
    for t in range(1, T + 1):
        x -= v
        sched.append((t, round(x, 6), round(v, 6)))
    return {"schedule": sched, "n": T}


def vwap_schedule(X: float, volumes: list) -> dict:
    """Volume-weighted schedule: trade proportional to the expected per-interval
    volume (v_t = X * vol_t / sum(vol)). Requires a volume profile."""
    try:
        X = float(X)
        vols = [float(v) for v in (volumes or []) if v is not None and v > 0]
    except (TypeError, ValueError):
        return {"schedule": [], "n": 0}
    if X <= 0 or not vols:
        return {"schedule": [], "n": 0}
    total = sum(vols)
    sched, x = [], X
    for t, vt in enumerate(vols, start=1):
        v = X * vt / total
        x -= v
        sched.append((t, round(x, 6), round(v, 6)))
    return {"schedule": sched, "n": len(vols)}


def pov_schedule(X: float, volume_each_interval: float, participation: float = 0.10) -> dict:
    """Participation-rate (POV) schedule: v_t = participation * volume_t — the
    live-volume control rule (child order size). Advisories; None-safe."""
    try:
        X = float(X)
        vol = float(volume_each_interval)
        p = float(participation)
    except (TypeError, ValueError):
        return {"schedule": [], "n": 0}
    if X <= 0 or vol <= 0 or not (0.0 < p <= 1.0):
        return {"schedule": [], "n": 0}
    v = p * vol
    sched, x, t = [], X, 0
    while x > 1e-9 and t < 5000:
        t += 1
        trade = min(v, x)
        x -= trade
        sched.append((t, round(x, 6), round(trade, 6)))
    return {"schedule": sched, "n": t}


__all__ = ["almgren_chriss", "twap_schedule", "vwap_schedule", "pov_schedule"]
