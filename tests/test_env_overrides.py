"""Tests for TRADINGAGENTS_* env-var overlay onto DEFAULT_CONFIG."""

from __future__ import annotations

import importlib

import pytest

import tradingagents.default_config as default_config_module


def _reload_with_env(monkeypatch, **overrides):
    """Set/clear env vars then reload default_config to re-evaluate DEFAULT_CONFIG."""
    for key in list(default_config_module._ENV_OVERRIDES):
        monkeypatch.delenv(key, raising=False)
    for key, val in overrides.items():
        monkeypatch.setenv(key, val)
    return importlib.reload(default_config_module)


def test_no_env_uses_built_in_defaults(monkeypatch):
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["llm_provider"] == "openai"
    assert dc.DEFAULT_CONFIG["deep_think_llm"] == "gpt-5.5"
    assert dc.DEFAULT_CONFIG["quick_think_llm"] == "gpt-5.4-mini"
    assert dc.DEFAULT_CONFIG["backend_url"] is None
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 1
    assert dc.DEFAULT_CONFIG["checkpoint_enabled"] is False


def test_string_overrides(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_LLM_PROVIDER="google",
        TRADINGAGENTS_DEEP_THINK_LLM="gemini-3-pro-preview",
        TRADINGAGENTS_QUICK_THINK_LLM="gemini-3-flash-preview",
        TRADINGAGENTS_LLM_BACKEND_URL="https://example.invalid/v1",
        TRADINGAGENTS_OUTPUT_LANGUAGE="Chinese",
    )
    assert dc.DEFAULT_CONFIG["llm_provider"] == "google"
    assert dc.DEFAULT_CONFIG["deep_think_llm"] == "gemini-3-pro-preview"
    assert dc.DEFAULT_CONFIG["quick_think_llm"] == "gemini-3-flash-preview"
    assert dc.DEFAULT_CONFIG["backend_url"] == "https://example.invalid/v1"
    assert dc.DEFAULT_CONFIG["output_language"] == "Chinese"


def test_backup_llm_override(monkeypatch):
    """TRADINGAGENTS_BACKUP_LLM maps to the backup_llm config key; unset -> ''."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_BACKUP_LLM="openrouter:deepseek/deepseek-chat",
    )
    assert dc.DEFAULT_CONFIG["backup_llm"] == "openrouter:deepseek/deepseek-chat"
    dc2 = _reload_with_env(monkeypatch)
    assert dc2.DEFAULT_CONFIG["backup_llm"] == ""


def test_int_coercion(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_MAX_DEBATE_ROUNDS="3",
        TRADINGAGENTS_MAX_RISK_ROUNDS="2",
    )
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 3
    assert isinstance(dc.DEFAULT_CONFIG["max_debate_rounds"], int)
    assert dc.DEFAULT_CONFIG["max_risk_discuss_rounds"] == 2
    assert isinstance(dc.DEFAULT_CONFIG["max_risk_discuss_rounds"], int)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("False", False), ("0", False), ("no", False), ("off", False),
    ],
)
def test_bool_coercion(monkeypatch, raw, expected):
    dc = _reload_with_env(monkeypatch, TRADINGAGENTS_CHECKPOINT_ENABLED=raw)
    assert dc.DEFAULT_CONFIG["checkpoint_enabled"] is expected


def test_reasoning_thinking_overrides(monkeypatch):
    """The provider reasoning/thinking knobs are env-configurable (non-interactive runs)."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_OPENAI_REASONING_EFFORT="high",
        TRADINGAGENTS_GOOGLE_THINKING_LEVEL="minimal",
        TRADINGAGENTS_ANTHROPIC_EFFORT="low",
    )
    assert dc.DEFAULT_CONFIG["openai_reasoning_effort"] == "high"
    assert dc.DEFAULT_CONFIG["google_thinking_level"] == "minimal"
    assert dc.DEFAULT_CONFIG["anthropic_effort"] == "low"


def test_reasoning_effort_defaults_to_none(monkeypatch):
    """Unset reasoning/thinking knobs stay None so each provider uses its own default."""
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["openai_reasoning_effort"] is None
    assert dc.DEFAULT_CONFIG["google_thinking_level"] is None
    assert dc.DEFAULT_CONFIG["anthropic_effort"] is None


