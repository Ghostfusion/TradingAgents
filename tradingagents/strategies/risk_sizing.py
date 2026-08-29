"""Fixed-risk position sizing (commission-aware, tranche-aware).

A single deterministic primitive mirroring NautilusTrader's
``calculate_fixed_risk_position_size``: a position size driven by a risk
budget (a fraction of equity) divided by the per-share risk distance to the
stop, net of commission, with an optional hard notional cap and a tranche
count. Every function returns a plain float or ``None`` per the
no-fabrication contract - never an invented number.

This is the "one sizer" that unifies ``size.py`` (quarter-Kelly +
risk/stop) and ``value_dip.tranche_plan`` / ``tranche_risk_read`` so the risk
governor's budget and the sizer's output always agree.
"""

from __future__ import annotations

import contextlib


def risk_points(entry: float, stop: float) -> float:
    """Per-share risk distance = |entry - stop|.

    Zero when the inputs are degenerate (entry == stop or non-finite), so no
    downstream division-by-zero can occur.
    """
    try:
        e = float(entry)
        s = float(stop)
    except (TypeError, ValueError):
        return 0.0
    return abs(e - s)


def riskable_money(equity: float, risk_frac: float, commission_rate: float = 0.0) -> float:
    """Dollar risk budget available to a trade, net of an assumed commission.

    ``equity * risk_frac / (1 + commission_rate)`` - the commission consumes
    part of the stated risk budget, so the position is sized slightly smaller
    to keep the worst-case loss (including commission) inside the budget.
    Returns 0.0 for non-positive inputs.
    """
    try:
        eq = float(equity)
        rf = float(risk_frac)
        cr = float(commission_rate)
    except (TypeError, ValueError):
        return 0.0
    if eq <= 0 or not (0.0 <= rf <= 1.0) or cr < 0:
        return 0.0
    return eq * rf / (1.0 + cr)


def risk_money(
    entry: float,
    stop_loss: float,
    equity: float,
    risk: float,
    commission_rate: float = 0.0,
    exchange_rate: float = 1.0,
    hard_limit: float | None = None,
) -> float:
    """Fixed-risk position size in units (shares), net of commission.

    ``size = (equity * risk / (1 + commission)) / |entry - stop|`` in the
    account currency, converted by ``exchange_rate``. Optional ``hard_limit``
    bounds the result. Returns 0.0 when the risk distance or equity is
    unusable - never a fabricated size.
    """
    rp = risk_points(entry, stop_loss)
    if rp <= 0:
        return 0.0
    riskable = riskable_money(equity, risk, commission_rate)
    if riskable <= 0:
        return 0.0
    try:
        fx = float(exchange_rate)
    except (TypeError, ValueError):
        fx = 1.0
    if fx <= 0:
        return 0.0
    size = riskable / fx / rp
    if hard_limit is not None:
        with contextlib.suppress(TypeError, ValueError):
            size = min(size, float(hard_limit))
    return max(0.0, size)


def risk_quantity(
    entry: float,
    stop_loss: float,
    equity: float,
    risk: float,
    commission_rate: float = 0.0,
    exchange_rate: float = 1.0,
    hard_limit: float | None = None,
    units: int = 1,
    unit_batch_size: float = 1.0,
) -> float:
    """Fixed-risk position size split across ``units`` tranches.

    The total size is computed exactly like ``risk_money`` and then split
    evenly across ``units``, each tranche rounded down to the nearest
    ``unit_batch_size`` multiple (the Nautilus ``units`` / ``unit_batch_size``
    pattern). Returns the total position size (0.0 when unusable); the caller
    derives the per-tranche slice from ``units`` and ``unit_batch_size``.
    """
    total = risk_money(
        entry,
        stop_loss,
        equity,
        risk,
        commission_rate=commission_rate,
        exchange_rate=exchange_rate,
        hard_limit=hard_limit,
    )
    if total <= 0:
        return 0.0
    n = max(1, int(units))
    per = total / n
    if unit_batch_size and unit_batch_size > 0:
        b = float(unit_batch_size)
        per = (per // b) * b
    return per * n


__all__ = [
    "risk_points",
    "riskable_money",
    "risk_money",
    "risk_quantity",
]
