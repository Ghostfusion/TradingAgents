"""The research layer's one score snapshot (WP-12, `P12-1`).

`quant_scorecard(ticker, trade_date, cfg)` is the **single producer** of the
engines' numbers on the research surface. The eight engines reach a human
through two gated tool leaves and `run_card.json`; this module adds the third
reader the design calls for - the debate and manager prompts - by computing each
engine **once** and returning the engines' own results verbatim.

Design rules it must not break (``docs/scores/ResearchLayerWiring.md`` §2, §3):

* **One producer per number.** It computes nothing itself: no alignment, no
  re-weighting, no substitution, no derived quantity. Every value in the
  returned dict is a value some engine produced. The composite is produced by
  `strategies.trade_score.trade_score`, not here.
* **`NA` is not `0`.** An engine whose gate is off, whose components could not be
  measured, or which raised is recorded as **absent with its reason** - never as
  a zero and never as a neutral 50.
* **A gate is a membership switch.** An engine entry is present **iff that
  engine's own gate is on** - the rule `reporting._run_card_trade_score` already
  applies, adopted here for all readers so the leaf, the card and the debate
  cannot print different numbers for one vector.
* **Every engine is read through the date the run is for.** The date-dependent
  engines (`fundamental`, `sentiment`, `news`) are handed ``trade_date``, not the
  wall clock. Scoring the clock was defect D-7
  (`docs/scores/ResearchLayerWiring.md` §6).
* **Advisory only.** Nothing here gates, sizes or reaches `opportunity_score`.
  The executor's checks run downstream and block regardless.

The snapshot is built **before the graph runs** (``graph/trading_graph.py``,
before `_compiled_decision_context`), so the debate's number and the report's
number are provably one number.

``catalyst_snapshot`` is the one input that cannot be read at that point: the
catalyst overlay is stamped **after** the graph
(``trading_graph._apply_strategy_overlays``). Callers that have it - the post-run
readers - pass it in and the event engine is measured; callers that do not get
the event engine **absent with that reason**, which is the honest read and never
a zero.
"""

from __future__ import annotations

from typing import Any

from tradingagents.strategies.score_engine import NON_MONOTONIC_INPUTS

__all__ = [
    "ANALYST_SECTIONS",
    "COMPOSITE_ENGINES",
    "ENGINE_GATES",
    "ENGINE_SECTIONS",
    "ENGINE_TOOLS",
    "EVENT_NO_SNAPSHOT",
    "SCORECARD_BASIS",
    "SCORECARD_HEADER",
    "SCORECARD_MAX_CHARS",
    "SCORECARD_PURPOSE",
    "engine_scores",
    "engines_for_analyst",
    "format_engine_detail",
    "format_quant_scorecard",
    "quant_scorecard",
    "scorecard_status",
    "split_scorecard_block",
]

#: The eight engine gates, in the order the surfaces print them. An entry is
#: present iff its own gate is on (§3.4) - the master `enable_quant_scorecard`
#: gate governs the scorecard **surface**, never the engines it reports.
ENGINE_GATES: dict[str, str] = {
    "fundamental": "enable_fundamental_score",
    "technical": "enable_technical_score",
    "regime": "enable_regime_score",
    "risk": "enable_risk_score",
    "sentiment": "enable_sentiment_score",
    "news": "enable_news_score",
    "event": "enable_event_state",
    "trade": "enable_trade_score",
}

#: The engines the decision composite reads - `{fundamental, technical, regime,
#: risk}` over the owner's `0.40/0.25/0.15/0.20` vector. The research allocation
#: and the decision composite are separate objects: **no engine enters the
#: composite by adjacency** (master rule 17), which is why `sentiment`, `news`
#: and `event` are reported by this snapshot but never fed to `trade_score`.
COMPOSITE_ENGINES: tuple[str, ...] = ("fundamental", "technical", "regime", "risk")

#: The score tool that publishes each engine to an analyst's LLM.
ENGINE_TOOLS: dict[str, str] = {
    "fundamental": "get_fundamental_score",
    "technical": "get_technical_score",
    "regime": "get_regime_score",
    "risk": "get_risk_score",
    "sentiment": "get_sentiment_score",
    "news": "get_news_score",
    "event": "get_event_state",
    "trade": "get_trade_score",
}

