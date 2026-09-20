"""The Decision Packet (design doc §6-§8, Phase 2).

The decision model receives **one bounded, deterministic block**. Nothing else
about the trade is in the prompt.

**The packet constrains the information channel, not the decision.** A block
printing ``AGREEMENT 7/8`` beside ``COMPOSITE 82`` invites the model to compute
``7/8 bullish -> BUY`` instead of forming an independent judgement. The packet
therefore reports **evidence**, never a recommendation, and it carries **no
``DECISION`` line**.

Four semantic categories, kept visually distinct:
``constraints != evidence != synthesis != decision``.

Two contracts are load-bearing and each is tested:

* **The packet is a pure function of state** - no model call, no vendor call, no
  state mutation. The same state always renders the same string.
* **Every number carries its coverage or a named gap** - never a bare number,
  and ``NA`` never ``0``.

**A row whose producer has not run is a NAMED GAP, never a default.** The packet
is rendered at several points in the graph (the Trader runs before the risk
stances are sampled; the risk gate runs after the decision), and §16's own
architecture puts the deterministic gates *downstream* of the decision. So a
pre-decision render cannot carry a post-decision fact. This module names that
axis ``unavailable_pre_<stage>`` rather than asserting a plausible default -
the same discipline ``regime_gate_read`` already applies to its ``catalyst_window``
tri-state (D-11: the pre-graph context holds no event fact, so it says so).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "CATEGORY_EVIDENCE",
    "CATEGORY_RISK_CONSTRAINTS",
    "CATEGORY_SYNTHESIS",
    "CONFLICT_CLASS_ORDER",
    "CONTEXT_EXPANSION_BUDGET",
    "DECISION_EXPANSION_KEY",
    "DECISION_PACKET_BUDGET",
    "DECISION_PACKET_CLOSES_KEY",
    "DECISION_PACKET_KEY",
    "DECISION_PACKET_NODE",
    "EXPANSION_AGREEMENT_FLOOR",
    "EXPANSION_HEADER",
    "PACKET_MAX_CHARS",
    "PACKET_TRUNCATION_PREFIX",
    "PACKET_VERSION",
    "create_decision_packet_node",
    "decision_packet_or_context",
    "expansion_decision",
    "expansion_facts",
    "packet_facts",
    "render_decision_packet",
    "render_expansion",
    "stage_gap",
    "uncertainty_read",
]

#: The state key the graph renders the packet into. Declared in
#: ``agent_states.AgentState`` - native LangGraph SILENTLY DROPS undeclared keys
#: (docs/AGENT_ONBOARDING.md, 2026-08-28). Written only when the gate is on, so a
#: gate-off run gains no key and stays byte-identical.
DECISION_PACKET_KEY = "decision_packet"

#: The packet's own version. Recorded per run, so a later reader can tell which
#: packet shape a decision was made from.
PACKET_VERSION = "v1"

#: §7's budget. **Measurement is the point**: ``packet_chars`` is written into
#: ``run_card.json`` so the bound is observable per run - today no such
#: measurement exists for any prompt.
DECISION_PACKET_BUDGET: dict[str, int] = {
    "packet_max_chars": 12_000,  # ~3,000 tokens
    "engine_row_max_chars": 160,
    "conflict_max_rows": 12,
    "conflict_row_max_chars": 200,
    "falsifier_max_rows": 8,
}
PACKET_MAX_CHARS: int = DECISION_PACKET_BUDGET["packet_max_chars"]

#: The conflict classes, most actionable first. §10 may act on ``unresolved``
#: alone and §9 calls ``defect`` the ledger's signal-to-noise, so the ledger
#: prints in this order and truncates from the tail: a run whose twelve rows were
#: twelve `basis_difference`s would hide the one row that matters.
CONFLICT_CLASS_ORDER = ("unresolved", "defect", "basis_difference")

#: The marker appended when rows are dropped. Visible and counted, never silent
#: (§7, and the risk table's "the budget silently truncates a decisive row").
PACKET_TRUNCATION_PREFIX = "[packet truncated: "

#: The first line. It states what the block is, in the same spirit as
#: ``quant_scorecard.SCORECARD_HEADER``.
PACKET_HEADER = "DECISION PACKET {version} - {ticker} - {date}"

#: The purpose line. **English only, and digit-free**: the L1 registry parses
#: ``key=value`` pairs out of this context for citable ground truth, and a digit
#: after a word is a key the parser will invent (the ordering rule
#: ``quant_scorecard.format_quant_scorecard`` already documents).
PACKET_PURPOSE = (
    "Purpose: the bounded, deterministic decision context - research evidence and "
    "decision-domain constraints, for adjudication. Not an order, not a "
    "recommendation and not a gate."
)

CATEGORY_RISK_CONSTRAINTS = "RISK CONSTRAINTS"
CATEGORY_EVIDENCE = "EVIDENCE"
CATEGORY_SYNTHESIS = "SYNTHESIS"

#: What each category IS, printed under its heading so the distinction survives
#: even when a reader skims. §6 rule 5: ``ENGINE EVIDENCE``, ``DIRECTIONAL
#: DISTRIBUTION``, ``CONSENSUS`` and ``COMPOSITE`` are all research evidence.
_CATEGORY_NOTE = {
    CATEGORY_RISK_CONSTRAINTS: (
        "not evidence - a decision-domain constraint the model reasons WITHIN"
    ),
    CATEGORY_EVIDENCE: "research evidence",
    CATEGORY_SYNTHESIS: (
        "downstream synthesis - not a recommendation, and the consensus line is a "
        "DIAGNOSTIC over independent reads, not evidence (design doc §4.4)"
    ),
    "TRADE PARAMETERS": "the measured plan, when a plan is measurable",
    "FALSIFIERS": "the invalidation conditions this thesis is subject to",
}

#: §6 rule 4: the packet carries no ``DECISION`` line. Asserted by test, so a
#: later edit cannot quietly add one.
FORBIDDEN_LINE_PREFIXES = ("DECISION",)

#: Every block heading the packet can print, in the order
#: ``render_decision_packet`` emits them. ``_CATEGORY_NOTE`` is the same registry
#: (``_assemble`` indexes it for every block), so a new block cannot be added
#: without appearing here - and a reader that needs to know where one block ENDS
#: has one list to read rather than a guess about indentation. The packet's rows
#: are NOT indented (``conditions  1 declared`` sits at column zero); only the
#: sub-rows of a row are, which is why "indented means a row" is wrong.
PACKET_BLOCK_HEADINGS: tuple[str, ...] = tuple(_CATEGORY_NOTE)


def stage_gap(stage: str, reason: str | None = None) -> str:
    """A row whose producer has not run: ``unavailable_pre_<stage>``.

    Named, never defaulted. A default would read as a measurement nobody made -
    which is exactly what ``catalyst_window=False`` did before D-11.
    """
    return f"unavailable_pre_{stage}" + (f" - {reason}" if reason else "")


def _num(value: Any) -> str | None:
    """A number exactly as its producer emitted it, or ``None``.

    ``repr`` of the float, deliberately, matching ``quant_scorecard._number``: a
    fixed-precision format would round a number the packet claims is the
    engine's own.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    text = repr(f)
    return text


