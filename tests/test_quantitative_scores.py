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


def test_beneish_depi_uses_ppe_plus_depreciation():
    """Regression (audit): DEPI denominators are (PPE + Dep), NOT (PPE - Dep).
    dep overstating PPE by +20 with all else flat must RAISE depi (good-for-
    manipulator index), not lower it."""
    fin = {
        "revenue": {"current": 1000.0, "prior": 1000.0},
        "net_receivables": {"current": 150.0, "prior": 150.0},
        "cogs": {"current": 600.0, "prior": 600.0},
        "sga": {"current": 100.0, "prior": 100.0},
        "depreciation": {"current": 60.0, "prior": 60.0},
        "current_assets": {"current": 500.0, "prior": 500.0},
        "ppem": {"current": 400.0, "prior": 400.0},
        "marketable_securities": {"current": 20.0, "prior": 20.0},
        "total_assets": {"current": 1500.0, "prior": 1500.0},
        "current_liabilities": {"current": 300.0, "prior": 300.0},
        "total_debt": {"current": 200.0, "prior": 200.0},
        "operating_cashflow": 150.0,
        "net_income": 100.0,
    }
    m = beneish_m_score(fin)
    fin_big = dict(fin)
    fin_big["ppem"] = {"current": 420.0, "prior": 400.0}
    m_big = beneish_m_score(fin_big)
    # canonical DEPI = [60/(400+60)] / [60/(420+60)] = 1.043478
    # AQI also moves (PPE is in the AQI non-current-asset slice):
    #   AQI = [1-(TA-CA-PPE-Sec)/TA]_t / [1-(...)_t-1]
    #       = [1-560/1500]/[1-580/1500] = 1.021739
    # old (broken) DEPI = [60/(400-60)]/[60/(420-60)] = 1.05882 changes the
    # depi delta, so the pinned total discriminates the canonical (+) form.
    depi = 1.0434782608695652
    aqi = 1.0217391304347827
    assert m_big is not None
    assert m_big - m == pytest.approx(
        0.115 * (depi - 1.0) + 0.404 * (aqi - 1.0), abs=1e-6
    )


def test_beneish_lvgi_adds_longterm_debt():
    """Regression (audit): LVGI numerator is (CL + LTD), NOT (CL - LTD). A
    capital-heavy firm (LTD > CL) must yield a POSITIVE LVGI ratio, and with
    the canonical -0.327 coefficient, M must FALL as leverage grows. The old
    (CL - LTD) form computed a negative leverage ratio whose sign flip pushed
    M the wrong way."""
    fin = {
        "revenue": {"current": 1000.0, "prior": 1000.0},
        "net_receivables": {"current": 150.0, "prior": 150.0},
        "cogs": {"current": 600.0, "prior": 600.0},
        "sga": {"current": 100.0, "prior": 100.0},
        "depreciation": {"current": 60.0, "prior": 60.0},
        "current_assets": {"current": 500.0, "prior": 500.0},
        "ppem": {"current": 400.0, "prior": 400.0},
        "marketable_securities": {"current": 20.0, "prior": 20.0},
        "total_assets": {"current": 1500.0, "prior": 1500.0},
        "current_liabilities": {"current": 100.0, "prior": 100.0},
        "total_debt": {"current": 500.0, "prior": 500.0},
        "operating_cashflow": 150.0,
        "net_income": 100.0,
    }
    m = beneish_m_score(fin)
    fin2 = dict(fin)
    fin2["total_debt"] = {"current": 700.0, "prior": 500.0}
    m2 = beneish_m_score(fin2)
    assert m is not None and m2 is not None
    # canonical LVGI_t = (100+700)/1500 = 0.5333 vs flat 1.0 in the base year
    lvgi = (100 + 700) / 1500.0 / ((100 + 500) / 1500.0)
    assert lvgi == pytest.approx(1.3333, abs=1e-3)
    # M delta = -0.327*(lvgi - 1); old (CL - LTD) form gave lvgi = 1.5 -> a
    # materially different delta, so this pins the canonical (CL + LTD) form.
    assert m2 - m == pytest.approx(-0.327 * (lvgi - 1.0), abs=1e-6)


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
