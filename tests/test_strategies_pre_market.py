"""Pre-market review deterministic layer - pure/offline tests.

Covers tradingagents/strategies/pre_market.py: the gap read, catalyst-window
re-check, re-anchored tranche plan, and the CONFIRM/REVISE/REJECT arbiter, plus
the prior-state loader. Every test inherits the repo's pytest-timeout deadline
(180s per-test / 30-min session) so a hung call can never block the session.
"""

import json

import pytest

from tradingagents.strategies.pre_market import (
    catalyst_window_read,
    ledger_track_record,
    load_prior_state,
    premarket_gap,
    record_review,
    reanchor_plan,
    resolve_ledger,
    review_decision,
)

# ---------------------------------------------------------------------------
# Gap read
# ---------------------------------------------------------------------------


def test_gap_normal_favorable():
    g = premarket_gap(100.0, 103.0, prior_stop=96.5, entry_price=102.0, atr=4.0)
    assert g["gap_pct"] == pytest.approx(0.03)
    assert g["gap_atr"] == pytest.approx(0.75)
    assert g["through_stop"] is False
    assert g["vacuum_to_stop"] is False
    assert g["direction"] == "long"


def test_gap_through_stop():
    g = premarket_gap(100.0, 95.0, prior_stop=96.5, entry_price=102.0, atr=4.0)
    assert g["through_stop"] is True
    assert g["gap_pct"] == pytest.approx(-0.05)
    assert g["gap_atr"] == pytest.approx(-1.25)


def test_gap_adverse_fill_zone():
    g = premarket_gap(100.0, 98.0, prior_stop=96.5, entry_price=102.0, atr=4.0)
    assert g["through_stop"] is False
    assert g["vacuum_to_stop"] is True  # filled between entry and stop on the adverse side


def test_gap_missing_quote_none():
    g = premarket_gap(None, 100.0)
    assert g["gap_pct"] is None
    assert g["gap_atr"] is None


# ---------------------------------------------------------------------------
# Catalyst window re-check
# ---------------------------------------------------------------------------


def test_catalyst_no_imminent():
    out = catalyst_window_read({"verdict": "no-imminent-catalyst", "scale": 1.0})
    assert out["hard_block"] is False
    assert out["tightened"] is False


def test_catalyst_window_tightens():
    out = catalyst_window_read({"verdict": "earnings-window", "scale": 0.5})
    assert out["tightened"] is True
    assert out["hard_block"] is False


def test_catalyst_hard_block():
    snap = {
        "verdict": "earnings-hard-block",
        "scale": 0.0,
        "hard_block": {"days_until": 2, "earnings_date": "2026-08-25", "window_days": 5},
    }
    out = catalyst_window_read(snap)
    assert out["hard_block"] is True
    assert out["days_until"] == 2
    assert out["scale"] == 0.0


# ---------------------------------------------------------------------------
# Re-anchored tranche plan
# ---------------------------------------------------------------------------


def test_reanchor_valid_and_caps():
    r = reanchor_plan(103.0, 4.0, max_position_pct=0.30, max_book_position_pct=0.45)
    assert r["valid"]
    assert r["avg_entry"] > 0
    assert r["stop"] < r["avg_entry"]
    assert r["cap_ok"] is True
    assert r["book_ok"] is True
    assert r["peak_deployed_pct"] is not None


def test_reanchor_tight_cap_breaches():
    r = reanchor_plan(95.0, 1.0, max_position_pct=0.02)
    assert r["valid"]
    assert r["cap_ok"] is False


def test_reanchor_no_price_invalid():
    assert reanchor_plan(None, 4.0)["valid"] is False
    assert reanchor_plan(103.0, None)["valid"] is False


# ---------------------------------------------------------------------------
# The deterministic verdict arbiter
# ---------------------------------------------------------------------------


def test_same_night_no_deltas_confirm():
    v = review_decision(catalyst_snapshot=None)
    assert v["verdict"] == "CONFIRM"
    assert v["reasons"]


