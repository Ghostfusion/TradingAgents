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

__all__ = [
    "COMPOSITE_ENGINES",
    "ENGINE_GATES",
    "EVENT_NO_SNAPSHOT",
    "SCORECARD_HEADER",
    "SCORECARD_MAX_CHARS",
    "SCORECARD_PURPOSE",
    "engine_scores",
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

#: Why the event engine is absent on a pre-graph snapshot, stated once so every
#: reader prints the same reason.
EVENT_NO_SNAPSHOT = (
    "the catalyst snapshot is stamped after the graph "
    "(trading_graph._apply_strategy_overlays), and the snapshot is built before "
    "it runs - pass catalyst_snapshot to measure this engine"
)


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
    enabled = [name for name, e in engines.items() if e.get("enabled")]
    disabled = [name for name, e in engines.items() if not e.get("enabled")]
    measured = [n for n in enabled if (engines.get(n) or {}).get("score") is not None]
    if not enabled:
        status = "DISABLED"
    elif disabled or len(measured) != len(enabled):
        status = "PARTIAL"
    else:
        status = "COMPLETE"
    composite = engines.get("trade") or {}
    return {
        "scorecard_status": status,
        "enabled": enabled,
        "disabled": disabled,
        "vector_status": composite.get("status") or "UNAVAILABLE",
        "movement": "UNAVAILABLE",
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
    pairs: list[str] = []
    score = _number(comp.get("score"))
    if score is None:
        pairs.append("trade_score=NA")
    else:
        pairs.append(f"trade_score={score}")
        coverage = _number(comp.get("coverage"))
        if coverage is not None:
            pairs.append(f"trade_coverage={coverage}")
    lines.append(_pair_line(pairs, trailing=f"trade_status={status}" if status else None))

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
