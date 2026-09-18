"""`quant_scorecard` (WP-12 `P12-1`) — the one producer for the research layer.

Acceptance (`docs/scores/ResearchLayerWiring.md` §7, verbatim): *a unit test
scoring a fixed component set returns the engines' own numbers; no arithmetic in
the module.*

What is actually load-bearing here, and why each assertion exists:

- **The engines' own numbers come back verbatim.** A snapshot that re-derived,
  rounded or re-weighted anything would be a second producer for a number that
  already has one (master rule 15) — the defect D-8 the whole workstream exists
  to remove.
- **The date-dependent engines are handed the run's date, not the clock.** This
  is defect D-7 re-guarded on the new path: a test that pins a function's output
  but not its arguments cannot see that class (§6.2).
- **`NA` is not `0`.** A gated-off or unmeasurable engine is absent **with its
  reason** — never a zero, never a neutral 50 — and its absence reaches the
  composite as `None`.
- **The composite is `trade_score`'s number over four engines**, never by
  adjacency (master rule 17): `sentiment`/`news`/`event` are measured but never
  fed to it.

Offline and deterministic: every component helper and engine entry point is
patched, so no vendor call and no clock. Each test fails under a mutation of the
code it guards (plan §11).
"""

from __future__ import annotations

import pytest

from tradingagents.strategies import quant_scorecard as qs

TICKER = "MSFT"
DATE = "2026-07-22"

#: Every engine gate on — the fully-gated case.
ALL_ON = dict.fromkeys(qs.ENGINE_GATES.values(), True)

#: Distinctive literals so a swapped value cannot pass: each is unique to its
#: engine, and none is reachable by arithmetic over the others.
SCORES = {
    "fundamental": 71.0,
    "technical": 82.0,
    "regime": 78.0,
    "risk": 35.0,
    "sentiment": 63.0,
    "news": 55.0,
    "event": 41.0,
}

FUNDAMENTAL_RESULT = {
    "ticker": TICKER,
    "status": "RESEARCH_ONLY",
    "scores": {TICKER: SCORES["fundamental"]},
    "coverage": {TICKER: 0.90},
    "panel_n": 9,
    "basis": "peer panel as of the run date",
}
TECHNICAL_RESULT = {
    "status": "advisory",
    "score": SCORES["technical"],
    "coverage": 0.95,
    "bands": "favourable",
}
REGIME_RESULT = {
    "status": "advisory",
    "score": SCORES["regime"],
    "coverage": 0.83,
    "band": "neutral",
}
RISK_RESULT = {
    "status": "advisory",
    "score": SCORES["risk"],
    "coverage": 0.45,
    "bands": "unfavourable",
    "uncertainty": 0.31,
}
SENTIMENT_RESULT = {
    "status": "advisory",
    "score": SCORES["sentiment"],
    "coverage": 0.50,
    "bands": "favourable",
    "quadrant": "T1",
}
NEWS_RESULT = {"status": "advisory", "score": SCORES["news"], "coverage": 0.40}
EVENT_RESULT = {
    "status": "advisory",
    "score": SCORES["event"],
    "coverage": 0.70,
    "band": "neutral",
    "hard_block": None,
}


class _Calls:
    """Records every argument the snapshot passes to a producer."""

    def __init__(self) -> None:
        self.calls: dict[str, list[tuple]] = {}

    def record(self, name: str, *args):
        self.calls.setdefault(name, []).append(args)


