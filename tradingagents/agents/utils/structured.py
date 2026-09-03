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
import re as _re
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


def _looks_stub(text: str) -> bool:
    """Is a free-text fallback response a degenerate stub (no usable body)?

    A model that misses structured output can answer with only a section
    header (e.g. ``**Decision``) or whitespace; downstream that silently
    becomes an empty final decision in the reports and memory log. Return
    True only for such degenerate responses (empty, a single label token, or
    fewer than ~2 words of actual content after stripping markdown
    decorators), never for real prose.
    """
    t = (text or "").strip()
    if not t:
        return True
    body = _re.sub(r"[#*_`|>\-]", "", t)
    words = [w for w in body.split() if not _re.fullmatch(r"[\W_]+", w)]
    if len(words) < 2:
        return True
    return bool(len(" ".join(words)) < 12 and ":" not in t)


def _stub_completion_prompt(original: Any) -> str:
    """Ask a model that produced only a header/stub to write the real body.

    The stub retry re-invokes with the original instructions + evidence so a
    context-light model still has everything it needs to deliver the decision
    (mirrors ``_continuation_prompt``'s grounding-by-context approach).
    """
    text = original if isinstance(original, str) else str(original)
    return (
        "Your previous response contained only a section header or label "
        "with no actual decision content. Re-read the instructions and "
        "evidence below and produce the COMPLETE decision now: the "
        "recommendation, position action, and reasoning. Cite only computed "
        "values you were given; state 'unavailable' where none exist. Do not "
        "echo the instructions back.\n\n"
        "INSTRUCTIONS + EVIDENCE:\n" + text[:4000]
    )


def _model_name(llm: Any) -> str:
    """Best-effort model name for logs; '' when unreadable."""
    for attr in ("model_name", "model", "model_id", "name"):
        try:
            v = getattr(llm, attr, None)
            if v:
                return str(v)
        except Exception:  # noqa: BLE001
            continue
    return ""


def _retry_if_stub(plain_llm: Any, prompt: Any, response_text: str, agent_name: str,
                   fallback_llm: Any | None = None) -> str:
    """A stub free-text fallback is not a usable decision.

    The structured->free-text path can carry back a bare stub (live runs have
    landed a lone ``**Decision`` in the final report). Re-invoke with a
    completion directive; if the retry is still degenerate, return an explicit
    'unavailable' notice instead of an empty decision.

    ``fallback_llm`` (optional): when the structured+free-text chain failed on
    the model (a repeated no-parse/degenerate case), the FIRST stub retry runs
    on this fallback model (e.g. the quick tier) instead of the same flaky
    model — the degeneration-loop cost killer. A default of None keeps today's
    behavior; the swap is skipped when the fallback is the same model.
    """
    text = response_text or ""
    attempts = 0
    if not _looks_stub(text):
        return text
    # 1st retry: fallback model when provided and different (model swap on
    # fail - avoids re-paying the premium tier for a likely-repeat failure).
    try:
        if fallback_llm is not None and fallback_llm is not plain_llm:
            logger.info(
                "%s: stub after structured fail - retrying on fallback model %r",
                agent_name, _model_name(fallback_llm) or fallback_llm,
            )
            resp = fallback_llm.invoke(_stub_completion_prompt(prompt))
            nxt = resp.content if hasattr(resp, "content") else str(resp)
            attempts += 1
            if nxt and nxt.strip() and not _looks_stub(nxt):
                return nxt
            text = nxt if nxt and nxt.strip() else text
    except Exception as exc:  # noqa: BLE001 - a failed fallback degrades
        logger.warning("%s: fallback-model stub retry failed: %s", agent_name, exc)
    # Remaining budget on the original model.
    for _ in range(max(0, _MAX_TRUNCATION_RETRIES - attempts)):
        if not _looks_stub(text):
            return text
        try:
            resp = plain_llm.invoke(_stub_completion_prompt(prompt))
            nxt = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:  # noqa: BLE001 - a failed retry degrades
            logger.warning("%s: stub-completion retry failed: %s", agent_name, exc)
            break
        if not nxt or not nxt.strip():
            break
        text = nxt
    if _looks_stub(text):
        logger.warning(
            "%s: free-text fallback returned an empty/stub response; "
            "emitting an explicit unavailable decision",
            agent_name,
        )
        return (
            "**Decision**: unavailable — the model returned an incomplete "
            "response after the structured-output fallback. The prior "
            "research and risk debate stand; re-run to regenerate the final "
            "decision."
        )
    return text


