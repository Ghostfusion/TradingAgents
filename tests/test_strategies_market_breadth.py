"""P0-3: the market-wide breadth producer (percent-above-MA + A/D + highs/lows),
plus X3's Marchenko-Pastur lower-spectrum read over ONE panel."""

import math

import numpy as np
import pytest

from tradingagents.strategies.market_breadth import market_breadth, mp_below_count
from tradingagents.strategies.sector_breadth import mp_lower_spectrum, multi_breadth
from tradingagents.strategies.sector_rank import SPDR_SECTORS

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



# ---------------------------------------------------------------------------
# ad_ratio - the leg `technical_score` declares with THIS module as producer
# ---------------------------------------------------------------------------


def test_ad_ratio_is_the_advance_decline_ratio_over_the_panel():
    """`technical_score` declares `ad_ratio` with `market_breadth` as its
    producer and a (-0.30, 0.30) ramp, so the module must emit the RATIO and
    not only the difference: one producer, two readings of one numerator
    (rule 15)."""
    panel = {f"UP{i}": [100.0 + 0.1 * j for j in range(260)] for i in range(20)}
    panel.update({f"DN{i}": [100.0 - 0.1 * j for j in range(260)] for i in range(5)})
    got = market_breadth(panel)
    assert got["advancers"] == 20
    assert got["decliners"] == 5
    assert got["ad_ratio"] == pytest.approx(0.6)
    assert got["ad_ratio"] == pytest.approx(got["advance_decline"] / got["n"])


def test_ad_ratio_is_withheld_on_a_small_sample_like_the_percentages():
    """A 3-name advance/decline ratio is not a market read (master rule 1)."""
    got = market_breadth({f"X{i}": [100.0 + j for j in range(60)] for i in range(3)})
    assert got["small_sample"] is True
    assert got["ad_ratio"] is None
    assert got["pct_above_50d"] is None


# ---------------------------------------------------------------------------
# X3 - the Marchenko-Pastur lower-spectrum read: ONE read per PANEL
# ---------------------------------------------------------------------------


def _two_block_panel(window=44):
    """``(panel, return rows)`` for the 11 SPDR sector ETFs in two blocks.

    The keys are ``sector_rank``'s own ``SPDR_SECTORS`` - the panel this read is
    for, not a synthetic universe. Six names share one return vector and five
    share another; the two vectors are ``sin``/``cos`` over one full period, so
    they are both zero-mean and mutually orthogonal. The panel correlation
    matrix is therefore ``[[J6, 0], [0, J5]]``, whose eigenvalues are
    ``{6, 5, 0 x 9}`` - so at ``window=44`` (bound
    ``(1 - sqrt(11/44))**2 = 0.25``) the count is known by construction: 9.
    """
    etfs = sorted(SPDR_SECTORS)
    assert len(etfs) == 11  # the panel X3 reads, exactly
    k = np.arange(window, dtype=float)
    ra = 0.01 * np.sin(2.0 * np.pi * k / window)
    rb = 0.01 * np.cos(2.0 * np.pi * k / window)

    def closes(rets):
        return [1000.0] + list(1000.0 * np.cumprod(1.0 + np.asarray(rets)))

    panel = {etfs[i]: closes(ra) for i in range(6)}
    panel.update({etfs[i]: closes(rb) for i in range(6, 11)})
    return panel, [ra] * 6 + [rb] * 5


def test_mp_below_count_unavailable_when_window_not_longer_than_names():
    """X3 acceptance: a window no longer than the panel is ``unavailable`` -
    NOT ``count == 0`` - and at a longer window the count is the number of
    eigenvalues below ``(1 - sqrt(n/w))^2``, with that bound and the window it
    was computed over reported.

    ``w == n`` is the case a ``w <= n`` -> ``w < n`` guard turns into a measured
    ``count == 0``: there the bound collapses to 0, so "nothing below the
    bound" would be an artifact of a degenerate limit, not a panel reading.
    """
    panel, rows = _two_block_panel(44)
    corr = np.corrcoef(np.asarray(rows))
    assert corr.shape == (11, 11)

    for window in (11, 5):  # w == n, then w < n
        refused = mp_below_count(corr, 11, window)
        assert refused["status"] == "unavailable"
        assert refused["count"] is None  # never a zero standing in for a refusal
        assert refused["mp_lower"] is None
        assert refused["window"] == window
        assert refused["n_names"] == 11

    read = mp_below_count(corr, 11, 44)
    assert read["status"] == "ok"
    assert read["mp_lower"] == pytest.approx((1.0 - math.sqrt(11 / 44)) ** 2)  # 0.25
    assert read["count"] == 9  # [[J6, 0], [0, J5]] -> {6, 5, 0 x 9}
    assert read["count"] == int((np.linalg.eigvalsh(corr) < read["mp_lower"]).sum())
    assert read["window"] == 44 and read["n_names"] == 11  # the window travels

    # The gate off leaves the existing breadth output exactly as it was: the
    # shared producer's shape and values, and no spectrum key.
    snapshot = multi_breadth(
        {"XLK": {"A": [100.0 + j for j in range(30)],
                 "B": [100.0 - j for j in range(30)]}},
        min_n=1,
    )
    assert snapshot == {"XLK": {"n": 2, "pct_20d": 50.0, "pct_50d": 0.0,
                                "pct_200d": 0.0, "small_sample": False, "min_n": 1}}
    assert "mp_lower_spectrum" not in market_breadth(panel, min_n=1, cfg={})


def test_the_panel_spectrum_is_gated_and_adds_one_key_that_moves_nothing():
    """The gate is the only switch. Off, the read returns None and the breadth
    output carries no spectrum key; on, it adds that ONE key - the panel's
    count, never a per-name one - and every other number is identical."""
    panel, _ = _two_block_panel(44)
    off = market_breadth(panel, min_n=1, cfg={})
    assert "mp_lower_spectrum" not in off
    assert mp_lower_spectrum(panel, window=44, cfg={}) is None

    on = market_breadth(panel, min_n=1, cfg={"enable_mp_lower_spectrum": True},
                        spectrum_window=44)
    spectrum = on["mp_lower_spectrum"]
    assert spectrum["status"] == "ok"
    assert spectrum["count"] == 9
    assert spectrum["window"] == 44
    assert spectrum["n_names"] == 11 and spectrum["panel_n"] == 11
    assert {k: v for k, v in on.items() if k != "mp_lower_spectrum"} == off


def test_the_panel_spectrum_refuses_a_panel_that_cannot_carry_the_window():
    """Rule 4: a panel of short series has no window to read, so the read is
    ``unavailable`` with its coverage printed - never a count over padded
    names, and never a zero."""
    short = {etf: [100.0 + j for j in range(10)] for etf in sorted(SPDR_SECTORS)}
    refused = mp_lower_spectrum(short, window=44,
                                cfg={"enable_mp_lower_spectrum": True})
    assert refused["status"] == "unavailable"
    assert refused["count"] is None and refused["mp_lower"] is None
    assert refused["n_names"] == 0 and refused["panel_n"] == 11
    assert "44" in refused["unavailable"]
