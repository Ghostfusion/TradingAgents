"""Tests for ETF relative-strength + risk profile.

The IGV 2026-09-09 review loop: the report inferred relative performance
from a single priceRelativeToS&P500 field with no benchmark leg, and treated
beta alone as the risk signal. etf_relative_strength renders both legs
(IGV/SPY/relative at 21/63/126/252d) and etf_risk_profile adds beta,
downside/upside capture, vol percentile, ATR% and max drawdown.
"""

from __future__ import annotations

import random

from tradingagents.strategies.etf_risk import (
    etf_relative_strength,
    etf_risk_profile,
)


def _series(n=400, drift=0.0, seed=1, scale=1.0):
    rng = random.Random(seed)
    c = [100.0]
    for _ in range(n - 1):
        c.append(c[-1] + rng.uniform(-scale, scale) + drift)
    return c


def test_relative_strength_shows_both_legs():
    etf = _series(drift=0.05, seed=1)   # rising ETF
    spy = _series(drift=0.02, seed=2)   # slower market
    r = etf_relative_strength("IGV", closes=etf, bench_map={"SPY": spy})
    b = r["benchmarks"]["SPY"]
    # ETF outperformed over the long window -> positive relative at 126/252d
    assert b["21"]["etf_ret"] is not None
    assert b["252"]["bench_ret"] is not None
    assert b["252"]["relative"] is not None
    # A faster-drifting ETF against a slower SPY must show positive relative
    # over the long window (deterministic drift dominates noise at 252d).
    assert b["252"]["relative"] > 0.0


def test_relative_strength_missing_benchmark_none_safe():
    r = etf_relative_strength("IGV", closes=_series(), bench_map={"SPY": None, "QQQ": _series()})
    assert r["benchmarks"]["SPY"]["21"]["etf_ret"] is not None
    assert r["benchmarks"]["SPY"]["21"]["bench_ret"] is None
    assert r["benchmarks"]["SPY"]["21"]["relative"] is None
    assert r["benchmarks"]["QQQ"]["21"]["relative"] is not None


def test_risk_profile_beta_and_capture():
    etf = _series(seed=1)
    spy = [x * 0.9 for x in etf]  # high-correlation: IGV = beta of 1.0 vs SPY
    r = etf_risk_profile("IGV", closes=etf, bench_map={"SPY": spy})
    b = r["benchmarks"]["SPY"]
    assert b["beta"] is not None
    assert abs(b["beta"] - 1.0) < 0.15  # exact linear copy -> beta ~1.0
    assert b["downside_capture"] is not None


def test_risk_profile_atr_pct_requires_highs():
    closes = _series(seed=3)
    # no highs -> ATR n/a
    r = etf_risk_profile("IGV", closes=closes)
    assert r["atr_pct"] is None
    # with highs/lows -> ATR% positive
    r2 = etf_risk_profile(
        "IGV", closes=closes,
        highs=[x * 1.01 for x in closes], lows=[x * 0.99 for x in closes],
    )
    assert r2["atr_pct"] is not None and 0 < r2["atr_pct"] < 0.5


def test_risk_profile_vol_percentile_none_when_short_history():
    r = etf_risk_profile("IGV", closes=[100.0] * 30)
    assert r["realized_vol"] is None or r["realized_vol"] == 0.0
    assert r["vol_percentile"] is None
