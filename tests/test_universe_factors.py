"""Phase-2 universe producers (``tradingagents.strategies.universe_factors``).

One deterministic fixture per producer and the ``NA``-honest refusal cases
(master rule: a quantity that cannot be measured returns ``None`` with a reason,
never ``0``; ``NA != 0``). Offline: every input is synthetic, no vendor call.

Covered: ``_price_target_read`` / ``_forecast_dispersion`` (§4.2/§4.3/§28), the
§16 insider ratio, the §1 size factor, the §3 acceleration, the §27 persistence,
the §18 reinvestment rate, the §22 macro beta, the block-flow read, and the
§25/§26 dilution/buyback pair.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.universe_factors import (
    BLOCK_MIN_NOTIONAL,
    _block_flow,
    _buyback_yield,
    _dilution_rate,
    _earnings_acceleration,
    _earnings_persistence,
    _economic_sensitivity,
    _forecast_dispersion,
    _insider_ratio,
    _price_target_read,
    _reinvestment_rate,
    _size_factor,
)

pytestmark = pytest.mark.timeout(180)


# --- §4.2/§4.3 price target upside + dispersion -----------------------------


def test_price_target_upside_and_dispersion_over_the_vendor_triple() -> None:
    out = _price_target_read(
        target_mean=110.0, target_median=108.0, target_high=125.0,
        target_low=95.0, price=100.0,
    )
    assert out["target"] == 110.0 and out["target_kind"] == "mean"
    assert out["upside"] == pytest.approx(0.10)
    assert out["dispersion"] == pytest.approx((125.0 - 95.0) / 110.0)
    assert out["reason"] is None


def test_price_target_falls_back_to_the_median_when_no_mean() -> None:
    out = _price_target_read(target_median=90.0, target_high=100.0,
                            target_low=80.0, price=100.0)
    assert out["target_kind"] == "median"
    assert out["upside"] == pytest.approx(-0.10)


def test_price_target_refuses_without_a_close() -> None:
    out = _price_target_read(target_mean=110.0, target_high=125.0, target_low=95.0)
    assert out["upside"] is None
    assert out["reason"] and "close price" in out["reason"]


def test_price_target_refuses_dispersion_below_the_level_floor() -> None:
    out = _price_target_read(target_mean=110.0, target_high=125.0, price=100.0)
    assert out["upside"] is not None
    assert out["dispersion"] is None
    assert out["reason"] and "targetLow" in out["reason"]


# --- §28 forecast dispersion (the open placement question) ------------------


def test_forecast_dispersion_is_the_normalised_range() -> None:
    out = _forecast_dispersion(target_mean=100.0, target_high=120.0, target_low=80.0)
    assert out["dispersion"] == pytest.approx(0.40)
    assert out["n"] == 3 and out["reason"] is None


def test_forecast_dispersion_refuses_without_both_ends() -> None:
    out = _forecast_dispersion(target_mean=100.0, target_high=120.0)
    assert out["dispersion"] is None
    assert out["reason"] and "targetLow" in out["reason"]


def test_forecast_dispersion_refuses_without_a_scale() -> None:
    out = _forecast_dispersion(target_high=120.0, target_low=80.0)
    assert out["dispersion"] is None
    assert out["reason"] and "targetMean" in out["reason"]


def test_forecast_dispersion_surfaces_the_open_placement_question() -> None:
    doc = _forecast_dispersion.__doc__ or ""
    assert "Diether" in doc and "uncertainty" in doc


# --- §16 insider ratio + average transaction size ---------------------------


def test_insider_ratio_and_average_transaction_size() -> None:
    out = _insider_ratio(buys=3, sells=1, buy_value=1000.0, sell_value=200.0)
    assert out["ibs"] == pytest.approx(0.75)
    assert out["avg_txn_value"] == pytest.approx(1200.0 / 4.0)
    assert out["n_buys"] == 3 and out["n_sells"] == 1
    assert out["reason"] is None


def test_insider_ratio_is_none_with_no_trades_never_zero() -> None:
    out = _insider_ratio(buys=0, sells=0, buy_value=0.0, sell_value=0.0)
    assert out["ibs"] is None
    assert out["reason"] and "no open-market" in out["reason"]


def test_insider_ratio_refuses_without_counts() -> None:
    out = _insider_ratio()
    assert out["ibs"] is None
    assert out["reason"] and "counts not supplied" in out["reason"]


def test_insider_average_size_refuses_without_dollar_values() -> None:
    out = _insider_ratio(buys=2, sells=0)
    assert out["ibs"] == pytest.approx(1.0)
    assert out["avg_txn_value"] is None
    assert out["reason"] and "dollar values" in out["reason"]


# --- §1 size factor ---------------------------------------------------------


def test_size_factor_z_scores_winsorised_log_market_cap() -> None:
    caps = {"A": 1e9, "B": 2e9, "C": 5e9, "D": 1e10, "E": 5e10}
    out = _size_factor(caps)
    assert out["n"] == 5 and out["min_n"] == 5
    assert set(out["factor"]) == set(caps)
    assert out["factor"]["E"] > out["factor"]["A"]
    assert out["reason"] is None


def test_size_factor_refuses_below_the_stated_cross_section_floor() -> None:
    out = _size_factor({"A": 1e9, "B": 2e9})
    assert out["factor"] is None
    assert out["reason"] and "min_n=5" in out["reason"]


def test_size_factor_refuses_a_dispersionless_cross_section() -> None:
    out = _size_factor(dict.fromkeys("ABCDE", 1000000000.0))
    assert out["factor"] is None
    assert out["reason"] and "zero dispersion" in out["reason"]


def test_size_factor_ignores_non_positive_caps() -> None:
    out = _size_factor({"A": 1e9, "B": 2e9, "C": 5e9, "D": 1e10, "E": 0.0, "F": -3.0})
    assert out["n"] == 4
    assert out["factor"] is None  # 4 < min_n
    assert "below the stated floor" in out["reason"]


# --- §3 earnings acceleration -----------------------------------------------


def test_earnings_acceleration_is_the_latest_growth_delta() -> None:
    out = _earnings_acceleration([0.05, 0.08, 0.12, 0.10])
    assert out["deltas"] == pytest.approx([0.03, 0.04, -0.02])
    assert out["acceleration"] == pytest.approx(-0.02)
    assert out["n"] == 4 and out["floor"] == 3


def test_earnings_acceleration_refuses_below_the_period_floor() -> None:
    out = _earnings_acceleration([0.05, 0.08])
    assert out["acceleration"] is None and out["deltas"] is None
    assert out["reason"] and "below the stated floor" in out["reason"]


def test_earnings_acceleration_drops_non_finite_points() -> None:
    out = _earnings_acceleration([0.05, None, 0.08, float("nan"), 0.12])
    assert out["n"] == 3
    assert out["acceleration"] == pytest.approx(0.04)


# --- §27 earnings persistence -----------------------------------------------


def test_earnings_persistence_sigma_and_lag1_autocorrelation() -> None:
    out = _earnings_persistence([1.0, 2.0, 3.0, 4.0, 5.0])
    assert out["sigma_delta_eps"] == pytest.approx(0.0)
    assert out["autocorr_lag1"] == pytest.approx(1.0)
    assert out["n"] == 5 and out["floor"] == 4


def test_earnings_persistence_refuses_below_the_period_floor() -> None:
    out = _earnings_persistence([1.0, 2.0, 3.0])
    assert out["sigma_delta_eps"] is None and out["autocorr_lag1"] is None
    assert out["reason"] and "below the stated floor" in out["reason"]


def test_earnings_persistence_flat_series_has_no_autocorrelation() -> None:
    out = _earnings_persistence([2.0, 2.0, 2.0, 2.0])
    assert out["sigma_delta_eps"] == pytest.approx(0.0)
    assert out["autocorr_lag1"] is None
    assert out["reason"] and "zero-variance" in out["reason"]


# --- §18 reinvestment rate --------------------------------------------------


def test_reinvestment_rate_from_the_delta_capital_base() -> None:
    out = _reinvestment_rate(nopat=100.0, invested_capital=500.0,
                            prior_invested_capital=400.0)
    assert out["_reinvestment_rate"] == pytest.approx(1.0)
    assert out["method"] == "delta_ic_over_nopat"


def test_reinvestment_rate_from_a_growth_rate() -> None:
    out = _reinvestment_rate(nopat=100.0, invested_capital=500.0, growth=0.10)
    assert out["_reinvestment_rate"] == pytest.approx(0.5)
    assert out["method"] == "growth_times_ic_over_nopat"


def test_reinvestment_rate_refuses_a_non_positive_capital_base() -> None:
    out = _reinvestment_rate(nopat=100.0, invested_capital=0.0, growth=0.1)
    assert out["_reinvestment_rate"] is None
    assert out["reason"] and "non-positive" in out["reason"]


def test_reinvestment_rate_refuses_a_non_positive_nopat() -> None:
    out = _reinvestment_rate(nopat=-5.0, invested_capital=500.0, growth=0.1)
    assert out["_reinvestment_rate"] is None
    assert out["reason"] and "NOPAT" in out["reason"]


def test_reinvestment_rate_refuses_without_a_base_or_a_growth() -> None:
    out = _reinvestment_rate(nopat=100.0, invested_capital=500.0)
    assert out["_reinvestment_rate"] is None
    assert out["reason"] and "prior_invested_capital or growth" in out["reason"]


# --- §22 economic sensitivity ------------------------------------------------


def _aligned(n: int = 30):
    dates = [f"2024-01-{d:02d}" for d in range(1, n + 1)]
    macro = {d: 0.5 * i for i, d in enumerate(dates)}
    stock = {d: 2.0 * v for d, v in macro.items()}
    return stock, macro


def test_economic_sensitivity_recovers_a_known_beta() -> None:
    stock, macro = _aligned()
    out = _economic_sensitivity(stock, {"rates": macro})
    assert out["betas"]["rates"] == pytest.approx(2.0)
    assert out["aligned_n"]["rates"] == 30
    assert out["reason"] is None


def test_economic_sensitivity_refuses_a_short_aligned_history() -> None:
    stock, macro = _aligned(10)
    out = _economic_sensitivity(stock, {"rates": macro}, min_obs=20)
    assert out["betas"]["rates"] is None
    assert out["aligned_n"]["rates"] == 10


def test_economic_sensitivity_windows_to_the_most_recent_observations() -> None:
    stock, macro = _aligned(40)
    out = _economic_sensitivity(stock, {"rates": macro}, window=25)
    assert out["aligned_n"]["rates"] == 25
    assert out["window"] == 25


def test_economic_sensitivity_refuses_empty_input() -> None:
    out = _economic_sensitivity({}, {})
    assert out["betas"] == {} and out["reason"]
    assert "macro series" in out["reason"]


# --- block flow (large-print detection) -------------------------------------


def test_block_flow_share_from_per_print_notionals() -> None:
    out = _block_flow([{"notional": 2e6}, {"notional": 0.5e6}, {"notional": 3e6}])
    assert out["n_prints"] == 3 and out["n_blocks"] == 2
    assert out["block_notional"] == pytest.approx(5e6)
    assert out["block_share"] == pytest.approx(5e6 / 5.5e6)
    assert out["reason"] is None


def test_block_flow_refuses_aggregate_weekly_flow() -> None:
    out = _block_flow(None)
    assert out["block_share"] is None
    assert out["reason"] and "weekly aggregates" in out["reason"]
    assert BLOCK_MIN_NOTIONAL == 1_000_000.0


def test_block_flow_refuses_rows_without_a_per_print_notional() -> None:
    out = _block_flow([{"shares": 1000, "trades": 10}])
    assert out["block_share"] is None
    assert out["reason"] and "per-print notional" in out["reason"]


# --- §25/§26 dilution rate + buyback yield ----------------------------------


def test_dilution_rate_from_the_share_count_change() -> None:
    out = _dilution_rate(shares_issued=50.0, prior_shares=1000.0)
    assert out["_dilution_rate"] == pytest.approx(0.05)
    assert out["reason"] is None


def test_dilution_rate_refuses_without_a_prior_share_count() -> None:
    out = _dilution_rate(shares_issued=50.0)
    assert out["_dilution_rate"] is None
    assert out["reason"] and "prior share count" in out["reason"]


def test_dilution_rate_refuses_without_a_change() -> None:
    out = _dilution_rate(prior_shares=1000.0)
    assert out["_dilution_rate"] is None
    assert out["reason"] and "shares_issued" in out["reason"]


def test_buyback_yield_over_a_stated_market_cap_denominator() -> None:
    out = _buyback_yield(repurchase_spend=3e9, market_cap=100e9)
    assert out["_buyback_yield"] == pytest.approx(0.03)
    assert out["denominator"] == "market_cap"
    assert out["reason"] is None


def test_buyback_yield_refuses_a_missing_price_denominator() -> None:
    out = _buyback_yield(repurchase_spend=3e9)
    assert out["_buyback_yield"] is None
    assert out["reason"] and "repurchase-price feed" in out["reason"]


def test_buyback_yield_refuses_without_spend() -> None:
    out = _buyback_yield(market_cap=100e9)
    assert out["_buyback_yield"] is None
    assert out["reason"] and "repurchase spend" in out["reason"]
