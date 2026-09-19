"""`EventScore` (WP-8) - one test per acceptance clause of the plan's §5.7 / §9 Phase B.

The clauses, in the plan's own words:

(a) *The imminence scalars are monotone and bounded* - a day further out never
    scores higher, and the value is always in [0, 1], `None` for an absent
    day-count (never 0).
(b) *The hard block is untouched and still fires only on earnings* - a macro-only
    window must not block, and the event score never writes it.
(c) *The event keys are disjoint from `RiskScore`'s.*
(d) *No data returns `None` with the reason, never a neutral.*
(e) No event path reaches `GATE_PRECEDENCE` through a score (doc §6.4), the
    engine's bands are its own (master rule 2), and the score never sizes
    (doc §5.4).

Synthetic and offline: every input is a literal or comes from a producer run on
literal rows, so the file makes no vendor call and is deterministic.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from tradingagents.strategies.catalyst import build_catalyst_snapshot
from tradingagents.strategies.event_state import (
    ABSENT,
    ABSENT_REASONS,
    CALENDAR_INTERFACES,
    COMPONENTS,
    EVENT_BANDS,
    EVENT_MIN_COVERAGE,
    FAMILY_AVAILABILITY,
    FAMILY_ORDER,
    FAMILY_SCOPE,
    FLAG_COMPONENTS,
    HARD_BLOCK_KEY,
    HORIZONS,
    IMMINENCE_COMPONENTS,
    NA_REASONS,
    SCORABLE,
    STATUS_RESEARCH_ONLY,
    event_components,
    event_state,
    forward_calendar,
    imminence,
)

MODULE_PATH = Path("tradingagents/strategies/event_state.py")


def _full_components() -> dict:
    """One measured slot per producible family, plus every window flag."""
    return {
        "earnings_imminence": 12,
        "earnings_in_window": True,
        "macro_imminence": 2,
        "macro_count_high": 1,
        "catalyst_unassessed": False,
        "fed_imminence": 6,
        "fed_modal_prob": 87.5,
        "opex_imminence": 3,
        "opex_in_week": True,
        "opex_post_unwind": False,
    }


def _snapshot(data: dict, trade_date: str = "2026-09-18", cfg: dict | None = None) -> dict:
    return build_catalyst_snapshot(data, trade_date, cfg or {"catalyst_hard_block_days": 5})


# --------------------------------------------------------------------------
# (a) the imminence scalars are monotone and bounded
# --------------------------------------------------------------------------


def test_the_imminence_scalar_is_monotone_and_bounded() -> None:
    for family, horizon in HORIZONS.items():
        values = [imminence(d, horizon) for d in range(-5, int(2 * horizon) + 1)]
        assert all(v is not None and 0.0 <= v <= 1.0 for v in values), family
        assert all(b <= a for a, b in zip(values, values[1:])), family  # non-increasing
        assert imminence(0, horizon) == 1.0, family
        assert imminence(horizon, horizon) == 0.0, family
        assert imminence(horizon + 1, horizon) == 0.0, family
        assert imminence(-3, horizon) == 1.0, family  # an event that passed is on top of us
    # half the horizon -> exactly 1/2, whatever the family (one function, one rule)
    for horizon in HORIZONS.values():
        assert imminence(horizon / 2.0, horizon) == 0.5


def test_deleting_the_clamp_or_flipping_the_sign_would_fail_this() -> None:
    """The two mutations the scalar is worth a test for."""
    # 1 - days/horizon cannot leave [0, 1]: unclamped, 3*horizon -> -2.
    assert imminence(3 * 60, 60.0) == 0.0
    # A monotone DECREASE, not an increase: this is the assertion a sign flip breaks.
    assert imminence(1, 60.0) > imminence(2, 60.0) > imminence(50, 60.0)


def test_imminence_is_none_for_an_absent_day_count_never_zero() -> None:
    assert imminence(None, 30.0) is None
    assert imminence(True, 30.0) is None  # a boolean is not a day-count
    assert imminence("not-a-date", 30.0) is None
    assert imminence(float("nan"), 30.0) is None
    assert imminence(float("inf"), 30.0) is None
    for bad_horizon in (None, 0, -7, "x"):
        assert imminence(3, bad_horizon) is None


def test_the_same_imminence_function_serves_every_family() -> None:
    """Four producers, three declared interfaces, one implementation."""
    quarters = {
        name: HORIZONS[COMPONENTS[name].family] / 4.0 for name in IMMINENCE_COMPONENTS
    }
    assert {imminence(days, HORIZONS[COMPONENTS[name].family]) for name, days in quarters.items()} == {0.75}
    res = event_state(quarters)
    for family in FAMILY_ORDER:
        assert res["families"][family]["imminence"] == pytest.approx(0.75)
        assert res["families"][family]["score"] == pytest.approx(75.0)
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert source.count("def imminence(") == 1


# --------------------------------------------------------------------------
# (d) no data returns None with the reason, never a neutral
# --------------------------------------------------------------------------


def test_no_data_returns_none_with_the_reason_never_a_neutral() -> None:
    res = event_state({})
    assert res["score"] is None and res["band"] is None
    assert res["coverage"] == 0.0
    assert "floor" in res["withheld"]
    assert res["hard_block"] is None
    for family in FAMILY_ORDER:
        state = res["families"][family]
        assert state["imminence"] is None and state["score"] is None
        assert not isinstance(state["score"], (int, float))  # never 0, never 50
        assert state["reason"], family
    assert res["families_present"] == []
    assert set(res["families_unmeasured"]) == set(FAMILY_ORDER)


def test_a_missing_family_lowers_coverage_by_its_own_family_and_the_state_renders() -> None:
    full = event_state(_full_components())
    assert full["score"] is not None
    assert full["coverage"] == pytest.approx(4 / 7, abs=1e-4)
    assert full["families_present"] == ["earnings", "macro", "fed", "opex"]

    without_opex = dict(_full_components())
    without_opex.pop("opex_imminence")
    partial = event_state(without_opex)
    assert partial["coverage"] == pytest.approx(3 / 7, abs=1e-4)
    assert partial["score"] is not None
    assert "opex" in partial["families_unmeasured"]
    assert "opex" in partial["families"][  # the reason travels with the family
        "opex"]["reason"]
    # The absent family leaves the numerator AND stays in the denominator.
    assert partial["families"]["opex"]["score"] is None
    assert partial["score"] != full["score"]


def test_the_score_moves_toward_the_present_families_not_toward_zero() -> None:
    vals = _full_components()
    high = event_state(vals)["score"]
    # Drop the two least imminent families: the present mean must RISE.
    trimmed = dict(vals)
    trimmed.pop("macro_imminence")  # 2/3 -> 33.3
    trimmed.pop("fed_imminence")  # 6/10 -> 40.0
    assert event_state(trimmed)["score"] > high


def test_a_count_floor_is_capped_at_the_component_sets_own_size() -> None:
    from tradingagents.strategies.event_state import _family_floor

    assert _family_floor() == EVENT_MIN_COVERAGE
    assert _family_floor(999) == len(FAMILY_ORDER)  # never larger than the family set
    # One family alone is below the floor: withheld WITH the reason, never scored.
    one = event_state({"opex_imminence": 1})
    assert one["score"] is None and "floor" in one["withheld"]
    # ...and four families clear it.
    assert event_state(_full_components())["score"] is not None


def test_the_printed_family_scores_recompute_the_printed_composite() -> None:
    res = event_state(_full_components())
    num = den = 0.0
    for family in res["families_present"]:
        num += 1.0 * res["families"][family]["score"]
        den += 1.0
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / len(FAMILY_ORDER), abs=1e-4)


def test_a_supplied_weight_vector_is_printed_and_used() -> None:
    w = {family: 1.0 for family in FAMILY_ORDER}
    w["earnings"] = 3.0
    res = event_state(_full_components(), weights=w)
    assert res["weights"] == w
    assert "earnings=3" in res["basis"]
    num = sum(w[f] * res["families"][f]["score"] for f in res["families_present"])
    den = sum(w[f] for f in res["families_present"])
    assert res["score"] == pytest.approx(num / den, abs=0.005)


def test_no_published_weight_vector_means_equal_weights_and_the_basis_says_so() -> None:
    res = event_state(_full_components())
    assert res["weights"] is None
    assert "no weight vector is published" in res["basis"]
    assert "equal weights" in res["basis"]
    assert res["coverage"] == pytest.approx(4 / 7, abs=1e-4)  # equal weight, 7 families


def test_the_engine_status_is_research_only_for_the_unvalidated_combination() -> None:
    res = event_state(_full_components())
    assert res["status"] == STATUS_RESEARCH_ONLY
    assert res["status"] == "RESEARCH_ONLY"
    assert "RESEARCH_ONLY" not in {s for s in (res["band"],)}
    # The scale direction is printed, not implied: 100 = an event on top of us.
    assert "INVERTED" in res["basis"]


# --------------------------------------------------------------------------
# (b) the hard block is untouched and still fires only on earnings
# --------------------------------------------------------------------------

FED_ROWS = [{"meeting_date": "2026-09-20", "probability": 88.0, "target_range": "3.75-4.00%"}]
MACRO_ROWS = [{"star": "HIGH", "timestamp": "2026-09-18", "event": "CPI"}]
OPEX = {
    "next_opex": "2026-09-20",
    "prev_opex": "2026-08-21",
    "days_to_next": 2,
    "in_opex_week": True,
    "post_opex_unwind": False,
}


def test_a_macro_only_window_does_not_block_and_macro_fed_opex_cannot_set_it() -> None:
    snap = _snapshot({"economic_calendar": MACRO_ROWS, "fed_watch": FED_ROWS})
    assert snap["verdict"] in ("earnings-window", "macro-catalyst", "fed-catalyst", "no-imminent-catalyst")
    assert snap["verdict"] != "earnings-hard-block"
    assert snap["hard_block"] is None
    comps = event_components(snap, opex=OPEX)
    assert comps[HARD_BLOCK_KEY] is None
    assert comps["macro_imminence"] == 0 and comps["fed_imminence"] == 2
    res = event_state(comps)
    assert res["hard_block"] is None
    # ...and a 0-day macro event still cannot create one.
    assert res["families"]["macro"]["imminence"] == 1.0


def test_the_hard_block_still_fires_on_earnings_only() -> None:
    earnings = [{"date": "2026-09-21", "eps_estimate": 1.0, "eps_actual": None}]
    snap = _snapshot(
        {"earnings_calendar": earnings, "economic_calendar": MACRO_ROWS, "fed_watch": FED_ROWS}
    )
    assert snap["verdict"] == "earnings-hard-block"
    assert snap["hard_block"] == {
        "days_until": 3,
        "window_days": 5,
        "earnings_date": "2026-09-21",
    }
    # Earnings inside the window but OUTSIDE the block window: still no block.
    far = _snapshot(
        {"earnings_calendar": [{"date": "2026-10-30"}], "economic_calendar": MACRO_ROWS}
    )
    assert far["earnings"]["days_until"] == 42
    assert far["hard_block"] is None


def test_the_event_state_passes_the_hard_block_through_and_owns_no_window() -> None:
    earnings = [{"date": "2026-09-21", "eps_estimate": 1.0}]
    snap = _snapshot({"earnings_calendar": earnings})
    block = snap["hard_block"]
    assert block is not None

    comps = event_components(snap)
    assert comps[HARD_BLOCK_KEY] is block  # copied, never rebuilt
    res = event_state(comps)
    assert res["hard_block"] is block  # passed through by identity, not re-derived

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "catalyst_hard_block_days" not in source
    assert "hard_block_days" not in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            assert HARD_BLOCK_KEY not in ast.unparse(node), ast.unparse(node)
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            assert HARD_BLOCK_KEY != ast.unparse(node.slice).strip("'\""), ast.unparse(node)
    assert HARD_BLOCK_KEY not in COMPONENTS  # a passthrough, not a scored component
    assert HARD_BLOCK_KEY not in {n for n in FLAG_COMPONENTS}


def test_the_flags_are_printed_and_never_scored() -> None:
    full = event_state(_full_components())
    flags_only = event_state(
        {k: v for k, v in _full_components().items() if k in FLAG_COMPONENTS}
    )
    assert flags_only["score"] is None  # flags are evidence, not occurrence
    assert full["score"] is not None
    changed = dict(_full_components())
    changed["opex_in_week"] = False
    changed["macro_count_high"] = 9
    assert event_state(changed)["score"] == full["score"]
    for name in FLAG_COMPONENTS:
        entry = full["components"][name]
        assert entry["scored"] is False and entry["raw"] == _full_components()[name]


# --------------------------------------------------------------------------
# (c) the event keys are disjoint from RiskScore's
# --------------------------------------------------------------------------

# `RiskScore`'s event leg keeps the EXPOSURE measures (EventScore.md §0.2's split
# table and RiskScore.md §1's "Event risk" row). Pinned here as literals so the
# assertion holds whether or not WP-5 has landed; when the module exists its own
# declared tables are checked too.
RISKSCORE_EVENT_LEG_KEYS = {
    "implied_move",
    "implied_move_pct",
    "catalyst_scale",
    "scale",
    "catalyst_risk_penalty",
    "risk_penalty",
    "position_mult_by_side",
    "book_correlated_stress",
    "correlated_stress",
    "stop_distance",
    "size_pct",
}


def _riskscore_declared_keys() -> set[str]:
    """RiskScore's own declared keys, when WP-5's module is importable."""
    try:
        from tradingagents.strategies import risk_score as rs
    except Exception:  # noqa: BLE001 - WP-5 may not have landed yet
        return set()
    found: set[str] = set()
    for attr in dir(rs):
        if not attr.isupper() or attr.startswith("_"):
            continue
        obj = getattr(rs, attr)
        if isinstance(obj, dict) and obj and all(isinstance(k, str) for k in obj):
            found.update(obj)
    return found


def test_the_event_keys_are_disjoint_from_riskscores_event_keys() -> None:
    event_keys = set(COMPONENTS)
    risk_keys = set(RISKSCORE_EVENT_LEG_KEYS) | _riskscore_declared_keys()
    assert not event_keys & risk_keys, sorted(event_keys & risk_keys)
    # The split is by question: occurrence here, exposure there.
    assert "earnings_imminence" in event_keys and "implied_move" in risk_keys
    # The namespaces cannot collide: every event key is family-prefixed.
    for name in event_keys:
        assert (
            name.startswith(tuple(f"{fam}_" for fam in FAMILY_ORDER))
            or name == "catalyst_unassessed"
        ), name


# --------------------------------------------------------------------------
# (e) no gate, no size, no decision band
# --------------------------------------------------------------------------


def _referenced_names(tree: ast.AST) -> set[str]:
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            referenced.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add(node.module or "")
            referenced.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                referenced.add(".".join(reversed(parts)))
    return referenced


def test_the_module_never_touches_the_sizing_path() -> None:
    """No import and no attribute access on the sizing path (prose is not a
    dependency), and no gate precedence anywhere in the source."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    referenced = _referenced_names(tree)
    for forbidden in (
        "sizing",
        "risk.sizing",
        "risk_multiplier",
        "knife_guard",
        "position_size",
        "decision_guardrail",
        "risk_governor",
        "GATE_PRECEDENCE",
        "SCORE_BANDS",
        "risk_hierarchy",
    ):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)


