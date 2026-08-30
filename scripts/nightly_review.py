#!/usr/bin/env python3
"""Nightly pre-open review driver (feature 2 of docs/pre_market_review.md).

Reads the latest ``reports/batch_summary_*.jsonl`` from a close-time batch run
and runs the pre-market review (``scripts/pre_market_review.py``) once per
symbol before the next open, so one command reviews the whole batch instead of
one manual invocation per ticker.

    py -3.12 scripts/nightly_review.py                 # latest batch summary
    py -3.12 scripts/nightly_review.py --summary reports/batch_summary_<ts>.jsonl
    py -3.12 scripts/nightly_review.py --skip-llm --dry-run   # deterministic, no writes
    py -3.12 scripts/nightly_review.py --max-symbols 3

Exit codes: 0 all ok, 2 at least one REJECT (paper-book skip), 3 no summary,
4 a symbol's review errored (kept going).
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _latest_summary() -> str | None:
    from tradingagents.dataflows.utils import resolve_output_path

    matches = sorted(
        glob.glob(str(resolve_output_path("reports") / "batch_summary_*.jsonl")),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _load_pre_market_script():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre_market_review.py")
    spec = importlib.util.spec_from_file_location("pre_market_review_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default=None, help="explicit batch_summary_*.jsonl")
    parser.add_argument("--max-symbols", type=int, default=0, help="0 = all")
    parser.add_argument("--prior-date", default=None, help="prior trade date YYYY-MM-DD")
    parser.add_argument("--skip-llm", action="store_true", help="deterministic verdict only")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = parser.parse_args(argv)

    summary = args.summary or _latest_summary()
    if not summary:
        print("no reports/batch_summary_*.jsonl found", file=sys.stderr)
        return 3

    rows = []
    with open(summary, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue

    pm = _load_pre_market_script()
    reviews = [r for r in rows if r.get("report_dir") and not r.get("error")]
    if args.max_symbols > 0:
        reviews = reviews[: args.max_symbols]
    if not reviews:
        print(f"no completed symbols in {summary}", file=sys.stderr)
        return 3

    rejects = 0
    failed = 0
    for r in reviews:
        ticker = r.get("symbol") or ""
        if not ticker:
            continue
        print(f"[nightly] reviewing {ticker} ({r.get('report_dir')})")
        rc = pm.main(
            [
                "--ticker", ticker,
                "--report-dir", r.get("report_dir"),
                *( [] if args.prior_date is None else ["--prior-date", args.prior_date] ),
                *(["--skip-llm"] if args.skip_llm else []),
                *(["--dry-run"] if args.dry_run else []),
            ]
        )
        if rc == 2:
            rejects += 1
            print(f"[nightly]   REJECT: {ticker}")
        elif rc not in (0, 3):
            failed += 1
            print(f"[nightly]   error rc={rc} for {ticker}")

    print(f"[nightly] {len(reviews)} reviewed; {rejects} REJECT; {failed} errored")
    return 0 if not rejects and not failed else (2 if rejects else 4)


if __name__ == "__main__":
    raise SystemExit(main())
