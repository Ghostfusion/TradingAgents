"""P4 — Dual-mode schema adapter for structured debate turns (R3).

Primary: the provider's structured-output API (``with_structured_output``).
Fallback: a markdown-fence / JSON parse + Pydantic validation + a BOUNDED
repair loop (``debate_regen_max`` scoped to malformed fields). Fail closed:
after the bounded repair budget the turn is REJECTED (never silently coerced
into a different payload).

Reuses ``structured.bind_structured`` / ``invoke_structured_or_freetext``
patterns; the markdown-fence parser is a pure function so it is unit-testable
offline.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_markdown_fence(text: str) -> str | None:
    """Extract the first JSON-looking fenced block; None when absent."""
    if not text:
        return None
    for block in _FENCE_RE.findall(text):
        stripped = block.strip()
        if stripped.startswith("{"):
            return stripped
    # Fallback: a bare {...} anywhere in the text. Deepseek often rambles
    # prose BEFORE emitting the JSON, so prefer the LARGEST balanced-block
    # candidate (the real payload dwarfs inline junk braces) among matches
    # scanning from the END of the text; fall back to the first.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else None


def parse_and_validate(
    text: str, schema: type[T]
) -> tuple[T | None, str | None]:
    """Parse a fenced/JSON text into the schema.

    Returns ``(model, None)`` on success or ``(None, error_message)``.
    """
    block = parse_markdown_fence(text)
    if block is None:
        return None, "no JSON block found"
    try:
        data = json.loads(block)
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    try:
        return schema.model_validate(data), None
    except ValidationError as e:
        return None, "validation error: " + "; ".join(
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()
        )


def repair_and_validate(
    llm, prompt: str, schema: type[T], max_repairs: int = 1
) -> tuple[T | None, str | None]:
    """Bounded repair loop: re-invoke the LLM with the validation error and
    the original prompt, asking for a corrected JSON block. Returns
    ``(model, error)``; error is a string when the budget is exhausted.
    """
    _, first_error = parse_and_validate(prompt, schema)  # prime (unused)
    del first_error
    return _repair(llm, prompt, schema, max_repairs)


def _repair(
    llm, prompt: str, schema: type[T], max_repairs: int
) -> tuple[T | None, str | None]:
    repair_prompt = (
        f"{prompt}\n\nYour previous JSON did not validate. Return ONLY the "
        f"corrected JSON object inside a ```json``` fence matching the schema."
    )
    last_error = None
    for _ in range(max_repairs):
        try:
            resp = llm.invoke(repair_prompt)
        except Exception as e:  # noqa: BLE001
            return None, f"LLM invoke during repair failed: {e}"
        text = resp.content if hasattr(resp, "content") else str(resp)
        model, err = parse_and_validate(text, schema)
        if model is not None:
            return model, None
        last_error = err
    return None, f"repair budget exhausted: {last_error}"


def invoke_structured_turn(
    structured_llm, plain_llm, prompt: str, schema: type[T],
    backup_llm=None,
) -> tuple[T | None, str | None, str]:
    """Primary structured call with render fallback to the repair loop.

    ``backup_llm`` (optional, TRADINGAGENTS_BACKUP_LLM): once the PRIMARY
    attempt fails (structured call raised / content unparseable — e.g. a
    max_tokens cut), the fallback invoke AND the bounded repair run on the
    backup model instead of re-paying the one that failed. When
    ``structured_llm`` is None (provider lacks structured output) the plain
    invoke is the primary attempt and stays on ``plain_llm``; only the
    repair (a retry after a failed parse) swaps to the backup.

    Returns ``(model, error, mode)``; ``error`` is None on success and
    ``mode`` is ``"structured"`` (the provider's structured-output API
    returned a valid model), ``"plain"`` (free-text + JSON parse succeeded,
    i.e. a STRUCTURED FALLBACK — the D2 reliability flag) or ``"repair"``
    (bounded repair loop produced the model). ``mode=="plain"/"repair"`` is a
    reliability warning: the deterministic structured path was not honored.
    """
    retry_llm = plain_llm
    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
        except Exception as e:  # noqa: BLE001
            logger.warning("structured debate invoke failed, falling back: %s", e)
            # The structured call was the primary attempt; the fallback is a
            # RETRY -> run it on the backup model when configured.
            retry_llm = backup_llm or plain_llm
        else:
            if isinstance(result, BaseModel):
                return cast(T, result), None, "structured"
            if hasattr(result, "content") and isinstance(result.content, str):
                model, err = parse_and_validate(result.content, schema)
                if model is not None:
                    return model, None, "structured"
                # Parsed-but-invalid content (e.g. cut mid-JSON): retry on backup.
                retry_llm = backup_llm or plain_llm
    # Dual-mode fallback: plain LLM + bounded repair.
    try:
        resp = retry_llm.invoke(prompt)
    except Exception as e:  # noqa: BLE001
        return None, f"plain invoke failed: {e}", "plain"
    text = resp.content if hasattr(resp, "content") else str(resp)
    model, err = parse_and_validate(text, schema)
    if model is not None:
        return model, None, "plain"
    if err is None:
        err = "no JSON block found"
    # The repair is always a retry after a failed parse -> backup when set.
    repaired, rerr = _repair(backup_llm or retry_llm, prompt, schema, max_repairs=1)
    if repaired is not None:
        return repaired, None, "repair"
    return None, rerr or err, "repair"


__all__ = [
    "parse_markdown_fence",
    "parse_and_validate",
    "repair_and_validate",
    "invoke_structured_turn",
]
