"""Every report-producing agent must apply the configured output language
(#740/#801) and the per-role output budget.

A non-English run should produce a fully localized report, not a mix of
languages. The bug originally happened because several agents silently omitted
the instruction (fixed in 6b384f7); this test codifies the invariant so a future
refactor can't quietly drop it again.

The invariant is asserted where it is observable: the rendered prompt the agent
hands to its LLM must carry both directives.
"""
import importlib

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.agents.utils.agent_utils import (
    get_language_instruction,
    get_output_budget,
)
from tradingagents.dataflows.config import reset_config, set_config

# Every node whose text reaches the saved report: (module path, factory,
# per-role output-budget section). If you add a report-producing agent, add it
# here — and make its prompt carry get_language_instruction()/get_output_budget().
REPORT_AGENTS = [
    ("analysts/market_analyst.py", "create_market_analyst", "analyst"),
    ("analysts/news_analyst.py", "create_news_analyst", "analyst"),
    ("analysts/fundamentals_analyst.py", "create_fundamentals_analyst", "analyst"),
    ("analysts/sentiment_analyst.py", "create_sentiment_analyst", "analyst"),
    ("researchers/bull_researcher.py", "create_bull_researcher", "debater"),
    ("researchers/bear_researcher.py", "create_bear_researcher", "debater"),
    ("managers/research_manager.py", "create_research_manager", "research"),
    ("managers/portfolio_manager.py", "create_portfolio_manager", "portfolio"),
    ("risk_mgmt/aggressive_debator.py", "create_aggressive_debator", "debater"),
    ("risk_mgmt/conservative_debator.py", "create_conservative_debator", "debater"),
    ("risk_mgmt/neutral_debator.py", "create_neutral_debator", "debater"),
    ("trader/trader.py", "create_trader", "trader"),
]


def _agent_state() -> dict:
    """Minimal state every report-producing node can render a prompt from."""
    return {
        "company_of_interest": "NVDA",
        "company_name": "NVIDIA",
        "asset_type": "stock",
        "instrument_context": "NVDA (NVIDIA Corp)",
        "trade_date": "2026-09-10",
        "messages": [HumanMessage(content="NVDA")],
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "past_context": "",
        "computed_decision_context": "",
        "investment_plan": "investment plan",
        "trader_investment_plan": "trader plan",
        "investment_debate_state": {
            "bull_history": "bull case",
            "bear_history": "bear case",
            "history": "debate history",
            "current_response": "current response",
            "judge_decision": "",
            "count": 1,
        },
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive case",
            "conservative_history": "conservative case",
            "neutral_history": "neutral case",
            "latest_speaker": "Aggressive",
            "current_aggressive_response": "aggressive case",
            "current_conservative_response": "conservative case",
            "current_neutral_response": "neutral case",
            "count": 1,
            "judge_decision": "",
        },
        "researcher_independent_stances": {},
        "debate_state": {},
        "structured_risk_state": {},
        "risk_context": {},
    }


def _render_prompt(prompt) -> str:
    """Flatten whatever the agent handed its LLM into one searchable string."""
    if isinstance(prompt, str):
        return prompt
    messages = getattr(prompt, "messages", None)
    if messages is None and isinstance(prompt, (list, tuple)):
        messages = list(prompt)
    if messages is None:
        return str(prompt)
    parts = []
    for message in messages:
        if isinstance(message, dict):
            parts.append(str(message.get("content", "")))
        else:
            parts.append(str(getattr(message, "content", message)))
    return "\n".join(parts)


def _stub_llm():
    """Runnable stub that records every prompt it is invoked with."""
    prompts: list = []

    def _call(prompt):
        prompts.append(prompt)
        return AIMessage(
            content="stub report body long enough to look like a real report.",
            tool_calls=[],
        )

    class _Stub(RunnableLambda):
        def bind_tools(self, tools=None, **kwargs):
            return self

    return _Stub(_call), prompts


def _agent_prompts(rel: str, factory: str, monkeypatch) -> list:
    module = importlib.import_module(
        "tradingagents.agents." + rel[:-3].replace("/", ".")
    )
    if rel.endswith("sentiment_analyst.py"):
        # The sentiment analyst pre-fetches its sources before building the
        # prompt; stub the vendors and the deterministic compute so the test
        # stays offline (the rendered prompt is what is under test).
        class _News:
            def func(self, *a, **k):
                return "<news unavailable>"

        monkeypatch.setattr(module, "get_news", _News())
        monkeypatch.setattr(
            module, "fetch_stocktwits_messages", lambda *a, **k: "<stocktwits unavailable>"
        )
        monkeypatch.setattr(
            module, "fetch_reddit_posts", lambda *a, **k: "<reddit unavailable>"
        )
        set_config({"enable_sentiment": False})

    llm, prompts = _stub_llm()
    getattr(module, factory)(llm)(_agent_state())
    return prompts


@pytest.fixture()
def _non_english_output():
    set_config({"output_language": "中文"})
    yield
    reset_config()


@pytest.mark.unit
class TestLanguageInstruction:
    def test_english_adds_no_tokens(self, monkeypatch):
        from tradingagents.dataflows.config import set_config
        set_config({"output_language": "English"})
        assert get_language_instruction() == ""

    def test_non_english_emits_directive(self):
        from tradingagents.dataflows.config import set_config
        set_config({"output_language": "中文"})
        out = get_language_instruction()
        assert "中文" in out
        assert "entire response" in out


@pytest.mark.unit
@pytest.mark.parametrize(
    "rel,factory,role", REPORT_AGENTS, ids=[row[0] for row in REPORT_AGENTS]
)
def test_report_agent_prompt_carries_language_and_budget(
    rel, factory, role, monkeypatch, _non_english_output
):
    prompts = _agent_prompts(rel, factory, monkeypatch)
    assert prompts, f"{rel} never rendered a prompt"
    rendered = "\n".join(_render_prompt(p) for p in prompts)

    language = get_language_instruction()
    assert language and language in rendered, (
        f"{rel} prompt omits the output-language directive; its report would "
        f"ignore the configured output_language (#740/#801)."
    )

    budget = get_output_budget(role)
    assert budget and budget in rendered, (
        f"{rel} prompt omits the per-role output budget; its report could "
        f"exceed the configured per-role max_tokens cap."
    )
