"""Batch runner vendor preset: --vendor merges a data-vendors chain per worker."""

import unittest
from unittest import mock

import batch
from batch import VENDOR_PRESETS


class BatchVendorPresetTests(unittest.TestCase):
    def test_moomoo_preset_is_moomoo_first_everywhere(self):
        chains = VENDOR_PRESETS["moomoo"]
        self.assertEqual(chains["core_stock_apis"], "moomoo,yfinance")
        self.assertEqual(chains["options_data"], "moomoo,yfinance")
        self.assertEqual(chains["analyst_ratings"], "moomoo,finnhub")
        self.assertEqual(chains["prediction_markets"], "moomoo,polymarket")
        self.assertEqual(chains["macro_data"], "moomoo,fred")
        # Every category is present so a preset never drops a source silently.
        self.assertEqual(set(chains), set(batch.DEFAULT_CONFIG["data_vendors"]))

    def test_yfinance_preset_is_pure_yfinance_stack(self):
        chains = VENDOR_PRESETS["yfinance"]
        self.assertEqual(chains["core_stock_apis"], "yfinance")
        self.assertEqual(chains["fundamental_data"], "yfinance")
        self.assertEqual(chains["prediction_markets"], "polymarket")
        self.assertEqual(set(chains), set(batch.DEFAULT_CONFIG["data_vendors"]))

    def test_analyze_applies_vendor_preset_per_worker(self):
        """analyze() must merge the preset into the worker's own data_vendors."""
        captured = {}

        class FakeGraph:
            def __init__(self, **kwargs):
                captured["config"] = kwargs["config"]

            def propagate(self, symbol, trade_date):
                captured["propagate"] = (symbol, trade_date)
                return {"final_trade_decision": "**Rating**: Buy\nPlan."}, "Buy"

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
            mock.patch.object(batch, "crypto_base", lambda s: None),
        ):
            sym, decision, report_dir, wall_seconds, rating = batch.analyze(
                "AAPL",
                "2026-08-01",
                ("market",),
                depth=3,
                vendor="moomoo",
            )

        self.assertEqual(sym, "AAPL")
        self.assertEqual(rating, "Buy")
        self.assertEqual(captured["propagate"], ("AAPL", "2026-08-01"))
        dv = captured["config"]["data_vendors"]
        self.assertEqual(dv["core_stock_apis"], "moomoo,yfinance")
        self.assertEqual(dv["prediction_markets"], "moomoo,polymarket")

    def test_analyze_default_vendor_keeps_config_chains(self):
        """vendor='default' must leave the .env / DEFAULT_CONFIG chains alone."""
        captured = {}

        class FakeGraph:
            def __init__(self, **kwargs):
                captured["config"] = kwargs["config"]

            def propagate(self, symbol, trade_date):
                return {"final_trade_decision": "Hold"}, "Hold"

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
            mock.patch.object(batch, "crypto_base", lambda s: None),
        ):
            batch.analyze("AAPL", "2026-08-01", ("market",), depth=3, vendor="default")

        dv = captured["config"]["data_vendors"]
        self.assertEqual(
            dv["core_stock_apis"],
            batch.DEFAULT_CONFIG["data_vendors"]["core_stock_apis"],
        )

    def test_crypto_override_still_wins_over_preset(self):
        """A crypto symbol must still disable ratings/earnings after the preset."""
        captured = {}

        class FakeGraph:
            def __init__(self, **kwargs):
                captured["config"] = kwargs["config"]

            def propagate(self, symbol, trade_date):
                return {"final_trade_decision": "Buy"}, "Buy"

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
            mock.patch.object(batch, "crypto_base", lambda s: "BTC"),
        ):
            batch.analyze("BTC-USD", "2026-08-01", ("market",), depth=3, vendor="moomoo")

        dv = captured["config"]["data_vendors"]
        self.assertEqual(dv["core_stock_apis"], "moomoo,yfinance")
        self.assertEqual(dv["analyst_ratings"], "none")
        self.assertEqual(dv["earnings_calendar"], "none")


if __name__ == "__main__":
    unittest.main()