#: The analyst report each engine's AUTHORITATIVE result belongs to, or ``None``
#: for report-level. **This is the ownership map: one place decides where an
#: engine's result appears, so the model never chooses.**
#:
#: Two surfaces derive from it and therefore cannot drift from each other or
#: from this table:
#:
#: * the tool binding - `agents/toolsets.py` gives each analyst exactly the
#:   leaves of the engines it owns, so an analyst can never be handed a tool for
#:   a domain it does not own (the `get_technical_score`-on-the-fundamentals-
#:   analyst defect this table fixes);
#: * the prompt fragment - `agents/utils/report_hygiene.engine_score_rules`
#:   tells each analyst which of its own scores to call and cite.
#:
#: `regime`, `risk` and `trade` are report-level **by decision, not omission**:
#: regime describes the operating environment, risk is a cross-cutting
#: constraint and trade is the downstream decision layer - none is an
#: independent analytical opinion, so none gets an analyst section. They stay in
#: the quant scorecard and the computed decision context.
ENGINE_SECTIONS: dict[str, str | None] = {
    "fundamental": "fundamentals",
    "technical": "market",
    "sentiment": "sentiment",
    "news": "news",
    "event": "news",
    "regime": None,
    "risk": None,
    "trade": None,
}

#: The analyst keys the map above assigns to, in report order.
ANALYST_SECTIONS: tuple[str, ...] = ("market", "sentiment", "news", "fundamentals")


def engines_for_analyst(analyst_key: str) -> tuple[str, ...]:
    """The engines whose authoritative result belongs to ``analyst_key``.

    The inverse of `ENGINE_SECTIONS`, derived rather than restated, so the tool
    binding and the prompt fragment are two readings of one table.
    """
    return tuple(
        name for name, section in ENGINE_SECTIONS.items() if section == analyst_key
    )


#: Why the event engine is absent on a pre-graph snapshot, stated once so every
#: reader prints the same reason.
EVENT_NO_SNAPSHOT = (
    "the catalyst snapshot is stamped after the graph "
    "(trading_graph._apply_strategy_overlays), and the snapshot is built before "
    "it runs - pass catalyst_snapshot to measure this engine"
)

#: §4.6's engine vocabulary. Three states, and the distinction is load-bearing:
#: an engine whose gate is **off** is not part of the scorecard at all, while an
#: engine that is enabled and could not measure is **missing evidence**. Conflating
#: them would let an engine that failed to measure disappear from the count and
#: make a partial scorecard look complete - which is exactly what `PARTIAL` exists
#: to prevent (master rule 3).
STATE_DISABLED = "DISABLED"  # gate off; intentionally not running
STATE_MEASURED = "MEASURED"  # enabled, and produced evidence
STATE_NA = "NA"  # enabled, but measurement could not be produced


def engine_state(entry: dict | None) -> str:
    """`DISABLED` | `MEASURED` | `NA` for one engine entry.

    | state | meaning | scorecard participation |
    | --- | --- | --- |
    | `DISABLED` | the gate is off; the engine is intentionally not running | not applicable - no row at all |
    | `MEASURED` | enabled and produced evidence | included |
    | `NA` | enabled, but measurement could not be produced | missing evidence - contributes to `PARTIAL` |

    A `DISABLED` engine still makes the scorecard `PARTIAL` rather than `COMPLETE`,
    because the evidence set is incomplete against the full engine set: the status
    describes how much of the intended evidence is present, and an engine that was
    never switched on is evidence that is not there.
    """
    e = entry or {}
    if not e.get("enabled"):
        return STATE_DISABLED
    return STATE_MEASURED if e.get("score") is not None else STATE_NA


def _cfg_or_ambient(cfg: dict | None) -> dict:
    """The config to read gates from: the caller's, else the ambient one."""
    if cfg is not None:
        return cfg
    try:
        from tradingagents.dataflows.config import get_config

        return get_config() or {}
    except Exception:  # noqa: BLE001 - a missing config is an ungated read, not a crash
        return {}