def test_the_event_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert not {label for _, label in EVENT_BANDS} & {label for _, label in SCORE_BANDS}


def test_no_event_path_reaches_the_executor_gate_precedence() -> None:
    """The engine contributes no check to the executor's 17 fail-closed checks."""
    contracts = Path("../TradingExecution/signald/contracts.py")
    if not contracts.exists():
        pytest.skip("the executor repo is not checked out beside this one")
    tree = ast.parse(contracts.read_text(encoding="utf-8"))
    names: tuple[str, ...] = ()
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "GATE_PRECEDENCE":
            names = tuple(ast.literal_eval(node.value))
    assert names, "GATE_PRECEDENCE not found in the executor's contracts"
    for name in names:
        assert not any(
            token in name for token in ("event", "earnings", "catalyst", "opex", "fed", "macro")
        ), name


def test_the_state_carries_no_gate_or_size_key() -> None:
    res = event_state(_full_components())
    allowed = {
        "score",
        "band",
        "coverage",
        # The resolved coverage floor, exposed 2026-09-19 so a reader can print
        # "required" beside the coverage (ScoreContextContract.md §13.4). Not a
        # gate and not a size - the token check below still governs.
        "floor",
        "families",
        "families_present",
        "families_unmeasured",
        "components",
        "imminence",
        "hard_block",
        "weights",
        "status",
        "withheld",
        "basis",
    }
    assert set(res) == allowed
    assert res["hard_block"] is None  # the one passthrough, and it is empty here
    for key in res:
        assert not any(
            token in key for token in ("gate", "blocked", "size", "position_scale", "action")
        ), key


