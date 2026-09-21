"""The api_reference "Bound to" column must be machine-true.

That table is what a reader (or an agent) trusts when deciding whether a
computed read is already available to an analyst. It drifted once: the
2026-09-04 wiring gate defined "bound" as appearing in a ToolNode list, so 16
tools were documented as agent-callable while no `bind_tools` set carried
them, and the false claim outlived the gate that produced it.

This gate parses the table and checks every claim against the toolset
OBJECTS: a tool documented on a surface must be in that surface's toolset, and
a tool that no surface can call must be documented as declared (and appear in
the declarations list). Unknown surface labels fail, so a new label cannot
sneak a claim past the check.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "api_reference.md"
WIRING_TEST = REPO / "tests" / "test_calc_agent_wiring.py"
UTILS = REPO / "tradingagents" / "agents" / "utils"
# Docs whose tool tables are hand-maintained: their surface/signature cells are
# not machine-checked (the contract doc is api_reference.md), but a tool they
# name must still exist - a deleted tool must not linger in the wiring design.
EXTRA_TOOL_DOCS = (REPO / "docs" / "design_risk_calculations_agent_wiring.md",)

# The doc's label -> the surface it claims. "macro" is the doc's name for the
# macro-data reads the news analyst owns.
SURFACE_ALIASES = {"macro": "news"}
DECLARED = "declared"


def _declared_tools() -> set[str]:
    """Keys of TOOL_LEGACY_BINDING, read without importing the wiring gate."""
    tree = ast.parse(WIRING_TEST.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        if any(getattr(t, "id", None) == "TOOL_LEGACY_BINDING" for t in node.targets):
            return {
                k.value
                for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
    raise AssertionError("TOOL_LEGACY_BINDING not found in tests/test_calc_agent_wiring.py")


def _surfaces() -> dict[str, set[str]]:
    from tradingagents.agents.toolsets import (
        fundamentals_company_tools,
        fundamentals_etf_tools,
        market_tools,
        news_tools,
    )
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    return {
        "market": {t.name for t in market_tools()},
        "news": {t.name for t in news_tools()},
        "fundamentals": {t.name for t in fundamentals_company_tools()}
        | {t.name for t in fundamentals_etf_tools()},
        "risk debators": {t.name for t in risk_tool_loop.RISK_DEBATOR_TOOLS},
        "trader": {t.name for t in risk_tool_loop.TRADER_TOOLS},
    }


def _rows() -> list[tuple[int, str, str]]:
    """(line number, tool name, bound-to cell) for the tool table rows."""
    out: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(DOC.read_text(encoding="utf-8").splitlines(), 1):
        if not re.match(r"^\|\s*`get_", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = re.match(r"`([A-Za-z_]\w*)", cells[0])
        if name:
            out.append((lineno, name.group(1), cells[2]))
    return out


def _claims(cell: str) -> list[str]:
    return [p.strip().lower() for p in re.split(r"[/+]", cell) if p.strip()]


def test_reference_table_is_non_empty():
    rows = _rows()
    assert len(rows) > 50, f"the tool table moved or shrank unexpectedly ({len(rows)} rows)"


def _tool_names(path: Path) -> set[str]:
    """Public @tool-decorated functions in a module (same rule as the wiring gate)."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        for dec in node.decorator_list:
            name = None
            if isinstance(dec, ast.Name):
                name = dec.id
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                name = dec.func.id
            elif isinstance(dec, ast.Attribute):
                name = dec.attr
            if name == "tool":
                out.add(node.name)
                break
    return out


