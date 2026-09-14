"""Offline tests for S11 symmetric evidence for paired roles.

Covers the S11a symmetry report, S11b declared deterministic defaults, the
S11c mirrored discretionary budget and the S11d plan validation + fallback.
Every fixture is a fake tool or a fake plan - no vendor call and no LLM.
"""

from __future__ import annotations

import importlib.util
import logging
import types
from pathlib import Path

import pytest
from langchain_core.tools import tool

from tradingagents.agents.utils import evidence_gather as eg
from tradingagents.agents.utils.evidence_gather import (
    MODEL_POOL_KEY,
    SYMMETRY_KEY,
    TOOL_ARG_DEFAULTS,
    TOOL_EVIDENCE_KEY,
    classify_tool_pools,
    gather_evidence,
    gather_for_analyst_node,
    mirror_discretionary_budget,
    parse_evidence_plan,
    plan_evidence_calls,
    resolve_model_pool_plan,
    stored_symmetry,
    symmetry_report,
    symmetry_rows,
)

pytestmark = pytest.mark.timeout(120)

_REPO_ROOT = Path(__file__).resolve().parents[1]


@tool
def get_financials(ticker: str, current_date: str | None = None) -> str:
    """Fake fundamentals surface (required args all in the gather context)."""
    return f"fin:{ticker}:{current_date or 'none'}"


@tool
def get_bsm_quote(spot: float, strike: float, t_years: float, vol: float) -> str:
    """Fake model-pool tool: every arg is model-supplied (no declared default)."""
    return f"bsm:{spot}:{strike}:{t_years}:{vol}"


@tool
def get_macro_indicators(
    indicator: str, curr_date: str, look_back_days: int | None = None
) -> str:
    """Fake of the real enumerable-arg tool (S11b declares its default)."""
    return f"macro:{indicator}:{curr_date}:{look_back_days}"


def _leaf(name: str, args: dict, status: str = "ok", content: str = "value") -> dict:
    return {
        "tool": name,
        "args": args,
        "status": status,
        "content": content,
        "args_hash": "deadbeefcafe",
        "ts": 0.0,
    }


