"""Timeout wiring for the LLM clients (alias fix + default).

langchain-openai 1.x / langchain-anthropic expose the underlying SDK timeout
as `request_timeout` / `default_request_timeout` — the `timeout` key in both
clients' passthrough lists was a latent TypeError at construction, and no
default was ever set. That meant a stalled provider (e.g. a congested
DeepSeek at US-night peak) could hang a chain.invoke indefinitely and the
job would look 'stuck re-trying truncated output'.

These tests pin: the `timeout=` alias maps to the real field, the 300 s
default applies when nothing is set, and an explicit timeout wins.
"""

import pytest

from tradingagents.llm_clients import anthropic_client as amod, openai_client as omod


def _capture_openai_kwargs(monkeypatch):
    captured: dict = {}

    def _fake(**kwargs):
        captured.setdefault("kwargs", kwargs)
        return object()

    # get_llm builds the client from the provider SPEC's chat_class, not the
    # module attribute directly — patch both so construction is intercepted
    # regardless of which reference get_llm resolves.
    monkeypatch.setattr(omod, "NormalizedChatOpenAI", _fake)
    monkeypatch.setitem(
        omod.OPENAI_COMPATIBLE_PROVIDERS, "openai",
        omod.ProviderSpec(chat_class=_fake, use_responses_api=True),
    )
    return captured


def _capture_anthropic_kwargs(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        amod, "NormalizedChatAnthropic",
        lambda **kwargs: captured.setdefault("kwargs", kwargs),
    )
    return captured


@pytest.mark.unit
class TestOpenAITimeout:
    @staticmethod
    def _set_key(monkeypatch):
        # The openai client validates the API-key env BEFORE forwarding the
        # ctor kwarg; set it so get_llm reaches the constructor.
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def test_explicit_timeout_maps_to_request_timeout(self, monkeypatch):
        self._set_key(monkeypatch)
        captured = _capture_openai_kwargs(monkeypatch)
        omod.OpenAIClient(model="gpt-4o-mini", api_key="x", timeout=42).get_llm()
        assert captured["kwargs"].get("request_timeout") == 42
        assert "timeout" not in captured["kwargs"]  # never the invalid kwarg

    def test_default_timeout_applies_when_unset(self, monkeypatch):
        self._set_key(monkeypatch)
        captured = _capture_openai_kwargs(monkeypatch)
        omod.OpenAIClient(model="gpt-4o-mini", api_key="x").get_llm()
        assert captured["kwargs"].get("request_timeout") == 300

    def test_request_timeout_also_accepted(self, monkeypatch):
        self._set_key(monkeypatch)
        captured = _capture_openai_kwargs(monkeypatch)
        omod.OpenAIClient(model="gpt-4o-mini", api_key="x", request_timeout=90).get_llm()
        assert captured["kwargs"].get("request_timeout") == 90


@pytest.mark.unit
class TestAnthropicTimeout:
    def test_explicit_timeout_maps_to_default_request_timeout(self, monkeypatch):
        captured = _capture_anthropic_kwargs(monkeypatch)
        amod.AnthropicClient(model="claude-sonnet-4-6", api_key="x", timeout=42).get_llm()
        assert captured["kwargs"].get("default_request_timeout") == 42
        assert "timeout" not in captured["kwargs"]

    def test_default_timeout_applies_when_unset(self, monkeypatch):
        captured = _capture_anthropic_kwargs(monkeypatch)
        amod.AnthropicClient(model="claude-sonnet-4-6", api_key="x").get_llm()
        assert captured["kwargs"].get("default_request_timeout") == 300

    def test_default_request_timeout_also_accepted(self, monkeypatch):
        captured = _capture_anthropic_kwargs(monkeypatch)
        amod.AnthropicClient(
            model="claude-sonnet-4-6", api_key="x", default_request_timeout=90
        ).get_llm()
        assert captured["kwargs"].get("default_request_timeout") == 90
