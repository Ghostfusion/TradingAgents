"""Agents on the schema-only structured-output path must not invite tool calls (#1130).

`with_structured_output` binds exactly one tool (the schema). A prompt that
primes tool use makes models emit an unknown `web_search` call, which discards
the structured attempt and forces a free-text retry — an extra LLM round trip
and the loss of typed output.

These assert the constraint reaches the *rendered* prompt each agent actually
sends, not merely that the constant is referenced in the module.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

import tradingagents.agents.analysts.sentiment_analyst as sentiment
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.structured import NO_EXTERNAL_TOOLS


def _capturing_llm(captured: dict, result):
    """LLM whose structured binding records the prompt it was handed."""
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or result
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _prompt_text(prompt) -> str:
    """Flatten a captured prompt (str, message list, or objects) to text."""
    if isinstance(prompt, str):
        return prompt
    parts = []
    for m in prompt:
        parts.append(m.get("content", "") if isinstance(m, dict) else getattr(m, "content", ""))
    return "\n".join(str(p) for p in parts)


@pytest.mark.unit
def test_trader_prompt_injects_computed_decision_context():
    from tradingagents.agents.schemas import TraderAction, TraderProposal

    captured = {}
    llm = _capturing_llm(captured, TraderProposal(action=TraderAction.BUY, reasoning="x"))
    create_trader(llm)({
        "company_of_interest": "NVDA",
        "investment_plan": "**Recommendation**: Buy",
        "computed_decision_context": (
            "Computed regime gate (mean-reversion entry): verdict=clean pass=True\n\n"
            "### Trade plan card: NVDA\n- Reference price: 200.0\n"
        ),
    })
    text = _prompt_text(captured["prompt"])
    assert "Computed decision context" in text
    assert "Trade plan card: NVDA" in text
    assert "verdict=clean" in text


@pytest.mark.unit
def test_portfolio_manager_prompt_injects_computed_decision_context():
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD, executive_summary="x", investment_thesis="y"
        ),
    )
    risk = {
        "history": "h", "aggressive_history": "a", "conservative_history": "c",
        "neutral_history": "n", "current_aggressive_response": "",
        "current_conservative_response": "", "current_neutral_response": "",
        "latest_speaker": "Neutral", "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
        "computed_decision_context": "### Trade plan card: NVDA\n- Reference price: 200.0\n",
    })
    text = _prompt_text(captured["prompt"])
    assert "Computed decision context" in text
    assert "Trade plan card: NVDA" in text




@pytest.mark.unit
def test_research_manager_prompt_injects_independent_researcher_reads():
    """Option-A: when independent pre-debate researcher stances exist, the RM
    sees them (uncontaminated bull/bear reads) alongside the debate history."""
    from tradingagents.agents.schemas import PortfolioRating, ResearchPlan

    captured = {}
    llm = _capturing_llm(
        captured,
        ResearchPlan(
            recommendation=PortfolioRating.BUY, rationale="x", strategic_actions="y"
        ),
    )
    create_research_manager(llm)({
        "company_of_interest": "NVDA",
        "investment_debate_state": {
            "history": "h", "bull_history": "b", "bear_history": "r",
            "current_response": "", "judge_decision": "", "count": 1,
        },
        "researcher_independent_stances": {
            "bull": {"rating": "Buy", "strength": 70, "reason": "moat intact"},
            "bear": {"rating": "Sell", "strength": 60, "reason": "peak margin"},
        },
    })
    text = _prompt_text(captured["prompt"])
    assert "Independent pre-debate researcher reads" in text
    assert "**Bull** (independent, pre-debate): Buy (strength 70/100)" in text
    assert ".**Bear**" in text or "**Bear**" in text




@pytest.mark.unit
def test_portfolio_manager_uses_independent_vote_when_present():
    """Option-A: when the graph produced the independent pre-debate vote, the PM
    prompt must use it (not the legacy parse-from-history consensus line)."""
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
        ),
    )
    risk = {
        "history": "h", "aggressive_history": "a", "conservative_history": "c",
        "neutral_history": "n", "current_aggressive_response": "",
        "current_conservative_response": "", "current_neutral_response": "",
        "latest_speaker": "Neutral", "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
        "computed_independent_vote": (
            "**Independent pre-debate risk stances** (sampled before any cross-talk):\n"
            "- **Aggressive**: Buy\n"
            "**Independent agreement**: agreement=0.50 label=low (n=3)"
        ),
    })
    text = _prompt_text(captured["prompt"])
    assert "**Independent pre-debate risk stances**" in text
    assert "agreement=0.50 label=low" in text
    # The legacy parse-from-history line must NOT appear when the independent vote is present.
    assert "Computed risk-consensus** (deterministic): agreement=" not in text


@pytest.mark.unit
def test_portfolio_manager_falls_back_to_legacy_consensus_without_independent_vote():
    """When the independent vote is absent (flag off / sampling failure), the PM
    still gets the legacy parse-from-history consensus line — no silent gap."""
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
        ),
    )
    risk = {
        "history": "h",
        "aggressive_history": "Aggressive Analyst: Rating Buy, high risk.",
        "conservative_history": "Conservative Analyst: Rating Sell.",
        "neutral_history": "Neutral Analyst: Rating Hold.",
        "current_aggressive_response": "",
        "current_conservative_response": "",
        "current_neutral_response": "",
        "latest_speaker": "Neutral",
        "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
    })
    text = _prompt_text(captured["prompt"])
    assert "**Computed risk-consensus**" in text
    assert "agreement=" in text


@pytest.mark.unit
def test_portfolio_manager_prompt_injects_computed_cvar():
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
        ),
    )
    risk = {
        "history": "h", "aggressive_history": "a", "conservative_history": "c",
        "neutral_history": "n", "current_aggressive_response": "",
        "current_conservative_response": "", "current_neutral_response": "",
        "latest_speaker": "Neutral", "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
        # Computed risk context is injected by the graph post-overlay.
        "risk_context": {"single_cvar": 0.0123, "book_cvar": 0.0325},
    })
    text = _prompt_text(captured["prompt"])
    assert "Computed daily-tail CVaR" in text
    assert "analyzed-name daily CVaR 1.23%" in text
    assert "portfolio (book) daily CVaR 3.25%" in text
    assert "portfolio (book) daily CVaR 3.25% — fed the gate" in text


@pytest.mark.unit
def test_portfolio_manager_prompt_no_cvar_context_omits_line():
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
        ),
    )
    risk = {
        "history": "h", "aggressive_history": "a", "conservative_history": "c",
        "neutral_history": "n", "current_aggressive_response": "",
        "current_conservative_response": "", "current_neutral_response": "",
        "latest_speaker": "Neutral", "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
    })
    assert "Computed daily-tail CVaR" not in _prompt_text(captured["prompt"])


@pytest.mark.unit
def test_sentiment_prompt_states_constraint(monkeypatch):
    from tradingagents.agents.schemas import SentimentBand, SentimentReport

    # Pre-fetched sources are stubbed so the prompt builds without network I/O.
    monkeypatch.setattr(sentiment, "fetch_stocktwits_messages", lambda *a, **k: "st")
    monkeypatch.setattr(sentiment, "fetch_reddit_posts", lambda *a, **k: "rd")
    monkeypatch.setattr(sentiment.get_news, "func", lambda *a, **k: "news", raising=False)

    captured = {}
    llm = _capturing_llm(captured, SentimentReport(
        overall_band=SentimentBand.BULLISH, overall_score=7.5,
        confidence="high", narrative="n",
    ))
    sentiment.create_sentiment_analyst(llm)({
        "company_of_interest": "NVDA", "trade_date": "2026-01-15",
        "asset_type": "stock", "messages": [],
    })
    text = _prompt_text(captured["prompt"])
    assert NO_EXTERNAL_TOOLS in text
    # This agent binds no tools, so tool-range wording must not reappear.
    assert "tool-call date ranges" not in text


@pytest.mark.unit
def test_tool_using_analysts_keep_their_date_guidance():
    # The analysts that really do call tools keep the wording that anchors their
    # tool date ranges (#836) — this fix is scoped to no-tool agents.
    import tradingagents.agents.analysts.market_analyst as market
    import tradingagents.agents.analysts.news_analyst as news
    for module in (market, news):
        assert "tool-call date ranges" in inspect.getsource(module)


@pytest.mark.unit
def test_agent_state_declares_decision_context_channels():
    """The compiled advisory context must be a declared LangGraph channel.

    ``_run_graph`` seeds ``computed_decision_context`` and ``risk_context``
    onto the initial state so the Trader / PM / risk debators read them, and
    reporting appends the IVa section from ``final_state``. Native LangGraph
    drops undeclared keys (nodes never see them, and they are absent from the
    output), so these MUST be declared on ``AgentState`` or the whole
    end-to-end injection is a silent no-op (#value-dip wiring).
    """
    from tradingagents.agents.utils.agent_states import AgentState

    assert "computed_decision_context" in AgentState.__annotations__
    assert "risk_context" in AgentState.__annotations__


@pytest.mark.unit
def test_agent_state_carries_decision_context_through_graph():
    """A value seeded onto the initial state reaches a node and the output."""
    from langgraph.graph import StateGraph

    from tradingagents.agents.utils.agent_states import AgentState

    def probe(state):
        seen = state.get("computed_decision_context")
        return {
            "company_of_interest": str(state.get("company_of_interest"))
            + ":" + (seen or "NONE"),
        }

    g = StateGraph(AgentState)
    g.add_node("probe", probe)
    g.set_entry_point("probe")
    g.add_edge("probe", "__end__")
    app = g.compile()

    res = app.invoke(
        {
            "messages": [],
            "company_of_interest": "NVDA",
            "computed_decision_context": "### Trade plan card: NVDA",
            "risk_context": {"single_cvar": 0.0123},
        }
    )
    assert "### Trade plan card: NVDA" in res["company_of_interest"]
    assert res.get("computed_decision_context") == "### Trade plan card: NVDA"
    assert res.get("risk_context") == {"single_cvar": 0.0123}
