"""Quant-engine v2 tests (DuPont / scenario DCF / earnings-quality verdict)."""

import pytest

from tradingagents.strategies.dupont import dupont_3, dupont_5
from tradingagents.strategies.earnings_quality import earnings_quality_verdict
from tradingagents.strategies.scenario_dcf import scenario_dcf

pytestmark = pytest.mark.timeout(60)


def test_dupont_3_computes_roe_and_driver():
    r = dupont_3(0.2, 0.9, 2.0)
    assert r["roe"] == 0.36
    assert r["driver"] == "equity_multiplier"  # 2.0/0.36 > margin 0.2/0.36


def test_dupont_3_none_safe():
    r = dupont_3(None, 0.9, 2.0)
    assert r["roe"] is None and r["note"].startswith("incomplete")


def test_dupont_5_extends_with_burdens():
    # ROE = 0.2 * 0.9 * 1.0 * 0.9 * 2.0
    r = dupont_5(0.2, 0.9, 1.0, 0.9, 2.0)
    assert r["roe"] == 0.324
    assert r["driver"] in ("equity_multiplier", "net_margin")


def test_scenario_dcf_range_bear_lt_base_lt_bull():
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, g_base=0.03)
    assert r["scenarios"]["bear"]["price"] < r["scenarios"]["base"]["price"] < r["scenarios"]["bull"]["price"]
    assert r["scenarios"]["base"]["price"] == 161.67


def test_scenario_dcf_none_safe():
    r = scenario_dcf(None, 0.09)
    assert r["scenarios"] == {}


def test_scenario_dcf_margin_shock_scales():
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, g_base=0.03,
                     margin_shock_bear=-0.2, margin_shock_bull=0.2)
    bear = r["scenarios"]["bear"]["price"]
    bull = r["scenarios"]["bull"]["price"]
    assert bear < 100 and bull > 161.67


def test_earnings_quality_healthy_low():
    r = earnings_quality_verdict(10, 12, 100, fcf=5, eps_growth=0.1, fcf_growth=0.05)
    assert r["level"] == "LOW"
    assert r["cash_conversion"] == 1.2


def test_earnings_quality_red_flags_high():
    r = earnings_quality_verdict(10, 9, 100, fcf=4, eps_growth=0.2, fcf_growth=-0.1)
    assert r["level"] == "HIGH"
    assert any("RISING EPS while FCF falls" in e or "cash conversion" in e for e in r["evidence"])


def test_earnings_quality_negative_fcf_positive_ni():
    r = earnings_quality_verdict(10, 8, 100, fcf=-2)
    assert any("negative FCF with positive NI" in e for e in r["evidence"])


def test_earnings_quality_no_inputs_low():
    # No usable inputs -> no evidence -> LOW (a verdict is always returned,
    # never fabricated, but with zero inputs it is uninformative).
    r = earnings_quality_verdict(None, None, None)
    assert r["level"] == "LOW" and r["evidence"] == []
    assert r["cash_conversion"] is None and r["accrual"] is None
