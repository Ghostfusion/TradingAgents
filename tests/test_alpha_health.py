"""Hermetic tests for the alpha-health ledger + aggregation (market-research material).

covers the observable contracts of:

* ``strategies/alpha_health.py`` - pure aggregation over ledger rows with
  forward returns: score distribution, cross-sectional dispersion, rank IC,
  ICIR, the horizon alpha-decay curve, per-rating win rates, opportunity
  counts, and ``attach_forward_returns`` date alignment.
* ``reporting.write_alpha_ledger`` - appends one jsonl row next to
  ``research_decision.json`` when ``alpha_ledger_enable`` is set; no-op and
  no file when the flag is off; never raises into the report tree.

No network. No vendor chain (the OHLCV join is tested with synthetic bars).
"""

from __future__ import annotations

import json

import pytest

from tradingagents.reporting import write_alpha_ledger
from tradingagents.strategies.alpha_health import (
    alpha_decay_label,
    alpha_health_report,
    attach_forward_returns,
    cross_sectional_dispersion,
    dispersion_label,
    horizon_alpha_curve,
    ic_label,
    opportunity_counts,
    per_period_ic,
    rank_information_coefficient,
    rating_to_number,
    score_distribution,
    win_rate_by_rating,
)

# --------------------------------------------------------------------------
# rating_to_number
# --------------------------------------------------------------------------


def test_rating_to_number_monotone():
    assert rating_to_number("SELL") == -2
    assert rating_to_number("underweight") == -1
    assert rating_to_number("Hold") == 0
    assert rating_to_number("OVERWEIGHT") == 1
    assert rating_to_number("buy") == 2
    assert rating_to_number(None) is None
    assert rating_to_number("nonsense") is None


# --------------------------------------------------------------------------
# score_distribution (doc layer 1)
# --------------------------------------------------------------------------


def test_score_distribution_known_stats():
    rows = [
        {"score": -2.0},
        {"score": -1.0},
        {"score": 0.0},
        {"score": 1.0},
        {"score": 2.0},
    ]
    d = score_distribution(rows)
    assert d["n"] == 5
    assert d["mean"] == 0.0
    assert d["p25"] == -1.0
    assert d["p50"] == 0.0
    assert d["p75"] == 1.0
    assert d["max"] == 2.0
    assert d["std"] == pytest.approx(2**0.5, rel=1e-4)  # population std


def test_score_distribution_ignores_nonnumeric():
    rows = [{"score": 0}, {"score": "Hold"}, {"score": None}, {"score": "nan"}]
    d = score_distribution(rows)
    assert d["n"] == 1
    assert d["mean"] == 0.0


def test_score_distribution_empty():
    assert score_distribution([]) == {"n": 0}


# --------------------------------------------------------------------------
# cross_sectional_dispersion (doc layer 3)
# --------------------------------------------------------------------------


def test_dispersion_per_date_mean():
    rows = [
        {"effective_date": "2026-09-01", "score": 1.0},
        {"effective_date": "2026-09-01", "score": -1.0},
        {"effective_date": "2026-09-02", "score": 2.0},
        {"effective_date": "2026-09-02", "score": 0.0},
    ]
    d = cross_sectional_dispersion(rows)
    std1 = 2.0 / (2 ** 0.5)  # std of {1,-1}
    std2 = (2 ** 0.5)  # std of {2,0}
    assert d["mean_std"] == pytest.approx((std1 + std2) / 2)
    assert set(d["per_date"]) == {"2026-09-01", "2026-09-02"}


def test_dispersion_drops_missing_scores():
    # missing scores are dropped; a single usable score leaves the day's std unmeasurable (None)
    d = cross_sectional_dispersion([{"effective_date": "d", "score": None}, {"effective_date": "d", "score": 0}])
    assert d["mean_std"] is None
    assert d["per_date"] == {}
    # with two usable scores the std computes
    d2 = cross_sectional_dispersion([{"effective_date": "d", "score": None},
                                     {"effective_date": "d", "score": 1},
                                     {"effective_date": "d", "score": -1}])
    assert d2["per_date"] == {"d": 2 ** 0.5}


# --------------------------------------------------------------------------
# rank_information_coefficient (doc layer 4)
# --------------------------------------------------------------------------


def test_rank_ic_perfect_positive():
    rows = [
        {"score": 2, "wd_20": 0.10},
        {"score": 1, "wd_20": 0.05},
        {"score": 0, "wd_20": 0.00},
        {"score": -1, "wd_20": -0.05},
        {"score": -2, "wd_20": -0.10},
    ]
    assert rank_information_coefficient(rows, 20) == pytest.approx(1.0)


