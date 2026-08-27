"""Item 1 unit tests: correlation-aware allocation (portfolio.py)."""

import pytest

from tradingagents.strategies.portfolio import (
    correlation_penalty,
    mean_correlation,
    value_ratio_weights,
)


def _returns_common_factor():
    # A and B track a common factor tightly; C is independent noise (a true
    # diversifier), so A/B are highly correlated with the book but C is not.
    import random

    rng = random.Random(7)
    base = [rng.random() for _ in range(40)]
    return {
        "A": [b + 0.001 * i for i, b in enumerate(base)],
        "B": [b * 1.01 for b in base],
        "C": [rng.random() for _ in range(40)],
    }


def test_mean_correlation_self_peers():
    rets = _returns_common_factor()
    # A and B are near-perfectly correlated; C is independent
    ab = mean_correlation(rets, "A")
    assert ab is not None
    assert ab > 0.5
    c = mean_correlation(rets, "C")
    assert c is not None
    assert c < 0.3


def test_mean_correlation_requires_peer():
    assert mean_correlation({"A": [1, 2, 3]}, "A") is None


def test_correlation_penalty_downweights_high_corr():
    # A and B highly correlated with the book -> their weights are cut;
    # C (the diversifier) keeps its weight.
    rets = _returns_common_factor()
    w = {"A": 0.4, "B": 0.4, "C": 0.2}
    adj = correlation_penalty(w, rets, threshold=0.5, penalty=0.5)
    assert adj["A"] < 0.4
    assert adj["B"] < 0.4
    assert adj["C"] > 0.2


def test_correlation_penalty_renormalizes():
    rets = _returns_common_factor()
    w = {"A": 0.4, "B": 0.4, "C": 0.2}
    adj = correlation_penalty(w, rets, threshold=0.5, penalty=0.5)
    assert abs(sum(adj.values()) - 1.0) < 1e-6


def test_correlation_penalty_missing_series_unchanged():
    # name with no series is left unchanged (never fabricated)
    rets = {"A": [1, 2, 3, 4, 5]}
    w = {"A": 0.5, "B": 0.5}
    adj = correlation_penalty(w, rets, threshold=0.5, penalty=0.5)
    assert adj["A"] == 0.5
    assert adj["B"] == 0.5


def test_value_ratio_weights_baseline():
    w = value_ratio_weights({"X": 100, "Y": 100})
    assert abs(w["X"] - 0.5) < 1e-9 and abs(w["Y"] - 0.5) < 1e-9
