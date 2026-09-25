"""Volatility-compression reads (spec §2): ATR/close percentile + range tightness.

Both are reported measurements on the VDU/VCP ladder. They must never gate,
must never fabricate a reading from too little history, and must rank the
current ATR inside a window that contains only bars already observed.
"""

from __future__ import annotations

import statistics

import pytest

from tradingagents.strategies import compression as C, value_dip as vd

pytestmark = pytest.mark.timeout(120)


def _bars(widths, *, start=100.0, pos=0.5):
    """Bars whose ``(high - low) / close`` is exactly each requested width.

    The close is held flat, so a bar's true range is exactly its width (times
    the price) - which makes the ATR series the Wilder average of those widths
    and every expectation below arithmetic rather than a fitted guess.
    """
    closes, highs, lows = [], [], []
    for w in widths:
        r = w * start
        lo = start - pos * r
        closes.append(start)
        highs.append(lo + r)
        lows.append(lo)
    return closes, highs, lows


def _ref_atr(highs, lows, closes, window=14):
    """Independent Wilder ATR series (the test's own reference)."""
    tr = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    out = [sum(tr[:window]) / window]
    for i in range(window, len(tr)):
        out.append((out[-1] * (window - 1) + tr[i]) / window)
    return out


WIDE = [0.03] * 190
QUIET = [0.002] * 10


@pytest.mark.unit
def test_a_quiet_tail_reads_compressed():
    closes, highs, lows = _bars(WIDE + QUIET)
    r = C.atr_compression_read(highs, lows, closes)
    assert r is not None
    assert r["compressed"] is True
    assert r["percentile"] <= 0.20
    # Today's ATR/close is a fraction of the noisy regime's 3% ranges.
    assert r["atr_pct"] < 0.03
    assert r["lookback"] == C.COMPRESSION_LOOKBACK


@pytest.mark.unit
def test_constant_ranges_rank_at_the_top_of_their_own_window():
    """Every ATR value equals the current one, so nothing is compressed."""
    closes, highs, lows = _bars([0.01] * 160)
    r = C.atr_compression_read(highs, lows, closes)
    assert r is not None
    assert r["percentile"] == 1.0
    assert r["compressed"] is False


@pytest.mark.unit
def test_the_rank_window_is_the_trailing_lookback_only():
    """A short lookback sees only recent ATRs - the whole point of the window."""
    closes, highs, lows = _bars(WIDE + QUIET)
    short = C.atr_compression_read(highs, lows, closes, lookback=5)
    long = C.atr_compression_read(highs, lows, closes, lookback=126)
    assert short is not None and long is not None
    # The quiet tail is strictly decreasing, so with 5 bars exactly one value
    # (today's) is at or below today's.
    assert short["lookback"] == 5
    assert short["percentile"] == 0.2
    # With 126 bars, the only ATR at or below today's is today's own: the quiet
    # tail is still decaying from the 3% regime, so every earlier value ranks
    # ABOVE it.
    assert long["lookback"] == 126
    assert long["percentile"] == round(1 / 126, 4)
    assert long["min_atr"] == long["atr"]


@pytest.mark.unit
def test_the_reading_uses_only_the_trailing_window():
    """The reported window stats are the observed ATRs, not future ones."""
    closes, highs, lows = _bars(WIDE + QUIET)
    r = C.atr_compression_read(highs, lows, closes, lookback=20)
    assert r is not None
    tail = _ref_atr(highs, lows, closes)[-20:]
    assert r["min_atr"] == round(min(tail), 6)
    assert r["max_atr"] == round(max(tail), 6)
    assert r["median_atr"] == round(statistics.median(tail), 6)


@pytest.mark.unit
def test_too_little_history_is_unmeasured_not_fabricated():
    closes, highs, lows = _bars([0.01] * 2)
    assert C.atr_compression_read(highs, lows, closes) is None
    assert C.closing_range_read(closes, highs, lows) is None


@pytest.mark.unit
def test_a_non_positive_close_is_refused_rather_than_divided_by():
    closes, highs, lows = _bars([0.01] * 20)
    closes[-1] = 0.0
    assert C.atr_compression_read(highs, lows, closes) is None
    assert C.closing_range_read(closes, highs, lows) is None


@pytest.mark.unit
def test_closing_range_flags_a_tight_coil_and_closes_near_the_high():
    closes, highs, lows = _bars([0.006, 0.005, 0.004], pos=0.9)
    r = C.closing_range_read(closes, highs, lows)
    assert r is not None
    assert r["tight"] is True
    assert r["range_pct"] == [0.006, 0.005, 0.004]
    assert all(p == 0.9 for p in r["close_position"])
    assert r["close_position_mean"] == 0.9

    closes2, highs2, lows2 = _bars([0.006, 0.005, 0.02], pos=0.9)
    wide = C.closing_range_read(closes2, highs2, lows2)
    assert wide is not None
    assert wide["tight"] is False
    assert wide["mean_range_pct"] == round((0.006 + 0.005 + 0.02) / 3, 6)


@pytest.mark.unit
def test_a_zero_range_bar_reports_no_close_position():
    closes, highs, lows = _bars([0.006, 0.0, 0.006], pos=0.9)
    r = C.closing_range_read(closes, highs, lows)
    assert r is not None
    assert r["close_position"] == [0.9, None, 0.9]
    assert r["tight"] is True


@pytest.mark.unit
def test_value_dip_setup_reports_the_reads_without_gating_on_them(monkeypatch):
    """The rows are reported, and the reading cannot flip the candidate.

    ``value_dip_setup`` imports the producers at call time, so patching the
    module attribute is exactly what a real run would import.
    """
    closes = [100.0 + (i % 9) * 0.35 for i in range(260)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1_000_000] * 260

    base = vd.value_dip_setup(
        closes, highs, lows, volumes, margin_of_safety=0.30, fcf_yield=0.08, roe=0.20, fcf=100.0
    )
    assert base["rows"]["compression"]["percentile"] is not None
    assert base["rows"]["closing_range"]["tight"] is not None

    monkeypatch.setattr(
        C, "atr_compression_read", lambda *a, **k: {"compressed": False, "percentile": 1.0}
    )
    monkeypatch.setattr(
        C, "closing_range_read", lambda *a, **k: {"tight": False, "mean_range_pct": 0.05}
    )
    flipped = vd.value_dip_setup(
        closes, highs, lows, volumes, margin_of_safety=0.30, fcf_yield=0.08, roe=0.20, fcf=100.0
    )
    assert flipped["candidate"] == base["candidate"]
    assert flipped["reasons"] == base["reasons"]
