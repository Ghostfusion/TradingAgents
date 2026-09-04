"""Kalman-filter dynamic hedge-ratio spread estimation (six-pillar item 3).

The classic static (rolling OLS) hedge ratio in ``statistical.spread_zscore``
assumes a constant beta. Real pairs drift — a Kalman filter tracks the hedge
ratio state online:

    beta_k = beta_{k-1} + eta_k               (state evolves)
    y_k    = alpha_k + beta_k * x_k + eps_k   (measurement; alpha static)

Posterior update (material's form):

    K_k  = P_{k|k-1} x_k / (P_{k|k-1} x_k^2 + R)
    beta_k = beta_{k-1} + K_k (y_k - beta_{k-1} x_k - alpha)
    P_k  = (1 - K_k x_k) P_{k|k-1} + Q

Outputs the dynamic beta series + the model spread ``s = y - alpha -
beta*x`` so a pair signal can mean-revert on a stable, adaptive hedge rather
than a fixed regression slope. Deterministic, pure, no numpy dependency.
"""

from __future__ import annotations

from typing import Any

DEFAULT_Q = 1e-4  # state noise: slow drift
DEFAULT_R = 1e-2  # measurement noise
DEFAULT_ALPHA = 0.0  # long-run intercept (ignore level by default)


def _clean(series) -> list[float]:
    out = []
    for v in series or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:  # not NaN
            out.append(f)
    return out


def kalman_spread(
    x: list,
    y: list,
    process_noise: float = DEFAULT_Q,
    measurement_noise: float = DEFAULT_R,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Online Kalman-filter hedge-ratio spread for a pair.

    Args:
        x: independent series (prices/levels, oldest first).
        y: dependent series (the pair's target).
        process_noise: Q - state-evolution noise (beta drift).
        measurement_noise: R - observation noise.
        alpha: fixed intercept in the measurement equation.

    Returns:
        dict: ``{beta, spread, signal, last_beta, last_spread, n}``.
          * beta - full dynamic beta series (length == min(n_x, n_y)).
          * spread - model spread series (y - alpha - beta*x), same length.
          * signal - +1 / -1 / 0 of the LAST z of the spread vs its own
            rolling window (mean-reversion; None when too short).
    """
    xs = _clean(x)
    ys = _clean(y)
    n = min(len(xs), len(ys))
    if n < 5:
        return {"beta": [], "spread": [], "signal": None,
                "last_beta": None, "last_spread": None, "n": 0}
    xs, ys = xs[:n], ys[:n]
    Q = max(float(process_noise), 1e-12)
    R = max(float(measurement_noise), 1e-12)
    a = float(alpha)

    beta = 0.0  # start flat
    P = 1.0  # initial state covariance
    betas: list[float] = []
    spreads: list[float] = []
    for i in range(n):
        xk = xs[i]
        yk = ys[i]
        K = (P * xk) / (P * xk * xk + R)
        residual = yk - a - beta * xk
        beta = beta + K * residual
        P = (1.0 - K * xk) * P + Q
        betas.append(beta)
        spreads.append(yk - a - beta * xk)
    signal = None
    if len(spreads) >= 20:
        tail = spreads[-20:]
        m = sum(tail) / len(tail)
        var = sum((v - m) ** 2 for v in tail) / (len(tail) - 1)
        sd = var ** 0.5 if var > 0 else 0.0
        z = (spreads[-1] - m) / sd if sd > 0 else 0.0
        signal = 1 if z > 1.5 else (-1 if z < -1.5 else 0)
    return {
        "beta": [round(v, 6) for v in betas],
        "spread": [round(v, 6) for v in spreads],
        "signal": signal,
        "last_beta": round(betas[-1], 6),
        "last_spread": round(spreads[-1], 6),
        "n": n,
    }


__all__ = ["kalman_spread", "DEFAULT_Q", "DEFAULT_R", "DEFAULT_ALPHA"]
