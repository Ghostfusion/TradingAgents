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

from langchain_core.runnables import RunnableLambda

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


def _declared_defaults(fn, defaults=None) -> dict:
    """The S11b declared enumerable defaults for one tool (name-keyed).

    Defaults to NO table: the ungated path must synthesize exactly the args it
    did before S11b. A gate-on caller passes ``TOOL_ARG_DEFAULTS`` explicitly
    (``gather_for_analyst_node`` does) - defaulting to the full table here made
    the gate depend on every caller remembering to pass ``{}``, the opposite of
    ground rule 5.
    """
    table = {} if defaults is None else defaults
    name = str(getattr(fn, "name", "") or "")
    return dict(table.get(name) or {})


def _args_for(fn, context: dict | None, defaults=None) -> dict:
    """Synthesize deterministic args for one tool from the run context bag.

    Only declared schema keys present in the context are passed; tools that
    declare nothing (bare callables) receive the whole context and degrade
    per their own signature (a mismatch is a recorded ``error`` leaf, never
    a raise). Tools needing non-context args stay OUT of the curated forced
    sets (Phase 4); they remain the model's gap-fill domain.

    S11b: a tool with a declared enumerable default (``TOOL_ARG_DEFAULTS``)
    also receives that value for the covered required arg, so it can move into
    the deterministic gather. A tool WITHOUT a declared default gets nothing
    invented for it.
    """
    declared = getattr(fn, "args", None)
    ctx = dict(context or {})
    defaults = _declared_defaults(fn, defaults)
    if isinstance(declared, dict) and declared:
        out = {k: ctx[k] for k in declared if k in ctx}
        for key, value in defaults.items():
            if key in declared and key not in out:
                out[key] = value
        return out
    # LangChain StructuredTool.args is a dict; plain callables may expose
    # ``__annotations__`` instead.
    annotations = getattr(fn, "__annotations__", None)
    if isinstance(annotations, dict) and annotations:
        out = {k: ctx[k] for k in annotations if k in ctx}
        for key, value in defaults.items():
            if key in annotations and key not in out:
                out[key] = value
        return out
    out = dict(ctx)
    for key, value in defaults.items():
        out.setdefault(key, value)
    return out


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
    arg_defaults=None,
    args_by_name: dict | None = None,
) -> list[ToolEvidenceLeaf]:
    """Invoke every forced tool deterministically; always return leaves.

    Executes at most ``max_parallel`` tools concurrently; a tool still
    running after ``timeout_s`` is recorded as ``status=timeout`` while its
    daemon thread drains in the background. Never raises; a missing resolver
    entry becomes an ``error`` leaf.

    ``args_by_name`` (S11d) supplies explicit per-tool args (an LLM plan's
    ``{tool: {arg: value}}``), overriding ``context`` for those names;
    otherwise args are synthesized from the context plus the S11b declared
    defaults (``arg_defaults``).
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

    def resolve_args(name: str, fn) -> dict:
        explicit = (args_by_name or {}).get(name)
        if explicit is not None:
            return dict(explicit)
        return _args_for(fn, context, arg_defaults)

    def run_one(name: str, fn) -> None:
        start = time.monotonic()
        args = resolve_args(name, fn)
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
                    args = resolve_args(name, fn)
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

# S11b: declared per-tool deterministic defaults for enumerable args. When a
# model-pool tool's only non-context required args have a defensible declared
# value, the tool moves into the deterministic gather (composition becomes
# deterministic for free) and the reason is printed. A tool WITHOUT a
# defensible default stays in the model pool - an arg is never invented to
# force a tool in (plan section 2 S11b).
TOOL_ARG_DEFAULTS: dict[str, dict] = {
    "get_macro_indicators": {"indicator": "10y_treasury"},
}

TOOL_ARG_DEFAULT_REASONS: dict[str, str] = {
    "get_macro_indicators": (
        "declared enumerable default indicator='10y_treasury': the run's "
        "macro-authority gate cites the 10Y first, and a single-valued enum "
        "makes the forced leaf set deterministic"
    ),
}

# Reserved key in the tool_evidence state dict carrying the persisted S11a
# symmetry block. The value is a LIST of dicts (summary row first, then one
# row per pair), never a nested dict: ``reporting._evidence_sources`` walks
# every tool_evidence value as a leaf list, and a dict would raise there,
# while a list of dicts lacking a ``tool`` key is skipped like a metadata row.
SYMMETRY_KEY = "_symmetry"

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
    defaults=None,
    on_move=None,
) -> tuple[list[str], list[str]]:
    """Classify bound tools into (gather_pool, model_pool).

    The gather (auto) pool = every tool whose required args are all covered by
    the deterministic context, plus (S11b) a required arg covered by a declared
    enumerable default. The model pool = every tool that still requires an arg
    the context cannot supply (e.g. ``get_bsm_option_quote`` needs
    spot/strike/t_years/vol), plus any name in ``forced_model`` (the
    analyst_tools_model_supplied override). Classified from each tool's own
    schema, so a FUTURE tool that needs a model input lands in the model pool
    automatically - no maintained list to go stale.

    A tool that moves into the gather because of a declared default prints the
    reason (``on_move(name, covered_args, reason)`` callback + a log line); a
    tool with no defensible default stays in the model pool - an arg is never
    invented to force a tool in.
    """
    table = {} if defaults is None else defaults  # gate-on callers pass the table
    forced = set(forced_model or ())
    gather: list[str] = []
    model: list[str] = []
    for t in tools:
        name = getattr(t, "name", None)
        if not name:
            continue
        args = getattr(t, "args", None) or {}
        required = [k for k, meta in args.items() if "default" not in meta]
        covered = dict(table.get(name) or {})
        missing = [k for k in required if k not in context_keys and k not in covered]
        if name in forced or missing:
            model.append(name)
            continue
        gather.append(name)
        moved = [k for k in required if k not in context_keys and k in covered]
        if moved:
            reason = TOOL_ARG_DEFAULT_REASONS.get(name) or (
                "declared enumerable defaults "
                + ", ".join(f"{k}={covered[k]!r}" for k in moved)
            )
            logger.info(
                "tool %r moved to the deterministic gather: %s", name, reason
            )
            if on_move is not None:
                on_move(name, moved, reason)
    return gather, sorted(model)


def _render_evidence(leaves, model_names, reference_line: str = "", notes=None) -> str:
    """Evidence block + the model-pool hint (the analyst reduce sees both).

    ``reference_line`` (optional): the run's price basis (as-of date + close,
    with the FORMING/provisional flag on an intraday run) rendered above the
    leaves. It is not a tool leaf — it is the basis of every price-derived
    figure in the block, and only the market analyst has a snapshot tool that
    states it otherwise (GOOG 2026-09-11: the fundamentals report compared a
    forming close against intrinsic value and an SMA while the market section
    flagged the same bar provisional).
    """
    block = format_evidence_block(leaves)
    if reference_line:
        block = f"{reference_line}\n\n{block}"
    if notes:
        # S11b: print WHY a tool left the model pool (composition basis).
        block += "\n\n## Declared-default tools moved to the deterministic gather\n" + "\n".join(
            f"- {note}" for note in notes
        )
    if model_names:
        block += "\n\n" + MODEL_POOL_HEADER + "\n" + ", ".join(sorted(model_names))
    return block


def _reference_price_line(state: dict) -> str:
    """The run's price basis for the evidence block ("" when unknown)."""
    try:
        from tradingagents.agents.utils.price_consistency import price_basis_line

        return price_basis_line(
            str(state.get("company_of_interest") or ""),
            str(state.get("trade_date") or "") or None,
        )
    except Exception:  # noqa: BLE001 - advisory line, never break the gather
        return ""


