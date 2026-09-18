"""`TradeScore` (WP-11) — the four-engine composite and the gate boundary.

Covers the plan's acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §8, §9
Phase E, verbatim):

- `TradeScore` prints its weights, its status and its coverage, and reaches no
  gate, no size and no `opportunity_score`;
- the hard-gate test passes: a maximal composite changes nothing on a `BLOCK`;
- the promotion ladder is documented and enforced by a test that an unvalidated
  vector cannot be promoted by configuration.

Plus the cross-engine rules this module is built on: `NA != 0` (an absent engine
leaves the denominator, a count floor cannot exceed the engine set), the engine
set is not extended by adjacency (master rule 17), and the weights printed are
the weights used.

Offline and deterministic: every score is a literal, no vendor call, no clock.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tradingagents.strategies.trade_score import (
    COMPOSITE_MIN_COVERAGE,
    ENGINE_LETTERS,
    ENGINE_ORDER,
    ENGINE_WEIGHTS,
    GATE_NAME,
    PROMOTION_EVIDENCE,
    PROMOTION_LADDER,
    RESEARCH_ALLOCATION,
    STATUS_CONTRACT_MIGRATION,
    STATUS_PRODUCTION,
    STATUS_RESEARCH_ONLY,
    STATUS_VALIDATED,
    TRADE_BANDS,
    format_trade_score,
    promotion_state,
    trade_score,
)
from tradingagents.strategies.risk_multiplier import (
    HARD_NAMES,
    SOFT_CATALOG,
    RiskMultiplier,
    combine,
)

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "tradingagents" / "strategies" / "trade_score.py"

#: The plan's acceptance case (§8): high quality, strong setup, favourable
#: regime, high risk.
ACCEPTANCE_CASE = {"F": 92, "T": 85, "R": 78, "K": 35}

#: Every engine at its maximum — the composite the gate must ignore.
MAXIMAL = {name: 100.0 for name in ENGINE_ORDER}


def _references(path: Path) -> set[str]:
    """Imports, dotted attribute chains and plain names read out of a module.

    Prose is not a dependency (the module's own docstring says "sizing" and
    "opportunity_score" — that is a sentence, not a call), so only names are
    collected.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            refs.add(node.module or "")
            refs.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                refs.add(".".join(reversed(parts)))
    return refs


# --------------------------------------------------------------------------
# the weights: the printed vector is the vector used (acceptance (c))
# --------------------------------------------------------------------------


def test_the_owner_vector_is_the_default_and_is_printed() -> None:
    res = trade_score(ACCEPTANCE_CASE)
    assert res["weights"] == ENGINE_WEIGHTS
    assert res["weights_source"] == "owner"
    assert "F=0.4" in res["weights_basis"] and "K=0.2" in res["weights_basis"]
    assert "owner weights" in res["basis"]
    # printed == used, per engine
    for name, entry in res["components"].items():
        assert entry["weight"] == ENGINE_WEIGHTS[name], name


def test_a_supplied_vector_is_printed_and_used() -> None:
    weights = {"fundamental": 1.0, "technical": 1.0, "regime": 1.0, "risk": 1.0}
    res = trade_score(ACCEPTANCE_CASE, weights=weights)
    assert res["weights"] == weights
    assert res["weights_source"] == "supplied"
    assert "supplied weights" in res["basis"]
    assert res["score"] == pytest.approx(
        sum(weights[n] * res["components"][n]["value"] for n in ENGINE_ORDER) / 4.0,
        abs=0.005,
    )


def test_the_default_vector_is_never_an_equal_weight_fallback() -> None:
    """No fabricated coefficients: with no supplied vector the owner's is used.

    The kernel equal-weights only when it is handed no vector at all; this
    module always resolves one first, so `1/4` can never appear as a number the
    owner did not publish.
    """
    res = trade_score(MAXIMAL)
    assert res["weights"] == ENGINE_WEIGHTS
    assert len(set(res["weights"].values())) > 1  # not 1/4 everywhere
    assert "equal weights" not in res["basis"]


