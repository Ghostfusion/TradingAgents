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
# P0 context-bounding: static registry (key->value + proposal summary) built
# once per run; active-disputes list (unresolved/breached claims surfaced in
# prompts).
GROUND_TRUTH_REGISTRY = "ground_truth_registry"
ACTIVE_DISPUTES = "active_disputes"

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


def _bounded(text, max_chars: int = 8000) -> str:
    """Tail-truncate a growing context block (history / ledger / report).

    The debate history and claim ledger GROW every round; a debater only
    needs the recent turns to rebut, and a thinking model's reasoning cost
    scales with input size — shipping 10 rounds of prose + every claim on
    each turn burns the output budget in hidden reasoning and degrades to
    truncated JSON. Keep the TAIL (most recent) and say what was cut.
    """
    text = text or ""
    if len(text) <= max_chars:
        return text
    return "[earlier context truncated...]\n" + text[-max_chars:]


def _registry_index(reg: dict) -> str:
    """Render the static Ground-Truth Key Index (direction.md): the authorized
    key->value map the debater may cite. Constant size; built once per run."""
    keys = (reg or {}).get("keys") or {}
    if not keys:
        return "  (registry unavailable)"
    bits = []
    for k, v in list(keys.items())[:40]:
        bits.append(f"  {k}={v}")
    return _EOL.join(bits)


def _last_turn_context(ds: dict, role: str) -> str:
    """Immediately preceding speaker's payload (the direct rebuttal target).

    ``round_records[-1]`` holds the prior turn dict ``{other_role: payload}``;
    if the last record is the CURRENT role (round restart / regen), walk back
    to the previous record so the debater always rebuts an opponent who just
    spoke, never themselves.
    """
    records = ds.get(ROUND_RECORDS) or []
    for rec in reversed(records):
        for r, payload in rec.items():
            if r != role and isinstance(payload, dict):
                claims = payload.get("quantitative_claims") or []
                claim_lines = [
                    f"    - {c.get('ground_truth_key', '?')}={c.get('asserted_value')}"
                    for c in claims[:10]
                ]
                lines = [
                    f"  stance: {payload.get('stance', r)}",
                    f"  core_thesis: {str(payload.get('core_thesis', ''))[:600]}",
                ]
                if claim_lines:
                    lines.append("  claims:")
                    lines.extend(claim_lines)
                return _EOL.join(lines)
    return "  (opening round — no preceding opponent turn)"


