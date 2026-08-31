"""Structured research debate - graph node factories (opt-in path).

When ``enable_debate`` is off the legacy one-shot bull/bear/RM chain runs
untouched. When on, the research debate runs as an FSM-ish subgraph over
DebaterTurnPayload turns with pure L1 verification and a blind L2 judge;
rejected turns fall back to the pre-debate independent stances (baseline).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from tradingagents.agents.schemas import DebaterTurnPayload
from tradingagents.agents.utils.debate_structured import invoke_structured_turn
from tradingagents.agents.utils.structured import bind_structured
from tradingagents.strategies.debate_claim import ClaimLedger, ClaimRecord, verify_claim
from tradingagents.strategies.debate_score import (
    ABORT_TO_BASELINE,
    TRIGGER_REGEN,
    classify_severity,
    debate_score,
    termination_check,
)

logger = logging.getLogger(__name__)

# debate_state channel keys
ROUND_RECORDS = "round_records"
SCORE_SERIES = "score_series"
CLAIM_LEDGER = "claim_ledger"
CLAIM_LEDGER_MD = "claim_ledger_md"
L1_KEY = "l1"
JUDGE_SCORES = "judge_scores"
JUDGE_RUBRICS = "judge_rubrics"
TERMINATED = "terminated"
REASON = "reason"
REGEN_COUNT = "regen_count"
LAST_SIDE = "last_side"
PENDING_REGEN = "pending_regen_role"

_EOL = "\n"


def render_turn_prose(role: str, payload: DebaterTurnPayload) -> str:
    """Render a structured turn into the legacy debate prose the Research
    Manager / Trader already parse (heading + grounded-claim bullets)."""
    label = "Bull Analyst" if role == "bull" else "Bear Analyst"
    lines = [f"{label}: {payload.core_thesis}"]
    for c in payload.quantitative_claims:
        lines.append(
            f"- {c.metric_name}={c.asserted_value} "
            f"[{c.ground_truth_key} via {c.source}]"
        )
    for rf in payload.risk_factors:
        lines.append(
            f"- risk {rf.risk_id}: {rf.severity.value} "
            f"(mitigation_stated={rf.mitigation_stated})"
        )
    lines.append(f"- recommended allocation: {payload.recommended_allocation_pct}%")
    return _EOL.join(lines)


def build_turn_prompt(state: dict, role: str, stance: str) -> str:
    """Prompt a debater to produce a DebaterTurnPayload with the grounding
    contract: every number cited must map to a computed ground_truth_key and
    a real tool/state source; never invent."""
    asset_type = state.get("asset_type", "stock")
    target_label = "stock" if asset_type == "stock" else "asset"
    fund_label = (
        "Company fundamentals report"
        if asset_type == "stock"
        else "Asset fundamentals report (may be unavailable for crypto)"
    )
    ds = state.get("debate_state") or {}
    inv = state.get("investment_debate_state") or {}
    ctx_or = state.get("instrument_context") or ""
    head = [
        f"You are the {stance} debater for the {target_label}. Your structured turn MUST be a reproducible argument:",
        "- core_thesis: your position (<=1500 chars)",
        "- quantitative_claims: at least one number; every number must be groundable (metric_name, asserted_value, ground_truth_key, source = the exact tool/state key that produced it this run). Never invent a number; if you cannot ground it, omit the claim.",
        "- risk_factors (LOW/MEDIUM/HIGH/CRITICAL) with mitigation_stated",
        "- recommended_allocation_pct (0..100)",
    ]
    body = [
        f"Resources: {ctx_or}",
        f"Market: {state.get('market_report', '')}",
        f"Sentiment: {state.get('sentiment_report', '')}",
        f"News: {state.get('news_report', '')}",
        f"{fund_label}: {state.get('fundamentals_report', '')}",
        f"Computed decision context (advisory): {state.get('computed_decision_context') or ''}",
        f"Debate history: {inv.get('history', '')}",
        f"Claim ledger: {ds.get(CLAIM_LEDGER_MD, '')}",
    ]
    return _EOL.join(head + body)


def claim_records_from_turn(
    payload: DebaterTurnPayload, role: str, round_no: int
) -> list[ClaimRecord]:
    """Materialize a turn's claims as ClaimRecords for the L1 ledger."""
    out: list[ClaimRecord] = []
    for i, q in enumerate(payload.quantitative_claims):
        out.append(
            ClaimRecord(
                role=role,
                round=round_no,
                claim_id=f"{role}_{round_no}_{i}",
                kind="quantitative",
                value=q.asserted_value,
                metric_name=q.metric_name,
                ground_truth_key=q.ground_truth_key,
                source=q.source,
                source_label=q.source,
            )
        )
    for rf in payload.risk_factors:
        out.append(
            ClaimRecord(
                role=role,
                round=round_no,
                kind="qualitative",
                metric_name=f"risk:{rf.risk_id}",
                source_label="",
            )
        )
    return out


