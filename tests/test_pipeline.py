"""B2 pipeline tests: universe -> screen -> rank -> top-N -> batch summary."""

import unittest
from unittest import mock

import pipeline


class _FakeScreener:
    """Minimal value_screener stand-in for pipeline logic."""

    @staticmethod
    def _is_non_equity(name):
        return name in ("FUND", "ETF")

    @staticmethod
    def _fetch_closes(ticker):
        return [100.0 + i for i in range(120)]

    @staticmethod
    def fetch_ticker(ticker, run_date):
        return {"ticker": ticker}

    @staticmethod
    def screen_ticker(ticker, fin):
        m = {"AAPL": (0.08, 20.0), "MSFT": (0.06, 25.0), "NVDA": (0.12, 15.0)}
        ey, ev = m.get(ticker, (0.05, 50.0))
        return {"earnings_yield": ey, "ev_ebit": ev, "fscore": 7, "mscore": -2.3, "zscore": 4.1}

    @staticmethod
    def rank_watchlist(results):
        return sorted(results, key=lambda r: -(r["earnings_yield"] or -1))

    @staticmethod
    def composite_scores(results, closes_map):
        return {r["ticker"]: r["earnings_yield"] for r in results}

    @staticmethod
    def _fetch_closes(ticker):
        return _FakeScreener._score_closes(ticker) if False else [100.0 + i for i in range(120)]

    _score_closes = staticmethod(lambda t: [100.0 + i for i in range(120)])


class PipelineUnitTests(unittest.TestCase):
    def test_build_universe_from_tickers(self):
        args = mock.Mock(
            universe="tickers",
            tickers=["aapl", "MSFT"],
            file=None,
            market="US",
            movers_count=50,
            min_mcap=1e9,
            price_min=0,
            pe_max=0,
        )
        vs = _FakeScreener()
        tickers = pipeline._build_universe(vs, args)
        self.assertEqual(tickers, ["AAPL", "MSFT"])

    def test_build_universe_from_movers_respects_gates(self):
        args = mock.Mock(
            universe="top-losers",
            market="US",
            movers_count=50,
            min_mcap=10e9,
            price_min=15.0,
            pe_max=40.0,
            tickers=[],
            file=None,
        )
        movers = [
            {
                "symbol": "AAA",
                "name": "Acme",
                "cur_price": 100.0,
                "pe_ttm": 20.0,
                "market_cap": 50e9,
                "change_ratio": -0.05,
            },
            {
                "symbol": "BBB",
                "name": "Fund etf",
                "cur_price": 10.0,
                "pe_ttm": 5.0,
                "market_cap": 200e9,
                "change_ratio": -0.03,
            },  # non-equity name
            {
                "symbol": "CCC",
                "name": "Corp",
                "cur_price": 8.0,
                "pe_ttm": 10.0,
                "market_cap": 100e9,
                "change_ratio": -0.02,
            },  # below price gate
            {
                "symbol": "DDD",
                "name": "Labs",
                "cur_price": 60.0,
                "pe_ttm": 90.0,
                "market_cap": 12e9,
                "change_ratio": -0.01,
            },  # above PE gate
            {
                "symbol": "EEE",
                "name": "Big",
                "cur_price": 50.0,
                "pe_ttm": 30.0,
                "market_cap": 11e9,
                "change_ratio": -0.01,
            },
        ]
        with mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo", return_value=movers
        ):
            tickers = pipeline._build_universe(_FakeScreener(), args)
        self.assertEqual(tickers, ["AAA", "EEE"])

    def test_screen_and_rank_orders_by_ey(self):
        ranked = pipeline._screen_and_rank(_FakeScreener(), ["NVDA", "AAPL", "MSFT"], "2026-08-19")
        self.assertEqual(ranked[0]["ticker"], "NVDA")  # highest earnings yield first
        self.assertEqual(len(ranked), 3)

    def test_composite_picks_top_n(self):
        vs = _FakeScreener()
        ranked = [
            {"ticker": t, "earnings_yield": ey, "ev_ebit": ev}
            for t, ey, ev in [("AAPL", 0.08, 20), ("MSFT", 0.06, 25), ("NVDA", 0.03, 30)]
        ]
        picks = pipeline._composite_picks(vs, ranked, top=2)
        self.assertEqual([p["ticker"] for p in picks], ["AAPL", "MSFT"])

    def test_run_batch_calls_analyze_and_collects(self):
        def fake_analyze(symbol, date, analysts, depth, vendor):
            return (symbol, "Buy", f"reports/{symbol}_x", 1.2, "Buy")

        results = (
            pipeline._run_batch(
                [{"ticker": "AAPL"}, {"ticker": "MSFT"}],
                mock.Mock(
                    date="2026-08-19", analysts=["market"], depth="deep", workers=2, vendor="moomoo"
                ),
            )
            if False
            else None
        )
        # call directly with a patched batch.analyze
        with (
            mock.patch("pipeline.batch.analyze", side_effect=fake_analyze),
            mock.patch("pipeline.DEPTH_LEVELS", {"deep": 5}),
        ):
            args = mock.Mock(
                date="2026-08-19", analysts=["market"], depth="deep", workers=2, vendor="moomoo"
            )
            results = pipeline._run_batch([{"ticker": "AAPL"}, {"ticker": "MSFT"}], args)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.get("report_dir") for r in results))

    def test_write_summary_creates_files(self, tmp_path=None):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            old = Path.cwd()
            try:
                import os

                os.chdir(d)
                md, jl = pipeline._write_summary(
                    [{"ticker": "AAPL", "rating": "buy", "decision": "D", "report_dir": "r"}],
                    [{"ticker": "AAPL", "earnings_yield": 0.08, "ev_ebit": 20.0}],
                    ["AAPL"],
                    mock.Mock(
                        date="2026-08-19",
                        universe="tickers",
                        vendor="moomoo",
                        depth="deep",
                        analysts=["market"],
                        top=5,
                    ),
                    "T1",
                )
                self.assertTrue(md.exists())
                self.assertTrue(jl.exists())
                self.assertIn("AAPL", md.read_text(encoding="utf-8"))
            finally:
                import os

                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