def test_same_night_hard_block_reject():
    snap = {
        "verdict": "earnings-hard-block",
        "scale": 0.0,
        "hard_block": {"days_until": 1, "earnings_date": "2026-08-25", "window_days": 5},
    }
    v = review_decision(catalyst_snapshot=snap)
    assert v["verdict"] == "REJECT"
    assert any("hard block" in r for r in v["reasons"])


def test_same_night_window_revise():
    v = review_decision(catalyst_snapshot={"verdict": "earnings-window", "scale": 0.5})
    assert v["verdict"] == "REVISE"
    assert any("window" in r for r in v["reasons"])


def test_pre_open_gap_through_stop_rejects():
    v = review_decision(
        prior_close=100.0,
        open_price=95.0,
        prior_stop=96.5,
        entry_price=102.0,
        atr_value=4.0,
    )
    assert v["verdict"] == "REJECT"
    assert v["gap"]["through_stop"] is True
    assert any("stop" in r.lower() for r in v["reasons"])


def test_pre_open_adverse_fill_revises():
    v = review_decision(
        prior_close=100.0,
        open_price=98.0,
        prior_stop=96.5,
        entry_price=102.0,
        atr_value=4.0,
    )
    assert v["verdict"] == "REVISE"
    assert any("re-anchor" in r.lower() for r in v["reasons"])


def test_pre_open_big_gap_revises():
    v = review_decision(
        prior_close=100.0,
        open_price=93.0,  # -7% > 1 ATR
        prior_stop=90.0,
        entry_price=102.0,
        atr_value=2.0,
    )
    assert v["verdict"] == "REVISE"
    assert v["gap"]["gap_atr"] == pytest.approx(-3.5)


def test_pre_open_cap_breach_rejects():
    # Re-anchor with a tight cap -> the arbiter rejects the REVISE.
    r = reanchor_plan(95.0, 1.0, max_position_pct=0.02)
    v = review_decision(
        prior_close=100.0,
        open_price=95.0,
        prior_stop=90.0,
        entry_price=102.0,
        atr_value=1.0,
        reanchor=r,
    )
    assert v["verdict"] == "REJECT"
    assert any("cap" in r.lower() for r in v["reasons"])


# ---------------------------------------------------------------------------
# Prior-state loader (fail-open, never raises)
# ---------------------------------------------------------------------------


def test_load_prior_state_missing_folder_fail_open(tmp_path):
    out = load_prior_state(str(tmp_path / "does_not_exist"))
    assert out["state"] is None
    assert out["decision_md"] == ""
    assert out["log_path"] is None


def test_load_prior_state_reads_log_and_decision(tmp_path):
    logs = tmp_path / "EIX" / "TradingAgentsStrategy_logs"
    logs.mkdir(parents=True)
    (logs / "full_states_log_2026-08-21.json").write_text(
        json.dumps(
            {
                "company_of_interest": "EIX",
                "trade_date": "2026-08-21",
                "final_trade_decision": "**Rating**: Buy",
            }
        ),
        encoding="utf-8",
    )
    out = load_prior_state(str(tmp_path / "EIX"), results_dir=str(tmp_path))
    assert out["state"] is not None
    assert out["state"]["final_trade_decision"] == "**Rating**: Buy"
    assert out["date"] == "2026-08-21"


# ---------------------------------------------------------------------------
# Defect-1 fix: planned entry/stop extraction for the gap/through-stop checks
# ---------------------------------------------------------------------------


def test_parse_planned_levels_from_trader_plan():
    from tradingagents.strategies.pre_market import parse_planned_levels

    state = {
        "trader_investment_decision": "**Action**: Buy\n**Entry Price**: 102.0\n**Stop Loss**: 96.5"
    }
    p = parse_planned_levels(state, "**Rating**: Buy")
    assert p["entry"] == pytest.approx(102.0)
    assert p["stop"] == pytest.approx(96.5)


