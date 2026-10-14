"""When a fact could first exist (the availability policy table).

Sources (all read 2026-10-14):

- 17 CFR 249.308a(a) - a Form 10-Q is due "40 days after the end of the fiscal
  quarter for large accelerated filers and accelerated filers" and "45 days
  after the end of the fiscal quarter for all other registrants".
- 17 CFR 249.310(b) - a Form 10-K is due 60 days after the fiscal year end for
  large accelerated filers, 75 for accelerated filers, 90 for all others.
- Item 8 of Form 20-F (foreign private issuers) - 4 months after the fiscal year
  end (Mayer Brown's 2023 SEC filing-deadline note dates it).
- 17 CFR 240.13f-1(a) - a Form 13F is due 45 days after each calendar quarter
  end; ``filing_deadlines.form_13f_deadline`` is its one producer, so
  ``availability.form_deadline`` delegates rather than restating 45.
- Exchange Act Rule 0-3(a) - a due date landing on a Saturday, Sunday or federal
  holiday moves to the next business day (the roll the 2026 Form 13F calendar
  shows: Feb 17, May 15, Aug 14, Nov 16).
- Rule 12b-25 - a late-filing notification buys 5 extra calendar days for a
  Form 10-Q and 15 for a Form 10-K, which is why the due date is a LOWER bound
  and the notification date an upper one.
"""

import datetime as dt

import pytest

from tradingagents.strategies.availability import (
    AVAILABILITY_REASON_CODES,
    AVAILABILITY_STATES,
    FILER_STATUSES,
    FORM_LAG_DAYS,
    availability_window,
    default_filer_status,
    fact_availability,
    form_deadline,
    form_for_kind,
    form_lag_days,
    latest_form_deadline,
    period_end_of,
)
from tradingagents.strategies.filing_deadlines import form_13f_deadline

pytestmark = pytest.mark.timeout(60)


def test_the_statutory_lags_are_the_published_ones():
    assert form_lag_days("10-Q", filer_status="large_accelerated") == (40, "large_accelerated", False)
    assert form_lag_days("10-Q", filer_status="accelerated") == (40, "accelerated", False)
    assert form_lag_days("10-Q", filer_status="all_other") == (45, "all_other", False)
    assert form_lag_days("10-K", filer_status="large_accelerated") == (60, "large_accelerated", False)
    assert form_lag_days("10-K", filer_status="accelerated") == (75, "accelerated", False)
    assert form_lag_days("10-K", filer_status="all_other") == (90, "all_other", False)
    assert form_lag_days("20-F", filer_status="unknown") == (120, "any", False)


def test_an_unknown_filer_class_resolves_to_the_slowest_bound_and_says_so():
    """Fail closed: completeness is claimed only once EVERY filer class must
    have filed, and the resolution is named rather than implied."""
    assert form_lag_days("10-Q", filer_status="unknown") == (45, "all_other", True)
    assert form_lag_days("10-K", filer_status="unknown") == (90, "all_other", True)
    assert form_lag_days("20-F", filer_status="unknown")[2] is False
    assert default_filer_status("10-K") == "all_other"
    assert default_filer_status("13F") == "any"


def test_an_unknown_filer_class_is_reported_on_the_verdict():
    out = fact_availability(period_end="2026-06-30", form="10-Q", as_of="2026-08-14")
    assert out["assumed"] is True
    assert out["filer_status"] == "all_other"
    assert "filer class assumed" in out["basis"]


def test_a_due_date_rolls_to_the_next_business_day():
    # 2026-09-30 + 45d = Sat 2026-11-14 -> Mon 2026-11-16.
    due, status, assumed = form_deadline("10-Q", dt.date(2026, 9, 30), filer_status="all_other")
    assert due == dt.date(2026, 11, 16)
    assert (status, assumed) == ("all_other", False)
    # 2026-12-31 + 45d = Sun 2027-02-14 -> Presidents' Day 2027-02-15 -> Tue 16.
    assert form_deadline("10-Q", dt.date(2026, 12, 31), filer_status="all_other")[0] == dt.date(
        2027, 2, 16
    )


def test_13f_delegates_to_its_one_producer():
    """The 45-day Form 13F rule lives in ``filing_deadlines`` and nowhere else."""
    for end in (dt.date(2026, 3, 31), dt.date(2026, 6, 30), dt.date(2026, 12, 31)):
        assert form_deadline("13F", end)[0] == form_13f_deadline(end)


