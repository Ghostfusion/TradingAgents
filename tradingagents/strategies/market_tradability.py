"""Backtest tradability model (Qlib ``Exchange`` pillar 13 port).

Extends ``backtest_models.py``'s fee/slippage layer with the tradability
rules Qlib's exchange enforces: limit-up/down gates (untradable to buy /
sell), suspended days (NaN/None close = suspended, the ``$close``
convention), participation caps on order size vs day volume, and a
configurable deal-price selector (``close`` | ``open`` | ``vwap``, or a
buy/sell pair). Every function is pure and returns ``float | None`` / bool /
int per the no-fabrication contract — the fill engine consumes these and
states the model it used.

Each refusal (a limit-up/down side, a suspension, an order truncated to zero
shares) is also recorded in the H7 refusal ledger when ``enable_refusal_ledger``
is on, so a tradability gate's precision becomes measurable. The ledger only
observes: verdicts and returned quantities are unchanged, and a ledger failure
never reaches the caller.
"""

from __future__ import annotations

import contextlib
import math

from .refusal_ledger import log_refusal


def _note_refusal(rule: str, reason: str, *, symbol=None, as_of=None, **snapshot) -> None:
    """Record one tradability refusal (H7); never raises, never gates the caller.

    The ledger observes the gate, it does not participate in it: the verdict is
    returned unchanged whatever happens here.
    """
    with contextlib.suppress(Exception):
        log_refusal(
            symbol=symbol,
            as_of=as_of,
            gate="market_tradability",
            reason=reason,
            snapshot={"rule": rule, **snapshot},
        )


def _suspension_reason(close) -> str | None:
    """The one producer of the suspended verdict: the reason, or ``None``.

    Reading the tradability state (``deal_price_selector``, ``change_vs_prev``)
    asks this; only the public :func:`suspended` records the refusal, so one
    untradable day is one ledger row rather than one per reader.
    """
    if close is None:
        return "suspended: no close supplied (Qlib $close rule)"
    try:
        f = float(close)
    except (TypeError, ValueError):
        return f"suspended: non-numeric close {close!r}"
    if not math.isfinite(f) or f <= 0:
        return f"suspended: close {f!r} is not a tradable price"
    return None


def suspended(close, *, symbol=None, as_of=None) -> bool:
    """True when the close is missing/NaN (Qlib ``$close`` suspended rule).

    ``symbol``/``as_of`` (keyword-only, optional) are the H7 refusal ledger's
    identity for the untradable day. Purely observational: the verdict is the
    same either way, the row is written only when ``enable_refusal_ledger`` is
    on, and a ledger failure never reaches the caller.
    """
    reason = _suspension_reason(close)
    if reason is not None:
        _note_refusal("suspended", reason, symbol=symbol, as_of=as_of, close=close)
        return True
    return False


def limit_gate(change, threshold: float = 0.0, *, symbol=None, as_of=None) -> str | None:
    """Limit-up/down tradability gate from a day's pct change (fraction).

    ``change`` = today's move vs yesterday's close (0.10 = +10%).
    Returns ``"up"`` (limit-up: untradable to BUY) when change >= threshold,
    ``"down"`` (untradable to SELL) when change <= -threshold, else None.
    ``threshold <= 0`` disables the gate (None always).

    A non-None return is a REFUSAL and is recorded in the H7 refusal ledger
    (``symbol``/``as_of`` are its keyword-only, optional identity). Purely
    observational: the returned side is the same either way, the row is written
    only when ``enable_refusal_ledger`` is on, and a ledger failure never
    reaches the caller.
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
        side = "up"
    elif c <= -threshold:
        side = "down"
    else:
        return None
    _note_refusal(
        "limit_gate",
        f"limit-{side}: untradable to {'BUY' if side == 'up' else 'SELL'} "
        f"(change {c:+.2%} vs threshold {float(threshold):.2%})",
        symbol=symbol,
        as_of=as_of,
        change=c,
        threshold=float(threshold),
        side=side,
    )
    return side


def volume_gate(order_qty, day_volume, participation_cap: float = 0.2, *,
                symbol=None, as_of=None) -> int:
    """Cap an order's quantity at ``participation_cap`` of the day's volume.

    Returns the truncated integer quantity (>= 0); a day with no measurable
    volume yields 0 (no fill) when a cap is active.

    Truncating a non-empty order to zero shares is a REFUSAL and is recorded in
    the H7 refusal ledger (``symbol``/``as_of`` are its keyword-only, optional
    identity). Purely observational: the returned quantity is the same either
    way, the row is written only when ``enable_refusal_ledger`` is on, and a
    ledger failure never reaches the caller.
    """
    try:
        q = float(order_qty)
        v = float(day_volume)
        cap = float(participation_cap)
    except (TypeError, ValueError):
        return max(0, int(order_qty)) if order_qty is not None else 0
    if cap <= 0 or v <= 0:
        if cap > 0:
            if int(q) > 0:
                _note_refusal(
                    "volume_gate",
                    "participation cap active with no measurable day volume: "
                    "order truncated to 0 shares",
                    symbol=symbol, as_of=as_of, order_qty=q, day_volume=v,
                    participation_cap=cap,
                )
            return 0
        return max(0, int(q))
    capped = max(0, min(int(q), int(v * cap)))
    if capped == 0 and int(q) > 0:
        _note_refusal(
            "volume_gate",
            f"participation cap {cap:g} of day volume {v:g} truncates the order "
            "to 0 shares",
            symbol=symbol, as_of=as_of, order_qty=q, day_volume=v,
            participation_cap=cap,
        )
    return capped


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
        # Reads the state through the pure predicate: only ``suspended`` records
        # the refusal, so this reader cannot double-count the same day.
        if value is None or _suspension_reason(value) is not None:
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
    if _suspension_reason(close) is not None or _suspension_reason(prev_close) is not None:
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
