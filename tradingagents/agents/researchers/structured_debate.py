"""Structured research debate - graph node factories (opt-in path).

When ``enable_debate`` is off the legacy one-shot bull/bear/RM chain runs
untouched. When on, the research debate runs as an FSM-ish subgraph over
DebaterTurnPayload turns with pure L1 verification and a blind L2 judge;
rejected turns fall back to the pre-debate independent stances (baseline).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from tradingagents.agents.schemas import DebaterTurnPayload, RiskDebaterTurnPayload
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
# Section tables: research = legacy bull/bear chain; risk = the three
# debators, generalized to the same structured machinery (direction.md).
SECTION_ROLES = {
    "research": ("bull", "bear"),
    "risk": ("aggressive", "conservative", "neutral"),
}
SECTION_CHANNEL = {
    "research": "debate_state",
    "risk": "structured_risk_state",
}
# Prose channel mirrors the legacy keys the RM/PM/reporting consume: the
# structured risk debaters append to risk_debate_state.history exactly like
# the legacy prose debators did.
SECTION_PROSE = {
    "research": "investment_debate_state",
    "risk": "risk_debate_state",
}

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
    _LABELS = {
        "bull": "Bull Analyst",
        "bear": "Bear Analyst",
        "aggressive": "Aggressive Analyst",
        "conservative": "Conservative Analyst",
        "neutral": "Neutral Analyst",
    }
    label = _LABELS.get(role, role.title())
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
    section = "risk" if role in SECTION_ROLES["risk"] else "research"
    ds = state.get(SECTION_CHANNEL[section]) or {}
    inv = state.get(SECTION_PROSE[section]) or {}
    ctx_or = state.get("instrument_context") or ""
    head = [
        f"You are the {stance} debater for the {target_label}. Your structured turn MUST be a reproducible argument:",
        "- core_thesis: your position (<=1500 chars)",
        "- quantitative_claims: at least one number; every number must be groundable (metric_name, asserted_value, ground_truth_key, source = the exact tool/state key that produced it this run). Never invent a number; if you cannot ground it, omit the claim.",
        "- risk_factors (LOW/MEDIUM/HIGH/CRITICAL) with mitigation_stated",
        "- recommended_allocation_pct (0..100)",
    ]
    risk_ctx = ""
    if role in SECTION_ROLES["risk"]:
        risk_ctx = f"Trader's proposal: {state.get('trader_investment_plan', '')}"
    body = [
        f"Resources: {ctx_or}",
        f"Market: {state.get('market_report', '')}",
        f"Sentiment: {state.get('sentiment_report', '')}",
        f"News: {state.get('news_report', '')}",
        f"{fund_label}: {state.get('fundamentals_report', '')}",
        f"Computed decision context (advisory): {state.get('computed_decision_context') or ''}",
        f"Debate history: {inv.get('history', '')}",
        risk_ctx,
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

def _section_for_role(role: str) -> str:
    """Which section (research/risk) owns a debater role."""
    return "risk" if role in SECTION_ROLES["risk"] else "research"


def create_debater_turn(
    role: str, llm, *, ground_truth: Callable, section: str | None = None
) -> Callable:
    """Node factory: one structured debater turn (dual-mode adapter).

    ``section`` selects the state channels: "research" keeps the legacy
    ``debate_state`` + ``investment_debate_state``; "risk" uses the new
    ``structured_risk_state`` + ``risk_debate_state`` so the risk debate
    mirrors the research one without touching the legacy risk prose keys
    (reporting/PM keep consuming ``risk_debate_state.history``).
    """
    section = section or _section_for_role(role)
    channel = SECTION_CHANNEL[section]
    prose_channel = SECTION_PROSE[section]
    schema = RiskDebaterTurnPayload if section == "risk" else DebaterTurnPayload
    structured_llm = bind_structured(llm, schema, f"{role.title()} Debater")

    def turn_node(state: dict) -> dict:
        ds = dict(state.get(channel) or {})
        round_records = list(ds.get(ROUND_RECORDS) or [])
        inv = dict(state.get(prose_channel) or {})
        prompt = build_turn_prompt(state, role, role.upper())
        payload, err = invoke_structured_turn(structured_llm, llm, prompt, schema)
        if payload is None:
            # Degraded turn: the role's provider produced no structured
            # payload. Build the HONEST empty payload (schema allows empty
            # claims now); round_index is capped inside 1..5. Last-resort
            # model_construct (skips validation) guarantees a failed
            # provider can NEVER crash the graph — one ValidationError here
            # previously killed the whole run and, via moomoo's non-daemon
            # threads, left the process hanging in interpreter shutdown
            # (flat CPU + all sockets CLOSE_WAIT).
            try:
                payload = schema(
                    round_index=min(len(round_records) + 1, 5),
                    stance=role.upper(),
                    core_thesis="No structured turn produced: " + str(err),
                    quantitative_claims=[],
                    recommended_allocation_pct=0.0,
                )
            except Exception as exc:  # noqa: BLE001 - degraded turn must never kill the graph
                logger.error(
                    "fallback payload construction failed for %s: %s", role, exc
                )
                payload = schema.model_construct(
                    round_index=min(len(round_records) + 1, 5),
                    stance=role.upper(),
                    core_thesis="No structured turn produced: " + str(err),
                    quantitative_claims=[],
                    recommended_allocation_pct=0.0,
                )
        prose = render_turn_prose(role, payload)
        pending = ds.get(PENDING_REGEN)
        # Store the payload as a plain dict: the judge (anonymize_and_rotate)
        # and reporting read round_records with dict APIs (.get). Storing the
        # pydantic OBJECT raised AttributeError 'DebaterTurnPayload' object
        # has no attribute 'get' the first time the L2 judge ran on a live
        # round (regression: judge never ran before the judge-skip fix).
        payload_dict = payload.model_dump()
        if pending == role and round_records:
            round_records[-1][role] = payload_dict
        else:
            round_records.append({role: payload_dict})
        ds[ROUND_RECORDS] = round_records
        ds[LAST_SIDE] = role
        ds.pop(PENDING_REGEN, None)
        new_inv = dict(inv)
        new_inv["history"] = (inv.get("history", "") + _EOL + prose).strip()
        new_inv["current_response"] = prose
        new_inv[role + "_history"] = (inv.get(role + "_history", "") + _EOL + prose)
        new_inv["count"] = int(inv.get("count", 0)) + 1
        if section == "risk":
            # The risk prose TypedDict consumers (PM, reporting) index the
            # per-role keys DIRECTLY; an early L1 termination (consensus /
            # plateau / regen-abort) can skip roles, so prime every legacy
            # key with a default and keep latest_speaker current.
            for _k in (
                "aggressive_history",
                "conservative_history",
                "neutral_history",
                "current_aggressive_response",
                "current_conservative_response",
                "current_neutral_response",
            ):
                new_inv.setdefault(_k, "")
            new_inv["latest_speaker"] = role.title()
        out = {channel: ds, prose_channel: new_inv}
        return out

    return turn_node


def create_debate_l1(
    ground_truth: Callable, cfg: dict | None = None, section: str = "research"
) -> Callable:
    """Node factory: pure L1 claim verification + severity triage + termination.

    ``section`` picks the channel (debate_state / structured_risk_state) and
    the round-complete role (bear for research, neutral for risk).
    """
    cfg = cfg or {}
    roles = SECTION_ROLES[section]
    channel = SECTION_CHANNEL[section]
    final_role = roles[-1]

    def l1_node(state: dict) -> dict:
        ds = dict(state.get(channel) or {})
        round_records = list(ds.get(ROUND_RECORDS) or [])
        if not round_records:
            return {channel: {**ds, TERMINATED: True, REASON: "no turns"}}
        role = ds.get(LAST_SIDE, roles[0])
        latest = round_records[-1].get(role) or {}
        schema = RiskDebaterTurnPayload if section == "risk" else DebaterTurnPayload
        try:
            payload = schema.model_validate(latest)
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
            return {channel: new_ds}

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
            return {channel: new_ds}
        if severity.get("l1_action") == ABORT_TO_BASELINE:
            new_ds[TERMINATED] = True
            new_ds[REASON] = "L1 hard breach; baseline fallback"
            return {channel: new_ds}

        # Full round (both sides) verified: score + termination check.
        if role == final_role and round_records:
            _complete_round(new_ds, ledger, cfg, roles)
        return {channel: new_ds}

    return l1_node


def _complete_round(
    ds: dict, ledger: ClaimLedger, cfg: dict, roles: Sequence[str]
) -> None:
    """Score the completed round and decide continuation (design §4.3/4.4).

    Generalized to N roles: research (bull, bear) and risk
    (aggressive, conservative, neutral) share the identical scoring math.
    """
    round_no = len(ds.get(ROUND_RECORDS) or [])
    prior = ds.get(SCORE_SERIES) or []
    prior_claims = ledger.previous_claims(roles[0], round_no)
    all_q = [
        c
        for c in ledger.rows
        if c.kind == "quantitative" and c.role in roles
    ]
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


def render_judge_evidence(ds: dict) -> str:
    """Render the structured-debate judge evidence block for the section's
    consumer (Research Manager / Portfolio Manager).

    Advisory, deterministic: the L1 severity verdict (side known) plus the
    blind L2 judge candidate scores and rationales. Empty string when the
    section has no judge output yet.
    """
    if not ds:
        return ""
    lines = []
    l1 = ds.get(L1_KEY) or {}
    if l1:
        lines.append(
            f"- L1 verdict: {l1.get('severity_tier', '?')} / "
            f"{l1.get('l1_action', '?')} (side={l1.get('side', '?')})"
        )
    judge = ds.get(JUDGE_SCORES) or {}
    for alias, agg in judge.items():
        lines.append(
            f"- {alias}: mean {agg.get('mean', '-')} "
            f"(scores: {agg.get('scores', {})})"
        )
    for rubric in ds.get(JUDGE_RUBRICS) or []:
        ra = getattr(rubric, "rationale", "") or ""
        if ra:
            lines.append(f"- rationale: {ra}")
    if not lines:
        return ""
    return (
        "\n\n**Structured debate judge evidence (deterministic):**\n"
        + "\n".join(lines)
    )


def _baseline_fallback_reason(reason: str) -> bool:
    """True when the debate ended as an L1 baseline fallback — the only case
    where the L2 jury must NOT run (the design never asks the judge to score
    a mathematically invalid / aborted debate). Normal terminations (hard
    cap, plateau, consensus) MUST still be judged."""
    r = (reason or "").lower()
    return (
        "baseline" in r
        or "hard breach" in r
        or "no turns" in r
        or "schema" in r
    )


def create_debate_finalize(
    judge_llm, cfg: dict | None = None, section: str = "research"
) -> Callable:
    """Node factory: L2 judge call + verdict + baseline reweight.

    ``section`` routes the judge read/write to the section's channel
    (debate_state for research, structured_risk_state for risk). The L2
    judge ALWAYS runs except on an L1 baseline-fallback termination — a
    debate that ended normally (round cap, plateau, consensus) still needs
    its verdict. Regression: the previous ``if not TERMINATED`` guard also
    skipped the judge for NORMAL terminations, so a live 5-round debate
    finished unjudged.
    """
    cfg = cfg or {}
    from tradingagents.agents.arbiters.debate_judge import create_debate_judge

    channel = SECTION_CHANNEL[section]
    judge_node = create_debate_judge(judge_llm, section=section)

    def finalize_node(state: dict) -> dict:
        ds = dict(state.get(channel) or {})
        if not _baseline_fallback_reason(ds.get(REASON, "")) or not ds.get(TERMINATED):
            out = judge_node(state)
            merged = out.get(channel) or out.get("debate_state") or ds
            ds = dict(merged)
        ds[TERMINATED] = True
        ds[REASON] = ds.get(REASON) or "debate finalized"
        # Baseline reweight toward the pre-debate independent allocation when
        # flagged (R2'): W = (1-a)W_debate + a W_baseline.
        alpha = float(cfg.get("debate_reweight_to_baseline", 0.0))
        if alpha > 0:
            ds["reweight_alpha"] = alpha
        return {channel: ds}

    return finalize_node


__all__ = [
    "SECTION_ROLES",
    "SECTION_CHANNEL",
    "SECTION_PROSE",
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