def gather_for_analyst_node(
    state: dict,
    analyst_key: str,
    tools: list,
    config: dict | None = None,
    planner=None,
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
        return _render_evidence(
            existing[analyst_key], pool, reference_line=_reference_price_line(state)
        ), existing

    by_name = {t.name: t for t in tools}
    # S11b is gated: with the gate off the declared-default table is empty, so
    # the pool split (and every output) is byte-identical to HEAD. With the
    # gate on, a tool whose required arg has a defensible declared default
    # moves into the deterministic gather and its reason is printed into the
    # evidence block.
    arg_defaults = TOOL_ARG_DEFAULTS if _flag("enable_evidence_symmetry") else {}
    move_notes: list = []
    gather_names, model_names = classify_tool_pools(
        by_name.values(),
        forced_model=(config or {}).get("analyst_tools_model_supplied") or [],
        defaults=arg_defaults,
        on_move=lambda name, covered, reason: move_notes.append(f"{name}: {reason}"),
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
    leaves: list[ToolEvidenceLeaf] = []
    # S11d (gated): one cheap completion emits a typed plan over the model-pool
    # remainder; code validates it against the remainder whitelist + each
    # tool's own args schema and fires it through the same executor. An empty,
    # invalid or out-of-whitelist plan falls back to today's loop and says so -
    # it never raises and never thins the evidence.
    if planner is not None and _flag("enable_evidence_symmetry"):
        plan_reason = ""
        try:
            raw = planner(analyst_key, list(model_names), tools)
        except Exception as exc:  # noqa: BLE001 - a planner must never abort the gather
            plan_reason = f"planner raised {type(exc).__name__}: {exc}"
        else:
            plan_leaves, plan_reason = resolve_model_pool_plan(
                raw, by_name, model_names
            )
            if not plan_reason:
                leaves.extend(plan_leaves)
                # Journal the accepted plan (one line per call) so repro_check
                # can diff the plan the run actually fired.
                try:
                    from tradingagents.agents.utils.tool_call_log import log_tool_call

                    for leaf in plan_leaves:
                        log_tool_call(
                            analyst_key,
                            leaf.tool,
                            "planned",
                            args=leaf.args,
                            state=state,
                            in_model_pool=True,
                        )
                except Exception:  # noqa: BLE001 - advisory, never break the gather
                    pass
        if plan_reason:
            logger.warning(
                "evidence-symmetry plan for %r fell back to the legacy loop: %s",
                analyst_key,
                plan_reason,
            )
    leaves.extend(
        gather_evidence(
            by_name,
            names,
            context=context,
            timeout_s=float(config.get("analyst_forced_tools_timeout_s") or 30),
            max_parallel=int(config.get("analyst_forced_tools_max_parallel") or 1),
            summary_window=int(config.get("analyst_forced_tools_summary_window") or 12000),
            arg_defaults=arg_defaults,
        )
    )
    updated = {**existing, analyst_key: [leaf.__dict__ for leaf in leaves]}
    pools = dict(existing.get(MODEL_POOL_KEY) or {})
    pools[analyst_key] = model_names
    updated[MODEL_POOL_KEY] = pools
    return _render_evidence(
        leaves, model_names, reference_line=_reference_price_line(state), notes=move_notes
    ), updated


def _leaf_as_dict(leaf) -> dict:
    """Normalize a ToolEvidenceLeaf or its persisted dict form."""
    if isinstance(leaf, ToolEvidenceLeaf):
        return leaf.__dict__
    return dict(leaf or {})


class _ShortCircuitToolNode(RunnableLambda):
    """Runnable tool-node wrapper that keeps the wrapped node's attributes.

    The wrapper has to be a Runnable - LangGraph's ``add_node`` rejects a plain
    proxy object ("Expected a Runnable, callable or dict") - and it has to keep
    the node's public surface answering: the tool-binding contract tests read
    ``tools_by_name`` off ``graph.tool_nodes`` (one producer per number), so a
    bare ``RunnableLambda`` blinds them. Unknown attributes delegate to the
    wrapped node; private names do not, so LangChain's own internals never leak
    into the ToolNode.
    """

    def __init__(self, tool_node, analyst_key: str) -> None:
        self._wrapped = tool_node
        invoke = tool_node.invoke
        super().__init__(
            lambda state, config=None: short_circuit_tool_calls(
                lambda st: invoke(st, config), analyst_key, state
            )
        )

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self._wrapped, item)


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

    LangGraph's ``ToolNode`` is a Runnable, NOT a plain function:
    ``callable(ToolNode(tools))`` is False. An earlier ``callable`` guard here
    therefore returned every PRODUCTION node UNWRAPPED while the unit tests -
    which pass plain-function doubles - stayed green: the short-circuit, the
    per-analyst tool-call journal and the model-pool evidence leaves were all
    dead in real runs (QQQI 2026-09-13: the news analyst's real
    ``get_macro_indicators`` / ``get_prediction_markets`` calls left no leaf, so
    the verifier's macro-authority gate flagged the report's 10Y / RRP /
    Polymarket lines as UNSUPPORTED). A Runnable node gets a RunnableLambda so
    LangGraph injects the node config its ``invoke`` requires - a bare
    ``invoke(state)`` raises "Missing required config key" outside the graph.

    A node that is neither callable nor a Runnable is left untouched, but the
    disable is now LOUD: silently returning it is what hid the unwrapped-node
    defect for months.
    """
    invoke = getattr(tool_node, "invoke", None)
    if callable(tool_node):

        def wrapper(state):
            return short_circuit_tool_calls(tool_node, analyst_key, state)

        return wrapper

    if callable(invoke):
        return _ShortCircuitToolNode(tool_node, analyst_key)

    logger.warning(
        "short-circuit disabled for the %s analyst: tool node %r is neither "
        "callable nor a Runnable - gathered tools will re-run and model-pool "
        "tool results will not be journaled as evidence",
        analyst_key,
        type(tool_node).__name__,
    )
    return tool_node


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
        # nothing gathered on this turn - plain passthrough. Still journal the
        # executed model-pool results below so later verification can see them.
        result = tool_node(state)
        real_msgs = list((result or {}).get("messages", []))
        return _journal_executed(state, analyst_key, remaining, real_msgs)

    # Mixed: short the gathered ones, delegate the rest in one underlying call.
    filtered_last = AIMessage(
        content=getattr(last, "content", ""),
        tool_calls=list(remaining),
        id=getattr(last, "id", None),
    )
    sub_state = {**state, "messages": [*messages[:-1], filtered_last]}
    result = tool_node(sub_state)
    real_msgs = list((result or {}).get("messages", []))
    return _journal_executed(state, analyst_key, remaining, real_msgs, outputs=outputs)


def _journal_executed(state: dict, analyst_key: str, remaining: list, real_msgs: list, outputs: list | None = None) -> dict:
    """Append LLM-executed (model-pool / gap-fill) tool results as evidence leaves.

    The deterministic gatherer records the forced set into tool_evidence, but
    tools the LLM calls itself (the model-pool ~40, e.g. get_macro_indicators,
    get_prediction_markets) execute against the vendor and their results live
    ONLY in the chat transcript — so the report verifier and repro_check see
    "no leaf evidence" for anything those tools returned (the JPM/GS 2026-09-08
    macro block was falsely flagged as unsupported). This appends a leaf per
    executed tool, from the returned ToolMessage content, so the evidence block
    covers EVERYTHING the analyst actually received. Advisory: never raises.
    """
    try:
        # The final message list is the short-circuit replies + the results of
        # the tools that actually executed (both are consumed by the graph).
        out_msgs = list(outputs or []) + list(real_msgs)
        if not real_msgs:
            # Nothing executed; pass through exactly what the caller expects
            # (the pure-short-circuit path returns only shorted ToolMessages).
            return {"messages": out_msgs}
        from langchain_core.messages import ToolMessage

        # S11c: the mirrored discretionary allowance for this role's pair. Active
        # only under the gate AND with a declared pair (``evidence_symmetry_pairs``);
        # no pair -> None -> today's behaviour byte-identical. The split itself is
        # the shared mirror rule, so the pair API and this live path cannot drift.
        allowance = (
            _pair_allowance_for(analyst_key, state, _config())
            if _flag("enable_evidence_symmetry")
            else None
        )
        forced_names = {
            str(_leaf_as_dict(leaf).get("tool") or "")
            for leaf in (state.get(TOOL_EVIDENCE_KEY) or {}).get(analyst_key) or []
        }
        candidates: list[dict] = []
        for msg in real_msgs:
            if not isinstance(msg, ToolMessage):
                continue
            name = str(getattr(msg, "name", "") or "")
            content = str(getattr(msg, "content", "") or "")
            if not name or not content.strip():
                continue
            call = next(
                (c for c in remaining if str((c or {}).get("name") or "") == name),
                None,
            )
            if call is None:
                continue
            candidates.append(
                {"name": name, "args": (call or {}).get("args"), "content": content}
            )
        kept_calls, suppressed_calls = _split_discretionary(
            candidates, allowance, forced_names
        )
        # A surplus call beyond the mirror is suppressed AND journaled with its
        # args, so the asymmetry is visible rather than hidden.
        _journal_suppressed(analyst_key, suppressed_calls, state=state)
        new_leaves: list[dict] = [
            make_evidence_leaf(
                item["name"], item["content"], args=item["args"], status="ok"
            )
            for item in kept_calls
        ]
        if not new_leaves:
            return {"messages": out_msgs}
        evidence = dict(state.get(TOOL_EVIDENCE_KEY) or {})
        existing = list(evidence.get(analyst_key) or [])
        existing.extend(new_leaves)
        evidence[analyst_key] = existing
        return {"messages": out_msgs, "tool_evidence": evidence}
    except Exception:  # noqa: BLE001 - advisory, never break the tool loop
        return {"messages": out_msgs}


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
    # Gather-time metric reconciliation (strategies/metric_reconcile.py): if
    # the same metric appears in leaves from different tools/vendors at
    # conflicting values, surface it HERE so the analyst sees the conflict
    # before reducing (the TJX 2026-09-08 DCF-80.76-vs-80.60 class used to be
    # caught only post-hoc by the verifier). Renders ONLY conflicted metrics;
    # a consistent/vendor-single metric is silent.
    try:
        from tradingagents.strategies.metric_reconcile import reconcile_metrics, render_reconcile

        leaf_dicts = [_leaf_as_dict(leaf) for leaf in leaves]
        reconciled = reconcile_metrics(leaf_dicts)
        reconcile_text = render_reconcile(reconciled)
        if reconcile_text:
            lines.append(
                "\n### Metric reconciliation (deterministic - gather-time)\n" + reconcile_text
            )
    except Exception:  # noqa: BLE001 - advisory; never break the evidence block
        pass
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# S11 - symmetric evidence for paired roles (plan section 2 S11; gate
# ``enable_evidence_symmetry``). S11 changes *how* evidence is gathered, never
# how anything is scored: every function below only reads the leaves and model
# pools the pipeline already journals, and none of them can raise.
# ---------------------------------------------------------------------------


def _config() -> dict:
    """The run config dict, or ``{}`` - a config read must never break a run."""
    try:
        from tradingagents.dataflows.config import get_config

        return dict(get_config() or {})
    except Exception:  # noqa: BLE001
        return {}


def _flag(name: str, default: bool = False) -> bool:
    """Read a run config gate defensively (matches the repo's tool pattern)."""
    return bool(_config().get(name, default))


def _side_stats(leaves, model_names) -> dict:
    """Per-side evidence stats: fired/planned tools, leaves, arg keys, as-of."""
    fired: set = set()
    arg_keys: set = set()
    as_of: set = set()
    n_ok = 0
    n_unavailable = 0
    count = 0
    for leaf in leaves or []:
        count += 1
        d = _leaf_as_dict(leaf)
        tool = str(d.get("tool") or "")
        if tool:
            fired.add(tool)
        if str(d.get("status") or "ok") == "ok":
            n_ok += 1
        else:
            n_unavailable += 1
        args = d.get("args") or {}
        arg_keys.update(str(k) for k in args)
        for key in ("current_date", "curr_date", "trade_date", "as_of", "end_date", "start_date"):
            value = args.get(key)
            if value:
                as_of.add(str(value))
    model = sorted(str(n) for n in (model_names or []))
    return {
        "fired": sorted(fired),
        "planned": sorted(fired | set(model)),
        "leaves": count,
        "ok": n_ok,
        "unavailable": n_unavailable,
        "arg_keys": arg_keys,
        "as_of": sorted(as_of),
        "discretionary": len(model),
    }


def _normalize_pairs(pairs, keys) -> list[dict]:
    """Normalize pair specs to ``{"pair", "side_a", "side_b"}``.

    ``pairs`` may be pairs of side keys, or dicts carrying ``side_a``/
    ``side_b`` (and an optional ``pair`` label). The default is every unordered
    pair of the side keys present, so a two-side fixture reports exactly one
    row.
    """
    if not pairs:
        import itertools

        return [
            {"pair": f"{a}/{b}", "side_a": a, "side_b": b}
            for a, b in itertools.combinations(sorted(keys), 2)
        ]
    out: list[dict] = []
    for spec in pairs:
        if isinstance(spec, dict):
            a = str(spec.get("side_a") or "")
            b = str(spec.get("side_b") or "")
            label = str(spec.get("pair") or f"{a}/{b}")
        else:
            a, b = (list(spec) + ["", ""])[:2]
            a, b = str(a), str(b)
            label = f"{a}/{b}"
        out.append({"pair": label, "side_a": a, "side_b": b})
    return out


def _pair_row(pair: str, side_a: str, side_b: str, sa: dict, sb: dict) -> dict:
    tool_diff = sorted(set(sa["planned"]) ^ set(sb["planned"]))
    arg_diff = sorted(sa["arg_keys"] ^ sb["arg_keys"])
    if sa["leaves"] == 0 or sb["leaves"] == 0:
        # A side with no leaves has nothing to compare: unavailable, never
        # SYMMETRIC (plan section 4 mutation "report SYMMETRIC when a side has
        # no leaves").
        verdict = "unavailable"
        differs: list[str] = []
    else:
        differs = tool_diff
        asymmetric = bool(tool_diff) or bool(arg_diff) or (
            sa["discretionary"] != sb["discretionary"]
        )
        verdict = "ASYMMETRIC" if asymmetric else "SYMMETRIC"
    return {
        "pair": pair,
        "side_a": side_a,
        "side_b": side_b,
        "planned": {"a": sa["planned"], "b": sb["planned"]},
        "fired": {"a": sa["fired"], "b": sb["fired"]},
        "leaves": {"a": sa["leaves"], "b": sb["leaves"]},
        "unavailable": {"a": sa["unavailable"], "b": sb["unavailable"]},
        "arg_key_diff": arg_diff,
        "as_of": {"a": sa["as_of"], "b": sb["as_of"]},
        "discretionary": {"a": sa["discretionary"], "b": sb["discretionary"]},
        "verdict": verdict,
        "differs_on": differs,
    }


def symmetry_report(evidence, model_pool=None, pairs=None) -> dict:
    """S11a: per-pair symmetry verdict over the evidence the pipeline journals.

    Implements the contract ``SYM(A,B) = (W_A = W_B) and (K_A = K_B) and
    (|D_A| = |D_B|)``: the planned tool sets (fired leaves union the
    ``_model_pool`` remainder), the arg keys, and the discretionary counts read
    from ``_model_pool``. ``differs_on`` names the tools whose planned sets
    differ. A pair with no leaves on either side renders ``unavailable`` -
    never ``SYMMETRIC`` (a missing input is never a score of zero).

    Pure and offline: it makes **zero** vendor calls (the tests assert this
    with a call counter, not by inspection). ``evidence`` is the state's
    ``tool_evidence`` dict; ``model_pool`` defaults to its ``_model_pool``
    metadata.
    """
    ev = dict(evidence or {})
    if model_pool is None:
        pools = {
            str(k): list(v or []) for k, v in (ev.get(MODEL_POOL_KEY) or {}).items()
        }
    elif isinstance(model_pool, dict):
        pools = {str(k): list(v or []) for k, v in model_pool.items()}
    else:
        pools = {}
    keys = {str(k) for k in ev if not str(k).startswith("_")}
    keys |= set(pools)
    rows = []
    for spec in _normalize_pairs(pairs, keys):
        a, b = spec["side_a"], spec["side_b"]
        rows.append(
            _pair_row(
                spec["pair"],
                a,
                b,
                _side_stats(ev.get(a), pools.get(a)),
                _side_stats(ev.get(b), pools.get(b)),
            )
        )
    if not rows or all(r["verdict"] == "unavailable" for r in rows):
        verdict = "unavailable"
    elif any(r["verdict"] == "ASYMMETRIC" for r in rows):
        verdict = "ASYMMETRIC"
    else:
        verdict = "SYMMETRIC"
    differs_on = sorted({name for r in rows for name in r["differs_on"]})
    basis = (
        f"{len(rows)} pair(s); planned = fired leaves union the _model_pool "
        "remainder; compared planned tool sets, arg keys and discretionary "
        "counts; no vendor calls made"
    )
    return {"pairs": rows, "verdict": verdict, "differs_on": differs_on, "basis": basis}


def symmetry_rows(report) -> list[dict]:
    """Persist-shape rows for the ``tool_evidence`` block (reporting-safe).

    ``reporting._evidence_sources`` walks every ``tool_evidence`` value as a
    leaf list, so the block must be a LIST of dicts (summary first, then one
    row per pair), never a nested dict. Each dict lacks a ``tool`` key, so the
    source-coverage walk skips it exactly like a metadata row.
    """
    report = report or {}
    rows = [
        {
            "verdict": str(report.get("verdict") or "unavailable"),
            "differs_on": list(report.get("differs_on") or []),
            "n_pairs": len(report.get("pairs") or []),
            "basis": str(report.get("basis") or ""),
        }
    ]
    rows.extend(list(report.get("pairs") or []))
    return rows


def stored_symmetry(evidence) -> dict | None:
    """Recover the ``symmetry_report`` dict from a persisted evidence block."""
    raw = (evidence or {}).get(SYMMETRY_KEY)
    if not raw:
        return None
    if isinstance(raw, dict):  # tolerate a caller that stored the dict directly
        return raw
    rows = list(raw)
    summary = rows[0] if rows else {}
    return {
        "pairs": rows[1:],
        "verdict": summary.get("verdict", "unavailable"),
        "differs_on": list(summary.get("differs_on") or []),
        "basis": summary.get("basis", ""),
    }


def _call_tool(call) -> str:
    return str((call or {}).get("name") or (call or {}).get("tool") or "")


def _split_discretionary(calls, allowance, forced_names) -> tuple[list, list]:
    """S11c's single split rule: keep the first ``allowance`` NON-forced calls.

    ``allowance is None`` means "no mirror": every call is kept, so a gate-off
    run - or a gate-on run with no declared pair - is byte-identical. A forced
    (S11b) leaf is never dropped AND never consumes the allowance (it is not a
    discretionary call). Shared by ``mirror_discretionary_budget`` (pair level)
    and the live ``_journal_executed`` path so the two cannot drift.
    """
    if allowance is None:
        return list(calls), []
    keep: list = []
    drop: list = []
    used = 0
    for call in calls:
        if _call_tool(call) in forced_names:
            keep.append(call)
            continue
        if used >= allowance:
            drop.append(call)
            continue
        used += 1
        keep.append(call)
    return keep, drop


def _journal_suppressed(role, dropped, state=None) -> None:
    """S11c: journal each suppressed call WITH its args (advisory, never raises)."""
    if not dropped:
        return
    try:
        from tradingagents.agents.utils.tool_call_log import log_tool_call

        for call in dropped:
            log_tool_call(
                role,
                _call_tool(call),
                "suppressed",
                args=(call or {}).get("args"),
                state=state,
                in_model_pool=True,
            )
    except Exception:  # noqa: BLE001 - advisory, never break the loop
        pass


def mirror_discretionary_budget(
    calls_by_role,
    *,
    pairs=None,
    budget=None,
    forced=(),
    state=None,
    journal=True,
) -> dict:
    """S11c: mirror each paired role's discretionary call allowance.

    Each pair gets the same allowance - the smaller of its two sides' call
    counts, or an explicit ``budget`` - and any call beyond it is suppressed
    AND journaled with its args (``event='suppressed'``) so the asymmetry is
    visible rather than hidden. The mirror is per pair, never global, and a
    call whose tool is a forced (S11b) leaf is never suppressed. Returns the
    per-role kept/suppressed split; never raises.
    """
    forced_names = {str(f) for f in (forced or ())}
    source = dict(calls_by_role or {})
    roles = sorted(str(r) for r in source)
    kept: dict[str, list] = {r: list(source.get(r) or []) for r in roles}
    suppressed: dict[str, list] = {r: [] for r in roles}
    allowances: dict[str, int] = {}
    for spec in _normalize_pairs(pairs, roles):
        a, b = spec["side_a"], spec["side_b"]
        if a not in kept or b not in kept or a == b:
            continue
        allowance = min(len(kept[a]), len(kept[b])) if budget is None else int(budget)
        allowances[spec["pair"]] = allowance
        for role in (a, b):
            keep, drop = _split_discretionary(kept[role], allowance, forced_names)
            kept[role] = keep
            suppressed[role] = drop
            if journal:
                _journal_suppressed(role, drop, state=state)
    return {
        "pairs": _normalize_pairs(pairs, roles),
        "allowances": allowances,
        "kept": kept,
        "suppressed": suppressed,
    }


def _pair_spec_for(role: str, config: dict | None) -> dict | None:
    """The declared pair spec containing ``role`` (``evidence_symmetry_pairs``)."""
    for spec in (config or {}).get("evidence_symmetry_pairs") or []:
        if not isinstance(spec, dict):
            continue
        if role in [str(r) for r in (spec.get("roles") or [])]:
            return spec
    return None


def _pair_budget_for(role: str, config: dict | None) -> int | None:
    """The mirrored discretionary allowance DECLARED for ``role``'s pair."""
    spec = _pair_spec_for(role, config)
    if spec is None:
        return None
    try:
        return int(spec.get("budget"))
    except (TypeError, ValueError):
        return None


def _observed_discretionary(state: dict, role: str) -> int | None:
    """Discretionary (model-pool) leaves ``role`` gathered, or None if not run.

    None - not 0 - for a role with no evidence key yet: counting "has not run"
    as zero would let a partner that produced no count at all cap a first mover
    to nothing.
    """
    evidence = state.get(TOOL_EVIDENCE_KEY) or {}
    if role not in evidence:
        return None
    pool = set((evidence.get(MODEL_POOL_KEY) or {}).get(role) or [])
    return sum(
        1
        for leaf in evidence.get(role) or []
        if str(_leaf_as_dict(leaf).get("tool") or "") in pool
    )


def _pair_allowance_for(role: str, state: dict, config: dict | None) -> int | None:
    """S11c: ``role``'s allowance - declared budget, else the pair's observed min.

    The plan's rule is "the same allowance = the smaller of its two sides' call
    counts, or an explicit budget". The explicit budget comes from the pair
    spec; without one the mirror binds to the smallest discretionary count an
    already-run partner recorded, and stays uncapped (None) while no partner
    count exists.
    """
    spec = _pair_spec_for(role, config)
    if spec is None:
        return None
    declared = _pair_budget_for(role, config)
    if declared is not None:
        return declared
    others = [str(r) for r in (spec.get("roles") or []) if str(r) != role]
    counts = [c for c in (_observed_discretionary(state, r) for r in others) if c is not None]
    return min(counts) if counts else None


def parse_evidence_plan(raw, whitelist, tools_by_name) -> tuple[dict | None, str]:
    """S11d: parse + validate a model plan reply into ``{tool: {arg: value}}``.

    Accepts a JSON object or its string form. Returns ``(plan, "")`` on a valid
    plan and ``(None, reason)`` on an empty, unparseable, out-of-whitelist or
    schema-violating one. Never raises - a bad plan falls back to today's loop
    (plan section 2 S11d).
    """
    import re

    allowed = {str(w) for w in (whitelist or ())}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, "empty plan"
        try:
            raw = json.loads(text)
        except ValueError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None, "plan is not JSON"
            try:
                raw = json.loads(match.group(0))
            except ValueError:
                return None, "plan is not JSON"
    if not isinstance(raw, dict) or not raw:
        return None, "empty plan"
    plan: dict[str, dict] = {}
    for tool, args in raw.items():
        name = str(tool)
        if name not in allowed:
            return None, f"tool {name!r} is outside the whitelist"
        if name not in tools_by_name:
            return None, f"tool {name!r} is not bound to this analyst"
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return None, f"args for {name!r} are not an object"
        declared = getattr(tools_by_name[name], "args", None) or {}
        if declared:
            unknown = sorted(k for k in args if k not in declared)
            if unknown:
                return None, f"args for {name!r} outside its schema: {unknown}"
            missing = sorted(
                k for k, meta in declared.items() if "default" not in meta and k not in args
            )
            if missing:
                return None, f"args for {name!r} missing required keys: {missing}"
        plan[name] = {str(k): v for k, v in args.items()}
    return plan, ""


def plan_evidence_calls(
    tools_by_name,
    plan,
    *,
    timeout_s: float = 30,
    max_parallel: int = 1,
    summary_window: int = 12000,
) -> list[ToolEvidenceLeaf]:
    """S11d: fire a validated plan through the existing executor.

    Bounded parallel, per-call timeout and error leaves come from
    ``gather_evidence``; the plan's per-tool args are passed verbatim.
    """
    names = [n for n in plan if n in tools_by_name]
    return gather_evidence(
        tools_by_name,
        names,
        context=None,
        timeout_s=timeout_s,
        max_parallel=max_parallel,
        summary_window=summary_window,
        args_by_name={n: plan[n] for n in names},
    )


PLAN_PROMPT_HEADER = """You plan one analyst's TOOL CALLS before the report is written.

The tools below are the analyst's model-discretionary remainder. Choose a
minimal plan - only the calls whose arguments you can state concretely. Reply
with ONE JSON object mapping each chosen tool name to its argument object, and
nothing else. If you cannot supply a call's arguments, omit that tool (an
empty object is a valid plan). Never invent a tool or an argument name.
"""


def build_plan_prompt(analyst_key: str, model_names, tools) -> str:
    """S11d: the cheap-plan prompt over the model-pool remainder."""
    by_name = {getattr(t, "name", ""): t for t in tools}
    lines = [PLAN_PROMPT_HEADER, f"Analyst: {analyst_key}", "", "Tools:"]
    for name in model_names:
        fn = by_name.get(name)
        schema = getattr(fn, "args", None) or {}
        desc = (getattr(fn, "description", "") or "").strip().splitlines()
        lines.append(f"- {name}: {desc[0] if desc else ''}".rstrip())
        for arg, meta in schema.items():
            required = "required" if "default" not in meta else "optional"
            lines.append(f"    {arg} ({required})")
    return "\n".join(lines)


def make_llm_planner(llm):
    """S11d: build the one-cheap-completion planner callable.

    Returns ``planner(analyst_key, model_names, tools) -> raw plan text``; the
    caller validates + fires it (``resolve_model_pool_plan``), so a malformed
    completion falls back to today's loop rather than raising.
    """

    def planner(analyst_key, model_names, tools):
        prompt = build_plan_prompt(analyst_key, list(model_names), tools)
        response = llm.invoke(prompt)
        return getattr(response, "content", response)

    return planner


def resolve_model_pool_plan(raw, tools_by_name, whitelist) -> tuple[list, str]:
    """S11d: validate a plan and fire it; ``""`` on success, reason otherwise.

    On any empty/invalid/out-of-whitelist plan it returns ``([], reason)`` so
    the caller falls back to today's loop and states why - it never raises.
    """
    try:
        plan, error = parse_evidence_plan(raw, whitelist, tools_by_name)
        if plan is None:
            return [], error
        return plan_evidence_calls(tools_by_name, plan), ""
    except Exception as exc:  # noqa: BLE001 - a plan must never abort the gather
        return [], f"plan failed: {type(exc).__name__}: {exc}"


__all__ = [
    "ALL_LITERAL",
    "CONTEXT_ARG_KEYS",
    "EVIDENCE_SECTION_HEADER",
    "MODEL_POOL_HEADER",
    "MODEL_POOL_KEY",
    "PLAN_PROMPT_HEADER",
    "SYMMETRY_KEY",
    "TOOL_ARG_DEFAULTS",
    "TOOL_ARG_DEFAULT_REASONS",
    "TOOL_EVIDENCE_KEY",
    "ToolEvidenceLeaf",
    "build_plan_prompt",
    "classify_tool_pools",
    "format_evidence_block",
    "gather_evidence",
    "gather_for_analyst_node",
    "make_evidence_leaf",
    "make_llm_planner",
    "make_short_circuit_tool_node",
    "mirror_discretionary_budget",
    "parse_evidence_plan",
    "parse_forced_spec",
    "plan_evidence_calls",
    "resolve_model_pool_plan",
    "short_circuit_tool_calls",
    "stored_symmetry",
    "symmetry_report",
    "symmetry_rows",
]
