import warnings
from abc import ABC, abstractmethod
from typing import Any

# The shared output-token cap arrives under ONE key (``max_tokens``, from
# config/env ``max_tokens`` / ``TRADINGAGENTS_MAX_TOKENS``). Each provider
# spells the request field differently: Gemini's langchain wrapper uses
# ``max_output_tokens``; the OpenAI-compatible family, Azure, Anthropic and
# Bedrock all use ``max_tokens``. One row per provider that differs.
_OUTPUT_TOKEN_PARAM = {
    "google": "max_output_tokens",
}
_DEFAULT_OUTPUT_TOKEN_PARAM = "max_tokens"


def output_token_param(provider: str | None) -> str:
    """The provider's own request-field name for the shared output-token cap."""
    key = str(provider or "").strip().lower()
    return _OUTPUT_TOKEN_PARAM.get(key, _DEFAULT_OUTPUT_TOKEN_PARAM)


def content_to_text(content) -> str:
    """Normalize LLM response content to a plain string.

    Multiple providers (OpenAI Responses API, Google Gemini 3) return content
    as a list of typed blocks, e.g. [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}].
    Downstream agents expect response.content to be a string. This extracts
    and joins the text blocks, discarding reasoning/metadata blocks. It also
    captures ``refusal`` blocks (OpenAI Responses API) and ``content``-keyed
    text blocks so a model refusal or an unusual relay shape never collapses
    to a silent empty string.

    Returns "" for None and for non-text shapes, so callers may use the result
    with ``.strip()`` without a type guard: a list-valued content used to raise
    AttributeError inside the retry paths and silently degrade to a fallback.
    """
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", "") or "")
                elif item.get("type") == "refusal":
                    texts.append(item.get("refusal", "") or "")
                elif isinstance(item.get("content"), str):
                    texts.append(item.get("content"))
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(t for t in texts if t)
    return str(content)


def normalize_content(response):
    """Normalize LLM response content to a plain string, in place.

    See ``content_to_text`` for the block shapes handled.
    """
    response.content = content_to_text(response.content)
    return response


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model: str, base_url: str | None = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    def get_provider_name(self) -> str:
        """Return the provider name used in warning messages."""
        provider = getattr(self, "provider", None)
        if provider:
            return str(provider)
        return self.__class__.__name__.removesuffix("Client").lower()

    def output_token_kwargs(self) -> dict[str, Any]:
        """The shared output-token cap, translated to this provider's field.

        Reads the unified ``max_tokens`` kwarg (config/env ``max_tokens`` /
        ``TRADINGAGENTS_MAX_TOKENS``) and returns ``{provider_param: value}`` -
        e.g. ``{"max_output_tokens": n}`` for Gemini, ``{"max_tokens": n}`` for
        OpenAI-compatible / Anthropic / Bedrock / Azure. Returns ``{}`` when the
        cap is unset, so an unconfigured run is byte-identical to today.
        """
        cap = self.kwargs.get("max_tokens")
        if cap is None:
            return {}
        return {output_token_param(self.get_provider_name()): cap}

    def warn_if_unknown_model(self) -> None:
        """Warn when the model is outside the known list for the provider."""
        if self.validate_model():
            return

        warnings.warn(
            (
                f"Model '{self.model}' is not in the known model list for "
                f"provider '{self.get_provider_name()}'. Continuing anyway."
            ),
            RuntimeWarning,
            stacklevel=2,
        )

    @abstractmethod
    def get_llm(self) -> Any:
        """Return the configured LLM instance."""
        pass

    @abstractmethod
    def validate_model(self) -> bool:
        """Validate that the model is supported by this client."""
        pass
