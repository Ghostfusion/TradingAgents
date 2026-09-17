"""Every analyst prompt carries the shared report-hygiene rules, once.

Two artifact classes reached the report trees because the prompts disagreed
about them: the news analyst forbade inline self-correction ("corrected: ..."),
the market and fundamentals analysts forbade only the restart form, and the
sentiment analyst neither - and VTV 2026-09-16 market.md then shipped
"Corrected positioning bullet:" plus four loop-error notes. The rules now live
in one constant (`agents/utils/report_hygiene.py`) that every analyst appends;
this gate keeps the four modules wired to it instead of drifting back into
per-analyst variants. Deadline: the repo-wide pytest-timeout (180 s).
"""

from __future__ import annotations

import re
from pathlib import Path

from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.agents.utils.report_hygiene import REPORT_HYGIENE_RULES

REPO = Path(__file__).resolve().parents[1]
ANALYSTS = REPO / "tradingagents" / "agents" / "analysts"
ANALYST_MODULES = ("market_analyst.py", "news_analyst.py",
                   "fundamentals_analyst.py", "sentiment_analyst.py")


def test_the_shared_rule_covers_both_artifact_classes():
    assert "NO SELF-CORRECTION ARTIFACTS" in REPORT_HYGIENE_RULES
    assert "corrected:" in REPORT_HYGIENE_RULES  # the marker the verifier scans for
    assert "NEVER RESTART OR RE-EMIT" in REPORT_HYGIENE_RULES
    for phrase in ("I am stuck repeating myself", "disregard this draft",
                   "I will restart cleanly"):
        assert phrase in REPORT_HYGIENE_RULES


def test_every_analyst_prompt_is_wired_to_the_shared_rule():
    """One convention: the constant is imported and appended exactly once."""
    for name in ANALYST_MODULES:
        src = (ANALYSTS / name).read_text(encoding="utf-8")
        assert "from tradingagents.agents.utils.report_hygiene import" in src, name
        assert len(re.findall(r"REPORT_HYGIENE_RULES", src)) == 2, name  # import + use
        # The per-analyst variants are gone (no second convention beside this).
        assert "NEVER RESTART OR RE-EMIT" not in src, name
        assert "NO SELF-CORRECTION ARTIFACTS" not in src, name


def test_the_sentiment_system_message_carries_the_rule():
    """The built message, not the module's source shape: the rule is in the
    text the model receives."""
    message = sentiment_analyst._build_system_message(
        ticker="VTV", start_date="2026-09-09", end_date="2026-09-16",
        news_block="headline", stocktwits_block="post", reddit_block="",
    )
    assert REPORT_HYGIENE_RULES in message