def test_parse_planned_levels_overlay_fallback():
    from tradingagents.strategies.pre_market import parse_planned_levels

    state = {"strategy_overlays": {"position_contract": "size 10.0%, stop 95.0, reason: kelly"}}
    p = parse_planned_levels(state, "**Rating**: Buy")
    assert p["entry"] is None  # no entry in the overlay
    assert p["stop"] == pytest.approx(95.0)


def test_parse_planned_levels_missing_returns_none():
    from tradingagents.strategies.pre_market import parse_planned_levels

    p = parse_planned_levels({"trader_investment_decision": "**Action**: HOLD"}, "")
    assert p == {"entry": None, "stop": None}


def test_review_uses_planned_stop_for_through_stop():
    # Regression: prior_stop must feed the gap read (defect-1 wiring).
    v = review_decision(
        prior_close=100.0,
        open_price=95.0,
        prior_stop=96.5,
        entry_price=102.0,
        atr_value=4.0,
    )
    assert v["verdict"] == "REJECT"
    assert v["gap"]["through_stop"] is True


# ---------------------------------------------------------------------------
# Defect-2 fix: load_prior_state finds the JSON under an explicit results_dir
# ---------------------------------------------------------------------------


def test_load_prior_state_with_results_dir(tmp_path):
    logs = tmp_path / "logs" / "EIX" / "TradingAgentsStrategy_logs"
    logs.mkdir(parents=True)
    (logs / "full_states_log_2026-08-21.json").write_text(
        json.dumps(
            {
                "company_of_interest": "EIX",
                "trade_date": "2026-08-21",
                "final_trade_decision": "**Rating**: Buy",
                "trader_investment_decision": "**Entry Price**: 102.0\n**Stop Loss**: 96.5",
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "reports" / "EIX_20260821_181500"
    report.mkdir(parents=True)
    (report / "5_portfolio").mkdir()
    (report / "5_portfolio" / "decision.md").write_text("**Rating**: Buy\n", encoding="utf-8")

    out = load_prior_state(str(report), results_dir=str(tmp_path / "logs"))
    assert out["state"] is not None
    assert out["state"]["final_trade_decision"] == "**Rating**: Buy"
    # defect-1 levels parse straight out of the located JSON
    p = {"entry": out["state"]["trader_investment_decision"].split("Entry Price**: ")[1].split()[0]}
    assert float(p["entry"]) == pytest.approx(102.0)


def test_ledger_track_record_measures_wins(tmp_path):
    """Item 4: the paper-ledger track record computes win rate / avg return."""
    path = str(tmp_path / "ledger.jsonl")
    record_review(
        path, ticker="EIX", prior_date="2026-08-20", trade_date="2026-08-21",
        verdict="CONFIRM", reasons=[], gap_pct=0.0,
    )
    record_review(
        path, ticker="EIX", prior_date="2026-08-21", trade_date="2026-08-22",
        verdict="REJECT", reasons=[], gap_pct=-0.01,
    )
    # resolve both with an "open" price: gap 0 -> prior_close == open; gap -1% -> higher
    n = resolve_ledger(path, "EIX", "2026-08-23", 100.0)
    assert n == 2
    tr = ledger_track_record(path)
    assert tr["resolved"] == 2
    assert tr["win_rate"] is not None
    assert 0 <= float(tr["win_rate"]) <= 1
    assert tr["sum_realized"] is not None


def test_ledger_track_record_direction_filter(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    record_review(
        path, ticker="EIX", prior_date="2026-08-20", trade_date="2026-08-21",
        verdict="CONFIRM", reasons=[], gap_pct=0.02,
    )
    resolve_ledger(path, "EIX", "2026-08-22", 102.0)
    # only CONFIRM rows counted
    tr = ledger_track_record(path, direction="CONFIRM")
    assert tr["resolved"] == 1
    # no matching direction -> resolved 0, win_rate None (never fabricated)
    other = ledger_track_record(path, direction="REVISE")
    assert other["resolved"] == 0
    assert other["win_rate"] is None
