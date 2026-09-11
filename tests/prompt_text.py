"""Extract the prompt text a module builds, for prompt-content assertions.

Prompt-wording guards ("the analyst must be told to cite this tool", "the
analyst that calls tools keeps its date guidance") are real contracts, but
reading them with ``inspect.getsource`` pins the file's shape: a rename or a
reformat breaks the test with no behaviour change, and a wording that survives
only in a comment still satisfies it.

This collects the string literals a module can hand to a model - the
``system_message`` chain, any ``*_SYSTEM_TAIL`` constant, the literals inside
``ChatPromptTemplate`` messages, and anything a builder function returns -
while excluding docstrings (which are documentation, not prompt text).

Not a test module (no ``test_`` prefix), so pytest does not collect it.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["prompt_strings"]


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of string constants that are module/class/function docstrings."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if body and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                out.add(id(value))
    return out


def prompt_strings(module_file: str | Path) -> str:
    """Every non-docstring string literal in ``module_file``, joined."""
    path = Path(module_file)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.append(v.value)
    return "\n".join(out)