def test_the_printed_weights_equals_the_weight_table_used() -> None:
    """Master rule 6: mutation — a weight change must move the printed vector."""
    res = trade_score(MAXIMAL)
    res2 = trade_score(MAXIMAL, weights={"fundamental": 0.9, "technical": 0.1})
    assert res2["weights"] != res["weights"]
    assert res2["weights"]["fundamental"] == 0.9
    # an engine with no supplied weight is dropped by the kernel, with a reason
    assert res2["components"]["regime"]["weight"] == 0.0
    assert "dropped (no weight)" in res2["basis"] or "regime" in res2["present"]


# --------------------------------------------------------------------------
# the engine set: no entry by adjacency (master rule 17)
# --------------------------------------------------------------------------


def test_a_fifth_engine_is_excluded_and_named_never_weighted() -> None:
    """News and Sentiment participate in the *research allocation*, not here."""
    base = trade_score(ACCEPTANCE_CASE)
    extended = trade_score({**ACCEPTANCE_CASE, "news": 99.0, "sentiment": 99.0})
    assert extended["score"] == base["score"]
    assert extended["coverage"] == base["coverage"]
    assert set(extended["excluded"]) == {"news", "sentiment"}
    assert "not a TradeScore engine" in extended["excluded"]["news"]
    assert "excluded" in extended["basis"]


def test_the_research_allocation_is_a_different_object() -> None:
    assert set(RESEARCH_ALLOCATION) - set(ENGINE_ORDER) == {"news", "sentiment"}
    assert set(ENGINE_WEIGHTS) == set(ENGINE_ORDER)
    assert not set(ENGINE_WEIGHTS) & (set(RESEARCH_ALLOCATION) - set(ENGINE_ORDER))
    # and the allocation is not silently read as this composite's vector
    assert trade_score(MAXIMAL)["weights"] == ENGINE_WEIGHTS
    assert sum(RESEARCH_ALLOCATION.values()) == pytest.approx(1.0)
    assert ENGINE_WEIGHTS["fundamental"] == pytest.approx(0.40)
    assert RESEARCH_ALLOCATION["fundamental"] == pytest.approx(0.35)


def test_every_engine_is_one_of_the_four_with_its_own_letter() -> None:
    assert set(ENGINE_LETTERS) == set(ENGINE_ORDER)
    assert sorted(ENGINE_LETTERS.values()) == ["F", "K", "R", "T"]
    assert sum(ENGINE_WEIGHTS.values()) == pytest.approx(1.0)


def test_the_plan_notation_resolves_to_the_same_engines() -> None:
    assert trade_score(ACCEPTANCE_CASE) == trade_score(
        {"fundamental": 92, "technical": 85, "regime": 78, "risk": 35}
    )


def test_two_spellings_of_one_engine_is_an_error() -> None:
    """One number, one producer (master rule 3) - never a silent overwrite."""
    with pytest.raises(ValueError):
        trade_score({"F": 92, "fundamental": 80})


def test_a_non_mapping_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        trade_score([("fundamental", 90)])


# --------------------------------------------------------------------------
# NA is not 0 (master rule 1)
# --------------------------------------------------------------------------


def test_an_absent_engine_leaves_the_denominator() -> None:
    full = ENGINE_WEIGHTS
    res = trade_score({"fundamental": 90, "technical": 80, "regime": 70})
    num = full["fundamental"] * 90 + full["technical"] * 80 + full["regime"] * 70
    den = full["fundamental"] + full["technical"] + full["regime"]
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den, abs=1e-9)
    assert res["absent"] == ["risk"]
    assert res["components"]["risk"]["value"] is None
    assert res["components"]["risk"]["state"] == "NA"