def test_empty_env_value_is_passthrough(monkeypatch):
    """Empty TRADINGAGENTS_* values must not clobber the built-in default."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_LLM_PROVIDER="",
        TRADINGAGENTS_MAX_DEBATE_ROUNDS="",
    )
    assert dc.DEFAULT_CONFIG["llm_provider"] == "openai"
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 1


def test_invalid_int_raises(monkeypatch):
    """Garbage int values should surface a ValueError at import, not silently misconfigure."""
    monkeypatch.setenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "not-a-number")
    with pytest.raises(ValueError, match="TRADINGAGENTS_MAX_DEBATE_ROUNDS"):
        importlib.reload(default_config_module)
    # Restore module state for subsequent tests in this process
    monkeypatch.delenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", raising=False)
    importlib.reload(default_config_module)


@pytest.mark.parametrize("bad", ["treu", "flase", "maybe", "2", "enabled"])
def test_invalid_bool_raises(monkeypatch, bad):
    """A misspelled boolean must fail loudly (like ints) instead of silently False."""
    monkeypatch.setenv("TRADINGAGENTS_CHECKPOINT_ENABLED", bad)
    with pytest.raises(ValueError, match="TRADINGAGENTS_CHECKPOINT_ENABLED"):
        importlib.reload(default_config_module)
    monkeypatch.delenv("TRADINGAGENTS_CHECKPOINT_ENABLED", raising=False)
    importlib.reload(default_config_module)


def test_unknown_env_var_is_ignored(monkeypatch):
    """Env vars outside _ENV_OVERRIDES must not bleed into DEFAULT_CONFIG."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_NONEXISTENT_KEY="oops",
    )
    assert "nonexistent_key" not in dc.DEFAULT_CONFIG


def test_list_coercion(monkeypatch):
    dc = _reload_with_env(monkeypatch, TRADINGAGENTS_RISK_BASKET_TICKERS="SPY,QQQ,AAPL")
    assert dc.DEFAULT_CONFIG["risk_basket_tickers"] == ["SPY", "QQQ", "AAPL"]
    assert isinstance(dc.DEFAULT_CONFIG["risk_basket_tickers"], list)


def test_numeric_list_coercion_tranche_weights(monkeypatch):
    """Regression: list-typed defaults were coerced to strings, so
    TRADINGAGENTS_TRANCHE_WEIGHTS=0.3,0.3,0.4 landed as ['0.3',...] and made
    value_dip.tranche_plan's sum() raise (silently disabling the tranche fold).
    A numeric default list must come back as numbers."""
    dc = _reload_with_env(monkeypatch, TRADINGAGENTS_TRANCHE_WEIGHTS="0.3,0.3,0.4")
    w = dc.DEFAULT_CONFIG["tranche_weights"]
    assert w == [0.3, 0.3, 0.4]
    assert all(isinstance(x, float) for x in w)


def test_dict_coercion_kv_pairs(monkeypatch):
    dc = _reload_with_env(
        monkeypatch, TRADINGAGENTS_RISK_BASKET_WEIGHTS="SPY=0.4,QQQ=0.6"
    )
    w = dc.DEFAULT_CONFIG["risk_basket_weights"]
    assert w == {"SPY": 0.4, "QQQ": 0.6}
    assert isinstance(w, dict)


def test_dict_coercion_json(monkeypatch):
    dc = _reload_with_env(
        monkeypatch, TRADINGAGENTS_RISK_BASKET_WEIGHTS='{"SPY": 0.5, "QQQ": 0.5}'
    )
    assert dc.DEFAULT_CONFIG["risk_basket_weights"] == {"SPY": 0.5, "QQQ": 0.5}