def _entry(
    name: str,
    *,
    result: dict | None = None,
    score: Any = None,
    coverage: Any = None,
    band: Any = None,
    reason: str | None = None,
    **extra: Any,
) -> dict:
    """One engine's entry: the result verbatim plus the fields readers print.

    ``result`` is the engine's own return dict, unmodified. ``score``/``coverage``
    /``band`` are **extracted** from it, never computed - the engines disagree on
    the key they use for the band (`bands` for the composite label in
    `technical_score`/`risk_score`, `band` elsewhere), which is why each reader
    below names its own.
    """
    out = {
        "engine": name,
        "gate": ENGINE_GATES[name],
        # Whether the engine's own gate was ON. This is not the same question as
        # "did it produce a score": a gated-off engine is **not part of the
        # scorecard**, while an enabled engine that could not measure is
        # **absent evidence**. The renderer and §4.6's status need both.
        "enabled": True,
        "status": (result or {}).get("status") if isinstance(result, dict) else None,
        "score": score,
        "coverage": coverage,
        "band": band,
        "reason": reason,
        "result": result,
    }
    out.update(extra)
    # Computed last, because `extra` may carry `enabled=False`.
    out["state"] = engine_state(out)
    return out


def _read_fundamental(ticker: str, date: str | None) -> dict:
    try:
        from tradingagents.strategies.fundamental_score import (
            fundamental_score_for_ticker,
        )

        res = fundamental_score_for_ticker(ticker, date)
    except Exception as exc:  # noqa: BLE001 - one engine must not cost the snapshot
        return _entry("fundamental", reason=f"{type(exc).__name__}: {exc}")
    key = str(res.get("ticker") or ticker).strip().upper()
    return _entry(
        "fundamental",
        result=res,
        score=(res.get("scores") or {}).get(key),
        coverage=(res.get("coverage") or {}).get(key),
        panel_n=res.get("panel_n"),
    )


def _read_technical(ticker: str) -> dict:
    try:
        from tradingagents.agents.utils.analysis_tools import _technical_components
        from tradingagents.strategies.technical_score import technical_score

        vals = _technical_components(ticker)
        if not vals:
            return _entry(
                "technical",
                reason="no component could be measured from the run's bars",
            )
        res = technical_score(vals)
    except Exception as exc:  # noqa: BLE001
        return _entry("technical", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "technical",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("bands"),
    )


def _read_regime() -> dict:
    try:
        from tradingagents.agents.utils.analysis_tools import (
            _regime_components,
            _regime_two_paths,
        )
        from tradingagents.strategies.regime_score import regime_score

        vals = _regime_components()
        if not vals:
            return _entry("regime", reason="no market data for the benchmark")
        res = regime_score(vals)
    except Exception as exc:  # noqa: BLE001
        return _entry("regime", reason=f"{type(exc).__name__}: {exc}")
    try:
        paths = _regime_two_paths()
    except Exception:  # noqa: BLE001 - the disagreement read is one extra line
        paths = None
    return _entry(
        "regime",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("band"),
        two_paths=paths,
    )


def _read_risk(ticker: str) -> dict:
    try:
        from tradingagents.agents.utils.analysis_tools import _risk_components
        from tradingagents.strategies.risk_score import risk_score

        vals = _risk_components(ticker)
        if not vals:
            return _entry("risk", reason="no risk component could be measured")
        res = risk_score(vals)
    except Exception as exc:  # noqa: BLE001
        return _entry("risk", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "risk",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("bands"),
        uncertainty=res.get("uncertainty"),
    )


def _read_sentiment(ticker: str, date: str | None) -> dict:
    try:
        from tradingagents.agents.utils.analysis_tools import (
            _sentiment_components,
            _sentiment_price_read,
        )
        from tradingagents.strategies.sentiment_score import sentiment_score

        vals, source = _sentiment_components(ticker, date)
        if not vals:
            return _entry("sentiment", reason="no sentiment producer measured")
        res = sentiment_score(
            vals, source=source, price_read=_sentiment_price_read(ticker)
        )
    except Exception as exc:  # noqa: BLE001
        return _entry("sentiment", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "sentiment",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("bands"),
        quadrant=res.get("quadrant"),
    )


def _read_news(ticker: str, date: str | None) -> dict:
    try:
        from tradingagents.agents.utils.analysis_tools import _news_components
        from tradingagents.strategies.news_score import news_score

        vals = _news_components(ticker, date)
        if not vals:
            return _entry("news", reason="no news producer measured")
        res = news_score(vals)
    except Exception as exc:  # noqa: BLE001
        return _entry("news", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "news",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
    )


