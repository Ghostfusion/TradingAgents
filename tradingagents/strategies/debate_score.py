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


__all__ = [
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