def test_the_module_reaches_no_vendor_or_network() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert modules <= {
        "__future__",
        "math",
        "typing",
        "catalyst",
        "score_engine",
    }, modules


# --------------------------------------------------------------------------
# the producer bridge, the absent families and the calendar interfaces
# --------------------------------------------------------------------------


def test_the_engine_reads_the_producers_own_windows() -> None:
    snap = _snapshot(
        {
            "earnings_calendar": [{"date": "2026-09-21", "eps_estimate": 1.0}],
            "economic_calendar": MACRO_ROWS,
            "fed_watch": FED_ROWS,
        }
    )
    comps = event_components(snap, opex=OPEX)
    assert comps["earnings_imminence"] == 3
    assert comps["macro_imminence"] == 0
    assert comps["macro_count_high"] == 1
    assert comps["fed_imminence"] == 2
    assert comps["fed_modal_prob"] == 88.0
    assert comps["opex_imminence"] == 2
    res = event_state(comps)
    assert res["families"]["earnings"]["imminence"] == pytest.approx(1 - 3 / 60)
    assert res["families"]["opex"]["imminence"] == pytest.approx(1 - 2 / 7)
    assert res["coverage"] == pytest.approx(4 / 7, abs=1e-4)
    assert res["score"] is not None

    # A snapshot with no calendars at all is the producer's honest degradation...
    bare = _snapshot({})
    bare_comps = event_components(bare)
    assert bare_comps["catalyst_unassessed"] is True
    assert "earnings_imminence" not in bare_comps
    assert "fed_imminence" not in bare_comps
    # ...and opex_status with no forward expiry contributes nothing, never 0.
    empty_opex = event_components(snap, opex={"next_opex": None, "days_to_next": None})
    assert "opex_imminence" not in empty_opex


