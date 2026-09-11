"""Calc -> agent wiring audit gate (DSA phase A-D follow-up).

Every public calculation/formula in ``strategies/`` and the quantitative
``dataflows/`` MUST be reachable from the pipeline that feeds virtual agents:
the agent tool surface (``agents/utils/*_tools.py`` + analyst tool lists),
the graph/state layer, ``reporting``, or a production script. A public calc
with ZERO references outside its own module is either a wiring gap (the
agents cannot reach a computed read they were built for) or dead legacy.

The whitelist below is the audited legacy set (dead/helper code or a pure
utility whose home is a test helper), each with a reason. Anything new that
lands on the list in a future change fails the gate, so wiring decisions are
reviewed, not silent.
"""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CALC_DIRS = (REPO / "tradingagents" / "strategies", REPO / "tradingagents" / "dataflows")
REFERENCE_DOMAINS = (
    REPO / "tradingagents",
    REPO / "scripts",
)

# Audited legacy/dead set: module:function -> why it is exempt from wiring.
LEGACY_WHITELIST = {
    "strategies/backtest_engine.py:is_filled": "harness internals (backtest engine)",
    "strategies/backtest_engine.py:cancel": "harness internals (backtest engine)",
    "strategies/capital_income.py:indicated_yield_from_rate": "dead helper (capital_income screener path)",
    "strategies/capital_income.py:apply_top_n": "dead helper (capital_income screener path)",
    "strategies/debate_claim.py:for_round": "dead helper after structured-debate refactor",
    "strategies/factors.py:z_composite_alpha": "legacy factor composite (qlib factor_expressions is the live path)",
    "strategies/factors.py:momentum_multihorizon": "legacy factor composite (qlib factor_expressions is the live path)",
    "strategies/liquidity_risk.py:volume_share_slippage": "legacy slippage model (not used by the liquidity gate)",
    "strategies/liquidity_risk.py:market_impact_slippage": "legacy slippage model (not used by the liquidity gate)",
    "dataflows/config.py:reset_config": "test/utility helper, not a calc",
    "dataflows/schema.py:to_markdown": "dead formatting utility (schema layer)",
    # W4-2 typed-state schema artifacts - DESIGN REFERENCE by explicit design
    # (module doc: \"nothing re-wires the existing graph\"): the dataclass
    # schemas + pure compact summarizer are the pinned spec for the future
    # typed-state cutover, not an agent calc. Permanent classification, not
    # deferred work - the tests pin the behavior today.
    "strategies/typed_state.py:summarize_report": "design-reference artifact (W4-2 typed-state spec), tests-pinned, intentionally not agent-bound",
    "strategies/typed_state.py:to_compact": "design-reference artifact (W4-2 typed-state spec), tests-pinned, intentionally not agent-bound",
    # W4-8 complexity/maintenance-tax report - a developer ops tool (LOC +
    # fan-in), not an agent read; no periodic hook by design.
    "strategies/integrity_tools.py:complexity_report": "developer ops report (LOC/fan-in); not an agent calc",
    # options_surface IV-rank read - PERMANENT data limitation: no vendor
    # delivers a per-day IV history (the cboe/chain reads are spot-only), so
    # the percentile has no input and stays a tested helper awaiting source.
    "strategies/options_surface.py:iv_percentile": "needs per-day IV history no vendor delivers (chain is spot-only)",
}