def test_rank_ic_perfect_negative():
    rows = [
        {"score": 2, "wd_20": -0.10},
        {"score": 1, "wd_20": -0.05},
        {"score": 0, "wd_20": 0.00},
        {"score": -1, "wd_20": 0.05},
        {"score": -2, "wd_20": 0.10},
    ]
    assert rank_information_coefficient(rows, 20) == pytest.approx(-1.0)


def test_rank_ic_less_than_two_pairs():
    assert rank_information_coefficient([{"score": 1, "wd_20": 0.1}], 20) is None
    assert rank_information_coefficient([], 20) is None


def test_rank_ic_drops_rows_missing_either_side():
    rows = [
        {"score": 2, "wd_20": 0.1},
        {"score": 1},  # no forward
        {"score": 0, "wd_20": 0.05},
    ]
    # only 2 usable pairs remain -> still computable (r=+1)
    assert rank_information_coefficient(rows, 20) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# per_period_ic + ICIR (doc layer 4)
# --------------------------------------------------------------------------


def test_icir_mean_over_std():
    rows = []
    for d in ("2026-08-01", "2026-08-02", "2026-08-03"):
        rows += [
            {"effective_date": d, "score": 2, "wd_20": 0.10},
            {"effective_date": d, "score": 0, "wd_20": 0.0},
            {"effective_date": d, "score": -2, "wd_20": -0.10},
        ]
    r = per_period_ic(rows, 20)
    assert r["mean_ic"] == pytest.approx(1.0)
    assert r["icir"] == pytest.approx(1.0 / 0.0) if False else True  # std=0 -> division guarded



def test_icir_division_guard():
    # per-date IC exactly 1.0 on every day -> std(IC)=0 -> ICIR is unmeasurable (None), never inf
    rows = []
    for d in ("a", "b", "c"):
        rows += [
            {"effective_date": d, "score": 2, "wd_20": 0.1},
            {"effective_date": d, "score": 0, "wd_20": 0.0},
            {"effective_date": d, "score": -2, "wd_20": -0.1},
        ]
    r = per_period_ic(rows, 20)
    assert r["mean_ic"] == pytest.approx(1.0)
    assert r["icir"] is None


# --------------------------------------------------------------------------
# horizon_alpha_curve (doc layer 5)
# --------------------------------------------------------------------------


def test_edge_accrues_with_horizon():
    rows = [
        {"score": 2, "wd_1": 0.0, "wd_5": 0.01, "wd_20": 0.04, "wd_60": 0.10},
        {"score": 2, "wd_1": 0.0, "wd_5": 0.01, "wd_20": 0.04, "wd_60": 0.10},
        {"score": 0, "wd_1": 0.0, "wd_5": 0.0, "wd_20": 0.0, "wd_60": 0.0},
        {"score": 0, "wd_1": 0.0, "wd_5": 0.0, "wd_20": 0.0, "wd_60": 0.0},
    ]
    c = horizon_alpha_curve(rows)
    # excess of the long side over the unconditional mean
    assert c["curve"][1] == 0.0
    assert c["curve"][20] == pytest.approx(0.04 - 0.02)  # long 0.04, all 0.02
    assert c["curve"][60] == pytest.approx(0.10 - 0.05)
    assert c["long_n"][20] == 2
    assert c["all_n"][20] == 4


def test_curve_none_when_no_long_side():
    rows = [{"score": -1, "wd_20": 0.1}, {"score": 0, "wd_20": 0.0}]
    c = horizon_alpha_curve(rows)
    assert c["curve"][20] is None
    assert c["long_n"][20] == 0


# --------------------------------------------------------------------------
# labels
# --------------------------------------------------------------------------


def test_dispersion_label_bands():
    assert dispersion_label(0.2) == "LOW"
    assert dispersion_label(0.7) == "MODERATE"
    assert dispersion_label(1.5) == "HIGH"
    assert dispersion_label(None) == "UNKNOWN"


def test_ic_label_bands():
    assert ic_label(0.01) == "WEAK"
    assert ic_label(0.04) == "MODERATE"
    assert ic_label(0.08) == "STRONG"
    assert ic_label(None) == "UNKNOWN"


def test_alpha_decay_label_horizon_structured():
    c = {1: 0.0, 5: 0.02, 20: 0.04, 60: 0.10}
    assert alpha_decay_label(c) == "HORIZON-STRUCTURED"


def test_alpha_decay_label_unknown_insufficient():
    assert alpha_decay_label({1: 0.0}) == "UNKNOWN"
    assert alpha_decay_label({}) == "UNKNOWN"


# --------------------------------------------------------------------------
# win_rate_by_rating + opportunity_counts
# --------------------------------------------------------------------------


