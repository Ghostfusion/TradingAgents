"""Batch A of the FINDINGS §3/§4 backlog: E5, E10, E11, E12.

- E5  cost-floor precondition on the G5 threshold gate (gross edge vs round trip).
- E10 regime-conditional sign test (distribution-free, per regime).
- E11 per-event-class sentiment half-life.
- E12 Marchenko-Pastur i.i.d.-premise check (reported, not gated).

Offline only; no vendor call.
"""

import random

import pytest

pytestmark = pytest.mark.timeout(120)


# ---------------------------------------------------------------------------
# E5 - the cost-floor precondition
# ---------------------------------------------------------------------------


def test_e5_cost_floor_refuses_a_gross_edge_below_round_trip_cost():
    from scripts.evaluate_config_gate import gate_verdict

    returns = [0.002 if i % 2 else 0.001 for i in range(200)]  # mean 0.0015
    base = gate_verdict(returns, train_len=60, test_len=20)
    assert base["ok"] is True and base["reason"] == "pass"

    v = gate_verdict(returns, train_len=60, test_len=20, round_trip_cost=0.01)
    assert v["ok"] is None
    assert v["reason"] == "gross edge below round-trip cost"
    assert v["cost_floor"] == pytest.approx(0.01)
    assert v["gross_edge"] == pytest.approx(0.0015, abs=1e-6)

    # A cost under the edge does not refuse.
    v2 = gate_verdict(returns, train_len=60, test_len=20, round_trip_cost=0.0005)
    assert v2["ok"] is True and v2["reason"] == "pass"


def test_e5_default_is_the_off_state():
    from scripts.evaluate_config_gate import gate_verdict

    returns = [0.002 if i % 2 else 0.001 for i in range(200)]
    v = gate_verdict(returns, train_len=60, test_len=20)
    assert v["cost_floor"] == 0.0
    assert "cost" not in v["reason"]


# ---------------------------------------------------------------------------
# E10 - the regime sign test
# ---------------------------------------------------------------------------


def test_e10_regime_sign_test_is_an_exact_binomial():
    from tradingagents.strategies.regime_performance import regime_conditioned_performance

    rows = [
        {"regime": "bull", "outcome": {"hit": True, "return_pct": 1.0}},
        {"regime": "bull", "outcome": {"hit": True, "return_pct": 2.0}},
        {"regime": "bull", "outcome": {"hit": True, "return_pct": 3.0}},
        {"regime": "bull", "outcome": {"hit": False, "return_pct": -1.0}},
    ]
    st = regime_conditioned_performance(rows)["bull"]["sign_test"]
    assert st["n"] == 4 and st["positives"] == 3
    # two-sided exact binomial, k=3 of 4: 2*(C(4,3)+C(4,4))/2^4 = 10/16
    assert st["p_value"] == pytest.approx(0.625)


def test_e10_sign_test_excludes_zeros_and_none_when_empty():
    from tradingagents.strategies.regime_performance import regime_conditioned_performance

    rows = [
        {"regime": "flat", "outcome": {"hit": True, "return_pct": 0.0}},
        {"regime": "flat", "outcome": {"hit": True, "return_pct": 0.0}},
    ]
    # every return is exactly zero -> nothing non-zero to test
    assert regime_conditioned_performance(rows)["flat"]["sign_test"] is None

    rows2 = [{"regime": "up", "outcome": {"hit": True, "return_pct": 1.0}}] * 3
    st = regime_conditioned_performance(rows2)["up"]["sign_test"]
    assert st["n"] == 3 and st["positives"] == 3
    assert st["p_value"] == pytest.approx(0.25)  # 2 * 1/8


# ---------------------------------------------------------------------------
# E11 - per-event-class half-life
# ---------------------------------------------------------------------------


def test_e11_resolver_and_declared_table():
    from tradingagents.strategies.sentiment import (
        DEFAULT_EVENT_HALF_LIFE_DAYS,
        half_life_for_event,
    )

    assert half_life_for_event("Earnings") == 30.0  # case-insensitive
    assert half_life_for_event("macro") == 3.0
    assert half_life_for_event("not-a-class") == DEFAULT_EVENT_HALF_LIFE_DAYS
    assert half_life_for_event(None, default=12.0) == 12.0


