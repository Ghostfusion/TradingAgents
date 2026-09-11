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

from tradingagents.llm_clients.base_client import content_to_text

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

# Repetition-loop guard (degenerate generation that pads toward max_tokens):
# a run of >= these identical full lines is treated as an autoregressive
# attractor loop and trimmed BEFORE the continuation prompt so the loop is
# never fed back as context.
_REPETITION_MIN_REPS = 3
_REPETITION_MIN_LINE = 8


def _repetition_loop_cut(text: str) -> tuple[str, bool]:
    """Trim a degenerately-repeating block from ``text``; return (text, flag).

    The max_tokens-padding failure mode is the model emitting the same block
    over and over until the cap. This detects a run of ``>= _REPETITION_MIN_REPS``
    identical, non-trivial consecutive full lines — the unambiguous signature
    of such a loop — and trims ``text`` at the FIRST occurrence, so the
    continuation prompt receives a clean prefix and the loop is never re-fed.

    Conservative on purpose: only exact duplicate consecutive lines (legitimate
    repeated section headers/table rows with different bodies are untouched),
    only runs of >= 3, only lines of real length. Returns ``(text, False)``
    unchanged otherwise.
    """
    t = (text or "")
    lines = t.splitlines()
    n = len(lines)
    if n < _REPETITION_MIN_REPS:
        return t, False
    start = 0
    while start < n:
        line = lines[start]
        if len(line.strip()) < _REPETITION_MIN_LINE:
            start += 1
            continue
        end = start
        while end + 1 < n and lines[end + 1] == line:
            end += 1
        run = end - start + 1
        if run >= _REPETITION_MIN_REPS:
            prefix = "\n".join(lines[:start]).rstrip()
            logger.warning(
                "repetition loop detected: line repeated %d times (len %d); "
                "trimming %d chars before continuation",
                run,
                len(line),
                len(t) - len(prefix),
            )
            return prefix, True
        start = end + 1
    return t, False


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


def _retry_if_truncated(plain_llm: Any, prompt: Any, response_text: str,
                        backup_llm: Any | None = None) -> str:
    """Re-invoke the LLM when the response was cut at the output cap.

    ``max_tokens`` is a ceiling, not a floor — the model writes what it wants
    and the API stops it mid-sentence. This is the enforcement: detect the cut
    (``_looks_truncated``) and re-invoke with a continuation prompt, merging
    the continuation into the full text. Up to ``_MAX_TRUNCATION_RETRIES``
    attempts; each is one extra LLM call, only when a cut was detected.

    ``backup_llm`` (optional): once a cut is detected, the continuation retries
    run on this model instead of the truncated one (``TRADINGAGENTS_BACKUP_LLM``
    in the graph) — the flaky model that hit the cap is not re-paid for the
    repair. A default of None keeps today's same-model behavior; the swap is
    skipped when the backup is the same object.
    """
    full = response_text or ""
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_truncated(full):
            break
        full, _looped = _repetition_loop_cut(full)
        retry_llm = plain_llm
        if backup_llm is not None and backup_llm is not plain_llm:
            retry_llm = backup_llm
            logger.info(
                "truncated response detected; continuing on backup model %r",
                _model_name(backup_llm) or backup_llm,
            )
        try:
            cont = retry_llm.invoke(_continuation_prompt(full))
            cont_text = content_to_text(getattr(cont, "content", cont))
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
        "INSTRUCTIONS + EVIDENCE:\n" + text[:8000]
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
                   fallback_llm: Any | None = None, backup_llm: Any | None = None) -> str:
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

    ``backup_llm`` (optional): ALL remaining stub retries run on this model
    (``TRADINGAGENTS_BACKUP_LLM``) instead of the original — a model that
    keeps returning stubs must never be re-paid for the repair (the
    hy4-preview 20-call back-to-back burst on 2026-09-09 was the same-model
    stub loop). The swap is skipped when the backup is the same object.
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
            nxt = content_to_text(getattr(resp, "content", resp))
            attempts += 1
            if nxt and nxt.strip() and not _looks_stub(nxt):
                return nxt
            text = nxt if nxt and nxt.strip() else text
    except Exception as exc:  # noqa: BLE001 - a failed fallback degrades
        logger.warning("%s: fallback-model stub retry failed: %s", agent_name, exc)
    # Remaining budget on the BACKUP model (never the original — a stub loop
    # on the same model is the infinite-retry cost killer).
    retry_llm = backup_llm if (backup_llm is not None and backup_llm is not plain_llm) else None
    for _ in range(max(0, _MAX_TRUNCATION_RETRIES - attempts)):
        if not _looks_stub(text):
            return text
        if retry_llm is None:
            break
        try:
            logger.info(
                "%s: stub retry on backup model %r",
                agent_name, _model_name(retry_llm) or retry_llm,
            )
            resp = retry_llm.invoke(_stub_completion_prompt(prompt))
            nxt = content_to_text(getattr(resp, "content", resp))
        except Exception as exc:  # noqa: BLE001 - a failed retry degrades
            logger.warning("%s: backup stub-completion retry failed: %s", agent_name, exc)
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

