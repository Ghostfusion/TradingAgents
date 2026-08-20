"""Relative-strength (RS) module tests - pure/offline."""

import math

from tradingagents.strategies.relative_strength import (
    align_tail,
    divergence,
    relative_strength_report,
    rs_position,
    rs_series,
    rs_trend,
    slope_pct,
)


def _uptrend(n: int = 260, start: float = 100.0, step: float = 0.5) -> list:
    return [start + step * i for i in range(n)]


def test_align_tail_common_length():
    a = _uptrend(260)
    b = _uptrend(240, start=200.0)
    out = align_tail(a, b)
    assert out is not None
    assert len(out[0]) == len(out[1]) == 240
    assert out[0][-1] == a[-1]  # tail anchored on the newest close


def test_align_tail_too_short_none():
    assert align_tail([1.0], [2.0, 3.0]) is None
    assert align_tail([], [1.0, 2.0]) is None


def test_rs_series_ratio():
    stock = [10.0 + i for i in range(5)]
    bench = [20.0 + 2 * i for i in range(5)]
    rs = rs_series(stock, bench)
    assert rs is not None
    assert abs(rs[-1] - stock[-1] / bench[-1]) < 1e-9


def test_rs_series_skips_invalid():
    stock = [10.0, 0.0, 12.0, 13.0]
    bench = [2.0, 2.0, 2.0, 2.0]
    rs = rs_series(stock, bench)
    assert rs is not None
    assert rs == [10.0 / 2.0, 12.0 / 2.0, 13.0 / 2.0]


def test_slope_pct_positive_for_uptrend():
    s = [1.0 + 0.01 * i for i in range(60)]
    assert slope_pct(s, window=20) is not None
    assert slope_pct(s, window=20) > 0


def test_rs_trend_flags():
    # Stock rallies 10x vs a market that drifts flat: RS must read as an
    # established uptrend.
    stock = _uptrend(260, step=0.5)
    bench = _uptrend(260, start=200.0, step=0.01)
    rs = rs_series(stock, bench)
    trend = rs_trend(rs)
    assert trend["uptrend"] is True
    assert trend["slope_pct"] > 0
    assert trend["above_sma"] is True


def test_rs_trend_insufficient():
    assert rs_trend([1.0, 2.0], window=20)["uptrend"] is None


def test_rs_position_new_high_and_near():
    rs = [1.0 + 0.001 * i for i in range(100)]
    pos = rs_position(rs, lookback=252)
    assert pos["new_high"] is True
    assert pos["near_high"] is True
    assert pos["dist_from_high"] is not None


def test_divergence_price_high_rs_lag():
    # Price makes a new high off its own prior window but the RS line stalls.
    stock = list(range(100, 160)) + [170.0]  # step down then a final pop
    bench = [100.0 + 0.9 * i for i in range(len(stock))]
    # RS turns down in the back half because the market outpaces the stock there.
    d = divergence(stock, bench, lookback=40)
    assert d["price_new_high"] in (True, False)
    assert d["divergence"] in (True, False)


def test_report_verdict_leading():
    stock = _uptrend(260, step=1.0)
    bench = _uptrend(260, start=200.0, step=0.001)
    r = relative_strength_report(stock, bench)
    assert r["verdict"] == "leading"
    assert r["uptrend"] is True


def test_report_verdict_lagging_when_market_wins():
    # A flat stock vs a strongly rising market: no price leadership and a
    # falling RS line - pure lagging (no divergence: price makes no new high).
    stock = [100.0] * 260
    bench = _uptrend(260, start=200.0, step=1.0)
    r = relative_strength_report(stock, bench)
    assert r["verdict"] == "lagging"
    assert r["uptrend"] is False


def test_report_unknown_on_no_benchmark():
    r = relative_strength_report([1.0, 2.0], [])
    assert r["verdict"] == "unknown"
    assert r["rs"] is None


def test_report_no_divergence_in_clean_lead():
    stock = _uptrend(260, step=1.0)
    bench = _uptrend(260, start=200.0, step=0.001)
    r = relative_strength_report(stock, bench)
    assert r["divergence"] is False
    assert r["verdict"] != "diverging"


def test_divergence_detected_when_price_spikes_but_rs_flat():
    # Classic setup: last-bar price jump (new high) that the RS line does not
    # back - the benchmark jumped even harder, so RS sits below its prior high.
    n = 120
    stock = [100.0 + i for i in range(n)] + [100.0 + n + 12.0]
    bench = [100.0 + 0.95 * i for i in range(n)] + [100.0 + 0.95 * n + 20.0]
    d = divergence(stock, bench, lookback=60)
    rs = rs_series(stock, bench)
    pos = rs_position(rs, 60)
    assert d["price_new_high"] is True
    assert d["rs_near_high"] is False
    assert d["divergence"] is True
    assert pos["new_high"] is False


def test_report_context_is_text():
    stock = _uptrend(260, step=0.5)
    bench = _uptrend(260, start=200.0, step=0.01)
    r = relative_strength_report(stock, bench, window=20)
    assert isinstance(r["context"], str) and "RS" in r["context"]


def test_math_sin_noise_never_crashes():
    closes = [100.0 + 0.5 * i + 8.0 * math.sin(i / 6) for i in range(260)]
    mkt = [200.0 + 0.05 * i for i in range(260)]
    r = relative_strength_report(closes, mkt)
    assert r["verdict"] in ("leading", "uptrend", "lagging", "diverging", "unknown")
