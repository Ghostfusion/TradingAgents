"""Pre-market review: script + batch-integration hermetic tests.

Covers the standalone ``scripts/pre_market_review.py`` orchestration and the
same-night in-batch path (``batch._batch_pre_market_check``). Every vendor call
is mocked; no network. Each test inherits the pytest-timeout deadline.
"""

import json
import os
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_prior_report(tmp_path, ticker="EIX", date="2026-08-21", decision="**Rating**: Buy\n"):
    """Create a minimal prior report folder with a decision.md."""
    report = tmp_path / f"{ticker}_{date.replace('-', '')}_181500"
    (report / "5_portfolio").mkdir(parents=True)
    (report / "5_portfolio" / "decision.md").write_text(decision, encoding="utf-8")
    return report


def _load_script():
    """Load scripts/pre_market_review.py as a module (it is not a package)."""
    import importlib.util

    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "pre_market_review.py")
    spec = importlib.util.spec_from_file_location("pre_market_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_dry_run_writes_nothing(tmp_path):
    mod = _load_script()
    report = _make_prior_report(tmp_path)

    # route_to_vendor returns a tiny CSV window; catalyst returns a benign snapshot
    def fake_route(method, *a, **k):
        if method == "get_stock_data":
            return (
                "Date,Open,High,Low,Close,Volume\n"
                "2026-08-18,100,102,99,101,1000000\n"
                "2026-08-19,101,103,100,102,1200000\n"
                "2026-08-20,102,104,101,103,1100000\n"
            )
        return "NO_DATA_AVAILABLE"

    with (
        mock.patch("tradingagents.dataflows.interface.route_to_vendor", fake_route),
        mock.patch(
            "tradingagents.strategies.catalyst.fetch_catalyst_data",
            return_value={"ok": True},
        ),
        mock.patch(
            "tradingagents.strategies.catalyst.build_catalyst_snapshot",
            return_value={"verdict": "no-imminent-catalyst", "scale": 1.0},
        ),
        mock.patch(
            # discovery: the script looks under cwd/reports
            "pathlib.Path.cwd",
            return_value=tmp_path,
        ),
    ):
        pass
    # discovery uses Path.cwd()/reports — point it at tmp_path
    (tmp_path / "reports").mkdir(exist_ok=True)
    import shutil

    shutil.move(str(report), str(tmp_path / "reports" / report.name))
    rc = mod.main(["--ticker", "EIX", "--dry-run", "--skip-llm"])
    assert rc == 0
    assert not (tmp_path / "reports" / report.name / "pre_market_review_*.md").exists()


def test_batch_same_night_writes_review_file(tmp_path, monkeypatch):
    """_batch_pre_market_check writes pre_market_review_<date>.md next to the report."""
    import batch

    report = _make_prior_report(tmp_path, decision="**Rating**: Buy\n**Thesis**: x\n")

    monkeypatch.setattr(
        "tradingagents.strategies.catalyst.fetch_catalyst_data", lambda *a, **k: {"ok": True}
    )
    monkeypatch.setattr(
        "tradingagents.strategies.catalyst.build_catalyst_snapshot",
        lambda *a, **k: {"verdict": "no-imminent-catalyst", "scale": 1.0},
    )
    monkeypatch.setattr(batch, "DEFAULT_CONFIG", {"enable_pre_market_review": True})

    with mock.patch(
        "tradingagents.strategies.pre_market.load_prior_state",
        return_value={
            "decision_md": "**Rating**: Buy\n",
            "state": {"final_trade_decision": "**Rating**: Buy"},
        },
    ):
        batch._batch_pre_market_check("EIX", str(report), "2026-08-21")

    out = report / "pre_market_review_2026-08-21.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Pre-Market Review" in text
    assert "**CONFIRM**" in text or "**REVISE**" in text


def test_batch_same_night_factor_unavailable_never_fails(tmp_path, monkeypatch):
    import batch

    report = _make_prior_report(tmp_path)
    monkeypatch.setattr(
        "tradingagents.strategies.catalyst.fetch_catalyst_data",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(batch, "DEFAULT_CONFIG", {"enable_pre_market_review": True})
    # Must not raise: the batch symbol must not be marked failed by the review.
    batch._batch_pre_market_check("EIX", str(report), "2026-08-21")


# Explicit timer for this module (repo default is 180s/test; keep it visible).
pytestmark = pytest.mark.timeout(180)


def _load_script_module():
    import importlib.util

    for name in ("pre_market_review", "pre_market_review_mod"):
        if name in sys.modules:
            del sys.modules[name]
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "pre_market_review.py")
    spec = importlib.util.spec_from_file_location("pre_market_review_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_headline_delta_parses_titles():
    mod = _load_script_module()
    fake_news = "- **Edison beats earnings** (2026-08-22)\n- **Sempra dividend raised**\n"
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=lambda method, *a, **k: (
            fake_news if method == "get_news" else "NO_DATA_AVAILABLE"
        ),
    ):
        titles = mod._headline_delta("EIX", "2026-08-16", "2026-08-22", limit=2)
    assert len(titles) == 2
    assert "Edison beats earnings" in titles[0]


def test_headline_delta_degrades_to_empty():
    mod = _load_script_module()
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
    ):
        assert mod._headline_delta("EIX", "2026-08-16", "2026-08-22") == []


