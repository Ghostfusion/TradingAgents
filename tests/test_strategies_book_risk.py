"""R2/R4 unit tests: book risk + risk report summary."""

import pytest

from scripts.risk_report import audit_summary
from tradingagents.strategies.book_risk import (
    cvar,
    drawdown_gate,
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
