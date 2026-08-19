"""R1b unit tests: risk gate injected into reports; compact risk mode; TOC."""

from tradingagents.reporting import _slugify, write_report_tree


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
    path = write_report_tree(_state(verdict="REJECT", reasons=["size over cap"]), "TST", tmp_path)
    aggressive = (tmp_path / "4_risk" / "aggressive.md").read_text(encoding="utf-8")
    assert "### Risk Gate (computed)" in aggressive
    assert "REJECT" in aggressive
    assert "aggressive prose" in aggressive  # transcript still present (non-compact)
    report = path.read_text(encoding="utf-8")
    assert "## IV. Risk Management Team Decision" in report
    assert "Risk Gate (computed)" in report


def test_decision_mirrors_risk_gate(tmp_path):
    write_report_tree(_state(verdict="WARN", reasons=["near cap"]), "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Risk Gate (computed)" in decision
    assert "WARN" in decision


def test_compact_mode_verdict_only(tmp_path):
    path = write_report_tree(_state("PASS"), "TST", tmp_path, config={"risk_compact_report": True})
    assert (tmp_path / "4_risk" / "verdict.md").exists()
    assert not (tmp_path / "4_risk" / "aggressive.md").exists()
    report = path.read_text(encoding="utf-8")
    assert "aggressive prose" not in report  # chat suppressed
    assert "Risk Gate (computed)" in report


def test_no_gate_no_changes(tmp_path):
    state = {
        "risk_debate_state": {
            "judge_decision": "decision",
            "aggressive_history": "a",
        }
    }
    path = write_report_tree(state, "TST", tmp_path)
    report = path.read_text(encoding="utf-8")
    assert "Risk Gate (computed)" not in report


def _full_state():
    return {
        "market_report": "# MKT\n\n## 1. Price\n",
        "sentiment_report": "# SENT\n",
        "news_report": "# NEWS\n",
        "fundamentals_report": "# FUND\n",
        "trader_investment_plan": "Trader plan\n",
        "investment_debate_state": {
            "bull_history": "bull\n",
            "bear_history": "bear\n",
            "judge_decision": "decision\n",
        },
        "risk_debate_state": {
            "aggressive_history": "a\n",
            "conservative_history": "c\n",
            "neutral_history": "n\n",
            "judge_decision": "**Rating**: Hold\n",
        },
    }


def test_toc_present_and_links_anchors(tmp_path):
    """The consolidated report carries an auto Table of Contents with anchors."""
    report = write_report_tree(_full_state(), "TST", tmp_path).read_text(encoding="utf-8")
    toc = report.split("## Table of Contents\n", 1)[1].split("\n\n---\n\n## I.", 1)[0]
    assert "[I. Analyst Team Reports](#i-analyst-team-reports)" in toc
    assert "[Market Analyst](#market-analyst)" in toc
    assert "[Fundamentals Analyst](#fundamentals-analyst)" in toc
    assert "[Bull Researcher](#bull-researcher)" in toc
    assert "[Trader](#trader)" in toc
    assert "[Portfolio Manager](#portfolio-manager)" in toc
    # Embedded agent headings are demoted and must NOT leak into the TOC.
    assert "#mkt" not in toc
    assert "[1. Price]" not in toc


def test_slugify():
    assert _slugify("## I. Analyst Team Reports") == "i-analyst-team-reports"
    assert _slugify("### Market Analyst") == "market-analyst"
    assert _slugify("### Aggressive Analyst") == "aggressive-analyst"
