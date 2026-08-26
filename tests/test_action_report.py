"""Conditional action report: hermetic tests for scripts/action_report.py.

Covers the report discovery, decision parsing, classification (basket
Underweight/Sell vs non-basket Overweight/Buy), condition extraction, the
deterministic MET / NOT_MET / UNKNOWN checker, and the report builder. Every
vendor call is mocked; no network. Each test inherits the pytest-timeout
deadline.
"""

import json
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scripts.action_report as ar  # noqa: E402

pytestmark = pytest.mark.timeout(180)


def _decision_md(rating="Underweight", position_size="", exec_summary=""):
    return (
        f"**Rating**: {rating}\n\n"
        f"**Executive Summary**: {exec_summary}\n\n"
        f"**Position Size**: {position_size}\n\n"
        f"**Stop Loss**: 100.0\n\n"
        f"**Price Target**: 90.0\n"
    )


def _make_report(tmp_path, symbol, stamp, md):
    folder = tmp_path / f"{symbol}_{stamp}"
    (folder / "5_portfolio").mkdir(parents=True)
    (folder / "5_portfolio" / "decision.md").write_text(md, encoding="utf-8")
    return folder


def _synth_ohlcv(price, n=250):
    closes = [price * 0.9] * n + [price]
    return {
        "closes": closes,
        "highs": [c * 1.01 for c in closes],
        "lows": [c * 0.99 for c in closes],
        "volumes": [1_000_000.0] * (n + 1),
    }


# ---------------------------------------------------------------------------
# Basket + discovery + parsing + classification
# ---------------------------------------------------------------------------


def test_load_basket_from_config():
    b = ar.load_basket()
    assert isinstance(b, dict)
    assert all(isinstance(v, float) for v in b.values())


def test_load_basket_override():
    b = ar.load_basket("AAPL=0.1,MSFT=0.2")
    assert b == {"AAPL": 0.1, "MSFT": 0.2}


def test_discover_reports_newest_per_symbol(tmp_path):
    _make_report(tmp_path, "QCOM", "20260818_105451", _decision_md())
    _make_report(tmp_path, "QCOM", "20260819_090000", _decision_md())
    _make_report(tmp_path, "AMZN", "20260816_225735", _decision_md("Overweight"))
    reports = ar.discover_reports(str(tmp_path))
    assert set(reports) == {"QCOM", "AMZN"}
    assert reports["QCOM"].name == "QCOM_20260819_090000"  # newest wins


def test_parse_decision_fields():
    md = _decision_md(
        "Underweight",
        "Trim 25-50% into strength at $168-176",
        "Re-enter only on a test of $147.60",
    )
    d = ar.parse_decision(md)
    assert d["rating"] == "Underweight"
    assert "Trim 25-50%" in d["position_size"]
    assert "Re-enter only" in d["exec_summary"]
    assert d["stop_loss"] == 100.0
    assert d["price_target"] == 90.0


def test_classify_buy_sell_equivalence():
    basket = {"QCOM": 0.02}
    # basket + Underweight/Sell -> keep
    assert ar.classify("QCOM", "Underweight", basket) == "basket-underweight"
    assert ar.classify("QCOM", "Sell", basket) == "basket-underweight"
    # basket + Overweight/Buy -> not in scope
    assert ar.classify("QCOM", "Overweight", basket) is None
    assert ar.classify("QCOM", "Buy", basket) is None
    # non-basket + Overweight/Buy -> keep
    assert ar.classify("AMZN", "Overweight", basket) == "non-basket-overweight"
    assert ar.classify("AMZN", "Buy", basket) == "non-basket-overweight"
    # non-basket + Underweight/Hold -> not in scope
    assert ar.classify("AMZN", "Underweight", basket) is None
    assert ar.classify("AMZN", "Hold", basket) is None


# ---------------------------------------------------------------------------
# Condition extraction
# ---------------------------------------------------------------------------


def test_extract_condition_prefers_specific_trigger():
    d = {
        "position_size": "0% - no new position; trim existing holdings to underweight",
        "exec_summary": "Re-enter only on a test of $147.60 (or the $127-130 base) or a daily close back above the 200-SMA ($167.50).",
    }
    cond = ar.extract_condition(d)
    assert "$147.60" in cond
    assert "$167.50" in cond
    # the generic "trim" clause from position_size is not used (specific found)
    assert "trim existing holdings" not in cond


