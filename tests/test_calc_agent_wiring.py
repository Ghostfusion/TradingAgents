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
from collections import Counter
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
    # html.parser.HTMLParser dispatches on these EXACT method names, so they
    # cannot be renamed to _-private or inlined. They are the override hooks
    # of `_TableParser`, the class the reachable `extract_tables` /
    # `governance_tables` drive.
    "dataflows/proxy.py:handle_starttag": "HTMLParser protocol override (name fixed by stdlib)",
    "dataflows/proxy.py:handle_endtag": "HTMLParser protocol override (name fixed by stdlib)",
    "dataflows/proxy.py:handle_data": "HTMLParser protocol override (name fixed by stdlib)",
    "dataflows/moomoo.py:close_all_contexts": (
        "lifecycle helper, not a computed read: closes the SDK's OpenQuoteContexts "
        "by code (the web app's jobs.shutdown() and its test suite call it)"
    ),
    "strategies/backtest_engine.py:is_filled": "harness internals (backtest engine)",
    "strategies/backtest_engine.py:cancel": "harness internals (backtest engine)",
    "strategies/capital_income.py:indicated_yield_from_rate": "dead helper (capital_income screener path)",
    "strategies/capital_income.py:apply_top_n": "dead helper (capital_income screener path)",
    "strategies/debate_claim.py:for_round": "dead helper after structured-debate refactor",
    "strategies/factors.py:z_composite_alpha": "legacy factor composite (qlib factor_expressions is the live path)",
    # momentum_multihorizon was whitelisted as legacy; it is now wired into
    # get_momentum_detail (the 21/63/126/252 ensemble), so it left the list.
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
    # The factor schema's own self-check: it asserts one identity per measure,
    # +/-1 directions and that no factor enters two sub-scores. Its consumer is
    # the schema's test suite (a violation must fail a build, not a run).
    "strategies/factor_schema.py:validate_schema": "the schema's own self-check (one identity per measure, +/-1 directions, no factor in two sub-scores); its consumer is the schema's test suite, so a violation fails a build rather than a run",
}

# ---------------------------------------------------------------------------
# Class-level declaration: what the corrected detector surfaced, by class.
# ---------------------------------------------------------------------------
#
# The corrections above (whole-identifier matching, and an `__all__` entry no
# longer counting as a use) surfaced 115 public calculators that no production
# code references. Eight reviewers each took one contiguous slice of the
# corrected list and verified, per function, what it is and who could own it.
#
# Four classes came out, and all of them are DECLARATIONS WITH A REASON - the
# same standing as LEGACY_WHITELIST above: a wiring decision the owner has seen,
# not a silent pass. `ADVISORY_CALCULATORS` says why a read is deliberately not
# agent-bound; `GAP_CALCULATORS` is the actionable half - a verified wiring gap
# with the consumer that should own it, recorded so the follow-up is a named
# task rather than a rediscovery.
#
# Nothing moves silently: wiring one removes its key, and
# `test_declared_calculators_are_real_and_still_orphaned` refuses a key that is
# no longer orphaned (a stale exemption) or that names no real function (a typo).

ADVISORY_CLASSES = {
    "reference": (
        "reference / recipe / debug / schema-self-check read, or a read whose "
        "claim is already covered by a different wired symbol - correct and "
        "test-pinned, deliberately not agent-bound (cf. the W4-2 typed-state "
        "artifacts above)"
    ),
    "dead": (
        "no consumer, and a live duplicate implements the same read - the wired "
        "symbol that covers it is named in the D3 triage record (FINDINGS.md §2)"
    ),
}

