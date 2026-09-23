"""Cross-run ledger for the security-context blocks (SC-9).

Design: ``docs/design_security_context.md`` §17. One run's classification is a
fact about one company; what a *layer* needs is the same fact across runs, so a
drift is visible before it reaches a decision. The classification is deterministic
and versioned, so it is checkable over time - and the check is cheap because every
number here comes from blocks the runs already wrote.

Follows ``scripts/coverage_scorecard.py``: a pure ``build_*`` over the trees, a
``render_text`` for humans, and a ``main`` with ``--json``. Read-only - it emits a
report, never an artefact, so running it cannot change a tree.

**What it is careful to distinguish.** A tree with no ``security_context`` is only
evidence that the gate was off if the tree is *older* than the gate; a tree whose
block is present but whose sector is empty is a genuinely unclassified company.
Those are different findings and the tallies keep them apart. Nothing here is a
score: the numbers are counts of what was classified, and how.

    py -3.12 scripts/security_context_ledger.py [--reports-dir reports]
                                               [--limit N] [--json]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_REPORTS_DIR = "reports"
CARD_NAME = "run_card.json"
BLOCK_KEY = "security_context"


def load_blocks(
    reports_dir: str = DEFAULT_REPORTS_DIR, *, limit: int | None = None
) -> list[tuple[str, dict | None, bool]]:
    """``(tree_name, block, card_read)`` per tree, newest first.

    ``card_read`` is False when the tree has no readable ``run_card.json`` - a
    malformed or absent card is NOT evidence about the gate, so it is counted
    separately rather than folded into "no block".
    """
    root = Path(reports_dir)
    if not root.is_dir():
        return []
    # Newest first by MTIME, not by name: a tree is named `TICKER_YYYYMMDD_HHMMSS`,
    # so sorting names would order by ticker and `--limit` would sample the
    # alphabet rather than the recent past.
    trees = [p for p in root.iterdir() if p.is_dir()]
    trees.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    if limit is not None:
        trees = trees[:limit]
    out: list[tuple[str, dict | None, bool]] = []
    for tree in trees:
        card = tree / CARD_NAME
        try:
            payload = json.loads(card.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append((tree.name, None, False))
            continue
        block = payload.get(BLOCK_KEY) if isinstance(payload, dict) else None
        out.append((tree.name, block if isinstance(block, dict) else None, True))
    return out


def build_ledger(reports_dir: str = DEFAULT_REPORTS_DIR, *, limit: int | None = None) -> dict:
    """Count what the runs classified, and how - never how well."""
    rows = load_blocks(reports_dir, limit=limit)
    trees = len(rows)
    unreadable = sum(1 for _, _, ok in rows if not ok)
    with_block = [b for _, b, ok in rows if ok and isinstance(b, dict)]
    absent = sum(1 for _, b, ok in rows if ok and b is None)

    status: Counter[str] = Counter()
    sector: Counter[str] = Counter()
    source: Counter[str] = Counter()
    version: Counter[str] = Counter()
    triggers: Counter[str] = Counter()
    promoted: Counter[str] = Counter()
    unclassified = sic_present = 0
    promotions_total = 0

    for block in with_block:
        status[str(block.get("status") or "unknown")] += 1
        version[
            f"matrix={block.get('matrix_version') or '-'} "
            f"triggers={block.get('trigger_version') or '-'}"
        ] += 1
        ctx = block.get("context") if isinstance(block.get("context"), dict) else {}
        canonical = ctx.get("sector_canonical")
        if canonical:
            sector[str(canonical)] += 1
        else:
            unclassified += 1
        src = ctx.get("sector_source")
        if src:
            source[str(src)] += 1
        if ctx.get("sec_sic"):
            sic_present += 1
        for theme, row in (block.get("theme_triggers") or {}).items():
            if isinstance(row, dict) and row.get("triggered"):
                triggers[str(theme)] += 1
        props = block.get("promoted_themes") or []
        promotions_total += len(props)
        for theme in props:
            promoted[str(theme)] += 1

    return {
        "reports_dir": str(reports_dir),
        "trees": trees,
        "unreadable_cards": unreadable,
        "with_block": len(with_block),
        "without_block": absent,
        "status": dict(sorted(status.items())),
        "unclassified": unclassified,
        "sec_sic_present": sic_present,
        "sector_canonical": dict(sorted(sector.items())),
        "sector_source": dict(sorted(source.items())),
        "versions": dict(sorted(version.items())),
        "theme_triggered": dict(sorted(triggers.items())),
        "theme_promoted": dict(sorted(promoted.items())),
        "promotions_total": promotions_total,
        "note": (
            "classification provenance only. A tree with no block is counted as "
            "'without_block' whether the gate was off or the tree predates it - "
            "the ledger cannot tell those apart, so it does not claim to. Nothing "
            "here scores a company or orders a theme."
        ),
    }


def render_text(ledger: dict) -> str:
    """The human-readable ledger."""
    lines: list[str] = []
    lines.append(f"Security-context ledger - {ledger['reports_dir']}")
    lines.append("")
    lines.append(
        f"trees: {ledger['trees']}  with block: {ledger['with_block']}  "
        f"without: {ledger['without_block']}  unreadable cards: {ledger['unreadable_cards']}"
    )
    if not ledger["with_block"]:
        lines.append("")
        lines.append(
            "no security_context blocks found. The gate is enable_security_context "
            "(default off, and every tree here may simply predate it)."
        )
        return "\n".join(lines)
    lines.append(
        f"unclassified: {ledger['unclassified']}  "
        f"sec_sic present: {ledger['sec_sic_present']}"
    )
    for title, key in (
        ("status", "status"),
        ("canonical sector", "sector_canonical"),
        ("sector source", "sector_source"),
        ("versions", "versions"),
        ("themes triggered", "theme_triggered"),
        ("themes promoted", "theme_promoted"),
    ):
        rows = ledger.get(key) or {}
        if not rows:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for name, count in sorted(rows.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {count:>5}  {name}")
    lines.append("")
    lines.append(f"promotions total: {ledger['promotions_total']}")
    lines.append(f"note: {ledger['note']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR,
                        help="dir holding the run trees (default: reports)")
    parser.add_argument("--limit", type=int, default=None,
                        help="read at most N trees, newest first")
    parser.add_argument("--json", action="store_true", help="emit JSON, not text")
    args = parser.parse_args(argv)

    ledger = build_ledger(args.reports_dir, limit=args.limit)
    if args.json:
        print(json.dumps(ledger, indent=2, sort_keys=True))
        return 0
    print(render_text(ledger))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BLOCK_KEY", "CARD_NAME", "DEFAULT_REPORTS_DIR", "build_ledger", "load_blocks", "main", "render_text"]
