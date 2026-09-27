"""The absent `NewsScore` producers (NEWS-5/NEWS-7/NEWS-9).

NEWS-5: the regulatory/legal tag->category classifier over the tag surfaces the
vendors already return (Benzinga channels, EODHD tags, Alpha Vantage topics) - a
legal tag maps to the ``regulatory_legal`` category, an unrelated tag set
refuses with a reason. NEWS-7: the sector-relative abnormal move over the news
window. NEWS-9: the TF-IDF headline similarity, the duplicate-suppression weight
``W_dup`` and the weighted novelty that combines them.

Offline and deterministic: every input is synthetic, no vendor call.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.news_score import (
    IMPORTANCE_SEVERITY,
    NOVELTY_MAX_ARTICLES,
    TAG_CATEGORIES,
    duplicate_weight,
    headline_similarity,
    industry_shock,
    tag_category_read,
    weighted_novelty,
)

pytestmark = pytest.mark.timeout(600)


# --- NEWS-5: regulatory / legal tag classifier ----------------------------- #


def test_legal_tag_maps_to_regulatory_category():
    res = tag_category_read(["lawsuit", "SEC investigation"])
    assert res["category"] == "regulatory_legal"
    assert "regulatory_legal" in res["categories"]
    assert res["read"] is not None and 0.0 < res["read"] <= 1.0
    assert res["unrecognised"] == []


def test_benzinga_channels_and_importance_scale_the_read():
    important = tag_category_read(["legal"], importance_rank=1)
    minor = tag_category_read(["legal"], importance_rank=5)
    assert important["read"] > minor["read"] > 0.0
    assert minor["read"] == pytest.approx(IMPORTANCE_SEVERITY[5])


def test_unrelated_tags_refuse_never_a_neutral_score():
    res = tag_category_read(["sunny", "coffee", "sports"])
    assert res["read"] is None
    assert res["category"] is None
    assert res["reason"] and "unrecognised" in res["reason"]


def test_read_is_the_mapped_share_of_the_tag_set():
    res = tag_category_read(["litigation", "sunny", "coffee"])
    assert res["category"] == "regulatory_legal"
    assert res["read"] == pytest.approx(1.0 / 3.0)
    assert res["unrecognised"] == ["coffee", "sunny"]


def test_alpha_vantage_topic_underscores_normalise_to_categories():
    res = tag_category_read(["mergers_and_acquisitions"])
    assert res["category"] == "corporate_events"
    assert res["read"] == pytest.approx(1.0)


def test_vocabulary_values_are_engine_category_names():
    from tradingagents.strategies.news_score import NEWS_CATEGORY_ORDER

    assert set(TAG_CATEGORIES.values()) <= set(NEWS_CATEGORY_ORDER)


# --- NEWS-7: industry shock (sector-relative abnormal move) ---------------- #


def test_industry_shock_is_zero_when_stock_tracks_sector():
    stock = [0.01, -0.02, 0.03, 0.005]
    res = industry_shock(stock, list(stock))
    assert res["abnormal"] == pytest.approx(0.0, abs=1e-9)
    assert res["sigma"] == pytest.approx(0.0, abs=1e-12)
    # no dispersion to standardise by -> z is None, never fabricated
    assert res["z"] is None


def test_industry_shock_is_positive_when_stock_outperforms():
    # the excess must VARY for the standardisation to exist at all: a constant
    # excess is zero-dispersion, and z is undefined there (a separate test below
    # pins that refusal rather than papering over it with a fabricated 0).
    stock = [0.03, 0.02, 0.05, 0.01]
    sector = [0.01, 0.00, 0.02, -0.01]
    res = industry_shock(stock, sector)
    assert res["abnormal"] > 0.0
    assert res["mean_excess"] > 0.0
    assert res["z"] is not None


def test_industry_shock_refuses_without_pairs():
    res = industry_shock([], [])
    assert res["abnormal"] is None
    assert res["reason"]


def test_industry_shock_window_keeps_the_tail():
    res = industry_shock([0.5, 0.03], [0.0, 0.01], window=1)
    assert res["n"] == 1
    assert res["abnormal"] == pytest.approx(0.02)


# --- NEWS-9: similarity, W_dup and weighted novelty ------------------------ #


def test_identical_headlines_similarity_is_one():
    sim = headline_similarity(
        "Nvidia lands major AI contract!", "nvidia lands major ai contract"
    )
    assert sim == pytest.approx(1.0, abs=1e-6)
    assert duplicate_weight(sim) == pytest.approx(0.0, abs=1e-6)


def test_distinct_headlines_have_no_similarity():
    sim = headline_similarity(
        "Nvidia lands major AI contract", "Coffee prices climb in Brazil"
    )
    assert sim == pytest.approx(0.0, abs=1e-6)


def test_w_dup_lowers_weighted_novelty_versus_distinct():
    identical = ["Nvidia lands major AI contract", "Nvidia lands major AI contract"]
    distinct = ["Nvidia lands major AI contract", "Coffee prices climb in Brazil"]
    dup = weighted_novelty(identical)
    dis = weighted_novelty(distinct)
    assert dup["weighted_novelty"] < dis["weighted_novelty"]
    assert dup["similarity"][1] == pytest.approx(1.0, abs=1e-6)
    assert dup["w_dup"] < dis["w_dup"]


def test_weighted_novelty_refuses_on_an_empty_set():
    res = weighted_novelty([])
    assert res["weighted_novelty"] is None
    assert res["reason"]


def test_weighted_novelty_caps_the_pairwise_pass():
    articles = [f"headline number {i}" for i in range(NOVELTY_MAX_ARTICLES + 5)]
    res = weighted_novelty(articles)
    assert res["capped"] is True
    assert res["n"] == NOVELTY_MAX_ARTICLES
