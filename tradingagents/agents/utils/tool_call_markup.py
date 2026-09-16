"""Tool calls a provider wrote as TEXT instead of as ``tool_calls``.

Some relays answer a tool-bound turn with the provider's own tool-call markup
inside ``content`` and an EMPTY ``tool_calls`` list. Measured 2026-09-15
(provider ``openrouter``, model ``deepseek/deepseek-v4.1-flash``): the trader's
deterministic-verification pass returned that markup as its "final prose", so
``3_trading/trader.md`` gained the whole block under the heading "**Computed
verification (deterministic tools):**" - while NOT one tool had run, because
``risk_tool_loop.run_tool_loop`` only ever looked at ``result.tool_calls``.
Same model, same day: the NVDA 14:19 tree is clean and the 22:32 tree is not,
so this is intermittent emission, not a configuration error.

Two spellings reached the reports - a single-wrapped ``U+FF5C DSML U+FF5C`` and
a double-wrapped one - and in both the word before ``calls`` had lost its
``tool_`` prefix (the reports read " calls", never "tool_calls"), so that prefix
is optional in the tag vocabulary below.  The same vocabulary is what
``report_verifier`` uses to flag an already-leaked block as a self-correction
artifact; keeping one definition here stops the producer (which parses and
executes the calls) and the detector from drifting apart.
"""

from __future__ import annotations

import re
from typing import Any

from tradingagents.llm_clients.base_client import content_to_text

# A tool-call markup tag in any spelling seen in the field: optional pipe and
# DSML wrappers on either side of the tag word, optional ``tool_`` prefix, and
# any attribute text up to the closing angle bracket.
TOOL_CALL_MARKUP_RE = re.compile(
    r"</?\s*(?:[^\s<>]{1,3}\s*)?(?:DSML\s*)?(?:[^\s<>]{1,3}\s*)?"
    r"(?:tool_)?(?:calls?|invoke|parameter|function_calls?)\b[^>]{0,80}>",
    re.I,
)

# One ``invoke`` block: the opening tag (its attributes carry ``name``) and
# everything up to its own closing tag. ``invoke`` blocks never nest, so a
# non-greedy body is exact.
_INVOKE_RE = re.compile(
    r"<[^<>]{0,60}\binvoke\b([^<>]{0,200})>(.*?)</[^<>]{0,60}\binvoke\s*>",
    re.I | re.S,
)

# One ``parameter`` block inside an ``invoke`` body.
_PARAMETER_RE = re.compile(
    r"<[^<>]{0,60}\bparameter\b([^<>]{0,200})>(.*?)</[^<>]{0,60}\bparameter\s*>",
    re.I | re.S,
)

_NAME_RE = re.compile(r"""\bname\s*=\s*["']([^"']+)["']""", re.I)
_STRING_FLAG_RE = re.compile(r"""\bstring\s*=\s*["'](true|false)["']""", re.I)
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


# What a caller receives when a model answered with markup and nothing else:
# the calls were never prose and no deliverable exists. One definition - the
# risk loop (which parses the calls into real ones), the report guards (which
# strip them) and the trader's append check all mean this by "unavailable".
MARKUP_UNAVAILABLE = (
    "unavailable: the model returned tool-call markup instead of prose - "
    "nothing was produced for this section"
)


def has_tool_call_markup(content: object) -> bool:
    """True when the text carries a tool-call markup tag."""
    return bool(TOOL_CALL_MARKUP_RE.search(content_to_text(content)))


def parse_text_tool_calls(content: object) -> list[dict[str, Any]]:
    """Extract the tool calls a provider wrote as text.

    Returns ``[]`` when the text carries no markup or none of its ``invoke``
    blocks names a tool. Each call is ``{"name", "args", "id", "type"}`` - the
    shape ``run_tool_loop`` reads off a structured ``tool_calls`` list, so both
    forms run through one dispatch path. Parameter values are coerced from the
    markup's own ``string="true|false"`` flag: a ``false`` flag whose text is
    numeric becomes an int/float (a tool whose schema wants ``float`` rejects a
    string argument), anything else stays text.
    """
    text = content_to_text(content)
    if not text or not TOOL_CALL_MARKUP_RE.search(text):
        return []
    calls: list[dict[str, Any]] = []
    for index, match in enumerate(_INVOKE_RE.finditer(text)):
        attrs, body = match.group(1), match.group(2)
        name_match = _NAME_RE.search(attrs)
        if not name_match:
            continue
        args: dict[str, Any] = {}
        for param in _PARAMETER_RE.finditer(body):
            param_attrs, raw_value = param.group(1), param.group(2)
            param_name = _NAME_RE.search(param_attrs)
            if not param_name:
                continue
            args[param_name.group(1)] = _coerce_value(param_attrs, raw_value)
        calls.append({
            "name": name_match.group(1).strip(),
            "args": args,
            "id": f"call_markup_{index}",
            "type": "tool_call",
        })
    return calls


def strip_tool_call_markup(content: object) -> str:
    """Return the text with every tool-call markup block removed.

    Used as the last resort when a model answers only with markup: the residual
    prose (if any) is what a caller can honestly keep.
    """
    text = content_to_text(content)
    if not TOOL_CALL_MARKUP_RE.search(text):
        return text
    text = _INVOKE_RE.sub("", text)
    text = TOOL_CALL_MARKUP_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _coerce_value(param_attrs: str, raw_value: str) -> Any:
    text = re.sub(r"<[^>]*>", "", raw_value or "").strip()
    flag = _STRING_FLAG_RE.search(param_attrs or "")
    if flag and flag.group(1).lower() == "true":
        return text
    number = _NUMBER_RE.fullmatch(text)
    if number:
        value = float(text)
        return int(value) if value.is_integer() else value
    return text
