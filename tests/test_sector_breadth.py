"""Tests for the sector breadth layer (strategies/sector_breadth.py).

Covers the multi-timeframe breadth matrix (20/50/200 with the n-gate), the
McClellan oscillator + Summation Index (cumulative-sum, cold-start guard,
sign separation), the RRG heading/trajectory flags, and the advisory MSI
zone mapping. All hermetic (synthetic, monotone + oscillating universes).
"""

import random

import pytest

from tradingagents.strategies.sector_breadth import (
    mcclellan_read,
    msi_zone,
    multi_breadth,
    rrg_heading,
)

pytestmark = pytest.mark.timeout(90)


def _mono(n=260, drift=0.006):
    return [100.0 * (1 + drift) ** i for i in range(n)]


def _mixed(n=260, up_prob=0.6, seed=1):
    rnd = random.Random(seed)
    px, out = 100.0, []
    for _ in range(n):
        dirn = 1.0 if rnd.random() < up_prob else -1.0
        px *= 1 + dirn * rnd.uniform(0.001, 0.02)
        out.append(px)
    return out


def _map(n=25, fn=_mono, **kw):
    return {f"SSS{i}": fn(**kw) for i in range(n)}


# ---------------------------------------------------------------------------
# multi_breadth
# ---------------------------------------------------------------------------


def test_multi_breadth_healthy_up():
    mb = multi_breadth({"XLK": _map(fn=_mono, drift=0.006)}, min_n=20)
    b = mb["XLK"]
    assert b["n"] == 25 and b["small_sample"] is False
    assert b["pct_50d"] == 100.0  # all monotone-up above SMA50
    assert b["pct_20d"] == 100.0 and b["pct_200d"] == 100.0
    # a flat/declining member drops the fraction below 100
    mb2 = multi_breadth({"XLK": {f"SSS{i}": _mono(drift=0.006 if i else -0.004)
                                  for i in range(25)}}, min_n=20)
    assert mb2["XLK"]["pct_50d"] < 100.0


def test_multi_breadth_small_sample_gate():
    mb = multi_breadth({"XLE": _map(n=3, fn=_mono)}, min_n=20)
    assert mb["XLE"]["small_sample"] is True
    assert mb["XLE"]["n"] == 3  # raw n kept (honest display, not a fake %)


def test_multi_breadth_none_safe():
    mb = multi_breadth({"XLK": {}})
    assert mb["XLK"]["n"] == 0 and mb["XLK"]["pct_50d"] is None


# ---------------------------------------------------------------------------
# mcclellan
# ---------------------------------------------------------------------------


def test_mcclellan_sign_separates_up_vs_down():
    # deterministic tails: the last 40 bars are all-up for H, all-down for L
    def tail(series, up):
        last = series[-1]
        tail_bars = [last]
        for _ in range(40):
            last = last * (1.01 if up else 0.99)
            tail_bars.append(last)
        return series + tail_bars
    up = mcclellan_read({"H": {f"H{i}": tail(_mixed(up_prob=0.5, seed=3 + i), True)
                               for i in range(25)}})["H"]
    dn = mcclellan_read({"L": {f"L{i}": tail(_mixed(up_prob=0.5, seed=9 + i), False)
                               for i in range(25)}})["L"]
    assert up["mo"] is not None and dn["mo"] is not None
    assert up["mo"] > dn["mo"]  # rising tail -> oscillator positive
    assert up["burn_in"] is False and dn["burn_in"] is False


def test_mcclellan_cold_start_guard():
    # 30-bar members => the aligned A/D series is 29 bars < burn-in 60
    short = mcclellan_read({"H": {f"H{i}": _mono(n=30) for i in range(25)}},
                           burn_in=60)["H"]
    assert short["burn_in"] is True
    assert short["mo"] is None and short["msi"] is None  # not trusted pre-burn-in


def test_mcclellan_msi_is_cumulative_sum():
    # monotone-up gives a constant positive net => the oscillator is the EMA
    # gap of a constant => 0, but the MSI (cumsum) is non-zero over the ramp.
    mc = mcclellan_read({"H": _map(fn=_mixed, up_prob=0.9, seed=5)})["H"]
    assert mc["msi"] is not None
    assert mc["n"] >= 20


def test_mcclellan_none_safe():
    mc = mcclellan_read({"XLK": {}})
    assert mc["XLK"]["mo"] is None and mc["XLK"]["msi"] is None


# ---------------------------------------------------------------------------
# rrg heading + msi zone
# ---------------------------------------------------------------------------


def test_rrg_heading_constructive_and_trap():
    ne = rrg_heading(103.0, 102.0, 101.0, 101.0)
    assert ne["heading_deg"] < 90.0 and ne["constructive"] is True
    sw = rrg_heading(104.0, 99.0, 106.0, 101.0)
    assert 180.0 <= sw["heading_deg"] <= 270.0
    assert sw["weakening_trap"] is True and sw["constructive"] is False
    assert rrg_heading(None, 1.0, 1.0, 1.0)["heading_deg"] is None


def test_msi_zone_mapping():
    assert msi_zone(200, 30, 2000)["zone"] == "Expansion"
    assert msi_zone(-300, -40, 2000)["zone"] == "Structural Distribution"
    assert msi_zone(1300, -5, 2000)["zone"] == "Climax Exhaustion"
    assert msi_zone(-1100, 20, 2000)["zone"] == "Washout Capitulation"
    assert msi_zone(None, None, 2000)["allow_new_longs"] is None  # cold start
