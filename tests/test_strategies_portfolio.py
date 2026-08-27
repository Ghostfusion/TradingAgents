"""Item 1 unit tests: correlation-aware allocation (portfolio.py)."""

from tradingagents.strategies.portfolio import (
    allocation_block,
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


def test_allocation_block_gate_off_ignores_returns():
    # Gate off: returns_by_name is accepted but never applied (no note).
    rets = _returns_common_factor()
    text = allocation_block(
        {"A": 0.4, "B": 0.4, "C": 0.2},
        cfg={"max_name_weight": 0.5, "enable_correlation_penalty": False},
        returns_by_name=rets,
    )
    assert "correlation-penalized" not in text
    assert "- A: 40.0%" in text


def test_allocation_block_gate_on_penalizes_high_corr():
    # Gate on: A/B (highly correlated with the book) are down-weighted and the
    # block says so; C (the diversifier) gains relative weight.
    rets = _returns_common_factor()
    text = allocation_block(
        {"A": 0.4, "B": 0.4, "C": 0.2},
        cfg={
            "max_name_weight": 0.5,
            "enable_correlation_penalty": True,
            "correlation_threshold": 0.5,
            "correlation_penalty_frac": 0.5,
        },
        returns_by_name=rets,
    )
    assert "correlation-penalized" in text
    # A and B (highly correlated with the book) were cut 40% -> 20% each, C
    # (the diversifier) kept 20%, then the book renormalized to 33.3% each -
    # the correlated names no longer dominate the book.
    assert "- A: 33.3%" in text
    assert "- B: 33.3%" in text
    assert "- C: 33.3%" in text


def test_allocation_block_gate_on_missing_series_unchanged():
    # Only A has a series; B has none -> B is never penalized (no fabrication).
    text = allocation_block(
        {"A": 0.5, "B": 0.5},
        cfg={"max_name_weight": 0.5, "enable_correlation_penalty": True},
        returns_by_name={"A": [1, 2, 3, 4, 5]},
    )
    assert "- A: 50.0%" in text
    assert "- B: 50.0%" in text
