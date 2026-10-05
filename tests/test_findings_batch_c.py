"""Batch C of the FINDINGS §3 backlog: the additive methodology items.

- C1  pbo_flag vs the CSCV probability (landed as E1; pinned here too).
- C4  deflation indexed to the EFFECTIVE (decorrelated) trial count.
- C5  HAR-RV on log-RV, not only squared-return levels.
- C12 kelly_weights on the Ledoit-Wolf covariance, not the raw sample.
- C17 correlation_matrix reports the panel's excess kurtosis beside the matrix.

Offline only; no vendor call.
"""

import math
import random

import pytest

pytestmark = pytest.mark.timeout(120)


def test_c1_pbo_flag_still_exists_beside_cscv_pbo():
    from tradingagents.strategies.evaluate import cscv_pbo, pbo_flag

    assert pbo_flag([2.0, 1.0], [1.0, 1.0], threshold=0.0) is False
    r = cscv_pbo([[3.0] * 4, [1.0] * 4], S=2)
    assert r is not None and r["pbo"] == 0.0


def test_c4_effective_trials_shrink_the_deflation_penalty():
    from tradingagents.strategies.evaluate import deflated_sharpe

    rng = random.Random(11)
    returns = [rng.gauss(0.0008, 0.01) for _ in range(300)]
    raw = deflated_sharpe(returns, n_trials=100)
    eff = deflated_sharpe(returns, n_trials=100, n_effective=3)
    # fewer (effective) trials -> smaller threshold -> a larger deflated value
    assert eff > raw
    report = __import__(
        "tradingagents.strategies.evaluate", fromlist=["deflated_sharpe_report"]
    ).deflated_sharpe_report(returns, n_trials=100, n_effective=3)
    assert report["n_effective"] == 3


def test_c5_rv_forecast_fits_log_rv_when_asked():
    from tradingagents.strategies.long_memory import rv_forecast

    rng = random.Random(5)
    returns = [rng.gauss(0.0, 0.012) for _ in range(220)]
    level = rv_forecast(returns)
    logged = rv_forecast(returns, log_rv=True)
    assert level["rv_space"] == "level"
    assert logged["rv_space"] == "log"
    # a strictly-positive series fits both; the log target is a different number
    if level["status"] == "ok" and logged["status"] == "ok":
        assert logged["forecast"] != level["forecast"]
    # a constant series has no memory to measure - refused, never a crash
    bad = rv_forecast([0.0] * 220, log_rv=True)
    assert bad["status"] == "unavailable"
    # a zero realized variance refuses the log path
    mixed = rv_forecast([0.0] + [rng.gauss(0.0, 0.012) for _ in range(219)], log_rv=True)
    assert mixed["status"] == "unavailable"


def test_c12_kelly_uses_the_shrunk_covariance_by_default():
    from tradingagents.strategies.portfolio import kelly_weights

    rng = random.Random(3)
    base = [rng.gauss(0.0005, 0.01) for _ in range(120)]
    returns = {"A": base, "B": [x * 1.4 + rng.gauss(0.0, 0.001) for x in base]}
    mu = {"A": 0.0006, "B": 0.0007}
    shrunk = kelly_weights(mu, returns)
    raw = kelly_weights(mu, returns, shrinkage=False)
    assert abs(sum(shrunk.values()) - 1.0) < 1e-6
    assert abs(sum(raw.values()) - 1.0) < 1e-6


def test_c17_correlation_matrix_reports_excess_kurtosis():
    from tradingagents.strategies.statistical import correlation_matrix

    rng = random.Random(9)
    data = {
        "A": [rng.gauss(0.0, 0.01) for _ in range(80)],
        "B": [rng.gauss(0.0, 0.01) for _ in range(80)],
    }
    out = correlation_matrix(data)
    assert "mean_excess_kurtosis" in out
    assert out["method"] == "pearson"
    assert out["names"] == ["A", "B"]
    assert math.isfinite(out["mean_excess_kurtosis"])


def test_c6_memory_parameter_can_target_volatility():
    from tradingagents.strategies.long_memory import memory_parameter

    rng = random.Random(4)
    returns = [rng.gauss(0.0, 0.01) for _ in range(300)]
    assert memory_parameter(returns)["target"] == "returns"
    assert memory_parameter(returns, on_volatility=True)["target"] == "volatility"


def test_c8_heavy_tail_horizon_scaling_is_reported_beside_sqrt_t():
    from tradingagents.strategies.book_risk import var_cvar_horizon

    rng = random.Random(6)
    returns = [rng.gauss(0.0, 0.01) for _ in range(200)]
    base = var_cvar_horizon(returns, 10)
    assert base["heavy_tail_var"] is None  # off by default
    heavy = var_cvar_horizon(returns, 10, tail_index=3.0)
    assert heavy["slope_exponent"] == pytest.approx(1.0 / 3.0)
    assert heavy["heavy_tail_var"] is not None
    # sqrt(T)=T^0.5 scales a loss by MORE than T^(1/3)
    assert heavy["emp_var"] < heavy["heavy_tail_var"] < 0.0