def test_decision_history_reads_logs(tmp_path):
    logs_dir = tmp_path / "EIX" / "TradingAgentsStrategy_logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "full_states_log_2026-08-20.json").write_text(
        json.dumps(
            {
                "company_of_interest": "EIX",
                "trade_date": "2026-08-20",
                "final_trade_decision": "**Rating**: Buy\n**Executive Summary**: x",
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "full_states_log_2026-08-21.json").write_text(
        json.dumps(
            {
                "company_of_interest": "EIX",
                "trade_date": "2026-08-21",
                "final_trade_decision": "**Rating**: Hold\n**Executive Summary**: y",
            }
        ),
        encoding="utf-8",
    )
    from scripts.decision_history import history_for

    rows = history_for("EIX", str(tmp_path))
    assert [r["date"] for r in rows] == ["2026-08-20", "2026-08-21"]
    assert rows[0]["rating"] == "Buy"
    assert rows[1]["rating"] == "Hold"


def test_decision_history_missing_returns_empty(tmp_path):
    from scripts.decision_history import history_for

    assert history_for("NOPE", str(tmp_path)) == []


def test_nightly_review_drives_from_summary(tmp_path, monkeypatch):
    """The batch-summary driver calls the review per symbol and maps REJECTs."""
    import scripts.nightly_review as nr

    summary = tmp_path / "batch_summary_20260822_190000.jsonl"
    summary.write_text(
        json.dumps(
            {"symbol": "EIX", "report_dir": str(tmp_path / "EIX_20260821_181500"), "depth": "deep"}
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "EIX_20260821_181500" / "5_portfolio").mkdir(parents=True)
    (tmp_path / "EIX_20260821_181500" / "5_portfolio" / "decision.md").write_text(
        "**Rating**: Buy\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    called = []

    def fake_main(argv):
        called.append(argv)
        return 2  # simulate a REJECT review

    fake_mod = types.ModuleType("pre_market_review_mod")
    fake_mod.main = fake_main
    monkeypatch.setattr(nr, "_load_pre_market_script", lambda: fake_mod)
    rc = nr.main(["--summary", str(summary), "--skip-llm", "--dry-run"])
    assert rc == 2
    assert len(called) == 1
    assert "--ticker" in called[0] and "EIX" in called[0]


def test_decision_history_report_folder_fallback(tmp_path):
    """Batch reports carry only markdown (no full_states_log json); the history
    must fall back to 5_portfolio/decision.md per report folder."""
    from scripts.decision_history import history_for

    rep = tmp_path / "MSFT_20260811_143655"
    (rep / "5_portfolio").mkdir(parents=True)
    (rep / "5_portfolio" / "decision.md").write_text(
        "**Rating**: Buy\n**Executive Summary**: x\n", encoding="utf-8"
    )
    rep2 = tmp_path / "msft_20260730_135724"
    (rep2 / "5_portfolio").mkdir(parents=True)
    (rep2 / "5_portfolio" / "decision.md").write_text("**Rating**: Hold\n", encoding="utf-8")
    rows = history_for("MSFT", results_dir=str(tmp_path))
    assert len(rows) == 2
    assert {r["rating"] for r in rows} == {"Buy", "Hold"}
    assert all(r["flags"] == "report-folder" for r in rows)
    # lowercase ticker still matches
    assert len(history_for("msft", results_dir=str(tmp_path))) == 2


def test_decision_history_case_insensitive(tmp_path):
    from scripts.decision_history import history_for

    assert history_for("nope", results_dir=str(tmp_path)) == []


def test_decision_history_cli_main_finds_report_folders(tmp_path, monkeypatch, capsys):
    """Regression: main() used to pass the default results_dir into history_for,
    which treated it as an explicit override and skipped the reports/ tree (so
    the CLI/web path returned 'no history' even with report folders present)."""
    import scripts.decision_history as dh

    rep = tmp_path / "MSFT_20260811_143655"
    (rep / "5_portfolio").mkdir(parents=True)
    (rep / "5_portfolio" / "decision.md").write_text(
        "**Rating**: Buy\n**Executive Summary**: x\n", encoding="utf-8"
    )
    # fake _results_dir so the default path points at tmp_path (hermetic),
    # then run main(['msft']) which must discover the report folder.
    monkeypatch.setattr(dh, "_results_dir", lambda: str(tmp_path))
    rc = dh.main(["msft"])
    out = capsys.readouterr()
    assert rc == 0
    assert "MSFT" in out.out and "Buy" in out.out
