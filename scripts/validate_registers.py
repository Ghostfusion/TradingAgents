"""Diff-scoped register and citation validator (advisory; never edits).

Two invariants, both stated by the docs themselves, both cheap to check and
expensive to notice by eye:

1. **Register provenance.**  Every OPEN work item in a
   `Strategies/books*/FINDINGS.md` register is a `- [ ]` row, and the register's
   own README states that provenance is marked on every row before anyone acts
   on it (`[verified]` / `[reported]` / `[landed in books/]` / the brief number
   `[NN]`).  A marker on a wrapped continuation line counts - the check is per
   *block*, not per line.  Done (`- [x]`) and corroboration rows are exempt:
   the README marks those as already-true, and they are not a promise about
   future action.

2. **Citation line ranges.**  A `path:line` citation that resolves to a UNIQUE
   file in this workspace must name a line that exists.  A citation resolves
   against the repo root, then against `tradingagents/` (the tree's convention:
   `evaluate.py:37`, `agents/utils/analysis_tools.py:10153`), and - for a bare
   basename - only when that basename is unique across the sibling repos the
   docs may reference too (`main.py`, `capabilities.py` are the web app's and
   the executor's as often as this tree's).  A citation that matches nothing, or
   matches several files, is NOT a finding: it is a cross-repo or third-party
   reference, and flagging those is the over-strict doc invariant the existing
   doc gates deliberately avoid (see `tests/test_doc_binding_claims.py`'s scope
   note).

**Diff-scoping is the point.**  A full run reports every violation as a
*warning*: this repository carries legacy register rows and citations that must
not block a change.  `--diff-from <ref>` narrows the report to the lines ADDED
since `<ref>` and promotes those to *errors*: new debt is a failure, old debt is
a backlog.  Exit code 1 iff an error exists.

Usage:
    py -3.12 scripts/validate_registers.py                       # warnings only
    py -3.12 scripts/validate_registers.py --diff-from origin/main
    py -3.12 scripts/validate_registers.py --json
    py -3.12 scripts/validate_registers.py --paths docs/AGENT_ONBOARDING.md
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import namedtuple

REPO = pathlib.Path(__file__).resolve().parents[1]

#: The register files, and the docs whose prose citations are checked.
REGISTER_GLOBS = ("Strategies/books*/FINDINGS.md",)
DOC_GLOBS = (
    "docs/**/*.md",
    "Strategies/books*/FINDINGS.md",
    "CHANGELOG.md",
    "README.md",
)
#: Trees indexed for a bare-basename resolution.
INDEX_GLOBS = (
    "tradingagents/**/*.py",
    "scripts/*.py",
    "tests/*.py",
    "docs/**/*.md",
    "Strategies/**/*.md",
    "*.md",
    "*.py",
    "*.toml",
    "contracts/*.json",
)
#: Sibling repositories whose own files a bare basename may name; a basename
#: present in one of these is ambiguous and is not checked.
SIBLINGS = ("TradingExecution", "trading_web")
_EXCLUDE_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
     ".mypy_cache", ".ruff_cache", ".pytest_cache", ".next", "coverage"}
)
_WORKSPACE_SUFFIXES = frozenset({".py", ".md", ".json", ".toml", ".txt", ".yaml", ".yml"})

_CITE = re.compile(
    r"(?<![\w/.])((?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|json|toml|txt|ya?ml|cfg|ini)):(\d+)"
)
_OPEN_BULLET = re.compile(r"^\s*-\s*\[\s\]")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
#: A provenance marker: [verified], [reported], [landed in books/], [FIXED ...],
#: or the brief number [NN] the register's "How to read a row" defines.
_MARK = re.compile(r"\[(verified|reported|landed in books/|FIXED[^\]]*|\d+)\]")

Finding = namedtuple("Finding", "kind path line message")

#: A citation like `evaluate.py:37` is written relative to the package, so the
#: resolver tries `tradingagents/` as a second root.
_PKG_ROOT = REPO / "tradingagents"


def _skip(path: pathlib.Path) -> bool:
    s = path.as_posix()
    return "/worktrees/" in s or "__pycache__" in s


def _index() -> dict[str, list[pathlib.Path]]:
    """basename -> every file under REPO with that name (worktrees excluded)."""
    out: dict[str, list[pathlib.Path]] = {}
    for pat in INDEX_GLOBS:
        for p in REPO.glob(pat):
            if _skip(p) or not p.is_file():
                continue
            out.setdefault(p.name, []).append(p)
    return out


def _sibling_basenames() -> set[str]:
    """Every file basename in a sibling repo (pruning heavy directories)."""
    out: set[str] = set()
    for name in SIBLINGS:
        root = REPO.parent / name
        if not root.is_dir():
            continue
        for _dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
            for fn in filenames:
                if pathlib.PurePath(fn).suffix in _WORKSPACE_SUFFIXES:
                    out.add(fn)
    return out


def resolve(
    rel: str, index: dict[str, list[pathlib.Path]], siblings: set[str]
) -> tuple[pathlib.Path | None, bool]:
    """(unique path | None, ambiguous).  None+False = external (not a finding)."""
    if "/" in rel:
        cands = [c for c in (REPO / rel, _PKG_ROOT / rel) if c.is_file()]
        if len(cands) == 1:
            return cands[0], False
        return None, len(cands) > 1
    matches = index.get(rel, [])
    if len(matches) == 1 and rel not in siblings:
        return matches[0], False
    return None, len(matches) > 1 or rel in siblings


def _lines(path: pathlib.Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def citation_findings(
    path: pathlib.Path, index: dict[str, list[pathlib.Path]], siblings: set[str]
) -> list[Finding]:
    """A uniquely-resolved citation naming a line past EOF."""
    out: list[Finding] = []
    for i, line in enumerate(_lines(path), start=1):
        for m in _CITE.finditer(line):
            rel, n = m.group(1), int(m.group(2))
            cand, ambiguous = resolve(rel, index, siblings)
            if cand is None or ambiguous:
                continue
            total = len(_lines(cand))
            if total and n > total:
                out.append(
                    Finding(
                        "citation-out-of-range",
                        path,
                        i,
                        f"`{rel}:{n}` -> {cand.relative_to(REPO).as_posix()} has {total} lines",
                    )
                )
    return out


def register_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """(start_line, block_text) for every OPEN bullet, wrapped lines included."""
    blocks: list[tuple[int, str]] = []
    start: int | None = None
    buf: list[str] = []
    for i, line in enumerate(lines, start=1):
        if _OPEN_BULLET.match(line):
            if start is not None:
                blocks.append((start, "\n".join(buf)))
            start, buf = i, [line]
        elif start is not None:
            if not line.strip() or line.startswith("#") or _TABLE_ROW.match(line):
                blocks.append((start, "\n".join(buf)))
                start, buf = None, []
            else:
                buf.append(line)
    if start is not None:
        blocks.append((start, "\n".join(buf)))
    return blocks


def register_findings(path: pathlib.Path) -> list[Finding]:
    """An open work bullet whose block carries no provenance marker anywhere."""
    out: list[Finding] = []
    for start, block in register_blocks(_lines(path)):
        if not _MARK.search(block):
            head = block.splitlines()[0].strip()
            out.append(
                Finding(
                    "unmarked-row",
                    path,
                    start,
                    f"open work row with no [verified]/[reported]/[NN] marker: {head[:80]}",
                )
            )
    return out


def _targets(paths: list[str] | None) -> list[pathlib.Path]:
    if paths:
        return [p for p in (REPO / x for x in paths) if p.is_file() and not _skip(p)]
    files: list[pathlib.Path] = []
    for pat in DOC_GLOBS:
        files += [p for p in REPO.glob(pat) if p.is_file() and not _skip(p)]
    return sorted(set(files))


def collect(paths: list[str] | None = None) -> list[Finding]:
    index = _index()
    siblings = _sibling_basenames()
    register_names = {p.name for pat in REGISTER_GLOBS for p in REPO.glob(pat)}
    out: list[Finding] = []
    for f in _targets(paths):
        out += citation_findings(f, index, siblings)
        if f.name in register_names and "FINDINGS.md" in f.name:
            out += register_findings(f)
    return out


def added_lines(ref: str) -> dict[str, set[int]]:
    """path (repo-relative) -> set of line numbers added since `ref`."""
    proc = subprocess.run(
        ["git", "diff", "-U0", ref],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit(f"git diff failed against {ref!r}: {proc.stderr.strip()}")
    out: dict[str, set[int]] = {}
    cur: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            out.setdefault(cur, set())
        elif line.startswith("@@") and cur is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) else 1
                out[cur].update(range(start, start + count))
    return out


def is_error(finding: Finding, diff: dict[str, set[int]] | None) -> bool:
    if diff is None:
        return False
    rel = finding.path.relative_to(REPO).as_posix()
    return finding.line in diff.get(rel, set())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diff-from", default=None, help="Git ref; lines added since it are ERRORS.")
    ap.add_argument("--paths", nargs="*", default=None, help="Only check these files.")
    ap.add_argument("--json", action="store_true", help="Machine-readable findings.")
    ap.add_argument("--limit", type=int, default=40, help="Max findings to print (default 40).")
    ap.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit 1 on any warning too (for a scheduled audit, which has no diff).",
    )
    args = ap.parse_args(argv)

    diff = added_lines(args.diff_from) if args.diff_from else None
    findings = sorted(
        collect(args.paths),
        key=lambda f: (0 if is_error(f, diff) else 1, f.path.as_posix(), f.line),
    )
    errors = [f for f in findings if is_error(f, diff)]

    if args.json:
        print(
            json.dumps(
                {
                    "diff_from": args.diff_from,
                    "errors": len(errors),
                    "warnings": len(findings) - len(errors),
                    "findings": [
                        {
                            "kind": f.kind,
                            "path": f.path.relative_to(REPO).as_posix(),
                            "line": f.line,
                            "message": f.message,
                            "severity": "error" if is_error(f, diff) else "warning",
                        }
                        for f in findings
                    ],
                },
                indent=2,
            )
        )
        return 1 if errors else 0

    for f in findings[: args.limit]:
        sev = "error" if is_error(f, diff) else "warning"
        print(f"{sev}: {f.path.relative_to(REPO).as_posix()}:{f.line}: {f.kind}: {f.message}")
    if len(findings) > args.limit:
        print(f"... {len(findings) - args.limit} more (raise --limit)")

    scope = f"changed since {args.diff_from}" if args.diff_from else "whole tree"
    print(
        f"\nregister/citation validator: {len(errors)} error(s), "
        f"{len(findings) - len(errors)} warning(s) over {scope}."
    )
    if diff is None:
        print("(advisory full run - pass --diff-from <ref> to make added lines fatal)")
    return 1 if (errors or (args.fail_on_warnings and findings)) else 0


if __name__ == "__main__":
    sys.exit(main())
