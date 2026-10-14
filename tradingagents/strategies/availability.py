"""When a fact could first EXIST - one producer per filing class.

A financial number is not a measurement until its *knowledge time* is known
(VIM 2.9: a result is complete only with its uncertainty; the standard temporal
model separates the time a fact was TRUE from the time it became KNOWN -
Snodgrass' valid time vs transaction time). A statement line item carries only
the first; this module supplies the second from the form it must have arrived
in.

The deadline arithmetic itself lives in :mod:`tradingagents.strategies.
filing_deadlines` (business-day roll + the Form 13F rule, one producer per
deadline); this module is the POLICY table, the filer-status resolution and the
"may it exist yet?" answer:

- **Form 10-Q**, 17 CFR 249.308a(a): 40 days after the fiscal quarter end for
  large accelerated filers and accelerated filers, 45 days for all other
  registrants.
- **Form 10-K**, 17 CFR 249.310(b): 60 days after the fiscal year end for large
  accelerated filers, 75 for accelerated filers, 90 for all other registrants.
- **Form 13F**, 17 CFR 240.13f-1(a): 45 days after each calendar quarter end and
  after the calendar year end (:func:`filing_deadlines.form_13f_deadline`).
- **Form 20-F** (foreign private issuers): 4 months after the fiscal year end
  (Item 8 of Form 20-F; Mayer Brown's 2023 SEC filing-deadline note dates it).
- **The roll**, Exchange Act Rule 0-3(a): a due date landing on a Saturday,
  Sunday or federal holiday moves to the next business day - the reason the four
  2026 Form 13F dates read February 17, May 15, August 14 and November 16.
- **Rule 12b-25**: a registrant that files a late-filing notification gets 5
  extra calendar days for a 10-Q and 15 for a 10-K. That is why a form's due
  date is a *lower* bound on when its data may exist, and the notification date
  is the upper bound this module publishes beside it.

**Fail closed on an unknown filer status.** The filer class is not in any
vendor payload this engine reads, so the default is ``unknown`` and resolves to
the LATEST statutory date (the all-other-registrants bound): completeness is
only claimed once every filer class must have filed. The resolution is
``assumed`` and named in the basis, never silent.

**Never guess a period end.** A vendor label that states no fiscal calendar
(``2025/FY``, ``2026/Q2`` from a June-year issuer) has no derivable period end,
and :func:`availability_window` returns ``None`` for it (UNKNOWN) rather than
importing a calendar assumption - an unparsed period is not evidence of
availability.
"""

from __future__ import annotations

import datetime as _dt

from tradingagents.strategies.filing_deadlines import form_13f_deadline, next_business_day

__all__ = [
    "AVAILABILITY_REASON_CODES",
    "AVAILABILITY_STATES",
    "FILER_STATUSES",
    "FORM_LAG_DAYS",
    "LATE_FILING_EXTENSION_DAYS",
    "availability_window",
    "default_filer_status",
    "fact_availability",
    "form_deadline",
    "form_for_kind",
    "form_lag_days",
    "latest_form_deadline",
    "period_end_of",
]

#: The closed vocabulary for "why the availability of this fact is what it is".
AVAILABILITY_REASON_CODES = (
    "FILED_FORM_DUE",  # the form's due date has passed: the data may exist
    "FORM_NOT_YET_DUE",  # the form is not due yet: the data may not exist yet
    "NO_FILING_FORM",  # market data (a price, a market cap) has no form
    "PERIOD_END_UNKNOWN",  # the label states no fiscal calendar
    "FORM_UNDECLARED",  # the source does not declare which form carried it
    "AVAILABILITY_UNKNOWN",  # no clock to compare against
)

AVAILABILITY_STATES = ("available", "not_yet_due", "unknown", "not_applicable")

#: Days after the period end, per form and filer class. ``all_other`` is the
#: longest statutory lag and therefore the fail-closed default. Form 13F is
#: absent on purpose: ``filing_deadlines.form_13f_deadline`` is its producer.
FORM_LAG_DAYS: dict[str, dict[str, int]] = {
    "10-K": {"large_accelerated": 60, "accelerated": 75, "all_other": 90},
    "10-Q": {"large_accelerated": 40, "accelerated": 40, "all_other": 45},
    "20-F": {"any": 120},
}

