"""RiskScore.md §8.2 risk-scalar producers: one deterministic fixture per
producer plus the refusal cases (`NA != 0` - a producer that cannot measure
returns ``None`` or a ``None``-valued key, never ``0``).

Pure and offline: no network, no vendor call, no wall clock.
"""

import math

import pytest

from tradingagents.strategies.book_risk import (
    _fx_exposure,
    _liquidity_adjusted_cvar,
    _nonlinear_risk_penalty,
    _tail_adjusted_return,
    cvar,
    fx_move_var,
    loss_frequency_family,
    momentum_reversal,
    prob_loss,
    sterling_ratio,
    stop_hit_probability,
    volatility_window_ratio,
)
from tradingagents.strategies.liquidity_risk import (
    market_impact_slippage,
    ownership_hhi,
    portfolio_hhi,
    revenue_concentration,
)

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# RISK-2 - portfolio HHI over position weights
# ---------------------------------------------------------------------------


def test_portfolio_hhi_scale_is_the_engine_row_scale():
    # Single position = 1.0; two equal = 0.5; four equal = 0.25. The engine's
    # ramp (0.05, 0.50) is 20 / 2 equal names.
    assert portfolio_hhi({"a": 1.0}) == 1.0
    assert portfolio_hhi({"a": 0.5, "b": 0.5}) == 0.5
    assert portfolio_hhi({"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}) == 0.25
    assert portfolio_hhi([0.4, 0.6]) == 0.52


def test_portfolio_hhi_is_not_the_holder_hhi():
    """Portfolio HHI (0-1) and holder HHI (0-10000) differ by 10^4."""
    assert portfolio_hhi({"a": 1.0}) == 1.0
    assert ownership_hhi([100.0]) == 10000.0
    assert portfolio_hhi({"a": 0.5, "b": 0.5}) == 0.5
    assert ownership_hhi([50.0, 50.0]) == 5000.0


def test_portfolio_hhi_cash_sleeve_and_over_allocation():
    # Sum <= 1.0 keeps the raw weights: the uninvested half dilutes the HHI.
    assert portfolio_hhi({"a": 0.5}) == 0.25
    # Sum > 1.0 (config error) normalizes down to a valid book.
    assert portfolio_hhi({"a": 1.5, "b": 0.5}) == 0.625


# ---------------------------------------------------------------------------
# RISK-19 - revenue-share HHI for ONE vendor dimension (§50/§51)
# ---------------------------------------------------------------------------


def test_revenue_concentration_is_on_the_portfolio_hhi_scale():
    # One segment = 1.0; two equal = 0.5 (effective N 2); four equal = 0.25.
    assert revenue_concentration([1.0])["hhi"] == 1.0
    two = revenue_concentration([0.5, 0.5])
    assert two["hhi"] == 0.5 and two["effective_n"] == 2.0 and two["n"] == 2
    assert revenue_concentration([0.25] * 4)["hhi"] == 0.25
    # MSFT FY2026 REGION (probed live): 51.47% + 48.53% -> 0.5004.
    region = revenue_concentration([0.5147, 0.4853])
    assert region["hhi"] == pytest.approx(0.500432, abs=1e-6)
    # The SAME split on the holder HHI's percent scale is 10^4 larger - the
    # mix-up the producer's own `scale`/`basis` strings forbid.
    assert ownership_hhi([51.47, 48.53]) == pytest.approx(5004.3218, abs=1e-3)
    assert ownership_hhi([51.47, 48.53]) / region["hhi"] == pytest.approx(10000.0)


def test_revenue_concentration_normalizes_and_ignores_non_shares():
    # A partial breakdown is normalized to its own sum, so a reported subset
    # measures the concentration AMONG the segments it carries.
    assert revenue_concentration([3.0, 1.0])["hhi"] == pytest.approx(0.625)
    # A zero share does not dilute; negatives, None and junk are ignored.
    mixed = revenue_concentration([0.0, -1.0, "x", None, 0.5, 0.5])
    assert mixed["hhi"] == 0.5 and mixed["n"] == 2
    assert revenue_concentration([0.0, 0.0]) is None
    assert revenue_concentration([]) is None
    assert revenue_concentration(None) is None


def test_portfolio_hhi_refusals():
    assert portfolio_hhi(None) is None
    assert portfolio_hhi({}) is None
    assert portfolio_hhi({"a": 0.0}) is None
    assert portfolio_hhi({"a": -0.5}) is None
    assert portfolio_hhi([0.0, "bad"]) is None


# ---------------------------------------------------------------------------
# RISK-17 - P(R < 0)
# ---------------------------------------------------------------------------


def test_prob_loss_frequency():
    r = [0.01, -0.02, 0.03, -0.01, 0.02]
    assert prob_loss(r) == 0.4
    assert prob_loss(r, -0.015) == 0.2
    # A series that never lost measures a real 0.0, not NA.
    assert prob_loss([0.01, 0.02]) == 0.0


def test_prob_loss_refusals():
    assert prob_loss([]) is None
    assert prob_loss([None, "x"]) is None


# ---------------------------------------------------------------------------
# RISK-10 - sigma20/sigma60 ratio and expansion
# ---------------------------------------------------------------------------


def test_volatility_window_ratio_expansion():
    vals = ([0.001 if i % 2 else -0.001 for i in range(40)]
            + [0.01 if i % 2 else -0.01 for i in range(20)])
    out = volatility_window_ratio(vals, short=20, long=60)
    assert out is not None
    assert out["short"] == 20 and out["long"] == 60
    assert out["ratio"] > 1.0 and out["expansion"] > 0.0
    assert out["ratio"] == pytest.approx(
        out["sigma_short"] / out["sigma_long"], rel=1e-5
    )
    assert out["expansion"] == pytest.approx(
        (out["sigma_short"] - out["sigma_long"]) / out["sigma_long"], rel=1e-5
    )


def test_volatility_window_ratio_refusals():
    # Series shorter than the long window.
    assert volatility_window_ratio([0.01] * 30, short=20, long=60) is None
    # Degenerate windows.
    assert volatility_window_ratio([0.01] * 60, short=60, long=20) is None
    assert volatility_window_ratio([0.01] * 60, short=20, long=20) is None
    # Zero denominator: a flat series has sigma_long == 0.
    assert volatility_window_ratio([0.01] * 60, short=20, long=60) is None


# ---------------------------------------------------------------------------
# RISK-13 - Sterling ratio (return / average MDD)
# ---------------------------------------------------------------------------


def test_sterling_ratio_over_average_drawdown():
    # 1.25, -20%, then three +25%: one 20% drawdown episode, base 1.25**3.
    r = [0.25, -0.20, 0.25, 0.25, 0.25]
    out = sterling_ratio(r, periods_per_year=1.0)
    assert out is not None and out > 0.0
    assert out == pytest.approx((1.25 ** 0.6 - 1.0) / 0.2, abs=1e-6)


def test_sterling_ratio_refusals():
    assert sterling_ratio([0.01] * 10) is None  # no drawdown episode
    assert sterling_ratio([0.01]) is None  # < 2 observations
    assert sterling_ratio([]) is None


# ---------------------------------------------------------------------------
# RISK-14 - the loss-frequency family
# ---------------------------------------------------------------------------


def test_loss_frequency_family_counts():
    # 100 periods: 80 gains, 15 x -1%, 4 x -4%, 1 x -10%.
    r = [0.01] * 80 + [-0.01] * 15 + [-0.04] * 4 + [-0.10]
    out = loss_frequency_family(r)
    assert out is not None
    assert out["n"] == 100 and out["n_losses"] == 20
    assert out["downside_freq"] == 0.2
    assert out["large_loss_freq"] == 0.05  # at/below the -2% floor
    assert out["extreme_loss"] == -0.04  # simple_var(0.05) of this series
    assert out["extreme_loss_freq"] == 0.05
    assert out["crash"] == -0.08  # 2x the VaR threshold
    assert out["crash_freq"] == 0.01
    assert out["avg_loss"] == -0.0205
    assert out["worst_loss"] == -0.10


def test_loss_frequency_family_no_losses_keeps_none_keys():
    out = loss_frequency_family([0.01] * 10)
    assert out is not None
    assert out["downside_freq"] == 0.0
    assert out["large_loss_freq"] == 0.0
    assert out["avg_loss"] is None
    assert out["worst_loss"] is None


def test_loss_frequency_family_refusal():
    assert loss_frequency_family([]) is None
    assert loss_frequency_family([None, "x"]) is None


# ---------------------------------------------------------------------------
# RISK-15 - momentum-reversal leg R_short - R_long
# ---------------------------------------------------------------------------


def test_momentum_reversal_leg():
    # R_short = -0.05, R_long = 1.10*0.95 - 1 = 0.045.
    assert momentum_reversal([0.10, -0.05], short=1, long=2) == pytest.approx(-0.095)
    # R_short = 1.03*1.01 - 1, R_long = 1.02*1.03*1.01 - 1.
    assert momentum_reversal([0.02, 0.03, 0.01], short=2, long=3) == pytest.approx(-0.020806)


def test_momentum_reversal_refusals():
    assert momentum_reversal([0.1], short=1, long=2) is None  # shorter than long
    assert momentum_reversal([0.1, 0.2], short=2, long=2) is None  # degenerate
    assert momentum_reversal([]) is None


# ---------------------------------------------------------------------------
# RISK-22 - tail-adjusted return (ExpectedReturn / CVaR); PRIVATE producer,
# awaiting a leaf that holds both inputs
# ---------------------------------------------------------------------------


def test_tail_adjusted_return_uses_positive_loss():
    assert _tail_adjusted_return(0.12, 0.04) == 3.0
    # The pinned convention: the tail input is abs() of the negative cvar.
    cv = cvar([-0.05] * 10 + [0.01] * 90, 0.05)
    assert cv is not None and cv < 0
    assert _tail_adjusted_return(0.12, abs(cv)) == pytest.approx(2.4)


def test_tail_adjusted_return_refusals():
    assert _tail_adjusted_return(None, 0.04) is None
    assert _tail_adjusted_return(0.12, None) is None
    assert _tail_adjusted_return(0.12, 0.0) is None  # zero denominator
    assert _tail_adjusted_return(0.12, -0.04) is None  # mis-signed loss refused


# ---------------------------------------------------------------------------
# RISK-24 - liquidity-adjusted CVaR (CVaR + ExecutionCost_tail); PRIVATE
# producer, awaiting a leaf that holds the mix and the orders
# ---------------------------------------------------------------------------


def test_liquidity_adjusted_cvar_sums_the_tail_legs():
    r = [-0.05] * 10 + [0.01] * 90
    positions = {"a": {"order_qty": 1000.0, "adv": 100000.0, "price": 50.0}}
    out = _liquidity_adjusted_cvar(r, positions, alpha=0.05, weights={"a": 1.0})
    assert out is not None
    assert out["cvar"] == 0.05  # positive loss magnitude
    assert out["n"] == 1
    # impact_coeff * qty / adv = 0.1 * 1000 / 100000 = 0.001 return fraction.
    assert out["execution_cost_tail"] == 0.001
    assert out["liquidity_adjusted_cvar"] == 0.051
    slip = market_impact_slippage(1000.0, 100000.0, 50.0, 0.1)
    assert out["execution_cost_tail"] == pytest.approx(slip / 50.0)


def test_liquidity_adjusted_cvar_weight_averages_names():
    r = [-0.05] * 10 + [0.01] * 90
    positions = {
        "a": {"order_qty": 1000.0, "adv": 100000.0, "price": 50.0},  # 0.001
        "b": {"order_qty": 2000.0, "adv": 100000.0, "price": 25.0},  # 0.002
    }
    out = _liquidity_adjusted_cvar(r, positions, weights={"a": 0.5, "b": 0.5})
    assert out is not None and out["n"] == 2
    assert out["execution_cost_tail"] == pytest.approx(0.0015)


def test_liquidity_adjusted_cvar_refusals():
    # No measurable position -> refuse rather than print a plain CVaR.
    assert _liquidity_adjusted_cvar([-0.05] * 10, {}) is None
    assert _liquidity_adjusted_cvar([-0.05] * 10, None) is None
    # A position whose producer refuses (adv == 0) is not a measurement.
    assert _liquidity_adjusted_cvar(
        [-0.05] * 10, {"a": {"order_qty": 1.0, "adv": 0.0, "price": 10.0}}
    ) is None
    assert _liquidity_adjusted_cvar(
        [], {"a": {"order_qty": 1.0, "adv": 10.0, "price": 10.0}}
    ) is None


# ---------------------------------------------------------------------------
# RISK-23 - nonlinear risk penalty x ** gamma; PRIVATE producer, awaiting the
# engine-side alignment (the score's ramp is still linear)
# ---------------------------------------------------------------------------


def test_nonlinear_risk_penalty_exponents():
    assert _nonlinear_risk_penalty(0.5, gamma=2.0) == 0.25
    assert _nonlinear_risk_penalty(0.5, gamma=1.0) == 0.5  # the linear identity
    assert _nonlinear_risk_penalty(0.5, gamma=0.5) == pytest.approx(math.sqrt(0.5))
    # Clamped into [lo, hi] before the power.
    assert _nonlinear_risk_penalty(2.0, gamma=2.0, lo=0.0, hi=1.0) == 1.0
    assert _nonlinear_risk_penalty(-1.0, gamma=2.0, lo=0.0, hi=1.0) == 0.0


def test_nonlinear_risk_penalty_refusals():
    assert _nonlinear_risk_penalty(None, 2.0) is None
    assert _nonlinear_risk_penalty(0.5, 0.0) is None
    assert _nonlinear_risk_penalty(0.5, 2.0, lo=1.0, hi=1.0) is None


# ---------------------------------------------------------------------------
# RISK-20 - the per-unit FX VaR factor (§52), and the exposure formula that
# has no caller yet
# ---------------------------------------------------------------------------


def test_fx_move_var_is_sigma_times_z_per_position_unit():
    levels = [100.0]
    for i in range(60):
        levels.append(levels[-1] * math.exp(0.01 if i % 2 == 0 else -0.01))
    out = fx_move_var(levels)
    assert out is not None
    # The library's FXVaR = Position * FXVol * z_c - this is the factor that
    # multiplies a position, never billed as the position's own VaR.
    assert out["var_pct"] == pytest.approx(out["vol_daily"] * 1.645, abs=1e-6)
    assert out["horizon"] == 1 and out["n"] == 60 and out["z_c"] == 1.645
    # A 4-day horizon scales by sqrt(4) = 2, not by 4.
    longer = fx_move_var(levels, horizon=4)
    assert longer["var_pct"] == pytest.approx(out["var_pct"] * 2.0, abs=1e-6)


def test_fx_move_var_refusals():
    assert fx_move_var([100.0] * 30) is None  # a flat series has no variance
    assert fx_move_var([100.0, 101.0]) is None  # fewer than three levels
    assert fx_move_var([100.0] * 30, z_c=0.0) is None
    assert fx_move_var([100.0] * 30, z_c=float("nan")) is None
    assert fx_move_var([100.0] * 30, horizon=0) is None
    assert fx_move_var([]) is None


def test_fx_exposure_is_private_and_awaiting_a_caller():
    # RISK-20's balance-sheet leg: the library's formula is kept, but no vendor
    # in the chain returns a foreign-currency asset/liability split, so nothing
    # can supply the numerator today. Private = not wired behind a fake caller.
    out = _fx_exposure(400.0, 100.0, 1000.0)
    assert out is not None and out["exposure"] == pytest.approx(0.3)
    assert _fx_exposure(400.0, 400.0, 1000.0)["exposure"] == 0.0
    assert _fx_exposure(400.0, 100.0, 0.0) is None  # zero denominator
    assert _fx_exposure(None, 100.0, 1000.0) is None


# ---------------------------------------------------------------------------
# RISK-16 - P(hitting stop) over the trailing path (§33)
# ---------------------------------------------------------------------------


def test_stop_hit_probability_counts_breaching_windows():
    # One -10% bar in an 11-bar series, 3-bar windows: the three windows that
    # contain it breach a 5% stop; nine windows in total.
    out = stop_hit_probability([0.0] * 5 + [-0.10] + [0.0] * 5, 0.05, horizon=3)
    assert out is not None
    assert out["n_windows"] == 9 and out["hits"] == 3
    # p_hit is rounded to 6 dp on purpose; compare at that precision.
    assert out["p_hit"] == pytest.approx(3 / 9, abs=1e-6)
    assert out["horizon"] == 3 and out["stop_pct"] == 0.05
    assert "overlapping" in out["basis"]


def test_stop_hit_probability_is_a_path_test_not_a_terminal_test():
    """A window that dips below the stop and recovers has still hit it."""
    # -10% then +20% ends POSITIVE (-0.10 + 0.20 + the cross term = +8%), so a
    # terminal-value test would score 0.0; the running minimum breaches.
    dipped = stop_hit_probability([-0.10, 0.20], 0.05, horizon=2)
    assert dipped is not None and dipped["p_hit"] == 1.0
    assert dipped["hits"] == 1 and dipped["n_windows"] == 1
    # A path that never dips is a real 0.0 - measured, not refused.
    calm = stop_hit_probability([0.01, 0.01, 0.01, 0.01], 0.05, horizon=2)
    assert calm["p_hit"] == 0.0 and calm["hits"] == 0 and calm["n_windows"] == 3


def test_stop_hit_probability_refusals():
    # Fewer observations than the horizon leaves no window at all - while
    # exactly `horizon` of them is one window (the two-bar case above).
    assert stop_hit_probability([0.0], 0.05, horizon=2) is None
    assert stop_hit_probability([0.0] * 10, 0.05, horizon=11) is None
    assert stop_hit_probability([], 0.05) is None
    # A stop is a positive distance; zero, negative and NaN are not.
    assert stop_hit_probability([0.0] * 10, 0.0) is None
    assert stop_hit_probability([0.0] * 10, -0.05) is None
    assert stop_hit_probability([0.0] * 10, float("nan")) is None
    assert stop_hit_probability([0.0] * 10, 0.05, horizon=0) is None