def build_turn_prompt(state: dict, role: str, stance: str) -> str:
    """Debater prompt, context-bounded (P1/direction.md).

    STATIC (constant size): Ground-Truth Key Index (registry key->value) +
    Proposal Summary. DYNAMIC (bounded): Preceding Opponent Turn (last round
    only) + Active Dispute Ledger (<=5 unresolved/breached claims). The full
    analyst reports, full debate history, and full claim ledger are NOT
    injected — the registry IS the grounding, L1 still verifies every cited
    key against the real computed value.
    """
    asset_type = state.get("asset_type", "stock")
    target_label = "stock" if asset_type == "stock" else "asset"
    section = "risk" if role in SECTION_ROLES["risk"] else "research"
    ds = state.get(SECTION_CHANNEL[section]) or {}
    reg = ds.get(GROUND_TRUTH_REGISTRY) or build_or_get_registry(state, section)
    ctx_or = state.get("instrument_context") or ""

    head = [
        f"You are the {stance} debater for the {target_label}. Your structured turn MUST be a reproducible argument:",
        "- core_thesis: your position (<=1500 chars)",
        "- quantitative_claims: at least one number; every number must be groundable (metric_name, asserted_value, ground_truth_key, source). Never invent a number; if you cannot ground it, omit the claim.",
        "- risk_factors (LOW/MEDIUM/HIGH/CRITICAL) with mitigation_stated",
        "- recommended_allocation_pct (0..100)",
        "",
        "You are an expert financial debater operating within a structured, deterministic evaluation graph. Your mandate is to defend your designated role and stance using rigorous, empirically grounded arguments.",
        "",
        "**Operational Invariants:**",
        "1. **Zero Hallucination / Strict Key Binding**: Every numerical figure you introduce MUST be mapped to an exact `ground_truth_key` from the provided Ground Truth Key Index. Do not invent metrics or extrapolate keys.",
        "2. **Deterministic L1 Audit**: Any assertion that contradicts the computed value for a key triggers a deterministic HARD BREACH and disqualifies the turn. Missing/invalid keys trigger soft score penalties.",
        "3. **Direct Rebuttal**: Address the opponent's immediately preceding thesis and active disputes rather than generating isolated talking points.",
        "4. **Structured Output Only**: Respond strictly with the valid JSON schema. Do not wrap JSON in conversational commentary.",
        "",
        "---",
        "### Input Context Provided Per Turn",
    ]

    disputes = active_disputes(ds)
    dispute_lines = ["  (no unresolved disputes)"] if not disputes else [
        f"  - {d.get('ground_truth_key')}: {d.get('role')} asserted "
        f"{d.get('asserted_value')} -> {d.get('status')}"
        for d in disputes
    ]

    body = [
        f"Resources: {ctx_or}",
        f"**Proposal Summary** (the trade under review): {_bounded(str((reg or {}).get('proposal_summary') or ''), 1500)}",
        "",
        "**Ground Truth Key Index** (authorized keys you may cite):",
        _registry_index(reg),
        "",
        "**Preceding Opponent Turn** (immediate prior speaker):",
        _last_turn_context(ds, role),
        "",
        "**Active Dispute Ledger** (unresolved/breached, up to 5):",
        _EOL.join(dispute_lines),
        "",
        "**Computed decision context (deterministic, advisory - ground your argument in these numbers, never invent your own):**",
        f"{_bounded(state.get('computed_decision_context') or '', 3000)}",
        "",
        "**Execution Directives:**",
        "- If challenging an opponent's claim: reference the specific metric from the Preceding Opponent Turn or Active Dispute Ledger and cite the corresponding ground_truth_key demonstrating why their thesis fails.",
        "- If opening round (N=1): ground your baseline position directly on the Proposal Summary and initial metrics from the Ground Truth Key Index.",
        "- Sizing Discipline: your recommended_allocation_pct must directly reflect the balance between your quantitative_claims and risk_factors. Avoid arbitrary allocations unsupported by your cited metrics.",
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


# Capture ``key = -12.34`` / ``key: 55.48`` / ``key=7.41`` anywhere in a
# line (computed context + analyst computed rows). Key is a short,
# lowercase-ish token; the value is the first number after the separator.
_KEY_VALUE_RE = __import__("re").compile(
    r"(?i)([a-z_][a-z0-9 _-]{2,39}?)[\s:=](?:\s|=|:)*?(-?\d+(?:\.\d+)?)"
)


def _parse_key_value_lines(text: str) -> dict[str, float]:
    """Extract ``key=value`` numeric pairs from a text block (computed
    context or analyst-report computed lines). Deterministic; the same
    values L1 verifies against."""
    out: dict[str, float] = {}
    for line in str(text or "").splitlines():
        # finditer: one line may carry a comma-list (computed context)
        for m in _KEY_VALUE_RE.finditer(line):
            k = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            if not k or len(k) > 40:
                continue
            try:
                out[k] = float(m.group(2))
            except (TypeError, ValueError):
                continue
    return out


def ground_truth_from_state(state: dict) -> dict[str, float]:
    """Deterministic ground truth for claim verification (P4 registry).

    Parses the computed decision context AND the analyst reports' computed
    lines for ``key=value`` numeric pairs — the full set of values a debater
    may legitimately cite (the same set L1 verifies against). Computed
    context wins on key collision; report-harvested keys are the coverage
    guard so a citeable number from the analysts is registry-verifiable,
    never an unavoidable 'unverified'.
    """
    gt: dict[str, float] = {}
    ctx = state.get("computed_decision_context") or ""
    gt.update(_parse_key_value_lines(ctx))
    for key in ("market_report", "fundamentals_report", "sentiment_report", "news_report"):
        gt.update(_parse_key_value_lines(state.get(key) or ""))
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
        # P0: build the static registry on the FIRST turn of the section
        # (cache-friendly; reused by every later turn + P1 prompt).
        reg = build_or_get_registry(state, section)
        ds.setdefault(GROUND_TRUTH_REGISTRY, reg)
        ds.setdefault(ACTIVE_DISPUTES, [])
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
        # P0: persist each verdict back onto its ledger row so the
        # active-disputes extractor (and round scoring) can read status.
        _vmap = {v.get("claim_id"): v.get("status") for v in verifs}
        for c in claims:
            c.status = _vmap.get(c.claim_id, "qualitative")
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
    """Claim ids with a persisted non-valid L1 status (P0).

    Replaces the stub: the claim ledger rows now carry ``status`` set by L1.
    Any violated / unverified / abstain claim counts against its side in the
    round score (conservative: non-valid = penalty, never a silent pass).
    """
    ledger = ClaimLedger.from_dict(ds.get(CLAIM_LEDGER) or [])
    return {
        c.claim_id
        for c in ledger.rows
        if c.status in ("violated", "unverified", "abstain")
    }


def active_disputes(ds: dict, n: int = 5) -> list[dict]:
    """Most recent unresolved/breached claims (P0/direction.md).

    Returns up to ``n`` dicts ``{claim_id, role, round, metric_name,
    asserted_value, ground_truth_key, status}`` newest-first — the bounded
    dispute ledger debaters must challenge/defend.
    """
    ledger = ClaimLedger.from_dict(ds.get(CLAIM_LEDGER) or [])
    bad = [
        c
        for c in ledger.rows
        if c.status in ("violated", "unverified")
    ]
    out = []
    for c in reversed(bad[-n:]):
        out.append(
            {
                "claim_id": c.claim_id,
                "role": c.role,
                "round": c.round,
                "metric_name": c.metric_name or c.ground_truth_key,
                "asserted_value": c.value,
                "ground_truth_key": c.ground_truth_key,
                "status": c.status,
            }
        )
    return out


def build_or_get_registry(state: dict, section: str) -> dict:
    """Static ground-truth registry, built ONCE per channel (P0/direction.md).

    ``{keys: {authorized_key: value}, proposal_summary: ...}`` from the
    deterministic computed context + analyst computed lines. The debater
    prompt only ever cites keys present here; a cited key missing from it
    is L1 ``unverified`` (never a silent pass).
    """
    channel = SECTION_CHANNEL[section]
    ds = dict(state.get(channel) or {})
    reg = ds.get(GROUND_TRUTH_REGISTRY)
    if reg:
        return reg
    gt = ground_truth_from_state(state)  # parsed computed decision context
    keys = {}
    for k, v in gt.items():
        try:
            keys[k] = round(float(v), 4)
        except (TypeError, ValueError):
            continue
    # Proposal summary: risk debaters judge the trader's plan; research has
    # no trader yet -> a compact plan-card excerpt from the computed context.
    proposal = ""
    if section == "risk":
        proposal = (state.get("trader_investment_plan") or "")[:2000]
    else:
        cc = (state.get("computed_decision_context") or "")[:3000]
        proposal = cc
    reg = {"keys": keys, "proposal_summary": proposal}
    return reg


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


def render_consumer_debate_matrix(ds: dict, roles: Sequence[str]) -> str:
    """Tabulated Debate Matrix for RM/PM (P3/direction.md).

    Straight from round_records + judge_scores + persisted L1 statuses:
    | Role | Stance | Core Thesis | L1 Valid % | Judge Score | Rec Alloc |
    Replaces raw prose transcripts in the consumer prompts (reporting keeps
    the full transcripts). Judge aliases are the deterministic seed-0
    rotation (roles order -> Candidate_X/Y/...).
    """
    from tradingagents.strategies.debate_claim import ClaimLedger

    def _last_role_payload(role):
        for rec in reversed(ds.get(ROUND_RECORDS) or []):
            p = rec.get(role)
            if isinstance(p, dict):
                return p
        return None

    ledger = ClaimLedger.from_dict(ds.get(CLAIM_LEDGER) or [])
    judge = ds.get(JUDGE_SCORES) or {}
    rows = []
    for i, role in enumerate(roles):
        payload = _last_role_payload(role)
        stance = (payload or {}).get("stance", role)
        thesis = str((payload or {}).get("core_thesis", ""))[:80]
        alloc = (payload or {}).get("recommended_allocation_pct", "-")
        # L1 valid % across this role's claims (statuses persisted, P0)
        role_claims = [c for c in ledger.rows if c.role == role]
        n = len(role_claims)
        valid = sum(1 for c in role_claims if c.status == "valid")
        l1_pct = f"{100 * valid / n:.0f}%" if n else "-"
        # judge alias deterministic seed-0 rotation: roles[i] -> Candidate_X+i
        alias = f"Candidate_{chr(ord('X') + i)}"
        j = judge.get(alias) or {}
        j_mean = j.get("mean", "-")
        rows.append(
            f"| {role} | {stance} | {thesis} | {l1_pct} | {j_mean} | {alloc}% |"
        )
    table = (
        "| Role | Stance | Core Thesis | L1 Valid % | Judge Score (0-10) | "
        "Rec Alloc |\n|---|---|---|---|---|---|\n" + "\n".join(rows)
    )
    return table


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
    "GROUND_TRUTH_REGISTRY",
    "ACTIVE_DISPUTES",
    "active_disputes",
    "build_or_get_registry",
    "render_consumer_debate_matrix",
    "render_turn_prose",
    "build_turn_prompt",
    "claim_records_from_turn",
    "ground_truth_from_state",
    "create_debater_turn",
    "create_debate_l1",
    "create_debate_finalize",
]
