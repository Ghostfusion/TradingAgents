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


# Cache-read multiplier on the input rate, per model prefix (OpenRouter's
# documented per-provider cache pricing). A cache READ is billed at this share
# of the normal input price; cache WRITES are billed at the normal input price
# for the providers used here (DeepSeek writes = 1.0x, Anthropic = 1.25x).
# Unlisted model -> None, and the caller prices cached tokens at the FULL input
# rate: an over-estimate is the honest failure mode for a cost figure.
_CACHE_READ_MULTIPLIER: dict[str, float] = {
    "deepseek": 0.10,
    "claude": 0.10,
    "gemini": 0.25,
    "grok": 0.25,
    "qwen": 0.10,
    "moonshot": 0.25,
}


def cache_read_multiplier(model: str) -> float | None:
    """Cache-READ price share of the input rate; None when unlisted."""
    m = str(model or "").lower()
    if not m:
        return None
    for prefix, mult in sorted(_CACHE_READ_MULTIPLIER.items(), key=lambda kv: -len(kv[0])):
        if m.startswith(prefix):
            return mult
    return None


def estimate_cost(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = None,
) -> float | None:
    """Estimated USD for one call/run; None when model or token counts unknown.

    ``cached_input_tokens`` (part of ``input_tokens``, not additive) are priced
    at the provider's documented cache-read share — 0.1x input for DeepSeek, the
    model this repo runs. Unknown model -> cached tokens priced at the full input
    rate (deliberately conservative).
    """
    if not model or input_tokens is None or output_tokens is None:
        return None
    rate = rate_for(model)
    if rate is None:
        return None
    cached = max(0, min(int(cached_input_tokens or 0), int(input_tokens)))
    multiplier = cache_read_multiplier(model)
    if multiplier is None:
        # Unknown cache pricing for this model: bill the whole input at the
        # input rate rather than inventing a discount (over-estimate).
        cached, multiplier = 0, 0.0
    fresh = int(input_tokens) - cached
    return (
        (fresh / 1_000_000.0) * rate[0]
        + (cached / 1_000_000.0) * rate[0] * multiplier
        + (output_tokens / 1_000_000.0) * rate[1]
    )


__all__ = [
    "rate_for",
    "cache_read_multiplier",
    "estimate_cost",
    "_RATE_TABLE",
    "_CACHE_READ_MULTIPLIER",
]
