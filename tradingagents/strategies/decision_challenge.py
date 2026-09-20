"""The closed-vocabulary challenge pass (design doc §10, Phase 5).

**The sharpest genuine gap (§5.1), and the LAST phase by owner instruction.**
§10's rule: after the decision, ONE additional call whose output vocabulary is
closed, and which may only invalidate.

```
CHALLENGE - you may ONLY invalidate.
Output: {invalidated: bool, ground: <(a)|(b)|(c)|none>, evidence: <packet row>}
```

The only admissible grounds are

|    | ground |
|----|--------|
| (a) | a falsifier from the ``FALSIFIERS`` list is breached |
| (b) | the decision relied on a metric with an **unresolved** contradiction |
| (c) | the decision asserts a number the packet does not carry |

**Why this is not the existing debate.** §2.3 documents the debate's failure
mode: conformity, consensus collapse, a persuasive agent dragging the group. A
closed-vocabulary pass with a materiality test has no room for it - it either
finds a mechanical breach or it does not.

**The invariant, stated precisely:** *the challenge pass may downgrade only on
one of the three closed grounds; it may not create a new caution rationale.*
Invalidation IS an increase in caution, so "cannot add caution" would be false.
It may legitimately turn ``BUY -> HOLD`` on a breached falsifier or a
materially-relied-upon unresolved contradiction; it must never turn ``BUY ->
HOLD`` because *"there is uncertainty"*, *"markets are unpredictable"*, or
*"another engine is bearish"*.

**The model proposes; this module decides.** Every ground is re-checked
mechanically against the packet and the decision before anything is downgraded -
the model's assertion is an INPUT to the check, never the check itself. Three of
§10's four rules are therefore enforced by code rather than by prompt wording:

1. **Closed vocabulary** - a ``ground`` outside ``(a)``/``(b)``/``(c)`` is
   discarded, so an invented reason for caution cannot land.
2. **Evidence must be a packet row** - an objection citing text the packet does
   not contain is discarded.
3. **Downgrade only** - the sole mutation available is
   ``decision_guardrail.downgrade_toward_hold``, which can only move toward Hold.
4. **No new caution rationale** - an ``UNCERTAINTY`` row is not a valid
   citation, and directional disagreement is not a contradiction (§8's rule,
   enforced mechanically: only a ``CONFLICT`` row classified ``unresolved`` may
   carry ground (b)).

**The materiality test (§10's correction).** *"The packet contains a
contradiction"* is dangerous as stated - a model could read ``fundamental =
bullish`` beside ``regime = bearish`` as a contradiction and invalidate, which
recreates exactly the conservatism the design exists to remove. So ground (b)
requires all three of: the metric has an unresolved contradiction, AND the
decision relied upon it. The second is checked against the decision's own text:
the metric must appear there. A contradiction the decision never mentions is
**recorded, not acted on** - §10's *"Otherwise: contradiction exists -> record
the contradiction -> do NOT invalidate."*

Advisory throughout: every failure path returns a non-invalidating result, and
nothing here can raise into a run.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "CHALLENGE_GROUNDS",
    "CHALLENGE_GROUND_LABELS",
    "ChallengeVerdict",
    "adjudicate_challenge",
    "challenge_facts",
    "challenge_prompt",
    "run_challenge",
]

#: §10's closed vocabulary. ``none`` is the "did not invalidate" member; anything
#: outside this tuple is discarded rather than mapped onto the nearest member.
CHALLENGE_GROUNDS: tuple[str, ...] = ("a", "b", "c")

CHALLENGE_GROUND_LABELS: dict[str, str] = {
    "a": "a FALSIFIERS condition is breached",
    "b": "the decision relied on a metric with an unresolved contradiction",
    "c": "the decision asserts a number the packet does not carry",
}

#: §10: *"An ``UNCERTAINTY`` entry is not a valid invalidation - the §8 rule,
#: enforced mechanically."* An absence of measurement is not evidence against a
#: thesis, so it cannot be the ground for weakening one.
_UNCERTAINTY_PREFIX = "UNCERTAINTY"

#: Decimal figures in the decision's own text - the (c) check's input. A bare
#: integer is too noisy (a horizon of "6 months", a rating of "2"), so only
#: figures with a decimal point are checked, matching
#: ``report_verifier._float_tokens``'s reasoning.
_FIGURE_RE = re.compile(r"\d+\.\d+")


class ChallengeVerdict(BaseModel):
    """The challenge pass's closed output. The model fills exactly these fields.

    ``ground`` is a plain ``str``, **not** a ``Literal``. A ``Literal`` would
    reject an invented ground at validation, which turns §10 rule 1 - *"it cannot
    invent a new reason for caution"* - into an unrecorded provider-level failure
    indistinguishable from an outage. As a ``str``, the invented ground reaches
    ``adjudicate_challenge``, which discards it and names it in the record. The
    vocabulary is stated in the field description so the model is steered; it is
    ENFORCED mechanically, where the discard is auditable.
    """

    invalidated: bool = Field(
        description=(
            "True ONLY if one of the three closed grounds is met. False otherwise, "
            "including when you merely disagree with the decision."
        )
    )
    ground: str = Field(
        description=(
            "Which closed ground the invalidation rests on: 'a' a FALSIFIERS "
            "condition is breached, 'b' the decision relied on a metric with an "
            "UNRESOLVED contradiction, 'c' the decision asserts a number the "
            "packet does not carry. 'none' when not invalidating. There is no "
            "other ground - uncertainty, unpredictability and another engine "
            "disagreeing are NOT grounds."
        )
    )
    evidence: str = Field(
        default="",
        description=(
            "The packet ROW this rests on, copied verbatim from the packet. An "
            "objection citing nothing is discarded."
        ),
    )
    metric: str = Field(
        default="",
        description=(
            "For ground 'b' only: the metric whose contradiction the decision "
            "relied on. Must be a metric named in the packet's CONFLICT rows."
        ),
    )
    reason: str = Field(
        default="",
        description="One sentence stating the breach. Recorded, never acted on.",
    )


def _norm(text: str) -> str:
    """Whitespace-normalised text, for substring checks across wrapped rows."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _row_in_packet(evidence: str, packet: str) -> bool:
    """Does the cited text appear in the packet as a row (§10 rule 2)?

    Whitespace-normalised on both sides, because a packet row is long and a model
    quoting it back will re-wrap it. Nothing shorter than a few characters counts:
    a citation of ``"5"`` would otherwise match any row carrying that digit and
    turn "an objection citing nothing" into a pass.
    """
    cited = _norm(evidence)
    if len(cited) < 4:
        return False
    return cited in _norm(packet)


