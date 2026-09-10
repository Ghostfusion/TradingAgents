"""Normalized-cycle valuation - WDC/MU/SNDK 2026-09 review-loop follow-up.

A run-rate (TTM) DCF is distorted at a memory/NAND pricing peak or trough;
get_normalized_cycle_dcf anchors on the MEDIAN of the recent annual FCF series
so a cyclical reporter's intrinsic value does not ride the current cycle leg.
Pure None-safe; degrades when < 3 annual years exist.
"""
import pytest

from tradingagents.strategies.cycle_dcf import (
    MIN_YEARS,
    normalized_cycle_fcf,
    perpetuity_value,
)


def test_normalized_cycle_fcf_median_not_mean():
    # A classic memory cycle: one peak year, one trough, three mid years.
    series = [-5.8e9, 0.8e9, 2.5e9, 3.5e9, 1.1e9]
    r = normalized_cycle_fcf(series)
    assert r["n"] == 5
    assert r["median"] == pytest.approx(1.1e9)
    assert r["min"] == pytest.approx(-5.8e9)
    assert r["max"] == pytest.approx(3.5e9)
    assert r["mean"] == pytest.approx(0.42e9)
    # The median is far below the peak-year run-rate (the whole point).
    assert r["median"] < 3.4e9


def test_normalized_cycle_requires_min_years():
    r = normalized_cycle_fcf([1e9, 2e9])
    assert r["median"] is None
    assert r["n"] == 2
    r = normalized_cycle_fcf([])
    assert r["n"] == 0
    assert MIN_YEARS == 3


def test_perpetuity_value_and_degenerate():
    assert perpetuity_value(1.1e9, 0.10) == pytest.approx(1.1e9 * 1.025 / 0.075)
    # wacc <= g -> no finite value.
    assert perpetuity_value(1.1e9, 0.02) is None
    assert perpetuity_value(None, 0.10) is None
    assert perpetuity_value(1.1e9, 0.10, g=0.11) is None
