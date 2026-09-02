"""Combine broker position CSVs into the TRADINGAGENTS_RISK_BASKET_* .env keys.

Reads every ``*.csv`` under ``positions/`` (or ``--positions DIR``), merges
all accounts, computes weights AS A FRACTION OF THE WHOLE BOOK (positions +
cash), and - with ``--apply`` - rewrites the two basket lines in ``.env`` in
place (other lines untouched, a ``.env.bak`` backup first). ``--write-book-json``
persists the dollar book to ``positions/book_value.json`` so a future
execution layer can read real dollars without re-parsing CSVs.

Sensitive: position files and the book JSON are gitignored (``positions/``);
the script prints values only to stdout / writes only to ``.env`` + the
ignored JSON, never into a tracked file. ``--exclude SYM`` never removes the
line's *name* from dry-run output - it drops it from the emitted weight map
so a ticker you do not want in the basket (e.g. a single-name hedge) is
excluded from the gate, not hidden.

Run shape:
    py -3.12 scripts/positions_to_basket.py            # dry-run: summary, no writes
    py -3.12 scripts/positions_to_basket.py --apply    # rewrite .env (backup first)
    py -3.12 scripts/positions_to_basket.py --apply --write-book-json
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

from tradingagents.dataflows.utils import repo_root
from tradingagents.strategies.book_positions import (
    book_stats,
    compute_weights,
    patch_env_text,
    render_env_basket,
)

REPO = repo_root()
POSITIONS_DIR = REPO / "positions"
ENV_FILE = REPO / ".env"
BOOK_JSON = POSITIONS_DIR / "book_value.json"


def _discover(files: list[str], directory: pathlib.Path | None) -> list[pathlib.Path]:
    if files:
        out = []
        for f in files:
            p = pathlib.Path(f)
            if not p.is_file():
                p = REPO / f
            if not p.is_file():
                raise SystemExit(f"position csv not found: {f}")
            out.append(p)
        return out
    d = directory or POSITIONS_DIR
    found = sorted(d.rglob("*.csv")) if d.exists() else []
    if not found:
        raise SystemExit(f"no *.csv found under {d}")
    return found


def _load_rows(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _read_env() -> str:
    if not ENV_FILE.exists():
        raise SystemExit(f"{ENV_FILE} not found")
    return ENV_FILE.read_text(encoding="utf-8")


def _cli(argv: list[str] | None = None, _print=None) -> int:
    """Argparse-driven entry, importable for hermetic tests.

    ``_print`` optionally overrides the print target (captures JSON output in
    tests); the module globals ENV_FILE / BOOK_JSON / POSITIONS_DIR are read
    at call time, so tests monkeypatch them to run against temp paths.
    """
    print_ = _print or print
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--positions", type=pathlib.Path, default=None,
                    help="directory of position CSVs (default repo positions/)")
    ap.add_argument("files", nargs="*", help="explicit CSV file(s)")
    ap.add_argument("--apply", action="store_true",
                    help="rewrite TRADINGAGENTS_RISK_BASKET_* in .env (backup first)")
    ap.add_argument("--min-value", type=float, default=0.0,
                    help="drop positions worth less than this $ (dust filter)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="symbol to exclude from the emitted basket (repeatable); "
                         "affects --apply/--write-book-json only, not dry-run display")
    ap.add_argument("--write-book-json", action="store_true",
                    help="write the dollar book to positions/book_value.json (gitignored)")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args(argv)

    files = _discover(args.files, args.positions)
    by_account = {}
    for p in files:
        acct = p.parent.name if p.parent != REPO else p.name
        by_account[acct] = _load_rows(p)

    stats = book_stats(by_account)
    exclude = {s.upper() for s in args.exclude}
    keep = {s: v for s, v in stats["positions"].items() if s.upper() not in exclude}
    weights = compute_weights(keep, stats["cash_value"], min_value=args.min_value)
    tickers_line, weights_line = render_env_basket(weights)

    if args.json:
        payload = {
            "total_value": stats["total_value"],
            "cash_value": stats["cash_value"],
            "weights": weights,
            "tickers": list(weights),
            "skipped": stats["skipped"],
            "excluded": sorted(exclude),
        }
        if args.write_book_json:
            payload["book_json"] = str(BOOK_JSON)
        print_(json.dumps(payload, indent=2))
    else:
        print_(f"Books: {', '.join(by_account)}")
        print_(f"Total value: ${stats['total_value']:,.2f} | Cash: "
              f"${stats['cash_value']:,.2f} ({stats['cash_value'] / stats['total_value'] * 100:.1f}% of book)")
        for acct, a in stats["per_account"].items():
            print(f"  {acct}: {len(a['positions'])} positions, cash ${a['cash_value']:,.2f}, "
                  f"broker pct sum {a['broker_pct_sum']:.1f}% (cross-check)")
        print_("\nComputed basket weights (positions + cash denominator):")
        for sym, w in weights.items():
            marker = " (excluded from emit)" if sym in exclude else ""
            print(f"  {sym:8s} {w * 100:6.2f}%{marker}")
        print_(f"  (cash remainder: {100 - 100 * sum(weights.values()):5.2f}% - implicit)")
        for s in stats["skipped"]:
            print(f"skipped: {s}")

    if args.write_book_json:
        BOOK_JSON.parent.mkdir(parents=True, exist_ok=True)
        book = {
            "generated": __import__("datetime").date.today().isoformat(),
            "sources": [str(p) for p in files],
            "cash_value": stats["cash_value"],
            "total_value": stats["total_value"],
            "positions": {s: {"value": v, "weight": weights.get(s)} for s, v in keep.items()},
        }
        BOOK_JSON.write_text(json.dumps(book, indent=2), encoding="utf-8")
        if not args.json:
            print_(f"wrote {BOOK_JSON} (gitignored)")

    if args.apply:
        env = _read_env()
        # Path(".env").with_suffix() turns ".env" into ".env.env.bak" (leading-
        # dot names have no suffix) - append the backup marker to the filename.
        backup = ENV_FILE.with_name(f"{ENV_FILE.name}.bak")
        backup.write_text(env, encoding="utf-8")
        new_env = patch_env_text(env, tickers_line, weights_line)
        ENV_FILE.write_text(new_env, encoding="utf-8")
        print_(f"\n.env updated (backup: {backup.name})")
        print_(f"  TRADINGAGENTS_RISK_BASKET_TICKERS={tickers_line or '(none)'}")
        print_(f"  TRADINGAGENTS_RISK_BASKET_WEIGHTS={weights_line or '(none)'}")
    elif not args.json:
        print_("\nDry run - no changes. Re-run with --apply to update .env "
              "(and --write-book-json for the dollar book).")
    return 0


def main() -> int:
    """Console entry (also importable)."""
    return _cli()


if __name__ == "__main__":
    raise SystemExit(main())

