"""Batch run TradingAgents over several symbols concurrently.

Usage examples:
    py -3.12 batch.py --symbols NVDA MSFT AAPL
    py -3.12 batch.py --symbols NVDA MSFT AAPL 0700.HK BTC-USD --date 2026-07-22 --workers 4
    py -3.12 batch.py --symbols NVDA --depth deep --analysts market news
    py -3.12 batch.py --symbols NVDA MSFT --vendor moomoo
    py -3.12 batch.py --symbols NVDA MSFT --vendor yfinance

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

from tradingagents.dataflows.symbol_utils import crypto_base
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

#: Hard parallel-work cap. Moomoo's OpenD gateway allows at most 128 open
#: connections; each concurrent batch worker opens its own thread-local
#: OpenQuoteContext, so many workers pile up connections and the gateway
#: rejects new contexts ("The number of connections exceeds 128").
MAX_PARALLEL_WORKERS = 4


def effective_workers(requested: int) -> int:
    """Cap the requested worker count (env override sets the ceiling)."""
    import os

    cap = MAX_PARALLEL_WORKERS
    try:
        override = int(os.environ.get("TRADINGAGENTS_MAX_WORKERS", ""))
        if override > 0:
            cap = min(max(1, override), 32)
    except ValueError:
        pass
    return min(max(1, int(requested)), cap)

# All four analyst teams, in the CLI's execution order. This mirrors the
# interactive checkbox's "select all" so batch runs match the CLI default.
ALL_ANALYSTS = ("market", "social", "news", "fundamentals")

# Research depth -> debate/risk round counts. Same values the interactive
# CLI's Shallow / Medium / Deep options use (cli/utils.py DEPTH_OPTIONS).
DEPTH_LEVELS = {"shallow": 1, "medium": 3, "deep": 5}

# Vendor presets for --vendor: full data_vendors chains per category.
# ``default`` (no flag) leaves the .env / DEFAULT_CONFIG chains untouched.
VENDOR_PRESETS = {
    # Moomoo primary, with the established free vendors as fallbacks.
    "moomoo": {
        "core_stock_apis": "moomoo,yfinance",
        "technical_indicators": "moomoo,yfinance",
        "fundamental_data": "moomoo,yfinance",
        "news_data": "moomoo,yfinance",
        "macro_data": "moomoo,fred",
        "prediction_markets": "moomoo,polymarket",
        "analyst_ratings": "moomoo,finnhub",
        "earnings_calendar": "moomoo,finnhub",
        "options_data": "moomoo,yfinance",
        "sec_filings": "sec_edgar",
        "short_interest": "moomoo,yfinance",
        "exchange_symbols": "eodhd",
        # moomoo-only enrichment (Tier 1/2)
        "capital_flow": "moomoo",
        "smart_money": "moomoo",
        "economic_calendar": "moomoo",
        "fed_watch": "moomoo",
        "market_breadth": "moomoo",
        "revenue_breakdown": "moomoo",
        "corporate_actions": "moomoo",
        "earnings_catalyst": "moomoo",
        "institution_data": "moomoo",
        "earnings_surprise": "moomoo",
        "expected_move": "moomoo",
    },
    # Pure-yfinance stack (the pre-moomoo defaults).
    "yfinance": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
        "macro_data": "fred",
        "prediction_markets": "polymarket",
        "analyst_ratings": "finnhub",
        "earnings_calendar": "finnhub",
        "options_data": "yfinance",
        "sec_filings": "sec_edgar",
        "short_interest": "yfinance",
        "exchange_symbols": "eodhd",
        # moomoo-only enrichment: the yfinance preset disables them ("none"
        # is the router's disable sentinel, so no moomoo data is used).
        "capital_flow": "none",
        "smart_money": "none",
        "economic_calendar": "none",
        "fed_watch": "none",
        "market_breadth": "none",
        "revenue_breakdown": "none",
        "corporate_actions": "none",
        "earnings_catalyst": "none",
        "institution_data": "none",
        "earnings_surprise": "none",
        "expected_move": "none",
    },
    # EODHD-first OHLCV (daily bars; EOD plan 100k/day @ 1000/min). The
    # moomoo K-line quota (100 calls/7 days) is the screener's bottleneck, so
    # this preset puts EODHD first in the OHLCV + news + corporate-actions
    # chains and keeps the rest on the established free vendors.
    "eodhd": {
        "core_stock_apis": "eodhd,moomoo,yfinance",
        "technical_indicators": "moomoo,yfinance",
        "fundamental_data": "moomoo,yfinance",
        "news_data": "eodhd,yfinance",
        "macro_data": "fred",
        "prediction_markets": "polymarket",
        "analyst_ratings": "finnhub",
        "earnings_calendar": "finnhub",
        "options_data": "yfinance",
        "sec_filings": "sec_edgar",
        "short_interest": "yfinance",
        "exchange_symbols": "eodhd",
        "corporate_actions": "eodhd",
        # moomoo-only enrichment: disabled ("none" = router disable sentinel).
        "capital_flow": "none",
        "smart_money": "none",
        "economic_calendar": "none",
        "fed_watch": "none",
        "market_breadth": "none",
        "revenue_breakdown": "none",
        "earnings_catalyst": "none",
        "institution_data": "none",
        "earnings_surprise": "none",
        "expected_move": "none",
    },
    # Tiingo-as-fallback (additive): eodhd/moomoo/yfinance stay first for
    # OHLCV and fundamentals; Tiingo (free Starter tier, low caps) is a
    # final fallback and, via tiingo/market_snapshot, the IEX quote.
    "tiingo": {
        "core_stock_apis": "eodhd,moomoo,yfinance,tiingo",
        "technical_indicators": "moomoo,yfinance",
        "fundamental_data": "moomoo,yfinance,tiingo",
        "news_data": "eodhd,yfinance",
        "macro_data": "fred",
        "prediction_markets": "polymarket",
        "analyst_ratings": "finnhub",
        "earnings_calendar": "finnhub",
        "options_data": "yfinance",
        "sec_filings": "sec_edgar",
        "short_interest": "yfinance",
        "exchange_symbols": "eodhd",
        "corporate_actions": "eodhd",
        # moomoo-only enrichment: disabled ("none" = router disable sentinel).
        "capital_flow": "none",
        "smart_money": "none",
        "economic_calendar": "none",
        "fed_watch": "none",
        "market_breadth": "none",
        "revenue_breakdown": "none",
        "earnings_catalyst": "none",
        "institution_data": "none",
        "earnings_surprise": "none",
        "expected_move": "none",
    },
}


def _per_symbol_memory_path(symbol: str) -> str:
    """Per-worker decision log, keyed on the (path-safe) symbol.

    Keeps each worker's memory writes isolated so concurrent reflection
    read-modify-write cycles can't interleave in one shared file. Same
    directory as the default trading_memory.md, but one file per symbol.
    """
    base = Path(DEFAULT_CONFIG["memory_log_path"]).expanduser()
    return str(base.parent / f"{safe_ticker_component(symbol)}.md")


def analyze(
    symbol: str,
    trade_date: str,
    analysts: tuple[str, ...],
    depth: int,
    vendor: str = "default",
):
    """Run one symbol end-to-end with its own graph instance (thread-safe).

    Returns a ``(symbol, decision, report_dir, wall_seconds, rating)`` tuple so
    the caller can write a machine-readable summary line.  ``vendor`` applies a
    VENDOR_PRESETS data-vendors chain ("default" = leave .env chains alone).
    """
    started = time.monotonic()
    config = DEFAULT_CONFIG.copy()
    # DEFAULT_CONFIG.copy() is a shallow copy — the nested data_vendors dict is
    # shared with the module global, so give this worker its own copy before
    # mutating it (otherwise a crypto override would leak into other symbols).
    config["data_vendors"] = dict(config["data_vendors"])
    if vendor in VENDOR_PRESETS:
        config["data_vendors"].update(VENDOR_PRESETS[vendor])
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
        # Tier 1/2 enrichment tools are meaningless for crypto (no segments,
        # no earnings catalysts, no corporate actions, no ARK holdings).
        for tier_key in (
            "smart_money",
            "revenue_breakdown",
            "corporate_actions",
            "earnings_catalyst",
        ):
            config["data_vendors"][tier_key] = "none"

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
        Path.cwd()
        / "reports"
        / f"{safe_ticker_component(symbol).upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    ta.save_reports(final_state, symbol, save_path=report_dir)
    return symbol, decision, report_dir, wall_seconds, rating


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="One or more tickers, e.g. NVDA MSFT 0700.HK BTC-USD",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Analysis date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="How many symbols to analyze concurrently (default: 3)",
    )
    parser.add_argument(
        "--analysts",
        nargs="+",
        default=list(ALL_ANALYSTS),
        choices=ALL_ANALYSTS,
        help="Analyst teams to run (default: all four).",
    )
    parser.add_argument(
        "--depth",
        choices=list(DEPTH_LEVELS),
        default="deep",
        help="Research depth: shallow(1) / medium(3) / deep(5) rounds (default: deep).",
    )
    parser.add_argument(
        "--vendor",
        choices=["default", *VENDOR_PRESETS],
        default="default",
        help="Vendor chain preset: moomoo (moomoo-first with yfinance/finnhub/"
        "fred/polymarket fallbacks) or yfinance (pure-yfinance stack). "
        "default keeps the .env / DEFAULT_CONFIG chains. (default: default)",
    )
    args = parser.parse_args()

    symbols = args.symbols
    analysts = tuple(args.analysts)
    depth = DEPTH_LEVELS[args.depth]
    vendor = args.vendor
    workers = effective_workers(args.workers)
    print(
        f"Running {len(symbols)} symbol(s) on {args.date} "
        f"with {workers} worker(s) (requested {args.workers}; capped at "
        f"{MAX_PARALLEL_WORKERS} to stay under moomoo connection limits) | "
        f"depth={args.depth} | "
        f"vendor={vendor} | "
        f"analysts={','.join(analysts)}..."
    )

    results = []
    summary_path = (
        Path.cwd() / "reports" / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(analyze, s, args.date, analysts, depth, vendor): s for s in symbols}
        for fut in as_completed(futures):
            symbol = futures[fut]
            try:
                sym, decision, report_dir, wall_seconds, rating = fut.result()
                results.append((sym, decision, report_dir))
                print(f"[done] {sym} -> {decision}")
                print(f"       report: {report_dir}")
                # Same-night pre-market re-check (choice (a) of the design):
                # a catalyst/quality re-read of the just-written decision, not
                # a gap re-anchor (that is the pre-open standalone script).
                if DEFAULT_CONFIG.get("enable_pre_market_review"):
                    _batch_pre_market_check(sym, report_dir, args.date)
                # Append one JSON line per completed symbol (thread-safe enough
                # here since the main thread is the only writer).
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "symbol": sym,
                                "date": args.date,
                                "rating": rating,
                                "decision": decision,
                                "report_dir": str(report_dir),
                                "wall_seconds": wall_seconds,
                                "depth": args.depth,
                                "analysts": list(analysts),
                                "vendor": vendor,
                                "llm_provider": DEFAULT_CONFIG["llm_provider"],
                                "deep_think_llm": DEFAULT_CONFIG["deep_think_llm"],
                                "quick_think_llm": DEFAULT_CONFIG["quick_think_llm"],
                            }
                        )
                        + "\n"
                    )
            except Exception as exc:  # keep other symbols running on failure
                print(f"[failed] {symbol}: {exc!r}", file=sys.stderr)
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "symbol": symbol,
                                "date": args.date,
                                "error": repr(exc),
                                "depth": args.depth,
                                "analysts": list(analysts),
                                "vendor": vendor,
                            }
                        )
                        + "\n"
                    )

    print("\n=== Summary ===")
    for sym, decision, _ in results:
        print(f"{sym}: {decision}")
    print(f"\n{len(results)}/{len(symbols)} completed.")
    print(f"Batch log: {summary_path}")
    return 0 if len(results) == len(symbols) else 1


if __name__ == "__main__":
    raise SystemExit(main())


def _batch_pre_market_check(symbol: str, report_dir, trade_date: str) -> None:
    """Same-night pre-market re-check for one batch symbol (choice (a)).

    Runs right after ``save_reports``: a catalyst/quality re-read of the
    just-written decision using the deterministic arbiter
    (``strategies/pre_market.review_decision``) in same-night mode (catalyst
    snapshot only — no quote, no gap, no re-anchor; the pre-open gap/anchor
    path is the standalone ``scripts/pre_market_review.py``). Writes
    ``pre_market_review_<trade_date>.md`` next to the report. Best-effort:
    any failure is logged and never fails the batch symbol.
    """
    try:
        from tradingagents.strategies.catalyst import (
            build_catalyst_snapshot,
            fetch_catalyst_data,
        )
        from tradingagents.strategies.pre_market import load_prior_state, review_decision

        prior = load_prior_state(report_dir, results_dir=DEFAULT_CONFIG.get("results_dir"))
        decision_text = prior.get("decision_md") or ""
        if not decision_text:
            decision_text = (prior.get("state") or {}).get("final_trade_decision", "")
        snapshot = None
        try:
            data = fetch_catalyst_data(symbol, trade_date)
            if data is not None:
                snapshot = build_catalyst_snapshot(data, trade_date, DEFAULT_CONFIG)
        except Exception as exc:  # noqa: BLE001 - degrade like the router
            print(f"[pre-market] catalyst unavailable for {symbol}: {exc}")
        verdict = review_decision(catalyst_snapshot=snapshot)
        cat_line = (
            f"- catalyst: {verdict['catalyst']['verdict']} "
            f"scale {verdict['catalyst']['scale']:.2f}"
            if verdict.get("catalyst")
            else "- no measurable catalyst delta"
        )
        body = [
            f"# Pre-Market Review (same-night) — {symbol} ({trade_date})",
            "",
            f"**Prior decision**: {decision_text[:300]}",
            "",
            "## Measured deltas",
            cat_line,
            "",
            "## Deterministic verdict",
            f"**{verdict['verdict']}**",
            "; ".join(verdict["reasons"]),
            "",
        ]
        out = Path(report_dir) / f"pre_market_review_{trade_date}.md"
        out.write_text("\n".join(body), encoding="utf-8")
        print(f"[pre-market] {symbol}: {verdict['verdict']} -> {out}")
    except Exception as exc:  # noqa: BLE001 - never fail the batch symbol
        print(f"[pre-market] review skipped for {symbol}: {exc}")
