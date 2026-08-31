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
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from tradingagents.graph.conditional_logic import MAX_TOOL_ROUNDS

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
        get_credit_spread_read,
        get_downside_read,
        get_exit_check,
        get_exit_overrides,
        get_fixed_risk_size,
        get_garch_volatility,
        get_horizon_var,
        get_ledger_risk_state,
        get_mean_reversion_quality,
        get_position_sizing,
        get_pre_trade_read,
        get_premarket_review,
        get_regime_gate_read,
        get_risk_gate,
        get_tail_decomposition,
        get_tail_risk,
        get_trade_plan,
        get_trailing_exit,
        get_vol_cones,
        get_volatility_estimators,
    )
    from tradingagents.agents.utils.market_position_tools import get_liquidity_risk
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
        get_horizon_var,
        get_downside_read,
        get_credit_spread_read,
        get_volatility_estimators,
        get_garch_volatility,
        get_mean_reversion_quality,
        get_tranche_plan,
        get_position_sizing,
        get_fixed_risk_size,
        get_exit_check,
        get_trailing_exit,
        get_liquidity_risk,
        get_premarket_review,
        get_ledger_risk_state,
        get_exit_overrides,
        get_pre_trade_read,
        get_vol_cones,
        get_regime_gate_read,
        get_trade_plan,
    ])

    from tradingagents.agents.utils.analysis_tools import (
        get_exit_plan,
        get_scaleout_plan,
        get_swing_exits,
        get_swing_set,
    )

    TRADER_TOOLS.extend([
        get_position_sizing,
        get_risk_gate,
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


def run_tool_loop(
    llm,
    prompt_text: str,
    tools,
    *,
    system_text: str | None = None,
    max_rounds: int | None = None,
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

    Returns:
        ``(final_prose, transcript)`` — the model's last non-tool-calling
        answer (or the cap-forced terminal prose), plus a compact list of
        ``tool(args) -> first-line`` strings for callers that want to carry
        the findings into a structured invocation.
    """
    _build_lists()
    rounds = int(max_rounds or MAX_TOOL_ROUNDS)
    sys = system_text or (
        "You are a risk analyst. Ground every number you cite: call the "
        "available tools before asserting a VaR/CVaR, stop, position-size, "
        "liquidity, tail, credit or tranche figure. Never invent a computed "
        "value; if a tool returns 'unavailable', say so explicitly."
    )
    messages = [SystemMessage(content=sys), HumanMessage(content=prompt_text)]
    executor = ToolExecutor(tools)
    try:
        chain = llm.bind_tools(tools)
    except Exception:  # noqa: BLE001 - a provider without tool binding degrades
        # to a plain invocation (the analysts already assume tool support, but
        # a weak/legacy provider here must never break the decision chain).
        result = llm.invoke(prompt_text)
        text = result.content if hasattr(result, "content") else str(result)
        return str(text or ""), []
    transcript: list[str] = []

    result = chain.invoke(messages)
    pending = result.tool_calls if isinstance(result.tool_calls, list) else []
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
        pending = result.tool_calls if isinstance(result.tool_calls, list) else []

    if pending:
        # Cap hit: force the terminal prose turn (dangling tool_calls
        # stripped, one final LLM call) so the loop always terminates.
        from tradingagents.agents.utils.structured import finalize_messages

        text = finalize_messages(chain, messages, result)
    else:
        text = result.content if hasattr(result, "content") else str(result)
    return str(text or ""), transcript