def _pct(value: Any) -> str | None:
    """A fraction as a percentage, or ``None`` - never ``0%`` for a missing read."""
    n = _num(value)
    return None if n is None else f"{float(n):.2%}"


def _row(label: str, pairs: list[str], trailing: str | None = None) -> str:
    """One row: ``label  k=v  k=v  <trailing>``.

    The trailing token is non-numeric by construction where it must be, so the
    ground-truth parser does not invent a key out of prose.
    """
    bits = [label] + [p for p in pairs if p]
    if trailing:
        bits.append(trailing)
    return "  ".join(bits)


# ---------------------------------------------------------------------------
# RISK CONSTRAINTS
# ---------------------------------------------------------------------------


def _risk_constraints_rows(state: dict, cfg: dict, *, closes=None) -> list[str]:
    """The decision-domain constraints: what the model reasons WITHIN.

    **Not evidence.** ``PERMISSION TRADE_ALLOWED`` listed among engine scores
    would visually resemble one more bullish input; under ``RISK CONSTRAINTS`` it
    reads as what it is - a boundary, not a fact to weigh.
    """
    rows: list[str] = []

    # The limits registry - the numbers the gates will judge against.
    try:
        from tradingagents.strategies.risk_governor import default_limits

        lim = default_limits(cfg)
        rows.append(
            _row(
                "limits",
                [
                    f"max_position={_pct(lim.get('max_position_pct'))}",
                    f"book_cap={_pct(lim.get('max_book_position_pct'))}",
                    f"cvar_budget={_pct(lim.get('risk_daily_cvar_budget_pct'))}",
                    f"drawdown_limit={_pct(lim.get('risk_max_drawdown_pct'))}",
                    f"sector_cap={_pct(lim.get('safety_cap_pct'))}",
                ],
            )
        )
    except Exception:  # noqa: BLE001 - advisory; never break a render
        rows.append(_row("limits", [], "unavailable"))

    # The measured book state. Every number is computed or a named gap.
    rctx = state.get("risk_context") or {}
    book_pairs: list[str] = []
    cvar = rctx.get("book_cvar")
    if cvar is None:
        cvar = rctx.get("single_cvar")
    if cvar is not None:
        book_pairs.append(f"cvar={_pct(cvar)}")
    if rctx.get("book_stress") is not None:
        book_pairs.append(f"stress={_pct(rctx['book_stress'])}")
    dd = rctx.get("book_drawdown")
    if dd is not None:
        dd_txt = f"drawdown={_pct(dd)}"
        limit = rctx.get("drawdown_limit")
        if limit is not None:
            dd_txt += f" (limit {float(limit):.0%})"
            dd_txt += " - new risk blocked" if float(dd) > float(limit) else " - within limit"
        book_pairs.append(dd_txt)
    rows.append(_row("book", book_pairs, None if book_pairs else "no CVaR or drawdown measured"))

    # The liquidity read that fed the risk gate (when enable_liquidity_gate ran).
    liq = rctx.get("liquidity") or {}
    if liq.get("verdict"):
        rows.append(
            _row(
                "liquidity",
                [
                    f"verdict={str(liq['verdict']).upper()}",
                    f"illiq={liq['illiq']:.2e}" if liq.get("illiq") is not None else "",
                    f"float_turnover={_pct(liq.get('float_turnover'))}",
                    f"iwf={_pct(liq.get('iwf'))}",
                ],
            )
        )
    else:
        rows.append(_row("liquidity", [], "unavailable"))

    # The regime gate - the ONE gate readable before the decision, and the same
    # read the compiled context already carries.
    if closes:
        try:
            from tradingagents.strategies.regime import regime_gate_read

            rg = regime_gate_read(closes, cfg=cfg) or {}
            cat = rg.get("catalyst_window")
            rows.append(
                _row(
                    "regime",
                    [
                        f"verdict={rg.get('verdict')}",
                        f"pass={rg.get('pass')}",
                        f"vol_pct={_num(rg.get('vol_pct'))}",
                        f"fast_downtrend={rg.get('fast_downtrend')}",
                    ],
                    "catalyst_window=unavailable_pre_graph" if cat is None else None,
                )
            )
        except Exception:  # noqa: BLE001
            rows.append(_row("regime", [], "unavailable"))
    else:
        rows.append(_row("regime", [], stage_gap("graph", "no close series supplied")))

    # §6's `permission` row, and the boundary that makes this phase's finding.
    # `portfolio_action_from_gate` derives the portfolio instruction from the
    # COMPOSED RISK GATE VERDICT, and that verdict is produced by
    # `risk_governor.govern` in the graph's post-decision fold
    # (trading_graph.py, `final_state["risk_gate"]`). §16's architecture puts the
    # deterministic gates DOWNSTREAM of the decision, so no pre-decision render
    # can carry this. Named, not defaulted: a default would assert a permission
    # nobody measured, and the two-value `TRADE_ALLOWED | BLOCKED` vocabulary in
    # §6's sketch has no producer at all - the live vocabulary is
    # `signal_action.PORTFOLIO_ACTIONS`, produced for the decision artifact by
    # `signal_action_split`.
    rows.append(
        _row(
            "permission",
            [],
            stage_gap("decision", "signal_action_split needs the post-decision gate verdict"),
        )
    )
    return rows


