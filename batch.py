"""Batch run TradingAgents over several symbols concurrently.

Usage examples:
    py -3.12 batch.py --symbols NVDA MSFT AAPL
    py -3.12 batch.py --symbols NVDA MSFT AAPL 0700.HK BTC-USD --date 2026-07-22 --workers 4
    py -3.12 batch.py --symbols NVDA --depth deep --analysts market news

Configuration (llm_provider, OpenRouter models, API key) is inherited from
.env via tradingagents/__init__.py + default_config.py — no code changes needed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.dataflows.symbol_utils import crypto_base

# All four analyst teams, in the CLI's execution order. This mirrors the
# interactive checkbox's "select all" so batch runs match the CLI default.
ALL_ANALYSTS = ("market", "social", "news", "fundamentals")

# Research depth -> debate/risk round counts. Same values the interactive
# CLI's Shallow / Medium / Deep options use (cli/utils.py DEPTH_OPTIONS).
DEPTH_LEVELS = {"shallow": 1, "medium": 3, "deep": 5}


def _per_symbol_memory_path(symbol: str) -> str:
    """Per-worker decision log, keyed on the (path-safe) symbol.

    Keeps each worker's memory writes isolated so concurrent reflection
    read-modify-write cycles can't interleave in one shared file. Same
    directory as the default trading_memory.md, but one file per symbol.
    """
    base = Path(DEFAULT_CONFIG["memory_log_path"]).expanduser()
    return str(base.parent / f"{safe_ticker_component(symbol)}.md")


def analyze(symbol: str, trade_date: str, analysts: tuple[str, ...], depth: int):
    """Run one symbol end-to-end with its own graph instance (thread-safe).

    Returns a ``(symbol, decision, report_dir, wall_seconds, rating)`` tuple so
    the caller can write a machine-readable summary line.
    """
    started = time.monotonic()
    config = DEFAULT_CONFIG.copy()
    # DEFAULT_CONFIG.copy() is a shallow copy — the nested data_vendors dict is
    # shared with the module global, so give this worker its own copy before
    # mutating it (otherwise a crypto override would leak into other symbols).
    config["data_vendors"] = dict(config["data_vendors"])
    config["memory_log_path"] = _per_symbol_memory_path(symbol)
    # Research depth controls both the bull/bear debate rounds and the
    # risk-debate rounds, exactly as the interactive CLI maps them.
    config["max_debate_rounds"] = depth
    config["max_risk_discuss_rounds"] = depth

    # Crypto has no fundamentals and no earnings, so sell-side ratings and the
    # earnings calendar are meaningless there — disable them to skip wasted
    # Finnhub calls. ("none" is the router's disable sentinel.)
    if crypto_base(symbol):
        config["data_vendors"]["analyst_ratings"] = "none"
        config["data_vendors"]["earnings_calendar"] = "none"

    # Fresh instance per worker: propagate() mutates self.ticker/curr_state,
    # so a single shared instance would race across threads.
    ta = TradingAgentsGraph(
        selected_analysts=analysts,
        debug=False,
        config=config,
    )
    final_state, decision = ta.propagate(symbol, trade_date)
    wall_seconds = round(time.monotonic() - started, 2)

    # Extract the 5-tier rating deterministically (same helper the graph uses).
    from tradingagents.agents.utils.rating import parse_rating
    rating = parse_rating(final_state.get("final_trade_decision", decision))

    # Save using the CLI's original folder + naming convention:
    #   ./reports/<TICKER>_<YYYYMMDD_HHMMSS>/...  (no prompt)
    report_dir = (
        Path.cwd() / "reports"
        / f"{safe_ticker_component(symbol).upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    ta.save_reports(final_state, symbol, save_path=report_dir)
    return symbol, decision, report_dir, wall_seconds, rating


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols", nargs="+", required=True,
        help="One or more tickers, e.g. NVDA MSFT 0700.HK BTC-USD",
    )
    parser.add_argument(
        "--date", default=date.today().isoformat(),
        help="Analysis date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help="How many symbols to analyze concurrently (default: 3)",
    )
    parser.add_argument(
        "--analysts", nargs="+", default=list(ALL_ANALYSTS),
        choices=ALL_ANALYSTS,
        help="Analyst teams to run (default: all four).",
    )
    parser.add_argument(
        "--depth", choices=list(DEPTH_LEVELS), default="deep",
        help="Research depth: shallow(1) / medium(3) / deep(5) rounds "
             "(default: deep).",
    )
    args = parser.parse_args()

    symbols = args.symbols
    analysts = tuple(args.analysts)
    depth = DEPTH_LEVELS[args.depth]
    print(f"Running {len(symbols)} symbol(s) on {args.date} "
          f"with {args.workers} worker(s) | depth={args.depth} | "
          f"analysts={','.join(analysts)}...")

    results = []
    summary_path = Path.cwd() / "reports" / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(analyze, s, args.date, analysts, depth): s
            for s in symbols
        }
        for fut in as_completed(futures):
            symbol = futures[fut]
            try:
                sym, decision, report_dir, wall_seconds, rating = fut.result()
                results.append((sym, decision, report_dir))
                print(f"[done] {sym} -> {decision}")
                print(f"       report: {report_dir}")
                # Append one JSON line per completed symbol (thread-safe enough
                # here since the main thread is the only writer).
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "symbol": sym,
                        "date": args.date,
                        "rating": rating,
                        "decision": decision,
                        "report_dir": str(report_dir),
                        "wall_seconds": wall_seconds,
                        "depth": args.depth,
                        "analysts": list(analysts),
                        "llm_provider": DEFAULT_CONFIG["llm_provider"],
                        "deep_think_llm": DEFAULT_CONFIG["deep_think_llm"],
                        "quick_think_llm": DEFAULT_CONFIG["quick_think_llm"],
                    }) + "\n")
            except Exception as exc:  # keep other symbols running on failure
                print(f"[failed] {symbol}: {exc!r}", file=sys.stderr)
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "symbol": symbol,
                        "date": args.date,
                        "error": repr(exc),
                        "depth": args.depth,
                        "analysts": list(analysts),
                    }) + "\n")

    print("\n=== Summary ===")
    for sym, decision, _ in results:
        print(f"{sym}: {decision}")
    print(f"\n{len(results)}/{len(symbols)} completed.")
    print(f"Batch log: {summary_path}")
    return 0 if len(results) == len(symbols) else 1


if __name__ == "__main__":
    raise SystemExit(main())
