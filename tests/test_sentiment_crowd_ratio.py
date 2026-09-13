"""S5: crowd ratio, dispersion and display-only bands (round-3 additions).

The crowd bands are display-only by contract: the governor's verdict is
asserted byte-identical with the gate on and off.
"""

import pytest

from tradingagents.strategies.sentiment import (
    compute_social_scores,
    consensus_overlap,
    crowd_ratio,
    sentiment_dispersion,
)


def test_worked_example_45_30_25_is_60_crowded_bullish():
    out = crowd_ratio(45, 30, neutrals=25)
    assert out is not None
    assert out["ratio"] == pytest.approx(60.0)
    assert out["band"] == "crowded-bullish"
    assert out["net_share"] == pytest.approx(0.2)
    assert "display-only" in out["basis"]
    assert "StockTwits/Reddit" in out["basis"]


def test_zero_zero_is_unavailable_never_50():
    assert crowd_ratio(0, 0) is None
    assert crowd_ratio(0, 0, neutrals=50) is None


def test_bands_both_sides_and_neutral():
    assert crowd_ratio(80, 20)["band"] == "crowded-bullish"
    assert crowd_ratio(20, 80)["band"] == "crowded-bearish"
    assert crowd_ratio(50, 50)["band"] == "neutral"


def test_dispersion_two_cluster_exceeds_one_cluster_same_mean():
    one = sentiment_dispersion([0.0, 0.0, 0.0, 0.0])
    two = sentiment_dispersion([1.0, 1.0, -1.0, -1.0])
    assert one is not None and two is not None
    assert one["dispersion"] == pytest.approx(0.0)
    assert two["dispersion"] > one["dispersion"]


def test_weighted_dispersion_hand_computed():
    out = sentiment_dispersion([1.0, -1.0], weights=[9.0, 1.0])
    # mean 0.8; var = (9*0.04 + 1*3.24) / 10 = 0.36 -> 0.6
    assert out["dispersion"] == pytest.approx(0.6)


def test_agreement_reuses_consensus_overlap():
    labels = ["bullish", "bullish", "bearish"]
    out = sentiment_dispersion([1.0, 1.0, -1.0], labels=labels)
    assert out["agreement"] == pytest.approx(consensus_overlap(labels))


def test_empty_scores_unavailable():
    assert sentiment_dispersion([]) is None
    assert sentiment_dispersion([None, None]) is None


def test_band_never_changes_the_governor_verdict():
    from tradingagents.strategies.risk_governor import govern

    base = {"max_position_pct": 0.30}
    off = govern(0.10, {**base, "enable_crowd_ratio_bands": False})
    on = govern(0.10, {**base, "enable_crowd_ratio_bands": True})
    assert on == off


def test_compute_social_scores_carries_additive_crowd_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "tradingagents.dataflows.stocktwits.stocktwits_counts",
        lambda *a, **k: (45, 30, 25, 100),
    )
    res = compute_social_scores("AAPL", cache_dir=str(tmp_path))
    assert res["computed_score"] == pytest.approx(0.2)
    assert res["sample_size"] == 100
    assert (res["bullish"], res["bearish"], res["unlabeled"]) == (45, 30, 25)
    assert res["crowd_ratio"]["ratio"] == pytest.approx(60.0)
    assert res["crowd_ratio"]["band"] == "crowded-bullish"
    assert res["crowd_dispersion"]["agreement"] is not None


def test_crowd_row_gated_on_the_tool(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import config as config_module

    polarity = [1.0] * 45 + [-1.0] * 30 + [0.0] * 25
    monkeypatch.setattr(
        "tradingagents.strategies.sentiment.compute_social_scores",
        lambda *a, **k: {
            "computed_score": 0.2,
            "computed_velocity": None,
            "sample_size": 100,
            "bullish": 45,
            "bearish": 30,
            "unlabeled": 25,
            "crowd_ratio": crowd_ratio(45, 30, neutrals=25),
            "crowd_dispersion": sentiment_dispersion(polarity),
        },
    )
    tool = at.get_sentiment_computed
    assert "crowd ratio" not in tool.invoke({"ticker": "AAPL"})
    config_module.set_config({"enable_crowd_ratio_bands": True})
    on = tool.invoke({"ticker": "AAPL"})
    assert "crowd ratio (crowd counts (StockTwits/Reddit))" in on
    assert "display-only" in on
