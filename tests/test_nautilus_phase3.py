"""Phase-3 tests: config range validation + the Nautilus-style stats."""

import pytest

from tradingagents.default_config import DEFAULT_CONFIG, validate_config
from tradingagents.strategies import evaluate as ev

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# E2 - validate_config
# ---------------------------------------------------------------------------


def test_validate_config_healthy_default():
    assert validate_config(DEFAULT_CONFIG) == []


def test_validate_config_flags_out_of_range_fraction():
    bad = dict(DEFAULT_CONFIG, kelly_fraction=1.7)
    assert any("kelly_fraction=1.7" in v for v in validate_config(bad))


def test_validate_config_flags_negative_window():
    bad = dict(DEFAULT_CONFIG, catalyst_window_days=-3)
    assert any("catalyst_window_days=-3.0" in v for v in validate_config(bad))


def test_validate_config_hwm_tier_monotonic():
    bad = dict(DEFAULT_CONFIG, risk_hwm_soft_pct=0.3, risk_hwm_hard_pct=0.1)
    assert any("must be <=" in v for v in validate_config(bad))


def test_validate_config_tranche_weights_sum():
    bad = dict(DEFAULT_CONFIG, tranche_weights=[0.5, 0.5, 0.5])
    assert any("sum to 1.5000" in v for v in validate_config(bad))


def test_validate_config_non_numeric():
    bad = dict(DEFAULT_CONFIG, target_vol="high")
    assert any("target_vol is not a number" in v for v in validate_config(bad))


def test_validate_config_missing_keys_ok():
    # A sub-slice config must not crash: missing keys are simply skipped.
    assert validate_config({"kelly_fraction": 0.2}) == []


def test_validate_config_accepts_zero_where_off_is_valid():
    bad = dict(DEFAULT_CONFIG, catalyst_hard_block_days=0)  # 0 = off
    assert not any("catalyst_hard_block_days" in v for v in validate_config(bad))


# ---------------------------------------------------------------------------
# E1 - calmar / ulcer / capture / tail / expectancy
# ---------------------------------------------------------------------------


def test_calmar_ratio_positive():
    ret = [0.01, -0.005, 0.02, -0.01, 0.015, 0.0, -0.02, 0.03]
    c = ev.calmar_ratio(ret)
    assert c is not None and c > 0
    # Compound growth over max drawdown magnitude.
    eq = ev.equity_curve(ret)
    assert c == pytest.approx(ev.cagr(ret) / ev.max_drawdown(eq))


def test_calmar_ratio_none_on_monotone_up():
    # No drawdown -> no meaningful ratio.
    assert ev.calmar_ratio([0.01, 0.01, 0.01, 0.01]) is None
    assert ev.calmar_ratio([0.01]) is None


def test_ulcer_index_positive_and_bounded():
    ret = [0.01, -0.02, -0.01, 0.005]
    u = ev.ulcer_index(ret)
    assert u is not None and u > 0


def test_ulcer_index_none_on_no_drawdown():
    assert ev.ulcer_index([0.01, 0.02, 0.03]) == pytest.approx(0.0)
    assert ev.ulcer_index([0.01]) is None


def test_capture_ratio_up_and_down():
    a = [0.01, -0.005, 0.02, -0.01, 0.015, 0.0, -0.02, 0.03]
    b = [0.005, 0.001, 0.01, -0.002, 0.008, 0.0, -0.005, 0.012]
    up = ev.capture_ratio(a, b, up=True)
    down = ev.capture_ratio(a, b, up=False)
    assert up is not None and down is not None
    # In the up periods above, the algo out-returned the bench -> up capture > 0.


def test_capture_ratio_none_insufficient_or_flat():
    assert ev.capture_ratio([0.01], [0.0]) is None  # <2 aligned
    assert ev.capture_ratio([0.01, 0.02], [0.0, 0.0]) is None  # bench flat


def test_tail_ratio_asymmetric():
    # Returns series with +3 winners and -1 losers -> ratio 3.0.
    assert ev.tail_ratio([3.0, -1.0, 3.0, -1.0]) == pytest.approx(3.0)
    assert ev.tail_ratio([1.0, 2.0, 3.0, -1.5]) == pytest.approx(2.0 / 1.5)
    assert ev.tail_ratio([1.0, 2.0]) is None   # no losses
    assert ev.tail_ratio([-1.0, -2.0]) is None  # no wins


def test_expectancy_stats_shape_and_values():
    s = ev.expectancy_stats([250.0, 200.0], [100.0])
    assert s["n_trades"] == 3
    assert s["win_rate"] == pytest.approx(2 / 3)
    assert s["profit_factor"] == pytest.approx(450.0 / 100.0)
    assert s["expectancy"] == pytest.approx((2 / 3) * 225.0 - (1 / 3) * 100.0)
    assert s["tail_ratio"] == pytest.approx(2.25)


def test_expectancy_stats_empty():
    assert ev.expectancy_stats([], []) is None
    assert ev.expectancy_stats([], []) is None
