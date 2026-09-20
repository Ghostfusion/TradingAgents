"""The Decision Packet (design doc §6-§8, Phase 2).

What is pinned here is **behaviour a consumer observes**, not the render's
wording: the gate contract, the four categories staying distinct, the uncertainty
counter's DISABLED/NA discipline, the budget's structural truncation, and the
purity that makes the packet safe to render before the graph.

The gate's own registration (DEFAULT_CONFIG / `_ENV_OVERRIDES` / the registry doc
/ `.env.example` / flippability) is enforced by `tests/test_gate_env_toggles.py`;
it is not duplicated here.
"""

from __future__ import annotations

import copy
import re

import pytest

from tradingagents.strategies.decision_packet import (
    CATEGORY_EVIDENCE,
    CATEGORY_RISK_CONSTRAINTS,
    CATEGORY_SYNTHESIS,
    DECISION_PACKET_BUDGET,
    DECISION_PACKET_KEY,
    PACKET_MAX_CHARS,
    PACKET_TRUNCATION_PREFIX,
    PACKET_VERSION,
    decision_packet_or_context,
    packet_facts,
    render_decision_packet,
    uncertainty_read,
)


def _engine(name, *, enabled=True, score=None, coverage=None, reason=None, result=None):
    """One scorecard engine entry in the shape `quant_scorecard._entry` emits."""
    return {
        "engine": name,
        "gate": f"enable_{name}_score",
        "enabled": enabled,
        "state": ("MEASURED" if score is not None else ("DISABLED" if not enabled else "NA")),
        "score": score,
        "coverage": coverage,
        "band": None,
        "reason": reason,
        "result": result,
    }


def _snapshot(engines: dict) -> dict:
    return {"ticker": "TEST", "trade_date": "2026-01-02", "engines": engines}


def _state(**over):
    state = {
        "company_of_interest": "test",
        "trade_date": "2026-01-02",
        "computed_decision_context": "Computed decision context: the legacy string.",
    }
    state.update(over)
    return state


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_gate_off_returns_the_compiled_context_byte_for_byte():
    """Acceptance criterion 1: gate off ⇒ byte-identical output.

    The consumer sites all read `computed_decision_context` through this one
    function, so this is the whole of the gate-off contract.
    """
    legacy = "Computed regime gate (mean-reversion entry): verdict=tradable pass=True\nplan card ..."
    state = _state(computed_decision_context=legacy)
    assert decision_packet_or_context(state, {}) == legacy
    assert decision_packet_or_context(state, {"enable_decision_packet": False}) == legacy
    # ...and it is the SAME OBJECT's text, not a re-render that happens to match.
    assert decision_packet_or_context(state, {}) == state["computed_decision_context"]


def test_gate_on_returns_the_stored_packet_not_a_re_render():
    """One producer of the packet string: the graph renders, the consumers read."""
    state = _state(**{DECISION_PACKET_KEY: "DECISION PACKET v1 - TEST - 2026-01-02\nSENTINEL"})
    out = decision_packet_or_context(state, {"enable_decision_packet": True})
    assert "SENTINEL" in out
    assert state["computed_decision_context"] not in out


def test_gate_on_with_no_packet_rendered_is_an_explicit_defect_not_a_fallback():
    """A broken packet must not look like a working gate-off run.

    Silently falling back to `computed_decision_context` would hide a wiring
    defect behind plausible output - the failure mode the design doc exists to
    catch. The reader must be able to tell.
    """
    state = _state()
    out = decision_packet_or_context(state, {"enable_decision_packet": True})
    assert "UNAVAILABLE" in out
    assert state["computed_decision_context"] not in out
    assert DECISION_PACKET_KEY in out
    # no doubled version prefix
    assert "vv1" not in out


# ---------------------------------------------------------------------------
# §6: the four categories stay distinct, and there is no DECISION line
# ---------------------------------------------------------------------------


