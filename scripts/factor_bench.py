#!/usr/bin/env python3
"""Vibe-Trading alpha-bench mirror (P2-6): bench factor expressions offline.

    py -3.12 scripts/factor_bench.py --expr "pct_change(close,5)" --days 250
    py -3.12 scripts/factor_bench.py --zoo-file zoo.csv --symbol AAPL

Pure + offline (no LLM): evaluates each gated expression against a symbol's
OHLCV via the vendor chain and prints rank-IC vs forward returns. The
purity gate rejects anything outside the safe operator menu.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _fetch_records(symbol: str, days: int) -> list[dict]:
    from scripts.backtest_strategy import fetch_bars

    bars = fetch_bars(symbol, days) or []
    return [{"open": b.open, "high": b.high, "low": b.low,
             "close": b.close, "volume": getattr(b, "volume", 0.0)}
            for b in bars]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expr", default=None, help="single expression to bench")
    parser.add_argument("--zoo-file", default=None, help="CSV with one expr per line/column 'expr'")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--days", type=int, default=250)
    parser.add_argument("--fwd", type=int, default=1, help="forward-return days for rank IC")
    parser.add_argument("--walk-forward", action="store_true",
                        help="report mean IC across rolling train/test folds (W2-3)")
    parser.add_argument("--cpcv", type=int, default=0, metavar="FOLDS",
                        help="run combinatorial purged CV and flag overfit (W2-2)")
    parser.add_argument("--n-trials", type=int, default=1,
                        help="factors tried; >1 deflates the IC/Sharpe (W2-1)")
    args = parser.parse_args(argv)

    from tradingagents.strategies.alpha_zoo import bench_zoo, purity_gate

    exprs: list[str] = []
    if args.expr:
        exprs = [args.expr]
    elif args.zoo_file:
        p = Path(args.zoo_file)
        if not p.is_file():
            print(f"[err] no zoo file {p}", file=sys.stderr)
            return 2
        with open(p, encoding="utf-8") as fh:
            rows = csv.DictReader(fh)
            exprs = [r["expr"] for r in rows if r.get("expr")]
    else:
        # built-in minizoo: the pure ops are all gated + valid
        exprs = ["close", "pct_change(close, 1)", "delta(close, 1)",
                 "zscore(mean(close, 5), 10)", "rank(close)", "volume"]

    bad = [e for e in exprs if not purity_gate(e)[0]]
    if bad:
        print("[err] expressions failed the purity gate:", bad, file=sys.stderr)
        return 3

    recs = _fetch_records(args.symbol, args.days)
    if not recs:
        print("[err] no OHLCV for", args.symbol, file=sys.stderr)
        return 4

    out = bench_zoo(exprs, recs, forward_days=args.fwd, n_trials=args.n_trials,
                    walk_forward=args.walk_forward, cpcv_folds=args.cpcv)
    print(f"== alpha bench {args.symbol} fwd={args.fwd}d ==")
    hdr = f"{'expr':<30}{'IC':<8}{'OOS':<8}{'WF':<8}{'CPCV':<7}{'defIC':<8}error"
    print(hdr)
    for o in out:
        def _fmt(v):
            return "n/a" if v is None else f"{v:.3f}"
        cpcv = "overfit" if o.get("cpcv_overfit") else ("ok" if o.get("cpcv_overfit") is not None else "-")
        print(f"{o['expr']:<30}{_fmt(o['rank_ic']):<8}{_fmt(o.get('oos_rank_ic')):<8}"
              f"{_fmt(o.get('wf_ic')):<8}{cpcv:<7}{_fmt(o.get('deflated_ic')):<8}{o['error'] or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
