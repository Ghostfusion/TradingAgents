"""Phase 2 regime breadth-depth leaves: the cumulative A/D line + Zweig thrust
(``market_breadth.advance_decline_line``) and the participation / correlation /
concentration / cross-asset / interaction / composite / statistical-inference
producers in ``breadth_depth``. Every case is deterministic and offline."""

import math

import pytest

from tradingagents.strategies.breadth_depth import (
    _chow_test,
    _coverage_confidence,
    _factor_weighted_confidence,
    _gaussian_mixture_probability,
    _logistic_normalize,
    _mahalanobis_distance,
    _regime_similarity,
    _robust_z,
    _rolling_z,
    _winsorize_series,
    average_pairwise_correlation,
    concentration_hhi,
    interaction_terms,
    market_participation,
    pair_spread,
    regime_composite,
)
from tradingagents.strategies.market_breadth import advance_decline_line

pytestmark = pytest.mark.timeout(180)


def _closes(returns, start=100.0):
    """Closes from a per-session return list (length n -> n+1 closes)."""
    c = [start]
    for r in returns:
        c.append(c[-1] * (1.0 + r))
    return c


# --- REG-5 / REG-6: cumulative A/D line + Zweig thrust ---------------------


def test_advance_decline_line_accumulates_the_known_net_counts():
    """3 names always up, 1 always down -> net +2 every session, so the
    cumulative line is 2, 4, ... and the thrust share is 0.75 (never depressed)."""
    panel = {
        "UP1": _closes([0.01] * 24),
        "UP2": _closes([0.01] * 24),
        "UP3": _closes([0.01] * 24),
        "DOWN": _closes([-0.01] * 24),
    }
    got = advance_decline_line(panel, min_n=2)
    assert got["sessions"] == 24
    assert got["net"] == [2] * 24
    assert got["ad_line"] == [2 * (i + 1) for i in range(24)]
    assert got["advancers"] == [3] * 24 and got["decliners"] == [1] * 24
    assert got["zweig_thrust"]["current_ratio"] == pytest.approx(0.75)
    assert got["zweig_thrust"]["active"] is False  # never crossed from <0.40


def test_zweig_thrust_fires_when_the_share_crosses_low_to_high():
    """10 names: first 25 sessions 2 up (share 0.2), last 5 sessions 9 up (share
    0.9) -> the advance share's EMA rose from below 0.40 to above 0.615 inside
    the 10-session window (the canonical producer's EMA event)."""
    sessions, names = 30, 10
    up = {}
    for t in range(sessions):
        winners = {0, 1} if t < 25 else set(range(9))
        for i in range(names):
            up[(t, i)] = i in winners
    panel = {}
    for i in range(names):
        rets = [0.01 if up[(t, i)] else -0.01 for t in range(sessions)]
        panel[f"N{i}"] = _closes(rets)
    got = advance_decline_line(panel, min_n=2)
    assert got["net"][:25] == [-6] * 25
    assert got["net"][25:] == [8] * 5
    assert got["zweig_thrust"]["active"] is True


def test_advance_decline_line_withholds_thrust_on_a_small_panel_and_empty_map():
    panel = {f"N{i}": _closes([0.01] * 12) for i in range(3)}
    got = advance_decline_line(panel, min_n=100)
    assert got["small_sample"] is True
    assert got["ad_line"] == [3 * (i + 1) for i in range(12)]  # counts survive
    assert got["zweig_thrust"]["active"] is None
    assert got["zweig_thrust"]["current_ratio"] is None
    assert "sample" in got["reason"]
    assert advance_decline_line({}) is None


# --- REG-7 / §12: participation counts -------------------------------------


def test_market_participation_counts_positive_returns_and_trend():
    panel = {
        "UP1": _closes([0.01] * 30),
        "UP2": _closes([0.01] * 30),
        "UP3": _closes([0.01] * 30),
        "DOWN": _closes([-0.01] * 30),
    }
    got = market_participation(panel, horizons=(20,), trend_windows=(10, 20), min_n=2)
    assert got["positive_return_counts"][20] == 3
    assert got["positive_return_n"] == 4
    assert got["participation_rate"] == pytest.approx(0.75)
    assert got["participation_rate_by_horizon"][20] == pytest.approx(0.75)
    assert got["positive_trend_count"] == 3
    assert got["positive_trend_rate"] == pytest.approx(0.75)


def test_market_participation_keeps_counts_but_withholds_rates_when_small():
    panel = {f"N{i}": _closes([0.01] * 30) for i in range(3)}
    got = market_participation(panel, horizons=(20,), min_n=100)
    assert got["small_sample"] is True
    assert got["positive_return_counts"][20] == 3  # a count is a count
    assert got["participation_rate"] is None
    assert got["participation_rate_by_horizon"][20] is None
    assert "sample" in got["reason"]
    assert market_participation({}) is None


