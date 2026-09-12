"""Same-night pre-market re-check runs inside analyze(), and only there.

The CLI batch and the sibling web app (``trading_web``'s ``run_batch``, which
calls ``batch.analyze`` in-process) share one implementation; a step living in
``main()``'s ``as_completed`` loop was silently skipped by the web path, so the
same job produced different artefacts per entry point.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import batch


class FakeGraph:
    def __init__(self, **kwargs):
        pass

    def propagate(self, symbol, trade_date):
        return {"final_trade_decision": "**Rating**: Buy\nPlan."}, "Buy"

    def save_reports(self, *args, **kwargs):
        return "fake_report_dir"


def _analyze(symbol="AAPL", trade_date="2026-08-01"):
    """Run analyze() with a stub graph; nothing touches the real reports tree."""
    with (
        mock.patch.object(batch, "TradingAgentsGraph", FakeGraph),
        mock.patch.object(batch, "crypto_base", lambda s: None),
    ):
        return batch.analyze(symbol, trade_date, ("market",), depth=3, vendor="default")


class BatchPreMarketAnalyzeTests(unittest.TestCase):
    def test_analyze_runs_pre_market_check_once(self):
        """With the flag on, analyze() does the re-check itself, passing the
        symbol, the report dir it just wrote and its own trade_date."""
        calls = []

        with (
            mock.patch.dict(batch.DEFAULT_CONFIG, {"enable_pre_market_review": True}),
            mock.patch.object(
                batch, "_batch_pre_market_check", side_effect=lambda *a: calls.append(a)
            ),
        ):
            sym, _, report_dir, _, _ = _analyze()

        self.assertEqual(sym, "AAPL")
        self.assertEqual(calls, [("AAPL", report_dir, "2026-08-01")])

    def test_analyze_skips_pre_market_check_when_disabled(self):
        """The opt-in gate still applies: flag off -> no re-check."""
        calls = []

        with (
            mock.patch.dict(batch.DEFAULT_CONFIG, {"enable_pre_market_review": False}),
            mock.patch.object(
                batch, "_batch_pre_market_check", side_effect=lambda *a: calls.append(a)
            ),
        ):
            _analyze()

        self.assertEqual(calls, [])


class BatchMainPreMarketTests(unittest.TestCase):
    def test_main_does_not_run_pre_market_check(self):
        """main() must not run the re-check: with analyze() stubbed out, any
        call could only come from the loop, and it must be zero (a double run
        would write pre_market_review_<date>.md twice per symbol)."""
        calls = []

        def fake_analyze(symbol, *args):
            return symbol, "Buy", f"reports/{symbol}_x", 1.2, "Buy"

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(batch, "analyze", side_effect=fake_analyze),
            mock.patch.object(batch, "resolve_output_path", lambda _which: Path(tmp)),
            mock.patch.dict(batch.DEFAULT_CONFIG, {"enable_pre_market_review": True}),
            mock.patch.object(
                batch,
                "_batch_pre_market_check",
                side_effect=lambda *a: calls.append(a),
            ),
            mock.patch.object(sys, "argv", ["batch.py", "--symbols", "AAPL", "MSFT"]),
        ):
            rc = batch.main()

        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
