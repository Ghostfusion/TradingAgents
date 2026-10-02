"""Hermetic tests for repro_check's analyst-figure grounding cross-check.

The `--evidence` figure cross-check flags decimal numbers in an analyst's
report that have no matching value in that run's `tool_evidence.json` - the
copy-garble class seen on QCOM 2026-09-07 news.md ('TGA 303.9->944B' for
903.9, 'CCC 0.51%' for 10.51, '7.6%' for 7.4%). Tolerance-matched, so a
legitimately rounded copy of a tool value passes.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.timeout(120)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_repro_check():
    spec = importlib.util.spec_from_file_location(
        "repro_check_under_test", _REPO_ROOT / "scripts" / "repro_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_float_tokens_extracts_decimals_only():
    rc = _load_repro_check()
    out = rc._float_tokens("TGA draw 303.9B; price 168.74; integer 5; CCC 0.51%")
    assert out == {303.9, 168.74, 0.51}


def test_matches_tolerance_grounds_rounded_copies():
    rc = _load_repro_check()
    refs = {151.0957, 903.9, 7.4, 10.51, 168.43}
    # Rounded copy of a tool value -> grounded, not flagged.
    assert rc._matches(151.10, refs)
    # Near-identical but distinct series (price vs 50-SMA) -> passes cheaply.
    assert rc._matches(168.74, refs)
    # The QCOM garble class -> flagged.
    assert not rc._matches(303.9, refs)   # TGA 903.9 -> "303.9"
    assert not rc._matches(0.51, refs)    # CCC 10.51 -> "0.51"
    assert not rc._matches(7.6, refs)     # implied move 7.4 -> "7.6"


def test_figure_cross_check_flags_garble_and_passes_grounded(tmp_path, capsys):
    rc = _load_repro_check()
    md_dir = tmp_path / "1_analysts"
    md_dir.mkdir()
    (md_dir / "news.md").write_text(
        "TGA draw 303.9B (was 903.9B); stop 151.10; price 168.74; ATR 5.97; "
        "EPS -0.49% est 2.22 rep 2.21",
        encoding="utf-8",
    )
    leaves = [
        {"tool": "get_tga_balance", "status": "ok",
         "content": "2026-09-02: 944.4B; 2026-09-03: 903.9B; draw 38.9B"},
        {"tool": "get_swing_set", "status": "ok",
         "content": "stop=151.0957 ATR=5.1243"},
        {"tool": "get_verified_market_snapshot", "status": "ok",
         "content": "atr=5.97\nclose=168.43"},
        {"tool": "get_earnings_calendar", "status": "ok",
         "content": "estimate=2.22; reported=2.21; surprise_pct=-0.49"},
    ]
    rc._figure_cross_check([str(tmp_path)], [{"news": leaves}])
    out = capsys.readouterr().out
    assert "news: 1 figure(s) with no matching tool-output value" in out
    assert "303.9" in out
    assert "151.1" not in out  # rounded stop is grounded, not listed


def test_engine_scorecard_figures_are_grounded_from_run_card(tmp_path, capsys):
    """A cited engine score must not be flagged - it is the run's OWN number.

    The scorecard reaches the analyst prompt through a block, not a tool call,
    so it is absent from tool_evidence.json in every form. Measured 2026-10-02:
    CB's TradeScore 60.43 was reported as ungrounded in all four analyst reports
    while its six sibling engines passed only because round numbers like 63.0 /
    75.0 / 47.0 happened to fall inside the ±0.5% tolerance. Any engine value
    without such a neighbour was a guaranteed false positive.
    """
    rc = _load_repro_check()
    md_dir = tmp_path / "1_analysts"
    md_dir.mkdir()
    (md_dir / "fundamentals.md").write_text(
        "TradeScore 60.43 (coverage 0.6)", encoding="utf-8"
    )
    (tmp_path / "run_card.json").write_text(
        json.dumps(
            {"trade_score": {"score": 60.43, "coverage": 0.6, "status": "RESEARCH_ONLY"}}
        ),
        encoding="utf-8",
    )
    rc._figure_cross_check([str(tmp_path)], [{"fundamentals": []}])
    out = capsys.readouterr().out
    assert "all decimal figures grounded" in out
    assert "60.43" not in out


def test_a_garbled_engine_score_is_still_flagged(tmp_path, capsys):
    """Grounding the scorecard must not hide a garbled copy of it.

    A decimal-shift garble (60.43 -> 160.43) matches neither the tool evidence
    nor the run's scorecard, so the tripwire still fires - the fix removes false
    positives without adding false negatives.
    """
    rc = _load_repro_check()
    md_dir = tmp_path / "1_analysts"
    md_dir.mkdir()
    (md_dir / "market.md").write_text("TradeScore 160.43", encoding="utf-8")
    (tmp_path / "run_card.json").write_text(
        json.dumps({"trade_score": {"score": 60.43}}), encoding="utf-8"
    )
    rc._figure_cross_check([str(tmp_path)], [{"market": []}])
    out = capsys.readouterr().out
    assert "1 figure(s) with no matching" in out
    assert "160.4" in out


def test_run_card_tokens_is_empty_without_a_usable_card(tmp_path):
    """Absent or malformed run_card.json adds no grounding (older trees keep
    their previous behaviour)."""
    rc = _load_repro_check()
    assert rc._run_card_tokens(str(tmp_path)) == set()
    (tmp_path / "run_card.json").write_text("{not json", encoding="utf-8")
    assert rc._run_card_tokens(str(tmp_path)) == set()