def _load_repro_check():
    spec = importlib.util.spec_from_file_location(
        "repro_check_evidence_symmetry", _REPO_ROOT / "scripts" / "repro_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# S11a - symmetry report
# ---------------------------------------------------------------------------


def test_symmetry_report_contract_shape_and_symmetric_pair():
    evidence = {"a": [_leaf("t1", {"ticker": "X"})], "b": [_leaf("t1", {"ticker": "X"})]}
    report = symmetry_report(evidence, {})
    assert set(report) == {"pairs", "verdict", "differs_on", "basis"}
    assert report["verdict"] == "SYMMETRIC"
    assert report["differs_on"] == []
    row = report["pairs"][0]
    assert set(row) == {
        "pair",
        "side_a",
        "side_b",
        "planned",
        "fired",
        "leaves",
        "unavailable",
        "arg_key_diff",
        "as_of",
        "discretionary",
        "verdict",
        "differs_on",
    }
    assert row["planned"] == {"a": ["t1"], "b": ["t1"]}


def test_asymmetric_pair_names_the_extra_tool():
    # The extra tool sits in side A's model-pool remainder: planned A gains it,
    # planned B does not -> ASYMMETRIC naming it (plan section 4 mutation
    # "count leaves but not planned tools").
    evidence = {
        "a": [_leaf("get_financials", {"ticker": "X"})],
        "b": [_leaf("get_financials", {"ticker": "X"})],
        MODEL_POOL_KEY: {"a": ["get_macro_indicators"], "b": []},
    }
    report = symmetry_report(evidence)
    assert report["verdict"] == "ASYMMETRIC"
    assert report["differs_on"] == ["get_macro_indicators"]
    assert report["pairs"][0]["discretionary"] == {"a": 1, "b": 0}


def test_asymmetric_pair_extra_fired_tool_is_named():
    evidence = {
        "a": [_leaf("t1", {}), _leaf("t2", {})],
        "b": [_leaf("t1", {})],
    }
    report = symmetry_report(evidence, {})
    assert report["verdict"] == "ASYMMETRIC"
    assert report["differs_on"] == ["t2"]


def test_no_leaf_pair_is_unavailable_not_symmetric():
    # Mutation "report SYMMETRIC when a side has no leaves".
    evidence = {"a": [], "b": [_leaf("t1", {})]}
    report = symmetry_report(evidence, {})
    assert report["pairs"][0]["verdict"] == "unavailable"
    assert report["verdict"] == "unavailable"


def test_arg_key_diff_and_as_of_are_reported():
    evidence = {
        "a": [_leaf("t1", {"ticker": "X", "as_of": "2026-09-07"})],
        "b": [_leaf("t1", {"ticker": "X", "as_of": "2026-09-07", "window": 30})],
    }
    report = symmetry_report(evidence, {})
    row = report["pairs"][0]
    assert row["arg_key_diff"] == ["window"]
    assert row["as_of"] == {"a": ["2026-09-07"], "b": ["2026-09-07"]}
    assert row["verdict"] == "ASYMMETRIC"


def test_symmetry_report_makes_zero_vendor_calls(monkeypatch):
    counter = {"n": 0}

    def explode(*args, **kwargs):
        counter["n"] += 1
        raise AssertionError("symmetry_report must not execute a tool")

    monkeypatch.setattr(eg, "gather_evidence", explode)
    evidence = {
        "market": [_leaf("t1", {})],
        "news": [_leaf("t1", {})],
        MODEL_POOL_KEY: {"market": ["m1"], "news": []},
    }
    symmetry_report(evidence)
    assert counter["n"] == 0


def test_symmetry_rows_are_reporting_safe():
    report = symmetry_report({"a": [], "b": []}, {})
    rows = symmetry_rows(report)
    assert isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows)
    assert all("tool" not in r for r in rows)
    assert stored_symmetry({SYMMETRY_KEY: rows})["verdict"] == report["verdict"]

    # The persisted block must not break reporting's source-coverage walk.
    from tradingagents.reporting import _evidence_sources

    used, empty = _evidence_sources(
        {"tool_evidence": {"a": [_leaf("t1", {})], SYMMETRY_KEY: rows}}
    )
    assert used == ["t1"]
    assert empty == []


# ---------------------------------------------------------------------------
# S11b - declared deterministic default args
# ---------------------------------------------------------------------------


def test_declared_default_moves_tool_to_gather_with_reason(caplog):
    moves = []
    with caplog.at_level(logging.INFO):
        gather, model = classify_tool_pools(
            [get_macro_indicators, get_bsm_quote, get_financials],
            defaults=TOOL_ARG_DEFAULTS,
            on_move=lambda name, covered, reason: moves.append((name, covered, reason)),
        )
    assert "get_macro_indicators" in gather
    assert "get_bsm_quote" in model
    assert moves and moves[0][0] == "get_macro_indicators"
    assert "indicator" in moves[0][1]
    assert "declared enumerable default" in moves[0][2]
    assert "get_macro_indicators" in caplog.text


def test_tool_without_declared_default_stays_in_model_pool():
    gather, model = classify_tool_pools([get_bsm_quote], on_move=lambda *a: None)
    assert gather == []
    assert model == ["get_bsm_quote"]


def test_forced_leaf_set_is_byte_identical_for_single_valued_enum():
    tools = {"get_macro_indicators": get_macro_indicators}
    context = {"curr_date": "2026-09-07"}
    first = gather_evidence(
        tools, ["get_macro_indicators"], context=context, arg_defaults=TOOL_ARG_DEFAULTS
    )
    second = gather_evidence(
        tools, ["get_macro_indicators"], context=context, arg_defaults=TOOL_ARG_DEFAULTS
    )
    assert first[0].args["indicator"] == "10y_treasury"
    assert first[0].args == second[0].args
    assert first[0].args_hash == second[0].args_hash
    assert first[0].content == second[0].content


# ---------------------------------------------------------------------------
# S11c - mirrored discretionary budget
# ---------------------------------------------------------------------------


