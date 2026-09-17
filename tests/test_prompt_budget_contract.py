"""Prompt size ceiling: bound-tool guidance may grow only deliberately.

The market analyst's prompt is the largest fixed instruction block in the
repo and every bound tool costs a line of it, re-sent on every call and every
tool-loop round. Adding guidance is therefore a real cost, not free
documentation, and it has to be paid for explicitly.

Measured when this gate was written (non-docstring string literals a module
can hand a model, ``JoinedStr`` children counted once):

    market          37,527 chars, 161 lines, 77 forced-tool bullets,
                    longest bullet 523 chars
    news             9,531 chars
    fundamentals    19,853 chars

The ceiling is that market figure plus the room the binding plan's own
additions need. A reflow cannot hide growth: the bullet COUNT is capped as
well, and the longest bullet may not grow either.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ANALYSTS = REPO / "tradingagents" / "agents" / "analysts"

# 40_000 -> 40_300 (2026-09-16, deliberate): four tool-guidance lines gained the two
# argument contracts that produced wrong numbers in the reports - every `*_pct`
# argument is a FRACTION (0.01 = 1%) and the exit tools MEASURE their price/ATR when
# given a ticker (NVDA 2026-09-15 read a 1% proposal as 100% and passed an invented
# atr=7.0). The wording was trimmed to the minimum that carries both facts.
#
# 40_300 -> 42_050 (2026-09-16, deliberate): the rule-prose consolidation. Six
# scattered rules became QUOTE-TYPE & SESSION INTEGRITY, seven became CANONICAL
# VALUE DISCIPLINE and three became ATR & STOP MECHANICS, and two rules are new -
# INTRINSIC-VALUE PLAUSIBILITY (sanction `get_scenario_dcf` against the
# options-implied read and the trend/regime tools before a directional call; the
# MSFT 2026-09-16 DCF-vs-consensus case) and SIGNAL SYNTHESIS (name a conflict and
# say what was weighted, routing `get_vif_read`-flagged redundant signals away from
# being restated as independent confirmations). Measured 41,999 chars, so the slack
# is 51 - the next growth must trim something or raise this again.
#
# The block's leading four-space indent was stripped back to column 0 in the same
# pass: it padded every line of the prompt text (456 chars) and pushed the longest
# tool bullet to 527 for a whitespace-only reason, leaving the indicator/tool block
# byte-identical to the previous revision. The bullet COUNT is capped as well as the
# ceiling, so a reflow cannot hide growth.
#
# 42_050 -> 50_000 (2026-09-16, owner's call, deliberate): standing headroom so the
# next rule additions do not each need a budget decision. Measured 41,999 chars - the
# consolidation's real size, unchanged by the helper fix below - so the slack is
# 8,001. The bullet count (95) and the longest-bullet pin (523) are unchanged and
# still bind; only the whole-prompt number is looser. `test_other_analyst_prompts_stay_bounded`
# reuses this constant as a coarse backstop for the other three prompt modules, which
# it was already loose for - none of them has a per-rule style of its own: news
# 15,337, fundamentals 27,617, sentiment 7,105.
#
# `prompt_literal_text` no longer excludes `JoinedStr` segments (2026-09-16, defect
# fixed on sight): an f-string's literal parts ARE `Constant` nodes that `ast.walk`
# visits exactly once, so the exclusion was not a dedup - it was a blind spot that
# hid 2,177 chars of the news prompt and all but 1,406 chars of the sentiment system
# message. Sizes above are post-fix; market/fundamentals did not move.
MARKET_CEILING = 50_000
MARKET_BULLET_LIMIT = 95
LONGEST_BULLET_LIMIT = 523
BULLET_RE = re.compile(r"^\s*-\s*[a-z_]+\s*\(")


def prompt_literal_text(path: Path) -> str:
    """The module's prompt-bearing literals, counted once.

    Every non-docstring string constant, joined. An f-string's literal segments
    ARE ``Constant`` nodes, and ``ast.walk`` visits each exactly once, so no
    special case is needed for ``ast.JoinedStr`` - and adding one is a silent
    blind spot: the earlier revision excluded every segment of a ``JoinedStr``,
    which hid 2,177 chars of the news prompt and effectively the whole sentiment
    system message (1,406 counted against 7,105 real) from the ceiling.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    parts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and node.value.strip()
    ]
    return "\n".join(parts)


def tool_bullets(text: str) -> list[str]:
    return [line for line in text.splitlines() if BULLET_RE.match(line)]


def budget_violations(text: str, ceiling: int, longest: int) -> list[str]:
    """The three budget checks, as a pure function (so it can be tested)."""
    out: list[str] = []
    if len(text) > ceiling:
        out.append(f"prompt text {len(text)} chars exceeds the {ceiling} ceiling")
    bullets = tool_bullets(text)
    if len(bullets) > MARKET_BULLET_LIMIT:
        out.append(f"{len(bullets)} tool bullets exceed the {MARKET_BULLET_LIMIT} limit")
    worst = max((len(b) for b in bullets), default=0)
    if worst > longest:
        out.append(f"longest tool bullet {worst} chars exceeds the {longest} recorded max")
    return out


def test_market_prompt_within_budget():
    text = prompt_literal_text(ANALYSTS / "market_analyst.py")
    assert not budget_violations(text, MARKET_CEILING, LONGEST_BULLET_LIMIT), (
        "the market prompt outgrew its budget - trim wording or raise the "
        "ceiling in this test deliberately"
    )


@pytest.mark.parametrize(
    "name",
    ["news_analyst.py", "fundamentals_analyst.py", "sentiment_analyst.py"],
    ids=lambda n: n,
)
def test_other_analyst_prompts_stay_bounded(name):
    """The other prompts have no per-line style, but they must not balloon.

    All three prompt-bearing analysts are listed: sentiment's system message is
    one f-string, so before the ``JoinedStr`` blind spot in ``prompt_literal_text``
    was fixed it was not measured at all (1,406 chars counted against 7,105 real).
    """
    text = prompt_literal_text(ANALYSTS / name)
    assert len(text) < MARKET_CEILING, f"{name} prompt grew past the market ceiling"


def test_budget_checker_has_teeth():
    over = "- get_x(ticker) - " + "x" * 600 + "\n"
    assert budget_violations(over, MARKET_CEILING, LONGEST_BULLET_LIMIT)
    def _name(i: int) -> str:
        return "get_" + chr(97 + (i // 26) % 26) + chr(97 + i % 26)

    fat = "\n".join(f"- {_name(i)}(ticker) - claim." for i in range(MARKET_BULLET_LIMIT + 1))
    assert any("tool bullets" in v for v in budget_violations(fat, 10**9, 10**9))
    assert not budget_violations("- get_x(t) - ok", MARKET_CEILING, LONGEST_BULLET_LIMIT)
