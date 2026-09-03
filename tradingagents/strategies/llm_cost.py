"""LLM cost estimation (W1-8): quality-per-dollar measurement.

A provider rate table (USD per 1M input/output tokens) + a pure
``estimate_cost`` that returns an honest estimate or None when the model
isn't in the table. Advisory: the actual bill is the provider's; this is
for scorecard/run-card transparency only.

Rates are indicative provider list prices (accurate enough for relative
quality-per-dollar comparisons; never a billing claim).
"""

from __future__ import annotations

# USD per 1M tokens: {model-prefix: (in, out)}. Unlisted models -> None
# (honest "unknown", never a guessed rate).
_RATE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-": (2.50, 10.00),
    "gpt-4": (30.00, 60.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-5": (1.25, 10.00),
    "claude-": (3.00, 15.00),
    "claude-3-opus": (15.00, 75.00),
    "deepseek": (0.27, 1.10),
    "gemini": (1.25, 5.00),
    "mistral": (0.24, 1.00),
    "llama": (0.15, 0.60),
    "qwen": (0.23, 0.90),
}


def rate_for(model: str) -> tuple[float, float] | None:
    """(in, out) USD-per-1M for a model name; None when unlisted (honest)."""
    m = str(model or "").lower()
    if not m:
        return None
    for prefix, rate in sorted(_RATE_TABLE.items(), key=lambda kv: -len(kv[0])):
        if m.startswith(prefix):
            return rate
    return None


def estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """Estimated USD for one call/run; None when model or token counts unknown."""
    if not model or input_tokens is None or output_tokens is None:
        return None
    rate = rate_for(model)
    if rate is None:
        return None
    return (input_tokens / 1_000_000.0) * rate[0] + (output_tokens / 1_000_000.0) * rate[1]


__all__ = ["rate_for", "estimate_cost", "_RATE_TABLE"]