# ---------------------------------------------------------------------------
# EVIDENCE
# ---------------------------------------------------------------------------


def uncertainty_read(snapshot: dict | None) -> dict:
    """§8's uncertainty counter: the named gaps, aggregated from their owners.

    Three counters, never one - ``EVIDENCE`` bullish/bearish/neutral counts
    MEASURED facts, and ``UNCERTAINTY`` counts the absence of measurement. The
    two must never be added together: an unknown is not evidence against a
    thesis.

    The gaps come from the **one place each is declared**, so no reason is
    invented here:

    * an engine that was enabled and could not measure - ``quant_scorecard``'s
      own ``absent`` map carries ``{engine: reason}``;
    * a component an engine reports as absent - the engine's own ``absent`` list,
      or ``news_score``'s richer ``absent_reasons`` map.

    An engine whose gate is **off** is NOT a gap: it is intentionally not
    running, which is the ``STATE_DISABLED`` / ``STATE_NA`` distinction the
    scorecard already draws. Counting it would make a partly-gated run look like
    a run full of missing evidence.
    """
    engines = (snapshot or {}).get("engines") or {}
    gaps: list[str] = []
    for name, entry in engines.items():
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled"):
            continue  # gate off - not part of the scorecard at all
        if entry.get("score") is None:
            gaps.append(f"{name} ({entry.get('reason') or 'no score produced'})")
            continue
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        reasons = result.get("absent_reasons")
        if isinstance(reasons, dict) and reasons:
            gaps.extend(f"{name}.{k} ({v})" for k, v in sorted(reasons.items()))
            continue
        absent = result.get("absent")
        if isinstance(absent, (list, tuple)) and absent:
            gaps.append(f"{name}: {', '.join(str(a) for a in absent)}")
    return {"count": len(gaps), "gaps": gaps}


def _engine_rows(snapshot: dict | None) -> list[str]:
    """One row per engine: its score beside its coverage, or ``NA``.

    An engine whose gate is off is **not printed at all** - it is not part of the
    scorecard. ``NA`` means "evidence that was meant to be here and could not be
    measured", which is a different fact (master rule 3).

    ``engine_row_max_chars`` (§7) bounds this row. When it is exceeded the bound
    is met by dropping **whole cells** from the tail, never by cutting a cell in
    half: a truncated `technical=6` would be a number without its label, which is
    the thing the budget exists to prevent. The dropped cells are counted, so the
    bound is visible rather than silent.
    """
    from tradingagents.strategies.quant_scorecard import ENGINE_GATES

    engines = (snapshot or {}).get("engines") or {}
    cells: list[str] = []
    for name in ENGINE_GATES:
        entry = engines.get(name) or {}
        if not entry.get("enabled"):
            continue
        score = _num(entry.get("score"))
        if score is None:
            cells.append(f"{name}=NA")
            continue
        cell = f"{name}={score}"
        coverage = _num(entry.get("coverage"))
        if coverage is not None:
            cell += f" [cov {coverage}]"
        cells.append(cell)
    if not cells:
        return ["engines  unavailable - no scorecard snapshot in state"]

    limit = int(DECISION_PACKET_BUDGET["engine_row_max_chars"])

    def build(kept: list[str], n_dropped: int) -> str:
        trailing = f"[{n_dropped} engines not shown - row budget]" if n_dropped else None
        return _row("engines", kept, trailing)

    dropped = 0
    # The trailing marker counts against the bound too, so the row is rebuilt
    # and re-measured each time rather than measured once before the marker.
    while cells and len(build(cells, dropped)) > limit:
        cells.pop()
        dropped += 1
    return [build(cells, dropped)]


