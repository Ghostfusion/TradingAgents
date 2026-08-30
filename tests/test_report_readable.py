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
    # paragraph spacing added between plain prose lines
    assert "round one prose line\n\ncontinues here" in out
    # tables/headings/list untouched
    assert "| H | V |" in out
    assert "# Heading stays" in out
    assert "- list item" in out


def test_readable_section_single_intro_no_round_heading():
    # A single "Role:" prefix (not a multi-round debate) must NOT gain guards.
    out = _readable_section("Bull: a single prose block only.", role="Bull")
    assert "### Round" not in out
    assert "Bull: a single prose block only." in out


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
