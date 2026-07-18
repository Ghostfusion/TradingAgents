import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class StatsCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

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

        if input_tokens or output_tokens:
            with self._lock:
                self.tokens_in += input_tokens
                self.tokens_out += output_tokens

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
            }
