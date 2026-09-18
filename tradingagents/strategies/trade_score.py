"""`TradeScore` (WP-11) — the four-engine decision composite, and its ladder.

``TradeScore = 0.40 F + 0.25 T + 0.15 R + 0.20 K`` over the four engines the
owner named (master §1.4/§1.5, plan §8). It is **the decision composite**; the
six-engine ``35/20/15/15/7.5/7.5`` table is the **research allocation** — a
different object with a different job and a different name (master rule 17).

Five rules this module exists to hold:

1. **It combines, it does not measure.** The input is ``{engine: score}`` — the
   engines are separate modules and are read here only as numbers. No engine's
   internals are imported, and `NewsScore` / `SentimentScore` / `EventScore` are
   **not** components: master rule 17 says an engine joins the decision
   composite only by an explicit decision, never by adjacency, so a score handed
   in under any other name is dropped **by name** — printed in the basis, never
   silently weighted as a fifth or sixth factor.
2. **`NA` is not `0`.** A missing — or unusable — engine leaves the denominator
   and lowers ``coverage``; a composite below its floor is withheld **with its
   reason**. Never 0, never a neutral 50.
3. **No fabricated coefficients.** The default vector is the owner's published
   ``0.40 / 0.25 / 0.15 / 0.20`` — the one he re-affirmed for this object — and
   the basis prints it as his, with its unvalidated status. A supplied vector is
   printed instead. Nothing is invented here and no equal-weight fallback is
   applied silently.
4. **No configuration is a promotion.** A vector's status is the ladder
   ``RESEARCH_ONLY -> VALIDATED -> CONTRACT_MIGRATION -> PRODUCTION``, each rung
   reached only by its own recorded evidence, contiguously from the bottom
   (`PROMOTION_EVIDENCE`). This module reads no configuration at all, so a gate
   flip cannot promote a vector; a status *request* above the evidence is
   refused and the refusal is printed.
5. **Never a gate, never a size, never an `opportunity_score`.** The composite
   is advisory text. The executor's 17 ``GATE_PRECEDENCE`` checks and the two
   tier ``risk_multiplier`` never read a score, `execution_contract`'s
   ``opportunity_score()`` stays ``None``, and the sizing contract
   (`strategies/contract.build_position_contract`) takes no score. A maximal
   `TradeScore` therefore changes nothing when the gate is ``BLOCK`` — the
   acceptance case ``F 92 / T 85 / R 78 / K 35`` reads *"high quality, strong
   setup, favourable regime, high risk -> NO NEW RISK"*, and the "NO NEW RISK"
   is the gate's answer, not this module's.

`RiskScore` is a `TradeScore` engine, not a risk gate (master rule 18): it
contributes the ``K`` component here, and the hard gates operate **downstream**
of the composite.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from .score_engine import combine

#: The gate that puts this engine's leaf on the advisory surface. Named here so
#: the leaf, the run-card block and the `.env.example` row cannot drift; the
#: module itself never reads it (rule 4 - a gate is not a promotion).
GATE_NAME = "enable_trade_score"

# --- The four engines ------------------------------------------------------

#: The four engines the decision composite is defined over, in weight order.
#: ``regime`` is the market/regime engine and ``risk`` is `RiskScore` (100 =
#: low risk). Fundamental, Technical, Regime and Risk only - master rule 17.
ENGINE_ORDER: tuple[str, ...] = ("fundamental", "technical", "regime", "risk")

ENGINE_LETTERS: dict[str, str] = {
    "fundamental": "F",
    "technical": "T",
    "regime": "R",
    "risk": "K",
}

#: Accepted spellings, resolved to the one canonical name per engine. The plan
#: writes the composite in letters (``F 92 / T 85 / R 78 / K 35``); the engine
#: names are what the leaves pass. Two spellings of the same engine in one call
#: is an error, never a silent overwrite (master rule 3, one number one
#: producer).
_ALIASES: dict[str, str] = {
    "f": "fundamental",
    "fundamental": "fundamental",
    "fundamental_score": "fundamental",
    "t": "technical",
    "technical": "technical",
    "technical_score": "technical",
    "r": "regime",
    "regime": "regime",
    "regime_score": "regime",
    "k": "risk",
    "risk": "risk",
    "risk_score": "risk",
}

# --- The owner's vector, and the vector that is NOT this object ------------

#: The owner's published decision-composite vector, re-affirmed 2026-09-17 for
#: this object (master §1.4 ledger; plan §8). It is his - not fabricated here,
#: not equal-weighted, and not validated: Phase C measures it, and until then
#: the composite ships `RESEARCH_ONLY` with this vector *printed*.
ENGINE_WEIGHTS: dict[str, float] = {
    "fundamental": 0.40,
    "technical": 0.25,
    "regime": 0.15,
    "risk": 0.20,
}

#: The six-engine research allocation (master §1.4). A **different object** -
#: research attribution, not the decision composite - and deliberately not read
#: by :func:`trade_score`: `NewsScore` and `SentimentScore` do not become a
#: fifth/sixth `TradeScore` factor by being drawn next to the other four. Kept
#: as data so the two tables can be compared without being confused for one.
RESEARCH_ALLOCATION: dict[str, float] = {
    "fundamental": 0.35,
    "technical": 0.20,
    "regime": 0.15,
    "risk": 0.15,
    "news": 0.075,
    "sentiment": 0.075,
}

#: How many of the four engines must be present for a composite to mean
#: anything. A "composite" of one engine is that engine, mislabelled: the whole
#: reason the design keeps the engines separate (master §1.1) is that four
#: numbers say more than their average. The floor is a count and the engine set
#: is fixed at four, so it can never exceed the component set.
COMPOSITE_MIN_COVERAGE = 2

#: No band table, deliberately. A label on a composite is a *rating*, and master
#: rule 2 keeps a score out of the rating business; more concretely, the band
#: that matters (`ALLOW` / `REDUCE` / `BLOCK`) is the executor's
#: ``GATE_PRECEDENCE`` verdict, downstream of this number and unreachable from
#: it. The table is declared empty rather than absent so the choice is visible
#: and a test can assert it.
TRADE_BANDS: tuple = ()

# --- The promotion ladder --------------------------------------------------

STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"
STATUS_VALIDATED = "VALIDATED"
STATUS_CONTRACT_MIGRATION = "CONTRACT_MIGRATION"
STATUS_PRODUCTION = "PRODUCTION"

#: The ladder (owner Q2, plan §8). Order is the meaning: a step is only reached
#: from the one below it, and each step has its own evidence. Note `ADVISORY` is
#: not on it: that is the status of a *deterministic diagnostic* (a single
#: engine's own read), and a combination of engines is never one.
PROMOTION_LADDER: tuple[str, ...] = (
    STATUS_RESEARCH_ONLY,
    STATUS_VALIDATED,
    STATUS_CONTRACT_MIGRATION,
    STATUS_PRODUCTION,
)

#: What each rung requires. `RESEARCH_ONLY` is the default state of any vector
#: nobody has measured; each rung above it requires a **record** - a mapping that
#: names its producer and its result - not a flag and not a setting. The test
#: that guards this: a boolean, a string, or a config gate never promotes.
PROMOTION_EVIDENCE: dict[str, str] = {
    STATUS_RESEARCH_ONLY: "nothing - the default state of an unmeasured vector",
    STATUS_VALIDATED: (
        "a WP-10 measurement of THIS vector over the EODHD US panel "
        "(IC / rank IC / ICIR / decile spread / monotonicity / OOS, vector_id "
        "and universe recorded); the research allocation is not this vector"
    ),
    STATUS_CONTRACT_MIGRATION: (
        "a named consumer contract that makes the number a machine-read input "
        "(schema + version bump + migration test), decided, not inferred"
    ),
    STATUS_PRODUCTION: (
        "the owner's production decision naming the vector version and the "
        "date, recorded against the validated measurement"
    ),
}


def _is_evidence(record) -> bool:
    """A rung's evidence is a **record** (a non-empty mapping), never a flag.

    ``{"VALIDATED": True}`` is a claim with nothing behind it and does not
    promote; ``{"VALIDATED": {"vector_id": ..., "rank_ic": ...}}`` does.
    """
    return isinstance(record, Mapping) and bool(record)


def promotion_state(*, evidence: Mapping | None = None, requested=None) -> dict:
    """Where this vector actually stands on the ladder, and what a request got.

    ``evidence`` is ``{step: record}``. The ladder is walked **contiguously from
    the bottom**: a rung counts only when its own record is present, and a rung
    above a missing one cannot be reached even if its own record is there.

    ``requested`` is the status the caller asked for (the leaf's, or a config
    decision's). It is clamped down to the evidenced rung, never up, and the
    refusal is returned so the printed block can say so. An unknown rung is a
    closed-vocabulary error, not a default.

    Returns ``{"status", "requested", "refused", "steps", "evidence_required",
    "evidence_present", "rejected", "missing"}``.
    """
    ev = dict(evidence or {})
    reached: list[str] = []
    step = PROMOTION_LADDER[0]
    for rung in PROMOTION_LADDER[1:]:
        if _is_evidence(ev.get(rung)):
            step = rung
            reached.append(rung)
        else:
            break
    # Records supplied for a rung that is not evidence (a flag, an empty dict,
    # a string) are named, so a caller cannot think a claim promoted anything.
    rejected = sorted(
        rung for rung in PROMOTION_LADDER[1:] if rung in ev and not _is_evidence(ev[rung])
    )
    request = None
    if requested is not None:
        request = str(requested).strip().upper()
        if request not in PROMOTION_LADDER:
            raise ValueError(
                f"status must be one of {list(PROMOTION_LADDER)}, got {requested!r}"
            )
    refused = None
    if request is not None and PROMOTION_LADDER.index(request) > PROMOTION_LADDER.index(step):
        refused = (
            f"status {request} refused by {step}: it requires "
            f"{PROMOTION_EVIDENCE[request]}; configuration is not evidence"
        )
    return {
        "status": step,
        "requested": request,
        "refused": refused,
        "steps": list(PROMOTION_LADDER),
        "evidence_required": dict(PROMOTION_EVIDENCE),
        "evidence_present": reached,
        "rejected": rejected,
        "missing": list(PROMOTION_LADDER[PROMOTION_LADDER.index(step) + 1:]),
    }


# --- Input normalisation ---------------------------------------------------


def _canonical(key) -> str | None:
    """The canonical engine name for a key, or ``None`` when it is not one."""
    if not isinstance(key, str):
        return None
    return _ALIASES.get(key.strip().lower())


def _normalise(mapping: Mapping, *, what: str) -> dict:
    """``{canonical engine: value}``, or ``ValueError`` on two keys for one.

    A key that is not one of the four engines is **excluded**, never weighted:
    master rule 17 - an engine joins the decision composite only by an explicit
    decision, never by adjacency.
    """
    out: dict = {}
    origin: dict[str, str] = {}
    excluded: dict[str, str] = {}
    for key, value in mapping.items():
        name = _canonical(key)
        if name is None:
            excluded[str(key)] = "not a TradeScore engine (master rule 17)"
            continue
        if name in out:
            raise ValueError(
                f"{what}: two entries for {name!r} ({origin[name]!r} and {key!r}); "
                "one number, one producer"
            )
        out[name] = value
        origin[name] = str(key)
    out["__excluded__"] = excluded  # returned to the caller, not weighted
    return out


def _coerce(value) -> tuple[float | None, str | None]:
    """A usable 0-100 score, or ``(None, reason)`` - never 0, never 50."""
    if isinstance(value, bool) or value is None:
        return None, None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, f"not a number ({value!r})"
    if not math.isfinite(v):
        return None, f"not finite ({value!r})"
    if not 0.0 <= v <= 100.0:
        return None, f"outside the producer-owned 0..100 scale ({v})"
    return v, None


# --- The composite ---------------------------------------------------------


def trade_score(
    engine_scores,
    *,
    weights: Mapping | None = None,
    status=None,
    evidence: Mapping | None = None,
) -> dict:
    """The four-engine decision composite, or withheld with its reason.

    ``engine_scores`` is ``{engine: 0-100}`` for the engines in
    :data:`ENGINE_ORDER` (letters accepted; anything else is excluded by name).
    An engine that is absent, ``None``, non-numeric or outside 0..100 is **not**
    a zero: it leaves the denominator and lowers ``coverage``.

    ``weights`` overrides the owner's vector and is printed; ``status`` is a
    *request* for a ladder rung; ``evidence`` is ``{rung: record}``. The returned
    ``status`` is the evidenced rung, never the requested one above it (rule 4).

    Returns ``{"score", "coverage", "components", "weights", "weights_source",
    "status", "ladder", "present", "absent", "invalid", "excluded", "withheld",
    "band", "weights_basis", "basis"}``. ``score`` is ``None`` below the floor -
    never 0, never 50 - and there is deliberately **no** ``opportunity_score``
    key (the executor owns that slot and it stays ``null``).
    """
    if not isinstance(engine_scores, Mapping):
        raise ValueError(
            f"engine_scores must be a mapping of {{engine: score}}, got "
            f"{type(engine_scores).__name__}"
        )
    normalised = _normalise(engine_scores, what="engine_scores")
    excluded = normalised.pop("__excluded__")
    raw = {name: normalised.get(name) for name in ENGINE_ORDER}
    comps: dict[str, float | None] = {}
    invalid: dict[str, str] = {}
    for name in ENGINE_ORDER:
        value, reason = _coerce(raw[name])
        comps[name] = value
        if reason is not None:
            invalid[name] = reason

    if weights is None:
        w = dict(ENGINE_WEIGHTS)
        weights_source = "owner"
        weights_basis = (
            "owner weights "
            + ", ".join(f"{ENGINE_LETTERS[k]}={v:g}" for k, v in ENGINE_WEIGHTS.items())
            + " (published and re-affirmed for the decision composite, "
            "unvalidated until Phase C measures it)"
        )
    else:
        if not isinstance(weights, Mapping):
            raise ValueError(f"weights must be a mapping, got {type(weights).__name__}")
        supplied = _normalise(weights, what="weights")
        excluded.update(supplied.pop("__excluded__"))
        w = {}
        for name, value in supplied.items():
            try:
                w[name] = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"weights[{name!r}] is not a number: {value!r}") from exc
        weights_source = "supplied"
        weights_basis = (
            "supplied weights "
            + ", ".join(f"{ENGINE_LETTERS[k]}={v:g}" for k, v in sorted(w.items()))
        )

    combined = combine(comps, weights=w, min_coverage=COMPOSITE_MIN_COVERAGE)
    ladder = promotion_state(evidence=evidence, requested=status)

    present = [name for name in ENGINE_ORDER if comps[name] is not None]
    absent = [name for name in ENGINE_ORDER if comps[name] is None and name not in invalid]
    basis_bits = [
        f"TradeScore [{ladder['status']}]: {weights_basis}",
        f"coverage {combined['coverage']:.0%} over {len(present)} of "
        f"{len(ENGINE_ORDER)} engines ({', '.join(ENGINE_LETTERS[n] + '/' + n for n in present) or 'none'})",
    ]
    if absent:
        basis_bits.append(f"absent (NA, never 0): {', '.join(absent)}")
    if invalid:
        basis_bits.append(
            "unusable (left out, never 0): "
            + ", ".join(f"{name} {reason}" for name, reason in sorted(invalid.items()))
        )
    if excluded:
        basis_bits.append(
            "excluded, not a decision-composite engine: "
            + ", ".join(sorted(excluded))
        )
    if combined.get("withheld"):
        basis_bits.append(f"WITHHELD ({combined['withheld']})")
    if ladder["refused"]:
        basis_bits.append(f"REFUSED ({ladder['refused']})")
    if ladder["rejected"]:
        basis_bits.append(
            "evidence rejected (a record is required, not a flag): "
            + ", ".join(ladder["rejected"])
        )
    basis_bits.append(
        f"floor {COMPOSITE_MIN_COVERAGE} engines; no band table (a composite "
        "label is a rating - master rule 2, and the ALLOW/REDUCE/BLOCK verdict "
        "is the executor's, downstream); advisory only - never a gate, never a "
        "size, never an opportunity_score"
    )
    return {
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
        "components": {
            name: {
                "letter": ENGINE_LETTERS[name],
                "raw": raw[name],
                "value": comps[name],
                "weight": w.get(name, 0.0),
                "state": (
                    "scored"
                    if comps[name] is not None
                    else invalid.get(name, "NA")
                ),
            }
            for name in ENGINE_ORDER
        },
        "weights": w,
        "weights_source": weights_source,
        "weights_basis": weights_basis,
        "status": ladder["status"],
        "ladder": ladder,
        "present": present,
        "absent": absent,
        "invalid": invalid,
        "excluded": excluded,
        "withheld": combined.get("withheld"),
        "band": None,
        "basis": " | ".join(basis_bits),
    }


# --- The printed block -----------------------------------------------------


def format_trade_score(res: dict, *, ticker: str | None = None) -> str:
    """Render the composite: its weights, its status and its coverage.

    Pure text, no I/O: the leaf's tool text and the run-card block both read the
    same dict, so a reader can recompute the printed number from the printed
    attribution rows instead of quoting it.
    """
    res = res or {}
    head = "## TradeScore"
    if ticker:
        head += f" - {ticker}"
    lines = [
        f"{head} (advisory; {res.get('status')})",
        "",
        "Four-engine decision composite "
        + " + ".join(
            f"{res.get('components', {}).get(n, {}).get('weight', 0.0):g}"
            f"{ENGINE_LETTERS[n]}"
            for n in ENGINE_ORDER
        )
        + ". Advisory only: never a gate, never a size, never an opportunity_score. "
        "The hard gates operate downstream and block regardless of this number.",
        "",
    ]
    for name in ENGINE_ORDER:
        entry = (res.get("components") or {}).get(name) or {}
        label = f"{name} ({entry.get('letter')}, weight {entry.get('weight', 0.0):g})"
        if entry.get("value") is None:
            lines.append(f"- {label}: unavailable - {entry.get('state')}")
        else:
            lines.append(
                f"- {label}: {entry['value']:.1f}/100"
                f" (raw {entry.get('raw')})"
            )
    if res.get("score") is None:
        lines.append(f"- composite: unavailable - {res.get('withheld')}")
    else:
        lines.append(
            f"- composite [{res.get('status')}]: {res['score']:.2f}/100 - "
            f"{res.get('weights_basis')}, renormalised over the engines "
            f"measured; coverage {(res.get('coverage') or 0.0):.0%}"
        )
    excluded = res.get("excluded") or {}
    if excluded:
        lines.append("")
        lines.append(
            "excluded by name (rule 17 - an engine joins the decision composite "
            "only by an explicit decision, never by adjacency): "
            + ", ".join(sorted(excluded))
        )
    lines.append("")
    lines.append(f"basis: {res.get('basis')}")
    return "\n".join(lines)


__all__ = [
    "COMPOSITE_MIN_COVERAGE",
    "ENGINE_LETTERS",
    "ENGINE_ORDER",
    "ENGINE_WEIGHTS",
    "GATE_NAME",
    "PROMOTION_EVIDENCE",
    "PROMOTION_LADDER",
    "RESEARCH_ALLOCATION",
    "STATUS_CONTRACT_MIGRATION",
    "STATUS_PRODUCTION",
    "STATUS_RESEARCH_ONLY",
    "STATUS_VALIDATED",
    "TRADE_BANDS",
    "format_trade_score",
    "promotion_state",
    "trade_score",
]
