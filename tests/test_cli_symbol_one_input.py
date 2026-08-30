"""CLI --symbol = one-input mode: only the ticker is needed.

When ``--symbol`` is passed, ``get_user_selections`` must return a complete,
non-interactive run config: the given ticker, all four analysts, deep research
(5 debate/risk rounds), today's date, and the LLM provider + thinking models
pulled from the environment / DEFAULT_CONFIG — no questionary prompts.
Interactive (no ``--symbol``) flow must be untouched.
"""

from unittest import mock

import pytest

import cli.main as M

pytestmark = pytest.mark.timeout(180)


def _env():
    import os

    os.environ.setdefault("TRADINGAGENTS_LLM_PROVIDER", "openrouter")
    os.environ.setdefault("TRADINGAGENTS_QUICK_THINK_LLM", "deepseek/quick")
    os.environ.setdefault("TRADINGAGENTS_DEEP_THINK_LLM", "deepseek/deep")


@pytest.fixture(autouse=True)
def _quiet():
    with (
        mock.patch.object(M, "ensure_api_key", return_value=None),
        mock.patch.object(M, "fetch_announcements", return_value=""),
        mock.patch.object(M, "display_announcements", return_value=None),
    ):
        yield


def test_symbol_mode_returns_noninteractive_full_config():
    _env()
    sel = M.get_user_selections(symbol="AAPL")
    assert sel["ticker"] == "AAPL"
    assert sel["research_depth"] == 5  # deep
    assert {a.value for a in sel["analysts"]} == {
        "market", "social", "news", "fundamentals",
    }
    # Provider + models come from the environment / DEFAULT_CONFIG (the .env
    # values are already loaded into os.environ at import), never prompted.
    assert sel["llm_provider"] == M.DEFAULT_CONFIG["llm_provider"].lower()
    assert sel["shallow_thinker"]
    assert sel["deep_thinker"]
    assert sel["analysis_date"]  # today default


def test_symbol_mode_all_analysts_even_crypto_filters_fundamentals():
    _env()
    sel = M.get_user_selections(symbol="BTC-USD")
    assert {a.value for a in sel["analysts"]} == {"market", "social", "news"}
    assert sel["research_depth"] == 5


def test_symbol_mode_no_questionary_calls():
    """Symbol mode must never call the interactive prompt helpers."""
    _env()
    with (
        mock.patch.object(M, "get_ticker", side_effect=AssertionError("no prompt")),
        mock.patch.object(M, "select_analysts", side_effect=AssertionError("no prompt")),
        mock.patch.object(M, "select_research_depth", side_effect=AssertionError("no prompt")),
        mock.patch.object(M, "select_llm_provider", side_effect=AssertionError("no prompt")),
    ):
        sel = M.get_user_selections(symbol="MSFT")
        assert sel["ticker"] == "MSFT"
