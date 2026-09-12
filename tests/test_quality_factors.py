"""GP/A (Novy-Marx) and NOA (Hirshleifer et al.) plus screener columns."""

import pytest

import scripts.value_screener as vs
from tradingagents.dataflows.quantitative_scores import (
    gross_profitability,
    net_operating_assets,
)


def test_gross_profitability_hand_computed():
    fin = {"revenue": 1000.0, "cogs": 600.0, "total_assets": 2000.0}
    row = gross_profitability(fin)
    assert row is not None
    assert row["value"] == pytest.approx(0.2)
    assert "GP/A" in row["basis"]
    assert row["classification"] == "cogs line: cogs"


def test_gross_profitability_cost_of_revenue_fallback():
    fin = {"revenue": 1000.0, "cost_of_revenue": 400.0, "total_assets": 2000.0}
    row = gross_profitability(fin)
    assert row is not None
    assert row["value"] == pytest.approx(0.3)
    assert row["classification"] == "cogs line: cost_of_revenue"


def test_gross_profitability_missing_cogs_is_none_not_operating_income():
    # operating_income is present but is NOT a COGS substitute.
    fin = {"revenue": 1000.0, "operating_income": 600.0, "total_assets": 2000.0}
    assert gross_profitability(fin) is None


def test_gross_profitability_missing_revenue_or_assets_is_none():
    assert gross_profitability({"cogs": 600.0, "total_assets": 2000.0}) is None
    assert gross_profitability({"revenue": 1000.0, "cogs": 600.0}) is None


def test_net_operating_assets_hand_computed():
    fin = {
        "total_assets": {"current": 2000.0, "prior": 1800.0},
        "total_liabilities": 900.0,
        "cash": 300.0,
        "marketable_securities": 100.0,
        "total_debt": 400.0,
    }
    row = net_operating_assets(fin)
    assert row is not None
    # operating assets = 2000 - 400 = 1600; operating liabilities = 900 - 400 = 500
    # NOA = (1600 - 500) / 1800 (PRIOR total assets)
    assert row["value"] == pytest.approx(1100.0 / 1800.0)
    assert row["value"] != pytest.approx(1100.0 / 2000.0)
    assert "total_assets_prev" in row["basis"]
    assert "cash" in row["classification"] and "total_debt" in row["classification"]


def test_net_operating_assets_missing_prior_balance_sheet_is_none():
    fin = {
        "total_assets": 2000.0,  # flat -> no prior period
        "total_liabilities": 900.0,
        "cash": 300.0,
        "total_debt": 400.0,
    }
    assert net_operating_assets(fin) is None


def test_net_operating_assets_missing_liabilities_is_none():
    fin = {"total_assets": {"current": 2000.0, "prior": 1800.0}, "cash": 300.0}
    assert net_operating_assets(fin) is None


def test_screen_ticker_exposes_quality_columns():
    fin = {
        "revenue": {"current": 1000.0, "prior": 800.0},
        "cogs": 600.0,
        "total_assets": {"current": 2000.0, "prior": 1800.0},
        "total_liabilities": 900.0,
        "cash": 300.0,
        "marketable_securities": 100.0,
        "total_debt": 400.0,
    }
    row = vs.screen_ticker("TEST", fin)
    assert row["gp_a"] == pytest.approx(0.2, abs=1e-4)
    assert row["noa"] == pytest.approx(1100.0 / 1800.0, abs=1e-4)
    assert row["gp_a_classification"] == "cogs line: cogs"
    assert row["noa_classification"] is not None


def test_composite_score_unchanged_by_quality_columns():
    """The informational GP/A + NOA columns must not move the composite rank."""
    base_results = [
        {"ticker": "AAA", "earnings_yield": 0.10},
        {"ticker": "BBB", "earnings_yield": 0.05},
        {"ticker": "CCC", "earnings_yield": 0.08},
    ]
    with_cols = [
        {**r, "gp_a": 0.2 + i * 0.03, "noa": 0.5 - i * 0.1}
        for i, r in enumerate(base_results)
    ]
    # empty closes_map -> only the ey factor enters the composite, so any
    # change can only come from the new columns leaking into the factor row.
    scores_before = vs.composite_scores(base_results, {})
    scores_after = vs.composite_scores(with_cols, {})
    assert scores_after == scores_before