def _public_funcs(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")}


def _reference_blob() -> str:
    parts = []
    for dom in REFERENCE_DOMAINS:
        for p in sorted(dom.rglob("*.py")):
            try:
                parts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(parts)


blob = _reference_blob()

# A strategy module with ZERO references anywhere in the production domains
# (agents / graph / reporting / dataflows-interface / scripts / entrypoints)
# is either a wiring gap or dead legacy - same contract as the per-fn check,
# but at the module level so a whole unwired module cannot hide behind its own
# internal self-references. Whitelisted definitions live in LEGACY_WHITELIST
# keyed by ANY of the module's public functions (the per-fn gate below still
# requires each specific fn to be wired or whitelisted).
_MODULE_CASES = []
for f in sorted(REPO.joinpath("tradingagents", "strategies").glob("*.py")):
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        continue
    fns = {n.name for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and not n.name.startswith("_")}
    if fns and not any(fn in blob for fn in fns):
        key = next(iter(sorted(fns)))
        _MODULE_CASES.append((f"{f.parent.name}/{f.name}", key))


@pytest.mark.parametrize("case", _MODULE_CASES, ids=[c[0] for c in _MODULE_CASES])
def test_module_reachable_or_whitelisted(case):
    module, any_fn = case
    assert f"{module}:{any_fn}" in LEGACY_WHITELIST, (
        f"strategy module {module} has zero references outside itself - it is "
        "either a wiring gap (the virtual agents cannot reach its calculations) "
        "or dead code. Wire it to an agent tool / graph / reporting / script, "
        "or whitelist one of its functions in LEGACY_WHITELIST with a reason."
    )

CASES = []
for calc_dir in CALC_DIRS:
    for f in sorted(calc_dir.glob("*.py")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fns = sorted(_public_funcs(f))
        # Module-level reachability (any public fn referenced outside the
        # module itself) - the whole-module escape hatch.
        module_reachable = any(blob.count(fn) - text.count(fn) > 0 for fn in fns)
        for fn in fns:
            # Wired = referenced OUTSIDE its own module, OR an internal
            # helper of a module that is itself externally reachable. A fn
            # referenced only by its own module's text (the old self-count
            # escape) is NOT wired unless the module is reachable.
            outside = blob.count(fn) - text.count(fn)
            internal_use = text.count(fn) > 1
            if outside > 0 or (module_reachable and internal_use):
                continue
            CASES.append((f"{calc_dir.name}/{f.name}:{fn}", f"{calc_dir.name}/{f.name}:{fn}"))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_public_calc_reachable_or_whitelisted(case):
    key, _ = case
    assert key in LEGACY_WHITELIST, (
        f"calculation {key} has zero references outside its module (and is "
        "not an internal helper of a reachable module) - it is either a wiring "
        "gap (virtual agents cannot reach a computed read) or dead code. Wire "
        "it as an agent tool / pipeline hook, or move it to the "
        "LEGACY_WHITELIST with a reason."
    )


# ---------------------------------------------------------------------------
# @tool -> agent-binding gate: every LangChain @tool in agents/utils/*_tools.py
# must be bound by name in the agent-side binding surface (the graph ToolNode
# lists, the Trader/risk-debator tool loops, or an analyst/arbiter binding
# file) - otherwise the analyst can never actually call it. This closes the
# "defined but unbound" gap that text-substring audits cannot see.
# ---------------------------------------------------------------------------

TOOL_BINDING_DOMAINS = (
    list((REPO / "tradingagents" / "agents" / "analysts").rglob("*.py"))
    + list((REPO / "tradingagents" / "agents" / "arbiters").rglob("*.py"))
    + list((REPO / "tradingagents" / "agents" / "managers").rglob("*.py"))
    + list((REPO / "tradingagents" / "agents" / "risk_mgmt").rglob("*.py"))
    + list((REPO / "tradingagents" / "agents" / "researchers").rglob("*.py"))
    + [REPO / "tradingagents" / "agents" / "utils" / "risk_tool_loop.py"]
    + list((REPO / "tradingagents" / "graph").glob("*.py"))
)
TOOL_BINDING_BLOB = "\n".join(
    p.read_text(encoding="utf-8", errors="ignore")
    for p in TOOL_BINDING_DOMAINS
    if p.exists()
)

# Tools bound only inside their own module (no agent-side binding) -> must be
# whitelisted with a reason (e.g. internal helpers a wrapper calls directly).
TOOL_LEGACY_BINDING = {
    # @tool functions that no analyst binds and that are not wired into the
    # risk loop. They were previously "bound" only by appearing in a graph
    # ToolNode list, which satisfied this gate while leaving them uncallable
    # by any LLM (the model can only emit calls for tools it was bound).
    # S1 now derives every ToolNode from the analyst's own toolset, so the
    # truth is visible: these are library/registry reads with no agent
    # surface. Each entry states its real consumers; revisit as either
    # "bind + document in the analyst prompt" or "delete".
    "get_consensus": "advisory consensus read; docs/api_reference.md + AGENT_ONBOARDING; exercised by test_analysis_tools.py",
    "get_enhanced_index_tilt": "index-tilt read; docs/design_qlib_integration.md; exercised by test_qlib_wiring.py",
    "get_kelly_alloc": "allocation read documented in api_reference.md; no code/test consumer",
    "get_kyle_lambda": "liquidity read documented in api_reference.md; no code/test consumer",
    "get_macro_regime_read": "macro-regime read documented in README/api_reference; no code/test consumer",
    "get_no_trade_guard_band": "rebalance guard read documented in README; no code/test consumer",
    "get_pair_risk": "pair-risk read; docs/design_risk_calculations_agent_wiring.md; exercised by test_risk_agent_wiring.py",
    "get_prediction_ledger_score": "ledger-score read documented in README/api_reference; no code/test consumer",
    "get_prompt_injection_read": "injection-scan read; no consumer anywhere (docs, tests or code) - bind-or-delete candidate",
    "get_stress_grid_read": "stress-grid read documented in README/api_reference; no code/test consumer",
    "get_thesis_evidence_matrix": "thesis-evidence read; no consumer anywhere (docs, tests or code) - bind-or-delete candidate",
    "get_topk_drop_plan": "drop-plan read; docs/implementation_qlib_integration.md; exercised by test_qlib_wiring.py",
    "get_trade_excursions": "excursion read; docs/design_risk_calculations_agent_wiring.md; exercised by test_risk_agent_wiring.py",
    "get_trade_outcome_metrics": "outcome-metric read documented in README/api_reference; no code/test consumer",
    "get_vif_read": "multicollinearity read; docs/design_risk_calculations_agent_wiring.md; exercised by test_risk_agent_wiring.py",
    "screen_equities": "equity screener; called by scripts/screener.py (CLI-facing), not an analyst tool",
}


def _tool_names(path: Path):
    """Names of @tool-decorated PUBLIC functions in a file (LangChain
    decorator). Underscore-prefixed (private @tool helpers called by other
    tools) are excluded from the binding requirement."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        for dec in node.decorator_list:
            is_tool = (
                isinstance(dec, ast.Name) and dec.id == "tool"
            ) or (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Name)
                and dec.func.id == "tool"
            ) or (
                isinstance(dec, ast.Attribute) and dec.attr == "tool"
            )
            if is_tool:
                out.append(node.name)
                break
    return out


TOOL_CASES = []
for f in sorted((REPO / "tradingagents" / "agents" / "utils").glob("*_tools.py")):
    own = f.read_text(encoding="utf-8", errors="ignore")
    for name in sorted(_tool_names(f)):
        # The tool's own module is in agents/utils - binding must be in the
        # non-utils binding surface (its own def text would self-count).
        if name in TOOL_BINDING_BLOB:
            continue
        TOOL_CASES.append((f"{f.parent.name}/{f.name}:{name}", name))


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c[0] for c in TOOL_CASES])
def test_tool_bound_to_agent_surface(case):
    key, name = case
    assert name in TOOL_LEGACY_BINDING, (
        f"@tool {key} is not bound anywhere in the agent surface (graph "
        "ToolNode lists / risk-tool loop / analyst files) - the agents can "
        "never call it. Bind it to a ToolNode or the risk loop, or "
        "whitelist it in TOOL_LEGACY_BINDING with a reason."
    )


# ---------------------------------------------------------------------------
# prompt-guidance gate: every @tool bound to an analyst's tool list must be
# mentioned in that analyst's system_message (or _build_system_message), so
# the LLM knows WHEN the tool applies. This closes the "bound but never
# explained" gap - a tool in the list an LLM never triggers is dead weight,
# and the risk-loop binds tools by name with the loop's own guidance.
# ---------------------------------------------------------------------------


def _system_message_strings(path: Path) -> str:
    """Concatenated prompt text from ``system_message = (...+...)`` assignments
    and ``_build_system_message`` f-string returns (AST-safe, paren-safe)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return ""
    vals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "system_message":
                    vals.append(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == "_build_system_message":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.JoinedStr):
                    vals.append(sub.value)
    out = []

    def collect(v):
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            out.append(v.value)
        elif isinstance(v, ast.JoinedStr):
            for x in v.values:
                if isinstance(x, ast.Constant):
                    out.append(x.value)
        elif isinstance(v, ast.BinOp):
            collect(v.left)
            collect(v.right)
        elif isinstance(v, ast.Tuple):
            for e in v.elts:
                collect(e)

    for v in vals:
        collect(v)
    return "\n".join(out)


def _tool_list_names(path: Path) -> set[str]:
    """Names appearing in the file's indented tool-list assignments (the same
    heuristic the binding gate uses for the tool list)."""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    try:
        ast.parse(txt)
    except (OSError, SyntaxError):
        return set()
    clean = re.sub(r"#.*$", "", txt, flags=re.M)
    return {m.group(1) for m in re.finditer(r"^\s+([A-Za-z_]\w*),?\s*$", clean, re.M)}


def _imported_names(path: Path) -> set[str]:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(txt)
    except (OSError, SyntaxError):
        return set()
    return {a.asname or a.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) for a in node.names}


def _tool_names_set() -> set[str]:
    names: set[str] = set()
    for f in (REPO / "tradingagents" / "agents" / "utils").glob("*_tools.py"):
        names |= set(_tool_names(f))
    return names


PROMPT_CASES: list[tuple[str, str, str]] = []
for f in sorted((REPO / "tradingagents" / "agents" / "analysts").rglob("*.py")):
    prompt = _system_message_strings(f)
    listed = _tool_list_names(f)
    imported = _imported_names(f)
    for name in sorted(listed & imported & _tool_names_set()):
        if re.search(r"\b" + re.escape(name) + r"\b", prompt):
            continue
        PROMPT_CASES.append((f"{f.parent.name}/{f.name}:{name}", name, f.name))



@pytest.mark.parametrize("case", PROMPT_CASES, ids=[c[0] for c in PROMPT_CASES])
def test_bound_tool_has_prompt_guidance(case):
    key, name, analyst = case
    assert False, (
        f"@tool {key} is in {analyst}'s tool list but is never mentioned in its "
        "system_message - the LLM has no guidance for when to call it. Add a "
        "'cite it before any X claim' line for this tool to that analyst's prompt."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
