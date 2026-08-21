"""R2/R4 unit tests: book risk + risk report summary."""

import pytest

from scripts.risk_report import audit_summary
from tradingagents.strategies.book_risk import (
    cvar,
    drawdown_gate,
    portfolio_cvar,
    portfolio_returns,
    simple_var,
    stress_loss,
)


def test_var_and_cvar_negative_tails():
    rets = [0.01, -0.02, -0.05, -0.03, 0.02, 0.0, -0.01]
    v = simple_var(rets, alpha=0.2)
    c = cvar(rets, alpha=0.2)
    assert v is not None and v < 0
    assert c is not None and c <= v  # CVaR is worse than VaR


def test_var_empty_none():
    assert simple_var([]) is None
    assert cvar([]) is None


def test_portfolio_returns_weighted():
    weights = {"a": 0.6, "b": 0.4}
    series = {"a": [0.01, -0.01], "b": [0.02, 0.01]}
    out = portfolio_returns(weights, series)
    assert out[0] == pytest.approx(0.6 * 0.01 + 0.4 * 0.02)
    assert out[1] == pytest.approx(0.6 * -0.01 + 0.4 * 0.01)


def test_portfolio_cvar_mixes_weighted_series():
    # a: flat-ish, b: a hard loss day => the basket tail is pulled negative by b.
    series = {
        "a": [0.001] * 60,
        "b": [0.001] * 59 + [-0.10],
    }
    # b at 10% weight makes the worst 5% tail negative...
    cv_with_b = portfolio_cvar(series, weights={"a": 0.9, "b": 0.1}, alpha=0.05)
    assert cv_with_b is not None and cv_with_b < 0
    # ...while a pure-a basket keeps the tail positive.
    cv_single_a = portfolio_cvar(series, weights={"a": 1.0, "b": 0.0}, alpha=0.05)
    assert cv_single_a is not None and cv_single_a > 0


def test_portfolio_cvar_requires_two_names():
    assert portfolio_cvar({}) is None
    assert portfolio_cvar({"a": [0.01] * 30}) is None


def test_portfolio_cvar_normalizes_missing_weights():
    series = {"a": [0.01] * 40, "b": [-0.02] * 40}
    # no weights -> equal weight, so the result matches 0.5/0.5 mixing
    cv_no_weights = portfolio_cvar(series)
    cv_half = portfolio_cvar(series, weights={"a": 0.5, "b": 0.5})
    assert cv_no_weights is not None and cv_half is not None
    assert abs(cv_no_weights - cv_half) < 1e-12


def test_stress_loss():
    assert stress_loss({"A": 0.5, "B": 0.5}, shock=-0.10) == pytest.approx(0.10)


def test_drawdown_gate():
    assert drawdown_gate(0.12, limit_pct=0.10) is True
    assert drawdown_gate(0.05, 0.10) is False
    assert drawdown_gate(None, 0.10) is False


def test_audit_summary():
    entries = [
        {"verdict": "PASS", "reasons": []},
        {"verdict": "REJECT", "reasons": ["size over cap", "cvar over budget"]},
    ]
    sm = audit_summary(entries)
    assert sm["total"] == 2
    assert sm["counts"]["REJECT"] == 1
    assert "size over cap" in sm["limit_hits"]


def test_portfolio_cvar_sub_unity_weights_dilute_by_cash():
    """Weights summing < 1.0 mean the remainder is zero-return cash.

    The mixed series must be scaled by the invested fraction (0.68 in this
    case), so the CVaR is diluted - NOT renormalized back to the full book.
    """
    a = [0.0005] * 60
    b = [0.0005] * 59 + [-0.05]
    w_full = {"a": 0.5, "b": 0.5}
    w_cash = {"a": 0.34, "b": 0.34}  # 0.68 invested, 0.32 cash

    cv_full = portfolio_cvar({"a": a, "b": b}, weights=w_full)
    cv_cash = portfolio_cvar({"a": a, "b": b}, weights=w_cash)
    assert cv_cash is not None and cv_full is not None
    assert cv_full < 0 and cv_cash < 0
    # Cash dilution scales the tail by the invested share.
    assert cv_cash / cv_full == pytest.approx(0.68, rel=1e-9)


def test_portfolio_cvar_over_allocated_weights_clamp_to_unity():
    """Weights summing > 1.0 must be clamped to a valid portfolio (no crash)."""
    a = [0.001] * 40
    b = [-0.02] * 20 + [0.001] * 20
    cv = portfolio_cvar({"a": a, "b": b}, weights={"a": 2.0, "b": 2.0})
    assert cv is not None and cv < 0
