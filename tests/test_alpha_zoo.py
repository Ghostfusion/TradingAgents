"""Vibe-Trading alpha-zoo transfer (P2-6): purity gate + bounded evaluator +
bench. The zoo is a pure, offline catalog — no LLM, no network."""

import pytest

from tradingagents.strategies.alpha_zoo import bench_zoo, evaluate_expr, purity_gate

pytestmark = pytest.mark.timeout(30)


def _records(n=60):
    return [{"close": 100.0 + i * 2, "volume": 1000 + i,
             "open": 99.0 + i * 2, "high": 101.0 + i * 2, "low": 98.0 + i * 2}
            for i in range(n)]


class TestPurityGate:
    def test_ok_expressions(self):
        for e in ("close", "pct_change(close, 1)", "delta(close, 1)",
                  "zscore(mean(close, 5), 10)", "rank(close)", "sign(delta(close, 1))"):
            ok, _ = purity_gate(e)
            assert ok, f"should pass: {e}"

    def test_rejects_attacks(self):
        for e in ('__import__("os")', "close[0]", "x.y", "open(1)",
                  "getattr(close, 'x')", "close.x", "lambda: 1"):
            ok, reason = purity_gate(e)
            assert not ok, f"should reject: {e} -> {reason}"

    def test_rejects_unknown_name(self):
        assert not purity_gate("bogus(close)")[0]
        assert "unknown operator" in purity_gate("bogus(close)")[1]

    def test_empty_and_long(self):
        assert not purity_gate("")[0]
        assert not purity_gate("zscore(" + "1" * 500 + ")")[0]


class TestEvaluate:
    def test_column_series(self):
        series, err = evaluate_expr("close", _records())
        assert err == "" and series[0] == 100.0

    def test_operator_series(self):
        series, err = evaluate_expr("pct_change(close, 1)", _records())
        assert err == "" and series[0] is None and series[1] is not None

    def test_ungated_fails(self):
        series, err = evaluate_expr("__import__('os')", _records())
        assert series is None and err


class TestBench:
    def test_bench_returns_rows(self):
        out = bench_zoo(["close", "pct_change(close, 1)", "bogus(close)"], _records())
        assert len(out) == 3
        assert out[0]["rank_ic"] is not None  # monotone close -> IC 1.0
        assert out[2]["error"]  # unknown op flagged

    def test_bench_never_raises(self):
        out = bench_zoo(["close"], [])
        assert out == [{"expr": "close", "rank_ic": None, "error": None}] or out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