def test_a_missing_engine_does_not_punish_the_name() -> None:
    """`NA != 0`: the score is the renormalised mean of the engines measured.

    Scored as a zero the absent engine would have pulled the composite down to
    66.5; renormalised, the score stays inside the range of the present three.
    """
    res = trade_score({"fundamental": 90, "technical": 80, "regime": 70})
    assert res["score"] == pytest.approx(83.125, abs=0.005)
    assert 70.0 <= res["score"] <= 90.0
    assert res["score"] > 66.5
    assert res["score"] == pytest.approx(
        (0.40 * 90 + 0.25 * 80 + 0.15 * 70) / 0.80, abs=0.005
    )


def test_no_engine_at_all_withholds_never_zero_never_fifty() -> None:
    for empty in ({}, {name: None for name in ENGINE_ORDER}):
        res = trade_score(empty)
        assert res["score"] is None
        assert res["score"] not in (0, 50)
        assert res["coverage"] == 0.0
        assert "0 of 4 components present" in res["withheld"]
        assert "WITHHELD" in res["basis"]


def test_an_out_of_scale_value_is_left_out_never_clamped() -> None:
    """A producer's 150 is a bug to surface, not a 100 to score."""
    res = trade_score({"fundamental": 150, "technical": 80})
    assert res["components"]["fundamental"]["value"] is None
    assert res["components"]["fundamental"]["raw"] == 150
    assert "outside" in res["invalid"]["fundamental"]
    assert res["score"] is None  # 1 of 4 present, floor is 2
    assert "unusable" in res["basis"]


def test_a_boolean_is_not_a_score() -> None:
    res = trade_score({"fundamental": True, "technical": 80})
    assert res["components"]["fundamental"]["value"] is None
    assert res["components"]["fundamental"]["state"] == "NA"


def test_the_floor_is_a_count_capped_at_the_engine_set() -> None:
    from tradingagents.strategies.score_engine import coverage_floor

    assert COMPOSITE_MIN_COVERAGE == 2
    assert COMPOSITE_MIN_COVERAGE <= len(ENGINE_ORDER)
    assert coverage_floor(COMPOSITE_MIN_COVERAGE, len(ENGINE_ORDER)) == COMPOSITE_MIN_COVERAGE
    # one engine is not a composite: the design's whole point is four numbers
    res = trade_score({"fundamental": 90})
    assert res["score"] is None and "floor is 2" in res["withheld"]
    # ...and three of four is
    assert trade_score({"fundamental": 90, "technical": 80, "regime": 70})["score"] is not None


# --------------------------------------------------------------------------
# the attribution recomputes the printed score
# --------------------------------------------------------------------------


def test_a_reader_recomputing_the_weighted_mean_gets_the_printed_score() -> None:
    res = trade_score(ACCEPTANCE_CASE)
    num = den = 0.0
    for name in ENGINE_ORDER:
        entry = res["components"][name]
        if entry["value"] is None:
            continue
        num += entry["weight"] * entry["value"]
        den += entry["weight"]
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / sum(ENGINE_WEIGHTS.values()), abs=1e-9)


def test_an_invalid_engine_is_excluded_from_the_recompute() -> None:
    res = trade_score({"fundamental": 90, "technical": 80, "regime": 70, "risk": -5})
    assert res["score"] is not None
    assert res["coverage"] == pytest.approx(0.80, abs=1e-9)
    assert res["invalid"]["risk"].startswith("outside")


# --------------------------------------------------------------------------
# the printed block (acceptance: weights, status, coverage)
# --------------------------------------------------------------------------


def test_the_printed_block_carries_weights_status_and_coverage() -> None:
    text = format_trade_score(trade_score(ACCEPTANCE_CASE), ticker="MSFT")
    assert "TradeScore - MSFT" in text
    assert STATUS_RESEARCH_ONLY in text
    assert "coverage 100%" in text
    for name in ENGINE_ORDER:
        assert f"- {name} ({ENGINE_LETTERS[name]}, weight {ENGINE_WEIGHTS[name]:g})" in text
    assert "76.75" in text
    assert "never a gate, never a size, never an opportunity_score" in text


