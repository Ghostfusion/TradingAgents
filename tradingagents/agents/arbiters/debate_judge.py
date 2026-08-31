"""P4 — L2 blind dimensioned judge for the structured research debate.

The judge is a THIRD model family (anonymized, order-rotated, dimensioned
rubric) that never sees which side is bull/bear — only ``Candidate_X`` /
``Candidate_Y`` in a shuffled order. Its ``L2JudgeDimensionedRubric`` scores
are aggregated per side and carried into the judge verdict; the L1
deterministic verdict ties-breaks disagreements (design §4.5).
"""

from __future__ import annotations

import logging

from tradingagents.agents.schemas import L2JudgeDimensionedRubric
from tradingagents.agents.utils.debate_structured import invoke_structured_turn
from tradingagents.agents.utils.structured import bind_structured

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "You are a neutral, dimensioned debate judge. You review TWO anonymized "
    "investment arguments (Candidate_X and Candidate_Y) with their grounded "
    "claims and risk factors. Score each candidate 0..10 on each dimension: "
    "empirical_grounding (verified mechanics vs narrative), "
    "downside_tail_risk_weight (asymmetric low-probability-high-impact risks), "
    "catalyst_clarity (specific timeline triggers), assumption_sensitivity "
    "(how valuations move under altered inputs). Also rate rebuttal_effectiveness "
    "(how directly the argument invalidated the opponent's specific premises) "
    "and set entrenchment_detected when a candidate merely repeated itself "
    "without new counter-evidence. Give every score a one-line rationale. "
    "Never guess numbers; a claim you cannot verify is scored low."
)


def _build_judge_prompt(
    round_no: int,
    candidates: list[dict],
    claim_ledger_md: str,
) -> str:
    """Anonymized, order-rotated judge prompt from two candidate dicts.

    Each candidate dict: {alias, thesis, claims, risk_factors, allocation}.
    """
    blocks = []
    for cand in candidates:
        rows = [f"### {cand['alias']}"]
        rows.append(f"Core thesis: {cand.get('thesis', '')[:1500]}")
        for claim in cand.get("claims", []):
            rows.append(
                f"- claim: {claim.get('metric_name', '')}="
                f"{claim.get('asserted_value')} (source={claim.get('source', '-')})"
            )
        for rf in cand.get("risk_factors", []):
            rows.append(
                f"- risk {rf.get('risk_id', '')} severity={rf.get('severity', '')} "
                f"mitigation_stated={bool(rf.get('mitigation_stated'))}"
            )
        rows.append(f"Recommended allocation: {cand.get('allocation', '-')}%")
        blocks.append("\n".join(rows))
    return (
        f"{_JUDGE_SYSTEM}\n\n--- Round {round_no} (anonymized) ---\n\n"
        + "\n\n".join(blocks)
        + f"\n\n{claim_ledger_md}"
    )


def anonymize_and_rotate(
    bull_turn: dict, bear_turn: dict, seed: int = 0
) -> list[dict]:
    """Strip identities + shuffle presentation order.

    Returns ``[{alias, thesis, claims, risk_factors, allocation}, ...]`` with
    stable aliases Candidate_X/Y; the rotation is seeded so tests are
    deterministic.
    """
    flip = (seed % 2) == 1
    order = ("bear", "bull") if flip else ("bull", "bear")
    alias_map = {role: f"Candidate_{'X' if i == 0 else 'Y'}" for i, role in enumerate(order)}
    out = []
    for role in order:
        t = bull_turn if role == "bull" else bear_turn
        out.append(
            {
                "alias": alias_map[role],
                "thesis": t.get("core_thesis", ""),
                "claims": t.get("quantitative_claims", []),
                "risk_factors": t.get("risk_factors", []),
                "allocation": t.get("recommended_allocation_pct"),
            }
        )
    return out


def aggregate_scores(rubric, candidates: list[dict]) -> dict:
    """Aggregate L2 dimension scores per side: mean of the four dimensions.

    Returns ``{alias: {mean, scores}}``.
    """
    out = {}
    for cand in candidates:
        dims = rubric.dimension_scores
        vals = [v for v in dims.values() if isinstance(v, (int, float))]
        out[cand["alias"]] = {
            "mean": round(sum(vals) / len(vals), 4) if vals else 0.0,
            "scores": {k.value if hasattr(k, "value") else str(k): v for k, v in dims.items()},
        }
    return out


def create_debate_judge(judge_llm):
    """Graph node factory for the L2 judge.

    ``judge_llm`` is the resolved judge model (deep tier by default). The
    node reads the structured debate state, anonymizes+rotates the latest
    round's paylods, invokes the dimensioned rubric via the dual-mode
    adapter, and writes per-side aggregate scores + the rubric into
    ``debate_state``.
    """
    structured_llm = bind_structured(judge_llm, L2JudgeDimensionedRubric, "Debate Judge")

    def judge_node(state) -> dict:
        debate_state = state.get("debate_state") or {}
        round_records = debate_state.get("round_records") or []
        if not round_records:
            return {"debate_state": {**debate_state, "judge_scores": {}, "judge_rubric": None}}
        latest = round_records[-1]
        bull_turn = latest.get("bull") or {}
        bear_turn = latest.get("bear") or {}
        candidates = anonymize_and_rotate(bull_turn, bear_turn)
        prompt = _build_judge_prompt(
            len(round_records),
            candidates,
            debate_state.get("claim_ledger_md", ""),
        )
        side_scores = {}
        rubrics = []
        for cand in candidates:
            rubric, err = invoke_structured_turn(
                structured_llm, judge_llm, prompt + f"\n\nScore ONLY {cand['alias']}.",
                L2JudgeDimensionedRubric,
            )
            if rubric is None:
                logger.warning("debate judge unavailable for %s: %s", cand["alias"], err)
                rubric = L2JudgeDimensionedRubric(
                    judge_model_id="",
                    round_evaluated=len(round_records),
                    evaluated_agent_alias=cand["alias"],
                    rationale=f"judge unavailable: {err}",
                )
            rubrics.append(rubric)
            dims = rubric.dimension_scores
            vals = [v for v in dims.values() if isinstance(v, (int, float))]
            side_scores[rubric.evaluated_agent_alias or cand["alias"]] = {
                "mean": round(sum(vals) / len(vals), 4) if vals else 0.0,
                "scores": {k.value if hasattr(k, "value") else str(k): v for k, v in dims.items()},
            }
        new_state = {
            **debate_state,
            "judge_scores": side_scores,
            "judge_rubrics": rubrics,
        }
        return {"debate_state": new_state}

    return judge_node


__all__ = [
    "anonymize_and_rotate",
    "aggregate_scores",
    "create_debate_judge",
    "_build_judge_prompt",
]
