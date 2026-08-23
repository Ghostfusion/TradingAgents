"""Pre-Market Reviewer: re-validates a prior close-time decision against
measured overnight deltas (design: ``docs/pre_market_review.md`` §7).

Choice (a) of the design: the in-batch step is a same-night catalyst/quality
re-check, and the full gap/anchor path runs in the standalone pre-open script.
Both reuse the deep LLM (``deep_think_llm``) exactly like the Portfolio
Manager — no new graph node, just a prompt variant — and the factory lives in
its own file so a dedicated node can be split out later without rewiring the
graph.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PreMarketVerdict, render_pre_market_verdict
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_pre_market_reviewer(llm):
    """Return a self-contained callable reviewing a prior decision at the open.

    The reviewer is a pure prompt variant over the deep LLM: it reads the prior
    decision plus a pre-built, number-only ``deltas_summary`` (already computed
    deterministically by ``strategies/pre_market.review_decision``) and emits a
    ``PreMarketVerdict``. It has no tool node of its own — every delta is
    computed *before* the call, so the LLM only reasons over the numbers
    (compute, don't narrate).
    """

    structured_llm = bind_structured(llm, PreMarketVerdict, "Pre-Market Reviewer")

    def pre_market_reviewer(prior_decision: str, deltas_summary: str) -> str:
        """Run one review; return the rendered verdict markdown.

        ``deltas_summary`` is a compact text block of measured numbers (gap % /
        ATR, catalyst window, capital-at-risk). The reviewer must index it, never
        invent a value.
        """
        prompt = f"""As the Pre-Market Reviewer, re-validate a prior close-time decision against the fresh overnight deltas and deliver one verdict.

**Prior decision (from the prior report):**
{prior_decision}

**Measured overnight deltas (deterministic):**
{deltas_summary}

Verdict rules (design §6):
- **CONFIRM** — nothing measured changed the plan; the prior decision stands.
- **REVISE** — keep the idea but re-anchor entry/stop/size to the measured open.
- **REJECT** — the prior plan is invalid: a gap through the stop, a catalyst
  hard block, or a re-anchored size cap breach. Every reason must cite a
  measured delta (never "sentiment seems worse").

Default to **CONFIRM** when the deltas do not change the plan.

{NO_EXTERNAL_TOOLS}{get_language_instruction()}"""

        return invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pre_market_verdict,
            "Pre-Market Reviewer",
        )

    return pre_market_reviewer