def test_packet_carries_no_decision_line():
    """Criterion 11: the packet does not instruct.

    The header legitimately names the packet; what must never appear is a line
    stating a decision. So the invariant is that ``DECISION`` opens no line
    except the header.
    """
    text = render_decision_packet(_state(), {})
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DECISION"):
            assert stripped.upper().startswith("DECISION PACKET "), stripped
    # ...and no rating vocabulary is asserted anywhere in the block
    for token in ("=Buy", "=Sell", "=Overweight", "=Underweight", "RECOMMEND"):
        assert token not in text


def test_the_four_categories_are_visually_distinct_and_constraints_are_not_evidence():
    """Criterion 18: `constraints != evidence != synthesis != decision`.

    `permission` must sit under RISK CONSTRAINTS - listed among engine scores it
    would resemble one more bullish input, which is the whole reason §6 moved it.
    """
    state = _state(
        quant_scorecard=_snapshot({"fundamental": _engine("fundamental", score=67.7)}),
    )
    text = render_decision_packet(state, {})
    order = [
        text.index(CATEGORY_RISK_CONSTRAINTS),
        text.index(CATEGORY_EVIDENCE),
        text.index(CATEGORY_SYNTHESIS),
        text.index("TRADE PARAMETERS"),
        text.index("FALSIFIERS"),
    ]
    assert order == sorted(order), "the §6 block order is not preserved"
    assert text.index("permission") < text.index(CATEGORY_EVIDENCE)
    assert text.index("permission") > text.index(CATEGORY_RISK_CONSTRAINTS)
    # each category states what it is
    assert "not evidence" in text
    assert "research evidence" in text


def test_a_directional_distribution_is_named_absent_rather_than_fabricated():
    """§6's distribution row has NO valid producer, and the packet says so.

    The engines carry no directional sign (`score_engine.align` erases it), and
    the independent stances may not enter as evidence (§4.4, criterion 22). A
    fabricated `bullish=` would present a diagnostics stream as evidence.
    """
    state = _state(
        quant_scorecard=_snapshot({"fundamental": _engine("fundamental", score=67.7)}),
        risk_independent_stances={"aggressive": {"rating": "Buy"}, "neutral": {"rating": "Sell"}},
    )
    text = render_decision_packet(state, {})
    assert "DIRECTIONAL DISTRIBUTION" in text
    assert "unavailable_pre_producer" in text
    assert "bullish=" not in text
    assert "bearish=" not in text


# ---------------------------------------------------------------------------
# §8: the uncertainty counter
# ---------------------------------------------------------------------------


def test_an_enabled_engine_that_cannot_measure_is_a_named_gap():
    snap = _snapshot(
        {
            "fundamental": _engine("fundamental", score=67.7),
            "event": _engine("event", reason="the catalyst snapshot is stamped after the graph"),
        }
    )
    unc = uncertainty_read(snap)
    assert unc["count"] == 1
    assert "event" in unc["gaps"][0]
    assert "catalyst snapshot" in unc["gaps"][0]


def test_a_gated_off_engine_is_not_a_gap():
    """The DISABLED / NA distinction, which is what makes PARTIAL meaningful.

    Counting an intentionally-off engine as missing evidence would make a
    partly-gated run read as a run full of gaps.
    """
    off = _snapshot(
        {
            "fundamental": _engine("fundamental", score=67.7),
            "news": _engine("news", enabled=False, reason="enable_news_score is off"),
        }
    )
    assert uncertainty_read(off)["count"] == 0

    on = _snapshot(
        {
            "fundamental": _engine("fundamental", score=67.7),
            "news": _engine("news", reason="no news rows in window"),
        }
    )
    assert uncertainty_read(on)["count"] == 1


def test_component_gaps_come_from_the_engine_that_declares_them():
    """`news_score` names its own absent components and the reasons for them."""
    snap = _snapshot(
        {
            "news": _engine(
                "news",
                score=57.6,
                result={"absent_reasons": {"sentiment_leg": "no labelled messages"}},
            )
        }
    )
    unc = uncertainty_read(snap)
    assert unc["count"] == 1
    assert "news.sentiment_leg" in unc["gaps"][0]
    assert "no labelled messages" in unc["gaps"][0]


