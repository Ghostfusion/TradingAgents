"""Reproducibility check: run one symbol N times and measure verdict deviation.

The whole point of the D1-D3 work (judge ensemble, deterministic sampling,
free-text-fallback flag) is to collapse the same-data verdict flips (TSM
2026-09-07 produced Overweight -> Underweight -> Hold on identical 428.91
data). This script quantifies that deviation:

  - runs ``batch.analyze`` N times (same symbol/date, fresh graph each time),
  - extracts the parsed 5-tier rating from each produced decision,
  - prints every run's rating + the agreement / flip metrics.

Usage::
    py -3.12 scripts/repro_check.py --symbol tsm --runs 3 --workers 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from batch import analyze

_CONFIG_HASH_CACHE: dict = {}


def _config_hash() -> str:
    """One stable hash of the run-affecting config, so 'same input' is provable."""
    key = ("n/a",)
    if key in _CONFIG_HASH_CACHE:
        return _CONFIG_HASH_CACHE[key]
    from tradingagents.default_config import DEFAULT_CONFIG

    relevant = {
        k: DEFAULT_CONFIG[k]
        for k in (
            "llm_provider",
            "deep_think_llm",
            "quick_think_llm",
            "backup_llm",
            "temperature",
            "debate_temperature",
            "debate_judge_ensemble",
            "debate_judge_model",
            "debate_bull_model",
            "debate_bear_model",
            "debate_max_rounds",
            "max_debate_rounds",
            "max_risk_discuss_rounds",
            "openrouter_reasoning_effort",
        )
        if k in DEFAULT_CONFIG
    }
    h = hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:12]
    _CONFIG_HASH_CACHE[key] = h
    return h


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--analysts", nargs="+", default=["market", "social", "news", "fundamentals"])
    parser.add_argument("--depth", default="deep")
    args = parser.parse_args()

    from batch import DEPTH_LEVELS

    depth = DEPTH_LEVELS[args.depth]
    analysts = tuple(args.analysts)
    cfg_hash = _config_hash()
    print(f"repro-check {args.symbol} x{args.runs} @ config_hash={cfg_hash}")

    results = []
    for i in range(args.runs):
        symbol, decision, report_dir, wall, rating = analyze(
            args.symbol,
            args.date or __import__("datetime").date.today().isoformat(),
            analysts,
            depth,
        )
        results.append(rating)
        print(f"  run {i + 1}: rating={rating} | decision={decision!r} | {wall}s | {report_dir}")
        with open(Path(report_dir) / "run_card.json", encoding="utf-8") as fh:
            run_card = json.load(fh)
        print(f"    run_card config_hash={run_card.get('config_hash')}")

    from collections import Counter as _C

    counts = _C(results)
    top, top_n = counts.most_common(1)[0]
    agreement = round(top_n / len(results), 4)
    print("\n=== repro summary ===")
    print(f"ratings: {results}")
    print(f"agreement (top / n): {agreement}  ({top_n}/{len(results)} on {top})")
    print(f"config_hash: {_config_hash()}")
    return 0 if agreement == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