def test_the_printed_rows_recompute_the_printed_number() -> None:
    res = trade_score(ACCEPTANCE_CASE)
    text = format_trade_score(res)
    assert "- fundamental (F, weight 0.4): 92.0/100" in text
    assert "- risk (K, weight 0.2): 35.0/100" in text
    assert res["score"] == 76.75


def test_the_printed_block_says_when_a_score_is_withheld() -> None:
    text = format_trade_score(trade_score({"fundamental": 90}))
    assert "composite: unavailable" in text
    assert "floor is 2" in text


def test_the_printed_block_names_the_excluded_engines() -> None:
    text = format_trade_score(trade_score({**ACCEPTANCE_CASE, "news": 99.0}))
    assert "excluded by name" in text and "news" in text


# --------------------------------------------------------------------------
# the promotion ladder (acceptance (d), owner Q2)
# --------------------------------------------------------------------------


def test_the_ladder_is_the_owner_ladder_in_order() -> None:
    assert PROMOTION_LADDER == (
        "RESEARCH_ONLY",
        "VALIDATED",
        "CONTRACT_MIGRATION",
        "PRODUCTION",
    )
    assert set(PROMOTION_EVIDENCE) == set(PROMOTION_LADDER)
    # ADVISORY is the status of a deterministic diagnostic, not a rung of a
    # combination's ladder
    assert "ADVISORY" not in PROMOTION_LADDER
    for rung in PROMOTION_LADDER[1:]:
        assert PROMOTION_EVIDENCE[rung].strip()


def test_an_unvalidated_vector_is_research_only() -> None:
    res = trade_score(ACCEPTANCE_CASE)
    assert res["status"] == STATUS_RESEARCH_ONLY
    assert res["ladder"]["evidence_present"] == []
    assert res["ladder"]["missing"] == [
        STATUS_VALIDATED,
        STATUS_CONTRACT_MIGRATION,
        STATUS_PRODUCTION,
    ]
    assert "unvalidated until Phase C" in res["basis"]


def test_a_status_request_without_evidence_is_refused_and_printed() -> None:
    res = trade_score(ACCEPTANCE_CASE, status=STATUS_PRODUCTION)
    assert res["status"] == STATUS_RESEARCH_ONLY
    assert res["score"] == 76.75  # the number prints; only the claim is refused
    assert "refused" in res["ladder"]["refused"]
    assert "REFUSED" in res["basis"]
    assert "configuration is not evidence" in res["basis"]


def test_a_status_request_at_the_evidenced_rung_is_honoured() -> None:
    res = trade_score(
        ACCEPTANCE_CASE,
        status=STATUS_VALIDATED,
        evidence={STATUS_VALIDATED: {"vector_id": "wp10-2026-09", "rank_ic": 0.031}},
    )
    assert res["status"] == STATUS_VALIDATED
    assert res["ladder"]["refused"] is None


def test_a_boolean_claim_is_not_evidence() -> None:
    state = promotion_state(evidence={STATUS_VALIDATED: True}, requested=STATUS_VALIDATED)
    assert state["status"] == STATUS_RESEARCH_ONLY
    assert state["rejected"] == [STATUS_VALIDATED]
    assert "record is required, not a flag" in trade_score(
        ACCEPTANCE_CASE, evidence={STATUS_VALIDATED: True}
    )["basis"]


def test_the_ladder_is_contiguous_from_the_bottom() -> None:
    """Production's own record cannot skip the measured rung below it."""
    state = promotion_state(
        evidence={STATUS_PRODUCTION: {"dated": "2026-09-17", "version": "v1"}},
        requested=STATUS_PRODUCTION,
    )
    assert state["status"] == STATUS_RESEARCH_ONLY
    assert state["missing"] == [
        STATUS_VALIDATED,
        STATUS_CONTRACT_MIGRATION,
        STATUS_PRODUCTION,
    ]