def _tools_in_tables(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        m = re.match(r"^\|\s*`((?:get_|screen_)[a-z_0-9]+)\(", line)
        if m:
            out.add(m.group(1))
    return out


def test_tools_named_in_hand_maintained_tables_exist():
    """A tool deleted from the code must not linger in a hand-kept table."""
    known: set[str] = set()
    for f in UTILS.glob("*_tools.py"):
        known |= _tool_names(f)
    ghost = sorted(
        (path.name, name)
        for path in EXTRA_TOOL_DOCS
        for name in _tools_in_tables(path)
        if name not in known
    )
    assert not ghost, (
        "these docs name tools that no longer exist - delete or correct the rows: "
        + ", ".join(f"{doc}:{name}" for doc, name in ghost)
    )


def test_documented_surfaces_are_known():
    known = set(_surfaces()) | set(SURFACE_ALIASES) | {DECLARED}
    unknown = sorted(
        {label for _, _, cell in _rows() for label in _claims(cell)} - known
    )
    assert not unknown, (
        f"docs/api_reference.md uses surface labels the gate cannot verify: {unknown}. "
        f"Use one of {sorted(known)} (aliases: {SURFACE_ALIASES})."
    )


def test_documented_bindings_are_real():
    surfaces = _surfaces()
    declared = _declared_tools()
    bad: list[str] = []
    for lineno, name, cell in _rows():
        for label in _claims(cell):
            label = SURFACE_ALIASES.get(label, label)
            if label == DECLARED:
                if name in set().union(*surfaces.values()):
                    bad.append(f"L{lineno} {name}: documented as declared but IS bound")
                elif name not in declared:
                    bad.append(f"L{lineno} {name}: documented as declared but not in TOOL_LEGACY_BINDING")
                continue
            if label not in surfaces:  # unknown labels are reported by their own test
                continue
            if name not in surfaces[label]:
                bad.append(f"L{lineno} {name}: claims {label!r} but is not in that toolset")
    assert not bad, (
        "docs/api_reference.md asserts bindings the toolsets do not have "
        "(the doc is the contract the next reader trusts):\n  " + "\n  ".join(bad)
    )


# ---------------------------------------------------------------------------
# A named test file must exist.
#
# Same class as the table above, one layer out: a test that says "enforced by
# `tests/test_X.py`" is making a claim a reader will follow. Three of these were
# wrong before this check existed - `tests/test_decision_challenge.py` pointed at
# a `test_gate_env_switches.py` that never existed, and the gate registry's
# "Proven by" column named two more (`test_options_surface.py`,
# `test_risk_free_curve.py`) over gates that had no proof at all. Each was found
# by hand; this is the check that finds them instead.
#
# Scoped deliberately to references made BY TEST MODULES. Docs are not included:
# measured over `docs/`, 28 `tests/test_*.py` references resolve to nothing and
# are all legitimate - `docs/implementation_plan_*.md` and `docs/design_*.md` are
# forward-looking plans naming tests still to be written, several in the sibling
# repos (`test_doc_claims.py`, `test_engine_contract.py` are `trading_web`'s,
# `test_inbox.py`/`test_envelope_v2.py` are `TradingExecution`'s), and the
# CHANGELOG records renames (`test_quality_composite.py` ->
# `test_category_scores.py`). A blanket doc check would be an over-strict
# invariant that fails on 28 true statements. A test naming a test is not a
# plan; it is a pointer.
# ---------------------------------------------------------------------------

# Word-boundary anchored: `strategies/backtest_engine.py` ends with
# `test_engine.py` and must NOT be read as a reference to a test module.
_TEST_REF = re.compile(r"(?<![A-Za-z0-9_])test_[A-Za-z0-9_]+\.py")

# This module is the one exclusion, and the only one: the comment block above
# has to quote the broken filenames to explain the defect, so its prose is a
# specification rather than a pointer. Excluding it by NAME (not by pattern)
# keeps that from becoming a general escape hatch.
_SELF = Path(__file__).name


def test_every_test_file_a_test_module_names_exists():
    bad: list[str] = []
    for path in sorted((REPO / "tests").glob("*.py")):
        if path.name == _SELF:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ref in _TEST_REF.findall(line):
                if ref == path.name:
                    continue
                if not (REPO / "tests" / ref).exists():
                    bad.append(f"{path.name}:{lineno} names `tests/{ref}`, which does not exist")
    assert not bad, (
        "a test module points at a test file that is not there, so a reader "
        "following it finds nothing:\n  " + "\n  ".join(bad)
    )
