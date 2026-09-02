"""Tests for the Qlib Phase-1 pure modules.

Covers design_qlib_integration.md §8 acceptance items 1-3, 7-9:
- §8-1  get_factor_profile-style factor set on a live series; unavailable path
- §8-7  learn/infer split: a malicious test-window value never changes the
        train-fitted moments
- §8-2  rank_ic / icir recover planted signals; quantile monotonicity
- §8-3  topk-drop holds top-k, drops worst-held, turnover = 2*drop/topk
- §8-9  convex enhanced-index caps tracking error AND turnover, honours
        masks, falls back to w0 on an infeasible problem
- §8-8  market_tradability: limit-up blocks a buy, suspended day -> no fill,
        participation cap truncates qty, deal-price selector
"""

import math

import numpy as np
import pytest

from tradingagents.strategies import (
    factor_expressions as fe,
    market_tradability as mt,
    portfolio_strategy as ps,
    signal_analysis as sa,
)

pytestmark = pytest.mark.timeout(30)


def _rising_ohlcv(n: int = 120, step: float = 2.0) -> dict:
    closes = [100.0 + step * i for i in range(n)]
    return {
        "closes": closes,
        "opens": closes,
        "highs": [c + 3 for c in closes],
        "lows": [c - 3 for c in closes],
        "volumes": [1_000_000] * n,
    }


# ---------------------------------------------------------------------------
# factor_expressions
# ---------------------------------------------------------------------------


class TestFactorExpressions:
    def test_alpha158_shape_and_leads(self):
        out = fe.alpha158_subset(_rising_ohlcv())
        assert set(out) == set(fe._ALPHA158_SUBSET)
        assert len(out["mom_20"]) == 120
        assert out["mom_20"][0] is None  # leading pads
        assert out["mom_20"][-1] is not None
        assert out["rsi_14"][-1] == 100.0  # monotone-up -> 100

    def test_min_obs_returns_none(self):
        out = fe.alpha158_subset(_rising_ohlcv(5))
        assert out["mom_20"] == [None] * 5

    def test_operator_math(self):
        s = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert fe.delta(s, 1)[-1] == 1.0
        assert fe.mom(s, 2)[-1] == pytest.approx(5.0 / 3.0 - 1.0)
        assert fe.ref(s, 2)[2] == 1.0
        assert fe.mean(s, 3)[-1] == pytest.approx(4.0)
        assert fe.zscore(s, 3)[-1] is not None

    def test_profile_style_unavailable(self):
        fe.clear_expr_cache()
        # an expression cache miss for a nonsense expression -> empty, honest
        assert fe.cached_expression("alpha158:nope", "X", 100, None, _rising_ohlcv()) == []

    def test_expression_cache_hit_and_invalidation(self):
        fe.clear_expr_cache()
        ohlcv = _rising_ohlcv()
        first = fe.cached_expression("alpha158:rsi_14", "AAPL", 120, "2026-01-01", ohlcv)
        assert fe.expr_cache_size() == 1
        second = fe.cached_expression("alpha158:rsi_14", "AAPL", 120, "2026-01-01", ohlcv)
        assert first == second  # cache hit
        # a different as-of date must recompute (different key)
        other = fe.cached_expression("alpha158:rsi_14", "AAPL", 120, "2026-02-01", ohlcv)
        assert other == first  # same data, but cached under its own key
        assert fe.expr_cache_size() == 2

    def test_learn_infer_split_malicious_test_value(self):
        # §8-7: moments fit on the train segment ONLY; a malicious value in
        # the test window must not move the fitted mean/std.
        train = [float(i) for i in range(50)]
        moments = fe.fit_zscore(train)
        assert moments is not None
        leaked = fe.fit_zscore(train + [1e9])  # the prohibited re-fit
        assert leaked != moments  # this is exactly the leak the split forbids
        # determinism: the same train segment always yields the same moments
        assert fe.fit_zscore(list(train)) == moments
        # applying the train-fitted moments to the tail is stable + finite
        z = fe.apply_zscore([1e9], moments)[0]
        assert z is not None and math.isfinite(z)

    def test_winsorize_fit_apply(self):
        bounds = fe.fit_winsorize([1.0, 2.0, 3.0, 4.0, 5.0], lo_q=0.0, hi_q=1.0)
        assert bounds is not None and bounds == (1.0, 5.0)
        assert fe.apply_winsorize([200.0, 3.0], bounds) == [pytest.approx(5.0), 3.0]
        assert fe.apply_winsorize([200.0], None) == [None]  # no fitted bounds

    def test_cross_sectional_rank(self):
        panel = {"A": [1.0], "B": [3.0], "C": [2.0]}
        ranks = fe.cross_sectional_rank(panel, 0)
        assert ranks is not None
        assert ranks["B"] == 1.0 and ranks["C"] == 0.5 and ranks["A"] == 0.0