def test_extract_condition_dedups_restated_trigger():
    d = {
        "position_size": "scale to 5% only on confirmation-a held $248-$250 support test with stabilization or a volume-confirmed close above $284.",
        "exec_summary": "only on confirmation-either a held pullback into the $248-$250 support zone or a volume-confirmed close above $284.",
    }
    cond = ar.extract_condition(d)
    # the two clauses restate the same levels -> deduped to one
    assert cond.count("$284") == 1
    assert cond.count("$248") == 1


def test_extract_condition_skips_prohibition():
    d = {
        "position_size": "Do not chase above $270 without a fresh catalyst.",
        "exec_summary": "Scale to 5% only on confirmation-a held $248-$250 support test.",
    }
    cond = ar.extract_condition(d)
    assert "Do not chase" not in cond
    assert "$248" in cond


# ---------------------------------------------------------------------------
# Deterministic condition check
# ---------------------------------------------------------------------------


def test_check_condition_above_level_met():
    r = ar.check_condition("close above $284 on volume", _synth_ohlcv(285.0))
    assert r["verdict"] == "NOT_MET"  # price met, volume ratio 1.0 < 1.3
    labels = [c["label"] for c in r["checks"]]
    assert any("$284" in lab for lab in labels)
    assert any("volume" in lab for lab in labels)


def test_check_condition_above_level_met_with_volume():
    ohlcv = _synth_ohlcv(285.0)
    ohlcv["volumes"] = [1_000_000.0] * 250 + [2_000_000.0]  # ratio 2.0
    r = ar.check_condition("close above $284 on volume", ohlcv)
    assert r["verdict"] == "MET"


def test_check_condition_test_level_met():
    r = ar.check_condition("re-enter only on a test of $147.60", _synth_ohlcv(147.60))
    assert r["verdict"] == "MET"
    assert any("$147.60" in c["label"] for c in r["checks"])


def test_check_condition_not_met():
    r = ar.check_condition("re-enter only on a test of $147.60", _synth_ohlcv(158.10))
    assert r["verdict"] == "NOT_MET"


def test_check_condition_unknown_unmeasurable():
    r = ar.check_condition("add only on confirmation (clean PUC decision)", _synth_ohlcv(86.0))
    assert r["verdict"] == "UNKNOWN"
    assert any(c["verdict"] == "UNKNOWN" for c in r["checks"])


def test_check_condition_stop_level_informational():
    # a stop level must not block a trigger MET
    r = ar.check_condition("trim into strength at $168-176; hard stop below $143", _synth_ohlcv(170.0))
    assert r["verdict"] == "MET"
    stop_checks = [c for c in r["checks"] if c.get("informational")]
    assert stop_checks and "143" in stop_checks[0]["label"]


def test_check_condition_no_price_history():
    r = ar.check_condition("close above $284", {"closes": [], "highs": [], "lows": [], "volumes": []})
    assert r["verdict"] == "UNKNOWN"
    assert r["reasons"]


def test_check_condition_sma_reclaim():
    # price above the 200-SMA -> reclaim met
    closes = [100.0] * 250 + [120.0]
    ohlcv = {"closes": closes, "highs": [c * 1.01 for c in closes],
             "lows": [c * 0.99 for c in closes], "volumes": [1_000_000.0] * 251}
    r = ar.check_condition("daily close back above the 200-SMA", ohlcv)
    assert r["verdict"] == "MET"
    assert any("SMA200" in c["label"] for c in r["checks"])


# ---------------------------------------------------------------------------
# Report builder + main flow
# ---------------------------------------------------------------------------


