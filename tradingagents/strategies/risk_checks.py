"""Pre-trade risk checks: submission-rate throttling + per-symbol notional caps.

Deterministic, advisory pre-trade gates for the backtest / paper-execution
path, mirroring the kind of limits NautilusTrader's risk layer enforces
conceptually (``RiskEngineConfig`` rate throttles + ``max_notional_per_order``
in this checkout). They never touch the analysis graph - they bound what a
paper/backtest *would* submit, so a burst of orders or an oversized order
cannot slip past the risk budget silently.

Every function is pure and returns a bool verdict. No state leaks between
calls unless the caller persists the ``RateLimiter``.
"""

from __future__ import annotations

from collections import deque


class RateLimiter:
    """Rolling-window submission throttle.

    Allows at most ``max_count`` events within any trailing ``window_secs``.
    ``now`` is supplied by the caller (monotonic seconds) so the limiter is
    deterministic and clock-agnostic in tests.
    """

    def __init__(self, max_count: int, window_secs: float) -> None:
        self.max_count = max(1, int(max_count))
        self.window_secs = max(0.0, float(window_secs))
        self._times: deque[float] = deque()

    def allow(self, now: float) -> bool:
        """Record an event at ``now`` and return whether it is within budget."""
        cutoff = now - self.window_secs
        while self._times and self._times[0] < cutoff:
            self._times.popleft()
        if len(self._times) >= self.max_count:
            return False
        self._times.append(now)
        return True

    @property
    def count(self) -> int:
        return len(self._times)


def pre_trade_check(
    symbol: str,
    notional: float,
    symbol_notional: dict[str, float],
    max_notional: float | None = None,
    limiter: RateLimiter | None = None,
    now: float = 0.0,
) -> bool:
    """Evaluate whether a prospective order passes the pre-trade gates.

    Two checks, both advisory:
    * notional cap - the order's notional must be <= ``max_notional``, and
      the cumulative per-symbol notional (``symbol_notional`` + this order)
      must stay within ``max_notional`` when provided;
    * rate throttle - ``limiter.allow(now)`` must pass.

    Does NOT mutate ``symbol_notional`` on success - the caller records the
    committed notional separately so a denied order never counts toward the
    cap. Returns False when either gate blocks.
    """
    if notional is None or notional < 0:
        return False
    if max_notional is not None and max_notional > 0:
        if notional > max_notional:
            return False
        cumulative = symbol_notional.get(symbol, 0.0) + notional
        if cumulative > max_notional:
            return False
    return not (limiter is not None and not limiter.allow(now))


def notional(price: float, quantity: float) -> float:
    """Order notional (dollar value) = price * quantity; 0 on bad input."""
    try:
        return float(price) * float(quantity)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "RateLimiter",
    "pre_trade_check",
    "notional",
]