def test_contiguous_evidence_reaches_each_rung() -> None:
    records = {
        STATUS_VALIDATED: {"vector_id": "wp10-2026-09", "rank_ic": 0.031},
        STATUS_CONTRACT_MIGRATION: {"consumer": "signal.v2", "schema_version": "2.0.0"},
        STATUS_PRODUCTION: {"decision": "owner", "dated": "2026-09-18"},
    }
    assert promotion_state(evidence=records)["status"] == STATUS_PRODUCTION
    assert trade_score(ACCEPTANCE_CASE, evidence=records)["status"] == STATUS_PRODUCTION
    assert promotion_state(
        evidence={k: records[k] for k in (STATUS_VALIDATED, STATUS_CONTRACT_MIGRATION)}
    )["status"] == STATUS_CONTRACT_MIGRATION
    assert trade_score(
        ACCEPTANCE_CASE, evidence={STATUS_VALIDATED: records[STATUS_VALIDATED]}
    )["status"] == STATUS_VALIDATED


def test_an_unknown_status_is_a_closed_vocabulary_error() -> None:
    with pytest.raises(ValueError):
        trade_score(ACCEPTANCE_CASE, status="CERTIFIED")


def test_configuration_alone_cannot_promote_a_vector(monkeypatch) -> None:
    """Acceptance (d): `enable_trade_score` is a switch on the surface, not a rung."""
    import tradingagents.dataflows.config as cfgmod

    monkeypatch.setattr(cfgmod, "get_config", lambda: {GATE_NAME: True})
    assert trade_score(ACCEPTANCE_CASE, status=STATUS_PRODUCTION)["status"] == (
        STATUS_RESEARCH_ONLY
    )
    # the only promoter is a recorded measurement handed to `evidence`
    assert trade_score(
        ACCEPTANCE_CASE, evidence={STATUS_VALIDATED: {"vector_id": "x"}}
    )["status"] == STATUS_VALIDATED


def test_the_module_reads_no_configuration_at_all() -> None:
    """A gate that can promote is a strategy switch wearing a status's name."""
    refs = _references(MODULE_PATH)
    for forbidden in ("get_config", "default_config", "cfgmod", "_r3_flag", "os.environ"):
        assert not any(forbidden in ref for ref in refs), (forbidden, refs)


# --------------------------------------------------------------------------
# the gate boundary - acceptance (a): a maximal composite changes nothing
# --------------------------------------------------------------------------


def test_a_maximal_composite_changes_nothing_on_a_block() -> None:
    """The plan's §8 acceptance (a).

    The hard gate is the two-tier policy the repo already runs
    (`risk_multiplier.combine` zeroes the soft product when a hard flag is
    live). The composite is 100.0 - every engine maximal - and the verdict is
    byte-identical to the verdict with no composite in existence, because the
    composite is not an input to it.
    """
    blocked = combine(RiskMultiplier(hard=("max_portfolio_risk",)))
    assert blocked == {
        "factor": 0.0,
        "blocked": True,
        "soft_reasons": [],
        "hard_reasons": ["max_portfolio_risk"],
    }
    res = trade_score(MAXIMAL)
    assert res["score"] == 100.0 and res["coverage"] == 1.0
    assert combine(RiskMultiplier(hard=("max_portfolio_risk",))) == blocked


def test_the_acceptance_case_reads_no_new_risk() -> None:
    """`F 92 / T 85 / R 78 / K 35` -> high composite, gate BLOCK -> no new risk."""
    res = trade_score(ACCEPTANCE_CASE)
    assert res["score"] == 76.75
    gate = combine(RiskMultiplier(hard=("max_portfolio_risk",)))
    assert gate["blocked"] is True and gate["factor"] == 0.0
    # a high composite does not lift a hard block, and a soft reduction is not
    # a promotion either
    assert combine(RiskMultiplier(soft={"knife": 0.5}, hard=("halt",)))["factor"] == 0.0


