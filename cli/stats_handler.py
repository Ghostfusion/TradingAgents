import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# langchain maps the provider's prompt-cache counters into
# ``usage_metadata["input_token_details"]``: cached reads come from the
# provider's ``cached_tokens``, cache writes from ``cache_write_tokens``.
# When the response carries a service tier, langchain prefixes BOTH keys with
# it (``priority_cache_read`` / ``flex_cache_read`` — see
# ``langchain_openai._create_usage_metadata``), so every form must be read or a
# priority route silently reports zero caching. First present wins: the plain
# and prefixed forms describe the same tokens.
_CACHE_READ_KEYS = ("cache_read", "priority_cache_read", "flex_cache_read")
_CACHE_WRITE_KEYS = ("cache_creation", "priority_cache_creation", "flex_cache_creation")


def _first_present(details: dict, keys: tuple[str, ...]) -> int:
    """First present integer among ``keys`` in ``details`` (0 when none)."""
    for key in keys:
        value = details.get(key)
        if value is not None:
            return int(value or 0)
    return 0


class StatsCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        # Prompt-cache accounting: tokens READ from the provider's prefix cache
        # (billed at a discount, and the proof that prefix caching is working)
        # and tokens WRITTEN into it. Without these two the cache path is
        # unmeasurable from the UI.
        self.tokens_cached = 0
        self.tokens_cache_write = 0

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when a chat model starts."""
        with self._lock:
            self.llm_calls += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Sum token usage across all generations in the response."""
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        cache_write_tokens = 0

        for gen_list in response.generations:
            for generation in gen_list:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None) if message else None
                if not usage:
                    continue
                in_tok = usage.get("input_tokens")
                out_tok = usage.get("output_tokens")
                # Some providers only report a single total; use it as the
                # fallback so the footer doesn't undercount to zero.
                total = usage.get("total_tokens")
                if in_tok is None and out_tok is None and total is not None:
                    out_tok = total
                input_tokens += int(in_tok or 0)
                output_tokens += int(out_tok or 0)
                details = usage.get("input_token_details") or {}
                cached_tokens += _first_present(details, _CACHE_READ_KEYS)
                cache_write_tokens += _first_present(details, _CACHE_WRITE_KEYS)

        if input_tokens or output_tokens or cached_tokens or cache_write_tokens:
            with self._lock:
                self.tokens_in += input_tokens
                self.tokens_out += output_tokens
                self.tokens_cached += cached_tokens
                self.tokens_cache_write += cache_write_tokens

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Increment tool call counter when a tool starts."""
        with self._lock:
            self.tool_calls += 1

    def get_stats(self) -> dict[str, Any]:
        """Return current statistics."""
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "tokens_cached": self.tokens_cached,
                "tokens_cache_write": self.tokens_cache_write,
            }
