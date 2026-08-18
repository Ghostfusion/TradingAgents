"""V1 unit tests: normalized earnings, percentiles, trap verdict."""

import pytest

from tradingagents.strategies.normalized import (
    median_norm_ebit, percentile_hist, accruals_ratio, trap_verdict,
    margin_of_safety,
)


def test_median_norm_ebit_uses_median_margin():
    revenues = [100.0] * 5
    margins = [0.05, 0.06, 0.04, 0.30, 0.05]  # peak 0.30 must NOT dominate
    neb = median_norm_ebit(revenues, ebit_margins=margins)
    assert neb is not None
    assert neb == pytest.approx(100.0 * 0.05, abs=0.01)  # median of sorted


def test_median_norm_ebit_from_series():
    revs = [100.0, 100.0, 100.0, 100.0, 1000.0]
    ebits = [4.0, 4.0, 3.0, 30.0, 50.0]
    neb = median_norm_ebit(revs, ebits=ebits)
    # margins: .04 .04 .03 .03 .05 -> median .04 * 1000 = 40
    assert neb == pytest.approx(0.04 * 1000.0, abs=0.01)


def test_percentile_hist():
    assert percentile_hist(5.0, [1, 2, 3, 4, 5]) == pytest.approx(1.0)
    assert percentile_hist(None, [1, 2, 3]) == 0.5
    assert percentile_hist(3.0, []) == 0.5


def test_accruals_ratio():
    r = accruals_ratio(net_income=10.0, cfo=6.0, total_assets=100.0)
    assert r == pytest.approx(0.04)
    assert accruals_ratio(None, 6.0, 100.0) is None


def test_trap_verdict_low():
    v = trap_verdict(f_score=8, m_score=-3.0, z_score=4.0,
                     mom12=0.2, accrual=0.01)
    assert v["level"] == "LOW"


def test_trap_verdict_high_on_multiple_triggers():
    v = trap_verdict(f_score=2, m_score=-0.5, z_score=1.2,
                     mom12=-0.3, accrual=0.10)
    assert v["level"] == "HIGH"
    assert len(v["evidence"]) >= 2


def test_margin_of_safety():
    assert margin_of_safety(price=80.0, intrinsic=100.0) == pytest.approx(0.2)
    assert margin_of_safety(price=100.0, intrinsic=None) is None
