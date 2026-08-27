"""Hermetic tests for the new technical factors (Aroon, Fisher, Chaikin,
Elder-Ray, Supertrend, volume profile) and the market-session module
(opening range, gap type, order imbalance, premarket liquidity, post-close
confirmation). Pure/offline; no network.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradingagents.strategies import (  # noqa: E402
    market_session as ms,
    technical_factors as tf,
)

pytestmark = pytest.mark.timeout(120)


def _uptrend(n=60):
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    vols = [1_000_000.0] * n
    return closes, highs, lows, vols


def _random_walk(seed=7, n=80):
    import random

    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1 + rng.uniform(-0.02, 0.02)))
    highs = [c * (1 + rng.uniform(0.005, 0.02)) for c in closes]
    lows = [c * (1 - rng.uniform(0.005, 0.02)) for c in closes]
    vols = [rng.uniform(500_000, 2_000_000) for _ in closes]
    return closes, highs, lows, vols


# ---------------------------------------------------------------------------
# Technical factors
# ---------------------------------------------------------------------------


def test_aroon_uptrend():
    _, highs, lows, _ = _uptrend()
    r = tf.aroon(highs, lows)
    assert r["aroon_up"] == 100.0
    assert r["aroon_down"] == 0.0
    assert r["verdict"] == "uptrend"


def test_aroon_insufficient():
    r = tf.aroon([1, 2], [1, 2])
    assert r["aroon_up"] is None and r["aroon_down"] is None


def test_fisher_transform_returns_values():
    closes, _, _, _ = _random_walk()
    r = tf.fisher_transform(closes)
    assert r["fisher"] is not None
    assert r["trigger"] is not None
    assert r["verdict"] in ("up", "down", "reversal-up", "reversal-down")


def test_fisher_insufficient():
    r = tf.fisher_transform([1, 2])
    assert r["fisher"] is None


def test_chaikin_oscillator_asymmetric():
    closes, highs, lows, vols = _random_walk()
    v = tf.chaikin_oscillator(highs, lows, closes, vols)
    assert v is not None
    assert isinstance(v, float)


def test_chaikin_insufficient():
    assert tf.chaikin_oscillator([1], [1], [1], [1]) is None


def test_elder_ray_returns_powers():
    closes, highs, lows, _ = _random_walk()
    r = tf.elder_ray(highs, lows, closes)
    assert r["bull_power"] is not None
    assert r["bear_power"] is not None
    assert r["verdict"] in ("buying-pressure", "selling-pressure", "mixed-bull", "mixed-bear")


def test_elder_ray_insufficient():
    r = tf.elder_ray([1], [1], [1])
    assert r["bull_power"] is None


def test_supertrend_returns_line():
    closes, highs, lows, _ = _random_walk()
    r = tf.supertrend(highs, lows, closes)
    assert r["line"] is not None
    assert r["direction"] in ("up", "down")


def test_supertrend_insufficient():
    r = tf.supertrend([1], [1], [1])
    assert r["line"] is None


def test_volume_profile_returns_poc():
    closes, _, _, vols = _random_walk()
    r = tf.volume_profile(closes, vols)
    assert r["poc"] is not None
    assert r["value_area_high"] is not None
    assert r["value_area_low"] is not None
    assert r["value_area_low"] <= r["poc"] <= r["value_area_high"]


def test_volume_profile_insufficient():
    r = tf.volume_profile([1], [1])
    assert r["poc"] is None


# ---------------------------------------------------------------------------
# Market session
# ---------------------------------------------------------------------------


def test_opening_range_up_breakout():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 105])
    assert r["or_high"] == 104.0
    assert r["or_low"] == 96.0
    assert r["breakout"] == "up"
    assert r["stop"] == 96.0
    assert r["target"] == 120.0  # or_high + 2*width


def test_opening_range_down_breakout():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 95])
    assert r["breakout"] == "down"
    assert r["stop"] == 104.0
    assert r["target"] == 80.0


def test_opening_range_inside():
    r = ms.opening_range([101, 102, 103, 104], [99, 98, 97, 96],
                         closes=[100, 101, 102, 100])
    assert r["breakout"] is None


def test_opening_range_insufficient():
    r = ms.opening_range([101], [99])
    assert r["or_high"] is None


def test_gap_type_breakaway():
    closes = [100.0] * 25 + [103.0]
    highs = [101.0] * 25 + [104.0]
    lows = [99.0] * 25 + [102.0]
    vols = [1_000_000.0] * 25 + [3_000_000.0]
    r = ms.gap_type(closes, highs, lows, vols)
    assert r["type"] == "breakaway"
    assert r["gap_pct"] is not None
    assert r["fill_probability"] is not None


def test_gap_type_common():
    closes = [100.0] * 25 + [100.5]
    highs = [101.0] * 25 + [101.0]
    lows = [99.0] * 25 + [99.5]
    vols = [1_000_000.0] * 26
    r = ms.gap_type(closes, highs, lows, vols)
    assert r["type"] == "common"
    assert r["fill_probability"] >= 0.5


def test_gap_type_insufficient():
    r = ms.gap_type([1, 2], [1, 2], [1, 2], [1, 2])
    assert r["type"] is None


def test_order_imbalance_buy_heavy():
    r = ms.order_imbalance(0.5, -0.2)
    assert r["verdict"] == "buy-heavy"
    assert r["ratio"] > 0.3


def test_order_imbalance_sell_heavy():
    r = ms.order_imbalance(-0.5, 0.2)
    assert r["verdict"] == "sell-heavy"


def test_order_imbalance_balanced():
    r = ms.order_imbalance(0.1, -0.1)
    assert r["verdict"] == "balanced"


def test_order_imbalance_none():
    r = ms.order_imbalance(None, None)
    assert r["verdict"] is None


def test_premarket_liquidity_thin():
    r = ms.premarket_liquidity(50_000, 1_000_000)
    assert r["verdict"] == "thin"
    assert r["ratio"] == 0.05


def test_premarket_liquidity_liquid():
    r = ms.premarket_liquidity(200_000, 1_000_000)
    assert r["verdict"] == "liquid"


def test_premarket_liquidity_none():
    r = ms.premarket_liquidity(None, None)
    assert r["verdict"] is None


def test_post_close_stopped_out():
    r = ms.post_close_confirmation(95, 100, 120)
    assert r["verdict"] == "stopped-out"
    assert r["action"] == "exit"


def test_post_close_target_hit():
    r = ms.post_close_confirmation(125, 100, 120)
    assert r["verdict"] == "target-hit"
    assert r["action"] == "take-profit"


def test_post_close_holding():
    r = ms.post_close_confirmation(110, 100, 120)
    assert r["verdict"] == "holding"
    assert r["action"] == "hold"


def test_post_close_none():
    r = ms.post_close_confirmation(None, 100, 120)
    assert r["verdict"] is None
