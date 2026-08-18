"""L4b unit tests: order-flow evaluation metrics (offline)."""

import pytest

from scripts.orderflow_evaluate import compute_metrics


def test_empty_ledger_metrics():
    m = compute_metrics([])
    assert m["total"] == 0
    assert m["win_rate"] is None


def test_win_rate_and_mean_alpha():
    entries = [
        {"analyst": "market", "ticker": "UNH", "delta_r": 0.04},
        {"analyst": "market", "ticker": "AAPL", "delta_r": -0.02},
    ]
    m = compute_metrics(entries)
    assert m["total"] == 2
    assert m["wins"] == 1
    assert m["win_rate"] == 0.5
    assert m["mean_alpha"] == pytest.approx(0.01)
    b = m["by_analyst"]["market"]
    assert b["win_rate"] == 0.5


def test_by_analyst_split():
    entries = [
        {"analyst": "a", "delta_r": 0.1},
        {"analyst": "a", "delta_r": -0.05},
        {"analyst": "b", "delta_r": 0.07},
    ]
    m = compute_metrics(entries)
    assert m["by_analyst"]["a"]["total"] == 2
    assert m["by_analyst"]["b"]["win_rate"] == 1.0
