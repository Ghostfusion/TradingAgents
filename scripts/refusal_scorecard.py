#!/usr/bin/env python3
"""Per-gate save-to-miss scorecard over the H7 refusal ledger.

The refusal ledger is written in-run, one immutable row per candidate a gate
refused. Classification is a later, separate pass: it needs the price path that
followed each refusal, which by definition does not exist at decision time. So
this script is the read side - it loads the ledger, joins each row with the
forward closes supplied for its ``(symbol, as_of)``, classifies the refusal into
the paper's five tiers, and prints the per-gate taxonomy with its save-to-miss
ratio.

Every gate line carries its **event count** beside the ratio, and the ratio is a
conservative lower bound: the tie-break (missed beats saved) puts a refusal that
both saved capital and missed a run into ``missed-moon``. The taxonomy and the
discipline transfer from 2607.02830; its 3.7:1 figure does not - 13-22 day
windows, one chain, one deployment, one regime, and a headline tier its own
matched lifecycle test refuted.

``--classify-row`` / ``--classify-path`` expose the classification rule for a
single row, so the rule itself is externally testable (the deposit 2605.12151
argues for) rather than only observable through a report.

The forward closes are supplied as JSON rather than fetched here: the ledger is
the engine's record and the paths are the operator's input, and this script
makes no vendor call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.strategies.refusal_ledger import (  # noqa: E402
    DEFAULT_HORIZON,
    DEFAULT_MIN_EVENTS,
    TIERS,
    classify_refusal,
    gate_on,
    rows,
    save_to_miss_ratio,
    score_all,
)


def load_paths(path: str) -> dict:
    """``{(symbol, as_of): [closes]}`` from a ``{"SYMBOL|AS_OF": [...]}`` JSON file.

    The key is the row's own ``(symbol, as_of)`` identity. A key without the
    separator is skipped rather than guessed at.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for key, closes in (raw or {}).items():
        symbol, sep, as_of = str(key).partition("|")
        if not sep:
            continue
        out[(symbol, as_of)] = closes
    return out


def build_report(results_dir: str | None, closes_by_key: dict, *,
                 horizon: int = DEFAULT_HORIZON,
                 min_events: int = DEFAULT_MIN_EVENTS) -> dict:
    """The scorecard: ledger size, per-gate taxonomy, ratio + event count."""
    ledger = rows(results_dir)
    scored = score_all(closes_by_key, results_dir, horizon=horizon)
    report = save_to_miss_ratio(scored, min_events=min_events)
    report["ledger_rows"] = len(ledger)
    report["sampled_rows"] = sum(
        1 for r in scored if r.get("classification") is not None
    )
    report["unsampled_rows"] = report["ledger_rows"] - report["sampled_rows"]
    report["gate_on"] = gate_on()
    return report


def classify_one(row_path: str, closes_path: str, **kwargs) -> dict:
    """Classify ONE ledger row against an explicit close list (the rule, exposed)."""
    with open(row_path, encoding="utf-8") as fh:
        row = json.load(fh)
    with open(closes_path, encoding="utf-8") as fh:
        closes = json.load(fh)
    return classify_refusal(row, closes, **kwargs)


def render_text(report: dict) -> str:
    """The human-readable scorecard: one line per refusing gate."""
    lines = [
        "refusal ledger - per-gate save-to-miss (H7)",
        f"  ledger rows: {report.get('ledger_rows', 0)}"
        f"  sampled: {report.get('sampled_rows', 0)}"
        f"  unsampled: {report.get('unsampled_rows', 0)}"
        f"  writer gate: {'on' if report.get('gate_on') else 'off'}",
        f"  tie-break: {report.get('tie_break')} (the ratio is a lower bound)",
        "",
        f"  {'gate':<20} {'events':>7} {'saves':>6} {'misses':>7} {'flat':>6} "
        f"{'uncl.':>6} {'ratio':>8}  notes",
    ]
    gates = report.get("gates") or {}
    if not gates:
        lines.append("  (no refusals in the ledger)")
    for gate in sorted(gates):
        e = gates[gate]
        ratio = e.get("ratio")
        notes = []
        if e.get("underpowered"):
            notes.append(f"underpowered (< {e.get('min_events')} events)")
        if e.get("unavailable"):
            notes.append(str(e["unavailable"]))
        lines.append(
            f"  {gate:<20} {e['events']:>7} {e['saves']:>6} {e['misses']:>7} "
            f"{e['flat']:>6} {e['unclassifiable']:>6} "
            f"{(f'{ratio:.2f}' if ratio is not None else 'n/a'):>8}  "
            + "; ".join(notes)
        )
    lines.append("")
    lines.append("  tiers: " + ", ".join(TIERS))
    lines.append("  basis: " + str(report.get("basis") or ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--results-dir", default=None,
                        help="dir holding refusals.jsonl (default: ~/.tradingagents/logs)")
    parser.add_argument("--paths", default=None,
                        help="JSON {\"SYMBOL|AS_OF\": [forward closes, ...]}")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON,
                        help=f"forward window in bars (default: {DEFAULT_HORIZON})")
    parser.add_argument("--min-events", type=int, default=DEFAULT_MIN_EVENTS,
                        help=f"below this a gate is flagged underpowered "
                             f"(default: {DEFAULT_MIN_EVENTS})")
    parser.add_argument("--json", action="store_true", help="emit JSON, not text")
    parser.add_argument("--classify-row", default=None,
                        help="classify ONE ledger row from a JSON file (with --classify-path)")
    parser.add_argument("--classify-path", default=None,
                        help="JSON list of forward closes for --classify-row")
    args = parser.parse_args(argv)

    if args.classify_row:
        if not args.classify_path:
            parser.error("--classify-row needs --classify-path")
        scored = classify_one(args.classify_row, args.classify_path,
                              horizon=args.horizon)
        print(json.dumps(scored, indent=2, sort_keys=True, default=str))
        return 0

    if not args.paths:
        parser.error("--paths is required (or use --classify-row)")
    report = build_report(args.results_dir, load_paths(args.paths),
                          horizon=args.horizon, min_events=args.min_events)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_report",
    "classify_one",
    "load_paths",
    "main",
    "render_text",
]