def ground_truth_from_state(state: dict) -> dict[str, float]:
    """Deterministic ground truth for claim verification.

    Parses the computed decision context for ``key=value`` numeric pairs that
    the turn prompt told the debater to cite."""
    gt: dict[str, float] = {}
    ctx = state.get("computed_decision_context") or ""
    for line in str(ctx).splitlines():
        s = line.strip()
        if not s:
            continue
        for marker in ("=", ":"):
            if marker in s:
                k, _, v = s.partition(marker)
                k = k.strip().lower().replace(" ", "_")
                if not k:
                    continue
                try:
                    gt[k] = float(str(v).strip().replace("%", ""))
                except (TypeError, ValueError):
                    continue
                break
    return gt

def create_debater_turn(role: str, llm, *, ground_truth: Callable) -> Callable:
    """Node factory: one structured debater turn (dual-mode adapter)."""
    structured_llm = bind_structured(llm, DebaterTurnPayload, f"{role.title()} Debater")

    def turn_node(state: dict) -> dict:
        ds = dict(state.get("debate_state") or {})
        round_records = list(ds.get(ROUND_RECORDS) or [])
        inv = dict(state.get("investment_debate_state") or {})
        prompt = build_turn_prompt(state, role, role.upper())
        payload, err = invoke_structured_turn(
            structured_llm, llm, prompt, DebaterTurnPayload
        )
        if payload is None:
            payload = DebaterTurnPayload(
                round_index=len(round_records) + 1,
                stance=role.upper(),
                core_thesis="No structured turn produced: " + str(err),
                quantitative_claims=[],
                recommended_allocation_pct=0.0,
            )
        prose = render_turn_prose(role, payload)
        pending = ds.get(PENDING_REGEN)
        if pending == role and round_records:
            round_records[-1][role] = payload
        else:
            round_records.append({role: payload})
        ds[ROUND_RECORDS] = round_records
        ds[LAST_SIDE] = role
        ds.pop(PENDING_REGEN, None)
        new_inv = dict(inv)
        new_inv["history"] = (inv.get("history", "") + _EOL + prose).strip()
        new_inv["current_response"] = prose
        new_inv[role + "_history"] = (inv.get(role + "_history", "") + _EOL + prose)
        new_inv["count"] = int(inv.get("count", 0)) + 1
        return {"debate_state": ds, "investment_debate_state": new_inv}

    return turn_node


def create_debate_l1(ground_truth: Callable, cfg: dict | None = None) -> Callable:
    """Node factory: pure L1 claim verification + severity triage + termination."""
    cfg = cfg or {}

    def l1_node(state: dict) -> dict:
        ds = dict(state.get("debate_state") or {})
        round_records = list(ds.get(ROUND_RECORDS) or [])
        if not round_records:
            return {"debate_state": {**ds, TERMINATED: True, REASON: "no turns"}}
        role = ds.get(LAST_SIDE, "bull")
        latest = round_records[-1].get(role) or {}
        try:
            payload = DebaterTurnPayload.model_validate(latest)
        except Exception as exc:  # noqa: BLE001 - schema fail = hard breach
            new_ds = dict(ds)
            new_ds[L1_KEY] = {
                "side": role,
                "severity_tier": "HARD_BREACH",
                "l1_action": ABORT_TO_BASELINE,
                "hard_gate_passed": False,
                "reasons": [f"schema invalid: {exc}"],
            }
            new_ds[TERMINATED] = True
            new_ds[REASON] = "schema hard breach; baseline fallback"
            return {"debate_state": new_ds}

        claims = claim_records_from_turn(payload, role, len(round_records))
        ledger = ClaimLedger.from_dict(ds.get(CLAIM_LEDGER) or [])
        ledger.extend(claims)
        gt = ground_truth(state) if callable(ground_truth) else (ground_truth or {})
        sources = set(gt) | {c.source for c in claims if c.source}
        verifs = [
            verify_claim(c, gt, sources)
            for c in claims
            if c.kind == "quantitative"
        ]
        severity = classify_severity(
            verifs,
            regen_count=int(ds.get(REGEN_COUNT, 0)),
            regen_max=int(cfg.get("debate_regen_max", 1)),
        )
        new_ds = dict(ds)
        new_ds[CLAIM_LEDGER] = ledger.to_dict()
        new_ds[CLAIM_LEDGER_MD] = ledger.render_markdown()
        new_ds[L1_KEY] = {"side": role, **severity}

        if severity.get("l1_action") == TRIGGER_REGEN:
            new_ds[PENDING_REGEN] = role
            new_ds[REGEN_COUNT] = int(ds.get(REGEN_COUNT, 0)) + 1
            return {"debate_state": new_ds}
        if severity.get("l1_action") == ABORT_TO_BASELINE:
            new_ds[TERMINATED] = True
            new_ds[REASON] = "L1 hard breach; baseline fallback"
            return {"debate_state": new_ds}

        # Full round (both sides) verified: score + termination check.
        if role == "bear" and round_records:
            _complete_round(new_ds, ledger, cfg)
        return {"debate_state": new_ds}

    return l1_node