ADVISORY_CALCULATORS = {
    "strategies/analyst_revisions.py:winsor_z": "reference",
    "strategies/backtest_engine.py:simple_long_pnl": "reference",
    "strategies/backtest_models.py:slip_price": "reference",
    "strategies/breadth_depth.py:concentration_hhi": "reference",
    "strategies/calibration.py:isotonic_calibrate": "reference",
    "strategies/capital_income.py:adtv_dollar": "reference",
    "strategies/catalyst.py:apply_catalyst_scale": "reference",
    "strategies/cross_section.py:no_trade_band": "reference",
    "strategies/cross_section.py:residualize_returns": "reference",
    "strategies/cycle_tilt.py:macro_stance": "reference",
    "strategies/data_quality.py:disagreement_flag": "reference",
    "strategies/debate_claim.py:by_role": "reference",
    "strategies/decision_guardrail.py:score_for_rating": "reference",
    "strategies/domain_bundles.py:news_relevance_profile": "reference",
    "strategies/evaluate.py:gross_exposure": "reference",
    "strategies/evaluate.py:net_exposure": "reference",
    "strategies/evaluate.py:rolling_beta": "reference",
    "strategies/evaluate.py:rolling_sharpe": "reference",
    "strategies/evaluate.py:turnover_cost": "reference",
    "strategies/exits.py:net_of_cost": "reference",
    "strategies/exits.py:rebalance_due": "reference",
    "strategies/exits.py:stop_to_breakeven_r": "reference",
    "strategies/factor_expressions.py:clear_expr_cache": "reference",
    "strategies/factor_expressions.py:cross_sectional_rank": "reference",
    "strategies/factor_expressions.py:expr_cache_size": "reference",
    "strategies/factors.py:fama_french_5_factor": "reference",
    "strategies/factors.py:value_momentum_score": "reference",
    "strategies/fundamental_score.py:factor_gap_report": "reference",
    "strategies/integrity_tools.py:thesis_evidence_matrix": "reference",
    "strategies/lottery.py:max_drawdown_of_closes": "dead",
    "strategies/market_session.py:decompose_returns_text": "reference",
    "strategies/news_score.py:component_weight_share": "reference",
    "strategies/news_score.py:headline_similarity": "reference",
    "strategies/news_score.py:news_confidence": "reference",
    "strategies/news_score.py:news_persistence": "reference",
    "strategies/news_score.py:news_volume_acceleration": "reference",
    "strategies/options_math.py:black_vol_surface": "reference",
    "strategies/options_math.py:implied_vol_and_greeks": "reference",
    "strategies/portfolio_optimizer.py:enforce_sector_exposure": "reference",
    "strategies/rate_utils.py:compound_factor": "reference",
    "strategies/rate_utils.py:equivalent_rate": "reference",
    "strategies/rate_utils.py:forward_rate": "reference",
    "strategies/rate_utils.py:monotone_fill": "reference",
    "strategies/report_attribution.py:admit_factor": "reference",
    "strategies/report_attribution.py:reference_names": "reference",
    "strategies/risk_score.py:category_weight_share": "reference",
    "strategies/sector_breadth.py:msi_zone": "reference",
    "strategies/sector_breadth.py:rrg_heading": "reference",
    "strategies/sentiment.py:herfindahl_index": "reference",
    "strategies/sentiment_score.py:category_weight_share": "reference",
    "strategies/size.py:optimal_f": "reference",
    "strategies/size.py:position_size_with_risk": "dead",
    "strategies/size.py:stop_loss_atr": "dead",
    "strategies/statistical.py:ecm_loading": "reference",
    "strategies/statistical.py:pair_quantities": "reference",
    "strategies/swing.py:fib_levels": "dead",
    "strategies/technical_score.py:category_weight_share": "reference",
    "dataflows/alpaca.py:get_bars_batch": "reference",
    "dataflows/alpaca.py:get_latest_snapshot": "reference",
    "dataflows/event_calendars.py:calendar_coverage": "reference",
    "dataflows/event_calendars.py:court_probe": "reference",
    "dataflows/fmp.py:get_balance_history": "reference",
    "dataflows/fmp.py:get_cashflow_history": "reference",
    "dataflows/fmp.py:get_earnings_surprises": "reference",
    "dataflows/fmp.py:get_ev_history": "reference",
    "dataflows/fmp.py:get_historical_prices": "reference",
    "dataflows/fmp.py:get_key_metrics_ttm": "reference",
    "dataflows/interface.py:route_to_vendor_typed": "reference",
    "dataflows/moomoo.py:get_kl_quota_moomoo": "reference",
    "dataflows/pit_registry.py:read_all": "reference",
    "dataflows/registry.py:all_coverage": "reference",
    "dataflows/registry.py:command_map": "reference",
    "dataflows/registry.py:filter_params": "reference",
    "dataflows/registry.py:method_requires_credentials": "reference",
    "dataflows/registry.py:vendor_for_cfg": "reference",
    "dataflows/vendor_breaker.py:probe_due": "reference",
    "dataflows/vendor_breaker.py:state_snapshot": "reference",
}

