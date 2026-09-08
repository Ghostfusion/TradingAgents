"""Hermetic tests for repro_check's analyst-figure grounding cross-check.

The `--evidence` figure cross-check flags decimal numbers in an analyst's
report that have no matching value in that run's `tool_evidence.json` - the
copy-garble class seen on QCOM 2026-09-07 news.md ('TGA 303.9->944B' for
903.9, 'CCC 0.51%' for 10.51, '7.6%' for 7.4%). Tolerance-matched, so a
legitimately rounded copy of a tool value passes.
"""

from __future__ import annotations

import importlib.util
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
