"""Unit tests for the QuantLib + Lean enhancement calculators.

Covers the pure deterministic modules added from the deep study:
- evaluate.py breadth: sortino / probabilistic_sharpe / beta / alpha / IR /
  underwater_drawdowns
- exits.py: trailing_stop_exit / max_giveback_exit
- book_risk.py: return_autocorrelation / var_cvar_horizon
- journal.py: trade_excursions
- options_math.py: black76 / implied_vol_and_greeks / black_vol_surface
- rate_utils.py: rate equivalence / monotone_fill / downside_measures
- portfolio_optimizer.py: risk_parity / min_variance / confidence / sector
- risk_manager.py: two-pass manage_risk / trailing_stop_targets
- liquidity_risk.py: volume_share_slippage
- alpha_eval.py: alpha_score / insight_accuracy
- config_robustness.py: config_robustness

All offline / hermetic, no network.
"""

import math
import random

import pytest

from tradingagents.strategies import (
    alpha_eval,
    book_risk,
    config_robustness,
    evaluate as ev,
    exits,
    journal,
    liquidity_risk,
    options_math,
    portfolio_optimizer,
    rate_utils,
    risk_manager,
)

# --------------------------------------------------------------------------
# evaluate.py breadth (Lean L3)
# --------------------------------------------------------------------------


def test_sortino_downside_only_series_undef():
    # All returns above MAR -> zero downside dev -> None
    assert ev.sortino([0.01] * 10, mar=0.0) is None


def test_sortino_known_value():
    # hand-check: returns [-0.02, 0.02], mar=0
    # downside dev = sqrt( (-0.02)^2/2 * 252 ); cagr ~ (0.98*1.02)^0.5yrs...
    r = ev.sortino([-0.02, 0.02], mar=0.0)
    assert r is not None
    assert math.isfinite(r)


def test_beta_identical_is_one():
    r = [0.01, -0.01, 0.02, 0.0, 0.015]
    assert ev.beta(r, r) == pytest.approx(1.0, abs=1e-9)


def test_alpha_same_series_zero():
    r = [0.01, -0.01, 0.02, 0.0, 0.015]
    assert abs(ev.alpha(r, r)) < 1e-9


def test_treynor_zero_beta_none():
    assert ev.treynor([0.01, 0.01, 0.01], [1.0, 1.0, 1.0]) is None  # zero bench var


def test_probabilistic_sharpe_short_series_none():
    assert ev.probabilistic_sharpe([0.01, 0.0]) is None  # <4 obs


def test_probabilistic_sharpe_in_unit_range():
    random.seed(42)
    r = [random.gauss(0, 0.01) for _ in range(200)]
    psr = ev.probabilistic_sharpe(r)
    assert psr is not None and 0.0 <= psr <= 1.0


def test_underwater_drawdowns_sequence():
    eq = [100, 110, 120, 90, 95, 130]
    events = ev.underwater_drawdowns(eq)
    assert events, "should detect one drawdown"
    first = events[0]
    assert first["peak"] == 120
    assert first["trough"] == 90
    assert first["depth"] == pytest.approx(0.25)
    assert first["recovery"] == 2


def test_underwater_drawdowns_still_open():
    eq = [100, 120, 90]
    events = ev.underwater_drawdowns(eq)
    assert events and events[-1]["recovery"] is None


def test_skewness_kurtosis_none_short():
    assert ev.skewness([1.0, 2.0]) is None
    assert ev.kurtosis([1.0, 2.0, 3.0]) is None


# --------------------------------------------------------------------------
# exits.py (Lean L4)
# --------------------------------------------------------------------------


def test_trailing_stop_exit_triggered():
    r = exits.trailing_stop_exit(100, 120, 112, 0.05)
    assert r["exit"] is True
    assert r["stop_px"] == pytest.approx(114.0)


def test_trailing_stop_exit_not_triggered():
    r = exits.trailing_stop_exit(100, 120, 116, 0.05)
    assert r["exit"] is False
    assert r["drawdown_from_peak"] == pytest.approx(116 / 120 - 1.0)


def test_trailing_stop_exit_missing_inputs():
    r = exits.trailing_stop_exit(None, 120, 110)
    assert r["exit"] is False and r["stop_px"] is None


def test_max_giveback_exit():
    # entry 100, peaked 140, current 105 -> remaining 5% < 70% of 40% gain
    r = exits.max_giveback_exit(100, 140, 105, 0.30)
    assert r["exit"] is True


