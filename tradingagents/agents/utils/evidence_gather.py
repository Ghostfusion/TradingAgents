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


def make_evidence_leaf(
    tool: str,
    content: str,
    args: dict | None = None,
    status: str = "ok",
    summary_window: int | None = None,
) -> dict:
    """Persist-shape evidence dict for a non-tool, deterministic source.

    Same shape/hash/truncation as a gatherer leaf, so ``tool_evidence.json``
    and ``repro_check --evidence`` treat externally journaled inputs (e.g.
    the sentiment analyst's pre-fetched news / StockTwits / Reddit blocks)
    identically to forced-tool leaves. ``status``: ok | error | no_data |
    timeout.
    """
    return _leaf_as_dict(
        _leaf(
            tool,
            args,
            status,
            content,
            time.monotonic(),
            summary_window if summary_window is not None else 12000,
        )
    )


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


# Arg keys the deterministic gather context can supply. A tool with a required
# arg outside this set needs a model-supplied input -> it belongs to the model
# pool, not the gather pool.
CONTEXT_ARG_KEYS = frozenset(
    {"ticker", "symbol", "current_date", "curr_date", "start_date", "end_date", "look_back_days"}
)

# Reserved key in the tool_evidence state dict carrying the per-analyst
# model-pool name lists (persisted for the --evidence G/M split).
MODEL_POOL_KEY = "_model_pool"

MODEL_POOL_HEADER = (
    "## Model-supplied tools (not pre-gathered — call them with your own "
    "inputs if needed)"
)


def classify_tool_pools(
    tools,
    context_keys=CONTEXT_ARG_KEYS,
    forced_model=(),
) -> tuple[list[str], list[str]]:
    """Classify bound tools into (gather_pool, model_pool).

    The gather (auto) pool = every tool whose required args are all covered
    by the deterministic context. The model pool = every tool that requires an
    arg the context cannot supply (e.g. ``get_bsm_option_quote`` needs
    spot/strike/t_years/vol; ``get_macro_indicators`` needs ``indicator``),
    plus any name in ``forced_model`` (the analyst_tools_model_supplied
    override). Classified from each tool's own schema, so a FUTURE tool that
    needs a model input lands in the model pool automatically — no
    maintained list to go stale.
    """
    forced = set(forced_model or ())
    gather: list[str] = []
    model: list[str] = []
    for t in tools:
        name = getattr(t, "name", None)
        if not name:
            continue
        args = getattr(t, "args", None) or {}
        required = [k for k, meta in args.items() if "default" not in meta]
        if name in forced or any(k not in context_keys for k in required):
            model.append(name)
        else:
            gather.append(name)
    return gather, sorted(model)