def test_mirror_journals_surplus_and_report_is_asymmetric(monkeypatch):
    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda analyst, tool, event, args=None, state=None, in_model_pool=None: events.append(
            (analyst, tool, event, args)
        ),
    )
    calls = {
        "A": [
            {"name": "t1", "args": {"q": 1}},
            {"name": "t2", "args": {"q": 2}},
            {"name": "t3", "args": {"q": 3}},
        ],
        "B": [{"name": "t1", "args": {"q": 1}}],
    }
    out = mirror_discretionary_budget(calls)
    assert out["allowances"]["A/B"] == 1
    assert [c["name"] for c in out["suppressed"]["A"]] == ["t2", "t3"]
    assert out["suppressed"]["B"] == []
    assert [c["name"] for c in out["kept"]["A"]] == ["t1"]
    # The journal carries the surplus WITH its args, so the asymmetry is visible.
    assert [(e[0], e[1], e[2]) for e in events] == [
        ("A", "t2", "suppressed"),
        ("A", "t3", "suppressed"),
    ]
    assert events[0][3] == {"q": 2}

    # The discretionary split the mirror reveals is an ASYMMETRIC symmetry row.
    report = symmetry_report(
        {"A": [_leaf("t1", {})], "B": [_leaf("t1", {})]},
        {"A": ["t1", "t2", "t3"], "B": ["t1"]},
    )
    assert report["verdict"] == "ASYMMETRIC"


def test_mirror_equal_case_is_clean(monkeypatch):
    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda *a, **k: events.append(a),
    )
    out = mirror_discretionary_budget(
        {"A": [{"name": "t1"}], "B": [{"name": "t1"}]}
    )
    assert out["suppressed"] == {"A": [], "B": []}
    assert events == []


def test_mirror_never_drops_a_forced_leaf(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call", lambda *a, **k: None
    )
    calls = {
        "A": [{"name": "t1"}, {"name": "forced"}, {"name": "t2"}],
        "B": [{"name": "t1"}],
    }
    out = mirror_discretionary_budget(calls, forced=["forced"])
    assert [c["name"] for c in out["kept"]["A"]] == ["t1", "forced"]
    assert [c["name"] for c in out["suppressed"]["A"]] == ["t2"]


# ---------------------------------------------------------------------------
# S11d - argument-plan call + fallback
# ---------------------------------------------------------------------------


def test_valid_plan_fires_leaves_one_to_one():
    tools = {"get_financials": get_financials}
    plan = {"get_financials": {"ticker": "TSM", "current_date": "2026-09-07"}}
    leaves = plan_evidence_calls(tools, plan)
    assert len(leaves) == 1
    assert leaves[0].tool == "get_financials"
    assert leaves[0].args == plan["get_financials"]
    assert leaves[0].status == "ok"


def test_invalid_plan_returns_a_reason_and_never_raises():
    tools = {"get_financials": get_financials}
    plan, reason = parse_evidence_plan("not json at all", ["get_financials"], tools)
    assert plan is None and "JSON" in reason
    leaves, reason = resolve_model_pool_plan("also not json", tools, ["get_financials"])
    assert leaves == [] and reason


def test_plan_outside_the_whitelist_is_rejected():
    tools = {"get_financials": get_financials, "get_bsm_quote": get_bsm_quote}
    plan, reason = parse_evidence_plan(
        {"get_bsm_quote": {"spot": 1.0, "strike": 1.0, "t_years": 1.0, "vol": 0.2}},
        ["get_financials"],
        tools,
    )
    assert plan is None and "whitelist" in reason


def test_empty_plan_is_rejected():
    tools = {"get_financials": get_financials}
    plan, reason = parse_evidence_plan({}, ["get_financials"], tools)
    assert plan is None and reason
    plan, reason = parse_evidence_plan("   ", ["get_financials"], tools)
    assert plan is None and reason


def test_plan_args_must_match_the_tool_schema():
    tools = {"get_financials": get_financials}
    plan, reason = parse_evidence_plan(
        {"get_financials": {"nope": 1}}, ["get_financials"], tools
    )
    assert plan is None and "schema" in reason


