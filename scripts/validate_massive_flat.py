"""Validate a Massive Flat-File day-aggregate CSV dropped into the screener's
bulk-history folder.

The value-screener's ``_fetch_ohlcv`` reads day-aggregate CSVs from
``massive_flat_dir`` (default ``data/massive_flat``) *only when*
``enable_massive_flat`` is ON. Use this script before / after dropping a file
to confirm it (a) parses in Massive's schema, (b) yields the expected symbol
row-counts, and (c) will actually be picked up by the screener (>=15 rows).

Usage:
    py -3.12 scripts/validate_massive_flat.py [folder] [--ticker AAPL,MSFT]
    py -3.12 scripts/validate_massive_flat.py data/massive_flat
    py -3.12 scripts/validate_massive_flat.py data/massive_flat -t AAPL,MSFT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _fmt(v) -> str:
    """Thousands-separated int or n/a."""
    if v is None:
        return "n/a"
    try:
        n = float(v)
        if n.is_integer():
            return f"{int(n):,}"
        return f"{n:,.1f}"
    except (TypeError, ValueError):
        return "n/a"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", default=None,
                        help="folder with the CSV(s); default = massive_flat_dir config")
    parser.add_argument("-t", "--ticker", nargs="*", default=[],
                        help="only report these symbols (repeatable, upper-cased)")
    parser.add_argument("--min-rows", type=int, default=15,
                        help="minimum close rows to be usable by the screener (default 15)")
    args = parser.parse_args(argv)

    from tradingagents.dataflows.config import get_config
    from tradingagents.dataflows.massive_flat import load_day_aggregates, ohlcv_for_ticker_dir

    cfg = get_config()
    folder = args.folder or cfg.get("massive_flat_dir") or "data/massive_flat"
    enabled = bool(cfg.get("enable_massive_flat"))

    folder_path = Path(folder)
    # Requested symbols, split on spaces/commas (argparse nargs="*" keeps each
    # `-t AAPL,MSFT` token together).
    requested = [
        t.upper()
        for p in args.ticker
        for t in p.split(",")
        if t.strip()
    ]
    print(f"folder      : {folder_path}")
    print(f"screener ON : {enabled}  (toggle must be true to read these files)")
    if not folder_path.is_dir():
        print(f"E: folder does not exist: {folder_path}")
        return 2

    csvs = sorted(folder_path.glob("*.csv"))
    if not csvs:
        print("no day-aggregates CSV found here (drop a Massive day-aggregates file).")
        return 0
    print(f"CSVs found  : {len(csvs)}")
    for c in csvs:
        print(f"  - {c.name} ({_fmt(c.stat().st_size)} bytes)")

    # Parse each CSV with the exact loader the screener uses, then summarize.
    ok = True
    for csv_path in csvs:
        print(f"\n== {csv_path.name} ==")
        series = load_day_aggregates(str(csv_path))
        if not series:
            print("  parse -> no tickers parsed; check header / column order")
            ok = False
            continue
        print(f"  tickers: {len(series):,}")
        # summarize a few / the requested ones.
        tickers = requested or list(series)[:6]
        for sym in tickers:
            b = series.get(sym)
            if not b:
                print(f"  {sym:8s} : NOT PRESENT")
                if sym in args.ticker:
                    ok = False
                continue
            n = len(b["closes"])
            dates = b.get("dates", [])
            lo, hi = (dates[0], dates[-1]) if len(dates) > 1 else ("", "")
            usable = n >= args.min_rows
            print(
                f"  {sym:8s} : {n} closes  [{lo}..{hi}]  "
                + (f"OK (>={args.min_rows})" if usable else "(too few for screener)")
            )
            if sym in requested and not usable:
                ok = False

    # Cross-check the screener's actual lookup for the requested tickers.
    if requested:
        print("\n== screener lookup check ==")
        for sym in requested:
            out = ohlcv_for_ticker_dir(str(folder_path), sym)
            n = len(out["closes"]) if out else 0
            usable = bool(out and n >= args.min_rows)
            print(
                f"  {sym.upper():8s} : ohlcv_for_ticker_dir -> {n} closes "
                f"{'(usable)' if usable else '(-)'}"
            )
            if not usable:
                ok = False

    print("\n" + ("result: READY for screener (toggle ON)" if ok else
                  "result: check CSV content / column order / ticker presence."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
