"""Swing-trade building blocks (Phases 3/5) - pure/offline tests."""

import math

from tradingagents.strategies.swing import (
    pullback_setup,
    rsi,
    rsi_band,
    scaleout_plan,
    swing_low_stop,
    swing_report,
    targets_rr,
    trail_ema,
    trend_architecture,
)


def _ema_last(series, n: int = 20) -> float:
    k = 2.0 / (n + 1)
    ema = sum(series[:n]) / n
    for v in series[n:]:
        ema = v * k + ema * (1 - k)
    return ema


def _uptrend(n: int = 260, start: float = 100.0, step: float = 0.5) -> list:
    return [start + step * i for i in range(n)]


def _vols(n: int, base: float = 5e6) -> list:
    return [base] * n


def _swing_fixture():
    """Noisy uptrend + a gentle 6-bar pullback into the 20-day EMA with
    fading volume - a valid (non-invalidating) swing setup."""
    n = 252
    base = [100.0 + 0.5 * i + 8.0 * math.sin(i / 6) for i in range(n)]
    ema = _ema_last(base, 20)
    closes = base + [ema + 5.0, ema + 4.0, ema + 3.0, ema + 2.0, ema + 1.0, ema + 1.6]
    vols = _vols(len(closes))
    vols = vols[:-6] + [1e6] * 6  # volume fades into the pullback
    lows = [float(c) - 2.0 for c in closes]
    highs = [float(c) + 2.0 for c in closes]
    return closes, highs, lows, vols


def test_rsi_band_labels():
    assert rsi_band(50.0)["label"] == "strong"
    assert rsi_band(42.0)["label"] == "reset"
    assert rsi_band(35.0)["label"] == "broken"
    assert rsi_band(78.0)["label"] == "hot"
    assert rsi_band(None)["label"] == "unknown"
    b = rsi_band(43.0)
    assert b["pullback"] is True and b["reset_zone"] is True
    assert rsi_band(50.0)["in_band"] is True


def test_rsi_monotone_up_is_100():
    assert rsi([100.0 + i for i in range(40)]) == 100.0


def test_trend_architecture_stacked_uptrend():
    closes = _uptrend(260)
    arch = trend_architecture(closes)
    assert arch["stacked"] is True
    assert arch["above_sma50"] is True
    assert arch["above_sma200"] is True
    assert arch["sma50_rising"] is True
    assert arch["sma200_rising"] is True
    assert arch["ema20_above_sma50"] is True


def test_trend_architecture_insufficient_none():
    arch = trend_architecture([100.0] * 50)
    assert arch["stacked"] is None
    assert arch["above_sma200"] is None


def test_trend_architecture_not_stacked_in_downtrend():
    closes = list(reversed(_uptrend(260)))
    arch = trend_architecture(closes)
    assert arch["stacked"] is False


def test_pullback_setup_candidate():
    closes = _uptrend(260)
    # A 2-bar dip: last low pierces the EMA, last close holds at/above it.
    cls = list(closes)
    ema = _ema_last(cls)
    cls = cls[:-2] + [ema - 0.01, ema + 0.01]
    lows = [float(c) - 2.0 for c in cls]
    vols = _vols(len(cls))
    vols = vols[:-6] + [2e6] * 6  # volume fades into the pullback
    p = pullback_setup(cls, lows, vols)
    assert p["near_ema"] is True
    assert p["volume_fade"] is True
    assert p["uptrend_base"] is True
    assert p["candidate"] is True


def test_pullback_setup_fails_on_volume_expansion():
    closes = _uptrend(260)
    cls = list(closes)
    ema = _ema_last(closes)
    cls = cls[:-2] + [ema - 0.01, ema + 0.01]
    lows = [float(c) - 2.0 for c in cls]
    vols = _vols(len(cls))
    vols = vols[:-6] + [20e6] * 6  # heavy volume into the dip = distribution
    p = pullback_setup(cls, lows, vols)
    assert p["candidate"] is False


