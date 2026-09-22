"""Phase 2 unit tests: Kelly sizing, vol targeting, ATR stops, CVaR budget."""

from tradingagents.strategies.size import (
    atr,
    cvar_budget,
    kelly_fraction,
    position_size_kelly,
    position_size_with_risk,
    stop_loss_atr,
    volatility_target_scale,
)


def test_kelly_bounds():
    assert abs(kelly_fraction(0.6, 1.0) - 0.2) < 1e-9
    assert kelly_fraction(0.4, 1.0) == 0.0  # no edge
    assert kelly_fraction(1.0, 2.0) == 1.0


def test_quarter_kelly_capped():
    assert position_size_kelly(0.8, fraction=0.25) < 0.5
    assert 0.0 <= position_size_kelly(0.9, max_size=0.05) <= 0.05


def test_vol_target_scale():
    calm = [0.002, -0.001, 0.003, -0.002, 0.001, 0.002, -0.001]
    scale = volatility_target_scale(calm, target_vol=0.15)
    assert 0.0 < scale <= 3.0
    assert volatility_target_scale([], 0.15) == 0.0


def test_vol_target_override_needs_no_return_series():
    """Regression: the `len(returns) < 5` guard ran BEFORE the override branch,
    so `vol_override` - documented as supplying an externally computed
    annualized vol, e.g. GARCH's long-run vol - returned 0.0 whenever the
    caller had no series to hand. A 0.0 scale silently zeroes a position size
    rather than scaling it, and it is why two callers re-derived the ratio
    inline instead of calling the one producer (rule 15).
    """
    # an override IS the input, so the series length is irrelevant
    for series in ([], [0.01] * 3, [0.01] * 30):
        got = volatility_target_scale(series, vol_override=0.25, target_vol=0.15)
        assert abs(got - 0.6) < 1e-9, series
    # the 0..3 clamp and the no-data contract are unchanged
    assert volatility_target_scale([], vol_override=0.01, target_vol=0.15) == 3.0
    assert volatility_target_scale([], vol_override=0.0, target_vol=0.15) == 0.0
    assert volatility_target_scale([], target_vol=0.15) == 0.0
    assert volatility_target_scale([], vol_override=0.25, target_vol=0.0) == 0.0


def test_atr_positive():
    high = [100.0] * 3 + [102.0] * 3
    low = [99.0] * 6
    close = [99.5] * 6
    assert atr(high, low, close) > 0


def test_stop_below_close():
    high = [100.0, 100.0, 102.0]
    low = [99.0, 99.0, 98.0]
    close = [99.5, 100.0, 101.0]
    assert stop_loss_atr(close, high, low) < close[-1]


def test_atr_is_none_when_unmeasurable():
    """Regression: `atr` returned 0.0 for a missing or mismatched series, so a
    caller testing `is not None` read "unknown volatility" as "zero
    volatility" - the NA-as-zero defect class. `stop_loss_atr` and
    `etf_risk._atr` already returned None for the same reason."""
    assert atr([1.0], [1.0], [1.0]) is None
    assert atr([1.0, 2.0], [1.0], [1.0, 2.0]) is None  # mismatched lengths
    assert atr([], [], []) is None
    assert stop_loss_atr([100.0, 101.0], [100.0], [99.0]) is None
    a = atr([100.0, 101.0, 102.0], [99.0, 100.0, 101.0], [99.5, 100.5, 101.5])
    assert a is not None and a > 0


def test_cvar_negative_tail():
    bad = [-0.1, -0.08, -0.05, 0.01, 0.05]
    assert cvar_budget(bad, alpha=0.2) < 0


def test_risk_cap_respected():
    size = position_size_with_risk(0.7, 1.0, atr=2.0, close=100.0, risk_per_trade=0.01)
    assert 0.0 < size <= 0.10  # quarter-Kelly (0.1) is the binding cap
