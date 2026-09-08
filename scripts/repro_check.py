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


def _print_evidence_diff(report_dirs) -> None:
    """Print per-run forced-tool evidence + a cross-run composition/status diff.

    Reads ``tool_evidence.json`` from each run's report tree (persisted by
    ``tradingagents.reporting`` when the deterministic gatherer ran). When the
    config has no forced tools the file is absent everywhere — say so so the
    user knows the check needs ``analyst_forced_tools`` set.
    """
    evidence: list[dict] = []
    for d in report_dirs:
        p = Path(d) / "tool_evidence.json"
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                evidence.append(json.load(fh))
        else:
            evidence.append(None)

    print("\n=== forced-tool evidence diff ===")
    if all(e is None for e in evidence):
        print("no tool_evidence.json in any run — analyst_forced_tools is off;")
        print("set it to diff the per-run tool composition.")
        return
    if any(e is None for e in evidence):
        print("WARNING: some runs have evidence, some don't — config changed mid-check?")

    # Build tool → {status: str, statuses per run} across analysts.
    from collections import Counter as _C

    rows: dict[str, list] = {}
    for run_i, ev in enumerate(evidence):
        if ev is None:
            continue
        for analyst_key, leaves in (ev or {}).items():
            for leaf in leaves:
                key = f"{analyst_key}:{leaf['tool']}"
                row = rows.setdefault(key, [None] * len(evidence))
                row[run_i] = leaf.get("status")

    if not rows:
        print("evidence files exist but are empty.")
        return

    status_counts = {k: _C(r for r in v if r) for k, v in rows.items()}
    print(f"{'tool':<52} " + " ".join(f"run{i + 1}" for i in range(len(evidence))))
    differing = []
    for key in sorted(rows):
        statuses = rows[key]
        cells = [f"{s or '-':>6}" for s in statuses]
        print(f"{key:<52} " + " ".join(cells))
        if len(_C(s for s in statuses if s)) > 1:
            differing.append(key)
    if differing:
        print("\nDIFFERING STATUS ACROSS RUNS:")
        for key in differing:
            print("  ", key, status_counts[key])
    else:
        print("\nall tool statuses identical across runs (composition + status stable)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--analysts", nargs="+", default=["market", "social", "news", "fundamentals"])
    parser.add_argument("--depth", default="deep")
    parser.add_argument(
        "--evidence",
        action="store_true",
        help=(
            "print the per-run forced-tool evidence (tool_evidence.json) and a "
            "cross-run composition/status diff, so 'did every run see the same "
            "tool set' is answerable from the saved reports"
        ),
    )
    args = parser.parse_args()

    from batch import DEPTH_LEVELS

    depth = DEPTH_LEVELS[args.depth]
    analysts = tuple(args.analysts)
    cfg_hash = _config_hash()
    print(f"repro-check {args.symbol} x{args.runs} @ config_hash={cfg_hash}")

    results = []
    report_dirs: list[str] = []
    for i in range(args.runs):
        symbol, decision, report_dir, wall, rating = analyze(
            args.symbol,
            args.date or __import__("datetime").date.today().isoformat(),
            analysts,
            depth,
        )
        results.append(rating)
        report_dirs.append(report_dir)
        print(f"  run {i + 1}: rating={rating} | decision={decision!r} | {wall}s | {report_dir}")
        with open(Path(report_dir) / "run_card.json", encoding="utf-8") as fh:
            run_card = json.load(fh)
        print(f"    run_card config_hash={run_card.get('config_hash')}")

    if args.evidence:
        _print_evidence_diff(report_dirs)

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