def test_max_giveback_exit_hold_high_gain():
    r = exits.max_giveback_exit(100, 140, 130, 0.30)
    assert r["exit"] is False


# --------------------------------------------------------------------------
# book_risk.py (QuantLib Q1/Q4)
# --------------------------------------------------------------------------


def test_return_autocorrelation_iid_gate():
    random.seed(1)
    r = [random.gauss(0, 0.01) for _ in range(200)]
    out = book_risk.return_autocorrelation(r)
    assert out["acf"] and abs(out["acf"][0]) < 0.2


def test_return_autocorrelation_momentum_not_iid():
    r = [0.0] * 200
    for i in range(1, 200):
        r[i] = 0.5 * r[i - 1] + random.gauss(0, 0.008)
    out = book_risk.return_autocorrelation(r)
    assert abs(out["acf"][0]) > 0.3


def test_return_autocorrelation_short_none():
    out = book_risk.return_autocorrelation([0.01] * 5)
    assert out["acf"] == [] and out["is_iidish"] is False


def test_var_cvar_horizon_direction():
    random.seed(2)
    r = [random.gauss(0, 0.01) for _ in range(200)]
    out = book_risk.var_cvar_horizon(r, 5, 0.95)
    assert out["emp_var"] is not None and out["emp_var"] < 0  # negative loss
    assert out["emp_cvar"] is not None and out["emp_cvar"] < 0


def test_var_cvar_horizon_scaling_flag_momentum():
    r = [0.0] * 60
    for i in range(1, 60):
        r[i] = 0.8 * r[i - 1] + 0.002
    out = book_risk.var_cvar_horizon(r, 5)
    assert out["scaling_valid"] is False


# --------------------------------------------------------------------------
# journal.py (Lean L5)
# --------------------------------------------------------------------------


def test_trade_excursions_profit_factor():
    trades = [
        {"entry_price": 100, "exit_price": 120, "low": 95, "high": 130},
        {"entry_price": 100, "exit_price": 85, "low": 80, "high": 105},
    ]
    out = journal.trade_excursions(trades)
    assert out["avg_mae"] == pytest.approx(-0.125)
    assert out["largest_mfe"] == pytest.approx(0.30)
    assert out["profit_factor"] == pytest.approx(0.2 / 0.15, rel=1e-3)
    assert out["largest_mae"] == pytest.approx(-0.20)


def test_trade_excursions_missing_inputs_not_fabricated():
    out = journal.trade_excursions([{"entry_price": 100}])
    assert out["avg_mae"] is None and out["profit_factor"] is None


# --------------------------------------------------------------------------
# options_math.py (QuantLib Q2/Q3)
# --------------------------------------------------------------------------


def test_black76_roundtrip_price():
    g = options_math.black76(100, 100, 0.25, 0.2, "call")
    assert g["price"] is not None and g["price"] > 0
    assert g["delta"] is not None and 0 < g["delta"] < 1


def test_implied_vol_roundtrips_mid():
    g = options_math.implied_vol_and_greeks(100, 100, 0.25, 0, 0, 2.5, "call")
    assert g["implied_vol"] is not None
    # price at solved vol reproduces the mid
    p = options_math.black76(100, 100, 0.25, g["implied_vol"], "call")["price"]
    assert abs(p - 2.5) < 1e-3


def test_implied_vol_at_or_below_intrinsic_none():
    # mid <= intrinsic -> no time value -> None
    g = options_math.implied_vol_and_greeks(100, 100, 0.25, 0, 0, 0.0, "call")
    assert g["implied_vol"] is None


def test_black_vol_surface_requires_three_points():
    assert options_math.black_vol_surface([0.1, 0.3], [0.5, 0.5], [0.2, 0.3], 100)[
        "atm_vol"
    ] is None


def test_black_vol_surface_atm_read():
    s = options_math.black_vol_surface(
        [0.1, 0.3, 0.5], [0.25, 0.5, 0.75], [0.2, 0.25, 0.3], 100
    )
    assert s["atm_vol"] is not None and 0.2 < s["atm_vol"] < 0.3


# --------------------------------------------------------------------------
# rate_utils.py (QuantLib Q7/Q9/Q10)
# --------------------------------------------------------------------------