def test_uncertainty_never_renders_as_a_directional_fact():
    """Criterion 6: an uncertainty is not a bearish fact.

    The invariant is asserted on the output, not the prompt text: an added
    unmeasured engine grows the UNCERTAINTY count and produces no bearish count
    anywhere in the packet.
    """
    base = {"fundamental": _engine("fundamental", score=67.7)}
    grown = dict(base)
    grown["event"] = _engine("event", reason="catalyst snapshot absent")

    before = render_decision_packet(_state(quant_scorecard=_snapshot(base)), {})
    after = render_decision_packet(_state(quant_scorecard=_snapshot(grown)), {})
    assert "0 named gaps" in before
    assert "1 named gaps" in after
    assert "bearish=" not in after


def test_no_snapshot_is_not_the_claim_that_every_engine_measured():
    text = render_decision_packet(_state(), {})
    assert "every enabled engine measured" not in text
    assert "unavailable_pre_scorecard" in text


# ---------------------------------------------------------------------------
# §6 rule 1: no number without its coverage or a named gap
# ---------------------------------------------------------------------------


def test_an_unmeasured_engine_prints_na_and_never_zero():
    snap = _snapshot(
        {
            "fundamental": _engine("fundamental", score=0.0, coverage=1.0),
            "risk": _engine("risk", reason="no components measured"),
            "news": _engine("news", enabled=False),
        }
    )
    text = render_decision_packet(_state(quant_scorecard=snap), {})
    assert "risk=NA" in text
    # a measured 0.0 is the engine's number and must survive as itself
    assert "fundamental=0.0" in text
    # a gated-off engine is not part of the scorecard at all
    assert "news=" not in text


def test_every_engine_row_carries_its_coverage_when_it_has_one():
    snap = _snapshot({"technical": _engine("technical", score=62.29, coverage=0.95)})
    text = render_decision_packet(_state(quant_scorecard=snap), {})
    assert "technical=62.29 [cov 0.95]" in text


# ---------------------------------------------------------------------------
# §7: the budget
# ---------------------------------------------------------------------------


def test_the_packet_fits_its_budget():
    assert packet_facts(render_decision_packet(_state(), {}))["packet_chars"] <= PACKET_MAX_CHARS


def test_an_oversized_packet_drops_whole_rows_and_says_so():
    """§7: truncation is visible and counted, never silent.

    The composite's `basis` is an engine-authored string of unbounded length, so
    it is the row that can genuinely blow the packet budget. The marker's count
    must match the number of rows that actually disappeared, and the structural
    elements - header, headings, category notes - must survive.
    """
    snap = _snapshot(
        {
            "fundamental": _engine("fundamental", score=67.7),
            "trade": _engine(
                "trade",
                score=70.6,
                coverage=1.0,
                result={"floor": 2, "basis": "B" * 20_000},
            ),
        }
    )
    text = render_decision_packet(_state(quant_scorecard=snap), {})

    assert PACKET_TRUNCATION_PREFIX in text
    assert len(text) <= PACKET_MAX_CHARS + len(PACKET_TRUNCATION_PREFIX) + 20
    match = re.search(
        re.escape(PACKET_TRUNCATION_PREFIX) + r"(\d+) rows dropped\]", text
    )
    assert match is not None, "the truncation marker has no count"
    assert int(match.group(1)) > 0
    # structural truncation: header, every heading and every note survives
    assert text.startswith("DECISION PACKET " + PACKET_VERSION)
    for heading in (
        CATEGORY_RISK_CONSTRAINTS,
        CATEGORY_EVIDENCE,
        CATEGORY_SYNTHESIS,
        "TRADE PARAMETERS",
        "FALSIFIERS",
    ):
        assert heading in text
    assert "not evidence" in text
    # a row that was NOT dropped still carries its full number and label
    assert "fundamental=67.7" in text


