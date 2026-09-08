"""Deterministic forced-tool evidence gathering (the "map" side).

When ``analyst_forced_tools`` is set, the runtime invokes a fixed tool set
(comma list or ``ALL``) and records one result leaf per tool BEFORE the
analyst runs, so the analyst's report input is deterministic in *composition*
(which tools were asked) instead of whatever subset the LLM happened to
request under its tool-selection freedom. The analyst then *reduces* the
merged evidence block into its report (the block is injected by the analyst
nodes; ``format_evidence_block`` here is the shared renderer).

Design: docs/design_mapreduce_forced_tool_gathering.md
Plan: docs/implementation_plan_mapreduce_forced_tool_gathering.md

Failure semantics (design §3.4/§3.5): a tool that raises, returns
"unavailable"/NO_DATA, or exceeds the deadline becomes a recorded leaf
(``status=error|no_data|timeout``), never a raised exception. A wedged
thread (a tool stuck in C or blocking I/O) cannot be preempted in Python:
it runs as a *daemon* thread, is marked ``timeout`` after the deadline, and
drains in the background — it must not block the graph node, and it must not
block interpreter exit (tracked: hung-thread termination is deferred, design
§3.5 / TRACKED-1).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass

# State key accumulating the evidence leaves (design doc ``analyst_tool_evidence_key``).
TOOL_EVIDENCE_KEY = "tool_evidence"

# Section header the analyst reduce prompt uses (design §3.3).
EVIDENCE_SECTION_HEADER = "## Tool Evidence (deterministic - all invoked)"

# The special literal meaning "the entire registered tool set".
ALL_LITERAL = "ALL"

logger = logging.getLogger(__name__)

_EMPTY_SENTINELS = ("", "unavailable", "no_data", "n/a", "{}", "[]", "no data available")


@dataclass(frozen=True)
class ToolEvidenceLeaf:
    """One tool's gathered result, in fixed composition order."""

    tool: str
    args: dict
    args_hash: str  # sha256 of the sorted JSON args (deterministic identity)
    status: str  # "ok" | "error" | "no_data" | "timeout"
    content: str  # tool output or error notice, truncated at the summary window
    ts: float  # monotonic() at completion


def parse_forced_spec(spec, registered_names) -> list[str]:
    """Normalize the forced-tool spec to an ordered, deduped name list.

    ``spec`` may be a comma-separated string, a list of names, or ``ALL``
    (expands to the full registered set, in registration order). Unknown
    names are skipped with a warning — never raised, so a stale config
    cannot kill a run.
    """
    if not spec:
        return []
    if isinstance(spec, str):
        items = [item.strip() for item in spec.split(",") if item.strip()]
    else:
        items = [str(item).strip() for item in spec if str(item).strip()]
    if not items:
        return []

    if ALL_LITERAL in items:
        return list(registered_names)

    seen: set[str] = set()
    out: list[str] = []
    for name in items:
        if name in seen:
            continue
        seen.add(name)
        if name not in registered_names:
            logger.warning("forced-tool spec references unknown tool %r - skipped", name)
            continue
        out.append(name)
    return out


def _truncate(text: str, window: int) -> str:
    text = str(text or "")
    if window and len(text) > window:
        return text[:window] + f"\n...[truncated at {window} chars]"
    return text


def _args_for(fn, context: dict | None) -> dict:
    """Synthesize deterministic args for one tool from the run context bag.

    Only declared schema keys present in the context are passed; tools that
    declare nothing (bare callables) receive the whole context and degrade
    per their own signature (a mismatch is a recorded ``error`` leaf, never
    a raise). Tools needing non-context args stay OUT of the curated forced
    sets (Phase 4); they remain the model's gap-fill domain.
    """
    declared = getattr(fn, "args", None)
    ctx = dict(context or {})
    if isinstance(declared, dict) and declared:
        return {k: ctx[k] for k in declared if k in ctx}
    # LangChain StructuredTool.args is a dict; plain callables may expose
    # ``__annotations__`` instead.
    annotations = getattr(fn, "__annotations__", None)
    if isinstance(annotations, dict) and annotations:
        return {k: ctx[k] for k in annotations if k in ctx}
    return ctx


