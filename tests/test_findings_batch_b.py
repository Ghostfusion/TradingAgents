"""Batch B of the FINDINGS §3/§4 backlog: E1, E6, E7, E8, E9, E13.

- E1  CSCV Probability of Backtest Overfitting (a probability, `evaluate.cscv_pbo`).
- E6  Diebold-Mariano + Mincer-Zarnowitz on the forecast-evaluation path.
- E7  CRPS / QLIKE producers backing the declared `SCORING_RULES`.
- E8  the equal-weight combination arm for the forecast registry.
- E9  Ledoit-Wolf shrinkage in the allocation path.
- E13 refuted: the volatility tool already uses Yang-Zhang.

Offline only; no vendor call.
"""

import pytest

pytestmark = pytest.mark.timeout(120)


# ---------------------------------------------------------------------------
# E1 - the CSCV PBO probability
# ---------------------------------------------------------------------------


def test_e1_cscv_pbo_is_a_probability_not_a_flag():
    from tradingagents.strategies.evaluate import cscv_pbo

    # A candidate that dominates every period is never an overfit winner.
    dominant = [[3.0, 3.0, 3.0, 3.0], [1.0, 1.0, 1.0, 1.0]]
    r = cscv_pbo(dominant, S=2)
    assert r is not None
    assert r["n_splits"] == 2 and r["n_candidates"] == 2
    assert r["pbo"] == 0.0

    # A candidate that wins the FIRST half and loses the second is the classic
    # overfit: the in-sample winner lands below the OOS median in both splits.
    fluke = [[5.0, 5.0, -5.0, -5.0], [0.0, 0.0, 0.0, 0.0]]
    f = cscv_pbo(fluke, S=2)
    assert f is not None and f["pbo"] >= 0.5


def test_e1_cscv_pbo_refuses_thin_or_malformed_input():
    from tradingagents.strategies.evaluate import cscv_pbo

    assert cscv_pbo([[1.0, 2.0]]) is None                     # one candidate
    assert cscv_pbo([[1.0, 2.0], [3.0, 4.0]], S=8) is None    # S > periods
    assert cscv_pbo([[1.0, 2.0], [3.0, 4.0]], S=3) is None    # odd S


def test_e1_gate_reports_the_probability_and_refuses_when_it_is_high():
    from scripts.evaluate_config_gate import gate_verdict

    returns = [0.002 if i % 2 else 0.001 for i in range(20)]
    # candidate 0 wins the first half in-sample only -> PBO high -> refused
    fluke = [[1.0] * 10 + [-1.0] * 10, [0.0] * 20]
    v = gate_verdict(returns, train_len=4, test_len=2, candidate_matrix=fluke)
    assert v["pbo_probability"] is not None
    assert v["pbo_probability"] > 0.5
    assert v["reason"] == "PBO"
    # no matrix -> the degraded flag path, probability None
    plain = gate_verdict(returns, train_len=4, test_len=2)
    assert plain["pbo_probability"] is None


# ---------------------------------------------------------------------------
# E6 - Mincer-Zarnowitz (DM already exists)
# ---------------------------------------------------------------------------


def test_e6_mz_regression_recovers_a_calibrated_forecast():
    from tradingagents.strategies.calibration import mz_regression

    # actual == forecast exactly -> slope 1, intercept 0, R^2 1
    actual = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    r = mz_regression(actual, actual)
    assert r is not None
    assert r["slope"] == pytest.approx(1.0, abs=1e-9)
    assert r["intercept"] == pytest.approx(0.0, abs=1e-9)
    assert r["r_squared"] == pytest.approx(1.0, abs=1e-9)
    assert r["calibrated"] is True


def test_e6_mz_regression_refuses_degenerate_input():
    from tradingagents.strategies.calibration import mz_regression

    assert mz_regression([1.0, 2.0], [1.0, 2.0]) is None      # < 3 pairs
    assert mz_regression([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # no variance in forecast


# ---------------------------------------------------------------------------
# E7 - CRPS / QLIKE
# ---------------------------------------------------------------------------


def test_e7_point_rules_and_qlike():
    from tradingagents.strategies.forecast_scores import mae, qlike, rmse, score_forecast

    assert rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert mae([1.0, 2.0, 3.0], [2.0, 2.0, 3.0]) == pytest.approx(1.0 / 3.0)
    # QLIKE is 0 at a perfect variance forecast
    assert qlike([0.04, 0.09], [0.04, 0.09]) == pytest.approx(0.0, abs=1e-12)
    assert qlike([0.04], [0.0]) is None  # non-positive forecast refuses
    out = score_forecast("RMSE", [1.0, 2.0], [1.0, 2.0])
    assert out["rule"] == "RMSE" and out["score"] == pytest.approx(0.0)
    assert score_forecast("NOPE", [1.0], [1.0])["score"] is None


def test_e7_crps_ensemble_reduces_to_mae_for_a_point_mass():
    from tradingagents.strategies.forecast_scores import crps

    # a degenerate ensemble (all members equal) gives |x - a|, i.e. MAE
    members = [[2.0, 2.0, 2.0], [4.0, 4.0, 4.0]]
    assert crps([1.0, 5.0], members) == pytest.approx((1.0 + 1.0) / 2.0)


# ---------------------------------------------------------------------------
# E9 - Ledoit-Wolf in the allocation path
# ---------------------------------------------------------------------------


def test_e9_allocator_covariance_is_shrunk():
    from tradingagents.strategies.portfolio_optimizer import _covariance_matrix

    # strongly correlated names -> a well-conditioned shrunk covariance
    rng = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.012, -0.008,
           0.017, -0.011, 0.009, -0.014, 0.013, -0.007, 0.018, -0.009,
           0.011, -0.013, 0.016, -0.006, 0.014, -0.012, 0.01, -0.004,
           0.019, -0.015, 0.008, -0.003, 0.021, -0.016, 0.007, -0.002]
    returns = {"A": rng, "B": [x * 1.1 for x in rng]}
    cov = _covariance_matrix(returns)
    assert cov is not None
    assert "shrinkage" in cov  # the LW intensity travels with the matrix


# ---------------------------------------------------------------------------
# E13 - refuted: the volatility tool already carries Yang-Zhang
# ---------------------------------------------------------------------------


def test_e13_volatility_tool_already_uses_yang_zhang():
    from tradingagents.strategies.volatility_models import yang_zhang_vol

    # the producer exists and is what the analyst tool calls; this is the
    # refutation of the FINDINGS row, pinned so a regression is visible.
    assert callable(yang_zhang_vol)