def test_the_absent_families_carry_their_probe_evidence() -> None:
    """Two families are still ABSENT after the 2026-09-18 sourcing decision, and
    each names its own reason. ``product_clinical`` is NO LONGER one of them: it
    has a producer now (pdufa.bio), so claiming it is absent would be false."""
    for family in ("court", "investor_day"):
        assert FAMILY_AVAILABILITY[family] == ABSENT
        assert "ABSENT" in ABSENT_REASONS[family]
        assert "forward_calendar" in MODULE_PATH.read_text(encoding="utf-8")
    assert FAMILY_AVAILABILITY["product_clinical"] == SCORABLE, (
        "pdufa.bio answers this family's two interfaces as of 2026-09-18")
    assert "product_clinical" not in ABSENT_REASONS, (
        "an absent-reason for a family that has a producer is a dead claim")
    res = event_state(_full_components())
    for family in ("court", "investor_day"):
        state = res["families"][family]
        assert state["availability"] == ABSENT
        assert state["imminence"] is None and state["score"] is None
        assert state["reason"] and state["reason"] in ABSENT_REASONS.values()
    # The court reason is the LIVE vendor finding, not the old assumption.
    assert "CourtListener" in ABSENT_REASONS["court"]
    assert "backward-looking" in ABSENT_REASONS["court"]
    assert "DROPPED" in ABSENT_REASONS["investor_day"]
    # ...and the product_clinical family, when it cannot measure, says why.
    state = res["families"]["product_clinical"]
    assert state["availability"] == SCORABLE
    assert state["imminence"] is None and state["reason"] == NA_REASONS["product_clinical"]