def test_invalid_dict_raises(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_RISK_BASKET_WEIGHTS", "not-a-dict")
    with pytest.raises(ValueError, match="TRADINGAGENTS_RISK_BASKET_WEIGHTS"):
        importlib.reload(default_config_module)
    monkeypatch.delenv("TRADINGAGENTS_RISK_BASKET_WEIGHTS", raising=False)
    importlib.reload(default_config_module)


def test_output_token_caps_override_low_launcher_env(monkeypatch):
    """A launcher that exports LOW max_output_tokens (e.g. 8000/8000/4000) must
    NOT starve report turns: tradingagents.__init__ reloads .env with
    override=True for the three cap keys so the repo's declared values win."""
    import subprocess
    import sys

    import tradingagents  # noqa: F401  (registers the __init__ override)

    # Run a fresh interpreter with LOW caps pre-injected + locked cwd, like the
    # batch launcher, and confirm the module raises them from .env.
    code = (
        "import os;"
        "import tradingagents;"
        "from tradingagents.default_config import DEFAULT_CONFIG;"
        "print(DEFAULT_CONFIG['max_output_tokens']);"
        "print(DEFAULT_CONFIG['max_output_tokens_quick']);"
        "print(DEFAULT_CONFIG['max_output_tokens_deep']);"
        "print(os.environ.get('TRADINGAGENTS_MAX_OUTPUT_TOKENS'));"
        "print(os.environ.get('TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK'));"
        "print(os.environ.get('TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP'))"
    )
    env = {
        **dict(__import__("os").environ),
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS": "8000",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK": "8000",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP": "4000",
    }
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=__file__.rsplit("tests", 1)[0],
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    # effective config: raised above the injected 8000/8000/4000
    assert int(lines[0]) >= 8000, lines
    quick, deep = int(lines[1]), int(lines[2])
    assert quick >= 8000 and deep >= 4000, lines
    # the env vars themselves were raised too (so llm clients see them)
    assert int(lines[3]) >= 8000 and int(lines[4]) >= 8000 and int(lines[5]) >= 4000, lines


def test_forced_tools_default_off(monkeypatch):
    """Unset forced-tool vars keep the legacy LLM-selected path (empty list)."""
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["analyst_forced_tools"] == []
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_max_parallel"] == 1
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_timeout_s"] == 30
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_summary_window"] == 12000


def test_forced_tools_overrides(monkeypatch):
    """Comma list coerces to a list; ints coerce to ints."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_ANALYST_FORCED_TOOLS="get_fundamentals,get_financial_ratios",
        TRADINGAGENTS_ANALYST_FORCED_TOOLS_MAX_PARALLEL="2",
        TRADINGAGENTS_ANALYST_FORCED_TOOLS_TIMEOUT_S="15",
        TRADINGAGENTS_ANALYST_FORCED_TOOLS_SUMMARY_WINDOW="4000",
    )
    assert dc.DEFAULT_CONFIG["analyst_forced_tools"] == [
        "get_fundamentals",
        "get_financial_ratios",
    ]
    assert isinstance(dc.DEFAULT_CONFIG["analyst_forced_tools"], list)
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_max_parallel"] == 2
    assert isinstance(dc.DEFAULT_CONFIG["analyst_forced_tools_max_parallel"], int)
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_timeout_s"] == 15
    assert isinstance(dc.DEFAULT_CONFIG["analyst_forced_tools_timeout_s"], int)
    assert dc.DEFAULT_CONFIG["analyst_forced_tools_summary_window"] == 4000


def test_forced_tools_all_literal(monkeypatch):
    """'ALL' passes through as a single-element list (gatherer expands it)."""
    dc = _reload_with_env(
        monkeypatch, TRADINGAGENTS_ANALYST_FORCED_TOOLS="ALL"
    )
    assert dc.DEFAULT_CONFIG["analyst_forced_tools"] == ["ALL"]


def test_forced_tools_invalid_max_parallel_raises(monkeypatch):
    """Non-numeric max_parallel fails loudly, like the other int knobs."""
    monkeypatch.setenv("TRADINGAGENTS_ANALYST_FORCED_TOOLS_MAX_PARALLEL", "two")
    with pytest.raises(ValueError):
        importlib.reload(default_config_module)


def test_forced_tools_validation_ranges():
    """validate_config catches non-positive gatherer knobs."""
    dc = importlib.reload(default_config_module)
    violations = dc.validate_config(
        {
            "analyst_forced_tools": ["get_fundamentals"],
            "analyst_forced_tools_max_parallel": 0,
            "analyst_forced_tools_timeout_s": 0,
            "analyst_forced_tools_summary_window": 0,
        }
    )
    assert any("analyst_forced_tools_max_parallel" in v for v in violations)
    # timeout/summary_window allow zero = "off"; concurrency does not.
    assert not any("analyst_forced_tools_timeout_s" in v for v in violations)
    assert not any("analyst_forced_tools_summary_window" in v for v in violations)
