"""Tier-1 quant formulas added from the taxonomy: Hurst exponent
(mean_reversion.py), TWAP (momentum.py), VPIN (orderflow.py).

All offline/deterministic. Endpoints verified against the standard
definitions (per working-agreement §7, formulas web-checked first).
"""

from tradingagents.strategies.mean_reversion import hurst_exponent
from tradingagents.strategies.momentum import twap
from tradingagents.strategies.orderflow import vpin

# --- Hurst exponent ---------------------------------------------------------

def test_hurst_short_series_returns_none():
    assert hurst_exponent([]) is None
    assert hurst_exponent([1.0, 2.0]) is None


def test_hurst_random_walk_around_half():
    import math
    import random

    random.seed(1)
    levels = [100.0]
    for _ in range(4000):
        levels.append(levels[-1] * (1.0 + random.gauss(0.0, 0.01)))
    # R/S must be fed the RETURN series (levels are biased high)
    rets = [math.log(levels[i] / levels[i - 1]) for i in range(1, len(levels))]
    h = hurst_exponent(rets)
    assert h is not None
    # random-walk returns land near 0.5 (finite-sample tolerance 0.25..0.75)
    assert 0.25 <= h <= 0.75, h


def test_hurst_mean_reverting_returns_below_half():
    import math
    import random

    random.seed(11)
    levels = [100.0]
    for _ in range(6000):
        levels.append(100.0 + 0.7 * (levels[-1] - 100.0) + random.gauss(0, 2.0))
    rets = [
        math.log(levels[i] / levels[i - 1])
        for i in range(1, len(levels))
        if levels[i - 1] > 0 and levels[i] > 0
    ]
    h = hurst_exponent(rets)
    # anti-persistent returns of a mean-reverting level process -> H < 0.5
    assert h is not None and h < 0.5, h


def test_hurst_trending_above_half():
    import random

    random.seed(3)
    levels = [100.0]
    for _ in range(4000):
        levels.append(levels[-1] * (1.0 + 0.002 + random.gauss(0, 0.01)))
    h = hurst_exponent(levels)
    assert h is not None and h > 0.5, h


# --- TWAP -------------------------------------------------------------------

def test_twap_simple_mean():
    assert twap([100.0, 102.0, 98.0, 104.0]) == 101.0


def test_twap_ignores_noise_and_empty():
    assert twap([100.0, None, 102.0]) == 101.0
    assert twap([]) is None


# --- VPIN -------------------------------------------------------------------

def test_vpin_balanced_flow_low_toxicity():
    trades = []
    for _ in range(100):
        trades.append({"volume": 1000, "side": "B"})
        trades.append({"volume": 1000, "side": "S"})
    out = vpin(trades, bucket_volume=100_000)
    assert out["vpin"] is not None and 0.0 <= out["vpin"] <= 0.2


def test_vpin_one_sided_max_toxicity():
    trades = [{"volume": 1000, "side": "B"} for _ in range(200)]
    out = vpin(trades, bucket_volume=100_000)
    assert out["vpin"] == 1.0


def test_vpin_empty_returns_vpin_none():
    out = vpin([])
    assert out["vpin"] is None
    assert out["unclassified_volume_share"] == 1.0
