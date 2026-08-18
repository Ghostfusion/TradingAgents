"""Phase 3 unit tests: momentum / 52w distance / composite rank."""

import pytest

from tradingagents.strategies.factors import (
    momentum, high_distance, vol_adjusted_momentum, percentile_rank,
    composite_score,
)


def _trend(closes, flat=100.0):
    return list(closes)


def test_momentum_uptrend_positive():
    series = [100.0 + 0.5 * i for i in range(300)]
    m = momentum(series, lookback=60, skip=5)
    assert m is not None and m > 0


def test_momentum_insufficient_data_none():
    assert momentum([1.0, 2.0], lookback=252) is None


def test_high_distance():
    series = [100.0] * 240 + [60.0] * 12  # far below 52w high
    d = high_distance(series)
    assert d is not None and d < 0
    series_high = [50.0] * 240 + [60.0] * 52  # new highs
    d2 = high_distance(series_high)
    assert d2 is not None and d2 >= 0.0


def test_vol_adjusted_momentum_finite():
    import math

    series = [1000.0 + 0.3 * i + 2.0 * math.sin(i) for i in range(300)]
    v = vol_adjusted_momentum(series)
    assert v is not None and v > 0


def test_percentile_rank():
    assert percentile_rank(1.0, [1.0, 2.0, 3.0]) == pytest.approx(1 / 3)
    assert percentile_rank(9.9, []) == 0.5


def test_composite_score_ranks_best_first():
    factors = {
        "AAA": {"ey": 0.05, "mom": 0.20},
        "BBB": {"ey": 0.03, "mom": 0.05},
        "CCC": {"ey": 0.01, "mom": -0.10},
    }
    scores = composite_score(factors)
    assert scores["AAA"] >= scores["BBB"] >= scores["CCC"]


def test_composite_missing_factor_skipped():
    factors = {"A": {"ey": 0.1}, "B": {"mom": 0.2}}
    scores = composite_score(factors)
    assert 0.0 <= scores["A"] <= 1.0