def test_the_four_calendar_interfaces_answer_available_missing_or_not_applicable() -> None:
    assert CALENDAR_INTERFACES == ("product", "clinical", "court", "investor_day")
    missing = forward_calendar("court")
    assert missing["status"] == "missing" and missing["next"] is None
    assert "CourtListener" in missing["reason"], "the live finding, not a stale assumption"
    rows = [{"date": "2026-09-30"}, {"date": "2026-10-05"}]
    ready = forward_calendar("investor_day", rows, trade_date="2026-09-18")
    assert ready["status"] == "available"
    assert ready["next"] == {"date": "2026-09-30", "days_until": 12}
    assert ready["events"] == 2
    assert forward_calendar("product", [], trade_date="2026-09-18")["status"] == "not_applicable"
    past = forward_calendar("clinical", [{"date": "2026-09-01"}], trade_date="2026-09-18")
    assert past["status"] == "not_applicable"
    with pytest.raises(KeyError):
        forward_calendar("nope")


def test_a_scorable_family_asked_with_no_rows_states_the_na_reason() -> None:
    """A family WITH a producer that was not asked (the calendar gate is off, or
    the source did not answer) is not the same as a family with no producer.

    This crashed on the first run after pdufa.bio landed: ``forward_calendar``
    reached for ABSENT_REASONS, which no longer carries ``product_clinical``.
    """
    answer = forward_calendar("product")
    assert answer["status"] == "missing"
    assert answer["reason"] == NA_REASONS["product_clinical"]
    # ...and an adapter's own finding still wins over both static texts.
    own = forward_calendar("product", None, reason="the source said so")
    assert own["reason"] == "the source said so"


