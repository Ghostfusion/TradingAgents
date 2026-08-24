#!/usr/bin/env python3
"""Compact per-ticker decision history (feature 4 of docs/pre_market_review.md).

Reads the machine-shaped run logs the graph writes
(``<results_dir>/<TICKER>/TradingAgentsStrategy_logs/full_states_log_*.json`` —
one file per trade date) and prints a compact series: date | rating | decision
summary | (risk-gate / tranche flags when present). This is the "prior decision
history" the Portfolio Manager's track record (memory log) only approximates —
it turns the on-disk log files into a reviewer/PM-friendly time series.

    py -3.12 scripts/decision_history.py EIX
    py -3.12 scripts/decision_history.py EIX --json
    py -3.12 scripts/decision_history.py EIX --max-days 30
    py -3.12 scripts/decision_history.py --all            # every ticker w/ logs

Exit codes: 0 ok, 3 no history found for the ticker.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _results_dir() -> str:
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get("results_dir") or os.path.expanduser("~/.tradingagents/logs")


def _rating(text: str) -> str:
    try:
        from tradingagents.agents.utils.rating import parse_rating

        return parse_rating(text, default="n/a")
    except Exception:  # noqa: BLE001
        return "n/a"


def _flags(state: dict) -> str:
    flags = []
    risk = (state.get("risk_gate") or {}).get("verdict")
    if risk:
        flags.append(f"risk={risk}")
    tc = state.get("tranche_context") or {}
    if tc:
        flags.append(f"peak={tc.get('peak_deployed_pct') or ''}")
    overlays = state.get("strategy_overlays") or {}
    if isinstance(overlays, dict) and (overlays.get("catalyst") or {}).get("verdict"):
        flags.append(f"cat={(overlays['catalyst'] or {}).get('verdict')}")
    return ", ".join(flags)


def history_for(ticker: str, results_dir: str | None = None) -> list[dict]:
    """Sorted (date asc) decision rows for one ticker; never raises.

    Searches BOTH the configured ``results_dir`` (the graph's
    ``full_states_log_<date>.json`` layout) and the batch ``reports/<SYM>_<ts>/``
    tree (which may embed a ``TradingAgentsStrategy_logs/`` folder when a run
    saved there). Ticker matching is case-insensitive so web input like ``msft``
    works.
    """

    roots = [results_dir] if results_dir else []
    if not results_dir:
        roots.append(_results_dir())
        # batch report folders live in the repo root reports/ (config.REPORTS_DIR)
        reports_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"
        )
        roots.append(reports_root)
    rows: list[dict] = []
    seen: set[str] = set()
    upper = (ticker or "").upper()
    for base in roots:
        if not base or not os.path.isdir(base):
            continue
        # 1) default layout: <base>/<TICKER>/TradingAgentsStrategy_logs
        logs = os.path.join(base, upper, "TradingAgentsStrategy_logs")
        for path in glob.glob(os.path.join(logs, "full_states_log_*.json")):
            rows += _parse_log(path, seen)
        # 2) batch layout: <base>/<SYM>_<ts>/TradingAgentsStrategy_logs (any case)
        for folder in os.listdir(base):
            if not folder.upper().startswith(upper + "_"):
                continue
            flogs = os.path.join(base, folder, "TradingAgentsStrategy_logs")
            if os.path.isdir(flogs):
                for path in glob.glob(os.path.join(flogs, "full_states_log_*.json")):
                    rows += _parse_log(path, seen)
        # 3) batch layout WITHOUT json logs: the report folders themselves carry
        #    the decision in 5_portfolio/decision.md — surface a row per folder
        #    (the graph's _log_state writes the JSON only to the default
        #    results_dir, which batch's ./reports saves don't populate).
        for folder in os.listdir(base):
            if not folder.upper().startswith(upper + "_"):
                continue
            decision_md = os.path.join(base, folder, "5_portfolio", "decision.md")
            if not os.path.isfile(decision_md):
                continue
            # derive a date from the folder stamp <TICKER>_YYYYMMDD_HHMMSS
            stamp = folder.split("_")[1] if "_" in folder else ""
            d = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}" if len(stamp) >= 8 else folder
            if d in seen:
                continue
            seen.add(d)
            text = ""
            try:
                with open(decision_md, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                text = ""
            rows.append(
                {
                    "date": d,
                    "rating": _rating(text),
                    "decision": next(
                        (ln.strip()[:120] for ln in text.splitlines() if ln.strip()),
                        "",
                    ),
                    "flags": "report-folder",
                }
            )
    return sorted(rows, key=lambda r: r["date"])


def _parse_log(path: str, seen: set[str]) -> list[dict]:
    """Parse one full_states_log JSON into a decision row; dedupe by (date)."""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return []
    d = state.get("trade_date") or Path(path).stem.replace("full_states_log_", "")
    if d in seen:
        return []
    seen.add(d)
    return [
        {
            "date": d,
            "rating": _rating(state.get("final_trade_decision") or ""),
            "decision": (state.get("final_trade_decision") or "").splitlines()[0]
            if state.get("final_trade_decision")
            else "",
            "flags": _flags(state),
        }
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols")
    parser.add_argument("--all", action="store_true", help="every ticker with logs")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--max-days", type=int, default=0, help="0 = all")
    parser.add_argument("--results-dir", default=None, help="override results_dir")
    args = parser.parse_args(argv)

    base = args.results_dir or _results_dir()
    if args.all:
        tickers = sorted(
            d.name
            for d in Path(base).iterdir()
            if d.is_dir() and (d / "TradingAgentsStrategy_logs").is_dir()
        )
    else:
        tickers = [t.upper() for t in args.tickers]
    if not tickers:
        print("nothing to show; pass tickers or --all", file=sys.stderr)
        return 2

    out_all = []
    rc = 0
    for t in tickers:
        # Pass None (not base) so history_for uses its full default search
        # (results_dir + repo reports/ tree). Only an explicit --results-dir
        # restricts the search (hermetic).
        rows = history_for(t, args.results_dir)
        if args.max_days > 0:
            rows = rows[-args.max_days :]
        if not rows:
            print(f"[{t}] no history", file=sys.stderr)
            rc = 3 if not args.all else rc
            continue
        if args.json:
            out_all.append({"ticker": t, "decisions": rows})
            continue
        print(f"== {t} ==")
        print(f"{'date':<14}{'rating':<12}{'flags':<40}decision")
        for r in rows:
            print(f"{r['date']:<14}{r['rating']:<12}{r['flags']:<40}{r['decision'][:60]}")
        print()
    if args.json:
        print(json.dumps(out_all, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