def _read_event(date: str | None, catalyst_snapshot: dict | None) -> dict:
    """The event engine, when the caller holds the catalyst snapshot."""
    if not isinstance(catalyst_snapshot, dict):
        return _entry("event", reason=EVENT_NO_SNAPSHOT)
    try:
        from datetime import datetime

        from tradingagents.strategies.derivatives_gamma import opex_status
        from tradingagents.strategies.event_state import (
            event_components,
            event_state,
        )

        opex = None
        if date:
            try:
                opex = opex_status(
                    datetime.strptime(str(date)[:10], "%Y-%m-%d").date()
                )
            except Exception:  # noqa: BLE001 - OPEX is one extra family
                opex = None
        # No snapshot in the run is a reason, not a crash: the card block treats
        # a missing snapshot the same way.
        res = event_state(event_components(catalyst_snapshot, opex=opex))
    except Exception as exc:  # noqa: BLE001
        return _entry("event", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "event",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("band"),
        hard_block=res.get("hard_block"),
    )


def _read_composite(engines: dict[str, dict]) -> dict:
    """The decision composite, from the four engine scores and nothing else.

    `trade_score` is the producer; this function only assembles its argument.
    The engines it reads are `COMPOSITE_ENGINES` - never by adjacency.
    """
    try:
        from tradingagents.strategies.trade_score import trade_score

        res = trade_score(
            {name: engines.get(name, {}).get("score") for name in COMPOSITE_ENGINES}
        )
    except Exception as exc:  # noqa: BLE001
        return _entry("trade", reason=f"{type(exc).__name__}: {exc}")
    return _entry(
        "trade",
        result=res,
        score=res.get("score"),
        coverage=res.get("coverage"),
        band=res.get("bands"),
        # The engines' own values, as `trade_score` saw them, so the number
        # stays recomputable from the snapshot alone.
        engines={
            name: (res.get("components") or {}).get(name, {}).get("value")
            for name in COMPOSITE_ENGINES
        },
    )


def quant_scorecard(
    ticker: str,
    trade_date: str | None = None,
    cfg: dict | None = None,
    *,
    catalyst_snapshot: dict | None = None,
) -> dict:
    """Every engine's result for one ticker on one run date, computed once.

    Returns ``{"ticker", "trade_date", "engines", "present", "absent",
    "composite", "gates"}``:

    * ``engines`` - one entry per engine, each carrying the engine's own return
      dict under ``result`` plus the ``score``/``coverage``/``band`` a reader
      prints. An engine that is off or unmeasurable carries ``None`` for those
      and a ``reason`` in place of a number.
    * ``present`` / ``absent`` - the enabled and disabled engine names, so a
      caller can render the partial state explicitly rather than inferring it.
      This is what keeps a partly-gated scorecard from reading as a complete one
      (master rule 3).
    * ``composite`` - the `trade_score` entry, or ``None`` when its gate is off.

    Nothing is computed here. The caller decides what to render; this function
    never decides what anything means.
    """
    config = _cfg_or_ambient(cfg)
    date = trade_date
    engines: dict[str, dict] = {}

    for name in ENGINE_GATES:
        if not bool(config.get(ENGINE_GATES[name])):
            engines[name] = _entry(
                name, reason=f"{ENGINE_GATES[name]} is off", enabled=False
            )
            continue
        if name == "trade":
            # Assembled last, from the four engines above - a composite that
            # cannot see them would be a second producer.
            engines[name] = _read_composite(engines)
        elif name == "fundamental":
            engines[name] = _read_fundamental(ticker, date)
        elif name == "technical":
            engines[name] = _read_technical(ticker)
        elif name == "regime":
            engines[name] = _read_regime()
        elif name == "risk":
            engines[name] = _read_risk(ticker)
        elif name == "sentiment":
            engines[name] = _read_sentiment(ticker, date)
        elif name == "news":
            engines[name] = _read_news(ticker, date)
        else:  # event
            engines[name] = _read_event(date, catalyst_snapshot)

    present = [n for n, e in engines.items() if e.get("score") is not None]
    absent = {
        n: (e.get("reason") or "no score produced")
        for n, e in engines.items()
        if e.get("score") is None
    }
    return {
        "ticker": str(ticker).strip().upper(),
        "trade_date": str(date)[:10] if date else None,
        "engines": engines,
        "present": present,
        "absent": absent,
        "composite": engines.get("trade", {}).get("result"),
        "gates": {name: ENGINE_GATES[name] for name in ENGINE_GATES},
    }


