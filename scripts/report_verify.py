"""Second-layer report-verification CLI (the LLM pass over the tool evidence).

Run against an EXISTING report tree (no live run): each analyst report
(1_analysts/*.md) + its tool_evidence.json leaves go through a grounded
verifier that returns per-claim verdicts (GROUNDED / UNSUPPORTED /
CONTRADICTED), then a deterministic numeric anchor reconciles the verdicts
with ``repro_check --evidence`` tolerance so the two gates never disagree.

Usage:
    py -3.12 scripts/report_verify.py --report-dir reports/MSTR_20260908_144143
    py -3.12 scripts/report_verify.py --report-dir <dir> --max-calls 8
    py -3.12 scripts/report_verify.py --report-dir <dir> --model <x> --provider openrouter

Exit code: 0 = every report PASS or UNKNOWN (unavailable); 1 = any FLAG.
Advisory: never edits reports; the verdict JSON is written to
verify_flags.json in the report tree.

Design: docs/design_report_verification_llm.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tradingagents.agents.utils.report_verifier import REPORT_STEMS, verify_report_dir


def _write_out(report_dir: str, payload: dict) -> Path:
    out = Path(report_dir) / "verify_flags.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, help="Path to one report tree.")
    parser.add_argument(
        "--model",
        default=None,
        help="Verifier model (default: TRADINGAGENTS_VERIFY_MODEL or quick tier).",
    )
    parser.add_argument(
        "--provider", default=None, help="Verifier provider (default: llm_provider)."
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=12,
        help="Max LLM calls (one per analyst report) before degrade (default: 12).",
    )
    parser.add_argument(
        "--stem",
        choices=list(REPORT_STEMS),
        help="Run a single analyst report stem (default: all present).",
    )
    args = parser.parse_args()

    report_dir = args.report_dir
    if not Path(report_dir).exists():
        print(f"report dir not found: {report_dir}", file=sys.stderr)
        return 2

    payload = verify_report_dir(
        report_dir,
        model=args.model,
        provider=args.provider,
        max_calls=args.max_calls,
        stems=(args.stem,) if args.stem else None,
    )
    out = _write_out(report_dir, payload)

    flags = 0
    print(f"report-verify: {report_dir}")
    debate = payload.get("debate") or {}
    if debate.get("degraded"):
        flags += 1
        reason = f" (reason: {debate['reason']})" if debate.get("reason") else ""
        print(
            "  debate        DEGRADED  the run card says the structured debate was "
            "enabled but 2_research/structured_debate.md is missing" + reason
        )
    elif debate.get("enabled") is True:
        print("  debate        OK        structured-debate evidence present")
    verification = payload.get("verification") or {}
    for stem in REPORT_STEMS:
        entry = verification.get(stem)
        if entry is None:
            continue
        overall = entry.get("overall", "UNKNOWN")
        nclaims = len(entry.get("claims") or [])
        bad = [
            c["claim"][:90]
            for c in entry.get("claims") or []
            if c.get("status") in ("UNSUPPORTED", "CONTRADICTED")
        ]
        print(f"  {stem:<13} {overall:<8} ({nclaims} claims)" + (f" FLAGS={bad}" if bad else ""))
        if overall == "FLAG":
            flags += 1

    print(f"verdicts written: {out}")
    print("(advisory; numeric parse shared with repro_check --evidence)")
    return 1 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main())