def _block_rows(packet: str, heading: str) -> list[str]:
    """The rows of one packet block, note line excluded.

    The packet's blocks are ``heading`` / ``note`` / ``rows``, and a block ends at
    the next HEADING - never at an indentation change. The first version of this
    function assumed rows were the indented lines, which is false: a row prints at
    column zero (``conditions  1 declared``) and only a row's SUB-rows are
    indented. That version returned ``[]`` for every packet, so ground (a) could
    never be met - a check that always fails looks strict and is simply broken.

    **Scoping matters for ground (a).** A whole-packet scan for ``- `` lines
    would also match a bullet inside an attached report when §11's expansion is
    on, and ground (a) would then rest on a line the packet never offered as a
    falsifier. The expansion's own header is a stop for the same reason.
    """
    from tradingagents.strategies.decision_packet import (
        EXPANSION_HEADER,
        PACKET_BLOCK_HEADINGS,
    )

    stops = {*PACKET_BLOCK_HEADINGS, EXPANSION_HEADER}
    lines = str(packet or "").splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return []
    rows: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in stops:
            break
        rows.append(stripped)
    # The first line after the heading is the category note, never a row.
    return rows[1:]


def _falsifier_rows(packet: str) -> list[str]:
    """The packet's FALSIFIERS rows - the only rows ground (a) may cite."""
    return [r for r in _block_rows(packet, "FALSIFIERS") if r.startswith("- ")]


