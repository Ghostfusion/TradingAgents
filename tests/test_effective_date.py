"""Tests for effective-trading-date + all-closed (DSA phase B; design §6-6).

- weekend/holiday/pre-close/post-close cases with a planted session table
- fail-open with no calendar (never blocks)
- all-closed skip; force-run bypass
"""

from datetime import datetime, timezone

import pytest

from tradingagents.dataflows import effective_date as ed

pytestmark = pytest.mark.timeout(30)

UTC = timezone.utc

# US-ET: Mon 2026-09-14, Tue 15, Wed 16, Thu 17, Fri 18, Sat 19, Sun 20.
MON = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)      # Mon noon UTC = 8:00 ET (before close)
MON_AFTER = datetime(2026, 9, 14, 21, 30, tzinfo=UTC)  # Mon 17:30 ET (after close)
SAT = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
JUL4_ET = datetime(2026, 7, 3, 22, 0, tzinfo=UTC)   # Fri 2026-07-03 18:00 ET (holiday; falls pre-close? 18:00 is after 16:00 close but holiday)

HOLIDAYS = {"2026-07-03"}  # US Independence Day observed (Fri)


class TestEffectiveDate:
    def test_weekend_goes_previous_session(self):
        # Sat 09-19 -> previous business day = Fri 09-18
        assert ed.effective_trading_date("US", SAT) == "2026-09-18"

    def test_pre_close_uses_previous_session(self):
        # Mon 08:00 ET (before 16:00 close) -> the last COMPLETED session
        # (Friday 09-11 of the prior week; 09-18 has not happened yet)
        assert ed.effective_trading_date("US", MON) == "2026-09-11"

    def test_after_close_uses_current_session(self):
        # Mon 17:30 ET -> the Monday session itself
        assert ed.effective_trading_date("US", MON_AFTER) == "2026-09-14"

    def test_holiday_with_override(self):
        # 2026-07-03 is a known holiday -> previous business day (Thu 07-02)
        assert ed.effective_trading_date("US", JUL4_ET, non_trading_days=HOLIDAYS) == "2026-07-02"
        # without the override set, fail-open treats it as a normal Fri-after-close
        assert ed.effective_trading_date("US", JUL4_ET) == "2026-07-03"

    def test_force_run_bypasses(self):
        assert ed.effective_trading_date("US", SAT, force_run=True) == "2026-09-19"

    def test_unknown_region_fail_open(self):
        # unknown region falls back to US close tz AND keeps the rules:
        # Sat -> previous session (Fri 09-18). Never blocks.
        assert ed.effective_trading_date("XX", SAT) == "2026-09-18"


class TestAllClosed:
    def test_all_closed_on_weekend(self):
        assert ed.should_skip_all_closed(["US"], SAT) is True

    def test_not_closed_when_one_open(self):
        assert ed.should_skip_all_closed(["US"], MON_AFTER) is False
        # US closed (weekend) but JP open after its close on Mon -> not all closed
        jp_open_mon = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)  # Mon 17:00 JST after close
        assert ed.should_skip_all_closed(["US", "JP"], jp_open_mon) is False

    def test_empty_regions_no_skip(self):
        assert ed.should_skip_all_closed([], SAT) is False

    def test_fail_open_never_blocks(self):
        assert ed.should_skip_all_closed(["XX"], SAT) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

