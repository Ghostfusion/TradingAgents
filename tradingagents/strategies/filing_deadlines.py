"""SEC filing-deadline arithmetic - one producer per deadline.

**Form 13F** (17 CFR 240.13f-1(a), Form 13F General Instruction 3): a manager
reports within **45 days** after the last day of each calendar year and of each
of the first three calendar quarters. A due date that lands on a Saturday,
Sunday or federal holiday moves to the **next business day** - Skadden's 2026
filing-deadline calendar states the rule and applies it to the four 2026 13F
dates (February 17, May 15, August 14, November 16).

Why this exists: the institutional-holdings tool renders the vendor's own
``period_text`` (``2026/Q3``) and the SentimentScore ``inst_flow_z`` leaf
z-scores that period's change in % of float. On 2026-10-14 the Q3 13F filings
are not due until 2026-11-16, so a "2026/Q3" aggregate can only be an
early-filer snapshot: a completed-quarter DELTA computed over a quarter that is
still accumulating. Publishing it as a measured period change is the defect
this module makes detectable - the caller asks whether a period is COMPLETE
before treating its delta as a measurement.

A period whose text cannot be parsed returns ``None`` (unknown), never a guess:
an unrecognised label is not evidence that the period is complete.
"""

from __future__ import annotations

import datetime as _dt

__all__ = [
    "filing_period_complete",
    "form_13f_deadline",
    "next_business_day",
    "period_end_from_text",
    "us_federal_holidays",
]

_QUARTER_MONTHS = {1: 3, 2: 6, 3: 9, 4: 12}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    """The ``n``-th ``weekday`` (Mon=0) of ``month`` in ``year``."""
    first = _dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + _dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> _dt.date:
    """The last ``weekday`` of ``month`` in ``year``."""
    if month == 12:
        last = _dt.date(year, 12, 31)
    else:
        last = _dt.date(year, month + 1, 1) - _dt.timedelta(days=1)
    return last - _dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: _dt.date) -> _dt.date:
    """A fixed-date holiday observed on the nearest weekday (Sat->Fri, Sun->Mon)."""
    if d.weekday() == 5:
        return d - _dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + _dt.timedelta(days=1)
    return d


def us_federal_holidays(year: int) -> frozenset[_dt.date]:
    """Observed federal holidays falling in ``year`` (including cross-year shifts).

    New Year's Day of ``year + 1`` can be observed on 2026-12-31 (a Saturday
    January 1), and New Year's Day of ``year`` can be observed on December 31
    of ``year - 1``; both are included so ``next_business_day`` is right at the
    year boundary.
    """
    days = {
        _nth_weekday(year, 1, 0, 3),  # MLK
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _last_weekday(year, 5, 0),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 10, 0, 2),  # Columbus Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(_dt.date(year, 1, 1)),
        _observed(_dt.date(year, 6, 19)),
        _observed(_dt.date(year, 7, 4)),
        _observed(_dt.date(year, 11, 11)),
        _observed(_dt.date(year, 12, 25)),
        # Cross-year shifts: only the ones that land inside ``year``.
        _observed(_dt.date(year + 1, 1, 1)),
        _observed(_dt.date(year - 1, 1, 1)),
    }
    return frozenset(d for d in days if d.year == year)


def _holiday_window(d: _dt.date) -> frozenset[_dt.date]:
    return (
        us_federal_holidays(d.year)
        | us_federal_holidays(d.year - 1)
        | us_federal_holidays(d.year + 1)
    )


def next_business_day(d: _dt.date) -> _dt.date:
    """``d`` when it is a business day, else the next weekday that is not a holiday."""
    out = d
    # Bounded: the longest run of non-business days is a weekend plus holidays.
    for _ in range(10):
        if out.weekday() < 5 and out not in _holiday_window(out):
            return out
        out = out + _dt.timedelta(days=1)
    return out


def form_13f_deadline(period_end: _dt.date) -> _dt.date:
    """The Form 13F due date for a period ending ``period_end``.

    Quarter/year end + 45 days, moved to the next business day when that lands
    on a weekend or federal holiday.
    """
    return next_business_day(period_end + _dt.timedelta(days=45))


def period_end_from_text(period_text: str) -> _dt.date | None:
    """Last day of the quarter named by a vendor period label (``2026/Q3``).

    Accepts ``YYYY/Qn`` and ``YYYY-Qn`` (either case). ``None`` for any other
    shape - an unparsed label is UNKNOWN, never assumed complete.
    """
    text = (period_text or "").strip().upper().replace("-", "/")
    parts = text.split("/")
    if len(parts) != 2:
        return None
    year_s, quarter_s = parts[0].strip(), parts[1].strip().lstrip("Q")
    if not (year_s.isdigit() and quarter_s.isdigit()):
        return None
    year, quarter = int(year_s), int(quarter_s)
    if quarter not in _QUARTER_MONTHS or not (1900 <= year <= 2200):
        return None
    month = _QUARTER_MONTHS[quarter]
    if month == 12:
        return _dt.date(year, 12, 31)
    return _dt.date(year, month + 1, 1) - _dt.timedelta(days=1)


def _as_date(value) -> _dt.date | None:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def filing_period_complete(period_text: str, *, as_of) -> bool | None:
    """Whether a 13F-style period's filings are all due as of ``as_of``.

    ``True`` only after that period's Form 13F deadline has passed; ``False``
    while filings are still arriving (the period is accumulating); ``None`` when
    the period label, or ``as_of``, cannot be understood. never ``True`` on
    unknown input - a partial aggregate must not be published as complete.
    """
    end = period_end_from_text(period_text)
    day = _as_date(as_of)
    if end is None or day is None:
        return None
    return day >= form_13f_deadline(end)
