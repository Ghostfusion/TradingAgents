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

MARKET_CEILING = 40_000
MARKET_BULLET_LIMIT = 95
LONGEST_BULLET_LIMIT = 523
BULLET_RE = re.compile(r"^\s*-\s*[a-z_]+\s*\(")


def prompt_literal_text(path: Path) -> str:
    """The module's prompt-bearing literals, counted once.

    Mirrors ``tests/prompt_text.py`` but excludes a ``JoinedStr`` child that
    its parent already contributes, so an f-string cannot be counted twice.
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
    in_joined: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant):
                    in_joined.add(id(value))
    parts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and id(node) not in in_joined
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
    "name", ["news_analyst.py", "fundamentals_analyst.py"], ids=lambda n: n
)
def test_other_analyst_prompts_stay_bounded(name):
    """The other prompts have no per-line style, but they must not balloon."""
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
