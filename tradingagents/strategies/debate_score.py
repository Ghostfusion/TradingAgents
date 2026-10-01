"""P2 — Debate scoring, termination, severity triage, entrenchment, reweight.

Pure deterministic functions (no LLM) backing the two-layer judiciary:

- ``debate_score`` / ``information_gain`` — evidence × novelty × constraint
  scoring with config weights (design §4.3).
- ``termination_check`` — plateau / consensus-exit / hard cap (design §4.4).
- ``classify_severity`` — R1' L1 severity triage replacing a binary gate.
- ``entrenchment_index`` / ``divergence_check`` / ``reweight_to_baseline`` —
  R2' artificial-consensus + entrenchment machinery.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .debate_claim import ABSTAIN, QUALITATIVE, UNVERIFIED, VALID, VIOLATED

# Severity tiers (mirror L1ExecutionContext.severity_tier and l1_action).
GREEN = "GREEN"
SOFT_WARNING = "SOFT_WARNING"
RETRYABLE_ERROR = "RETRYABLE_ERROR"
HARD_BREACH = "HARD_BREACH"

PROCEED = "PROCEED"
APPLY_PENALTY_AND_PROCEED = "APPLY_PENALTY_AND_PROCEED"
TRIGGER_REGEN = "TRIGGER_REGEN"
ABORT_TO_BASELINE = "ABORT_TO_BASELINE"

DEFAULT_WEIGHTS = {"evidence": 0.6, "novelty": 0.25, "constraint": 0.15}


# ---------------------------------------------------------------------------
# Scoring (design §4.3)
# ---------------------------------------------------------------------------


def claim_stats(verifications: Sequence[dict]) -> dict:
    """Aggregate verification rows into {n, valid, violated, abstain, ...}."""
    n = len(verifications)
    return {
        "n": n,
        "valid": sum(1 for v in verifications if v.get("status") == VALID),
        "violated": sum(1 for v in verifications if v.get("status") == VIOLATED),
        "abstain": sum(1 for v in verifications if v.get("status") == ABSTAIN),
        "unverified": sum(1 for v in verifications if v.get("status") == UNVERIFIED),
        "qualitative": sum(1 for v in verifications if v.get("status") == QUALITATIVE),
    }


def evidence_quality(verifications: Sequence[dict]) -> float | None:
    """Avg. claim validity share over verifiable rows; None on no rows."""
    if not verifications:
        return None
    n = len(verifications)
    return sum(1 for v in verifications if v.get("is_valid")) / n


def novelty_gain(
    claims: Sequence[dict], prior: Sequence[dict], metric_key: str = "metric_name"
) -> float | None:
    """Share of this turn's claims never seen in prior rounds; None if none."""
    if not claims:
        return None
    seen = {c.get(metric_key) for c in prior if c.get(metric_key)}
    novel = [c for c in claims if c.get(metric_key) and c.get(metric_key) not in seen]
    return len(novel) / len(claims)


