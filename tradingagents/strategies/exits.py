"""V4 - value-style exit & cadence helpers.

Swing-scale discipline for the value overlay: stop-to-breakeven after one
ATR in your favor, ATR-based targets, cost-aware netting, monthly rebalance
cadence hint.
"""

from __future__ import annotations


def stop_to_breakeven(entry_price: float, atr: float, cushion_atr: float = 1.0) -> float:
    """Move the stop to entry + cushion*ATR once the trade is green enough."""
    return entry_price + max(0.0, float(cushion_atr)) * float(atr)


def target_level(close: float, atr: float, atr_mult: float = 4.0) -> float:
    """ATR-based profit target for longs."""
    return close + max(0.0, float(atr_mult)) * float(atr)


def net_of_cost(
    gross_return: float,
    cost_bps: float = 10.0,
    illiq: float | None = None,
    illiq_cost_mult: float = 1e5,
) -> float:
    """Net a per-trade cost (basis points) from a return.

    Item 3 (liquidity-aware costs): when ``illiq`` (Amihud ILLIQ, the
    screener's price-impact proxy) is provided, scale the cost up for
    illiquid names — real firms charge more to trade them. The default
    ``illiq_cost_mult`` maps an ILLIQ of ~1e-5 (a reasonable liquid large-cap)
    to roughly +1bps extra. ``cost_bps`` stays the base; None ``illiq`` keeps
    the original flat-cost behavior (backward compatible).
    """
    bps = float(cost_bps)
    if illiq is not None:
        bps += float(illiq) * float(illiq_cost_mult)
    return float(gross_return) - bps / 10000.0


def rebalance_due(days_since_last: int | None, interval_days: int = 30) -> bool:
    """Value rebalance cadence: due after the interval."""
    if days_since_last is None:
        return False
    return int(days_since_last) >= max(1, int(interval_days))


def exit_check(
    entry: float, close: float, atr: float, target_mult: float = 4.0, breakeven_cushion: float = 1.0
) -> dict:
    """Exit decision flags for a long: stop-break, target-hit, hence trade outcome."""
    be = stop_to_breakeven(entry, atr, cushion_atr=breakeven_cushion)
    tgt = target_level(close, atr, atr_mult=target_mult)
    return {
        "breakeven_stop": round(be, 4),
        "target": round(tgt, 4),
        "stop_hit": close < be,
        "target_hit": close >= tgt,
        "holding_action": "target" if close >= tgt else ("stop" if close < be else "hold"),
    }


__all__ = ["stop_to_breakeven", "target_level", "net_of_cost", "rebalance_due", "exit_check"]
