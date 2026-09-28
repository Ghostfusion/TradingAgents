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
    tgt = target_level(entry, atr, atr_mult=target_mult)
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
                       trail_pct: float = 0.05,
                       atr_value: float | None = None,
                       atr_mult: float | None = None) -> dict:
    """Peak-trailing exit (Lean L4): exit when ``current`` has pulled back
    ``trail_pct`` below the highest value seen since entry.

    Gives acknowledgment to a position that ran +40% and gave back 30% — the
    fixed ATE/ATR rules never force such a giveback. Long-only. ``exit`` True
    (and a ``stop_px`` below current) means the peak-trail stop is struck.
    Returns all-``None``/``exit=False`` on unusable inputs — never fabricates.

    Regime-adaptive trailing (``atr_value`` + ``atr_mult``): when both are
    supplied (and positive), the stop distance is ``atr_mult * ATR`` instead
    of the static ``trail_pct`` — a high-beta name at 2x ATR > 5% gets a
    proportionate trailing band instead of being stopped out prematurely, and
    a defensive name at 0.4x ATR gets a tighter stop than the static 5%.
    A static 5% works poorly across regimes (premature exits on vol names,
    too loose on sleepers); the ATR form is the regime-adaptive alternative.

    Precedence (exit hierarchy, matches the framework): terminal risk
    (HWM / daily-loss / drawdown) > stop-loss > trailing stop > min-holding.
    The trailing stop only *ratchets upward* from its baseline; breakeven
    (contract.py) resets the *baseline*, never the other way around.
    """
    if entry is None or peak is None or current is None:
        return {"exit": False, "stop_px": None, "drawdown_from_peak": None}
    peak = float(peak)
    current = float(current)
    if peak <= 0:
        return {"exit": False, "stop_px": None, "drawdown_from_peak": None}
    # ATR-adaptive band when both supplied and positive; else static %.
    if atr_value is not None and atr_mult is not None and float(atr_value) > 0 and float(atr_mult) > 0:
        pct = abs(float(atr_value) * float(atr_mult) / peak)
    else:
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


#: The §101 exit precedence for a long. Terminal risk leads - the repo's own
#: hierarchy (``trailing_stop_exit``'s docstring: terminal risk > stop >
#: trailing > min-holding) - then the price levels, the structural/thesis
#: exits, the clock, and finally a negative expected value.
EXIT_PRECEDENCE = (
    "risk_gate",
    "stop",
    "trailing_stop",
    "target",
    "thesis_break",
    "time_exit",
    "expected_value",
)


def time_exit(
    days_held: int | None,
    max_holding_days: int | None,
    min_holding_days: int | None = None,
) -> dict:
    """Time-based exit (§58 of ``Strategies/entry_exit.md``).

    A position held past its horizon is exited; one still inside its minimum
    holding period is reported as not-yet-eligible, so a time exit can never
    fire before the minimum. ``exit`` is ``None`` - not ``False`` - when
    ``days_held`` or the horizon is unknown: an unmeasurable time exit is
    absent, never "no exit".
    """
    if days_held is None or max_holding_days is None:
        return {
            "exit": None,
            "days_held": days_held,
            "max_holding_days": max_holding_days,
            "min_elapsed": None,
            "reason": "days held or holding horizon unavailable",
        }
    held = int(days_held)
    horizon = int(max_holding_days)
    min_elapsed = None if min_holding_days is None else held >= int(min_holding_days)
    if held < horizon:
        return {
            "exit": False, "days_held": held, "max_holding_days": horizon,
            "min_elapsed": min_elapsed, "reason": f"held {held}d < horizon {horizon}d",
        }
    if min_elapsed is False:
        return {
            "exit": False, "days_held": held, "max_holding_days": horizon,
            "min_elapsed": False,
            "reason": (
                f"held {held}d past the {horizon}d horizon but still inside "
                f"the {int(min_holding_days)}d minimum"
            ),
        }
    return {
        "exit": True, "days_held": held, "max_holding_days": horizon,
        "min_elapsed": min_elapsed, "reason": f"held {held}d >= horizon {horizon}d",
    }


#: Which price to transact at when each price-level condition fires.
_PRICE_CONDITIONS = frozenset({"stop", "trailing_stop", "target"})


def exit_decision(
    *,
    close: float | None,
    stop: float | None = None,
    trailing_stop: float | None = None,
    target: float | None = None,
    thesis_break: bool | None = None,
    risk_gate: str | None = None,
    time_exit_fired: bool | None = None,
    expected_value: float | None = None,
) -> dict:
    """The §101 exit predicate for a long.

    Six independent exits, evaluated independently and reported in
    ``conditions``; the first to fire in ``EXIT_PRECEDENCE`` names the
    ``reason``. A condition that could not be evaluated is **absent** from
    ``conditions`` and shrinks ``coverage`` - it is never read as "no exit".
    With nothing decidable, ``exit`` is ``None`` rather than ``False``.

    ``exit_price`` is the level that fired for a price condition, otherwise
    the close (a non-price exit is taken at market). Flags only - this never
    blocks a decision by itself.
    """
    conditions: dict[str, bool] = {}
    if risk_gate is not None:
        conditions["risk_gate"] = str(risk_gate).strip().upper() == "REJECT"
    if close is not None and stop is not None:
        conditions["stop"] = float(close) <= float(stop)
    if close is not None and trailing_stop is not None:
        conditions["trailing_stop"] = float(close) <= float(trailing_stop)
    if close is not None and target is not None:
        conditions["target"] = float(close) >= float(target)
    if thesis_break is not None:
        conditions["thesis_break"] = bool(thesis_break)
    if time_exit_fired is not None:
        conditions["time_exit"] = bool(time_exit_fired)
    if expected_value is not None:
        conditions["expected_value"] = float(expected_value) < 0.0

    if not conditions:
        return {
            "exit": None,
            "reason": "no exit condition could be evaluated",
            "exit_price": None,
            "conditions": {},
            "coverage": 0,
        }

    reason = next((name for name in EXIT_PRECEDENCE if conditions.get(name)), None)
    levels = {"stop": stop, "trailing_stop": trailing_stop, "target": target}
    price = levels.get(reason) if reason in _PRICE_CONDITIONS else close
    return {
        "exit": reason is not None,
        "reason": reason or "no exit condition fired",
        "exit_price": float(price) if price is not None else None,
        "conditions": conditions,
        "coverage": len(conditions),
    }


__all__ = [
    "stop_to_breakeven", "stop_to_breakeven_r", "breakeven_after_confirmation",
    "target_level", "net_of_cost", "rebalance_due", "exit_check",
    "trailing_stop_exit", "max_giveback_exit", "time_exit", "exit_decision",
    "EXIT_PRECEDENCE",
]
