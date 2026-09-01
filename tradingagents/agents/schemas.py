"""Pydantic schemas used by agents that produce structured output.

The framework's primary artifact is still prose: each agent's natural-language
reasoning is what users read in the saved markdown reports and what the
downstream agents read as context.  Structured output is layered onto the
three decision-making agents (Research Manager, Trader, Portfolio Manager)
so that:

- Their outputs follow consistent section headers across runs and providers
- Each provider's native structured-output mode is used (json_schema for
  OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic)
- Schema field descriptions become the model's output instructions, freeing
  the prompt body to focus on context and the rating-scale guidance
- A render helper turns the parsed Pydantic instance back into the same
  markdown shape the rest of the system already consumes, so display,
  memory log, and saved reports keep working unchanged
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# LLMs sometimes write a placeholder string ("None", "N/A", ...) into an optional
# numeric field instead of omitting it. Coerce those to None so the structured
# call validates instead of erroring (#1058). Pydantic still parses real numeric
# strings ("189.5") to float.
_NULLISH_FLOAT = {"", "none", "n/a", "na", "null", "nil", "-", "tbd", "unknown"}


def _coerce_optional_float(value):
    if isinstance(value, str) and value.strip().lower() in _NULLISH_FLOAT:
        return None
    return value


# ---------------------------------------------------------------------------
# Shared rating types
# ---------------------------------------------------------------------------


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader.

    The Trader's job is to translate the Research Manager's investment plan
    into a concrete transaction proposal: should the desk execute a Buy, a
    Sell, or sit on Hold this round.  Position sizing and the nuanced
    Overweight / Underweight calls happen later at the Portfolio Manager.
    """

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


# ---------------------------------------------------------------------------
# Research Manager
# ---------------------------------------------------------------------------


