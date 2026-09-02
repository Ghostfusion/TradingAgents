"""Backtest tradability model (Qlib ``Exchange`` pillar 13 port).

Extends ``backtest_models.py``'s fee/slippage layer with the tradability
rules Qlib's exchange enforces: limit-up/down gates (untradable to buy /
sell), suspended days (NaN/None close = suspended, the ``$close``
convention), participation caps on order size vs day volume, and a
configurable deal-price selector (``close`` | ``open`` | ``vwap``, or a
buy/sell pair). Every function is pure and returns ``float | None`` / bool /
int per the no-fabrication contract — the fill engine consumes these and
states the model it used.
"""

from __future__ import annotations

import math


def suspended(close) -> bool:
    """True when the close is missing/NaN (Qlib ``$close`` suspended rule)."""
    if close is None:
        return True
    try:
        f = float(close)
    except (TypeError, ValueError):
        return True
    return not math.isfinite(f) or f <= 0


def limit_gate(change, threshold: float = 0.0) -> str | None:
    """Limit-up/down tradability gate from a day's pct change (fraction).

    ``change`` = today's move vs yesterday's close (0.10 = +10%).
    Returns ``"up"`` (limit-up: untradable to BUY) when change >= threshold,
    ``"down"`` (untradable to SELL) when change <= -threshold, else None.
    ``threshold <= 0`` disables the gate (None always).
    """
    if threshold <= 0:
        return None
    try:
        c = float(change)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(c):
        return None
    if c >= threshold:
        return "up"
    if c <= -threshold:
        return "down"
    return None


def volume_gate(order_qty, day_volume, participation_cap: float = 0.2) -> int:
    """Cap an order's quantity at ``participation_cap`` of the day's volume.

    Returns the truncated integer quantity (>= 0); a day with no measurable
    volume yields 0 (no fill) when a cap is active.
    """
    try:
        q = float(order_qty)
        v = float(day_volume)
        cap = float(participation_cap)
    except (TypeError, ValueError):
        return max(0, int(order_qty)) if order_qty is not None else 0
    if cap <= 0 or v <= 0:
        return 0 if cap > 0 else max(0, int(q))
    return max(0, min(int(q), int(v * cap)))


def deal_price_selector(bar: dict, price_spec: str | tuple) -> float | None:
    """Deal price for a fill from a bar dict, per Qlib ``deal_price``.

    ``price_spec`` = ``"close"`` | ``"open"`` | ``"vwap"``, or a
    ``(buy_spec, sell_spec)`` tuple (buy fills use the first, sells the
    second). None when the bar lacks the requested field (no fill).
    """
    spec = price_spec[0] if isinstance(price_spec, tuple) else price_spec
    if not isinstance(spec, str):
        return None
    key = spec.strip().lower()
    if key in ("close", "open", "vwap"):
        value = bar.get(key)
        if value is None and key == "vwap":
            value = _vwap_from_bar(bar)
        if value is None or suspended(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _vwap_from_bar(bar: dict) -> float | None:
    vals = [bar.get(k) for k in ("high", "low", "close")]
    if any(v is None for v in vals):
        return None
    try:
        return (float(vals[0]) + float(vals[1]) + float(vals[2])) / 3.0
    except (TypeError, ValueError):
        return None


def change_vs_prev(close, prev_close) -> float | None:
    """Day pct change (fraction) for the limit gate; None when unmeasurable."""
    if suspended(close) or suspended(prev_close):
        return None
    try:
        p = float(prev_close)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return float(close) / p - 1.0


__all__ = [
    "suspended",
    "limit_gate",
    "volume_gate",
    "deal_price_selector",
    "change_vs_prev",
]
