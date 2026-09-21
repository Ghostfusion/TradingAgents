"""Regenerate the `docs/api_reference.md` §1.1 env table from the code.

The heading claims "(complete)". `tests/test_api_reference_env_table.py` is what
enforces that; this script is how you satisfy it without hand-editing 264 rows.

Two mechanisms reach the config, and the union is the surface:

1. `_ENV_OVERRIDES` in `tradingagents/default_config.py` (the bulk), and
2. a literal `os.getenv("TRADINGAGENTS_...", fallback)` inside the
   `DEFAULT_CONFIG` dict (`results_dir`, `data_cache_dir`, the verifier model,
   the tool-call log dir, ...).

Existing human notes in the table are preserved verbatim - they carry domain
knowledge the code cannot. New rows get a code-derived `default X` note and
never an invented semantic one; credential-shaped keys get no note at all.

Usage:
    py -3.12 scripts/gen_api_reference_table.py --check   # exit 1 if stale
    py -3.12 scripts/gen_api_reference_table.py --write
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "api_reference.md"
SRC = REPO / "tradingagents" / "default_config.py"

_SECRET = re.compile(r"key|secret|token|password|passwd", re.I)
_HEADING = "### 1.1"


def code_surface() -> dict[str, str]:
    """Every env var that reaches the config, mapped to the key it sets."""
    source = SRC.read_text(encoding="utf-8")
    surface: dict[str, str] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "_ENV_OVERRIDES" for t in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                assert isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                surface[str(k.value)] = str(v.value)
    # Capture the "key": os.getenv("ENV") PAIR in one match - a backward scan for
    # the nearest preceding key silently reports the PREVIOUS row's key.
    for m in re.finditer(
        r'"([a-z_][a-z0-9_]*)"\s*:\s*(?:int\()?\s*os\.(?:getenv|environ\.get)\(\s*"([A-Z_]+)"',
        source,
    ):
        surface.setdefault(m.group(2), m.group(1))
    return surface


def config_defaults() -> dict[str, object]:
    """Literal defaults, plus the fallback of an `os.getenv` call where it has one."""
    source = SRC.read_text(encoding="utf-8")
    out: dict[str, object] = {}
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", None) == "DEFAULT_CONFIG" for t in node.targets)
            and isinstance(node.value, ast.Call)
        ):
            continue
        arg = node.value.args[0]
        if not isinstance(arg, ast.Dict):
            continue
        for k, v in zip(arg.keys, arg.values, strict=True):
            if not isinstance(k, ast.Constant):
                continue
            key = str(k.value)
            try:
                out[key] = ast.literal_eval(v)
                continue
            except Exception:
                pass
            # Not a literal: an os.getenv("X", FALLBACK) call has a real fallback
            # worth stating; anything else is computed and must NOT be guessed
            # at as None (a wrong note is worse than no note).
            if (
                isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute)
                and v.func.attr in {"getenv", "get"}
                and len(v.args) >= 2
            ):
                try:
                    out[key] = ast.literal_eval(v.args[1])
                except Exception:
                    out[key] = f"computed: {ast.unparse(v.args[1])}"
            else:
                out[key] = "computed"
    return out


def table_bounds(lines: list[str]) -> tuple[int, int]:
    """(header line index, last row index) of the §1.1 table."""
    start = next(i for i, ln in enumerate(lines) if ln.startswith(_HEADING))
    header = next(i for i in range(start, len(lines)) if lines[i].startswith("| Env var"))
    end = header
    while end + 1 < len(lines) and lines[end + 1].startswith("|"):
        end += 1
    return header, end


def harvest_notes(lines: list[str], header: int, end: int) -> dict[str, str]:
    """Existing env -> note, so no hand-written knowledge is lost.

    A row may name several env vars as `` `A` / `_B` ``; the `_B` continuation
    inherits the prefix of the first.
    """
    notes: dict[str, str] = {}
    for i in range(header + 2, end + 1):
        ln = lines[i]
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        # cells[2] IS the note in a 3-cell row; anything beyond it is corruption
        # from a mangled row, never more note.
        note = cells[2].strip() if len(cells) > 2 else ""
        if not note or note in {"—", "-"}:
            continue
        for tok in re.findall(r"`([^`]+)`", cells[0]):
            for part in (p.strip() for p in tok.split("/")):
                if not part or part == "—":
                    continue
                if part.startswith("_"):
                    first = cells[0].split("`")[1].split("/")[0].strip()
                    part = re.sub(r"_[A-Z0-9_]*$", "", first) + part
                notes.setdefault(part, note)
    return notes


def note_for(env: str, key: str, notes: dict[str, str], defaults: dict[str, object]) -> str:
    if env in notes:
        return notes[env]
    if _SECRET.search(key) or _SECRET.search(env):
        return ""          # never print a value for a credential-shaped key
    val = defaults.get(key, "?")
    if val == "computed":
        return "default computed at load"
    if val is None:
        return "default `None`"
    if isinstance(val, bool):
        return "default `" + ("true" if val else "false") + "`"
    if isinstance(val, (int, float)):
        return f"default `{val}`"
    if isinstance(val, str):
        return "default empty" if val == "" else f"default `{val}`"
    if isinstance(val, dict):
        return f"default `{val}`" if len(val) <= 4 else f"default `{{...}}` ({len(val)} entries)"
    if isinstance(val, (list, tuple)):
        return f"default `{list(val)}`" if len(val) <= 6 else f"default `[...]` ({len(val)} entries)"
    return f"default `{type(val).__name__}`"


def build_table(lines: list[str]) -> list[str]:
    surface = code_surface()
    defaults = config_defaults()
    header, end = table_bounds(lines)
    notes = harvest_notes(lines, header, end)
    rows = ["| Env var | Config key | Notes |", "| --- | --- | --- |"]
    for env, key in surface.items():
        note = note_for(env, key, notes, defaults).replace("|", r"\|")
        rows.append(f"| `{env}` | `{key}` | {note} |")
    return lines[:header] + rows + lines[end + 1 :]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="rewrite the table in place")
    g.add_argument("--check", action="store_true", help="exit 1 if the table is stale")
    args = ap.parse_args(argv)

    raw = DOC.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "expected a CRLF tree"

    updated = build_table(lines)
    new = ("\r\n".join(updated) + "\r\n").encode("utf-8")
    if new == raw:
        print("docs/api_reference.md §1.1 is up to date")
        return 0
    if args.check:
        print("docs/api_reference.md §1.1 is STALE - re-run with --write", file=sys.stderr)
        return 1
    DOC.write_bytes(new)
    print(f"wrote {DOC.relative_to(REPO)} ({len(updated)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