def _distribution_rows() -> list[str]:
    """§6's directional DISTRIBUTION - and it has NO valid producer. Named.

    §6 sketches ``bullish=<b> bearish=<d> neutral=<n>`` and justifies it with
    *"the engines already carry a sign per component"*. **They do not**, and this
    build verified it at the definition sites:

    * the engine band tables are not directional - ``REGIME_BANDS`` is
      ``benign``/``constructive``/``mixed``/``stressed``/``hostile``,
      ``RISK_BANDS`` is ``low risk``/``contained``/``moderate``/``elevated``/
      ``high``/``severe``, ``NEWS_BANDS`` is ``high-information``/``informative``/
      ``mixed``/``quiet``/``stale``/``no-signal``, ``QUALITY_BANDS`` is
      ``elite``/``poor``/``distressed``;
    * ``score_engine.align`` maps every component to a 0-100 value **in the
      favourable direction**, erasing the observation's sign - there is no
      ``sign`` key in any component dict, and the only signed field is ``raw``,
      whose arithmetic sign is meaningless for the band-mapped and boolean
      components (RSI, MFI, stochastic, Williams %R).

    The one existing counter, ``prompt_metrics.stance_direction_counts``, counts
    the **independent stances** - and those may not enter the packet as evidence:
    §4.4 and acceptance criterion 22 make them *"diagnostics, not evidence …
    they must not become a second evidence stream that the PM averages"*. Feeding
    them in would silently turn ``independent_agreement`` into the consensus the
    model defers to, which is the failure §4.4 exists to prevent.

    So the row is a **named gap**, not a zero and not a substitute count. A
    fabricated distribution would be worse than no distribution: it would present
    a diagnostics stream as evidence, and a reader could not tell.
    """
    return [
        _row(
            "DIRECTIONAL DISTRIBUTION",
            [],
            stage_gap(
                "producer",
                "the engines carry no directional sign, and the independent stances "
                "are diagnostics, not evidence (design doc §4.4)",
            ),
        )
    ]


def _conflict_rows(state: dict) -> list[str]:
    """§9's CONFLICT ledger - the same-metric disagreements, machine-classified.

    The rows come from ``report_verifier.report_ledger``, which applies the
    verifier's own ``_basis_registry`` + ``basis_conflicts`` to the four analyst
    reports **in run state**. That is the same producer the post-hoc tree pass
    uses, applied while the documents are still in state, so the packet the model
    read and the tree's ``conflicts`` key cannot disagree (rule 15).

    **Every class is printed, and the actionable ones print first.** §9's rule is
    that nothing is suppressed: a ``basis_difference`` is visible and inert, and
    only ``unresolved`` may participate in a challenge invalidation (§10). But
    the ledger is bounded, and the measured distribution is dominated by
    ``basis_difference`` (199 of 284 rows over 53 trees) - so truncating from the
    tail in metric order would routinely hide the single ``unresolved`` row
    behind twelve rows the model cannot act on. ``CONFLICT_CLASS_ORDER`` is that
    correction, and the count line states the full distribution regardless.

    Three states are distinguished, never conflated:

    * **no reports read** - the packet is being rendered before the analysts ran
      (or a caller invoked the render directly). ``unavailable_pre_reports``.
    * **reports read, nothing disagreed** - a real measurement, printed as zero.
    * **reports read, disagreements found** - the count line and the rows.
    """
    from tradingagents.agents.utils.report_verifier import report_ledger

    rows, stems_read = report_ledger(state)
    if not stems_read:
        return [
            _row(
                "CONFLICT",
                [],
                stage_gap(
                    "reports",
                    "no analyst report in state yet - the ledger is a property of "
                    "the reports (design doc §9)",
                ),
            )
        ]

    counts = dict.fromkeys(CONFLICT_CLASS_ORDER, 0)
    for r in rows:
        counts[r.classification] = counts.get(r.classification, 0) + 1
    summary = _row(
        "CONFLICT",
        [f"{counts['unresolved']} unresolved"],
        f"{counts['defect']} defect  {counts['basis_difference']} basis_difference "
        f"of {len(rows)} same-metric disagreements across {stems_read} reports",
    )
    if not rows:
        return [_row("CONFLICT", ["0 unresolved"], "no same-metric disagreement found")]

    limit_rows = int(DECISION_PACKET_BUDGET["conflict_max_rows"])
    limit_chars = int(DECISION_PACKET_BUDGET["conflict_row_max_chars"])
    ordered = sorted(
        rows,
        key=lambda r: (
            CONFLICT_CLASS_ORDER.index(r.classification)
            if r.classification in CONFLICT_CLASS_ORDER
            else len(CONFLICT_CLASS_ORDER),
            r.metric,
        ),
    )
    shown = ordered[:limit_rows]
    detail = [_conflict_detail(r, limit_chars) for r in shown]
    if len(ordered) > limit_rows:
        detail.append(
            f"  ... {len(ordered) - limit_rows} more disagreements not shown "
            "- ledger row budget"
        )
    return [summary, *detail]


def _conflict_detail(row, limit_chars: int) -> str:
    """One ledger row: ``metric  a vs b  [class]  producers  bases  section``.

    Built longest-first and **trimmed by dropping whole trailing clauses**, never
    by cutting a value from its label: the metric, both values and the class are
    the row's irreducible content, and the producer/basis/section clauses are
    dropped in that order when the bound binds. The same rule as
    ``engine_row_max_chars`` - a bound met by cutting a cell in half produces a
    number with no label, which is what the bound exists to prevent.
    """
    values = sorted({round(s.value, 6) for s in row.sides}, reverse=True)
    head = f"{row.metric}  " + " vs ".join(_num(v) or "?" for v in values)
    cls = f"[{row.classification}]"

    producers = sorted({s.producer for s in row.sides if s.producer})
    bases = sorted({s.basis for s in row.sides if s.basis})
    clauses = [
        f"producers: {' vs '.join(producers)}" if producers else "",
        f"bases: {' vs '.join(bases)}" if bases else "",
        f"section: {row.section}" if row.section else "",
    ]
    bits = [head, cls]
    for clause in clauses:
        if not clause:
            continue
        if len("  ".join([*bits, clause])) <= limit_chars:
            bits.append(clause)
    return "  " + "  ".join(bits)


