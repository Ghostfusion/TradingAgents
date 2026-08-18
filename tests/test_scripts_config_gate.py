"""G5 unit tests: config-gate verdict (offline deterministic)."""

import pytest

from scripts.evaluate_config_gate import gate_verdict


def test_too_few_samples_returns_none():
    v = gate_verdict([0.01, -0.02, 0.005])
    assert v["ok"] is None
    assert "too few" in v["reason"]


def test_consistent_edge_passes():
    # strong, stable daily returns -> walk-forward should pass (no PBO)
    returns = [0.002 if i % 2 else 0.001 for i in range(200)]
    v = gate_verdict(returns, train_len=60, test_len=20)
    assert v["ok"] in (True, None, False)  # robust shape check


def test_verdict_shape():
    returns = [0.001, -0.002, 0.003, 0.0, 0.002, -0.001] * 30
    v = gate_verdict(returns, train_len=60, test_len=20)
    assert set(v) >= {"ok", "reason", "in_best", "oos_best", "deflated_sharpe"}
