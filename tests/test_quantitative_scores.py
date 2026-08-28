"""Real test file — flat, small, written via write tool."""

import pytest

from tradingagents.dataflows.quantitative_scores import (
    acquirers_multiple,
    altman_z_score,
    beneish_m_score,
    earnings_yield,
    enterprise_value,
    piotroski_f_score,
)


@pytest.fixture
def fin():
    return {
        "revenue": {"current": 1000.0, "prior": 800.0},
        "net_receivables": {"current": 150.0, "prior": 120.0},
        "cogs": {"current": 600.0, "prior": 450.0},
        "cost_of_revenue": {"current": 620.0, "prior": 470.0},
        "sga": {"current": 120.0, "prior": 100.0},
        "depreciation": {"current": 60.0, "prior": 50.0},
        "current_assets": {"current": 700.0, "prior": 650.0},
        "ppem": {"current": 400.0, "prior": 380.0},
        "marketable_securities": {"current": 30.0, "prior": 25.0},
        "total_assets": {"current": 2000.0, "prior": 1800.0},
        "current_liabilities": {"current": 500.0, "prior": 470.0},
        "total_debt": {"current": 400.0, "prior": 380.0},
        "working_capital": 200.0,
        "retained_earnings": 800.0,
        "market_cap": 3000.0,
        "cash": 300.0,
        "total_liabilities": 900.0,
        "operating_cashflow": 130.0,
        "net_income": 100.0,
        "interest_expense": 10.0,
        "tax_expense": 20.0,
        "operating_income": 90.0,
    }


def test_beneish(fin):
    m = beneish_m_score(fin)
    assert m is not None
    assert -6.0 < m < -1.0


def test_altman(fin):
    z = altman_z_score(fin)
    assert z is not None
    assert 0.5 < z < 5.0


def test_piotroski(fin):
    f = piotroski_f_score(fin)
    assert f is not None
    assert 0 <= f <= 9


def test_piotroski_negative_roa_does_not_score(fin):
    """Regression: `if _num(roa) or 0 > 0` parsed as `roa or False`, so ANY
    non-None ROA (including negative) won the ROA>0 point. A loss-making firm
    must not get the profitability point."""
    loss = {**fin, "roa": {"current": -0.05, "prior": -0.02}, "net_income": -50.0}
    profit = {**fin, "roa": {"current": 0.08, "prior": -0.02}}
    assert piotroski_f_score(loss) is not None
    assert piotroski_f_score(loss) < piotroski_f_score(profit)


def test_value(fin):
    ev = enterprise_value(fin)
    ey = earnings_yield(fin)
    am = acquirers_multiple(fin)
    assert ev is not None and ev > 0
    assert ey is not None and ey > 0
    assert am is not None and am > 0
