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
    """A 60-bar panel cannot produce a 52-week figure, and the basis says which
    window the counts came from so the read cannot be quoted as one."""
    short = {f"N{i}": [100.0 + j for j in range(60)] for i in range(25)}
    got = market_breadth(short)
    assert got["new_highs"] == 25
    assert "up to 60 bars each" in got["basis"]
    assert "52" not in got["basis"]
