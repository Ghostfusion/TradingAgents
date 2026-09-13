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
        "total_liabilities": 400e6,
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
    # Every RATIO is None; ``basis`` is metadata (the periods the block would
    # have come from), not a value, so it is excluded from the no-fabrication
    # sweep - the point of the test is that no number is invented.
    assert all(r[k] is None for k, _label, _kind in RENDER_ORDER)


def test_the_block_states_the_basis_it_was_built_from():
    """NVDA 2026-09-12 (D1): a P/E on annual earnings sat unlabelled in the same
    block as quarterly balance-sheet ratios, and the report quoted it as a
    current multiple. The basis is now part of the output."""
    ttm = compute_ratios(
        _fin(net_income_ttm=40e6, revenue_ttm=1000e6),
        basis={"flows": "TTM", "flows_period": "4 quarters ending 2026-07-31",
               "balance": "2026-07-31"},
    )
    text = render_ratios(ttm)
    assert "- basis: flows TTM (4 quarters ending 2026-07-31); balance sheet 2026-07-31" in text
    # the TTM earnings figure wins: 1000/40 = 25x, not 1000/80 = 12.5x
    assert ttm["price_to_earnings"] == pytest.approx(25.0)
    assert ttm["price_to_sales"] == pytest.approx(1.0)

    reported = render_ratios(compute_ratios(_fin()))
    assert "- basis: flows as reported" in reported
    assert reported.index("- basis:") == 0  # it leads the block, not buried

    # No basis supplied and no TTM keys -> inferred, still labelled.
    assert compute_ratios(_fin())["basis"]["label"] == "flows as reported"


def test_the_price_parameter_is_the_labelled_pe_fallback():
    """The documented ``price`` sanity check was dead code (never referenced in
    the body). It is now the fallback when no earnings figure exists, and the
    rendered line says so - a price/EPS multiple is not the market-cap one."""
    fin = _fin(net_income=None, eps=4.0)
    r = compute_ratios(fin, price=100.0)
    assert r["price_to_earnings"] == pytest.approx(25.0)
    assert r["basis"]["p_e_fallback"] is True
    assert "- P/E: 25.00 (basis: price / reported EPS)" in render_ratios(r)
    # With earnings present the market-cap basis is used and not annotated.
    r2 = compute_ratios(_fin(), price=100.0)
    assert r2["basis"]["p_e_fallback"] is False
    assert "P/E: 12.50" in render_ratios(r2)


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


def test_current_ratio_subset_invariant_guard():
    """Regression (MSFT 2026-09-08): a mis-parsed current_assets (~=total
    assets) produced current 3.74 vs the true 1.23. A current-asset value
    exceeding total assets violates the balance-sheet subset invariant -
    null the ratio instead of emitting a wrong number."""
    r = compute_ratios(_fin(total_assets=200e6, total_liabilities=400e6))  # CA(300) > TA(200)
    assert r["current"] is None
    assert r["quick"] is None
    r2 = compute_ratios(_fin(total_liabilities=100e6))
    assert r2["current"] is None
    r3 = compute_ratios(_fin())
    assert r3["current"] == pytest.approx(300e6 / 150e6)


def test_debt_equity_and_dividend_yield_plausibility_guards():
    """A D/E above 10x or a dividend yield above 25% is a units/scaling
    artifact (MSFT 2026-09-08: D/E 29.118 vs true 0.13; yield 73% vs 0.71%),
    not a real balance-sheet read - render n/a instead of the artifact."""
    r = compute_ratios(_fin(total_debt=8000e6, total_equity=100e6))  # 80x
    assert r["debt_to_equity"] is None
    r2 = compute_ratios(_fin(dividends_paid=2000e6, market_cap=1000e6))  # 200%
    assert r2["dividend_yield"] is None
    r3 = compute_ratios(_fin())
    assert r3["debt_to_equity"] == pytest.approx(0.4)
    assert r3["dividend_yield"] == pytest.approx(0.02)
