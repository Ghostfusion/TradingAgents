"""S10 unit tests: Mohanram G-Score, Montier C-Score, peer-median leg.

Mutation guards (plan §4): a sector mean instead of the median; a missing
signal counted 0; a 4-name peer group accepted.
"""

import pytest

from tradingagents.dataflows.quantitative_scores import growth_score, overpriced_score
from tradingagents.strategies.cross_section import group_median

G_FIN = {
    "net_income": 100.0,
    "operating_cashflow": 150.0,
    "total_assets": {"current": 1000.0, "prior": 900.0},
    "revenue": 1000.0,
    "research_development": 60.0,
    "capex": 70.0,
    "advertising": 30.0,
    "roa_series": [0.10, 0.10, 0.10, 0.10, 0.10],
    "revenue_series": [1000.0, 1050.0, 1102.5, 1157.625, 1215.50625],
}

G_MED = {
    "roa": {"median": 0.05, "n": 10},
    "cfo": {"median": 0.10, "n": 10},
    "var_roa": {"median": 0.02, "n": 10},
    "var_sales_growth": {"median": 0.05, "n": 10},
    "rd_intensity": {"median": 0.03, "n": 10},
    "capex_intensity": {"median": 0.05, "n": 10},
    "ad_intensity": {"median": 0.02, "n": 10},
}

BAD_FIN = {
    "net_income": 200.0,
    "operating_cashflow": 150.0,
    "total_assets": {"current": 1000.0, "prior": 900.0},
    "revenue": 1000.0,
    "research_development": 10.0,
    "capex": 10.0,
    "advertising": 5.0,
    "roa_series": [0.1, 0.5, 0.1, 0.5, 0.1],
    "revenue_series": [1000.0, 1500.0, 900.0, 1600.0, 800.0],
}

BAD_MED = {
    "roa": {"median": 0.30, "n": 10},
    "cfo": {"median": 0.50, "n": 10},
    "var_roa": {"median": 0.01, "n": 10},
    "var_sales_growth": {"median": 0.01, "n": 10},
    "rd_intensity": {"median": 0.03, "n": 10},
    "capex_intensity": {"median": 0.05, "n": 10},
    "ad_intensity": {"median": 0.02, "n": 10},
}


def test_good_band_high_score():
    out = growth_score(G_FIN, G_MED)
    assert out["score"] == 8
    assert out["band"]["label"] == "good"


def test_poor_band_low_score():
    out = growth_score(BAD_FIN, BAD_MED)
    assert out["score"] == 0
    assert out["band"]["label"] == "poor"


def test_band_prints_table_9():
    assert "6-8" in growth_score(G_FIN, G_MED)["band"]["bands"]


def test_group_median_is_median_not_mean():
    values = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 100.0}
    groups = dict.fromkeys(values, "g")
    got = group_median(values, groups, min_n=5)
    assert got["g"]["median"] == pytest.approx(1.0)  # mean would be 20.8
    assert got["g"]["n"] == 5


def test_peer_group_below_floor_is_unavailable():
    values = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    groups = dict.fromkeys(values, "g")
    assert group_median(values, groups, min_n=5)["g"] is None


def test_four_name_peer_group_does_not_score_a_leg():
    med = dict(G_MED)
    med["roa"] = {"median": 0.05, "n": 4}
    out = growth_score(G_FIN, med)
    assert out["signals"]["g1"] is None
    assert any("below floor" in d for d in out["deviations"])


def test_three_year_history_excludes_variance_legs():
    fin = dict(G_FIN)
    fin["roa_series"] = [0.10, 0.10, 0.10]
    fin["revenue_series"] = [1000.0, 1050.0, 1102.5]
    out = growth_score(fin, G_MED)
    assert out["signals"]["g4"] is None
    assert out["signals"]["g5"] is None
    # g1,g2,g3,g6,g7,g8 remain -> a 6-signal G, band withheld below 8 signals.
    assert sum(1 for v in out["signals"].values() if v is not None) == 6
    assert out["score"] == 6
    assert out["band"] is None
    assert any("g4" in d for d in out["deviations"])
    assert any("g5" in d for d in out["deviations"])


def test_missing_median_never_scores_zero():
    out = growth_score(G_FIN, None)
    # Only G3 (CFO>NI) is computable without peer medians.
    assert out["score"] == 1
    assert out["signals"]["g3"] is True
    assert all(out["signals"][k] is None for k in ("g1", "g2", "g6", "g7", "g8"))
    assert out["band"] is None
    assert any("industry median unavailable" in d for d in out["deviations"])


def test_g8_absence_is_visible():
    fin = {k: v for k, v in G_FIN.items() if k != "advertising"}
    out = growth_score(fin, G_MED)
    assert out["signals"]["g8"] is None
    assert any("advertising" in d for d in out["deviations"])


C_POOR = {
    "net_income": {"current": 100.0, "prior": 80.0},
    "operating_cashflow": {"current": 60.0, "prior": 70.0},
    "total_assets": {"current": 1200.0, "prior": 1000.0},
    "revenue": {"current": 1000.0, "prior": 1000.0},
    "net_receivables": {"current": 200.0, "prior": 150.0},
    "inventory": {"current": 150.0, "prior": 100.0},
    "cogs": {"current": 750.0, "prior": 750.0},
    "current_assets": {"current": 800.0, "prior": 700.0},
    "cash": {"current": 100.0, "prior": 150.0},
    "depreciation": {"current": 100.0, "prior": 120.0},
    "ppem": {"current": 1000.0, "prior": 1000.0},
}

C_GOOD = {
    "net_income": {"current": 100.0, "prior": 80.0},
    "operating_cashflow": {"current": 120.0, "prior": 70.0},
    "total_assets": {"current": 1050.0, "prior": 1000.0},
    "revenue": {"current": 1000.0, "prior": 1000.0},
    "net_receivables": {"current": 100.0, "prior": 150.0},
    "inventory": {"current": 50.0, "prior": 100.0},
    "cogs": {"current": 750.0, "prior": 750.0},
    "current_assets": {"current": 500.0, "prior": 700.0},
    "cash": {"current": 100.0, "prior": 150.0},
    "depreciation": {"current": 150.0, "prior": 120.0},
    "ppem": {"current": 1000.0, "prior": 1000.0},
}


def test_c_score_poor_risk_screen():
    out = overpriced_score(C_POOR)
    assert all(out["signals"][k] is True for k in out["signals"])
    assert out["score"] == 6
    assert out["band"]["label"] == "poor"
    assert out["risk_screen"] is True
    assert "not a short signal" in out["basis"]


def test_c_score_good_edge():
    out = overpriced_score(C_GOOD)
    assert out["score"] == 0
    assert out["band"]["label"] == "good"


def test_c5_proxy_is_recorded():
    out = overpriced_score(C_POOR)
    assert any("ppem" in d for d in out["deviations"])
