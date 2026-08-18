"""L1 unit tests: order-flow signal layer (UNH live numbers embedded)."""

import pytest

from tradingagents.strategies.orderflow import (
    tier_nets, institutional_net, retail_net, tier_outflow_score,
    distribution_score, divergence, exhaustion, alignment, summarize,
)

# Exact values pulled from moomoo live distribution for UNH (2026-08-17).
UNH_BUCKETS = {
    "capital_in_super": 1191141.151,
    "capital_out_super": 11333787.54,
    "capital_in_big": 23437297.964,
    "capital_out_big": 36226526.266,
    "capital_in_mid": 40759859.957,
    "capital_out_mid": 57739893.659,
    "capital_in_small": 72657456.219,
    "capital_out_small": 112263837.988,
}


def test_super_ratio_matches_screenshot():
    score = tier_outflow_score(UNH_BUCKETS, "super")
    assert score == pytest.approx(11.33 / (11.33 + 1.19), abs=0.02)


def test_tier_nets_negative_all_tiers():
    nets = tier_nets(UNH_BUCKETS)
    for t in ("super", "big", "mid", "small"):
        assert nets[t] < 0


def test_inst_and_retail_nets():
    nets = tier_nets(UNH_BUCKETS)
    assert institutional_net(nets) < 0
    assert retail_net(nets) < 0
    assert abs(institutional_net(nets)) < abs(retail_net(nets))


def test_distribution_high():
    d = distribution_score(UNH_BUCKETS)
    assert d >= 0.7  # heavy institutional distribution flag threshold


def test_divergence_logic():
    assert divergence("up", -1e6) == "distribution_into_strength"
    assert divergence("down", 1e6) == "silent_accumulation"
    assert divergence("down", -1e6) == "aligned"


def test_alignment():
    nets = tier_nets(UNH_BUCKETS)
    assert alignment(nets) == "all_four_negative"


def test_exhaustion():
    assert exhaustion([-1e6, -8e5, -9e5], -1e5) == "exhaustion_candidate"
    assert exhaustion([-1e6, -8e5, -9e5], -1e6) == "active"
    assert exhaustion([], -1e5) == "unknown"


def test_summarize_flags_distribution():
    sm = summarize(UNH_BUCKETS, direction="flat",
                   weekly_nets=[-1e6, -8e5, -9e5])
    assert sm["flag"] == "distribution"
    assert "FLOW_WARNING" in sm["text"]
    assert sm["distribution_score"] >= 0.7
