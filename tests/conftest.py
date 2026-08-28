"""Shared pytest fixtures that prevent CI hangs when API keys are absent."""

import os
from unittest.mock import MagicMock, patch

import pytest


def pytest_configure(config):
    for marker in ("unit", "integration", "smoke"):
        config.addinivalue_line("markers", f"{marker}: {marker}-level tests")


_API_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_CN_API_KEY",
    "ZHIPU_API_KEY",
    "ZHIPU_CN_API_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY",
    "OPENROUTER_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
)


@pytest.fixture(autouse=True)
def _dummy_api_keys(monkeypatch):
    for env_var in _API_KEY_ENV_VARS:
        # `or` not a .get default: an env var present but empty (e.g. a key left
        # blank in a .env copied from .env.example) must still get the placeholder.
        monkeypatch.setenv(env_var, os.environ.get(env_var) or "placeholder")


@pytest.fixture(autouse=True)
def _isolate_config():
    """Reset the global + thread-local dataflows config before and after each test.

    ``set_config`` merges (it never clears keys absent from the override), so a
    test that sets e.g. ``tool_vendors`` would otherwise leak into later tests
    and make routing behavior order-dependent. ``reset_config()`` clears both
    the process fallback and the current thread's override, so every test
    starts from a clean DEFAULT_CONFIG.
    """
    import tradingagents.dataflows.config as config_module

    config_module.reset_config()
    # The vendor cache is a module-level singleton; clear its in-memory layer so
    # a prior test's mocked vendor result can't be served to this test.
    from tradingagents.dataflows.vendor_cache import vendor_cache

    vendor_cache.clear()
    # The analysis-tools run-level OHLCV cache is a module-level singleton too;
    # clear it so a prior test's mocked OHLCV can't leak into this one.
    from tradingagents.agents.utils import analysis_tools as _atools

    _atools._clear_ohlcv_cache()
    yield
    config_module.reset_config()
    vendor_cache.clear()
    _atools._clear_ohlcv_cache()
    # Close any real moomoo OpenQuoteContext a test created. The SDK's
    # background threads only tear down while the process is healthy; contexts
    # left open until interpreter exit hang the run for minutes.
    from tradingagents.dataflows.moomoo import _close_all_ctxs

    _close_all_ctxs()


@pytest.fixture(autouse=True)
def _disable_reddit_killswitch(monkeypatch):
    """Force the Reddit fetch path during tests.

    ``TRADINGAGENTS_DISABLE_REDDIT`` is read from the ambient environment (which
    loads a developer's ``.env`` at package import). Unit tests for the fetcher
    must exercise the real fetch path regardless of that local opt-out, so the
    kill-switch is removed for every test.
    """
    monkeypatch.delenv("TRADINGAGENTS_DISABLE_REDDIT", raising=False)
    yield


@pytest.fixture(autouse=True)
def _mock_computed_sentiment(monkeypatch):
    """Keep the sentiment analyst's computed layer hermetic.

    ``enable_sentiment`` is on by default, so the sentiment analyst calls
    ``sentiment.compute_social_scores`` (a live StockTwits fetch). Unit tests
    must not hit the network; mock it to return None (the analyst then skips
    the computed line) unless a test explicitly overrides it.
    """
    monkeypatch.setattr(
        "tradingagents.strategies.sentiment.compute_social_scores", lambda *a, **k: None
    )
    yield


@pytest.fixture()
def mock_llm_client():
    client = MagicMock()
    client.get_llm.return_value = MagicMock()
    with patch(
        "tradingagents.llm_clients.factory.create_llm_client",
        return_value=client,
    ):
        yield client
