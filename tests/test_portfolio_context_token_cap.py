"""Portfolio three-state honesty, checkpoint book fingerprint, output-token cap.

(a) A book at the analysis date has THREE distinct states - a position, a
genuinely flat book, and NO context - and the PM must never render "not
provided" as "flat" (upstream ``portfolio.py``).
(b) A checkpoint started against one book must not silently resume against a
different one; the book digest is stable for an identical book.
(c) One output-token cap is translated to each provider's own request field
(Gemini ``max_output_tokens``, others ``max_tokens``) and omitted when unset.
"""

import copy
from typing import TypedDict
from unittest import mock

import pytest
from langgraph.graph import END, START, StateGraph

pytestmark = pytest.mark.timeout(600)


# ---------------------------------------------------------------------------
# (a) three-state honesty
# ---------------------------------------------------------------------------


def test_no_context_is_not_a_flat_book():
    from tradingagents.agents.utils.portfolio_context import (
        NO_CONTEXT_LINE,
        render_portfolio_context,
    )

    rendered = render_portfolio_context(None, "AAPL")
    assert rendered == NO_CONTEXT_LINE
    assert "none supplied" in rendered
    assert "says nothing about the account" in rendered
    # It must NOT make the flat-book claim for the analyzed name.
    assert "No current position" not in rendered


def test_genuinely_flat_book_renders_as_flat():
    from tradingagents.agents.utils.portfolio_context import (
        NO_CONTEXT_LINE,
        render_portfolio_context,
    )

    # A supplied-but-empty book is a real flat book; it is rendered as such,
    # never as the no-context refusal.
    rendered = render_portfolio_context({"positions": [], "cash": 1.0}, "AAPL")
    assert "No current position in AAPL" in rendered
    assert rendered != NO_CONTEXT_LINE
    assert "none supplied" not in rendered
    assert "says nothing about the account" not in rendered


def test_book_without_the_name_is_flat_for_that_name_but_has_others():
    from tradingagents.agents.utils.portfolio_context import render_portfolio_context

    rendered = render_portfolio_context(
        {"positions": [{"ticker": "SPY", "weight": 0.5}], "cash": 0.5}, "AAPL"
    )
    assert "No current position in AAPL" in rendered  # genuinely not held
    assert "SPY" in rendered  # the book itself is known
    assert "none supplied" not in rendered


def test_book_with_the_name_renders_the_position():
    from tradingagents.agents.utils.portfolio_context import render_portfolio_context

    rendered = render_portfolio_context(
        {"positions": [{"ticker": "AAPL", "weight": 0.25}], "cash": 0.75}, "aapl"
    )
    assert "Current position in AAPL" in rendered
    assert "25.0% of book" in rendered
    assert "No current position" not in rendered


def _pm_prompt(state: dict) -> str:
    """Run the Portfolio Manager node and return the rendered prompt text."""
    from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    structured = mock.MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt)
        or PortfolioDecision(rating=PortfolioRating.HOLD, executive_summary="x", investment_thesis="y")
    )
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = structured
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
        **state,
    })
    prompt = captured["prompt"]
    if isinstance(prompt, str):
        return prompt
    return "\n".join(
        m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "") for m in prompt
    )


def test_pm_no_context_does_not_claim_flat(monkeypatch):
    from tradingagents.agents.utils.portfolio_context import NO_CONTEXT_LINE

    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: {})
    text = _pm_prompt({})
    assert NO_CONTEXT_LINE in text
    assert "No current position in NVDA" not in text


def test_pm_flat_book_is_rendered_flat(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: {})
    text = _pm_prompt({"portfolio_context": {"positions": [], "cash": 1.0}})
    assert "No current position in NVDA" in text
    assert "none supplied" not in text


def test_pm_position_is_rendered(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: {})
    text = _pm_prompt({"portfolio_context": {"positions": [{"ticker": "NVDA", "weight": 0.1}], "cash": 0.9}})
    assert "Current position in NVDA" in text


