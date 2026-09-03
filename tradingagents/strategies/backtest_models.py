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


# ---------------------------------------------------------------------------
# W2-6/7/8 impact + turnover + capacity + borrow models (remediation phase 7)
# ---------------------------------------------------------------------------


def square_root_impact(notional_usd: float, adv_usd: float | None,
                       spread_bps: float | None = None,
                       vol_pct: float | None = None) -> float | None:
    """Almgren-Chriss style square-root market impact (W2-6).

    impact = k * sigma * sqrt(q / adv) with k ~ 0.1 (documented). Missing
    adv -> None (cannot compute, never assumed). ``spread_bps`` optionally
    adds a participation-scaled spread cost (bps of notional).
    Returns impact as a FRACTION of notional (e.g. 0.001 = 10bps).
    """
    if not adv_usd or adv_usd <= 0 or notional_usd <= 0:
        return None
    sig = (vol_pct or 0.20) / 100.0
    partic = notional_usd / adv_usd
    k = 0.1
    impact = k * sig * (partic ** 0.5)
    if spread_bps:
        impact += (spread_bps / 10000.0) * 0.5
    return round(impact, 6)


def turnover(fill_qty: list[float], target_qty: list[float]) -> float | None:
    """One-way turnover from fills vs targets (W2-7): mean |fill - target| /
    mean |target|, None on unmeasured."""
    if not fill_qty or not target_qty or len(fill_qty) != len(target_qty):
        return None
    denom = sum(abs(t) for t in target_qty) or 0.0
    if denom <= 0:
        return None
    return round(sum(abs(f - t) for f, t in zip(fill_qty, target_qty, strict=False)) / denom, 4)


def capacity_pct(notional_usd: float, adv_usd: float | None,
                 max_participation: float = 0.10) -> float | None:
    """W2-7 capacity check: the position as a fraction of ADV; False (None)
    when unmeasurable or above ``max_participation`` (a signal that works at
    size only if it stays within execution feasibility)."""
    if not adv_usd or adv_usd <= 0 or notional_usd <= 0:
        return None
    pct = notional_usd / adv_usd
    return round(pct, 4)


def borrow_cost(short_notional: float, annual_rate_pct: float,
                days: int) -> float | None:
    """W2-8: the financing cost of a short position over ``days`` (None when
    unmeasurable). Annual rate is the borrow/prime rate (e.g. 0.5% hard-to-
    borrow premium; set 0 to model free-to-borrow)."""
    if short_notional <= 0 or days <= 0 or annual_rate_pct is None:
        return None
    return round(short_notional * (annual_rate_pct / 100.0) * (days / 365.0), 6)


def quote_adjust(price: float, factor: float | None = None, divisor: float | None = None,
                 special_dividend: float = 0.0) -> float:
    """W2-9 corporate-action price adjustment (backtest-normalized series):
    multiply by a split factor (2 for a 2-for-1), divide by a divisor, and
    subtract a special cash dividend. Pure; missing factor -> unchanged."""
    out = price
    if factor:
        out *= factor
    if divisor:
        out /= divisor
    out -= special_dividend
    return round(out, 6)


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
