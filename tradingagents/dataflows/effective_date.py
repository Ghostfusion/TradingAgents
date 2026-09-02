"""Effective trading-date helpers (DSA research §3.6, pillar 10-11).

Port of daily_stock_analysis's `get_effective_trading_date` + all-closed
skip, scoped to the fork's regions. Deterministic + fail-open:

- ``effective_trading_date(region, ref_utc=None, force_run=False)`` — the
  date a decision/report binds to: if ``ref_utc`` is a non-trading day or
  before that market's close, the PREVIOUS session is used; after close the
  CURRENT session is used; anything unmeasurable fails open to the
  market-local date.
- ``should_skip_all_closed(regions, ref_utc=None)`` — all configured
  regions closed -> True (the nightly skips the run with a log; the caller
  exposes ``--force-run``).

The reference calendar is provided (pure; no exchange-calendars dependency):
a minimal known-session + close-time table. Region defaults: US (ET close
16:00), CA (same zone), EU (multiple zones - approximated CET close 17:30),
JP/KR (JST/KST close 15:30), TW (close 13:30). Fail-open means missing
calendar data NEVER blocks a run (matches DSA's is_market_open fail-open).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

UTC = timezone.utc

# Market close times by region (local time). Approximate but deterministic.
_REGION_CLOSE = {
    "US": (time(16, 0), timezone(timedelta(hours=-5))),  # ET (standard)
    "CA": (time(16, 0), timezone(timedelta(hours=-5))),
    "EU": (time(17, 30), timezone(timedelta(hours=1))),  # CET approximation
    "JP": (time(15, 30), timezone(timedelta(hours=9))),
    "KR": (time(15, 30), timezone(timedelta(hours=9))),
    "TW": (time(13, 30), timezone(timedelta(hours=8))),
}

# Minimal known non-trading days (weekends are handled by weekday(); this is
# the override set the caller may supply). None -> weekends only.
_DEFAULT_NON_TRADING = None  # (market-local date strings, e.g. "2026-07-03")


def _market_dt(ref_utc: datetime, region: str) -> datetime | None:
    try:
        _, tz = _REGION_CLOSE.get(str(region).upper(), _REGION_CLOSE["US"])
        return ref_utc.astimezone(tz)
    except (ValueError, OverflowError):
        return None


def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # Sat=5, Sun=6


def _previous_business_day(dt: datetime, non_trading: set | None) -> datetime:
    d = dt.date() - timedelta(days=1)
    while _is_weekend(datetime.combine(d, time(0))) or (non_trading and d.isoformat() in non_trading):
        d -= timedelta(days=1)
    return datetime.combine(d, time(0), dt.tzinfo)


def effective_trading_date(region: str = "US", ref_utc: datetime | None = None,
                           force_run: bool = False,
                           non_trading_days: set | None = _DEFAULT_NON_TRADING) -> str:
    """The effective trading date (YYYY-MM-DD) a decision/report binds to.

    Rule (DSA): non-trading day -> previous session; trading day BEFORE the
    market close -> previous session; after close -> current session.
    ``force_run`` returns the ref (market-local) date regardless — the
    documented escape hatch. Fail-open: anything unmeasurable returns the
    market-local date (never blocks).
    """
    ref = ref_utc or datetime.now(UTC)
    region = str(region).upper()
    mdt = _market_dt(ref, region)
    if mdt is None or force_run:
        mdt = ref.astimezone(_REGION_CLOSE.get(region, _REGION_CLOSE["US"])[1])
        return mdt.strftime("%Y-%m-%d")
    if _is_weekend(mdt) or (non_trading_days and mdt.date().isoformat() in non_trading_days):
        return _previous_business_day(mdt, non_trading_days).strftime("%Y-%m-%d")
    close_time, _ = _REGION_CLOSE[region]
    if mdt.time() < close_time:
        return _previous_business_day(mdt, non_trading_days).strftime("%Y-%m-%d")
    return mdt.strftime("%Y-%m-%d")


def should_skip_all_closed(regions: list[str], ref_utc: datetime | None = None,
                           non_trading_days: set | None = _DEFAULT_NON_TRADING) -> bool:
    """True when EVERY region's effective date is a previous-session date
    (i.e. all are currently closed/non-trading) — the all-closed skip."""
    ref = ref_utc or datetime.now(UTC)
    if not regions:
        return False
    for region in regions:
        if region.upper() not in _REGION_CLOSE:
            return False  # unknown region -> fail-open, never block
        mdt = _market_dt(ref, region)
        if mdt is None:
            return False  # fail-open: never block on missing calendar
        if _is_weekend(mdt) or (non_trading_days and mdt.date().isoformat() in non_trading_days):
            continue  # closed -> candidate for skip
        close_time, _ = _REGION_CLOSE[region.upper()]
        if mdt.time() >= close_time:
            return False  # at least one market is open (after close = makes the date)
    return True


__all__ = [
    "effective_trading_date",
    "should_skip_all_closed",
    "_REGION_CLOSE",
]