# Directive for the cap-forced terminal turn when it came back EMPTY (no text at
# all — e.g. a reasoning model burned its whole output budget on hidden
# reasoning and emitted no content). Ask the model (prefer the backup when
# configured) to write the complete report from the tool evidence already
# gathered, never another empty/status turn.
_EMPTY_CAP_PROMPT = (
    "Your previous response was empty - no report text was produced. "
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


def retry_chain_if_stub(chain: Any, messages: Any, response_text: str, agent_name: str,
                        backup_chain: Any | None = None) -> str:
    """Re-invoke a tool-calling chain when its final report is a degenerate stub.

    Mirrors ``_retry_if_stub`` for the analyst chain path: a model that ran a
    tool loop and then returned only a status turn or a bare header must be
    asked ONCE to write the complete report from the evidence already in
    ``messages`` (it may call more tools if it needs data). If the retry is
    still degenerate, return an explicit unavailable notice - never an empty
    or one-line report that downstream would render as truth.

    ``backup_chain`` (optional): the retries run on this chain (bound to
    ``TRADINGAGENTS_BACKUP_LLM``) instead of the original — a model that keeps
    returning stubs must never be re-paid for the repair (the 2026-09-09
    hy4-preview back-to-back burst was the same-model stub loop). The swap is
    skipped when the backup is the same object.
    """
    text = response_text or ""
    retry_chain = backup_chain if (backup_chain is not None and backup_chain is not chain) else None
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_report_stub(text):
            return text
        if retry_chain is None:
            break
        try:
            from langchain_core.messages import HumanMessage

            history = _deorphan_tool_calls(messages)
            cont = retry_chain.invoke([*history, HumanMessage(content=_STUB_CHAIN_COMPLETION_PROMPT)])
            text = content_to_text(getattr(cont, "content", cont))
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


def _deorphan_tool_calls(messages: list) -> list:
    """Return the conversation with every assistant tool call fulfilled.

    Strict tool-calling backends (OpenAI / Azure through the OpenRouter
    relay) hard-400 a request whose history contains an assistant turn with
    a ``tool_calls`` entry that has no matching tool output — "No tool
    output found for function call <id>" (observed on the cap-forced
    final-report retry, TSM 2026-09-07). The analyst tool loop can leave
    exactly that in ``messages``: one assistant reply may request several
    tools while the loop executes only the first (the rest never get a
    ToolMessage), or the tool-round cap forces the terminal turn before a
    reply's calls land. Strip the unfulfilled calls from that turn — never
    fabricate a result — so the history is valid for any model. Turns
    without orphaned calls pass through untouched (same objects).

    Callers keep the returned list; if no call was stripped the original
    objects are returned so retries stay byte-identical.

    When a call IS stripped, logs the offending call ids — the agent-turn
    index and the ids actually kept — so a production hit reveals the real
    orphan mechanism (id reuse / relay id-mangling / single-output-of-multi-
    call), not just a swallowed defect.
    """
    from langchain_core.messages import AIMessage, ToolMessage

    fulfilled = {
        tm.tool_call_id
        for tm in messages
        if isinstance(tm, ToolMessage) and tm.tool_call_id
    }
    out: list = []
    changed = False
    for idx, m in enumerate(messages):
        calls = list(getattr(m, "tool_calls", None) or [])
        if not calls:
            out.append(m)
            continue
        kept = [c for c in calls if (c.get("id") or "") in fulfilled]
        if len(kept) == len(calls):
            out.append(m)
            continue
        changed = True
        stripped = [c for c in calls if (c.get("id") or "") not in fulfilled]
        logger.warning(
            "de-orphaning %d unfulfilled tool call(s) at message[%d] "
            "(kept=%s stripped=%s): "
            "%s",
            len(stripped), idx, [c.get("id") for c in kept],
            [c.get("id") for c in stripped],
            "; ".join(
                f"call {c.get('id')!r} (tool {c.get('name')!r}) has no tool "
                f"output in the history"
                for c in stripped
            ),
        )
        out.append(
            AIMessage(
                content=m.content or "",
                id=m.id,
                name=m.name,
                tool_calls=kept,
            )
        )
    return out if changed else messages


def retry_chain_if_truncated(chain: Any, messages: Any, response_text: str,
                             backup_chain: Any | None = None) -> str:
    """Re-invoke a tool-calling chain when its final content was cut.

    The analyst nodes run ``chain = prompt | llm.bind_tools(tools)`` and take
    ``result.content`` when no tool calls remain. If that content was cut at
    the output cap, re-invoke the chain with a continuation message so the
    model finishes the report (it may call more tools if it needs data).

    ``backup_chain`` (optional): same shape as ``chain`` but bound to the
    backup model (``TRADINGAGENTS_BACKUP_LLM``); the continuation retries run
    on it instead of the truncated chain. A default of None keeps today's
    same-model behavior; the swap is skipped when backup == chain.
    """
    full = response_text or ""
    for _ in range(_MAX_TRUNCATION_RETRIES):
        if not _looks_truncated(full):
            break
        full, _looped = _repetition_loop_cut(full)
        cont_chain = chain
        if backup_chain is not None and backup_chain is not chain:
            cont_chain = backup_chain
        try:
            from langchain_core.messages import HumanMessage

            # A strict backend 400s a history with an unfulfilled tool call;
            # strip orphans before the continuation re-invoke (same guard as
            # ``_deorphan_tool_calls`` in ``finalize_messages``).
            history = _deorphan_tool_calls(messages)
            cont = cont_chain.invoke([*history, HumanMessage(content=_continuation_prompt(full))])
            cont_text = content_to_text(getattr(cont, "content", cont))
        except Exception as exc:  # noqa: BLE001 - a failed continuation degrades
            logger.warning("chain truncation continuation failed: %s", exc)
            break
        if not cont_text or not cont_text.strip():
            break
        full = full.rstrip() + "\n" + cont_text.strip()
    return full


def retry_llm_if_truncated(llm: Any, prompt: Any, response_text: str,
                           backup_llm: Any | None = None) -> str:
    """Re-invoke a plain LLM when its response was cut at the output cap.

    The researchers / risk debators call ``llm.invoke(prompt)`` directly and
    wrap the content in a speaker tag. This retries the raw content with a
    continuation prompt and merges, so the debate argument is not truncated.
    ``backup_llm`` (optional) reroutes the continuation onto the backup model
    (see ``_retry_if_truncated``).
    """
    return _retry_if_truncated(llm, prompt, response_text, backup_llm=backup_llm)


def _terminal_turn_max_tokens() -> int | None:
    """Output budget to grant a cap-forced repair turn (2x the configured cap).

    Reasoning tokens share ``max_tokens``, so a reasoning model can spend the
    WHOLE budget on hidden reasoning and emit no content at all - the empty
    cap-forced terminal turn. Granting the repair turn twice the configured cap
    leaves room for the reasoning plus the report that follows it.

    Measured (GOOG, deepseek-v4.1-flash, reasoning_effort=high, 44k-token
    evidence context): at the configured 16000 cap the turn stopped at exactly
    16000 output tokens with ``finish_reason="length"``; the same input at
    32000 finished naturally (19696 output tokens, 6691 of them reasoning).

    Returns None when no cap is configured (the provider default applies).
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - advisory; no override when unknown
        return None
    cap = cfg.get("max_output_tokens_quick") or cfg.get("max_output_tokens")
    try:
        cap = int(cap)
    except (TypeError, ValueError):
        return None
    if cap <= 0:
        return None
    return cap * 2


def finalize_messages(chain: Any, messages: Any, result: Any,
                      backup_chain: Any | None = None,
                      agent_name: str = "",
                      plain_chain: Any | None = None,
                      backup_plain_chain: Any | None = None) -> str:
    """Force a terminal report turn when an analyst hit its tool-round cap.

    The analyst routers force back to the analyst node after
    ``MAX_TOOL_ROUNDS`` tool rounds; on that turn the model must produce the
    final report instead of more tool calls (the dangling tool_calls are
    stripped here). The evidence gathered so far stays in ``messages``, so the
    model writes the report from what it has - never an empty string, never an
    invented value. Degrades to the current turn's content on any failure so
    the pipeline never blocks.

    ``backup_chain`` (optional): the cap-forced terminal turn's truncation
    continuation runs on this chain (backup model) - see
    ``retry_chain_if_truncated``.

    ``agent_name`` (optional): the role whose report this turn produces. Used
    for the log lines and the forensic journal entry, so an empty terminal turn
    can be traced to the analyst that burned its budget.

    ``plain_chain`` / ``backup_plain_chain`` (optional): the same prompt bound
    to the same model WITHOUT tools. The terminal turn runs on the tool-less
    chain, because a relay that ignores ``tool_choice="none"`` can answer the
    forced turn with yet another tool call, whose content is empty - measured
    2026-09-11 through OpenRouter (`finish_reason="tool_calls"`, 467 output
    tokens): the "empty terminal turn" notice was a model still asking for
    tools, not a token burn. Without a plain chain the bound chain is used
    (unchanged legacy behavior) and the repair loop below is the only net.

    An EMPTY terminal turn is repaired on a different chain with a doubled
    output budget before degrading to the unavailable notice. Rationale:
    reasoning tokens share ``max_tokens``, so the model can spend the whole
    budget on hidden reasoning and emit no text; re-asking the same question
    with the same cap on the same chain reproduces the same burn. At most two
    repair attempts (backup first, then the primary).
    """
    if not getattr(result, "tool_calls", None):
        # No cap turn: normal path unchanged.
        return content_to_text(getattr(result, "content", result))
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
        # A strict backend (OpenAI/Azure via OpenRouter) 400s a history that
        # carries an unfulfilled tool call ("No tool output found for function
        # call <id>"). The tool loop can leave earlier multi-call turns
        # half-executed, so de-orphan BEFORE any re-invoke: the terminal turn,
        # its truncation continuation AND the backup empty-retry all see a
        # valid history (regression: TSM 2026-09-07 cap retry).
        cleaned_msgs = _deorphan_tool_calls(cleaned_msgs)
        term_chain = plain_chain if plain_chain is not None else chain
        final = term_chain.invoke(cleaned_msgs)
        text = content_to_text(getattr(final, "content", final))
        if text.strip():
            return _retry_if_truncated(term_chain, cleaned_msgs, text,
                                       backup_llm=backup_plain_chain or backup_chain)
        # Cap-forced terminal turn came back empty: no usable report text.
        # Repair on a different chain with a RAISED output budget (see
        # ``_terminal_turn_max_tokens``); only then emit the explicit
        # unavailable notice - never a silent "" that downstream would render
        # as a bare report-unavailable placeholder (QCOM fundamentals / NXPI
        # market 2026-09-07).
        from langchain_core.messages import HumanMessage

        repair_msgs = [*cleaned_msgs, HumanMessage(content=_EMPTY_CAP_PROMPT)]
        raised_cap = _terminal_turn_max_tokens()
        candidates: list[tuple[str, Any]] = []
        for label, bound_chain, plain in (
            ("backup model", backup_chain, backup_plain_chain),
            ("primary model", chain, plain_chain),
        ):
            for suffix, cand in ((" (tools unbound)", plain), ("", bound_chain)):
                if cand is None or any(cand is c for _, c in candidates):
                    continue
                candidates.append((label + suffix, cand))
                break
            if len(candidates) >= 2:
                break
        outcomes: list[str] = []
        first_meta: dict[str, Any] = {}
        first = True
        for label, repair_chain in candidates:
            kwargs = {"max_tokens": raised_cap} if raised_cap else {}
            logger.info(
                "cap-forced terminal turn returned empty%s; repairing on %s "
                "(max_tokens=%s)",
                f" ({agent_name})" if agent_name else "", label,
                raised_cap or "default",
            )
            try:
                resp = repair_chain.invoke(repair_msgs, **kwargs)
            except Exception as exc:  # noqa: BLE001 - degrade, never raise
                logger.warning("final-report empty repair on %s failed: %s", label, exc)
                outcomes.append(f"{label}: raised {type(exc).__name__}: {exc}")
                first = False
                continue
            nxt = content_to_text(getattr(resp, "content", resp))
            if first:
                meta = getattr(resp, "response_metadata", None) or {}
                usage = getattr(resp, "usage_metadata", None) or {}
                first_meta = {
                    "repair_finish_reason": meta.get("finish_reason"),
                    "repair_output_tokens": usage.get("output_tokens"),
                    "repair_reasoning_tokens": (
                        usage.get("output_token_details") or {}
                    ).get("reasoning"),
                }
                first = False
            if nxt.strip():
                outcomes.append(f"{label}: {len(nxt)} chars")
                _journal_terminal_turn(agent_name, final, first_meta, outcomes,
                                       repaired=True, raised_cap=raised_cap)
                return _retry_if_truncated(repair_chain, repair_msgs, nxt,
                                           backup_llm=backup_plain_chain or backup_chain)
            outcomes.append(f"{label}: empty")
        logger.warning(
            "cap-forced final report turn returned empty after %d repair "
            "attempt(s); emitting unavailable notice",
            len(candidates),
        )
        _journal_terminal_turn(agent_name, final, first_meta, outcomes,
                               repaired=False, raised_cap=raised_cap)
        return _unavailable_notice(final)
    except Exception as exc:  # noqa: BLE001 - degrade, never raise mid-run
        logger.warning("final-report turn after tool cap failed: %s", exc)
        return content_to_text(getattr(result, "content", result))


# Why the forced terminal turn produced no text, keyed by the provider's
# finish reason. The cause decides what the reader is told: a turn that called
# tools again is a different failure from one that exhausted its output budget,
# and calling both "burned its output budget" (the first wording) was wrong for
# every production hit recorded on 2026-09-11.
_EMPTY_TURN_REASONS = {
    "tool_calls": "the model kept requesting tools instead of writing",
    "function_call": "the model kept requesting tools instead of writing",
    "length": "the model burned its output budget before writing",
}


def _unavailable_notice(final: Any) -> str:
    """The reader-facing notice for an unrepairable empty terminal turn."""
    meta = getattr(final, "response_metadata", None) or {}
    reason = _EMPTY_TURN_REASONS.get(
        str(meta.get("finish_reason") or ""), "the model produced no report text"
    )
    return (
        "**Report unavailable** - the analyst's cap-forced terminal turn"
        f" returned empty content ({reason}). The prior tool evidence stands;"
        " re-run to regenerate the report."
    )


def _journal_terminal_turn(agent_name: str, final: Any, first_meta: dict,
                           outcomes: list[str], *, repaired: bool,
                           raised_cap: int | None) -> None:
    """Record an empty cap-forced terminal turn (advisory; never raises).

    The unavailable notice is the one failure this pipeline emits with no other
    trace: the empty turn does not raise, so nothing reaches the LLM failure
    journal unless it is written here. Without this entry the notice cannot be
    diagnosed (observed live 2026-09-11: a news report replaced by the notice,
    with no record of the model, the finish reason or the token split).
    """
    usage = getattr(final, "usage_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    meta = getattr(final, "response_metadata", None) or {}
    try:
        from tradingagents.agents.utils.llm_failure_journal import (
            journal_llm_note,
        )

        journal_llm_note(
            f"finalize_messages/{agent_name or 'analyst'}",
            "cap-forced terminal turn returned empty content",
            repaired=repaired,
            finish_reason=meta.get("finish_reason"),
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=details.get("reasoning"),
            input_tokens=usage.get("input_tokens"),
            raised_max_tokens=raised_cap,
            repair_outcomes=outcomes,
            **first_meta,
        )
    except Exception as exc:  # noqa: BLE001 - advisory only
        logger.debug("terminal-turn journal write skipped: %s", exc)


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
    backup_llm: Any | None = None,
    mandatory_fields: tuple[str, ...] | None = None,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape). The same value is forwarded to the free-text path so the
    fallback sees the same input the structured call did.

    ``backup_llm`` (optional): cut-at-cap continuation runs on this model
    instead of the truncated one (see ``_retry_if_truncated``).

    ``mandatory_fields`` (optional): the required field names of the schema.
    When the parsed result has one of them empty, the DSA per-field integrity
    retry rebuilds it before rendering (see
    ``retry_structured_missing_fields``) instead of rendering an empty
    mandatory field as-is.
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
            if mandatory_fields:
                rendered = retry_structured_missing_fields(
                    structured_llm,
                    prompt,
                    result,
                    render,
                    agent_name,
                    mandatory_fields,
                    backup_llm=backup_llm,
                )
            else:
                rendered = render(result)
            # Enforce completeness on the structured-success path too: a model
            # can hit max_tokens mid-render and still parse into the schema,
            # in which case render() ends mid-sentence and only the report
            # marker would catch it. Merge a continuation exactly like the
            # free-text path (no-op when the render is complete — the extra
            # _looks_truncated check costs nothing).
            return _retry_if_truncated(plain_llm, prompt, rendered, backup_llm=backup_llm)
        except Exception as exc:
            from tradingagents.agents.utils.llm_failure_journal import (
                journal_llm_failure,
            )

            journal_llm_failure(f"structured/{agent_name}", exc)
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name,
                exc,
            )

    response = plain_llm.invoke(prompt)
    response_text = content_to_text(getattr(response, "content", response))
    # Enforce completeness: cut-at-cap -> continuation merge.
    response_text = _retry_if_truncated(plain_llm, prompt, response_text, backup_llm=backup_llm)
    # Harden: a bare header/stub is not a usable decision. Regenerate once;
    # if still degenerate, return an explicit 'unavailable' notice so a
    # structured-output miss can never silently produce an empty decision.
    return _retry_if_stub(
            plain_llm, prompt, response_text, agent_name,
            fallback_llm=fallback_llm, backup_llm=backup_llm,
        )


def retry_structured_missing_fields(
    structured_llm: Any,
    prompt: Any,
    result: T,
    render: Callable[[T], str],
    agent_name: str,
    mandatory_fields: tuple[str, ...],
    max_retries: int = 1,
    backup_llm: Any | None = None,
) -> str:
    """DSA-style per-field integrity retry (research §3.2, pillar 4).

    When the structured result is missing a mandatory field, re-invoke with a
    TARGETED rebuild: the original prompt + the prior response + a per-field
    spec of exactly what is missing — not a blind re-roll. Returns the render
    of the repaired result (or the prior render when the retry fails / the
    field appears absent after retry, so the pipeline never blocks).

    ``backup_llm`` (optional): the repair re-invocation runs on this model
    (``TRADINGAGENTS_BACKUP_LLM``) when one is configured — a model that keeps
    dropping fields must never be re-paid for the repair. Without a backup the
    repair runs on ``structured_llm`` itself: a targeted rebuild on the same
    model is still better than rendering an empty mandatory field as-is.
    """
    missing = [f for f in mandatory_fields if getattr(result, f, None) in (None, "", [])]
    # A mandatory field that was CUT mid-sentence (max_tokens) is as unusable as
    # an empty one, and the rendered-text truncation guard cannot see it: the
    # trader's render ends with the mandatory "FINAL TRANSACTION PROPOSAL" banner
    # AND a single-line field starts with its own "**Reasoning**:" label — both
    # trip `_looks_truncated`'s exemptions, so the cut survived into the artifact
    # (GOOG 2026-09-11 trader.md: reasoning ended "…is elite — so t"). Probing the
    # FIELD value sees the bare cut (no banner, no label), so it is detected here.
    cut = [
        f for f in mandatory_fields
        if isinstance(getattr(result, f, None), str)
        and _looks_truncated(getattr(result, f))
    ]
    for f in cut:
        if f not in missing:
            missing.append(f)
    if not missing:
        return render(result)
    current = result
    retry_llm = (
        backup_llm
        if backup_llm is not None and backup_llm is not structured_llm
        else structured_llm
    )
    for _ in range(max_retries):
        still = [
            f for f in missing
            if getattr(current, f, None) in (None, "", [])
            or (
                isinstance(getattr(current, f, None), str)
                and _looks_truncated(getattr(current, f))
            )
        ]
        if not still:
            break
        if retry_llm is None:
            break
        spec = "; ".join(
            f"{f} must be present, non-empty and COMPLETE (not cut mid-sentence)"
            for f in still
        )
        retry_prompt = (
            f"{prompt}\n\n---\nYour previous response was parsed into the "
            f"schema but is missing required field(s): {spec}.\nPrevious "
            f"response:\n{render(current)}\n\nRe-send the COMPLETE decision "
            f"including the missing field(s), each finished - never cut off."
        )
        try:
            repaired = retry_llm.invoke(retry_prompt)
            if repaired is None:
                continue
            current = repaired
        except Exception as exc:  # noqa: BLE001 - degrade, never raise
            logger.warning("%s: integrity retry failed: %s", agent_name, exc)
            break
    return render(current)