def debate_score(
    verifications: Sequence[dict],
    claims: Sequence[dict],
    prior_claims: Sequence[dict],
    weights: dict | None = None,
    constraint_ok: float = 1.0,
) -> dict:
    """Weighted debate score for one debater turn -> {score, evidence, novelty, ...}."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    ev = evidence_quality(verifications) or 0.0
    nv = novelty_gain(claims, prior_claims) or 0.0
    score = w["evidence"] * ev + w["novelty"] * nv + w["constraint"] * constraint_ok
    return {
        "score": round(float(score), 6),
        "evidence": round(float(ev), 6),
        "novelty": round(float(nv), 6),
        "constraint_ok": float(constraint_ok),
        "weights": dict(w),
    }


def information_gain(current: dict, prior: dict | None) -> float | None:
    """Round-over-round marginal novelty gain; None when no prior round."""
    if prior is None or current.get("novelty") is None or prior.get("novelty") is None:
        return None
    return round(float(current["novelty"]) - float(prior["novelty"]), 6)


# ---------------------------------------------------------------------------
# Termination (design §4.4)
# ---------------------------------------------------------------------------


def termination_check(
    score_series: Sequence[dict],
    *,
    max_rounds: int,
    min_gain: float = 0.05,
    stop_consecutive: int = 2,
    consensus_score: float | None = None,
    consensus_thresh: float = 0.85,
    hard_abort: bool = False,
) -> tuple[str, str]:
    """Decide whether the debate continues.

    Returns ``(decision, reason)`` with decision ∈ {"continue", "stop"}.
    Precedence: hard abort > hard cap > consensus exit > plateau.
    """
    rounds = len(score_series)
    if hard_abort:
        return "stop", "L1 hard breach on round 1 (fast-abort)"
    if rounds >= max_rounds:
        return "stop", f"hard cap ({max_rounds} rounds)"
    if consensus_score is not None and consensus_score >= consensus_thresh:
        return "stop", f"independent consensus {consensus_score:.2f} >= {consensus_thresh}"

    if rounds >= 2:
        gains = []
        for i in range(1, rounds):
            g = information_gain(score_series[i], score_series[i - 1])
            if g is not None:
                gains.append(g)
        if len(gains) >= stop_consecutive and all(
            g <= min_gain for g in gains[-stop_consecutive:]
        ):
            return "stop", f"information-gain plateau ({min_gain} for {stop_consecutive})"
    return "continue", ""


# ---------------------------------------------------------------------------
# R1' severity triage
# ---------------------------------------------------------------------------


def classify_severity(
    verifications: Sequence[dict],
    *,
    regen_count: int = 0,
    regen_max: int = 1,
    schema_ok: bool = True,
) -> dict:
    """Map L1 verification results into the severity tier + action (R1').

    Returns ``{severity_tier, l1_action, penalty_score, hard_gate_passed,
    reasons[]}``. Penalty is a 0..100 deterministic deduction derived from the
    violated|unverified share; soft violations forward to L2 annotated.
    """
    if not schema_ok:
        return {
            "severity_tier": HARD_BREACH,
            "l1_action": ABORT_TO_BASELINE,
            "penalty_score": 100.0,
            "hard_gate_passed": False,
            "reasons": ["schema malformed / unparseable"],
        }

    stats = claim_stats(verifications)
    n = stats["n"]
    violated = stats["violated"]
    unverified = stats["unverified"]
    abstain = stats["abstain"]

    if n and violated:
        return {
            "severity_tier": HARD_BREACH,
            "l1_action": TRIGGER_REGEN if regen_count < regen_max else ABORT_TO_BASELINE,
            "penalty_score": 100.0,
            "hard_gate_passed": False,
            "reasons": [f"{violated}/{n} claims violated (hard breach)"],
            "regen_requested": regen_count < regen_max,
        }

    if n and n == abstain:
        return {
            "severity_tier": RETRYABLE_ERROR,
            "l1_action": TRIGGER_REGEN if regen_count < regen_max else ABORT_TO_BASELINE,
            "penalty_score": 50.0,
            "hard_gate_passed": False,
            "reasons": ["all claims abstained (no grounded evidence)"],
            "regen_requested": regen_count < regen_max,
        }

    penalty = round(100.0 * (violated + unverified) / n, 2) if n else 0.0
    if unverified or abstain:
        return {
            "severity_tier": SOFT_WARNING,
            "l1_action": APPLY_PENALTY_AND_PROCEED,
            "penalty_score": penalty,
            "hard_gate_passed": True,
            "reasons": [f"{unverified} unverified / {abstain} abstained claims"],
        }
    return {
        "severity_tier": GREEN,
        "l1_action": PROCEED,
        "penalty_score": 0.0,
        "hard_gate_passed": True,
        "reasons": ["all quantitative claims verified"],
    }


# ---------------------------------------------------------------------------
# R2' entrenchment + divergence + reweight
# ---------------------------------------------------------------------------


def _safe_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two real vectors; 0 when degenerate."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def entrenchment_index(
    round_vec: Sequence[float],
    prev_vec: Sequence[float],
    alloc: float | None,
    prev_alloc: float | None,
) -> float:
    """I_entrench = CosineSim(v_R, v_{R-1}) * (1 - |ΔAlloc|/Alloc_{R-1}).

    Bounds 0..1; > τ_entrench => entrenchment penalty. When allocation data is
    absent the allocation factor is 1.0 (pure semantic overlap).
    """
    if not round_vec or not prev_vec:
        return 0.0
    sim = _safe_cosine(round_vec, prev_vec)
    if alloc is None or prev_alloc is None or prev_alloc == 0:
        return float(sim)
    factor = 1.0 - min(1.0, abs(alloc - prev_alloc) / abs(prev_alloc))
    return round(float(sim * factor), 6)


def divergence_check(
    bull_score: float | None,
    bear_score: float | None,
    divergence_min: float = 0.15,
    artificial: bool = False,
) -> dict:
    """|bull-bear| below the floor (or explicit artifact) -> consensus flag.

    Returns ``{artificial_consensus, divergence_delta, flag}``.
    """
    if artificial:
        return {"artificial_consensus": True, "divergence_delta": 0.0, "flag": True}
    if bull_score is None or bear_score is None:
        return {"artificial_consensus": False, "divergence_delta": None, "flag": False}
    divergence = round(abs(float(bull_score) - float(bear_score)), 6)
    flag = divergence < divergence_min
    return {"artificial_consensus": flag, "divergence_delta": divergence, "flag": flag}


def reweight_to_baseline(
    w_debate: float,
    w_baseline: float,
    alpha: float = 0.5,
) -> float:
    """W_final = (1 - alpha) * W_debate + alpha * W_baseline."""
    return round((1 - alpha) * w_debate + alpha * w_baseline, 6)


# ---------------------------------------------------------------------------
# L1's dimensioned rubric (design §4.3 / §4.5)
# ---------------------------------------------------------------------------

# The six names the L2 judge scores - its four ``JudgeDimension`` members plus
# ``rebuttal_effectiveness`` and ``entrenchment_detected`` - so the two tiers
# can be read dimension-for-dimension. L1 fills the four it can MEASURE.
#
# They are reported under their OWN key (``l1_rubric``) and are never merged
# into ``judge_scores``. A deterministic measurement and a stochastic judge
# opinion must not share a dict, or some consumer will average them: this is
# the same reason ``research_decision.json``'s ``opportunity_score`` is null
# rather than the judge's rubric mean.
L1_RUBRIC_DIMENSIONS = (
    "empirical_grounding",
    "downside_tail_risk_weight",
    "catalyst_clarity",
    "assumption_sensitivity",
    "rebuttal_effectiveness",
    "entrenchment_detected",
)
# Cosine-overlap at or above which a role is judged to be repeating itself
# (design §4.5 R2'). A parameter default, not a config key - ``divergence_check``
# pins its own floor the same way.
DEFAULT_ENTRENCHMENT_THRESHOLD = 0.8
# Severities that count toward ``downside_tail_risk_weight``.
HIGH_SEVERITIES = frozenset({"HIGH", "CRITICAL"})
# Relative disagreement above which two values on the same metric are a
# contradiction rather than rounding.
REBUTTAL_TOLERANCE_PCT = 1.0


def _l1_dim(value, reason: str) -> dict:
    """One rubric member: ``{value, status, reason}``.

    ``status`` is ``OK`` / ``NO_SOURCE`` with ``NO_SOURCE`` **iff** ``value``
    is ``None`` - the same contract the §103 price members use.
    """
    return {
        "value": value,
        "status": "OK" if value is not None else "NO_SOURCE",
        "reason": reason,
    }


def direct_challenge_share(
    claims: Sequence[dict],
    opponent_claims: Sequence[dict],
    tolerance_pct: float = REBUTTAL_TOLERANCE_PCT,
) -> float | None:
    """Share of this turn's quantitative claims that contradict an opponent.

    ``rebuttal_effectiveness`` at L2 is the judge's read of how directly an
    argument invalidated the opponent's specific premises, which a rule cannot
    see. What a rule CAN see is whether the turn actually met the opponent's
    numbers: a claim on the same metric as an opponent's earlier claim, at a
    different value, is a direct challenge to a stated premise. That is the
    deterministic floor for this dimension - deliberately about the opponent's
    premises, not about speaking at length.

    ``None`` when there is nothing to rebut (no opposing quantitative claim, or
    this turn made no quantitative claim of its own), never ``0.0``: an empty
    turn is not an ineffective one.
    """
    mine = [
        c
        for c in claims
        if str(c.get("kind", "quantitative")) == "quantitative"
        and c.get("value") is not None
    ]
    if not mine:
        return None
    theirs = {}
    for c in opponent_claims:
        if str(c.get("kind", "quantitative")) != "quantitative":
            continue
        key = str(c.get("metric_name") or "").strip().lower()
        if key and c.get("value") is not None:
            theirs[key] = float(c["value"])
    if not theirs:
        return None
    hits = 0
    for c in mine:
        key = str(c.get("metric_name") or "").strip().lower()
        if key not in theirs:
            continue
        truth = theirs[key]
        denom = abs(truth) if truth else 1.0
        if abs(float(c["value"]) - truth) / denom * 100.0 > tolerance_pct:
            hits += 1
    return hits / len(mine)


def aligned_value_vectors(
    current: dict, previous: dict
) -> tuple[list[float], list[float]]:
    """Two equal-length value lists ordered by the union of metric names.

    ``entrenchment_index`` (design §4.5) takes two vectors; a role's vector is
    the numbers it asserted, aligned by metric name. A metric present in only
    one of the two turns contributes ``0.0`` to the other side, so dropping a
    metric reads as drift instead of being silently ignored.
    """
    keys = sorted(set(current) | set(previous))
    return (
        [float(current.get(k) or 0.0) for k in keys],
        [float(previous.get(k) or 0.0) for k in keys],
    )


def l1_rubric(
    verifications: Sequence[dict],
    claims: Sequence[dict],
    *,
    opponent_claims: Sequence[dict] = (),
    current_values: dict | None = None,
    prior_values: dict | None = None,
    allocation: float | None = None,
    prior_allocation: float | None = None,
    entrenchment_threshold: float = DEFAULT_ENTRENCHMENT_THRESHOLD,
) -> dict:
    """L1's dimensioned rubric, deterministic and pure.

    Every value comes from the turn's own claims and the run's verified ground
    truth. Scaled 0..10 to match
    ``L2JudgeDimensionedRubric.dimension_scores`` so the tiers can be compared
    directly; stored separately, never merged.

    Four of the six have a producer here. Two do not, and say so rather than
    guessing: ``catalyst_clarity`` needs the forward calendar (not held by the
    debate node) and ``assumption_sensitivity`` needs a valuation perturbation
    (not computed on this path). An absent member is ``None`` with its reason,
    never ``0``.

    Returns ``{dimensions: {name: {value, status, reason}}, present, absent}``.
    """
    dims: dict[str, dict] = {}

    ev = evidence_quality(verifications)
    dims["empirical_grounding"] = _l1_dim(
        None if ev is None else round(10.0 * ev, 4),
        "10 x the valid share of this turn's verifiable claims"
        if ev is not None
        else "the turn made no verifiable claim",
    )

    sevs = [str(c.get("severity") or "").strip().upper() for c in claims]
    sevs = [s for s in sevs if s]
    if sevs:
        high = sum(1 for s in sevs if s in HIGH_SEVERITIES)
        dims["downside_tail_risk_weight"] = _l1_dim(
            round(10.0 * high / len(sevs), 4),
            f"{high}/{len(sevs)} declared risk factors at HIGH or CRITICAL",
        )
    else:
        dims["downside_tail_risk_weight"] = _l1_dim(
            None, "the turn declared no risk factor"
        )

    dims["catalyst_clarity"] = _l1_dim(
        None, "needs the forward calendar, which the debate node does not hold"
    )
    dims["assumption_sensitivity"] = _l1_dim(
        None, "needs a valuation perturbation, which the L1 tier does not compute"
    )

    share = direct_challenge_share(claims, opponent_claims)
    dims["rebuttal_effectiveness"] = _l1_dim(
        None if share is None else round(10.0 * share, 4),
        "10 x the share of this turn's quantitative claims that contradict an "
        "opponent claim on the same metric (deterministic floor; a judge reads "
        "rhetoric, a rule only sees whether the numbers were met)"
        if share is not None
        else "no preceding opposing claim to rebut",
    )

    cur = dict(current_values or {})
    prev = dict(prior_values or {})
    if cur and prev:
        a, b = aligned_value_vectors(cur, prev)
        idx = entrenchment_index(a, b, allocation, prior_allocation)
        detected = bool(idx >= entrenchment_threshold)
        alloc_known = allocation is not None and prior_allocation is not None
        dims["entrenchment_detected"] = _l1_dim(
            detected,
            f"index {idx:g} vs threshold {entrenchment_threshold:g} "
            f"({'repeated its numbers' if detected else 'new evidence'})"
            + (
                ""
                if alloc_known
                else "; allocation unavailable, so the index is pure value overlap"
            ),
        )
    else:
        dims["entrenchment_detected"] = _l1_dim(
            None, "this role has no earlier turn to compare against"
        )

    present = [k for k in L1_RUBRIC_DIMENSIONS if dims[k]["value"] is not None]
    return {
        "dimensions": dims,
        "present": present,
        "absent": [k for k in L1_RUBRIC_DIMENSIONS if k not in present],
    }


__all__ = [
    "L1_RUBRIC_DIMENSIONS",
    "DEFAULT_ENTRENCHMENT_THRESHOLD",
    "HIGH_SEVERITIES",
    "REBUTTAL_TOLERANCE_PCT",
    "direct_challenge_share",
    "aligned_value_vectors",
    "l1_rubric",
    "GREEN",
    "SOFT_WARNING",
    "RETRYABLE_ERROR",
    "HARD_BREACH",
    "PROCEED",
    "APPLY_PENALTY_AND_PROCEED",
    "TRIGGER_REGEN",
    "ABORT_TO_BASELINE",
    "DEFAULT_WEIGHTS",
    "claim_stats",
    "evidence_quality",
    "novelty_gain",
    "debate_score",
    "information_gain",
    "termination_check",
    "classify_severity",
    "entrenchment_index",
    "divergence_check",
    "reweight_to_baseline",
]
