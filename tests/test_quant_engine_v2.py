"""Quant-engine v2 tests (DuPont / scenario DCF / earnings-quality verdict)."""

import pytest

from tradingagents.strategies.dupont import dupont_3, dupont_5
from tradingagents.strategies.earnings_quality import earnings_quality_verdict
from tradingagents.strategies.scenario_dcf import scenario_dcf

pytestmark = pytest.mark.timeout(60)


def test_dupont_3_computes_roe_and_driver():
    r = dupont_3(0.2, 0.9, 2.0)
    assert r["roe"] == 0.36
    # log-DuPont attribution: the 20% margin deviates most from the neutral
    # 1.0 benchmark (|ln 0.2| = 1.61 vs |ln 2.0| = 0.69) -> margin-led.
    assert r["driver"] == "net_margin"
    assert r["note"] == "margin-led"


def test_dupont_3_moderate_leverage_is_not_leverage_led():
    # EM 1.5 is normal leverage; a thin 15% margin is the quality story.
    r = dupont_3(0.15, 1.0, 1.5)
    assert r["driver"] == "net_margin"
    assert r["note"] == "margin-led"


def test_dupont_3_heavy_leverage_is_leverage_led():
    r = dupont_3(0.5, 1.0, 4.0)
    assert r["driver"] == "equity_multiplier"
    assert r["note"] == "leverage-led"


def test_dupont_3_mixed_when_no_leg_dominates():
    r = dupont_3(1.5, 1.6, 1.4)
    assert r["driver"] == "mixed"
    assert "mixed" in r["note"]


def test_dupont_3_non_positive_margin_is_the_story():
    for m in (-0.2, 0.0):
        r = dupont_3(m, 1.0, 1.5)
        assert r["driver"] == "net_margin"
        assert "margin" in r["note"]


def test_dupont_3_none_safe():
    r = dupont_3(None, 0.9, 2.0)
    assert r["roe"] is None and r["note"].startswith("incomplete")


def test_dupont_5_extends_with_burdens():
    # ROE = 0.2 * 0.9 * 1.0 * 0.9 * 2.0
    r = dupont_5(0.2, 0.9, 1.0, 0.9, 2.0)
    assert r["roe"] == 0.324
    assert r["driver"] == "net_margin"
    assert r["note"] == "margin-led"


def test_scenario_dcf_range_bear_lt_base_lt_bull():
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, g_base=0.03)
    prices = {k: v["price"] for k, v in r["scenarios"].items()}
    assert prices["bear"] < prices["base"] < prices["bull"]
    assert prices["base"] == 161.67


def test_scenario_dcf_respects_zero_g_base():
    # g_base=0.0 must stay 0 (regression: `or 0.03` silently turned it to 3%).
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, g_base=0.0)
    assert r["scenarios"]["base"]["g"] == 0.0
    assert r["scenarios"]["base"]["price"] == 106.11


def test_scenario_dcf_market_band_and_mos():
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, market_price=160.0)
    assert r["market"]["band"] == "bear-base (discounted)"
    assert r["market"]["mos_base"] == pytest.approx(0.0103)
    r_deep = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, market_price=90.0)
    assert r_deep["market"]["band"] == "below bear (deep value)"
    assert r_deep["scenarios"]["bear"]["mos"] == pytest.approx(0.25)
    r_rich = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, market_price=300.0)
    assert r_rich["market"]["band"] == "above bull (premium)"
    assert r_rich["market"]["mos_base"] < 0


def test_scenario_dcf_none_safe():
    r = scenario_dcf(None, 0.09)
    assert r["scenarios"] == {}


def test_scenario_dcf_margin_shock_scales():
    r = scenario_dcf(100, 0.09, shares=10, cash=50, debt=100, g_base=0.03,
                     margin_shock_bear=-0.2, margin_shock_bull=0.2)
    bear = r["scenarios"]["bear"]["price"]
    bull = r["scenarios"]["bull"]["price"]
    assert bear == 95.0 and bull == 295.0


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


def test_earnings_quality_no_inputs_is_none():
    # No usable inputs -> n/a (never a fabricated LOW confidence).
    r = earnings_quality_verdict(None, None, None)
    assert r["level"] is None and r["evidence"] == []
    assert r["cash_conversion"] is None and r["accrual"] is None


def test_earnings_quality_capex_derived_fcf_sign_robust():
    # FCF = OCF - |capex|: a negative GAAP-signed capex must give the same
    # FCF as the positive magnitude (project convention, matches dcf.py).
    pos = earnings_quality_verdict(10, 8, 100, capex=12)
    neg = earnings_quality_verdict(10, 8, 100, capex=-12)
    assert pos["fcf"] == -4.0 and neg["fcf"] == -4.0
    assert any("negative FCF with positive NI" in e for e in pos["evidence"])
    assert any("negative FCF with positive NI" in e for e in neg["evidence"])


def test_earnings_quality_capex_positive_fcf_no_red_flag():
    r = earnings_quality_verdict(10, 8, 100, capex=5)
    assert r["fcf"] == 3.0
    assert not any("negative FCF" in e for e in r["evidence"])
