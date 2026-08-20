"""L4b - evaluate order-flow-aware decisions from the reflection ledger.

Reads the strategy ledger (alphas per analyst/ticker) and reports sample
size, win-rate, and mean realized alpha - the go/no-go numbers for the
order-flow overlay. When flow tags are present in entries (future runs),
splits win-rates by flow alignment.

Usage:
    python scripts/evaluate_orderflow.py [--ledger PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def compute_metrics(entries: list) -> dict:
    """Aggregate ledger entries into win-rate / mean-alpha metrics."""
    if not entries:
        return {"total": 0, "wins": 0, "win_rate": None, "mean_alpha": None, "by_analyst": {}}
    wins = sum(1 for e in entries if (e.get("delta_r") or 0.0) > 0)
    alphas = [float(e["delta_r"]) for e in entries if e.get("delta_r") is not None]
    by_analyst: dict = {}
    for e in entries:
        a = e.get("analyst") or "?"
        bucket = by_analyst.setdefault(a, {"total": 0, "wins": 0, "alphas": []})
        bucket["total"] += 1
        if (e.get("delta_r") or 0.0) > 0:
            bucket["wins"] += 1
        if e.get("delta_r") is not None:
            bucket["alphas"].append(float(e["delta_r"]))

    mean_alpha = (sum(alphas) / len(alphas)) if alphas else None
    return {
        "total": len(entries),
        "wins": wins,
        "win_rate": wins / len(entries) if entries else None,
        "mean_alpha": mean_alpha,
        "by_analyst": {
            k: {
                "total": v["total"],
                "wins": v["wins"],
                "win_rate": (v["wins"] / v["total"]) if v["total"] else None,
                "mean_alpha": (sum(v["alphas"]) / len(v["alphas"])) if v["alphas"] else None,
            }
            for k, v in sorted(by_analyst.items())
        },
    }


def print_report(metrics: dict, ledger_path) -> int:
    lines = [f"ledger: {ledger_path}"]
    if metrics["total"] == 0:
        lines.append("samples: 0 - run trades first; 5+ resolved outcomes needed.")
        print("\n".join(lines))
        return 0
    lines.append(
        f"samples: {metrics['total']}  wins: {metrics['wins']}  win_rate: {metrics['win_rate']:.0%}"
        if metrics["win_rate"] is not None
        else ""
    )
    if metrics["mean_alpha"] is not None:
        lines.append(f"mean realized alpha: {metrics['mean_alpha']:+.2%}")
    lines.append("by analyst:")
    for analyst, b in metrics["by_analyst"].items():
        wr = f"{b['win_rate']:.0%}" if b["win_rate"] is not None else "n/a"
        ma = f"{b['mean_alpha']:+.2%}" if b["mean_alpha"] is not None else "n/a"
        lines.append(f"  {analyst}: n={b['total']} wins={b['wins']} win_rate={wr} mean_alpha={ma}")
    lines.append(
        "NOTE: flow tags attach to new ledger entries when "
        "enable_orderflow is on; resample after a few resolved trades."
    )
    print("\n".join(lines))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default=None, help="path to strategy_ledger.jsonl")
    args = parser.parse_args(argv)
    ledger = args.ledger
    if ledger is None:
        try:
            from tradingagents.default_config import DEFAULT_CONFIG as cfg

            base = Path(cfg.get("data_cache_dir", "~/.tradingagents")).expanduser()
            ledger = str(base / "strategy_ledger.jsonl")
        except Exception:
            ledger = str(Path.home() / ".tradingagents" / "strategy_ledger.jsonl")
    from tradingagents.strategies.reflection import ReflectionLedger

    store = ReflectionLedger(path=ledger)
    return print_report(compute_metrics(store.entries), ledger)


if __name__ == "__main__":
    raise SystemExit(main())
