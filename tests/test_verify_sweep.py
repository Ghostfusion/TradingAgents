"""Tests for the post-verifier adjudication workbench (scripts/verify_sweep.py).

AMZN 2026-09-09 loop item 3: surface "N confirmed misquotes / M unsupported"
per tree from existing verify_flags.json so the real defects are not buried in
a 47-claim dump.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import verify_sweep as S


def _write_flags(tree: Path, verification: dict) -> None:
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "verify_flags.json").write_text(
        json.dumps({"report_dir": str(tree), "model": "test", "verification": verification}),
        encoding="utf-8",
    )


def _flags_payload():
    return {
        "market": {
            "overall": "FLAG",
            "claims": [
                {
                    "claim": "T1(2R ahead) = 265.03",
                    "status": "MISQUOTED",
                    "reason": "anchored: figures ARE in tool evidence but the "
                    "claim may attach them to the wrong label - verify attribution",
                },
                {
                    "claim": "williams_r = -95.38",
                    "status": "CONTRADICTED",
                    "reason": "get_mean_reversion_tech [ok] gives williams_r=-92.31",
                },
                {
                    "claim": "VWMA 258.95",
                    "status": "GROUNDED",
                    "reason": "get_swing_set [ok]",
                },
            ],
        },
        "news": {
            "claims": [
                {
                    "claim": "10y Treasury 9.78%",
                    "status": "UNSUPPORTED",
                    "reason": "no leaf evidence for any Treasury/yield figure",
                },
                {
                    "claim": "polymarket 93%",
                    "status": "UNSUPPORTED",
                    "reason": "no leaf - prediction markets tool not called",
                },
            ]
        },
    }


def test_sweep_counts_confirmed_and_suspect(tmp_path):
    tree = tmp_path / "AMZN_20260909_TEST"
    _write_flags(tree, _flags_payload())
    (tree / "tool_evidence.json").write_text(
        json.dumps({"market": [{"tool": "get_swing_set", "status": "ok", "content": "x"}]}),
        encoding="utf-8",
    )
    r = S._sweep_tree(tree)
    assert r["present"] is True
    assert r["summary"]["MISQUOTED"] == 1
    assert r["summary"]["CONTRADICTED"] == 1
    assert r["summary"]["UNSUPPORTED"] == 2
    assert r["summary"]["GROUNDED"] == 1
    # Confirmed = MISQUOTED + CONTRADICTED (2 rows); suspect = UNSUPPORTED (2 rows).
    assert len(r["confirmed"]) == 2
    assert r["confirmed"][0]["claim"].startswith("T1")
    assert r["confirmed"][1]["claim"].startswith("williams_r")
    assert len(r["suspect"]) == 2


def test_sweep_missing_flags_reports_absent(tmp_path):
    r = S._sweep_tree(tmp_path)
    assert r["present"] is False
    assert r["confirmed"] == [] and r["suspect"] == []


def test_sweep_cli_json(tmp_path):
    tree = tmp_path / "AMZN_20260909_CLI"
    _write_flags(tree, _flags_payload())
    proc = subprocess.run(
        [sys.executable, str(Path("scripts/verify_sweep.py")), "--tree", str(tree), "--json"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 1  # confirmed/suspect present
    data = json.loads(proc.stdout)
    assert data["confirmed"] == 2
    assert data["suspect"] == 2


def test_sweep_cli_clean_exits_zero(tmp_path):
    tree = tmp_path / "CLEAN_20260909"
    _write_flags(
        tree,
        {"market": {"overall": "PASS", "claims": [{"status": "GROUNDED", "claim": "x", "reason": "y"}]}},
    )
    proc = subprocess.run(
        [sys.executable, str(Path("scripts/verify_sweep.py")), "--tree", str(tree), "--json"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0
