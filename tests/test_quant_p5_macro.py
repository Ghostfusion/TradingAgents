"""Tests for P5: Taylor-rule implied rate + deviation, macro stance read."""

import pytest

from tradingagents.strategies.cycle_tilt import (
    macro_stance,
    taylor_deviation,
    taylor_rule,
)

pytestmark = pytest.mark.timeout(60)


def test_taylor_rule_implied_simple_case():
    # i = r* + pi + 0.5*(pi - pi*) = 0.02 + 0.03 + 0.5*0.01 = 0.055
    # (classic Taylor 1993 neutral real rate 2%; old default 0.5% removed)
    from tradingagents.strategies.cycle_tilt import taylor_rule

    implied = taylor_rule(policy_rate=0.05, inflation=0.03, output_gap=0.0)
    assert implied == pytest.approx(0.055)


def test_taylor_rule_output_gap_raises_rate():
    implied_full = taylor_rule(policy_rate=0.05, inflation=0.03, output_gap=0.02)
    implied_zero = taylor_rule(policy_rate=0.05, inflation=0.03, output_gap=0.0)
    assert implied_full > implied_zero


def test_taylor_rule_none_safe():
    assert taylor_rule(None, 0.03) is None
    assert taylor_rule(0.05, None) is None


def test_taylor_deviation_signs():
    assert taylor_deviation(0.05, 0.04) == pytest.approx(0.01)  # tight
    assert taylor_deviation(0.03, 0.04) == pytest.approx(-0.01)  # easy
    assert taylor_deviation(None, 0.04) is None


def test_macro_stance_combines_phase_and_taylor():
    st = macro_stance(52, 0.4, 3.0, 0.05, 0.03, 0.0)
    assert st["phase"] == "mid"
    assert st["taylor_implied"] == pytest.approx(0.055)  # r* = 2% (1993)
    assert st["deviation"] == pytest.approx(-0.005)
    assert st["stance"] in ("easy", "neutral")  # -50bp sits on the stance band
    assert "Technology" in st["tilt"]


def test_macro_stance_none_safe():
    st = macro_stance(None, None, None, None, None)
    assert st["phase"] is None and st["stance"] is None
    assert st["tilt"] == []