def test_the_engine_row_bound_is_met_by_dropping_whole_cells():
    """§7's `engine_row_max_chars` is enforced, and never by cutting a number.

    Every surviving cell must still read `name=value`; a truncated cell would be
    a number without its label.
    """
    engines = {
        name: _engine(name, score=60.0 + i, coverage=0.5 + i / 100)
        for i, name in enumerate(
            ("fundamental", "technical", "regime", "risk", "sentiment", "news", "event", "trade")
        )
    }
    text = render_decision_packet(_state(quant_scorecard=_snapshot(engines)), {})
    row = next(ln for ln in text.splitlines() if ln.startswith("engines"))
    assert len(row) <= DECISION_PACKET_BUDGET["engine_row_max_chars"]
    assert "engines not shown - row budget" in row
    for cell in row.split("  ")[1:]:
        if "=" not in cell:
            continue
        name, _, value = cell.partition("=")
        assert name, cell
        assert re.match(r"^-?\d", value), cell


# ---------------------------------------------------------------------------
# §6 rule 2: the packet is a pure function
# ---------------------------------------------------------------------------


def test_render_is_pure_and_does_not_mutate_state():
    state = _state(
        quant_scorecard=_snapshot({"fundamental": _engine("fundamental", score=67.7)}),
        risk_context={"book_drawdown": 0.072, "drawdown_limit": 0.10},
    )
    before = copy.deepcopy(state)
    first = render_decision_packet(state, {"enable_quant_scorecard": True})
    second = render_decision_packet(state, {"enable_quant_scorecard": True})
    assert first == second
    assert state == before


def test_packet_facts_reports_absence_as_null_never_zero():
    """§13.1 finding 3's rule: a counter that cannot be taken is null, not 0."""
    assert packet_facts(None) == {
        "packet_version": None,
        "packet_chars": None,
        "packet_truncated": None,
    }
    assert packet_facts("") == {
        "packet_version": None,
        "packet_chars": None,
        "packet_truncated": None,
    }


def test_packet_facts_measures_the_text_it_is_given():
    text = render_decision_packet(_state(), {})
    facts = packet_facts(text)
    assert facts["packet_chars"] == len(text)
    assert facts["packet_version"] == PACKET_VERSION
    assert facts["packet_truncated"] is False


def test_the_declared_budget_keys_are_the_ones_the_doc_specifies():
    """§7's budget is a contract, so a silent edit to it is a contract change.

    `conflict_row_max_chars` (Phase 3) bounds one ledger row the same way
    `engine_row_max_chars` bounds the engines row: a declared bound that does
    nothing is the defect class `engine_row_max_chars` itself was caught by.
    """
    assert DECISION_PACKET_BUDGET == {
        "packet_max_chars": 12_000,
        "engine_row_max_chars": 160,
        "conflict_max_rows": 12,
        "conflict_row_max_chars": 200,
        "falsifier_max_rows": 8,
    }


# ---------------------------------------------------------------------------
# The falsifiers come from their one producer
# ---------------------------------------------------------------------------


def test_falsifiers_render_the_producers_own_conditions():
    """`report_disclosure.invalidation_conditions` is the decision-artifact rule.

    The packet reads it rather than restating the conditions, so the prompt and
    `research_decision.json` cannot disagree. With no plan measurable the
    producer's own honest fallback is what appears.
    """
    text = render_decision_packet(_state(), {})
    assert "conditions  1 declared" in text
    assert "manual:thesis_reassessment" in text


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path",
    [
        "tradingagents/agents/trader/trader.py",
        "tradingagents/agents/managers/portfolio_manager.py",
        "tradingagents/agents/risk_mgmt/aggressive_debator.py",
        "tradingagents/agents/risk_mgmt/conservative_debator.py",
        "tradingagents/agents/risk_mgmt/neutral_debator.py",
    ],
)
def test_every_decision_consumer_reads_the_context_through_the_gate(module_path):
    """§6 names the consumers: the trader, the PM and the three risk debators.

    A consumer that reads `computed_decision_context` directly bypasses the gate
    and would keep receiving the unbounded context with the packet on. This is a
    source check because the contract IS "which function this site calls" - the
    same shape `test_calc_agent_wiring` uses for its bindings.
    """
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    src = (repo / module_path).read_text(encoding="utf-8")
    assert "decision_packet_or_context(" in src, f"{module_path} bypasses the packet gate"
    assert 'state.get("computed_decision_context")' not in src, (
        f"{module_path} still reads the compiled context directly"
    )


