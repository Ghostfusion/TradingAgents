"""Batch runner --probe tracing: per-stage JSONL writes around the graph run."""

import unittest
from unittest import mock

import batch


class BatchProbeTests(unittest.TestCase):
    def tearDown(self):
        batch.config_probe = None
        batch._probe_start = 0.0

    def _probe(self, events):
        def fn(symbol, stage, t, config=None, error=None, wall_seconds=None):
            events.append(
                {
                    "symbol": symbol,
                    "stage": stage,
                    "error": error,
                    "wall_seconds": wall_seconds,
                    "has_config": config is not None,
                }
            )

        return fn

    def test_probe_traces_done_stages(self):
        """graph_start/graph_done fire with the per-worker config and elapsed
        wall time when a probe is installed (--probe path)."""
        events = []

        class FakeGraph:
            def __init__(self, **kwargs):
                pass

            def propagate(self, symbol, trade_date):
                return {"final_trade_decision": "**Rating**: Buy\nPlan."}, "Buy"

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
            mock.patch.object(batch, "crypto_base", lambda s: None),
        ):
            batch.config_probe = self._probe(events)
            sym, decision, _, wall, rating = batch.analyze(
                "AAPL", "2026-08-01", ("market",), depth=3, vendor="default"
            )

        self.assertEqual(sym, "AAPL")
        self.assertEqual(rating, "Buy")
        stages = [e["stage"] for e in events]
        self.assertEqual(stages[:2], ["graph_start", "graph_done"])
        self.assertTrue(events[0]["has_config"])
        self.assertIsNone(events[0]["error"])
        self.assertIsNone(events[1]["error"])
        self.assertIsNotNone(events[1]["wall_seconds"])
        self.assertEqual(wall, events[1]["wall_seconds"])

    def test_probe_absent_is_noop(self):
        """Without --probe (config_probe None) the graph runs untraced and no
        probe callback is ever invoked."""
        events = []

        class FakeGraph:
            def __init__(self, **kwargs):
                pass

            def propagate(self, symbol, trade_date):
                return {"final_trade_decision": "Hold"}, "Hold"

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
            mock.patch.object(batch, "crypto_base", lambda s: None),
        ):
            batch.analyze("AAPL", "2026-08-01", ("market",), depth=3, vendor="default")

        self.assertEqual(events, [])

    def test_probe_records_graph_failure(self):
        """A propagate failure is probed (graph_failed + error) then re-raised -
        the batch keeps other symbols running but the trace says what broke."""
        events = []

        class FailingGraph:
            def __init__(self, **kwargs):
                pass

            def propagate(self, symbol, trade_date):
                raise RuntimeError("vendor boom")

            def save_reports(self, *args, **kwargs):
                return "fake_report_dir"

        with (
            mock.patch.object(batch, "TradingAgentsGraph", FailingGraph),
            mock.patch.object(batch, "crypto_base", lambda s: None),
        ):
            batch.config_probe = self._probe(events)
            with self.assertRaises(RuntimeError):
                batch.analyze("AAPL", "2026-08-01", ("market",), depth=3, vendor="default")

        self.assertEqual(events[0]["stage"], "graph_start")
        self.assertEqual(events[1]["stage"], "graph_failed")
        self.assertEqual(events[1]["error"], "vendor boom")


if __name__ == "__main__":
    unittest.main()
