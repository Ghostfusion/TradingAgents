"""P4 — L2 blind dimensioned judge for the structured research debate.

The judge is a THIRD model family (anonymized, order-rotated, dimensioned
rubric) that never sees which side is bull/bear — only ``Candidate_X`` /
``Candidate_Y`` in a shuffled order. Its ``L2JudgeDimensionedRubric`` scores
are aggregated per side and carried into the judge verdict; the L1
deterministic verdict ties-breaks disagreements (design §4.5).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from tradingagents.agents.researchers.structured_debate import (
    SECTION_CHANNEL,
    SECTION_ROLES,
)
from tradingagents.agents.schemas import L2JudgeDimensionedRubric
from tradingagents.agents.utils.debate_structured import invoke_structured_turn

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


def _candidate_block(cand: dict) -> str:
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
    return "\n".join(rows)


def _build_judge_candidate_prompt(
    round_no: int,
    candidate: dict,
    opponent: dict | None,
    l1_scorecard: str,
) -> str:
    """O(1) judge context (P2/direction.md): candidate's latest payload +
    the IMMEDIATELY PRECEDING opponent payload (rebuttal baseline) + the L1
    verification scorecard. The multi-round transcript and full claim ledger
    are NOT sent — the judge scores the round, not the history.

    Args:
        candidate: {alias, thesis, claims, risk_factors, allocation}.
        opponent: preceding speaker's {alias, thesis, claims} or None
            (opening round).
        l1_scorecard: deterministic per-role valid/violated/unverified/abstain
            counts (rendered by the caller).
    """
    opp_block = _candidate_block(opponent) if opponent else (
        "Opening round - evaluate thesis clarity."
    )
    return (
        f"{_JUDGE_SYSTEM}\n\n--- Round {round_no} (anonymized) ---\n\n"
        + _candidate_block(candidate)
        + f"\n\n### Preceding opponent (rebuttal baseline)\n{opp_block}"
        + f"\n\n**L1 verification scorecard (deterministic):**\n{l1_scorecard}"
    )


def anonymize_and_rotate(
    turn_by_role: dict[str, dict], roles: Sequence[str], seed: int = 0
) -> list[dict]:
    """Strip identities + shuffle presentation order for N roles.

    Args:
        turn_by_role: {role: DebaterTurnPayload dict} for the round.
        roles: ordered role list (research: bull/bear; risk: aggressive/
            conservative/neutral).
        seed: rotation seed (odd = reverse presentation order).

    Returns ``[{alias, thesis, claims, risk_factors, allocation}, ...]`` with
    stable aliases Candidate_X/Y/...; rotation deterministic for tests.
    """
    order = list(roles)
    if (seed % 2) == 1:
        order.reverse()
    alias_map = {role: f"Candidate_{chr(ord('X') + i)}" for i, role in enumerate(order)}
    out = []
    for role in order:
        t = turn_by_role.get(role) or {}
        if hasattr(t, "model_dump"):
            t = t.model_dump()
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


def create_debate_judge(judge_llm, section: str = "research", cfg: dict | None = None):
    """Graph node factory for the L2 judge.

    ``judge_llm`` is the resolved judge model (deep tier by default). The
    node reads the structured debate state, anonymizes+rotates the latest
    round's N payloads, invokes the dimensioned rubric via the dual-mode
    adapter, and writes per-side aggregate scores + the rubric into the
    section's channel (``debate_state`` for research, ``structured_risk_state``
    for risk).
    """
    channel = SECTION_CHANNEL[section]
    roles = SECTION_ROLES[section]
    # Prefer DeepSeek native JSON mode for the judge too (deepseek
    # JSON-enforcement): server-side valid-JSON constraint when the runtime
    # model supports json_mode + config debate_json_mode; else provider default.
    from tradingagents.agents.researchers.structured_debate import (
        bind_debate_structured,
    )

    structured_llm = bind_debate_structured(
        judge_llm, L2JudgeDimensionedRubric, "Debate Judge", cfg
    )

    def judge_node(state) -> dict:
        debate_state = state.get(channel) or {}
        round_records = debate_state.get("round_records") or []
        if not round_records:
            return {channel: {**debate_state, "judge_scores": {}, "judge_rubric": None}}
        from tradingagents.strategies.debate_claim import ClaimLedger

        ledger = ClaimLedger.from_dict(debate_state.get("claim_ledger") or [])
        # Pick each role's LAST NON-DEGRADED payload (regression: the O(1)
        # judge read only round_records[-1]; if the final round's turn
        # degraded ("No structured turn produced"), the judge scored 0.0
        # despite substantive earlier rounds. Skip degraded shells when
        # choosing what to judge.)
        def _degraded(p):
            thesis = str((p or {}).get("core_thesis", "")) or ""
            return thesis.startswith("No structured turn produced") or not p

        def _last_good_payload(role):
            for rec in reversed(round_records):
                p = rec.get(role)
                if isinstance(p, dict) and not _degraded(p):
                    return p
            return {}

        turn_by_role = {r: _last_good_payload(r) for r in roles}
        candidates = anonymize_and_rotate(turn_by_role, roles)
        # Flag if any candidate is an empty shell (all its turns degraded).
        for cand in candidates:
            if not cand.get("thesis"):
                cand["degraded"] = True
        # Per-role L1 scorecard (P0). A claim is counted only when it came
        # from a round <= the role's latest non-degraded round, so the judge
        # sees the scorecard of the evidence it is actually scoring.
        latest_round_by_role = {
            r: rec.get("round_no", idx + 1)
            for r in roles
            for idx, rec in enumerate(round_records)
            if isinstance(rec.get(r), dict) and not _degraded(rec.get(r))
        }
        sc_lines = []
        for r in roles:
            rows = [c for c in ledger.rows if c.role == r]
            if not rows:
                sc_lines.append(f"- {r}: no claims")
                continue
            counts = {"valid": 0, "violated": 0, "unverified": 0, "abstain": 0}
            for c in rows:
                counts[c.status] = counts.get(c.status, 0) + 1
            sc_lines.append(
                f"- {r}: valid={counts['valid']} violated={counts['violated']} "
                f"unverified={counts['unverified']} abstain={counts['abstain']}"
            )
        l1_scorecard = "\n".join(sc_lines) or "(no claims verified)"
        side_scores = {}
        rubrics = []
        for i, cand in enumerate(candidates):
            # Preceding opponent = the role BEFORE this candidate (last
            # non-degraded payload); round-1 candidate has none.
            prev_role = roles[i - 1] if i > 0 else None
            opponent = None
            if prev_role:
                for rec in reversed(round_records):
                    p = rec.get(prev_role)
                    if isinstance(p, dict) and not _degraded(p):
                        opponent = anonymize_and_rotate({prev_role: p}, [prev_role])[0]
                        break
            judge_round = latest_round_by_role.get(roles[i], len(round_records))
            prompt = _build_judge_candidate_prompt(
                judge_round,
                cand,
                opponent,
                l1_scorecard,
            )
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
        return {channel: new_state}

    return judge_node


__all__ = [
    "anonymize_and_rotate",
    "aggregate_scores",
    "create_debate_judge",
    "_build_judge_candidate_prompt",
]