def test_the_run_card_is_unchanged_when_the_gate_is_off():
    """Criterion 1, on the CARD and not just the prompt.

    Phase 0's card recorded `context_mode: None` and no `packet_chars` key. A
    gate-off run must still record exactly that: adding a `packet_chars` key or
    writing a mode would alter the card on a run where the packet does not exist.
    The release invariant is stronger than "the prompt is unchanged".
    """
    from tradingagents.reporting import _run_card_decision_context

    state = _state(quant_scorecard=_snapshot({"fundamental": _engine("fundamental", score=67.7)}))
    off = _run_card_decision_context(state, {})
    assert off["context"]["context_mode"] is None
    assert off["context"]["packet_version"] is None
    assert off["context"]["packet_truncated"] is None
    assert "packet_chars" not in off

    packet = render_decision_packet(state, {})
    on = _run_card_decision_context(
        {**state, DECISION_PACKET_KEY: packet},
        {"enable_decision_packet": True},
    )
    assert on["context"]["context_mode"] == "packet"
    assert on["context"]["packet_version"] == PACKET_VERSION
    assert on["context"]["packet_truncated"] is False
    # the measurement describes the string the GRAPH stored - the block the
    # model read - not a fresh render
    assert on["packet_chars"] == len(packet)


def test_the_packet_state_key_is_declared_in_agent_state():
    """Native LangGraph SILENTLY DROPS undeclared keys.

    An undeclared `decision_packet` would vanish between the render and the
    consumer, and every consumer would then report the wiring defect - a silent
    failure that looks like a gate problem.
    """
    from tradingagents.agents.utils.agent_states import AgentState

    assert DECISION_PACKET_KEY in AgentState.__annotations__


# ---------------------------------------------------------------------------
# Phase 3 (§9) - the conflict ledger
# ---------------------------------------------------------------------------

#: A report that asserts ONE metric at two values where one side states its
#: basis and the other does not - §9's `unresolved`, the only class §10 may act
#: on, and therefore the row the ledger exists to surface.
_UNRESOLVED_REPORT = (
    "## Ratios\n"
    "get_ratios reports EV/EBIT 5.50 on the ratios table (ttm:ttm basis).\n"
    "## Analyst verdict\n"
    "EV/EBIT of 4.40 implies the name is cheap.\n"
)


def test_the_ledger_renders_the_in_run_reports():
    """§9's CONFLICT row carries the metric, both values, the class and the section."""
    text = render_decision_packet(
        _state(fundamentals_report=_UNRESOLVED_REPORT), {}, closes=[]
    )
    assert "unavailable_pre_ledger" not in text
    assert "unavailable_pre_reports" not in text
    assert "[unresolved]" in text
    assert "ev/ebit" in text
    assert "5.5" in text and "4.4" in text
    assert "section: fundamentals" in text
    assert "1 unresolved" in text


def test_no_reports_yet_is_a_named_gap_and_never_a_zero():
    """A render before the analysts ran must not claim zero disagreements.

    `0 unresolved` reads as a measurement nobody made - the D-11 failure. The
    packet distinguishes "no report in state" from "reports read, nothing
    disagreed", which are different facts.
    """
    text = render_decision_packet(_state(), {}, closes=[])
    assert "unavailable_pre_reports" in text
    assert "0 unresolved" not in text


def test_reports_that_agree_render_a_real_zero():
    """The other half of the pair: a measured zero IS printed as a zero."""
    text = render_decision_packet(
        _state(fundamentals_report="## Ratios\nget_ratios reports EV/EBIT 5.50.\n"),
        {},
        closes=[],
    )
    assert "0 unresolved" in text
    assert "no same-metric disagreement found" in text


