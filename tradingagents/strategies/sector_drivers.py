"""Each SPDR sector's macro driver, as a MAPPING rather than a gate.

The sector-dip playbook's third check is "has the macro catalyst that drove the
sector to leadership changed?". The engine already reads every input that
question needs and reads them live (FRED: DGS10, T10Y2Y, NAPM, HY OAS, the broad
dollar, WTI, copper) - what was missing is the binding between a sector and the
series that actually drives it, so a reader gets numbers and no mapping.

This module is that binding, plus a pure read of the driver's own change:

* :data:`SECTOR_DRIVERS` - one documented driver and sign per SPDR group.
* :func:`_driver_change_read` - level and 1m/3m change of ONE series.
* :func:`sector_driver_read` - the sector's mapped driver and whether its move
  HELPS that sector, with the mapping's reason travelling beside it.

ADVISORY and REPORTED ONLY: nothing here gates a rank, a candidate or a size.
The driver table is a conventional reading of the sector literature (long-duration
growth, utilities and REITs are discount-rate sensitive, energy is oil, materials
are copper, discretionary is credit-sensitive, banks and industrials want a
steeper curve), NOT a fitted coefficient - so ``favourable`` describes the sign
of the move against that convention and never claims a measured edge.

Windows are counted in OBSERVATIONS, not calendar days, because FRED series
differ in frequency (DGS10/T10Y2Y/WTI/the dollar are daily; copper and
industrial production are monthly): the read reports the observation count it
used and the caller states it, so a monthly series is never described as a
21-day move - and a monthly series simply reads n/a at these windows.
"""

from __future__ import annotations

#: Conventional 1-month and 3-month windows, in observations.
DRIVER_ONE_MONTH = 21
DRIVER_THREE_MONTHS = 63

#: Which driver moves with which sector, and the sign that HELPS it.
#: ``(fred_alias, direction)``: direction ``+1`` means "up is good for the
#: sector", ``-1`` means "up is bad for it". Aliases are FRED's own (the table in
#: ``dataflows/fred.py``); anything absent from this table is left unmapped on
#: purpose - the nearest available series is not the same thing as the driver.
SECTOR_DRIVERS: dict[str, tuple[str, int]] = {
    "XLK": ("10y_treasury", -1),   # long-duration growth: rates up, multiples down
    "XLU": ("10y_treasury", -1),   # bond proxy: the discount rate IS the story
    "XLRE": ("10y_treasury", -1),  # levered, yield-shaped
    "XLC": ("10y_treasury", -1),   # same duration profile as tech
    "XLF": ("10y_2y_spread", +1),  # a steeper curve widens net interest margin
    "XLI": ("industrial_production", +1),  # capex/industrial cycle. NOT the
                                   # "pmi" alias: FRED's NAPM is discontinued
                                   # and returns zero observations (measured
                                   # 2026-09-25), so the mapping would read n/a
                                   # forever. (The alias itself is left alone -
                                   # it is an owner-facing name; see the report.)
    "XLE": ("wti", +1),            # the sector IS the commodity
    "XLB": ("copper", +1),         # global industrial demand in one series
    "XLY": ("hy_oas", -1),         # discretionary spending is credit-sensitive
}

#: Why a sector has no single mapped driver (reported, never silently skipped).
UNMAPPED_REASONS: dict[str, str] = {
    "XLV": "defensive demand and policy/approval risk, not one macro series",
    "XLP": "defensive demand; the dollar is a second-order effect at best",
}

#: The aliases this table may name, so a typo cannot silently become "unmapped".
KNOWN_DRIVERS: frozenset = frozenset(
    {
        "10y_treasury",
        "10y_2y_spread",
        "pmi",  # listed because the alias exists; it resolves to nothing (see above)
        "industrial_production",
        "hy_oas",
        "dollar_index",
        "wti",
        "copper",
    }
)