def test_swing_low_stop():
    lows = [100.0 - i for i in range(30)][::-1]
    # lows descending then a swing low 10 bars back; stop = swing low - 1 ATR
    lows = [90.0 + 0.5 * i for i in range(30)]
    lows[25] = 90.0  # recent swing low
    s = swing_low_stop(lows, atr_value=2.0, atr_mult=1.0, lookback=10, close=99.0)
    assert s["swing_low"] == 90.0
    assert s["stop"] == 88.0
    assert s["risk_pct"] is not None and 0.0 < s["risk_pct"] < 0.2


def test_swing_low_stop_missing_data():
    s = swing_low_stop([1.0, 2.0], atr_value=1.0)
    assert s["stop"] is None


def test_targets_rr_two_tier():
    t = targets_rr(entry=100.0, stop=95.0)
    assert t["valid"] is True
    assert t["t1"] == 110.0  # 2R
    assert t["t2"] == 115.0  # 3R
    assert t["risk"] == 5.0


def test_targets_rr_invalid():
    assert targets_rr(entry=95.0, stop=100.0)["valid"] is False


def test_scaleout_plan():
    p = scaleout_plan(100.0, 95.0)
    assert p["valid"] is True
    assert p["t1_fraction"] == 0.5
    assert p["t2_fraction"] == 0.5
    assert p["breakeven_after_t1"] is True
    assert p["trail"] == "20-day EMA"


def test_trail_ema():
    closes = _uptrend(260)
    up = trail_ema(closes)
    assert up["exit"] is False
    # A final collapse below the ema must set the trail-exit flag.
    ema = _ema_last(closes)
    down = trail_ema(closes[:-1] + [ema - 5.0])
    assert down["below"] is True
    assert down["exit"] is True


def test_swing_report_candidate_with_benchmark():
    closes, highs, lows, vols = _swing_fixture()
    mkt = [200.0] * len(closes)  # flat benchmark -> RS must read as an uptrend
    r = swing_report(
        closes,
        highs=highs,
        lows=lows,
        volumes=vols,
        atr_value=3.0,
        benchmark_closes=mkt,
    )
    assert r is not None
    assert r["architecture"]["stacked"] is True
    assert r["relative_strength"]["uptrend"] is True
    assert r["pullback"]["candidate"] is True
    assert r["stop"]["stop"] is not None
    assert r["targets"]["t1"] > r["stop"]["stop"]
    assert r["candidate"] is True


def test_swing_report_none_when_short_history():
    assert (
        swing_report(
            [100.0] * 50, [101.0] * 50, [99.0] * 50, [1e6] * 50, benchmark_closes=[200.0] * 50
        )
        is None
    )


def test_swing_report_rs_lag_blocks_candidate():
    closes, highs, lows, vols = _swing_fixture()
    mkt = [200.0 + 0.5 * i for i in range(len(closes))]  # market outpaces the stock
    r = swing_report(
        closes, highs=highs, lows=lows, volumes=vols, atr_value=3.0, benchmark_closes=mkt
    )
    assert r is not None
    assert r["candidate"] is False  # RS lagging must kill the gate
    assert r["relative_strength"]["verdict"] == "lagging"


def test_swing_report_unknown_rs_ignored():
    closes, highs, lows, vols = _swing_fixture()
    # No benchmark -> rs None -> treated as unknown and must not block.
    r = swing_report(closes, highs=highs, lows=lows, volumes=vols, atr_value=3.0)
    assert r is not None
    assert r["relative_strength"] is None
    assert r["candidate"] is True


def test_swing_report_rsi_hot_blocks_candidate():
    n = 260
    closes = [100.0 + 1.0 * i for i in range(n)]  # monotone -> RSI 100 (hot)
    lows = [c - 1.0 for c in closes]
    vols = _vols(len(closes))
    r = swing_report(closes, closes, lows, vols, atr_value=1.0)
    assert r is not None
    assert r["rsi"]["label"] == "hot"
    assert r["candidate"] is False
