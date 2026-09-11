"""A terminal without a console buffer must fail with one actionable line (#1138).

prompt_toolkit raises NoConsoleScreenBufferError before the first prompt in
non-interactive Windows terminals; the CLI should not surface that traceback.
The Windows-only exception import must also stay inert on other platforms.
"""
from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

import cli.main as m


def test_no_console_error_tuple_matches_platform():
    # Off Windows the win32 module is never imported (it asserts the platform),
    # so the tuple is empty — which `except` accepts and never matches. On
    # Windows it holds the real exception type, and a broken prompt_toolkit
    # would raise at import rather than silently disabling the handler.
    assert isinstance(m._NO_CONSOLE_ERRORS, tuple)
    assert all(issubclass(e, BaseException) for e in m._NO_CONSOLE_ERRORS)
    if sys.platform == "win32":
        assert m._NO_CONSOLE_ERRORS, "Windows must resolve the console error type"
    else:
        assert m._NO_CONSOLE_ERRORS == ()


def test_missing_console_prints_actionable_message(monkeypatch):
    class _NoConsole(Exception):
        pass

    # Simulate the Windows failure on any platform by registering a stand-in.
    monkeypatch.setattr(m, "_NO_CONSOLE_ERRORS", (_NoConsole,))

    def _boom(*a, **k):
        raise _NoConsole("No Windows console found. Are you running cmd.exe?")

    monkeypatch.setattr(m, "run_analysis", _boom)

    result = CliRunner().invoke(m.app, [])
    assert result.exit_code == 1
    assert "no Windows console available" in result.output
    # The raw prompt_toolkit traceback must not reach the user.
    assert "Traceback" not in result.output


def test_unrelated_errors_still_propagate(monkeypatch):
    # The handler must stay narrow: only the console error is translated.
    monkeypatch.setattr(m, "_NO_CONSOLE_ERRORS", (RuntimeError,))

    def _boom(*a, **k):
        raise ValueError("unrelated")

    monkeypatch.setattr(m, "run_analysis", _boom)
    result = CliRunner().invoke(m.app, [])
    assert isinstance(result.exception, ValueError)


def test_analyze_accepts_save_and_display_flags(monkeypatch):
    """--save-report/--display-report/--save-path are accepted and passed
    through to run_analysis (save+display default ON). `analyze` is the app's
    single command, so the flags go directly (no subcommand prefix)."""
    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(m, "run_analysis", _fake_run)
    result = CliRunner().invoke(
        m.app,
        ["--save-report", "--display-report", "--save-path", "out/x"],
    )
    assert result.exit_code == 0
    assert captured["save_report"] is True
    assert captured["display_report"] is True
    assert captured["save_path_arg"] == Path("out/x")


def test_analyze_defaults_save_and_display_on(monkeypatch):
    """Default behavior: save + display stay ON (user's requirement)."""
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(m, "run_analysis", fake_run)
    result = CliRunner().invoke(m.app, [])
    assert result.exit_code == 0
    assert captured["save_report"] is True
    assert captured["display_report"] is True
    assert captured["save_path_arg"] is None


def test_analyze_no_save_no_display_flags(monkeypatch):
    """--no-save-report / --no-display-report turn the defaults off."""
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(m, "run_analysis", fake_run)
    result = CliRunner().invoke(m.app, ["--no-save-report", "--no-display-report"])
    assert result.exit_code == 0
    assert captured["save_report"] is False
    assert captured["display_report"] is False
    assert captured["save_path_arg"] is None


def test_cli_applies_strategy_overlays_and_seeds_risk_context(monkeypatch, tmp_path):
    """The interactive CLI must mirror propagate(): seed risk_context before
    the graph streams and apply the strategy overlays before saving, so a CLI
    report carries the same Risk Gate block / position contract that the
    batch/API path renders (a former CLI-vs-batch divergence - a 12:02 batch
    NVDA report showed a Risk Gate PASS while a 13:48 CLI report showed none
    and a materially different decision)."""
    import types

    calls: list[str] = []
    seen_state: dict = {}
    saved: list = []

    class _Propagator:
        @staticmethod
        def create_initial_state(*a, **k):
            return {"company_of_interest": "NVDA"}

        @staticmethod
        def get_graph_args(**k):
            return {}

    class _Stream:
        @staticmethod
        def stream(state, **k):
            calls.append("stream")
            seen_state.update(state)
            return iter([{"market_report": "m", "final_trade_decision": "**Rating**: Hold"}])

    class _FakeGraph:
        propagator = _Propagator
        graph = _Stream

        def resolve_instrument_context(self, ticker, asset_type):
            return "NVDA (NVIDIA Corp)"

        def _precompute_risk_context(self, ticker):
            calls.append("risk_context")
            return {"cvar_95": -0.03}

        def _apply_strategy_overlays(self, state, ticker):
            calls.append("overlays")
            return {**state, "strategy_overlays": {"position_contract": "2.0%"}}

    class _NullLive:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(m, "TradingAgentsGraph", lambda *a, **k: _FakeGraph())
    monkeypatch.setattr(
        m,
        "get_user_selections",
        lambda symbol=None: {
            "ticker": "NVDA",
            "analysis_date": "2026-09-10",
            "asset_type": "stock",
            "analysts": [types.SimpleNamespace(value="market")],
        },
    )
    monkeypatch.setattr(
        m,
        "_build_run_config",
        lambda selections, checkpoint: {
            "results_dir": str(tmp_path),
            "enable_risk_governor": True,
        },
    )
    # Keep the TUI inert: no Rich rendering, no report path resolution.
    monkeypatch.setattr(m, "create_layout", lambda: object())
    monkeypatch.setattr(m, "update_display", lambda *a, **k: None)
    monkeypatch.setattr(m, "update_analyst_statuses", lambda *a, **k: None)
    monkeypatch.setattr(m, "display_complete_report", lambda *a, **k: None)
    monkeypatch.setattr(m, "Live", _NullLive)
    monkeypatch.setattr(
        "tradingagents.dataflows.utils.resolve_output_path", lambda *a, **k: tmp_path
    )

    def _fake_save(state, ticker, save_path):
        calls.append("save")
        saved.append((state, ticker))
        return Path(save_path) / "decision.md"

    monkeypatch.setattr(m, "save_report_to_disk", _fake_save)
    # run_analysis rebinds these methods on the module-level buffer; let
    # monkeypatch (not the run) own that global mutation.
    monkeypatch.setattr(m.message_buffer, "add_message", m.message_buffer.add_message)
    monkeypatch.setattr(m.message_buffer, "add_tool_call", m.message_buffer.add_tool_call)
    monkeypatch.setattr(
        m.message_buffer, "update_report_section", m.message_buffer.update_report_section
    )

    m.run_analysis(save_report=True, display_report=False, save_path_arg=tmp_path / "out")

    # 1) risk_context is computed and seeded into the state the graph streams.
    assert calls == ["risk_context", "stream", "overlays", "save"]
    assert seen_state["risk_context"] == {"cvar_95": -0.03}
    # 2) the saved state is the overlay-applied one, not the raw merged stream.
    saved_state, saved_ticker = saved[0]
    assert saved_ticker == "NVDA"
    assert saved_state["strategy_overlays"] == {"position_contract": "2.0%"}
    assert saved_state["final_trade_decision"] == "**Rating**: Hold"
