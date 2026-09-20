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

from typing import Any

__all__ = [
    "CATEGORY_EVIDENCE",
    "CATEGORY_RISK_CONSTRAINTS",
    "CATEGORY_SYNTHESIS",
    "DECISION_PACKET_BUDGET",
    "DECISION_PACKET_KEY",
    "PACKET_MAX_CHARS",
    "PACKET_TRUNCATION_PREFIX",
    "PACKET_VERSION",
    "decision_packet_or_context",
    "packet_facts",
    "render_decision_packet",
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
    "falsifier_max_rows": 8,
}
PACKET_MAX_CHARS: int = DECISION_PACKET_BUDGET["packet_max_chars"]

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

    # §9's conflict ledger is Phase 3. Named as absent rather than defaulted to
    # zero: the same-metric pairs are resolved post-hoc over the report tree by
    # the verifier, and are not in run state.
    rows.append(
        _row(
            "CONFLICT",
            [],
            stage_gap("ledger", "same-metric pairs are resolved post-hoc (design doc §9, Phase 3)"),
        )
    )
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