# --- REG-8 / §13: average pairwise correlation + spike z -------------------


def _varying_corr_panel():
    """Deterministic: a shared sine plus a small then large idiosyncratic term, so
    the rolling average correlation is high early and collapses late."""
    def pseudo(i, j):
        return math.sin((i + 1) * (j + 7) * 2.399963)

    base = [math.sin(j / 4) for j in range(120)]
    return {
        f"N{i}": [
            base[j] + (0.05 if j < 60 else 3.0) * pseudo(i, j) for j in range(120)
        ]
        for i in range(4)
    }


def test_average_pairwise_correlation_reads_a_negative_spike():
    got = average_pairwise_correlation(_varying_corr_panel(), window=20, min_obs=5)
    assert got["unavailable"] is None
    assert got["n_names"] == 4
    assert got["rolling_points"] > 0
    assert got["spike_z"] is not None and got["spike_z"] < 0  # corr collapsed late


def test_average_pairwise_correlation_refuses_one_name():
    got = average_pairwise_correlation({"only": [0.1, -0.2, 0.3]}, window=2)
    assert got["avg_corr"] is None
    assert "below the 2" in got["unavailable"]
    assert average_pairwise_correlation({})["unavailable"]


# --- REG-9 / §16: concentration HHI / effective-N --------------------------


def test_concentration_hhi_equal_weights_gives_1_over_n():
    got = concentration_hhi({f"n{i}": 1.0 for i in range(5)})
    assert got["hhi"] == pytest.approx(0.2)
    assert got["effective_n"] == pytest.approx(5.0)
    assert got["n_assets"] == 5


def test_concentration_hhi_refuses_a_negative_weight_and_empty():
    got = concentration_hhi({"a": 1.0, "b": -1.0})
    assert got["hhi"] is None
    assert "negative" in got["unavailable"]
    assert concentration_hhi([]) is None


# --- REG-13 / §58-§63: cross-asset pair spreads ----------------------------


def test_pair_spread_is_the_return_difference():
    a = _closes([0.01] * 25)
    b = _closes([0.0] * 25)
    got = pair_spread(a, b, window=21, label_a="cyclicals", label_b="defensives")
    assert got["spread"] == pytest.approx(got["ret_a"] - got["ret_b"])
    assert got["ret_a"] > 0 and got["ret_b"] == pytest.approx(0.0)


def test_pair_spread_refuses_a_short_or_non_positive_series():
    short = pair_spread([100, 101], [100, 102], window=21)
    assert short["spread"] is None and short["unavailable"]
    got = pair_spread(_closes([0.01] * 25), [100.0, 100.0, 100.0, 0.0] + [100.0] * 21,
                      window=21)
    assert got["spread"] is None and got["unavailable"]


# --- REG-14 / §64-§66: interaction terms -----------------------------------


def test_interaction_terms_product_the_three_library_forms():
    got = interaction_terms(
        trend_strength=1.0, breadth=0.5, volatility_stress=0.2,
        correlation=0.6, volatility=0.3,
    )
    assert got["terms"]["trend_breadth"] == pytest.approx(0.5)
    assert got["terms"]["trend_vol"] == pytest.approx(0.8)  # 1.0 * (1 - 0.2)
    assert got["terms"]["correlation_vol"] == pytest.approx(0.18)


def test_interaction_terms_refuses_a_missing_factor():
    got = interaction_terms(trend_strength=1.0)
    assert got["terms"]["trend_breadth"] is None
    assert "trend_strength and breadth" in got["unavailable"]["trend_breadth"]


# --- REG-15 / §68-§73: declared composites ---------------------------------


def test_regime_composite_withholds_the_invented_index_and_reports_components():
    got = regime_composite({"breadth_50": 60.0, "participation": 0.4}, label="breadth")
    assert got["composite"] is None
    assert got["weights_declared"] is False
    assert "no declared weight vector" in got["unavailable"]
    assert got["components"] == {"breadth_50": 60.0, "participation": 0.4}


def test_regime_composite_computes_when_weights_are_declared():
    got = regime_composite(
        {"a": 1.0, "b": None, "c": 3.0}, weights={"a": 1.0, "b": 1.0, "c": 1.0}
    )
    assert got["weights_declared"] is True
    assert got["composite"] == pytest.approx(2.0)  # (1+3)/2 measured weights
    assert got["coverage"] == pytest.approx(2 / 3, abs=1e-4)


# --- REG-18 / §43, §76-§78, §81, §85-§88, §92, §95 -------------------------