# ---------------------------------------------------------------------------
# The block (§4.1)
# ---------------------------------------------------------------------------

#: The block's first line. It states what the numbers are.
SCORECARD_HEADER = (
    "Quant scorecard (deterministic, advisory - evidence for review, not an "
    "order):"
)

#: The purpose, on the new surface (§4.1). **English only** - see the ordering
#: rule in `format_quant_scorecard`: a non-numeric `key=value` on the same line
#: as a numeric one is swallowed into that numeric pair's key by the
#: ground-truth parser, so prose that must not be parsed is kept digit-free and
#: on its own line.
SCORECARD_PURPOSE = (
    "Purpose: the highest-level quantitative evidence summary, for human "
    "research review - not an order, not a position size and not a gate."
)

#: The scorecard's own explanation, on the **new** surface (§9 D3 / §9.1).
#: `basis` - the composite's shipped negative-constraint string - is **not**
#: rewritten and not touched by this rollout; a field its consumer still reads is
#: `basis`, so the scorecard's explanation gets its own name and its own home.
SCORECARD_BASIS = (
    "One deterministic snapshot of this run's own engine results, computed once "
    "before the graph and read by the debate block, the report card and the tool "
    "leaf, so all three print the same number. Enablement and measurement are "
    "separate axes: `Scorecard status` says which engines are switched on, "
    "`Vector status` says how far the weight vector itself has been validated, and "
    "`Movement` stays UNAVAILABLE until a prior observation exists under the same "
    "validated vector. The engines' own `basis` fields are unchanged and remain "
    "authoritative for what each engine measured."
)

#: The bound on the rendered block (§4.4). The block is placed **first** in
#: `computed_decision_context` so that any truncation downstream consumes
#: something else, but it is still bounded on its own.
SCORECARD_MAX_CHARS = 1200


