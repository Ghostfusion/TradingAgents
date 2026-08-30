"""Option-A hybrid: independent pre-debate stances, debate stays a stress test.

Each of the 3 risk debators + 2 researchers emits ONE structured stance on
the trade proposal BEFORE the debate loop runs. The stance prompt contains NO
debate transcript and NO opponents' responses — the independence invariant
the research argues for (FREE-MAD: consensus pressure reduces reasoning
accuracy; adversarial persuasion can drag a group toward a wrong consensus).
The G3 agreement/consensus math therefore comes from opinions sampled before
any cross-talk, not from round-N rhetoric.

The debate then runs unchanged as the risk-surfacing / explanation layer; the
Portfolio Manager receives both the independent pre-debate distribution
(``computed_independent_vote`` / ``risk_independent_stances``) and the full
transcript. Gated by ``enable_independent_vote``: when off, the nodes no-op
and every consumer falls back to the legacy parse-from-history path.
"""

from __future__ import annotations

import contextlib

from tradingagents.agents.schemas import IndependentStance, render_stance
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)
from tradingagents.agents.utils.rating import parse_rating
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.dataflows.config import get_config
from tradingagents.strategies.consensus import agreement_score, consensus_from_score

RISK_ROLES = ("aggressive", "conservative", "neutral")
RESEARCHER_ROLES = ("bull", "bear")

# One-line persona per role, kept aligned with the debate prompts but framed
# as an honest read of the evidence (never "defend this position").
_PERSONA = {
    "aggressive": (
        "you naturally weight upside, growth, and competitive advantage; state your "
        "genuine read of the proposal on that axis"
    ),
    "conservative": (
        "you naturally weight downside, drawdown, and fragility; state your genuine "
        "read of the proposal on that axis"
    ),
    "neutral": (
        "you aim for a balanced, evidence-weighted read of both sides; state your "
        "genuine read of the proposal"
    ),
    "bull": (
        "You naturally build the strongest evidence-based case for investing. "
        "State how strong that case really is on the evidence alone."
    ),
    "bear": (
        "You naturally stress-test the thesis for fragility and downside. "
        "State how strong that case really is on the evidence alone."
    ),
}

_PERSONA_NAME = {
    "aggressive": "Aggressive Risk Analyst",
    "conservative": "Conservative Risk Analyst",
    "neutral": "Neutral Risk Analyst",
    "bull": "Bull Researcher",
    "bear": "Bear Researcher",
}


def build_stance_prompt(role: str, state: dict) -> str:
    """Independent stance prompt: analyst reports + computed context ONLY.

    Deliberately excludes ``risk_debate_state`` / ``investment_debate_state``
    (no history, no opponent responses, no speaker prefixes) — the whole
    point of the pass. The independence invariant is asserted in tests.
    """
    name = _PERSONA_NAME[role]
    persona = _PERSONA[role]
    instrument_context = get_instrument_context_from_state(state)
    computed_context = state.get("computed_decision_context") or ""

    plan_line = ""
    if role in RISK_ROLES:
        plan_line = f"\nTrader's proposal: {state.get('trader_investment_plan', '')}\n"

    prompt = f"""You are the {name}, reporting your INDEPENDENT stance BEFORE any debate begins.

Your role: {persona}. You have NOT seen any other analyst's argument. Do not
simulate, quote, or reference any debate, transcript, history, or other
speaker — judge only the evidence below and state YOUR OWN stance.{plan_line}

Evidence available:
{instrument_context}
Market research report: {state.get('market_report', '')}
Social media sentiment report: {state.get('sentiment_report', '')}
Latest world affairs news: {state.get('news_report', '')}
Company fundamentals report: {state.get('fundamentals_report', '')}

**Computed decision context (deterministic, advisory - ground your stance in
these numbers, never invent your own):**
{computed_context}

Output a single structured stance: the rating (Buy / Overweight / Hold /
Underweight / Sell), your confidence 0-1, a case strength 0-100 (how strongly
the evidence argues for your rating), and a one-sentence reason citing
computed values or stating 'unavailable'.

{NO_EXTERNAL_TOOLS}""" + get_language_instruction() + get_output_budget("debater")

    return prompt


def _sample_stance(structured_llm, plain_llm, prompt: str) -> dict:
    """One role's stance: structured call with a result hook; free-text fallback.

    Returns a dict ``{rating, confidence, strength, reason}`` where
    ``rating`` is always the canonical 5-tier string (or the parse of the
    free-text fallback) — never fabricated.
    """
    holder: dict = {}

    def hook(result) -> None:
        rating = result.rating
        holder["stance"] = {
            "rating": rating.value if hasattr(rating, "value") else str(rating),
            "confidence": result.confidence,
            "strength": result.strength,
            "reason": (result.reason or "").strip(),
        }

    text = invoke_structured_or_freetext(
        structured_llm,
        plain_llm,
        prompt,
        render_stance,
        "independent stance",
        result_hook=hook,
    )
    if "stance" in holder:
        return holder["stance"]
    # Free-text fallback (provider lacks structured output): parse the rating
    # deterministically; confidence/strength are unknown, never guessed.
    return {
        "rating": parse_rating(text),
        "confidence": None,
        "strength": None,
        "reason": (text or "").strip(),
    }


