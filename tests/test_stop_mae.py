"""Phase 5 of the entry/exit price engine: the measured stop distance.

``mae_stop_distance`` turns the MAE distribution of past closed decisions into
the stop distance it implies, so a stop can be measured rather than modelled.
Below the sample floor the read is a count, not a distance.
"""

from __future__ import annotations

import math

import pytest

from tradingagents.strategies.stop_mae import (
    DEFAULT_QUANTILE,
    MAE_MIN_SAMPLE,
    mae_stop_distance,
)

pytestmark = pytest.mark.timeout(600)

_TEN = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]


def test_quantile_of_the_sample_is_the_stop_distance():
    out = mae_stop_distance(_TEN)
    assert out["status"] == "OK"
    assert out["sample"] == 10
    assert out["quantile"] == pytest.approx(DEFAULT_QUANTILE)
    # linear-interpolation p90 of 0.01..0.10 is 0.091
    assert out["stop_fraction"] == pytest.approx(0.091)
    assert out["median"] == pytest.approx(0.055)


def test_a_higher_quantile_is_a_wider_stop():
    at70 = mae_stop_distance(_TEN, quantile=0.70)["stop_fraction"]
    at95 = mae_stop_distance(_TEN, quantile=0.95)["stop_fraction"]
    assert at70 < at95


def test_below_the_floor_is_no_sample_with_the_count():
    out = mae_stop_distance([0.02, 0.03])
    assert out["stop_fraction"] is None
    assert out["status"] == "NO_SAMPLE"
    assert out["sample"] == 2
    assert "min_sample" in out["reason"]
    # the median is still reported - it is a fact about the sample
    assert out["median"] == pytest.approx(0.025)


def test_no_observations_is_no_sample():
    out = mae_stop_distance([])
    assert out["stop_fraction"] is None
    assert out["status"] == "NO_SAMPLE"
    assert out["sample"] == 0
    assert out["reason"]


def test_sign_is_ignored_mae_is_a_loss_by_definition():
    signed = mae_stop_distance([-v for v in _TEN])
    unsigned = mae_stop_distance(_TEN)
    assert signed["stop_fraction"] == pytest.approx(unsigned["stop_fraction"])


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "n/a", True])
def test_unusable_observation_is_dropped_not_zeroed(bad):
    """A dropped observation must not be coerced to 0 - that would drag the
    quantile toward a stop that is far too tight."""
    out = mae_stop_distance(_TEN + [bad])
    assert out["sample"] == 10
    assert out["stop_fraction"] == pytest.approx(0.091)


def test_floor_is_actually_enforced_at_the_boundary():
    below = _TEN[: MAE_MIN_SAMPLE - 1]
    at = _TEN[: MAE_MIN_SAMPLE]
    assert mae_stop_distance(below)["status"] == "NO_SAMPLE"
    assert mae_stop_distance(at)["status"] == "OK"
    assert math.isfinite(mae_stop_distance(at)["stop_fraction"])
