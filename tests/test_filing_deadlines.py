"""Form 13F deadlines + the still-accumulating period (GMED 2026-10-14).

The institutional-holdings tool renders the vendor's own ``period_text`` and the
SentimentScore ``inst_flow_z`` leaf z-scores that period's change in % of float.
On 2026-10-14 the newest vendor row was ``2026/Q3``, whose Form 13F filings are
not due until 2026-11-16 - so the "+0.3pp" was a delta over a quarter that is
still accumulating, and z-scoring it against completed quarters dragged the
component to -0.03 where the newest COMPLETE period (2026/Q2, +7.0pp) reads
+1.80 against a declared ramp of (-2.0, 2.0).
"""

import datetime as dt

import pytest

from tradingagents.strategies.filing_deadlines import (
    filing_period_complete,
    form_13f_deadline,
    next_business_day,
    period_end_from_text,
)
from tradingagents.strategies.sentiment_research import inst_flow_z


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("2025/Q4", "2026-02-17"),  # 45d = Sat 2026-02-14; Mon 16 = Presidents' Day
        ("2026/Q1", "2026-05-15"),
        ("2026/Q2", "2026-08-14"),
        ("2026/Q3", "2026-11-16"),  # 45d = Sat 2026-11-14 -> Mon 16
    ],
)
def test_13f_deadlines_match_the_published_2026_calendar(period, expected):
    """The four 2026 Form 13F dates (Skadden's 2026 filing-deadline calendar)."""
    end = period_end_from_text(period)
    assert end is not None
    assert form_13f_deadline(end).isoformat() == expected


def test_period_end_parsing_and_unknown_labels():
    assert period_end_from_text("2026/Q3") == dt.date(2026, 9, 30)
    assert period_end_from_text("2026-q4") == dt.date(2026, 12, 31)
    assert period_end_from_text("2025/Q1") == dt.date(2025, 3, 31)
    assert period_end_from_text("2026/FY") is None
    assert period_end_from_text("") is None
    assert period_end_from_text("Q3") is None


def test_next_business_day_rolls_weekends_and_holidays():
    assert next_business_day(dt.date(2026, 11, 14)) == dt.date(2026, 11, 16)  # Sat
    assert next_business_day(dt.date(2026, 2, 16)) == dt.date(2026, 2, 17)  # Presidents' Day
    assert next_business_day(dt.date(2026, 10, 14)) == dt.date(2026, 10, 14)  # a Wednesday


def test_a_quarter_is_incomplete_until_its_filings_are_due():
    assert filing_period_complete("2026/Q3", as_of="2026-10-14") is False
    assert filing_period_complete("2026/Q3", as_of="2026-11-15") is False
    assert filing_period_complete("2026/Q3", as_of="2026-11-16") is True
    assert filing_period_complete("2026/Q2", as_of="2026-10-14") is True


def test_unknown_input_is_never_complete():
    assert filing_period_complete("2026/FY", as_of="2026-10-14") is None
    assert filing_period_complete("2026/Q3", as_of="") is None
    assert filing_period_complete("2026/Q3", as_of=None) is None


def _rows(*specs):
    return [
        {"period": period, "pct_change": change, "period_complete": complete}
        for period, change, complete in specs
    ]


def test_flow_z_skips_a_still_filing_period_and_names_it():
    out = inst_flow_z(
        _rows(
            ("2026/Q3", 0.305, False),
            ("2026/Q2", 7.038, True),
            ("2026/Q1", -0.697, True),
            ("2025/Q4", -4.9, True),
            ("2025/Q3", 2.3, True),
        )
    )
    assert out is not None
    # The newest COMPLETE period's change, never the partial quarter's.
    assert out["pct_change"] == 7.038
    assert out["n"] == 4
    assert "skipped still-filing period(s): 2026/Q3" in out["basis"]


def test_flow_z_refuses_when_no_period_is_complete():
    out = inst_flow_z(_rows(("2026/Q3", 0.305, False), ("2026/Q2", 7.0, False)))
    assert out is not None
    assert out["inst_flow_z"] is None
    assert out["pct_change"] is None
    assert "no completed 13F period" in out["reason"]
    assert "2026/Q3" in out["reason"]


def test_flow_z_without_a_completeness_verdict_keeps_its_old_behaviour():
    """A caller that supplies no verdict is not claiming the period is complete."""
    out = inst_flow_z(
        [
            {"period": "2026/Q3", "pct_change": 0.3},
            {"period": "2026/Q2", "pct_change": 7.0},
            {"period": "2026/Q1", "pct_change": -0.7},
            {"period": "2025/Q4", "pct_change": -4.9},
            {"period": "2025/Q3", "pct_change": 2.3},
        ]
    )
    assert out is not None
    assert out["pct_change"] == 0.3
    assert out["n"] == 5
    assert "skipped" not in out["basis"]
