"""Mean-reversion + Roll spread tests (quants.md; offline)."""

import math

import numpy as np
import pytest

from tradingagents.strategies.liquidity_risk import roll_spread
from tradingagents.strategies.mean_reversion import (
    ar1_half_life,
    mean_reversion_verdict,
    ou_half_life,
)

pytestmark = pytest.mark.timeout(120)


def test_ar1_half_life_known_phi():
    # Simulate an AR(1) around a nonzero level with phi = -0.1 (reverting).
    rng = np.random.default_rng(1)
    vals = [100.0]
    phi = -0.1
    for _ in range(500):
        vals.append((1.0 + phi) * (vals[-1] - 100.0) + 100.0 + rng.normal(0, 0.5))
    hl = ar1_half_life(vals)
    assert hl is not None
    expected = -math.log(2.0) / math.log(1.0 + phi)
    assert hl == pytest.approx(expected, rel=0.25)


def test_ar1_random_walk_none():
    rng = np.random.default_rng(2)
    vals = list(np.cumsum(rng.normal(0.0, 0.02, 400)))
    assert ar1_half_life(vals) is None  # phi >= 0 -> trending


def test_ar1_insufficient():
    assert ar1_half_life([1.0, 2.0, 3.0]) is None
    assert ar1_half_life([1.0] * 100) is None  # zero variance


def test_ou_half_life_matches_ar1_speed():
    rng = np.random.default_rng(3)
    phi = -0.08
    vals = [100.0]
    for _ in range(500):
        vals.append((1.0 + phi) * (vals[-1] - 100.0) + 100.0 + rng.normal(0, 0.5))
    hl_ou = ou_half_life(vals)
    hl_ar = ar1_half_life(vals)
    assert hl_ou is not None and hl_ar is not None
    assert hl_ou == pytest.approx(hl_ar, rel=0.2)


def test_mean_reversion_verdict_classifies():
    rng = np.random.default_rng(4)
    reverting = [100.0]
    for _ in range(500):
        reverting.append(0.88 * (reverting[-1] - 100.0) + 100.0 + rng.normal(0, 0.5))
    v = mean_reversion_verdict(reverting)
    assert v["verdict"] == "mean-reverting"
    # A genuine random walk (noise-dominated, no reversion): phi ~ 0, the
    # significance gate rejects the 'reverting' label.
    trending = list(100.0 + np.cumsum(rng.normal(0.0, 2.0, 400)))
    assert mean_reversion_verdict(trending)["verdict"] == "trending"
    assert mean_reversion_verdict([100.0] * 80)["verdict"] == "stable"


def test_roll_spread_positive_on_planted_spread():
    # Roll's estimator: trades alternate by offset a around the mid, so the
    # per-step move dp = +/-2a with cov = -(2a)^2/2*... = -4a^2/4; the
    # estimator 2*sqrt(-cov) = 2a = the round-trip effective spread. With
    # offset 0.25 the round-trip is 1.0.
    px = [100.0 + (0.25 if i % 2 == 0 else -0.25) for i in range(400)]
    s = roll_spread(px)
    assert s is not None
    assert s == pytest.approx(1.0, rel=0.1)


def test_roll_spread_none_on_trend_only():
    rng = np.random.default_rng(6)
    px = list(np.cumsum(rng.normal(0.01, 0.02, 300)) + 100)
    assert roll_spread(px) is None  # positive autocovariance


def test_mean_reversion_quality_tool_render(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import (
        _RUN_OHLCV_CACHE,
        get_mean_reversion_quality,
    )

    n = 160
    rng = np.random.default_rng(7)
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] + rng.normal(0, 0.5)))
    dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
    _RUN_OHLCV_CACHE[("AAPL", 320)] = {
        "dates": dates,
        "closes": closes,
        "opens": closes,
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [1_000_000.0] * n,
    }
    try:
        out = get_mean_reversion_quality.invoke({"ticker": "AAPL"})
        assert "Mean-Reversion Quality" in out
        assert "verdict" in out
    finally:
        _RUN_OHLCV_CACHE.clear()


def test_mean_reversion_mixed_evidence_disclosed(monkeypatch):
    """AMZN 2026-09-09 adjudication: an AR(1)-significant mean-reverting
    verdict must disclose long-horizon counter-evidence (Hurst > 0.5 leans
    persistence, VR > 1 leans momentum) instead of a clean 'dip entries
    supported' read."""
    import tradingagents.strategies.mean_reversion as mr
    from tradingagents.agents.utils.analysis_tools import (
        _RUN_OHLCV_CACHE,
        get_mean_reversion_quality,
    )

    n = 120
    closes = [100.0 + 0.05 * i for i in range(n)]  # trending level
    dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
    _RUN_OHLCV_CACHE[("AMZN", 320)] = {
        "dates": dates,
        "closes": closes,
        "opens": closes,
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [1_000_000.0] * n,
    }
    monkeypatch.setattr(mr, "mean_reversion_verdict", lambda use: {
        "verdict": "mean-reverting", "half_life": 10.78, "phi": -0.0623, "n": 120,
    })
    monkeypatch.setattr(mr, "ar1_half_life", lambda use: 10.78)
    monkeypatch.setattr(mr, "ou_half_life", lambda use: 10.78)
    monkeypatch.setattr(mr, "hurst_exponent", lambda diffs: 0.6425)
    monkeypatch.setattr(mr, "variance_ratio", lambda *a, **k: {"vr": 1.1828, "z": 1.6})
    try:
        out = get_mean_reversion_quality.invoke({"ticker": "AMZN"})
        assert "verdict: mean-reverting" in out
        assert "MIXED" in out
        assert "leans persistence" in out
        assert "leans momentum" in out
        assert "require an explicit trigger" in out
    finally:
        _RUN_OHLCV_CACHE.clear()


def test_mean_reversion_clean_when_no_counter_evidence(monkeypatch):
    """With no Hurst/VR counter-signal the read stays the clean 'dip entries
    supported' form (no regression for the un-mixed case)."""
    import tradingagents.strategies.mean_reversion as mr
    from tradingagents.agents.utils.analysis_tools import (
        _RUN_OHLCV_CACHE,
        get_mean_reversion_quality,
    )

    n = 120
    closes = [100.0] * n
    dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
    _RUN_OHLCV_CACHE[("MSFTX", 320)] = {
        "dates": dates,
        "closes": closes,
        "opens": closes,
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [1_000_000.0] * n,
    }
    monkeypatch.setattr(mr, "mean_reversion_verdict", lambda use: {
        "verdict": "mean-reverting", "half_life": 4.0, "phi": -0.15, "n": n,
    })
    monkeypatch.setattr(mr, "ar1_half_life", lambda use: 4.0)
    monkeypatch.setattr(mr, "ou_half_life", lambda use: 4.0)
    monkeypatch.setattr(mr, "hurst_exponent", lambda diffs: 0.40)
    monkeypatch.setattr(mr, "variance_ratio", lambda *a, **k: {"vr": 0.90, "z": -1.1})
    try:
        out = get_mean_reversion_quality.invoke({"ticker": "MSFTX"})
        assert "verdict: mean-reverting" in out
        assert "MIXED" not in out
        assert "dip entries supported" in out
    finally:
        _RUN_OHLCV_CACHE.clear()


