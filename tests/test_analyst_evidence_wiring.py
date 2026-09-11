"""Hermetic wiring tests: the analyst nodes reduce from forced-tool evidence.

Proves the Phase-2 contract without any network: when ``analyst_forced_tools``
is set, the analyst node's first entry gathers the fixed tool set, injects the
rendered evidence block into the system prompt, and returns ``tool_evidence``
on state; a tool-loop re-entry (same state key) does NOT re-gather.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from tradingagents.agents.analysts import (
    fundamentals_analyst as fundamentals_mod,
    market_analyst as market_mod,
    news_analyst as news_mod,
)
from tradingagents.agents import toolsets as toolsets_mod
from tradingagents.agents.utils.evidence_gather import (
    EVIDENCE_SECTION_HEADER,
    TOOL_EVIDENCE_KEY,
    format_evidence_block,
)

_FORCED_CONFIG = {
    "analyst_forced_tools": ["get_basic_financials"],
    "analyst_forced_tools_max_parallel": 1,
    "analyst_forced_tools_timeout_s": 5,
    "analyst_forced_tools_summary_window": 12000,
}


class _FakeBindable:
    """Callable stand-in for ``llm.bind_tools(tools)`` — captures the messages."""

    def __init__(self, responses, captured):
        self._responses = list(responses)
        self._captured = captured

    def __call__(self, messages):
        # The chain may hand the template output as a list OR a
        # ChatPromptValue (which carries .messages) depending on input shape.
        if hasattr(messages, "messages"):
            messages = messages.messages
        self._captured.extend(list(messages))
        text = self._responses.pop(0) if self._responses else "done"
        return AIMessage(content=text)


class _FakeLLM:
    def __init__(self, responses, captured):
        self._responses = responses
        self._captured = captured

    def bind_tools(self, tools):
        return _FakeBindable(self._responses, self._captured)


def test_analyst_node_reduces_from_evidence_once(monkeypatch):
    calls = {"n": 0}

    @tool
    def get_basic_financials(ticker: str) -> str:
        """Fake finnhub basic-financials surface (patched over the real one)."""
        calls["n"] += 1
        return f"FAKE_FIN_OK_{ticker}"

    monkeypatch.setattr(toolsets_mod, "get_basic_financials", get_basic_financials)

    captured: list = []
    node = fundamentals_mod.create_fundamentals_analyst(
        _FakeLLM(["final report"], captured), config=_FORCED_CONFIG
    )

    state = _base_state()
    out = node(state)

    # First entry gathers the forced tool and returns the evidence on state.
    assert calls["n"] == 1
    assert TOOL_EVIDENCE_KEY in out
    leaves = out[TOOL_EVIDENCE_KEY]["fundamentals"]
    assert [leaf["tool"] for leaf in leaves] == ["get_basic_financials"]
    assert leaves[0]["status"] == "ok"

    # The system prompt the model actually saw contains the evidence block.
    sys_text = "".join(
        getattr(m, "content", "") for m in captured if getattr(m, "type", "") == "system"
    )
    assert EVIDENCE_SECTION_HEADER in sys_text
    assert "FAKE_FIN_OK_TSM" in sys_text

    # The node also carries the report through unchanged.
    assert out["fundamentals_report"] == "final report"


def test_analyst_node_skips_regather_on_reentry(monkeypatch):
    calls = {"n": 0}

    @tool
    def get_basic_financials(ticker: str) -> str:
        """Fake basic-financials surface."""
        calls["n"] += 1
        return f"FAKE_FIN_OK_{ticker}"

    monkeypatch.setattr(toolsets_mod, "get_basic_financials", get_basic_financials)

    captured: list = []
    node = fundamentals_mod.create_fundamentals_analyst(
        _FakeLLM(["final report"], captured), config=_FORCED_CONFIG
    )

    state = _base_state()
    first = node(state)

    # Tool-loop re-entry: the same state key is present, so no re-gather.
    reentry_state = {**state, **first}
    second = node(reentry_state)

    assert calls["n"] == 1  # still one gather across both entries
    assert TOOL_EVIDENCE_KEY in second
    assert "fundamentals" in second[TOOL_EVIDENCE_KEY]

    # The rendered block on re-entry comes from the CACHED leaves.
    sys_text = "".join(
        getattr(m, "content", "") for m in captured if getattr(m, "type", "") == "system"
    )
    assert EVIDENCE_SECTION_HEADER in sys_text


def test_analyst_without_forced_config_is_unchanged(monkeypatch):
    calls = {"n": 0}

    @tool
    def get_basic_financials(ticker: str) -> str:
        """Fake surface."""
        calls["n"] += 1
        return f"FIN_{ticker}"

    monkeypatch.setattr(toolsets_mod, "get_basic_financials", get_basic_financials)

    captured: list = []
    node = fundamentals_mod.create_fundamentals_analyst(
        _FakeLLM(["plain report"], captured), config=None
    )

    out = node(_base_state())
    # Legacy path: no gather; tool_evidence stays empty on the returned state.
    assert calls["n"] == 0
    assert out.get(TOOL_EVIDENCE_KEY) == {}
    assert out["fundamentals_report"] == "plain report"
    sys = "".join(m.content for m in captured if getattr(m, "type", "") == "system")
    assert EVIDENCE_SECTION_HEADER not in sys


def test_market_and_news_prompts_carry_verbatim_citation_rule():
    """Regression (QCOM 2026-09-07 news.md/market.md): analysts re-typed and
    spliced figures from different tools ('TGA 303.9->944B' for 903.9,
    'CCC 0.51%' for 10.51, a 5.97 ATR onto a stop built from 5.1243). The
    rendered prompt must carry the hard verbatim-citation + conflict-quote
    rule so numbers are copied, never retyped or spliced."""
    captured: list = []
    market_mod.create_market_analyst(_FakeLLM(["m"], captured), config=None)(_base_state())
    sys_text = "".join(m.content for m in captured if getattr(m, "type", "") == "system")
    assert "HARD CITATION RULE" in sys_text
    assert "quote BOTH with their tool names" in sys_text

    captured = []
    news_mod.create_news_analyst(_FakeLLM(["n"], captured), config=None)(_base_state())
    sys_text = "".join(m.content for m in captured if getattr(m, "type", "") == "system")
    assert "HARD CITATION RULE" in sys_text
    assert "never splice, substitute, or reconcile silently" in sys_text


def test_evidence_block_render_carries_citation_rule():
    """The shared §Tool Evidence block (all evidence-fed analysts) states the
    same verbatim-copy / conflict-quote rule above the leaves."""
    block = format_evidence_block(
        [{"tool": "get_news", "status": "ok", "content": "octopus", "args": {}}]
    )
    assert "HARD CITATION RULE" in block
    assert "quote BOTH with their tool names" in block
    assert "octopus" in block


def _base_state():
    return {
        "company_of_interest": "TSM",
        "asset_type": "stock",
        "trade_date": "2026-09-07",
        "instrument_context": "The instrument to analyze is `TSM`.",
        "messages": [HumanMessage(content="Analyze TSM")],
        TOOL_EVIDENCE_KEY: {},
    }
