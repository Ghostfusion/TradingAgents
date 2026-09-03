"""Phase 1: prediction ledger + MAE/MFE (W1-1/3) + LLM cost (W1-8) tests."""

import pathlib
import tempfile

import pytest

from tradingagents.strategies import llm_cost, prediction_ledger as pl

pytestmark = pytest.mark.timeout(30)


def _tmp():
    return str(pathlib.Path(tempfile.mkdtemp()))


class TestLedger:
    def test_log_and_read_roundtrip(self):
        d = _tmp()
        r = pl.log_decision("MSFT", "2026-09-02", "Buy", direction="long",
                            entry=100.0, target=115.0, stop=95.0,
                            confidence=0.78, results_dir=d)
        assert r["ticker"] == "MSFT" and r["rating"] == "Buy"
        got = pl.rows(d)
        assert len(got) == 1 and got[0]["entry"] == 100.0

    def test_extra_fields(self):
        d = _tmp()
        pl.log_decision("AAPL", "2026-09-02", "Hold", results_dir=d,
                        regime="trending_up")
        assert pl.rows(d)[0]["regime"] == "trending_up"

    def test_corrupt_tail_tolerated(self):
        d = _tmp()
        pl.log_decision("X", "d", "Hold", results_dir=d)
        p = pathlib.Path(d) / "predictions.jsonl"
        p.write_text(p.read_text(encoding="utf-8") + "{broken\n", encoding="utf-8")
        assert len(pl.rows(d)) == 1


class TestOutcome:
    def test_mae_mfe_long(self):
        closes = [100.0, 98.0, 96.0, 102.0, 108.0]
        om = pl.outcome_metrics(closes, entry=100.0, stop=90.0, target=115.0, direction="long")
        assert om["mae_pct"] == pytest.approx(-4.0, abs=0.01)   # touched 96
        assert om["mfe_pct"] == pytest.approx(8.0, abs=0.01)    # touched 108
        assert om["stop_hit"] is False and om["target_hit"] is False

    def test_stop_and_target_hits(self):
        closes = [100.0, 95.0, 90.0]
        om = pl.outcome_metrics(closes, entry=100.0, stop=92.0, target=120.0, direction="long")
        assert om["stop_hit"] is True and om["target_hit"] is False
        closes2 = [100.0, 121.0]
        om2 = pl.outcome_metrics(closes2, entry=100.0, stop=90.0, target=120.0, direction="long")
        assert om2["target_hit"] is True

    def test_short_sign(self):
        closes = [100.0, 104.0, 96.0]
        om = pl.outcome_metrics(closes, entry=100.0, stop=105.0, target=95.0, direction="short")
        assert om["mae_pct"] == pytest.approx(-4.0, abs=0.01)  # adverse = price rose to 104
        assert om["mfe_pct"] == pytest.approx(4.0, abs=0.01)   # favorable = price fell to 96
        assert om["stop_hit"] is False   # price only reached 104 < 105
        assert om["target_hit"] is False  # only reached 96 > 95

    def test_short_stop_hit(self):
        closes = [100.0, 106.0]
        om = pl.outcome_metrics(closes, entry=100.0, stop=105.0, target=95.0, direction="short")
        assert om["stop_hit"] is True

    def test_no_entry_or_empty_series(self):
        assert pl.outcome_metrics([], entry=None)["n_bars"] == 0
        assert pl.outcome_metrics([100.0, 101.0], entry=None)["mae_pct"] is None
        assert pl.outcome_metrics([], entry=100.0)["mae_pct"] is None


class TestScore:
    def test_score_hit_and_return(self):
        d = _tmp()
        pl.log_decision("MSFT", "2026-09-02", "Buy", direction="long",
                        entry=100.0, stop=90.0, target=115.0, horizon_days=3,
                        results_dir=d)
        scored = pl.score_all({("MSFT", "2026-09-02"): [100.0, 103.0, 106.0, 109.0]}, d)
        o = scored[0]["outcome"]
        assert o["hit"] is True
        # horizon_days=3 -> window [100,103,106], last=106 -> +6%
        assert o["return_pct"] == pytest.approx(6.0, abs=0.01)
        assert o["target_hit"] is False  # 115 not reached
        assert o["stop_hit"] is False    # never below 100

    def test_score_missing_series_none(self):
        d = _tmp()
        pl.log_decision("MSFT", "2026-09-02", "Buy", direction="long", entry=100.0, results_dir=d)
        scored = pl.score_all({}, d)
        assert scored[0]["outcome"] is None  # honest no-data

    def test_score_horizon_truncates(self):
        d = _tmp()
        pl.log_decision("X", "d", "Buy", direction="long", entry=100.0, horizon_days=2, results_dir=d)
        scored = pl.score_all({("X", "d"): [100.0, 101.0, 102.0, 103.0]}, d)
        assert scored[0]["outcome"]["n_scored"] == 2


class TestCost:
    def test_known_rate(self):
        assert llm_cost.rate_for("gpt-4o") is not None
        c = llm_cost.estimate_cost("gpt-4o", input_tokens=1_000_000, output_tokens=500_000)
        assert c == pytest.approx(2.5 + 5.0, abs=0.01)

    def test_unknown_model_none(self):
        assert llm_cost.rate_for("unknown-vendor") is None
        assert llm_cost.estimate_cost("unknown-vendor", 100, 100) is None

    def test_missing_tokens_none(self):
        assert llm_cost.estimate_cost("gpt-4o", None, 100) is None
        assert llm_cost.estimate_cost("", 100, 100) is None

    def test_prefix_longest_match(self):
        # gpt-4 prefix wins over gpt- for gpt-4o
        assert llm_cost.rate_for("gpt-4o") == (2.50, 10.00)
        assert llm_cost.rate_for("gpt-4-turbo") == (30.00, 60.00)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