class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager.

    Hand-off to the Trader: the recommendation pins the directional view,
    the rationale captures which side of the bull/bear debate carried the
    argument, and the strategic actions translate that into concrete
    instructions the trader can execute against.
    """

    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Reserve Hold for situations where the "
            "evidence on both sides is genuinely balanced; otherwise commit to "
            "the side with the stronger arguments."
        ),
    )
    rationale: str = Field(
        description=(
            "Conversational summary of the key points from both sides of the "
            "debate, ending with which arguments led to the recommendation. "
            "Speak naturally, as if to a teammate."
        ),
    )
    strategic_actions: str = Field(
        description=(
            "Concrete steps for the trader to implement the recommendation, "
            "including position sizing guidance consistent with the rating."
        ),
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown for storage and the trader's prompt context."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader.

    The trader reads the Research Manager's investment plan and the analyst
    reports, then turns them into a concrete transaction: what action to
    take, the reasoning that justifies it, and the practical levels for
    entry, stop-loss, and sizing.
    """

    action: TraderAction = Field(
        description="The transaction direction. Exactly one of Buy / Hold / Sell.",
    )
    reasoning: str = Field(
        description=(
            "The case for this action, anchored in the analysts' reports and "
            "the research plan. Two to four sentences."
        ),
    )
    entry_price: float | None = Field(
        default=None,
        description="Optional entry price target in the instrument's quote currency.",
    )
    stop_loss: float | None = Field(
        default=None,
        description="Optional stop-loss price in the instrument's quote currency.",
    )
    position_sizing: str | None = Field(
        default=None,
        description="Optional sizing guidance, e.g. '5% of portfolio'.",
    )

    @field_validator("entry_price", "stop_loss", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown.

    The trailing ``FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`` line is
    preserved for backward compatibility with the analyst stop-signal text
    and any external code that greps for it.
    """
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Structured output produced by the Portfolio Manager.

    The model fills every field as part of its primary LLM call; no separate
    extraction pass is required. Field descriptions double as the model's
    output instructions, so the prompt body only needs to convey context and
    the rating-scale guidance.
    """

    rating: PortfolioRating = Field(
        description=(
            "The final position rating. Exactly one of Buy / Overweight / Hold / "
            "Underweight / Sell, picked based on the analysts' debate."
        ),
    )
    executive_summary: str = Field(
        description=(
            "A concise action plan covering entry strategy, position sizing, "
            "key risk levels, and time horizon. Two to four sentences."
        ),
    )
    investment_thesis: str = Field(
        description=(
            "Detailed reasoning anchored in specific evidence from the analysts' "
            "debate. If prior lessons are referenced in the prompt context, "
            "incorporate them; otherwise rely solely on the current analysis."
        ),
    )
    price_target: float | None = Field(
        default=None,
        description="Optional target price in the instrument's quote currency.",
    )
    time_horizon: str | None = Field(
        default=None,
        description="Optional recommended holding period, e.g. '3-6 months'.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Conviction in this decision, 0.0 (no conviction) to 1.0 (certain). "
            "Lower this when the risk analysts disagree or data is sparse; "
            "raise it when the debate converged on strong, well-evidenced views."
        ),
    )
    position_size: str | None = Field(
        default=None,
        description=(
            "Explicit position sizing guidance, e.g. '5% of portfolio', "
            "'2% initial, scale to 4% on confirmation', or '0% — no new "
            "position' when the decision is Hold/Underweight/Sell. This is the "
            "final, risk-adjusted size that caps the trader's proposal using the "
            "risk debate's volatility/liquidity assessment."
        ),
    )
    stop_loss: float | None = Field(
        default=None,
        description="Optional risk-management stop-loss price in the instrument's quote currency.",
    )
    consensus: Literal["high", "low"] | None = Field(
        default=None,
        description=(
            "Whether the risk analysts converged. 'high' = broadly aligned on "
            "the decision; 'low' = material disagreement (a dissent flag that "
            "should reduce confidence and position size)."
        ),
    )

    @field_validator("price_target", "stop_loss", "confidence", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision back to the markdown shape the rest of the system expects.

    Memory log, CLI display, and saved report files all read this markdown,
    so the rendered output preserves the exact section headers (``**Rating**``,
    ``**Executive Summary**``, ``**Investment Thesis**``) that downstream
    parsers and the report writers already handle.
    """
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    if decision.confidence is not None:
        parts.extend(["", f"**Confidence**: {decision.confidence:.2f}"])
    if decision.position_size:
        parts.extend(["", f"**Position Size**: {decision.position_size}"])
    if decision.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {decision.stop_loss}"])
    if decision.consensus is not None:
        parts.extend(["", f"**Consensus**: {decision.consensus.capitalize()}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Independent pre-debate stance (Option-A hybrid)
# ---------------------------------------------------------------------------


class IndependentStance(BaseModel):
    """One decision role's independent, pre-debate stance.

    Sampled by the Option-A pre-pass BEFORE any debate cross-talk: the prompt
    contains no transcript and no opponents' responses, so the G3
    agreement/consensus math (and the PM's dissent flag) comes from
    independent opinions, not round-N rhetoric contaminated by conformity.
    The debate still runs afterwards, unchanged, as the risk-surfacing /
    explanation layer.
    """

    rating: PortfolioRating = Field(
        description=(
            "This role's independent rating of the trade decision before any "
            "debate: exactly one of Buy / Overweight / Hold / Underweight / "
            "Sell, grounded only in the evidence below."
        ),
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Conviction in this stance, 0.0 to 1.0, formed before seeing any "
            "other role's argument."
        ),
    )
    strength: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Case strength 0-100: how strongly the evidence argues for this "
            "rating (100 = overwhelming case, 0 = barely any case)."
        ),
    )
    reason: str = Field(
        default="",
        description=(
            "One short, evidence-anchored sentence justifying the stance from "
            "the reports below. Never invent numbers; cite computed values or "
            "state 'unavailable'."
        ),
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)

    @field_validator("strength", mode="before")
    @classmethod
    def _nullish_int_to_none(cls, v):
        if isinstance(v, str) and v.strip().lower() in _NULLISH_FLOAT:
            return None
        return v


def render_stance(stance: IndependentStance) -> str:
    """Render an IndependentStance to the markdown stored in state."""
    parts = [f"**Rating**: {stance.rating.value}", ""]
    if stance.confidence is not None:
        parts.extend(["", f"**Confidence**: {stance.confidence:.2f}"])
    if stance.strength is not None:
        parts.extend(["", f"**Strength**: {stance.strength}/100"])
    if stance.reason:
        parts.extend(["", f"**Reason**: {stance.reason}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Sentiment Analyst
# ---------------------------------------------------------------------------


class SentimentBand(str, Enum):
    """Discrete sentiment direction produced by the Sentiment Analyst.

    Six tiers keep the signal granular enough to be actionable while remaining
    small enough for every provider to map reliably from its JSON output.
    """

    BULLISH = "Bullish"
    MILDLY_BULLISH = "Mildly Bullish"
    NEUTRAL = "Neutral"
    MIXED = "Mixed"
    MILDLY_BEARISH = "Mildly Bearish"
    BEARISH = "Bearish"


class SentimentReport(BaseModel):
    """Structured sentiment report produced by the Sentiment Analyst.

    Replaces the previous free-form prose output so downstream consumers
    (dashboards, audit logs, PDF renderers, other agents) can read
    ``overall_band`` and ``overall_score`` without maintaining fragile regex
    fallbacks that drift with every model release. ``narrative`` preserves the
    rich source-by-source analysis; ``render_sentiment_report`` prepends a
    deterministic header so the saved report stays human-readable.
    """

    overall_band: SentimentBand = Field(
        description=(
            "Overall sentiment direction. Exactly one of: "
            "Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. "
            "Use Mixed when sources point in clearly different directions. "
            "Use Neutral only when all sources are genuinely silent or non-committal."
        ),
    )
    overall_score: float = Field(
        ge=0.0,
        le=10.0,
        description=(
            "Numeric sentiment intensity on a 0–10 scale. "
            "0 = maximally bearish, 5 = neutral, 10 = maximally bullish. "
            "Guideline for consistency with overall_band: "
            "Bullish ~6.5–10, Mildly Bullish ~5.5–6.4, Neutral/Mixed ~4.5–5.5, "
            "Mildly Bearish ~3.5–4.4, Bearish ~0–3.4. "
            "Only the 0–10 bounds are enforced."
        ),
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description=(
            "Confidence in the assessment based on data quality and sample size. "
            "Use 'low' when one or more sources returned a placeholder or fewer "
            "than 5 data points; 'medium' when data is present but sparse; "
            "'high' when all three sources returned substantive data."
        ),
    )
    computed_score: float | None = Field(
        default=None,
        description=(
            "Deterministic signed sentiment in [-1, 1] from labeled message "
            "counts (vendor labels), computed by the pipeline (not the LLM) "
            "when enable_sentiment is on."
        ),
    )
    computed_velocity: float | None = Field(
        default=None,
        description=(
            "z-score of today's computed_score vs the ticker's rolling 30-day "
            "baseline of deterministic scores."
        ),
    )
    sample_size: int | None = Field(
        default=None,
        description="Number of labeled sentiment messages used for computed_score.",
    )
    narrative: str = Field(
        description=(
            "Full sentiment report covering, in order: "
            "(1) source-by-source breakdown with specific evidence (cite message "
            "counts, ratios, notable posts); "
            "(2) cross-source divergences and alignments; "
            "(3) dominant narrative themes; "
            "(4) catalysts and risks surfaced by the data; "
            "(5) a markdown table summarising key sentiment signals, their "
            "direction, source, and supporting evidence. "
            "Keep it informative and substantive: develop each section thoroughly "
            "with concrete evidence so every point adds new signal for the trader."
        ),
    )


def render_sentiment_report(report: SentimentReport) -> str:
    """Render a SentimentReport to the markdown shape the rest of the system expects.

    The structured header (band + score + confidence) is prepended to the
    narrative so the saved report is both human-readable and machine-parseable
    without regex.
    """
    return "\n".join([
        f"**Overall Sentiment:** **{report.overall_band.value}** "
        f"(Score: {report.overall_score:.1f}/10)",
        f"**Confidence:** {report.confidence.capitalize()}",
        "",
        _computed_line(report),
        report.narrative,
    ])


def _computed_line(report) -> str:
    """Deterministic computed-sentiment line; empty when unset."""
    if report.computed_score is None:
        return ""
    extra = f"{report.computed_score:+.2f}"
    if report.computed_velocity is not None and report.sample_size is not None:
        extra += f" (velocity {report.computed_velocity:+.2f}sigma, n={report.sample_size})"
    elif report.computed_velocity is not None:
        extra += f" (velocity {report.computed_velocity:+.2f}sigma)"
    elif report.sample_size is not None:
        extra += f" (n={report.sample_size})"
    return f"**Computed Sentiment:** {extra}"


# ---------------------------------------------------------------------------
# Pre-Market Reviewer
# ---------------------------------------------------------------------------


class PreMarketVerdict(BaseModel):
    """Structured verdict produced by the pre-market reviewer (design
    ``docs/pre_market_review.md`` §7).

    Re-validates a prior close-time decision against measured overnight
    deltas. ``CONFIRM`` = the prior decision still stands; ``REVISE`` = keep
    the idea but re-anchor entry/stop/size to the open; ``REJECT`` = drop the
    plan (gap through the stop, catalyst hard block, or a cap breach on the
    re-anchored size). Every reason must cite a measured delta — a no-fabrication
    rule identical to the analyst tools; when nothing measurable changed the
    verdict must be ``CONFIRM``.
    """

    verdict: Literal["CONFIRM", "REVISE", "REJECT"] = Field(
        description=(
            "Exactly one of CONFIRM (the prior decision still stands), REVISE "
            "(keep the idea but re-anchor entry/stop/size to the measured open), "
            "or REJECT (drop the plan - gap through the stop, catalyst hard "
            "block, or a re-anchored size cap breach). Default to CONFIRM when "
            "nothing measurable changed."
        ),
    )
    entry_price: float | None = Field(
        default=None,
        description="Re-anchored entry price (usually the pre-market/open price) when REVISE.",
    )
    stop_loss: float | None = Field(
        default=None,
        description="Re-anchored stop-loss price when REVISE.",
    )
    position_size: float | None = Field(
        default=None,
        description="Re-anchored position size as a fraction (0..1) when REVISE; None = keep prior size.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Every reason must cite a measured delta (gap % / ATR, catalyst "
            "window days, re-anchored capital-at-risk). Empty reasons are only "
            "allowed for CONFIRM."
        ),
    )
    catalyst_days_to_print: int | None = Field(
        default=None,
        description="Days until the next scheduled earnings print, when known.",
    )

    @field_validator("entry_price", "stop_loss", "position_size", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)


def render_pre_market_verdict(verdict: PreMarketVerdict) -> str:
    """Render a PreMarketVerdict to the markdown the saved report consumes."""
    parts = [f"**Verdict**: {verdict.verdict}"]
    if verdict.entry_price is not None:
        parts.append(f"**Entry Price**: {verdict.entry_price}")
    if verdict.stop_loss is not None:
        parts.append(f"**Stop Loss**: {verdict.stop_loss}")
    if verdict.position_size is not None:
        parts.append(f"**Position Size**: {verdict.position_size:.2%}")
    if verdict.catalyst_days_to_print is not None:
        parts.append(f"**Days to Earnings**: {verdict.catalyst_days_to_print}")
    if verdict.reasons:
        parts.append("**Reasons**: " + "; ".join(verdict.reasons))
    return "\n".join(parts)


class ActionConditionVerdict(BaseModel):
    """Optional LLM judge verdict for a report condition the deterministic
    checker could not fully resolve (design: ``scripts/action_report.py``).

    The deterministic checker (price levels, SMA/volume/MACD/RSI refs) is the
    primary path and never fabricates; this schema is only used when
    ``--llm`` is passed and a condition is UNKNOWN. The judge must reason over
    the provided market snapshot only (no external tools) and must say
    UNKNOWN when the evidence is insufficient — never invent a number.
    """

    verdict: Literal["MET", "NOT_MET", "UNKNOWN"] = Field(
        description=(
            "Exactly one of MET (the condition is satisfied by the snapshot), "
            "NOT_MET (the snapshot contradicts it), or UNKNOWN (insufficient "
            "evidence - never guess)."
        ),
    )
    reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Every reason must cite a number from the provided market snapshot "
            "(price, SMA, volume ratio, RSI, MACD). Empty reasons are only "
            "allowed for UNKNOWN with an explicit 'insufficient evidence' note."
        ),
    )


# ---------------------------------------------------------------------------
# Structured multi-agent debate — canonical wire schemas
# (design docs/design_multi_agent_debate.md §4.7, rev v3; pydantic mirrors of
#  the source doc Strategies/Multi_Agents_Debate.md's four JSON schemas)
# ---------------------------------------------------------------------------


class Stance(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"


class RiskStance(str, Enum):
    """Risk-debater role for the structured risk debate (direction.md parity).

    The risk section mirrors the research debate but with three roles
    (aggressive / conservative / neutral) instead of two (bull / bear). The
    payload schema is identical to ``DebaterTurnPayload`` except the stance
    enum — the L1 verification and blind judge machinery are shared.
    """

    AGGRESSIVE = "AGGRESSIVE"
    CONSERVATIVE = "CONSERVATIVE"
    NEUTRAL = "NEUTRAL"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class QuantitativeClaim(BaseModel):
    """One grounded quantitative claim (debater_turn.json quantitative_claims[]).

    Provider-tolerant (deepseek sends ragged free-text JSON): only
    ``asserted_value`` is required for a claim to be verifiable; a claim
    missing ``ground_truth_key``/``source`` still PARSES and L1 scores it
    ``unverified`` (soft penalty) instead of failing the whole turn.
    """

    metric_name: str = Field(
        default="", description="Human-readable metric (e.g. trailing P/E)"
    )
    asserted_value: float = Field(description="The number the debater asserts")
    ground_truth_key: str = Field(
        default="", description="Key of the computed state/tool value this claim maps to"
    )
    source: str = Field(
        default="", description="Tool/state call that actually produced the number this run"
    )


class RiskFactor(BaseModel):
    """One risk factor (debater_turn.json risk_factors[]).

    Provider-tolerant: deepseek's free-text JSON often omits fields or sends
    lowercase severity. All fields default; a ragged entry (missing risk_id)
    is DROPPED at the payload level by DebaterTurnPayload.sanitize_lists,
    never failing the whole turn.
    """

    risk_id: str = ""
    severity: RiskSeverity = RiskSeverity.LOW
    mitigation_stated: bool = False

    @field_validator("risk_id", mode="before")
    @classmethod
    def _coerce_risk_id(cls, v):
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        return str(v)

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v


class DebaterTurnPayload(BaseModel):
    """Structured turn from one debater role (source schema debater_turn.json).

    ``quantitative_claims`` may be EMPTY: that is the honest degraded turn
    (``create_debater_turn`` builds it when the LLM produced no structured
    payload). L1 scores it as zero evidence (GREEN/PROCEED, no verifications)
    and the report renders the "no structured turn produced" prose — an empty
    turn must never raise, or one failed provider kills the whole run.
    """

    round_index: int = Field(ge=1, le=5)
    stance: Stance
    core_thesis: str = Field(max_length=1500)
    # Bounded lists: an unbounded payload lets a verbose model emit hundreds
    # of claims and truncate at the output cap (glm-5.3-flash -> 8000 tokens
    # every turn). 25 grounded claims is far beyond any grounded run's data.
    quantitative_claims: list[QuantitativeClaim] = Field(
        default_factory=list, max_length=25
    )
    risk_factors: list[RiskFactor] = Field(default_factory=list, max_length=25)
    recommended_allocation_pct: float = Field(ge=0.0, le=100.0)

    @field_validator("stance", mode="before")
    @classmethod
    def _norm_stance(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("quantitative_claims", mode="before")
    @classmethod
    def _sanitize_claims(cls, v):
        """Drop entries that can never be verified instead of failing the
        turn: non-dicts and entries without a parseable asserted_value."""
        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            if isinstance(item, BaseModel):
                # already-valid model instances pass through (a before
                # validator runs BEFORE nested coercion)
                out.append(item)
                continue
            if not isinstance(item, dict):
                continue
            try:
                float(item.get("asserted_value"))
            except (TypeError, ValueError):
                continue
            out.append(item)
        return out

    @field_validator("risk_factors", mode="before")
    @classmethod
    def _sanitize_risk_factors(cls, v):
        """Drop ragged risk entries (missing risk_id) — deepseek emits them
        often; a risk factor with no id is meaningless, not a turn killer."""
        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            if isinstance(item, BaseModel):
                out.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if not str(item.get("risk_id") or "").strip():
                continue
            out.append(item)
        return out


class RiskDebaterTurnPayload(DebaterTurnPayload):
    """Structured turn from a RISK debater role (aggressive/conservative/neutral).

    Identical contract to ``DebaterTurnPayload`` (grounded quantitative
    claims, risk factors, allocation) but the stance enum is the risk role —
    this is what lets the research section's L1/judge machinery run the risk
    debate unchanged (direction.md: both sections share the debater+judge
    pattern).
    """

    stance: RiskStance

    @field_validator("stance", mode="before")
    @classmethod
    def _coerce_risk_stance(cls, v):
        """Risk-stance fallback (tolerate ragged input): the shared 1-shot can
        leak the RESEARCH labels (BULL/BEAR) into a risk payload. Map them to
        their risk analog instead of hard-validation-failing a contract slip —
        a model slip is not a turn-killer. Unknown values still fall through
        to honest validation failure."""
        if isinstance(v, str):
            s = v.strip().upper()
            mapping = {
                "BULL": "AGGRESSIVE",
                "BEAR": "CONSERVATIVE",
            }
            return mapping.get(s, s)
        return v


class MetricVerification(BaseModel):
    """One L1 metric check (l1_eval_result.json metric_verification[])."""

    metric_name: str
    asserted_value: float
    ground_truth_value: float | None = None
    error_margin_pct: float | None = None
    is_valid: bool = False


class RiskGateEvaluation(BaseModel):
    """L1 risk-gate evaluation (l1_eval_result.json risk_gate_evaluation)."""

    max_drawdown_compliant: bool = False
    allocation_bound_compliant: bool = False
    calculated_var_95: float | None = None


class L1Verdict(str, Enum):
    PASS = "PASS"
    FAIL_HARD_GATE = "FAIL_HARD_GATE"
    FAIL_DATA_MISMATCH = "FAIL_DATA_MISMATCH"


class L1DeterministicResult(BaseModel):
    """L1 deterministic evaluation (source schema l1_eval_result.json)."""

    evaluation_timestamp: str = ""
    verdict: L1Verdict
    hard_gate_passed: bool = False
    metric_verification: list[MetricVerification] = Field(default_factory=list)
    risk_gate_evaluation: RiskGateEvaluation = Field(default_factory=RiskGateEvaluation)
    penalty_score: float = Field(ge=0.0, le=100.0, default=0.0)


class JudgeDimension(str, Enum):
    EMPIRICAL_GROUNDING = "empirical_grounding"
    DOWNSIDE_TAIL_RISK_WEIGHT = "downside_tail_risk_weight"
    CATALYST_CLARITY = "catalyst_clarity"
    ASSUMPTION_SENSITIVITY = "assumption_sensitivity"


class L2JudgeDimensionedRubric(BaseModel):
    """Blind L2 judge output (source schema l2_judge_rubric.json).

    Provider-tolerant (luna emits ragged string/object values for the bool/
    number fields on this OpenRouter route): coerce instead of failing the
    whole rubric — same discipline as the debater sanitizers. A malformed
    boolean/number is defaulted; dimension keys are validated by the
    judge's scoring loop (unknown keys dropped), never a rubric killer.
    """

    judge_model_id: str = ""
    round_evaluated: int = 0
    evaluated_agent_alias: str = Field(
        default="", description="Anonymized token (Candidate_X / Candidate_Y)"
    )
    dimension_scores: dict[JudgeDimension, float] = Field(
        default_factory=dict, description="0..10 per orthogonal dimension"
    )
    entrenchment_detected: bool = False
    rebuttal_effectiveness: float = Field(ge=0.0, le=10.0, default=0.0)
    rationale: str = Field(default="", max_length=1000)

    @field_validator("entrenchment_detected", mode="before")
    @classmethod
    def _coerce_entrenchment(cls, v):
        """'true'/'false'/'True'/'1'/'yes' -> bool; anything else -> False."""
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes", "y"):
                return True
            if s in ("false", "0", "no", "n", ""):
                return False
        return False

    @field_validator("rebuttal_effectiveness", mode="before")
    @classmethod
    def _coerce_rebuttal(cls, v):
        """Number-or-numeric-string; clamp 0..10; anything else -> 0.0."""
        if isinstance(v, (int, float)):
            return max(0.0, min(float(v), 10.0))
        if isinstance(v, str):
            try:
                f = float(v.strip())
                return max(0.0, min(f, 10.0))
            except (TypeError, ValueError):
                pass
        return 0.0


class L1SeverityTier(str, Enum):
    GREEN = "GREEN"
    SOFT_WARNING = "SOFT_WARNING"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    HARD_BREACH = "HARD_BREACH"


class L1Action(str, Enum):
    PROCEED = "PROCEED"
    APPLY_PENALTY_AND_PROCEED = "APPLY_PENALTY_AND_PROCEED"
    TRIGGER_REGEN = "TRIGGER_REGEN"
    ABORT_TO_BASELINE = "ABORT_TO_BASELINE"


class EntrenchmentMetrics(BaseModel):
    entrenchment_index: float = Field(ge=0.0, le=1.0, default=0.0)
    divergence_delta: float | None = None
    artificial_consensus_flag: bool = False
    reweight_alpha: float = Field(ge=0.0, le=1.0, default=0.0)

class BaselineFallbackPayload(BaseModel):
    base_allocation_pct: float = 0.0
    var_95_limit: float = 0.0
    unconditional_risk_rating: str = ""


class L1ExecutionContext(BaseModel):
    """Recovery-path record between FSM states (l1_execution_context.json)."""

    round_index: int = Field(ge=1, default=1)
    regen_count: int = Field(ge=0, default=0)
    debate_regen_max: int = Field(default=1)
    severity_tier: L1SeverityTier = L1SeverityTier.GREEN
    l1_action: L1Action = L1Action.PROCEED
    entrenchment_metrics: EntrenchmentMetrics = Field(default_factory=EntrenchmentMetrics)
    baseline_fallback_payload: BaselineFallbackPayload = Field(
        default_factory=BaselineFallbackPayload
    )


def render_l1_context(ctx: L1ExecutionContext) -> str:
    """Render an L1ExecutionContext to a compact audit row."""
    return (        f"**L1:** t{ctx.round_index} / {ctx.severity_tier.value} / "
        f"regen {ctx.regen_count}/{ctx.debate_regen_max} / "
        f"{ctx.l1_action.value}"
    )