def test_a_missing_calendar_is_never_converted_to_zero() -> None:
    """§7 Q5: unknown is not "no event exists" and certainly not "negative"."""
    answers = {
        "product": forward_calendar("product"),  # missing
        "clinical": forward_calendar("clinical", [], trade_date="2026-09-18"),  # not_applicable
    }
    comps = event_components(_snapshot({}), calendars=answers)
    assert not any(k.startswith("product_clinical") for k in comps)
    res = event_state(comps)
    assert res["families"]["product_clinical"]["imminence"] is None
    assert res["families"]["product_clinical"]["availability"] == SCORABLE
    # An available answer fills the slot, and the nearest of the two wins.
    live = {"clinical": forward_calendar("clinical", [{"date": "2026-10-16"}], trade_date="2026-09-18"),
            "product": forward_calendar("product", [{"date": "2026-09-21"}], trade_date="2026-09-18")}
    filled = event_components(_snapshot({}), calendars=live)
    assert filled["product_clinical_imminence"] == 3
    assert event_state(filled)["families"]["product_clinical"]["imminence"] == pytest.approx(1 - 3 / 90)


def test_the_calendar_answers_never_collapse_none_into_an_empty_list() -> None:
    """The one mistake that turns "this source cannot carry a forward date" into
    the false claim "no event is scheduled"."""
    from tradingagents.strategies.event_state import calendar_answers

    answers = calendar_answers(
        {"product": [], "clinical": None, "court": None, "investor_day": None},
        trade_date="2026-09-18",
        reasons={"court": "no forward date exists in this source"},
    )
    assert answers["product"]["status"] == "not_applicable", "asked and empty"
    assert answers["clinical"]["status"] == "missing", "NOT asked - a different claim"
    assert answers["court"]["reason"] == "no forward date exists in this source"
    assert answers["investor_day"]["status"] == "missing"