# ---------------------------------------------------------------------------
# signal_analysis
# ---------------------------------------------------------------------------


class TestSignalAnalysis:
    def _planted(self, n: int = 80, flip: bool = False):
        rng = np.random.default_rng(7)
        sig = rng.uniform(0, 1, n)
        fwd = 0.02 * (sig * (-1 if flip else 1)) + rng.normal(0, 0.001, n)
        return sig.tolist(), fwd.tolist()

    def test_rank_ic_planted_positive_and_reversed(self):
        sig, fwd = self._planted()
        ic = sa.rank_ic(sig, fwd)
        assert ic is not None and ic > 0.5
        neg = sa.rank_ic(sig, [0.02 * (1.0 - s) + 0.0 for s in sig])
        assert neg is not None and neg < -0.5

    def test_rank_ic_short_history_none(self):
        assert sa.rank_ic([1.0, 2.0, 3.0], [0.01, 0.02, 0.03]) is None

    def test_quantile_monotonicity(self):
        sig, fwd = self._planted()
        out = sa.quantile_long_short(sig, fwd, n_buckets=5, cost_bps=0)
        assert out is not None and out["monotonicity"] == 1.0
        assert out["long_short_return"] is not None
        assert out["long_short_return"] > 0

    def test_long_short_returns_arithmetic(self):
        ls, avg = sa.long_short_return(0.10, 0.02)
        assert ls == pytest.approx(0.04) and avg == pytest.approx(0.06)

    def test_pred_autocorr_sticky(self):
        sticky = [0.5 + 1e-3 * i for i in range(100)]
        assert sa.pred_autocorr(sticky) is not None
        assert sa.pred_autocorr(sticky) > 0.99

    def test_ic_decay_half_life(self):
        hl = sa.ic_decay_half_life([(1, 0.05), (2, 0.04), (5, 0.02), (10, 0.01)])
        assert hl is not None and 1.0 < hl < 10.0
        assert sa.ic_decay_half_life([(1, 0.05), (2, 0.06)]) is None  # no decay

    def test_with_without_cost_table(self):
        noisy = [0.01 + 0.002 * math.sin(i / 3) for i in range(30)]
        out = sa.with_without_cost_table(noisy, cost_bps=10)
        assert out["n"] == 30
        assert out["without_cost"]["sharpe"] > 0
        assert out["with_cost"]["sharpe"] is not None
        assert out["with_cost"]["cagr"] < out["without_cost"]["cagr"]


# ---------------------------------------------------------------------------
# portfolio_strategy
# ---------------------------------------------------------------------------