def _classify(content: str) -> str:
    cleaned = str(content or "").strip().lower()
    if not cleaned:
        return "no_data"
    for sentinel in _EMPTY_SENTINELS:
        if cleaned == sentinel:
            return "no_data"
    return "ok"


def gather_evidence(
    tools_by_name: dict,
    forced_names: list[str],
    context: dict | None = None,
    *,
    timeout_s: float = 30,
    max_parallel: int = 1,
    summary_window: int = 12000,
) -> list[ToolEvidenceLeaf]:
    """Invoke every forced tool deterministically; always return leaves.

    Executes at most ``max_parallel`` tools concurrently; a tool still
    running after ``timeout_s`` is recorded as ``status=timeout`` while its
    daemon thread drains in the background. Never raises; a missing resolver
    entry becomes an ``error`` leaf.
    """
    if not forced_names or not tools_by_name:
        return []

    resolved = [n for n in forced_names if n in tools_by_name]
    leaves: dict[str, ToolEvidenceLeaf] = {}
    timed_out: set[str] = set()
    lock = threading.Lock()
    batches = [
        resolved[i : i + max(1, max_parallel)]
        for i in range(0, len(resolved), max(1, max_parallel))
    ]

    def run_one(name: str, fn) -> None:
        start = time.monotonic()
        args = _args_for(fn, context)
        try:
            out = str(fn.invoke(dict(args or {})))
            status = _classify(out)
            content = out
        except Exception as exc:  # noqa: BLE001 - never let a tool abort the map
            status = "error"
            content = f"raised {type(exc).__name__}: {exc}"
            logger.warning("forced-tool evidence: %s raised %s", name, exc)
        with lock:
            # Once a tool is marked ``timeout`` it is frozen: the still-running
            # thread must NOT clobber the timeout leaf with a late result.
            if name in timed_out:
                return
            leaves[name] = _leaf(name, args, status, content, start, summary_window)

    for batch in batches:
        threads: list[threading.Thread] = []
        for name in batch:
            if name in leaves or name in timed_out:
                continue
            t = threading.Thread(
                target=run_one, args=(name, tools_by_name[name]), daemon=True
            )
            t.start()
            threads.append((name, t))
        if not threads:
            continue
        # The deadline is absolute from batch start; a thread is marked
        # ``timeout`` if it is still alive when its join deadline passes.
        # Sequential per-thread ``join(timeout)`` with the same scalar would
        # give later threads a later effective deadline - use a shared deadline.
        deadline = time.monotonic() + timeout_s if timeout_s else None
        for name, t in threads:
            if deadline is None:
                t.join()
            else:
                t.join(timeout=max(0.0, deadline - time.monotonic()))
            if t.is_alive():
                with lock:
                    if name in leaves or name in timed_out:
                        continue
                    timed_out.add(name)
                    fn = tools_by_name[name]
                    args = _args_for(fn, context)
                    leaves[name] = _leaf(
                        name,
                        args,
                        "timeout",
                        f"timed out after {timeout_s}s; thread still draining in background",
                        time.monotonic(),
                        summary_window,
                    )

    # Order is the spec's order, so composition is stable across runs.
    return [leaves[name] for name in resolved if name in leaves]


