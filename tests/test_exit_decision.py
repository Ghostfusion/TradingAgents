"""Phase 1 of the entry/exit price engine: the §101 exit predicate.

``exit_decision`` evaluates the six independent exits for a long and names the
first that fires; ``time_exit`` is the §58 clock. Both follow the repo's
absent-with-a-reason discipline: a condition that could not be evaluated is
absent and shrinks coverage, never read as "no exit".
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.exits import EXIT_PRECEDENCE, exit_decision, time_exit

pytestmark = pytest.mark.timeout(600)


# --- time_exit (§58) --------------------------------------------------------


def test_time_exit_fires_past_the_horizon():
    out = time_exit(40, 30)
    assert out["exit"] is True
    assert out["days_held"] == 40
    assert out["reason"]


def test_time_exit_does_not_fire_inside_the_horizon():
    out = time_exit(10, 30)
    assert out["exit"] is False
    assert out["days_held"] == 10


def test_time_exit_never_fires_inside_a_longer_minimum_hold():
    """A horizon shorter than the minimum holding period must not exit early."""
    out = time_exit(40, 30, min_holding_days=45)
    assert out["exit"] is False
    assert out["min_elapsed"] is False
    assert "minimum" in out["reason"]


def test_time_exit_is_none_not_false_when_unmeasurable():
    out = time_exit(None, 30)
    assert out["exit"] is None
    assert out["reason"]
    assert time_exit(20, None)["exit"] is None


# --- exit_decision (§101) ---------------------------------------------------


def test_stop_fires_and_quotes_the_stop_level():
    out = exit_decision(close=94.0, stop=95.0)
    assert out["exit"] is True
    assert out["reason"] == "stop"
    assert out["exit_price"] == pytest.approx(95.0)
    assert out["conditions"]["stop"] is True


def test_holding_is_reported_when_nothing_fires():
    out = exit_decision(close=100.0, stop=95.0, target=110.0)
    assert out["exit"] is False
    assert out["reason"] == "no exit condition fired"
    assert out["conditions"]["stop"] is False
    assert out["conditions"]["target"] is False


def test_target_fires_and_quotes_the_target_level():
    out = exit_decision(close=112.0, stop=95.0, target=110.0)
    assert out["reason"] == "target"
    assert out["exit_price"] == pytest.approx(110.0)


def test_terminal_risk_takes_precedence_over_a_price_stop():
    """The repo's own hierarchy: terminal risk > stop (trailing_stop_exit)."""
    out = exit_decision(close=94.0, stop=95.0, risk_gate="REJECT")
    assert out["reason"] == "risk_gate"
    assert out["conditions"]["stop"] is True
    # A non-price exit is taken at market, not at the stop level.
    assert out["exit_price"] == pytest.approx(94.0)


def test_risk_gate_acceptance_is_not_an_exit():
    out = exit_decision(close=100.0, risk_gate="PASS")
    assert out["exit"] is False
    assert out["conditions"]["risk_gate"] is False


def test_thesis_break_and_time_exit_and_negative_edge_each_fire():
    assert exit_decision(close=None, thesis_break=True)["reason"] == "thesis_break"
    assert exit_decision(close=None, time_exit_fired=True)["reason"] == "time_exit"
    assert exit_decision(close=None, expected_value=-0.1)["reason"] == "expected_value"
    assert exit_decision(close=None, expected_value=0.1)["exit"] is False


def test_unmeasured_condition_is_absent_and_shrinks_coverage():
    """Coverage counts only what was decidable - an absent condition is not a
    silent 'no exit'."""
    thin = exit_decision(close=100.0, stop=95.0)
    full = exit_decision(
        close=100.0, stop=95.0, target=110.0, trailing_stop=90.0,
        thesis_break=False, risk_gate="PASS", time_exit_fired=False,
        expected_value=0.05,
    )
    assert thin["coverage"] == 1
    assert full["coverage"] == len(EXIT_PRECEDENCE)
    assert set(thin["conditions"]) == {"stop"}
    assert set(full["conditions"]) == set(EXIT_PRECEDENCE)


def test_nothing_decidable_is_none_not_false():
    out = exit_decision(close=None)
    assert out["exit"] is None
    assert out["coverage"] == 0
    assert out["conditions"] == {}
    assert out["exit_price"] is None
    assert out["reason"]


def test_precedence_order_is_declared_and_respected():
    assert EXIT_PRECEDENCE[0] == "risk_gate"
    assert "stop" in EXIT_PRECEDENCE and "target" in EXIT_PRECEDENCE
    out = exit_decision(
        close=112.0, stop=95.0, target=110.0, thesis_break=True, risk_gate="REJECT"
    )
    assert out["reason"] == "risk_gate"
    assert all(out["conditions"][k] for k in ("target", "thesis_break"))