def test_the_ledger_prints_the_actionable_class_first_and_truncates_its_tail():
    """A bounded ledger must not hide the one row the model can act on.

    The measured distribution is dominated by `basis_difference` (199 of 284 rows
    over 53 trees), so truncating in metric order would routinely drop the single
    `unresolved` row behind twelve inert ones. The unresolved row survives.
    """
    # Thirteen real registry metrics, each a basis_difference (two producers),
    # plus one unresolved pair. `conflict_max_rows` is 12, so a tail must drop.
    pairs = [
        ("market cap", "market cap $87.8B", "market cap 91.4"),
        ("roe", "ROE 53.92%", "ROE 59.77%"),
        ("debt/equity", "debt/equity 0.41", "debt/equity 0.63"),
        ("book value", "book value 12.10", "book value 14.80"),
        ("dividend yield", "dividend yield 1.10%", "dividend yield 2.40%"),
        ("eps ttm", "EPS TTM 7.04", "EPS TTM 8.11"),
        ("diluted eps", "diluted EPS 3.10", "diluted EPS 4.55"),
        ("eps actual", "EPS actual 7.04", "EPS actual 7.90"),
        ("earnings power value", "earnings power value 14.20", "earnings power value 19.60"),
        ("insider net", "insider net $1.2M", "insider net $9.4M"),
        ("200-day sma", "200-day SMA 101.20", "200-day SMA 118.60"),
        ("ema20", "EMA 20 trail 54.66", "EMA 20 trail 61.90"),
        ("dcf fair value", "DCF fair value 25.92", "DCF fair value 34.59"),
    ]
    lines: list[str] = []
    for _, a, b in pairs:
        lines.append(f"get_ratios reports {a}.")
        lines.append(f"get_fundamentals reports {b}.")
    lines.append("get_ratios reports EV/EBIT 5.50 on the ratios table (ttm:ttm basis).")
    lines.append("EV/EBIT of 4.40 implies the name is cheap.")
    text = render_decision_packet(
        _state(fundamentals_report="\n".join(lines)), {}, closes=[]
    )
    assert "1 unresolved" in text
    assert "[unresolved]" in text
    assert "ev/ebit" in text
    assert "more disagreements not shown" in text


def test_the_in_run_ledger_and_the_tree_pass_are_one_producer():
    """Rule 15: the same functions produce both, so the two cannot disagree.

    `verify_report_dir` runs post-hoc over the saved tree; the packet's ledger is
    built in-run from the same report text. They must agree row for row, or a
    reader would see two different conflict lists for one run.
    """
    from tradingagents.agents.utils.report_verifier import (
        _basis_registry,
        basis_conflicts,
        report_ledger,
    )

    state = _state(fundamentals_report=_UNRESOLVED_REPORT)
    in_run, stems = report_ledger(state)
    tree = basis_conflicts(_basis_registry(_UNRESOLVED_REPORT, set()), section="fundamentals")
    assert stems == 1
    assert [(r.metric, r.classification, r.section) for r in in_run] == [
        (r.metric, r.classification, r.section) for r in tree
    ]


def test_the_card_counts_the_ledger_only_when_the_packet_is_on():
    """The count is real when the ledger ran, and null-with-a-reason when it did not.

    `0` for a gate-off run would read as "no conflicts were found" when the truth
    is "nothing counted them".
    """
    from tradingagents.reporting import _run_card_evidence_counts

    state = _state(fundamentals_report=_UNRESOLVED_REPORT)
    on = _run_card_evidence_counts(state, {"enable_decision_packet": True})
    assert on["conflict_count"] == 1
    assert on["conflict_counts"]["unresolved"] == 1
    assert on["conflict_reports_read"] == 1

    off = _run_card_evidence_counts(state, {"enable_decision_packet": False})
    assert off["conflict_count"] is None
    assert "enable_decision_packet" in off["conflict_count_reason"]


# ---------------------------------------------------------------------------
# Phase 4 (§11) - conditional expansion
# ---------------------------------------------------------------------------


def _divided_state(**over):
    """A state whose independent reads disagree - §11's "agreement low" branch."""
    state = _state(
        risk_independent_stances={
            "aggressive": {"rating": "Buy"},
            "conservative": {"rating": "Sell"},
            "neutral": {"rating": "Hold"},
        },
    )
    state.setdefault("fundamentals_report", _UNRESOLVED_REPORT)
    state.update(over)
    return state