def _leaf(
    name: str,
    args: dict,
    status: str,
    content: str,
    start: float,
    summary_window: int,
) -> ToolEvidenceLeaf:
    args = args or {}
    return ToolEvidenceLeaf(
        tool=name,
        args=args,
        args_hash=hashlib.sha256(
            json.dumps(args, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12],
        status=status,
        content=_truncate(content, summary_window),
        ts=time.monotonic() - start,
    )


def gather_for_analyst_node(
    state: dict,
    analyst_key: str,
    tools: list,
    config: dict | None = None,
) -> tuple[str, dict]:
    """Gather forced evidence once per analyst run; return (block, evidence).

    Call at the top of the analyst node. When ``analyst_forced_tools`` is
    unset (empty list), returns ``("", existing)`` untouched — the legacy
    LLM-selected path. When set, resolves the forced names from the node's
    bound tools, gathers them deterministically (context = the run's ticker /
    date), stores the leaves under ``analyst_key`` in the state's
    ``tool_evidence`` dict, and returns the rendered reduce block. A later
    re-entry (tool-loop return / cap turn) finds the key already set and
    skips the gather — the fix composition is what matters, not a re-fetch.
    """
    existing: dict = dict(state.get(TOOL_EVIDENCE_KEY) or {})
    forced = (config or {}).get("analyst_forced_tools") or []
    if not forced:
        return "", existing

    if analyst_key in existing:
        return format_evidence_block(existing[analyst_key]), existing

    by_name = {t.name: t for t in tools}
    # The config is one GLOBAL list serving all four analysts; a name missing
    # from THIS node is expected (it belongs to a sibling analyst), so pass
    # the union as "registered" to suppress per-node "unknown tool" noise and
    # filter down to THIS analyst's names in config order.
    parsed = parse_forced_spec(forced, set(by_name) | set(forced))
    names = list(by_name) if ALL_LITERAL in forced else [n for n in parsed if n in by_name]
    if not names:
        return "", existing

    context = {
        "ticker": state.get("company_of_interest", ""),
        "current_date": state.get("trade_date", ""),
        # Some tools declare ``curr_date`` instead of ``current_date``.
        "curr_date": state.get("trade_date", ""),
    }
    leaves = gather_evidence(
        by_name,
        names,
        context=context,
        timeout_s=float(config.get("analyst_forced_tools_timeout_s") or 30),
        max_parallel=int(config.get("analyst_forced_tools_max_parallel") or 1),
        summary_window=int(config.get("analyst_forced_tools_summary_window") or 12000),
    )
    updated = {**existing, analyst_key: [leaf.__dict__ for leaf in leaves]}
    return format_evidence_block(leaves), updated


def _leaf_as_dict(leaf) -> dict:
    """Normalize a ToolEvidenceLeaf or its persisted dict form."""
    if isinstance(leaf, ToolEvidenceLeaf):
        return leaf.__dict__
    return dict(leaf or {})


def format_evidence_block(leaves) -> str:
    """Render the deterministic block the analyst reduces from (design §3.3).

    Accepts ``ToolEvidenceLeaf`` objects or their dict form (as read back
    from state on a re-entry). Failed / empty / timed-out leaves are printed
    explicitly ``unavailable`` so the analyst can state them rather than
    silently losing the signal.
    """
    if not leaves:
        return ""
    lines = [
        EVIDENCE_SECTION_HEADER,
        "All of the following tools were invoked deterministically BEFORE your "
        "analysis. Ground your report in this evidence; you may still call any "
        "other tool to fill gaps, but do not re-request these.",
    ]
    for leaf in leaves:
        d = _leaf_as_dict(leaf)
        tool = str(d.get("tool") or "?")
        status = str(d.get("status") or "ok")
        content = str(d.get("content") or "")
        args = d.get("args") or {}
        args_str = json.dumps(args, sort_keys=True) if args else ""
        status_marker = {
            "ok": "ok",
            "error": "error",
            "no_data": "no_data",
            "timeout": "timeout",
        }.get(status, status)
        lines.append(f"\n### {tool} [{status_marker}]" + (f" args={args_str}" if args_str else ""))
        if status in ("timeout", "error", "no_data"):
            lines.append(f"unavailable: {content}")
        else:
            lines.append(content)
    return "\n".join(lines)