def test_e11_event_class_overrides_the_global_decay():
    from tradingagents.strategies.sentiment import (
        aggregate_weighted_sentiment,
        decayed_weight,
    )

    arts = [
        # 20:00Z is 16:00 NY - at the cutoff, so it rolls to the 08-02 session
        # and carries an age of 1 day; the second is same-session, age 0.
        {
            "time_published": "20260801T200000",
            "ticker_sentiment": [
                {"ticker": "AAPL", "ticker_sentiment_score": 0.4, "relevance_score": 100.0}
            ],
            "title": "A",
            "event_class": "earnings",  # declared half-life 30d, not the global 7
        },
        {
            "time_published": "20260802T100000",
            "ticker_sentiment": [
                {"ticker": "AAPL", "ticker_sentiment_score": -0.2, "relevance_score": 100.0}
            ],
            "title": "B",
        },
    ]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL", half_life=7.0)
    assert out is not None and len(out) == 1
    row = out[0]
    assert row["n"] == 2
    w_old = decayed_weight(1.0, 30.0)  # the earnings-tagged article
    w_new = decayed_weight(0.0, 7.0)   # the untagged article -> global half_life
    assert row["weighted"] == pytest.approx(
        (w_old * 0.4 + w_new * -0.2) / (w_old + w_new), abs=1e-4
    )
    assert "E11" in row["basis"]


def test_e11_untagged_feed_is_unchanged():
    from tradingagents.strategies.sentiment import aggregate_weighted_sentiment, decayed_weight

    arts = [
        {"time_published": "20260801T200000", "ticker_sentiment": [
            {"ticker": "AAPL", "ticker_sentiment_score": 0.4, "relevance_score": 100.0}],
         "title": "A"},
        {"time_published": "20260802T100000", "ticker_sentiment": [
            {"ticker": "AAPL", "ticker_sentiment_score": -0.2, "relevance_score": 100.0}],
         "title": "B"},
    ]
    out = aggregate_weighted_sentiment(arts, ticker="AAPL", half_life=7.0)
    assert out is not None
    row = out[0]
    w_old, w_new = decayed_weight(1.0, 7.0), decayed_weight(0.0, 7.0)
    assert row["weighted"] == pytest.approx(
        (w_old * 0.4 + w_new * -0.2) / (w_old + w_new), abs=1e-4
    )
    assert "E11" not in row["basis"]


# ---------------------------------------------------------------------------
# E12 - the Marchenko-Pastur i.i.d.-premise check
# ---------------------------------------------------------------------------


def test_e12_premise_flags_an_autocorrelated_panel():
    from tradingagents.strategies.market_breadth import mp_iid_premise

    rng = random.Random(7)
    clean = [[rng.gauss(0.0, 0.01) for _ in range(80)] for _ in range(4)]
    ok = mp_iid_premise(clean, threshold=0.2)
    assert ok["iid_ok"] is True
    assert ok["mean_abs_lag1_acf"] < 0.2

    trend: list[list[float]] = []
    for _ in range(4):
        s = [0.0]
        for _ in range(79):
            s.append(0.9 * s[-1] + rng.gauss(0.0, 0.001))
        trend.append(s)
    bad = mp_iid_premise(trend, threshold=0.2)
    assert bad["iid_ok"] is False
    assert bad["mean_abs_lag1_acf"] > 0.2


def test_e12_premise_is_none_never_a_fabricated_true():
    from tradingagents.strategies.market_breadth import mp_iid_premise

    assert mp_iid_premise([])["iid_ok"] is None
    assert mp_iid_premise([[0.1, 0.2]])["iid_ok"] is None  # < 3 returns
    assert mp_iid_premise([[0.0, 0.0, 0.0, 0.0]])["iid_ok"] is None  # flat, no variance


def test_e12_mp_lower_spectrum_carries_the_premise_read():
    from tradingagents.strategies.sector_breadth import mp_lower_spectrum

    rng = random.Random(3)
    closes = {f"S{i}": [100.0] for i in range(12)}
    for _ in range(60):
        for k in closes:
            closes[k].append(closes[k][-1] * (1.0 + rng.gauss(0.0, 0.01)))
    out = mp_lower_spectrum(closes, window=44, cfg={"enable_mp_lower_spectrum": True})
    assert out is not None
    assert "iid_premise" in out
    assert out["iid_premise"]["n_names"] >= 2
    # gate off -> unchanged (the read is not taken)
    assert mp_lower_spectrum(closes, window=44, cfg={}) is None
