"""O'Neil distribution-day count: both expiries, the +5% cancel, the FTD reset.

The count only means something if all three drop-off rules work, so each is
pinned separately against a synthetic index. All series are built here, so
every expectation is arithmetic rather than a fitted value.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.distribution_days import distribution_days

pytestmark = pytest.mark.timeout(120)

BASE_VOL = 1000.0


def _series(n=40, *, drop_at=(), drop_pct=0.005, rise_pct=0.002, jumps=None, quiet_at=()):
    """A rising index with named down-sessions and optional one-day jumps.

    ``drop_at`` bars close ``drop_pct`` lower on double volume (a distribution
    day); ``jumps`` maps a bar index to a one-day gain; ``quiet_at`` bars carry
    a correction-sized decline of their own.
    """
    jumps = jumps or {}
    closes, volumes = [], []
    px = 100.0
    for i in range(n):
        if i == 0:
            closes.append(px)
            volumes.append(BASE_VOL)
            continue
        if i in drop_at:
            px *= 1 - drop_pct
            volumes.append(BASE_VOL * 2)
        elif i in quiet_at:
            px *= 1 - 0.015
            volumes.append(BASE_VOL * 1.5)
        else:
            px *= 1 + jumps.get(i, rise_pct)
            volumes.append(BASE_VOL * (2.0 if i in jumps else 1.0))
        closes.append(px)
    return closes, volumes


@pytest.mark.unit
def test_a_few_distribution_days_are_counted_but_not_a_top_signal():
    closes, volumes = _series(drop_at=(30, 33, 36))
    r = distribution_days(closes, volumes)
    assert r is not None
    assert r["detected"] == 3
    assert r["count"] == 3
    assert r["under_distribution"] is False
    assert [row["sessions_ago"] for row in r["active"]] == [9, 6, 3]


@pytest.mark.unit
def test_five_or_more_days_read_as_under_distribution():
    closes, volumes = _series(drop_at=(20, 23, 26, 29, 32, 35))
    r = distribution_days(closes, volumes)
    assert r is not None
    assert r["count"] == 6
    assert r["under_distribution"] is True


@pytest.mark.unit
def test_a_day_expires_after_the_window():
    # Bar 5 is 34 sessions back (expired); bar 30 is 9 sessions back (active).
    closes, volumes = _series(drop_at=(5, 30))
    r = distribution_days(closes, volumes)
    assert r is not None
    assert r["detected"] == 2
    assert r["expired"] == 1
    assert r["count"] == 1
    assert r["active"][0]["sessions_ago"] == 9


@pytest.mark.unit
def test_a_five_percent_rally_cancels_the_day_early():
    closes, volumes = _series(drop_at=(30,), jumps={32: 0.06})
    r = distribution_days(closes, volumes)
    assert r is not None
    assert r["detected"] == 1
    assert r["cancelled_rally"] == 1
    assert r["count"] == 0
    assert r["expired"] == 0


@pytest.mark.unit
def test_a_follow_through_day_resets_the_count():
    """The reset the swing literature omits: pre-FTD days stop counting."""
    closes, volumes = _series(
        quiet_at=(20, 21, 22),   # a 4.4% correction -> the low is bar 22
        jumps={27: 0.02},        # +2.0% on double volume, 5 sessions later
    )
    r = distribution_days(closes, volumes)
    assert r is not None
    # Only the first correction bar is a distribution day: the next two close
    # lower on EQUAL volume, which is not higher volume.
    assert r["detected"] == 1
    assert r["ftd"] is not None
    assert r["ftd"]["sessions_ago"] == 12
    assert r["ftd"]["gain_pct"] == 0.02
    assert r["ftd"]["volume_confirmed"] is True
    assert r["reset_by_ftd"] == 1
    assert r["count"] == 0
    assert r["expired"] == 0
    assert r["cancelled_rally"] == 0

    # Negative control: raise the rally bar (5%) so no day qualifies as a
    # follow-through, and the very same day stays counted.
    no_ftd = distribution_days(closes, volumes, ftd_min_gain=0.05)
    assert no_ftd is not None
    assert no_ftd["ftd"] is None
    assert no_ftd["count"] == 1


@pytest.mark.unit
def test_the_drop_off_rules_account_for_every_detected_day():
    closes, volumes = _series(drop_at=(5, 12, 20, 30), jumps={32: 0.06})
    r = distribution_days(closes, volumes)
    assert r is not None
    assert r["detected"] == 4
    assert r["count"] + r["expired"] + r["cancelled_rally"] + r["reset_by_ftd"] == r["detected"]


@pytest.mark.unit
def test_dates_are_carried_through_when_supplied():
    closes, volumes = _series(drop_at=(30, 33))
    dates = [f"2026-01-{i + 1:02d}" for i in range(len(closes))]
    r = distribution_days(closes, volumes, dates=dates)
    assert r is not None
    assert [row["date"] for row in r["active"]] == [dates[30], dates[33]]
    # A mismatched date list is ignored rather than misaligned.
    mismatched = distribution_days(closes, volumes, dates=dates[:3])
    assert mismatched is not None
    assert mismatched["active"][0]["date"] is None


@pytest.mark.unit
def test_too_little_or_inconsistent_series_is_unmeasured():
    closes, volumes = _series(n=20)
    assert distribution_days(closes, volumes) is None
    closes, volumes = _series(n=40)
    assert distribution_days(closes, volumes[:-1]) is None
    assert distribution_days([], []) is None
