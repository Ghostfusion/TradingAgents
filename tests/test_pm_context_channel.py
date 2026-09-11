"""W4 — the Portfolio Manager prompt renders the hoisted pre-decision inputs.

The PM is ``NO_EXTERNAL_TOOLS``: the context channel is its only source, so a
rule may not reference a number the rendered prompt does not contain. This
test builds the PM prompt from a fixture state (free-text LLM stub; no
network, no real LLM) and asserts the hoisted liquidity verdict, book
drawdown and drawdown limit reach the prompt text - and that the rules that
were rewritten now cite the pre-decision limits instead of the post-decision
position contract the PM never sees.
"""

from __future__ import annotations

import tradingagents.agents.managers.portfolio_manager as pm_mod


class _CaptureLLM:
    """Free-text stub: records every prompt, returns a usable decision.

    No ``with_structured_output`` attribute, so the agent takes its documented
    free-text path (``bind_structured`` degrades to ``None``).
    """

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, prompt, *a, **k):
        self.prompts.append(prompt)

        class _Response:
            content = (
                "**Rating**: Hold\n\n"
                "Sizing stays inside the computed pre-decision limits; no new risk "
                "is added while the book drawdown sits over its limit."
            )

        return _Response()


def _state(**risk_context) -> dict:
    default_ctx = {
        "book_drawdown": 0.042,
        "drawdown_limit": 0.10,
        "max_position_pct": 0.30,
        "cvar_budget_pct": 0.03,
        "liquidity": {
            "verdict": "illiquid",
            "illiq": 2.5e-7,
            "float_turnover": 0.004,
            "iwf": 0.42,
            "dangers": ["float-turnover=0.400% below 0.50%"],
        },
    }
    default_ctx.update(risk_context)
    return {
        "company_of_interest": "NVDA",
        "instrument_context": "NVDA (stock)",
        "investment_plan": "research plan",
        "trader_investment_plan": "trader proposal",
        "computed_independent_vote": "",
        "computed_decision_context": "Computed decision context (stub)",
        "risk_context": default_ctx,
        "risk_debate_state": {
            "history": "debate history",
            "aggressive_history": ["Aggressive: Buy"],
            "conservative_history": ["Conservative: Hold"],
            "neutral_history": ["Neutral: Hold"],
            "current_aggressive_response": "aggressive",
            "current_conservative_response": "conservative",
            "current_neutral_response": "neutral",
            "count": 1,
            "latest_speaker": "Neutral",
        },
    }


def test_pm_prompt_renders_liquidity_drawdown_and_limit():
    llm = _CaptureLLM()
    node = pm_mod.create_portfolio_manager(llm)
    out = node(_state())
    prompt = llm.prompts[-1]

    assert "verdict=ILLIQUID" in prompt
    assert "book drawdown 4.20% vs limit 10.00%" in prompt
    assert "per-trade size cap 30.0%" in prompt
    assert "daily CVaR budget 3.00%" in prompt
    assert out["final_trade_decision"]


def test_pm_rules_cite_pre_graph_limits_not_the_contract():
    llm = _CaptureLLM()
    node = pm_mod.create_portfolio_manager(llm)
    node(_state())
    prompt = llm.prompts[-1]

    # The rewritten rules reference the hoisted limits/stop read...
    assert "pre-decision limits" in prompt
    assert "trade-plan card's unified stop" in prompt
    # ...and no longer point at the post-decision contract.
    assert "computed Position contract" not in prompt


def test_pm_prompt_reports_over_limit_drawdown_as_veto():
    llm = _CaptureLLM()
    node = pm_mod.create_portfolio_manager(llm)
    node(_state(book_drawdown=0.18, drawdown_limit=0.10))
    prompt = llm.prompts[-1]

    assert "book drawdown 18.00% vs limit 10.00% (OVER LIMIT - new risk blocked)" in prompt

    llm2 = _CaptureLLM()
    pm_mod.create_portfolio_manager(llm2)(_state())
    assert "(within limit)" in llm2.prompts[-1]


def test_pm_prompt_omits_limits_line_when_context_absent():
    llm = _CaptureLLM()
    node = pm_mod.create_portfolio_manager(llm)
    state = _state()
    state.pop("risk_context")
    node(state)
    prompt = llm.prompts[-1]

    assert "Computed pre-decision limits" not in prompt
