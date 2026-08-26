"""Technical factors + swing/value dip extensions (Phases 1) - pure tests.

Covers chandelier_exit / fib_levels (swing.py), the new technical_factors
(KST, MFI, Stochastic, ADX, pivot) and fib_retrace_entry (value_dip.py), plus
the no-fabrication rule (None on missing input).
"""

import pytest

from tradingagents.strategies.swing import chandelier_exit, fib_levels
from tradingagents.strategies.technical_factors import (
    adx,
    kst,
    mf_index,
    pivot_points,
    stochastic_oscillator,
)
from tradingagents.strategies.value_dip import fib_retrace_entry


def test_chandelier_exit():
    closes = [100.0] * 22 + [95.0]
    out = chandelier_exit(closes, atr_value=2.0)
    assert out["chandelier"] == pytest.approx(94.0)  # hi(100) - 3*2
    assert out["exit"] is False  # 95 > 94
    below = chandelier_exit([100.0] * 22 + [90.0], atr_value=2.0)
    assert below["exit"] is True  # 90 < 94


def test_chandelier_exit_missing():
    assert chandelier_exit([], atr_value=2.0)["chandelier"] is None
    assert chandelier_exit([100.0] * 5, atr_value=None)["chandelier"] is None
    assert chandelier_exit([100.0] * 22, atr_value=0)["chandelier"] is None


def test_fib_levels():
    f = fib_levels(110.0, 100.0)
    assert f["0.382"] == pytest.approx(106.18, rel=1e-3)
    assert f["0.5"] == pytest.approx(105.0)
    assert f["0.618"] == pytest.approx(103.82, rel=1e-3)
    assert fib_levels(None, 100.0)["range"] is None
    assert fib_levels(100.0, 110.0)["0.382"] is None  # high <= low


def test_kst_insufficient():
    assert kst([])["kst"] is None
    assert kst([100.0] * 10)["kst"] is None


def test_kst_computes():
    closes = [100.0 + 0.5 * i for i in range(60)]
    out = kst(closes)
    assert out["kst"] is not None
    assert out["trigger"] is not None
    assert out["kst_up"] in (True, False)


def test_mfi():
    # Rising closes -> all positive money flow -> MFI near 100.
    closes = [100.0 + i * 0.1 for i in range(30)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1e6] * 30
    val = mf_index(highs, lows, closes, vols)
    assert val is not None and val > 90


def test_mfi_missing():
    assert mf_index([], [], [], []) is None
    assert mf_index([1.0] * 3, [1.0] * 3, [1.0] * 3, [1.0] * 3) is None  # < 14 bars


def test_stochastic_oscillator():
    closes = [100.0 + i for i in range(30)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    s = stochastic_oscillator(highs, lows, closes)
    assert s["k"] is not None and 0 <= s["k"] <= 100
    assert s["d"] is not None
    # rising market -> not oversold
    assert s["oversold"] is False


def test_adx():
    closes = [100.0 + 0.5 * i for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    a = adx(highs, lows, closes)
    assert a["adx"] is not None
    assert a["di_plus"] is not None


def test_pivot_points():
    p = pivot_points(110.0, 100.0, 105.0)
    assert p["p"] == pytest.approx(105.0)
    assert p["r1"] == pytest.approx(110.0)
    assert p["s1"] == pytest.approx(100.0)
    assert pivot_points(None, 100.0, 105.0)["p"] is None


def test_fib_retrace_entry():
    closes = [90.0, 92.0, 88.0, 95.0, 91.0, 96.0, 90.0, 89.0, 93.0, 94.0, 92.0, 95.0]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    f = fib_retrace_entry(closes, highs, lows)
    # current price within the swing range -> levels present + near_level set
    assert f["levels"] is not None
    assert f["near_level"] in ("0.382", "0.5", "0.618")
    assert fib_retrace_entry([], [], [])["near_level"] is None
    # short history -> None
    assert fib_retrace_entry([90.0, 92.0], [91, 93], [89, 91])["levels"] is None