def test_agent_state_declares_portfolio_context():
    """The state channel must be declared or native LangGraph drops it."""
    from tradingagents.agents.utils.agent_states import AgentState

    assert "portfolio_context" in AgentState.__annotations__


def test_build_context_from_config():
    from tradingagents.agents.utils.portfolio_context import (
        build_portfolio_context,
        render_portfolio_context,
    )

    assert build_portfolio_context({}) is None
    assert build_portfolio_context(None) is None
    assert build_portfolio_context({"risk_basket_tickers": []}) is None

    ctx = build_portfolio_context(
        {"risk_basket_tickers": ["SPY", "QQQ"], "risk_basket_weights": {"SPY": 0.4, "QQQ": 0.4}}
    )
    assert ctx is not None
    rendered = render_portfolio_context(ctx, "SPY")
    assert "Current position in SPY" in rendered
    # Weights sum below 1.0 -> cash is the residual.
    assert abs(ctx["cash"] - 0.2) < 1e-9


# ---------------------------------------------------------------------------
# (b) checkpoint book fingerprint
# ---------------------------------------------------------------------------

_BOOK_A = {"positions": [{"ticker": "AAPL", "quantity": 10, "average_price": 180.0}], "cash": 500.0}
_BOOK_A_REORDERED = {
    "cash": 500.0,
    "positions": [{"average_price": 180.0, "quantity": 10, "ticker": "AAPL"}],
}
_BOOK_B = {"positions": [{"ticker": "AAPL", "quantity": 20, "average_price": 180.0}], "cash": 500.0}


def test_fingerprint_stable_and_order_insensitive():
    from tradingagents.graph.checkpointer import book_fingerprint

    assert book_fingerprint(_BOOK_A) == book_fingerprint(copy.deepcopy(_BOOK_A))
    assert book_fingerprint(_BOOK_A) == book_fingerprint(_BOOK_A_REORDERED)


def test_fingerprint_changes_with_the_book():
    from tradingagents.graph.checkpointer import book_fingerprint

    assert book_fingerprint(_BOOK_A) != book_fingerprint(_BOOK_B)
    # No context is distinct from a supplied (even empty) book.
    assert book_fingerprint(None) == ""
    assert book_fingerprint({}) == ""
    assert book_fingerprint({"positions": []}) != ""


def test_resume_book_conflict_detects_a_changed_book(tmp_path):
    from tradingagents.graph.checkpointer import resolve_run_id, resume_book_conflict

    resolve_run_id(tmp_path, "AAPL", "2026-04-20", "sig", portfolio_context=_BOOK_A)
    assert resume_book_conflict(tmp_path, "AAPL", "2026-04-20", "sig", _BOOK_A) is None
    message = resume_book_conflict(tmp_path, "AAPL", "2026-04-20", "sig", _BOOK_B)
    assert message is not None
    assert "fingerprint mismatch" in message


class _CountState(TypedDict):
    count: int


def _step(state: _CountState) -> dict:
    return {"count": state["count"] + 1}


def _tiny_graph():
    builder = StateGraph(_CountState)
    builder.add_node("step", _step)
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    return builder


def test_changed_book_does_not_silently_resume(tmp_path):
    from tradingagents.graph.checkpointer import (
        get_checkpointer,
        resolve_run_id,
        thread_id,
    )

    sig = "analysts=market|asset=stock"
    run_a = resolve_run_id(tmp_path, "AAPL", "2026-04-20", sig, portfolio_context=_BOOK_A)

    # Write a real checkpoint under run A's thread so there is something to resume.
    tid = thread_id("AAPL", "2026-04-20", sig, run_a)
    with get_checkpointer(tmp_path, "AAPL") as saver:
        _tiny_graph().compile(checkpointer=saver).invoke(
            {"count": 0}, config={"configurable": {"thread_id": tid}}
        )

    # Same book -> resumes the SAME run id.
    assert resolve_run_id(tmp_path, "AAPL", "2026-04-20", sig, portfolio_context=_BOOK_A) == run_a
    # Changed book -> a fresh run id (the stale checkpoint is NOT resumed).
    assert resolve_run_id(tmp_path, "AAPL", "2026-04-20", sig, portfolio_context=_BOOK_B) != run_a


