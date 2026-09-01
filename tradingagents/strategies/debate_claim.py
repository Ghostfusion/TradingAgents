"""P1 — Grounding contract: claim ledger + L1 hard verifier (pure, no LLM).

Design: ``docs/design_multi_agent_debate.md`` §4.2 (rev v3). A debater turn's
quantitative claims are recorded as ``ClaimRecord`` rows and verified
deterministically against the run's computed ground truth (the decision
context factsheet / tool outputs) and the run's tool-call ledger. This is the
deterministic half of the two-layer judiciary: the L2 LLM judge is never
asked to score a claim that contradicted a computed value.

Hard rules (no fabrication):
- a quantitative claim requires ``(value, ground_truth_key, source)``;
- a source that is not an ACTUAL tool/state call for this run
  (``sources`` ledger) is "deceptive grounding" -> violated;
- a claim whose value disagrees with ground truth beyond ``tolerance_pct``
  is violated;
- a claim whose ground_truth_key is unknown is left "unverified" (never
  invented as a pass) or downgraded to abstain when it has no source;
- qualitative claims weigh ~0; the model may always abstain.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Severity tiers every claim resolves to (mirrored in L1ExecutionContext).
VALID = "valid"
VIOLATED = "violated"
ABSTAIN = "abstain"
UNVERIFIED = "unverified"
QUALITATIVE = "qualitative"

_DEFAULT_TOLERANCE_PCT = 5.0

# Bounded key-alias map (registry-key mismatch fix): debaters humanize the
# Ground-Truth Key Index labels ("QCOM price", "Free-cash-flow yield") instead
# of copying the canonical key verbatim, so L1 marks them unverified->(unused).
# Normalize the common variants back to their canonical computed key before
# the ground-truth lookup. Deterministic; unknown labels stay unverified.
KEY_ALIASES = {
    "qcom_price": "last_price",
    "qcom_last_price": "last_price",
    "intraday_vwap": "vwap",
    "vwap_intraday": "vwap",
    "trailing_roe": "roe",
    "roe_trailing": "roe",
    "free_cash_flow_yield": "fcf_yield",
    "free_cash_flow_yield_pct": "fcf_yield",
    "fcf_yield_pct": "fcf_yield",
    "current_ratio_liquidity": "current_ratio",
    "reference_terminal_value": "dcf_fair_value",
    "terminal_value_per_share": "dcf_fair_value",
    "dcf_value_per_share": "dcf_fair_value",
    "fair_value_per_share": "dcf_fair_value",
    "forward_pe": "pe_ttm",
    "trailing_pe": "pe_ttm",
    "forward_p_e": "pe_ttm",
    "trailing_p_e": "pe_ttm",
    "p_e_ratio": "pe_ttm",
    "dividend_yield_pct": "dividend_yield",
    "beta_capm": "beta",
    "macd_histogram_value": "macd_histogram",
    "macd_hist": "macd_histogram",
    "rsi_14": "rsi",
    "rsi14": "rsi",
    "rsi_2": "rsi2",
    "stochastic_rsi": "stochrsi",
    "price_velocity_5d": "price_velocity",
    "impact_5d": "impact",
    "trend_strength_idx": "trend_strength",
    "down_from_overhead_pct": "down_from_overhead",
    "downside_overhead_pct": "down_from_overhead",
    "price_lows": "band_low",
    "price_highs": "band_high",
    "band_upper": "band_high",
}


def resolve_ground_truth_key(key: str, ground_truth: dict) -> str | None:
    """Canonical key for a claim's ground_truth_key, or None if unresolvable.

    Returns the key itself when it is already in the ground-truth map; else
    the aliased canonical key (lowercased, spaces->underscores); else None
    (stays unverified — never fabricate a match).
    """
    if not key:
        return None
    k = str(key).strip().lower()
    for ch in (" ", "-", "/", "(", ")", ":", "%", "$"):
        k = k.replace(ch, "_")
    while "__" in k:
        k = k.replace("__", "_")
    k = k.strip("_")
    if k in ground_truth:
        return k
    canon = KEY_ALIASES.get(k)
    if canon and canon in ground_truth:
        return canon
    return None


@dataclass
class ClaimRecord:
    """One debater claim, structured for deterministic verification.

    Mirrors the ``quantitative_claims[]`` items of the source doc's
    ``debater_turn.json`` schema (design §4.7).
    """

    role: str
    round: int
    claim_id: str = ""
    kind: str = "quantitative"  # quantitative | qualitative | abstain
    value: float | None = None
    metric_name: str = ""
    ground_truth_key: str = ""
    source: str = ""  # tool/state key that produced the number
    source_label: str = ""
    confidence: float | None = None
    # L1 verification verdict persisted back onto the claim (P0): one of
    # valid / violated / abstain / unverified / qualitative ("" until L1
    # runs). Drives the active-disputes ledger surfaced in prompts.
    status: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "round": self.round,
            "claim_id": self.claim_id,
            "kind": self.kind,
            "value": self.value,
            "metric_name": self.metric_name,
            "ground_truth_key": self.ground_truth_key,
            "source": self.source,
            "source_label": self.source_label,
            "confidence": self.confidence,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ClaimRecord:
        return cls(
            role=str(d.get("role", "")),
            round=int(d.get("round", 0)),
            claim_id=str(d.get("claim_id", "")),
            kind=str(d.get("kind", "quantitative")),
            value=d.get("value"),
            metric_name=str(d.get("metric_name", "")),
            ground_truth_key=str(d.get("ground_truth_key", "")),
            source=str(d.get("source", "")),
            source_label=str(d.get("source_label", "")),
            confidence=d.get("confidence"),
            status=str(d.get("status", "") or ""),
        )


class ClaimLedger:
    """Append-only per-run claim store with rendering helpers."""

    def __init__(self):
        self._rows: list[ClaimRecord] = []

    def append(self, claim: ClaimRecord) -> None:
        if not claim.claim_id:
            claim.claim_id = f"{claim.role}_{claim.round}_{len(self._rows)}"
        self._rows.append(claim)

    def extend(self, claims: Iterable[ClaimRecord]) -> None:
        for c in claims:
            self.append(c)

    @property
    def rows(self) -> list[ClaimRecord]:
        return list(self._rows)

    def by_role(self, role: str) -> list[ClaimRecord]:
        return [r for r in self._rows if r.role == role]

    def for_round(self, round_no: int) -> list[ClaimRecord]:
        return [r for r in self._rows if r.round == round_no]

    def previous_claims(self, role: str, round_no: int) -> list[ClaimRecord]:
        """Claims by this role from strictly earlier rounds (for novelty)."""
        return [r for r in self._rows if r.role == role and r.round < round_no]

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self) -> list[dict]:
        return [r.to_dict() for r in self._rows]

    @classmethod
    def from_dict(cls, rows: list[dict]) -> ClaimLedger:
        ledger = cls()
        for d in rows:
            ledger.append(ClaimRecord.from_dict(d))
        return ledger

    def render_markdown(self, used_claim_ids: set[str] | None = None) -> str:
        """Compact claim ledger block for reports / judge context."""
        if not self._rows:
            return ""
        lines = ["**Claim ledger (grounded):**"]
        used = used_claim_ids or set()
        for r in self._rows:
            marker = "" if r.claim_id in used else " (unused)"
            value = "-" if r.value is None else f"{r.value:g}"
            lines.append(
                f"- `{r.claim_id}` {r.role} R{r.round} "
                f"{r.kind} {r.metric_name or r.ground_truth_key or '?'}={value} "
                f"src={r.source or '-'}{marker}"
            )
        return "\n".join(lines)


def verify_claim(
    claim: ClaimRecord,
    ground_truth: dict[str, float],
    sources: set[str] | None = None,
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT,
) -> dict:
    """Deterministic verification of one claim.

    Returns a dict: ``{claim_id, metric_name, kind, asserted_value,
    ground_truth_value, error_margin_pct, is_valid, status, reason}`` where
    ``status`` ∈ {valid, violated, abstain, unverified, qualitative}.

    Status precedence (hardest first):
    1. kind == abstain               -> abstain
    2. kind == qualitative           -> qualitative (weight ~0)
    3. quantitative with a source not in ``sources`` (when provided)
                                      -> violated (deceptive grounding)
    4. quantitative, unknown ground_truth_key:
         - no usable source          -> abstain (unsupported, downgraded)
         - has source                -> unverified (cannot check, not a pass)
    5. |asserted - truth|/|truth| > tolerance_pct -> violated
    6. matches within tolerance      -> valid
    """
    base = {
        "claim_id": claim.claim_id,
        "metric_name": claim.metric_name or claim.ground_truth_key,
        "kind": claim.kind,
        "asserted_value": claim.value,
        "ground_truth_value": None,
        "error_margin_pct": None,
        "is_valid": False,
        "status": ABSTAIN,
        "reason": "",
    }

    if claim.kind == "abstain":
        base["reason"] = "abstained"
        return base
    if claim.kind == "qualitative":
        base["status"] = QUALITATIVE
        base["reason"] = "qualitative (weight ~0)"
        return base
    if claim.kind != "quantitative":
        base["status"] = ABSTAIN
        base["reason"] = f"unknown kind {claim.kind!r}"
        return base

    # Quantitative claim: must have a source from THIS run's tool ledger.
    if sources is not None and claim.source and claim.source not in sources:
        base["status"] = VIOLATED
        base["reason"] = "deceptive grounding: source not in run ledger"
        return base

    resolved_key = resolve_ground_truth_key(claim.ground_truth_key, ground_truth)
    truth = ground_truth.get(resolved_key) if resolved_key else None
    if truth is None:
        if not claim.source:
            base["status"] = ABSTAIN
            base["reason"] = "unsupported quantitative claim (no source)"
        else:
            base["status"] = UNVERIFIED
            base["reason"] = f"no ground truth for {claim.ground_truth_key!r}"
        return base

    if claim.value is None:
        base["status"] = ABSTAIN
        base["reason"] = "quantitative claim with no value"
        return base

    denom = abs(truth) if truth else 1.0
    err = abs(claim.value - truth) / denom * 100.0
    base["ground_truth_value"] = truth
    base["error_margin_pct"] = round(err, 4)
    if err <= tolerance_pct:
        base["status"] = VALID
        base["is_valid"] = True
        base["reason"] = f"within {tolerance_pct:g}% tolerance"
    else:
        base["status"] = VIOLATED
        base["reason"] = f"{err:g}% off ground truth (> {tolerance_pct:g}%)"
    return base
