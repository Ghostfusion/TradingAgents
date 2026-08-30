"""Computed ratios module (strategies/ratios.py) - pure/offline tests.

Verifies the ratio formulas replicate the plan-gated Massive block from
canonical line items, and the no-fabrication rule (missing input -> None/n/a).
Each test inherits the repo's pytest-timeout deadline (180s/test, 30-min cap).
"""


import pytest

from tradingagents.strategies.ratios import RENDER_ORDER, compute_ratios, render_ratios


def _fin(**over):
    base = {
        "market_cap": 1000e6,
        "total_debt": 200e6,
        "cash": 50e6,
        "operating_income": 120e6,
        "depreciation": 30e6,
        "revenue": 900e6,
        "net_income": 80e6,
        "total_equity": 500e6,
        "total_assets": 800e6,
        "operating_cashflow": 90e6,
        "capex": 30e6,
        "current_assets": 300e6,
        "current_liabilities": 150e6,
        "inventory": 60e6,
        "dividends_paid": 20e6,
    }
    base.update(over)
    return base


def test_full_ratio_block():
    r = compute_ratios(_fin())
    # EV = 1000+200-50 = 1150
    assert r["ev"] == pytest.approx(1150e6)
    # EV/EBITDA = 1150 / (120+30=150) = 7.6667
    assert r["ev_ebitda"] == pytest.approx(7.6666, rel=1e-3)
    assert r["ev_ebit"] == pytest.approx(1150e6 / 120e6)
    assert r["ev_sales"] == pytest.approx(1150e6 / 900e6)
    assert r["price_to_earnings"] == pytest.approx(1000e6 / 80e6)
    assert r["price_to_book"] == pytest.approx(1000e6 / 500e6)
    assert r["price_to_sales"] == pytest.approx(1000e6 / 900e6)
    assert r["price_to_cash_flow"] == pytest.approx(1000e6 / 90e6)
    assert r["return_on_equity"] == pytest.approx(80e6 / 500e6)
    assert r["return_on_assets"] == pytest.approx(80e6 / 800e6)
    assert r["debt_to_equity"] == pytest.approx(200e6 / 500e6)
    assert r["current"] == pytest.approx(300e6 / 150e6)
    # quick = (CA - inv)/CL = (300-60)/150 = 1.6
    assert r["quick"] == pytest.approx(1.6)
    assert r["cash_ratio"] == pytest.approx(50e6 / 150e6)
    assert r["dividend_yield"] == pytest.approx(20e6 / 1000e6)
    assert r["free_cash_flow"] == pytest.approx(90e6 - 30e6)
    assert r["price_to_free_cash_flow"] == pytest.approx(1000e6 / 60e6)
    assert r["market_cap"] == pytest.approx(1000e6)


def test_missing_inputs_render_none_never_fabricate():
    r = compute_ratios({})  # no data
    assert all(v is None for v in r.values())


def test_capex_none_does_not_raise():
    """Regression: OCF present but capex missing must not call abs(None)."""
    r = compute_ratios(_fin(capex=None))
    assert r["free_cash_flow"] is None
    assert r["price_to_free_cash_flow"] is None
    # the rest of the block still computes (no crash)
    assert r["ev"] == pytest.approx(1150e6)
    assert r["dividend_yield"] == pytest.approx(0.02)
    # partial: no inventory -> quick None, others still computed
    r2 = compute_ratios(_fin(inventory=None))
    assert r2["quick"] is None
    assert r2["current"] is not None
    assert r2["price_to_earnings"] is not None
    # no depreciation -> EBITDA None (but EBIT still set)
    r3 = compute_ratios(_fin(depreciation=None))
    assert r3["ev_ebitda"] is None
    assert r3["ev_ebit"] is not None


def test_zero_denominator_safe():
    r = compute_ratios(_fin(total_equity=0))
    for k in ("price_to_book", "debt_to_equity", "return_on_equity"):
        assert r[k] is None  # no ZeroDivision


def test_render_ratios_matches_massive_labels():
    txt = render_ratios(compute_ratios(_fin()))
    for _, label, _k in RENDER_ORDER:
        assert label in txt
    # percentages render as %
    assert "ROE: 16.00%" in txt
    assert "EV: 1,150,000,000" in txt
    assert "P/E: 12.50" in txt


def test_render_ratios_n_a_for_missing():
    txt = render_ratios(compute_ratios(_fin(inventory=None)))
    assert "Quick: n/a" in txt
    assert "P/E: 12.50" in txt
