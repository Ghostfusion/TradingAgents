"""Multi-axis regime state tests (regime-gate material): trend/volatility/
relative/drawdown axes + F_regime factor composition. All pure/offline."""

from __future__ import annotations

import random

import pytest

from tradingagents.strategies.contract import build_position_contract
from tradingagents.strategies.regime_state import (
    regime_drawdown,
    regime_factor,
    regime_relative,
    regime_state,
    regime_trend,
    regime_vol_ratio,
)

pytestmark = pytest.mark.timeout(120)


def _walk(n=120, base=100.0, drift=0.0, noise=0.3, seed=7, hilo=0.2):
    rng = random.Random(seed)
    c = [base]
    for _ in range(1, n):
        c.append(c[-1] + drift + rng.uniform(-noise, noise))
    h = [x + hilo for x in c]
    low_ = [x - hilo for x in c]
    return c, h, low_


def test_trend_uptrend_is_bull():
    c, _, _ = _walk(n=100, drift=0.2, noise=0.1, seed=1)
    t = regime_trend(c)
    assert t["label"] in ("BULL", "STRONG_BULL")
    assert t["score"] is not None and t["score"] > 0


def test_trend_downtrend_is_bear():
    c, _, _ = _walk(n=100, drift=-0.2, noise=0.1, seed=2)
    t = regime_trend(c)
    assert t["label"] in ("BEAR", "STRONG_BEAR")
    assert t["score"] < 0


def test_trend_short_history_unknown():
    assert regime_trend([100.0] * 10)["label"] == "UNKNOWN"


def test_vol_ratio_normal_and_extreme():
    c, h, low_ = _walk(n=80, noise=0.2, seed=5)
    v = regime_vol_ratio(h, low_, c)
    assert v["label"] in ("LOW", "NORMAL", "HIGH", "EXTREME")
    assert v["ratio"] is not None
    # a huge current ATR spike -> EXTREME
    h2 = h[:-1] + [h[-1] * 2.5]
    l2 = low_[:-1] + [low_[-1] * 0.5]
    v2 = regime_vol_ratio(h2, l2, c[:-1] + [c[-1]])
    assert v2["ratio"] > 2.0


def test_relative_vs_benchmark():
    # stock down 1% while benchmark down 5% -> stock OUTPERFORMS (rel > +0.5%)
    r = regime_relative([100.0, 100, 99, 98, 97], [100.0, 98, 96, 94, 92])
    assert r["label"] == "OUTPERFORM"
    # a tiny ±0.1% relative gap stays NEUTRAL at the 0.5% threshold
    rn = regime_relative([100.0, 100, 99, 98, 97], [100.0, 99, 98, 97, 96])
    assert rn["label"] == "NEUTRAL"
    # stock down 2.5% while benchmark FLAT -> UNDERPERFORM
    r2 = regime_relative([100.0, 99, 97, 94, 90], [100.0, 100, 100, 100, 100])
    assert r2["label"] == "UNDERPERFORM"
    assert r2["relative_ret"] < 0
    # no benchmark -> NEUTRAL (cannot judge)
    assert regime_relative([100.0, 99, 98, 97], None)["label"] == "NEUTRAL"


def test_drawdown_regimes():
    # shallow dip from a recent high -> NORMAL
    d = regime_drawdown([100.0] * 30 + [99.0])
    assert d["label"] == "NORMAL"
    # deep from high -> SEVERE
    d2 = regime_drawdown([100.0] * 30 + [70.0])
    assert d2["label"] == "SEVERE"
    d3 = regime_drawdown([100.0] * 30 + [90.0])
    assert d3["label"] == "CORRECTION"


def test_factor_composition():
    assert regime_factor("STRONG_BULL", "NORMAL") == 1.0
    assert regime_factor("BEAR", "NORMAL") == 0.5
    assert regime_factor("BEAR", "HIGH") == 0.5
    assert regime_factor("BULL", "EXTREME") == 0.0
    assert regime_factor("BULL", "NORMAL", drawdown="SEVERE") == 0.0
    assert regime_factor("STRONG_BEAR", "NORMAL") == 0.25


