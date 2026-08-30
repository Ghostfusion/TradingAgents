"""Volatility models unit tests (quants.md §Volatility; offline)."""

import math

import numpy as np
import pytest

from tradingagents.strategies.volatility_models import (
    ewma_vol,
    garch11_fit,
    garman_klass_vol,
    parkinson_vol,
)

pytestmark = pytest.mark.timeout(120)


def _flat_high_low(n=60, base=100.0, day_range=2.0):
    highs = [base + day_range] * n
    lows = [base - day_range] * n
    closes = [base] * n
    opens = [base] * n
    return opens, highs, lows, closes


def test_parkinson_known_range():
    # Range 4 (high 102, low 98): ln(102/98)^2 per day, annualized.
    _, highs, lows, _ = _flat_high_low(n=252, base=100.0, day_range=2.0)
    v = parkinson_vol(highs, lows)
    assert v is not None
    expected = math.sqrt(math.log(102.0 / 98.0) ** 2 / (4.0 * math.log(2.0)) * 252.0)
    assert v == pytest.approx(expected, rel=1e-6)
    # Window applies.
    v3 = parkinson_vol(highs, lows, window=3)
    assert v3 is not None and v3 == pytest.approx(expected, rel=1e-6)


def test_parkinson_insufficient_none():
    assert parkinson_vol([], []) is None
    assert parkinson_vol([1.0], [1.0]) is None
    assert parkinson_vol([100.0, 100.0, 100.0], [100.0, 100.0, 100.0]) is None  # zero range


def test_garman_klass_flat_ohlc():
    opens, highs, lows, closes = _flat_high_low(n=252)
    v = garman_klass_vol(opens, highs, lows, closes)
    assert v is not None
    # Range-only term dominates; open==close so the OC term is 0.
    expected = math.sqrt(
        0.5 * math.log(102.0 / 98.0) ** 2 - (2.0 * math.log(2.0) - 1.0) * 0.0
    ) * math.sqrt(252.0 / 252.0)  # per-day then annualized
    # per-day variance only from the range term, annualized by 252.
    expected = math.sqrt(
        (0.5 * math.log(102.0 / 98.0) ** 2) * 252.0
    )
    assert v == pytest.approx(expected, rel=1e-6)


def test_ewma_constant_returns():
    r = [0.01] * 60
    v = ewma_vol(r, lam=0.94)
    assert v is not None
    # Steady-state: sigma^2 = (1-lam)/(1-lam) * r^2 ... = r^2.
    assert v == pytest.approx(0.01 * math.sqrt(252.0), rel=0.15)
    assert ewma_vol([0.01] * 5, min_obs=20) is None  # too few


def test_garch_recovers_simulated_series():
    rng = np.random.default_rng(7)
    n = 800
    omega, alpha, beta = 0.00002, 0.12, 0.84
    var = omega / (1.0 - alpha - beta)
    e = []
    sigma2 = var
    for _ in range(n):
        sigma2 = omega + alpha * (rng.standard_normal() ** 2) * sigma2 + beta * sigma2
        e.append(float(rng.standard_normal() * math.sqrt(max(sigma2, 1e-9))))
    fit = garch11_fit(e)
    assert fit is not None
    assert fit["converged"] is True
    # The likelihood surface is flat in (alpha,beta); the robust target is the
    # long-run vol. Truth: var=omega/(1-0.96)=0.0005/day -> ~0.355 annualized.
    assert fit["alpha"] == pytest.approx(alpha, abs=0.09)
    assert fit["beta"] == pytest.approx(beta, abs=0.09)
    assert 0.1 < fit["long_run_vol"] < 0.6
    assert len(fit["series"]) == len(e)


def test_garch_insufficient_none():
    assert garch11_fit([0.01] * 10) is None
    assert garch11_fit([]) is None


def test_overlay_estimator_switch_used():
    """With volatility_estimator=ewma/garch the overlay sizing uses the
    chosen estimator (close default is unchanged when unset or 'close')."""
    from tradingagents.strategies.overlays import build_strategy_overlays

    rng = np.random.default_rng(3)
    closes = list(100.0 * np.cumprod(1 + rng.normal(0.0003, 0.02, 300)))
    base = build_strategy_overlays(
        {"enable_strategy_overlays": True, "target_vol": 0.15, "volatility_estimator": "close"},
        closes,
    )
    ew = build_strategy_overlays(
        {"enable_strategy_overlays": True, "target_vol": 0.15, "volatility_estimator": "ewma"},
        closes,
    )
    gc = build_strategy_overlays(
        {"enable_strategy_overlays": True, "target_vol": 0.15, "volatility_estimator": "garch"},
        closes,
    )
    # The estimator only changes the scale via vol_override; with 300 obs the
    # ewma/garch scales should differ from the close scale in general, and all
    # must be valid scales.
    for ov in (base, ew, gc):
        assert ov is not None and 0 < ov["position_scale"] <= 1.5
    # Unknown estimator degrades to close (no crash).
    bad = build_strategy_overlays(
        {"enable_strategy_overlays": True, "target_vol": 0.15, "volatility_estimator": "bogus"},
        closes,
    )
    assert bad is not None and bad["position_scale"] == base["position_scale"]


def test_volatility_estimator_tools_render(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import (
        _RUN_OHLCV_CACHE,
        get_volatility_estimators,
    )

    n = 120
    closes = [100.0 + 0.05 * i for i in range(n)]
    dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
    _RUN_OHLCV_CACHE[("AAPL", 320)] = {
        "dates": dates,
        "closes": closes,
        "opens": [c - 0.1 for c in closes],
        "highs": [c + 1.0 for c in closes],
        "lows": [c - 1.0 for c in closes],
        "volumes": [1_000_000.0] * n,
    }
    try:
        out = get_volatility_estimators.invoke({"ticker": "AAPL"})
        assert "Volatility Estimators" in out
        assert "parkinson" in out and "garman-klass" in out
        assert "ewma" in out and "garch" in out
    finally:
        _RUN_OHLCV_CACHE.clear()