FILER_STATUSES = ("large_accelerated", "accelerated", "all_other", "any", "unknown")

#: Rule 12b-25: the extra calendar days a late-filing notification buys.
LATE_FILING_EXTENSION_DAYS: dict[str, int] = {"10-Q": 5, "10-K": 15}

_KIND_FORMS = {
    "annual": "10-K",
    "quarterly": "10-Q",
    "ttm": "10-Q",  # a trailing-twelve-month total needs its NEWEST quarter filed
    "fiscal_annual": "10-K",
    "fiscal_quarterly": "10-Q",
}


def form_for_kind(kind: str | None) -> str | None:
    """The form a period KIND must have arrived in, or ``None``.

    ``annual`` -> 10-K, ``quarterly``/``ttm`` -> 10-Q. An unstated kind (a bare
    date header, a market figure) maps to ``None``: no form can be demanded of
    it, and the caller reports the availability as unknown rather than assuming
    a filing.
    """
    return _KIND_FORMS.get(str(kind or "").strip().lower())


def default_filer_status(form: str) -> str:
    """The filer class assumed when none is declared: the SLOWEST one."""
    return "any" if form in ("13F", "20-F") else "all_other"


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


def period_end_of(label: str | None) -> _dt.date | None:
    """The period end a label STATES, or ``None`` when it states none.

    Only an ISO date (``2026-06-30``, the shape yfinance/tiingo column headers
    carry) is accepted. A vendor fiscal label - ``2026/Q2``, ``2025/FY`` - is
    NOT mapped onto a calendar date, because the issuer's fiscal calendar is not
    in the label and a June-year issuer's "Q2" ends 2026-03-31, not 2026-06-30.
    The calibration calendar assumption in
    :func:`filing_deadlines.period_end_from_text` belongs to the Form 13F rule
    (whose periods ARE calendar quarters) and is deliberately not reused here.
    """
    text = str(label or "").strip()
    if not text:
        return None
    head = text.split(" ", 1)[0]
    return _as_date(head)


def form_lag_days(form: str, *, filer_status: str = "unknown") -> tuple[int, str, bool] | None:
    """``(days, resolved_status, assumed)`` for a form, or ``None``.

    ``None`` means the form has no lag table here (a market figure, or an
    unknown form). ``assumed`` is True when the filer class was not declared and
    the slowest class was used - the caller prints it rather than implying the
    issuer's real class.
    """
    lags = FORM_LAG_DAYS.get(str(form or "").strip())
    if not lags:
        return None
    status = str(filer_status or "unknown").strip().lower()
    assumed = False
    if status not in lags:
        if len(lags) == 1:
            # One filer class (13F, 20-F): there is nothing to assume - the
            # deadline is the same for every registrant that files the form.
            status = next(iter(lags))
        else:
            status = default_filer_status(str(form).strip())
            assumed = True
    return lags[status], status, assumed


def form_deadline(
    form: str, period_end, *, filer_status: str = "unknown"
) -> tuple[_dt.date, str, bool] | None:
    """``(due_date, resolved_status, assumed)`` for a form and period end.

    The due date is rolled to the next business day when it lands on a weekend
    or federal holiday (Rule 0-3(a)). ``None`` when the form has no lag table or
    the period end is not a date - UNKNOWN, never a guessed deadline.
    """
    end = _as_date(period_end)
    if end is None:
        return None
    name = str(form or "").strip()
    if name == "13F":
        return form_13f_deadline(end), "any", False
    resolved = form_lag_days(name, filer_status=filer_status)
    if resolved is None:
        return None
    days, status, assumed = resolved
    return next_business_day(end + _dt.timedelta(days=days)), status, assumed


def latest_form_deadline(
    form: str, period_end, *, filer_status: str = "unknown"
) -> tuple[_dt.date, str, bool] | None:
    """``(latest_due_date, resolved_status, assumed)`` including a Rule 12b-25
    late-filing notification, or ``None``.

    A registrant that cannot file on time and files the notification gets 5
    extra calendar days for a 10-Q and 15 for a 10-K, so the notification date
    is the last day its data could first exist. A form with no published
    extension (20-F, 13F) returns its due date unchanged.
    """
    resolved = form_deadline(form, period_end, filer_status=filer_status)
    if resolved is None:
        return None
    due, status, assumed = resolved
    extra = LATE_FILING_EXTENSION_DAYS.get(str(form or "").strip(), 0)
    return due + _dt.timedelta(days=extra), status, assumed


