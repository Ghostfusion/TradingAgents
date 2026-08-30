"""Readability + risk-file behavior of the report writer.

1. _readable_section must turn a dense single-newline debate into spaced
   paragraphs with Round headings, without corrupting tables/headings/lists.
2. The interactive CLI must always write the verbose risk files (aggressive/
   conservative/neutral), never the compact verdict.md, regardless of any
   ambient TRADINGAGENTS_RISK_COMPACT_REPORT.
"""

import tempfile
from pathlib import Path

import pytest

from tradingagents.reporting import _readable_section, write_report_tree

pytestmark = pytest.mark.timeout(180)


def test_readable_section_spaces_prose_and_preserves_blocks():
    sample = (
        "Aggressive Analyst: round one prose line\n"
        "continues here without a break\n"
        "To the neutral: a second paragraph\n"
        "| H | V |\n| --- | --- |\n| a | 1 |\n"
        "# Heading stays\n"
        "- list item\n"
        "Aggressive Analyst: round two prose\n"
        "more wall text"
    )
    out = _readable_section(sample, role="Aggressive Analyst")
    # round markers promoted
    assert "### Round 1" in out and "### Round 2" in out
    # the role line and its first continuation stay one paragraph;
    # spacing is added between DISTINCT paragraphs
    assert "round one prose line\ncontinues here" in out
    assert "continues here without a break\n\nTo the neutral" in out
    # tables/headings/list untouched
    assert "| H | V |" in out
    assert "# Heading stays" in out
    assert "- list item" in out


def test_readable_section_single_intro_no_round_heading():
    # A single "Role:" prefix (not a multi-round debate) must NOT gain guards.
    out = _readable_section("Bull: a single prose block only.", role="Bull")
    assert "### Round" not in out
    assert "Bull: a single prose block only." in out


def test_readable_section_is_idempotent():
    sample = (
        "Aggressive Analyst: round one prose line\n"
        "continues here without break\n"
        "Aggressive Analyst: round two prose\n"
        "more wall text"
    )
    once = _readable_section(sample, role="Aggressive Analyst")
    assert once.count("### Round") == 2
    twice = _readable_section(once, role="Aggressive Analyst")
    thrice = _readable_section(twice, role="Aggressive Analyst")
    assert once == twice == thrice
    assert "\n\n\n" not in once


def test_analyst_files_do_not_repeat_risk_gate():
    """The computed gate belongs in 4_risk + 5_portfolio once, not at the
    head of every analyst report (input evidence, not risk output)."""
    state = {
        "market_report": "## Market\n\nanalyzing\n",
        "sentiment_report": "## Sentiment\n\nsocial\n",
        "news_report": "## News\n\nheadlines\n",
        "fundamentals_report": "## Fundamentals\n\nfinancials\n",
        "risk_debate_state": {
            "aggressive_history": "aggressive prose\n",
            "conservative_history": "conservative prose\n",
            "neutral_history": "neutral prose\n",
            "judge_decision": "**Rating**: Hold\n",
        },
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "risk_snapshot": "verdict=PASS",
        "position_contract": "size 10.0% @ stop 95.0",
        "trader_investment_plan": "Trader plan",
        "risk_context": {"single_cvar": 0.05, "book_cvar": 0.02},
    }
    with tempfile.TemporaryDirectory() as d:
        write_report_tree(state, "TST", Path(d), config={"risk_compact_report": False})
        root = Path(d)
        for f in ("market", "sentiment", "news", "fundamentals"):
            body = (root / "1_analysts" / f"{f}.md").read_text(encoding="utf-8")
            assert not body.startswith("### Risk Gate (computed)"), f
        # gate once in the decision and once in each risk transcript
        assert (root / "5_portfolio" / "decision.md").read_text(encoding="utf-8").startswith(
            "### Risk Gate (computed)"
        )
        for f in ("aggressive", "conservative", "neutral"):
            assert (root / "4_risk" / f"{f}.md").read_text(encoding="utf-8").startswith(
                "### Risk Gate (computed)"
            )


def test_compact_verdict_does_not_duplicate_decision():
    """Compact verdict.md = the computed risk gate + a pointer, NOT a byte-copy
    of the PM decision (which lives once in 5_portfolio/decision.md)."""
    state = {
        "market_report": "## Market\n\nanalyzing\n",
        "risk_debate_state": {
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "judge_decision": "**Rating**: Overweight\n**Executive Summary**: FULL_DECISION_MARKER\n",
        },
        "risk_gate": {"verdict": "REJECT", "reasons": ["cvar over budget"]},
        "risk_snapshot": "verdict=REJECT; size=5.0%",
        "risk_context": {"single_cvar": 0.025, "book_cvar": 0.02},
        "trader_investment_plan": "**Action**: Buy\n",
    }
    with tempfile.TemporaryDirectory() as d:
        write_report_tree(state, "TST", Path(d), config={"risk_compact_report": True})
        root = Path(d)
        verdict = (root / "4_risk" / "verdict.md").read_text(encoding="utf-8")
        decision = (root / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
        assert "### Risk Gate (computed)" in verdict
        assert "FULL_DECISION_MARKER" in decision
        assert "FULL_DECISION_MARKER" not in verdict
        assert "5_portfolio/decision.md" in verdict


def test_write_report_tree_verbose_risk_without_compact():
    state = {
        "risk_debate_state": {
            "aggressive_history": "aggressive prose\n",
            "conservative_history": "conservative prose\n",
            "neutral_history": "neutral prose\n",
            "judge_decision": "**Rating**: Hold\n**Executive Summary**: x\n",
        },
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "risk_snapshot": "verdict=PASS",
        "trader_investment_plan": "Trader plan",
        "risk_context": {},
    }
    with tempfile.TemporaryDirectory() as d:
        # force verbose: _readable_section must not be gated by compact
        path = write_report_tree(state, "TST", Path(d), config={"risk_compact_report": False})
        risk = Path(d) / "4_risk"
        assert (risk / "aggressive.md").exists()
        assert (risk / "conservative.md").exists()
        assert (risk / "neutral.md").exists()
        assert not (risk / "verdict.md").exists()
        assert path.name == "complete_report.md"
