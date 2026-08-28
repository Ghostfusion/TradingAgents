"""The market analyst is bound (and prompt-instructed) to call
get_verified_market_snapshot; if the executor ToolNode doesn't register it, the
call fails and the model reports the tool "unavailable" and skips verification.

Regression guard for that wiring gap (snapshot bound to the LLM but missing from
the market ToolNode).
"""
import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
def test_market_toolnode_can_execute_verified_snapshot():
    # _create_tool_nodes does not use self -> call unbound (avoids building LLMs).
    nodes = TradingAgentsGraph._create_tool_nodes(None)
    market_tools = set(nodes["market"].tools_by_name)
    assert "get_verified_market_snapshot" in market_tools, (
        "get_verified_market_snapshot is bound to the market analyst but not "
        "registered in the market ToolNode, so the model's call fails."
    )
    # the other core market tools must remain too
    assert {"get_stock_data", "get_indicators"} <= market_tools


@pytest.mark.unit
def test_market_toolnode_binds_swing_dip_and_market_session_tools():
    """Regression guard: the market analyst's prompt lists get_swing_exits /
    get_dip_technical / get_mean_reversion_tech and the 5 market-session tools
    (get_opening_range / get_gap_type / get_order_imbalance /
    get_premarket_liquidity / get_post_close_confirmation), but they were NOT
    registered in the market ToolNode (a wiring gap from the original
    value-dip+swing commits) - so every run had the LLM call tools that error
    with "not a valid tool". They must all be executable here.
    """
    nodes = TradingAgentsGraph._create_tool_nodes(None)
    market_tools = set(nodes["market"].tools_by_name)
    expected = {
        "get_swing_exits",
        "get_dip_technical",
        "get_mean_reversion_tech",
        "get_opening_range",
        "get_gap_type",
        "get_order_imbalance",
        "get_premarket_liquidity",
        "get_post_close_confirmation",
    }
    missing = expected - market_tools
    assert not missing, (
        "market analyst prompt lists these tools but the market ToolNode does "
        f"not bind them (LLM calls error 'not a valid tool'): {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# get_sec_filings -> Massive insider fallback (when SEC EDGAR fails)
# ---------------------------------------------------------------------------


def test_sec_filings_returns_edgar_when_available(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as mpt

    monkeypatch.setattr(
        mpt, "route_to_vendor", lambda *a, **k: "## Recent SEC Filings\n| 8-K | 2026-08-01 | ..."
    )
    out = mpt.get_sec_filings.invoke({"ticker": "AAPL"})
    assert "## Recent SEC Filings" in out
    assert "Massive" not in out


def test_sec_filings_falls_back_to_massive_on_error(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as mpt

    def boom(*a, **k):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(mpt, "route_to_vendor", boom)
    monkeypatch.setattr(
        mpt,
        "_sec_filings_massive_fallback",
        lambda t: "MASSIVE_FALLBACK_FORM4 " + t.upper(),
    )
    out = mpt.get_sec_filings.invoke({"ticker": "MSFT"})
    assert "MASSIVE_FALLBACK_FORM4 MSFT" in out


def test_sec_filings_falls_back_on_no_data_sentinel(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as mpt

    monkeypatch.setattr(
        mpt, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE: no EDGAR record"
    )
    monkeypatch.setattr(
        mpt, "_sec_filings_massive_fallback", lambda t: "FALLBACK " + t
    )
    out = mpt.get_sec_filings.invoke({"ticker": "0700.HK"})
    assert "FALLBACK 0700.HK" in out


def test_sec_filings_massive_fallback_returns_insider_body(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as mpt

    fake_massive = "## EIX Insider Transactions (Form 4, Massive.com)\n- BUY 100 sh"
    monkeypatch.setattr("tradingagents.dataflows.massive.get_form4_insider_massive", lambda *a, **k: fake_massive)
    out = mpt.get_sec_filings.invoke({"ticker": "EIX"})
    assert "Massive insider-activity fallback" in out
    assert "Form 4" in out
    assert "Insider Transactions" in out


def test_sec_filings_massive_fallback_degrades_when_both_down(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as mpt

    def boom(*a, **k):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(mpt, "route_to_vendor", boom)
    monkeypatch.setattr(
        "tradingagents.dataflows.massive.get_form4_insider_massive",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("massive down")),
    )
    out = mpt.get_sec_filings.invoke({"ticker": "EIX"})
    assert "unavailable" in out.lower()
    assert "fabricate" in out.lower()