def _evidence_rows(state: dict) -> list[str]:
    snapshot = state.get("quant_scorecard")
    rows = _engine_rows(snapshot)
    rows.extend(_distribution_rows())

    unc = uncertainty_read(snapshot)
    if snapshot is None:
        # No snapshot is not "every engine measured" - nothing examined them.
        rows.append(
            _row(
                "UNCERTAINTY",
                [],
                stage_gap("scorecard", "no scorecard snapshot in state - nothing examined the engines"),
            )
        )
    elif unc["count"]:
        named = "; ".join(unc["gaps"])
        if len(named) > 400:
            named = named[:397] + "..."
        rows.append(_row("UNCERTAINTY", [f"{unc['count']} named gaps"], named))
    else:
        rows.append(
            _row(
                "UNCERTAINTY",
                ["0 named gaps"],
                "every enabled engine measured",
            )
        )

    # §9's conflict ledger (Phase 3). It replaces the named gap that stood here
    # while the ledger had no producer: the same-metric pairs are computed from
    # the analyst reports by `report_verifier.report_ledger`, the same function
    # the post-hoc tree pass uses. Rendering before the analysts ran still
    # degrades to `unavailable_pre_reports` rather than to a zero.
    rows.extend(_conflict_rows(state))
    return rows


# ---------------------------------------------------------------------------
# SYNTHESIS
# ---------------------------------------------------------------------------


def _synthesis_rows(state: dict) -> list[str]:
    """``consensus`` and ``composite`` - printed last and labelled.

    Both are the highest-level summaries and the most likely to be read as an
    instruction, so each says what it is (master rule 17).
    """
    rows: list[str] = []
    try:
        from tradingagents.strategies.consensus import (
            agreement_score,
            consensus_from_score,
            weighted_consensus,
        )

        stances = state.get("risk_independent_stances") or {}
        ratings = [
            str(p["rating"])
            for p in stances.values()
            if isinstance(p, dict) and p.get("rating")
        ]
        if ratings:
            stance, _weight = weighted_consensus([(r, 1.0) for r in ratings])
            score = agreement_score(ratings)
            pairs = []
            if stance is not None:
                pairs.append(f"weighted_stance={stance:.2f}")
            if score is not None:
                pairs.append(f"label={consensus_from_score(score)}")
                pairs.append(f"agreement={score:.2f}")
            pairs.append(f"n={len(ratings)}")
            rows.append(_row("consensus", pairs))
        else:
            rows.append(
                _row("consensus", [], stage_gap("stances", "no independent stance sampled yet"))
            )
    except Exception:  # noqa: BLE001
        rows.append(_row("consensus", [], "unavailable"))

    # The composite, read from the scorecard's own entry. `basis` is the
    # engine's shipped string and is NOT rewritten here (D3: the composite's
    # printed `basis` contract is FROZEN - new fields only).
    engines = (state.get("quant_scorecard") or {}).get("engines") or {}
    comp = engines.get("trade") or {}
    if comp.get("enabled") and comp.get("score") is not None:
        raw_result = comp.get("result")
        result: dict = raw_result if isinstance(raw_result, dict) else {}
        pairs = [f"score={_num(comp.get('score'))}"]
        coverage = _num(comp.get("coverage"))
        if coverage is not None:
            pairs.append(f"coverage={coverage}")
        floor = _num(result.get("floor"))
        if floor is not None:
            pairs.append(f"floor={floor}")
        basis = result.get("basis")
        if basis:
            pairs.append(f"basis={basis}")
        rows.append(_row("composite", pairs))
    elif comp.get("enabled"):
        rows.append(_row("composite", [], "NA - the composite could not be measured"))
    else:
        rows.append(
            _row("composite", [], stage_gap("scorecard", "enable_quant_scorecard is off"))
        )
    return rows


# ---------------------------------------------------------------------------
# TRADE PARAMETERS and FALSIFIERS
# ---------------------------------------------------------------------------


def _trade_parameter_rows(cfg: dict, *, closes=None) -> tuple[list[str], dict]:
    """The measured plan rows, and the same tranche read for the falsifiers.

    ``measured_inputs`` is the ONE producer of these - the same call the compiled
    context already makes, so the packet's stop and the plan card's stop are one
    number.
    """
    if not closes:
        return [_row("plan", [], stage_gap("graph", "no close series supplied"))], {}
    try:
        from tradingagents.strategies.trade_plan import measured_inputs

        pieces = measured_inputs(closes, cfg) or {}
    except Exception:  # noqa: BLE001
        return [_row("plan", [], "unavailable")], {}
    tranche = pieces.get("tranche") or {}
    if not tranche.get("valid"):
        return [_row("plan", [], "unavailable - no usable tranche read")], pieces
    targets = pieces.get("targets") or tranche.get("targets") or {}
    rows = [
        _row(
            "levels",
            [
                f"entry={_num(tranche.get('avg_entry'))}",
                f"stop={_num(tranche.get('stop'))}",
                f"p1={_num(tranche.get('p1'))}",
                f"p2={_num(tranche.get('p2'))}",
                f"p3={_num(tranche.get('p3'))}",
                f"t1={_num(targets.get('t1'))}",
                f"t2={_num(targets.get('t2'))}",
            ],
        ),
        _row(
            "size",
            [
                f"shares={_num(tranche.get('total_shares'))}",
                f"capital_at_risk={_pct(tranche.get('capital_at_risk_pct'))}",
                f"peak_deployed={_pct(tranche.get('peak_deployed_pct'))}",
            ],
        ),
    ]
    return rows, pieces