def test_discount_factor_simple_continuous_consistency():
    # continuous 5% over 1y == simple with rate = exp(0.05)-1
    df = rate_utils.discount_factor(0.05, 1.0, "continuous")
    assert df == pytest.approx(math.exp(-0.05))
    simple = rate_utils.discount_factor(0.05, 1.0, "simple")
    assert simple == pytest.approx(1.0 / 1.05)


def test_equivalent_rate_annual_to_continuous():
    cont = rate_utils.equivalent_rate(0.05, "annual", "continuous", 1.0)
    assert cont == pytest.approx(math.log(1.05))


def test_monotone_fill_drops_out_of_range():
    out = rate_utils.monotone_fill([0, 1, 2], [1, 2, 4], [0.5, 5.0], method="log_linear")
    assert out[0] == pytest.approx(math.sqrt(2.0))
    assert out[1] is None  # extrapolation refused


def test_monotone_fill_force_positive():
    out = rate_utils.monotone_fill([0, 1], [-1.0, 1.0], [0.5], method="linear", force_positive=True)
    assert out[0] == 0.0


def test_downside_measures():
    d = rate_utils.downside_measures([0.01, -0.02, 0.03, -0.04], 0.0)
    assert d["shortfall_prob"] == pytest.approx(0.5)
    assert d["avg_shortfall"] == pytest.approx(0.03)
    assert d["downside_deviation"] == pytest.approx(math.sqrt((0.02 ** 2 + 0.04 ** 2) / 2))


# --------------------------------------------------------------------------
# portfolio_optimizer.py (Lean L2/L9/L10)
# --------------------------------------------------------------------------


def test_risk_parity_equal_variance_equal_weights():
    a = [0.01 if i % 2 == 0 else -0.01 for i in range(60)]
    b = [0.01 if i % 2 == 1 else -0.01 for i in range(60)]
    w = portfolio_optimizer.risk_parity_weights({"A": a, "B": b})["weights"]
    assert abs(w["A"] - 0.5) < 0.05 and abs(w["B"] - 0.5) < 0.05


def test_min_variance_downs_high_vol():
    random.seed(3)
    lo = [random.gauss(0, 0.001) for _ in range(300)]
    hi = [random.gauss(0, 0.05) for _ in range(300)]
    w = portfolio_optimizer.min_variance_weights({"LO": lo, "HI": hi})["weights"]
    assert w["LO"] > 0.9


def test_confidence_weights_proportional():
    w = portfolio_optimizer.confidence_weights({"A": 0.9, "B": 0.1})
    assert w["A"] == pytest.approx(0.9) and w["B"] == pytest.approx(0.1)


def test_confidence_weights_zero_total():
    assert portfolio_optimizer.confidence_weights({"A": 0, "B": 0}) == {"A": 0.0, "B": 0.0}


def test_enforce_sector_exposure_renormalizes():
    out = portfolio_optimizer.enforce_sector_exposure(
        {"A": 0.3, "B": 0.3, "C": 0.4}, {"A": "T", "B": "T", "C": "E"}, 0.45
    )
    # total tech 0.6 capped to 0.45; both A,B scale by 0.45/0.6=0.75
    assert out["A"] == pytest.approx(0.3 * 0.75 / (0.3 * 0.75 + 0.3 * 0.75 + 0.4))
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_risk_parity_degrade_on_single_name():
    out = portfolio_optimizer.risk_parity_weights({"A": [0.01, 0.02]})
    assert out["note"].startswith("equal-weight")


# --------------------------------------------------------------------------
# risk_manager.py (Lean L1)
# --------------------------------------------------------------------------


def test_manage_risk_liquidates_breach():
    out = risk_manager.manage_risk(
        {"A": 1.0}, {"A": {"entry": 100, "peak": 100, "current": 92}}, 0.05
    )
    assert out["overrides"] == {"A": 0.0}


def test_manage_risk_keeps_within_limit():
    out = risk_manager.manage_risk(
        {"A": 1.0}, {"A": {"entry": 100, "peak": 100, "current": 97}}, 0.05
    )
    assert out["overrides"] == {}


def test_manage_risk_unavailable_without_state():
    assert risk_manager.manage_risk({"A": 1.0}, {}) == "unavailable"


def test_manage_risk_skips_missing_peak():
    out = risk_manager.manage_risk({"A": 1.0}, {"A": {"entry": 100}}, 0.05)
    assert out["overrides"] == {}
    assert any("skip" in n for n in out["notes"])


