"""Risk-adjusted entry: §68's position-size-adjusted maximum entry.

For a fixed stop, a higher entry means a wider per-share risk. Past some
fraction of the entry the position can no longer be sized to a sane risk
budget, so there is a *price ceiling* implied by the risk rule itself.
Solving ``(E - S) / E <= f`` for ``E``:

    E_max = S / (1 - f)

that is ``P_risk,max`` - the highest entry at which the stop is still within
``f`` of the entry.

The permission half is separate and is reported as a **status**, never folded
into the price: a name whose measured CVaR already exceeds the book's budget
cannot be entered at any price. That was the binding constraint on the AMD
run (name CVaR 9.00% vs a 3.00% budget), and a price would misrepresent it.

Pure and deterministic. Advisory.
"""

from __future__ import annotations

import math

from tradingagents.strategies.entry_ceiling import usable_price_level

#: The CVaR permission statuses (§87/§88's RiskGate half, as a string).
CVAR_STATUSES = ("OK", "OVER_BUDGET", "NO_SOURCE")


def _fraction(v) -> float | None:
    """A usable fraction in ``[0, 1)``, or ``None``. ``None`` means absent."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 0.0 or f >= 1.0:
        return None
    return f


def risk_adjusted_entry(
    *,
    stop=None,
    max_stop_fraction=None,
    name_cvar=None,
    cvar_budget=None,
) -> dict:
    """§68's maximum entry from the stop-distance rule, plus the CVaR status.

    Args:
        stop: the invalidation price (the tranche's unified stop).
        max_stop_fraction: the largest per-share risk, as a fraction of the
            entry, that the rule will still size.
        name_cvar: the name's measured CVaR, as a positive loss fraction.
        cvar_budget: the book's CVaR budget for one name.

    Returns:
        ``value`` (= ``stop / (1 - max_stop_fraction)``), ``stop_fraction``,
        ``cvar_status``, ``status`` and ``reason``. ``value`` is ``None``
        when either input is unusable - never a fallback price, and never a
        position size standing in for a price.
    """
    stop_level = usable_price_level(stop)
    fraction = _fraction(max_stop_fraction)

    cvar = _fraction(name_cvar)
    budget = _fraction(cvar_budget)
    if cvar is None or budget is None:
        cvar_status = "NO_SOURCE"
    else:
        cvar_status = "OK" if cvar <= budget else "OVER_BUDGET"

    if stop_level is None or fraction is None:
        return {
            "value": None,
            "stop_fraction": None,
            "cvar_status": cvar_status,
            "status": "NO_SOURCE",
            "reason": (
                "stop unavailable" if stop_level is None
                else "max stop fraction unavailable"
            ),
        }

    return {
        "value": stop_level / (1.0 - fraction),
        "stop_fraction": fraction,
        "cvar_status": cvar_status,
        "status": "OK",
        "reason": "",
    }


__all__ = ["CVAR_STATUSES", "risk_adjusted_entry"]