def _falsifier_rows(state: dict, pieces: dict, cfg: dict) -> list[str]:
    """The invalidation conditions, from their one producer.

    ``report_disclosure.invalidation_conditions`` is the decision-artifact rule
    (">=1 invalidation per decision"), and it is already what the rendered
    disclosure block and ``research_decision.json`` use. The packet reads it
    rather than restating the conditions, so the prompt and the artifact cannot
    disagree.
    """
    tranche = pieces.get("tranche") or {}
    targets = pieces.get("targets") or tranche.get("targets") or {}
    stop = tranche.get("stop")
    target = targets.get("t1")
    try:
        from tradingagents.strategies.report_disclosure import invalidation_conditions

        conditions = invalidation_conditions(
            stop_loss=float(stop) if stop is not None else None,
            take_profit=float(target) if target is not None else None,
            data_quality=None,
        )
    except Exception:  # noqa: BLE001
        return [_row("conditions", [], "unavailable")]
    cap = int(DECISION_PACKET_BUDGET["falsifier_max_rows"])
    shown = list(conditions)[:cap]
    dropped = len(conditions) - len(shown)
    rows = [_row("conditions", [f"{len(conditions)} declared"])]
    rows.extend(f"  - {c}" for c in shown)
    if dropped > 0:
        rows.append(f"  - [{dropped} more not shown - packet row budget]")
    return rows


# ---------------------------------------------------------------------------
# CONDITIONAL EXPANSION (§11, Phase 4)
# ---------------------------------------------------------------------------

#: §11's budget for the expansion. **Separate from the packet's**, because the
#: packet's bound (§7) is the decision channel's and must stay measurable and
#: small; the expansion is the escape hatch that attaches research, and giving it
#: the packet's bound would either blow the packet's or silently shrink it.
CONTEXT_EXPANSION_BUDGET: dict[str, int] = {
    "expansion_max_chars": 24_000,
    "expansion_section_max_chars": 6_000,
}

#: The state key the expansion renders into. A SECOND key rather than a longer
#: packet: `packet_chars` must keep measuring the bounded decision channel, or
#: §7's bound stops meaning anything the moment a run expands.
DECISION_EXPANSION_KEY = "decision_expansion"

#: The header the expanded block opens with, so a reader can always tell which
#: context mode produced the text in front of them.
EXPANSION_HEADER = "EXPANDED RESEARCH CONTEXT"

#: §11's agreement floor. Below this the independent reads disagree, which is
#: the "agreement low" branch of §11's diagram.
EXPANSION_AGREEMENT_FLOOR = 0.5


def expansion_decision(state: dict | None, cfg: dict | None = None) -> dict:
    """§11's trigger: **expand when the evidence is divided.**

    §11 names its inputs and requires they be read as *diagnostics*, not as
    evidence: `independent_agreement` (`independent_vote.py`),
    `weighted_consensus` / `should_hold` (`consensus.py`), and the §9 conflict
    count. This reads those same producers rather than deriving its own
    agreement number, so the trigger and the consensus line the model already
    receives cannot disagree (rule 15).

    **Three ways in, and each is a measured state, not a guess:**

    * ``independent_agreement`` below the floor - the independently sampled risk
      reads disagree;
    * ``should_hold`` on the weighted stance - a divided book, which `consensus`
      already defines as "not a directional call";
    * any **unresolved** same-metric contradiction in the §9 ledger - two
      incompatible values for one metric, the sharpest form of disagreement.

    A missing input contributes **nothing**. "No stance was sampled" is not
    "everyone agreed", so it cannot count toward agreement OR toward expansion;
    with no measurable input at all the decision is ``expand=False`` and the
    reason says why.

    §11's caution - *"expansion adds information; it must not add caution"* - is
    structural here: this returns a decision to ATTACH DOCUMENTS. It cannot
    change a rating, and the only pass that can (§10) is closed-vocabulary.
    """
    st = state or {}
    reasons: list[str] = []
    agreement: float | None = None
    stance: float | None = None
    hold: bool | None = None

    try:
        from tradingagents.agents.utils.independent_vote import independent_agreement

        agreement = independent_agreement(st.get("risk_independent_stances") or {})
    except Exception:  # noqa: BLE001 - a missing producer is not agreement
        agreement = None
    if agreement is not None and agreement < EXPANSION_AGREEMENT_FLOOR:
        reasons.append(
            f"independent reads disagree (agreement {agreement:.2f} < {EXPANSION_AGREEMENT_FLOOR:.2f})"
        )

    try:
        from tradingagents.strategies.consensus import should_hold, weighted_consensus

        stances = st.get("risk_independent_stances") or {}
        ratings = [
            str(p["rating"])
            for p in stances.values()
            if isinstance(p, dict) and p.get("rating")
        ]
        if ratings:
            stance, _w = weighted_consensus([(r, 1.0) for r in ratings])
            hold = should_hold(stance)
            if hold:
                reasons.append(
                    "the weighted stance is below threshold - a divided book is not "
                    "a directional call"
                )
    except Exception:  # noqa: BLE001 - advisory
        stance, hold = None, None

    unresolved = 0
    try:
        from tradingagents.agents.utils.report_verifier import report_ledger

        ledger, _stems = report_ledger(st)
        unresolved = sum(1 for r in ledger if r.classification == "unresolved")
    except Exception:  # noqa: BLE001 - advisory
        unresolved = 0
    if unresolved:
        reasons.append(
            f"{unresolved} unresolved same-metric contradiction(s) in the §9 ledger"
        )

    measured = agreement is not None or stance is not None
    return {
        "expand": bool(reasons),
        "reasons": reasons,
        "independent_agreement": agreement,
        "weighted_stance": stance,
        "should_hold": hold,
        "unresolved_conflicts": unresolved,
        "measured": measured,
        "reason": (
            "; ".join(reasons)
            if reasons
            else (
                "no division measured"
                if measured
                else "nothing measured the division - no independent stance sampled"
            )
        ),
    }