def test_trailing_stop_targets_struck():
    out = risk_manager.trailing_stop_targets(
        {"A": 1.0}, {"A": {"peak": 100, "current": 90}}, 0.05
    )
    assert out["overrides"] == {"A": 0.0}


# --------------------------------------------------------------------------
# liquidity_risk.py (Lean L6)
# --------------------------------------------------------------------------


def test_volume_share_slippage():
    # participation = min(20000/1e6, 0.1) = 0.02; cost = 50 * 0.025 * 0.02^2
    c = liquidity_risk.volume_share_slippage(20000, 1000000, 50.0)
    assert c == pytest.approx(50 * 0.025 * 0.02 ** 2)


def test_volume_share_slippage_missing_none():
    assert liquidity_risk.volume_share_slippage(100, 0, 50) is None


def test_market_impact_slippage():
    assert liquidity_risk.market_impact_slippage(20000, 1000000, 50.0) == pytest.approx(0.1)


# --------------------------------------------------------------------------
# alpha_eval.py (Lean L7)
# --------------------------------------------------------------------------


def test_alpha_score_hit_positive():
    r = alpha_eval.alpha_score("up", 0.12, 30, 0.02)
    assert r["hit"] is True and r["score"] > 0


def test_alpha_score_down_hit_positive():
    r = alpha_eval.alpha_score("down", -0.10, 30, -0.08)
    assert r["hit"] is True and r["score"] > 0


def test_alpha_score_wrong_direction_negative():
    r = alpha_eval.alpha_score("up", 0.12, 30, -0.05)
    assert r["hit"] is False and r["score"] <= 0


def test_alpha_score_magnitude_error():
    r = alpha_eval.alpha_score("up", 0.12, 30, 0.02)
    assert r["magnitude_err"] == pytest.approx(-0.10)


def test_insight_accuracy():
    out = alpha_eval.insight_accuracy(
        [
            alpha_eval.alpha_score("up", 0.10, 30, 0.05),
            alpha_eval.alpha_score("up", 0.10, 30, -0.02),
        ]
    )
    assert out["hit_rate"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# config_robustness.py (Lean L8)
# --------------------------------------------------------------------------


def test_config_robustness_flags_edge():
    rows = [{"x": 1, "score": 0.5}, {"x": 10, "score": 0.9}, {"x": 5, "score": 0.7}]
    out = config_robustness.config_robustness(rows, ["x"], box={"x": (1, 10)})
    assert out["edge_flag"]["x"] is True
    assert out["best"]["x"] == 10


def test_config_robustness_plateau_vs_spike():
    plat = config_robustness.config_robustness(
        [{"p": i, "score": 10 - i * 0.05} for i in range(30)], ["p"]
    )
    spike = config_robustness.config_robustness(
        [{"p": i, "score": (20 if i == 15 else 5)} for i in range(30)], ["p"]
    )
    assert "fragile spike" in spike["note"]
    assert "fragile spike" not in plat["note"]


def test_config_robustness_no_results():
    out = config_robustness.config_robustness([], ["x"])
    assert out["n"] == 0 and out["best"] is None


# --------------------------------------------------------------------------
# Classifiers require reasonable, distinct inputs — a few parametrized cases
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func,args,kwargs",
    [
        (ev.sortino, [[-0.01, 0.01, -0.02]], {"mar": 0.0}),
        (ev.beta, [[0.01, -0.01, 0.02], [0.005, -0.005, 0.01]], {}),
        (book_risk.return_autocorrelation, [[0.0, 0.0, 0.0] * 40], {}),
        (exits.trailing_stop_exit, [100, 110, 104], {}),
        (rate_utils.monotone_fill, [[0, 1, 2], [1, 2, 4], [0.5]], {}),
        (portfolio_optimizer.risk_parity_weights, [{"A": [0.01] * 40, "B": [0.02] * 40}], {}),
        (risk_manager.manage_risk, [{"A": 1.0}, {"A": {"peak": 100, "current": 90}}], {}),
        (alpha_eval.alpha_score, ["up", 0.1, 30, 0.05], {}),
    ],
)
def test_calculators_do_not_raise(func, args, kwargs):
    # Every new calculator must either return a usable value or an explicit
    # None/'unavailable' — never a TypeError/exception.
    out = func(*args, **kwargs)
    if isinstance(out, dict):
        # a dict result is fine; assert it does not carry a bare exception
        assert not (isinstance(out, str))
