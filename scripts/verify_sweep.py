"""Post-verifier adjudication workbench (item 3 of the AMZN 2026-09-09 loop).

``scripts/report_verify.py --verify`` writes per-tree verify_flags.json with
hundreds of per-claim verdicts; scrolling them buries the real defects. This
script condenses one run into the confirmation list a human actually needs:

  CONFIRMED (needs a fix / report edit):
    - MISQUOTED          figures ARE in tool evidence but the claim attached
                         them to the wrong label/context (the deterministic
                         anchor detected it - e.g. AMZN composite_rank A/e
                         transposition, T1 265.03 vs 265.97)
    - CONTRADICTED       evidence contains an opposing value/state
    - INTERNAL_CONFLICT  the same metric asserted at conflicting values
                         within ONE report (ATR 6.47 vs 5.7079, T1 mismatch)
  SUSPECT (adjudicate - probably a defect, needs a call):
    - UNSUPPORTED with a matching tool present  -> likely mis-quote / leak
    - UNSUPPORTED with "no leaf evidence"       -> likely fabricated number

Usage:
    py -3.12 scripts/verify_sweep.py                      # all trees under reports/
    py -3.12 scripts/verify_sweep.py --reports-dir reports --json
    py -3.12 scripts/verify_sweep.py --tree reports/AMZN_20260909_122815

Exit code: 1 when any CONFIRMED or SUSPECT claim exists, else 0.
Advisory: read-only, never edits reports or verify_flags.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

CONFIRMED_STATUSES = {"MISQUOTED", "CONTRADICTED", "INTERNAL_CONFLICT"}
SUSPECT_STATUSES = {"UNSUPPORTED"}


def _tool_names(report_tree: Path) -> set:
    """Tool names present in the tree's tool_evidence.json (per analyst)."""
    ev = report_tree / "tool_evidence.json"
    if not ev.exists():
        return set()
    try:
        data = json.loads(ev.read_text(encoding="utf-8", errors="ignore"))
    except (ValueError, TypeError):
        return set()
    names: set = set()
    for block in data.values():
        if not isinstance(block, list):
            continue
        for leaf in block:
            if isinstance(leaf, dict) and leaf.get("tool"):
                names.add(str(leaf["tool"]))
    return names


def _sweep_tree(tree: Path) -> dict:
    flags_path = tree / "verify_flags.json"
    if not flags_path.exists():
        return {"tree": str(tree), "present": False, "summary": {}, "confirmed": [], "suspect": []}
    try:
        flags = json.loads(flags_path.read_text(encoding="utf-8", errors="ignore"))
    except (ValueError, TypeError):
        return {"tree": str(tree), "present": False, "summary": {}, "confirmed": [], "suspect": []}
    verification = flags.get("verification") or {}
    tool_names = _tool_names_in_tree(tree)
    status_counts: Counter = Counter()
    confirmed: list[dict] = []
    suspect: list[dict] = []
    for stem, v in verification.items():
        claims = v.get("claims") if isinstance(v, dict) else None
        if not isinstance(claims, list):
            continue
        for c in claims:
            st = c.get("status")
            if not st:
                continue
            status_counts[st] += 1
            cls = "confirmed" if st in CONFIRMED_STATUSES else ("suspect" if st in SUSPECT_STATUSES else "ok")
            row = {
                "stem": stem,
                "claim": (c.get("claim") or "")[:180],
                "reason": (c.get("reason") or "")[:220],
                "tool_hint": sorted(tool_names & set((c.get("reason") or "").split())),
            }
            if cls == "confirmed":
                confirmed.append(row)
            elif cls == "suspect":
                suspect.append(row)
    return {
        "tree": str(tree),
        "present": True,
        "summary": dict(status_counts),
        "confirmed": confirmed,
        "suspect": suspect,
    }


def _tool_names_in_tree(tree: Path) -> set:
    return _tool_names(tree)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing report trees (default: reports/).",
    )
    parser.add_argument(
        "--tree", default=None, help="Scan a single report tree instead of the whole dir."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON instead of the table."
    )
    parser.add_argument(
        "--confirm-only",
        action="store_true",
        help="Show only CONFIRMED claims (skip SUSPECT).",
    )
    args = parser.parse_args()

    root = Path(args.tree) if args.tree else Path(args.reports_dir)
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2

    trees: list[Path] = [root] if args.tree else sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "verify_flags.json").exists()
    )
    if not trees:
        print(f"no report trees with verify_flags.json under {root}")
        return 0

    results = [_sweep_tree(t) for t in trees]
    n_confirmed = sum(len(r["confirmed"]) for r in results)
    n_suspect = sum(len(r["suspect"]) for r in results)

    if args.json:
        print(json.dumps({"trees": results, "confirmed": n_confirmed, "suspect": n_suspect}, indent=2))
        return 1 if (n_confirmed or n_suspect) else 0

    # Human table.
    print(f"=== verify sweep: {len(trees)} tree(s), {n_confirmed} confirmed / {n_suspect} suspect ===")
    for r in results:
        if not r["present"]:
            print(f"  {r['tree']}: no verify_flags.json")
            continue
        counts = " ".join(f"{k}={v}" for k, v in sorted(r["summary"].items()))
        print(f"\n[{r['tree']}]  {counts}")
        for c in r["confirmed"]:
            print(f"  CONFIRMED ({c['stem']}): {c['claim']}")
            print(f"      {c['reason']}")
        if not args.confirm_only:
            for c in r["suspect"][:15]:
                print(f"  SUSPECT   ({c['stem']}): {c['claim']}")
                print(f"      {c['reason']}")
            if len(r["suspect"]) > 15:
                print(f"  ... {len(r['suspect']) - 15} more suspect (adjudicate)")

    return 1 if (n_confirmed or n_suspect) else 0


if __name__ == "__main__":
    sys.exit(main())
