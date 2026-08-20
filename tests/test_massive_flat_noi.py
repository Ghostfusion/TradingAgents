"""Massive Flat Files (bulk OHLCV) + WebSocket NOI monitor tests (offline)."""

import json
import unittest
from unittest import mock

import pytest

from tradingagents.dataflows import massive_flat, massive_noi

_FLAT_CSV = """ticker,volume,open,close,high,low,window_start,transactions
BCC,248274,61.68,61.99,62.565,61.41,1680033600000000000,4073
AAPL,28727878,119.79,120.47,120.53,118.81,1680033600000000000,100000
AAPL,28730100,119.80,120.60,120.70,118.90,1680120100000000000,100100
"""


@pytest.mark.unit
class MassiveFlatTests(unittest.TestCase):
    def setUp(self):
        self.path = "test_massive_flat.csv"
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(_FLAT_CSV)
        self.addCleanup(self._rm)

    def _rm(self):
        import os
        from contextlib import suppress

        with suppress(OSError):
            os.remove(self.path)

    def test_load_day_aggregates_parses_multiple_days(self):
        s = massive_flat.load_day_aggregates(self.path)
        self.assertIn("AAPL", s)
        self.assertEqual(s["AAPL"]["closes"], [120.47, 120.6])
        self.assertEqual(s["AAPL"]["highs"], [120.53, 120.7])
        self.assertEqual(s["AAPL"]["volumes"], [28727878.0, 28730100.0])
        self.assertEqual(len(s["BCC"]["closes"]), 1)

    def test_window_start_to_date(self):
        s = massive_flat.load_day_aggregates(self.path)
        self.assertTrue(s["AAPL"]["dates"])
        # 1680033600000000000 ns -> 2023-03-28 UTC
        self.assertIn("2023-03-28", s["AAPL"]["dates"])

    def test_ohlcv_for_ticker_returns_screener_shape(self):
        o = massive_flat.ohlcv_for_ticker(self.path, "AAPL")
        self.assertIsNotNone(o)
        for key in ("closes", "opens", "highs", "lows", "volumes", "dates"):
            self.assertIn(key, o)
        self.assertEqual(o["closes"], [120.47, 120.6])

    def test_ohlcv_for_missing_ticker_is_none(self):
        self.assertIsNone(massive_flat.ohlcv_for_ticker(self.path, "ZZZ"))

    def test_empty_csv_returns_empty(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("ticker,volume,open,close,high,low,window_start,transactions\n")
        self.assertEqual(massive_flat.load_day_aggregates(self.path), {})


@pytest.mark.unit
class MassiveNoiTests(unittest.TestCase):
    _EV = {
        "ev": "NOI", "T": "AAPL", "t": 1601318039223013600, "at": 1600,
        "a": "C", "x": 10, "o": 480, "p": 440, "b": 25.03,
    }

    def test_build_url_list_and_token(self):
        u = massive_noi.build_url(["AAPL", "MSFT"], "SECRET")
        self.assertIn("ticker=AAPL,MSFT", u)
        self.assertIn("token=SECRET", u)

    def test_build_url_all(self):
        self.assertIn("ticker=*", massive_noi.build_url(["*"], "k"))

    def test_parse_frame_noi(self):
        ev = massive_noi.parse_frame(json.dumps(self._EV))
        self.assertEqual(ev["type"], "NOI")
        self.assertEqual(ev["ticker"], "AAPL")
        self.assertEqual(ev["auction"], "C")
        self.assertEqual(ev["imbalance"], 480)
        self.assertEqual(ev["clearing_price"], 25.03)

    def test_parse_frame_ignores_other_events(self):
        self.assertEqual(massive_noi.parse_frame(json.dumps({"ev": "quote"})), {})

    def test_describe(self):
        ev = massive_noi.parse_frame(json.dumps(self._EV))
        s = massive_noi.describe(ev)
        self.assertIn("NOI", s)
        self.assertIn("AAPL", s)
        self.assertIn("close", s)
        self.assertIn("480", s)

    def test_stream_noi_missing_dep_raises(self):
        with (
            mock.patch.object(
                massive_noi, "_client", side_effect=RuntimeError("no websocket-client")
            ),
            self.assertRaises(RuntimeError),
        ):
            massive_noi.stream_noi(["AAPL"], lambda e: None, api_key="k")
