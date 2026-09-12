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


def test_rebuild_preserves_a_real_runs_json(tmp_path, capsys):
    """A markdown-only rebuild has no pm_decision/risk state, so it must NOT
    rewrite the run-scoped JSON: the 2026-09-12 web rebuild replaced real
    ratings/theses with nulls across the report trees (544 files)."""
    import json

    state = _state()
    state["pm_decision"] = {
        "rating": "Underweight",
        "investment_thesis": "thesis",
        "executive_summary": "summary",
        "data_quality": "fresh",
    }
    tree = tmp_path / "NVDA_20260101_000000"
    tree.mkdir()
    write_report_tree(state, "NVDA", tree, config={"risk_compact_report": False})
    decision_before = (tree / "research_decision.json").read_bytes()
    card_before = (tree / "run_card.json").read_bytes()
    assert json.loads(decision_before)["rating"] == "Underweight"

    rebuild_report(tree)

    assert (tree / "research_decision.json").read_bytes() == decision_before
    assert (tree / "run_card.json").read_bytes() == card_before
    out = capsys.readouterr().out
    assert "preserved" in out and "research_decision.json" in out
    # ...and the markdown really was re-rendered.
    assert (tree / "complete_report.md").exists()


def test_emitter_refuses_to_null_an_existing_contract(tmp_path):
    """Defence in depth: even a direct emitter call without a PM decision must
    leave an existing contract alone."""
    from tradingagents.reporting import write_research_decision

    tree = tmp_path / "TREE"
    tree.mkdir()
    (tree / "research_decision.json").write_text('{"rating": "Overweight"}', encoding="utf-8")
    write_research_decision({"risk_gate": {"verdict": "PASS"}}, "NVDA", tree)
    assert (tree / "research_decision.json").read_text(encoding="utf-8") == '{"rating": "Overweight"}'