def test_a_divided_book_triggers_expansion_and_a_missing_input_does_not():
    """§11's trigger, and the rule that absence is not agreement."""
    from tradingagents.strategies.decision_packet import expansion_decision

    divided = expansion_decision(_divided_state(), {})
    assert divided["expand"] is True
    assert divided["independent_agreement"] == 0.0
    assert divided["should_hold"] is True
    assert divided["unresolved_conflicts"] == 1

    # No stance sampled and nothing conflicting: nothing measured the division,
    # so it cannot count toward agreement OR toward expansion.
    empty = expansion_decision(
        _state(fundamentals_report="## Ratios\nget_ratios reports EV/EBIT 5.50.\n"), {}
    )
    assert empty["expand"] is False
    assert empty["measured"] is False
    assert "no independent stance sampled" in empty["reason"]


def test_an_agreed_book_does_not_expand():
    """The other branch of §11's diagram, so the trigger is not always-on."""
    from tradingagents.strategies.decision_packet import expansion_decision

    agreed = expansion_decision(
        _state(
            risk_independent_stances={
                "aggressive": {"rating": "Buy"},
                "conservative": {"rating": "Buy"},
                "neutral": {"rating": "Buy"},
            },
            fundamentals_report="## Ratios\nget_ratios reports EV/EBIT 5.50.\n",
        ),
        {},
    )
    assert agreed["expand"] is False
    assert agreed["independent_agreement"] == 1.0


def test_expansion_attaches_named_sections_and_is_bounded():
    """§11: additive and bounded - whole named sections, never a half-attached one."""
    from tradingagents.strategies.decision_packet import (
        CONTEXT_EXPANSION_BUDGET,
        EXPANSION_HEADER,
        render_expansion,
    )

    long_report = "\n".join(f"line {i} of the report" for i in range(4000))
    text = render_expansion(_divided_state(fundamentals_report=long_report), {})
    assert text.startswith(EXPANSION_HEADER)
    assert "## fundamentals" in text
    assert "expansion budget" in text
    assert len(text) <= CONTEXT_EXPANSION_BUDGET["expansion_max_chars"]


def test_the_expansion_is_a_separate_channel_so_packet_chars_still_measures_the_packet():
    """§7's bound must keep meaning the DECISION channel, not the expansion.

    Appending the research to the packet's own string would make `packet_chars`
    grow with the research, and §7's bound would stop being a bound.
    """
    from tradingagents.strategies.decision_packet import (
        DECISION_EXPANSION_KEY,
        create_decision_packet_node,
    )

    state = _divided_state()
    cfg = {"enable_decision_packet": True, "enable_context_expansion": True}
    out = create_decision_packet_node(cfg)(state)
    assert DECISION_EXPANSION_KEY in out
    facts = packet_facts(out[DECISION_PACKET_KEY])
    assert facts["packet_chars"] == len(out[DECISION_PACKET_KEY])
    assert facts["packet_chars"] <= PACKET_MAX_CHARS
    # the consumer still reads ONE string
    context = decision_packet_or_context({**state, **out}, cfg)
    assert context.startswith(out[DECISION_PACKET_KEY])
    assert out[DECISION_EXPANSION_KEY] in context


def test_context_mode_is_packet_when_the_expansion_gate_is_off():
    """§11 records the mode, so the expansion rate is measurable."""
    from tradingagents.reporting import _run_card_decision_context
    from tradingagents.strategies.decision_packet import create_decision_packet_node

    state = _divided_state()
    packet = create_decision_packet_node({"enable_decision_packet": True})(state)[
        DECISION_PACKET_KEY
    ]
    off = _run_card_decision_context(
        {**state, DECISION_PACKET_KEY: packet},
        {"enable_decision_packet": True, "enable_context_expansion": False},
    )
    assert off["context"]["context_mode"] == "packet"
    assert "expansion_chars" not in off

    on_state = create_decision_packet_node(
        {"enable_decision_packet": True, "enable_context_expansion": True}
    )(state)
    on = _run_card_decision_context(
        {**state, **on_state},
        {"enable_decision_packet": True, "enable_context_expansion": True},
    )
    assert on["context"]["context_mode"] == "packet+expanded"
    assert on["expansion_chars"] > 0
