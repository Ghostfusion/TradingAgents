"""Test-quality gate (S6): a test must be able to fail.

The 2026-09-10 audit found ~25 tests that could not fail - tautologies
(``... or True``, ``x is not None or x is None``, ``assert True``,
``x in (True, None, False)``), assertions pinning source text instead of
behaviour (``inspect.getsource``), and escapes that convert a real regression
into a skip (``except Exception: pytest.skip``). Each one makes a green suite
lie about what it covers: the lookahead sentinel whose PnL check was
unconditionally true, the gate test that accepted every verdict, the
disconnect between a test name and what it exercises.

This gate bans those shapes in ``tests/`` so they cannot come back. It is
deliberately narrow: only patterns that are never correct in a test, so a
failure here is always a real defect rather than a style opinion.

Legitimate cases are not flagged: ``monkeypatch.chdir`` (restored by pytest),
``datetime.now()``/``time.time()`` used to build an input (nondeterminism is a
separate concern), and ``pytest.skip`` outside an exception handler.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"
SELF = Path(__file__).name

# (label, compiled pattern, why it cannot fail)
BANNED = [
    (
        "assert-true",
        re.compile(r"^\s*assert\s+True\s*(#.*)?$"),
        "'assert True' verifies nothing - assert the observable result instead",
    ),
    (
        "assert-false",
        re.compile(r"^\s*assert\s+False\b"),
        "'assert False' vanishes under python -O; raise AssertionError(...) instead",
    ),
    (
        "or-true",
        re.compile(r"\bor\s+True\s*$"),
        "a trailing 'or True' makes the whole assertion unconditionally true",
    ),
    (
        "all-values",
        re.compile(r"\bin\s*\(\s*True\s*,\s*None\s*,\s*False\s*\)|\bin\s*\(\s*False\s*,\s*True\s*,\s*None\s*\)"),
        "enumerating every possible value asserts nothing about which one holds",
    ),
    (
        "not-none-or-none",
        re.compile(r"is\s+not\s+None\s+or\s+[^#\n]*\bis\s+None\b"),
        "'x is not None or x is None' is always true",
    ),
    (
        "getsource",
        re.compile(r"\binspect\.getsource\("),
        "asserting on source text pins the implementation, not the behaviour",
    ),
    (
        "raw-chdir",
        re.compile(r"(?<!monkeypatch\.)\bos\.chdir\("),
        "os.chdir mutates process-global state; use monkeypatch.chdir(tmp_path)",
    ),
]


def _test_files() -> list[Path]:
    return sorted(p for p in TESTS.rglob("test_*.py") if p.name != SELF)


def _code_lines(path: Path):
    """(lineno, line) for executable lines (docstrings/comments excluded)."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    skip: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        end = getattr(node, "end_lineno", None) or node.lineno
        if end > node.lineno:
            skip.update(range(node.lineno, end + 1))
    for i, line in enumerate(src.splitlines(), 1):
        if i in skip or line.lstrip().startswith("#"):
            continue
        yield i, line


CASES: list[tuple[str, str, str, int, str]] = []
for _f in _test_files():
    for _label, _pat, _why in BANNED:
        for _ln, _line in _code_lines(_f):
            if _pat.search(_line):
                CASES.append((f"{_f.name}:{_ln}:{_label}", _label, _why, _ln, _line.strip()))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_no_unfalsifiable_assertion(case):
    key, label, why, _lineno, line = case
    raise AssertionError(f"{key}: {line}\n  {label}: {why}")


def test_no_skip_inside_except_handler():
    """A blanket except that turns a regression into a skip hides it instead."""
    offenders = []
    for f in _test_files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and getattr(sub.func, "attr", "") in {"skip", "xfail", "importorskip"}
                ):
                    offenders.append(f"{f.name}:{sub.lineno}")
    assert not offenders, (
        "pytest.skip/xfail/importorskip inside an except handler converts a real "
        f"failure into a skip: {offenders}"
    )


def test_gate_scans_the_suite():
    """The gate must actually read the suite (an empty scan is not a pass)."""
    files = _test_files()
    assert len(files) > 150, f"only {len(files)} test files scanned - the gate broke"
    lines = sum(1 for f in files for _ in _code_lines(f))
    assert lines > 10_000, f"only {lines} executable test lines scanned"
