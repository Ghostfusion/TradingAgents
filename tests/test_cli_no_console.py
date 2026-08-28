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


def test_cli_applies_strategy_overlays_and_seeds_risk_context():
    """The interactive CLI must mirror propagate(): seed risk_context before
    the Portfolio Manager and apply the strategy overlays before saving, so a
    CLI report carries the same Risk Gate block / position contract that the
    batch/API path renders (a former CLI-vs-batch divergence - a 12:02 batch
    NVDA report showed a Risk Gate PASS while a 13:48 CLI report showed none
    and a materially different decision)."""
    src = Path("cli/main.py").read_text(encoding="utf-8")

    # 1) risk_context seeded into the initial state before the graph streams.
    assert "_precompute_risk_context(" in src
    assert 'init_agent_state["risk_context"]' in src
    seed_pos = src.index("_precompute_risk_context(")
    stream_pos = src.index("graph.graph.stream(")
    assert seed_pos < stream_pos, "risk_context must be seeded before the graph runs"

    # 2) overlays applied to the merged final_state before saving.
    assert "_apply_strategy_overlays(" in src
    overlay_pos = src.index("_apply_strategy_overlays(")
    save_pos = src.rindex("save_report_to_disk(")
    assert overlay_pos < save_pos, "overlays must run before the report is saved"