def test_the_late_filing_notification_is_the_upper_bound():
    """Rule 12b-25: +5 calendar days for a 10-Q, +15 for a 10-K, nothing for a
    20-F - so the due date is the EARLIEST its data may exist."""
    end = dt.date(2026, 6, 30)
    due, latest, _status, _assumed = availability_window("10-Q", end, filer_status="all_other")
    assert (latest - due).days == 5
    due_k, latest_k, _s, _a = availability_window("10-K", end, filer_status="all_other")
    assert (latest_k - due_k).days == 15
    due_f, latest_f, _s, _a = availability_window("20-F", end, filer_status="all_other")
    assert latest_f == due_f


def test_a_form_with_no_lag_table_has_no_deadline():
    assert form_lag_days("S-1", filer_status="any") is None
    assert form_deadline("S-1", dt.date(2026, 6, 30)) is None
    assert latest_form_deadline("S-1", dt.date(2026, 6, 30)) is None


def test_period_end_of_accepts_only_a_stated_iso_date():
    """A fiscal label states no calendar, so it does not yield a period end: a
    June-year issuer's "2026/Q2" ends 2026-03-31, not 2026-06-30, and guessing
    would put a wrong deadline on it."""
    assert period_end_of("2026-06-30") == dt.date(2026, 6, 30)
    assert period_end_of("2026-06-30 (FY 2026, currency: USD)") == dt.date(2026, 6, 30)
    assert period_end_of("2026/Q2") is None
    assert period_end_of("2025/FY") is None
    assert period_end_of(None) is None
    assert period_end_of("") is None


def test_the_period_kind_maps_to_the_form_it_must_have_arrived_in():
    assert form_for_kind("annual") == "10-K"
    assert form_for_kind("quarterly") == "10-Q"
    assert form_for_kind("ttm") == "10-Q"
    assert form_for_kind("unstated") is None
    assert form_for_kind(None) is None


def test_market_data_has_no_filing_form():
    out = fact_availability(period_end="2026-10-14", form="info", as_of="2026-10-14")
    assert out["state"] == "not_applicable"
    assert out["reason"] == "NO_FILING_FORM"


def test_an_undeclared_form_is_unknown_not_available():
    out = fact_availability(period_end="2026-06-30", as_of="2026-10-14")
    assert out["state"] == "unknown"
    assert out["reason"] == "FORM_UNDECLARED"


def test_a_fiscal_label_yields_period_end_unknown_not_a_guessed_deadline():
    out = fact_availability(period_end=None, kind="quarterly", as_of="2026-10-14")
    assert out["state"] == "unknown"
    assert out["reason"] == "PERIOD_END_UNKNOWN"
    assert "states no ISO end date" in out["basis"]


def test_no_clock_is_unknown_never_available():
    out = fact_availability(period_end="2026-06-30", form="10-Q", as_of=None)
    assert out["state"] == "unknown"
    assert out["earliest"] == "2026-08-14"
    assert "no clock to compare against" in out["basis"]


def test_a_quarter_is_not_filed_yet_until_its_form_is_due():
    """The GMED 2026-10-14 case: a quarter ending 2026-09-30 cannot have a FILED
    10-Q basis on 2026-10-14 (due 2026-11-16 at the fail-closed bound)."""
    before = fact_availability(period_end="2026-09-30", kind="quarterly", as_of="2026-10-14")
    assert before["state"] == "not_yet_due"
    assert before["reason"] == "FORM_NOT_YET_DUE"
    assert before["earliest"] == "2026-11-16"
    after = fact_availability(period_end="2026-09-30", kind="quarterly", as_of="2026-11-16")
    assert after["state"] == "available"
    assert after["reason"] == "FILED_FORM_DUE"


def test_a_quarter_whose_form_is_due_is_available():
    out = fact_availability(period_end="2026-06-30", kind="quarterly", as_of="2026-10-14")
    assert out["state"] == "available"
    assert out["earliest"] == "2026-08-14"
    assert out["latest"] == "2026-08-19"


def test_the_vocabularies_are_closed():
    # Form 13F has no lag table here on purpose: filing_deadlines owns its 45 days.
    assert "13F" not in FORM_LAG_DAYS
    assert set(FORM_LAG_DAYS) == {"10-K", "10-Q", "20-F"}
    assert set(AVAILABILITY_STATES) == {"available", "not_yet_due", "unknown", "not_applicable"}
    assert set(AVAILABILITY_REASON_CODES) >= {
        "FILED_FORM_DUE",
        "FORM_NOT_YET_DUE",
        "PERIOD_END_UNKNOWN",
        "FORM_UNDECLARED",
        "AVAILABILITY_UNKNOWN",
    }
    assert set(FILER_STATUSES) == {
        "large_accelerated",
        "accelerated",
        "all_other",
        "any",
        "unknown",
    }
