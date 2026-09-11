"""Every bound tool must be *triggered* in its owner's prompt, not just named.

The binding gate proves the model can call a tool; this one proves the model
is told WHEN. The distinction matters because a tool the prompt only lists
(or never mentions while the schema is bound) is dead weight: the analyst
keeps using its own prose for the claim the computed read was built for.

The old check in ``test_calc_agent_wiring.py`` required only the tool NAME to
appear anywhere in the prompt, and since the single-source refactor it matched
no tools at all (the hand-written lists it searched are gone), so it was
vacuous. This gate reads the prompt text with ``tests/prompt_text.py`` and the
toolsets from ``tradingagents.agents.toolsets``, and requires a trigger
sentence - "use before any X claim", "cite it before ..." - on the line that
mentions the tool.

``PENDING`` is the audited set that predates this gate; each entry is filled
in W3 of docs/implementation_plan_calc_agent_binding.md. The list may only
shrink: an entry that no longer violates the contract fails the gate, so the
debt cannot be parked here forever.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.prompt_text import prompt_strings

REPO = Path(__file__).resolve().parents[1]
UTILS = REPO / "tradingagents" / "agents" / "utils"

# The house style: a claim the tool must be cited before, or a use-before
# instruction. Broad on purpose - wording is the author's, the contract is
# "the model is told when this applies".
TRIGGER_RE = re.compile(
    r"("
    r"use (?:it |them |these |its )?before"
    r"|cite (?:it|them|these|the|this|that|your)\b"
    r"|cite these"
    r"|before any"
    r"|before (?:claiming|presenting|calling|asserting|proposing|sizing|trusting)"
    r"|call it before"
    r"|call before"
    r"|must be cited"
    r"|always cite"
    r"|never cite"
    r"|ground (?:it|the|every|any)\b[^.]{0,40}before"
    r")",
    re.IGNORECASE,
)

# Audited pre-existing gaps (W3 fills each one, then its entry is deleted
# here; an entry whose tool now carries a trigger fails the gate).
PENDING: dict[str, set[str]] = {}


def _surfaces() -> dict[Path, list]:
    """Prompt file -> the tool objects that prompt's owner may call."""
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    analysts = REPO / "tradingagents" / "agents" / "analysts"
    risk_mgmt = REPO / "tradingagents" / "agents" / "risk_mgmt"
    return {
        analysts / "market_analyst.py": analyst_toolset("market"),
        analysts / "news_analyst.py": analyst_toolset("news"),
        analysts / "fundamentals_analyst.py": analyst_toolset("fundamentals"),
        risk_mgmt / "aggressive_debator.py": risk_tool_loop.RISK_DEBATOR_TOOLS,
    }


def _docstring_triggers() -> set[str]:
    """Tools whose own docstring carries the trigger.

    The model reads the tool schema, so a docstring trigger is a real
    instruction - it is exempt from the prompt-side requirement (and named
    here so the exemption is visible rather than accidental).
    """
    out: set[str] = set()
    for f in UTILS.glob("*_tools.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(n) or ""
                if doc and TRIGGER_RE.search(doc):
                    out.add(n.name)
    return out


def triggerless(prompt_text: str, names: set[str], doc_exempt: set[str]) -> set[str]:
    """Names mentioned in the prompt without a trigger on any mentioning line."""
    lines = prompt_text.splitlines()
    out: set[str] = set()
    for name in names:
        if name in doc_exempt:
            continue
        pat = re.compile(r"\b" + re.escape(name) + r"\b")
        hits = [line for line in lines if pat.search(line)]
        if not hits or not any(TRIGGER_RE.search(line) for line in hits):
            out.add(name)
    return out


@pytest.mark.parametrize("path", sorted(_surfaces()), ids=lambda p: p.name)
def test_bound_tools_carry_a_prompt_trigger(path):
    names = {t.name for t in _surfaces()[path]}
    missing = triggerless(prompt_strings(path), names, _docstring_triggers())
    pending = PENDING.get(path.name, set())
    unexplained = sorted(missing - pending)
    assert not unexplained, (
        f"{path.name}: these bound tools are never given a trigger sentence "
        f"('use/cite before any <claim>'): {unexplained}. The model can call "
        "them but is never told when - add the house-style line."
    )
    stale = sorted(pending - missing)
    assert not stale, (
        f"{path.name}: PENDING lists tools that now DO carry a trigger: "
        f"{stale}. Delete those entries so the list only shrinks."
    )


def test_pending_entries_are_really_bound():
    """A pending name must be a tool some surface can call (no typos)."""
    callable_names = {t.name for tools in _surfaces().values() for t in tools}
    unknown = sorted(
        name for names in PENDING.values() for name in names if name not in callable_names
    )
    assert not unknown, f"PENDING names tools that are not bound anywhere: {unknown}"


def test_checker_has_teeth():
    """The contract can fail: a name-only mention is not a trigger."""
    prompt = "- get_expected_move(ticker) - the implied move.\n"
    assert triggerless(prompt, {"get_expected_move"}, set()) == {"get_expected_move"}
    triggered = (
        "- get_expected_move(ticker) - the implied move spread. "
        "Use before any 'the market expects a big move' claim.\n"
    )
    assert triggerless(triggered, {"get_expected_move"}, set()) == set()
    # A docstring trigger is a real instruction the model reads.
    assert triggerless(prompt, {"get_expected_move"}, {"get_expected_move"}) == set()