_ANALYST_STATUS_TURN_RE = _re.compile(
    r"\b(progress|let me (now )?(continue|gather|fetch|pull|collect|check|dig))\b",
    _re.IGNORECASE,
)

# Directive for the analyst-stub retry: write the COMPLETE report from the
# tool evidence already gathered (the messages carry every tool result the
# model asked for), never another status turn.
_STUB_CHAIN_COMPLETION_PROMPT = (
    "Your previous response was only a status/progress note, not the report. "
    "Re-read the tool evidence you have gathered and write the COMPLETE "
    "analysis report now: verdict, signal-by-signal evidence with exact "
    "computed numbers, risks, and a clear stance. Cite only values you "
    "actually retrieved; state 'unavailable' where none exist. Do not "
    "announce further tool calls - deliver the report."
)


def _looks_report_stub(text: str) -> bool:
    """Is an analyst report a degenerate stub (no report substance)?

    Like ``_looks_stub`` for decisions, but catches the analyst-chain
    pathology: a model that answers a tool loop with a bare *status turn*
    ("Good progress. Now let me gather the remaining signals ...") instead of
    the report. Such a turn emits no tool_calls, so the router treats it as
    final and it would land in ``*_report`` verbatim (observed: a 217-byte
    fundamentals report). Detection: any degenerate stub OR a short
    status-announcement sentence. Real analyst reports are long by design
    ("comprehensive report ... as much detail as possible"); a one-line
    progress note is not one.
    """
    t = (text or "").strip()
    if not t:
        return True
    if _looks_stub(t):
        return True
    return len(t) < 400 and bool(_ANALYST_STATUS_TURN_RE.search(t))


def retry_chain_if_stub(chain: Any, messages: Any, response_text: str, agent_name: str) -> str:
    """Re-invoke a tool-calling chain when its final report is a degenerate stub.

    Mirrors ``_retry_if_stub`` for the analyst chain path: a model that ran a
    tool loop and then returned only a status turn or a bare header must be
    asked ONCE to write the complete report from the evidence already in
    ``messages`` (it may call more tools if it needs data). If the retry is
    still degenerate, return an explicit unavailable notice - never an empty
    or one-line report that downstream would render as truth.
    """
    text = response_text or ""
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_report_stub(text):
            return text
        try:
            from langchain_core.messages import HumanMessage

            cont = chain.invoke([*messages, HumanMessage(content=_STUB_CHAIN_COMPLETION_PROMPT)])
            text = cont.content if hasattr(cont, "content") else str(cont)
        except Exception as exc:  # noqa: BLE001 - failed retry degrades
            logger.warning("%s: chain stub-completion retry failed: %s", agent_name, exc)
            break
        if not text or not text.strip():
            break
    if _looks_report_stub(text):
        logger.warning(
            "%s: analyst returned a status-turn stub; emitting unavailable report",
            agent_name,
        )
        return (
            "**Report unavailable** — the analyst returned a degenerate status "
            f"stub ({(text[:80]).strip() or 'empty'}). The prior tool evidence "
            "stands; re-run to regenerate the full report."
        )
    return text


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