@pytest.fixture()
def wired(monkeypatch):
    """Patch every producer the snapshot reads, and record its arguments."""
    calls = _Calls()

    def _fundamental(ticker, date=None):
        calls.record("fundamental_score_for_ticker", ticker, date)
        return dict(FUNDAMENTAL_RESULT)

    def _technical_components(ticker):
        calls.record("_technical_components", ticker)
        return {"rsi": 61.0, "mfi": 55.0}

    def _risk_components(ticker):
        calls.record("_risk_components", ticker)
        return {"beta": 1.1}

    def _regime_components():
        calls.record("_regime_components")
        return {"vix_pct": 0.4}

    def _regime_two_paths():
        return {"disagree": False, "path_a": "neutral", "path_b": "neutral"}

    def _sentiment_components(ticker, date=None, *, days=120):
        calls.record("_sentiment_components", ticker, date)
        return {"stocktwits": 0.2}, "eodhd"

    def _news_components(ticker, date=None, *, days=30):
        calls.record("_news_components", ticker, date)
        return {"sentiment": 0.1}

    def _sentiment_price_read(ticker):
        return 0.05

    monkeypatch.setattr(
        "tradingagents.strategies.fundamental_score.fundamental_score_for_ticker",
        _fundamental,
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._technical_components",
        _technical_components,
    )
    monkeypatch.setattr(
        "tradingagents.strategies.technical_score.technical_score",
        lambda vals: dict(TECHNICAL_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._risk_components", _risk_components
    )
    monkeypatch.setattr(
        "tradingagents.strategies.risk_score.risk_score",
        lambda vals: dict(RISK_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._regime_components",
        _regime_components,
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._regime_two_paths",
        _regime_two_paths,
    )
    monkeypatch.setattr(
        "tradingagents.strategies.regime_score.regime_score",
        lambda vals: dict(REGIME_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._sentiment_components",
        _sentiment_components,
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._sentiment_price_read",
        _sentiment_price_read,
    )
    monkeypatch.setattr(
        "tradingagents.strategies.sentiment_score.sentiment_score",
        lambda vals, source=None, price_read=None: dict(SENTIMENT_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._news_components",
        _news_components,
    )
    monkeypatch.setattr(
        "tradingagents.strategies.news_score.news_score",
        lambda vals: dict(NEWS_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.strategies.event_state.event_state",
        lambda vals: dict(EVENT_RESULT),
    )
    monkeypatch.setattr(
        "tradingagents.strategies.event_state.event_components",
        lambda snap, opex=None: {"earnings": 1},
    )
    monkeypatch.setattr(
        "tradingagents.strategies.derivatives_gamma.opex_status", lambda d: "opex"
    )
    return calls


def _snapshot(cfg=None, **kw):
    return qs.quant_scorecard(
        TICKER, DATE, cfg if cfg is not None else ALL_ON, **kw
    )


# ---------------------------------------------------------------------------
# the engines' own numbers, verbatim
# ---------------------------------------------------------------------------


def test_every_engine_returns_its_own_number_and_its_own_result(wired):
    snap = _snapshot(catalyst_snapshot={"earnings": {"days_until": 3}})
    for engine, expected in SCORES.items():
        entry = snap["engines"][engine]
        assert entry["score"] == expected, engine
        assert entry["reason"] is None, engine
    # the result dicts come back untouched, so a reader can recompute
    assert snap["engines"]["technical"]["result"] == TECHNICAL_RESULT
    assert snap["engines"]["risk"]["result"] == RISK_RESULT
    assert snap["engines"]["risk"]["uncertainty"] == 0.31
    assert snap["engines"]["regime"]["two_paths"]["disagree"] is False


def test_the_band_key_each_engine_uses_is_read_correctly(wired):
    """`technical_score`/`risk_score` return `bands`; the others `band`.

    Getting this wrong prints `band=None` for two engines while their scores
    look right — the number would read as one without a band at all.
    """
    snap = _snapshot(catalyst_snapshot={"earnings": {"days_until": 3}})
    engines = snap["engines"]
    assert engines["technical"]["band"] == "favourable"
    assert engines["risk"]["band"] == "unfavourable"
    assert engines["regime"]["band"] == "neutral"
    assert engines["event"]["band"] == "neutral"


def test_the_date_dependent_engines_are_read_through_the_runs_date(wired):
    """D-7 re-guarded on this path: the run's date, never the wall clock."""
    _snapshot()
    assert wired.calls["fundamental_score_for_ticker"] == [(TICKER, DATE)]
    assert wired.calls["_sentiment_components"] == [(TICKER, DATE)]
    assert wired.calls["_news_components"] == [(TICKER, DATE)]
    assert wired.calls["_technical_components"] == [(TICKER,)]
    assert wired.calls["_risk_components"] == [(TICKER,)]


def test_the_snapshot_is_keyed_on_the_run_date(wired):
    snap = _snapshot()
    assert snap["trade_date"] == DATE
    assert snap["ticker"] == TICKER


# ---------------------------------------------------------------------------
# NA is not 0
# ---------------------------------------------------------------------------


def test_a_gated_off_engine_is_absent_with_its_gate_named(wired):
    cfg = dict(ALL_ON)
    cfg["enable_regime_score"] = False
    snap = _snapshot(cfg)
    entry = snap["engines"]["regime"]
    assert entry["score"] is None
    assert entry["score"] != 0
    assert "enable_regime_score" in entry["reason"]
    assert "regime" not in snap["present"]
    assert snap["absent"]["regime"] == entry["reason"]
    # and the other engines still measured
    assert snap["engines"]["risk"]["score"] == SCORES["risk"]


def test_an_engine_that_raises_is_absent_without_costing_the_others(
    wired, monkeypatch
):
    def _boom(vals):
        raise ValueError("vendor exploded")

    monkeypatch.setattr(
        "tradingagents.strategies.technical_score.technical_score", _boom
    )
    snap = _snapshot()
    entry = snap["engines"]["technical"]
    assert entry["score"] is None
    assert "ValueError" in entry["reason"] and "vendor exploded" in entry["reason"]
    assert snap["engines"]["fundamental"]["score"] == SCORES["fundamental"]
    assert snap["engines"]["risk"]["score"] == SCORES["risk"]


def test_an_engine_with_no_measurable_components_is_absent_with_a_reason(
    wired, monkeypatch
):
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._risk_components",
        lambda ticker: {},
    )
    snap = _snapshot()
    assert snap["engines"]["risk"]["score"] is None
    assert "no risk component" in snap["engines"]["risk"]["reason"]


def test_a_measured_zero_is_a_number_and_not_an_absence(wired, monkeypatch):
    """`NA != 0` cuts both ways: a real `0.0` is present and enters the composite.

    `RiskScore` 0 means maximum risk — a legitimate measurement. Treating it as
    missing would drop a real engine from the denominator, which is the same
    defect as reporting `NA` as `0`, in the opposite direction.
    """
    monkeypatch.setattr(
        "tradingagents.strategies.risk_score.risk_score",
        lambda vals: {**RISK_RESULT, "score": 0.0},
    )
    seen = {}

    import tradingagents.strategies.trade_score as ts

    original = ts.trade_score

    def _spy(engines):
        seen.update(engines)
        return original(engines)

    try:
        ts.trade_score = _spy
        snap = _snapshot()
    finally:
        ts.trade_score = original

    assert snap["engines"]["risk"]["score"] == 0.0
    assert "risk" in snap["present"]
    assert "risk" not in snap["absent"]
    assert seen["risk"] == 0.0


def test_the_missing_engine_reaches_the_composite_as_none_not_zero(wired):
    """The composite's argument carries `None`, which lowers coverage.

    A `0` here would read as a maximally adverse engine and drag the composite,
    which is exactly the `NA != 0` rule.
    """
    seen = {}

    def _spy(engines):
        seen.update(engines)
        return {"status": "RESEARCH_ONLY", "score": 50.0, "coverage": 0.5}

    import tradingagents.strategies.trade_score as ts

    original = ts.trade_score
    try:
        ts.trade_score = _spy
        cfg = dict(ALL_ON)
        cfg["enable_risk_score"] = False
        _snapshot(cfg)
    finally:
        ts.trade_score = original
    assert seen["risk"] is None
    assert seen["fundamental"] == SCORES["fundamental"]


# ---------------------------------------------------------------------------
# the composite is the producer's number, over four engines
# ---------------------------------------------------------------------------


def test_the_composite_is_trade_scores_own_result(wired):
    seen = {}

    import tradingagents.strategies.trade_score as ts

    original = ts.trade_score

    def _spy(engines):
        seen["engines"] = dict(engines)
        return original(engines)

    try:
        ts.trade_score = _spy
        snap = _snapshot()
    finally:
        ts.trade_score = original

    # exactly the four composite engines - sentiment/news/event never enter
    assert set(seen["engines"]) == set(qs.COMPOSITE_ENGINES)
    assert seen["engines"] == {
        "fundamental": SCORES["fundamental"],
        "technical": SCORES["technical"],
        "regime": SCORES["regime"],
        "risk": SCORES["risk"],
    }
    # and the snapshot reports the producer's number, not one of its own
    assert snap["composite"]["score"] == snap["engines"]["trade"]["score"]
    assert snap["engines"]["trade"]["result"] == snap["composite"]


def test_the_composite_is_absent_when_its_gate_is_off_but_the_engines_are_read(
    wired,
):
    cfg = dict(ALL_ON)
    cfg["enable_trade_score"] = False
    snap = _snapshot(cfg)
    assert snap["engines"]["trade"]["score"] is None
    assert "enable_trade_score" in snap["engines"]["trade"]["reason"]
    assert snap["composite"] is None
    assert snap["engines"]["fundamental"]["score"] == SCORES["fundamental"]


# ---------------------------------------------------------------------------
# the event engine, and the one input that does not exist pre-graph
# ---------------------------------------------------------------------------


def test_the_event_engine_is_absent_before_the_graph_with_its_reason(wired):
    snap = _snapshot()  # no catalyst_snapshot
    entry = snap["engines"]["event"]
    assert entry["score"] is None
    assert entry["reason"] == qs.EVENT_NO_SNAPSHOT
    assert "event" in snap["absent"]


def test_the_event_engine_measures_when_the_snapshot_is_passed(wired):
    snap = _snapshot(catalyst_snapshot={"earnings": {"days_until": 3}})
    assert snap["engines"]["event"]["score"] == SCORES["event"]
    assert snap["engines"]["event"]["hard_block"] is None


# ---------------------------------------------------------------------------
# the gate map is the one rule all three readers share
# ---------------------------------------------------------------------------


def test_the_gate_map_names_a_real_config_default_for_every_engine():
    """A gate name that exists nowhere would silently never be on."""
    from tradingagents.default_config import DEFAULT_CONFIG

    for engine, gate in qs.ENGINE_GATES.items():
        assert gate in DEFAULT_CONFIG, f"{engine} -> {gate}"
        assert DEFAULT_CONFIG[gate] is False, f"{gate} must default off"


def test_only_the_four_composite_engines_are_allowed_into_the_composite():
    assert qs.COMPOSITE_ENGINES == ("fundamental", "technical", "regime", "risk")
    assert set(qs.COMPOSITE_ENGINES) <= set(qs.ENGINE_GATES)


# ---------------------------------------------------------------------------
# P12-2 — the state channel, and the trap that makes declaring it mandatory
# ---------------------------------------------------------------------------


def test_the_snapshot_channel_survives_a_real_graph_round_trip():
    """The undeclared-channel trap, tested rather than assumed (P12-2).

    Native LangGraph drops keys that are not declared on the state schema: a
    node never sees them and they are absent from the output. So this builds a
    real `StateGraph` over `AgentState`, writes the snapshot in one node and
    reads it back in the next. Remove the declaration and LangGraph silently
    drops the snapshot here - which is the whole failure mode.
    """
    from langgraph.graph import StateGraph

    from tradingagents.agents.utils.agent_states import AgentState

    seen: dict = {}

    def writer(state):
        return {"quant_scorecard": {"trade_date": DATE, "present": ["risk"]}}

    def probe(state):
        seen["read"] = state.get("quant_scorecard")
        return {}

    g = StateGraph(AgentState)
    g.add_node("writer", writer)
    g.add_node("probe", probe)
    g.set_entry_point("writer")
    g.add_edge("writer", "probe")
    g.add_edge("probe", "__end__")
    app = g.compile()

    res = app.invoke({"messages": [], "company_of_interest": TICKER, "trade_date": DATE})

    assert seen["read"] == {"trade_date": DATE, "present": ["risk"]}
    assert res.get("quant_scorecard") == {"trade_date": DATE, "present": ["risk"]}


def test_the_snapshot_channel_is_declared_on_agent_state():
    from tradingagents.agents.utils.agent_states import AgentState

    assert "quant_scorecard" in AgentState.__annotations__


def test_the_scorecard_gate_exists_and_defaults_off():
    """The master gate is `enable_quant_scorecard`, and it defaults off.

    §9 D1: this gate governs the scorecard **surface**; the eight engine gates
    above decide which engines populate it. It must never imply them.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["enable_quant_scorecard"] is False
    assert "enable_quant_scorecard" not in qs.ENGINE_GATES.values()


# ---------------------------------------------------------------------------
# P12-3 — the block
# ---------------------------------------------------------------------------


def _render(scores=None, coverage=None, status=None, enabled=None):
    """A snapshot shaped like the producer's, for render-only tests.

    The composite is **computed from the drivers** unless the caller passes one
    explicitly, because that is what the real producer does: a fixture that
    hardcoded it would be internally inconsistent, and the three-surface
    agreement test could not mean anything.
    """
    from tradingagents.strategies.trade_score import trade_score

    scores = dict(scores or {})
    coverage = coverage or {}
    enabled = enabled if enabled is not None else set(qs.ENGINE_GATES)
    if "trade" in enabled and "trade" not in scores:
        scores["trade"] = trade_score(
            {n: (scores.get(n) if n in enabled else None) for n in qs.COMPOSITE_ENGINES}
        ).get("score")
    engines = {}
    for name in qs.ENGINE_GATES:
        engines[name] = {
            "engine": name,
            "gate": qs.ENGINE_GATES[name],
            "enabled": name in enabled,
            "score": scores.get(name) if name in enabled else None,
            "coverage": coverage.get(name),
            "status": status if name == "trade" else None,
            "result": {"status": status} if name == "trade" else None,
        }
    return {"engines": engines, "trade_date": DATE, "ticker": TICKER}


def test_the_block_parses_to_exactly_the_keys_it_prints():
    """The block must be citable ground truth, not prose the registry garbles.

    This is not a formatting preference. `_parse_key_value_lines`' key pattern
    is case-insensitive and admits spaces, so a line ordered
    `trade_score=… trade_status=RESEARCH_ONLY trade_coverage=…` recovers the key
    **`research_only_trade_coverage`** and `trade_coverage` never exists in the
    registry at all. Verified against the real parser: the section 4.1 example
    produces exactly that bogus key. Reorder the status token and this fails.
    """
    from tradingagents.agents.researchers.structured_debate import (
        _parse_key_value_lines,
    )

    snap = _render(
        scores={
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        coverage={
            "trade": 0.95,
            "fundamental": 1.0,
            "technical": 0.95,
            "regime": 0.83,
            "risk": 0.45,
        },
        status="RESEARCH_ONLY",
    )
    parsed = _parse_key_value_lines(qs.format_quant_scorecard(snap))
    assert set(parsed) == {
        "trade_score",
        "trade_coverage",
        "fundamental_score",
        "fundamental_coverage",
        "technical_score",
        "technical_coverage",
        "regime_score",
        "regime_coverage",
        "risk_score",
        "risk_coverage",
    }
    # the printed composite is the snapshot's own number, not a re-derivation
    assert parsed["trade_score"] == snap["engines"]["trade"]["score"]
    assert parsed["trade_coverage"] == 0.95
    assert parsed["risk_score"] == 35.0
    assert parsed["risk_coverage"] == 0.45


def test_the_printed_number_is_the_engines_number_not_a_rounded_copy():
    """`67.925` must not become `67.93`: the block's claim is that these ARE the
    engines' numbers. The composite is passed explicitly here because this test is
    about the *form* of a three-decimal value, not about how it is derived."""
    snap = _render(scores={"trade": 67.925, "fundamental": 92.0})
    text = qs.format_quant_scorecard(snap)
    assert "trade_score=67.925" in text
    assert "67.93" not in text


def test_the_composite_is_printed_beside_its_four_drivers():
    """`76` alone is a different story from `76 because F 92 / T 85 / R 78 / K 35`."""
    snap = _render(
        scores={
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        }
    )
    text = qs.format_quant_scorecard(snap)
    for name in qs.COMPOSITE_ENGINES:
        assert f"{name}_score=" in text, name
    assert "trade_score=" in text


def test_coverage_is_printed_per_engine_and_on_the_composite():
    snap = _render(
        scores={"fundamental": 92.0, "technical": 85.0, "regime": 78.0, "risk": 35.0},
        coverage={"trade": 0.95, "fundamental": 1.0, "risk": 0.45},
    )
    text = qs.format_quant_scorecard(snap)
    assert "trade_coverage=0.95" in text
    assert "fundamental_coverage=1.0" in text
    assert "risk_coverage=0.45" in text


def test_an_unmeasurable_engine_prints_na_never_zero():
    snap = _render(scores={"fundamental": 92.0}, coverage={"fundamental": 1.0})
    text = qs.format_quant_scorecard(snap)
    assert "risk_score=NA" in text
    assert "risk_score=0" not in text
    # and it is named as absent
    assert "absent=" in text and "risk" in text.split("absent=")[-1]


def test_a_gated_off_engine_is_not_printed_and_not_called_absent():
    """A gate-off engine is not part of the scorecard — it is not "missing
    evidence"."""
    snap = _render(
        scores={"trade": 70.0, "fundamental": 92.0},
        enabled={"trade", "fundamental"},
    )
    text = qs.format_quant_scorecard(snap)
    assert "risk_score" not in text
    assert "technical_score" not in text
    assert "absent=none" in text


def test_the_block_states_its_purpose_and_stays_within_its_bound():
    snap = _render(scores={"fundamental": 92.0})
    text = qs.format_quant_scorecard(snap)
    assert text.startswith(qs.SCORECARD_HEADER)
    assert qs.SCORECARD_PURPOSE in text
    assert "not an order" in text
    assert len(text) <= qs.SCORECARD_MAX_CHARS


def test_the_block_becomes_citable_ground_truth():
    """P12-3's acceptance: `ground_truth_from_state` returns the score keys.

    A number the debate cannot cite is a number the L1 registry marks
    unverified, so the block has to survive the real parse.
    """
    from tradingagents.agents.researchers.structured_debate import (
        ground_truth_from_state,
    )

    snap = _render(
        scores={
            "trade": 67.925,
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        coverage={"trade": 0.95, "risk": 0.45},
        status="RESEARCH_ONLY",
    )
    gt = ground_truth_from_state(
        {"computed_decision_context": qs.format_quant_scorecard(snap)}
    )
    assert gt["trade_score"] == 67.925
    assert gt["trade_coverage"] == 0.95
    assert gt["fundamental_score"] == 92.0
    assert gt["risk_score"] == 35.0
    assert gt["risk_coverage"] == 0.45


def test_the_debate_prompt_keeps_the_scorecard_when_the_context_is_truncated():
    """P12-4's acceptance: the 3000-char bound applies to the REST of the context.

    Without a field of its own, the block would sit inside that bound and could
    be truncated away — on the one path in the graph with deterministic claim
    verification.
    """
    from tradingagents.agents.researchers.structured_debate import build_turn_prompt

    snap = _render(
        scores={
            "trade": 67.925,
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        coverage={"trade": 0.95, "risk": 0.45},
        status="RESEARCH_ONLY",
    )
    block = qs.format_quant_scorecard(snap)
    filler = "\n\n".join(
        f"Section {i} of the deterministic context. " + ("y" * 500) for i in range(12)
    )
    assert len(filler) > 3000
    state = {
        "computed_decision_context": block + "\n\n" + filler,
        "asset_type": "stock",
        "trade_date": DATE,
    }

    prompt = build_turn_prompt(state, "bull", "bullish")

    assert "**Quant scorecard**" in prompt
    scorecard_field = prompt.split("**Quant scorecard**")[1].split(
        "**Computed decision context"
    )[0]
    assert "trade_score=67.925" in scorecard_field
    assert "risk_score=35.0" in scorecard_field
    # the block is NOT left inside the bounded context as well
    ctx_field = prompt.split("**Computed decision context")[1]
    assert "trade_score=67.925" not in ctx_field
    # and the rest is still bounded (the header is followed by the bounded body)
    ctx_body = ctx_field.splitlines()[1] if len(ctx_field.splitlines()) > 1 else ""
    assert len(ctx_body) <= 3100, len(ctx_body)


def test_the_debate_prompt_is_unchanged_when_there_is_no_scorecard():
    """Gate off: no block on the context, so no new field and no reformatting."""
    from tradingagents.agents.researchers.structured_debate import build_turn_prompt

    state = {
        "computed_decision_context": "Computed regime gate: verdict=tradable pass=True",
        "asset_type": "stock",
        "trade_date": DATE,
    }
    prompt = build_turn_prompt(state, "bull", "bullish")
    assert "**Quant scorecard**" not in prompt
    assert "Computed regime gate: verdict=tradable pass=True" in prompt


def test_splitting_the_block_returns_the_rest_untouched():
    snap = _render(scores={"fundamental": 92.0})
    block = qs.format_quant_scorecard(snap)
    rest = "Computed regime gate: verdict=tradable"
    got_block, got_rest = qs.split_scorecard_block(f"{block}\n\n{rest}")
    assert got_block == block
    assert got_rest == rest
    # no block -> nothing is split, which is the gate-off case
    assert qs.split_scorecard_block(rest) == (None, rest)
    assert qs.split_scorecard_block("") == (None, "")


def test_the_block_prints_its_three_status_axes_and_names_the_engines():
    """§4.6: enablement, measurement and movement are printed, not inferred.

    The names come from the snapshot's own engine entries, so `trade` (the
    composite's own gate) is listed beside the drivers - it is one of the engines
    whose gate decides what the scorecard is.
    """
    snap = _render(
        scores={"fundamental": 92.0, "technical": 85.0, "risk": 35.0},
        enabled={"trade", "fundamental", "technical", "risk"},
        status="RESEARCH_ONLY",
    )
    text = qs.format_quant_scorecard(snap)
    assert (
        "Scorecard status: PARTIAL - enabled: fundamental, technical, risk, trade; "
        "disabled: regime, sentiment, news, event" in text
    )
    assert "Vector status: RESEARCH_ONLY" in text
    assert "Movement: UNAVAILABLE" in text


def test_a_fully_gated_and_measured_scorecard_reads_complete():
    """`COMPLETE` needs **every** engine gate on and every engine measured.

    §4.6's definition is deliberately strict: a scorecard with three engines
    switched off is `PARTIAL`, not complete-with-fewer-parts. That is what stops
    a half-configured run reading as a whole one (master rule 3).
    """
    every = {name: 50.0 for name in qs.ENGINE_GATES}
    every.update(
        {"fundamental": 92.0, "technical": 85.0, "regime": 78.0, "risk": 35.0}
    )
    snap = _render(
        scores=every, enabled=set(qs.ENGINE_GATES), status="RESEARCH_ONLY"
    )
    text = qs.format_quant_scorecard(snap)
    assert "Scorecard status: COMPLETE" in text
    assert "disabled: none" in text


def test_a_scorecard_with_engines_switched_off_is_partial_not_complete():
    """The same rule in the other direction - the case dark launch actually hits."""
    snap = _render(
        scores={
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        enabled={"trade", "fundamental", "technical", "regime", "risk"},
        status="RESEARCH_ONLY",
    )
    text = qs.format_quant_scorecard(snap)
    assert "Scorecard status: PARTIAL" in text
    assert "disabled: sentiment, news, event" in text


def test_an_enabled_engine_that_could_not_measure_makes_it_partial():
    """A half-measured scorecard must not read as a whole one (master rule 3)."""
    snap = _render(scores={"fundamental": 92.0})
    text = qs.format_quant_scorecard(snap)
    assert "Scorecard status: PARTIAL" in text


def test_the_status_lines_add_no_spurious_registry_keys():
    from tradingagents.agents.researchers.structured_debate import (
        _parse_key_value_lines,
    )

    snap = _render(
        scores={"trade": 70.0, "fundamental": 92.0},
        enabled={"trade", "fundamental"},
        status="RESEARCH_ONLY",
    )
    parsed = _parse_key_value_lines(qs.format_quant_scorecard(snap))
    assert set(parsed) == {"trade_score", "fundamental_score"}


def test_movement_is_unavailable_until_a_validated_vector_exists():
    """§4.3/§9 D2's hard invariant, as a printed default.

    `no validated vector -> no delta -> no movement`. The store is `P12-8`; until
    then the honest output is `UNAVAILABLE`, never a manufactured delta.
    """
    snap = _render(scores={"fundamental": 92.0}, status="RESEARCH_ONLY")
    assert qs.scorecard_status(snap)["movement"] == "UNAVAILABLE"
    assert "trade_delta" not in qs.format_quant_scorecard(snap)
    assert "trade_prev" not in qs.format_quant_scorecard(snap)


def test_the_card_gains_no_scorecard_key_when_the_gate_is_off():
    from tradingagents.reporting import _run_card_quant_scorecard

    snap = _render(scores={"fundamental": 92.0})
    assert _run_card_quant_scorecard({"quant_scorecard": snap}, {}) is None
    assert (
        _run_card_quant_scorecard(
            {"quant_scorecard": snap}, {"enable_quant_scorecard": False}
        )
        is None
    )


def test_the_card_key_carries_the_same_block_the_debate_read():
    """The gate-on card gains exactly one key, and its block is the prompt's block."""
    from tradingagents.reporting import _run_card_quant_scorecard

    every = {name: 50.0 for name in qs.ENGINE_GATES}
    every.update(
        {"fundamental": 92.0, "technical": 85.0, "regime": 78.0, "risk": 35.0}
    )
    snap = _render(
        scores=every,
        coverage={"trade": 0.95},
        enabled=set(qs.ENGINE_GATES),
        status="RESEARCH_ONLY",
    )
    block = _run_card_quant_scorecard(
        {"quant_scorecard": snap}, {"enable_quant_scorecard": True}
    )
    assert block is not None
    assert block["block"] == qs.format_quant_scorecard(snap)
    assert block["scorecard_status"] == "COMPLETE"
    assert block["engines"]["risk"]["score"] == 35.0
    # the same number the rendered block prints
    assert f"risk_score={block['engines']['risk']['score']}" in block["block"]


def test_gate_off_leaves_the_context_and_the_card_unchanged():
    """§9.3's release-level invariant, on the two surfaces it names.

    Not "the block is short enough" and not a test detail: with the gate off
    nothing about the existing surfaces may move. The strong form is that adding
    the block changes **nothing else** in the context, which is what the
    comparison below asserts.
    """
    import types

    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.reporting import _run_card_quant_scorecard

    stub = types.SimpleNamespace(
        config={"data_cache_dir": "C:/nonexistent-cache"},
        _try_fetch_closes=lambda ticker: [],
    )
    snapshot = _render(scores={"fundamental": 92.0}, status="RESEARCH_ONLY")
    gated = TradingAgentsGraph._compiled_decision_context(
        stub, "MSFT", {"quant_scorecard": snapshot}
    )
    ungated = TradingAgentsGraph._compiled_decision_context(stub, "MSFT", {})

    assert gated.startswith(qs.SCORECARD_HEADER)
    assert not ungated.startswith(qs.SCORECARD_HEADER)
    # everything after the block is byte-identical to the gate-off context
    assert gated.split("\n\n", 1)[1] == ungated
    # and the card gains no key at all (absent, not empty)
    assert _run_card_quant_scorecard({"quant_scorecard": snapshot}, {}) is None
    assert (
        _run_card_quant_scorecard(
            {"quant_scorecard": snapshot}, {"enable_quant_scorecard": False}
        )
        is None
    )


def test_the_debate_block_the_card_key_and_the_leaf_print_one_number():
    """The verification case the design adds to plan §11.3.

    *The debate's number and the report's number are the same number* — asserted
    in one run across the rendered block (`IVa`), the card key, and the leaf's
    rendered text. Three surfaces, one snapshot, so a disagreement here means a
    reader stopped using the producer.
    """
    from tradingagents.reporting import _run_card_quant_scorecard
    from tradingagents.strategies.trade_score import format_trade_score, trade_score

    snap = _render(
        scores={
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        coverage={"trade": 0.95, "risk": 0.45},
        status="RESEARCH_ONLY",
    )

    # 1. what the debate reads, and what section IVa renders
    block = qs.format_quant_scorecard(snap)
    # 2. what the card writes
    card_key = _run_card_quant_scorecard(
        {"quant_scorecard": snap}, {"enable_quant_scorecard": True}
    )
    # 3. what the tool leaf renders, from the same snapshot
    leaf_text = format_trade_score(
        trade_score(qs.engine_scores(snap)), ticker="MSFT"
    )

    composite = snap["engines"]["trade"]["score"]
    assert f"trade_score={composite}" in block
    assert card_key["block"] == block
    assert f"trade_score={composite}" in card_key["block"]
    # the leaf prints the same composite, from the same four values
    assert composite is not None
    leaf_composite = trade_score(qs.engine_scores(snap))["score"]
    assert leaf_composite == composite
    assert "Advisory only" in leaf_text
    # and the card's engines map is the leaf's input, value for value
    assert {
        name: card_key["engines"][name]["score"] for name in qs.COMPOSITE_ENGINES
    } == qs.engine_scores(snap)


def test_the_scorecard_explanation_is_a_new_field_and_basis_is_untouched():
    """§9 D3's invariant, as a test: a field `basis`'s consumer reads is `basis`.

    The scorecard explains itself in `scorecard_basis`. The composite's shipped
    `basis` string is not rewritten, not appended to, and not renamed.
    """
    from tradingagents.reporting import _run_card_quant_scorecard

    snap = _render(scores={"fundamental": 92.0}, status="RESEARCH_ONLY")
    card_key = _run_card_quant_scorecard(
        {"quant_scorecard": snap}, {"enable_quant_scorecard": True}
    )
    assert card_key["scorecard_basis"] == qs.SCORECARD_BASIS
    block = qs.format_quant_scorecard(snap)
    # the purpose IS on the new block surface (§4.1)...
    assert qs.SCORECARD_PURPOSE in block
    # ...while the field name itself belongs to the card, not the prompt
    assert "scorecard_basis" not in block
    # and the frozen negative-constraint wording is smuggled nowhere new
    assert "never an opportunity_score" not in card_key["scorecard_basis"]
    assert "never an opportunity_score" not in block
    assert "never a gate, never a size" not in card_key["scorecard_basis"]


def test_the_delta_is_printed_with_its_prior_date_and_adds_no_bogus_keys():
    """§4.3's delta, parse-safely.

    Two traps in the doc's own §4.3 example, both verified against the real
    parser: `trade_delta=+3.55` **never registers at all** (the number pattern is
    `-?\\d+`, so a leading `+` fails the match), and `trade_prev_date=2026-09-11`
    registers as **`trade_prev_date = 2026`** — a year under a name that reads
    like a metric. The sign is therefore carried by the absence of `-`, and the
    date is parenthesised so it yields no key.
    """
    from tradingagents.agents.researchers.structured_debate import (
        _parse_key_value_lines,
    )

    snap = _render(
        scores={
            "fundamental": 92.0,
            "technical": 85.0,
            "regime": 78.0,
            "risk": 35.0,
        },
        status="VALIDATED",
    )
    snap["movement"] = {
        "movement": "AVAILABLE",
        "reason": None,
        "prev": 73.20,
        "prev_date": "2026-09-11",
        "delta": 3.55,
    }
    text = qs.format_quant_scorecard(snap)

    assert "trade_prev=73.2" in text
    assert "trade_delta=3.55" in text
    assert "prior observation (2026-09-11)" in text
    assert "Movement: AVAILABLE" in text

    parsed = _parse_key_value_lines(text)
    assert parsed["trade_delta"] == 3.55
    assert parsed["trade_prev"] == 73.2
    # the two traps this format exists to avoid
    assert "trade_prev_date" not in parsed
    assert "prior_observation" not in parsed


def test_a_falling_delta_keeps_its_sign():
    snap = _render(scores={"trade": 76.75, "fundamental": 92.0}, status="VALIDATED")
    snap["movement"] = {
        "movement": "AVAILABLE",
        "reason": None,
        "prev": 91.0,
        "prev_date": "2026-09-11",
        "delta": -14.25,
    }
    text = qs.format_quant_scorecard(snap)
    assert "trade_delta=-14.25" in text
    from tradingagents.agents.researchers.structured_debate import (
        _parse_key_value_lines,
    )

    assert _parse_key_value_lines(text)["trade_delta"] == -14.25


def test_an_unavailable_movement_prints_no_delta_keys_at_all():
    """`NA` rules: no prior row means no keys, never a zero."""
    snap = _render(scores={"fundamental": 92.0}, status="RESEARCH_ONLY")
    snap["movement"] = {
        "movement": "UNAVAILABLE",
        "reason": "the weight vector is not validated yet",
        "prev": None,
        "prev_date": None,
        "delta": None,
    }
    text = qs.format_quant_scorecard(snap)
    assert "trade_delta" not in text
    assert "trade_prev" not in text
    assert "Movement: UNAVAILABLE" in text


def test_the_block_is_bounded_even_with_every_engine_absent():
    """Every engine enabled, none able to measure: `NA` everywhere, nothing numeric."""
    from tradingagents.agents.researchers.structured_debate import (
        _parse_key_value_lines,
    )

    snap = _render(scores={"trade": None}, enabled=set(qs.ENGINE_GATES))
    text = qs.format_quant_scorecard(snap)
    assert len(text) <= qs.SCORECARD_MAX_CHARS
    # every score is NA, so the parser finds no number at all — and no bogus key
    assert _parse_key_value_lines(text) == {}
    assert "trade_score=NA" in text
    assert "risk_score=NA" in text
    # no absence is ever rendered as a zero
    assert "=0 " not in text and not text.rstrip().endswith("=0")
    assert "score=0" not in text
