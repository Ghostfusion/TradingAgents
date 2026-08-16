"""Symbol normalization must apply on every yfinance path, not just price fetch.

Regression tests for #983 (instrument identity), #984 (reflection returns), and
the news path: a broker symbol like XAUUSD must resolve to the same Yahoo symbol
(GC=F) that the price path uses, so identity, realized-return, and news lookups
hit the right instrument instead of failing/mismatching.
"""

import pandas as pd

import tradingagents.agents.utils.agent_utils as au
import tradingagents.dataflows.yfinance_news as ynews
import tradingagents.graph.trading_graph as tg
from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_identity_lookup_normalizes_symbol(monkeypatch):
    seen = {}

    class FakeTicker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        @property
        def info(self):
            return {"longName": "Gold Futures", "quoteType": "FUTURE"}

    monkeypatch.setattr(au.yf, "Ticker", FakeTicker)
    au.resolve_instrument_identity.cache_clear()

    identity = au.resolve_instrument_identity("XAUUSD")

    assert seen["symbol"] == "GC=F"  # normalized, not the raw broker symbol
    assert identity.get("company_name") == "Gold Futures"


def test_fetch_returns_normalizes_symbol(monkeypatch):
    queried = []

    class FakeTicker:
        def __init__(self, symbol):
            queried.append(symbol)

        def history(self, *args, **kwargs):
            return pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]})

    monkeypatch.setattr(tg.yf, "Ticker", FakeTicker)
    # Tier 3 trading-day calendar is not this test's subject — force the
    # calendar-heuristic fallback so the test stays hermetic (no OpenD).
    from tradingagents.dataflows import moomoo as moomoo_mod
    from tradingagents.dataflows.moomoo import MoomooNotConfiguredError

    def _no_calendar(*args, **kwargs):
        raise MoomooNotConfiguredError("OpenD not reachable in this test")

    monkeypatch.setattr(moomoo_mod, "get_trading_days_between", _no_calendar)

    # _fetch_returns only needs ``self`` for the trading-day calendar
    # (Tier 3); build a bare instance rather than the full graph.
    import tradingagents.default_config as dc

    graph = object.__new__(TradingAgentsGraph)
    graph.config = dc.DEFAULT_CONFIG.copy()
    raw, alpha, days = graph._fetch_returns("XAUUSD", "2025-01-02", holding_days=5, benchmark="SPY")

    assert queried[0] == "GC=F"  # stock symbol normalized (#984)
    assert queried[1] == "SPY"  # benchmark left as the canonical symbol
    assert raw is not None and days is not None


def test_news_lookup_normalizes_symbol(monkeypatch):
    seen = {}

    class FakeTicker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        def get_news(self, count):
            return []

    monkeypatch.setattr(ynews.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(ynews, "yf_retry", lambda fn: fn())

    out = ynews.get_news_yfinance("XAUUSD", "2025-01-01", "2025-01-10")

    assert seen["symbol"] == "GC=F"  # news queried with the canonical symbol
    assert "XAUUSD" in out  # the user's ticker stays in the report
    assert "GC=F" in out  # provenance noted
