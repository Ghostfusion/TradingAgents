"""Fundamental floors + mean-reversion technicals (Phases A/B) - pure tests.

Covers the 11 research gaps: Graham Number, NCAV/net-net, Earnings Power
Value (EPV), StochRSI, RSI2, Williams %R, Keltner, Donchian, OBV divergence,
Parabolic SAR, Elder thermometer - plus the no-fabrication rule (None on
missing).
"""

import pytest

from tradingagents.strategies.fundamental_floors import (
    earnings_power_value,
    epv_per_share,
    graham_cheap,
    graham_number,
    ncav_cheap,
    ncav_per_share,
)
from tradingagents.strategies.technical_factors import (
    donchian_channel,
    elder_thermometer,
    keltner_channel,
    obv_divergence,
    parabolic_sar,
    rsi2,
    stoch_rsi,
    williams_r,
)


# ---- Fundamental floors ----
def test_graham_number():
    # EPS 4.00, BVPS 30 -> sqrt(22.5*4*30)=sqrt(2700)=51.96
    assert graham_number(4.0, 30.0) == pytest.approx(51.96, rel=1e-3)
    assert graham_number(None, 30.0) is None
    assert graham_number(4.0, None) is None
    assert graham_number(-4.0, 30.0) is None  # negative EPS -> no floor


def test_graham_cheap():
    assert graham_cheap(50.0, 60.0) is True
    assert graham_cheap(70.0, 60.0) is False
    assert graham_cheap(None, 60.0) is None


def test_ncav_per_share():
    # (1e9 - 4e8)/1e8 = 6.0
    assert ncav_per_share(1e9, 4e8, 1e8) == pytest.approx(6.0)
    assert ncav_per_share(None, 4e8, 1e8) is None
    assert ncav_per_share(1e9, 4e8, 0) is None  # zero shares


def test_ncav_cheap():
    assert ncav_cheap(5.0, 6.0) is True
    assert ncav_cheap(7.0, 6.0) is False
    assert ncav_cheap(None, 6.0) is None


def test_epv():
    # EPV = 2e8*(1-0.21)/(0.09-0.0) = 1.756e9
    e = earnings_power_value(2e8, 0.21, 0.09)
    assert e["epv"] == pytest.approx(1.756e9, rel=1e-3)
    assert e["conclusion"] == "earnings-power-floor"
    # RoIC < WACC -> weak
    e2 = earnings_power_value(2e8, 0.21, 0.09, roic=0.05)
    assert "weak" in e2["conclusion"]
    # WACC <= growth -> None
    assert earnings_power_value(2e8, 0.21, 0.02, growth=0.03)["epv"] is None
    assert earnings_power_value(None, 0.21, 0.09)["epv"] is None


def test_epv_per_share():
    assert epv_per_share(1.756e9, 1e8) == pytest.approx(17.56, rel=1e-3)
    assert epv_per_share(None, 1e8) is None
    assert epv_per_share(1.0, 0) is None


# ---- Mean-reversion technicals ----
def _series(n=60, slope=0.5):
    closes = [100.0 + slope * i for i in range(n)]
    return closes, [c + 1 for c in closes], [c - 1 for c in closes], [1e6] * n


def test_stoch_rsi():
    closes, *_ = _series()
    s = stoch_rsi(closes)
    assert s["stochrsi"] is not None and 0 <= s["stochrsi"] <= 1
    assert s["oversold"] in (True, False)
    assert stoch_rsi([100.0] * 5)["stochrsi"] is None  # insufficient


def test_rsi2():
    closes, *_ = _series()
    # rising series -> all gains -> RSI2 = 100.0
    assert rsi2(closes) == pytest.approx(100.0)
    # flat series -> no gains/losses -> 50.0 (neutral, not None)
    assert rsi2([100.0] * 5) == pytest.approx(50.0)
    assert rsi2([100.0]) is None  # fewer than n+1 bars


def test_williams_r():
    closes, highs, lows, *_ = _series()
    w = williams_r(highs, lows, closes)
    assert w is not None and -100 <= w <= 0
    assert williams_r([1.0] * 5, [1.0] * 5, [1.0] * 5) is None


def test_keltner_channel():
    closes, *_ = _series()
    k = keltner_channel(closes, atr_value=2.0)
    assert k["upp"] if "upp" in k else k["upper"] is not None
    assert k["mid"] is not None
    assert keltner_channel(closes, atr_value=None)["pct"] is None


def test_donchian_channel():
    _, highs, lows, _ = _series()
    d = donchian_channel(highs, lows)
    assert d["upper"] is not None and d["lower"] is not None
    assert d["upper"] > d["lower"]


def test_obv_divergence():
    closes, _, _, vols = _series()
    o = obv_divergence(closes, vols)
    assert o["obv_up"] in (True, False)
    assert o["bullish_div"] in (True, False)
    assert obv_divergence([100.0] * 5, [1e6] * 5)["obv_up"] is None


def test_parabolic_sar():
    _, highs, lows, _ = _series()
    p = parabolic_sar(highs, lows)
    assert p["sar"] is not None
    assert parabolic_sar([1.0], [1.0])["sar"] is None


def test_elder_thermometer():
    e = elder_thermometer([1e6] * 30)
    assert e["ratio"] == pytest.approx(1.0)
    assert elder_thermometer([1e6] * 5)["ratio"] is None


def test_elder_thermometer_override():
    # heavy participation (last volume > 21-day avg)
    vols = [1e6] * 20 + [2e6] * 10
    e = elder_thermometer(vols, n=21)
    assert e["heavy"] is True
