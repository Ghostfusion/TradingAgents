"""Tests for the options-surface reads added to `strategies/options_surface.py`.

V4: the pre-event ATM term-structure shape is indexed in **event time** (days to
the scheduled catalyst), so the same chain read against a different catalyst is
a different shape. The read describes; it never forecasts.
"""

import pytest

from tradingagents.strategies.options_surface import pre_event_iv_lift

pytestmark = pytest.mark.timeout(60)

AS_OF = "2026-09-10"


def _chain(expiries_iv: dict[int, float], spot: float = 100.0) -> list[dict]:
    """Synthetic chain: one ATM call + put pair per ``days_to_expiry``."""
    rows = []
    for days, iv in expiries_iv.items():
        for side in ("call", "put"):
            rows.append({"strike": spot, "iv": iv, "days_to_expiry": days,
                         "spot": spot, "side": side})
    return rows


def _bundle(rows: list[dict], meeting: str, prob: float = 88.0) -> dict:
    """The chain bundle the tool builds: rows + as-of + the Fed calendar."""
    return {
        "rows": rows,
        "as_of": AS_OF,
        "fed_watch": [{"meeting_date": meeting, "probability": prob,
                       "target_range": "3.75-4.00%"}],
    }


def test_pre_event_lift_is_indexed_in_event_time():
    """The same chain read against two different catalysts gives two different
    shapes, because the expiry axis is re-anchored on the event (days to event)
    rather than left in calendar days to expiry."""
    # the expiry nearest the catalyst carries the richest vol, the furthest the
    # cheapest -- the paper's pre-event rise, as the shape's own orientation
    rows = _chain({2: 0.26, 5: 0.30, 9: 0.34})
    a = pre_event_iv_lift(_bundle(rows, "2026-09-20"), "2026-09-20")  # 10 days out
    b = pre_event_iv_lift(_bundle(rows, "2026-09-22"), "2026-09-22")  # 12 days out

    assert a["status"] == "ok" and b["status"] == "ok"
    assert a["event_date"] == "2026-09-20" and b["event_date"] == "2026-09-22"
    assert a["days_until_event"] == 10 and b["days_until_event"] == 12

    ta = [p["days_to_event"] for p in a["points"]]
    tb = [p["days_to_event"] for p in b["points"]]
    assert ta == [1, 5, 8]  # 10 - 9, 10 - 5, 10 - 2
    assert tb == [3, 7, 10]  # 12 - 9, 12 - 5, 12 - 2
    assert ta != tb
    # the same expiry moves by exactly the shift in the catalyst date
    assert [t - ta[i] for i, t in enumerate(tb)] == [2, 2, 2]

    # the shape keeps the event-time orientation: nearest the catalyst is the
    # richest vol, furthest before it the cheapest, and `lift` is that spread.
    assert a["points"][0]["atm_iv"] == 0.34
    assert a["points"][-1]["atm_iv"] == 0.26
    assert a["lift"] == pytest.approx(0.34 / 0.26 - 1.0, abs=1e-6)


def test_pre_event_lift_refuses_without_a_scheduled_event():
    """No certified catalyst -> `unavailable`, never a shape over a guessed date."""
    rows = _chain({2: 0.34, 5: 0.30, 9: 0.26})

    # the calendar holds no meeting inside the window
    none_in_window = pre_event_iv_lift(
        {"rows": rows, "as_of": AS_OF, "fed_watch": []}, None
    )
    assert none_in_window["status"] == "unavailable"
    assert none_in_window["points"] == [] and none_in_window["lift"] is None
    assert "no scheduled catalyst" in none_in_window["unavailable"]

    # a catalyst outside the window is not certified either
    too_far = pre_event_iv_lift(_bundle(rows, "2026-10-15"), "2026-10-15", window_days=14)
    assert too_far["status"] == "unavailable"

    # and a named date the calendar does not hold is refused, not re-indexed
    off_calendar = pre_event_iv_lift(_bundle(rows, "2026-09-20"), "2026-09-22")
    assert off_calendar["status"] == "unavailable"

    # with no name the calendar itself supplies the date it certified
    derived = pre_event_iv_lift(_bundle(rows, "2026-09-20"), None)
    assert derived["status"] == "ok" and derived["event_date"] == "2026-09-20"


def test_pre_event_lift_carries_no_value_past_the_catalyst():
    """Expiries dated after the event are counted, never valued: the read has no
    forecasting leg past the catalyst."""
    rows = _chain({2: 0.34, 5: 0.30, 9: 0.26, 16: 0.24, 30: 0.22})
    rec = pre_event_iv_lift(_bundle(rows, "2026-09-20"), "2026-09-20")

    assert rec["status"] == "ok"
    assert [p["days_to_event"] for p in rec["points"]] == [1, 5, 8]
    assert all(p["days_to_event"] >= 0 for p in rec["points"])
    assert rec["n_post_event_expiries"] == 2  # the 16d and the 30d expiry