def _driver_change_read(
    series: list,
    *,
    one_month: int = DRIVER_ONE_MONTH,
    three_months: int = DRIVER_THREE_MONTHS,
) -> dict:
    """Level and 1m/3m change of one macro series (oldest -> newest).

    ``None`` - never a fabricated number - whenever the series is too short for
    the window asked for: a change over 21 observations needs 22. The
    observation count travels with the reading so a monthly series is not
    described as a 21-day move.
    """
    vals = [float(v) for v in (series or []) if v is not None]
    out = {
        "observations": len(vals),
        "one_month": one_month,
        "three_months": three_months,
    }
    if not vals:
        return {**out, "level": None, "change_1m": None, "change_3m": None}
    level = vals[-1]
    chg_1m = (
        round(level - vals[-(one_month + 1)], 4)
        if one_month and len(vals) > one_month
        else None
    )
    chg_3m = (
        round(level - vals[-(three_months + 1)], 4)
        if three_months and len(vals) > three_months
        else None
    )
    return {**out, "level": round(level, 4), "change_1m": chg_1m, "change_3m": chg_3m}


def sector_driver_read(
    sector: str,
    series_by_driver: dict,
    *,
    one_month: int = DRIVER_ONE_MONTH,
    three_months: int = DRIVER_THREE_MONTHS,
) -> dict:
    """The sector's mapped macro driver, its change, and whether that move helps.

    ``series_by_driver`` is ``{fred_alias: [values oldest -> newest]}`` - the
    caller fetches each DISTINCT alias once (the mapping is many-to-one) and
    hands the SAME series to every sector that maps to it.

    ``favourable_1m``/``favourable_3m`` are ``True`` when the move's sign matches
    the mapping's direction, ``False`` when it opposes it and ``None`` when the
    change is unmeasured - never ``False`` for a series nobody read. ``basis``
    names the mapping and the observation count, which is what a reader needs to
    argue with it.
    """
    sym = str(sector or "").strip().upper()
    mapping = SECTOR_DRIVERS.get(sym)
    unmapped_reason = UNMAPPED_REASONS.get(sym)
    out = {
        "sector": sym,
        "driver": mapping[0] if mapping else None,
        "direction": mapping[1] if mapping else None,
        "mapped": mapping is not None,
        "unmapped_reason": None if mapping else (unmapped_reason or "no mapping"),
        "level": None,
        "change_1m": None,
        "change_3m": None,
        "favourable_1m": None,
        "favourable_3m": None,
        "observations": 0,
        "basis": None,
    }
    if mapping is None:
        out["basis"] = (
            f"no macro driver mapped for {sym}: {out['unmapped_reason']}"
        )
        return out
    driver, direction = mapping
    read = _driver_change_read(
        (series_by_driver or {}).get(driver) or [],
        one_month=one_month,
        three_months=three_months,
    )
    out.update(
        {
            "level": read["level"],
            "change_1m": read["change_1m"],
            "change_3m": read["change_3m"],
            "observations": read["observations"],
        }
    )

    def _helps(change: float | None) -> bool | None:
        """Does the move's SIGN match the mapping's direction?

        ``None`` when the change is unmeasured, never ``False`` - an unread
        series has not failed a sign test. A zero change reads ``False``: it
        fails the sign test, which is what "favourable" asks.
        """
        if change is None:
            return None
        if change == 0:
            # A flat driver helps nothing: without this, `(change > 0) ==
            # (direction > 0)` reads a zero as FAVOURABLE for every -1 sector,
            # because both sides are False.
            return False
        return (change > 0) == (direction > 0)

    out["favourable_1m"] = _helps(read["change_1m"])
    out["favourable_3m"] = _helps(read["change_3m"])
    out["basis"] = (
        f"{driver}: {read['observations']} observation(s) "
        f"(1m={one_month}, 3m={three_months}; FRED frequency varies by series), "
        f"direction {'up helps' if direction > 0 else 'up hurts'} {sym}"
    )
    return out


def driver_aliases() -> tuple:
    """The distinct FRED aliases the mapping needs - fetched once per run."""
    return tuple(sorted({alias for alias, _ in SECTOR_DRIVERS.values()}))


__all__ = [
    "DRIVER_ONE_MONTH",
    "DRIVER_THREE_MONTHS",
    "KNOWN_DRIVERS",
    "SECTOR_DRIVERS",
    "UNMAPPED_REASONS",
    "driver_aliases",
    "sector_driver_read",
]
