"""Shared look-ahead-safe date-window filtering for dated content.

News, StockTwits, and Reddit all pull recent items that must be trimmed to the
analysis window so a historical/backtest run never sees content published after
its as-of date. Centralizing the rule keeps every source consistent (#1126,
#1220): every timestamp is normalized to UTC, the upper bound is exclusive at
midnight after ``end`` (so an item stamped exactly then can't leak), and an
undated item is kept only when the window reaches the present (a live run), since
in a backtest we can't prove it isn't future.
"""

from __future__ import annotations

import contextvars
from datetime import datetime, timedelta, timezone

# The run's as-of date, published by the graph at run start and read by the
# dated agent tool leaves so a model-supplied date can never reach past it.
# Run-scoped, not global state: each thread (and each concurrent run) gets its
# own value, and an unset/empty value means "no run date known" - the clamps
# below are then no-ops, so direct tool calls in tests and live runs behave
# exactly as they did before the clamp existed.
_RUN_TRADE_DATE: contextvars.ContextVar[str] = contextvars.ContextVar(
    "run_trade_date", default=""
)


def set_run_trade_date(trade_date: str | None) -> None:
    """Publish the current run's ``trade_date`` for the dated tool leaves.

    Empty/``None`` clears it to the no-op default. Called once per run from the
    graph's pre-graph setup; the value is thread-local via :mod:`contextvars`.
    """
    _RUN_TRADE_DATE.set(str(trade_date) if trade_date else "")


def get_run_trade_date() -> str:
    """The current run's ``trade_date`` as ``YYYY-MM-DD``, or ``""`` if unset.

    The dated tool leaves call this and pass it to :func:`as_of` /
    :func:`as_of_window`; an empty result makes those clamps no-ops.
    """
    return _RUN_TRADE_DATE.get()


# The run's wall-clock instant, published by the graph at run start beside the
# trade date. Left UNSET by default ON PURPOSE: an unset clock means "no live
# session known", so every offline call, test and historical run reads exactly
# as it did before the clock existed - the same no-op defaulting as the date,
# and the reason the volume leaves cannot be adjusted by the time of day a
# process happens to run at.
_RUN_CLOCK: contextvars.ContextVar[datetime | None] = contextvars.ContextVar(
    "run_clock", default=None
)


def set_run_clock(now: datetime | None) -> None:
    """Publish the run's wall-clock instant (aware) for the session leaves.

    The instant must be in EXCHANGE time (ET): the readers take its wall clock
    as ET, so a caller that only has the machine's zone converts first
    (``market_session.to_exchange_time``). Called once per run from the graph's
    pre-graph setup, beside :func:`set_run_trade_date`. ``None`` clears it to the
    no-op default, which is what a historical run publishes so a backtest is
    never adjusted by the present time of day.
    """
    _RUN_CLOCK.set(now)


def get_run_clock() -> datetime | None:
    """The run's published wall-clock instant, or ``None`` when none was published.

    ``None`` is the honest answer for an offline call and for a historical run:
    readers must treat it as "no live session known" rather than substituting
    the real clock, which would adjust a backtest by the current time of day.
    """
    return _RUN_CLOCK.get()


def _parse_date(value: str | None) -> datetime | None:
    """Parse a ``YYYY-MM-DD`` prefix; ``None`` when absent/unparseable.

    Leading/trailing whitespace is ignored and only the leading date is used,
    so a value carrying a time suffix (``2024-05-10T14:00``) still parses.
    """
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def as_of(date: str | None, trade_date: str | None) -> str | None:
    """Clamp a single ``date`` string to the run's ``trade_date``.

    Returns ``min(date, trade_date)``: a date the model asked for that is after
    the run date is pulled back to the run date; anything on or before it is
    returned unchanged. The clamp is TOTAL - it never raises and always returns
    a usable value. When either argument is empty or unparseable the input
    ``date`` is returned unchanged, so an empty/absent ``trade_date`` is a
    no-op (the caller's value flows through untouched).
    """
    d = _parse_date(date)
    t = _parse_date(trade_date)
    if d is None or t is None:
        return date
    return date if d <= t else trade_date


def as_of_window(
    start: str | None, end: str | None, trade_date: str | None
) -> tuple[str | None, str | None]:
    """Clamp a ``[start, end]`` date window to the run's ``trade_date``.

    Each bound is clamped with :func:`as_of`; additionally the result is never
    allowed to start after it ends: if clamping pulls the start forward past the
    (also-clamped) end - e.g. the model asked for a window that opens after the
    run date while its end stays on or before it - the start is pulled back to
    the end so callers always get a valid, non-inverted window. Total like
    ``as_of``: an empty/unparseable ``trade_date`` (or empty bound) is a no-op
    and both inputs are returned unchanged.
    """
    clamped_start = as_of(start, trade_date)
    clamped_end = as_of(end, trade_date)
    s = _parse_date(clamped_start)
    e = _parse_date(clamped_end)
    if s is not None and e is not None and s > e:
        clamped_start = clamped_end
    return clamped_start, clamped_end


def to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC-aware; a naive value is assumed to be UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def in_window(pub_dt: datetime | None, start_dt: datetime, end_dt: datetime) -> bool:
    """Whether an item belongs in the half-open window ``[start, end + 1 day)``.

    ``pub_dt`` None means undated: kept only when the window still reaches the
    present DAY (its end date is today or later). A window that ended on an
    earlier day cannot prove an undated item isn't future, so it is dropped -
    the old "within the last 24h" slack admitted a prior-session backtest window.
    """
    end = to_utc(end_dt)
    if pub_dt is not None:
        return to_utc(start_dt) <= to_utc(pub_dt) < end + timedelta(days=1)
    return end.date() >= datetime.now(timezone.utc).date()