def _unresolved_metrics(packet: str) -> dict[str, str]:
    """``{metric: row}`` for every CONFLICT row classified ``unresolved``.

    Read from the packet's own ledger rows rather than recomputed, so the pass
    can only cite a contradiction the MODEL could see. That is what makes the
    check meaningful: a contradiction the packet did not print cannot be the
    ground for invalidating a decision made from it.
    """
    out: dict[str, str] = {}
    for line in str(packet or "").splitlines():
        stripped = line.strip()
        if not stripped or "[unresolved]" not in stripped:
            continue
        metric = stripped.split("  ", 1)[0].strip().lower()
        if metric:
            out[metric] = stripped
    return out


def _missing_figures(prose: str, packet: str) -> list[str]:
    """Figures the decision asserts that the packet does not carry. **Numerically.**

    A text comparison is wrong and was measured wrong: the packet prints ``4.4``
    while the decision writes ``4.40``, so every figure quoted to a different
    precision read as "not carried" and ground (c) fired on a decision that had
    invented nothing. One number printed at two precisions is ONE number - the
    repo has already had to fix this exact class once, in
    ``report_verifier._cluster_value_tokens`` (LRCX 2026-09-14).

    So both sides are parsed and compared within the same 0.5% relative tolerance
    the verifier's anchor and ``repro_check`` share, which is the tolerance the
    rest of the repo already means by "the same figure".

    Scoped to the decision's PROSE, never its own parameters: ``confidence``,
    ``position_size`` and ``stop_loss`` are the decision's own proposals, not
    assertions about the world, and checking them would make ground (c) fire on
    almost every decision - a fresh route to HOLD arriving through the check
    rather than through the model.
    """
    packet_values = [float(m) for m in _FIGURE_RE.findall(str(packet or ""))]
    missing: list[str] = []
    for raw in sorted(set(_FIGURE_RE.findall(str(prose or "")))):
        value = float(raw)
        if not any(
            abs(p - value) <= max(0.005 * max(abs(p), abs(value)), 1e-9)
            for p in packet_values
        ):
            missing.append(raw)
    return missing


def _uncertainty_rows(packet: str) -> list[str]:
    return [
        line.strip()
        for line in str(packet or "").splitlines()
        if line.strip().startswith(_UNCERTAINTY_PREFIX)
    ]


