"""Technical factors + swing/value dip extensions (Phases 1) - pure tests.

Covers chandelier_exit / fib_levels (swing.py), the new technical_factors
(KST, MFI, Stochastic, ADX, pivot) and fib_retrace_entry (value_dip.py), plus
the no-fabrication rule (None on missing input).
"""

import pytest

from tradingagents.strategies.swing import chandelier_exit, fib_levels
from tradingagents.strategies.technical_factors import (
    adx,
    aroon,
    chaikin_oscillator,
    elder_ray,
    fisher_transform,
    kst,
    mf_index,
    pivot_distance_atr,
    pivot_points,
    stochastic_oscillator,
    supertrend,
    volume_profile,
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


def _uptrend(n=60):
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    vols = [1_000_000.0] * n
    return closes, highs, lows, vols


def test_aroon_uptrend():
    _, highs, lows, _ = _uptrend()
    r = aroon(highs, lows)
    assert r["aroon_up"] == 100.0
    assert r["aroon_down"] == 0.0
    assert r["verdict"] == "uptrend"
    assert aroon([1, 2], [1, 2])["aroon_up"] is None


def test_fisher_transform():
    closes, _, _, _ = _uptrend()
    r = fisher_transform(closes)
    assert r["fisher"] is not None
    assert r["verdict"] in ("up", "down", "reversal-up", "reversal-down")
    assert fisher_transform([1, 2])["fisher"] is None


def test_chaikin_oscillator():
    closes, highs, lows, vols = _uptrend()
    v = chaikin_oscillator(highs, lows, closes, vols)
    assert v is not None
    assert chaikin_oscillator([1], [1], [1], [1]) is None


def test_elder_ray():
    closes, highs, lows, _ = _uptrend()
    r = elder_ray(highs, lows, closes)
    assert r["bull_power"] is not None
    assert r["bear_power"] is not None
    assert elder_ray([1], [1], [1])["bull_power"] is None


def test_supertrend():
    closes, highs, lows, _ = _uptrend()
    r = supertrend(highs, lows, closes)
    assert r["line"] is not None
    assert r["direction"] in ("up", "down")
    assert supertrend([1], [1], [1])["line"] is None


def test_volume_profile():
    closes, _, _, vols = _uptrend()
    r = volume_profile(closes, vols)
    assert r["poc"] is not None
    assert r["value_area_low"] <= r["poc"] <= r["value_area_high"]
    assert volume_profile([1], [1])["poc"] is None


def test_volume_profile_reports_its_own_coverage():
    """Regression: the value-area loop carried a dead incremental add (the
    accumulator was recomputed from the bins on the next line), and the band it
    produced could legitimately span the whole price range for a bimodal
    distribution - which the AMAT 2026-09-14 read (va_low == poc == 169.56,
    va_high == 424.64) could not be distinguished from a broken accumulator.
    The band is the smallest one holding >=70% of the volume, and
    `value_area_pct` now says how much it actually holds."""
    closes, _, _, vols = _uptrend()
    r = volume_profile(closes, vols)
    assert r["value_area_pct"] >= 0.7
    assert r["value_area_low"] <= r["poc"] <= r["value_area_high"]
    # two tight clusters at opposite ends: the 70% band must span both, and the
    # coverage read makes the width explicit instead of looking like a bug
    c = [100.0 + (i % 2) * 40.0 for i in range(80)]
    r2 = volume_profile(c, [1e6] * 80)
    assert r2["value_area_pct"] >= 0.7
    assert r2["value_area_high"] - r2["value_area_low"] > 20.0
    assert volume_profile([1], [1])["poc"] is None


def test_fib_levels_degenerate_paths_share_one_key_set():
    """Every degenerate path returns the SAME keys as the live path.

    A caller does dict access on the result - ``fib_zone`` reads ["0.382"] and
    ["0.618"] - so a key present on one path and absent on another is a KeyError
    waiting for the right input. fib_levels has FOUR return paths (missing
    bound, non-numeric bound, high <= low, and the real one), which is exactly
    where the 0.236/0.786 widening could have shipped a partial edit.
    """
    shapes = {
        frozenset(fib_levels(*args))
        for args in [(None, None), (None, 100.0), (100.0, 100.0), (100.0, 110.0), ("x", "y")]
    }
    assert len(shapes) == 1, f"degenerate paths disagree on keys: {shapes}"
    assert shapes == {frozenset(fib_levels(110.0, 100.0))}


def test_fib_levels_are_the_standard_retracement_set():
    f = fib_levels(110.0, 100.0)  # range 10
    assert f["0.236"] == pytest.approx(107.64, rel=1e-3)
    assert f["0.786"] == pytest.approx(102.14, rel=1e-3)
    # 0.786 is sqrt(0.618): the two levels must not be transposed.
    assert f["0.786"] < f["0.618"] < f["0.5"] < f["0.382"] < f["0.236"]


def test_pivot_points_full_set_and_consistent_shape():
    p = pivot_points(105.0, 95.0, 100.0)
    assert p["p"] == pytest.approx(100.0)
    assert p["r3"] == pytest.approx(115.0)  # h + 2*(p - low) = 105 + 2*5
    assert p["s3"] == pytest.approx(85.0)  # low - 2*(h - p) = 95 - 2*5
    assert p["r3"] > p["r2"] > p["r1"] > p["p"] > p["s1"] > p["s2"] > p["s3"]
    shapes = {
        frozenset(pivot_points(*a))
        for a in [(None, None, None), (1.0, None, 2.0), ("x", "y", "z")]
    }
    assert shapes == {frozenset(p)}


def test_pivot_distance_atr_is_stationary_and_never_invents_zero():
    # 3 points above the pivot, ATR 2 -> 1.5 ATRs.
    assert pivot_distance_atr(103.0, 100.0, 2.0) == pytest.approx(1.5)
    assert pivot_distance_atr(96.0, 100.0, 2.0) == pytest.approx(-2.0)
    # The same dollar gap in a higher-ATR name is a smaller distance.
    assert pivot_distance_atr(103.0, 100.0, 6.0) == pytest.approx(0.5)
    # A non-positive ATR must be None, never 0.0: 0.0 reads as "price sits
    # exactly on the pivot", which is a claim the input cannot support.
    assert pivot_distance_atr(103.0, 100.0, 0.0) is None
    assert pivot_distance_atr(103.0, 100.0, -2.0) is None
    assert pivot_distance_atr(103.0, 100.0, None) is None
    assert pivot_distance_atr(None, 100.0, 2.0) is None
    assert pivot_distance_atr(103.0, None, 2.0) is None
    assert pivot_distance_atr("x", 100.0, 2.0) is None
