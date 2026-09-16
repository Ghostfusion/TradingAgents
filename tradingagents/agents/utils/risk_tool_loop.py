"""In-node tool-calling loop for the risk debators + Trader.

The analyst nodes run their tool loop through LangGraph edges
(analyst -> tools -> analyst). The risk debators and the Trader sit inside
the fixed debate chain and mutate debate/structured state; adding graph edges
for them would multiply the edge-registration surface in both concurrency
modes. Instead the loop runs INSIDE the node: bind the plain LLM to a
per-role toolset, iterate tool calls up to ``MAX_TOOL_ROUNDS`` through a
``ToolExecutor``, and hand the final prose (or the cap-forced terminal turn,
via ``structured.finalize_messages``) back to the caller. Nothing leaves the
node, so risk_debate_state, the routers and the reports are untouched.

Advisory-only: every executed tool returns exact numbers or an explicit
"unavailable" string; a tool failure degrades to an "unavailable" ToolMessage
and the loop continues - it never raises and never fabricates.

A relay can answer a tool-bound turn with the provider's own tool-call markup
inside ``content`` and an EMPTY ``tool_calls`` list (OpenRouter +
deepseek/deepseek-v4.1-flash, 2026-09-15: the trader's verification turn). The
loop used to read that as "no tool calls" and hand the markup back as the final
prose, so the caller appended it under a heading that claims deterministic
verification - with no tool run at all. ``_turn_calls`` now parses the markup
into real calls (see ``tool_call_markup``) so that round executes, and
``_final_prose`` guarantees markup never reaches a caller as prose.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.agents.utils.tool_call_markup import (
    has_tool_call_markup,
    parse_text_tool_calls,
    strip_tool_call_markup,
)
from tradingagents.graph.conditional_logic import MAX_TOOL_ROUNDS
from tradingagents.llm_clients.base_client import content_to_text

# Returned instead of markup-only prose: the caller must never write a claim of
# a deterministic check it could not obtain. Starts with "unavailable" so the
# trader's append guard rejects it (see ``trader.create_trader``).
MARKUP_UNAVAILABLE = (
    "unavailable: the model returned tool-call markup instead of prose - no "
    "computed verification was produced"
)

# Appended to every system directive: the provider-native markup interface is
# not one this loop can rely on, so name the interface to use instead.
_NO_MARKUP_INSTRUCTION = (
    " Call the tools through the function-calling interface only. Never write "
    "tool-call markup (or a tool call as text) into your answer: a call written "
    "as text is not executed, and your answer is read by a human."
)

# Appended to every system directive as well: the two argument traps that
# produced wrong numbers in the reports. Every ``*_pct`` argument is a fraction
# (the gate read a 1% proposal as 100% and REJECTed it, NVDA 2026-09-15), and a
# market level the model supplies itself is an invented number that the tool
# then prints as if it were computed (the same run passed atr=7.0).
_LEVEL_BASIS_INSTRUCTION = (
    " Every argument named *_pct, and every size or drawdown, is a FRACTION of "
    "capital: 0.01 means 1%, not 1. Never pass a price, ATR or other market "
    "level you did not receive from a tool - pass ticker=<symbol> wherever a "
    "tool can measure it instead."
)

# Risk toolset for the 3 risk debators (aggressive/conservative/neutral).
# All wrap deterministic strategies over the run-level OHLCV cache or config;
# the LLM grounds every risk number it cites in one of these.
RISK_DEBATOR_TOOLS = []

# Sizing / exit toolset for the Trader (entry/stop/position-size grounding).
TRADER_TOOLS = []


def _build_lists() -> None:
    """Populate the tool lists lazily (avoids import-time cycles).

    ``analysis_tools`` and ``market_position_tools`` only import the vendor
    layer, so importing them here is safe; the tools themselves import the
    deterministic strategies at call time, never at module import.
    """
    global RISK_DEBATOR_TOOLS, TRADER_TOOLS
    if RISK_DEBATOR_TOOLS:
        return
    from tradingagents.agents.utils.analysis_tools import (
        get_book_tail_risk,
        get_composite_sizing,
        get_concentration_read,
        get_covariance_read,
        get_credit_spread_read,
        get_downside_read,
        get_exit_check,
        get_exit_overrides,
        get_fixed_risk_size,
        get_garch_volatility,
        get_horizon_var,
        get_ledger_risk_state,
        get_mean_reversion_quality,
        get_merton_distance,
        get_position_sizing,
        get_pre_trade_read,
        get_premarket_review,
        get_regime_gate_read,
        get_risk_gate,
        get_tail_decomposition,
        get_tail_extreme_var,
        get_tail_risk,
        get_trade_outcome_metrics,
        get_trade_plan,
        get_trailing_exit,
        get_vol_cones,
        get_volatility_estimators,
    )
    from tradingagents.agents.utils.market_position_tools import get_liquidity_risk
    from tradingagents.agents.utils.quant_formula_tools import get_book_risk_budget
    from tradingagents.agents.utils.value_dip_tools import (
        get_trade_expectancy,
        get_tranche_plan,
    )

    # Mutate in place (not rebind): callers hold a reference to the module
    # list object (``from ... import RISK_DEBATOR_TOOLS``); a rebind would
    # leave their reference empty and every tool-call would be 'unknown'.
    RISK_DEBATOR_TOOLS.extend([
        get_risk_gate,
        get_tail_risk,
        get_book_tail_risk,
        get_tail_decomposition,
        get_tail_extreme_var,
        get_covariance_read,
        get_concentration_read,
        get_horizon_var,
        get_downside_read,
        get_credit_spread_read,
        get_merton_distance,
        get_volatility_estimators,
        get_garch_volatility,
        get_mean_reversion_quality,
        get_tranche_plan,
        get_position_sizing,
        get_fixed_risk_size,
        get_exit_check,
        get_trailing_exit,
        get_liquidity_risk,
        get_book_risk_budget,
        get_premarket_review,
        get_ledger_risk_state,
        get_exit_overrides,
        get_pre_trade_read,
        get_vol_cones,
        get_regime_gate_read,
        get_trade_plan,
        get_trade_outcome_metrics,
    ])

    from tradingagents.agents.utils.analysis_tools import (
        get_book_tail_risk,
        get_composed_risk_gate,
        get_exit_plan,
        get_scaleout_plan,
        get_swing_exits,
        get_swing_set,
    )

    TRADER_TOOLS.extend([
        get_position_sizing,
        get_composite_sizing,
        get_risk_gate,
        # The composed (portfolio-gate > trade-gate) verdict and the book tail:
        # without these the trader's verification pass could only reach
        # get_risk_gate, so it "verified" the book drawdown with a
        # model-supplied number instead of the gate's measured one
        # (NVDA 2026-09-12).
        get_composed_risk_gate,
        get_book_tail_risk,
        get_fixed_risk_size,
        get_exit_check,
        get_exit_plan,
        get_trailing_exit,
        get_scaleout_plan,
        get_tranche_plan,
        get_trade_expectancy,
        get_trade_plan,
        get_swing_set,
        get_swing_exits,
    ])


class ToolExecutor:
    """Map tool name -> callable and execute one tool call, never raising."""

    def __init__(self, tools):
        self._by_name = {t.name: t for t in tools}

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def run(self, name: str, args: dict) -> str:
        fn = self._by_name.get(name)
        if fn is None:
            return f"unavailable: unknown tool {name}"
        try:
            out = fn.invoke(dict(args or {}))
            return str(out)
        except Exception as exc:  # noqa: BLE001 - degrade, never raise mid-loop
            return f"unavailable: {name} raised {exc}"


def _fmt_args(args: dict) -> str:
    return str(args)[:160]


def _first_line(text) -> str:
    line = (str(text) or "").splitlines()[0] if str(text) else ""
    return line[:220]


def _turn_calls(result) -> tuple[Any, list[dict]]:
    """The turn's tool calls: structured, or parsed out of its text markup.

    Returns the (possibly rewritten) turn plus its calls, in the shape the
    dispatch loop reads. When only text markup carries the calls, the turn is
    replaced by a well-formed function-call message: a strict backend rejects a
    ToolMessage that follows an assistant turn without a matching tool_call, and
    dropping the markup also stops the model re-reading its own markup in the
    history as a format to imitate.
    """
    calls = [
        tc for tc in (getattr(result, "tool_calls", None) or [])
        if isinstance(tc, dict) and tc.get("name")
    ]
    if calls:
        return result, calls
    parsed = parse_text_tool_calls(getattr(result, "content", result))
    if not parsed:
        return result, []
    return AIMessage(content="", tool_calls=parsed), parsed


def _final_prose(llm, messages, text, *, backup_llm=None) -> str:
    """Never hand tool-call markup to a caller as prose.

    Text that reached here was neither executed as a call nor an answer. Ask
    once more for the prose, WITHOUT tools, because the model already holds
    every tool result it asked for; if it answers with markup again, strip the
    markup and keep whatever prose was left, and only then say explicitly that
    no verification could be produced. Measured failure this guards (NFLX
    2026-09-15 15:22, NVDA 2026-09-15 22:32): the raw block was written into
    ``3_trading/trader.md`` under the "**Computed verification (deterministic
    tools):**" heading while no tool had run.
    """
    if not has_tool_call_markup(text):
        return text
    for chain in (llm, backup_llm):
        if chain is None:
            continue
        try:
            response = chain.invoke(
                [
                    *messages,
                    HumanMessage(
                        content=(
                            "Answer in prose now, using the tool results already "
                            "in this conversation. Do not write tool-call markup."
                        )
                    ),
                ]
            )
        except Exception as exc:  # noqa: BLE001 - degrade, never raise mid-loop
            logger.warning("prose retry after tool-call markup failed: %s", exc)
            continue
        out = content_to_text(getattr(response, "content", response))
        if out.strip() and not has_tool_call_markup(out):
            return out
    stripped = strip_tool_call_markup(text)
    if stripped and any(ch.isdigit() for ch in stripped):
        return stripped
    return MARKUP_UNAVAILABLE


def run_tool_loop(
    llm,
    prompt_text: str,
    tools,
    *,
    system_text: str | None = None,
    max_rounds: int | None = None,
    backup_llm: Any | None = None,
) -> tuple[str, list[str]]:
    """Run a tool-calling loop inside the calling node.

    Args:
        llm: the plain (unstructured) LLM; the loop binds ``tools`` to it.
        prompt_text: the node's user prompt (role + data + computed context).
        tools: list of LangChain ``@tool`` objects to bind.
        system_text: optional system directive; a default risk-analyst
            directive is used when omitted.
        max_rounds: tool-call rounds allowed; defaults to
            ``conditional_logic.MAX_TOOL_ROUNDS``.
        backup_llm: optional backup model; the cap-forced terminal turn's
            truncation continuation runs on it (see
            ``structured.finalize_messages``).

    Returns:
        ``(final_prose, transcript)`` — the model's last non-tool-calling
        answer (or the cap-forced terminal prose), plus a compact list of
        ``tool(args) -> first-line`` strings for debugging.
    """
    _build_lists()
    rounds = int(max_rounds or MAX_TOOL_ROUNDS)
    sys = (system_text or (
        "You are a risk analyst. Ground every number you cite: call the "
        "available tools before asserting a VaR/CVaR, stop, position-size, "
        "liquidity, tail, credit or tranche figure. Never invent a computed "
        "value; if a tool returns 'unavailable', say so explicitly."
    )) + _NO_MARKUP_INSTRUCTION + _LEVEL_BASIS_INSTRUCTION
    messages = [SystemMessage(content=sys), HumanMessage(content=prompt_text)]
    executor = ToolExecutor(tools)
    try:
        chain = llm.bind_tools(tools)
    except Exception:  # noqa: BLE001 - a provider without tool binding degrades
        # to a plain invocation (the analysts already assume tool support, but
        # a weak/legacy provider here must never break the decision chain).
        fallback_prompt = [HumanMessage(content=prompt_text)]
        result = llm.invoke(prompt_text)
        return _final_prose(
            llm, fallback_prompt, content_to_text(getattr(result, "content", result))
        ), []
    transcript: list[str] = []

    result = chain.invoke(messages)
    result, pending = _turn_calls(result)
    while pending and len(transcript) < rounds:
        messages.append(result)
        for tc in pending:
            name = (tc or {}).get("name") or ""
            args = (tc or {}).get("args") or {}
            content = executor.run(name, args)
            transcript.append(f"{name}({_fmt_args(args)}) -> {_first_line(content)}")
            messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=(tc or {}).get("id") or "",
                    name=name,
                )
            )
        result = chain.invoke(messages)
        result, pending = _turn_calls(result)

    if pending:
        # Cap hit: force the terminal prose turn (dangling tool_calls
        # stripped, one final LLM call) so the loop always terminates.
        from tradingagents.agents.utils.structured import finalize_messages

        backup_chain = None
        if backup_llm is not None and backup_llm is not llm:
            try:
                backup_chain = backup_llm.bind_tools(tools)
            except Exception:  # noqa: BLE001 - provider without tool binding
                backup_chain = None
        # Tool-less twins: the cap-forced terminal turn runs on these, because a
        # relay that ignores tool_choice="none" can answer the forced turn with
        # another tool call and an empty content (2026-09-11).
        text = finalize_messages(
            chain, messages, result, backup_chain=backup_chain,
            agent_name="Risk Debators",
            plain_chain=llm,
            backup_plain_chain=(backup_llm if backup_llm is not llm else None),
        )
    else:
        text = content_to_text(getattr(result, "content", result))
    # A markup turn can also be what the cap-forced terminal turn produced; the
    # guard runs on both exits, because the caller must never write a claim of a
    # deterministic check that produced no prose.
    text = _final_prose(llm, messages, text, backup_llm=backup_llm)
    return str(text or ""), transcript
