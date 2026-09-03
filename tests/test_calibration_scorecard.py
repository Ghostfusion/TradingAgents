"""Phase 4: calibration + scorecard + benchmark hierarchy + feedback (W1-2/4/6/7)."""

import pathlib
import tempfile

import pytest

from tradingagents.strategies.calibration import calibration_table, scorecard
from tradingagents.strategies.evaluate import benchmark_table
from tradingagents.strategies.prediction_ledger import log_decision, score_all

pytestmark = pytest.mark.timeout(30)


def _ledger_row(ticker, date, confidence, entry, stop=None, agent="market"):
    return {"ticker": ticker, "date": date, "rating": "Buy", "direction": "long",
            "entry": entry, "stop": stop, "target": entry * 1.2,
            "confidence": confidence, "horizon_days": 3, "data_quality": "fresh",
            "agent": agent}


class TestCalibration:
    def test_bins_hit_rate(self):
        rows = [
            _ledger_row("A", "d1", 0.55, 100.0),
            _ledger_row("B", "d2", 0.55, 100.0),
            _ledger_row("C", "d3", 0.55, 100.0),
            _ledger_row("D", "d4", 0.95, 100.0),
        ]
        closes = {("A", "d1"): [100, 115], ("B", "d2"): [100, 115],
                  ("C", "d3"): [100, 90], ("D", "d4"): [100, 108]}
        d = str(pathlib.Path(tempfile.mkdtemp()))
        for r in rows:
            # write via log_decision to keep shape
            log_decision(r["ticker"], r["date"], r["rating"], direction="long",
                         entry=r["entry"], stop=r["stop"], target=r["entry"] * 1.2,
                         confidence=r["confidence"], horizon_days=3, results_dir=d,
                         agent=r["agent"])
        scored = score_all(closes, d)
        tab = calibration_table(scored)
        b55 = next(t for t in tab if t["bin"].startswith("50%"))
        assert b55["n"] == 3 and b55["actual_hit_rate"] == pytest.approx(2 / 3, abs=0.01)
        b95 = next(t for t in tab if t["bin"].startswith("90%"))
        assert b95["n"] == 1 and b95["actual_hit_rate"] == 1.0

    def test_no_confidence_rows_excluded(self):
        rows = [_ledger_row("A", "d1", None, 100.0)]
        # confidence None -> unable to bin; table empty
        d = str(pathlib.Path(tempfile.mkdtemp()))
        r = rows[0]
        log_decision(r["ticker"], r["date"], r["rating"], direction="long",
                     entry=r["entry"], confidence=None, horizon_days=3, results_dir=d)
        scored = [{"confidence": None, "outcome": {"hit": True}}]
        assert calibration_table(scored) == []


class TestScorecard:
    def test_per_agent_measurement(self):
        # market: 2/3 wins; news: 1/1 win
        rows = [
            _ledger_row("A", "d1", None, 100.0, agent="market"),
            _ledger_row("B", "d2", None, 100.0, agent="market"),
            _ledger_row("C", "d3", None, 100.0, agent="market"),
            _ledger_row("D", "d4", None, 100.0, agent="news"),
        ]
        closes = {("A", "d1"): [100, 115], ("B", "d2"): [100, 115],
                  ("C", "d3"): [100, 90], ("D", "d4"): [100, 108]}
        d = str(pathlib.Path(tempfile.mkdtemp()))
        for r in rows:
            log_decision(r["ticker"], r["date"], r["rating"], direction="long",
                         entry=r["entry"], confidence=None, horizon_days=3,
                         results_dir=d, agent=r["agent"])
        scored = score_all(closes, d)
        sc = {s["agent"]: s for s in scorecard(scored)}
        assert sc["market"]["hit_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert sc["market"]["predictions"] == 3
        assert sc["news"]["hit_rate"] == 1.0


class TestBenchmarkHierarchy:
    def test_compares_aligned_window(self):
        strat = [0.01] * 100
        bench = [0.005] * 100
        out = benchmark_table(strat, bench, simple={"buy&hold": [0.0] * 100})
        assert out["window"] == 100 and len(out["rows"]) == 3
        names = [r["name"] for r in out["rows"]]
        assert names == ["strategy", "benchmark", "buy&hold"]
        assert out["rows"][0]["sharpe"] is not None

    def test_short_series_none(self):
        out = benchmark_table([0.01], [0.005])
        assert out["rows"][0]["total_return"] is None


class TestFeedback:
    def test_auto_invalidate_on_stop(self):
        d = str(pathlib.Path(tempfile.mkdtemp()))
        log_decision("MSFT", "2026-09-02", "Buy", direction="long",
                     entry=100.0, stop=95.0, confidence=0.9, horizon_days=3, results_dir=d)
        scored = score_all({("MSFT", "2026-09-02"): [100, 94, 93, 92]}, d,
                           auto_invalidate=True)
        assert scored[0]["outcome"]["stop_hit"] is True
        from tradingagents.strategies.invalidation_ledger import rows

        lr = rows("MSFT", results_dir=d)
        assert len(lr) == 1 and "stop_loss" in lr[0]["conditions"][0]

    def test_no_invalidate_when_no_stop_hit(self):
        d = str(pathlib.Path(tempfile.mkdtemp()))
        log_decision("MSFT", "2026-09-02", "Buy", direction="long",
                     entry=100.0, stop=95.0, confidence=0.9, horizon_days=3, results_dir=d)
        score_all({("MSFT", "2026-09-02"): [100, 101, 102, 103]}, d, auto_invalidate=True)
        from tradingagents.strategies.invalidation_ledger import rows

        assert rows("MSFT", results_dir=d) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