class TestPortfolioStrategy:
    def test_topk_drop_holds_top_k(self):
        scores = {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "E": 1.0}
        out = ps.topk_drop_weights(scores, held=["C", "D", "E"], topk=3, n_drop=1)
        assert out is not None
        assert out["held"] == ["A", "B", "C"]
        assert out["dropped"] == ["E"]
        assert out["turnover"] == pytest.approx(2.0 / 3.0, abs=1e-3)
        assert sum(out["weights"].values()) == pytest.approx(1.0, abs=1e-3)

    def test_topk_drop_no_held_buys_top(self):
        out = ps.topk_drop_weights({"A": 5.0, "B": 4.0, "C": 3.0}, held=[], topk=2, n_drop=1)
        assert out["held"] == ["A", "B"] and out["dropped"] == []

    def test_enhanced_index_caps_turnover_and_te(self):
        scores = {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0}
        bench = {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1}
        out = ps.enhanced_index_weights(scores, bench, bench, turnover_cap=0.1, b_dev=0.05)
        assert out is not None
        w = np.array([float(out[n]) for n in sorted(bench)])
        wb = np.array([bench[n] for n in sorted(bench)])
        assert np.sum(np.abs(w - wb)) <= 0.1 + 1e-6
        assert np.max(np.abs(w - wb)) <= 0.05 + 1e-6
        assert abs(np.sum(w) - 1.0) < 1e-6
        assert np.min(w) >= -1e-6

    def test_enhanced_index_masks(self):
        bench = {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1}
        out = ps.enhanced_index_weights(
            {"A": 0.0, "B": 10.0, "C": 0.0, "D": 0.0}, bench, bench,
            turnover_cap=0.2, b_dev=0.05, force_hold={"A", "B"}, force_sell={"C", "D"},
        )
        assert out is not None
        assert out["A"] >= 0.4 - 1e-6 and out["B"] >= 0.3 - 1e-6  # forced hold
        assert out["C"] <= 0.2 + 1e-6 and out["D"] <= 0.1 + 1e-6  # forced sell

    def test_enhanced_index_infeasible_returns_w0(self):
        # turnover cap 0 -> only w0 itself is feasible; solver must return it.
        scores = {"A": 5.0, "B": 4.0}
        bench = {"A": 0.5, "B": 0.5}
        out = ps.enhanced_index_weights(scores, bench, bench, turnover_cap=0.0, b_dev=0.0)
        assert out is not None
        assert out == {"A": 0.5, "B": 0.5}

    def test_enhanced_index_degenerate_none(self):
        assert ps.enhanced_index_weights({}, {}, {}) is None


# ---------------------------------------------------------------------------
# market_tradability
# ---------------------------------------------------------------------------


class TestMarketTradability:
    def test_limit_gate_blocks_buy_allows_sell(self):
        assert mt.limit_gate(0.11, 0.1) == "up"   # limit-up: untradable to buy
        assert mt.limit_gate(-0.11, 0.1) == "down"
        assert mt.limit_gate(0.05, 0.1) is None
        assert mt.limit_gate(0.11, 0.0) is None  # disabled

    def test_suspended(self):
        assert mt.suspended(None)
        assert mt.suspended(float("nan"))
        assert not mt.suspended(101.5)

    def test_volume_gate_truncates(self):
        assert mt.volume_gate(5000, 10_000, 0.2) == 2000
        assert mt.volume_gate(100, 10_000, 0.2) == 100  # under cap unchanged
        assert mt.volume_gate(5000, 0, 0.2) == 0        # no volume -> no fill

    def test_deal_price_selector(self):
        bar = {"close": 101.5, "open": 100.1, "high": 102.0, "low": 99.5}
        assert mt.deal_price_selector(bar, "open") == 100.1
        assert mt.deal_price_selector(bar, "vwap") == pytest.approx(101.0)
        assert mt.deal_price_selector(bar, ("open", "close")) == 100.1  # buy side
        assert mt.deal_price_selector({"close": None}, "close") is None

    def test_change_vs_prev(self):
        assert mt.change_vs_prev(110.0, 100.0) == pytest.approx(0.10)
        assert mt.change_vs_prev(None, 100.0) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
