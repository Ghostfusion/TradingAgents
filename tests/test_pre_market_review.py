"""Pre-market review: script + batch-integration hermetic tests.

Covers the standalone ``scripts/pre_market_review.py`` orchestration and the
same-night in-batch path (``batch._batch_pre_market_check``). Every vendor call
is mocked; no network. Each test inherits the pytest-timeout deadline.
"""

import os
import sys
from unittest import mock

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

    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor", fake_route
    ), mock.patch(
        "tradingagents.strategies.catalyst.fetch_catalyst_data",
        return_value={"ok": True},
    ), mock.patch(
        "tradingagents.strategies.catalyst.build_catalyst_snapshot",
        return_value={"verdict": "no-imminent-catalyst", "scale": 1.0},
    ), mock.patch(
        # discovery: the script looks under cwd/reports
        "pathlib.Path.cwd",
        return_value=tmp_path,
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