def test_the_composite_is_not_a_risk_multiplier_input() -> None:
    assert "trade_score" not in SOFT_CATALOG
    assert "trade_score" not in HARD_NAMES
    assert set(RiskMultiplier.__dataclass_fields__) == {"soft", "hard"}
    # the multiplier's inputs are named guards, not scores
    assert not any("score" in name for name in SOFT_CATALOG + tuple(HARD_NAMES))


def test_the_sizing_contract_takes_no_score() -> None:
    path = REPO / "tradingagents" / "strategies" / "contract.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "build_position_contract"
    )
    params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    assert not any("score" in p for p in params), params
    assert "trade_score" not in path.read_text(encoding="utf-8")


def test_the_gate_order_has_no_score_and_no_event_check() -> None:
    """`GATE_PRECEDENCE` is the gate order; the governor never reads a score."""
    path = REPO.parent / "TradingExecution" / "signald" / "contracts.py"
    if not path.exists():
        pytest.skip("execution repo not present; the gate order cannot be read")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    checks = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == (
            "GATE_PRECEDENCE"
        ):
            checks = [e.value for e in node.value.elts]
    assert checks == [
        "mandate", "sleeve_capital", "house_drawdown", "house_cvar",
        "correlation_stress", "vol_regime", "market_regime", "knife_guard",
        "concentration", "liquidity", "cost", "wash", "shortability", "data",
        "time", "halt", "approval",
    ]
    assert len(checks) == 17
    assert not any("score" in check for check in checks)
    assert "event" not in checks
    source = path.read_text(encoding="utf-8").lower()
    assert "trade_score" not in source


def test_the_composite_never_reaches_the_opportunity_score_slot() -> None:
    from tradingagents.execution_contract import opportunity_score

    assert opportunity_score() is None
    slot = (REPO / "tradingagents" / "execution_contract.py").read_text(encoding="utf-8")
    assert "trade_score" not in slot and "TradeScore" not in slot
    # and the composite's own result carries no such key
    assert "opportunity_score" not in trade_score(MAXIMAL)


def test_the_module_never_touches_the_gate_sizing_or_rating_path() -> None:
    """No import and no attribute access on the gate / sizing / rating path."""
    refs = _references(MODULE_PATH)
    for forbidden in (
        "sizing",
        "risk_sizing",
        "risk_multiplier",
        "knife_guard",
        "position_size",
        "position_contract",
        "build_position_contract",
        "decision_guardrail",
        "SCORE_BANDS",
        "execution_contract",
        "opportunity_score",
        "GATE_PRECEDENCE",
    ):
        assert not any(forbidden in ref for ref in refs), (forbidden, refs)


def test_the_composite_carries_no_band_table_and_no_label() -> None:
    """A composite label would be a rating (master rule 2), so there is none."""
    assert TRADE_BANDS == ()
    res = trade_score(MAXIMAL)
    assert res["band"] is None
    assert "no band table" in res["basis"]
    assert "decision_guardrail" not in _references(MODULE_PATH)
    assert "no band table" in format_trade_score(res)


def test_the_module_names_its_gate_and_the_leaf_is_where_it_is_read() -> None:
    """The gate is a switch on the surface; naming it here keeps it from drifting."""
    assert GATE_NAME == "enable_trade_score"
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert GATE_NAME not in called


# --------------------------------------------------------------------------
# the wiring (added by the integration owner after the shared files landed)
# --------------------------------------------------------------------------


