"""Tail decomposition (incremental/component VaR) tests (offline)."""

import numpy as np
import pytest

from tradingagents.strategies.book_risk import component_var, incremental_var

pytestmark = pytest.mark.timeout(120)


def _book(n=400, seed=1):
    rng = np.random.default_rng(seed)
    # Three names: A very volatile (drives the tail), B moderate, C calm.
    a = list(rng.normal(0.0, 0.04, n))
    b = list(rng.normal(0.0, 0.015, n))
    c = list(rng.normal(0.0, 0.005, n))
    return {"A": a, "B": b, "C": c}


def test_component_var_sums_to_total():
    rbn = _book()
    w = {"A": 0.5, "B": 0.3, "C": 0.2}
    out = component_var(rbn, w)
    assert out is not None
    assert out["coverage"] == pytest.approx(1.0, abs=0.05)
    assert out["total_var"] < 0  # loss is negative
    # The volatile name dominates the tail.
    assert abs(out["components"]["A"]) > abs(out["components"]["B"]) > abs(out["components"]["C"])


def test_component_var_insufficient():
    # Degenerate covariance (no variance in any name's series) -> None.
    flat = {"A": [0.0] * 60, "B": [0.0] * 60, "C": [0.0] * 60}
    assert component_var(flat, {"A": 0.4, "B": 0.3, "C": 0.3}) is None
    assert component_var(_book(), {}) is None  # no weights
    # Unequal-length series that can't align a common window -> None.
    assert component_var({"A": [0.01] * 10, "B": [0.01] * 10, "C": [0.01] * 3}, {"A": 0.4, "B": 0.3, "C": 0.3}) is None


def test_incremental_var_direction():
    rbn = _book()
    w = {"A": 0.4, "B": 0.3, "C": 0.3}
    out = incremental_var(rbn, w)
    assert out is not None
    # A is the most volatile -> adding weight to A should widen the VaR (more negative delta).
    assert out["incremental"]["A"] < 0
    assert out["incremental"]["A"] < out["incremental"]["C"]


def test_incremental_var_too_small_book():
    assert incremental_var({"A": [0.01] * 50, "B": [0.01] * 50}, {"A": 0.5, "B": 0.5}) is None


def test_tail_decomposition_tool_render(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import _RUN_OHLCV_CACHE, get_tail_decomposition

    n = 120
    rng = np.random.default_rng(2)
    for t in ("A", "B", "C"):
        closes = list(100.0 * np.cumprod(1 + rng.normal(0.0, [0.005, 0.001, 0.0005][["A", "B", "C"].index(t)], n)))
        dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
        _RUN_OHLCV_CACHE[(t, 320)] = {
            "dates": dates,
            "closes": closes,
            "opens": closes,
            "highs": [c * 1.01 for c in closes],
            "lows": [c * 0.99 for c in closes],
            "volumes": [1_000_000.0] * n,
        }
    try:
        out = get_tail_decomposition.invoke({"names": "A,B,C", "weights": "A=0.4,B=0.3,C=0.3"})
        assert "Tail Decomposition" in out
        assert "component var" in out.lower()
    finally:
        _RUN_OHLCV_CACHE.clear()
