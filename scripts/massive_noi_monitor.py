"""Massive.com Net Order Imbalance (NOI) live monitor.

A standalone real-time monitor for NYSE auction order-imbalance events. This is
a **monitoring app**, not a batch-graph node: NOI is a live WebSocket stream, so
it does not fit the per-ticker ``route_to_vendor`` @tool contract that the
analyst graph uses.

Usage:
    py -3.12 scripts/massive_noi_monitor.py --tickers AAPL,MSFT,GME
    py -3.12 scripts/massive_noi_monitor.py --all       # every ticker (*)
    py -3.12 scripts/massive_noi_monitor.py -t AAPL --once

Entitlement: requires the Massive **Imbalances Expansion** add-on (not on the
free Basic plan). ``websocket-client`` must be installed.

Options:
    -t / --ticker   comma-separated tickers (repeatable)
    -a / --all      subscribe to all tickers (*)
    -o / --once     exit after one event (smoke test that the feed is live)
    --max-per-ticker N   stop after N events for a single ticker
    --ws-url URL    override the WebSocket endpoint
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-t", "--ticker", action="append", default=[], help="ticker (repeatable)")
    parser.add_argument("-a", "--all", action="store_true", help="subscribe to all tickers (*)")
    parser.add_argument("--once", type=int, default=None, metavar="N",
                        help="exit after N events (smoke test)")
    parser.add_argument("--max-per-ticker", type=int, default=None)
    parser.add_argument("--ws-url", default=None, help="override WebSocket endpoint")
    args = parser.parse_args(argv)

    if args.all:
        tickers = ["*"]
    elif args.ticker:
        tickers = [t.upper() for t in args.ticker]
    else:
        print("Provide --ticker AAPL,MSFT or --all.", file=sys.stderr)
        return 2

    from tradingagents.dataflows.massive_noi import describe, stream_noi

    def _on_event(ev):
        print(describe(ev), flush=True)

    try:
        n = stream_noi(
            tickers,
            _on_event,
            ws_url=args.ws_url,
            stop_after=args.once,
            max_per_ticker=args.max_per_ticker,
        )
    except RuntimeError as exc:
        print(f"NOI monitor unavailable: {exc}", file=sys.stderr)
        return 1
    print(f"\n[ticker] {n} NOI events received.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