def _number(value: Any) -> str | None:
    """A number exactly as an engine produced it, or ``None``.

    ``repr`` of the float, deliberately: any fixed-precision format would round
    a value the engine did not round, and the block's whole claim is that its
    numbers are the engines' numbers. Scientific notation is expanded because
    the ground-truth parser reads ``1e-05`` as ``1``.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    text = repr(f)
    if "e" in text or "E" in text:
        text = f"{f:.10f}".rstrip("0").rstrip(".") or "0"
    return text


def _pair_line(pairs: list[str], trailing: str | None = None) -> str:
    """One line of the block: numeric pairs, then a non-numeric token last.

    **The ordering is load-bearing, not cosmetic.** `ground_truth_from_state`
    parses this text with `_parse_key_value_lines`, whose key pattern is
    case-insensitive and admits spaces - so on the line

        ``trade_score=76.75 trade_status=RESEARCH_ONLY trade_coverage=0.95``

    the key it actually recovers is ``research_only_trade_coverage``, and
    ``trade_coverage`` never exists in the registry. Verified by running the real
    parser: the section 4.1 example yields exactly that spurious key. Putting the
    non-numeric token last on its line removes the opportunity, because the
    parser works line by line and a trailing token has no number after it to
    anchor a key.
    """
    line = " ".join(pairs)
    if trailing:
        line = f"{line} {trailing}" if line else trailing
    return line


def scorecard_status(snapshot: dict | None) -> dict:
    """§4.6's axes: enablement, measurement, movement - printed, never inferred.

    Enablement is `DISABLED` / `PARTIAL` / `COMPLETE` over the engines' **own**
    gates, and the enabled and disabled names travel with it. A partial scorecard
    read as a complete one is the same failure as a partial engine printed as a
    whole one (master rule 3), and D1's whole point is that the partial state is
    useful during dark launch only if it is **explicit**.

    Measurement is the vector's rung, taken verbatim from the composite the engine
    produced - never re-derived here, so there is one producer for it too.
    `trade_score`'s vocabulary is `RESEARCH_ONLY` -> `VALIDATED` -> `PRODUCTION`;
    §4.6's ladder names the promoted rung `ACTIVE`, and the value printed is the
    engine's own word for it.

    Movement is `UNAVAILABLE` until a prior observation exists under the **same
    validated** vector (§4.3/§9 D2). The hard invariant is *no validated vector ->
    no delta -> no movement*, so this is the honest default rather than a
    placeholder: `P12-8` adds the store that can make it real.
    """
    engines = (snapshot or {}).get("engines") or {}
    states = {
        name: (entry.get("state") or engine_state(entry))
        for name, entry in engines.items()
    }
    disabled = [n for n, s in states.items() if s == STATE_DISABLED]
    missing = [n for n, s in states.items() if s == STATE_NA]
    measured = [n for n, s in states.items() if s == STATE_MEASURED]
    if not measured and not missing:
        status = "DISABLED"
    elif disabled or missing:
        status = "PARTIAL"
    else:
        status = "COMPLETE"
    composite = engines.get("trade") or {}
    movement = (snapshot or {}).get("movement") or {}
    return {
        "scorecard_status": status,
        "enabled": [n for n in states if n not in disabled],
        "disabled": disabled,
        # the engines that were meant to measure and could not - the ones that
        # make PARTIAL meaningful rather than cosmetic
        "unmeasured": missing,
        "measured": measured,
        "vector_status": composite.get("status") or "UNAVAILABLE",
        "movement": movement.get("movement") or "UNAVAILABLE",
        "movement_reason": movement.get("reason"),
    }


def engine_scores(snapshot: dict | None) -> dict[str, float | None]:
    """The four composite engines' scores from a snapshot, as the gates decided.

    **This is the one way a composite reader gets its inputs** (§3.4). The
    snapshot already applied the rule *an engine entry is present iff its own gate
    is on*, so a reader that goes through here cannot disagree with the block the
    debate read or the key the card wrote - which is defect D-8: the leaf
    assembled its own four values regardless of the gates, so with
    `enable_trade_score` on and a sub-gate off the leaf and the card printed
    **different composites** for one vector.

    An engine that is absent comes back as ``None``, which leaves it out of the
    composite's denominator - never `0` (rule 2).
    """
    engines = (snapshot or {}).get("engines") or {}
    return {
        name: (engines.get(name) or {}).get("score") for name in COMPOSITE_ENGINES
    }


def split_scorecard_block(context: str) -> tuple[str | None, str]:
    """``(scorecard_block, rest)`` for a context whose block is **first** (§4.4).

    The block is part of `computed_decision_context` because the report renders
    that whole string as section `IVa` and the L1 registry parses it for citable
    ground truth. The structured debate needs it in a field of its own, though,
    so that its 3000-character bound applies to the *rest* of the context and
    cannot silently truncate the scorecard away. Splitting here keeps both
    readers on one string, so neither can drift from the other.

    Returns ``(None, context)`` when there is no block - which is exactly the
    gate-off case, so the caller changes nothing.
    """
    text = str(context or "")
    if not text.startswith(SCORECARD_HEADER):
        return None, text
    block, _, rest = text.partition("\n\n")
    return block, rest


def _plain(value: Any) -> str | None:
    """A number for the detail surfaces: exact, but without a bare `.0`.

    `_number` keeps `repr`'s exactness (the block's claim is that its numbers are
    the engines' numbers). The detail views read better without `85.0`, and they
    must match the leaf's own triple character for character, so the trailing
    `.0` is dropped there and nowhere else.
    """
    text = _number(value)
    if text is None:
        return None
    return text[:-2] if text.endswith(".0") else text


def format_engine_detail(snapshot: dict | None) -> str:
    """Level 2 (§4.2): each engine's categories beside the measurements they came from.

    *"Level 2 is where the owner's 'research evidence → score → interpretation'
    chain becomes visible"* — an addition that renders each engine's
    **already-computed** result and adds no producer. The composite is printed
    beside the categories and their weights, so a reader can recompute it rather
    than trust it.

    **Non-monotonic inputs are shown as the triple** (§4.5). `score_engine.align`
    maps eight inputs through a producer-defined ramp, so a high raw value can
    align *low* — RSI `82` aligns to `45`. A reader given only `technical 85`
    cannot tell a healthy momentum read from an overbought one, and the point is
    that they can **challenge the interpretation without touching the
    mathematics**. Where a component is monotonic, no mapping note is printed.
    """
    snap = snapshot or {}
    engines = snap.get("engines") or {}
    ticker = str(snap.get("ticker") or "").strip().upper()
    lines: list[str] = []
    for name in ENGINE_GATES:
        entry = engines.get(name) or {}
        if not entry.get("enabled"):
            continue
        result = entry.get("result")
        score = _plain(entry.get("score"))
        head = f"### {name.capitalize()}Score"
        if score is None:
            head += f" — NA ({entry.get('reason') or 'not measured'})"
        else:
            head += f" — {score}/100"
            if entry.get("band"):
                head += f" ({entry['band']})"
            coverage = _plain(entry.get("coverage"))
            if coverage is not None:
                head += f", coverage {coverage}"
        lines.append(head)
        if not isinstance(result, dict):
            lines.append("")
            continue
        cats = result.get("categories") or result.get("subscores") or {}
        if not isinstance(cats, dict) or not cats:
            lines.append("- no category detail carried by this engine")
            lines.append("")
            continue
        components = result.get("components") or {}
        for cat, cat_entry in cats.items():
            if not isinstance(cat_entry, dict):
                continue
            # A PANEL engine (`FundamentalScore`) keys each sub-score's
            # `scores`/`bands`/`coverage`/`withheld` by TICKER, so the analysed
            # name's own row is the only correct read. Taking the first value
            # instead reads whichever peer the producer inserted first - and
            # `category_scores` inserts in ASCENDING percentile order, so that is
            # always the WORST peer, whose percentile is 0.0. Measured on
            # reports/MSFT_20260920_145644: the report printed `- FQS: 0/100`
            # for a run whose own card carried FQS 37.5.
            panel_keyed = isinstance(cat_entry.get("scores"), dict)
            if panel_keyed:
                c_score = (cat_entry.get("scores") or {}).get(ticker)
                c_band = (cat_entry.get("bands") or {}).get(ticker)
                withheld = (cat_entry.get("withheld") or {}).get(ticker)
            else:
                c_score = cat_entry.get("score")
                c_band = cat_entry.get("band")
                withheld = cat_entry.get("withheld")
            weight = cat_entry.get("weight")
            head = f"- {cat}"
            if weight is not None:
                head += f" (weight {_plain(weight)})"
            head += f": {'NA' if c_score is None else _plain(c_score)}/100"
            if c_band:
                head += f" ({c_band})"
            # `factors_NA` is the set of factors with NO supplier. It is a NAMED
            # GAP, never a "present component" list - and for a panel engine the
            # `components` dict is keyed by ticker, so a factor-name lookup
            # against it could not match anyway.
            present = cat_entry.get("present")
            if panel_keyed:
                cov = (cat_entry.get("coverage") or {}).get(ticker) or {}
                if cov.get("of"):
                    head += f" | coverage {cov.get('n', 0)} of {cov['of']} factors"
            elif isinstance(present, (list, tuple)) and present:
                head += f" over {len(present)} components"
            lines.append(head)
            if withheld:
                lines.append(f"    withheld: {withheld}")
            if panel_keyed:
                na = cat_entry.get("factors_NA")
                if isinstance(na, (list, tuple)) and na:
                    lines.append(f"    factors NA: {', '.join(str(f) for f in na)}")
            for comp in present if isinstance(present, (list, tuple)) else []:
                detail = components.get(comp) if isinstance(components, dict) else None
                if not isinstance(detail, dict):
                    continue
                raw = _plain(detail.get("raw"))
                aligned = _plain(detail.get("aligned"))
                if raw is None or aligned is None:
                    continue
                if comp in NON_MONOTONIC_INPUTS:
                    # §4.5's triple: the value, the aligned value, and why they
                    # differ — so "the score is 85" is a claim the reader can
                    # interrogate rather than a fact they must accept.
                    lines.append(
                        f"    {comp}={raw} {comp}_aligned={aligned} "
                        "mapping=producer-defined non-monotonic band"
                    )
                else:
                    lines.append(f"    {comp}={raw} -> {aligned}")
        lines.append("")
    return "\n".join(lines).strip()


def format_quant_scorecard(snapshot: dict | None) -> str:
    """Render the snapshot as the `key=value` block the debate reads (§4.1).

    Three properties are non-negotiable and each is tested:

    * **the composite is printed with its four drivers beside it**, because `76`
      and `76 because F 92 / T 85 / R 78 / K 35` are different research
      situations and a reader cannot tell them apart without the drivers;
    * **coverage is printed per engine and on the composite** - `72` at
      `coverage 68%` means *72 over 68% of the intended evidence*, and the
      engines that could not measure are named;
    * **it is parseable** by `structured_debate._parse_key_value_lines`, so the
      values become citable, verifiable ground truth rather than prose the L1
      registry cannot check.

    An engine that could not measure prints `NA`, never `0` (rule 2). An engine
    whose gate is *off* is not printed at all - it is not part of the scorecard -
    and only the engines named in ``absent`` are those that were meant to be
    there and could not be measured.
    """
    snap = snapshot or {}
    engines = snap.get("engines") or {}
    lines = [SCORECARD_HEADER, SCORECARD_PURPOSE]

    comp = engines.get("trade") or {}
    status = comp.get("status")
    move = snap.get("movement") or {}
    has_delta = (
        move.get("movement") == "AVAILABLE"
        and move.get("delta") is not None
        and move.get("prev") is not None
    )
    pairs: list[str] = []
    score = _number(comp.get("score"))
    if score is None:
        pairs.append("trade_score=NA")
    else:
        pairs.append(f"trade_score={score}")
        coverage = _number(comp.get("coverage"))
        if coverage is not None:
            pairs.append(f"trade_coverage={coverage}")
        if has_delta:
            # §4.3's delta, printed UNSIGNED. The doc's example writes `+3.55`,
            # and the ground-truth parser's number pattern is `-?\d+...` - a
            # leading `+` is not matched, so `trade_delta` never registers at
            # all. Verified by running the real parser over that example. The
            # sign still reads for a human (a fall carries `-`).
            pairs.append(f"trade_prev={_number(move.get('prev'))}")
            pairs.append(f"trade_delta={_number(move.get('delta'))}")
    lines.append(_pair_line(pairs, trailing=f"trade_status={status}" if status else None))
    if has_delta:
        # The date is mandatory - a delta against an unstated date is a disguised
        # fabrication - and it is printed in parentheses so it adds NO registry
        # key. `trade_prev_date=2026-09-11` would register as `trade_prev_date =
        # 2026`, a year under a name that reads like a metric.
        lines.append(f"prior observation ({move.get('prev_date')})")

    for name in COMPOSITE_ENGINES:
        entry = engines.get(name) or {}
        # An engine whose gate is off is not part of the scorecard at all — no
        # `NA` row, because `NA` means "evidence that was meant to be here and
        # could not be measured". §4.6's status names the disabled ones instead.
        if not entry.get("enabled"):
            continue
        pairs = []
        value = _number(entry.get("score"))
        if value is None:
            pairs.append(f"{name}_score=NA")
        else:
            pairs.append(f"{name}_score={value}")
            coverage = _number(entry.get("coverage"))
            if coverage is not None:
                pairs.append(f"{name}_coverage={coverage}")
        lines.append(_pair_line(pairs))

    # Only engines that were meant to be measured and could not be are "absent";
    # a gated-off engine is not part of the scorecard. Names only - a reason can
    # carry a digit, and a digit after a word is a key the parser will invent.
    missing = [
        name
        for name, entry in engines.items()
        if entry.get("enabled") and entry.get("score") is None
    ]
    lines.append(f"absent={','.join(missing) if missing else 'none'}")

    # §4.6: enablement, measurement and movement, all printed rather than left to
    # inference. No digits in any of these lines - see the ordering rule above.
    status = scorecard_status(snap)
    lines.append(
        f"Scorecard status: {status['scorecard_status']} - "
        f"enabled: {', '.join(status['enabled']) or 'none'}; "
        f"disabled: {', '.join(status['disabled']) or 'none'}"
    )
    lines.append(f"Vector status: {status['vector_status']}")
    lines.append(f"Movement: {status['movement']}")

    text = "\n".join(lines)
    if len(text) > SCORECARD_MAX_CHARS:
        # The bound is on the block itself (§4.4). Only the absent list can grow
        # unboundedly here, and it is the least load-bearing line, so trim it
        # rather than truncate a number.
        text = "\n".join(
            f"absent={len(missing)} engines (see the card)"
            if line.startswith("absent=")
            else line
            for line in lines
        )
    return text
