"""Alpaca data-only vendor unit tests (offline; mock the HTTP layer)."""

from unittest import mock

import pytest


def _patch(payload):
    return mock.patch("tradingagents.dataflows.alpaca.alpaca_get",
                      side_effect=lambda *a, **k: payload)


def test_bars_parse():
    from tradingagents.dataflows import alpaca

    payload = {"bars": [{"t": "2026-08-18T04:00:00Z", "o": 100.0, "h": 103.0,
                         "l": 99.0, "c": 101.5, "v": 5_000_000}]}
    with _patch(payload):
        bars = alpaca.get_bars("AAPL", timeframe="1Day", limit=5)
    assert bars and bars[0]["c"] == 101.5
    assert bars[0]["v"] == 5_000_000


def test_batch_bars_map_by_symbol():
    from tradingagents.dataflows import alpaca

    payload = {"bars": {"AAPL": [{"t": "x", "o": 1, "h": 2, "l": 1, "c": 1.5,
                                  "v": 10}],
                        "MSFT": [{"t": "x", "o": 2, "h": 3, "l": 2, "c": 2.5,
                                  "v": 20}]}}
    with _patch(payload):
        out = alpaca.get_bars_batch(["AAPL", "MSFT"])
    assert out and set(out) == {"AAPL", "MSFT"}


def test_snapshot_daily_bar_fields():
    from tradingagents.dataflows import alpaca

    payload = {"AAPL": {"dailyBar": {"t": "2026-08-18",
                    "o": 100.0, "h": 103.0, "l": 99.0, "c": 101.5, "v": 9}}}
    with _patch(payload):
        out = alpaca.get_latest_snapshot(["AAPL"])
    assert out["AAPL"]["close"] == 101.5
    assert out["AAPL"]["high"] == 103.0


def test_calendar_first_row():
    from tradingagents.dataflows import alpaca

    payload = [{"date": "2026-08-18", "open": "09:30", "close": "16:00"}]
    with _patch(payload):
        cal = alpaca.get_calendar("2026-08-18", "2026-08-22")
    assert cal and cal["open"] == "09:30"


def test_no_credentials_no_http_call():
    from tradingagents.dataflows import alpaca_common

    with mock.patch.object(alpaca_common, "alpaca_credentials",
                           return_value=(None, None)), \
         mock.patch("requests.get") as req:
        out = alpaca_common.alpaca_get("stocks/AAPL/bars", {})
    assert out is None
    req.assert_not_called()


def test_screener_ohlcv_falls_back_to_alpaca():
    """When the vendor CSV path is empty and enable_alpaca, Alpaca bars fill OHLCV."""
    import scripts.value_screener as vs

    bars = [{"t": f"d{i}", "o": 100.0 + i, "h": 104.0 + i, "l": 98.0 + i,
             "c": 102.0 + i, "v": 5_000_000} for i in range(250)]
    with mock.patch.object(vs, "route_to_vendor", return_value="NO_DATA_AVAILABLE"), \
         mock.patch("tradingagents.dataflows.config.get_config",
                    return_value={"enable_alpaca": True}), \
         mock.patch("tradingagents.dataflows.alpaca.alpaca_get",
                    return_value={"bars": bars}):
        o = vs._fetch_ohlcv("AAPL")
    assert len(o["closes"]) == 250
    assert o["volumes"][-1] == 5_000_000