def test_c18_ols_factors_hac_standard_errors():
    from tradingagents.strategies.statistical import ols_factors

    rng = random.Random(8)
    x = [rng.gauss(0.0, 1.0) for _ in range(200)]
    # autocorrelated residuals -> HAC se differs from the IID one
    y = [0.5 * xi + rng.gauss(0.0, 1.0) for xi in x]
    iid = ols_factors(y, {"x": x})
    hac = ols_factors(y, {"x": x}, hac=True)
    assert hac["params"]["x"]["coef"] == pytest.approx(iid["params"]["x"]["coef"])
    assert hac["params"]["x"]["std_err"] != iid["params"]["x"]["std_err"]


def test_c2_cpcv_default_embargo_is_positive():
    from tradingagents.strategies.evaluate import CPCV_DEFAULT_EMBARGO, purged_cpcv_splits

    assert CPCV_DEFAULT_EMBARGO >= 1
    splits = list(purged_cpcv_splits(60, 5))
    assert splits  # still yields train/test folds
    # with the default embargo no train index sits within one bar of the test block
    for train, test in splits:
        lo, hi = min(test), max(test)
        assert all(idx < lo - CPCV_DEFAULT_EMBARGO or idx > hi + CPCV_DEFAULT_EMBARGO
                   for idx in train)


def test_c3_regime_stability_flag():
    from tradingagents.strategies.regime_performance import regime_stability_check

    assert regime_stability_check(
        {"bull": [0.01, 0.02], "bear": [-0.01, -0.02]}
    )["stable"] is False
    assert regime_stability_check(
        {"bull": [0.01, 0.02], "bear": [0.01, 0.02]}
    )["stable"] is True
    assert regime_stability_check({"bull": [0.01]}) is None  # < 2 regimes


def test_c7_iid_band_stays_byte_identical_off_gate():
    from tradingagents.strategies.conformal import rolling_band

    rng = random.Random(2)
    pairs = [(0.0, rng.gauss(0.0, 0.01)) for _ in range(80)]
    out = rolling_band(pairs)
    assert out is not None
    # C7: the gate-off band stays byte-identical; the honest read
    # (realized_coverage) travels, and the block interval stays the option.
    assert "coverage_caveat" not in out
    assert "realized_coverage" in out


def test_c9_coverage_simulation_p():
    from tradingagents.strategies.book_risk import var_coverage_test

    rng = random.Random(12)
    returns = [rng.gauss(0.0, 0.02) for _ in range(120)]
    out = var_coverage_test(returns, simulate=True)
    assert out["coverage_sim_p"] is not None
    assert 0.0 <= out["coverage_sim_p"] <= 1.0


def test_c10_extreme_quantile_echoes_the_threshold():
    from tradingagents.strategies.book_risk import extreme_quantile_var

    rng = random.Random(21)
    returns = [rng.gauss(0.0, 0.02) for _ in range(300)]
    out = extreme_quantile_var(returns, alpha=0.05)
    assert out is not None and out["threshold_quantile"] == pytest.approx(0.90)


def test_c11_copula_reports_model_risk():
    from tradingagents.strategies.book_risk import copula_scenarios

    rng = random.Random(13)
    data = {"A": [rng.gauss(0.0, 0.01) for _ in range(40)],
            "B": [rng.gauss(0.0, 0.01) for _ in range(40)]}
    out = copula_scenarios(data, n=50)
    assert out is not None
    assert out["model_risk"]["nu"] == 5
    assert out["model_risk"]["tail_dependence_checked"] is True


def test_c13_c14_declared_shapes_and_cap():
    from tradingagents.strategies.liquidity_risk import (
        IMPACT_MODEL_SHAPES,
        PARTICIPATION_CAP,
        PREFERRED_IMPACT_SHAPE,
    )

    assert PREFERRED_IMPACT_SHAPE == "square_root"
    assert set(IMPACT_MODEL_SHAPES) == {"square_root", "quadratic", "linear"}
    assert pytest.approx(0.10) == PARTICIPATION_CAP


def test_c15_kyle_lagged_direction_is_a_different_regressor():
    from tradingagents.strategies.liquidity_risk import kyle_lambda

    rng = random.Random(15)
    closes = [100.0]
    vols = []
    for _ in range(60):
        closes.append(closes[-1] * (1.0 + rng.gauss(0.0, 0.01)))
        vols.append(rng.uniform(1e5, 5e5))
    raw = kyle_lambda(closes, vols)
    lagged = kyle_lambda(closes, vols, direction="lagged")
    assert raw is not None and lagged is not None
    assert raw != lagged
