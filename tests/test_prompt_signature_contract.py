"""Every tool call form an analyst prompt advertises must actually work (S2).

The existing prompt-guidance gate (``tests/test_calc_agent_wiring.py``) only
checks that a bound tool's NAME appears somewhere in the analyst's
``system_message``. A prompt can therefore tell the model to call a tool with
the wrong arguments and stay green while every such call is rejected by the
tool's pydantic args schema - the model wastes the turn, or silently drops the
evidence the prompt demanded.

This gate compares the advertised argument list against the real signature:
the number of arguments the prompt shows must fit the tool (no more than it
accepts, no fewer than it requires). It found four live mismatches in
``market_analyst`` that the name-only gate could not see, including a prompt
advertising the raw-number earnings-quality inputs under the
``get_earnings_quality(ticker, current_date)`` name (the verdict variant is
``get_earnings_quality_verdict``).

Forms containing an ellipsis are treated as "unspecified arguments" and
skipped - the prompt is not claiming a specific arity there.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from tests.prompt_text import prompt_strings
from tradingagents.agents.utils import analysis_tools as analysis_tools_mod

REPO = Path(__file__).resolve().parents[1]
ANALYSTS = REPO / "tradingagents" / "agents" / "analysts"
_UTILS = REPO / "tradingagents" / "agents" / "utils"

# name -> callable, for every @tool defined in the agents/utils tool modules
_TOOLS: dict[str, Any] = {}
for _p in _UTILS.glob("*_tools.py"):
    try:
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        continue
    for _node in ast.walk(_tree):
        _is_public_def = isinstance(_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _node.name.startswith("_")
        _is_tool = _is_public_def and any(
            (isinstance(d, ast.Name) and d.id == "tool")
            or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "tool")
            or (isinstance(d, ast.Attribute) and d.attr == "tool")
            for d in _node.decorator_list
        )
        if _is_tool:
            _fn = getattr(analysis_tools_mod, _node.name, None)
            if _fn is not None and hasattr(_fn, "func"):
                _TOOLS[_node.name] = _fn

# Tools defined outside analysis_tools (same package, imported there)
for _name in ("get_regime_gate_read",):
    _fn = getattr(analysis_tools_mod, _name, None)
    if _fn is not None and hasattr(_fn, "func"):
        _TOOLS.setdefault(_name, _fn)


def _advertised_calls(text: str) -> list[tuple[str, str]]:
    """(tool_name, args_source) for every advertised call of a known tool."""
    found: list[tuple[str, str]] = []
    for m in re.finditer(r"\b([a-z_]\w*)\(([^()]{0,120})\)", text):
        name, args = m.group(1), m.group(2)
        if name not in _TOOLS:
            continue
        if "..." in args or "…" in args:
            continue  # ellipsis = arity not claimed
        found.append((name, args))
    return found


def _signature(tool_name: str) -> inspect.Signature:
    fn = _TOOLS[tool_name]
    return inspect.signature(fn.func)


def _counts(tool_name: str) -> tuple[int, int]:
    params = [
        p
        for p in _signature(tool_name).parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    ]
    required = len([p for p in params if p.default is inspect.Parameter.empty])
    return required, len(params)


CASES: list[tuple[str, str, str]] = []
for _f in sorted(ANALYSTS.rglob("*.py")):
    if _f.name == "__init__.py":
        continue
    _text = prompt_strings(_f)
    if not _text.strip():
        continue
    for _name, _args in _advertised_calls(_text):
        _given = len([a for a in _args.split(",") if a.strip()])
        _required, _accepted = _counts(_name)
        if _given > _accepted or _given < _required:
            CASES.append((f"{_f.name}:{_name}", _name, _args.strip()))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_advertised_tool_call_matches_signature(case):
    key, name, args = case
    required, accepted = _counts(name)
    raise AssertionError(
        f"{key} advertises `{name}({args})` but the tool accepts "
        f"{required}-{accepted} arguments - a model following this guidance gets a "
        "validation error and loses the evidence the prompt demands. Fix the prompt "
        "or the tool signature."
    )


def test_gate_has_coverage():
    """The gate must actually inspect prompts (an empty scan is not a pass)."""
    total = 0
    for f in sorted(ANALYSTS.rglob("*.py")):
        if f.name == "__init__.py":
            continue
        total += len(_advertised_calls(prompt_strings(f)))
    assert total > 50, f"only {total} advertised tool calls found - the prompt scan broke"
