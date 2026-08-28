#!/usr/bin/env python3
"""Strategy-quality report: honest metrics from the paper/realized ledgers.

Item 7 (industry practice): firms periodically grade a strategy on its actual,
post-cost track record before trusting it with more capital. This script reads
the two machine-shaped ledgers the framework already writes and reports the
metrics a firm would ask for:

  - the reflection ledger (strategy_ledger.jsonl) — per-analyst realized alpha
  - the pre-market paper-book ledger (pre_market_ledger.jsonl) — realized
    review returns (CONFIRM/REVISE/REJECT resolved against the open)

It computes, via ``strategies/evaluate.py`` (cost-aware, walk-forward aware):
  - realized returns series from the ledgers
  - net-of-cost cumulative / CAGR / Sharpe (liquid names default 10bps; pass
    ``--illiq`` to scale cost up)
  - max drawdown of the book
  - per-analyst win rate + mean alpha
  - pre-market reviewer win rate (resolved rows)

A scheduled run just wires this into a cron / nightly step; it never trades.

Examples:
    py -3.12 scripts/strategy_quality_report.py
    py -3.12 scripts/strategy_quality_report.py --data-dir ~/.tradingagents
    py -3.12 scripts/strategy_quality_report.py --json

Exit codes: 0 ok.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_data_dir() -> str:
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get("data_cache_dir") or os.path.expanduser("~/.tradingagents")


def _load_jsonl(path: str) -> list:
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def build_report(data_dir: str, cost_bps: float = 10.0) -> dict:
    """Collect ledger metrics into a dict; never raises.

    ``cost_bps`` is the one-way cost used to net the realized returns (default
    10bps = liquid; a higher value models an illiquid/impactful book).
    """
    from tradingagents.strategies.evaluate import (
        cagr,
        equity_curve,
        max_drawdown,
        net_returns,
        sharpe,
        total_return,
    )

    out = {"data_dir": data_dir, "ledgers": {}}

    # 1. Reflection ledger (per-analyst realized alpha).
    ref_path = os.path.join(data_dir, "strategy_ledger.jsonl")
    ref_rows = _load_jsonl(ref_path)
    analysts: dict[str, dict] = {}
    for r in ref_rows:
        a = r.get("analyst") or "?"
        delta = r.get("delta_r")
        if delta is None:
            continue
        bucket = analysts.setdefault(a, {"n": 0, "wins": 0, "sum": 0.0})
        bucket["n"] += 1
        bucket["sum"] += float(delta)
        if float(delta) > 0:
            bucket["wins"] += 1
    analyzed = {"rows": len(ref_rows), "by_analyst": {}}
    for a, b in sorted(analysts.items()):
        analyzed["by_analyst"][a] = {
            "n": b["n"],
            "win_rate": round(b["wins"] / b["n"], 3) if b["n"] else None,
            "mean_alpha": round(b["sum"] / b["n"], 4) if b["n"] else None,
        }
    out["ledgers"]["reflection"] = analyzed

    # 2. Pre-market paper-book ledger (realized review returns).
    pm_path = os.path.join(data_dir, "pre_market_ledger.jsonl")
    pm_rows = _load_jsonl(pm_path)
    pm_realized = [float(r["realized_return"]) for r in pm_rows if r.get("realized_return") is not None]
    wins = sum(1 for v in pm_realized if v > 0)
    out["ledgers"]["pre_market"] = {
        "rows": len(pm_rows),
        "resolved": len(pm_realized),
        "win_rate": round(wins / len(pm_realized), 3) if pm_realized else None,
        "avg_realized": round(sum(pm_realized) / len(pm_realized), 5) if pm_realized else None,
    }

    # 3. Whole-book net-of-cost metrics from the realized returns (pre-market
    #    book as the canonical series; flat 10bps default, scaled by --illiq).
    out["metrics"] = {"available": bool(pm_realized), "cost_bps": cost_bps}
    if pm_realized:
        net = net_returns(pm_realized, cost_bps=cost_bps)
        eq = equity_curve(net)
        out["metrics"].update(
            {
                "total_return": round(total_return(net), 4),
                "cagr": round(cagr(net), 4) if len(net) else None,
                "sharpe": round(sharpe(net), 3) if len(net) >= 2 else None,
                "max_drawdown": round(max_drawdown(eq), 4) if eq else None,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=None, help="ledger dir (default: config data_cache_dir)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--illiq", action="store_true",
                        help="scale net cost up to 50bps (illiquid / impact-heavy book)")
    args = parser.parse_args(argv)

    data_dir = args.data_dir or _default_data_dir()
    # Ensure the data dir is absolute so ledger paths resolve regardless of CWD.
    data_dir = os.path.abspath(os.path.expanduser(data_dir))
    cost_bps = 50.0 if args.illiq else 10.0
    report = build_report(data_dir, cost_bps=cost_bps)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    lines = ["# Strategy Quality Report", f"\nData dir: `{data_dir}`", ""]
    ref = report["ledgers"]["reflection"]
    lines.append(f"## Reflection ledger ({ref['rows']} realized outcomes)")
    for a, s in (ref.get("by_analyst") or {}).items():
        lines.append(f"- {a}: n={s['n']} win_rate={s['win_rate']} mean_alpha={s['mean_alpha']}")
    pm = report["ledgers"]["pre_market"]
    lines.append(f"\n## Pre-market paper-book ({pm['resolved']} resolved of {pm['rows']})")
    lines.append(f"- win_rate={pm['win_rate']} avg_realized={pm['avg_realized']}")
    m = report["metrics"]
    if m.get("available"):
        lines.append(f"\n## Book metrics (net of {m.get('cost_bps', 10.0):g}bps)")
        lines.append(
            f"- total_return={m['total_return']} sharpe={m['sharpe']} "
            f"max_drawdown={m['max_drawdown']}"
        )
    else:
        lines.append("\nNo realized pre-market rows yet — run pre-market reviews to populate.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
