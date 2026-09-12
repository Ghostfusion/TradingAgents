"""Conformal valuation bands: calibration, coverage honesty, min_n floor."""

import random

import pytest

from tradingagents.strategies.conformal import (
    calibrate,
    coverage,
    quantile_band,
    rolling_band,
)


def test_calibrate_uses_conformal_order_statistic():
    # n=10, alpha=0.1 -> ceil(11 * 0.9) = 10 -> the largest calibration score.
    assert calibrate(range(1, 11), 0.1) == 10.0
    # n=5, alpha=0.2 -> ceil(6 * 0.8) = 5 -> the largest.
    assert calibrate([5, 1, 3, 2, 4], 0.2) == 5.0
    # n=4, alpha=0.5 -> ceil(5 * 0.5) = 3 -> the 3rd smallest.
    assert calibrate([40, 10, 30, 20], 0.5) == 30.0


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 2.0, float("nan")])
def test_calibrate_rejects_alpha_outside_unit_interval(alpha):
    assert calibrate([1.0, 2.0, 3.0], alpha) is None


def test_calibrate_none_when_empty_or_degenerate():
    assert calibrate([], 0.1) is None
    assert calibrate(None, 0.1) is None
    assert calibrate([None, None], 0.1) is None
    assert calibrate([float("nan"), float("inf")], 0.1) is None


def test_quantile_band_without_scores_is_point_spread():
    band = quantile_band([1.0, 2.0, 3.0, 4.0, 5.0], 0.2)
    assert band is not None
    assert band["low"] == pytest.approx(1.4)  # q[0.10] of [1..5]
    assert band["high"] == pytest.approx(4.6)  # q[0.90] of [1..5]
    assert band["nominal"] == pytest.approx(0.8)
    assert "basis" in band


def test_quantile_band_widened_by_calibrated_quantile():
    band = quantile_band([1.0, 2.0, 3.0, 4.0, 5.0], 0.2, scores=[1.0, 2.0, 3.0, 4.0, 5.0])
    assert band is not None
    # calibrate([1..5], 0.2) == 5.0 -> widen both ends by 5.
    assert band["low"] == pytest.approx(1.4 - 5.0)
    assert band["high"] == pytest.approx(4.6 + 5.0)


def test_quantile_band_none_on_degenerate_inputs():
    assert quantile_band([], 0.1) is None
    assert quantile_band([1.0], 0.0) is None
    # scores supplied but no usable calibration scores -> refuse.
    assert quantile_band([1.0, 2.0], 0.1, scores=[]) is None


def test_coverage_counts_actuals_inside_band():
    pairs = [(0.0, 1.0), (0.0, 3.0), (0.0, 5.0), (0.0, 9.0)]
    assert coverage(pairs, 2.0, 5.0) == pytest.approx(2 / 4)
    assert coverage(pairs, 2.0, 2.0) == pytest.approx(0.0)
    assert coverage([], 0.0, 1.0) is None
    assert coverage(pairs, None, 1.0) is None


def _synthetic_pairs(n=300, prediction=100.0, sigma=5.0, seed=1234):
    rng = random.Random(seed)
    return [(prediction, prediction + rng.gauss(0.0, sigma)) for _ in range(n)]


def test_rolling_band_coverage_tracks_nominal():
    pairs = _synthetic_pairs()
    band = rolling_band(pairs, window=250, alpha=0.1, min_n=40)
    assert band is not None
    assert band["nominal"] == pytest.approx(0.9)
    assert band["window"] == 250
    assert band["n"] == 250
    # realized coverage is always reported beside the nominal level.
    assert band["realized_coverage"] is not None
    # exchangeability holds here (i.i.d. Gaussian residuals), so the calibrated
    # empirical quantile must land within tolerance of the nominal level.
    assert abs(band["realized_coverage"] - 0.9) <= 0.05


def test_rolling_band_bounds_match_calibrated_quantile_of_residuals():
    pairs = _synthetic_pairs()
    band = rolling_band(pairs, window=250, alpha=0.1, min_n=40)
    # hand-compute: Q = conformal 1-alpha quantile of the last 250 |residuals|,
    # applied around the constant point prediction (spread is zero).
    calib = pairs[-250:]
    scores = sorted(abs(actual - pred) for pred, actual in calib)
    import math

    level = math.ceil((len(scores) + 1) * (1.0 - 0.1))
    q = scores[level - 1]
    assert q != pytest.approx(0.05)  # guard: the band is not a constant widen
    assert band["low"] == pytest.approx(100.0 - q)
    assert band["high"] == pytest.approx(100.0 + q)


def test_rolling_band_consumer_contract_inside_not_flagged_outside_is():
    pairs = _synthetic_pairs()
    band = rolling_band(pairs, window=250, alpha=0.1, min_n=40)
    inside = (band["low"] + band["high"]) / 2.0
    outside_hi = band["high"] * 2.0
    outside_lo = band["low"] - abs(band["low"])
    assert band["low"] <= inside <= band["high"]
    assert not (band["low"] <= outside_hi <= band["high"])
    assert not (band["low"] <= outside_lo <= band["high"])


def test_rolling_band_none_below_min_n():
    pairs = _synthetic_pairs(n=30)
    assert rolling_band(pairs, window=250, alpha=0.1, min_n=40) is None
    # exactly at the floor is enough
    ok = rolling_band(_synthetic_pairs(n=40), window=250, alpha=0.1, min_n=40)
    assert ok is not None
    assert ok["n"] == 40


def test_rolling_band_none_on_invalid_alpha_or_empty():
    assert rolling_band([], 250, 0.1, 40) is None
    assert rolling_band(_synthetic_pairs(n=100), 250, 1.5, 40) is None
    # non-finite pairs are dropped; too few survive -> None
    bad = [(float("nan"), 1.0)] * 100
    assert rolling_band(bad, 250, 0.1, 40) is None
