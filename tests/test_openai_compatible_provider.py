"""Generic OpenAI-compatible provider (vLLM / LM Studio / llama.cpp / relays).

Verifies the user-supplied base_url is required and honored, the key is optional
(keyless local default), Chat Completions (not the Responses API) is used, any
model name is accepted, and the env backend URL precedence (#978).
"""

import pytest

from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.validators import validate_model

# Note: assert by class NAME, not isinstance — other tests reload the
# openai_client module, which would otherwise create a second class identity.


@pytest.mark.unit
def test_factory_routes_to_openai_client():
    client = create_llm_client(
        provider="openai_compatible", model="my-model", base_url="http://localhost:8000/v1"
    )
    assert type(client).__name__ == "OpenAIClient"


@pytest.mark.unit
def test_base_url_required(monkeypatch):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="requires a base_url"):
        create_llm_client(provider="openai_compatible", model="m").get_llm()


@pytest.mark.unit
def test_keyless_local_uses_placeholder_and_chat_completions(monkeypatch):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    llm = create_llm_client(
        provider="openai_compatible", model="qwen2.5", base_url="http://localhost:8000/v1"
    ).get_llm()
    assert type(llm).__name__ == "LocalCompatibleChatOpenAI"
    assert str(llm.openai_api_base) == "http://localhost:8000/v1"
    # keyless local servers: a placeholder key is sent
    key = llm.openai_api_key.get_secret_value() if hasattr(llm.openai_api_key, "get_secret_value") else llm.openai_api_key
    assert key == "EMPTY"
    # must use Chat Completions, not OpenAI's Responses API
    assert getattr(llm, "use_responses_api", False) in (False, None)


@pytest.mark.unit
def test_optional_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-relay-123")
    llm = create_llm_client(
        provider="openai_compatible", model="m", base_url="https://relay.example/v1"
    ).get_llm()
    key = llm.openai_api_key.get_secret_value() if hasattr(llm.openai_api_key, "get_secret_value") else llm.openai_api_key
    assert key == "sk-relay-123"


@pytest.mark.unit
def test_any_model_accepted_no_forced_key():
    assert validate_model("openai_compatible", "literally-anything") is True
    # The key env exists (read for keyed relays) but the provider is marked
    # key-optional, so the CLI never forces a prompt and keyless servers work.
    assert get_api_key_env("openai_compatible") == "OPENAI_COMPATIBLE_API_KEY"
    from tradingagents.llm_clients.openai_client import OPENAI_COMPATIBLE_PROVIDERS
    assert OPENAI_COMPATIBLE_PROVIDERS["openai_compatible"].key_optional is True


@pytest.mark.unit
def test_env_backend_url_precedence():
    # #978: explicit env URL wins over the menu/default regardless of provider source.
    from cli.utils import resolve_backend_url
    assert resolve_backend_url("openai", "https://api.openai.com/v1", env_url="http://proxy/v1") == "http://proxy/v1"
    assert resolve_backend_url("openai", "https://api.openai.com/v1", env_url=None) == "https://api.openai.com/v1"
    assert resolve_backend_url("deepseek", None, None) == "https://api.deepseek.com"


@pytest.mark.unit
def test_structured_output_suppresses_object_tool_choice(monkeypatch):
    # LM Studio / vLLM reject the object-form tool_choice langchain sends for
    # function-calling structured output (#1057). The generic provider binds the
    # schema as a tool but must not force tool_choice.
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel

    class Schema(BaseModel):
        x: int

    captured = {}
    monkeypatch.setattr(
        ChatOpenAI,
        "with_structured_output",
        lambda self, schema, method=None, **kw: captured.update({"method": method, **kw}) or "BOUND",
    )
    llm = create_llm_client(
        provider="openai_compatible", model="local-llm-30b", base_url="http://localhost:1234/v1"
    ).get_llm()
    out = llm.with_structured_output(Schema)
    assert out == "BOUND"
    assert captured["method"] == "function_calling"
    assert captured["tool_choice"] is None  # not the object form


# ---------------------------------------------------------------------------
# OpenRouter provider-routing ignore list (slow-provider blocking)
# ---------------------------------------------------------------------------


def test_openrouter_ignore_provider_extra_body(monkeypatch):
    """provider.ignore must be sent via extra_body on OpenRouter."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"openrouter_ignore_providers": ["venice", "io-net", "akashml"]},
    )
    from tradingagents.llm_clients.openai_client import OpenAIClient

    c = OpenAIClient("deepseek/deepseek-v4-flash-0731", provider="openrouter")
    llm = c.get_llm()
    assert llm is not None
    eb = getattr(llm, "extra_body", None) or {}
    assert eb.get("provider") == {"ignore": ["venice", "io-net", "akashml"]}


def test_openrouter_ignore_empty_no_extra_body(monkeypatch):
    """Empty ignore list must NOT add a provider payload."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config", lambda: {"openrouter_ignore_providers": []}
    )
    from tradingagents.llm_clients.openai_client import OpenAIClient

    c = OpenAIClient("deepseek/deepseek-v4-flash-0731", provider="openrouter")
    llm = c.get_llm()
    eb = getattr(llm, "extra_body", None) or {}
    assert "provider" not in eb


def test_openrouter_ignore_not_applied_to_other_providers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"openrouter_ignore_providers": ["venice"]},
    )
    from tradingagents.llm_clients.openai_client import OpenAIClient

    c = OpenAIClient("gpt-5.5", provider="openai")
    llm = c.get_llm()
    eb = getattr(llm, "extra_body", None) or {}
    assert "provider" not in eb


# ---------------------------------------------------------------------------
# Per-role max output tokens (quick=6000, deep=2500), most-info-not-overflow
# ---------------------------------------------------------------------------


def test_openrouter_max_tokens_passthrough(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"max_output_tokens": 6000, "max_output_tokens_quick": 6000,
                 "max_output_tokens_deep": 2500},
    )
    from tradingagents.llm_clients.openai_client import OpenAIClient

    # quick tier
    c = OpenAIClient("deepseek/deepseek-v4-flash-0731", provider="openrouter", max_tokens=6000)
    llm = c.get_llm()
    assert getattr(llm, "max_tokens", None) == 6000


def test_output_budget_helper_density_and_tool_call():
    from tradingagents.agents.utils.agent_utils import get_output_budget

    a = get_output_budget("analyst")
    assert "tool" in a and "bullet" in a and "table" in a
    r = get_output_budget("research")
    assert "250-400" in r
    t = get_output_budget("trader")
    assert "concise" in t.lower()
