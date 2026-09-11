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

        args = mock.Mock(
            date="2026-08-19", analysts=["market"], depth="deep", workers=2, vendor="moomoo"
        )
        with (
            mock.patch("pipeline.batch.analyze", side_effect=fake_analyze),
            mock.patch("pipeline.batch.effective_workers", return_value=2),
        ):
            results = pipeline._run_batch([{"ticker": "AAPL"}, {"ticker": "MSFT"}], args)
        self.assertEqual({r["ticker"] for r in results}, {"AAPL", "MSFT"})
        for row in results:
            self.assertEqual(row["decision"], "Buy")
            self.assertEqual(row["rating"], "Buy")
            self.assertTrue(row["report_dir"])
            self.assertEqual(row["wall_seconds"], 1.2)


def test_write_summary_creates_files(tmp_path, monkeypatch):
    """_write_summary writes pipeline_<stamp>.md/.jsonl under the resolved
    output dir and lists the screened candidates."""
    monkeypatch.chdir(tmp_path)
    # resolve_output_path anchors to the repo root, so point it at tmp_path:
    # otherwise the test writes into the real <repo>/reports.
    monkeypatch.setattr(
        "tradingagents.dataflows.utils.resolve_output_path",
        lambda _which: tmp_path / "reports",
    )
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
    assert md.exists() and md.name == "pipeline_T1.md"
    assert jl.exists() and jl.name == "pipeline_T1.jsonl"
    assert "AAPL" in md.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