# Verified wiring gaps: no wired equivalent implements the read, and the named
# consumer should own it. Deferred, not forgotten - wiring one is a
# calc -> tool -> binding -> prompt change of its own, never a rider on this gate
# fix. `""` marks a gap whose consumer the triage could not name from the tree.
GAP_CALCULATORS = {
    "strategies/alpha_eval.py:insight_accuracy": "agents/utils/analysis_tools.py:get_alpha_scoring",
    "strategies/complexity.py:approximate_entropy": "agents/utils/analysis_tools.py:get_mean_reversion_quality",
    "strategies/debate_score.py:divergence_check": "docs/design_multi_agent_debate.md §4.5 (no wired equivalent)",
    "strategies/debate_score.py:reweight_to_baseline": "agents/researchers/structured_debate.py:create_debate_finalize",
    "strategies/domain_bundles.py:get_fundamental_profile": "agents/analysts/fundamentals_analyst.py",
    "strategies/domain_bundles.py:get_market_technicals": "agents/analysts/market_analyst.py",
    "strategies/domain_bundles.py:get_portfolio_risk_envelope": "agents/risk_mgmt/aggressive_debator.py",
    "strategies/domain_bundles.py:get_sentiment_flow_feed": "agents/analysts/news_analyst.py",
    "strategies/factor_expressions.py:apply_winsorize": "agents/utils/analysis_tools.py:get_factor_profile",
    "strategies/factor_expressions.py:apply_zscore": "agents/utils/analysis_tools.py:get_factor_profile",
    "strategies/factor_expressions.py:fit_winsorize": "agents/utils/analysis_tools.py:get_factor_profile",
    "strategies/falsification.py:monitor_conditions": "strategies/monitor.py:notify",
    "strategies/falsification.py:record_breaches": "strategies/falsification.py:monitor_conditions",
    "strategies/mean_reversion.py:memory_profile": "agents/utils/analysis_tools.py:get_mean_reversion_quality",
    "strategies/monitor.py:notify": "strategies/falsification.py:monitor_conditions",
    "strategies/portfolio_optimizer.py:confidence_weights": "agents/utils/analysis_tools.py:get_risk_parity_alloc",
    "strategies/quant_baseline.py:baseline_rating": "strategies/prediction_ledger.py:log_decision",
    "strategies/quant_baseline.py:quant_signal": "strategies/prediction_ledger.py:log_decision",
    "strategies/reflection.py:build_reflection_context": "graph/trading_graph.py:prepare_initial_state (under enable_reflection)",
    "strategies/regime.py:market_stress_composite": "agents/utils/analysis_tools.py:get_regime_components",
    "strategies/regime.py:relative_vol_ratio": "agents/utils/analysis_tools.py:get_regime_components",
    "strategies/regime.py:upside_downside_beta": "agents/utils/analysis_tools.py:get_regime_components",
    "strategies/risk_sizing.py:risk_quantity": "agents/utils/analysis_tools.py:get_fixed_risk_size",
    "strategies/sector_screener.py:stock_screen": "agents/utils/analysis_tools.py:get_sector_rotation_screen",
    "strategies/sentiment.py:event_study": "",
    "strategies/sentiment.py:gini_coefficient": "",
    "strategies/sentiment.py:sentiment_dynamics": "agents/utils/analysis_tools.py:_sentiment_depth_rows",
    "strategies/signal_analysis.py:ic_decay_half_life": "agents/utils/analysis_tools.py:get_signal_quality",
    "strategies/signal_analysis.py:pred_autocorr": "agents/utils/analysis_tools.py:get_signal_quality",
    "strategies/technical_score.py:technical_disagreement": "agents/utils/analysis_tools.py:get_technical_score",
    "strategies/technical_score.py:technical_state": "agents/utils/analysis_tools.py:get_technical_score",
    "strategies/triadic_stress.py:triadic_stress": "agents/utils/analysis_tools.py:_risk_components",
    "dataflows/alpaca.py:get_calendar": "scripts/value_screener.py",
    "dataflows/pit_registry.py:markup_label": "",
    "dataflows/preopen.py:postfill_drift": "scripts/strategy_quality_report.py:build_report",
    "dataflows/stockdata.py:get_market_snapshot_stockdata": "agents/utils/market_position_tools.py:get_market_snapshot",
    "dataflows/yfinance_sector.py:fetch_eps_revisions": "scripts/value_screener.py:_fetch_revision_guarded",
}