def test_legacy_marker_without_fingerprint_does_not_conflict(tmp_path):
    """A checkpoint written before fingerprints existed must still resume."""
    from tradingagents.graph.checkpointer import resolve_run_id, resume_book_conflict

    resolve_run_id(tmp_path, "AAPL", "2026-04-20", "sig", portfolio_context=_BOOK_A)
    # Simulate a legacy run: remove the fingerprint sidecar.
    cp_dir = tmp_path / "checkpoints"
    for sidecar in cp_dir.glob("*.book"):
        sidecar.unlink()
    assert resume_book_conflict(tmp_path, "AAPL", "2026-04-20", "sig", _BOOK_B) is None


# ---------------------------------------------------------------------------
# (c) output-token cap translation
# ---------------------------------------------------------------------------


def _bare_base_client(**kwargs):
    from tradingagents.llm_clients.base_client import BaseLLMClient

    class _Client(BaseLLMClient):
        def get_llm(self):
            return None

        def validate_model(self):
            return True

    return _Client("model-x", **kwargs)


def test_output_token_param_names():
    from tradingagents.llm_clients.base_client import output_token_param

    assert output_token_param("google") == "max_output_tokens"
    assert output_token_param("anthropic") == "max_tokens"
    assert output_token_param("openai") == "max_tokens"
    assert output_token_param(None) == "max_tokens"


def test_token_cap_omitted_when_unset():
    client = _bare_base_client()
    assert client.output_token_kwargs() == {}


def test_token_cap_uses_default_param_name():
    client = _bare_base_client(max_tokens=4096)
    assert client.output_token_kwargs() == {"max_tokens": 4096}


def test_gemini_cap_is_max_output_tokens():
    import tradingagents.llm_clients.google_client as mod

    captured = {}
    with mock.patch.object(mod, "NormalizedChatGoogleGenerativeAI", lambda **kw: captured.update(kw)):
        mod.GoogleClient("gemini-3.5-flash", api_key="x", max_tokens=1234).get_llm()
    assert captured["max_output_tokens"] == 1234
    assert "max_tokens" not in captured


def test_gemini_cap_omitted_when_unset():
    import tradingagents.llm_clients.google_client as mod

    captured = {}
    with mock.patch.object(mod, "NormalizedChatGoogleGenerativeAI", lambda **kw: captured.update(kw)):
        mod.GoogleClient("gemini-3.5-flash", api_key="x").get_llm()
    assert "max_output_tokens" not in captured
    assert "max_tokens" not in captured


def test_anthropic_cap_is_max_tokens():
    import tradingagents.llm_clients.anthropic_client as mod

    captured = {}
    with mock.patch.object(mod, "NormalizedChatAnthropic", lambda **kw: captured.update(kw)):
        mod.AnthropicClient("claude-mythos-preview", api_key="x", max_tokens=2048).get_llm()
    assert captured["max_tokens"] == 2048


def test_anthropic_cap_omitted_when_unset():
    import tradingagents.llm_clients.anthropic_client as mod

    captured = {}
    with mock.patch.object(mod, "NormalizedChatAnthropic", lambda **kw: captured.update(kw)):
        mod.AnthropicClient("claude-mythos-preview", api_key="x").get_llm()
    assert "max_tokens" not in captured


def test_openai_compatible_cap_is_max_tokens(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    from tradingagents.llm_clients.openai_client import OpenAIClient

    llm = OpenAIClient("deepseek/deepseek-v4-flash-0731", provider="openrouter", max_tokens=6000).get_llm()
    assert getattr(llm, "max_tokens", None) == 6000


def test_openai_compatible_cap_omitted_when_unset(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    from tradingagents.llm_clients.openai_client import OpenAIClient

    llm = OpenAIClient("deepseek/deepseek-v4-flash-0731", provider="openrouter").get_llm()
    assert getattr(llm, "max_tokens", None) is None