def _expansion_section(stem: str, text: str, limit: int) -> str:
    """One named section of the expansion, bounded at a LINE boundary.

    Truncation is at a whole line, with a visible marker, for the packet's
    reason (§7): a paragraph cut mid-sentence reads as the report's own prose and
    the reader cannot tell. The marker names how much was dropped so the bound is
    auditable rather than silent.
    """
    body = str(text or "").rstrip()
    if len(body) <= limit:
        return f"## {stem}\n{body}"
    lines = body.splitlines()
    kept: list[str] = []
    used = len(stem) + 4
    for line in lines:
        if used + len(line) + 1 > limit:
            break
        kept.append(line)
        used += len(line) + 1
    dropped = len(lines) - len(kept)
    return (
        f"## {stem}\n"
        + "\n".join(kept)
        + f"\n[{dropped} further lines of this section not shown - expansion budget]"
    )


def render_expansion(state: dict | None, cfg: dict | None = None) -> str | None:
    """§11's expansion: the analyst reports, attached and named. ``None`` if not triggered.

    **Additive and bounded** (§11). The base packet is untouched and separately
    bounded; this attaches whole named sections, each bounded, until the
    expansion's own bound is reached. A section that does not fit is dropped
    WHOLE rather than half-attached, and the drop is stated.

    Only the four analyst reports are attached. They are the research the packet
    summarizes, and §1.1's invariant is about the DECISION context being large by
    accident - a triggered expansion is large on purpose, which is why it is
    recorded as a distinct `context_mode` and measured separately.
    """
    st = state or {}
    decision = expansion_decision(st, cfg)
    if not decision["expand"]:
        return None
    limit = int(CONTEXT_EXPANSION_BUDGET["expansion_max_chars"])
    section_limit = int(CONTEXT_EXPANSION_BUDGET["expansion_section_max_chars"])
    parts = [
        EXPANSION_HEADER,
        "Attached because the evidence is divided: "
        + "; ".join(decision["reasons"])
        + ". This is INFORMATION - it is not a reason to be more cautious, and "
        "no pass may turn it into one (design doc §10, §11).",
        "=" * 44,
    ]
    used = sum(len(p) + 1 for p in parts)
    attached = 0
    # The stem list has ONE producer (`report_verifier.REPORT_STEMS`), so the
    # expansion attaches the same four sections the ledger and the tree pass read.
    from tradingagents.agents.utils.report_verifier import REPORT_STEMS

    for stem in REPORT_STEMS:
        text = st.get(f"{stem}_report")
        if not text or not isinstance(text, str):
            continue
        section = _expansion_section(stem, text, section_limit)
        if used + len(section) + 1 > limit:
            parts.append(
                f"## {stem}\n[section not attached - expansion budget exhausted]"
            )
            continue
        parts.append(section)
        used += len(section) + 1
        attached += 1
    if not attached:
        parts.append("[no analyst report available to attach]")
    return "\n".join(parts).rstrip()


def expansion_facts(text: str | None) -> dict:
    """``{context_mode, expansion_chars}`` for the run card."""
    body = str(text or "")
    return {
        "context_mode": "packet+expanded" if body else "packet",
        "expansion_chars": len(body) if body else None,
    }


# ---------------------------------------------------------------------------
# Assembly, budget and measurement
# ---------------------------------------------------------------------------


def _assemble(blocks: list[tuple[str, list[str]]], header: list[str]) -> tuple[str, int]:
    """Render the blocks, dropping WHOLE rows until the packet fits the budget.

    Truncation is **structural, never textual**: only rows can be dropped, never
    a heading, a category note, the header or the purpose line. That keeps the
    labelling intact under pressure - a packet whose blocks are no longer named
    is exactly the unlabelled blob §6 exists to prevent. Drop order is
    tail-first, because the earliest blocks carry the constraints and the
    evidence a decision is made from.

    Returns ``(text, dropped_row_count)``. Never mid-row and never a number
    without its label (§7).
    """
    mutable = [[heading, [*rows]] for heading, rows in blocks]
    dropped = 0

    def render() -> list[str]:
        out = list(header)
        for heading, rows in mutable:
            out.append(heading)
            out.append(_CATEGORY_NOTE[heading])
            out.extend(rows)
            out.append("")
        return out

    lines = render()
    while len("\n".join(lines)) > PACKET_MAX_CHARS:
        victim = None
        for block in reversed(mutable):
            if block[1]:
                victim = block
                break
        if victim is None:
            break  # nothing left to drop; the header alone exceeds the budget
        victim[1].pop()
        dropped += 1
        lines = render()
    return "\n".join(lines).rstrip(), dropped


