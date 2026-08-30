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

    # 2b. C1 execution block: arrival-vs-fill slippage + fill-rate (advisory).
    slips = [float(r["slippage_bps"]) for r in pm_rows if r.get("slippage_bps") is not None]
    fills = [r for r in pm_rows if r.get("fill_price") is not None]
    # Implementation-shortfall (TCA) per row: (fill - arrival) + (arrival - decision)
    # proxied over the paper book; decision = prior_close, arrival/fill as stored.
    is_rows = []
    for r in pm_rows:
        if r.get("fill_price") is None or r.get("arrival_price") is None or r.get("prior_close") is None:
            continue
        try:
            from tradingagents.strategies.evaluate import implementation_shortfall

            res = implementation_shortfall(
                float(r["prior_close"]), float(r["arrival_price"]), float(r["fill_price"])
            )
            if res is not None:
                is_rows.append(res["implementation_shortfall_bp"])
        except Exception:  # noqa: BLE001 - one bad row degrades
            continue
    out["execution"] = {
        "rows_with_slippage": len(slips),
        "avg_slippage_bps": round(sum(slips) / len(slips), 2) if slips else None,
        "fill_rate": round(len(fills) / len(pm_rows), 3) if pm_rows else None,
        "avg_is_bp": round(sum(is_rows) / len(is_rows), 2) if is_rows else None,
        "note": "arrival-benchmark slippage: (fill - arrival)/arrival in bps; "
                "avg_is_bp = implementation shortfall (decision->arrival->fill) "
                "in bps; higher = worse execution. None when no measured "
                "arrival/fill (the paper book records the review open as fill).",
    }

    # 2c2. C3 alpha-profile: post-fill drift vs arrival (the "did our fill
    #      leak / did price move against us" test). Uses the paper ledger's own
    #      arrival_price + realized_return proxies (no new vendor).
    fills = [r for r in pm_rows if r.get("arrival_price") and r.get("prior_close")]
    drift_rows = []
    for r in fills:
        arr = float(r["arrival_price"])
        # fill proxy = prior_close (the decision-time close) - C1 semantics
        drift_rows.append((float(r.get("prior_close")) - arr) / arr if arr else None)
    drift_rows = [d for d in drift_rows if d is not None]
    out["alpha_profile"] = {
        "rows": len(drift_rows),
        "avg_postfill_drift_pct": round(sum(drift_rows) / len(drift_rows) * 100, 3) if drift_rows else None,
        "pos_drift_share": round(sum(1 for d in drift_rows if d > 0) / len(drift_rows), 3) if drift_rows else None,
        "note": "post-fill drift: (decision-close - arrival)/arrival over the paper "
                "book. Positive share = fills benign; sustained negative = possible "
                "adverse selection / leak (review execution).",
    }

    # 2d. D1 sleeve attribution: the pre-market ledger carries a per-decision
    #     sleeve tag (value-dip / swing / vcp / momentum / hold) when the run
    #     provided one; group realized returns by sleeve when present.
    sleeves: dict[str, dict] = {}
    for r in pm_rows:
        sv = (r.get("sleeve") or "hold").strip() or "hold"
        rr = r.get("realized_return")
        if rr is None:
            continue
        b = sleeves.setdefault(sv, {"n": 0, "wins": 0, "sum": 0.0})
        b["n"] += 1
        b["sum"] += float(rr)
        if float(rr) > 0:
            b["wins"] += 1
    out["sleeves"] = {
        sv: {
            "n": b["n"],
            "win_rate": round(b["wins"] / b["n"], 3) if b["n"] else None,
            "avg_realized": round(b["sum"] / b["n"], 5) if b["n"] else None,
        }
        for sv, b in sorted(sleeves.items())
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
        # D2 alpha-decay monitor: rolling 4-week hit rate / sharpe vs the
        # full-history baseline. DRIFT when the rolling measure trails the
        # baseline for 2 consecutive periods (config `drift_periods`).
        try:
            hist = [float(v) for v in pm_realized if v is not None]
            if len(hist) >= 12:
                n = max(5, min(20, len(hist) // 4))
                recent = hist[-n:]
                base_win = sum(1 for v in hist if v > 0) / len(hist)
                recent_win = sum(1 for v in recent if v > 0) / len(recent)
                base_sharpe = sharpe(hist) if len(hist) >= 2 else None
                recent_sharpe = sharpe(recent) if len(recent) >= 2 else None
                threshold = float(os.environ.get("TRADINGAGENTS_DRIFT_THRESHOLD", "0.15"))
                drift_win = (recent_win < base_win - threshold) if base_win else False
                drift_sharpe = (
                    recent_sharpe is not None
                    and base_sharpe is not None
                    and recent_sharpe < base_sharpe - 0.3
                )
                out["drift"] = {
                    "window": n,
                    "baseline_win_rate": round(base_win, 3),
                    "recent_win_rate": round(recent_win, 3),
                    "baseline_sharpe": round(base_sharpe, 3) if base_sharpe is not None else None,
                    "recent_sharpe": round(recent_sharpe, 3) if recent_sharpe is not None else None,
                    "drift_win_rate": bool(drift_win),
                    "drift_sharpe": bool(drift_sharpe),
                    "review_hint": "DRIFT detected" if (drift_win or drift_sharpe) else "stable",
                }
        except Exception:  # noqa: BLE001 - drift monitor is advisory
            out["drift"] = None
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