def test_the_families_declare_their_scope() -> None:
    assert [FAMILY_SCOPE[f] for f in FAMILY_ORDER] == [
        "NAME", "MARKET", "MARKET", "MARKET", "NAME", "NAME", "NAME",
    ]
    for family in FAMILY_ORDER:
        assert family in HORIZONS, family
        assert HORIZONS[family] > 0, family


def test_the_every_family_has_one_imminence_slot() -> None:
    slots = [c.family for c in COMPONENTS.values() if c.kind == "imminence"]
    assert sorted(slots) == sorted(FAMILY_ORDER)
    assert inspect.ismodule(inspect.getmodule(event_state))
    for family in FAMILY_ORDER:
        assert any(COMPONENTS[n].family == family for n in COMPONENTS)


# --------------------------------------------------------------------------
# the wiring (added by the integration owner after the shared files landed)
# --------------------------------------------------------------------------


def test_the_event_leaf_is_in_no_toolset_whatever_the_gate(monkeypatch) -> None:
    """§13.3 + §6 acceptance (a), now one stronger statement.

    The leaf was bound to the news analyst when its gate was on. Engine leaves
    are application-internal calculation mechanisms, not LLM-facing tools, so
    the toolset is byte-identical whether the gate is on or off - which is
    acceptance (a) satisfied by construction rather than by a branch.
    """
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents import toolsets

    monkeypatch.setattr(cfgmod, "get_config", lambda: {})
    off = [t.name for t in toolsets.news_tools()]
    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_event_state": True})
    on = [t.name for t in toolsets.news_tools()]
    assert "get_event_state" not in off
    assert "get_event_state" not in on
    assert on == off


def test_gate_off_writes_no_card_key() -> None:
    from tradingagents.reporting import _run_card_event_state

    assert _run_card_event_state({}, {}) is None


def test_the_leaf_says_the_gate_is_off(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents.utils.analysis_tools import get_event_state

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_event_state": False})
    out = get_event_state.invoke({"ticker": "MSFT", "current_date": "2026-09-18"})
    assert "gated off" in out and "enable_event_state" in out


def test_the_card_block_reads_the_runs_own_snapshot(monkeypatch) -> None:
    from tradingagents.reporting import _run_card_event_state

    state = {
        "trade_date": "2026-09-18",
        "strategy_overlays": {
            "catalyst": {
                "next_earnings": {"days_until": 3, "date": "2026-09-21"},
                "hard_block": {"reason": "earnings in window"},
            }
        },
    }
    block = _run_card_event_state(state, {"enable_event_state": True})
    assert block["status"] == "RESEARCH_ONLY"
    assert block["hard_block"] == {"reason": "earnings in window"}
    assert block["families"]
    assert block["basis"]


def test_the_card_block_degrades_without_a_snapshot() -> None:
    from tradingagents.reporting import _run_card_event_state

    block = _run_card_event_state({}, {"enable_event_state": True})
    assert block["score"] is None
    assert "no catalyst snapshot" in block["unavailable"]
