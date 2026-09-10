"""Tests for ETF routing in the fundamentals analyst (design_etf_fundamental_valuation.md).

Phase 5: when enable_etf_engine is on and the security classifies as an ETF,
the fundamentals analyst swaps the company statement toolset for the ETF one
(get_etf_valuation / get_etf_decline_driver / get_etf_relative_strength /
get_etf_risk / get_etf_mechanics) and appends the ETF system tail; state is
stamped with security_type. Default-off: a UNKNOWN classification keeps the
company path unchanged.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from tradingagents.agents.analysts import fundamentals_analyst as fundamentals_mod
from tradingagents.agents.utils.evidence_gather import TOOL_EVIDENCE_KEY


class _FakeLLM:
    def __init__(self, response="final report"):
        self.captured_tools = None

    def bind_tools(self, tools):
        self.captured_tools = {getattr(t, "name", str(t)) for t in tools}
        return _FakeChain("final report")


class _FakeChain:
    def __init__(self, text):
        self._text = text

    def __call__(self, messages):
        return AIMessage(content=self._text, tool_calls=[])


def _state(ticker="IGV"):
    return {
        "company_of_interest": ticker,
        "asset_type": "stock",
        "trade_date": "2026-09-09",
        "instrument_context": f"The instrument to analyze is `{ticker}`.",
        "messages": [HumanMessage(content=f"Analyze {ticker}")],
        TOOL_EVIDENCE_KEY: {},
    }


def _patch_identity(monkeypatch, quote_type="ETF", name="iShares Expanded Tech-Software Sector ETF"):
    monkeypatch.setattr(
        "tradingagents.agents.utils.agent_utils.resolve_instrument_identity",
        lambda ticker: {"quote_type": quote_type, "company_name": name},
    )


def test_etf_classification_uses_etf_toolset(monkeypatch):
    _patch_identity(monkeypatch)
    llm = _FakeLLM()
    node = fundamentals_mod.create_fundamentals_analyst(
        llm, config={"enable_etf_engine": True}
    )
    out = node(_state("IGV"))
    names = llm.captured_tools or set()
    # ETF toolset present; company statement tools gone.
    assert "get_etf_valuation" in names
    assert "get_etf_decline_driver" in names
    assert "get_etf_mechanics" in names
    assert "get_balance_sheet" not in names
    assert "get_dcf_valuation" not in names
    # security_type stamped on state
    assert out.get("security_type") == "ETF"


def test_etf_disabled_uses_company_toolset(monkeypatch):
    _patch_identity(monkeypatch, quote_type="EQ")
    llm = _FakeLLM()
    node = fundamentals_mod.create_fundamentals_analyst(llm, config={})
    out = node(_state("MSFT"))
    names = llm.captured_tools or set()
    assert "get_etf_valuation" not in names
    assert "get_balance_sheet" in names
    assert out.get("security_type") == "UNKNOWN"


def test_etf_engine_requires_flag(monkeypatch):
    # ETF engine off -> even an ETF-classified ticker keeps the company path.
    _patch_identity(monkeypatch)  # quote_type ETF
    llm = _FakeLLM()
    node = fundamentals_mod.create_fundamentals_analyst(llm, config=None)
    out = node(_state("IGV"))
    names = llm.captured_tools or set()
    assert "get_etf_valuation" not in names
    assert "get_balance_sheet" in names
    assert out.get("security_type") == "UNKNOWN"
