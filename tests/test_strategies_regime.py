"""Phase 1 unit tests: regime features + rule labels (offline, no hmm)."""

from tradingagents.strategies.regime import (
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
    assert regime_label(0.5, 0.0, 0.9) == "neutral"


def test_choppiness_bounds():
    c = choppiness(_uptrend())
    assert 0.0 <= c <= 1.0