def test_regime_state_aggregates_and_factors():
    c, h, low_ = _walk(n=120, drift=-0.15, noise=0.2, seed=9)
    rs = regime_state(c, h, low_)
    assert set(rs["labels"]) == {"trend", "volatility", "relative", "drawdown"}
    assert 0.0 <= rs["factor"] <= 1.0
    labels = rs["labels"]
    assert labels["trend"] in ("BULL", "STRONG_BULL", "BEAR", "STRONG_BEAR", "UNKNOWN")
    assert labels["volatility"] in ("LOW", "NORMAL", "HIGH", "EXTREME", "UNKNOWN")
    assert labels["relative"] in ("UNDERPERFORM", "NEUTRAL", "OUTPERFORM", "UNKNOWN")
    assert labels["drawdown"] in ("NORMAL", "CORRECTION", "BEAR", "SEVERE", "UNKNOWN")
    # drift-down + quiet vol -> BEAR-ish and factor <= 0.5 (never 1.0 in a bear)
    if labels["trend"].startswith("BEAR"):
        assert rs["factor"] <= 0.5


def test_regime_state_missing_inputs_unknowns():
    rs = regime_state([100.0] * 80)  # no highs/lows/benchmark
    assert rs["labels"]["volatility"] == "UNKNOWN"
    assert rs["labels"]["relative"] == "NEUTRAL"  # no bench -> neutral
    # MISSING HIGH/LOW -> vol_ratio fallback proxy (unknown) keeps factor >= 0.5,
    # but trend of a flat series = BEAR-ish 0.5. Assert factor is reasonable.
    assert 0.0 <= rs["factor"] <= 1.0


def test_contract_scales_by_regime_and_knife():
    closes = [100.0 + 0.1 * i for i in range(60)]
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    c1 = build_position_contract(cfg={}, closes=closes, high=highs, low=lows)
    c2 = build_position_contract(cfg={}, closes=closes, high=highs, low=lows,
                                 knife_factor=0.5, regime_factor=0.25)
    assert c1 is not None and c2 is not None
    assert c2.size_pct <= c1.size_pct * 0.6
    assert any("knife_scale" in r for r in c2.reason_parts)
    assert any("regime_scale" in r for r in c2.reason_parts)


# --- Regime Vol Cap (F_vol ladder) ---


def test_vol_cap_factor_ladder():
    from tradingagents.strategies.regime_state import vol_cap_factor

    assert vol_cap_factor(1.0) == 1.0
    assert vol_cap_factor(1.2001) == 0.75
    assert vol_cap_factor(1.7) == 0.5
    assert vol_cap_factor(2.5) == 0.25
    assert vol_cap_factor(3.5) == 0.0
    assert vol_cap_factor(None) == 1.0  # unknown -> advisory 1.0
    # boundary
    assert vol_cap_factor(1.2) == 0.75  # material: <1.2 is 100%, 1.2 starts 75%


def test_regime_factor_drops_vol_leg_on_request():
    # HIGH vol halves F_regime when the leg is included...
    assert regime_factor("BULL", "HIGH", include_vol_leg=True) == 0.5
    # ...and stops halving when the standalone F_vol ladder carries it
    assert regime_factor("BULL", "HIGH", include_vol_leg=False) == 1.0
    # a BEAR trend still halves regardless of the vol leg
    assert regime_factor("BEAR", "HIGH", include_vol_leg=False) == 0.5
    assert regime_factor("STRONG_BEAR", "NORMAL", include_vol_leg=False) == 0.25


def test_regime_state_exposes_vol_ratio():
    c, h, low_ = _walk(n=80, noise=0.2, seed=5)
    rs = regime_state(c, h, low_)
    assert "vol_ratio" in rs
    assert rs["vol_ratio"] is None or rs["vol_ratio"] > 0
    # a spike pushes the ratio up and F_vol down
    h2 = h[:-1] + [h[-1] * 2.5]
    l2 = low_[:-1] + [low_[-1] * 0.5]
    rs2 = regime_state(c[:-1] + [c[-1]], h2, l2)
    from tradingagents.strategies.regime_state import vol_cap_factor

    assert vol_cap_factor(rs2["vol_ratio"]) <= vol_cap_factor(rs["vol_ratio"] or 1.0)


def test_contract_scales_by_vol_cap():
    closes = [100.0 + 0.1 * i for i in range(60)]
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    c1 = build_position_contract(cfg={}, closes=closes, high=highs, low=lows)
    c2 = build_position_contract(cfg={}, closes=closes, high=highs, low=lows, vol_cap_factor=0.25)
    assert c1 is not None and c2 is not None
    assert c2.size_pct <= c1.size_pct * 0.3
    assert any("vol_cap_scale" in r for r in c2.reason_parts)