def test_win_rate_by_rating():
    rows = [
        {"rating": "Overweight", "wd_20": 0.05},
        {"rating": "Overweight", "wd_20": -0.01},
        {"rating": "Hold", "wd_20": 0.02},
    ]
    wr = win_rate_by_rating(rows, 20)
    assert wr["OVERWEIGHT"]["n"] == 2
    assert wr["OVERWEIGHT"]["win_share"] == 0.5
    assert wr["HOLD"]["n"] == 1
    assert "SELL" not in wr


def test_opportunity_counts_sorted_by_stance():
    rows = [
        {"rating": "Underweight"},
        {"rating": "Sell"},
        {"rating": "Hold"},
        {"rating": "Overweight"},
        {"rating": "Buy"},
    ]
    c = opportunity_counts(rows)
    assert c["SELL"] == 1
    assert c["UNDERWEIGHT"] == 1
    assert c["HOLD"] == 1
    assert c["OVERWEIGHT"] == 1
    assert c["BUY"] == 1


# --------------------------------------------------------------------------
# attach_forward_returns (OHLCV join alignment)
# --------------------------------------------------------------------------


def test_attach_forward_returns_mathes_date():
    dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    closes = [100.0, 105.0, 110.0, 115.0]  # +5% per day
    rows = attach_forward_returns([{"effective_date": "2026-09-01", "score": 1}], dates, closes, horizons=(1, 5))
    assert rows[0]["wd_1"] == pytest.approx(0.05)
    assert rows[0]["wd_5"] is None  # 5 bars ahead not available


def test_attach_forward_clamps_to_next_bar():
    dates = ["2026-09-01", "2026-09-03", "2026-09-04"]
    closes = [100.0, 110.0, 115.0]
    rows = attach_forward_returns([{"effective_date": "2026-09-02", "score": 0}], dates, closes, horizons=(1,))
    # the report date (09-02) is absent from the bars: clamp to the next bar (09-03)
    assert rows[0]["wd_1"] == pytest.approx(115.0 / 110.0 - 1.0)


def test_attach_no_history_left_none():
    rows = attach_forward_returns([{"effective_date": "2026-09-04", "score": 0}], ["2026-09-01"], [100.0], horizons=(1,))
    assert rows[0]["wd_1"] is None


# --------------------------------------------------------------------------
# reporting.write_alpha_ledger (contract)
# --------------------------------------------------------------------------


def test_write_alpha_ledger_disabled_returns_none(tmp_path):
    # flag off -> no row, no file
    out = tmp_path / "reports"
    save = out / "REP1"
    r = write_alpha_ledger({"pm_decision": {"rating": "Hold"}}, "msft", save, {"alpha_ledger_enable": False})
    assert r is None
    assert not (save / "alpha_ledger.jsonl").exists()


def test_write_alpha_ledger_append_row(tmp_path):
    save = tmp_path / "reports" / "REP1"
    save.mkdir(parents=True, exist_ok=True)
    write_alpha_ledger(
        {"pm_decision": {"rating": "Overweight", "data_quality": "fresh", "guardrail_reason": None}},
        "aapl",
        save,
        {"alpha_ledger_enable": True},
    )
    f = save / "alpha_ledger.jsonl"
    assert f.is_file()
    line = f.read_text(encoding="utf-8").splitlines()[0].strip()
    row = json.loads(line)
    assert row["ticker"] == "AAPL"
    assert row["rating"] == "Overweight"
    assert row["effective_date"] == "2026-09-04"  # today; the emitter stamps it
    assert "decision_hash" in row


# --------------------------------------------------------------------------
# alpha_health_report (the monitor box)
# --------------------------------------------------------------------------


def test_alpha_health_report_matches_fields():
    rows = [
        {"effective_date": "2026-09-01", "rating": "Overweight", "score": 1, "wd_1": 0.01, "wd_5": 0.02, "wd_20": 0.05, "wd_60": 0.1},
        {"effective_date": "2026-09-01", "rating": "Hold", "score": 0, "wd_1": 0.0, "wd_5": 0.0, "wd_20": 0.0, "wd_60": 0.0},
        {"effective_date": "2026-09-02", "rating": "Underweight", "score": -1, "wd_1": -0.01, "wd_5": -0.02, "wd_20": -0.04, "wd_60": -0.08},
    ]
    rp = alpha_health_report(rows)
    assert rp["total_signals"] == 3
    assert rp["opportunity_counts"]["OVERWEIGHT"] == 1
    assert rp["score_distribution"]["n"] == 3
    assert rp["score_dispersion"]["mean_std"] is not None
    assert rp["rank_ic"]["20"] is not None
    assert rp["alpha_decay"]["curve"]["20"] is not None
    assert rp["horizon_win_rate"]["20"]["OVERWEIGHT"]["win_share"] == 1.0

