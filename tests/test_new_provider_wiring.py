"""Vendor-chain + tool-fallback wiring for the new Twelve Data / StockData.org.

Covers: routing registration, the get_market_snapshot fallback chain reaching
the new Twelve Data tail, and the get_crypto_prices Twelve Data fallback.
All hermetic (mock the network seams / module functions).
"""

from __future__ import annotations

from unittest import mock

import pytest

pytestmark = pytest.mark.timeout(180)


def test_twelve_data_and_stockdata_in_vendor_list():
    from tradingagents.dataflows.interface import VENDOR_LIST

    assert "twelve_data" in VENDOR_LIST
    assert "stockdata" in VENDOR_LIST


def test_twelve_data_and_stockdata_in_default_chains():
    from tradingagents.default_config import DEFAULT_CONFIG

    assert "twelve_data" in DEFAULT_CONFIG["data_vendors"]["core_stock_apis"]
    assert "stockdata" in DEFAULT_CONFIG["data_vendors"]["core_stock_apis"]
    assert "stockdata" in DEFAULT_CONFIG["data_vendors"]["news_data"]


def test_market_snapshot_falls_back_to_twelve_data_when_all_previous_fail():
    """The market-snapshot tool must degrade Massive -> EODHD -> Tiingo ->
    Twelve Data, so a new provider is reachable when all others fail."""
    from tradingagents.agents.utils.market_position_tools import get_market_snapshot

    def twelve(tk):
        return "## Market Snapshot — AAPL (Twelve Data)\n- ticker: AAPL\n- close: 319.70"

    with mock.patch(
        "tradingagents.dataflows.massive.get_market_snapshot_massive"
    ) as massive, mock.patch(
        "tradingagents.dataflows.eodhd.get_market_snapshot_eodhd"
    ) as eodhd, mock.patch(
        "tradingagents.dataflows.tiingo.get_market_snapshot_tiingo"
    ) as tiingo, mock.patch(
        "tradingagents.dataflows.twelve_data.get_market_snapshot_twelve_data", twelve
    ):
        massive.side_effect = Exception("massive down")
        eodhd.side_effect = Exception("eodhd down")
        tiingo.side_effect = Exception("tiingo down")
        out = get_market_snapshot.invoke({"ticker": "AAPL"})
    assert "Twelve Data" in out
    assert "319.70" in out


def test_market_snapshot_returns_massive_when_available():
    from tradingagents.agents.utils.market_position_tools import get_market_snapshot

    with mock.patch(
        "tradingagents.dataflows.massive.get_market_snapshot_massive",
        return_value="## AAPL Market Snapshot — Massive",
    ) as massive:
        out = get_market_snapshot.invoke({"ticker": "AAPL"})
    assert "Massive" in out
    massive.assert_called_once()


def test_crypto_prices_falls_back_to_twelve_data():
    from tradingagents.agents.utils.market_position_tools import get_crypto_prices

    def twelve(tk, start, end):
        return "Date,Open,High,Low,Close,Volume\n2026-08-28,80249.59,81478.87,76888.00,77845.87,0"

    with mock.patch(
        "tradingagents.dataflows.tiingo.get_crypto_prices_tiingo"
    ) as tiingo, mock.patch(
        "tradingagents.dataflows.twelve_data.get_crypto_prices_twelve_data", twelve
    ):
        tiingo.side_effect = Exception("tiingo down")
        out = get_crypto_prices.invoke(
            {"ticker": "BTC-USD", "start_date": "2026-08-28", "end_date": "2026-08-30"}
        )
    assert "Date,Open,High,Low,Close,Volume" in out
    assert "2026-08-28" in out