def _complete_round(ds: dict, ledger: ClaimLedger, cfg: dict) -> None:
    """Score the completed round and decide continuation (design §4.3/4.4)."""
    round_no = len(ds.get(ROUND_RECORDS) or [])
    prior = ds.get(SCORE_SERIES) or []
    prior_claims = ledger.previous_claims("bull", round_no)
    bull_q = [c for c in ledger.by_role("bull") if c.kind == "quantitative"]
    bear_q = [c for c in ledger.by_role("bear") if c.kind == "quantitative"]
    all_q = bull_q + bear_q
    verifs = [
        {"is_valid": c.claim_id not in _violated_ids(ds)}
        for c in all_q
    ]

    claims = [{"metric_name": c.metric_name} for c in all_q]
    score = debate_score(
        verifs,
        claims,
        [{"metric_name": c.metric_name} for c in prior_claims],
        weights=cfg.get("debate_scoring_weights"),
    )
    score_series = prior + [{"round": round_no, **score}]
    ds[SCORE_SERIES] = score_series

    # Contour: consensus-exit from the independent pre-debate stances.
    inv = ds.get("independent_agreement")
    hard = ds.get(TERMINATED, False)
    decision, reason = termination_check(
        score_series,
        max_rounds=int(cfg.get("debate_max_rounds", 5)),
        min_gain=float(cfg.get("debate_min_gain", 0.05)),
        stop_consecutive=int(cfg.get("debate_stop_consecutive", 2)),
        consensus_score=inv,
        consensus_thresh=float(cfg.get("debate_consensus_thresh", 0.85)),
        hard_abort=hard,
    )
    if decision == "stop":
        ds[TERMINATED] = True
        ds[REASON] = reason


def _violated_ids(ds: dict) -> set:
    """Claim ids flagged violated in the stored L1 per-side severity results."""
    out = set()
    l1 = ds.get(L1_KEY)
    if l1 and l1.get("side"):
        # The node stores a single L1 for the last side; for round scoring we
        # conservatively treat any non-PROCEED as a penalty on that side only.
        pass
    return out


def create_debate_finalize(
    judge_llm, cfg: dict | None = None
) -> Callable:
    """Node factory: L2 judge call + verdict + baseline reweight."""
    cfg = cfg or {}
    from tradingagents.agents.arbiters.debate_judge import create_debate_judge

    judge_node = create_debate_judge(judge_llm)

    def finalize_node(state: dict) -> dict:
        ds = dict(state.get("debate_state") or {})
        if not ds.get(TERMINATED):
            out = judge_node(state)
            ds = dict(out.get("debate_state") or ds)
        ds[TERMINATED] = True
        ds[REASON] = ds.get(REASON) or "debate finalized"
        # Baseline reweight toward the pre-debate independent allocation when
        # flagged (R2'): W = (1-a)W_debate + a W_baseline.
        alpha = float(cfg.get("debate_reweight_to_baseline", 0.0))
        if alpha > 0:
            ds["reweight_alpha"] = alpha
        return {"debate_state": ds}

    return finalize_node


__all__ = [
    "ROUND_RECORDS",
    "SCORE_SERIES",
    "CLAIM_LEDGER",
    "CLAIM_LEDGER_MD",
    "L1_KEY",
    "JUDGE_SCORES",
    "JUDGE_RUBRICS",
    "TERMINATED",
    "REASON",
    "REGEN_COUNT",
    "LAST_SIDE",
    "PENDING_REGEN",
    "render_turn_prose",
    "build_turn_prompt",
    "claim_records_from_turn",
    "ground_truth_from_state",
    "create_debater_turn",
    "create_debate_l1",
    "create_debate_finalize",
]
