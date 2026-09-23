"""The security-context cross-run ledger (SC-9).

The ledger's job is to make a drift visible across runs - and its main risk is
claiming more than it can see. A tree with no block is not evidence the gate was
off (it may predate the gate); a tree whose sector is empty IS evidence of an
unclassified company. These tests pin that distinction, and pin that a malformed
card is reported as a malformed card rather than as a classification finding.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.security_context_ledger import build_ledger, load_blocks, render_text


def _tree(root: Path, name: str, block: dict | None, *, mtime: float) -> Path:
    tree = root / name
    tree.mkdir(parents=True)
    card: dict = {"ticker": name.split("_")[0], "sections": []}
    if block is not None:
        card["security_context"] = block
    (tree / "run_card.json").write_text(json.dumps(card), encoding="utf-8")
    os.utime(tree, (mtime, mtime))
    return tree


def _block(canonical: str | None, *, source: str | None = "yfinance", sic: str | None = None,
           triggered=(), promoted=()) -> dict:
    ctx = {"symbol": "X"}
    if canonical:
        ctx["sector_canonical"] = canonical
    if source and canonical:
        ctx["sector_source"] = source
    if sic:
        ctx["sec_sic"] = sic
    return {
        "status": "ok",
        "matrix_version": "2026-09-22.1",
        "trigger_version": "2026-09-22.1",
        "context": ctx,
        "theme_triggers": {t: {"triggered": True, "hits": 1, "terms": [t]} for t in triggered},
        "promoted_themes": list(promoted),
    }


def test_a_missing_reports_dir_is_an_empty_ledger_not_a_crash(tmp_path):
    ledger = build_ledger(str(tmp_path / "nope"))
    assert ledger["trees"] == 0
    assert ledger["with_block"] == 0
    assert "no security_context blocks" in render_text(ledger)


def test_a_tree_without_the_block_is_not_a_classification_finding(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", None, mtime=1_700_000_000)
    ledger = build_ledger(str(tmp_path))
    assert ledger["trees"] == 1
    assert ledger["without_block"] == 1
    assert ledger["with_block"] == 0
    # The ledger must not claim to know WHY the block is absent.
    assert "predate" in ledger["note"] or "cannot tell" in ledger["note"]


def test_an_unreadable_card_is_counted_as_a_card_problem(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", None, mtime=1_700_000_000)
    bad = tmp_path / "BBB_20260102_000000"
    bad.mkdir()
    (bad / "run_card.json").write_text("{not json", encoding="utf-8")
    ledger = build_ledger(str(tmp_path))
    assert ledger["unreadable_cards"] == 1
    # ...and it is NOT double-counted as a tree whose gate was off.
    assert ledger["without_block"] == 1
    assert ledger["trees"] == 2


def test_unclassified_is_counted_apart_from_classified(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", _block("technology"), mtime=1_700_000_100)
    _tree(tmp_path, "BBB_20260102_000000", _block(None), mtime=1_700_000_200)
    _tree(tmp_path, "CCC_20260103_000000", _block("energy", sic="1311"), mtime=1_700_000_300)
    ledger = build_ledger(str(tmp_path))
    assert ledger["with_block"] == 3
    assert ledger["unclassified"] == 1
    assert ledger["sector_canonical"] == {"energy": 1, "technology": 1}
    assert ledger["sector_source"] == {"yfinance": 2}
    assert ledger["sec_sic_present"] == 1


def test_triggers_and_promotions_are_counted_per_theme(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", _block("utilities", triggered=("ai", "tariff"),
                                                  promoted=("tariff",)), mtime=1_700_000_100)
    _tree(tmp_path, "BBB_20260102_000000", _block("utilities", triggered=("ai",)),
          mtime=1_700_000_200)
    ledger = build_ledger(str(tmp_path))
    assert ledger["theme_triggered"] == {"ai": 2, "tariff": 1}
    assert ledger["theme_promoted"] == {"tariff": 1}
    assert ledger["promotions_total"] == 1


def test_versions_are_reported_so_a_mixed_past_is_visible(tmp_path):
    older = _block("technology")
    older["matrix_version"] = "2026-01-01.1"
    _tree(tmp_path, "AAA_20260101_000000", older, mtime=1_700_000_100)
    _tree(tmp_path, "BBB_20260102_000000", _block("technology"), mtime=1_700_000_200)
    ledger = build_ledger(str(tmp_path))
    assert len(ledger["versions"]) == 2, ledger["versions"]


def test_limit_takes_the_newest_trees_not_the_alphabet(tmp_path):
    """Tree names start with the ticker, so a name sort would sample A-C."""
    _tree(tmp_path, "AAA_20260101_000000", _block("technology"), mtime=1_700_000_100)
    _tree(tmp_path, "ZZZ_20260102_000000", _block("energy"), mtime=1_700_000_900)
    rows = load_blocks(str(tmp_path), limit=1)
    assert len(rows) == 1
    assert rows[0][0].startswith("ZZZ"), "the newest tree is ZZZ by mtime"
    ledger = build_ledger(str(tmp_path), limit=1)
    assert ledger["sector_canonical"] == {"energy": 1}


def test_the_ledger_is_deterministic_and_json_serialisable(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", _block("technology", sic="3571"), mtime=1_700_000_100)
    a = build_ledger(str(tmp_path))
    b = build_ledger(str(tmp_path))
    assert a == b
    json.dumps(a)  # must not raise
    assert render_text(a) == render_text(b)


def test_the_ledger_carries_no_score_or_verdict(tmp_path):
    _tree(tmp_path, "AAA_20260101_000000", _block("technology"), mtime=1_700_000_100)
    ledger = build_ledger(str(tmp_path))
    flat = json.dumps(ledger)
    for word in ("rating", "verdict", "signal", "trade_score"):
        assert word not in flat, word
