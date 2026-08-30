"""rebuild_complete_report must round-trip the risk gate from any file that
carries it (decision.md, risk files, or analyst files in older layouts)."""

import tempfile
from pathlib import Path

import pytest

from scripts.rebuild_complete_report import _recover_gate, rebuild_report
from tradingagents.reporting import write_report_tree

pytestmark = pytest.mark.timeout(180)


def _state(verdict="REJECT"):
    return {
        "market_report": "## Market\n\nanalyzing\n",
        "sentiment_report": "## Sentiment\n\nsocial\n",
        "news_report": "## News\n\nheadlines\n",
        "fundamentals_report": "## Fundamentals\n\nfinancials\n",
        "investment_debate_state": {"bull_history": "b\n", "bear_history": "b\n", "judge_decision": "**Plan**: x\n"},
        "trader_investment_plan": "**Action**: Buy\n",
        "risk_debate_state": {
            "aggressive_history": "Aggressive Analyst: round one\nmore\n",
            "conservative_history": "conservative\nprose\n",
            "neutral_history": "neutral\nprose\n",
            "judge_decision": "**Rating**: Overweight\n**Executive Summary**: x\n",
        },
        "risk_gate": {"verdict": verdict, "reasons": ["cvar over budget"]},
        "risk_snapshot": f"verdict={verdict}; size=10.0%",
        "risk_context": {"single_cvar": 0.025, "book_cvar": 0.02},
        "position_contract": "size 10.0% @ stop 95.0",
    }


def test_rebuild_roundtrips_gate_from_decision():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # fresh write: gate in decision + risk, not analysts
        write_report_tree(_state(), "TST", root, config={"risk_compact_report": False})
        rebuilt = rebuild_report(root)
        assert rebuilt.name == "complete_report.md"
        dec = (root / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
        assert dec.startswith("### Risk Gate (computed)")
        assert "REJECT" in dec
        # analysts stay clean
        mkt = (root / "1_analysts" / "market.md").read_text(encoding="utf-8")
        assert not mkt.startswith("### Risk Gate (computed)")


def test_rebuild_is_idempotent_no_double_rounds():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        write_report_tree(_state(), "TST", root, config={"risk_compact_report": False})
        aggr = (root / "4_risk" / "aggressive.md").read_text(encoding="utf-8")
        rebuild_report(root)  # once
        rebuild_report(root)  # twice
        aggr2 = (root / "4_risk" / "aggressive.md").read_text(encoding="utf-8")
        assert aggr2.count("### Round ") == aggr.count("### Round ")


def test_recover_gate_accepts_risk_file_when_decision_lacks_it():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        write_report_tree(_state(), "TST", root, config={"risk_compact_report": False})
        # simulate an older layout: gate only on a risk file
        (root / "5_portfolio" / "decision.md").write_text(
            (root / "5_portfolio" / "decision.md").read_text(encoding="utf-8").split("\n\n\n", 1)[-1],
            encoding="utf-8",
        )
        gate_text, gate, _extra = _recover_gate(root)
        assert gate_text and gate.get("verdict") == "REJECT"
