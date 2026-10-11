"""The strategy-quality report's new blocks (offline, temp ledgers and trees)."""

import json

import pytest

from scripts.strategy_quality_report import _run_economics_block, build_report, main

pytestmark = pytest.mark.timeout(120)


def _ledger(tmp_path, rows) -> str:
    path = tmp_path / "pre_market_ledger.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(tmp_path)


def test_the_report_carries_the_loss_side_surface_and_the_cross_sectional_null(tmp_path):
    data_dir = _ledger(tmp_path, [
        {"ticker": "AAA", "realized_return": 0.012, "sleeve": "swing"},
        {"ticker": "AAA", "realized_return": 0.004, "sleeve": "swing"},
        {"ticker": "BBB", "realized_return": -0.003, "sleeve": "value-dip"},
        {"ticker": "BBB", "realized_return": 0.001, "sleeve": "value-dip"},
        {"ticker": "CCC", "realized_return": 0.006, "sleeve": "momentum"},
        {"ticker": "CCC", "realized_return": 0.002, "sleeve": "momentum"},
    ])
    report = build_report(data_dir, cost_bps=10.0)

    surface = report["benchmark_surface"]
    assert surface["available"] is True
    row = surface["rows"][0]
    assert row["name"] == "strategy" and row["n"] == 6
    assert row["cvar"] is not None and row["prob_ge_threshold"] is not None
    assert surface["baseline_available"] is False
    assert "raw single curve is not a result" in surface["reason"]

    # The per-row series is now in the artifact: the old --benchmark block read a
    # key this dict never carried, so its arm series was always empty.
    assert report["ledgers"]["pre_market"]["realized"] == [
        0.012, 0.004, -0.003, 0.001, 0.006, 0.002,
    ]

    cs = report["cross_sectional_null"]
    assert cs["available"] is True and cs["n_names"] == 3
    assert cs["verdict"] in ("distinguishable_from_zero", "consistent_with_zero")
    # AAA +0.008, BBB -0.001, CCC +0.004: two names up, one down.
    assert cs["sign_test"]["n_positive"] == 2 and cs["sign_test"]["n_negative"] == 1


def test_the_report_refuses_both_new_blocks_when_nothing_resolved(tmp_path):
    data_dir = _ledger(tmp_path, [{"ticker": "AAA", "realized_return": None}])
    report = build_report(data_dir, cost_bps=10.0)
    assert report["benchmark_surface"]["available"] is False
    assert report["cross_sectional_null"]["available"] is False


def test_the_run_economics_sweep_joins_cost_to_quality(tmp_path):
    tree = tmp_path / "AAA_20260101_000000"
    tree.mkdir()
    (tree / "run_card.json").write_text(json.dumps({
        "ticker": "AAA",
        "llm_cost_est": {
            "quick_think_llm": {
                "model": "m1",
                "rate_usd_per_1m": {"in": 1.0, "out": 2.0},
                "max_output_leg_usd": 0.25,
            }
        },
    }), encoding="utf-8")
    (tree / "verify_flags.json").write_text(json.dumps({
        "verification": {"market": {"overall": "PASS"}, "news": {"overall": "FLAG"}},
        "prose": {"overall": "PASS", "reports": {}},
    }), encoding="utf-8")

    block = _run_economics_block(str(tmp_path))
    assert block["available"] is True and block["n_trees"] == 1
    assert block["n_priced"] == 1 and block["n_passed"] == 1
    row = block["rows"][0]
    assert row["tree"] == "AAA_20260101_000000"
    assert row["cost_upper_usd"] == pytest.approx(0.25)
    assert row["quality"]["flags_count"] == 1
    assert row["quality"]["flagged_stems"] == ["news"]
    assert row["flags_per_usd"] == pytest.approx(4.0)


def test_the_sweep_reports_an_empty_tree_dir_as_a_refusal(tmp_path):
    block = _run_economics_block(str(tmp_path))
    assert block["available"] is False and "no run_card.json" in block["reason"]


def test_main_renders_the_new_sections(tmp_path, capsys):
    data_dir = _ledger(tmp_path, [
        {"ticker": "AAA", "realized_return": 0.012},
        {"ticker": "BBB", "realized_return": -0.004},
        {"ticker": "CCC", "realized_return": 0.006},
    ])
    assert main(["--data-dir", data_dir]) == 0
    text = capsys.readouterr().out
    assert "Baseline-relative surface" in text
    assert "Cross-sectional null over per-name PnL" in text
    assert "strategy (loss side):" in text


def test_main_json_carries_the_trees_join(tmp_path, capsys):
    tree = tmp_path / "trees" / "AAA_20260101_000000"
    tree.mkdir(parents=True)
    (tree / "run_card.json").write_text(json.dumps({
        "ticker": "AAA",
        "llm_cost_est": {"quick_think_llm": {"model": "m1",
                                             "rate_usd_per_1m": {"in": 1.0, "out": 1.0},
                                             "max_output_leg_usd": 0.5}},
    }), encoding="utf-8")
    data_dir = _ledger(tmp_path, [{"ticker": "AAA", "realized_return": 0.01}])
    assert main(["--data-dir", data_dir, "--trees", str(tmp_path / "trees"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_economics"]["n_trees"] == 1
    assert payload["run_economics"]["rows"][0]["cost_upper_usd"] == pytest.approx(0.5)
    assert payload["run_economics"]["rows"][0]["quality"] is None
