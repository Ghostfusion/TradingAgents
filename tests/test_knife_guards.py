"""Knife-guard tests (falling-knife filters): VPIN toxicity, velocity z, ATR
range expansion — items 1-3 of the knife-guard review. All pure/offline."""

from __future__ import annotations

import random

import pytest

from tradingagents.strategies.orderflow import knife_guard_vpin
from tradingagents.strategies.value_dip import (
    price_velocity_z,
    range_expansion_guard,
    value_dip_setup,
)

pytestmark = pytest.mark.timeout(120)


def _series(n=60, base=100.0, drift=0.0, noise=0.3, seed=7, crash_at=None, crash_drop=18.0):
    """Seeded noisy random walk (mild noise per day) with an optional crash.

    ``crash_at`` is a START index: the level drops by ``crash_drop`` once and
    STAYS down for every subsequent bar (a real sustained cascade), so the
    3-day velocity over the crash window is large-negative.
    """
    rng = random.Random(seed)
    prices = [base]
    for _ in range(1, n):
        prices.append(prices[-1] + drift + rng.uniform(-noise, noise))
    if crash_at:
        start = crash_at[0]
        for i in range(start, n):
            prices[i] = prices[i] - crash_drop
    return prices


def _ohlcv_around(closes):
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    return highs, lows


# --- #1: downside-conditioned VPIN ---


def test_vpin_guard_toxic_downside_active():
    assert knife_guard_vpin(0.85, -0.3) is True
    assert knife_guard_vpin(0.80, -0.01) is True


def test_vpin_guard_toxic_upside_inactive():
    """High VPIN on an UP move must NOT block (directional conditioning)."""
    assert knife_guard_vpin(0.85, +0.3) is False


def test_vpin_guard_low_toxicity_inactive():
    assert knife_guard_vpin(0.5, -0.3) is False


def test_vpin_guard_missing_inputs_inactive():
    assert knife_guard_vpin(None, -0.3) is False
    assert knife_guard_vpin(0.9, None) is False


def test_vpin_guard_threshold_respected():
    assert knife_guard_vpin(0.74, -0.1, threshold=0.75) is False
    assert knife_guard_vpin(0.76, -0.1, threshold=0.75) is True


# --- #2: normalized price velocity z ---


def test_velocity_z_calm_series_not_knife():
    z = price_velocity_z(_series(noise=0.3))
    assert z is not None
    assert z > -2.5  # mild noise, no cascade


def test_velocity_z_crash_triggers_knife():
    z = price_velocity_z(_series(noise=0.3, crash_at=[57], crash_drop=18.0))
    assert z is not None
    assert z < -2.5  # unresolved cascade


def test_velocity_z_short_history_none():
    assert price_velocity_z([100.0] * 10) is None


def test_velocity_z_degenerate_vol_none():
    assert price_velocity_z([100.0] * 40) is None  # zero variance


# --- #3: ATR range expansion ---


def test_range_expansion_normal_candle_inactive():
    highs, lows = _ohlcv_around([100.0] * 30)
    g = range_expansion_guard(highs, lows, [100.0] * 30, atr_value=1.0)
    assert g is not None
    assert g["active"] is False


def test_range_expansion_monster_candle_active():
    max_mult = 2.5
    closes = [100.0] * 29 + [99.0]  # close BELOW the slow EMA
    highs = [100.1] * 29 + [101.0]
    lows = [99.9] * 29 + [97.9]
    g = range_expansion_guard(highs, lows, closes, atr_value=0.1, max_mult=max_mult)
    assert g is not None
    assert g["range_atr_mult"] > max_mult
    assert g["close_below_ema"] is True
    assert g["active"] is True


def test_range_expansion_up_move_above_ema_inactive():
    """Monster candle but close ABOVE the slow EMA: not a knife — active False."""
    max_mult = 2.5
    closes = [100.0] * 29 + [102.0]  # close above EMA of rising series
    highs = [100.1] * 29 + [103.0]
    lows = [99.9] * 29 + [100.5]
    g = range_expansion_guard(highs, lows, closes, atr_value=0.1, max_mult=max_mult)
    assert g is not None
    assert g["close_below_ema"] is False
    assert g["active"] is False


# --- integrated: value_dip_setup rows + gating ---


def _setup_kwargs(**kw):
    closes = _series(40, noise=0.15, seed=3)
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    base = {
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": [1_000_000] * 40,
        "margin_of_safety": 0.30,
        "fcf_yield": 0.08,
        "roe": 0.20,
        "fcf": 100.0,
    }
    base.update(kw)
    return base


def test_setup_lists_knife_rows():
    s = value_dip_setup(**_setup_kwargs())
    rows = s["rows"]
    assert "knife_velocity" in rows and "knife_range" in rows and "knife_flow" in rows
    assert rows["knife_velocity"] is not None
    assert rows["knife_velocity"]["active"] is False


def test_setup_knife_rows_display_only_by_default():
    s = value_dip_setup(**_setup_kwargs())
    s2 = value_dip_setup(**_setup_kwargs(vpin_value=0.9, price_delta_tau=-2.0))
    assert s2["rows"]["knife_flow"]["active"] is True
    assert s2["candidate"] == s["candidate"]  # advisory: does not gate by default
    assert any("knife advisory" in r for r in s2["reasons"])


