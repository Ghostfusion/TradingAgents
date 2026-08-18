"""R1b unit tests: risk gate injected into reports; compact risk mode."""

from tradingagents.reporting import write_report_tree


def _state(verdict="PASS", reasons=None):
    return {
        "risk_debate_state": {
            "aggressive_history": "aggressive prose\n",
            "conservative_history": "conservative prose\n",
            "neutral_history": "neutral prose\n",
            "judge_decision": "**Rating**: Hold\n**Executive Summary**: x\n",
        },
        "risk_gate": {"verdict": verdict, "reasons": reasons or []},
        "risk_snapshot": f"verdict={verdict}; size=10.0%; cvar=1.00%",
        "position_contract": "size 10.0% @ stop 95.0 (kelly=0.100)",
        "trader_investment_plan": "Trader plan",
    }


def test_risk_gate_injected_ahead_of_debate(tmp_path):
    path = write_report_tree(_state(verdict="REJECT", reasons=["size over cap"]),
                             "TST", tmp_path)
    aggressive = (tmp_path / "4_risk" / "aggressive.md").read_text(encoding="utf-8")
    assert "### Risk Gate (computed)" in aggressive
    assert "REJECT" in aggressive
    assert "aggressive prose" in aggressive  # transcript still present (non-compact)
    report = path.read_text(encoding="utf-8")
    assert "## IV. Risk Management Team Decision" in report
    assert "Risk Gate (computed)" in report


def test_decision_mirrors_risk_gate(tmp_path):
    path = write_report_tree(_state(verdict="WARN", reasons=["near cap"]),
                             "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Risk Gate (computed)" in decision
    assert "WARN" in decision


def test_compact_mode_verdict_only(tmp_path):
    path = write_report_tree(_state("PASS"),
                             "TST", tmp_path, config={"risk_compact_report": True})
    assert (tmp_path / "4_risk" / "verdict.md").exists()
    assert not (tmp_path / "4_risk" / "aggressive.md").exists()
    report = path.read_text(encoding="utf-8")
    assert "aggressive prose" not in report  # chat suppressed
    assert "Risk Gate (computed)" in report


def test_no_gate_no_changes(tmp_path):
    state = {"risk_debate_state": {
        "judge_decision": "decision",
        "aggressive_history": "a",
    }}
    path = write_report_tree(state, "TST", tmp_path)
    report = path.read_text(encoding="utf-8")
    assert "Risk Gate (computed)" not in report