def test_gate_off_keeps_the_composite_tool_out_of_every_toolset(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents import toolsets

    monkeypatch.setattr(cfgmod, "get_config", lambda: {})
    names_off = [t.name for t in toolsets.fundamentals_company_tools()]
    assert "get_trade_score" not in names_off
    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_trade_score": True})
    names_on = [t.name for t in toolsets.fundamentals_company_tools()]
    assert set(names_on) - set(names_off) == {"get_trade_score"}


def test_gate_off_writes_no_card_key() -> None:
    from tradingagents.reporting import _run_card_trade_score

    assert _run_card_trade_score({"fundamental_score": {"score": 80.0}}, {}) is None


def test_the_card_composite_reads_the_engine_blocks(monkeypatch) -> None:
    from tradingagents.reporting import _run_card_trade_score

    card = {
        "fundamental_score": {"score": 92.0},
        "technical_score": {"score": 85.0},
        "regime_score": {"score": 78.0},
        "risk_score": {"score": 35.0},
    }
    block = _run_card_trade_score(card, {"enable_trade_score": True})
    assert block["score"] == 76.75
    assert block["status"] == "RESEARCH_ONLY"
    assert block["coverage"] == 1.0
    assert block["engines"] == {
        "fundamental": 92.0, "technical": 85.0, "regime": 78.0, "risk": 35.0
    }


def test_the_card_composite_is_withheld_without_two_engines() -> None:
    from tradingagents.reporting import _run_card_trade_score

    block = _run_card_trade_score(
        {"fundamental_score": {"score": 92.0}}, {"enable_trade_score": True}
    )
    assert block["score"] is None
    assert block["absent"] and "technical" in block["absent"]
    assert block["withheld"]


def test_the_leaf_says_the_gate_is_off(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents.utils.analysis_tools import get_trade_score

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_trade_score": False})
    out = get_trade_score.invoke({"ticker": "MSFT"})
    assert "gated off" in out and "enable_trade_score" in out


def test_the_engine_assembly_never_substitutes_a_number(monkeypatch) -> None:
    """An engine that cannot measure stays None; nothing is invented for it.

    Every engine is pinned to a failure, so the test is offline and asserts the
    contract rather than the environment: no leg may be filled with a number.
    """
    import tradingagents.agents.utils.analysis_tools as at
    import tradingagents.strategies.fundamental_score as fs
    import tradingagents.strategies.regime_score as rs
    import tradingagents.strategies.technical_score as ts

    def _boom(*a, **kw):
        raise RuntimeError("nothing to measure")

    monkeypatch.setattr(at, "_technical_components", _boom)
    monkeypatch.setattr(at, "_regime_components", _boom)
    monkeypatch.setattr(at, "_risk_components", _boom)
    monkeypatch.setattr(fs, "fundamental_score_for_ticker", _boom)
    scores = at._trade_score_engines("NOPE")
    assert scores == {"fundamental": None, "technical": None, "regime": None, "risk": None}


#: A risk component set the real engine can score: two ramps in `volatility`,
#: the two positive-magnitude tail producers, and the pinned drawdown pair - three
#: categories, which clears `RiskScore`'s own floor of three. The semivariance
#: triple is deliberately absent (supplying any of it requires all of it).
_RISK_COMPONENTS: dict = {
    "realized_vol": 0.25,
    "implied_move_pct": 0.04,
    "stress_loss": 0.03,
    "es_pct": 0.03,
    "measured_book_drawdown": 0.05,
    "cdar": 0.04,
}


def test_the_engine_assembly_reads_the_risk_engine(monkeypatch) -> None:
    """`risk` is read through `RiskScore`'s own entry point, like the other three.

    The defect this pins: the assembler returned ``risk: None`` unconditionally,
    behind a stale "until WP-5 lands" comment, so the leaf's composite never
    applied the owner's ``K=0.20`` and its coverage was capped at 80%. Only the
    I/O seam is patched here; the engine that scores the components is the real
    one, so the number is `RiskScore`'s and not this test's.
    """
    import tradingagents.agents.utils.analysis_tools as at

    monkeypatch.setattr(at, "_risk_components", lambda ticker: dict(_RISK_COMPONENTS))
    scores = at._trade_score_engines("TEST")
    assert scores["risk"] == 74.0

    # ...and the composite then treats it as one of its four engines, not as a
    # gap: `K` is present and carries its published weight.
    res = trade_score(scores)
    assert "risk" in res["present"]
    assert res["components"]["risk"]["weight"] == ENGINE_WEIGHTS["risk"]
