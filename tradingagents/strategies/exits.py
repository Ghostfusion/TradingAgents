"""V4 - value-style exit & cadence helpers.

Swing-scale discipline for the value overlay: stop-to-breakeven after one
ATR in your favor, ATR-based targets, cost-aware netting, monthly rebalance
cadence hint.
"""

from __future__ import annotations


def stop_to_breakeven(entry_price: float, atr: float, cushion_atr: float = 1.0) -> float:
    """Move the stop to entry + cushion*ATR once the trade is green enough."""
    return entry_price + max(0.0, float(cushion_atr)) * float(atr)


def stop_to_breakeven_r(entry_price: float, stop_price: float, rr: float = 1.0) -> float:
    """Return the price trigger at which the stop should be moved to
    break-even: entry + rr x R, where R = entry - stop (the per-share risk).
    Mirrors the web's "move to BE after ~1R-1.5R in favor".
    """
    risk = float(entry_price) - float(stop_price)
    if risk <= 0:
        return float(entry_price)
    return float(entry_price) + float(rr) * risk


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




def breakeven_after_confirmation(
    entry_price: float,
    stop_price: float | None,
    trigger: str = "structure",
    higher_low: float | None = None,
    rr: float = 1.0,
    cushion_atr: float = 1.0,
    atr: float | None = None,
) -> dict:
    """Breakeven stop price per the configured trigger (B3, advisory).

    Practice says: move to BE only AFTER confirmation, or ordinary pullbacks
    stop winners early. Triggers:
      'atr'       - entry + cushion*ATR (the legacy fixed-cushion rule).
      'r'         - entry + rr x R, where R = entry - stop (need stop_price).
      'structure' - the LATER of (higher_low price) and (rr x R), i.e. the
                    more conservative confirmation. Requires stop_price; falls
                    back to 'atr' when R is unknown.
    Returns ``{price, trigger, source}``; ``price`` None when unusable.
    """
    t = (trigger or "structure").strip().lower()
    risk = None
    if stop_price is not None and float(stop_price) < float(entry_price):
        risk = float(entry_price) - float(stop_price)
    if t == "r" or (t == "structure" and risk is not None):
        r_price = float(entry_price) + float(rr) * risk if risk and risk > 0 else None
        if t == "r":
            return {"price": r_price, "trigger": "r", "source": f"entry + {rr:g}R"}
        if r_price is not None and higher_low is not None:
            return {"price": max(r_price, float(higher_low)), "trigger": "structure",
                    "source": "max(r x R, higher-low)"}
        if higher_low is not None:
            return {"price": float(higher_low), "trigger": "structure", "source": "higher-low"}
        if r_price is not None:
            return {"price": r_price, "trigger": "structure", "source": "r x R (no higher-low)"}
    # 'atr' or fallback when R is unknowable
    if atr is not None and atr > 0:
        return {"price": float(entry_price) + max(0.0, float(cushion_atr)) * float(atr),
                "trigger": "atr", "source": "entry + cushion x ATR"}
    return {"price": None, "trigger": t, "source": "insufficient inputs"}


def trailing_stop_exit(entry: float, peak: float, current: float,
                       trail_pct: float = 0.05) -> dict:
    """Peak-trailing exit (Lean L4): exit when ``current`` has pulled back
    ``trail_pct`` below the highest value seen since entry.

    Gives acknowledgment to a position that ran +40% and gave back 30% — the
    fixed ATE/ATR rules never force such a giveback. Long-only. ``exit`` True
    (and a ``stop_px`` below current) means the peak-trail stop is struck.
    Returns all-``None``/``exit=False`` on unusable inputs — never fabricates.
    """
    if entry is None or peak is None or current is None:
        return {"exit": False, "stop_px": None, "drawdown_from_peak": None}
    peak = float(peak)
    current = float(current)
    if peak <= 0:
        return {"exit": False, "stop_px": None, "drawdown_from_peak": None}
    pct = abs(float(trail_pct))
    dd = current / peak - 1.0
    return {
        "exit": dd < -pct,
        "stop_px": peak * (1.0 - pct),
        "drawdown_from_peak": dd,
    }


def max_giveback_exit(entry: float, peak: float, current: float,
                      giveback_pct: float = 0.30) -> dict:
    """Margin give-back stop (Lean L4 commit): a position that ran well but
    has surrendered a fraction of its best peak return is exited. Computes the
    remaining unrealized vs the peak gain; exits when ``<= giveback_pct`` of
    the best peak gain is left (drawdown-from-peak crosses the giveback band).
    Long-only; None on unusable inputs.
    """
    if entry is None or peak is None or current is None or float(entry) <= 0:
        return {"exit": False, "remaining_gain_pct": None, "stop_px": None}
    entry = float(entry)
    peak = float(peak)
    current = float(current)
    peak_gain = peak / entry - 1.0
    if peak_gain <= 0:
        return {"exit": False, "remaining_gain_pct": 0.0, "stop_px": None}
    remaining = current / entry - 1.0
    pct = abs(float(giveback_pct))
    keep = peak_gain * (1.0 - pct)
    return {
        "exit": remaining < keep,
        "remaining_gain_pct": remaining,
        "stop_px": entry * (1.0 + keep),
    }


__all__ = [
    "stop_to_breakeven", "stop_to_breakeven_r", "breakeven_after_confirmation",
    "target_level", "net_of_cost", "rebalance_due", "exit_check",
    "trailing_stop_exit", "max_giveback_exit",
]
