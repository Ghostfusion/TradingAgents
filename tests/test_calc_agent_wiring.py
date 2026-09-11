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

def _bound_tool_names() -> set[str]:
    """Names callable by an agent, read from the toolset OBJECTS.

    The old gate searched the raw text of the analyst/graph files, so a tool
    named only in a prompt sentence counted as "bound" while no LLM could
    call it (the gate asserted the docs, not the capability). Reading the
    actual lists is the only definition that cannot be fooled by wording.
    """
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    names: set[str] = set()
    for key in ("market", "news", "fundamentals"):
        names |= {t.name for t in analyst_toolset(key)}
    names |= {t.name for t in risk_tool_loop.RISK_DEBATOR_TOOLS}
    names |= {t.name for t in risk_tool_loop.TRADER_TOOLS}
    return names

# Tools bound only inside their own module (no agent-side binding) -> must be
# whitelisted with a reason (e.g. internal helpers a wrapper calls directly).
TOOL_LEGACY_BINDING = {
    # @tool functions with NO callable agent surface. Every entry names either
    # the bound tool that covers the same claim or the real consumer of the
    # read; "nothing uses it" is not an acceptable reason to keep one, and the
    # test above refuses an entry once its tool becomes bound.
    "get_consensus": "covered: the PM receives the computed agreement number in computed_independent_vote; both managers run NO_EXTERNAL_TOOLS",
    "get_enhanced_index_tilt": "universe-level index tilt; consumer is the screener alloc block (docs/design_qlib_integration.md), exercised by tests/test_qlib_wiring.py",
    "get_kelly_alloc": "covered: get_allocation_black_litterman / get_position_sizing / get_hrp_alloc are the bound allocation reads",
    "get_kyle_lambda": "covered: get_liquidity_risk returns ILLIQ / float-turnover / IWF / verdict; the tool docstring forbids per-ticker use",
    "get_no_trade_guard_band": "rebalance guard; needs a current book weight no agent surface carries (README documents it)",
    "get_prediction_ledger_score": "covered: get_ledger_risk_state is the bound win-rate read; the stops/targets half is get_trade_outcome_metrics (bound to the debators)",
    "get_prompt_injection_read": "ingestion-layer guard: by the time an LLM can call it the text is already in context, so the scan belongs to the loader, not a tool",
    "get_stress_grid_read": "covered: get_scenario_dcf is the modelled version; the grid never receives its sensitivity axis and says so",
    "get_topk_drop_plan": "universe-level drop plan; consumer is the screener alloc block (docs/implementation_qlib_integration.md) - the PM that docs once gave it to runs NO_EXTERNAL_TOOLS",
    "get_trade_excursions": "journal / QA rows for the CLI batch path (docs/design_risk_calculations_agent_wiring.md), exercised by tests/test_risk_agent_wiring.py",
    "screen_equities": "CLI screener (scripts/screener.py, enable_screener=False); breadth is covered by the bound get_market_movers",
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
_ALL_TOOL_NAMES: set[str] = set()
for f in sorted((REPO / "tradingagents" / "agents" / "utils").glob("*_tools.py")):
    for name in sorted(_tool_names(f)):
        _ALL_TOOL_NAMES.add(name)
        if name in _bound_tool_names():
            continue
        TOOL_CASES.append((f"{f.parent.name}/{f.name}:{name}", name))


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c[0] for c in TOOL_CASES])
def test_tool_bound_to_agent_surface(case):
    key, name = case
    assert name in TOOL_LEGACY_BINDING, (
        f"@tool {key} is not in any agent toolset or tool loop (the objects "
        "are the source of truth) - no LLM can call it. Bind it to a toolset "
        "or the risk loop, or declare it in TOOL_LEGACY_BINDING with the real "
        "consumer and the reason it stays unbound."
    )


def test_declared_tools_are_real_and_unbound():
    """A declaration must name a real @tool that is genuinely unbound.

    Both halves matter: a typo would silently exempt nothing, and a stale
    entry would keep claiming "no agent can call this" for a tool that is now
    bound. The list may only shrink as declarations are wired or deleted.
    """
    bound = _bound_tool_names()
    stale = sorted(n for n in TOOL_LEGACY_BINDING if n in bound)
    unknown = sorted(n for n in TOOL_LEGACY_BINDING if n not in _ALL_TOOL_NAMES)
    assert not stale, (
        "TOOL_LEGACY_BINDING still declares tools that ARE bound - remove "
        f"these entries: {stale}"
    )
    assert not unknown, (
        "TOOL_LEGACY_BINDING names functions that are not @tools in "
        f"agents/utils/*_tools.py - drop the typos: {unknown}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