def _render_evidence(leaves, model_names) -> str:
    """Evidence block + the model-pool hint (the analyst reduce sees both)."""
    block = format_evidence_block(leaves)
    if model_names:
        block += "\n\n" + MODEL_POOL_HEADER + "\n" + ", ".join(sorted(model_names))
    return block


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
    bound tools and gathers the GATHER-POOL subset deterministically (context
    = the run's ticker / date / window). Model-pool tools (required args the
    context cannot supply) are NEVER auto-attempted: they stay bound to the
    LLM, which owns their inputs — an explicit forced name in the model pool
    is skipped with a warning. Evidence leaves are stored under
    ``analyst_key`` and the model-pool names under ``MODEL_POOL_KEY`` in the
    state's ``tool_evidence`` dict; the rendered block is returned for the
    reduce prompt. A re-entry finds the key already set and skips the gather.
    """
    existing: dict = dict(state.get(TOOL_EVIDENCE_KEY) or {})
    forced = (config or {}).get("analyst_forced_tools") or []
    if not forced:
        return "", existing

    pool = (existing.get(MODEL_POOL_KEY) or {}).get(analyst_key) or []
    if analyst_key in existing:
        return _render_evidence(existing[analyst_key], pool), existing

    by_name = {t.name: t for t in tools}
    gather_names, model_names = classify_tool_pools(
        by_name.values(),
        forced_model=(config or {}).get("analyst_tools_model_supplied") or [],
    )
    model_set = set(model_names)

    if ALL_LITERAL in forced:
        # Force-gather EVERY auto-gatherable tool; the model pool is never
        # auto-attempted (its inputs are the model's, not ours to invent).
        names = gather_names
    else:
        # The config is one GLOBAL list serving all four analysts; a name
        # missing from THIS node is expected (it belongs to a sibling), so
        # pass the union as "registered" to suppress unknown-tool noise.
        parsed = parse_forced_spec(forced, set(by_name) | set(forced))
        names = []
        for n in parsed:
            if n in model_set:
                logger.warning(
                    "forced-tool %r needs model-supplied inputs (model pool) - "
                    "skipping the gather; the agent LLM controls it",
                    n,
                )
            elif n in by_name:
                names.append(n)

    if not names:
        # The pool hint is still worth persisting so the split is visible.
        updated = {**existing}
        pools = dict(existing.get(MODEL_POOL_KEY) or {})
        pools[analyst_key] = model_names
        updated[MODEL_POOL_KEY] = pools
        return "", updated

    context = _evidence_context(state)
    leaves = gather_evidence(
        by_name,
        names,
        context=context,
        timeout_s=float(config.get("analyst_forced_tools_timeout_s") or 30),
        max_parallel=int(config.get("analyst_forced_tools_max_parallel") or 1),
        summary_window=int(config.get("analyst_forced_tools_summary_window") or 12000),
    )
    updated = {**existing, analyst_key: [leaf.__dict__ for leaf in leaves]}
    pools = dict(existing.get(MODEL_POOL_KEY) or {})
    pools[analyst_key] = model_names
    updated[MODEL_POOL_KEY] = pools
    return _render_evidence(leaves, model_names), updated


def _leaf_as_dict(leaf) -> dict:
    """Normalize a ToolEvidenceLeaf or its persisted dict form."""
    if isinstance(leaf, ToolEvidenceLeaf):
        return leaf.__dict__
    return dict(leaf or {})


def make_short_circuit_tool_node(tool_node, analyst_key: str):
    """Wrap an analyst ToolNode so already-gathered tools never re-run.

    User directive (docs/implementation_plan_mapreduce_forced_tool_gathering.md
    "Operating philosophy"): feed every registered tool's evidence to the LLM
    once, deterministically, and never re-request the same info — the model's
    gap-fill loop must NOT re-invoke a tool that the gatherer already ran.

    The wrapper inspects the last assistant message's tool calls: a call whose
    name is in the analyst's gathered evidence set is answered with a
    ToolMessage pointing back to the ``## Tool Evidence`` block (no vendor
    hit); anything NOT gathered (possible only when a partial list is
    configured, since ``ALL`` covers the whole registry) is delegated to the
    underlying node. Off-path when no evidence exists (legacy default) → the
    node behaves exactly as before.
    """
    if not callable(tool_node):
        # Not a real ToolNode (e.g. a non-callable test double): no way to
        # short-circuit, so leave it untouched.
        return tool_node

    def wrapper(state):
        return short_circuit_tool_calls(tool_node, analyst_key, state)

    return wrapper


def short_circuit_tool_calls(tool_node, analyst_key: str, state: dict) -> dict:
    """Execute the wrapper logic (see ``make_short_circuit_tool_node``)."""
    from langchain_core.messages import AIMessage, ToolMessage

    messages = list(state.get("messages") or [])
    if not messages:
        return tool_node(state)

    last = messages[-1]
    calls = getattr(last, "tool_calls", None) or []
    if not calls:
        return tool_node(state)

    evidence = (state.get(TOOL_EVIDENCE_KEY) or {}).get(analyst_key) or []
    gathered: dict[str, str] = {}
    for leaf in evidence:
        d = _leaf_as_dict(leaf)
        tool_name = str(d.get("tool") or "")
        if tool_name:
            gathered[tool_name] = str(d.get("status") or "ok")

    # Analyst's model-pool names (bound to the LLM; not auto-gathered), so the
    # tool-call log can mark which invoked tools were pool-controlled.
    from tradingagents.agents.utils.tool_call_log import log_tool_call

    model_pool: set = set(
        ((state.get(TOOL_EVIDENCE_KEY) or {}).get(MODEL_POOL_KEY) or {}).get(analyst_key) or []
    )

    outputs: list = []
    remaining: list = []
    for call in calls:
        name = str((call or {}).get("name") or "")
        if name in gathered:
            status = gathered[name]
            log_tool_call(
                analyst_key,
                name,
                "short_circuit",
                args=(call or {}).get("args"),
                state=state,
                in_model_pool=name in model_pool,
            )
            outputs.append(
                ToolMessage(
                    content=(
                        f"[forced-tool evidence already gathered] {name} "
                        f"(status={status}) was gathered deterministically before this "
                        "run - see its entry in the '## Tool Evidence (deterministic - "
                        "all invoked)' block of the system prompt. Do not re-fetch; "
                        "write the report from that evidence."
                    ),
                    tool_call_id=str((call or {}).get("id") or ""),
                    name=name,
                )
            )
        else:
            remaining.append(call)

    if not remaining:
        return {"messages": outputs}

    # Record every tool the LLM actually invoked and will execute against the
    # vendor (the model-pool / gap-fill calls) before delegating.
    for call in remaining:
        log_tool_call(
            analyst_key,
            str((call or {}).get("name") or ""),
            "executed",
            args=(call or {}).get("args"),
            state=state,
            in_model_pool=str((call or {}).get("name") or "") in model_pool,
        )

    if not outputs:
        # nothing gathered on this turn - plain passthrough.
        return tool_node(state)

    # Mixed: short the gathered ones, delegate the rest in one underlying call.
    filtered_last = AIMessage(
        content=getattr(last, "content", ""),
        tool_calls=list(remaining),
        id=getattr(last, "id", None),
    )
    sub_state = {**state, "messages": [*messages[:-1], filtered_last]}
    result = tool_node(sub_state)
    real_msgs = list((result or {}).get("messages", []))
    return {"messages": [*outputs, *real_msgs]}


def _evidence_context(state: dict) -> dict:
    """Deterministic args bag for forced tools, derived from the run state.

    In addition to ticker/date aliases, provides the date-window keys that
    data tools declare (``symbol``, ``start_date``, ``end_date``,
    ``look_back_days``) so window tools are invoked with real (not empty)
    args and return data, not validation errors. The window is a rolling
    30 calendar days ending at the trade date (matches the codebase's common
    ``look_back_days=30`` default). When the trade date does not parse as
    ``YYYY-MM-DD``, the window keys are omitted so each tool falls back to
    its own defaults instead of erroring on a bad date.
    """
    ticker = str(state.get("company_of_interest") or "")
    trade_date = str(state.get("trade_date") or "")
    context: dict = {
        "ticker": ticker,
        "current_date": trade_date,
        # Some tools declare ``curr_date`` instead of ``current_date``.
        "curr_date": trade_date,
    }
    try:
        from datetime import datetime as _dt, timedelta as _td

        d = _dt.strptime(trade_date, "%Y-%m-%d").date()
        context["symbol"] = ticker
        context["start_date"] = (d - _td(days=29)).isoformat()
        context["end_date"] = trade_date
        context["look_back_days"] = 30
    except (TypeError, ValueError):
        # Unparseable/absent trade date: leave the window keys out; tools with
        # their own defaults still gather.
        pass
    return context


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
        "HARD CITATION RULE for figures: copy every figure VERBATIM from the "
        "tool output above - exact digits and units, never retyped or "
        "reformatted. When you must state a derived percentage or level, "
        "compute it from verbatim-copied inputs. If two tools disagree on the "
        "same quantity, quote BOTH with their tool names and say they "
        "conflict; never splice, substitute, or silently reconcile.",
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
