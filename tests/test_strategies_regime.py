"""Phase 1 unit tests: regime features + rule labels (offline, no hmm)."""

from tradingagents.strategies.regime import (
    CHOP_TREND_THRESHOLD,
    choppiness,
    realized_vol,
    regime_label,
    trend_strength,
    vol_percentile,
)


def _uptrend(n=260, base=100.0, step=0.3):
    return [base + step * i for i in range(n)]


def test_trend_strength_positive_on_uptrend():
    t = trend_strength(_uptrend())
    assert t > 0


def test_trend_strength_negative_on_downtrend():
    t = trend_strength(_uptrend(step=-0.3))
    assert t < 0


def test_realized_vol_positive_and_finite():
    v = realized_vol(_uptrend())
    assert v >= 0


def test_vol_percentile_bounds():
    history = [_uptrend(base=b, step=0.1) for b in range(5)]
    pct = vol_percentile(history, current_window=21)
    assert 0.0 <= pct <= 1.0


def test_rule_labels():
    assert regime_label(0.9, 0.05, 0.1) == "high_vol"
    assert regime_label(0.1, 0.05, 0.1).startswith("bull")
    assert regime_label(0.1, -0.05, 0.1).startswith("bear")
    assert regime_label(0.5, 0.0, 90.0) == "neutral"  # CHOP scale 0-100


def test_choppiness_close_only_is_on_the_same_0_100_scale():
    """Close-only input now uses 100*(1 - efficiency ratio): the SAME 0-100
    scale and direction as the OHLC branch. It used to return a 0-1 dispersion
    (~0.01), which is why `overlays` passed a literal 0.4 and the label's
    choppiness branch could never fire."""
    c = choppiness(_uptrend())
    assert c is not None
    assert 0.0 <= c <= 100.0
    # a monotone trend is maximally efficient -> LOW choppiness
    assert c < CHOP_TREND_THRESHOLD
    # a flat tape makes no directional progress -> maximally choppy
    assert choppiness([100.0] * 40) == 100.0


def test_choppiness_is_none_when_unmeasurable():
    """Neither branch can be measured -> None, never a fabricated neutral."""
    assert choppiness([]) is None
    assert choppiness([100.0, 101.0, 102.0]) is None


def test_regime_label_moves_with_the_trend_on_the_default_path():
    """Regression for the dead chop branch: with vol_pct in the middle band
    (the common case) the label used to be `neutral` whatever the trend was,
    because overlays passed a literal chop of 0.4 against a 0.30 default."""
    from tradingagents.strategies.overlays import build_strategy_overlays

    cfg = {"enable_strategy_overlays": True}
    up = build_strategy_overlays(cfg, _trend_closes())
    down = build_strategy_overlays(cfg, _trend_closes(step=-0.05))
    assert up is not None and down is not None
    assert up["regime"] != down["regime"]
    assert up["regime"] == "bull" and down["regime"] == "bear"


def test_chop_threshold_sits_on_the_producers_own_scale():
    """The threshold must be comparable with what `choppiness` returns: the
    canonical branch is 0-100, so the trending/ranging split is 30. The other
    caller passed a literal 0.4 against a 0.30 default, which made the branch
    unreachable; this pins the contract in both directions."""
    highs = [100.0 + 1.0 * i for i in range(30)]
    lows = [99.0 + 1.0 * i for i in range(30)]
    closes = [99.5 + 1.0 * i for i in range(30)]
    c = choppiness(closes, highs=highs, lows=lows, window=14)
    assert c is not None and c < CHOP_TREND_THRESHOLD
    # a measurably trending tape fires the branch, in the direction of the trend
    assert regime_label(0.5, 0.05, c) == "bull"
    assert regime_label(0.5, -0.05, c) == "bear"
    # a ranging tape does not
    assert regime_label(0.5, 0.05, 70.0) == "neutral"
    # and an unmeasurable one does not assert a trend either
    assert regime_label(0.5, 0.05, None) == "neutral"


def test_choppiness_ohlc_trend_is_low():
    """Canonical CHOP (0-100): a monotone uptrend is LOW CHOP (trending),
    a tight range-highs/lows series is HIGH CHOP (ranging)."""
    highs = [100.0 + 1.0 * i for i in range(30)]
    lows = [99.0 + 1.0 * i for i in range(30)]
    closes = [99.5 + 1.0 * i for i in range(30)]
    c = choppiness(closes, highs=highs, lows=lows, window=14)
    assert 0.0 <= c <= 100.0
    assert c < 40.0  # monotone trend -> low CHOP (not the old 0-1 std)
    # a wide, tight-range oscillation (noisy but bounded) reads high CHOP-ish
    ch = [100.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    lh = [95.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    ll = [90.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    c2 = choppiness(ch, highs=lh, lows=ll, window=14)
    assert c2 > c

def _trend_closes(n=260, base=100.0, step=0.05):
    """Monotone uptrend close series (low vol, above SMA200)."""
    return [base + step * i for i in range(n)]


def test_regime_market_stress_blocks_on_high_index_vol():
    # stock series calm, index series extremely volatile -> market_stress
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    # volatile index: alternate +/- big moves
    idx = []
    v = 100.0
    for i in range(260):
        v += (25.0 if i % 2 == 0 else -25.0)
        idx.append(v)
    rg = regime_gate_read(calm, cfg={"market_stress_vol_cap": 0.8}, index_closes=idx)
    assert rg["market_stress"] is True
    assert rg["pass"] is False
    assert any("market stress" in r for r in rg["reasons"])


def test_regime_market_stress_off_without_index():
    # no index series -> market_stress False, pass unaffected
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    rg = regime_gate_read(calm, cfg={})
    assert rg["market_stress"] is False      # default leg (no index -> False)
    assert rg["pass"] is True


def test_regime_market_stress_index_returns_fields():
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    rg = regime_gate_read(calm, cfg={}, index_closes=calm)
    assert "index_vol_pct" in rg and "index_fast_downtrend" in rg
    assert "market_stress" in rg