def _declared(key: str) -> bool:
    """Is this ``module:fn`` key exempt by a declaration with a reason?"""
    return (key in LEGACY_WHITELIST or key in ADVISORY_CALCULATORS
            or key in GAP_CALCULATORS)


def _public_funcs(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")}


def _identifier_uses(path: Path) -> Counter:
    """Every identifier a file *uses*, as ``name -> count``.

    Three kinds of use are counted:

    * AST ``Name`` / ``Attribute`` - the ordinary call, attribute and bare-name
      forms (``evaluate.rolling_sharpe(...)``, ``iso(...)``).
    * import aliases - ``from ... import x`` / ``import x.y``.
    * **string constants** - this repo dispatches by name
      (``route_to_vendor("get_x")``, the string tool lists), so a name that only
      ever appears as a literal is still wired by this repo's own definition.
      Dropping strings would falsely flag the whole vendor layer.

    Two kinds are deliberately NOT counted: a **docstring** (prose *about* a
    function is not a use of it) and the strings of the **``__all__``
    assignment** (exporting a function is not using it - that escape is what let
    a ``def`` plus an ``__all__`` entry satisfy the old ``text.count(fn) > 1``
    rule). Matching is by whole identifier or whole literal, never a substring,
    so ``max_pain`` no longer matches ``max_pain_dist_atr``.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return Counter()

    docstrings: set[int] = set()
    exported: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    exported.add(id(sub))

    uses: Counter = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            uses[node.id] += 1
        elif isinstance(node, ast.Attribute):
            uses[node.attr] += 1
        elif isinstance(node, ast.alias):
            uses[node.name.split(".")[0]] += 1
            if node.asname:
                uses[node.asname] += 1
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and id(node) not in exported):
            uses[node.value] += 1
    return uses


_USES: dict[Path, Counter] = {}
for _dom in REFERENCE_DOMAINS:
    for _p in sorted(_dom.rglob("*.py")):
        _USES[_p] = _identifier_uses(_p)


def _outside_uses(fn: str, own: Path) -> int:
    """Times ``fn`` is used anywhere in the reference domains but its own file."""
    return sum(c.get(fn, 0) for p, c in _USES.items() if p != own)


# A strategy module with ZERO references anywhere in the production domains
# (agents / graph / reporting / dataflows-interface / scripts / entrypoints)
# is either a wiring gap or dead legacy - same contract as the per-fn check,
# but at the module level so a whole unwired module cannot hide behind its own
# internal self-references. Whitelisted definitions live in LEGACY_WHITELIST
# keyed by ANY of the module's public functions (the per-fn gate below still
# requires each specific fn to be wired or whitelisted).
_MODULE_CASES = []
for f in sorted(REPO.joinpath("tradingagents", "strategies").glob("*.py")):
    fns = _public_funcs(f)
    if fns and not any(_outside_uses(fn, f) > 0 for fn in fns):
        key = next(iter(sorted(fns)))
        _MODULE_CASES.append((f"{f.parent.name}/{f.name}", key))


_MODULE_DECLARED = {
    key.split(":", 1)[0]
    for key in (*LEGACY_WHITELIST, *ADVISORY_CALCULATORS, *GAP_CALCULATORS)
}


@pytest.mark.parametrize("case", _MODULE_CASES, ids=[c[0] for c in _MODULE_CASES])
def test_module_reachable_or_whitelisted(case):
    module, any_fn = case
    assert module in _MODULE_DECLARED, (
        f"strategy module {module} has zero references outside itself - it is "
        "either a wiring gap (the virtual agents cannot reach its calculations) "
        "or dead code. Wire it to an agent tool / graph / reporting / script, "
        "or declare one of its functions in LEGACY_WHITELIST / "
        "ADVISORY_CALCULATORS / GAP_CALCULATORS with a reason."
    )

CASES = []
for calc_dir in CALC_DIRS:
    for f in sorted(calc_dir.glob("*.py")):
        fns = sorted(_public_funcs(f))
        own = _USES.get(f, Counter())
        # Module-level reachability (any public fn referenced outside the
        # module itself) - the whole-module escape hatch.
        module_reachable = any(_outside_uses(fn, f) > 0 for fn in fns)
        for fn in fns:
            # Wired = used OUTSIDE its own module, OR an internal helper of a
            # module that is itself externally reachable. "Internal helper"
            # means the module's own *code* names it (a sibling call or a
            # string dispatch) - the `def` line and an `__all__` entry are not
            # uses, and a fn named only by a test is not wired either.
            outside = _outside_uses(fn, f)
            internal_use = own.get(fn, 0) > 0
            if outside > 0 or (module_reachable and internal_use):
                continue
            CASES.append((f"{calc_dir.name}/{f.name}:{fn}", f"{calc_dir.name}/{f.name}:{fn}"))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_public_calc_reachable_or_whitelisted(case):
    key, _ = case
    assert _declared(key), (
        f"calculation {key} has zero references outside its module (and is "
        "not an internal helper of a reachable module) - it is either a wiring "
        "gap (virtual agents cannot reach a computed read) or dead code. Wire "
        "it as an agent tool / pipeline hook, or declare it in "
        "LEGACY_WHITELIST / ADVISORY_CALCULATORS / GAP_CALCULATORS with a reason."
    )


def test_declared_calculators_are_real_and_still_orphaned():
    """A declaration must name a real public function that is still orphaned.

    Both halves matter: a typo would exempt nothing, and a stale entry would keep
    claiming "unwired" for a function that now reaches production. The lists may
    only shrink as declarations are wired or deleted.
    """
    stale = []
    for key in (*ADVISORY_CALCULATORS, *GAP_CALCULATORS):
        module, _, fn = key.partition(":")
        path = REPO / "tradingagents" / module
        fns = _public_funcs(path)
        assert fn in fns, f"{key} names no public function in {module}"
        own = _USES.get(path, Counter())
        module_reachable = any(_outside_uses(f, path) > 0 for f in fns)
        if _outside_uses(fn, path) > 0 or (module_reachable and own.get(fn, 0) > 0):
            stale.append(key)
    assert not stale, (
        "these declarations are STALE - the function now reaches production, so "
        f"remove the entries: {sorted(stale)}"
    )
    for klass in ADVISORY_CALCULATORS.values():
        assert klass in ADVISORY_CLASSES, f"unknown advisory class {klass!r}"


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
    import contextlib

    import tradingagents.dataflows.config as _cfgmod
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils import risk_tool_loop

    # The score-engine gates are toolset MEMBERSHIP switches: with a gate off
    # the tool is deliberately absent (a gate-off toolset is byte-identical),
    # and with it on the LLM can call it. This test asks "can an agent reach
    # this tool at all", so it reads the toolsets with every engine gate forced
    # on and restores the config afterwards.
    _engine_gates = (
        "enable_fundamental_score",
        "enable_technical_score",
        "enable_regime_score",
        "enable_risk_score",
        "enable_sentiment_score",
        "enable_news_score",
        "enable_event_state",
        "enable_trade_score",
    )
    _saved = dict(_cfgmod.get_config() or {})
    with contextlib.suppress(Exception):
        _cfgmod.set_config({**_saved, **dict.fromkeys(_engine_gates, True)})

    risk_tool_loop._build_lists()
    names: set[str] = set()
    try:
        for key in ("market", "news", "fundamentals", "sentiment"):
            names |= {t.name for t in analyst_toolset(key)}
    finally:
        with contextlib.suppress(Exception):
            _cfgmod.set_config(_saved)
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
    # ALL NINE ENGINE LEAVES. These are application-internal calculation
    # mechanisms, NOT LLM-facing analytical tools (ScoreContextContract.md
    # §13.3): the engines are computed by the application and their results are
    # SUPPLIED to every analyst prompt by `report_hygiene.scorecard_context_block`
    # (the full scorecard) and `report_hygiene.engine_score_block` (the owned
    # engine). A second discretionary route to a number the prompt already
    # carries is the ambiguity the contract removes, so no analyst binds one.
    #
    # `regime`, `risk` and `trade` were already report-level by decision
    # (`ENGINE_SECTIONS` gives them `None`); the other five were bound to their
    # owning analyst until 2026-09-19 and are dropped here. The readers
    # themselves stay - they are what the block calls.
    "get_fundamental_score": "engine leaf; consumer is report_hygiene.scorecard_context_block / engine_score_block, which SUPPLY the computed score to every analyst prompt (ScoreContextContract.md §13.3)",
    "get_technical_score": "engine leaf; consumer is report_hygiene.scorecard_context_block / engine_score_block, which SUPPLY the computed score to every analyst prompt (ScoreContextContract.md §13.3)",
    "get_momentum_score": "engine leaf (MOM-1; ENGINE_SECTIONS['momentum'] = 'market'); consumer is report_hygiene.scorecard_context_block / engine_score_block, which SUPPLY the computed score to every analyst prompt (ScoreContextContract.md §13.3)",
    "get_sentiment_score": "engine leaf; consumer is report_hygiene.scorecard_context_block / engine_score_block - the ONLY route into the sentiment report, whose analyst binds no tools (ScoreContextContract.md §13.3)",
    "get_news_score": "engine leaf; consumer is report_hygiene.scorecard_context_block / engine_score_block, which SUPPLY the computed score to every analyst prompt (ScoreContextContract.md §13.3)",
    "get_event_state": "engine leaf; consumer is report_hygiene.scorecard_context_block / engine_score_block, which SUPPLY the computed score to every analyst prompt (ScoreContextContract.md §13.3)",
    "get_regime_score": "report-level engine leaf (ENGINE_SECTIONS['regime'] is None); consumer is the supplied scorecard / run card / computed decision context, not an analyst tool loop (ScoreContextContract.md §13.3)",
    "get_risk_score": "report-level engine leaf (ENGINE_SECTIONS['risk'] is None); consumer is the supplied scorecard / run card / computed decision context, not an analyst tool loop (ScoreContextContract.md §13.3)",
    "get_trade_score": "report-level composite leaf (ENGINE_SECTIONS['trade'] is None); consumer is the supplied scorecard / run card / computed decision context, not an analyst tool loop (ScoreContextContract.md §13.3)",
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
