"""Execution price: §74-§78's cost buffer and the price you can realistically pay.

``Strategies/entry_exit.md`` §100 applies the execution cost *before* the hard
ceiling - ``P_entry,target = P_risk - ExecutionBuffer`` - and §102's
``LiquidityGate`` is the permission half. This module is the price half,
pure and deterministic: it prices the cost terms the caller measured and
reports the ones it did not.

Each term is a **fraction of price**. The repo's cost models return *price
units* (``liquidity_risk.volume_share_slippage`` / ``market_impact_slippage``
multiply by the price), so a caller converts by dividing by that price -
``book_risk``'s impact row does exactly this to land in return units. An absent
term shrinks ``coverage``; it is never defaulted to zero, because "not
measured" and "free" are different claims.

**Contract rule** (owner decision 2026-10-02): an execution cost may adjust an
executable price **only** when it is sourced from measured microstructure or
an explicitly validated cost model. With no measured term the field is
``NO_SOURCE`` - never an assumed zero, and never a config placeholder standing
in for a measurement. That is the deliberate seam a future cost model plugs
into: supply the term here when it is measured, leave it absent until then.
"""

from __future__ import annotations

import math

from tradingagents.strategies.entry_ceiling import usable_price_level

#: The §74-§78 cost terms, in declared order.
COST_SOURCES = ("spread", "impact", "slippage")


def _fraction(v) -> float | None:
    """A usable cost fraction in ``[0, 1)``, or ``None``.

    ``None`` means *absent*. A cost of exactly 1.0 would make the execution
    price zero, so it is rejected as unusable rather than accepted.
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 0.0 or f >= 1.0:
        return None
    return f


def execution_price(
    *,
    price,
    spread=None,
    impact=None,
    slippage=None,
    liquidity_status: str | None = None,
) -> dict:
    """The execution buffer and the price net of it.

    Args:
        price: the reference price the costs are charged against.
        spread / impact / slippage: per-share cost **fractions** of ``price``.
        liquidity_status: the caller's liquidity verdict (the price half never
            derives it - that is ``liquidity_risk.liquidity_verdict``).

    Returns:
        ``buffer`` / ``buffer_fraction`` / ``execution_price`` /
        ``liquidity_adjusted_entry_price`` (the §103 name for the same
        number) / ``basis`` / ``available_sources`` / ``missing_sources`` /
        ``coverage`` / ``coverage_ratio`` / ``liquidity_status`` / ``status``
        / ``reason``.

        With no price or no cost term the buffer is ``None`` and
        ``status`` is ``NO_SOURCE`` - never a zero-cost execution price,
        which would read as a free trade.
    """
    price_level = usable_price_level(price)
    supplied = {
        "spread": _fraction(spread),
        "impact": _fraction(impact),
        "slippage": _fraction(slippage),
    }
    present: list[tuple[str, float]] = []
    for term in COST_SOURCES:
        frac = supplied[term]
        if frac is not None:
            present.append((term, frac))
    missing = [k for k in COST_SOURCES if supplied[k] is None]

    if price_level is None or not present:
        return {
            "buffer": None,
            "buffer_fraction": None,
            "execution_price": None,
            "liquidity_adjusted_entry_price": None,
            "basis": {},
            "available_sources": [],
            "missing_sources": missing,
            "coverage": 0,
            "coverage_ratio": 0.0,
            "liquidity_status": liquidity_status,
            "status": "NO_SOURCE",
            "reason": (
                "no reference price" if price_level is None
                else "no execution cost term measured; a zero buffer is not assumed"
            ),
        }

    fraction = sum(frac for _, frac in present)
    buffer = price_level * fraction
    net = price_level - buffer
    return {
        "buffer": buffer,
        "buffer_fraction": fraction,
        "execution_price": net,
        "liquidity_adjusted_entry_price": net,
        "basis": dict(present),
        "available_sources": [k for k, _ in present],
        "missing_sources": missing,
        "coverage": len(present),
        "coverage_ratio": len(present) / len(COST_SOURCES),
        "liquidity_status": liquidity_status,
        "status": "OK",
        "reason": "",
    }


__all__ = ["COST_SOURCES", "execution_price"]
