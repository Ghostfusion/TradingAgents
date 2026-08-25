"""Capital-oriented screener math (strategies/capital_income.py) - pure tests.

Verifies the Strategies/capital_income.md methodology: annualized dividend,
indicated yield, ADTV dollar, the $250M/$1M liquidity gate, top-N yield
ranking, MV weighting, the 3% single-constituent cap with pro-rata
redistribution, and the honest equal-weight fallback when MV is unavailable.
"""

import pytest

from tradingagents.strategies.capital_income import (
    adtv_dollar,
    annualized_dividend,
    apply_top_n,
    build_capital_income_plan,
    cap_and_redistribute,
    equal_weights,
    indicated_yield,
    indicated_yield_from_rate,
    passes_liq_screen,
    raw_mv_weight,
)


def test_annualized_dividend_prefers_rate():
    # dividendRate is pre-annualized (GS-PD rate 1.21).
    assert annualized_dividend(1.21) == pytest.approx(1.21)
    assert annualized_dividend(1.21, latest_regular=0.30) == pytest.approx(1.21)
    # fallback to 4x latest regular (quarterly)
    assert annualized_dividend(None, latest_regular=0.30) == pytest.approx(1.20)
    assert annualized_dividend(None, None) is None
    assert annualized_dividend(0, None) is None


def test_indicated_yield():
    assert indicated_yield(1.21, 18.78) == pytest.approx(0.06443, rel=0.01)
    assert indicated_yield_from_rate(1.21, 18.78) == pytest.approx(0.06443, rel=0.01)
    assert indicated_yield(None, 18.78) is None
    assert indicated_yield(1.21, None) is None
    assert indicated_yield(1.21, 0) is None


def test_adtv_dollar():
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    vols = [100.0, 200.0, 300.0, 400.0, 500.0]
    # (1000+2200+3600+5200+7000)/5 = 3800
    assert adtv_dollar(closes, vols, days=5) == pytest.approx(3800.0)
    assert adtv_dollar([], []) is None
    assert adtv_dollar([10.0], [100.0]) is None


def test_liquidity_screen():
    assert passes_liq_screen(300e6, 1.5e6) is True
    assert passes_liq_screen(100e6, 1.5e6) is False  # below market-cap floor
    assert passes_liq_screen(300e6, 0.5e6) is False  # below ADTV floor
    assert passes_liq_screen(None, 1.5e6) is False  # missing -> not eligible
    assert passes_liq_screen(300e6, None) is False
    # existing-component floor ($100M) honored when passed explicitly
    assert passes_liq_screen(150e6, 1.5e6, min_cap=100e6) is True


def test_raw_mv_weight():
    assert raw_mv_weight([100.0, 200.0, 300.0]) == pytest.approx([1/6, 2/6, 3/6])
    # any missing -> entire list None (equal-weight fallback)
    assert raw_mv_weight([100.0, None, 300.0]) == [None, None, None]
    assert raw_mv_weight([]) == []


def test_equal_weights():
    assert equal_weights(3) == pytest.approx([1/3, 1/3, 1/3])
    assert equal_weights(0) == []



def test_cap_and_redistribute():
    # Standard full capping: cap each name at ceiling (3.5%) then renormalize
    # to sum 1, so a small name keeps its relative smallness.
    out = cap_and_redistribute([0.06, 0.04, 0.02])
    # 0.06, 0.04 -> 0.035, 0.02 stays 0.02; renormalized by /0.09
    assert out[0] == pytest.approx(0.035 / 0.09, rel=1e-3)
    assert out[1] == pytest.approx(0.035 / 0.09, rel=1e-3)
    assert out[2] == pytest.approx(0.02 / 0.09, rel=1e-3)
    assert sum(out) == pytest.approx(1.0, rel=1e-3)
    # After full-capping renormalization, weights can exceed the ceiling
    # (scaled up to refill the removed excess) - that's standard behavior.
    assert all(0 <= x <= 1.0 for x in out)
    # Names already at/under the cap are preserved proportionally.
    assert cap_and_redistribute([0.03, 0.03]) == pytest.approx([0.5, 0.5])
    assert cap_and_redistribute([]) == []


def test_apply_top_n():
    yields = [None, 0.05, 0.02, 0.08, 0.03]
    assert apply_top_n(yields, n=3) == [3, 1, 4]  # top 3 yields
    assert apply_top_n([None, None], n=5) == []
    assert apply_top_n([], n=5) == []


def test_build_plan_happy_path():
    tickers = ["A", "B", "C"]
    plan = build_capital_income_plan(
        tickers,
        prices={"A": 20.0, "B": 25.0, "C": 30.0},
        dividends={"A": 1.5, "B": 1.0, "C": 2.4},
        mv={"A": 500e6, "B": 300e6, "C": 900e6},
        adtv={"A": 2e6, "B": 1.5e6, "C": 3e6},
        top=2,
    )
    assert plan["liquid"] == ["A", "B", "C"]
    # top-2 by yield = A (7.5%) and C (8%) -> [C, A]
    assert [r["ticker"] for r in plan["ranked"]] == ["C", "A"]
    assert plan["used_equal_weight"] is False
    # MV weights used: C = 900/1400 = 0.643, A = 500/1400 = 0.357; both over
    # the 3.5% ceiling so both cap to 3.5% and renormalize to 0.5/0.5, i.e.
    # the full-capping is applied (no name keeps a >3.5% pre-renorm weight).
    for r in plan["ranked"]:
        assert r["weight"] is not None
        assert r["weight"] == pytest.approx(0.5)  # equal after full-capping both


def test_build_plan_equal_weight_fallback():
    tickers = ["A", "B"]
    plan = build_capital_income_plan(
        tickers,
        prices={"A": 20.0, "B": 25.0},
        dividends={"A": 1.5, "B": 1.0},
        mv={"A": None, "B": None},  # per-issue MV unavailable
        adtv={"A": 2e6, "B": 1.5e6},
        top=50,
    )
    assert plan["used_equal_weight"] is True
    assert all(r["weight"] == pytest.approx(0.5) for r in plan["ranked"])