def finalize_messages(chain: Any, messages: Any, result: Any) -> str:
    """Force a terminal report turn when an analyst hit its tool-round cap.

    The analyst routers force back to the analyst node after
    ``MAX_TOOL_ROUNDS`` tool rounds; on that turn the model must produce the
    final report instead of more tool calls (the dangling tool_calls are
    stripped here). The evidence gathered so far stays in ``messages``, so the
    model writes the report from what it has - never an empty string, never an
    invented value. Degrades to the current turn's content on any failure so
    the pipeline never blocks.
    """
    if not getattr(result, "tool_calls", None):
        # No cap turn: normal path unchanged.
        return result.content if hasattr(result, "content") else str(result)
    try:
        # Strip the dangling tool_calls on the last message so the model must
        # answer with prose, then run one final turn.
        from langchain_core.messages import AIMessage

        last = messages[-1]
        cleaned_tail = AIMessage(
            content=getattr(last, "content", "") or "",
            id=getattr(last, "id", None),
            name=getattr(last, "name", None),
        )
        cleaned_msgs = [*messages[:-1], cleaned_tail]
        final = chain.invoke(cleaned_msgs)
        text = final.content if hasattr(final, "content") else str(final)
        if text and text.strip():
            return _retry_if_truncated(chain, cleaned_msgs, text)
        return text
    except Exception as exc:  # noqa: BLE001 - degrade, never raise mid-run
        logger.warning("final-report turn after tool cap failed: %s", exc)
        return result.content if hasattr(result, "content") else str(result)


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
    fallback_llm: Any | None = None,
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
            rendered = render(result)
            # Enforce completeness on the structured-success path too: a model
            # can hit max_tokens mid-render and still parse into the schema,
            # in which case render() ends mid-sentence and only the report
            # marker would catch it. Merge a continuation exactly like the
            # free-text path (no-op when the render is complete — the extra
            # _looks_truncated check costs nothing).
            return _retry_if_truncated(plain_llm, prompt, rendered)
        except Exception as exc:
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name,
                exc,
            )

    response = plain_llm.invoke(prompt)
    response_text = response.content if hasattr(response, "content") else str(response)
    # Enforce completeness: cut-at-cap -> continuation merge.
    response_text = _retry_if_truncated(plain_llm, prompt, response_text)
    # Harden: a bare header/stub is not a usable decision. Regenerate once;
    # if still degenerate, return an explicit 'unavailable' notice so a
    # structured-output miss can never silently produce an empty decision.
    return _retry_if_stub(plain_llm, prompt, response_text, agent_name, fallback_llm=fallback_llm)


def retry_structured_missing_fields(
    structured_llm: Any,
    prompt: Any,
    result: T,
    render: Callable[[T], str],
    agent_name: str,
    mandatory_fields: tuple[str, ...],
    max_retries: int = 1,
) -> str:
    """DSA-style per-field integrity retry (research §3.2, pillar 4).

    When the structured result is missing a mandatory field, re-invoke with a
    TARGETED rebuild: the original prompt + the prior response + a per-field
    spec of exactly what is missing — not a blind re-roll. Returns the render
    of the repaired result (or the prior render when the retry fails / the
    field appears absent after retry, so the pipeline never blocks).
    """
    missing = [f for f in mandatory_fields if getattr(result, f, None) in (None, "", [])]
    if not missing:
        return render(result)
    current = result
    for _ in range(max_retries):
        still = [f for f in missing if getattr(current, f, None) in (None, "", [])]
        if not still:
            break
        spec = "; ".join(f"{f} must be present and non-empty" for f in still)
        retry_prompt = (
            f"{prompt}\n\n---\nYour previous response was parsed into the "
            f"schema but is missing required field(s): {spec}.\nPrevious "
            f"response:\n{render(current)}\n\nRe-send the COMPLETE decision "
            f"including the missing field(s)."
        )
        try:
            repaired = structured_llm.invoke(retry_prompt)
            if repaired is None:
                continue
            current = repaired
        except Exception as exc:  # noqa: BLE001 - degrade, never raise
            logger.warning("%s: integrity retry failed: %s", agent_name, exc)
            break
    return render(current)