def create_independent_stance_node(roles, llm):
    """Return a graph node sampling one independent stance per role.

    ``roles`` must be all risk roles (aggressive/conservative/neutral) or all
    researcher roles (bull/bear). The risk node also writes
    ``computed_independent_vote`` (the deterministic agreement summary);
    the researcher node writes only the per-role stances. Gated by
    ``enable_independent_vote``: when off the node no-ops so the debate path
    is byte-for-byte unchanged.
    """
    risk_roles = tuple(r for r in roles if r in RISK_ROLES)
    researcher_roles = tuple(r for r in roles if r in RESEARCHER_ROLES)
    if risk_roles and researcher_roles:
        raise ValueError("a stance node must be all-risk or all-researcher roles")
    selected = risk_roles or researcher_roles

    structured_llm = bind_structured(llm, IndependentStance, "Independent Stance")

    def independent_stance_node(state) -> dict:
        if not (get_config() or {}).get("enable_independent_vote"):
            return {}

        stances: dict = {}
        for role in selected:
            stances[role] = _sample_stance(
                structured_llm, plain_llm=llm, prompt=build_stance_prompt(role, state)
            )

        out: dict = {}
        if risk_roles:
            out["risk_independent_stances"] = {
                role: stances[role] for role in risk_roles
            }
            out["computed_independent_vote"] = build_independent_vote_summary(
                {role: stances[role] for role in risk_roles},
                {},
            )
        if researcher_roles:
            out["researcher_independent_stances"] = {
                role: stances[role] for role in researcher_roles
            }
        return out

    return independent_stance_node


def independent_agreement(risk_stances: dict) -> float | None:
    """agreement_score over the INDEPENDENT risk ratings; None < 2 valid."""
    ratings = []
    for role in RISK_ROLES:
        s = risk_stances.get(role) or {}
        rating = s.get("rating")
        if isinstance(rating, str) and rating:
            ratings.append(rating)
    if len(ratings) < 2:
        return None
    return agreement_score(ratings)


def _fmt_strength(v) -> str:
    if v is None:
        return ""
    try:
        return f" (strength {int(v)}/100)"
    except (TypeError, ValueError):
        return ""


def build_independent_vote_summary(risk_stances: dict, researcher_stances: dict) -> str:
    """Deterministic markdown: agreement from INDEPENDENT ratings + role reads.

    Pure function over the sampled stances — no LLM here, so it is
    unit-testable and stable for prompt injection / reporting.
    """
    ratings = []
    role_lines = []
    for role in RISK_ROLES:
        s = risk_stances.get(role) or {}
        rating = s.get("rating")
        if isinstance(rating, str) and rating:
            ratings.append(rating)
        bits = [f"- **{role.capitalize()}**: {rating or 'unavailable'}"]
        bits.append(_fmt_strength(s.get("strength")))
        conf = s.get("confidence")
        if conf is not None:
            with contextlib.suppress(TypeError, ValueError):
                bits.append(f" (conf {float(conf):.2f})")
        role_lines.append("".join(bits))

    score = independent_agreement(risk_stances)
    label = consensus_from_score(score)
    head = (
        f"agreement={score:.2f} label={label} (n={len(ratings)})"
        if score is not None
        else "agreement=unavailable (fewer than 2 rated pre-debate stances)"
    )

    lines = [
        "**Independent pre-debate risk stances** (sampled before any cross-talk):",
        *role_lines,
        f"**Independent agreement**: {head}",
    ]
    if researcher_stances:
        lines.append("**Independent researcher reads** (pre-debate):")
        for role in RESEARCHER_ROLES:
            s = researcher_stances.get(role) or {}
            reason = (s.get("reason") or "").strip()
            lines.append(
                f"- {role.capitalize()}: {s.get('rating') or 'unavailable'}"
                f"{_fmt_strength(s.get('strength'))}"
                + (f" — {reason}" if reason else "")
            )
    lines.append(
        "Set your PortfolioDecision.consensus to this computed level, not a "
        "guess; pre-debate disagreement is a genuine dissent flag (no debate "
        "conformity contaminates it)."
    )
    return "\n".join(lines)


__all__ = [
    "RISK_ROLES",
    "RESEARCHER_ROLES",
    "build_stance_prompt",
    "create_independent_stance_node",
    "independent_agreement",
    "build_independent_vote_summary",
]
