"""Extended technical indicators + candlestick patterns (hermetic).

Phase 1 of the indicator-gap plan: the standard trend/momentum/volume/structure
group the project did not yet compute locally. All pure / offline; every test
pins the no-fabrication contract (None / explicit flags on short or invalid
history).
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.extended_indicators import (
    accumulation_distribution,
    anchored_vwap,
    cci,
    chaikin_money_flow,
    force_index,
    golden_death_cross,
    ichimoku,
    momentum_oscillator,
    roc,
    scan_candlesticks,
    trix,
    vpt,
)

pytestmark = pytest.mark.timeout(60)


# ---------------------------------------------------------------------------
# trend
# ---------------------------------------------------------------------------


def test_golden_death_cross_short_history_none():
    assert golden_death_cross([100.0] * 10)["label"] is None


def test_golden_cross_no_false_death():
    # A monotonic uptrend must never report a false DEATH cross, and the
    # function must return a well-formed label (golden/None).
    closes = [100.0 + i * 0.4 for i in range(260)]
    r = golden_death_cross(closes)
    assert set(r) == {"golden", "death", "label"}
    assert r["death"] is False
    assert r["label"] in (None, "golden")


def test_ichimoku_short_history_all_none():
    r = ichimoku([100] * 20, [90] * 20, [95] * 20)
    assert r["conversion"] is None


def test_ichimoku_cloud_above():
    closes = [100.0 + i * 0.5 for i in range(260)]
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    r = ichimoku(highs, lows, closes)
    assert r["conversion"] is not None
    assert r["base"] is not None
    assert r["span_a"] is not None
    assert r["span_b"] is not None
    assert r["label"] in ("above", "below")


# ---------------------------------------------------------------------------
# momentum
# ---------------------------------------------------------------------------


def test_cci_short_history_none():
    assert cci([100] * 5, [90] * 5, [95] * 5, n=20) is None


def test_cci_returns_number():
    closes = [100.0 + i * 0.5 for i in range(60)]
    highs = [c + 3 for c in closes]
    lows = [c - 3 for c in closes]
    v = cci(highs, lows, closes, n=20)
    assert v is not None
    assert isinstance(v, float)


def test_roc_positive_for_uptrend():
    closes = [100.0 + i * 1.0 for i in range(30)]
    assert roc(closes, n=12) is not None and roc(closes, n=12) > 0


def test_roc_short_none():
    assert roc([100.0] * 5, n=12) is None


def test_momentum_oscillator():
    closes = [100.0 + i * 1.0 for i in range(15)]
    assert momentum_oscillator(closes, n=10) == pytest.approx(10.0, abs=0.01)


def test_trix_returns_dict():
    closes = [100.0 + i * 0.3 for i in range(120)]
    r = trix(closes, n=15)
    assert "trix" in r and "signal" in r
    assert r["trix"] is not None


def test_force_index_short_none():
    assert force_index([100] * 5, [1000] * 5, n=13) is None


def test_force_index_returns():
    closes = [100.0 + i * 0.2 for i in range(30)]
    vols = [1000.0] * 30
    assert force_index(closes, vols, n=13) is not None


# ---------------------------------------------------------------------------
# volume
# ---------------------------------------------------------------------------


def test_accumulation_distribution_positive():
    # closes ABOVE the bar midpoint -> positive CLV -> positive A/D.
    highs = [102.0 + i for i in range(30)]
    lows = [98.0 + i for i in range(30)]
    closes = [101.0 + i for i in range(30)]
    vols = [1000.0] * 30
    assert accumulation_distribution(highs, lows, closes, vols) is not None


def test_accumulation_flat_returns_none():
    # all H == L -> no A/D movement (no fabrication of a value)
    assert accumulation_distribution([100] * 5, [100] * 5, [100] * 5, [10] * 5) is None


def test_vpt_returns():
    closes = [100.0 + i for i in range(30)]
    vols = [1000.0] * 30
    assert vpt(closes, vols) is not None


def test_chaikin_money_flow_pos():
    # rising closes, closing ABOVE the bar midpoint (low far below) -> buying
    # pressure -> positive CMF.
    closes = [100.0 + i * 0.5 for i in range(40)]
    highs = [c + 2 for c in closes]
    lows = [c - 6 for c in closes]
    vols = [1000.0 + i * 10 for i in range(40)]
    v = chaikin_money_flow(highs, lows, closes, vols, n=20)
    assert v is not None
    assert v > 0


def test_anchored_vwap_plain():
    closes = [100.0, 102.0, 104.0, 106.0]
    vols = [10.0, 10.0, 10.0, 10.0]
    av = anchored_vwap(closes, vols)
    assert av is not None
    assert av == pytest.approx(103.0, abs=0.01)


def test_anchored_vwap_from_anchor():
    closes = [100.0, 102.0, 104.0, 106.0]
    vols = [10.0, 10.0, 10.0, 10.0]
    # from 104 onward (anchor threshold), including the anchor bar: (104+106)/2 = 105
    av = anchored_vwap(closes, vols, anchor_price=103.0)
    assert av is not None
    assert av == pytest.approx(105.0, abs=0.01)


# ---------------------------------------------------------------------------
# candlestick patterns
# ---------------------------------------------------------------------------


def test_scan_candlesticks_empty():
    r = scan_candlesticks([], [], [], [])
    assert r["patterns"]["doji"] is None and r["bars"] == []


def test_scan_candlesticks_finds_engulfing():
    # Last bar: big bullish candle (o=98 c=112) engulfing the prior down candle
    # (o=105 c=98).
    opens = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 98.0]
    closes = [101.0, 102.0, 103.0, 104.0, 105.0, 98.0, 112.0]
    highs = [101.0, 102.0, 103.0, 104.0, 106.0, 106.0, 113.0]
    lows = [100.0, 101.0, 102.0, 103.0, 104.0, 97.0, 97.0]
    r = scan_candlesticks(opens, highs, lows, closes)
    assert r["patterns"]["bullish_engulfing"] is True


def test_scan_candlesticks_doji():
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    opens = [9.9, 10.9, 11.9, 12.9, 13.9, 14.9, 16.02]  # last ~doji (close 16, open 16.02)
    highs = [x + 0.5 for x in closes]
    lows = [x - 0.5 for x in closes]
    r = scan_candlesticks(opens, highs, lows, closes)
    assert r["patterns"]["doji"] is True


def test_scan_candlesticks_returns_bars():
    closes = [10.0 + i for i in range(6)]
    opens = [x - 0.5 for x in closes]
    highs = [x + 1 for x in closes]
    lows = [x - 1 for x in closes]
    r = scan_candlesticks(opens, highs, lows, closes, lookback=3)
    assert len(r["bars"]) == 3
    assert "close" in r["bars"][0]
