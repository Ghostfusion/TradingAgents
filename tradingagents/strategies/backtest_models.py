"""Fee, slippage and fill-probability models for the backtest harness.

Cost realism extracted as pure functions so the ``MatchingEngine`` stays
numeric and composable. Mirrors NautilusTrader's ``FixedFeeModel`` /
``MakerTakerFeeModel`` (fee selected by maker/taker liquidity) and
``DefaultFillModel`` (probability of an adverse tick / a limit filling).

Each of these eventually feeds ``cost_fn`` / ``slippage_ticks`` on the
backtest engine; every function returns a plain float or ``None`` per the
no-fabrication contract.
"""

from __future__ import annotations


def fixed_fee(notional: float, fee_bps: float) -> float:
    """Flat commission = notional * fee_bps / 10000. Non-negative."""
    try:
        n = float(notional)
        b = float(fee_bps)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, n * b / 10_000.0)


def maker_taker_fee(notional: float, maker_bps: float, taker_bps: float,
                    liquidity: str = "taker") -> float:
    """Commission selected by liquidity side (Nautilus's MakerTaker model).

    ``liquidity`` is ``"maker"`` or ``"taker"``; a maker (passive) fill is
    usually cheaper (or a rebate, here floored at 0). Non-negative result.
    """
    bps = maker_bps if liquidity == "maker" else taker_bps
    return fixed_fee(notional, bps)


def slip_price(price: float, tick: float, fill_model: str = "none") -> float:
    """Adverse-tick slippage: buy fills higher by ``tick``, sell fills lower.

    ``fill_model`` = ``"none"`` (no slippage), ``"fixed"`` (always one tick) or
    ``"probabilistic"`` (always one tick - kept deterministic; a probabilistic
    branch would need an RNG and violate reproducibility). Returns the slipped
    price; 0-gated on degenerate tick/price.
    """
    try:
        px = float(price)
        t = float(tick)
    except (TypeError, ValueError):
        return price
    if fill_model == "none" or t <= 0:
        return px
    return px + t  # the engine applies direction (buy/sell) via slippage_ticks


def make_cost_fn(fee_bps: float = 0.0, maker_bps: float | None = None,
                 taker_bps: float | None = None):
    """Return a ``cost_fn(notional, side)`` for the MatchingEngine.

    Uses maker/taker when both are supplied, else a flat fixed fee. The side
     argument is accepted for signature compatibility with the engine; maker/
    taker selection by fill liquidity is opted-in per order by the caller via
    a more-specific wrapper - here we return the flat or taker fee.
    """
    if maker_bps is not None and taker_bps is not None:
        return lambda notional, side: maker_taker_fee(notional, maker_bps, taker_bps, "taker")
    return lambda notional, side: fixed_fee(notional, fee_bps)


def limit_fill_probability(distance_to_limit_pct: float, base: float = 0.5) -> float:
    """Adverse-tick probability for a limit resting in the book.

    ``distance_to_limit_pct`` is how far price is from the limit as a fraction
    (0 = touching, =1 a full move away). Returns base probability scaled down
    as distance grows - a heuristic fill-probability, bounded [0, 1], not a
    gated decision.
    """
    try:
        d = abs(float(distance_to_limit_pct))
    except (TypeError, ValueError):
        return base
    return max(0.0, min(1.0, base * max(0.0, 1.0 - d)))


__all__ = [
    "fixed_fee",
    "maker_taker_fee",
    "slip_price",
    "make_cost_fn",
    "limit_fill_probability",
]
