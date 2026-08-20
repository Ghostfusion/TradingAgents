"""G1 + G4 unit tests: position contract + sentiment decay/velocity."""

import pytest

from tradingagents.strategies.contract import (
    build_position_contract,
)
from tradingagents.strategies.sentiment import (
    decayed_weight,
    surprise_velocity,
    weighted_sentiment,
)


def _cfg(**kw):
    base = {
        "risk_per_trade": 0.01,
        "max_position_pct": 0.30,
        "atr_mult": 2.0,
        "target_vol": 0.15,
        "position_odds": 1.0,
        "kelly_fraction": 0.25,
    }
    base.update(kw)
    return base


def _closes(n=120, base=100.0, step=0.4):
    return [base + step * i for i in range(n)]


def test_contract_none_without_closes():
    assert build_position_contract(closes=None, cfg=_cfg()) is None


def test_contract_respects_caps_and_stop():
    closes_f = _closes()
    c = build_position_contract(cfg=_cfg(), closes=closes_f)
    assert c is not None
    assert 0.0 <= c.size_pct <= 0.30
    assert 0.005 <= c.stop_pct <= 0.50
    assert c.stop_loss is not None and c.stop_loss < closes_f[-1]
    assert "kelly=" in c.reason()


def test_contract_flow_scales_down():
    base = build_position_contract(cfg=_cfg(), closes=_closes())
    flow = {"distribution_score": 0.79}
    heavy_dist = build_position_contract(cfg=_cfg(), closes=_closes(), flow_summary=flow)
    assert heavy_dist.size_pct <= base.size_pct
    assert heavy_dist.size_pct == pytest.approx(base.size_pct * 0.21, abs=0.002)


def test_contract_agreement_scales():
    c = build_position_contract(cfg=_cfg(), closes=_closes(), agreement=0.0)
    assert c.size_pct == 0.0


def test_decay_weight_halflife():
    assert decayed_weight(0.0) == pytest.approx(1.0)
    assert decayed_weight(7.0) == pytest.approx(0.5)


def test_weighted_sentiment_labels_and_age():
    msgs = [
        {"label": "bullish", "age_days": 0},  # +1, weight 1
        {"label": "bearish", "age_days": 28},  # -1, weight 0.0625
    ]
    w = weighted_sentiment(msgs)
    assert w is not None and w > 0.5  # fresh bull dominates
    assert weighted_sentiment([]) is None


def test_weighted_sentiment_credibility():
    msgs = [
        {"score": 0.9, "age_days": 0, "credibility": 100.0},
        {"score": -0.8, "age_days": 0, "credibility": 1.0},
    ]
    assert weighted_sentiment(msgs) > 0  # high-cred bull wins


def test_surprise_velocity_zscore():
    history = [0.10, 0.12, 0.08, 0.11, 0.09, 0.13, 0.07, 0.10, 0.12, 0.08] * 3
    uvz = surprise_velocity(0.10, history)  # at baseline -> near zero z
    hot = surprise_velocity(0.90, history)  # big jump -> large positive z
    assert abs(uvz or 0.0) < 3.0
    assert hot is not None and hot > 2.0
    assert surprise_velocity(0.9, []) is None


def test_contract_stop_uses_atr_when_provided():
    closes = [100.0] * 20
    high = [102.0] * 20
    low = [98.0] * 20
    c = build_position_contract(cfg=_cfg(), closes=closes, high=high, low=low)
    assert c is not None
    assert c.stop_loss < 100.0
