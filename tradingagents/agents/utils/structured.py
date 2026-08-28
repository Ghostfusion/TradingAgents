"""Shared helpers for invoking an agent with structured output and a graceful fallback.

The Portfolio Manager, Trader, and Research Manager all follow the same
canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. If the provider does
   not support structured output (rare; mostly older Ollama models), the
   wrap is skipped and the agent uses free-text generation instead.
2. At invocation, run the structured call and render the result back to
   markdown. If the structured call itself fails for any reason
   (malformed JSON from a weak model, transient provider issue), fall
   back to a plain ``llm.invoke`` so the pipeline never blocks.

Centralising the pattern here keeps the agent factories small and ensures
all three agents log the same warnings when fallback fires.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Schema-only structured output binds exactly one tool (the schema itself), so a
# model that reaches for a search tool emits an unknown tool call and the whole
# structured attempt is discarded for a free-text retry. Agents on this path
# state the constraint explicitly rather than relying on the binding alone
# (#1130).
NO_EXTERNAL_TOOLS = (
    "Use only the evidence provided in this prompt. Do not call external tools "
    "or search the web; if something is missing, say so explicitly."
)


# Max continuation attempts before giving up (each is one extra LLM call, only
# when the previous response was detected as truncated).
_MAX_TRUNCATION_RETRIES = 2


def _looks_truncated(text: str) -> bool:
    """Heuristic: does an LLM report end mid-sentence (max_tokens cut)?

    Mirrors ``reporting._looks_truncated`` (kept here so the retry path does
    not import the reporting module, which pulls in the whole report writer).
    Conservative on purpose: only flags endings that are neither sentence
    punctuation nor a clean markdown construct (table row, bold/italic, code
    fence, heading, closing bracket/quote, or a bold-label line like
    ``**Consensus**: High``). A report ending in a bare lowercase word is
    almost always a cut — the model was stopped before it could finish the
    sentence. The minimum length keeps terse strings (test fixtures, one-line
    verdicts) from being mis-flagged.
    """
    t = (text or "").rstrip()
    if not t or len(t) < 120:
        return False
    last = t[-1]
    if last in ".!?;:":
        return False
    if last in "|*`#)]}>\"'":
        return False
    last_line = t.rsplit("\n", 1)[-1]
    if "**:" in last_line:
        return False
    return last.islower() or last.isdigit()


def _continuation_prompt(truncated: str) -> str:
    """Build a continuation prompt from a truncated response.

    The model was cut off mid-sentence; feed it the tail it already wrote and
    ask it to continue from exactly where it stopped, so the continuation
    merges cleanly (no restating the beginning).
    """
    tail = truncated.rstrip()[-400:]
    return (
        "Your previous response was cut off at the output limit. Continue "
        "exactly from where you stopped — do NOT restate anything you already "
        "wrote. Here is the tail of your previous response:\n\n"
        f"...{tail}\n\n"
        "Continue from the last incomplete sentence and finish the report. "
        "Keep the same style and structure."
    )


def _retry_if_truncated(plain_llm: Any, prompt: Any, response_text: str) -> str:
    """Re-invoke the LLM when the response was cut at the output cap.

    ``max_tokens`` is a ceiling, not a floor — the model writes what it wants
    and the API stops it mid-sentence. This is the enforcement: detect the cut
    (``_looks_truncated``) and re-invoke with a continuation prompt, merging
    the continuation into the full text. Up to ``_MAX_TRUNCATION_RETRIES``
    attempts; each is one extra LLM call, only when a cut was detected.
    """
    full = response_text or ""
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_truncated(full):
            break
        try:
            cont = plain_llm.invoke(_continuation_prompt(full))
            cont_text = cont.content if hasattr(cont, "content") else str(cont)
        except Exception as exc:  # noqa: BLE001 - a failed continuation degrades
            logger.warning("truncation continuation failed: %s", exc)
            break
        if not cont_text or not cont_text.strip():
            break
        # Merge: drop the tail we already fed back, then append the continuation.
        full = full.rstrip() + "\n" + cont_text.strip()
    return full


def retry_chain_if_truncated(chain: Any, messages: Any, response_text: str) -> str:
    """Re-invoke a tool-calling chain when its final content was cut.

    The analyst nodes run ``chain = prompt | llm.bind_tools(tools)`` and take
    ``result.content`` when no tool calls remain. If that content was cut at
    the output cap, re-invoke the chain with a continuation message so the
    model finishes the report (it may call more tools if it needs data).
    """
    full = response_text or ""
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_truncated(full):
            break
        try:
            from langchain_core.messages import HumanMessage

            cont = chain.invoke([*messages, HumanMessage(content=_continuation_prompt(full))])
            cont_text = cont.content if hasattr(cont, "content") else str(cont)
        except Exception as exc:  # noqa: BLE001 - a failed continuation degrades
            logger.warning("chain truncation continuation failed: %s", exc)
            break
        if not cont_text or not cont_text.strip():
            break
        full = full.rstrip() + "\n" + cont_text.strip()
    return full


def retry_llm_if_truncated(llm: Any, prompt: Any, response_text: str) -> str:
    """Re-invoke a plain LLM when its response was cut at the output cap.

    The researchers / risk debators call ``llm.invoke(prompt)`` directly and
    wrap the content in a speaker prefix. This retries the raw content with a
    continuation prompt and merges, so the debate argument is not truncated.
    """
    return _retry_if_truncated(llm, prompt, response_text)


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Any | None:
    """Return ``llm.with_structured_output(schema)`` or ``None`` if unsupported.

    Logs a warning when the binding fails so the user understands the agent
    will use free-text generation for every call instead of one-shot fallback.
    """
    try:
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        logger.warning(
            "%s: provider does not support with_structured_output (%s); "
            "falling back to free-text generation",
            agent_name,
            exc,
        )
        return None


def invoke_structured_or_freetext(
    structured_llm: Any | None,
    plain_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
    result_hook: Callable[[Any], None] | None = None,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape). The same value is forwarded to the free-text path so the
    fallback sees the same input the structured call did.
    """
    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
            if result is None:
                # A thinking model can answer in plain text instead of calling
                # the tool, leaving the parser with nothing to return. Treat it
                # as a structured miss and fall back, with a clear reason.
                raise ValueError("structured output returned no parsed result")
            if result_hook is not None:
                result_hook(result)
            return render(result)
        except Exception as exc:
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name,
                exc,
            )

    response = plain_llm.invoke(prompt)
    response_text = response.content if hasattr(response, "content") else str(response)
    # Enforce completeness: if the response was cut at the output cap, re-invoke
    # with a continuation prompt and merge (max_tokens is a ceiling, not a
    # floor — this is what guarantees the agent's report is not truncated).
    return _retry_if_truncated(plain_llm, prompt, response_text)
