"""R0 unit tests: RiskGovernor gate."""

from tradingagents.strategies.risk_governor import (
    build_risk_snapshot,
    default_limits,
    govern,
)


def test_pass_when_within_limits():
    v = govern(0.10, {"max_position_pct": 0.30})
    assert v["verdict"] == "PASS"


def test_reject_over_size_cap():
    v = govern(0.60, {"max_position_pct": 0.30})
    assert v["verdict"] == "REJECT"
    assert "cap" in v["reasons"][0]


def test_reject_on_multiple_touches():
    v = govern(0.28, {"max_position_pct": 0.30, "risk_max_drawdown_pct": 0.10}, drawdown_pct=0.22)
    assert v["verdict"] == "REJECT"


def test_warn_near_cap():
    v = govern(0.29, {"max_position_pct": 0.30})
    assert v["verdict"] == "WARN"
    assert "near cap" in v["touches"][0]


def test_halt_rejects():
    v = govern(0.05, halted=True)
    assert v["verdict"] == "REJECT"


def test_unknown_size_passes():
    v = govern(None)
    assert v["verdict"] == "PASS"


def test_cvar_budget_gate():
    v = govern(0.05, {"risk_daily_cvar_budget_pct": 0.03}, cvar_pct=0.05)
    assert v["verdict"] == "REJECT" or v["verdict"] == "WARN"


def test_book_cap():
    v = govern(0.20, {"risk_max_position_pct": 0.45}, book_total_pct=0.30)
    assert v["verdict"] == "REJECT"


def test_snapshot_is_compact():
    snap = build_risk_snapshot(
        {"verdict": "WARN", "reasons": ["size near cap"]},
        size_pct=0.28,
        stop_pct=0.02,
        cvar_pct=0.04,
    )
    assert snap.startswith("risk snapshot:")
    assert "size=28.0%" in snap


def test_default_limits():
    limits = default_limits({"max_position_pct": 0.5})
    assert limits["max_position_pct"] == 0.5


# --------------------------------------------------------------------------
# Tranche fold: capital-at-risk budget (Value_Dip_swing_Continue.md)
# --------------------------------------------------------------------------


def test_capital_at_risk_over_budget_rejects():
    v = govern(0.05, {}, capital_at_risk_pct=0.03, risk_cap_pct=0.015)
    assert v["verdict"] == "REJECT"
    assert "capital-at-risk 3.00% > cap 1.50%" in v["reasons"][0]


def test_capital_at_risk_within_budget_passes():
    v = govern(0.05, {}, capital_at_risk_pct=0.012, risk_cap_pct=0.015)
    assert v["verdict"] == "PASS"


def test_capital_at_risk_near_budget_warns():
    v = govern(0.05, {}, capital_at_risk_pct=0.0142, risk_cap_pct=0.015)
    assert v["verdict"] == "WARN"
    assert "near cap" in v["touches"][0]


def test_capital_at_risk_skipped_when_none():
    # backward compat: no args -> unchanged
    v = govern(0.05, {})
    assert v["verdict"] == "PASS"


def test_snapshot_shows_capital_at_risk():
    snap = build_risk_snapshot(
        {"verdict": "WARN", "reasons": []},
        size_pct=0.05,
        stop_pct=0.03,
        cvar_pct=0.02,
        capital_at_risk_pct=0.014,
    )
    assert "cap_at_risk=1.40%" in snap
