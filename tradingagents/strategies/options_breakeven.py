"""Option-position breakeven & PMCC discipline reads (advisory).

Computed reads for an option position — most commonly the Poor Man's
Covered Call (PMCC): a long deep-ITM LEAPS call (the stock substitute) with
short OTM calls sold above it (time-value harvest). Everything here is pure
math on caller-supplied position parameters, None-safe throughout: a missing
input makes that field n/a, never fabricated. Advisory only — no execution,
no options trading mandate change.

Breakeven = long strike + long premium paid per share (the cost basis of
the long leg if held to expiry). The short-call floor rule (from the AVGO
PMCC sample): the short strike must exceed that breakeven.
"""

from __future__ import annotations


def pmcc_breakeven(long_strike: float | None, long_premium: float | None) -> float | None:
    """Cost basis of a long call if held to expiry: strike + premium paid."""
    if long_strike is None or long_premium is None:
        return None
    if long_strike < 0 or long_premium < 0:
        return None
    return round(long_strike + long_premium, 2)


def short_call_discipline(
    short_strike: float | None, breakeven: float | None
) -> dict:
    """Short-call floor rule: selling strike must be ABOVE the breakeven.

    Returns ``{ok, breakeven, cushion}`` — cushion = short_strike - breakeven
    (how far the sold call can be tested before the position turns negative).
    Any missing input -> ``{ok: None, ...}``.
    """
    if short_strike is None or breakeven is None:
        return {"ok": None, "breakeven": breakeven, "cushion": None}
    return {
        "ok": short_strike > breakeven,
        "breakeven": breakeven,
        "cushion": round(short_strike - breakeven, 2),
    }


def long_leg_time_split(
    spot: float | None, long_strike: float | None, long_premium: float | None
) -> dict:
    """Split the long-leg premium into intrinsic vs extrinsic (time) value.

    A deep-ITM LEAPS should be mostly intrinsic: low time premium means low
    daily theta bleed on the long leg. Missing inputs -> ``{..: None}``.
    """
    if spot is None or long_strike is None or long_premium is None:
        return {
            "intrinsic": None,
            "extrinsic": None,
            "intrinsic_pct": None,
            "extrinsic_pct": None,
            "itm": None,
        }
    intrinsic = max(spot - long_strike, 0.0)
    extrinsic = max(long_premium - intrinsic, 0.0)
    return {
        "intrinsic": round(intrinsic, 2),
        "extrinsic": round(extrinsic, 2),
        "intrinsic_pct": round(100.0 * intrinsic / long_premium, 1) if long_premium else None,
        "extrinsic_pct": round(100.0 * extrinsic / long_premium, 1) if long_premium else None,
        "itm": spot > long_strike,
    }


def delta_profile(delta: float | None) -> str | None:
    """Advisory delta band (PMCC sample conventions).

    Long LEAPS: 0.75-0.85 deep-ITM (captures most of the upside, low time
    premium). Short calls: 0.20-0.30 OTM. Returns a one-line advisory or None.
    """
    if delta is None:
        return None
    if delta >= 0.70:
        return "deep-ITM long leg (0.75-0.85): minimal time premium, captures most upside"
    if delta >= 0.35:
        return "mid-delta: more time premium on the long leg; raise delta toward 0.75-0.85 to reduce bleed"
    if delta >= 0.20:
        return "low-delta short call (0.20-0.30): preferred OTM rent strike"
    return "very-low delta: far OTM / misses most upside — verify the strike is above breakeven"


def theta_zone(days_to_expiry: float | None) -> str | None:
    """Advisory theta window for a sold call (time-value harvest).

    30-45 days is the accelerated-decay window (the PMCC sample's rent
    cadence); shorter gives premium quickly but near-term gamma risk;
    longer collects more premium but decays slower.
    """
    if days_to_expiry is None:
        return None
    if 30.0 <= days_to_expiry <= 45.0:
        return "30-45d rent window: theta accelerating, the sample's preferred sell cadence"
    if days_to_expiry < 30.0:
        return "under 30d: quick premium but near-term gamma/assignment risk rises"
    return "over 45d: slower decay; more premium collected but capital tied longer"


def catalyst_window(days_to_catalyst: float | None, window: float = 7.0) -> dict:
    """Earnings/catalyst imminence warning for the sold call.

    The sample rule: never hold a low-strike short call into a catalyst.
    ``days_to_catalyst`` of None -> ``{"imminent": None, "note": None}``.
    """
    if days_to_catalyst is None:
        return {"imminent": None, "note": None}
    imminent = days_to_catalyst <= window
    return {
        "imminent": imminent,
        "note": (
            f"catalyst in {days_to_catalyst:.0f}d — avoid holding a low-strike "
            "short call through it (gap/pulse risk)"
            if imminent else
            f"catalyst ~{days_to_catalyst:.0f}d out — outside the risk window"
        ),
    }


def pmcc_read(
    long_strike: float | None,
    long_premium: float | None,
    *,
    short_strike: float | None = None,
    spot: float | None = None,
    short_ttm_days: float | None = None,
    delta: float | None = None,
    days_to_earnings: float | None = None,
    days_to_ex_div: float | None = None,
) -> dict:
    """Combined advisory read for an option position (PMCC-style).

    None-safe: any missing input renders that field n/a (never fabricated).
    """
    breakeven = pmcc_breakeven(long_strike, long_premium)
    discipline = short_call_discipline(short_strike, breakeven)
    split = long_leg_time_split(spot, long_strike, long_premium)
    ex_div = (
        {
            "days_to_ex_div": days_to_ex_div,
            "note": (
                f"ex-div in {days_to_ex_div:.0f}d — if the short call is ITM "
                "with time value below the dividend, close/roll before the ex-div date"
                if days_to_ex_div <= 3.0 else
                f"ex-div ~{days_to_ex_div:.0f}d out"
            ),
        }
        if days_to_ex_div is not None else {"days_to_ex_div": None, "note": None}
    )
    return {
        "long_breakeven": breakeven,
        "short_discipline": discipline,
        "long_leg_split": split,
        "delta_profile": delta_profile(delta),
        "short_theta_zone": theta_zone(short_ttm_days),
        "earnings_window": catalyst_window(days_to_earnings),
        "assignment": ex_div,
        "inputs": {
            "long_strike": long_strike,
            "long_premium": long_premium,
            "short_strike": short_strike,
            "spot": spot,
            "short_ttm_days": short_ttm_days,
            "delta": delta,
            "days_to_earnings": days_to_earnings,
            "days_to_ex_div": days_to_ex_div,
        },
    }


__all__ = [
    "pmcc_breakeven",
    "short_call_discipline",
    "long_leg_time_split",
    "delta_profile",
    "theta_zone",
    "catalyst_window",
    "pmcc_read",
]
