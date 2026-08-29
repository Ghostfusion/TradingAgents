#!/usr/bin/env python3
"""Backtest a report's trade plan over daily OHLCV (advisory, analysis-only).

Replays a single entry -> stop/target plan through a deterministic walk of
daily bars, applying fee + slippage costs. The plan is read either from a
report folder's ``full_states_log_*.json`` (the stop / position scale the
strategy overlays computed) or from explicit ``--entry/--stop/--targets``.

This is an *evaluation* tool - it never emits orders and never changes the
graph. Use it to see how a report's suggested plan would have filled, not as a
promise of live results (daily-bar model, no queue-position realism).

    py -3.12 scripts/backtest_strategy.py --ticker NVDA --report-dir reports/NVDA_...
    py -3.12 scripts/backtest_strategy.py --entry 240 --stop 232 \\
        --targets 248,252 --quantity 100 --out backtest_aapl.csv
    py -3.12 scripts/backtest_strategy.py --ticker AAPL --bars 250 --fee-bps 5

Exit codes: 0 ok, 3 no report/plan found, 4 unusable OHLCV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.strategies import evaluate as ev  # noqa: E402
from tradingagents.strategies.backtest_engine import (  # noqa: E402
    Bar,
    OrderSide,
)
from tradingagents.strategies.backtest_models import make_cost_fn  # noqa: E402


def _results_dir() -> str:
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get("results_dir") or os.path.expanduser("~/.tradingagents/logs")


def find_state_log(ticker: str, report_dir: str | None, prior_date: str | None) -> dict | None:
    """Locate + load the newest full_states_log for ``ticker`` (or a folder)."""
    candidates: list[str] = []
    if report_dir:
        root = Path(report_dir)
        candidates = sorted(str(p) for p in root.glob("**/full_states_log_*.json"))
    else:
        base = Path(_results_dir()) / ticker
        candidates = sorted(str(p) for p in base.glob("**/full_states_log_*.json"))
    if not candidates:
        return None
    if prior_date:
        wanted = [c for c in candidates if prior_date in c]
        if wanted:
            candidates = wanted
    path = max(candidates, key=os.path.getmtime)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def extract_stop(contract_str: str | None) -> float | None:
    """``0.0% @ stop 181.3773 (kelly=...)`` -> 181.3773 (or None)."""
    if not contract_str:
        return None
    m = re.search(r"stop\s+([0-9.]+)", contract_str)
    return float(m.group(1)) if m else None


def fetch_bars(ticker: str, bars: int) -> list[Bar]:
    """Pull daily OHLCV through the vendor chain ('' -> no bars)."""
    from tradingagents.dataflows.interface import route_to_vendor

    end = date.today()
    start = end - timedelta(days=bars + 40)
    raw = route_to_vendor(
        "get_stock_data", ticker, start.isoformat(), end.isoformat()
    )
    if not raw:
        return []
    lines = raw.strip().splitlines()
    rows: list[tuple[float, float, float, float]] = []
    for ln in lines:
        if not ln or ln.lower().startswith(("date", "datetime", "timestamp")):
            continue
        parts = [p.strip() for p in ln.replace("\t", ",").split(",") if p.strip()]
        if len(parts) < 5:
            continue
        try:
            o, h, lo, c = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
        except (ValueError, IndexError):
            continue
        rows.append((o, h, lo, c))
    if len(rows) < 2:
        return []
    rows = rows[-bars:]
    return [Bar(i, o, h, lo, c) for i, (o, h, lo, c) in enumerate(rows)]


def backtest(bars: list[Bar], entry: float, stop: float, targets: list[float],
             qty: float, side: str, fee_bps: float, slippage_ticks: float) -> dict:
    """Replay a single entry -> stop/target plan over bars, honoring order.

    A long plan enters at ``entry`` when a bar's low first reaches it (a
    short when a bar's high reaches it), then exits at whichever of ``stop`` /
    ``targets`` the price touches first *after* entry. Returns fills + net PnL.
    """
    entry_side = OrderSide.BUY if side == "long" else OrderSide.SELL
    exit_side = OrderSide.SELL if side == "long" else OrderSide.BUY
    cost_fn = make_cost_fn(fee_bps=fee_bps)

    # Entry: first bar whose range reaches the plan price.
    entry_bar_i: int | None = None
    for i, bar in enumerate(bars):
        hit = (
            (entry_side == OrderSide.BUY and bar.low <= entry)
            or (entry_side == OrderSide.SELL and bar.high >= entry)
        )
        if hit:
            entry_bar_i = i
            break
    if entry_bar_i is None:
        entry_bar_i = 0
        entry = bars[0].close
    entry_px = entry
    if slippage_ticks:
        entry_px = entry * (1.0 + slippage_ticks) if entry_side == OrderSide.BUY else entry * (1.0 - slippage_ticks)

    # Exit: stop or the first target touched after entry.
    exit_bar_i = entry_bar_i
    exit_px = entry_px
    exit_label = "none"
    stop_px = stop
    for i in range(entry_bar_i, len(bars)):
        bar = bars[i]
        stop_hit = (
            (exit_side == OrderSide.SELL and bar.low <= stop_px)
            or (exit_side == OrderSide.BUY and bar.high >= stop_px)
        )
        if stop_hit:
            exit_bar_i, exit_px, exit_label = i, stop_px, "stop"
            break
        for tgt in targets[:2]:
            hit = (
                (exit_side == OrderSide.SELL and bar.high >= tgt)
                or (exit_side == OrderSide.BUY and bar.low <= tgt)
            )
            if hit:
                exit_bar_i, exit_px, exit_label = i, tgt, f"target{tgt:.2f}"
                break
        if exit_label != "none":
            break
        exit_px = bar.close
    if exit_label == "none":
        exit_bar_i, exit_px = len(bars) - 1, bars[-1].close

    gross = (exit_px - entry_px) * qty if side == "long" else (entry_px - exit_px) * qty
    cost = cost_fn(entry_px * qty, entry_side) + cost_fn(exit_px * qty, exit_side)
    return {
        "fills": [
            {"side": entry_side.value, "qty": qty, "price": entry_px, "bar": entry_bar_i},
            {"side": exit_side.value, "qty": qty, "price": exit_px, "bar": exit_bar_i},
        ],
        "entry_price": entry_px,
        "exit_price": exit_px,
        "exit_label": exit_label,
        "net_pnl": gross - cost,
        "gross_pnl": gross,
        "cost": cost,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ticker", default=None, help="ticker symbol (OHLCV + report lookup)")
    parser.add_argument("--report-dir", default=None, help="report folder with a full_states_log")
    parser.add_argument("--prior-date", default=None, help="prior trade date YYYY-MM-DD")
    parser.add_argument("--entry", type=float, default=None)
    parser.add_argument("--stop", type=float, default=None)
    parser.add_argument("--targets", default=None, help="comma list, e.g. 248,252")
    parser.add_argument("--quantity", type=float, default=100.0)
    parser.add_argument("--side", choices=["long", "short"], default="long")
    parser.add_argument("--bars", type=int, default=250)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-ticks", type=float, default=0.0)
    parser.add_argument("--out", default=None, help="write a CSV of the plan + fills")
    args = parser.parse_args(argv)

    ticker = args.ticker
    entry = args.entry
    stop = args.stop
    targets = [float(t) for t in (args.targets or "").split(",") if t.strip()] if args.targets else []

    state = None
    if entry is None or stop is None:
        if not ticker:
            print("[err] need --ticker (to auto-read a plan) or explicit --entry/--stop")
            return 3
        state = find_state_log(ticker, args.report_dir, args.prior_date)
        if state is None:
            print(f"[err] no full_states_log for {ticker} ({args.report_dir or 'newest'})")
            return 3
    if state is not None and stop is None:
        ov = state.get("strategy_overlays") or {}
        contract = ov.get("position_contract") if isinstance(ov, dict) else None
        if isinstance(contract, str):
            stop = extract_stop(contract)
        if stop is None:
            print("[err] report has no usable stop; pass --stop")
            return 3
        if entry is None:
            print("[muted] report gives a stop but no clean entry; pass --entry or I use last close")

    if not ticker:
        ticker = "PLAN"

    bars = fetch_bars(ticker, args.bars) if ticker != "PLAN" else None
    if bars is None or len(bars) < 2:
        print("[err] no usable OHLCV for", ticker)
        return 4
    if entry is None:
        entry = bars[-1].close
    if stop is None:
        print("[err] no stop determined; pass --stop")
        return 3

    result = backtest(bars, entry, stop, targets, args.quantity, args.side,
                      args.fee_bps, args.slippage_ticks)
    print(f"entry={result['entry_price']:.2f} stop={stop:.2f} targets={targets}")
    print(f"fills={result['fills']}")
    print(f"exit={result['exit_price']:.2f} ({result['exit_label']}) "
          f"gross={result['gross_pnl']:.2f} net={result['net_pnl']:.2f} "
          f"(fees+slippage={result['cost']:.2f})")
    rets = simple_return_series(len(bars), result["entry_price"], result["exit_price"])
    if rets:
        print(f"net_cagr~{ev.cagr(rets):.4f} sharpe~{ev.sharpe(rets):.3f}")

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["field", "value"])
            w.writerow(["symbol", ticker])
            w.writerow(["entry", result["entry_price"]])
            w.writerow(["stop", stop])
            w.writerow(["targets", ",".join(map(str, targets))])
            w.writerow(["side", args.side])
            w.writerow(["quantity", args.quantity])
            w.writerow(["entry_bar", result["fills"][0]["bar"]])
            w.writerow(["exit_price", result["exit_price"]])
            w.writerow(["exit_label", result["exit_label"]])
            w.writerow(["net_pnl", result["net_pnl"]])
        print("wrote", args.out)
    return 0


def simple_return_series(n: int, entry: float, exit_px: float) -> list[float]:
    """A one-trade return proxy for the stat printout (length = n bars)."""
    mid = (entry + exit_px) / 2.0
    if mid <= 0 or n <= 0:
        return []
    total = (exit_px - entry) / mid
    return [total / n] * n


if __name__ == "__main__":
    sys.exit(main())
