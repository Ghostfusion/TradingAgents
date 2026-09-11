"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

import logging
import re as _re

from langchain_core.messages import AIMessage

from tradingagents.agents.schemas import TraderProposal, render_trader_proposal
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)

logger = logging.getLogger(__name__)


_VERIFY_ASSIGNMENT_RE = _re.compile(r"\b[a-z_]{2,}\s*=\s*[-+]?\d", _re.IGNORECASE)
_VERIFY_ANNOUNCEMENT_RE = _re.compile(
    r"\b(let me|i'?ll|i will|will verify|next,? i|i'?m going to)\b", _re.IGNORECASE
)


def _verification_is_stub(text: object) -> bool:
    """True when the post-proposal verification pass produced no trade spec.

    The verify prompt asks for a compact spec (`entry=… stop=… size_pct=… rr=…`)
    plus cited reasons. A reply that *announces* the checks is a status turn, not
    a verification — GOOG 2026-09-11 trader.md appended, under the heading
    "**Computed verification (deterministic tools):**", the text "Key finding
    already: … Let me verify the exit arithm and the stop validity." with no
    numbers, no spec and no tool citation. Reject: no digits at all, or an
    announcement carrying no ``field=value`` assignment (naming a field in prose
    — "the stop validity" — is not a spec).
    """
    t = str(text or "").strip()
    if not t:
        return True
    if not any(ch.isdigit() for ch in t):
        return True
    if _VERIFY_ASSIGNMENT_RE.search(t):
        return False
    return bool(_VERIFY_ANNOUNCEMENT_RE.search(t))


def create_trader(llm, backup_llm=None):
    structured_llm = bind_structured(llm, TraderProposal, "Trader")

    def trader_node(state):
        company_name = state["company_of_interest"]
        instrument_context = get_instrument_context_from_state(state)
        investment_plan = state["investment_plan"]
        # Computed decision context (regime / re-rating / plan card / risk
        # snapshot) - advisory hard data compiled by the graph's
        # _compiled_decision_context; absent string = nothing to inject.
        computed_context = state.get("computed_decision_context") or ""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a trading agent analyzing market data to make investment decisions. "
                    "Based on your analysis, provide a specific recommendation to buy, sell, or hold. "
                    "Anchor your reasoning in the analysts' reports and the research plan. "
                    + NO_EXTERNAL_TOOLS
                    + get_language_instruction()
                    + get_output_budget("trader")
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Based on a comprehensive analysis by a team of analysts, here is an investment "
                    f"plan tailored for {company_name}. {instrument_context} This plan incorporates "
                    f"insights from current technical market trends, macroeconomic indicators, and "
                    f"social media sentiment. Use this plan as a foundation for evaluating your next "
                    f"trading decision.\n\nProposed Investment Plan: {investment_plan}\n\n"
                    f"Leverage these insights to make an informed and strategic decision.\n\n"
                    f"Computed decision context (deterministic, advisory - cite these numbers, "
                    f"do not invent your own):\n{computed_context}"
                ),
            },
        ]

        trader_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            messages,
            render_trader_proposal,
            "Trader",
            backup_llm=backup_llm,
            # Required TraderProposal fields: an empty action/reasoning must be
            # repaired, never rendered as a blank proposal.
            mandatory_fields=("action", "reasoning"),
        )

        # Post-proposal computed verification pass (Phase-5 audit wiring): the
        # plain LLM verifies the proposal's entry/stop/size against the
        # deterministic sizing + exit tools and returns a corrected compact
        # trade spec. Advisory - the structured proposal stays the primary
        # output; verification is appended as a labeled block the PM / risk
        # team read. Any failure degrades to a short 'unavailable' note.
        verification = ""
        try:
            from tradingagents.agents.utils.risk_tool_loop import (
                TRADER_TOOLS,
                run_tool_loop,
            )

            verify_prompt = (
                f"Here is the Trader's proposed transaction for {company_name}:\n\n"
                f"{trader_plan}\n\n"
                "Verify the entry / stop / position-size against the tools. Call "
                "get_position_sizing / get_fixed_risk_size (with the proposal's "
                "risk budget), get_risk_gate (PASS/WARN/REJECT on the proposed "
                "size), get_swing_set / get_swing_exits (structure stop + "
                "targets), get_exit_check / get_exit_plan / get_trailing_exit / "
                "get_scaleout_plan (exit arithm), get_tranche_plan (tranche "
                "levels), get_trade_expectancy (win-rate at the proposed R:R), "
                "get_trade_plan (the plan card). If the proposal is risky or "
                "mis-sized, say so with the computed numbers. Output a compact "
                "corrected trade spec: entry=... stop=... size_pct=... rr=... "
                "+ reasons citing the tool outputs. If a tool is 'unavailable' "
                "or no proposal levels exist, output 'verification unavailable'."
            )
            verification, _t = run_tool_loop(
                llm,
                verify_prompt,
                TRADER_TOOLS,
                system_text=(
                    "You are a trade-risk verifier. Only the deterministic "
                    "tools may produce numbers; never invent a price or size."
                ),
                max_rounds=2,  # bound runtime: 2 tool rounds per verification
            )
            if _verification_is_stub(verification):
                # A reply that ANNOUNCES the checks instead of reporting them is
                # a status turn, not a verification (GOOG 2026-09-11 trader.md:
                # the appended block read "Key finding already: … Let me verify
                # the exit arithm and the stop validity." with no numbers). Ask
                # once more for the spec the prompt already specified.
                logger.info("trader verification returned a status turn; asking once for the spec")
                verification, _t = run_tool_loop(
                    llm,
                    verify_prompt
                    + "\n\nOutput the compact spec NOW - one line, no preamble, "
                    "no description of what you intend to check: "
                    "entry=… stop=… size_pct=… rr=… + one reason per cited tool. "
                    "If nothing can be verified, output exactly 'verification unavailable'.",
                    TRADER_TOOLS,
                    system_text=(
                        "You are a trade-risk verifier. Only the deterministic "
                        "tools may produce numbers; never invent a price or size."
                    ),
                    max_rounds=2,
                )
        except Exception as exc:  # noqa: BLE001 - verification is advisory
            verification = f"verification unavailable: {exc}"
        if _verification_is_stub(verification) and "unavailable" not in verification[:40].lower():
            # Never append a promise under a heading that claims a computed
            # check: report it unavailable instead, so the PM/risk readers know
            # no deterministic verification happened.
            logger.warning(
                "trader verification produced no computed spec; reporting unavailable"
            )
            verification = "verification unavailable: the verifier returned no computed spec"
        if (
            verification
            and "unavailable" not in verification[:40].lower()
            and "<MagicMock" not in verification
            and "MagicMock" not in verification
        ):
            # A mock/stub LLM (tests) returns a Mock repr, not a real
            # verification; never append that to the proposal.
            trader_plan = (
                trader_plan
                + "\n\n**Computed verification (deterministic tools):**\n"
                + verification
            )

        return {
            "messages": [AIMessage(content=trader_plan)],
            "trader_investment_plan": trader_plan,
        }

    return trader_node
