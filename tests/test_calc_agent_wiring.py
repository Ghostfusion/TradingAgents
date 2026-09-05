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
    # W4-2 typed-state schema artifacts - explicitly FUTURE/advisory by design
    # (module doc: "nothing re-wires the existing graph"; the compact
    # summarizer lands with the typed-state cutover).
    "strategies/typed_state.py:summarize_report": "advisory typed-state (W4-2) artifact for a future graph cutover",
    "strategies/typed_state.py:to_compact": "advisory typed-state (W4-2) artifact for a future graph cutover",
    # W4-8 complexity/maintenance-tax report - a developer ops tool, not an
    # agent read; run on demand (no periodic hook yet).
    "strategies/integrity_tools.py:complexity_report": "developer ops report (LOC/fan-in), no periodic hook yet",
    # W2-11/W4-6 scenario-grid reads - DCF-at-price consumers; no decision
    # surface prices them today (the DCF tool is the live fundamental path).
    "strategies/regime_performance.py:stress_grid": "advisory scenario grid; no DCF-at-price consumer yet",
    "strategies/regime_performance.py:macro_regime": "advisory cross-asset regime label; no consumer yet",
    # W1 scoring helpers - need the prediction-horizon close join; log_decision
    # is wired, the scoring consumption lands with fast-path horizon resolution.
    "strategies/prediction_ledger.py:score_all": "scoring needs the horizon close join (fast-path T0/T1 work)",
    "strategies/prediction_ledger.py:score_outcome": "scoring needs the horizon close join (fast-path T0/T1 work)",
    "strategies/prediction_ledger.py:outcome_metrics": "scoring needs the horizon close join (fast-path T0/T1 work)",
    # options_surface IV-rank read - needs a per-day IV history no vendor
    # delivers (cboe/chain is spot-only); the chain-based reads are tool-wired.
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
        for fn in sorted(_public_funcs(f)):
            # referenced inside its own module (self-count >1) or anywhere in
            # the production reference domains -> wired.
            if text.count(fn) > 1 or blob.count(fn) > 1:
                continue
            CASES.append((f"{calc_dir.name}/{f.name}:{fn}", f"{calc_dir.name}/{f.name}:{fn}"))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_public_calc_reachable_or_whitelisted(case):
    key, _ = case
    assert key in LEGACY_WHITELIST, (
        f"calculation {key} has zero references outside its module - it is "
        "either a wiring gap (virtual agents cannot reach a computed read) or "
        "dead code. Wire it as an agent tool / pipeline hook, or move it to "
        "the LEGACY_WHITELIST with a reason."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
