#!/usr/bin/env python3
"""Rebuild the consolidated complete_report.md for existing report folders.

Reads the per-section markdown files (``1_analysts/``, ``2_research/``,
``3_trading/``, ``4_risk/``, ``5_portfolio/``), reconstructs the run state
(preserving a leading ``### Risk Gate (computed)`` block when present), and
re-runs :func:`tradingagents.reporting.write_report_tree` so the consolidated
report gets the heading-demotion hierarchy — without re-running the analysis.

Usage:
    py -3.12 scripts/rebuild_complete_report.py reports/SFTBY_20260819_115450
    py -3.12 scripts/rebuild_complete_report.py reports/SFTBY_* reports/DELL_*
    py -3.12 scripts/rebuild_complete_report.py          # all report folders
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tradingagents.reporting import write_report_tree

_GATE_MARK = "### Risk Gate (computed)"
_GATE_END = "\n\n\n"

_ANALYST_FILES = (
    ("market_report", "1_analysts/market.md"),
    ("sentiment_report", "1_analysts/sentiment.md"),
    ("news_report", "1_analysts/news.md"),
    ("fundamentals_report", "1_analysts/fundamentals.md"),
)


def _read(dirpath: Path, rel: str) -> str:
    p = dirpath / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _split_gate(text: str) -> tuple[str | None, str]:
    """Split a leading risk-gate block from the raw content.

    Gate blocks were prepended as ``gate_block + "\\n\\n" + content``; the gate's
    own trailing newline means the boundary is the first ``\\n\\n\\n``.
    """
    idx = text.find(_GATE_END)
    if text.startswith(_GATE_MARK) and idx != -1:
        return text[: idx + 1], text[idx + len(_GATE_END) :]
    return None, text


def _parse_gate(gate_text: str) -> tuple[dict, dict]:
    """Parse the rendered gate back into ``risk_gate`` + extra state keys."""
    gate: dict = {}
    extra: dict = {}
    for line in gate_text.splitlines():
        if line.startswith("Verdict: "):
            v = line[len("Verdict: ") :].strip()
            gate["verdict"] = v.strip("*").strip()
        elif line.startswith("Reasons: "):
            gate["reasons"] = [r.strip() for r in line[len("Reasons: ") :].split(";") if r.strip()]
        elif line.startswith("Snapshot: "):
            extra["risk_snapshot"] = line[len("Snapshot: ") :].strip()
        elif line.startswith("Position contract: "):
            extra["position_contract"] = line[len("Position contract: ") :].strip()
        elif "RISK HALT ACTIVE" in line:
            extra["risk_halt"] = True
    return gate, extra


def rebuild_report(dirpath: Path) -> Path:
    """Regenerate the consolidated report for one folder; returns its path."""
    path = Path(dirpath)
    ticker = path.name.split("_")[0].lower()

    state: dict = {}
    for key, rel in _ANALYST_FILES:
        _, body = _split_gate(_read(path, rel))
        state[key] = body

    state["trader_investment_plan"] = _read(path, "3_trading/trader.md")

    debate: dict = {}
    for key, rel in (
        ("bull_history", "2_research/bull.md"),
        ("bear_history", "2_research/bear.md"),
        ("judge_decision", "2_research/manager.md"),
    ):
        _, body = _split_gate(_read(path, rel))
        debate[key] = body
    state["investment_debate_state"] = debate

    risk: dict = {}
    for key, rel in (
        ("aggressive_history", "4_risk/aggressive.md"),
        ("conservative_history", "4_risk/conservative.md"),
        ("neutral_history", "4_risk/neutral.md"),
    ):
        _, body = _split_gate(_read(path, rel))
        risk[key] = body
    gate_text, judge = _split_gate(_read(path, "5_portfolio/decision.md"))
    risk["judge_decision"] = judge
    state["risk_debate_state"] = risk

    if gate_text:
        gate, extra = _parse_gate(gate_text)
        if gate:
            state["risk_gate"] = gate
        state.update(extra)

    return write_report_tree(state, ticker, path, config={"risk_compact_report": False})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="*", help="Report folders; default: all under reports/")
    args = parser.parse_args()

    if args.dirs:
        dirs = [Path(d) for d in args.dirs]
    else:
        base = Path.cwd() / "reports"
        dirs = (
            sorted(d for d in base.iterdir() if d.is_dir() and (d / "1_analysts").exists())
            if base.is_dir()
            else []
        )

    if not dirs:
        print("No report folders found.", file=sys.stderr)
        return 1

    for d in dirs:
        try:
            out = rebuild_report(d)
            print(f"[ok] {d.name} -> {out}")
        except Exception as exc:  # noqa: BLE001 — keep rebuilding the others
            print(f"[failed] {d.name}: {exc!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