def adjudicate_challenge(
    verdict: ChallengeVerdict | None,
    *,
    packet: str,
    decision_text: str,
    decision_prose: str | None = None,
) -> dict:
    """Re-check the model's proposed invalidation mechanically. **The decider.**

    ``decision_text`` is what the model was shown (the whole rendered decision);
    ``decision_prose`` is the part that ASSERTS things about the world (the
    executive summary and the investment thesis). The grounds are checked against
    the prose - see ``_missing_figures`` for why checking the decision's own
    parameters would make ground (c) fire on almost every decision.

    Returns a dict that is always safe to record:

    ``{invalidated, ground, reason, discarded, cited, recorded_contradictions}``

    ``invalidated`` is True only when the proposed ground survived every check
    for that ground. Otherwise ``discarded`` names the check that failed - a
    discarded invalidation is a RECORD, not a silence, so a reader can see the
    pass proposed something and why it did not land.
    """
    asserted = decision_prose if decision_prose is not None else decision_text
    out: dict = {
        "invalidated": False,
        "ground": None,
        "reason": "",
        "discarded": None,
        "cited": "",
        "recorded_contradictions": [],
    }
    if verdict is None:
        out["discarded"] = "the challenge pass produced no verdict"
        return out
    out["cited"] = str(verdict.evidence or "")
    if not verdict.invalidated:
        out["ground"] = "none"
        out["reason"] = "the pass did not invalidate"
        return out

    ground = str(verdict.ground or "").strip().lower()
    # RULE 1 - closed vocabulary. An invented ground cannot land, so no new
    # caution rationale can be created by wording.
    if ground not in CHALLENGE_GROUNDS:
        out["discarded"] = (
            f"ground {verdict.ground!r} is not in the closed vocabulary "
            f"({', '.join(CHALLENGE_GROUNDS)})"
        )
        return out
    out["ground"] = ground

    # RULE 2 - the evidence must be a packet row.
    if not _row_in_packet(verdict.evidence, packet):
        out["discarded"] = "the cited evidence is not a row of the packet"
        return out

    # §8's rule, enforced mechanically: an absence of measurement is not
    # evidence against a thesis, so it can never be the ground for weakening one.
    if any(_norm(verdict.evidence) in _norm(row) for row in _uncertainty_rows(packet)):
        out["discarded"] = (
            "the citation is an UNCERTAINTY row - an unknown is not evidence "
            "against a thesis (design doc §8)"
        )
        return out

    if ground == "a":
        rows = _falsifier_rows(packet)
        if not rows or not any(_norm(verdict.evidence) in _norm(r) for r in rows):
            out["discarded"] = (
                "ground (a) requires a FALSIFIERS row; the citation is not one"
            )
            return out
        out["invalidated"] = True
        out["reason"] = (
            "a FALSIFIERS condition is breached: " + _norm(verdict.evidence)[:200]
        )
        return out

    if ground == "b":
        unresolved = _unresolved_metrics(packet)
        metric = str(verdict.metric or "").strip().lower()
        if not metric:
            # The row itself may name the metric; fall back to it, because the
            # citation was already checked to be a real packet row.
            metric = _norm(verdict.evidence).split("  ", 1)[0].strip().lower()
        # MATERIALITY, leg 2: the metric must have an UNRESOLVED contradiction.
        # `basis_difference` and `defect` are excluded by construction - §10
        # names `unresolved` as the only class this ground may rest on.
        if metric not in unresolved:
            out["discarded"] = (
                f"{metric or 'the cited metric'!r} has no UNRESOLVED contradiction "
                "in the packet's ledger (only `unresolved` may carry ground (b))"
            )
            return out
        # MATERIALITY, legs 1 and 3: the decision must have RELIED on it. The
        # decision's own text naming the metric is the only in-run evidence of
        # reliance; a contradiction the decision never mentions is recorded
        # instead of acted on (§10).
        if metric and metric not in _norm(asserted).lower():
            out["recorded_contradictions"].append(unresolved[metric])
            out["discarded"] = (
                f"{metric!r} has an unresolved contradiction, but the decision "
                "does not rely on it - contradiction recorded, not invalidated"
            )
            return out
        out["invalidated"] = True
        out["reason"] = (
            f"the decision relies on {metric}, which has an unresolved "
            f"contradiction: {unresolved[metric][:160]}"
        )
        return out

    # ground == "c" - checked, not trusted: the decision must ACTUALLY assert a
    # figure the packet does not carry. A model that claims (c) while every
    # figure it printed is in the packet is discarded.
    missing = _missing_figures(asserted, packet)
    if not missing:
        out["discarded"] = (
            "ground (c) claims the decision asserts a number the packet does not "
            "carry, but every figure the decision states appears in the packet"
        )
        return out
    out["invalidated"] = True
    out["reason"] = (
        "the decision asserts a figure the packet does not carry: "
        + ", ".join(missing[:5])
    )
    return out


