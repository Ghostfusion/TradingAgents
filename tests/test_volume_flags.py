"""Mechanically-huge volume: OPEX-week flags and the discounted RVOL/VDU read.

The point of the discount is that expiration turnover is not the stock's own
supply/demand: it can confirm a breakout that never happened, and it can inflate
the baseline a dry-up is measured against. Both directions are pinned here, plus
the rule that an unmeasured discount never silently changes a gate.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tradingagents.strategies import value_dip as vd, volume_flags as V

pytestmark = pytest.mark.timeout(120)

# The third Friday of March 2026 is the 20th; the OPEX week is the five
# sessions ending on it (16th-20th).
OPEX_FRIDAY = date(2026, 3, 20)


def _weekdays(start: date, n: int) -> list[str]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def test_opex_week_is_flagged_and_the_rest_is_not():
    dates = _weekdays(date(2026, 3, 2), 25)
    flags = V.mechanical_volume_flags(dates)
    assert flags is not None
    assert len(flags) == len(dates)
    flagged = [d for d, f in zip(dates, flags, strict=True) if f]
    assert flagged == ["2026-03-16", "2026-03-17", "2026-03-18", "2026-03-19", "2026-03-20"]


def test_quarterly_only_skips_the_monthly_expirations():
    dates = _weekdays(date(2026, 2, 2), 40)  # spans Feb 20 and Mar 20
    monthly = V.mechanical_volume_flags(dates)
    quarterly = V.mechanical_volume_flags(dates, quarterly_only=True)
    assert monthly is not None and quarterly is not None
    assert monthly.count(True) > quarterly.count(True)
    assert quarterly[dates.index("2026-02-20")] is False
    assert quarterly[dates.index("2026-03-20")] is True


def test_include_unwind_flags_the_session_after_opex():
    dates = _weekdays(date(2026, 3, 16), 6)  # Mon 16th .. Mon 23rd
    plain = V.mechanical_volume_flags(dates)
    unwind = V.mechanical_volume_flags(dates, include_unwind=True)
    assert plain is not None and unwind is not None
    assert plain[-1] is False
    assert unwind[-1] is True


def test_unparseable_or_absent_dates_are_unmeasured():
    assert V.mechanical_volume_flags([]) is None
    assert V.mechanical_volume_flags(["not-a-date"]) is None
    assert V.mechanical_volume_flags(None) is None


def test_rvol_denominator_drops_the_opex_spike():
    dates = _weekdays(date(2026, 3, 2), 22)
    volumes = [1000.0] * 22
    opex_i = dates.index("2026-03-20")
    volumes[opex_i] = 5000.0        # the expiration spike
    volumes[-1] = 1600.0            # today, an ordinary session
    r = V.rvol_ex_mechanical(volumes, dates, window=21)
    assert r is not None
    assert r["measured"] is True
    # The whole OPEX week (5 sessions) sits inside the prior window.
    assert r["excluded"] == 5
    assert r["flagged_today"] is False
    # Dropping the spike lowers the baseline, so today reads stronger.
    assert r["rvol_ex_mechanical"] > r["rvol"]
    assert r["rvol_ex_mechanical"] == 1.6


def test_rvol_without_dates_reports_the_raw_ratio_only():
    volumes = [1000.0] * 21 + [1600.0]
    r = V.rvol_ex_mechanical(volumes, window=21)
    assert r is not None
    assert r["measured"] is False
    assert r["rvol_ex_mechanical"] is None
    assert r["rvol"] == 1.6


def test_a_misaligned_flag_list_is_refused():
    volumes = [1000.0] * 22
    assert V.rvol_ex_mechanical(volumes, flags=[False, True], window=21) is None


def test_the_trigger_is_suppressed_when_today_is_mechanical():
    """A trigger cannot be confirmed by its OWN expiration turnover."""
    # 15 weekdays from 2026-03-02 end on the OPEX Friday (the 20th).
    dates = _weekdays(date(2026, 3, 2), 15)
    assert dates[-1] == "2026-03-20"    # today IS the OPEX session
    n = len(dates)
    closes = [100.0 + i for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    closes[-1] = closes[-2] + 2.0      # closes above the prior high
    highs[-1] = closes[-1] + 1.0
    volumes = [1000.0] * (n - 1) + [2000.0]

    raw = vd.trigger_candle(closes, highs, lows, volumes, window=10)
    assert raw["trigger"] is True
    assert raw["rvol"] == 2.0

    discounted = vd.trigger_candle(
        closes, highs, lows, volumes, window=10, dates=dates, discount_mechanical=True
    )
    assert discounted["mechanical_today"] is True
    assert discounted["trigger"] is False
    # Without dates the discount is unmeasured and the raw ratio still gates.
    assert vd.trigger_candle(
        closes, highs, lows, volumes, window=10, dates=None, discount_mechanical=True
    )["trigger"] is True


def test_the_dry_up_ratio_drops_the_opex_spike():
    """An expiration spike must not manufacture a dry-up."""
    n = 40
    dates = _weekdays(date(2026, 3, 2), n)
    volumes = [1000.0] * n
    volumes[dates.index("2026-03-20")] = 6000.0
    volumes[-6:] = [750.0] * 6          # the quiet sessions before today

    raw = vd.volume_dry_up(volumes, window=20, lookback=5)
    discounted = vd.volume_dry_up(
        volumes, window=20, lookback=5, dates=dates, discount_mechanical=True
    )
    # The spike inflated the baseline, so the raw read reports a dry-up the
    # discount removes.
    assert raw["dry_up"] is True
    assert raw["vdu_ratio"] == 0.6
    assert discounted["mechanical_discount_measured"] is True
    # The prior window spans the March OPEX week's Friday AND the first four
    # sessions of April's OPEX week (the 40-session list reaches into April).
    assert discounted["mechanical_excluded"] == 5
    assert discounted["vdu_ratio_ex_mechanical"] == 0.75
    assert discounted["dry_up"] is False


def test_the_ladder_forwards_the_discount(monkeypatch):
    """The ladder's candidate must follow the discounted sub-reads."""
    n = 40
    closes = [100.0 + (i % 5) for i in range(n)]
    highs = [c + 0.4 for c in closes]
    lows = [c - 0.4 for c in closes]
    dates = _weekdays(date(2026, 3, 2), n)
    volumes = [1000.0] * n
    calls: dict = {}

    def _spy(volumes_, *a, **k):
        calls["dates"] = k.get("dates")
        calls["discount"] = k.get("discount_mechanical")
        return {"dry_up": None, "vdu_ratio": None}

    monkeypatch.setattr(vd, "volume_dry_up", _spy)
    vd.vdu_entry_setup(closes, highs, lows, volumes, dates=dates, discount_mechanical=True)
    assert calls["dates"] == dates
    assert calls["discount"] is True