def test_chow_test_detects_a_slope_break():
    y = [1.0, 2.0, 3.05, 3.95, 5.0, 5.0, 7.1, 8.9, 11.05, 13.0]
    got = _chow_test(y, 5)
    assert got["f_stat"] is not None and got["f_stat"] > 0
    assert got["n1"] == 5 and got["n2"] == 5


def test_chow_test_refuses_a_perfect_fit_and_an_out_of_range_break():
    got = _chow_test([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], 4)
    assert got["f_stat"] is None
    assert "exactly" in got["unavailable"]
    assert _chow_test([1.0, 2.0, 3.0], 9) is None


def test_robust_z_uses_the_median_mad_scale():
    got = _robust_z(5.0, [1, 2, 3, 4, 5])
    assert got["median"] == pytest.approx(3.0)
    assert got["mad"] == pytest.approx(1.0)
    assert got["z"] == pytest.approx(2.0 / 1.4826)


def test_robust_z_refuses_a_zero_mad():
    got = _robust_z(3.0, [3, 3, 3, 3])
    assert got["z"] is None
    assert "MAD is zero" in got["unavailable"]


def test_winsorize_series_clips_to_the_quantiles():
    got = _winsorize_series([1, 2, 3, 4, 100])
    assert max(got["winsorized"]) == pytest.approx(got["upper_value"])
    assert got["winsorized"][-1] < 100
    assert max(got["winsorized"]) <= got["upper_value"]


def test_winsorize_series_refuses_a_bad_quantile_pair():
    got = _winsorize_series([1, 2, 3], lower=0.9, upper=0.1)
    assert got["winsorized"] is None
    assert got["unavailable"]
    assert _winsorize_series([]) is None


def test_logistic_normalize_is_a_pure_0_100_read():
    assert _logistic_normalize(0.0) == pytest.approx(50.0)
    assert _logistic_normalize(1e9) == pytest.approx(100.0)
    assert _logistic_normalize(-1e9) == pytest.approx(0.0)


def test_rolling_z_normalizes_and_refuses_a_constant_series():
    got = _rolling_z([1.0, 2.0, 3.0, 4.0, 5.0], window=3, min_obs=2)
    assert got["z"][0] is None  # no window yet
    assert got["z"][1] == pytest.approx(0.707107, abs=1e-6)  # (2-1.5)/sd([1,2])
    assert got["z"][2] == pytest.approx(1.0)  # (3 - 2) / 1
    assert got["unavailable"] is None
    flat = _rolling_z([2.0, 2.0, 2.0], window=3)
    assert all(v is None for v in flat["z"]) and flat["unavailable"]


def test_mahalanobis_distance_and_its_refusal():
    got = _mahalanobis_distance([1.0, 2.0], [0.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
    assert got["distance"] == pytest.approx(math.sqrt(5.0))
    bad = _mahalanobis_distance([1.0, 2.0], [0.0, 0.0], [[1.0, 1.0], [1.0, 1.0]])
    assert bad["distance"] is None and "singular" in bad["unavailable"]


def test_regime_similarity_normalizes_and_refuses_underflow():
    got = _regime_similarity({"a": 0.0, "b": 2.0})
    assert got["argmax"] == "a"
    assert sum(got["probability"].values()) == pytest.approx(1.0)
    under = _regime_similarity({"a": 1000.0})
    assert under["argmax"] is None and under["unavailable"]


def test_gaussian_mixture_probability_and_refusal():
    got = _gaussian_mixture_probability(
        [0.0],
        [
            {"weight": 1.0, "mean": [0.0], "cov": [[1.0]]},
            {"weight": 1.0, "mean": [3.0], "cov": [[1.0]]},
        ],
    )
    assert sum(got["probability"]) == pytest.approx(1.0)
    assert got["argmax"] == 0
    bad = _gaussian_mixture_probability(
        [0.0], [{"weight": 1.0, "mean": [0.0], "cov": [[0.0]]}]
    )
    assert bad["probability"] is None and "singular" in bad["unavailable"]
    assert _gaussian_mixture_probability(None, []) is None


def test_coverage_confidence_product_and_refusal():
    assert _coverage_confidence(0.8, 0.5)["confidence"] == pytest.approx(0.4)
    missing = _coverage_confidence(0.8, None)
    assert missing["confidence"] is None and missing["unavailable"]


def test_factor_weighted_confidence_and_refusal():
    got = _factor_weighted_confidence(
        [{"weight": 1.0, "availability": 1.0, "quality": 0.5, "freshness": 0.5}]
    )
    assert got["confidence"] == pytest.approx(0.25)
    zero = _factor_weighted_confidence([{"weight": 0.0, "availability": 1.0,
                                        "quality": 1.0, "freshness": 1.0}])
    assert zero["confidence"] is None and zero["unavailable"]
    assert _factor_weighted_confidence([]) is None
