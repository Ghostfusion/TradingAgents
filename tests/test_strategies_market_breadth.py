"""P0-3: the market-wide breadth producer (percent-above-MA + A/D + highs/lows)."""

import pytest

from tradingagents.strategies.market_breadth import market_breadth

BARS = 260


def _rising(bars=BARS, *, last="up"):
    """Above every SMA (a long ramp); the final bar rises, falls or is flat."""
    s = [50.0 + 50.0 * j / (bars - 1) for j in range(bars)]
    return s[:-1] + [{"up": s[-1] + 1.0, "down": s[-1] - 0.5, "flat": s[-2]}[last]]


def _falling(bars=BARS, *, last="down"):
    """Below every SMA (a long decline); the final bar rises, falls or is flat."""
    s = [150.0 - 50.0 * j / (bars - 1) for j in range(bars)]
    return s[:-1] + [{"up": s[-2] + 0.5, "down": s[-1], "flat": s[-2]}[last]]


def _five_name_panel():
    """Five names, one per shape, so every count is known by construction:
    two above the 200-day (one up on the day, one down), three below (one up, one
    down, one flat), and exactly one at its own high."""
    return {
        "RISE": _rising(last="up"),            # above, advancing, at its high
        "RISE_DOWN": _rising(last="down"),     # above, declining
        "FALL": _falling(last="down"),         # below, declining, at its low
        "FALL_UP": _falling(last="up"),        # below, advancing
        "FALL_FLAT": _falling(last="flat"),    # below, flat
    }


def test_a_five_name_panel_matches_its_known_answers():
    """Acceptance: with the gate set to the panel size, every key matches the
    construction - 2 of 5 above the 200-day, 2 up on the day, 1 at its high."""
    got = market_breadth(_five_name_panel(), min_n=5)
    assert got is not None
    assert got["n"] == 5
    assert got["coverage"] == pytest.approx(1.0)
    assert got["pct_above_200d"] == pytest.approx(40.0)  # 2 of 5
    assert got["advancers"] == 2
    assert got["decliners"] == 2
    assert got["advance_decline"] == 0
    assert got["new_highs"] == 1
    # FALL ends at its own low, and FALL_FLAT's final bar IS its series minimum
    # (the flat step lands on the previous bar, which is the lowest point).
    assert got["new_lows"] == 2
    assert got["small_sample"] is False


def test_a_panel_below_the_floor_withholds_the_percentages_with_its_reason():
    """The denominator-integrity gate: five names are not a breadth read, so the
    percentages are None with the reason - never a noisy number (master rule 1)."""
    got = market_breadth(_five_name_panel())  # default min_n=20
    assert got["small_sample"] is True
    assert got["pct_above_200d"] is None
    assert got["pct_above_50d"] is None
    assert "5 < 20" in got["reason"]
    # The COUNTS still travel - they are counts, not rates.
    assert got["advancers"] == 2 and got["new_highs"] == 1


def test_a_panel_over_the_floor_prints_its_percentages_and_panel_size():
    panel = {f"R{i}": _rising() for i in range(15)}
    panel.update({f"F{i}": _falling() for i in range(25)})
    got = market_breadth(panel)
    assert got["small_sample"] is False
    assert got["n"] == 40
    assert got["pct_above_200d"] == pytest.approx(37.5)  # 15 of 40
    assert "40-name panel" in got["basis"]  # the panel size travels with the read
    assert "reason" not in got


def test_an_empty_or_unusable_panel_is_none_never_zero():
    assert market_breadth({}) is None
    assert market_breadth(None) is None
    panel = {f"N{i}": [100.0, 101.0] for i in range(25)}
    panel.update({"EMPTY": [], "ONE": [100.0], "NONE": [None, None]})
    got = market_breadth(panel)
    assert got["n"] == 25
    assert got["coverage"] == pytest.approx(25 / 28, abs=1e-3)


def test_the_new_high_count_is_measured_against_the_window_it_was_given():
    """``new_highs`` counts against the panel each name was given, and the basis
    says which window that was. The fixed-year pair is the one that may be
    quoted as 52-week, and a 60-bar panel cannot fill it: None, not 0.

    This used to assert ``"52" not in basis`` - a proxy for "the read makes no
    52-week claim". Now that a genuine 52-week counter exists, the claim is
    pinned where it belongs: on the counter.
    """
    short = {f"N{i}": [100.0 + j for j in range(60)] for i in range(25)}
    got = market_breadth(short)
    assert got["new_highs"] == 25
    assert "up to 60 bars each" in got["basis"]
    assert got["new_highs_52w"] is None
    assert got["new_lows_52w"] is None
    assert got["net_new_highs_52w"] is None
    assert got["new_highs_52w_n"] == 0


def test_the_52w_counters_use_a_fixed_year_not_the_panel_window():
    """The whole point of the fixed lookback: a 300-bar panel and the last 252
    bars of it give the SAME 52-week answer, and that answer can differ from the
    panel-window count - which is why both are printed.

    Construction: 300 bars flat at 100 with a 300.0 spike at index 10 (outside
    the last 252) and a 159.0 last bar. Against the full panel the last bar is
    not a high (300 beats it); against the last 252 sessions it is.
    """
    s = [100.0] * 300
    s[10] = 300.0
    s[-1] = 159.0
    got = market_breadth({"SPIKE": s}, min_n=1)
    assert got["new_highs"] == 0  # the panel-window count sees the old spike
    assert got["new_highs_52w"] == 1  # the fixed-year count does not
    assert got["new_highs_52w_n"] == 1
    assert got["new_lows_52w"] == 0
    assert got["net_new_highs_52w"] == 1
    assert "252-session year" in got["basis"]


def test_the_52w_counts_match_a_known_five_name_panel():
    """Known-answer check on the shared fixture: 260 bars each, so all five names
    carry a year - one at its high (RISE), two at their low (FALL, FALL_FLAT)."""
    got = market_breadth(_five_name_panel(), min_n=5)
    assert got["new_highs_52w_n"] == 5
    assert got["new_highs_52w"] == 1
    assert got["new_lows_52w"] == 2
    assert got["net_new_highs_52w"] == -1