def render_decision_packet(
    state: dict | None,
    cfg: dict | None = None,
    *,
    closes=None,
) -> str:
    """Render the packet: **a pure function of state**, no model or vendor call.

    Args:
        state: the graph state. Read only - never mutated.
        cfg: the run config. Read for the limits registry and the trade plan.
        closes: the close series, when the caller holds one. It is the only input
            not already in state, and without it the regime and plan rows are
            named gaps rather than guesses.

    Returns the packet string, bounded by ``DECISION_PACKET_BUDGET``. When rows
    must be dropped a visible ``[packet truncated: N rows dropped]`` marker is
    appended.
    """
    st = state or {}
    conf = cfg or {}
    ticker = str(st.get("company_of_interest") or st.get("ticker") or "UNKNOWN").upper()
    date = str(st.get("trade_date") or "")[:10] or "unset"

    plan_rows, pieces = _trade_parameter_rows(conf, closes=closes)
    blocks = [
        (CATEGORY_RISK_CONSTRAINTS, _risk_constraints_rows(st, conf, closes=closes)),
        (CATEGORY_EVIDENCE, _evidence_rows(st)),
        (CATEGORY_SYNTHESIS, _synthesis_rows(st)),
        ("TRADE PARAMETERS", plan_rows),
        ("FALSIFIERS", _falsifier_rows(st, pieces, conf)),
    ]

    header = [
        PACKET_HEADER.format(version=PACKET_VERSION, ticker=ticker, date=date),
        PACKET_PURPOSE,
        "=" * 44,
    ]
    text, dropped = _assemble(blocks, header)
    if dropped:
        text += f"\n{PACKET_TRUNCATION_PREFIX}{dropped} rows dropped]"
    return text


def packet_facts(text: str | None) -> dict:
    """``{packet_version, packet_chars, packet_truncated}`` for the run card.

    §7: *"A ``packet_chars`` field written into ``run_card.json`` makes the
    budget observable per run."* This is that measurement.
    """
    body = str(text or "")
    return {
        "packet_version": PACKET_VERSION if body else None,
        "packet_chars": len(body) if body else None,
        "packet_truncated": (PACKET_TRUNCATION_PREFIX in body) if body else None,
    }


#: The state channel carrying the ONE close series this run fetched, so the
#: packet node renders the same series the compiled context did. §13.4:
#: *"the close series is fetched ONCE here and handed to both the compiled
#: context and the packet, so the packet's regime and plan rows cannot come from
#: a second vendor read of the same series."* Declared in ``agent_states``
#: because native LangGraph SILENTLY DROPS undeclared keys.
DECISION_PACKET_CLOSES_KEY = "decision_packet_closes"

#: The graph node that renders the packet. **Phase 3 moved the render here from
#: the pre-graph block.** §9's ledger is a property of the analyst reports, which
#: do not exist before the analysts run, and §9 makes the ledger part of the
#: packet - so a packet compiled before the graph could only ever carry a named
#: gap where its CONFLICT row belongs. One node, one render, one
#: ``packet_chars`` measurement: the property §13.4 established is preserved, and
#: the render now happens where its inputs exist.
DECISION_PACKET_NODE = "Decision Packet"


def create_decision_packet_node(cfg: dict | None):
    """The graph node that renders the packet into state. Never raises.

    It returns only ``DECISION_PACKET_KEY``, so it cannot disturb any other
    channel. A render failure leaves the key unwritten, and
    ``decision_packet_or_context`` then reports a wiring defect rather than
    silently falling back to the compiled context - a broken packet must not
    look like a working gate-off run.
    """

    def _node(state: dict) -> dict:
        try:
            closes = list((state or {}).get(DECISION_PACKET_CLOSES_KEY) or [])
            out = {DECISION_PACKET_KEY: render_decision_packet(state, cfg, closes=closes)}
            # §11 (Phase 4): the conditional expansion. A separate channel with
            # its own bound, so `packet_chars` keeps measuring the decision
            # channel. Gated independently: with `enable_context_expansion` off
            # this writes nothing and `context_mode` stays "packet".
            if bool((cfg or {}).get("enable_context_expansion")):
                expansion = render_expansion(state, cfg)
                if expansion:
                    out[DECISION_EXPANSION_KEY] = expansion
            return out
        except Exception as exc:  # noqa: BLE001 - advisory; never break a run
            logger.warning("decision packet render failed: %s", exc)
            return {}

    return _node


def decision_packet_or_context(state: dict | None, cfg: dict | None = None) -> str:
    """The decision context for one consumer site: the packet, or the legacy string.

    **This is the gate**, and it is the only place the switch is read. With
    ``enable_decision_packet`` off the caller gets ``computed_decision_context``
    byte-for-byte as before, so a gate-off run is identical to the run before the
    packet existed (acceptance criterion 1).

    With it on the caller gets the packet the graph rendered ONCE into state
    (``DECISION_PACKET_KEY``). Reading the stored string rather than re-rendering
    per site keeps **one producer of the packet** and one ``packet_chars``
    measurement - the block the model read is the block the card measures.
    """
    st = state or {}
    if not bool((cfg or {}).get("enable_decision_packet")):
        return st.get("computed_decision_context") or ""
    packet = st.get(DECISION_PACKET_KEY)
    if packet:
        # §11: the expansion is additive and separately bounded. Appending it
        # here - the ONE read site - keeps a single string for the consumer and a
        # single `packet_chars` for the card, which still measures the bounded
        # decision channel alone.
        expansion = st.get(DECISION_EXPANSION_KEY)
        if expansion:
            return f"{packet}\n\n{expansion}"
        return str(packet)
    # The gate is on but nothing rendered: a wiring defect, not a silent
    # fallback. Returning the compiled context here would make a broken packet
    # look like a working gate-off run, which is the failure mode this whole
    # document is about.
    return (
        f"DECISION PACKET {PACKET_VERSION} - UNAVAILABLE\n"
        "The packet gate is on but no packet was rendered into state "
        f"(expected state key {DECISION_PACKET_KEY!r}). This is a wiring defect."
    )
