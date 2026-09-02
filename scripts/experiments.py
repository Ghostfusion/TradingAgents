"""Experiment read view (Qlib ``search_records``-style).

Filters the recorder-style ``experiments.jsonl`` ledger (written by
``scripts/runfile.py``) by metrics/params/status and prints a table or JSON;
``--diff`` renders two runs side by side. Purely read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _default_ledger_dir() -> str:
    try:
        from tradingagents.dataflows.config import get_config

        return os.path.join(str(get_config().get("data_cache_dir") or "~/.tradingagents/cache"),
                            "experiments")
    except Exception:  # noqa: BLE001
        return os.path.join(os.path.expanduser("~/.tradingagents/cache"), "experiments")


def load_rows(ledger_dir: str | None = None) -> list[dict]:
    """Read every ledger row; a corrupt line degrades, never raises."""
    d = ledger_dir or _default_ledger_dir()
    path = os.path.join(d, "experiments.jsonl")
    rows: list[dict] = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _leaf(spec: str, row: dict):
    """Dotted-path lookup: 'metrics.ic' -> row['metrics']['ic'].

    A bare key ('ic') falls back to a one-level scan of top-level dict
    values so filters like 'ic>0.03' work without the dotted prefix.
    """
    node: object = row
    for part in spec.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            break
    else:
        return node
    if "." not in spec:
        for top in row.values():
            if isinstance(top, dict) and spec in top:
                return top[spec]
    return None




def _matches(row: dict, filters: list[str]) -> bool:
    """Each filter is 'path op value' (op in ==, !=, >, <, >=, <=, =); a bare
    path requires a truthy value. Non-matching rows are excluded."""
    for f in filters:
        for op in (">=", "<=", "!=", ">", "<", "==", "="):
            if op in f:
                spec, _, raw = f.partition(op)
                got = _leaf(spec.strip(), row)
                try:
                    rhs = float(raw)
                    if isinstance(got, (int, float)):
                        ok = {"==": got == rhs, "!=": got != rhs,
                              ">": got > rhs, "<": got < rhs,
                              ">=": got >= rhs, "<=": got <= rhs,
                              "=": got == rhs}[op]
                    else:
                        ok = (str(got) == raw.strip())
                except ValueError:
                    ok = (str(got).strip().lower() == raw.strip().lower())
                if not ok:
                    return False
                break
        else:
            if not _leaf(f.strip(), row):
                return False
    return True


def _fmt_row(row: dict, cols: list[str]) -> list[str]:
    return [str(_leaf(c, row) if _leaf(c, row) is not None else "") for c in cols]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger-dir", default=None, help="ledger dir override")
    parser.add_argument("--filter-metrics", default=None,
                        help="comma list, e.g. 'ic>0.03,pbo=false,status=done'")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--cols", default="run_id,config_hash,status",
                        help="comma columns (dotted paths)")
    parser.add_argument("--diff", nargs=2, metavar=("A", "B"),
                        help="two run_ids to diff (all columns)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    rows = load_rows(args.ledger_dir)
    if args.diff:
        a = [r for r in rows if r.get("run_id") == args.diff[0]]
        b = [r for r in rows if r.get("run_id") == args.diff[1]]
        if not a or not b:
            print(f"[err] diff needs both run_ids (found {len(a)}, {len(b)})")
            return 2
        keys = sorted({k for r in a + b for k in (r.keys() - {"artifact"})})
        print(f"{'field':<22} {args.diff[0]:<28} {args.diff[1]:<28}")
        for k in keys:
            va = json.dumps((a[-1].get(k)), default=str)[:26]
            vb = json.dumps((b[-1].get(k)), default=str)[:26]
            print(f"{k:<22} {va:<28} {vb:<28}")
        return 0

    filters = [f.strip() for f in (args.filter_metrics or "").split(",") if f.strip()]
    matched = [r for r in rows if _matches(r, filters)]
    matched = matched[-args.limit:] if args.limit else matched
    if not matched:
        print("no matching rows")
        return 0

    if args.format == "json":
        print(json.dumps(matched, ensure_ascii=False, indent=2, default=str))
        return 0

    cols = [c.strip() for c in args.cols.split(",") if c.strip()]
    header = cols or ["run_id", "status"]
    print(" | ".join(h.ljust(14) for h in header))
    print("-+-".join("-" * 14 for _ in header))
    for row in matched[-args.limit:]:
        print(" | ".join(v.ljust(14) for v in _fmt_row(row, header)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
