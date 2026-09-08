"""Tests for the anti-repetition sampling controls (top_p / frequency /
presence penalties) — the loop-escape levers from the repetition-degeneration
analysis. Default None preserves reproducibility; when set the value must
reach every client that supports it (and only those).
"""

import importlib

import pytest

from tradingagents.llm_clients.factory import create_llm_client


def _getattr_safe(obj, name):
    try:
        return getattr(obj, name)
    except AttributeError:
        return None


@pytest.mark.unit
class TestSamplingForwarding:
    @pytest.mark.parametrize(
        "provider,model",
        [
            ("openai", "gpt-4.1"),
            ("deepseek", "deepseek-chat"),
        ],
    )
    def test_openai_compatible_forwards_all_three(self, provider, model):
        llm = create_llm_client(
            provider=provider,
            model=model,
            top_p=0.9,
            frequency_penalty=0.3,
            presence_penalty=0.2,
            api_key="placeholder",
        ).get_llm()
        assert _getattr_safe(llm, "top_p") == 0.9
        assert _getattr_safe(llm, "frequency_penalty") == 0.3
        assert _getattr_safe(llm, "presence_penalty") == 0.2

    @pytest.mark.parametrize(
        "provider,model",
        [("anthropic", "claude-sonnet-5"), ("google", "gemini-3.5-flash")],
    )
    def test_penalty_less_providers_forward_top_p_only(self, provider, model):
        # Anthropic / Gemini support top_p but not OpenAI-style penalties:
        # forwarding only the supported key must not crash construction.
        llm = create_llm_client(
            provider=provider,
            model=model,
            top_p=0.9,
            frequency_penalty=0.3,
            presence_penalty=0.2,
            api_key="placeholder",
        ).get_llm()
        assert _getattr_safe(llm, "top_p") == 0.9

    def test_unset_leaves_provider_defaults(self):
        llm = create_llm_client(
            provider="openai", model="gpt-4.1", api_key="placeholder"
        ).get_llm()
        assert _getattr_safe(llm, "top_p") is None
        assert _getattr_safe(llm, "frequency_penalty") is None
        assert _getattr_safe(llm, "presence_penalty") is None


@pytest.mark.unit
class TestSamplingEnvOverlay:
    def test_env_sets_all_three(self, monkeypatch):
        monkeypatch.setenv("TRADINGAGENTS_TOP_P", "0.9")
        monkeypatch.setenv("TRADINGAGENTS_FREQUENCY_PENALTY", "0.3")
        monkeypatch.setenv("TRADINGAGENTS_PRESENCE_PENALTY", "0.2")
        import tradingagents.default_config as dc

        importlib.reload(dc)
        assert float(dc.DEFAULT_CONFIG["top_p"]) == 0.9
        assert float(dc.DEFAULT_CONFIG["frequency_penalty"]) == 0.3
        assert float(dc.DEFAULT_CONFIG["presence_penalty"]) == 0.2
        monkeypatch.delenv("TRADINGAGENTS_TOP_P", raising=False)
        monkeypatch.delenv("TRADINGAGENTS_FREQUENCY_PENALTY", raising=False)
        monkeypatch.delenv("TRADINGAGENTS_PRESENCE_PENALTY", raising=False)
        importlib.reload(dc)

    def test_defaults_none_when_unset(self, monkeypatch):
        import tradingagents.default_config as dc

        for k in ("TRADINGAGENTS_TOP_P", "TRADINGAGENTS_FREQUENCY_PENALTY",
                  "TRADINGAGENTS_PRESENCE_PENALTY"):
            monkeypatch.delenv(k, raising=False)
        importlib.reload(dc)
        assert dc.DEFAULT_CONFIG["top_p"] is None
        assert dc.DEFAULT_CONFIG["frequency_penalty"] is None
        assert dc.DEFAULT_CONFIG["presence_penalty"] is None
        importlib.reload(dc)


@pytest.mark.unit
class TestProviderKwargsSampling:
    """_get_provider_kwargs float-coerces and forwards the sampling keys."""

    def _kwargs_for(self, **keys):
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
        graph.config = {"llm_provider": "openai", **keys}
        return TradingAgentsGraph._get_provider_kwargs(graph)

    def test_float_strings_coerced(self):
        out = self._kwargs_for(
            top_p="0.9", frequency_penalty="0.3", presence_penalty="0.2"
        )
        assert out["top_p"] == 0.9
        assert out["frequency_penalty"] == 0.3
        assert out["presence_penalty"] == 0.2

    def test_none_omitted(self):
        out = self._kwargs_for(top_p=None, frequency_penalty=None, presence_penalty=None)
        assert "top_p" not in out
        assert "frequency_penalty" not in out
        assert "presence_penalty" not in out


@pytest.mark.unit
class TestSamplingValidation:
    def test_top_p_bounds(self):
        from tradingagents.default_config import validate_config

        assert not validate_config({"top_p": 0.95, "frequency_penalty": -2.0})
        assert any("top_p" in v for v in validate_config({"top_p": 1.5}))
        assert any("top_p" in v for v in validate_config({"top_p": -0.1}))

    def test_penalty_bounds(self):
        from tradingagents.default_config import validate_config

        # OpenAI range is -2..2; 20 is a typo for 0.2 and must fail loudly.
        assert any("frequency_penalty" in v for v in validate_config({"frequency_penalty": 20}))
        assert any("presence_penalty" in v for v in validate_config({"presence_penalty": 20}))
        assert not validate_config({"frequency_penalty": 0.5, "presence_penalty": -0.5})