def challenge_prompt(packet: str, decision_text: str) -> str:
    """The one challenge call's prompt. **Closed vocabulary, stated as a contract.**

    The three grounds are printed with their exact boundaries, including the two
    that are NOT grounds - uncertainty and another engine disagreeing - because a
    model told only what IS allowed will reach for the nearest plausible
    substitute for what is not.
    """
    return (
        "CHALLENGE - you may ONLY invalidate.\n\n"
        "Below is the DECISION and the DECISION PACKET it was made from. You have "
        "exactly three grounds to invalidate the decision, and no others:\n\n"
        "  (a) a condition in the packet's FALSIFIERS block is breached by the "
        "packet's own numbers;\n"
        "  (b) the decision relies on a metric that has an UNRESOLVED "
        "contradiction in the packet's CONFLICT rows;\n"
        "  (c) the decision asserts a number the packet does not carry.\n\n"
        "These are NOT grounds, and citing them will be discarded:\n"
        "  - uncertainty, unpredictability, or 'something could go wrong';\n"
        "  - another engine or analyst being bearish - directional disagreement "
        "is the normal state of evidence, not a contradiction;\n"
        "  - any packet row marked UNCERTAINTY - an unknown is not evidence "
        "against a thesis;\n"
        "  - a CONFLICT row classified `basis_difference` or `defect` - only "
        "`unresolved` may carry ground (b).\n\n"
        "`evidence` must be a row copied verbatim from the packet. An objection "
        "citing nothing is discarded.\n\n"
        "If no ground is met, return invalidated=false and ground='none'. "
        "Disagreeing with the decision is not a ground.\n\n"
        "=== DECISION ===\n"
        f"{decision_text}\n\n"
        "=== DECISION PACKET ===\n"
        f"{packet}\n"
    )


def _no_invalidation(cfg: dict | None, discarded: str) -> dict:
    """A non-invalidating outcome, in the SAME key set as an adjudicated one.

    Every return path in ``run_challenge`` goes through this or
    ``adjudicate_challenge``. A short-circuited path that omitted ``invalidated``
    would make a consumer guess whether the key exists before reading it - the
    uniform-payload rule ``report_verifier`` already states for its own entries.
    """
    return {
        **challenge_facts(cfg),
        "invalidated": False,
        "ground": None,
        "reason": "",
        "discarded": discarded,
        "cited": "",
        "recorded_contradictions": [],
        "proposed": None,
    }


def run_challenge(
    structured_llm: Any,
    *,
    packet: str,
    decision_text: str,
    decision_prose: str | None = None,
    cfg: dict | None = None,
) -> dict:
    """Run the pass and adjudicate it. **Never raises; never invalidates on failure.**

    A provider failure, an unparsable verdict, or a missing packet all return a
    non-invalidating result with a named reason. The alternative - treating a
    failure as an invalidation - would make an outage silently downgrade every
    decision, which is the conservatism §10 exists to remove arriving through the
    back door.
    """
    if not challenge_facts(cfg)["challenge_enabled"]:
        return _no_invalidation(cfg, "challenge pass is off")
    if not str(packet or "").strip():
        return _no_invalidation(cfg, "no packet in state - nothing to challenge against")
    if structured_llm is None:
        return _no_invalidation(cfg, "no structured LLM available")
    try:
        verdict = structured_llm.invoke(challenge_prompt(packet, decision_text))
        if not isinstance(verdict, ChallengeVerdict):
            verdict = ChallengeVerdict.model_validate(verdict)
    except Exception as exc:  # noqa: BLE001 - advisory; never invalidates on failure
        logger.warning("challenge pass failed (%s); not invalidating", exc)
        return _no_invalidation(cfg, f"challenge call failed: {type(exc).__name__}")
    out = adjudicate_challenge(
        verdict,
        packet=packet,
        decision_text=decision_text,
        decision_prose=decision_prose,
    )
    out.update({k: v for k, v in challenge_facts(cfg).items() if k not in out})
    out["proposed"] = {
        "invalidated": bool(getattr(verdict, "invalidated", False)),
        "ground": str(getattr(verdict, "ground", "") or ""),
        "reason": str(getattr(verdict, "reason", "") or "")[:300],
    }
    return out


def challenge_facts(cfg: dict | None = None) -> dict:
    """``{challenge_enabled}`` for the card and the runner.

    The ground is NOT returned here: it is a property of a verdict, and a
    defaulted ``None`` in a facts dict is exactly the "row whose producer has not
    run reads as a measurement" defect this repo keeps finding. ``run_challenge``
    merges these keys into the adjudicated outcome, which carries the real one.
    """
    return {"challenge_enabled": bool((cfg or {}).get("enable_decision_challenge"))}
