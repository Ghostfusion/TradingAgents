"""Phase 2: validation guards (W2) — CPCV, OOS split, walk-forward, DSR."""

import pytest

from tradingagents.strategies.alpha_zoo import bench_zoo
from tradingagents.strategies.evaluate import (
    cpcv_overfit_mask,
    deflated_sharpe,
    oos_split,
    purged_cpcv_splits,
    walk_forward_splits,
)

pytestmark = pytest.mark.timeout(30)


def _records(n=120):
    # a signal that genuinely predicts (close = trend), so rank IC is non-zero
    return [{"close": 100.0 + i * 0.5, "volume": 1000 + i} for i in range(n)]


class TestCpcv:
    def test_splits_cover_all_indices(self):
        n = 50
        covered, seen = set(), 0
        for train, test in purged_cpcv_splits(n, n_splits=5):
            assert max(test) < n and min(train) >= 0
            covered.update(test)
        assert len(covered) == n  # every index tested in some fold

    def test_train_excludes_test_with_embargo(self):
        for train, test in purged_cpcv_splits(50, n_splits=5, embargo=2):
            lo, hi = min(test) - 2, max(test) + 3
            assert not any(lo <= i < hi for i in train)

    def test_cpcv_overfit_mask(self):
        # best in-sample IPC fold fails OOS -> flagged
        assert cpcv_overfit_mask([0.10, 0.02, 0.01], [-0.05, 0.02, 0.01]) is True
        assert cpcv_overfit_mask([0.10, 0.02], [0.09, 0.02]) is False


class TestOOS:
    def test_oos_split_slices_tail(self):
        sig, fwd = list(range(100)), list(range(100))
        so, fo = oos_split(sig, fwd, train_frac=0.7)
        assert len(so) == 30 and so[0] == 70 and fo[0] == 70

    def test_oos_split_edge(self):
        assert oos_split([1], [1], train_frac=0.7) == ([], [])
        assert oos_split([1, 2], [1, 2], train_frac=0.0) == ([], [])


class TestWalkForward:
    def test_yields_rolling_folds(self):
        folds = list(walk_forward_splits(list(range(100)), 40, 20))
        assert len(folds) == 3  # (0:40,40:60), (40:80,80:100)
        assert folds[0][0][0] == 0 and folds[0][1][0] == 40


class TestBenchValidation:
    def test_oos_and_wf_columns(self):
        recs = _records()
        out = bench_zoo(["close"], recs, forward_days=1, walk_forward=True)
        r = out[0]
        assert r["rank_ic"] is not None and r["oos_rank_ic"] is not None
        assert r["wf_ic"] is not None

    def test_cpcv_column(self):
        out = bench_zoo(["close"], _records(), forward_days=1, cpcv_folds=5)
        assert out[0]["cpcv_overfit"] is not None

    def test_deflated_column(self):
        out = bench_zoo(["close"], _records(), forward_days=1, n_trials=10)
        assert out[0]["deflated_ic"] is not None

    def test_error_not_raised(self):
        out = bench_zoo(["bogus(close)"], _records())
        assert out[0]["error"] and out[0]["rank_ic"] is None


class TestDeflatedSharpe:
    def test_penalizes_multiple_trials(self):
        rets = [0.01] * 100
        assert deflated_sharpe(rets, n_trials=1) > deflated_sharpe(rets, n_trials=50)
        assert deflated_sharpe(rets, n_trials=1) == deflated_sharpe(rets, n_trials=1)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
