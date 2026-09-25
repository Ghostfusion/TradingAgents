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


# --- T-1 base priming: yesterday quiet, today expands -----------------------


def _priming_bars(*, prior_width: float, today_width: float, close_at_high: bool):
    """60 flat-volume bars whose last two carry the requested ranges.

    The close is held flat until the final bar, so ``range_pct`` is exactly the
    requested width and every expectation below is arithmetic.
    """
    n = 60
    closes = [100.0] * n
    highs = [100.0 * (1 + 0.5 * prior_width)] * n
    lows = [100.0 * (1 - 0.5 * prior_width)] * n
    vols = [1e6] * n
    # the prior bar: exactly prior_width, closed mid-bar
    highs[-2] = 100.0 * (1 + 0.5 * prior_width)
    lows[-2] = 100.0 * (1 - 0.5 * prior_width)
    closes[-2] = 100.0
    # the final bar: exactly today_width, closed at the high or mid-bar
    hi = 100.0 * (1 + 0.5 * today_width)
    lo = 100.0 * (1 - 0.5 * today_width)
    highs[-1] = hi
    lows[-1] = lo
    closes[-1] = hi if close_at_high else (hi + lo) / 2
    return closes, highs, lows, vols


@pytest.mark.unit
def test_base_priming_reads_a_quiet_bar_then_an_expansion():
    """Yesterday tight + today expanding out of it on volume = primed."""
    closes, highs, lows, vols = _priming_bars(
        prior_width=0.002, today_width=0.010, close_at_high=True
    )
    vols[-1] = 2e6
    bp = C.base_priming_read(closes, highs, lows, vols)
    assert bp["prev_tight"] is True
    assert bp["expansion"] is True
    assert bp["expansion_ratio"] == pytest.approx(5.0, abs=0.15)
    assert bp["cleared"] is True
    assert bp["rvol"] == pytest.approx(2.0, abs=0.05)
    assert bp["rvol_ok"] is True
    assert bp["close_position"] == pytest.approx(1.0)
    assert bp["close_ok"] is True
    assert bp["primed"] is True
    assert bp["reasons"] == []


@pytest.mark.unit
def test_base_priming_is_false_when_today_does_not_expand():
    """A quiet bar with no expansion is the ordinary case: absent, not unknown."""
    closes, highs, lows, vols = _priming_bars(
        prior_width=0.002, today_width=0.002, close_at_high=False
    )
    bp = C.base_priming_read(closes, highs, lows, vols)
    assert bp["prev_tight"] is True
    assert bp["expansion"] is False
    assert bp["expansion_ratio"] == pytest.approx(1.0, abs=0.05)
    assert bp["primed"] is False
    assert any("range" in r for r in bp["reasons"])


@pytest.mark.unit
def test_base_priming_reads_an_unmeasured_leg_as_unknown_never_absent():
    """Too few bars, or no volume baseline, makes the STATE unknown.

    ``primed is False`` is a claim that the setup was measured and is not
    there; without the bars to measure it, the honest answer is ``None``.
    """
    bp = C.base_priming_read([100.0, 101.0], [100.5, 101.5], [99.5, 100.5], [1e6, 1e6])
    assert bp["primed"] is None and bp["prev_tight"] is None
    assert any("3 bars" in r for r in bp["reasons"])

    closes, highs, lows, _ = _priming_bars(
        prior_width=0.002, today_width=0.010, close_at_high=True
    )
    thin = C.base_priming_read(closes, highs, lows, [1e6, 2e6])  # one prior bar
    assert thin["rvol"] is None and thin["rvol_ok"] is None
    assert thin["primed"] is None
    assert any("volume baseline" in r for r in thin["reasons"])


@pytest.mark.unit
def test_the_base_priming_read_never_moves_the_vdu_candidate(monkeypatch):
    """REPORTED only: patching a clean prime into the producer changes no gate.

    The same acceptance E1's compression rows carry - if this read can flip a
    candidate, it is not a reported row.
    """
    closes, highs, lows, vols = _priming_bars(
        prior_width=0.002, today_width=0.010, close_at_high=True
    )
    vols[-1] = 2e6
    plain = vd.vdu_entry_setup(closes, highs, lows, vols)
    monkeypatch.setattr(
        C, "base_priming_read", lambda *a, **kw: {"primed": True, "reasons": []}
    )
    forced = vd.vdu_entry_setup(closes, highs, lows, vols)
    assert forced["base_priming"]["primed"] is True
    assert forced["candidate"] == plain["candidate"]
    assert forced["reasons"] == plain["reasons"]


@pytest.mark.unit
def test_value_dip_setup_carries_the_base_priming_row_and_never_gates_it(monkeypatch):
    """The row travels on the full setup too, and the read stays out of the gates.

    Same acceptance as the compression rows: a hard-coded absent prime reports
    the same candidate and the same reasons.
    """
    closes, highs, lows, vols = _priming_bars(
        prior_width=0.002, today_width=0.010, close_at_high=True
    )
    vols[-1] = 2e6
    base = vd.value_dip_setup(closes, highs, lows, vols, margin_of_safety=0.10)
    assert base["rows"]["base_priming"]["primed"] is True

    monkeypatch.setattr(
        C, "base_priming_read", lambda *a, **k: {"primed": False, "reasons": ["no prime"]}
    )
    flipped = vd.value_dip_setup(closes, highs, lows, vols, margin_of_safety=0.10)
    assert flipped["rows"]["base_priming"]["primed"] is False
    assert flipped["candidate"] == base["candidate"]
    assert flipped["reasons"] == base["reasons"]
