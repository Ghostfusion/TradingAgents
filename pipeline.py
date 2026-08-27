#!/usr/bin/env python3
"""Cross-sectional pipeline: screen -> rank -> top-N -> batch analyze (B2).

Ties the value watchlist screener (scripts/value_screener.py) to the batch
runner (batch.py): one command goes from a universe (positional/file tickers,
or moomoo's top-losers / heat-proxy movers) to ranked picks, composite factor
scores, and full moomoo-driven TradingAgents reports with TOCs.

Flow:
  1. universe   - positional/file tickers, ``top-losers`` or ``heat-proxy``
  2. score      - value screens (value_screener engine) + composite rank
  3. select     - top-N by composite score (EY + momentum + 52w distance)
  4. run        - concurrent batch.analyze (per-symbol memory logs,
                  reports/<SYM>_<ts>/ layout, moomoo-first chains)
  5. summary    - reports/pipeline_<ts>.md (candidates + results, links to
                  each report) + pipeline_<ts>.jsonl

Usage:
    py -3.12 pipeline.py --universe top-losers --top 5
    py -3.12 pipeline.py -f universe.txt --top 5 --date 2026-08-19
    py -3.12 pipeline.py AAPL MSFT NVDA --top 2 --workers 4 --depth deep
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import batch

logger = logging.getLogger(__name__)

ALL_ANALYSTS = ("market", "social", "news", "fundamentals")
DEPTH_LEVELS = {"shallow": 1, "medium": 3, "deep": 5}
SCRIPT_DIR = Path(__file__).parent


def _load_screener():
    """Load scripts/value_screener.py as a module (scripts is not a package)."""
    path = SCRIPT_DIR / "scripts" / "value_screener.py"
    spec = importlib.util.spec_from_file_location("value_screener", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_universe(vs, args) -> list:
    tickers = []
    if args.universe == "top-movers-massive":
        try:
            from tradingagents.dataflows.massive import get_top_movers_massive

            direction = args.movers_direction
            rendered = get_top_movers_massive(direction, args.movers_count)
            # Rendered lines look like "- AAPL: 120.5 (1.2%)". Keep the ones
            # that parse as bare tickers; the plan-gated 'unavailable' line is
            # ignored and the pipeline falls back to positional tickers.
            for ln in rendered.splitlines():
                ln = ln.strip()
                if not ln.startswith("-"):
                    continue
                body = ln[1:].strip()
                sym = body.split(":")[0].strip().upper()
                if not sym or not sym.replace(".", "").isalnum():
                    continue
                if "unavailable" not in body.lower() and sym not in tickers:
                    tickers.append(sym)
        except Exception as exc:  # noqa: BLE001 - Massive plan-gated
            logger.warning("massive mover universe unavailable (%s)", exc)
    elif args.universe in ("top-losers", "heat-proxy"):
        try:
            from tradingagents.dataflows.moomoo import (
                get_hot_movers_moomoo,
                get_top_movers_moomoo,
            )

            market = "US" if args.universe == "heat-proxy" else args.market
            if args.universe == "heat-proxy":
                movers = get_hot_movers_moomoo(
                    count=args.movers_count, market=market, min_market_cap=args.min_mcap
                )
                movers = [
                    m for m in movers if m.get("change_ratio") is not None and m["change_ratio"] < 0
                ]
            else:
                movers = get_top_movers_moomoo(
                    sort_dir="losers",
                    count=args.movers_count,
                    market=market,
                    min_market_cap=args.min_mcap,
                )
            for m in movers[: args.movers_count * 4]:
                if vs._is_non_equity(m.get("name")):
                    continue
                sym = (m.get("symbol") or "").upper()
                if not sym:
                    continue
                price, pe, cap = m.get("cur_price"), m.get("pe_ttm"), m.get("market_cap")
                if args.price_min and (price is None or price < args.price_min):
                    continue
                if args.pe_max and (pe is None or not (0.0 < pe <= args.pe_max)):
                    continue
                if args.min_mcap and (cap is None or cap < args.min_mcap):
                    continue
                if sym not in tickers:
                    tickers.append(sym)
        except Exception as exc:  # noqa: BLE001 - moomoo unavailable
            logger.warning("mover universe unavailable (%s); using positional tickers", exc)
    if not tickers and args.tickers:
        tickers = list(dict.fromkeys(t.upper() for t in args.tickers))
    if not tickers and args.file:
        tickers = [
            ln.strip().upper()
            for ln in Path(args.file).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    return tickers


def _screen_and_rank(vs, tickers: list[str], run_date: str) -> list:
    """Value-screen each candidate and rank (earnings yield / EV-EBIT)."""
    results = []
    for sym in tickers:
        try:
            fin = vs.fetch_ticker(sym, run_date)
            row = vs.screen_ticker(sym, fin)
            if row.get("earnings_yield") is None and row.get("ev_ebit") is None:
                continue  # nothing quantifiable -> not a screenable candidate
            row["ticker"] = sym
            results.append(row)
        except Exception as exc:  # noqa: BLE001
            logger.warning("screen failed for %s: %s", sym, exc)
    return vs.rank_watchlist(results)


def _composite_picks(vs, ranked: list, top: int) -> list:
    """Score with the EY+momentum+52w composite and return the top-N rows."""
    closes_map = {}
    for r in ranked[: max(top * 5, 50)]:
        try:
            closes = vs._fetch_closes(r["ticker"])
            if len(closes) >= 70:
                closes_map[r["ticker"]] = closes
        except Exception:
            pass
    scores = vs.composite_scores(ranked, closes_map) or {}
    return sorted(ranked, key=lambda r: scores.get(r["ticker"]) or -1.0, reverse=True)[:top]


def _run_batch(picks: list, args) -> list:
    analysts = tuple(args.analysts)
    depth = DEPTH_LEVELS[args.depth]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(batch.analyze, r["ticker"], args.date, analysts, depth, args.vendor): r
            for r in picks
        }
        for fut in as_completed(futures):
            pick = futures[fut]
            try:
                sym, decision, report_dir, wall, rating = fut.result()
                results.append(
                    {
                        "ticker": sym,
                        "decision": decision,
                        "rating": rating,
                        "report_dir": str(report_dir),
                        "wall_seconds": wall,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - keep the rest running
                logger.error("analysis failed for %s: %r", pick["ticker"], exc)
                results.append({"ticker": pick["ticker"], "error": repr(exc)})
    return results


def _fmt(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def _write_summary(results, ranked, universe, args, stamp):
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    lines = [
        f"# Cross-Sectional Pipeline - {args.date}",
        "",
        f"Universe: {len(universe)} candidates ({args.universe}) — vendor={args.vendor}, "
        f"depth={args.depth}, analysts={','.join(args.analysts)}",
        "",
        "## Screened candidates (composite rank)",
        "| # | Ticker | EY | EV/EBIT | F | M | Z |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(ranked[: max(args.top, 10)], 1):
        lines.append(
            f"| {i} | {r.get('ticker', '')} | {_fmt(r.get('earnings_yield'))} | "
            f"{_fmt(r.get('ev_ebit'))} | {_fmt(r.get('fscore'))} | "
            f"{_fmt(r.get('mscore'))} | {_fmt(r.get('zscore'))} |"
        )
    lines += [
        "",
        "## Analysis results",
        "| Ticker | Rating | Decision | Report |",
        "| --- | --- | --- | --- |",
    ]
    for row in sorted(results, key=lambda x: x.get("ticker", "")):
        if "error" in row:
            lines.append(f"| {row['ticker']} | - | ERROR {row['error'][:60]} | - |")
        else:
            lines.append(
                f"| {row['ticker']} | {row.get('rating', '-')} | "
                f"{str(row.get('decision', ''))[:60]} | {row.get('report_dir', '-')} |"
            )
    body = "\n".join(lines) + "\n"
    md = out_dir / f"pipeline_{stamp}.md"
    md.write_text(body, encoding="utf-8")
    jl = out_dir / f"pipeline_{stamp}.jsonl"
    with jl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": args.date, "vendor": args.vendor, "results": results}) + "\n")
    return md, jl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("tickers", nargs="*", help="ticker symbols (fallback universe)")
    parser.add_argument("-f", "--file", help="universe file (one ticker per line)")
    parser.add_argument(
        "-u", "--universe", choices=("tickers", "top-losers", "heat-proxy", "top-movers-massive"), default="tickers"
    )
    parser.add_argument("--market", default="US")
    parser.add_argument("-n", "--movers-count", type=int, default=50)
    parser.add_argument(
        "--movers-direction",
        choices=("gainers", "losers"),
        default="losers",
        help="Direction for --universe top-movers-massive (default losers)",
    )
    parser.add_argument("--top", type=int, default=5, help="picks to analyze")
    parser.add_argument("--limit", type=int, default=0, help="max candidates to screen (0 = all)")
    parser.add_argument("-d", "--date", default=date.today().isoformat())
    parser.add_argument("--min-mcap", type=float, default=10e9)
    parser.add_argument("--price-min", type=float, default=15.0)
    parser.add_argument("--pe-max", type=float, default=40.0)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--analysts", nargs="+", default=list(ALL_ANALYSTS), choices=ALL_ANALYSTS)
    parser.add_argument("--depth", choices=list(DEPTH_LEVELS), default="deep")
    parser.add_argument("--vendor", choices=("default", "moomoo", "yfinance", "eodhd"), default="moomoo")
    args = parser.parse_args(argv)

    vs = _load_screener()
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()

    tickers = _build_universe(vs, args)
    if not tickers:
        print("No candidates in the universe.", file=sys.stderr)
        return 1
    limit = args.limit if args.limit and args.limit > 0 else len(tickers)
    print(f"[pipeline] universe: {len(tickers)} -> screening up to {limit}")
    ranked = _screen_and_rank(vs, tickers[:limit], args.date)
    print(f"[pipeline] {len(ranked)} screened candidates; selecting top {args.top}")
    picks = _composite_picks(vs, ranked, args.top)
    print("[pipeline] picks: " + ", ".join(r["ticker"] for r in picks))
    print(f"[pipeline] running batch analysis (vendor={args.vendor}, depth={args.depth})")
    results = _run_batch(picks, args)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md, jl = _write_summary(results, ranked, tickers, args, stamp)
    print(f"[pipeline] done in {time.time() - t0:.1f}s; summary: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