def test_gate_off_leaves_the_gather_unchanged(monkeypatch):
    # Explicit OFF: the operator's .env may have the gate on (dark launch).
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: False)
    calls = {"planner": 0}

    def planner(*args, **kwargs):
        calls["planner"] += 1
        return {"get_bsm_quote": {"spot": 1.0, "strike": 1.0, "t_years": 1.0, "vol": 0.2}}

    cfg = {"analyst_forced_tools": ["get_financials"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    _, evidence = gather_for_analyst_node(
        state, "market", [get_financials, get_bsm_quote], cfg, planner=planner
    )
    assert calls["planner"] == 0
    assert [leaf["tool"] for leaf in evidence["market"]] == ["get_financials"]


def test_gate_off_does_not_move_declared_default_tool(monkeypatch):
    # Explicit OFF: the operator's .env may have the gate on (dark launch).
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: False)
    cfg = {"analyst_forced_tools": ["get_macro_indicators"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    _, evidence = gather_for_analyst_node(state, "market", [get_macro_indicators], cfg)
    # Gate off: the tool stays in the model pool, so no gather leaf is made.
    assert "market" not in evidence
    assert evidence[MODEL_POOL_KEY]["market"] == ["get_macro_indicators"]


def test_gate_on_moves_declared_default_tool_and_prints_reason(monkeypatch):
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)
    cfg = {"analyst_forced_tools": ["get_macro_indicators"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    block, evidence = gather_for_analyst_node(state, "market", [get_macro_indicators], cfg)
    assert [leaf["tool"] for leaf in evidence["market"]] == ["get_macro_indicators"]
    assert "Declared-default tools moved to the deterministic gather" in block
    assert "indicator='10y_treasury'" in block


def test_gated_plan_fires_through_the_executor(monkeypatch):
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)

    def planner(*args, **kwargs):
        return {"get_bsm_quote": {"spot": 1.0, "strike": 1.0, "t_years": 1.0, "vol": 0.2}}

    cfg = {"analyst_forced_tools": ["get_financials"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    _, evidence = gather_for_analyst_node(
        state, "market", [get_financials, get_bsm_quote], cfg, planner=planner
    )
    fired = [leaf["tool"] for leaf in evidence["market"]]
    assert fired == ["get_bsm_quote", "get_financials"]


class _FakePlanLLM:
    def __init__(self, content):
        self._content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return types.SimpleNamespace(content=self._content)


def test_llm_planner_plan_is_journaled_and_fires_one_to_one(monkeypatch):
    from tradingagents.agents.utils.evidence_gather import make_llm_planner

    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda analyst, tool, event, args=None, state=None, in_model_pool=None: events.append(
            (analyst, tool, event, args)
        ),
    )
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)
    llm = _FakePlanLLM(
        '{"get_bsm_quote": {"spot": 1.0, "strike": 1.0, "t_years": 1.0, "vol": 0.2}}'
    )
    cfg = {"analyst_forced_tools": ["get_financials"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    _, evidence = gather_for_analyst_node(
        state,
        "market",
        [get_financials, get_bsm_quote],
        cfg,
        planner=make_llm_planner(llm),
    )
    fired = [leaf["tool"] for leaf in evidence["market"]]
    assert fired == ["get_bsm_quote", "get_financials"]
    planned = [e for e in events if e[2] == "planned"]
    assert [(e[0], e[1], e[3]["spot"]) for e in planned] == [
        ("market", "get_bsm_quote", 1.0)
    ]
    assert llm.prompts and "get_bsm_quote" in llm.prompts[0]


def test_gated_invalid_plan_falls_back_with_a_stated_reason(monkeypatch, caplog):
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)
    cfg = {"analyst_forced_tools": ["get_financials"]}
    state = {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    with caplog.at_level(logging.WARNING):
        _, evidence = gather_for_analyst_node(
            state,
            "market",
            [get_financials, get_bsm_quote],
            cfg,
            planner=lambda *a, **k: "definitely not a plan",
        )
    assert [leaf["tool"] for leaf in evidence["market"]] == ["get_financials"]
    assert any("fell back to the legacy loop" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Pre-debate node + repro rendering
# ---------------------------------------------------------------------------


def test_pre_debate_symmetry_node_records_verdict_without_blocking():
    from tradingagents.graph.setup import create_evidence_symmetry_node

    node = create_evidence_symmetry_node({})
    state = {
        TOOL_EVIDENCE_KEY: {
            "market": [_leaf("get_financials", {})],
            "news": [_leaf("get_financials", {})],
            MODEL_POOL_KEY: {"market": ["get_macro_indicators"], "news": []},
        }
    }
    out = node(state)
    evidence = out[TOOL_EVIDENCE_KEY]
    report = stored_symmetry(evidence)
    assert report is not None and report["verdict"] == "ASYMMETRIC"
    # never blocks: every other channel is untouched, and a malformed state is safe
    assert set(out) == {TOOL_EVIDENCE_KEY}
    assert evidence["market"][0]["tool"] == "get_financials"
    assert node({"tool_evidence": "not a dict"}) == {}


def test_repro_renders_symmetry_columns(capsys):
    rc = _load_repro_check()
    evidence = {
        "market": [_leaf("get_financials", {})],
        "news": [_leaf("get_financials", {})],
        MODEL_POOL_KEY: {"market": ["get_macro_indicators"], "news": []},
    }
    rc._print_symmetry([evidence])
    out = capsys.readouterr().out
    assert "evidence symmetry" in out
    assert "ASYMMETRIC" in out
    assert "get_macro_indicators" in out


def test_repro_config_hash_tracks_round3_gates():
    rc = _load_repro_check()
    from tradingagents.default_config import DEFAULT_CONFIG

    rc._CONFIG_HASH_CACHE.clear()
    before = rc._config_hash()
    # Flip relative to whatever the operator's config holds, so the test does not
    # depend on the ambient .env gate state.
    original = DEFAULT_CONFIG["enable_evidence_symmetry"]
    try:
        DEFAULT_CONFIG["enable_evidence_symmetry"] = not original
        rc._CONFIG_HASH_CACHE.clear()
        after = rc._config_hash()
    finally:
        DEFAULT_CONFIG["enable_evidence_symmetry"] = original
        rc._CONFIG_HASH_CACHE.clear()
    assert before != after


# ---------------------------------------------------------------------------
# S11c wiring: the live tool-loop path (
#   _journal_executed) uses the same split rule as the pair API, under the gate
#   and only for a DECLARED pair.
# ---------------------------------------------------------------------------


def _pool_state(analyst: str, forced: list, partner: str | None = None, partner_pool=()):
    evidence = {MODEL_POOL_KEY: {analyst: []}, analyst: forced}
    if partner is not None:
        evidence[partner] = [_leaf(name, {}) for name in partner_pool]
        evidence[MODEL_POOL_KEY][partner] = list(partner_pool)
    return {TOOL_EVIDENCE_KEY: evidence}


def _tool_messages(names):
    from langchain_core.messages import ToolMessage

    return [
        ToolMessage(content=f"result-{name}", name=name, tool_call_id=f"c{index}")
        for index, name in enumerate(names)
    ]


def test_journal_executed_suppresses_surplus_discretionary_calls(monkeypatch):
    """A declared pair budget caps the LIVE path: surplus calls are dropped

    from the evidence and journaled with their args (S11c).
    """
    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda analyst, tool, event, args=None, state=None, in_model_pool=None: events.append(
            (analyst, tool, event, args)
        ),
    )
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)
    monkeypatch.setattr(
        eg, "_config", lambda: {"evidence_symmetry_pairs": [{"roles": ["fundamentals", "news"], "budget": 1}]}
    )
    state = _pool_state("fundamentals", [_leaf("get_financials", {})])
    remaining = [
        {"name": "get_bsm_quote", "args": {"spot": 1.0}},
        {"name": "get_probe_a", "args": {"q": 2}},
        {"name": "get_probe_b", "args": {"q": 3}},
    ]
    out = eg._journal_executed(
        state, "fundamentals", remaining,
        _tool_messages(["get_bsm_quote", "get_probe_a", "get_probe_b"]),
    )
    tools = [leaf["tool"] for leaf in out["tool_evidence"]["fundamentals"]]
    assert tools == ["get_financials", "get_bsm_quote"]
    assert [(e[0], e[1], e[2]) for e in events] == [
        ("fundamentals", "get_probe_a", "suppressed"),
        ("fundamentals", "get_probe_b", "suppressed"),
    ]
    assert events[0][3] == {"q": 2}


def test_journal_executed_is_unchanged_without_a_declared_pair(monkeypatch):
    """Gate on but no pair declared: byte-identical to today (the mirror is inert)."""
    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda *a, **k: events.append(a),
    )
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: True)
    monkeypatch.setattr(eg, "_config", lambda: {"evidence_symmetry_pairs": []})
    state = _pool_state("fundamentals", [_leaf("get_financials", {})])
    remaining = [
        {"name": "t1", "args": {}},
        {"name": "t2", "args": {}},
        {"name": "t3", "args": {}},
    ]
    out = eg._journal_executed(
        state, "fundamentals", remaining, _tool_messages(["t1", "t2", "t3"])
    )
    tools = [leaf["tool"] for leaf in out["tool_evidence"]["fundamentals"]]
    assert tools == ["get_financials", "t1", "t2", "t3"]
    assert events == []


def test_journal_executed_is_unchanged_with_the_gate_off(monkeypatch):
    """Declared pair but gate off: the mirror never runs."""
    events = []
    monkeypatch.setattr(
        "tradingagents.agents.utils.tool_call_log.log_tool_call",
        lambda *a, **k: events.append(a),
    )
    monkeypatch.setattr(eg, "_flag", lambda name, default=False: False)
    monkeypatch.setattr(
        eg, "_config", lambda: {"evidence_symmetry_pairs": [{"roles": ["fundamentals", "news"], "budget": 0}]}
    )
    state = _pool_state("fundamentals", [])
    remaining = [{"name": "t1", "args": {}}, {"name": "t2", "args": {}}]
    out = eg._journal_executed(
        state, "fundamentals", remaining, _tool_messages(["t1", "t2"])
    )
    assert [leaf["tool"] for leaf in out["tool_evidence"]["fundamentals"]] == ["t1", "t2"]
    assert events == []


def test_split_counts_only_discretionary_calls():
    """A forced leaf neither consumes the allowance nor is ever dropped."""
    calls = [{"name": "forced"}, {"name": "a"}, {"name": "b"}]
    keep, drop = eg._split_discretionary(calls, 1, {"forced"})
    assert [c["name"] for c in keep] == ["forced", "a"]
    assert [c["name"] for c in drop] == ["b"]
    assert eg._split_discretionary(calls, None, {"forced"}) == (calls, [])


def test_pair_allowance_mirrors_an_already_run_partner():
    """No declared budget: the allowance is the pair's smallest OBSERVED count."""
    pairs = {"evidence_symmetry_pairs": [{"roles": ["news", "fundamentals"]}]}
    state = _pool_state(
        "fundamentals", [], partner="news", partner_pool=("t1", "t2")
    )
    assert eg._pair_allowance_for("fundamentals", state, pairs) == 2
    # A partner that has not run cannot cap a first mover to zero.
    assert eg._pair_allowance_for("news", _pool_state("news", []), pairs) is None
    # A declared budget always wins over the observed count.
    declared = {"evidence_symmetry_pairs": [{"roles": ["news", "fundamentals"], "budget": 1}]}
    assert eg._pair_allowance_for("fundamentals", state, declared) == 1
    # No pair at all -> no mirror.
    assert eg._pair_allowance_for("fundamentals", state, {}) is None


def test_symmetry_pair_env_accepts_a_json_list():
    from tradingagents.default_config import _coerce

    raw = '[{"roles": ["news", "fundamentals"], "budget": 2}]'
    assert _coerce(raw, []) == [{"roles": ["news", "fundamentals"], "budget": 2}]
    with pytest.raises(ValueError):
        _coerce('[not json', [])
    # The comma form still works for plain string lists.
    assert _coerce("news,fundamentals", []) == ["news", "fundamentals"]


def test_pair_spec_key_is_declared_and_env_mappable():
    from tradingagents import default_config as dc

    assert dc.DEFAULT_CONFIG["evidence_symmetry_pairs"] == []
    assert dc._ENV_OVERRIDES["TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS"] == (
        "evidence_symmetry_pairs"
    )