def test_build_report_renders_sections():
    rows = [
        {
            "symbol": "QCOM", "kind": "basket-underweight", "weight": 0.02,
            "report": "QCOM_20260818_105451", "date": "2026-08-18",
            "rating": "Underweight", "condition": "re-enter only on a test of $147.60",
            "verdict": "NOT_MET", "checks": [{"label": "price at/near $147.60",
                                              "verdict": "NOT_MET", "detail": "price=158.10"}],
            "reasons": [], "judge": None, "stop_loss": 156.75, "price_target": 147.6,
        },
        {
            "symbol": "AMZN", "kind": "non-basket-overweight", "weight": None,
            "report": "AMZN_20260816_225735", "date": "2026-08-16",
            "rating": "Overweight", "condition": "close above $284 on volume",
            "verdict": "MET", "checks": [{"label": "price above $284.00",
                                          "verdict": "MET", "detail": "price=285.00"}],
            "reasons": [], "judge": None, "stop_loss": 237.7, "price_target": 333.0,
        },
    ]
    md = ar.build_report(rows, {"QCOM": 0.02}, "reports", "2026-08-26")
    assert "Basket names" in md
    assert "Non-basket names" in md
    assert "ADD/BUY" in md  # AMZN MET -> ADD/BUY
    assert "MONITOR" in md  # QCOM NOT_MET -> MONITOR


def test_main_dry_run_with_mocked_vendor(tmp_path, capsys):
    """End-to-end: a basket Underweight report + a non-basket Overweight
    report, vendor mocked, --dry-run prints the report and writes nothing."""
    basket = {"QCOM": 0.02}
    _make_report(
        tmp_path, "QCOM", "20260818_105451",
        _decision_md("Underweight", "Trim into strength at $168-176",
                     "Re-enter only on a test of $147.60"),
    )
    _make_report(
        tmp_path, "AMZN", "20260816_225735",
        _decision_md("Overweight", "Scale to 5% only on confirmation-a held $248-$250 support test or a volume-confirmed close above $284.",
                     "Do not chase above $270 without a fresh catalyst."),
    )
    with (
        mock.patch.object(ar, "load_basket", return_value=basket),
        mock.patch.object(
            ar, "fetch_ohlcv",
            side_effect=lambda t: {
                **(_synth_ohlcv(285.0)),
                "volumes": [1_000_000.0] * 250 + [2_000_000.0],  # 2.0x -> volume confirmed
            },
        ),
    ):
        rc = ar.main(["--reports-dir", str(tmp_path), "--dry-run", "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "QCOM" in out and "AMZN" in out
    assert "MONITOR" in out  # QCOM re-entry not met at 285
    assert "ADD/BUY" in out  # AMZN close above 284 + volume 2.0x -> met
    # no report file written in dry-run
    assert not (tmp_path / "out").exists()


def test_main_saves_report(tmp_path):
    """Non-dry-run writes the report to --out-dir (keep-only-newest)."""
    _make_report(
        tmp_path, "QCOM", "20260818_105451",
        _decision_md("Underweight", "Trim into strength at $168-176",
                     "Re-enter only on a test of $147.60"),
    )
    with (
        mock.patch.object(ar, "load_basket", return_value={"QCOM": 0.02}),
        mock.patch.object(ar, "fetch_ohlcv", return_value=_synth_ohlcv(147.60)),
    ):
        rc = ar.main(["--reports-dir", str(tmp_path), "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    saved = list((tmp_path / "out").glob("*.md"))
    assert len(saved) == 1
    assert "QCOM" in saved[0].read_text(encoding="utf-8")


def test_main_json_output(tmp_path, capsys):
    _make_report(
        tmp_path, "QCOM", "20260818_105451",
        _decision_md("Underweight", "Trim into strength at $168-176",
                     "Re-enter only on a test of $147.60"),
    )
    with (
        mock.patch.object(ar, "load_basket", return_value={"QCOM": 0.02}),
        mock.patch.object(ar, "fetch_ohlcv", return_value=_synth_ohlcv(147.60)),
    ):
        rc = ar.main(["--reports-dir", str(tmp_path), "--json", "--dry-run"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["symbol"] == "QCOM"
    assert rows[0]["kind"] == "basket-underweight"
    assert rows[0]["verdict"] == "MET"


def test_main_no_reports(tmp_path, capsys):
    rc = ar.main(["--reports-dir", str(tmp_path / "empty"), "--dry-run"])
    assert rc == 2
    assert "no report folders" in capsys.readouterr().err