def test_setup_require_knife_blocks_on_crash():
    closes = _series(60, noise=0.15, seed=3, crash_at=[57], crash_drop=18.0)
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    s = value_dip_setup(
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=[1_000_000] * 60,
        margin_of_safety=0.30,
        fcf_yield=0.08,
        roe=0.20,
        fcf=100.0,
        vpin_value=0.9,
        price_delta_tau=-3.0,
        require_knife=True,
    )
    assert s["candidate"] is False
    assert any("knife guard blocked" in r for r in s["reasons"])


def test_setup_require_knife_passes_when_no_knife():
    s = value_dip_setup(
        **_setup_kwargs(vpin_value=0.4, price_delta_tau=-0.5, require_knife=True)
    )
    base = value_dip_setup(**_setup_kwargs())
    assert s["rows"]["knife_flow"]["active"] is False
    assert s["candidate"] == base["candidate"]


# --- composite knife score (item: composite K + graduated F_knife) ---


def _crash_series(n=60, noise=0.3, seed=7, crash_at=None, decay=0.97, vol_spike_at=None):
    """Random walk with a sustained -3%/bar DECAY from the crash start.

    The decline stays active into the current window (a real falling knife the
    composite legs must see): after ``crash_at[0]`` every bar is ~3% below the
    prior one. ``vol_spike_at`` multiplies volume 3x from its start.
    """
    import random as _r

    rng = _r.Random(seed)
    prices = [100.0]
    volumes = [1_000_000] * n
    for _ in range(1, n):
        prices.append(prices[-1] + rng.uniform(-noise, noise))
    if crash_at:
        start = crash_at[0]
        for i in range(start, n):
            prices[i] = prices[i - 1] * decay
            if vol_spike_at and i >= vol_spike_at[0]:
                volumes[i] *= 3
    return prices, volumes


def _cho(c):
    return [x + 0.2 for x in c], [x - 0.2 for x in c]


def test_composite_calm_score_normal_factor():
    from tradingagents.strategies.knife_guard import knife_score

    closes, vols = _crash_series(noise=0.3)  # no crash
    highs_, lows_ = _cho(closes)
    kc = knife_score(closes, highs_, lows_, vols, vpin_downside=0.3)
    assert kc["K"] < 1.5
    assert kc["factor"] == 1.0
    assert kc["band"] == "normal"


def test_composite_crash_reaches_block():
    from tradingagents.strategies.knife_guard import knife_score

    closes, vols = _crash_series(noise=0.3, crash_at=[57], vol_spike_at=[57])
    highs_, lows_ = _cho(closes)
    kc = knife_score(closes, highs_, lows_, vols, vpin_downside=0.9)
    assert kc["K"] >= 3.0
    assert kc["factor"] == 0.0
    assert kc["band"] == "block"
    # order-flow leg contributes
    assert kc["severities"]["of"] > 0.0


def test_composite_borderline_reduces_not_blocks():
    from tradingagents.strategies.knife_guard import knife_factor

    # moderate K between 1.5 and 2.5 -> graduated 0.5, NOT a binary flip
    f, b = knife_factor(1.8)
    assert f == 0.5 and b == "reduce"
    f, b = knife_factor(2.7)
    assert f == 0.25 and b == "caution"


def test_composite_directional_legs():
    """Volume/ATR legs must be conditioned on the decline, not raw."""
    from tradingagents.strategies.knife_guard import knife_score

    # UP move with high volume: volume leg must be 0 (no downside conditioning)
    closes = [100.0 + 0.5 * i for i in range(40)]
    vols = [1_000_000] * 30 + [3_000_000] * 10
    highs_, lows_ = _cho(closes)
    kc = knife_score(closes, highs_, lows_, vols, vpin_downside=0.9)
    assert kc["severities"]["vol"] == 0.0
    assert kc["severities"]["of"] > 0.0  # vpin still counts (downside-conditioned flag)


def test_guard_band_halfwidth():
    from tradingagents.strategies.knife_guard import guard_band_halfwidth, should_trade

    h = guard_band_halfwidth(10.0 / 10_000.0, 0.02, gamma=1.0)
    assert h is not None and h > 0
    # higher cost -> wider band (cube root)
    h2 = guard_band_halfwidth(50.0 / 10_000.0, 0.02, gamma=1.0)
    assert h2 > h
    # degenerate -> None
    assert guard_band_halfwidth(0.0, 0.02, 1.0) is None
    assert guard_band_halfwidth(0.001, 0.0, 1.0) is None
    # should_trade respects the band
    assert should_trade(0.05, h) is True
    assert should_trade(h * 0.5, h) is False
    assert should_trade(0.1, None) is True  # no band -> don't suppress


def test_setup_composite_row_present_and_gates():
    kw = _setup_kwargs()
    s = value_dip_setup(**kw)
    assert "knife_composite" in s["rows"]
    if s["rows"]["knife_composite"] is not None:
        assert 0.0 <= s["rows"]["knife_composite"]["factor"] <= 1.0
        assert s["rows"]["knife_composite"]["band"] in ("normal", "reduce", "caution", "block")
    # block-band collision with require_knife flips candidate off
    closes = _crash_series(noise=0.15, seed=3, crash_at=[57], vol_spike_at=[57])[0]
    highs_, lows_ = _cho(closes)
    s2 = value_dip_setup(
        closes=closes, highs=highs_, lows=lows_, volumes=[1_000_000] * 60,
        margin_of_safety=0.30, fcf_yield=0.08, roe=0.20, fcf=100.0,
        vpin_value=0.9, price_delta_tau=-3.0, require_knife=True,
    )
    kc = s2["rows"]["knife_composite"]
    assert kc is None or kc["factor"] == 0.0 or s2["candidate"] is False