def availability_window(
    form: str, period_end, *, filer_status: str = "unknown"
) -> tuple[_dt.date, _dt.date, str, bool] | None:
    """``(earliest, latest, resolved_status, assumed)`` a form's data may exist.

    ``earliest`` is the statutory due date (rolled) and ``latest`` adds the
    Rule 12b-25 grace. ``None`` when the form or the period end is unknown.
    """
    first = form_deadline(form, period_end, filer_status=filer_status)
    last = latest_form_deadline(form, period_end, filer_status=filer_status)
    if first is None or last is None:
        return None
    return first[0], last[0], first[1], first[2]


def fact_availability(
    *,
    period_end,
    form: str | None = None,
    kind: str | None = None,
    as_of=None,
    filer_status: str = "unknown",
) -> dict:
    """The availability verdict for one fact-shaped reading.

    Returns ``{"state", "reason", "earliest", "latest", "form", "filer_status",
    "assumed", "basis"}`` where ``state`` is one of
    :data:`AVAILABILITY_STATES`:

    - ``available`` - the form's due date has passed as of ``as_of``; the data
      may exist (it was not necessarily filed on time - Rule 12b-25 exists).
    - ``not_yet_due`` - the form is not due yet, so a FILED basis for this
      period cannot exist. This is the fail-closed state the caller must not
      consume as a measurement.
    - ``unknown`` - no clock, no period end, or no declared form: the honest
      answer, never promoted to ``available``.
    - ``not_applicable`` - the reading has no filing form at all (a price, a
      market cap).

    ``as_of`` accepts a ``YYYY-MM-DD`` string or a date. An unset clock means
    the comparison cannot be made, which is ``unknown`` - the same
    no-live-session default as :func:`date_window.get_run_clock`.
    """
    out: dict = {
        "state": "unknown",
        "reason": "AVAILABILITY_UNKNOWN",
        "earliest": None,
        "latest": None,
        "form": form or None,
        "filer_status": None,
        "assumed": False,
        "basis": "",
    }
    name = str(form or kind or "").strip()
    if not name:
        out["reason"] = "FORM_UNDECLARED"
        out["basis"] = "no form and no period kind: which filing carried this is undeclared"
        return out
    if name not in FORM_LAG_DAYS and name != "13F":
        resolved_form = form_for_kind(name)
        if resolved_form is None:
            out["state"] = "not_applicable"
            out["reason"] = "NO_FILING_FORM"
            out["basis"] = f"{name!r} is not a filing class (market data has no form)"
            return out
        name = resolved_form
    out["form"] = name
    end = _as_date(period_end)
    if end is None:
        out["reason"] = "PERIOD_END_UNKNOWN"
        out["basis"] = (
            f"{name}: the period label states no ISO end date, so its due date "
            "cannot be derived (a fiscal label is not a calendar date)"
        )
        return out
    window = availability_window(name, end, filer_status=filer_status)
    if window is None:
        return out
    earliest, latest, status, assumed = window
    out["earliest"] = earliest.isoformat()
    out["latest"] = latest.isoformat()
    out["filer_status"] = status
    out["assumed"] = assumed
    day = _as_date(as_of)
    assume_note = f" (filer class assumed: {status})" if assumed else f" ({status})"
    if day is None:
        out["basis"] = (
            f"{name} for period ending {end.isoformat()} is due {earliest.isoformat()}"
            f"{assume_note}; no clock to compare against"
        )
        return out
    if day >= earliest:
        out["state"] = "available"
        out["reason"] = "FILED_FORM_DUE"
        out["basis"] = (
            f"{name} for period ending {end.isoformat()} was due {earliest.isoformat()}"
            f"{assume_note}; latest possible filing {latest.isoformat()}"
        )
        return out
    out["state"] = "not_yet_due"
    out["reason"] = "FORM_NOT_YET_DUE"
    out["basis"] = (
        f"{name} for period ending {end.isoformat()} is not due until "
        f"{earliest.isoformat()}{assume_note}; a filed basis for this period "
        "cannot exist yet"
    )
    return out
